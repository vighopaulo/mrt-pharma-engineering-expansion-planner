/**
 * bentleySpatialAdapter — READ-ONLY discovery of the live iModel's floor/room
 * spatial semantics, converted into the Bentley-free SpatialModelSemantics that
 * the pure association domain consumes.
 *
 * This is the ONLY spatial module that imports @itwin. It is reached via dynamic
 * import from DEV controls / the overlay so vitest never pulls the Bentley
 * stack. It NEVER modifies the iModel (no inserts, no changesets): it only runs
 * bounded ECSQL SELECTs and reads element ranges.
 *
 * Discovery is defensive: we do not assume a Revit/IFC schema. We probe for a
 * set of candidate BIS/spatial-composition classes, report what actually exists
 * with counts, and build floor/room references only from classes that are
 * genuinely present. Absence is reported honestly (NOT_AVAILABLE), never faked.
 */
import { IModelApp, type IModelConnection } from '@itwin/core-frontend'
import { QueryBinder, QueryRowFormat } from '@itwin/core-common'
import {
    EMPTY_MODEL_SEMANTICS,
    validateWorldRange,
    type SpatialFloorReference,
    type SpatialModelSemantics,
    type SpatialRoomReference,
    type SpatialSourceConfidence,
    type WorldRange3,
} from '../../domain/assets'

/** A discovered spatial class row for the inventory. */
export interface SpatialClassInventoryRow {
    classFullName: string
    count: number
    exampleElementId?: string
    exampleLabel?: string
}

export interface BimSpatialInventory {
    rows: SpatialClassInventoryRow[]
    floorSourceClass: string | 'NOT_AVAILABLE'
    roomSourceClass: string | 'NOT_AVAILABLE'
    roomObjectCount: number
    summary: string
}

/** Candidate class names to probe, ordered most→least specific. */
const FLOOR_CANDIDATE_CLASSES = [
    'BuildingSpatial:Story',
    'SpatialComposition:CompositeElement',
    'BisCore:SpatialLocationElement',
]
const ROOM_CANDIDATE_CLASSES = [
    'BuildingSpatial:Space',
    'SpatialComposition:SpatialStructureElement',
    'BisCore:SpatialLocationElement',
]

function getIModel(): IModelConnection | undefined {
    const vp = IModelApp.viewManager?.selectedView
    return vp?.iModel
}

/** Bounded count for a class; returns -1 if the class is not in the schema. */
async function safeCount(iModel: IModelConnection, classFullName: string): Promise<number> {
    const ecsql = classFullName.replace(':', '.')
    try {
        const reader = iModel.createQueryReader(
            `SELECT COUNT(*) FROM ${ecsql}`,
            undefined,
            { rowFormat: QueryRowFormat.UseECSqlPropertyIndexes },
        )
        for await (const row of reader) return Number(row[0]) || 0
        return 0
    } catch {
        // Class not present in this iModel's schema.
        return -1
    }
}

/** Fetch one example element (id + label) for a present class. */
async function safeExample(iModel: IModelConnection, classFullName: string): Promise<{ id?: string; label?: string }> {
    const ecsql = classFullName.replace(':', '.')
    try {
        const reader = iModel.createQueryReader(
            `SELECT ECInstanceId, UserLabel, CodeValue FROM ${ecsql} LIMIT 1`,
            undefined,
            { rowFormat: QueryRowFormat.UseECSqlPropertyIndexes },
        )
        for await (const row of reader) {
            return { id: String(row[0]), label: (row[1] as string) ?? (row[2] as string) ?? undefined }
        }
    } catch {
        /* ignore */
    }
    return {}
}

/**
 * Discover the spatial-class inventory (bounded). Read-only. Returns the set of
 * candidate classes that are actually present with counts + one example each.
 */
export async function discoverBimSpatialInventory(): Promise<BimSpatialInventory> {
    const iModel = getIModel()
    if (!iModel) {
        return { rows: [], floorSourceClass: 'NOT_AVAILABLE', roomSourceClass: 'NOT_AVAILABLE', roomObjectCount: 0, summary: 'NO_ACTIVE_VIEWPORT' }
    }
    const probe = Array.from(new Set([...FLOOR_CANDIDATE_CLASSES, ...ROOM_CANDIDATE_CLASSES]))
    const rows: SpatialClassInventoryRow[] = []
    for (const cls of probe) {
        const count = await safeCount(iModel, cls)
        if (count < 0) continue // not in schema
        const ex = count > 0 ? await safeExample(iModel, cls) : {}
        rows.push({ classFullName: cls, count, exampleElementId: ex.id, exampleLabel: ex.label })
    }
    const floorSourceClass = FLOOR_CANDIDATE_CLASSES.find((c) => rows.find((r) => r.classFullName === c && r.count > 0)) ?? 'NOT_AVAILABLE'
    const roomRow = ROOM_CANDIDATE_CLASSES
        .map((c) => rows.find((r) => r.classFullName === c && r.count > 0))
        .find((r) => r !== undefined)
    const roomSourceClass = roomRow?.classFullName ?? 'NOT_AVAILABLE'
    const roomObjectCount = roomRow?.count ?? 0

    const summary = rows.length === 0
        ? 'NO_CANDIDATE_SPATIAL_CLASSES_PRESENT'
        : rows.map((r) => `${r.classFullName}=${r.count}`).join(' | ')
    if (import.meta.env.DEV) {
        console.info('[bentley-spatial] INVENTORY %s | floorClass=%s roomClass=%s roomCount=%d',
            summary, floorSourceClass, roomSourceClass, roomObjectCount)
    }
    return { rows, floorSourceClass, roomSourceClass, roomObjectCount, summary }
}

/**
 * Read-only ARCHITECTURAL geometry inventory + honest visual classification of
 * the connected iModel. This is DIAGNOSTIC ONLY (Developer Mode / reporting): it
 * does NOT feed the floor/room association logic and does NOT change any
 * spatial-semantics behavior. It probes for architectural class candidates
 * (walls/slabs/floors/doors) and BuildingSpatial:Space, counts them, and returns
 * the deterministic classification from the pure planningPlan seam.
 *
 * Class names are probed defensively (no schema assumed); missing classes count
 * as 0. Never modifies the iModel.
 */
const WALL_CANDIDATE_CLASSES = ['BuildingPhysical:Wall', 'ArchitecturalPhysical:Wall', 'Building:Wall']
const SLAB_FLOOR_CANDIDATE_CLASSES = ['BuildingPhysical:Slab', 'ArchitecturalPhysical:Slab', 'BuildingPhysical:Floor', 'BuildingSpatial:Story']
const DOOR_CANDIDATE_CLASSES = ['BuildingPhysical:Door', 'ArchitecturalPhysical:Door', 'Building:Door']

async function sumCandidateCounts(iModel: IModelConnection, classes: string[]): Promise<number> {
    let total = 0
    for (const cls of classes) {
        const c = await safeCount(iModel, cls)
        if (c > 0) total += c
    }
    return total
}

export interface BimArchitecturalDiagnostic {
    wallCount: number
    slabOrFloorCount: number
    doorCount: number
    otherGeometricCount: number
    spaceCount: number
    /** From the pure classifyBimModel seam. */
    classification: string
    /** From the pure resolveNormalModePrimaryContext seam. */
    normalModePrimaryContext: string
    summary: string
}

export async function inspectBimArchitecturalInventory(): Promise<BimArchitecturalDiagnostic> {
    const empty: BimArchitecturalDiagnostic = {
        wallCount: 0, slabOrFloorCount: 0, doorCount: 0, otherGeometricCount: 0, spaceCount: 0,
        classification: 'OTHER', normalModePrimaryContext: 'MODEL_DEFAULT', summary: 'NO_ACTIVE_VIEWPORT',
    }
    const iModel = getIModel()
    if (!iModel) return empty

    const wallCount = await sumCandidateCounts(iModel, WALL_CANDIDATE_CLASSES)
    const slabOrFloorCount = await sumCandidateCounts(iModel, SLAB_FLOOR_CANDIDATE_CLASSES)
    const doorCount = await sumCandidateCounts(iModel, DOOR_CANDIDATE_CLASSES)
    const spaceCount = Math.max(0, await safeCount(iModel, 'BuildingSpatial:Space'))
    const totalGeom = Math.max(0, await safeCount(iModel, 'BisCore:GeometricElement3d'))
    const otherGeometricCount = Math.max(0, totalGeom - wallCount - slabOrFloorCount - doorCount)

    // Pure classification (Bentley-free seam).
    const { classifyBimModel, resolveNormalModePrimaryContext } = await import('./planningPlan')
    const inv = { wallCount, slabOrFloorCount, doorCount, otherGeometricCount, spaceCount }
    const classification = classifyBimModel(inv)
    const normalModePrimaryContext = resolveNormalModePrimaryContext(classification)
    const summary = `walls=${wallCount} slabs/floors=${slabOrFloorCount} doors=${doorCount} spaces=${spaceCount} otherGeom=${otherGeometricCount} => ${classification}`
    if (import.meta.env.DEV) console.info('[bentley-spatial] ARCH_INVENTORY %s', summary)
    return { ...inv, classification, normalModePrimaryContext, summary }
}

/**
 * Read a spatial element's world bounding range from its placement bbox.
 *
 * NaN ROOT CAUSE (previous defect): selecting the point/struct columns
 * `BBoxLow`/`BBoxHigh` directly under UseECSqlPropertyIndexes returned struct
 * objects whose `.x/.y/.z` were not decomposed, so `lo.x + origin.x` produced
 * `undefined + number = NaN`, and the NaN range was accepted as RANGE_ONLY.
 *
 * FIX: select EXPLICIT SCALAR coordinate columns (BBoxLow.X, .Y, .Z, ...) so
 * every value arrives as a number, then validate finiteness via the pure
 * domain `validateWorldRange` before returning. Any non-finite / malformed
 * result yields undefined (the room becomes METADATA_ONLY, never a fake range).
 * Only GeometricElement3d subclasses have a placement bbox; non-geometric Space
 * objects legitimately return undefined here.
 */
async function elementRange(iModel: IModelConnection, elementId: string): Promise<WorldRange3 | undefined> {
    // 1) Placement bbox on GeometricElement3d (local bbox + placement origin).
    try {
        const reader = iModel.createQueryReader(
            `SELECT
                BBoxLow.X, BBoxLow.Y, BBoxLow.Z,
                BBoxHigh.X, BBoxHigh.Y, BBoxHigh.Z,
                Origin.X, Origin.Y, Origin.Z
             FROM bis.GeometricElement3d WHERE ECInstanceId=?`,
            QueryBinder.from([elementId]),
            { rowFormat: QueryRowFormat.UseECSqlPropertyIndexes },
        )
        for await (const row of reader) {
            const lx = Number(row[0]), ly = Number(row[1]), lz = Number(row[2])
            const hx = Number(row[3]), hy = Number(row[4]), hz = Number(row[5])
            const ox = Number(row[6] ?? 0), oy = Number(row[7] ?? 0), oz = Number(row[8] ?? 0)
            // Local bbox offset by placement origin (yaw ignored for a
            // conservative axis-aligned world range — RANGE_ONLY authority).
            // validateWorldRange rejects any non-finite coordinate.
            const placement = validateWorldRange({
                low: { x: lx + ox, y: ly + oy, z: lz + oz },
                high: { x: hx + ox, y: hy + oy, z: hz + oz },
            })
            if (placement) return placement
            break // row existed but bbox was null/degenerate — fall through.
        }
    } catch {
        /* element is not a GeometricElement3d / has no placement — try index. */
    }

    // 2) Fallback: the persistent spatial R-tree index (bis.SpatialIndex) carries
    //    a WORLD-aligned min/max for every spatial element that has geometry —
    //    including BuildingSpatial:Space rows whose direct placement bbox is
    //    null/degenerate (a common IFC-space case). This is why the clinical
    //    overlay footprint was not found. Read-only; validated for finiteness.
    try {
        const reader = iModel.createQueryReader(
            `SELECT MinX, MinY, MinZ, MaxX, MaxY, MaxZ FROM bis.SpatialIndex WHERE ECInstanceId=?`,
            QueryBinder.from([elementId]),
            { rowFormat: QueryRowFormat.UseECSqlPropertyIndexes },
        )
        for await (const row of reader) {
            return validateWorldRange({
                low: { x: Number(row[0]), y: Number(row[1]), z: Number(row[2]) },
                high: { x: Number(row[3]), y: Number(row[4]), z: Number(row[5]) },
            })
        }
    } catch {
        /* SpatialIndex not queryable in this iModel — no range. */
    }
    return undefined
}

/**
 * Build a Bentley-free SpatialModelSemantics from the live iModel. When explicit
 * room/space objects exist, room references are created with whatever geometry
 * authority is available (RANGE_ONLY from placement bbox in this foundation —
 * VOLUME/FOOTPRINT extraction is a future refinement). When they do not exist,
 * availability is reported NOT_AVAILABLE and the pure layer will honestly report
 * NOT_AVAILABLE_FROM_BIM.
 */
export async function buildModelSemantics(maxRooms = 200): Promise<SpatialModelSemantics> {
    const iModel = getIModel()
    if (!iModel) return { ...EMPTY_MODEL_SEMANTICS }
    const inventory = await discoverBimSpatialInventory()

    const floors: SpatialFloorReference[] = []
    const rooms: SpatialRoomReference[] = []
    let floorAvailability: SpatialSourceConfidence = 'NOT_AVAILABLE'
    let roomAvailability: SpatialSourceConfidence = 'NOT_AVAILABLE'

    // Floors.
    if (inventory.floorSourceClass !== 'NOT_AVAILABLE') {
        floorAvailability = 'AUTHORITATIVE_BIM'
        const ecsql = inventory.floorSourceClass.replace(':', '.')
        try {
            const reader = iModel.createQueryReader(
                `SELECT ECInstanceId, UserLabel, CodeValue FROM ${ecsql} LIMIT 100`,
                undefined,
                { rowFormat: QueryRowFormat.UseECSqlPropertyIndexes },
            )
            for await (const row of reader) {
                const id = String(row[0])
                const label = (row[1] as string) ?? (row[2] as string) ?? `Floor ${id}`
                const range = await elementRange(iModel, id)
                floors.push({
                    floorId: id,
                    displayName: label,
                    sourceClass: inventory.floorSourceClass,
                    sourceElementId: id,
                    confidence: 'AUTHORITATIVE_BIM',
                    verticalRange: range ? { zLow: range.low.z, zHigh: range.high.z } : undefined,
                    elevation: range ? range.low.z : undefined,
                })
            }
        } catch { /* ignore */ }
        // Honesty: SpatialComposition:CompositeElement are composite/structure
        // nodes, not necessarily storeys, and frequently carry NO placement
        // geometry. If no floor exposes a usable vertical range OR elevation,
        // we do NOT claim AUTHORITATIVE_BIM floor authority — association will
        // then honestly report NOT_FOUND_AT_POSITION rather than a fake floor.
        const anyFloorRange = floors.some((f) => f.verticalRange)
        const anyFloorElev = floors.some((f) => typeof f.elevation === 'number')
        if (!anyFloorRange && !anyFloorElev) floorAvailability = 'NOT_AVAILABLE'
        else if (!anyFloorRange) floorAvailability = 'DERIVED'
    }

    // Rooms.
    if (inventory.roomSourceClass !== 'NOT_AVAILABLE') {
        roomAvailability = 'AUTHORITATIVE_BIM'
        const ecsql = inventory.roomSourceClass.replace(':', '.')
        try {
            const reader = iModel.createQueryReader(
                `SELECT ECInstanceId, UserLabel, CodeValue FROM ${ecsql} LIMIT ${Math.max(1, Math.min(maxRooms, 1000))}`,
                undefined,
                { rowFormat: QueryRowFormat.UseECSqlPropertyIndexes },
            )
            const ids: { id: string; label: string }[] = []
            for await (const row of reader) {
                const id = String(row[0])
                ids.push({ id, label: (row[1] as string) ?? (row[2] as string) ?? `Room ${id}` })
            }
            for (const { id, label } of ids) {
                const range = await elementRange(iModel, id)
                rooms.push({
                    roomId: id,
                    displayName: label,
                    sourceClass: inventory.roomSourceClass,
                    sourceElementId: id,
                    confidence: 'AUTHORITATIVE_BIM',
                    geometryType: range ? 'RANGE_ONLY' : 'METADATA_ONLY',
                    range: range ? { low: { ...range.low }, high: { ...range.high } } : undefined,
                })
            }
        } catch { /* ignore */ }
        // ROOM_SOURCE_CONFIDENCE (that the BIM defines rooms) is distinct from
        // ROOM_GEOMETRY_CAPABILITY (whether containment can be tested). If the
        // rooms exist but expose no usable geometry, source stays AUTHORITATIVE_BIM
        // — the pure associateRoom() then reports NOT_AVAILABLE_FROM_BIM for
        // containment (never a false NOT_FOUND). If zero rooms were read, there
        // is no room semantics at all.
        if (rooms.length === 0) roomAvailability = 'NOT_AVAILABLE'
    }

    return {
        floors,
        rooms,
        floorAvailability,
        roomAvailability,
        inventorySummary: inventory.summary,
    }
}

/**
 * Bounded DEV diagnostic: list the discovered room ranges (id, label, low/high,
 * geometry type). Read-only. Intended for a small number of spaces (e.g. 8);
 * capped so it never dumps arbitrary geometry.
 */
export async function summarizeRoomRanges(max = 12): Promise<string> {
    const semantics = await buildModelSemantics()
    if (semantics.rooms.length === 0) return `NO_ROOMS (roomAvail=${semantics.roomAvailability})`
    const usable = semantics.rooms.filter((r) => !!r.range && (r.geometryType === 'RANGE_ONLY' || r.geometryType === 'VOLUME')).length
    const lines = semantics.rooms.slice(0, max).map((r) => {
        // r.range is a finite, validated WorldRange3 or undefined — never NaN.
        const range = r.range
            ? `low=(${r.range.low.x.toFixed(1)},${r.range.low.y.toFixed(1)},${r.range.low.z.toFixed(1)}) high=(${r.range.high.x.toFixed(1)},${r.range.high.y.toFixed(1)},${r.range.high.z.toFixed(1)})`
            : 'RANGE_UNAVAILABLE'
        return `#${r.roomId}[${r.displayName}] ${r.geometryType} ${range}`
    })
    const summary = `rooms=${semantics.rooms.length} usableRanges=${usable} roomAvail=${semantics.roomAvailability} | ${lines.join(' || ')}`
    if (import.meta.env.DEV) console.info('[bentley-spatial] ROOM_RANGES %s', summary)
    return summary
}

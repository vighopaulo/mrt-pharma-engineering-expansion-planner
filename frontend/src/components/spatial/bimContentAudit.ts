/**
 * bimContentAudit — READ-ONLY diagnostic audit of the connected iModel's actual
 * geometric content. Runs bounded ECSQL SELECTs + schema/class metadata queries
 * to answer: does this iModel contain detailed architectural hospital geometry,
 * or is it a simplified spatial-semantic / development fixture?
 *
 * DIAGNOSTIC ONLY. It is NOT wired into product behavior. It creates/deletes/
 * modifies NOTHING, changes no display/visibility/ViewFlags, and never prints
 * secrets. It is reached from a single DEV-drawer button so the user can run it
 * in the authenticated browser session (the only place the live iModel exists).
 *
 * Output is bounded: counts, top classes, a handful of representative examples.
 */
import { IModelApp, type IModelConnection } from '@itwin/core-frontend'

function getIModel(): IModelConnection | undefined {
    return IModelApp.viewManager?.selectedView?.iModel
}

async function scalar(iModel: IModelConnection, ecsql: string): Promise<number> {
    try {
        const reader = iModel.createQueryReader(ecsql)
        for await (const row of reader) return Number(row[0]) || 0
        return 0
    } catch {
        return -1
    }
}

/** Grouped geometric-element class counts (top N by count, descending). */
async function geometricClassCounts(iModel: IModelConnection, topN = 25): Promise<{ className: string; count: number }[]> {
    const rows: { className: string; count: number }[] = []
    try {
        const reader = iModel.createQueryReader(
            `SELECT ec_classname(ECClassId), COUNT(*) AS n FROM bis.GeometricElement3d GROUP BY ECClassId ORDER BY n DESC`,
        )
        for await (const row of reader) {
            rows.push({ className: String(row[0]), count: Number(row[1]) || 0 })
            if (rows.length >= topN) break
        }
    } catch { /* GeometricElement3d absent */ }
    return rows
}

/** Present schemas (bounded). */
async function schemaNames(iModel: IModelConnection): Promise<string[]> {
    const names: string[] = []
    try {
        const reader = iModel.createQueryReader(`SELECT Name FROM meta.ECSchemaDef ORDER BY Name`)
        for await (const row of reader) names.push(String(row[0]))
    } catch { /* meta unavailable */ }
    return names
}

/**
 * Search class metadata for class names matching any of the given terms
 * (case-insensitive substring), then count instances of each match. Returns the
 * matches that actually exist, with counts. Bounded.
 */
async function findClassesByTerms(iModel: IModelConnection, terms: string[]): Promise<{ className: string; count: number }[]> {
    const out: { className: string; count: number }[] = []
    try {
        // Join class + schema names so we can build a fully-qualified name.
        const reader = iModel.createQueryReader(
            `SELECT s.Name, c.Name FROM meta.ECClassDef c JOIN meta.ECSchemaDef s ON c.Schema.Id = s.ECInstanceId`,
        )
        const candidates: string[] = []
        for await (const row of reader) {
            const schema = String(row[0])
            const cls = String(row[1])
            const lc = cls.toLowerCase()
            if (terms.some((t) => lc.includes(t.toLowerCase()))) candidates.push(`${schema}.${cls}`)
        }
        for (const full of candidates) {
            // Only count classes that are geometric/instantiable; ignore failures.
            const n = await scalar(iModel, `SELECT COUNT(*) FROM ${full}`)
            if (n >= 0) out.push({ className: full, count: n })
        }
    } catch { /* meta unavailable */ }
    return out.sort((a, b) => b.count - a.count)
}

/** Bounded room inventory (id + label + geometric-range presence). */
async function roomInventory(iModel: IModelConnection, limit = 40): Promise<{ id: string; label: string; hasRange: boolean }[]> {
    const out: { id: string; label: string; hasRange: boolean }[] = []
    try {
        const reader = iModel.createQueryReader(
            `SELECT ECInstanceId, UserLabel, CodeValue FROM BuildingSpatial.Space LIMIT ${limit}`,
        )
        for await (const row of reader) {
            const id = String(row[0])
            const label = (row[1] as string) ?? (row[2] as string) ?? '(unlabeled)'
            let hasRange = false
            try {
                const r = iModel.createQueryReader(
                    `SELECT BBoxLow.X FROM bis.GeometricElement3d WHERE ECInstanceId=${id}`,
                )
                for await (const _rr of r) { hasRange = true; break }
            } catch { /* not geometric */ }
            out.push({ id, label, hasRange })
        }
    } catch { /* Space absent */ }
    return out
}

export interface BimContentAudit {
    modelCount: number
    geometricModelCount: number
    schemas: string[]
    geometricClassCounts: { className: string; count: number }[]
    geometricElement3dCount: number
    physicalElementCount: number
    spatialLocationElementCount: number
    buildingSpatialSpaceCount: number
    buildingSpatialStoryCount: number
    spatialCompositionCompositeCount: number
    spatialCompositionStructureCount: number
    wallLikeClasses: { className: string; count: number }[]
    slabFloorLikeClasses: { className: string; count: number }[]
    doorLikeClasses: { className: string; count: number }[]
    windowLikeClasses: { className: string; count: number }[]
    ceilingRoofLikeClasses: { className: string; count: number }[]
    rooms: { id: string; label: string; hasRange: boolean }[]
    /** The iModel id the audit actually ran against (never a silent fallback). */
    activeIModelId: string
    classification: string
    summary: string
}

/**
 * Run the full read-only content audit. Safe to call from a DEV button. Returns
 * a bounded, serializable snapshot suitable for the Developer Inspector + the
 * audit report. NEVER modifies the iModel.
 */
export async function runBimContentAudit(): Promise<BimContentAudit> {
    const iModel = getIModel()
    const empty: BimContentAudit = {
        modelCount: 0, geometricModelCount: 0, schemas: [], geometricClassCounts: [],
        geometricElement3dCount: 0, physicalElementCount: 0, spatialLocationElementCount: 0,
        buildingSpatialSpaceCount: 0, buildingSpatialStoryCount: 0,
        spatialCompositionCompositeCount: 0, spatialCompositionStructureCount: 0,
        wallLikeClasses: [], slabFloorLikeClasses: [], doorLikeClasses: [],
        windowLikeClasses: [], ceilingRoofLikeClasses: [], rooms: [],
        activeIModelId: 'NO_ACTIVE_VIEWPORT',
        classification: 'NO_ACTIVE_VIEWPORT', summary: 'NO_ACTIVE_VIEWPORT',
    }
    if (!iModel) return empty
    const activeIModelId = (iModel as unknown as { iModelId?: string }).iModelId ?? 'UNKNOWN'

    const modelCount = Math.max(0, await scalar(iModel, `SELECT COUNT(*) FROM bis.Model`))
    const geometricModelCount = Math.max(0, await scalar(iModel, `SELECT COUNT(*) FROM bis.GeometricModel`))
    const schemas = await schemaNames(iModel)
    const geometricClassCountsRows = await geometricClassCounts(iModel)
    const geometricElement3dCount = Math.max(0, await scalar(iModel, `SELECT COUNT(*) FROM bis.GeometricElement3d`))
    const physicalElementCount = Math.max(0, await scalar(iModel, `SELECT COUNT(*) FROM bis.PhysicalElement`))
    const spatialLocationElementCount = Math.max(0, await scalar(iModel, `SELECT COUNT(*) FROM bis.SpatialLocationElement`))
    const buildingSpatialSpaceCount = Math.max(0, await scalar(iModel, `SELECT COUNT(*) FROM BuildingSpatial.Space`))
    const buildingSpatialStoryCount = Math.max(0, await scalar(iModel, `SELECT COUNT(*) FROM BuildingSpatial.Story`))
    const spatialCompositionCompositeCount = Math.max(0, await scalar(iModel, `SELECT COUNT(*) FROM SpatialComposition.CompositeElement`))
    const spatialCompositionStructureCount = Math.max(0, await scalar(iModel, `SELECT COUNT(*) FROM SpatialComposition.SpatialStructureElement`))

    const wallLikeClasses = await findClassesByTerms(iModel, ['Wall', 'Partition', 'CurtainWall'])
    const slabFloorLikeClasses = await findClassesByTerms(iModel, ['Slab', 'Floor', 'Deck', 'Plate'])
    const doorLikeClasses = await findClassesByTerms(iModel, ['Door', 'Opening'])
    const windowLikeClasses = await findClassesByTerms(iModel, ['Window', 'Glazing'])
    const ceilingRoofLikeClasses = await findClassesByTerms(iModel, ['Ceiling', 'Roof'])
    const rooms = await roomInventory(iModel)

    const wallTotal = wallLikeClasses.reduce((s, c) => s + Math.max(0, c.count), 0)
    const slabTotal = slabFloorLikeClasses.reduce((s, c) => s + Math.max(0, c.count), 0)
    const doorTotal = doorLikeClasses.reduce((s, c) => s + Math.max(0, c.count), 0)
    const anyArch = wallTotal > 0 || slabTotal > 0 || doorTotal > 0
    let classification: string
    if (wallTotal >= 4 && slabTotal >= 1) classification = 'DETAILED_ARCHITECTURAL_BIM'
    else if (anyArch) classification = 'PARTIAL_ARCHITECTURAL_BIM'
    else if (buildingSpatialSpaceCount > 0 && geometricElement3dCount <= Math.max(40, buildingSpatialSpaceCount * 3))
        classification = 'SIMPLIFIED_DEVELOPMENT_TEST_FIXTURE'
    else if (buildingSpatialSpaceCount > 0) classification = 'SPATIAL_SEMANTIC_MODEL_WITH_LIMITED_ARCHITECTURE'
    else classification = 'OTHER'

    const summary = [
        `models=${modelCount}(geom=${geometricModelCount})`,
        `geomEl3d=${geometricElement3dCount}`,
        `physical=${physicalElementCount}`,
        `spatialLoc=${spatialLocationElementCount}`,
        `space=${buildingSpatialSpaceCount}`,
        `story=${buildingSpatialStoryCount}`,
        `composite=${spatialCompositionCompositeCount}`,
        `walls=${wallTotal}`,
        `slabs/floors=${slabTotal}`,
        `doors=${doorTotal}`,
        `=> ${classification}`,
    ].join(' | ')
    if (import.meta.env.DEV) console.info('[bim-audit] %s', summary)

    return {
        modelCount, geometricModelCount, schemas, geometricClassCounts: geometricClassCountsRows,
        geometricElement3dCount, physicalElementCount, spatialLocationElementCount,
        buildingSpatialSpaceCount, buildingSpatialStoryCount,
        spatialCompositionCompositeCount, spatialCompositionStructureCount,
        wallLikeClasses, slabFloorLikeClasses, doorLikeClasses, windowLikeClasses, ceilingRoofLikeClasses,
        rooms, activeIModelId, classification, summary,
    }
}

/** Human-readable multi-line report for the Developer Inspector. */
export function formatBimContentAudit(a: BimContentAudit): string {
    const cls = (rows: { className: string; count: number }[]) =>
        rows.length ? rows.map((r) => `${r.className}=${r.count}`).join(', ') : 'NONE'
    const topGeom = a.geometricClassCounts.length
        ? a.geometricClassCounts.map((r) => `  ${r.className} = ${r.count}`).join('\n')
        : '  (none)'
    const roomLines = a.rooms.length
        ? a.rooms.map((r) => `  ${r.label} [${r.id}] range=${r.hasRange ? 'YES' : 'no'}`).join('\n')
        : '  (none)'
    return [
        `ACTIVE_IMODEL_ID = ${a.activeIModelId}`,
        `CLASSIFICATION = ${a.classification}`,
        `SUMMARY = ${a.summary}`,
        '',
        `models = ${a.modelCount} (geometric ${a.geometricModelCount})`,
        `schemas = ${a.schemas.join(', ') || '(none)'}`,
        '',
        `GeometricElement3d = ${a.geometricElement3dCount}`,
        `PhysicalElement = ${a.physicalElementCount}`,
        `SpatialLocationElement = ${a.spatialLocationElementCount}`,
        `BuildingSpatial:Space = ${a.buildingSpatialSpaceCount}`,
        `BuildingSpatial:Story = ${a.buildingSpatialStoryCount}`,
        `SpatialComposition:CompositeElement = ${a.spatialCompositionCompositeCount}`,
        `SpatialComposition:SpatialStructureElement = ${a.spatialCompositionStructureCount}`,
        '',
        `wall-like = ${cls(a.wallLikeClasses)}`,
        `slab/floor-like = ${cls(a.slabFloorLikeClasses)}`,
        `door-like = ${cls(a.doorLikeClasses)}`,
        `window-like = ${cls(a.windowLikeClasses)}`,
        `ceiling/roof-like = ${cls(a.ceilingRoofLikeClasses)}`,
        '',
        'top geometric classes:',
        topGeom,
        '',
        'rooms:',
        roomLines,
    ].join('\n')
}

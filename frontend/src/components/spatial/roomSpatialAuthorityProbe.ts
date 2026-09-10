/**
 * roomSpatialAuthorityProbe — DEV-only, READ-ONLY live probe of the true spatial
 * authority available for a single BIM space (the persisted Uptake 01 target).
 *
 * It inspects the exact bimSpaceId (identity authority — never a name/nearest
 * search) and gathers bounded evidence: EC class + hierarchy, geometry stream /
 * placement / calculated range / spatial-index range, IFC space representation,
 * spatial hierarchy (parent/children), physical containment + boundary
 * relationships (walls/doors/openings/slabs), adjacency. It then classifies the
 * strongest authority via the pure classifyRoomSpatialAuthority seam.
 *
 * No Bentley writes, no token logging, bounded output. This build ONLY diagnoses;
 * it does not change the overlay.
 */
import { IModelApp, type IModelConnection } from '@itwin/core-frontend'
import { QueryBinder, QueryRowFormat } from '@itwin/core-common'
import {
    classifyRoomSpatialAuthority,
    overlaySourceForAuthority,
    type RoomSpatialAuthorityEvidence,
} from './roomSpatialAuthority'

function activeIModel(): IModelConnection | undefined {
    return IModelApp.viewManager?.selectedView?.iModel
}

/** Index-accessible row view (matches the existing adapter's row[i] usage). */
type RowLike = { [i: number]: unknown }

/** One scalar row helper (bounded, read-only). Returns undefined on any error. */
async function firstRow(iModel: IModelConnection, ecsql: string, binds?: unknown[]): Promise<RowLike | undefined> {
    try {
        const reader = iModel.createQueryReader(
            ecsql,
            binds ? QueryBinder.from(binds) : undefined,
            { rowFormat: QueryRowFormat.UseECSqlPropertyIndexes },
        )
        for await (const row of reader) return row as unknown as RowLike
    } catch { /* class/relationship absent */ }
    return undefined
}

/** Bounded COUNT for a query; -1 when the query fails (class absent). */
async function countRows(iModel: IModelConnection, ecsql: string, binds?: unknown[]): Promise<number> {
    const row = await firstRow(iModel, ecsql, binds)
    if (!row) return -1
    const n = Number(row[0])
    return Number.isFinite(n) ? n : -1
}

const WALL_CLASSES = ['BuildingPhysical.Wall', 'ArchitecturalPhysical.Wall', 'Building.Wall']
const DOOR_CLASSES = ['BuildingPhysical.Door', 'ArchitecturalPhysical.Door', 'Building.Door']

/**
 * Run the read-only spatial-authority probe for one bimSpaceId. Returns a bounded
 * multi-line summary and the classified authority.
 */
export async function probeRoomSpatialAuthority(input: { bimSpaceId: string; originalBimLabel: string }): Promise<string> {
    const iModel = activeIModel()
    const L: string[] = []
    L.push('=== UPTAKE 01 SPATIAL AUTHORITY DIAGNOSTIC ===')
    L.push(`TARGET = ${input.originalBimLabel}`)
    L.push(`BIM_SPACE_ID = ${input.bimSpaceId}`)
    if (!iModel) { L.push('NO_ACTIVE_VIEWPORT'); return L.join('\n') }
    if (!input.bimSpaceId) { L.push('NO_BIM_SPACE_ID'); return L.join('\n') }

    // --- identity + EC class ---
    const idRow = await firstRow(iModel, 'SELECT ECClassId, Model.Id, CodeValue, UserLabel FROM bis.Element WHERE ECInstanceId=?', [input.bimSpaceId])
    let ecClassName = 'UNKNOWN'
    if (idRow) {
        // ECClassId resolves to a name via meta.ECClassDef.
        const clsRow = await firstRow(iModel, 'SELECT Name, Schema.Id FROM meta.ECClassDef WHERE ECInstanceId=?', [idRow[0]])
        ecClassName = clsRow ? String(clsRow[0]) : String(idRow[0])
        L.push('--- identity ---')
        L.push(`EC_CLASS = ${ecClassName}`)
        L.push(`modelId present = ${idRow[1] ? 'YES' : 'NO'} codeValue=${idRow[2] ?? '—'} userLabel=${idRow[3] ?? '—'}`)
    } else {
        L.push('EC_CLASS = ELEMENT_NOT_FOUND')
    }

    // --- class hierarchy (is it a GeometricElement3d / SpatialLocationElement?) ---
    // Probe by attempting membership queries against candidate base classes.
    const isGeometric = (await countRows(iModel, 'SELECT COUNT(*) FROM bis.GeometricElement3d WHERE ECInstanceId=?', [input.bimSpaceId])) > 0
    const isSpatialLocation = (await countRows(iModel, 'SELECT COUNT(*) FROM bis.SpatialLocationElement WHERE ECInstanceId=?', [input.bimSpaceId])) > 0
    L.push('--- class hierarchy ---')
    L.push(`derivesFrom GeometricElement3d = ${isGeometric ? 'YES' : 'NO'} · SpatialLocationElement = ${isSpatialLocation ? 'YES' : 'NO'}`)

    // --- geometry stream / placement / ranges ---
    let hasPlacement = false
    let hasCalculatedRange = false
    if (isGeometric) {
        const geomRow = await firstRow(iModel, 'SELECT Origin.X, BBoxLow.X, BBoxHigh.X, GeometryStream FROM bis.GeometricElement3d WHERE ECInstanceId=?', [input.bimSpaceId])
        if (geomRow) {
            hasPlacement = Number.isFinite(Number(geomRow[0]))
            hasCalculatedRange = Number.isFinite(Number(geomRow[1])) && Number.isFinite(Number(geomRow[2]))
        }
    }
    const idxRow = await firstRow(iModel, 'SELECT MinX, MinY, MinZ, MaxX, MaxY, MaxZ FROM bis.SpatialIndex WHERE ECInstanceId=?', [input.bimSpaceId])
    const hasSpatialIndexRange = !!idxRow && [0, 1, 2, 3, 4, 5].every((i) => Number.isFinite(Number(idxRow[i])))
    // A geometry stream is a stronger signal than a range; probe it separately.
    const geomStreamRow = isGeometric ? await firstRow(iModel, 'SELECT GeometryStream FROM bis.GeometricElement3d WHERE ECInstanceId=? AND GeometryStream IS NOT NULL', [input.bimSpaceId]) : undefined
    const hasGeometryStream = !!geomStreamRow
    L.push('--- geometry ---')
    L.push(`SPACE_GEOMETRY_STREAM = ${isGeometric ? (hasGeometryStream ? 'YES' : 'NO') : 'NOT_AVAILABLE'}`)
    L.push(`SPACE_PLACEMENT = ${isGeometric ? (hasPlacement ? 'YES' : 'NO') : 'NOT_AVAILABLE'}`)
    L.push(`SPACE_CALCULATED_RANGE = ${isGeometric ? (hasCalculatedRange ? 'YES' : 'NO') : 'NOT_AVAILABLE'}`)
    L.push(`SPACE_SPATIAL_INDEX_RANGE = ${hasSpatialIndexRange ? 'YES' : 'NO'}`)
    if (idxRow && hasSpatialIndexRange) {
        L.push(`  index range low=(${Number(idxRow[0]).toFixed(1)},${Number(idxRow[1]).toFixed(1)},${Number(idxRow[2]).toFixed(1)}) high=(${Number(idxRow[3]).toFixed(1)},${Number(idxRow[4]).toFixed(1)},${Number(idxRow[5]).toFixed(1)})`)
    }
    L.push(`SPATIAL_INDEX_RANGE_COUNTS_AS_EXACT_BOUNDARY = NO`)

    // --- IFC space representation (probe common IFC-derived aspect classes) ---
    let ifcRepFound = false
    for (const cls of ['ifc.IfcSpace', 'IfcDynamic.IfcSpace', 'ifc2x3.IfcSpace', 'ifc4.IfcSpace']) {
        const c = await countRows(iModel, `SELECT COUNT(*) FROM ${cls} WHERE ECInstanceId=?`, [input.bimSpaceId])
        if (c > 0) { ifcRepFound = true; break }
    }
    L.push('--- ifc representation ---')
    L.push(`IFC_SPACE_REPRESENTATION_SEARCH = PERFORMED`)
    L.push(`IFC_SPACE_REPRESENTATION_FOUND = ${ifcRepFound ? 'YES' : 'NO'}`)

    // --- authoritative space boundary (exact polygon/shell) ---
    // Only a real geometry stream on the Space itself counts as exact geometry.
    const authoritativeBoundaryFound = hasGeometryStream
    L.push('--- authoritative boundary ---')
    L.push(`AUTHORITATIVE_SPACE_BOUNDARY_FOUND = ${authoritativeBoundaryFound ? 'YES' : 'NO'}`)

    // --- spatial hierarchy (parent + children via bis.ElementOwnsChildElements) ---
    const parentRow = await firstRow(iModel, 'SELECT Parent.Id FROM bis.Element WHERE ECInstanceId=?', [input.bimSpaceId])
    const childCount = await countRows(iModel, 'SELECT COUNT(*) FROM bis.Element WHERE Parent.Id=?', [input.bimSpaceId])
    L.push('--- spatial hierarchy ---')
    L.push(`parent present = ${parentRow && parentRow[0] ? 'YES' : 'NO'} · childElements = ${childCount < 0 ? 'n/a' : childCount}`)

    // --- physical containment + boundary relationships ---
    // Elements contained in this spatial element (bis.SpatialElementIsInSpatialStructure-style).
    const containedCount = await countRows(iModel, 'SELECT COUNT(*) FROM bis.GeometricElement3d WHERE Parent.Id=?', [input.bimSpaceId])
    let wallCount = 0
    for (const cls of WALL_CLASSES) { const c = await countRows(iModel, `SELECT COUNT(*) FROM ${cls} WHERE Parent.Id=?`, [input.bimSpaceId]); if (c > 0) wallCount += c }
    let doorCount = 0
    for (const cls of DOOR_CLASSES) { const c = await countRows(iModel, `SELECT COUNT(*) FROM ${cls} WHERE Parent.Id=?`, [input.bimSpaceId]); if (c > 0) doorCount += c }
    // Explicit IFC space-boundary relationships (RelSpaceBoundary), if present.
    let explicitBoundaryRelCount = -1
    for (const cls of ['ifc.IfcRelSpaceBoundary', 'ifc2x3.IfcRelSpaceBoundary', 'ifc4.IfcRelSpaceBoundary']) {
        const c = await countRows(iModel, `SELECT COUNT(*) FROM ${cls}`, undefined)
        if (c >= 0) { explicitBoundaryRelCount = c; break }
    }
    L.push('--- physical containment / boundaries ---')
    L.push(`SPACE_PHYSICAL_CONTAINMENT_SEARCH = PERFORMED · containedGeometric = ${containedCount < 0 ? 'n/a' : containedCount}`)
    L.push(`SPACE_BOUNDARY_RELATIONSHIP_SEARCH = PERFORMED`)
    L.push(`BOUNDARY_WALLS = ${wallCount} · BOUNDARY_DOORS = ${doorCount}`)
    L.push(`EXPLICIT_BOUNDARY_RELATIONSHIPS(IfcRelSpaceBoundary) = ${explicitBoundaryRelCount < 0 ? 'NOT_AVAILABLE' : explicitBoundaryRelCount}`)

    // --- adjacency ---
    L.push(`ADJACENT_SPACES = ${explicitBoundaryRelCount > 0 ? 'DERIVABLE_FROM_RELATIONSHIPS' : 'NOT_AVAILABLE'}`)

    // --- physical-boundary derivation feasibility (bounded, conservative) ---
    // Feasible only if the space directly owns enough wall geometry to close a region.
    const physicalBoundaryDerivationFeasible = wallCount >= 3
    L.push(`PHYSICAL_BOUNDARY_DERIVATION_FEASIBLE = ${physicalBoundaryDerivationFeasible ? 'YES' : 'NO'}`)

    // --- classify (pure seam) ---
    const evidence: RoomSpatialAuthorityEvidence = {
        hasExactSpaceGeometry: authoritativeBoundaryFound,
        hasExplicitBoundaryRelationships: explicitBoundaryRelCount > 0,
        physicalBoundaryDerivationFeasible,
        hasRange: hasSpatialIndexRange || hasCalculatedRange,
        hasAnchor: hasSpatialIndexRange || hasCalculatedRange || hasPlacement,
    }
    const cls = classifyRoomSpatialAuthority(evidence)
    L.push('--- classification ---')
    L.push(`ROOM_SPATIAL_AUTHORITY_CLASS = ${cls}`)
    L.push(`NEXT_OVERLAY_SOURCE (advisory) = ${overlaySourceForAuthority(cls)}`)
    L.push('NOTE: overlay UNCHANGED this build (diagnostic-first).')

    const out = L.join('\n')
    if (import.meta.env.DEV) console.info('[room-spatial-authority]\n%s', out)
    return out
}

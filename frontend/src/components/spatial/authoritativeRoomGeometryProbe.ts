/**
 * authoritativeRoomGeometryProbe — DEV/runtime READ-ONLY extraction of the true
 * IfcSpace geometry for a BIM space, feeding the pure footprint seam.
 *
 * Uses IModelConnection.generateElementMeshes (read-only; no writes, no changeset)
 * to obtain polyfaces for the exact bimSpaceId, flattens them into a world-space
 * triangle mesh, and derives the true room footprint + interior anchor via the
 * pure authoritativeRoomFootprint seam. If extraction yields no usable geometry
 * the result is NOT_AVAILABLE — the caller must NOT silently fall back to the
 * range rectangle.
 */
import { IModelApp, type IModelConnection } from '@itwin/core-frontend'
import { readElementMeshes } from '@itwin/core-common'
import {
    deriveAuthoritativeRoomFootprint,
    resolveRoomInteriorAnchor,
    characterizeAuthoritativeRoomVolume,
    polygonArea,
    type RoomMesh,
    type RoomFootprintResult,
    type RoomVolumeCharacterization,
    type Vec2,
} from './authoritativeRoomFootprint'

export interface AuthoritativeRoomGeometry {
    bimSpaceId: string
    /** True room footprint in BIM/world coordinates (outer loop + holes). */
    footprint: RoomFootprintResult
    /** Deterministic interior anchor in world XY at the footprint floorZ. */
    interiorAnchor: { x: number; y: number; z: number }
    /** 3D volume characterization (zLow/zHigh, closed, components, faces). */
    volume?: RoomVolumeCharacterization
    /** The retained authoritative world mesh (for view-only volume rendering). */
    mesh?: RoomMesh
    /** Bounded diagnostics (counts only — never raw geometry). */
    polyfaceCount: number
    triangleCount: number
    vertexCount: number
    outerLoopPointCount: number
    holeCount: number
    footprintArea: number
    resultBytes: number
    ok: boolean
    reason?: string
}

/**
 * Flatten decoded IndexedPolyfaces into a single world-space triangle mesh.
 * IndexedPolyface point indices are 1-based in the pointIndex array; we expand
 * each facet into triangles (fan) referencing a flat vertex array.
 */
function polyfacesToMesh(polyfaces: ReturnType<typeof readElementMeshes>): RoomMesh {
    const vertices: { x: number; y: number; z: number }[] = []
    const triangles: number[] = []
    for (const pf of polyfaces) {
        const base = vertices.length
        const pts = pf.data.point
        const count = pts.length
        for (let i = 0; i < count; i++) {
            const p = pts.getPoint3dAtUncheckedPointIndex(i)
            vertices.push({ x: p.x, y: p.y, z: p.z })
        }
        // Walk facets via the pointIndex + facetStart arrays. pointIndex holds
        // GLOBAL 0-based indices into this polyface's point array.
        const pointIndex = pf.data.pointIndex
        const facetStart = pf.facetStart
        for (let f = 0; f + 1 < facetStart.length; f++) {
            const start = facetStart[f]
            const end = facetStart[f + 1]
            const face: number[] = []
            for (let k = start; k < end; k++) {
                const idx = pointIndex[k]
                if (idx >= 0 && idx < count) face.push(base + idx)
            }
            // Fan-triangulate the face.
            for (let t = 1; t + 1 < face.length; t++) {
                triangles.push(face[0], face[t], face[t + 1])
            }
        }
    }
    return { vertices, triangles }
}

/**
 * Extract the authoritative room geometry for a bimSpaceId. Read-only. The active
 * iModel is supplied by the caller (resolved via the explicit product-viewport
 * resolver — NOT solely selectedView, which can be null while the clinic renders).
 * Returns ok=false with a reason when no usable geometry can be extracted (so the
 * caller reports failure rather than reverting to the range rectangle).
 */
export async function extractAuthoritativeRoomGeometry(bimSpaceId: string, iModelOverride?: IModelConnection): Promise<AuthoritativeRoomGeometry> {
    const fail = (reason: string, polyfaceCount = 0, triangleCount = 0, resultBytes = 0): AuthoritativeRoomGeometry => ({
        bimSpaceId,
        footprint: { outerLoop: [], holes: [], floorZ: 0, geometryQuality: 'NOT_AVAILABLE', source: 'AUTHORITATIVE_IFCSPACE_GEOMETRY_STREAM' },
        interiorAnchor: { x: 0, y: 0, z: 0 },
        polyfaceCount, triangleCount, vertexCount: 0, outerLoopPointCount: 0, holeCount: 0, footprintArea: 0, resultBytes,
        ok: false, reason,
    })

    const iModel = iModelOverride ?? IModelApp.viewManager?.selectedView?.iModel
    if (!iModel) return fail('NO_ACTIVE_VIEWPORT')
    if (!bimSpaceId) return fail('NO_BIM_SPACE_ID')

    let mesh: RoomMesh
    let polyfaceCount = 0
    let resultBytes = 0
    try {
        // Read-only geometry request. chordTolerance small for room fidelity.
        const data = await iModel.generateElementMeshes({ source: bimSpaceId, chordTolerance: 0.05, angleTolerance: Math.PI / 12 })
        resultBytes = data?.length ?? 0
        if (!data || data.length === 0) return fail('EMPTY_MESH_RESPONSE', 0, 0, resultBytes)
        const polyfaces = readElementMeshes(data)
        polyfaceCount = polyfaces.length
        if (polyfaceCount === 0) return fail('NO_POLYFACES', 0, 0, resultBytes)
        mesh = polyfacesToMesh(polyfaces)
    } catch (e) {
        return fail('EXTRACTION_ERROR: ' + (e instanceof Error ? e.message : String(e)), 0, 0, resultBytes)
    }

    if (mesh.vertices.length < 3 || mesh.triangles.length < 3) return fail('DEGENERATE_MESH', polyfaceCount, mesh.triangles.length / 3, resultBytes)

    // Characterize the 3D volume BEFORE flattening (§9).
    const volume = characterizeAuthoritativeRoomVolume(mesh)

    const footprint = deriveAuthoritativeRoomFootprint(mesh)
    if (footprint.geometryQuality !== 'EXACT_ROOM_BOUNDARY') {
        return { ...fail('FOOTPRINT_DERIVATION_FAILED', polyfaceCount, mesh.triangles.length / 3, resultBytes), volume, mesh }
    }

    const anchor2d: Vec2 = resolveRoomInteriorAnchor({ outerLoop: footprint.outerLoop, holes: footprint.holes })
    return {
        bimSpaceId,
        footprint,
        interiorAnchor: { x: anchor2d.x, y: anchor2d.y, z: footprint.floorZ },
        volume,
        mesh,
        polyfaceCount,
        triangleCount: mesh.triangles.length / 3,
        vertexCount: mesh.vertices.length,
        outerLoopPointCount: footprint.outerLoop.length,
        holeCount: footprint.holes.length,
        footprintArea: polygonArea(footprint.outerLoop),
        resultBytes,
        ok: true,
    }
}

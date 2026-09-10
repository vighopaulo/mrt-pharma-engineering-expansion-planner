/**
 * clinicalProgramAnchor — pure, Bentley-free FIXED PHYSICAL ANCHORING for the
 * clinical-program overlay.
 *
 * This seam separates two concepts the manual acceptance proved must not be
 * conflated:
 *   1. FACILITY ANCHOR — the FIXED physical location (BIM/world coordinates) of
 *      the assigned BIM space. It is a function of the BIM geometry ONLY; it is
 *      never derived from the camera, viewport, or screen. Camera movement can
 *      only change worldToView(anchor), never the anchor itself.
 *   2. DISPLAY ANCHOR — the facility anchor plus a small VIEW-ONLY Z lift used to
 *      keep the label/footprint readable above the floor slab. The Z lift never
 *      mutates the facility anchor.
 *
 * It also classifies the geometry HONESTLY: an axis-aligned BIM range is a
 * BIM_RANGE_APPROXIMATION, never an EXACT_ROOM_BOUNDARY. An exact boundary is
 * only claimed when the active BIM actually exposes an authoritative space
 * polygon.
 */
import type { SpatialRoomReference } from '../../domain/assets'
import { deriveRoomFootprint, resolveRoomStoreyId, type PlanFootprint, type StoreyZRange } from './planningPlan'

/** Honest geometry-quality classification (never over-claims). */
export type ProgramGeometryQuality =
    | 'EXACT_ROOM_BOUNDARY' // authoritative BIM-space polygon
    | 'BIM_RANGE_APPROXIMATION' // axis-aligned BIM range rectangle
    | 'ANCHOR_ONLY' // a point anchor, no usable footprint
    | 'NOT_AVAILABLE' // no geometry at all

export type ProgramGeometrySource =
    | 'AUTHORITATIVE_BIM_SPACE_GEOMETRY'
    | 'BIM_SPATIAL_RANGE'
    | 'NONE'

export interface Vec3 { x: number; y: number; z: number }

export interface ClinicalProgramFacilityAnchor {
    bimSpaceId: string
    storeyId?: string
    /** FIXED physical location in BIM/world coordinates. Camera-invariant. */
    worldAnchor: Vec3
    /** Closed world-coordinate ring (approximate or exact) if any; else undefined. */
    boundary?: { x: number; y: number; z: number }[]
    geometrySource: ProgramGeometrySource
    geometryQuality: ProgramGeometryQuality
}

/**
 * An authoritative room boundary the BIM may expose (future/optional). If the
 * caller supplies one it is used as the EXACT boundary; otherwise the seam falls
 * back to the BIM range and classifies honestly. This keeps the seam ready for
 * exact space geometry without fabricating it today.
 */
export interface ExactRoomBoundary {
    /** Closed CCW world ring (XY) of the true space boundary. */
    ring: { x: number; y: number }[]
    /** Elevation the boundary sits at (world Z). */
    elevation: number
}

function isFiniteNum(n: unknown): n is number { return typeof n === 'number' && Number.isFinite(n) }

function ringCentroid(ring: readonly { x: number; y: number }[]): { x: number; y: number } {
    const n = ring.length || 1
    return { x: ring.reduce((s, p) => s + p.x, 0) / n, y: ring.reduce((s, p) => s + p.y, 0) / n }
}

/**
 * Resolve the FIXED facility anchor for an assigned room. Preference:
 *   1. an authoritative exact boundary, if the BIM exposes one => EXACT_ROOM_BOUNDARY;
 *   2. else the BIM range footprint => BIM_RANGE_APPROXIMATION (centroid anchor);
 *   3. else no usable geometry => NOT_AVAILABLE (anchor at origin is not invented).
 *
 * The anchor is a pure function of the BIM inputs — never the camera.
 */
export function resolveClinicalProgramFacilityAnchor(input: {
    room: Pick<SpatialRoomReference, 'roomId' | 'displayName' | 'range' | 'geometryType'>
    storeys: readonly StoreyZRange[]
    exactBoundary?: ExactRoomBoundary
}): ClinicalProgramFacilityAnchor {
    const { room } = input

    // 1) Exact authoritative boundary (only when actually provided).
    if (input.exactBoundary && input.exactBoundary.ring.length >= 3) {
        const b = input.exactBoundary
        const c = ringCentroid(b.ring)
        const worldAnchor: Vec3 = { x: c.x, y: c.y, z: b.elevation }
        const storeyId = resolveRoomStoreyId({ zLow: b.elevation, zHigh: b.elevation }, input.storeys)
        return {
            bimSpaceId: room.roomId,
            storeyId,
            worldAnchor,
            boundary: b.ring.map((p) => ({ x: p.x, y: p.y, z: b.elevation })),
            geometrySource: 'AUTHORITATIVE_BIM_SPACE_GEOMETRY',
            geometryQuality: 'EXACT_ROOM_BOUNDARY',
        }
    }

    // 2) BIM range fallback — honest approximation.
    const fp: PlanFootprint | undefined = deriveRoomFootprint(room)
    if (fp) {
        const c = ringCentroid(fp.ring)
        const worldAnchor: Vec3 = { x: c.x, y: c.y, z: fp.elevation }
        const storeyId = resolveRoomStoreyId(fp, input.storeys)
        return {
            bimSpaceId: room.roomId,
            storeyId,
            worldAnchor,
            boundary: fp.ring.map((p) => ({ x: p.x, y: p.y, z: fp.elevation })),
            geometrySource: 'BIM_SPATIAL_RANGE',
            geometryQuality: 'BIM_RANGE_APPROXIMATION',
        }
    }

    // 3) No usable geometry — anchor-only if a finite range center exists, else none.
    const r = room.range
    if (r && [r.low.x, r.low.y, r.low.z, r.high.x, r.high.y, r.high.z].every(isFiniteNum)) {
        const worldAnchor: Vec3 = { x: (r.low.x + r.high.x) / 2, y: (r.low.y + r.high.y) / 2, z: Math.min(r.low.z, r.high.z) }
        const storeyId = resolveRoomStoreyId({ zLow: worldAnchor.z, zHigh: worldAnchor.z }, input.storeys)
        return { bimSpaceId: room.roomId, storeyId, worldAnchor, geometrySource: 'BIM_SPATIAL_RANGE', geometryQuality: 'ANCHOR_ONLY' }
    }
    return {
        bimSpaceId: room.roomId,
        storeyId: undefined,
        worldAnchor: { x: 0, y: 0, z: 0 },
        geometrySource: 'NONE',
        geometryQuality: 'NOT_AVAILABLE',
    }
}

/**
 * Derive the DISPLAY anchor: facility anchor + a VIEW-ONLY Z lift. The facility
 * anchor object is never mutated; a new Vec3 is returned. Camera-independent.
 */
export function resolveProgramDisplayAnchor(input: { facilityAnchor: ClinicalProgramFacilityAnchor; zOffset: number }): Vec3 {
    const a = input.facilityAnchor.worldAnchor
    return { x: a.x, y: a.y, z: a.z + (Number.isFinite(input.zOffset) ? input.zOffset : 0) }
}

/** Display boundary = facility boundary lifted by the same view-only Z offset. */
export function resolveProgramDisplayBoundary(input: { facilityAnchor: ClinicalProgramFacilityAnchor; zOffset: number }): { x: number; y: number; z: number }[] | undefined {
    const b = input.facilityAnchor.boundary
    if (!b) return undefined
    const dz = Number.isFinite(input.zOffset) ? input.zOffset : 0
    return b.map((p) => ({ x: p.x, y: p.y, z: p.z + dz }))
}

/** Human-readable geometry-quality label for restrained UI disclosure. */
export function describeGeometryQuality(q: ProgramGeometryQuality): string {
    switch (q) {
        case 'EXACT_ROOM_BOUNDARY': return 'Authoritative BIM room boundary'
        case 'BIM_RANGE_APPROXIMATION': return 'BIM range approximation'
        case 'ANCHOR_ONLY': return 'BIM anchor only (no footprint)'
        default: return 'No BIM geometry available'
    }
}

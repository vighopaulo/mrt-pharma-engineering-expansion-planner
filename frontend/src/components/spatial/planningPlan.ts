/**
 * planningPlan — pure, Bentley-free derivation of a DERIVED BIM-BACKED PLANNING
 * CONTEXT from authoritative BuildingSpatial:Space ranges.
 *
 * CONTEXT (Visual Planning Foundation — Correction 2): the connected iModel is
 * dominated by spatial-VOLUME semantics (BuildingSpatial:Space) rather than
 * detailed architectural surfaces. The first correction hid those volumes, which
 * removed almost all hospital context. The honest replacement is NOT fake walls
 * — it is a restrained plan-like representation derived from the already
 * authoritative finite room ranges: a horizontal FOOTPRINT per room at a
 * planning elevation, plus the room's own BIM label.
 *
 * Everything here is a pure function of the spatial semantics snapshot:
 *   - it derives, never fabricates (invalid ranges yield no footprint);
 *   - it references the SAME room identity (roomId) — never a second identity;
 *   - it is VIEW-ONLY input (the caller renders decorations; nothing is written
 *     to the iModel and no engineering/association state is mutated).
 *
 * The SOURCE OF TRUTH remains SpatialModelSemantics / BuildingSpatial:Space and
 * the existing association logic. This module does not own room coordinates; it
 * regenerates from whatever snapshot it is given.
 */
import type { SpatialRoomReference, WorldRange3 } from '../../domain/assets/spatialSemantics'
import type { ViewerMode } from './planningVisuals'

// ---------------------------------------------------------------------------
// BIM visual classification (drives the visual strategy)
// ---------------------------------------------------------------------------

/** Read-only architectural/spatial class counts from a live inventory probe. */
export interface BimGeometryInventory {
    wallCount: number
    slabOrFloorCount: number
    doorCount: number
    /** Other geometric elements not in the specific buckets above. */
    otherGeometricCount: number
    /** BuildingSpatial:Space count (room semantics). */
    spaceCount: number
}

/** Honest classification of the connected iModel's visual content. */
export type BimVisualClassification =
    | 'DETAILED_ARCHITECTURAL_BIM'
    | 'PARTIAL_ARCHITECTURAL_BIM'
    | 'SPATIAL_SEMANTIC_MODEL_WITH_LIMITED_ARCHITECTURE'
    | 'OTHER'

/**
 * Classify the iModel from its geometry inventory. Deterministic:
 *   - substantial walls AND floors/slabs => DETAILED_ARCHITECTURAL_BIM
 *   - some architectural geometry (walls or slabs or doors) => PARTIAL
 *   - no architectural geometry but spaces present => SPATIAL_SEMANTIC (limited)
 *   - nothing recognizable => OTHER
 */
export function classifyBimModel(inv: BimGeometryInventory): BimVisualClassification {
    const walls = Math.max(0, inv.wallCount | 0)
    const slabs = Math.max(0, inv.slabOrFloorCount | 0)
    const doors = Math.max(0, inv.doorCount | 0)
    const spaces = Math.max(0, inv.spaceCount | 0)
    const anyArch = walls > 0 || slabs > 0 || doors > 0
    if (walls >= 4 && slabs >= 1) return 'DETAILED_ARCHITECTURAL_BIM'
    if (anyArch) return 'PARTIAL_ARCHITECTURAL_BIM'
    if (spaces > 0) return 'SPATIAL_SEMANTIC_MODEL_WITH_LIMITED_ARCHITECTURE'
    return 'OTHER'
}

/** The normal-mode primary context implied by a classification. */
export type NormalModePrimaryContext = 'ARCHITECTURAL_BIM_GEOMETRY' | 'DERIVED_BIM_SPATIAL_PLAN' | 'MODEL_DEFAULT'

export function resolveNormalModePrimaryContext(cls: BimVisualClassification): NormalModePrimaryContext {
    switch (cls) {
        case 'DETAILED_ARCHITECTURAL_BIM':
        case 'PARTIAL_ARCHITECTURAL_BIM':
            return 'ARCHITECTURAL_BIM_GEOMETRY'
        case 'SPATIAL_SEMANTIC_MODEL_WITH_LIMITED_ARCHITECTURE':
            return 'DERIVED_BIM_SPATIAL_PLAN'
        default:
            return 'MODEL_DEFAULT'
    }
}

// ---------------------------------------------------------------------------
// Normal-mode room representation policy
// ---------------------------------------------------------------------------

/** How a room is represented in a given viewer mode. */
export type RoomRepresentation = 'PLAN_FOOTPRINT' | 'FULL_VOLUME'

/**
 * NORMAL_PLANNING => PLAN_FOOTPRINT (thin outline + light fill, no tall
 * translucent box). DEVELOPER => FULL_VOLUME (raw range diagnostic available).
 * Never HIDDEN_WITHOUT_REPLACEMENT — that was the failed first correction.
 */
export function resolveNormalRoomRepresentation(mode: ViewerMode): RoomRepresentation {
    return mode === 'DEVELOPER' ? 'FULL_VOLUME' : 'PLAN_FOOTPRINT'
}

// ---------------------------------------------------------------------------
// Room footprint derivation (view-only geometry)
// ---------------------------------------------------------------------------

export interface PlanFootprint {
    /** Same identity as the source BIM room — never a second identity. */
    roomId: string
    label: string
    /** Closed CCW ring of world XY corners at the planning elevation. */
    ring: { x: number; y: number }[]
    /** Deterministic planning elevation (Z) the footprint is drawn at. */
    elevation: number
    /** The room's authoritative vertical extent (preserved for semantics). */
    zLow: number
    zHigh: number
    provenance: 'BIM_DERIVED'
}

function isFiniteNum(n: unknown): n is number {
    return typeof n === 'number' && Number.isFinite(n)
}

/** Where the footprint's planning elevation comes from. */
export type PlanningElevationSource = 'ROOM_RANGE_LOW_Z'

/**
 * Derive a horizontal footprint from a finite room range. Returns undefined for
 * any non-finite / malformed range (NaN, Infinity, missing) — geometry is NEVER
 * fabricated. Corners are ordered CCW: (xmin,ymin)->(xmax,ymin)->(xmax,ymax)->
 * (xmin,ymax). The planning elevation defaults to the range low.z (an honest,
 * deterministic BIM-derived source — NOT a fabricated authoritative floor).
 */
export function deriveRoomFootprint(
    room: Pick<SpatialRoomReference, 'roomId' | 'displayName'> & { range?: WorldRange3 },
    opts?: { elevationSource?: PlanningElevationSource },
): PlanFootprint | undefined {
    const r = room.range
    if (!r) return undefined
    const { low, high } = r
    const coords = [low?.x, low?.y, low?.z, high?.x, high?.y, high?.z]
    if (!coords.every(isFiniteNum)) return undefined
    const xmin = Math.min(low.x, high.x)
    const xmax = Math.max(low.x, high.x)
    const ymin = Math.min(low.y, high.y)
    const ymax = Math.max(low.y, high.y)
    const zLow = Math.min(low.z, high.z)
    const zHigh = Math.max(low.z, high.z)
    // Degenerate footprint (zero area) is not useful planning context.
    if (xmax === xmin || ymax === ymin) return undefined
    // Currently one honest source: the room range low Z (planning elevation).
    const elevation = opts?.elevationSource === 'ROOM_RANGE_LOW_Z' ? zLow : zLow
    return {
        roomId: room.roomId,
        label: room.displayName,
        ring: [
            { x: xmin, y: ymin },
            { x: xmax, y: ymin },
            { x: xmax, y: ymax },
            { x: xmin, y: ymax },
        ],
        elevation,
        zLow,
        zHigh,
        provenance: 'BIM_DERIVED',
    }
}

/**
 * Derive footprints for a set of rooms. Rooms without a usable finite range are
 * skipped (no fabricated geometry). Deterministic order preserved.
 */
export function deriveRoomPlan(rooms: readonly (Pick<SpatialRoomReference, 'roomId' | 'displayName'> & { range?: WorldRange3 })[]): PlanFootprint[] {
    const out: PlanFootprint[] = []
    for (const room of rooms) {
        const fp = deriveRoomFootprint(room)
        if (fp) out.push(fp)
    }
    return out
}

// ---------------------------------------------------------------------------
// Planning elevation + multi-level visibility policy
// ---------------------------------------------------------------------------

/**
 * Resolve the active planning elevation deterministically from an honest source
 * (never a fabricated authoritative floor):
 *   - a selected/placed AssetInstance Z, if provided; else
 *   - the lowest room footprint elevation (the ground planning level); else
 *   - 0.
 */
export function resolvePlanningElevation(input: {
    selectedAssetZ?: number
    footprints: readonly PlanFootprint[]
}): { elevation: number; provenance: 'SELECTED_ASSET_Z' | 'LOWEST_ROOM_RANGE_LOW_Z' | 'DEFAULT_ZERO' } {
    if (isFiniteNum(input.selectedAssetZ)) {
        return { elevation: input.selectedAssetZ, provenance: 'SELECTED_ASSET_Z' }
    }
    if (input.footprints.length > 0) {
        const lowest = input.footprints.reduce((m, f) => (f.zLow < m ? f.zLow : m), input.footprints[0].zLow)
        return { elevation: lowest, provenance: 'LOWEST_ROOM_RANGE_LOW_Z' }
    }
    return { elevation: 0, provenance: 'DEFAULT_ZERO' }
}

/**
 * Deterministic multi-level visibility: a room footprint is visible at the
 * active planning elevation when that elevation falls within the room's
 * vertical range (inclusive, with a small tolerance so a room's own low.z shows
 * it). This avoids overlaying every level's plan at once.
 */
export function roomFootprintVisibleAtElevation(fp: PlanFootprint, elevation: number, tolerance = 0.5): boolean {
    if (!isFiniteNum(elevation)) return false
    return elevation >= fp.zLow - tolerance && elevation <= fp.zHigh + tolerance
}

/** Filter footprints to those visible at the active planning elevation. */
export function visibleFootprintsAtElevation(footprints: readonly PlanFootprint[], elevation: number, tolerance = 0.5): PlanFootprint[] {
    return footprints.filter((fp) => roomFootprintVisibleAtElevation(fp, elevation, tolerance))
}

// ---------------------------------------------------------------------------
// Storey binning (pure) — associate a room footprint with a storey by Z
// ---------------------------------------------------------------------------

export interface StoreyZRange { id: string; label: string; zLow: number; zHigh: number }

/**
 * Bin a room footprint into a storey by testing its vertical midpoint against
 * each storey's Z range (inclusive). Deterministic: the FIRST containing storey
 * wins; when none contain it, the NEAREST storey by center-Z distance is used
 * (so a room always maps to a storey when any storey exists). Returns undefined
 * only when there are no storeys. Pure — never queries Bentley.
 */
export function resolveRoomStoreyId(fp: Pick<PlanFootprint, 'zLow' | 'zHigh'>, storeys: readonly StoreyZRange[]): string | undefined {
    if (storeys.length === 0) return undefined
    const midZ = (fp.zLow + fp.zHigh) / 2
    const contained = storeys.find((s) => midZ >= Math.min(s.zLow, s.zHigh) && midZ <= Math.max(s.zLow, s.zHigh))
    if (contained) return contained.id
    let best = storeys[0]
    let bestD = Infinity
    for (const s of storeys) {
        const center = (s.zLow + s.zHigh) / 2
        const d = Math.abs(center - midZ)
        if (d < bestD) { bestD = d; best = s }
    }
    return best.id
}

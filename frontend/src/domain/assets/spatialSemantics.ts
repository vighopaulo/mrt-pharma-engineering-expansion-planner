/**
 * spatialSemantics — pure, Bentley-free BIM spatial-semantics domain.
 *
 * This layer answers "which FLOOR and which ROOM contain an asset position"
 * from AUTHORITATIVE BIM-derived spatial references, or says explicitly that
 * the BIM does not expose usable floor/room semantics. It is OBSERVATIONAL:
 * association never changes an asset's position, Z, rotation, or identity.
 *
 * Doctrine:
 *   asset position + SpatialModelSemantics -> SpatialAssociationResult
 * The result carries a rich, typed status (never collapsing uncertainty into a
 * single NOT_ASSIGNED) plus provenance describing how the association was made
 * and which Bentley source element(s) backed it.
 *
 * Nothing here imports @itwin. The Bentley adapter (a separate module) queries
 * the live iModel and converts results into the plain references defined here,
 * so all association logic is unit-testable without WebGL / auth / a viewport.
 */

// ---------------------------------------------------------------------------
// Confidence / provenance
// ---------------------------------------------------------------------------

/** How trustworthy a discovered spatial reference is. */
export type SpatialSourceConfidence =
    | 'AUTHORITATIVE_BIM' // came directly from an explicit BIM spatial object
    | 'DERIVED' // computed from ranges/elevations, not an explicit space object
    | 'NOT_AVAILABLE' // the BIM does not expose this semantic at all

/** The concrete method used to associate a point with a floor/room. */
export type SpatialAssociationMethod =
    | 'BIM_ROOM_VOLUME' // point inside an explicit room 3D volume
    | 'BIM_ROOM_FOOTPRINT' // point inside an explicit room 2D footprint (+ floor)
    | 'BIM_ELEMENT_RANGE' // point inside an explicit spatial element bounding range
    | 'STOREY_ELEVATION_RANGE' // point within a storey/floor vertical range
    | 'DERIVED_RANGE' // range-derived containment (labelled non-exact)
    | 'NONE' // no association method applied

// ---------------------------------------------------------------------------
// Geometry availability (what the BIM physically gives us to reason with)
// ---------------------------------------------------------------------------

export type SpatialGeometryType =
    | 'VOLUME'
    | 'FOOTPRINT'
    | 'RANGE_ONLY'
    | 'METADATA_ONLY'
    | 'NOT_AVAILABLE'

/** Axis-aligned world range (meters, BENTLEY_WORLD_COORDINATES). */
export interface WorldRange3 {
    low: { x: number; y: number; z: number }
    high: { x: number; y: number; z: number }
}

/** A closed 2D footprint polygon (world XY) with a vertical extent. */
export interface WorldFootprint {
    /** Ordered polygon vertices (world XY). Assumed simple (non-self-intersecting). */
    ring: { x: number; y: number }[]
    /** Vertical extent the footprint applies over. */
    zLow: number
    zHigh: number
}

// ---------------------------------------------------------------------------
// Floor / room references (Bentley-independent)
// ---------------------------------------------------------------------------

/**
 * A floor / building storey reference. Carries only supported information;
 * missing elevation/range stays optional rather than being fabricated.
 */
export interface SpatialFloorReference {
    floorId: string
    displayName: string
    /** Bentley source class this floor was derived from (e.g. bis class name). */
    sourceClass: string
    /** Authoritative source element id, if any. */
    sourceElementId?: string
    confidence: SpatialSourceConfidence
    /** Reference elevation (meters), if the BIM supplies one. */
    elevation?: number
    /** Vertical range the floor occupies, if known. */
    verticalRange?: { zLow: number; zHigh: number }
}

/**
 * A room / space reference. Carries only supported information; room numbers /
 * names are never invented.
 */
export interface SpatialRoomReference {
    roomId: string
    displayName: string
    sourceClass: string
    sourceElementId?: string
    /** The floor this room belongs to, if actually known from the BIM. */
    floorId?: string
    confidence: SpatialSourceConfidence
    /** What geometry authority backs containment tests for this room. */
    geometryType: SpatialGeometryType
    /** 3D range (present when geometryType is VOLUME or RANGE_ONLY). */
    range?: WorldRange3
    /** 2D footprint (present when geometryType is FOOTPRINT). */
    footprint?: WorldFootprint
}

/**
 * A Bentley-free snapshot of the model's spatial semantics, produced by the
 * adapter from the live iModel and consumed by the pure association functions.
 */
export interface SpatialModelSemantics {
    floors: SpatialFloorReference[]
    rooms: SpatialRoomReference[]
    /** Overall availability of floor semantics in the source BIM. */
    floorAvailability: SpatialSourceConfidence
    /** Overall availability of room semantics in the source BIM. */
    roomAvailability: SpatialSourceConfidence
    /** Bounded, human-readable inventory summary (for DEV / provenance). */
    inventorySummary?: string
}

/** An empty semantics snapshot — the BIM exposes no usable floor/room objects. */
export const EMPTY_MODEL_SEMANTICS: SpatialModelSemantics = {
    floors: [],
    rooms: [],
    floorAvailability: 'NOT_AVAILABLE',
    roomAvailability: 'NOT_AVAILABLE',
}

// ---------------------------------------------------------------------------
// Association status + result
// ---------------------------------------------------------------------------

/**
 * Explicit association status. Uncertainty is NOT collapsed into a single value:
 *   ASSIGNED               — a defensible floor/room was found
 *   NOT_FOUND_AT_POSITION  — semantics exist, but no space contains this point
 *   NOT_AVAILABLE_FROM_BIM — the BIM does not expose this semantic at all
 *   AMBIGUOUS              — more than one space contains the point (no arbitrary pick)
 *   OUTSIDE_MODELED_SPACE  — the point is outside the modeled spatial envelope
 */
export type SpatialAssociationStatus =
    | 'ASSIGNED'
    | 'NOT_FOUND_AT_POSITION'
    | 'NOT_AVAILABLE_FROM_BIM'
    | 'AMBIGUOUS'
    | 'OUTSIDE_MODELED_SPACE'

/** Where a room assignment came from (kept distinct from BIM-derived results). */
export type RoomAssignmentProvenance = 'MANUAL' | 'BIM_DERIVED' | 'NOT_ASSIGNED'

/** Provenance of a single association computation. */
export interface SpatialAssociationProvenance {
    source: RoomAssignmentProvenance
    method: SpatialAssociationMethod
    /** Bentley source element ids that backed the association (floor/room). */
    sourceElementIds: string[]
    /** The world point actually tested (asset origin/center — see convention). */
    testedPoint: { x: number; y: number; z: number }
    /** Whether a point-vs-range/footprint boundary was treated as inside. */
    boundaryInclusive: boolean
}

/**
 * The typed association result for one asset instance. `floor` / `room` are the
 * resolved references when the corresponding status is ASSIGNED, otherwise
 * undefined. Statuses are independent: a floor can be ASSIGNED while the room is
 * NOT_AVAILABLE_FROM_BIM.
 */
export interface SpatialAssociationResult {
    assetInstanceId: string
    floor?: SpatialFloorReference
    room?: SpatialRoomReference
    floorStatus: SpatialAssociationStatus
    roomStatus: SpatialAssociationStatus
    provenance: SpatialAssociationProvenance
    /** Minimal derived placement validity (informational only; blocks nothing). */
    validity: SpatialValidity
}

/**
 * Minimal informational placement validity. This build does NOT implement
 * collision/clearance; validity never blocks drag/rotation/placement.
 */
export type SpatialValidity =
    | 'VALID_ASSOCIATED'
    | 'ROOM_UNKNOWN'
    | 'FLOOR_UNKNOWN'
    | 'OUTSIDE_MODELED_ROOM'
    | 'AMBIGUOUS_ROOM'

// ---------------------------------------------------------------------------
// Boundary policy
// ---------------------------------------------------------------------------

/**
 * BOUNDARY POLICY (deterministic): a point exactly on a floor vertical-range
 * boundary or a room range/footprint edge is treated as INSIDE (inclusive on
 * the low and high bounds). This is documented, deterministic, and applied
 * uniformly by every containment test below.
 */
export const SPATIAL_BOUNDARY_INCLUSIVE = true

// ---------------------------------------------------------------------------
// Containment primitives (pure)
// ---------------------------------------------------------------------------

/** Inclusive 1D range test (see SPATIAL_BOUNDARY_INCLUSIVE). */
function within(v: number, lo: number, hi: number): boolean {
    const low = Math.min(lo, hi)
    const high = Math.max(lo, hi)
    return SPATIAL_BOUNDARY_INCLUSIVE ? v >= low && v <= high : v > low && v < high
}

/**
 * Validate + normalize a candidate world range. Returns a WorldRange3 ONLY when
 * every coordinate is finite (no NaN / Infinity) and the low/high are ordered
 * (low <= high per axis, normalizing swapped endpoints). Returns undefined for
 * any non-finite or malformed input — such a range must NOT be treated as
 * usable geometry (it becomes METADATA_ONLY, never RANGE_ONLY).
 */
export function validateWorldRange(candidate: {
    low: { x: number; y: number; z: number }
    high: { x: number; y: number; z: number }
}): WorldRange3 | undefined {
    const c = candidate
    const coords = [c.low.x, c.low.y, c.low.z, c.high.x, c.high.y, c.high.z]
    if (!coords.every((n) => Number.isFinite(n))) return undefined
    return {
        low: { x: Math.min(c.low.x, c.high.x), y: Math.min(c.low.y, c.high.y), z: Math.min(c.low.z, c.high.z) },
        high: { x: Math.max(c.low.x, c.high.x), y: Math.max(c.low.y, c.high.y), z: Math.max(c.low.z, c.high.z) },
    }
}

/** Point inside a 3D world range (inclusive boundary). */
export function pointInRange3(p: { x: number; y: number; z: number }, r: WorldRange3): boolean {
    return within(p.x, r.low.x, r.high.x) && within(p.y, r.low.y, r.high.y) && within(p.z, r.low.z, r.high.z)
}

/**
 * Point-in-polygon (world XY) using a ray-cast even-odd rule, with an explicit
 * inclusive on-edge result to honor the documented boundary policy. Vertical
 * extent is checked inclusively against [zLow, zHigh].
 */
export function pointInFootprint(p: { x: number; y: number; z: number }, f: WorldFootprint): boolean {
    if (!within(p.z, f.zLow, f.zHigh)) return false
    const ring = f.ring
    const n = ring.length
    if (n < 3) return false
    // On-edge detection (inclusive).
    for (let i = 0; i < n; i++) {
        const a = ring[i]
        const b = ring[(i + 1) % n]
        if (pointOnSegmentXY(p.x, p.y, a.x, a.y, b.x, b.y)) return SPATIAL_BOUNDARY_INCLUSIVE
    }
    // Even-odd ray cast to +x.
    let inside = false
    for (let i = 0, j = n - 1; i < n; j = i++) {
        const yi = ring[i].y, yj = ring[j].y
        const xi = ring[i].x, xj = ring[j].x
        const intersects = (yi > p.y) !== (yj > p.y) &&
            p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi
        if (intersects) inside = !inside
    }
    return inside
}

function pointOnSegmentXY(px: number, py: number, ax: number, ay: number, bx: number, by: number): boolean {
    const cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if (Math.abs(cross) > 1e-9) return false
    const dot = (px - ax) * (bx - ax) + (py - ay) * (by - ay)
    if (dot < 0) return false
    const len2 = (bx - ax) ** 2 + (by - ay) ** 2
    return dot <= len2
}

// ---------------------------------------------------------------------------
// Floor association (deterministic)
// ---------------------------------------------------------------------------

/**
 * Associate a world position with a floor. Preference order:
 *   1. explicit storey vertical range containment (STOREY_ELEVATION_RANGE)
 *   2. nearest-elevation storey when only elevations exist (DERIVED_RANGE)
 * Deterministic: identical inputs always yield the identical floor. On a tie in
 * range containment the result is AMBIGUOUS (never an arbitrary pick).
 */
export function associateFloor(
    position: { x: number; y: number; z: number },
    semantics: Pick<SpatialModelSemantics, 'floors' | 'floorAvailability'>,
): { status: SpatialAssociationStatus; floor?: SpatialFloorReference; method: SpatialAssociationMethod } {
    if (semantics.floorAvailability === 'NOT_AVAILABLE' || semantics.floors.length === 0) {
        return { status: 'NOT_AVAILABLE_FROM_BIM', method: 'NONE' }
    }
    // 1. Range containment.
    const ranged = semantics.floors.filter((f) => f.verticalRange && within(position.z, f.verticalRange.zLow, f.verticalRange.zHigh))
    if (ranged.length === 1) {
        return { status: 'ASSIGNED', floor: ranged[0], method: 'STOREY_ELEVATION_RANGE' }
    }
    if (ranged.length > 1) {
        return { status: 'AMBIGUOUS', method: 'STOREY_ELEVATION_RANGE' }
    }
    // 2. Nearest elevation (derived) when elevations exist but no range contained it.
    const withElev = semantics.floors.filter((f) => typeof f.elevation === 'number')
    if (withElev.length > 0) {
        let best: SpatialFloorReference | undefined
        let bestDist = Infinity
        let tie = false
        for (const f of withElev) {
            const d = Math.abs((f.elevation as number) - position.z)
            if (d < bestDist) { bestDist = d; best = f; tie = false }
            else if (d === bestDist) { tie = true }
        }
        if (tie) return { status: 'AMBIGUOUS', method: 'DERIVED_RANGE' }
        // A nearest-elevation match is DERIVED, not exact containment.
        return { status: 'ASSIGNED', floor: best, method: 'DERIVED_RANGE' }
    }
    return { status: 'NOT_FOUND_AT_POSITION', method: 'NONE' }
}

// ---------------------------------------------------------------------------
// Room association (deterministic)
// ---------------------------------------------------------------------------

/**
 * Associate a world position with a room. Preference order per room:
 *   VOLUME    -> point-in-range3            (BIM_ROOM_VOLUME)
 *   FOOTPRINT -> point-in-footprint         (BIM_ROOM_FOOTPRINT)
 *   RANGE_ONLY-> point-in-range3, labelled  (DERIVED_RANGE, not exact)
 * If more than one room contains the point => AMBIGUOUS (no arbitrary pick).
 * When a floor is provided, rooms are constrained to that floor when the room
 * declares a floorId. Deterministic and order-independent.
 */
export function associateRoom(
    position: { x: number; y: number; z: number },
    semantics: Pick<SpatialModelSemantics, 'rooms' | 'roomAvailability'>,
    floorId?: string,
): { status: SpatialAssociationStatus; room?: SpatialRoomReference; method: SpatialAssociationMethod } {
    if (semantics.roomAvailability === 'NOT_AVAILABLE' || semantics.rooms.length === 0) {
        return { status: 'NOT_AVAILABLE_FROM_BIM', method: 'NONE' }
    }
    const candidates = semantics.rooms.filter((r) => (floorId && r.floorId ? r.floorId === floorId : true))
    const hits: { room: SpatialRoomReference; method: SpatialAssociationMethod }[] = []
    // Count rooms that expose USABLE containment geometry (a valid volume /
    // footprint / range). A room that is METADATA_ONLY (or whose range failed
    // finite validation) is NOT a usable search space.
    let testableCount = 0
    for (const room of candidates) {
        const hasVolume = room.geometryType === 'VOLUME' && !!room.range
        const hasFootprint = room.geometryType === 'FOOTPRINT' && !!room.footprint
        const hasRange = room.geometryType === 'RANGE_ONLY' && !!room.range
        if (!hasVolume && !hasFootprint && !hasRange) continue
        testableCount += 1
        if (hasVolume && pointInRange3(position, room.range as WorldRange3)) {
            hits.push({ room, method: 'BIM_ROOM_VOLUME' })
        } else if (hasFootprint && pointInFootprint(position, room.footprint as WorldFootprint)) {
            hits.push({ room, method: 'BIM_ROOM_FOOTPRINT' })
        } else if (hasRange && pointInRange3(position, room.range as WorldRange3)) {
            hits.push({ room, method: 'DERIVED_RANGE' })
        }
    }
    if (hits.length === 1) return { status: 'ASSIGNED', room: hits[0].room, method: hits[0].method }
    if (hits.length > 1) return { status: 'AMBIGUOUS', method: hits[0].method }
    // CRITICAL: NOT_FOUND requires a valid search space. If room objects exist
    // but NONE expose usable containment geometry, we cannot say the point is
    // "outside" them — the honest answer is that room GEOMETRY is unavailable.
    if (testableCount === 0) return { status: 'NOT_AVAILABLE_FROM_BIM', method: 'NONE' }
    // Rooms with usable geometry exist, and the point is inside none of them.
    return { status: 'NOT_FOUND_AT_POSITION', method: 'NONE' }
}

// ---------------------------------------------------------------------------
// Full association (floor first, then room)
// ---------------------------------------------------------------------------

/**
 * Compute the full spatial association for one asset instance.
 *
 * ROOM_ASSOCIATION_POINT convention: the ASSET INSTANCE ORIGIN
 * (transform.position) is the tested point. This is a documented first method;
 * whole-equipment footprint containment is deferred to future clearance work.
 *
 * This function is pure and never mutates the asset — position/identity are
 * read-only inputs.
 */
export function computeSpatialAssociation(input: {
    assetInstanceId: string
    position: { x: number; y: number; z: number }
    semantics: SpatialModelSemantics
}): SpatialAssociationResult {
    const { assetInstanceId, position, semantics } = input
    const floorRes = normalizeAssignment(associateFloor(position, semantics), 'floor')
    const roomRes = normalizeAssignment(associateRoom(position, semantics, floorRes.floor?.floorId), 'room')

    const sourceElementIds: string[] = []
    if (floorRes.floor?.sourceElementId) sourceElementIds.push(floorRes.floor.sourceElementId)
    if (roomRes.room?.sourceElementId) sourceElementIds.push(roomRes.room.sourceElementId)

    const method: SpatialAssociationMethod =
        roomRes.method !== 'NONE' ? roomRes.method : floorRes.method

    const provenanceSource: RoomAssignmentProvenance =
        roomRes.status === 'ASSIGNED' || floorRes.status === 'ASSIGNED' ? 'BIM_DERIVED' : 'NOT_ASSIGNED'

    return {
        assetInstanceId,
        floor: floorRes.floor,
        room: roomRes.room,
        floorStatus: floorRes.status,
        roomStatus: roomRes.status,
        provenance: {
            source: provenanceSource,
            method,
            sourceElementIds,
            testedPoint: { ...position },
            boundaryInclusive: SPATIAL_BOUNDARY_INCLUSIVE,
        },
        validity: deriveValidity(floorRes.status, roomRes.status),
    }
}

/**
 * INVARIANT ENFORCEMENT: an ASSIGNED status MUST carry a concrete reference
 * (floor.floorId / room.roomId). A defensive downgrade guards against any
 * upstream (e.g. adapter) producing ASSIGNED with a missing/blank reference —
 * that state is treated as NOT_FOUND_AT_POSITION so the product UI and the DEV
 * inspector can never disagree by rendering the same invalid result two ways.
 */
function normalizeAssignment<T extends { status: SpatialAssociationStatus; floor?: SpatialFloorReference; room?: SpatialRoomReference; method: SpatialAssociationMethod }>(
    res: T,
    slot: 'floor' | 'room',
): T {
    if (res.status !== 'ASSIGNED') return res
    const ref = slot === 'floor' ? res.floor : res.room
    const id = slot === 'floor' ? res.floor?.floorId : res.room?.roomId
    if (ref && typeof id === 'string' && id.length > 0) return res
    // ASSIGNED without a usable reference is not a valid assignment.
    return { ...res, status: 'NOT_FOUND_AT_POSITION', method: 'NONE', floor: undefined, room: undefined }
}

/** Assert the invariant holds on a computed result (used by tests). */
export function assignmentInvariantHolds(r: SpatialAssociationResult): boolean {
    const floorOk = r.floorStatus !== 'ASSIGNED' || (!!r.floor && typeof r.floor.floorId === 'string' && r.floor.floorId.length > 0)
    const roomOk = r.roomStatus !== 'ASSIGNED' || (!!r.room && typeof r.room.roomId === 'string' && r.room.roomId.length > 0)
    return floorOk && roomOk
}

/** Derive minimal informational validity from the two statuses. */
function deriveValidity(floor: SpatialAssociationStatus, room: SpatialAssociationStatus): SpatialValidity {
    if (room === 'ASSIGNED') return 'VALID_ASSOCIATED'
    if (room === 'AMBIGUOUS') return 'AMBIGUOUS_ROOM'
    if (room === 'NOT_FOUND_AT_POSITION') return 'OUTSIDE_MODELED_ROOM'
    // room NOT_AVAILABLE_FROM_BIM / OUTSIDE — fall back to floor knowledge.
    if (floor === 'ASSIGNED') return 'ROOM_UNKNOWN'
    return 'FLOOR_UNKNOWN'
}

/**
 * SINGLE SHARED formatter for a floor/room slot label. Both the Placed Assets
 * product UI and the DEV inspector render association through THIS function, so
 * they can never disagree about the same result. ASSIGNED always shows the
 * concrete identity (label + id) — never the bare word "ASSIGNED" (the invariant
 * guarantees a reference exists when status is ASSIGNED). Other statuses map to
 * explicit, honest wording.
 */
export function formatAssociationSlotLabel(r: SpatialAssociationResult, slot: 'floor' | 'room'): string {
    const status = slot === 'floor' ? r.floorStatus : r.roomStatus
    switch (status) {
        case 'ASSIGNED': {
            if (slot === 'floor' && r.floor) return `${r.floor.displayName} (${r.floor.floorId})`
            if (slot === 'room' && r.room) return `${r.room.displayName} (${r.room.roomId})`
            // Unreachable given the invariant; degrade honestly rather than lie.
            return 'Not found at position'
        }
        case 'NOT_AVAILABLE_FROM_BIM': return 'Not available from BIM'
        case 'NOT_FOUND_AT_POSITION': return 'Not found at position'
        case 'AMBIGUOUS': return 'Ambiguous (multiple candidates)'
        case 'OUTSIDE_MODELED_SPACE': return 'Outside modeled space'
        default: return String(status)
    }
}

/** Structured id/label accessors (used by the inspector's explicit fields). */
export function associationSlotId(r: SpatialAssociationResult, slot: 'floor' | 'room'): string {
    if (slot === 'floor') return r.floor?.floorId ?? 'NONE'
    return r.room?.roomId ?? 'NONE'
}
export function associationSlotDisplay(r: SpatialAssociationResult, slot: 'floor' | 'room'): string {
    if (slot === 'floor') return r.floor?.displayName ?? 'NONE'
    return r.room?.displayName ?? 'NONE'
}

/**
 * Bounded, human-readable one-line summary of an association (DEV inspector).
 * Explicitly exposes BOTH status AND id AND label for floor and room so the two
 * are never compressed into one ambiguous field.
 */
export function summarizeAssociation(r: SpatialAssociationResult): string {
    return [
        `asset=${r.assetInstanceId}`,
        `position=(${r.provenance.testedPoint.x.toFixed(2)},${r.provenance.testedPoint.y.toFixed(2)},${r.provenance.testedPoint.z.toFixed(2)})`,
        `floorStatus=${r.floorStatus}`,
        `floorId=${associationSlotId(r, 'floor')}`,
        `floorLabel=${associationSlotDisplay(r, 'floor')}`,
        `roomStatus=${r.roomStatus}`,
        `roomId=${associationSlotId(r, 'room')}`,
        `roomLabel=${associationSlotDisplay(r, 'room')}`,
        `method=${r.provenance.method}`,
        `source=${r.provenance.source}`,
        `srcIds=${r.provenance.sourceElementIds.join(',') || '—'}`,
        `validity=${r.validity}`,
    ].join(' | ')
}

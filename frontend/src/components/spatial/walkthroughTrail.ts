/**
 * walkthroughTrail — pure, Bentley-free WALKTHROUGH PROGRESSION TRAIL (Build 1B).
 *
 * The walker marker already shows POSITION + HEADING (from the single
 * walkthroughController read-model). This module adds the SEPARATE, app-owned
 * HISTORICAL trail: the route the user has actually walked, so the 2D plan can
 * show START → travelled path → CURRENT.
 *
 * DOCTRINE:
 *   - VISUALIZATION-ONLY HISTORY. The trail is derived EXCLUSIVELY from
 *     successive authoritative `WalkthroughState` snapshots
 *     (walkthroughController). It is NEVER a second movement model and can NEVER
 *     move the walker (PLAN_CAN_MOVE_WALKER = NO / DUPLICATE_WALKER_STORE = NO).
 *   - TRANSLATION-ONLY SAMPLING. A point is appended only when the walker has
 *     translated ≥ WALKTHROUGH_TRAIL_MIN_STEP_M in XY from the previous accepted
 *     point. Turning in place, looking up/down, and changing FOV produce zero XY
 *     translation, so they never extend the trail.
 *   - STOREY-SCOPED SEGMENTS. Each segment belongs to one storey; a storey change
 *     starts a new segment. Rendering draws only the active storey's segments, so
 *     there is never a false diagonal connector between floors.
 *   - NO FALSE CONNECTORS ON DISCONTINUITY. A targeted re-entry / reset / new
 *     session / large teleport jump CLOSES the current segment and STARTS a new
 *     one at the new spawn — never a straight line across walls/floors.
 *   - PURE + DETERMINISTIC. No @itwin, no DOM, no viewport. Same input sequence
 *     => same trail, so it is fully unit-testable.
 */

export interface TrailVec2 { x: number; y: number }

/** One accepted trail point (world XY + the storey it occurred on). */
export interface TrailPoint {
    x: number
    y: number
    storeyId?: string
    /** Monotonic sequence index across the whole session (diagnostic/order). */
    seq: number
}

/** A contiguous same-storey run of trail points (a polyline). */
export interface TrailSegment {
    /** Segment index within the session (0-based). */
    index: number
    storeyId?: string
    points: TrailPoint[]
}

/** The app-owned trail state for the CURRENT walkthrough session. */
export interface WalkthroughTrail {
    /** True once a session is open (walker active). */
    active: boolean
    segments: TrailSegment[]
    /** Total accepted points across the session. */
    pointCount: number
    /** Next sequence index to assign. */
    nextSeq: number
}

/**
 * Minimum XY translation (metres) between accepted trail points. Justified by the
 * walkthrough movement scale: WALKTHROUGH_SPEED_M_PER_S = 1.6 m/s, so a per-frame
 * step (~0.1 s) is ~0.16 m; a 0.5 m threshold samples roughly every ~0.3 s of
 * continuous walking — dense enough to read the path, sparse enough to avoid
 * thousands of near-duplicate points.
 */
export const WALKTHROUGH_TRAIL_MIN_STEP_M = 0.5

/**
 * A jump larger than this (metres) is treated as a DISCONTINUITY (targeted entry /
 * reset / teleport), not a walked step — it starts a NEW segment with no connector.
 * A normal per-frame walk step is well under this, so genuine walking never trips it.
 */
export const WALKTHROUGH_TRAIL_JUMP_M = 5

/** The empty trail (no session open). */
export function emptyTrail(): WalkthroughTrail {
    return { active: false, segments: [], pointCount: 0, nextSeq: 0 }
}

function dist2d(a: TrailVec2, b: TrailVec2): number {
    return Math.hypot(a.x - b.x, a.y - b.y)
}

function isFiniteNum(n: unknown): n is number { return typeof n === 'number' && Number.isFinite(n) }

/** The last accepted point of the whole trail (across segments), or undefined. */
function lastPoint(trail: WalkthroughTrail): TrailPoint | undefined {
    for (let i = trail.segments.length - 1; i >= 0; i--) {
        const seg = trail.segments[i]
        if (seg.points.length > 0) return seg.points[seg.points.length - 1]
    }
    return undefined
}

/** The current (last) open segment, or undefined. */
function currentSegment(trail: WalkthroughTrail): TrailSegment | undefined {
    return trail.segments.length > 0 ? trail.segments[trail.segments.length - 1] : undefined
}

/** A minimal authoritative sample the trail consumes (a subset of WalkthroughState). */
export interface TrailSample {
    active: boolean
    eye: { x: number; y: number; z: number }
    storeyId?: string
}

/**
 * Advance the trail with one authoritative walkthrough sample. Returns a NEW trail
 * (pure; never mutates the input). Rules:
 *   - sample.active === false  => the session ends (active=false); segments kept.
 *   - first active sample (session start) => open a new segment + record the spawn.
 *   - storey change             => close current, open a new segment at the new point.
 *   - jump ≥ JUMP_M (teleport)   => close current, open a new segment (no connector).
 *   - translation ≥ MIN_STEP_M  => append to the current segment.
 *   - otherwise (turn/pitch/fov / tiny move) => unchanged.
 */
export function advanceTrail(trail: WalkthroughTrail, sample: TrailSample): WalkthroughTrail {
    // Session end: mark inactive, keep history (renderer may clear on new session).
    if (!sample.active) {
        if (!trail.active) return trail
        return { ...trail, active: false }
    }
    if (!isFiniteNum(sample.eye?.x) || !isFiniteNum(sample.eye?.y)) return trail

    const pt = (seq: number): TrailPoint => ({ x: sample.eye.x, y: sample.eye.y, storeyId: sample.storeyId, seq })

    // New session (was inactive) OR no segment yet => start a fresh segment + spawn.
    if (!trail.active || trail.segments.length === 0) {
        const seg: TrailSegment = { index: trail.segments.length === 0 ? 0 : trail.segments.length, storeyId: sample.storeyId, points: [pt(trail.nextSeq)] }
        // A brand-new session (was inactive with prior history) starts a new
        // segment; existing history is preserved but a new run begins.
        const segments = !trail.active && trail.segments.length > 0
            ? [...trail.segments, { ...seg, index: trail.segments.length }]
            : [seg]
        return { active: true, segments, pointCount: trail.pointCount + 1, nextSeq: trail.nextSeq + 1 }
    }

    const seg = currentSegment(trail)!
    const last = lastPoint(trail)
    const here = { x: sample.eye.x, y: sample.eye.y }

    // Fresh (empty) current segment — e.g. just after breakTrailSegment. SEED it
    // with this sample regardless of step: it is the start of a new run, adopting
    // the sample's storey (a break may precede a storey change).
    if (seg.points.length === 0) {
        const seeded: TrailSegment = { ...seg, storeyId: sample.storeyId, points: [pt(trail.nextSeq)] }
        const segments = trail.segments.slice(0, -1).concat(seeded)
        return { ...trail, segments, pointCount: trail.pointCount + 1, nextSeq: trail.nextSeq + 1 }
    }

    // Storey change => new segment (never connect across storeys).
    if ((seg.storeyId ?? undefined) !== (sample.storeyId ?? undefined)) {
        const newSeg: TrailSegment = { index: trail.segments.length, storeyId: sample.storeyId, points: [pt(trail.nextSeq)] }
        return { ...trail, segments: [...trail.segments, newSeg], pointCount: trail.pointCount + 1, nextSeq: trail.nextSeq + 1 }
    }

    // Teleport/reset jump => new segment (no false connector).
    if (last && dist2d(last, here) >= WALKTHROUGH_TRAIL_JUMP_M) {
        const newSeg: TrailSegment = { index: trail.segments.length, storeyId: sample.storeyId, points: [pt(trail.nextSeq)] }
        return { ...trail, segments: [...trail.segments, newSeg], pointCount: trail.pointCount + 1, nextSeq: trail.nextSeq + 1 }
    }

    // Meaningful translation => append to the current segment.
    if (!last || dist2d(last, here) >= WALKTHROUGH_TRAIL_MIN_STEP_M) {
        const appended: TrailSegment = { ...seg, points: [...seg.points, pt(trail.nextSeq)] }
        const segments = trail.segments.slice(0, -1).concat(appended)
        return { ...trail, segments, pointCount: trail.pointCount + 1, nextSeq: trail.nextSeq + 1 }
    }

    // Turn-in-place / pitch / FOV / sub-threshold move => no change.
    return trail
}

/**
 * Force a NEW segment at the next sample (used by an explicit discontinuity the
 * caller already knows about — targeted entry / reset). Marks the current session
 * so the next `advanceTrail` opens a new segment even if the position barely moved.
 * Implemented by appending an empty sentinel segment that the next active sample
 * fills; if the last segment is already empty this is a no-op.
 */
export function breakTrailSegment(trail: WalkthroughTrail): WalkthroughTrail {
    if (!trail.active) return trail
    const seg = currentSegment(trail)
    if (seg && seg.points.length === 0) return trail // already broken/empty
    return { ...trail, segments: [...trail.segments, { index: trail.segments.length, storeyId: seg?.storeyId, points: [] }] }
}

/** The trail segments to DRAW for a given storey (storey-scoped; never cross-storey). */
export function trailSegmentsForStorey(trail: WalkthroughTrail, storeyId: string | undefined): TrailSegment[] {
    return trail.segments.filter((s) => (s.storeyId ?? undefined) === (storeyId ?? undefined) && s.points.length > 0)
}

/** Total drawable points for a storey (diagnostic). */
export function trailPointCountForStorey(trail: WalkthroughTrail, storeyId: string | undefined): number {
    return trailSegmentsForStorey(trail, storeyId).reduce((n, s) => n + s.points.length, 0)
}

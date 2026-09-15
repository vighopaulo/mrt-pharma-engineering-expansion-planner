/**
 * Build 1B Defect 2 — WALKTHROUGH PROGRESSION TRAIL pure domain tests.
 *
 *   §25 — TRAIL SAMPLING. The trail is derived EXCLUSIVELY from successive
 *         authoritative walkthrough samples. A point is appended only on
 *         meaningful XY translation (≥ WALKTHROUGH_TRAIL_MIN_STEP_M); turning in
 *         place, looking up/down and changing FOV produce zero XY translation, so
 *         they never extend it. The trail can never move the walker (it is a pure
 *         function of samples with no feedback).
 *   §26 — TRAIL SEGMENTS. Segments are storey-scoped (a storey change starts a new
 *         segment; rendering is per-storey so there is never a false cross-storey
 *         connector). A teleport / reset / new session starts a new segment with no
 *         connector. Session end keeps history.
 *
 * The trail module is pure + deterministic — no @itwin, no DOM, no viewport.
 */
import { describe, it, expect } from 'vitest'
import {
    emptyTrail,
    advanceTrail,
    breakTrailSegment,
    trailSegmentsForStorey,
    trailPointCountForStorey,
    WALKTHROUGH_TRAIL_MIN_STEP_M,
    WALKTHROUGH_TRAIL_JUMP_M,
    type WalkthroughTrail,
    type TrailSample,
} from '../components/spatial/walkthroughTrail'

// Convenience: an active sample at (x,y) on a storey.
function s(x: number, y: number, storeyId: string | undefined = 's1', active = true): TrailSample {
    return { active, eye: { x, y, z: 1.65 }, storeyId }
}

// Feed a sequence of samples through advanceTrail from empty.
function run(samples: TrailSample[]): WalkthroughTrail {
    return samples.reduce((t, sample) => advanceTrail(t, sample), emptyTrail())
}

// ===========================================================================
// §25 — TRAIL SAMPLING
// ===========================================================================

describe('§25 walkthrough trail sampling', () => {
    it('starts empty (no session, no points)', () => {
        const t = emptyTrail()
        expect(t.active).toBe(false)
        expect(t.segments).toHaveLength(0)
        expect(t.pointCount).toBe(0)
    })

    it('the first active sample opens a session and records the spawn point', () => {
        const t = advanceTrail(emptyTrail(), s(5, 5))
        expect(t.active).toBe(true)
        expect(t.pointCount).toBe(1)
        expect(t.segments).toHaveLength(1)
        expect(t.segments[0].points[0]).toMatchObject({ x: 5, y: 5, storeyId: 's1' })
    })

    it('appends a point only after ≥ MIN_STEP_M of XY translation', () => {
        // Walk forward in steps just under, then over, the threshold.
        const t = run([
            s(0, 0),
            s(0, WALKTHROUGH_TRAIL_MIN_STEP_M - 0.01), // sub-threshold: ignored
            s(0, WALKTHROUGH_TRAIL_MIN_STEP_M + 0.01), // crosses threshold: appended
        ])
        expect(t.pointCount).toBe(2) // spawn + one accepted step
    })

    it('TURNING IN PLACE never extends the trail (no XY translation)', () => {
        // Same eye position; the trail cannot see yaw/pitch/fov — only eye XY.
        const t = run([s(3, 3), s(3, 3), s(3, 3)])
        expect(t.pointCount).toBe(1) // only the spawn point
        expect(trailPointCountForStorey(t, 's1')).toBe(1)
    })

    it('accumulates a walked path as a sequence of accepted points', () => {
        const t = run([s(0, 0), s(0, 1), s(0, 2), s(0, 3)])
        expect(t.pointCount).toBe(4)
        expect(trailSegmentsForStorey(t, 's1')).toHaveLength(1)
        expect(trailSegmentsForStorey(t, 's1')[0].points.map((p) => p.y)).toEqual([0, 1, 2, 3])
    })

    it('is PURE — never mutates its input trail', () => {
        const before = run([s(0, 0), s(0, 1)])
        const snapshot = JSON.stringify(before)
        const after = advanceTrail(before, s(0, 2))
        expect(JSON.stringify(before)).toEqual(snapshot) // input unchanged
        expect(after).not.toBe(before) // new object
        expect(after.pointCount).toBe(before.pointCount + 1)
    })

    it('is DETERMINISTIC — same sample sequence yields the same trail', () => {
        const seq = [s(0, 0), s(0, 1), s(1, 1), s(2, 1)]
        expect(JSON.stringify(run(seq))).toEqual(JSON.stringify(run(seq)))
    })

    it('ignores non-finite eye coordinates (never corrupts the trail)', () => {
        const t = run([s(0, 0), { active: true, eye: { x: NaN, y: 1, z: 0 }, storeyId: 's1' }, s(0, 1)])
        expect(t.pointCount).toBe(2) // spawn + the valid (0,1) step; NaN ignored
        expect(Number.isFinite(t.segments[0].points[1].x)).toBe(true)
    })
})

// ===========================================================================
// §26 — TRAIL SEGMENTS (storey-scoped; discontinuities; session end)
// ===========================================================================

describe('§26 walkthrough trail segments', () => {
    it('a storey change starts a NEW segment (no cross-storey connector)', () => {
        const t = run([s(0, 0, 's1'), s(0, 1, 's1'), s(0, 1, 's2'), s(0, 2, 's2')])
        expect(t.segments).toHaveLength(2)
        expect(t.segments[0].storeyId).toBe('s1')
        expect(t.segments[1].storeyId).toBe('s2')
    })

    it('rendering is STOREY-SCOPED — only the active storey draws', () => {
        const t = run([s(0, 0, 's1'), s(0, 1, 's1'), s(0, 1, 's2'), s(0, 2, 's2')])
        expect(trailSegmentsForStorey(t, 's1').every((seg) => seg.storeyId === 's1')).toBe(true)
        expect(trailSegmentsForStorey(t, 's2').every((seg) => seg.storeyId === 's2')).toBe(true)
        // A storey with no history draws nothing.
        expect(trailSegmentsForStorey(t, 's3')).toHaveLength(0)
    })

    it('a teleport jump (≥ JUMP_M) starts a NEW segment (no false connector)', () => {
        const t = run([s(0, 0), s(0, 1), s(0, 1 + WALKTHROUGH_TRAIL_JUMP_M + 1)])
        expect(t.segments).toHaveLength(2)
        // The new segment begins at the teleport destination, disconnected.
        const last = t.segments[t.segments.length - 1]
        expect(last.points[0].y).toBeCloseTo(1 + WALKTHROUGH_TRAIL_JUMP_M + 1, 6)
    })

    it('a new SESSION (active false -> true) starts a new segment but keeps history', () => {
        const walked = run([s(0, 0), s(0, 1), s(0, 2)])
        const ended = advanceTrail(walked, { active: false, eye: { x: 0, y: 2, z: 1.65 }, storeyId: 's1' })
        expect(ended.active).toBe(false)
        expect(ended.segments).toHaveLength(1) // history preserved
        const reentered = advanceTrail(ended, s(20, 20)) // new spawn far away
        expect(reentered.active).toBe(true)
        expect(reentered.segments).toHaveLength(2) // fresh segment, old kept
        expect(reentered.segments[1].points[0]).toMatchObject({ x: 20, y: 20 })
    })

    it('session end keeps the history (inactive but segments retained)', () => {
        const t = advanceTrail(run([s(0, 0), s(0, 1)]), { active: false, eye: { x: 0, y: 1, z: 0 }, storeyId: 's1' })
        expect(t.active).toBe(false)
        expect(t.pointCount).toBe(2)
        expect(trailSegmentsForStorey(t, 's1')[0].points).toHaveLength(2)
    })

    it('breakTrailSegment forces a new segment at the next sample (targeted entry/reset)', () => {
        const walked = run([s(0, 0), s(0, 1)])
        const broken = breakTrailSegment(walked)
        // The next sample (even a tiny move) begins a fresh segment.
        const next = advanceTrail(broken, s(0, 1.05))
        const drawn = trailSegmentsForStorey(next, 's1')
        expect(drawn.length).toBeGreaterThanOrEqual(2)
        // The new segment's first point is the re-entry position.
        expect(drawn[drawn.length - 1].points[0].y).toBeCloseTo(1.05, 6)
    })

    it('breakTrailSegment is a no-op on an inactive trail', () => {
        const t = emptyTrail()
        expect(breakTrailSegment(t)).toBe(t)
    })

    it('trailPointCountForStorey sums only that storey drawable points', () => {
        const t = run([s(0, 0, 's1'), s(0, 1, 's1'), s(0, 1, 's2')])
        expect(trailPointCountForStorey(t, 's1')).toBe(2)
        expect(trailPointCountForStorey(t, 's2')).toBe(1)
    })
})

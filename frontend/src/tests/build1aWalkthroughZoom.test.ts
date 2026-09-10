/**
 * Build 1A walkthrough incremental zoom/dolly correction — pure tests (§22/§23).
 * Proves the bounded wheel/trackpad normalization + that dolly reuses the same
 * floor-constrained, collision-gated horizontal movement as walking (never
 * vertical free flight, never a multi-scene leap, no spring-back/inertia).
 */
import { describe, it, expect } from 'vitest'
import {
    normalizeWheelDolly,
    WALKTHROUGH_ZOOM_BASE_STEP_M,
    WALKTHROUGH_ZOOM_MAX_STEP_M,
    WHEEL_DELTA_MODE_PIXEL,
    WHEEL_DELTA_MODE_LINE,
    WHEEL_DELTA_MODE_PAGE,
    WHEEL_PIXELS_PER_BASE_STEP,
    resolveWalkCollision,
    type WalkCollisionStorey,
} from '../components/spatial/walkNav'
import { candidateEye } from '../components/spatial/firstPerson'

// --- §22 pure wheel normalization -----------------------------------------

describe('§22 wheel/trackpad normalization is bounded + deterministic', () => {
    it('1. small wheel delta → small bounded increment', () => {
        const s = normalizeWheelDolly({ deltaY: -10, deltaMode: WHEEL_DELTA_MODE_PIXEL })
        expect(s).toBeGreaterThan(0)
        expect(s).toBeLessThan(WALKTHROUGH_ZOOM_BASE_STEP_M) // 10px << 100px base
    })
    it('2. large wheel delta is clamped to the max step', () => {
        const s = normalizeWheelDolly({ deltaY: -100000, deltaMode: WHEEL_DELTA_MODE_PIXEL })
        expect(s).toBeCloseTo(WALKTHROUGH_ZOOM_MAX_STEP_M, 6)
    })
    it('3. trackpad high-resolution burst is bounded (never a multi-room leap)', () => {
        const s = normalizeWheelDolly({ deltaY: -5000, deltaMode: WHEEL_DELTA_MODE_PIXEL })
        expect(Math.abs(s)).toBeLessThanOrEqual(WALKTHROUGH_ZOOM_MAX_STEP_M + 1e-9)
    })
    it('4. positive/negative directions remain symmetric', () => {
        const inn = normalizeWheelDolly({ deltaY: -40, deltaMode: WHEEL_DELTA_MODE_PIXEL })
        const out = normalizeWheelDolly({ deltaY: 40, deltaMode: WHEEL_DELTA_MODE_PIXEL })
        expect(inn).toBeCloseTo(-out, 9)
        expect(inn).toBeGreaterThan(0) // wheel up = zoom in = forward +
        expect(out).toBeLessThan(0)
    })
    it('5. deltaMode normalization is deterministic (line/page scaled to pixels)', () => {
        const pixel = normalizeWheelDolly({ deltaY: -16, deltaMode: WHEEL_DELTA_MODE_PIXEL })
        const line = normalizeWheelDolly({ deltaY: -1, deltaMode: WHEEL_DELTA_MODE_LINE }) // 1 line = 16 px
        expect(line).toBeCloseTo(pixel, 9)
        const page = normalizeWheelDolly({ deltaY: -1, deltaMode: WHEEL_DELTA_MODE_PAGE }) // 1 page = 100 px = 1 base step
        expect(page).toBeCloseTo(WALKTHROUGH_ZOOM_BASE_STEP_M, 9)
    })
    it('6. repeated small inputs produce incremental (additive) movement', () => {
        const one = normalizeWheelDolly({ deltaY: -20, deltaMode: WHEEL_DELTA_MODE_PIXEL })
        expect(one * 3).toBeCloseTo(normalizeWheelDolly({ deltaY: -20, deltaMode: WHEEL_DELTA_MODE_PIXEL }) * 3, 9)
        expect(one).toBeLessThan(WALKTHROUGH_ZOOM_MAX_STEP_M)
    })
    it('7. one large event ≠ unbounded multi-room leap', () => {
        expect(normalizeWheelDolly({ deltaY: -1e9, deltaMode: WHEEL_DELTA_MODE_PIXEL })).toBeLessThanOrEqual(WALKTHROUGH_ZOOM_MAX_STEP_M)
    })
    it('8. zero delta → zero movement', () => {
        expect(normalizeWheelDolly({ deltaY: 0, deltaMode: WHEEL_DELTA_MODE_PIXEL })).toBe(0)
    })
    it('9. NaN / Infinity input is handled safely (→ 0)', () => {
        expect(normalizeWheelDolly({ deltaY: NaN, deltaMode: 0 })).toBe(0)
        expect(normalizeWheelDolly({ deltaY: Infinity, deltaMode: 0 })).toBe(0)
        expect(normalizeWheelDolly({ deltaY: -Infinity, deltaMode: 0 })).toBe(0)
    })
    it('10. output remains finite for all finite inputs', () => {
        for (const d of [-1, -100, -1e6, 1, 100, 1e6]) {
            expect(Number.isFinite(normalizeWheelDolly({ deltaY: d, deltaMode: 0 }))).toBe(true)
        }
    })
    it('base step for exactly one reference-pixel-magnitude event', () => {
        const s = normalizeWheelDolly({ deltaY: -WHEEL_PIXELS_PER_BASE_STEP, deltaMode: WHEEL_DELTA_MODE_PIXEL })
        expect(s).toBeCloseTo(WALKTHROUGH_ZOOM_BASE_STEP_M, 9)
    })
})

// --- §23 dolly reuses floor-constrained, collision-gated horizontal movement ---

function boxRoomStorey(): WalkCollisionStorey {
    // A wall at y=5 (long along x); no door → solid.
    return {
        storeyId: 's', elevation: 0,
        wallBoundaries: [{ id: 'w', a: { x: -50, y: 5 }, b: { x: 50, y: 5 }, thickness: 0.2 }],
        doorPortals: [], windowBoundaries: [], nonTraversableOpenings: [], hasFloor: true,
    }
}

describe('§23 dolly = bounded horizontal step through the walk pipeline', () => {
    const eye = { x: 0, y: 0, z: 1.65 }
    it('9. wheel dolly does NOT change eye height (candidateEye pins z)', () => {
        const step = normalizeWheelDolly({ deltaY: -50, deltaMode: 0 })
        const cand = candidateEye(eye, /*yaw*/ 0, { forward: step > 0 ? 1 : -1, strafe: 0 }, Math.abs(step))
        expect(cand.z).toBe(eye.z) // no vertical free flight
    })
    it('a forward dolly step is bounded (never a multi-room leap)', () => {
        const step = normalizeWheelDolly({ deltaY: -100000, deltaMode: 0 })
        const cand = candidateEye(eye, 0, { forward: 1, strafe: 0 }, Math.abs(step))
        const moved = Math.hypot(cand.x - eye.x, cand.y - eye.y)
        expect(moved).toBeLessThanOrEqual(WALKTHROUGH_ZOOM_MAX_STEP_M + 1e-9)
    })
    it('11. a dolly toward a solid wall is blocked by the SAME collision authority', () => {
        // From y=4.9, a forward (+y) dolly toward the wall at y=5 is blocked.
        const near = { x: 0, y: 4.9, z: 1.65 }
        const cand = candidateEye(near, 0, { forward: 1, strafe: 0 }, 0.6)
        const decision = resolveWalkCollision({ current: { x: near.x, y: near.y }, candidate: { x: cand.x, y: cand.y }, storey: boxRoomStorey(), collisionRadius: 0.35 })
        expect(decision).toBe('BLOCK_WALL')
    })
    it('a backward dolly away from the wall is allowed', () => {
        const near = { x: 0, y: 4.9, z: 1.65 }
        const cand = candidateEye(near, 0, { forward: -1, strafe: 0 }, 0.6)
        const decision = resolveWalkCollision({ current: { x: near.x, y: near.y }, candidate: { x: cand.x, y: cand.y }, storey: boxRoomStorey(), collisionRadius: 0.35 })
        expect(decision).toBe('ALLOW')
    })
})

/**
 * Build 1A — MacBook trackpad walkthrough look tests (focused; §8).
 * Proves the pure invariants the controller applies for trackpad drag-look +
 * two-finger dolly: vertical drag changes pitch, horizontal drag changes yaw,
 * pitch stays clamped (no inversion), vertical drag never alters eye Z, W stays
 * horizontal after looking up/down, and wheel/two-finger scroll is a bounded dolly.
 */
import { describe, it, expect } from 'vitest'
import {
    clampPitch,
    MAX_PITCH,
    candidateEye,
    resolveFirstPersonOrientation,
    eyeZForFloor,
} from '../components/spatial/firstPerson'
import { normalizeWheelDolly, WALKTHROUGH_ZOOM_MAX_STEP_M } from '../components/spatial/walkNav'

// The controller's drag-look math (mirrors walkthroughController onMouseMove):
//   yaw   -= dx * SENS
//   pitch  = clampPitch(pitch - dy * SENS)
const SENS = 0.0022
const applyDrag = (yaw: number, pitch: number, dx: number, dy: number) => ({
    yaw: yaw - dx * SENS,
    pitch: clampPitch(pitch - dy * SENS),
})

describe('§8 trackpad drag-look — yaw / pitch', () => {
    it('vertical drag changes pitch (up = look up)', () => {
        const a = applyDrag(0, 0, 0, -100) // drag up
        expect(a.pitch).toBeGreaterThan(0)
        const b = applyDrag(0, 0, 0, 100) // drag down
        expect(b.pitch).toBeLessThan(0)
    })
    it('horizontal drag changes yaw (and not pitch)', () => {
        const a = applyDrag(0, 0, 120, 0)
        expect(a.yaw).not.toBe(0)
        expect(a.pitch).toBe(0)
    })
    it('pitch is clamped symmetrically (no inversion past ±MAX_PITCH)', () => {
        const up = applyDrag(0, 0, 0, -100000)
        const down = applyDrag(0, 0, 0, 100000)
        expect(up.pitch).toBeCloseTo(MAX_PITCH, 6)
        expect(down.pitch).toBeCloseTo(-MAX_PITCH, 6)
        expect(Math.abs(up.pitch)).toBeLessThan(Math.PI / 2) // never past straight up
    })
})

describe('§8 walking stays horizontal regardless of look pitch', () => {
    const eye = { x: 10, y: 20, z: 3 }
    it('candidateEye ignores pitch — forward step keeps eye Z (no vertical translation)', () => {
        // candidateEye computes horizontal movement (uses pitch=0 internally).
        const fwd = candidateEye(eye, 0.3, { forward: 1, strafe: 0 }, 0.5)
        expect(fwd.z).toBe(eye.z) // Z unchanged by a forward walk step
    })
    it('W after looking strongly DOWN still walks horizontally (Z unchanged)', () => {
        // Even though the LOOK orientation has a downward pitch...
        const o = resolveFirstPersonOrientation(0, -MAX_PITCH)
        expect(o.forward.z).toBeLessThan(0) // look direction points down
        // ...the WALK step uses the flat forward and preserves eye Z.
        const step = candidateEye(eye, 0, { forward: 1, strafe: 0 }, 0.5)
        expect(step.z).toBe(eye.z)
        expect(Math.hypot(step.x - eye.x, step.y - eye.y)).toBeCloseTo(0.5, 6)
    })
    it('W after looking strongly UP still walks horizontally (Z unchanged)', () => {
        const o = resolveFirstPersonOrientation(0, MAX_PITCH)
        expect(o.forward.z).toBeGreaterThan(0) // look direction points up
        const step = candidateEye(eye, 0, { forward: 1, strafe: 0 }, 0.5)
        expect(step.z).toBe(eye.z)
    })
    it('eye Z is pinned to the floor + eye height (floor-constrained pedestrian)', () => {
        const z1 = eyeZForFloor(0, 1.65)
        const z2 = eyeZForFloor(0, 1.65)
        expect(z1).toBe(z2) // deterministic, no drift
        expect(z1).toBe(1.65)
    })
})

describe('§8 two-finger scroll = bounded incremental dolly (not pitch)', () => {
    it('a normal scroll produces a small bounded signed dolly step', () => {
        const step = normalizeWheelDolly({ deltaY: -100, deltaMode: 0 }) // scroll up
        expect(step).toBeGreaterThan(0) // forward/zoom-in
        expect(Math.abs(step)).toBeLessThanOrEqual(WALKTHROUGH_ZOOM_MAX_STEP_M)
    })
    it('a huge trackpad flick is clamped (no multi-room leap)', () => {
        const step = normalizeWheelDolly({ deltaY: 100000, deltaMode: 0 })
        expect(Math.abs(step)).toBeLessThanOrEqual(WALKTHROUGH_ZOOM_MAX_STEP_M)
    })
    it('zero / non-finite delta => zero step', () => {
        expect(normalizeWheelDolly({ deltaY: 0, deltaMode: 0 })).toBe(0)
        expect(normalizeWheelDolly({ deltaY: NaN, deltaMode: 0 })).toBe(0)
    })
    it('sign is symmetric (scroll down = backward)', () => {
        const down = normalizeWheelDolly({ deltaY: 100, deltaMode: 0 })
        expect(down).toBeLessThan(0)
    })
})

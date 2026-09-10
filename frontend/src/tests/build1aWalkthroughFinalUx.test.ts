/**
 * Build 1A walkthrough final UX — focused pure regression tests for full look
 * pitch (up + down, clamped, no inversion) while movement stays a floor-
 * constrained pedestrian (pitch never drives vertical translation).
 */
import { describe, it, expect } from 'vitest'
import {
    candidateEye,
    clampPitch,
    MAX_PITCH,
    resolveFirstPersonOrientation,
    eyeZForFloor,
} from '../components/spatial/firstPerson'

const near = (a: number, b: number, eps = 1e-9) => Math.abs(a - b) <= eps

// The controller's mouse-look applies: pitch = clampPitch(pitch - movementY*SENS).
// Dragging UP => movementY < 0 => pitch increases (look up); DOWN => decreases.
const SENS = 0.0022
const applyLook = (pitch: number, movementY: number) => clampPitch(pitch - movementY * SENS)

describe('§7-9 full look pitch (up + down), clamped, no inversion', () => {
    it('look UP increases pitch (drag up = negative movementY)', () => {
        const p1 = applyLook(0, -100)
        expect(p1).toBeGreaterThan(0)
    })
    it('look DOWN decreases pitch (drag down = positive movementY)', () => {
        const p1 = applyLook(0, 100)
        expect(p1).toBeLessThan(0)
    })
    it('pitch is symmetric up/down and clamped to +/- MAX_PITCH (no inversion)', () => {
        // Huge upward drag clamps at +MAX_PITCH; huge downward at -MAX_PITCH.
        let up = 0
        for (let i = 0; i < 10000; i++) up = applyLook(up, -100)
        expect(up).toBe(MAX_PITCH)
        let down = 0
        for (let i = 0; i < 10000; i++) down = applyLook(down, 100)
        expect(down).toBe(-MAX_PITCH)
        // MAX_PITCH stays below vertical (never inverts): < PI/2.
        expect(MAX_PITCH).toBeLessThan(Math.PI / 2)
    })
    it('the look vector points upward at max up-pitch and downward at max down-pitch', () => {
        expect(resolveFirstPersonOrientation(0, MAX_PITCH).forward.z).toBeGreaterThan(0)
        expect(resolveFirstPersonOrientation(0, -MAX_PITCH).forward.z).toBeLessThan(0)
    })
})

describe('§10 pitch controls VIEW only — translation stays horizontal', () => {
    it('candidateEye ignores pitch entirely (yaw-only walk vector)', () => {
        const eye = { x: 0, y: 0, z: 1.65 }
        // candidateEye takes (eye, yaw, input, step) — pitch is never an input.
        const c = candidateEye(eye, 0, { forward: 1, strafe: 0 }, 2)
        expect(near(c.x, 0)).toBe(true)
        expect(near(c.y, 2)).toBe(true)
        expect(c.z).toBe(1.65) // Z unchanged by a forward step
    })
    it('W forward keeps eye Z stable while looking strongly UP', () => {
        const eye = { x: 0, y: 0, z: 1.65 }
        // Regardless of look pitch, the horizontal forward step keeps Z.
        const c = candidateEye(eye, 0, { forward: 1, strafe: 0 }, 3)
        expect(c.z).toBe(1.65)
        // (the camera would look up via orientation, but the WALK vector is flat)
        expect(resolveFirstPersonOrientation(0, MAX_PITCH).forwardFlat.z).toBe(0)
    })
    it('W forward keeps eye Z stable while looking strongly DOWN (no floor dive)', () => {
        const eye = { x: 0, y: 0, z: 1.65 }
        const c = candidateEye(eye, 0, { forward: 1, strafe: 0 }, 3)
        expect(c.z).toBe(1.65)
        expect(resolveFirstPersonOrientation(0, -MAX_PITCH).forwardFlat.z).toBe(0)
    })
    it('S / A / D also keep eye Z stable on a level floor (no vertical drift)', () => {
        const eye = { x: 0, y: 0, z: 1.65 }
        expect(candidateEye(eye, 0, { forward: -1, strafe: 0 }, 2).z).toBe(1.65)
        expect(candidateEye(eye, 0, { forward: 0, strafe: 1 }, 2).z).toBe(1.65)
        expect(candidateEye(eye, 0, { forward: 0, strafe: -1 }, 2).z).toBe(1.65)
    })
})

describe('§10-11 floor-constrained eye height (no drift over repeated steps)', () => {
    it('repeated level walking never accumulates Z drift (eye Z re-derived from floor)', () => {
        const floorZ = 0
        const eyeHeight = 1.65
        // Simulate many horizontal steps; the controller re-pins Z = eyeZForFloor
        // each frame, so Z is invariant regardless of movement count.
        let eye = { x: 0, y: 0, z: eyeZForFloor(floorZ, eyeHeight) }
        for (let i = 0; i < 500; i++) {
            const c = candidateEye(eye, 0.3, { forward: 1, strafe: 1 }, 0.5)
            eye = { x: c.x, y: c.y, z: eyeZForFloor(floorZ, eyeHeight) }
            expect(eye.z).toBe(floorZ + eyeHeight)
        }
        expect(Number.isFinite(eye.x) && Number.isFinite(eye.y) && Number.isFinite(eye.z)).toBe(true)
    })
    it('eyeZForFloor is a pure function of (floor, height) — different storeys differ', () => {
        expect(eyeZForFloor(0, 1.65)).toBe(1.65)
        expect(eyeZForFloor(4, 1.65)).toBe(5.65) // upper storey => higher eye, no global constant
    })
})

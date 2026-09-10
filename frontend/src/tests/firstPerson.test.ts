/**
 * Offline tests for the pure first-person navigation + walk-movement + storey
 * selector policy. No Bentley runtime.
 */
import { describe, expect, it } from 'vitest'
import {
    candidateEye,
    clampPitch,
    eyeZForFloor,
    MAX_PITCH,
    resolveFirstPersonOrientation,
    resolveWalkMovement,
    storeySelectorEntries,
    type StoreyCandidate,
} from '../components/spatial/firstPerson'

const near = (a: number, b: number, eps = 1e-9) => Math.abs(a - b) < eps

describe('first-person orientation (yaw does not orbit the eye)', () => {
    it('changing yaw changes look direction only', () => {
        const a = resolveFirstPersonOrientation(0, 0)
        const b = resolveFirstPersonOrientation(Math.PI / 2, 0)
        expect(near(a.forwardFlat.x, 0)).toBe(true)
        expect(near(a.forwardFlat.y, 1)).toBe(true)
        expect(near(b.forwardFlat.x, 1)).toBe(true)
        expect(near(b.forwardFlat.y, 0)).toBe(true)
        expect(near(a.right.x, 1)).toBe(true)
    })
    it('YAW_DOES_NOT_ORBIT_EYE: no movement input keeps eye fixed under any yaw', () => {
        const eye = { x: 5, y: 7, z: 2 }
        for (const yaw of [0, 1, 2, 3, Math.PI]) {
            expect(candidateEye(eye, yaw, { forward: 0, strafe: 0 }, 1)).toEqual(eye)
        }
    })
})

describe('pitch clamp', () => {
    it('clamps beyond +/- MAX_PITCH and never flips', () => {
        expect(clampPitch(10)).toBe(MAX_PITCH)
        expect(clampPitch(-10)).toBe(-MAX_PITCH)
        expect(clampPitch(0.5)).toBe(0.5)
        expect(clampPitch(NaN)).toBe(0)
    })
})

describe('forward / strafe move the eye horizontally', () => {
    it('forward advances along horizontal forward vector', () => {
        const c = candidateEye({ x: 0, y: 0, z: 1.65 }, 0, { forward: 1, strafe: 0 }, 2)
        expect(near(c.x, 0)).toBe(true)
        expect(near(c.y, 2)).toBe(true)
        expect(c.z).toBe(1.65)
    })
    it('strafe moves along horizontal right vector', () => {
        const c = candidateEye({ x: 0, y: 0, z: 1.65 }, 0, { forward: 0, strafe: 1 }, 2)
        expect(near(c.x, 2)).toBe(true)
        expect(near(c.y, 0)).toBe(true)
    })
})

describe('walk movement resolution', () => {
    it('BLOCK_NO_FLOOR takes precedence even through a door', () => {
        expect(resolveWalkMovement({ crossing: 'DOOR', hasFloorSupport: false })).toBe('BLOCK_NO_FLOOR')
    })
    it('NONE => ALLOW, DOOR => ALLOW_DOOR', () => {
        expect(resolveWalkMovement({ crossing: 'NONE', hasFloorSupport: true })).toBe('ALLOW')
        expect(resolveWalkMovement({ crossing: 'DOOR', hasFloorSupport: true })).toBe('ALLOW_DOOR')
    })
    it('WALL => BLOCK_WALL, WINDOW => BLOCK_WINDOW, UNKNOWN => BLOCK_UNKNOWN_OPENING', () => {
        expect(resolveWalkMovement({ crossing: 'WALL', hasFloorSupport: true })).toBe('BLOCK_WALL')
        expect(resolveWalkMovement({ crossing: 'WINDOW', hasFloorSupport: true })).toBe('BLOCK_WINDOW')
        expect(resolveWalkMovement({ crossing: 'UNKNOWN_OPENING', hasFloorSupport: true })).toBe('BLOCK_UNKNOWN_OPENING')
    })
})

describe('floor support + eye height', () => {
    it('eye Z = walking surface elevation + generic eye height', () => {
        expect(eyeZForFloor(4, 1.65)).toBe(5.65)
        expect(eyeZForFloor(0, 1.65)).toBe(1.65)
    })
    it('no-floor movement is rejected regardless of crossing', () => {
        expect(resolveWalkMovement({ crossing: 'NONE', hasFloorSupport: false })).toBe('BLOCK_NO_FLOOR')
    })
})

describe('storey selector source (stories only; rooms excluded)', () => {
    const inv: StoreyCandidate[] = [
        { id: 's1', label: 'Level 1', kind: 'STORY' },
        { id: 's2', label: 'Level 2', kind: 'STORY' },
        { id: 's3', label: 'Level 3', kind: 'STORY' },
        { id: 's4', label: 'Level 4', kind: 'STORY' },
        ...Array.from({ length: 269 }, (_, i) => ({ id: `room${i}`, label: 'CORRIDOR', kind: 'SPACE' as const })),
        { id: 'c1', label: 'Composite', kind: 'COMPOSITE' as const },
    ]
    it('derives exactly the actual storeys and excludes all 269 rooms + composites', () => {
        const entries = storeySelectorEntries(inv)
        expect(entries.length).toBe(4)
        expect(entries.every((e) => e.kind === 'STORY')).toBe(true)
        expect(entries.some((e) => e.kind === 'SPACE')).toBe(false)
    })
    it('ROOM_BUTTON_COUNT_IN_BIRDS_EYE_TOP_LEVEL = 0', () => {
        const entries = storeySelectorEntries(inv)
        expect(entries.filter((e) => e.kind === 'SPACE').length).toBe(0)
    })
})

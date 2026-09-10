/**
 * Build 1A walkthrough forward-movement correction — pure domain tests.
 *
 * Proves: W=forward / S=backward (opposite of the same walk vector); A/D strafe;
 * the movement is horizontal (camera pitch never drives vertical translation);
 * floor contact never falsely blocks; a genuine wall crossing blocks; and — the
 * fix — a step moving AWAY from a nearby wall is no longer proximity-blocked
 * (the forward defect), while a step approaching a wall still blocks.
 */
import { describe, it, expect } from 'vitest'
import {
    candidateEye,
    resolveFirstPersonOrientation,
    eyeZForFloor,
    type Vec3,
} from '../components/spatial/firstPerson'
import {
    resolveWalkCollision,
    type WalkCollisionStorey,
    type WallSegment,
} from '../components/spatial/walkNav'

const EYE: Vec3 = { x: 0, y: 0, z: 5 }

// --- §20.1/2/5/6/7 forward/backward map to the same walk vector, opposite sign ---
describe('§20 W/S/A/D movement mapping', () => {
    it('W (forward=+1) at yaw 0 moves along +Y; S (forward=-1) moves along -Y', () => {
        const fwd = candidateEye(EYE, 0, { forward: 1, strafe: 0 }, 1)
        const back = candidateEye(EYE, 0, { forward: -1, strafe: 0 }, 1)
        expect(fwd.y).toBeCloseTo(1, 6)
        expect(back.y).toBeCloseTo(-1, 6)
        expect(fwd.x).toBeCloseTo(0, 6)
        // Opposite displacement of the SAME walk vector (shared pipeline).
        expect(fwd.y - EYE.y).toBeCloseTo(-(back.y - EYE.y), 6)
    })
    it('forward requested displacement is nonzero (the reported defect)', () => {
        const fwd = candidateEye(EYE, 0, { forward: 1, strafe: 0 }, 0.5)
        expect(Math.hypot(fwd.x - EYE.x, fwd.y - EYE.y)).toBeGreaterThan(0)
    })
    it('A/D strafe move along the horizontal right vector (opposite signs)', () => {
        const d = candidateEye(EYE, 0, { forward: 0, strafe: 1 }, 1) // D = +right
        const a = candidateEye(EYE, 0, { forward: 0, strafe: -1 }, 1) // A = -right
        expect(d.x).toBeCloseTo(1, 6) // right at yaw0 = +X
        expect(a.x).toBeCloseTo(-1, 6)
    })
})

// --- §20.8 / §10A-10I forward vector horizontal; pitch never drives vertical ---
describe('§10 walk is floor-constrained pedestrian, not free flight', () => {
    it('forwardFlat is horizontal (z=0) and unit-length at any pitch', () => {
        for (const pitch of [-1.4, -0.5, 0, 0.5, 1.4]) {
            const o = resolveFirstPersonOrientation(0.7, pitch)
            expect(o.forwardFlat.z).toBe(0)
            expect(Math.hypot(o.forwardFlat.x, o.forwardFlat.y)).toBeCloseTo(1, 6)
        }
    })
    it('candidateEye keeps eye Z constant regardless of look pitch (W looking DOWN)', () => {
        // candidateEye uses yaw-only horizontal forward; pitch is not an input.
        const down = candidateEye(EYE, 0, { forward: 1, strafe: 0 }, 1)
        expect(down.z).toBe(EYE.z) // no descent into the floor
    })
    it('candidateEye keeps eye Z constant (W looking UP)', () => {
        const up = candidateEye(EYE, 0, { forward: 1, strafe: 0 }, 1)
        expect(up.z).toBe(EYE.z) // no climb through the ceiling
    })
    it('eye Z follows floor + eye height (no drift), independent of movement', () => {
        expect(eyeZForFloor(0, 1.7)).toBe(1.7)
        expect(eyeZForFloor(4.5, 1.7)).toBe(6.2) // second storey floor
    })
    it('repeated level walking does not accumulate vertical drift', () => {
        let p = { ...EYE }
        for (let i = 0; i < 10; i++) p = candidateEye(p, 0.3, { forward: 1, strafe: 0 }, 0.5)
        expect(p.z).toBe(EYE.z)
        expect(Number.isFinite(p.x) && Number.isFinite(p.y)).toBe(true)
    })
})

// --- collision fix: away-from-wall no longer proximity-blocked; approach/crossing still block ---
const wall: WallSegment = { id: 'w', a: { x: -5, y: 0 }, b: { x: 5, y: 0 }, thickness: 0.2 }
const storey = (o: Partial<WalkCollisionStorey> = {}): WalkCollisionStorey => ({
    storeyId: 's', elevation: 0, wallBoundaries: [wall], doorPortals: [], windowBoundaries: [],
    nonTraversableOpenings: [], hasFloor: true, ...o,
})
const step = (from: { x: number; y: number }, to: { x: number; y: number }, radius = 0.35) =>
    resolveWalkCollision({ current: from, candidate: to, storey: storey(), collisionRadius: radius })

describe('walk collision forward-defect fix (approach vs away)', () => {
    it('THE FIX: a step near a wall but moving AWAY from it is ALLOWED (was falsely blocked)', () => {
        // Spawn near the wall (y=0.3), step forward AWAY to y=1.0. Distance grows
        // 0.3 -> 1.0. Previously blocked by proximity; now allowed.
        expect(step({ x: 0, y: 0.3 }, { x: 0, y: 1.0 })).toBe('ALLOW')
    })
    it('a step APPROACHING the wall within the band still blocks', () => {
        // y=1 -> y=0.1 (toward the wall, within radius). Must still block.
        expect(step({ x: 0, y: 1 }, { x: 0, y: 0.1 })).toBe('BLOCK_WALL')
    })
    it('a genuine crossing of the wall still blocks (both directions)', () => {
        expect(step({ x: 0, y: -1 }, { x: 0, y: 1 })).toBe('BLOCK_WALL') // forward crossing
        expect(step({ x: 0, y: 1 }, { x: 0, y: -1 })).toBe('BLOCK_WALL') // backward crossing
    })
    it('open-area movement far from any wall is ALLOWED', () => {
        expect(step({ x: 0, y: 3 }, { x: 0, y: 4 })).toBe('ALLOW')
    })
    it('a parallel step along a wall the walker is pressed against does not crash and returns a decision', () => {
        const r = step({ x: 0, y: 0.1 }, { x: 1, y: 0.1 })
        expect(['ALLOW', 'BLOCK_WALL', 'BLOCK_WINDOW', 'BLOCK_UNKNOWN_OPENING']).toContain(r)
    })
    it('no floor => BLOCK_NO_FLOOR (floor authority preserved)', () => {
        expect(resolveWalkCollision({ current: { x: 0, y: 3 }, candidate: { x: 0, y: 4 }, storey: storey({ hasFloor: false }), collisionRadius: 0.35 })).toBe('BLOCK_NO_FLOOR')
    })
})

// --- door passage preserved (locality) ---
describe('door passage preserved after the fix', () => {
    it('crossing at a traversable door portal => ALLOW_DOOR; away from the door on the same wall => BLOCK_WALL', () => {
        const withDoor = storey({ doorPortals: [{ id: 'd', wallId: 'w', center: { x: 2, y: 0 }, halfWidth: 0.6, traversable: true }] })
        expect(resolveWalkCollision({ current: { x: 2, y: -1 }, candidate: { x: 2, y: 1 }, storey: withDoor, collisionRadius: 0.35 })).toBe('ALLOW_DOOR')
        expect(resolveWalkCollision({ current: { x: -3, y: -1 }, candidate: { x: -3, y: 1 }, storey: withDoor, collisionRadius: 0.35 })).toBe('BLOCK_WALL')
    })
})

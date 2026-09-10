/**
 * Offline tests for the pure walk-collision model, segment-crossing resolver,
 * FOV policy, turn-around, and storey-cutaway policy. No Bentley runtime.
 */
import { describe, expect, it } from 'vitest'
import {
    ALL_BUILDING_ID,
    clampFovDegrees,
    FOV_PRESETS,
    resolveKeyboardYaw,
    resolveNavigationAcceptance,
    resolveStoreyCutaway,
    resolveWalkCollision,
    resolveWalkthroughFovDegrees,
    slideAlongWall,
    storeysByElevation,
    turnAroundYaw,
    type NavigationItem,
    type Portal,
    type WalkCollisionStorey,
    type WallSegment,
    type StoreyRange,
} from '../components/spatial/walkNav'
import { candidateEye, resolveFirstPersonOrientation } from '../components/spatial/firstPerson'

// A wall from (0,0)->(10,0); a door portal at x=5 (halfWidth 1); window at x=8.
const wall: WallSegment = { id: 'w1', a: { x: 0, y: 0 }, b: { x: 10, y: 0 }, thickness: 0.2 }
const door: Portal = { id: 'd1', wallId: 'w1', center: { x: 5, y: 0 }, halfWidth: 1, traversable: true }
const win: Portal = { id: 'win1', wallId: 'w1', center: { x: 8, y: 0 }, halfWidth: 0.6, traversable: false }
const unk: Portal = { id: 'o1', wallId: 'w1', center: { x: 2, y: 0 }, halfWidth: 0.5, traversable: false }

const storey = (over?: Partial<WalkCollisionStorey>): WalkCollisionStorey => ({
    storeyId: 's1', elevation: 0, wallBoundaries: [wall], doorPortals: [door],
    windowBoundaries: [win], nonTraversableOpenings: [unk], hasFloor: true, ...over,
})

const step = (from: { x: number; y: number }, to: { x: number; y: number }, radius = 0.3) =>
    resolveWalkCollision({ current: from, candidate: to, storey: storey(), collisionRadius: radius })

describe('walk collision resolver', () => {
    it('SOLID_WALL: crossing the wall away from any opening => BLOCK_WALL', () => {
        expect(step({ x: 0.5, y: -1 }, { x: 0.5, y: 1 })).toBe('BLOCK_WALL')
    })
    it('DOOR_PORTAL: crossing at the door region => ALLOW_DOOR', () => {
        expect(step({ x: 5, y: -1 }, { x: 5, y: 1 })).toBe('ALLOW_DOOR')
    })
    it('DOOR_PORTAL_LOCALITY: same wall away from the door => BLOCK_WALL (mandatory)', () => {
        // x=1 is far from the door at x=5 -> must block even though a door exists on this wall
        expect(step({ x: 1, y: -1 }, { x: 1, y: 1 })).toBe('BLOCK_WALL')
    })
    it('WINDOW: crossing at the window => BLOCK_WINDOW', () => {
        expect(step({ x: 8, y: -1 }, { x: 8, y: 1 })).toBe('BLOCK_WINDOW')
    })
    it('UNKNOWN_OPENING: crossing at a non-established opening => BLOCK_UNKNOWN_OPENING', () => {
        expect(step({ x: 2, y: -1 }, { x: 2, y: 1 })).toBe('BLOCK_UNKNOWN_OPENING')
    })
    it('SAME_AREA: movement that never crosses the wall => ALLOW', () => {
        expect(step({ x: 3, y: 2 }, { x: 4, y: 3 })).toBe('ALLOW')
    })
    it('NO_FLOOR: storey without a floor => BLOCK_NO_FLOOR', () => {
        expect(resolveWalkCollision({ current: { x: 3, y: 2 }, candidate: { x: 4, y: 3 }, storey: storey({ hasFloor: false }), collisionRadius: 0.3 })).toBe('BLOCK_NO_FLOOR')
    })
    it('COLLISION_RADIUS: center does not cross but radius overlaps the wall => blocked', () => {
        // candidate at y=0.1 (above wall) within radius 0.3 of the wall away from door
        expect(step({ x: 1, y: 1 }, { x: 1, y: 0.1 }, 0.3)).toBe('BLOCK_WALL')
    })
    it('WALL_CORNER: radius would clip a corner => not allowed to cut through', () => {
        const cornerWall: WallSegment = { id: 'w2', a: { x: 10, y: 0 }, b: { x: 10, y: 10 }, thickness: 0.2 }
        const s = storey({ wallBoundaries: [wall, cornerWall] })
        const r = resolveWalkCollision({ current: { x: 9.9, y: 0.2 }, candidate: { x: 10.1, y: -0.1 }, storey: s, collisionRadius: 0.3 })
        expect(r === 'BLOCK_WALL' || r === 'BLOCK_UNKNOWN_OPENING' || r === 'BLOCK_WINDOW').toBe(true)
    })
})

describe('wall sliding', () => {
    it('preserves the tangential component along the wall', () => {
        const slid = slideAlongWall({ x: 1, y: 1 }, { x: 2, y: -1 }, wall) // wall is horizontal
        expect(slid.y).toBe(1) // no normal (y) movement
        expect(slid.x).toBe(2) // tangential x preserved
    })
})

describe('continuous heading (offline)', () => {
    const near = (a: number, b: number, e = 1e-6) => Math.abs(a - b) < e
    it('15° yaw yields ~15° forward change (no snapping)', () => {
        const o = resolveFirstPersonOrientation((15 * Math.PI) / 180, 0)
        const ang = (Math.atan2(o.forwardFlat.x, o.forwardFlat.y) * 180) / Math.PI
        expect(near(ang, 15, 1e-6)).toBe(true)
    })
    it('arbitrary yaws produce continuous normalized forward vectors', () => {
        for (const deg of [5, 22, 37, 73, 115, 179]) {
            const o = resolveFirstPersonOrientation((deg * Math.PI) / 180, 0)
            expect(near(Math.hypot(o.forwardFlat.x, o.forwardFlat.y), 1)).toBe(true)
        }
    })
    it('forward after a partial turn follows the new heading', () => {
        const yaw = (15 * Math.PI) / 180
        const c = candidateEye({ x: 0, y: 0, z: 1.6 }, yaw, { forward: 1, strafe: 0 }, 1)
        const ang = (Math.atan2(c.x, c.y) * 180) / Math.PI
        expect(near(ang, 15, 1e-6)).toBe(true)
    })
    it('strafe stays perpendicular to forward at arbitrary yaw', () => {
        const o = resolveFirstPersonOrientation(0.9, 0)
        expect(near(o.forwardFlat.x * o.right.x + o.forwardFlat.y * o.right.y, 0)).toBe(true)
    })
    it('TURN_AROUND rotates yaw by ~180°', () => {
        expect(near(turnAroundYaw(0.4) - 0.4, Math.PI)).toBe(true)
    })
})

describe('FOV policy', () => {
    it('exactly three presets, ordered NORMAL < WIDE < ULTRA_WIDE', () => {
        expect(FOV_PRESETS.length).toBe(3)
        expect(resolveWalkthroughFovDegrees('NORMAL')).toBeLessThan(resolveWalkthroughFovDegrees('WIDE'))
        expect(resolveWalkthroughFovDegrees('WIDE')).toBeLessThan(resolveWalkthroughFovDegrees('ULTRA_WIDE'))
    })
    it('all presets stay inside safe camera bounds (no 0/neg/near-180)', () => {
        for (const p of FOV_PRESETS) {
            const d = resolveWalkthroughFovDegrees(p)
            expect(d).toBeGreaterThan(0)
            expect(d).toBeLessThan(160)
        }
        expect(clampFovDegrees(0)).toBeGreaterThanOrEqual(35)
        expect(clampFovDegrees(-5)).toBeGreaterThanOrEqual(35)
        expect(clampFovDegrees(300)).toBeLessThanOrEqual(120)
        expect(clampFovDegrees(NaN)).toBe(70)
    })
})

describe('storey cutaway policy', () => {
    const storeys: StoreyRange[] = [
        { id: 'f1', label: 'First Floor', zLow: 0, zHigh: 4 },
        { id: 'f2', label: 'Second Floor', zLow: 4, zHigh: 8 },
        { id: 'roof', label: 'Roof - Main', zLow: 8, zHigh: 10 },
    ]
    it('ALL_BUILDING => no clip', () => {
        expect(resolveStoreyCutaway({ selectedStoreyId: ALL_BUILDING_ID, storeys })).toEqual({ allBuilding: true })
    })
    it('First Floor cutaway differs materially from All Building', () => {
        const c = resolveStoreyCutaway({ selectedStoreyId: 'f1', storeys })
        expect(c.allBuilding).toBe(false)
        expect(c.clipHigh).toBeLessThan(8) // upper floors excluded
        expect(c.storeyId).toBe('f1')
    })
    it('Second Floor cutaway differs from All Building AND First Floor', () => {
        const f1 = resolveStoreyCutaway({ selectedStoreyId: 'f1', storeys })
        const f2 = resolveStoreyCutaway({ selectedStoreyId: 'f2', storeys })
        expect(f2.clipLow).not.toBe(f1.clipLow)
        expect(f2.focusZ).not.toBe(f1.focusZ)
    })
    it('keyed by storey identity, not index', () => {
        const c = resolveStoreyCutaway({ selectedStoreyId: 'roof', storeys })
        expect(c.storeyId).toBe('roof')
    })
    it('storeysByElevation sorts by actual zLow, not source order', () => {
        const shuffled: StoreyRange[] = [storeys[2], storeys[0], storeys[1]]
        expect(storeysByElevation(shuffled).map((s) => s.id)).toEqual(['f1', 'f2', 'roof'])
    })
    it('unknown storey id falls back to all building (never opens arbitrary)', () => {
        expect(resolveStoreyCutaway({ selectedStoreyId: 'ghost', storeys })).toEqual({ allBuilding: true })
    })
})

describe('keyboard yaw (MacBook fine steering)', () => {
    const near = (a: number, b: number, e = 1e-9) => Math.abs(a - b) < e
    it('no turn keys => yaw unchanged', () => {
        expect(resolveKeyboardYaw({ yaw: 1.0, turnLeft: false, turnRight: false, deltaSeconds: 0.5 })).toBe(1.0)
    })
    it('left turn increases yaw continuously', () => {
        expect(resolveKeyboardYaw({ yaw: 0, turnLeft: true, turnRight: false, deltaSeconds: 0.1, yawRate: 1.4 })).toBeCloseTo(0.14, 6)
    })
    it('right turn decreases yaw continuously', () => {
        expect(resolveKeyboardYaw({ yaw: 0, turnLeft: false, turnRight: true, deltaSeconds: 0.1, yawRate: 1.4 })).toBeCloseTo(-0.14, 6)
    })
    it('short tap => small delta; longer hold => larger delta', () => {
        const small = resolveKeyboardYaw({ yaw: 0, turnLeft: true, turnRight: false, deltaSeconds: 0.05 })
        const large = resolveKeyboardYaw({ yaw: 0, turnLeft: true, turnRight: false, deltaSeconds: 0.5 })
        expect(Math.abs(large)).toBeGreaterThan(Math.abs(small))
    })
    it('frame-rate independent: 60x(1/60) ~= 30x(1/30) for the same 1s hold', () => {
        let a = 0; for (let i = 0; i < 60; i++) a = resolveKeyboardYaw({ yaw: a, turnLeft: true, turnRight: false, deltaSeconds: 1 / 60 })
        let b = 0; for (let i = 0; i < 30; i++) b = resolveKeyboardYaw({ yaw: b, turnLeft: true, turnRight: false, deltaSeconds: 1 / 30 })
        expect(near(a, b, 1e-9)).toBe(true)
    })
    it('opposing keys => neutral (no change)', () => {
        expect(resolveKeyboardYaw({ yaw: 0.7, turnLeft: true, turnRight: true, deltaSeconds: 0.3 })).toBe(0.7)
    })
})

describe('navigation acceptance policy', () => {
    const allPass = (): Record<NavigationItem, 'PASS'> => ({
        TRUE_FIRST_PERSON_WALKTHROUGH_CAMERA: 'PASS', MACBOOK_SMALL_ANGLE_STEERING: 'PASS', FORWARD_INTERIOR_NAVIGATION: 'PASS',
        HARD_WALL_COLLISION: 'PASS', REAL_DOOR_PASS: 'PASS', DOOR_LOCALITY_PROOF: 'PASS', WINDOW_BLOCK: 'PASS',
        TURN_AROUND: 'PASS', FOV_CONTROLS: 'PASS', BIRDS_EYE_STOREY_SELECTOR: 'PASS', FIRST_FLOOR_CUTAWAY: 'PASS',
        SECOND_FLOOR_CUTAWAY: 'PASS', RETURN_TO_PLANNING: 'PASS',
    })
    it('all mandatory PASS => ACCEPTED', () => {
        expect(resolveNavigationAcceptance(allPass()).acceptance).toBe('ACCEPTED')
    })
    it('wall failure blocks freeze', () => {
        const r = resolveNavigationAcceptance({ ...allPass(), HARD_WALL_COLLISION: 'FAIL' })
        expect(r.acceptance).toBe('NOT_ACCEPTED')
        expect(r.blockers).toContain('HARD_WALL_COLLISION')
    })
    it('MacBook steering failure blocks freeze', () => {
        const r = resolveNavigationAcceptance({ ...allPass(), MACBOOK_SMALL_ANGLE_STEERING: 'FAIL' })
        expect(r.acceptance).toBe('NOT_ACCEPTED')
        expect(r.blockers).toContain('MACBOOK_SMALL_ANGLE_STEERING')
    })
    it('cutaway failure blocks freeze', () => {
        const r1 = resolveNavigationAcceptance({ ...allPass(), FIRST_FLOOR_CUTAWAY: 'FAIL' })
        const r2 = resolveNavigationAcceptance({ ...allPass(), SECOND_FLOOR_CUTAWAY: 'FAIL' })
        expect(r1.acceptance).toBe('NOT_ACCEPTED')
        expect(r2.acceptance).toBe('NOT_ACCEPTED')
    })
})

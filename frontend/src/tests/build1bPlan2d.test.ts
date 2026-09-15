/**
 * Build 1B §B — TRUE 2D BIM plan PROJECTION pure domain tests.
 *   §PB1 — projection (shared bimSpaceId identity, exact vs approximate footprint,
 *          storey filter, assignment/candidate join, equipment, walker marker).
 *   §PB2 — fit/transform + hit-test helpers (world<->screen round-trip, click
 *          selects the correct room; selection/pan never move the walker).
 *
 * The projection is pure and deterministic — no @itwin, no DOM, no viewport.
 */
import { describe, it, expect } from 'vitest'
import {
    projectBim2dPlan,
    computePlanFitTransform,
    worldToScreen,
    screenToWorld,
    pointInRing,
    hitTestPlanRoom,
    headingFromYaw,
    polygonAbsArea,
    ringCentroid,
    type Bim2dPlanProjectionInput,
    type PlanRoomInput,
} from '../components/spatial/bim2dPlanProjection'

// A room with an EXACT extracted footprint (an L-shape so it is NOT the range rect).
const exactRoom: PlanRoomInput = {
    bimSpaceId: '0xExact',
    originalBimLabel: 'Uptake 01',
    storeyId: 's1',
    worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 4, y: 4, z: 3 } },
    exactOuterLoop: [
        { x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 2 }, { x: 2, y: 2 }, { x: 2, y: 4 }, { x: 0, y: 4 },
    ],
}

// A room with ONLY a BIM range (approximate footprint).
const approxRoom: PlanRoomInput = {
    bimSpaceId: '0xApprox',
    originalBimLabel: 'Injection Room 01',
    storeyId: 's1',
    worldRange: { low: { x: 10, y: 0, z: 0 }, high: { x: 14, y: 3, z: 3 } },
}

// A room on a DIFFERENT storey (filtered out when storeyId='s1').
const otherStoreyRoom: PlanRoomInput = {
    bimSpaceId: '0xUp2',
    originalBimLabel: 'Level 2 Room',
    storeyId: 's2',
    worldRange: { low: { x: 0, y: 0, z: 3 }, high: { x: 4, y: 4, z: 6 } },
}

function baseInput(over: Partial<Bim2dPlanProjectionInput> = {}): Bim2dPlanProjectionInput {
    return {
        rooms: [exactRoom, approxRoom, otherStoreyRoom],
        assignments: [{ bimSpaceId: '0xExact', clinicalFunction: 'UPTAKE_ROOM', mrtDisplayName: 'Uptake 01' }],
        ...over,
    }
}

// ===========================================================================
// §PB1 — PROJECTION
// ===========================================================================

describe('§PB1 2D plan projection', () => {
    it('joins rooms + assignments by the SAME bimSpaceId (no second identity)', () => {
        const view = projectBim2dPlan(baseInput())
        const room = view.rooms.find((r) => r.bimSpaceId === '0xExact')!
        expect(room.clinicalFunction).toBe('UPTAKE_ROOM')
        // The projected room key IS the bimSpaceId (shared identity).
        expect(room.bimSpaceId).toBe('0xExact')
    })

    it('prefers the EXACT extracted footprint over the range rectangle', () => {
        const view = projectBim2dPlan(baseInput())
        const room = view.rooms.find((r) => r.bimSpaceId === '0xExact')!
        expect(room.footprintSource).toBe('EXACT_ROOM_MESH')
        // The exact L-shape has 6 points (the range rect would have 4).
        expect(room.ring).toHaveLength(6)
    })

    it('tags a range-only room as an approximation (never silently exact)', () => {
        const view = projectBim2dPlan(baseInput())
        const room = view.rooms.find((r) => r.bimSpaceId === '0xApprox')!
        expect(room.footprintSource).toBe('BIM_RANGE_APPROXIMATION')
        expect(room.ring).toHaveLength(4)
    })

    it('honest provenance counts exact vs approximate rooms', () => {
        const view = projectBim2dPlan(baseInput({ storeyId: 's1' }))
        expect(view.provenance.exactFootprintRooms).toBe(1)
        expect(view.provenance.approximateFootprintRooms).toBe(1)
        expect(view.provenance.totalRooms).toBe(2) // s2 room filtered out
    })

    it('storey filter hides rooms on other storeys but keeps unknown-storey rooms', () => {
        const view = projectBim2dPlan(baseInput({ storeyId: 's1' }))
        expect(view.rooms.some((r) => r.bimSpaceId === '0xUp2')).toBe(false)
        // A room with no storey id is included (we never hide geometry we can't bin).
        const unknown: PlanRoomInput = { bimSpaceId: '0xU', originalBimLabel: 'Zone', worldRange: { low: { x: -5, y: -5, z: 0 }, high: { x: -1, y: -1, z: 3 } } }
        const v2 = projectBim2dPlan(baseInput({ rooms: [exactRoom, unknown], storeyId: 's1' }))
        expect(v2.rooms.some((r) => r.bimSpaceId === '0xU')).toBe(true)
    })

    it('annotates candidate tiers when supplied (join by bimSpaceId)', () => {
        const view = projectBim2dPlan(baseInput({
            candidates: [{ bimSpaceId: '0xExact', clinicalFunction: 'UPTAKE_ROOM', tier: 'RECOMMENDED', score: 0.9, recommended: true }],
        }))
        expect(view.rooms.find((r) => r.bimSpaceId === '0xExact')!.candidateTier).toBe('RECOMMENDED')
        expect(view.rooms.find((r) => r.bimSpaceId === '0xApprox')!.candidateTier).toBeUndefined()
    })

    it('marks the selected room and no other', () => {
        const view = projectBim2dPlan(baseInput({ selectedBimSpaceId: '0xApprox' }))
        expect(view.rooms.find((r) => r.bimSpaceId === '0xApprox')!.selected).toBe(true)
        expect(view.rooms.find((r) => r.bimSpaceId === '0xExact')!.selected).toBe(false)
    })

    it('projects visible AND hidden equipment; hidden ones are flagged (EVI-MA-02E: hidden stays recoverable)', () => {
        // EVI-MA-02E §9 supersedes the earlier "skips hidden" behavior: hidden
        // equipment still physically exists (reserves space) and must remain a
        // recoverable, selectable subdued marker — so it is projected WITH a
        // `hidden` flag rather than dropped.
        const view = projectBim2dPlan(baseInput({
            equipment: [
                { id: 'e1', parentBimSpaceId: '0xExact', storeyId: 's1', displayLabel: 'PET/CT', lifecycleState: 'LOCKED', footprint: [{ x: 1, y: 1 }, { x: 2, y: 1 }, { x: 2, y: 2 }, { x: 1, y: 2 }] },
                { id: 'e2', parentBimSpaceId: '0xExact', storeyId: 's1', displayLabel: 'Hidden', lifecycleState: 'DRAFT', hidden: true, footprint: [{ x: 3, y: 3 }, { x: 3.5, y: 3 }, { x: 3.5, y: 3.5 }, { x: 3, y: 3.5 }] },
            ],
            storeyId: 's1',
        }))
        expect(view.equipment.map((e) => e.id).sort()).toEqual(['e1', 'e2'])
        expect(view.equipment.find((e) => e.id === 'e1')!.hidden).toBe(false)
        expect(view.equipment.find((e) => e.id === 'e2')!.hidden).toBe(true)
        expect(view.provenance.equipmentCount).toBe(2)
    })

    it('places the walker marker from the single walkthrough read-model (position + heading)', () => {
        const view = projectBim2dPlan(baseInput({
            storeyId: 's1',
            walker: { active: true, eye: { x: 2, y: 2, z: 1.65 }, yaw: 0, activeStoreyId: 's1' },
        }))
        expect(view.walker).toBeDefined()
        expect(view.walker!.position).toEqual({ x: 2, y: 2 })
        // yaw 0 -> heading +x.
        expect(view.walker!.heading.x).toBeCloseTo(1, 6)
        expect(view.walker!.heading.y).toBeCloseTo(0, 6)
        expect(view.provenance.walkerPresent).toBe(true)
    })

    it('hides the walker when inactive or on a different storey', () => {
        const inactive = projectBim2dPlan(baseInput({ walker: { active: false, eye: { x: 2, y: 2, z: 1.65 }, yaw: 0 } }))
        expect(inactive.walker).toBeUndefined()
        const wrongStorey = projectBim2dPlan(baseInput({
            storeyId: 's1',
            walker: { active: true, eye: { x: 2, y: 2, z: 4 }, yaw: 0, activeStoreyId: 's2' },
        }))
        expect(wrongStorey.walker).toBeUndefined()
    })

    it('is deterministic — same input yields the same view-model', () => {
        const a = projectBim2dPlan(baseInput({ storeyId: 's1' }))
        const b = projectBim2dPlan(baseInput({ storeyId: 's1' }))
        expect(JSON.stringify(a)).toEqual(JSON.stringify(b))
    })

    it('computes bounds that enclose all projected geometry', () => {
        const view = projectBim2dPlan(baseInput({ storeyId: 's1' }))
        expect(view.bounds.ok).toBe(true)
        expect(view.bounds.minX).toBeLessThanOrEqual(0)
        expect(view.bounds.maxX).toBeGreaterThanOrEqual(14) // approx room reaches x=14
    })
})

// ===========================================================================
// §PB2 — FIT / TRANSFORM / HIT-TEST (renderer helpers; view-only)
// ===========================================================================

describe('§PB2 plan transform + hit-test', () => {
    it('world->screen->world round-trips', () => {
        const bounds = { minX: 0, minY: 0, maxX: 10, maxY: 8, ok: true }
        const t = computePlanFitTransform(bounds, 200, 160)
        const w = { x: 3.5, y: 6.2 }
        const s = worldToScreen(t, w)
        const back = screenToWorld(t, s)
        expect(back.x).toBeCloseTo(w.x, 6)
        expect(back.y).toBeCloseTo(w.y, 6)
    })

    it('a degenerate bounds yields a safe (non-dividing) transform', () => {
        const t = computePlanFitTransform({ minX: 0, minY: 0, maxX: 0, maxY: 0, ok: false }, 200, 160)
        expect(Number.isFinite(t.scale)).toBe(true)
        expect(t.scale).toBeGreaterThan(0)
    })

    it('pointInRing detects inside vs outside', () => {
        const ring = [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 4 }, { x: 0, y: 4 }]
        expect(pointInRing({ x: 2, y: 2 }, ring)).toBe(true)
        expect(pointInRing({ x: 9, y: 9 }, ring)).toBe(false)
    })

    it('hitTestPlanRoom returns the bimSpaceId of the clicked room (shared identity)', () => {
        const view = projectBim2dPlan(baseInput({ storeyId: 's1' }))
        // A point inside the approx room (x in [10,14], y in [0,3]).
        expect(hitTestPlanRoom(view, { x: 12, y: 1.5 })).toBe('0xApprox')
        // A point inside the exact L-shape.
        expect(hitTestPlanRoom(view, { x: 1, y: 1 })).toBe('0xExact')
        // Empty space -> no hit.
        expect(hitTestPlanRoom(view, { x: 100, y: 100 })).toBeUndefined()
    })

    it('hit-test prefers the SMALLER room on overlap (nested spaces selectable)', () => {
        const big: PlanRoomInput = { bimSpaceId: '0xBig', originalBimLabel: 'Big', worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 10, y: 10, z: 3 } } }
        const small: PlanRoomInput = { bimSpaceId: '0xSmall', originalBimLabel: 'Small', worldRange: { low: { x: 2, y: 2, z: 0 }, high: { x: 4, y: 4, z: 3 } } }
        const view = projectBim2dPlan({ rooms: [big, small], assignments: [] })
        expect(hitTestPlanRoom(view, { x: 3, y: 3 })).toBe('0xSmall')
    })

    it('headingFromYaw is a unit vector', () => {
        for (const yaw of [0, Math.PI / 2, Math.PI, -Math.PI / 3]) {
            const h = headingFromYaw(yaw)
            expect(Math.hypot(h.x, h.y)).toBeCloseTo(1, 6)
        }
    })

    it('polygonAbsArea + ringCentroid are sane for a unit square', () => {
        const ring = [{ x: 0, y: 0 }, { x: 2, y: 0 }, { x: 2, y: 2 }, { x: 0, y: 2 }]
        expect(polygonAbsArea(ring)).toBeCloseTo(4, 6)
        const c = ringCentroid(ring)!
        expect(c.x).toBeCloseTo(1, 6)
        expect(c.y).toBeCloseTo(1, 6)
    })
})

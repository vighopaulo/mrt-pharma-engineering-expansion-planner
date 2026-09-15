/**
 * Build 1B UX CORRECTION — pure domain tests for the label-density policy and the
 * geometry-primary + walker-immutability invariants.
 *
 *   §22 LABEL DENSITY — a ~200-room floor must NOT yield ~200 permanent labels.
 *        Only Clinical Program rooms (permanent, badged) and the SELECTED room are
 *        permanently labelled; a HOVERED room is labelled transiently; ordinary
 *        rooms carry NO permanent label but keep their identity for hover/click.
 *   §23 FLOOR-PLAN GEOMETRY — geometry is primary: every room projects a polygon
 *        (exact or approximate) regardless of labelling; labelling never changes
 *        the ring, footprint source, or which rooms render.
 *   §24 WALKER IMMUTABILITY — the plan's pure layer never mutates the walker; the
 *        label decision does not depend on and cannot change the walker read-model.
 *
 * All pure — no @itwin, no DOM, no viewport.
 */
import { describe, it, expect } from 'vitest'
import {
    projectBim2dPlan,
    resolvePlanRoomLabel,
    clinicalBadge,
    isProgramClinicalFunction,
    countPermanentPlanLabels,
    type Bim2dPlanProjectionInput,
    type PlanRoomInput,
    type PlanRoom,
} from '../components/spatial/bim2dPlanProjection'
import type { ClinicalFunction } from '../components/spatial/clinicalProgram'

// A ~200-room floor: 2 clinical (Uptake 01, Injection Room 01) + 198 ordinary.
function makeManyRooms(nOrdinary: number): PlanRoomInput[] {
    const rooms: PlanRoomInput[] = [
        { bimSpaceId: '0xUptake', originalBimLabel: 'Uptake 01', storeyId: 's1', worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 4, y: 4, z: 3 } } },
        { bimSpaceId: '0xInject', originalBimLabel: 'Injection Room 01', storeyId: 's1', worldRange: { low: { x: 5, y: 0, z: 0 }, high: { x: 9, y: 4, z: 3 } } },
    ]
    for (let i = 0; i < nOrdinary; i++) {
        const x = 10 + (i % 20) * 5
        const y = (Math.floor(i / 20)) * 5
        rooms.push({ bimSpaceId: `0xR${i}`, originalBimLabel: `Space ${i}`, storeyId: 's1', worldRange: { low: { x, y, z: 0 }, high: { x: x + 4, y: y + 4, z: 3 } } })
    }
    return rooms
}

function baseInput(over: Partial<Bim2dPlanProjectionInput> = {}): Bim2dPlanProjectionInput {
    return {
        rooms: makeManyRooms(198),
        assignments: [
            { bimSpaceId: '0xUptake', clinicalFunction: 'UPTAKE_ROOM', mrtDisplayName: 'Uptake 01' },
            { bimSpaceId: '0xInject', clinicalFunction: 'INJECTION_ROOM', mrtDisplayName: 'Injection Room 01' },
        ],
        storeyId: 's1',
        ...over,
    }
}

const clinicalRoom = (fn: ClinicalFunction): Pick<PlanRoom, 'bimSpaceId' | 'label' | 'clinicalFunction' | 'selected' | 'footprintSource'> =>
    ({ bimSpaceId: '0xC', label: 'Room', clinicalFunction: fn, selected: false, footprintSource: 'EXACT_ROOM_MESH' })

// ===========================================================================
// §22 — LABEL DENSITY
// ===========================================================================

describe('§22 label density', () => {
    it('a ~200-room floor produces only a HANDFUL of permanent labels (not ~200)', () => {
        const view = projectBim2dPlan(baseInput())
        expect(view.provenance.totalRooms).toBe(200)
        // Only the 2 clinical rooms are permanently labelled (no selection here).
        expect(countPermanentPlanLabels(view)).toBe(2)
        expect(countPermanentPlanLabels(view)).toBeLessThan(view.rooms.length / 10)
    })

    it('selecting an ordinary room adds exactly ONE more permanent label', () => {
        const view = projectBim2dPlan(baseInput({ selectedBimSpaceId: '0xR5' }))
        expect(countPermanentPlanLabels(view)).toBe(3) // 2 clinical + 1 selected
    })

    it('Clinical Program rooms are ALWAYS labelled, ordinary rooms are NOT', () => {
        const view = projectBim2dPlan(baseInput())
        const uptake = view.rooms.find((r) => r.bimSpaceId === '0xUptake')!
        const ordinary = view.rooms.find((r) => r.bimSpaceId === '0xR0')!
        expect(resolvePlanRoomLabel(uptake).show).toBe(true)
        expect(resolvePlanRoomLabel(uptake).kind).toBe('CLINICAL')
        expect(resolvePlanRoomLabel(ordinary).show).toBe(false)
        expect(resolvePlanRoomLabel(ordinary).kind).toBe('NONE')
    })

    it('a clinical label carries a compact badge + the display name (Uptake / Injection dominant)', () => {
        const view = projectBim2dPlan(baseInput())
        const uptake = view.rooms.find((r) => r.bimSpaceId === '0xUptake')!
        const inject = view.rooms.find((r) => r.bimSpaceId === '0xInject')!
        expect(resolvePlanRoomLabel(uptake).text).toBe('[U] Uptake 01')
        expect(resolvePlanRoomLabel(inject).text).toBe('[I] Injection Room 01')
    })

    it('a HOVERED ordinary room is labelled TRANSIENTLY (identity available), others stay unlabelled', () => {
        const view = projectBim2dPlan(baseInput())
        const r0 = view.rooms.find((r) => r.bimSpaceId === '0xR0')!
        const r1 = view.rooms.find((r) => r.bimSpaceId === '0xR1')!
        const hovered = resolvePlanRoomLabel(r0, '0xR0')
        expect(hovered.show).toBe(true)
        expect(hovered.kind).toBe('HOVERED')
        expect(hovered.text).toContain('Space 0')
        // Not the hovered one -> still no label.
        expect(resolvePlanRoomLabel(r1, '0xR0').show).toBe(false)
        // Hover is transient: countPermanentPlanLabels excludes it entirely.
        expect(countPermanentPlanLabels(view)).toBe(2)
    })

    it('the SELECTED room wins a permanent label even with no clinical function', () => {
        const view = projectBim2dPlan(baseInput({ selectedBimSpaceId: '0xR9' }))
        const sel = view.rooms.find((r) => r.bimSpaceId === '0xR9')!
        const d = resolvePlanRoomLabel(sel)
        expect(d.show).toBe(true)
        expect(d.kind).toBe('SELECTED')
    })

    it('UNASSIGNED_EXISTING is NOT treated as a Clinical Program label', () => {
        expect(isProgramClinicalFunction('UNASSIGNED_EXISTING')).toBe(false)
        expect(isProgramClinicalFunction(undefined)).toBe(false)
        expect(isProgramClinicalFunction('UPTAKE_ROOM')).toBe(true)
        const d = resolvePlanRoomLabel(clinicalRoom('UNASSIGNED_EXISTING'))
        expect(d.show).toBe(false)
        expect(d.kind).toBe('NONE')
    })

    it('clinicalBadge maps the key clinical functions to compact glyphs', () => {
        expect(clinicalBadge('UPTAKE_ROOM')).toBe('[U]')
        expect(clinicalBadge('INJECTION_ROOM')).toBe('[I]')
        expect(clinicalBadge('PET_CT_SCANNER_ROOM')).toBe('[P]')
        expect(clinicalBadge('SPECT_CT_SCANNER_ROOM')).toBe('[S]')
        expect(clinicalBadge('RADIOPHARMACY')).toBe('[R]')
        expect(clinicalBadge('CYCLOTRON')).toBe('[C]')
        expect(clinicalBadge('UNASSIGNED_EXISTING')).toBe('')
        expect(clinicalBadge(undefined)).toBe('')
    })

    it('the label decision is pure + deterministic', () => {
        const r = clinicalRoom('UPTAKE_ROOM')
        expect(resolvePlanRoomLabel(r)).toEqual(resolvePlanRoomLabel(r))
    })
})

// ===========================================================================
// §23 — FLOOR-PLAN GEOMETRY IS PRIMARY (labelling never hides geometry)
// ===========================================================================

describe('§23 floor-plan geometry primary', () => {
    it('every room projects a polygon regardless of whether it is labelled', () => {
        const view = projectBim2dPlan(baseInput())
        // All 200 rooms render a ring even though only 2 are permanently labelled.
        expect(view.rooms).toHaveLength(200)
        expect(view.rooms.every((r) => r.ring.length >= 3)).toBe(true)
        expect(countPermanentPlanLabels(view)).toBe(2)
    })

    it('the label policy never alters ring / footprintSource / labelAnchor', () => {
        const view = projectBim2dPlan(baseInput())
        const ordinary = view.rooms.find((r) => r.bimSpaceId === '0xR0')!
        const before = JSON.stringify({ ring: ordinary.ring, src: ordinary.footprintSource, anchor: ordinary.labelAnchor })
        // Resolve a label (hovered/none) — a PURE read; it returns a decision only.
        resolvePlanRoomLabel(ordinary)
        resolvePlanRoomLabel(ordinary, '0xR0')
        const after = JSON.stringify({ ring: ordinary.ring, src: ordinary.footprintSource, anchor: ordinary.labelAnchor })
        expect(after).toEqual(before)
    })

    it('exact vs approximate provenance is preserved independent of labels', () => {
        const rooms = makeManyRooms(1)
        rooms[0].exactOuterLoop = [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 2 }, { x: 2, y: 2 }, { x: 2, y: 4 }, { x: 0, y: 4 }]
        const view = projectBim2dPlan(baseInput({ rooms }))
        const uptake = view.rooms.find((r) => r.bimSpaceId === '0xUptake')!
        expect(uptake.footprintSource).toBe('EXACT_ROOM_MESH')
        const inject = view.rooms.find((r) => r.bimSpaceId === '0xInject')!
        expect(inject.footprintSource).toBe('BIM_RANGE_APPROXIMATION')
    })
})

// ===========================================================================
// §24 — WALKER IMMUTABILITY (label policy is independent of the walker)
// ===========================================================================

describe('§24 walker immutability', () => {
    it('resolving labels does not read or mutate the walker read-model', () => {
        const walker = { active: true, eye: { x: 2, y: 2, z: 1.65 }, yaw: 0, activeStoreyId: 's1' }
        const before = JSON.stringify(walker)
        const view = projectBim2dPlan(baseInput({ walker }))
        // Resolve every room's label (what the renderer does each frame).
        for (const r of view.rooms) { resolvePlanRoomLabel(r); resolvePlanRoomLabel(r, r.bimSpaceId) }
        countPermanentPlanLabels(view)
        expect(JSON.stringify(walker)).toEqual(before)
        // The walker marker is still placed from the read-model (unchanged).
        expect(view.walker).toBeDefined()
        expect(view.walker!.position).toEqual({ x: 2, y: 2 })
    })

    it('label density does not depend on the walker being present', () => {
        const withWalker = projectBim2dPlan(baseInput({ walker: { active: true, eye: { x: 2, y: 2, z: 1.65 }, yaw: 0, activeStoreyId: 's1' } }))
        const withoutWalker = projectBim2dPlan(baseInput())
        expect(countPermanentPlanLabels(withWalker)).toBe(countPermanentPlanLabels(withoutWalker))
    })
})

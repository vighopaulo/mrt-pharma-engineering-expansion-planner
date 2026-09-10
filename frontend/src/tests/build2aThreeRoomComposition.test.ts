import { describe, it, expect } from 'vitest'
import {
    assignClinicalFunction,
    resetAssignment,
    summarizeProgram,
    type ClinicalProgramAssignment,
} from '../components/spatial/clinicalProgram'
import {
    addOrReplacePlanningVolume,
    updatePlanningVolumeParams,
    setPlanningVolumeVisibility,
    setPlanningVolumeLifecycle,
    deletePlanningVolume,
    findPlanningVolume,
    summarizePlanningVolumes,
} from '../components/spatial/clinicalVolumeCollection'
import {
    makeClinicalVolumeId,
    seedPrismParamsFromParent,
    type ClinicalPlanningVolume,
    type PrismParams,
    type Vec2,
} from '../components/spatial/clinicalPlanningVolume'
import { reconstructUptake01Baseline, UPTAKE_01_BASELINE } from '../components/spatial/uptake01Reconstruction'

const IMODEL = '36381ef4-b5f5-4d6d-b64b-2dbd69ba26a4'

/** Assign a function to a space, returning the updated array. */
function assign(fn: Parameters<typeof assignClinicalFunction>[0]['clinicalFunction'], space: string, label: string, existing: ClinicalProgramAssignment[]): ClinicalProgramAssignment[] {
    const r = assignClinicalFunction({ bimSpace: { bimSpaceId: space, originalBimLabel: label }, clinicalFunction: fn, existingAssignments: existing })
    if (!r.ok) throw new Error(r.reason)
    return r.assignments
}

function vol(parent: string, name: string, fn: string, o: Partial<ClinicalPlanningVolume> = {}): ClinicalPlanningVolume {
    return {
        id: makeClinicalVolumeId(IMODEL, parent, name.toLowerCase().replace(/[^a-z0-9]+/g, '-')),
        iModelId: IMODEL, parentBimSpaceId: parent, clinicalFunction: fn,
        displayName: name, geometryType: 'ORIENTED_RECTANGULAR_PRISM',
        params: { centerX: 0, centerY: 0, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0 },
        lifecycleState: 'DRAFT', geometrySource: 'MRT_PLANNING_SUBVOLUME', hidden: false, ...o,
    }
}

describe('§39 Uptake 01 regression baseline', () => {
    it('reconstruction produces the exact frozen baseline identity + geometry', () => {
        const r = reconstructUptake01Baseline({ iModelId: IMODEL, existingAssignments: [], existingVolumes: [] })
        expect(r.assignment.bimSpaceId).toBe('0x200000001f1')
        expect(r.assignment.clinicalFunction).toBe('UPTAKE_ROOM')
        expect(r.assignment.mrtDisplayName).toBe('Uptake 01')
        expect(r.volume.params).toEqual(UPTAKE_01_BASELINE.params)
        expect(r.volume.lifecycleState).toBe('DRAFT')
    })
})

describe('§38.1-3 add rooms without mutating existing', () => {
    it('Uptake → +Injection → +PET/CT keeps each prior assignment intact', () => {
        let a = assign('UPTAKE_ROOM', '0x200000001f1', '1AC1 CENTRAL WAITING', [])
        const uptake = a.find((x) => x.bimSpaceId === '0x200000001f1')!
        a = assign('INJECTION_ROOM', 'SPACE_INJ', 'SOME ROOM A', a)
        expect(a.find((x) => x.bimSpaceId === '0x200000001f1')).toEqual(uptake) // Uptake unchanged
        const inj = a.find((x) => x.bimSpaceId === 'SPACE_INJ')!
        a = assign('PET_CT_SCANNER_ROOM', 'SPACE_PET', 'SOME ROOM B', a)
        expect(a.find((x) => x.bimSpaceId === '0x200000001f1')).toEqual(uptake)
        expect(a.find((x) => x.bimSpaceId === 'SPACE_INJ')).toEqual(inj)
        expect(a.filter((x) => x.clinicalFunction !== 'UNASSIGNED_EXISTING')).toHaveLength(3)
    })
})

describe('§38.4 deterministic display naming', () => {
    it('first of each function => 01 names', () => {
        let a = assign('UPTAKE_ROOM', 'S1', 'a', [])
        a = assign('INJECTION_ROOM', 'S2', 'b', a)
        a = assign('PET_CT_SCANNER_ROOM', 'S3', 'c', a)
        expect(a.find((x) => x.bimSpaceId === 'S1')!.mrtDisplayName).toBe('Uptake 01')
        expect(a.find((x) => x.bimSpaceId === 'S2')!.mrtDisplayName).toBe('Injection Room 01')
        expect(a.find((x) => x.bimSpaceId === 'S3')!.mrtDisplayName).toBe('PET/CT 01')
    })
})

describe('§38.14 no duplicate assignment for same parent', () => {
    it('re-assigning the same space replaces (one primary)', () => {
        let a = assign('UPTAKE_ROOM', 'S1', 'a', [])
        a = assign('INJECTION_ROOM', 'S1', 'a', a)
        expect(a.filter((x) => x.bimSpaceId === 'S1' && x.clinicalFunction !== 'UNASSIGNED_EXISTING')).toHaveLength(1)
    })
})

describe('§38.5-6 zero-or-one volume + stable identity', () => {
    it('one volume per parent, ids independent of display name', () => {
        let vols: ClinicalPlanningVolume[] = []
        vols = addOrReplacePlanningVolume(vols, vol('0x200000001f1', 'Uptake 01', 'UPTAKE_ROOM'))
        vols = addOrReplacePlanningVolume(vols, vol('SPACE_INJ', 'Injection Room 01', 'INJECTION_ROOM'))
        vols = addOrReplacePlanningVolume(vols, vol('SPACE_PET', 'PET/CT 01', 'PET_CT_SCANNER_ROOM'))
        expect(vols).toHaveLength(3)
        expect(new Set(vols.map((v) => v.id)).size).toBe(3)
        // renaming display name would not change id authority (id is parent-derived)
        expect(vols.find((v) => v.parentBimSpaceId === 'SPACE_INJ')!.id).toContain('SPACE_INJ')
    })
})

describe('§38.8 edit isolation', () => {
    it('editing one volume never mutates the others', () => {
        let vols = [vol('0x200000001f1', 'Uptake 01', 'UPTAKE_ROOM', { params: { centerX: -9.84, centerY: 30.53, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0 } }), vol('SPACE_INJ', 'Injection Room 01', 'INJECTION_ROOM'), vol('SPACE_PET', 'PET/CT 01', 'PET_CT_SCANNER_ROOM')]
        vols = updatePlanningVolumeParams(vols, 'SPACE_INJ', { centerX: 12, centerY: 5, zLow: 0, zHigh: 3, width: 5, depth: 2, yaw: 0.3 })
        expect(findPlanningVolume(vols, '0x200000001f1')!.params.centerX).toBe(-9.84)
        expect(findPlanningVolume(vols, 'SPACE_PET')!.params.centerX).toBe(0)
        expect(findPlanningVolume(vols, 'SPACE_INJ')!.params.centerX).toBe(12)
    })
})

describe('§38.9-10 visibility + lifecycle isolation', () => {
    it('hide + lock affect only the target', () => {
        let vols = [vol('A', 'Uptake 01', 'UPTAKE_ROOM'), vol('B', 'Injection Room 01', 'INJECTION_ROOM'), vol('C', 'PET/CT 01', 'PET_CT_SCANNER_ROOM')]
        vols = setPlanningVolumeVisibility(vols, 'B', false)
        vols = setPlanningVolumeLifecycle(vols, 'C', 'LOCKED')
        expect(findPlanningVolume(vols, 'A')!.hidden).toBeFalsy()
        expect(findPlanningVolume(vols, 'A')!.lifecycleState).toBe('DRAFT')
        expect(findPlanningVolume(vols, 'B')!.hidden).toBe(true)
        expect(findPlanningVolume(vols, 'C')!.lifecycleState).toBe('LOCKED')
    })
})

describe('§38.11-12 DRAFT delete isolation + LOCKED delete rejection', () => {
    it('delete a DRAFT keeps others; LOCKED rejected', () => {
        const vols = [vol('A', 'Uptake 01', 'UPTAKE_ROOM'), vol('B', 'Injection Room 01', 'INJECTION_ROOM', { lifecycleState: 'LOCKED' })]
        const d1 = deletePlanningVolume(vols, 'A')
        expect(d1.deleted).toBe(true)
        expect(d1.volumes).toHaveLength(1)
        const d2 = deletePlanningVolume(vols, 'B')
        expect(d2.deleted).toBe(false)
        expect(d2.reason).toBe('LOCKED_MUST_UNLOCK_FIRST')
    })
})

describe('§38.13 reset DRAFT assignment removes only that assignment', () => {
    it('reset removes the assignment (volume cleanup is overlay-side)', () => {
        let a = assign('UPTAKE_ROOM', 'S1', 'a', [])
        a = assign('INJECTION_ROOM', 'S2', 'b', a)
        a = resetAssignment('S2', a)
        expect(a.filter((x) => x.bimSpaceId === 'S2' && x.clinicalFunction !== 'UNASSIGNED_EXISTING')).toHaveLength(0)
        expect(a.filter((x) => x.bimSpaceId === 'S1' && x.clinicalFunction !== 'UNASSIGNED_EXISTING')).toHaveLength(1)
    })
})

describe('§38.15 three-room summary counts', () => {
    it('counts assignments by function and volumes by lifecycle/visibility', () => {
        let a = assign('UPTAKE_ROOM', 'S1', 'a', [])
        a = assign('INJECTION_ROOM', 'S2', 'b', a)
        a = assign('PET_CT_SCANNER_ROOM', 'S3', 'c', a)
        const prog = summarizeProgram(a)
        expect(prog.assignedCount).toBe(3)
        expect(prog.countByFunction.UPTAKE_ROOM).toBe(1)
        expect(prog.countByFunction.INJECTION_ROOM).toBe(1)
        expect(prog.countByFunction.PET_CT_SCANNER_ROOM).toBe(1)

        const vols = [vol('S1', 'Uptake 01', 'UPTAKE_ROOM'), vol('S2', 'Injection Room 01', 'INJECTION_ROOM', { lifecycleState: 'LOCKED' }), vol('S3', 'PET/CT 01', 'PET_CT_SCANNER_ROOM', { hidden: true })]
        const vs = summarizePlanningVolumes(vols)
        expect(vs.planningVolumes).toBe(3)
        expect(vs.draft).toBe(2)
        expect(vs.locked).toBe(1)
        expect(vs.visible).toBe(2)
        expect(vs.hidden).toBe(1)
    })
})

describe('§9 new-volume seed from parent geometry (not origin / not Uptake coords)', () => {
    it('seeds inside the parent footprint centroid with bounded size', () => {
        // An Injection parent well away from Uptake, e.g. centered at (5, 12).
        const footprint: Vec2[] = [{ x: 2, y: 9 }, { x: 8, y: 9 }, { x: 8, y: 15 }, { x: 2, y: 15 }]
        const seed: PrismParams = seedPrismParamsFromParent({ footprint, zLow: 0, zHigh: 4 })
        expect(seed.centerX).toBeCloseTo(5, 6)
        expect(seed.centerY).toBeCloseTo(12, 6)
        // not Uptake's (-9.84, 30.53), not origin
        expect(seed.centerX).not.toBeCloseTo(-9.84, 1)
        expect(seed.centerX).not.toBe(0)
        // bounded: ~50% of the 6x6 extent
        expect(seed.width).toBeCloseTo(3, 6)
        expect(seed.depth).toBeCloseTo(3, 6)
        expect(seed.zLow).toBe(0)
        expect(seed.zHigh).toBeGreaterThan(seed.zLow)
    })
})

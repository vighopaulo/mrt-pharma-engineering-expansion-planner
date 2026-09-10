import { describe, it, expect } from 'vitest'
import {
    reconstructUptake01Baseline,
    UPTAKE_01_BASELINE,
} from '../components/spatial/uptake01Reconstruction'
import {
    saveClinicalVolumes,
    loadClinicalVolumes,
    type ClinicalPlanningVolume,
} from '../components/spatial/clinicalPlanningVolume'
import {
    saveProgramAssignments,
    loadProgramAssignments,
    type ClinicalProgramAssignment,
} from '../components/spatial/clinicalProgram'

const IMODEL = '36381ef4-b5f5-4d6d-b64b-2dbd69ba26a4'

describe('§31 authorized reconstruction from empty', () => {
    it('creates exactly one assignment + one DRAFT visible volume with the accepted baseline', () => {
        const r = reconstructUptake01Baseline({ iModelId: IMODEL, existingAssignments: [], existingVolumes: [] })
        expect(r.alreadyPresent).toBe(false)
        // one active assignment
        const active = r.assignments.filter((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')
        expect(active).toHaveLength(1)
        expect(r.assignment.bimSpaceId).toBe('0x200000001f1')
        expect(r.assignment.clinicalFunction).toBe('UPTAKE_ROOM')
        expect(r.assignment.mrtDisplayName).toBe('Uptake 01')
        // one volume, accepted geometry, DRAFT, visible
        expect(r.volumes).toHaveLength(1)
        expect(r.volume.parentBimSpaceId).toBe('0x200000001f1')
        expect(r.volume.params).toEqual(UPTAKE_01_BASELINE.params)
        expect(r.volume.params.centerX).toBe(-9.84)
        expect(r.volume.params.centerY).toBe(30.53)
        expect(r.volume.params.width).toBe(4)
        expect(r.volume.params.depth).toBe(3)
        expect(r.volume.params.zLow).toBe(0)
        expect(r.volume.params.zHigh).toBe(3)
        expect(r.volume.params.yaw).toBe(0)
        expect(r.volume.lifecycleState).toBe('DRAFT')
        expect(r.volume.hidden).toBe(false)
    })
})

describe('§32 duplicate guard (idempotent)', () => {
    it('running twice keeps one assignment + one volume with the same stable ids', () => {
        const first = reconstructUptake01Baseline({ iModelId: IMODEL, existingAssignments: [], existingVolumes: [] })
        const second = reconstructUptake01Baseline({ iModelId: IMODEL, existingAssignments: first.assignments, existingVolumes: first.volumes })
        expect(second.alreadyPresent).toBe(true)
        expect(second.volumes).toHaveLength(1)
        expect(second.assignments.filter((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')).toHaveLength(1)
        // stable ids preserved
        expect(second.volume.id).toBe(first.volume.id)
        expect(second.assignment.assignmentId).toBe(first.assignment.assignmentId)
    })
})

describe('§33 reload roundtrip', () => {
    it('persisted reconstructed records restore with identical id + geometry', () => {
        const store: Record<string, string> = {}
        const st = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v } }
        const r = reconstructUptake01Baseline({ iModelId: IMODEL, existingAssignments: [], existingVolumes: [] })
        saveProgramAssignments(IMODEL, r.assignments, st)
        saveClinicalVolumes(IMODEL, r.volumes, st)
        const backA: ClinicalProgramAssignment[] = loadProgramAssignments(IMODEL, st)
        const backV: ClinicalPlanningVolume[] = loadClinicalVolumes(IMODEL, st)
        expect(backA.filter((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')).toHaveLength(1)
        expect(backV).toHaveLength(1)
        expect(backV[0].id).toBe(r.volume.id)
        expect(backV[0].params).toEqual(UPTAKE_01_BASELINE.params)
        expect(backV[0].lifecycleState).toBe('DRAFT')
        // reconstructing again from the reloaded state is a no-op
        const again = reconstructUptake01Baseline({ iModelId: IMODEL, existingAssignments: backA, existingVolumes: backV })
        expect(again.alreadyPresent).toBe(true)
        expect(again.volume.id).toBe(r.volume.id)
    })
})

describe('§34 iModel isolation', () => {
    it('reconstruction stored for clinic is not returned for another iModel', () => {
        const store: Record<string, string> = {}
        const st = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v } }
        const r = reconstructUptake01Baseline({ iModelId: IMODEL, existingAssignments: [], existingVolumes: [] })
        saveProgramAssignments(IMODEL, r.assignments, st)
        saveClinicalVolumes(IMODEL, r.volumes, st)
        expect(loadProgramAssignments('fixture-imodel', st)).toHaveLength(0)
        expect(loadClinicalVolumes('fixture-imodel', st)).toHaveLength(0)
    })
})

describe('does not auto-lock', () => {
    it('reconstructed volume lifecycle is DRAFT (never LOCKED)', () => {
        const r = reconstructUptake01Baseline({ iModelId: IMODEL, existingAssignments: [], existingVolumes: [] })
        expect(r.volume.lifecycleState).toBe('DRAFT')
    })
})

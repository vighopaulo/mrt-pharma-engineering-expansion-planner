import { describe, it, expect } from 'vitest'
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
    loadClinicalVolumes,
    saveClinicalVolumes,
    type ClinicalPlanningVolume,
    type PrismParams,
} from '../components/spatial/clinicalPlanningVolume'

const P = (o: Partial<PrismParams> = {}): PrismParams => ({ centerX: 0, centerY: 0, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0, ...o })

function vol(parent: string, name: string, o: Partial<ClinicalPlanningVolume> = {}): ClinicalPlanningVolume {
    return {
        id: makeClinicalVolumeId('clinic', parent, name.toLowerCase().replace(/\W+/g, '-')),
        iModelId: 'clinic', parentBimSpaceId: parent, clinicalFunction: 'UPTAKE_ROOM',
        displayName: name, geometryType: 'ORIENTED_RECTANGULAR_PRISM', params: P(),
        lifecycleState: 'DRAFT', geometrySource: 'MRT_PLANNING_SUBVOLUME', ...o,
    }
}

describe('§45 add — independent stable ids', () => {
    it('two assignments => two independent volumes with distinct ids', () => {
        let vols: ClinicalPlanningVolume[] = []
        vols = addOrReplacePlanningVolume(vols, vol('SPACE_A', 'Uptake 01'))
        vols = addOrReplacePlanningVolume(vols, vol('SPACE_B', 'Injection Room 01'))
        expect(vols).toHaveLength(2)
        expect(new Set(vols.map((v) => v.id)).size).toBe(2)
    })
    it('0-or-1 per parent: re-add for same parent replaces (not duplicates)', () => {
        let vols: ClinicalPlanningVolume[] = [vol('SPACE_A', 'Uptake 01')]
        vols = addOrReplacePlanningVolume(vols, vol('SPACE_A', 'Uptake 01', { params: P({ centerX: 5 }) }))
        expect(vols.filter((v) => v.parentBimSpaceId === 'SPACE_A')).toHaveLength(1)
        expect(vols[0].params.centerX).toBe(5)
    })
})

describe('§46 isolated update', () => {
    it('updating one volume leaves the others unchanged', () => {
        let vols = [vol('SPACE_A', 'Uptake 01', { params: P({ centerX: -10 }) }), vol('SPACE_B', 'Injection Room 01', { params: P({ centerX: 3 }) })]
        vols = updatePlanningVolumeParams(vols, 'SPACE_B', P({ centerX: 99 }))
        expect(findPlanningVolume(vols, 'SPACE_A')!.params.centerX).toBe(-10)
        expect(findPlanningVolume(vols, 'SPACE_B')!.params.centerX).toBe(99)
    })
    it('LOCKED volume params are not updated', () => {
        let vols = [vol('SPACE_A', 'Uptake 01', { lifecycleState: 'LOCKED', params: P({ centerX: 1 }) })]
        vols = updatePlanningVolumeParams(vols, 'SPACE_A', P({ centerX: 50 }))
        expect(findPlanningVolume(vols, 'SPACE_A')!.params.centerX).toBe(1)
    })
})

describe('§47 visibility isolation', () => {
    it('hiding one volume does not change another', () => {
        let vols = [vol('SPACE_A', 'Uptake 01'), vol('SPACE_B', 'PET/CT 01')]
        vols = setPlanningVolumeVisibility(vols, 'SPACE_B', false)
        expect(findPlanningVolume(vols, 'SPACE_A')!.hidden).toBeFalsy()
        expect(findPlanningVolume(vols, 'SPACE_B')!.hidden).toBe(true)
    })
})

describe('§48 lock isolation', () => {
    it('locking one volume does not lock another', () => {
        let vols = [vol('SPACE_A', 'Uptake 01'), vol('SPACE_B', 'Injection Room 01')]
        vols = setPlanningVolumeLifecycle(vols, 'SPACE_A', 'LOCKED')
        expect(findPlanningVolume(vols, 'SPACE_A')!.lifecycleState).toBe('LOCKED')
        expect(findPlanningVolume(vols, 'SPACE_B')!.lifecycleState).toBe('DRAFT')
    })
})

describe('§49 delete draft', () => {
    it('deletes only the targeted DRAFT volume; others remain', () => {
        const vols = [vol('SPACE_A', 'Uptake 01'), vol('SPACE_B', 'Injection Room 01')]
        const r = deletePlanningVolume(vols, 'SPACE_B')
        expect(r.deleted).toBe(true)
        expect(r.volumes).toHaveLength(1)
        expect(r.volumes[0].parentBimSpaceId).toBe('SPACE_A')
    })
})

describe('§50 locked delete rejected', () => {
    it('a LOCKED volume cannot be deleted (unlock first)', () => {
        const vols = [vol('SPACE_A', 'Uptake 01', { lifecycleState: 'LOCKED' })]
        const r = deletePlanningVolume(vols, 'SPACE_A')
        expect(r.deleted).toBe(false)
        expect(r.reason).toBe('LOCKED_MUST_UNLOCK_FIRST')
        expect(r.volumes).toHaveLength(1)
    })
})

describe('§51 persistence — three volumes roundtrip', () => {
    it('persists and restores identities + geometry + visibility + lifecycle', () => {
        const store: Record<string, string> = {}
        const storage = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v } }
        const vols = [
            vol('SPACE_A', 'Uptake 01', { params: P({ centerX: -10, centerY: 30, yaw: 0.3 }) }),
            vol('SPACE_B', 'Injection Room 01', { hidden: true }),
            vol('SPACE_C', 'PET/CT 01', { lifecycleState: 'LOCKED' }),
        ]
        saveClinicalVolumes('clinic', vols, storage)
        const back = loadClinicalVolumes('clinic', storage)
        expect(back).toHaveLength(3)
        expect(back.find((v) => v.parentBimSpaceId === 'SPACE_A')!.params.centerX).toBe(-10)
        expect(back.find((v) => v.parentBimSpaceId === 'SPACE_B')!.hidden).toBe(true)
        expect(back.find((v) => v.parentBimSpaceId === 'SPACE_C')!.lifecycleState).toBe('LOCKED')
    })
})

describe('§52 iModel isolation', () => {
    it('volumes saved for clinic are not returned for another iModel', () => {
        const store: Record<string, string> = {}
        const storage = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v } }
        saveClinicalVolumes('clinic', [vol('SPACE_A', 'Uptake 01')], storage)
        expect(loadClinicalVolumes('fixture', storage)).toHaveLength(0)
        expect(loadClinicalVolumes('clinic', storage)).toHaveLength(1)
    })
})

describe('summary counts', () => {
    it('counts by lifecycle + visibility', () => {
        const vols = [
            vol('A', 'Uptake 01'),
            vol('B', 'Injection Room 01', { lifecycleState: 'LOCKED' }),
            vol('C', 'PET/CT 01', { hidden: true }),
        ]
        const s = summarizePlanningVolumes(vols)
        expect(s.planningVolumes).toBe(3)
        expect(s.draft).toBe(2)
        expect(s.locked).toBe(1)
        expect(s.visible).toBe(2)
        expect(s.hidden).toBe(1)
    })
})

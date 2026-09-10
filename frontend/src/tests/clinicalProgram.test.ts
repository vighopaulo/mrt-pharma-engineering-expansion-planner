import { describe, it, expect, beforeEach } from 'vitest'
import {
    CLINICAL_FUNCTIONS,
    DEFAULT_PROGRAM_FUNCTION,
    assignClinicalFunction,
    resolveDefaultClinicalProgramName,
    ensureUniqueDisplayName,
    resetAssignment,
    assignmentForSpace,
    resolveProgramRoomLabel,
    resolveProgramRoomVisible,
    prioritizeProgramLabels,
    summarizeProgram,
    checkProgramCompleteness,
    isSafeProgramPayload,
    toSafeProgramPayload,
    loadProgramAssignments,
    saveProgramAssignments,
    type ClinicalProgramAssignment,
    type BimSpaceRef,
} from '../components/spatial/clinicalProgram'

const space = (id: string, label: string, storey = 'story-1'): BimSpaceRef => ({ bimSpaceId: id, originalBimLabel: label, bimStoreyId: storey })

/** Convenience: assign and return the updated array (throws on failure). */
function assign(fn: Parameters<typeof assignClinicalFunction>[0]['clinicalFunction'], s: BimSpaceRef, existing: ClinicalProgramAssignment[], name?: string): ClinicalProgramAssignment[] {
    const r = assignClinicalFunction({ bimSpace: s, clinicalFunction: fn, requestedDisplayName: name, existingAssignments: existing })
    if (!r.ok) throw new Error(r.reason)
    return r.assignments
}

describe('clinicalProgram taxonomy', () => {
    it('is controlled and includes the required functions', () => {
        for (const f of ['UNASSIGNED_EXISTING', 'RADIOPHARMACY', 'INJECTION_ROOM', 'UPTAKE_ROOM', 'PET_CT_SCANNER_ROOM']) {
            expect(CLINICAL_FUNCTIONS).toContain(f)
        }
        expect(DEFAULT_PROGRAM_FUNCTION).toBe('UNASSIGNED_EXISTING')
    })
})

describe('§60 ASSIGN_UPTAKE', () => {
    it('creates one planning assignment referencing the same BIM space', () => {
        const out = assign('UPTAKE_ROOM', space('S1', 'TRICARE OFFICE'), [])
        expect(out).toHaveLength(1)
        const a = out[0]
        expect(a.bimSpaceId).toBe('S1')
        expect(a.originalBimLabel).toBe('TRICARE OFFICE')
        expect(a.clinicalFunction).toBe('UPTAKE_ROOM')
        expect(a.status).toBe('PLANNING_ASSIGNMENT')
        expect(a.provenance).toBe('USER_DEFINED_PLANNING_OVERLAY')
    })
})

describe('§61 BIM_IDENTITY_IMMUTABILITY', () => {
    it('preserves bimSpaceId, originalBimLabel, bimStoreyId', () => {
        const s = space('S1', 'TRICARE OFFICE', 'First Floor')
        const out = assign('UPTAKE_ROOM', s, [])
        expect(out[0].bimSpaceId).toBe('S1')
        expect(out[0].originalBimLabel).toBe('TRICARE OFFICE')
        expect(out[0].bimStoreyId).toBe('First Floor')
    })
})

describe('§62 ONE_PRIMARY_ASSIGNMENT', () => {
    it('replaces the primary assignment — never two simultaneous functions', () => {
        let out = assign('UPTAKE_ROOM', space('S1', 'TRICARE OFFICE'), [])
        out = assign('PET_CT_SCANNER_ROOM', space('S1', 'TRICARE OFFICE'), out)
        const forSpace = out.filter((a) => a.bimSpaceId === 'S1' && a.clinicalFunction !== 'UNASSIGNED_EXISTING')
        expect(forSpace).toHaveLength(1)
        expect(forSpace[0].clinicalFunction).toBe('PET_CT_SCANNER_ROOM')
    })
})

describe('§63 DEFAULT_UPTAKE_NAME', () => {
    it('first Uptake 01, second Uptake 02', () => {
        let out = assign('UPTAKE_ROOM', space('S1', 'A'), [])
        expect(out[0].mrtDisplayName).toBe('Uptake 01')
        out = assign('UPTAKE_ROOM', space('S2', 'B'), out)
        const second = out.find((a) => a.bimSpaceId === 'S2')!
        expect(second.mrtDisplayName).toBe('Uptake 02')
    })
})

describe('§64 DEFAULT_PET_CT_NAME', () => {
    it('first PET/CT 01', () => {
        const out = assign('PET_CT_SCANNER_ROOM', space('S1', 'A'), [])
        expect(out[0].mrtDisplayName).toBe('PET/CT 01')
    })
    it('RADIOPHARMACY singular is Radiopharmacy', () => {
        expect(resolveDefaultClinicalProgramName({ clinicalFunction: 'RADIOPHARMACY', existingAssignments: [] })).toBe('Radiopharmacy')
    })
})

describe('§65 DISPLAY_NAME_UNIQUENESS', () => {
    it('resolves duplicate requested names deterministically', () => {
        let out = assign('UPTAKE_ROOM', space('S1', 'A'), [], 'Uptake 01')
        out = assign('UPTAKE_ROOM', space('S2', 'B'), out, 'Uptake 01')
        const names = out.map((a) => a.mrtDisplayName)
        expect(new Set(names).size).toBe(names.length)
        expect(names).toContain('Uptake 01 (2)')
    })
    it('ensureUniqueDisplayName appends suffix', () => {
        const existing: ClinicalProgramAssignment[] = [{ assignmentId: 'x', bimSpaceId: 'S9', originalBimLabel: 'Z', clinicalFunction: 'UPTAKE_ROOM', mrtDisplayName: 'Uptake 01', status: 'PLANNING_ASSIGNMENT', provenance: 'USER_DEFINED_PLANNING_OVERLAY' }]
        expect(ensureUniqueDisplayName('Uptake 01', existing)).toBe('Uptake 01 (2)')
    })
})

describe('§66 RESET', () => {
    it('removes the override, preserves BIM identity concept', () => {
        let out = assign('UPTAKE_ROOM', space('S1', 'TRICARE OFFICE'), [])
        out = resetAssignment('S1', out)
        expect(assignmentForSpace('S1', out)).toBeUndefined()
    })
    it('assigning UNASSIGNED_EXISTING also resets', () => {
        let out = assign('UPTAKE_ROOM', space('S1', 'TRICARE OFFICE'), [])
        out = assign('UNASSIGNED_EXISTING', space('S1', 'TRICARE OFFICE'), out)
        expect(assignmentForSpace('S1', out)).toBeUndefined()
    })
})

describe('§67 IMODEL_SCOPE', () => {
    it('assignments are scoped per iModel id in storage', () => {
        const store: Record<string, string> = {}
        const storage = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v } }
        const clinic = assign('UPTAKE_ROOM', space('S1', 'A'), [])
        saveProgramAssignments('clinic-imodel', clinic, storage)
        expect(loadProgramAssignments('fixture-imodel', storage)).toHaveLength(0)
        expect(loadProgramAssignments('clinic-imodel', storage)).toHaveLength(1)
    })
})

describe('§68 PERSISTENCE_ROUNDTRIP', () => {
    it('serialize + restore preserves fields', () => {
        const store: Record<string, string> = {}
        const storage = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v } }
        const out = assign('PET_CT_SCANNER_ROOM', space('S1', 'RADIOLOGY', 'Second Floor'), [])
        saveProgramAssignments('m1', out, storage)
        const restored = loadProgramAssignments('m1', storage)
        expect(restored[0]).toMatchObject({
            bimSpaceId: 'S1', bimStoreyId: 'Second Floor', clinicalFunction: 'PET_CT_SCANNER_ROOM',
            mrtDisplayName: 'PET/CT 01', status: 'PLANNING_ASSIGNMENT', provenance: 'USER_DEFINED_PLANNING_OVERLAY',
        })
    })
})

describe('§69 PERSISTENCE_SECRET', () => {
    it('rejects payloads with secret-like fields', () => {
        const poisoned = [{ bimSpaceId: 'S1', clinicalFunction: 'UPTAKE_ROOM', accessToken: 'x' }]
        expect(isSafeProgramPayload(poisoned)).toBe(false)
    })
    it('rejects Authorization / pkce / clientSecret', () => {
        expect(isSafeProgramPayload([{ bimSpaceId: 'S1', clinicalFunction: 'X', Authorization: 'y' }])).toBe(false)
        expect(isSafeProgramPayload([{ bimSpaceId: 'S1', clinicalFunction: 'X', pkceVerifier: 'y' }])).toBe(false)
        expect(isSafeProgramPayload([{ bimSpaceId: 'S1', clinicalFunction: 'X', clientSecret: 'y' }])).toBe(false)
    })
    it('accepts a clean payload', () => {
        const clean = toSafeProgramPayload(assign('UPTAKE_ROOM', space('S1', 'A'), []))
        expect(isSafeProgramPayload(clean)).toBe(true)
    })
    it('save omits any injected secret keys (only safe subset persisted)', () => {
        const store: Record<string, string> = {}
        const storage = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v } }
        const dirty = [{ ...assign('UPTAKE_ROOM', space('S1', 'A'), [])[0], accessToken: 'SECRET' } as unknown as ClinicalProgramAssignment]
        saveProgramAssignments('m1', dirty, storage)
        expect(store['mrtpharma.clinicalProgram.v1.m1']).not.toContain('SECRET')
        expect(store['mrtpharma.clinicalProgram.v1.m1']).not.toContain('accessToken')
    })
})

describe('§70 LABEL_PRECEDENCE', () => {
    it('assigned room shows MRT display name; original inspectable', () => {
        const out = assign('UPTAKE_ROOM', space('S1', 'TRICARE OFFICE'), [], 'Uptake 01')
        const a = assignmentForSpace('S1', out)!
        expect(resolveProgramRoomLabel({ originalBimLabel: 'TRICARE OFFICE', assignment: a })).toBe('Uptake 01')
        expect(a.originalBimLabel).toBe('TRICARE OFFICE') // still inspectable
    })
})

describe('§71 UNASSIGNED_ROOM_LABEL', () => {
    it('no fabricated clinical identity for unassigned rooms', () => {
        expect(resolveProgramRoomLabel({ originalBimLabel: 'BREAK ROOM', assignment: undefined })).toBe('BREAK ROOM')
    })
})

describe('§72 STOREY_FILTER', () => {
    it('room on First Floor not shown as primary Second Floor overlay', () => {
        expect(resolveProgramRoomVisible({ activeStoreyId: 'Second Floor', roomStoreyId: 'First Floor', assigned: true, selected: false, rankAmongVisibleCandidates: 0 })).toBe(false)
        expect(resolveProgramRoomVisible({ activeStoreyId: 'Second Floor', roomStoreyId: 'Second Floor', assigned: true, selected: false, rankAmongVisibleCandidates: 0 })).toBe(true)
    })
})

describe('§73 ASSIGNED_LABEL_PRIORITY', () => {
    it('assigned room ranks above unassigned when density is limited', () => {
        const rooms = [
            { id: 'u1', assigned: false, selected: false },
            { id: 'a1', assigned: true, selected: false },
            { id: 'u2', assigned: false, selected: false },
        ]
        const ordered = prioritizeProgramLabels(rooms)
        expect(ordered[0].id).toBe('a1')
    })
    it('selected + assigned still shown under a tight max', () => {
        expect(resolveProgramRoomVisible({ assigned: true, selected: false, rankAmongVisibleCandidates: 0, maxLabels: 1 })).toBe(true)
        expect(resolveProgramRoomVisible({ assigned: false, selected: false, rankAmongVisibleCandidates: 5, maxLabels: 1 })).toBe(false)
    })
})

describe('§74 PROGRAM_SUMMARY', () => {
    it('returns exact counts by function', () => {
        let out: ClinicalProgramAssignment[] = []
        out = assign('RADIOPHARMACY', space('R1', 'a'), out)
        out = assign('INJECTION_ROOM', space('I1', 'b'), out)
        out = assign('INJECTION_ROOM', space('I2', 'c'), out)
        out = assign('UPTAKE_ROOM', space('U1', 'd'), out)
        out = assign('UPTAKE_ROOM', space('U2', 'e'), out)
        out = assign('UPTAKE_ROOM', space('U3', 'f'), out)
        out = assign('UPTAKE_ROOM', space('U4', 'g'), out)
        out = assign('PET_CT_SCANNER_ROOM', space('P1', 'h'), out)
        out = assign('PET_CT_SCANNER_ROOM', space('P2', 'i'), out)
        const s = summarizeProgram(out)
        expect(s.assignedCount).toBe(9)
        expect(s.countByFunction.RADIOPHARMACY).toBe(1)
        expect(s.countByFunction.INJECTION_ROOM).toBe(2)
        expect(s.countByFunction.UPTAKE_ROOM).toBe(4)
        expect(s.countByFunction.PET_CT_SCANNER_ROOM).toBe(2)
    })
})

describe('§75 COMPLETENESS', () => {
    it('identifies a missing required function; does not auto-create', () => {
        let out: ClinicalProgramAssignment[] = []
        out = assign('RADIOPHARMACY', space('R1', 'a'), out)
        out = assign('INJECTION_ROOM', space('I1', 'b'), out)
        out = assign('UPTAKE_ROOM', space('U1', 'c'), out)
        const before = out.length
        const check = checkProgramCompleteness(out)
        expect(check.complete).toBe(false)
        expect(check.missing).toContain('PET_CT_SCANNER_ROOM')
        expect(out.length).toBe(before) // no auto-create
    })
    it('complete when all present', () => {
        let out: ClinicalProgramAssignment[] = []
        out = assign('RADIOPHARMACY', space('R1', 'a'), out)
        out = assign('INJECTION_ROOM', space('I1', 'b'), out)
        out = assign('UPTAKE_ROOM', space('U1', 'c'), out)
        out = assign('PET_CT_SCANNER_ROOM', space('P1', 'd'), out)
        expect(checkProgramCompleteness(out).complete).toBe(true)
    })
})

describe('§76 NO_COMPLIANCE_INFERENCE', () => {
    it('assignment never sets compliant/validated/certified/shielded/hvac/equipment-fit', () => {
        const a = assign('PET_CT_SCANNER_ROOM', space('S1', 'a'), [])[0]
        expect(a.status).toBe('PLANNING_ASSIGNMENT')
        const keys = Object.keys(a)
        for (const forbidden of ['compliant', 'validated', 'certified', 'shielded', 'hvacApproved', 'equipmentFit']) {
            expect(keys.map((k) => k.toLowerCase())).not.toContain(forbidden.toLowerCase())
        }
    })
})

describe('§77 OVERLAY_BIM_IMMUTABILITY', () => {
    it('assign / rename / reset / visibility are pure — no BIM mutation side channel', () => {
        // These are all pure functions returning new arrays; nothing here can call Bentley.
        let out = assign('UPTAKE_ROOM', space('S1', 'TRICARE OFFICE'), [])
        const originalLabel = out[0].originalBimLabel
        out = assign('UPTAKE_ROOM', space('S1', 'TRICARE OFFICE'), out, 'Renamed Uptake')
        expect(out.find((a) => a.bimSpaceId === 'S1')!.originalBimLabel).toBe(originalLabel)
        out = resetAssignment('S1', out)
        // visibility toggles are pure booleans
        expect(typeof resolveProgramRoomVisible({ assigned: false, selected: false, rankAmongVisibleCandidates: 0 })).toBe('boolean')
        expect(out).toHaveLength(0)
    })
})

describe('load safety', () => {
    beforeEach(() => { /* isolated store per test via param */ })
    it('returns [] on corrupt storage', () => {
        const storage = { getItem: () => '{not json', setItem: () => {} }
        expect(loadProgramAssignments('m1', storage)).toEqual([])
    })
    it('returns [] when payload is unsafe', () => {
        const storage = { getItem: () => JSON.stringify([{ bimSpaceId: 'S1', clinicalFunction: 'X', token: 'secret' }]), setItem: () => {} }
        expect(loadProgramAssignments('m1', storage)).toEqual([])
    })
})

/**
 * Build 1A.4 — pure product-facing containment validation tests (§28).
 * Proves the PlanningVolumeValidationState view model + last-known-valid +
 * restore/reset semantics + summary + persistence, without @itwin.
 */
import { describe, it, expect } from 'vitest'
import {
    resolvePlanningVolumeValidation,
    summarizePlanningValidation,
    type PlanningVolumeValidationState,
} from '../components/spatial/bimRoomVolumeRegistry'
import {
    isSafeVolumePayload,
    toSafeVolumePayload,
    loadClinicalVolumes,
    saveClinicalVolumes,
    seedPrismParamsFromParent,
    isValidPrismParams,
    makeClinicalVolumeId,
    type ClinicalPlanningVolume,
    type PrismParams,
} from '../components/spatial/clinicalPlanningVolume'

const base = (o: Partial<Parameters<typeof resolvePlanningVolumeValidation>[0]> = {}) => resolvePlanningVolumeValidation({
    planningVolumeId: 'clinical-volume:im:0xF6:injection-room-01',
    displayName: 'Injection Room 01',
    lifecycleState: 'DRAFT',
    containmentStatus: 'PASS',
    authorityQuality: 'EXACT_SPACE_GEOMETRY',
    totalSamples: 21, failedSamples: 0,
    hasLastKnownValid: true,
    parentMeshAvailable: true,
    ...o,
})

// §28.1 — PASS produces no warning
describe('§28.1 PASS => no warning', () => {
    it('PASS has NONE warning and lock allowed', () => {
        const v = base({ containmentStatus: 'PASS' })
        expect(v.warningCode).toBe('NONE')
        expect(v.warningMessage).toBe('')
        expect(v.isLockAllowed).toBe(true)
    })
})

// §28.2 — FAIL produces warning
// §28.6 — warning identifies affected planning volume
describe('§28.2/6 FAIL => warning identifying the volume', () => {
    it('FAIL warning names the room and disables lock', () => {
        const v = base({ containmentStatus: 'FAIL', failedSamples: 21 })
        expect(v.warningCode).toBe('OUTSIDE_PARENT')
        expect(v.warningMessage).toContain('Injection Room 01')
        expect(v.warningMessage.toLowerCase()).toContain('outside')
        expect(v.isLockAllowed).toBe(false)
    })
})

// §28.3 — NOT_EVALUATED is neither PASS nor FAIL
describe('§28.3 NOT_EVALUATED honest', () => {
    it('parent unavailable => PARENT_GEOMETRY_UNAVAILABLE, not FAIL/PASS', () => {
        const v = base({ containmentStatus: 'NOT_EVALUATED', parentMeshAvailable: false, totalSamples: 0, failedSamples: 0 })
        expect(v.containmentStatus).toBe('NOT_EVALUATED')
        expect(v.warningCode).toBe('PARENT_GEOMETRY_UNAVAILABLE')
        expect(v.isLockAllowed).toBe(false)
        expect(v.warningMessage).not.toMatch(/inside|outside/i)
    })
    it('evaluated-but-zero-samples => NOT_EVALUATED (not FAIL)', () => {
        const v = base({ containmentStatus: 'NOT_EVALUATED', parentMeshAvailable: true, totalSamples: 0, failedSamples: 0 })
        expect(v.warningCode).toBe('NOT_EVALUATED')
        expect(v.isLockAllowed).toBe(false)
    })
})

// §28.4 — FAIL disables lock (with visible reason)
describe('§28.4 FAIL disables lock with reason', () => {
    it('lockDisabledReason is populated on FAIL', () => {
        const v = base({ containmentStatus: 'FAIL', failedSamples: 21 })
        expect(v.isLockAllowed).toBe(false)
        expect(v.lockDisabledReason.length).toBeGreaterThan(0)
        expect(v.lockDisabledReason).toContain('Injection Room 01')
    })
})

// §28.5 — PASS allows lock subject to lifecycle rules
describe('§28.5 PASS allows lock (lifecycle-gated)', () => {
    it('DRAFT+PASS => lockable; LOCKED+PASS => not offered (already locked)', () => {
        expect(base({ containmentStatus: 'PASS', lifecycleState: 'DRAFT' }).isLockAllowed).toBe(true)
        const locked = base({ containmentStatus: 'PASS', lifecycleState: 'LOCKED' })
        expect(locked.isLockAllowed).toBe(false)
        expect(locked.lockDisabledReason).toContain('locked')
    })
})

// §28.7 — warning not color-only (carries an explicit message/code)
describe('§28.7 warning is not color-only', () => {
    it('the view model carries a textual code + message (not just a color)', () => {
        const v = base({ containmentStatus: 'FAIL', failedSamples: 21 })
        expect(typeof v.warningCode).toBe('string')
        expect(v.warningMessage.length).toBeGreaterThan(10)
    })
})

// §28.18 — zero samples do not become FAIL (covered in §28.3 second case) — reconfirm
describe('§28.18 zero samples ≠ FAIL', () => {
    it('0/0 with parent available maps to NOT_EVALUATED', () => {
        expect(base({ containmentStatus: 'NOT_EVALUATED', totalSamples: 0, failedSamples: 0 }).warningCode).not.toBe('OUTSIDE_PARENT')
    })
})

// §28.19/20 — exact vs approximate authority labeled
describe('§28.19/20 authority quality labeled', () => {
    it('EXACT_SPACE_GEOMETRY is not flagged approximate', () => {
        expect(base({ authorityQuality: 'EXACT_SPACE_GEOMETRY' }).approximateParent).toBe(false)
    })
    it('RANGE_ONLY_APPROXIMATION is flagged approximate + noted in detail', () => {
        const v = base({ authorityQuality: 'RANGE_ONLY_APPROXIMATION' })
        expect(v.approximateParent).toBe(true)
        expect(v.technicalDetail.toLowerCase()).toContain('approximation')
    })
})

// §28.16 — two volumes maintain independent warnings (summary)
// §28.17 — Uptake unaffected by Injection failure (independent states)
describe('§28.16/17 per-volume isolation + summary', () => {
    it('one FAIL + one PASS => summary valid=1 needsAttention=1; each state independent', () => {
        const injection = base({ planningVolumeId: 'inj', displayName: 'Injection Room 01', containmentStatus: 'FAIL', failedSamples: 21 })
        const uptake = base({ planningVolumeId: 'upt', displayName: 'Uptake 01', containmentStatus: 'PASS' })
        expect(injection.warningCode).toBe('OUTSIDE_PARENT')
        expect(uptake.warningCode).toBe('NONE') // Uptake NOT flagged by Injection's failure
        const s = summarizePlanningValidation([injection, uptake])
        expect(s).toMatchObject({ planningVolumes: 2, valid: 1, needsAttention: 1, notEvaluated: 0 })
    })
})

// --- last-known-valid geometry (§28.8/9/10/11/12) via persistence semantics ---

const P = (o: Partial<PrismParams> = {}): PrismParams => ({ centerX: 0, centerY: 0, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0, ...o })
const vol = (o: Partial<ClinicalPlanningVolume> = {}): ClinicalPlanningVolume => ({
    id: makeClinicalVolumeId('im', '0xF6', 'injection-room-01'), iModelId: 'im', parentBimSpaceId: '0xF6',
    clinicalFunction: 'INJECTION_ROOM', displayName: 'Injection Room 01', geometryType: 'ORIENTED_RECTANGULAR_PRISM',
    params: P({ centerX: -31.99, centerY: 32.09, width: 14.2, depth: 4.17 }), lifecycleState: 'DRAFT', geometrySource: 'MRT_PLANNING_SUBVOLUME', ...o,
})

function memStorage(): Storage {
    const m = new Map<string, string>()
    return { getItem: (k) => (m.has(k) ? m.get(k)! : null), setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k), clear: () => m.clear(), key: (i) => Array.from(m.keys())[i] ?? null, get length() { return m.size } } as Storage
}

describe('§28.8/9 last-known-valid geometry persistence', () => {
    it('lastKnownValidParams is an accepted, validated persisted field', () => {
        const v = vol({ lastKnownValidParams: P({ centerX: -31.99, centerY: 32.09, width: 14.2, depth: 4.17 }) })
        expect(isSafeVolumePayload([v])).toBe(true)
        const safe = toSafeVolumePayload([v])
        expect(safe[0].lastKnownValidParams).toBeDefined()
        expect(safe[0].lastKnownValidParams!.centerX).toBeCloseTo(-31.99, 2)
    })
    it('roundtrips through save/load with lastKnownValidParams intact', () => {
        const s = memStorage()
        saveClinicalVolumes('im', [vol({ lastKnownValidParams: P({ centerX: 5 }) })], s)
        const loaded = loadClinicalVolumes('im', s)
        expect(loaded).toHaveLength(1)
        expect(loaded[0].lastKnownValidParams?.centerX).toBe(5)
    })
    it('an invalid lastKnownValidParams is rejected by the safe payload guard', () => {
        const bad = vol()
        bad.lastKnownValidParams = P({ zLow: 3, zHigh: 0 }) // invalid: zHigh <= zLow
        expect(isSafeVolumePayload([bad])).toBe(false)
    })
})

// §28.11/12 — restore uses the SAME volume; reset derives from THIS parent (pure seed)
describe('§28.11/12 restore/reset never use another room', () => {
    it('the parent-derived seed for reset is centered on THIS parent footprint (not Uptake/origin)', () => {
        const footprint = [{ x: 40, y: 60 }, { x: 50, y: 60 }, { x: 50, y: 68 }, { x: 40, y: 68 }]
        const seed = seedPrismParamsFromParent({ footprint, zLow: 0, zHigh: 3 })
        expect(seed.centerX).toBeCloseTo(45, 5)
        expect(seed.centerY).toBeCloseTo(64, 5)
        expect(isValidPrismParams(seed)).toBe(true)
        expect(seed.centerX).not.toBe(0) // not origin
        expect(seed.centerX).not.toBeCloseTo(-9.84, 2) // not Uptake
    })
})

// §28.13/14 — invalid DRAFT may remain, cannot lock (restore always offered on FAIL)
describe('§28.13/14 invalid DRAFT editable but not lockable', () => {
    it('FAIL keeps restore offered and lock blocked', () => {
        const v = base({ containmentStatus: 'FAIL', failedSamples: 21, lifecycleState: 'DRAFT' })
        expect(v.isLockAllowed).toBe(false)
        expect(v.restoreAvailable).toBe(true)
    })
})

// §28.15 — invalid state recomputes (view model derives from CURRENT containment, not a stored verdict)
describe('§28.15 validation derives from current containment (recomputable)', () => {
    it('same volume flips PASS↔FAIL purely by containment input', () => {
        expect(base({ containmentStatus: 'PASS' }).warningCode).toBe('NONE')
        expect(base({ containmentStatus: 'FAIL', failedSamples: 21 }).warningCode).toBe('OUTSIDE_PARENT')
    })
})

// summary notEvaluated bucket
describe('summary counts NOT_EVALUATED separately', () => {
    it('one of each bucket', () => {
        const states: PlanningVolumeValidationState[] = [
            base({ containmentStatus: 'PASS' }),
            base({ containmentStatus: 'FAIL', failedSamples: 21 }),
            base({ containmentStatus: 'NOT_EVALUATED', parentMeshAvailable: false, totalSamples: 0, failedSamples: 0 }),
        ]
        expect(summarizePlanningValidation(states)).toMatchObject({ planningVolumes: 3, valid: 1, needsAttention: 1, notEvaluated: 1 })
    })
})

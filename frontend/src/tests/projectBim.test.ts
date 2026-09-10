/**
 * Offline tests for the pure project-BIM registry, active-BIM resolver, and safe
 * persistence. No Bentley runtime.
 */
import { describe, expect, it } from 'vitest'
import {
    buildProjectBimRegistry,
    isSafePersistedPayload,
    loadPersistedActiveBim,
    productDefaultBim,
    resolveActiveProjectBim,
    resolveBimSelectorRowState,
    savePersistedActiveBim,
    toPersistedActiveBim,
    type PersistedActiveBim,
    type RegisteredBim,
} from '../lib/projectBim'

const ITWIN = 'bdf29ecd-b4a4-404d-861a-ac3061c7b12f'
const FIXTURE_ID = 'fixture-imodel-000000000000'
const CLINIC_ID = '36381ef4-b5f5-4d6d-b64b-2dbd69ba26a4'
const registry: RegisteredBim[] = buildProjectBimRegistry({ iTwinId: ITWIN, fixtureIModelId: FIXTURE_ID })
const legacy = { iModelId: FIXTURE_ID, iTwinId: ITWIN }

describe('registry', () => {
    it('registers >= 2 models incl the clinic (product) and the fixture', () => {
        expect(registry.length).toBeGreaterThanOrEqual(2)
        expect(registry.find((b) => b.iModelId === CLINIC_ID)?.role).toBe('PRODUCT_DEMO_BIM')
        expect(registry.find((b) => b.iModelId === FIXTURE_ID)?.role).toBe('ENGINEERING_REGRESSION_FIXTURE')
    })
    it('product default is the clinic', () => {
        expect(productDefaultBim(registry)?.iModelId).toBe(CLINIC_ID)
    })
})

describe('resolveActiveProjectBim precedence', () => {
    it('URL override wins and does NOT change persisted selection', () => {
        const persisted: PersistedActiveBim = { iModelId: CLINIC_ID, iTwinId: ITWIN, displayName: 'MRTway Medical Clinic Demo', role: 'PRODUCT_DEMO_BIM' }
        const r = resolveActiveProjectBim({ urlOverrideIModelId: FIXTURE_ID, persisted, registry, legacyFallback: legacy })
        expect(r.source).toBe('URL_OVERRIDE')
        expect(r.iModelId).toBe(FIXTURE_ID)
        // persisted object is untouched by resolution (pure fn, no mutation)
        expect(persisted.iModelId).toBe(CLINIC_ID)
    })
    it('persisted clinic is restored when no URL override', () => {
        const persisted: PersistedActiveBim = { iModelId: CLINIC_ID, iTwinId: ITWIN, displayName: 'MRTway Medical Clinic Demo', role: 'PRODUCT_DEMO_BIM' }
        const r = resolveActiveProjectBim({ persisted, registry, legacyFallback: legacy })
        expect(r.source).toBe('PERSISTED_SELECTION')
        expect(r.iModelId).toBe(CLINIC_ID)
    })
    it('product default = clinic when no override and no persisted selection', () => {
        const r = resolveActiveProjectBim({ registry, legacyFallback: legacy })
        expect(r.source).toBe('PRODUCT_DEFAULT')
        expect(r.iModelId).toBe(CLINIC_ID)
        expect(r.role).toBe('PRODUCT_DEMO_BIM')
    })
    it('legacy fallback when no override, no persisted, and no product default', () => {
        const noProduct = registry.filter((b) => b.role !== 'PRODUCT_DEMO_BIM')
        const r = resolveActiveProjectBim({ registry: noProduct, legacyFallback: legacy })
        expect(r.source).toBe('LEGACY_FALLBACK')
        expect(r.iModelId).toBe(FIXTURE_ID)
    })
    it('invalid persisted id (not in registry) is ignored -> product default, never blindly opened', () => {
        const persisted: PersistedActiveBim = { iModelId: 'unregistered-id-123456', iTwinId: ITWIN, displayName: 'Ghost', role: 'PRODUCT_DEMO_BIM' }
        const r = resolveActiveProjectBim({ persisted, registry, legacyFallback: legacy })
        expect(r.iModelId).toBe(CLINIC_ID)
        expect(r.source).toBe('PRODUCT_DEFAULT')
    })
    it('switching selection to the fixture resolves to the fixture (no writes involved)', () => {
        const persisted: PersistedActiveBim = { iModelId: FIXTURE_ID, iTwinId: ITWIN, displayName: 'MRTway Hospital Campus Development', role: 'ENGINEERING_REGRESSION_FIXTURE' }
        const r = resolveActiveProjectBim({ persisted, registry, legacyFallback: legacy })
        expect(r.iModelId).toBe(FIXTURE_ID)
        expect(r.role).toBe('ENGINEERING_REGRESSION_FIXTURE')
    })
})

describe('persistence safety', () => {
    it('persisted payload contains only safe metadata', () => {
        const payload = toPersistedActiveBim({ iModelId: CLINIC_ID, iTwinId: ITWIN, displayName: 'MRTway Medical Clinic Demo', role: 'PRODUCT_DEMO_BIM' })
        expect(Object.keys(payload).sort()).toEqual(['displayName', 'iModelId', 'iTwinId', 'lastOpenedAt', 'role'])
        expect(isSafePersistedPayload(payload)).toBe(true)
    })
    it('rejects payloads carrying token/secret-shaped fields', () => {
        expect(isSafePersistedPayload({ iModelId: CLINIC_ID, iTwinId: ITWIN, displayName: 'x', role: 'PRODUCT_DEMO_BIM', accessToken: 'abc' })).toBe(false)
        expect(isSafePersistedPayload({ iModelId: CLINIC_ID, iTwinId: ITWIN, displayName: 'x', role: 'PRODUCT_DEMO_BIM', refresh_token: 'r' })).toBe(false)
        expect(isSafePersistedPayload({ iModelId: CLINIC_ID, iTwinId: ITWIN, displayName: 'x', role: 'PRODUCT_DEMO_BIM', Authorization: 'Bearer z' })).toBe(false)
    })
    it('save then load round-trips via an injected storage (safe only)', () => {
        const mem = new Map<string, string>()
        const storage = { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v) }
        savePersistedActiveBim({ iModelId: CLINIC_ID, iTwinId: ITWIN, displayName: 'MRTway Medical Clinic Demo', role: 'PRODUCT_DEMO_BIM' }, storage)
        const loaded = loadPersistedActiveBim(storage)
        expect(loaded?.iModelId).toBe(CLINIC_ID)
        expect(loaded && isSafePersistedPayload(loaded)).toBe(true)
    })
    it('load ignores a tampered payload with secret fields', () => {
        const mem = new Map<string, string>([['mrtpharma.activeProjectBim.v1', JSON.stringify({ iModelId: CLINIC_ID, iTwinId: ITWIN, displayName: 'x', role: 'PRODUCT_DEMO_BIM', access_token: 'leak' })]])
        const storage = { getItem: (k: string) => mem.get(k) ?? null }
        expect(loadPersistedActiveBim(storage)).toBeNull()
    })
})

describe('resolveBimSelectorRowState (exactly one ACTIVE; identity-based)', () => {
    it('clinic active => clinic ACTIVE, fixture OPEN', () => {
        expect(resolveBimSelectorRowState({ candidateIModelId: CLINIC_ID, activeIModelId: CLINIC_ID })).toBe('ACTIVE')
        expect(resolveBimSelectorRowState({ candidateIModelId: FIXTURE_ID, activeIModelId: CLINIC_ID })).toBe('OPEN')
    })
    it('fixture active => fixture ACTIVE, clinic OPEN', () => {
        expect(resolveBimSelectorRowState({ candidateIModelId: FIXTURE_ID, activeIModelId: FIXTURE_ID })).toBe('ACTIVE')
        expect(resolveBimSelectorRowState({ candidateIModelId: CLINIC_ID, activeIModelId: FIXTURE_ID })).toBe('OPEN')
    })
    it('exactly one ACTIVE across the registry for a resolved active id', () => {
        const active = CLINIC_ID
        const states = registry.map((b) => resolveBimSelectorRowState({ candidateIModelId: b.iModelId, activeIModelId: active }))
        expect(states.filter((s) => s === 'ACTIVE').length).toBe(1)
    })
    it('pending switch target renders OPENING (active row stays ACTIVE)', () => {
        expect(resolveBimSelectorRowState({ candidateIModelId: FIXTURE_ID, activeIModelId: CLINIC_ID, switchPendingIModelId: FIXTURE_ID })).toBe('OPENING')
        expect(resolveBimSelectorRowState({ candidateIModelId: CLINIC_ID, activeIModelId: CLINIC_ID, switchPendingIModelId: FIXTURE_ID })).toBe('ACTIVE')
    })
    it('never infers ACTIVE from equal role/name — only iModel identity', () => {
        // Two different ids with the SAME (hypothetical) role must not both be ACTIVE.
        expect(resolveBimSelectorRowState({ candidateIModelId: 'id-A-000000', activeIModelId: 'id-B-000000' })).toBe('OPEN')
    })
})

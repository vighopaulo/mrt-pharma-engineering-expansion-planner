/**
 * Build 1B — pure equipment-binding domain tests (§53), no @itwin.
 *
 * Proves: the canonical catalog mirror matches the source-first audit (no
 * invented classes), equipment-instance identity + iModel scope + parent
 * binding, parent-derived floor-aware placement, translate/rotate, envelope
 * containment (NOT center-only) + NOT_EVALUATED honesty, lock prevention,
 * last-known-valid + restore/reset, multi-equipment isolation, safe persistence
 * + reload + iModel isolation, capacity/production/cost crosswalk by canonical
 * id, vestibule/endpoint distinction, generic diagnostic, and no fabricated
 * values.
 */
import { describe, it, expect } from 'vitest'
import {
    CANONICAL_GENERATOR_MODELS,
    CANONICAL_MRT_FACILITY_MODELS,
    CANONICAL_EQUIPMENT_MODELS,
    canonicalEquipmentById,
    canonicalEquipmentByClass,
    canonicalMrtFacility,
    isBindableEquipmentFamily,
    summarizeCanonicalCatalog,
} from '../components/spatial/canonicalEquipmentCatalog'
import {
    createEquipmentInstance,
    seedEquipmentPlacementFromParent,
    evaluateEquipmentContainment,
    translateEquipment,
    rotateEquipment,
    canLockEquipment,
    restoreEquipmentPlacement,
    resetEquipmentToParentDerived,
    isValidEquipmentPlacement,
    placementToPrismParams,
    isSafeEquipmentPayload,
    toSafeEquipmentPayload,
    loadEquipmentInstances,
    saveEquipmentInstances,
    type EquipmentAssetInstance,
    type EquipmentPlacement,
} from '../components/spatial/equipmentInstance'
import {
    resolveEquipmentValidation,
    summarizeEquipmentValidation,
    buildEquipmentCrosswalkReadout,
    buildSelectedEquipmentDiagnostic,
    formatSelectedEquipmentDiagnostic,
} from '../components/spatial/equipmentValidation'
import { buildOrientedPlanningPrism, type Mesh } from '../components/spatial/clinicalPlanningVolume'

// A small closed box mesh (a room) for containment tests. 10x8x3 centered on (45,64).
function roomMesh(): Mesh {
    const g = buildOrientedPlanningPrism({ centerX: 45, centerY: 64, zLow: 0, zHigh: 3, width: 10, depth: 8, yaw: 0 })
    return { vertices: g.vertices, triangles: g.triangles }
}
const ROOM_FOOTPRINT = [{ x: 40, y: 60 }, { x: 50, y: 60 }, { x: 50, y: 68 }, { x: 40, y: 68 }]

function memStorage(): Storage {
    const m = new Map<string, string>()
    return { getItem: (k) => (m.has(k) ? m.get(k)! : null), setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k), clear: () => m.clear(), key: (i) => Array.from(m.keys())[i] ?? null, get length() { return m.size } } as Storage
}

// ---------------------------------------------------------------------------
// §53.1 canonical catalog audit — matches source-first findings, no invention
// ---------------------------------------------------------------------------
describe('§53.1 canonical catalog audit (source-first, no invented classes)', () => {
    it('counts: 17 cyclotron, 4 generator, 6 scanner, 27 total, 2 MRT facility classes', () => {
        const a = summarizeCanonicalCatalog()
        expect(a.cyclotronModelCount).toBe(17)
        expect(a.generatorModelCount).toBe(4)
        expect(a.scannerModelCount).toBe(6)
        expect(a.totalEquipmentModelCount).toBe(27)
        expect(a.mrtFacilityClassCount).toBe(2)
        expect(a.newUnauthorizedEquipmentClasses).toBe(0)
    })
    it('calibrated envelopes are ONLY IBA_CYCLONE_KEY, IBA_CYCLONE_KIUBE, ACSI_TR_24', () => {
        const ids = summarizeCanonicalCatalog().calibratedEnvelopeModelIds.slice().sort()
        expect(ids).toEqual(['ACSI_TR_24', 'IBA_CYCLONE_KEY', 'IBA_CYCLONE_KIUBE'])
    })
    it('every model references a real backend catalog + carries crosswalk pointers (never values)', () => {
        for (const m of CANONICAL_EQUIPMENT_MODELS) {
            expect(m.catalogModelId.length).toBeGreaterThan(0)
            expect(m.capacityCrosswalk.authorityRef).toContain(m.catalogModelId.split('#')[0] === m.catalogModelId ? m.catalogModelId : m.catalogModelId)
            expect(typeof m.costCrosswalk.authorityRef).toBe('string')
            // No numeric cost/capacity is stored on the mirror (by-reference only).
            expect(m).not.toHaveProperty('capex')
            expect(m).not.toHaveProperty('eobMbq')
        }
    })
    it('IBA_CYCLONE_KEY envelope is the calibrated 1.5 x 1.4 x 1.35 (CALIBRATED)', () => {
        const m = canonicalEquipmentById('IBA_CYCLONE_KEY')!
        expect(m.envelope.width).toBeCloseTo(1.5)
        expect(m.envelope.depth).toBeCloseTo(1.4)
        expect(m.envelope.height).toBeCloseTo(1.35)
        expect(m.envelope.provenance).toBe('CALIBRATED')
    })
    it('a GE PETtrace has a GENERIC_ENGINEERING_PLACEHOLDER envelope (honest, no dims in catalog)', () => {
        const m = canonicalEquipmentById('GE_PETTRACE_840')!
        expect(m.envelope.provenance).toBe('GENERIC_ENGINEERING_PLACEHOLDER')
        expect(m.envelope.calibration).toBe('NOT_CALIBRATED')
    })
    it('SUMITOMO_CYPRIS_MP_30 exists and its production crosswalk is NOT_CALIBRATED', () => {
        const m = canonicalEquipmentById('SUMITOMO_CYPRIS_MP_30')!
        expect(m.canonicalClass).toBe('CYCLOTRON')
        expect(m.productionCrosswalk.calibration).toBe('NOT_CALIBRATED')
    })
    it('generator models have no geometry AssetFamily (dims null in catalog)', () => {
        for (const m of CANONICAL_GENERATOR_MODELS) expect(m.assetFamily).toBeUndefined()
    })
    it('scanner PET->PET_CT_SCANNER, SPECT->SPECT_CT_SCANNER family mapping', () => {
        expect(canonicalEquipmentById('GE_DISCOVERY_MI')!.assetFamily).toBe('PET_CT_SCANNER')
        expect(canonicalEquipmentById('SIEMENS_SYMBIA_PRO_SPECTA')!.assetFamily).toBe('SPECT_CT_SCANNER')
    })
    it('bindable families are exactly the catalog-backed + MRT facility classes (SYNTHESIS/HOT_CELL excluded)', () => {
        expect(isBindableEquipmentFamily('CYCLOTRON')).toBe(true)
        expect(isBindableEquipmentFamily('PET_CT_SCANNER')).toBe(true)
        expect(isBindableEquipmentFamily('SPECT_CT_SCANNER')).toBe(true)
        expect(isBindableEquipmentFamily('MRT_RADIOPHARMACY_VESTIBULE')).toBe(true)
        expect(isBindableEquipmentFamily('MRT_ENDPOINT')).toBe(true)
        expect(isBindableEquipmentFamily('SYNTHESIS_MODULE')).toBe(false)
        expect(isBindableEquipmentFamily('HOT_CELL')).toBe(false)
        expect(isBindableEquipmentFamily('DOSE_CALIBRATOR')).toBe(false)
    })
    it('canonicalEquipmentByClass partitions all 27 models', () => {
        expect(canonicalEquipmentByClass('CYCLOTRON')).toHaveLength(17)
        expect(canonicalEquipmentByClass('GENERATOR')).toHaveLength(4)
        expect(canonicalEquipmentByClass('SCANNER')).toHaveLength(6)
    })
})

// ---------------------------------------------------------------------------
// §53.2 vestibule / endpoint distinction (distinct cost authorities, §37)
// ---------------------------------------------------------------------------
describe('§53.2 vestibule vs endpoint distinct cost authorities', () => {
    it('vestibule cost ref = canonical_spatial_authority.MRT_VESTIBULE_CAPEX_USD', () => {
        const v = canonicalMrtFacility('MRT_RADIOPHARMACY_VESTIBULE')!
        expect(v.costCrosswalk.authorityRef).toBe('canonical_spatial_authority.MRT_VESTIBULE_CAPEX_USD')
    })
    it('endpoint cost ref = shared_mrt_multistream_authority.LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT (distinct)', () => {
        const e = canonicalMrtFacility('MRT_ENDPOINT')!
        expect(e.costCrosswalk.authorityRef).toBe('shared_mrt_multistream_authority.LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT')
        expect(e.costCrosswalk.authorityRef).not.toBe(canonicalMrtFacility('MRT_RADIOPHARMACY_VESTIBULE')!.costCrosswalk.authorityRef)
    })
    it('facility models carry no numeric cost (by reference only)', () => {
        for (const m of CANONICAL_MRT_FACILITY_MODELS) expect(m).not.toHaveProperty('capex')
    })
})

// ---------------------------------------------------------------------------
// §53.3 instance identity + iModel scope + parent binding
// ---------------------------------------------------------------------------
function makeInstance(o?: Partial<{ iModelId: string; canonicalEquipmentId: string; parentBimSpaceId: string; seq: number }>): EquipmentAssetInstance {
    const r = createEquipmentInstance({
        iModelId: o?.iModelId ?? 'im-1',
        canonicalEquipmentId: o?.canonicalEquipmentId ?? 'IBA_CYCLONE_KEY',
        parentBimSpaceId: o?.parentBimSpaceId ?? '0xF6',
        footprint: ROOM_FOOTPRINT,
        zLow: 0,
        zHigh: 3,
        seq: o?.seq ?? 1,
    })
    if (!r.ok) throw new Error(r.reason)
    return r.instance
}

describe('§53.3 instance identity + iModel scope + parent binding', () => {
    it('id embeds iModel + parent room + canonical id (distinct identities)', () => {
        const e = makeInstance()
        expect(e.id).toContain('im-1')
        expect(e.id).toContain('0xF6')
        expect(e.id).toContain('IBA_CYCLONE_KEY')
        expect(e.canonicalEquipmentId).toBe('IBA_CYCLONE_KEY')
        expect(e.parentBimSpaceId).toBe('0xF6')
        expect(e.iModelId).toBe('im-1')
    })
    it('rejects an unknown canonical equipment id (no invention)', () => {
        const r = createEquipmentInstance({ iModelId: 'im', canonicalEquipmentId: 'FAKE_MODEL_9000', parentBimSpaceId: '0xF6', footprint: ROOM_FOOTPRINT, zLow: 0, zHigh: 3, seq: 1 })
        expect(r.ok).toBe(false)
        if (!r.ok) expect(r.reason).toBe('UNKNOWN_CANONICAL_EQUIPMENT')
    })
    it('rejects a missing parent room', () => {
        const r = createEquipmentInstance({ iModelId: 'im', canonicalEquipmentId: 'IBA_CYCLONE_KEY', parentBimSpaceId: '', footprint: ROOM_FOOTPRINT, zLow: 0, zHigh: 3, seq: 1 })
        expect(r.ok).toBe(false)
    })
})

// ---------------------------------------------------------------------------
// §53.4 parent-derived, floor-aware placement + translate/rotate
// ---------------------------------------------------------------------------
describe('§53.4 parent-derived floor-aware placement + translate/rotate', () => {
    it('seed is centered on THIS parent footprint centroid and sits on the floor (zBase = room zLow)', () => {
        const m = canonicalEquipmentById('IBA_CYCLONE_KEY')!
        const p = seedEquipmentPlacementFromParent({ canonicalModel: m, footprint: ROOM_FOOTPRINT, zLow: 5, zHigh: 8 })
        expect(p.centerX).toBeCloseTo(45)
        expect(p.centerY).toBeCloseTo(64)
        expect(p.zBase).toBeCloseTo(5) // floor-aware
        expect(p.centerX).not.toBe(0) // never origin
    })
    it('a calibrated envelope is preserved (clamped only if larger than the room)', () => {
        const m = canonicalEquipmentById('IBA_CYCLONE_KEY')! // 1.5 x 1.4 fits in a 10x8 room seed
        const p = seedEquipmentPlacementFromParent({ canonicalModel: m, footprint: ROOM_FOOTPRINT, zLow: 0, zHigh: 3 })
        expect(p.width).toBeCloseTo(1.5)
        expect(p.depth).toBeCloseTo(1.4)
        expect(p.envelopeProvenance).toBe('CALIBRATED')
    })
    it('translate moves XY only; rotate changes yaw only', () => {
        const e = makeInstance()
        const t = translateEquipment(e.placement, 2, -3)
        expect(t.centerX).toBeCloseTo(e.placement.centerX + 2)
        expect(t.centerY).toBeCloseTo(e.placement.centerY - 3)
        expect(t.zBase).toBe(e.placement.zBase)
        const r = rotateEquipment(e.placement, Math.PI / 2)
        expect(r.yaw).toBeCloseTo(e.placement.yaw + Math.PI / 2)
        expect(r.centerX).toBe(e.placement.centerX)
    })
})

// ---------------------------------------------------------------------------
// §53.5 envelope containment (NOT center-only) + NOT_EVALUATED honesty
// ---------------------------------------------------------------------------
describe('§53.5 envelope containment (not center-only)', () => {
    it('an envelope inside the room PASSes', () => {
        const p: EquipmentPlacement = { centerX: 45, centerY: 64, zBase: 0.1, width: 1.5, depth: 1.4, height: 1.35, yaw: 0, envelopeProvenance: 'CALIBRATED' }
        const c = evaluateEquipmentContainment({ placement: p, parentMesh: roomMesh() })
        expect(c.status).toBe('PASS')
        expect(c.contained).toBe(true)
    })
    it('an envelope whose CENTER is inside but a corner protrudes FAILs (proves not center-only)', () => {
        // Room is 10x8 centered at (45,64) => x in [40,50]. A 12-wide box centered at 45
        // has its center inside but its edges at x=39 and x=51 outside the room.
        const p: EquipmentPlacement = { centerX: 45, centerY: 64, zBase: 0.1, width: 12, depth: 1, height: 1, yaw: 0, envelopeProvenance: 'CALIBRATED' }
        const c = evaluateEquipmentContainment({ placement: p, parentMesh: roomMesh() })
        expect(c.status).toBe('FAIL')
        expect(c.failedSamples).toBeGreaterThan(0)
    })
    it('no parent mesh => NOT_EVALUATED (never a false FAIL)', () => {
        const p: EquipmentPlacement = { centerX: 45, centerY: 64, zBase: 0.1, width: 1.5, depth: 1.4, height: 1.35, yaw: 0, envelopeProvenance: 'CALIBRATED' }
        const c = evaluateEquipmentContainment({ placement: p, parentMesh: undefined })
        expect(c.status).toBe('NOT_EVALUATED')
        expect(c.reason).toBe('NO_PARENT_MESH')
    })
    it('placementToPrismParams maps zBase+height to zLow/zHigh and is valid', () => {
        const p: EquipmentPlacement = { centerX: 1, centerY: 2, zBase: 5, width: 2, depth: 2, height: 3, yaw: 0, envelopeProvenance: 'CALIBRATED' }
        const pr = placementToPrismParams(p)
        expect(pr.zLow).toBe(5)
        expect(pr.zHigh).toBe(8)
        expect(isValidEquipmentPlacement(p)).toBe(true)
    })
})

// ---------------------------------------------------------------------------
// §53.6 lock prevention when not contained
// ---------------------------------------------------------------------------
describe('§53.6 lock gate', () => {
    it('lock allowed when contained', () => {
        const e = makeInstance()
        e.placement = { centerX: 45, centerY: 64, zBase: 0.1, width: 1.5, depth: 1.4, height: 1.35, yaw: 0, envelopeProvenance: 'CALIBRATED' }
        expect(canLockEquipment(e, roomMesh()).ok).toBe(true)
    })
    it('lock blocked when outside the room', () => {
        const e = makeInstance()
        e.placement = { centerX: 45, centerY: 64, zBase: 0.1, width: 12, depth: 1, height: 1, yaw: 0, envelopeProvenance: 'CALIBRATED' }
        expect(canLockEquipment(e, roomMesh()).ok).toBe(false)
    })
    it('lock blocked when parent mesh unavailable (NOT_EVALUATED)', () => {
        const e = makeInstance()
        const gate = canLockEquipment(e, undefined)
        expect(gate.ok).toBe(false)
    })
})

// ---------------------------------------------------------------------------
// §53.7 last-known-valid + restore/reset
// ---------------------------------------------------------------------------
describe('§53.7 last-known-valid restore / reset', () => {
    it('restore returns the last-known-valid placement when present', () => {
        const e = makeInstance()
        const valid: EquipmentPlacement = { centerX: 46, centerY: 65, zBase: 0.2, width: 1.5, depth: 1.4, height: 1.35, yaw: 0.1, envelopeProvenance: 'CALIBRATED' }
        e.lastKnownValidPlacement = valid
        const r = restoreEquipmentPlacement({ instance: e, footprint: ROOM_FOOTPRINT, zLow: 0, zHigh: 3 })
        expect(r?.centerX).toBeCloseTo(46)
        expect(r?.yaw).toBeCloseTo(0.1)
    })
    it('restore falls back to a parent-derived seed when no last-known-valid', () => {
        const e = makeInstance()
        const r = restoreEquipmentPlacement({ instance: e, footprint: ROOM_FOOTPRINT, zLow: 0, zHigh: 3 })
        expect(r?.centerX).toBeCloseTo(45) // parent centroid, not origin
    })
    it('reset always derives a fresh parent-derived seed', () => {
        const e = makeInstance()
        const r = resetEquipmentToParentDerived({ instance: e, footprint: ROOM_FOOTPRINT, zLow: 0, zHigh: 3 })
        expect(r?.centerX).toBeCloseTo(45)
        expect(r?.centerY).toBeCloseTo(64)
    })
})

// ---------------------------------------------------------------------------
// §53.8 multi-equipment isolation
// ---------------------------------------------------------------------------
describe('§53.8 multi-equipment isolation', () => {
    it('two instances in the same room have distinct ids and independent placements', () => {
        const a = makeInstance({ canonicalEquipmentId: 'IBA_CYCLONE_KEY', seq: 1 })
        const b = makeInstance({ canonicalEquipmentId: 'GE_DISCOVERY_MI', seq: 2 })
        expect(a.id).not.toBe(b.id)
        const bMoved = { ...b, placement: translateEquipment(b.placement, 3, 0) }
        expect(bMoved.placement.centerX).not.toBe(a.placement.centerX)
    })
})

// ---------------------------------------------------------------------------
// §53.9 safe persistence + reload + iModel isolation
// ---------------------------------------------------------------------------
describe('§53.9 safe persistence + reload + iModel isolation', () => {
    it('roundtrips instances through save/load (scoped by iModel)', () => {
        const s = memStorage()
        const a = makeInstance({ iModelId: 'im-A', seq: 1 })
        saveEquipmentInstances('im-A', [a], s)
        const loaded = loadEquipmentInstances('im-A', s)
        expect(loaded).toHaveLength(1)
        expect(loaded[0].canonicalEquipmentId).toBe('IBA_CYCLONE_KEY')
        // A different iModel key is empty (isolation).
        expect(loadEquipmentInstances('im-B', s)).toHaveLength(0)
    })
    it('rejects a payload with an unknown canonical id (no fabricated resurrection)', () => {
        const a = makeInstance()
        const bad = { ...a, canonicalEquipmentId: 'FAKE_9000' }
        expect(isSafeEquipmentPayload([bad])).toBe(false)
    })
    it('rejects a forbidden secret-like key', () => {
        const a = makeInstance()
        const bad = { ...a, token: 'secret' }
        expect(isSafeEquipmentPayload([bad])).toBe(false)
    })
    it('toSafeEquipmentPayload strips to the serializable subset (no mesh, no extras)', () => {
        const a = makeInstance()
        const safe = toSafeEquipmentPayload([a])
        expect(safe[0]).not.toHaveProperty('mesh')
        expect(Object.keys(safe[0].placement).sort()).toEqual(['centerX', 'centerY', 'depth', 'envelopeProvenance', 'height', 'width', 'yaw', 'zBase'].sort())
    })
})

// ---------------------------------------------------------------------------
// §53.10 validation view model (PASS/FAIL/NOT_EVALUATED, identifies room)
// ---------------------------------------------------------------------------
describe('§53.10 equipment validation view model', () => {
    const inst = makeInstance()
    const base = (o: Partial<Parameters<typeof resolveEquipmentValidation>[0]> = {}) => resolveEquipmentValidation({
        instance: inst, containmentStatus: 'PASS', authorityQuality: 'EXACT_SPACE_GEOMETRY',
        totalSamples: 21, failedSamples: 0, parentMeshAvailable: true, ...o,
    })
    it('PASS => no warning, lockable (DRAFT)', () => {
        const v = base({ containmentStatus: 'PASS' })
        expect(v.warningCode).toBe('NONE')
        expect(v.isLockAllowed).toBe(true)
    })
    it('FAIL => OUTSIDE_PARENT warning identifying the equipment + room, lock blocked', () => {
        const v = base({ containmentStatus: 'FAIL', failedSamples: 21 })
        expect(v.warningCode).toBe('OUTSIDE_PARENT')
        expect(v.warningMessage).toContain(inst.displayLabel)
        expect(v.warningMessage.toLowerCase()).toContain('outside')
        expect(v.isLockAllowed).toBe(false)
        expect(v.lockDisabledReason.length).toBeGreaterThan(0)
    })
    it('NOT_EVALUATED (no mesh) => PARENT_GEOMETRY_UNAVAILABLE, never inside/outside', () => {
        const v = base({ containmentStatus: 'NOT_EVALUATED', parentMeshAvailable: false, totalSamples: 0, failedSamples: 0 })
        expect(v.warningCode).toBe('PARENT_GEOMETRY_UNAVAILABLE')
        expect(v.warningMessage).not.toMatch(/inside|outside/i)
    })
    it('placeholder envelope is disclosed honestly', () => {
        const petInst = makeInstance({ canonicalEquipmentId: 'GE_DISCOVERY_MI', seq: 9 })
        const v = resolveEquipmentValidation({ instance: petInst, containmentStatus: 'PASS', authorityQuality: 'EXACT_SPACE_GEOMETRY', totalSamples: 21, failedSamples: 0, parentMeshAvailable: true })
        expect(v.envelopeIsPlaceholder).toBe(true)
    })
    it('summary counts valid / needsAttention / notEvaluated / locked / placeholder', () => {
        const pass = base({ containmentStatus: 'PASS' })
        const fail = base({ containmentStatus: 'FAIL', failedSamples: 21 })
        const s = summarizeEquipmentValidation({ states: [pass, fail], instances: [inst, inst] })
        expect(s.equipmentCount).toBe(2)
        expect(s.valid).toBe(1)
        expect(s.needsAttention).toBe(1)
    })
})

// ---------------------------------------------------------------------------
// §53.11 crosswalk readout + generic diagnostic (by reference, no fabrication)
// ---------------------------------------------------------------------------
describe('§53.11 crosswalk + generic diagnostic', () => {
    it('crosswalk readout returns capacity/production/cost pointers for a known model', () => {
        const xw = buildEquipmentCrosswalkReadout('IBA_CYCLONE_KEY')!
        const labels = xw.lines.map((l) => l.label)
        expect(labels).toContain('Capacity')
        expect(labels).toContain('Production')
        expect(labels).toContain('Cost')
        // Cost points at the study-level cyclotron installation CapEx anchor.
        expect(xw.lines.find((l) => l.label === 'Cost')!.authorityRef).toContain('cyclotron_installation_capex')
    })
    it('unknown canonical id => no readout (never fabricates)', () => {
        expect(buildEquipmentCrosswalkReadout('FAKE_9000')).toBeUndefined()
    })
    it('generic diagnostic asserts FABRICATED_COSTS=NO / FABRICATED_CAPACITY=NO / BENTLEY_WRITE=NONE', () => {
        const inst = makeInstance()
        const validation = resolveEquipmentValidation({ instance: inst, containmentStatus: 'PASS', authorityQuality: 'EXACT_SPACE_GEOMETRY', totalSamples: 21, failedSamples: 0, parentMeshAvailable: true })
        const d = buildSelectedEquipmentDiagnostic({ instance: inst, validation, totalSamples: 21, failedSamples: 0 })
        const text = formatSelectedEquipmentDiagnostic(d)
        expect(text).toContain('FABRICATED_COSTS = NO')
        expect(text).toContain('FABRICATED_CAPACITY = NO')
        expect(text).toContain('BENTLEY_WRITE = NONE')
        expect(text).toContain('IBA_CYCLONE_KEY')
    })
})

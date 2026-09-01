/**
 * Offline unit tests for the MRT Pharma Asset Library + controlled click-to-place
 * foundation. No Bentley auth, no network, no @itwin runtime — pure domain +
 * store/controller invariants. Uses the REPOSITORY_SOURCE_DERIVED GE Discovery
 * MI record.
 */
import { describe, expect, it } from 'vitest'
import {
    buildAssetLibraryEntry,
    buildPetCtAssetLibrary,
    buildPlacementIntent,
    CATALOG_TEST_ASSET_DEFINITION_ID,
    createSeedRegistry,
    GE_DISCOVERY_MI_RECORD,
    GENERIC_PET_CT_GEOMETRY_ID,
    InstanceIdGenerator,
    placeFromIntent,
    SpatialAssetStore,
    TEST_PROJECT_ID,
    type AuthoritativeEquipmentRecord,
    type ScenarioProvenance,
} from '../domain/assets'

const DEV_SCENARIO: ScenarioProvenance = { scenarioId: 'MRT_DEV_SCENARIO', scenarioState: 'DRAFT' }

function newStore(): SpatialAssetStore {
    return new SpatialAssetStore({ projectId: TEST_PROJECT_ID, scenario: DEV_SCENARIO })
}

const FIXTURE_CYCLOTRON: AuthoritativeEquipmentRecord = {
    catalogSource: 'TEST_FIXTURE_CATALOG',
    catalogRecordId: 'TEST_CYCLOTRON_X',
    manufacturer: 'TEST_MANUFACTURER',
    model: 'TEST_CYC',
    modality: 'CYCLOTRON',
    dimensionsCalibrated: false,
    provenance: 'TEST_FIXTURE',
}

// --- 61. Asset Library data ---
describe('Asset Library (view model over authoritative catalog)', () => {
    it('A/B/C/D — derives GE Discovery MI: label, catalog id, family from catalog', () => {
        const registry = createSeedRegistry()
        const entry = buildAssetLibraryEntry(GE_DISCOVERY_MI_RECORD, registry)
        expect(entry).toBeDefined()
        expect(entry!.displayLabel).toBe('GE HealthCare Discovery MI')
        expect(entry!.catalogRecordId).toBe('GE_DISCOVERY_MI')
        expect(entry!.assetFamily).toBe('PET_CT_SCANNER')
    })

    it('E — geometry status resolves to GENERIC_PET_CT_SCANNER_V1 (generic)', () => {
        const registry = createSeedRegistry()
        const entry = buildAssetLibraryEntry(GE_DISCOVERY_MI_RECORD, registry)!
        expect(entry.geometryAvailability).toBe('GEOMETRY_AVAILABLE')
        expect(entry.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
        expect(entry.geometryIsGeneric).toBe(true)
        expect(entry.geometryStatusNote).toMatch(/generic/i)
    })

    it('F — catalog dimension state remains NOT_CALIBRATED', () => {
        const registry = createSeedRegistry()
        const entry = buildAssetLibraryEntry(GE_DISCOVERY_MI_RECORD, registry)!
        expect(entry.dimensionStatus).toBe('NOT_CALIBRATED')
    })

    it('G — the library does not reclassify generic geometry dims as catalog dims', () => {
        const registry = createSeedRegistry()
        const entry = buildAssetLibraryEntry(GE_DISCOVERY_MI_RECORD, registry)!
        // Entry carries NO calibrated dimensions; only an honest status.
        expect(entry.dimensionStatus).not.toBe('CALIBRATED')
        expect(entry).not.toHaveProperty('width')
    })

    it('is PET/CT-scoped: a cyclotron record is excluded from the library', () => {
        const registry = createSeedRegistry()
        expect(buildAssetLibraryEntry(FIXTURE_CYCLOTRON, registry)).toBeUndefined()
        const lib = buildPetCtAssetLibrary([GE_DISCOVERY_MI_RECORD, FIXTURE_CYCLOTRON], registry)
        expect(lib).toHaveLength(1)
        expect(lib[0].catalogRecordId).toBe('GE_DISCOVERY_MI')
    })
})

// --- 62. Placement intent ---
describe('PlacementIntent', () => {
    it('A — selecting/entering intent does NOT create an AssetInstance', () => {
        const store = newStore()
        const intentRes = buildPlacementIntent({
            record: GE_DISCOVERY_MI_RECORD,
            assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID,
            registry: store.getRegistry(),
        })
        expect(intentRes.ok).toBe(true)
        if (intentRes.ok) store.beginPlacement(intentRes.intent)
        expect(store.isPlacementModeActive()).toBe(true)
        expect(store.count).toBe(0) // no instance yet
    })

    it('B/C — intent contains correct catalog/definition/geometry identity', () => {
        const registry = createSeedRegistry()
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry })
        expect(res.ok).toBe(true)
        if (!res.ok) return
        expect(res.intent.catalogRecordId).toBe('GE_DISCOVERY_MI')
        expect(res.intent.assetDefinitionId).toBe(CATALOG_TEST_ASSET_DEFINITION_ID)
        expect(res.intent.resolvedGeometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
        expect(res.intent.assetFamily).toBe('PET_CT_SCANNER')
        expect(res.intent.displayLabel).toBe('GE HealthCare Discovery MI')
    })

    it('D — cancelling creates no AssetInstance and exits placement mode', () => {
        const store = newStore()
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res.ok) store.beginPlacement(res.intent)
        store.cancelPlacement()
        expect(store.isPlacementModeActive()).toBe(false)
        expect(store.count).toBe(0)
    })

    it('E — successful placement consumes the intent exactly once', () => {
        const store = newStore()
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res.ok) store.beginPlacement(res.intent)
        const first = store.completePlacementAt({ x: 1, y: 2, z: 3 })
        expect(first.ok).toBe(true)
        // A second click with no active intent must NOT place again.
        const second = store.completePlacementAt({ x: 4, y: 5, z: 6 })
        expect(second.ok).toBe(false)
        if (!second.ok) expect(second.reason).toBe('INVALID_PLACEMENT_INTENT')
        expect(store.count).toBe(1)
    })
})

// --- 13/51. One click = one instance; id generator ---
describe('one click one instance + id generator', () => {
    it('one accepted placement click creates exactly one instance', () => {
        const store = newStore()
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res.ok) store.beginPlacement(res.intent)
        const before = store.count
        store.completePlacementAt({ x: 10, y: 10, z: 0 })
        expect(store.count).toBe(before + 1)
    })

    it('id generator issues unique, sequential, non-resetting ids', () => {
        const gen = new InstanceIdGenerator()
        const a = gen.next('GE_DISCOVERY_MI')
        const b = gen.next('GE_DISCOVERY_MI')
        expect(a).toBe('PETCT-GE-DISCOVERY-MI-0001')
        expect(b).toBe('PETCT-GE-DISCOVERY-MI-0002')
        expect(a).not.toBe(b)
        expect(gen.countFor('GE_DISCOVERY_MI')).toBe(2)
    })

    it('user-placed ids are NOT the deterministic fixture ids', () => {
        const store = newStore()
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res.ok) store.beginPlacement(res.intent)
        const placed = store.completePlacementAt({ x: 0, y: 0, z: 0 })
        expect(placed.ok).toBe(true)
        if (placed.ok) {
            expect(placed.instance.assetInstanceId).not.toBe('PETCT-TEST-01')
            expect(placed.instance.assetInstanceId).not.toBe('PETCT-CATALOG-TEST-01')
            expect(placed.instance.assetInstanceId).toMatch(/^PETCT-GE-DISCOVERY-MI-\d{4}$/)
        }
    })
})

// --- 63. Unique instances sharing one geometry ---
describe('multiple user instances share one geometry, distinct spatial ids', () => {
    it('two placements: SAME engineering + geometry identity, DIFFERENT instance ids', () => {
        const store = newStore()
        function placeOnce(x: number) {
            const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
            if (res.ok) store.beginPlacement(res.intent)
            const r = store.completePlacementAt({ x, y: 0, z: 0 })
            if (!r.ok) throw new Error(r.reason)
            return r.instance
        }
        const a = placeOnce(1)
        const b = placeOnce(2)
        expect(a.assetDefinitionId).toBe(CATALOG_TEST_ASSET_DEFINITION_ID)
        expect(b.assetDefinitionId).toBe(CATALOG_TEST_ASSET_DEFINITION_ID)
        expect(a.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
        expect(b.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
        expect(a.assetInstanceId).not.toBe(b.assetInstanceId)
        expect(store.count).toBe(2)
    })
})

// --- 64. World-transform ---
describe('world-transform application', () => {
    it('placed instance position = accepted world point; default rotation preserved', () => {
        const registry = createSeedRegistry()
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry })
        expect(res.ok).toBe(true)
        if (!res.ok) return
        const P = { x: 11.05, y: 10, z: 3.5 }
        const placed = placeFromIntent({
            registry,
            intent: res.intent,
            assetInstanceId: 'PETCT-GE-DISCOVERY-MI-0001',
            projectId: TEST_PROJECT_ID,
            position: P,
            scenario: DEV_SCENARIO,
        })
        expect(placed.ok).toBe(true)
        if (!placed.ok) return
        expect(placed.instance.transform.position).toEqual(P)
        expect(placed.instance.transform.rotation).toEqual({ yaw: 0, pitch: 0, roll: 0 })
        expect(placed.instance.transform.coordinateSpace).toBe('BENTLEY_WORLD_COORDINATES')
        // Geometry representation native coords are unchanged (shared id, no per-instance geometry).
        const geo = registry.getGeometryRepresentation(GENERIC_PET_CT_GEOMETRY_ID)!
        expect(geo.nativeDimensions.width).toBe(2.2)
    })

    it('rejects a non-finite world point', () => {
        const registry = createSeedRegistry()
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry })
        if (!res.ok) return
        const placed = placeFromIntent({
            registry, intent: res.intent, assetInstanceId: 'X', projectId: TEST_PROJECT_ID,
            position: { x: NaN, y: 0, z: 0 }, scenario: DEV_SCENARIO,
        })
        expect(placed.ok).toBe(false)
        if (!placed.ok) expect(placed.reason).toBe('WORLD_POINT_NOT_RESOLVED')
    })
})

// --- 21/65. spatial source + ASSET_PLACED event ---
describe('spatial source + ASSET_PLACED event', () => {
    it('user placement carries USER_PLACED source and catalog origin in createdFrom', () => {
        const store = newStore()
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res.ok) store.beginPlacement(res.intent)
        const r = store.completePlacementAt({ x: 1, y: 1, z: 0 })
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.instance.spatialSource).toBe('USER_PLACED')
        expect(r.instance.createdFrom).toBe('catalog:scanner_equipment_catalog.json#GE_DISCOVERY_MI')
        expect(r.instance.installationState).toBe('PLACED')
        expect(r.instance.roomAssignment.state).toBe('NOT_ASSIGNED')
        expect(r.instance.scenario?.scenarioId).toBe('MRT_DEV_SCENARIO')
    })

    it('placement emits ASSET_PLACED with identity + position + scenario detail', () => {
        const store = newStore()
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res.ok) store.beginPlacement(res.intent)
        const r = store.completePlacementAt({ x: 7, y: 8, z: 9 })
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.event.type).toBe('ASSET_PLACED')
        expect(SpatialAssetStore.isPlacedEvent(r.event)).toBe(true)
        expect(r.event.detail?.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
        expect(r.event.detail?.catalogRecordId).toBe('GE_DISCOVERY_MI')
        expect(r.event.detail?.x).toBe(7)
        expect(r.event.detail?.scenarioId).toBe('MRT_DEV_SCENARIO')
    })
})

// --- 66. Overlay/store observability + survival invariants ---
describe('store observability + overlay-state survival', () => {
    it('is event-driven: subscribers are notified once per state change', () => {
        const store = newStore()
        let calls = 0
        const unsub = store.subscribe(() => { calls += 1 })
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res.ok) store.beginPlacement(res.intent) // notify #1
        store.completePlacementAt({ x: 0, y: 0, z: 0 }) // notify #2
        expect(calls).toBe(2)
        unsub()
        store.insertInstance({ ...store.getProjectInstances()[0], assetInstanceId: 'ANOTHER' })
        expect(calls).toBe(2) // no notification after unsubscribe
    })

    it('overlay identity is keyed by assetInstanceId only (re-insert same id replaces, not duplicates)', () => {
        const store = newStore()
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res.ok) store.beginPlacement(res.intent)
        const r = store.completePlacementAt({ x: 0, y: 0, z: 0 })
        if (!r.ok) return
        const count1 = store.count
        store.insertInstance({ ...r.instance, displayLabel: 'RENAMED' })
        expect(store.count).toBe(count1) // replaced, not duplicated
        expect(store.getInstance(r.instance.assetInstanceId)?.displayLabel).toBe('RENAMED')
    })

    it('placed instances survive a simulated decorator detach/re-attach (store is independent)', () => {
        // The store is decoupled from the Bentley decorator lifecycle; simulate a
        // detach by dropping all listeners and re-subscribing (as a remount does).
        const store = newStore()
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res.ok) store.beginPlacement(res.intent)
        const r = store.completePlacementAt({ x: 5, y: 5, z: 0 })
        if (!r.ok) return
        const id = r.instance.assetInstanceId
        // "detach": listeners dropped
        const unsub = store.subscribe(() => { /* decorator sync */ })
        unsub()
        // "re-attach": new subscription
        store.subscribe(() => { /* decorator sync */ })
        // Instance state is intact.
        expect(store.getInstance(id)).toBeDefined()
        expect(store.getProjectInstances().some((i) => i.assetInstanceId === id)).toBe(true)
    })
})

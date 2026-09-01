/**
 * Offline unit tests for REAL equipment catalog -> generic 3D geometry binding.
 * No Bentley auth, no network, no @itwin runtime. Uses the REPOSITORY_SOURCE_
 * DERIVED GE Discovery MI record plus clearly-marked TEST_FIXTURE records.
 */
import { describe, expect, it } from 'vitest'
import {
    adaptCatalogRecordToAssetDefinition,
    assetFamilyForCatalogModality,
    AssetRegistry,
    buildGeDiscoveryMiCatalogTestAsset,
    CATALOG_TEST_ASSET_DEFINITION_ID,
    CATALOG_TEST_ASSET_INSTANCE_ID,
    createAssetInstanceFromCatalog,
    createSeedRegistry,
    GE_DISCOVERY_MI_RECORD,
    GENERIC_PET_CT_DIMENSIONS,
    GENERIC_PET_CT_GEOMETRY,
    GENERIC_PET_CT_GEOMETRY_ID,
    type AssetDimensions,
    type AuthoritativeEquipmentRecord,
    type GeometryRepresentation,
} from '../domain/assets'

const NEIGH = { center: { x: 10, y: 20, z: 0 }, diagonal: 33 }

const PLACEHOLDER_DIMS: AssetDimensions = { ...GENERIC_PET_CT_DIMENSIONS, provenance: 'GENERIC_ENGINEERING_PLACEHOLDER' }

const FIXTURE_PET_CT_A: AuthoritativeEquipmentRecord = {
    catalogSource: 'TEST_FIXTURE_CATALOG',
    catalogRecordId: 'TEST_PET_CT_A',
    manufacturer: 'TEST_MANUFACTURER',
    model: 'TEST_MODEL_A',
    modality: 'PET',
    configurationNote: 'Integrated diagnostic CT (PET/CT)',
    dimensionsCalibrated: false,
    provenance: 'TEST_FIXTURE',
}
const FIXTURE_PET_CT_B: AuthoritativeEquipmentRecord = {
    ...FIXTURE_PET_CT_A,
    catalogRecordId: 'TEST_PET_CT_B',
    model: 'TEST_MODEL_B',
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

// A/B/C — adaptation + identity/metadata preservation
describe('catalog -> AssetDefinition adaptation', () => {
    it('adapts the REAL GE Discovery MI record with catalog identity + reference', () => {
        const res = adaptCatalogRecordToAssetDefinition(GE_DISCOVERY_MI_RECORD, {
            assetDefinitionId: 'DEF_GE_MI',
            defaultGeometryRepresentationId: GENERIC_PET_CT_GEOMETRY_ID,
            dimensions: PLACEHOLDER_DIMS,
        })
        expect(res.ok).toBe(true)
        if (res.ok) {
            expect(res.definition.assetFamily).toBe('PET_CT_SCANNER')
            expect(res.definition.assetClass).toBe('IMAGING')
            expect(res.definition.displayName).toBe('GE HealthCare Discovery MI') // F: label from catalog
            expect(res.definition.manufacturer).toBe('GE HealthCare')
            expect(res.definition.catalogReference).toBe('scanner_equipment_catalog.json#GE_DISCOVERY_MI')
            expect(res.definition.engineeringMetadataReference.catalogReference).toBe('GE_DISCOVERY_MI')
            expect(res.definition.engineeringMetadataReference.resolved).toBe(true) // repository-source-derived
        }
    })

    it('marks a TEST_FIXTURE record engineering reference as unresolved', () => {
        const res = adaptCatalogRecordToAssetDefinition(FIXTURE_PET_CT_A, {
            assetDefinitionId: 'DEF_A',
            defaultGeometryRepresentationId: GENERIC_PET_CT_GEOMETRY_ID,
            dimensions: PLACEHOLDER_DIMS,
        })
        expect(res.ok).toBe(true)
        if (res.ok) expect(res.definition.engineeringMetadataReference.resolved).toBe(false)
    })
})

// modality mapping
describe('modality -> family mapping', () => {
    it('maps PET to PET_CT_SCANNER', () => {
        expect(assetFamilyForCatalogModality('PET', 'Integrated diagnostic CT (PET/CT)')).toBe('PET_CT_SCANNER')
    })
    it('maps CYCLOTRON to CYCLOTRON', () => {
        expect(assetFamilyForCatalogModality('CYCLOTRON')).toBe('CYCLOTRON')
    })
    it('returns undefined for an unmappable modality', () => {
        expect(assetFamilyForCatalogModality('MICROSCOPE')).toBeUndefined()
    })
})

// D — generic geometry resolves for compatible PET_CT_SCANNER family
describe('geometry resolution', () => {
    it('resolves the generic PET/CT geometry for the PET_CT_SCANNER family', () => {
        const r = createSeedRegistry()
        const res = r.resolveCompatibleGeometry('PET_CT_SCANNER')
        expect(res.status).toBe('RESOLVED')
        if (res.status === 'RESOLVED') expect(res.representation.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
    })

    it('returns GEOMETRY_NOT_AVAILABLE for a family with no representation', () => {
        const r = createSeedRegistry()
        const res = r.resolveCompatibleGeometry('CYCLOTRON')
        expect(res.status).toBe('GEOMETRY_NOT_AVAILABLE')
    })
})

// Section 33 — deterministic priority
describe('geometry resolution priority', () => {
    function registryWithBoth(): AssetRegistry {
        const r = createSeedRegistry()
        const mfrSpecific: GeometryRepresentation = {
            ...GENERIC_PET_CT_GEOMETRY,
            geometryRepresentationId: 'GE_DISCOVERY_MI_SPECIFIC_V1',
            representationType: 'MANUFACTURER_SPECIFIC',
            manufacturerSpecific: true,
            status: 'AVAILABLE',
        }
        r.registerGeometryRepresentation(mfrSpecific)
        return r
    }

    it('prefers explicit assignment when compatible', () => {
        const r = registryWithBoth()
        const res = r.resolveCompatibleGeometry('PET_CT_SCANNER', GENERIC_PET_CT_GEOMETRY_ID)
        expect(res.status).toBe('RESOLVED')
        if (res.status === 'RESOLVED') expect(res.representation.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
    })

    it('prefers manufacturer-specific over generic when no explicit id', () => {
        const r = registryWithBoth()
        const res = r.resolveCompatibleGeometry('PET_CT_SCANNER')
        expect(res.status).toBe('RESOLVED')
        if (res.status === 'RESOLVED') expect(res.representation.geometryRepresentationId).toBe('GE_DISCOVERY_MI_SPECIFIC_V1')
    })

    it('falls back to generic when only generic exists', () => {
        const r = createSeedRegistry()
        const res = r.resolveCompatibleGeometry('PET_CT_SCANNER')
        if (res.status === 'RESOLVED') expect(res.representation.manufacturerSpecific).toBe(false)
    })

    it('ignores an explicit id of the wrong family (no cross-family fallback)', () => {
        const r = registryWithBoth()
        // explicit id belongs to PET_CT family; ask for CYCLOTRON -> not available.
        const res = r.resolveCompatibleGeometry('CYCLOTRON', GENERIC_PET_CT_GEOMETRY_ID)
        expect(res.status).toBe('GEOMETRY_NOT_AVAILABLE')
    })
})

// E/F — catalog-backed instance creation
describe('createAssetInstanceFromCatalog', () => {
    it('creates a catalog-backed instance with independent instance id + catalog label', () => {
        const r = createSeedRegistry()
        const res = createAssetInstanceFromCatalog({
            registry: r,
            record: GE_DISCOVERY_MI_RECORD,
            assetDefinitionId: 'DEF_GE_MI',
            assetInstanceId: 'PETCT-CATALOG-XYZ',
            projectId: 'PROJ',
            position: { x: 1, y: 2, z: 0 },
            dimensions: PLACEHOLDER_DIMS,
        })
        expect(res.ok).toBe(true)
        if (res.ok) {
            expect(res.instance.assetInstanceId).toBe('PETCT-CATALOG-XYZ')
            expect(res.instance.assetDefinitionId).toBe('DEF_GE_MI')
            expect(res.instance.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
            expect(res.instance.displayLabel).toBe('GE HealthCare Discovery MI')
            expect(res.instance.spatialSource).toBe('CATALOG')
            expect(res.instance.createdFrom).toContain('scanner_equipment_catalog.json#GE_DISCOVERY_MI')
        }
    })

    it('rejects claiming CATALOG dimension provenance when catalog footprint is not calibrated', () => {
        const r = createSeedRegistry()
        const res = createAssetInstanceFromCatalog({
            registry: r,
            record: GE_DISCOVERY_MI_RECORD, // dimensionsCalibrated=false
            assetDefinitionId: 'DEF_GE_MI',
            assetInstanceId: 'X',
            projectId: 'PROJ',
            position: { x: 0, y: 0, z: 0 },
            dimensions: { ...PLACEHOLDER_DIMS, provenance: 'CATALOG' },
        })
        expect(res.ok).toBe(false)
        if (!res.ok) expect(res.reason).toBe('DIMENSIONS_NOT_CALIBRATED')
    })
})

// Section 19 — no silent cross-family fallback
describe('family compatibility', () => {
    it('a cyclotron never resolves to the generic PET/CT geometry', () => {
        const r = createSeedRegistry()
        const res = createAssetInstanceFromCatalog({
            registry: r,
            record: FIXTURE_CYCLOTRON,
            assetDefinitionId: 'DEF_CYC',
            assetInstanceId: 'CYC-X',
            projectId: 'PROJ',
            position: { x: 0, y: 0, z: 0 },
            dimensions: PLACEHOLDER_DIMS,
        })
        expect(res.ok).toBe(false)
        if (!res.ok) expect(res.reason).toBe('GEOMETRY_NOT_AVAILABLE')
    })

    it('an unmappable modality returns UNSUPPORTED_ASSET_FAMILY', () => {
        const r = createSeedRegistry()
        const res = createAssetInstanceFromCatalog({
            registry: r,
            record: { ...FIXTURE_PET_CT_A, modality: 'MICROSCOPE' },
            assetDefinitionId: 'DEF_M',
            assetInstanceId: 'M-X',
            projectId: 'PROJ',
            position: { x: 0, y: 0, z: 0 },
            dimensions: PLACEHOLDER_DIMS,
        })
        expect(res.ok).toBe(false)
        if (!res.ok) expect(res.reason).toBe('UNSUPPORTED_ASSET_FAMILY')
    })
})

// Section 34 — one geometry, two real-like catalog identities
describe('GENERIC_GEOMETRY_REUSE_ACROSS_CATALOG_IDENTITIES', () => {
    it('two fixture catalog records resolve to the same geometry with distinct identities/labels', () => {
        const r = createSeedRegistry()
        const a = createAssetInstanceFromCatalog({
            registry: r, record: FIXTURE_PET_CT_A, assetDefinitionId: 'DEF_A', assetInstanceId: 'INST_A',
            projectId: 'PROJ', position: { x: 0, y: 0, z: 0 }, dimensions: PLACEHOLDER_DIMS,
        })
        const b = createAssetInstanceFromCatalog({
            registry: r, record: FIXTURE_PET_CT_B, assetDefinitionId: 'DEF_B', assetInstanceId: 'INST_B',
            projectId: 'PROJ', position: { x: 5, y: 0, z: 0 }, dimensions: PLACEHOLDER_DIMS,
        })
        expect(a.ok && b.ok).toBe(true)
        if (a.ok && b.ok) {
            expect(a.instance.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
            expect(b.instance.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
            expect(a.instance.assetDefinitionId).not.toBe(b.instance.assetDefinitionId)
            expect(a.instance.displayLabel).not.toBe(b.instance.displayLabel)
            expect(a.instance.assetInstanceId).not.toBe(b.instance.assetInstanceId)
        }
        // still exactly one geometry representation registered.
        expect(r.listGeometryRepresentations()).toHaveLength(1)
    })
})

// Section 35 — no engineering data leaks into geometry representation
describe('no engineering data in GeometryRepresentation', () => {
    it('GeometryRepresentation carries no throughput/power/capex fields', () => {
        const keys = Object.keys(GENERIC_PET_CT_GEOMETRY)
        for (const forbidden of ['throughput', 'capacity', 'power', 'cooling', 'capex', 'opex', 'cycleTime']) {
            expect(keys.map((k) => k.toLowerCase())).not.toContain(forbidden.toLowerCase())
        }
    })
})

// Sections 11/12 — generic + catalog coexist, keyed by assetInstanceId
describe('overlay coexistence invariant (assetInstanceId keyed)', () => {
    // Mirror the overlay controller's dedupe rule at the domain level (the
    // controller imports Bentley and cannot run in vitest, but its rule is:
    // dedupe by assetInstanceId ONLY, never by geometry/definition/family).
    function upsertByInstanceId(list: { assetInstanceId: string }[], next: { assetInstanceId: string }): typeof list {
        return [...list.filter((i) => i.assetInstanceId !== next.assetInstanceId), next]
    }

    it('generic and catalog instances (same geometry) coexist as two entries', () => {
        const r = createSeedRegistry()
        const cat = createAssetInstanceFromCatalog({
            registry: r, record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: 'CATALOG_PET_CT_GE_DISCOVERY_MI',
            assetInstanceId: 'PETCT-CATALOG-TEST-01', projectId: 'MRT_DEV_VIEWER_PROJECT',
            position: { x: 5, y: 0, z: 0 }, dimensions: PLACEHOLDER_DIMS,
        })
        expect(cat.ok).toBe(true)
        if (!cat.ok) return
        const generic = { assetInstanceId: 'PETCT-TEST-01', geometryRepresentationId: GENERIC_PET_CT_GEOMETRY_ID }
        let overlay: { assetInstanceId: string }[] = []
        overlay = upsertByInstanceId(overlay, generic)
        overlay = upsertByInstanceId(overlay, { assetInstanceId: cat.instance.assetInstanceId })
        expect(overlay).toHaveLength(2)
        expect(overlay.map((o) => o.assetInstanceId).sort()).toEqual(['PETCT-CATALOG-TEST-01', 'PETCT-TEST-01'])
        // Both reference the SAME geometry id — proves dedupe is NOT by geometry.
        expect(cat.instance.geometryRepresentationId).toBe(generic.geometryRepresentationId)
    })

    it('re-showing the same instance id replaces (not duplicates) it', () => {
        function up(list: { assetInstanceId: string; v: number }[], n: { assetInstanceId: string; v: number }) {
            return [...list.filter((i) => i.assetInstanceId !== n.assetInstanceId), n]
        }
        let overlay: { assetInstanceId: string; v: number }[] = []
        overlay = up(overlay, { assetInstanceId: 'PETCT-CATALOG-TEST-01', v: 1 })
        overlay = up(overlay, { assetInstanceId: 'PETCT-CATALOG-TEST-01', v: 2 })
        expect(overlay).toHaveLength(1)
        expect(overlay[0].v).toBe(2)
    })
})

// Deterministic catalog proof instance
describe('GE Discovery MI catalog proof instance', () => {
    it('builds PETCT-CATALOG-TEST-01 backed by the real record, reusing generic geometry', () => {
        const { result } = buildGeDiscoveryMiCatalogTestAsset(NEIGH)
        expect(result.ok).toBe(true)
        if (result.ok) {
            expect(result.instance.assetInstanceId).toBe(CATALOG_TEST_ASSET_INSTANCE_ID)
            expect(result.instance.assetDefinitionId).toBe(CATALOG_TEST_ASSET_DEFINITION_ID)
            expect(result.instance.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
            expect(result.instance.displayLabel).toBe('GE HealthCare Discovery MI')
            expect(result.instance.dimensions.provenance).toBe('GENERIC_ENGINEERING_PLACEHOLDER')
            // identity separation: three distinct ids
            expect(result.instance.assetInstanceId).not.toBe(result.instance.assetDefinitionId)
            expect(result.instance.assetDefinitionId).not.toBe(result.instance.geometryRepresentationId)
        }
    })

    it('is placed at a non-overlapping position relative to the generic proof', () => {
        const { result } = buildGeDiscoveryMiCatalogTestAsset(NEIGH)
        if (result.ok) {
            // generic is at center.x + offset; catalog is at center.x - 2*offset -> different
            expect(result.instance.transform.position.x).toBeLessThan(NEIGH.center.x)
        }
    })
})

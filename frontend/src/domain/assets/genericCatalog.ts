/**
 * MRT Pharma — generic seed catalog for the 3D asset architecture proof.
 *
 * Establishes ONE generic PET/CT geometry representation and TWO distinct
 * generic engineering definitions that both resolve to it — proving
 * ONE GEOMETRY → MANY ENGINEERING IDENTITIES without duplicating geometry.
 *
 * All dimensions here are explicitly GENERIC_ENGINEERING_PLACEHOLDER. They are
 * NOT manufacturer specifications. No real manufacturer is invented; both
 * definitions use manufacturer = GENERIC and unresolved engineering references.
 */
import { AssetRegistry } from './registry'
import {
    GENERIC_MANUFACTURER,
    type AssetDefinition,
    type AssetDimensions,
    type GeometryRepresentation,
} from './types'

/** GENERIC_TEST_DIMENSIONS — approximately realistic PET/CT proportions (m). */
export const GENERIC_PET_CT_DIMENSIONS: AssetDimensions = {
    width: 2.2, // gantry width (X)
    depth: 3.0, // patient-table travel depth (Y)
    height: 2.0, // gantry height (Z)
    unit: 'METERS',
    provenance: 'GENERIC_ENGINEERING_PLACEHOLDER',
}

export const GENERIC_PET_CT_GEOMETRY_ID = 'GENERIC_PET_CT_SCANNER_V1'

export const GENERIC_PET_CT_GEOMETRY: GeometryRepresentation = {
    geometryRepresentationId: GENERIC_PET_CT_GEOMETRY_ID,
    assetFamily: 'PET_CT_SCANNER',
    representationType: 'GENERIC',
    source: 'GENERATED_GENERIC',
    sourceFormat: 'PARAMETRIC_BENTLEY_GRAPHICS',
    nativeDimensions: GENERIC_PET_CT_DIMENSIONS,
    unit: 'METERS',
    lod: 'LOW',
    manufacturerSpecific: false,
    provenance: 'MRT Pharma generic parametric placeholder; not a manufacturer model; no branding.',
    status: 'PLACEHOLDER',
}

/** Primary generic engineering-test definition used by the proof instance. */
export const GENERIC_PET_CT_DEFINITION_ID = 'GENERIC_PET_CT_ENGINEERING_TEST'

export const GENERIC_PET_CT_DEFINITION: AssetDefinition = {
    assetDefinitionId: GENERIC_PET_CT_DEFINITION_ID,
    assetClass: 'IMAGING',
    assetFamily: 'PET_CT_SCANNER',
    displayName: 'Generic PET/CT Scanner',
    manufacturer: GENERIC_MANUFACTURER,
    model: 'GENERIC_TEST',
    catalogReference: 'GENERIC_PET_CT_ENGINEERING_TEST',
    engineeringMetadataReference: {
        catalogReference: 'GENERIC_PET_CT_ENGINEERING_TEST',
        resolved: false,
        note: 'No real engineering catalog entry linked; generic architecture-proof definition.',
    },
    defaultGeometryRepresentationId: GENERIC_PET_CT_GEOMETRY_ID,
    defaultDimensions: GENERIC_PET_CT_DIMENSIONS,
    capabilities: {
        mrtEndpointRequired: false,
    },
}

/**
 * Second distinct generic definition that reuses the SAME geometry — proves
 * geometry reuse across engineering identities. Still generic; no real
 * manufacturer specs invented.
 */
export const GENERIC_PET_CT_DEFINITION_B_ID = 'GENERIC_PET_CT_ENGINEERING_TEST_B'

export const GENERIC_PET_CT_DEFINITION_B: AssetDefinition = {
    ...GENERIC_PET_CT_DEFINITION,
    assetDefinitionId: GENERIC_PET_CT_DEFINITION_B_ID,
    displayName: 'Generic PET/CT Scanner (Variant B)',
    catalogReference: 'GENERIC_PET_CT_ENGINEERING_TEST_B',
    engineeringMetadataReference: {
        catalogReference: 'GENERIC_PET_CT_ENGINEERING_TEST_B',
        resolved: false,
        note: 'Second generic definition reusing GENERIC_PET_CT_SCANNER_V1 geometry.',
    },
}

/** Build a fresh registry seeded with the generic PET/CT geometry + definitions. */
export function createSeedRegistry(): AssetRegistry {
    const registry = new AssetRegistry()
    registry.registerGeometryRepresentation(GENERIC_PET_CT_GEOMETRY)
    registry.registerAssetDefinition(GENERIC_PET_CT_DEFINITION)
    registry.registerAssetDefinition(GENERIC_PET_CT_DEFINITION_B)
    return registry
}

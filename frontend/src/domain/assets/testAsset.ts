/**
 * Deterministic construction of the ONE generic PET/CT proof instance.
 *
 * The instance's world placement is derived from the currently displayed model
 * range (passed in by the viewer layer as a plain center point + rough size) so
 * it lands within the model's spatial neighborhood — never a huge global
 * coordinate, never dependent on Bentley runtime objects here.
 */
import { createAssetInstance, createAssetInstanceFromCatalog, type CatalogCommandResult, type CommandResult } from './commands'
import { GE_DISCOVERY_MI_RECORD } from './catalogAdapter'
import { createSeedRegistry, GENERIC_PET_CT_DIMENSIONS, GENERIC_PET_CT_DEFINITION_ID, GENERIC_PET_CT_GEOMETRY_ID } from './genericCatalog'
import type { AssetInstance, SpatialPosition } from './types'
import type { AssetRegistry } from './registry'

export const TEST_PROJECT_ID = 'MRT_DEV_VIEWER_PROJECT'
export const TEST_ASSET_INSTANCE_ID = 'PETCT-TEST-01'

/** Plain description of the current model neighborhood (Bentley-free). */
export interface ModelNeighborhood {
    center: SpatialPosition
    /** Rough diagonal size in meters; used to keep the offset bounded/plausible. */
    diagonal: number
}

/**
 * Compute a deterministic, bounded world position for the proof asset near the
 * model center. Offset is a small fraction of the model diagonal (clamped) so
 * the scanner sits beside the model rather than inside or far away.
 */
export function computeTestPlacement(neigh: ModelNeighborhood): SpatialPosition {
    const d = Number.isFinite(neigh.diagonal) && neigh.diagonal > 0 ? neigh.diagonal : 10
    const offset = Math.min(Math.max(d * 0.15, 2), 15) // clamp to [2, 15] m
    return { x: neigh.center.x + offset, y: neigh.center.y, z: neigh.center.z }
}

export interface BuildTestAssetResult {
    registry: AssetRegistry
    result: CommandResult
}

/**
 * Build the seed registry and the single generic PET/CT proof instance placed
 * relative to the given model neighborhood. Deterministic and idempotent for a
 * given neighborhood input.
 */
export function buildGenericPetCtTestAsset(neigh: ModelNeighborhood): BuildTestAssetResult {
    const registry = createSeedRegistry()
    const position = computeTestPlacement(neigh)
    const result = createAssetInstance({
        registry,
        assetInstanceId: TEST_ASSET_INSTANCE_ID,
        assetDefinitionId: GENERIC_PET_CT_DEFINITION_ID,
        projectId: TEST_PROJECT_ID,
        position,
        installationState: 'PLACED',
        spatialSource: 'GENERATED_GENERIC',
        createdFrom: 'MRT Pharma 3D asset architecture proof',
    })
    return { registry, result }
}

export const CATALOG_TEST_ASSET_INSTANCE_ID = 'PETCT-CATALOG-TEST-01'
export const CATALOG_TEST_ASSET_DEFINITION_ID = 'CATALOG_PET_CT_GE_DISCOVERY_MI'

/**
 * Build a catalog-backed proof instance from the REAL GE Discovery MI scanner
 * catalog record, reusing GENERIC_PET_CT_SCANNER_V1 geometry. Placed at a
 * deterministic, non-overlapping offset from the generic proof asset.
 *
 * Dimensions use GEOMETRY_NATIVE provenance (the scanner catalog footprint is
 * NOT_CALIBRATED) — the real manufacturer/model identity drives the label, but
 * dimensions are honestly NOT presented as calibrated catalog dimensions.
 */
export interface BuildCatalogAssetResult {
    registry: AssetRegistry
    result: CatalogCommandResult
}

export function buildGeDiscoveryMiCatalogTestAsset(neigh: ModelNeighborhood): BuildCatalogAssetResult {
    const registry = createSeedRegistry()
    // Place on the OTHER side of the model center from the generic instance so
    // the two proof assets never overlap.
    const base = computeTestPlacement(neigh)
    const d = Number.isFinite(neigh.diagonal) && neigh.diagonal > 0 ? neigh.diagonal : 10
    const separation = Math.min(Math.max(d * 0.15, 2), 15) * 2
    const position = { x: base.x - separation, y: neigh.center.y, z: neigh.center.z }

    const result = createAssetInstanceFromCatalog({
        registry,
        record: GE_DISCOVERY_MI_RECORD,
        assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID,
        assetInstanceId: CATALOG_TEST_ASSET_INSTANCE_ID,
        projectId: TEST_PROJECT_ID,
        position,
        dimensions: {
            ...GENERIC_PET_CT_DIMENSIONS,
            // Reuse generic geometry-native dims but mark provenance honestly:
            // the catalog footprint is NOT_CALIBRATED, so this is geometry-native.
            provenance: 'GENERIC_ENGINEERING_PLACEHOLDER',
        },
        installationState: 'PLACED',
        spatialSource: 'CATALOG',
    })
    return { registry, result }
}

/** Convenience: return only the instance (throws on the impossible failure). */
export function buildGenericPetCtTestInstance(neigh: ModelNeighborhood): AssetInstance {
    const { result } = buildGenericPetCtTestAsset(neigh)
    if (!result.ok) {
        throw new Error(`generic PET/CT test instance construction failed: ${result.errors.map((e) => `${e.field} ${e.message}`).join('; ')}`)
    }
    // Sanity: geometry id is the shared generic geometry.
    if (result.instance.geometryRepresentationId !== GENERIC_PET_CT_GEOMETRY_ID) {
        throw new Error('unexpected geometry representation for test instance')
    }
    return result.instance
}

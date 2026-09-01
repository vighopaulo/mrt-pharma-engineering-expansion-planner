/**
 * Deterministic construction of the ONE generic PET/CT proof instance.
 *
 * The instance's world placement is derived from the currently displayed model
 * range (passed in by the viewer layer as a plain center point + rough size) so
 * it lands within the model's spatial neighborhood — never a huge global
 * coordinate, never dependent on Bentley runtime objects here.
 */
import { createAssetInstance, type CommandResult } from './commands'
import { createSeedRegistry, GENERIC_PET_CT_DEFINITION_ID, GENERIC_PET_CT_GEOMETRY_ID } from './genericCatalog'
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

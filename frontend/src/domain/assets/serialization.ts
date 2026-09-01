/**
 * Stable JSON-compatible serialization for AssetInstance. Never serializes
 * runtime Bentley objects (Viewport / GraphicBuilder / Decorator). Preserves
 * identity, definition reference, geometry reference, transform, dimensions,
 * room assignment, installation state, source/provenance, and scenario.
 *
 * This is the persistence boundary later used by project saves, What-If states,
 * LOCKDOWN scenarios, and event journals.
 */
import { validateAssetInstance } from './validation'
import type { AssetInstance } from './types'

/** Stable versioned wire shape. */
export interface SerializedAssetInstance {
    schema: 'mrt.asset-instance/v1'
    assetInstanceId: string
    assetDefinitionId: string
    projectId: string
    displayLabel: string
    geometryRepresentationId: string
    transform: AssetInstance['transform']
    dimensions: AssetInstance['dimensions']
    roomAssignment: AssetInstance['roomAssignment']
    installationState: AssetInstance['installationState']
    spatialSource: AssetInstance['spatialSource']
    scenario?: AssetInstance['scenario']
    createdFrom?: string
}

export function serializeAssetInstance(inst: AssetInstance): SerializedAssetInstance {
    const v = validateAssetInstance(inst)
    if (!v.ok) {
        throw new Error(`cannot serialize invalid AssetInstance: ${v.errors.map((e) => `${e.field} ${e.message}`).join('; ')}`)
    }
    return {
        schema: 'mrt.asset-instance/v1',
        assetInstanceId: inst.assetInstanceId,
        assetDefinitionId: inst.assetDefinitionId,
        projectId: inst.projectId,
        displayLabel: inst.displayLabel,
        geometryRepresentationId: inst.geometryRepresentationId,
        transform: inst.transform,
        dimensions: inst.dimensions,
        roomAssignment: inst.roomAssignment,
        installationState: inst.installationState,
        spatialSource: inst.spatialSource,
        scenario: inst.scenario,
        createdFrom: inst.createdFrom,
    }
}

export function deserializeAssetInstance(data: SerializedAssetInstance): AssetInstance {
    if (data.schema !== 'mrt.asset-instance/v1') {
        throw new Error(`unsupported asset-instance schema: ${String((data as { schema?: string }).schema)}`)
    }
    const inst: AssetInstance = {
        assetInstanceId: data.assetInstanceId,
        assetDefinitionId: data.assetDefinitionId,
        projectId: data.projectId,
        displayLabel: data.displayLabel,
        geometryRepresentationId: data.geometryRepresentationId,
        transform: data.transform,
        dimensions: data.dimensions,
        roomAssignment: data.roomAssignment,
        installationState: data.installationState,
        spatialSource: data.spatialSource,
        scenario: data.scenario,
        createdFrom: data.createdFrom,
    }
    const v = validateAssetInstance(inst)
    if (!v.ok) {
        throw new Error(`deserialized AssetInstance is invalid: ${v.errors.map((e) => `${e.field} ${e.message}`).join('; ')}`)
    }
    return inst
}

/**
 * MRT Pharma spatial asset command service — pure, immutable domain operations.
 *
 * Operations return UPDATED domain state (never hidden global mutation), which
 * keeps them friendly to future What-If branching, LOCKDOWN, undo/redo, and the
 * existing Event Journal. Each mutating op also emits a structured
 * AssetJournalEvent descriptor so a future journal integration can record it
 * (this domain does NOT own or duplicate the event journal).
 *
 * Operations return updated domain state rather than mutating Bentley rendering
 * internals. Rendering (the decorator) consumes the resulting AssetInstance[].
 */
import type { AssetRegistry } from './registry'
import {
    IDENTITY_SCALE,
    ROOM_NOT_ASSIGNED,
    ZERO_ROTATION,
    type AssetDefinition,
    type AssetInstallationState,
    type AssetInstance,
    type RoomAssignment,
    type SpatialPosition,
    type SpatialRotation,
    type SpatialSource,
    type SpatialTransform,
    type ValidationError,
} from './types'

export type AssetJournalEventType =
    | 'ASSET_INSTANCE_CREATED'
    | 'ASSET_PLACED'
    | 'ASSET_MOVED'
    | 'ASSET_ROTATED'
    | 'ASSET_ROOM_ASSIGNED'
    | 'ASSET_REMOVED'

/** Structured descriptor for a future Event Journal entry (integration point). */
export interface AssetJournalEvent {
    type: AssetJournalEventType
    assetInstanceId: string
    projectId: string
    detail?: Record<string, string | number | boolean>
}

export type CommandResult =
    | { ok: true; instance: AssetInstance; event: AssetJournalEvent }
    | { ok: false; errors: ValidationError[] }

export type RemoveResult =
    | { ok: true; removedInstanceId: string; event: AssetJournalEvent }
    | { ok: false; errors: ValidationError[] }

export interface CreateAssetInstanceInput {
    registry: AssetRegistry
    assetInstanceId: string
    assetDefinitionId: string
    projectId: string
    /** World-coordinate position for the initial placement. */
    position: SpatialPosition
    /** Optional overrides; sensible defaults derived from the definition. */
    rotation?: SpatialRotation
    displayLabel?: string
    installationState?: AssetInstallationState
    spatialSource?: SpatialSource
    roomAssignment?: RoomAssignment
    createdFrom?: string
}

/**
 * Create a spatial asset instance from a registered definition, placed at the
 * given world position. Display label derives from the definition (never
 * hardcoded independently). Validated against the registry before returning.
 */
export function createAssetInstance(input: CreateAssetInstanceInput): CommandResult {
    const def: AssetDefinition | undefined = input.registry.getAssetDefinition(input.assetDefinitionId)
    if (!def) {
        return { ok: false, errors: [{ field: 'assetDefinitionId', message: `unresolved definition: ${input.assetDefinitionId}` }] }
    }
    const geoRes = input.registry.resolveGeometryForAssetDefinition(input.assetDefinitionId)
    if (geoRes.status !== 'RESOLVED') {
        return { ok: false, errors: [{ field: 'geometryRepresentationId', message: `GEOMETRY_NOT_AVAILABLE for ${input.assetDefinitionId}` }] }
    }

    const transform: SpatialTransform = {
        position: input.position,
        rotation: input.rotation ?? { ...ZERO_ROTATION },
        scale: { ...IDENTITY_SCALE },
        coordinateSpace: 'BENTLEY_WORLD_COORDINATES',
    }

    const instance: AssetInstance = {
        assetInstanceId: input.assetInstanceId,
        assetDefinitionId: def.assetDefinitionId,
        projectId: input.projectId,
        displayLabel: input.displayLabel ?? def.displayName,
        geometryRepresentationId: def.defaultGeometryRepresentationId,
        transform,
        dimensions: { ...def.defaultDimensions },
        roomAssignment: input.roomAssignment ?? { ...ROOM_NOT_ASSIGNED },
        installationState: input.installationState ?? 'PLACED',
        spatialSource: input.spatialSource ?? 'MRT_PHARMA',
        createdFrom: input.createdFrom,
    }

    const v = input.registry.validateAssetInstanceAgainstRegistry(instance)
    if (!v.ok) return { ok: false, errors: v.errors }

    return {
        ok: true,
        instance,
        event: {
            type: 'ASSET_INSTANCE_CREATED',
            assetInstanceId: instance.assetInstanceId,
            projectId: instance.projectId,
            detail: { assetDefinitionId: instance.assetDefinitionId, geometryRepresentationId: instance.geometryRepresentationId },
        },
    }
}

function withTransform(inst: AssetInstance, transform: SpatialTransform): AssetInstance {
    return { ...inst, transform }
}

/** Immutable placement/move: returns a new instance at the given world position. */
export function placeAsset(inst: AssetInstance, position: SpatialPosition): CommandResult {
    if (![position.x, position.y, position.z].every(Number.isFinite)) {
        return { ok: false, errors: [{ field: 'position', message: 'must be finite' }] }
    }
    const updated = withTransform(inst, { ...inst.transform, position })
    return { ok: true, instance: updated, event: { type: 'ASSET_PLACED', assetInstanceId: inst.assetInstanceId, projectId: inst.projectId } }
}

export function moveAsset(inst: AssetInstance, delta: SpatialPosition): CommandResult {
    if (![delta.x, delta.y, delta.z].every(Number.isFinite)) {
        return { ok: false, errors: [{ field: 'delta', message: 'must be finite' }] }
    }
    const position = {
        x: inst.transform.position.x + delta.x,
        y: inst.transform.position.y + delta.y,
        z: inst.transform.position.z + delta.z,
    }
    const updated = withTransform(inst, { ...inst.transform, position })
    return { ok: true, instance: updated, event: { type: 'ASSET_MOVED', assetInstanceId: inst.assetInstanceId, projectId: inst.projectId } }
}

export function rotateAsset(inst: AssetInstance, rotation: SpatialRotation): CommandResult {
    if (![rotation.yaw, rotation.pitch, rotation.roll].every(Number.isFinite)) {
        return { ok: false, errors: [{ field: 'rotation', message: 'must be finite' }] }
    }
    const updated = withTransform(inst, { ...inst.transform, rotation })
    return { ok: true, instance: updated, event: { type: 'ASSET_ROTATED', assetInstanceId: inst.assetInstanceId, projectId: inst.projectId } }
}

export function assignAssetToRoom(inst: AssetInstance, room: RoomAssignment): CommandResult {
    const updated: AssetInstance = { ...inst, roomAssignment: room }
    return {
        ok: true,
        instance: updated,
        event: {
            type: 'ASSET_ROOM_ASSIGNED',
            assetInstanceId: inst.assetInstanceId,
            projectId: inst.projectId,
            detail: { roomState: room.state, roomId: room.roomId ?? '' },
        },
    }
}

/** Mark removed (soft). Returns the id + event; callers drop it from state. */
export function removeAsset(inst: AssetInstance): RemoveResult {
    return {
        ok: true,
        removedInstanceId: inst.assetInstanceId,
        event: { type: 'ASSET_REMOVED', assetInstanceId: inst.assetInstanceId, projectId: inst.projectId },
    }
}

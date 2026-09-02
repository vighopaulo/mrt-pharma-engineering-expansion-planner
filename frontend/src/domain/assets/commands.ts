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
import { adaptCatalogRecordToAssetDefinition, assetFamilyForCatalogModality, type AuthoritativeEquipmentRecord } from './catalogAdapter'
import {
    IDENTITY_SCALE,
    ROOM_NOT_ASSIGNED,
    ZERO_ROTATION,
    type AssetDefinition,
    type AssetDimensions,
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

function scenarioDetail(inst: AssetInstance): Record<string, string> {
    return {
        scenarioId: inst.scenario?.scenarioId ?? '',
        scenarioState: inst.scenario?.scenarioState ?? '',
    }
}

/** Immutable placement/move: returns a new instance at the given world position. */
export function placeAsset(inst: AssetInstance, position: SpatialPosition): CommandResult {
    if (![position.x, position.y, position.z].every(Number.isFinite)) {
        return { ok: false, errors: [{ field: 'position', message: 'must be finite' }] }
    }
    const updated = withTransform(inst, { ...inst.transform, position })
    return { ok: true, instance: updated, event: { type: 'ASSET_PLACED', assetInstanceId: inst.assetInstanceId, projectId: inst.projectId } }
}

/**
 * Immutable absolute move: returns a NEW instance positioned at `position`.
 * IDENTITY IMMUTABLE — only transform.position changes; rotation/scale and all
 * identity/provenance fields are preserved. Emits ASSET_MOVED with previous +
 * new position (and unchanged rotation) for the event journal.
 */
export function moveAssetTo(inst: AssetInstance, position: SpatialPosition): CommandResult {
    if (![position.x, position.y, position.z].every(Number.isFinite)) {
        return { ok: false, errors: [{ field: 'position', message: 'must be finite' }] }
    }
    const previous = inst.transform.position
    const updated = withTransform(inst, { ...inst.transform, position })
    return {
        ok: true,
        instance: updated,
        event: {
            type: 'ASSET_MOVED',
            assetInstanceId: inst.assetInstanceId,
            projectId: inst.projectId,
            detail: {
                assetDefinitionId: inst.assetDefinitionId,
                geometryRepresentationId: inst.geometryRepresentationId,
                prevX: previous.x, prevY: previous.y, prevZ: previous.z,
                newX: position.x, newY: position.y, newZ: position.z,
                yaw: inst.transform.rotation.yaw,
                roomAssignment: inst.roomAssignment.state,
                ...scenarioDetail(inst),
            },
        },
    }
}

/** Immutable relative move by a delta (kept for future use / tests). */
export function moveAsset(inst: AssetInstance, delta: SpatialPosition): CommandResult {
    if (![delta.x, delta.y, delta.z].every(Number.isFinite)) {
        return { ok: false, errors: [{ field: 'delta', message: 'must be finite' }] }
    }
    return moveAssetTo(inst, {
        x: inst.transform.position.x + delta.x,
        y: inst.transform.position.y + delta.y,
        z: inst.transform.position.z + delta.z,
    })
}

/**
 * Immutable rotation: returns a NEW instance with the given rotation. IDENTITY
 * IMMUTABLE — only transform.rotation changes; position/scale and all identity/
 * provenance fields are preserved. Emits ASSET_ROTATED with previous + new
 * rotation.
 */
export function rotateAsset(inst: AssetInstance, rotation: SpatialRotation): CommandResult {
    if (![rotation.yaw, rotation.pitch, rotation.roll].every(Number.isFinite)) {
        return { ok: false, errors: [{ field: 'rotation', message: 'must be finite' }] }
    }
    const previous = inst.transform.rotation
    const updated = withTransform(inst, { ...inst.transform, rotation })
    return {
        ok: true,
        instance: updated,
        event: {
            type: 'ASSET_ROTATED',
            assetInstanceId: inst.assetInstanceId,
            projectId: inst.projectId,
            detail: {
                assetDefinitionId: inst.assetDefinitionId,
                geometryRepresentationId: inst.geometryRepresentationId,
                prevYaw: previous.yaw, prevPitch: previous.pitch, prevRoll: previous.roll,
                newYaw: rotation.yaw, newPitch: rotation.pitch, newRoll: rotation.roll,
                x: inst.transform.position.x, y: inst.transform.position.y, z: inst.transform.position.z,
                ...scenarioDetail(inst),
            },
        },
    }
}

/** Rotation unit + step for the controlled ±90° yaw workflow. */
export const ROTATION_UNIT = 'DEGREES' as const
export const ROTATION_STEP_DEGREES = 90

/** Normalize a yaw in degrees to the half-open range [0, 360). */
export function normalizeYawDegrees(yaw: number): number {
    if (!Number.isFinite(yaw)) return 0
    const m = yaw % 360
    return m < 0 ? m + 360 : m
}

/**
 * Immutable controlled yaw rotation by ±90° (or a multiple). Only yaw changes;
 * pitch/roll are preserved exactly. Result yaw is normalized to [0, 360).
 */
export function rotateAssetYawBy(inst: AssetInstance, deltaDegrees: number): CommandResult {
    if (!Number.isFinite(deltaDegrees)) {
        return { ok: false, errors: [{ field: 'rotation', message: 'delta must be finite' }] }
    }
    const rotation: SpatialRotation = {
        yaw: normalizeYawDegrees(inst.transform.rotation.yaw + deltaDegrees),
        pitch: inst.transform.rotation.pitch,
        roll: inst.transform.rotation.roll,
    }
    return rotateAsset(inst, rotation)
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

// ---------------------------------------------------------------------------
// Catalog-backed creation
// ---------------------------------------------------------------------------

export type CatalogCreateFailure =
    | 'CATALOG_RECORD_NOT_FOUND'
    | 'UNSUPPORTED_ASSET_FAMILY'
    | 'GEOMETRY_NOT_AVAILABLE'
    | 'GEOMETRY_FAMILY_MISMATCH'
    | 'INVALID_CATALOG_ADAPTER'
    | 'DIMENSIONS_NOT_CALIBRATED'

export type CatalogCommandResult =
    | { ok: true; instance: AssetInstance; definition: AssetDefinition; event: AssetJournalEvent }
    | { ok: false; reason: CatalogCreateFailure; message: string }

export interface CreateFromCatalogInput {
    registry: AssetRegistry
    record: AuthoritativeEquipmentRecord
    assetDefinitionId: string
    assetInstanceId: string
    projectId: string
    position: SpatialPosition
    /** Geometry-native / placeholder dims + honest provenance (catalog footprint
     * is typically NOT_CALIBRATED, so callers must NOT claim CATALOG provenance
     * unless the record's dimensionsCalibrated is true). */
    dimensions: AssetDimensions
    /** Optional explicit geometry id; otherwise resolved by family priority. */
    explicitGeometryRepresentationId?: string
    rotation?: SpatialRotation
    installationState?: AssetInstallationState
    spatialSource?: SpatialSource
    roomAssignment?: RoomAssignment
}

/**
 * Build a spatial asset instance from an authoritative equipment catalog record:
 *   1. adapt record → AssetDefinition (label from catalog identity),
 *   2. resolve a COMPATIBLE geometry representation (family-checked, priority),
 *   3. register the definition + create a distinct instance,
 *   4. preserve catalog provenance,
 *   5. return explicit typed failures at each stage.
 * No Bentley interaction. Engineering values are referenced, not copied.
 */
export function createAssetInstanceFromCatalog(input: CreateFromCatalogInput): CatalogCommandResult {
    // Guard against claiming calibrated catalog dimensions when the record says otherwise.
    if (input.dimensions.provenance === 'CATALOG' && !input.record.dimensionsCalibrated) {
        return {
            ok: false,
            reason: 'DIMENSIONS_NOT_CALIBRATED',
            message: `catalog record ${input.record.catalogRecordId} has no calibrated footprint; cannot label dimensions as CATALOG`,
        }
    }

    // 1. adapt (this also determines the asset family from modality).
    const family = assetFamilyForCatalogModality(input.record.modality, input.record.configurationNote)
    if (!family) {
        return { ok: false, reason: 'UNSUPPORTED_ASSET_FAMILY', message: `no family mapping for modality '${input.record.modality}'` }
    }

    // 2. resolve compatible geometry (family-checked, deterministic priority).
    const geoRes = input.registry.resolveCompatibleGeometry(family, input.explicitGeometryRepresentationId)
    if (geoRes.status !== 'RESOLVED') {
        return { ok: false, reason: 'GEOMETRY_NOT_AVAILABLE', message: `no compatible geometry for family ${family}` }
    }
    if (geoRes.representation.assetFamily !== family) {
        return { ok: false, reason: 'GEOMETRY_FAMILY_MISMATCH', message: `resolved geometry family ${geoRes.representation.assetFamily} != ${family}` }
    }

    const adapted = adaptCatalogRecordToAssetDefinition(input.record, {
        assetDefinitionId: input.assetDefinitionId,
        defaultGeometryRepresentationId: geoRes.representation.geometryRepresentationId,
        dimensions: input.dimensions,
    })
    if (!adapted.ok) {
        const reason: CatalogCreateFailure = adapted.reason === 'UNSUPPORTED_ASSET_FAMILY' ? 'UNSUPPORTED_ASSET_FAMILY' : 'INVALID_CATALOG_ADAPTER'
        return { ok: false, reason, message: adapted.message }
    }

    // 3. register the definition (idempotent-ish: registry validates + family-checks).
    try {
        if (!input.registry.getAssetDefinition(adapted.definition.assetDefinitionId)) {
            input.registry.registerAssetDefinition(adapted.definition)
        }
    } catch (e) {
        return { ok: false, reason: 'INVALID_CATALOG_ADAPTER', message: e instanceof Error ? e.message : String(e) }
    }

    // 4. create the instance (label comes from the adapted definition).
    const created = createAssetInstance({
        registry: input.registry,
        assetInstanceId: input.assetInstanceId,
        assetDefinitionId: adapted.definition.assetDefinitionId,
        projectId: input.projectId,
        position: input.position,
        rotation: input.rotation,
        installationState: input.installationState ?? 'PLACED',
        spatialSource: input.spatialSource ?? 'CATALOG',
        roomAssignment: input.roomAssignment,
        createdFrom: `catalog:${input.record.catalogSource}#${input.record.catalogRecordId}`,
    })
    if (!created.ok) {
        return { ok: false, reason: 'INVALID_CATALOG_ADAPTER', message: created.errors.map((x) => `${x.field} ${x.message}`).join('; ') }
    }
    // Ensure the placed instance carries the catalog-derived dimensions/provenance.
    const instance: AssetInstance = { ...created.instance, dimensions: input.dimensions }

    return {
        ok: true,
        instance,
        definition: adapted.definition,
        event: {
            type: 'ASSET_INSTANCE_CREATED',
            assetInstanceId: instance.assetInstanceId,
            projectId: instance.projectId,
            detail: {
                assetDefinitionId: instance.assetDefinitionId,
                geometryRepresentationId: instance.geometryRepresentationId,
                catalogRecordId: input.record.catalogRecordId,
            },
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

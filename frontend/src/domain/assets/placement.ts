/**
 * MRT Pharma controlled placement — domain layer (Bentley-free).
 *
 * Flow:
 *   AssetLibraryEntry --select--> PlacementIntent --(user clicks)--> world point
 *     --> placeFromIntent() reuses createAssetInstanceFromCatalog()
 *     --> AssetInstance + ASSET_PLACED event
 *
 * Separation of concerns (Sec 31/32): the catalog record is resolved into a
 * PlacementIntent up front. The Bentley placement tool receives an already
 * resolved intent + a world point and never queries the catalog. This module
 * never imports Bentley and is fully unit-testable.
 */
import { createAssetInstanceFromCatalog, type AssetJournalEvent } from './commands'
import type { AuthoritativeEquipmentRecord } from './catalogAdapter'
import { GENERIC_PET_CT_DIMENSIONS } from './genericCatalog'
import type { AssetRegistry } from './registry'
import {
    ZERO_ROTATION,
    type AssetDimensions,
    type AssetInstance,
    type AssetFamily,
    type RoomAssignment,
    type ScenarioProvenance,
    type SpatialPosition,
    type SpatialRotation,
    ROOM_NOT_ASSIGNED,
} from './types'

/**
 * A resolved intent to place a specific catalog-backed asset. Created when the
 * user chooses PLACE; consumed exactly once when a world point is accepted. No
 * AssetInstance exists until placement is accepted.
 */
export interface PlacementIntent {
    /** Authoritative catalog record being placed (identity, referenced). */
    record: AuthoritativeEquipmentRecord
    catalogRecordId: string
    assetDefinitionId: string
    resolvedGeometryRepresentationId: string
    assetFamily: AssetFamily
    displayLabel: string
    /** Default rotation stored so later rotation tools can modify it. */
    defaultRotation: SpatialRotation
}

export type BuildIntentResult =
    | { ok: true; intent: PlacementIntent }
    | { ok: false; reason: BuildIntentFailure; message: string }

export type BuildIntentFailure =
    | 'UNSUPPORTED_ASSET_FAMILY'
    | 'GEOMETRY_NOT_AVAILABLE'
    | 'INVALID_PLACEMENT_INTENT'

import { assetFamilyForCatalogModality } from './catalogAdapter'

/**
 * Resolve a catalog record into a PlacementIntent WITHOUT creating an instance.
 * Determines the family, resolves compatible geometry, and computes the
 * definition id. `assetDefinitionId` is provided by the caller so the intent
 * stays aligned with the catalog-backed definition used at creation time.
 */
export function buildPlacementIntent(input: {
    record: AuthoritativeEquipmentRecord
    assetDefinitionId: string
    registry: AssetRegistry
    explicitGeometryRepresentationId?: string
}): BuildIntentResult {
    const { record, assetDefinitionId, registry } = input
    if (!record.catalogRecordId?.trim() || !assetDefinitionId.trim()) {
        return { ok: false, reason: 'INVALID_PLACEMENT_INTENT', message: 'missing catalog record id or definition id' }
    }
    const family = assetFamilyForCatalogModality(record.modality, record.configurationNote)
    if (!family) {
        return { ok: false, reason: 'UNSUPPORTED_ASSET_FAMILY', message: `no family mapping for modality '${record.modality}'` }
    }
    const geoRes = registry.resolveCompatibleGeometry(family, input.explicitGeometryRepresentationId)
    if (geoRes.status !== 'RESOLVED') {
        return { ok: false, reason: 'GEOMETRY_NOT_AVAILABLE', message: `no compatible geometry for family ${family}` }
    }
    return {
        ok: true,
        intent: {
            record,
            catalogRecordId: record.catalogRecordId,
            assetDefinitionId,
            resolvedGeometryRepresentationId: geoRes.representation.geometryRepresentationId,
            assetFamily: family,
            displayLabel: `${record.manufacturer} ${record.model}`,
            defaultRotation: { ...ZERO_ROTATION },
        },
    }
}

/**
 * Deterministic-per-application instance-id generator. Sequence is owned by
 * application state (NOT a React component), so it does not reset on re-render,
 * viewer remount, or decorator re-registration. Ids are prefixed by catalog
 * record so multiple families never collide.
 */
export class InstanceIdGenerator {
    private counters = new Map<string, number>()

    /** e.g. next('GE_DISCOVERY_MI') -> 'PETCT-GE-DISCOVERY-MI-0001'. */
    next(catalogRecordId: string): string {
        const n = (this.counters.get(catalogRecordId) ?? 0) + 1
        this.counters.set(catalogRecordId, n)
        const slug = catalogRecordId.replace(/[^A-Za-z0-9]+/g, '-').toUpperCase().replace(/^-+|-+$/g, '')
        return `PETCT-${slug}-${String(n).padStart(4, '0')}`
    }

    /** Current count issued for a record (for tests/inspection). */
    countFor(catalogRecordId: string): number {
        return this.counters.get(catalogRecordId) ?? 0
    }
}

export type PlacementFailure =
    | 'NO_ACTIVE_VIEWPORT'
    | 'WORLD_POINT_NOT_RESOLVED'
    | 'CATALOG_RECORD_NOT_FOUND'
    | 'GEOMETRY_NOT_AVAILABLE'
    | 'INVALID_PLACEMENT_INTENT'
    | 'ASSET_INSTANCE_CREATION_FAILED'
    | 'OVERLAY_INSERTION_FAILED'
    | 'PLACEMENT_CANCELLED'

export type PlacementResult =
    | { ok: true; instance: AssetInstance; event: AssetJournalEvent }
    | { ok: false; reason: PlacementFailure; message: string }

export interface PlaceFromIntentInput {
    registry: AssetRegistry
    intent: PlacementIntent
    assetInstanceId: string
    projectId: string
    /** Accepted world-space point (from the Bentley placement tool). */
    position: SpatialPosition
    scenario: ScenarioProvenance
    rotation?: SpatialRotation
    roomAssignment?: RoomAssignment
    /** Placeholder/geometry-native dims (catalog footprint is NOT_CALIBRATED). */
    dimensions?: AssetDimensions
}

/**
 * Create a user-placed AssetInstance from a resolved PlacementIntent + accepted
 * world point. Reuses createAssetInstanceFromCatalog (single creation path — no
 * UI-specific shortcut). spatialSource = USER_PLACED; catalog origin preserved
 * in createdFrom; roomAssignment defaults to NOT_ASSIGNED (no auto room).
 */
export function placeFromIntent(input: PlaceFromIntentInput): PlacementResult {
    if (![input.position.x, input.position.y, input.position.z].every(Number.isFinite)) {
        return { ok: false, reason: 'WORLD_POINT_NOT_RESOLVED', message: 'world point is not finite' }
    }
    const dims: AssetDimensions = input.dimensions ?? {
        ...GENERIC_PET_CT_DIMENSIONS,
        provenance: 'GENERIC_ENGINEERING_PLACEHOLDER',
    }

    const created = createAssetInstanceFromCatalog({
        registry: input.registry,
        record: input.intent.record,
        assetDefinitionId: input.intent.assetDefinitionId,
        assetInstanceId: input.assetInstanceId,
        projectId: input.projectId,
        position: input.position,
        dimensions: dims,
        explicitGeometryRepresentationId: input.intent.resolvedGeometryRepresentationId,
        rotation: input.rotation ?? input.intent.defaultRotation,
        installationState: 'PLACED',
        spatialSource: 'USER_PLACED',
        roomAssignment: input.roomAssignment ?? { ...ROOM_NOT_ASSIGNED },
    })
    if (!created.ok) {
        const reason: PlacementFailure =
            created.reason === 'CATALOG_RECORD_NOT_FOUND'
                ? 'CATALOG_RECORD_NOT_FOUND'
                : created.reason === 'GEOMETRY_NOT_AVAILABLE' || created.reason === 'GEOMETRY_FAMILY_MISMATCH'
                    ? 'GEOMETRY_NOT_AVAILABLE'
                    : 'ASSET_INSTANCE_CREATION_FAILED'
        return { ok: false, reason, message: created.message }
    }

    // Attach scenario provenance + explicit ASSET_PLACED event descriptor.
    const instance: AssetInstance = { ...created.instance, scenario: input.scenario }
    const event: AssetJournalEvent = {
        type: 'ASSET_PLACED',
        assetInstanceId: instance.assetInstanceId,
        projectId: instance.projectId,
        detail: {
            assetDefinitionId: instance.assetDefinitionId,
            geometryRepresentationId: instance.geometryRepresentationId,
            catalogRecordId: input.intent.catalogRecordId,
            x: input.position.x,
            y: input.position.y,
            z: input.position.z,
            yaw: instance.transform.rotation.yaw,
            pitch: instance.transform.rotation.pitch,
            roll: instance.transform.rotation.roll,
            roomAssignment: instance.roomAssignment.state,
            scenarioId: input.scenario.scenarioId ?? '',
            scenarioState: input.scenario.scenarioState ?? '',
        },
    }
    return { ok: true, instance, event }
}

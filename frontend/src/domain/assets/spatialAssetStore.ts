/**
 * SpatialAssetStore — the SINGLE authoritative, application-owned store of
 * spatial AssetInstances for the active project/scenario context.
 *
 * There is ONE source of truth. The Bentley overlay decorator, the Asset
 * Library placement workflow, and the Placed Assets panel all consume this
 * store. It is event-driven (explicit subscribe/notify) — NO polling, NO
 * setInterval, NO render-loop synchronization, NO repeated Bentley queries.
 *
 * The store is Bentley-free (unit-testable). It owns:
 *   - the seed AssetRegistry (geometry + definitions),
 *   - the current AssetInstance[] (project-scoped),
 *   - the InstanceIdGenerator (application-scoped, survives re-render/remount),
 *   - the active PlacementIntent (if any).
 *
 * Decorator registration lifecycle is deliberately NOT owned here (that stays
 * in spatialAssetOverlay), preserving the corrected separation:
 *   decorator registration lifecycle != asset instance state lifecycle.
 */
import { createSeedRegistry } from './genericCatalog'
import type { AssetRegistry } from './registry'
import {
    InstanceIdGenerator,
    placeFromIntent,
    type PlacementIntent,
    type PlacementResult,
} from './placement'
import { moveAssetTo, rotateAssetYawBy, type AssetJournalEvent } from './commands'
import type { AssetInstance, ScenarioProvenance, SpatialPosition, SpatialRotation } from './types'

export interface SpatialAssetStoreOptions {
    projectId: string
    scenario: ScenarioProvenance
}

export type StoreListener = () => void

/**
 * Narrow, mutually-exclusive spatial interaction state. Only one interaction
 * can be active at a time so two Bentley tools never compete for clicks.
 */
export type SpatialInteractionState = 'IDLE' | 'PLACING' | 'MOVING'

/**
 * A resolved intent to MOVE an existing instance. Bound to one assetInstanceId
 * for the whole move so a UI selection change cannot retarget the active move.
 */
export interface MoveIntent {
    assetInstanceId: string
    displayLabel: string
    previousPosition: SpatialPosition
}

export type MoveResult =
    | { ok: true; instance: AssetInstance; event: AssetJournalEvent }
    | { ok: false; reason: MoveFailure; message: string }

export type MoveFailure =
    | 'ASSET_NOT_FOUND'
    | 'WORLD_POINT_NOT_RESOLVED'
    | 'MOVE_INTENT_INVALID'
    | 'SPATIAL_INTERACTION_ALREADY_ACTIVE'
    | 'STORE_UPDATE_FAILED'

export type RotateResult =
    | { ok: true; instance: AssetInstance; event: AssetJournalEvent }
    | { ok: false; reason: RotateFailure; message: string }

export type RotateFailure =
    | 'ASSET_NOT_FOUND'
    | 'ROTATION_INVALID'
    | 'SPATIAL_INTERACTION_ALREADY_ACTIVE'
    | 'STORE_UPDATE_FAILED'

/** Public read-only snapshot for UI consumers (stable per version). */
export interface SpatialAssetSnapshot {
    version: number
    projectId: string
    instances: readonly AssetInstance[]
    interaction: SpatialInteractionState
    placementIntent: PlacementIntent | undefined
    placementModeActive: boolean
    moveIntent: MoveIntent | undefined
    moveModeActive: boolean
    selectedAssetInstanceId: string | undefined
}

export class SpatialAssetStore {
    private readonly registry: AssetRegistry = createSeedRegistry()
    private readonly idGen = new InstanceIdGenerator()
    private instances: AssetInstance[] = []
    private intent: PlacementIntent | undefined
    private moveIntent: MoveIntent | undefined
    private selectedId: string | undefined
    private readonly listeners = new Set<StoreListener>()
    private version = 0
    private snapshot: SpatialAssetSnapshot

    readonly projectId: string
    readonly scenario: ScenarioProvenance

    constructor(opts: SpatialAssetStoreOptions) {
        this.projectId = opts.projectId
        this.scenario = opts.scenario
        this.snapshot = this.computeSnapshot()
    }

    getRegistry(): AssetRegistry {
        return this.registry
    }

    // --- observability (event-driven; getSnapshot returns a stable ref) ---
    subscribe(listener: StoreListener): () => void {
        this.listeners.add(listener)
        return () => {
            this.listeners.delete(listener)
        }
    }

    getSnapshot(): SpatialAssetSnapshot {
        return this.snapshot
    }

    /** Instances scoped to the active project (what the overlay draws). */
    getProjectInstances(): readonly AssetInstance[] {
        return this.instances.filter((i) => i.projectId === this.projectId)
    }

    /** The single mutually-exclusive interaction state. */
    getInteractionState(): SpatialInteractionState {
        if (this.intent !== undefined) return 'PLACING'
        if (this.moveIntent !== undefined) return 'MOVING'
        return 'IDLE'
    }

    private computeSnapshot(): SpatialAssetSnapshot {
        return {
            version: this.version,
            projectId: this.projectId,
            instances: this.instances.slice(),
            interaction: this.getInteractionState(),
            placementIntent: this.intent,
            placementModeActive: this.intent !== undefined,
            moveIntent: this.moveIntent,
            moveModeActive: this.moveIntent !== undefined,
            selectedAssetInstanceId: this.selectedId,
        }
    }

    private emit(): void {
        this.version += 1
        this.snapshot = this.computeSnapshot()
        for (const l of this.listeners) l()
    }

    // --- placement intent lifecycle ---
    /**
     * Enter placement mode with a resolved intent (no instance created yet).
     * Rejected if any interaction (placement or move) is already active so two
     * Bentley tools never compete for clicks.
     */
    beginPlacement(intent: PlacementIntent): { ok: true } | { ok: false; reason: 'SPATIAL_INTERACTION_ALREADY_ACTIVE' } {
        if (this.getInteractionState() !== 'IDLE') {
            return { ok: false, reason: 'SPATIAL_INTERACTION_ALREADY_ACTIVE' }
        }
        this.intent = intent
        this.emit()
        return { ok: true }
    }

    isPlacementModeActive(): boolean {
        return this.intent !== undefined
    }

    getActiveIntent(): PlacementIntent | undefined {
        return this.intent
    }

    /** Exit placement mode WITHOUT creating an instance (cancel). */
    cancelPlacement(): void {
        if (this.intent === undefined) return
        this.intent = undefined
        this.emit()
    }

    /**
     * Complete placement at an accepted world point. Consumes the active intent
     * exactly once, creates ONE unique instance, inserts it (keyed by
     * assetInstanceId), and exits placement mode. One accepted click => one new
     * instance.
     */
    completePlacementAt(position: SpatialPosition, rotation?: SpatialRotation): PlacementResult {
        const intent = this.intent
        if (!intent) {
            return { ok: false, reason: 'INVALID_PLACEMENT_INTENT', message: 'no active placement intent' }
        }
        // Consume the intent up front so a duplicate click cannot double-place.
        this.intent = undefined

        const assetInstanceId = this.idGen.next(intent.catalogRecordId)
        const result = placeFromIntent({
            registry: this.registry,
            intent,
            assetInstanceId,
            projectId: this.projectId,
            position,
            rotation,
            scenario: this.scenario,
        })
        if (!result.ok) {
            // Failed placement still exits placement mode (emit for the intent clear).
            this.emit()
            return result
        }
        // Insert without its own emit; a single emit below covers the intent
        // consumption + insertion as ONE state change (one click = one notify).
        this.instances = this.instances.filter((i) => i.assetInstanceId !== result.instance.assetInstanceId)
        this.instances.push(result.instance)
        this.emit()
        return result
    }

    // --- selection ---
    /** Select an existing placed asset (product selection; store-resolved). */
    selectAsset(assetInstanceId: string | undefined): void {
        if (this.selectedId === assetInstanceId) return
        this.selectedId = assetInstanceId
        this.emit()
    }

    getSelectedInstance(): AssetInstance | undefined {
        return this.selectedId ? this.getInstance(this.selectedId) : undefined
    }

    // --- move lifecycle ---
    /**
     * Enter MOVE mode for a specific instance. The move is bound to this
     * assetInstanceId for its whole lifetime — a later UI selection change does
     * NOT retarget the active move. Rejected if any interaction is already
     * active (mutual exclusivity).
     */
    beginMove(assetInstanceId: string): { ok: true; intent: MoveIntent } | { ok: false; reason: MoveFailure } {
        if (this.getInteractionState() !== 'IDLE') {
            return { ok: false, reason: 'SPATIAL_INTERACTION_ALREADY_ACTIVE' }
        }
        const inst = this.getInstance(assetInstanceId)
        if (!inst) return { ok: false, reason: 'ASSET_NOT_FOUND' }
        this.moveIntent = {
            assetInstanceId: inst.assetInstanceId,
            displayLabel: inst.displayLabel,
            previousPosition: { ...inst.transform.position },
        }
        this.emit()
        return { ok: true, intent: this.moveIntent }
    }

    isMoveModeActive(): boolean {
        return this.moveIntent !== undefined
    }

    getActiveMoveIntent(): MoveIntent | undefined {
        return this.moveIntent
    }

    /** Exit MOVE mode WITHOUT changing any transform (cancel). */
    cancelMove(): void {
        if (this.moveIntent === undefined) return
        this.moveIntent = undefined
        this.emit()
    }

    /**
     * Complete a move at an accepted world point. Consumes the active move
     * intent exactly once, updates ONLY the bound instance's position (identity
     * + rotation preserved), and exits MOVE mode. One accepted click => one move.
     */
    completeMoveAt(position: SpatialPosition): MoveResult {
        const intent = this.moveIntent
        if (!intent) return { ok: false, reason: 'MOVE_INTENT_INVALID', message: 'no active move intent' }
        // Consume up front so a duplicate click cannot double-move.
        this.moveIntent = undefined

        if (![position.x, position.y, position.z].every(Number.isFinite)) {
            this.emit()
            return { ok: false, reason: 'WORLD_POINT_NOT_RESOLVED', message: 'world point not finite' }
        }
        const inst = this.getInstance(intent.assetInstanceId)
        if (!inst) {
            this.emit()
            return { ok: false, reason: 'ASSET_NOT_FOUND', message: `asset gone: ${intent.assetInstanceId}` }
        }
        const cmd = moveAssetTo(inst, position)
        if (!cmd.ok) {
            this.emit()
            return { ok: false, reason: 'STORE_UPDATE_FAILED', message: cmd.errors.map((e) => `${e.field} ${e.message}`).join('; ') }
        }
        // Replace the same-id instance (identity immutable) and emit once.
        this.instances = this.instances.map((i) => (i.assetInstanceId === cmd.instance.assetInstanceId ? cmd.instance : i))
        this.emit()
        return { ok: true, instance: cmd.instance, event: cmd.event }
    }

    // --- rotation (immediate; no interaction mode) ---
    /**
     * Rotate an instance's yaw by a controlled step (±90°). Rejected while MOVE
     * or PLACEMENT is active (deterministic interaction). Only yaw changes.
     */
    rotateAssetYaw(assetInstanceId: string, deltaDegrees: number): RotateResult {
        if (this.getInteractionState() !== 'IDLE') {
            return { ok: false, reason: 'SPATIAL_INTERACTION_ALREADY_ACTIVE', message: `interaction active: ${this.getInteractionState()}` }
        }
        const inst = this.getInstance(assetInstanceId)
        if (!inst) return { ok: false, reason: 'ASSET_NOT_FOUND', message: `asset not found: ${assetInstanceId}` }
        const cmd = rotateAssetYawBy(inst, deltaDegrees)
        if (!cmd.ok) {
            return { ok: false, reason: 'ROTATION_INVALID', message: cmd.errors.map((e) => `${e.field} ${e.message}`).join('; ') }
        }
        this.instances = this.instances.map((i) => (i.assetInstanceId === cmd.instance.assetInstanceId ? cmd.instance : i))
        this.emit()
        return { ok: true, instance: cmd.instance, event: cmd.event }
    }

    // --- direct instance insertion (used by DEV fixtures + placement) ---
    /** Insert/replace an instance keyed by assetInstanceId ONLY. */
    insertInstance(instance: AssetInstance): void {
        this.instances = this.instances.filter((i) => i.assetInstanceId !== instance.assetInstanceId)
        this.instances.push(instance)
        this.emit()
    }

    /** Remove an instance by id (used to hide DEV fixtures / cancel uncommitted). */
    removeInstance(assetInstanceId: string): void {
        const before = this.instances.length
        this.instances = this.instances.filter((i) => i.assetInstanceId !== assetInstanceId)
        if (this.instances.length !== before) this.emit()
    }

    getInstance(assetInstanceId: string): AssetInstance | undefined {
        return this.instances.find((i) => i.assetInstanceId === assetInstanceId)
    }

    /** Count of instances (all projects). */
    get count(): number {
        return this.instances.length
    }

    /** Event descriptor emitter hook is the caller's responsibility; the store
     * returns the ASSET_PLACED event through completePlacementAt's result. This
     * accessor exists so tests can assert last-known event wiring if needed. */
    static isPlacedEvent(e: AssetJournalEvent | undefined): boolean {
        return e?.type === 'ASSET_PLACED'
    }
}

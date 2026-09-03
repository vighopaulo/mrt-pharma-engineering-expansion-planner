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
import { moveAssetTo, normalizeYawDegrees, removeAsset, rotateAsset, rotateAssetYawBy, type AssetJournalEvent } from './commands'
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
export type SpatialInteractionState = 'IDLE' | 'PLACING' | 'MOVING' | 'ROTATING'

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

/**
 * Transient preview transform used ONLY while a direct fluid drag is active.
 * It is never persisted, never serialized as project state, and never written
 * to the event journal. The authoritative committed transform stays on the
 * AssetInstance in the store until drag release.
 */
export interface DragPreview {
    assetInstanceId: string
    startPosition: SpatialPosition
    /** assetPosition - dragStartWorldPoint, so the grab point is preserved. */
    grabOffset: SpatialPosition
    previewPosition: SpatialPosition
}

export type DragCommitResult =
    | { ok: true; instance: AssetInstance; event: AssetJournalEvent }
    | { ok: false; reason: MoveFailure; message: string }

/**
 * Transient yaw preview used ONLY while an object-attached fluid rotation is
 * active. Never persisted, never serialized, never journaled. The authoritative
 * committed yaw stays on the AssetInstance until rotation release.
 */
export interface RotationPreview {
    assetInstanceId: string
    startYaw: number
    previewYaw: number
    /** World-space center the rotation pivots about (the instance position). */
    center: SpatialPosition
}

export type RotationCommitResult =
    | { ok: true; instance: AssetInstance; event: AssetJournalEvent }
    | { ok: false; reason: RotateFailure; message: string }

export type DeleteResult =
    | { ok: true; removedInstanceId: string; event: AssetJournalEvent }
    | { ok: false; reason: DeleteFailure; message: string }

export type DeleteFailure =
    | 'ASSET_NOT_FOUND'
    | 'INTERACTION_ACTIVE'
    | 'DELETE_NOT_ALLOWED_FOR_SOURCE'

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
    /** Active fluid-drag preview (transient), if any. */
    dragPreview: DragPreview | undefined
    dragActive: boolean
    /** Active object-attached rotation preview (transient), if any. */
    rotationPreview: RotationPreview | undefined
    rotationActive: boolean
}

export class SpatialAssetStore {
    private readonly registry: AssetRegistry = createSeedRegistry()
    private readonly idGen = new InstanceIdGenerator()
    private instances: AssetInstance[] = []
    private intent: PlacementIntent | undefined
    private moveIntent: MoveIntent | undefined
    private dragPreview: DragPreview | undefined
    private rotationPreview: RotationPreview | undefined
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

    /** The single mutually-exclusive interaction state. A fluid drag counts as
     * MOVING (so command-move/placement cannot start mid-drag). */
    getInteractionState(): SpatialInteractionState {
        if (this.intent !== undefined) return 'PLACING'
        if (this.rotationPreview !== undefined) return 'ROTATING'
        if (this.moveIntent !== undefined || this.dragPreview !== undefined) return 'MOVING'
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
            dragPreview: this.dragPreview,
            dragActive: this.dragPreview !== undefined,
            rotationPreview: this.rotationPreview,
            rotationActive: this.rotationPreview !== undefined,
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

    // --- direct fluid drag (transient preview; ONE commit on release) ---
    /**
     * Begin a fluid drag of an instance. Records the grab offset so the grab
     * point under the cursor is preserved. Rejected if any interaction is
     * already active. The authoritative AssetInstance transform is NOT changed
     * here — only a transient preview is created.
     */
    beginDrag(assetInstanceId: string, grabWorldPoint: SpatialPosition): { ok: true; preview: DragPreview } | { ok: false; reason: MoveFailure } {
        if (this.getInteractionState() !== 'IDLE') {
            return { ok: false, reason: 'SPATIAL_INTERACTION_ALREADY_ACTIVE' }
        }
        const inst = this.getInstance(assetInstanceId)
        if (!inst) return { ok: false, reason: 'ASSET_NOT_FOUND' }
        const start = { ...inst.transform.position }
        const grabOffset = {
            x: start.x - grabWorldPoint.x,
            y: start.y - grabWorldPoint.y,
            z: 0, // Z is preserved during fluid drag (X/Y movement only).
        }
        this.dragPreview = { assetInstanceId, startPosition: start, grabOffset, previewPosition: start }
        // Selection follows the drag target.
        this.selectedId = assetInstanceId
        this.emit()
        return { ok: true, preview: this.dragPreview }
    }

    isDragActive(): boolean {
        return this.dragPreview !== undefined
    }

    getDragPreview(): DragPreview | undefined {
        return this.dragPreview
    }

    /**
     * Update the transient preview position from a drag world point. Preserves
     * the start Z (fluid X/Y drag) and applies the grab offset. Does NOT emit a
     * domain event and does NOT change the committed AssetInstance.
     */
    updateDragPreview(dragWorldPoint: SpatialPosition): void {
        const dp = this.dragPreview
        if (!dp) return
        const previewPosition: SpatialPosition = {
            x: dragWorldPoint.x + dp.grabOffset.x,
            y: dragWorldPoint.y + dp.grabOffset.y,
            z: dp.startPosition.z, // preserve start Z
        }
        this.dragPreview = { ...dp, previewPosition }
        this.emit()
    }

    /**
     * Commit the active drag: exactly ONE authoritative move transition + ONE
     * ASSET_MOVED event. Identity and rotation preserved. Clears the preview.
     * If the preview position equals the start (no real movement) it is treated
     * as a no-op commit failure so callers can decide (still clears preview).
     */
    commitDrag(): DragCommitResult {
        const dp = this.dragPreview
        if (!dp) return { ok: false, reason: 'MOVE_INTENT_INVALID', message: 'no active drag' }
        // Consume the preview up front so a duplicate release cannot double-commit.
        this.dragPreview = undefined

        const inst = this.getInstance(dp.assetInstanceId)
        if (!inst) {
            this.emit()
            return { ok: false, reason: 'ASSET_NOT_FOUND', message: `asset gone: ${dp.assetInstanceId}` }
        }
        const cmd = moveAssetTo(inst, dp.previewPosition)
        if (!cmd.ok) {
            this.emit()
            return { ok: false, reason: 'STORE_UPDATE_FAILED', message: cmd.errors.map((e) => `${e.field} ${e.message}`).join('; ') }
        }
        this.instances = this.instances.map((i) => (i.assetInstanceId === cmd.instance.assetInstanceId ? cmd.instance : i))
        this.emit()
        return { ok: true, instance: cmd.instance, event: cmd.event }
    }

    /** Cancel the active drag: discard the preview, no commit, no event. */
    cancelDrag(): void {
        if (this.dragPreview === undefined) return
        this.dragPreview = undefined
        this.emit()
    }

    // --- object-attached fluid yaw rotation (transient preview; ONE commit) ---
    /**
     * Begin an object-attached fluid rotation of an instance. Records the start
     * yaw and pivot center. Rejected if any interaction is already active. The
     * authoritative rotation is NOT changed here — only a transient preview.
     */
    beginRotate(assetInstanceId: string): { ok: true; preview: RotationPreview } | { ok: false; reason: RotateFailure } {
        if (this.getInteractionState() !== 'IDLE') {
            return { ok: false, reason: 'SPATIAL_INTERACTION_ALREADY_ACTIVE' }
        }
        const inst = this.getInstance(assetInstanceId)
        if (!inst) return { ok: false, reason: 'ASSET_NOT_FOUND' }
        const startYaw = normalizeYawDegrees(inst.transform.rotation.yaw)
        this.rotationPreview = {
            assetInstanceId,
            startYaw,
            previewYaw: startYaw,
            center: { ...inst.transform.position },
        }
        this.selectedId = assetInstanceId
        this.emit()
        return { ok: true, preview: this.rotationPreview }
    }

    isRotationActive(): boolean {
        return this.rotationPreview !== undefined
    }

    getRotationPreview(): RotationPreview | undefined {
        return this.rotationPreview
    }

    /**
     * Update the transient rotation preview to an absolute yaw (already computed
     * by the caller's angular math), normalized to [0, 360). Fluid — no event,
     * no committed change.
     */
    updateRotatePreview(previewYawDegrees: number): void {
        const rp = this.rotationPreview
        if (!rp) return
        if (!Number.isFinite(previewYawDegrees)) return // ignore invalid; keep last
        this.rotationPreview = { ...rp, previewYaw: normalizeYawDegrees(previewYawDegrees) }
        this.emit()
    }

    /**
     * Commit the active rotation: exactly ONE authoritative rotation transition
     * + ONE ASSET_ROTATED event. Position + identity preserved (yaw only).
     * Clears the preview.
     */
    commitRotate(): RotationCommitResult {
        const rp = this.rotationPreview
        if (!rp) return { ok: false, reason: 'ROTATION_INVALID', message: 'no active rotation' }
        this.rotationPreview = undefined // consume once

        const inst = this.getInstance(rp.assetInstanceId)
        if (!inst) {
            this.emit()
            return { ok: false, reason: 'ASSET_NOT_FOUND', message: `asset gone: ${rp.assetInstanceId}` }
        }
        const rotation: SpatialRotation = {
            yaw: normalizeYawDegrees(rp.previewYaw),
            pitch: inst.transform.rotation.pitch,
            roll: inst.transform.rotation.roll,
        }
        const cmd = rotateAsset(inst, rotation)
        if (!cmd.ok) {
            this.emit()
            return { ok: false, reason: 'ROTATION_INVALID', message: cmd.errors.map((e) => `${e.field} ${e.message}`).join('; ') }
        }
        this.instances = this.instances.map((i) => (i.assetInstanceId === cmd.instance.assetInstanceId ? cmd.instance : i))
        this.emit()
        return { ok: true, instance: cmd.instance, event: cmd.event }
    }

    /** Cancel the active rotation: discard preview, restore committed yaw, no event. */
    cancelRotate(): void {
        if (this.rotationPreview === undefined) return
        this.rotationPreview = undefined
        this.emit()
    }

    // --- controlled single-asset delete ---
    /**
     * Remove ONE application-owned instance from the store. Only USER_PLACED
     * instances are deletable through the product path (DEV fixtures excluded).
     * Rejected while any interaction is active. Emits ONE ASSET_REMOVED,
     * preserves the shared definition/geometry/catalog and all other instances,
     * clears selection if the deleted instance was selected. Never touches the
     * iModel.
     */
    deleteAsset(assetInstanceId: string): DeleteResult {
        if (this.getInteractionState() !== 'IDLE') {
            return { ok: false, reason: 'INTERACTION_ACTIVE', message: `interaction active: ${this.getInteractionState()}` }
        }
        const inst = this.getInstance(assetInstanceId)
        if (!inst) return { ok: false, reason: 'ASSET_NOT_FOUND', message: `asset not found: ${assetInstanceId}` }
        if (inst.spatialSource !== 'USER_PLACED') {
            return { ok: false, reason: 'DELETE_NOT_ALLOWED_FOR_SOURCE', message: `delete allowed only for USER_PLACED; got ${inst.spatialSource}` }
        }
        const removed = removeAsset(inst) // structured ASSET_REMOVED descriptor
        // Enrich the event with prior transform/scenario for the journal.
        const event: AssetJournalEvent = {
            type: 'ASSET_REMOVED',
            assetInstanceId: inst.assetInstanceId,
            projectId: inst.projectId,
            detail: {
                assetDefinitionId: inst.assetDefinitionId,
                geometryRepresentationId: inst.geometryRepresentationId,
                createdFrom: inst.createdFrom ?? '',
                priorX: inst.transform.position.x, priorY: inst.transform.position.y, priorZ: inst.transform.position.z,
                priorYaw: inst.transform.rotation.yaw,
                scenarioId: inst.scenario?.scenarioId ?? '',
                scenarioState: inst.scenario?.scenarioState ?? '',
            },
        }
        this.instances = this.instances.filter((i) => i.assetInstanceId !== assetInstanceId)
        if (this.selectedId === assetInstanceId) this.selectedId = undefined
        this.emit()
        return { ok: true, removedInstanceId: removed.ok ? removed.removedInstanceId : assetInstanceId, event }
    }

    /**
     * Instances with the active transient preview applied to the active instance
     * (what the overlay renders): drag preview → position; rotation preview →
     * yaw. Only one preview can be active at a time. Non-active instances use
     * their committed transforms.
     */
    getEffectiveProjectInstances(): readonly AssetInstance[] {
        const dp = this.dragPreview
        const rp = this.rotationPreview
        const base = this.getProjectInstances()
        if (!dp && !rp) return base
        return base.map((i) => {
            if (dp && i.assetInstanceId === dp.assetInstanceId) {
                return { ...i, transform: { ...i.transform, position: dp.previewPosition } }
            }
            if (rp && i.assetInstanceId === rp.assetInstanceId) {
                return { ...i, transform: { ...i.transform, rotation: { ...i.transform.rotation, yaw: rp.previewYaw } } }
            }
            return i
        })
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

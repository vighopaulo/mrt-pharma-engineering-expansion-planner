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
import type { AssetJournalEvent } from './commands'
import type { AssetInstance, ScenarioProvenance, SpatialPosition, SpatialRotation } from './types'

export interface SpatialAssetStoreOptions {
    projectId: string
    scenario: ScenarioProvenance
}

export type StoreListener = () => void

/** Public read-only snapshot for UI consumers (stable per version). */
export interface SpatialAssetSnapshot {
    version: number
    projectId: string
    instances: readonly AssetInstance[]
    placementIntent: PlacementIntent | undefined
    placementModeActive: boolean
}

export class SpatialAssetStore {
    private readonly registry: AssetRegistry = createSeedRegistry()
    private readonly idGen = new InstanceIdGenerator()
    private instances: AssetInstance[] = []
    private intent: PlacementIntent | undefined
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

    private computeSnapshot(): SpatialAssetSnapshot {
        return {
            version: this.version,
            projectId: this.projectId,
            instances: this.instances.slice(),
            placementIntent: this.intent,
            placementModeActive: this.intent !== undefined,
        }
    }

    private emit(): void {
        this.version += 1
        this.snapshot = this.computeSnapshot()
        for (const l of this.listeners) l()
    }

    // --- placement intent lifecycle ---
    /** Enter placement mode with a resolved intent (no instance created yet). */
    beginPlacement(intent: PlacementIntent): void {
        this.intent = intent
        this.emit()
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

/**
 * spatialAssetOverlay — bounded controller that owns the MRT Pharma spatial
 * asset overlay lifecycle inside the live Bentley viewport.
 *
 * Responsibilities:
 *  - own the ONE application-owned SpatialAssetStore (source of truth) for the
 *    active dev-viewer project/scenario;
 *  - register exactly ONE SpatialAssetDecorator with the viewManager;
 *  - build the generic + catalog PET/CT proof fixtures from the live model range;
 *  - drive product placement (Asset Library → placement tool → store);
 *  - show / hide / inspect for the DEV controls.
 *
 * It does NOT modify the iModel, ViewFlags, camera, or transparency. The
 * decorator uses cached decorations, so nothing churns while idle.
 *
 * LIFECYCLE INVARIANT (preserved from the previous checkpoint correction):
 *   decorator registration lifecycle != asset instance state lifecycle.
 * disposeOverlay() only detaches the Bentley decorator; the store (and its
 * placed instances) survives a transient detach/re-attach (React StrictMode
 * mount→cleanup→mount, or viewer remount). The store is a module singleton so
 * placed equipment is never wiped by a remount.
 */
import { IModelApp } from '@itwin/core-frontend'
import { SpatialAssetDecorator } from './SpatialAssetDecorator'
import {
    buildGeDiscoveryMiCatalogTestAsset,
    buildGenericPetCtTestAsset,
    buildPlacementIntent,
    buildPetCtAssetLibrary,
    CATALOG_TEST_ASSET_DEFINITION_ID,
    CATALOG_TEST_ASSET_INSTANCE_ID,
    GE_DISCOVERY_MI_RECORD,
    serializeAssetInstance,
    SpatialAssetStore,
    TEST_PROJECT_ID,
    type AssetInstance,
    type AssetLibraryEntry,
    type ModelNeighborhood,
    type ScenarioProvenance,
    type StoreListener,
} from '../../domain/assets'

/** Fixed dev scenario provenance (preserves LOCKDOWN / What-If compatibility). */
const DEV_SCENARIO: ScenarioProvenance = { scenarioId: 'MRT_DEV_SCENARIO', scenarioState: 'DRAFT' }

/**
 * The ONE application-owned spatial asset store. Module singleton so its
 * lifetime is independent of any React component or the Bentley decorator — a
 * viewer/decorator remount never resets it.
 */
export const spatialAssetStore = new SpatialAssetStore({ projectId: TEST_PROJECT_ID, scenario: DEV_SCENARIO })

let decorator: SpatialAssetDecorator | undefined
let removeDecorator: (() => void) | undefined

/** Subscribe to store changes (product UI observability). */
export function subscribeSpatialAssets(listener: StoreListener): () => void {
    return spatialAssetStore.subscribe(listener)
}

/** Register the decorator once. Safe to call repeatedly (idempotent). */
export function ensureDecoratorRegistered(): void {
    if (decorator && removeDecorator) return
    if (!decorator) {
        decorator = new SpatialAssetDecorator(
            // Render the transient preview transform (position or yaw) for the
            // active instance; committed transforms for all others.
            () => spatialAssetStore.getEffectiveProjectInstances(),
            () => spatialAssetStore.getSnapshot().selectedAssetInstanceId,
            // Disable decoration caching while a drag is active so the moving
            // scanner is rebuilt from the preview transform every frame.
            () => spatialAssetStore.isDragActive(),
            // Same for an active rotation preview.
            () => spatialAssetStore.isRotationActive(),
        )
    }
    removeDecorator = IModelApp.viewManager.addDecorator(decorator)
}

/** Resolve a Bentley BODY pick id (HitDetail.sourceId) to an asset id. */
export function assetIdForPickId(pickId: string): string | undefined {
    return decorator?.assetIdForPickId(pickId)
}

/** Resolve a Bentley ROTATION HANDLE pick id to its asset id. */
export function handleAssetIdForPickId(pickId: string): string | undefined {
    return decorator?.handleAssetIdForPickId(pickId)
}

/** The registered decorator (for the direct-manipulation tool's redraw hook). */
export function getSpatialDecorator(): SpatialAssetDecorator | undefined {
    return decorator
}

/**
 * Detach the decorator from the viewManager (Bentley cleanup on viewer unmount).
 *
 * IMPORTANT: this does NOT clear the application-owned store. The decorator is a
 * rendering attachment; the store's domain state is authoritative and must
 * survive a transient detach/re-attach. Re-registration reuses the same
 * decorator + the retained store instances.
 */
export function disposeOverlay(): void {
    if (removeDecorator) removeDecorator()
    removeDecorator = undefined
    // Keep `decorator` and the store so re-registration restores the overlay.
}

function invalidateDecorations(): void {
    const vp = IModelApp.viewManager?.selectedView
    if (!vp || !decorator) return
    if (spatialAssetStore.isDragActive() || spatialAssetStore.isRotationActive()) {
        // During a drag/rotation the decorator is NOT caching; force a plain
        // decoration redraw so the scanner follows the preview this frame.
        vp.invalidateDecorations()
    } else {
        // Idle: the decorator caches; invalidate the cache so the next frame
        // rebuilds (e.g. after a placement/move/rotate or drag commit/cancel).
        vp.invalidateCachedDecorations(decorator)
    }
}

/**
 * Wire the store so any change invalidates decorations. Registered once. This is
 * the ONLY sync between store state and Bentley rendering — event-driven, no
 * polling.
 */
let storeSyncBound = false
function bindStoreToDecorations(): void {
    if (storeSyncBound) return
    spatialAssetStore.subscribe(() => invalidateDecorations())
    storeSyncBound = true
}

/** Read the current model neighborhood (center + diagonal) from the live view. */
function currentNeighborhood(): ModelNeighborhood | undefined {
    const vp = IModelApp.viewManager?.selectedView
    if (!vp) return undefined
    const range = vp.view.computeFitRange()
    if (range.isNull) return undefined
    const c = range.center
    return { center: { x: c.x, y: c.y, z: c.z }, diagonal: range.diagonal().magnitude() }
}

export interface ShowResult {
    ok: boolean
    reason: string
    instanceId?: string
    serialized?: unknown
}

// ---------------------------------------------------------------------------
// DEV fixtures (architecture-proof; unchanged identity chains)
// ---------------------------------------------------------------------------

/** Build + show the ONE generic PET/CT proof asset near the model center. */
export function showGenericPetCt(): ShowResult {
    ensureDecoratorRegistered()
    bindStoreToDecorations()
    const neigh = currentNeighborhood()
    if (!neigh) return { ok: false, reason: 'NO_ACTIVE_VIEWPORT_OR_RANGE' }

    const { result } = buildGenericPetCtTestAsset(neigh)
    if (!result.ok) {
        return { ok: false, reason: 'BUILD_FAILED: ' + result.errors.map((e) => `${e.field} ${e.message}`).join('; ') }
    }
    spatialAssetStore.insertInstance(result.instance)

    if (import.meta.env.DEV) {
        console.info('[bentley-asset] SHOW instanceId=%s def=%s geo=%s label=%s pos=(%s,%s,%s)',
            result.instance.assetInstanceId, result.instance.assetDefinitionId, result.instance.geometryRepresentationId,
            result.instance.displayLabel,
            result.instance.transform.position.x.toFixed(2), result.instance.transform.position.y.toFixed(2),
            result.instance.transform.position.z.toFixed(2))
    }
    return { ok: true, reason: 'SHOWN', instanceId: result.instance.assetInstanceId, serialized: serializeAssetInstance(result.instance) }
}

/** Build + show the catalog-backed GE Discovery MI PET/CT proof asset. */
export function showCatalogPetCt(): ShowResult {
    ensureDecoratorRegistered()
    bindStoreToDecorations()
    const neigh = currentNeighborhood()
    if (!neigh) return { ok: false, reason: 'NO_ACTIVE_VIEWPORT_OR_RANGE' }

    const before = spatialAssetStore.count
    const { result } = buildGeDiscoveryMiCatalogTestAsset(neigh)
    if (!result.ok) {
        if (import.meta.env.DEV) {
            console.error('[catalog-asset] FAILURE_STAGE=build FAILURE_CODE=%s message=%s', result.reason, result.message)
        }
        return { ok: false, reason: `${result.reason}: ${result.message}` }
    }

    // Dedupe by assetInstanceId ONLY (store enforces this) so the generic and
    // catalog scanners coexist despite sharing GENERIC_PET_CT_SCANNER_V1.
    spatialAssetStore.insertInstance(result.instance)

    const present = spatialAssetStore.getInstance(result.instance.assetInstanceId) !== undefined
    if (import.meta.env.DEV) {
        console.info('[catalog-asset] CATALOG_RECORD_FOUND=YES CATALOG_RECORD_ID=GE_DISCOVERY_MI ADAPTER_RESULT=SUCCESS ASSET_DEFINITION_ID=%s ASSET_FAMILY=%s GEOMETRY_RESOLUTION=%s DIMENSION_PROVENANCE=%s INSTANCE_CREATION=SUCCESS INSTANCE_ID=%s OVERLAY_INSTANCE_COUNT_BEFORE=%d OVERLAY_INSTANCE_COUNT_AFTER=%d OVERLAY_INSERTION=%s',
            result.instance.assetDefinitionId, result.definition.assetFamily, result.instance.geometryRepresentationId,
            result.instance.dimensions.provenance, result.instance.assetInstanceId, before, spatialAssetStore.count, present ? 'SUCCESS' : 'FAILED')
    }
    return { ok: true, reason: 'SHOWN', instanceId: result.instance.assetInstanceId, serialized: serializeAssetInstance(result.instance) }
}

/** Remove the catalog-backed fixture instance only. */
export function hideCatalogPetCt(): void {
    spatialAssetStore.removeInstance(CATALOG_TEST_ASSET_INSTANCE_ID)
    if (import.meta.env.DEV) console.info('[bentley-asset] HIDE_CATALOG')
}

function summarize(inst: AssetInstance): string {
    return [
        `assetInstanceId=${inst.assetInstanceId}`,
        `displayLabel=${inst.displayLabel}`,
        `assetDefinitionId=${inst.assetDefinitionId}`,
        `geometryRepresentationId=${inst.geometryRepresentationId}`,
        `createdFrom=${inst.createdFrom ?? '—'}`,
        `dims=${inst.dimensions.width}x${inst.dimensions.depth}x${inst.dimensions.height}${inst.dimensions.unit}`,
        `dimProvenance=${inst.dimensions.provenance}`,
        `pos=(${inst.transform.position.x.toFixed(2)},${inst.transform.position.y.toFixed(2)},${inst.transform.position.z.toFixed(2)})`,
        `rot=(yaw=${inst.transform.rotation.yaw},pitch=${inst.transform.rotation.pitch},roll=${inst.transform.rotation.roll})`,
        `room=${inst.roomAssignment.state}`,
        `state=${inst.installationState}`,
        `source=${inst.spatialSource}`,
        `scenario=${inst.scenario?.scenarioId ?? '—'}/${inst.scenario?.scenarioState ?? '—'}`,
    ].join(' | ')
}

/** Sanitized metadata for the catalog-backed fixture instance. */
export function inspectCatalogPetCt(): string {
    const inst = spatialAssetStore.getInstance(CATALOG_TEST_ASSET_INSTANCE_ID)
    if (!inst) return 'NO_CATALOG_ASSET_PLACED'
    const summary = summarize(inst)
    if (import.meta.env.DEV) console.info('[bentley-asset] INSPECT_CATALOG %s', summary)
    return summary
}

/** Remove the generic fixture instance (hide). */
export function hideGenericPetCt(): void {
    spatialAssetStore.removeInstance('PETCT-TEST-01')
    if (import.meta.env.DEV) console.info('[bentley-asset] HIDE')
}

/** Return sanitized metadata for the generic proof instance (inspection). */
export function inspectGenericPetCt(): string {
    const inst = spatialAssetStore.getInstance('PETCT-TEST-01') ?? spatialAssetStore.getProjectInstances()[0]
    if (!inst) return 'NO_ASSET_PLACED'
    const summary = summarize(inst)
    if (import.meta.env.DEV) console.info('[bentley-asset] INSPECT %s', summary)
    return summary
}

// ---------------------------------------------------------------------------
// PRODUCT: Asset Library + controlled placement
// ---------------------------------------------------------------------------

/**
 * The PET/CT-scoped Asset Library derived from the authoritative catalog
 * records available to the frontend. Currently the REPOSITORY_SOURCE_DERIVED
 * GE Discovery MI record. Geometry availability is resolved via the store's
 * registry.
 */
export function getAssetLibrary(): AssetLibraryEntry[] {
    return buildPetCtAssetLibrary([GE_DISCOVERY_MI_RECORD], spatialAssetStore.getRegistry())
}

export interface EnterPlacementResult {
    ok: boolean
    reason: string
    intentSummary?: string
}

/**
 * Enter placement mode for a library entry. Builds a PlacementIntent (no
 * instance yet) and starts the bounded Bentley placement tool. Selecting an
 * entry does not place anything — only PLACE enters this mode.
 */
export async function beginPlacementForLibraryEntry(entry: AssetLibraryEntry): Promise<EnterPlacementResult> {
    if (entry.catalogRecordId !== GE_DISCOVERY_MI_RECORD.catalogRecordId) {
        return { ok: false, reason: `UNSUPPORTED_LIBRARY_ENTRY: ${entry.catalogRecordId}` }
    }
    ensureDecoratorRegistered()
    bindStoreToDecorations()

    const intentRes = buildPlacementIntent({
        record: GE_DISCOVERY_MI_RECORD,
        assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID,
        registry: spatialAssetStore.getRegistry(),
    })
    if (!intentRes.ok) {
        return { ok: false, reason: `${intentRes.reason}: ${intentRes.message}` }
    }
    const began = spatialAssetStore.beginPlacement(intentRes.intent)
    if (!began.ok) {
        return { ok: false, reason: began.reason }
    }

    if (import.meta.env.DEV) {
        console.info('[mrt-placement] PLACEMENT_MODE_ENTERED catalogRecordId=%s assetDefinitionId=%s geometryRepresentationId=%s displayLabel=%s assetFamily=%s',
            intentRes.intent.catalogRecordId, intentRes.intent.assetDefinitionId, intentRes.intent.resolvedGeometryRepresentationId,
            intentRes.intent.displayLabel, intentRes.intent.assetFamily)
    }

    // Start the bounded Bentley placement tool (dynamic import to keep tool
    // registration out of the offline bundle).
    const { runMrtAssetPlacementTool } = await import('./MrtAssetPlacementTool')
    const started = await runMrtAssetPlacementTool()
    if (!started) {
        // Could not start the tool; roll back placement mode.
        spatialAssetStore.cancelPlacement()
        return { ok: false, reason: 'NO_ACTIVE_VIEWPORT' }
    }

    const intent = intentRes.intent
    return {
        ok: true,
        reason: 'PLACEMENT_MODE_ACTIVE',
        intentSummary: `catalogRecordId=${intent.catalogRecordId} assetDefinitionId=${intent.assetDefinitionId} geometryRepresentationId=${intent.resolvedGeometryRepresentationId} displayLabel=${intent.displayLabel} assetFamily=${intent.assetFamily}`,
    }
}

/** Cancel the active placement (from a UI Cancel button). */
export async function cancelPlacement(): Promise<void> {
    spatialAssetStore.cancelPlacement()
    // Ask the tool to exit if it is running.
    try {
        const { exitMrtAssetPlacementTool } = await import('./MrtAssetPlacementTool')
        await exitMrtAssetPlacementTool()
    } catch {
        // tool module not loaded — nothing to exit.
    }
    if (import.meta.env.DEV) console.info('[mrt-placement] PLACEMENT_MODE_EXITED reason=CANCELLED')
}

/** DEV diagnostic: bounded snapshot of the active placement intent. */
export function inspectPlacementIntent(): string {
    const intent = spatialAssetStore.getActiveIntent()
    if (!intent) return 'PLACEMENT_INTENT_ACTIVE=NO'
    return [
        'PLACEMENT_INTENT_ACTIVE=YES',
        `catalogRecordId=${intent.catalogRecordId}`,
        `assetDefinitionId=${intent.assetDefinitionId}`,
        `geometryRepresentationId=${intent.resolvedGeometryRepresentationId}`,
        `displayLabel=${intent.displayLabel}`,
        `assetFamily=${intent.assetFamily}`,
    ].join(' | ')
}

/** Product inspection for any placed asset (by id). */
export function inspectPlacedAsset(assetInstanceId: string): string {
    const inst = spatialAssetStore.getInstance(assetInstanceId)
    if (!inst) return `NOT_FOUND: ${assetInstanceId}`
    return summarize(inst)
}

// ---------------------------------------------------------------------------
// PRODUCT: controlled MOVE + ROTATE of an existing asset
// ---------------------------------------------------------------------------

/** Select an existing placed asset (product selection). */
export function selectAsset(assetInstanceId: string | undefined): void {
    spatialAssetStore.selectAsset(assetInstanceId)
}

export interface BeginMoveResult {
    ok: boolean
    reason: string
}

/**
 * Enter MOVE mode for an existing instance and start the bounded Bentley move
 * tool. Bound to the given assetInstanceId for the whole move. Rejected if any
 * spatial interaction is already active (mutual exclusivity).
 */
export async function beginMoveForAsset(assetInstanceId: string): Promise<BeginMoveResult> {
    ensureDecoratorRegistered()
    bindStoreToDecorations()

    const began = spatialAssetStore.beginMove(assetInstanceId)
    if (!began.ok) {
        return { ok: false, reason: began.reason }
    }
    if (import.meta.env.DEV) {
        console.info('[mrt-move] MOVE_MODE_ENTERED assetInstanceId=%s previousPosition=(%s,%s,%s)',
            began.intent.assetInstanceId, began.intent.previousPosition.x.toFixed(2),
            began.intent.previousPosition.y.toFixed(2), began.intent.previousPosition.z.toFixed(2))
    }

    const { runMrtAssetMoveTool } = await import('./MrtAssetMoveTool')
    const started = await runMrtAssetMoveTool()
    if (!started) {
        spatialAssetStore.cancelMove()
        return { ok: false, reason: 'NO_ACTIVE_VIEWPORT' }
    }
    return { ok: true, reason: 'MOVE_MODE_ACTIVE' }
}

/** Cancel the active move (from a UI Cancel button). */
export async function cancelMove(): Promise<void> {
    spatialAssetStore.cancelMove()
    try {
        const { exitMrtAssetMoveTool } = await import('./MrtAssetMoveTool')
        await exitMrtAssetMoveTool()
    } catch {
        // tool module not loaded — nothing to exit.
    }
    if (import.meta.env.DEV) console.info('[mrt-move] MOVE_MODE_EXITED reason=CANCELLED')
}

export interface RotateResultSummary {
    ok: boolean
    reason: string
    yaw?: number
    assetInstanceId?: string
}

// ---------------------------------------------------------------------------
// PRODUCT: direct object selection + fluid drag (used by the Bentley tool)
// ---------------------------------------------------------------------------

/** Resolve a Bentley pick id to an asset and select it (direct object select). */
export function selectByPickId(pickId: string): string | undefined {
    const assetId = assetIdForPickId(pickId)
    if (assetId) {
        spatialAssetStore.selectAsset(assetId)
        if (import.meta.env.DEV) console.info('[mrt-direct] DIRECT_SELECT assetInstanceId=%s', assetId)
    }
    return assetId
}

/** Begin a fluid drag of an asset at a grab world point. */
export function beginDrag(assetInstanceId: string, grabWorldPoint: { x: number; y: number; z: number }): boolean {
    dragDiagCount = 0
    const r = spatialAssetStore.beginDrag(assetInstanceId, grabWorldPoint)
    if (r.ok && import.meta.env.DEV) {
        console.info('[mrt-direct] DRAG_START assetInstanceId=%s grab=(%s,%s,%s)', assetInstanceId,
            grabWorldPoint.x.toFixed(2), grabWorldPoint.y.toFixed(2), grabWorldPoint.z.toFixed(2))
    }
    return r.ok
}

let dragDiagCount = 0

/** Update the transient drag preview (no event, no committed change). */
export function updateDragPreview(dragWorldPoint: { x: number; y: number; z: number }): void {
    spatialAssetStore.updateDragPreview(dragWorldPoint)
    // Bounded DEV diagnostic: sample only the first few preview updates per drag
    // (never every frame indefinitely) so the preview pipeline can be verified.
    if (import.meta.env.DEV && dragDiagCount < 5) {
        const dp = spatialAssetStore.getDragPreview()
        const eff = spatialAssetStore.getEffectiveProjectInstances().find((i) => i.assetInstanceId === dp?.assetInstanceId)
        const committed = dp ? spatialAssetStore.getInstance(dp.assetInstanceId) : undefined
        if (dp && eff && committed) {
            dragDiagCount += 1
            const c = committed.transform.position, p = dp.previewPosition, e = eff.transform.position
            console.info('[drag-preview] assetInstanceId=%s committed=(%s,%s,%s) preview=(%s,%s,%s) effective=(%s,%s,%s) previewActive=true',
                dp.assetInstanceId, c.x.toFixed(2), c.y.toFixed(2), c.z.toFixed(2),
                p.x.toFixed(2), p.y.toFixed(2), p.z.toFixed(2), e.x.toFixed(2), e.y.toFixed(2), e.z.toFixed(2))
        }
    }
}

/** Commit the active drag: ONE authoritative move + ONE ASSET_MOVED. */
export function commitDrag(): { ok: boolean; reason: string; assetInstanceId?: string } {
    const r = spatialAssetStore.commitDrag()
    if (!r.ok) {
        if (import.meta.env.DEV) console.info('[mrt-direct] DRAG_COMMIT_SKIPPED reason=%s', r.reason)
        return { ok: false, reason: r.reason }
    }
    if (import.meta.env.DEV) {
        const p = r.instance.transform.position
        console.info('[mrt-direct] DRAG_COMMIT assetInstanceId=%s pos=(%s,%s,%s) ASSET_MOVED=1',
            r.instance.assetInstanceId, p.x.toFixed(2), p.y.toFixed(2), p.z.toFixed(2))
    }
    return { ok: true, reason: 'COMMITTED', assetInstanceId: r.instance.assetInstanceId }
}

/** Cancel the active drag: discard preview, restore committed position. */
export function cancelDrag(): void {
    spatialAssetStore.cancelDrag()
    if (import.meta.env.DEV) console.info('[mrt-direct] DRAG_CANCELLED')
}

// --- object-attached fluid rotation ---
/** Begin an object-attached fluid rotation of an asset. */
export function beginRotate(assetInstanceId: string): boolean {
    const r = spatialAssetStore.beginRotate(assetInstanceId)
    if (r.ok && import.meta.env.DEV) console.info('[mrt-rotate] ROTATE_START assetInstanceId=%s startYaw=%s', assetInstanceId, r.preview.startYaw)
    return r.ok
}

/** Update the transient rotation preview to an absolute yaw (degrees). */
export function updateRotatePreview(previewYawDegrees: number): void {
    spatialAssetStore.updateRotatePreview(previewYawDegrees)
}

/** Commit the active rotation: ONE authoritative rotate + ONE ASSET_ROTATED. */
export function commitRotate(): { ok: boolean; reason: string; yaw?: number; assetInstanceId?: string } {
    const r = spatialAssetStore.commitRotate()
    if (!r.ok) {
        if (import.meta.env.DEV) console.info('[mrt-rotate] ROTATE_COMMIT_SKIPPED reason=%s', r.reason)
        return { ok: false, reason: r.reason }
    }
    if (import.meta.env.DEV) console.info('[mrt-rotate] ROTATE_COMMIT assetInstanceId=%s yaw=%s ASSET_ROTATED=1', r.instance.assetInstanceId, r.instance.transform.rotation.yaw)
    return { ok: true, reason: 'COMMITTED', yaw: r.instance.transform.rotation.yaw, assetInstanceId: r.instance.assetInstanceId }
}

/** Cancel the active rotation: discard preview, restore committed yaw. */
export function cancelRotate(): void {
    spatialAssetStore.cancelRotate()
    if (import.meta.env.DEV) console.info('[mrt-rotate] ROTATE_CANCELLED')
}

// --- controlled delete ---
export interface DeleteAssetResult {
    ok: boolean
    reason: string
    removedInstanceId?: string
}

/** Delete the given USER_PLACED asset (product delete). One ASSET_REMOVED. */
export function deleteAsset(assetInstanceId: string): DeleteAssetResult {
    const r = spatialAssetStore.deleteAsset(assetInstanceId)
    if (!r.ok) {
        if (import.meta.env.DEV) console.error('[mrt-delete] DELETE_FAILED reason=%s message=%s', r.reason, r.message)
        return { ok: false, reason: r.reason }
    }
    if (import.meta.env.DEV) console.info('[mrt-delete] ASSET_REMOVED assetInstanceId=%s', r.removedInstanceId)
    return { ok: true, reason: 'REMOVED', removedInstanceId: r.removedInstanceId }
}

/** DEV: read-only rotation-state inspection. */
export function inspectRotationState(): string {
    const snap = spatialAssetStore.getSnapshot()
    const rp = snap.rotationPreview
    const committed = rp ? spatialAssetStore.getInstance(rp.assetInstanceId) : spatialAssetStore.getSelectedInstance()
    const summary = [
        `activeTool=${IModelApp.toolAdmin?.activeTool?.toolId ?? '—'}`,
        `selected=${snap.selectedAssetInstanceId ?? '—'}`,
        `interaction=${snap.interaction}`,
        `rotationActive=${snap.rotationActive}`,
        `committedYaw=${committed ? committed.transform.rotation.yaw : '—'}`,
        `previewYaw=${rp ? rp.previewYaw.toFixed(1) : '—'}`,
    ].join(' | ')
    if (import.meta.env.DEV) console.info('[rotation-inspect] %s', summary)
    return summary
}

/**
 * Read-only DEV inspector for the direct-drag interaction state. Reports the
 * active Bentley tool id, selection, interaction, and committed/preview/
 * effective positions of the drag target. Mutates nothing.
 */
export function inspectDirectDragState(): string {
    const snap = spatialAssetStore.getSnapshot()
    const dp = snap.dragPreview
    const committed = dp ? spatialAssetStore.getInstance(dp.assetInstanceId) : undefined
    const eff = dp ? spatialAssetStore.getEffectiveProjectInstances().find((i) => i.assetInstanceId === dp.assetInstanceId) : undefined
    const activeToolId = IModelApp.toolAdmin?.activeTool?.toolId ?? '—'
    const c = committed?.transform.position
    const e = eff?.transform.position
    const summary = [
        `activeTool=${activeToolId}`,
        `selected=${snap.selectedAssetInstanceId ?? '—'}`,
        `interaction=${snap.interaction}`,
        `dragActive=${snap.dragActive}`,
        `dragTarget=${dp?.assetInstanceId ?? '—'}`,
        `committed=${c ? `(${c.x.toFixed(2)},${c.y.toFixed(2)},${c.z.toFixed(2)})` : '—'}`,
        `preview=${dp ? `(${dp.previewPosition.x.toFixed(2)},${dp.previewPosition.y.toFixed(2)},${dp.previewPosition.z.toFixed(2)})` : '—'}`,
        `effective=${e ? `(${e.x.toFixed(2)},${e.y.toFixed(2)},${e.z.toFixed(2)})` : '—'}`,
    ].join(' | ')
    if (import.meta.env.DEV) console.info('[direct-inspect] %s', summary)
    return summary
}

/**
 * Ensure the decorator is registered, store-decoration sync bound, and the
 * bounded direct-manipulation tool is running so clicking a scanner selects it
 * and dragging moves it. Idempotent — safe to call repeatedly (StrictMode-safe).
 * Returns whether the tool is active.
 */
export async function ensureDirectManipulationReady(): Promise<boolean> {
    ensureDecoratorRegistered()
    bindStoreToDecorations()
    // Do not steal the viewport from an active placement/move tool.
    if (spatialAssetStore.getInteractionState() !== 'IDLE') return false
    try {
        const { runMrtDirectManipulationTool } = await import('./MrtDirectManipulationTool')
        return await runMrtDirectManipulationTool()
    } catch {
        return false
    }
}

/** Rotate the given asset's yaw by a controlled step (±90°). Immediate. */
export function rotateAssetYaw(assetInstanceId: string, deltaDegrees: number): RotateResultSummary {
    const r = spatialAssetStore.rotateAssetYaw(assetInstanceId, deltaDegrees)
    if (!r.ok) {
        if (import.meta.env.DEV) console.error('[mrt-rotate] ROTATE_FAILED reason=%s message=%s', r.reason, r.message)
        return { ok: false, reason: r.reason }
    }
    if (import.meta.env.DEV) {
        console.info('[mrt-rotate] ASSET_ROTATED assetInstanceId=%s newYaw=%s',
            r.instance.assetInstanceId, r.instance.transform.rotation.yaw)
    }
    return { ok: true, reason: 'ROTATED', yaw: r.instance.transform.rotation.yaw, assetInstanceId: r.instance.assetInstanceId }
}

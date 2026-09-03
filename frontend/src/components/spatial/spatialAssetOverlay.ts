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
import { resolveDecorationRedrawPolicy } from './assetPicking'
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

/**
 * UI-only rotation-handle hover flag. The manipulation tool sets this when the
 * pointer is near the selected asset's rotation ring so the decorator can raise
 * the faint idle handle to a subtle HOVER prominence. Not authoritative state.
 */
let rotationHandleHover = false
export function setRotationHandleHover(hover: boolean): void {
    if (rotationHandleHover === hover) return
    rotationHandleHover = hover
    // Trigger a redraw so the hover prominence updates.
    const vp = IModelApp.viewManager?.selectedView
    vp?.invalidateDecorations()
}

/**
 * UI-only right-click asset context-menu state. The manipulation tool opens it
 * with a concrete assetInstanceId + screen position; the React panel subscribes
 * and renders it. Not authoritative domain state; never stored in the domain.
 */
export interface AssetContextMenuState {
    assetInstanceId: string
    screenX: number
    screenY: number
}
let contextMenu: AssetContextMenuState | undefined
const contextMenuListeners = new Set<() => void>()
export function subscribeContextMenu(listener: () => void): () => void {
    contextMenuListeners.add(listener)
    return () => { contextMenuListeners.delete(listener) }
}
export function getContextMenu(): AssetContextMenuState | undefined {
    return contextMenu
}
export function openAssetContextMenu(state: AssetContextMenuState): void {
    contextMenu = state
    for (const l of contextMenuListeners) l()
}
export function closeAssetContextMenu(): void {
    if (!contextMenu) return
    contextMenu = undefined
    for (const l of contextMenuListeners) l()
}

/**
 * UI-only marquee (bounding-box) selection rectangle state, in VIEW pixels. The
 * manipulation tool sets it during an empty-space primary drag; the React panel
 * renders a restrained rectangle. Not authoritative selection state — selection
 * updates on release through the store, keyed by assetInstanceId.
 */
export interface MarqueeRectState {
    startX: number
    startY: number
    currentX: number
    currentY: number
}
let marqueeRect: MarqueeRectState | undefined
const marqueeListeners = new Set<() => void>()
export function subscribeMarquee(listener: () => void): () => void {
    marqueeListeners.add(listener)
    return () => { marqueeListeners.delete(listener) }
}
export function getMarqueeRect(): MarqueeRectState | undefined {
    return marqueeRect
}
export function setMarqueeRect(rect: MarqueeRectState | undefined): void {
    marqueeRect = rect
    for (const l of marqueeListeners) l()
}

/**
 * Compute screen-space (view px) bounds for every application-owned project
 * AssetInstance by projecting the 8 corners of its yaw-transformed world bbox.
 * Used by the marquee to resolve intersecting assets. Returns app assets only
 * (DEV/catalog fixtures are USER-visible but their transforms come from the same
 * store; callers pass the project instances which are the app-owned set).
 */
export function computeAssetScreenBounds(): { assetInstanceId: string; bounds: import('./assetPicking').ScreenRect }[] {
    const vp = IModelApp.viewManager?.selectedView
    if (!vp) return []
    const DEG2RAD = Math.PI / 180
    const out: { assetInstanceId: string; bounds: import('./assetPicking').ScreenRect }[] = []
    for (const inst of spatialAssetStore.getProjectInstances()) {
        const p = inst.transform.position
        const s = inst.transform.scale
        const w = inst.dimensions.width * s.x
        const d = inst.dimensions.depth * s.y
        const h = inst.dimensions.height * s.z
        const yaw = inst.transform.rotation.yaw * DEG2RAD
        const cos = Math.cos(yaw), sin = Math.sin(yaw)
        const hx = w / 2, hy = d / 2
        // 8 corners of the local bbox (z from p.z .. p.z+h), yaw-rotated about center.
        const corners: [number, number, number][] = []
        for (const sx of [-hx, hx]) for (const sy of [-hy, hy]) for (const sz of [0, h]) {
            const rx = sx * cos - sy * sin
            const ry = sx * sin + sy * cos
            corners.push([p.x + rx, p.y + ry, p.z + sz])
        }
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
        for (const [x, y, z] of corners) {
            const v = vp.worldToView({ x, y, z })
            if (v.x < minX) minX = v.x
            if (v.y < minY) minY = v.y
            if (v.x > maxX) maxX = v.x
            if (v.y > maxY) maxY = v.y
        }
        if ([minX, minY, maxX, maxY].every(Number.isFinite)) {
            out.push({ assetInstanceId: inst.assetInstanceId, bounds: { minX, minY, maxX, maxY } })
        }
    }
    return out
}

/** Replace the selection with the given ids (marquee release). */
export function replaceSelection(assetInstanceIds: readonly string[]): void {
    spatialAssetStore.replaceSelection(assetInstanceIds)
}

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
            // Render the transient preview transform (position or yaw or group)
            // for the active instance(s); committed transforms for all others.
            () => spatialAssetStore.getEffectiveProjectInstances(),
            () => spatialAssetStore.getSnapshot().selectedAssetInstanceId,
            // Disable decoration caching while a drag is active so the moving
            // scanner is rebuilt from the preview transform every frame.
            () => spatialAssetStore.isDragActive(),
            // Same for an active rotation preview.
            () => spatialAssetStore.isRotationActive(),
            // Authoritative multi-selection (rotation handle only for a sole
            // selected asset; hidden for 0 or >1).
            () => spatialAssetStore.getSelectedIds(),
            // Disable caching during a group drag so all members follow.
            () => spatialAssetStore.isGroupDragActive(),
            // Rotation-handle hover (set by the manipulation tool on motion).
            () => rotationHandleHover,
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
    // Choose the redraw path via the SAME predicate the decorator uses to
    // disable caching. During ANY active preview (single drag, GROUP drag, or
    // rotation) the decorator's useCachedDecorations is undefined => there is NO
    // cache entry, so invalidateCachedDecorations(decorator) would assert in
    // DecorationsCache.delete. Use a plain invalidateDecorations() instead.
    const policy = resolveDecorationRedrawPolicy({
        dragActive: spatialAssetStore.isDragActive(),
        groupDragActive: spatialAssetStore.isGroupDragActive(),
        rotationActive: spatialAssetStore.isRotationActive(),
    })
    if (import.meta.env.DEV) {
        // Bounded: only log while a preview is active (not per idle emit).
        if (policy === 'DYNAMIC_REDRAW') {
            invalidateDiag()
        }
    }
    if (policy === 'DYNAMIC_REDRAW') {
        vp.invalidateDecorations()
    } else {
        // Idle: the decorator caches; invalidate the cache so the next frame
        // rebuilds (e.g. after a placement/move/rotate or drag/group commit/cancel).
        vp.invalidateCachedDecorations(decorator)
    }
}

/** Bounded [decor-cache] diagnostic (first few dynamic-redraw invalidations). */
let invalidateDiagCount = 0
function invalidateDiag(): void {
    if (invalidateDiagCount >= 6) return
    invalidateDiagCount += 1
    console.info('[decor-cache] stage=REDRAW policy=DYNAMIC_REDRAW groupActive=%s dragActive=%s rotationActive=%s',
        String(spatialAssetStore.isGroupDragActive()), String(spatialAssetStore.isDragActive()), String(spatialAssetStore.isRotationActive()))
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

/** Toggle an asset in the multi-selection (Shift-click add/remove). */
export function toggleAsset(assetInstanceId: string): void {
    spatialAssetStore.toggleAsset(assetInstanceId)
}

/** Remove one asset from the selection (context-menu DESELECT). */
export function deselectAsset(assetInstanceId: string): void {
    spatialAssetStore.deselectAsset(assetInstanceId)
}

/** Clear the entire selection (empty-space click). */
export function clearSelection(): void {
    spatialAssetStore.clearSelection()
}

// --- group translation (multi-select) ---
/** Begin a fluid GROUP drag anchored on a selected member. Returns success. */
export function beginGroupDrag(anchorAssetInstanceId: string, grabWorldPoint: { x: number; y: number; z: number }): boolean {
    const r = spatialAssetStore.beginGroupDrag(anchorAssetInstanceId, grabWorldPoint)
    if (import.meta.env.DEV) console.info('[mrt-group] BEGIN anchor=%s ok=%s', anchorAssetInstanceId, String(r.ok))
    return r.ok
}

/** Update the transient group preview from a drag world point (no event). */
export function updateGroupDragPreview(dragWorldPoint: { x: number; y: number; z: number }): void {
    spatialAssetStore.updateGroupDragPreview(dragWorldPoint)
}

/** Commit the active group drag: ONE ASSET_MOVED per moved member. */
export function commitGroupDrag(): { ok: boolean; movedCount: number } {
    const r = spatialAssetStore.commitGroupDrag()
    if (import.meta.env.DEV) console.info('[mrt-group] COMMIT ok=%s movedCount=%s', String(r.ok), String(r.ok ? r.movedCount : 0))
    return { ok: r.ok, movedCount: r.ok ? r.movedCount : 0 }
}

/** Cancel the active group drag: discard preview, no event. */
export function cancelGroupDrag(): void {
    spatialAssetStore.cancelGroupDrag()
    if (import.meta.env.DEV) console.info('[mrt-group] CANCEL')
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

// ---------------------------------------------------------------------------
// BIM spatial semantics: floor + room association (observational, read-only)
// ---------------------------------------------------------------------------
//
// The association is DERIVED state: it is computed on demand from an asset's
// authoritative position + a cached, Bentley-free SpatialModelSemantics
// snapshot built by the (dynamically imported) bentleySpatialAdapter. It NEVER
// mutates an asset's position, Z, rotation, or identity. The cache is refreshed
// explicitly (e.g. by a DEV inspector) — there is no per-frame BIM query and no
// authoritative room/floor change during a drag preview.

import type { SpatialAssociationResult, SpatialModelSemantics } from '../../domain/assets'
import { EMPTY_MODEL_SEMANTICS, computeSpatialAssociation, summarizeAssociation } from '../../domain/assets'

/** Cached model semantics (Bentley-free). Refreshed explicitly, never per-frame. */
let cachedModelSemantics: SpatialModelSemantics = { ...EMPTY_MODEL_SEMANTICS }
let semanticsLoaded = false
/** Monotonic generation; bumped each successful refresh so consumers can detect
 * whether they computed against the same BIM semantics snapshot. */
let semanticsGeneration = 0

/** The current cached semantics (may be empty until refreshed). */
export function getCachedModelSemantics(): SpatialModelSemantics {
    return cachedModelSemantics
}

/** The current semantics generation (0 until first refresh). */
export function getSemanticsGeneration(): number {
    return semanticsGeneration
}

/** Whether the semantics cache has been loaded at least once. */
export function isSemanticsLoaded(): boolean {
    return semanticsLoaded
}

/**
 * Refresh the cached SpatialModelSemantics from the live iModel via the adapter
 * (dynamic import so the Bentley query code is never pulled into tests). Bounded,
 * read-only, one-shot per call. Returns the refreshed semantics.
 */
export async function refreshModelSemantics(): Promise<SpatialModelSemantics> {
    try {
        const { buildModelSemantics } = await import('./bentleySpatialAdapter')
        cachedModelSemantics = await buildModelSemantics()
        semanticsLoaded = true
        semanticsGeneration += 1
    } catch (e) {
        if (import.meta.env.DEV) console.error('[bentley-spatial] REFRESH_ERROR', e instanceof Error ? e.message : String(e))
    }
    return cachedModelSemantics
}

/**
 * Compute the derived spatial association for one instance from its COMMITTED
 * position and the cached semantics. Pure wrt the asset (no mutation). Returns
 * undefined if the instance is not found.
 */
export function getAssociationForInstance(assetInstanceId: string): SpatialAssociationResult | undefined {
    const inst = spatialAssetStore.getInstance(assetInstanceId)
    if (!inst) return undefined
    return computeSpatialAssociation({
        assetInstanceId,
        position: { ...inst.transform.position },
        semantics: cachedModelSemantics,
    })
}

/**
 * DEV: inspect the live BIM spatial structure (bounded class inventory).
 * Read-only; refreshes the cached semantics as a side effect so a subsequent
 * INSPECT SPATIAL ASSOCIATION uses fresh data.
 */
export async function inspectBimSpatialStructure(): Promise<string> {
    try {
        const { discoverBimSpatialInventory, summarizeRoomRanges } = await import('./bentleySpatialAdapter')
        const inv = await discoverBimSpatialInventory()
        await refreshModelSemantics()
        const roomRanges = await summarizeRoomRanges()
        const summary = [
            `floorClass=${inv.floorSourceClass}`,
            `roomClass=${inv.roomSourceClass}`,
            `roomCount=${inv.roomObjectCount}`,
            `classes=[${inv.summary}]`,
            `floorAvail=${cachedModelSemantics.floorAvailability}`,
            `roomAvail=${cachedModelSemantics.roomAvailability}`,
            `gen=${semanticsGeneration}`,
            `ranges=[${roomRanges}]`,
        ].join(' | ')
        if (import.meta.env.DEV) console.info('[bentley-spatial] INSPECT_STRUCTURE %s', summary)
        return summary
    } catch (e) {
        return 'INSPECT_STRUCTURE_ERROR: ' + (e instanceof Error ? e.message : String(e))
    }
}

/**
 * DEV: inspect the spatial association of the currently selected asset. Refreshes
 * the semantics cache first (if never loaded) so the result reflects the live
 * BIM. Read-only.
 */
export async function inspectSpatialAssociation(): Promise<string> {
    const snap = spatialAssetStore.getSnapshot()
    const selected = snap.selectedAssetInstanceId
    if (!selected) return 'NO_SELECTED_ASSET'
    if (!semanticsLoaded) await refreshModelSemantics()
    const result = getAssociationForInstance(selected)
    if (!result) return `NOT_FOUND: ${selected}`
    const summary = `${summarizeAssociation(result)} | semanticsGeneration=${semanticsGeneration}`
    if (import.meta.env.DEV) console.info('[spatial-assoc] %s', summary)
    return summary
}

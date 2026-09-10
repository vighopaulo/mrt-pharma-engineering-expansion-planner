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
import { RoomPlanDecorator } from './RoomPlanDecorator'
import { ClinicalProgramDecorator } from './ClinicalProgramDecorator'
import { deriveRoomFootprint, resolveRoomStoreyId, type StoreyZRange } from './planningPlan'
import { resolveDecoratorRegistrationAction } from './decoratorRegistration'
import { resolveClinicalProgramFacilityAnchor, describeGeometryQuality } from './clinicalProgramAnchor'
import {
    discoverRoomVolumes,
    summarizeRoomVolumeDiscovery,
    filterDiscoveredRoomsByStorey,
    countRoomsByStorey,
    buildSelectedRoomVolumeDiagnostic,
    formatSelectedRoomVolumeDiagnostic,
    type DiscoveredRoomVolume,
    type RoomVolumeDiscoverySummary,
    type RoomMeshCacheFacts,
} from './bimRoomVolumeRegistry'
import {
    INITIAL_ROOM_DISCOVERY_STATE,
    beginRefreshState,
    decideSemanticsCommit,
    roomSelectorLabel,
    type RoomDiscoveryState,
    type RefreshCompletion,
    type RefreshOutcome,
} from './roomDiscoveryLifecycle'
import { resolveViewportSource, type ViewportSource } from './viewportResolution'
import type { ScreenViewport } from '@itwin/core-frontend'
import {
    assignClinicalFunction as pureAssignClinicalFunction,
    resetAssignment as pureResetAssignment,
    assignmentForSpace as pureAssignmentForSpace,
    summarizeProgram as pureSummarizeProgram,
    checkProgramCompleteness as pureCheckProgramCompleteness,
    loadProgramAssignments,
    saveProgramAssignments,
    type ClinicalProgramAssignment,
    type ClinicalFunction,
    type BimSpaceRef,
} from './clinicalProgram'
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
 * UI-only viewer mode (NORMAL_PLANNING default vs DEVELOPER). Presentation only:
 * gates developer controls and the raw engineering dump. Never affects
 * engineering/interaction state. Shared via subscription so both BentleyViewer
 * and the lazy product panels observe the same mode.
 */
import type { ViewerMode } from './planningVisuals'
import { DEFAULT_VIEWER_MODE } from './planningVisuals'
let viewerMode: ViewerMode = DEFAULT_VIEWER_MODE
const viewerModeListeners = new Set<() => void>()
export function subscribeViewerMode(listener: () => void): () => void {
    viewerModeListeners.add(listener)
    return () => { viewerModeListeners.delete(listener) }
}
export function getViewerMode(): ViewerMode {
    return viewerMode
}
export function setViewerMode(mode: ViewerMode): void {
    if (viewerMode === mode) return
    viewerMode = mode
    for (const l of viewerModeListeners) l()
    // Redraw so the derived room-plan appears/disappears with the mode.
    const vp = IModelApp.viewManager?.selectedView
    vp?.invalidateDecorations()
}
export function toggleViewerMode(): void {
    setViewerMode(viewerMode === 'DEVELOPER' ? 'NORMAL_PLANNING' : 'DEVELOPER')
}

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

// The product viewport the viewer component explicitly registers. This is the
// authoritative source for "the live clinic viewport" — selectedView can be null
// while this is present (the proven NO_ACTIVE_VIEWPORT root cause).
let explicitProductViewport: ScreenViewport | undefined

/** The viewer registers its live ScreenViewport here on view-open. */
export function setActiveProductViewport(vp: ScreenViewport | undefined): void {
    explicitProductViewport = vp
}

/** Resolve the active product viewport with explicit precedence (pure policy). */
export function resolveActiveProductViewport(): { viewport?: ScreenViewport; source: ViewportSource } {
    const selected = IModelApp.viewManager?.selectedView ?? undefined
    // Count viewports the viewManager owns (bounded iteration).
    let registeredCount = 0
    let onlyRegistered: ScreenViewport | undefined
    try {
        for (const vp of IModelApp.viewManager) { registeredCount += 1; onlyRegistered = vp }
    } catch { /* viewManager not iterable / not initialized */ }

    const source = resolveViewportSource({
        explicitProductViewportAvailable: !!explicitProductViewport,
        selectedViewAvailable: !!selected,
        registeredViewportCount: registeredCount,
    })
    switch (source) {
        case 'EXPLICIT_PRODUCT_VIEWPORT': return { viewport: explicitProductViewport, source }
        case 'SELECTED_VIEW': return { viewport: selected, source }
        case 'SINGLE_REGISTERED_VIEWPORT': return { viewport: onlyRegistered, source }
        default: return { viewport: undefined, source }
    }
}

let decorator: SpatialAssetDecorator | undefined
let removeDecorator: (() => void) | undefined
let roomPlanDecorator: RoomPlanDecorator | undefined
let removeRoomPlanDecorator: (() => void) | undefined
let clinicalProgramDecorator: ClinicalProgramDecorator | undefined
let removeClinicalProgramDecorator: (() => void) | undefined

/** Subscribe to store changes (product UI observability). */
export function subscribeSpatialAssets(listener: StoreListener): () => void {
    return spatialAssetStore.subscribe(listener)
}

/** Register the decorator once. Safe to call repeatedly (idempotent). */
export function ensureDecoratorRegistered(): void {
    // The CLINICAL PROGRAM decorator has its own idempotent registration and
    // MUST run before the SpatialAssetDecorator early-return below — otherwise a
    // remount where the asset decorator is already attached skips it entirely
    // (the proven DECORATOR_NOT_REGISTERED failure).
    ensureClinicalProgramDecoratorRegistered()
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

    // Derived BIM-backed room-plan context (view-only decorations). Normal mode
    // only; developer mode keeps the raw BIM volumes. Source of truth is the
    // cached SpatialModelSemantics room ranges — never a second identity.
    if (!roomPlanDecorator) {
        roomPlanDecorator = new RoomPlanDecorator({
            getMode: () => viewerMode,
            getRooms: () => cachedModelSemantics.rooms,
            // Honest planning elevation: the selected asset's Z if one is
            // selected/placed; otherwise the plan defaults to the lowest room.
            getSelectedAssetZ: () => {
                const sel = spatialAssetStore.getSnapshot().selectedAssetInstanceId
                if (!sel) return undefined
                const inst = spatialAssetStore.getEffectiveProjectInstances().find((i) => i.assetInstanceId === sel)
                return inst?.transform.position.z
            },
            getShowLabels: () => true,
        })
    }
    removeRoomPlanDecorator = IModelApp.viewManager.addDecorator(roomPlanDecorator)

    // (CLINICAL PROGRAM decorator already ensured at the top of this function,
    // before the early-return, via ensureClinicalProgramDecoratorRegistered.)

    // One-shot: load the authoritative room semantics so the derived room-plan
    // has ranges to draw in normal mode (read-only; also used by association).
    // Bounded and idempotent (refreshModelSemantics is safe to call; the guard
    // avoids repeated queries). After it lands, redraw the decorations.
    if (!semanticsLoaded && !roomPlanSemanticsRequested) {
        roomPlanSemanticsRequested = true
        void refreshModelSemantics().then(() => {
            const vp = IModelApp.viewManager?.selectedView
            vp?.invalidateDecorations()
        }).catch(() => { roomPlanSemanticsRequested = false })
    }
}

let roomPlanSemanticsRequested = false

/** Resolve a Bentley BODY pick id (HitDetail.sourceId) to an asset id. */
export function assetIdForPickId(pickId: string): string | undefined {
    return decorator?.assetIdForPickId(pickId)
}

/** Resolve a Bentley ROTATION HANDLE pick id to its asset id. */
export function handleAssetIdForPickId(pickId: string): string | undefined {
    return decorator?.handleAssetIdForPickId(pickId)
}

/**
 * Register the CLINICAL PROGRAM decorator with the Bentley ViewManager — its OWN
 * idempotent, runtime-gated lifecycle (proven addDecorator pattern). Independent
 * of Developer mode, room selection, and assignment state: the decorator itself
 * decides per-frame whether to draw (getEnabled). Registering it here, before the
 * SpatialAssetDecorator early-return in ensureDecoratorRegistered, is the fix for
 * the proven DECORATOR_NOT_REGISTERED failure. Invalidates decorations once after
 * a fresh registration so the existing persisted assignment renders immediately.
 */
export function ensureClinicalProgramDecoratorRegistered(): void {
    const runtimeReady = !!IModelApp?.viewManager
    const action = resolveDecoratorRegistrationAction({
        runtimeReady,
        alreadyRegistered: !!removeClinicalProgramDecorator,
        featureEnabled: true,
    })
    if (action === 'WAIT' || action === 'KEEP') return
    if (action === 'UNREGISTER') {
        if (removeClinicalProgramDecorator) removeClinicalProgramDecorator()
        removeClinicalProgramDecorator = undefined
        return
    }
    // action === 'REGISTER'
    if (!clinicalProgramDecorator) {
        clinicalProgramDecorator = new ClinicalProgramDecorator({
            getEnabled: () => programState.enabled,
            getMode: () => viewerMode,
            getRooms: () => cachedModelSemantics.rooms,
            getAssignments: () => programState.assignments,
            getActiveStoreyId: () => programState.activeStoreyId,
            getSelectedSpaceId: () => programState.selectedSpaceId,
            getStoreyRanges: () => programStoreyRanges,
            getAuthoritativeFootprint: (bimSpaceId: string) => {
                const e = authoritativeFootprints.get(bimSpaceId)
                if (!e || !e.ok) return undefined
                return { outerLoop: e.outerLoop, holes: e.holes, floorZ: e.floorZ, interiorAnchor: e.interiorAnchor }
            },
            getShowRoomVolume: () => programState.showRoomVolume,
            getRoomVolumeMesh: (bimSpaceId: string) => {
                const e = authoritativeFootprints.get(bimSpaceId)
                return e?.ok ? e.mesh : undefined
            },
            getShowClinicalVolume: () => showClinicalVolume,
            getPlanningVolumeForSpace: (bimSpaceId: string) => {
                const v = planningVolumes.find((x) => x.parentBimSpaceId === bimSpaceId)
                if (!v || v.hidden) return undefined // per-volume visibility
                // Build 1A.4: surface the last-computed containment FAIL as an
                // invalid visual cue (synchronous read of the per-space status
                // cache; updated by getClinicalVolumeContainment on every edit).
                const invalid = containmentStatusCache.get(bimSpaceId) === 'FAIL'
                return { params: v.params, lifecycleState: v.lifecycleState, displayName: v.displayName, selected: programState.selectedSpaceId === bimSpaceId, invalid }
            },
            // Build 1A label-occlusion: the active camera mode drives the
            // walkthrough-aware label-visibility policy in the decorator.
            getCameraMode: () => activeCameraMode,
        })
    }
    removeClinicalProgramDecorator = IModelApp.viewManager.addDecorator(clinicalProgramDecorator)
    // Immediate refresh so an already-persisted assignment draws without a camera nudge.
    IModelApp.viewManager?.selectedView?.invalidateDecorations()
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
    if (removeRoomPlanDecorator) removeRoomPlanDecorator()
    removeRoomPlanDecorator = undefined
    if (removeClinicalProgramDecorator) removeClinicalProgramDecorator()
    removeClinicalProgramDecorator = undefined
    // Keep the decorator instances and the store so re-registration restores the
    // overlay (the domain state is authoritative and survives a transient detach).
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

import type { SpatialAssociationResult, SpatialModelSemantics, SpatialRoomReference } from '../../domain/assets'
import { EMPTY_MODEL_SEMANTICS, computeSpatialAssociation, summarizeAssociation } from '../../domain/assets'

/** Cached model semantics (Bentley-free). Refreshed explicitly, never per-frame. */
let cachedModelSemantics: SpatialModelSemantics = { ...EMPTY_MODEL_SEMANTICS }
let semanticsLoaded = false
/** Monotonic generation; bumped each successful COMMIT so consumers can detect
 * whether they computed against the same BIM semantics snapshot. */
let semanticsGeneration = 0
/**
 * Build 1A.1 — explicit room-discovery lifecycle (iModel ownership + status +
 * stale-guard). Prevents a not-ready/failed/stale refresh from erasing a valid
 * cache (the 200 → 0 regression). See roomDiscoveryLifecycle.ts.
 */
let roomDiscoveryState: RoomDiscoveryState = { ...INITIAL_ROOM_DISCOVERY_STATE }
/** In-flight refresh dedupe (one live refresh at a time; callers await it). */
let semanticsRefreshInFlight: Promise<SpatialModelSemantics> | undefined

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

/** The current room-discovery lifecycle state (read-only copy). */
export function getRoomDiscoveryState(): RoomDiscoveryState {
    return { ...roomDiscoveryState }
}

/** Whether a semantics refresh is currently in flight. */
export function isSemanticsRefreshInFlight(): boolean {
    return !!semanticsRefreshInFlight
}

/**
 * Refresh the cached SpatialModelSemantics from the live iModel via the adapter
 * (dynamic import so the Bentley query code is never pulled into tests). Bounded,
 * read-only.
 *
 * Build 1A.1 lifecycle guard: the result is committed through
 * `decideSemanticsCommit`, so a NOT_READY (viewport transiently unbound), FAILED,
 * or STALE (different iModel) refresh NEVER overwrites a currently-valid cache —
 * fixing the 200 → 0 regression where an empty not-ready result clobbered the
 * good room set. A legitimate current-iModel zero IS still accepted. Concurrent
 * callers share one in-flight refresh.
 */
export async function refreshModelSemantics(): Promise<SpatialModelSemantics> {
    if (semanticsRefreshInFlight) return semanticsRefreshInFlight
    const run = (async (): Promise<SpatialModelSemantics> => {
        const targetIModelId = programState.iModelId || undefined
        roomDiscoveryState = beginRefreshState({ current: roomDiscoveryState, targetIModelId })
        let completion: RefreshCompletion
        try {
            const { buildActiveModelSemantics, getActiveSemanticsIModelId } = await import('./bentleySpatialAdapter')
            const active = getActiveSemanticsIModelId()
            const built = await buildActiveModelSemantics()
            const outcome: RefreshOutcome = !built.bound
                ? 'NOT_READY'
                : built.semantics.rooms.length > 0 ? 'READY_NONEMPTY' : 'READY_EMPTY'
            completion = {
                targetIModelId,
                ranAgainstIModelId: built.ranAgainstIModelId ?? active,
                outcome,
                roomCount: built.semantics.rooms.length,
            }
            const decision = decideSemanticsCommit({
                current: roomDiscoveryState,
                activeIModelId: programState.iModelId || undefined,
                completion,
            })
            roomDiscoveryState = decision.next
            if (decision.commit) {
                cachedModelSemantics = built.semantics
                semanticsLoaded = true
                semanticsGeneration += 1
                roomStoreyIdCache.clear() // storey binning depends on the new rooms
            } else if (import.meta.env.DEV) {
                console.info('[bentley-spatial] SEMANTICS_DISCARDED reason=%s outcome=%s target=%s ran=%s',
                    decision.reason, completion.outcome, String(targetIModelId), String(completion.ranAgainstIModelId))
            }
        } catch (e) {
            const errorClass = e instanceof Error ? e.name : 'UNKNOWN'
            completion = { targetIModelId, outcome: 'FAILED', roomCount: 0, errorClass }
            roomDiscoveryState = decideSemanticsCommit({
                current: roomDiscoveryState,
                activeIModelId: programState.iModelId || undefined,
                completion,
            }).next
            if (import.meta.env.DEV) console.error('[bentley-spatial] REFRESH_ERROR', e instanceof Error ? e.message : String(e))
        }
        return cachedModelSemantics
    })()
    semanticsRefreshInFlight = run
    try { return await run } finally { semanticsRefreshInFlight = undefined }
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
 * DEV / AUDIT: run the READ-ONLY BIM content audit (schemas, class counts,
 * architectural-class search, room inventory) and return a bounded, formatted
 * report for the Developer Inspector. Modifies nothing. Diagnostic only.
 */
export async function inspectBimContentAudit(): Promise<string> {
    try {
        const { runBimContentAudit, formatBimContentAudit } = await import('./bimContentAudit')
        const audit = await runBimContentAudit()
        return formatBimContentAudit(audit)
    } catch (e) {
        return 'BIM_CONTENT_AUDIT_ERROR: ' + (e instanceof Error ? e.message : String(e))
    }
}

/**
 * Camera navigation (view-only). Applies a product camera mode to the active
 * viewport via the walkthrough controller. Never writes the iModel / emits
 * engineering events. Returns storey list for the cutaway UI.
 */
export async function applyCameraMode(mode: import('./cameraNav').CameraMode, opts?: { storeyId?: string; fovPreset?: import('./walkNav').FovPreset }): Promise<boolean> {
    const ctl = await import('./walkthroughController')
    let storey: import('./walkthroughController').StoreyInfo | undefined
    if (opts?.storeyId) {
        const storeys = await ctl.loadStoreys()
        storey = storeys.find((s) => s.id === opts.storeyId)
    }
    // Build 1A label-occlusion: track the active CAMERA mode (distinct from the
    // ViewerMode planning/developer axis) so the ClinicalProgramDecorator can
    // apply the walkthrough-aware label-visibility policy. View concern only.
    activeCameraMode = mode
    const ok = await ctl.applyCameraMode(mode, { storey, startStoreyId: opts?.storeyId, fovPreset: opts?.fovPreset })
    notifyProgram() // redraw so labels re-evaluate under the new camera-mode policy
    return ok
}

/**
 * Build 1A — the active product CAMERA mode (PLANNING / WALKTHROUGH /
 * BIRDS_EYE_CUTAWAY). Separate axis from ViewerMode; drives the walkthrough
 * label-visibility policy. Defaults to PLANNING.
 */
let activeCameraMode: import('./cameraNav').CameraMode = 'PLANNING'
export function getActiveCameraMode(): import('./cameraNav').CameraMode {
    return activeCameraMode
}

export async function setWalkthroughFov(preset: import('./walkNav').FovPreset): Promise<void> {
    const ctl = await import('./walkthroughController')
    ctl.setWalkthroughFov(preset)
}

export async function turnAroundWalkthrough(): Promise<void> {
    const ctl = await import('./walkthroughController')
    ctl.turnAround()
}

export async function loadCameraStoreys(): Promise<import('./walkthroughController').StoreyInfo[]> {
    const ctl = await import('./walkthroughController')
    return ctl.loadStoreys()
}

export async function exitWalkthroughMode(): Promise<void> {
    const ctl = await import('./walkthroughController')
    ctl.exitWalkthrough()
}

/** DEV: bounded walkthrough movement diagnostic (Build 1A walkthrough correction). */
export async function diagnoseWalkthroughMovement(): Promise<string> {
    const ctl = await import('./walkthroughController')
    return ctl.diagnoseWalkthroughMovement()
}

export async function resetWalkthroughMode(): Promise<void> {
    const ctl = await import('./walkthroughController')
    ctl.resetWalkthrough()
}

/**
 * DEV / PROBE: read-only, GET-only Bentley cloud permission probe using the
 * existing runtime auth token. Returns a sanitized report for the Developer
 * Inspector. Creates/uploads/runs nothing; never logs the token.
 */
export async function probeBentleyCloudPermissions(): Promise<string> {
    try {
        const { runBentleyPermissionProbe, formatPermissionProbe } = await import('./bentleyPermissionProbe')
        const report = await runBentleyPermissionProbe()
        return formatPermissionProbe(report)
    } catch (e) {
        return 'BENTLEY_PERMISSION_PROBE_ERROR: ' + (e instanceof Error ? e.message : String(e))
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

// ===========================================================================
// MRT PHARMA CLINICAL PROGRAM OVERLAY — application-owned planning state
// ===========================================================================
//
// Non-destructive planning layer over the existing Bentley BIM. All state lives
// here (never in Bentley). Assignments are iModel-scoped, persisted safely, and
// drive the view-only ClinicalProgramDecorator + the normal-mode UI panel. No
// Bentley write API is ever called from this seam.

interface ProgramState {
    enabled: boolean
    activeStoreyId?: string
    selectedSpaceId?: string
    iModelId: string
    assignments: ClinicalProgramAssignment[]
    /** View-only: render the authoritative IfcSpace volume shell. */
    showRoomVolume: boolean
}

const programState: ProgramState = {
    enabled: false,
    activeStoreyId: undefined,
    selectedSpaceId: undefined,
    iModelId: '',
    assignments: [],
    showRoomVolume: false,
}

const programListeners = new Set<() => void>()

function notifyProgram(): void {
    for (const l of programListeners) l()
    IModelApp.viewManager?.selectedView?.invalidateDecorations()
}

/** Subscribe to clinical-program state changes (UI observability). */
export function subscribeClinicalProgram(listener: () => void): () => void {
    programListeners.add(listener)
    return () => { programListeners.delete(listener) }
}

/**
 * Bind the clinical-program layer to a specific iModel id and load its persisted
 * assignments. Switching id loads that id's scoped set (so a clinic's program
 * never appears on the fixture, §21/§67). Idempotent when the id is unchanged.
 */
export function loadClinicalProgramForIModel(iModelId: string): void {
    if (!iModelId) return
    if (programState.iModelId === iModelId) {
        notifyProgram()
        return
    }
    programState.iModelId = iModelId
    programState.assignments = loadProgramAssignments(iModelId)
    programState.selectedSpaceId = undefined
    // Switching iModel invalidates any cached authoritative footprints + volumes.
    authoritativeFootprints.clear()
    authoritativeInFlight.clear()
    planningVolumes = []
    // Build 1A.1: switching iModel intentionally invalidates the room-discovery
    // authority (semantics belong to the previous BIM). Reset to NOT_BOUND so a
    // stale previous-iModel refresh cannot be treated as current; the next
    // refresh rebinds for the new iModel. (Never copies rooms across iModels.)
    cachedModelSemantics = { ...EMPTY_MODEL_SEMANTICS }
    semanticsLoaded = false
    roomDiscoveryState = { ...INITIAL_ROOM_DISCOVERY_STATE }
    roomStoreyIdCache.clear()
    containmentStatusCache.clear() // Build 1A.4: per-space invalid cue is iModel-scoped
    loadPlanningVolumesForIModel(iModelId)
    // Ensure the decorator is attached once the runtime is ready (idempotent;
    // no-op if runtime not ready — ensureDecoratorRegistered will attach later).
    ensureClinicalProgramDecoratorRegistered()
    requestAuthoritativeFootprintsForAssignments()
    notifyProgram()
}

/** Persist the current assignments under the active iModel id (safe subset). */
function persistProgram(): void {
    if (programState.iModelId) saveProgramAssignments(programState.iModelId, programState.assignments)
}

/** Current snapshot for the UI (read-only copies). */
export function getClinicalProgramSnapshot(): {
    enabled: boolean
    activeStoreyId?: string
    selectedSpaceId?: string
    iModelId: string
    assignments: readonly ClinicalProgramAssignment[]
    showRoomVolume: boolean
} {
    return {
        enabled: programState.enabled,
        activeStoreyId: programState.activeStoreyId,
        selectedSpaceId: programState.selectedSpaceId,
        iModelId: programState.iModelId,
        assignments: programState.assignments,
        showRoomVolume: programState.showRoomVolume,
    }
}

/** View-only: toggle the authoritative room-volume shell rendering. */
export function setClinicalProgramShowRoomVolume(show: boolean): void {
    if (programState.showRoomVolume === show) return
    programState.showRoomVolume = show
    // Build 1A.2: turning the volume ON lazily requests the SELECTED room's exact
    // authoritative mesh (on-demand; idempotent + cached; never eager/all-rooms).
    // ensureAuthoritativeRoomFootprint calls notifyProgram() on completion, so the
    // product panel's geometry status refreshes reactively without a reselect.
    if (show && programState.selectedSpaceId) {
        void ensureAuthoritativeRoomFootprint(programState.selectedSpaceId)
    }
    notifyProgram()
}

/** The retained authoritative mesh for a space (view-only volume rendering). */
export function getAuthoritativeRoomMesh(bimSpaceId: string): { vertices: readonly { x: number; y: number; z: number }[]; triangles: readonly number[] } | undefined {
    const e = authoritativeFootprints.get(bimSpaceId)
    return e?.ok ? e.mesh : undefined
}

// ===========================================================================
// MRT PHARMA CLINICAL PLANNING VOLUME — true 3D world-space planning objects
// ===========================================================================
//
// A ClinicalPlanningVolume is an app-owned oriented 3D prism (WORLD_GEOMETRY)
// that is a CHILD of an authoritative parent IfcSpace. Physical authority is in
// BIM/world coordinates; the camera never defines it. LOCK freezes the app object
// only (no Bentley write). One volume per build (Uptake 01).

let planningVolumes: import('./clinicalPlanningVolume').ClinicalPlanningVolume[] = []
/** True once the active iModel's volumes have been loaded (writes gated until then). */
let planningVolumesHydrated = false
let showClinicalVolume = true
/**
 * Build 1A.4 — per-space last-computed containment status (synchronous cache for
 * the decorator's invalid visual cue). Updated by getClinicalVolumeContainment;
 * cleared on iModel switch. Never authoritative — containment is recomputed.
 */
const containmentStatusCache = new Map<string, 'PASS' | 'FAIL' | 'NOT_EVALUATED'>()

/** Load planning volumes for the active iModel (scoped; cleared on switch). */
function loadPlanningVolumesForIModel(iModelId: string): void {
    planningVolumesHydrated = false
    void import('./clinicalPlanningVolume').then((m) => {
        // Only bind if the active iModel has not changed while loading (LOAD →
        // BIND → then allow writes). Prevents saving an empty/previous collection
        // into the new iModel's key.
        if (programState.iModelId !== iModelId) return
        planningVolumes = iModelId ? m.loadClinicalVolumes(iModelId) : []
        planningVolumesHydrated = true
        notifyProgram()
    })
}

function persistPlanningVolumes(): void {
    // HYDRATION GUARD: never write the (transiently empty) collection back to the
    // active iModel's key until the async load has completed. This closed the
    // empty-overwrite race where load→[]→save could clobber persisted volumes.
    if (!programState.iModelId || !planningVolumesHydrated) return
    void import('./clinicalPlanningVolume').then((m) => m.saveClinicalVolumes(programState.iModelId, planningVolumes))
}

/** The planning volume for a parent space (or undefined). */
export function getClinicalPlanningVolume(parentBimSpaceId: string): import('./clinicalPlanningVolume').ClinicalPlanningVolume | undefined {
    return planningVolumes.find((v) => v.parentBimSpaceId === parentBimSpaceId)
}

/** Snapshot of all planning volumes (read-only). */
export function getClinicalPlanningVolumes(): readonly import('./clinicalPlanningVolume').ClinicalPlanningVolume[] {
    return planningVolumes
}

export function getShowClinicalVolume(): boolean { return showClinicalVolume }
export function setShowClinicalVolume(show: boolean): void {
    if (showClinicalVolume === show) return
    showClinicalVolume = show
    notifyProgram()
}

/** Per-volume visibility (view-only; never mutates geometry or lifecycle). */
export async function setPlanningVolumeVisibility(parentBimSpaceId: string, visible: boolean): Promise<void> {
    const c = await import('./clinicalVolumeCollection')
    planningVolumes = c.setPlanningVolumeVisibility(planningVolumes, parentBimSpaceId, visible)
    persistPlanningVolumes()
    notifyProgram()
}

/**
 * Delete a DRAFT planning volume (app-owned only). LOCKED volumes are rejected
 * (unlock first). Never touches the assignment, Bentley space, or parent geometry.
 */
export async function deleteClinicalVolume(parentBimSpaceId: string): Promise<{ ok: boolean; reason?: string }> {
    const c = await import('./clinicalVolumeCollection')
    const r = c.deletePlanningVolume(planningVolumes, parentBimSpaceId)
    if (!r.deleted) return { ok: false, reason: r.reason }
    planningVolumes = r.volumes
    persistPlanningVolumes()
    notifyProgram()
    return { ok: true }
}

/** Per-collection volume summary (counts by lifecycle + visibility). */
export async function getClinicalVolumeSummary(): Promise<import('./clinicalVolumeCollection').VolumeSummary> {
    const c = await import('./clinicalVolumeCollection')
    return c.summarizePlanningVolumes(planningVolumes)
}

/**
 * Create or update the DRAFT planning volume for a parent space + clinical
 * function. Deterministic, no Bentley write. Returns the volume.
 */
export async function defineClinicalVolume(input: {
    parentBimSpaceId: string
    clinicalFunction: string
    displayName: string
    storeyId?: string
    params: import('./clinicalPlanningVolume').PrismParams
}): Promise<import('./clinicalPlanningVolume').ClinicalPlanningVolume> {
    const m = await import('./clinicalPlanningVolume')
    const existing = planningVolumes.find((v) => v.parentBimSpaceId === input.parentBimSpaceId)
    const slug = input.displayName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'volume'
    const id = existing?.id ?? m.makeClinicalVolumeId(programState.iModelId || 'unknown', input.parentBimSpaceId, slug)
    const vol: import('./clinicalPlanningVolume').ClinicalPlanningVolume = {
        id,
        iModelId: programState.iModelId,
        parentBimSpaceId: input.parentBimSpaceId,
        storeyId: input.storeyId,
        clinicalFunction: input.clinicalFunction,
        displayName: input.displayName,
        geometryType: 'ORIENTED_RECTANGULAR_PRISM',
        params: input.params,
        lifecycleState: existing?.lifecycleState === 'LOCKED' ? 'LOCKED' : 'DRAFT',
        geometrySource: 'MRT_PLANNING_SUBVOLUME',
    }
    planningVolumes = [...planningVolumes.filter((v) => v.parentBimSpaceId !== input.parentBimSpaceId), vol]
    persistPlanningVolumes()
    notifyProgram()
    return vol
}

/**
 * Derive a DRAFT seed for a NEW planning volume from the SELECTED parent's own
 * authoritative BIM geometry (never Uptake coords / world origin). Extracts the
 * parent mesh (read-only), uses its footprint centroid + Z range. Falls back to a
 * bounded default only if geometry is unavailable.
 */
export async function suggestPlanningVolumeSeedForParent(parentBimSpaceId: string): Promise<import('./clinicalPlanningVolume').PrismParams> {
    const m = await import('./clinicalPlanningVolume')
    await ensureAuthoritativeRoomFootprint(parentBimSpaceId)
    const parent = authoritativeFootprints.get(parentBimSpaceId)
    if (parent?.ok && parent.outerLoop && parent.outerLoop.length >= 3) {
        return m.seedPrismParamsFromParent({
            footprint: parent.outerLoop,
            zLow: parent.volume?.zLow ?? parent.floorZ,
            zHigh: parent.volume?.zHigh ?? (parent.floorZ + 3),
        })
    }
    // Bounded default (no geometry yet) — still not another room's coords.
    return { centerX: 0, centerY: 0, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0 }
}

/** Update the DRAFT volume's params (rejected if LOCKED). */
export function updateClinicalVolumeParams(parentBimSpaceId: string, params: import('./clinicalPlanningVolume').PrismParams): void {
    const v = planningVolumes.find((x) => x.parentBimSpaceId === parentBimSpaceId)
    if (!v || v.lifecycleState === 'LOCKED') return
    v.params = params
    planningVolumes = [...planningVolumes]
    persistPlanningVolumes()
    notifyProgram()
}

/** Live containment status of a volume against its authoritative parent mesh. */
export async function getClinicalVolumeContainment(parentBimSpaceId: string): Promise<{ status: 'PASS' | 'FAIL' | 'NOT_EVALUATED'; failedSamples: number; totalSamples: number; parentMeshAvailable: boolean; reason?: string }> {
    const v = planningVolumes.find((x) => x.parentBimSpaceId === parentBimSpaceId)
    if (!v) return { status: 'NOT_EVALUATED', failedSamples: 0, totalSamples: 0, parentMeshAvailable: false, reason: 'NO_VOLUME' }
    // Await extraction to completion (in-flight-aware) so a fresh volume is not
    // mis-reported before its parent mesh has loaded.
    await ensureAuthoritativeRoomFootprint(parentBimSpaceId)
    const m = await import('./clinicalPlanningVolume')
    const parent = authoritativeFootprints.get(parentBimSpaceId)
    const parentMeshAvailable = !!(parent?.ok && parent.mesh && parent.mesh.triangles.length >= 3)
    if (!parentMeshAvailable) {
        const naStatus = m.resolveContainmentStatus({ parentMeshAvailable: false, sampleCount: 0, failedSampleCount: 0 })
        containmentStatusCache.set(parentBimSpaceId, naStatus)
        return { status: naStatus, failedSamples: 0, totalSamples: 0, parentMeshAvailable: false, reason: parent?.reason ?? 'PARENT_MESH_NOT_LOADED' }
    }
    const r = m.validatePlanningVolumeContainment({ params: v.params, parentMesh: parent!.mesh! })
    const status = m.resolveContainmentStatus({ parentMeshAvailable: true, sampleCount: r.totalSamples, failedSampleCount: r.failedSamples })
    containmentStatusCache.set(parentBimSpaceId, status)
    // Build 1A.4: record the LAST-KNOWN-VALID geometry on PASS. Never overwrite it
    // with an invalid (FAIL) edit — that is what makes "Restore Valid Position"
    // safe. App-owned only; persisted; no Bentley write.
    if (status === 'PASS') {
        const snapshot = { ...v.params }
        if (JSON.stringify(v.lastKnownValidParams) !== JSON.stringify(snapshot)) {
            v.lastKnownValidParams = snapshot
            planningVolumes = [...planningVolumes]
            persistPlanningVolumes()
        }
    }
    return { status, failedSamples: r.failedSamples, totalSamples: r.totalSamples, parentMeshAvailable: true, reason: r.reason }
}

/**
 * Build 1A.4 — the product-facing VALIDATION view model for a planning volume
 * (pure model resolved from live containment + authority quality + last-known-
 * valid presence). Read-only; never mutates geometry, lifecycle, or Bentley.
 */
export async function getPlanningVolumeValidation(parentBimSpaceId: string): Promise<import('./bimRoomVolumeRegistry').PlanningVolumeValidationState | undefined> {
    const v = planningVolumes.find((x) => x.parentBimSpaceId === parentBimSpaceId)
    if (!v) return undefined
    const reg = await import('./bimRoomVolumeRegistry')
    const contain = await getClinicalVolumeContainment(parentBimSpaceId)
    const quality = getClinicalProgramRoomGeometryQuality(parentBimSpaceId)?.quality
    const authorityQuality: import('./bimRoomVolumeRegistry').PlanningAuthorityQuality =
        quality === 'EXACT_ROOM_BOUNDARY' ? 'EXACT_SPACE_GEOMETRY'
            : quality === 'BIM_RANGE_APPROXIMATION' ? 'RANGE_ONLY_APPROXIMATION'
                : 'NOT_AVAILABLE'
    return reg.resolvePlanningVolumeValidation({
        planningVolumeId: v.id,
        displayName: v.displayName,
        lifecycleState: v.lifecycleState,
        containmentStatus: contain.status,
        authorityQuality,
        totalSamples: contain.totalSamples,
        failedSamples: contain.failedSamples,
        hasLastKnownValid: !!v.lastKnownValidParams,
        parentMeshAvailable: contain.parentMeshAvailable,
    })
}

/** Build 1A.4 — restrained planning-validation summary across ALL volumes. */
export async function getPlanningValidationSummary(): Promise<import('./bimRoomVolumeRegistry').PlanningValidationSummary> {
    const reg = await import('./bimRoomVolumeRegistry')
    const states: import('./bimRoomVolumeRegistry').PlanningVolumeValidationState[] = []
    for (const v of planningVolumes) {
        const s = await getPlanningVolumeValidation(v.parentBimSpaceId)
        if (s) states.push(s)
    }
    return reg.summarizePlanningValidation(states)
}

/**
 * Build 1A.4 — RESTORE VALID POSITION for a DRAFT volume: restore this SAME
 * volume's most recent last-known-valid geometry; if none exists, fall back to a
 * parent-derived seed from this room's OWN authoritative geometry. Never restores
 * Uptake coords / another room / origin. No Bentley write. Rejected if LOCKED.
 */
export async function restoreValidPosition(parentBimSpaceId: string): Promise<{ ok: boolean; reason?: string; source?: 'LAST_KNOWN_VALID' | 'PARENT_DERIVED' }> {
    const v = planningVolumes.find((x) => x.parentBimSpaceId === parentBimSpaceId)
    if (!v) return { ok: false, reason: 'NO_VOLUME' }
    if (v.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED' }
    if (v.lastKnownValidParams) {
        v.params = { ...v.lastKnownValidParams }
        planningVolumes = [...planningVolumes]
        persistPlanningVolumes()
        notifyProgram()
        return { ok: true, source: 'LAST_KNOWN_VALID' }
    }
    // No last-known-valid — derive a fresh valid seed from this room's own parent.
    const seed = await suggestPlanningVolumeSeedForParent(parentBimSpaceId)
    v.params = seed
    planningVolumes = [...planningVolumes]
    persistPlanningVolumes()
    notifyProgram()
    return { ok: true, source: 'PARENT_DERIVED' }
}

/**
 * Build 1A.4 — RESET TO PARENT-DERIVED VOLUME: recompute a fresh valid seed from
 * this room's OWN authoritative parent geometry (distinct from Restore, which
 * uses the most recent valid USER state). No Bentley write. Rejected if LOCKED.
 */
export async function resetToParentDerived(parentBimSpaceId: string): Promise<{ ok: boolean; reason?: string }> {
    const v = planningVolumes.find((x) => x.parentBimSpaceId === parentBimSpaceId)
    if (!v) return { ok: false, reason: 'NO_VOLUME' }
    if (v.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED' }
    const seed = await suggestPlanningVolumeSeedForParent(parentBimSpaceId)
    v.params = seed
    planningVolumes = [...planningVolumes]
    persistPlanningVolumes()
    notifyProgram()
    return { ok: true }
}

/** Lock the volume (only when containment PASS + valid). No Bentley write. */
export async function lockClinicalVolume(parentBimSpaceId: string): Promise<{ ok: boolean; reason?: string }> {
    const v = planningVolumes.find((x) => x.parentBimSpaceId === parentBimSpaceId)
    if (!v) return { ok: false, reason: 'NO_VOLUME' }
    await ensureAuthoritativeRoomFootprint(parentBimSpaceId)
    const parent = authoritativeFootprints.get(parentBimSpaceId)
    if (!parent?.ok || !parent.mesh || parent.mesh.triangles.length < 3) return { ok: false, reason: 'PARENT_MESH_NOT_LOADED' }
    const m = await import('./clinicalPlanningVolume')
    const gate = m.canLockVolume(v, parent.mesh)
    if (!gate.ok) return gate
    v.lifecycleState = 'LOCKED'
    planningVolumes = [...planningVolumes]
    persistPlanningVolumes()
    notifyProgram()
    return { ok: true }
}

/** Unlock for editing (planning-object freeze only — NOT simulation Lockdown). */
export function unlockClinicalVolume(parentBimSpaceId: string): void {
    const v = planningVolumes.find((x) => x.parentBimSpaceId === parentBimSpaceId)
    if (!v || v.lifecycleState !== 'LOCKED') return
    v.lifecycleState = 'DRAFT'
    planningVolumes = [...planningVolumes]
    persistPlanningVolumes()
    notifyProgram()
}

/** DEV diagnostic: bounded report of the Uptake 01 planning volume. */
export async function diagnoseClinicalPlanningVolume(): Promise<string> {
    const target = programState.assignments.find((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')
    const L: string[] = ['=== UPTAKE 01 PLANNING VOLUME ===']
    if (!target) { L.push('NO_ACTIVE_ASSIGNMENT'); return L.join('\n') }
    const v = planningVolumes.find((x) => x.parentBimSpaceId === target.bimSpaceId)
    L.push(`PARENT_BIM_SPACE_ID = ${target.bimSpaceId}`)
    L.push(`IMODEL_ID = ${programState.iModelId || '(none)'}`)
    if (!v) { L.push('PLANNING_VOLUME = NONE (use Define Volume)'); return L.join('\n') }
    const m = await import('./clinicalPlanningVolume')
    const g = m.buildOrientedPlanningPrism(v.params)
    const contain = await getClinicalVolumeContainment(target.bimSpaceId)
    const parent = authoritativeFootprints.get(target.bimSpaceId)
    L.push(`PLANNING_VOLUME_ID = ${v.id}`)
    L.push(`LIFECYCLE_STATE = ${v.lifecycleState}`)
    L.push(`GEOMETRY_TYPE = ${v.geometryType}`)
    L.push(`CENTER = (${v.params.centerX.toFixed(2)},${v.params.centerY.toFixed(2)},${((v.params.zLow + v.params.zHigh) / 2).toFixed(2)})`)
    L.push(`WIDTH = ${v.params.width.toFixed(2)} DEPTH = ${v.params.depth.toFixed(2)}`)
    L.push(`Z_LOW = ${v.params.zLow.toFixed(2)} Z_HIGH = ${v.params.zHigh.toFixed(2)} HEIGHT = ${(v.params.zHigh - v.params.zLow).toFixed(2)}`)
    L.push(`YAW_DEG = ${((v.params.yaw * 180) / Math.PI).toFixed(1)}`)
    L.push(`PRISM_VERTEX_COUNT = ${g.vertices.length} PRISM_TRIANGLE_COUNT = ${g.triangles.length / 3}`)
    L.push(`INTERIOR_ANCHOR = (${g.interiorAnchor.x.toFixed(2)},${g.interiorAnchor.y.toFixed(2)},${g.interiorAnchor.z.toFixed(2)})`)
    L.push('--- containment ---')
    L.push(`PARENT_MESH_AVAILABLE = ${contain.parentMeshAvailable ? 'YES' : 'NO'}`)
    L.push(`PARENT_GEOMETRY_SOURCE = ${parent?.ok ? 'AUTHORITATIVE_IFCSPACE_GEOMETRY' : 'NONE'}`)
    L.push(`PARENT_VERTEX_COUNT = ${parent?.volume?.vertexCount ?? 0} PARENT_TRIANGLE_COUNT = ${parent?.volume?.triangleCount ?? 0}`)
    L.push(`PARENT_CLOSED_MESH = ${parent?.volume?.closedMesh ? 'YES' : 'NO'}`)
    L.push(`CONTAINMENT_SAMPLE_COUNT = ${contain.totalSamples}`)
    L.push(`CONTAINMENT_FAILED_SAMPLE_COUNT = ${contain.failedSamples}`)
    L.push(`CONTAINMENT_RESULT = ${contain.status}`)
    L.push(`LOCK_ALLOWED = ${contain.status === 'PASS' ? 'YES' : 'NO'}`)
    L.push(`RANGE_FALLBACK_USED = NO`)
    L.push(`WORLD_GEOMETRY = YES`)
    L.push(`SCREEN_SPACE_AUTHORITY = NO`)
    return L.join('\n')
}

/**
 * DEV diagnostic: READ-ONLY inspection of the MRT Pharma clinical-program /
 * planning-volume localStorage keys + runtime, classifying the persistence
 * regression. Inspects ONLY the mrtpharma.clinical* namespaces; never dumps
 * unrelated storage, tokens, or full payloads.
 */
export async function diagnoseClinicalProgramPersistence(): Promise<string> {
    const TARGET_SPACE = '0x200000001f1'
    const ASSIGN_PREFIX = 'mrtpharma.clinicalProgram.'
    const VOLUME_PREFIX = 'mrtpharma.clinicalVolume.'
    const iModelId = programState.iModelId || ''
    const L: string[] = ['=== CLINICAL PROGRAM PERSISTENCE ===']
    L.push(`ACTIVE_IMODEL_ID = ${iModelId || '(none)'}`)
    L.push(`RUNTIME_ASSIGNMENT_COUNT = ${programState.assignments.filter((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING').length}`)
    L.push(`RUNTIME_PLANNING_VOLUME_COUNT = ${planningVolumes.length}`)

    const store = typeof window !== 'undefined' ? window.localStorage : undefined
    if (!store) { L.push('NO_LOCALSTORAGE'); return L.join('\n') }

    // Bounded namespace scan (never other keys).
    const assignKeys: string[] = []
    const volumeKeys: string[] = []
    for (let i = 0; i < store.length; i++) {
        const k = store.key(i)
        if (!k) continue
        if (k.startsWith(ASSIGN_PREFIX)) assignKeys.push(k)
        else if (k.startsWith(VOLUME_PREFIX)) volumeKeys.push(k)
    }

    const currentAssignKey = `mrtpharma.clinicalProgram.v1.${iModelId}`
    const currentVolumeKey = `mrtpharma.clinicalVolume.v1.${iModelId}`

    // Bounded inventory helper (counts only; parse status; no payload dump).
    const inspect = (key: string): { present: boolean; chars: number; parseOk: boolean; count: number; hasTarget: boolean } => {
        const raw = store.getItem(key)
        if (raw == null) return { present: false, chars: 0, parseOk: true, count: 0, hasTarget: false }
        try {
            const parsed = JSON.parse(raw) as unknown
            const arr = Array.isArray(parsed) ? parsed as Record<string, unknown>[] : []
            const hasTarget = arr.some((r) => r && (r.bimSpaceId === TARGET_SPACE || r.parentBimSpaceId === TARGET_SPACE))
            return { present: true, chars: raw.length, parseOk: true, count: arr.length, hasTarget }
        } catch {
            return { present: true, chars: raw.length, parseOk: false, count: 0, hasTarget: false }
        }
    }

    const ca = inspect(currentAssignKey)
    const cv = inspect(currentVolumeKey)
    L.push('--- current keys ---')
    L.push(`CURRENT_ASSIGNMENT_STORAGE_KEY = ${currentAssignKey}`)
    L.push(`CURRENT_ASSIGNMENT_STORAGE_PRESENT = ${ca.present ? 'YES' : 'NO'} chars=${ca.chars} parseOk=${ca.parseOk ? 'YES' : 'NO'} recordCount=${ca.count}`)
    L.push(`CURRENT_VOLUME_STORAGE_KEY = ${currentVolumeKey}`)
    L.push(`CURRENT_VOLUME_STORAGE_PRESENT = ${cv.present ? 'YES' : 'NO'} chars=${cv.chars} parseOk=${cv.parseOk ? 'YES' : 'NO'} recordCount=${cv.count}`)
    L.push(`UPTAKE_ASSIGNMENT_FOUND_CURRENT = ${ca.hasTarget ? 'YES' : 'NO'}`)
    L.push(`UPTAKE_VOLUME_FOUND_CURRENT = ${cv.hasTarget ? 'YES' : 'NO'}`)

    // Legacy = any namespace key that is NOT the current-version key.
    const legacyAssign = assignKeys.filter((k) => k !== currentAssignKey)
    const legacyVolume = volumeKeys.filter((k) => k !== currentVolumeKey)
    let legacyAssignCount = 0, legacyVolumeCount = 0, legacyAssignTarget = false, legacyVolumeTarget = false
    for (const k of legacyAssign) { const r = inspect(k); legacyAssignCount += r.count; legacyAssignTarget = legacyAssignTarget || r.hasTarget }
    for (const k of legacyVolume) { const r = inspect(k); legacyVolumeCount += r.count; legacyVolumeTarget = legacyVolumeTarget || r.hasTarget }
    L.push('--- legacy / other-scope keys ---')
    L.push(`ASSIGNMENT_NAMESPACE_KEYS = ${assignKeys.length} (legacy/other=${legacyAssign.length})`)
    L.push(`VOLUME_NAMESPACE_KEYS = ${volumeKeys.length} (legacy/other=${legacyVolume.length})`)
    L.push(`LEGACY_MATCHING_KEY_COUNT = ${legacyAssign.length + legacyVolume.length}`)
    L.push(`UPTAKE_ASSIGNMENT_FOUND_LEGACY = ${legacyAssignTarget ? 'YES' : 'NO'}`)
    L.push(`UPTAKE_VOLUME_FOUND_LEGACY = ${legacyVolumeTarget ? 'YES' : 'NO'}`)
    // Note: other-scope keys may simply be a different iModel's data (not a defect).

    const { classifyClinicalPersistenceRegression, recoveryActionForClass } = await import('./clinicalPersistenceDiagnostic')
    const cls = classifyClinicalPersistenceRegression({
        currentAssignmentRecordCount: ca.count,
        currentVolumeRecordCount: cv.count,
        legacyAssignmentRecordCount: legacyAssignTarget ? legacyAssignCount : 0,
        legacyVolumeRecordCount: legacyVolumeTarget ? legacyVolumeCount : 0,
        runtimeAssignmentCount: programState.assignments.filter((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING').length,
        runtimeVolumeCount: planningVolumes.length,
        currentAssignmentParseFailed: ca.present && !ca.parseOk,
        currentVolumeParseFailed: cv.present && !cv.parseOk,
    })
    L.push('--- classification ---')
    L.push(`PERSISTENCE_REGRESSION_CLASS = ${cls}`)
    L.push(`RECOVERY_ACTION = ${recoveryActionForClass(cls)}`)
    L.push('SECRET_SAFE = YES (namespace-scoped, counts only, no payload/token dump)')
    return L.join('\n')
}

/**
 * AUTHORIZED, one-time reconstruction of the accepted Uptake 01 baseline
 * (assignment + DRAFT planning volume) — used only because the persistence
 * diagnostic proved PERSISTED_STATE_GENUINELY_ABSENT. Duplicate-guarded +
 * idempotent: never creates a second Uptake 01, never auto-runs on startup, never
 * auto-locks. Persists via the accepted assignment + volume paths.
 */
export async function reconstructUptake01Baseline(): Promise<{ ok: boolean; alreadyPresent: boolean; assignmentId?: string; planningVolumeId?: string; reason?: string }> {
    if (!programState.iModelId) return { ok: false, alreadyPresent: false, reason: 'NO_ACTIVE_IMODEL' }
    const { reconstructUptake01Baseline: reconstruct, UPTAKE_01_BASELINE } = await import('./uptake01Reconstruction')
    // Ensure volumes are hydrated before reconstructing (avoid clobbering).
    if (!planningVolumesHydrated) { try { await new Promise((r) => setTimeout(r, 0)) } catch { /* noop */ } }
    const storeyId = resolveRoomStoreyIdCached(UPTAKE_01_BASELINE.bimSpaceId)
    const result = reconstruct({
        iModelId: programState.iModelId,
        storeyId,
        existingAssignments: programState.assignments,
        existingVolumes: planningVolumes,
    })
    if (result.alreadyPresent) {
        return { ok: true, alreadyPresent: true, assignmentId: result.assignment.assignmentId, planningVolumeId: result.volume.id, reason: 'ALREADY_PRESENT' }
    }
    // Commit through the accepted persistence paths.
    programState.assignments = result.assignments
    persistProgram()
    planningVolumes = result.volumes
    planningVolumesHydrated = true // permit persistence now that a real record exists
    persistPlanningVolumes()
    // Extract parent geometry so containment recomputes.
    void ensureAuthoritativeRoomFootprint(UPTAKE_01_BASELINE.bimSpaceId)
    ensureClinicalProgramDecoratorRegistered()
    notifyProgram()
    return { ok: true, alreadyPresent: false, assignmentId: result.assignment.assignmentId, planningVolumeId: result.volume.id }
}

/** DEV diagnostic: bounded per-volume report across ALL planning volumes. */
export async function diagnoseClinicalPlanningVolumes(): Promise<string> {
    const c = await import('./clinicalVolumeCollection')
    const summary = c.summarizePlanningVolumes(planningVolumes)
    const L: string[] = ['=== CLINICAL PLANNING VOLUMES ===']
    L.push(`IMODEL_ID = ${programState.iModelId || '(none)'}`)
    L.push(`ASSIGNMENT_COUNT = ${programState.assignments.filter((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING').length}`)
    L.push(`PLANNING_VOLUME_COUNT = ${summary.planningVolumes} (draft=${summary.draft} locked=${summary.locked} visible=${summary.visible} hidden=${summary.hidden})`)
    L.push(`SELECTED_VOLUME_SPACE_ID = ${programState.selectedSpaceId ?? 'none'}`)
    for (const v of planningVolumes) {
        const contain = await getClinicalVolumeContainment(v.parentBimSpaceId)
        L.push('---')
        L.push(`displayName = ${v.displayName}`)
        L.push(`planningVolumeId = ${v.id}`)
        L.push(`parentBimSpaceId = ${v.parentBimSpaceId}`)
        L.push(`lifecycle = ${v.lifecycleState} visible = ${v.hidden ? 'NO' : 'YES'}`)
        L.push(`center = (${v.params.centerX.toFixed(2)},${v.params.centerY.toFixed(2)},${((v.params.zLow + v.params.zHigh) / 2).toFixed(2)}) w=${v.params.width.toFixed(2)} d=${v.params.depth.toFixed(2)} z=${v.params.zLow.toFixed(2)}..${v.params.zHigh.toFixed(2)} yaw=${((v.params.yaw * 180) / Math.PI).toFixed(1)}`)
        L.push(`containment = ${contain.status} (${contain.failedSamples}/${contain.totalSamples})`)
    }
    if (planningVolumes.length === 0) L.push('(no planning volumes defined)')
    return L.join('\n')
}

/** Enable/disable the clinical-program overlay + editing affordance. */
export function setClinicalProgramEnabled(enabled: boolean): void {
    if (programState.enabled === enabled) return
    programState.enabled = enabled
    // Defensive: guarantee the decorator is attached whenever the overlay is
    // turned on (independent of the asset-decorator lifecycle). Idempotent.
    if (enabled) { ensureClinicalProgramDecoratorRegistered(); requestAuthoritativeFootprintsForAssignments() }
    notifyProgram()
}

/** Set the active storey used for overlay storey-filtering. */
export function setClinicalProgramActiveStorey(storeyId: string | undefined): void {
    if (programState.activeStoreyId === storeyId) return
    programState.activeStoreyId = storeyId
    notifyProgram()
}

/** Select a BIM space for program editing (BIM_SPACE_ID; §12). */
export function setClinicalProgramSelectedSpace(bimSpaceId: string | undefined): void {
    if (programState.selectedSpaceId === bimSpaceId) return
    programState.selectedSpaceId = bimSpaceId
    // Build 1A.2: selecting a room lazily requests its exact authoritative mesh
    // (on-demand, idempotent, cached — never eager/all-rooms). This resolves the
    // honest EXACT vs RANGE geometry status for the selected room; the async
    // completion calls notifyProgram() so the panel refreshes reactively. Never
    // creates an assignment or a planning volume.
    if (bimSpaceId) void ensureAuthoritativeRoomFootprint(bimSpaceId)
    notifyProgram()
}

/** The rooms the UI can select from (authoritative cached BIM spaces). */
export function getClinicalProgramRooms(): readonly SpatialRoomReference[] {
    return cachedModelSemantics.rooms
}

// ===========================================================================
// BUILD 1A — GENERIC BIM ROOM-VOLUME DISCOVERY + ACTIVATION (all valid rooms)
// ===========================================================================
//
// Generalizes the accepted Uptake-01 spatial proof: every discovered BIM room
// becomes spatially addressable + volume-aware WITHOUT auto-creating any
// ClinicalPlanningVolume (§6). Exact-mesh extraction stays LAZY (§8/§23): the
// discovered-room model only REPORTS cache availability; extraction happens
// on-demand when a room is inspected/activated. Discovery is iModel-scoped by
// the active programState.iModelId + cachedModelSemantics (cleared on switch).

/** Build the per-room cache facts from the on-demand authoritative footprint map. */
function roomMeshCacheFacts(bimSpaceId: string): RoomMeshCacheFacts {
    const e = authoritativeFootprints.get(bimSpaceId)
    if (!e) return { exactMeshCached: false, exactMeshOk: false }
    return {
        exactMeshCached: true,
        exactMeshOk: !!e.ok,
        vertexCount: e.volume?.vertexCount ?? 0,
        triangleCount: e.volume?.triangleCount ?? 0,
        closedMesh: e.volume?.closedMesh ?? false,
        extractionReason: e.ok ? undefined : e.reason,
    }
}

/** Assemble the cache-facts record for every currently-discovered room. */
function allRoomMeshCacheFacts(): Record<string, RoomMeshCacheFacts> {
    const out: Record<string, RoomMeshCacheFacts> = {}
    for (const room of cachedModelSemantics.rooms) {
        if (room.roomId) out[room.roomId] = roomMeshCacheFacts(room.roomId)
    }
    return out
}

/**
 * The GENERIC discovered room-volume model for the active BIM. Reflects live
 * assignment + planning-volume + lazy-mesh-cache state; NEVER creates any of
 * them. Camera-independent, iModel-scoped. (§5, §6, §7, §9)
 */
export function getDiscoveredRoomVolumes(): DiscoveredRoomVolume[] {
    return discoverRoomVolumes({
        iModelId: programState.iModelId,
        rooms: cachedModelSemantics.rooms,
        storeys: programStoreyRanges,
        meshCacheByRoom: allRoomMeshCacheFacts(),
        assignments: programState.assignments.map((a) => ({
            bimSpaceId: a.bimSpaceId,
            clinicalFunction: a.clinicalFunction,
            mrtDisplayName: a.mrtDisplayName,
        })),
        planningVolumeParentIds: planningVolumes.map((v) => v.parentBimSpaceId),
    })
}

/** Bounded room-volume discovery summary for the active BIM (§24). */
export function getRoomVolumeDiscoverySummary(): RoomVolumeDiscoverySummary {
    return summarizeRoomVolumeDiscovery({
        iModelId: programState.iModelId,
        discovered: getDiscoveredRoomVolumes(),
        planningVolumeCount: planningVolumes.length,
    })
}

/**
 * Build 1A.1 — the UI-facing room-discovery lifecycle for the room selector.
 * Returns the explicit status, the storey-filtered room count, and the label the
 * selector should show (never a false READY-zero). The count reflects the active
 * storey filter (view subset only — the underlying discovery authority is not
 * mutated by filtering).
 */
export function getRoomDiscoveryUiStatus(): {
    status: RoomDiscoveryState['status']
    baseRoomCount: number
    filteredRoomCount: number
    label: string
} {
    const discovered = getDiscoveredRoomVolumes()
    // Build 1A.3: canonical storey filter (a specific storey shows ONLY its own
    // rooms; unresolved-storey rooms appear only under "All"). Fixes the observed
    // First=Second=153 collapse where the count/options ignored the storey change.
    const filtered = filterDiscoveredRoomsByStorey(discovered, programState.activeStoreyId)
    const label = roomSelectorLabel({ status: roomDiscoveryState.status, filteredRoomCount: filtered.length })
    return {
        status: roomDiscoveryState.status,
        baseRoomCount: discovered.length,
        filteredRoomCount: filtered.length,
        label,
    }
}

/**
 * Build 1A.3 — the storey-filtered discovered-room OPTIONS for the Clinical
 * Program room selector. Recomputed from the immutable base discovery + the
 * current canonical storey filter (programState.activeStoreyId). The count of
 * this list is exactly the selector count (getRoomDiscoveryUiStatus.filteredRoomCount).
 */
export function getDiscoveredRoomOptions(): DiscoveredRoomVolume[] {
    return filterDiscoveredRoomsByStorey(getDiscoveredRoomVolumes(), programState.activeStoreyId)
}

/**
 * Build 1A.3 — whether the currently SELECTED room is outside the active storey
 * filter. The UI uses this to clear the visible selection (out-of-filter policy)
 * WITHOUT deleting the domain assignment or planning volume.
 */
export function isSelectedRoomOutsideActiveStorey(): boolean {
    const sel = programState.selectedSpaceId
    if (!sel || !programState.activeStoreyId) return false
    const options = getDiscoveredRoomOptions()
    return !options.some((r) => r.bimSpaceId === sel)
}

/**
 * DEV: GENERIC BIM room-discovery diagnostic (§17). Bounded; never dumps raw room
 * payloads. Reports the live authority chain so a 200 → 0 style regression can be
 * localized to the exact seam. Read-only (does NOT force a refresh).
 */
export async function diagnoseBimRoomDiscovery(): Promise<string> {
    const { getActiveSemanticsIModelId } = await import('./bentleySpatialAdapter')
    let productViewportIModelId: string | undefined
    let viewportFound = false
    try {
        const { viewport } = resolveActiveProductViewport()
        viewportFound = !!viewport
        productViewportIModelId = viewport?.iModel?.iModelId
    } catch { /* runtime not ready */ }
    const semanticsIModelId = getActiveSemanticsIModelId()
    const discovered = getDiscoveredRoomVolumes()
    const activeStorey = programState.activeStoreyId
    const filtered = filterDiscoveredRoomsByStorey(discovered, activeStorey)
    const L: string[] = ['=== BIM ROOM DISCOVERY DIAGNOSTIC ===']
    L.push(`ACTIVE_PRODUCT_VIEWPORT_FOUND = ${viewportFound ? 'YES' : 'NO'}`)
    L.push(`PRODUCT_VIEWPORT_IMODEL_ID = ${productViewportIModelId ?? '(none)'}`)
    L.push(`CLINICAL_PROGRAM_IMODEL_ID = ${programState.iModelId || '(none)'}`)
    L.push(`SEMANTICS_CACHE_OWNER_IMODEL_ID = ${roomDiscoveryState.ownerIModelId ?? '(none)'}`)
    L.push(`LIVE_SEMANTICS_IMODEL_ID = ${semanticsIModelId ?? '(none)'}`)
    L.push(`SEMANTICS_STATUS = ${roomDiscoveryState.status}`)
    L.push(`SEMANTICS_REFRESH_IN_FLIGHT = ${semanticsRefreshInFlight ? 'YES' : 'NO'}`)
    L.push(`SEMANTICS_ROOM_COUNT = ${cachedModelSemantics.rooms.length}`)
    L.push(`BASE_DISCOVERED_ROOM_COUNT = ${discovered.length}`)
    L.push(`ACTIVE_STOREY_FILTER = ${activeStorey ?? 'ALL'}`)
    L.push(`FILTERED_ROOM_COUNT = ${filtered.length}`)
    L.push(`CLINICAL_PROGRAM_ON = ${programState.enabled ? 'YES' : 'NO'}`)
    L.push(`SELECTED_ROOM_ID = ${programState.selectedSpaceId ?? '(none)'}`)
    L.push(`SELECTED_ROOM_OUTSIDE_ACTIVE_STOREY = ${isSelectedRoomOutsideActiveStorey() ? 'YES' : 'NO'}`)
    // Build 1A.3 — bounded per-storey facts (never a full room dump).
    const counts = countRoomsByStorey(discovered)
    L.push('--- storey counts ---')
    L.push(`ALL = ${counts.all}`)
    L.push(`UNRESOLVED_STOREY = ${counts.unresolved}`)
    for (const s of programStoreyRanges) {
        const sample = discovered.filter((r) => r.storeyId === s.id).slice(0, 3)
            .map((r) => `${r.bimSpaceId}[${r.originalBimLabel}]`).join(', ')
        L.push(`${s.label} (${s.id}) = ${counts.byStorey[s.id] ?? 0}${sample ? ` | e.g. ${sample}` : ''}`)
    }
    L.push(`LAST_REFRESH_RESULT = ${roomDiscoveryState.lastRefreshResult ?? '(none)'}`)
    L.push(`LAST_REFRESH_ERROR_CLASS = ${roomDiscoveryState.lastRefreshErrorClass ?? '(none)'}`)
    L.push(`STALE_REFRESH_DISCARDED_COUNT = ${roomDiscoveryState.staleDiscardedCount}`)
    L.push(`SELECTOR_LABEL = ${roomSelectorLabel({ status: roomDiscoveryState.status, filteredRoomCount: filtered.length })}`)
    return L.join('\n')
}

/**
 * Read-only inspection of ANY discovered room's authoritative volume (§10).
 * Triggers LAZY exact-mesh extraction for the inspected room ONLY (never every
 * room), then returns the honest discovered-room model. Inspection NEVER creates
 * a ClinicalPlanningVolume or a Clinical Program assignment.
 */
export async function inspectRoomVolume(bimSpaceId: string): Promise<DiscoveredRoomVolume | undefined> {
    if (!bimSpaceId) return undefined
    // Lazy on-demand extraction for the inspected room only (idempotent + cached).
    await ensureAuthoritativeRoomFootprint(bimSpaceId)
    return getDiscoveredRoomVolumes().find((r) => r.bimSpaceId === bimSpaceId)
}

/**
 * DEV: GENERIC selected-room volume diagnostic (§25) — targets ANY selected
 * room, not only Uptake 01. Defaults to the currently selected space. Read-only;
 * lazily extracts the exact mesh for the target room, computes live containment
 * (only when a planning volume exists), and composes a bounded report.
 */
export async function diagnoseSelectedRoomVolume(bimSpaceId?: string): Promise<string> {
    const targetId = bimSpaceId
        ?? programState.selectedSpaceId
        ?? programState.assignments.find((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')?.bimSpaceId
    if (!targetId) return 'NO_SELECTED_ROOM: select a BIM room first.'
    // Ensure semantics are loaded so the room is discoverable (read-only).
    if (!semanticsLoaded || cachedModelSemantics.rooms.length === 0) {
        try { await refreshModelSemantics() } catch { /* offline */ }
    }
    await ensureAuthoritativeRoomFootprint(targetId)
    const room = getDiscoveredRoomVolumes().find((r) => r.bimSpaceId === targetId)
    if (!room) return `ROOM_NOT_DISCOVERED: ${targetId}`
    const entry = authoritativeFootprints.get(targetId)
    const pv = planningVolumes.find((v) => v.parentBimSpaceId === targetId)
    const containment = pv
        ? (await getClinicalVolumeContainment(targetId)).status
        : 'NOT_EVALUATED' as const
    const d = buildSelectedRoomVolumeDiagnostic({
        room,
        closedMesh: entry?.volume?.closedMesh ?? false,
        planningVolumeId: pv?.id,
        containmentStatus: containment,
        uptakeBaselineBimSpaceId: '0x200000001f1',
    })
    return formatSelectedRoomVolumeDiagnostic(d)
}

/**
 * Assign (or update) the single primary clinical function for a BIM space, then
 * persist. Returns the resolved assignment or a bounded failure reason. Never
 * touches Bentley identity (§4/§53/§77).
 */
export function assignClinicalProgram(input: {
    bimSpace: BimSpaceRef
    clinicalFunction: ClinicalFunction
    requestedDisplayName?: string
}): { ok: true; assignment: ClinicalProgramAssignment } | { ok: false; reason: string } {
    const result = pureAssignClinicalFunction({
        bimSpace: input.bimSpace,
        clinicalFunction: input.clinicalFunction,
        requestedDisplayName: input.requestedDisplayName,
        existingAssignments: programState.assignments,
    })
    if (!result.ok) return result
    programState.assignments = result.assignments
    persistProgram()
    // Extract the true room geometry for the newly-assigned space (read-only).
    if (result.assignment.clinicalFunction !== 'UNASSIGNED_EXISTING') void ensureAuthoritativeRoomFootprint(result.assignment.bimSpaceId)
    notifyProgram()
    return { ok: true, assignment: result.assignment }
}

/** Reset a BIM space back to UNASSIGNED_EXISTING (remove override), then persist. */
export function resetClinicalProgram(bimSpaceId: string): void {
    programState.assignments = pureResetAssignment(bimSpaceId, programState.assignments)
    persistProgram()
    // No orphans: a reset assignment removes its DRAFT child volume. A LOCKED
    // volume is retained (the UI requires an explicit unlock before reset can
    // clear it) — so we never silently discard locked planning geometry.
    const child = planningVolumes.find((v) => v.parentBimSpaceId === bimSpaceId)
    if (child && child.lifecycleState !== 'LOCKED') {
        planningVolumes = planningVolumes.filter((v) => v.parentBimSpaceId !== bimSpaceId)
        persistPlanningVolumes()
    }
    notifyProgram()
}

/** The active (non-UNASSIGNED) assignment for a space, if any. */
export function getClinicalProgramAssignment(bimSpaceId: string): ClinicalProgramAssignment | undefined {
    return pureAssignmentForSpace(bimSpaceId, programState.assignments)
}

/** Compact program summary (assigned count + count by function). */
export function getClinicalProgramSummary(): ReturnType<typeof pureSummarizeProgram> {
    return pureSummarizeProgram(programState.assignments)
}

/** Informational PET-demo completeness (never auto-creates rooms; §37/§75). */
export function getClinicalProgramCompleteness(): ReturnType<typeof pureCheckProgramCompleteness> {
    return pureCheckProgramCompleteness(programState.assignments)
}

// --- Storey binning for the program overlay's storey filter ---------------
// The room semantics carry a floorId that is not guaranteed to equal the
// storey-selector ids (they come from different queries). To make the storey
// filter reliable we Z-bin each room footprint into the loaded storey ranges.

let programStoreyRanges: StoreyZRange[] = []
const roomStoreyIdCache = new Map<string, string | undefined>()

/** Provide the storey Z-ranges used to bin rooms for storey-filtering. */
export function setClinicalProgramStoreyRanges(ranges: readonly StoreyZRange[]): void {
    programStoreyRanges = ranges.slice()
    roomStoreyIdCache.clear()
    notifyProgram()
}

function resolveRoomStoreyIdCached(roomId: string): string | undefined {
    if (roomStoreyIdCache.has(roomId)) return roomStoreyIdCache.get(roomId)
    const room = cachedModelSemantics.rooms.find((r) => r.roomId === roomId)
    let storeyId: string | undefined
    if (room) {
        const fp = deriveRoomFootprint(room)
        if (fp) storeyId = resolveRoomStoreyId(fp, programStoreyRanges)
    }
    roomStoreyIdCache.set(roomId, storeyId)
    return storeyId
}

/** Room storey id for the UI (same Z-binning the decorator uses). */
export function getClinicalProgramRoomStoreyId(roomId: string): string | undefined {
    return resolveRoomStoreyIdCached(roomId)
}

// --- Authoritative IfcSpace geometry (true room footprint) ------------------
// When an assigned space has EXACT_SPACE_GEOMETRY, we replace the range
// rectangle with the true footprint extracted (read-only) from the geometry
// stream. Extraction is async + cached per bimSpaceId; the decorator reads the
// cached world footprint. Never a silent range fallback.

interface AuthoritativeFootprintEntry {
    outerLoop: { x: number; y: number }[]
    holes: { x: number; y: number }[][]
    floorZ: number
    interiorAnchor: { x: number; y: number; z: number }
    outerLoopPointCount: number
    holeCount: number
    area: number
    ok: boolean
    reason?: string
    // 3D volume characterization + retained mesh (view-only volume rendering).
    volume?: {
        zLow: number; zHigh: number; height: number; vertexCount: number; triangleCount: number
        componentCount: number; closedMesh: boolean; horizontalFaceCount: number; verticalFaceCount: number
        worldRangeLow: { x: number; y: number; z: number }; worldRangeHigh: { x: number; y: number; z: number }
    }
    mesh?: { vertices: readonly { x: number; y: number; z: number }[]; triangles: readonly number[] }
    resultBytes?: number
    polyfaceCount?: number
}

const authoritativeFootprints = new Map<string, AuthoritativeFootprintEntry>()
/** In-flight extraction promises, keyed by bimSpaceId (await-to-completion dedupe). */
const authoritativeInFlight = new Map<string, Promise<void>>()

/** The cached authoritative footprint for a space (undefined if not extracted). */
export function getAuthoritativeRoomFootprint(bimSpaceId: string): AuthoritativeFootprintEntry | undefined {
    return authoritativeFootprints.get(bimSpaceId)
}

/**
 * Ensure the authoritative geometry for an assigned space has been extracted
 * (read-only, once per space). On success caches the true footprint + interior
 * anchor and redraws. Never falls back to the range rectangle here.
 */
export async function ensureAuthoritativeRoomFootprint(bimSpaceId: string): Promise<void> {
    if (!bimSpaceId) return
    // Already extracted successfully -> nothing to do.
    if (authoritativeFootprints.get(bimSpaceId)?.ok) return
    // De-dupe by an IN-FLIGHT PROMISE (not a boolean): awaiting this call always
    // resolves AFTER extraction completes, so live containment sees the mesh
    // (fixes the (0/0) race where the boolean guard returned before the mesh
    // was cached).
    const existing = authoritativeInFlight.get(bimSpaceId)
    if (existing) { await existing; return }
    const run = (async () => {
        try {
            const { extractAuthoritativeRoomGeometry } = await import('./authoritativeRoomGeometryProbe')
            const { viewport } = resolveActiveProductViewport()
            const geom = await extractAuthoritativeRoomGeometry(bimSpaceId, viewport?.iModel)
            authoritativeFootprints.set(bimSpaceId, {
                outerLoop: geom.footprint.outerLoop,
                holes: geom.footprint.holes,
                floorZ: geom.footprint.floorZ,
                interiorAnchor: geom.interiorAnchor,
                outerLoopPointCount: geom.outerLoopPointCount,
                holeCount: geom.holeCount,
                area: geom.footprintArea,
                ok: geom.ok,
                reason: geom.reason,
                volume: geom.volume,
                mesh: geom.mesh,
                resultBytes: geom.resultBytes,
                polyfaceCount: geom.polyfaceCount,
            })
                ; (viewport ?? IModelApp.viewManager?.selectedView)?.invalidateDecorations()
            // Parent mesh now available -> tell observers so containment recomputes.
            notifyProgram()
        } catch { /* leave uncached; a later call retries */ }
        finally { authoritativeInFlight.delete(bimSpaceId) }
    })()
    authoritativeInFlight.set(bimSpaceId, run)
    await run
}

/** Kick off authoritative extraction for every currently assigned space. */
function requestAuthoritativeFootprintsForAssignments(): void {
    for (const a of programState.assignments) {
        if (a.clinicalFunction !== 'UNASSIGNED_EXISTING' && a.bimSpaceId) void ensureAuthoritativeRoomFootprint(a.bimSpaceId)
    }
}

/**
 * The honest geometry-quality of a room's overlay (for restrained UI disclosure).
 * Returns e.g. { quality: 'BIM_RANGE_APPROXIMATION', description: 'BIM range approximation' }.
 */
export function getClinicalProgramRoomGeometryQuality(roomId: string): { quality: string; description: string } | undefined {
    const room = cachedModelSemantics.rooms.find((r) => r.roomId === roomId)
    if (!room) return undefined
    // Build 1A.2: prefer the cached AUTHORITATIVE exact footprint when it has been
    // lazily extracted for this room — so the product status reflects real
    // EXACT_ROOM_BOUNDARY rather than remaining stuck at BIM_RANGE_APPROXIMATION.
    // The range fallback stays honest when no exact mesh is available.
    const cached = authoritativeFootprints.get(roomId)
    const exactBoundary = cached?.ok && cached.outerLoop && cached.outerLoop.length >= 3
        ? { ring: cached.outerLoop, elevation: cached.floorZ }
        : undefined
    const anchor = resolveClinicalProgramFacilityAnchor({ room, storeys: programStoreyRanges, exactBoundary })
    return { quality: anchor.geometryQuality, description: describeGeometryQuality(anchor.geometryQuality) }
}

/**
 * DEV: run the READ-ONLY spatial-authority probe against the persisted target
 * assignment (identity authority = its bimSpaceId; never a name/nearest search).
 * Diagnostic-only — never changes the overlay.
 */
export async function diagnoseRoomSpatialAuthority(): Promise<string> {
    const { probeRoomSpatialAuthority } = await import('./roomSpatialAuthorityProbe')
    // Ensure semantics are loaded so the original label is available (read-only).
    if (!semanticsLoaded || cachedModelSemantics.rooms.length === 0) {
        try { await refreshModelSemantics() } catch { /* offline */ }
    }
    const target = programState.assignments.find((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')
    if (!target) return 'NO_ACTIVE_ASSIGNMENT: assign a clinical function first (target defaults to the persisted Uptake 01).'
    return probeRoomSpatialAuthority({ bimSpaceId: target.bimSpaceId, originalBimLabel: target.originalBimLabel })
}

/**
 * DEV: bounded diagnostic of the AUTHORITATIVE IfcSpace geometry extracted for
 * the persisted target (counts + footprint area + anchor — never a raw dump).
 */
export async function diagnoseAuthoritativeRoomGeometry(): Promise<string> {
    const EXPECTED_CLINIC_IMODEL_ID = '36381ef4-b5f5-4d6d-b64b-2dbd69ba26a4'
    const target = programState.assignments.find((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')
    const L: string[] = []
    L.push('=== UPTAKE 01 AUTHORITATIVE GEOMETRY ===')
    // §40 viewport-resolution entry diagnostic (bounded).
    const { viewport, source } = resolveActiveProductViewport()
    const activeIModelId = viewport?.iModel?.iModelId ?? '(none)'
    L.push(`VIEWPORT_RESOLUTION_SOURCE = ${source}`)
    L.push(`ACTIVE_VIEWPORT_FOUND = ${viewport ? 'YES' : 'NO'}`)
    L.push(`ACTIVE_EXTRACTION_IMODEL_ID = ${activeIModelId}`)
    L.push(`EXPECTED_CLINIC_IMODEL_ID = ${EXPECTED_CLINIC_IMODEL_ID}`)
    L.push(`IMODEL_MATCH = ${activeIModelId === EXPECTED_CLINIC_IMODEL_ID ? 'YES' : 'NO'}`)
    if (!target) { L.push('NO_ACTIVE_ASSIGNMENT'); return L.join('\n') }
    L.push(`TARGET = ${target.originalBimLabel}`)
    L.push(`BIM_SPACE_ID = ${target.bimSpaceId}`)
    // Re-run extraction fresh so GENERATE_ELEMENT_MESHES fields reflect this call.
    authoritativeInFlight.delete(target.bimSpaceId)
    authoritativeFootprints.delete(target.bimSpaceId)
    await ensureAuthoritativeRoomFootprint(target.bimSpaceId)
    const e = authoritativeFootprints.get(target.bimSpaceId)
    L.push(`GENERATE_ELEMENT_MESHES_CALLED = ${viewport ? 'YES' : 'NO'}`)
    if (!e) { L.push('extraction pending / unavailable'); return L.join('\n') }
    if (!e.ok) {
        L.push(`geometrySource = AUTHORITATIVE_IFCSPACE_GEOMETRY`)
        L.push(`geometryQuality = NOT_AVAILABLE (extraction failed: ${e.reason ?? 'unknown'})`)
        L.push(`SILENT_RANGE_RECTANGLE_FALLBACK = NO (failure is disclosed, not hidden)`)
        return L.join('\n')
    }
    L.push(`GENERATE_ELEMENT_MESHES_RESULT_BYTES = ${e.resultBytes ?? 0}`)
    L.push(`POLYFACE_COUNT = ${e.polyfaceCount ?? 0}`)
    L.push(`geometrySource = AUTHORITATIVE_IFCSPACE_GEOMETRY`)
    L.push(`geometryQuality = EXACT_ROOM_BOUNDARY`)
    L.push(`outerLoopPointCount = ${e.outerLoopPointCount}`)
    L.push(`holeCount = ${e.holeCount}`)
    L.push(`footprintArea = ${e.area.toFixed(2)} m^2`)
    L.push(`facilityAnchor = (${e.interiorAnchor.x.toFixed(2)},${e.interiorAnchor.y.toFixed(2)},${e.interiorAnchor.z.toFixed(2)})`)
    L.push(`rangeFallbackUsed = NO`)
    // §9 3D characterization.
    if (e.volume) {
        const v = e.volume
        L.push('--- 3D characterization ---')
        L.push(`VERTEX_COUNT = ${v.vertexCount} TRIANGLE_COUNT = ${v.triangleCount}`)
        L.push(`WORLD_RANGE_LOW = (${v.worldRangeLow.x.toFixed(2)},${v.worldRangeLow.y.toFixed(2)},${v.worldRangeLow.z.toFixed(2)})`)
        L.push(`WORLD_RANGE_HIGH = (${v.worldRangeHigh.x.toFixed(2)},${v.worldRangeHigh.y.toFixed(2)},${v.worldRangeHigh.z.toFixed(2)})`)
        L.push(`zLow = ${v.zLow.toFixed(2)} zHigh = ${v.zHigh.toFixed(2)} height = ${v.height.toFixed(2)}`)
        L.push(`closedMesh = ${v.closedMesh ? 'YES' : 'NO'} components = ${v.componentCount}`)
        L.push(`horizontalFaces = ${v.horizontalFaceCount} verticalFaces = ${v.verticalFaceCount}`)
    }
    return L.join('\n')
}

/**
 * DEV: instrument the LIVE clinical-program overlay rendering chain for the
 * current assigned room(s) — primarily the persisted Uptake 01 — and classify
 * the single primary failure (why it is / isn't visible on the building).
 *
 * Read-only, view-only, no Bentley writes, no token logging, no persistence
 * mutation. Refreshes semantics once if empty so the trace reflects live rooms.
 */
export async function diagnoseClinicalProgramOverlay(): Promise<string> {
    const { deriveRoomFootprint: deriveFp, resolveRoomStoreyId: resolveStorey } = await import('./planningPlan')
    const { deriveClinicalProgramOverlay } = await import('./clinicalProgramOverlay')
    const { classifyClinicalOverlayFailure, summarizeClinicalOverlayObservation } = await import('./clinicalOverlayDiagnostics')

    // Ensure rooms are loaded (read-only).
    if (!semanticsLoaded || cachedModelSemantics.rooms.length === 0) {
        try { await refreshModelSemantics() } catch { /* offline / no iModel */ }
    }

    const assignments = programState.assignments
    // Target = the first active (non-UNASSIGNED) assignment (the persisted Uptake 01).
    const target = assignments.find((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')
    const lines: string[] = []
    lines.push('=== CLINICAL PROGRAM OVERLAY DIAGNOSTIC ===')
    lines.push(`iModel=${programState.iModelId || '(unbound)'}`)
    lines.push(`programEnabled=${programState.enabled} activeStorey=${programState.activeStoreyId ?? 'ALL'} selected=${programState.selectedSpaceId ?? 'none'}`)
    lines.push(`assignments=${assignments.length} storeyRanges=${programStoreyRanges.length} rooms=${cachedModelSemantics.rooms.length}`)

    if (!target) {
        lines.push('assignmentFound=NO — no active clinical-program assignment to trace.')
        return lines.join('\n')
    }

    // §8 assignment record (sanitized).
    lines.push('--- assignment ---')
    lines.push(`mrtDisplayName=${target.mrtDisplayName} clinicalFunction=${target.clinicalFunction}`)
    lines.push(`bimSpaceId present=${target.bimSpaceId ? 'YES' : 'NO'} bimStoreyId present=${target.bimStoreyId ? 'YES' : 'NO'}`)
    lines.push(`originalBimLabel=${target.originalBimLabel}`)

    // §9 BIM space match (exact bimSpaceId).
    const matches = cachedModelSemantics.rooms.filter((r) => r.roomId === target.bimSpaceId)
    lines.push('--- bim space match ---')
    lines.push(`matchCount=${matches.length}`)

    const room = matches[0]
    // §12 room identity.
    if (room) {
        lines.push('--- room identity ---')
        lines.push(`displayName=${room.displayName} floorId present=${room.floorId ? 'YES' : 'NO'} range present=${room.range ? 'YES' : 'NO'} geometryType=${room.geometryType} confidence=${room.confidence}`)
        // §13 range.
        if (room.range) {
            const { low, high } = room.range
            lines.push(`range low=(${low.x.toFixed(1)},${low.y.toFixed(1)},${low.z.toFixed(1)}) high=(${high.x.toFixed(1)},${high.y.toFixed(1)},${high.z.toFixed(1)}) w=${(high.x - low.x).toFixed(1)} d=${(high.y - low.y).toFixed(1)} h=${(high.z - low.z).toFixed(1)}`)
        } else {
            lines.push('range=NOT_AVAILABLE')
        }
    }

    // §14 footprint.
    const footprint = room ? deriveFp(room) : undefined
    lines.push('--- footprint ---')
    if (footprint) {
        const cx = footprint.ring.reduce((s, p) => s + p.x, 0) / footprint.ring.length
        const cy = footprint.ring.reduce((s, p) => s + p.y, 0) / footprint.ring.length
        lines.push(`found=YES points=${footprint.ring.length} elevation=${footprint.elevation.toFixed(2)} centroid=(${cx.toFixed(1)},${cy.toFixed(1)}) rangeDerived=YES`)
    } else {
        lines.push('found=NO')
    }

    // §16 storey mapping.
    const roomStoreyId = footprint ? resolveStorey(footprint, programStoreyRanges) : undefined
    const roomStorey = programStoreyRanges.find((s) => s.id === roomStoreyId)
    lines.push('--- storey mapping ---')
    if (footprint) {
        const midZ = (footprint.zLow + footprint.zHigh) / 2
        lines.push(`midZ=${midZ.toFixed(2)} storeys=${programStoreyRanges.length} resolvedStoreyId=${roomStoreyId ?? 'none'} resolvedStoreyLabel=${roomStorey?.label ?? 'none'}`)
    }
    const activeStorey = programState.activeStoreyId
    const storeyMatch = activeStorey === undefined ? true : (roomStoreyId !== undefined && roomStoreyId === activeStorey)
    lines.push(`activeFilter=${activeStorey ?? 'ALL'} storeyMatch=${storeyMatch ? 'YES' : 'NO'}`)

    // §18 pure overlay model.
    const overlay = deriveClinicalProgramOverlay({
        rooms: cachedModelSemantics.rooms,
        assignments,
        activeStoreyId: programState.activeStoreyId,
        selectedRoomId: programState.selectedSpaceId,
        storeys: programStoreyRanges,
    })
    const targetRecord = overlay.find((o) => o.bimSpaceId === target.bimSpaceId)
    lines.push('--- overlay model ---')
    lines.push(`records=${overlay.length} targetFound=${targetRecord ? 'YES' : 'NO'}`)
    if (targetRecord) lines.push(`priority=${targetRecord.priority} assigned=${targetRecord.assigned} selected=${targetRecord.selected} anchor=(${targetRecord.anchor.x.toFixed(1)},${targetRecord.anchor.y.toFixed(1)},${targetRecord.anchor.z.toFixed(2)})`)

    // §38 FIXED PHYSICAL LOCATION: facility anchor vs display anchor + honesty.
    if (targetRecord) {
        const fa = targetRecord.facilityAnchor
        const da = targetRecord.displayAnchor
        lines.push('--- fixed physical location ---')
        lines.push(`geometrySource=${targetRecord.geometrySource} geometryQuality=${targetRecord.geometryQuality}`)
        lines.push(`facilityAnchor=(${fa.x.toFixed(2)},${fa.y.toFixed(2)},${fa.z.toFixed(2)})`)
        lines.push(`displayAnchor=(${da.x.toFixed(2)},${da.y.toFixed(2)},${da.z.toFixed(2)}) zLift=${(da.z - fa.z).toFixed(2)}`)
        lines.push(`boundaryPointCount=${targetRecord.boundary?.length ?? 0} rangeFallbackUsed=${targetRecord.geometrySource === 'BIM_SPATIAL_RANGE' ? 'YES' : 'NO'}`)
        lines.push(`facilityAnchorCameraDependence=NONE (world coordinates; worldToView only transforms the screen position)`)
        // Authoritative IfcSpace geometry, if extracted.
        const auth = authoritativeFootprints.get(target.bimSpaceId)
        if (auth) {
            lines.push('--- authoritative geometry ---')
            if (auth.ok) {
                lines.push(`geometrySource=AUTHORITATIVE_IFCSPACE_GEOMETRY geometryQuality=EXACT_ROOM_BOUNDARY`)
                lines.push(`outerLoopPointCount=${auth.outerLoopPointCount} holeCount=${auth.holeCount} area=${auth.area.toFixed(2)} rangeFallbackUsed=NO`)
                lines.push(`interiorAnchor=(${auth.interiorAnchor.x.toFixed(2)},${auth.interiorAnchor.y.toFixed(2)},${auth.interiorAnchor.z.toFixed(2)})`)
            } else {
                lines.push(`geometryQuality=NOT_AVAILABLE (extraction failed: ${auth.reason ?? 'unknown'}) — no silent range fallback`)
            }
        } else {
            lines.push('--- authoritative geometry --- (extraction pending; will render true footprint when ready)')
        }
    }

    // §20/§22 decorator state.
    const dec = clinicalProgramDecorator
    const registered = !!(dec && removeClinicalProgramDecorator)
    lines.push('--- decorator ---')
    lines.push(`registered=${registered ? 'YES' : 'NO'} enabled=${programState.enabled ? 'YES' : 'NO'} decorateCount=${dec?.diag.decorateCount ?? 0} lastDecorateAt=${dec?.diag.lastDecorateAt ?? 'none'}`)
    if (dec) lines.push(`lastSeen: assignments=${dec.diag.assignmentCountSeen} rooms=${dec.diag.roomCountSeen} storeyRanges=${dec.diag.storeyRangeCountSeen} activeStorey=${dec.diag.activeStoreySeen ?? 'ALL'} overlay=${dec.diag.overlayCountSeen} enabled=${dec.diag.lastEnabled} mode=${dec.diag.lastMode}`)

    // §23 draw attempt for target.
    const spaceId = target.bimSpaceId
    const footprintDrawn = !!dec?.diag.footprintDrawnFor.has(spaceId)
    const labelDrawn = !!dec?.diag.labelDrawnFor.has(spaceId)
    const graphicCreated = !!dec?.diag.footprintGraphicCreatedFor.has(spaceId)
    const htmlAttached = !!dec?.diag.htmlLabelAttachedFor.has(spaceId)
    lines.push('--- draw attempt (target) ---')
    lines.push(`footprintDrawAttempted=${footprintDrawn ? 'YES' : 'NO'} labelDrawAttempted=${labelDrawn ? 'YES' : 'NO'} graphicType=${dec?.diag.graphicType ?? '?'} zLift=${dec?.diag.zLift ?? '?'}`)

    // §25 world-to-view for the target anchor.
    let anchorInside = false
    const vp = IModelApp.viewManager?.selectedView
    if (vp && targetRecord) {
        try {
            const world = { x: targetRecord.anchor.x, y: targetRecord.anchor.y, z: targetRecord.anchor.z }
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const view = (vp as any).worldToView(world)
            const w = vp.viewRect?.width ?? 0
            const h = vp.viewRect?.height ?? 0
            anchorInside = Number.isFinite(view?.x) && Number.isFinite(view?.y) && view.x >= 0 && view.y >= 0 && view.x <= w && view.y <= h
            lines.push('--- world to view ---')
            lines.push(`world=(${world.x.toFixed(1)},${world.y.toFixed(1)},${world.z.toFixed(2)}) view=(${Number(view?.x).toFixed(0)},${Number(view?.y).toFixed(0)}) vp=${w}x${h} inside=${anchorInside ? 'YES' : 'NO'}`)
        } catch { lines.push('--- world to view --- (unavailable)') }
    } else {
        lines.push('--- world to view --- (no viewport or no target record)')
    }

    // Build the observation and classify.
    const observation = {
        assignmentFound: true,
        roomMatchCount: matches.length,
        footprintFound: !!footprint,
        activeStoreyId: programState.activeStoreyId,
        roomStoreyId,
        overlayRecordCount: overlay.length,
        targetOverlayRecordFound: !!targetRecord,
        decoratorRegistered: registered,
        decoratorEnabled: programState.enabled,
        // If the decorator has drawn since program state changed, invalidation works.
        decoratorInvalidatedAfterChange: (dec?.diag.decorateCount ?? 0) > 0,
        drawAttempted: footprintDrawn || labelDrawn,
        anchorInsideViewport: anchorInside,
        htmlLabelAttached: htmlAttached,
        footprintGraphicCreated: graphicCreated,
        overlayHiddenByLayout: false,
    }
    const cls = classifyClinicalOverlayFailure(observation)
    lines.push('--- classification ---')
    lines.push(`PROGRAM_OVERLAY_FAILURE_CLASS = ${cls}`)
    lines.push(summarizeClinicalOverlayObservation(observation, cls))

    const out = lines.join('\n')
    if (import.meta.env.DEV) console.info('[clinical-overlay-diag]\n%s', out)
    return out
}

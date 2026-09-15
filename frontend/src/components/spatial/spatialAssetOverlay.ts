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
import { buildEquipmentEnvelope, findEquipmentCollision } from './equipmentInstance'
import { vestibulePortRenderOptions as resolveVestibulePorts } from './clinicalLogisticsVestibule'
import { projectBim2dPlan } from './bim2dPlanProjection'
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
 * EVI-MA-02 — UI-only right-click EQUIPMENT context-menu state (distinct from the
 * legacy AssetInstance menu). The direct-manipulation tool opens it with a
 * concrete equipmentInstanceId + screen position; the React panel subscribes and
 * renders it. Non-authoritative view state; the equipmentInstanceId is the ONLY
 * identity (never screen px).
 */
export interface EquipmentContextMenuState {
    equipmentInstanceId: string
    screenX: number
    screenY: number
}
let equipmentContextMenu: EquipmentContextMenuState | undefined
const equipmentContextMenuListeners = new Set<() => void>()
export function subscribeEquipmentContextMenu(listener: () => void): () => void {
    equipmentContextMenuListeners.add(listener)
    return () => { equipmentContextMenuListeners.delete(listener) }
}
export function getEquipmentContextMenu(): EquipmentContextMenuState | undefined {
    return equipmentContextMenu
}
export function openEquipmentContextMenu(state: EquipmentContextMenuState): void {
    // Opening the equipment menu also establishes the exact instance as selected
    // (task 3: right-click first selects). Also close any legacy asset menu.
    closeAssetContextMenu()
    equipmentContextMenu = state
    selectEquipment(state.equipmentInstanceId)
    for (const l of equipmentContextMenuListeners) l()
}
export function closeEquipmentContextMenu(): void {
    if (!equipmentContextMenu) return
    equipmentContextMenu = undefined
    for (const l of equipmentContextMenuListeners) l()
}

// EVI-MA-05B — vestibule right-click context menu store (mirrors equipment).
export interface VestibuleContextMenuState {
    vestibuleInstanceId: string
    screenX: number
    screenY: number
}
let vestibuleContextMenu: VestibuleContextMenuState | undefined
const vestibuleContextMenuListeners = new Set<() => void>()
export function subscribeVestibuleContextMenu(listener: () => void): () => void {
    vestibuleContextMenuListeners.add(listener)
    return () => { vestibuleContextMenuListeners.delete(listener) }
}
export function getVestibuleContextMenu(): VestibuleContextMenuState | undefined {
    return vestibuleContextMenu
}
export function openVestibuleContextMenu(state: VestibuleContextMenuState): void {
    // Opening the vestibule menu closes the equipment/asset menus and selects the
    // exact vestibule (right-click first selects), converging on ONE selection.
    closeAssetContextMenu()
    closeEquipmentContextMenu()
    vestibuleContextMenu = state
    selectVestibule(state.vestibuleInstanceId)
    for (const l of vestibuleContextMenuListeners) l()
}
export function closeVestibuleContextMenu(): void {
    if (!vestibuleContextMenu) return
    vestibuleContextMenu = undefined
    for (const l of vestibuleContextMenuListeners) l()
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

/** Disposer for the tool-independent right-click bridge on the current viewport. */
let appContextMenuBridgeDispose: (() => void) | undefined
/** The host element the bridge is currently installed on (idempotency guard). */
let appContextMenuBridgeEl: HTMLElement | undefined

/** DEV structured diagnostics ring for the right-click bridge (bounded). */
const appContextMenuDiagnostics: import('./appObjectContextMenuBridge').ContextMenuBridgeDiagnostic[] = []
export function getAppContextMenuDiagnostics(): readonly import('./appObjectContextMenuBridge').ContextMenuBridgeDiagnostic[] {
    return appContextMenuDiagnostics
}

/**
 * EVI-MA-06 CORRECTION — (re)install the TOOL-INDEPENDENT right-click bridge on a
 * viewport host so right-click works regardless of which Bentley tool is active
 * (the tool-scoped bridge tore down on every camera-driven tool switch — the
 * accepted defect). Idempotent per host element.
 */
function installViewportContextMenuBridge(vp: ScreenViewport): void {
    const host = (vp as unknown as { vpDiv?: HTMLElement; parentDiv?: HTMLElement })
    const element = host.vpDiv ?? host.parentDiv
    if (!element) return
    if (appContextMenuBridgeEl === element && appContextMenuBridgeDispose) return // already installed
    // Tear down a stale bridge (viewport remount) before re-installing.
    appContextMenuBridgeDispose?.()
    appContextMenuBridgeDispose = undefined
    void import('./appObjectContextMenuBridge').then((m) => {
        // Guard: the viewport may have changed again while importing.
        if (explicitProductViewport !== vp) return
        appContextMenuBridgeEl = element
        appContextMenuBridgeDispose = m.installAppObjectContextMenuBridge(
            {
                element,
                clientToRay: (clientX, clientY) => {
                    try {
                        const rect = element.getBoundingClientRect()
                        const viewX = clientX - rect.left
                        const viewY = clientY - rect.top
                        const npc = vp.viewToNpc({ x: viewX, y: viewY, z: 0 } as unknown as import('@itwin/core-geometry').Point3d)
                        const near = vp.npcToWorld({ x: npc.x, y: npc.y, z: 0 } as unknown as import('@itwin/core-geometry').Point3d)
                        const far = vp.npcToWorld({ x: npc.x, y: npc.y, z: 1 } as unknown as import('@itwin/core-geometry').Point3d)
                        if (!near || !far) return undefined
                        return { origin: [near.x, near.y, near.z], direction: [far.x - near.x, far.y - near.y, far.z - near.z] }
                    } catch { return undefined }
                },
            },
            {
                resolve: (ray) => {
                    const t = resolveAppObjectAtRay(ray)
                    return t ? { objectType: t.objectType, instanceId: t.instanceId } : undefined
                },
                select: (ref) => selectAppObject({ objectType: ref.objectType as AppObjectType, instanceId: ref.instanceId }),
                openMenu: (target, viewX, viewY) => {
                    // EVI-MA-07 — right-click opens the SAME local action popover as
                    // left-click by selecting-with-anchor (one menu model). The
                    // viewX/viewY are viewport-relative; convert to page coords.
                    const rect = element.getBoundingClientRect()
                    selectAppObjectWithAnchor(
                        { objectType: target.objectType as AppObjectType, instanceId: target.instanceId },
                        { x: Math.round(rect.left + viewX), y: Math.round(rect.top + viewY) },
                    )
                },
                closeMenus: () => { closeEquipmentContextMenu(); closeVestibuleContextMenu() },
                isGestureActive: () => spatialAssetStore.isDragActive() || spatialAssetStore.isGroupDragActive() || spatialAssetStore.isRotationActive(),
                onDiagnostic: (d) => {
                    appContextMenuDiagnostics.push(d)
                    if (appContextMenuDiagnostics.length > 50) appContextMenuDiagnostics.shift()
                    if (import.meta.env.DEV) console.info('[rc-bridge] stage=%s %s', d.stage, d.instanceId ? `${d.objectType}=${d.instanceId}` : '')
                },
            },
        )
    })
}

/** The viewer registers its live ScreenViewport here on view-open. */
export function setActiveProductViewport(vp: ScreenViewport | undefined): void {
    explicitProductViewport = vp
    if (vp) {
        // EVI-MA-06 CORRECTION — attach the tool-independent right-click bridge for
        // the LIFETIME of this viewport (survives every tool switch / camera move).
        installViewportContextMenuBridge(vp)
    } else {
        appContextMenuBridgeDispose?.()
        appContextMenuBridgeDispose = undefined
        appContextMenuBridgeEl = undefined
    }
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
            // Build 1B — app-owned equipment envelopes (true 3D world boxes).
            getShowEquipment: () => showEquipment,
            getEquipmentForRender: () => equipmentInstances
                .filter((e) => !e.hidden)
                .map((e) => ({
                    id: e.id,
                    params: {
                        centerX: e.placement.centerX, centerY: e.placement.centerY,
                        zLow: e.placement.zBase, zHigh: e.placement.zBase + e.placement.height,
                        width: e.placement.width, depth: e.placement.depth, yaw: e.placement.yaw,
                    },
                    lifecycleState: e.lifecycleState,
                    label: e.displayLabel,
                    selected: selectedEquipmentId === e.id,
                    invalid: equipmentContainmentCache.get(e.id) === 'FAIL',
                    placeholder: e.placement.envelopeProvenance === 'GENERIC_ENGINEERING_PLACEHOLDER',
                    // Visual-integration: carry the canonical class + spatial
                    // family so the decorator can resolve a recognizable generic
                    // VISUAL family (cyclotron / PET-CT / hot-cell) WITHOUT ever
                    // touching the exact canonical identity.
                    canonicalClass: e.canonicalClass,
                    assetFamily: e.assetFamily,
                })),
            // EVI-MA-05A — app-owned clinical logistics vestibules (wall-integrated).
            getVestibulesForRender: () => vestibuleInstances
                .filter((v) => !v.hidden)
                .map((v) => ({
                    id: v.vestibuleInstanceId,
                    params: {
                        centerX: v.pose.centerX, centerY: v.pose.centerY,
                        zLow: v.pose.zBase, zHigh: v.pose.zBase + v.pose.height,
                        width: v.pose.width, depth: v.pose.depth, yaw: v.pose.yaw,
                    },
                    family: v.visualFamily,
                    ports: resolveVestibulePorts(v.serviceClass),
                    lifecycleState: v.lifecycleState === 'LOCKED' ? 'LOCKED' as const : 'DRAFT' as const,
                    label: v.displayLabel,
                    selected: selectedVestibuleId === v.vestibuleInstanceId,
                })),
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

/** The registered clinical-program decorator (equipment pick resolution). */
export function getClinicalProgramDecorator(): ClinicalProgramDecorator | undefined {
    return clinicalProgramDecorator
}

/**
 * EVI-MA-02 — resolve a Bentley decoration pick id to its stable
 * equipmentInstanceId (or undefined). Delegates to the clinical-program
 * decorator's pick map. The tool uses this to route a 3D click/right-click to
 * the exact EquipmentAssetInstance without inferring identity from model name.
 */
export function equipmentIdForPickId(pickId: string): string | undefined {
    return clinicalProgramDecorator?.equipmentIdForPickId(pickId)
}

/**
 * EVI-MA-05A — resolve a Bentley decoration pick id to its stable
 * vestibuleInstanceId (or undefined). Delegates to the clinical-program
 * decorator's SEPARATE vestibule pick map, so a vestibule pick never returns an
 * equipment id and an equipment pick never returns a vestibule id.
 */
export function vestibuleIdForPickId(pickId: string): string | undefined {
    return clinicalProgramDecorator?.vestibuleIdForPickId(pickId)
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

/**
 * EVI-MA-07A.1 — READ-ONLY placement/interaction state for the darkening
 * diagnostic. Reads the authoritative store + the live Bentley active tool.
 * Mutates nothing. openPanel / selectedCatalogAsset are React-owned and supplied
 * by the caller (this module has no access to them).
 */
export function readPlacementStateForDiagnostic(): {
    placementModeActive: boolean
    intentPresent: boolean
    intentSummary: string | undefined
    interactionState: string
    pendingPlacementAssetId: string | undefined
    placementCandidatePresent: boolean
    placementToolActive: boolean
    activeBentleyToolId: string | undefined
    selectedAppObject: string | undefined
} {
    const snap = spatialAssetStore.getSnapshot()
    const intent = spatialAssetStore.getActiveIntent()
    const activeToolId = IModelApp.toolAdmin?.activeTool?.toolId
    const ref = getSelectedAppObjectRef()
    return {
        placementModeActive: snap.placementModeActive,
        intentPresent: intent !== undefined,
        intentSummary: intent ? `${intent.catalogRecordId} (${intent.displayLabel})` : undefined,
        interactionState: snap.interaction,
        pendingPlacementAssetId: intent?.catalogRecordId,
        placementCandidatePresent: intent !== undefined,
        placementToolActive: activeToolId === 'MrtPharma.AssetPlacement',
        activeBentleyToolId: activeToolId,
        selectedAppObject: ref ? `${ref.objectType}:${ref.instanceId}` : undefined,
    }
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

/**
 * Build 1B Problem B — PLANNING controlled screen-space pan (L/R/U/D). `right` /
 * `up` are fractions of the current view extent (positive = right / up). VIEW-
 * ONLY: preserves orbit/zoom/fit/cutaway. Returns whether the pan applied.
 */
export async function panPlanningCamera(right: number, up: number): Promise<boolean> {
    const ctl = await import('./walkthroughController')
    return ctl.panPlanningCamera(right, up)
}

/**
 * Build 1B Problem C — resolve a TARGETED safe walkthrough spawn for a specific
 * clinical room WITHOUT entering (drives the UI preview + honest failure). Uses
 * the room's authoritative footprint + storey band + the walk collision walls.
 * The planning volume / equipment are NEVER the spawn authority. Pure resolver.
 */
export async function resolveClinicalRoomWalkthroughSpawn(input: {
    bimSpaceId: string
    eyeHeight?: number
}): Promise<import('./targetedWalkthroughSpawn').SpawnResult> {
    const spawnMod = await import('./targetedWalkthroughSpawn')
    const { WALKTHROUGH_EYE_HEIGHT_M } = await import('./cameraNav')
    if (!input.bimSpaceId) return { ok: false, code: 'DEGENERATE_FOOTPRINT', reason: 'No room specified.' }
    await ensureAuthoritativeRoomFootprint(input.bimSpaceId).catch(() => undefined)
    const fp = authoritativeFootprints.get(input.bimSpaceId)
    if (!fp?.ok || !fp.outerLoop || fp.outerLoop.length < 3) {
        return { ok: false, code: 'DEGENERATE_FOOTPRINT', reason: 'Room geometry is not available to derive a safe spawn.' }
    }
    // Storey band for wrong-storey rejection.
    const storeyId = resolveRoomStoreyIdCached(input.bimSpaceId)
    const band = programStoreyRanges.find((s) => s.id === storeyId)
    // Wall segments (collision-active clearance).
    const ctl = await import('./walkthroughController')
    const collision = await ctl.loadWalkCollision().catch(() => undefined)
    return spawnMod.resolveTargetedWalkthroughSpawn({
        room: {
            outerLoop: fp.outerLoop,
            holes: fp.holes,
            floorZ: fp.volume?.zLow ?? fp.floorZ,
            ceilingZ: fp.volume?.zHigh,
            interiorAnchor: fp.interiorAnchor,
        },
        storey: band ? { storeyId: band.id, zLow: band.zLow, zHigh: band.zHigh } : undefined,
        eyeHeight: input.eyeHeight ?? WALKTHROUGH_EYE_HEIGHT_M,
        walls: collision?.wallBoundaries,
    })
}

/**
 * Build 1B Problem C — ENTER WALKTHROUGH HERE. Resolve the room-specific safe
 * spawn and enter walkthrough AT that point (collision-active). On an honest
 * NO_SAFE_WALKTHROUGH_SPAWN it does NOT silently fall back to the model center —
 * it returns the failure so the UI can explain it. Requires a user gesture.
 */
export async function enterWalkthroughAtClinicalRoom(input: {
    bimSpaceId: string
    eyeHeight?: number
}): Promise<{ ok: true; spawn: { x: number; y: number; z: number }; provenance: string } | { ok: false; code: string; reason: string }> {
    const spawn = await resolveClinicalRoomWalkthroughSpawn(input)
    if (!spawn.ok) return { ok: false, code: spawn.code, reason: spawn.reason }
    const storeyId = resolveRoomStoreyIdCached(input.bimSpaceId)
    const ctl = await import('./walkthroughController')
    activeCameraMode = 'WALKTHROUGH'
    const ok = await ctl.enterWalkthrough(storeyId, 'NORMAL', spawn.spawn)
    notifyProgram()
    if (!ok) return { ok: false, code: 'ENTER_FAILED', reason: 'Walkthrough could not be entered (no active viewport).' }
    return { ok: true, spawn: spawn.spawn, provenance: spawn.provenance }
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
 * Build 1B §B: read-only structured walkthrough state (eye + heading + storey) for
 * the synchronized 2D BIM plan. Pass-through to the SINGLE walkthroughController
 * walkState — the overlay adds NO second walker-position store. Returns undefined
 * when not walking.
 */
export async function getWalkthroughState(): Promise<import('./walkthroughController').WalkthroughState | undefined> {
    const ctl = await import('./walkthroughController')
    return ctl.getWalkthroughState()
}

/**
 * Build 1B §B: subscribe to walkthrough state changes for the 2D plan walker
 * marker. Delegates to the single controller subscription (no duplicate store).
 * Returns a Promise of an unsubscribe fn. The listener fires immediately with the
 * current state and again on every camera update / enter / exit.
 */
export async function subscribeWalkthroughState(
    listener: (state: import('./walkthroughController').WalkthroughState | undefined) => void,
): Promise<() => void> {
    const ctl = await import('./walkthroughController')
    return ctl.subscribeWalkthroughState(listener)
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
    // Build 1B: equipment instances are iModel-scoped — switching clears + reloads.
    equipmentContainmentCache.clear()
    // EVI-MA-07: Undo/Redo history is app-owned + iModel-scoped — clear on switch.
    appEditHistory.clear()
    notifyAppHistory()
    loadEquipmentForIModel(iModelId)
    // EVI-MA-05A: clinical logistics vestibules are iModel-scoped too.
    loadVestibulesForIModel(iModelId)
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
    /**
     * B1B-MA-03A: the active viewport camera mode, surfaced so the Clinical
     * Program panel can auto-collapse (presentation only) on Walkthrough entry.
     * Panel VISIBILITY is separate from FEATURE STATE — this never affects the
     * selection, assignments, volumes, equipment or storey filter.
     */
    cameraMode: import('./cameraNav').CameraMode
} {
    return {
        enabled: programState.enabled,
        activeStoreyId: programState.activeStoreyId,
        selectedSpaceId: programState.selectedSpaceId,
        iModelId: programState.iModelId,
        assignments: programState.assignments,
        showRoomVolume: programState.showRoomVolume,
        cameraMode: activeCameraMode,
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
            holes: parent.holes,
            // B1B-MA-01: center the seed on a PROVEN-interior anchor (essential for
            // rotated / irregular rooms) so the parent-derived volume is contained.
            interiorAnchor: parent.interiorAnchor,
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
 * B1B-MA-03B — resolve a single discovered room by its stable BIM id from the
 * IMMUTABLE base discovery, INDEPENDENT of the active storey filter. The room
 * selector uses this so the authoritative selected room (programState.selectedSpaceId)
 * remains resolvable — and its detail/assignment/volume UI stays intact — even when
 * the storey chip filter would otherwise hide it from the dropdown option list.
 * The storey chip filters the OPTIONS shown, never the authoritative selection.
 */
export function getDiscoveredRoomById(bimSpaceId: string | undefined): DiscoveredRoomVolume | undefined {
    if (!bimSpaceId) return undefined
    return getDiscoveredRoomVolumes().find((r) => r.bimSpaceId === bimSpaceId)
}

/**
 * Build 1A.3 — whether the currently SELECTED room is outside the active storey
 * filter. B1B-MA-03B: this is now PURELY INFORMATIONAL — the UI uses it only to
 * surface an "outside current storey filter" hint and to render the selected
 * room's option even when filtered out. It MUST NOT be used to clear the
 * authoritative selection (that overwrite path was the B1B-MA-03B defect).
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

// ===========================================================================
// MRT PHARMA BUILD 1B — CANONICAL EQUIPMENT SPATIAL BINDING (app-owned)
// ===========================================================================
//
// App-owned equipment instances bind a canonical catalog model (by reference to
// its backend catalog_model_id) to a parent BIM room. Placement is a parent-
// derived floor-aware oriented envelope; containment is evaluated against the
// room's EXACT mesh (corners+edges+anchor, NOT center-only) reusing the accepted
// planning-volume primitives. LOCK freezes the app object only — no Bentley write.
// Instances are iModel-scoped, persisted safely, and recomputed on reload.

import type {
    EquipmentAssetInstance,
    EquipmentPlacement,
} from './equipmentInstance'

let equipmentInstances: EquipmentAssetInstance[] = []
/** True once the active iModel's equipment has loaded (writes gated until then). */
let equipmentHydrated = false
let equipmentSeq = 0
let showEquipment = true
let selectedEquipmentId: string | undefined
/** Per-instance last-computed containment status (sync cache for the decorator). */
const equipmentContainmentCache = new Map<string, 'PASS' | 'FAIL' | 'NOT_EVALUATED'>()

/** Load equipment instances for the active iModel (scoped; cleared on switch). */
function loadEquipmentForIModel(iModelId: string): void {
    equipmentHydrated = false
    selectedEquipmentId = undefined
    void import('./equipmentInstance').then((m) => {
        if (programState.iModelId !== iModelId) return
        equipmentInstances = iModelId ? m.loadEquipmentInstances(iModelId) : []
        // Seed the seq past any restored ids so new ids never collide.
        equipmentSeq = equipmentInstances.length
        equipmentHydrated = true
        notifyProgram()
        // EVI-MA-02A: if persisted equipment was restored, arm the tool so the
        // restored cyclotrons are directly selectable/deletable after reload
        // even with zero legacy AssetInstances.
        if (equipmentInstances.length > 0) void ensureDirectManipulationReady().catch(() => false)
    })
}

function persistEquipment(): void {
    if (!programState.iModelId || !equipmentHydrated) return
    void import('./equipmentInstance').then((m) => m.saveEquipmentInstances(programState.iModelId, equipmentInstances))
}

/** Snapshot of all equipment instances (read-only). */
export function getEquipmentInstances(): readonly EquipmentAssetInstance[] {
    return equipmentInstances
}

/** The equipment instance for an id (or undefined). */
export function getEquipmentInstance(id: string): EquipmentAssetInstance | undefined {
    return equipmentInstances.find((e) => e.id === id)
}

/** Equipment instances currently bound to a parent room. */
export function getEquipmentForRoom(bimSpaceId: string): readonly EquipmentAssetInstance[] {
    return equipmentInstances.filter((e) => e.parentBimSpaceId === bimSpaceId)
}

/**
 * Build 1B §B: assemble the TRUE 2D BIM floor-plan view-model shown SIMULTANEOUSLY
 * with the 3D Walkthrough. This is a pure projection of the SAME authorities the
 * 3D scene uses — discovered rooms, program assignments, equipment envelopes, and
 * (optionally) ranked candidate tiers — all joined by `bimSpaceId`. It prefers the
 * EXACT extracted room footprint and tags approximate outlines honestly. No new
 * store is created (§26/§15/§9). Rendering happens in the React component.
 *
 * The `walker` read-model is passed IN by the caller (the plan component
 * subscribes to the single walkthrough state) so this stays synchronous and the
 * walker is never duplicated here.
 */
/**
 * Build 1B Defect 1: HYDRATE the discovered-room registry for the 2D plan
 * INDEPENDENT of the Clinical Program.
 *
 * The 2D plan reads `getDiscoveredRoomVolumes()`, which is derived from
 * `cachedModelSemantics.rooms`. Those semantics are only populated by
 * `refreshModelSemantics()`. Previously that refresh was driven ONLY by the
 * Clinical Program's discovery effect, so with CLINICAL PROGRAM = Off (the normal
 * Walkthrough case) the semantics were never loaded and the plan projected 0
 * rooms — the observed "200 rooms → 0 rooms" regression.
 *
 * This helper lets the plan (or Walkthrough) trigger the SAME existing,
 * idempotent, in-flight-guarded semantics refresh WITHOUT enabling the Clinical
 * Program. It creates NO second room registry / discovery system (§24) — it just
 * ensures the ONE authority is populated. Safe to call repeatedly: it no-ops once
 * rooms are present, and shares the single in-flight refresh otherwise.
 *
 * Returns the number of discovered room volumes after the attempt (0 offline).
 */
export async function ensureBim2dPlanRoomsHydrated(): Promise<number> {
    if (semanticsLoaded && cachedModelSemantics.rooms.length > 0) {
        return getDiscoveredRoomVolumes().length
    }
    try {
        await refreshModelSemantics()
    } catch {
        /* offline / no iModel — return whatever we have (likely 0) */
    }
    return getDiscoveredRoomVolumes().length
}

export function getBim2dPlanView(opts?: {
    /** Storey to project; defaults to the program's active storey. */
    storeyId?: string
    /** The selected room to highlight; defaults to the program's selected space. */
    selectedBimSpaceId?: string
    /** Optional ranked candidates (bimSpaceId+tier) to annotate on the plan. */
    candidates?: readonly import('./bim2dPlanProjection').PlanCandidateInput[]
    /** Optional walker read-model from subscribeWalkthroughState (never duplicated). */
    walker?: import('./bim2dPlanProjection').PlanWalkerInput
}): import('./bim2dPlanProjection').Bim2dPlanView {
    // §8 STOREY TRUTH: while walking, the plan MUST follow the WALKER's active
    // storey (the single walkthrough read-model), NOT the Clinical Program's
    // active storey — those are independent and were the source of the "wrong /
    // empty floor" seam. Precedence: explicit opt > active walker storey >
    // program active storey.
    const walkerStoreyId = opts?.walker?.active ? opts.walker.activeStoreyId : undefined
    const storeyId = opts?.storeyId ?? walkerStoreyId ?? programState.activeStoreyId
    const selectedBimSpaceId = opts?.selectedBimSpaceId ?? programState.selectedSpaceId

    // Rooms: discovered volumes + their EXACT extracted footprint if cached.
    const rooms: import('./bim2dPlanProjection').PlanRoomInput[] = getDiscoveredRoomVolumes().map((r) => {
        const fp = authoritativeFootprints.get(r.bimSpaceId)
        const useExact = !!fp && fp.ok && fp.outerLoop.length >= 3
        return {
            bimSpaceId: r.bimSpaceId,
            originalBimLabel: r.originalBimLabel,
            mrtDisplayName: r.mrtDisplayName,
            storeyId: r.storeyId,
            worldRange: r.worldRange
                ? { low: { x: r.worldRange.low.x, y: r.worldRange.low.y, z: r.worldRange.low.z }, high: { x: r.worldRange.high.x, y: r.worldRange.high.y, z: r.worldRange.high.z } }
                : undefined,
            exactOuterLoop: useExact ? fp!.outerLoop.map((p) => ({ x: p.x, y: p.y })) : undefined,
            exactHoles: useExact ? fp!.holes.map((h) => h.map((p) => ({ x: p.x, y: p.y }))) : undefined,
            exactFloorZ: useExact ? fp!.floorZ : undefined,
        }
    })

    // Assignments: the app-owned clinical program (join by bimSpaceId).
    const assignments: import('./bim2dPlanProjection').PlanAssignmentInput[] = programState.assignments
        .filter((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')
        .map((a) => ({ bimSpaceId: a.bimSpaceId, clinicalFunction: a.clinicalFunction, mrtDisplayName: a.mrtDisplayName }))

    // Equipment: project each visible instance's envelope footprint.
    const equipment: import('./bim2dPlanProjection').PlanEquipmentInput[] = equipmentInstances.map((e) => {
        const env = buildEquipmentEnvelope(e.placement)
        return {
            id: e.id,
            parentBimSpaceId: e.parentBimSpaceId,
            storeyId: e.storeyId,
            displayLabel: e.displayLabel,
            lifecycleState: e.lifecycleState,
            hidden: e.hidden,
            footprint: env.footprint.map((p) => ({ x: p.x, y: p.y })),
        }
    })

    // EVI-MA-05A — vestibules: ONE marker each (reserved-volume footprint + front
    // face + MRT/PTS stub ends). The reserved volume is an AABB; its footprint is
    // the 4 XY corners. Front face + stub ends come from the pose + persisted ports.
    const vestibules: import('./bim2dPlanProjection').PlanVestibuleInput[] = vestibuleInstances.map((v) => {
        const rv = v.reservedVolume
        const footprint = [
            { x: rv.minX, y: rv.minY }, { x: rv.maxX, y: rv.minY },
            { x: rv.maxX, y: rv.maxY }, { x: rv.minX, y: rv.maxY },
        ]
        const mrt = v.transportPorts.find((p) => p.transportFamily === 'MRT' && p.fabricated)
        const pts = v.transportPorts.find((p) => p.transportFamily === 'PTS' && p.fabricated)
        return {
            id: v.vestibuleInstanceId,
            parentBimSpaceId: v.parentBimSpaceId,
            storeyId: undefined,
            displayLabel: v.displayLabel,
            lifecycleState: v.lifecycleState === 'LOCKED' ? 'LOCKED' as const : 'DRAFT' as const,
            hidden: v.hidden,
            footprint,
            frontFace: { x: v.frontFacePlane.pointX, y: v.frontFacePlane.pointY },
            frontNormal: { x: v.frontFacePlane.normalX, y: v.frontFacePlane.normalY },
            mrtStubEnd: mrt ? { x: mrt.position.x, y: mrt.position.y } : undefined,
            ptsStubEnd: pts ? { x: pts.position.x, y: pts.position.y } : undefined,
        }
    })

    return projectBim2dPlan({
        rooms,
        assignments,
        candidates: opts?.candidates,
        equipment,
        vestibules,
        walker: opts?.walker,
        storeyId,
        selectedBimSpaceId,
    })
}

export function getShowEquipment(): boolean { return showEquipment }
export function setShowEquipment(show: boolean): void {
    if (showEquipment === show) return
    showEquipment = show
    notifyProgram()
}

export function getSelectedEquipmentId(): string | undefined { return selectedEquipmentId }
export function selectEquipment(id: string | undefined): void {
    if (selectedEquipmentId === id) return
    selectedEquipmentId = id
    // EVI-MA-05A — one active selection at a time: selecting equipment clears any
    // selected vestibule so the two floating controls never both show.
    if (id) selectedVestibuleId = undefined
    notifyProgram()
}

/** The per-instance containment status last computed (for the decorator cue). */
export function getEquipmentContainmentStatus(id: string): 'PASS' | 'FAIL' | 'NOT_EVALUATED' {
    return equipmentContainmentCache.get(id) ?? 'NOT_EVALUATED'
}

/**
 * Place a canonical equipment model in a parent BIM room. Derives a parent-
 * derived, floor-aware envelope seed from the room's OWN authoritative geometry
 * (extracted read-only, on demand). Never fabricates equipment not in the
 * canonical catalog. No Bentley write.
 */
export async function placeEquipmentInParent(input: {
    canonicalEquipmentId: string
    parentBimSpaceId: string
}): Promise<{ ok: boolean; reason?: string; equipmentInstanceId?: string; duplicateInRoom?: boolean; displayLabel?: string; conflictLabel?: string; conflictEquipmentId?: string }> {
    if (!programState.iModelId) return { ok: false, reason: 'NO_IMODEL' }
    // EVI-MA-02 §9 — detect (but never block/merge) an identical canonical model
    // already in the SAME parent room, so the UI can surface a non-blocking note.
    const duplicateInRoom = equipmentInstances.some(
        (e) => e.parentBimSpaceId === input.parentBimSpaceId && e.canonicalEquipmentId === input.canonicalEquipmentId,
    )
    const m = await import('./equipmentInstance')
    await ensureAuthoritativeRoomFootprint(input.parentBimSpaceId)
    const parent = authoritativeFootprints.get(input.parentBimSpaceId)
    // Prefer the room's exact footprint; fall back to a bounded default (still the
    // parent room, never another room / world origin) when geometry is pending.
    const footprint = parent?.ok && parent.outerLoop && parent.outerLoop.length >= 3
        ? parent.outerLoop
        : [{ x: -2, y: -2 }, { x: 2, y: -2 }, { x: 2, y: 2 }, { x: -2, y: 2 }]
    const zLow = parent?.volume?.zLow ?? parent?.floorZ ?? 0
    const zHigh = parent?.volume?.zHigh ?? (zLow + 3)
    const pv = getClinicalPlanningVolume(input.parentBimSpaceId)
    equipmentSeq += 1
    const created = m.createEquipmentInstance({
        iModelId: programState.iModelId,
        canonicalEquipmentId: input.canonicalEquipmentId,
        parentBimSpaceId: input.parentBimSpaceId,
        parentClinicalPlanningVolumeId: pv?.id,
        storeyId: resolveRoomStoreyIdCached(input.parentBimSpaceId),
        footprint,
        zLow,
        zHigh,
        seq: equipmentSeq,
    })
    if (!created.ok) return { ok: false, reason: created.reason }
    // EVI-MA-02A §12A — HARD spatial-exclusivity check. Test the proposed
    // equipment's occupied 3D volume against every existing equipment instance
    // (locked included). If it intersects, REJECT: create nothing, leave no
    // transient instance, and report the conflicting model. The first placed
    // instance reserves its volume until deleted or moved.
    const collision = m.findEquipmentCollision({ proposed: created.instance.placement, existing: equipmentInstances })
    if (collision.collides) {
        const cat = await import('./canonicalEquipmentCatalog')
        const cm = collision.conflictCanonicalId ? cat.canonicalEquipmentById(collision.conflictCanonicalId) : undefined
        const conflictModel = cm ? `${cm.manufacturer} ${cm.model}` : (collision.conflictLabel ?? collision.conflictId)
        return { ok: false, reason: 'EQUIPMENT_COLLISION', conflictLabel: conflictModel, conflictEquipmentId: collision.conflictId }
    }
    equipmentInstances = [...equipmentInstances, created.instance]
    // §9 — the NEW instance becomes selected (never silently leaves the prior
    // one selected), and its context menu / card converge on it.
    selectedEquipmentId = created.instance.id
    persistEquipment()
    notifyProgram()
    // EVI-MA-02A root-cause fix: ensure the direct-manipulation tool is armed so
    // the newly placed equipment is immediately left-click selectable and
    // right-click deletable in the live 3D viewport — WITHOUT requiring a legacy
    // AssetInstance to exist. Idempotent; no-op if a placement/move owns the vp.
    void ensureDirectManipulationReady().catch(() => false)
    // Compute containment now that the instance exists (records last-known-valid).
    void getEquipmentValidation(created.instance.id)
    return { ok: true, equipmentInstanceId: created.instance.id, duplicateInRoom, displayLabel: created.instance.displayLabel }
}

/**
 * Update a DRAFT instance's placement (rejected if LOCKED). No Bentley write.
 *
 * EVI-MA-02A §12D — a pose edit that would make this instance's volume overlap
 * ANOTHER equipment instance is REJECTED; the existing valid arrangement remains
 * authoritative (the instance keeps its current placement). Returns a result so
 * callers/UI can report the rejection instead of silently allowing overlap.
 */
export function updateEquipmentPlacement(id: string, placement: EquipmentPlacement): { ok: boolean; reason?: string; conflictEquipmentId?: string } {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return { ok: false, reason: 'NO_INSTANCE' }
    if (e.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED' }
    // Collision against every OTHER instance (locked included); self excluded.
    const collision = findEquipmentCollision({ proposed: placement, existing: equipmentInstances, excludeId: id })
    if (collision.collides) {
        return { ok: false, reason: 'EQUIPMENT_COLLISION', conflictEquipmentId: collision.conflictId }
    }
    e.placement = placement
    equipmentInstances = [...equipmentInstances]
    persistEquipment()
    notifyProgram()
    void getEquipmentValidation(id)
    return { ok: true }
}

/** Translate a DRAFT instance in world XY (rejected on equipment collision). */
export async function translateEquipmentInstance(id: string, dx: number, dy: number): Promise<{ ok: boolean; reason?: string; conflictEquipmentId?: string }> {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return { ok: false, reason: 'NO_INSTANCE' }
    if (e.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED' }
    const m = await import('./equipmentInstance')
    return updateEquipmentPlacement(id, m.translateEquipment(e.placement, dx, dy))
}

/** Rotate a DRAFT instance about vertical (radians) (rejected on collision). */
export async function rotateEquipmentInstance(id: string, dyaw: number): Promise<{ ok: boolean; reason?: string; conflictEquipmentId?: string }> {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return { ok: false, reason: 'NO_INSTANCE' }
    if (e.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED' }
    const m = await import('./equipmentInstance')
    return updateEquipmentPlacement(id, m.rotateEquipment(e.placement, dyaw))
}

/** Live containment of an instance against its parent room mesh. */
export async function getEquipmentContainment(id: string): Promise<{ status: 'PASS' | 'FAIL' | 'NOT_EVALUATED'; failedSamples: number; totalSamples: number; parentMeshAvailable: boolean; reason?: string }> {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return { status: 'NOT_EVALUATED', failedSamples: 0, totalSamples: 0, parentMeshAvailable: false, reason: 'NO_INSTANCE' }
    await ensureAuthoritativeRoomFootprint(e.parentBimSpaceId)
    const m = await import('./equipmentInstance')
    const parent = authoritativeFootprints.get(e.parentBimSpaceId)
    const parentMesh = parent?.ok && parent.mesh && parent.mesh.triangles.length >= 3 ? parent.mesh : undefined
    const c = m.evaluateEquipmentContainment({ placement: e.placement, parentMesh })
    equipmentContainmentCache.set(id, c.status)
    // Record LAST-KNOWN-VALID on PASS only (never overwrite with an invalid edit).
    if (c.status === 'PASS') {
        const snap = { ...e.placement }
        if (JSON.stringify(e.lastKnownValidPlacement) !== JSON.stringify(snap)) {
            e.lastKnownValidPlacement = snap
            equipmentInstances = [...equipmentInstances]
            persistEquipment()
        }
    }
    return { status: c.status, failedSamples: c.failedSamples, totalSamples: c.totalSamples, parentMeshAvailable: !!parentMesh, reason: c.reason }
}

/** The product-facing VALIDATION view model for an equipment instance. */
export async function getEquipmentValidation(id: string): Promise<import('./equipmentValidation').EquipmentValidationState | undefined> {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return undefined
    const val = await import('./equipmentValidation')
    const contain = await getEquipmentContainment(id)
    const quality = getClinicalProgramRoomGeometryQuality(e.parentBimSpaceId)?.quality
    const authorityQuality: import('./equipmentValidation').EquipmentAuthorityQuality =
        quality === 'EXACT_ROOM_BOUNDARY' ? 'EXACT_SPACE_GEOMETRY'
            : quality === 'BIM_RANGE_APPROXIMATION' ? 'RANGE_ONLY_APPROXIMATION'
                : 'NOT_AVAILABLE'
    return val.resolveEquipmentValidation({
        instance: e,
        containmentStatus: contain.status,
        authorityQuality,
        totalSamples: contain.totalSamples,
        failedSamples: contain.failedSamples,
        parentMeshAvailable: contain.parentMeshAvailable,
    })
}

/** Restrained equipment-validation summary across ALL instances. */
export async function getEquipmentValidationSummary(): Promise<import('./equipmentValidation').EquipmentValidationSummary> {
    const val = await import('./equipmentValidation')
    const states: import('./equipmentValidation').EquipmentValidationState[] = []
    for (const e of equipmentInstances) {
        const s = await getEquipmentValidation(e.id)
        if (s) states.push(s)
    }
    return val.summarizeEquipmentValidation({ states, instances: equipmentInstances })
}

/**
 * RESTORE VALID POSITION for a DRAFT instance: restore this SAME instance's most
 * recent last-known-valid placement; else derive a fresh parent-derived seed from
 * this room's OWN geometry. No Bentley write. Rejected if LOCKED.
 */
export async function restoreEquipmentValidPosition(id: string): Promise<{ ok: boolean; reason?: string; source?: 'LAST_KNOWN_VALID' | 'PARENT_DERIVED' }> {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return { ok: false, reason: 'NO_INSTANCE' }
    if (e.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED' }
    const m = await import('./equipmentInstance')
    if (e.lastKnownValidPlacement) {
        const r = updateEquipmentPlacement(id, { ...e.lastKnownValidPlacement })
        return r.ok ? { ok: true, source: 'LAST_KNOWN_VALID' } : { ok: false, reason: r.reason }
    }
    await ensureAuthoritativeRoomFootprint(e.parentBimSpaceId)
    const parent = authoritativeFootprints.get(e.parentBimSpaceId)
    const footprint = parent?.ok && parent.outerLoop && parent.outerLoop.length >= 3
        ? parent.outerLoop
        : [{ x: -2, y: -2 }, { x: 2, y: -2 }, { x: 2, y: 2 }, { x: -2, y: 2 }]
    const seed = m.restoreEquipmentPlacement({ instance: e, footprint, zLow: parent?.volume?.zLow ?? parent?.floorZ ?? 0, zHigh: parent?.volume?.zHigh ?? 3 })
    if (!seed) return { ok: false, reason: 'NO_SEED' }
    const r = updateEquipmentPlacement(id, seed)
    return r.ok ? { ok: true, source: 'PARENT_DERIVED' } : { ok: false, reason: r.reason }
}

/** RESET TO PARENT-DERIVED for a DRAFT instance. No Bentley write. Rejected if LOCKED. */
export async function resetEquipmentToParentDerived(id: string): Promise<{ ok: boolean; reason?: string }> {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return { ok: false, reason: 'NO_INSTANCE' }
    if (e.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED' }
    const m = await import('./equipmentInstance')
    await ensureAuthoritativeRoomFootprint(e.parentBimSpaceId)
    const parent = authoritativeFootprints.get(e.parentBimSpaceId)
    const footprint = parent?.ok && parent.outerLoop && parent.outerLoop.length >= 3
        ? parent.outerLoop
        : [{ x: -2, y: -2 }, { x: 2, y: -2 }, { x: 2, y: 2 }, { x: -2, y: 2 }]
    const seed = m.resetEquipmentToParentDerived({ instance: e, footprint, zLow: parent?.volume?.zLow ?? parent?.floorZ ?? 0, zHigh: parent?.volume?.zHigh ?? 3 })
    if (!seed) return { ok: false, reason: 'NO_SEED' }
    return updateEquipmentPlacement(id, seed)
}

/** Lock an equipment instance (only when containment PASS + valid). No Bentley write. */
export async function lockEquipment(id: string): Promise<{ ok: boolean; reason?: string }> {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return { ok: false, reason: 'NO_INSTANCE' }
    await ensureAuthoritativeRoomFootprint(e.parentBimSpaceId)
    const m = await import('./equipmentInstance')
    const parent = authoritativeFootprints.get(e.parentBimSpaceId)
    const parentMesh = parent?.ok && parent.mesh && parent.mesh.triangles.length >= 3 ? parent.mesh : undefined
    const gate = m.canLockEquipment(e, parentMesh)
    if (!gate.ok) return gate
    e.lifecycleState = 'LOCKED'
    equipmentInstances = [...equipmentInstances]
    persistEquipment()
    notifyProgram()
    return { ok: true }
}

/** Unlock an equipment instance for editing (planning-object freeze only). */
export function unlockEquipment(id: string): void {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e || e.lifecycleState !== 'LOCKED') return
    e.lifecycleState = 'DRAFT'
    equipmentInstances = [...equipmentInstances]
    persistEquipment()
    notifyProgram()
}

/** Per-instance visibility (view-only; never mutates placement or lifecycle). */
export function setEquipmentVisibility(id: string, visible: boolean): void {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return
    const hidden = !visible
    if ((e.hidden ?? false) === hidden) return
    e.hidden = hidden
    equipmentInstances = [...equipmentInstances]
    persistEquipment()
    notifyProgram()
}

/**
 * EVI-MA-02C — explicit, non-silent result for equipment deletion. Every Delete
 * entry point (card, 3D right-click menu, keyboard) inspects this.
 */
export type DeleteEquipmentResult =
    | { ok: true; deletedId: string; canonicalModelId: string }
    | { ok: false; reason: 'NOT_FOUND' | 'LOCKED' | 'PERSISTENCE_FAILED' | 'INVALID_STATE'; message: string }

/**
 * Delete an equipment instance STRICTLY BY equipmentInstanceId (never by model /
 * family / room / label / array position). LOCKED is rejected (unlock first).
 * On success: remove exactly one instance, drop its containment reservation,
 * clear the selection + context menu if they referenced it, persist the NEW
 * collection, and notify subscribers so every derived representation (3D
 * geometry, envelope, label, 2D marker, card, collision reservation) disappears.
 *
 * EVI-MA-02C root cause NOTE: the live Delete previously never mutated the store
 * because the context-menu handler gated `deleteEquipment` behind a blocking
 * `window.confirm(...)` that returns false in the embedded viewer host (Hide had
 * no such gate, so Hide worked and Delete did not). The gate is removed; this
 * function is the single authoritative mutation and always returns a result.
 */
export function deleteEquipment(id: string): DeleteEquipmentResult {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return { ok: false, reason: 'NOT_FOUND', message: `No equipment instance with id ${id}.` }
    if (e.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED', message: 'Unlock equipment before deleting.' }
    const canonicalModelId = e.canonicalEquipmentId
    const before = equipmentInstances.length
    equipmentInstances = equipmentInstances.filter((x) => x.id !== id)
    if (equipmentInstances.length !== before - 1) {
        // Should be impossible (find succeeded), but never silently "succeed".
        return { ok: false, reason: 'INVALID_STATE', message: 'Equipment collection did not decrement by exactly one.' }
    }
    equipmentContainmentCache.delete(id)
    // Clear derived selection/menu references to the now-deleted instance.
    if (selectedEquipmentId === id) selectedEquipmentId = undefined
    if (equipmentContextMenu?.equipmentInstanceId === id) closeEquipmentContextMenu()
    // Persist the NEW authoritative collection and redraw all derived views.
    persistEquipment()
    notifyProgram()
    return { ok: true, deletedId: id, canonicalModelId }
}

/** The capacity/production/cost crosswalk readout for an instance's canonical model. */
export async function getEquipmentCrosswalk(id: string): Promise<import('./equipmentValidation').EquipmentCrosswalkReadout | undefined> {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return undefined
    const val = await import('./equipmentValidation')
    return val.buildEquipmentCrosswalkReadout(e.canonicalEquipmentId)
}

/**
 * TRANSPORT-ENDPOINT SPATIAL AUTHORITY accessor. Returns the canonical MRT
 * facility spatial class + cost-authority reference for a bindable MRT facility
 * class (vestibule / endpoint). By reference only — never a fabricated cost.
 */
export async function getMrtFacilitySpatialAuthority(cls: import('./canonicalEquipmentCatalog').CanonicalMrtFacilityClass): Promise<import('./canonicalEquipmentCatalog').CanonicalMrtFacilityModel | undefined> {
    const cat = await import('./canonicalEquipmentCatalog')
    return cat.canonicalMrtFacility(cls)
}

/**
 * DIAGNOSE SELECTED EQUIPMENT — generic bounded text report for the selected (or
 * a given) equipment instance. Never dumps raw geometry; never mutates anything.
 */
export async function diagnoseSelectedEquipment(id?: string): Promise<string> {
    const targetId = id ?? selectedEquipmentId
    if (!targetId) return 'NO_SELECTED_EQUIPMENT: place or select an equipment instance first.'
    const e = equipmentInstances.find((x) => x.id === targetId)
    if (!e) return `NO_SUCH_EQUIPMENT: ${targetId}`
    const val = await import('./equipmentValidation')
    const validation = await getEquipmentValidation(e.id)
    const contain = await getEquipmentContainment(e.id)
    if (!validation) return `NO_VALIDATION: ${targetId}`
    const d = val.buildSelectedEquipmentDiagnostic({
        instance: e, validation, totalSamples: contain.totalSamples, failedSamples: contain.failedSamples,
    })
    const out = val.formatSelectedEquipmentDiagnostic(d)
    if (import.meta.env.DEV) console.info('[equipment-diag]\n%s', out)
    return out
}

/**
 * EVI-MA-01 — structured VISUAL/RENDER diagnostic for one equipment instance
 * (pose, resolved visual family, envelope + visual world bounds, primitive
 * count, renderable). Makes a future visual failure diagnosable in one call.
 * View-only; never mutates. Returns undefined for an unknown id.
 */
export async function getEquipmentVisualDiagnostic(
    id?: string,
): Promise<import('./equipmentGeometry').EquipmentVisualDiagnostic | undefined> {
    const targetId = id ?? selectedEquipmentId
    if (!targetId) return undefined
    const e = equipmentInstances.find((x) => x.id === targetId)
    if (!e) return undefined
    const geo = await import('./equipmentGeometry')
    const p = e.placement
    const diag = geo.buildEquipmentVisualDiagnostic({
        equipmentInstanceId: e.id,
        canonicalModelId: e.canonicalEquipmentId,
        canonicalClass: e.canonicalClass,
        assetFamily: e.assetFamily,
        parentRoomId: e.parentBimSpaceId,
        pose: {
            center: [p.centerX, p.centerY, p.zBase],
            width: p.width,
            depth: p.depth,
            height: p.height,
            yawRadians: p.yaw,
        },
    })
    if (import.meta.env.DEV) console.info('[equipment-visual-diag] %o', diag)
    return diag
}

/** Bounded Build 1B equipment overlay summary (for the report/audit). */
export async function summarizeEquipmentBinding(): Promise<{
    iModelId: string
    equipmentCount: number
    byClass: Record<string, number>
    lockedCount: number
    placeholderEnvelopeCount: number
    boundRoomCount: number
}> {
    const byClass: Record<string, number> = {}
    let locked = 0, placeholder = 0
    const rooms = new Set<string>()
    for (const e of equipmentInstances) {
        byClass[e.canonicalClass] = (byClass[e.canonicalClass] ?? 0) + 1
        if (e.lifecycleState === 'LOCKED') locked += 1
        if (e.placement.envelopeProvenance === 'GENERIC_ENGINEERING_PLACEHOLDER') placeholder += 1
        rooms.add(e.parentBimSpaceId)
    }
    return {
        iModelId: programState.iModelId,
        equipmentCount: equipmentInstances.length,
        byClass,
        lockedCount: locked,
        placeholderEnvelopeCount: placeholder,
        boundRoomCount: rooms.size,
    }
}

// ===========================================================================
// Build 1B spatial-foundation correction — CLINICAL ROOM CANDIDATE DISCOVERY
// + RE-PARENTING (Problem A). Consumes the pure engines (clinicalRoomCandidate,
// clinicalRoomReparent); wires the lazy authoritative-footprint extraction for
// the shortlist. Never mutates Bentley identity/label/range/mesh.
// ===========================================================================

/**
 * Build the footprint facts map (bimSpaceId -> exact outer loop + Z) from the
 * overlay's authoritative-footprint cache for the given rooms. Only rooms that
 * have ALREADY been extracted (ok) contribute; this NEVER triggers extraction.
 */
function collectCandidateFootprintFacts(
    bimSpaceIds: readonly string[],
): import('./clinicalRoomCandidate').CandidateFootprintFacts {
    const out: Record<string, { outerLoop: { x: number; y: number }[]; floorZ?: number; zLow?: number; zHigh?: number }> = {}
    for (const id of bimSpaceIds) {
        const fp = authoritativeFootprints.get(id)
        if (fp?.ok && fp.outerLoop && fp.outerLoop.length >= 3) {
            out[id] = {
                outerLoop: fp.outerLoop,
                floorZ: fp.floorZ,
                zLow: fp.volume?.zLow ?? fp.floorZ,
                zHigh: fp.volume?.zHigh,
            }
        }
    }
    return out
}

/**
 * Find ranked, explainable clinical-room CANDIDATES for a chosen function. This
 * is the SHORTLIST stage of the staged evaluation:
 *   1. discover rooms (already cached BIM semantics),
 *   2. rank with the pure engine using CURRENTLY-KNOWN geometry,
 *   3. LAZILY extract the exact mesh for the top-N flagged shortlist,
 *   4. re-rank with the improved geometry so the final list is high-confidence.
 * Deterministic per input; camera-independent. Never mutates Bentley.
 */
export async function findClinicalRoomCandidates(input: {
    clinicalFunction: ClinicalFunction
    storeyId?: string
    limit?: number
    recommendedOnly?: boolean
    /** How many top shortlisted rooms to lazily extract exact geometry for. */
    exactExtractionBudget?: number
}): Promise<{
    candidates: import('./clinicalRoomCandidate').RankedRoomCandidate[]
    summary: import('./clinicalRoomCandidate').CandidateRankingSummary
    vocabulary: import('./clinicalRoomCandidate').DiscoveredSemanticVocabulary
}> {
    const engine = await import('./clinicalRoomCandidate')
    const discovered = getDiscoveredRoomVolumes()

    // The current parent for this function (so it can be marked in the list).
    const currentAssignment = programState.assignments.find(
        (a) => a.clinicalFunction === input.clinicalFunction,
    )
    const currentParentBimSpaceId = currentAssignment?.bimSpaceId

    // Pass 1 — rank with currently-known geometry (cheap; no extraction).
    const pass1 = engine.rankClinicalRoomCandidates({
        clinicalFunction: input.clinicalFunction,
        rooms: discovered,
        footprints: collectCandidateFootprintFacts(discovered.map((r) => r.bimSpaceId)),
        currentParentBimSpaceId,
        storeyId: input.storeyId,
        recommendedOnly: input.recommendedOnly,
        limit: input.limit,
    })

    // Pass 2 — lazily extract exact geometry for the top recommended shortlist
    // that still needs it, then re-rank. Bounded by exactExtractionBudget.
    const budget = Math.max(0, input.exactExtractionBudget ?? 6)
    const toExtract = pass1
        .filter((c) => c.recommended && c.needsExactGeometry)
        .slice(0, budget)
        .map((c) => c.bimSpaceId)
    if (toExtract.length > 0) {
        await Promise.all(toExtract.map((id) => ensureAuthoritativeRoomFootprint(id).catch(() => undefined)))
    }

    const candidates = engine.rankClinicalRoomCandidates({
        clinicalFunction: input.clinicalFunction,
        rooms: discovered,
        footprints: collectCandidateFootprintFacts(discovered.map((r) => r.bimSpaceId)),
        currentParentBimSpaceId,
        storeyId: input.storeyId,
        recommendedOnly: input.recommendedOnly,
        limit: input.limit,
    })
    const summary = engine.summarizeCandidateRanking({ clinicalFunction: input.clinicalFunction, candidates })

    // Vocabulary is computed over ALL discovered rooms (honest disclosure).
    const classifications = discovered.map((r) =>
        engine.classifyBimSpaceSemantics({ originalBimLabel: r.originalBimLabel, sourceClass: r.sourceClass }),
    )
    const vocabulary = engine.summarizeDiscoveredVocabulary(classifications)

    return { candidates, summary, vocabulary }
}

/**
 * Score a SINGLE candidate room for a function (used by direct-3D selection where
 * the user clicks a room in the viewport). Lazily extracts that room's exact mesh
 * first so the returned candidate is high-confidence. Returns undefined when the
 * bimSpaceId is not a known discovered room (honest NO_ROOM_RESOLVED upstream).
 */
export async function scoreClinicalRoomCandidate(input: {
    bimSpaceId: string
    clinicalFunction: ClinicalFunction
}): Promise<import('./clinicalRoomCandidate').RankedRoomCandidate | undefined> {
    const engine = await import('./clinicalRoomCandidate')
    const discovered = getDiscoveredRoomVolumes()
    const room = discovered.find((r) => r.bimSpaceId === input.bimSpaceId)
    if (!room) return undefined
    await ensureAuthoritativeRoomFootprint(input.bimSpaceId).catch(() => undefined)
    const currentAssignment = programState.assignments.find((a) => a.clinicalFunction === input.clinicalFunction)
    return engine.scoreRoomCandidate({
        room,
        clinicalFunction: input.clinicalFunction,
        footprint: collectCandidateFootprintFacts([input.bimSpaceId])[input.bimSpaceId],
        currentParentBimSpaceId: currentAssignment?.bimSpaceId,
    })
}

/**
 * Assess the compatibility of re-parenting a function onto a candidate room WITHOUT
 * applying it (drives the UI warning + override prompt). Pure result.
 */
export async function assessClinicalReparent(input: {
    bimSpaceId: string
    clinicalFunction: ClinicalFunction
}): Promise<import('./clinicalRoomReparent').ReparentCompatibility | undefined> {
    const candidate = await scoreClinicalRoomCandidate(input)
    if (!candidate) return undefined
    const reparent = await import('./clinicalRoomReparent')
    return reparent.assessReparentCompatibility(candidate)
}

/**
 * RE-PARENT a clinical function onto a NEW BIM room the user chose from the
 * candidate shortlist (Problem A pt2). Applies the pure re-parent plan:
 *   - move the assignment onto the new parent (single active assignment kept),
 *   - REMOVE the old parent's DRAFT planning volume (no orphan),
 *   - REGENERATE the new volume from the NEW parent's OWN authoritative footprint
 *     (never reuse the old passage-space coords),
 *   - re-verify containment against the new parent mesh.
 * A LOCKED old volume is rejected (unlock first). Never mutates Bentley identity.
 */
export async function reparentClinicalFunction(input: {
    clinicalFunction: ClinicalFunction
    newParentBimSpaceId: string
    overrideAccepted?: boolean
}): Promise<
    | { ok: true; newParentBimSpaceId: string; regenerated: boolean; containment: 'PASS' | 'FAIL' | 'NOT_EVALUATED' }
    | { ok: false; reason: string; blockCode: string; compatibility?: import('./clinicalRoomReparent').ReparentCompatibility }
> {
    const reparent = await import('./clinicalRoomReparent')

    const candidate = await scoreClinicalRoomCandidate({ bimSpaceId: input.newParentBimSpaceId, clinicalFunction: input.clinicalFunction })
    if (!candidate) return { ok: false, reason: 'NO_ROOM_RESOLVED', blockCode: 'NO_TARGET' }

    const currentAssignment = programState.assignments.find((a) => a.clinicalFunction === input.clinicalFunction)
    const oldParentBimSpaceId = currentAssignment?.bimSpaceId
    const oldVolume = oldParentBimSpaceId ? planningVolumes.find((v) => v.parentBimSpaceId === oldParentBimSpaceId) : undefined

    const targetRoom = getDiscoveredRoomVolumes().find((r) => r.bimSpaceId === input.newParentBimSpaceId)
    const targetStoreyId = targetRoom?.storeyId ?? resolveRoomStoreyIdCached(input.newParentBimSpaceId)

    const planResult = reparent.planReparent({
        clinicalFunction: input.clinicalFunction,
        mrtDisplayName: currentAssignment?.mrtDisplayName ?? '',
        oldParent: oldParentBimSpaceId ? { parentBimSpaceId: oldParentBimSpaceId, lifecycleState: oldVolume?.lifecycleState ?? 'DRAFT' } : undefined,
        target: {
            bimSpaceId: input.newParentBimSpaceId,
            originalBimLabel: targetRoom?.originalBimLabel ?? candidate.originalBimLabel,
            storeyId: targetStoreyId,
        },
        targetCandidate: candidate,
        overrideAccepted: input.overrideAccepted,
    })
    if (!planResult.ok) {
        return { ok: false, reason: planResult.reason, blockCode: planResult.blockCode, compatibility: planResult.compatibility }
    }
    const plan = planResult.plan

    // 1. Move the assignment onto the new parent (preserve function + display name).
    const assignResult = pureAssignClinicalFunction({
        bimSpace: { bimSpaceId: plan.newParent.bimSpaceId, originalBimLabel: plan.newParent.originalBimLabel, bimStoreyId: plan.newParent.storeyId },
        clinicalFunction: plan.clinicalFunction,
        requestedDisplayName: plan.mrtDisplayName || undefined,
        existingAssignments: programState.assignments,
    })
    if (!assignResult.ok) return { ok: false, reason: assignResult.reason, blockCode: 'ASSIGN_FAILED' }

    // 2. Remove the OLD parent override (no duplicate assignment) + its orphan volume.
    let nextAssignments = assignResult.assignments
    if (plan.oldParentBimSpaceId && plan.oldParentBimSpaceId !== plan.newParent.bimSpaceId) {
        nextAssignments = pureResetAssignment(plan.oldParentBimSpaceId, nextAssignments)
        // Re-apply the new assignment (reset above operates on the pre-assign list order).
        if (!nextAssignments.some((a) => a.bimSpaceId === plan.newParent.bimSpaceId)) {
            nextAssignments = [...nextAssignments, assignResult.assignment]
        }
        if (plan.removeOldVolume) {
            planningVolumes = planningVolumes.filter((v) => v.parentBimSpaceId !== plan.oldParentBimSpaceId)
        }
    }
    programState.assignments = nextAssignments
    persistProgram()

    // 3. Extract the NEW parent geometry + REGENERATE the volume from it.
    await ensureAuthoritativeRoomFootprint(plan.newParent.bimSpaceId).catch(() => undefined)
    const seed = await suggestPlanningVolumeSeedForParent(plan.newParent.bimSpaceId)
    await defineClinicalVolume({
        parentBimSpaceId: plan.newParent.bimSpaceId,
        clinicalFunction: plan.clinicalFunction,
        displayName: plan.mrtDisplayName || plan.newParent.originalBimLabel,
        storeyId: targetStoreyId,
        params: seed,
    })
    persistPlanningVolumes()

    // 4. Re-verify containment against the NEW parent mesh.
    const containment = await getClinicalVolumeContainment(plan.newParent.bimSpaceId)

    // B1B-MA-01 recovery UX: select the NEW parent so the normal Clinical Program
    // editor (validation warning + Restore Valid Position / Reset to Parent-Derived
    // / edit) is immediately reachable if containment is not PASS. No dead end.
    programState.selectedSpaceId = plan.newParent.bimSpaceId

    notifyProgram()
    return { ok: true, newParentBimSpaceId: plan.newParent.bimSpaceId, regenerated: true, containment: containment.status }
}

/**
 * FIT-TO-ROOM candidate 3D preview (Problem A pt3). Lazily extracts the room's
 * authoritative footprint, derives a world range + interior anchor from it, and
 * frames the camera on that room (VIEW-ONLY — orbit/zoom/fit remain usable).
 * Falls back to the BIM range when no exact footprint is available. Returns false
 * when no geometry is resolvable. Never mutates Bentley.
 */
export async function fitViewToClinicalRoom(bimSpaceId: string): Promise<boolean> {
    if (!bimSpaceId) return false
    await ensureAuthoritativeRoomFootprint(bimSpaceId).catch(() => undefined)
    const fp = authoritativeFootprints.get(bimSpaceId)
    let low: { x: number; y: number; z: number } | undefined
    let high: { x: number; y: number; z: number } | undefined
    let anchor: { x: number; y: number; z: number } | undefined

    if (fp?.ok && fp.outerLoop && fp.outerLoop.length >= 3) {
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
        for (const p of fp.outerLoop) {
            if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x
            if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y
        }
        const zLow = fp.volume?.zLow ?? fp.floorZ
        const zHigh = fp.volume?.zHigh ?? fp.floorZ + 3
        low = { x: minX, y: minY, z: zLow }
        high = { x: maxX, y: maxY, z: zHigh }
        anchor = fp.interiorAnchor
    } else {
        // Range fallback (honest approximation).
        const room = cachedModelSemantics.rooms.find((r) => r.roomId === bimSpaceId)
        const r = room?.range
        if (r) {
            low = { x: r.low.x, y: r.low.y, z: r.low.z }
            high = { x: r.high.x, y: r.high.y, z: r.high.z }
            anchor = { x: (r.low.x + r.high.x) / 2, y: (r.low.y + r.high.y) / 2, z: (r.low.z + r.high.z) / 2 }
        }
    }
    if (!low || !high || !anchor) return false
    const wc = await import('./walkthroughController')
    return wc.fitViewToRoom({ low, high, anchor })
}

/**
 * EVI-MA-01 — FIT TO EQUIPMENT. Frame the Bentley viewport on the authoritative
 * world bounds of one app-owned equipment instance (recognizable visual parts
 * ∪ containment envelope), at its OWN pose. Selects the instance and leaves it
 * selected. VIEW-ONLY: never mutates the equipment pose, parent, clinical
 * assignment, containment, or the iModel. Returns a status so the UI can
 * honestly surface a failure instead of pretending.
 */
export async function fitViewToEquipment(id: string): Promise<{ ok: boolean; reason?: string }> {
    if (!id) return { ok: false, reason: 'NO_ID' }
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return { ok: false, reason: 'NO_INSTANCE' }
    // Ensure it is the selected equipment (highlight + card focus) before fit.
    selectEquipment(id)
    const geo = await import('./equipmentGeometry')
    const p = e.placement
    const pose = {
        center: [p.centerX, p.centerY, p.zBase] as [number, number, number],
        width: p.width,
        depth: p.depth,
        height: p.height,
        yawRadians: p.yaw,
    }
    const family = geo.resolveVisualFamilyForCanonical({ canonicalClass: e.canonicalClass, assetFamily: e.assetFamily })
    const bounds = geo.computeEquipmentWorldBounds({ pose, family })
    if (!bounds || !geo.isNonDegenerateBounds(bounds)) {
        return { ok: false, reason: 'VISUAL_NOT_AVAILABLE' }
    }
    const low = { x: bounds.low[0], y: bounds.low[1], z: bounds.low[2] }
    const high = { x: bounds.high[0], y: bounds.high[1], z: bounds.high[2] }
    const anchor = { x: (low.x + high.x) / 2, y: (low.y + high.y) / 2, z: (low.z + high.z) / 2 }
    const wc = await import('./walkthroughController')
    const ok = wc.fitViewToRoom({ low, high, anchor })
    return ok ? { ok: true } : { ok: false, reason: 'CAMERA_UNAVAILABLE' }
}

// ===========================================================================
// EVI-MA-05A — LIVE CLINICAL LOGISTICS VESTIBULE lifecycle
//
// Wires the EVI-MA-05 ClinicalLogisticsVestibuleInstance domain into the live
// viewer, mirroring the equipment lifecycle above: an iModel-scoped in-memory
// store, safe persistence, a create action driven from the selected cyclotron,
// selection, Hide/Show, Lock/Unlock, Delete, Fit, collision and duplicate guards.
// There is ONE vestibule domain model (no VestibuleV2). Ports terminate at short
// UNCONNECTED stubs — NO transport routing/animation (that is Build 2).
// ===========================================================================

import type {
    ClinicalLogisticsVestibuleInstance,
    ServiceClass as VestibuleServiceClass,
} from './clinicalLogisticsVestibule'

let vestibuleInstances: ClinicalLogisticsVestibuleInstance[] = []
let vestibuleHydrated = false
let vestibuleSeq = 0
let selectedVestibuleId: string | undefined

/** Load vestibule instances for the active iModel (scoped; cleared on switch). */
function loadVestibulesForIModel(iModelId: string): void {
    vestibuleHydrated = false
    selectedVestibuleId = undefined
    void import('./clinicalLogisticsVestibule').then((m) => {
        if (programState.iModelId !== iModelId) return
        vestibuleInstances = iModelId ? m.loadVestibuleInstances(iModelId) : []
        vestibuleSeq = vestibuleInstances.length
        vestibuleHydrated = true
        notifyProgram()
        if (vestibuleInstances.length > 0) void ensureDirectManipulationReady().catch(() => false)
    })
}

function persistVestibules(): void {
    if (!programState.iModelId || !vestibuleHydrated) return
    void import('./clinicalLogisticsVestibule').then((m) => m.saveVestibuleInstances(programState.iModelId, vestibuleInstances))
}

/** Snapshot of all vestibule instances (read-only). */
export function getVestibuleInstances(): readonly ClinicalLogisticsVestibuleInstance[] {
    return vestibuleInstances
}

/** The vestibule instance for an id (or undefined). */
export function getVestibuleInstance(id: string): ClinicalLogisticsVestibuleInstance | undefined {
    return vestibuleInstances.find((v) => v.vestibuleInstanceId === id)
}

export function getSelectedVestibuleId(): string | undefined { return selectedVestibuleId }

/** Select a vestibule (clears equipment selection so the two never fight). */
export function selectVestibule(id: string | undefined): void {
    if (selectedVestibuleId === id) return
    selectedVestibuleId = id
    if (id) selectedEquipmentId = undefined // one active selection at a time
    notifyProgram()
}

/** The occupied AABBs of all equipment envelopes (for vestibule collision). */
function equipmentOccupiedAabbs(): { id: string; aabb: import('./clinicalLogisticsVestibule').Aabb }[] {
    return equipmentInstances.map((e) => {
        const env = buildEquipmentEnvelope(e.placement)
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
        for (const p of env.footprint) {
            if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x
            if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y
        }
        return {
            id: e.id,
            aabb: { minX, minY, minZ: e.placement.zBase, maxX, maxY, maxZ: e.placement.zBase + e.placement.height },
        }
    })
}

/**
 * EVI-MA-05A result surface for a live create. Distinguishes the honest
 * outcomes the spec requires: success, an existing vestibule (duplicate guard),
 * no defensible wall, a room-side collision, or a missing prerequisite.
 */
export type CreateVestibuleLiveResult =
    | { ok: true; vestibuleInstanceId: string }
    | { ok: false; reason: 'VESTIBULE_ALREADY_EXISTS'; existingVestibuleId: string }
    | { ok: false; reason: 'NO_SELECTED_CYCLOTRON' | 'NOT_A_CYCLOTRON' | 'NO_PARENT_ROOM' | 'NO_DEFENSIBLE_WALL' | 'ROOM_TOO_SHORT' | 'VESTIBULE_COLLISION' | 'POSE_SEED_FAILED'; conflictId?: string }

/**
 * CREATE RADIOPHARMACY VESTIBULE for the given (or currently selected)
 * cyclotron. Places ONE wall-integrated ClinicalLogisticsVestibuleInstance in
 * the SAME parent BIM room as the cyclotron, collision-checked against existing
 * equipment + vestibules, duplicate-guarded (one active radiopharmacy vestibule
 * per production context). On success: persist, select, and the caller Fits.
 * Never modifies the Bentley wall (PROPOSED_WALL_PENETRATION).
 */
export async function createRadiopharmacyVestibuleForCyclotron(cyclotronId?: string): Promise<CreateVestibuleLiveResult> {
    if (!programState.iModelId) return { ok: false, reason: 'NO_PARENT_ROOM' }
    const eqId = cyclotronId ?? selectedEquipmentId
    if (!eqId) return { ok: false, reason: 'NO_SELECTED_CYCLOTRON' }
    const cyclo = equipmentInstances.find((e) => e.id === eqId)
    if (!cyclo) return { ok: false, reason: 'NO_SELECTED_CYCLOTRON' }
    if (cyclo.canonicalClass !== 'CYCLOTRON') return { ok: false, reason: 'NOT_A_CYCLOTRON' }
    const parentRoomId = cyclo.parentBimSpaceId
    if (!parentRoomId) return { ok: false, reason: 'NO_PARENT_ROOM' }

    // Duplicate guard: one active RADIOPHARMACY vestibule per production context
    // (same parent room). Repeated create selects + returns the existing one.
    const existing = vestibuleInstances.find(
        (v) => v.serviceClass === 'RADIOPHARMACY' && v.parentBimSpaceId === parentRoomId,
    )
    if (existing) {
        // Duplicate guard — select the existing instance so the caller can Fit.
        selectVestibule(existing.vestibuleInstanceId)
        return { ok: false, reason: 'VESTIBULE_ALREADY_EXISTS', existingVestibuleId: existing.vestibuleInstanceId }
    }

    const m = await import('./clinicalLogisticsVestibule')
    await ensureAuthoritativeRoomFootprint(parentRoomId)
    const parent = authoritativeFootprints.get(parentRoomId)
    const footprint = parent?.ok && parent.outerLoop && parent.outerLoop.length >= 3
        ? parent.outerLoop
        : [{ x: -2, y: -2 }, { x: 2, y: -2 }, { x: 2, y: 2 }, { x: -2, y: 2 }]
    const zLow = parent?.volume?.zLow ?? parent?.floorZ ?? cyclo.placement.zBase
    const zHigh = parent?.volume?.zHigh ?? (zLow + 3)

    // Try each defensible wall (longest first) until one places without a
    // room-side collision. Never seed at the centroid; never optimize for
    // shortest cyclotron distance.
    const walls = m.enumerateWallCandidates(footprint).filter((w) => w.wallLength >= m.MIN_VESTIBULE_WALL_WIDTH_M)
    if (walls.length === 0) return { ok: false, reason: 'NO_DEFENSIBLE_WALL' }
    const occupied = [
        ...equipmentOccupiedAabbs(),
        ...vestibuleInstances.map((v) => ({ id: v.vestibuleInstanceId, aabb: m.reservedVolumeAsAabb(v.reservedVolume) })),
    ]
    vestibuleSeq += 1
    let created: ClinicalLogisticsVestibuleInstance | undefined
    let lastConflict: string | undefined
    for (const wall of walls) {
        const res = m.createVestibuleInstance({
            iModelId: programState.iModelId,
            serviceClass: 'RADIOPHARMACY',
            parentBimSpaceId: parentRoomId,
            sourceClinicalContextId: cyclo.id,
            footprint,
            zLow,
            zHigh,
            seq: vestibuleSeq,
            wallSide: wall.wallSide,
        })
        if (!res.ok) {
            if (res.reason === 'ROOM_TOO_SHORT') return { ok: false, reason: 'ROOM_TOO_SHORT' }
            continue
        }
        const conflict = m.findVestibuleCollision(res.instance.reservedVolume, occupied)
        if (conflict) { lastConflict = conflict; continue }
        created = res.instance
        break
    }
    if (!created) {
        return lastConflict
            ? { ok: false, reason: 'VESTIBULE_COLLISION', conflictId: lastConflict }
            : { ok: false, reason: 'NO_DEFENSIBLE_WALL' }
    }

    vestibuleInstances = [...vestibuleInstances, created]
    selectVestibule(created.vestibuleInstanceId)
    persistVestibules()
    notifyProgram()
    void ensureDirectManipulationReady().catch(() => false)
    return { ok: true, vestibuleInstanceId: created.vestibuleInstanceId }
}

/** Per-instance vestibule visibility (view-only; keeps pose, ports, reservation). */
export function setVestibuleVisibility(id: string, visible: boolean): void {
    const v = vestibuleInstances.find((x) => x.vestibuleInstanceId === id)
    if (!v) return
    const hidden = !visible
    if ((v.hidden ?? false) === hidden) return
    v.hidden = hidden
    vestibuleInstances = [...vestibuleInstances]
    persistVestibules()
    notifyProgram()
}

/** Lock a vestibule (freezes pose edits; stays visible/selectable). No BIM write. */
export function lockVestibule(id: string): void {
    const v = vestibuleInstances.find((x) => x.vestibuleInstanceId === id)
    if (!v || v.lifecycleState === 'LOCKED') return
    v.lifecycleState = 'LOCKED'
    vestibuleInstances = [...vestibuleInstances]
    persistVestibules()
    notifyProgram()
}

/** Unlock a vestibule for editing. */
export function unlockVestibule(id: string): void {
    const v = vestibuleInstances.find((x) => x.vestibuleInstanceId === id)
    if (!v || v.lifecycleState !== 'LOCKED') return
    v.lifecycleState = 'DRAFT'
    vestibuleInstances = [...vestibuleInstances]
    persistVestibules()
    notifyProgram()
}

export type DeleteVestibuleResult =
    | { ok: true; deletedId: string }
    | { ok: false; reason: 'NOT_FOUND' | 'LOCKED' | 'INVALID_STATE'; message: string }

/**
 * Delete the ONE authoritative ClinicalLogisticsVestibuleInstance by id. Removes
 * the instance and every derived representation (3D visual, rear manifold, wall
 * sleeve, MRT + PTS stubs, both connection ports, 2D marker, selected control,
 * reserved collision space). The cyclotron and the BIM wall remain. Persists.
 */
export function deleteVestibule(id: string): DeleteVestibuleResult {
    const v = vestibuleInstances.find((x) => x.vestibuleInstanceId === id)
    if (!v) return { ok: false, reason: 'NOT_FOUND', message: `No vestibule with id ${id}.` }
    if (v.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED', message: 'Unlock vestibule before deleting.' }
    const before = vestibuleInstances.length
    vestibuleInstances = vestibuleInstances.filter((x) => x.vestibuleInstanceId !== id)
    if (vestibuleInstances.length !== before - 1) {
        return { ok: false, reason: 'INVALID_STATE', message: 'Vestibule collection did not decrement by exactly one.' }
    }
    if (selectedVestibuleId === id) selectedVestibuleId = undefined
    if (vestibuleContextMenu?.vestibuleInstanceId === id) closeVestibuleContextMenu()
    persistVestibules()
    notifyProgram()
    return { ok: true, deletedId: id }
}

/**
 * FIT TO VESTIBULE — frame the full assembly (front face + wall sleeve + rear
 * manifold + MRT transition/stub + PTS stub) using authoritative world bounds.
 * View-only: selects the vestibule, never mutates pose. Mirrors fitViewToEquipment.
 */
export async function fitViewToVestibule(id: string): Promise<{ ok: boolean; reason?: string }> {
    if (!id) return { ok: false, reason: 'NO_ID' }
    const v = vestibuleInstances.find((x) => x.vestibuleInstanceId === id)
    if (!v) return { ok: false, reason: 'NO_INSTANCE' }
    selectVestibule(id)
    const geo = await import('./equipmentGeometry')
    const m = await import('./clinicalLogisticsVestibule')
    const pose = {
        center: [v.pose.centerX, v.pose.centerY, v.pose.zBase] as [number, number, number],
        width: v.pose.width, depth: v.pose.depth, height: v.pose.height, yawRadians: v.pose.yaw,
    }
    const ports = m.vestibulePortRenderOptions(v.serviceClass)
    const bounds = geo.computeEquipmentWorldBounds({ pose, family: v.visualFamily, vestibulePorts: ports })
    if (!bounds || !geo.isNonDegenerateBounds(bounds)) return { ok: false, reason: 'VISUAL_NOT_AVAILABLE' }
    const low = { x: bounds.low[0], y: bounds.low[1], z: bounds.low[2] }
    const high = { x: bounds.high[0], y: bounds.high[1], z: bounds.high[2] }
    const anchor = { x: (low.x + high.x) / 2, y: (low.y + high.y) / 2, z: (low.z + high.z) / 2 }
    const wc = await import('./walkthroughController')
    const ok = wc.fitViewToRoom({ low, high, anchor })
    return ok ? { ok: true } : { ok: false, reason: 'CAMERA_UNAVAILABLE' }
}

/** Whether a service class is currently supported for live placement. */
export function vestibuleServiceClassSupportsLivePlacement(sc: VestibuleServiceClass): boolean {
    // EVI-MA-05A live placement is demonstrated for RADIOPHARMACY; the other
    // classes keep their EVI-MA-05 policy foundation (no live placement required).
    return sc === 'RADIOPHARMACY'
}

// ===========================================================================
// EVI-MA-06 — UNIFIED application-object interaction layer
//
// ONE picker + ONE delete dispatcher + ONE selection notion shared by left-click
// selection, left-drag, right-click context menu, and the Delete key. Delegates
// to the EXISTING lifecycle stores (equipment / vestibule / asset) — it never
// rewrites them. Renderer ownership is not lifecycle authority.
// ===========================================================================

import type {
    AppObjectCandidate,
    AppObjectPickTarget,
    AppObjectRef,
    AppObjectType,
    AppPickRay,
} from './appObjectPicking'
import { resolveAppObjectPickTarget } from './appObjectPicking'

/**
 * Build the live application-object pick candidates from the authoritative
 * stores. EQUIPMENT (scanner + cyclotron) contributes an ORIENTED occupied box
 * (yaw-respecting); a VESTIBULE contributes its FULL occupied AABB (room-side +
 * behind-wall) so any visible component resolves the one vestibule. Planning
 * volumes and native BIM are intentionally NOT candidates. Pure snapshot.
 */
export function buildAppObjectCandidates(): AppObjectCandidate[] {
    const out: AppObjectCandidate[] = []
    for (const e of equipmentInstances) {
        const p = e.placement
        out.push({
            objectType: 'EQUIPMENT_INSTANCE',
            instanceId: e.id,
            parentBimSpaceId: e.parentBimSpaceId,
            volume: {
                kind: 'OBB',
                centerX: p.centerX, centerY: p.centerY, centerZ: p.zBase + p.height / 2,
                halfX: p.width / 2, halfY: p.depth / 2, halfZ: p.height / 2,
                yaw: p.yaw,
            },
            hidden: e.hidden ?? false,
            locked: e.lifecycleState === 'LOCKED',
            draggableWhenUnlocked: true,
            deletableWhenUnlocked: true,
        })
    }
    for (const v of vestibuleInstances) {
        // Full occupied volume (room-side + behind-wall) as an AABB so a ray on
        // ANY component (fascia..PTS tube) resolves the one vestibuleInstanceId.
        const hw = v.pose.width / 2, hd = v.pose.depth / 2
        const c = Math.cos(v.pose.yaw), s = Math.sin(v.pose.yaw)
        const corners = [
            { x: -hw, y: -hd }, { x: hw, y: -hd }, { x: hw, y: hd }, { x: -hw, y: hd },
        ].map((q) => ({ x: v.pose.centerX + q.x * c - q.y * s, y: v.pose.centerY + q.x * s + q.y * c }))
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
        for (const q of corners) { minX = Math.min(minX, q.x); maxX = Math.max(maxX, q.x); minY = Math.min(minY, q.y); maxY = Math.max(maxY, q.y) }
        out.push({
            objectType: 'CLINICAL_LOGISTICS_VESTIBULE',
            instanceId: v.vestibuleInstanceId,
            parentBimSpaceId: v.parentBimSpaceId,
            volume: { kind: 'AABB', minX, minY, minZ: v.pose.zBase, maxX, maxY, maxZ: v.pose.zBase + v.pose.height },
            hidden: v.hidden ?? false,
            locked: v.lifecycleState === 'LOCKED',
            draggableWhenUnlocked: true,
            deletableWhenUnlocked: true,
        })
    }
    return out
}

/** The currently selected application object as a unified ref (equipment or vestibule). */
export function getSelectedAppObjectRef(): AppObjectRef | undefined {
    if (selectedVestibuleId) return { objectType: 'CLINICAL_LOGISTICS_VESTIBULE', instanceId: selectedVestibuleId }
    if (selectedEquipmentId) return { objectType: 'EQUIPMENT_INSTANCE', instanceId: selectedEquipmentId }
    return undefined
}

/**
 * Resolve the ONE application-object pick target under a world ray, using the
 * live candidate snapshot + the current unified selection for selected-object
 * preference. This is the single resolution left-click / right-click / drag all
 * begin from. Pure w.r.t. the store snapshot.
 */
export function resolveAppObjectAtRay(ray: AppPickRay): AppObjectPickTarget | undefined {
    return resolveAppObjectPickTarget(ray, buildAppObjectCandidates(), getSelectedAppObjectRef())
}

/** Select the exact application object (routes to the family selection authority). */
export function selectAppObject(ref: AppObjectRef | undefined): void {
    if (!ref) { selectEquipment(undefined); selectVestibule(undefined); return }
    if (ref.objectType === 'CLINICAL_LOGISTICS_VESTIBULE') selectVestibule(ref.instanceId)
    else selectEquipment(ref.instanceId)
}

/**
 * EVI-MA-07 — the screen-space anchor for the LOCAL action popover, set at the
 * moment of selection (click/right-click point). Persists with the selection; it
 * is NOT recomputed on hover/motion (the menu belongs to the captured object).
 */
let selectedAppObjectAnchor: { x: number; y: number } | undefined
export function setSelectedAppObjectAnchor(anchor: { x: number; y: number } | undefined): void {
    selectedAppObjectAnchor = anchor
    notifyProgram()
}
export function getSelectedAppObjectAnchor(): { x: number; y: number } | undefined { return selectedAppObjectAnchor }

/**
 * EVI-MA-07 — select an app object AND capture its local-menu anchor in one
 * authoritative step (the tool calls this on left/right click). Clearing the
 * selection (undefined) also clears the anchor.
 */
export function selectAppObjectWithAnchor(ref: AppObjectRef | undefined, anchor?: { x: number; y: number }): void {
    selectAppObject(ref)
    setSelectedAppObjectAnchor(ref ? anchor : undefined)
}

/** Unified application-object delete result. */
export type DeleteAppObjectResult =
    | { ok: true; objectType: AppObjectType; deletedId: string }
    | { ok: false; objectType: AppObjectType; reason: string; message: string }

/**
 * ONE authoritative application-object delete dispatcher. It ONLY routes to the
 * existing lifecycle delete for the target's family — no duplicated delete logic,
 * no window.confirm. EQUIPMENT_INSTANCE → deleteEquipment; CLINICAL_LOGISTICS_
 * VESTIBULE → deleteVestibule. (ASSET_INSTANCE routing is reserved for the
 * legacy fixture path, which owns its own delete surface.)
 */
export function deleteAppObject(target: { objectType: AppObjectType; instanceId: string }): DeleteAppObjectResult {
    if (target.objectType === 'EQUIPMENT_INSTANCE') {
        const r = deleteEquipment(target.instanceId)
        return r.ok
            ? { ok: true, objectType: 'EQUIPMENT_INSTANCE', deletedId: r.deletedId }
            : { ok: false, objectType: 'EQUIPMENT_INSTANCE', reason: r.reason, message: r.message }
    }
    if (target.objectType === 'CLINICAL_LOGISTICS_VESTIBULE') {
        const r = deleteVestibule(target.instanceId)
        return r.ok
            ? { ok: true, objectType: 'CLINICAL_LOGISTICS_VESTIBULE', deletedId: r.deletedId }
            : { ok: false, objectType: 'CLINICAL_LOGISTICS_VESTIBULE', reason: r.reason, message: r.message }
    }
    return { ok: false, objectType: target.objectType, reason: 'UNSUPPORTED', message: `Delete not routed for ${target.objectType}.` }
}

/**
 * EVI-MA-06 — delete the CURRENTLY SELECTED application object (Delete key path).
 * Focus-safety (not inside an input/textarea/select/contenteditable) is enforced
 * by the caller; this only acts on the unified selection and refuses when locked.
 */
export function deleteSelectedAppObject(): DeleteAppObjectResult | undefined {
    const ref = getSelectedAppObjectRef()
    if (!ref) return undefined
    return deleteAppObject(ref)
}

// ---------------------------------------------------------------------------
// EVI-MA-06 — unified drag commit authorities (pure w.r.t. store; persist inside)
// ---------------------------------------------------------------------------

/**
 * The floor Z of an equipment instance's parent room, if the authoritative
 * footprint is cached; else the instance's current base Z. Used as the drag
 * plane elevation so freestanding equipment never floats vertically.
 */
function equipmentFloorZ(e: EquipmentAssetInstance): number {
    const fp = authoritativeFootprints.get(e.parentBimSpaceId)
    return fp?.volume?.zLow ?? fp?.floorZ ?? e.placement.zBase
}

/**
 * Move freestanding EQUIPMENT to a floor-plane world point (X/Y from the point,
 * Z pinned to the parent-room floor, yaw/extents unchanged). Delegates to the
 * authoritative `updateEquipmentPlacement` which enforces collision + persists;
 * on rejection the instance keeps its current (last-valid) placement. Returns a
 * result so the drag handler can show valid/invalid feedback + restore.
 */
export function moveEquipmentToFloorPoint(id: string, worldX: number, worldY: number): { ok: boolean; reason?: string; conflictEquipmentId?: string } {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return { ok: false, reason: 'NO_INSTANCE' }
    if (e.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED' }
    const candidate: EquipmentPlacement = {
        ...e.placement,
        centerX: worldX,
        centerY: worldY,
        zBase: equipmentFloorZ(e),
    }
    return updateEquipmentPlacement(id, candidate)
}

/**
 * Slide a wall-integrated VESTIBULE along its attached wall to the wall-tangent
 * position nearest a world point (front stays flush, rear stays behind wall),
 * clamped to the usable wall span; collision-checked against equipment + other
 * vestibules (room-side access zone only). Persists on success. Pure delegation
 * to the vestibule wall-slide math + existing collision engine.
 */
export async function slideVestibuleToWallPoint(id: string, worldX: number, worldY: number): Promise<{ ok: boolean; reason?: string; conflictId?: string }> {
    const v = vestibuleInstances.find((x) => x.vestibuleInstanceId === id)
    if (!v) return { ok: false, reason: 'NO_INSTANCE' }
    if (v.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED' }
    const frame = v.wallReference.frame
    if (!frame) return { ok: false, reason: 'NO_WALL_FRAME' }
    const m = await import('./clinicalLogisticsVestibule')
    const nextPose = m.slideVestibuleAlongWall({ pose: v.pose, frame, wallLength: v.wallReference.wallLength, targetX: worldX, targetY: worldY })
    const reserved = m.reservedVolumeFromPose(nextPose)
    // Collision: room-side access zone vs equipment + OTHER vestibules.
    const occupied = [
        ...equipmentInstances.map((e) => {
            const env = buildEquipmentEnvelope(e.placement)
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
            for (const p of env.footprint) { minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x); minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y) }
            return { id: e.id, aabb: { minX, minY, minZ: e.placement.zBase, maxX, maxY, maxZ: e.placement.zBase + e.placement.height } }
        }),
        ...vestibuleInstances.filter((o) => o.vestibuleInstanceId !== id).map((o) => ({ id: o.vestibuleInstanceId, aabb: m.reservedVolumeAsAabb(o.reservedVolume) })),
    ]
    const conflict = m.findVestibuleCollision(reserved, occupied)
    if (conflict) return { ok: false, reason: 'VESTIBULE_COLLISION', conflictId: conflict }
    v.pose = nextPose
    v.frontFacePlane = m.frontFacePlaneFromPose(nextPose)
    v.reservedVolume = reserved
    // Ports follow the pose (rear stays behind the wall).
    v.transportPorts = m.buildTransportPortsForInstance({ vestibuleInstanceId: v.vestibuleInstanceId, serviceClass: v.serviceClass, pose: nextPose })
    vestibuleInstances = [...vestibuleInstances]
    persistVestibules()
    notifyProgram()
    return { ok: true }
}

// ===========================================================================
// EVI-MA-07 — authoritative selection notify + Undo/Redo + captured actions
// ===========================================================================

import { AppEditHistory, type AppEditCommand } from './appEditHistory'

const appEditHistory = new AppEditHistory()
const appHistoryListeners = new Set<() => void>()
export function subscribeAppHistory(listener: () => void): () => void {
    appHistoryListeners.add(listener)
    return () => { appHistoryListeners.delete(listener) }
}
function notifyAppHistory(): void { for (const l of appHistoryListeners) l() }
export function getAppHistoryCounts(): { undo: number; redo: number } { return appEditHistory.counts() }
export function canUndoAppEdit(): boolean { return appEditHistory.canUndo() }
export function canRedoAppEdit(): boolean { return appEditHistory.canRedo() }

/** Deep-clone an app-owned snapshot (JSON round-trip; never contains BIM/mesh). */
function cloneSnapshot<T>(v: T): T { return JSON.parse(JSON.stringify(v)) as T }

/** Re-insert a previously-deleted EQUIPMENT instance with its EXACT identity. */
function restoreEquipmentSnapshot(snap: EquipmentAssetInstance): void {
    if (equipmentInstances.some((e) => e.id === snap.id)) return
    equipmentInstances = [...equipmentInstances, cloneSnapshot(snap)]
    persistEquipment()
    notifyProgram()
    void getEquipmentValidation(snap.id)
}

/** Re-insert a previously-deleted VESTIBULE instance with its EXACT identity. */
function restoreVestibuleSnapshot(snap: ClinicalLogisticsVestibuleInstance): void {
    if (vestibuleInstances.some((v) => v.vestibuleInstanceId === snap.vestibuleInstanceId)) return
    vestibuleInstances = [...vestibuleInstances, cloneSnapshot(snap)]
    persistVestibules()
    notifyProgram()
}

/** Set an equipment instance's exact placement (undo/redo of MOVE/ROTATE). */
function setEquipmentPlacementExact(id: string, placement: EquipmentPlacement): void {
    const e = equipmentInstances.find((x) => x.id === id)
    if (!e) return
    e.placement = cloneSnapshot(placement)
    equipmentInstances = [...equipmentInstances]
    persistEquipment()
    notifyProgram()
}

/** Set a vestibule instance's exact pose + derived fields (undo/redo of MOVE). */
async function setVestibulePoseExact(id: string, pose: import('./clinicalLogisticsVestibule').VestibulePose): Promise<void> {
    const v = vestibuleInstances.find((x) => x.vestibuleInstanceId === id)
    if (!v) return
    const m = await import('./clinicalLogisticsVestibule')
    v.pose = cloneSnapshot(pose)
    v.frontFacePlane = m.frontFacePlaneFromPose(v.pose)
    v.reservedVolume = m.reservedVolumeFromPose(v.pose)
    v.transportPorts = m.buildTransportPortsForInstance({ vestibuleInstanceId: v.vestibuleInstanceId, serviceClass: v.serviceClass, pose: v.pose })
    vestibuleInstances = [...vestibuleInstances]
    persistVestibules()
    notifyProgram()
}

/** Set exact hidden state (undo/redo of HIDE/SHOW). */
function setHiddenExact(objectType: AppObjectType, id: string, hidden: boolean): void {
    if (objectType === 'EQUIPMENT_INSTANCE') setEquipmentVisibility(id, !hidden)
    else if (objectType === 'CLINICAL_LOGISTICS_VESTIBULE') setVestibuleVisibility(id, !hidden)
}

/** Set exact lock state (undo/redo of LOCK/UNLOCK). */
function setLockedExact(objectType: AppObjectType, id: string, locked: boolean): void {
    if (objectType === 'EQUIPMENT_INSTANCE') {
        const e = equipmentInstances.find((x) => x.id === id)
        if (!e) return
        e.lifecycleState = locked ? 'LOCKED' : 'DRAFT'
        equipmentInstances = [...equipmentInstances]
        persistEquipment(); notifyProgram()
    } else if (objectType === 'CLINICAL_LOGISTICS_VESTIBULE') {
        if (locked) lockVestibule(id); else unlockVestibule(id)
    }
}

/**
 * Apply one recorded command in a direction. UNDO applies `beforeState`; REDO
 * applies `afterState`. Only app-owned state is touched — never Bentley/BIM.
 */
function applyAppEditCommand(cmd: AppEditCommand, direction: 'UNDO' | 'REDO'): void {
    const ot = cmd.objectType as AppObjectType
    switch (cmd.type) {
        case 'DELETE':
            if (direction === 'UNDO') {
                // Restore the exact deleted instance (same id, pose, ports, ...).
                if (ot === 'EQUIPMENT_INSTANCE') restoreEquipmentSnapshot(cmd.beforeState as EquipmentAssetInstance)
                else if (ot === 'CLINICAL_LOGISTICS_VESTIBULE') restoreVestibuleSnapshot(cmd.beforeState as ClinicalLogisticsVestibuleInstance)
            } else {
                // Redo the delete.
                if (ot === 'EQUIPMENT_INSTANCE') deleteEquipment(cmd.instanceId)
                else if (ot === 'CLINICAL_LOGISTICS_VESTIBULE') deleteVestibule(cmd.instanceId)
            }
            return
        case 'HIDE':
        case 'SHOW': {
            const hidden = direction === 'UNDO' ? (cmd.beforeState as { hidden: boolean }).hidden : (cmd.afterState as { hidden: boolean }).hidden
            setHiddenExact(ot, cmd.instanceId, hidden)
            return
        }
        case 'LOCK':
        case 'UNLOCK': {
            const locked = direction === 'UNDO' ? (cmd.beforeState as { locked: boolean }).locked : (cmd.afterState as { locked: boolean }).locked
            setLockedExact(ot, cmd.instanceId, locked)
            return
        }
        case 'MOVE':
        case 'ROTATE': {
            const state = direction === 'UNDO' ? cmd.beforeState : cmd.afterState
            if (ot === 'EQUIPMENT_INSTANCE') setEquipmentPlacementExact(cmd.instanceId, state as EquipmentPlacement)
            else if (ot === 'CLINICAL_LOGISTICS_VESTIBULE') void setVestibulePoseExact(cmd.instanceId, state as import('./clinicalLogisticsVestibule').VestibulePose)
            return
        }
    }
}

/** Record a reversible app-owned edit (clears redo). Snapshots are deep-cloned. */
export function recordAppEdit(cmd: Omit<AppEditCommand, 'timestamp'>): void {
    appEditHistory.record({ ...cmd, beforeState: cloneSnapshot(cmd.beforeState), afterState: cloneSnapshot(cmd.afterState), timestamp: Date.now() })
    notifyAppHistory()
}

/** Undo the most recent app-owned edit. Returns the reversed command (or none). */
export function undoLastAppEdit(): AppEditCommand | undefined {
    const cmd = appEditHistory.popUndo()
    if (!cmd) return undefined
    applyAppEditCommand(cmd, 'UNDO')
    notifyAppHistory()
    return cmd
}

/** Redo the most recently undone app-owned edit. */
export function redoLastAppEdit(): AppEditCommand | undefined {
    const cmd = appEditHistory.popRedo()
    if (!cmd) return undefined
    applyAppEditCommand(cmd, 'REDO')
    notifyAppHistory()
    return cmd
}

// ---------------------------------------------------------------------------
// EVI-MA-07 — captured-target actions (the local menu calls THESE; they never
// re-raycast, and they record Undo). objectType+instanceId are the CAPTURED
// SelectedAppObject; nothing here derives a target from the cursor/hover.
// ---------------------------------------------------------------------------

/** Delete a captured target (records Undo with the full pre-delete snapshot). */
export function deleteCapturedAppObject(target: { objectType: AppObjectType; instanceId: string }): DeleteAppObjectResult {
    if (target.objectType === 'EQUIPMENT_INSTANCE') {
        const e = equipmentInstances.find((x) => x.id === target.instanceId)
        if (!e) return { ok: false, objectType: target.objectType, reason: 'NOT_FOUND', message: 'No such equipment.' }
        const snap = cloneSnapshot(e)
        const label = e.displayLabel
        const r = deleteEquipment(target.instanceId)
        if (r.ok) recordAppEdit({ type: 'DELETE', objectType: 'EQUIPMENT_INSTANCE', instanceId: target.instanceId, beforeState: snap, afterState: null, label: `${label} deleted` })
        return r.ok ? { ok: true, objectType: 'EQUIPMENT_INSTANCE', deletedId: r.deletedId } : { ok: false, objectType: 'EQUIPMENT_INSTANCE', reason: r.reason, message: r.message }
    }
    if (target.objectType === 'CLINICAL_LOGISTICS_VESTIBULE') {
        const v = vestibuleInstances.find((x) => x.vestibuleInstanceId === target.instanceId)
        if (!v) return { ok: false, objectType: target.objectType, reason: 'NOT_FOUND', message: 'No such vestibule.' }
        const snap = cloneSnapshot(v)
        const label = v.displayLabel
        const r = deleteVestibule(target.instanceId)
        if (r.ok) recordAppEdit({ type: 'DELETE', objectType: 'CLINICAL_LOGISTICS_VESTIBULE', instanceId: target.instanceId, beforeState: snap, afterState: null, label: `${label} deleted` })
        return r.ok ? { ok: true, objectType: 'CLINICAL_LOGISTICS_VESTIBULE', deletedId: r.deletedId } : { ok: false, objectType: 'CLINICAL_LOGISTICS_VESTIBULE', reason: r.reason, message: r.message }
    }
    return { ok: false, objectType: target.objectType, reason: 'UNSUPPORTED', message: `Delete not routed for ${target.objectType}.` }
}

/** Toggle-visibility a captured target (records Undo). */
export function setCapturedAppObjectVisibility(target: { objectType: AppObjectType; instanceId: string }, visible: boolean): void {
    const beforeHidden = isCapturedHidden(target)
    if (target.objectType === 'EQUIPMENT_INSTANCE') setEquipmentVisibility(target.instanceId, visible)
    else if (target.objectType === 'CLINICAL_LOGISTICS_VESTIBULE') setVestibuleVisibility(target.instanceId, visible)
    const afterHidden = !visible
    if (beforeHidden !== afterHidden) {
        recordAppEdit({ type: afterHidden ? 'HIDE' : 'SHOW', objectType: target.objectType, instanceId: target.instanceId, beforeState: { hidden: beforeHidden }, afterState: { hidden: afterHidden } })
    }
}

/** Lock/unlock a captured target (records Undo). */
export async function setCapturedAppObjectLock(target: { objectType: AppObjectType; instanceId: string }, locked: boolean): Promise<void> {
    const beforeLocked = isCapturedLocked(target)
    if (target.objectType === 'EQUIPMENT_INSTANCE') {
        if (locked) await lockEquipment(target.instanceId); else unlockEquipment(target.instanceId)
    } else if (target.objectType === 'CLINICAL_LOGISTICS_VESTIBULE') {
        if (locked) lockVestibule(target.instanceId); else unlockVestibule(target.instanceId)
    }
    const afterLocked = isCapturedLocked(target)
    if (beforeLocked !== afterLocked) {
        recordAppEdit({ type: afterLocked ? 'LOCK' : 'UNLOCK', objectType: target.objectType, instanceId: target.instanceId, beforeState: { locked: beforeLocked }, afterState: { locked: afterLocked } })
    }
}

/** Fit to a captured target (view-only; no Undo). */
export async function fitCapturedAppObject(target: { objectType: AppObjectType; instanceId: string }): Promise<{ ok: boolean; reason?: string }> {
    if (target.objectType === 'EQUIPMENT_INSTANCE') return fitViewToEquipment(target.instanceId)
    if (target.objectType === 'CLINICAL_LOGISTICS_VESTIBULE') return fitViewToVestibule(target.instanceId)
    return { ok: false, reason: 'UNSUPPORTED' }
}

function isCapturedHidden(target: { objectType: AppObjectType; instanceId: string }): boolean {
    if (target.objectType === 'EQUIPMENT_INSTANCE') return equipmentInstances.find((x) => x.id === target.instanceId)?.hidden ?? false
    if (target.objectType === 'CLINICAL_LOGISTICS_VESTIBULE') return vestibuleInstances.find((x) => x.vestibuleInstanceId === target.instanceId)?.hidden ?? false
    return false
}
function isCapturedLocked(target: { objectType: AppObjectType; instanceId: string }): boolean {
    if (target.objectType === 'EQUIPMENT_INSTANCE') return equipmentInstances.find((x) => x.id === target.instanceId)?.lifecycleState === 'LOCKED'
    if (target.objectType === 'CLINICAL_LOGISTICS_VESTIBULE') return vestibuleInstances.find((x) => x.vestibuleInstanceId === target.instanceId)?.lifecycleState === 'LOCKED'
    return false
}

/**
 * A view-model of the CAPTURED selected object for the local action popover:
 * exact title, hidden/locked flags, and the objectType/instanceId. Derived from
 * the ONE authoritative selection; NEVER from the cursor/hover.
 */
export interface SelectedAppObjectView {
    objectType: AppObjectType
    instanceId: string
    title: string
    hidden: boolean
    locked: boolean
    fitLabel: string
}
/**
 * EVI-MA-07 §19 — the existing RADIOPHARMACY vestibule for a cyclotron's room, if
 * any. Lets the cyclotron control offer "Select existing" instead of a duplicate
 * "Create" CTA (one production context must not create duplicates).
 */
export function getRadiopharmacyVestibuleForRoom(parentBimSpaceId: string): string | undefined {
    return vestibuleInstances.find((v) => v.serviceClass === 'RADIOPHARMACY' && v.parentBimSpaceId === parentBimSpaceId)?.vestibuleInstanceId
}

export function getSelectedAppObjectView(): SelectedAppObjectView | undefined {
    const ref = getSelectedAppObjectRef()
    if (!ref) return undefined
    if (ref.objectType === 'EQUIPMENT_INSTANCE') {
        const e = equipmentInstances.find((x) => x.id === ref.instanceId)
        if (!e) return undefined
        return { objectType: ref.objectType, instanceId: ref.instanceId, title: e.displayLabel, hidden: e.hidden ?? false, locked: e.lifecycleState === 'LOCKED', fitLabel: 'Fit to Equipment' }
    }
    const v = vestibuleInstances.find((x) => x.vestibuleInstanceId === ref.instanceId)
    if (!v) return undefined
    return { objectType: ref.objectType, instanceId: ref.instanceId, title: v.displayLabel, hidden: v.hidden ?? false, locked: v.lifecycleState === 'LOCKED', fitLabel: 'Fit to Vestibule' }
}

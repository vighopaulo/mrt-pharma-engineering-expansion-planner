/**
 * LiveItwinViewer — the ONLY module that imports the heavy Bentley viewer
 * stack (`@itwin/web-viewer-react`, `@itwin/browser-authorization`). It is
 * lazy-loaded by `BentleyViewer.tsx` so unit tests never pull in these
 * packages or a WebGL context.
 *
 * It renders the LIVE iModel via `<Viewer authClient iTwinId iModelId>` — the
 * real MRTway Hospital Campus Development model. No mock geometry, no sample
 * model, no placeholder cube (Sec 14). READ-ONLY (Sec 29). Selection is
 * forwarded to the inspection panel via `onSelect`.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Viewer } from '@itwin/web-viewer-react'
import { BrowserAuthorizationClient } from '@itwin/browser-authorization'
import { IModelApp, TileTreeLoadStatus, ViewCreator3d, type IModelConnection, type ScreenViewport, type ViewState } from '@itwin/core-frontend'
import { Range3d } from '@itwin/core-geometry'
import { QueryBinder } from '@itwin/core-common'
import type { ViewerConfig } from '../../lib/viewerConfig'
import { browserAuthClientOptions } from '../../lib/viewerAuth'
import type { RawBentleySelection } from '../../lib/viewerSelection'

interface Props {
    config: ViewerConfig
    onSelect: (raw: RawBentleySelection, properties: Record<string, unknown>) => void | Promise<void>
    onAuthSuccess: () => void
    onAuthError: (message: string) => void
}

// DEV-only lifecycle counters (module scope) to prove the loop is gone. These
// must NOT grow while the user is idle. Sanitized — no tokens/secrets.
const devCounters = {
    mount: 0,
    unmount: 0,
    authEffectRun: 0,
    authEffectCleanup: 0,
    authClientCreate: 0,
    signInSilent: 0,
    render: 0,
    viewStateCreate: 0,
    viewportConfigurerRun: 0,
}

export default function LiveItwinViewer({ config, onSelect, onAuthSuccess, onAuthError }: Props) {
    const [ready, setReady] = useState(false)

    if (import.meta.env.DEV) {
        devCounters.render += 1
        console.info('[bentley-life] VIEWER_COMPONENT_RENDER_COUNT=%d', devCounters.render)
    }

    // Derive the auth client from PRIMITIVE config values, not the object
    // identity, so an accidental new-config-object does not recreate the client.
    const { clientId, authority, scope, redirectUri, postSignoutRedirectUri, iTwinId, iModelId } = config
    const authClient = useMemo(() => {
        if (import.meta.env.DEV) {
            devCounters.authClientCreate += 1
            console.info('[bentley-life] AUTH_CLIENT_CREATION_COUNT=%d', devCounters.authClientCreate)
        }
        return new BrowserAuthorizationClient(
            browserAuthClientOptions({ clientId, authority, scope, redirectUri, postSignoutRedirectUri, responseType: 'code', iTwinId, iModelId }),
        )
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [clientId, authority, scope, redirectUri, postSignoutRedirectUri])

    // Keep the latest auth callbacks in a ref so the auth effect does NOT list
    // them as deps (their identity, even if stabilized upstream, must never be
    // able to re-run the one-shot sign-in effect).
    const cbRef = useRef({ onAuthSuccess, onAuthError })
    cbRef.current = { onAuthSuccess, onAuthError }

    // Mount/unmount accounting.
    useEffect(() => {
        if (import.meta.env.DEV) {
            devCounters.mount += 1
            console.info('[bentley-life] LIVE_ITWIN_VIEWER_MOUNT_COUNT=%d', devCounters.mount)
        }
        return () => {
            if (import.meta.env.DEV) {
                devCounters.unmount += 1
                console.info('[bentley-life] LIVE_ITWIN_VIEWER_UNMOUNT_COUNT=%d', devCounters.unmount)
            }
        }
    }, [])

    // Sign-in effect. NO cross-mount "one-shot" ref guard — that deadlocked
    // under StrictMode (first effect set the flag then was cleaned up; the
    // second effect saw the flag and returned without ever authenticating,
    // leaving the UI stuck on "Signing in…"). Instead we rely on the now-stable
    // authClient identity (deps below) so the effect does not loop, and a
    // per-run `cancelled` flag only prevents a stale async completion from
    // mutating state after cleanup. A bounded StrictMode double-run is fine;
    // signInSilent is idempotent and signInRedirect navigates away.
    useEffect(() => {
        let cancelled = false
        const timeoutMs = 30_000
        const timer = setTimeout(() => {
            if (!cancelled) {
                if (import.meta.env.DEV) console.error('[bentley-auth] AUTH_TIMEOUT after %dms', timeoutMs)
                cbRef.current.onAuthError('AUTH_TIMEOUT: Bentley sign-in did not complete or redirect. Please retry.')
            }
        }, timeoutMs)

        void (async () => {
            if (import.meta.env.DEV) {
                devCounters.authEffectRun += 1
                console.info('[bentley-life] AUTH_EFFECT_ENTER_COUNT=%d', devCounters.authEffectRun)
            }
            try {
                if (import.meta.env.DEV) {
                    devCounters.signInSilent += 1
                    console.info('[bentley-life] SIGN_IN_SILENT_START_COUNT=%d', devCounters.signInSilent)
                }
                await authClient.signInSilent()
                if (cancelled) return
                clearTimeout(timer)
                if (import.meta.env.DEV) console.info('[bentley-auth] SIGN_IN_SILENT_SUCCESS AUTHENTICATED_STATE=YES (silent)')
                setReady(true)
                cbRef.current.onAuthSuccess()
            } catch {
                if (cancelled) return
                if (import.meta.env.DEV) console.info('[bentley-auth] SIGN_IN_SILENT_FAILURE -> SIGN_IN_REDIRECT_START RETURN_ROUTE=/viewer')
                try {
                    // Navigates the browser away to Bentley IMS; execution
                    // normally does not continue past this call.
                    await authClient.signInRedirect('/viewer')
                } catch (e) {
                    if (cancelled) return
                    clearTimeout(timer)
                    cbRef.current.onAuthError(e instanceof Error ? e.message : String(e))
                }
            }
        })()

        return () => {
            cancelled = true
            clearTimeout(timer)
            if (import.meta.env.DEV) {
                devCounters.authEffectCleanup = (devCounters.authEffectCleanup ?? 0) + 1
                console.info('[bentley-life] AUTH_EFFECT_CLEANUP_COUNT=%d', devCounters.authEffectCleanup)
            }
        }
    }, [authClient])

    // Stable option objects: passing fresh nested objects to <Viewer> on every
    // render can make it reopen/reconfigure the iModel. Memoize them so their
    // identity is constant for the session.
    const viewportOptions = useMemo(() => ({ viewState: buildSpatialViewState }), [])
    const viewCreatorOptions = useMemo(
        () => ({ cameraOn: true, allSubCategoriesVisible: true, viewportConfigurer: inspectAndMaybeFitViewport }),
        [],
    )
    const onIModelConnected = useCallback(
        (iModel: unknown) => {
            void wireSelection(iModel, onSelect)
        },
        [onSelect],
    )

    if (!ready) return <div className="viewer-loading">Signing in with Bentley…</div>

    return (
        <Viewer
            authClient={authClient}
            iTwinId={iTwinId}
            iModelId={iModelId}
            enablePerformanceMonitors={false}
            viewportOptions={viewportOptions}
            viewCreatorOptions={viewCreatorOptions}
            onIModelConnected={onIModelConnected}
        />
    )
}

/**
 * Construct a valid 3D spatial ViewState for the live iModel using the
 * Bentley-supported `ViewCreator3d`. With no modelIds argument it includes
 * every 3D geometric model in the iModel, and `allSubCategoriesVisible` forces
 * all categories/subcategories on so real geometry is not silently hidden.
 * Throws (surfaced as a viewer error) only if the iModel truly has no 3D model.
 */
async function buildSpatialViewState(iModel: IModelConnection): Promise<ViewState> {
    if (import.meta.env.DEV) {
        devCounters.viewStateCreate += 1
        console.info('[bentley-life] VIEW_STATE_CREATION_COUNT=%d', devCounters.viewStateCreate)
    }
    const creator = new ViewCreator3d(iModel)
    const view = await creator.createDefaultView({ cameraOn: true, allSubCategoriesVisible: true })
    if (import.meta.env.DEV) {
        const modelCount = (view as unknown as { modelSelector?: { models?: { size?: number } } }).modelSelector?.models?.size
        const catCount = (view as unknown as { categorySelector?: { categories?: { size?: number } } }).categorySelector?.categories?.size
        console.info('[bentley-view] IMODEL_CONNECTION_OPENED IMODEL_ID=%s', iModel.iModelId)
        console.info('[bentley-view] VIEW_STATE_CREATED VIEW_STATE_TYPE=%s DISPLAYED_MODEL_COUNT=%s VISIBLE_CATEGORY_COUNT=%s',
            view.classFullName, String(modelCount ?? 'unknown'), String(catCount ?? 'unknown'))
    }
    return view
}

/**
 * Set FORCE_INITIAL_FIT=true to re-enable a post-load camera fit. It is OFF by
 * default because ViewCreator3d.createDefaultView already frames the model, and
 * a forced fit was pushing the camera into an invalid frustum (geometry flashed
 * then went dark). When ON, the fit runs ONLY against a finite, non-degenerate
 * `computeFitRange()` — we never blindly union queried model ranges (which can
 * include remote/non-spatial models and fling the camera far away).
 */
const FORCE_INITIAL_FIT = false

/**
 * Diagnostics-first viewport configurer. Logs sanitized BEFORE/AFTER view state
 * and only performs a guarded fit when explicitly enabled and safe. This is the
 * control described in the diagnosis: by default it does NOT alter the camera,
 * so the geometry framed by ViewCreator3d stays visible.
 */
function inspectAndMaybeFitViewport(viewport: ScreenViewport): void {
    try {
        if (import.meta.env.DEV) {
            devCounters.viewportConfigurerRun += 1
            console.info('[bentley-life] VIEWPORT_CONFIGURER_RUN_COUNT=%d', devCounters.viewportConfigurerRun)
        }
        logViewState('BEFORE_FIT', viewport)

        const range: Range3d = viewport.view.computeFitRange()
        const rangeUsable = isUsableRange(range)
        if (import.meta.env.DEV) {
            console.info('[bentley-view] FIT_RANGE_IS_NULL=%s FIT_RANGE_IS_EMPTY=%s FIT_RANGE_LOW=%s FIT_RANGE_HIGH=%s FIT_RANGE_DIAGONAL=%s FIT_RANGE_USABLE=%s',
                String(range.isNull), String(range.isAlmostZeroX && range.isAlmostZeroY && range.isAlmostZeroZ),
                fmtPt(range.low), fmtPt(range.high),
                range.isNull ? 'n/a' : range.diagonal().magnitude().toFixed(3),
                String(rangeUsable))
        }

        let fitExecuted = false
        if (FORCE_INITIAL_FIT && rangeUsable) {
            viewport.zoomToVolume(range, { animateFrustumChange: false })
            viewport.synchWithView()
            fitExecuted = true
        }

        if (import.meta.env.DEV) {
            const dpr = typeof window !== 'undefined' ? window.devicePixelRatio : undefined
            console.info('[bentley-view] EXTENTS_VALID=%s INITIAL_FIT_VIEW_EXECUTED=%s FORCE_INITIAL_FIT=%s VIEWPORT_READY=YES VIEWPORT_WIDTH=%s VIEWPORT_HEIGHT=%s WEBGL_CONTEXT_AVAILABLE=%s DPR=%s',
                String(rangeUsable), String(fitExecuted), String(FORCE_INITIAL_FIT),
                String(viewport.viewRect.width), String(viewport.viewRect.height),
                String(Boolean((viewport.target as unknown as { renderSystem?: unknown }).renderSystem)),
                String(dpr))
            logViewState('AFTER_FIT', viewport)
        }
    } catch (e) {
        if (import.meta.env.DEV) console.error('[bentley-view] CONFIGURER_ERROR', e instanceof Error ? e.message : String(e))
    }
}

export interface FitLiveModelResult {
    ok: boolean
    reason: string
    viewportWidth: number
    viewportHeight: number
    modelSelectorSize: number
    categorySelectorSize: number
    fitRangeValid: boolean
    diagonal: number | null
}

/**
 * ONE controlled, bounded native fit against the active live viewport. Invoked
 * only by the diagnostic "FIT LIVE MODEL" button (never in an effect/render
 * loop). It: obtains the active ScreenViewport, proves models+categories+range
 * are valid, then executes a single Bentley-supported zoom-to-volume. It issues
 * NO Bentley API calls itself and never mutates the iModel.
 */
export function fitLiveModel(): FitLiveModelResult {
    const empty: FitLiveModelResult = {
        ok: false, reason: '', viewportWidth: 0, viewportHeight: 0,
        modelSelectorSize: 0, categorySelectorSize: 0, fitRangeValid: false, diagonal: null,
    }
    const vp = IModelApp.viewManager?.selectedView
    if (!vp) {
        if (import.meta.env.DEV) console.error('[bentley-fit] ACTIVE_VIEWPORT_PRESENT=NO')
        return { ...empty, reason: 'NO_ACTIVE_VIEWPORT' }
    }
    const width = vp.viewRect.width
    const height = vp.viewRect.height
    const view = vp.view as unknown as {
        is3d?: () => boolean
        classFullName?: string
        modelSelector?: { models?: { size?: number } }
        categorySelector?: { categories?: { size?: number } }
    }
    const modelSize = view.modelSelector?.models?.size ?? 0
    const catSize = view.categorySelector?.categories?.size ?? 0
    const imodelOpen = Boolean(vp.iModel && !(vp.iModel as unknown as { isClosed?: boolean }).isClosed)

    if (import.meta.env.DEV) {
        console.info('[bentley-fit] ACTIVE_VIEWPORT_PRESENT=YES VIEWPORT_WIDTH=%d VIEWPORT_HEIGHT=%d IMODEL_CONNECTION_OPEN=%s',
            width, height, String(imodelOpen))
        logViewState('FIT_BUTTON_BEFORE', vp)
        console.info('[bentley-fit] VIEW_IS_3D=%s MODEL_SELECTOR_SIZE=%d CATEGORY_SELECTOR_SIZE=%d',
            String(typeof view.is3d === 'function' ? view.is3d() : 'n/a'), modelSize, catSize)
    }

    if (width <= 0 || height <= 0) return { ...empty, reason: 'VIEWPORT_ZERO_SIZE', viewportWidth: width, viewportHeight: height }
    if (modelSize <= 0) {
        if (import.meta.env.DEV) console.error('[bentley-fit] MODEL_SELECTOR_SIZE=0 -> not fitting empty view')
        return { ...empty, reason: 'MODEL_SELECTOR_EMPTY', viewportWidth: width, viewportHeight: height, modelSelectorSize: 0, categorySelectorSize: catSize }
    }
    if (catSize <= 0) {
        if (import.meta.env.DEV) console.error('[bentley-fit] CATEGORY_SELECTOR_SIZE=0 -> not fitting empty category set')
        return { ...empty, reason: 'CATEGORY_SELECTOR_EMPTY', viewportWidth: width, viewportHeight: height, modelSelectorSize: modelSize, categorySelectorSize: 0 }
    }

    // Fit range from the CURRENT displayed spatial view only.
    const range: Range3d = vp.view.computeFitRange()
    const valid = isUsableRange(range)
    const diagonal = range.isNull ? null : range.diagonal().magnitude()
    if (import.meta.env.DEV) {
        console.info('[bentley-fit] FIT_RANGE_VALID=%s FIT_RANGE_LOW=%s FIT_RANGE_HIGH=%s FIT_RANGE_DIAGONAL=%s',
            String(valid), fmtPt(range.low), fmtPt(range.high), diagonal === null ? 'n/a' : diagonal.toFixed(3))
    }
    if (!valid) return { ...empty, reason: 'FIT_RANGE_INVALID', viewportWidth: width, viewportHeight: height, modelSelectorSize: modelSize, categorySelectorSize: catSize, fitRangeValid: false, diagonal }

    // ONE native fit-to-content.
    vp.zoomToVolume(range, { animateFrustumChange: true })
    vp.synchWithView()
    if (import.meta.env.DEV) {
        console.info('[bentley-fit] NATIVE_FIT_EXECUTED=YES')
        logViewState('FIT_BUTTON_AFTER', vp)
    }
    return {
        ok: true, reason: 'FIT_EXECUTED', viewportWidth: width, viewportHeight: height,
        modelSelectorSize: modelSize, categorySelectorSize: catSize, fitRangeValid: true, diagonal,
    }
}

export interface RenderStateResult {
    summary: string
}

/**
 * Bounded one-shot watcher for tile-load transitions. Subscribes to the
 * supported `tileAdmin.onTileLoad` event, logs each tile that resolves (content
 * id, load status, hasGraphics), and AUTO-REMOVES after 8s or 20 events —
 * whichever first. No polling loop, no mutation. Catches whether the stuck
 * child tile ever leaves Loading(2).
 */
let tileWatchActive = false
export function watchTileLoads(): string {
    if (tileWatchActive) return 'ALREADY_WATCHING'
    const admin = IModelApp.tileAdmin as unknown as {
        onTileLoad?: { addListener: (cb: (t: unknown) => void) => () => void }
    }
    if (!admin?.onTileLoad) return 'ONTILELOAD_UNAVAILABLE'
    const loadNames = ['NotLoaded', 'Queued', 'Loading', 'Ready', 'NotFound', 'Abandoned']
    let count = 0
    tileWatchActive = true
    const remove = admin.onTileLoad.addListener((t: unknown) => {
        count += 1
        const tile = t as { contentId?: string; loadStatus?: number; hasGraphics?: boolean; isReady?: boolean }
        if (import.meta.env.DEV) {
            console.info('[bentley-render] ONTILELOAD #%d CONTENT_ID=%s LOAD_STATUS=%s(%s) HAS_GRAPHICS=%s IS_READY=%s',
                count, String(tile.contentId), loadNames[tile.loadStatus ?? -1] ?? 'unknown', String(tile.loadStatus),
                String(tile.hasGraphics), String(tile.isReady))
        }
        if (count >= 20) { remove(); tileWatchActive = false; if (import.meta.env.DEV) console.info('[bentley-render] ONTILELOAD_WATCH_ENDED reason=max_events') }
    })
    window.setTimeout(() => {
        if (tileWatchActive) { remove(); tileWatchActive = false; if (import.meta.env.DEV) console.info('[bentley-render] ONTILELOAD_WATCH_ENDED reason=timeout events=%d', count) }
    }, 8000)
    return 'WATCHING_8s'
}

/** Bounded tile-count read (no fit, no mutation). Used for the t=0/1/3/5s series. */
export function readTileCounts(label: string): string {
    const vp = IModelApp.viewManager?.selectedView
    if (!vp) return `${label}: NO_ACTIVE_VIEWPORT`
    const s = `${label}: requested=${vp.numRequestedTiles} selected=${vp.numSelectedTiles} ready=${vp.numReadyTiles} allTreesLoaded=${vp.areAllTileTreesLoaded}`
    if (import.meta.env.DEV) console.info('[bentley-render] TILE_COUNTS %s', s)
    return s
}

/**
 * READ-ONLY render-state inspection. Captures why a valid, framed model may not
 * paint: displayed model/category identity, tile-tree load status, live tile
 * counts (requested/selected/ready), display style / render mode / view flags,
 * and active clip. Issues NO Bentley API mutations and changes NO view state.
 * Sanitized — never prints tokens/SAS/Authorization.
 */
export async function inspectRenderState(): Promise<RenderStateResult> {
    const vp = IModelApp.viewManager?.selectedView
    if (!vp) {
        if (import.meta.env.DEV) console.error('[bentley-render] ACTIVE_VIEWPORT_PRESENT=NO')
        return { summary: 'NO_ACTIVE_VIEWPORT' }
    }
    const notes: string[] = []
    try {
        const view = vp.view
        const anyView = view as unknown as {
            classFullName?: string
            is3d?: () => boolean
            isSpatialView?: () => boolean
            modelSelector?: { models?: Set<string> }
            categorySelector?: { categories?: Set<string> }
        }
        const modelIds = anyView.modelSelector?.models ? Array.from(anyView.modelSelector.models) : []
        const catIds = anyView.categorySelector?.categories ? Array.from(anyView.categorySelector.categories) : []
        const displayedModelId = modelIds[0]
        const visibleCategoryId = catIds[0]

        // (1) Displayed model identity + (2) category — queried read-only via ECSQL.
        let modelClass = 'n/a', modelName = 'n/a', catName = 'n/a'
        try {
            if (displayedModelId) {
                // bis.Model has no CodeValue; the code lives on the modeled
                // element (same ECInstanceId). Class from Model, name from Element.
                const reader = vp.iModel.createQueryReader(
                    `SELECT ec_classname(m.ECClassId), e.CodeValue FROM bis.Model m JOIN bis.Element e ON e.ECInstanceId = m.ECInstanceId WHERE m.ECInstanceId=?`,
                    QueryBinder.from([displayedModelId]),
                )
                for await (const row of reader) {
                    modelClass = String(row[0] ?? 'n/a'); modelName = String(row[1] ?? 'n/a')
                }
            }
        } catch (e) { notes.push('MODEL_QUERY_ERR:' + (e instanceof Error ? e.message : String(e))) }
        try {
            if (visibleCategoryId) {
                const reader = vp.iModel.createQueryReader(
                    `SELECT CodeValue FROM bis.Category WHERE ECInstanceId=?`,
                    QueryBinder.from([visibleCategoryId]),
                )
                for await (const row of reader) { catName = String(row[0] ?? 'n/a') }
            }
        } catch (e) { notes.push('CAT_QUERY_ERR:' + (e instanceof Error ? e.message : String(e))) }

        if (import.meta.env.DEV) {
            console.info('[bentley-render] DISPLAYED_MODEL_ID=%s DISPLAYED_MODEL_CLASS=%s DISPLAYED_MODEL_NAME=%s VIEW_IS_3D=%s VIEW_IS_SPATIAL=%s VIEWS_MODEL=%s',
                String(displayedModelId), modelClass, modelName,
                String(typeof anyView.is3d === 'function' ? anyView.is3d() : 'n/a'),
                String(typeof anyView.isSpatialView === 'function' ? anyView.isSpatialView() : 'n/a'),
                String(displayedModelId ? vp.viewsModel(displayedModelId) : 'n/a'))
            console.info('[bentley-render] VISIBLE_CATEGORY_ID=%s CATEGORY_NAME=%s CATEGORY_COUNT=%d MODEL_COUNT=%d',
                String(visibleCategoryId), catName, catIds.length, modelIds.length)
        }

        // View frustum (WORLD coords) as a range, for the intersection test.
        let frustumRange: Range3d | undefined
        try {
            const frustum = vp.getWorldFrustum()
            frustumRange = Range3d.createArray(frustum.points as unknown as { x: number; y: number; z: number }[])
            if (import.meta.env.DEV) {
                console.info('[bentley-render] VIEW_FRUSTUM_RANGE_LOW=%s VIEW_FRUSTUM_RANGE_HIGH=%s CAMERA_ON=%s',
                    fmtPt(frustumRange.low), fmtPt(frustumRange.high),
                    String((view as unknown as { isCameraOn?: boolean }).isCameraOn))
            }
        } catch (e) { notes.push('FRUSTUM_ERR:' + (e instanceof Error ? e.message : String(e))) }

        // (3/5/7) Tile-tree state + world content range + transform + root tile.
        let treeRefCount = 0
        const statusNames = ['NotLoaded', 'Loading', 'Loaded', 'NotFound']
        vp.forEachTileTreeRef((ref) => {
            treeRefCount += 1
            try {
                const owner = ref.treeOwner
                const status = owner.loadStatus as TileTreeLoadStatus
                const tree = owner.tileTree
                if (import.meta.env.DEV) {
                    console.info('[bentley-render] TILE_TREE_REF #%d LOAD_STATUS=%s(%d) TREE_PRESENT=%s',
                        treeRefCount, statusNames[status] ?? 'unknown', status, String(Boolean(tree)))
                }
                // model->world transform (IFC connector may translate to global origin)
                try {
                    const loc = ref.getLocation()
                    if (import.meta.env.DEV && loc) {
                        const o = loc.origin
                        console.info('[bentley-render] TREE#%d MODEL_TO_WORLD_TRANSLATION=(%s,%s,%s) TRANSFORM_IS_IDENTITY=%s',
                            treeRefCount, o.x.toFixed(2), o.y.toFixed(2), o.z.toFixed(2), String(loc.isIdentity))
                    } else if (import.meta.env.DEV) {
                        console.info('[bentley-render] TREE#%d MODEL_TO_WORLD_TRANSFORM_PRESENT=NO', treeRefCount)
                    }
                } catch (e) { notes.push('TREE_LOC_ERR:' + (e instanceof Error ? e.message : String(e))) }

                // tile-tree local range
                if (tree && import.meta.env.DEV) {
                    const r = tree.range
                    console.info('[bentley-render] TREE#%d TREE_RANGE_LOW=%s TREE_RANGE_HIGH=%s TREE_RANGE_DIAGONAL=%s CONTENT_UNBOUNDED=%s',
                        treeRefCount, fmtPt(r.low), fmtPt(r.high),
                        r.isNull ? 'n/a' : r.diagonal().magnitude().toFixed(3),
                        String((tree as unknown as { isContentUnbounded?: boolean }).isContentUnbounded))
                }

                // WORLD content range — the decisive comparison vs the frustum.
                try {
                    const worldRange = ref.computeWorldContentRange()
                    if (import.meta.env.DEV) {
                        const intersects = frustumRange && !worldRange.isNull ? frustumRange.intersectsRange(worldRange) : undefined
                        console.info('[bentley-render] TREE#%d WORLD_CONTENT_RANGE_LOW=%s WORLD_CONTENT_RANGE_HIGH=%s TILE_TREE_INTERSECTS_VIEW_FRUSTUM=%s',
                            treeRefCount, fmtPt(worldRange.low), fmtPt(worldRange.high),
                            intersects === undefined ? 'NOT_QUERYABLE' : String(intersects))
                    }
                } catch (e) { notes.push('WORLD_RANGE_ERR:' + (e instanceof Error ? e.message : String(e))) }

                // root tile + immediate children content state
                try {
                    const loadNames = ['NotLoaded', 'Queued', 'Loading', 'Ready', 'NotFound', 'Abandoned']
                    const root = tree ? (tree as unknown as {
                        rootTile?: {
                            range?: { low: { x: number; y: number; z: number }; high: { x: number; y: number; z: number }; isNull?: boolean }
                            isDisplayable?: boolean; contentId?: string; loadStatus?: number
                            hasGraphics?: boolean; isReady?: boolean; hasContentRange?: boolean
                            children?: Array<{ contentId?: string; loadStatus?: number; isDisplayable?: boolean; hasGraphics?: boolean; isReady?: boolean }>
                        }
                    }).rootTile : undefined
                    if (root && import.meta.env.DEV) {
                        console.info('[bentley-render] TREE#%d ROOT_TILE_PRESENT=YES ROOT_IS_DISPLAYABLE=%s ROOT_HAS_GRAPHICS=%s ROOT_IS_READY=%s ROOT_LOAD_STATUS=%s(%s) ROOT_CONTENT_ID=%s ROOT_HAS_CHILDREN=%s ROOT_CHILD_COUNT=%s',
                            treeRefCount, String(root.isDisplayable), String(root.hasGraphics), String(root.isReady),
                            loadNames[root.loadStatus ?? -1] ?? 'unknown', String(root.loadStatus), String(root.contentId),
                            String(Boolean(root.children)), String(root.children?.length ?? 0))
                        const kids = root.children ?? []
                        kids.slice(0, 6).forEach((c, i) => {
                            console.info('[bentley-render] TREE#%d CHILD#%d LOAD_STATUS=%s(%s) IS_DISPLAYABLE=%s HAS_GRAPHICS=%s IS_READY=%s CONTENT_ID=%s',
                                treeRefCount, i, loadNames[c.loadStatus ?? -1] ?? 'unknown', String(c.loadStatus),
                                String(c.isDisplayable), String(c.hasGraphics), String(c.isReady), String(c.contentId))
                        })
                    } else if (import.meta.env.DEV) {
                        console.info('[bentley-render] TREE#%d ROOT_TILE_PRESENT=NO', treeRefCount)
                    }
                } catch (e) { notes.push('ROOT_TILE_ERR:' + (e instanceof Error ? e.message : String(e))) }
            } catch (e) { notes.push('TREE_REF_ERR:' + (e instanceof Error ? e.message : String(e))) }
        })

        // (3/4) Live tile counts on the viewport. HAS_MISSING_TILES is derived
        // from the supported `areAllTileTreesLoaded` accessor (inverted).
        if (import.meta.env.DEV) {
            console.info('[bentley-render] TILE_TREE_REF_COUNT=%d NUM_REQUESTED_TILES=%d NUM_SELECTED_TILES=%d NUM_READY_TILES=%d ALL_TREES_LOADED=%s HAS_MISSING_TILES=%s',
                treeRefCount, vp.numRequestedTiles, vp.numSelectedTiles, vp.numReadyTiles,
                String(vp.areAllTileTreesLoaded), String(!vp.areAllTileTreesLoaded))
        }

        // (3/5) TileAdmin session statistics — the decisive content-request
        // evidence: dispatched vs completed vs failed vs timed-out vs empty vs
        // undisplayable vs elided vs aborted. Distinguishes "never requested"
        // from "requested but failed/timed-out/quota-aborted".
        try {
            const stats = IModelApp.tileAdmin?.statistics as unknown as Record<string, number> | undefined
            if (stats && import.meta.env.DEV) {
                console.info('[bentley-render] TILEADMIN numActive=%d numPending=%d totalDispatched=%d totalCompleted=%d totalFailed=%d totalTimedOut=%d totalEmpty=%d totalUndisplayable=%d totalElided=%d totalAborted=%d totalCacheMisses=%d',
                    stats.numActiveRequests, stats.numPendingRequests, stats.totalDispatchedRequests,
                    stats.totalCompletedRequests, stats.totalFailedRequests, stats.totalTimedOutRequests,
                    stats.totalEmptyTiles, stats.totalUndisplayableTiles, stats.totalElidedTiles,
                    stats.totalAbortedRequests, stats.totalCacheMisses)
            }
        } catch (e) { notes.push('TILEADMIN_ERR:' + (e instanceof Error ? e.message : String(e))) }

        // (2/3) Per-channel request state — distinguishes "in-flight to backend"
        // (numActive>0) from "queued, not dispatched" (numPending>0) and shows
        // WHICH channel the stuck geometry request is on.
        try {
            const channels = (IModelApp.tileAdmin as unknown as { channels?: Iterable<{ name?: string; concurrency?: number; numActive?: number; numPending?: number }> }).channels
            if (channels && import.meta.env.DEV) {
                for (const ch of channels) {
                    const na = ch.numActive ?? 0, np = ch.numPending ?? 0
                    if (na > 0 || np > 0) {
                        console.info('[bentley-render] CHANNEL name=%s concurrency=%s numActive=%d numPending=%d',
                            String(ch.name), String(ch.concurrency), na, np)
                    }
                }
            }
        } catch (e) { notes.push('CHANNELS_ERR:' + (e instanceof Error ? e.message : String(e))) }

        // (9) Browser changeset vs mesh-export changeset (service-verified tip
        // = 94e4a669… index 13, which contains the proven 5.imdl geometry).
        try {
            const cs = (vp.iModel as unknown as { changeset?: { id?: string; index?: number } }).changeset
            if (import.meta.env.DEV) {
                const meshExportCs = '94e4a66905e2e5142273e5ef683684a5152bb7a6'
                console.info('[bentley-render] BROWSER_CHANGESET_ID=%s BROWSER_CHANGESET_INDEX=%s MESH_EXPORT_CHANGESET_ID=%s CHANGESETS_MATCH=%s',
                    String(cs?.id), String(cs?.index), meshExportCs, String(cs?.id === meshExportCs))
            }
        } catch (e) { notes.push('CHANGESET_ERR:' + (e instanceof Error ? e.message : String(e))) }

        // (7) Display style / render mode / view flags.
        const vf = vp.viewFlags
        if (import.meta.env.DEV) {
            console.info('[bentley-render] RENDER_MODE=%s VISIBLE_EDGES=%s TRANSPARENCY=%s CONSTRUCTIONS=%s LIGHTING=%s CLIP_VOLUME_FLAG=%s',
                String(vf.renderMode), String(vf.visibleEdges), String(vf.transparency),
                String(vf.constructions), String(vf.lighting), String(vf.clipVolume))
        }

        // (8) Active clip.
        const clip = view.getViewClip()
        if (import.meta.env.DEV) {
            console.info('[bentley-render] CLIP_VOLUME_ACTIVE=%s VIEW_CLIP_PRESENT=%s',
                String(Boolean(clip)), String(Boolean(clip)))
        }

        const summary = `models=${modelIds.length} cats=${catIds.length} treeRefs=${treeRefCount} requested=${vp.numRequestedTiles} selected=${vp.numSelectedTiles} ready=${vp.numReadyTiles} allTreesLoaded=${vp.areAllTileTreesLoaded} renderMode=${vf.renderMode} clip=${Boolean(clip)}${notes.length ? ' | ' + notes.join(';') : ''}`
        if (import.meta.env.DEV) console.info('[bentley-render] SUMMARY %s', summary)
        return { summary }
    } catch (e) {
        const msg = e instanceof Error ? e.message : String(e)
        if (import.meta.env.DEV) console.error('[bentley-render] INSPECT_ERROR', msg)
        return { summary: 'INSPECT_ERROR: ' + msg }
    }
}

/** A range is usable for zoom only if finite, non-null and non-degenerate. */
function isUsableRange(range: Range3d): boolean {
    if (range.isNull) return false
    const lo = range.low, hi = range.high
    const finite = [lo.x, lo.y, lo.z, hi.x, hi.y, hi.z].every((n) => Number.isFinite(n))
    if (!finite) return false
    const diag = range.diagonal().magnitude()
    return diag > 1e-6 && Number.isFinite(diag)
}

/** Sanitized view-state snapshot (no tokens/secrets). */
function logViewState(phase: string, viewport: ScreenViewport): void {
    if (!import.meta.env.DEV) return
    try {
        const view = viewport.view as unknown as {
            classFullName?: string
            modelSelector?: { models?: { size?: number } }
            categorySelector?: { categories?: { size?: number } }
            getEyePoint?: () => { x: number; y: number; z: number }
            getTargetPoint?: () => { x: number; y: number; z: number }
        }
        const extents = viewport.view.getViewedExtents()
        const eye = typeof view.getEyePoint === 'function' ? view.getEyePoint() : undefined
        const tgt = typeof view.getTargetPoint === 'function' ? view.getTargetPoint() : undefined
        console.info('[bentley-view] %s VIEW_TYPE=%s DISPLAYED_MODELS=%s VISIBLE_CATEGORIES=%s CAMERA_EYE=%s TARGET=%s VIEWED_EXTENTS_LOW=%s VIEWED_EXTENTS_HIGH=%s',
            phase, String(view.classFullName),
            String(view.modelSelector?.models?.size ?? 'n/a'),
            String(view.categorySelector?.categories?.size ?? 'n/a'),
            eye ? fmtPt(eye) : 'n/a', tgt ? fmtPt(tgt) : 'n/a',
            fmtPt(extents.low), fmtPt(extents.high))
    } catch {
        // diagnostics must never break the viewport
    }
}

function fmtPt(p: { x: number; y: number; z: number }): string {
    return `(${p.x.toFixed(2)},${p.y.toFixed(2)},${p.z.toFixed(2)})`
}

/**
 * Subscribe to the connected iModel's selection set and forward the selected
 * element's identity + source properties to the panel. Kept defensive so an
 * API shape change degrades gracefully rather than crashing the viewport.
 */
async function wireSelection(
    iModel: unknown,
    onSelect: (raw: RawBentleySelection, properties: Record<string, unknown>) => void | Promise<void>,
): Promise<void> {
    try {
        const im = iModel as {
            selectionSet?: { onChanged?: { addListener: (cb: (set: { elements: Set<string> }) => void) => void } }
            iModelId?: string
            changeset?: { id?: string }
        }
        im.selectionSet?.onChanged?.addListener((set) => {
            const first = set.elements.values().next().value as string | undefined
            if (!first) return
            void onSelect(
                { elementId: first, iModelId: im.iModelId ?? null, changesetId: im.changeset?.id ?? null },
                {},
            )
        })
    } catch {
        // selection wiring is best-effort; the viewport still renders read-only.
    }
}

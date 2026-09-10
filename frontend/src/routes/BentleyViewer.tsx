/**
 * /viewer — Basic Bentley 3D Viewer page.
 *
 * Renders the LIVE MRTway Hospital Campus Development iModel in the browser via
 * the isolated `<LiveItwinViewer>` wrapper (lazy-loaded so unit tests never
 * import the heavy @itwin viewer stack). Left/center = 3D viewport; right =
 * inspection panel (selected element identity + Bentley properties + MRT
 * binding). READ-ONLY; no building drag/drop (Sec 28), no live mutation (Sec 29).
 */
import { Suspense, lazy, useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { getViewerConfig, isViewerConfigured, ViewerConfigError, type ViewerConfig } from '../lib/viewerConfig'
import { authReducer, INITIAL_AUTH_STATE } from '../lib/viewerAuth'
import { resolveFloatingPanelAction, type FloatingPanelId, type FloatingPanelAction } from '../components/spatial/floatingPanels'
import {
    VIEWER_CAMERA_CAPABILITIES,
    BASIC_CLIPPING_CAPABILITY,
    resolveMrtBinding,
    toBentleySourceIdentity,
    toPropertyRows,
    type BentleySourceIdentity,
    type MrtBindingResult,
    type PropertyRow,
    type RawBentleySelection,
} from '../lib/viewerSelection'
import './BentleyViewer.css'

// Isolated heavy viewer: only loaded in the browser, never in vitest.
const LiveItwinViewer = lazy(() => import('../components/viewer/LiveItwinViewer'))
// Product Asset Library / placement UI (also isolated so vitest never imports
// the Bentley placement stack it pulls in through the overlay).
const ViewerAssetLibrary = lazy(() =>
    import('../components/spatial/ViewerAssetLibrary').then((m) => ({ default: m.ViewerAssetLibrary })),
)
// DEV-only Medical Clinic demo ingestion panel (isolated + lazy so tests / the
// non-viewer bundle never import the Bentley write workflow).
const ClinicIngestionPanel = lazy(() =>
    import('../components/spatial/ClinicIngestionPanel').then((m) => ({ default: m.ClinicIngestionPanel })),
)
// DEV-only BIM audit diagnostics in a dedicated, reliably hit-testable panel.
const AuditDiagnosticsPanel = lazy(() =>
    import('../components/spatial/AuditDiagnosticsPanel').then((m) => ({ default: m.AuditDiagnosticsPanel })),
)
// NORMAL-MODE project BIM selector (active BIM + switch). Not dev-gated.
const ProjectBimSelector = lazy(() =>
    import('../components/spatial/ProjectBimSelector').then((m) => ({ default: m.ProjectBimSelector })),
)
// NORMAL-MODE camera/view mode control (Planning / Walkthrough / Bird's-eye).
const CameraModeControl = lazy(() =>
    import('../components/spatial/CameraModeControl').then((m) => ({ default: m.CameraModeControl })),
)
// NORMAL-MODE MRT Pharma clinical-program overlay panel (room repurposing).
const ClinicalProgramControl = lazy(() =>
    import('../components/spatial/ClinicalProgramControl').then((m) => ({ default: m.ClinicalProgramControl })),
)
// Right-click asset context menu (viewport overlay). Isolated/lazy so vitest
// never pulls the Bentley overlay stack.
const ViewerAssetContextMenu = lazy(() =>
    import('../components/spatial/ViewerAssetContextMenu').then((m) => ({ default: m.ViewerAssetContextMenu })),
)
// Marquee (bounding-box) selection overlay. Lazy + outside the viewer Suspense.
const ViewerMarqueeOverlay = lazy(() =>
    import('../components/spatial/ViewerMarqueeOverlay').then((m) => ({ default: m.ViewerMarqueeOverlay })),
)

interface Selection {
    identity: BentleySourceIdentity
    properties: PropertyRow[]
    binding: MrtBindingResult | null
}

export function BentleyViewer() {
    const [auth, dispatch] = useReducer(authReducer, INITIAL_AUTH_STATE)
    const [selection, setSelection] = useState<Selection | null>(null)
    const configured = isViewerConfigured()

    // Product viewer mode (PRESENTATION only). Default NORMAL_PLANNING: the DEV
    // control block + raw diagnostics stay OUT of the viewport. DEVELOPER mode is
    // opt-in and reveals the developer drawer. Pushed to the overlay so the lazy
    // product panels observe the same mode (hide the raw engineering dump etc.).
    const [devMode, setDevMode] = useState(false)
    const toggleDevMode = useCallback(() => {
        setDevMode((prev) => {
            const next = !prev
            void import('../components/spatial/spatialAssetOverlay')
                .then((m) => m.setViewerMode(next ? 'DEVELOPER' : 'NORMAL_PLANNING'))
                .catch(() => { /* overlay not yet loaded; panels default to normal */ })
            if (!next) setOpenPanel(null) // leaving dev mode closes dev tool panels
            return next
        })
    }, [])

    // FLOATING TOOL-PANEL lifecycle: at most one major dev tool panel open at a
    // time. VISIBILITY only — never mutates feature state (active BIM, camera
    // mode, Clinical Program ON/OFF, assignments). Uses the pure lifecycle seam.
    const [openPanel, setOpenPanel] = useState<FloatingPanelId | null>(null)
    const dispatchPanel = useCallback((action: FloatingPanelAction, targetPanel?: FloatingPanelId) => {
        setOpenPanel((cur) => resolveFloatingPanelAction({ currentlyOpenPanel: cur, action, targetPanel }).nextOpenPanel)
    }, [])
    // Esc closes the open tool panel (does not exit Bird's-eye / turn off features).
    useEffect(() => {
        if (!openPanel) return
        const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') dispatchPanel('ESCAPE') }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [openPanel, dispatchPanel])

    // Reversible, view-only planning appearance (opaque architecture + hide the
    // room/space VOLUME semantics that otherwise dominate as translucent boxes).
    // DEFAULT ON — applied only AFTER the viewer is ready (never at view-open),
    // so it cannot blank the viewport on load. Toggleable in normal mode.
    const [planningAppearance, setPlanningAppearanceState] = useState(true)
    const applyPlanningAppearance = useCallback((next: boolean) => {
        void import('../components/viewer/LiveItwinViewer')
            .then((m) => m.setPlanningAppearance(next))
            .catch(() => { /* viewer not ready */ })
    }, [])
    const togglePlanningAppearance = useCallback(() => {
        setPlanningAppearanceState((prev) => {
            const next = !prev
            applyPlanningAppearance(next)
            return next
        })
    }, [applyPlanningAppearance])

    // Auto-apply the DEFAULT-ON planning appearance ONCE the viewer is ready.
    // Gated on AUTHENTICATED (viewer only mounts then) and guarded by a ref so
    // it runs a single logical time. setPlanningAppearance returns
    // NO_ACTIVE_VIEWPORT gracefully until the viewport exists, so we retry on a
    // short bounded schedule and stop as soon as it succeeds. This is the SAFE
    // post-ready application point (never onViewOpen), so it cannot blank the
    // viewport on load. View-only; emits no engineering events.
    const planningAutoAppliedRef = useRef(false)
    useEffect(() => {
        if (auth.state !== 'AUTHENTICATED') return
        if (planningAutoAppliedRef.current) return
        if (!planningAppearance) return
        let cancelled = false
        let attempts = 0
        const maxAttempts = 20 // ~ 20 * 500ms = 10s bounded
        const tryApply = () => {
            if (cancelled || planningAutoAppliedRef.current) return
            attempts += 1
            void import('../components/viewer/LiveItwinViewer')
                .then((m) => m.setPlanningAppearance(true))
                .then((res) => {
                    if (cancelled) return
                    if (res && res.ok) {
                        planningAutoAppliedRef.current = true
                    } else if (attempts < maxAttempts) {
                        window.setTimeout(tryApply, 500)
                    }
                })
                .catch(() => {
                    if (!cancelled && attempts < maxAttempts) window.setTimeout(tryApply, 500)
                })
        }
        const t = window.setTimeout(tryApply, 500)
        return () => { cancelled = true; window.clearTimeout(t) }
    }, [auth.state, planningAppearance])

    // STABLE identity: handleSelect is passed to <LiveItwinViewer>. If it were
    // recreated every render it would (via the child's effects) contribute to
    // the remount/request loop. setSelection is a stable setter, so [] deps.
    const handleSelect = useCallback(
        async (raw: RawBentleySelection, properties: Record<string, unknown>) => {
            const identity = toBentleySourceIdentity(raw)
            const binding = await resolveMrtBinding(raw)
            setSelection({ identity, properties: toPropertyRows(properties), binding })
        },
        [],
    )

    // STABLE identity: getViewerConfig() returns a NEW object each call. Passing
    // a fresh config to <LiveItwinViewer> every render was recreating the auth
    // client and re-running the auth effect on a loop (the proven cause of the
    // unbounded signInSilent / namedversions / changesets requests). Memoize it
    // so its identity is stable for the session (env is fixed at load time).
    const { config, configError } = useMemo<{ config: ViewerConfig | undefined; configError: string | null }>(() => {
        if (!configured) return { config: undefined, configError: null }
        try {
            return { config: getViewerConfig(), configError: null }
        } catch (e) {
            return { config: undefined, configError: e instanceof ViewerConfigError ? e.message : String(e) }
        }
    }, [configured])

    // STABLE identities for the auth callbacks passed to <LiveItwinViewer>.
    // dispatch is stable, so [] deps. Inline arrows here would change identity
    // every render and re-trigger the child's auth effect.
    const handleAuthSuccess = useCallback(() => dispatch({ type: 'AUTH_SUCCEEDED' }), [])
    const handleAuthError = useCallback((m: string) => dispatch({ type: 'AUTH_FAILED', message: m }), [])

    // Diagnostic control: invoke ONE bounded native fit against the live
    // viewport. Dynamically imports the viewer module so unit tests / the
    // non-viewer bundle never pull in @itwin. Never loops or mutates the iModel.
    const [fitNote, setFitNote] = useState<string | null>(null)

    // Developer Inspector panel (UI-only, non-authoritative). Verbose DEV
    // diagnostics render HERE — in the right-side inspection area — instead of
    // being painted over the 3D viewport. State is bounded: a title, the current
    // content, and open/closed. It never mutates SpatialAssetStore, the BIM, or
    // viewer state; CLEAR empties content, CLOSE hides the panel.
    const [devInspector, setDevInspector] = useState<{ open: boolean; title: string; content: string }>(
        { open: false, title: '', content: '' },
    )
    const showDev = useCallback((title: string, content: string) => {
        setDevInspector({ open: true, title, content })
    }, [])
    const clearDev = useCallback(() => setDevInspector((s) => ({ ...s, content: '' })), [])
    const closeDev = useCallback(() => setDevInspector((s) => ({ ...s, open: false })), [])
    const handleFitLiveModel = useCallback(async () => {
        try {
            const mod = await import('../components/viewer/LiveItwinViewer')
            const r = mod.fitLiveModel()
            setFitNote(r.ok
                ? `Fit executed (models=${r.modelSelectorSize}, categories=${r.categorySelectorSize}, diagonal=${r.diagonal?.toFixed(1) ?? '—'}m)`
                : `Fit not performed: ${r.reason} (models=${r.modelSelectorSize}, categories=${r.categorySelectorSize})`)
        } catch (e) {
            setFitNote(`Fit error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [])

    // Diagnostic: capture render/tile state (read-only). Runs once now and once
    // ~1.5s later to catch tile activity after a render tick. No mutation.
    // MRT Pharma 3D asset architecture proof: show / hide / inspect the ONE
    // generic PET/CT test asset as a Bentley world-decoration overlay. Dynamic
    // import keeps the spatial/Bentley code out of the offline test bundle.
    const handleShowGenericPetCt = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            const r = mod.showGenericPetCt()
            setFitNote(r.ok ? `Generic PET/CT shown: ${r.instanceId}` : `Show failed: ${r.reason}`)
        } catch (e) {
            setFitNote(`Asset show error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [])
    const handleHideGenericPetCt = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            mod.hideGenericPetCt()
            setFitNote('Generic PET/CT hidden')
        } catch (e) {
            setFitNote(`Asset hide error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [])
    const handleInspectGenericPetCt = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            showDev('Generic PET/CT', mod.inspectGenericPetCt())
        } catch (e) {
            showDev('Generic PET/CT', `error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [showDev])

    // Catalog-backed PET/CT (real GE Discovery MI identity, generic geometry).
    const handleShowCatalogPetCt = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            const r = mod.showCatalogPetCt()
            setFitNote(r.ok ? `Catalog PET/CT shown: ${r.instanceId}` : `Show failed: ${r.reason}`)
        } catch (e) {
            setFitNote(`Catalog show error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [])
    const handleHideCatalogPetCt = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            mod.hideCatalogPetCt()
            setFitNote('Catalog PET/CT hidden')
        } catch (e) {
            setFitNote(`Catalog hide error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [])
    const handleInspectCatalogPetCt = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            showDev('Catalog PET/CT', mod.inspectCatalogPetCt())
        } catch (e) {
            showDev('Catalog PET/CT', `error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [showDev])

    // DEV diagnostic: bounded snapshot of the active placement intent (creates
    // no AssetInstance).
    const handleInspectPlacementIntent = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            showDev('Placement Intent', mod.inspectPlacementIntent())
        } catch (e) {
            showDev('Placement Intent', `error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [showDev])

    // DEV diagnostic: read-only snapshot of the direct-drag interaction state
    // (active tool id, selection, interaction, committed/preview/effective).
    const handleInspectDirectDragState = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            showDev('Direct Drag', mod.inspectDirectDragState())
        } catch (e) {
            showDev('Direct Drag', `error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [showDev])

    // DEV diagnostic: read-only snapshot of the object-attached rotation state.
    const handleInspectRotationState = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            showDev('Rotation', mod.inspectRotationState())
        } catch (e) {
            showDev('Rotation', `error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [showDev])

    // DEV diagnostic: read-only bounded inventory of the live BIM's spatial
    // structure (candidate floor/room classes + counts + geometry availability).
    const handleInspectBimSpatialStructure = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            showDev('BIM Spatial Structure', await mod.inspectBimSpatialStructure())
        } catch (e) {
            showDev('BIM Spatial Structure', `error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [showDev])

    // NOTE: RUN BIM CONTENT AUDIT and PROBE BENTLEY CLOUD PERMISSIONS moved into
    // the dedicated AuditDiagnosticsPanel (own hit-testable drawer) — they were
    // unreliable buried at the bottom of the crowded, clipped .viewer-dev-drawer.

    // DEV diagnostic: read-only floor/room association of the selected asset.
    const handleInspectSpatialAssociation = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            showDev('Spatial Association', await mod.inspectSpatialAssociation())
        } catch (e) {
            showDev('Spatial Association', `error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [showDev])

    // NOTE: DIAGNOSE CLINICAL PROGRAM OVERLAY moved into the dedicated
    // AuditDiagnosticsPanel (own reliably hit-testable drawer) — it was invisible
    // buried at the bottom of the crowded, clipped .viewer-dev-drawer.

    const handleInspectFeatureAppearance = useCallback(async () => {
        try {
            const mod = await import('../components/viewer/LiveItwinViewer')
            const r = await mod.inspectFeatureAppearance()
            showDev('Feature Appearance', r.summary)
        } catch (e) {
            showDev('Feature Appearance', `error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [showDev])

    const handleInspectRenderState = useCallback(async () => {
        try {
            const mod = await import('../components/viewer/LiveItwinViewer')
            // Start the bounded onTileLoad watcher (8s / 20 events, auto-removes)
            // BEFORE inspecting, so we catch any transition of the stuck child.
            mod.watchTileLoads()
            const first = await mod.inspectRenderState()
            // Bounded tile-selection series: t=0 (now) + t=1s/3s/5s, accumulated
            // into the Developer Inspector panel (not painted over the viewport).
            const lines = [`Render state: ${first.summary}`, mod.readTileCounts('t=0')]
            showDev('Render State', lines.join('\n'))
            const append = (s: string) => { lines.push(s); showDev('Render State', lines.join('\n')) }
            window.setTimeout(() => append(mod.readTileCounts('t=1s')), 1000)
            window.setTimeout(() => append(mod.readTileCounts('t=3s')), 3000)
            window.setTimeout(() => append(mod.readTileCounts('t=5s')), 5000)
        } catch (e) {
            showDev('Render State', `error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [showDev])

    return (
        <main className="viewer-page">
            <section className="viewer-stage" aria-label="Bentley 3D viewport">
                {!configured || configError ? (
                    <div className="viewer-cta">
                        <h1>MRTway Development Viewer</h1>
                        <p>{configError ?? 'Bentley viewer configuration is not set.'}</p>
                        <button type="button" disabled aria-disabled="true">
                            Sign in with Bentley (configure client id first)
                        </button>
                    </div>
                ) : auth.state === 'NOT_AUTHENTICATED' ? (
                    <div className="viewer-cta">
                        <h1>MRTway Development Viewer</h1>
                        <p>Sign in to view the live MRTway Hospital Campus Development model.</p>
                        <button type="button" onClick={() => dispatch({ type: 'SIGN_IN_REQUESTED' })}>
                            Sign in with Bentley
                        </button>
                    </div>
                ) : auth.state === 'AUTH_ERROR' ? (
                    <div className="viewer-cta" role="alert">
                        <h1>Authentication error</h1>
                        <p>{auth.errorMessage}</p>
                        <button type="button" onClick={() => dispatch({ type: 'SIGN_IN_REQUESTED' })}>Try again</button>
                    </div>
                ) : (
                    <Suspense fallback={<div className="viewer-loading">Loading 3D viewport…</div>}>
                        {config && (
                            <LiveItwinViewer
                                config={config}
                                onSelect={handleSelect}
                                onAuthSuccess={handleAuthSuccess}
                                onAuthError={handleAuthError}
                            />
                        )}
                        {/* Compact planning control bar (always present, top-right,
                            does not cover the model). Mode toggle + view-only
                            planning appearance. */}
                        <div className="viewer-mode-bar">
                            <button
                                type="button"
                                className={devMode ? 'viewer-mode-btn active' : 'viewer-mode-btn'}
                                aria-pressed={devMode}
                                onClick={toggleDevMode}
                                title="Toggle developer tools"
                            >
                                {devMode ? 'Developer mode: ON' : 'Developer'}
                            </button>
                            <button
                                type="button"
                                className={planningAppearance ? 'viewer-mode-btn active' : 'viewer-mode-btn'}
                                aria-pressed={planningAppearance}
                                onClick={togglePlanningAppearance}
                                title="Solid architectural surfaces for planning legibility"
                            >
                                {planningAppearance ? 'Planning view: solid' : 'Planning view'}
                            </button>
                        </div>

                        {/* NORMAL-MODE project BIM selector (active BIM + switch).
                            Always available (not dev-gated); its own top-left panel. */}
                        <div className="viewer-projectbim-bar">
                            <Suspense fallback={null}>
                                <ProjectBimSelector />
                            </Suspense>
                        </div>

                        {/* NORMAL-MODE VIEW / camera-mode control (Planning /
                            Walkthrough / Bird's-eye). Own top-left panel, below
                            the Asset Library area's top; never dev-gated. */}
                        <div className="viewer-camera-bar">
                            <Suspense fallback={null}>
                                <CameraModeControl />
                            </Suspense>
                        </div>

                        {/* NORMAL-MODE MRT Pharma CLINICAL PROGRAM overlay +
                            room repurposing. Own right-side panel below the VIEW
                            control; never dev-gated (dev only reveals ids). */}
                        <div className="viewer-program-bar">
                            <Suspense fallback={null}>
                                <ClinicalProgramControl iModelId={config?.iModelId} devMode={devMode} />
                            </Suspense>
                        </div>

                        {/* DEVELOPER MODE: compact toolbar toggles the tool panels.
                            Developer mode ON no longer means every panel is open. */}
                        {devMode && (
                            <div className="viewer-devbar" aria-label="Developer panels">
                                <span className="viewer-dev-label">DEV</span>
                                <button type="button" className={openPanel === 'DEV_TOOLS' ? 'active' : ''} aria-pressed={openPanel === 'DEV_TOOLS'} onClick={() => dispatchPanel('TOGGLE', 'DEV_TOOLS')}>Tools</button>
                                <button type="button" className={openPanel === 'AUDIT_DIAGNOSTICS' ? 'active' : ''} aria-pressed={openPanel === 'AUDIT_DIAGNOSTICS'} onClick={() => dispatchPanel('TOGGLE', 'AUDIT_DIAGNOSTICS')}>Diagnostics</button>
                                <button type="button" className={openPanel === 'INGESTION' ? 'active' : ''} aria-pressed={openPanel === 'INGESTION'} onClick={() => dispatchPanel('TOGGLE', 'INGESTION')}>Ingestion</button>
                            </div>
                        )}

                        {/* Outside-click backdrop: closes the open tool panel. Only
                            mounted while a panel is open; transparent; below panels. */}
                        {openPanel && (
                            <div className="viewer-panel-backdrop" aria-hidden="true" onPointerDown={() => dispatchPanel('OUTSIDE_CLICK')} />
                        )}

                        {/* DEVELOPER MODE ONLY: the diagnostics block lives in a
                            dedicated right-side drawer, never over the model center. */}
                        {devMode && openPanel === 'DEV_TOOLS' && (
                            <div className="viewer-dev-drawer" aria-label="Developer tools" onPointerDown={(e) => e.stopPropagation()}>
                                <div className="viewer-panel-head"><span className="viewer-dev-label">DEVELOPER</span><button type="button" className="viewer-panel-close" aria-label="Close" onClick={() => dispatchPanel('CLOSE', 'DEV_TOOLS')}>×</button></div>
                                <button type="button" onClick={() => void handleFitLiveModel()}>FIT LIVE MODEL</button>
                                <button type="button" onClick={() => void handleInspectRenderState()}>INSPECT RENDER STATE</button>
                                <button type="button" onClick={() => void handleInspectFeatureAppearance()}>INSPECT FEATURE APPEARANCE</button>
                                <button type="button" onClick={() => void handleShowGenericPetCt()}>SHOW GENERIC PET/CT</button>
                                <button type="button" onClick={() => void handleHideGenericPetCt()}>HIDE GENERIC PET/CT</button>
                                <button type="button" onClick={() => void handleInspectGenericPetCt()}>INSPECT GENERIC PET/CT</button>
                                <button type="button" onClick={() => void handleShowCatalogPetCt()}>SHOW CATALOG PET/CT</button>
                                <button type="button" onClick={() => void handleHideCatalogPetCt()}>HIDE CATALOG PET/CT</button>
                                <button type="button" onClick={() => void handleInspectCatalogPetCt()}>INSPECT CATALOG PET/CT</button>
                                <button type="button" onClick={() => void handleInspectPlacementIntent()}>INSPECT PLACEMENT INTENT</button>
                                <button type="button" onClick={() => void handleInspectDirectDragState()}>INSPECT DIRECT DRAG STATE</button>
                                <button type="button" onClick={() => void handleInspectRotationState()}>INSPECT ROTATION STATE</button>
                                <button type="button" onClick={() => void handleInspectBimSpatialStructure()}>INSPECT BIM SPATIAL STRUCTURE</button>
                                <button type="button" onClick={() => void handleInspectSpatialAssociation()}>INSPECT SPATIAL ASSOCIATION</button>
                                {fitNote && <span className="viewer-fit-note">{fitNote}</span>}
                            </div>
                        )}

                        {/* DEV-ONLY: Medical Clinic demo ingestion lives in its OWN
                            dedicated panel (bottom-left), NOT buried at the bottom of
                            the crowded, clipped diagnostics drawer where its controls
                            fell below the overflow fold and clicks missed. High
                            z-index + own scroll so pointer events always reach it. */}
                        {devMode && openPanel === 'INGESTION' && (
                            <div className="viewer-ingest-drawer" aria-label="Medical Clinic ingestion" onPointerDown={(e) => e.stopPropagation()}>
                                <div className="viewer-panel-head"><span className="viewer-dev-label">INGESTION</span><button type="button" className="viewer-panel-close" aria-label="Close" onClick={() => dispatchPanel('CLOSE', 'INGESTION')}>×</button></div>
                                <Suspense fallback={<span className="viewer-dev-label">Loading ingestion…</span>}>
                                    <ClinicIngestionPanel />
                                </Suspense>
                            </div>
                        )}

                        {/* DEV-ONLY: BIM audit diagnostics in its own dedicated,
                            reliably hit-testable panel (bottom-center-left), using
                            the same proven pattern as the ingestion drawer. */}
                        {devMode && openPanel === 'AUDIT_DIAGNOSTICS' && (
                            <div className="viewer-audit-drawer" aria-label="BIM audit diagnostics" onPointerDown={(e) => e.stopPropagation()}>
                                <div className="viewer-panel-head"><span className="viewer-dev-label">BIM AUDIT</span><button type="button" className="viewer-panel-close" aria-label="Close" onClick={() => dispatchPanel('CLOSE', 'AUDIT_DIAGNOSTICS')}>×</button></div>
                                <Suspense fallback={<span className="viewer-dev-label">Loading audit…</span>}>
                                    <AuditDiagnosticsPanel />
                                </Suspense>
                            </div>
                        )}

                        {/* PRODUCT: Asset Library + controlled placement + placed
                            assets. Additive; does not replace the DEV fixtures. */}
                        <div className="viewer-product-panel">
                            <Suspense fallback={<div className="mrt-lib-empty">Loading Asset Library…</div>}>
                                <ViewerAssetLibrary />
                            </Suspense>
                        </div>

                    </Suspense>
                )}
                {/* Right-click MRT asset context menu (viewport overlay). Rendered
                    OUTSIDE the viewer's Suspense boundary so its lazy chunk can
                    never suspend/unmount LiveItwinViewer and interrupt the Bentley
                    sign-in effect (regression: PLACE stalled at "Signing in…"). */}
                {config && auth.state === 'AUTHENTICATED' && (
                    <Suspense fallback={null}>
                        <ViewerAssetContextMenu />
                        <ViewerMarqueeOverlay />
                    </Suspense>
                )}
            </section>

            <aside className="viewer-inspector" aria-label="Inspection panel">
                {devMode && devInspector.open && (
                    <div className="dev-inspector" aria-label="Developer Inspector">
                        <div className="dev-inspector-head">
                            <strong>Developer Inspector</strong>
                            <span className="dev-inspector-title">{devInspector.title || '—'}</span>
                            <span className="dev-inspector-actions">
                                <button type="button" onClick={clearDev}>CLEAR</button>
                                <button type="button" onClick={closeDev}>CLOSE</button>
                            </span>
                        </div>
                        <pre className="dev-inspector-body">{devInspector.content || '(empty)'}</pre>
                    </div>
                )}
                <h2>Inspection</h2>
                {!selection ? (
                    <p className="inspector-empty">Select an element in the model to inspect it.</p>
                ) : (
                    <>
                        <h3>Bentley source identity</h3>
                        <dl className="inspector-identity">
                            <dt>Element ID</dt><dd>{selection.identity.elementId}</dd>
                            <dt>Class</dt><dd>{selection.identity.className ?? '—'}</dd>
                            <dt>Label</dt><dd>{selection.identity.label ?? '—'}</dd>
                            <dt>Category</dt><dd>{selection.identity.category ?? '—'}</dd>
                            <dt>Model</dt><dd>{selection.identity.modelId ?? '—'}</dd>
                            <dt>Changeset</dt><dd>{selection.identity.changesetId ?? '—'}</dd>
                        </dl>

                        <h3>Bentley properties</h3>
                        {selection.properties.length === 0 ? (
                            <p className="inspector-empty">No source properties returned for this element.</p>
                        ) : (
                            <table className="inspector-props">
                                <tbody>
                                    {selection.properties.map((p) => (
                                        <tr key={p.name}><th scope="row">{p.name}</th><td>{p.value}</td></tr>
                                    ))}
                                </tbody>
                            </table>
                        )}

                        <h3>MRT Pharma binding</h3>
                        {!selection.binding || !selection.binding.isBound ? (
                            <p className="inspector-unbound">
                                {selection.binding?.bindingStatus ?? 'UNBOUND'} — no MRT Pharma object bound to this element.
                            </p>
                        ) : (
                            <dl className="inspector-binding">
                                <dt>MRT object ID</dt><dd>{selection.binding.mrtObjectId}</dd>
                                <dt>MRT object type</dt><dd>{selection.binding.mrtObjectType ?? '—'}</dd>
                                <dt>Status</dt><dd>{selection.binding.bindingStatus}</dd>
                                <dt>Provenance</dt><dd>{selection.binding.sourceProvenance ?? '—'}</dd>
                            </dl>
                        )}
                    </>
                )}

                <h3>Camera</h3>
                <ul className="inspector-caps">
                    <li>Orbit: {VIEWER_CAMERA_CAPABILITIES.orbit ? 'available' : 'no'}</li>
                    <li>Pan: {VIEWER_CAMERA_CAPABILITIES.pan ? 'available' : 'no'}</li>
                    <li>Zoom: {VIEWER_CAMERA_CAPABILITIES.zoom ? 'available' : 'no'}</li>
                    <li>Fit view: {VIEWER_CAMERA_CAPABILITIES.fitView ? 'available' : 'no'}</li>
                    <li>Cutaway/clip: {BASIC_CLIPPING_CAPABILITY}</li>
                </ul>
            </aside>
        </main>
    )
}

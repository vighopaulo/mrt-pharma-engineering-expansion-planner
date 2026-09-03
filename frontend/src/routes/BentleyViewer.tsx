/**
 * /viewer — Basic Bentley 3D Viewer page.
 *
 * Renders the LIVE MRTway Hospital Campus Development iModel in the browser via
 * the isolated `<LiveItwinViewer>` wrapper (lazy-loaded so unit tests never
 * import the heavy @itwin viewer stack). Left/center = 3D viewport; right =
 * inspection panel (selected element identity + Bentley properties + MRT
 * binding). READ-ONLY; no building drag/drop (Sec 28), no live mutation (Sec 29).
 */
import { Suspense, lazy, useCallback, useMemo, useReducer, useState } from 'react'
import { getViewerConfig, isViewerConfigured, ViewerConfigError, type ViewerConfig } from '../lib/viewerConfig'
import { authReducer, INITIAL_AUTH_STATE } from '../lib/viewerAuth'
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

interface Selection {
    identity: BentleySourceIdentity
    properties: PropertyRow[]
    binding: MrtBindingResult | null
}

export function BentleyViewer() {
    const [auth, dispatch] = useReducer(authReducer, INITIAL_AUTH_STATE)
    const [selection, setSelection] = useState<Selection | null>(null)
    const configured = isViewerConfigured()

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

    // DEV diagnostic: read-only floor/room association of the selected asset.
    const handleInspectSpatialAssociation = useCallback(async () => {
        try {
            const mod = await import('../components/spatial/spatialAssetOverlay')
            showDev('Spatial Association', await mod.inspectSpatialAssociation())
        } catch (e) {
            showDev('Spatial Association', `error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [showDev])

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
                        {/* DEV diagnostics OUTSIDE the Bentley toolbars. Grouped
                            under a DEV label; separate from the PRODUCT UI. */}
                        <div className="viewer-fit-control">
                            <span className="viewer-dev-label">DEV</span>
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

                        {/* PRODUCT: Asset Library + controlled placement + placed
                            assets. Additive; does not replace the DEV fixtures. */}
                        <div className="viewer-product-panel">
                            <Suspense fallback={<div className="mrt-lib-empty">Loading Asset Library…</div>}>
                                <ViewerAssetLibrary />
                            </Suspense>
                        </div>
                    </Suspense>
                )}
            </section>

            <aside className="viewer-inspector" aria-label="Inspection panel">
                {devInspector.open && (
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

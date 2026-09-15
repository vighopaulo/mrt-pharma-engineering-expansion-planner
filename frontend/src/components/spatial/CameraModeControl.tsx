/**
 * CameraModeControl — NORMAL-MODE VIEW control: Planning / Walkthrough /
 * Bird's-eye, plus a storey selector in bird's-eye cutaway. View-only: switching
 * modes changes only the viewport camera + clip (no iModel write, no engineering
 * event, active BIM preserved).
 *
 * Mode ownership: entering WALKTHROUGH signals the app to disable asset
 * manipulation (camera owns input) via resolveCameraModePolicy; leaving it
 * restores planning input.
 */
import { useCallback, useEffect, useState } from 'react'
import { CAMERA_MODES, DEFAULT_CAMERA_MODE, resolveCameraModePolicy, type CameraMode } from './cameraNav'

const MODE_LABEL: Record<CameraMode, string> = {
    PLANNING: 'Planning',
    WALKTHROUGH: 'Walkthrough',
    BIRDS_EYE_CUTAWAY: "Bird's-eye",
}

interface Storey { id: string; label: string }

export function CameraModeControl() {
    const [mode, setMode] = useState<CameraMode>(DEFAULT_CAMERA_MODE)
    const [storeys, setStoreys] = useState<Storey[]>([])
    const [activeStoreyId, setActiveStoreyId] = useState<string | undefined>(undefined)
    const [pending, setPending] = useState(false)
    const [note, setNote] = useState('')
    const [fov, setFov] = useState<'NORMAL' | 'WIDE' | 'ULTRA_WIDE'>('NORMAL')
    // Build 1A walkthrough final UX: the controls/help pane is dismissible
    // (× / Esc / outside-click) and reopenable. Opens fresh each time walkthrough
    // is entered; never auto-reopens on camera movement.
    const [controlsHelpOpen, setControlsHelpOpen] = useState(true)
    // Build 1B Problem C: the ENTIRE walkthrough control card is dismissible, not
    // just the help subsection. Collapsing it clears the on-screen obstruction over
    // the 3D scene while keeping EXIT WALKTHROUGH reachable. Opens fresh on entry;
    // never auto-reopens on camera movement. (WALKTHROUGH_CONTROL_CARD_DISMISSIBLE)
    const [walkthroughCardOpen, setWalkthroughCardOpen] = useState(true)
    // Build 1B Problem B: dismissible PLANNING camera help (MacBook-friendly).
    const [planningHelpOpen, setPlanningHelpOpen] = useState(false)

    // Build 1B Problem B: controlled screen-space PAN in PLANNING mode. VIEW-ONLY;
    // preserves orbit/zoom/fit/cutaway. Step = fraction of the current view extent
    // (so it works after a deep zoom).
    const PAN_STEP = 0.18
    const pan = useCallback((right: number, up: number) => {
        void import('./spatialAssetOverlay').then((o) => o.panPlanningCamera(right * PAN_STEP, up * PAN_STEP))
    }, [])

    const applyMode = useCallback(async (next: CameraMode, storeyId?: string) => {
        if (pending) return
        setPending(true)
        setNote(next === 'WALKTHROUGH' ? 'Entering walkthrough… (W/S/A/D to walk, click + drag to look, two-finger scroll to dolly, Esc to release)' : next === 'BIRDS_EYE_CUTAWAY' ? 'Opening bird\u2019s-eye…' : 'Planning view')
        try {
            const overlay = await import('./spatialAssetOverlay')
            await overlay.applyCameraMode(next, { storeyId, fovPreset: next === 'WALKTHROUGH' ? fov : undefined })
            setMode(next)
            if (next === 'WALKTHROUGH') {
                setControlsHelpOpen(true) // fresh help on entry
                setWalkthroughCardOpen(true) // fresh full card on entry
            }
            setNote(next === 'WALKTHROUGH' ? 'Walkthrough active — Esc releases the pointer.' : 'Ready')
        } catch (e) {
            setNote(`camera mode error: ${e instanceof Error ? e.message : String(e)}`)
        } finally { setPending(false) }
    }, [pending, fov])

    // Load storeys (stories only) when entering bird's-eye or walkthrough.
    useEffect(() => {
        if (mode !== 'BIRDS_EYE_CUTAWAY' && mode !== 'WALKTHROUGH') return
        let cancelled = false
        void import('./spatialAssetOverlay').then(async (o) => {
            const list = await o.loadCameraStoreys()
            if (cancelled) return
            setStoreys(list.map((s) => ({ id: s.id, label: s.label })))
        })
        return () => { cancelled = true }
    }, [mode])

    // Build 1B Problem C: dismiss the WHOLE walkthrough control card via Esc-first
    // and outside-click. Only active while in walkthrough.
    //
    //   - Esc: the FIRST Esc collapses the card (it is consumed in the CAPTURE
    //     phase via stopPropagation so it does NOT also release the pointer this
    //     press — one Esc, one action). Once the card is COLLAPSED, a subsequent
    //     Esc is left untouched here and falls through to the walkthrough
    //     controller's own pointer-release handler (FIRST_ESC_EXITS_WALKTHROUGH =
    //     NO: the first Esc collapses the card, it does not exit walkthrough).
    //   - Outside-click: clicking anywhere outside the `.camera-mode` card collapses
    //     it. There is NO full-screen invisible blocker — we listen on the window
    //     and test the event target's ancestry, so 3D-scene pointer input is never
    //     intercepted (WALKTHROUGH_CARD_INVISIBLE_BLOCKER = NO).
    useEffect(() => {
        if (mode !== 'WALKTHROUGH') return
        const onKeyDownCapture = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && walkthroughCardOpen) {
                setWalkthroughCardOpen(false)
                e.stopPropagation() // consume: collapse the card, don't release pointer
            }
            // If the card is already collapsed, do nothing here — the controller's
            // own Esc handler performs the existing pointer-release behavior.
        }
        const onOutsidePointerDown = (e: PointerEvent) => {
            if (!walkthroughCardOpen) return
            const target = e.target as HTMLElement | null
            // Outside the whole card => collapse it. Clicks INSIDE keep it open.
            if (target && !target.closest('.camera-mode')) setWalkthroughCardOpen(false)
        }
        window.addEventListener('keydown', onKeyDownCapture, true) // capture phase
        window.addEventListener('pointerdown', onOutsidePointerDown)
        return () => {
            window.removeEventListener('keydown', onKeyDownCapture, true)
            window.removeEventListener('pointerdown', onOutsidePointerDown)
        }
    }, [mode, walkthroughCardOpen])

    const policy = resolveCameraModePolicy(mode)

    return (
        <div className="camera-mode" aria-label="View / camera mode">
            <span className="camera-mode-caption">VIEW</span>
            <div className="camera-mode-actions">
                {CAMERA_MODES.map((m) => (
                    <button
                        key={m}
                        type="button"
                        className={m === mode ? 'camera-mode-btn active' : 'camera-mode-btn'}
                        aria-pressed={m === mode}
                        disabled={pending}
                        onClick={() => void applyMode(m)}
                    >{MODE_LABEL[m]}</button>
                ))}
            </div>
            {mode === 'PLANNING' && (
                <div className="camera-mode-planning">
                    <span className="camera-mode-sub">Pan (after zoom)</span>
                    <div className="camera-mode-pan" role="group" aria-label="Planning pan controls">
                        <button type="button" className="camera-mode-pan-btn up" aria-label="Pan up" onClick={() => pan(0, 1)}>↑</button>
                        <div className="camera-mode-pan-mid">
                            <button type="button" className="camera-mode-pan-btn left" aria-label="Pan left" onClick={() => pan(-1, 0)}>←</button>
                            <button type="button" className="camera-mode-pan-btn right" aria-label="Pan right" onClick={() => pan(1, 0)}>→</button>
                        </div>
                        <button type="button" className="camera-mode-pan-btn down" aria-label="Pan down" onClick={() => pan(0, -1)}>↓</button>
                    </div>
                    <button
                        type="button"
                        className="camera-mode-help-reopen"
                        aria-expanded={planningHelpOpen}
                        onClick={() => setPlanningHelpOpen((o) => !o)}
                    >{planningHelpOpen ? 'Hide camera tips' : 'Camera tips'}</button>
                    {planningHelpOpen && (
                        <div className="camera-mode-help" role="dialog" aria-label="Planning camera controls">
                            <button type="button" className="camera-mode-help-close" aria-label="Dismiss camera tips" onClick={() => setPlanningHelpOpen(false)}>×</button>
                            <span className="camera-mode-help-text">
                                MacBook trackpad — Orbit (rotate): drag with one finger · Pan: two-finger drag (or the ←/→/↑/↓ buttons after a deep zoom) · Zoom: pinch, or two-finger scroll · Fit: double-tap, or the Fit control · Cutaway: use Bird&rsquo;s-eye to isolate a storey. The buttons above pan in screen space and keep working when the trackpad pan feels stuck after zooming in close.
                            </span>
                        </div>
                    )}
                </div>
            )}
            {mode === 'BIRDS_EYE_CUTAWAY' && (
                <div className="camera-mode-storeys">
                    <span className="camera-mode-sub">Level (storeys only)</span>
                    <button
                        type="button"
                        className={!activeStoreyId ? 'camera-mode-storey active' : 'camera-mode-storey'}
                        disabled={pending}
                        onClick={() => { setActiveStoreyId(undefined); void applyMode('BIRDS_EYE_CUTAWAY', undefined) }}
                    >All Building</button>
                    {storeys.map((s) => (
                        <button
                            key={s.id}
                            type="button"
                            className={s.id === activeStoreyId ? 'camera-mode-storey active' : 'camera-mode-storey'}
                            disabled={pending}
                            onClick={() => { setActiveStoreyId(s.id); void applyMode('BIRDS_EYE_CUTAWAY', s.id) }}
                        >{s.label}</button>
                    ))}
                </div>
            )}
            {mode === 'WALKTHROUGH' && walkthroughCardOpen && (
                <div className="camera-mode-walkthrough" role="group" aria-label="Walkthrough controls">
                    <div className="camera-mode-walkthrough-head">
                        <span className="camera-mode-sub">Walkthrough Controls</span>
                        <button
                            type="button"
                            className="camera-mode-card-close"
                            aria-label="Collapse walkthrough controls"
                            title="Collapse controls (Esc)"
                            onClick={() => setWalkthroughCardOpen(false)}
                        >×</button>
                    </div>
                    {storeys.length > 0 && (
                        <div className="camera-mode-storeys">
                            <span className="camera-mode-sub">Enter storey (storeys only)</span>
                            {storeys.map((s) => (
                                <button
                                    key={s.id}
                                    type="button"
                                    className={s.id === activeStoreyId ? 'camera-mode-storey active' : 'camera-mode-storey'}
                                    disabled={pending}
                                    onClick={() => { setActiveStoreyId(s.id); void applyMode('WALKTHROUGH', s.id) }}
                                >{s.label}</button>
                            ))}
                        </div>
                    )}
                    <div className="camera-mode-storeys">
                        <span className="camera-mode-sub">FOV</span>
                        {(['NORMAL', 'WIDE', 'ULTRA_WIDE'] as const).map((f) => (
                            <button
                                key={f}
                                type="button"
                                className={f === fov ? 'camera-mode-storey active' : 'camera-mode-storey'}
                                disabled={pending}
                                onClick={() => { setFov(f); void import('./spatialAssetOverlay').then((o) => o.setWalkthroughFov(f)) }}
                            >{f === 'NORMAL' ? 'Normal' : f === 'WIDE' ? 'Wide' : 'Ultra-wide'}</button>
                        ))}
                    </div>
                    <div className="camera-mode-actions">
                        <button type="button" className="camera-mode-btn" disabled={pending} onClick={() => { void import('./spatialAssetOverlay').then((o) => o.turnAroundWalkthrough()) }}>TURN AROUND</button>
                        <button type="button" className="camera-mode-btn" disabled={pending} onClick={() => { void import('./spatialAssetOverlay').then((o) => o.resetWalkthroughMode()) }}>RESET WALKTHROUGH</button>
                    </div>
                    <button type="button" className="camera-mode-exit" disabled={pending} onClick={() => void applyMode('PLANNING')}>EXIT WALKTHROUGH</button>
                    {controlsHelpOpen ? (
                        <div className="camera-mode-help" role="dialog" aria-label="Walkthrough key controls">
                            <button
                                type="button"
                                className="camera-mode-help-close"
                                aria-label="Close controls"
                                title="Close controls"
                                onClick={() => setControlsHelpOpen(false)}
                            >×</button>
                            <span className="camera-mode-help-text">Click + drag: Look around · Two-finger scroll: Incremental dolly · W/S: Walk · A/D: Strafe · ←/→: Turn · Shift: Faster · Esc: Release</span>
                        </div>
                    ) : (
                        <button
                            type="button"
                            className="camera-mode-help-reopen"
                            aria-label="Show walkthrough key controls"
                            onClick={() => setControlsHelpOpen(true)}
                        >Controls ?</button>
                    )}
                </div>
            )}
            {mode === 'WALKTHROUGH' && !walkthroughCardOpen && (
                <div className="camera-mode-walkthrough-collapsed" role="group" aria-label="Walkthrough controls (collapsed)">
                    <button
                        type="button"
                        className="camera-mode-card-reopen"
                        aria-label="Show walkthrough controls"
                        onClick={() => setWalkthroughCardOpen(true)}
                    >Walkthrough Controls</button>
                    {/* EXIT stays reachable even while the card is collapsed. */}
                    <button
                        type="button"
                        className="camera-mode-exit"
                        disabled={pending}
                        onClick={() => void applyMode('PLANNING')}
                    >EXIT WALKTHROUGH</button>
                </div>
            )}
            {note && <div className="camera-mode-note">{note}</div>}
            {/* Signals asset-manipulation ownership for the current mode (used by
                the overlay's tool gating; kept as a data attribute for clarity). */}
            <span hidden data-asset-manipulation={policy.assetManipulation ? 'on' : 'off'} />
        </div>
    )
}

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

    const applyMode = useCallback(async (next: CameraMode, storeyId?: string) => {
        if (pending) return
        setPending(true)
        setNote(next === 'WALKTHROUGH' ? 'Entering walkthrough… (click the model, WASD to move, mouse to look, Esc to release)' : next === 'BIRDS_EYE_CUTAWAY' ? 'Opening bird\u2019s-eye…' : 'Planning view')
        try {
            const overlay = await import('./spatialAssetOverlay')
            await overlay.applyCameraMode(next, { storeyId, fovPreset: next === 'WALKTHROUGH' ? fov : undefined })
            setMode(next)
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
            {mode === 'WALKTHROUGH' && (
                <>
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
                    <div className="camera-mode-help">W/S Walk · A/D Strafe · ←/→ Turn · Shift Faster · Drag to look · Esc release</div>
                </>
            )}
            {note && <div className="camera-mode-note">{note}</div>}
            {/* Signals asset-manipulation ownership for the current mode (used by
                the overlay's tool gating; kept as a data attribute for clarity). */}
            <span hidden data-asset-manipulation={policy.assetManipulation ? 'on' : 'off'} />
        </div>
    )
}

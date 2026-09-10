/**
 * AuditDiagnosticsPanel — DEV-only diagnostics hosted in a DEDICATED panel with
 * the same proven layout/hit-testing pattern as the ingestion panel (its own
 * high-z-index drawer, not buried at the bottom of the crowded, clipped
 * .viewer-dev-drawer where controls fell below the overflow fold and clicks
 * missed).
 *
 * RUN BIM CONTENT AUDIT and PROBE BENTLEY CLOUD PERMISSIONS live here. Every
 * button records SYNCHRONOUS pointerdown + click counters before any async, so a
 * physical click immediately shows POINTER_DOWN_COUNT / CLICK_COUNT and an
 * *_START_RECEIVED line — a blocked/failed trigger is visible, never a no-op.
 * Output renders inline (bounded); the audit reports the ACTIVE iModel id it ran
 * against. Read-only; no writes; no model-selection change.
 */
import { useCallback, useState } from 'react'

export function AuditDiagnosticsPanel() {
    const [pointerDownCount, setPointerDownCount] = useState(0)
    const [clickCount, setClickCount] = useState(0)
    const [status, setStatus] = useState('idle')
    const [out, setOut] = useState<string>('')
    const [busy, setBusy] = useState(false)

    const runAudit = useCallback(async () => {
        setClickCount((n) => n + 1)
        setStatus('AUDIT_START_RECEIVED')
        if (busy) { setOut('AUDIT blocked: a diagnostic is still running.'); return }
        setBusy(true); setOut('AUDIT_RUNNING (resolving active viewport/iModel + ECSQL)…')
        try {
            const mod = await import('./spatialAssetOverlay')
            const text = await mod.inspectBimContentAudit()
            setOut(text)
            setStatus('AUDIT_DONE')
        } catch (e) {
            setOut(`AUDIT error: ${e instanceof Error ? e.message : String(e)}`)
            setStatus('AUDIT_ERROR')
        } finally { setBusy(false) }
    }, [busy])

    const runProbe = useCallback(async () => {
        setClickCount((n) => n + 1)
        setStatus('PROBE_START_RECEIVED')
        if (busy) { setOut('PROBE blocked: a diagnostic is still running.'); return }
        setBusy(true); setOut('PROBE_RUNNING…')
        try {
            const mod = await import('./spatialAssetOverlay')
            const text = await mod.probeBentleyCloudPermissions()
            setOut(text)
            setStatus('PROBE_DONE')
        } catch (e) {
            setOut(`PROBE error: ${e instanceof Error ? e.message : String(e)}`)
            setStatus('PROBE_ERROR')
        } finally { setBusy(false) }
    }, [busy])

    // Live clinical-program overlay chain diagnostic. Same proven pattern: the
    // synchronous CLICK counter + CLINICAL_OVERLAY_DIAGNOSTIC_START_RECEIVED fire
    // BEFORE any async work, so a physical click is never a silent no-op.
    const runOverlayDiag = useCallback(async () => {
        setClickCount((n) => n + 1)
        setStatus('CLINICAL_OVERLAY_DIAGNOSTIC_START_RECEIVED')
        if (busy) { setOut('OVERLAY DIAGNOSTIC blocked: a diagnostic is still running.'); return }
        setBusy(true); setOut('CLINICAL_OVERLAY_DIAGNOSTIC_RUNNING (tracing assignment → footprint → storey → overlay → decorator → draw)…')
        try {
            const mod = await import('./spatialAssetOverlay')
            const text = await mod.diagnoseClinicalProgramOverlay()
            setOut(text)
            setStatus('CLINICAL_OVERLAY_DIAGNOSTIC_DONE')
        } catch (e) {
            setOut(`CLINICAL_OVERLAY_DIAGNOSTIC error: ${e instanceof Error ? e.message : String(e)}`)
            setStatus('CLINICAL_OVERLAY_DIAGNOSTIC_ERROR')
        } finally { setBusy(false) }
    }, [busy])

    // Read-only spatial-authority probe for the persisted Uptake 01 BIM space.
    // Same proven synchronous-first pattern; diagnostic-only (never mutates the overlay).
    const runRoomAuthorityDiag = useCallback(async () => {
        setClickCount((n) => n + 1)
        setStatus('ROOM_SPATIAL_DIAGNOSTIC_START_RECEIVED')
        if (busy) { setOut('SPATIAL AUTHORITY DIAGNOSTIC blocked: a diagnostic is still running.'); return }
        setBusy(true); setOut('ROOM_SPATIAL_DIAGNOSTIC_RUNNING (probing EC class → geometry → IFC → boundaries → authority)…')
        try {
            const mod = await import('./spatialAssetOverlay')
            const text = await mod.diagnoseRoomSpatialAuthority()
            setOut(text)
            setStatus('ROOM_SPATIAL_DIAGNOSTIC_DONE')
        } catch (e) {
            setOut(`ROOM_SPATIAL_DIAGNOSTIC error: ${e instanceof Error ? e.message : String(e)}`)
            setStatus('ROOM_SPATIAL_DIAGNOSTIC_ERROR')
        } finally { setBusy(false) }
    }, [busy])

    // AUTHORIZED one-time Uptake 01 baseline reconstruction (duplicate-guarded).
    // Explicit user action only; never auto-invoked on startup.
    const runReconstructUptake01 = useCallback(async () => {
        setClickCount((n) => n + 1)
        setStatus('UPTAKE_01_RECONSTRUCTION_START_RECEIVED')
        if (busy) { setOut('RECONSTRUCTION blocked: a diagnostic is still running.'); return }
        setBusy(true); setOut('UPTAKE_01_RECONSTRUCTION_RUNNING…')
        try {
            const mod = await import('./spatialAssetOverlay')
            const r = await mod.reconstructUptake01Baseline()
            if (!r.ok) setOut(`RECONSTRUCTION failed: ${r.reason}`)
            else if (r.alreadyPresent) setOut(`Uptake 01 already present (no duplicate). assignmentId=${r.assignmentId} planningVolumeId=${r.planningVolumeId}`)
            else setOut(`Uptake 01 reconstructed (DRAFT, visible). assignmentId=${r.assignmentId} planningVolumeId=${r.planningVolumeId}\nRun DIAGNOSE CLINICAL PROGRAM PERSISTENCE to verify.`)
            setStatus('UPTAKE_01_RECONSTRUCTION_DONE')
        } catch (e) {
            setOut(`UPTAKE_01_RECONSTRUCTION error: ${e instanceof Error ? e.message : String(e)}`)
            setStatus('UPTAKE_01_RECONSTRUCTION_ERROR')
        } finally { setBusy(false) }
    }, [busy])

    // Read-only persistence-regression diagnostic (localStorage namespace scan).
    const runPersistenceDiag = useCallback(async () => {
        setClickCount((n) => n + 1)
        setStatus('CLINICAL_PERSISTENCE_DIAGNOSTIC_START_RECEIVED')
        if (busy) { setOut('PERSISTENCE DIAGNOSTIC blocked: a diagnostic is still running.'); return }
        setBusy(true); setOut('CLINICAL_PERSISTENCE_DIAGNOSTIC_RUNNING…')
        try {
            const mod = await import('./spatialAssetOverlay')
            const text = await mod.diagnoseClinicalProgramPersistence()
            setOut(text)
            setStatus('CLINICAL_PERSISTENCE_DIAGNOSTIC_DONE')
        } catch (e) {
            setOut(`CLINICAL_PERSISTENCE_DIAGNOSTIC error: ${e instanceof Error ? e.message : String(e)}`)
            setStatus('CLINICAL_PERSISTENCE_DIAGNOSTIC_ERROR')
        } finally { setBusy(false) }
    }, [busy])

    // Bounded diagnostic of ALL clinical planning volumes (multi-object).
    const runPlanningVolumesDiag = useCallback(async () => {
        setClickCount((n) => n + 1)
        setStatus('PLANNING_VOLUMES_DIAGNOSTIC_START_RECEIVED')
        if (busy) { setOut('PLANNING VOLUMES DIAGNOSTIC blocked: a diagnostic is still running.'); return }
        setBusy(true); setOut('PLANNING_VOLUMES_DIAGNOSTIC_RUNNING…')
        try {
            const mod = await import('./spatialAssetOverlay')
            const text = await mod.diagnoseClinicalPlanningVolumes()
            setOut(text)
            setStatus('PLANNING_VOLUMES_DIAGNOSTIC_DONE')
        } catch (e) {
            setOut(`PLANNING_VOLUMES_DIAGNOSTIC error: ${e instanceof Error ? e.message : String(e)}`)
            setStatus('PLANNING_VOLUMES_DIAGNOSTIC_ERROR')
        } finally { setBusy(false) }
    }, [busy])

    // Bounded diagnostic of the MRT clinical PLANNING volume.
    const runPlanningVolumeDiag = useCallback(async () => {
        setClickCount((n) => n + 1)
        setStatus('PLANNING_VOLUME_DIAGNOSTIC_START_RECEIVED')
        if (busy) { setOut('PLANNING VOLUME DIAGNOSTIC blocked: a diagnostic is still running.'); return }
        setBusy(true); setOut('PLANNING_VOLUME_DIAGNOSTIC_RUNNING…')
        try {
            const mod = await import('./spatialAssetOverlay')
            const text = await mod.diagnoseClinicalPlanningVolume()
            setOut(text)
            setStatus('PLANNING_VOLUME_DIAGNOSTIC_DONE')
        } catch (e) {
            setOut(`PLANNING_VOLUME_DIAGNOSTIC error: ${e instanceof Error ? e.message : String(e)}`)
            setStatus('PLANNING_VOLUME_DIAGNOSTIC_ERROR')
        } finally { setBusy(false) }
    }, [busy])

    // Bounded diagnostic of the extracted authoritative IfcSpace footprint.
    const runAuthGeometryDiag = useCallback(async () => {
        setClickCount((n) => n + 1)
        setStatus('AUTH_GEOMETRY_DIAGNOSTIC_START_RECEIVED')
        if (busy) { setOut('AUTH GEOMETRY DIAGNOSTIC blocked: a diagnostic is still running.'); return }
        setBusy(true); setOut('AUTH_GEOMETRY_DIAGNOSTIC_RUNNING (extracting true IfcSpace footprint)…')
        try {
            const mod = await import('./spatialAssetOverlay')
            const text = await mod.diagnoseAuthoritativeRoomGeometry()
            setOut(text)
            setStatus('AUTH_GEOMETRY_DIAGNOSTIC_DONE')
        } catch (e) {
            setOut(`AUTH_GEOMETRY_DIAGNOSTIC error: ${e instanceof Error ? e.message : String(e)}`)
            setStatus('AUTH_GEOMETRY_DIAGNOSTIC_ERROR')
        } finally { setBusy(false) }
    }, [busy])

    return (
        <div className="audit-diag" aria-label="BIM audit diagnostics">
            <span className="viewer-dev-label">BIM AUDIT DIAGNOSTICS</span>
            <div className="audit-diag-actions">
                <button
                    type="button"
                    onPointerDown={() => setPointerDownCount((n) => n + 1)}
                    onClick={() => void runAudit()}
                >RUN BIM CONTENT AUDIT</button>
                <button
                    type="button"
                    onPointerDown={() => setPointerDownCount((n) => n + 1)}
                    onClick={() => void runProbe()}
                >PROBE BENTLEY CLOUD PERMISSIONS</button>
                <button
                    type="button"
                    onPointerDown={() => setPointerDownCount((n) => n + 1)}
                    onClick={() => void runOverlayDiag()}
                >DIAGNOSE CLINICAL PROGRAM OVERLAY</button>
                <button
                    type="button"
                    onPointerDown={() => setPointerDownCount((n) => n + 1)}
                    onClick={() => void runRoomAuthorityDiag()}
                >DIAGNOSE UPTAKE 01 SPATIAL AUTHORITY</button>
                <button
                    type="button"
                    onPointerDown={() => setPointerDownCount((n) => n + 1)}
                    onClick={() => void runAuthGeometryDiag()}
                >DIAGNOSE UPTAKE 01 AUTHORITATIVE GEOMETRY</button>
                <button
                    type="button"
                    onPointerDown={() => setPointerDownCount((n) => n + 1)}
                    onClick={() => void runPlanningVolumeDiag()}
                >DIAGNOSE UPTAKE 01 PLANNING VOLUME</button>
                <button
                    type="button"
                    onPointerDown={() => setPointerDownCount((n) => n + 1)}
                    onClick={() => void runPlanningVolumesDiag()}
                >DIAGNOSE CLINICAL PLANNING VOLUMES</button>
                <button
                    type="button"
                    onPointerDown={() => setPointerDownCount((n) => n + 1)}
                    onClick={() => void runPersistenceDiag()}
                >DIAGNOSE CLINICAL PROGRAM PERSISTENCE</button>
                <button
                    type="button"
                    onPointerDown={() => setPointerDownCount((n) => n + 1)}
                    onClick={() => void runReconstructUptake01()}
                >RECONSTRUCT UPTAKE 01 BASELINE</button>
            </div>
            <div className="audit-diag-state">
                status = {status}{busy ? ' (busy)' : ''} | POINTER_DOWN_COUNT = {pointerDownCount} | CLICK_COUNT = {clickCount}
            </div>
            {out && <pre className="audit-diag-out">{out}</pre>}
        </div>
    )
}

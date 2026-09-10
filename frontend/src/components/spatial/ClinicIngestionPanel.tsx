/**
 * ClinicIngestionPanel — DEV-only, explicitly two-stage UI for the Medical Clinic
 * demo BIM ingestion. Nothing runs on mount or on file selection. The user must:
 *   1. pick Clinic_Architectural.ifc,
 *   2. press PREFLIGHT (read-only: header check + existing-name check),
 *   3. then, only if preflight passes, press START INGESTION (the cloud writes).
 *
 * DIAGNOSTIC HARDENING (no-op fix): START is NEVER a silently-disabled button.
 * Its onClick ALWAYS runs and immediately records a synchronous START_RECEIVED
 * stage line, then reports each subsequent stage (guard result, token, first
 * POST, HTTP statuses). If a guard blocks it, that is shown explicitly instead
 * of a dead no-op. The bearer token is never displayed or logged.
 */
import { useCallback, useRef, useState } from 'react'
import type { PreflightResult, IngestionResult } from './bentleyClinicIngestion'

type Stage = 'IDLE' | 'PREFLIGHT_OK' | 'PREFLIGHT_BLOCKED' | 'INGESTING' | 'DONE'

export function ClinicIngestionPanel() {
    const [file, setFile] = useState<File | null>(null)
    const [stage, setStage] = useState<Stage>('IDLE')
    const [pre, setPre] = useState<PreflightResult | null>(null)
    const [result, setResult] = useState<IngestionResult | null>(null)
    const [log, setLog] = useState<string[]>([])
    const [busy, setBusy] = useState(false)
    // EARLY event-boundary diagnostics: incremented SYNCHRONOUSLY at pointerdown
    // and click, before any async. If these do not move on a physical click, the
    // pointer event is not reaching the button (layout/overlay defect).
    const [pointerDownCount, setPointerDownCount] = useState(0)
    const [clickCount, setClickCount] = useState(0)
    const inputRef = useRef<HTMLInputElement>(null)
    // Ref mirror of the latest stage/file/busy so the click handler reads FRESH
    // values even if a stale closure or re-render race is involved (this removes
    // the "silently ignored click" class of no-op entirely).
    const liveRef = useRef({ stage, file, busy })
    liveRef.current = { stage, file, busy }

    const appendLog = useCallback((line: string) => {
        const ts = new Date().toISOString().substring(11, 19)
        setLog((prev) => [...prev, `[${ts}] ${line}`])
    }, [])

    const onPick = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const f = e.target.files?.[0] ?? null
        setFile(f)
        setStage('IDLE'); setPre(null); setResult(null); setLog([]); setBusy(false)
    }, [])

    const runPreflight = useCallback(async () => {
        if (!liveRef.current.file) { appendLog('PREFLIGHT ignored: no file selected'); return }
        setBusy(true); appendLog('PREFLIGHT started')
        try {
            const mod = await import('./bentleyClinicIngestion')
            const r = await mod.preflight(liveRef.current.file)
            setPre(r)
            setStage(r.canProceed ? 'PREFLIGHT_OK' : 'PREFLIGHT_BLOCKED')
            appendLog(`PREFLIGHT ${r.canProceed ? 'OK' : 'BLOCKED'}: header=${r.headerCheck} existing=${r.existingDemoImodel}`)
        } catch (e) {
            setPre(null); setStage('PREFLIGHT_BLOCKED')
            appendLog(`PREFLIGHT error: ${e instanceof Error ? e.message : String(e)}`)
        } finally { setBusy(false) }
    }, [appendLog])

    // Read-only re-check: did the earlier click nevertheless create the demo?
    const recheckExisting = useCallback(async () => {
        appendLog('RECHECK_RUNNING')
        appendLog('RECHECK existing demo iModel (GET-only)…')
        try {
            const mod = await import('./bentleyClinicIngestion')
            const r = await mod.checkDemoImodelExists()
            appendLog(`RECHECK: ${r.status}${r.id ? ` id=${r.id}` : ''}${r.raw ? ` (${r.raw})` : ''}`)
            if (r.status === 'ALREADY_EXISTS' && r.id) appendLog(`OPEN: /viewer?imodel=${r.id} (verify content before reuse)`)
        } catch (e) {
            appendLog(`RECHECK error: ${e instanceof Error ? e.message : String(e)}`)
        }
    }, [appendLog])

    const startIngestion = useCallback(async () => {
        // ALWAYS record the click synchronously — never a silent no-op.
        appendLog('START_RECEIVED')
        const { stage: s, file: f, busy: b } = liveRef.current
        if (!f) { appendLog('START blocked: no file selected'); return }
        if (b) { appendLog('START blocked: a previous operation is still busy'); return }
        if (s !== 'PREFLIGHT_OK') { appendLog(`START blocked: stage=${s} (run PREFLIGHT until OK)`); return }

        setBusy(true); setStage('INGESTING')
        appendLog('START accepted -> INGESTING')
        try {
            const mod = await import('./bentleyClinicIngestion')
            appendLog('ingestion module loaded; invoking startIngestion()')
            const r = await mod.startIngestion(f, appendLog)
            setResult(r); setStage('DONE')
            appendLog(`FINISHED: IFC_SYNCHRONIZATION_STATUS=${r.synchronizationStatus}`)
        } catch (e) {
            appendLog(`ingestion error: ${e instanceof Error ? e.message : String(e)}`)
            setStage('DONE')
        } finally { setBusy(false) }
    }, [appendLog])

    return (
        <div className="clinic-ingest" aria-label="Medical Clinic demo ingestion">
            <span className="viewer-dev-label">MEDICAL CLINIC DEMO INGESTION</span>
            <input ref={inputRef} type="file" accept=".ifc" onChange={onPick} aria-label="Select Clinic_Architectural.ifc" />
            <div className="clinic-ingest-actions">
                <button type="button" onClick={() => void runPreflight()}>PREFLIGHT</button>
                <button
                    type="button"
                    onPointerDown={() => setPointerDownCount((n) => n + 1)}
                    onClick={() => { setClickCount((n) => n + 1); void recheckExisting() }}
                >RE-CHECK DEMO EXISTS</button>
                {/* START is intentionally NOT disabled: it always runs and reports
                    its guard result, so a blocked start is visible, never a no-op. */}
                <button
                    type="button"
                    className="clinic-ingest-start"
                    onPointerDown={() => setPointerDownCount((n) => n + 1)}
                    onClick={() => { setClickCount((n) => n + 1); void startIngestion() }}
                >START INGESTION</button>
            </div>
            <div className="clinic-ingest-state">
                stage = {stage}{busy ? ' (busy)' : ''} | POINTER_DOWN_COUNT = {pointerDownCount} | CLICK_COUNT = {clickCount}
            </div>
            {pre && (
                <pre className="clinic-ingest-out">{[
                    `file = ${pre.fileName} (${(pre.fileSizeBytes / 1048576).toFixed(1)} MiB)`,
                    `header = ${pre.headerCheck}`,
                    `existing "MRTway Medical Clinic Demo" = ${pre.existingDemoImodel}`,
                    `canProceed = ${pre.canProceed}`,
                    pre.message,
                ].join('\n')}</pre>
            )}
            {log.length > 0 && <pre className="clinic-ingest-out">{log.join('\n')}</pre>}
            {result && (
                <pre className="clinic-ingest-out">{[
                    `DEMO_IMODEL_CREATED = ${result.demoImodelCreated ? 'YES' : 'NO'}`,
                    `DEMO_IMODEL_ID = ${result.demoImodelId}`,
                    `IFC_UPLOADED = ${result.ifcUploaded ? 'YES' : 'NO'}`,
                    `SYNCHRONIZATION_CONNECTION_CREATED = ${result.connectionCreated ? 'YES' : 'NO'}`,
                    `SYNCHRONIZATION_CONNECTION_ID = ${result.connectionId}`,
                    `IFC_SYNCHRONIZATION_STARTED = ${result.runStarted ? 'YES' : 'NO'}`,
                    `IFC_SYNCHRONIZATION_STATUS = ${result.synchronizationStatus}`,
                    `run state/result = ${result.runState} / ${result.runResult}`,
                    `ENGINEERING_FIXTURE_MODIFIED = NO`,
                    result.synchronizationStatus === 'SUCCEEDED' && result.demoImodelId !== 'NOT_CREATED'
                        ? `\nOPEN DEMO: /viewer?imodel=${result.demoImodelId}  (fixture stays default without the query)`
                        : '',
                ].filter(Boolean).join('\n')}</pre>
            )}
        </div>
    )
}

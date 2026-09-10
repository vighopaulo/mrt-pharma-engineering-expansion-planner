/**
 * ClinicalProgramControl — NORMAL-MODE MRT Pharma CLINICAL PROGRAM panel.
 *
 * A normal product-facing (Capital Project) affordance to overlay a
 * non-destructive clinical-program layer on the existing Bentley BIM:
 *   - toggle the CLINICAL PROGRAM overlay on/off (§79/§83);
 *   - filter by the active storey (§31);
 *   - select a real BIM space by its original label (BIM_SPACE_ID key; §12/§80);
 *   - the room editor shows Original BIM name / Storey / current function / MRT
 *     name, with Assign/Update + Reset to Existing (§14/§81/§18);
 *   - a compact program summary + informational PET-demo completeness (§36/§37).
 *
 * It NEVER shows raw UUIDs in normal mode (§82) and NEVER writes to Bentley — it
 * drives only the application-owned program store in spatialAssetOverlay. All
 * assignment logic is the pure clinicalProgram seam. Persistence is iModel-scoped.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { CLINICAL_FUNCTIONS, type ClinicalFunction, type ClinicalProgramAssignment } from './clinicalProgram'

const FUNCTION_LABEL: Record<ClinicalFunction, string> = {
    UNASSIGNED_EXISTING: 'Unassigned (existing)',
    RADIOPHARMACY: 'Radiopharmacy',
    CYCLOTRON: 'Cyclotron',
    HOT_CELL_SYNTHESIS: 'Hot Cell / Synthesis',
    QUALITY_CONTROL: 'Quality Control',
    DOSE_DISPENSING: 'Dose Dispensing',
    INJECTION_ROOM: 'Injection Room',
    UPTAKE_ROOM: 'Uptake Room',
    PET_CT_SCANNER_ROOM: 'PET/CT Scanner Room',
    SPECT_CT_SCANNER_ROOM: 'SPECT/CT Scanner Room',
    CONTROL_ROOM: 'Control Room',
    PATIENT_WAITING: 'Patient Waiting',
    PATIENT_PREPARATION: 'Patient Preparation',
    RECOVERY: 'Recovery',
    CLEAN_SUPPLY: 'Clean Supply',
    WASTE_DECAY_STORAGE: 'Waste / Decay Storage',
    STAFF_SUPPORT: 'Staff Support',
    MECHANICAL_ELECTRICAL: 'Mechanical / Electrical',
    CLINICAL_CORRIDOR: 'Clinical Corridor',
    GENERAL_SUPPORT: 'General Support',
}

interface RoomOption { bimSpaceId: string; originalBimLabel: string; storeyLabel?: string }
interface StoreyOpt { id: string; label: string }

export function ClinicalProgramControl(props?: { iModelId?: string; devMode?: boolean }) {
    const devMode = props?.devMode ?? false
    const [enabled, setEnabled] = useState(false)
    const [rooms, setRooms] = useState<RoomOption[]>([])
    const [storeys, setStoreys] = useState<StoreyOpt[]>([])
    const [activeStoreyId, setActiveStoreyId] = useState<string | undefined>(undefined)
    const [selectedSpaceId, setSelectedSpaceId] = useState<string | undefined>(undefined)
    const [assignments, setAssignments] = useState<readonly ClinicalProgramAssignment[]>([])
    const [pendingFunction, setPendingFunction] = useState<ClinicalFunction>('UNASSIGNED_EXISTING')
    const [pendingName, setPendingName] = useState('')
    const [geometryQuality, setGeometryQuality] = useState<string | null>(null)
    const [showRoomVolume, setShowRoomVolume] = useState(false)
    // Clinical planning VOLUME (true 3D world prism child of the parent IfcSpace).
    const [vol, setVol] = useState<{ params: { centerX: number; centerY: number; zLow: number; zHigh: number; width: number; depth: number; yaw: number }; lifecycleState: 'DRAFT' | 'LOCKED'; hidden?: boolean } | null>(null)
    const [volumeSummary, setVolumeSummary] = useState<{ planningVolumes: number; draft: number; locked: number } | null>(null)
    const [volDraft, setVolDraft] = useState<{ centerX: number; centerY: number; zLow: number; zHigh: number; width: number; depth: number; yawDeg: number }>({ centerX: 0, centerY: 0, zLow: 0, zHigh: 3, width: 4, depth: 3, yawDeg: 0 })
    const [containment, setContainment] = useState<string>('')
    const [note, setNote] = useState('')
    const [loading, setLoading] = useState(false)
    // Build 1A.4: product-facing containment validation view model + summary.
    const [validation, setValidation] = useState<import('./bimRoomVolumeRegistry').PlanningVolumeValidationState | null>(null)
    const [validationSummary, setValidationSummary] = useState<import('./bimRoomVolumeRegistry').PlanningValidationSummary | null>(null)
    // Build 1A.1: honest room-discovery lifecycle (never a false READY-zero).
    const [discoveryStatus, setDiscoveryStatus] = useState<'NOT_BOUND' | 'LOADING' | 'READY' | 'ERROR'>('NOT_BOUND')
    const [selectorLabel, setSelectorLabel] = useState<string>('Open the model to discover rooms')

    // Build 1A.3: derive the STOREY-FILTERED selector options + honest count/label
    // from the immutable base discovery via the overlay's pure filter. Called on
    // every program notification (incl. storey-filter change) so the selector
    // recomputes immediately. `o` is the already-imported overlay module.
    const applyRoomOptions = useCallback((o: typeof import('./spatialAssetOverlay')) => {
        const ui = o.getRoomDiscoveryUiStatus()
        const options = o.getDiscoveredRoomOptions() // storey-filtered discovered rooms
        setRooms(options.map((r) => ({ bimSpaceId: r.bimSpaceId, originalBimLabel: r.originalBimLabel || 'Unnamed space', storeyLabel: r.storeyId })))
        setDiscoveryStatus(ui.status)
        setSelectorLabel(ui.label)
        if (ui.status === 'READY') setNote(ui.baseRoomCount === 0 ? 'This BIM exposes no valid rooms.' : '')
        else if (ui.status === 'ERROR') setNote('Room discovery unavailable — retrying.')
        else setNote('')
    }, [])

    // Bind program state to the active iModel + subscribe.
    useEffect(() => {
        let unsub = () => { }
        let cancelled = false
        void import('./spatialAssetOverlay').then((o) => {
            if (props?.iModelId) o.loadClinicalProgramForIModel(props.iModelId)
            const sync = () => {
                if (cancelled) return
                const snap = o.getClinicalProgramSnapshot()
                setEnabled(snap.enabled)
                setActiveStoreyId(snap.activeStoreyId)
                setSelectedSpaceId(snap.selectedSpaceId)
                setAssignments(snap.assignments)
                setShowRoomVolume(snap.showRoomVolume)
                // Build 1A.2: re-read the selected room's geometry quality on EVERY
                // program notification, so async exact-mesh extraction completion
                // (which calls notifyProgram) reactively updates the Spatial geometry
                // status — no reselect / reload / dev-mode needed.
                setGeometryQuality(snap.selectedSpaceId
                    ? (o.getClinicalProgramRoomGeometryQuality(snap.selectedSpaceId)?.description ?? null)
                    : null)
                // Build 1A.3: re-derive the STOREY-FILTERED room options + count on
                // EVERY notification (a storey-filter change calls notifyProgram), so
                // the selector recomputes immediately from the immutable base
                // discovery — fixing the First=Second=153 stale-count/options defect.
                applyRoomOptions(o)
                // Out-of-filter selected-room policy: if the selected room is not in
                // the active storey's options, clear the UI selection ONLY (never
                // deletes the assignment or planning volume — domain state persists).
                if (o.isSelectedRoomOutsideActiveStorey()) o.setClinicalProgramSelectedSpace(undefined)
            }
            unsub = o.subscribeClinicalProgram(sync)
            sync()
        })
        return () => { cancelled = true; unsub() }
    }, [props?.iModelId])

    // Load storeys once enabled so the storey filter + Z-binning have ranges.
    useEffect(() => {
        if (!enabled) return
        let cancelled = false
        void import('./spatialAssetOverlay').then(async (o) => {
            const list = await o.loadCameraStoreys()
            if (cancelled) return
            o.setClinicalProgramStoreyRanges(list.map((s) => ({ id: s.id, label: s.label, zLow: s.zLow, zHigh: s.zHigh })))
            setStoreys(list.map((s) => ({ id: s.id, label: s.label })))
        })
        return () => { cancelled = true }
    }, [enabled])

    // Load the selectable BIM rooms (needs semantics; refresh if empty).
    const refreshRooms = useCallback(async () => {
        setLoading(true)
        try {
            const o = await import('./spatialAssetOverlay')
            // Build 1A.1: drive the lifecycle-guarded refresh, then read the HONEST
            // discovery status. A NOT_READY/FAILED refresh no longer erases a valid
            // cache, and 0 rooms is only shown as final when status is READY.
            await o.refreshModelSemantics()
            applyRoomOptions(o)
        } finally { setLoading(false) }
    }, [applyRoomOptions])

    // Drive discovery while enabled: (re)load until READY, then stop. A LOADING /
    // NOT_BOUND / ERROR status schedules a bounded retry (the viewport may still
    // be binding); a READY status (even READY-zero) is terminal for auto-retry.
    useEffect(() => {
        if (!enabled) return
        if (discoveryStatus === 'READY') return
        let cancelled = false
        let attempts = 0
        const tick = () => {
            if (cancelled) return
            attempts += 1
            void refreshRooms().then(() => {
                if (cancelled) return
                // getRoomDiscoveryUiStatus already applied via setDiscoveryStatus;
                // schedule another bounded attempt if still not READY.
                if (attempts < 20) window.setTimeout(() => {
                    if (cancelled) return
                    void import('./spatialAssetOverlay').then((o) => {
                        if (o.getRoomDiscoveryUiStatus().status !== 'READY') tick()
                    })
                }, 500)
            })
        }
        tick()
        return () => { cancelled = true }
    }, [enabled, discoveryStatus, refreshRooms])

    const toggleEnabled = useCallback(() => {
        void import('./spatialAssetOverlay').then((o) => o.setClinicalProgramEnabled(!enabled))
    }, [enabled])

    const chooseStorey = useCallback((id: string | undefined) => {
        void import('./spatialAssetOverlay').then((o) => o.setClinicalProgramActiveStorey(id))
    }, [])

    const selectSpace = useCallback((id: string | undefined) => {
        void import('./spatialAssetOverlay').then((o) => {
            o.setClinicalProgramSelectedSpace(id)
            const current = id ? o.getClinicalProgramAssignment(id) : undefined
            setPendingFunction(current?.clinicalFunction ?? 'UNASSIGNED_EXISTING')
            setPendingName(current?.mrtDisplayName ?? '')
            setGeometryQuality(id ? (o.getClinicalProgramRoomGeometryQuality(id)?.description ?? null) : null)
        })
    }, [])

    const selectedRoom = useMemo(() => rooms.find((r) => r.bimSpaceId === selectedSpaceId), [rooms, selectedSpaceId])
    const currentAssignment = useMemo(
        () => assignments.find((a) => a.bimSpaceId === selectedSpaceId && a.clinicalFunction !== 'UNASSIGNED_EXISTING'),
        [assignments, selectedSpaceId],
    )

    const doAssign = useCallback(() => {
        if (!selectedRoom) return
        void import('./spatialAssetOverlay').then((o) => {
            const storeyId = o.getClinicalProgramRoomStoreyId(selectedRoom.bimSpaceId)
            const result = o.assignClinicalProgram({
                bimSpace: { bimSpaceId: selectedRoom.bimSpaceId, originalBimLabel: selectedRoom.originalBimLabel, bimStoreyId: storeyId },
                clinicalFunction: pendingFunction,
                requestedDisplayName: pendingName.trim() || undefined,
            })
            if (!result.ok) { setNote(`Could not assign: ${result.reason}`); return }
            setPendingName(result.assignment.mrtDisplayName)
            setNote(pendingFunction === 'UNASSIGNED_EXISTING' ? 'Reset to existing.' : `Assigned ${FUNCTION_LABEL[pendingFunction]} → ${result.assignment.mrtDisplayName}`)
        })
    }, [selectedRoom, pendingFunction, pendingName])

    const doReset = useCallback(() => {
        if (!selectedSpaceId) return
        void import('./spatialAssetOverlay').then((o) => {
            o.resetClinicalProgram(selectedSpaceId)
            setPendingFunction('UNASSIGNED_EXISTING')
            setPendingName('')
            setNote('Reset to existing — BIM identity unchanged.')
        })
    }, [selectedSpaceId])

    // --- Clinical planning VOLUME handlers ---------------------------------
    const refreshVolume = useCallback((spaceId: string | undefined) => {
        if (!spaceId) { setVol(null); setContainment(''); setValidation(null); return }
        void import('./spatialAssetOverlay').then(async (o) => {
            const v = o.getClinicalPlanningVolume(spaceId)
            o.getClinicalVolumeSummary().then((s) => setVolumeSummary({ planningVolumes: s.planningVolumes, draft: s.draft, locked: s.locked })).catch(() => { })
            o.getPlanningValidationSummary().then((s) => setValidationSummary(s)).catch(() => { })
            if (v) {
                setVol({ params: v.params, lifecycleState: v.lifecycleState, hidden: v.hidden })
                setVolDraft({ centerX: v.params.centerX, centerY: v.params.centerY, zLow: v.params.zLow, zHigh: v.params.zHigh, width: v.params.width, depth: v.params.depth, yawDeg: (v.params.yaw * 180) / Math.PI })
                const c = await o.getClinicalVolumeContainment(spaceId)
                if (c.status === 'PASS') setContainment(`INSIDE PARENT SPACE (${c.totalSamples - c.failedSamples}/${c.totalSamples})`)
                else if (c.status === 'FAIL') setContainment(`OUTSIDE PARENT SPACE (${c.failedSamples}/${c.totalSamples} outside)`)
                else setContainment(`CONTAINMENT NOT EVALUATED${c.reason ? ` (${c.reason})` : ''}`)
                // Build 1A.4: pure product-facing validation view model (warning,
                // lock gate + reason, restore availability, approximate label).
                setValidation((await o.getPlanningVolumeValidation(spaceId)) ?? null)
            } else { setVol(null); setContainment(''); setValidation(null) }
        })
    }, [])

    const restoreValidPosition = useCallback(() => {
        if (!selectedRoom) return
        void import('./spatialAssetOverlay').then(async (o) => {
            const r = await o.restoreValidPosition(selectedRoom.bimSpaceId)
            setNote(r.ok ? (r.source === 'LAST_KNOWN_VALID' ? 'Restored last valid position.' : 'No prior valid position — restored a parent-derived valid volume.') : `Cannot restore: ${r.reason}`)
            refreshVolume(selectedRoom.bimSpaceId)
        })
    }, [selectedRoom, refreshVolume])

    const resetToParentDerived = useCallback(() => {
        if (!selectedRoom) return
        void import('./spatialAssetOverlay').then(async (o) => {
            const r = await o.resetToParentDerived(selectedRoom.bimSpaceId)
            setNote(r.ok ? 'Reset to a fresh parent-derived volume.' : `Cannot reset: ${r.reason}`)
            refreshVolume(selectedRoom.bimSpaceId)
        })
    }, [selectedRoom, refreshVolume])

    useEffect(() => { refreshVolume(selectedSpaceId) }, [selectedSpaceId, assignments, refreshVolume])

    const draftToParams = useCallback((d: typeof volDraft) => ({ centerX: d.centerX, centerY: d.centerY, zLow: d.zLow, zHigh: d.zHigh, width: d.width, depth: d.depth, yaw: (d.yawDeg * Math.PI) / 180 }), [])

    const defineVolume = useCallback(() => {
        if (!selectedRoom || !currentAssignment) return
        void import('./spatialAssetOverlay').then(async (o) => {
            const storeyId = o.getClinicalProgramRoomStoreyId(selectedRoom.bimSpaceId)
            // NEW volume: seed from THIS parent's authoritative BIM geometry (never
            // Uptake coords / origin). Existing volume: keep the current draft.
            const seed = vol ? draftToParams(volDraft) : await o.suggestPlanningVolumeSeedForParent(selectedRoom.bimSpaceId)
            await o.defineClinicalVolume({ parentBimSpaceId: selectedRoom.bimSpaceId, clinicalFunction: currentAssignment.clinicalFunction, displayName: currentAssignment.mrtDisplayName, storeyId, params: seed })
            refreshVolume(selectedRoom.bimSpaceId)
            setNote('Draft clinical volume defined from parent BIM geometry (3D world).')
        })
    }, [selectedRoom, currentAssignment, vol, volDraft, draftToParams, refreshVolume])

    const applyVolumeEdit = useCallback((next: typeof volDraft) => {
        setVolDraft(next)
        if (!selectedRoom) return
        void import('./spatialAssetOverlay').then((o) => { o.updateClinicalVolumeParams(selectedRoom.bimSpaceId, draftToParams(next)); refreshVolume(selectedRoom.bimSpaceId) })
    }, [selectedRoom, draftToParams, refreshVolume])

    const lockVolume = useCallback(() => {
        if (!selectedRoom) return
        void import('./spatialAssetOverlay').then(async (o) => {
            const r = await o.lockClinicalVolume(selectedRoom.bimSpaceId)
            setNote(r.ok ? 'Clinical volume LOCKED.' : `Cannot lock: ${r.reason}`)
            refreshVolume(selectedRoom.bimSpaceId)
        })
    }, [selectedRoom, refreshVolume])

    const unlockVolume = useCallback(() => {
        if (!selectedRoom) return
        void import('./spatialAssetOverlay').then((o) => { o.unlockClinicalVolume(selectedRoom.bimSpaceId); refreshVolume(selectedRoom.bimSpaceId) })
    }, [selectedRoom, refreshVolume])

    // Per-volume show/hide (independent of other volumes).
    const toggleThisVolume = useCallback(() => {
        if (!selectedRoom || !vol) return
        void import('./spatialAssetOverlay').then((o) => { o.setPlanningVolumeVisibility(selectedRoom.bimSpaceId, !!vol.hidden); refreshVolume(selectedRoom.bimSpaceId) })
    }, [selectedRoom, vol, refreshVolume])

    const deleteVolume = useCallback(() => {
        if (!selectedRoom) return
        void import('./spatialAssetOverlay').then(async (o) => {
            const r = await o.deleteClinicalVolume(selectedRoom.bimSpaceId)
            setNote(r.ok ? 'Clinical volume deleted (assignment + BIM space unchanged).' : `Cannot delete: ${r.reason}`)
            refreshVolume(selectedRoom.bimSpaceId)
        })
    }, [selectedRoom, refreshVolume])

    const summary = useMemo(() => {
        const active = assignments.filter((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')
        const byFn = new Map<ClinicalFunction, number>()
        for (const a of active) byFn.set(a.clinicalFunction, (byFn.get(a.clinicalFunction) ?? 0) + 1)
        return { assignedCount: active.length, byFn: [...byFn.entries()] }
    }, [assignments])

    // Build 2A three-room proof: Uptake + Injection + PET/CT (Radiopharmacy is
    // deferred to Build 2B — the full PET department is NOT complete here).
    const completeness = useMemo(() => {
        const required: ClinicalFunction[] = ['UPTAKE_ROOM', 'INJECTION_ROOM', 'PET_CT_SCANNER_ROOM']
        const present = new Set(assignments.map((a) => a.clinicalFunction))
        const missing = required.filter((f) => !present.has(f))
        return { missing, threeRoomProofComplete: missing.length === 0 }
    }, [assignments])

    return (
        <div className="clinical-program" aria-label="MRT Pharma clinical program">
            <div className="clinical-program-head">
                <span className="clinical-program-caption">CLINICAL PROGRAM</span>
                <button
                    type="button"
                    className={enabled ? 'clinical-program-toggle active' : 'clinical-program-toggle'}
                    aria-pressed={enabled}
                    onClick={toggleEnabled}
                >{enabled ? 'On' : 'Off'}</button>
            </div>

            {enabled && (
                <>
                    <div className="clinical-program-hint">Bird&rsquo;s-eye / Cutaway is the primary programming view. Assignments are planning overlays — the Bentley BIM is never renamed.</div>

                    {storeys.length > 0 && (
                        <div className="clinical-program-storeys">
                            <span className="clinical-program-sub">Storey filter</span>
                            <button type="button" className={!activeStoreyId ? 'clinical-program-chip active' : 'clinical-program-chip'} onClick={() => chooseStorey(undefined)}>All</button>
                            {storeys.map((s) => (
                                <button key={s.id} type="button" className={s.id === activeStoreyId ? 'clinical-program-chip active' : 'clinical-program-chip'} onClick={() => chooseStorey(s.id)}>{s.label}</button>
                            ))}
                        </div>
                    )}

                    <div className="clinical-program-row">
                        <span className="clinical-program-sub">Room (BIM space)</span>
                        <select
                            className="clinical-program-select"
                            value={selectedSpaceId ?? ''}
                            onChange={(e) => selectSpace(e.target.value || undefined)}
                        >
                            <option value="">{loading && discoveryStatus !== 'READY' ? 'Loading rooms…' : selectorLabel}</option>
                            {rooms.map((r) => {
                                const a = assignments.find((x) => x.bimSpaceId === r.bimSpaceId && x.clinicalFunction !== 'UNASSIGNED_EXISTING')
                                const label = a ? `${a.mrtDisplayName} — ${r.originalBimLabel}` : r.originalBimLabel
                                return <option key={r.bimSpaceId} value={r.bimSpaceId}>{label}</option>
                            })}
                        </select>
                    </div>

                    {selectedRoom && (
                        <div className="clinical-program-editor">
                            <div className="clinical-program-field"><span>Original BIM room</span><strong>{selectedRoom.originalBimLabel}</strong></div>
                            <div className="clinical-program-field"><span>Storey</span><strong>{storeys.find((s) => s.id === (activeStoreyId))?.label ?? '—'}</strong></div>
                            <div className="clinical-program-field"><span>Current function</span><strong>{currentAssignment ? FUNCTION_LABEL[currentAssignment.clinicalFunction] : 'Unassigned (existing)'}</strong></div>
                            {geometryQuality && <div className="clinical-program-field"><span>Spatial geometry</span><strong>{geometryQuality}</strong></div>}

                            <label className="clinical-program-sub" htmlFor="cp-fn">Assign clinical function</label>
                            <select id="cp-fn" className="clinical-program-select" value={pendingFunction} onChange={(e) => setPendingFunction(e.target.value as ClinicalFunction)}>
                                {CLINICAL_FUNCTIONS.map((f) => <option key={f} value={f}>{FUNCTION_LABEL[f]}</option>)}
                            </select>

                            {pendingFunction !== 'UNASSIGNED_EXISTING' && (
                                <>
                                    <label className="clinical-program-sub" htmlFor="cp-name">MRT Pharma name</label>
                                    <input id="cp-name" className="clinical-program-input" value={pendingName} placeholder="auto (e.g. Uptake 01)" onChange={(e) => setPendingName(e.target.value)} />
                                </>
                            )}

                            <div className="clinical-program-actions">
                                <button type="button" className="clinical-program-btn primary" onClick={doAssign}>{pendingFunction === 'UNASSIGNED_EXISTING' ? 'Set Unassigned' : 'Assign / Update'}</button>
                                <button type="button" className="clinical-program-btn" onClick={doReset} disabled={!currentAssignment}>Reset to Existing</button>
                            </div>

                            {currentAssignment && (
                                <div className="clinical-program-volume">
                                    <span className="clinical-program-sub">Clinical volume (true 3D)</span>
                                    {!vol ? (
                                        <button type="button" className="clinical-program-btn primary" onClick={defineVolume}>Define Volume</button>
                                    ) : (
                                        <>
                                            <div className="clinical-program-grid">
                                                {([['centerX', 'X'], ['centerY', 'Y'], ['width', 'Width'], ['depth', 'Depth'], ['zLow', 'Z Low'], ['zHigh', 'Z High'], ['yawDeg', 'Yaw°']] as const).map(([k, lbl]) => (
                                                    <label key={k} className="clinical-program-num">
                                                        <span>{lbl}</span>
                                                        <input
                                                            type="number"
                                                            step="0.1"
                                                            className="clinical-program-input"
                                                            value={volDraft[k]}
                                                            disabled={vol.lifecycleState === 'LOCKED'}
                                                            onChange={(e) => applyVolumeEdit({ ...volDraft, [k]: Number(e.target.value) })}
                                                        />
                                                    </label>
                                                ))}
                                            </div>
                                            {/* Build 1A.4: product-facing validation. Warning identifies the
                                                room; technical sample detail is secondary. NOT_EVALUATED is
                                                shown honestly (never inside/outside). */}
                                            {validation?.containmentStatus === 'PASS' && (
                                                <div className="clinical-program-summary-line ok">Fully inside its parent BIM room.{validation.approximateParent ? ' (parent is a range approximation)' : ''}</div>
                                            )}
                                            {validation?.warningCode === 'OUTSIDE_PARENT' && (
                                                <div className="clinical-program-warning" role="alert">
                                                    <strong>⚠ {validation.warningMessage}</strong>
                                                    <div className="clinical-program-summary-line muted">{validation.technicalDetail}</div>
                                                </div>
                                            )}
                                            {(validation?.warningCode === 'NOT_EVALUATED' || validation?.warningCode === 'PARENT_GEOMETRY_UNAVAILABLE') && (
                                                <div className="clinical-program-summary-line muted">{validation.warningMessage}</div>
                                            )}
                                            <div className="clinical-program-actions">
                                                {vol.lifecycleState === 'DRAFT'
                                                    ? <button type="button" className="clinical-program-btn primary" onClick={lockVolume} disabled={!validation?.isLockAllowed} title={validation && !validation.isLockAllowed ? validation.lockDisabledReason : 'Lock this planning volume'}>Lock Volume</button>
                                                    : <button type="button" className="clinical-program-btn" onClick={unlockVolume}>Unlock for Editing</button>}
                                                <button type="button" className={vol.hidden ? 'clinical-program-btn' : 'clinical-program-btn primary'} onClick={toggleThisVolume}>{vol.hidden ? 'Show Volume' : 'Hide Volume'}</button>
                                            </div>
                                            {vol.lifecycleState === 'DRAFT' && !validation?.isLockAllowed && (
                                                <div className="clinical-program-summary-line muted">Lock unavailable: {validation?.lockDisabledReason}</div>
                                            )}
                                            <div className="clinical-program-actions">
                                                {validation?.restoreAvailable && (
                                                    <button type="button" className="clinical-program-btn" onClick={restoreValidPosition} disabled={vol.lifecycleState === 'LOCKED'} title="Restore this volume's most recent valid position (or a parent-derived valid volume)">Restore Valid Position</button>
                                                )}
                                                <button type="button" className="clinical-program-btn" onClick={resetToParentDerived} disabled={vol.lifecycleState === 'LOCKED'} title="Recompute a fresh valid volume from this room's own BIM geometry">Reset to Parent-Derived Volume</button>
                                            </div>
                                            <div className="clinical-program-actions">
                                                <button type="button" className="clinical-program-btn" onClick={deleteVolume} disabled={vol.lifecycleState === 'LOCKED'} title={vol.lifecycleState === 'LOCKED' ? 'Unlock before deleting' : 'Delete this planning volume (assignment kept)'}>Delete Volume</button>
                                            </div>
                                            <div className="clinical-program-summary-line muted">State: {vol.lifecycleState} · {vol.hidden ? 'hidden' : 'visible'}</div>
                                        </>
                                    )}
                                </div>
                            )}

                            {devMode && (
                                <div className="clinical-program-dev">
                                    {containment && <span>containment(raw): {containment}</span>}
                                    <span>bimSpaceId: {selectedRoom.bimSpaceId}</span>
                                    {currentAssignment && <span>assignmentId: {currentAssignment.assignmentId}</span>}
                                    {currentAssignment?.bimStoreyId && <span>bimStoreyId: {currentAssignment.bimStoreyId}</span>}
                                    <span>provenance: USER_DEFINED_PLANNING_OVERLAY · status: PLANNING_ASSIGNMENT</span>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="clinical-program-summary">
                        <span className="clinical-program-sub">Program summary</span>
                        <div className="clinical-program-summary-line">Assigned rooms: <strong>{summary.assignedCount}</strong></div>
                        {volumeSummary && <div className="clinical-program-summary-line">Planning volumes: <strong>{volumeSummary.planningVolumes}</strong> (draft {volumeSummary.draft} · locked {volumeSummary.locked})</div>}
                        {validationSummary && validationSummary.planningVolumes > 0 && (
                            <div className={validationSummary.needsAttention > 0 ? 'clinical-program-summary-line muted' : 'clinical-program-summary-line ok'}>
                                Valid: <strong>{validationSummary.valid}</strong>
                                {validationSummary.needsAttention > 0 && <> · Needs attention: <strong>{validationSummary.needsAttention}</strong></>}
                                {validationSummary.notEvaluated > 0 && <> · Not evaluated: <strong>{validationSummary.notEvaluated}</strong></>}
                            </div>
                        )}
                        {summary.byFn.length === 0 && <div className="clinical-program-summary-line muted">No clinical functions assigned yet.</div>}
                        {summary.byFn.map(([fn, n]) => (
                            <div key={fn} className="clinical-program-summary-line">{FUNCTION_LABEL[fn]}: <strong>{n}</strong></div>
                        ))}
                        {completeness.missing.length > 0 ? (
                            <div className="clinical-program-summary-line muted">Three-room proof missing: {completeness.missing.map((f) => FUNCTION_LABEL[f]).join(', ')}</div>
                        ) : summary.assignedCount > 0 ? (
                            <div className="clinical-program-summary-line ok">Three-room proof complete (Uptake + Injection + PET/CT). PET department NOT complete — Radiopharmacy deferred.</div>
                        ) : null}
                    </div>

                    <div className="clinical-program-row">
                        <span className="clinical-program-sub">Room volume (view-only)</span>
                        <button
                            type="button"
                            className={showRoomVolume ? 'clinical-program-btn primary' : 'clinical-program-btn'}
                            onClick={() => void import('./spatialAssetOverlay').then((o) => o.setClinicalProgramShowRoomVolume(!showRoomVolume))}
                        >{showRoomVolume ? 'Hide Room Volume' : 'Show Room Volume'}</button>
                    </div>

                    {note && <div className="clinical-program-note">{note}</div>}
                </>
            )}
        </div>
    )
}

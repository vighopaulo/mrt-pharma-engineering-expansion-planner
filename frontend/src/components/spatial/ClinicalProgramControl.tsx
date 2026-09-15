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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CLINICAL_FUNCTIONS, type ClinicalFunction, type ClinicalProgramAssignment } from './clinicalProgram'
import type { CameraMode } from './cameraNav'
import {
    CANONICAL_CYCLOTRON_MODELS,
    CANONICAL_GENERATOR_MODELS,
    CANONICAL_SCANNER_MODELS,
    CANONICAL_MRT_FACILITY_MODELS,
    type CanonicalEquipmentModel,
} from './canonicalEquipmentCatalog'
import type { EquipmentAssetInstance } from './equipmentInstance'
import type { EquipmentValidationState, EquipmentCrosswalkReadout } from './equipmentValidation'

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

// Build 1B candidate acceptance tier -> product label + badge class.
const TIER_LABEL: Record<import('./clinicalRoomCandidate').CandidateTier, string> = {
    RECOMMENDED: 'Recommended',
    SUITABLE: 'Suitable',
    NEEDS_REVIEW: 'Needs review',
    REJECTED: 'Rejected',
}
const TIER_BADGE_CLASS: Record<import('./clinicalRoomCandidate').CandidateTier, string> = {
    RECOMMENDED: 'ok',
    SUITABLE: 'suitable',
    NEEDS_REVIEW: 'warn',
    REJECTED: 'reject',
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
    // Build 1B: canonical equipment binding state.
    const [equipment, setEquipment] = useState<readonly EquipmentAssetInstance[]>([])
    const [equipmentValidations, setEquipmentValidations] = useState<Record<string, EquipmentValidationState>>({})
    const [equipmentCrosswalks, setEquipmentCrosswalks] = useState<Record<string, EquipmentCrosswalkReadout>>({})
    const [pendingEquipmentId, setPendingEquipmentId] = useState<string>('')
    const [showEquipment, setShowEquipment] = useState(true)
    const [selectedEquipmentId, setSelectedEquipmentId] = useState<string | undefined>(undefined)
    // Build 1A.1: honest room-discovery lifecycle (never a false READY-zero).
    const [discoveryStatus, setDiscoveryStatus] = useState<'NOT_BOUND' | 'LOADING' | 'READY' | 'ERROR'>('NOT_BOUND')
    const [selectorLabel, setSelectorLabel] = useState<string>('Open the model to discover rooms')
    // B1B-MA-03B: the authoritative selected room resolved from the IMMUTABLE base
    // discovery (independent of the storey filter), so a deliberately-selected room
    // stays fully usable (detail/assignment/volume/equipment) even when the active
    // storey chip would filter it out of the dropdown option list. `outsideFilter`
    // drives a non-destructive "outside current storey filter" hint + a rendered
    // option for the selected room — it NEVER clears the selection.
    const [selectedRoomFallback, setSelectedRoomFallback] = useState<RoomOption | undefined>(undefined)
    const [selectedRoomOutsideFilter, setSelectedRoomOutsideFilter] = useState(false)
    // B1B-MA-03A: the active viewport camera mode + a PRESENTATION-ONLY collapse of
    // the Clinical Program panel. Entering Walkthrough auto-collapses the panel so
    // it no longer obstructs the 3D scene, leaving a compact reopen chip; returning
    // to Planning auto-expands it. Collapse NEVER resets the selected room, storey
    // filter, assignments, planning volumes, equipment, candidates or summary —
    // panel VISIBILITY is strictly separate from FEATURE STATE. The user can also
    // reopen it while still in Walkthrough (inspect the model, return to context).
    const [cameraMode, setCameraMode] = useState<CameraMode>('PLANNING')
    const [panelCollapsed, setPanelCollapsed] = useState(false)
    const prevCameraModeRef = useRef<CameraMode>('PLANNING')
    // Build 1B spatial correction: clinical-room CANDIDATE DISCOVERY + re-parenting.
    const [candidateFunction, setCandidateFunction] = useState<ClinicalFunction>('UPTAKE_ROOM')
    const [candidates, setCandidates] = useState<readonly import('./clinicalRoomCandidate').RankedRoomCandidate[]>([])
    const [candidateSummary, setCandidateSummary] = useState<import('./clinicalRoomCandidate').CandidateRankingSummary | null>(null)
    const [candidateVocab, setCandidateVocab] = useState<import('./clinicalRoomCandidate').DiscoveredSemanticVocabulary | null>(null)
    const [candidateBusy, setCandidateBusy] = useState(false)
    const [selectedCandidateId, setSelectedCandidateId] = useState<string | undefined>(undefined)
    const [reparentOverride, setReparentOverride] = useState(false)

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
                // Build 1B: reflect equipment state + recompute per-instance
                // validation/crosswalk using THIS (same-module) overlay handle, so
                // the async validation path never depends on a second dynamic import.
                // Wrapped defensively so an overlay/mock that predates the equipment
                // surface (e.g. Build 1A UI test mocks, where accessing an undefined
                // mock export throws) never breaks the clinical-program sync.
                try {
                    const eqList = o.getEquipmentInstances()
                    setEquipment(eqList)
                    setShowEquipment(o.getShowEquipment())
                    setSelectedEquipmentId(o.getSelectedEquipmentId())
                    void (async () => {
                        const vals: Record<string, EquipmentValidationState> = {}
                        const xws: Record<string, EquipmentCrosswalkReadout> = {}
                        for (const e of eqList) {
                            const v = await o.getEquipmentValidation(e.id)
                            if (v) vals[e.id] = v
                            const x = await o.getEquipmentCrosswalk(e.id)
                            if (x) xws[e.id] = x
                        }
                        if (!cancelled) { setEquipmentValidations(vals); setEquipmentCrosswalks(xws) }
                    })().catch(() => { /* equipment surface unavailable */ })
                } catch { /* overlay/mock without the equipment surface */ }
                setEnabled(snap.enabled)
                setActiveStoreyId(snap.activeStoreyId)
                setSelectedSpaceId(snap.selectedSpaceId)
                setAssignments(snap.assignments)
                setShowRoomVolume(snap.showRoomVolume)
                // B1B-MA-03A: surface the active camera mode so the panel-collapse
                // transition effect can auto-collapse on Walkthrough entry. This is a
                // presentation signal only — it does not touch selection/feature state.
                setCameraMode(snap.cameraMode)
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
                // B1B-MA-03B: the authoritative selected room is ONE stable BIM id
                // (programState.selectedSpaceId). The storey chip is a FILTER on the
                // dropdown OPTIONS only — it is NOT a selection authority. A selection
                // made deliberately (dropdown / 2D plan / candidate accept / direct BIM)
                // must PERSIST across every program notification: hover samples, walker
                // camera samples, candidate refresh, footprint extraction, storey-chip
                // changes and Walkthrough entry all call notifyProgram(). The previous
                // out-of-filter auto-clear here silently overwrote a valid selection
                // (e.g. Radiopharmacy 2C17 on Second Floor being cleared the instant it
                // was selected, or when hovering a corridor). It is removed. The
                // selected room is still resolved authoritatively (see selectedRoom)
                // and rendered in the dropdown even when outside the active filter; an
                // "outside current storey filter" hint is shown instead of clearing.
                setSelectedRoomOutsideFilter(!!snap.selectedSpaceId && o.isSelectedRoomOutsideActiveStorey())
                setSelectedRoomFallback(
                    // Defensive: getDiscoveredRoomById is the authoritative base-discovery
                    // lookup; older overlay mocks may predate it — fall back to undefined
                    // (the in-filter option resolution still covers the common case).
                    snap.selectedSpaceId && typeof o.getDiscoveredRoomById === 'function'
                        ? (() => {
                            const rec = o.getDiscoveredRoomById(snap.selectedSpaceId)
                            return rec ? { bimSpaceId: rec.bimSpaceId, originalBimLabel: rec.originalBimLabel || 'Unnamed space', storeyLabel: rec.storeyId } : undefined
                        })()
                        : undefined,
                )
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

    // B1B-MA-03A: auto-collapse the panel on the PLANNING/BIRDS_EYE -> WALKTHROUGH
    // TRANSITION only (not on every notification while already in walkthrough, so a
    // user who reopens the panel mid-walkthrough is not fought). Returning to
    // PLANNING auto-expands it. This is a presentation transition: it flips
    // EVI-MA-02A root-cause fix: arm the bounded direct-manipulation tool whenever
    // CLINICAL EQUIPMENT exists — independent of the legacy Asset Library (which
    // only armed the tool when a legacy AssetInstance was placed, so cyclotron-only
    // scenes had NO tool installed and right-click never reached the equipment
    // handlers). Idempotent + IDLE-gated; re-arms after the interaction returns to
    // IDLE (e.g. after a placement/move completes).
    useEffect(() => {
        if (equipment.length === 0) return
        void import('./spatialAssetOverlay').then((o) => o.ensureDirectManipulationReady()).catch(() => false)
    }, [equipment.length])

    // panelCollapsed and nothing else — the authoritative selection, storey filter,
    // assignments, volumes, equipment, candidates and summary are all untouched.
    useEffect(() => {
        const prev = prevCameraModeRef.current
        if (prev !== 'WALKTHROUGH' && cameraMode === 'WALKTHROUGH') setPanelCollapsed(true)
        else if (prev === 'WALKTHROUGH' && cameraMode !== 'WALKTHROUGH') setPanelCollapsed(false)
        prevCameraModeRef.current = cameraMode
    }, [cameraMode])

    // B1B-MA-03A: while in WALKTHROUGH, a pointer-down OUTSIDE the panel collapses
    // it (so the planning UI gets out of the way for model inspection). This mirrors
    // the CameraModeControl walkthrough-card pattern: a WINDOW listener that tests
    // the event target's ancestry — there is NO full-screen invisible blocker, so
    // 3D-scene pointer input is never intercepted. Collapsing is presentation only;
    // it NEVER clears the selection or any other feature state. Not armed in Planning
    // (the panel is the primary programming surface there).
    useEffect(() => {
        if (cameraMode !== 'WALKTHROUGH') return
        if (panelCollapsed) return
        const onOutsidePointerDown = (e: PointerEvent) => {
            const target = e.target as HTMLElement | null
            if (target && !target.closest('.clinical-program')) setPanelCollapsed(true)
        }
        window.addEventListener('pointerdown', onOutsidePointerDown)
        return () => window.removeEventListener('pointerdown', onOutsidePointerDown)
    }, [cameraMode, panelCollapsed])

    // B1B-MA-03B: resolve the selected room authoritatively. Prefer the in-filter
    // option, but fall back to the base-discovery record when the active storey
    // chip filters the selected room out of the dropdown list. This keeps the
    // room detail / assignment / volume / equipment UI intact for the persistent
    // selection instead of collapsing to "no room" the way the old auto-clear did.
    const selectedRoom = useMemo(
        () => rooms.find((r) => r.bimSpaceId === selectedSpaceId)
            ?? (selectedRoomFallback && selectedRoomFallback.bimSpaceId === selectedSpaceId ? selectedRoomFallback : undefined),
        [rooms, selectedSpaceId, selectedRoomFallback],
    )
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

    // --- Build 1B: clinical-room CANDIDATE DISCOVERY + re-parenting --------
    // Find ranked, explainable candidate rooms for the chosen function. The
    // engine is pure; the overlay wires lazy exact-mesh extraction for the
    // shortlist. Never guesses/hardcodes room ids — it ranks discovered rooms.
    const findCandidates = useCallback(() => {
        setCandidateBusy(true)
        setSelectedCandidateId(undefined)
        setReparentOverride(false)
        void import('./spatialAssetOverlay').then(async (o) => {
            try {
                const r = await o.findClinicalRoomCandidates({ clinicalFunction: candidateFunction, storeyId: activeStoreyId, limit: 25 })
                setCandidates(r.candidates)
                setCandidateSummary(r.summary)
                setCandidateVocab(r.vocabulary)
                setNote(r.candidates.length === 0
                    ? 'No candidate rooms found for this function on the current storey.'
                    : `${r.summary.recommendedCount} recommended candidate room(s) for ${FUNCTION_LABEL[candidateFunction]}.`)
            } finally { setCandidateBusy(false) }
        }).catch(() => setCandidateBusy(false))
    }, [candidateFunction, activeStoreyId])

    // Select a candidate: highlight it as the program's selected space + fit the
    // 3D view to that room (candidate preview). VIEW-ONLY camera move.
    const previewCandidate = useCallback((bimSpaceId: string) => {
        setSelectedCandidateId(bimSpaceId)
        setReparentOverride(false)
        void import('./spatialAssetOverlay').then(async (o) => {
            o.setClinicalProgramSelectedSpace(bimSpaceId)
            await o.fitViewToClinicalRoom(bimSpaceId).catch(() => false)
        })
    }, [])

    // USE THIS ROOM — re-parent the chosen function onto the selected candidate.
    const useCandidateRoom = useCallback((bimSpaceId: string) => {
        void import('./spatialAssetOverlay').then(async (o) => {
            const r = await o.reparentClinicalFunction({ clinicalFunction: candidateFunction, newParentBimSpaceId: bimSpaceId, overrideAccepted: reparentOverride })
            if (!r.ok) {
                if (r.blockCode === 'OVERRIDE_REQUIRED') {
                    setNote(`${r.reason} — tick "override" to proceed anyway.`)
                } else {
                    setNote(`Cannot re-parent: ${r.reason}`)
                }
                return
            }
            setNote(`Re-parented ${FUNCTION_LABEL[candidateFunction]} onto the selected room. New volume regenerated from its geometry (containment: ${r.containment}).`)
            setCandidates([])
            setCandidateSummary(null)
            setSelectedCandidateId(undefined)
            setReparentOverride(false)
        })
    }, [candidateFunction, reparentOverride])

    // Build 1B Problem C: ENTER WALKTHROUGH HERE — targeted safe spawn for a
    // specific room (collision-active; honest failure, never a silent fallback).
    const enterWalkthroughHere = useCallback((bimSpaceId: string) => {
        void import('./spatialAssetOverlay').then(async (o) => {
            const r = await o.enterWalkthroughAtClinicalRoom({ bimSpaceId })
            setNote(r.ok
                ? `Entered walkthrough at this room (spawn: ${r.provenance}).`
                : `Cannot enter walkthrough here: ${r.reason}`)
        })
    }, [])

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

    // --- Build 1B equipment handlers --------------------------------------
    const placeEquipment = useCallback(() => {
        if (!selectedRoom || !pendingEquipmentId) return
        void import('./spatialAssetOverlay').then(async (o) => {
            const r = await o.placeEquipmentInParent({ canonicalEquipmentId: pendingEquipmentId, parentBimSpaceId: selectedRoom.bimSpaceId })
            if (!r.ok) {
                // EVI-MA-02A §12A — spatial exclusivity: an overlapping placement
                // is rejected outright (nothing created), naming the conflict.
                if (r.reason === 'EQUIPMENT_COLLISION') {
                    setNote(`Cannot place equipment here. Its volume intersects ${r.conflictLabel ?? 'existing equipment'}. Move or delete the existing equipment first.`)
                } else {
                    setNote(`Could not place equipment: ${r.reason}`)
                }
                return
            }
            // §9 — surface the NEW instance identity (now selected). If an
            // identical canonical model already exists in this room, add a
            // NON-BLOCKING note (the duplicate is neither merged nor rejected).
            const dupNote = r.duplicateInRoom ? ` Note: another ${r.displayLabel ?? pendingEquipmentId} already exists in this room.` : ''
            setNote(`Placed ${r.displayLabel ?? pendingEquipmentId} in ${selectedRoom.originalBimLabel} (now selected).${dupNote}`)
        })
    }, [selectedRoom, pendingEquipmentId])

    const editEquipmentPlacement = useCallback((id: string, patch: Partial<{ centerX: number; centerY: number; yawDeg: number; width: number; depth: number; height: number }>) => {
        void import('./spatialAssetOverlay').then((o) => {
            const e = o.getEquipmentInstance(id)
            if (!e) return
            const p = e.placement
            const next = {
                ...p,
                centerX: patch.centerX ?? p.centerX,
                centerY: patch.centerY ?? p.centerY,
                width: patch.width ?? p.width,
                depth: patch.depth ?? p.depth,
                height: patch.height ?? p.height,
                yaw: patch.yawDeg !== undefined ? (patch.yawDeg * Math.PI) / 180 : p.yaw,
            }
            const r = o.updateEquipmentPlacement(id, next)
            if (!r.ok) {
                // EVI-MA-02A §12D — a pose edit that would overlap another
                // equipment instance is rejected; the last valid pose is kept.
                if (r.reason === 'EQUIPMENT_COLLISION') {
                    const conflict = r.conflictEquipmentId ? o.getEquipmentInstance(r.conflictEquipmentId) : undefined
                    setNote(`Move rejected: equipment volume would intersect ${conflict?.displayLabel ?? 'existing equipment'}. Position kept.`)
                } else if (r.reason === 'LOCKED') {
                    setNote('Move rejected: equipment is locked. Unlock first.')
                }
            }
        })
    }, [])

    const selectEquipmentRow = useCallback((id: string) => {
        void import('./spatialAssetOverlay').then((o) => o.selectEquipment(id === selectedEquipmentId ? undefined : id))
    }, [selectedEquipmentId])

    // EVI-MA-01 — Fit to Equipment: select the instance and frame the Bentley
    // viewport on its recognizable geometry / envelope. View-only (no re-parent,
    // no pose change). Surfaces an honest failure instead of pretending.
    const fitToEquipmentRow = useCallback((id: string) => {
        void import('./spatialAssetOverlay').then(async (o) => {
            const r = await o.fitViewToEquipment(id)
            setNote(r.ok
                ? 'Framed the equipment in the 3D view.'
                : r.reason === 'VISUAL_NOT_AVAILABLE'
                    ? 'VISUAL_NOT_AVAILABLE: no recognizable geometry resolved for this equipment.'
                    : `Could not fit to equipment: ${r.reason}`)
        })
    }, [])

    const lockEquipmentRow = useCallback((id: string) => {
        void import('./spatialAssetOverlay').then(async (o) => {
            const r = await o.lockEquipment(id)
            setNote(r.ok ? 'Equipment LOCKED.' : `Cannot lock: ${r.reason}`)
        })
    }, [])

    const unlockEquipmentRow = useCallback((id: string) => {
        void import('./spatialAssetOverlay').then((o) => o.unlockEquipment(id))
    }, [])

    const restoreEquipmentRow = useCallback((id: string) => {
        void import('./spatialAssetOverlay').then(async (o) => {
            const r = await o.restoreEquipmentValidPosition(id)
            setNote(r.ok ? (r.source === 'LAST_KNOWN_VALID' ? 'Restored last valid equipment position.' : 'No prior valid position — restored a parent-derived placement.') : `Cannot restore: ${r.reason}`)
        })
    }, [])

    const resetEquipmentRow = useCallback((id: string) => {
        void import('./spatialAssetOverlay').then(async (o) => {
            const r = await o.resetEquipmentToParentDerived(id)
            setNote(r.ok ? 'Equipment reset to a fresh parent-derived placement.' : `Cannot reset: ${r.reason}`)
        })
    }, [])

    const toggleEquipmentVisibility = useCallback((id: string, hidden: boolean) => {
        void import('./spatialAssetOverlay').then((o) => o.setEquipmentVisibility(id, hidden))
    }, [])

    const deleteEquipmentRow = useCallback((id: string) => {
        void import('./spatialAssetOverlay').then((o) => {
            const r = o.deleteEquipment(id)
            setNote(r.ok ? 'Equipment deleted (BIM room unchanged).' : `Cannot delete: ${r.reason}`)
        })
    }, [])

    const toggleShowEquipment = useCallback(() => {
        void import('./spatialAssetOverlay').then((o) => o.setShowEquipment(!showEquipment))
    }, [showEquipment])

    const summary = useMemo(() => {
        const active = assignments.filter((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')
        const byFn = new Map<ClinicalFunction, number>()
        for (const a of active) byFn.set(a.clinicalFunction, (byFn.get(a.clinicalFunction) ?? 0) + 1)
        return { assignedCount: active.length, byFn: [...byFn.entries()] }
    }, [assignments])

    // Build 2A three-room proof: Uptake + Injection + PET/CT.
    const completeness = useMemo(() => {
        const required: ClinicalFunction[] = ['UPTAKE_ROOM', 'INJECTION_ROOM', 'PET_CT_SCANNER_ROOM']
        const present = new Set(assignments.map((a) => a.clinicalFunction))
        const missing = required.filter((f) => !present.has(f))
        return { missing, threeRoomProofComplete: missing.length === 0 }
    }, [assignments])

    // Build 1B: complete basic PET clinical program (adds Radiopharmacy). The
    // required-vs-present summary is informational; it never auto-adds a room.
    const petDepartment = useMemo(() => {
        const required: ClinicalFunction[] = ['RADIOPHARMACY', 'INJECTION_ROOM', 'UPTAKE_ROOM', 'PET_CT_SCANNER_ROOM']
        const present = new Set(assignments.map((a) => a.clinicalFunction))
        const missing = required.filter((f) => !present.has(f))
        return { required, missing, complete: missing.length === 0 }
    }, [assignments])

    return (
        <div className={panelCollapsed ? 'clinical-program collapsed' : 'clinical-program'} aria-label="MRT Pharma clinical program">
            {/* B1B-MA-03A: when collapsed, the panel shows ONLY a compact reopen
                chip. All feature state (selection, storey filter, assignments,
                volumes, equipment, candidates, summary) is preserved — reopening
                restores the exact same room context. */}
            {enabled && panelCollapsed ? (
                <button
                    type="button"
                    className="clinical-program-reopen"
                    data-testid="clinical-program-reopen"
                    aria-expanded={false}
                    title="Show the Clinical Program panel"
                    onClick={() => setPanelCollapsed(false)}
                >CLINICAL PROGRAM ▸{selectedRoom ? ` · ${(currentAssignment?.mrtDisplayName ?? selectedRoom.originalBimLabel)}` : ''}</button>
            ) : (
                <>
                    <div className="clinical-program-head">
                        <span className="clinical-program-caption">CLINICAL PROGRAM</span>
                        <button
                            type="button"
                            className={enabled ? 'clinical-program-toggle active' : 'clinical-program-toggle'}
                            aria-pressed={enabled}
                            onClick={toggleEnabled}
                        >{enabled ? 'On' : 'Off'}</button>
                        {enabled && (
                            <button
                                type="button"
                                className="clinical-program-collapse"
                                data-testid="clinical-program-collapse"
                                aria-label="Collapse Clinical Program panel"
                                title="Collapse panel (selection is kept)"
                                onClick={() => setPanelCollapsed(true)}
                            >×</button>
                        )}
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
                                    {/* B1B-MA-03B: keep the authoritative selected room selectable
                                even when the active storey chip filters it out of the list,
                                so the <select> reflects the real selection instead of
                                falling back to the blank placeholder. */}
                                    {selectedRoomOutsideFilter && selectedRoom && !rooms.some((r) => r.bimSpaceId === selectedRoom.bimSpaceId) && (() => {
                                        const a = assignments.find((x) => x.bimSpaceId === selectedRoom.bimSpaceId && x.clinicalFunction !== 'UNASSIGNED_EXISTING')
                                        const base = a ? `${a.mrtDisplayName} — ${selectedRoom.originalBimLabel}` : selectedRoom.originalBimLabel
                                        return <option key={selectedRoom.bimSpaceId} value={selectedRoom.bimSpaceId}>{`${base} (outside current storey filter)`}</option>
                                    })()}
                                </select>
                                {selectedRoomOutsideFilter && (
                                    <div className="clinical-program-hint" data-testid="selected-room-outside-filter-hint">
                                        Selected room is outside the current storey filter. It stays selected — switch the storey chip to see it in the list.
                                    </div>
                                )}
                            </div>

                            {/* ===== Build 1B — CLINICAL ROOM CANDIDATE DISCOVERY =====
                        Placed AFTER the room selector so the BIM-room combobox stays
                        the FIRST combobox (preserves existing equipment/1A.4 UI tests
                        that address comboboxes by index). */}
                            <div className="clinical-program-candidates" aria-label="Clinical room candidate discovery">
                                <span className="clinical-program-sub">Find candidate rooms</span>
                                <div className="clinical-program-hint">Pick a clinical function, then find defensible enclosed rooms ranked by semantic + geometric fit. Corridors, stairs, shafts and service space are flagged; unknown rooms are allowed. Geometric containment is judged separately from clinical suitability.</div>
                                <div className="clinical-program-row">
                                    <select className="clinical-program-select" value={candidateFunction} onChange={(e) => setCandidateFunction(e.target.value as ClinicalFunction)} aria-label="Candidate function">
                                        {(['UPTAKE_ROOM', 'INJECTION_ROOM', 'PET_CT_SCANNER_ROOM', 'RADIOPHARMACY'] as ClinicalFunction[]).map((f) => (
                                            <option key={f} value={f}>{FUNCTION_LABEL[f]}</option>
                                        ))}
                                    </select>
                                    <button type="button" className="clinical-program-btn primary" onClick={findCandidates} disabled={candidateBusy || discoveryStatus !== 'READY'}>{candidateBusy ? 'Finding…' : 'Find Candidate Rooms'}</button>
                                </div>

                                {candidateSummary && (
                                    <div className="clinical-program-summary-line muted">
                                        {candidateSummary.totalConsidered} considered · {candidateSummary.tierCounts.RECOMMENDED} recommended · {candidateSummary.tierCounts.SUITABLE} suitable · {candidateSummary.tierCounts.NEEDS_REVIEW} needs review · {candidateSummary.tierCounts.REJECTED} rejected
                                    </div>
                                )}
                                {candidateVocab && (
                                    <div className="clinical-program-summary-line muted">
                                        Discovered room kinds: {Object.entries(candidateVocab.kindCounts).filter(([, n]) => n > 0).map(([k, n]) => `${k}=${n}`).join(' · ')}
                                    </div>
                                )}

                                {candidates.length > 0 && (
                                    <div
                                        className="clinical-program-candidate-list"
                                        role="listbox"
                                        aria-label="Candidate rooms (scrollable)"
                                        data-testid="candidate-results-region"
                                    >
                                        {candidates.map((c) => {
                                            const tierClass = TIER_BADGE_CLASS[c.tier]
                                            const tierLabel = TIER_LABEL[c.tier]
                                            const storeyLabel = storeys.find((s) => s.id === c.storeyId)?.label ?? c.storeyId ?? '—'
                                            const areaText = c.eligibility.metrics.floorAreaM2 !== undefined
                                                ? `${c.eligibility.metrics.floorAreaM2.toFixed(1)} m²`
                                                : 'area pending'
                                            const authority = c.eligibility.geometryQuality === 'EXACT_SPACE_GEOMETRY' ? 'exact geometry' : 'approx. geometry'
                                            const isSelected = selectedCandidateId === c.bimSpaceId
                                            const needsOverride = c.semantic.rejectedByDefault || !c.eligibility.eligible
                                            return (
                                                <div
                                                    key={c.bimSpaceId}
                                                    role="option"
                                                    aria-selected={isSelected}
                                                    className={`clinical-program-candidate compact${isSelected ? ' selected' : ''}`}
                                                    data-testid="candidate-card"
                                                    data-tier={c.tier}
                                                >
                                                    <div className="clinical-program-candidate-head">
                                                        <button type="button" className="clinical-program-candidate-title" onClick={() => setSelectedCandidateId(isSelected ? undefined : c.bimSpaceId)} title="Show / hide the ranking reasons for this room">
                                                            {c.mrtDisplayName ? `${c.mrtDisplayName} — ` : ''}{c.originalBimLabel || 'Unnamed space'}
                                                        </button>
                                                        <span className={`clinical-program-candidate-badge ${tierClass}`} data-testid="candidate-tier-badge">{tierLabel}</span>
                                                    </div>
                                                    <div className="clinical-program-candidate-meta muted">
                                                        <span>Storey {storeyLabel}</span>
                                                        <span>Suitability {(c.clinicalSuitabilityScore * 100).toFixed(0)}%</span>
                                                        <span>Fit {(c.geometricFitScore * 100).toFixed(0)}%</span>
                                                        <span>{areaText}</span>
                                                        <span>{authority}</span>
                                                        {c.isCurrentParent && <span>current parent</span>}
                                                    </div>
                                                    {isSelected && (
                                                        <ul className="clinical-program-candidate-reasons">
                                                            {c.reasons.map((reason, i) => <li key={i}>{reason}</li>)}
                                                        </ul>
                                                    )}
                                                    {isSelected && needsOverride && (
                                                        <label className="clinical-program-candidate-override">
                                                            <input type="checkbox" checked={reparentOverride} onChange={(e) => setReparentOverride(e.target.checked)} />
                                                            <span>Override compatibility warning (this space is genuinely an enclosed room)</span>
                                                        </label>
                                                    )}
                                                    {/* Actions are ALWAYS reachable at the bottom of each compact card
                                                (the list itself scrolls). Fit to Room + Enter Walkthrough Here
                                                are INSPECTION-ONLY (never re-parent); only Use This Room re-parents. */}
                                                    <div className="clinical-program-actions">
                                                        <button type="button" className="clinical-program-btn" onClick={() => previewCandidate(c.bimSpaceId)} title="Inspection only — highlights + fits the 3D view to this exact room. Does NOT re-parent.">Fit to Room</button>
                                                        <button type="button" className="clinical-program-btn" onClick={() => enterWalkthroughHere(c.bimSpaceId)} title="Inspection only — enters walkthrough at a safe point inside this room. Does NOT re-parent.">Enter Walkthrough Here</button>
                                                        <button type="button" className="clinical-program-btn primary" onClick={() => useCandidateRoom(c.bimSpaceId)} disabled={needsOverride && !(isSelected && reparentOverride)} title="Confirms the re-parent onto this room.">Use This Room</button>
                                                    </div>
                                                </div>
                                            )
                                        })}
                                    </div>
                                )}
                            </div>

                            {selectedRoom && (
                                <div className="clinical-program-editor">
                                    <div className="clinical-program-field"><span>Original BIM room</span><strong>{selectedRoom.originalBimLabel}</strong></div>
                                    <div className="clinical-program-field"><span>Storey</span><strong>{storeys.find((s) => s.id === (activeStoreyId))?.label ?? '—'}</strong></div>
                                    <div className="clinical-program-field"><span>Current function</span><strong>{currentAssignment ? FUNCTION_LABEL[currentAssignment.clinicalFunction] : 'Unassigned (existing)'}</strong></div>
                                    {geometryQuality && <div className="clinical-program-field"><span>Spatial geometry</span><strong>{geometryQuality}</strong></div>}

                                    <div className="clinical-program-actions">
                                        <button type="button" className="clinical-program-btn" onClick={() => enterWalkthroughHere(selectedRoom.bimSpaceId)} title="Enter walkthrough at a safe point inside this room (room-geometry-derived spawn)">Enter Walkthrough Here</button>
                                    </div>

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
                                    <div className="clinical-program-summary-line ok">Three-room proof complete (Uptake + Injection + PET/CT).</div>
                                ) : null}
                                {/* Build 1B: full basic PET clinical program (required vs present). */}
                                {petDepartment.complete ? (
                                    <div className="clinical-program-summary-line ok">Basic PET clinical program complete (Radiopharmacy + Injection + Uptake + PET/CT).</div>
                                ) : (
                                    <div className="clinical-program-summary-line muted">PET program missing: {petDepartment.missing.map((f) => FUNCTION_LABEL[f]).join(', ')}</div>
                                )}
                            </div>

                            {/* ============ Build 1B — CANONICAL EQUIPMENT BINDING ============ */}
                            <div className="equipment-section" aria-label="MRT Pharma equipment binding">
                                <div className="clinical-program-head">
                                    <h4>EQUIPMENT (canonical catalog)</h4>
                                    <button type="button" className={showEquipment ? 'clinical-program-btn primary' : 'clinical-program-btn'} onClick={toggleShowEquipment}>{showEquipment ? 'Visible' : 'Hidden'}</button>
                                </div>
                                <div className="clinical-program-hint">Bind canonical catalog equipment to the selected BIM room. Envelopes are calibrated where the catalog has physical dimensions; otherwise a labelled proxy. Identity, capacity, production, and cost stay in the backend catalog (by reference).</div>

                                <div className="clinical-program-row">
                                    <span className="clinical-program-sub">Equipment model</span>
                                    <select className="clinical-program-select" value={pendingEquipmentId} onChange={(e) => setPendingEquipmentId(e.target.value)}>
                                        <option value="">Select a canonical model…</option>
                                        <optgroup label="Cyclotron">
                                            {CANONICAL_CYCLOTRON_MODELS.map((m: CanonicalEquipmentModel) => <option key={m.catalogModelId} value={m.catalogModelId}>{m.manufacturer} {m.model}{m.envelope.provenance === 'GENERIC_ENGINEERING_PLACEHOLDER' ? ' (proxy env.)' : ''}</option>)}
                                        </optgroup>
                                        <optgroup label="Generator">
                                            {CANONICAL_GENERATOR_MODELS.map((m) => <option key={m.catalogModelId} value={m.catalogModelId}>{m.manufacturer} {m.model} (proxy env.)</option>)}
                                        </optgroup>
                                        <optgroup label="Scanner">
                                            {CANONICAL_SCANNER_MODELS.map((m) => <option key={m.catalogModelId} value={m.catalogModelId}>{m.manufacturer} {m.model} (proxy env.)</option>)}
                                        </optgroup>
                                    </select>
                                </div>
                                <div className="clinical-program-actions">
                                    <button type="button" className="clinical-program-btn primary" onClick={placeEquipment} disabled={!selectedRoom || !pendingEquipmentId} title={!selectedRoom ? 'Select a BIM room first' : 'Place in the selected room'}>Place in Selected Room</button>
                                </div>
                                <div className="clinical-program-summary-line muted">
                                    MRT facility classes (by reference): {CANONICAL_MRT_FACILITY_MODELS.map((m) => m.displayName).join(' · ')}
                                </div>

                                {equipment.length === 0 ? (
                                    <div className="clinical-program-summary-line muted">No equipment placed yet.</div>
                                ) : (
                                    <div className="equipment-list">
                                        {equipment.map((e) => {
                                            const v = equipmentValidations[e.id]
                                            const xw = equipmentCrosswalks[e.id]
                                            const status = v?.containmentStatus ?? 'NOT_EVALUATED'
                                            const statusClass = status === 'PASS' ? 'pass' : status === 'FAIL' ? 'fail' : 'not-evaluated'
                                            const yawDeg = (e.placement.yaw * 180) / Math.PI
                                            return (
                                                <div key={e.id} className={selectedEquipmentId === e.id ? 'equipment-row selected' : 'equipment-row'}>
                                                    <div className="equipment-row-header">
                                                        <button type="button" className="equipment-row-title" onClick={() => selectEquipmentRow(e.id)} title="Select / deselect">{e.displayLabel}</button>
                                                        <button type="button" className="clinical-program-btn" onClick={() => fitToEquipmentRow(e.id)} title="Select this equipment and frame the 3D view on its recognizable geometry (view-only; does not move it).">Fit to Equipment</button>
                                                        <span className={`equipment-status ${statusClass}`}>{status === 'PASS' ? 'Inside room' : status === 'FAIL' ? 'Outside room' : 'Not evaluated'}</span>
                                                    </div>
                                                    <div className="clinical-program-summary-line muted">{e.canonicalClass} · room {e.parentBimSpaceId} · {e.lifecycleState} · {e.hidden ? 'Hidden' : 'Visible'}{e.placement.envelopeProvenance === 'GENERIC_ENGINEERING_PLACEHOLDER' ? ' · proxy envelope' : ' · calibrated envelope'}</div>

                                                    {/* Editable placement (disabled when LOCKED). */}
                                                    <div className="clinical-program-grid">
                                                        {([['centerX', 'X'], ['centerY', 'Y'], ['yawDeg', 'Yaw°']] as const).map(([k, lbl]) => {
                                                            const val = k === 'yawDeg' ? Number(yawDeg.toFixed(1)) : Number((e.placement[k] as number).toFixed(2))
                                                            return (
                                                                <label key={k} className="clinical-program-num">
                                                                    <span>{lbl}</span>
                                                                    <input
                                                                        type="number"
                                                                        step="0.1"
                                                                        className="clinical-program-input"
                                                                        value={val}
                                                                        disabled={e.lifecycleState === 'LOCKED'}
                                                                        onChange={(ev) => editEquipmentPlacement(e.id, { [k]: Number(ev.target.value) })}
                                                                    />
                                                                </label>
                                                            )
                                                        })}
                                                    </div>

                                                    {/* Validation warning (identifies equipment + room; not color-only). */}
                                                    {v?.warningCode === 'OUTSIDE_PARENT' && (
                                                        <div className="equipment-warning" role="alert">
                                                            <strong>⚠ {v.warningMessage}</strong>
                                                            <div className="clinical-program-summary-line muted">{v.technicalDetail}</div>
                                                        </div>
                                                    )}
                                                    {(v?.warningCode === 'NOT_EVALUATED' || v?.warningCode === 'PARENT_GEOMETRY_UNAVAILABLE') && (
                                                        <div className="clinical-program-summary-line muted">{v.warningMessage}</div>
                                                    )}
                                                    {v?.containmentStatus === 'PASS' && (
                                                        <div className="clinical-program-summary-line ok">Envelope fully inside its parent room.{v.approximateParent ? ' (parent is a range approximation)' : ''}</div>
                                                    )}

                                                    <div className="equipment-controls">
                                                        {e.lifecycleState === 'DRAFT'
                                                            ? <button type="button" className="clinical-program-btn primary" onClick={() => lockEquipmentRow(e.id)} disabled={!v?.isLockAllowed} title={v && !v.isLockAllowed ? v.lockDisabledReason : 'Lock this equipment placement'}>Lock</button>
                                                            : <button type="button" className="clinical-program-btn" onClick={() => unlockEquipmentRow(e.id)}>Unlock</button>}
                                                        {v?.restoreAvailable && (
                                                            <button type="button" className="clinical-program-btn" onClick={() => restoreEquipmentRow(e.id)} disabled={e.lifecycleState === 'LOCKED'} title="Restore this equipment's most recent valid position">Restore Valid Position</button>
                                                        )}
                                                        <button type="button" className="clinical-program-btn" onClick={() => resetEquipmentRow(e.id)} disabled={e.lifecycleState === 'LOCKED'} title="Recompute a fresh parent-derived placement">Reset to Parent-Derived</button>
                                                        <button type="button" className="clinical-program-btn" onClick={() => toggleEquipmentVisibility(e.id, !e.hidden)}>{e.hidden ? 'Show' : 'Hide'}</button>
                                                        <button type="button" className="clinical-program-btn" onClick={() => deleteEquipmentRow(e.id)} disabled={e.lifecycleState === 'LOCKED'} title={e.lifecycleState === 'LOCKED' ? 'Unlock before deleting' : 'Delete this equipment (BIM room kept)'}>Delete</button>
                                                    </div>

                                                    {e.lifecycleState === 'DRAFT' && v && !v.isLockAllowed && (
                                                        <div className="clinical-program-summary-line muted">Lock unavailable: {v.lockDisabledReason}</div>
                                                    )}

                                                    {/* Crosswalk readout — by reference; the value lives in the backend. */}
                                                    {xw && (
                                                        <div className="equipment-crosswalk">
                                                            {xw.lines.map((line) => (
                                                                <div key={line.label}>{line.label}: <span className="cal">[{line.calibration}]</span> {line.authorityRef}</div>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            )
                                        })}
                                    </div>
                                )}
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
                </>
            )}
        </div>
    )
}

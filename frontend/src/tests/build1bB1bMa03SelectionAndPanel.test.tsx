/**
 * B1B-MA-03 — Walkthrough / Clinical-Program STATE SYNCHRONIZATION + DISMISSIBLE
 * PLANNING PANEL (UI regression tests).
 *
 * Two coupled manual-acceptance defects are covered:
 *
 *   B1B-MA-03B (transient selection overwrite) — the authoritative selected room
 *   is ONE stable bimSpaceId. It must survive every program notification: hover
 *   samples, walker/camera samples, candidate refresh, footprint extraction,
 *   storey-chip filter changes, and Walkthrough entry. The PRIOR defect was an
 *   out-of-filter auto-clear inside ClinicalProgramControl's sync(): whenever a
 *   notification fired while the selected room was outside the active storey
 *   filter, the UI silently ran setClinicalProgramSelectedSpace(undefined). These
 *   tests REPRODUCE that exact overwrite path (select a room, then fire a storey /
 *   walkthrough / hover notification with the selection outside the active filter)
 *   and prove the selection now PERSISTS — they are NOT mere setter assertions.
 *
 *   B1B-MA-03A (panel not dismissible in Walkthrough) — the Clinical Program panel
 *   auto-collapses (presentation only) on Walkthrough entry, exposes a compact
 *   reopen chip, and can be reopened while still in Walkthrough with the SAME room
 *   context (selection / storey filter preserved). Collapse never mutates feature
 *   state; returning to Planning auto-expands.
 *
 * A faithful in-memory overlay mock drives programState + notifications (no @itwin,
 * no viewport). isSelectedRoomOutsideActiveStorey uses the REAL storey-filter rule
 * so the old overwrite path is genuinely reproduced.
 */
import { render, screen, act, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { filterDiscoveredRoomsByStorey, type DiscoveredRoomVolume } from '../components/spatial/bimRoomVolumeRegistry'
import { roomSelectorLabel } from '../components/spatial/roomDiscoveryLifecycle'
import type { CameraMode } from '../components/spatial/cameraNav'

// --- a mixed two-storey model. Radiopharmacy 2C17 is on the SECOND floor. ---
const discovered: DiscoveredRoomVolume[] = [
    { iModelId: 'im', bimSpaceId: '0x2C17', originalBimLabel: '2C17 PROSTH. LAB', storeyId: 'SECOND', sourceClass: 'S', authorityClass: 'EXACT_SPACE_GEOMETRY', geometryQuality: 'EXACT_SPACE_GEOMETRY', exactMeshAvailable: true, vertexCount: 10, triangleCount: 16, assigned: true, mrtDisplayName: 'Radiopharmacy 2C17', clinicalFunction: 'RADIOPHARMACY', hasPlanningVolume: true },
    { iModelId: 'im', bimSpaceId: '0x1DC8', originalBimLabel: '1DC8 CORRIDOR', storeyId: 'FIRST', sourceClass: 'S', authorityClass: 'RANGE_ONLY_APPROXIMATION', geometryQuality: 'RANGE_ONLY_APPROXIMATION', exactMeshAvailable: false, vertexCount: 0, triangleCount: 0, assigned: false, hasPlanningVolume: false },
    { iModelId: 'im', bimSpaceId: '0x1AC1', originalBimLabel: '1AC1 CENTRAL WAITING', storeyId: 'FIRST', sourceClass: 'S', authorityClass: 'RANGE_ONLY_APPROXIMATION', geometryQuality: 'RANGE_ONLY_APPROXIMATION', exactMeshAvailable: false, vertexCount: 0, triangleCount: 0, assigned: false, hasPlanningVolume: false },
]

interface FakeState {
    enabled: boolean
    activeStoreyId?: string
    selectedSpaceId?: string
    iModelId: string
    assignments: { bimSpaceId: string; clinicalFunction: string; mrtDisplayName: string; originalBimLabel: string; status: string; provenance: string; assignmentId: string }[]
    showRoomVolume: boolean
    cameraMode: CameraMode
}

const state: FakeState = {
    enabled: true, activeStoreyId: undefined, selectedSpaceId: undefined, iModelId: 'im',
    assignments: [{ bimSpaceId: '0x2C17', clinicalFunction: 'RADIOPHARMACY', mrtDisplayName: 'Radiopharmacy 2C17', originalBimLabel: '2C17 PROSTH. LAB', status: 'PLANNING_ASSIGNMENT', provenance: 'USER_DEFINED_PLANNING_OVERLAY', assignmentId: 'a1' }],
    showRoomVolume: false, cameraMode: 'PLANNING',
}
const listeners = new Set<() => void>()
const notify = () => { for (const l of listeners) l() }

// A spy that records every write to the selection AUTHORITY, so we can prove the
// component never clears it via the old out-of-filter path.
const selectWrites: (string | undefined)[] = []

vi.mock('../components/spatial/spatialAssetOverlay', () => ({
    loadClinicalProgramForIModel: vi.fn(),
    subscribeClinicalProgram: (fn: () => void) => { listeners.add(fn); return () => listeners.delete(fn) },
    getClinicalProgramSnapshot: () => ({ ...state, assignments: state.assignments }),
    refreshModelSemantics: vi.fn(async () => { }),
    getRoomDiscoveryUiStatus: () => {
        const filtered = filterDiscoveredRoomsByStorey(discovered, state.activeStoreyId)
        return { status: 'READY' as const, baseRoomCount: discovered.length, filteredRoomCount: filtered.length, label: roomSelectorLabel({ status: 'READY', filteredRoomCount: filtered.length }) }
    },
    getDiscoveredRoomOptions: () => filterDiscoveredRoomsByStorey(discovered, state.activeStoreyId),
    getDiscoveredRoomById: (id: string | undefined) => discovered.find((r) => r.bimSpaceId === id),
    // REAL storey-filter rule — the old code called setSelectedSpace(undefined)
    // exactly when this returned true, which is the overwrite path under test.
    isSelectedRoomOutsideActiveStorey: () => {
        if (!state.selectedSpaceId || !state.activeStoreyId) return false
        return !filterDiscoveredRoomsByStorey(discovered, state.activeStoreyId).some((r) => r.bimSpaceId === state.selectedSpaceId)
    },
    setClinicalProgramActiveStorey: (id: string | undefined) => { state.activeStoreyId = id; notify() },
    setClinicalProgramSelectedSpace: (id: string | undefined) => { selectWrites.push(id); state.selectedSpaceId = id; notify() },
    setClinicalProgramEnabled: (v: boolean) => { state.enabled = v; notify() },
    getClinicalProgramAssignment: (id: string) => state.assignments.find((a) => a.bimSpaceId === id),
    getClinicalProgramRoomGeometryQuality: () => ({ quality: 'EXACT_ROOM_BOUNDARY', description: 'Exact BIM space geometry' }),
    getClinicalProgramRoomStoreyId: (id: string) => discovered.find((r) => r.bimSpaceId === id)?.storeyId,
    loadCameraStoreys: vi.fn(async () => [
        { id: 'FIRST', label: 'First Floor', zLow: 0, zHigh: 4 },
        { id: 'SECOND', label: 'Second Floor', zLow: 4, zHigh: 8 },
    ]),
    setClinicalProgramStoreyRanges: vi.fn(),
    setClinicalProgramShowRoomVolume: vi.fn(),
    getClinicalPlanningVolume: () => undefined,
    getClinicalVolumeSummary: vi.fn(async () => ({ planningVolumes: 1, draft: 0, locked: 1, visible: 1, hidden: 0 })),
    getClinicalVolumeContainment: vi.fn(async () => ({ status: 'NOT_EVALUATED', failedSamples: 0, totalSamples: 0, parentMeshAvailable: false })),
    getPlanningVolumeValidation: vi.fn(async () => undefined),
    getPlanningValidationSummary: vi.fn(async () => ({ planningVolumes: 1, valid: 1, needsAttention: 0, notEvaluated: 0 })),
    restoreValidPosition: vi.fn(), resetToParentDerived: vi.fn(), lockClinicalVolume: vi.fn(),
    unlockClinicalVolume: vi.fn(), setPlanningVolumeVisibility: vi.fn(), deleteClinicalVolume: vi.fn(),
    updateClinicalVolumeParams: vi.fn(), suggestPlanningVolumeSeedForParent: vi.fn(), defineClinicalVolume: vi.fn(),
    assignClinicalProgram: vi.fn(), resetClinicalProgram: vi.fn(),
    checkProgramCompleteness: () => ({ complete: false, missing: [] }),
    summarizeProgram: () => ({ assignedCount: 1, countByFunction: { RADIOPHARMACY: 1 } }),
    getEquipmentInstances: vi.fn(() => []),
    getShowEquipment: () => true,
    setShowEquipment: vi.fn(),
    getSelectedEquipmentId: () => undefined,
    selectEquipment: vi.fn(),
}))

import { ClinicalProgramControl } from '../components/spatial/ClinicalProgramControl'

async function flush() { await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve() }) }

// Simulate a program notification that is NOT a selection (walker sample, hover,
// footprint extraction, candidate refresh, walkthrough entry) by driving a raw
// notify() through a state mutation the real overlay would perform.
function fireProgramNotification() { notify() }

function selectRoom(id: string) {
    selectWrites.push(id); state.selectedSpaceId = id; notify()
}

async function mount() {
    render(<ClinicalProgramControl iModelId="im" />)
    await flush()
}

beforeEach(() => {
    state.activeStoreyId = undefined
    state.selectedSpaceId = undefined
    state.enabled = true
    state.cameraMode = 'PLANNING'
    selectWrites.length = 0
})

// ============================================================================
// B1B-MA-03B — one authoritative selected room by stable id (persistence)
// ============================================================================
describe('B1B-MA-03B §22 — Walkthrough entry PRESERVES the selected room (2C17)', () => {
    it('selecting 2C17 then entering Walkthrough leaves 2C17 selected (old path would have cleared it)', async () => {
        await mount()
        // Select Radiopharmacy 2C17 (SECOND floor) while the filter is All.
        selectRoom('0x2C17')
        await flush()
        // Now the user filters to First Floor (2C17 is out of filter) and enters
        // Walkthrough — BOTH fire notifyProgram(). The OLD sync() would have run
        // setClinicalProgramSelectedSpace(undefined) here.
        state.activeStoreyId = 'FIRST'
        state.cameraMode = 'WALKTHROUGH'
        fireProgramNotification()
        await flush()
        // Authority is intact: no undefined was ever written by the component.
        expect(state.selectedSpaceId).toBe('0x2C17')
        expect(selectWrites).not.toContain(undefined)
    })
})

describe('B1B-MA-03B §23 — hovering a corridor does NOT clear the selected room', () => {
    it('a non-selection program notification (hover 1DC8 CORRIDOR) preserves 2C17', async () => {
        await mount()
        state.activeStoreyId = 'SECOND'
        selectRoom('0x2C17')
        await flush()
        // Simulate hover over a FIRST-floor corridor: hover writes NO selection,
        // it only fires a redraw notification. (In the 2D panel, hover sets local
        // hoveredId only.) The selection must be untouched.
        fireProgramNotification()
        fireProgramNotification()
        await flush()
        expect(state.selectedSpaceId).toBe('0x2C17')
        expect(selectWrites.filter((w) => w === undefined)).toHaveLength(0)
    })

    it('REPRODUCES the old overwrite path: selection outside active filter + repeated notifications still persists', async () => {
        await mount()
        // Deliberately create the exact prior-defect condition: selected room is
        // outside the active storey filter (First Floor filter, SECOND-floor room).
        state.activeStoreyId = 'FIRST'
        selectRoom('0x2C17')
        expect(state.selectedSpaceId).toBe('0x2C17')
        // Fire many notifications (walker samples / footprint extraction / candidate
        // refresh). Old code cleared on the FIRST such notification.
        for (let i = 0; i < 5; i++) fireProgramNotification()
        await flush()
        expect(state.selectedSpaceId).toBe('0x2C17')
        expect(selectWrites).not.toContain(undefined)
    })
})

describe('B1B-MA-03B §20/§21 — dropdown reflects the persistent selection even when out of filter', () => {
    it('the selected room remains selectable + labelled (outside current storey filter) with a non-destructive hint', async () => {
        await mount()
        state.activeStoreyId = 'FIRST' // 2C17 is on SECOND -> outside this filter
        selectRoom('0x2C17')
        await flush()
        // The dropdown value is still 2C17, an option for it is rendered, and the
        // non-destructive hint explains it stays selected.
        const select = screen.getAllByRole('combobox')[0] as HTMLSelectElement
        expect(select.value).toBe('0x2C17')
        expect(screen.getByTestId('selected-room-outside-filter-hint')).toBeTruthy()
        expect(screen.getByText(/outside current storey filter/i)).toBeTruthy()
        // The room editor still resolves the selected room (detail intact).
        expect(screen.getByText('2C17 PROSTH. LAB')).toBeTruthy()
    })

    it('switching the storey chip to Second Floor shows 2C17 in the normal list, still selected', async () => {
        await mount()
        state.activeStoreyId = 'FIRST'
        selectRoom('0x2C17')
        await flush()
        await act(async () => { screen.getByRole('button', { name: 'Second Floor' }).click() })
        await flush()
        const select = screen.getAllByRole('combobox')[0] as HTMLSelectElement
        expect(select.value).toBe('0x2C17')
        expect(state.selectedSpaceId).toBe('0x2C17')
    })
})

// ============================================================================
// B1B-MA-03A — dismissible Clinical Program panel in Walkthrough
// ============================================================================
describe('B1B-MA-03A §25 — panel auto-collapses on Walkthrough entry (presentation only)', () => {
    it('entering Walkthrough collapses the panel to a compact reopen chip; selection preserved', async () => {
        await mount()
        state.activeStoreyId = 'SECOND'
        selectRoom('0x2C17')
        await flush()
        // Panel is expanded in Planning (the storey filter chips are visible).
        expect(screen.queryByTestId('clinical-program-reopen')).toBeNull()
        // Enter Walkthrough (fires notifyProgram with cameraMode=WALKTHROUGH).
        state.cameraMode = 'WALKTHROUGH'
        fireProgramNotification()
        await flush()
        // Panel collapsed to the reopen chip; selection authority untouched.
        expect(screen.getByTestId('clinical-program-reopen')).toBeTruthy()
        expect(state.selectedSpaceId).toBe('0x2C17')
        expect(selectWrites).not.toContain(undefined)
    })
})

describe('B1B-MA-03A §24 — reopening the collapsed panel preserves room + assignment + storey filter', () => {
    it('collapse -> reopen restores the exact same room context (2C17 + Radiopharmacy + Second Floor)', async () => {
        await mount()
        state.activeStoreyId = 'SECOND'
        selectRoom('0x2C17')
        await flush()
        // Enter Walkthrough -> auto-collapse.
        state.cameraMode = 'WALKTHROUGH'
        fireProgramNotification()
        await flush()
        const chip = screen.getByTestId('clinical-program-reopen')
        // The chip surfaces the persistent room context.
        expect(chip.textContent).toMatch(/Radiopharmacy 2C17/)
        // Reopen while STILL in Walkthrough.
        await act(async () => { fireEvent.click(chip) })
        await flush()
        // Full panel back; the selection, assignment and storey filter are intact.
        expect(screen.queryByTestId('clinical-program-reopen')).toBeNull()
        const select = screen.getAllByRole('combobox')[0] as HTMLSelectElement
        expect(select.value).toBe('0x2C17')
        expect(state.activeStoreyId).toBe('SECOND')
        expect(screen.getByText('2C17 PROSTH. LAB')).toBeTruthy()
        expect(state.selectedSpaceId).toBe('0x2C17')
        expect(selectWrites).not.toContain(undefined)
    })

    it('explicit collapse control (×) is presentation-only and never clears the selection', async () => {
        await mount()
        state.activeStoreyId = 'SECOND'
        selectRoom('0x2C17')
        await flush()
        const collapseBtn = screen.getByTestId('clinical-program-collapse')
        await act(async () => { fireEvent.click(collapseBtn) })
        await flush()
        expect(screen.getByTestId('clinical-program-reopen')).toBeTruthy()
        expect(state.selectedSpaceId).toBe('0x2C17')
        expect(selectWrites).not.toContain(undefined)
    })
})

describe('B1B-MA-03A §25 — returning to Planning auto-expands the panel', () => {
    it('exiting Walkthrough (back to Planning) reopens the full panel automatically', async () => {
        await mount()
        state.cameraMode = 'WALKTHROUGH'
        fireProgramNotification()
        await flush()
        expect(screen.getByTestId('clinical-program-reopen')).toBeTruthy()
        state.cameraMode = 'PLANNING'
        fireProgramNotification()
        await flush()
        expect(screen.queryByTestId('clinical-program-reopen')).toBeNull()
    })
})

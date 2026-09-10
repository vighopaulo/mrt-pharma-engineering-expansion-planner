/**
 * Build 1A.4 — UI tests (§29): the Clinical Program editor surfaces the
 * product-facing containment validation for the SELECTED assigned room — warning
 * on FAIL, gone on PASS, Lock disabled + reason on FAIL, Restore Valid Position +
 * Reset to Parent-Derived actions, warning identifies the room, no Developer mode
 * required. The overlay is mocked (no @itwin). Selection flows through the real
 * notify → sync → selectedSpaceId path, exercising the live effect chain.
 */
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { resolvePlanningVolumeValidation } from '../components/spatial/bimRoomVolumeRegistry'

let containmentStatus: 'PASS' | 'FAIL' | 'NOT_EVALUATED' = 'FAIL'
let selectedSpaceId: string | undefined = undefined
const listeners = new Set<() => void>()
const notify = () => { for (const l of Array.from(listeners)) l() }
const assignments = [{ bimSpaceId: '0xF6', clinicalFunction: 'INJECTION_ROOM', mrtDisplayName: 'Injection Room 01', originalBimLabel: '1DC1 WAITING / ACTIVITY AREA', status: 'PLANNING_ASSIGNMENT', provenance: 'USER_DEFINED_PLANNING_OVERLAY', assignmentId: 'a1' }]

const validationFor = () => resolvePlanningVolumeValidation({
    planningVolumeId: 'inj', displayName: 'Injection Room 01', lifecycleState: 'DRAFT',
    containmentStatus, authorityQuality: 'EXACT_SPACE_GEOMETRY',
    totalSamples: 21, failedSamples: containmentStatus === 'FAIL' ? 21 : 0,
    hasLastKnownValid: true, parentMeshAvailable: true,
})

vi.mock('../components/spatial/spatialAssetOverlay', () => ({
    loadClinicalProgramForIModel: vi.fn(),
    subscribeClinicalProgram: (fn: () => void) => { listeners.add(fn); return () => listeners.delete(fn) },
    getClinicalProgramSnapshot: () => ({ enabled: true, activeStoreyId: undefined, selectedSpaceId, iModelId: 'im', assignments, showRoomVolume: false }),
    refreshModelSemantics: vi.fn(async () => { }),
    getRoomDiscoveryUiStatus: () => ({ status: 'READY' as const, baseRoomCount: 1, filteredRoomCount: 1, label: 'Select a room (1)' }),
    getDiscoveredRoomOptions: () => [{ iModelId: 'im', bimSpaceId: '0xF6', originalBimLabel: '1DC1 WAITING / ACTIVITY AREA', storeyId: 'FIRST', sourceClass: 'S', authorityClass: 'EXACT_SPACE_GEOMETRY', geometryQuality: 'EXACT_SPACE_GEOMETRY', exactMeshAvailable: true, vertexCount: 10, triangleCount: 16, assigned: true, mrtDisplayName: 'Injection Room 01', clinicalFunction: 'INJECTION_ROOM', hasPlanningVolume: true }],
    isSelectedRoomOutsideActiveStorey: () => false,
    setClinicalProgramActiveStorey: vi.fn(),
    setClinicalProgramSelectedSpace: (id: string | undefined) => { selectedSpaceId = id; notify() },
    setClinicalProgramEnabled: vi.fn(),
    getClinicalProgramAssignment: (id: string) => assignments.find((a) => a.bimSpaceId === id),
    getClinicalProgramRoomGeometryQuality: () => ({ quality: 'EXACT_ROOM_BOUNDARY', description: 'Exact BIM space geometry' }),
    getClinicalProgramRoomStoreyId: () => 'FIRST',
    loadCameraStoreys: vi.fn(async () => [{ id: 'FIRST', label: 'First Floor', zLow: 0, zHigh: 4 }]),
    setClinicalProgramStoreyRanges: vi.fn(),
    setClinicalProgramShowRoomVolume: vi.fn(),
    getClinicalPlanningVolume: () => ({ params: { centerX: -31.99, centerY: 32.09, zLow: 0, zHigh: 3, width: 14.2, depth: 4.17, yaw: 0 }, lifecycleState: 'DRAFT', hidden: false }),
    getClinicalVolumeSummary: vi.fn(async () => ({ planningVolumes: 1, draft: 1, locked: 0, visible: 1, hidden: 0 })),
    getClinicalVolumeContainment: vi.fn(async () => ({ status: containmentStatus, failedSamples: containmentStatus === 'FAIL' ? 21 : 0, totalSamples: 21, parentMeshAvailable: true })),
    getPlanningVolumeValidation: vi.fn(async () => validationFor()),
    getPlanningValidationSummary: vi.fn(async () => ({ planningVolumes: 1, valid: containmentStatus === 'PASS' ? 1 : 0, needsAttention: containmentStatus === 'FAIL' ? 1 : 0, notEvaluated: 0 })),
    restoreValidPosition: vi.fn(async () => { containmentStatus = 'PASS'; notify(); return { ok: true, source: 'LAST_KNOWN_VALID' } }),
    resetToParentDerived: vi.fn(async () => { containmentStatus = 'PASS'; notify(); return { ok: true } }),
    lockClinicalVolume: vi.fn(async () => ({ ok: containmentStatus === 'PASS' })),
    unlockClinicalVolume: vi.fn(),
    setPlanningVolumeVisibility: vi.fn(),
    deleteClinicalVolume: vi.fn(async () => ({ ok: true })),
    updateClinicalVolumeParams: vi.fn(),
    suggestPlanningVolumeSeedForParent: vi.fn(async () => ({ centerX: 0, centerY: 0, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0 })),
    defineClinicalVolume: vi.fn(async () => { }),
    assignClinicalProgram: vi.fn(() => ({ ok: true, assignment: assignments[0] })),
    resetClinicalProgram: vi.fn(),
    checkProgramCompleteness: () => ({ complete: false, missing: [] }),
    summarizeProgram: () => ({ assignedCount: 1, countByFunction: { INJECTION_ROOM: 1 } }),
}))

import { ClinicalProgramControl } from '../components/spatial/ClinicalProgramControl'

/** Mount and select the injection room through the real select (drives sync). */
async function mountAndSelect() {
    render(<ClinicalProgramControl iModelId="im" />)
    const select = await screen.findByRole('combobox', {}, { timeout: 4000 })
    await act(async () => { fireEvent.change(select, { target: { value: '0xF6' } }) })
}

describe('Build 1A.4 §29 — product containment validation UI (no Developer mode)', () => {
    beforeEach(() => { containmentStatus = 'FAIL'; selectedSpaceId = undefined })

    it('FAIL shows a product warning that identifies the room', async () => {
        await mountAndSelect()
        const warning = await screen.findByRole('alert', {}, { timeout: 4000 })
        expect(warning.textContent).toContain('Injection Room 01')
        expect(warning.textContent?.toLowerCase()).toContain('outside')
    })

    it('FAIL disables Lock and shows the disabled reason', async () => {
        await mountAndSelect()
        const lock = await screen.findByRole('button', { name: 'Lock Volume' }, { timeout: 4000 })
        expect((lock as HTMLButtonElement).disabled).toBe(true)
        expect(screen.getByText(/Lock unavailable:/)).toBeTruthy()
    })

    it('Restore Valid Position + Reset to Parent-Derived actions are offered on FAIL', async () => {
        await mountAndSelect()
        expect(await screen.findByRole('button', { name: 'Restore Valid Position' }, { timeout: 4000 })).toBeTruthy()
        expect(screen.getByRole('button', { name: 'Reset to Parent-Derived Volume' })).toBeTruthy()
    })

    it('Restore Valid Position clears the warning and re-enables Lock (PASS)', async () => {
        await mountAndSelect()
        const restore = await screen.findByRole('button', { name: 'Restore Valid Position' }, { timeout: 4000 })
        await act(async () => { restore.click() })
        await waitFor(() => expect(screen.queryByRole('alert')).toBeNull(), { timeout: 4000 })
        const lock = screen.getByRole('button', { name: 'Lock Volume' })
        expect((lock as HTMLButtonElement).disabled).toBe(false)
    })

    it('PASS shows the fully-inside line and no warning', async () => {
        containmentStatus = 'PASS'
        await mountAndSelect()
        expect(await screen.findByText(/Fully inside its parent BIM room/, {}, { timeout: 4000 })).toBeTruthy()
        expect(screen.queryByRole('alert')).toBeNull()
    })

    it('the validation summary reports needs-attention on FAIL', async () => {
        await mountAndSelect()
        expect(await screen.findByText(/Needs attention:/, {}, { timeout: 4000 })).toBeTruthy()
    })
})

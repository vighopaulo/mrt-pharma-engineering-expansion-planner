/**
 * Build 1B — Equipment UI tests (§54): the Clinical Program panel surfaces the
 * canonical equipment inventory, places equipment in the selected room, shows a
 * per-instance validation warning on FAIL that identifies the equipment + room,
 * disables Lock with a visible reason, and offers Restore / Reset / Delete — all
 * WITHOUT Developer mode. The overlay is mocked (no @itwin); selection flows
 * through the real notify → sync path.
 */
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { resolveEquipmentValidation, buildEquipmentCrosswalkReadout } from '../components/spatial/equipmentValidation'
import type { EquipmentAssetInstance } from '../components/spatial/equipmentInstance'

let containmentStatus: 'PASS' | 'FAIL' | 'NOT_EVALUATED' = 'FAIL'
let selectedSpaceId: string | undefined = undefined
let equipment: EquipmentAssetInstance[] = []
let selectedEquipmentId: string | undefined = undefined
const listeners = new Set<() => void>()
const notify = () => { for (const l of Array.from(listeners)) l() }
const placeSpy = vi.fn()
const lockSpy = vi.fn()
const deleteSpy = vi.fn()

const assignments = [{ bimSpaceId: '0xF6', clinicalFunction: 'CYCLOTRON', mrtDisplayName: 'Cyclotron 01', originalBimLabel: '1DC1 VAULT', status: 'PLANNING_ASSIGNMENT', provenance: 'USER_DEFINED_PLANNING_OVERLAY', assignmentId: 'a1' }]

function anInstance(): EquipmentAssetInstance {
    return {
        id: 'equipment:im:0xF6:IBA_CYCLONE_KEY:1',
        iModelId: 'im',
        canonicalEquipmentId: 'IBA_CYCLONE_KEY',
        canonicalClass: 'CYCLOTRON',
        assetFamily: 'CYCLOTRON',
        parentBimSpaceId: '0xF6',
        storeyId: 'FIRST',
        displayLabel: 'IBA Cyclone KEY',
        geometryType: 'ORIENTED_EQUIPMENT_ENVELOPE',
        placement: { centerX: 45, centerY: 64, zBase: 0, width: 1.5, depth: 1.4, height: 1.35, yaw: 0, envelopeProvenance: 'CALIBRATED' },
        lifecycleState: 'DRAFT',
        geometrySource: 'MRT_EQUIPMENT_BINDING',
    }
}

const validationForId = () => resolveEquipmentValidation({
    instance: anInstance(), containmentStatus, authorityQuality: 'EXACT_SPACE_GEOMETRY',
    totalSamples: 21, failedSamples: containmentStatus === 'FAIL' ? 21 : 0, parentMeshAvailable: true,
})

vi.mock('../components/spatial/spatialAssetOverlay', () => ({
    loadClinicalProgramForIModel: vi.fn(),
    subscribeClinicalProgram: (fn: () => void) => { listeners.add(fn); return () => listeners.delete(fn) },
    getClinicalProgramSnapshot: vi.fn(() => ({ enabled: true, activeStoreyId: undefined, selectedSpaceId, iModelId: 'im', assignments, showRoomVolume: false })),
    refreshModelSemantics: vi.fn(async () => { }),
    getRoomDiscoveryUiStatus: () => ({ status: 'READY' as const, baseRoomCount: 1, filteredRoomCount: 1, label: 'Select a room (1)' }),
    getDiscoveredRoomOptions: () => [{ iModelId: 'im', bimSpaceId: '0xF6', originalBimLabel: '1DC1 VAULT', storeyId: 'FIRST', sourceClass: 'S', authorityClass: 'EXACT_SPACE_GEOMETRY', geometryQuality: 'EXACT_SPACE_GEOMETRY', exactMeshAvailable: true, vertexCount: 10, triangleCount: 16, assigned: true, mrtDisplayName: 'Cyclotron 01', clinicalFunction: 'CYCLOTRON', hasPlanningVolume: false }],
    getDiscoveredRoomById: (id: string | undefined) => id === '0xF6' ? { iModelId: 'im', bimSpaceId: '0xF6', originalBimLabel: '1DC1 VAULT', storeyId: 'FIRST', sourceClass: 'S', authorityClass: 'EXACT_SPACE_GEOMETRY', geometryQuality: 'EXACT_SPACE_GEOMETRY', exactMeshAvailable: true, vertexCount: 10, triangleCount: 16, assigned: true, mrtDisplayName: 'Cyclotron 01', clinicalFunction: 'CYCLOTRON', hasPlanningVolume: false } : undefined,
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
    getClinicalPlanningVolume: () => undefined,
    getClinicalVolumeSummary: vi.fn(async () => ({ planningVolumes: 0, draft: 0, locked: 0, visible: 0, hidden: 0 })),
    getClinicalVolumeContainment: vi.fn(async () => ({ status: 'NOT_EVALUATED', failedSamples: 0, totalSamples: 0, parentMeshAvailable: false })),
    getPlanningVolumeValidation: vi.fn(async () => undefined),
    getPlanningValidationSummary: vi.fn(async () => ({ planningVolumes: 0, valid: 0, needsAttention: 0, notEvaluated: 0 })),
    restoreValidPosition: vi.fn(), resetToParentDerived: vi.fn(), lockClinicalVolume: vi.fn(),
    unlockClinicalVolume: vi.fn(), setPlanningVolumeVisibility: vi.fn(), deleteClinicalVolume: vi.fn(),
    updateClinicalVolumeParams: vi.fn(), suggestPlanningVolumeSeedForParent: vi.fn(), defineClinicalVolume: vi.fn(),
    assignClinicalProgram: vi.fn(() => ({ ok: true, assignment: assignments[0] })), resetClinicalProgram: vi.fn(),
    checkProgramCompleteness: () => ({ complete: false, missing: [] }),
    summarizeProgram: () => ({ assignedCount: 1, countByFunction: { CYCLOTRON: 1 } }),
    // --- Build 1B equipment overlay surface ---
    getEquipmentInstances: vi.fn(() => equipment),
    getEquipmentInstance: (id: string) => equipment.find((e) => e.id === id),
    getShowEquipment: () => true,
    setShowEquipment: vi.fn(),
    getSelectedEquipmentId: () => selectedEquipmentId,
    selectEquipment: (id: string | undefined) => { selectedEquipmentId = id; notify() },
    placeEquipmentInParent: vi.fn(async (input: { canonicalEquipmentId: string; parentBimSpaceId: string }) => {
        placeSpy(input)
        equipment = [anInstance()]
        selectedEquipmentId = equipment[0].id
        notify()
        return { ok: true, equipmentInstanceId: equipment[0].id }
    }),
    updateEquipmentPlacement: vi.fn(),
    // Return a validation for any known instance id regardless of the mutable
    // `equipment` array timing (the component computes validation asynchronously).
    getEquipmentValidation: vi.fn(async (id: string) => (id ? validationForId() : undefined)),
    getEquipmentCrosswalk: vi.fn(async (id: string) => (id ? buildEquipmentCrosswalkReadout('IBA_CYCLONE_KEY') : undefined)),
    restoreEquipmentValidPosition: vi.fn(async () => { containmentStatus = 'PASS'; notify(); return { ok: true, source: 'LAST_KNOWN_VALID' } }),
    resetEquipmentToParentDerived: vi.fn(async () => { containmentStatus = 'PASS'; notify(); return { ok: true } }),
    lockEquipment: vi.fn(async (id: string) => { lockSpy(id); return { ok: containmentStatus === 'PASS' } }),
    unlockEquipment: vi.fn(),
    setEquipmentVisibility: vi.fn(),
    deleteEquipment: vi.fn((id: string) => { deleteSpy(id); equipment = equipment.filter((e) => e.id !== id); notify(); return { ok: true } }),
}))

import { ClinicalProgramControl } from '../components/spatial/ClinicalProgramControl'

async function mountAndSelectRoom() {
    render(<ClinicalProgramControl iModelId="im" />)
    // Multiple comboboxes exist (room selector + equipment inventory); the FIRST
    // is the BIM room (space) selector.
    const combos = await screen.findAllByRole('combobox', {}, { timeout: 4000 })
    await act(async () => { fireEvent.change(combos[0], { target: { value: '0xF6' } }) })
}

describe('Build 1B §54 — equipment binding UI (no Developer mode)', () => {
    beforeEach(() => { containmentStatus = 'FAIL'; selectedSpaceId = undefined; equipment = []; selectedEquipmentId = undefined; placeSpy.mockClear(); lockSpy.mockClear(); deleteSpy.mockClear() })

    it('renders the canonical equipment inventory (grouped) not-dev-gated', async () => {
        await mountAndSelectRoom()
        expect(await screen.findByText('EQUIPMENT (canonical catalog)', {}, { timeout: 4000 })).toBeTruthy()
        // Inventory contains a cyclotron option label.
        expect(screen.getByText(/IBA Cyclone KEY/)).toBeTruthy()
    })



    it('placing equipment calls the overlay and renders the instance row', async () => {
        await mountAndSelectRoom()
        // Choose a model in the equipment select (the last combobox).
        const combos = await screen.findAllByRole('combobox')
        const equipSelect = combos[combos.length - 1]
        await act(async () => { fireEvent.change(equipSelect, { target: { value: 'IBA_CYCLONE_KEY' } }) })
        const placeBtn = screen.getByRole('button', { name: 'Place in Selected Room' })
        await act(async () => { placeBtn.click() })
        expect(placeSpy).toHaveBeenCalledWith({ canonicalEquipmentId: 'IBA_CYCLONE_KEY', parentBimSpaceId: '0xF6' })
        // The instance ROW renders a unique detail line (distinct from the inventory option).
        await screen.findByText(/CYCLOTRON · room 0xF6/, {}, { timeout: 4000 })
    })

    it('a FAIL instance shows a warning identifying the equipment + Lock disabled with reason', async () => {
        equipment = [anInstance()]; selectedEquipmentId = equipment[0].id
        await mountAndSelectRoom()
        const warning = await screen.findByRole('alert', {}, { timeout: 4000 })
        expect(warning.textContent).toContain('IBA Cyclone KEY')
        expect(warning.textContent?.toLowerCase()).toContain('outside')
        const lock = screen.getByRole('button', { name: 'Lock' })
        expect((lock as HTMLButtonElement).disabled).toBe(true)
        expect(screen.getByText(/Lock unavailable:/)).toBeTruthy()
    })

    it('Restore + Reset + Delete controls are offered for a DRAFT instance', async () => {
        equipment = [anInstance()]; selectedEquipmentId = equipment[0].id
        await mountAndSelectRoom()
        expect(await screen.findByRole('button', { name: 'Restore Valid Position' }, { timeout: 4000 })).toBeTruthy()
        expect(screen.getByRole('button', { name: 'Reset to Parent-Derived' })).toBeTruthy()
        expect(screen.getByRole('button', { name: 'Delete' })).toBeTruthy()
    })

    it('Restore clears the warning (PASS) and enables Lock', async () => {
        equipment = [anInstance()]; selectedEquipmentId = equipment[0].id
        await mountAndSelectRoom()
        const restore = await screen.findByRole('button', { name: 'Restore Valid Position' }, { timeout: 4000 })
        await act(async () => { restore.click() })
        await waitFor(() => expect(screen.queryByRole('alert')).toBeNull(), { timeout: 4000 })
        const lock = screen.getByRole('button', { name: 'Lock' })
        expect((lock as HTMLButtonElement).disabled).toBe(false)
    })

    it('the crosswalk readout is shown by reference (calibration + authority ref, no value)', async () => {
        equipment = [anInstance()]; selectedEquipmentId = equipment[0].id
        await mountAndSelectRoom()
        expect(await screen.findByText(/cyclotron_installation_capex/, {}, { timeout: 4000 })).toBeTruthy()
    })

    it('Delete removes the instance', async () => {
        equipment = [anInstance()]; selectedEquipmentId = equipment[0].id
        await mountAndSelectRoom()
        const del = await screen.findByRole('button', { name: 'Delete' }, { timeout: 4000 })
        await act(async () => { del.click() })
        await waitFor(() => expect(deleteSpy).toHaveBeenCalled(), { timeout: 4000 })
        // The instance ROW detail line disappears (inventory option remains).
        await waitFor(() => expect(screen.queryByText(/CYCLOTRON · room 0xF6/)).toBeNull(), { timeout: 4000 })
    })
})

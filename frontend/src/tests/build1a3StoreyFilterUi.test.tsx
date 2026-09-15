/**
 * Build 1A.3 — UI tests (§24): the Clinical Program room selector's options +
 * count are driven by the storey filter and recompute immediately when the
 * active storey changes; the "All" filter returns the base collection; and
 * storey filtering never changes the clinical assignment count. A faithful
 * in-memory overlay mock drives programState + notifications (no @itwin).
 */
import { render, screen, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
    filterDiscoveredRoomsByStorey,
    type DiscoveredRoomVolume,
} from '../components/spatial/bimRoomVolumeRegistry'
import { roomSelectorLabel } from '../components/spatial/roomDiscoveryLifecycle'

// --- an in-memory overlay that mimics the real state machine --------------

interface FakeState {
    enabled: boolean
    activeStoreyId?: string
    selectedSpaceId?: string
    iModelId: string
    assignments: { bimSpaceId: string; clinicalFunction: string; mrtDisplayName: string; originalBimLabel: string; status: string; provenance: string; assignmentId: string }[]
    showRoomVolume: boolean
}

const discovered: DiscoveredRoomVolume[] = [
    { iModelId: 'im', bimSpaceId: '0xF1', originalBimLabel: '1DC1 WAITING / ACTIVITY AREA', storeyId: 'FIRST', sourceClass: 'S', authorityClass: 'RANGE_ONLY_APPROXIMATION', geometryQuality: 'RANGE_ONLY_APPROXIMATION', exactMeshAvailable: false, vertexCount: 0, triangleCount: 0, assigned: false, hasPlanningVolume: false },
    { iModelId: 'im', bimSpaceId: '0xF2', originalBimLabel: '1AC1 CENTRAL WAITING', storeyId: 'FIRST', sourceClass: 'S', authorityClass: 'RANGE_ONLY_APPROXIMATION', geometryQuality: 'RANGE_ONLY_APPROXIMATION', exactMeshAvailable: false, vertexCount: 0, triangleCount: 0, assigned: true, mrtDisplayName: 'Uptake 01', clinicalFunction: 'UPTAKE_ROOM', hasPlanningVolume: true },
    { iModelId: 'im', bimSpaceId: '0xS1', originalBimLabel: '2ND ROOM A', storeyId: 'SECOND', sourceClass: 'S', authorityClass: 'RANGE_ONLY_APPROXIMATION', geometryQuality: 'RANGE_ONLY_APPROXIMATION', exactMeshAvailable: false, vertexCount: 0, triangleCount: 0, assigned: false, hasPlanningVolume: false },
]

const state: FakeState = {
    enabled: true, activeStoreyId: undefined, selectedSpaceId: undefined, iModelId: 'im',
    assignments: [{ bimSpaceId: '0xF2', clinicalFunction: 'UPTAKE_ROOM', mrtDisplayName: 'Uptake 01', originalBimLabel: '1AC1 CENTRAL WAITING', status: 'PLANNING_ASSIGNMENT', provenance: 'USER_DEFINED_PLANNING_OVERLAY', assignmentId: 'a1' }],
    showRoomVolume: false,
}
const listeners = new Set<() => void>()
const notify = () => { for (const l of listeners) l() }

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
    isSelectedRoomOutsideActiveStorey: () => {
        if (!state.selectedSpaceId || !state.activeStoreyId) return false
        return !filterDiscoveredRoomsByStorey(discovered, state.activeStoreyId).some((r) => r.bimSpaceId === state.selectedSpaceId)
    },
    setClinicalProgramActiveStorey: (id: string | undefined) => { state.activeStoreyId = id; notify() },
    setClinicalProgramSelectedSpace: (id: string | undefined) => { state.selectedSpaceId = id; notify() },
    setClinicalProgramEnabled: (v: boolean) => { state.enabled = v; notify() },
    getClinicalProgramAssignment: (id: string) => state.assignments.find((a) => a.bimSpaceId === id),
    getClinicalProgramRoomGeometryQuality: () => ({ quality: 'BIM_RANGE_APPROXIMATION', description: 'BIM range approximation' }),
    getClinicalProgramRoomStoreyId: () => undefined,
    loadCameraStoreys: vi.fn(async () => [
        { id: 'FIRST', label: 'First Floor', zLow: 0, zHigh: 4 },
        { id: 'SECOND', label: 'Second Floor', zLow: 4, zHigh: 8 },
    ]),
    setClinicalProgramStoreyRanges: vi.fn(),
    setClinicalProgramShowRoomVolume: vi.fn(),
    getClinicalPlanningVolume: () => undefined,
    getClinicalVolumeSummary: vi.fn(async () => ({ planningVolumes: 1, draft: 1, locked: 0, visible: 1, hidden: 0 })),
    getClinicalVolumeContainment: vi.fn(async () => ({ status: 'NOT_EVALUATED', failedSamples: 0, totalSamples: 0, parentMeshAvailable: false })),
    suggestPlanningVolumeSeedForParent: vi.fn(async () => ({ centerX: 0, centerY: 0, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0 })),
    checkProgramCompleteness: () => ({ complete: false, missing: [] }),
    summarizeProgram: () => ({ assignedCount: 1, countByFunction: { UPTAKE_ROOM: 1 } }),
}))

import { ClinicalProgramControl } from '../components/spatial/ClinicalProgramControl'

async function flush() { await act(async () => { await Promise.resolve(); await Promise.resolve() }) }

describe('Build 1A.3 §24 — storey filter drives the room selector', () => {
    beforeEach(() => { state.activeStoreyId = undefined; state.selectedSpaceId = undefined; state.enabled = true })

    it('All shows the base collection (3 rooms)', async () => {
        render(<ClinicalProgramControl iModelId="im" />)
        await flush()
        expect(await screen.findByText('Select a room (3)')).toBeTruthy()
    })

    it('switching to First Floor recomputes to only First-Floor rooms (2)', async () => {
        render(<ClinicalProgramControl iModelId="im" />)
        await flush()
        await act(async () => { screen.getByRole('button', { name: 'First Floor' }).click() })
        await flush()
        expect(await screen.findByText('Select a room (2)')).toBeTruthy()
        // Options are First-Floor only; the Second-Floor room is absent.
        expect(screen.queryByText('2ND ROOM A')).toBeNull()
    })

    it('switching to Second Floor recomputes to only Second-Floor rooms (1) — not stuck at First count', async () => {
        render(<ClinicalProgramControl iModelId="im" />)
        await flush()
        await act(async () => { screen.getByRole('button', { name: 'First Floor' }).click() })
        await flush()
        await act(async () => { screen.getByRole('button', { name: 'Second Floor' }).click() })
        await flush()
        // The regression was First==Second; here Second is a DISTINCT count.
        expect(await screen.findByText('Select a room (1)')).toBeTruthy()
        expect(screen.getByText('2ND ROOM A')).toBeTruthy()
    })

    it('back to All returns the base count (3)', async () => {
        render(<ClinicalProgramControl iModelId="im" />)
        await flush()
        await act(async () => { screen.getByRole('button', { name: 'First Floor' }).click() })
        await flush()
        await act(async () => { screen.getByRole('button', { name: 'All' }).click() })
        await flush()
        expect(await screen.findByText('Select a room (3)')).toBeTruthy()
    })

    it('storey filtering does not change the clinical assignment count (domain unaffected)', async () => {
        render(<ClinicalProgramControl iModelId="im" />)
        await flush()
        const before = state.assignments.length
        await act(async () => { screen.getByRole('button', { name: 'Second Floor' }).click() })
        await flush()
        expect(state.assignments.length).toBe(before) // no assignment created/deleted by filtering
    })
})

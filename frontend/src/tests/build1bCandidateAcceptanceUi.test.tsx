/**
 * Build 1B — CANDIDATE-ROOM ACCEPTANCE UX (UI tests).
 *   §20 — the candidate results render in a DEDICATED BOUNDED SCROLLABLE region
 *          with COMPACT cards that show the tier + both scores + area/storey/
 *          authority, and every card's actions (Fit to Room / Enter Walkthrough
 *          Here / Use This Room) are reachable.
 *   §21 — PREVIEW-DOES-NOT-REPARENT isolation: Fit to Room and Enter Walkthrough
 *          Here NEVER call the re-parent bridge; only Use This Room does.
 *
 * A faithful in-memory overlay mock drives the candidate discovery + action
 * bridges (no @itwin, no viewport). The ranked candidates are produced by the
 * REAL pure engine so the tiers under test are genuine (not fabricated).
 */
import { render, screen, act, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
    rankClinicalRoomCandidates,
    summarizeCandidateRanking,
    summarizeDiscoveredVocabulary,
    classifyBimSpaceSemantics,
    type DiscoveredSemanticVocabulary,
} from '../components/spatial/clinicalRoomCandidate'
import type { DiscoveredRoomVolume } from '../components/spatial/bimRoomVolumeRegistry'

// --- fixtures: a mixed model exercising every tier -------------------------
const range = (w: number, d: number) => ({ low: { x: 0, y: 0, z: 0 }, high: { x: w, y: d, z: 3 } })
const mixedRooms: Pick<DiscoveredRoomVolume, 'bimSpaceId' | 'originalBimLabel' | 'mrtDisplayName' | 'storeyId' | 'sourceClass' | 'worldRange' | 'geometryQuality'>[] = [
    { bimSpaceId: '0xUp', originalBimLabel: 'Uptake 01', storeyId: 'FIRST', sourceClass: 'S', worldRange: range(4, 3), geometryQuality: 'EXACT_SPACE_GEOMETRY' }, // RECOMMENDED
    { bimSpaceId: '0xWait', originalBimLabel: '1DC1 WAITING / ACTIVITY AREA', storeyId: 'FIRST', sourceClass: 'S', worldRange: range(8, 6), geometryQuality: 'EXACT_SPACE_GEOMETRY' }, // not recommended
    { bimSpaceId: '0xCorr', originalBimLabel: 'Corridor 2', storeyId: 'FIRST', sourceClass: 'S', worldRange: range(12, 3), geometryQuality: 'EXACT_SPACE_GEOMETRY' }, // REJECTED
]

const rankedCandidates = rankClinicalRoomCandidates({ clinicalFunction: 'UPTAKE_ROOM', rooms: mixedRooms, limit: 25 })
const rankedSummary = summarizeCandidateRanking({ clinicalFunction: 'UPTAKE_ROOM', candidates: rankedCandidates })
const rankedVocab: DiscoveredSemanticVocabulary = summarizeDiscoveredVocabulary(
    mixedRooms.map((r) => classifyBimSpaceSemantics({ originalBimLabel: r.originalBimLabel, sourceClass: r.sourceClass })),
)

// --- spies proving the re-parent isolation ---------------------------------
const fitSpy = vi.fn(async () => true)
const walkSpy = vi.fn(async () => ({ ok: true as const, provenance: 'INTERIOR_ANCHOR' }))
const reparentSpy = vi.fn(async () => ({ ok: true as const, containment: 'PASS' }))
const selectSpy = vi.fn()

const listeners = new Set<() => void>()

vi.mock('../components/spatial/spatialAssetOverlay', () => ({
    loadClinicalProgramForIModel: vi.fn(),
    subscribeClinicalProgram: (fn: () => void) => { listeners.add(fn); return () => listeners.delete(fn) },
    getClinicalProgramSnapshot: () => ({ enabled: true, activeStoreyId: undefined, selectedSpaceId: undefined, iModelId: 'im', assignments: [], showRoomVolume: false }),
    refreshModelSemantics: vi.fn(async () => { }),
    getRoomDiscoveryUiStatus: () => ({ status: 'READY' as const, baseRoomCount: 3, filteredRoomCount: 3, label: 'Select a room (3)' }),
    getDiscoveredRoomOptions: () => mixedRooms.map((r) => ({ ...r, iModelId: 'im', authorityClass: r.geometryQuality, exactMeshAvailable: true, vertexCount: 8, triangleCount: 12, assigned: false, hasPlanningVolume: false })),
    getDiscoveredRoomById: (id: string | undefined) => {
        const r = mixedRooms.find((m) => m.bimSpaceId === id)
        return r ? { ...r, iModelId: 'im', authorityClass: r.geometryQuality, exactMeshAvailable: true, vertexCount: 8, triangleCount: 12, assigned: false, hasPlanningVolume: false } : undefined
    },
    isSelectedRoomOutsideActiveStorey: () => false,
    setClinicalProgramActiveStorey: vi.fn(),
    setClinicalProgramSelectedSpace: selectSpy,
    setClinicalProgramEnabled: vi.fn(),
    getClinicalProgramAssignment: () => undefined,
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
    assignClinicalProgram: vi.fn(), resetClinicalProgram: vi.fn(),
    checkProgramCompleteness: () => ({ complete: false, missing: [] }),
    summarizeProgram: () => ({ assignedCount: 0, countByFunction: {} }),
    // --- Build 1B candidate discovery + acceptance bridges (under test) ---
    findClinicalRoomCandidates: vi.fn(async () => ({ candidates: rankedCandidates, summary: rankedSummary, vocabulary: rankedVocab })),
    fitViewToClinicalRoom: fitSpy,
    enterWalkthroughAtClinicalRoom: walkSpy,
    reparentClinicalFunction: reparentSpy,
    // equipment surface (unused here but referenced by the component) ---
    getEquipmentInstances: vi.fn(() => []),
    getShowEquipment: () => true,
    setShowEquipment: vi.fn(),
    getSelectedEquipmentId: () => undefined,
    selectEquipment: vi.fn(),
}))

import { ClinicalProgramControl } from '../components/spatial/ClinicalProgramControl'

async function flush() { await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve() }) }

async function mountAndFind() {
    render(<ClinicalProgramControl iModelId="im" />)
    await flush()
    // The candidate-function select is labelled; trigger the search.
    const btn = await screen.findByRole('button', { name: /Find Candidate Rooms/i })
    await act(async () => { fireEvent.click(btn) })
    await flush()
}

describe('Build 1B §20 — bounded scrollable candidate results + compact cards', () => {
    beforeEach(() => { fitSpy.mockClear(); walkSpy.mockClear(); reparentSpy.mockClear(); selectSpy.mockClear() })

    it('renders a dedicated scrollable results region containing every candidate card', async () => {
        await mountAndFind()
        const region = await screen.findByTestId('candidate-results-region')
        expect(region).toBeTruthy()
        expect(region.className).toContain('clinical-program-candidate-list')
        const cards = screen.getAllByTestId('candidate-card')
        expect(cards.length).toBe(rankedCandidates.length)
    })

    it('each compact card shows its tier badge and BOTH scores (suitability + fit)', async () => {
        await mountAndFind()
        const badges = screen.getAllByTestId('candidate-tier-badge')
        expect(badges.length).toBe(rankedCandidates.length)
        // A recommended, a non-recommended, and a rejected are all present.
        const badgeText = badges.map((b) => b.textContent)
        expect(badgeText).toContain('Recommended')
        expect(badgeText.some((t) => t === 'Rejected')).toBe(true)
        // Both score axes are surfaced.
        expect(screen.getAllByText(/Suitability \d+%/).length).toBeGreaterThan(0)
        expect(screen.getAllByText(/Fit \d+%/).length).toBeGreaterThan(0)
    })

    it('the WAITING / ACTIVITY AREA card is NOT recommended (the 1DC1 defect is corrected)', async () => {
        await mountAndFind()
        const waitCard = screen.getAllByTestId('candidate-card').find((c) => c.textContent?.includes('WAITING'))!
        expect(waitCard).toBeTruthy()
        expect(waitCard.getAttribute('data-tier')).not.toBe('RECOMMENDED')
        // Its badge is not "Recommended".
        expect(waitCard.querySelector('[data-testid="candidate-tier-badge"]')?.textContent).not.toBe('Recommended')
    })

    it('every card exposes reachable Fit to Room / Enter Walkthrough Here / Use This Room actions', async () => {
        await mountAndFind()
        const cards = screen.getAllByTestId('candidate-card')
        for (const card of cards) {
            expect(card.querySelector('button')).toBeTruthy()
            const btns = Array.from(card.querySelectorAll('button')).map((b) => b.textContent)
            expect(btns).toContain('Fit to Room')
            expect(btns).toContain('Enter Walkthrough Here')
            expect(btns).toContain('Use This Room')
        }
    })
})

describe('Build 1B §21 — preview actions NEVER re-parent (only Use This Room does)', () => {
    beforeEach(() => { fitSpy.mockClear(); walkSpy.mockClear(); reparentSpy.mockClear(); selectSpy.mockClear() })

    it('Fit to Room fits the view but does NOT re-parent', async () => {
        await mountAndFind()
        const recCard = screen.getAllByTestId('candidate-card').find((c) => c.getAttribute('data-tier') === 'RECOMMENDED')!
        const fitBtn = Array.from(recCard.querySelectorAll('button')).find((b) => b.textContent === 'Fit to Room')!
        await act(async () => { fireEvent.click(fitBtn) })
        await flush()
        expect(fitSpy).toHaveBeenCalledTimes(1)
        expect(reparentSpy).not.toHaveBeenCalled()
    })

    it('Enter Walkthrough Here spawns but does NOT re-parent', async () => {
        await mountAndFind()
        const recCard = screen.getAllByTestId('candidate-card').find((c) => c.getAttribute('data-tier') === 'RECOMMENDED')!
        const walkBtn = Array.from(recCard.querySelectorAll('button')).find((b) => b.textContent === 'Enter Walkthrough Here')!
        await act(async () => { fireEvent.click(walkBtn) })
        await flush()
        expect(walkSpy).toHaveBeenCalledTimes(1)
        expect(reparentSpy).not.toHaveBeenCalled()
    })

    it('Use This Room is the ONLY action that re-parents', async () => {
        await mountAndFind()
        const recCard = screen.getAllByTestId('candidate-card').find((c) => c.getAttribute('data-tier') === 'RECOMMENDED')!
        const useBtn = Array.from(recCard.querySelectorAll('button')).find((b) => b.textContent === 'Use This Room')!
        await act(async () => { fireEvent.click(useBtn) })
        await flush()
        expect(reparentSpy).toHaveBeenCalledTimes(1)
    })

    it('a rejected candidate cannot be re-parented without an explicit override', async () => {
        await mountAndFind()
        const rejCard = screen.getAllByTestId('candidate-card').find((c) => c.getAttribute('data-tier') === 'REJECTED')!
        const useBtn = Array.from(rejCard.querySelectorAll('button')).find((b) => b.textContent === 'Use This Room') as HTMLButtonElement
        expect(useBtn.disabled).toBe(true)
        await act(async () => { fireEvent.click(useBtn) })
        await flush()
        expect(reparentSpy).not.toHaveBeenCalled()
    })
})

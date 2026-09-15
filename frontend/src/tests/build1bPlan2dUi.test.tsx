/**
 * Build 1B §B — TRUE 2D BIM plan PANEL (UI tests).
 *   §PB3 — the plan renders rooms (exact vs approximate), the walker marker, and
 *          honest provenance; it is shown SIMULTANEOUSLY with the Walkthrough.
 *   §PB4 — VIEW-ONLY interaction: clicking a room SELECTS the same bimSpaceId and
 *          NEVER moves the walker; "Enter Walkthrough Here" reuses the safe spawn.
 *
 * The component is driven through its `loadOverlay` injection seam with a faithful
 * in-memory overlay whose plan view-model is produced by the REAL pure projection
 * (projectBim2dPlan) — so identities/tiers/geometry under test are genuine.
 */
import { render, screen, act, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { Bim2dPlanPanel } from '../components/spatial/Bim2dPlanPanel'
import {
    projectBim2dPlan,
    computePlanFitTransform,
    worldToScreen,
    type Bim2dPlanProjectionInput,
    type PlanWalkerInput,
} from '../components/spatial/bim2dPlanProjection'

// --- shared fixture (same identities the 3D scene would use) ---------------
const rooms: Bim2dPlanProjectionInput['rooms'] = [
    {
        bimSpaceId: '0xExact', originalBimLabel: 'Uptake 01', storeyId: 's1',
        worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 4, y: 4, z: 3 } },
        exactOuterLoop: [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 4 }, { x: 0, y: 4 }],
    },
    {
        bimSpaceId: '0xApprox', originalBimLabel: 'Injection Room 01', storeyId: 's1',
        worldRange: { low: { x: 10, y: 0, z: 0 }, high: { x: 14, y: 3, z: 3 } },
    },
]
const assignments: Bim2dPlanProjectionInput['assignments'] = [
    { bimSpaceId: '0xExact', clinicalFunction: 'UPTAKE_ROOM', mrtDisplayName: 'Uptake 01' },
]

// --- spies proving VIEW-ONLY behavior --------------------------------------
const selectSpy = vi.fn()
const fitSpy = vi.fn(async () => true)
const enterHereSpy = vi.fn(async () => ({ ok: true as const, provenance: 'INTERIOR_ANCHOR' }))
// A walker mover would be a DEFECT; we assert it is NEVER called by the plan.
const walkerMoveSpy = vi.fn()

let cameraMode = 'WALKTHROUGH'
let selectedBimSpaceId: string | undefined
let walker: PlanWalkerInput | undefined = { active: true, eye: { x: 2, y: 2, z: 1.65 }, yaw: 0, activeStoreyId: 's1' }
const programListeners = new Set<() => void>()
let walkListener: ((s: PlanWalkerInput | undefined) => void) | undefined

function makeOverlay() {
    return {
        getActiveCameraMode: () => cameraMode,
        getBim2dPlanView: (opts?: { walker?: PlanWalkerInput }) => projectBim2dPlan({
            rooms, assignments, storeyId: 's1', selectedBimSpaceId, walker: opts?.walker,
        }),
        subscribeClinicalProgram: (fn: () => void) => { programListeners.add(fn); return () => programListeners.delete(fn) },
        subscribeWalkthroughState: async (fn: (s: PlanWalkerInput | undefined) => void) => {
            walkListener = fn
            fn(walker) // emit current immediately (matches real controller)
            return () => { walkListener = undefined }
        },
        setClinicalProgramSelectedSpace: (id: string | undefined) => { selectedBimSpaceId = id; selectSpy(id); programListeners.forEach((l) => l()) },
        fitViewToClinicalRoom: fitSpy,
        enterWalkthroughAtClinicalRoom: enterHereSpy,
        // Present ONLY to prove the plan never calls a walker-move path.
        resetWalkthroughMode: walkerMoveSpy,
    } as unknown as typeof import('../components/spatial/spatialAssetOverlay')
}

const loadOverlay = () => Promise.resolve(makeOverlay())

async function renderPanel() {
    let utils!: ReturnType<typeof render>
    await act(async () => {
        utils = render(<Bim2dPlanPanel loadOverlay={loadOverlay} />)
        await Promise.resolve()
        await Promise.resolve()
    })
    return utils
}

beforeEach(() => {
    vi.clearAllMocks()
    cameraMode = 'WALKTHROUGH'
    selectedBimSpaceId = undefined
    walker = { active: true, eye: { x: 2, y: 2, z: 1.65 }, yaw: 0, activeStoreyId: 's1' }
    programListeners.clear()
    walkListener = undefined
})

// ===========================================================================
// §PB3 — RENDER (simultaneous with Walkthrough; exact vs approximate; walker)
// ===========================================================================

describe('§PB3 2D plan panel render', () => {
    it('renders the plan while the Walkthrough is active (simultaneous)', async () => {
        await renderPanel()
        expect(screen.getByLabelText('2D BIM floor plan')).toBeInTheDocument()
        expect(screen.getByText(/live with Walkthrough/i)).toBeInTheDocument()
    })

    it('renders each room keyed by the SAME bimSpaceId (shared identity)', async () => {
        const { container } = await renderPanel()
        expect(container.querySelector('[data-bim-space-id="0xExact"]')).toBeTruthy()
        expect(container.querySelector('[data-bim-space-id="0xApprox"]')).toBeTruthy()
    })

    it('tags the range-only room as an approximation and the exact room as exact', async () => {
        const { container } = await renderPanel()
        expect(container.querySelector('[data-bim-space-id="0xExact"]')!.getAttribute('data-footprint-source')).toBe('EXACT_ROOM_MESH')
        expect(container.querySelector('[data-bim-space-id="0xApprox"]')!.getAttribute('data-footprint-source')).toBe('BIM_RANGE_APPROXIMATION')
    })

    it('draws the walker marker from the single walkthrough read-model', async () => {
        await renderPanel()
        expect(screen.getByTestId('plan-walker')).toBeInTheDocument()
    })

    it('surfaces honest provenance (exact vs approx counts)', async () => {
        await renderPanel()
        expect(screen.getByText(/1 exact/i)).toBeInTheDocument()
        expect(screen.getByText(/1 approx/i)).toBeInTheDocument()
    })

    it('hides the walker marker when the walkthrough state goes inactive', async () => {
        await renderPanel()
        expect(screen.getByTestId('plan-walker')).toBeInTheDocument()
        await act(async () => {
            walker = undefined
            walkListener?.(undefined)
            await Promise.resolve()
        })
        expect(screen.queryByTestId('plan-walker')).not.toBeInTheDocument()
    })
})

// ===========================================================================
// §PB4 — VIEW-ONLY INTERACTION (select shares bimSpaceId; never moves walker)
// ===========================================================================

describe('§PB4 plan interaction is view-only', () => {
    it('clicking a room selects the SAME bimSpaceId and never moves the walker', async () => {
        const { container } = await renderPanel()
        const svg = container.querySelector('svg.bim2d-plan-svg') as SVGSVGElement
        // jsdom has no layout; stub the bounding rect so the click maps into the view
        // 1:1 with the SVG's internal 260x200 coordinate system.
        svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 260, height: 200, right: 260, bottom: 200, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect
        // Compute the exact screen pixel for a point inside the exact room using the
        // SAME auto-fit transform the panel uses (bounds of the projected view).
        const view = projectBim2dPlan({ rooms, assignments, storeyId: 's1' })
        const t = computePlanFitTransform(view.bounds, 260, 200)
        const target = worldToScreen(t, { x: 2, y: 2 }) // interior of the exact room
        await act(async () => {
            fireEvent.click(svg, { clientX: target.x, clientY: target.y })
            await Promise.resolve()
        })
        // A room was selected (shared identity) ...
        expect(selectSpy).toHaveBeenCalled()
        const selectedId = selectSpy.mock.calls[0][0]
        expect(selectedId).toBe('0xExact')
        // ... and NO walker-move path was invoked by the plan.
        expect(walkerMoveSpy).not.toHaveBeenCalled()
    })

    it('Enter Walkthrough Here reuses the safe spawn and is disabled with no selection', async () => {
        await renderPanel()
        const btn = screen.getByRole('button', { name: /Enter Walkthrough Here/i })
        expect(btn).toBeDisabled() // nothing selected yet
        // Select a room via the program subscription, then the button enables.
        await act(async () => {
            selectedBimSpaceId = '0xExact'
            programListeners.forEach((l) => l())
            await Promise.resolve()
        })
        expect(btn).not.toBeDisabled()
        await act(async () => {
            fireEvent.click(btn)
            await Promise.resolve()
        })
        expect(enterHereSpy).toHaveBeenCalledWith({ bimSpaceId: '0xExact' })
        expect(walkerMoveSpy).not.toHaveBeenCalled()
    })

})

// ===========================================================================
// §PB5 — BUILD 1B UX CORRECTION (mini-plan): no pan/zoom/fit toolbar; label
//        density (only Clinical Program + selected + hover); dismissible × with a
//        compact reopen and NO viewport-blocking layer while closed.
// ===========================================================================

describe('§PB5 mini-plan UX correction', () => {
    it('has NO Fit / ＋ / － / arrow toolbar (MINI_PLAN_CONTROL_ROW_REMOVED)', async () => {
        await renderPanel()
        for (const label of ['Fit plan', 'Zoom in', 'Zoom out', 'Pan up', 'Pan down', 'Pan left', 'Pan right']) {
            expect(screen.queryByLabelText(label)).toBeNull()
        }
        expect(document.querySelector('.bim2d-plan-toolbar')).toBeFalsy()
    })

    it('permanently labels ONLY the Clinical Program room (not all rooms)', async () => {
        const { container } = await renderPanel()
        const labels = Array.from(container.querySelectorAll('.bim2d-plan-room-label'))
        // Two rooms, but only the assigned Uptake 01 is permanently labelled.
        expect(labels).toHaveLength(1)
        const clinical = container.querySelector('.bim2d-plan-room-label--clinical')
        expect(clinical).toBeTruthy()
        expect(clinical!.textContent).toContain('[U]')
        expect(clinical!.textContent).toContain('Uptake 01')
        // The ordinary (unassigned) room is NOT permanently labelled.
        expect(container.querySelector('[data-label-kind="NONE"]')).toBeFalsy()
    })

    it('labels the SELECTED room in addition to the Clinical Program room', async () => {
        const { container } = await renderPanel()
        await act(async () => {
            selectedBimSpaceId = '0xApprox' // the ordinary room becomes selected
            programListeners.forEach((l) => l())
            await Promise.resolve()
        })
        const kinds = Array.from(container.querySelectorAll('.bim2d-plan-room-label'))
            .map((n) => n.getAttribute('data-label-kind'))
            .sort()
        expect(kinds).toEqual(['CLINICAL', 'SELECTED'])
    })

    it('closes to a compact "2D Plan" chip and reopens, with NO panel body while closed', async () => {
        await renderPanel()
        const close = screen.getByLabelText('Close 2D plan')
        await act(async () => { fireEvent.click(close); await Promise.resolve() })
        // Closed: no panel body, no SVG => nothing can block the 3D viewport.
        expect(screen.queryByLabelText('2D BIM floor plan')).toBeNull()
        expect(document.querySelector('svg.bim2d-plan-svg')).toBeFalsy()
        const reopen = screen.getByLabelText('Open 2D floor plan')
        expect(reopen).toBeInTheDocument()
        // Reopen restores the plan (and re-projects, so the walker returns).
        await act(async () => { fireEvent.click(reopen); await Promise.resolve(); await Promise.resolve() })
        expect(screen.getByLabelText('2D BIM floor plan')).toBeInTheDocument()
        expect(screen.getByTestId('plan-walker')).toBeInTheDocument()
    })
})

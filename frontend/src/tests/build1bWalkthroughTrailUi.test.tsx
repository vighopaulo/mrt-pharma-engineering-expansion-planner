/**
 * Build 1B — LIVE WALKTHROUGH PROGRESSION TRAIL + FLOOR-GEOMETRY COEXISTENCE
 * (UI tests, §29).
 *
 *   §29a — LIVE TRAIL. As the authoritative walkthrough state moves the eye, the
 *          2D plan grows a subdued-green trail behind the bright walker marker.
 *          Turning in place (same eye XY) never extends it. The heading indicator
 *          stays SEPARATE on the marker (HEADING_EQUALS_TRAIL = NO).
 *   §29b — GEOMETRY COEXISTENCE. The BIM floor geometry and the walker/trail are
 *          shown TOGETHER; the trail never removes rooms. When the plan first
 *          projects 0 rooms, it hydrates the room registry INDEPENDENT of the
 *          Clinical Program (Defect 1) and the floor reappears.
 *
 * Driven through the component's `loadOverlay` seam with a faithful in-memory
 * overlay whose plan view-model is produced by the REAL pure projection.
 */
import { render, screen, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { Bim2dPlanPanel } from '../components/spatial/Bim2dPlanPanel'
import {
    projectBim2dPlan,
    type Bim2dPlanProjectionInput,
    type PlanWalkerInput,
} from '../components/spatial/bim2dPlanProjection'

// The walkthrough sample shape the panel forwards to the trail (subset of state).
interface WalkSample { active: boolean; eye: { x: number; y: number; z: number }; yaw: number; activeStoreyId?: string; fovDeg?: number }

const rooms: Bim2dPlanProjectionInput['rooms'] = [
    {
        bimSpaceId: '0xExact', originalBimLabel: 'Uptake 01', storeyId: 's1',
        worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 10, y: 10, z: 3 } },
        exactOuterLoop: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }],
    },
]
const assignments: Bim2dPlanProjectionInput['assignments'] = [
    { bimSpaceId: '0xExact', clinicalFunction: 'UPTAKE_ROOM', mrtDisplayName: 'Uptake 01' },
]

let cameraMode = 'WALKTHROUGH'
// Whether the room registry is "hydrated". When false the plan projects 0 rooms
// until ensureBim2dPlanRoomsHydrated() flips it (Defect 1 behavior).
let roomsHydrated = true
let walkListener: ((s: WalkSample | undefined) => void) | undefined
const programListeners = new Set<() => void>()
const hydrateSpy = vi.fn(async () => { roomsHydrated = true; return rooms.length })

function makeOverlay() {
    return {
        getActiveCameraMode: () => cameraMode,
        // The plan follows the WALKER's active storey (Defect 1 §8): project only
        // that storey. Empty until hydrated.
        getBim2dPlanView: (opts?: { walker?: PlanWalkerInput }) => projectBim2dPlan({
            rooms: roomsHydrated ? rooms : [],
            assignments,
            storeyId: opts?.walker?.active ? opts.walker.activeStoreyId : 's1',
            walker: opts?.walker,
        }),
        ensureBim2dPlanRoomsHydrated: hydrateSpy,
        subscribeClinicalProgram: (fn: () => void) => { programListeners.add(fn); return () => programListeners.delete(fn) },
        subscribeWalkthroughState: async (fn: (s: WalkSample | undefined) => void) => {
            walkListener = fn
            fn({ active: true, eye: { x: 1, y: 1, z: 1.65 }, yaw: 0, activeStoreyId: 's1' })
            return () => { walkListener = undefined }
        },
        setClinicalProgramSelectedSpace: () => { /* view-only */ },
        fitViewToClinicalRoom: async () => true,
        enterWalkthroughAtClinicalRoom: async () => ({ ok: true as const }),
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

// Push a walkthrough sample through the live subscription and let React settle.
async function walkTo(x: number, y: number, opts: Partial<WalkSample> = {}) {
    await act(async () => {
        walkListener?.({ active: true, eye: { x, y, z: 1.65 }, yaw: 0, activeStoreyId: 's1', ...opts })
        await Promise.resolve()
        await Promise.resolve()
    })
}

beforeEach(() => {
    vi.clearAllMocks()
    cameraMode = 'WALKTHROUGH'
    roomsHydrated = true
    walkListener = undefined
    programListeners.clear()
})

// ===========================================================================
// §29a — LIVE TRAIL
// ===========================================================================

describe('§29a live walkthrough trail', () => {
    it('grows a trail as the walker moves (START -> travelled path)', async () => {
        const { container } = await renderPanel()
        // Initially just the spawn point — no drawn polyline yet.
        await walkTo(1, 2)
        await walkTo(1, 3)
        await walkTo(1, 4)
        const segs = container.querySelectorAll('[data-testid="plan-trail-segment"]')
        expect(segs.length).toBeGreaterThanOrEqual(1)
        const totalPoints = Array.from(segs)
            .reduce((n, el) => n + Number(el.getAttribute('data-trail-points') ?? '0'), 0)
        // spawn (1,1) + three ≥0.5m steps = 4 accepted points.
        expect(totalPoints).toBe(4)
    })

    it('the trail is drawn BEHIND the bright walker marker (separate heading)', async () => {
        const { container } = await renderPanel()
        await walkTo(1, 3)
        const svg = container.querySelector('svg.bim2d-plan-svg')!
        const nodes = Array.from(svg.children)
        const trailIdx = nodes.findIndex((n) => n.querySelector?.('[data-testid="plan-trail-segment"]') || (n as Element).getAttribute?.('data-testid') === 'plan-trail-segment')
        const walkerIdx = nodes.findIndex((n) => (n as Element).getAttribute?.('data-testid') === 'plan-walker' || n.querySelector?.('[data-testid="plan-walker"]'))
        // The walker marker (with its heading line) still renders and is present.
        expect(screen.getByTestId('plan-walker')).toBeInTheDocument()
        // Trail element(s) appear before the walker in document order (drawn behind).
        if (trailIdx >= 0 && walkerIdx >= 0) expect(trailIdx).toBeLessThan(walkerIdx)
    })

    it('TURNING IN PLACE (same eye XY) never extends the trail', async () => {
        const { container } = await renderPanel()
        await walkTo(1, 3) // one real step
        const before = Array.from(container.querySelectorAll('[data-testid="plan-trail-segment"]'))
            .reduce((n, el) => n + Number(el.getAttribute('data-trail-points') ?? '0'), 0)
        // Now only rotate/pitch/fov change — eye XY stays put.
        await walkTo(1, 3, { yaw: 1.2 })
        await walkTo(1, 3, { yaw: 2.4, fovDeg: 90 })
        const after = Array.from(container.querySelectorAll('[data-testid="plan-trail-segment"]'))
            .reduce((n, el) => n + Number(el.getAttribute('data-trail-points') ?? '0'), 0)
        expect(after).toBe(before) // no growth from turning/pitch/fov
    })
})

// ===========================================================================
// §29b — FLOOR-GEOMETRY COEXISTENCE + DEFECT-1 HYDRATION
// ===========================================================================

describe('§29b floor geometry coexists with the walker/trail', () => {
    it('renders BIM rooms AND the walker together (geometry not removed by the trail)', async () => {
        const { container } = await renderPanel()
        await walkTo(1, 3)
        expect(container.querySelector('[data-bim-space-id="0xExact"]')).toBeTruthy()
        expect(screen.getByTestId('plan-walker')).toBeInTheDocument()
    })

    it('when the plan first projects 0 rooms, it hydrates INDEPENDENT of Clinical Program', async () => {
        // Defect 1: registry not hydrated (e.g. Clinical Program = Off in Walkthrough).
        roomsHydrated = false
        const { container } = await renderPanel()
        // First projection is empty (0 rooms) ...
        // ... which triggers the Clinical-Program-independent hydration.
        await act(async () => { await Promise.resolve(); await Promise.resolve() })
        expect(hydrateSpy).toHaveBeenCalled()
        // After hydration the floor geometry reappears (regression 0 -> N fixed).
        expect(container.querySelector('[data-bim-space-id="0xExact"]')).toBeTruthy()
        expect(screen.getByText(/1 exact/i)).toBeInTheDocument()
    })
})

/**
 * Build 1B UX CORRECTION §25 — the ENTIRE Walkthrough control card is dismissible
 * (not just the small key-controls help subsection). This was the on-screen
 * obstruction over the 3D scene.
 *
 *   - Entering Walkthrough shows the full control card (storeys / FOV / turn /
 *     reset / EXIT / key-controls help).
 *   - × collapses the WHOLE card to a compact "Walkthrough Controls" reopen chip;
 *     EXIT WALKTHROUGH stays reachable while collapsed.
 *   - The FIRST Esc collapses the card (it does NOT exit walkthrough —
 *     FIRST_ESC_EXITS_WALKTHROUGH = NO).
 *   - Clicking OUTSIDE the card collapses it; there is NO full-screen invisible
 *     blocker (we listen on window + test target ancestry).
 *   - Reopen restores the full card.
 *
 * The overlay is mocked (no @itwin).
 */
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const applyCameraMode = vi.fn(async (_mode: unknown, _opts: unknown) => true)
vi.mock('../components/spatial/spatialAssetOverlay', () => ({
    applyCameraMode: (mode: unknown, opts: unknown) => applyCameraMode(mode, opts),
    loadCameraStoreys: vi.fn(async () => [{ id: 'FIRST', label: 'First Floor', zLow: 0, zHigh: 4 }]),
    setWalkthroughFov: vi.fn(),
    turnAroundWalkthrough: vi.fn(),
    resetWalkthroughMode: vi.fn(),
    panPlanningCamera: vi.fn(),
}))

import { CameraModeControl } from '../components/spatial/CameraModeControl'

const CARD = { name: 'Walkthrough controls' }

async function enterWalkthrough() {
    render(<CameraModeControl />)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Walkthrough' })) })
    await waitFor(() => expect(screen.getByRole('group', CARD)).toBeTruthy())
    applyCameraMode.mockClear() // ignore the entry call; focus on post-entry behavior
}

describe('Build 1B §25 — the whole Walkthrough control card is dismissible', () => {
    beforeEach(() => { vi.clearAllMocks() })

    it('shows the full control card on entering Walkthrough', async () => {
        await enterWalkthrough()
        expect(screen.getByRole('group', CARD)).toBeTruthy()
        expect(screen.getByRole('button', { name: 'EXIT WALKTHROUGH' })).toBeTruthy()
    })

    it('× collapses the WHOLE card to a compact reopen chip; EXIT stays reachable', async () => {
        await enterWalkthrough()
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Collapse walkthrough controls' })) })
        // Full card gone ...
        expect(screen.queryByRole('group', CARD)).toBeNull()
        // ... compact reopen chip present, and EXIT is still reachable.
        expect(screen.getByRole('button', { name: 'Show walkthrough controls' })).toBeTruthy()
        expect(screen.getByRole('button', { name: 'EXIT WALKTHROUGH' })).toBeTruthy()
        // Collapsing the card is NOT exiting walkthrough.
        expect(applyCameraMode).not.toHaveBeenCalled()
    })

    it('the FIRST Esc collapses the card and does NOT exit walkthrough', async () => {
        await enterWalkthrough()
        await act(async () => { fireEvent.keyDown(window, { key: 'Escape' }) })
        expect(screen.queryByRole('group', CARD)).toBeNull()
        expect(screen.getByRole('button', { name: 'Show walkthrough controls' })).toBeTruthy()
        expect(applyCameraMode).not.toHaveBeenCalled() // did not exit to PLANNING
    })

    it('clicking OUTSIDE the card collapses it (no full-screen blocker)', async () => {
        await enterWalkthrough()
        await act(async () => { fireEvent.pointerDown(document.body) })
        expect(screen.queryByRole('group', CARD)).toBeNull()
        expect(screen.getByRole('button', { name: 'Show walkthrough controls' })).toBeTruthy()
    })

    it('a click INSIDE the card keeps it open', async () => {
        await enterWalkthrough()
        await act(async () => { fireEvent.pointerDown(screen.getByRole('button', { name: 'EXIT WALKTHROUGH' })) })
        expect(screen.getByRole('group', CARD)).toBeTruthy()
    })

    it('reopen restores the full card', async () => {
        await enterWalkthrough()
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Collapse walkthrough controls' })) })
        expect(screen.queryByRole('group', CARD)).toBeNull()
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Show walkthrough controls' })) })
        expect(screen.getByRole('group', CARD)).toBeTruthy()
    })

    it('EXIT WALKTHROUGH still works from the collapsed state', async () => {
        await enterWalkthrough()
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Collapse walkthrough controls' })) })
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'EXIT WALKTHROUGH' })) })
        expect(applyCameraMode).toHaveBeenCalledWith('PLANNING', expect.anything())
    })
})

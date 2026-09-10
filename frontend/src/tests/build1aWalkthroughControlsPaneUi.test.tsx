/**
 * Build 1A walkthrough final UX — UI test (§15.1-6): the Walkthrough controls/
 * help pane is dismissible (× / outside-click / Esc) and reopenable, and when
 * closed it is simply not rendered (no invisible pointer-blocking layer). The
 * overlay is mocked (no @itwin).
 */
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../components/spatial/spatialAssetOverlay', () => ({
    applyCameraMode: vi.fn(async () => true),
    loadCameraStoreys: vi.fn(async () => [{ id: 'FIRST', label: 'First Floor', zLow: 0, zHigh: 4 }]),
    setWalkthroughFov: vi.fn(),
    turnAroundWalkthrough: vi.fn(),
    resetWalkthroughMode: vi.fn(),
}))

import { CameraModeControl } from '../components/spatial/CameraModeControl'

// Build 1A trackpad UX: help wording updated to Mac-trackpad phrasing
// ("Click + drag: Look around · Two-finger scroll: … · W/S: Walk …").
const HELP = /Click \+ drag: Look around/

async function enterWalkthrough() {
    render(<CameraModeControl />)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Walkthrough' })) })
    await waitFor(() => expect(screen.getByText(HELP)).toBeTruthy())
}

describe('Build 1A walkthrough §15 — dismissible controls pane', () => {
    beforeEach(() => { vi.clearAllMocks() })

    it('the controls/help pane is shown on entering Walkthrough', async () => {
        await enterWalkthrough()
        expect(screen.getByText(HELP)).toBeTruthy()
    })

    it('× Close button dismisses the pane', async () => {
        await enterWalkthrough()
        fireEvent.click(screen.getByRole('button', { name: 'Close controls' }))
        expect(screen.queryByText(HELP)).toBeNull()
    })

    it('the pane can be reopened via the Controls affordance', async () => {
        await enterWalkthrough()
        fireEvent.click(screen.getByRole('button', { name: 'Close controls' }))
        expect(screen.queryByText(HELP)).toBeNull()
        fireEvent.click(screen.getByRole('button', { name: 'Show walkthrough controls' }))
        expect(screen.getByText(HELP)).toBeTruthy()
    })

    it('clicking OUTSIDE the pane dismisses it', async () => {
        await enterWalkthrough()
        await act(async () => { fireEvent.pointerDown(document.body) })
        expect(screen.queryByText(HELP)).toBeNull()
    })

    it('a click INSIDE the pane keeps it open', async () => {
        await enterWalkthrough()
        await act(async () => { fireEvent.pointerDown(screen.getByText(HELP)) })
        expect(screen.getByText(HELP)).toBeTruthy()
    })

    it('Esc closes the open pane (first Esc)', async () => {
        await enterWalkthrough()
        await act(async () => { fireEvent.keyDown(window, { key: 'Escape' }) })
        expect(screen.queryByText(HELP)).toBeNull()
    })

    it('when closed the pane is NOT in the DOM (no invisible blocking layer)', async () => {
        await enterWalkthrough()
        fireEvent.click(screen.getByRole('button', { name: 'Close controls' }))
        // The reopen affordance is a small button; the full help pane is gone.
        expect(screen.queryByRole('dialog', { name: 'Walkthrough controls' })).toBeNull()
        expect(screen.getByRole('button', { name: 'Show walkthrough controls' })).toBeTruthy()
    })
})

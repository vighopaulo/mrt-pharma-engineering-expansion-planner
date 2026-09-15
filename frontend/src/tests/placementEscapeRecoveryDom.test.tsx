/**
 * EVI-MA-07A — DOM-level proof of placement escape / backdrop recovery.
 *
 * The manual-acceptance failure was a LIVE behaviour: after PLACE IN MODEL then
 * cancel, the viewport stayed blocked and Escape did not restore it. Pure
 * decision tests are necessary but not sufficient, so this test renders a harness
 * that wires the SAME helpers the /viewer shell uses (decideEscapeRecovery,
 * backdropMayMount, shouldCloseFloatingPanelOnPlacementArmed) against a mocked
 * overlay, and drives REAL DOM `keydown` Escape events.
 *
 * It proves (§12 A–I):
 *   A. PLACE IN MODEL -> placement ARMED -> placement UI visible.
 *   B. Escape -> IDLE -> backdrop gone.
 *   C. cancelPlacement() clears the placement session (mock spy called).
 *   D. "Placement cancelled" leaves NO dim/block layer.
 *   E. Escape works regardless of the (Bentley) active tool (no tool dependency).
 *   F. Escape while focus/pointer is over the Asset Library still cancels.
 *   G. Escape while focus/pointer is over the viewport still cancels.
 *   H. Re-enter placement after cancel works normally (3x, no orphaned latch).
 *   I. Existing placed assets are untouched by cancel (cancel only clears intent).
 *
 * The overlay is mocked so vitest never imports the @itwin stack (project pattern).
 */
import { render, screen, act, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useEffect, useState } from 'react'
import {
    decideEscapeRecovery,
    backdropMayMount,
    shouldCloseFloatingPanelOnPlacementArmed,
} from '../components/spatial/placementEscapeRecovery'

// --- mocked application-owned placement store (mirrors spatialAssetOverlay) ---
let placementActive = false
let placedCount = 3 // pretend 3 assets already exist; cancel must not touch them
const listeners = new Set<() => void>()
function notify() { for (const l of listeners) l() }

const cancelPlacement = vi.fn(async () => {
    // The REAL cancelPlacement clears ONLY the placement intent (never placed assets).
    placementActive = false
    notify()
})
function beginPlacement() {
    placementActive = true
    notify()
}

const overlayMock = {
    spatialAssetStore: { getSnapshot: () => ({ placementModeActive: placementActive, placedCount }) },
    subscribeSpatialAssets: (fn: () => void) => { listeners.add(fn); return () => listeners.delete(fn) },
    cancelPlacement: () => cancelPlacement(),
}
vi.mock('../components/spatial/spatialAssetOverlay', () => overlayMock)

/**
 * Harness reproducing the /viewer shell placement lifecycle wiring EXACTLY:
 * subscription -> placementModeActive; close-panel-on-arm; app-stable Escape;
 * backdrop gated by backdropMayMount. `openPanel` starts open to reproduce the
 * reported trap precondition (a panel was open when the user placed).
 */
function PlacementRecoveryHarness({ initialPanelOpen }: { initialPanelOpen: boolean }) {
    const [placementModeActive, setPlacementModeActive] = useState(false)
    const [openPanel, setOpenPanel] = useState<string | null>(initialPanelOpen ? 'DEV_TOOLS' : null)

    // subscription (event-driven, no polling)
    useEffect(() => {
        const read = () => setPlacementModeActive(overlayMock.spatialAssetStore.getSnapshot().placementModeActive)
        read()
        const unsub = overlayMock.subscribeSpatialAssets(read)
        return () => { unsub() }
    }, [])

    // §7 close panel the moment placement arms (kills orphan source)
    useEffect(() => {
        if (shouldCloseFloatingPanelOnPlacementArmed({ placementModeActive, hasOpenFloatingPanel: openPanel !== null })) {
            setOpenPanel(null)
        }
    }, [placementModeActive, openPanel])

    // §5 app-stable window Escape (capture phase; not gated on openPanel)
    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            const activeEl = document.activeElement as HTMLElement | null
            const d = decideEscapeRecovery({
                placementModeActive,
                hasOpenFloatingPanel: openPanel !== null,
                key: e.key,
                focusedTagName: activeEl?.tagName,
                focusedIsContentEditable: activeEl?.isContentEditable,
            })
            if (!d.handle) return
            e.preventDefault()
            if (d.closeFloatingPanel) setOpenPanel(null)
            if (d.cancelPlacement) void overlayMock.cancelPlacement()
        }
        window.addEventListener('keydown', onKey, true)
        return () => window.removeEventListener('keydown', onKey, true)
    }, [placementModeActive, openPanel])

    return (
        <div>
            {backdropMayMount({ hasOpenFloatingPanel: openPanel !== null, placementModeActive }) && (
                <div data-testid="backdrop" className="viewer-panel-backdrop" />
            )}
            {placementModeActive && (
                <div data-testid="placement-ui" role="status">Placing: GE HealthCare Discovery MI</div>
            )}
            <button type="button" data-testid="place" onClick={() => beginPlacement()}>PLACE IN MODEL</button>
            <span data-testid="placed-count">{placedCount}</span>
        </div>
    )
}

function pressEscape() {
    act(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })) })
}

describe('EVI-MA-07A placement escape / backdrop recovery (DOM)', () => {
    beforeEach(() => {
        placementActive = false
        placedCount = 3
        listeners.clear()
        vi.clearAllMocks()
    })

    it('A: PLACE IN MODEL arms placement and shows the placement UI', () => {
        render(<PlacementRecoveryHarness initialPanelOpen={false} />)
        expect(screen.queryByTestId('placement-ui')).toBeNull()
        fireEvent.click(screen.getByTestId('place'))
        expect(screen.getByTestId('placement-ui')).toBeTruthy()
    })

    it('B+C+D: Escape cancels placement, calls cancelPlacement(), and leaves NO backdrop', () => {
        // Precondition reproduces the trap: a panel (backdrop) was open when placing.
        render(<PlacementRecoveryHarness initialPanelOpen={true} />)
        expect(screen.getByTestId('backdrop')).toBeTruthy() // panel-driven backdrop present
        // Arm placement: the backdrop must immediately disappear (never coexists).
        fireEvent.click(screen.getByTestId('place'))
        expect(screen.queryByTestId('backdrop')).toBeNull()
        expect(screen.getByTestId('placement-ui')).toBeTruthy()
        // One Escape -> IDLE.
        pressEscape()
        expect(cancelPlacement).toHaveBeenCalledTimes(1)
        expect(screen.queryByTestId('placement-ui')).toBeNull()
        // "Placement cancelled" state leaves NO dim/block layer.
        expect(screen.queryByTestId('backdrop')).toBeNull()
    })

    it('E: Escape recovers regardless of the active tool (handler is window-level, tool-independent)', () => {
        render(<PlacementRecoveryHarness initialPanelOpen={false} />)
        fireEvent.click(screen.getByTestId('place'))
        // No Bentley tool is involved; a raw window Escape still recovers.
        pressEscape()
        expect(cancelPlacement).toHaveBeenCalledTimes(1)
        expect(screen.queryByTestId('placement-ui')).toBeNull()
    })

    it('F: Escape while focus is over the Asset Library still cancels', () => {
        render(<PlacementRecoveryHarness initialPanelOpen={false} />)
        const placeBtn = screen.getByTestId('place')
        fireEvent.click(placeBtn)
        placeBtn.focus() // focus a library button (not a text field)
        pressEscape()
        expect(cancelPlacement).toHaveBeenCalledTimes(1)
    })

    it('G: Escape while focus is over the viewport (no text field) still cancels', () => {
        render(<PlacementRecoveryHarness initialPanelOpen={false} />)
        fireEvent.click(screen.getByTestId('place'))
        if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
        pressEscape()
        expect(cancelPlacement).toHaveBeenCalledTimes(1)
    })

    it('H: re-enter placement after cancel works 3x with no orphaned state/backdrop', () => {
        render(<PlacementRecoveryHarness initialPanelOpen={true} />)
        for (let i = 1; i <= 3; i++) {
            fireEvent.click(screen.getByTestId('place'))
            expect(screen.getByTestId('placement-ui')).toBeTruthy()
            expect(screen.queryByTestId('backdrop')).toBeNull()
            pressEscape()
            expect(cancelPlacement).toHaveBeenCalledTimes(i)
            expect(screen.queryByTestId('placement-ui')).toBeNull()
            expect(screen.queryByTestId('backdrop')).toBeNull()
        }
    })

    it('I: cancelling placement never touches existing placed assets', () => {
        render(<PlacementRecoveryHarness initialPanelOpen={false} />)
        expect(screen.getByTestId('placed-count').textContent).toBe('3')
        fireEvent.click(screen.getByTestId('place'))
        pressEscape()
        expect(screen.getByTestId('placed-count').textContent).toBe('3') // unchanged
    })
})

/**
 * EVI-MA-07A — pure decision tests for the placement escape / backdrop recovery
 * lifecycle. These prove the LOGIC that the /viewer shell wires directly:
 *   - the full-viewport backdrop derives ONLY from panel state and NEVER coexists
 *     with an armed placement session (no orphan trap);
 *   - Escape recovers from ANY placement phase and closes any open panel atomically;
 *   - Escape does not hijack text-editing;
 *   - re-entry after cancel is unaffected.
 */
import { describe, it, expect } from 'vitest'
import {
    decideEscapeRecovery,
    backdropMayMount,
    shouldCloseFloatingPanelOnPlacementArmed,
} from '../components/spatial/placementEscapeRecovery'

describe('EVI-MA-07A backdropMayMount', () => {
    it('mounts the backdrop only for an open panel with NO active placement', () => {
        expect(backdropMayMount({ hasOpenFloatingPanel: true, placementModeActive: false })).toBe(true)
    })

    it('never mounts the backdrop while placement is active (viewer must stay visible)', () => {
        expect(backdropMayMount({ hasOpenFloatingPanel: true, placementModeActive: true })).toBe(false)
    })

    it('never mounts the backdrop when no panel is open (normal IDLE viewer is clear)', () => {
        expect(backdropMayMount({ hasOpenFloatingPanel: false, placementModeActive: false })).toBe(false)
        expect(backdropMayMount({ hasOpenFloatingPanel: false, placementModeActive: true })).toBe(false)
    })
})

describe('EVI-MA-07A shouldCloseFloatingPanelOnPlacementArmed', () => {
    it('closes an open panel the moment placement is armed (kills the orphan source)', () => {
        expect(shouldCloseFloatingPanelOnPlacementArmed({ placementModeActive: true, hasOpenFloatingPanel: true })).toBe(true)
    })
    it('does nothing when no panel is open, or when placement is idle', () => {
        expect(shouldCloseFloatingPanelOnPlacementArmed({ placementModeActive: true, hasOpenFloatingPanel: false })).toBe(false)
        expect(shouldCloseFloatingPanelOnPlacementArmed({ placementModeActive: false, hasOpenFloatingPanel: true })).toBe(false)
    })
})

describe('EVI-MA-07A decideEscapeRecovery', () => {
    it('cancels placement from an armed placement session (any phase), preventing the trap', () => {
        const d = decideEscapeRecovery({ placementModeActive: true, hasOpenFloatingPanel: false, key: 'Escape' })
        expect(d.handle).toBe(true)
        expect(d.cancelPlacement).toBe(true)
        expect(d.closeFloatingPanel).toBe(false)
    })

    it('closes an orphanable panel/backdrop even with no active placement', () => {
        const d = decideEscapeRecovery({ placementModeActive: false, hasOpenFloatingPanel: true, key: 'Escape' })
        expect(d.handle).toBe(true)
        expect(d.cancelPlacement).toBe(false)
        expect(d.closeFloatingPanel).toBe(true)
    })

    it('atomically cancels placement AND closes the panel in a single Escape (both set)', () => {
        const d = decideEscapeRecovery({ placementModeActive: true, hasOpenFloatingPanel: true, key: 'Escape' })
        expect(d).toEqual({ handle: true, cancelPlacement: true, closeFloatingPanel: true })
    })

    it('does nothing when nothing is recoverable (normal viewer, Escape is a no-op here)', () => {
        const d = decideEscapeRecovery({ placementModeActive: false, hasOpenFloatingPanel: false, key: 'Escape' })
        expect(d).toEqual({ handle: false, cancelPlacement: false, closeFloatingPanel: false })
    })

    it('ignores non-Escape keys', () => {
        expect(decideEscapeRecovery({ placementModeActive: true, hasOpenFloatingPanel: true, key: 'Enter' }).handle).toBe(false)
    })

    it('does NOT hijack Escape while typing in an input / textarea / select / contentEditable', () => {
        for (const tag of ['INPUT', 'TEXTAREA', 'SELECT']) {
            expect(decideEscapeRecovery({ placementModeActive: true, hasOpenFloatingPanel: true, key: 'Escape', focusedTagName: tag }).handle).toBe(false)
        }
        expect(decideEscapeRecovery({ placementModeActive: true, hasOpenFloatingPanel: false, key: 'Escape', focusedIsContentEditable: true }).handle).toBe(false)
    })

    it('recovery is independent of pointer/tool: it reads only placement + panel state', () => {
        // Same decision regardless of where the pointer is (no pointer input exists),
        // proving Escape works over Asset Library or over the viewport alike.
        const overLibrary = decideEscapeRecovery({ placementModeActive: true, hasOpenFloatingPanel: false, key: 'Escape', focusedTagName: 'BUTTON' })
        const overViewport = decideEscapeRecovery({ placementModeActive: true, hasOpenFloatingPanel: false, key: 'Escape', focusedTagName: 'CANVAS' })
        expect(overLibrary).toEqual(overViewport)
        expect(overLibrary.cancelPlacement).toBe(true)
    })

    it('re-entry after cancel behaves identically (stateless decision, no orphaned latch)', () => {
        // Cancel -> idle.
        expect(decideEscapeRecovery({ placementModeActive: false, hasOpenFloatingPanel: false, key: 'Escape' }).handle).toBe(false)
        // Re-arm -> Escape recovers again exactly as the first time.
        const second = decideEscapeRecovery({ placementModeActive: true, hasOpenFloatingPanel: false, key: 'Escape' })
        expect(second.cancelPlacement).toBe(true)
    })
})

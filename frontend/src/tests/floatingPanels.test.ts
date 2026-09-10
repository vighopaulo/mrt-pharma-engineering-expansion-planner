import { describe, it, expect } from 'vitest'
import { resolveFloatingPanelAction } from '../components/spatial/floatingPanels'
import { resolveViewportSource } from '../components/spatial/viewportResolution'

describe('§18 panel exclusivity', () => {
    it('opening Project BIM closes an open Clinical Program panel; feature state unchanged', () => {
        const r = resolveFloatingPanelAction({ currentlyOpenPanel: 'CLINICAL_PROGRAM', action: 'OPEN', targetPanel: 'PROJECT_BIM' })
        expect(r.nextOpenPanel).toBe('PROJECT_BIM')
        expect(r.featureStateChanged).toBe(false)
    })
})

describe('§19 escape', () => {
    it('Esc closes the open panel', () => {
        expect(resolveFloatingPanelAction({ currentlyOpenPanel: 'AUDIT_DIAGNOSTICS', action: 'ESCAPE' }).nextOpenPanel).toBeNull()
    })
    it('Esc with nothing open stays null', () => {
        expect(resolveFloatingPanelAction({ currentlyOpenPanel: null, action: 'ESCAPE' }).nextOpenPanel).toBeNull()
    })
})

describe('§20 outside click', () => {
    it('outside click closes the open panel', () => {
        expect(resolveFloatingPanelAction({ currentlyOpenPanel: 'INGESTION', action: 'OUTSIDE_CLICK' }).nextOpenPanel).toBeNull()
    })
})

describe('§21 inside click (no OUTSIDE_CLICK dispatched)', () => {
    it('a TOGGLE of the same panel closes it; an unrelated inside interaction does not', () => {
        // Inside interactions never dispatch OUTSIDE_CLICK/ESCAPE, so the panel
        // stays open unless the trigger is toggled.
        const stillOpen = resolveFloatingPanelAction({ currentlyOpenPanel: 'CLINICAL_PROGRAM', action: 'OPEN', targetPanel: 'CLINICAL_PROGRAM' })
        expect(stillOpen.nextOpenPanel).toBe('CLINICAL_PROGRAM')
    })
})

describe('§7 trigger toggle', () => {
    it('toggling the open panel closes it', () => {
        expect(resolveFloatingPanelAction({ currentlyOpenPanel: 'PROJECT_BIM', action: 'TOGGLE', targetPanel: 'PROJECT_BIM' }).nextOpenPanel).toBeNull()
    })
    it('toggling a different panel opens it (exclusive)', () => {
        expect(resolveFloatingPanelAction({ currentlyOpenPanel: 'PROJECT_BIM', action: 'TOGGLE', targetPanel: 'CLINICAL_PROGRAM' }).nextOpenPanel).toBe('CLINICAL_PROGRAM')
    })
})

describe('§22 feature-state independence', () => {
    it('closing any panel never reports a feature-state change', () => {
        for (const action of ['OPEN', 'TOGGLE', 'OUTSIDE_CLICK', 'ESCAPE', 'CLOSE'] as const) {
            expect(resolveFloatingPanelAction({ currentlyOpenPanel: 'CLINICAL_PROGRAM', action, targetPanel: 'CLINICAL_PROGRAM' }).featureStateChanged).toBe(false)
        }
    })
})

describe('CLOSE action', () => {
    it('CLOSE closes the targeted panel when open', () => {
        expect(resolveFloatingPanelAction({ currentlyOpenPanel: 'DEV_TOOLS', action: 'CLOSE', targetPanel: 'DEV_TOOLS' }).nextOpenPanel).toBeNull()
    })
    it('CLOSE of a non-open panel leaves the current open panel intact', () => {
        expect(resolveFloatingPanelAction({ currentlyOpenPanel: 'DEV_TOOLS', action: 'CLOSE', targetPanel: 'INGESTION' }).nextOpenPanel).toBe('DEV_TOOLS')
    })
})

// --- viewport resolution ---------------------------------------------------

describe('§33 explicit product viewport without selected view', () => {
    it('explicit available, no selected view => EXPLICIT_PRODUCT_VIEWPORT', () => {
        expect(resolveViewportSource({ explicitProductViewportAvailable: true, selectedViewAvailable: false, registeredViewportCount: 0 })).toBe('EXPLICIT_PRODUCT_VIEWPORT')
    })
    it('explicit wins even when selected view + registered exist', () => {
        expect(resolveViewportSource({ explicitProductViewportAvailable: true, selectedViewAvailable: true, registeredViewportCount: 3 })).toBe('EXPLICIT_PRODUCT_VIEWPORT')
    })
})

describe('§34 selected-view fallback', () => {
    it('no explicit, selected available => SELECTED_VIEW', () => {
        expect(resolveViewportSource({ explicitProductViewportAvailable: false, selectedViewAvailable: true, registeredViewportCount: 2 })).toBe('SELECTED_VIEW')
    })
})

describe('§35 single registered viewport fallback', () => {
    it('no explicit, no selected, exactly one registered => SINGLE_REGISTERED_VIEWPORT', () => {
        expect(resolveViewportSource({ explicitProductViewportAvailable: false, selectedViewAvailable: false, registeredViewportCount: 1 })).toBe('SINGLE_REGISTERED_VIEWPORT')
    })
})

describe('§36 ambiguous viewport', () => {
    it('no explicit, no selected, 0 registered => NOT_AVAILABLE', () => {
        expect(resolveViewportSource({ explicitProductViewportAvailable: false, selectedViewAvailable: false, registeredViewportCount: 0 })).toBe('NOT_AVAILABLE')
    })
    it('no explicit, no selected, multiple registered => NOT_AVAILABLE (never guess)', () => {
        expect(resolveViewportSource({ explicitProductViewportAvailable: false, selectedViewAvailable: false, registeredViewportCount: 3 })).toBe('NOT_AVAILABLE')
    })
})

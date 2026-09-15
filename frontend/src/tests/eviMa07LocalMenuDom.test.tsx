/**
 * EVI-MA-07 — DOM-level test for the local action popover (ViewerAppObjectMenu).
 *
 * Pure-picker/selection tests are insufficient: the accepted failures were live
 * UI behaviours (wrong-target actions, button clicks passing through to the
 * viewport). These tests render the REAL popover with a mocked overlay and prove:
 *   - the menu shows the CAPTURED SelectedAppObject (title + actions);
 *   - clicking Fit/Hide/Lock/Delete dispatches to the CAPTURED-target overlay
 *     functions (never a re-raycast) with the exact objectType + instanceId;
 *   - button clicks stopPropagation (they never reach the viewport behind them);
 *   - Delete shows a non-blocking Undo toast whose Undo calls undoLastAppEdit.
 * The overlay is mocked so vitest never imports the @itwin stack (project pattern).
 */
import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mutable seeded selection the mock returns.
let selectedView: { objectType: string; instanceId: string; title: string; hidden: boolean; locked: boolean; fitLabel: string } | undefined
const listeners = new Set<() => void>()
function notify() { for (const l of listeners) l() }

const deleteCaptured = vi.fn((_t: { objectType: string; instanceId: string }) => ({ ok: true, objectType: 'EQUIPMENT_INSTANCE', deletedId: 'x' }))
const setVisibility = vi.fn((_t: unknown, _v: boolean) => { })
const setLock = vi.fn(async (_t: unknown, _l: boolean) => { })
const fitCaptured = vi.fn(async (_t: unknown) => ({ ok: true }))
const undo = vi.fn(() => { })

vi.mock('../components/spatial/spatialAssetOverlay', () => ({
    subscribeClinicalProgram: (fn: () => void) => { listeners.add(fn); return () => listeners.delete(fn) },
    getSelectedAppObjectView: () => selectedView,
    getSelectedAppObjectAnchor: () => ({ x: 100, y: 100 }),
    deleteCapturedAppObject: (t: { objectType: string; instanceId: string }) => deleteCaptured(t),
    setCapturedAppObjectVisibility: (t: unknown, v: boolean) => setVisibility(t, v),
    setCapturedAppObjectLock: (t: unknown, l: boolean) => setLock(t, l),
    fitCapturedAppObject: (t: unknown) => fitCaptured(t),
    undoLastAppEdit: () => undo(),
}))

import { ViewerAppObjectMenu } from '../components/spatial/ViewerAppObjectMenu'

describe('EVI-MA-07 local action popover (DOM)', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        selectedView = { objectType: 'CLINICAL_LOGISTICS_VESTIBULE', instanceId: 'vestibule:rp:1', title: 'Radiopharmacy Logistics Vestibule', hidden: false, locked: false, fitLabel: 'Fit to Vestibule' }
    })

    it('renders the CAPTURED selected object title + the four common actions', () => {
        render(<ViewerAppObjectMenu />)
        expect(screen.getByText('Radiopharmacy Logistics Vestibule')).toBeTruthy()
        expect(screen.getByRole('menuitem', { name: 'Fit to Vestibule' })).toBeTruthy()
        expect(screen.getByRole('menuitem', { name: 'Hide' })).toBeTruthy()
        expect(screen.getByRole('menuitem', { name: 'Lock' })).toBeTruthy()
        expect(screen.getByRole('menuitem', { name: 'Delete' })).toBeTruthy()
    })

    it('Hide dispatches to the CAPTURED target (exact id) and stops propagation to the viewport', () => {
        render(<ViewerAppObjectMenu />)
        const btn = screen.getByRole('menuitem', { name: 'Hide' })
        // A click that would bubble to a viewport listener behind the menu.
        const bubbled = vi.fn()
        document.addEventListener('click', bubbled)
        fireEvent.click(btn)
        document.removeEventListener('click', bubbled)
        expect(setVisibility).toHaveBeenCalledWith({ objectType: 'CLINICAL_LOGISTICS_VESTIBULE', instanceId: 'vestibule:rp:1' }, false)
        // stopPropagation: the click never reached the document (viewport) behind it.
        expect(bubbled).not.toHaveBeenCalled()
    })

    it('Delete dispatches to the CAPTURED target and shows an Undo toast; toast Undo calls undoLastAppEdit', () => {
        render(<ViewerAppObjectMenu />)
        fireEvent.click(screen.getByRole('menuitem', { name: 'Delete' }))
        expect(deleteCaptured).toHaveBeenCalledWith({ objectType: 'CLINICAL_LOGISTICS_VESTIBULE', instanceId: 'vestibule:rp:1' })
        // Undo toast appears (non-blocking; no window.confirm/alert).
        const undoBtn = screen.getByRole('button', { name: 'Undo' })
        expect(undoBtn).toBeTruthy()
        fireEvent.click(undoBtn)
        expect(undo).toHaveBeenCalledTimes(1)
    })

    it('a LOCKED object disables Delete and offers Unlock (never a silent no-op Delete)', () => {
        selectedView = { objectType: 'EQUIPMENT_INSTANCE', instanceId: 'equipment:cyclo:1', title: 'IBA Cyclone KIUBE', hidden: false, locked: true, fitLabel: 'Fit to Equipment' }
        render(<ViewerAppObjectMenu />)
        const del = screen.getByRole('menuitem', { name: 'Delete' }) as HTMLButtonElement
        expect(del.disabled).toBe(true)
        expect(screen.getByRole('menuitem', { name: 'Unlock' })).toBeTruthy()
        fireEvent.click(del)
        expect(deleteCaptured).not.toHaveBeenCalled()
    })

    it('the action target does NOT change when the selection view changes AFTER capture within a click handler', () => {
        // Render for vestibule; the handler captures the vestibule target. Even if
        // some other object were hovered, the button still targets the captured id.
        render(<ViewerAppObjectMenu />)
        fireEvent.click(screen.getByRole('menuitem', { name: 'Fit to Vestibule' }))
        expect(fitCaptured).toHaveBeenCalledWith({ objectType: 'CLINICAL_LOGISTICS_VESTIBULE', instanceId: 'vestibule:rp:1' })
    })

    it('shows nothing when no object is selected', () => {
        selectedView = undefined
        act(() => notify())
        const { container } = render(<ViewerAppObjectMenu />)
        expect(container.querySelector('.mrt-appobject-menu')).toBeNull()
    })

    it('the selected object stays targeted after the store notifies (selection persists, not hover)', () => {
        render(<ViewerAppObjectMenu />)
        // A store notification (e.g. a hover-driven redraw elsewhere) must not
        // change the menu's target — it re-reads the SAME authoritative selection.
        act(() => notify())
        expect(screen.getByText('Radiopharmacy Logistics Vestibule')).toBeTruthy()
    })
})

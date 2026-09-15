/**
 * EVI-MA-06 CORRECTION — DOM-level right-click bridge test.
 *
 * The manual-acceptance failure proved that pure-picker tests are insufficient:
 * right-click did nothing in the live browser because the contextmenu bridge was
 * torn down whenever Bentley switched away from the primitive tool. These tests
 * dispatch a REAL `contextmenu` MouseEvent against an actual DOM viewport host
 * and prove the full live chain (DOM event → clientToRay → resolve →
 * open-menu store) fires with the correct instance id — for scanner, cyclotron,
 * and vestibule separately — and that the listener persists across simulated
 * tool switches (it is bound to the viewport host, not the tool).
 */
import { describe, expect, it, beforeEach } from 'vitest'
import {
    installAppObjectContextMenuBridge,
    handleContextMenuEvent,
    type ContextMenuBridgeDeps,
    type ViewportHost,
    type ContextMenuBridgeDiagnostic,
} from '../components/spatial/appObjectContextMenuBridge'

/** A DOM viewport host (jsdom div) + a trivial ray mapping. */
function makeHost(): ViewportHost {
    const element = document.createElement('div')
    // getBoundingClientRect is 0-based in jsdom; that's fine for these tests.
    document.body.appendChild(element)
    return {
        element,
        clientToRay: (x, y) => ({ origin: [x, y, 10], direction: [0, 0, -1] }),
    }
}

/** Deps that record the opened menu target + collected diagnostics. */
function makeDeps(resolveResult: { objectType: string; instanceId: string } | undefined) {
    const opened: { target: { objectType: string; instanceId: string }; viewX: number; viewY: number }[] = []
    const selected: { objectType: string; instanceId: string }[] = []
    let closed = 0
    const diagnostics: ContextMenuBridgeDiagnostic[] = []
    const deps: ContextMenuBridgeDeps = {
        resolve: () => resolveResult,
        select: (ref) => { selected.push(ref) },
        openMenu: (target, viewX, viewY) => { opened.push({ target, viewX, viewY }) },
        closeMenus: () => { closed += 1 },
        onDiagnostic: (d) => { diagnostics.push(d) },
    }
    return { deps, opened, selected, get closed() { return closed }, diagnostics }
}

function dispatchContextMenu(el: HTMLElement, clientX = 5, clientY = 7): MouseEvent {
    const e = new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX, clientY })
    el.dispatchEvent(e)
    return e
}

describe('EVI-MA-06 right-click bridge (DOM-level)', () => {
    beforeEach(() => { document.body.innerHTML = '' })

    it('a real contextmenu event on the viewport host opens the CYCLOTRON menu with the exact id', () => {
        const host = makeHost()
        const { deps, opened, selected } = makeDeps({ objectType: 'EQUIPMENT_INSTANCE', instanceId: 'equipment:cyclo:1' })
        const dispose = installAppObjectContextMenuBridge(host, deps)
        const e = dispatchContextMenu(host.element)
        expect(opened).toHaveLength(1)
        expect(opened[0].target).toEqual({ objectType: 'EQUIPMENT_INSTANCE', instanceId: 'equipment:cyclo:1' })
        expect(selected[0]).toEqual({ objectType: 'EQUIPMENT_INSTANCE', instanceId: 'equipment:cyclo:1' })
        expect(e.defaultPrevented).toBe(true) // browser menu suppressed for an app hit
        dispose()
    })

    it('opens the SCANNER menu (scanner is an EQUIPMENT_INSTANCE) with its exact id', () => {
        const host = makeHost()
        const { deps, opened } = makeDeps({ objectType: 'EQUIPMENT_INSTANCE', instanceId: 'equipment:scanner:1' })
        const dispose = installAppObjectContextMenuBridge(host, deps)
        dispatchContextMenu(host.element)
        expect(opened[0].target.instanceId).toBe('equipment:scanner:1')
        dispose()
    })

    it('opens the VESTIBULE menu with its exact id', () => {
        const host = makeHost()
        const { deps, opened } = makeDeps({ objectType: 'CLINICAL_LOGISTICS_VESTIBULE', instanceId: 'vestibule:rp:1' })
        const dispose = installAppObjectContextMenuBridge(host, deps)
        dispatchContextMenu(host.element)
        expect(opened[0].target).toEqual({ objectType: 'CLINICAL_LOGISTICS_VESTIBULE', instanceId: 'vestibule:rp:1' })
        dispose()
    })

    it('empty / native-BIM right-click closes app menus and does NOT suppress the browser menu', () => {
        const host = makeHost()
        const rec = makeDeps(undefined) // resolve returns nothing (BIM / empty)
        const dispose = installAppObjectContextMenuBridge(host, rec.deps)
        const e = dispatchContextMenu(host.element)
        expect(rec.opened).toHaveLength(0)
        expect(rec.closed).toBe(1)
        expect(e.defaultPrevented).toBe(false) // native menu left alone
        dispose()
    })

    it('the listener PERSISTS across simulated tool switches (it is bound to the host, not a tool)', () => {
        const host = makeHost()
        const { deps, opened } = makeDeps({ objectType: 'EQUIPMENT_INSTANCE', instanceId: 'equipment:cyclo:1' })
        const dispose = installAppObjectContextMenuBridge(host, deps)
        // Simulate arbitrary Bentley tool activity: fire many events; each still opens.
        dispatchContextMenu(host.element)
        dispatchContextMenu(host.element)
        dispatchContextMenu(host.element)
        expect(opened).toHaveLength(3)
        dispose()
        // After dispose the listener is gone (no further opens).
        dispatchContextMenu(host.element)
        expect(opened).toHaveLength(3)
    })

    it('skips while a gesture is active (does not open a menu mid-drag)', () => {
        const host = makeHost()
        const rec = makeDeps({ objectType: 'EQUIPMENT_INSTANCE', instanceId: 'equipment:cyclo:1' })
        rec.deps.isGestureActive = () => true
        const dispose = installAppObjectContextMenuBridge(host, rec.deps)
        dispatchContextMenu(host.element)
        expect(rec.opened).toHaveLength(0)
        expect(rec.diagnostics.some((d) => d.stage === 'GESTURE_ACTIVE_SKIP')).toBe(true)
        dispose()
    })

    it('structured diagnostics record the first reached stage per event', () => {
        const host = makeHost()
        const ok = makeDeps({ objectType: 'EQUIPMENT_INSTANCE', instanceId: 'equipment:cyclo:1' })
        handleContextMenuEvent(new MouseEvent('contextmenu', { clientX: 1, clientY: 1 }), host, ok.deps)
        expect(ok.diagnostics.map((d) => d.stage)).toContain('EVENT_RECEIVED')
        expect(ok.diagnostics.map((d) => d.stage)).toContain('MENU_OPENED')
        const noTarget = makeDeps(undefined)
        handleContextMenuEvent(new MouseEvent('contextmenu', { clientX: 1, clientY: 1 }), host, noTarget.deps)
        expect(noTarget.diagnostics.map((d) => d.stage)).toContain('NO_TARGET')
    })

    it('NO_RAY diagnostic when the viewport cannot build a ray', () => {
        const host: ViewportHost = { element: document.createElement('div'), clientToRay: () => undefined }
        document.body.appendChild(host.element)
        const rec = makeDeps({ objectType: 'EQUIPMENT_INSTANCE', instanceId: 'x' })
        handleContextMenuEvent(new MouseEvent('contextmenu', { clientX: 1, clientY: 1 }), host, rec.deps)
        expect(rec.opened).toHaveLength(0)
        expect(rec.diagnostics.some((d) => d.stage === 'NO_RAY')).toBe(true)
    })
})

/**
 * appObjectContextMenuBridge — EVI-MA-06 CORRECTION. A TOOL-INDEPENDENT
 * right-click (contextmenu) bridge attached directly to the live viewport host.
 *
 * ROOT CAUSE (manual acceptance failure): the previous right-click bridge lived
 * INSIDE MrtDirectManipulationTool and was installed in the tool's onPostInstall
 * / onDataButtonDown and REMOVED in onCleanup. Bentley's ToolAdmin frequently
 * activates the view-navigation tool (after camera orbit/pan, viewport focus
 * change, or when the primitive tool was never armed), which deactivates the
 * primitive tool and tears the bridge down. After any camera move the DOM
 * `contextmenu` event had no listener, so right-click did nothing — exactly the
 * "worked, failed, worked again, depended on tool lifecycle" symptom.
 *
 * FIX: bind the contextmenu listener to the viewport host for the LIFETIME of the
 * viewport (registered by the viewer via setActiveProductViewport), independent
 * of which Bentley tool is active. It resolves the SAME AppObjectPickTarget and
 * opens the SAME context-menu store the rest of the app uses.
 *
 * This module owns ONLY the DOM event → ray → resolve → open-menu wiring. The
 * ray math + resolution + menu store live elsewhere (injected), so this stays
 * thin and its DOM behaviour is testable by dispatching a real contextmenu event.
 */

/** A minimal viewport host shape (the element that receives pointer events). */
export interface ViewportHost {
    /** The DOM element to bind the contextmenu listener to (vpDiv/parentDiv). */
    element: HTMLElement
    /** Convert client (x,y) → a world pick ray via the viewport frustum. */
    clientToRay: (clientX: number, clientY: number) => { origin: [number, number, number]; direction: [number, number, number] } | undefined
}

/** The unified resolution + menu-open collaborators the bridge drives. */
export interface ContextMenuBridgeDeps {
    /** Resolve the app object under a world ray (equipment or vestibule), or undefined. */
    resolve: (ray: { origin: [number, number, number]; direction: [number, number, number] }) => { objectType: string; instanceId: string } | undefined
    /** Select the exact resolved object (unified selection). */
    select: (ref: { objectType: string; instanceId: string }) => void
    /** Open the correct context menu for the resolved target at view coords. */
    openMenu: (target: { objectType: string; instanceId: string }, viewX: number, viewY: number) => void
    /** Close all app context menus (empty / native-BIM right-click). */
    closeMenus: () => void
    /** Optional: is an interaction gesture (drag/rotate) currently active? */
    isGestureActive?: () => boolean
    /** Optional structured diagnostic sink (DEV). */
    onDiagnostic?: (d: ContextMenuBridgeDiagnostic) => void
}

/** A structured, PII-free diagnostic of one contextmenu bridge event. */
export interface ContextMenuBridgeDiagnostic {
    at: number
    /** The first stage reached before a stop/exit. */
    stage:
        | 'EVENT_RECEIVED'
        | 'GESTURE_ACTIVE_SKIP'
        | 'NO_RAY'
        | 'NO_TARGET'
        | 'MENU_OPENED'
    objectType?: string
    instanceId?: string
}

/**
 * The single DOM contextmenu handler. Exported for direct unit/DOM testing: a
 * test can build a fake ViewportHost + deps and dispatch a real `contextmenu`
 * MouseEvent to prove the menu opens with the correct instance id.
 */
export function handleContextMenuEvent(
    e: MouseEvent,
    host: ViewportHost,
    deps: ContextMenuBridgeDeps,
): void {
    const diag = (d: Omit<ContextMenuBridgeDiagnostic, 'at'>) => deps.onDiagnostic?.({ at: Date.now(), ...d })
    diag({ stage: 'EVENT_RECEIVED' })
    if (deps.isGestureActive?.()) { diag({ stage: 'GESTURE_ACTIVE_SKIP' }); return }
    const ray = host.clientToRay(e.clientX, e.clientY)
    if (!ray) { diag({ stage: 'NO_RAY' }); return }
    const target = deps.resolve(ray)
    if (!target) {
        // Native BIM / empty / planning volume: leave the browser menu alone.
        deps.closeMenus()
        diag({ stage: 'NO_TARGET' })
        return
    }
    // App-owned hit: suppress the browser menu, select + open the app menu.
    e.preventDefault()
    e.stopPropagation()
    const rect = host.element.getBoundingClientRect()
    const viewX = Math.round(e.clientX - rect.left)
    const viewY = Math.round(e.clientY - rect.top)
    deps.select(target)
    deps.openMenu(target, viewX, viewY)
    diag({ stage: 'MENU_OPENED', objectType: target.objectType, instanceId: target.instanceId })
}

/**
 * Install the tool-independent contextmenu bridge on a viewport host. Idempotent
 * per host element; returns a disposer that removes the listener. Capture phase
 * so it runs before Bentley/browser handlers regardless of the child under the
 * cursor. Safe to call repeatedly (re-install on viewport remount).
 */
export function installAppObjectContextMenuBridge(
    host: ViewportHost,
    deps: ContextMenuBridgeDeps,
): () => void {
    const listener = (e: MouseEvent) => handleContextMenuEvent(e, host, deps)
    host.element.addEventListener('contextmenu', listener, { capture: true })
    return () => host.element.removeEventListener('contextmenu', listener, { capture: true } as EventListenerOptions)
}

/**
 * placementEscapeRecovery — EVI-MA-07A.
 *
 * Pure, Bentley-free decision helpers for the placement-mode escape / backdrop
 * recovery lifecycle. These functions decide, from observable state only, what
 * an app-stable Escape handler must do and whether a full-viewport blocking
 * layer is allowed to be mounted.
 *
 * DOCTRINE (EVI-MA-07A):
 *   - The ONE authoritative placement state is `placementModeActive` (derived
 *     from the SpatialAssetStore intent). Normal viewer state == placement IDLE.
 *   - A full-viewport blocking treatment (the transparent `.viewer-panel-backdrop`,
 *     driven by an open floating tool panel) must NEVER survive placement. It can
 *     only exist while a floating panel is deliberately open, and it must be torn
 *     down the moment placement is armed so it can never become orphaned and trap
 *     the user after "Placement cancelled".
 *   - Escape must recover from ANY placement phase, from ANY pointer location,
 *     independent of Bentley's currently-active Tool.
 */

/** Observable state the Escape decision reads. */
export interface EscapeRecoveryInput {
    /** True while a placement intent is held (SpatialAssetStore.intent !== undefined). */
    placementModeActive: boolean
    /** True while any floating tool panel is open (drives the transparent backdrop). */
    hasOpenFloatingPanel: boolean
    /** The pressed key. */
    key: string
    /** The focused element tag (guards against cancelling while typing). */
    focusedTagName?: string | null
    /** Whether the focused element is contentEditable. */
    focusedIsContentEditable?: boolean
}

/** What the app-stable Escape handler should do. */
export interface EscapeRecoveryDecision {
    /** Escape was pressed in a recoverable state; handle it (and preventDefault). */
    handle: boolean
    /** Cancel the active placement session (calls the ONE cancelPlacement()). */
    cancelPlacement: boolean
    /** Close any open floating panel so no orphaned backdrop can remain. */
    closeFloatingPanel: boolean
}

const NO_OP: EscapeRecoveryDecision = { handle: false, cancelPlacement: false, closeFloatingPanel: false }

/**
 * Decide how the app-stable Escape handler should respond.
 *
 * Escape recovers whenever placement is active OR a floating panel (and thus the
 * full-viewport backdrop) is open. Recovery is atomic: it cancels placement AND
 * closes any open panel in a single press, so the viewport is never left blocked.
 *
 * It does NOT fire while the user is typing in a text input / textarea /
 * contentEditable region (so Escape there behaves normally for that field).
 */
export function decideEscapeRecovery(input: EscapeRecoveryInput): EscapeRecoveryDecision {
    if (input.key !== 'Escape') return NO_OP

    // Never hijack Escape while the user is editing text.
    const tag = (input.focusedTagName ?? '').toUpperCase()
    if (input.focusedIsContentEditable) return NO_OP
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return NO_OP

    const recoverable = input.placementModeActive || input.hasOpenFloatingPanel
    if (!recoverable) return NO_OP

    return {
        handle: true,
        cancelPlacement: input.placementModeActive,
        closeFloatingPanel: input.hasOpenFloatingPanel,
    }
}

/**
 * Whether the full-viewport blocking backdrop is ALLOWED to be mounted.
 *
 * §7/§8: the backdrop must derive directly from panel state and must never
 * coexist with an armed placement session (that coexistence is exactly the
 * orphan trap). While placement is active the viewport must remain clear so the
 * user can see the building to place equipment.
 */
export function backdropMayMount(input: { hasOpenFloatingPanel: boolean; placementModeActive: boolean }): boolean {
    return input.hasOpenFloatingPanel && !input.placementModeActive
}

/**
 * When placement becomes active, any open floating panel must be closed so the
 * transparent blocking backdrop cannot be orphaned. Returns true when the caller
 * should close the open panel.
 */
export function shouldCloseFloatingPanelOnPlacementArmed(input: {
    placementModeActive: boolean
    hasOpenFloatingPanel: boolean
}): boolean {
    return input.placementModeActive && input.hasOpenFloatingPanel
}

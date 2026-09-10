/**
 * floatingPanels — pure, Bentley-free lifecycle policy for the temporary floating
 * TOOL panels in /viewer. It decides which single major tool panel is open, and
 * NEVER changes feature state (active BIM, camera mode, Clinical Program ON/OFF,
 * assignments). Panel VISIBILITY is separate from FEATURE STATE.
 */

/** The temporary floating tool panels (feature state lives elsewhere). */
export type FloatingPanelId =
    | 'PROJECT_BIM'
    | 'CLINICAL_PROGRAM'
    | 'AUDIT_DIAGNOSTICS'
    | 'INGESTION'
    | 'DEV_TOOLS'
    | 'DEV_INSPECTOR'
    | 'VIEW_CONTROL'

export type FloatingPanelAction = 'OPEN' | 'TOGGLE' | 'OUTSIDE_CLICK' | 'ESCAPE' | 'CLOSE'

export interface FloatingPanelInput {
    /** The single major tool panel currently open (or null). */
    currentlyOpenPanel: FloatingPanelId | null
    action: FloatingPanelAction
    /** The panel the action targets (required for OPEN/TOGGLE/CLOSE). */
    targetPanel?: FloatingPanelId
}

export interface FloatingPanelResult {
    nextOpenPanel: FloatingPanelId | null
    /** ALWAYS false — closing/opening a panel never mutates feature state. */
    featureStateChanged: false
}

/**
 * Resolve the next open panel:
 *   - OPEN target        => target (exclusive; any other major panel closes).
 *   - TOGGLE target      => close if it's the open one, else open it (exclusive).
 *   - CLOSE target       => close it if open, else unchanged.
 *   - ESCAPE / OUTSIDE_CLICK => close whatever is open.
 * Never changes feature state.
 */
export function resolveFloatingPanelAction(input: FloatingPanelInput): FloatingPanelResult {
    const open = input.currentlyOpenPanel
    const target = input.targetPanel
    let next: FloatingPanelId | null = open
    switch (input.action) {
        case 'OPEN':
            next = target ?? open
            break
        case 'TOGGLE':
            next = target ? (open === target ? null : target) : open
            break
        case 'CLOSE':
            next = target ? (open === target ? null : open) : open
            break
        case 'ESCAPE':
        case 'OUTSIDE_CLICK':
            next = null
            break
    }
    return { nextOpenPanel: next, featureStateChanged: false }
}

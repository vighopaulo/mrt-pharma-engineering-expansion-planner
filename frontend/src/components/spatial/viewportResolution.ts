/**
 * viewportResolution — pure, Bentley-free policy for resolving which viewport is
 * the ACTIVE product viewport.
 *
 * Proven defect: authoritative geometry extraction failed with NO_ACTIVE_VIEWPORT
 * because it relied solely on IModelApp.viewManager.selectedView, which can be
 * null even while the clinic viewport is visibly rendered. The product owns the
 * live ScreenViewport (registered by the viewer component); this policy makes the
 * resolution precedence explicit and never guesses when it is ambiguous.
 */

export type ViewportSource =
    | 'EXPLICIT_PRODUCT_VIEWPORT'
    | 'SELECTED_VIEW'
    | 'SINGLE_REGISTERED_VIEWPORT'
    | 'NOT_AVAILABLE'

export interface ViewportResolutionInput {
    /** The viewer component explicitly registered its live ScreenViewport. */
    explicitProductViewportAvailable: boolean
    /** IModelApp.viewManager.selectedView is present. */
    selectedViewAvailable: boolean
    /** How many product viewports the viewManager currently owns. */
    registeredViewportCount: number
}

/**
 * Resolve the viewport source with explicit precedence:
 *   EXPLICIT_PRODUCT_VIEWPORT > SELECTED_VIEW > SINGLE_REGISTERED_VIEWPORT > NOT_AVAILABLE.
 * A count != 1 of registered viewports (with no explicit/selected) is ambiguous
 * → NOT_AVAILABLE (never guess).
 */
export function resolveViewportSource(input: ViewportResolutionInput): ViewportSource {
    if (input.explicitProductViewportAvailable) return 'EXPLICIT_PRODUCT_VIEWPORT'
    if (input.selectedViewAvailable) return 'SELECTED_VIEW'
    if (input.registeredViewportCount === 1) return 'SINGLE_REGISTERED_VIEWPORT'
    return 'NOT_AVAILABLE'
}

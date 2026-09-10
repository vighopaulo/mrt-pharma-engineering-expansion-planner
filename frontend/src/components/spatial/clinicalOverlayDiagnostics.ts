/**
 * clinicalOverlayDiagnostics — pure, Bentley-free classifier for WHY a clinical-
 * program assignment is not visible on the building. Given a bounded set of
 * observed facts about the live rendering chain (assignment → room → footprint →
 * storey → overlay model → decorator → draw → world-to-view → HTML/graphic), it
 * returns exactly ONE primary failure class (or NO_FAILURE_DETECTED).
 *
 * This is the diagnostic authority: the dev-only live diagnostic gathers the
 * facts from the real viewport and hands them here; nothing here touches Bentley.
 */

export type ClinicalOverlayFailureClass =
    | 'ASSIGNMENT_NOT_FOUND'
    | 'ASSIGNMENT_TO_SPACE_ID_MISMATCH'
    | 'AMBIGUOUS_BIM_SPACE_IDENTITY'
    | 'ROOM_FOOTPRINT_NOT_FOUND'
    | 'STOREY_FILTER_MISMATCH'
    | 'OVERLAY_MODEL_POLICY_FILTERED_ASSIGNMENT'
    | 'DECORATOR_NOT_REGISTERED'
    | 'DECORATOR_DISABLED'
    | 'DECORATOR_NOT_INVALIDATED'
    | 'DECORATOR_DRAW_PATH_NOT_REACHED'
    | 'LABEL_ANCHOR_OFFSCREEN'
    | 'HTML_DECORATION_NOT_ATTACHED'
    | 'FOOTPRINT_GRAPHIC_NOT_CREATED'
    | 'OVERLAY_HIDDEN_BY_LAYOUT'
    | 'OTHER_PROVEN_CAUSE'
    | 'NO_FAILURE_DETECTED'

/** Bounded observed facts about the live chain for a single target assignment. */
export interface ClinicalOverlayObservation {
    assignmentFound: boolean
    /** # of SpatialRoomReference matching assignment.bimSpaceId (exact). */
    roomMatchCount: number
    footprintFound: boolean
    /** Active clinical-program storey filter; undefined => all building. */
    activeStoreyId?: string
    /** Room's canonical (Z-binned) storey id; undefined => unknown. */
    roomStoreyId?: string
    /** # of overlay records produced by deriveClinicalProgramOverlay. */
    overlayRecordCount: number
    /** Whether the target's overlay record is present. */
    targetOverlayRecordFound: boolean
    decoratorRegistered: boolean
    decoratorEnabled: boolean
    /** Whether the decorator has actually been invoked since the last state change. */
    decoratorInvalidatedAfterChange: boolean
    /** Whether a draw was attempted for the target. */
    drawAttempted: boolean
    /** Whether the target label anchor projects inside the viewport bounds. */
    anchorInsideViewport: boolean
    /** Whether the HTML label element was attached to the decoration container. */
    htmlLabelAttached: boolean
    /** Whether the footprint overlay graphic was created. */
    footprintGraphicCreated: boolean
    /** Whether an app layout rule is hiding the overlay container. */
    overlayHiddenByLayout: boolean
}

/**
 * Classify the single primary failure. Evaluated in strict chain order so the
 * FIRST broken link is reported (fixing it may reveal the next, but we never
 * emit multiple speculative causes).
 */
export function classifyClinicalOverlayFailure(o: ClinicalOverlayObservation): ClinicalOverlayFailureClass {
    if (!o.assignmentFound) return 'ASSIGNMENT_NOT_FOUND'
    if (o.roomMatchCount === 0) return 'ASSIGNMENT_TO_SPACE_ID_MISMATCH'
    if (o.roomMatchCount > 1) return 'AMBIGUOUS_BIM_SPACE_IDENTITY'
    if (!o.footprintFound) return 'ROOM_FOOTPRINT_NOT_FOUND'

    // Storey filter: only a failure when a specific storey is active and the
    // room's canonical storey differs (or is unknown while a storey is active).
    if (o.activeStoreyId !== undefined) {
        if (o.roomStoreyId === undefined || o.roomStoreyId !== o.activeStoreyId) return 'STOREY_FILTER_MISMATCH'
    }

    if (!o.targetOverlayRecordFound) return 'OVERLAY_MODEL_POLICY_FILTERED_ASSIGNMENT'
    if (!o.decoratorRegistered) return 'DECORATOR_NOT_REGISTERED'
    if (!o.decoratorEnabled) return 'DECORATOR_DISABLED'
    if (!o.decoratorInvalidatedAfterChange) return 'DECORATOR_NOT_INVALIDATED'
    if (!o.drawAttempted) return 'DECORATOR_DRAW_PATH_NOT_REACHED'
    if (!o.anchorInsideViewport) return 'LABEL_ANCHOR_OFFSCREEN'
    if (!o.htmlLabelAttached) return 'HTML_DECORATION_NOT_ATTACHED'
    if (!o.footprintGraphicCreated) return 'FOOTPRINT_GRAPHIC_NOT_CREATED'
    if (o.overlayHiddenByLayout) return 'OVERLAY_HIDDEN_BY_LAYOUT'
    return 'NO_FAILURE_DETECTED'
}

/** A one-line human-readable summary of the observation + class (sanitized). */
export function summarizeClinicalOverlayObservation(o: ClinicalOverlayObservation, cls: ClinicalOverlayFailureClass): string {
    return [
        `class=${cls}`,
        `assignment=${o.assignmentFound ? 'Y' : 'N'}`,
        `roomMatch=${o.roomMatchCount}`,
        `footprint=${o.footprintFound ? 'Y' : 'N'}`,
        `activeStorey=${o.activeStoreyId ?? 'ALL'}`,
        `roomStorey=${o.roomStoreyId ?? 'none'}`,
        `overlayRecords=${o.overlayRecordCount}`,
        `targetRecord=${o.targetOverlayRecordFound ? 'Y' : 'N'}`,
        `decorator=${o.decoratorRegistered ? 'reg' : 'unreg'}/${o.decoratorEnabled ? 'on' : 'off'}`,
        `invalidated=${o.decoratorInvalidatedAfterChange ? 'Y' : 'N'}`,
        `draw=${o.drawAttempted ? 'Y' : 'N'}`,
        `onscreen=${o.anchorInsideViewport ? 'Y' : 'N'}`,
        `html=${o.htmlLabelAttached ? 'Y' : 'N'}`,
        `graphic=${o.footprintGraphicCreated ? 'Y' : 'N'}`,
    ].join(' ')
}

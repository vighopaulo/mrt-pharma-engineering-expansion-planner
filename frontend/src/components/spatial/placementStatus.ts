/**
 * placementStatus — pure presentation helper that derives the Asset Library
 * status line from placement-mode transitions in the SpatialAssetStore snapshot.
 *
 * This is a narrow PRESENTATION seam (Bentley-free, unit-testable). It exists so
 * the "Placing…" instruction never lingers after a successful placement: the
 * status is DERIVED from state transitions, not a manually-set string that can
 * go stale when the Bentley tool exits.
 *
 * It does NOT change any placement, store, overlay, or Bentley behavior.
 */

export type PlacementUiPhase = 'IDLE' | 'PLACEMENT_ACTIVE' | 'PLACEMENT_SUCCEEDED' | 'PLACEMENT_CANCELLED'

export interface PlacementStatusInput {
    /** Whether placement mode is currently active (an intent is held). */
    active: boolean
    /** Whether it was active on the previous observed snapshot. */
    wasActive: boolean
    /** Current placed-instance count. */
    count: number
    /** Placed-instance count on the previous observed snapshot. */
    prevCount: number
    /** Label of the intent currently/most-recently being placed. */
    displayLabel?: string
    /** Id of the most recently placed instance (if a placement just succeeded). */
    lastPlacedInstanceId?: string
}

export interface PlacementStatus {
    phase: PlacementUiPhase
    /** Human-readable status text for the UI (empty for IDLE with no history). */
    text: string
}

/**
 * Resolve the status phase + text from a placement-mode transition.
 *   active                                  -> PLACEMENT_ACTIVE ("Placing: …")
 *   was active -> inactive, count increased -> PLACEMENT_SUCCEEDED ("Placed: …")
 *   was active -> inactive, count unchanged -> PLACEMENT_CANCELLED
 *   otherwise                               -> IDLE
 */
export function resolvePlacementStatus(input: PlacementStatusInput): PlacementStatus {
    const { active, wasActive, count, prevCount, displayLabel, lastPlacedInstanceId } = input

    if (active) {
        return {
            phase: 'PLACEMENT_ACTIVE',
            text: `Placing: ${displayLabel ?? 'asset'} — click a location in the model (right-click / Esc to cancel)`,
        }
    }
    if (wasActive && !active) {
        if (count > prevCount) {
            const id = lastPlacedInstanceId
            return { phase: 'PLACEMENT_SUCCEEDED', text: id ? `Placed: ${id}` : `Placed: ${displayLabel ?? 'asset'}` }
        }
        return { phase: 'PLACEMENT_CANCELLED', text: 'Placement cancelled' }
    }
    return { phase: 'IDLE', text: '' }
}

export type MoveUiPhase = 'IDLE' | 'MOVE_ACTIVE' | 'MOVE_SUCCEEDED' | 'MOVE_CANCELLED'

export interface MoveStatusInput {
    /** Whether move mode is currently active. */
    active: boolean
    /** Whether move mode was active on the previous observed snapshot. */
    wasActive: boolean
    /** Label of the instance currently/most-recently being moved. */
    displayLabel?: string
    /** Id of the instance bound to the move (for the success line). */
    assetInstanceId?: string
    /**
     * Whether the just-ended move actually changed a transform. The store
     * version increments on both success and cancel, so the caller passes
     * whether the bound instance's position changed to disambiguate.
     */
    positionChanged?: boolean
}

export interface MoveStatus {
    phase: MoveUiPhase
    text: string
}

/**
 * Resolve the move status from a move-mode transition. Mirrors the placement
 * status lesson so the "Moving…" instruction never lingers after the tool exits.
 *   active                                  -> MOVE_ACTIVE ("Moving: …")
 *   was active -> inactive, position moved  -> MOVE_SUCCEEDED ("Moved: …")
 *   was active -> inactive, no change       -> MOVE_CANCELLED ("Move cancelled")
 *   otherwise                               -> IDLE
 */
export function resolveMoveStatus(input: MoveStatusInput): MoveStatus {
    const { active, wasActive, displayLabel, assetInstanceId, positionChanged } = input
    if (active) {
        return {
            phase: 'MOVE_ACTIVE',
            text: `Moving: ${displayLabel ?? 'asset'} — click a new location in the model (right-click / Esc to cancel)`,
        }
    }
    if (wasActive && !active) {
        if (positionChanged) {
            return { phase: 'MOVE_SUCCEEDED', text: assetInstanceId ? `Moved: ${assetInstanceId}` : `Moved: ${displayLabel ?? 'asset'}` }
        }
        return { phase: 'MOVE_CANCELLED', text: 'Move cancelled' }
    }
    return { phase: 'IDLE', text: '' }
}

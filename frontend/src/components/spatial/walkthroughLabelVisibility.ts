/**
 * walkthroughLabelVisibility — pure, Bentley-free policy for whether an app-owned
 * ClinicalPlanningVolume LABEL should be shown, per camera mode (Build 1A
 * walkthrough label-occlusion correction).
 *
 * Manual acceptance exposed that planning-volume labels ("Uptake 01 (draft)",
 * "Injection Room 01 (draft)") remained visible THROUGH walls / across rooms in
 * Walkthrough — because HTML-decoration labels are pure screen-space projections
 * with no depth/occlusion test, and the decorator had no notion of the active
 * camera mode. This module holds the DISPLAY policy (view concern only):
 *
 *   PLANNING       → labels persistent (unchanged accepted behavior).
 *   BIRDS_EYE      → labels persistent (unchanged accepted behavior).
 *   WALKTHROUGH    → visibility-aware: hide if behind camera, off-screen, beyond
 *                    a bounded distance, or occluded by solid BIM geometry.
 *
 * It NEVER moves the label anchor, mutates domain/planning-volume state, or
 * touches Bentley geometry. The decorator supplies the live viewport facts
 * (behind-camera / on-screen / occluded / distance); this seam decides.
 *
 * FUTURE explicit wayfinding may intentionally show through-wall guidance — that
 * is a separate opt-in mode, NOT this policy.
 */
import type { CameraMode } from './cameraNav'

/**
 * Bounded Walkthrough label distance (meters). Beyond this, a planning label is
 * suppressed even when unobstructed, so a walkthrough is not papered with every
 * label across the whole facility. Explicit named constant (no scattered magic
 * number); a generic navigation assumption, not a calibrated value.
 */
export const WALKTHROUGH_LABEL_MAX_DISTANCE_M = 18

export type LabelVisibilityReason =
    | 'MODE_PERSISTENT' // PLANNING / BIRDS_EYE: always shown
    | 'VISIBLE_NEARBY' // WALKTHROUGH: on-screen, in range, unobstructed
    | 'HIDDEN_BEHIND_CAMERA'
    | 'HIDDEN_OFFSCREEN'
    | 'HIDDEN_TOO_FAR'
    | 'HIDDEN_OCCLUDED'

export interface LabelVisibilityInput {
    cameraMode: CameraMode
    /** WALKTHROUGH viewport facts (ignored for PLANNING/BIRDS_EYE). */
    behindCamera: boolean
    onScreen: boolean
    /** Solid BIM geometry lies between the camera and the label anchor. */
    occluded: boolean
    /** Straight-line distance (m) from the walk eye to the label anchor. */
    distance: number
    /** Bounded max distance; defaults to WALKTHROUGH_LABEL_MAX_DISTANCE_M. */
    maxDistance?: number
}

export interface LabelVisibilityResult {
    visible: boolean
    reason: LabelVisibilityReason
}

/**
 * Decide whether a single planning-volume label is visible. Pure + deterministic.
 * Precedence in WALKTHROUGH: behind-camera > off-screen > too-far > occluded >
 * visible. PLANNING / BIRDS_EYE are always persistent (accepted behavior).
 */
export function resolveWalkthroughLabelVisibility(input: LabelVisibilityInput): LabelVisibilityResult {
    if (input.cameraMode === 'PLANNING' || input.cameraMode === 'BIRDS_EYE_CUTAWAY') {
        return { visible: true, reason: 'MODE_PERSISTENT' }
    }
    // WALKTHROUGH — visibility-aware.
    if (input.behindCamera) return { visible: false, reason: 'HIDDEN_BEHIND_CAMERA' }
    if (!input.onScreen) return { visible: false, reason: 'HIDDEN_OFFSCREEN' }
    const max = input.maxDistance ?? WALKTHROUGH_LABEL_MAX_DISTANCE_M
    if (!(input.distance <= max)) return { visible: false, reason: 'HIDDEN_TOO_FAR' }
    if (input.occluded) return { visible: false, reason: 'HIDDEN_OCCLUDED' }
    return { visible: true, reason: 'VISIBLE_NEARBY' }
}

/** Whether a camera mode uses the persistent (always-on) label policy. */
export function isPersistentLabelMode(mode: CameraMode): boolean {
    return mode === 'PLANNING' || mode === 'BIRDS_EYE_CUTAWAY'
}

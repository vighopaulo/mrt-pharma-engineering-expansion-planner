/**
 * Build 1A walkthrough LABEL occlusion + visibility correction — pure domain
 * tests (§20, 20 properties) for resolveWalkthroughLabelVisibility.
 *
 * Manual acceptance proved that ClinicalPlanningVolume labels ("Uptake 01
 * (draft)", "Injection Room 01 (draft)") showed THROUGH walls / across rooms in
 * Walkthrough, because HTML-decoration labels have no depth test and the
 * decorator had no camera-mode awareness. This suite pins the pure DISPLAY
 * policy: PLANNING / BIRDS_EYE persistent; WALKTHROUGH visibility-aware
 * (behind-camera > off-screen > too-far > occluded > visible). The policy never
 * moves an anchor or mutates domain state — it only returns a decision.
 */
import { describe, it, expect } from 'vitest'
import {
    resolveWalkthroughLabelVisibility,
    isPersistentLabelMode,
    WALKTHROUGH_LABEL_MAX_DISTANCE_M,
    type LabelVisibilityInput,
} from '../components/spatial/walkthroughLabelVisibility'
import type { CameraMode } from '../components/spatial/cameraNav'

// A fully-visible WALKTHROUGH baseline: on-screen, in range, unobstructed.
const walkVisible = (over: Partial<LabelVisibilityInput> = {}): LabelVisibilityInput => ({
    cameraMode: 'WALKTHROUGH',
    behindCamera: false,
    onScreen: true,
    occluded: false,
    distance: 5,
    ...over,
})

// §20.1-3 — PLANNING / BIRDS_EYE labels are always persistent (accepted behavior).
describe('§20.1-3 persistent modes', () => {
    it('PLANNING is always visible regardless of viewport facts', () => {
        const r = resolveWalkthroughLabelVisibility({
            cameraMode: 'PLANNING',
            behindCamera: true,
            onScreen: false,
            occluded: true,
            distance: 9999,
        })
        expect(r).toEqual({ visible: true, reason: 'MODE_PERSISTENT' })
    })
    it('BIRDS_EYE_CUTAWAY is always visible regardless of viewport facts', () => {
        const r = resolveWalkthroughLabelVisibility({
            cameraMode: 'BIRDS_EYE_CUTAWAY',
            behindCamera: true,
            onScreen: false,
            occluded: true,
            distance: 9999,
        })
        expect(r).toEqual({ visible: true, reason: 'MODE_PERSISTENT' })
    })
    it('isPersistentLabelMode is true for PLANNING/BIRDS_EYE, false for WALKTHROUGH', () => {
        expect(isPersistentLabelMode('PLANNING')).toBe(true)
        expect(isPersistentLabelMode('BIRDS_EYE_CUTAWAY')).toBe(true)
        expect(isPersistentLabelMode('WALKTHROUGH')).toBe(false)
    })
})

// §20.4-8 — WALKTHROUGH hide reasons + precedence
describe('§20.4-8 walkthrough hide reasons', () => {
    it('behind camera hides the label (HIDDEN_BEHIND_CAMERA)', () => {
        const r = resolveWalkthroughLabelVisibility(walkVisible({ behindCamera: true }))
        expect(r).toEqual({ visible: false, reason: 'HIDDEN_BEHIND_CAMERA' })
    })
    it('off-screen hides the label (HIDDEN_OFFSCREEN)', () => {
        const r = resolveWalkthroughLabelVisibility(walkVisible({ onScreen: false }))
        expect(r).toEqual({ visible: false, reason: 'HIDDEN_OFFSCREEN' })
    })
    it('beyond max distance hides the label (HIDDEN_TOO_FAR)', () => {
        const r = resolveWalkthroughLabelVisibility(walkVisible({ distance: WALKTHROUGH_LABEL_MAX_DISTANCE_M + 0.01 }))
        expect(r).toEqual({ visible: false, reason: 'HIDDEN_TOO_FAR' })
    })
    it('occluded by solid geometry hides the label (HIDDEN_OCCLUDED)', () => {
        const r = resolveWalkthroughLabelVisibility(walkVisible({ occluded: true }))
        expect(r).toEqual({ visible: false, reason: 'HIDDEN_OCCLUDED' })
    })
    it('behind-camera takes precedence over every other hide reason', () => {
        const r = resolveWalkthroughLabelVisibility(
            walkVisible({ behindCamera: true, onScreen: false, occluded: true, distance: 9999 }),
        )
        expect(r.reason).toBe('HIDDEN_BEHIND_CAMERA')
    })
})

// §20.9-11 — precedence ordering below behind-camera
describe('§20.9-11 precedence ordering', () => {
    it('off-screen takes precedence over too-far + occluded (not behind)', () => {
        const r = resolveWalkthroughLabelVisibility(
            walkVisible({ onScreen: false, occluded: true, distance: 9999 }),
        )
        expect(r.reason).toBe('HIDDEN_OFFSCREEN')
    })
    it('too-far takes precedence over occluded (on-screen, in front)', () => {
        const r = resolveWalkthroughLabelVisibility(
            walkVisible({ occluded: true, distance: 9999 }),
        )
        expect(r.reason).toBe('HIDDEN_TOO_FAR')
    })
    it('occluded is only reported when in front, on-screen, and in range', () => {
        const r = resolveWalkthroughLabelVisibility(walkVisible({ occluded: true, distance: 5 }))
        expect(r.reason).toBe('HIDDEN_OCCLUDED')
    })
})

// §20.12-14 — the visible case
describe('§20.12-14 visible-nearby-unobstructed', () => {
    it('nearby, on-screen, in front, unobstructed → VISIBLE_NEARBY', () => {
        const r = resolveWalkthroughLabelVisibility(walkVisible())
        expect(r).toEqual({ visible: true, reason: 'VISIBLE_NEARBY' })
    })
    it('a label directly in view close to the camera is shown', () => {
        const r = resolveWalkthroughLabelVisibility(walkVisible({ distance: 0.5 }))
        expect(r.visible).toBe(true)
    })
    it('exactly at max distance is still visible (inclusive boundary)', () => {
        const r = resolveWalkthroughLabelVisibility(walkVisible({ distance: WALKTHROUGH_LABEL_MAX_DISTANCE_M }))
        expect(r).toEqual({ visible: true, reason: 'VISIBLE_NEARBY' })
    })
})

// §20.15-16 — distance boundary is explicit + configurable, not a magic number
describe('§20.15-16 distance boundary', () => {
    it('default max distance constant is the documented 18 m', () => {
        expect(WALKTHROUGH_LABEL_MAX_DISTANCE_M).toBe(18)
    })
    it('caller-supplied maxDistance overrides the default', () => {
        const near = resolveWalkthroughLabelVisibility(walkVisible({ distance: 10, maxDistance: 8 }))
        expect(near).toEqual({ visible: false, reason: 'HIDDEN_TOO_FAR' })
        const within = resolveWalkthroughLabelVisibility(walkVisible({ distance: 6, maxDistance: 8 }))
        expect(within.visible).toBe(true)
    })
})

// §20.17 — NaN distance is treated as out-of-range (never silently visible)
describe('§20.17 degenerate distance', () => {
    it('NaN distance does not pass the range gate', () => {
        const r = resolveWalkthroughLabelVisibility(walkVisible({ distance: Number.NaN }))
        expect(r).toEqual({ visible: false, reason: 'HIDDEN_TOO_FAR' })
    })
})

// §20.18 — per-label independence: same policy, per-label facts decide separately
describe('§20.18 per-label independence', () => {
    it('two labels with different facts resolve independently', () => {
        // Uptake 01: in front, near, unobstructed → visible.
        const uptake = resolveWalkthroughLabelVisibility(walkVisible({ distance: 4 }))
        // Injection Room 01: occluded by a wall between camera and anchor → hidden.
        const injection = resolveWalkthroughLabelVisibility(walkVisible({ distance: 4, occluded: true }))
        expect(uptake.visible).toBe(true)
        expect(injection.visible).toBe(false)
        expect(injection.reason).toBe('HIDDEN_OCCLUDED')
    })
})

// §20.19 — purity: the policy has no side effects and does not mutate its input
describe('§20.19 purity / no mutation', () => {
    it('does not mutate the input object', () => {
        const input = walkVisible({ occluded: true })
        const snapshot = JSON.stringify(input)
        resolveWalkthroughLabelVisibility(input)
        expect(JSON.stringify(input)).toBe(snapshot)
    })
    it('is deterministic for identical inputs', () => {
        const a = resolveWalkthroughLabelVisibility(walkVisible({ occluded: true }))
        const b = resolveWalkthroughLabelVisibility(walkVisible({ occluded: true }))
        expect(a).toEqual(b)
    })
})

// §20.20 — every camera mode yields a well-formed result (no undefined/throw)
describe('§20.20 total function over camera modes', () => {
    const modes: CameraMode[] = ['PLANNING', 'WALKTHROUGH', 'BIRDS_EYE_CUTAWAY']
    it('returns a boolean visible + defined reason for all modes', () => {
        for (const mode of modes) {
            const r = resolveWalkthroughLabelVisibility(walkVisible({ cameraMode: mode }))
            expect(typeof r.visible).toBe('boolean')
            expect(r.reason).toBeTruthy()
        }
    })
})

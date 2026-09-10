/**
 * Build 1A walkthrough LABEL occlusion + visibility correction — integration /
 * UI-seam tests (§21).
 *
 * A full ClinicalProgramDecorator DOM mount needs a live iModel + viewport, so
 * these tests exercise the WIRING seam instead: the overlay's active-camera-mode
 * tracking (applyCameraMode → activeCameraMode → getActiveCameraMode), which is
 * exactly what the decorator reads via its getCameraMode input to choose the
 * label policy. Combined with the pure resolveWalkthroughLabelVisibility, this
 * proves:
 *   - a label is available (persistent) in PLANNING,
 *   - switching to WALKTHROUGH flips the policy so an occluded label is hidden,
 *   - switching back to PLANNING restores persistence,
 *   - the camera-mode / label decision performs NO planning-volume mutation.
 * The heavy walkthroughController (its @itwin deps) is mocked.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const applyCameraModeCtl = vi.fn(async () => true)
const loadStoreys = vi.fn(async () => [] as unknown[])

vi.mock('../components/spatial/walkthroughController', () => ({
    applyCameraMode: applyCameraModeCtl,
    loadStoreys,
    setWalkthroughFov: vi.fn(),
    turnAround: vi.fn(),
    getWalkEye: vi.fn(() => ({ x: 0, y: 0, z: 1.65 })),
}))

import { applyCameraMode, getActiveCameraMode } from '../components/spatial/spatialAssetOverlay'
import { resolveWalkthroughLabelVisibility } from '../components/spatial/walkthroughLabelVisibility'

// The decorator computes these viewport facts live; here we hold an occluded
// planning label fixed so ONLY the camera mode varies the outcome.
const occludedLabelFacts = {
    behindCamera: false,
    onScreen: true,
    occluded: true,
    distance: 4,
}

describe('Build 1A walkthrough §21 — camera-mode drives the label policy', () => {
    beforeEach(() => {
        applyCameraModeCtl.mockClear()
        loadStoreys.mockClear()
    })

    it('defaults to PLANNING and a planning label is persistent (available)', () => {
        expect(getActiveCameraMode()).toBe('PLANNING')
        const r = resolveWalkthroughLabelVisibility({ cameraMode: getActiveCameraMode(), ...occludedLabelFacts })
        expect(r).toEqual({ visible: true, reason: 'MODE_PERSISTENT' })
    })

    it('entering WALKTHROUGH tracks the active camera mode and hides the occluded label', async () => {
        await applyCameraMode('WALKTHROUGH')
        expect(applyCameraModeCtl).toHaveBeenCalledTimes(1)
        expect(getActiveCameraMode()).toBe('WALKTHROUGH')
        const r = resolveWalkthroughLabelVisibility({ cameraMode: getActiveCameraMode(), ...occludedLabelFacts })
        expect(r).toEqual({ visible: false, reason: 'HIDDEN_OCCLUDED' })
    })

    it('the SAME label facts flip from hidden→persistent when returning to PLANNING', async () => {
        await applyCameraMode('WALKTHROUGH')
        const hidden = resolveWalkthroughLabelVisibility({ cameraMode: getActiveCameraMode(), ...occludedLabelFacts })
        expect(hidden.visible).toBe(false)

        await applyCameraMode('PLANNING')
        expect(getActiveCameraMode()).toBe('PLANNING')
        const shown = resolveWalkthroughLabelVisibility({ cameraMode: getActiveCameraMode(), ...occludedLabelFacts })
        expect(shown).toEqual({ visible: true, reason: 'MODE_PERSISTENT' })
    })

    it('BIRDS_EYE_CUTAWAY keeps labels persistent (accepted planning behavior)', async () => {
        await applyCameraMode('BIRDS_EYE_CUTAWAY')
        expect(getActiveCameraMode()).toBe('BIRDS_EYE_CUTAWAY')
        const r = resolveWalkthroughLabelVisibility({ cameraMode: getActiveCameraMode(), ...occludedLabelFacts })
        expect(r.reason).toBe('MODE_PERSISTENT')
    })

    it('a walkthrough label directly in view (unobstructed, near) remains visible', async () => {
        await applyCameraMode('WALKTHROUGH')
        const r = resolveWalkthroughLabelVisibility({
            cameraMode: getActiveCameraMode(),
            behindCamera: false,
            onScreen: true,
            occluded: false,
            distance: 4,
        })
        expect(r).toEqual({ visible: true, reason: 'VISIBLE_NEARBY' })
    })

    it('camera-mode switching never writes the iModel (view-only): controller called without mutation opts', async () => {
        await applyCameraMode('WALKTHROUGH')
        // The overlay applyCameraMode delegates to the controller for view state only.
        // It must not be invoked with any engineering-write / domain-mutation payload.
        const [mode, opts] = applyCameraModeCtl.mock.calls[0] as unknown as [string, Record<string, unknown> | undefined]
        expect(mode).toBe('WALKTHROUGH')
        // No planning-volume params, coordinates, or lock flags are forwarded.
        const forwarded = opts ?? {}
        expect(Object.keys(forwarded).some((k) => /volume|prism|coord|lock|param/i.test(k))).toBe(false)
    })
})

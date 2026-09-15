/**
 * EVI-MA-07A.1 — tests for the LIVE darkening root-cause diagnostic.
 *
 * These prove the diagnostic itself is correct: it captures the elementsFromPoint
 * stack + full-viewport elements + common-ancestor dimmers from the real DOM, and
 * classifies the root cause deterministically. This is the instrument the spec
 * requires to prove the live cause; the tests guarantee it reports truthfully.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import {
    capturePlacementDarkeningSnapshot,
    classifyDarkening,
    isDarkeningContributor,
    snapshotElement,
    type PlacementStateSnapshot,
    type BentleyViewStateSnapshot,
} from '../components/spatial/placementDarkeningDiagnostic'

const IDLE_STATE: PlacementStateSnapshot = {
    placementModeActive: false,
    intentPresent: false,
    intentSummary: undefined,
    interactionState: 'IDLE',
    openPanel: null,
    selectedCatalogAssetId: undefined,
    pendingPlacementAssetId: undefined,
    placementCandidatePresent: false,
    placementToolActive: false,
    activeBentleyToolId: 'Select',
    selectedAppObject: undefined,
}
const NO_VP: BentleyViewStateSnapshot = { hasViewport: false, note: 'test' }

function setViewportSize(el: HTMLElement, x: number, y: number, w: number, h: number) {
    el.getBoundingClientRect = () => ({ x, y, width: w, height: h, top: y, left: x, right: x + w, bottom: y + h, toJSON: () => ({}) }) as DOMRect
}

describe('EVI-MA-07A.1 isDarkeningContributor', () => {
    const base = { tagName: 'DIV', id: '', className: '', rect: { x: 0, y: 0, width: 10, height: 10 }, zIndex: 'auto', position: 'static', pointerEvents: 'auto', background: '', backgroundColor: 'rgba(0, 0, 0, 0)', opacity: '1', filter: 'none', backdropFilter: 'none', visibility: 'visible', display: 'block', coversViewport: false }
    it('flags opacity < 1', () => { expect(isDarkeningContributor({ ...base, opacity: '0.4' })).toBe(true) })
    it('flags a real filter', () => { expect(isDarkeningContributor({ ...base, filter: 'brightness(0.4)' })).toBe(true) })
    it('flags a backdrop-filter', () => { expect(isDarkeningContributor({ ...base, backdropFilter: 'blur(4px)' })).toBe(true) })
    it('flags a translucent rgba background', () => { expect(isDarkeningContributor({ ...base, backgroundColor: 'rgba(10, 14, 20, 0.72)' })).toBe(true) })
    it('does NOT flag fully transparent or fully opaque backgrounds', () => {
        expect(isDarkeningContributor({ ...base, backgroundColor: 'rgba(0, 0, 0, 0)' })).toBe(false)
        expect(isDarkeningContributor({ ...base, backgroundColor: 'rgb(20, 20, 20)' })).toBe(false)
    })
})

describe('EVI-MA-07A.1 classifyDarkening', () => {
    function snap(partial: Parameters<typeof classifyDarkening>[0]) { return partial }

    it('ORPHANED_DOM_OVERLAY when a dimming element above the canvas covers the viewport', () => {
        const causes = classifyDarkening(snap({
            moment: 'AFTER_CANCEL_DARK', capturedAt: '', placementState: IDLE_STATE,
            viewport: { found: true, canvasFound: true },
            elementsFromPointStack: [
                { tagName: 'DIV', id: '', className: 'mystery', rect: { x: 0, y: 0, width: 100, height: 100 }, zIndex: '1200', position: 'absolute', pointerEvents: 'auto', background: '', backgroundColor: 'rgba(10,14,20,0.72)', opacity: '1', filter: 'none', backdropFilter: 'none', visibility: 'visible', display: 'block', coversViewport: true, canvasRelation: 'ABOVE_CANVAS' },
            ],
            pointerReceiver: undefined, fullViewportElements: [], commonAncestors: [], bentleyViewState: NO_VP,
        }))
        expect(causes).toContain('ORPHANED_DOM_OVERLAY')
    })

    it('COMMON_ANCESTOR_OPACITY when a shared ancestor has opacity < 1', () => {
        const dimAncestor = { tagName: 'MAIN', id: '', className: 'viewer-page', rect: { x: 0, y: 0, width: 100, height: 100 }, zIndex: 'auto', position: 'relative', pointerEvents: 'auto', background: '', backgroundColor: 'rgb(0,0,0)', opacity: '0.5', filter: 'none', backdropFilter: 'none', visibility: 'visible', display: 'block', coversViewport: true, canvasRelation: 'CONTAINS_CANVAS' as const }
        const causes = classifyDarkening(snap({
            moment: 'AFTER_CANCEL_DARK', capturedAt: '', placementState: IDLE_STATE,
            viewport: { found: true, canvasFound: true },
            elementsFromPointStack: [], pointerReceiver: undefined, fullViewportElements: [],
            commonAncestors: [
                { subject: '3D_VIEWPORT', chain: [dimAncestor] },
                { subject: '2D_FLOOR_PLAN', chain: [dimAncestor] },
                { subject: 'INSPECTION_PANEL', chain: [dimAncestor] },
            ],
            bentleyViewState: NO_VP,
        }))
        expect(causes).toContain('COMMON_ANCESTOR_OPACITY')
    })

    it('PLACEMENT_STATE_NOT_IDLE when placement is still active after cancel', () => {
        const causes = classifyDarkening(snap({
            moment: 'AFTER_CANCEL_DARK', capturedAt: '', placementState: { ...IDLE_STATE, placementModeActive: true },
            viewport: { found: true, canvasFound: true },
            elementsFromPointStack: [], pointerReceiver: undefined, fullViewportElements: [], commonAncestors: [], bentleyViewState: NO_VP,
        }))
        expect(causes).toContain('PLACEMENT_STATE_NOT_IDLE')
    })

    it('BENTLEY_DISPLAY_STATE_NOT_RESTORED when no DOM layer explains it but the canvas/scene is dark', () => {
        const causes = classifyDarkening(snap({
            moment: 'AFTER_CANCEL_DARK', capturedAt: '', placementState: IDLE_STATE,
            viewport: { found: true, canvasFound: true },
            elementsFromPointStack: [], pointerReceiver: undefined, fullViewportElements: [], commonAncestors: [],
            bentleyViewState: { hasViewport: true, canvasCssFilter: 'brightness(0.3)', featureOverrideProviderCount: 0, neverDrawnCount: 0 },
        }))
        expect(causes).toEqual(['BENTLEY_DISPLAY_STATE_NOT_RESTORED'])
    })

    it('NO_DARKENING_EVIDENCE for a clean normal snapshot (nothing dims)', () => {
        const causes = classifyDarkening(snap({
            moment: 'NORMAL', capturedAt: '', placementState: IDLE_STATE,
            viewport: { found: true, canvasFound: true },
            elementsFromPointStack: [], pointerReceiver: undefined, fullViewportElements: [], commonAncestors: [],
            bentleyViewState: { hasViewport: true, canvasCssOpacity: '1', canvasCssFilter: 'none', featureOverrideProviderCount: 0, neverDrawnCount: 0 },
        }))
        expect(causes).toEqual(['NO_DARKENING_EVIDENCE'])
    })
})

describe('EVI-MA-07A.1 capture (jsdom DOM)', () => {
    beforeEach(() => { document.body.innerHTML = '' })

    it('captures the viewport host, its center, and a full-viewport dimming overlay above the canvas', () => {
        const stage = document.createElement('section')
        stage.className = 'viewer-stage'
        setViewportSize(stage, 0, 0, 1000, 800)
        const canvas = document.createElement('canvas')
        stage.appendChild(canvas)
        document.body.appendChild(stage)

        const snap = capturePlacementDarkeningSnapshot({
            moment: 'AFTER_CANCEL_DARK',
            placementState: IDLE_STATE,
            bentleyViewState: NO_VP,
        })
        expect(snap.viewport.found).toBe(true)
        expect(snap.viewport.canvasFound).toBe(true)
        expect(snap.viewport.centerX).toBe(500)
        expect(snap.viewport.centerY).toBe(400)
        // The common-ancestor subjects are always enumerated (even if some absent).
        expect(snap.commonAncestors.map((c) => c.subject)).toEqual(['3D_VIEWPORT', '2D_FLOOR_PLAN', 'INSPECTION_PANEL'])
    })

    it('snapshotElement records canvas relation and darkening-relevant styles', () => {
        const stage = document.createElement('section')
        setViewportSize(stage, 0, 0, 100, 100)
        const canvas = document.createElement('canvas')
        stage.appendChild(canvas)
        document.body.appendChild(stage)
        const s = snapshotElement(stage, { x: 0, y: 0, width: 100, height: 100 }, canvas)
        expect(s.canvasRelation).toBe('CONTAINS_CANVAS')
        expect(s.coversViewport).toBe(true)
        const sc = snapshotElement(canvas, { x: 0, y: 0, width: 100, height: 100 }, canvas)
        expect(sc.canvasRelation).toBe('IS_CANVAS')
    })
})

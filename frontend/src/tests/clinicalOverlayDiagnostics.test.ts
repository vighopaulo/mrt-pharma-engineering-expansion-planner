import { describe, it, expect } from 'vitest'
import {
    classifyClinicalOverlayFailure,
    summarizeClinicalOverlayObservation,
    type ClinicalOverlayObservation,
} from '../components/spatial/clinicalOverlayDiagnostics'

/** A fully-healthy observation; individual tests break one link. */
function healthy(): ClinicalOverlayObservation {
    return {
        assignmentFound: true,
        roomMatchCount: 1,
        footprintFound: true,
        activeStoreyId: 'first',
        roomStoreyId: 'first',
        overlayRecordCount: 1,
        targetOverlayRecordFound: true,
        decoratorRegistered: true,
        decoratorEnabled: true,
        decoratorInvalidatedAfterChange: true,
        drawAttempted: true,
        anchorInsideViewport: true,
        htmlLabelAttached: true,
        footprintGraphicCreated: true,
        overlayHiddenByLayout: false,
    }
}

describe('§47 ID mismatch', () => {
    it('roomMatchCount 0 => ASSIGNMENT_TO_SPACE_ID_MISMATCH', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), roomMatchCount: 0 })).toBe('ASSIGNMENT_TO_SPACE_ID_MISMATCH')
    })
    it('assignment absent => ASSIGNMENT_NOT_FOUND', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), assignmentFound: false })).toBe('ASSIGNMENT_NOT_FOUND')
    })
    it('roomMatchCount > 1 => AMBIGUOUS_BIM_SPACE_IDENTITY', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), roomMatchCount: 2 })).toBe('AMBIGUOUS_BIM_SPACE_IDENTITY')
    })
})

describe('§48 storey mismatch', () => {
    it('different canonical storey => STOREY_FILTER_MISMATCH', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), activeStoreyId: 'second', roomStoreyId: 'first' })).toBe('STOREY_FILTER_MISMATCH')
    })
    it('unknown room storey while a storey is active => STOREY_FILTER_MISMATCH', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), activeStoreyId: 'first', roomStoreyId: undefined })).toBe('STOREY_FILTER_MISMATCH')
    })
    it('all-building (undefined active) is not a storey failure', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), activeStoreyId: undefined, roomStoreyId: 'first' })).toBe('NO_FAILURE_DETECTED')
    })
})

describe('§49 no footprint', () => {
    it('footprintFound false => ROOM_FOOTPRINT_NOT_FOUND', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), footprintFound: false })).toBe('ROOM_FOOTPRINT_NOT_FOUND')
    })
})

describe('§50 overlay filtered', () => {
    it('target record absent => OVERLAY_MODEL_POLICY_FILTERED_ASSIGNMENT', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), targetOverlayRecordFound: false })).toBe('OVERLAY_MODEL_POLICY_FILTERED_ASSIGNMENT')
    })
})

describe('§51 decorator', () => {
    it('not registered => DECORATOR_NOT_REGISTERED', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), decoratorRegistered: false })).toBe('DECORATOR_NOT_REGISTERED')
    })
    it('disabled => DECORATOR_DISABLED', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), decoratorEnabled: false })).toBe('DECORATOR_DISABLED')
    })
    it('not invalidated => DECORATOR_NOT_INVALIDATED', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), decoratorInvalidatedAfterChange: false })).toBe('DECORATOR_NOT_INVALIDATED')
    })
    it('draw not reached => DECORATOR_DRAW_PATH_NOT_REACHED', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), drawAttempted: false })).toBe('DECORATOR_DRAW_PATH_NOT_REACHED')
    })
})

describe('§52 offscreen / html / graphic / layout', () => {
    it('anchor offscreen => LABEL_ANCHOR_OFFSCREEN', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), anchorInsideViewport: false })).toBe('LABEL_ANCHOR_OFFSCREEN')
    })
    it('html not attached => HTML_DECORATION_NOT_ATTACHED', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), htmlLabelAttached: false })).toBe('HTML_DECORATION_NOT_ATTACHED')
    })
    it('graphic not created => FOOTPRINT_GRAPHIC_NOT_CREATED', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), footprintGraphicCreated: false })).toBe('FOOTPRINT_GRAPHIC_NOT_CREATED')
    })
    it('hidden by layout => OVERLAY_HIDDEN_BY_LAYOUT', () => {
        expect(classifyClinicalOverlayFailure({ ...healthy(), overlayHiddenByLayout: true })).toBe('OVERLAY_HIDDEN_BY_LAYOUT')
    })
})

describe('§53 success', () => {
    it('all healthy => NO_FAILURE_DETECTED', () => {
        expect(classifyClinicalOverlayFailure(healthy())).toBe('NO_FAILURE_DETECTED')
    })
    it('summary is bounded and contains the class + no secrets', () => {
        const o = healthy()
        const s = summarizeClinicalOverlayObservation(o, 'NO_FAILURE_DETECTED')
        expect(s).toContain('class=NO_FAILURE_DETECTED')
        expect(s.toLowerCase()).not.toContain('token')
        expect(s.toLowerCase()).not.toContain('authorization')
        expect(s.length).toBeLessThan(400)
    })
})

describe('chain ordering', () => {
    it('reports the FIRST broken link, not later ones', () => {
        // footprint missing AND decorator unregistered => footprint wins (earlier).
        const o = { ...healthy(), footprintFound: false, decoratorRegistered: false }
        expect(classifyClinicalOverlayFailure(o)).toBe('ROOM_FOOTPRINT_NOT_FOUND')
    })
})

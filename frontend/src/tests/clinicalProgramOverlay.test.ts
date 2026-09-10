import { describe, it, expect } from 'vitest'
import {
    deriveClinicalProgramOverlay,
    footprintCentroid,
    overlayPriority,
    overlayRoomEligible,
} from '../components/spatial/clinicalProgramOverlay'
import { assignClinicalFunction, type ClinicalProgramAssignment } from '../components/spatial/clinicalProgram'
import type { SpatialRoomReference } from '../domain/assets/spatialSemantics'
import type { StoreyZRange } from '../components/spatial/planningPlan'

// A room with a finite range (First Floor: z 0..4).
function room(id: string, label: string, z = { low: 0, high: 4 }): SpatialRoomReference {
    return {
        roomId: id,
        displayName: label,
        sourceClass: 'BuildingSpatial:Space',
        confidence: 'AUTHORITATIVE_BIM',
        geometryType: 'RANGE_ONLY',
        range: { low: { x: 0, y: 0, z: z.low }, high: { x: 10, y: 8, z: z.high } },
    } as SpatialRoomReference
}

const STOREYS: StoreyZRange[] = [
    { id: 'first', label: 'First Floor', zLow: 0, zHigh: 4 },
    { id: 'second', label: 'Second Floor', zLow: 4, zHigh: 8 },
]

function assignUptake(spaceId: string, label: string, existing: ClinicalProgramAssignment[] = []): ClinicalProgramAssignment[] {
    const r = assignClinicalFunction({ bimSpace: { bimSpaceId: spaceId, originalBimLabel: label, bimStoreyId: 'first' }, clinicalFunction: 'UPTAKE_ROOM', existingAssignments: existing })
    if (!r.ok) throw new Error(r.reason)
    return r.assignments
}

describe('§28 ASSIGNED_ROOM_OVERLAY_RESOLUTION', () => {
    it('produces exactly one overlay record for an assigned space', () => {
        const rooms = [room('SPACE_A', '1AC1 CENTRAL WAITING')]
        const assignments = assignUptake('SPACE_A', '1AC1 CENTRAL WAITING')
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS })
        expect(overlay).toHaveLength(1)
        expect(overlay[0].bimSpaceId).toBe('SPACE_A')
        expect(overlay[0].assigned).toBe(true)
    })
})

describe('§29 WRONG_SPACE does not resolve', () => {
    it('no overlay when the assignment references a different space', () => {
        const rooms = [room('SPACE_B', 'OTHER ROOM')]
        const assignments = assignUptake('SPACE_A', '1AC1 CENTRAL WAITING') // A, not B
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS })
        expect(overlay).toHaveLength(0)
    })
})

describe('§30 PHYSICAL_LABEL_PRECEDENCE', () => {
    it('assigned room label is the MRT display name', () => {
        const rooms = [room('SPACE_A', '1AC1 CENTRAL WAITING')]
        const assignments = assignUptake('SPACE_A', '1AC1 CENTRAL WAITING')
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS })
        expect(overlay[0].label).toBe('Uptake 01')
        expect(overlay[0].originalBimLabel).toBe('1AC1 CENTRAL WAITING')
    })
})

describe('§31 FOOTPRINT_IDENTITY', () => {
    it('overlay footprint uses the BIM-derived range coordinates', () => {
        const rooms = [room('SPACE_A', '1AC1 CENTRAL WAITING')]
        const assignments = assignUptake('SPACE_A', '1AC1 CENTRAL WAITING')
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS })
        const ring = overlay[0].footprint.ring
        const xs = ring.map((p) => p.x)
        const ys = ring.map((p) => p.y)
        expect(Math.min(...xs)).toBe(0)
        expect(Math.max(...xs)).toBe(10)
        expect(Math.min(...ys)).toBe(0)
        expect(Math.max(...ys)).toBe(8)
    })
})

describe('§32 ANCHOR', () => {
    it('anchor is the footprint centroid', () => {
        const rooms = [room('SPACE_A', '1AC1 CENTRAL WAITING')]
        const assignments = assignUptake('SPACE_A', '1AC1 CENTRAL WAITING')
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS })
        expect(overlay[0].anchor.x).toBe(5)
        expect(overlay[0].anchor.y).toBe(4)
    })
    it('footprintCentroid is deterministic', () => {
        const c = footprintCentroid({ roomId: 'x', label: 'y', ring: [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 2 }, { x: 0, y: 2 }], elevation: 1, zLow: 0, zHigh: 3, provenance: 'BIM_DERIVED' })
        expect(c).toEqual({ x: 2, y: 1, z: 1 })
    })
})

describe('§33/§34/§35 STOREY FILTER', () => {
    it('First Floor room visible when activeStorey = First Floor', () => {
        const rooms = [room('SPACE_A', '1AC1 CENTRAL WAITING', { low: 0, high: 4 })]
        const assignments = assignUptake('SPACE_A', '1AC1 CENTRAL WAITING')
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS, activeStoreyId: 'first' })
        expect(overlay).toHaveLength(1)
    })
    it('First Floor room NOT visible when activeStorey = Second Floor', () => {
        const rooms = [room('SPACE_A', '1AC1 CENTRAL WAITING', { low: 0, high: 4 })]
        const assignments = assignUptake('SPACE_A', '1AC1 CENTRAL WAITING')
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS, activeStoreyId: 'second' })
        expect(overlay).toHaveLength(0)
    })
    it('ALL_BUILDING (undefined) keeps assigned rooms eligible', () => {
        const rooms = [room('SPACE_A', '1AC1 CENTRAL WAITING')]
        const assignments = assignUptake('SPACE_A', '1AC1 CENTRAL WAITING')
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS, activeStoreyId: undefined })
        expect(overlay).toHaveLength(1)
    })
    it('overlayRoomEligible policy', () => {
        expect(overlayRoomEligible(undefined, 'first')).toBe(true)
        expect(overlayRoomEligible('first', 'first')).toBe(true)
        expect(overlayRoomEligible('second', 'first')).toBe(false)
        expect(overlayRoomEligible('first', undefined)).toBe(false)
    })
})

describe('§36 ASSIGNED_PRIORITY', () => {
    it('assigned room wins over unassigned under a budget of 1', () => {
        const rooms = [room('U', 'UNASSIGNED ROOM'), room('A', 'ASSIGNED ROOM')]
        const assignments = assignUptake('A', 'ASSIGNED ROOM')
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS, includeUnassigned: true, maxLabels: 1 })
        expect(overlay).toHaveLength(1)
        expect(overlay[0].bimSpaceId).toBe('A')
    })
})

describe('§37 SELECTED_PRIORITY', () => {
    it('selected assigned room receives the highest priority', () => {
        let assignments = assignUptake('A1', 'ROOM ONE')
        const r2 = assignClinicalFunction({ bimSpace: { bimSpaceId: 'A2', originalBimLabel: 'ROOM TWO' }, clinicalFunction: 'UPTAKE_ROOM', existingAssignments: assignments })
        if (r2.ok) assignments = r2.assignments
        const rooms = [room('A1', 'ROOM ONE'), room('A2', 'ROOM TWO')]
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS, selectedRoomId: 'A2' })
        // highest priority is drawn/selected; sorted highest-first
        expect(overlay[0].bimSpaceId).toBe('A2')
        expect(overlay[0].selected).toBe(true)
        expect(overlay[0].priority).toBeGreaterThan(overlay[1].priority)
    })
    it('overlayPriority ranking', () => {
        expect(overlayPriority(true, true)).toBe(3)
        expect(overlayPriority(true, false)).toBe(2)
        expect(overlayPriority(false, true)).toBe(1)
        expect(overlayPriority(false, false)).toBe(0)
    })
})

describe('§38 RESET removes overlay', () => {
    it('no overlay record after reset; room still exists', () => {
        const rooms = [room('SPACE_A', '1AC1 CENTRAL WAITING')]
        // reset = empty assignments
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments: [], storeys: STOREYS })
        expect(overlay).toHaveLength(0)
    })
})

describe('§39 ASSIGNMENT_UPDATE refreshes label', () => {
    it('changing the assignment changes the derived label', () => {
        const rooms = [room('SPACE_A', '1AC1 CENTRAL WAITING')]
        let assignments = assignUptake('SPACE_A', '1AC1 CENTRAL WAITING')
        expect(deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS })[0].label).toBe('Uptake 01')
        const r = assignClinicalFunction({ bimSpace: { bimSpaceId: 'SPACE_A', originalBimLabel: '1AC1 CENTRAL WAITING' }, clinicalFunction: 'PET_CT_SCANNER_ROOM', existingAssignments: assignments })
        if (r.ok) assignments = r.assignments
        const overlay = deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS })
        expect(overlay[0].label).toBe('PET/CT 01')
        expect(overlay[0].clinicalFunction).toBe('PET_CT_SCANNER_ROOM')
    })
})

describe('§40 BIM immutability', () => {
    it('deriving the overlay does not mutate the room or assignment inputs', () => {
        const rooms = [room('SPACE_A', '1AC1 CENTRAL WAITING')]
        const assignments = assignUptake('SPACE_A', '1AC1 CENTRAL WAITING')
        const roomsSnapshot = JSON.stringify(rooms)
        const assignmentsSnapshot = JSON.stringify(assignments)
        deriveClinicalProgramOverlay({ rooms, assignments, storeys: STOREYS })
        expect(JSON.stringify(rooms)).toBe(roomsSnapshot)
        expect(JSON.stringify(assignments)).toBe(assignmentsSnapshot)
    })
    it('skips rooms without a finite range (no fabricated footprint)', () => {
        const noRange = { roomId: 'NR', displayName: 'NO RANGE', sourceClass: 'BuildingSpatial:Space', confidence: 'DERIVED', geometryType: 'NOT_AVAILABLE' } as SpatialRoomReference
        const assignments = assignUptake('NR', 'NO RANGE')
        const overlay = deriveClinicalProgramOverlay({ rooms: [noRange], assignments, storeys: STOREYS })
        expect(overlay).toHaveLength(0)
    })
})

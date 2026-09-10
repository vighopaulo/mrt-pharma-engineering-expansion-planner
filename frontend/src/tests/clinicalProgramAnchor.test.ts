import { describe, it, expect } from 'vitest'
import {
    resolveClinicalProgramFacilityAnchor,
    resolveProgramDisplayAnchor,
    resolveProgramDisplayBoundary,
    describeGeometryQuality,
} from '../components/spatial/clinicalProgramAnchor'
import { deriveClinicalProgramOverlay } from '../components/spatial/clinicalProgramOverlay'
import { assignClinicalFunction, loadProgramAssignments, saveProgramAssignments, type ClinicalProgramAssignment } from '../components/spatial/clinicalProgram'
import type { SpatialRoomReference } from '../domain/assets/spatialSemantics'
import type { StoreyZRange } from '../components/spatial/planningPlan'

// 1AC1 CENTRAL WAITING live geometry (from the diagnostic): low(-20.2,25.8,0), high(0.2,35.0,4.6).
function centralWaiting(): SpatialRoomReference {
    return {
        roomId: 'SPACE_CW',
        displayName: '1AC1 CENTRAL WAITING',
        sourceClass: 'BuildingSpatial:Space',
        confidence: 'AUTHORITATIVE_BIM',
        geometryType: 'RANGE_ONLY',
        range: { low: { x: -20.2, y: 25.8, z: 0 }, high: { x: 0.2, y: 35.0, z: 4.6 } },
    } as SpatialRoomReference
}

const STOREYS: StoreyZRange[] = [
    { id: 'first', label: 'First Floor', zLow: 0, zHigh: 4.6 },
    { id: 'second', label: 'Second Floor', zLow: 4.6, zHigh: 9 },
]

function uptakeAssignment(): ClinicalProgramAssignment[] {
    const r = assignClinicalFunction({ bimSpace: { bimSpaceId: 'SPACE_CW', originalBimLabel: '1AC1 CENTRAL WAITING', bimStoreyId: 'first' }, clinicalFunction: 'UPTAKE_ROOM', existingAssignments: [] })
    if (!r.ok) throw new Error(r.reason)
    return r.assignments
}

describe('§35 RANGE approximation classification', () => {
    it('RANGE_ONLY room => BIM_RANGE_APPROXIMATION, never EXACT_ROOM_BOUNDARY', () => {
        const a = resolveClinicalProgramFacilityAnchor({ room: centralWaiting(), storeys: STOREYS })
        expect(a.geometryQuality).toBe('BIM_RANGE_APPROXIMATION')
        expect(a.geometrySource).toBe('BIM_SPATIAL_RANGE')
        expect(a.geometryQuality).not.toBe('EXACT_ROOM_BOUNDARY')
    })
})

describe('§36 EXACT boundary classification', () => {
    it('authoritative boundary => EXACT_ROOM_BOUNDARY', () => {
        const a = resolveClinicalProgramFacilityAnchor({
            room: centralWaiting(),
            storeys: STOREYS,
            exactBoundary: { ring: [{ x: -18, y: 26 }, { x: -2, y: 26 }, { x: -2, y: 34 }, { x: -18, y: 34 }], elevation: 0 },
        })
        expect(a.geometryQuality).toBe('EXACT_ROOM_BOUNDARY')
        expect(a.geometrySource).toBe('AUTHORITATIVE_BIM_SPACE_GEOMETRY')
    })
})

describe('§28/§29/§30 camera invariance (pure — no camera input possible)', () => {
    const room = centralWaiting()
    it('identical BIM inputs always yield the identical facility anchor', () => {
        const a1 = resolveClinicalProgramFacilityAnchor({ room, storeys: STOREYS })
        // Simulate "after rotate/pan/zoom": the function has NO camera parameter,
        // so a second call with the same BIM inputs must be numerically identical.
        const a2 = resolveClinicalProgramFacilityAnchor({ room, storeys: STOREYS })
        expect(a2.worldAnchor).toEqual(a1.worldAnchor)
        const delta = { dx: a2.worldAnchor.x - a1.worldAnchor.x, dy: a2.worldAnchor.y - a1.worldAnchor.y, dz: a2.worldAnchor.z - a1.worldAnchor.z }
        expect(delta).toEqual({ dx: 0, dy: 0, dz: 0 })
    })
    it('anchor is the range centroid in world coordinates', () => {
        const a = resolveClinicalProgramFacilityAnchor({ room, storeys: STOREYS })
        expect(a.worldAnchor.x).toBeCloseTo((-20.2 + 0.2) / 2, 6) // -10.0
        expect(a.worldAnchor.y).toBeCloseTo((25.8 + 35.0) / 2, 6) // 30.4
        expect(a.worldAnchor.z).toBeCloseTo(0, 6)
    })
})

describe('§37 display offset immutability', () => {
    it('facility Z unchanged; display Z = facility + offset', () => {
        const a = resolveClinicalProgramFacilityAnchor({ room: centralWaiting(), storeys: STOREYS })
        const beforeZ = a.worldAnchor.z
        const display = resolveProgramDisplayAnchor({ facilityAnchor: a, zOffset: 0.15 })
        expect(a.worldAnchor.z).toBe(beforeZ) // facility not mutated
        expect(display.z).toBeCloseTo(beforeZ + 0.15, 6)
        expect(display.x).toBe(a.worldAnchor.x)
        expect(display.y).toBe(a.worldAnchor.y)
    })
    it('display boundary is lifted but facility boundary unchanged', () => {
        const a = resolveClinicalProgramFacilityAnchor({ room: centralWaiting(), storeys: STOREYS })
        const b0z = a.boundary![0].z
        const db = resolveProgramDisplayBoundary({ facilityAnchor: a, zOffset: 0.15 })!
        expect(a.boundary![0].z).toBe(b0z)
        expect(db[0].z).toBeCloseTo(b0z + 0.15, 6)
    })
})

describe('§33 storey anchor', () => {
    it('resolves to First Floor for a z=0..4.6 room', () => {
        const a = resolveClinicalProgramFacilityAnchor({ room: centralWaiting(), storeys: STOREYS })
        expect(a.storeyId).toBe('first')
    })
})

describe('§31/§32 reload + BIM-space identity via overlay', () => {
    it('persisted assignment re-derives the same overlay location by bimSpaceId', () => {
        const store: Record<string, string> = {}
        const storage = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v } }
        const assignments = uptakeAssignment()
        saveProgramAssignments('clinic', assignments, storage)
        // Simulate reload: reload persisted, re-derive overlay from BIM rooms.
        const reloaded = loadProgramAssignments('clinic', storage)
        const overlay = deriveClinicalProgramOverlay({ rooms: [centralWaiting()], assignments: reloaded, storeys: STOREYS })
        expect(overlay).toHaveLength(1)
        expect(overlay[0].bimSpaceId).toBe('SPACE_CW')
        expect(overlay[0].facilityAnchor.x).toBeCloseTo(-10.0, 6)
        expect(overlay[0].facilityAnchor.y).toBeCloseTo(30.4, 6)
    })
})

describe('§34 iModel scope', () => {
    it('assignment saved under one iModel does not load under another', () => {
        const store: Record<string, string> = {}
        const storage = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v } }
        saveProgramAssignments('clinic', uptakeAssignment(), storage)
        const overlayFixture = deriveClinicalProgramOverlay({ rooms: [centralWaiting()], assignments: loadProgramAssignments('fixture', storage), storeys: STOREYS })
        expect(overlayFixture).toHaveLength(0)
    })
})

describe('overlay carries the explicit location model', () => {
    it('record has facilityAnchor, displayAnchor, geometrySource, geometryQuality, boundary', () => {
        const overlay = deriveClinicalProgramOverlay({ rooms: [centralWaiting()], assignments: uptakeAssignment(), storeys: STOREYS, displayZOffset: 0.15 })
        const r = overlay[0]
        expect(r.facilityAnchor).toBeDefined()
        expect(r.displayAnchor.z).toBeCloseTo(r.facilityAnchor.z + 0.15, 6)
        expect(r.geometrySource).toBe('BIM_SPATIAL_RANGE')
        expect(r.geometryQuality).toBe('BIM_RANGE_APPROXIMATION')
        expect(r.boundary && r.boundary.length).toBe(4)
        // Boundary vertices are world coordinates (not screen-space).
        expect(r.boundary!.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.z))).toBe(true)
    })
})

describe('§40 fixed BIM-space identity (no label rematch)', () => {
    it('a different bimSpaceId with the same label does NOT resolve the assignment', () => {
        const otherRoom = { ...centralWaiting(), roomId: 'SPACE_OTHER' } as SpatialRoomReference
        const overlay = deriveClinicalProgramOverlay({ rooms: [otherRoom], assignments: uptakeAssignment(), storeys: STOREYS })
        expect(overlay).toHaveLength(0) // matched by id, not by the shared label
    })
})

describe('geometry-quality description', () => {
    it('never claims exact for a range', () => {
        expect(describeGeometryQuality('BIM_RANGE_APPROXIMATION')).toMatch(/approximation/i)
        expect(describeGeometryQuality('EXACT_ROOM_BOUNDARY')).toMatch(/boundary/i)
    })
})

/**
 * Build 1A.3 — pure storey-filter tests (§23). Proves the canonical storey filter
 * over the discovered-room collection: All = base; a specific storey = only its
 * own rooms; unresolved-storey rooms appear only under All; equal counts do not
 * imply equal membership; filtering never mutates the base; deterministic; iModel
 * scoped; unaffected by program-toggle / camera mode (no such inputs).
 */
import { describe, it, expect } from 'vitest'
import {
    discoverRoomVolumes,
    filterDiscoveredRoomsByStorey,
    countRoomsByStorey,
    type DiscoveredRoomVolume,
} from '../components/spatial/bimRoomVolumeRegistry'
import type { SpatialRoomReference, WorldRange3 } from '../domain/assets/spatialSemantics'
import type { StoreyZRange } from '../components/spatial/planningPlan'

const range = (lo: [number, number, number], hi: [number, number, number]): WorldRange3 => ({
    low: { x: lo[0], y: lo[1], z: lo[2] }, high: { x: hi[0], y: hi[1], z: hi[2] },
})
const room = (id: string, zLo: number, zHi: number, label?: string): SpatialRoomReference => ({
    roomId: id, displayName: label ?? `Room ${id}`, sourceClass: 'BuildingSpatial:Space',
    confidence: 'AUTHORITATIVE_BIM', geometryType: 'RANGE_ONLY', range: range([0, 0, zLo], [2, 2, zHi]),
})
const metaRoom = (id: string): SpatialRoomReference => ({
    roomId: id, displayName: `Meta ${id}`, sourceClass: 'BuildingSpatial:Space',
    confidence: 'AUTHORITATIVE_BIM', geometryType: 'METADATA_ONLY', // no range => unresolved storey
})

const STOREYS: StoreyZRange[] = [
    { id: 'FIRST', label: 'First Floor', zLow: 0, zHigh: 4 },
    { id: 'SECOND', label: 'Second Floor', zLow: 4, zHigh: 8 },
    { id: 'ROOF', label: 'Roof - Main', zLow: 8, zHigh: 10 },
    { id: 'TOF', label: 'TOF Footing', zLow: -2, zHigh: 0 },
]

// A multi-storey clinic: 2 first, 2 second, 1 roof, 1 tof, 1 unresolved.
const clinicRooms: SpatialRoomReference[] = [
    room('0xF1', 0.5, 3.5, '1DC1 WAITING / ACTIVITY AREA'),
    room('0xF2', 1, 3, '1AC1 CENTRAL WAITING'),
    room('0xS1', 5, 7, '2ND ROOM A'),
    room('0xS2', 5.5, 6.5, '2ND ROOM B'),
    room('0xR1', 8.5, 9.5, 'ROOF PLANT'),
    room('0xT1', -1.5, -0.5, 'FOOTING VOID'),
    metaRoom('0xU1'),
]

const disc = (): DiscoveredRoomVolume[] => discoverRoomVolumes({ iModelId: 'im-clinic', rooms: clinicRooms, storeys: STOREYS })

// §23.1 — All returns all discovered rooms
describe('§23.1 All returns all discovered rooms', () => {
    it('activeStorey undefined => full base collection', () => {
        const all = filterDiscoveredRoomsByStorey(disc(), undefined)
        expect(all).toHaveLength(clinicRooms.length)
    })
})

// §23.2/3/4/5 — each storey returns only its own rooms
describe('§23.2-5 each storey returns only its own rooms', () => {
    it('First Floor', () => {
        const f = filterDiscoveredRoomsByStorey(disc(), 'FIRST').map((r) => r.bimSpaceId).sort()
        expect(f).toEqual(['0xF1', '0xF2'])
    })
    it('Second Floor', () => {
        const s = filterDiscoveredRoomsByStorey(disc(), 'SECOND').map((r) => r.bimSpaceId).sort()
        expect(s).toEqual(['0xS1', '0xS2'])
    })
    it('Roof - Main', () => {
        expect(filterDiscoveredRoomsByStorey(disc(), 'ROOF').map((r) => r.bimSpaceId)).toEqual(['0xR1'])
    })
    it('TOF Footing', () => {
        expect(filterDiscoveredRoomsByStorey(disc(), 'TOF').map((r) => r.bimSpaceId)).toEqual(['0xT1'])
    })
    it('unresolved-storey room appears only under All (never a specific storey)', () => {
        expect(filterDiscoveredRoomsByStorey(disc(), 'FIRST').some((r) => r.bimSpaceId === '0xU1')).toBe(false)
        expect(filterDiscoveredRoomsByStorey(disc(), undefined).some((r) => r.bimSpaceId === '0xU1')).toBe(true)
    })
})

// §23.6 — equal counts on two storeys do NOT imply equal membership
describe('§23.6 equal counts ≠ equal membership', () => {
    it('First and Second both have 2 rooms but different identities', () => {
        const f = filterDiscoveredRoomsByStorey(disc(), 'FIRST').map((r) => r.bimSpaceId).sort()
        const s = filterDiscoveredRoomsByStorey(disc(), 'SECOND').map((r) => r.bimSpaceId).sort()
        expect(f.length).toBe(s.length) // coincidental equal count
        expect(f).not.toEqual(s) // but memberships differ (the real acceptance criterion)
    })
})

// §23.7/12 — filtering does not mutate the base array / base discovery unchanged
describe('§23.7/12 filtering never mutates the base', () => {
    it('the base array is unchanged after filtering', () => {
        const base = disc()
        const snapshot = base.map((r) => r.bimSpaceId)
        filterDiscoveredRoomsByStorey(base, 'FIRST')
        filterDiscoveredRoomsByStorey(base, undefined)
        expect(base.map((r) => r.bimSpaceId)).toEqual(snapshot)
    })
    it('All returns a COPY (not the same reference)', () => {
        const base = disc()
        const all = filterDiscoveredRoomsByStorey(base, undefined)
        expect(all).not.toBe(base)
        expect(all).toEqual(base)
    })
})

// §23.8 — filter transitions are deterministic
describe('§23.8 deterministic transitions', () => {
    it('All → First → Second → All yields stable, repeatable results', () => {
        const base = disc()
        const first1 = filterDiscoveredRoomsByStorey(base, 'FIRST').map((r) => r.bimSpaceId)
        filterDiscoveredRoomsByStorey(base, 'SECOND')
        const allBack = filterDiscoveredRoomsByStorey(base, undefined).length
        const first2 = filterDiscoveredRoomsByStorey(base, 'FIRST').map((r) => r.bimSpaceId)
        expect(first1).toEqual(first2)
        expect(allBack).toBe(clinicRooms.length)
    })
})

// §23.9 — unknown/unresolved storey policy explicit (counts bucket)
describe('§23.9 unresolved storey policy is explicit', () => {
    it('countRoomsByStorey buckets unresolved separately', () => {
        const c = countRoomsByStorey(disc())
        expect(c.all).toBe(clinicRooms.length)
        expect(c.unresolved).toBe(1) // 0xU1
        expect(c.byStorey['FIRST']).toBe(2)
        expect(c.byStorey['SECOND']).toBe(2)
        expect(c.byStorey['ROOF']).toBe(1)
        expect(c.byStorey['TOF']).toBe(1)
        // sum of storey buckets + unresolved === all
        const sum = Object.values(c.byStorey).reduce((a, b) => a + b, 0) + c.unresolved
        expect(sum).toBe(c.all)
    })
    it('a filter for a non-existent storey returns empty (never leaks)', () => {
        expect(filterDiscoveredRoomsByStorey(disc(), 'NON_EXISTENT')).toHaveLength(0)
    })
})

// §23.13 — iModel ownership unchanged across filters
describe('§23.13 iModel scoped across filters', () => {
    it('filtered rooms still carry the active iModel id', () => {
        expect(filterDiscoveredRoomsByStorey(disc(), 'FIRST').every((r) => r.iModelId === 'im-clinic')).toBe(true)
    })
})

// §23.14/15 — no program-toggle / camera-mode input to the pure filter
describe('§23.14/15 filter is a pure function of (rooms, activeStorey) only', () => {
    it('has no dependency on program-enabled or camera mode (same input => same output)', () => {
        const base = disc()
        const a = filterDiscoveredRoomsByStorey(base, 'FIRST')
        const b = filterDiscoveredRoomsByStorey(base, 'FIRST')
        expect(a.map((r) => r.bimSpaceId)).toEqual(b.map((r) => r.bimSpaceId))
    })
})

/**
 * Build 1A.2 — pure generic selected-room diagnostic + geometry-status tests
 * (§20). Proves the diagnostic targets the selected room's cache state, reflects
 * exact vs range vs not-available honestly, never substitutes Uptake, and that a
 * later cache update flips the geometry authority (async status change).
 */
import { describe, it, expect } from 'vitest'
import {
    discoverRoomVolumes,
    buildSelectedRoomVolumeDiagnostic,
    formatSelectedRoomVolumeDiagnostic,
    resolveRoomVolumeGeometryQuality,
    type RoomMeshCacheFacts,
} from '../components/spatial/bimRoomVolumeRegistry'
import { resolveClinicalProgramFacilityAnchor } from '../components/spatial/clinicalProgramAnchor'
import type { SpatialRoomReference, WorldRange3 } from '../domain/assets/spatialSemantics'

const UPTAKE = '0x200000001f1'
const SELECTED = '0x200000001f6'

const range = (lo: [number, number, number], hi: [number, number, number]): WorldRange3 => ({
    low: { x: lo[0], y: lo[1], z: lo[2] }, high: { x: hi[0], y: hi[1], z: hi[2] },
})
const room = (o: Partial<SpatialRoomReference> & { roomId: string }): SpatialRoomReference => ({
    displayName: o.displayName ?? `Room ${o.roomId}`, sourceClass: 'BuildingSpatial:Space',
    confidence: 'AUTHORITATIVE_BIM', geometryType: o.geometryType ?? 'RANGE_ONLY', ...o,
})
const EXACT: RoomMeshCacheFacts = { exactMeshCached: true, exactMeshOk: true, vertexCount: 240, triangleCount: 476, closedMesh: true }

const clinicRooms: SpatialRoomReference[] = [
    room({ roomId: UPTAKE, displayName: '1AC1 CENTRAL WAITING', range: range([-20, 25, 0], [0, 35, 4.5]) }),
    room({ roomId: SELECTED, displayName: '1DC1 WAITING / ACTIVITY AREA', range: range([10, 40, 0], [18, 48, 3]) }),
]

// §20.1 / §20.7 — diagnostic targets selected room, never substitutes Uptake
describe('§20.1/7 diagnostic targets the SELECTED room, no Uptake substitution', () => {
    it('for the selected 1DC1 room the diagnostic carries its own identity', () => {
        const disc = discoverRoomVolumes({ iModelId: 'im-clinic', rooms: clinicRooms, storeys: [] })
        const sel = disc.find((r) => r.bimSpaceId === SELECTED)!
        const d = buildSelectedRoomVolumeDiagnostic({ room: sel, closedMesh: false, containmentStatus: 'NOT_EVALUATED', uptakeBaselineBimSpaceId: UPTAKE })
        expect(d.bimSpaceId).toBe(SELECTED)
        expect(d.originalBimLabel).toBe('1DC1 WAITING / ACTIVITY AREA')
        expect(d.isUptakeRegressionBaseline).toBe(false)
        const text = formatSelectedRoomVolumeDiagnostic(d)
        expect(text).toContain('BIM_SPACE_ID = 0x200000001f6')
        expect(text).not.toContain('0x200000001f1')
    })
})

// §20.2 — no selected room reports honestly (handled at overlay; here: empty discovery)
describe('§20.2 honest when the room is not discovered', () => {
    it('a room id absent from discovery is simply not found (no fabrication)', () => {
        const disc = discoverRoomVolumes({ iModelId: 'im-clinic', rooms: clinicRooms, storeys: [] })
        expect(disc.find((r) => r.bimSpaceId === '0xNOPE')).toBeUndefined()
    })
})

// §20.3/4/5/11 — exact vs range vs not-available; range never becomes exact
describe('§20.3/4/5/11 geometry authority is honest', () => {
    it('cached exact mesh => EXACT_SPACE_GEOMETRY', () => {
        const disc = discoverRoomVolumes({ iModelId: 'im-clinic', rooms: clinicRooms, storeys: [], meshCacheByRoom: { [SELECTED]: EXACT } })
        const sel = disc.find((r) => r.bimSpaceId === SELECTED)!
        expect(sel.geometryQuality).toBe('EXACT_SPACE_GEOMETRY')
        expect(sel.exactMeshAvailable).toBe(true)
        expect(sel.vertexCount).toBe(240)
        expect(sel.triangleCount).toBe(476)
    })
    it('range only => RANGE_ONLY_APPROXIMATION (never promoted to exact)', () => {
        const disc = discoverRoomVolumes({ iModelId: 'im-clinic', rooms: clinicRooms, storeys: [] })
        const sel = disc.find((r) => r.bimSpaceId === SELECTED)!
        expect(sel.geometryQuality).toBe('RANGE_ONLY_APPROXIMATION')
        expect(sel.exactMeshAvailable).toBe(false)
    })
    it('no geometry => NOT_AVAILABLE', () => {
        const disc = discoverRoomVolumes({ iModelId: 'im-clinic', rooms: [room({ roomId: '0xX', geometryType: 'NOT_AVAILABLE' })], storeys: [] })
        expect(disc[0].geometryQuality).toBe('NOT_AVAILABLE')
    })
})

// §20.6 — vertex/triangle counts come from the selected room's cache entry
describe('§20.6 counts come from the selected room cache', () => {
    it('the diagnostic uses the discovered room stats', () => {
        const disc = discoverRoomVolumes({ iModelId: 'im-clinic', rooms: clinicRooms, storeys: [], meshCacheByRoom: { [SELECTED]: EXACT } })
        const sel = disc.find((r) => r.bimSpaceId === SELECTED)!
        const d = buildSelectedRoomVolumeDiagnostic({ room: sel, closedMesh: true, containmentStatus: 'NOT_EVALUATED', uptakeBaselineBimSpaceId: UPTAKE })
        expect(d.vertexCount).toBe(240)
        expect(d.triangleCount).toBe(476)
        expect(d.closedMesh).toBe(true)
    })
})

// §20.8 — planning-volume absence remains absence
describe('§20.8 planning-volume absence honest', () => {
    it('no planning volume => hasPlanningVolume false, containment NOT_EVALUATED', () => {
        const disc = discoverRoomVolumes({ iModelId: 'im-clinic', rooms: clinicRooms, storeys: [] })
        const sel = disc.find((r) => r.bimSpaceId === SELECTED)!
        expect(sel.hasPlanningVolume).toBe(false)
        const d = buildSelectedRoomVolumeDiagnostic({ room: sel, closedMesh: false, containmentStatus: 'NOT_EVALUATED', uptakeBaselineBimSpaceId: UPTAKE })
        expect(d.hasPlanningVolume).toBe(false)
        expect(d.containmentStatus).toBe('NOT_EVALUATED')
    })
})

// §20.9/10 — inspection does not create assignment or planning volume
describe('§20.9/10 inspection has no side effects (pure model)', () => {
    it('discovery reflects only the assignments/volumes passed in — never adds any', () => {
        const disc = discoverRoomVolumes({
            iModelId: 'im-clinic', rooms: clinicRooms, storeys: [],
            meshCacheByRoom: { [SELECTED]: EXACT }, // inspected/extracted
            assignments: [], planningVolumeParentIds: [],
        })
        expect(disc.every((r) => !r.assigned)).toBe(true)
        expect(disc.every((r) => !r.hasPlanningVolume)).toBe(true)
    })
})

// §20.12 — async cache update can change geometry-quality status
describe('§20.12 async cache update flips geometry authority', () => {
    it('the SAME room is RANGE before the mesh caches and EXACT after (product status path)', () => {
        const sel = clinicRooms.find((r) => r.roomId === SELECTED)!
        // Before extraction: range approximation (no exactBoundary).
        const before = resolveClinicalProgramFacilityAnchor({ room: sel, storeys: [] })
        expect(before.geometryQuality).toBe('BIM_RANGE_APPROXIMATION')
        // After extraction: pass the cached exact outer loop as the exact boundary
        // (this is exactly what getClinicalProgramRoomGeometryQuality now does).
        const outerLoop = [{ x: 10, y: 40 }, { x: 18, y: 40 }, { x: 18, y: 48 }, { x: 10, y: 48 }]
        const after = resolveClinicalProgramFacilityAnchor({ room: sel, storeys: [], exactBoundary: { ring: outerLoop, elevation: 0 } })
        expect(after.geometryQuality).toBe('EXACT_ROOM_BOUNDARY')
    })
    it('resolveRoomVolumeGeometryQuality flips the same way (range → exact on cache)', () => {
        const sel = clinicRooms.find((r) => r.roomId === SELECTED)!
        expect(resolveRoomVolumeGeometryQuality({ room: sel, mesh: { exactMeshCached: false, exactMeshOk: false } })).toBe('RANGE_ONLY_APPROXIMATION')
        expect(resolveRoomVolumeGeometryQuality({ room: sel, mesh: EXACT })).toBe('EXACT_SPACE_GEOMETRY')
    })
})

// §20.13 — selected-room inspection remains iModel scoped
describe('§20.13 iModel scoped', () => {
    it('discovered rooms carry the active iModel id', () => {
        const disc = discoverRoomVolumes({ iModelId: 'im-clinic', rooms: clinicRooms, storeys: [] })
        expect(disc.every((r) => r.iModelId === 'im-clinic')).toBe(true)
    })
})

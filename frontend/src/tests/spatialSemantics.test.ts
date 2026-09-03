/**
 * Offline tests for the BIM-aware floor + room spatial-semantics domain.
 * Pure — no Bentley runtime, no WebGL, no viewport, no auth. Proves floor/room
 * association, honest status distinctions, deterministic boundary policy,
 * provenance, and position/identity immutability, plus store integration for
 * drag-commit reassociation, drag-preview non-authority, rotation immutability,
 * and delete isolation.
 */
import { describe, expect, it } from 'vitest'
import {
    assignmentInvariantHolds,
    associateFloor,
    associateRoom,
    buildPlacementIntent,
    CATALOG_TEST_ASSET_DEFINITION_ID,
    computeSpatialAssociation,
    EMPTY_MODEL_SEMANTICS,
    formatAssociationSlotLabel,
    GE_DISCOVERY_MI_RECORD,
    pointInFootprint,
    pointInRange3,
    summarizeAssociation,
    validateWorldRange,
    SpatialAssetStore,
    TEST_PROJECT_ID,
    type AssetInstance,
    type ScenarioProvenance,
    type SpatialModelSemantics,
    type SpatialFloorReference,
    type SpatialRoomReference,
} from '../domain/assets'

const DEV_SCENARIO: ScenarioProvenance = { scenarioId: 'MRT_DEV_SCENARIO', scenarioState: 'DRAFT' }
const newStore = () => new SpatialAssetStore({ projectId: TEST_PROJECT_ID, scenario: DEV_SCENARIO })

function placeAt(store: SpatialAssetStore, x: number, y: number, z: number): AssetInstance {
    const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
    if (!res.ok) throw new Error('intent build failed')
    store.beginPlacement(res.intent)
    const r = store.completePlacementAt({ x, y, z })
    if (!r.ok) throw new Error('placement failed')
    return r.instance
}

// --- synthetic BIM semantics fixtures ---------------------------------------

const floorL1: SpatialFloorReference = {
    floorId: 'F1', displayName: 'Level 1', sourceClass: 'BuildingSpatial:Story',
    sourceElementId: '0xF1', confidence: 'AUTHORITATIVE_BIM',
    elevation: 0, verticalRange: { zLow: 0, zHigh: 4 },
}
const floorL2: SpatialFloorReference = {
    floorId: 'F2', displayName: 'Level 2', sourceClass: 'BuildingSpatial:Story',
    sourceElementId: '0xF2', confidence: 'AUTHORITATIVE_BIM',
    elevation: 4, verticalRange: { zLow: 4, zHigh: 8 },
}
// Room A: a volume 0..10 x 0..10 x 0..4 on floor F1.
const roomA: SpatialRoomReference = {
    roomId: 'RA', displayName: 'PET/CT Room A', sourceClass: 'BuildingSpatial:Space',
    sourceElementId: '0xRA', floorId: 'F1', confidence: 'AUTHORITATIVE_BIM',
    geometryType: 'VOLUME', range: { low: { x: 0, y: 0, z: 0 }, high: { x: 10, y: 10, z: 4 } },
}
// Room B: a footprint square 20..30 x 0..10 over z 0..4 on floor F1.
const roomB: SpatialRoomReference = {
    roomId: 'RB', displayName: 'Control Room B', sourceClass: 'BuildingSpatial:Space',
    sourceElementId: '0xRB', floorId: 'F1', confidence: 'AUTHORITATIVE_BIM',
    geometryType: 'FOOTPRINT',
    footprint: { ring: [{ x: 20, y: 0 }, { x: 30, y: 0 }, { x: 30, y: 10 }, { x: 20, y: 10 }], zLow: 0, zHigh: 4 },
}
const semantics: SpatialModelSemantics = {
    floors: [floorL1, floorL2],
    rooms: [roomA, roomB],
    floorAvailability: 'AUTHORITATIVE_BIM',
    roomAvailability: 'AUTHORITATIVE_BIM',
}

// ---------------------------------------------------------------------------

describe('containment primitives (pure)', () => {
    it('pointInRange3 inclusive boundary', () => {
        const r = { low: { x: 0, y: 0, z: 0 }, high: { x: 10, y: 10, z: 4 } }
        expect(pointInRange3({ x: 5, y: 5, z: 2 }, r)).toBe(true)
        expect(pointInRange3({ x: 0, y: 0, z: 0 }, r)).toBe(true) // on low corner
        expect(pointInRange3({ x: 10, y: 10, z: 4 }, r)).toBe(true) // on high corner
        expect(pointInRange3({ x: 11, y: 5, z: 2 }, r)).toBe(false)
    })
    it('pointInFootprint inclusive edge + vertical extent', () => {
        const f = roomB.footprint!
        expect(pointInFootprint({ x: 25, y: 5, z: 2 }, f)).toBe(true)
        expect(pointInFootprint({ x: 20, y: 5, z: 2 }, f)).toBe(true) // on edge
        expect(pointInFootprint({ x: 25, y: 5, z: 9 }, f)).toBe(false) // above z extent
        expect(pointInFootprint({ x: 15, y: 5, z: 2 }, f)).toBe(false) // outside
    })
})

describe('floor association', () => {
    it('inside F1 range -> ASSIGNED F1 via STOREY_ELEVATION_RANGE', () => {
        const r = associateFloor({ x: 5, y: 5, z: 1 }, semantics)
        expect(r.status).toBe('ASSIGNED'); expect(r.floor?.floorId).toBe('F1'); expect(r.method).toBe('STOREY_ELEVATION_RANGE')
    })
    it('inside F2 range -> ASSIGNED F2', () => {
        const r = associateFloor({ x: 5, y: 5, z: 6 }, semantics)
        expect(r.status).toBe('ASSIGNED'); expect(r.floor?.floorId).toBe('F2')
    })
    it('boundary z=4 belongs to BOTH ranges -> AMBIGUOUS (inclusive policy, no arbitrary pick)', () => {
        const r = associateFloor({ x: 5, y: 5, z: 4 }, semantics)
        expect(r.status).toBe('AMBIGUOUS')
    })
    it('above all ranges but elevations exist -> DERIVED nearest elevation', () => {
        const r = associateFloor({ x: 5, y: 5, z: 100 }, semantics)
        expect(r.status).toBe('ASSIGNED'); expect(r.method).toBe('DERIVED_RANGE'); expect(r.floor?.floorId).toBe('F2')
    })
    it('no floor semantics -> NOT_AVAILABLE_FROM_BIM', () => {
        const r = associateFloor({ x: 5, y: 5, z: 1 }, EMPTY_MODEL_SEMANTICS)
        expect(r.status).toBe('NOT_AVAILABLE_FROM_BIM')
    })
    it('deterministic: same input -> same output', () => {
        const a = associateFloor({ x: 5, y: 5, z: 1 }, semantics)
        const b = associateFloor({ x: 5, y: 5, z: 1 }, semantics)
        expect(a).toEqual(b)
    })
})

describe('room association', () => {
    it('inside room A volume -> ASSIGNED RA via BIM_ROOM_VOLUME', () => {
        const r = associateRoom({ x: 5, y: 5, z: 2 }, semantics, 'F1')
        expect(r.status).toBe('ASSIGNED'); expect(r.room?.roomId).toBe('RA'); expect(r.method).toBe('BIM_ROOM_VOLUME')
    })
    it('inside room B footprint -> ASSIGNED RB via BIM_ROOM_FOOTPRINT', () => {
        const r = associateRoom({ x: 25, y: 5, z: 2 }, semantics, 'F1')
        expect(r.status).toBe('ASSIGNED'); expect(r.room?.roomId).toBe('RB'); expect(r.method).toBe('BIM_ROOM_FOOTPRINT')
    })
    it('point in no room -> NOT_FOUND_AT_POSITION', () => {
        const r = associateRoom({ x: 15, y: 5, z: 2 }, semantics, 'F1')
        expect(r.status).toBe('NOT_FOUND_AT_POSITION')
    })
    it('no room semantics -> NOT_AVAILABLE_FROM_BIM', () => {
        const r = associateRoom({ x: 5, y: 5, z: 2 }, EMPTY_MODEL_SEMANTICS)
        expect(r.status).toBe('NOT_AVAILABLE_FROM_BIM')
    })
    it('two overlapping rooms containing the point -> AMBIGUOUS (no arbitrary pick)', () => {
        const overlap: SpatialModelSemantics = {
            ...semantics,
            rooms: [
                roomA,
                { ...roomA, roomId: 'RA2', displayName: 'Overlapping A2', sourceElementId: '0xRA2' },
            ],
        }
        const r = associateRoom({ x: 5, y: 5, z: 2 }, overlap, 'F1')
        expect(r.status).toBe('AMBIGUOUS'); expect(r.room).toBeUndefined()
    })
})

describe('full association + validity + provenance', () => {
    it('assigned floor + room -> VALID_ASSOCIATED, BIM_DERIVED, source ids recorded', () => {
        const r = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 5, y: 5, z: 2 }, semantics })
        expect(r.floorStatus).toBe('ASSIGNED'); expect(r.roomStatus).toBe('ASSIGNED')
        expect(r.validity).toBe('VALID_ASSOCIATED')
        expect(r.provenance.source).toBe('BIM_DERIVED')
        expect(r.provenance.method).toBe('BIM_ROOM_VOLUME')
        expect(r.provenance.sourceElementIds).toEqual(['0xF1', '0xRA'])
        expect(r.provenance.boundaryInclusive).toBe(true)
        expect(r.provenance.testedPoint).toEqual({ x: 5, y: 5, z: 2 })
    })
    it('floor known, room not found -> ROOM stays honest, validity OUTSIDE_MODELED_ROOM', () => {
        const r = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 15, y: 5, z: 2 }, semantics })
        expect(r.floorStatus).toBe('ASSIGNED'); expect(r.roomStatus).toBe('NOT_FOUND_AT_POSITION')
        expect(r.validity).toBe('OUTSIDE_MODELED_ROOM')
    })
    it('status semantics distinct: NOT_AVAILABLE_FROM_BIM != NOT_FOUND_AT_POSITION', () => {
        const noBim = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 5, y: 5, z: 2 }, semantics: EMPTY_MODEL_SEMANTICS })
        expect(noBim.roomStatus).toBe('NOT_AVAILABLE_FROM_BIM')
        expect(noBim.floorStatus).toBe('NOT_AVAILABLE_FROM_BIM')
        const notFound = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 15, y: 5, z: 2 }, semantics })
        expect(notFound.roomStatus).toBe('NOT_FOUND_AT_POSITION')
        expect(noBim.roomStatus).not.toBe(notFound.roomStatus)
    })
    it('boundary policy is inclusive + deterministic', () => {
        const onEdge = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 0, y: 0, z: 0 }, semantics })
        // (0,0,0) is on room A low corner and floor F1 low boundary.
        expect(onEdge.roomStatus).toBe('ASSIGNED'); expect(onEdge.room?.roomId).toBe('RA')
        const again = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 0, y: 0, z: 0 }, semantics })
        expect(onEdge).toEqual(again)
    })
})

describe('association does not mutate the asset', () => {
    it('position + identity immutability', () => {
        const store = newStore()
        const inst = placeAt(store, 5, 5, 2)
        const before = JSON.parse(JSON.stringify(inst))
        const r = computeSpatialAssociation({ assetInstanceId: inst.assetInstanceId, position: { ...inst.transform.position }, semantics })
        expect(r.floorStatus).toBe('ASSIGNED')
        // The store instance is untouched by association.
        const after = store.getInstance(inst.assetInstanceId)!
        expect(after.transform.position).toEqual(before.transform.position)
        expect(after.assetInstanceId).toBe(before.assetInstanceId)
        expect(after.assetDefinitionId).toBe(before.assetDefinitionId)
        expect(after.geometryRepresentationId).toBe(before.geometryRepresentationId)
        expect(after.displayLabel).toBe(before.displayLabel)
        expect(after.dimensions).toEqual(before.dimensions)
        expect(after.transform.rotation).toEqual(before.transform.rotation)
        expect(after.installationState).toBe(before.installationState)
        expect(after.spatialSource).toBe(before.spatialSource)
        expect(after.scenario).toEqual(before.scenario)
    })
})

describe('store integration: reassociation lifecycle', () => {
    it('drag commit reassociates room A -> B; one committed position change; identity unchanged', () => {
        const store = newStore()
        const inst = placeAt(store, 5, 5, 2) // room A
        const a = computeSpatialAssociation({ assetInstanceId: inst.assetInstanceId, position: { ...store.getInstance(inst.assetInstanceId)!.transform.position }, semantics })
        expect(a.room?.roomId).toBe('RA')

        // Fluid drag to room B footprint (x=25). Z preserved.
        store.beginDrag(inst.assetInstanceId, { x: 5, y: 5, z: 2 })
        store.updateDragPreview({ x: 25, y: 5, z: 2 })
        // BEFORE release: authoritative position is still the start (room A).
        const midPos = store.getInstance(inst.assetInstanceId)!.transform.position
        expect(midPos.x).toBe(5)
        const midAssoc = computeSpatialAssociation({ assetInstanceId: inst.assetInstanceId, position: { ...midPos }, semantics })
        expect(midAssoc.room?.roomId).toBe('RA') // preview did NOT reassign

        const commit = store.commitDrag()
        expect(commit.ok).toBe(true)
        const b = computeSpatialAssociation({ assetInstanceId: inst.assetInstanceId, position: { ...store.getInstance(inst.assetInstanceId)!.transform.position }, semantics })
        expect(b.room?.roomId).toBe('RB')
        // Identity unchanged across the move.
        expect(store.getInstance(inst.assetInstanceId)!.assetDefinitionId).toBe(inst.assetDefinitionId)
    })

    it('rotation preserves floor + room association', () => {
        const store = newStore()
        const inst = placeAt(store, 5, 5, 2)
        const before = computeSpatialAssociation({ assetInstanceId: inst.assetInstanceId, position: { ...inst.transform.position }, semantics })
        store.beginRotate(inst.assetInstanceId)
        store.updateRotatePreview(137)
        store.commitRotate()
        const moved = store.getInstance(inst.assetInstanceId)!
        const after = computeSpatialAssociation({ assetInstanceId: inst.assetInstanceId, position: { ...moved.transform.position }, semantics })
        expect(after.floor?.floorId).toBe(before.floor?.floorId)
        expect(after.room?.roomId).toBe(before.room?.roomId)
        // Only yaw changed on the asset.
        expect(moved.transform.position).toEqual(inst.transform.position)
    })

    it('delete removes only the deleted instance association; other instance + BIM refs preserved', () => {
        const store = newStore()
        const a = placeAt(store, 5, 5, 2) // room A
        const b = placeAt(store, 6, 6, 2) // also room A
        const del = store.deleteAsset(a.assetInstanceId)
        expect(del.ok).toBe(true)
        expect(store.getInstance(a.assetInstanceId)).toBeUndefined()
        // B survives and still associates.
        const bInst = store.getInstance(b.assetInstanceId)!
        const bAssoc = computeSpatialAssociation({ assetInstanceId: b.assetInstanceId, position: { ...bInst.transform.position }, semantics })
        expect(bAssoc.room?.roomId).toBe('RA')
        // The BIM references themselves are untouched (still in the shared semantics).
        expect(semantics.rooms.find((r) => r.roomId === 'RA')).toBeDefined()
        expect(semantics.floors.find((f) => f.floorId === 'F1')).toBeDefined()
    })
})

describe('status <-> reference invariant + UI/inspector consistency', () => {
    // Semantics whose floors claim availability but carry NO usable range/elevation
    // (mirrors live SpatialComposition:CompositeElement with no placement geom).
    const floorsNoGeom: SpatialModelSemantics = {
        floors: [
            { floorId: 'C1', displayName: 'Composite 1', sourceClass: 'SpatialComposition:CompositeElement', sourceElementId: '0xC1', confidence: 'AUTHORITATIVE_BIM' },
            { floorId: 'C2', displayName: 'Composite 2', sourceClass: 'SpatialComposition:CompositeElement', sourceElementId: '0xC2', confidence: 'AUTHORITATIVE_BIM' },
        ],
        rooms: [roomA],
        // Availability accidentally left as AUTHORITATIVE_BIM (the defect the guard covers).
        floorAvailability: 'AUTHORITATIVE_BIM',
        roomAvailability: 'AUTHORITATIVE_BIM',
    }

    it('28/29 — ASSIGNED never coexists with a missing reference (invariant holds)', () => {
        const r = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 5, y: 5, z: 2 }, semantics: floorsNoGeom })
        expect(assignmentInvariantHolds(r)).toBe(true)
        // Floor cannot be ASSIGNED without a reference: with no range/elevation it
        // must be NOT_FOUND_AT_POSITION, floor undefined.
        expect(r.floorStatus).toBe('NOT_FOUND_AT_POSITION')
        expect(r.floor).toBeUndefined()
        // Room A does contain the point -> room ASSIGNED with a reference.
        expect(r.roomStatus).toBe('ASSIGNED')
        expect(r.room?.roomId).toBe('RA')
    })

    it('any well-formed result satisfies the invariant', () => {
        const cases = [
            computeSpatialAssociation({ assetInstanceId: 'A', position: { x: 5, y: 5, z: 2 }, semantics }),
            computeSpatialAssociation({ assetInstanceId: 'B', position: { x: 15, y: 5, z: 2 }, semantics }),
            computeSpatialAssociation({ assetInstanceId: 'C', position: { x: 5, y: 5, z: 100 }, semantics }),
            computeSpatialAssociation({ assetInstanceId: 'D', position: { x: 0, y: 0, z: 0 }, semantics: EMPTY_MODEL_SEMANTICS }),
        ]
        for (const r of cases) expect(assignmentInvariantHolds(r)).toBe(true)
    })

    it('30 — assigned floor displays identity (label + id), never the word ASSIGNED', () => {
        const r = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 5, y: 5, z: 1 }, semantics })
        expect(r.floorStatus).toBe('ASSIGNED')
        const label = formatAssociationSlotLabel(r, 'floor')
        expect(label).toBe('Level 1 (F1)')
        expect(label).not.toBe('ASSIGNED')
    })

    it('31 — room not found displays "Not found at position"', () => {
        const r = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 15, y: 5, z: 2 }, semantics })
        expect(formatAssociationSlotLabel(r, 'room')).toBe('Not found at position')
    })

    it('NOT_AVAILABLE_FROM_BIM displays distinctly from NOT_FOUND_AT_POSITION', () => {
        const noBim = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 5, y: 5, z: 2 }, semantics: EMPTY_MODEL_SEMANTICS })
        expect(formatAssociationSlotLabel(noBim, 'room')).toBe('Not available from BIM')
        const notFound = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 15, y: 5, z: 2 }, semantics })
        expect(formatAssociationSlotLabel(notFound, 'room')).toBe('Not found at position')
        expect(formatAssociationSlotLabel(noBim, 'room')).not.toBe(formatAssociationSlotLabel(notFound, 'room'))
    })

    it('32 — UI formatter and DEV inspector agree about floor/room identity from ONE result', () => {
        // Point on floor F1 (z=1) but outside every room (x=15) — mirrors the
        // live "floor assigned, room not found" case that surfaced the defect.
        const r = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 15, y: 5, z: 1 }, semantics })
        const uiFloor = formatAssociationSlotLabel(r, 'floor')
        const inspector = summarizeAssociation(r)
        // Floor ASSIGNED -> UI shows "Level 1 (F1)"; inspector exposes floorId=F1, floorLabel=Level 1.
        expect(r.floorStatus).toBe('ASSIGNED')
        expect(uiFloor).toBe('Level 1 (F1)')
        expect(inspector).toContain('floorId=F1')
        expect(inspector).toContain('floorLabel=Level 1')
        expect(inspector).toContain('floorStatus=ASSIGNED')
        // Neither surface renders a bare status word for the identity.
        expect(uiFloor).not.toBe('ASSIGNED')
        // Room NOT_FOUND at this point -> both surfaces agree.
        expect(r.roomStatus).toBe('NOT_FOUND_AT_POSITION')
        expect(formatAssociationSlotLabel(r, 'room')).toBe('Not found at position')
        expect(inspector).toContain('roomStatus=NOT_FOUND_AT_POSITION')
        expect(inspector).toContain('roomId=NONE')
    })
})

describe('finite-range validation + honest room-geometry semantics', () => {
    it('39 — finite range accepted (and normalized)', () => {
        const r = validateWorldRange({ low: { x: 10, y: 0, z: 0 }, high: { x: 0, y: 10, z: 4 } })
        expect(r).toBeDefined()
        // Endpoints normalized so low <= high per axis.
        expect(r!.low).toEqual({ x: 0, y: 0, z: 0 })
        expect(r!.high).toEqual({ x: 10, y: 10, z: 4 })
    })
    it('40 — NaN coordinate rejected', () => {
        expect(validateWorldRange({ low: { x: NaN, y: 0, z: 0 }, high: { x: 10, y: 10, z: 4 } })).toBeUndefined()
    })
    it('41 — Infinity coordinate rejected', () => {
        expect(validateWorldRange({ low: { x: 0, y: 0, z: 0 }, high: { x: Infinity, y: 10, z: 4 } })).toBeUndefined()
        expect(validateWorldRange({ low: { x: 0, y: -Infinity, z: 0 }, high: { x: 10, y: 10, z: 4 } })).toBeUndefined()
    })

    it('42 — 8 room metadata records, 0 usable geometry -> NOT_AVAILABLE_FROM_BIM (not NOT_FOUND)', () => {
        const metadataRooms: SpatialModelSemantics = {
            floors: [],
            rooms: Array.from({ length: 8 }, (_, i) => ({
                roomId: `S${i}`, displayName: `Space ${i}`, sourceClass: 'BuildingSpatial:Space',
                sourceElementId: `0xS${i}`, confidence: 'AUTHORITATIVE_BIM' as const, geometryType: 'METADATA_ONLY' as const,
            })),
            floorAvailability: 'NOT_AVAILABLE',
            roomAvailability: 'AUTHORITATIVE_BIM', // source is authoritative...
        }
        const r = associateRoom({ x: 5, y: 5, z: 2 }, metadataRooms)
        // ...but with no testable geometry the honest containment answer is NOT_AVAILABLE.
        expect(r.status).toBe('NOT_AVAILABLE_FROM_BIM')
    })

    it('42b — 8 rooms with usable ranges, point outside all -> NOT_FOUND_AT_POSITION', () => {
        const rangedRooms: SpatialModelSemantics = {
            floors: [],
            rooms: Array.from({ length: 8 }, (_, i) => ({
                roomId: `S${i}`, displayName: `Space ${i}`, sourceClass: 'BuildingSpatial:Space',
                sourceElementId: `0xS${i}`, confidence: 'AUTHORITATIVE_BIM' as const, geometryType: 'RANGE_ONLY' as const,
                range: { low: { x: i * 100, y: 0, z: 0 }, high: { x: i * 100 + 10, y: 10, z: 4 } },
            })),
            floorAvailability: 'NOT_AVAILABLE',
            roomAvailability: 'AUTHORITATIVE_BIM',
        }
        const r = associateRoom({ x: -999, y: -999, z: 2 }, rangedRooms)
        expect(r.status).toBe('NOT_FOUND_AT_POSITION')
    })

    it('43 — validity: no usable room geometry never yields OUTSIDE_MODELED_ROOM', () => {
        const metadataRooms: SpatialModelSemantics = {
            floors: [],
            rooms: [{ roomId: 'S0', displayName: 'Space 0', sourceClass: 'BuildingSpatial:Space', sourceElementId: '0xS0', confidence: 'AUTHORITATIVE_BIM', geometryType: 'METADATA_ONLY' }],
            floorAvailability: 'NOT_AVAILABLE',
            roomAvailability: 'AUTHORITATIVE_BIM',
        }
        const r = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 5, y: 5, z: 2 }, semantics: metadataRooms })
        expect(r.roomStatus).toBe('NOT_AVAILABLE_FROM_BIM')
        expect(r.validity).not.toBe('OUTSIDE_MODELED_ROOM')

        // With usable geometry + point outside -> OUTSIDE_MODELED_ROOM is allowed.
        const ranged: SpatialModelSemantics = {
            floors: [],
            rooms: [{ roomId: 'S0', displayName: 'Space 0', sourceClass: 'BuildingSpatial:Space', sourceElementId: '0xS0', confidence: 'AUTHORITATIVE_BIM', geometryType: 'RANGE_ONLY', range: { low: { x: 0, y: 0, z: 0 }, high: { x: 1, y: 1, z: 1 } } }],
            floorAvailability: 'NOT_AVAILABLE',
            roomAvailability: 'AUTHORITATIVE_BIM',
        }
        const r2 = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 50, y: 50, z: 2 }, semantics: ranged })
        expect(r2.roomStatus).toBe('NOT_FOUND_AT_POSITION')
        expect(r2.validity).toBe('OUTSIDE_MODELED_ROOM')
    })
})

describe('multi-room finite ranges + containment determinism (fixtures)', () => {
    // Fixture data shaped like the observed live 8-space inventory (NOT product
    // data): finite ranges, one room per region. Mirrors what INSPECT BIM
    // SPATIAL STRUCTURE reported (Radiopharmacy, Cyclotron Room, Scanner Room…).
    const eightSpaces: SpatialModelSemantics = {
        floors: [],
        rooms: [
            { roomId: 'R-CORR1', displayName: 'Floor 1 Main Corridor', sourceClass: 'BuildingSpatial:Space', sourceElementId: '0x1', confidence: 'AUTHORITATIVE_BIM', geometryType: 'RANGE_ONLY', range: { low: { x: 12, y: 7, z: 0 }, high: { x: 18, y: 13, z: 3 } } },
            { roomId: 'R-RADIO', displayName: 'Radiopharmacy', sourceClass: 'BuildingSpatial:Space', sourceElementId: '0x2', confidence: 'AUTHORITATIVE_BIM', geometryType: 'RANGE_ONLY', range: { low: { x: 2, y: 12, z: 0 }, high: { x: 8, y: 18, z: 3 } } },
            { roomId: 'R-CYCLO', displayName: 'Cyclotron Room', sourceClass: 'BuildingSpatial:Space', sourceElementId: '0x3', confidence: 'AUTHORITATIVE_BIM', geometryType: 'RANGE_ONLY', range: { low: { x: 9, y: 12, z: 0 }, high: { x: 15, y: 18, z: 3 } } },
            { roomId: 'R-VCORE', displayName: 'Vertical Circulation Core', sourceClass: 'BuildingSpatial:Space', sourceElementId: '0x4', confidence: 'AUTHORITATIVE_BIM', geometryType: 'RANGE_ONLY', range: { low: { x: 0, y: 0, z: 0 }, high: { x: 4, y: 4, z: 6 } } },
            { roomId: 'R-PATIENT', displayName: 'Patient Room', sourceClass: 'BuildingSpatial:Space', sourceElementId: '0x5', confidence: 'AUTHORITATIVE_BIM', geometryType: 'RANGE_ONLY', range: { low: { x: 20, y: 0, z: 0 }, high: { x: 26, y: 6, z: 3 } } },
            { roomId: 'R-INJECT', displayName: 'Injection/Uptake Room', sourceClass: 'BuildingSpatial:Space', sourceElementId: '0x6', confidence: 'AUTHORITATIVE_BIM', geometryType: 'RANGE_ONLY', range: { low: { x: 20, y: 8, z: 0 }, high: { x: 26, y: 14, z: 3 } } },
            { roomId: 'R-SCANNER', displayName: 'Scanner Room', sourceClass: 'BuildingSpatial:Space', sourceElementId: '0x7', confidence: 'AUTHORITATIVE_BIM', geometryType: 'RANGE_ONLY', range: { low: { x: 20, y: 16, z: 0 }, high: { x: 28, y: 24, z: 3 } } },
            { roomId: 'R-CORR2', displayName: 'Floor 2 Main Corridor', sourceClass: 'BuildingSpatial:Space', sourceElementId: '0x8', confidence: 'AUTHORITATIVE_BIM', geometryType: 'RANGE_ONLY', range: { low: { x: 12, y: 7, z: 3 }, high: { x: 18, y: 13, z: 6 } } },
        ],
        floorAvailability: 'NOT_AVAILABLE',
        roomAvailability: 'AUTHORITATIVE_BIM',
    }

    it('MULTI_ROOM_FINITE_RANGE_VALIDATION — all 8 ranges finite + ordered', () => {
        for (const r of eightSpaces.rooms) {
            const v = validateWorldRange(r.range!)
            expect(v).toBeDefined()
            expect(Object.values(v!.low).every(Number.isFinite)).toBe(true)
            expect(Object.values(v!.high).every(Number.isFinite)).toBe(true)
            expect(v!.low.x).toBeLessThanOrEqual(v!.high.x)
            expect(v!.low.y).toBeLessThanOrEqual(v!.high.y)
            expect(v!.low.z).toBeLessThanOrEqual(v!.high.z)
        }
    })

    it('ROOM_POINT_CONTAINMENT_DETERMINISTIC — 0 / 1 / multiple resolve deterministically', () => {
        // 1 match: inside Scanner Room only.
        const one = associateRoom({ x: 24, y: 20, z: 1 }, eightSpaces)
        expect(one.status).toBe('ASSIGNED'); expect(one.room?.roomId).toBe('R-SCANNER')
        // 0 matches: outside all.
        const zero = associateRoom({ x: -50, y: -50, z: 1 }, eightSpaces)
        expect(zero.status).toBe('NOT_FOUND_AT_POSITION')
        // multiple matches: add an overlapping room over Scanner Room -> AMBIGUOUS.
        const overlap: SpatialModelSemantics = {
            ...eightSpaces,
            rooms: [...eightSpaces.rooms, { roomId: 'R-DUP', displayName: 'Overlap', sourceClass: 'BuildingSpatial:Space', sourceElementId: '0x9', confidence: 'AUTHORITATIVE_BIM', geometryType: 'RANGE_ONLY', range: { low: { x: 20, y: 16, z: 0 }, high: { x: 28, y: 24, z: 3 } } }],
        }
        const many = associateRoom({ x: 24, y: 20, z: 1 }, overlap)
        expect(many.status).toBe('AMBIGUOUS'); expect(many.room).toBeUndefined()
        // Determinism: repeat yields identical results.
        expect(associateRoom({ x: 24, y: 20, z: 1 }, eightSpaces)).toEqual(one)
    })

    it('containment never mutates the tested position', () => {
        const pos = { x: 24, y: 20, z: 1 }
        const before = { ...pos }
        associateRoom(pos, eightSpaces)
        computeSpatialAssociation({ assetInstanceId: 'X', position: pos, semantics: eightSpaces })
        expect(pos).toEqual(before)
    })
})

describe('Bentley-free domain', () => {
    it('all association logic runs with plain objects (no @itwin import needed)', () => {
        // If this test file imported @itwin it would fail to run in the jsdom/node
        // vitest environment used here. The mere fact that computeSpatialAssociation
        // executes proves the domain is Bentley-independent.
        const r = computeSpatialAssociation({ assetInstanceId: 'X', position: { x: 5, y: 5, z: 2 }, semantics })
        expect(r).toBeTruthy()
    })
})

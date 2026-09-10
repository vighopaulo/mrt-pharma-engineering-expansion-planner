/**
 * Offline tests for the DERIVED BIM-BACKED PLANNING CONTEXT (Correction 2).
 * Pure, Bentley-free: classification, room-footprint derivation, planning
 * elevation, multi-level visibility, empty-project + placement context, and
 * engineering immutability. No Bentley runtime.
 */
import { describe, expect, it } from 'vitest'
import {
    classifyBimModel,
    deriveRoomFootprint,
    resolveRoomStoreyId,
    deriveRoomPlan,
    resolveNormalModePrimaryContext,
    resolveNormalRoomRepresentation,
    resolvePlanningElevation,
    roomFootprintVisibleAtElevation,
    visibleFootprintsAtElevation,
    type BimGeometryInventory,
    type PlanFootprint,
} from '../components/spatial/planningPlan'
import type { SpatialRoomReference, WorldRange3 } from '../domain/assets/spatialSemantics'

const range = (lx: number, ly: number, lz: number, hx: number, hy: number, hz: number): WorldRange3 => ({
    low: { x: lx, y: ly, z: lz },
    high: { x: hx, y: hy, z: hz },
})
const room = (roomId: string, displayName: string, r?: WorldRange3): Pick<SpatialRoomReference, 'roomId' | 'displayName'> & { range?: WorldRange3 } =>
    ({ roomId, displayName, range: r })

describe('BIM visual classification', () => {
    it('classifies the actual connected model (walls=0, floors=0, doors=0, spaces=8) as spatial-semantic with limited architecture', () => {
        const inv: BimGeometryInventory = { wallCount: 0, slabOrFloorCount: 0, doorCount: 0, otherGeometricCount: 3, spaceCount: 8 }
        expect(classifyBimModel(inv)).toBe('SPATIAL_SEMANTIC_MODEL_WITH_LIMITED_ARCHITECTURE')
    })
    it('classifies rich walls+slabs as detailed architectural BIM', () => {
        expect(classifyBimModel({ wallCount: 40, slabOrFloorCount: 3, doorCount: 12, otherGeometricCount: 0, spaceCount: 8 })).toBe('DETAILED_ARCHITECTURAL_BIM')
    })
    it('classifies some-but-sparse architecture as partial', () => {
        expect(classifyBimModel({ wallCount: 2, slabOrFloorCount: 0, doorCount: 0, otherGeometricCount: 0, spaceCount: 8 })).toBe('PARTIAL_ARCHITECTURAL_BIM')
    })
    it('classifies an empty inventory as OTHER', () => {
        expect(classifyBimModel({ wallCount: 0, slabOrFloorCount: 0, doorCount: 0, otherGeometricCount: 0, spaceCount: 0 })).toBe('OTHER')
    })
    it('maps classification to the normal-mode primary context', () => {
        expect(resolveNormalModePrimaryContext('SPATIAL_SEMANTIC_MODEL_WITH_LIMITED_ARCHITECTURE')).toBe('DERIVED_BIM_SPATIAL_PLAN')
        expect(resolveNormalModePrimaryContext('DETAILED_ARCHITECTURAL_BIM')).toBe('ARCHITECTURAL_BIM_GEOMETRY')
        expect(resolveNormalModePrimaryContext('PARTIAL_ARCHITECTURAL_BIM')).toBe('ARCHITECTURAL_BIM_GEOMETRY')
    })
})

describe('normal vs developer room representation policy', () => {
    it('normal mode uses a plan footprint, not a full volume, never hidden-without-replacement', () => {
        expect(resolveNormalRoomRepresentation('NORMAL_PLANNING')).toBe('PLAN_FOOTPRINT')
    })
    it('developer mode retains the full volume / range diagnostic', () => {
        expect(resolveNormalRoomRepresentation('DEVELOPER')).toBe('FULL_VOLUME')
    })
})

describe('room footprint derivation', () => {
    it('derives the exact CCW footprint at the deterministic planning elevation', () => {
        const fp = deriveRoomFootprint(room('0x20', 'Scanner Room', range(2, 12, 0, 8, 18, 3)))
        expect(fp).toBeDefined()
        expect(fp!.ring).toEqual([
            { x: 2, y: 12 },
            { x: 8, y: 12 },
            { x: 8, y: 18 },
            { x: 2, y: 18 },
        ])
        expect(fp!.elevation).toBe(0) // range low.z
        expect(fp!.zLow).toBe(0)
        expect(fp!.zHigh).toBe(3)
        expect(fp!.provenance).toBe('BIM_DERIVED')
    })
    it('references the SAME room identity, never a manufactured second identity', () => {
        const fp = deriveRoomFootprint(room('0xABC', 'Radiopharmacy', range(0, 0, 0, 4, 4, 3)))
        expect(fp!.roomId).toBe('0xABC')
        expect(fp!.label).toBe('Radiopharmacy')
    })
    it('rejects non-finite ranges (NaN/Infinity) — no fabricated geometry', () => {
        expect(deriveRoomFootprint(room('a', 'Bad NaN', range(NaN, 0, 0, 4, 4, 3)))).toBeUndefined()
        expect(deriveRoomFootprint(room('b', 'Bad Inf', range(0, 0, 0, Infinity, 4, 3)))).toBeUndefined()
    })
    it('rejects a missing range (metadata-only room)', () => {
        expect(deriveRoomFootprint(room('c', 'No range', undefined))).toBeUndefined()
    })
    it('rejects a degenerate (zero-area) footprint', () => {
        expect(deriveRoomFootprint(room('d', 'Flat', range(2, 5, 0, 2, 9, 3)))).toBeUndefined()
    })
    it('deriveRoomPlan skips unusable rooms and keeps deterministic order', () => {
        const plan = deriveRoomPlan([
            room('r1', 'Corridor', range(0, 0, 0, 10, 2, 3)),
            room('r2', 'Metadata only', undefined),
            room('r3', 'Cyclotron', range(0, 3, 0, 5, 8, 3)),
        ])
        expect(plan.map((f) => f.roomId)).toEqual(['r1', 'r3'])
    })
})

describe('planning elevation policy', () => {
    const fps: PlanFootprint[] = [
        { roomId: 'a', label: 'F1', ring: [], elevation: 0, zLow: 0, zHigh: 3, provenance: 'BIM_DERIVED' },
        { roomId: 'b', label: 'F2', ring: [], elevation: 4, zLow: 4, zHigh: 7, provenance: 'BIM_DERIVED' },
    ]
    it('prefers a selected asset Z when present', () => {
        expect(resolvePlanningElevation({ selectedAssetZ: 5, footprints: fps })).toEqual({ elevation: 5, provenance: 'SELECTED_ASSET_Z' })
    })
    it('falls back to the lowest room range low.z (ground planning level)', () => {
        expect(resolvePlanningElevation({ footprints: fps })).toEqual({ elevation: 0, provenance: 'LOWEST_ROOM_RANGE_LOW_Z' })
    })
    it('defaults to zero with no footprints and no selection', () => {
        expect(resolvePlanningElevation({ footprints: [] })).toEqual({ elevation: 0, provenance: 'DEFAULT_ZERO' })
    })
})

describe('multi-level visibility policy', () => {
    const f1: PlanFootprint = { roomId: 'a', label: 'F1', ring: [], elevation: 0, zLow: 0, zHigh: 3, provenance: 'BIM_DERIVED' }
    const f2: PlanFootprint = { roomId: 'b', label: 'F2', ring: [], elevation: 4, zLow: 4, zHigh: 7, provenance: 'BIM_DERIVED' }
    it('shows only the footprints whose vertical range contains the active elevation', () => {
        expect(roomFootprintVisibleAtElevation(f1, 1)).toBe(true)
        expect(roomFootprintVisibleAtElevation(f2, 1)).toBe(false)
        expect(visibleFootprintsAtElevation([f1, f2], 5).map((f) => f.roomId)).toEqual(['b'])
    })
    it('does not silently overlay all levels', () => {
        const visible = visibleFootprintsAtElevation([f1, f2], 0)
        expect(visible.map((f) => f.roomId)).toEqual(['a'])
    })
})

describe('empty-project + placement context', () => {
    it('a BIM-backed planning context is available with zero placed assets', () => {
        const plan = deriveRoomPlan([room('r1', 'Corridor', range(0, 0, 0, 10, 2, 3))])
        const { elevation } = resolvePlanningElevation({ footprints: plan }) // no selectedAssetZ
        expect(plan.length).toBe(1)
        expect(visibleFootprintsAtElevation(plan, elevation).length).toBe(1)
    })
})

describe('room plan engineering immutability', () => {
    it('derivation is a pure read: it never mutates the source room objects', () => {
        const src = room('r1', 'Scanner Room', range(2, 12, 0, 8, 18, 3))
        const before = JSON.parse(JSON.stringify(src))
        deriveRoomFootprint(src)
        deriveRoomPlan([src])
        expect(JSON.parse(JSON.stringify(src))).toEqual(before)
    })
})

describe('resolveRoomStoreyId (Z-binning)', () => {
    const storeys = [
        { id: 'f1', label: 'First Floor', zLow: 0, zHigh: 4 },
        { id: 'f2', label: 'Second Floor', zLow: 4, zHigh: 8 },
    ]
    it('bins a room into the storey containing its mid Z', () => {
        expect(resolveRoomStoreyId({ zLow: 0.5, zHigh: 3 }, storeys)).toBe('f1')
        expect(resolveRoomStoreyId({ zLow: 4.5, zHigh: 7 }, storeys)).toBe('f2')
    })
    it('falls back to the nearest storey when none contain the mid Z', () => {
        expect(resolveRoomStoreyId({ zLow: 20, zHigh: 22 }, storeys)).toBe('f2')
        expect(resolveRoomStoreyId({ zLow: -10, zHigh: -8 }, storeys)).toBe('f1')
    })
    it('returns undefined when there are no storeys', () => {
        expect(resolveRoomStoreyId({ zLow: 0, zHigh: 3 }, [])).toBeUndefined()
    })
})

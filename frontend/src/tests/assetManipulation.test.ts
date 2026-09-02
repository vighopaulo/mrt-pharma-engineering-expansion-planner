/**
 * Offline unit tests for controlled asset manipulation (SELECT -> MOVE -> ROTATE).
 * Pure domain + store invariants; no Bentley runtime. Governing doctrine:
 * SPATIAL TRANSFORM MAY CHANGE, ENGINEERING IDENTITY MUST NOT.
 */
import { describe, expect, it } from 'vitest'
import {
    buildPlacementIntent,
    CATALOG_TEST_ASSET_DEFINITION_ID,
    GE_DISCOVERY_MI_RECORD,
    GENERIC_PET_CT_GEOMETRY_ID,
    normalizeYawDegrees,
    rotateAssetYawBy,
    SpatialAssetStore,
    TEST_PROJECT_ID,
    type AssetInstance,
    type ScenarioProvenance,
} from '../domain/assets'
import { buildScannerParts } from '../components/spatial/scannerGeometry'

const DEV_SCENARIO: ScenarioProvenance = { scenarioId: 'MRT_DEV_SCENARIO', scenarioState: 'DRAFT' }

function newStore(): SpatialAssetStore {
    return new SpatialAssetStore({ projectId: TEST_PROJECT_ID, scenario: DEV_SCENARIO })
}

/** Place one GE Discovery MI at the given point and return its id. */
function placeOne(store: SpatialAssetStore, x: number, y: number, z: number): AssetInstance {
    const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
    if (!res.ok) throw new Error(res.reason)
    store.beginPlacement(res.intent)
    const r = store.completePlacementAt({ x, y, z })
    if (!r.ok) throw new Error(r.reason)
    return r.instance
}

function identitySnapshot(i: AssetInstance) {
    return {
        assetInstanceId: i.assetInstanceId,
        assetDefinitionId: i.assetDefinitionId,
        geometryRepresentationId: i.geometryRepresentationId,
        displayLabel: i.displayLabel,
        projectId: i.projectId,
        createdFrom: i.createdFrom,
        roomAssignment: i.roomAssignment.state,
        installationState: i.installationState,
        spatialSource: i.spatialSource,
        scenarioId: i.scenario?.scenarioId,
        dimProvenance: i.dimensions.provenance,
    }
}

// --- 47. MOVE / ROTATE event + identity immutability ---
describe('MOVE preserves identity, changes only position', () => {
    it('A/B — move changes only position; all identity/provenance preserved; rotation kept', () => {
        const store = newStore()
        const placed = placeOne(store, 1, 2, 3)
        const before = identitySnapshot(placed)
        const beforeRot = { ...placed.transform.rotation }

        store.beginMove(placed.assetInstanceId)
        const r = store.completeMoveAt({ x: 9, y: 8, z: 7 })
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.instance.transform.position).toEqual({ x: 9, y: 8, z: 7 })
        expect(r.instance.transform.rotation).toEqual(beforeRot)
        expect(identitySnapshot(r.instance)).toEqual(before)
    })

    it('C/D — move emits ASSET_MOVED with previous + new position', () => {
        const store = newStore()
        const placed = placeOne(store, 1, 1, 1)
        store.beginMove(placed.assetInstanceId)
        const r = store.completeMoveAt({ x: 5, y: 6, z: 7 })
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.event.type).toBe('ASSET_MOVED')
        expect(r.event.detail?.prevX).toBe(1)
        expect(r.event.detail?.newX).toBe(5)
        expect(r.event.detail?.newY).toBe(6)
        expect(r.event.detail?.newZ).toBe(7)
    })

    it('move does not change instance count', () => {
        const store = newStore()
        const placed = placeOne(store, 0, 0, 0)
        const before = store.count
        store.beginMove(placed.assetInstanceId)
        store.completeMoveAt({ x: 3, y: 3, z: 3 })
        expect(store.count).toBe(before)
    })
})

describe('ROTATE preserves identity, changes only rotation', () => {
    it('E/F — rotate changes only yaw; identity + position preserved', () => {
        const store = newStore()
        const placed = placeOne(store, 4, 5, 6)
        const before = identitySnapshot(placed)
        const beforePos = { ...placed.transform.position }

        const r = store.rotateAssetYaw(placed.assetInstanceId, 90)
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.instance.transform.rotation.yaw).toBe(90)
        expect(r.instance.transform.rotation.pitch).toBe(0)
        expect(r.instance.transform.rotation.roll).toBe(0)
        expect(r.instance.transform.position).toEqual(beforePos)
        expect(identitySnapshot(r.instance)).toEqual(before)
    })

    it('G/H — rotate emits ASSET_ROTATED with previous + new rotation', () => {
        const store = newStore()
        const placed = placeOne(store, 0, 0, 0)
        const r = store.rotateAssetYaw(placed.assetInstanceId, 90)
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.event.type).toBe('ASSET_ROTATED')
        expect(r.event.detail?.prevYaw).toBe(0)
        expect(r.event.detail?.newYaw).toBe(90)
    })
})

describe('composition: move-after-rotate and rotate-after-move', () => {
    it('I — move preserves an existing rotation (yaw stays 90 after move)', () => {
        const store = newStore()
        const placed = placeOne(store, 1, 1, 0)
        store.rotateAssetYaw(placed.assetInstanceId, 90)
        store.beginMove(placed.assetInstanceId)
        const r = store.completeMoveAt({ x: 20, y: 20, z: 0 })
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.instance.transform.rotation.yaw).toBe(90)
        expect(r.instance.transform.position).toEqual({ x: 20, y: 20, z: 0 })
    })

    it('J — rotate preserves a moved position', () => {
        const store = newStore()
        const placed = placeOne(store, 1, 1, 0)
        store.beginMove(placed.assetInstanceId)
        store.completeMoveAt({ x: 15, y: 16, z: 2 })
        const r = store.rotateAssetYaw(placed.assetInstanceId, 90)
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.instance.transform.position).toEqual({ x: 15, y: 16, z: 2 })
        expect(r.instance.transform.rotation.yaw).toBe(90)
    })
})

// --- 48. Interaction invariants ---
describe('interaction invariants', () => {
    it('A — move intent binds to one assetInstanceId', () => {
        const store = newStore()
        const a = placeOne(store, 1, 0, 0)
        placeOne(store, 2, 0, 0)
        const began = store.beginMove(a.assetInstanceId)
        expect(began.ok).toBe(true)
        if (began.ok) expect(began.intent.assetInstanceId).toBe(a.assetInstanceId)
    })

    it('B — one accepted move point creates one move transition; second click does nothing', () => {
        const store = newStore()
        const a = placeOne(store, 1, 0, 0)
        store.beginMove(a.assetInstanceId)
        const first = store.completeMoveAt({ x: 9, y: 0, z: 0 })
        expect(first.ok).toBe(true)
        const second = store.completeMoveAt({ x: 50, y: 0, z: 0 })
        expect(second.ok).toBe(false)
        if (!second.ok) expect(second.reason).toBe('MOVE_INTENT_INVALID')
        expect(store.getInstance(a.assetInstanceId)?.transform.position).toEqual({ x: 9, y: 0, z: 0 })
    })

    it('C — cancelling MOVE leaves transform unchanged', () => {
        const store = newStore()
        const a = placeOne(store, 3, 3, 3)
        store.beginMove(a.assetInstanceId)
        store.cancelMove()
        expect(store.isMoveModeActive()).toBe(false)
        expect(store.getInstance(a.assetInstanceId)?.transform.position).toEqual({ x: 3, y: 3, z: 3 })
    })

    it('D — changing UI selection during active MOVE does not retarget the move', () => {
        const store = newStore()
        const a = placeOne(store, 1, 0, 0)
        const b = placeOne(store, 2, 0, 0)
        store.beginMove(a.assetInstanceId)
        store.selectAsset(b.assetInstanceId) // UI selection changes mid-move
        const r = store.completeMoveAt({ x: 9, y: 9, z: 9 })
        expect(r.ok).toBe(true)
        // a moved; b untouched.
        expect(store.getInstance(a.assetInstanceId)?.transform.position).toEqual({ x: 9, y: 9, z: 9 })
        expect(store.getInstance(b.assetInstanceId)?.transform.position).toEqual({ x: 2, y: 0, z: 0 })
    })

    it('E — MOVE cannot start while placement mode is active', () => {
        const store = newStore()
        const a = placeOne(store, 1, 0, 0)
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res.ok) store.beginPlacement(res.intent)
        const began = store.beginMove(a.assetInstanceId)
        expect(began.ok).toBe(false)
        if (!began.ok) expect(began.reason).toBe('SPATIAL_INTERACTION_ALREADY_ACTIVE')
    })

    it('F — placement cannot start while MOVE mode is active', () => {
        const store = newStore()
        const a = placeOne(store, 1, 0, 0)
        store.beginMove(a.assetInstanceId)
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        expect(res.ok).toBe(true)
        if (!res.ok) return
        const began = store.beginPlacement(res.intent)
        expect(began.ok).toBe(false)
        if (!began.ok) expect(began.reason).toBe('SPATIAL_INTERACTION_ALREADY_ACTIVE')
    })

    it('G — rotation is rejected while MOVE is active', () => {
        const store = newStore()
        const a = placeOne(store, 1, 0, 0)
        store.beginMove(a.assetInstanceId)
        const r = store.rotateAssetYaw(a.assetInstanceId, 90)
        expect(r.ok).toBe(false)
        if (!r.ok) expect(r.reason).toBe('SPATIAL_INTERACTION_ALREADY_ACTIVE')
    })

    it('H/I — MOVE mode exits after success and after cancellation', () => {
        const store = newStore()
        const a = placeOne(store, 1, 0, 0)
        store.beginMove(a.assetInstanceId)
        store.completeMoveAt({ x: 2, y: 2, z: 2 })
        expect(store.isMoveModeActive()).toBe(false)
        store.beginMove(a.assetInstanceId)
        store.cancelMove()
        expect(store.isMoveModeActive()).toBe(false)
    })

    it('J — repeated subscription (StrictMode-style) does not duplicate a move', () => {
        const store = newStore()
        const a = placeOne(store, 1, 0, 0)
        const unsub1 = store.subscribe(() => { })
        const unsub2 = store.subscribe(() => { })
        store.beginMove(a.assetInstanceId)
        const r = store.completeMoveAt({ x: 4, y: 4, z: 4 })
        expect(r.ok).toBe(true)
        unsub1(); unsub2()
        expect(store.count).toBe(1)
        expect(store.getInstance(a.assetInstanceId)?.transform.position).toEqual({ x: 4, y: 4, z: 4 })
    })
})

// --- 49. Rotation normalization ---
describe('rotation normalization', () => {
    it('normalizeYawDegrees folds into [0, 360)', () => {
        expect(normalizeYawDegrees(0)).toBe(0)
        expect(normalizeYawDegrees(90)).toBe(90)
        expect(normalizeYawDegrees(360)).toBe(0)
        expect(normalizeYawDegrees(450)).toBe(90)
        expect(normalizeYawDegrees(-90)).toBe(270)
        expect(normalizeYawDegrees(-810)).toBe(270)
    })

    it('sequential +90 rotations: 0 -> 90 -> 180 -> 270 -> 0', () => {
        const store = newStore()
        const a = placeOne(store, 0, 0, 0)
        const yaws: number[] = []
        for (let i = 0; i < 4; i++) {
            const r = store.rotateAssetYaw(a.assetInstanceId, 90)
            if (r.ok) yaws.push(r.instance.transform.rotation.yaw)
        }
        expect(yaws).toEqual([90, 180, 270, 0])
    })

    it('-90 from 0 normalizes to 270', () => {
        const store = newStore()
        const a = placeOne(store, 0, 0, 0)
        const r = store.rotateAssetYaw(a.assetInstanceId, -90)
        expect(r.ok).toBe(true)
        if (r.ok) expect(r.instance.transform.rotation.yaw).toBe(270)
    })

    it('rotateAssetYawBy never changes pitch/roll', () => {
        const store = newStore()
        const a = placeOne(store, 0, 0, 0)
        const cmd = rotateAssetYawBy(a, 90)
        expect(cmd.ok).toBe(true)
        if (cmd.ok) {
            expect(cmd.instance.transform.rotation.pitch).toBe(0)
            expect(cmd.instance.transform.rotation.roll).toBe(0)
        }
    })
})

// --- 50. Rendering test seam: rotation actually changes world geometry ---
describe('rotation is applied to world geometry (pure seam)', () => {
    it('same scanner local geometry at yaw 0 vs 90 produces different world coordinates', () => {
        const store = newStore()
        const a = placeOne(store, 10, 10, 0)
        const partsYaw0 = buildScannerParts(a)
        const rotated = { ...a, transform: { ...a.transform, rotation: { yaw: 90, pitch: 0, roll: 0 } } }
        const partsYaw90 = buildScannerParts(rotated)

        // Gantry box corners differ once yawed.
        const g0 = partsYaw0.find((p) => p.part === 'GANTRY')!
        const g90 = partsYaw90.find((p) => p.part === 'GANTRY')!
        // The bounding low/high are pre-rotation in the WorldBox; the decorator
        // rotates corners. Prove the bore cylinder endpoints (already rotated in
        // buildScannerParts) differ.
        const b0 = partsYaw0.find((p) => p.part === 'BORE')! as { centerA: number[]; centerB: number[] }
        const b90 = partsYaw90.find((p) => p.part === 'BORE')! as { centerA: number[]; centerB: number[] }
        expect(b0.centerA).not.toEqual(b90.centerA)
        // Same geometry identity is used for both (no per-instance geometry object).
        expect(a.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
        expect(rotated.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
        // The box yawRadians differs (0 vs pi/2) so the decorator will rotate it.
        expect((g0 as { yawRadians: number }).yawRadians).toBe(0)
        expect((g90 as { yawRadians: number }).yawRadians).toBeCloseTo(Math.PI / 2)
    })
})

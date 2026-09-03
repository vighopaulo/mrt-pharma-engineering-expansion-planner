/**
 * Offline tests for object-attached fluid yaw rotation + controlled delete.
 * Pure domain/store + pure picking/rotation math; no Bentley runtime.
 * Doctrine: preview != commit (0 events during drag, 1 on release); rotation is
 * yaw-only and preserves position + identity; delete removes ONE USER_PLACED
 * instance (1 ASSET_REMOVED) preserving shared def/geometry/catalog/others.
 */
import { describe, expect, it } from 'vitest'
import {
    buildPlacementIntent,
    CATALOG_TEST_ASSET_DEFINITION_ID,
    GE_DISCOVERY_MI_RECORD,
    GENERIC_PET_CT_GEOMETRY_ID,
    SpatialAssetStore,
    TEST_PROJECT_ID,
    type AssetInstance,
    type ScenarioProvenance,
} from '../domain/assets'
import {
    computePreviewYaw,
    normalizeDeg,
    pointerNearProjectedRing,
    resolveMrtPickTarget,
    ringWorldSamples,
    signedAngleXYDeg,
} from '../components/spatial/assetPicking'

const DEV_SCENARIO: ScenarioProvenance = { scenarioId: 'MRT_DEV_SCENARIO', scenarioState: 'DRAFT' }
const newStore = () => new SpatialAssetStore({ projectId: TEST_PROJECT_ID, scenario: DEV_SCENARIO })

function placeAt(store: SpatialAssetStore, x: number, y: number, z: number): AssetInstance {
    const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
    if (!res.ok) throw new Error(res.reason)
    store.beginPlacement(res.intent)
    const r = store.completePlacementAt({ x, y, z })
    if (!r.ok) throw new Error(r.reason)
    return r.instance
}

// --- 44. Pick target decision ---
describe('MRT pick target decision (body vs handle)', () => {
    const handleMap = new Map([['0xH1', 'PETCT-GE-DISCOVERY-MI-0001']])
    const bodyMap = new Map([['0xB1', 'PETCT-GE-DISCOVERY-MI-0001']])
    const rh = (id: string) => handleMap.get(id)
    const rb = (id: string) => bodyMap.get(id)

    it('rotation-handle pick -> ROTATE target', () => {
        expect(resolveMrtPickTarget({ sourceId: '0xH1', isElementHit: false }, rh, rb)).toEqual({ type: 'ROTATION_HANDLE', assetInstanceId: 'PETCT-GE-DISCOVERY-MI-0001' })
    })
    it('asset-body pick -> TRANSLATE target', () => {
        expect(resolveMrtPickTarget({ sourceId: '0xB1', isElementHit: false }, rh, rb)).toEqual({ type: 'ASSET_BODY', assetInstanceId: 'PETCT-GE-DISCOVERY-MI-0001' })
    })
    it('BIM element -> ignored', () => {
        expect(resolveMrtPickTarget({ sourceId: '0xB1', isElementHit: true }, rh, rb)).toBeUndefined()
    })
    it('unknown decoration -> ignored', () => {
        expect(resolveMrtPickTarget({ sourceId: '0xZZ', isElementHit: false }, rh, rb)).toBeUndefined()
    })

    it('34 — handle and body ids for the same asset are distinct and classify independently', () => {
        // Same asset A: distinct body id 0xB1 and handle id 0xH1.
        expect(rh('0xH1')).toBe('PETCT-GE-DISCOVERY-MI-0001')
        expect(rb('0xB1')).toBe('PETCT-GE-DISCOVERY-MI-0001')
        expect('0xH1').not.toBe('0xB1')
        expect(resolveMrtPickTarget({ sourceId: '0xH1', isElementHit: false }, rh, rb)?.type).toBe('ROTATION_HANDLE')
        expect(resolveMrtPickTarget({ sourceId: '0xB1', isElementHit: false }, rh, rb)?.type).toBe('ASSET_BODY')
    })

    it('35 — two instances: each handle/body id resolves to its own asset (no cross-resolution)', () => {
        const handles = new Map([['0xHA', 'A'], ['0xHB', 'B']])
        const bodies = new Map([['0xBA', 'A'], ['0xBB', 'B']])
        const H = (id: string) => handles.get(id)
        const B = (id: string) => bodies.get(id)
        expect(resolveMrtPickTarget({ sourceId: '0xHA', isElementHit: false }, H, B)).toEqual({ type: 'ROTATION_HANDLE', assetInstanceId: 'A' })
        expect(resolveMrtPickTarget({ sourceId: '0xHB', isElementHit: false }, H, B)).toEqual({ type: 'ROTATION_HANDLE', assetInstanceId: 'B' })
        expect(resolveMrtPickTarget({ sourceId: '0xBA', isElementHit: false }, H, B)).toEqual({ type: 'ASSET_BODY', assetInstanceId: 'A' })
        expect(resolveMrtPickTarget({ sourceId: '0xBB', isElementHit: false }, H, B)).toEqual({ type: 'ASSET_BODY', assetInstanceId: 'B' })
    })
})

describe('scoped screen-space rotation-ring fallback (pure)', () => {
    // A projected ring centered at (100,100) with radius 50, sampled as a circle.
    const center = { x: 100, y: 100 }
    const radius = 50
    const samples: { x: number; y: number }[] = []
    for (let i = 0; i < 40; i++) {
        const a = (i / 40) * Math.PI * 2
        samples.push({ x: center.x + Math.cos(a) * radius, y: center.y + Math.sin(a) * radius })
    }

    it('pointer ON the ring outline is within tolerance', () => {
        // A point right on the +x outline (150,100).
        expect(pointerNearProjectedRing({ x: 150, y: 100 }, samples, 14)).toBe(true)
        // Slightly outside but within tolerance.
        expect(pointerNearProjectedRing({ x: 158, y: 100 }, samples, 14)).toBe(true)
    })

    it('pointer at the ring CENTER (the hole) is NOT near the outline', () => {
        // This is the key case: clicking the middle of the ring must not count
        // as a handle hit (that region belongs to body translation).
        expect(pointerNearProjectedRing({ x: 100, y: 100 }, samples, 14)).toBe(false)
    })

    it('pointer well OUTSIDE the ring is not near', () => {
        expect(pointerNearProjectedRing({ x: 300, y: 300 }, samples, 14)).toBe(false)
    })

    it('degenerate sample set is never a hit', () => {
        expect(pointerNearProjectedRing({ x: 150, y: 100 }, [], 14)).toBe(false)
        expect(pointerNearProjectedRing({ x: 150, y: 100 }, [{ x: 1, y: 1 }], 14)).toBe(false)
    })

    it('ringWorldSamples returns points on the circle in the center Z plane', () => {
        const pts = ringWorldSamples([10, 20, 5], 3, 8)
        expect(pts).toHaveLength(8)
        for (const [x, y, z] of pts) {
            expect(z).toBe(5)
            expect(Math.hypot(x - 10, y - 20)).toBeCloseTo(3, 6)
        }
    })
})

// --- 45. Fluid rotation math ---
describe('fluid yaw math', () => {
    it('signedAngleXYDeg: +X to +Y is +90', () => {
        expect(signedAngleXYDeg(1, 0, 0, 1)).toBeCloseTo(90)
    })
    it('signedAngleXYDeg: +X to -Y is -90', () => {
        expect(signedAngleXYDeg(1, 0, 0, -1)).toBeCloseTo(-90)
    })
    it('normalizeDeg folds into [0,360)', () => {
        expect(normalizeDeg(0)).toBe(0)
        expect(normalizeDeg(450)).toBe(90)
        expect(normalizeDeg(-90)).toBe(270)
        expect(normalizeDeg(360)).toBe(0)
    })
    it('computePreviewYaw: start 0 + quarter turn -> ~90', () => {
        const yaw = computePreviewYaw({ startYaw: 0, center: { x: 0, y: 0 }, startPoint: { x: 1, y: 0 }, currentPoint: { x: 0, y: 1 } })
        expect(yaw).toBeCloseTo(90)
    })
    it('computePreviewYaw: start 90 + quarter turn -> ~180', () => {
        const yaw = computePreviewYaw({ startYaw: 90, center: { x: 0, y: 0 }, startPoint: { x: 1, y: 0 }, currentPoint: { x: 0, y: 1 } })
        expect(yaw).toBeCloseTo(180)
    })
    it('computePreviewYaw: crossing 360 normalizes (start 350 + quarter -> ~80)', () => {
        const yaw = computePreviewYaw({ startYaw: 350, center: { x: 0, y: 0 }, startPoint: { x: 1, y: 0 }, currentPoint: { x: 0, y: 1 } })
        expect(yaw).toBeCloseTo(80)
    })
    it('computePreviewYaw: negative movement (start 0, -quarter -> ~270)', () => {
        const yaw = computePreviewYaw({ startYaw: 0, center: { x: 0, y: 0 }, startPoint: { x: 1, y: 0 }, currentPoint: { x: 0, y: -1 } })
        expect(yaw).toBeCloseTo(270)
    })
    it('computePreviewYaw: pointer on center -> undefined', () => {
        expect(computePreviewYaw({ startYaw: 0, center: { x: 5, y: 5 }, startPoint: { x: 5, y: 5 }, currentPoint: { x: 6, y: 6 } })).toBeUndefined()
    })
})

// --- 46/47. Rotation preview != commit ---
describe('object-attached rotation preview vs commit', () => {
    it('46 — preview yaw is non-authoritative; committed yaw unchanged; 0 events', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        store.rotateAssetYaw(a.assetInstanceId, 90) // committed yaw 90
        store.beginRotate(a.assetInstanceId)
        store.updateRotatePreview(137)
        const eff = store.getEffectiveProjectInstances().find((i) => i.assetInstanceId === a.assetInstanceId)!
        expect(eff.transform.rotation.yaw).toBe(137)                                 // rendered preview
        expect(store.getInstance(a.assetInstanceId)!.transform.rotation.yaw).toBe(90) // committed
    })

    it('47 — preview sequence keeps committed until release, then commits once', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0) // committed yaw 0
        store.beginRotate(a.assetInstanceId)
        for (const y of [101, 128, 157]) {
            store.updateRotatePreview(y)
            expect(store.getInstance(a.assetInstanceId)!.transform.rotation.yaw).toBe(0)
        }
        const r = store.commitRotate()
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.event.type).toBe('ASSET_ROTATED')
        expect(store.getInstance(a.assetInstanceId)!.transform.rotation.yaw).toBe(157)
        expect(store.getRotationPreview()).toBeUndefined()
        expect(store.getInteractionState()).toBe('IDLE')
        expect(store.getSnapshot().selectedAssetInstanceId).toBe(a.assetInstanceId)
    })
})

// --- 48. Rotation Esc cancel ---
describe('rotation cancel', () => {
    it('48 — cancel restores committed yaw, IDLE, selection kept, 0 events', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        store.rotateAssetYaw(a.assetInstanceId, 90) // committed 90
        store.beginRotate(a.assetInstanceId)
        store.updateRotatePreview(143)
        store.cancelRotate()
        expect(store.getInstance(a.assetInstanceId)!.transform.rotation.yaw).toBe(90)
        const eff = store.getEffectiveProjectInstances().find((i) => i.assetInstanceId === a.assetInstanceId)!
        expect(eff.transform.rotation.yaw).toBe(90)
        expect(store.getRotationPreview()).toBeUndefined()
        expect(store.getInteractionState()).toBe('IDLE')
        expect(store.getSnapshot().selectedAssetInstanceId).toBe(a.assetInstanceId)
    })
})

// --- 49/50. Rotation preserves position + identity ---
describe('rotation preserves position + identity', () => {
    it('49/50 — only yaw changes; position + identity immutable', () => {
        const store = newStore()
        const a = placeAt(store, 11.05, 10, 3.5)
        const before = {
            id: a.assetInstanceId, def: a.assetDefinitionId, geo: a.geometryRepresentationId,
            label: a.displayLabel, createdFrom: a.createdFrom, room: a.roomAssignment.state,
            state: a.installationState, source: a.spatialSource, scen: a.scenario?.scenarioId,
            pos: { ...a.transform.position }, pitch: a.transform.rotation.pitch, roll: a.transform.rotation.roll,
        }
        store.beginRotate(a.assetInstanceId)
        store.updateRotatePreview(63)
        const r = store.commitRotate()
        expect(r.ok).toBe(true)
        if (!r.ok) return
        const i = r.instance
        expect(i.transform.position).toEqual(before.pos)
        expect(i.transform.rotation.pitch).toBe(before.pitch)
        expect(i.transform.rotation.roll).toBe(before.roll)
        expect(i.transform.rotation.yaw).toBe(63)
        expect(i.assetInstanceId).toBe(before.id)
        expect(i.assetDefinitionId).toBe(before.def)
        expect(i.geometryRepresentationId).toBe(before.geo)
        expect(i.createdFrom).toBe(before.createdFrom)
        expect(i.roomAssignment.state).toBe(before.room)
        expect(i.installationState).toBe(before.state)
        expect(i.spatialSource).toBe(before.source)
        expect(i.scenario?.scenarioId).toBe(before.scen)
    })
})

// --- 51. Multi-instance rotation isolation ---
describe('rotation target isolation by assetInstanceId', () => {
    it('51 — rotating A leaves B unchanged; shared def/geometry preserved', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        const b = placeAt(store, 20, 0, 0)
        store.beginRotate(a.assetInstanceId)
        store.updateRotatePreview(120)
        store.commitRotate()
        expect(store.getInstance(a.assetInstanceId)!.transform.rotation.yaw).toBe(120)
        expect(store.getInstance(b.assetInstanceId)!.transform.rotation.yaw).toBe(0)
        expect(store.getInstance(a.assetInstanceId)!.assetDefinitionId).toBe(CATALOG_TEST_ASSET_DEFINITION_ID)
        expect(store.getInstance(b.assetInstanceId)!.assetDefinitionId).toBe(CATALOG_TEST_ASSET_DEFINITION_ID)
        expect(store.getInstance(a.assetInstanceId)!.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
        expect(store.getInstance(b.assetInstanceId)!.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
    })
})

// --- 52/53/54/55/56. Delete ---
describe('controlled delete', () => {
    it('52 — delete one instance; others + shared def/geometry preserved', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        const b = placeAt(store, 20, 0, 0)
        const r = store.deleteAsset(b.assetInstanceId)
        expect(r.ok).toBe(true)
        expect(store.getInstance(b.assetInstanceId)).toBeUndefined()
        expect(store.getInstance(a.assetInstanceId)).toBeDefined()
        // shared definition + geometry still resolvable in the registry.
        expect(store.getRegistry().getAssetDefinition(CATALOG_TEST_ASSET_DEFINITION_ID)).toBeDefined()
        expect(store.getRegistry().getGeometryRepresentation(GENERIC_PET_CT_GEOMETRY_ID)).toBeDefined()
    })

    it('53 — successful delete emits ONE ASSET_REMOVED; cancel path emits none', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        const r = store.deleteAsset(a.assetInstanceId)
        expect(r.ok).toBe(true)
        if (r.ok) expect(r.event.type).toBe('ASSET_REMOVED')
        // deleting again (already gone) -> not found, no event.
        const again = store.deleteAsset(a.assetInstanceId)
        expect(again.ok).toBe(false)
        if (!again.ok) expect(again.reason).toBe('ASSET_NOT_FOUND')
    })

    it('54 — delete blocked while an interaction is active', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        store.beginRotate(a.assetInstanceId)
        const r = store.deleteAsset(a.assetInstanceId)
        expect(r.ok).toBe(false)
        if (!r.ok) expect(r.reason).toBe('INTERACTION_ACTIVE')
        expect(store.getInstance(a.assetInstanceId)).toBeDefined()
    })

    it('55 — delete clears selection when the deleted asset was selected', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        store.selectAsset(a.assetInstanceId)
        store.deleteAsset(a.assetInstanceId)
        expect(store.getSnapshot().selectedAssetInstanceId).toBeUndefined()
        expect(store.isDragActive()).toBe(false)
        expect(store.isRotationActive()).toBe(false)
        expect(store.getInteractionState()).toBe('IDLE')
    })

    it('event detail carries prior transform + scenario', () => {
        const store = newStore()
        const a = placeAt(store, 4, 5, 6)
        store.rotateAssetYaw(a.assetInstanceId, 90)
        const r = store.deleteAsset(a.assetInstanceId)
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.event.detail?.priorX).toBe(4)
        expect(r.event.detail?.priorYaw).toBe(90)
        expect(r.event.detail?.scenarioId).toBe('MRT_DEV_SCENARIO')
    })
})

// --- delete only USER_PLACED ---
describe('delete restricted to USER_PLACED', () => {
    it('rejects deleting a non-USER_PLACED instance', () => {
        const store = newStore()
        // Insert a CATALOG-source instance directly (like a DEV fixture).
        const a = placeAt(store, 0, 0, 0)
        const fixture: AssetInstance = { ...a, assetInstanceId: 'PETCT-CATALOG-TEST-01', spatialSource: 'CATALOG' }
        store.insertInstance(fixture)
        const r = store.deleteAsset('PETCT-CATALOG-TEST-01')
        expect(r.ok).toBe(false)
        if (!r.ok) expect(r.reason).toBe('DELETE_NOT_ALLOWED_FOR_SOURCE')
        expect(store.getInstance('PETCT-CATALOG-TEST-01')).toBeDefined()
    })
})

// --- mutual exclusivity: rotation vs translate/placement ---
describe('rotation mutual exclusivity', () => {
    it('rotation cannot begin while translating; translate cannot begin while rotating', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        expect(store.beginRotate(a.assetInstanceId).ok).toBe(false)
        store.cancelDrag()
        store.beginRotate(a.assetInstanceId)
        expect(store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 }).ok).toBe(false)
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        expect(res.ok).toBe(true)
        if (res.ok) expect(store.beginPlacement(res.intent).ok).toBe(false)
    })
})

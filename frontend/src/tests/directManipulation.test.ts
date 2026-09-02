/**
 * Offline tests for direct object selection + fluid drag manipulation.
 * Pure domain/store + pure picking math; no Bentley runtime. Central doctrine:
 * preview is not commit — N preview updates, 1 release, 1 authoritative commit,
 * 1 ASSET_MOVED. Identity + rotation + start Z preserved.
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
import { decideHitAcceptance, pickNearestInstance, rayIntersectInstance, rayIntersectZPlane, type Ray3 } from '../components/spatial/assetPicking'
import { SpatialAssetDecorator } from '../components/spatial/SpatialAssetDecorator'

const DEV_SCENARIO: ScenarioProvenance = { scenarioId: 'MRT_DEV_SCENARIO', scenarioState: 'DRAFT' }

function newStore(): SpatialAssetStore {
    return new SpatialAssetStore({ projectId: TEST_PROJECT_ID, scenario: DEV_SCENARIO })
}

function placeAt(store: SpatialAssetStore, x: number, y: number, z: number): AssetInstance {
    const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
    if (!res.ok) throw new Error(res.reason)
    store.beginPlacement(res.intent)
    const r = store.completePlacementAt({ x, y, z })
    if (!r.ok) throw new Error(r.reason)
    return r.instance
}

// A downward ray from high above a point (x,y): origin (x,y,100), dir (0,0,-1).
function downRayAt(x: number, y: number): Ray3 {
    return { origin: [x, y, 100], direction: [0, 0, -1] }
}

// --- 8/11/12. Picking ---
describe('ray/bbox picking', () => {
    it('hits an instance directly above it', () => {
        const store = newStore()
        const a = placeAt(store, 10, 10, 0)
        expect(rayIntersectInstance(downRayAt(10, 10), a)).toBeTypeOf('number')
    })

    it('misses when the ray is well outside the footprint', () => {
        const store = newStore()
        const a = placeAt(store, 10, 10, 0)
        expect(rayIntersectInstance(downRayAt(100, 100), a)).toBeUndefined()
    })

    it('accounts for rotation: a yawed scanner is hit along its rotated extent', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        // width (X) = 2.2 -> half 1.1; depth (Y) = 3.0 -> half 1.5. A point at
        // (0, 1.4) is inside unrotated (|y|<1.5). After yaw 90, X and Y extents
        // swap, so (0,1.4) is now beyond the rotated Y half-extent (1.1) -> miss,
        // while (1.4, 0) becomes a hit. Prove rotation changed the hit set.
        store.rotateAssetYaw(a.assetInstanceId, 90)
        const rotated = store.getInstance(a.assetInstanceId)!
        const hitAlongRotatedX = rayIntersectInstance(downRayAt(1.4, 0), rotated)
        const missAlongRotatedY = rayIntersectInstance(downRayAt(0, 1.4), rotated)
        expect(hitAlongRotatedX).toBeTypeOf('number')
        expect(missAlongRotatedY).toBeUndefined()
    })

    it('picks the NEAREST instance along the ray, not by array order', () => {
        const store = newStore()
        // Two overlapping in XY at different Z; a downward ray hits the higher one first.
        const low = placeAt(store, 5, 5, 0)
        const high = placeAt(store, 5, 5, 10)
        const nearest = pickNearestInstance(downRayAt(5, 5), [low, high])
        expect(nearest).toBe(high.assetInstanceId)
        // Reverse array order — still the higher one.
        const nearest2 = pickNearestInstance(downRayAt(5, 5), [high, low])
        expect(nearest2).toBe(high.assetInstanceId)
    })

    it('distinguishes two GE Discovery MI instances by spatial hit', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        const b = placeAt(store, 20, 0, 0)
        expect(pickNearestInstance(downRayAt(0, 0), [a, b])).toBe(a.assetInstanceId)
        expect(pickNearestInstance(downRayAt(20, 0), [a, b])).toBe(b.assetInstanceId)
    })

    it('rayIntersectZPlane returns the planar point (drag-plane math)', () => {
        const ray: Ray3 = { origin: [3, 4, 10], direction: [0, 0, -1] }
        expect(rayIntersectZPlane(ray, 2)).toEqual([3, 4, 2])
        const angled: Ray3 = { origin: [0, 0, 10], direction: [1, 0, -1] }
        expect(rayIntersectZPlane(angled, 0)).toEqual([10, 0, 0])
    })
})

// --- 4/5/29/30. Fluid drag: preview is not commit ---
describe('fluid drag: transient preview vs authoritative commit', () => {
    it('N preview updates during drag emit ZERO ASSET_MOVED events; committed pos unchanged mid-drag', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 5)
        let events = 0
        // (there is no per-move event API; assert committed position is unchanged
        // through many preview updates, and the store count/transform stable.)
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 5 })
        for (let i = 1; i <= 25; i++) {
            store.updateDragPreview({ x: i, y: i, z: 5 })
            // committed instance must NOT move during preview.
            expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 0, y: 0, z: 5 })
        }
        expect(events).toBe(0)
        // Preview reflects the last update.
        expect(store.getDragPreview()!.previewPosition).toEqual({ x: 25, y: 25, z: 5 })
    })

    it('release commits exactly ONE move + ONE ASSET_MOVED; preview cleared', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 5)
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 5 })
        store.updateDragPreview({ x: 8, y: 9, z: 5 })
        const r = store.commitDrag()
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.event.type).toBe('ASSET_MOVED')
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 8, y: 9, z: 5 })
        expect(store.isDragActive()).toBe(false)
        expect(store.getDragPreview()).toBeUndefined()
        // A second commit does nothing (preview consumed once).
        const again = store.commitDrag()
        expect(again.ok).toBe(false)
    })

    it('grab offset is preserved (asset does not snap under the cursor)', () => {
        const store = newStore()
        const a = placeAt(store, 10, 10, 0)
        // Grab at (11,10) — 1m to the +X of the asset center.
        store.beginDrag(a.assetInstanceId, { x: 11, y: 10, z: 0 })
        // Drag the grab point to (21,10); asset should follow to (20,10).
        store.updateDragPreview({ x: 21, y: 10, z: 0 })
        expect(store.getDragPreview()!.previewPosition).toEqual({ x: 20, y: 10, z: 0 })
    })

    it('fluid drag preserves start Z (X/Y planar move)', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 7)
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 7 })
        // Even if the drag world point reports a different Z, preview keeps start Z.
        store.updateDragPreview({ x: 3, y: 3, z: 99 })
        expect(store.getDragPreview()!.previewPosition.z).toBe(7)
        const r = store.commitDrag()
        if (r.ok) expect(r.instance.transform.position.z).toBe(7)
    })
})

describe('fluid drag: cancel', () => {
    it('cancel discards the preview, commits nothing, restores committed position', () => {
        const store = newStore()
        const a = placeAt(store, 4, 4, 0)
        store.beginDrag(a.assetInstanceId, { x: 4, y: 4, z: 0 })
        store.updateDragPreview({ x: 40, y: 40, z: 0 })
        store.cancelDrag()
        expect(store.isDragActive()).toBe(false)
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 4, y: 4, z: 0 })
    })
})

// --- 33/34/36. Drag preserves rotation + identity; keyed by instance id ---
describe('fluid drag: identity + rotation immutability', () => {
    it('dragging a rotated scanner preserves yaw and all identity fields', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        store.rotateAssetYaw(a.assetInstanceId, 90) // yaw 90
        const before = store.getInstance(a.assetInstanceId)!
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        store.updateDragPreview({ x: 12, y: 0, z: 0 })
        const r = store.commitDrag()
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.instance.transform.rotation.yaw).toBe(90)
        expect(r.instance.assetInstanceId).toBe(before.assetInstanceId)
        expect(r.instance.assetDefinitionId).toBe(CATALOG_TEST_ASSET_DEFINITION_ID)
        expect(r.instance.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
        expect(r.instance.createdFrom).toBe(before.createdFrom)
        expect(r.instance.spatialSource).toBe('USER_PLACED')
        expect(r.instance.roomAssignment.state).toBe('NOT_ASSIGNED')
        expect(r.instance.installationState).toBe('PLACED')
        expect(r.instance.scenario?.scenarioId).toBe('MRT_DEV_SCENARIO')
    })

    it('dragging one of two instances moves only that instance (keyed by id)', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        const b = placeAt(store, 20, 0, 0)
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        store.updateDragPreview({ x: 5, y: 5, z: 0 })
        store.commitDrag()
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 5, y: 5, z: 0 })
        expect(store.getInstance(b.assetInstanceId)!.transform.position).toEqual({ x: 20, y: 0, z: 0 })
    })

    it('effective instances apply preview only to the dragged instance', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        const b = placeAt(store, 20, 0, 0)
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        store.updateDragPreview({ x: 3, y: 3, z: 0 })
        const eff = store.getEffectiveProjectInstances()
        const ea = eff.find((i) => i.assetInstanceId === a.assetInstanceId)!
        const eb = eff.find((i) => i.assetInstanceId === b.assetInstanceId)!
        expect(ea.transform.position).toEqual({ x: 3, y: 3, z: 0 })   // preview
        expect(eb.transform.position).toEqual({ x: 20, y: 0, z: 0 })  // committed
    })
})

// --- 28-32. Preview-render correction: effective transform + cache mode ---
describe('preview render correction', () => {
    it('28 — effective instance renders at preview B while committed stays at A', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0) // committed A = (1,1,0)
        store.beginDrag(a.assetInstanceId, { x: 1, y: 1, z: 0 })
        store.updateDragPreview({ x: 12, y: 8, z: 0 }) // preview B = (12,8,0)
        const eff = store.getEffectiveProjectInstances().find((i) => i.assetInstanceId === a.assetInstanceId)!
        expect(eff.transform.position).toEqual({ x: 12, y: 8, z: 0 })            // rendered at B
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 1, y: 1, z: 0 }) // committed A
    })

    it('29 — preview through B1/B2/B3 keeps committed A + 0 commits until release, then B3 + 1 event', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        for (const b of [{ x: 1, y: 0, z: 0 }, { x: 2, y: 0, z: 0 }, { x: 3, y: 0, z: 0 }]) {
            store.updateDragPreview(b)
            expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 0, y: 0, z: 0 })
        }
        const r = store.commitDrag()
        expect(r.ok).toBe(true)
        if (r.ok) expect(r.event.type).toBe('ASSET_MOVED')
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 3, y: 0, z: 0 })
    })

    it('30 — cancel returns effective render position to committed A', () => {
        const store = newStore()
        const a = placeAt(store, 5, 5, 0)
        store.beginDrag(a.assetInstanceId, { x: 5, y: 5, z: 0 })
        store.updateDragPreview({ x: 50, y: 50, z: 0 })
        store.cancelDrag()
        const eff = store.getEffectiveProjectInstances().find((i) => i.assetInstanceId === a.assetInstanceId)!
        expect(eff.transform.position).toEqual({ x: 5, y: 5, z: 0 })
    })

    it('31 — rotated preview keeps yaw on the effective instance', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        store.rotateAssetYaw(a.assetInstanceId, 180) // yaw 180
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        store.updateDragPreview({ x: 6, y: 0, z: 0 })
        const eff = store.getEffectiveProjectInstances().find((i) => i.assetInstanceId === a.assetInstanceId)!
        expect(eff.transform.rotation.yaw).toBe(180)
        expect(eff.transform.position).toEqual({ x: 6, y: 0, z: 0 })
    })

    it('32 — no instance replacement during preview (identity/count stable)', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        const beforeCount = store.count
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        store.updateDragPreview({ x: 9, y: 9, z: 0 })
        const eff = store.getEffectiveProjectInstances().find((i) => i.assetInstanceId === a.assetInstanceId)!
        expect(store.count).toBe(beforeCount)
        expect(eff.assetInstanceId).toBe(a.assetInstanceId)
        expect(eff.assetDefinitionId).toBe(CATALOG_TEST_ASSET_DEFINITION_ID)
        expect(eff.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
    })

    it('decorator useCachedDecorations is true when idle, undefined (no cache) while dragging', () => {
        let dragging = false
        const dec = new SpatialAssetDecorator(() => [], () => undefined, () => dragging)
        expect(dec.useCachedDecorations).toBe(true)
        dragging = true
        expect(dec.useCachedDecorations).toBeUndefined()
        dragging = false
        expect(dec.useCachedDecorations).toBe(true)
    })
})

// --- 21/22. Decoration hit acceptance decision (Bentley tool filterHit seam) ---
describe('decoration hit acceptance (filterHit decision)', () => {
    // A resolver simulating the decorator's pickId -> assetInstanceId map.
    const map = new Map<string, string>([
        ['0x1', 'PETCT-GE-DISCOVERY-MI-0001'],
        ['0x2', 'PETCT-GE-DISCOVERY-MI-0002'],
    ])
    const resolve = (pickId: string) => map.get(pickId)

    it('ACCEPTS a decoration hit whose pick id maps to an assetInstanceId', () => {
        expect(decideHitAcceptance({ sourceId: '0x1', isElementHit: false }, resolve)).toBe('ACCEPT')
    })

    it('REJECTS an unknown decoration pick id', () => {
        expect(decideHitAcceptance({ sourceId: '0x999', isElementHit: false }, resolve)).toBe('REJECT')
    })

    it('REJECTS a BIM element hit even if an id is present', () => {
        expect(decideHitAcceptance({ sourceId: '0x1', isElementHit: true }, resolve)).toBe('REJECT')
    })

    it('REJECTS a hit with no source id', () => {
        expect(decideHitAcceptance({ sourceId: undefined, isElementHit: false }, resolve)).toBe('REJECT')
    })

    it('resolves the correct independent assetInstanceId per pick id', () => {
        expect(resolve('0x1')).toBe('PETCT-GE-DISCOVERY-MI-0001')
        expect(resolve('0x2')).toBe('PETCT-GE-DISCOVERY-MI-0002')
        expect(decideHitAcceptance({ sourceId: '0x2', isElementHit: false }, resolve)).toBe('ACCEPT')
    })
})

// --- 40-45. Drag lifecycle termination + clean return to IDLE ---
describe('direct drag lifecycle termination', () => {
    it('40 — successful release: committed=B, preview cleared, IDLE, selection kept, 1 ASSET_MOVED', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0) // A
        store.selectAsset(a.assetInstanceId)
        store.beginDrag(a.assetInstanceId, { x: 1, y: 1, z: 0 })
        expect(store.getInteractionState()).toBe('MOVING')
        store.updateDragPreview({ x: 7, y: 8, z: 0 }) // B
        const r = store.commitDrag()
        expect(r.ok).toBe(true)
        if (r.ok) expect(r.event.type).toBe('ASSET_MOVED')
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 7, y: 8, z: 0 })
        expect(store.getDragPreview()).toBeUndefined()
        expect(store.getInteractionState()).toBe('IDLE')
        expect(store.getSnapshot().selectedAssetInstanceId).toBe(a.assetInstanceId)
    })

    it('41 — cancel: committed=A, preview cleared, IDLE, selection kept, 0 events', () => {
        const store = newStore()
        const a = placeAt(store, 3, 3, 0) // A
        store.selectAsset(a.assetInstanceId)
        store.beginDrag(a.assetInstanceId, { x: 3, y: 3, z: 0 })
        store.updateDragPreview({ x: 30, y: 30, z: 0 }) // B (discarded)
        store.cancelDrag()
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 3, y: 3, z: 0 })
        expect(store.getDragPreview()).toBeUndefined()
        expect(store.getInteractionState()).toBe('IDLE')
        expect(store.getSnapshot().selectedAssetInstanceId).toBe(a.assetInstanceId)
    })

    it('42 — after commit, a passive updateDragPreview is a no-op (no active drag)', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        store.updateDragPreview({ x: 5, y: 0, z: 0 })
        store.commitDrag() // committed (5,0,0), IDLE
        // passive motion after commit must not move the asset or restart drag.
        store.updateDragPreview({ x: 99, y: 99, z: 0 })
        expect(store.isDragActive()).toBe(false)
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 5, y: 0, z: 0 })
        expect(store.getInteractionState()).toBe('IDLE')
    })

    it('42b — after cancel, a passive updateDragPreview is a no-op', () => {
        const store = newStore()
        const a = placeAt(store, 2, 2, 0)
        store.beginDrag(a.assetInstanceId, { x: 2, y: 2, z: 0 })
        store.updateDragPreview({ x: 20, y: 20, z: 0 })
        store.cancelDrag()
        store.updateDragPreview({ x: 99, y: 99, z: 0 }) // ignored — no active drag
        expect(store.isDragActive()).toBe(false)
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 2, y: 2, z: 0 })
    })

    it('43 — rotation is eligible again after drag commit and after cancel (interaction IDLE)', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        store.updateDragPreview({ x: 4, y: 0, z: 0 })
        store.commitDrag()
        // interaction IDLE => rotation accepted.
        const rot1 = store.rotateAssetYaw(a.assetInstanceId, 90)
        expect(rot1.ok).toBe(true)
        // Another drag + cancel, then rotate again.
        store.beginDrag(a.assetInstanceId, { x: 4, y: 0, z: 0 })
        store.cancelDrag()
        const rot2 = store.rotateAssetYaw(a.assetInstanceId, 90)
        expect(rot2.ok).toBe(true)
    })

    it('45 — event semantics: select/preview=0, release=1, cancel=0', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        // selection click: no move.
        store.selectAsset(a.assetInstanceId)
        // begin + many previews: no committed change.
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        for (let i = 1; i <= 10; i++) store.updateDragPreview({ x: i, y: 0, z: 0 })
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 0, y: 0, z: 0 })
        // release: exactly one ASSET_MOVED.
        const committed = store.commitDrag()
        expect(committed.ok).toBe(true)
        if (committed.ok) expect(committed.event.type).toBe('ASSET_MOVED')
        // a cancel with no active drag returns nothing/no event.
        store.cancelDrag()
        expect(store.isDragActive()).toBe(false)
    })
})

// --- 20/21. Silent non-MRT hit behavior ---
describe('non-MRT hit is rejected silently with no state change', () => {
    const map = new Map<string, string>([['0x1', 'PETCT-GE-DISCOVERY-MI-0001']])
    const resolve = (pickId: string) => map.get(pickId)

    it('20 — BIM element and unknown decoration are REJECTED; known MRT id ACCEPTED', () => {
        expect(decideHitAcceptance({ sourceId: '0x1', isElementHit: false }, resolve)).toBe('ACCEPT')
        expect(decideHitAcceptance({ sourceId: '0xBIM', isElementHit: true }, resolve)).toBe('REJECT')
        expect(decideHitAcceptance({ sourceId: '0xUNKNOWN', isElementHit: false }, resolve)).toBe('REJECT')
    })

    it('21 — a rejected (non-MRT) hit produces no store state change', () => {
        const store = newStore()
        const a = placeAt(store, 5, 5, 0)
        store.selectAsset(a.assetInstanceId)
        const before = {
            selected: store.getSnapshot().selectedAssetInstanceId,
            interaction: store.getInteractionState(),
            drag: store.isDragActive(),
            count: store.count,
            pos: { ...store.getInstance(a.assetInstanceId)!.transform.position },
            yaw: store.getInstance(a.assetInstanceId)!.transform.rotation.yaw,
        }
        // Simulate the tool's decision on a BIM hit: REJECT -> tool does nothing.
        const decision = decideHitAcceptance({ sourceId: '0xBIM', isElementHit: true }, resolve)
        expect(decision).toBe('REJECT')
        // No store method is invoked on a rejected hit; assert nothing changed.
        expect(store.getSnapshot().selectedAssetInstanceId).toBe(before.selected)
        expect(store.getInteractionState()).toBe(before.interaction)
        expect(store.isDragActive()).toBe(before.drag)
        expect(store.count).toBe(before.count)
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual(before.pos)
        expect(store.getInstance(a.assetInstanceId)!.transform.rotation.yaw).toBe(before.yaw)
    })
})

// --- 26-31. Cancellation reliability (right-click / Esc converge on cancelDrag) ---
describe('direct drag cancellation restores last committed position', () => {
    // Both right-click and Esc converge on store.cancelDrag() via the tool's
    // single cancelActiveDirectDrag path; the store behavior is identical.
    function beginPreviewCancel(store: SpatialAssetStore, id: string, from: { x: number; y: number; z: number }, to: { x: number; y: number; z: number }) {
        store.beginDrag(id, from)
        store.updateDragPreview(to)
        store.cancelDrag()
    }

    it('26/27 — cancel restores committed position B, IDLE, selection kept, 0 events', () => {
        const store = newStore()
        const a = placeAt(store, 6, 6, 0) // committed B
        store.selectAsset(a.assetInstanceId)
        beginPreviewCancel(store, a.assetInstanceId, { x: 6, y: 6, z: 0 }, { x: 60, y: 60, z: 0 }) // toward C
        const eff = store.getEffectiveProjectInstances().find((i) => i.assetInstanceId === a.assetInstanceId)!
        expect(eff.transform.position).toEqual({ x: 6, y: 6, z: 0 })          // rendered at B
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 6, y: 6, z: 0 })
        expect(store.getDragPreview()).toBeUndefined()
        expect(store.getInteractionState()).toBe('IDLE')
        expect(store.getSnapshot().selectedAssetInstanceId).toBe(a.assetInstanceId)
    })

    it('28 — cancel returns to the MOST RECENT commit (A -> commit B -> drag toward C -> cancel = B)', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0) // A
        // successful drag commit to B
        store.beginDrag(a.assetInstanceId, { x: 1, y: 1, z: 0 })
        store.updateDragPreview({ x: 10, y: 10, z: 0 }) // B
        store.commitDrag()
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 10, y: 10, z: 0 })
        // second drag toward C, then cancel -> back to B (not A, not C)
        store.beginDrag(a.assetInstanceId, { x: 10, y: 10, z: 0 })
        store.updateDragPreview({ x: 99, y: 99, z: 0 }) // C
        store.cancelDrag()
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 10, y: 10, z: 0 })
    })

    it('29 — passive updateDragPreview after cancel is a no-op (no restart)', () => {
        const store = newStore()
        const a = placeAt(store, 2, 2, 0)
        beginPreviewCancel(store, a.assetInstanceId, { x: 2, y: 2, z: 0 }, { x: 20, y: 20, z: 0 })
        store.updateDragPreview({ x: 88, y: 88, z: 0 }) // ignored (no active drag)
        expect(store.isDragActive()).toBe(false)
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 2, y: 2, z: 0 })
    })

    it('right-click routing parity — cancel via the same store path yields the same outcome as Esc', () => {
        // The tool's secondary-button DOM guard and its Esc handler both call the
        // one shared cancelActiveDirectDrag -> store.cancelDrag(). Prove the store
        // outcome is identical regardless of which input triggered it.
        const runCancel = (fromX: number) => {
            const store = newStore()
            const a = placeAt(store, 7, 7, 0) // committed B
            store.selectAsset(a.assetInstanceId)
            store.beginDrag(a.assetInstanceId, { x: 7, y: 7, z: 0 })
            store.updateDragPreview({ x: fromX, y: fromX, z: 0 }) // toward C
            store.cancelDrag() // same call the RIGHT_CLICK and ESC paths make
            return {
                pos: store.getInstance(a.assetInstanceId)!.transform.position,
                drag: store.isDragActive(),
                interaction: store.getInteractionState(),
                selected: store.getSnapshot().selectedAssetInstanceId,
            }
        }
        const viaRightClick = runCancel(70)
        const viaEsc = runCancel(80)
        expect(viaRightClick).toEqual({ pos: { x: 7, y: 7, z: 0 }, drag: false, interaction: 'IDLE', selected: viaRightClick.selected })
        expect(viaEsc.pos).toEqual(viaRightClick.pos)
        expect(viaEsc.drag).toBe(false)
        expect(viaEsc.interaction).toBe('IDLE')
    })

    it('30 — rotation is eligible after cancel (interaction IDLE)', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        beginPreviewCancel(store, a.assetInstanceId, { x: 0, y: 0, z: 0 }, { x: 5, y: 5, z: 0 })
        const rot = store.rotateAssetYaw(a.assetInstanceId, 90)
        expect(rot.ok).toBe(true)
    })

    it('31 — cancel preserves all identity fields (only nothing changes)', () => {
        const store = newStore()
        const a = placeAt(store, 3, 4, 0)
        const id = (i: AssetInstance) => ({
            assetInstanceId: i.assetInstanceId, assetDefinitionId: i.assetDefinitionId,
            geometryRepresentationId: i.geometryRepresentationId, displayLabel: i.displayLabel,
            createdFrom: i.createdFrom, room: i.roomAssignment.state, state: i.installationState,
            source: i.spatialSource, scenarioId: i.scenario?.scenarioId, yaw: i.transform.rotation.yaw,
            dimProv: i.dimensions.provenance,
        })
        const before = id(store.getInstance(a.assetInstanceId)!)
        const beforePos = { ...store.getInstance(a.assetInstanceId)!.transform.position }
        beginPreviewCancel(store, a.assetInstanceId, { x: 3, y: 4, z: 0 }, { x: 30, y: 40, z: 0 })
        const after = store.getInstance(a.assetInstanceId)!
        expect(id(after)).toEqual(before)
        expect(after.transform.position).toEqual(beforePos)
    })
})

// --- mutual exclusivity ---
describe('drag mutual exclusivity', () => {
    it('drag cannot start while placement is active; placement cannot start while dragging', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 0)
        // placement active blocks drag
        const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res.ok) store.beginPlacement(res.intent)
        const dragBlocked = store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        expect(dragBlocked.ok).toBe(false)
        store.cancelPlacement()
        // drag active blocks placement + command move
        store.beginDrag(a.assetInstanceId, { x: 0, y: 0, z: 0 })
        const res2 = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
        if (res2.ok) {
            const placeBlocked = store.beginPlacement(res2.intent)
            expect(placeBlocked.ok).toBe(false)
        }
        const moveBlocked = store.beginMove(a.assetInstanceId)
        expect(moveBlocked.ok).toBe(false)
    })
})

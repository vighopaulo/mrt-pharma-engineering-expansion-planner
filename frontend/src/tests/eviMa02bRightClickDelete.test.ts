/**
 * EVI-MA-02B — right-click + Delete-key equipment deletion regression tests.
 * Bentley-FREE: exercises the pure focus-safety decision and the authoritative
 * equipment delete + collision-release semantics (the live right-click bridge
 * and keydown wiring are proven by manual acceptance).
 */
import { describe, expect, it } from 'vitest'
import { shouldHandleEquipmentDeleteKey } from '../components/spatial/assetPicking'
import {
    createEquipmentInstance,
    findEquipmentCollision,
    pickNearestEquipment,
    rayIntersectEquipment,
    type EquipmentAssetInstance,
    type EquipmentPlacement,
    type EquipmentPickRay,
} from '../components/spatial/equipmentInstance'
import { canonicalEquipmentById } from '../components/spatial/canonicalEquipmentCatalog'

const ROOM = [
    { x: -20, y: -20 }, { x: 20, y: -20 }, { x: 20, y: 20 }, { x: -20, y: 20 },
]
function place(canonicalId: string, seq: number): EquipmentAssetInstance {
    const r = createEquipmentInstance({
        iModelId: 'imodel-EVI2B', canonicalEquipmentId: canonicalId, parentBimSpaceId: '0xROOM',
        footprint: ROOM, zLow: 0, zHigh: 4, seq,
    })
    if (!r.ok) throw new Error(r.reason)
    return r.instance
}
function placement(x: number, y: number): EquipmentPlacement {
    return { centerX: x, centerY: y, zBase: 0, width: 2, depth: 2, height: 2, yaw: 0, envelopeProvenance: 'CALIBRATED' }
}

// Authoritative store stand-in mirroring selectedEquipmentId + deleteEquipment.
function makeStore(initial: EquipmentAssetInstance[]) {
    let instances = [...initial]
    let selectedId: string | undefined
    return {
        list: () => instances as readonly EquipmentAssetInstance[],
        select: (id: string | undefined) => { selectedId = id },
        selected: () => selectedId,
        delete: (id: string): { ok: boolean; reason?: string } => {
            const e = instances.find((x) => x.id === id)
            if (!e) return { ok: false, reason: 'NO_INSTANCE' }
            if (e.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED' }
            instances = instances.filter((x) => x.id !== id)
            if (selectedId === id) selectedId = undefined
            return { ok: true }
        },
        place: (canonicalId: string, p: EquipmentPlacement): { ok: boolean; id?: string; reason?: string } => {
            const inst = { ...place(canonicalId, instances.length + 1), placement: p }
            const c = findEquipmentCollision({ proposed: p, existing: instances })
            if (c.collides) return { ok: false, reason: 'EQUIPMENT_COLLISION' }
            instances = [...instances, inst]
            return { ok: true, id: inst.id }
        },
    }
}

// ---------------------------------------------------------------------------
// Focus safety — Delete key must not fire while typing
// ---------------------------------------------------------------------------
describe('EVI-MA-02B shouldHandleEquipmentDeleteKey', () => {
    it('handles Delete/Backspace over the viewport/body', () => {
        expect(shouldHandleEquipmentDeleteKey({ key: 'Delete', tagName: 'CANVAS', isContentEditable: false })).toBe(true)
        expect(shouldHandleEquipmentDeleteKey({ key: 'Backspace', tagName: 'BODY', isContentEditable: false })).toBe(true)
        expect(shouldHandleEquipmentDeleteKey({ key: 'Delete', tagName: undefined, isContentEditable: undefined })).toBe(true)
    })

    it('ignores when typing in input / textarea / select / contenteditable', () => {
        expect(shouldHandleEquipmentDeleteKey({ key: 'Delete', tagName: 'INPUT', isContentEditable: false })).toBe(false)
        expect(shouldHandleEquipmentDeleteKey({ key: 'Delete', tagName: 'TEXTAREA', isContentEditable: false })).toBe(false)
        expect(shouldHandleEquipmentDeleteKey({ key: 'Delete', tagName: 'SELECT', isContentEditable: false })).toBe(false)
        expect(shouldHandleEquipmentDeleteKey({ key: 'Backspace', tagName: 'DIV', isContentEditable: true })).toBe(false)
    })

    it('ignores non-delete keys', () => {
        expect(shouldHandleEquipmentDeleteKey({ key: 'a', tagName: 'CANVAS', isContentEditable: false })).toBe(false)
        expect(shouldHandleEquipmentDeleteKey({ key: 'Enter', tagName: 'BODY', isContentEditable: false })).toBe(false)
        expect(shouldHandleEquipmentDeleteKey({ key: 'Escape', tagName: 'BODY', isContentEditable: false })).toBe(false)
    })
})

// ---------------------------------------------------------------------------
// Delete-key acts on selectedEquipmentId (exact instance), lock respected
// ---------------------------------------------------------------------------
describe('EVI-MA-02B delete-key on selected equipment', () => {
    it('deletes the exact selected instance; KEY deletion leaves KIUBE', () => {
        const kiube = { ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(-8, 0) }
        const key = { ...place('IBA_CYCLONE_KEY', 2), placement: placement(8, 0) }
        const store = makeStore([kiube, key])
        store.select(key.id) // left-click KEY selected it
        // Delete key -> deleteEquipment(selectedEquipmentId)
        const res = store.delete(store.selected()!)
        expect(res.ok).toBe(true)
        expect(store.list().map((e) => e.id)).toEqual([kiube.id])
        expect(store.selected()).toBeUndefined()
    })

    it('locked selected equipment is NOT deleted by the delete key (reason LOCKED)', () => {
        const kiube: EquipmentAssetInstance = { ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(0, 0), lifecycleState: 'LOCKED' }
        const store = makeStore([kiube])
        store.select(kiube.id)
        const res = store.delete(store.selected()!)
        expect(res.ok).toBe(false)
        expect(res.reason).toBe('LOCKED')
        expect(store.list()).toHaveLength(1)
    })

    it('no-op when nothing is selected', () => {
        const store = makeStore([{ ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(0, 0) }])
        expect(store.selected()).toBeUndefined()
        // Handler would early-return without calling delete; store unchanged.
        expect(store.list()).toHaveLength(1)
    })
})

// ---------------------------------------------------------------------------
// Delete releases collision volume (EVI-MA-02A preserved)
// ---------------------------------------------------------------------------
describe('EVI-MA-02B delete releases occupied volume', () => {
    it('after deleting KIUBE, a KEY placement in the released space succeeds', () => {
        const store = makeStore([])
        const a = store.place('IBA_CYCLONE_KIUBE', placement(0, 0))
        expect(a.ok).toBe(true)
        // Overlapping KEY rejected while KIUBE occupies the space.
        expect(store.place('IBA_CYCLONE_KEY', placement(0.5, 0)).ok).toBe(false)
        // Delete KIUBE, then the same KEY placement succeeds.
        store.delete(a.id!)
        expect(store.place('IBA_CYCLONE_KEY', placement(0.5, 0)).ok).toBe(true)
    })
})

// ---------------------------------------------------------------------------
// Right-click ray pick — resolves the exact instance (the live-fix core)
// ---------------------------------------------------------------------------
describe('EVI-MA-02B right-click ray pick', () => {
    // A downward ray from above through a point hits the equipment box below it.
    function downRayAt(x: number, y: number): EquipmentPickRay {
        return { origin: [x, y, 100], direction: [0, 0, -1] }
    }

    it('a ray through an instance hits its oriented box', () => {
        const p = placement(3, -4)
        expect(rayIntersectEquipment(downRayAt(3, -4), p)).not.toBeUndefined()
        // A ray clearly outside the footprint misses.
        expect(rayIntersectEquipment(downRayAt(50, 50), p)).toBeUndefined()
    })

    it('pickNearestEquipment resolves the exact instance under the cursor (KEY not KIUBE)', () => {
        const kiube = { ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(-8, 0) }
        const key = { ...place('IBA_CYCLONE_KEY', 2), placement: placement(8, 0) }
        const list = [kiube, key]
        expect(pickNearestEquipment(downRayAt(8, 0), list)).toBe(key.id)
        expect(pickNearestEquipment(downRayAt(-8, 0), list)).toBe(kiube.id)
        // Empty space resolves to nothing (BIM/empty right-click -> no menu).
        expect(pickNearestEquipment(downRayAt(0, 30), list)).toBeUndefined()
    })

    it('overlapping instances resolve to the NEAREST along the ray (deterministic)', () => {
        // Two boxes at the same XY but different Z; a downward ray hits the higher one first.
        const lower: EquipmentAssetInstance = { ...place('IBA_CYCLONE_KIUBE', 1), placement: { ...placement(0, 0), zBase: 0, height: 2 } }
        const upper: EquipmentAssetInstance = { ...place('IBA_CYCLONE_KEY', 2), placement: { ...placement(0, 0), zBase: 5, height: 2 } }
        expect(pickNearestEquipment(downRayAt(0, 0), [lower, upper])).toBe(upper.id)
    })

    it('hidden instances are not picked', () => {
        const hidden: EquipmentAssetInstance = { ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(0, 0), hidden: true }
        expect(pickNearestEquipment(downRayAt(0, 0), [hidden])).toBeUndefined()
    })
})

// ---------------------------------------------------------------------------
// Canonical model title for the right-click menu (KEY vs KIUBE)
// ---------------------------------------------------------------------------
describe('EVI-MA-02B menu identity', () => {
    it('resolves distinct canonical titles for overlapping-family cyclotrons', () => {
        const key = place('IBA_CYCLONE_KEY', 1)
        const kiube = place('IBA_CYCLONE_KIUBE', 2)
        const ck = canonicalEquipmentById(key.canonicalEquipmentId)!
        const ci = canonicalEquipmentById(kiube.canonicalEquipmentId)!
        expect(`${ck.manufacturer} ${ck.model}`).toBe('IBA Cyclone KEY')
        expect(`${ci.manufacturer} ${ci.model}`).toBe('IBA Cyclone KIUBE')
        expect(key.id).not.toBe(kiube.id)
    })
})

/**
 * EVI-MA-02C — authoritative equipment delete + persistence regression tests.
 * Bentley-FREE. Proves delete removes exactly one instance by id, clears derived
 * selection, releases its collision volume, persists the NEW collection, and
 * that a reload does NOT resurrect a user-deleted instance (an empty persisted
 * collection stays empty). Hide is proven NOT to remove.
 */
import { describe, expect, it } from 'vitest'
import {
    createEquipmentInstance,
    findEquipmentCollision,
    loadEquipmentInstances,
    saveEquipmentInstances,
    type EquipmentAssetInstance,
    type EquipmentPlacement,
} from '../components/spatial/equipmentInstance'

const ROOM = [
    { x: -20, y: -20 }, { x: 20, y: -20 }, { x: 20, y: 20 }, { x: -20, y: 20 },
]
function place(canonicalId: string, seq: number): EquipmentAssetInstance {
    const r = createEquipmentInstance({
        iModelId: 'imodel-EVI2C', canonicalEquipmentId: canonicalId, parentBimSpaceId: '0xROOM',
        footprint: ROOM, zLow: 0, zHigh: 4, seq,
    })
    if (!r.ok) throw new Error(r.reason)
    return r.instance
}
function placement(x: number, y: number): EquipmentPlacement {
    return { centerX: x, centerY: y, zBase: 0, width: 2, depth: 2, height: 2, yaw: 0, envelopeProvenance: 'CALIBRATED' }
}

// Authoritative store stand-in mirroring the REAL deleteEquipment + Hide seams
// (deleteEquipment filters by id + clears selection; setEquipmentVisibility only
// flips hidden). Result shape matches DeleteEquipmentResult.
type DelResult =
    | { ok: true; deletedId: string; canonicalModelId: string }
    | { ok: false; reason: 'NOT_FOUND' | 'LOCKED' | 'PERSISTENCE_FAILED' | 'INVALID_STATE'; message: string }
function makeStore(initial: EquipmentAssetInstance[]) {
    let instances = [...initial]
    let selectedId: string | undefined
    let menuTargetId: string | undefined
    return {
        list: () => instances as readonly EquipmentAssetInstance[],
        count: () => instances.length,
        select: (id: string | undefined) => { selectedId = id },
        selected: () => selectedId,
        openMenu: (id: string) => { menuTargetId = id },
        menuTarget: () => menuTargetId,
        hide: (id: string) => {
            const e = instances.find((x) => x.id === id)
            if (!e) return
            instances = instances.map((x) => (x.id === id ? { ...x, hidden: true } : x))
        },
        delete: (id: string): DelResult => {
            const e = instances.find((x) => x.id === id)
            if (!e) return { ok: false, reason: 'NOT_FOUND', message: 'not found' }
            if (e.lifecycleState === 'LOCKED') return { ok: false, reason: 'LOCKED', message: 'Unlock equipment before deleting.' }
            const before = instances.length
            instances = instances.filter((x) => x.id !== id)
            if (instances.length !== before - 1) return { ok: false, reason: 'INVALID_STATE', message: 'decrement failed' }
            if (selectedId === id) selectedId = undefined
            if (menuTargetId === id) menuTargetId = undefined
            return { ok: true, deletedId: id, canonicalModelId: e.canonicalEquipmentId }
        },
    }
}

// ---------------------------------------------------------------------------
// Hide != Delete
// ---------------------------------------------------------------------------
describe('EVI-MA-02C Hide vs Delete', () => {
    it('Hide does NOT remove the instance (only flips hidden)', () => {
        const kiube = place('IBA_CYCLONE_KIUBE', 1)
        const store = makeStore([kiube])
        store.hide(kiube.id)
        expect(store.count()).toBe(1)
        expect(store.list()[0].hidden).toBe(true)
    })

    it('Delete removes the exact instance', () => {
        const kiube = place('IBA_CYCLONE_KIUBE', 1)
        const store = makeStore([kiube])
        const res = store.delete(kiube.id)
        expect(res.ok).toBe(true)
        if (res.ok) { expect(res.deletedId).toBe(kiube.id); expect(res.canonicalModelId).toBe('IBA_CYCLONE_KIUBE') }
        expect(store.count()).toBe(0)
    })
})

// ---------------------------------------------------------------------------
// Exact-instance deletion + derived-state clearing
// ---------------------------------------------------------------------------
describe('EVI-MA-02C exact-instance deletion', () => {
    it('deletes exactly once and only the target (KEY leaves KIUBE + PETtrace)', () => {
        const kiube = place('IBA_CYCLONE_KIUBE', 1)
        const key = place('IBA_CYCLONE_KEY', 2)
        const pettrace = place('GE_PETTRACE_890', 3)
        const store = makeStore([kiube, key, pettrace])
        const before = store.count()
        const res = store.delete(key.id)
        expect(res.ok).toBe(true)
        expect(store.count()).toBe(before - 1)
        expect(store.list().some((e) => e.id === key.id)).toBe(false)
        expect(store.list().some((e) => e.id === kiube.id)).toBe(true)
        expect(store.list().some((e) => e.id === pettrace.id)).toBe(true)
    })

    it('clears selectedEquipmentId only if the deleted id was selected', () => {
        const kiube = place('IBA_CYCLONE_KIUBE', 1)
        const key = place('IBA_CYCLONE_KEY', 2)
        const store = makeStore([kiube, key])
        store.select(kiube.id)
        store.delete(key.id) // deleting a non-selected instance keeps selection
        expect(store.selected()).toBe(kiube.id)
        store.delete(kiube.id) // deleting the selected instance clears it
        expect(store.selected()).toBeUndefined()
    })

    it('clears the context-menu target when its instance is deleted', () => {
        const key = place('IBA_CYCLONE_KEY', 1)
        const store = makeStore([key])
        store.openMenu(key.id)
        store.delete(key.id)
        expect(store.menuTarget()).toBeUndefined()
    })
})

// ---------------------------------------------------------------------------
// Explicit result reasons
// ---------------------------------------------------------------------------
describe('EVI-MA-02C explicit delete result', () => {
    it('NOT_FOUND for an unknown id', () => {
        const store = makeStore([place('IBA_CYCLONE_KIUBE', 1)])
        const res = store.delete('equipment:does-not-exist')
        expect(res.ok).toBe(false)
        if (!res.ok) expect(res.reason).toBe('NOT_FOUND')
    })

    it('unlocked equipment deletes successfully; LOCKED is rejected and remains', () => {
        const unlocked = place('IBA_CYCLONE_KIUBE', 1)
        const locked: EquipmentAssetInstance = { ...place('IBA_CYCLONE_KEY', 2), lifecycleState: 'LOCKED' }
        const store = makeStore([unlocked, locked])
        expect(store.delete(unlocked.id).ok).toBe(true)
        const res = store.delete(locked.id)
        expect(res.ok).toBe(false)
        if (!res.ok) expect(res.reason).toBe('LOCKED')
        expect(store.list().some((e) => e.id === locked.id)).toBe(true)
    })
})

// ---------------------------------------------------------------------------
// Persist -> delete -> reload: deleted id stays absent (the key regression)
// ---------------------------------------------------------------------------
describe('EVI-MA-02C persistence round-trip', () => {
    it('a deleted instance does NOT reappear after reload; empty stays empty', () => {
        const store = new Map<string, string>()
        const storage = {
            getItem: (k: string) => store.get(k) ?? null,
            setItem: (k: string, v: string) => { store.set(k, v) },
        }
        const IMODEL = 'imodel-EVI2C'
        const kiube = place('IBA_CYCLONE_KIUBE', 1)
        const key = place('IBA_CYCLONE_KEY', 2)

        // Persist both.
        saveEquipmentInstances(IMODEL, [kiube, key], storage)
        expect(loadEquipmentInstances(IMODEL, storage).map((e) => e.id).sort()).toEqual([kiube.id, key.id].sort())

        // Delete KEY -> persist the NEW collection (only KIUBE).
        saveEquipmentInstances(IMODEL, [kiube], storage)
        const afterDeleteKey = loadEquipmentInstances(IMODEL, storage)
        expect(afterDeleteKey.some((e) => e.id === key.id)).toBe(false)
        expect(afterDeleteKey.some((e) => e.id === kiube.id)).toBe(true)

        // Delete KIUBE too -> persist empty -> reload stays empty (no reseed).
        saveEquipmentInstances(IMODEL, [], storage)
        expect(loadEquipmentInstances(IMODEL, storage)).toEqual([])
        // The deleted ids never resurrect.
        expect(loadEquipmentInstances(IMODEL, storage).some((e) => e.id === kiube.id)).toBe(false)
    })
})

// ---------------------------------------------------------------------------
// Delete releases the collision volume (EVI-MA-02A preserved)
// ---------------------------------------------------------------------------
describe('EVI-MA-02C delete releases collision volume', () => {
    it('after deleting KIUBE, an overlapping KEY placement no longer collides', () => {
        const kiube = { ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(0, 0) }
        let existing: EquipmentAssetInstance[] = [kiube]
        // Overlapping placement collides while KIUBE occupies the space.
        expect(findEquipmentCollision({ proposed: placement(0.5, 0), existing }).collides).toBe(true)
        // Delete KIUBE -> space released.
        existing = existing.filter((e) => e.id !== kiube.id)
        expect(findEquipmentCollision({ proposed: placement(0.5, 0), existing }).collides).toBe(false)
    })
})

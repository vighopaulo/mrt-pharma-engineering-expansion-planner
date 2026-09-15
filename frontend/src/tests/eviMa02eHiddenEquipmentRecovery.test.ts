/**
 * EVI-MA-02E — hidden-equipment recovery (Hide must become Show). Bentley-FREE:
 * proves the authoritative `hidden` field drives the toggle, that Hide/Show keep
 * the same instance + pose, that hidden equipment persists and still reserves its
 * collision volume, and stays recoverable (in the collection + 2D marker).
 */
import { describe, expect, it } from 'vitest'
import {
    createEquipmentInstance,
    findEquipmentCollision,
    loadEquipmentInstances,
    saveEquipmentInstances,
    buildEquipmentEnvelope,
    type EquipmentAssetInstance,
    type EquipmentPlacement,
} from '../components/spatial/equipmentInstance'
import {
    projectBim2dPlan as project,
    hitTestPlanEquipment as hitEquip,
    type PlanEquipmentInput,
} from '../components/spatial/bim2dPlanProjection'

const ROOM = [
    { x: -20, y: -20 }, { x: 20, y: -20 }, { x: 20, y: 20 }, { x: -20, y: 20 },
]
function place(canonicalId: string, seq: number): EquipmentAssetInstance {
    const r = createEquipmentInstance({
        iModelId: 'imodel-EVI2E', canonicalEquipmentId: canonicalId, parentBimSpaceId: '0xROOM',
        footprint: ROOM, zLow: 0, zHigh: 4, seq,
    })
    if (!r.ok) throw new Error(r.reason)
    return r.instance
}
function placement(x: number, y: number): EquipmentPlacement {
    return { centerX: x, centerY: y, zBase: 0, width: 2, depth: 2, height: 2, yaw: 0, envelopeProvenance: 'CALIBRATED' }
}

// Store stand-in mirroring setEquipmentVisibility (only flips hidden; same id/pose).
function makeStore(initial: EquipmentAssetInstance[]) {
    let instances = [...initial]
    return {
        list: () => instances as readonly EquipmentAssetInstance[],
        get: (id: string) => instances.find((e) => e.id === id),
        setVisibility: (id: string, visible: boolean) => {
            instances = instances.map((e) => (e.id === id ? { ...e, hidden: !visible } : e))
        },
        // The floating-control / card button label derivation.
        labelFor: (id: string) => ((instances.find((e) => e.id === id)?.hidden ?? false) ? 'Show' : 'Hide'),
    }
}

// ---------------------------------------------------------------------------
// Hide/Show toggle label + state (A–F)
// ---------------------------------------------------------------------------
describe('EVI-MA-02E Hide/Show toggle', () => {
    it('A/B/C/D — visible shows Hide; hide flips hidden true + label Show; show flips back', () => {
        const kiube = place('IBA_CYCLONE_KIUBE', 1)
        const store = makeStore([kiube])
        expect(store.labelFor(kiube.id)).toBe('Hide') // visible -> Hide
        // Click Hide: setEquipmentVisibility(id, isHidden=false) -> visible=false.
        store.setVisibility(kiube.id, false)
        expect(store.get(kiube.id)!.hidden).toBe(true)
        expect(store.labelFor(kiube.id)).toBe('Show') // hidden -> Show
        // Click Show: setEquipmentVisibility(id, isHidden=true) -> visible=true.
        store.setVisibility(kiube.id, true)
        expect(store.get(kiube.id)!.hidden).toBe(false)
        expect(store.labelFor(kiube.id)).toBe('Hide')
    })

    it('E/F — same equipmentInstanceId + pose unchanged through Hide/Show', () => {
        const kiube = { ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(3, -4) }
        const store = makeStore([kiube])
        const idBefore = kiube.id
        const poseBefore = JSON.stringify(kiube.placement)
        store.setVisibility(kiube.id, false)
        store.setVisibility(kiube.id, true)
        const after = store.get(idBefore)!
        expect(after.id).toBe(idBefore)
        expect(JSON.stringify(after.placement)).toBe(poseBefore)
        expect(after.canonicalEquipmentId).toBe('IBA_CYCLONE_KIUBE')
    })
})

// ---------------------------------------------------------------------------
// Lock is orthogonal (G/H)
// ---------------------------------------------------------------------------
describe('EVI-MA-02E lock orthogonality', () => {
    it('G — a locked+hidden instance can be shown (lock never gates Show)', () => {
        const locked: EquipmentAssetInstance = { ...place('IBA_CYCLONE_KIUBE', 1), lifecycleState: 'LOCKED', hidden: true }
        const store = makeStore([locked])
        expect(store.labelFor(locked.id)).toBe('Show')
        store.setVisibility(locked.id, true) // Show works even while LOCKED
        expect(store.get(locked.id)!.hidden).toBe(false)
        expect(store.get(locked.id)!.lifecycleState).toBe('LOCKED') // still locked
    })

    it('H — a locked instance stays in the collection (delete policy unchanged; not deleted by hide/show)', () => {
        const locked: EquipmentAssetInstance = { ...place('IBA_CYCLONE_KIUBE', 1), lifecycleState: 'LOCKED' }
        const store = makeStore([locked])
        store.setVisibility(locked.id, false)
        store.setVisibility(locked.id, true)
        expect(store.list()).toHaveLength(1)
    })
})

// ---------------------------------------------------------------------------
// Hidden equipment stays in the collection + reserves collision (I/J)
// ---------------------------------------------------------------------------
describe('EVI-MA-02E hidden equipment still exists', () => {
    it('I — hidden instance remains in the authoritative collection', () => {
        const kiube = place('IBA_CYCLONE_KIUBE', 1)
        const store = makeStore([kiube])
        store.setVisibility(kiube.id, false)
        expect(store.list().some((e) => e.id === kiube.id)).toBe(true)
    })

    it('J — hidden equipment still reserves its collision volume (Hide != Delete)', () => {
        const kiube: EquipmentAssetInstance = { ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(0, 0), hidden: true }
        // A hidden instance is still in `existing` and still collides.
        const c = findEquipmentCollision({ proposed: placement(0.5, 0), existing: [kiube] })
        expect(c.collides).toBe(true)
        // Only deletion (removal from the collection) releases the space.
        const released = findEquipmentCollision({ proposed: placement(0.5, 0), existing: [] })
        expect(released.collides).toBe(false)
    })
})

// ---------------------------------------------------------------------------
// Persistence (K/L)
// ---------------------------------------------------------------------------
describe('EVI-MA-02E visibility persistence', () => {
    it('K/L — Hide persists hidden=true; Show persists hidden=false; same id throughout', () => {
        const store = new Map<string, string>()
        const storage = {
            getItem: (k: string) => store.get(k) ?? null,
            setItem: (k: string, v: string) => { store.set(k, v) },
        }
        const IMODEL = 'imodel-EVI2E'
        const kiube = place('IBA_CYCLONE_KIUBE', 1)

        saveEquipmentInstances(IMODEL, [{ ...kiube, hidden: true }], storage)
        let reloaded = loadEquipmentInstances(IMODEL, storage)
        expect(reloaded[0].id).toBe(kiube.id)
        expect(reloaded[0].hidden).toBe(true)

        saveEquipmentInstances(IMODEL, [{ ...kiube, hidden: false }], storage)
        reloaded = loadEquipmentInstances(IMODEL, storage)
        expect(reloaded[0].id).toBe(kiube.id)
        expect(reloaded[0].hidden).toBe(false)
    })
})

// ---------------------------------------------------------------------------
// 2D plan keeps a recoverable hidden marker (M/O)
// ---------------------------------------------------------------------------
describe('EVI-MA-02E 2D hidden marker recovery', () => {
    it('M/O — a hidden instance keeps a selectable 2D marker with the same id', () => {
        const kiube: EquipmentAssetInstance = { ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(0, 0), hidden: true }
        const equipment: PlanEquipmentInput[] = [{
            id: kiube.id,
            parentBimSpaceId: kiube.parentBimSpaceId,
            displayLabel: kiube.displayLabel,
            lifecycleState: kiube.lifecycleState,
            hidden: true,
            footprint: buildEquipmentEnvelope(kiube.placement).footprint,
        }]
        const view = project({ rooms: [], assignments: [], equipment })
        // Hidden equipment is STILL projected (subdued marker), retains id + hitTest.
        expect(view.equipment.some((e) => e.id === kiube.id && e.hidden)).toBe(true)
        expect(hitEquip(view, { x: 0, y: 0 })).toBe(kiube.id)
    })
})

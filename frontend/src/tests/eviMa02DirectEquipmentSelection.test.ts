/**
 * EVI-MA-02 — direct 3D equipment selection + context-menu deletion + duplicate
 * usability regression tests. Bentley-FREE: exercises the pure equipment
 * lifecycle (equipmentInstance), the 2D-plan equipment hit test, and the
 * pick-id -> stable-equipmentInstanceId resolution semantics the decorator uses
 * (a Map keyed by instance id; the transient pick id is never identity).
 */
import { describe, expect, it } from 'vitest'
import {
    createEquipmentInstance,
    buildEquipmentEnvelope,
    isSafeEquipmentPayload,
    toSafeEquipmentPayload,
    type EquipmentAssetInstance,
} from '../components/spatial/equipmentInstance'
import {
    projectBim2dPlan,
    hitTestPlanEquipment,
    type PlanEquipmentInput,
    type PlanRoomInput,
} from '../components/spatial/bim2dPlanProjection'

const ROOM_FOOTPRINT = [
    { x: -44, y: 26 }, { x: -36, y: 26 }, { x: -36, y: 34 }, { x: -44, y: 34 },
]

function make(canonicalId: string, seq: number, room = '0x2000000094e'): EquipmentAssetInstance {
    const r = createEquipmentInstance({
        iModelId: 'imodel-EVI2',
        canonicalEquipmentId: canonicalId,
        parentBimSpaceId: room,
        footprint: ROOM_FOOTPRINT,
        zLow: 8.4,
        zHigh: 12,
        seq,
    })
    if (!r.ok) throw new Error(`create failed: ${r.reason}`)
    return r.instance
}

// A tiny stand-in for the decorator's pick map (pickId -> equipmentInstanceId).
// Mirrors ClinicalProgramDecorator.equipmentPickIdToInstance semantics.
function buildPickMap(instances: readonly EquipmentAssetInstance[]): {
    resolve: (pickId: string) => string | undefined
    pickIdOf: (instanceId: string) => string
} {
    const forward = new Map<string, string>() // pickId -> instanceId
    const reverse = new Map<string, string>() // instanceId -> pickId
    let seq = 0
    for (const e of instances) {
        const pickId = `0xpick${(seq += 1)}`
        forward.set(pickId, e.id)
        reverse.set(e.id, pickId)
    }
    return {
        resolve: (pickId) => forward.get(pickId),
        pickIdOf: (instanceId) => reverse.get(instanceId)!,
    }
}

// A minimal authoritative equipment "store" mirroring the overlay's array +
// selectedEquipmentId + deleteEquipment semantics (single lifecycle).
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
        // Render derivation (what getEquipmentForRender maps) + 2D markers both
        // read the SAME array, so deletion removes ALL representations at once.
        renderIds: () => instances.filter((e) => !e.hidden).map((e) => e.id),
    }
}

// ---------------------------------------------------------------------------
// Pick-id resolves the stable EquipmentAssetInstance id
// ---------------------------------------------------------------------------
describe('EVI-MA-02 3D pick resolves stable instance id', () => {
    it('a pick id resolves to the exact equipmentInstanceId (not the model name)', () => {
        const kiube = make('IBA_CYCLONE_KIUBE', 1)
        const key = make('IBA_CYCLONE_KEY', 2)
        const pm = buildPickMap([kiube, key])
        expect(pm.resolve(pm.pickIdOf(kiube.id))).toBe(kiube.id)
        expect(pm.resolve(pm.pickIdOf(key.id))).toBe(key.id)
        // The two ids are distinct even though both are cyclotrons.
        expect(kiube.id).not.toBe(key.id)
    })

    it('a BIM / unknown pick id resolves to undefined (cannot invoke equipment delete)', () => {
        const kiube = make('IBA_CYCLONE_KIUBE', 1)
        const pm = buildPickMap([kiube])
        expect(pm.resolve('0xBIMwall1234')).toBeUndefined()
        expect(pm.resolve('')).toBeUndefined()
    })

    it('two IDENTICAL KIUBEs remain two distinct selectable instances/pick ids', () => {
        const a = make('IBA_CYCLONE_KIUBE', 1)
        const b = make('IBA_CYCLONE_KIUBE', 2)
        expect(a.id).not.toBe(b.id)
        const pm = buildPickMap([a, b])
        expect(pm.pickIdOf(a.id)).not.toBe(pm.pickIdOf(b.id))
        expect(pm.resolve(pm.pickIdOf(a.id))).toBe(a.id)
        expect(pm.resolve(pm.pickIdOf(b.id))).toBe(b.id)
    })
})

// ---------------------------------------------------------------------------
// Left-click / right-click selection targets the exact instance
// ---------------------------------------------------------------------------
describe('EVI-MA-02 selection targets the exact instance', () => {
    it('selecting a resolved pick id sets the exact selectedEquipmentId', () => {
        const kiube = make('IBA_CYCLONE_KIUBE', 1)
        const key = make('IBA_CYCLONE_KEY', 2)
        const store = makeStore([kiube, key])
        const pm = buildPickMap([kiube, key])
        // Left-click KEY -> resolve -> select KEY (not KIUBE).
        store.select(pm.resolve(pm.pickIdOf(key.id)))
        expect(store.selected()).toBe(key.id)
        expect(store.selected()).not.toBe(kiube.id)
    })
})

// ---------------------------------------------------------------------------
// Delete is real instance deletion; KEY != KIUBE; removes all representations
// ---------------------------------------------------------------------------
describe('EVI-MA-02 delete is authoritative instance deletion', () => {
    it('deleting KEY does not delete KIUBE, and removes KEY from render derivation', () => {
        const kiube = make('IBA_CYCLONE_KIUBE', 1)
        const key = make('IBA_CYCLONE_KEY', 2)
        const store = makeStore([kiube, key])
        store.select(key.id)
        const res = store.delete(key.id)
        expect(res.ok).toBe(true)
        expect(store.list().map((e) => e.id)).toEqual([kiube.id]) // KIUBE remains
        expect(store.renderIds()).toEqual([kiube.id]) // KEY gone from render (and 2D markers, cards read same array)
        expect(store.selected()).toBeUndefined() // stale selection cleared
    })

    it('deleting the SELECTED instance clears selectedEquipmentId (no stale id)', () => {
        const kiube = make('IBA_CYCLONE_KIUBE', 1)
        const store = makeStore([kiube])
        store.select(kiube.id)
        store.delete(kiube.id)
        expect(store.selected()).toBeUndefined()
        expect(store.renderIds()).toEqual([])
    })

    it('deleting a NON-selected instance leaves the other selection untouched', () => {
        const kiube = make('IBA_CYCLONE_KIUBE', 1)
        const key = make('IBA_CYCLONE_KEY', 2)
        const store = makeStore([kiube, key])
        store.select(kiube.id)
        store.delete(key.id)
        expect(store.selected()).toBe(kiube.id) // KIUBE selection untouched
    })
})

// ---------------------------------------------------------------------------
// Locked equipment is selectable; delete of locked is rejected honestly
// ---------------------------------------------------------------------------
describe('EVI-MA-02 locked equipment', () => {
    it('a LOCKED instance is still selectable (lock affects pose editing, not selection)', () => {
        const kiube: EquipmentAssetInstance = { ...make('IBA_CYCLONE_KIUBE', 1), lifecycleState: 'LOCKED' }
        const store = makeStore([kiube])
        store.select(kiube.id)
        expect(store.selected()).toBe(kiube.id)
        // Still rendered (lock is not invisibility).
        expect(store.renderIds()).toEqual([kiube.id])
    })

    it('deleting a LOCKED instance is rejected honestly (must unlock first)', () => {
        const kiube: EquipmentAssetInstance = { ...make('IBA_CYCLONE_KIUBE', 1), lifecycleState: 'LOCKED' }
        const store = makeStore([kiube])
        const res = store.delete(kiube.id)
        expect(res.ok).toBe(false)
        expect(res.reason).toBe('LOCKED')
        expect(store.renderIds()).toEqual([kiube.id]) // still present
    })
})

// ---------------------------------------------------------------------------
// 2D-plan marker click convergence (same instance id authority)
// ---------------------------------------------------------------------------
describe('EVI-MA-02 2D-plan marker convergence', () => {
    function planInputs(instances: EquipmentAssetInstance[]): { rooms: PlanRoomInput[]; equipment: PlanEquipmentInput[] } {
        const rooms: PlanRoomInput[] = [{
            bimSpaceId: '0x2000000094e',
            originalBimLabel: 'Radiopharmacy',
            exactOuterLoop: ROOM_FOOTPRINT,
        }]
        const equipment: PlanEquipmentInput[] = instances.map((e) => ({
            id: e.id,
            parentBimSpaceId: e.parentBimSpaceId,
            displayLabel: e.displayLabel,
            lifecycleState: e.lifecycleState,
            footprint: buildEquipmentEnvelope(e.placement).footprint,
        }))
        return { rooms, equipment }
    }

    it('clicking an equipment marker resolves the SAME equipmentInstanceId', () => {
        const kiube = make('IBA_CYCLONE_KIUBE', 1)
        const { rooms, equipment } = planInputs([kiube])
        const view = projectBim2dPlan({ rooms, assignments: [], equipment })
        // A point at the equipment center hits the equipment marker.
        const c = { x: kiube.placement.centerX, y: kiube.placement.centerY }
        // A marker-center click resolves to the exact equipment instance id.
        expect(hitTestPlanEquipment(view, c)).toBe(kiube.id)
        // A point far outside any equipment footprint does not resolve equipment.
        expect(hitTestPlanEquipment(view, { x: 1000, y: 1000 })).toBeUndefined()
    })
})

// ---------------------------------------------------------------------------
// Duplicate placement usability (detected, never merged/rejected)
// ---------------------------------------------------------------------------
describe('EVI-MA-02 duplicate placement usability', () => {
    it('two identical KIUBEs in one room persist as two distinct safe instances', () => {
        const a = make('IBA_CYCLONE_KIUBE', 1)
        const b = make('IBA_CYCLONE_KIUBE', 2)
        const payload = toSafeEquipmentPayload([a, b])
        expect(isSafeEquipmentPayload(payload)).toBe(true)
        expect(payload).toHaveLength(2)
        expect(payload[0].id).not.toBe(payload[1].id)
        // Both share the same canonical model (intentional duplicate, not merged).
        expect(payload[0].canonicalEquipmentId).toBe('IBA_CYCLONE_KIUBE')
        expect(payload[1].canonicalEquipmentId).toBe('IBA_CYCLONE_KIUBE')
    })
})

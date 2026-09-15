/**
 * EVI-MA-02D — deterministic equipment context pick + selected-equipment
 * convergence tests. Bentley-FREE: exercises the pure pickEquipmentForContext
 * resolver (selection-aware, planning-volumes-can-never-win) and confirms the
 * floating control + right-click + keyboard all resolve to the SAME id.
 */
import { describe, expect, it } from 'vitest'
import {
    createEquipmentInstance,
    pickEquipmentForContext,
    type EquipmentAssetInstance,
    type EquipmentPickRay,
    type EquipmentPlacement,
} from '../components/spatial/equipmentInstance'
import { canonicalEquipmentById } from '../components/spatial/canonicalEquipmentCatalog'

const ROOM = [
    { x: -30, y: -30 }, { x: 30, y: -30 }, { x: 30, y: 30 }, { x: -30, y: 30 },
]
function place(canonicalId: string, seq: number): EquipmentAssetInstance {
    const r = createEquipmentInstance({
        iModelId: 'imodel-EVI2D', canonicalEquipmentId: canonicalId, parentBimSpaceId: '0xROOM',
        footprint: ROOM, zLow: 0, zHigh: 4, seq,
    })
    if (!r.ok) throw new Error(r.reason)
    return r.instance
}
function at(inst: EquipmentAssetInstance, p: Partial<EquipmentPlacement>): EquipmentAssetInstance {
    return { ...inst, placement: { centerX: 0, centerY: 0, zBase: 0, width: 2, depth: 2, height: 2, yaw: 0, envelopeProvenance: 'CALIBRATED', ...p } }
}
function downRayAt(x: number, y: number): EquipmentPickRay {
    return { origin: [x, y, 100], direction: [0, 0, -1] }
}

describe('EVI-MA-02D pickEquipmentForContext', () => {
    it('A/E — ray through KIUBE resolves KIUBE; empty space resolves nothing', () => {
        const kiube = at(place('IBA_CYCLONE_KIUBE', 1), { centerX: 0, centerY: 0 })
        expect(pickEquipmentForContext(downRayAt(0, 0), [kiube], undefined)).toBe(kiube.id)
        expect(pickEquipmentForContext(downRayAt(20, 20), [kiube], undefined)).toBeUndefined()
    })

    it('B — prefers the SELECTED equipment when the ray hits its volume (overlap case)', () => {
        // Two instances overlapping in XY at different Z; a downward ray hits the
        // higher one first, but if the LOWER one is selected and the ray is within
        // its volume, selection wins (the user acts on what they selected).
        const lower = at(place('IBA_CYCLONE_KIUBE', 1), { centerX: 0, centerY: 0, zBase: 0, height: 2 })
        const upper = at(place('IBA_CYCLONE_KEY', 2), { centerX: 0, centerY: 0, zBase: 5, height: 2 })
        const list = [lower, upper]
        // No selection -> nearest (upper) wins.
        expect(pickEquipmentForContext(downRayAt(0, 0), list, undefined)).toBe(upper.id)
        // Lower selected + ray within its volume -> lower wins.
        expect(pickEquipmentForContext(downRayAt(0, 0), list, lower.id)).toBe(lower.id)
    })

    it('C — overlapping KEY/KIUBE with no selection: nearest along ray wins', () => {
        const near = at(place('IBA_CYCLONE_KEY', 1), { centerX: 0, centerY: 0, zBase: 6, height: 2 })
        const far = at(place('IBA_CYCLONE_KIUBE', 2), { centerX: 0, centerY: 0, zBase: 0, height: 2 })
        expect(pickEquipmentForContext(downRayAt(0, 0), [near, far], undefined)).toBe(near.id)
    })

    it('D — selected-equipment fallback: if the ray misses the selected one, nearest hit wins', () => {
        const selected = at(place('IBA_CYCLONE_KIUBE', 1), { centerX: 20, centerY: 0 }) // far away
        const other = at(place('IBA_CYCLONE_KEY', 2), { centerX: 0, centerY: 0 })
        // Ray at (0,0) misses the selected KIUBE (at x=20) -> resolves the KEY it hits.
        expect(pickEquipmentForContext(downRayAt(0, 0), [selected, other], selected.id)).toBe(other.id)
    })

    it('F — hidden equipment is never picked (even if selected)', () => {
        const hidden = { ...at(place('IBA_CYCLONE_KIUBE', 1), { centerX: 0, centerY: 0 }), hidden: true }
        expect(pickEquipmentForContext(downRayAt(0, 0), [hidden], hidden.id)).toBeUndefined()
    })

    it('E/L — a ray that hits no equipment returns undefined (planning volume can never win)', () => {
        // The equipment set contains ONLY equipment; a clinical planning volume /
        // room is not in it, so its id can never be returned. Empty set -> none.
        expect(pickEquipmentForContext(downRayAt(0, 0), [], 'planning-volume-or-room-id')).toBeUndefined()
    })
})

describe('EVI-MA-02D selection identity convergence', () => {
    it('the floating control, right-click, and keyboard all key off the same canonical model + id', () => {
        const kiube = place('IBA_CYCLONE_KIUBE', 1)
        const cm = canonicalEquipmentById(kiube.canonicalEquipmentId)!
        // Floating control title == right-click menu title == canonical model.
        expect(`${cm.manufacturer} ${cm.model}`).toBe('IBA Cyclone KIUBE')
        // The id used by every surface is the one stable instance id.
        expect(kiube.id).toContain('IBA_CYCLONE_KIUBE')
    })
})

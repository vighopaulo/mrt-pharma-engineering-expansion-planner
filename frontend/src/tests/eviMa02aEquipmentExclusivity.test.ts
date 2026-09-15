/**
 * EVI-MA-02A — equipment spatial exclusivity (no overlapping equipment) +
 * context-menu identity regression tests. Bentley-FREE: exercises the pure
 * oriented-volume collision test and the equipment lifecycle. The live
 * root-cause (tool not armed for cyclotron-only scenes) is a wiring fix proven
 * by manual acceptance; here we prove the collision doctrine deterministically.
 */
import { describe, expect, it } from 'vitest'
import {
    createEquipmentInstance,
    equipmentVolumesIntersect,
    findEquipmentCollision,
    rotateEquipment,
    translateEquipment,
    type EquipmentAssetInstance,
    type EquipmentPlacement,
} from '../components/spatial/equipmentInstance'
import { canonicalEquipmentById } from '../components/spatial/canonicalEquipmentCatalog'

// A large room footprint so placement is contained; collisions are equipment-vs-
// equipment, not room containment.
const ROOM = [
    { x: -20, y: -20 }, { x: 20, y: -20 }, { x: 20, y: 20 }, { x: -20, y: 20 },
]

function place(canonicalId: string, seq: number): EquipmentAssetInstance {
    const r = createEquipmentInstance({
        iModelId: 'imodel-EVI2A',
        canonicalEquipmentId: canonicalId,
        parentBimSpaceId: '0xROOM',
        footprint: ROOM,
        zLow: 0,
        zHigh: 4,
        seq,
    })
    if (!r.ok) throw new Error(`create failed: ${r.reason}`)
    return r.instance
}

/** A placement centered at (x,y), floor z=0, given extents + yaw (radians). */
function placement(x: number, y: number, w = 2, d = 2, h = 2, yaw = 0): EquipmentPlacement {
    return { centerX: x, centerY: y, zBase: 0, width: w, depth: d, height: h, yaw, envelopeProvenance: 'CALIBRATED' }
}

// ---------------------------------------------------------------------------
// Pure oriented-volume intersection
// ---------------------------------------------------------------------------
describe('EVI-MA-02A oriented equipment-volume intersection', () => {
    it('identical placements intersect', () => {
        expect(equipmentVolumesIntersect(placement(0, 0), placement(0, 0))).toBe(true)
    })

    it('clearly separated placements do NOT intersect', () => {
        expect(equipmentVolumesIntersect(placement(0, 0), placement(10, 0))).toBe(false)
    })

    it('overlapping placements intersect (partial XY overlap, shared Z)', () => {
        expect(equipmentVolumesIntersect(placement(0, 0, 2, 2), placement(1.5, 0, 2, 2))).toBe(true)
    })

    it('flush side-by-side (touching within tolerance) does NOT intersect', () => {
        // Two 2x2 boxes centered 2.0 apart touch exactly at the shared face.
        expect(equipmentVolumesIntersect(placement(0, 0, 2, 2), placement(2, 0, 2, 2))).toBe(false)
    })

    it('vertically separated placements (disjoint Z) do NOT intersect even if XY overlaps', () => {
        const a = placement(0, 0, 2, 2, 2) // z 0..2
        const b: EquipmentPlacement = { ...placement(0, 0, 2, 2, 2), zBase: 3 } // z 3..5
        expect(equipmentVolumesIntersect(a, b)).toBe(false)
    })

    it('rotation is respected: a yawed box overlaps where an axis-aligned test might not', () => {
        // A long thin box rotated 45deg sweeps into a neighbor its AABB-at-yaw-0
        // would still overlap; prove the yawed footprint drives the result.
        const a = placement(0, 0, 6, 1, 2, 0)
        const b = placement(0, 2.2, 6, 1, 2, Math.PI / 2) // rotated into A's column
        expect(equipmentVolumesIntersect(a, b)).toBe(true)
        // Same b without rotation clears A.
        const bFlat = placement(0, 2.2, 6, 1, 2, 0)
        expect(equipmentVolumesIntersect(a, bFlat)).toBe(false)
    })
})

// ---------------------------------------------------------------------------
// findEquipmentCollision — first conflict, self-exclusion, locked reserves
// ---------------------------------------------------------------------------
describe('EVI-MA-02A findEquipmentCollision', () => {
    it('reports the first conflicting instance (with id + canonical id)', () => {
        const a = { ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(0, 0) }
        const c = findEquipmentCollision({ proposed: placement(0.5, 0), existing: [a] })
        expect(c.collides).toBe(true)
        expect(c.conflictId).toBe(a.id)
        expect(c.conflictCanonicalId).toBe('IBA_CYCLONE_KIUBE')
    })

    it('excludeId lets an instance move without colliding with itself', () => {
        const a = { ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(0, 0) }
        const c = findEquipmentCollision({ proposed: placement(0, 0), existing: [a], excludeId: a.id })
        expect(c.collides).toBe(false)
    })

    it('LOCKED equipment still reserves its volume (collision detected)', () => {
        const a: EquipmentAssetInstance = { ...place('IBA_CYCLONE_KIUBE', 1), placement: placement(0, 0), lifecycleState: 'LOCKED' }
        const c = findEquipmentCollision({ proposed: placement(0.5, 0), existing: [a] })
        expect(c.collides).toBe(true)
    })
})

// ---------------------------------------------------------------------------
// §12F A–F collision scenarios (simulated authoritative store)
// ---------------------------------------------------------------------------
function makeStore() {
    let instances: EquipmentAssetInstance[] = []
    let seq = 0
    return {
        list: () => instances as readonly EquipmentAssetInstance[],
        count: () => instances.length,
        // Mirror placeEquipmentInParent: create -> collision check -> reject or add.
        place: (canonicalId: string, p: EquipmentPlacement): { ok: boolean; reason?: string; id?: string } => {
            const inst = { ...place(canonicalId, (seq += 1)), placement: p }
            const c = findEquipmentCollision({ proposed: p, existing: instances })
            if (c.collides) return { ok: false, reason: 'EQUIPMENT_COLLISION' }
            instances = [...instances, inst]
            return { ok: true, id: inst.id }
        },
        delete: (id: string) => { instances = instances.filter((x) => x.id !== id) },
        // Mirror updateEquipmentPlacement collision gate.
        move: (id: string, p: EquipmentPlacement): { ok: boolean; reason?: string } => {
            const c = findEquipmentCollision({ proposed: p, existing: instances, excludeId: id })
            if (c.collides) return { ok: false, reason: 'EQUIPMENT_COLLISION' }
            instances = instances.map((e) => (e.id === id ? { ...e, placement: p } : e))
            return { ok: true }
        },
    }
}

describe('EVI-MA-02A §12F collision scenarios', () => {
    it('A — first instance wins; overlapping second is rejected, nothing created', () => {
        const s = makeStore()
        expect(s.place('IBA_CYCLONE_KIUBE', placement(0, 0)).ok).toBe(true)
        const b = s.place('IBA_CYCLONE_KEY', placement(0.5, 0))
        expect(b.ok).toBe(false)
        expect(b.reason).toBe('EQUIPMENT_COLLISION')
        expect(s.count()).toBe(1) // no B created
    })

    it('B — delete A then the same B placement succeeds (space released)', () => {
        const s = makeStore()
        const a = s.place('IBA_CYCLONE_KIUBE', placement(0, 0))
        expect(s.place('IBA_CYCLONE_KEY', placement(0.5, 0)).ok).toBe(false)
        s.delete(a.id!)
        expect(s.place('IBA_CYCLONE_KEY', placement(0.5, 0)).ok).toBe(true)
        expect(s.count()).toBe(1)
    })

    it('C — same-model duplicate overlap rejected; a moved-clear duplicate succeeds with a distinct id', () => {
        const s = makeStore()
        const a = s.place('IBA_CYCLONE_KIUBE', placement(0, 0))
        expect(s.place('IBA_CYCLONE_KIUBE', placement(0.5, 0)).ok).toBe(false)
        const b = s.place('IBA_CYCLONE_KIUBE', placement(8, 0)) // clear space
        expect(b.ok).toBe(true)
        expect(a.id).not.toBe(b.id)
    })

    it('D — rotated proposal that intersects is rejected', () => {
        const s = makeStore()
        s.place('IBA_CYCLONE_KIUBE', placement(0, 0, 6, 1))
        const b = s.place('IBA_CYCLONE_KEY', placement(0, 2.2, 6, 1, 2, Math.PI / 2))
        expect(b.ok).toBe(false)
    })

    it('E — non-overlapping A and B both succeed with distinct ids', () => {
        const s = makeStore()
        const a = s.place('IBA_CYCLONE_KIUBE', placement(-8, 0))
        const b = s.place('IBA_CYCLONE_KEY', placement(8, 0))
        expect(a.ok && b.ok).toBe(true)
        expect(a.id).not.toBe(b.id)
        expect(s.count()).toBe(2)
    })

    it('F — locked A blocks an overlapping B (A unchanged)', () => {
        const s = makeStore()
        const a = s.place('IBA_CYCLONE_KIUBE', placement(0, 0))
        // Lock A in the store.
        ;(s.list().find((e) => e.id === a.id) as EquipmentAssetInstance).lifecycleState = 'LOCKED'
        const b = s.place('IBA_CYCLONE_KEY', placement(0.5, 0))
        expect(b.ok).toBe(false)
        expect(s.count()).toBe(1)
    })

    it('move that would overlap another instance is rejected; a clear move succeeds', () => {
        const s = makeStore()
        const a = s.place('IBA_CYCLONE_KIUBE', placement(-8, 0))
        s.place('IBA_CYCLONE_KEY', placement(8, 0))
        // Move A on top of B -> rejected.
        expect(s.move(a.id!, placement(8, 0)).ok).toBe(false)
        // Move A to clear space -> ok.
        expect(s.move(a.id!, placement(0, 0)).ok).toBe(true)
    })
})

// ---------------------------------------------------------------------------
// Context-menu title = exact canonical model
// ---------------------------------------------------------------------------
describe('EVI-MA-02A context-menu title identity', () => {
    it('resolves the exact canonical manufacturer + model for the title', () => {
        const kiube = place('IBA_CYCLONE_KIUBE', 1)
        const cm = canonicalEquipmentById(kiube.canonicalEquipmentId)!
        expect(`${cm.manufacturer} ${cm.model}`).toBe('IBA Cyclone KIUBE')
        const key = place('IBA_CYCLONE_KEY', 2)
        const cmk = canonicalEquipmentById(key.canonicalEquipmentId)!
        expect(`${cmk.manufacturer} ${cmk.model}`).toBe('IBA Cyclone KEY')
    })
})

// ---------------------------------------------------------------------------
// translate/rotate helpers remain pure (used by the collision-gated movers)
// ---------------------------------------------------------------------------
describe('EVI-MA-02A pose helpers', () => {
    it('translateEquipment/rotateEquipment produce the expected next placement', () => {
        const p = placement(0, 0)
        expect(translateEquipment(p, 3, -2).centerX).toBe(3)
        expect(translateEquipment(p, 3, -2).centerY).toBe(-2)
        expect(rotateEquipment(p, Math.PI / 2).yaw).toBeCloseTo(Math.PI / 2, 9)
    })
})

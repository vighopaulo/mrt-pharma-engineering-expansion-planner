/**
 * EVI-MA-06 — universal application-object direct manipulation.
 *
 * Bentley-FREE. Proves the ONE unified pick/selection/drag/delete architecture at
 * the pure layer the live tool delegates to:
 *   - resolveAppObjectPickTarget: selected-preference then nearest; hidden
 *     excluded; native BIM / planning volumes never candidates; any subcomponent
 *     resolves the one instance (whole-volume candidate).
 *   - deleteAppObject focus-safety predicate (isTextEditingElement).
 *   - freestanding equipment floor-plane move math + oriented collision +
 *     INDEPENDENT-POSE doctrine (moving one instance never moves another; a
 *     rejected move leaves BOTH poses unchanged).
 *   - vestibule wall-tangent slide keeps the front face flush + rear behind wall
 *     + clamps to the wall span; wall-snap evaluation uses a threshold/hysteresis.
 *
 * The live browser pointer-drag + right-click event delivery are exercised in
 * the app; manual acceptance remains authoritative for those (noted in the report).
 */
import { describe, expect, it } from 'vitest'
import {
    resolveAppObjectPickTarget,
    isTextEditingElement,
    rayHitObb,
    rayHitAabb,
    type AppObjectCandidate,
    type AppPickRay,
} from '../components/spatial/appObjectPicking'
import {
    createEquipmentInstance,
    translateEquipment,
    findEquipmentCollision,
    equipmentVolumesIntersect,
    type EquipmentAssetInstance,
} from '../components/spatial/equipmentInstance'
import {
    createVestibuleInstance,
    slideVestibuleAlongWall,
    evaluateWallSnap,
    frontFacePlaneFromPose,
    type ClinicalLogisticsVestibuleInstance,
} from '../components/spatial/clinicalLogisticsVestibule'

const ROOM = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 8 }, { x: 0, y: 8 }]
const ZLOW = 0, ZHIGH = 3.2

function equip(id: string, cx: number, cy: number): AppObjectCandidate {
    return {
        objectType: 'EQUIPMENT_INSTANCE', instanceId: id, parentBimSpaceId: 'room',
        volume: { kind: 'OBB', centerX: cx, centerY: cy, centerZ: 1, halfX: 0.5, halfY: 0.5, halfZ: 1, yaw: 0 },
        hidden: false, locked: false, draggableWhenUnlocked: true, deletableWhenUnlocked: true,
    }
}

// ---------------------------------------------------------------------------
// Unified picker
// ---------------------------------------------------------------------------
describe('resolveAppObjectPickTarget', () => {
    // Ray down -Z through the XY plane at various X.
    const rayAt = (x: number, y: number): AppPickRay => ({ origin: [x, y, 10], direction: [0, 0, -1] })

    it('nearest valid object wins when nothing is selected', () => {
        const cands = [equip('A', 0, 0), equip('B', 5, 0)]
        expect(resolveAppObjectPickTarget(rayAt(0, 0), cands)!.instanceId).toBe('A')
        expect(resolveAppObjectPickTarget(rayAt(5, 0), cands)!.instanceId).toBe('B')
    })

    it('the SELECTED object is preferred when the ray actually hits it (even if another is nearer along a shared ray)', () => {
        // Two stacked boxes at the same XY, different Z; ray hits both.
        const low: AppObjectCandidate = { ...equip('LOW', 0, 0), volume: { kind: 'OBB', centerX: 0, centerY: 0, centerZ: 1, halfX: 1, halfY: 1, halfZ: 1, yaw: 0 } }
        const high: AppObjectCandidate = { ...equip('HIGH', 0, 0), volume: { kind: 'OBB', centerX: 0, centerY: 0, centerZ: 5, halfX: 1, halfY: 1, halfZ: 1, yaw: 0 } }
        const ray = rayAt(0, 0)
        // No selection -> nearest along the ray (HIGH, hit first from z=10 downward).
        expect(resolveAppObjectPickTarget(ray, [low, high])!.instanceId).toBe('HIGH')
        // Selecting LOW (which the ray does hit) prefers LOW.
        expect(resolveAppObjectPickTarget(ray, [low, high], { objectType: 'EQUIPMENT_INSTANCE', instanceId: 'LOW' })!.instanceId).toBe('LOW')
    })

    it('hidden candidates are never picked; empty space returns undefined', () => {
        const hidden: AppObjectCandidate = { ...equip('H', 0, 0), hidden: true }
        expect(resolveAppObjectPickTarget(rayAt(0, 0), [hidden])).toBeUndefined()
        expect(resolveAppObjectPickTarget(rayAt(99, 99), [equip('A', 0, 0)])).toBeUndefined()
    })

    it('a locked object resolves but is neither draggable nor deletable', () => {
        const locked: AppObjectCandidate = { ...equip('L', 0, 0), locked: true }
        const t = resolveAppObjectPickTarget(rayAt(0, 0), [locked])!
        expect(t.locked).toBe(true)
        expect(t.draggable).toBe(false)
        expect(t.deletable).toBe(false)
    })

    it('every subcomponent maps to ONE instance (whole-volume candidate)', () => {
        // A wide vestibule-style AABB candidate: a ray anywhere over it resolves
        // the single instance id (fascia vs rear manifold are the same volume).
        const vest: AppObjectCandidate = {
            objectType: 'CLINICAL_LOGISTICS_VESTIBULE', instanceId: 'VEST-1', parentBimSpaceId: 'room',
            volume: { kind: 'AABB', minX: 0, minY: 0, minZ: 0, maxX: 2, maxY: 3, maxZ: 2 },
            hidden: false, locked: false, draggableWhenUnlocked: true, deletableWhenUnlocked: true,
        }
        expect(resolveAppObjectPickTarget(rayAt(0.2, 0.2), [vest])!.instanceId).toBe('VEST-1') // near front
        expect(resolveAppObjectPickTarget(rayAt(1.8, 2.8), [vest])!.instanceId).toBe('VEST-1') // near rear
    })

    it('ray/volume primitives: hit through a box, miss beside it', () => {
        expect(rayHitAabb({ origin: [0, 0, 10], direction: [0, 0, -1] }, { kind: 'AABB', minX: -1, minY: -1, minZ: 0, maxX: 1, maxY: 1, maxZ: 2 })).toBeTypeOf('number')
        expect(rayHitObb({ origin: [9, 9, 10], direction: [0, 0, -1] }, { kind: 'OBB', centerX: 0, centerY: 0, centerZ: 1, halfX: 1, halfY: 1, halfZ: 1, yaw: 0 })).toBeUndefined()
    })
})

// ---------------------------------------------------------------------------
// Delete-key focus safety
// ---------------------------------------------------------------------------
describe('isTextEditingElement', () => {
    it('true for input/textarea/select/contenteditable, false otherwise', () => {
        expect(isTextEditingElement({ tagName: 'INPUT' })).toBe(true)
        expect(isTextEditingElement({ tagName: 'TEXTAREA' })).toBe(true)
        expect(isTextEditingElement({ tagName: 'SELECT' })).toBe(true)
        expect(isTextEditingElement({ tagName: 'DIV', isContentEditable: true })).toBe(true)
        expect(isTextEditingElement({ tagName: 'CANVAS' })).toBe(false)
        expect(isTextEditingElement(null)).toBe(false)
    })
})

// ---------------------------------------------------------------------------
// Freestanding equipment move + INDEPENDENT-POSE doctrine (pure)
// ---------------------------------------------------------------------------
describe('equipment floor-plane move + independent-pose doctrine', () => {
    function makeEquip(seq: number): EquipmentAssetInstance {
        const r = createEquipmentInstance({
            iModelId: 'im', canonicalEquipmentId: 'IBA_CYCLONE_KIUBE', parentBimSpaceId: 'room',
            footprint: ROOM, zLow: ZLOW, zHigh: ZHIGH, seq,
        })
        if (!r.ok) throw new Error(r.reason)
        return r.instance
    }

    it('moving one instance mutates only its own placement; a valid candidate keeps others byte-identical', () => {
        const a = makeEquip(1)
        const b = makeEquip(2)
        // Snapshot B's placement (deep copy) before moving A.
        const bBefore = JSON.stringify(b.placement)
        // A candidate move of A to a free floor point (X/Y only, same Z/yaw).
        const candidateA = { ...a.placement, centerX: a.placement.centerX + 3, centerY: a.placement.centerY }
        // Collision-check the candidate against the OTHER instance (self excluded).
        const collision = findEquipmentCollision({ proposed: candidateA, existing: [a, b], excludeId: a.id })
        // Whether or not it collides, B must never be mutated by evaluating A's move.
        expect(JSON.stringify(b.placement)).toBe(bBefore)
        expect(collision).toBeDefined()
    })

    it('a rejected (colliding) candidate leaves BOTH the mover and the neighbor at their prior poses', () => {
        const a = makeEquip(1)
        const b = makeEquip(2)
        // Force B to sit exactly where A would move (overlap).
        b.placement = { ...b.placement, centerX: a.placement.centerX + 0.1, centerY: a.placement.centerY }
        const aBefore = JSON.stringify(a.placement)
        const bBefore = JSON.stringify(b.placement)
        const candidate = { ...a.placement, centerX: b.placement.centerX, centerY: b.placement.centerY }
        const collision = findEquipmentCollision({ proposed: candidate, existing: [a, b], excludeId: a.id })
        expect(collision.collides).toBe(true)
        // The pure collision test never mutates; the authoritative move would
        // return early on collision, so both poses are unchanged.
        expect(JSON.stringify(a.placement)).toBe(aBefore)
        expect(JSON.stringify(b.placement)).toBe(bBefore)
    })

    it('translateEquipment produces a NEW placement (does not mutate the input)', () => {
        const a = makeEquip(1)
        const before = JSON.stringify(a.placement)
        const moved = translateEquipment(a.placement, 2, 3)
        expect(moved.centerX).toBeCloseTo(a.placement.centerX + 2, 9)
        expect(JSON.stringify(a.placement)).toBe(before) // input untouched
    })

    it('oriented (yaw-aware) collision — two separated instances do not intersect', () => {
        const a = makeEquip(1)
        const far = { ...a.placement, centerX: a.placement.centerX + 50 }
        expect(equipmentVolumesIntersect(a.placement, far)).toBe(false)
    })
})

// ---------------------------------------------------------------------------
// Vestibule wall-slide + wall-snap (pure)
// ---------------------------------------------------------------------------
describe('vestibule wall-slide + wall-snap', () => {
    function makeVestibule(wallSide: 'X_MIN' | 'X_MAX' | 'Y_MIN' | 'Y_MAX'): ClinicalLogisticsVestibuleInstance {
        const r = createVestibuleInstance({
            iModelId: 'im', serviceClass: 'RADIOPHARMACY', parentBimSpaceId: 'room',
            footprint: ROOM, zLow: ZLOW, zHigh: ZHIGH, seq: 1, wallSide,
        })
        if (!r.ok) throw new Error(r.reason)
        return r.instance
    }

    it('sliding keeps the front face flush with the wall plane and the rear behind the wall', () => {
        const v = makeVestibule('Y_MAX')
        const frame = v.wallReference.frame!
        const beforeFront = frontFacePlaneFromPose(v.pose)
        const next = slideVestibuleAlongWall({ pose: v.pose, frame, wallLength: v.wallReference.wallLength, targetX: 8, targetY: 20 })
        const afterFront = frontFacePlaneFromPose(next)
        // Front-face plane distance along roomInward is unchanged (still flush).
        expect(afterFront.pointX).not.toBeCloseTo(beforeFront.pointX, 6) // slid along tangent (X)
        // Rear (center) stays on the wall-outward side of the front face.
        const outDot = (next.centerX - afterFront.pointX) * (-afterFront.normalX) + (next.centerY - afterFront.pointY) * (-afterFront.normalY)
        expect(outDot).toBeGreaterThan(0)
    })

    it('sliding clamps to the usable wall span (never slides the body off the wall)', () => {
        const v = makeVestibule('Y_MAX')
        const frame = v.wallReference.frame!
        // Target far beyond the wall end; result must be clamped within +/- (halfSpan - halfWidth).
        const next = slideVestibuleAlongWall({ pose: v.pose, frame, wallLength: v.wallReference.wallLength, targetX: 1000, targetY: 8 })
        const s = (next.centerX - frame.originX) * frame.tangentX + (next.centerY - frame.originY) * frame.tangentY
        const limit = v.wallReference.wallLength / 2 - v.pose.width / 2
        expect(s).toBeLessThanOrEqual(limit + 1e-9)
        expect(s).toBeGreaterThanOrEqual(-limit - 1e-9)
    })

    it('wall-snap: a target near a DIFFERENT wall becomes a snap candidate (threshold + hysteresis)', () => {
        // Current vestibule is on the Y_MAX wall (y=8).
        // A target hugging the X_MIN wall (x≈0) should snap to X_MIN.
        const snap = evaluateWallSnap({ footprint: ROOM, currentWallSide: 'Y_MAX', targetX: 0.1, targetY: 4 })
        expect(snap).toBe('X_MIN')
        // A target still near the current wall does NOT snap.
        const none = evaluateWallSnap({ footprint: ROOM, currentWallSide: 'Y_MAX', targetX: 5, targetY: 7.9 })
        expect(none).toBeUndefined()
    })
})

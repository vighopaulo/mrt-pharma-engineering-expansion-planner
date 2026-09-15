/**
 * EVI-MA-05B — wall-integrated vestibule placement correction + universal 3D
 * right-click resolution.
 *
 * Bentley-FREE. Proves (Defect A) the vestibule is truly WALL-INTEGRATED — its
 * front access face is flush with the room-side wall plane, only a shallow
 * room-side depth projects into the room, and the sleeve/manifold/MRT/PTS all
 * extend BEHIND the wall along wallOutwardNormal — while preserving the
 * EVI-MA-05A hollow-passage + port semantics; and (Defect B) that a context
 * pick resolves the ONE vestibuleInstanceId from ANY visible component, with
 * selection-preference / nearest / hidden-excluded semantics, and that native
 * BIM never resolves to an app-owned target.
 */
import { describe, expect, it } from 'vitest'
import {
    createVestibuleInstance,
    seedWallIntegratedPose,
    wallFrameForSide,
    frontFacePlaneFromPose,
    reservedVolumeFromPose,
    fullOccupiedVolumeFromPose,
    findVestibuleCollision,
    reservedVolumeAsAabb,
    pickVestibuleForContext,
    rayIntersectAabb,
    permittedPortsForServiceClass,
    type ClinicalLogisticsVestibuleInstance,
    type VestibulePose,
} from '../components/spatial/clinicalLogisticsVestibule'

// 6x5 cyclotron room, floor 0..3.2. Longest walls span X (Y_MIN / Y_MAX).
const ROOM = [{ x: 0, y: 0 }, { x: 6, y: 0 }, { x: 6, y: 5 }, { x: 0, y: 5 }]
const ZLOW = 0, ZHIGH = 3.2
const CYCLO_ROOM = '0x2000000094e'

function radiopharmacy(seq = 1): ClinicalLogisticsVestibuleInstance {
    const res = createVestibuleInstance({
        iModelId: 'imodel-05B', serviceClass: 'RADIOPHARMACY', parentBimSpaceId: CYCLO_ROOM,
        sourceClinicalContextId: 'cyclotron-1', footprint: ROOM, zLow: ZLOW, zHigh: ZHIGH, seq,
    })
    if (!res.ok) throw new Error(res.reason)
    return res.instance
}

// ---------------------------------------------------------------------------
// Defect A — wall-integrated placement
// ---------------------------------------------------------------------------
describe('EVI-MA-05B wall-integrated placement', () => {
    it('derives an explicit wall frame with roomInward = -wallOutward', () => {
        const f = wallFrameForSide(ROOM, 'Y_MAX')!
        expect(f.roomInwardX).toBeCloseTo(-f.wallOutwardX, 9)
        expect(f.roomInwardY).toBeCloseTo(-f.wallOutwardY, 9)
        // Y_MAX wall: room interior is toward -Y; behind-wall is +Y.
        expect(f.roomInwardY).toBeLessThan(0)
        expect(f.wallOutwardY).toBeGreaterThan(0)
    })

    it('B/C: the front face is flush with the selected wall plane and its normal points into the room', () => {
        const pose = seedWallIntegratedPose({ footprint: ROOM, zLow: ZLOW, zHigh: ZHIGH, wallSide: 'Y_MAX' })!
        const front = frontFacePlaneFromPose(pose)
        // Y_MAX wall plane is y = 5; the front face lands on it (flush).
        expect(front.pointY).toBeCloseTo(5, 6)
        // Normal points into the room (-Y).
        expect(front.normalY).toBeLessThan(0)
    })

    it('D: the body extends behind the wall (pose center is on the wall-outward side of the wall plane)', () => {
        const pose = seedWallIntegratedPose({ footprint: ROOM, zLow: ZLOW, zHigh: ZHIGH, wallSide: 'Y_MAX' })!
        // Center sits behind the wall (y > 5) so the assembly is not freestanding
        // in the room — this is the Defect A correction.
        expect(pose.centerY).toBeGreaterThan(5)
    })

    it('E: the room-side reserved (collision) volume is a SHALLOW slab, not the full assembly depth', () => {
        const pose = seedWallIntegratedPose({ footprint: ROOM, zLow: ZLOW, zHigh: ZHIGH, wallSide: 'Y_MAX' })!
        const roomSide = reservedVolumeFromPose(pose)
        const full = fullOccupiedVolumeFromPose(pose)
        const roomSideDepth = roomSide.maxY - roomSide.minY
        const fullDepth = full.maxY - full.minY
        expect(roomSideDepth).toBeLessThan(fullDepth)
        expect(roomSideDepth).toBeLessThanOrEqual(0.5) // shallow room-side projection
    })

    it('F..J: the behind-wall port stubs lie on the wall-outward side of the front face', () => {
        const v = radiopharmacy()
        const front = frontFacePlaneFromPose(v.pose)
        // wallOutward = -roomInward = -frontNormal. A port is behind the wall when
        // (port - frontFace) · wallOutward > 0, for whichever wall was chosen.
        const outX = -front.normalX, outY = -front.normalY
        for (const p of v.transportPorts) {
            if (!p.fabricated) continue
            const dot = (p.position.x - front.pointX) * outX + (p.position.y - front.pointY) * outY
            expect(dot).toBeGreaterThan(0)
        }
    })

    it('X: an intended wall penetration is NOT a room-side collision, but a real room overlap IS', () => {
        const v = radiopharmacy()
        // Equipment far inside the room (near centroid) does NOT overlap the
        // shallow room-side access slab that hugs the wall.
        const interior = { id: 'cyclotron-1', aabb: { minX: 2.5, minY: 2, minZ: 0, maxX: 3.5, maxY: 3, maxZ: 2 } }
        expect(findVestibuleCollision(v.reservedVolume, [interior])).toBeUndefined()
        // Equipment right at the access slab DOES overlap.
        const atFace = { id: 'blocker', aabb: reservedVolumeAsAabb(v.reservedVolume) }
        expect(findVestibuleCollision(v.reservedVolume, [atFace])).toBe('blocker')
    })

    it('Z/Y: wall relationship stays PROPOSED_WALL_PENETRATION and the frame persists on the instance', () => {
        const v = radiopharmacy()
        expect(v.wallRelationshipStatus).toBe('PROPOSED_WALL_PENETRATION')
        expect(v.wallReference.frame).toBeDefined()
        expect(v.wallReference.frame!.roomInwardY).toBeCloseTo(-v.wallReference.frame!.wallOutwardY, 9)
    })

    it('AC: create -> reload reconstructs the same wall-integrated pose (front face still flush)', () => {
        const v = radiopharmacy()
        // Re-seed from the persisted wall side + footprint; identical pose.
        const reseed = seedWallIntegratedPose({ footprint: ROOM, zLow: ZLOW, zHigh: ZHIGH, wallSide: v.wallReference.wallSide })!
        expect(reseed.centerX).toBeCloseTo(v.pose.centerX, 9)
        expect(reseed.centerY).toBeCloseTo(v.pose.centerY, 9)
        expect(reseed.yaw).toBeCloseTo(v.pose.yaw, 9)
    })

    it('AE: EVI-MA-05A port semantics unchanged (MRT + radiopharm-qualified PTS still fabricated)', () => {
        const ports = permittedPortsForServiceClass('RADIOPHARMACY')
        expect(ports.find((p) => p.transportFamily === 'MRT')!.fabricatedThisBuild).toBe(true)
        expect(ports.find((p) => p.transportFamily === 'PTS')!.ptsQualification).toBe('RADIOPHARMACEUTICAL_QUALIFIED')
    })
})

// ---------------------------------------------------------------------------
// Defect B — universal right-click / context pick resolution
// ---------------------------------------------------------------------------
describe('EVI-MA-05B universal context pick', () => {
    const v = radiopharmacy()
    // A ray from the room interior aimed at the vestibule, along the direction
    // OPPOSITE the front-face normal (i.e. from inside the room toward/through
    // the wall), regardless of which wall the placement chose. It passes through
    // the full occupied volume.
    const front = frontFacePlaneFromPose(v.pose)
    const zMid = v.pose.zBase + v.pose.height / 2
    const rayIntoWall = {
        origin: [front.pointX + front.normalX * 2, front.pointY + front.normalY * 2, zMid] as [number, number, number],
        direction: [-front.normalX, -front.normalY, 0] as [number, number, number],
    }

    it('C/D/E: the context pick resolves the ONE vestibuleInstanceId from the full occupied volume', () => {
        const id = pickVestibuleForContext(rayIntoWall, [v], undefined)
        expect(id).toBe(v.vestibuleInstanceId)
    })

    it('U: selection preference — the selected vestibule wins when the ray hits it', () => {
        const a = radiopharmacy(1)
        const b = { ...radiopharmacy(2), pose: { ...v.pose, centerY: v.pose.centerY + 0.01 } as VestibulePose }
        // Ray hits both; selecting b makes b win even if a is nearer.
        const id = pickVestibuleForContext(rayIntoWall, [a, b], b.vestibuleInstanceId)
        expect(id).toBe(b.vestibuleInstanceId)
    })

    it('V: otherwise the nearest vestibule along the ray wins', () => {
        const near = radiopharmacy(1)
        // Place "far" 50 m further along the ray direction (deeper past near) so
        // both are on the ray but near is closer to the origin.
        const far: ClinicalLogisticsVestibuleInstance = {
            ...radiopharmacy(2),
            pose: {
                ...near.pose,
                centerX: near.pose.centerX + rayIntoWall.direction[0] * 50,
                centerY: near.pose.centerY + rayIntoWall.direction[1] * 50,
            },
        }
        const id = pickVestibuleForContext(rayIntoWall, [far, near], undefined)
        expect(id).toBe(near.vestibuleInstanceId)
    })

    it('hidden vestibules are excluded from the pick', () => {
        const hidden: ClinicalLogisticsVestibuleInstance = { ...radiopharmacy(), hidden: true }
        expect(pickVestibuleForContext(rayIntoWall, [hidden], undefined)).toBeUndefined()
    })

    it('Q/R/S/T: a ray that misses every vestibule (empty/BIM) resolves nothing', () => {
        const miss = { origin: [100, 100, 100] as [number, number, number], direction: [0, 0, 1] as [number, number, number] }
        expect(pickVestibuleForContext(miss, [v], undefined)).toBeUndefined()
    })

    it('rayIntersectAabb returns a finite hit for a ray through the box and undefined for a miss', () => {
        const box = reservedVolumeAsAabb(fullOccupiedVolumeFromPose(v.pose))
        expect(rayIntersectAabb(rayIntoWall, box)).toBeTypeOf('number')
        expect(rayIntersectAabb({ origin: [999, 999, 999], direction: [0, 0, 1] }, box)).toBeUndefined()
    })
})

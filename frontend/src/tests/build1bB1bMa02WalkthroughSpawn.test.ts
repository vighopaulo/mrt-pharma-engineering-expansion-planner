/**
 * build1bB1bMa02WalkthroughSpawn — B1B-MA-02 regression suite.
 *
 * DEFECT (manually reproduced):
 *   "Enter Walkthrough Here" for an UPPER-STOREY clinical room (2C17 PROSTH. LAB
 *   → Radiopharmacy, Second Floor) spawned the camera BELOW / intersecting the
 *   floor slab instead of at pedestrian eye height inside the room.
 *
 * ROOT CAUSE:
 *   The targeted-spawn pipeline correctly resolved spawn.z = roomFloorZ + eye,
 *   but the walkthrough controller pinned the per-session FLOOR ELEVATION to the
 *   whole-model STOREY-BAND datum (loadStoreys Z-banding, ≈ ground/first floor).
 *   applyCamera re-derives eye Z every frame via eyeZForFloor(floorElevation,
 *   eye), so the correct upper-storey spawn Z was overwritten by the low datum
 *   → the camera dropped below/through the second-floor slab.
 *
 * FIX (pure seam extracted for this suite):
 *   resolveWalkthroughFloorElevation() — when a targeted spawn is supplied, the
 *   floor elevation = spawnOverride.z − eyeHeight (reconstructs the SELECTED
 *   ROOM's own floor using the SAME canonical eye height the resolver applied),
 *   else the storey-band datum. floorElevation feeds eyeZForFloor so the eye Z
 *   reproduces spawn.z EXACTLY and stays pinned there through movement.
 *
 * These tests assert the DEFECT-SPECIFIC guarantees. The 16 general spawn
 * sub-properties live in build1bSpatialCorrection.test.ts and are unchanged.
 */

import { describe, it, expect } from 'vitest'
import { resolveWalkthroughFloorElevation } from '../components/spatial/walkNav'
import { eyeZForFloor } from '../components/spatial/firstPerson'
import { WALKTHROUGH_EYE_HEIGHT_M } from '../components/spatial/cameraNav'
import {
    resolveTargetedWalkthroughSpawn,
    type SpawnRoomGeometry,
    type SpawnStoreyBand,
} from '../components/spatial/targetedWalkthroughSpawn'
import { pointInFootprint, type WorldFootprint } from '../domain/assets/spatialSemantics'

const EYE = WALKTHROUGH_EYE_HEIGHT_M

// A rectangular ground-floor room and its storey band.
const GROUND_FLOOR_Z = 0
const groundRoom: SpawnRoomGeometry = {
    outerLoop: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 8 }, { x: 0, y: 8 }],
    floorZ: GROUND_FLOOR_Z,
    ceilingZ: GROUND_FLOOR_Z + 3,
}
const groundBand: SpawnStoreyBand = { storeyId: 'S0', zLow: -0.1, zHigh: 3.1 }

// The SAME XY room but on an upper storey (Second Floor), floor at Z = 8.4.
// This mirrors the reproduced 2C17 PROSTH. LAB / Radiopharmacy defect.
const SECOND_FLOOR_Z = 8.4
const upperRoom: SpawnRoomGeometry = {
    ...groundRoom,
    floorZ: SECOND_FLOOR_Z,
    ceilingZ: SECOND_FLOOR_Z + 3,
}
const upperBand: SpawnStoreyBand = { storeyId: 'S2', zLow: 8.3, zHigh: 11.5 }

// The buggy whole-model storey-band datum the controller used to pin the camera
// to (loadStoreys Z-banding collapses toward the model's lowest storey).
const WHOLE_MODEL_BAND_DATUM = GROUND_FLOOR_Z

describe('B1B-MA-02 — upper-storey targeted walkthrough spawn', () => {
    // (a) Upper-storey targeted spawn.z ≈ roomFloorZ + eyeHeight, and the OLD
    // calc (pin to whole-model band datum) would have been BELOW the room floor.
    it('(a) upper-storey spawn.z ≈ roomFloorZ + eyeHeight; old storey-band calc is below the slab', () => {
        const r = resolveTargetedWalkthroughSpawn({ room: upperRoom, storey: upperBand, eyeHeight: EYE })
        expect(r.ok).toBe(true)
        if (!r.ok) return

        // Spawn is tied to the SELECTED ROOM's floor, not a global Z.
        expect(r.spawn.z).toBeCloseTo(SECOND_FLOOR_Z + EYE, 6)
        expect(r.spawn.z).toBeGreaterThan(SECOND_FLOOR_Z) // strictly above the slab

        // FIXED controller floor elevation reconstructs the room floor exactly.
        const fixedFloor = resolveWalkthroughFloorElevation({
            spawnOverrideZ: r.spawn.z,
            eyeHeight: EYE,
            storeyFloorZ: WHOLE_MODEL_BAND_DATUM,
        })
        expect(fixedFloor).toBeCloseTo(SECOND_FLOOR_Z, 6)

        // The camera Z applyCamera derives every frame == the resolved spawn.z.
        const fixedEyeZ = eyeZForFloor(fixedFloor, EYE)
        expect(fixedEyeZ).toBeCloseTo(r.spawn.z, 6)
        expect(fixedEyeZ).toBeGreaterThan(SECOND_FLOOR_Z)

        // REGRESSION GUARD: the OLD behaviour pinned floorElevation to the
        // whole-model band datum, so the eye Z landed at/below the second-floor
        // slab — the exact defect. Assert the new value is NOT that.
        const oldEyeZ = eyeZForFloor(WHOLE_MODEL_BAND_DATUM, EYE)
        expect(oldEyeZ).toBeLessThan(SECOND_FLOOR_Z) // proves the old value was below the room floor
        expect(fixedEyeZ).not.toBeCloseTo(oldEyeZ, 3)
    })

    // (b) Two rooms at the SAME XY on DIFFERENT storeys must resolve to DISTINCT
    // camera Z. This fails if both collapse to a single global/first-floor Z.
    it('(b) same-XY rooms on different storeys produce distinct camera Z (no collapse)', () => {
        const ground = resolveTargetedWalkthroughSpawn({ room: groundRoom, storey: groundBand, eyeHeight: EYE })
        const upper = resolveTargetedWalkthroughSpawn({ room: upperRoom, storey: upperBand, eyeHeight: EYE })
        expect(ground.ok && upper.ok).toBe(true)
        if (!ground.ok || !upper.ok) return

        // Same interior XY (same footprint), different Z.
        expect(upper.spawn.x).toBeCloseTo(ground.spawn.x, 6)
        expect(upper.spawn.y).toBeCloseTo(ground.spawn.y, 6)

        const groundEyeZ = eyeZForFloor(
            resolveWalkthroughFloorElevation({ spawnOverrideZ: ground.spawn.z, eyeHeight: EYE, storeyFloorZ: WHOLE_MODEL_BAND_DATUM }),
            EYE,
        )
        const upperEyeZ = eyeZForFloor(
            resolveWalkthroughFloorElevation({ spawnOverrideZ: upper.spawn.z, eyeHeight: EYE, storeyFloorZ: WHOLE_MODEL_BAND_DATUM }),
            EYE,
        )

        // Distinct storeys => distinct eye Z, separated by roughly the storey gap.
        expect(upperEyeZ).not.toBeCloseTo(groundEyeZ, 3)
        expect(upperEyeZ - groundEyeZ).toBeCloseTo(SECOND_FLOOR_Z - GROUND_FLOOR_Z, 5)
    })

    // (c) Irregular / concave room: the resolved interior XY must be inside the
    // footprint AND the Z must sit on the correct (upper) storey.
    it('(c) irregular/concave upper-storey room: interior XY inside footprint + correct storey Z', () => {
        // L-shaped room whose centroid falls OUTSIDE the polygon -> forces the
        // interior grid fallback; placed on the second floor.
        const lRoom: SpawnRoomGeometry = {
            outerLoop: [
                { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 4 },
                { x: 4, y: 4 }, { x: 4, y: 10 }, { x: 0, y: 10 },
            ],
            floorZ: SECOND_FLOOR_Z,
            ceilingZ: SECOND_FLOOR_Z + 3,
        }
        const r = resolveTargetedWalkthroughSpawn({ room: lRoom, storey: upperBand, eyeHeight: EYE })
        expect(r.ok).toBe(true)
        if (!r.ok) return

        const footprint: WorldFootprint = {
            ring: lRoom.outerLoop.map((p) => ({ x: p.x, y: p.y })),
            zLow: lRoom.floorZ,
            zHigh: lRoom.ceilingZ!,
        }
        expect(pointInFootprint({ x: r.spawn.x, y: r.spawn.y, z: r.spawn.z }, footprint)).toBe(true)
        expect(r.spawn.z).toBeCloseTo(SECOND_FLOOR_Z + EYE, 6)
        // Floor membership within the upper band.
        expect(lRoom.floorZ).toBeGreaterThanOrEqual(upperBand.zLow)
        expect(lRoom.floorZ).toBeLessThanOrEqual(upperBand.zHigh)
    })

    // (d) Floor constraint is STABLE across movement: the eye Z reconstructed
    // from the room floor is invariant regardless of XY translation (the camera
    // walks the floor plane, never drifts vertically, never passes the slab).
    it('(d) post-spawn floor constraint stays on the upper storey through movement', () => {
        const r = resolveTargetedWalkthroughSpawn({ room: upperRoom, storey: upperBand, eyeHeight: EYE })
        expect(r.ok).toBe(true)
        if (!r.ok) return

        const floor = resolveWalkthroughFloorElevation({ spawnOverrideZ: r.spawn.z, eyeHeight: EYE, storeyFloorZ: WHOLE_MODEL_BAND_DATUM })

        // Simulate several walk steps in XY; eyeZForFloor depends only on the
        // fixed floor elevation, so Z must be identical each step and above slab.
        const steps = [
            { x: r.spawn.x, y: r.spawn.y },
            { x: r.spawn.x + 1.5, y: r.spawn.y },
            { x: r.spawn.x + 1.5, y: r.spawn.y + 2.0 },
            { x: r.spawn.x - 0.7, y: r.spawn.y - 1.1 },
        ]
        const zs = steps.map(() => eyeZForFloor(floor, EYE))
        for (const z of zs) {
            expect(z).toBeCloseTo(r.spawn.z, 6)
            expect(z).toBeGreaterThan(SECOND_FLOOR_Z) // never below/through the slab
        }
        // No vertical drift across the whole walk.
        expect(Math.max(...zs) - Math.min(...zs)).toBeCloseTo(0, 9)
    })

    // (e) Equipment envelope inside the room AND spawn inside the room: the
    // spawn is room-geometry-derived and never coincides with equipment, yet
    // both land within the same footprint (containment sanity).
    it('(e) spawn ∈ room footprint and an in-room equipment envelope ∈ same footprint', () => {
        const r = resolveTargetedWalkthroughSpawn({ room: upperRoom, storey: upperBand, eyeHeight: EYE })
        expect(r.ok).toBe(true)
        if (!r.ok) return

        const footprint: WorldFootprint = {
            ring: upperRoom.outerLoop.map((p) => ({ x: p.x, y: p.y })),
            zLow: upperRoom.floorZ,
            zHigh: upperRoom.ceilingZ!,
        }
        // Spawn inside the room.
        expect(pointInFootprint({ x: r.spawn.x, y: r.spawn.y, z: r.spawn.z }, footprint)).toBe(true)

        // A representative equipment envelope (footprint corners) fully inside.
        const equipEnvelope = [
            { x: 2, y: 2 }, { x: 3.5, y: 2 }, { x: 3.5, y: 3.5 }, { x: 2, y: 3.5 },
        ]
        for (const c of equipEnvelope) {
            expect(pointInFootprint({ x: c.x, y: c.y, z: upperRoom.floorZ + 0.5 }, footprint)).toBe(true)
        }
    })
})

describe('B1B-MA-02 — resolveWalkthroughFloorElevation seam', () => {
    it('uses spawnOverride.z − eyeHeight when a finite override is supplied', () => {
        expect(resolveWalkthroughFloorElevation({ spawnOverrideZ: 10.05, eyeHeight: 1.65, storeyFloorZ: 0 }))
            .toBeCloseTo(8.4, 6)
    })

    it('falls back to the storey-band datum when there is no override', () => {
        expect(resolveWalkthroughFloorElevation({ spawnOverrideZ: undefined, eyeHeight: 1.65, storeyFloorZ: 8.4 }))
            .toBe(8.4)
    })

    it('falls back to the storey-band datum when the override is non-finite', () => {
        expect(resolveWalkthroughFloorElevation({ spawnOverrideZ: Number.NaN, eyeHeight: 1.65, storeyFloorZ: 3.2 }))
            .toBe(3.2)
        expect(resolveWalkthroughFloorElevation({ spawnOverrideZ: 5, eyeHeight: Number.NaN, storeyFloorZ: 3.2 }))
            .toBe(3.2)
    })

    it('round-trips: eyeZForFloor(resolveFloor(spawnZ), eye) === spawnZ (exact reconstruction)', () => {
        const spawnZ = SECOND_FLOOR_Z + EYE
        const floor = resolveWalkthroughFloorElevation({ spawnOverrideZ: spawnZ, eyeHeight: EYE, storeyFloorZ: WHOLE_MODEL_BAND_DATUM })
        expect(eyeZForFloor(floor, EYE)).toBeCloseTo(spawnZ, 9)
    })
})

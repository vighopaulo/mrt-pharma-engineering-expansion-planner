/**
 * assetPicking — pure, Bentley-free ray/bounding-volume picking for MRT Pharma
 * spatial assets. Used for offline-testable nearest-hit resolution and as the
 * mathematical basis for direct selection.
 *
 * The primary runtime selection path is NATIVE Bentley decoration picking
 * (pickable WorldDecoration graphics + Decorator.testDecorationHit +
 * HitDetail.sourceId). This module provides a deterministic, unit-testable
 * ray-vs-oriented-bounding-box intersection that accounts for the instance's
 * position, yaw rotation, scale, and dimensions — proving that a rotated
 * scanner is still hit at its visible location and that overlapping instances
 * resolve to the NEAREST along the ray. It never mutates any state.
 */
import type { AssetInstance } from '../../domain/assets'

export interface Ray3 {
    origin: [number, number, number]
    /** Need not be normalized. */
    direction: [number, number, number]
}

const DEG2RAD = Math.PI / 180

/** Axis-aligned half-extents (meters) of an instance in its LOCAL frame. */
function localHalfExtents(inst: AssetInstance): [number, number, number] {
    const s = inst.transform.scale
    return [
        (inst.dimensions.width * s.x) / 2,
        (inst.dimensions.depth * s.y) / 2,
        (inst.dimensions.height * s.z) / 2,
    ]
}

/** Rotate a world vector into the instance's LOCAL frame (inverse yaw about Z). */
function worldToLocalYaw(v: [number, number, number], yawDeg: number): [number, number, number] {
    const yaw = yawDeg * DEG2RAD
    const cos = Math.cos(-yaw), sin = Math.sin(-yaw)
    return [v[0] * cos - v[1] * sin, v[0] * sin + v[1] * cos, v[2]]
}

/**
 * Intersect a world-space ray with an instance's oriented bounding box.
 * Returns the nearest positive hit distance (t) along the ray, or undefined.
 *
 * The box is centered on the instance position + half its height (the scanner
 * body sits from z..z+H), yaw-rotated about Z. We transform the ray into the
 * box-local frame and run a slab test.
 */
export function rayIntersectInstance(ray: Ray3, inst: AssetInstance): number | undefined {
    const p = inst.transform.position
    const [hx, hy, hz] = localHalfExtents(inst)
    // Box center: the scanner body spans z..z+H, so center z is p.z + hz.
    const center: [number, number, number] = [p.x, p.y, p.z + hz]
    const yaw = inst.transform.rotation.yaw

    // Ray in box-local frame.
    const oWorld: [number, number, number] = [ray.origin[0] - center[0], ray.origin[1] - center[1], ray.origin[2] - center[2]]
    const o = worldToLocalYaw(oWorld, yaw)
    const d = worldToLocalYaw(ray.direction, yaw)

    const half = [hx, hy, hz]
    let tmin = -Infinity
    let tmax = Infinity
    for (let i = 0; i < 3; i++) {
        const oi = o[i], di = d[i], h = half[i]
        if (Math.abs(di) < 1e-12) {
            // Ray parallel to slab; miss if origin outside the slab.
            if (oi < -h || oi > h) return undefined
        } else {
            let t1 = (-h - oi) / di
            let t2 = (h - oi) / di
            if (t1 > t2) { const tmp = t1; t1 = t2; t2 = tmp }
            if (t1 > tmin) tmin = t1
            if (t2 < tmax) tmax = t2
            if (tmin > tmax) return undefined
        }
    }
    // Nearest non-negative intersection.
    const t = tmin >= 0 ? tmin : (tmax >= 0 ? tmax : undefined)
    return t
}

/**
 * Resolve the NEAREST hit instance along a ray among the given instances.
 * Returns the assetInstanceId of the closest hit, or undefined if none are hit.
 * Ties never depend on array order — smallest t wins.
 */
export function pickNearestInstance(ray: Ray3, instances: readonly AssetInstance[]): string | undefined {
    let bestId: string | undefined
    let bestT = Infinity
    for (const inst of instances) {
        const t = rayIntersectInstance(ray, inst)
        if (t !== undefined && t < bestT) {
            bestT = t
            bestId = inst.assetInstanceId
        }
    }
    return bestId
}

/** Decision result for whether a located hit is a valid MRT direct-drag target. */
export type HitAcceptance = 'ACCEPT' | 'REJECT'

/**
 * Pure decision seam mirroring the direct-manipulation tool's filterHit:
 * accept ONLY when the located hit is a decoration (not an iModel element) whose
 * pickable source id resolves to an MRT Pharma assetInstanceId. Everything else
 * (BIM elements, unknown/undefined ids) is rejected.
 *
 * `resolveAssetId` is the decorator's pickId -> assetInstanceId lookup.
 */
export function decideHitAcceptance(
    hit: { sourceId?: string; isElementHit: boolean },
    resolveAssetId: (pickId: string) => string | undefined,
): HitAcceptance {
    if (!hit.sourceId) return 'REJECT'
    if (hit.isElementHit) return 'REJECT' // BIM element, never a direct-drag target
    return resolveAssetId(hit.sourceId) ? 'ACCEPT' : 'REJECT'
}

/**
 * Intersect a ray with the horizontal plane Z = planeZ. Returns the world point
 * or undefined if the ray is parallel to the plane. Used to build the fluid
 * drag plane (preserve start Z).
 */
export function rayIntersectZPlane(ray: Ray3, planeZ: number): [number, number, number] | undefined {
    const dz = ray.direction[2]
    if (Math.abs(dz) < 1e-12) return undefined
    const t = (planeZ - ray.origin[2]) / dz
    if (!Number.isFinite(t)) return undefined
    return [ray.origin[0] + ray.direction[0] * t, ray.origin[1] + ray.direction[1] * t, planeZ]
}

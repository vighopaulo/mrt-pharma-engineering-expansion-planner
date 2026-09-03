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

/** What kind of MRT pickable a located hit resolves to. */
export type MrtPickTargetType = 'ASSET_BODY' | 'ROTATION_HANDLE'

export interface MrtPickTarget {
    type: MrtPickTargetType
    assetInstanceId: string
}

/**
 * Resolve a located hit into a typed MRT pick target, or undefined for BIM /
 * unknown / non-MRT hits. Two independent resolvers are supplied: one that maps
 * a pick id to an asset BODY, and one that maps a pick id to a ROTATION HANDLE.
 * The rotation-handle resolver is checked first so a handle drawn over the body
 * takes precedence for its own pick id. BIM element hits are always ignored.
 */
export function resolveMrtPickTarget(
    hit: { sourceId?: string; isElementHit: boolean },
    resolveHandleAssetId: (pickId: string) => string | undefined,
    resolveBodyAssetId: (pickId: string) => string | undefined,
): MrtPickTarget | undefined {
    if (!hit.sourceId || hit.isElementHit) return undefined
    const handleAsset = resolveHandleAssetId(hit.sourceId)
    if (handleAsset) return { type: 'ROTATION_HANDLE', assetInstanceId: handleAsset }
    const bodyAsset = resolveBodyAssetId(hit.sourceId)
    if (bodyAsset) return { type: 'ASSET_BODY', assetInstanceId: bodyAsset }
    return undefined
}

/**
 * Scoped screen-space hit test for the object-attached rotation ring, used ONLY
 * as a fallback for the SELECTED asset when native decoration locate returns the
 * body (or nothing) instead of the thin torus. Given the ring's projected center
 * and a set of sample points around the projected ring (all in screen/view px),
 * plus the pointer position, return true when the pointer lies within
 * `tolerancePx` of the ring outline.
 *
 * We approximate the (possibly elliptical, under perspective) projected ring by
 * the minimum distance from the pointer to a polyline of projected samples. This
 * keeps the test independent of the projection being a perfect circle.
 */
export function pointerNearProjectedRing(
    pointer: { x: number; y: number },
    ringSamples: readonly { x: number; y: number }[],
    tolerancePx: number,
): boolean {
    if (ringSamples.length < 2) return false
    let minDist = Infinity
    for (let i = 0; i < ringSamples.length; i++) {
        const a = ringSamples[i]
        const b = ringSamples[(i + 1) % ringSamples.length]
        const d = distancePointToSegment(pointer, a, b)
        if (d < minDist) minDist = d
    }
    return minDist <= tolerancePx
}

function distancePointToSegment(
    p: { x: number; y: number },
    a: { x: number; y: number },
    b: { x: number; y: number },
): number {
    const abx = b.x - a.x, aby = b.y - a.y
    const apx = p.x - a.x, apy = p.y - a.y
    const len2 = abx * abx + aby * aby
    let t = len2 > 0 ? (apx * abx + apy * aby) / len2 : 0
    t = Math.max(0, Math.min(1, t))
    const cx = a.x + t * abx, cy = a.y + t * aby
    return Math.hypot(p.x - cx, p.y - cy)
}

/** World-space sample points around a horizontal ring (center + radius, in the
 * Z = center.z plane). Returned in world coordinates for the caller to project. */
export function ringWorldSamples(
    center: [number, number, number],
    radius: number,
    count = 32,
): [number, number, number][] {
    const out: [number, number, number][] = []
    for (let i = 0; i < count; i++) {
        const a = (i / count) * Math.PI * 2
        out.push([center[0] + Math.cos(a) * radius, center[1] + Math.sin(a) * radius, center[2]])
    }
    return out
}

const RAD2DEG = 180 / Math.PI

/** Normalize degrees into [0, 360). */
export function normalizeDeg(deg: number): number {
    if (!Number.isFinite(deg)) return 0
    const m = deg % 360
    return m < 0 ? m + 360 : m
}

/**
 * Signed angle in DEGREES from vector A to vector B in the XY plane, in
 * (-180, 180]. Uses atan2(cross, dot). Positive = counter-clockwise about +Z.
 */
export function signedAngleXYDeg(
    ax: number, ay: number, bx: number, by: number,
): number {
    const cross = ax * by - ay * bx
    const dot = ax * bx + ay * by
    if (cross === 0 && dot === 0) return 0
    return Math.atan2(cross, dot) * RAD2DEG
}

/**
 * Compute the fluid preview yaw for an object-attached rotation:
 *   deltaAngle = signed angle from the start grab vector to the current vector
 *                (both measured from the pivot center in the XY plane),
 *   previewYaw = normalize(startYaw + deltaAngle).
 * All inputs/outputs in DEGREES. Returns undefined if either vector is
 * degenerate (pointer exactly on the center).
 */
export function computePreviewYaw(input: {
    startYaw: number
    center: { x: number; y: number }
    startPoint: { x: number; y: number }
    currentPoint: { x: number; y: number }
}): number | undefined {
    const ax = input.startPoint.x - input.center.x
    const ay = input.startPoint.y - input.center.y
    const bx = input.currentPoint.x - input.center.x
    const by = input.currentPoint.y - input.center.y
    if ((ax === 0 && ay === 0) || (bx === 0 && by === 0)) return undefined
    const delta = signedAngleXYDeg(ax, ay, bx, by)
    return normalizeDeg(input.startYaw + delta)
}

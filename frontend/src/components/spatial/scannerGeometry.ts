/**
 * Pure geometry description for the generic PET/CT scanner representation.
 *
 * This module is Bentley-FREE and fully testable in vitest. It converts an
 * AssetInstance's dimensions + world transform into a small set of primitive
 * "parts" (gantry / bore / patient table) expressed as world-coordinate boxes
 * and a bore cylinder. The Bentley decorator consumes these parts and emits
 * GraphicBuilder solids — the decorator never invents geometry itself.
 *
 * Coordinate space: BENTLEY_WORLD_COORDINATES. Local part layout is centered on
 * the instance position; yaw rotates the layout about the vertical (Z) axis.
 * (Pitch/roll are carried in the transform but this generic LOW-LOD part layout
 * only applies yaw, which is the meaningful DOF for floor-placed equipment.)
 */
import type { AssetInstance } from '../../domain/assets'

export interface WorldBox {
    /** Axis-aligned-in-local corner low/high, already rotated+translated to world via `points`. */
    kind: 'BOX'
    /** 8 world-space corner points (lo/hi combinations) for a (possibly yawed) box. */
    low: [number, number, number]
    high: [number, number, number]
    /** Yaw (radians) applied about the instance center for this box. */
    yawRadians: number
    /** Instance center (world) about which yaw is applied. */
    center: [number, number, number]
    part: ScannerPart
}

export interface WorldCylinder {
    kind: 'CYLINDER'
    /** Axis endpoints in world coordinates. */
    centerA: [number, number, number]
    centerB: [number, number, number]
    radius: number
    part: ScannerPart
}

export type ScannerPartGeometry = WorldBox | WorldCylinder
export type ScannerPart = 'GANTRY' | 'BORE' | 'PATIENT_TABLE'

const DEG2RAD = Math.PI / 180

/**
 * Build the generic scanner parts for one instance in WORLD coordinates.
 * Dimensions: width=X (gantry width), depth=Y (table travel), height=Z.
 */
export function buildScannerParts(inst: AssetInstance): ScannerPartGeometry[] {
    const { width: w, depth: d, height: h } = inst.dimensions
    const p = inst.transform.position
    const sx = inst.transform.scale.x, sy = inst.transform.scale.y, sz = inst.transform.scale.z
    const W = w * sx, D = d * sy, H = h * sz
    const yaw = inst.transform.rotation.yaw * DEG2RAD
    const center: [number, number, number] = [p.x, p.y, p.z]

    // Gantry: a substantial body block occupying the rear ~40% of the depth,
    // full width, full height, sitting on the floor (z from 0..H relative to p.z).
    const gantryDepth = D * 0.4
    const gantry: WorldBox = {
        kind: 'BOX',
        low: [p.x - W / 2, p.y + D / 2 - gantryDepth, p.z],
        high: [p.x + W / 2, p.y + D / 2, p.z + H],
        yawRadians: yaw,
        center,
        part: 'GANTRY',
    }

    // Bore: horizontal cylinder through the gantry along Y, centered vertically
    // a bit above mid-height (patient bore). Radius ~30% of height. The bore
    // axis must yaw with the instance too, so its endpoints are rotated about
    // the instance center by the same yaw as the boxes.
    const boreRadius = Math.max(H * 0.3, 0.2)
    const boreZ = p.z + H * 0.55
    const bore: WorldCylinder = {
        kind: 'CYLINDER',
        centerA: applyYaw([p.x, p.y + D / 2 - gantryDepth, boreZ], center, yaw),
        centerB: applyYaw([p.x, p.y + D / 2 + 0.01, boreZ], center, yaw),
        radius: boreRadius,
        part: 'BORE',
    }

    // Patient table: a narrow longitudinal slab extending forward (−Y) from the
    // bore, at bore height, narrower than the gantry.
    const tableWidth = Math.min(W * 0.35, boreRadius * 1.4)
    const tableTopZ = boreZ - boreRadius * 0.15
    const table: WorldBox = {
        kind: 'BOX',
        low: [p.x - tableWidth / 2, p.y - D / 2, tableTopZ - 0.08],
        high: [p.x + tableWidth / 2, p.y + D / 2 - gantryDepth, tableTopZ],
        yawRadians: yaw,
        center,
        part: 'PATIENT_TABLE',
    }

    return [gantry, bore, table]
}

/** Rotate a world point about `center` by `yawRadians` around Z. */
export function applyYaw(point: [number, number, number], center: [number, number, number], yawRadians: number): [number, number, number] {
    if (yawRadians === 0) return point
    const dx = point[0] - center[0]
    const dy = point[1] - center[1]
    const cos = Math.cos(yawRadians), sin = Math.sin(yawRadians)
    return [center[0] + dx * cos - dy * sin, center[1] + dx * sin + dy * cos, point[2]]
}

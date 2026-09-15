/**
 * targetedWalkthroughSpawn — pure, Bentley-free TARGETED WALKTHROUGH SAFE-SPAWN
 * resolver for MRT Pharma (Build 1B spatial-foundation correction, Problem C).
 *
 * PROBLEM
 *   The existing walkthrough spawns the camera at the WHOLE-MODEL center
 *   (range.center) on the lowest storey. That is not room-specific: entering a
 *   walkthrough to inspect a particular clinical room drops you somewhere
 *   generic, often inside a wall or the wrong space. This resolver computes a
 *   SAFE spawn point DERIVED FROM A SPECIFIC ROOM's authoritative geometry.
 *
 * DOCTRINE (16 sub-properties the resolver must honor — see tests §31):
 *   1.  Interior point is derived from the ROOM's own geometry (interior anchor
 *       preferred; centroid / grid fallback), never a global entrance.
 *   2.  Spawn Z is FLOOR/STOREY-derived + a configurable eye height — never a
 *       global hardcoded Z.
 *   3.  Collision is ACTIVE: a candidate too close to a wall is rejected
 *       (wall-clearance), never a wall pass-through.
 *   4.  Centroid-invalid fallback: if the anchor/centroid is outside the room or
 *       too close to a wall, a deterministic interior grid search finds another
 *       interior point.
 *   5.  A candidate OUTSIDE the room footprint is rejected.
 *   6.  A candidate on the WRONG storey (Z outside the storey band) is rejected.
 *   7.  Non-finite geometry / eye height => rejected (never NaN spawn).
 *   8.  Deterministic: identical inputs always yield the identical spawn.
 *   9.  Room-specific: the spawn is a function of THIS room, not the model.
 *   10. Honest failure: NO_SAFE_WALKTHROUGH_SPAWN with a bounded reason (never a
 *       silent fallback to the model center).
 *   11. The planning VOLUME is NOT the spawn authority (a prism can be a poor
 *       proxy; the room footprint is authority). Planning-volume coords are
 *       never read here.
 *   12. Equipment is NOT the spawn authority (equipment placement never moves
 *       the spawn). Equipment is never read here.
 *   13. Clearance radius is configurable (matches the walk collision radius).
 *   14. The chosen point stays strictly INSIDE the footprint (holes excluded).
 *   15. The result carries provenance (how the point was chosen) for diagnostics.
 *   16. No @itwin import; no side effects; unit-testable without a viewport.
 *
 * The walkthrough controller consumes the resolved {x,y,z} as an EXPLICIT spawn
 * override; it still runs its own live collision during movement. This resolver
 * only decides the ENTRY point.
 */

import { pointInFootprint, type WorldFootprint } from '../../domain/assets/spatialSemantics'
import { pointSegmentDistance, type WallSegment } from './walkNav'

// ---------------------------------------------------------------------------
// Inputs / outputs
// ---------------------------------------------------------------------------

export interface Vec2 { x: number; y: number }
export interface Vec3 { x: number; y: number; z: number }

/** The room's authoritative geometry (from the overlay's footprint cache). */
export interface SpawnRoomGeometry {
    /** Closed outer footprint ring (world XY), CCW or CW — winding-agnostic. */
    outerLoop: readonly Vec2[]
    /** Interior holes (world XY) the spawn must avoid. */
    holes?: readonly (readonly Vec2[])[]
    /** Room floor elevation (world Z). */
    floorZ: number
    /** Room ceiling elevation (world Z); floorZ + default when unknown. */
    ceilingZ?: number
    /** Preferred interior anchor (a true interior point), when available. */
    interiorAnchor?: Vec3
}

/** The storey vertical band the spawn must land within (wrong-storey rejection). */
export interface SpawnStoreyBand {
    storeyId?: string
    zLow: number
    zHigh: number
}

export type SpawnFailureCode =
    | 'NON_FINITE_GEOMETRY'
    | 'NON_FINITE_EYE_HEIGHT'
    | 'DEGENERATE_FOOTPRINT'
    | 'NO_INTERIOR_POINT'
    | 'NO_WALL_CLEARANCE'
    | 'WRONG_STOREY'

export type SpawnProvenance =
    | 'INTERIOR_ANCHOR'
    | 'FOOTPRINT_CENTROID'
    | 'INTERIOR_GRID_SEARCH'

export type SpawnResult =
    | {
        ok: true
        spawn: Vec3
        /** The eye-height applied above the floor. */
        eyeHeight: number
        /** Which method produced the interior point. */
        provenance: SpawnProvenance
        /** Wall clearance achieved at the chosen point (m; Infinity when no walls). */
        wallClearance: number
        reason: 'SAFE_SPAWN'
    }
    | {
        ok: false
        code: SpawnFailureCode
        reason: string
    }

// ---------------------------------------------------------------------------
// Resolver
// ---------------------------------------------------------------------------

export interface ResolveSpawnInput {
    room: SpawnRoomGeometry
    storey?: SpawnStoreyBand
    /** Eye height above the floor (meters). Configurable (no global hardcode). */
    eyeHeight: number
    /** Minimum wall clearance (meters). Defaults to the walk collision radius. */
    clearanceRadius?: number
    /** Wall segments for the clearance test (empty => clearance is trivially met). */
    walls?: readonly WallSegment[]
    /** Interior grid resolution for the fallback search (deterministic). */
    gridResolution?: number
}

const DEFAULT_CLEARANCE_RADIUS_M = 0.35 // matches WALK_COLLISION_RADIUS_M
const DEFAULT_GRID = 9

function isFiniteNum(n: unknown): n is number { return typeof n === 'number' && Number.isFinite(n) }
function isFiniteVec2(p: Vec2): boolean { return isFiniteNum(p.x) && isFiniteNum(p.y) }

/**
 * Resolve a safe walkthrough spawn for a specific room. Deterministic + pure.
 * Order: anchor -> centroid -> deterministic interior grid. Each candidate must
 * be (a) inside the footprint (holes excluded), (b) clear of walls, and the
 * resulting Z must sit within the storey band. Honest failure when none passes.
 */
export function resolveTargetedWalkthroughSpawn(input: ResolveSpawnInput): SpawnResult {
    const { room } = input
    const clearance = isFiniteNum(input.clearanceRadius) && input.clearanceRadius >= 0 ? input.clearanceRadius : DEFAULT_CLEARANCE_RADIUS_M
    const walls = input.walls ?? []

    // (7) Non-finite eye height => reject.
    if (!isFiniteNum(input.eyeHeight) || input.eyeHeight <= 0) {
        return { ok: false, code: 'NON_FINITE_EYE_HEIGHT', reason: 'Eye height is not a valid positive number.' }
    }
    // (7) Non-finite floor / footprint => reject.
    if (!isFiniteNum(room.floorZ)) {
        return { ok: false, code: 'NON_FINITE_GEOMETRY', reason: 'Room floor elevation is non-finite.' }
    }
    if (!room.outerLoop || room.outerLoop.length < 3 || !room.outerLoop.every(isFiniteVec2)) {
        return { ok: false, code: 'DEGENERATE_FOOTPRINT', reason: 'Room footprint is missing or degenerate.' }
    }
    // Near-zero area (collinear / sliver) footprint cannot host a walkthrough.
    if (polygonArea(room.outerLoop) < 1e-3) {
        return { ok: false, code: 'DEGENERATE_FOOTPRINT', reason: 'Room footprint has effectively zero area.' }
    }

    const spawnZ = room.floorZ + input.eyeHeight

    // (6) Wrong-storey rejection: the spawn Z (at the floor) must sit within the
    // storey band. We test the FLOOR elevation (not the eye) against the band so
    // a tall storey/eye-height never spuriously fails; the floor is the room's
    // true storey membership. Inclusive with a small epsilon.
    if (input.storey && isFiniteNum(input.storey.zLow) && isFiniteNum(input.storey.zHigh)) {
        const eps = 1e-6
        const lo = Math.min(input.storey.zLow, input.storey.zHigh) - eps
        const hi = Math.max(input.storey.zLow, input.storey.zHigh) + eps
        if (room.floorZ < lo || room.floorZ > hi) {
            return { ok: false, code: 'WRONG_STOREY', reason: `Room floor (${room.floorZ.toFixed(2)}) is outside the target storey band.` }
        }
    }

    const footprint = toWorldFootprint(room, spawnZ)
    const holes = (room.holes ?? []).filter((h) => h.length >= 3)

    // Candidate 1 — interior anchor (preferred).
    const anchor = room.interiorAnchor
    if (anchor && isFiniteNum(anchor.x) && isFiniteNum(anchor.y)) {
        const cand = { x: anchor.x, y: anchor.y }
        const check = evaluateCandidate(cand, footprint, holes, walls, clearance, spawnZ)
        if (check.ok) return spawnAt(cand, spawnZ, input.eyeHeight, 'INTERIOR_ANCHOR', check.clearance)
    }

    // Candidate 2 — footprint centroid (may fall outside a concave room; tested).
    const centroid = ringCentroid(room.outerLoop)
    if (isFiniteVec2(centroid)) {
        const check = evaluateCandidate(centroid, footprint, holes, walls, clearance, spawnZ)
        if (check.ok) return spawnAt(centroid, spawnZ, input.eyeHeight, 'FOOTPRINT_CENTROID', check.clearance)
    }

    // (4) Fallback — deterministic interior grid search over the footprint bbox.
    const grid = Math.max(3, Math.floor(input.gridResolution ?? DEFAULT_GRID))
    const bbox = ringBounds(room.outerLoop)
    let best: { p: Vec2; clearance: number } | undefined
    for (let iy = 1; iy < grid; iy++) {
        for (let ix = 1; ix < grid; ix++) {
            const p = {
                x: bbox.minX + ((bbox.maxX - bbox.minX) * ix) / grid,
                y: bbox.minY + ((bbox.maxY - bbox.minY) * iy) / grid,
            }
            const check = evaluateCandidate(p, footprint, holes, walls, clearance, spawnZ)
            if (check.ok) {
                // Pick the interior point with the GREATEST wall clearance (most
                // central-in-free-space) for a stable, comfortable spawn.
                if (!best || check.clearance > best.clearance) best = { p, clearance: check.clearance }
            }
        }
    }
    if (best) return spawnAt(best.p, spawnZ, input.eyeHeight, 'INTERIOR_GRID_SEARCH', best.clearance)

    // (10) Honest failure — distinguish "no interior point at all" from "interior
    // exists but no point clears the walls".
    const anyInterior = gridHasAnyInterior(bbox, grid, footprint, holes)
    if (!anyInterior) {
        return { ok: false, code: 'NO_INTERIOR_POINT', reason: 'No interior point could be found inside the room footprint.' }
    }
    return { ok: false, code: 'NO_WALL_CLEARANCE', reason: `No interior point achieves the required ${clearance.toFixed(2)} m wall clearance (NO_SAFE_WALKTHROUGH_SPAWN).` }
}

// ---------------------------------------------------------------------------
// Candidate evaluation (pure)
// ---------------------------------------------------------------------------

function evaluateCandidate(
    p: Vec2,
    footprint: WorldFootprint,
    holes: readonly (readonly Vec2[])[],
    walls: readonly WallSegment[],
    clearance: number,
    spawnZ: number,
): { ok: true; clearance: number } | { ok: false } {
    if (!isFiniteVec2(p)) return { ok: false }
    // (5)(14) Inside the outer footprint, outside every hole.
    const testPoint = { x: p.x, y: p.y, z: (footprint.zLow + footprint.zHigh) / 2 }
    if (!pointInFootprint(testPoint, footprint)) return { ok: false }
    for (const h of holes) {
        if (pointInFootprint(testPoint, { ring: h.map((q) => ({ x: q.x, y: q.y })), zLow: footprint.zLow, zHigh: footprint.zHigh })) {
            return { ok: false }
        }
    }
    // (3)(13) Wall clearance — reject if any wall is within the clearance radius.
    let minWall = Infinity
    for (const w of walls) {
        const d = pointSegmentDistance(p, w.a, w.b)
        if (d < minWall) minWall = d
    }
    if (minWall < clearance) return { ok: false }
    void spawnZ // spawnZ carried for symmetry; Z membership already validated
    return { ok: true, clearance: minWall }
}

function spawnAt(p: Vec2, z: number, eyeHeight: number, provenance: SpawnProvenance, clearance: number): SpawnResult {
    return { ok: true, spawn: { x: p.x, y: p.y, z }, eyeHeight, provenance, wallClearance: clearance, reason: 'SAFE_SPAWN' }
}

// ---------------------------------------------------------------------------
// Geometry helpers (pure)
// ---------------------------------------------------------------------------

function toWorldFootprint(room: SpawnRoomGeometry, spawnZ: number): WorldFootprint {
    const zLow = room.floorZ
    const zHigh = isFiniteNum(room.ceilingZ) && (room.ceilingZ as number) > room.floorZ ? (room.ceilingZ as number) : room.floorZ + 3
    // Use a mid-height test band that safely contains spawnZ.
    void spawnZ
    return { ring: room.outerLoop.map((p) => ({ x: p.x, y: p.y })), zLow, zHigh }
}

function polygonArea(ring: readonly Vec2[]): number {
    let a = 0
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        a += (ring[j].x + ring[i].x) * (ring[j].y - ring[i].y)
    }
    return Math.abs(a) / 2
}

function ringCentroid(ring: readonly Vec2[]): Vec2 {
    const n = ring.length || 1
    let sx = 0, sy = 0
    for (const p of ring) { sx += p.x; sy += p.y }
    return { x: sx / n, y: sy / n }
}

function ringBounds(ring: readonly Vec2[]): { minX: number; minY: number; maxX: number; maxY: number } {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const p of ring) {
        if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x
        if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y
    }
    return { minX, minY, maxX, maxY }
}

function gridHasAnyInterior(
    bbox: { minX: number; minY: number; maxX: number; maxY: number },
    grid: number,
    footprint: WorldFootprint,
    holes: readonly (readonly Vec2[])[],
): boolean {
    const zMid = (footprint.zLow + footprint.zHigh) / 2
    for (let iy = 1; iy < grid; iy++) {
        for (let ix = 1; ix < grid; ix++) {
            const p = {
                x: bbox.minX + ((bbox.maxX - bbox.minX) * ix) / grid,
                y: bbox.minY + ((bbox.maxY - bbox.minY) * iy) / grid,
                z: zMid,
            }
            if (!pointInFootprint(p, footprint)) continue
            let inHole = false
            for (const h of holes) {
                if (pointInFootprint(p, { ring: h.map((q) => ({ x: q.x, y: q.y })), zLow: footprint.zLow, zHigh: footprint.zHigh })) { inHole = true; break }
            }
            if (!inHole) return true
        }
    }
    return false
}

/** Bounded human-readable spawn diagnostic (report + DEV). Pure. */
export function describeSpawnResult(r: SpawnResult): string {
    const L: string[] = ['=== TARGETED WALKTHROUGH SPAWN ===']
    if (r.ok) {
        L.push(`RESULT = SAFE_SPAWN`)
        L.push(`SPAWN = (${r.spawn.x.toFixed(2)}, ${r.spawn.y.toFixed(2)}, ${r.spawn.z.toFixed(2)})`)
        L.push(`EYE_HEIGHT = ${r.eyeHeight.toFixed(2)}`)
        L.push(`PROVENANCE = ${r.provenance}`)
        L.push(`WALL_CLEARANCE = ${Number.isFinite(r.wallClearance) ? r.wallClearance.toFixed(2) : 'INF'}`)
    } else {
        L.push(`RESULT = NO_SAFE_WALKTHROUGH_SPAWN`)
        L.push(`CODE = ${r.code}`)
        L.push(`REASON = ${r.reason}`)
    }
    L.push('PLANNING_VOLUME_IS_SPAWN_AUTHORITY = NO')
    L.push('EQUIPMENT_IS_SPAWN_AUTHORITY = NO')
    L.push('COLLISION_ACTIVE = YES')
    return L.join('\n')
}

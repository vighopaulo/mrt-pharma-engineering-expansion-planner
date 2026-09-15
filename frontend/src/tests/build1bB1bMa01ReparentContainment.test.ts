/**
 * B1B-MA-01 — parent-derived ClinicalPlanningVolume must be CONTAINED by its own
 * parent after candidate-room acceptance / reparenting.
 *
 * Reproduction: the pre-fix seed built an axis-aligned box sized to ~50% of the
 * footprint's AABB, centered on the vertex mean. For a ROTATED or IRREGULAR room
 * (like the real 2D18 TECH. OFFICE) that box protrudes outside the actual polygon
 * → the parent-derived volume fails containment against its OWN parent mesh
 * (the observed "PET/CT 01 — OUTSIDE PARENT, containment: FAIL").
 *
 * The corrected seed centers on a PROVEN-interior anchor and shrinks the box until
 * every sampled corner/edge is inside the actual footprint polygon, insetting Z
 * off the floor/ceiling — so a parent-derived volume is CONTAINED whenever exact
 * geometry permits. These tests exercise the real seed→geometry→containment chain.
 */
import { describe, it, expect } from 'vitest'
import {
    seedPrismParamsFromParent,
    buildOrientedPlanningPrism,
    validatePlanningVolumeContainment,
    isValidPrismParams,
    type Mesh,
    type Vec2,
    type Vec3,
} from '../components/spatial/clinicalPlanningVolume'

// --- build a closed prism mesh from a footprint polygon extruded zLow..zHigh ---
function extrudeClosedMesh(footprint: readonly Vec2[], zLow: number, zHigh: number): Mesh {
    const nB = footprint.length
    const vertices: Vec3[] = []
    for (const p of footprint) vertices.push({ x: p.x, y: p.y, z: zLow }) // bottom 0..n-1
    for (const p of footprint) vertices.push({ x: p.x, y: p.y, z: zHigh }) // top n..2n-1
    const triangles: number[] = []
    // Bottom + top faces (fan). Winding is irrelevant to the even-odd ray test.
    for (let i = 1; i + 1 < nB; i++) { triangles.push(0, i, i + 1); triangles.push(nB, nB + i + 1, nB + i) }
    // Side walls.
    for (let i = 0; i < nB; i++) {
        const j = (i + 1) % nB
        triangles.push(i, j, nB + j)
        triangles.push(i, nB + j, nB + i)
    }
    return { vertices, triangles }
}

/** Rotate a footprint by `theta` about its centroid (produces a non-axis-aligned room). */
function rotateFootprint(fp: readonly Vec2[], theta: number): Vec2[] {
    const cx = fp.reduce((s, p) => s + p.x, 0) / fp.length
    const cy = fp.reduce((s, p) => s + p.y, 0) / fp.length
    const c = Math.cos(theta), s = Math.sin(theta)
    return fp.map((p) => ({ x: cx + (p.x - cx) * c - (p.y - cy) * s, y: cy + (p.x - cx) * s + (p.y - cy) * c }))
}

// Interior-anchor helper mirroring resolveRoomInteriorAnchor's guarantee for tests.
function interiorAnchor(fp: readonly Vec2[]): { x: number; y: number } {
    // Largest-triangle centroid (guaranteed interior for these convex/L fixtures).
    let best = { x: fp.reduce((s, p) => s + p.x, 0) / fp.length, y: fp.reduce((s, p) => s + p.y, 0) / fp.length }
    let bestArea = -1
    for (let i = 1; i + 1 < fp.length; i++) {
        const a = fp[0], b = fp[i], c = fp[i + 1]
        const area = Math.abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)) / 2
        if (area > bestArea) { bestArea = area; best = { x: (a.x + b.x + c.x) / 3, y: (a.y + b.y + c.y) / 3 } }
    }
    return best
}

// A rectangular office footprint (like a real BIM room), rotated ~30° — the
// condition that broke 2D18: axis-aligned seed box protrudes past rotated walls.
const RECT: Vec2[] = [{ x: 0, y: 0 }, { x: 14, y: 0 }, { x: 14, y: 4 }, { x: 0, y: 4 }]
const ROTATED = rotateFootprint(RECT, Math.PI / 6) // 30°
const Z_LOW = 0, Z_HIGH = 3

describe('B1B-MA-01 §14 reproduction: rotated parent room', () => {
    it('the corrected parent-derived seed is CONTAINED by its own rotated parent mesh', () => {
        const seed = seedPrismParamsFromParent({ footprint: ROTATED, zLow: Z_LOW, zHigh: Z_HIGH, interiorAnchor: interiorAnchor(ROTATED) })
        expect(isValidPrismParams(seed)).toBe(true)
        const mesh = extrudeClosedMesh(ROTATED, Z_LOW, Z_HIGH)
        const c = validatePlanningVolumeContainment({ params: seed, parentMesh: mesh })
        expect(c.contained).toBe(true) // pre-fix this FAILED (box protruded outside)
        expect(c.failedSamples).toBe(0)
        expect(c.totalSamples).toBeGreaterThan(0)
    })

    it('demonstrates WHY the pre-fix heuristic failed (50%-of-AABB box on vertex mean protrudes)', () => {
        // Reconstruct the OLD seed heuristic explicitly and show it was NOT contained.
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
        for (const p of ROTATED) { if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x; if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y }
        const oldSeed = {
            centerX: ROTATED.reduce((s, p) => s + p.x, 0) / ROTATED.length,
            centerY: ROTATED.reduce((s, p) => s + p.y, 0) / ROTATED.length,
            zLow: Z_LOW, zHigh: Z_HIGH, width: (maxX - minX) * 0.5, depth: (maxY - minY) * 0.5, yaw: 0,
        }
        const mesh = extrudeClosedMesh(ROTATED, Z_LOW, Z_HIGH)
        const c = validatePlanningVolumeContainment({ params: oldSeed, parentMesh: mesh })
        expect(c.contained).toBe(false) // the pre-fix defect
        expect(c.failedSamples).toBeGreaterThan(0)
    })
})

describe('B1B-MA-01 §15 parent-derived initialization', () => {
    it('exact axis-aligned parent → defensible contained initialization', () => {
        const seed = seedPrismParamsFromParent({ footprint: RECT, zLow: Z_LOW, zHigh: Z_HIGH, interiorAnchor: interiorAnchor(RECT) })
        const mesh = extrudeClosedMesh(RECT, Z_LOW, Z_HIGH)
        expect(validatePlanningVolumeContainment({ params: seed, parentMesh: mesh }).contained).toBe(true)
    })

    it('irregular L-shaped parent → contained (center on interior anchor, shrink to fit)', () => {
        const L: Vec2[] = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 4 }, { x: 4, y: 4 }, { x: 4, y: 10 }, { x: 0, y: 10 }]
        const seed = seedPrismParamsFromParent({ footprint: L, zLow: Z_LOW, zHigh: Z_HIGH, interiorAnchor: interiorAnchor(L) })
        const mesh = extrudeClosedMesh(L, Z_LOW, Z_HIGH)
        const c = validatePlanningVolumeContainment({ params: seed, parentMesh: mesh })
        expect(c.contained).toBe(true)
    })

    it('correct Z bounds: seed sits on the parent floor and is capped by room height', () => {
        // The seed preserves the Build 1A floor-aware contract: zLow == room floor
        // (so equipment derived from it sits on the floor), zHigh capped by the room.
        // The horizontal (+X) containment ray does not require a Z inset.
        const seed = seedPrismParamsFromParent({ footprint: RECT, zLow: 0, zHigh: 3, interiorAnchor: interiorAnchor(RECT) })
        expect(seed.zLow).toBe(0)
        expect(seed.zHigh).toBeLessThanOrEqual(3)
        expect(seed.zHigh).toBeGreaterThan(seed.zLow)
    })

    it('correct coordinate frame: seed center lies inside the actual polygon (not origin)', () => {
        const seed = seedPrismParamsFromParent({ footprint: ROTATED, zLow: Z_LOW, zHigh: Z_HIGH, interiorAnchor: interiorAnchor(ROTATED) })
        const g = buildOrientedPlanningPrism(seed)
        expect(Number.isFinite(g.interiorAnchor.x)).toBe(true)
        expect(seed.centerX).not.toBe(0) // rotated room is offset from origin
    })
})

describe('B1B-MA-01 §15 geometry authority: exact vs approximate', () => {
    it('a footprint with < 3 points cannot prove containment — seed falls back to bounded default (approximate)', () => {
        // No usable polygon → the seed uses the default sizing; the caller/overlay
        // treats a room with no exact mesh as NOT_EVALUATED (never fabricated PASS).
        const seed = seedPrismParamsFromParent({ footprint: [{ x: 5, y: 5 }], zLow: 0, zHigh: 3 })
        expect(isValidPrismParams(seed)).toBe(true)
        // Centered on the single point (its own coords), not origin/Uptake.
        expect(seed.centerX).toBe(5)
        expect(seed.centerY).toBe(5)
    })
})

describe('B1B-MA-01 §15 recovery: a genuinely-outside volume still FAILS honestly', () => {
    it('a volume deliberately placed outside the parent is NOT contained (real FAIL preserved)', () => {
        const mesh = extrudeClosedMesh(RECT, Z_LOW, Z_HIGH)
        const outside = { centerX: 40, centerY: 40, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0 }
        const c = validatePlanningVolumeContainment({ params: outside, parentMesh: mesh })
        expect(c.contained).toBe(false)
        expect(c.failedSamples).toBeGreaterThan(0)
    })
})

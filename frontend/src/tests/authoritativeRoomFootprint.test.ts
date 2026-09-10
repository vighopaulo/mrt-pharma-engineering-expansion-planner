import { describe, it, expect } from 'vitest'
import {
    deriveAuthoritativeRoomFootprint,
    resolveRoomInteriorAnchor,
    cleanLoop,
    polygonArea,
    pointInPolygon,
    signedArea,
    type RoomMesh,
    type Vec2,
} from '../components/spatial/authoritativeRoomFootprint'

/** Build a flat floor mesh (z=0) by triangulating a polygon fan + a matching
 *  top so the derivation sees a floor band. For footprint tests a single flat
 *  floor slab is sufficient (all vertices at z=0). */
function flatFloorMesh(loop: Vec2[]): RoomMesh {
    const vertices = loop.map((p) => ({ x: p.x, y: p.y, z: 0 }))
    const triangles: number[] = []
    for (let i = 1; i + 1 < loop.length; i++) { triangles.push(0, i, i + 1) }
    return { vertices, triangles }
}

const RECT: Vec2[] = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 6 }, { x: 0, y: 6 }]

describe('§31 rectangular space', () => {
    it('rectangular shell => same rectangle (not distorted)', () => {
        const fp = deriveAuthoritativeRoomFootprint(flatFloorMesh(RECT))
        expect(fp.geometryQuality).toBe('EXACT_ROOM_BOUNDARY')
        expect(polygonArea(fp.outerLoop)).toBeCloseTo(60, 3)
        expect(fp.outerLoop.length).toBe(4)
    })
})

describe('§32 concave (L-shaped) space', () => {
    const L: Vec2[] = [
        { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 4 },
        { x: 4, y: 4 }, { x: 4, y: 8 }, { x: 0, y: 8 },
    ]
    it('preserves the L-shape (6 vertices, correct area)', () => {
        const fp = deriveAuthoritativeRoomFootprint(flatFloorMesh(L))
        expect(fp.geometryQuality).toBe('EXACT_ROOM_BOUNDARY')
        // L area = 10*4 + 4*4 = 56.
        expect(polygonArea(fp.outerLoop)).toBeCloseTo(56, 3)
        expect(fp.outerLoop.length).toBe(6)
        // Not collapsed to bbox (bbox area would be 80).
        expect(polygonArea(fp.outerLoop)).toBeLessThan(80)
    })
})

describe('§33 rotated room', () => {
    it('a rotated rectangle stays rotated (not axis-aligned)', () => {
        // Rectangle rotated 30°.
        const ang = Math.PI / 6
        const rot = (p: Vec2): Vec2 => ({ x: p.x * Math.cos(ang) - p.y * Math.sin(ang), y: p.x * Math.sin(ang) + p.y * Math.cos(ang) })
        const fp = deriveAuthoritativeRoomFootprint(flatFloorMesh(RECT.map(rot)))
        expect(fp.outerLoop.length).toBe(4)
        expect(polygonArea(fp.outerLoop)).toBeCloseTo(60, 2)
        // At least one edge is not axis-aligned.
        const edgesAxisAligned = fp.outerLoop.every((p, i) => {
            const q = fp.outerLoop[(i + 1) % fp.outerLoop.length]
            return Math.abs(p.x - q.x) < 1e-6 || Math.abs(p.y - q.y) < 1e-6
        })
        expect(edgesAxisAligned).toBe(false)
    })
})

describe('§34 hole', () => {
    it('interior hole remains excluded (reported as a hole)', () => {
        // Outer square floor + a smaller inner square hole. Build as an annulus
        // mesh: triangles between outer and inner rings (no triangle covers the hole).
        const outer: Vec2[] = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }]
        const inner: Vec2[] = [{ x: 4, y: 4 }, { x: 6, y: 4 }, { x: 6, y: 6 }, { x: 4, y: 6 }]
        const vertices = [...outer, ...inner].map((p) => ({ x: p.x, y: p.y, z: 0 }))
        // Quad strip between outer[i] and inner[i] (both rings same winding, 4 verts).
        const tri: number[] = []
        for (let i = 0; i < 4; i++) {
            const o0 = i, o1 = (i + 1) % 4
            const h0 = 4 + i, h1 = 4 + ((i + 1) % 4)
            tri.push(o0, o1, h1, o0, h1, h0)
        }
        const fp = deriveAuthoritativeRoomFootprint({ vertices, triangles: tri })
        expect(fp.geometryQuality).toBe('EXACT_ROOM_BOUNDARY')
        expect(polygonArea(fp.outerLoop)).toBeCloseTo(100, 2)
        expect(fp.holes.length).toBe(1)
        expect(polygonArea(fp.holes[0])).toBeCloseTo(4, 2)
    })
})

describe('§35 duplicate vertex cleanup', () => {
    it('deduplicates consecutive near-duplicate points', () => {
        const withDup: Vec2[] = [{ x: 0, y: 0 }, { x: 0.005, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 6 }, { x: 0, y: 6 }]
        const cleaned = cleanLoop(withDup, 0.02)
        expect(cleaned.length).toBe(4)
    })
})

describe('§36 collinear cleanup', () => {
    it('removes unnecessary collinear midpoints without distortion', () => {
        const withMid: Vec2[] = [{ x: 0, y: 0 }, { x: 5, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 6 }, { x: 0, y: 6 }]
        const cleaned = cleanLoop(withMid, 0.02)
        expect(cleaned.length).toBe(4)
        expect(polygonArea(cleaned)).toBeCloseTo(60, 3)
    })
})

describe('§37 interior anchor (concave)', () => {
    it('anchor lies inside a concave polygon', () => {
        const L: Vec2[] = [
            { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 4 },
            { x: 4, y: 4 }, { x: 4, y: 8 }, { x: 0, y: 8 },
        ]
        const anchor = resolveRoomInteriorAnchor({ outerLoop: L })
        expect(pointInPolygon(anchor, L)).toBe(true)
    })
    it('rectangle anchor is the center', () => {
        const anchor = resolveRoomInteriorAnchor({ outerLoop: RECT })
        expect(anchor.x).toBeCloseTo(5, 6)
        expect(anchor.y).toBeCloseTo(3, 6)
    })
})

describe('§30 camera invariance (pure — no camera input)', () => {
    it('same mesh yields identical world footprint every call', () => {
        const m = flatFloorMesh(RECT)
        const a = deriveAuthoritativeRoomFootprint(m)
        const b = deriveAuthoritativeRoomFootprint(m)
        expect(b.outerLoop).toEqual(a.outerLoop)
        expect(b.floorZ).toBe(a.floorZ)
    })
})

describe('§38 exact classification', () => {
    it('successful extraction => EXACT_ROOM_BOUNDARY', () => {
        expect(deriveAuthoritativeRoomFootprint(flatFloorMesh(RECT)).geometryQuality).toBe('EXACT_ROOM_BOUNDARY')
    })
})

describe('§39 failed extraction', () => {
    it('empty/degenerate mesh => NOT_AVAILABLE (no fabricated rectangle)', () => {
        expect(deriveAuthoritativeRoomFootprint({ vertices: [], triangles: [] }).geometryQuality).toBe('NOT_AVAILABLE')
        expect(deriveAuthoritativeRoomFootprint({ vertices: [{ x: 0, y: 0, z: 0 }], triangles: [] }).geometryQuality).toBe('NOT_AVAILABLE')
        const degenerate = deriveAuthoritativeRoomFootprint({ vertices: [{ x: 0, y: 0, z: 0 }, { x: 1, y: 0, z: 0 }, { x: 2, y: 0, z: 0 }], triangles: [0, 1, 2] })
        expect(degenerate.geometryQuality).toBe('NOT_AVAILABLE')
    })
})

describe('signedArea helper', () => {
    it('CCW positive, CW negative', () => {
        expect(signedArea(RECT)).toBeGreaterThan(0)
        expect(signedArea([...RECT].reverse())).toBeLessThan(0)
    })
})

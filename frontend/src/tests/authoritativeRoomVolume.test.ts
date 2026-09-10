import { describe, it, expect } from 'vitest'
import {
    characterizeAuthoritativeRoomVolume,
    type RoomMesh,
    type Vec3,
} from '../components/spatial/authoritativeRoomFootprint'

/** Build a closed rectangular prism (box) mesh from min/max corners. */
function boxMesh(lo: Vec3, hi: Vec3): RoomMesh {
    const v: Vec3[] = [
        { x: lo.x, y: lo.y, z: lo.z }, // 0
        { x: hi.x, y: lo.y, z: lo.z }, // 1
        { x: hi.x, y: hi.y, z: lo.z }, // 2
        { x: lo.x, y: hi.y, z: lo.z }, // 3
        { x: lo.x, y: lo.y, z: hi.z }, // 4
        { x: hi.x, y: lo.y, z: hi.z }, // 5
        { x: hi.x, y: hi.y, z: hi.z }, // 6
        { x: lo.x, y: hi.y, z: hi.z }, // 7
    ]
    // 12 triangles, consistent winding so each edge is shared by exactly 2 tris.
    const t = [
        0, 2, 1, 0, 3, 2, // bottom
        4, 5, 6, 4, 6, 7, // top
        0, 1, 5, 0, 5, 4, // front (y=lo)
        1, 2, 6, 1, 6, 5, // right (x=hi)
        2, 3, 7, 2, 7, 6, // back (y=hi)
        3, 0, 4, 3, 4, 7, // left (x=lo)
    ]
    return { vertices: v, triangles: t }
}

describe('§29 closed rectangular room', () => {
    it('is a closed single-component prism with correct z extent', () => {
        const c = characterizeAuthoritativeRoomVolume(boxMesh({ x: 0, y: 0, z: 0 }, { x: 10, y: 6, z: 3 }))
        expect(c.closedMesh).toBe(true)
        expect(c.componentCount).toBe(1)
        expect(c.zLow).toBeCloseTo(0, 6)
        expect(c.zHigh).toBeCloseTo(3, 6)
        expect(c.height).toBeCloseTo(3, 6)
        // A box has 2 horizontal faces (4 tris) and 4 vertical faces (8 tris).
        expect(c.horizontalFaceCount).toBe(4)
        expect(c.verticalFaceCount).toBe(8)
        expect(c.worldRangeLow).toEqual({ x: 0, y: 0, z: 0 })
        expect(c.worldRangeHigh).toEqual({ x: 10, y: 6, z: 3 })
    })
})

describe('§30 rotated room', () => {
    it('world orientation preserved (range reflects rotation)', () => {
        const ang = Math.PI / 5
        const box = boxMesh({ x: 0, y: 0, z: 0 }, { x: 8, y: 4, z: 3 })
        const rot: RoomMesh = {
            vertices: box.vertices.map((p) => ({ x: p.x * Math.cos(ang) - p.y * Math.sin(ang), y: p.x * Math.sin(ang) + p.y * Math.cos(ang), z: p.z })),
            triangles: box.triangles,
        }
        const c = characterizeAuthoritativeRoomVolume(rot)
        expect(c.closedMesh).toBe(true)
        expect(c.zHigh - c.zLow).toBeCloseTo(3, 6)
        // Rotated: XY range is larger than the un-rotated 8x4 (proves not axis-aligned collapse).
        expect(c.worldRangeHigh.x - c.worldRangeLow.x).toBeGreaterThan(8)
    })
})

describe('§31 multi-component', () => {
    it('two disjoint boxes => componentCount 2 (never silently merged)', () => {
        const a = boxMesh({ x: 0, y: 0, z: 0 }, { x: 2, y: 2, z: 2 })
        const b = boxMesh({ x: 10, y: 10, z: 0 }, { x: 12, y: 12, z: 2 })
        const merged: RoomMesh = {
            vertices: [...a.vertices, ...b.vertices],
            triangles: [...a.triangles, ...b.triangles.map((i) => i + a.vertices.length)],
        }
        expect(characterizeAuthoritativeRoomVolume(merged).componentCount).toBe(2)
    })
})

describe('§32 camera invariance (pure — no camera input)', () => {
    it('identical mesh yields identical characterization', () => {
        const m = boxMesh({ x: 0, y: 0, z: 0 }, { x: 10, y: 6, z: 3 })
        const a = characterizeAuthoritativeRoomVolume(m)
        const b = characterizeAuthoritativeRoomVolume(m)
        expect(b).toEqual(a)
    })
})

describe('open mesh', () => {
    it('a single triangle is not a closed mesh', () => {
        const c = characterizeAuthoritativeRoomVolume({ vertices: [{ x: 0, y: 0, z: 0 }, { x: 1, y: 0, z: 0 }, { x: 0, y: 1, z: 0 }], triangles: [0, 1, 2] })
        expect(c.closedMesh).toBe(false)
        expect(c.triangleCount).toBe(1)
    })
})

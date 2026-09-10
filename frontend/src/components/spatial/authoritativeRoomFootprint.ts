/**
 * authoritativeRoomFootprint — pure, Bentley-free derivation of a TRUE room
 * footprint from an authoritative IfcSpace geometry (mesh / polyface / loops).
 *
 * The live diagnostic proved the target space has EXACT_SPACE_GEOMETRY, so the
 * range rectangle must be replaced with the real room boundary. This seam takes
 * the extracted world-space triangle mesh (or explicit loops) and derives the
 * floor-level perimeter loop(s):
 *   - collect the lowest horizontal band of triangle edges (the floor slice);
 *   - keep only BOUNDARY edges (used by exactly one triangle) → the room outline;
 *   - stitch edges into ordered closed loops;
 *   - dedupe near-duplicate + collinear vertices within a bounded tolerance;
 *   - the largest-area loop is the outer boundary; the rest are holes;
 *   - concavity + rotation are preserved (never collapsed to an axis-aligned bbox).
 *
 * All coordinates stay in BIM/world space. Bentley-free: the extractor feeds
 * world vertices + triangle indices; this seam does the geometry.
 */

export interface Vec3 { x: number; y: number; z: number }
export interface Vec2 { x: number; y: number }

export interface RoomMesh {
    /** World-space vertices. */
    vertices: readonly Vec3[]
    /** Triangle vertex indices (length multiple of 3). */
    triangles: readonly number[]
}

export type FootprintGeometryQuality = 'EXACT_ROOM_BOUNDARY' | 'NOT_AVAILABLE'

export interface RoomFootprintResult {
    /** Outer boundary loop (world XY at floorZ), CCW, closed implicitly. */
    outerLoop: Vec2[]
    /** Interior holes (each a loop), if any. */
    holes: Vec2[][]
    /** The floor elevation the footprint sits at (world Z). */
    floorZ: number
    geometryQuality: FootprintGeometryQuality
    source: 'AUTHORITATIVE_IFCSPACE_GEOMETRY_STREAM'
}

const DEFAULT_TOL = 0.02 // 2 cm — bounded; tight enough not to distort a room.

function almostEqual(a: number, b: number, tol: number): boolean { return Math.abs(a - b) <= tol }
function ptEqual(a: Vec2, b: Vec2, tol: number): boolean { return almostEqual(a.x, b.x, tol) && almostEqual(a.y, b.y, tol) }

/** Signed area (shoelace). Positive => CCW. */
export function signedArea(loop: readonly Vec2[]): number {
    let s = 0
    for (let i = 0; i < loop.length; i++) {
        const a = loop[i]
        const b = loop[(i + 1) % loop.length]
        s += a.x * b.y - b.x * a.y
    }
    return s / 2
}

export function polygonArea(loop: readonly Vec2[]): number { return Math.abs(signedArea(loop)) }

/** Remove consecutive duplicate + collinear vertices within tolerance. */
export function cleanLoop(loop: readonly Vec2[], tol = DEFAULT_TOL): Vec2[] {
    // 1) drop consecutive duplicates.
    const dedup: Vec2[] = []
    for (const p of loop) {
        if (dedup.length === 0 || !ptEqual(dedup[dedup.length - 1], p, tol)) dedup.push({ x: p.x, y: p.y })
    }
    while (dedup.length > 1 && ptEqual(dedup[0], dedup[dedup.length - 1], tol)) dedup.pop()
    if (dedup.length < 3) return dedup
    // 2) drop collinear middle vertices (cross product ~ 0, bounded by tol).
    const out: Vec2[] = []
    const n = dedup.length
    for (let i = 0; i < n; i++) {
        const prev = dedup[(i - 1 + n) % n]
        const cur = dedup[i]
        const next = dedup[(i + 1) % n]
        const ux = cur.x - prev.x, uy = cur.y - prev.y
        const vx = next.x - cur.x, vy = next.y - cur.y
        const cross = ux * vy - uy * vx
        const scale = Math.hypot(ux, uy) * Math.hypot(vx, vy)
        // Keep the vertex unless it is (near) collinear with its neighbours.
        if (scale === 0 || Math.abs(cross) > tol * Math.max(1, scale)) out.push(cur)
    }
    return out.length >= 3 ? out : dedup
}

/** A single undirected edge keyed for boundary detection. */
function edgeKey(ia: number, ib: number): string { return ia < ib ? `${ia}_${ib}` : `${ib}_${ia}` }

/**
 * Derive the room footprint from an authoritative world mesh. Returns
 * NOT_AVAILABLE when the mesh has no usable floor slice / boundary loop (the
 * caller must NOT silently fall back to a range rectangle).
 */
export function deriveAuthoritativeRoomFootprint(mesh: RoomMesh, tol = DEFAULT_TOL): RoomFootprintResult {
    const empty: RoomFootprintResult = { outerLoop: [], holes: [], floorZ: 0, geometryQuality: 'NOT_AVAILABLE', source: 'AUTHORITATIVE_IFCSPACE_GEOMETRY_STREAM' }
    const V = mesh.vertices
    const T = mesh.triangles
    if (V.length < 3 || T.length < 3) return empty

    // Floor elevation = min Z across the mesh; take triangles whose vertices are
    // (near) at that floor band. IfcSpace shells include a floor face at zLow.
    let minZ = Infinity, maxZ = -Infinity
    for (const v of V) { if (v.z < minZ) minZ = v.z; if (v.z > maxZ) maxZ = v.z }
    if (!Number.isFinite(minZ)) return empty
    const band = Math.max(tol, (maxZ - minZ) * 0.02)

    // Collect boundary edges of the floor-band triangles. A boundary edge is used
    // by exactly one floor triangle → it lies on the room perimeter (or a hole).
    const edgeCount = new Map<string, { a: number; b: number; n: number }>()
    const nearFloor = (i: number) => V[i] && V[i].z <= minZ + band
    for (let t = 0; t < T.length; t += 3) {
        const i0 = T[t], i1 = T[t + 1], i2 = T[t + 2]
        // A floor triangle: all three vertices in the floor band.
        if (!(nearFloor(i0) && nearFloor(i1) && nearFloor(i2))) continue
        for (const [ia, ib] of [[i0, i1], [i1, i2], [i2, i0]] as const) {
            const k = edgeKey(ia, ib)
            const e = edgeCount.get(k)
            if (e) e.n += 1
            else edgeCount.set(k, { a: ia, b: ib, n: 1 })
        }
    }
    // Boundary edges appear exactly once.
    const boundaryEdges = [...edgeCount.values()].filter((e) => e.n === 1)
    if (boundaryEdges.length < 3) return empty

    // Stitch boundary edges into ordered loops by walking shared vertices.
    const adj = new Map<number, number[]>()
    for (const e of boundaryEdges) {
        ; (adj.get(e.a) ?? adj.set(e.a, []).get(e.a)!).push(e.b)
            ; (adj.get(e.b) ?? adj.set(e.b, []).get(e.b)!).push(e.a)
    }
    const usedEdge = new Set<string>()
    const loops: number[][] = []
    for (const start of adj.keys()) {
        // Find an unused edge from start.
        const neighbours = adj.get(start) ?? []
        for (const first of neighbours) {
            if (usedEdge.has(edgeKey(start, first))) continue
            // Walk the loop.
            const loop: number[] = [start]
            let prev = start
            let cur = first
            usedEdge.add(edgeKey(prev, cur))
            let guard = 0
            while (cur !== start && guard++ < boundaryEdges.length + 2) {
                loop.push(cur)
                const nexts = (adj.get(cur) ?? []).filter((x) => x !== prev && !usedEdge.has(edgeKey(cur, x)))
                if (nexts.length === 0) break
                const next = nexts[0]
                usedEdge.add(edgeKey(cur, next))
                prev = cur
                cur = next
            }
            if (loop.length >= 3 && cur === start) loops.push(loop)
        }
    }
    if (loops.length === 0) return empty

    // Convert index loops to XY loops at floorZ, clean them.
    const xyLoops = loops
        .map((idx) => cleanLoop(idx.map((i) => ({ x: V[i].x, y: V[i].y })), tol))
        .filter((l) => l.length >= 3 && polygonArea(l) > tol * tol)
    if (xyLoops.length === 0) return empty

    // Largest-area loop is the outer boundary; the rest are holes.
    xyLoops.sort((a, b) => polygonArea(b) - polygonArea(a))
    const outer = xyLoops[0]
    const holes = xyLoops.slice(1)
    // Normalize outer to CCW for downstream consistency.
    const outerCCW = signedArea(outer) < 0 ? [...outer].reverse() : outer

    return {
        outerLoop: outerCCW,
        holes,
        floorZ: minZ,
        geometryQuality: 'EXACT_ROOM_BOUNDARY',
        source: 'AUTHORITATIVE_IFCSPACE_GEOMETRY_STREAM',
    }
}

/**
 * Deterministic interior anchor for a (possibly concave) polygon. The arithmetic
 * centroid can fall outside a concave room, so if it does we fall back to the
 * centroid of the polygon's largest triangle (guaranteed interior). Pure.
 */
export function resolveRoomInteriorAnchor(input: { outerLoop: readonly Vec2[]; holes?: readonly (readonly Vec2[])[] }): Vec2 {
    const loop = input.outerLoop
    if (loop.length === 0) return { x: 0, y: 0 }
    if (loop.length < 3) {
        return { x: loop.reduce((s, p) => s + p.x, 0) / loop.length, y: loop.reduce((s, p) => s + p.y, 0) / loop.length }
    }
    const avg = { x: loop.reduce((s, p) => s + p.x, 0) / loop.length, y: loop.reduce((s, p) => s + p.y, 0) / loop.length }
    if (pointInPolygon(avg, loop) && !(input.holes ?? []).some((h) => pointInPolygon(avg, h))) return avg

    // Fan-triangulate from vertex 0; pick the largest triangle's centroid.
    let best = avg
    let bestArea = -1
    for (let i = 1; i + 1 < loop.length; i++) {
        const a = loop[0], b = loop[i], c = loop[i + 1]
        const area = Math.abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)) / 2
        const centroid = { x: (a.x + b.x + c.x) / 3, y: (a.y + b.y + c.y) / 3 }
        if (area > bestArea && pointInPolygon(centroid, loop) && !(input.holes ?? []).some((h) => pointInPolygon(centroid, h))) {
            bestArea = area
            best = centroid
        }
    }
    return best
}

/** Ray-cast point-in-polygon (even-odd rule). */
export function pointInPolygon(p: Vec2, loop: readonly Vec2[]): boolean {
    let inside = false
    for (let i = 0, j = loop.length - 1; i < loop.length; j = i++) {
        const a = loop[i], b = loop[j]
        const intersects = (a.y > p.y) !== (b.y > p.y) && p.x < ((b.x - a.x) * (p.y - a.y)) / ((b.y - a.y) || 1e-12) + a.x
        if (intersects) inside = !inside
    }
    return inside
}

// ---------------------------------------------------------------------------
// 3D volume characterization (pure) — describe the space BEFORE projecting it
// ---------------------------------------------------------------------------

export interface RoomVolumeCharacterization {
    zLow: number
    zHigh: number
    height: number
    vertexCount: number
    triangleCount: number
    /** Connected components by shared vertex index (never silently merged). */
    componentCount: number
    /** Every edge shared by exactly two triangles => a watertight (closed) mesh. */
    closedMesh: boolean
    horizontalFaceCount: number
    verticalFaceCount: number
    worldRangeLow: Vec3
    worldRangeHigh: Vec3
}

/** Triangle normal (unnormalized) for orientation classification. */
function triNormal(a: Vec3, b: Vec3, c: Vec3): Vec3 {
    const ux = b.x - a.x, uy = b.y - a.y, uz = b.z - a.z
    const vx = c.x - a.x, vy = c.y - a.y, vz = c.z - a.z
    return { x: uy * vz - uz * vy, y: uz * vx - ux * vz, z: ux * vy - uy * vx }
}

/**
 * Characterize the authoritative 3D room volume from its world mesh. Pure:
 * classifies faces by normal (horizontal vs vertical), counts connected
 * components (union-find over shared vertices), and tests watertightness
 * (every undirected edge used by exactly two triangles). No camera input.
 */
export function characterizeAuthoritativeRoomVolume(mesh: RoomMesh): RoomVolumeCharacterization {
    const V = mesh.vertices
    const T = mesh.triangles
    let zLow = Infinity, zHigh = -Infinity
    let xLow = Infinity, yLow = Infinity, xHigh = -Infinity, yHigh = -Infinity
    for (const v of V) {
        if (v.z < zLow) zLow = v.z; if (v.z > zHigh) zHigh = v.z
        if (v.x < xLow) xLow = v.x; if (v.x > xHigh) xHigh = v.x
        if (v.y < yLow) yLow = v.y; if (v.y > yHigh) yHigh = v.y
    }
    if (!Number.isFinite(zLow)) { zLow = 0; zHigh = 0 }
    if (!Number.isFinite(xLow)) { xLow = 0; xHigh = 0; yLow = 0; yHigh = 0 }

    const triCount = Math.floor(T.length / 3)
    // Face orientation.
    let horizontal = 0, vertical = 0
    for (let t = 0; t + 2 < T.length; t += 3) {
        const a = V[T[t]], b = V[T[t + 1]], c = V[T[t + 2]]
        if (!a || !b || !c) continue
        const n = triNormal(a, b, c)
        const mag = Math.hypot(n.x, n.y, n.z) || 1
        const nz = Math.abs(n.z) / mag
        if (nz > 0.85) horizontal += 1
        else if (nz < 0.15) vertical += 1
    }

    // Connected components (union-find over vertex indices used by triangles).
    const parent = new Array(V.length).fill(0).map((_, i) => i)
    const find = (x: number): number => { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x] } return x }
    const union = (a: number, b: number) => { const ra = find(a), rb = find(b); if (ra !== rb) parent[ra] = rb }
    const usedVerts = new Set<number>()
    for (let t = 0; t + 2 < T.length; t += 3) {
        const i0 = T[t], i1 = T[t + 1], i2 = T[t + 2]
        usedVerts.add(i0); usedVerts.add(i1); usedVerts.add(i2)
        union(i0, i1); union(i1, i2)
    }
    const roots = new Set<number>()
    for (const v of usedVerts) roots.add(find(v))
    const componentCount = roots.size

    // Watertightness: undirected edge usage count.
    const edgeUse = new Map<string, number>()
    for (let t = 0; t + 2 < T.length; t += 3) {
        const i0 = T[t], i1 = T[t + 1], i2 = T[t + 2]
        for (const [a, b] of [[i0, i1], [i1, i2], [i2, i0]] as const) {
            const k = a < b ? `${a}_${b}` : `${b}_${a}`
            edgeUse.set(k, (edgeUse.get(k) ?? 0) + 1)
        }
    }
    let closedMesh = triCount > 0
    for (const n of edgeUse.values()) { if (n !== 2) { closedMesh = false; break } }

    return {
        zLow, zHigh, height: zHigh - zLow,
        vertexCount: usedVerts.size,
        triangleCount: triCount,
        componentCount,
        closedMesh,
        horizontalFaceCount: horizontal,
        verticalFaceCount: vertical,
        worldRangeLow: { x: xLow, y: yLow, z: zLow },
        worldRangeHigh: { x: xHigh, y: yHigh, z: zHigh },
    }
}

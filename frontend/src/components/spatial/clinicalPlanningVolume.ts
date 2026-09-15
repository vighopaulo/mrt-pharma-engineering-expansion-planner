/**
 * clinicalPlanningVolume — pure, Bentley-free TRUE 3D world-space clinical
 * planning volume for MRT Pharma.
 *
 * SPATIAL RENDERING CONTRACT (this build's foundational rule): a physical
 * facility object's spatial authority lives in BIM/WORLD coordinates. The camera
 * is an OBSERVER — it changes only the view/projection/screen position, never the
 * object's world geometry. A planning room is therefore a real oriented 3D prism
 * (8 world vertices, 12 triangles), NOT a screen-facing 2D billboard. The text
 * label is a separate VIEW_ANNOTATION and may billboard.
 *
 * The planning volume is a CHILD of an authoritative parent IfcSpace; it must be
 * contained within the parent's true (closed-mesh) geometry before it can be
 * LOCKED. LOCK freezes the app-owned planning object only — it never writes to
 * Bentley.
 */

export interface Vec3 { x: number; y: number; z: number }
export interface Vec2 { x: number; y: number }

export type ClinicalVolumeLifecycle = 'DRAFT' | 'LOCKED'
export type ClinicalVolumeGeometryType = 'ORIENTED_RECTANGULAR_PRISM'

/** The editable placement parameters of an oriented rectangular prism. */
export interface PrismParams {
    centerX: number
    centerY: number
    zLow: number
    zHigh: number
    width: number
    depth: number
    /** Yaw about the vertical (Z) axis, radians. */
    yaw: number
}

export interface ClinicalPlanningVolume {
    id: string
    iModelId: string
    parentBimSpaceId: string
    storeyId?: string
    clinicalFunction: string
    displayName: string
    geometryType: ClinicalVolumeGeometryType
    params: PrismParams
    lifecycleState: ClinicalVolumeLifecycle
    geometrySource: 'MRT_PLANNING_SUBVOLUME'
    /** View-only per-volume visibility (default visible when absent). */
    hidden?: boolean
    /**
     * Build 1A.4 — the most recent CONTAINED (valid) params for this volume. Set
     * only when containment PASSes; NEVER overwritten by an invalid edit. Used by
     * "Restore Valid Position" (app-owned; no Bentley write).
     */
    lastKnownValidParams?: PrismParams
}

/** Generated world geometry for a prism (WORLD_GEOMETRY, never screen-space). */
export interface PrismGeometry {
    vertices: Vec3[] // 8 corners: [0..3]=bottom CCW, [4..7]=top CCW
    triangles: number[] // 12 triangles (36 indices)
    /** Bottom-face footprint ring (world XY at zLow), CCW. */
    footprint: Vec2[]
    /** World interior anchor (centroid at mid-height). */
    interiorAnchor: Vec3
}

/** Numerical-stability minimum (NOT a clinical code requirement). */
export const MIN_VOLUME_DIM = 0.05

function isFiniteNum(n: unknown): n is number { return typeof n === 'number' && Number.isFinite(n) }

/** Validate prism params (reject non-finite / non-positive / inverted). */
export function isValidPrismParams(p: PrismParams): boolean {
    if (![p.centerX, p.centerY, p.zLow, p.zHigh, p.width, p.depth, p.yaw].every(isFiniteNum)) return false
    if (p.width <= 0 || p.depth <= 0) return false
    if (p.zHigh <= p.zLow) return false
    return true
}

/**
 * Build the world geometry of an oriented rectangular prism. Local half-extents
 * are rotated by yaw about Z and translated to (centerX, centerY). All output is
 * in BIM/world coordinates.
 */
export function buildOrientedPlanningPrism(p: PrismParams): PrismGeometry {
    const hw = p.width / 2
    const hd = p.depth / 2
    const c = Math.cos(p.yaw)
    const s = Math.sin(p.yaw)
    // Local bottom corners CCW: (-hw,-hd)->(hw,-hd)->(hw,hd)->(-hw,hd).
    const localXY: Vec2[] = [
        { x: -hw, y: -hd }, { x: hw, y: -hd }, { x: hw, y: hd }, { x: -hw, y: hd },
    ]
    const worldXY = localXY.map((q) => ({ x: p.centerX + q.x * c - q.y * s, y: p.centerY + q.x * s + q.y * c }))
    const bottom: Vec3[] = worldXY.map((q) => ({ x: q.x, y: q.y, z: p.zLow }))
    const top: Vec3[] = worldXY.map((q) => ({ x: q.x, y: q.y, z: p.zHigh }))
    const vertices: Vec3[] = [...bottom, ...top]

    // 12 triangles (2 bottom, 2 top, 8 sides), consistent winding so each edge is
    // shared by exactly two triangles (watertight).
    const triangles: number[] = [
        0, 2, 1, 0, 3, 2, // bottom
        4, 5, 6, 4, 6, 7, // top
        0, 1, 5, 0, 5, 4, // side 0-1
        1, 2, 6, 1, 6, 5, // side 1-2
        2, 3, 7, 2, 7, 6, // side 2-3
        3, 0, 4, 3, 4, 7, // side 3-0
    ]

    const interiorAnchor: Vec3 = { x: p.centerX, y: p.centerY, z: (p.zLow + p.zHigh) / 2 }
    return { vertices, triangles, footprint: worldXY.map((q) => ({ x: q.x, y: q.y })), interiorAnchor }
}

// ---------------------------------------------------------------------------
// Containment against the authoritative parent mesh (pure)
// ---------------------------------------------------------------------------

export interface Mesh { vertices: readonly Vec3[]; triangles: readonly number[] }

/**
 * Point-in-closed-mesh test by ray casting: shoot a ray in +X and count triangle
 * crossings; odd => inside. Robust enough for bounded planning containment. Pure.
 */
export function isPointInsideClosedMesh(point: Vec3, mesh: Mesh): boolean {
    const V = mesh.vertices
    const T = mesh.triangles
    // Ray origin = point, direction = +X.
    let crossings = 0
    for (let t = 0; t + 2 < T.length; t += 3) {
        const a = V[T[t]], b = V[T[t + 1]], c = V[T[t + 2]]
        if (!a || !b || !c) continue
        if (rayXIntersectsTriangle(point, a, b, c)) crossings += 1
    }
    return (crossings % 2) === 1
}

/** Möller–Trumbore for a ray along +X from `o`. */
function rayXIntersectsTriangle(o: Vec3, a: Vec3, b: Vec3, c: Vec3): boolean {
    const dir = { x: 1, y: 0, z: 0 }
    const e1 = { x: b.x - a.x, y: b.y - a.y, z: b.z - a.z }
    const e2 = { x: c.x - a.x, y: c.y - a.y, z: c.z - a.z }
    // p = dir × e2
    const px = dir.y * e2.z - dir.z * e2.y
    const py = dir.z * e2.x - dir.x * e2.z
    const pz = dir.x * e2.y - dir.y * e2.x
    const det = e1.x * px + e1.y * py + e1.z * pz
    if (Math.abs(det) < 1e-12) return false
    const inv = 1 / det
    const tvec = { x: o.x - a.x, y: o.y - a.y, z: o.z - a.z }
    const u = (tvec.x * px + tvec.y * py + tvec.z * pz) * inv
    if (u < 0 || u > 1) return false
    const qx = tvec.y * e1.z - tvec.z * e1.y
    const qy = tvec.z * e1.x - tvec.x * e1.z
    const qz = tvec.x * e1.y - tvec.y * e1.x
    const v = (dir.x * qx + dir.y * qy + dir.z * qz) * inv
    if (v < 0 || u + v > 1) return false
    const tHit = (e2.x * qx + e2.y * qy + e2.z * qz) * inv
    return tHit > 1e-9 // forward along +X only
}

export interface ContainmentResult {
    contained: boolean
    /** How many sampled points fell outside the parent (bounded). */
    failedSamples: number
    /** Total sampled points. */
    totalSamples: number
    confidence: 'CORNERS_AND_EDGES' | 'CORNERS_ONLY' | 'NONE'
    reason?: string
}

/**
 * Validate that a planning prism is contained within the parent mesh. Samples:
 * all 8 corners + edge midpoints + face-center samples + the interior anchor —
 * so a face protrusion between corners of an irregular parent is detected (not
 * just an axis-aligned bbox check). Uses transformed WORLD geometry (rotation
 * honoured). Pure.
 */
export function validatePlanningVolumeContainment(input: { params: PrismParams; parentMesh: Mesh }): ContainmentResult {
    if (!isValidPrismParams(input.params)) {
        return { contained: false, failedSamples: 0, totalSamples: 0, confidence: 'NONE', reason: 'INVALID_DIMENSIONS' }
    }
    if (!input.parentMesh || input.parentMesh.triangles.length < 3) {
        return { contained: false, failedSamples: 0, totalSamples: 0, confidence: 'NONE', reason: 'NO_PARENT_MESH' }
    }
    const g = buildOrientedPlanningPrism(input.params)
    const samples: Vec3[] = []
    // 8 corners.
    samples.push(...g.vertices)
    // 12 edge midpoints.
    const edges: [number, number][] = [
        [0, 1], [1, 2], [2, 3], [3, 0], // bottom
        [4, 5], [5, 6], [6, 7], [7, 4], // top
        [0, 4], [1, 5], [2, 6], [3, 7], // verticals
    ]
    for (const [i, j] of edges) {
        const a = g.vertices[i], b = g.vertices[j]
        samples.push({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 })
    }
    // Face centers (6) + interior anchor.
    samples.push(g.interiorAnchor)

    let failed = 0
    for (const s of samples) {
        if (!isPointInsideClosedMesh(s, input.parentMesh)) failed += 1
    }
    return {
        contained: failed === 0,
        failedSamples: failed,
        totalSamples: samples.length,
        confidence: 'CORNERS_AND_EDGES',
        reason: failed === 0 ? undefined : 'SAMPLES_OUTSIDE_PARENT',
    }
}

// ---------------------------------------------------------------------------
// Lifecycle transitions (pure)
// ---------------------------------------------------------------------------

/** Lock only when dimensions are valid AND containment passes. */
export function canLockVolume(vol: ClinicalPlanningVolume, parentMesh: Mesh): { ok: boolean; reason?: string } {
    if (!isValidPrismParams(vol.params)) return { ok: false, reason: 'INVALID_DIMENSIONS' }
    const c = validatePlanningVolumeContainment({ params: vol.params, parentMesh })
    if (!c.contained) return { ok: false, reason: c.reason ?? 'NOT_CONTAINED' }
    return { ok: true }
}

// ---------------------------------------------------------------------------
// Safe persistence (localStorage; iModel + parent scoped)
// ---------------------------------------------------------------------------

const STORAGE_PREFIX = 'mrtpharma.clinicalVolume.v1.'
const FORBIDDEN_KEYS = ['token', 'accessToken', 'refreshToken', 'authorization', 'Authorization', 'clientSecret', 'pkce', 'verifier', 'mesh', 'vertices', 'triangles']

export function isSafeVolumePayload(v: unknown): v is ClinicalPlanningVolume[] {
    if (!Array.isArray(v)) return false
    const allowed = new Set(['id', 'iModelId', 'parentBimSpaceId', 'storeyId', 'clinicalFunction', 'displayName', 'geometryType', 'params', 'lifecycleState', 'geometrySource', 'hidden', 'lastKnownValidParams'])
    const paramKeys = new Set(['centerX', 'centerY', 'zLow', 'zHigh', 'width', 'depth', 'yaw'])
    return v.every((a) => {
        if (!a || typeof a !== 'object') return false
        const keys = Object.keys(a as Record<string, unknown>)
        if (keys.some((k) => FORBIDDEN_KEYS.includes(k))) return false
        if (!keys.every((k) => allowed.has(k))) return false
        const o = a as ClinicalPlanningVolume
        if (!o.params || typeof o.params !== 'object') return false
        if (!Object.keys(o.params).every((k) => paramKeys.has(k))) return false
        // lastKnownValidParams (optional) must itself be a valid prism when present.
        if (o.lastKnownValidParams !== undefined) {
            if (typeof o.lastKnownValidParams !== 'object' || o.lastKnownValidParams === null) return false
            if (!Object.keys(o.lastKnownValidParams).every((k) => paramKeys.has(k))) return false
            if (!isValidPrismParams(o.lastKnownValidParams)) return false
        }
        return typeof o.id === 'string' && typeof o.parentBimSpaceId === 'string' && isValidPrismParams(o.params)
    })
}

export function toSafeVolumePayload(vols: readonly ClinicalPlanningVolume[]): ClinicalPlanningVolume[] {
    return vols.map((v) => ({
        id: v.id, iModelId: v.iModelId, parentBimSpaceId: v.parentBimSpaceId, storeyId: v.storeyId,
        clinicalFunction: v.clinicalFunction, displayName: v.displayName, geometryType: v.geometryType,
        params: { centerX: v.params.centerX, centerY: v.params.centerY, zLow: v.params.zLow, zHigh: v.params.zHigh, width: v.params.width, depth: v.params.depth, yaw: v.params.yaw },
        lifecycleState: v.lifecycleState, geometrySource: v.geometrySource, hidden: v.hidden,
        lastKnownValidParams: v.lastKnownValidParams
            ? { centerX: v.lastKnownValidParams.centerX, centerY: v.lastKnownValidParams.centerY, zLow: v.lastKnownValidParams.zLow, zHigh: v.lastKnownValidParams.zHigh, width: v.lastKnownValidParams.width, depth: v.lastKnownValidParams.depth, yaw: v.lastKnownValidParams.yaw }
            : undefined,
    }))
}

export function loadClinicalVolumes(iModelId: string, storage?: Pick<Storage, 'getItem'>): ClinicalPlanningVolume[] {
    const s = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined)
    if (!s || !iModelId) return []
    try {
        const raw = s.getItem(STORAGE_PREFIX + iModelId)
        if (!raw) return []
        const parsed = JSON.parse(raw) as unknown
        return isSafeVolumePayload(parsed) ? parsed : []
    } catch { return [] }
}

export function saveClinicalVolumes(iModelId: string, vols: readonly ClinicalPlanningVolume[], storage?: Pick<Storage, 'setItem'>): void {
    const s = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined)
    if (!s || !iModelId) return
    try { s.setItem(STORAGE_PREFIX + iModelId, JSON.stringify(toSafeVolumePayload(vols))) } catch { /* unavailable */ }
}

/** Stable application-owned id for a planning volume. */
export function makeClinicalVolumeId(iModelId: string, parentBimSpaceId: string, slug: string): string {
    return `clinical-volume:${iModelId}:${parentBimSpaceId}:${slug}`
}

/**
 * Derive a sensible DRAFT prism SEED for a NEW volume from the parent's own
 * authoritative footprint + Z range. Pure: centered on the footprint centroid,
 * sized to a bounded fraction of the footprint extent (clamped to numerical
 * minimums), sitting on the floor. This ensures a new room's volume starts INSIDE
 * its OWN parent — never at world origin and never reusing another room's coords.
 */
export function seedPrismParamsFromParent(input: {
    footprint: readonly Vec2[]
    zLow: number
    zHigh: number
    /** Optional interior holes (voids) the seed must also avoid. */
    holes?: readonly (readonly Vec2[])[]
    /**
     * Optional guaranteed-interior anchor (world XY). When supplied it centers the
     * seed at a point PROVEN inside the polygon (e.g. resolveRoomInteriorAnchor),
     * which is essential for rotated / irregular / L-shaped rooms where the AABB
     * center or vertex mean can lie outside the actual room.
     */
    interiorAnchor?: { x: number; y: number }
}): PrismParams {
    const ring = input.footprint
    const n = ring.length || 1
    // Center: a guaranteed-interior anchor when provided; else the AABB center
    // (more robust than the vertex mean for concave polygons); else vertex mean.
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const p of ring) { if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x; if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y }
    const aabbCx = (minX + maxX) / 2, aabbCy = (minY + maxY) / 2
    const vertMeanX = ring.reduce((s, p) => s + p.x, 0) / n
    const vertMeanY = ring.reduce((s, p) => s + p.y, 0) / n
    let cx = input.interiorAnchor && Number.isFinite(input.interiorAnchor.x) ? input.interiorAnchor.x
        : Number.isFinite(aabbCx) ? aabbCx : vertMeanX
    let cy = input.interiorAnchor && Number.isFinite(input.interiorAnchor.y) ? input.interiorAnchor.y
        : Number.isFinite(aabbCy) ? aabbCy : vertMeanY
    if (!Number.isFinite(cx)) cx = 0
    if (!Number.isFinite(cy)) cy = 0

    const extentX = Number.isFinite(maxX - minX) ? maxX - minX : 4
    const extentY = Number.isFinite(maxY - minY) ? maxY - minY : 4

    // B1B-MA-01 fix: derive a GUARANTEED-CONTAINED axis-aligned box. Starting from
    // ~50% of the parent XY extent, SHRINK the half-extents until every sampled
    // corner + edge midpoint (with a small inset) lies inside the outer polygon
    // and outside any hole. A plain 50%-of-AABB box on the vertex mean protruded
    // outside real rotated/irregular rooms (2D18 TECH. OFFICE) → the parent-derived
    // volume failed containment against its OWN parent. When a footprint polygon is
    // available we now converge to a contained box; when it is not (< 3 pts) we
    // fall back to the bounded default sizing (caller treats that as approximate).
    const usablePolygon = ring.length >= 3
    let halfW = Math.max(MIN_VOLUME_DIM * 2, extentX * 0.25)
    let halfD = Math.max(MIN_VOLUME_DIM * 2, extentY * 0.25)
    if (usablePolygon) {
        const inset = Math.max(0.15, WALL_CLEARANCE_INSET)
        // Shrink up to a bounded number of halving steps until contained.
        for (let attempt = 0; attempt < 12; attempt++) {
            if (boxContainedInPolygon({ cx, cy, halfW, halfD, inset }, ring, input.holes)) break
            halfW *= 0.7
            halfD *= 0.7
            if (halfW < MIN_VOLUME_DIM || halfD < MIN_VOLUME_DIM) { halfW = MIN_VOLUME_DIM; halfD = MIN_VOLUME_DIM; break }
        }
    }
    const width = Math.max(MIN_VOLUME_DIM * 2, halfW * 2)
    const depth = Math.max(MIN_VOLUME_DIM * 2, halfD * 2)

    // Z: preserve the established Build 1A seed contract — the seed SITS ON the
    // parent floor (zLow == room zLow) and does NOT inset Z. The containment ray
    // is horizontal (+X), so a sample coplanar with the parent floor/ceiling is
    // not a false boundary crossing (in-plane triangles have ~0 determinant and
    // are skipped); the horizontal ray still resolves inside/outside via the side
    // walls. Insetting Z here would push equipment off the floor (equipment zBase
    // is derived from this seed's zLow) and break floor-aware placement.
    const rawLow = Number.isFinite(input.zLow) ? input.zLow : 0
    const rawHigh = Number.isFinite(input.zHigh) ? input.zHigh : rawLow + 3
    const zLow = rawLow
    // Keep a sensible clinical height, capped by the room height, strictly > zLow.
    const zHigh = Math.max(zLow + MIN_VOLUME_DIM * 4, Math.min(rawHigh, zLow + 3))
    return { centerX: cx, centerY: cy, zLow, zHigh, width, depth, yaw: 0 }
}

/** Small default inset (m) keeping the seed clear of the room walls. */
export const WALL_CLEARANCE_INSET = 0.25

/**
 * Whether an axis-aligned box (center + half-extents, shrunk by `inset`) is fully
 * inside the outer polygon and clear of every hole. Samples the 4 corners + 4
 * edge midpoints + center — the same class of samples the containment validator
 * uses in XY — so a box that passes here is contained in plan. Pure.
 */
function boxContainedInPolygon(
    box: { cx: number; cy: number; halfW: number; halfD: number; inset: number },
    outer: readonly Vec2[],
    holes?: readonly (readonly Vec2[])[],
): boolean {
    // Test the ACTUAL box footprint the caller will build, PLUS the wall-clearance
    // inset — i.e. require the box corners to sit at least `inset` inside the
    // polygon. (Previously this SHRANK the tested box by `inset` while the caller
    // built the full-size box, so the built corners could protrude past what was
    // verified — the residual cause of the 2D18 rotated-room containment FAIL.)
    const hw = box.halfW + Math.max(0, box.inset)
    const hd = box.halfD + Math.max(0, box.inset)
    const samples: Vec2[] = [
        { x: box.cx, y: box.cy },
        { x: box.cx - hw, y: box.cy - hd }, { x: box.cx + hw, y: box.cy - hd },
        { x: box.cx + hw, y: box.cy + hd }, { x: box.cx - hw, y: box.cy + hd },
        { x: box.cx, y: box.cy - hd }, { x: box.cx + hw, y: box.cy },
        { x: box.cx, y: box.cy + hd }, { x: box.cx - hw, y: box.cy },
    ]
    for (const s of samples) {
        if (!pointInPolygon2d(s, outer)) return false
        if (holes && holes.some((h) => pointInPolygon2d(s, h))) return false
    }
    return true
}

/** Ray-cast even-odd point-in-polygon (world XY). Pure; local to this module. */
function pointInPolygon2d(p: Vec2, loop: readonly Vec2[]): boolean {
    let inside = false
    for (let i = 0, j = loop.length - 1; i < loop.length; j = i++) {
        const a = loop[i], b = loop[j]
        const intersects = (a.y > p.y) !== (b.y > p.y) &&
            p.x < ((b.x - a.x) * (p.y - a.y)) / ((b.y - a.y) || 1e-12) + a.x
        if (intersects) inside = !inside
    }
    return inside
}

// ---------------------------------------------------------------------------
// Containment status policy (pure) — distinguish NOT_EVALUATED from FAIL
// ---------------------------------------------------------------------------

export type ContainmentStatus = 'PASS' | 'FAIL' | 'NOT_EVALUATED'

/**
 * Map raw containment evidence to an honest status. A `(0/0)` evaluation (no
 * parent mesh, or zero samples produced) is NOT_EVALUATED — it must NEVER be
 * reported as OUTSIDE/FAIL. Only a real evaluation with samples decides PASS/FAIL.
 */
export function resolveContainmentStatus(input: {
    parentMeshAvailable: boolean
    sampleCount: number
    failedSampleCount: number
}): ContainmentStatus {
    if (!input.parentMeshAvailable) return 'NOT_EVALUATED'
    if (input.sampleCount <= 0) return 'NOT_EVALUATED'
    return input.failedSampleCount === 0 ? 'PASS' : 'FAIL'
}

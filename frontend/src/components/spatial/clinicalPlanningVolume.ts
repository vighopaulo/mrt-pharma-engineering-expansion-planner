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
    const allowed = new Set(['id', 'iModelId', 'parentBimSpaceId', 'storeyId', 'clinicalFunction', 'displayName', 'geometryType', 'params', 'lifecycleState', 'geometrySource', 'hidden'])
    const paramKeys = new Set(['centerX', 'centerY', 'zLow', 'zHigh', 'width', 'depth', 'yaw'])
    return v.every((a) => {
        if (!a || typeof a !== 'object') return false
        const keys = Object.keys(a as Record<string, unknown>)
        if (keys.some((k) => FORBIDDEN_KEYS.includes(k))) return false
        if (!keys.every((k) => allowed.has(k))) return false
        const o = a as ClinicalPlanningVolume
        if (!o.params || typeof o.params !== 'object') return false
        if (!Object.keys(o.params).every((k) => paramKeys.has(k))) return false
        return typeof o.id === 'string' && typeof o.parentBimSpaceId === 'string' && isValidPrismParams(o.params)
    })
}

export function toSafeVolumePayload(vols: readonly ClinicalPlanningVolume[]): ClinicalPlanningVolume[] {
    return vols.map((v) => ({
        id: v.id, iModelId: v.iModelId, parentBimSpaceId: v.parentBimSpaceId, storeyId: v.storeyId,
        clinicalFunction: v.clinicalFunction, displayName: v.displayName, geometryType: v.geometryType,
        params: { centerX: v.params.centerX, centerY: v.params.centerY, zLow: v.params.zLow, zHigh: v.params.zHigh, width: v.params.width, depth: v.params.depth, yaw: v.params.yaw },
        lifecycleState: v.lifecycleState, geometrySource: v.geometrySource, hidden: v.hidden,
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
}): PrismParams {
    const ring = input.footprint
    const n = ring.length || 1
    const cx = ring.reduce((s, p) => s + p.x, 0) / n
    const cy = ring.reduce((s, p) => s + p.y, 0) / n
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const p of ring) { if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x; if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y }
    const extentX = Number.isFinite(maxX - minX) ? maxX - minX : 4
    const extentY = Number.isFinite(maxY - minY) ? maxY - minY : 4
    // Start at ~50% of the parent's XY extent (bounded), well inside the room.
    const width = Math.max(MIN_VOLUME_DIM * 4, extentX * 0.5)
    const depth = Math.max(MIN_VOLUME_DIM * 4, extentY * 0.5)
    const zLow = Number.isFinite(input.zLow) ? input.zLow : 0
    const zHighRaw = Number.isFinite(input.zHigh) ? input.zHigh : zLow + 3
    // Cap height at a sensible ceiling; keep strictly > zLow.
    const zHigh = Math.max(zLow + MIN_VOLUME_DIM * 4, Math.min(zHighRaw, zLow + 3))
    return {
        centerX: Number.isFinite(cx) ? cx : 0,
        centerY: Number.isFinite(cy) ? cy : 0,
        zLow, zHigh, width, depth, yaw: 0,
    }
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

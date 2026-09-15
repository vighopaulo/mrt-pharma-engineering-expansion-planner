/**
 * equipmentInstance — pure, Bentley-free APP-OWNED equipment placement domain
 * for MRT Pharma Build 1B.
 *
 * This is the equipment analogue of `clinicalPlanningVolume`: an application-
 * owned spatial object that BINDS a canonical catalog equipment model to a
 * parent BIM room and validates that its PHYSICAL ENVELOPE is contained within
 * that room's true (closed-mesh) geometry before it can be LOCKED.
 *
 * DOCTRINE:
 *   - The equipment IDENTITY + engineering truth live in the backend catalog
 *     (referenced by `canonicalEquipmentId`); this object owns only the SPATIAL
 *     placement (parent room, position, yaw, envelope) and lifecycle.
 *   - The envelope is an ORIENTED rectangular prism reusing the accepted
 *     planning-volume primitives (`buildOrientedPlanningPrism`,
 *     `validatePlanningVolumeContainment`) so containment is evaluated against
 *     the room's EXACT mesh by sampling corners+edges+anchor — NOT center-only.
 *   - Envelope dimensions come from the canonical catalog: CALIBRATED where the
 *     backend has them, otherwise an honest GENERIC_ENGINEERING_PLACEHOLDER.
 *   - LOCK freezes the app-owned object only — it NEVER writes to Bentley.
 *   - Persistence is safe (no secrets, no raw mesh), iModel-scoped.
 */

import {
    buildOrientedPlanningPrism,
    validatePlanningVolumeContainment,
    resolveContainmentStatus,
    seedPrismParamsFromParent,
    isValidPrismParams,
    MIN_VOLUME_DIM,
    type PrismParams,
    type PrismGeometry,
    type Mesh,
    type Vec2,
    type ContainmentStatus,
} from './clinicalPlanningVolume'
import {
    canonicalEquipmentById,
    type CanonicalEquipmentModel,
    type CanonicalEquipmentClass,
} from './canonicalEquipmentCatalog'
import type { AssetFamily, DimensionProvenance } from '../../domain/assets/types'

export type EquipmentLifecycle = 'DRAFT' | 'LOCKED'
export type EquipmentGeometryType = 'ORIENTED_EQUIPMENT_ENVELOPE'

/**
 * The editable placement of one equipment instance. Position is the envelope's
 * XY center + floor Z; yaw about vertical. Envelope extents (width/depth/height)
 * derive from the canonical model but are stored so the instance is fully
 * serializable and its provenance is explicit.
 */
export interface EquipmentPlacement {
    centerX: number
    centerY: number
    /** Floor Z (envelope base). */
    zBase: number
    /** Envelope extents (meters). */
    width: number
    depth: number
    height: number
    /** Yaw about the vertical (Z) axis, radians. */
    yaw: number
    /** Provenance of the envelope extents (CALIBRATED vs placeholder). */
    envelopeProvenance: DimensionProvenance
}

/** One app-owned equipment instance bound to a parent BIM room. Serializable. */
export interface EquipmentAssetInstance {
    id: string
    iModelId: string
    /** == backend catalog_model_id (identity by reference). */
    canonicalEquipmentId: string
    canonicalClass: CanonicalEquipmentClass
    /** Spatial family (undefined for GENERATOR — no geometry family exists). */
    assetFamily?: AssetFamily
    /** Parent BIM room identity (the binding hook). */
    parentBimSpaceId: string
    /** Optional link to a ClinicalPlanningVolume in the same room. */
    parentClinicalPlanningVolumeId?: string
    storeyId?: string
    displayLabel: string
    geometryType: EquipmentGeometryType
    placement: EquipmentPlacement
    lifecycleState: EquipmentLifecycle
    geometrySource: 'MRT_EQUIPMENT_BINDING'
    /** View-only per-instance visibility (default visible when absent). */
    hidden?: boolean
    /**
     * The most recent CONTAINED (valid) placement. Set only when containment
     * PASSes; NEVER overwritten by an invalid edit. Used by "Restore Valid
     * Position" (app-owned; no Bentley write).
     */
    lastKnownValidPlacement?: EquipmentPlacement
}

// ---------------------------------------------------------------------------
// Envelope → prism bridge (reuse the accepted planning-volume geometry)
// ---------------------------------------------------------------------------

/** Convert an equipment placement into the shared oriented-prism params. */
export function placementToPrismParams(p: EquipmentPlacement): PrismParams {
    return {
        centerX: p.centerX,
        centerY: p.centerY,
        zLow: p.zBase,
        zHigh: p.zBase + p.height,
        width: p.width,
        depth: p.depth,
        yaw: p.yaw,
    }
}

/** Build the equipment envelope world geometry (reuses the planning prism). */
export function buildEquipmentEnvelope(p: EquipmentPlacement): PrismGeometry {
    return buildOrientedPlanningPrism(placementToPrismParams(p))
}

/** Validate a placement's envelope extents (finite, positive, non-inverted). */
export function isValidEquipmentPlacement(p: EquipmentPlacement): boolean {
    return isValidPrismParams(placementToPrismParams(p))
}

// ---------------------------------------------------------------------------
// EVI-MA-02A — equipment spatial exclusivity (oriented-volume collision)
// ---------------------------------------------------------------------------

/**
 * Small boundary tolerance (meters). Two envelopes that only touch within this
 * gap are NOT treated as colliding, so flush side-by-side placement and floating
 * point noise never register a false collision. Any real interpenetration beyond
 * this is a collision.
 */
export const EQUIPMENT_COLLISION_TOLERANCE_M = 0.02

/** The 4 world-XY corners of a placement's yawed footprint (CCW). */
function footprintCorners(p: EquipmentPlacement): { x: number; y: number }[] {
    const hw = p.width / 2
    const hd = p.depth / 2
    const c = Math.cos(p.yaw), s = Math.sin(p.yaw)
    const local = [
        { x: -hw, y: -hd }, { x: hw, y: -hd }, { x: hw, y: hd }, { x: -hw, y: hd },
    ]
    return local.map((q) => ({ x: p.centerX + q.x * c - q.y * s, y: p.centerY + q.x * s + q.y * c }))
}

/** Project polygon corners onto an axis; return [min, max]. */
function projectOnto(corners: readonly { x: number; y: number }[], ax: number, ay: number): [number, number] {
    let min = Infinity, max = -Infinity
    for (const p of corners) {
        const d = p.x * ax + p.y * ay
        if (d < min) min = d
        if (d > max) max = d
    }
    return [min, max]
}

/**
 * Oriented-rectangle (2D OBB) overlap via the Separating Axis Theorem, using the
 * 2 unique edge normals of each yawed footprint (4 axes total). A `tolerance`
 * shrinks the overlap so mere edge contact is not an overlap. Pure.
 */
function orientedFootprintsOverlap(a: EquipmentPlacement, b: EquipmentPlacement, tolerance: number): boolean {
    const ca = footprintCorners(a)
    const cb = footprintCorners(b)
    const axes: [number, number][] = []
    for (const corners of [ca, cb]) {
        for (let i = 0; i < 4; i++) {
            const p0 = corners[i], p1 = corners[(i + 1) % 4]
            const ex = p1.x - p0.x, ey = p1.y - p0.y
            // Edge normal (perpendicular), normalized so the tolerance is in meters.
            const len = Math.hypot(ex, ey) || 1
            axes.push([-ey / len, ex / len])
        }
    }
    for (const [ax, ay] of axes) {
        const [amin, amax] = projectOnto(ca, ax, ay)
        const [bmin, bmax] = projectOnto(cb, ax, ay)
        // Separating axis found if the intervals do not overlap beyond tolerance.
        if (amax - tolerance <= bmin || bmax - tolerance <= amin) return false
    }
    return true // no separating axis => the oriented footprints overlap
}

/** Do two equipment placements' Z ranges overlap (beyond tolerance)? */
function zRangesOverlap(a: EquipmentPlacement, b: EquipmentPlacement, tolerance: number): boolean {
    const aLow = a.zBase, aHigh = a.zBase + a.height
    const bLow = b.zBase, bHigh = b.zBase + b.height
    return aHigh - tolerance > bLow && bHigh - tolerance > aLow
}

/**
 * Do two equipment instances' occupied 3D VOLUMES intersect? Uses the oriented
 * (yaw-respecting) footprint overlap AND the Z-range overlap — a true 3D test,
 * NOT a center-distance / room-membership / 2D-marker heuristic. A rotated
 * instance reserves its correspondingly rotated volume. Pure + deterministic.
 */
export function equipmentVolumesIntersect(
    a: EquipmentPlacement,
    b: EquipmentPlacement,
    tolerance: number = EQUIPMENT_COLLISION_TOLERANCE_M,
): boolean {
    if (!isValidEquipmentPlacement(a) || !isValidEquipmentPlacement(b)) return false
    if (!zRangesOverlap(a, b, tolerance)) return false
    return orientedFootprintsOverlap(a, b, tolerance)
}

/** Result of testing a proposed placement against a set of existing instances. */
export interface EquipmentCollisionResult {
    collides: boolean
    /** The first existing instance the proposal intersects (if any). */
    conflictId?: string
    conflictLabel?: string
    conflictCanonicalId?: string
}

/**
 * Test a proposed placement against every OTHER existing equipment instance
 * (locked instances included — locked equipment still reserves its volume).
 * `excludeId` skips the instance being moved (so it never collides with itself).
 * Returns the first conflict for an honest, specific rejection message. Pure.
 */
export function findEquipmentCollision(input: {
    proposed: EquipmentPlacement
    existing: readonly EquipmentAssetInstance[]
    excludeId?: string
    tolerance?: number
}): EquipmentCollisionResult {
    for (const e of input.existing) {
        if (input.excludeId && e.id === input.excludeId) continue
        if (equipmentVolumesIntersect(input.proposed, e.placement, input.tolerance)) {
            return { collides: true, conflictId: e.id, conflictLabel: e.displayLabel, conflictCanonicalId: e.canonicalEquipmentId }
        }
    }
    return { collides: false }
}

// ---------------------------------------------------------------------------
// EVI-MA-02B — pure ray pick against equipment envelopes (for right-click).
// Reuses the SAME oriented-box math as collision so it is deterministic and
// independent of Bentley's decoration locate (which does not reliably fire on
// right-click). A world ray (origin + direction) is transformed into each
// instance's local yaw frame and slab-tested; the NEAREST hit wins.
// ---------------------------------------------------------------------------

export interface EquipmentPickRay {
    origin: [number, number, number]
    /** Need not be normalized. */
    direction: [number, number, number]
}

/** Nearest positive ray-vs-oriented-box t for one placement, or undefined. */
export function rayIntersectEquipment(ray: EquipmentPickRay, p: EquipmentPlacement): number | undefined {
    if (!isValidEquipmentPlacement(p)) return undefined
    // Box center in world (footprint center at mid-height).
    const cx = p.centerX, cy = p.centerY, cz = p.zBase + p.height / 2
    const hx = p.width / 2, hy = p.depth / 2, hz = p.height / 2
    // Transform ray into the box-local frame (inverse yaw about Z).
    const cos = Math.cos(-p.yaw), sin = Math.sin(-p.yaw)
    const ox = ray.origin[0] - cx, oy = ray.origin[1] - cy, oz = ray.origin[2] - cz
    const lo: [number, number, number] = [ox * cos - oy * sin, ox * sin + oy * cos, oz]
    const dx = ray.direction[0], dy = ray.direction[1], dz = ray.direction[2]
    const ld: [number, number, number] = [dx * cos - dy * sin, dx * sin + dy * cos, dz]
    const half = [hx, hy, hz]
    let tmin = -Infinity, tmax = Infinity
    for (let i = 0; i < 3; i++) {
        const oi = lo[i], di = ld[i], h = half[i]
        if (Math.abs(di) < 1e-12) {
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
    return tmin >= 0 ? tmin : (tmax >= 0 ? tmax : undefined)
}

/**
 * Resolve the NEAREST equipment instance along a world ray (hidden instances
 * excluded). Returns its stable id, or undefined. Ties resolve to the smallest
 * t (nearest along the ray) — never array order. Pure.
 */
export function pickNearestEquipment(ray: EquipmentPickRay, instances: readonly EquipmentAssetInstance[]): string | undefined {
    let bestId: string | undefined
    let bestT = Infinity
    for (const e of instances) {
        if (e.hidden) continue
        const t = rayIntersectEquipment(ray, e.placement)
        if (t !== undefined && t < bestT) { bestT = t; bestId = e.id }
    }
    return bestId
}

/**
 * EVI-MA-02D — resolve the equipment instance a RIGHT-CLICK / context action
 * targets, with a selection-aware priority so overlapping translucent geometry
 * (and clinical PLANNING VOLUMES, which are NOT in this equipment set) can never
 * steal the equipment context menu:
 *   1. the currently SELECTED equipment when the ray hits its occupied volume
 *      (the user is acting on what they already selected);
 *   2. otherwise the NEAREST equipment along the ray;
 *   3. otherwise undefined (no equipment context menu).
 * Only app-owned equipment instances are ever considered, so a planning-volume /
 * room id can never be returned as an equipmentInstanceId. Pure.
 */
export function pickEquipmentForContext(
    ray: EquipmentPickRay,
    instances: readonly EquipmentAssetInstance[],
    selectedId: string | undefined,
): string | undefined {
    if (selectedId) {
        const sel = instances.find((e) => e.id === selectedId && !e.hidden)
        if (sel && rayIntersectEquipment(ray, sel.placement) !== undefined) return sel.id
    }
    return pickNearestEquipment(ray, instances)
}

// ---------------------------------------------------------------------------
// Containment against the parent room mesh (NOT center-only)
// ---------------------------------------------------------------------------

export interface EquipmentContainmentResult {
    status: ContainmentStatus
    contained: boolean
    failedSamples: number
    totalSamples: number
    reason?: string
}

/**
 * Evaluate whether the equipment envelope is contained within the parent room's
 * mesh. Reuses `validatePlanningVolumeContainment` (samples corners + edges +
 * anchor) so an envelope face protruding between corners of an irregular room is
 * detected. `parentMeshAvailable=false` (no cached mesh) yields NOT_EVALUATED —
 * never a false FAIL.
 */
export function evaluateEquipmentContainment(input: {
    placement: EquipmentPlacement
    parentMesh?: Mesh
}): EquipmentContainmentResult {
    const parentMeshAvailable = !!input.parentMesh && input.parentMesh.triangles.length >= 3
    if (!parentMeshAvailable) {
        return { status: 'NOT_EVALUATED', contained: false, failedSamples: 0, totalSamples: 0, reason: 'NO_PARENT_MESH' }
    }
    const c = validatePlanningVolumeContainment({ params: placementToPrismParams(input.placement), parentMesh: input.parentMesh! })
    const status = resolveContainmentStatus({
        parentMeshAvailable: true,
        sampleCount: c.totalSamples,
        failedSampleCount: c.failedSamples,
    })
    return { status, contained: c.contained, failedSamples: c.failedSamples, totalSamples: c.totalSamples, reason: c.reason }
}

// ---------------------------------------------------------------------------
// Parent-derived, floor-aware placement seed
// ---------------------------------------------------------------------------

/**
 * Derive a DRAFT placement SEED for a NEW equipment instance from the parent
 * room's own authoritative footprint + Z range AND the canonical model's
 * envelope. The seed is centered on the room footprint centroid, sits on the
 * room floor (zBase = room zLow — floor-aware), and uses the canonical envelope
 * extents CLAMPED so the seed cannot exceed the room footprint (so a placeholder
 * box starts inside the room rather than bursting through the walls).
 *
 * This guarantees a new instance starts INSIDE its OWN parent — never at world
 * origin and never reusing another room's coordinates.
 */
export function seedEquipmentPlacementFromParent(input: {
    canonicalModel: CanonicalEquipmentModel
    footprint: readonly Vec2[]
    zLow: number
    zHigh: number
}): EquipmentPlacement {
    // Reuse the room seed to get a centroid + a bounded interior footprint size.
    const roomSeed = seedPrismParamsFromParent({ footprint: input.footprint, zLow: input.zLow, zHigh: input.zHigh })
    const env = input.canonicalModel.envelope
    // Clamp envelope extents to the room's interior seed footprint so a large
    // placeholder cannot start outside the room. Keep the canonical height but
    // never exceed the room's usable Z height.
    const maxW = roomSeed.width
    const maxD = roomSeed.depth
    const roomHeight = Math.max(MIN_VOLUME_DIM * 4, roomSeed.zHigh - roomSeed.zLow)
    const width = Math.max(MIN_VOLUME_DIM * 2, Math.min(env.width, maxW))
    const depth = Math.max(MIN_VOLUME_DIM * 2, Math.min(env.depth, maxD))
    const height = Math.max(MIN_VOLUME_DIM * 2, Math.min(env.height, roomHeight))
    return {
        centerX: roomSeed.centerX,
        centerY: roomSeed.centerY,
        zBase: roomSeed.zLow, // floor-aware: sits on the room floor
        width,
        depth,
        height,
        yaw: 0,
        envelopeProvenance: env.provenance,
    }
}

// ---------------------------------------------------------------------------
// Translate / rotate (pure editing)
// ---------------------------------------------------------------------------

export function translateEquipment(p: EquipmentPlacement, dx: number, dy: number): EquipmentPlacement {
    return { ...p, centerX: p.centerX + dx, centerY: p.centerY + dy }
}

export function rotateEquipment(p: EquipmentPlacement, dyaw: number): EquipmentPlacement {
    return { ...p, yaw: p.yaw + dyaw }
}

// ---------------------------------------------------------------------------
// Identity
// ---------------------------------------------------------------------------

/** Stable application-owned id for an equipment instance. */
export function makeEquipmentInstanceId(iModelId: string, parentBimSpaceId: string, canonicalEquipmentId: string, seq: number): string {
    return `equipment:${iModelId}:${parentBimSpaceId}:${canonicalEquipmentId}:${seq}`
}

// ---------------------------------------------------------------------------
// Factory (binds a canonical model to a parent room)
// ---------------------------------------------------------------------------

export type CreateEquipmentResult =
    | { ok: true; instance: EquipmentAssetInstance }
    | { ok: false; reason: string }

/**
 * Create a DRAFT equipment instance for a canonical model bound to a parent room.
 * Placement is the parent-derived floor-aware seed. Identity is by reference to
 * the backend catalog_model_id. Never fabricates equipment not in the catalog.
 */
export function createEquipmentInstance(input: {
    iModelId: string
    canonicalEquipmentId: string
    parentBimSpaceId: string
    parentClinicalPlanningVolumeId?: string
    storeyId?: string
    footprint: readonly Vec2[]
    zLow: number
    zHigh: number
    seq: number
    displayLabelOverride?: string
}): CreateEquipmentResult {
    if (!input.iModelId) return { ok: false, reason: 'NO_IMODEL' }
    if (!input.parentBimSpaceId) return { ok: false, reason: 'NO_PARENT_ROOM' }
    const model = canonicalEquipmentById(input.canonicalEquipmentId)
    if (!model) return { ok: false, reason: 'UNKNOWN_CANONICAL_EQUIPMENT' }

    const placement = seedEquipmentPlacementFromParent({
        canonicalModel: model, footprint: input.footprint, zLow: input.zLow, zHigh: input.zHigh,
    })
    const instance: EquipmentAssetInstance = {
        id: makeEquipmentInstanceId(input.iModelId, input.parentBimSpaceId, model.catalogModelId, input.seq),
        iModelId: input.iModelId,
        canonicalEquipmentId: model.catalogModelId,
        canonicalClass: model.canonicalClass,
        assetFamily: model.assetFamily,
        parentBimSpaceId: input.parentBimSpaceId,
        parentClinicalPlanningVolumeId: input.parentClinicalPlanningVolumeId,
        storeyId: input.storeyId,
        displayLabel: input.displayLabelOverride?.trim() || `${model.manufacturer} ${model.model}`,
        geometryType: 'ORIENTED_EQUIPMENT_ENVELOPE',
        placement,
        lifecycleState: 'DRAFT',
        geometrySource: 'MRT_EQUIPMENT_BINDING',
    }
    return { ok: true, instance }
}

// ---------------------------------------------------------------------------
// Lock gate (pure) — valid + contained
// ---------------------------------------------------------------------------

export function canLockEquipment(instance: EquipmentAssetInstance, parentMesh?: Mesh): { ok: boolean; reason?: string } {
    if (!isValidEquipmentPlacement(instance.placement)) return { ok: false, reason: 'INVALID_DIMENSIONS' }
    const c = evaluateEquipmentContainment({ placement: instance.placement, parentMesh })
    if (c.status !== 'PASS') return { ok: false, reason: c.reason ?? (c.status === 'NOT_EVALUATED' ? 'NOT_EVALUATED' : 'NOT_CONTAINED') }
    return { ok: true }
}

// ---------------------------------------------------------------------------
// Restore / reset (pure)
// ---------------------------------------------------------------------------

/**
 * Compute the placement to restore to: the last-known-valid placement if present,
 * otherwise the fresh parent-derived seed. LOCKED instances are not edited here
 * (the overlay rejects). Pure — returns the placement, does not mutate.
 */
export function restoreEquipmentPlacement(input: {
    instance: EquipmentAssetInstance
    footprint: readonly Vec2[]
    zLow: number
    zHigh: number
}): EquipmentPlacement | undefined {
    if (input.instance.lastKnownValidPlacement) return { ...input.instance.lastKnownValidPlacement }
    const model = canonicalEquipmentById(input.instance.canonicalEquipmentId)
    if (!model) return undefined
    return seedEquipmentPlacementFromParent({ canonicalModel: model, footprint: input.footprint, zLow: input.zLow, zHigh: input.zHigh })
}

/** Compute the fresh parent-derived seed placement (Reset to Parent-Derived). */
export function resetEquipmentToParentDerived(input: {
    instance: EquipmentAssetInstance
    footprint: readonly Vec2[]
    zLow: number
    zHigh: number
}): EquipmentPlacement | undefined {
    const model = canonicalEquipmentById(input.instance.canonicalEquipmentId)
    if (!model) return undefined
    return seedEquipmentPlacementFromParent({ canonicalModel: model, footprint: input.footprint, zLow: input.zLow, zHigh: input.zHigh })
}

// ---------------------------------------------------------------------------
// Safe persistence (localStorage; iModel-scoped) — mirrors clinicalPlanningVolume
// ---------------------------------------------------------------------------

const STORAGE_PREFIX = 'mrtpharma.equipment.v1.'
const FORBIDDEN_KEYS = ['token', 'accessToken', 'refreshToken', 'authorization', 'Authorization', 'clientSecret', 'pkce', 'verifier', 'mesh', 'vertices', 'triangles']

const INSTANCE_KEYS = new Set([
    'id', 'iModelId', 'canonicalEquipmentId', 'canonicalClass', 'assetFamily', 'parentBimSpaceId',
    'parentClinicalPlanningVolumeId', 'storeyId', 'displayLabel', 'geometryType', 'placement',
    'lifecycleState', 'geometrySource', 'hidden', 'lastKnownValidPlacement',
])
const PLACEMENT_KEYS = new Set(['centerX', 'centerY', 'zBase', 'width', 'depth', 'height', 'yaw', 'envelopeProvenance'])

function isSafePlacement(p: unknown): p is EquipmentPlacement {
    if (!p || typeof p !== 'object') return false
    const keys = Object.keys(p as Record<string, unknown>)
    if (!keys.every((k) => PLACEMENT_KEYS.has(k))) return false
    return isValidEquipmentPlacement(p as EquipmentPlacement)
}

export function isSafeEquipmentPayload(v: unknown): v is EquipmentAssetInstance[] {
    if (!Array.isArray(v)) return false
    return v.every((a) => {
        if (!a || typeof a !== 'object') return false
        const keys = Object.keys(a as Record<string, unknown>)
        if (keys.some((k) => FORBIDDEN_KEYS.includes(k))) return false
        if (!keys.every((k) => INSTANCE_KEYS.has(k))) return false
        const o = a as EquipmentAssetInstance
        if (typeof o.id !== 'string' || typeof o.iModelId !== 'string') return false
        if (typeof o.canonicalEquipmentId !== 'string' || typeof o.parentBimSpaceId !== 'string') return false
        if (!isSafePlacement(o.placement)) return false
        if (o.lastKnownValidPlacement !== undefined && !isSafePlacement(o.lastKnownValidPlacement)) return false
        // Only mirror canonical models that actually exist (never resurrect a fabricated id).
        if (!canonicalEquipmentById(o.canonicalEquipmentId)) return false
        return true
    })
}

function toSafePlacement(p: EquipmentPlacement): EquipmentPlacement {
    return {
        centerX: p.centerX, centerY: p.centerY, zBase: p.zBase,
        width: p.width, depth: p.depth, height: p.height, yaw: p.yaw,
        envelopeProvenance: p.envelopeProvenance,
    }
}

export function toSafeEquipmentPayload(instances: readonly EquipmentAssetInstance[]): EquipmentAssetInstance[] {
    return instances.map((i) => ({
        id: i.id, iModelId: i.iModelId, canonicalEquipmentId: i.canonicalEquipmentId, canonicalClass: i.canonicalClass,
        assetFamily: i.assetFamily, parentBimSpaceId: i.parentBimSpaceId,
        parentClinicalPlanningVolumeId: i.parentClinicalPlanningVolumeId, storeyId: i.storeyId,
        displayLabel: i.displayLabel, geometryType: i.geometryType, placement: toSafePlacement(i.placement),
        lifecycleState: i.lifecycleState, geometrySource: i.geometrySource, hidden: i.hidden,
        lastKnownValidPlacement: i.lastKnownValidPlacement ? toSafePlacement(i.lastKnownValidPlacement) : undefined,
    }))
}

export function loadEquipmentInstances(iModelId: string, storage?: Pick<Storage, 'getItem'>): EquipmentAssetInstance[] {
    const s = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined)
    if (!s || !iModelId) return []
    try {
        const raw = s.getItem(STORAGE_PREFIX + iModelId)
        if (!raw) return []
        const parsed = JSON.parse(raw) as unknown
        return isSafeEquipmentPayload(parsed) ? parsed : []
    } catch { return [] }
}

export function saveEquipmentInstances(iModelId: string, instances: readonly EquipmentAssetInstance[], storage?: Pick<Storage, 'setItem'>): void {
    const s = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined)
    if (!s || !iModelId) return
    try { s.setItem(STORAGE_PREFIX + iModelId, JSON.stringify(toSafeEquipmentPayload(instances))) } catch { /* unavailable */ }
}

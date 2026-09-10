/**
 * bimRoomVolumeRegistry — pure, Bentley-free GENERALIZATION of the accepted
 * Uptake-01 spatial proof into a GENERIC room-volume authority for ALL valid
 * BIM rooms (Build 1A).
 *
 * The accepted proof (Uptake 01) demonstrated:
 *   BIM IfcSpace -> authoritative 3D parent geometry -> application-owned
 *   ClinicalPlanningVolume -> world-space rendering -> containment -> persistence.
 *
 * This module makes the DISCOVERY + VOLUME-AWARENESS half of that chain generic:
 * given the already-discovered `SpatialRoomReference[]` (from the accepted
 * `cachedModelSemantics.rooms`) and bounded, caller-supplied cache-availability
 * facts about which rooms have had their EXACT mesh extracted, it produces a
 * bounded, honest DiscoveredRoomVolume model per room and a discovery summary.
 *
 * CRITICAL DOCTRINE (Build 1A §6, §8, §10):
 *   - Discovery is NOT planning-volume creation. This module NEVER creates a
 *     ClinicalPlanningVolume and NEVER creates a ClinicalProgramAssignment.
 *   - The source BIM room stays IMMUTABLE physical authority; nothing here
 *     mutates a Bentley identity, label, range, or mesh.
 *   - EXACT geometry is only claimed when the caller supplies evidence that the
 *     exact mesh has been extracted/cached — a mere BIM range is NEVER promoted
 *     to exact geometry.
 *   - Exact-mesh extraction is LAZY: this pure layer only REPORTS availability;
 *     it never triggers extraction (the overlay does that on demand).
 *   - iModel identity + bimSpaceId are the room identity authority; this module
 *     is scoped by the caller (it operates on one iModel's discovered rooms).
 *
 * Nothing here imports @itwin. The overlay wires the live cache facts in.
 */
import type { SpatialRoomReference, WorldRange3 } from '../../domain/assets/spatialSemantics'
import { resolveRoomStoreyId, type StoreyZRange } from './planningPlan'
import {
    classifyRoomSpatialAuthority,
    type RoomSpatialAuthorityClass,
} from './roomSpatialAuthority'

// ---------------------------------------------------------------------------
// Room geometry quality (Build 1A §9 — explicit, never over-claiming)
// ---------------------------------------------------------------------------

/**
 * The generic room-volume geometry quality. Mirrors the accepted authority
 * precedence but expressed in the Build-1A product vocabulary required by §9.
 * `EXACT_SPACE_GEOMETRY` is ONLY reachable when the caller confirms a cached
 * exact mesh (see `exactMeshCached`); a range alone can only be
 * `RANGE_ONLY_APPROXIMATION`.
 */
export type RoomVolumeGeometryQuality =
    | 'EXACT_SPACE_GEOMETRY'
    | 'RANGE_ONLY_APPROXIMATION'
    | 'ANCHOR_ONLY'
    | 'NOT_AVAILABLE'

/**
 * Bounded, caller-supplied cache facts for a single room (from the overlay's
 * `authoritativeFootprints` map). All optional: discovery works with none of
 * them (range-only), and the exact class only appears once `exactMeshCached`
 * is true AND the extraction actually succeeded (`exactMeshOk`).
 */
export interface RoomMeshCacheFacts {
    /** The exact mesh extraction has been attempted + cached for this room. */
    exactMeshCached: boolean
    /** The cached extraction succeeded (a real closed mesh is available). */
    exactMeshOk: boolean
    /** Cached mesh vertex count (0 when not cached / failed). */
    vertexCount?: number
    /** Cached mesh triangle count (0 when not cached / failed). */
    triangleCount?: number
    /** Whether the cached parent mesh is closed (containment-usable). */
    closedMesh?: boolean
    /** Honest reason when extraction was attempted but failed. */
    extractionReason?: string
}

/** The empty cache fact — a room that has never had its mesh requested. */
export const NO_MESH_CACHE: RoomMeshCacheFacts = { exactMeshCached: false, exactMeshOk: false }

/**
 * A discovered, volume-aware BIM room. This is the generic product-facing model
 * for room discovery + inspection. It is NOT a planning object: it carries no
 * editable prism, no lifecycle, and no assignment. `assigned` / `activated`
 * reflect whether the USER has separately assigned a clinical function (§6, §11)
 * — discovery alone never sets them true.
 */
export interface DiscoveredRoomVolume {
    iModelId: string
    /** BIM identity authority (SpatialRoomReference.roomId). */
    bimSpaceId: string
    /** Original BIM label — NEVER altered. */
    originalBimLabel: string
    /** Canonical storey id where resolvable (else undefined). */
    storeyId?: string
    /** The BIM source class the room came from (e.g. BuildingSpatial:Space). */
    sourceClass: string
    /** Authoritative world range when the BIM supplies a finite one. */
    worldRange?: WorldRange3
    /** The strongest spatial-authority class (accepted precedence). */
    authorityClass: RoomSpatialAuthorityClass
    /** Product-facing geometry quality (§9). */
    geometryQuality: RoomVolumeGeometryQuality
    /** True only when a cached, successful EXACT mesh is available. */
    exactMeshAvailable: boolean
    /** Cached mesh stats (0 when not cached). */
    vertexCount: number
    triangleCount: number
    /** Whether the room is CURRENTLY user-assigned a clinical function. */
    assigned: boolean
    /** The MRT display name if assigned (else undefined). */
    mrtDisplayName?: string
    /** The clinical function id if assigned (else undefined). */
    clinicalFunction?: string
    /** Whether an application-owned ClinicalPlanningVolume exists for this room. */
    hasPlanningVolume: boolean
}

// ---------------------------------------------------------------------------
// Geometry-quality resolution (pure)
// ---------------------------------------------------------------------------

/** Whether a room reference carries a usable finite world range. */
function hasUsableRange(room: Pick<SpatialRoomReference, 'geometryType' | 'range'>): boolean {
    if (!room.range) return false
    const r = room.range
    return [r.low.x, r.low.y, r.low.z, r.high.x, r.high.y, r.high.z].every((n) => Number.isFinite(n))
}

/** Whether a room reference carries a usable footprint. */
function hasUsableFootprint(room: Pick<SpatialRoomReference, 'geometryType' | 'footprint'>): boolean {
    return room.geometryType === 'FOOTPRINT' && !!room.footprint && room.footprint.ring.length >= 3
}

/**
 * Resolve the honest geometry quality for a room from (a) whether an EXACT mesh
 * is cached+ok, and (b) the BIM reference's own geometry. Exact wins ONLY with a
 * cached successful mesh; otherwise footprint/range => RANGE_ONLY_APPROXIMATION,
 * an anchor-ish reference => ANCHOR_ONLY, nothing => NOT_AVAILABLE. A range is
 * NEVER promoted to exact (§8 SILENT_BBOX_PROMOTION_TO_EXACT = NO).
 */
export function resolveRoomVolumeGeometryQuality(input: {
    room: Pick<SpatialRoomReference, 'geometryType' | 'range' | 'footprint'>
    mesh: RoomMeshCacheFacts
}): RoomVolumeGeometryQuality {
    if (input.mesh.exactMeshCached && input.mesh.exactMeshOk) return 'EXACT_SPACE_GEOMETRY'
    if (hasUsableFootprint(input.room) || hasUsableRange(input.room)) return 'RANGE_ONLY_APPROXIMATION'
    if (input.room.geometryType === 'METADATA_ONLY') return 'ANCHOR_ONLY'
    return 'NOT_AVAILABLE'
}

/**
 * Classify the strongest spatial-authority class from the accepted authority,
 * feeding it evidence derived from the BIM reference + cache facts. The cached
 * exact mesh is the only source of `hasExactSpaceGeometry` — the range alone
 * yields at most RANGE_ONLY_APPROXIMATION.
 */
export function resolveRoomAuthorityClass(input: {
    room: Pick<SpatialRoomReference, 'geometryType' | 'range' | 'footprint'>
    mesh: RoomMeshCacheFacts
}): RoomSpatialAuthorityClass {
    return classifyRoomSpatialAuthority({
        hasExactSpaceGeometry: input.mesh.exactMeshCached && input.mesh.exactMeshOk,
        hasExplicitBoundaryRelationships: false,
        physicalBoundaryDerivationFeasible: false,
        hasRange: hasUsableRange(input.room) || hasUsableFootprint(input.room),
        hasAnchor: input.room.geometryType === 'METADATA_ONLY',
    })
}

// ---------------------------------------------------------------------------
// Discovery (pure) — build the generic room-volume model
// ---------------------------------------------------------------------------

/** Minimal assignment fact (kept structurally decoupled from clinicalProgram). */
export interface RoomAssignmentFact {
    bimSpaceId: string
    clinicalFunction: string
    mrtDisplayName: string
}

export interface DiscoverRoomVolumesInput {
    iModelId: string
    /** The accepted discovered rooms (cachedModelSemantics.rooms). */
    rooms: readonly SpatialRoomReference[]
    /** Canonical storey ranges for storey resolution (may be empty). */
    storeys: readonly StoreyZRange[]
    /** Per-room cache facts, keyed by bimSpaceId (missing => NO_MESH_CACHE). */
    meshCacheByRoom?: Readonly<Record<string, RoomMeshCacheFacts>>
    /** Current user assignments (discovery never creates these). */
    assignments?: readonly RoomAssignmentFact[]
    /** bimSpaceIds that currently own a ClinicalPlanningVolume (never created here). */
    planningVolumeParentIds?: readonly string[]
}

/**
 * Build the generic DiscoveredRoomVolume list for one iModel. Deterministic,
 * pure, camera-independent. Stable order (by bimSpaceId). This DOES NOT create
 * planning volumes or assignments — it only reflects state the caller passes in.
 */
export function discoverRoomVolumes(input: DiscoverRoomVolumesInput): DiscoveredRoomVolume[] {
    const meshBy = input.meshCacheByRoom ?? {}
    const assignBy = new Map<string, RoomAssignmentFact>()
    for (const a of input.assignments ?? []) {
        if (a.clinicalFunction && a.clinicalFunction !== 'UNASSIGNED_EXISTING') assignBy.set(a.bimSpaceId, a)
    }
    const pvSet = new Set(input.planningVolumeParentIds ?? [])

    const out: DiscoveredRoomVolume[] = []
    for (const room of input.rooms) {
        if (!room.roomId) continue // BIM identity is the authority; skip identity-less
        const mesh = meshBy[room.roomId] ?? NO_MESH_CACHE
        const storeyId = resolveRoomStoreyIdSafe(room, input.storeys)
        const assignment = assignBy.get(room.roomId)
        out.push({
            iModelId: input.iModelId,
            bimSpaceId: room.roomId,
            originalBimLabel: room.displayName,
            storeyId,
            sourceClass: room.sourceClass,
            worldRange: hasUsableRange(room) ? room.range : undefined,
            authorityClass: resolveRoomAuthorityClass({ room, mesh }),
            geometryQuality: resolveRoomVolumeGeometryQuality({ room, mesh }),
            exactMeshAvailable: mesh.exactMeshCached && mesh.exactMeshOk,
            vertexCount: mesh.vertexCount ?? 0,
            triangleCount: mesh.triangleCount ?? 0,
            assigned: !!assignment,
            mrtDisplayName: assignment?.mrtDisplayName,
            clinicalFunction: assignment?.clinicalFunction,
            hasPlanningVolume: pvSet.has(room.roomId),
        })
    }
    out.sort((a, b) => a.bimSpaceId.localeCompare(b.bimSpaceId))
    return out
}

/**
 * Resolve a room's storey id from its authoritative Z extent. `resolveRoomStoreyId`
 * only needs {zLow, zHigh}; we derive those from the room's footprint (preferred)
 * or its range. Returns undefined when neither exists (never fabricated).
 */
function resolveRoomStoreyIdSafe(room: SpatialRoomReference, storeys: readonly StoreyZRange[]): string | undefined {
    if (storeys.length === 0) return undefined
    let zLow: number | undefined
    let zHigh: number | undefined
    if (room.footprint && Number.isFinite(room.footprint.zLow) && Number.isFinite(room.footprint.zHigh)) {
        zLow = room.footprint.zLow
        zHigh = room.footprint.zHigh
    } else if (room.range && Number.isFinite(room.range.low.z) && Number.isFinite(room.range.high.z)) {
        zLow = room.range.low.z
        zHigh = room.range.high.z
    }
    if (zLow === undefined || zHigh === undefined) return undefined
    return resolveRoomStoreyId({ zLow, zHigh }, storeys)
}

// ---------------------------------------------------------------------------
// Discovery summary (Build 1A §24 — bounded, no raw mesh dump)
// ---------------------------------------------------------------------------

export interface RoomVolumeDiscoverySummary {
    iModelId: string
    /** Total discovered rooms (BIM identities). */
    discoveredRoomCount: number
    /** Rooms whose EXACT mesh is cached + ok. */
    exactGeometryCachedCount: number
    /** Rooms currently classified RANGE_ONLY_APPROXIMATION. */
    rangeOnlyCount: number
    /** Rooms with no usable geometry at all. */
    noGeometryCount: number
    /** Rooms the USER has activated (assigned a clinical function). */
    activatedRoomCount: number
    /** Application-owned planning volumes present. */
    planningVolumeCount: number
    /** Distinct storeys represented among discovered rooms. */
    storeyCount: number
}

/**
 * Build 1A.3 — PURE storey filter over the discovered-room collection.
 * Storey filtering is a VIEW/SUBSET operation; it never mutates the base array.
 *
 *   - `activeStorey === undefined` (the "All" filter) => the full base collection.
 *   - a specific storey => ONLY rooms whose resolved canonical storey id matches.
 *
 * A room whose storey is UNRESOLVED (`storeyId === undefined`) appears ONLY under
 * "All" — never under a specific storey. This is what prevents the observed
 * failure mode where unresolved rooms would pad every storey to the same count.
 */
export function filterDiscoveredRoomsByStorey(
    rooms: readonly DiscoveredRoomVolume[],
    activeStorey: string | undefined,
): DiscoveredRoomVolume[] {
    if (!activeStorey) return rooms.slice() // "All" => base collection (copy; no mutation)
    return rooms.filter((r) => r.storeyId === activeStorey)
}

/**
 * Bounded per-storey counts for the discovered rooms (diagnostic + UI). Pure.
 * Includes an `UNRESOLVED` bucket for rooms with no resolved storey id, plus the
 * `ALL` total. Never mutates input.
 */
export function countRoomsByStorey(rooms: readonly DiscoveredRoomVolume[]): {
    all: number
    unresolved: number
    byStorey: Record<string, number>
} {
    const byStorey: Record<string, number> = {}
    let unresolved = 0
    for (const r of rooms) {
        if (!r.storeyId) { unresolved += 1; continue }
        byStorey[r.storeyId] = (byStorey[r.storeyId] ?? 0) + 1
    }
    return { all: rooms.length, unresolved, byStorey }
}

/** Bounded discovery summary for the active BIM. Pure. */
export function summarizeRoomVolumeDiscovery(input: {
    iModelId: string
    discovered: readonly DiscoveredRoomVolume[]
    planningVolumeCount: number
}): RoomVolumeDiscoverySummary {
    const storeys = new Set<string>()
    let exact = 0
    let range = 0
    let none = 0
    let activated = 0
    for (const r of input.discovered) {
        if (r.storeyId) storeys.add(r.storeyId)
        if (r.geometryQuality === 'EXACT_SPACE_GEOMETRY') exact += 1
        else if (r.geometryQuality === 'RANGE_ONLY_APPROXIMATION') range += 1
        else none += 1
        if (r.assigned) activated += 1
    }
    return {
        iModelId: input.iModelId,
        discoveredRoomCount: input.discovered.length,
        exactGeometryCachedCount: exact,
        rangeOnlyCount: range,
        noGeometryCount: none,
        activatedRoomCount: activated,
        planningVolumeCount: input.planningVolumeCount,
        storeyCount: storeys.size,
    }
}

// ---------------------------------------------------------------------------
// Generic selected-room diagnostic model (Build 1A §25 — not Uptake-specific)
// ---------------------------------------------------------------------------

export interface SelectedRoomVolumeDiagnostic {
    iModelId: string
    bimSpaceId: string
    originalBimLabel: string
    mrtDisplayName?: string
    clinicalFunction?: string
    storeyId?: string
    authorityClass: RoomSpatialAuthorityClass
    geometryQuality: RoomVolumeGeometryQuality
    exactMeshAvailable: boolean
    vertexCount: number
    triangleCount: number
    closedMesh: boolean
    worldRange?: WorldRange3
    hasPlanningVolume: boolean
    planningVolumeId?: string
    containmentStatus: 'PASS' | 'FAIL' | 'NOT_EVALUATED'
    /** Whether this room is the frozen Uptake 01 regression baseline. */
    isUptakeRegressionBaseline: boolean
}

/**
 * Build a bounded diagnostic for ANY selected discovered room (generic).
 * The overlay supplies the live containment status + planning-volume id + mesh
 * closed flag; this pure builder just composes the honest report. It never
 * dumps raw geometry (§25) and never mutates anything.
 */
export function buildSelectedRoomVolumeDiagnostic(input: {
    room: DiscoveredRoomVolume
    closedMesh: boolean
    planningVolumeId?: string
    containmentStatus: 'PASS' | 'FAIL' | 'NOT_EVALUATED'
    uptakeBaselineBimSpaceId: string
}): SelectedRoomVolumeDiagnostic {
    return {
        iModelId: input.room.iModelId,
        bimSpaceId: input.room.bimSpaceId,
        originalBimLabel: input.room.originalBimLabel,
        mrtDisplayName: input.room.mrtDisplayName,
        clinicalFunction: input.room.clinicalFunction,
        storeyId: input.room.storeyId,
        authorityClass: input.room.authorityClass,
        geometryQuality: input.room.geometryQuality,
        exactMeshAvailable: input.room.exactMeshAvailable,
        vertexCount: input.room.vertexCount,
        triangleCount: input.room.triangleCount,
        closedMesh: input.closedMesh,
        worldRange: input.room.worldRange,
        hasPlanningVolume: input.room.hasPlanningVolume,
        planningVolumeId: input.planningVolumeId,
        containmentStatus: input.containmentStatus,
        isUptakeRegressionBaseline: input.room.bimSpaceId === input.uptakeBaselineBimSpaceId,
    }
}

/** Format the generic selected-room diagnostic as a bounded text report. */
export function formatSelectedRoomVolumeDiagnostic(d: SelectedRoomVolumeDiagnostic): string {
    const L: string[] = ['=== SELECTED ROOM VOLUME (generic) ===']
    L.push(`IMODEL_ID = ${d.iModelId || '(none)'}`)
    L.push(`BIM_SPACE_ID = ${d.bimSpaceId}`)
    L.push(`ORIGINAL_BIM_LABEL = ${d.originalBimLabel}`)
    L.push(`CLINICAL_DISPLAY_NAME = ${d.mrtDisplayName ?? '(unassigned)'}`)
    L.push(`CLINICAL_FUNCTION = ${d.clinicalFunction ?? '(unassigned)'}`)
    L.push(`STOREY_ID = ${d.storeyId ?? '(unknown)'}`)
    L.push(`GEOMETRY_AUTHORITY = ${d.authorityClass}`)
    L.push(`GEOMETRY_QUALITY = ${d.geometryQuality}`)
    L.push(`EXACT_MESH_AVAILABLE = ${d.exactMeshAvailable ? 'YES' : 'NO'}`)
    L.push(`VERTEX_COUNT = ${d.vertexCount}`)
    L.push(`TRIANGLE_COUNT = ${d.triangleCount}`)
    L.push(`CLOSED_MESH = ${d.closedMesh ? 'YES' : 'NO'}`)
    if (d.worldRange) {
        const r = d.worldRange
        L.push(`WORLD_RANGE = low(${r.low.x.toFixed(2)},${r.low.y.toFixed(2)},${r.low.z.toFixed(2)}) high(${r.high.x.toFixed(2)},${r.high.y.toFixed(2)},${r.high.z.toFixed(2)})`)
    } else {
        L.push(`WORLD_RANGE = (none)`)
    }
    L.push(`PLANNING_VOLUME_PRESENT = ${d.hasPlanningVolume ? 'YES' : 'NO'}`)
    L.push(`PLANNING_VOLUME_ID = ${d.planningVolumeId ?? '(none)'}`)
    L.push(`CONTAINMENT_STATUS = ${d.containmentStatus}`)
    L.push(`UPTAKE_REGRESSION_BASELINE = ${d.isUptakeRegressionBaseline ? 'YES' : 'NO'}`)
    L.push(`SILENT_BBOX_PROMOTION_TO_EXACT = NO`)
    L.push(`BENTLEY_WRITE = NONE`)
    return L.join('\n')
}

// ---------------------------------------------------------------------------
// Build 1A.4 — pure product-facing planning-volume VALIDATION view model
// ---------------------------------------------------------------------------

export type PlanningContainmentStatus = 'PASS' | 'FAIL' | 'NOT_EVALUATED'
export type PlanningAuthorityQuality = 'EXACT_SPACE_GEOMETRY' | 'RANGE_ONLY_APPROXIMATION' | 'NOT_AVAILABLE'

/** Stable warning classes (never raw jargon as the primary customer message). */
export type PlanningWarningCode =
    | 'NONE'
    | 'OUTSIDE_PARENT'
    | 'NOT_EVALUATED'
    | 'PARENT_GEOMETRY_UNAVAILABLE'

/**
 * The pure product view model for one DRAFT/LOCKED planning volume's validation
 * state. Presentation reads THIS — it never re-derives validation logic in JSX.
 */
export interface PlanningVolumeValidationState {
    planningVolumeId: string
    displayName: string
    containmentStatus: PlanningContainmentStatus
    authorityQuality: PlanningAuthorityQuality
    /** True only when containment PASSes and dimensions are valid (LOCK gate). */
    isLockAllowed: boolean
    warningCode: PlanningWarningCode
    /** Concise product-facing sentence (empty when no warning). */
    warningMessage: string
    /** Reason LOCK is unavailable (empty when lock is allowed). */
    lockDisabledReason: string
    /** Whether a last-known-valid geometry exists to restore. */
    lastKnownValidAvailable: boolean
    /** Whether the Restore Valid Position action should be offered. */
    restoreAvailable: boolean
    /** Secondary technical detail (sample counts) — never the primary message. */
    technicalDetail: string
    /** Whether the parent authority is only an approximation (labeled honestly). */
    approximateParent: boolean
}

/**
 * Resolve the pure validation view model. Deterministic; no side effects.
 *
 *   PASS               => no warning; lock allowed (subject to lifecycle).
 *   FAIL               => OUTSIDE_PARENT warning identifying the room; lock blocked.
 *   NOT_EVALUATED      => honest "not yet evaluated" / "parent unavailable"; lock blocked.
 *
 * A range-only parent is labeled approximate (never presented as exact-mesh proof).
 */
export function resolvePlanningVolumeValidation(input: {
    planningVolumeId: string
    displayName: string
    lifecycleState: 'DRAFT' | 'LOCKED'
    containmentStatus: PlanningContainmentStatus
    authorityQuality: PlanningAuthorityQuality
    /** Total containment samples (secondary detail only). */
    totalSamples: number
    /** Failed containment samples (secondary detail only). */
    failedSamples: number
    /** A last-known-valid geometry exists for THIS volume. */
    hasLastKnownValid: boolean
    /** Parent-mesh availability (distinguishes NOT_EVALUATED reasons). */
    parentMeshAvailable: boolean
}): PlanningVolumeValidationState {
    const name = input.displayName || 'This planning volume'
    const approximateParent = input.authorityQuality === 'RANGE_ONLY_APPROXIMATION'
    const technicalDetail = input.containmentStatus === 'PASS'
        ? `Contained (${input.totalSamples - input.failedSamples}/${input.totalSamples} samples inside)`
        : input.containmentStatus === 'FAIL'
            ? `${input.failedSamples}/${input.totalSamples} sample points outside the parent`
            : 'Containment not evaluated (no sampled points)'

    if (input.containmentStatus === 'PASS') {
        return {
            planningVolumeId: input.planningVolumeId, displayName: name,
            containmentStatus: 'PASS', authorityQuality: input.authorityQuality,
            isLockAllowed: input.lifecycleState === 'DRAFT',
            warningCode: 'NONE', warningMessage: '',
            lockDisabledReason: input.lifecycleState === 'LOCKED' ? 'Already locked — unlock to edit.' : '',
            lastKnownValidAvailable: input.hasLastKnownValid,
            restoreAvailable: input.hasLastKnownValid,
            technicalDetail: approximateParent ? `${technicalDetail} — parent is a range approximation` : technicalDetail,
            approximateParent,
        }
    }

    if (input.containmentStatus === 'FAIL') {
        return {
            planningVolumeId: input.planningVolumeId, displayName: name,
            containmentStatus: 'FAIL', authorityQuality: input.authorityQuality,
            isLockAllowed: false,
            warningCode: 'OUTSIDE_PARENT',
            warningMessage: `${name} extends outside its parent BIM room. Move or resize the planning volume until it is fully contained.`,
            lockDisabledReason: `${name} extends outside its parent room — lock is available only when the volume is fully contained.`,
            lastKnownValidAvailable: input.hasLastKnownValid,
            restoreAvailable: true, // FAIL always offers a way back (last-valid or parent-derived)
            technicalDetail: approximateParent ? `${technicalDetail} — parent is a range approximation` : technicalDetail,
            approximateParent,
        }
    }

    // NOT_EVALUATED — honest; never presented as inside/outside/valid/invalid.
    const parentMissing = !input.parentMeshAvailable
    return {
        planningVolumeId: input.planningVolumeId, displayName: name,
        containmentStatus: 'NOT_EVALUATED', authorityQuality: input.authorityQuality,
        isLockAllowed: false,
        warningCode: parentMissing ? 'PARENT_GEOMETRY_UNAVAILABLE' : 'NOT_EVALUATED',
        warningMessage: parentMissing
            ? `Parent BIM geometry for ${name} is not yet available for containment validation.`
            : `Containment for ${name} has not yet been evaluated.`,
        lockDisabledReason: 'Containment must be evaluated and pass before locking.',
        lastKnownValidAvailable: input.hasLastKnownValid,
        restoreAvailable: input.hasLastKnownValid,
        technicalDetail,
        approximateParent,
    }
}

export interface PlanningValidationSummary {
    planningVolumes: number
    valid: number
    needsAttention: number
    notEvaluated: number
}

/** Restrained planning-validation program summary (pure). */
export function summarizePlanningValidation(states: readonly PlanningVolumeValidationState[]): PlanningValidationSummary {
    let valid = 0, needsAttention = 0, notEvaluated = 0
    for (const s of states) {
        if (s.containmentStatus === 'PASS') valid += 1
        else if (s.containmentStatus === 'FAIL') needsAttention += 1
        else notEvaluated += 1
    }
    return { planningVolumes: states.length, valid, needsAttention, notEvaluated }
}

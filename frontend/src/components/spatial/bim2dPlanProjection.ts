/**
 * bim2dPlanProjection — pure, Bentley-free TRUE 2D BIM FLOOR-PLAN PROJECTION for
 * MRT Pharma (Build 1B §B: synchronized 2D plan shown SIMULTANEOUSLY with the 3D
 * Walkthrough).
 *
 * WHY THIS EXISTS
 *   The user needs a real orthographic (top-down) floor plan visible at the same
 *   time as the first-person 3D Walkthrough — NOT a bird's-eye 3D camera reused
 *   as a "plan" (BIRDS_EYE_USED_AS_2D_PLAN = NO). This module PROJECTS the SAME
 *   authoritative BIM facts the 3D scene already uses into a flat XY view-model
 *   that a 2D canvas/SVG can render. It draws NOTHING itself (rendering stays in
 *   the React component) and holds NO state.
 *
 * DOCTRINE (carried from Build 1A / 1B):
 *   - SHARED IDENTITY. Every plan element is keyed by `bimSpaceId` — the SAME
 *     identity the 3D scene, assignments, planning volumes and equipment use.
 *     There is NO second spatial identity and NO duplicate store: rooms, program
 *     assignments, candidate tiers, equipment envelopes and the walker position
 *     are all READ from the existing authorities and joined here by bimSpaceId.
 *   - HONEST GEOMETRY. When an EXACT extracted room footprint is available we use
 *     its true outer loop; otherwise we fall back to the BIM range rectangle and
 *     TAG it as an approximation (`footprintSource`). We never present an
 *     approximation as exact.
 *   - NO WALKER DUPLICATION. The walker marker consumes the single walkthrough
 *     read-model (eye + yaw) — this module only projects it to XY; it never
 *     stores or integrates a position (DUPLICATE_WALKER_POSITION_STORE = NO).
 *   - PURE + DETERMINISTIC. No @itwin import, no DOM, no viewport. Same input =>
 *     same view-model, so it is fully unit-testable.
 *   - VIEW-ONLY. Selecting or panning in the plan changes only which room is
 *     highlighted / where the 2D viewport looks; it NEVER moves the walker and
 *     NEVER writes the iModel.
 */

import type { ClinicalFunction } from './clinicalProgram'

// ===========================================================================
// Inputs (plain data — gathered by the overlay from existing authorities)
// ===========================================================================

export interface PlanVec2 { x: number; y: number }

export interface PlanWorldRange {
    low: { x: number; y: number; z: number }
    high: { x: number; y: number; z: number }
}

/** How trustworthy a projected room outline is. */
export type PlanFootprintSource = 'EXACT_ROOM_MESH' | 'BIM_RANGE_APPROXIMATION' | 'NONE'

/** A discovered BIM room to project (joined by bimSpaceId). */
export interface PlanRoomInput {
    bimSpaceId: string
    originalBimLabel: string
    mrtDisplayName?: string
    storeyId?: string
    /** Axis-aligned world range (fallback footprint source). */
    worldRange?: PlanWorldRange
    /** Exact extracted outer loop (world XY), preferred when present. */
    exactOuterLoop?: readonly PlanVec2[]
    /** Exact interior holes (world XY), optional. */
    exactHoles?: readonly (readonly PlanVec2[])[]
    /** Floor Z of the exact footprint (elevation), optional. */
    exactFloorZ?: number
}

/** An app-owned clinical program assignment (joined by bimSpaceId). */
export interface PlanAssignmentInput {
    bimSpaceId: string
    clinicalFunction: ClinicalFunction
    mrtDisplayName: string
}

/** The candidate acceptance tier (mirrors clinicalRoomCandidate.CandidateTier). */
export type PlanCandidateTier = 'RECOMMENDED' | 'SUITABLE' | 'NEEDS_REVIEW' | 'REJECTED'

/** A ranked candidate to annotate on the plan (joined by bimSpaceId). */
export interface PlanCandidateInput {
    bimSpaceId: string
    clinicalFunction: ClinicalFunction
    tier: PlanCandidateTier
    score: number
    recommended: boolean
}

/** An app-owned equipment envelope to project (parented by bimSpaceId). */
export interface PlanEquipmentInput {
    id: string
    parentBimSpaceId: string
    storeyId?: string
    displayLabel: string
    lifecycleState: 'DRAFT' | 'LOCKED'
    hidden?: boolean
    /** Envelope footprint ring (world XY), from buildEquipmentEnvelope(...).footprint. */
    footprint: readonly PlanVec2[]
}

/**
 * EVI-MA-05A — an app-owned CLINICAL LOGISTICS VESTIBULE to project as ONE 2D
 * marker: its room-side front-face footprint, the wall-penetration segment
 * (front-face midpoint → behind the wall), and the MRT + PTS stub directions.
 * There is exactly ONE marker per vestibule (never separate MRT/PTS markers).
 */
export interface PlanVestibuleInput {
    id: string
    parentBimSpaceId: string
    storeyId?: string
    displayLabel: string
    lifecycleState: 'DRAFT' | 'LOCKED'
    hidden?: boolean
    /** Room-side reserved-volume footprint ring (world XY). */
    footprint: readonly PlanVec2[]
    /** Front-face midpoint (world XY) — the room-side access location. */
    frontFace: PlanVec2
    /** Unit outward normal of the front face (points into the room). */
    frontNormal: PlanVec2
    /** MRT stub end (world XY), or undefined when no MRT port is fabricated. */
    mrtStubEnd?: PlanVec2
    /** PTS stub end (world XY), or undefined when no PTS port is fabricated. */
    ptsStubEnd?: PlanVec2
}

/** Read-only walker read-model (from the single walkthroughController state). */
export interface PlanWalkerInput {
    active: boolean
    eye: { x: number; y: number; z: number }
    /** Look heading in radians (walkState.yaw). */
    yaw: number
    activeStoreyId?: string
    fovDeg?: number
}

export interface Bim2dPlanProjectionInput {
    rooms: readonly PlanRoomInput[]
    assignments: readonly PlanAssignmentInput[]
    candidates?: readonly PlanCandidateInput[]
    equipment?: readonly PlanEquipmentInput[]
    vestibules?: readonly PlanVestibuleInput[]
    walker?: PlanWalkerInput
    /** Only project elements on this storey (undefined => all storeys). */
    storeyId?: string
    /** The currently selected room (highlighted; SAME bimSpaceId identity). */
    selectedBimSpaceId?: string
}

// ===========================================================================
// Output view-model (flat XY; a renderer maps world XY -> screen)
// ===========================================================================

/** A world-XY bounding box (used to fit/scale the 2D viewport). */
export interface PlanBounds {
    minX: number
    minY: number
    maxX: number
    maxY: number
    /** Whether any geometry contributed (false => empty/degenerate). */
    ok: boolean
}

export interface PlanRoom {
    bimSpaceId: string
    /** Product-facing label (mrtDisplayName || originalBimLabel). */
    label: string
    storeyId?: string
    /** Closed world-XY ring to stroke/fill. Empty when no geometry available. */
    ring: PlanVec2[]
    /** Interior holes (world XY), if the exact footprint had any. */
    holes: PlanVec2[][]
    /** Where the ring came from (honest; approximation is tagged). */
    footprintSource: PlanFootprintSource
    /** The assigned clinical function, if any (drives room fill). */
    clinicalFunction?: ClinicalFunction
    /** The candidate tier for the active discovery function, if scored. */
    candidateTier?: PlanCandidateTier
    /** Whether this is the currently selected room. */
    selected: boolean
    /** A label anchor (centroid of the ring) for placing text. */
    labelAnchor?: PlanVec2
}

export interface PlanEquipment {
    id: string
    /** EVI-MA-02E — hidden equipment still exists + reserves space; the 2D plan
     * keeps a subdued marker (retains id, selectable) so it is recoverable. */
    hidden?: boolean
    parentBimSpaceId: string
    label: string
    lifecycleState: 'DRAFT' | 'LOCKED'
    /** Envelope footprint ring (world XY). */
    ring: PlanVec2[]
    labelAnchor?: PlanVec2
}

/** ONE projected vestibule marker (front face + wall penetration + stub dirs). */
export interface PlanVestibule {
    id: string
    hidden?: boolean
    parentBimSpaceId: string
    label: string
    lifecycleState: 'DRAFT' | 'LOCKED'
    /** Room-side reserved-volume footprint ring (world XY). */
    ring: PlanVec2[]
    /** Front-face access point (world XY). */
    frontFace: PlanVec2
    /** Wall-penetration segment [frontFace -> behind wall] for the marker. */
    wallPenetration: { from: PlanVec2; to: PlanVec2 }
    /** MRT stub direction segment (front-face-plane -> MRT stub end), if any. */
    mrtStub?: { from: PlanVec2; to: PlanVec2 }
    /** PTS stub direction segment, if any. */
    ptsStub?: { from: PlanVec2; to: PlanVec2 }
    labelAnchor?: PlanVec2
}

/** The projected walker marker (position + heading), or absent when not walking. */
export interface PlanWalker {
    /** World XY of the eye (Z dropped for the top-down plan). */
    position: PlanVec2
    /** Heading unit vector in world XY (from yaw). */
    heading: PlanVec2
    /** Raw yaw (radians) for renderers that prefer an angle. */
    yaw: number
    activeStoreyId?: string
    fovDeg?: number
}

/** Honest provenance counts for the plan (surfaced in the UI, not hidden). */
export interface PlanProvenance {
    totalRooms: number
    exactFootprintRooms: number
    approximateFootprintRooms: number
    noGeometryRooms: number
    equipmentCount: number
    walkerPresent: boolean
}

export interface Bim2dPlanView {
    storeyId?: string
    rooms: PlanRoom[]
    equipment: PlanEquipment[]
    vestibules: PlanVestibule[]
    walker?: PlanWalker
    bounds: PlanBounds
    provenance: PlanProvenance
}

// ===========================================================================
// Geometry helpers (pure)
// ===========================================================================

function isFiniteNum(n: unknown): n is number { return typeof n === 'number' && Number.isFinite(n) }

/** A finite XY point? */
function finitePt(p: PlanVec2 | undefined): p is PlanVec2 {
    return !!p && isFiniteNum(p.x) && isFiniteNum(p.y)
}

/** Clean a ring: keep only finite points; require at least a triangle. */
function cleanRing(ring: readonly PlanVec2[] | undefined): PlanVec2[] {
    if (!ring) return []
    const out: PlanVec2[] = []
    for (const p of ring) {
        if (finitePt(p)) out.push({ x: p.x, y: p.y })
    }
    return out.length >= 3 ? out : []
}

/** Axis-aligned rectangle ring (CCW) from a world range's XY extent. */
function rangeRing(range: PlanWorldRange | undefined): PlanVec2[] {
    if (!range) return []
    const { low, high } = range
    if (![low?.x, low?.y, high?.x, high?.y].every(isFiniteNum)) return []
    const xmin = Math.min(low.x, high.x)
    const xmax = Math.max(low.x, high.x)
    const ymin = Math.min(low.y, high.y)
    const ymax = Math.max(low.y, high.y)
    if (xmax === xmin || ymax === ymin) return []
    return [
        { x: xmin, y: ymin },
        { x: xmax, y: ymin },
        { x: xmax, y: ymax },
        { x: xmin, y: ymax },
    ]
}

/** Simple polygon centroid (area-weighted; falls back to vertex mean). */
export function ringCentroid(ring: readonly PlanVec2[]): PlanVec2 | undefined {
    const pts = cleanRing(ring)
    if (pts.length === 0) return undefined
    let a = 0
    let cx = 0
    let cy = 0
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
        const cross = pts[j].x * pts[i].y - pts[i].x * pts[j].y
        a += cross
        cx += (pts[j].x + pts[i].x) * cross
        cy += (pts[j].y + pts[i].y) * cross
    }
    a *= 0.5
    if (Math.abs(a) < 1e-9) {
        // Degenerate/collinear: use the vertex mean.
        const mean = pts.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), { x: 0, y: 0 })
        return { x: mean.x / pts.length, y: mean.y / pts.length }
    }
    return { x: cx / (6 * a), y: cy / (6 * a) }
}

/** Expand a bounds by a ring's points. */
function accumulateBounds(b: { minX: number; minY: number; maxX: number; maxY: number; any: boolean }, ring: readonly PlanVec2[]): void {
    for (const p of ring) {
        if (!finitePt(p)) continue
        if (p.x < b.minX) b.minX = p.x
        if (p.x > b.maxX) b.maxX = p.x
        if (p.y < b.minY) b.minY = p.y
        if (p.y > b.maxY) b.maxY = p.y
        b.any = true
    }
}

/** Unit heading vector from a yaw angle (radians) in world XY. */
export function headingFromYaw(yaw: number): PlanVec2 {
    if (!isFiniteNum(yaw)) return { x: 1, y: 0 }
    return { x: Math.cos(yaw), y: Math.sin(yaw) }
}

// ===========================================================================
// Projection (the single shared seam)
// ===========================================================================

/**
 * Project the current BIM + program + candidate + equipment + walker facts into a
 * flat top-down 2D floor-plan view-model. Everything is joined by `bimSpaceId`.
 * Pure and deterministic.
 *
 * Storey filtering: when `storeyId` is provided, only rooms/equipment on that
 * storey are projected. Rooms with an unknown storey are INCLUDED (honest — we
 * do not silently hide geometry we could not bin). The walker is only shown when
 * active AND (no storey filter OR it is on the filtered storey).
 */
export function projectBim2dPlan(input: Bim2dPlanProjectionInput): Bim2dPlanView {
    const storeyFilter = input.storeyId

    // Index assignments + candidates by bimSpaceId (shared identity join).
    const assignmentByRoom = new Map<string, PlanAssignmentInput>()
    for (const a of input.assignments) assignmentByRoom.set(a.bimSpaceId, a)
    const candidateByRoom = new Map<string, PlanCandidateInput>()
    for (const c of input.candidates ?? []) candidateByRoom.set(c.bimSpaceId, c)

    const b = { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity, any: false }

    const rooms: PlanRoom[] = []
    let exactCount = 0
    let approxCount = 0
    let noGeomCount = 0

    for (const r of input.rooms) {
        // Storey filter: include rooms on the target storey OR of unknown storey.
        if (storeyFilter && r.storeyId && r.storeyId !== storeyFilter) continue

        // Prefer the EXACT extracted footprint; fall back to the BIM range rect.
        let ring = cleanRing(r.exactOuterLoop)
        let source: PlanFootprintSource = 'NONE'
        if (ring.length >= 3) {
            source = 'EXACT_ROOM_MESH'
            exactCount += 1
        } else {
            ring = rangeRing(r.worldRange)
            if (ring.length >= 3) {
                source = 'BIM_RANGE_APPROXIMATION'
                approxCount += 1
            } else {
                noGeomCount += 1
            }
        }

        const holes: PlanVec2[][] = source === 'EXACT_ROOM_MESH'
            ? (r.exactHoles ?? []).map((h) => cleanRing(h)).filter((h) => h.length >= 3)
            : []

        accumulateBounds(b, ring)
        const assignment = assignmentByRoom.get(r.bimSpaceId)
        const candidate = candidateByRoom.get(r.bimSpaceId)

        rooms.push({
            bimSpaceId: r.bimSpaceId,
            label: r.mrtDisplayName || r.originalBimLabel,
            storeyId: r.storeyId,
            ring,
            holes,
            footprintSource: source,
            clinicalFunction: assignment?.clinicalFunction,
            candidateTier: candidate?.tier,
            selected: !!input.selectedBimSpaceId && r.bimSpaceId === input.selectedBimSpaceId,
            labelAnchor: ring.length >= 3 ? ringCentroid(ring) : undefined,
        })
    }

    // Equipment envelopes (join by parent bimSpaceId; respect storey + hidden).
    const equipment: PlanEquipment[] = []
    for (const e of input.equipment ?? []) {
        // EVI-MA-02E — hidden equipment is KEPT (subdued marker), not dropped, so
        // it stays recoverable and honestly represents that it still occupies
        // physical space. Storey filtering still applies.
        if (storeyFilter && e.storeyId && e.storeyId !== storeyFilter) continue
        const ring = cleanRing(e.footprint)
        if (ring.length < 3) continue
        accumulateBounds(b, ring)
        equipment.push({
            id: e.id,
            hidden: e.hidden ?? false,
            parentBimSpaceId: e.parentBimSpaceId,
            label: e.displayLabel,
            lifecycleState: e.lifecycleState,
            ring,
            labelAnchor: ringCentroid(ring),
        })
    }

    // Vestibules — ONE marker per vestibule (front face + wall penetration + MRT
    // and PTS stub directions). Hidden vestibules keep a subdued (recoverable)
    // marker, exactly like equipment. There is NEVER a separate MRT/PTS marker.
    const vestibules: PlanVestibule[] = []
    for (const v of input.vestibules ?? []) {
        if (storeyFilter && v.storeyId && v.storeyId !== storeyFilter) continue
        const ring = cleanRing(v.footprint)
        if (ring.length < 3) continue
        accumulateBounds(b, ring)
        // Wall-penetration segment: from the front face inward-behind by a short
        // fixed length along -frontNormal (into/through the wall).
        const pen = 0.6
        const wallTo = { x: v.frontFace.x - v.frontNormal.x * pen, y: v.frontFace.y - v.frontNormal.y * pen }
        accumulateBounds(b, [v.frontFace, wallTo])
        const mrtStub = v.mrtStubEnd ? { from: wallTo, to: v.mrtStubEnd } : undefined
        const ptsStub = v.ptsStubEnd ? { from: wallTo, to: v.ptsStubEnd } : undefined
        if (v.mrtStubEnd) accumulateBounds(b, [v.mrtStubEnd])
        if (v.ptsStubEnd) accumulateBounds(b, [v.ptsStubEnd])
        vestibules.push({
            id: v.id,
            hidden: v.hidden ?? false,
            parentBimSpaceId: v.parentBimSpaceId,
            label: v.displayLabel,
            lifecycleState: v.lifecycleState,
            ring,
            frontFace: v.frontFace,
            wallPenetration: { from: v.frontFace, to: wallTo },
            mrtStub,
            ptsStub,
            labelAnchor: ringCentroid(ring),
        })
    }

    // Walker marker (single walkthrough read-model; never a duplicate store).
    let walker: PlanWalker | undefined
    const w = input.walker
    if (w && w.active && isFiniteNum(w.eye?.x) && isFiniteNum(w.eye?.y)) {
        const onStorey = !storeyFilter || !w.activeStoreyId || w.activeStoreyId === storeyFilter
        if (onStorey) {
            const position = { x: w.eye.x, y: w.eye.y }
            accumulateBounds(b, [position])
            walker = {
                position,
                heading: headingFromYaw(w.yaw),
                yaw: isFiniteNum(w.yaw) ? w.yaw : 0,
                activeStoreyId: w.activeStoreyId,
                fovDeg: w.fovDeg,
            }
        }
    }

    const bounds: PlanBounds = b.any
        ? { minX: b.minX, minY: b.minY, maxX: b.maxX, maxY: b.maxY, ok: true }
        : { minX: 0, minY: 0, maxX: 0, maxY: 0, ok: false }

    return {
        storeyId: storeyFilter,
        rooms,
        equipment,
        vestibules,
        walker,
        bounds,
        provenance: {
            totalRooms: rooms.length,
            exactFootprintRooms: exactCount,
            approximateFootprintRooms: approxCount,
            noGeometryRooms: noGeomCount,
            equipmentCount: equipment.length,
            walkerPresent: !!walker,
        },
    }
}

// ===========================================================================
// Label-density policy (pure; Build 1B §5 — no mass labelling of ~200 rooms)
// ===========================================================================

/**
 * Which rooms get a PERMANENT text label on the 2D plan. The floor typically has
 * ~200 BIM spaces; permanently labelling every one produced an unreadable mass.
 * Policy:
 *   - CLINICAL: any room with a clinical function assigned (Uptake 01 / Injection
 *     Room 01 / …) is ALWAYS labelled, with a compact badge.
 *   - SELECTED: the currently selected room is ALWAYS labelled (its BIM identity).
 *   - HOVERED: a hovered room is transiently labelled (renderer-driven).
 *   - NONE: ordinary rooms are unlabelled — their polygon still renders and their
 *     identity remains available on hover/click. Identity is never destroyed.
 */
export type PlanLabelKind = 'CLINICAL' | 'SELECTED' | 'HOVERED' | 'NONE'

/**
 * Whether a clinical function counts as an ACTIVE clinical-program assignment for
 * label purposes. `UNASSIGNED_EXISTING` is the default/neutral value and is NOT a
 * program assignment, so it must not trigger a permanent label.
 */
export function isProgramClinicalFunction(fn: ClinicalFunction | undefined): boolean {
    return !!fn && fn !== 'UNASSIGNED_EXISTING'
}

/** A compact clinical badge prefix from the clinical function (e.g. "[U]"). */
export function clinicalBadge(fn: ClinicalFunction | undefined): string {
    switch (fn) {
        case 'UPTAKE_ROOM': return '[U]'
        case 'INJECTION_ROOM': return '[I]'
        case 'PET_CT_SCANNER_ROOM': return '[P]'
        case 'SPECT_CT_SCANNER_ROOM': return '[S]'
        case 'RADIOPHARMACY': return '[R]'
        case 'CYCLOTRON': return '[C]'
        case undefined:
        case 'UNASSIGNED_EXISTING': return ''
        default: return '[•]'
    }
}

export interface PlanRoomLabelDecision {
    /** Whether to draw a PERMANENT label for this room. */
    show: boolean
    /** Why (for tests + deterministic behavior). */
    kind: PlanLabelKind
    /** The text to draw when shown (badge + label; empty when not shown). */
    text: string
}

/**
 * Decide the label for one projected room. Pure + deterministic. A `hoveredId`
 * (renderer-driven) makes exactly that room show its identity transiently; it is
 * never persisted. Clinical + selected are always permanent.
 */
export function resolvePlanRoomLabel(room: Pick<PlanRoom, 'bimSpaceId' | 'label' | 'clinicalFunction' | 'selected' | 'footprintSource'>, hoveredId?: string): PlanRoomLabelDecision {
    const approxSuffix = room.footprintSource === 'BIM_RANGE_APPROXIMATION' ? ' ~' : ''
    if (isProgramClinicalFunction(room.clinicalFunction)) {
        const badge = clinicalBadge(room.clinicalFunction)
        return { show: true, kind: 'CLINICAL', text: `${badge ? badge + ' ' : ''}${room.label}` }
    }
    if (room.selected) {
        return { show: true, kind: 'SELECTED', text: `${room.label}${approxSuffix}` }
    }
    if (hoveredId && room.bimSpaceId === hoveredId) {
        return { show: true, kind: 'HOVERED', text: `${room.label}${approxSuffix}` }
    }
    return { show: false, kind: 'NONE', text: '' }
}

/**
 * How many PERMANENT labels a plan view would draw (clinical + selected only;
 * hover is transient and excluded). Used to prove the mass-label defect is fixed:
 * ~200 rooms must NOT yield ~200 permanent labels.
 */
export function countPermanentPlanLabels(view: Bim2dPlanView): number {
    let n = 0
    for (const room of view.rooms) {
        const d = resolvePlanRoomLabel(room)
        if (d.show) n += 1
    }
    return n
}

// ===========================================================================
// Fit / hit-test helpers (pure; used by the renderer for pan/zoom + click)
// ===========================================================================

/** Padding factor applied when fitting a bounds into a viewport. */
export const PLAN_FIT_PADDING = 0.08

/**
 * Compute a uniform world->screen transform that fits `bounds` into a viewport of
 * `width`×`height` (pixels), Y flipped (screen Y grows downward while world Y
 * grows upward on a plan), centered with padding. Returns identity-ish values for
 * a degenerate bounds so a renderer never divides by zero. Pure.
 */
export interface PlanFitTransform {
    scale: number
    /** Screen offset (pixels) applied after scaling world coords. */
    offsetX: number
    offsetY: number
    width: number
    height: number
}

export function computePlanFitTransform(
    bounds: PlanBounds,
    width: number,
    height: number,
    paddingFrac: number = PLAN_FIT_PADDING,
): PlanFitTransform {
    const safeW = isFiniteNum(width) && width > 0 ? width : 1
    const safeH = isFiniteNum(height) && height > 0 ? height : 1
    if (!bounds.ok) {
        return { scale: 1, offsetX: safeW / 2, offsetY: safeH / 2, width: safeW, height: safeH }
    }
    const bw = Math.max(bounds.maxX - bounds.minX, 1e-6)
    const bh = Math.max(bounds.maxY - bounds.minY, 1e-6)
    const pad = 1 - Math.min(Math.max(paddingFrac, 0), 0.45) * 2
    const scale = Math.min((safeW * pad) / bw, (safeH * pad) / bh)
    // World center maps to viewport center; Y flipped.
    const cx = (bounds.minX + bounds.maxX) / 2
    const cy = (bounds.minY + bounds.maxY) / 2
    const offsetX = safeW / 2 - cx * scale
    const offsetY = safeH / 2 + cy * scale
    return { scale, offsetX, offsetY, width: safeW, height: safeH }
}

/** Apply a fit transform to a world XY point -> screen pixels. Pure. */
export function worldToScreen(t: PlanFitTransform, p: PlanVec2): PlanVec2 {
    return { x: p.x * t.scale + t.offsetX, y: -p.y * t.scale + t.offsetY }
}

/** Invert a fit transform: screen pixels -> world XY. Pure. */
export function screenToWorld(t: PlanFitTransform, p: PlanVec2): PlanVec2 {
    const s = t.scale === 0 ? 1 : t.scale
    return { x: (p.x - t.offsetX) / s, y: -(p.y - t.offsetY) / s }
}

/** Point-in-polygon test (ray casting) in world XY. Pure. */
export function pointInRing(point: PlanVec2, ring: readonly PlanVec2[]): boolean {
    const pts = cleanRing(ring)
    if (pts.length < 3) return false
    let inside = false
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
        const yi = pts[i].y
        const yj = pts[j].y
        const xi = pts[i].x
        const xj = pts[j].x
        const intersects = (yi > point.y) !== (yj > point.y)
            && point.x < ((xj - xi) * (point.y - yi)) / ((yj - yi) || 1e-12) + xi
        if (intersects) inside = !inside
    }
    return inside
}

/**
 * Hit-test a WORLD-XY point against the plan rooms, returning the bimSpaceId of
 * the topmost containing room (later rooms win — matches typical draw order), or
 * undefined. Smaller rooms are preferred on ties so nested spaces are selectable.
 * Pure — used by the click handler; it NEVER moves the walker.
 */
export function hitTestPlanRoom(view: Bim2dPlanView, worldPoint: PlanVec2): string | undefined {
    let best: { id: string; area: number } | undefined
    for (const room of view.rooms) {
        if (!pointInRing(worldPoint, room.ring)) continue
        const area = polygonAbsArea(room.ring)
        if (!best || area < best.area) best = { id: room.bimSpaceId, area }
    }
    return best?.id
}

/**
 * EVI-MA-02 — hit-test an EQUIPMENT marker in the 2D plan. Returns the stable
 * equipmentInstanceId of the smallest-area equipment footprint under the point
 * (so an overlapping pair resolves deterministically to the tighter one, and
 * cycling can page through), or undefined. Pure — used by the click handler to
 * converge the 2D marker click on the SAME `selectedEquipmentId` authority.
 * Equipment is hit-tested BEFORE rooms so a marker click selects the equipment,
 * not its containing room.
 */
export function hitTestPlanEquipment(view: Bim2dPlanView, worldPoint: PlanVec2): string | undefined {
    let best: { id: string; area: number } | undefined
    for (const e of view.equipment) {
        if (!pointInRing(worldPoint, e.ring)) continue
        const area = polygonAbsArea(e.ring)
        if (!best || area < best.area) best = { id: e.id, area }
    }
    return best?.id
}

/**
 * EVI-MA-05A — resolve the vestibuleInstanceId whose room-side marker footprint
 * contains the point (tightest wins). ONE marker per vestibule, so a click
 * selects the same vestibuleInstanceId the 3D pick / floating control use — it
 * never resolves to a separate MRT/PTS marker. Pure.
 */
export function hitTestPlanVestibule(view: Bim2dPlanView, worldPoint: PlanVec2): string | undefined {
    let best: { id: string; area: number } | undefined
    for (const v of view.vestibules) {
        if (!pointInRing(worldPoint, v.ring)) continue
        const area = polygonAbsArea(v.ring)
        if (!best || area < best.area) best = { id: v.id, area }
    }
    return best?.id
}

/** Absolute shoelace area of a ring (world XY). Pure. */
export function polygonAbsArea(ring: readonly PlanVec2[]): number {
    const pts = cleanRing(ring)
    if (pts.length < 3) return 0
    let a = 0
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
        a += (pts[j].x + pts[i].x) * (pts[j].y - pts[i].y)
    }
    return Math.abs(a) / 2
}

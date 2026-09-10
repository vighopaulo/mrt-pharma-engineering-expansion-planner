/**
 * clinicalProgramOverlay — pure, Bentley-free derivation of the CLINICAL PROGRAM
 * OVERLAY MODEL that the ClinicalProgramDecorator renders.
 *
 * Correction (Physical Room Overlay Visibility): the decorator previously mixed
 * assignment / storey / priority / footprint logic into its Bentley draw path,
 * and drew the assigned-room accent at the room's FLOOR Z with a depth-tested
 * decoration — so the accent was occluded by the floor slab and the room was not
 * physically identifiable in Bird's-eye/Cutaway. This module lifts ALL of that
 * policy into one pure, testable seam that maps:
 *
 *   ClinicalProgramAssignment → BuildingSpatial:Space (bimSpaceId, EXACT match)
 *     → BIM-derived PlanFootprint (same footprint architecture as the plan)
 *     → canonical storey id (Z-binned; explicit room→storey mapping)
 *     → bounded ClinicalProgramOverlayRoom { footprint, anchor, priority, ... }
 *
 * The decorator then only renders these records (with a VIEW-ONLY Z lift so the
 * on-top overlay is readable). No Bentley identity, range, label, or storey is
 * ever mutated here.
 */
import type { SpatialRoomReference } from '../../domain/assets'
import {
    deriveRoomFootprint,
    resolveRoomStoreyId,
    type PlanFootprint,
    type StoreyZRange,
} from './planningPlan'
import {
    assignmentForSpace,
    resolveProgramRoomLabel,
    type ClinicalProgramAssignment,
    type ClinicalFunction,
} from './clinicalProgram'
import {
    resolveClinicalProgramFacilityAnchor,
    resolveProgramDisplayAnchor,
    type ProgramGeometryQuality,
    type ProgramGeometrySource,
    type Vec3,
} from './clinicalProgramAnchor'

/** The sentinel active-storey value meaning "show all storeys". */
export const ALL_BUILDING_STOREY = undefined

export interface ClinicalProgramOverlayRoom {
    bimSpaceId: string
    originalBimLabel: string
    mrtDisplayName: string
    /** The label the overlay should show (MRT name if assigned, else original). */
    label: string
    clinicalFunction?: ClinicalFunction
    storeyId?: string
    footprint: PlanFootprint
    /** Deterministic interior anchor (footprint centroid) at footprint elevation.
     *  Retained for backward compatibility; equals facilityAnchor. */
    anchor: { x: number; y: number; z: number }
    /** FIXED physical location in BIM/world coordinates (camera-invariant). */
    facilityAnchor: Vec3
    /** facilityAnchor + view-only Z lift (what worldToView is called on). */
    displayAnchor: Vec3
    /** Boundary in world coordinates (approximate range rect or exact polygon). */
    boundary?: { x: number; y: number; z: number }[]
    geometrySource: ProgramGeometrySource
    geometryQuality: ProgramGeometryQuality
    assigned: boolean
    selected: boolean
    /** Higher = drawn/labelled first under a density budget. */
    priority: number
}

export interface DeriveClinicalProgramOverlayInput {
    rooms: readonly SpatialRoomReference[]
    assignments: readonly ClinicalProgramAssignment[]
    /** Canonical active storey id (undefined => all building). */
    activeStoreyId?: string
    /** The BIM space id currently selected for editing. */
    selectedRoomId?: string
    /** Storey Z-ranges for the explicit room→storey mapping. */
    storeys: readonly StoreyZRange[]
    /** Max labelled rooms (density budget). Default 24. */
    maxLabels?: number
    /** When true, include unassigned rooms as low-priority context. Default false
     *  (this correction focuses on making ASSIGNED rooms identifiable). */
    includeUnassigned?: boolean
    /** View-only Z lift for the DISPLAY anchor (never mutates facility anchor). */
    displayZOffset?: number
}

/** Footprint centroid (deterministic interior anchor). */
export function footprintCentroid(fp: PlanFootprint): { x: number; y: number; z: number } {
    const n = fp.ring.length || 1
    const cx = fp.ring.reduce((s, p) => s + p.x, 0) / n
    const cy = fp.ring.reduce((s, p) => s + p.y, 0) / n
    return { x: cx, y: cy, z: fp.elevation }
}

/**
 * Priority score: selected assigned (3) > assigned (2) > selected unassigned (1)
 * > unassigned (0). Higher wins the density budget and draws last (on top).
 */
export function overlayPriority(assigned: boolean, selected: boolean): number {
    return (assigned ? 2 : 0) + (selected ? 1 : 0)
}

/**
 * Storey-filter policy: an overlay room is eligible when the active storey is
 * "all building" (undefined) OR the room's canonical storey equals the active
 * storey. Rooms with an unknown storey are shown only in all-building mode (so a
 * mis-mapped room never masquerades as belonging to a specific storey).
 */
export function overlayRoomEligible(activeStoreyId: string | undefined, roomStoreyId: string | undefined): boolean {
    if (activeStoreyId === undefined) return true
    if (roomStoreyId === undefined) return false
    return activeStoreyId === roomStoreyId
}

/**
 * Derive the bounded clinical-program overlay model. Pure: EXACT bimSpaceId match
 * (no name/index/coordinate matching), BIM-derived footprints only (rooms without
 * a usable finite range are skipped — never fabricated), explicit room→storey
 * mapping, deterministic anchor + priority, storey filter, density budget.
 */
export function deriveClinicalProgramOverlay(input: DeriveClinicalProgramOverlayInput): ClinicalProgramOverlayRoom[] {
    const maxLabels = input.maxLabels ?? 24
    const includeUnassigned = input.includeUnassigned ?? false

    const rows: ClinicalProgramOverlayRoom[] = []
    for (const room of input.rooms) {
        const assignment = assignmentForSpace(room.roomId, input.assignments)
        const assigned = !!assignment
        if (!assigned && !includeUnassigned) continue

        const footprint = deriveRoomFootprint(room)
        if (!footprint) continue // no fabricated geometry

        const storeyId = resolveRoomStoreyId(footprint, input.storeys)
        if (!overlayRoomEligible(input.activeStoreyId, storeyId)) continue

        const selected = room.roomId === input.selectedRoomId

        // FIXED facility anchor + honest geometry classification (pure; no camera).
        const facility = resolveClinicalProgramFacilityAnchor({ room, storeys: input.storeys })
        const zOffset = input.displayZOffset ?? 0
        const displayAnchor = resolveProgramDisplayAnchor({ facilityAnchor: facility, zOffset })

        rows.push({
            bimSpaceId: room.roomId,
            originalBimLabel: room.displayName,
            mrtDisplayName: assignment?.mrtDisplayName ?? '',
            label: resolveProgramRoomLabel({ originalBimLabel: room.displayName, assignment }),
            clinicalFunction: assignment?.clinicalFunction,
            storeyId,
            footprint,
            anchor: footprintCentroid(footprint),
            facilityAnchor: facility.worldAnchor,
            displayAnchor,
            boundary: facility.boundary,
            geometrySource: facility.geometrySource,
            geometryQuality: facility.geometryQuality,
            assigned,
            selected,
            priority: overlayPriority(assigned, selected),
        })
    }

    // Highest priority first; stable by bimSpaceId for determinism. Apply budget.
    rows.sort((a, b) => (b.priority - a.priority) || a.bimSpaceId.localeCompare(b.bimSpaceId))
    return rows.slice(0, Math.max(maxLabels, 1))
}

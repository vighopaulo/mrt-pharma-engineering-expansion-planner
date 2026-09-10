/**
 * roomSpatialAuthority — pure, Bentley-free classification of the STRONGEST
 * spatial authority available for a BIM room/space, with explicit precedence.
 *
 * The manual failure proved that an axis-aligned BIM range must NOT be treated
 * as an authoritative room boundary. This seam takes bounded observed evidence
 * about a space (does it have exact geometry? explicit boundary relationships?
 * derivable physical boundaries? only a range? only an anchor?) and returns the
 * single strongest authority class. It never promotes a mere range to an exact
 * boundary. It is Bentley-free: the live probe gathers the evidence, this seam
 * classifies it.
 */

export type RoomSpatialAuthorityClass =
    | 'EXACT_SPACE_GEOMETRY'
    | 'EXPLICIT_SPACE_BOUNDARY_RELATIONSHIPS'
    | 'DERIVABLE_FROM_PHYSICAL_BOUNDARIES'
    | 'RANGE_ONLY_APPROXIMATION'
    | 'ANCHOR_ONLY'
    | 'NO_USABLE_SPATIAL_AUTHORITY'

/** Explicit precedence, strongest first. */
export const ROOM_SPATIAL_AUTHORITY_PRECEDENCE: readonly RoomSpatialAuthorityClass[] = [
    'EXACT_SPACE_GEOMETRY',
    'EXPLICIT_SPACE_BOUNDARY_RELATIONSHIPS',
    'DERIVABLE_FROM_PHYSICAL_BOUNDARIES',
    'RANGE_ONLY_APPROXIMATION',
    'ANCHOR_ONLY',
    'NO_USABLE_SPATIAL_AUTHORITY',
]

/** Bounded observed evidence about one BIM space. */
export interface RoomSpatialAuthorityEvidence {
    /** An authoritative Space polygon / shell / solid derived from the Space itself. */
    hasExactSpaceGeometry: boolean
    /** Explicit room-boundary relationships (e.g. IfcRelSpaceBoundary) that enclose the room. */
    hasExplicitBoundaryRelationships: boolean
    /**
     * Enough deterministic physical boundary geometry (walls/partitions +
     * doors/openings + a floor plane) to derive a closed room-local region.
     */
    physicalBoundaryDerivationFeasible: boolean
    /** A finite BIM range (placement bbox or spatial-index range) exists. */
    hasRange: boolean
    /** A trustworthy point/centroid anchor exists (even without a usable range). */
    hasAnchor: boolean
}

/**
 * Classify the strongest available authority. Precedence is strict:
 *   exact geometry > explicit boundaries > derivable physical > range > anchor > none.
 * A range alone NEVER yields an exact/boundary class (no false promotion).
 */
export function classifyRoomSpatialAuthority(e: RoomSpatialAuthorityEvidence): RoomSpatialAuthorityClass {
    if (e.hasExactSpaceGeometry) return 'EXACT_SPACE_GEOMETRY'
    if (e.hasExplicitBoundaryRelationships) return 'EXPLICIT_SPACE_BOUNDARY_RELATIONSHIPS'
    if (e.physicalBoundaryDerivationFeasible) return 'DERIVABLE_FROM_PHYSICAL_BOUNDARIES'
    if (e.hasRange) return 'RANGE_ONLY_APPROXIMATION'
    if (e.hasAnchor) return 'ANCHOR_ONLY'
    return 'NO_USABLE_SPATIAL_AUTHORITY'
}

/** Whether the class establishes an exact room boundary (range/anchor do not). */
export function authorityEstablishesExactBoundary(cls: RoomSpatialAuthorityClass): boolean {
    return cls === 'EXACT_SPACE_GEOMETRY' || cls === 'EXPLICIT_SPACE_BOUNDARY_RELATIONSHIPS'
}

/** The overlay source implied by the authority class (for the NEXT correction). */
export type RoomOverlaySource =
    | 'AUTHORITATIVE_SPACE_GEOMETRY'
    | 'EXPLICIT_SPACE_BOUNDARIES'
    | 'DERIVED_PHYSICAL_ROOM_BOUNDARY'
    | 'FIXED_ANCHOR_ONLY_WITH_RANGE_CONTEXT'
    | 'FIXED_ROOM_MARKER'
    | 'NONE'

export function overlaySourceForAuthority(cls: RoomSpatialAuthorityClass): RoomOverlaySource {
    switch (cls) {
        case 'EXACT_SPACE_GEOMETRY': return 'AUTHORITATIVE_SPACE_GEOMETRY'
        case 'EXPLICIT_SPACE_BOUNDARY_RELATIONSHIPS': return 'EXPLICIT_SPACE_BOUNDARIES'
        case 'DERIVABLE_FROM_PHYSICAL_BOUNDARIES': return 'DERIVED_PHYSICAL_ROOM_BOUNDARY'
        case 'RANGE_ONLY_APPROXIMATION': return 'FIXED_ANCHOR_ONLY_WITH_RANGE_CONTEXT'
        case 'ANCHOR_ONLY': return 'FIXED_ROOM_MARKER'
        default: return 'NONE'
    }
}

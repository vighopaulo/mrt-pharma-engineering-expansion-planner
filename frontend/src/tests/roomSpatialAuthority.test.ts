import { describe, it, expect } from 'vitest'
import {
    classifyRoomSpatialAuthority,
    authorityEstablishesExactBoundary,
    overlaySourceForAuthority,
    ROOM_SPATIAL_AUTHORITY_PRECEDENCE,
    type RoomSpatialAuthorityEvidence,
} from '../components/spatial/roomSpatialAuthority'

function none(): RoomSpatialAuthorityEvidence {
    return {
        hasExactSpaceGeometry: false,
        hasExplicitBoundaryRelationships: false,
        physicalBoundaryDerivationFeasible: false,
        hasRange: false,
        hasAnchor: false,
    }
}

describe('§27 no false promotion (range only)', () => {
    it('range only => RANGE_ONLY_APPROXIMATION (never exact)', () => {
        const cls = classifyRoomSpatialAuthority({ ...none(), hasRange: true, hasAnchor: true })
        expect(cls).toBe('RANGE_ONLY_APPROXIMATION')
        expect(authorityEstablishesExactBoundary(cls)).toBe(false)
    })
})

describe('§28 exact geometry', () => {
    it('exact space geometry => EXACT_SPACE_GEOMETRY', () => {
        expect(classifyRoomSpatialAuthority({ ...none(), hasExactSpaceGeometry: true })).toBe('EXACT_SPACE_GEOMETRY')
    })
})

describe('§29 explicit boundary', () => {
    it('explicit boundary relationships (no exact polygon) => EXPLICIT_SPACE_BOUNDARY_RELATIONSHIPS', () => {
        expect(classifyRoomSpatialAuthority({ ...none(), hasExplicitBoundaryRelationships: true })).toBe('EXPLICIT_SPACE_BOUNDARY_RELATIONSHIPS')
    })
})

describe('§30 derivable boundary', () => {
    it('derivable from physical boundaries => DERIVABLE_FROM_PHYSICAL_BOUNDARIES', () => {
        expect(classifyRoomSpatialAuthority({ ...none(), physicalBoundaryDerivationFeasible: true })).toBe('DERIVABLE_FROM_PHYSICAL_BOUNDARIES')
    })
})

describe('§31 no authority', () => {
    it('nothing usable => NO_USABLE_SPATIAL_AUTHORITY', () => {
        expect(classifyRoomSpatialAuthority(none())).toBe('NO_USABLE_SPATIAL_AUTHORITY')
    })
    it('anchor only => ANCHOR_ONLY', () => {
        expect(classifyRoomSpatialAuthority({ ...none(), hasAnchor: true })).toBe('ANCHOR_ONLY')
    })
})

describe('§52 precedence when multiple sources present', () => {
    it('exact wins over everything', () => {
        expect(classifyRoomSpatialAuthority({ hasExactSpaceGeometry: true, hasExplicitBoundaryRelationships: true, physicalBoundaryDerivationFeasible: true, hasRange: true, hasAnchor: true })).toBe('EXACT_SPACE_GEOMETRY')
    })
    it('explicit boundary wins over derivable + range', () => {
        expect(classifyRoomSpatialAuthority({ ...none(), hasExplicitBoundaryRelationships: true, physicalBoundaryDerivationFeasible: true, hasRange: true })).toBe('EXPLICIT_SPACE_BOUNDARY_RELATIONSHIPS')
    })
    it('derivable wins over range', () => {
        expect(classifyRoomSpatialAuthority({ ...none(), physicalBoundaryDerivationFeasible: true, hasRange: true })).toBe('DERIVABLE_FROM_PHYSICAL_BOUNDARIES')
    })
    it('range wins over anchor', () => {
        expect(classifyRoomSpatialAuthority({ ...none(), hasRange: true, hasAnchor: true })).toBe('RANGE_ONLY_APPROXIMATION')
    })
    it('precedence list is strongest-first and complete', () => {
        expect(ROOM_SPATIAL_AUTHORITY_PRECEDENCE[0]).toBe('EXACT_SPACE_GEOMETRY')
        expect(ROOM_SPATIAL_AUTHORITY_PRECEDENCE[ROOM_SPATIAL_AUTHORITY_PRECEDENCE.length - 1]).toBe('NO_USABLE_SPATIAL_AUTHORITY')
        expect(ROOM_SPATIAL_AUTHORITY_PRECEDENCE).toHaveLength(6)
    })
})

describe('§54 range is not exact', () => {
    it('range present but no exact/boundary/derivation => RANGE_ONLY_APPROXIMATION', () => {
        expect(classifyRoomSpatialAuthority({ hasExactSpaceGeometry: false, hasExplicitBoundaryRelationships: false, physicalBoundaryDerivationFeasible: false, hasRange: true, hasAnchor: false })).toBe('RANGE_ONLY_APPROXIMATION')
    })
})

describe('overlay source mapping', () => {
    it('maps each authority class to its intended overlay source', () => {
        expect(overlaySourceForAuthority('EXACT_SPACE_GEOMETRY')).toBe('AUTHORITATIVE_SPACE_GEOMETRY')
        expect(overlaySourceForAuthority('EXPLICIT_SPACE_BOUNDARY_RELATIONSHIPS')).toBe('EXPLICIT_SPACE_BOUNDARIES')
        expect(overlaySourceForAuthority('DERIVABLE_FROM_PHYSICAL_BOUNDARIES')).toBe('DERIVED_PHYSICAL_ROOM_BOUNDARY')
        expect(overlaySourceForAuthority('RANGE_ONLY_APPROXIMATION')).toBe('FIXED_ANCHOR_ONLY_WITH_RANGE_CONTEXT')
        expect(overlaySourceForAuthority('ANCHOR_ONLY')).toBe('FIXED_ROOM_MARKER')
        expect(overlaySourceForAuthority('NO_USABLE_SPATIAL_AUTHORITY')).toBe('NONE')
    })
})

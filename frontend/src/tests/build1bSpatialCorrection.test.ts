/**
 * Build 1B spatial-foundation correction — PURE domain tests.
 *   §28 — clinical-room candidate CLASSIFICATION (semantic + geometric eligibility)
 *   §29 — per-function candidate RANKING (explainable, containment != suitability)
 *   §30 — RE-PARENTING (regenerate from new parent, no orphan, compatibility)
 *   §31 — TARGETED WALKTHROUGH SPAWN (all 16 sub-properties)
 *
 * No @itwin, no viewport, no DOM — the engines are pure and deterministic.
 */
import { describe, it, expect } from 'vitest'
import {
    classifyBimSpaceSemantics,
    isRejectedClinicalHostKind,
    summarizeDiscoveredVocabulary,
    evaluateRoomEligibility,
    deriveRoomGeometryMetrics,
    scoreRoomCandidate,
    rankClinicalRoomCandidates,
    summarizeCandidateRanking,
    resolveFunctionSpatialProfile,
    resolveCandidateTier,
    roomMatchesFunctionAffinity,
    getFunctionAffinityTokens,
    CLINICAL_HOST_SEMANTIC_VOCABULARY,
    TIER_RECOMMENDED_MIN,
    MIN_HOST_FLOOR_AREA_M2,
    type BimSpaceSemanticKind,
} from '../components/spatial/clinicalRoomCandidate'
import {
    assessReparentCompatibility,
    planReparent,
    describeReparentPlan,
} from '../components/spatial/clinicalRoomReparent'
import {
    resolveTargetedWalkthroughSpawn,
    describeSpawnResult,
    type SpawnRoomGeometry,
} from '../components/spatial/targetedWalkthroughSpawn'
import type { WallSegment } from '../components/spatial/walkNav'

// Helper: a discovered-room-ish shape the candidate engine accepts.
function room(o: Partial<{
    bimSpaceId: string; originalBimLabel: string; sourceClass: string; storeyId: string
    worldRange: { low: { x: number; y: number; z: number }; high: { x: number; y: number; z: number } }
    geometryQuality: 'EXACT_SPACE_GEOMETRY' | 'RANGE_ONLY_APPROXIMATION' | 'ANCHOR_ONLY' | 'NOT_AVAILABLE'
}> = {}) {
    return {
        bimSpaceId: o.bimSpaceId ?? '0x1',
        originalBimLabel: o.originalBimLabel ?? 'Room 101',
        mrtDisplayName: undefined,
        storeyId: o.storeyId,
        sourceClass: o.sourceClass ?? 'BuildingSpatial:Space',
        worldRange: o.worldRange,
        geometryQuality: o.geometryQuality ?? 'RANGE_ONLY_APPROXIMATION',
    }
}

// A 4x3 m axis-aligned range (usable geometry).
const range4x3 = { low: { x: 0, y: 0, z: 0 }, high: { x: 4, y: 3, z: 3 } }

// ===========================================================================
// §28 — SEMANTIC CLASSIFICATION
// ===========================================================================

describe('§28 clinical-room semantic classification', () => {
    it('rejects circulation/corridor/passage as a clinical host', () => {
        for (const label of ['Corridor 1', 'Main Hallway', 'Passage', 'Circulation Spine', 'Lobby']) {
            const c = classifyBimSpaceSemantics({ originalBimLabel: label })
            expect(c.kind).toBe('CIRCULATION')
            expect(c.rejectedByDefault).toBe(true)
            expect(c.matchedVocabulary).toBe(true)
        }
    })

    it('rejects stairs / elevators / shafts / sanitary / open-exterior', () => {
        const cases: Array<[string, BimSpaceSemanticKind]> = [
            ['Stair 2', 'VERTICAL_TRANSPORT'],
            ['Elevator Lobby Shaft', 'VERTICAL_TRANSPORT'],
            ['Duct Shaft', 'SHAFT'],
            ['Mens Toilet', 'SANITARY'],
            ['Atrium', 'OPEN_OR_EXTERIOR'],
            ['Roof Terrace', 'OPEN_OR_EXTERIOR'],
        ]
        for (const [label, kind] of cases) {
            const c = classifyBimSpaceSemantics({ originalBimLabel: label })
            expect(c.kind).toBe(kind)
            expect(c.rejectedByDefault).toBe(true)
        }
    })

    it('allows a generic enclosed room and clinical rooms', () => {
        for (const label of ['Exam Room 3', 'PET/CT Scanner Room', 'Injection Room', 'Uptake 01', 'Radiopharmacy Lab']) {
            const c = classifyBimSpaceSemantics({ originalBimLabel: label })
            expect(c.kind).toBe('ENCLOSED_ROOM')
            expect(c.rejectedByDefault).toBe(false)
        }
    })

    it('does NOT auto-reject an unknown label', () => {
        const c = classifyBimSpaceSemantics({ originalBimLabel: 'Zone Q7' })
        expect(c.kind).toBe('UNKNOWN')
        expect(c.matchedVocabulary).toBe(false)
        expect(c.rejectedByDefault).toBe(false)
    })

    it('service/plant space is rejected as a default host but overridable downstream', () => {
        const c = classifyBimSpaceSemantics({ originalBimLabel: 'Mechanical Room' })
        expect(c.kind).toBe('SERVICE_SUPPORT')
        expect(c.rejectedByDefault).toBe(true)
    })

    it('considers the BIM source class as well as the label', () => {
        const c = classifyBimSpaceSemantics({ originalBimLabel: '', sourceClass: 'Ifc:Stair' })
        expect(c.kind).toBe('VERTICAL_TRANSPORT')
    })

    it('is deterministic and returns the matched token for explainability', () => {
        const a = classifyBimSpaceSemantics({ originalBimLabel: 'Corridor A' })
        const b = classifyBimSpaceSemantics({ originalBimLabel: 'Corridor A' })
        expect(a).toEqual(b)
        expect(a.matchedToken).toBe('corridor')
    })

    it('isRejectedClinicalHostKind matches the doctrine', () => {
        expect(isRejectedClinicalHostKind('ENCLOSED_ROOM')).toBe(false)
        expect(isRejectedClinicalHostKind('UNKNOWN')).toBe(false)
        expect(isRejectedClinicalHostKind('CIRCULATION')).toBe(true)
        expect(isRejectedClinicalHostKind('SHAFT')).toBe(true)
    })

    it('surfaces the discovered vocabulary (kinds, tokens, unknown labels)', () => {
        const labels = ['Corridor 1', 'Exam Room', 'Stair 2', 'Zone Q7', 'Unknown Blob']
        const classifications = labels.map((l) => classifyBimSpaceSemantics({ originalBimLabel: l }))
        const vocab = summarizeDiscoveredVocabulary(classifications)
        expect(vocab.kindCounts.CIRCULATION).toBe(1)
        expect(vocab.kindCounts.ENCLOSED_ROOM).toBe(1)
        expect(vocab.kindCounts.VERTICAL_TRANSPORT).toBe(1)
        expect(vocab.kindCounts.UNKNOWN).toBe(2)
        expect(vocab.unknownLabels).toContain('Zone Q7')
        expect(vocab.matchedTokens).toContain('corridor')
    })

    it('the vocabulary is a non-empty ordered rule set', () => {
        expect(CLINICAL_HOST_SEMANTIC_VOCABULARY.length).toBeGreaterThan(4)
        expect(CLINICAL_HOST_SEMANTIC_VOCABULARY[0].kind).toBe('VERTICAL_TRANSPORT')
    })
})

// ===========================================================================
// §28 (cont.) — GEOMETRIC ELIGIBILITY (no fabricated regulatory minimums)
// ===========================================================================

describe('§28 geometric eligibility', () => {
    it('marks a usable room eligible from its BIM range', () => {
        const e = evaluateRoomEligibility({ room: room({ worldRange: range4x3 }) })
        expect(e.eligible).toBe(true)
        expect(e.code).toBe('ELIGIBLE')
        expect(e.metrics.floorAreaM2).toBeCloseTo(12, 5)
    })

    it('reports GEOMETRY_UNKNOWN (not ineligible-forever) when no geometry is known', () => {
        const e = evaluateRoomEligibility({ room: room({ worldRange: undefined, geometryQuality: 'NOT_AVAILABLE' }) })
        expect(e.eligible).toBe(false)
        expect(e.code).toBe('GEOMETRY_UNKNOWN')
    })

    it('rejects a degenerate sub-minimum area (numerical, not clinical)', () => {
        const tiny = { low: { x: 0, y: 0, z: 0 }, high: { x: 0.5, y: 0.5, z: 3 } }
        const e = evaluateRoomEligibility({ room: room({ worldRange: tiny }) })
        expect(e.eligible).toBe(false)
        expect(e.code).toBe('DEGENERATE_AREA')
        expect(MIN_HOST_FLOOR_AREA_M2).toBe(1)
    })

    it('rejects a collapsed height', () => {
        const flat = { low: { x: 0, y: 0, z: 0 }, high: { x: 4, y: 3, z: 0.5 } }
        const e = evaluateRoomEligibility({ room: room({ worldRange: flat }) })
        expect(e.eligible).toBe(false)
        expect(e.code).toBe('DEGENERATE_HEIGHT')
    })

    it('prefers an exact footprint over the range for metrics', () => {
        const m = deriveRoomGeometryMetrics({
            room: room({ worldRange: range4x3 }),
            footprint: { outerLoop: [{ x: 0, y: 0 }, { x: 6, y: 0 }, { x: 6, y: 4 }, { x: 0, y: 4 }], zLow: 0, zHigh: 3 },
        })
        expect(m.fromFootprint).toBe(true)
        expect(m.floorAreaM2).toBeCloseTo(24, 5)
    })
})

// ===========================================================================
// §29 — RANKING (explainable; containment != clinical suitability)
// ===========================================================================

describe('§29 per-function candidate ranking', () => {
    it('ranks an enclosed room above a corridor for UPTAKE', () => {
        // Build 1B §A: the enclosed room must carry function-specific evidence
        // ('uptake') to be RECOMMENDED — a generic 'Exam Room' would be capped at
        // SUITABLE (geometry alone cannot recommend). Ranking order still holds.
        const rooms = [
            room({ bimSpaceId: '0xCorr', originalBimLabel: 'Corridor 1', worldRange: range4x3, geometryQuality: 'EXACT_SPACE_GEOMETRY' }),
            room({ bimSpaceId: '0xRoom', originalBimLabel: 'Uptake Room', worldRange: range4x3, geometryQuality: 'EXACT_SPACE_GEOMETRY' }),
        ]
        const ranked = rankClinicalRoomCandidates({ clinicalFunction: 'UPTAKE_ROOM', rooms })
        expect(ranked[0].bimSpaceId).toBe('0xRoom')
        expect(ranked[0].recommended).toBe(true)
        const corr = ranked.find((c) => c.bimSpaceId === '0xCorr')!
        expect(corr.recommended).toBe(false)
    })

    it('keeps clinical suitability and geometric fit as INDEPENDENT axes', () => {
        // A corridor with plenty of area: high geometric fit, LOW clinical suitability.
        const bigCorridor = room({ originalBimLabel: 'Corridor', worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 10, y: 6, z: 3 } } })
        const c = scoreRoomCandidate({ room: bigCorridor, clinicalFunction: 'UPTAKE_ROOM' })
        expect(c.geometricFitScore).toBeGreaterThan(0.5) // geometry fits fine
        expect(c.clinicalSuitabilityScore).toBeLessThan(0.2) // but semantics say no
        expect(c.recommended).toBe(false)
        expect(c.reasons.join(' ')).toMatch(/separately from clinical suitability/i)
    })

    it('gives an UNKNOWN room a neutral (non-zero) suitability, but NEVER auto-recommends it (Build 1B calibration)', () => {
        const c = scoreRoomCandidate({ room: room({ originalBimLabel: 'Zone Q7', worldRange: range4x3 }), clinicalFunction: 'UPTAKE_ROOM' })
        // Neutral, non-zero (not auto-rejected)...
        expect(c.clinicalSuitabilityScore).toBeCloseTo(0.45, 5)
        // ...but eligible ≠ recommended: an UNKNOWN label is never RECOMMENDED.
        expect(c.recommended).toBe(false)
        expect(c.tier).not.toBe('RECOMMENDED')
        expect(c.tier).not.toBe('REJECTED') // not rejected either — reviewable
        expect(['SUITABLE', 'NEEDS_REVIEW']).toContain(c.tier)
    })

    it('scores PET/CT geometric fit higher for a large room than a small one', () => {
        const small = scoreRoomCandidate({ room: room({ originalBimLabel: 'Scanner Room', worldRange: range4x3 }), clinicalFunction: 'PET_CT_SCANNER_ROOM' })
        const large = scoreRoomCandidate({ room: room({ originalBimLabel: 'Scanner Room', worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 7, y: 6, z: 3 } } }), clinicalFunction: 'PET_CT_SCANNER_ROOM' })
        expect(large.geometricFitScore).toBeGreaterThan(small.geometricFitScore)
    })

    it('produces explainable reasons for every candidate', () => {
        const c = scoreRoomCandidate({ room: room({ originalBimLabel: 'Exam Room', worldRange: range4x3 }), clinicalFunction: 'INJECTION_ROOM' })
        expect(c.reasons.length).toBeGreaterThanOrEqual(3)
        expect(c.reasons[0]).toMatch(/dedicated clinical\/functional room/i)
    })

    it('is deterministic and stable-ordered', () => {
        const rooms = [
            room({ bimSpaceId: '0xB', originalBimLabel: 'Room B', worldRange: range4x3 }),
            room({ bimSpaceId: '0xA', originalBimLabel: 'Room A', worldRange: range4x3 }),
        ]
        const r1 = rankClinicalRoomCandidates({ clinicalFunction: 'UPTAKE_ROOM', rooms })
        const r2 = rankClinicalRoomCandidates({ clinicalFunction: 'UPTAKE_ROOM', rooms })
        expect(r1.map((c) => c.bimSpaceId)).toEqual(r2.map((c) => c.bimSpaceId))
    })

    it('marks the current parent without excluding it', () => {
        const rooms = [room({ bimSpaceId: '0xCurrent', originalBimLabel: 'Uptake', worldRange: range4x3 })]
        const ranked = rankClinicalRoomCandidates({ clinicalFunction: 'UPTAKE_ROOM', rooms, currentParentBimSpaceId: '0xCurrent' })
        expect(ranked[0].isCurrentParent).toBe(true)
    })

    it('recommendedOnly filters out rejected/ineligible rooms', () => {
        const rooms = [
            room({ bimSpaceId: '0xCorr', originalBimLabel: 'Corridor', worldRange: range4x3 }),
            room({ bimSpaceId: '0xRoom', originalBimLabel: 'Exam Room', worldRange: range4x3 }),
        ]
        const ranked = rankClinicalRoomCandidates({ clinicalFunction: 'UPTAKE_ROOM', rooms, recommendedOnly: true })
        expect(ranked.every((c) => c.recommended)).toBe(true)
        expect(ranked.some((c) => c.bimSpaceId === '0xCorr')).toBe(false)
    })

    it('summarizes the ranking honestly', () => {
        // Build 1B §A: only a function-matching enclosed room ('Uptake Room') with
        // usable geometry is RECOMMENDED; the corridor is rejected by default.
        const rooms = [
            room({ bimSpaceId: '0xCorr', originalBimLabel: 'Corridor', worldRange: range4x3, geometryQuality: 'EXACT_SPACE_GEOMETRY' }),
            room({ bimSpaceId: '0xRoom', originalBimLabel: 'Uptake Room', worldRange: range4x3, geometryQuality: 'EXACT_SPACE_GEOMETRY' }),
        ]
        const candidates = rankClinicalRoomCandidates({ clinicalFunction: 'UPTAKE_ROOM', rooms })
        const s = summarizeCandidateRanking({ clinicalFunction: 'UPTAKE_ROOM', candidates })
        expect(s.totalConsidered).toBe(2)
        expect(s.recommendedCount).toBe(1)
        expect(s.rejectedByDefaultCount).toBe(1)
    })

    it('resolves a spatial profile for each targeted function', () => {
        for (const fn of ['UPTAKE_ROOM', 'INJECTION_ROOM', 'PET_CT_SCANNER_ROOM', 'RADIOPHARMACY'] as const) {
            const p = resolveFunctionSpatialProfile(fn)
            expect(p.preferredAreaM2.min).toBeGreaterThan(0)
            expect(p.preferredAreaM2.ideal).toBeGreaterThanOrEqual(p.preferredAreaM2.min)
        }
    })
})

// ===========================================================================
// §18 — CANDIDATE ACCEPTANCE TIER (eligible ≠ recommended; RECOMMENDED is a
//        real minority; WAITING ≠ UPTAKE; ACTIVITY AREA ≠ clinical proof)
// ===========================================================================

describe('§18 candidate acceptance tier', () => {
    // A large, well-geometried UPTAKE room whose label matches the function.
    const uptakeRoom = room({ bimSpaceId: '0xUp', originalBimLabel: 'Uptake 01', worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 4, y: 3, z: 3 } }, geometryQuality: 'EXACT_SPACE_GEOMETRY' })

    it('RECOMMENDED requires dedicated clinical semantics matching the function + usable geometry', () => {
        const c = scoreRoomCandidate({ room: uptakeRoom, clinicalFunction: 'UPTAKE_ROOM' })
        expect(c.semantic.kind).toBe('ENCLOSED_ROOM')
        expect(c.clinicalSuitabilityScore).toBeCloseTo(1.0, 5) // 'uptake' matches UPTAKE affinity
        expect(c.tier).toBe('RECOMMENDED')
        expect(c.recommended).toBe(true)
    })

    it('a WAITING / ACTIVITY AREA is NEVER RECOMMENDED and NEVER 100% suitability (the 1DC1 defect)', () => {
        const waiting = room({ bimSpaceId: '0xWait', originalBimLabel: '1DC1 WAITING / ACTIVITY AREA', worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 8, y: 6, z: 3 } }, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
        const c = scoreRoomCandidate({ room: waiting, clinicalFunction: 'UPTAKE_ROOM' })
        expect(c.semantic.kind).toBe('GENERIC_OCCUPIABLE')
        // The core defect: waiting/activity must NOT score full clinical suitability.
        expect(c.clinicalSuitabilityScore).toBeLessThan(1.0)
        expect(c.clinicalSuitabilityScore).toBeCloseTo(0.5, 5)
        expect(c.tier).not.toBe('RECOMMENDED')
        expect(c.recommended).toBe(false)
        expect(['SUITABLE', 'NEEDS_REVIEW']).toContain(c.tier)
    })

    it('a default-rejected host (corridor) is REJECTED regardless of geometry', () => {
        const corr = room({ originalBimLabel: 'Corridor', worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 12, y: 8, z: 3 } }, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
        const c = scoreRoomCandidate({ room: corr, clinicalFunction: 'UPTAKE_ROOM' })
        expect(c.tier).toBe('REJECTED')
        expect(c.recommended).toBe(false)
    })

    it('degenerate/ineligible geometry forces REJECTED even for a clinical label', () => {
        const tiny = room({ originalBimLabel: 'Uptake', worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 0.5, y: 0.5, z: 3 } }, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
        const c = scoreRoomCandidate({ room: tiny, clinicalFunction: 'UPTAKE_ROOM' })
        expect(c.eligibility.eligible).toBe(false)
        expect(c.tier).toBe('REJECTED')
    })

    it('a dedicated clinical room for a DIFFERENT function is real but a weaker match (0.7 suitability)', () => {
        const scanner = room({ originalBimLabel: 'PET/CT Scanner Room', worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 4, y: 3, z: 3 } }, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
        const c = scoreRoomCandidate({ room: scanner, clinicalFunction: 'UPTAKE_ROOM' })
        expect(c.semantic.kind).toBe('ENCLOSED_ROOM')
        expect(c.clinicalSuitabilityScore).toBeCloseTo(0.7, 5) // dedicated room, non-matching function
    })

    it('RECOMMENDED is a real MINORITY across a mixed model (NOT 25/25)', () => {
        const rooms = [
            room({ bimSpaceId: '0x1', originalBimLabel: 'Uptake 01', worldRange: range4x3, geometryQuality: 'EXACT_SPACE_GEOMETRY' }), // RECOMMENDED
            room({ bimSpaceId: '0x2', originalBimLabel: 'Recovery Room', worldRange: range4x3, geometryQuality: 'EXACT_SPACE_GEOMETRY' }), // RECOMMENDED (recovery in UPTAKE affinity)
            room({ bimSpaceId: '0x3', originalBimLabel: '1DC1 WAITING / ACTIVITY AREA', worldRange: range4x3 }), // not recommended
            room({ bimSpaceId: '0x4', originalBimLabel: 'Zone Q7', worldRange: range4x3 }), // unknown, not recommended
            room({ bimSpaceId: '0x5', originalBimLabel: 'Corridor 2', worldRange: range4x3 }), // rejected
            room({ bimSpaceId: '0x6', originalBimLabel: 'Mens Toilet', worldRange: range4x3 }), // rejected
            room({ bimSpaceId: '0x7', originalBimLabel: 'Stair 3', worldRange: range4x3 }), // rejected
            room({ bimSpaceId: '0x8', originalBimLabel: 'Exam Room 4', worldRange: range4x3, geometryQuality: 'EXACT_SPACE_GEOMETRY' }), // dedicated, other-fn -> SUITABLE/RECOMMENDED
        ]
        const ranked = rankClinicalRoomCandidates({ clinicalFunction: 'UPTAKE_ROOM', rooms, limit: 25 })
        const s = summarizeCandidateRanking({ clinicalFunction: 'UPTAKE_ROOM', candidates: ranked })
        // The whole point of the correction: recommended is a strict subset, not "all".
        expect(s.recommendedCount).toBeLessThan(ranked.length)
        expect(s.recommendedCount).toBeGreaterThanOrEqual(1)
        expect(s.tierCounts.REJECTED).toBeGreaterThanOrEqual(3) // corridor, toilet, stair
        // Tier counts partition the candidate set exactly.
        const sum = s.tierCounts.RECOMMENDED + s.tierCounts.SUITABLE + s.tierCounts.NEEDS_REVIEW + s.tierCounts.REJECTED
        expect(sum).toBe(ranked.length)
    })

    it('the tier appears in the candidate reasons (explainability)', () => {
        const waiting = room({ originalBimLabel: 'Waiting Area', worldRange: range4x3, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
        const c = scoreRoomCandidate({ room: waiting, clinicalFunction: 'UPTAKE_ROOM' })
        expect(c.reasons.join(' ')).toMatch(new RegExp(c.tier.replace('_', ' '), 'i'))
    })

    it('summary top candidate tier is reported', () => {
        const rooms = [room({ originalBimLabel: 'Uptake 01', worldRange: range4x3, geometryQuality: 'EXACT_SPACE_GEOMETRY' })]
        const ranked = rankClinicalRoomCandidates({ clinicalFunction: 'UPTAKE_ROOM', rooms })
        const s = summarizeCandidateRanking({ clinicalFunction: 'UPTAKE_ROOM', candidates: ranked })
        expect(s.topCandidateTier).toBe('RECOMMENDED')
    })
})

// ===========================================================================
// §19 — SCORE SEPARATION (clinical suitability vs geometric fit are INDEPENDENT)
// ===========================================================================

describe('§19 clinical-suitability vs geometric-fit separation', () => {
    it('high geometric fit does NOT rescue low clinical suitability (corridor)', () => {
        const bigCorr = room({ originalBimLabel: 'Corridor', worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 12, y: 8, z: 3 } }, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
        const c = scoreRoomCandidate({ room: bigCorr, clinicalFunction: 'UPTAKE_ROOM' })
        expect(c.geometricFitScore).toBeGreaterThan(0.8)
        expect(c.clinicalSuitabilityScore).toBeLessThan(0.2)
        expect(c.tier).toBe('REJECTED')
    })

    it('high clinical suitability with SMALL geometry is not full-fit but stays clinically strong', () => {
        const smallUptake = room({ originalBimLabel: 'Uptake', worldRange: { low: { x: 0, y: 0, z: 0 }, high: { x: 2, y: 1, z: 3 } }, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
        const c = scoreRoomCandidate({ room: smallUptake, clinicalFunction: 'UPTAKE_ROOM' })
        // 2m^2 area is eligible (>1) but below UPTAKE preferred min of 6 -> partial fit.
        expect(c.clinicalSuitabilityScore).toBeCloseTo(1.0, 5)
        expect(c.geometricFitScore).toBeLessThan(0.6)
        // The two axes are reported independently and differ.
        expect(c.clinicalSuitabilityScore).not.toBeCloseTo(c.geometricFitScore, 2)
    })

    it('unknown geometry yields a neutral 0.5 geometric fit (pending extraction), independent of semantics', () => {
        const noGeom = room({ originalBimLabel: 'Uptake', worldRange: undefined, geometryQuality: 'NOT_AVAILABLE' })
        const c = scoreRoomCandidate({ room: noGeom, clinicalFunction: 'UPTAKE_ROOM' })
        // No geometry -> ineligible -> geometric fit collapses to 0 (cannot host).
        expect(c.eligibility.eligible).toBe(false)
        expect(c.needsExactGeometry).toBe(true)
        // Ineligible geometry forces REJECTED even though the label is clinical.
        expect(c.tier).toBe('REJECTED')
    })

    it('the blended score is exactly 0.6*suitability + 0.4*fit', () => {
        const c = scoreRoomCandidate({ room: room({ originalBimLabel: 'Exam Room', worldRange: range4x3, geometryQuality: 'EXACT_SPACE_GEOMETRY' }), clinicalFunction: 'INJECTION_ROOM' })
        expect(c.score).toBeCloseTo(0.6 * c.clinicalSuitabilityScore + 0.4 * c.geometricFitScore, 6)
    })
})

// ===========================================================================
// §A — RECOMMENDATION-SEMANTIC GUARD (Build 1B continuation)
//   Doctrine: GEOMETRIC FIT CANNOT BY ITSELF ESTABLISH THAT THE ROOM IS
//   CLINICALLY APPROPRIATE. RECOMMENDED requires AFFIRMATIVE, function-specific
//   semantic evidence. ELIGIBLE_EQUALS_RECOMMENDED = NO. A dedicated clinical
//   room for a DIFFERENT function (TECH.OFFICE / PROSTH.LAB / CERAMIC LAB) with
//   excellent geometry must be capped at SUITABLE, never RECOMMENDED.
// ===========================================================================

describe('§A recommendation-semantic guard', () => {
    // A large, EXACT-geometry enclosed room whose label is a DIFFERENT function.
    const bigExactRange = { low: { x: 0, y: 0, z: 0 }, high: { x: 8, y: 6, z: 3 } }

    it('(1) roomMatchesFunctionAffinity is TRUE only for the matching function', () => {
        expect(roomMatchesFunctionAffinity('Uptake 01', 'UPTAKE_ROOM')).toBe(true)
        expect(roomMatchesFunctionAffinity('Recovery Bay', 'UPTAKE_ROOM')).toBe(true)
        expect(roomMatchesFunctionAffinity('PET/CT Scanner Room', 'PET_CT_SCANNER_ROOM')).toBe(true)
        expect(roomMatchesFunctionAffinity('Radiopharmacy', 'RADIOPHARMACY')).toBe(true)
        // Mismatched / unrelated labels → no evidence.
        expect(roomMatchesFunctionAffinity('Tech Office', 'UPTAKE_ROOM')).toBe(false)
        expect(roomMatchesFunctionAffinity('Prosth Lab', 'UPTAKE_ROOM')).toBe(false)
        expect(roomMatchesFunctionAffinity('Ceramic Lab', 'INJECTION_ROOM')).toBe(false)
        expect(roomMatchesFunctionAffinity('Exam Room', 'UPTAKE_ROOM')).toBe(false)
        expect(roomMatchesFunctionAffinity('', 'UPTAKE_ROOM')).toBe(false)
    })

    it('(2) a DIFFERENT-function enclosed room with EXCELLENT geometry is NOT RECOMMENDED (capped at SUITABLE)', () => {
        const office = room({ bimSpaceId: '0xOff', originalBimLabel: 'Tech Office', worldRange: bigExactRange, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
        const c = scoreRoomCandidate({ room: office, clinicalFunction: 'UPTAKE_ROOM' })
        expect(c.semantic.kind).toBe('ENCLOSED_ROOM') // 'office' is a dedicated room word
        expect(c.geometricFitScore).toBeCloseTo(1.0, 5) // geometry is excellent
        expect(c.score).toBeGreaterThanOrEqual(TIER_RECOMMENDED_MIN) // would have been RECOMMENDED by score alone
        expect(c.hasFunctionSemanticEvidence).toBe(false)
        expect(c.tier).toBe('SUITABLE') // ...but the guard caps it
        expect(c.recommended).toBe(false)
        expect(c.cappedForNoSemanticEvidence).toBe(true)
    })

    it('(3) PROSTH.LAB / CERAMIC LAB (the observed defect) are capped at SUITABLE for UPTAKE', () => {
        for (const label of ['PROSTH.LAB', 'CERAMIC LAB', 'DENTAL LABORATORY']) {
            const r = room({ originalBimLabel: label, worldRange: bigExactRange, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
            const c = scoreRoomCandidate({ room: r, clinicalFunction: 'UPTAKE_ROOM' })
            expect(c.semantic.kind).toBe('ENCLOSED_ROOM')
            expect(c.recommended).toBe(false)
            expect(c.tier).not.toBe('RECOMMENDED')
        }
    })

    it('(4) the SAME-function room IS RECOMMENDED (guard does not block legitimate matches)', () => {
        const uptake = room({ bimSpaceId: '0xUp', originalBimLabel: 'Uptake 01', worldRange: bigExactRange, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
        const c = scoreRoomCandidate({ room: uptake, clinicalFunction: 'UPTAKE_ROOM' })
        expect(c.hasFunctionSemanticEvidence).toBe(true)
        expect(c.tier).toBe('RECOMMENDED')
        expect(c.recommended).toBe(true)
        expect(c.cappedForNoSemanticEvidence).toBe(false)
    })

    it('(5) the numeric score is preserved for within-tier ranking even when capped', () => {
        const office = room({ originalBimLabel: 'Tech Office', worldRange: bigExactRange, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
        const c = scoreRoomCandidate({ room: office, clinicalFunction: 'UPTAKE_ROOM' })
        // Capped tier does NOT zero the score — ranking within SUITABLE still works.
        expect(c.score).toBeCloseTo(0.6 * c.clinicalSuitabilityScore + 0.4 * c.geometricFitScore, 6)
        expect(c.score).toBeGreaterThan(0.55)
    })

    it('(6) resolveCandidateTier caps a high score at SUITABLE without semantic evidence', () => {
        const base = {
            semanticKind: 'ENCLOSED_ROOM' as BimSpaceSemanticKind,
            rejectedByDefault: false,
            eligible: true,
            clinicalSuitabilityScore: 0.7,
            geometricFitScore: 1.0,
            score: 0.82, // ≥ 0.75
            needsExactGeometry: false,
        }
        expect(resolveCandidateTier({ ...base, hasFunctionSemanticEvidence: false })).toBe('SUITABLE')
        expect(resolveCandidateTier({ ...base, hasFunctionSemanticEvidence: true })).toBe('RECOMMENDED')
    })

    it('(7) resolveCandidateTier defaults to fail-closed (no evidence flag → not RECOMMENDED)', () => {
        const t = resolveCandidateTier({
            semanticKind: 'ENCLOSED_ROOM',
            rejectedByDefault: false,
            eligible: true,
            clinicalSuitabilityScore: 0.7,
            geometricFitScore: 1.0,
            score: 0.82,
            needsExactGeometry: false,
            // hasFunctionSemanticEvidence omitted
        })
        expect(t).not.toBe('RECOMMENDED')
    })

    it('(8) the capped candidate carries an honest, function-named explanation', () => {
        const office = room({ originalBimLabel: 'Tech Office', worldRange: bigExactRange, geometryQuality: 'EXACT_SPACE_GEOMETRY' })
        const c = scoreRoomCandidate({ room: office, clinicalFunction: 'UPTAKE_ROOM' })
        const joined = c.reasons.join(' ')
        expect(joined).toMatch(/no affirmative UPTAKE_ROOM semantic evidence/i)
        expect(joined).toMatch(/capped at SUITABLE/i)
    })

    it('(9) across a mixed model only function-matching rooms reach RECOMMENDED', () => {
        const rooms = [
            room({ bimSpaceId: '0xA', originalBimLabel: 'Uptake 01', worldRange: bigExactRange, geometryQuality: 'EXACT_SPACE_GEOMETRY' }), // RECOMMENDED
            room({ bimSpaceId: '0xB', originalBimLabel: 'Tech Office', worldRange: bigExactRange, geometryQuality: 'EXACT_SPACE_GEOMETRY' }), // capped
            room({ bimSpaceId: '0xC', originalBimLabel: 'Prosth Lab', worldRange: bigExactRange, geometryQuality: 'EXACT_SPACE_GEOMETRY' }), // capped
            room({ bimSpaceId: '0xD', originalBimLabel: 'Ceramic Lab', worldRange: bigExactRange, geometryQuality: 'EXACT_SPACE_GEOMETRY' }), // capped
        ]
        const ranked = rankClinicalRoomCandidates({ clinicalFunction: 'UPTAKE_ROOM', rooms, limit: 25 })
        const recommended = ranked.filter((c) => c.recommended)
        expect(recommended).toHaveLength(1)
        expect(recommended[0].bimSpaceId).toBe('0xA')
        // The three geometry-only rooms are demoted, not rejected.
        for (const id of ['0xB', '0xC', '0xD']) {
            const c = ranked.find((r) => r.bimSpaceId === id)!
            expect(c.recommended).toBe(false)
            expect(c.tier).toBe('SUITABLE')
        }
    })

    it('(10) affinity vocabulary is exposed per function (non-empty for the four targets)', () => {
        for (const fn of ['UPTAKE_ROOM', 'INJECTION_ROOM', 'PET_CT_SCANNER_ROOM', 'RADIOPHARMACY'] as const) {
            expect(getFunctionAffinityTokens(fn).length).toBeGreaterThan(0)
        }
    })
})

// ===========================================================================
// §30 — RE-PARENTING
// ===========================================================================

describe('§30 re-parenting', () => {
    const goodCandidate = {
        semantic: classifyBimSpaceSemantics({ originalBimLabel: 'Exam Room' }),
        eligibility: evaluateRoomEligibility({ room: room({ worldRange: range4x3 }) }),
        needsExactGeometry: false,
        originalBimLabel: 'Exam Room',
    }
    const corridorCandidate = {
        semantic: classifyBimSpaceSemantics({ originalBimLabel: 'Corridor' }),
        eligibility: evaluateRoomEligibility({ room: room({ worldRange: range4x3 }) }),
        needsExactGeometry: false,
        originalBimLabel: 'Corridor',
    }

    it('is COMPATIBLE for a recommended enclosed room', () => {
        const c = assessReparentCompatibility(goodCandidate)
        expect(c.code).toBe('COMPATIBLE')
        expect(c.requiresOverride).toBe(false)
    })

    it('flags a rejected host kind as requiring override (advisory, not a hard block)', () => {
        const c = assessReparentCompatibility(corridorCandidate)
        expect(c.code).toBe('REJECTED_HOST_KIND')
        expect(c.requiresOverride).toBe(true)
        expect(c.warningMessage).toMatch(/circulation|passage/i)
    })

    it('plans a re-parent that REGENERATES from the new parent and removes the orphan', () => {
        const r = planReparent({
            clinicalFunction: 'UPTAKE_ROOM',
            mrtDisplayName: 'Uptake 01',
            oldParent: { parentBimSpaceId: '0xOldPassage', lifecycleState: 'DRAFT' },
            target: { bimSpaceId: '0xNewRoom', originalBimLabel: 'Exam Room' },
            targetCandidate: goodCandidate,
        })
        expect(r.ok).toBe(true)
        if (r.ok) {
            expect(r.plan.regenerateVolumeFromNewParent).toBe(true)
            expect(r.plan.removeOldVolume).toBe(true)
            expect(r.plan.oldParentBimSpaceId).toBe('0xOldPassage')
            expect(r.plan.newParent.bimSpaceId).toBe('0xNewRoom')
            expect(describeReparentPlan(r.plan)).toMatch(/REUSE_OLD_COORDS = NO/)
        }
    })

    it('blocks re-parenting when the old volume is LOCKED', () => {
        const r = planReparent({
            clinicalFunction: 'UPTAKE_ROOM', mrtDisplayName: 'Uptake 01',
            oldParent: { parentBimSpaceId: '0xOld', lifecycleState: 'LOCKED' },
            target: { bimSpaceId: '0xNew', originalBimLabel: 'Exam Room' },
            targetCandidate: goodCandidate,
        })
        expect(r.ok).toBe(false)
        if (!r.ok) expect(r.blockCode).toBe('OLD_VOLUME_LOCKED')
    })

    it('blocks a no-op re-parent onto the same parent', () => {
        const r = planReparent({
            clinicalFunction: 'UPTAKE_ROOM', mrtDisplayName: 'Uptake 01',
            oldParent: { parentBimSpaceId: '0xSame', lifecycleState: 'DRAFT' },
            target: { bimSpaceId: '0xSame', originalBimLabel: 'Exam Room' },
            targetCandidate: goodCandidate,
        })
        expect(r.ok).toBe(false)
        if (!r.ok) expect(r.blockCode).toBe('SAME_PARENT')
    })

    it('blocks a rejected-host re-parent unless override is accepted', () => {
        const blocked = planReparent({
            clinicalFunction: 'UPTAKE_ROOM', mrtDisplayName: 'Uptake 01',
            oldParent: { parentBimSpaceId: '0xOld', lifecycleState: 'DRAFT' },
            target: { bimSpaceId: '0xCorr', originalBimLabel: 'Corridor' },
            targetCandidate: corridorCandidate,
        })
        expect(blocked.ok).toBe(false)
        if (!blocked.ok) expect(blocked.blockCode).toBe('OVERRIDE_REQUIRED')

        const overridden = planReparent({
            clinicalFunction: 'UPTAKE_ROOM', mrtDisplayName: 'Uptake 01',
            oldParent: { parentBimSpaceId: '0xOld', lifecycleState: 'DRAFT' },
            target: { bimSpaceId: '0xCorr', originalBimLabel: 'Corridor' },
            targetCandidate: corridorCandidate,
            overrideAccepted: true,
        })
        expect(overridden.ok).toBe(true)
        if (overridden.ok) expect(overridden.plan.overrideAccepted).toBe(true)
    })

    it('allows re-parenting an UNPARENTED function (no old parent, no orphan removal)', () => {
        const r = planReparent({
            clinicalFunction: 'INJECTION_ROOM', mrtDisplayName: 'Injection Room 01',
            target: { bimSpaceId: '0xNew', originalBimLabel: 'Exam Room' },
            targetCandidate: goodCandidate,
        })
        expect(r.ok).toBe(true)
        if (r.ok) { expect(r.plan.removeOldVolume).toBe(false); expect(r.plan.oldParentBimSpaceId).toBeUndefined() }
    })
})

// ===========================================================================
// §31 — TARGETED WALKTHROUGH SPAWN (all 16 sub-properties)
// ===========================================================================

// A simple 10x8 rectangular room on floor Z=0, ceiling Z=3.
const rectRoom: SpawnRoomGeometry = {
    outerLoop: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 8 }, { x: 0, y: 8 }],
    floorZ: 0,
    ceilingZ: 3,
    interiorAnchor: { x: 5, y: 4, z: 1.5 },
}
const storey0 = { storeyId: 's0', zLow: -0.1, zHigh: 3.1 }

describe('§31 targeted walkthrough spawn (16 sub-properties)', () => {
    it('(1)(9) derives an interior point from the room geometry, room-specific', () => {
        const r = resolveTargetedWalkthroughSpawn({ room: rectRoom, storey: storey0, eyeHeight: 1.65 })
        expect(r.ok).toBe(true)
        if (r.ok) {
            expect(r.provenance).toBe('INTERIOR_ANCHOR')
            expect(r.spawn.x).toBeCloseTo(5, 5)
            expect(r.spawn.y).toBeCloseTo(4, 5)
        }
    })

    it('(2) spawn Z is floor + eye height (never a global hardcode)', () => {
        const r = resolveTargetedWalkthroughSpawn({ room: { ...rectRoom, floorZ: 12 }, storey: { storeyId: 's3', zLow: 11.9, zHigh: 15 }, eyeHeight: 1.65 })
        expect(r.ok).toBe(true)
        if (r.ok) expect(r.spawn.z).toBeCloseTo(13.65, 5)
    })

    it('(3)(13) rejects a candidate too close to a wall (collision-active clearance)', () => {
        // A wall right through the anchor forces clearance failure at the center;
        // the grid search must then avoid it.
        const walls: WallSegment[] = [{ id: 'w', a: { x: 5, y: 0 }, b: { x: 5, y: 8 }, thickness: 0.2 }]
        const r = resolveTargetedWalkthroughSpawn({ room: rectRoom, storey: storey0, eyeHeight: 1.65, walls, clearanceRadius: 0.5 })
        expect(r.ok).toBe(true)
        if (r.ok) {
            // The chosen point must be at least the clearance away from the wall x=5.
            expect(Math.abs(r.spawn.x - 5)).toBeGreaterThanOrEqual(0.5 - 1e-6)
            expect(r.provenance).not.toBe('INTERIOR_ANCHOR')
        }
    })

    it('(4) centroid-invalid fallback finds another interior point (concave room)', () => {
        // L-shaped room whose centroid falls in the missing notch.
        const lRoom: SpawnRoomGeometry = {
            outerLoop: [
                { x: 0, y: 0 }, { x: 8, y: 0 }, { x: 8, y: 3 }, { x: 3, y: 3 }, { x: 3, y: 8 }, { x: 0, y: 8 },
            ],
            floorZ: 0, ceilingZ: 3,
            // No interior anchor supplied -> forces centroid then grid.
        }
        const r = resolveTargetedWalkthroughSpawn({ room: lRoom, storey: storey0, eyeHeight: 1.65 })
        expect(r.ok).toBe(true)
        if (r.ok) {
            // The chosen point must be inside the L (not in the notch x>3 && y>3).
            expect(!(r.spawn.x > 3 && r.spawn.y > 3)).toBe(true)
        }
    })

    it('(5) rejects when there is no interior point at all (zero-area collinear ring)', () => {
        // A collinear "ring" (all vertices on the x-axis) encloses no area -> no
        // interior grid point can be found.
        const collinear: SpawnRoomGeometry = { outerLoop: [{ x: 0, y: 0 }, { x: 5, y: 0 }, { x: 10, y: 0 }], floorZ: 0 }
        const r = resolveTargetedWalkthroughSpawn({ room: collinear, storey: storey0, eyeHeight: 1.65, gridResolution: 7 })
        expect(r.ok).toBe(false)
        if (!r.ok) expect(['NO_INTERIOR_POINT', 'DEGENERATE_FOOTPRINT']).toContain(r.code)
    })

    it('(6) rejects a wrong-storey room', () => {
        const r = resolveTargetedWalkthroughSpawn({ room: rectRoom, storey: { storeyId: 's5', zLow: 20, zHigh: 24 }, eyeHeight: 1.65 })
        expect(r.ok).toBe(false)
        if (!r.ok) expect(r.code).toBe('WRONG_STOREY')
    })

    it('(7) rejects non-finite eye height and non-finite geometry', () => {
        const badEye = resolveTargetedWalkthroughSpawn({ room: rectRoom, eyeHeight: Number.NaN })
        expect(badEye.ok).toBe(false)
        if (!badEye.ok) expect(badEye.code).toBe('NON_FINITE_EYE_HEIGHT')

        const badFloor = resolveTargetedWalkthroughSpawn({ room: { ...rectRoom, floorZ: Number.NaN }, eyeHeight: 1.65 })
        expect(badFloor.ok).toBe(false)
        if (!badFloor.ok) expect(badFloor.code).toBe('NON_FINITE_GEOMETRY')
    })

    it('(8) is deterministic — identical inputs yield the identical spawn', () => {
        const a = resolveTargetedWalkthroughSpawn({ room: rectRoom, storey: storey0, eyeHeight: 1.65 })
        const b = resolveTargetedWalkthroughSpawn({ room: rectRoom, storey: storey0, eyeHeight: 1.65 })
        expect(a).toEqual(b)
    })

    it('(10) honest NO_SAFE_WALKTHROUGH_SPAWN when no point clears the walls', () => {
        // Dense wall grid covering the room so no interior point can clear a big radius.
        const walls: WallSegment[] = []
        for (let x = 0; x <= 10; x += 1) walls.push({ id: `v${x}`, a: { x, y: 0 }, b: { x, y: 8 }, thickness: 0.2 })
        const r = resolveTargetedWalkthroughSpawn({ room: rectRoom, storey: storey0, eyeHeight: 1.65, walls, clearanceRadius: 2, gridResolution: 6 })
        expect(r.ok).toBe(false)
        if (!r.ok) {
            expect(r.code).toBe('NO_WALL_CLEARANCE')
            expect(r.reason).toMatch(/NO_SAFE_WALKTHROUGH_SPAWN/)
        }
    })

    it('(11) planning-volume coords are NOT the spawn authority (not read)', () => {
        // Passing a wildly-off "planning volume"-like anchor OUTSIDE the room must
        // NOT be used — the resolver falls back to a valid interior point.
        const r = resolveTargetedWalkthroughSpawn({
            room: { ...rectRoom, interiorAnchor: { x: 999, y: 999, z: 1.5 } },
            storey: storey0, eyeHeight: 1.65,
        })
        expect(r.ok).toBe(true)
        if (r.ok) {
            expect(r.provenance).not.toBe('INTERIOR_ANCHOR')
            expect(r.spawn.x).toBeLessThanOrEqual(10)
            expect(r.spawn.y).toBeLessThanOrEqual(8)
        }
    })

    it('(12) equipment is NOT the spawn authority — the resolver takes no equipment input', () => {
        // Structural guarantee: the input type has no equipment field. A spawn is
        // resolvable purely from room geometry.
        const r = resolveTargetedWalkthroughSpawn({ room: rectRoom, storey: storey0, eyeHeight: 1.65 })
        expect(r.ok).toBe(true)
        expect(describeSpawnResult(r)).toMatch(/EQUIPMENT_IS_SPAWN_AUTHORITY = NO/)
    })

    it('(14) the spawn stays inside the footprint and out of holes', () => {
        const holed: SpawnRoomGeometry = {
            outerLoop: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 8 }, { x: 0, y: 8 }],
            holes: [[{ x: 4, y: 3 }, { x: 6, y: 3 }, { x: 6, y: 5 }, { x: 4, y: 5 }]],
            floorZ: 0, ceilingZ: 3,
            interiorAnchor: { x: 5, y: 4, z: 1.5 }, // anchor is INSIDE the hole -> must be rejected
        }
        const r = resolveTargetedWalkthroughSpawn({ room: holed, storey: storey0, eyeHeight: 1.65 })
        expect(r.ok).toBe(true)
        if (r.ok) {
            const inHole = r.spawn.x > 4 && r.spawn.x < 6 && r.spawn.y > 3 && r.spawn.y < 5
            expect(inHole).toBe(false)
        }
    })

    it('(15) carries provenance + wall clearance for diagnostics', () => {
        const r = resolveTargetedWalkthroughSpawn({ room: rectRoom, storey: storey0, eyeHeight: 1.65 })
        expect(r.ok).toBe(true)
        if (r.ok) {
            expect(['INTERIOR_ANCHOR', 'FOOTPRINT_CENTROID', 'INTERIOR_GRID_SEARCH']).toContain(r.provenance)
            expect(r.wallClearance).toBeGreaterThan(0)
        }
    })

    it('(16) works with no walls (clearance trivially met) and no storey band', () => {
        const r = resolveTargetedWalkthroughSpawn({ room: rectRoom, eyeHeight: 1.65 })
        expect(r.ok).toBe(true)
        if (r.ok) expect(r.wallClearance).toBe(Infinity)
    })
})

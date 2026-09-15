/**
 * clinicalRoomCandidate — pure, Bentley-free CLINICAL-ROOM CANDIDATE DISCOVERY
 * ENGINE for MRT Pharma (Build 1B spatial-foundation correction, Problem A).
 *
 * WHY THIS EXISTS
 *   Manual inspection proved two clinical planning volumes (Uptake 01, Injection
 *   Room 01) were parented onto BIM spaces that are PASSAGE / CIRCULATION space
 *   rather than enclosed clinical rooms. The fix is NOT to hardcode "the right
 *   room ids" — it is to build a GENERIC engine that, for any BIM model, can
 *   surface a ranked, explainable shortlist of candidate rooms for a chosen
 *   clinical function so the user can re-parent onto a defensible room.
 *
 * DOCTRINE (carried from Build 1A):
 *   - The source BIM room stays IMMUTABLE. Nothing here mutates a Bentley
 *     identity, label, range, or mesh. This layer only READS DiscoveredRoomVolume
 *     facts (from bimRoomVolumeRegistry) plus optional bounded footprint metrics.
 *   - No @itwin import. Deterministic, camera-independent, unit-testable.
 *   - NO fabricated regulatory minimums. Geometric eligibility uses only honest
 *     numerical-sanity thresholds (finite, positive, non-degenerate). It never
 *     asserts a clinical/radiation-safety area or shielding requirement — those
 *     are downstream analyses this build does not perform.
 *   - CONTAINMENT_EQUALS_CLINICAL_SUITABILITY = NO. Whether a planning prism
 *     geometrically FITS inside a parent (containment) is a SEPARATE question
 *     from whether the room is a semantically-appropriate clinical host. A
 *     corridor can "contain" a prism yet be a poor clinical host; this engine
 *     keeps the two axes independent and reports both.
 *   - UNKNOWN semantics are NOT auto-rejected. A room whose label matches no
 *     known vocabulary is eligible (lower confidence), never silently dropped.
 *
 * STAGED EVALUATION (coarse -> shortlist -> lazy exact):
 *   1. classifyBimSpaceSemantics  — label-vocabulary classification (cheap).
 *   2. evaluateRoomEligibility     — coarse geometric sanity from already-known
 *                                    range/footprint facts (cheap; no extraction).
 *   3. rankClinicalRoomCandidates  — per-function scoring + explainable reasons,
 *                                    marking which rooms WOULD benefit from lazy
 *                                    EXACT-mesh extraction before final selection.
 *   The overlay performs the actual lazy exact extraction (ensureAuthoritative-
 *   RoomFootprint) only for the shortlisted rooms — never here.
 */

import type { DiscoveredRoomVolume, RoomVolumeGeometryQuality } from './bimRoomVolumeRegistry'
import type { ClinicalFunction } from './clinicalProgram'

// ===========================================================================
// 1. SEMANTIC CLASSIFICATION (label-vocabulary classifier)
// ===========================================================================

/**
 * The coarse semantic KIND a BIM source label maps to. This is deliberately
 * SMALL and product-facing — it answers "could this plausibly be an enclosed
 * clinical room?" not "what exact IFC subtype is it?".
 *
 *   ENCLOSED_ROOM      — a generic enclosed room (default host candidate).
 *   CIRCULATION        — corridor / hallway / passage / lobby / vestibule.
 *   VERTICAL_TRANSPORT — stair / elevator / escalator / ramp.
 *   SHAFT              — shaft / duct / chase / riser (non-occupiable void).
 *   SERVICE_SUPPORT    — mechanical / electrical / plant / IT / janitor.
 *   SANITARY           — toilet / WC / bathroom / shower / restroom.
 *   OPEN_OR_EXTERIOR   — open area / atrium / courtyard / roof / parking.
 *   UNKNOWN            — label matched no known vocabulary (NOT auto-rejected).
 */
export type BimSpaceSemanticKind =
    | 'ENCLOSED_ROOM' // a dedicated clinical/functional room word (exam, lab, injection, scanner…)
    | 'GENERIC_OCCUPIABLE' // enclosed occupiable space but NOT a dedicated clinical room (waiting, activity, lounge…)
    | 'CIRCULATION'
    | 'VERTICAL_TRANSPORT'
    | 'SHAFT'
    | 'SERVICE_SUPPORT'
    | 'SANITARY'
    | 'OPEN_OR_EXTERIOR'
    | 'UNKNOWN'

/**
 * Whether a semantic kind is REJECTED as a clinical host by default. Circulation,
 * vertical transport, shafts, sanitary, and open/exterior space are rejected
 * (they are the observed defect class — clinical volumes must not live in
 * passage/void space). SERVICE_SUPPORT is rejected as a default clinical host too
 * (it is plant space), but the user can still override. ENCLOSED_ROOM and UNKNOWN
 * are NOT rejected.
 */
export function isRejectedClinicalHostKind(kind: BimSpaceSemanticKind): boolean {
    switch (kind) {
        case 'CIRCULATION':
        case 'VERTICAL_TRANSPORT':
        case 'SHAFT':
        case 'SANITARY':
        case 'OPEN_OR_EXTERIOR':
        case 'SERVICE_SUPPORT':
            return true
        case 'ENCLOSED_ROOM':
        case 'GENERIC_OCCUPIABLE':
        case 'UNKNOWN':
            return false
    }
}

/** A single vocabulary rule: keyword tokens -> semantic kind. */
interface SemanticVocabularyRule {
    kind: BimSpaceSemanticKind
    /** Lowercased whole-word/substring tokens. First matching rule (in order) wins. */
    tokens: readonly string[]
}

/**
 * The ordered classification vocabulary. Order matters: more specific / more
 * strongly-rejecting kinds are listed FIRST so e.g. "mechanical corridor" is
 * treated as CIRCULATION-relevant only if no stronger reject token matched. The
 * tokens are intentionally broad (BIM authoring varies wildly across models).
 *
 * This is EXPORTED so the report / tests can enumerate the exact vocabulary used
 * (the user asked the engine to "return the discovered vocabulary").
 */
export const CLINICAL_HOST_SEMANTIC_VOCABULARY: readonly SemanticVocabularyRule[] = [
    { kind: 'VERTICAL_TRANSPORT', tokens: ['stair', 'stairwell', 'stairs', 'elevator', 'lift', 'escalator', 'ramp'] },
    { kind: 'SHAFT', tokens: ['shaft', 'duct', 'chase', 'riser', 'plenum', 'void'] },
    { kind: 'SANITARY', tokens: ['toilet', 'wc', 'restroom', 'bathroom', 'washroom', 'shower', 'lavatory', 'water closet'] },
    { kind: 'SERVICE_SUPPORT', tokens: ['mechanical', 'electrical', 'plant', 'boiler', 'switchgear', 'server', 'it room', 'comms', 'janitor', 'cleaner', 'mep', 'utility', 'telecom', 'ups'] },
    { kind: 'CIRCULATION', tokens: ['corridor', 'hallway', 'hall', 'passage', 'passageway', 'lobby', 'foyer', 'vestibule', 'circulation', 'walkway', 'concourse'] },
    { kind: 'OPEN_OR_EXTERIOR', tokens: ['atrium', 'courtyard', 'open area', 'open space', 'roof', 'terrace', 'balcony', 'parking', 'garage', 'exterior', 'outdoor', 'garden'] },
    // NOTE: the generic IfcSpace class token ('space') is intentionally EXCLUDED
    // — nearly every BIM room is a BuildingSpatial:Space, so matching it would
    // upgrade every unknown-label room to a confident ENCLOSED_ROOM and defeat
    // the "unknown = neutral, not auto-rejected" doctrine. A room is classified
    // ENCLOSED_ROOM only when its LABEL carries an actual DEDICATED CLINICAL /
    // FUNCTIONAL room word (Build 1B calibration).
    //
    // ENCLOSED_ROOM = a DEDICATED clinical/functional room. These are the only
    // labels that earn FULL semantic confidence as a clinical host.
    { kind: 'ENCLOSED_ROOM', tokens: ['office', 'lab', 'laboratory', 'suite', 'ward', 'clinic', 'exam', 'examination', 'consult', 'procedure', 'scanner', 'imaging', 'ct', 'pet', 'spect', 'mri', 'injection', 'uptake', 'radiopharmacy', 'pharmacy', 'dispensing', 'hot cell', 'cyclotron', 'control', 'prep', 'preparation', 'recovery', 'clean'] },
    // GENERIC_OCCUPIABLE = an enclosed occupiable space that is NOT a dedicated
    // clinical room. A "WAITING / ACTIVITY AREA" is contextually relevant but is
    // NOT proof of uptake-room suitability — it earns only MODERATE confidence
    // (Build 1B calibration: WAITING ≠ UPTAKE_ROOM, ACTIVITY AREA ≠ clinical room).
    // The bare word 'room' also lands here (a generic "Room 214" is occupiable but
    // carries no clinical-function evidence). 'bay' and 'store/storage' are
    // support-ish occupiable spaces, not dedicated clinical rooms.
    { kind: 'GENERIC_OCCUPIABLE', tokens: ['waiting', 'activity', 'activity area', 'lounge', 'reception', 'day room', 'dayroom', 'bay', 'store', 'storage', 'room'] },
]

/**
 * The result of classifying a single BIM source label. Carries the matched kind,
 * the token that matched (explainability), and whether it is a default-rejected
 * host. `matchedVocabulary === false` means UNKNOWN (no token matched).
 */
export interface BimSpaceSemanticClassification {
    /** The original, unaltered BIM label that was classified. */
    originalBimLabel: string
    kind: BimSpaceSemanticKind
    /** True unless kind === UNKNOWN. */
    matchedVocabulary: boolean
    /** The specific keyword token that decided the kind ('' when UNKNOWN). */
    matchedToken: string
    /** Whether this kind is a default-rejected clinical host. */
    rejectedByDefault: boolean
    /** Concise, product-facing explanation of the classification. */
    reason: string
}

/** Normalize a label for token matching (lowercase, collapse separators). */
function normalizeLabel(label: string): string {
    return (label || '')
        .toLowerCase()
        .replace(/[_\-/:.]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
}

/**
 * Classify a BIM source label into a coarse semantic kind using the ordered
 * vocabulary. Deterministic; the FIRST rule (in vocabulary order) with any
 * matching token wins. No token match => UNKNOWN (never auto-rejected).
 *
 * Both the original BIM label AND the BIM source class (e.g. "IfcSpace",
 * "BuildingSpatial:Space") are considered — some models encode the room purpose
 * in the class rather than the label.
 */
export function classifyBimSpaceSemantics(input: {
    originalBimLabel: string
    sourceClass?: string
}): BimSpaceSemanticClassification {
    const label = input.originalBimLabel ?? ''
    const haystack = normalizeLabel(`${label} ${input.sourceClass ?? ''}`)

    for (const rule of CLINICAL_HOST_SEMANTIC_VOCABULARY) {
        for (const token of rule.tokens) {
            if (tokenMatches(haystack, token)) {
                return {
                    originalBimLabel: label,
                    kind: rule.kind,
                    matchedVocabulary: true,
                    matchedToken: token,
                    rejectedByDefault: isRejectedClinicalHostKind(rule.kind),
                    reason: describeKind(rule.kind, token),
                }
            }
        }
    }
    return {
        originalBimLabel: label,
        kind: 'UNKNOWN',
        matchedVocabulary: false,
        matchedToken: '',
        rejectedByDefault: false,
        reason: 'Label matched no known room vocabulary; treated as a possible room (unknown, not rejected).',
    }
}

/** Whole-word-ish token match: matches token as a bounded substring. */
function tokenMatches(haystack: string, token: string): boolean {
    if (!token) return false
    if (token.includes(' ')) return haystack.includes(token) // multi-word phrase
    // Single word: match on word boundaries so "corridor" != "office corridors"? we
    // still want "corridors" to match "corridor", so use prefix-at-word-boundary.
    const idx = haystack.indexOf(token)
    if (idx < 0) return false
    const before = idx === 0 ? ' ' : haystack[idx - 1]
    return before === ' ' // token starts at a word boundary; suffixes (plural) allowed
}

function describeKind(kind: BimSpaceSemanticKind, token: string): string {
    switch (kind) {
        case 'CIRCULATION': return `Circulation/passage space (matched "${token}") — not an enclosed clinical room.`
        case 'VERTICAL_TRANSPORT': return `Vertical transport (matched "${token}") — not an occupiable clinical room.`
        case 'SHAFT': return `Shaft/void (matched "${token}") — not an occupiable clinical room.`
        case 'SERVICE_SUPPORT': return `Service/plant space (matched "${token}") — not a default clinical host.`
        case 'SANITARY': return `Sanitary space (matched "${token}") — not a clinical host.`
        case 'OPEN_OR_EXTERIOR': return `Open/exterior space (matched "${token}") — not an enclosed clinical room.`
        case 'ENCLOSED_ROOM': return `Dedicated clinical/functional room (matched "${token}") — a strong clinical host.`
        case 'GENERIC_OCCUPIABLE': return `Enclosed occupiable space (matched "${token}") — relevant but NOT a dedicated clinical room; verify suitability.`
        case 'UNKNOWN': return 'Unknown space.'
    }
}

/**
 * The distinct vocabulary actually observed across a set of discovered rooms.
 * The user asked the engine to surface the vocabulary rather than hide it. Pure.
 */
export interface DiscoveredSemanticVocabulary {
    /** Distinct semantic kinds observed, with counts. */
    kindCounts: Record<BimSpaceSemanticKind, number>
    /** Distinct matched tokens observed (sorted). */
    matchedTokens: string[]
    /** Distinct original labels that classified as UNKNOWN (sorted, bounded). */
    unknownLabels: string[]
}

export function summarizeDiscoveredVocabulary(
    classifications: readonly BimSpaceSemanticClassification[],
): DiscoveredSemanticVocabulary {
    const kindCounts: Record<BimSpaceSemanticKind, number> = {
        ENCLOSED_ROOM: 0, GENERIC_OCCUPIABLE: 0, CIRCULATION: 0, VERTICAL_TRANSPORT: 0, SHAFT: 0,
        SERVICE_SUPPORT: 0, SANITARY: 0, OPEN_OR_EXTERIOR: 0, UNKNOWN: 0,
    }
    const tokens = new Set<string>()
    const unknown = new Set<string>()
    for (const c of classifications) {
        kindCounts[c.kind] += 1
        if (c.matchedToken) tokens.add(c.matchedToken)
        if (c.kind === 'UNKNOWN' && c.originalBimLabel) unknown.add(c.originalBimLabel)
    }
    return {
        kindCounts,
        matchedTokens: [...tokens].sort(),
        unknownLabels: [...unknown].sort().slice(0, 50),
    }
}

// ===========================================================================
// 2. GEOMETRIC ELIGIBILITY (coarse sanity — NO fabricated regulatory minimums)
// ===========================================================================

/**
 * Honest numerical-sanity floor for a "usable planning host". These are NOT
 * clinical/radiation-safety requirements — they only reject degenerate geometry
 * (a zero-area sliver, a collapsed height) that could never host ANY prism. A
 * room below these is flagged as geometrically too small to plan inside, never as
 * "clinically non-compliant".
 */
export const MIN_HOST_FLOOR_AREA_M2 = 1.0 // reject sub-1m^2 slivers (numerical only)
export const MIN_HOST_CLEAR_HEIGHT_M = 1.8 // reject collapsed vertical extents
export const MIN_HOST_PLAN_DIM_M = 0.6 // reject a room narrower than a doorway

/** Why a room is / isn't geometrically eligible. */
export type RoomEligibilityCode =
    | 'ELIGIBLE'
    | 'GEOMETRY_UNKNOWN' // no usable range/footprint/mesh at all
    | 'DEGENERATE_AREA' // finite but below the numerical area floor
    | 'DEGENERATE_HEIGHT' // finite but below the numerical height floor
    | 'DEGENERATE_PLAN_DIM' // one plan dimension below the doorway floor
    | 'NON_FINITE' // range/footprint present but non-finite

/**
 * Coarse geometric metrics derived from what we ALREADY know about a room
 * (its world range and/or footprint). No mesh extraction here.
 */
export interface RoomGeometryMetrics {
    /** Approx floor area (m^2) from footprint (preferred) or range XY. */
    floorAreaM2?: number
    /** Approx clear height (m) from range/footprint Z extent. */
    clearHeightM?: number
    /** Approx smaller plan dimension (m). */
    minPlanDimM?: number
    /** Approx larger plan dimension (m). */
    maxPlanDimM?: number
    /** Whether metrics came from an exact footprint (vs an axis-aligned range). */
    fromFootprint: boolean
}

/**
 * A room's geometric eligibility to HOST a planning volume. This is the
 * containment-INDEPENDENT axis (a corridor may be geometrically "eligible" to
 * hold a box yet be a poor clinical host — see semantic classification).
 */
export interface RoomEligibility {
    code: RoomEligibilityCode
    eligible: boolean
    metrics: RoomGeometryMetrics
    /** How trustworthy the geometry backing this eligibility is. */
    geometryQuality: RoomVolumeGeometryQuality
    /** Product-facing explanation. */
    reason: string
}

function isFiniteNum(n: unknown): n is number { return typeof n === 'number' && Number.isFinite(n) }

/**
 * Derive coarse geometry metrics for a room from its DiscoveredRoomVolume facts
 * plus an optional exact footprint (world XY ring + Z) supplied by the overlay's
 * lazy authoritative-footprint cache. Prefers the exact footprint when present.
 * Pure; never triggers extraction.
 */
export function deriveRoomGeometryMetrics(input: {
    room: Pick<DiscoveredRoomVolume, 'worldRange' | 'geometryQuality'>
    footprint?: { outerLoop: readonly { x: number; y: number }[]; floorZ?: number; zLow?: number; zHigh?: number }
}): RoomGeometryMetrics {
    const fp = input.footprint
    if (fp && fp.outerLoop.length >= 3) {
        const area = polygonArea(fp.outerLoop)
        const { minDim, maxDim } = ringPlanDims(fp.outerLoop)
        const zLow = isFiniteNum(fp.zLow) ? fp.zLow : (isFiniteNum(fp.floorZ) ? fp.floorZ : undefined)
        const zHigh = isFiniteNum(fp.zHigh) ? fp.zHigh : undefined
        const height = isFiniteNum(zLow) && isFiniteNum(zHigh) ? zHigh - zLow : undefined
        return {
            floorAreaM2: isFiniteNum(area) ? area : undefined,
            clearHeightM: isFiniteNum(height) && (height as number) > 0 ? height : undefined,
            minPlanDimM: isFiniteNum(minDim) ? minDim : undefined,
            maxPlanDimM: isFiniteNum(maxDim) ? maxDim : undefined,
            fromFootprint: true,
        }
    }
    const r = input.room.worldRange
    if (r) {
        const dx = r.high.x - r.low.x
        const dy = r.high.y - r.low.y
        const dz = r.high.z - r.low.z
        if ([dx, dy, dz].every(isFiniteNum)) {
            return {
                floorAreaM2: dx > 0 && dy > 0 ? dx * dy : 0,
                clearHeightM: dz > 0 ? dz : 0,
                minPlanDimM: Math.min(Math.abs(dx), Math.abs(dy)),
                maxPlanDimM: Math.max(Math.abs(dx), Math.abs(dy)),
                fromFootprint: false,
            }
        }
    }
    return { fromFootprint: false }
}

/** Shoelace polygon area (absolute, m^2). */
function polygonArea(ring: readonly { x: number; y: number }[]): number {
    let a = 0
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        a += (ring[j].x + ring[i].x) * (ring[j].y - ring[i].y)
    }
    return Math.abs(a) / 2
}

/** Approx min/max plan dimension from a ring's axis-aligned bounding box. */
function ringPlanDims(ring: readonly { x: number; y: number }[]): { minDim: number; maxDim: number } {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const p of ring) {
        if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x
        if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y
    }
    const w = maxX - minX
    const d = maxY - minY
    return { minDim: Math.min(w, d), maxDim: Math.max(w, d) }
}

/**
 * Evaluate a room's containment-INDEPENDENT geometric eligibility to host a
 * planning volume. Rejects only DEGENERATE geometry using honest numerical
 * floors (never a fabricated clinical minimum). GEOMETRY_UNKNOWN when no usable
 * geometry is available — this is NOT ineligible-forever, it means "extract the
 * exact mesh (lazy) before deciding".
 */
export function evaluateRoomEligibility(input: {
    room: Pick<DiscoveredRoomVolume, 'worldRange' | 'geometryQuality'>
    footprint?: { outerLoop: readonly { x: number; y: number }[]; floorZ?: number; zLow?: number; zHigh?: number }
}): RoomEligibility {
    const metrics = deriveRoomGeometryMetrics(input)
    const quality = input.room.geometryQuality

    const hasAnyGeometry = metrics.floorAreaM2 !== undefined || metrics.clearHeightM !== undefined
    if (!hasAnyGeometry) {
        return {
            code: 'GEOMETRY_UNKNOWN', eligible: false, metrics, geometryQuality: quality,
            reason: 'No usable geometry yet — extract the exact room mesh before evaluating eligibility.',
        }
    }

    // Non-finite guard (a present-but-broken range/footprint).
    const numericFields = [metrics.floorAreaM2, metrics.clearHeightM, metrics.minPlanDimM].filter((v) => v !== undefined) as number[]
    if (numericFields.some((n) => !Number.isFinite(n))) {
        return {
            code: 'NON_FINITE', eligible: false, metrics, geometryQuality: quality,
            reason: 'Room geometry contains non-finite values and cannot be used as a planning host.',
        }
    }

    if (metrics.floorAreaM2 !== undefined && metrics.floorAreaM2 < MIN_HOST_FLOOR_AREA_M2) {
        return {
            code: 'DEGENERATE_AREA', eligible: false, metrics, geometryQuality: quality,
            reason: `Floor area (${metrics.floorAreaM2.toFixed(2)} m²) is below the numerical minimum to host any volume.`,
        }
    }
    if (metrics.minPlanDimM !== undefined && metrics.minPlanDimM < MIN_HOST_PLAN_DIM_M) {
        return {
            code: 'DEGENERATE_PLAN_DIM', eligible: false, metrics, geometryQuality: quality,
            reason: `Narrowest plan dimension (${metrics.minPlanDimM.toFixed(2)} m) is below a usable minimum.`,
        }
    }
    if (metrics.clearHeightM !== undefined && metrics.clearHeightM < MIN_HOST_CLEAR_HEIGHT_M) {
        return {
            code: 'DEGENERATE_HEIGHT', eligible: false, metrics, geometryQuality: quality,
            reason: `Clear height (${metrics.clearHeightM.toFixed(2)} m) is below a usable minimum.`,
        }
    }

    return {
        code: 'ELIGIBLE', eligible: true, metrics, geometryQuality: quality,
        reason: metrics.fromFootprint
            ? 'Room geometry is usable (from exact footprint) to host a planning volume.'
            : 'Room geometry is usable (from BIM range approximation) to host a planning volume.',
    }
}

// ===========================================================================
// 3. PER-FUNCTION RANKING (explainable candidates)
// ===========================================================================

/**
 * A soft, product-facing footprint PREFERENCE per clinical function. These are
 * PREFERENCES used only to RANK already-eligible rooms — they are NOT gates and
 * NOT regulatory minimums. A room outside a preference band is still a valid
 * candidate; it simply scores lower with an explicit reason. Values are
 * deliberately generous planning heuristics, not code requirements.
 */
export interface ClinicalFunctionSpatialProfile {
    clinicalFunction: ClinicalFunction
    /** Preferred floor-area band (m^2); rooms far outside score lower. */
    preferredAreaM2: { min: number; ideal: number }
    /** A short human descriptor of the space's typical role. */
    descriptor: string
}

/**
 * Spatial profiles for the four functions the correction targets. Every value is
 * a soft planning preference (explicitly NOT a regulatory minimum). Functions not
 * listed fall back to a generic profile.
 */
export const CLINICAL_FUNCTION_SPATIAL_PROFILES: Partial<Record<ClinicalFunction, ClinicalFunctionSpatialProfile>> = {
    UPTAKE_ROOM: { clinicalFunction: 'UPTAKE_ROOM', preferredAreaM2: { min: 6, ideal: 12 }, descriptor: 'quiet enclosed uptake room for a single reclining patient' },
    INJECTION_ROOM: { clinicalFunction: 'INJECTION_ROOM', preferredAreaM2: { min: 6, ideal: 12 }, descriptor: 'enclosed injection/dosing room' },
    PET_CT_SCANNER_ROOM: { clinicalFunction: 'PET_CT_SCANNER_ROOM', preferredAreaM2: { min: 20, ideal: 35 }, descriptor: 'large scanner room housing a PET/CT gantry with clearance' },
    RADIOPHARMACY: { clinicalFunction: 'RADIOPHARMACY', preferredAreaM2: { min: 12, ideal: 25 }, descriptor: 'radiopharmacy / hot lab with hot cells and dispensing' },
}

const GENERIC_PROFILE: ClinicalFunctionSpatialProfile = {
    clinicalFunction: 'GENERAL_SUPPORT',
    preferredAreaM2: { min: 4, ideal: 12 },
    descriptor: 'generic clinical support room',
}

export function resolveFunctionSpatialProfile(fn: ClinicalFunction): ClinicalFunctionSpatialProfile {
    return CLINICAL_FUNCTION_SPATIAL_PROFILES[fn] ?? { ...GENERIC_PROFILE, clinicalFunction: fn }
}

/**
 * A single ranked, explainable candidate. `clinicalSuitabilityScore` and
 * `geometricFitScore` are INDEPENDENT axes (CONTAINMENT_EQUALS_CLINICAL_
 * SUITABILITY = NO). The overall score blends them but the reasons preserve the
 * distinction so the UI can show WHY.
 */
export interface RankedRoomCandidate {
    bimSpaceId: string
    originalBimLabel: string
    mrtDisplayName?: string
    storeyId?: string
    clinicalFunction: ClinicalFunction
    /** Semantic host classification (corridor/etc rejected; unknown allowed). */
    semantic: BimSpaceSemanticClassification
    /** Geometric eligibility (degenerate rejection; NOT clinical suitability). */
    eligibility: RoomEligibility
    /** 0..1 — how appropriate the room SEMANTICS are for this function. */
    clinicalSuitabilityScore: number
    /** 0..1 — how well the room GEOMETRY fits the function's spatial preference. */
    geometricFitScore: number
    /** 0..1 blended rank score (semantics weighted higher than raw fit). */
    score: number
    /** Explicit acceptance tier (Build 1B calibration — eligible ≠ recommended). */
    tier: CandidateTier
    /** Whether this candidate is RECOMMENDED (derived: tier === 'RECOMMENDED'). */
    recommended: boolean
    /** Whether extracting the exact mesh would improve confidence (lazy hint). */
    needsExactGeometry: boolean
    /**
     * Build 1B §A: TRUE when the room LABEL carries affirmative, function-specific
     * semantic evidence for this function. RECOMMENDED requires this to be true.
     */
    hasFunctionSemanticEvidence: boolean
    /**
     * Build 1B §A: TRUE when a HIGH-scoring room (score ≥ RECOMMENDED threshold)
     * was demoted below RECOMMENDED purely because it lacked function-specific
     * semantic evidence (geometry alone cannot recommend). Drives the honest
     * "recommendation capped at SUITABLE" explanation in the UI.
     */
    cappedForNoSemanticEvidence: boolean
    /** Ordered, human-readable reasons (explainability). */
    reasons: string[]
    /** Whether this room is the current parent for the function being re-homed. */
    isCurrentParent: boolean
}

/** Clamp helper. */
function clamp01(n: number): number { return n < 0 ? 0 : n > 1 ? 1 : n }

// ---------------------------------------------------------------------------
// Candidate acceptance TIER (Build 1B calibration — eligible ≠ recommended)
// ---------------------------------------------------------------------------

/**
 * Explicit acceptance tier. This REPLACES the old binary "recommended = eligible
 * && !rejected" that collapsed every plausible room into RECOMMENDED (the 25/25
 * defect).
 *
 *   RECOMMENDED  — strong semantic + geometric evidence for THIS function.
 *   SUITABLE     — physically/semantically plausible but not a preferred pick.
 *   NEEDS_REVIEW — not rejected, but real uncertainty/mismatch (unknown label,
 *                  generic occupiable space, missing exact geometry, weak fit).
 *   REJECTED     — default-rejected host kind OR degenerate/ineligible geometry.
 *
 * Data-driven score bands (no fixed quota per tier). Tuned so that a DEDICATED
 * clinical room matching the function with good geometry reaches RECOMMENDED,
 * while WAITING/ACTIVITY/UNKNOWN spaces land in SUITABLE/NEEDS_REVIEW.
 */
export type CandidateTier = 'RECOMMENDED' | 'SUITABLE' | 'NEEDS_REVIEW' | 'REJECTED'

/** Score thresholds (blended 0.6·suitability + 0.4·fit). Explicit + testable. */
export const TIER_RECOMMENDED_MIN = 0.75
export const TIER_SUITABLE_MIN = 0.55
export const TIER_NEEDS_REVIEW_MIN = 0.30

export function resolveCandidateTier(input: {
    semanticKind: BimSpaceSemanticKind
    rejectedByDefault: boolean
    eligible: boolean
    clinicalSuitabilityScore: number
    geometricFitScore: number
    score: number
    /** True when the exact mesh has not been extracted (confidence caveat). */
    needsExactGeometry: boolean
    /**
     * Build 1B recommendation-semantic guard (§A): TRUE only when the room's
     * LABEL carries AFFIRMATIVE, function-specific semantic evidence for THIS
     * clinical function (e.g. an "Uptake"/"Recovery" label for UPTAKE_ROOM, a
     * "PET"/"CT"/"Scanner" label for PET_CT_SCANNER_ROOM). This is the doctrine
     * enforcement: "GEOMETRIC FIT CANNOT BY ITSELF ESTABLISH THAT THE ROOM IS
     * CLINICALLY APPROPRIATE." A dedicated clinical room for a DIFFERENT function
     * (TECH.OFFICE, PROSTH.LAB, CERAMIC LAB) has NO function-specific evidence and
     * therefore CANNOT be promoted to RECOMMENDED by geometry alone — it is capped
     * at SUITABLE regardless of a high blended score. Defaults to false (fail
     * closed): absence of positive evidence never earns RECOMMENDED.
     */
    hasFunctionSemanticEvidence?: boolean
}): CandidateTier {
    // Hard rejects: default-rejected host kind or degenerate/ineligible geometry.
    if (input.rejectedByDefault || !input.eligible) return 'REJECTED'

    // An UNKNOWN or GENERIC_OCCUPIABLE space is NEVER auto-RECOMMENDED (§6): its
    // best tier is SUITABLE, and it drops to NEEDS_REVIEW when weak/uncertain.
    const capNonClinical = input.semanticKind === 'UNKNOWN' || input.semanticKind === 'GENERIC_OCCUPIABLE'

    // Build 1B §A recommendation-semantic guard: RECOMMENDED requires AFFIRMATIVE
    // function-specific semantic evidence. Without it, a room may still be a real
    // enclosed clinical room with excellent geometry, but geometry alone cannot
    // establish clinical appropriateness FOR THIS FUNCTION — so it is capped at
    // SUITABLE. ELIGIBLE_EQUALS_RECOMMENDED = NO.
    const canRecommend = !capNonClinical && input.hasFunctionSemanticEvidence === true

    if (canRecommend && input.score >= TIER_RECOMMENDED_MIN) return 'RECOMMENDED'
    if (input.score >= TIER_SUITABLE_MIN) return capNonClinical && input.needsExactGeometry ? 'NEEDS_REVIEW' : 'SUITABLE'
    if (input.score >= TIER_NEEDS_REVIEW_MIN) return 'NEEDS_REVIEW'
    return 'NEEDS_REVIEW' // eligible + non-rejected but low score: still reviewable, not auto-rejected
}

/**
 * Score how semantically appropriate a room is as a clinical host (0..1).
 * ENCLOSED_ROOM = high; UNKNOWN = neutral (never zero — not auto-rejected);
 * rejected kinds = near-zero. This is the CLINICAL SUITABILITY axis.
 */
/**
 * Per-function label affinity: the strongest clinical-word tokens for each target
 * function. A dedicated-room label matching its OWN function earns full semantic
 * confidence; a dedicated-room label for a DIFFERENT function is still a real
 * clinical room but a weaker match for this function (calibration — not a gate).
 */
const FUNCTION_AFFINITY_TOKENS: Partial<Record<ClinicalFunction, readonly string[]>> = {
    UPTAKE_ROOM: ['uptake', 'recovery', 'prep', 'preparation'],
    INJECTION_ROOM: ['injection', 'dispensing', 'dose', 'prep', 'preparation'],
    PET_CT_SCANNER_ROOM: ['pet', 'ct', 'scanner', 'imaging', 'mri', 'spect'],
    RADIOPHARMACY: ['radiopharmacy', 'pharmacy', 'hot cell', 'cyclotron', 'dispensing', 'lab', 'laboratory', 'clean'],
}

/**
 * The affinity tokens for a clinical function (empty when none are defined). Pure.
 * Exposed so the report/tests can enumerate exactly which words count as
 * affirmative function-specific evidence.
 */
export function getFunctionAffinityTokens(fn: ClinicalFunction): readonly string[] {
    return FUNCTION_AFFINITY_TOKENS[fn] ?? []
}

/**
 * Build 1B §A recommendation-semantic guard — PURE, exported, testable.
 *
 * Returns TRUE only when `label` carries AFFIRMATIVE, function-specific semantic
 * evidence that it is an appropriate host for `fn` (its label matches one of the
 * function's affinity tokens). This is the single source of truth for "does the
 * room NAME actually say it is for THIS clinical function?".
 *
 * Doctrine: GEOMETRIC FIT CANNOT BY ITSELF ESTABLISH CLINICAL APPROPRIATENESS.
 * A "TECH.OFFICE", "PROSTH.LAB" or "CERAMIC LAB" is a real enclosed room but has
 * NO affinity for UPTAKE_ROOM/INJECTION_ROOM/PET_CT_SCANNER_ROOM, so it returns
 * false and can never be promoted to RECOMMENDED by geometry alone.
 *
 * When a function has no defined affinity vocabulary, there is no way to prove
 * function-specific appropriateness from the label, so this returns false (fail
 * closed) — such functions never auto-RECOMMEND on geometry.
 */
export function roomMatchesFunctionAffinity(label: string, fn: ClinicalFunction): boolean {
    const affinity = FUNCTION_AFFINITY_TOKENS[fn] ?? []
    if (affinity.length === 0) return false
    const normalized = normalizeLabel(label)
    if (!normalized) return false
    return affinity.some((t) => (t.includes(' ') ? normalized.includes(t) : tokenMatches(normalized, t)))
}

/**
 * Score how semantically appropriate a room is as a clinical host for a SPECIFIC
 * function (0..1). Build 1B calibration:
 *   - ENCLOSED_ROOM whose label matches the TARGET function's affinity => 1.0.
 *   - ENCLOSED_ROOM (a dedicated clinical room) for a DIFFERENT function => 0.7.
 *   - GENERIC_OCCUPIABLE (waiting/activity/generic room) => 0.5 (relevant, not proof).
 *   - UNKNOWN => 0.45 (neutral; never zero, never auto-recommended).
 *   - rejected kinds => near-zero.
 * This is the CLINICAL SUITABILITY axis (independent of geometric fit).
 */
function scoreClinicalSuitability(semantic: BimSpaceSemanticClassification, clinicalFunction: ClinicalFunction): number {
    switch (semantic.kind) {
        case 'ENCLOSED_ROOM': {
            const matchesTargetFunction = roomMatchesFunctionAffinity(semantic.originalBimLabel, clinicalFunction)
            return matchesTargetFunction ? 1.0 : 0.7
        }
        case 'GENERIC_OCCUPIABLE': return 0.5
        case 'UNKNOWN': return 0.45
        case 'SERVICE_SUPPORT': return 0.15
        case 'SANITARY':
        case 'OPEN_OR_EXTERIOR':
        case 'CIRCULATION':
        case 'VERTICAL_TRANSPORT':
        case 'SHAFT':
            return 0.05
    }
}

/**
 * Score how well a room's geometry fits a function's soft area preference (0..1).
 * This is the GEOMETRIC axis — deliberately separate from clinical suitability.
 * A room with no metrics yet scores a neutral 0.5 (pending lazy extraction).
 */
function scoreGeometricFit(eligibility: RoomEligibility, profile: ClinicalFunctionSpatialProfile): number {
    const area = eligibility.metrics.floorAreaM2
    if (area === undefined) return 0.5 // unknown geometry -> neutral, needs extraction
    if (!eligibility.eligible) return 0.0 // degenerate geometry cannot host
    const { min, ideal } = profile.preferredAreaM2
    if (area >= ideal) return 1.0
    if (area >= min) return clamp01(0.6 + 0.4 * ((area - min) / Math.max(ideal - min, 1e-6)))
    // Below the preferred minimum but still geometrically usable: partial credit.
    return clamp01(0.3 * (area / Math.max(min, 1e-6)))
}

/**
 * Build a single ranked candidate for a room + function. Deterministic; pure.
 * Blends the two independent axes: clinical suitability weighted 0.6, geometric
 * fit 0.4 (semantics matter more than raw size for HOST appropriateness). A
 * default-rejected or geometrically-ineligible room is NOT recommended, but is
 * still RETURNED with reasons (the user may override for unknown/service space).
 */
export function scoreRoomCandidate(input: {
    room: Pick<DiscoveredRoomVolume, 'bimSpaceId' | 'originalBimLabel' | 'mrtDisplayName' | 'storeyId' | 'sourceClass' | 'worldRange' | 'geometryQuality'>
    clinicalFunction: ClinicalFunction
    footprint?: { outerLoop: readonly { x: number; y: number }[]; floorZ?: number; zLow?: number; zHigh?: number }
    currentParentBimSpaceId?: string
}): RankedRoomCandidate {
    const semantic = classifyBimSpaceSemantics({ originalBimLabel: input.room.originalBimLabel, sourceClass: input.room.sourceClass })
    const eligibility = evaluateRoomEligibility({ room: input.room, footprint: input.footprint })
    const profile = resolveFunctionSpatialProfile(input.clinicalFunction)

    const clinicalSuitabilityScore = clamp01(scoreClinicalSuitability(semantic, input.clinicalFunction))
    const geometricFitScore = clamp01(scoreGeometricFit(eligibility, profile))
    const score = clamp01(0.6 * clinicalSuitabilityScore + 0.4 * geometricFitScore)

    const needsExactGeometry = eligibility.code === 'GEOMETRY_UNKNOWN' || eligibility.geometryQuality !== 'EXACT_SPACE_GEOMETRY'

    // Build 1B §A recommendation-semantic guard: does the room LABEL carry
    // affirmative, function-specific semantic evidence for THIS function? A real
    // enclosed room for a DIFFERENT function (office/lab/etc.) has none, so it
    // cannot be promoted to RECOMMENDED by geometry alone.
    const hasFunctionSemanticEvidence = roomMatchesFunctionAffinity(input.room.originalBimLabel, input.clinicalFunction)

    // Build 1B calibration: eligible ≠ recommended. The tier is derived from the
    // two independent axes via explicit, testable score bands (see resolveCandidateTier).
    const tier = resolveCandidateTier({
        semanticKind: semantic.kind,
        rejectedByDefault: semantic.rejectedByDefault,
        eligible: eligibility.eligible,
        clinicalSuitabilityScore,
        geometricFitScore,
        score,
        needsExactGeometry,
        hasFunctionSemanticEvidence,
    })
    const recommended = tier === 'RECOMMENDED'
    // Whether a HIGH-scoring room was demoted from RECOMMENDED purely because it
    // lacked function-specific semantic evidence (geometry-only good match).
    const cappedForNoSemanticEvidence =
        tier !== 'RECOMMENDED' &&
        !semantic.rejectedByDefault &&
        eligibility.eligible &&
        semantic.kind === 'ENCLOSED_ROOM' &&
        !hasFunctionSemanticEvidence &&
        score >= TIER_RECOMMENDED_MIN

    const reasons: string[] = []
    reasons.push(semantic.reason)
    reasons.push(eligibility.reason)
    if (eligibility.metrics.floorAreaM2 !== undefined) {
        reasons.push(`Floor area ≈ ${eligibility.metrics.floorAreaM2.toFixed(1)} m² vs preferred ≥ ${profile.preferredAreaM2.min} m² (${profile.descriptor}).`)
    }
    // Tier-specific, honest caveats (eligible ≠ recommended).
    switch (tier) {
        case 'RECOMMENDED':
            reasons.push('RECOMMENDED — dedicated clinical-room semantics for this function plus usable geometry.')
            break
        case 'SUITABLE':
            if (cappedForNoSemanticEvidence) {
                reasons.push(
                    `SUITABLE (capped) — good geometric fit, but the label carries no affirmative ${input.clinicalFunction} semantic evidence, so geometry alone cannot recommend it. Recommendation capped at SUITABLE.`,
                )
            } else {
                reasons.push('SUITABLE — a plausible host, but not the strongest match for this function; confirm before use.')
            }
            break
        case 'NEEDS_REVIEW':
            if (semantic.kind === 'GENERIC_OCCUPIABLE') {
                reasons.push('NEEDS REVIEW — an enclosed occupiable space (e.g. waiting/activity area) is contextually relevant but is NOT proof of dedicated clinical-room suitability.')
            } else if (semantic.kind === 'UNKNOWN') {
                reasons.push('NEEDS REVIEW — the label matched no known clinical vocabulary; not rejected, but not auto-recommended. Verify manually.')
            } else {
                reasons.push('NEEDS REVIEW — eligible but with real uncertainty or a weak fit for this function.')
            }
            break
        case 'REJECTED':
            reasons.push('REJECTED as a default clinical host — override only if this space is genuinely an enclosed clinical room.')
            break
    }
    if (needsExactGeometry) {
        reasons.push('Confidence would improve after extracting the exact room mesh (currently a range/unknown approximation).')
    }
    reasons.push('Note: geometric containment (does a box fit?) is evaluated separately from clinical suitability.')

    return {
        bimSpaceId: input.room.bimSpaceId,
        originalBimLabel: input.room.originalBimLabel,
        mrtDisplayName: input.room.mrtDisplayName,
        storeyId: input.room.storeyId,
        clinicalFunction: input.clinicalFunction,
        semantic,
        eligibility,
        clinicalSuitabilityScore,
        geometricFitScore,
        score,
        tier,
        recommended,
        needsExactGeometry,
        hasFunctionSemanticEvidence,
        cappedForNoSemanticEvidence,
        reasons,
        isCurrentParent: !!input.currentParentBimSpaceId && input.room.bimSpaceId === input.currentParentBimSpaceId,
    }
}

/** Optional per-room exact footprint facts, keyed by bimSpaceId (from overlay). */
export type CandidateFootprintFacts = Readonly<Record<string, { outerLoop: readonly { x: number; y: number }[]; floorZ?: number; zLow?: number; zHigh?: number }>>

export interface RankClinicalRoomCandidatesInput {
    clinicalFunction: ClinicalFunction
    rooms: readonly Pick<DiscoveredRoomVolume, 'bimSpaceId' | 'originalBimLabel' | 'mrtDisplayName' | 'storeyId' | 'sourceClass' | 'worldRange' | 'geometryQuality'>[]
    /** Optional exact footprints for rooms already extracted (lazy). */
    footprints?: CandidateFootprintFacts
    /** The current parent bim space id for this function (marked, ranked normally). */
    currentParentBimSpaceId?: string
    /**
     * When true, ONLY recommended (non-rejected, eligible) candidates are
     * returned. Default false: rejected/ineligible rooms are still returned
     * (ranked last) so the UI can offer an explicit override.
     */
    recommendedOnly?: boolean
    /** Optional storey filter (only rooms on this storey). */
    storeyId?: string
    /** Max candidates to return (shortlist). Default 25. */
    limit?: number
}

/**
 * Rank clinical-room candidates for a chosen function. Deterministic and stable:
 * sorts by (recommended desc, score desc, area desc, bimSpaceId asc) so identical
 * inputs always yield the identical ordered shortlist. Pure.
 *
 * This is the SHORTLIST stage. It does NOT trigger exact-mesh extraction; it only
 * FLAGS which top candidates would benefit from it (`needsExactGeometry`) so the
 * overlay can lazily extract just those before final selection.
 */
export function rankClinicalRoomCandidates(input: RankClinicalRoomCandidatesInput): RankedRoomCandidate[] {
    const fp = input.footprints ?? {}
    const scored: RankedRoomCandidate[] = []
    for (const room of input.rooms) {
        if (input.storeyId && room.storeyId && room.storeyId !== input.storeyId) continue
        const candidate = scoreRoomCandidate({
            room,
            clinicalFunction: input.clinicalFunction,
            footprint: fp[room.bimSpaceId],
            currentParentBimSpaceId: input.currentParentBimSpaceId,
        })
        if (input.recommendedOnly && !candidate.recommended) continue
        scored.push(candidate)
    }
    scored.sort((a, b) => {
        if (a.recommended !== b.recommended) return a.recommended ? -1 : 1
        if (b.score !== a.score) return b.score - a.score
        const aa = a.eligibility.metrics.floorAreaM2 ?? -1
        const ba = b.eligibility.metrics.floorAreaM2 ?? -1
        if (ba !== aa) return ba - aa
        return a.bimSpaceId.localeCompare(b.bimSpaceId)
    })
    const limit = input.limit ?? 25
    return scored.slice(0, Math.max(1, limit))
}

/** Bounded ranking summary (diagnostic + UI header). Pure. */
export interface CandidateRankingSummary {
    clinicalFunction: ClinicalFunction
    totalConsidered: number
    recommendedCount: number
    /** Per-tier counts (Build 1B calibration — makes RECOMMENDED a real minority). */
    tierCounts: Record<CandidateTier, number>
    rejectedByDefaultCount: number
    ineligibleCount: number
    needsExactGeometryCount: number
    topCandidateBimSpaceId?: string
    topCandidateScore?: number
    topCandidateTier?: CandidateTier
}

export function summarizeCandidateRanking(input: {
    clinicalFunction: ClinicalFunction
    candidates: readonly RankedRoomCandidate[]
}): CandidateRankingSummary {
    const tierCounts: Record<CandidateTier, number> = {
        RECOMMENDED: 0, SUITABLE: 0, NEEDS_REVIEW: 0, REJECTED: 0,
    }
    let rejected = 0, ineligible = 0, needsExact = 0
    for (const c of input.candidates) {
        tierCounts[c.tier] += 1
        if (c.semantic.rejectedByDefault) rejected += 1
        if (!c.eligibility.eligible) ineligible += 1
        if (c.needsExactGeometry) needsExact += 1
    }
    const top = input.candidates[0]
    return {
        clinicalFunction: input.clinicalFunction,
        totalConsidered: input.candidates.length,
        recommendedCount: tierCounts.RECOMMENDED,
        tierCounts,
        rejectedByDefaultCount: rejected,
        ineligibleCount: ineligible,
        needsExactGeometryCount: needsExact,
        topCandidateBimSpaceId: top?.bimSpaceId,
        topCandidateScore: top?.score,
        topCandidateTier: top?.tier,
    }
}

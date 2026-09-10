/**
 * clinicalProgram — pure, Bentley-free MRT Pharma CLINICAL PROGRAM OVERLAY.
 *
 * A NON-DESTRUCTIVE planning layer over the existing Bentley BIM: it assigns an
 * MRT Pharma clinical FUNCTION + display name to an existing BuildingSpatial:Space
 * WITHOUT changing the Bentley identity or the original BIM label. Assignments
 * are application-owned, scoped by iModel, persisted safely (no secrets), and
 * scenario-ready. Assignment implies PLANNING only — never regulatory / equipment
 * fit / shielding / HVAC compliance.
 */

// ---------------------------------------------------------------------------
// Controlled clinical-function taxonomy
// ---------------------------------------------------------------------------

export const CLINICAL_FUNCTIONS = [
    'UNASSIGNED_EXISTING',
    'RADIOPHARMACY',
    'CYCLOTRON',
    'HOT_CELL_SYNTHESIS',
    'QUALITY_CONTROL',
    'DOSE_DISPENSING',
    'INJECTION_ROOM',
    'UPTAKE_ROOM',
    'PET_CT_SCANNER_ROOM',
    'SPECT_CT_SCANNER_ROOM',
    'CONTROL_ROOM',
    'PATIENT_WAITING',
    'PATIENT_PREPARATION',
    'RECOVERY',
    'CLEAN_SUPPLY',
    'WASTE_DECAY_STORAGE',
    'STAFF_SUPPORT',
    'MECHANICAL_ELECTRICAL',
    'CLINICAL_CORRIDOR',
    'GENERAL_SUPPORT',
] as const

export type ClinicalFunction = typeof CLINICAL_FUNCTIONS[number]
export const DEFAULT_PROGRAM_FUNCTION: ClinicalFunction = 'UNASSIGNED_EXISTING'

/** Assignment status — planning only until later analysis establishes more. */
export type ProgramAssignmentStatus = 'PLANNING_ASSIGNMENT'
export type ProgramAssignmentProvenance = 'USER_DEFINED_PLANNING_OVERLAY'

export interface ClinicalProgramAssignment {
    assignmentId: string
    bimSpaceId: string
    bimStoreyId?: string
    originalBimLabel: string
    clinicalFunction: ClinicalFunction
    mrtDisplayName: string
    status: ProgramAssignmentStatus
    provenance: ProgramAssignmentProvenance
}

// ---------------------------------------------------------------------------
// Default display-name generation (deterministic)
// ---------------------------------------------------------------------------

/** Base label + zero-padded index style per function. */
const NAME_BASE: Partial<Record<ClinicalFunction, string>> = {
    RADIOPHARMACY: 'Radiopharmacy',
    CYCLOTRON: 'Cyclotron',
    HOT_CELL_SYNTHESIS: 'Hot Cell',
    QUALITY_CONTROL: 'QC Lab',
    DOSE_DISPENSING: 'Dose Dispensing',
    INJECTION_ROOM: 'Injection Room',
    UPTAKE_ROOM: 'Uptake',
    PET_CT_SCANNER_ROOM: 'PET/CT',
    SPECT_CT_SCANNER_ROOM: 'SPECT/CT',
    CONTROL_ROOM: 'Control',
    PATIENT_WAITING: 'Waiting',
    PATIENT_PREPARATION: 'Prep',
    RECOVERY: 'Recovery',
    CLEAN_SUPPLY: 'Clean Supply',
    WASTE_DECAY_STORAGE: 'Decay Store',
    STAFF_SUPPORT: 'Staff',
    MECHANICAL_ELECTRICAL: 'MEP',
    CLINICAL_CORRIDOR: 'Corridor',
    GENERAL_SUPPORT: 'Support',
}

/** Functions that are typically singular (no numeric suffix on the first one). */
const SINGULAR_FUNCTIONS = new Set<ClinicalFunction>(['RADIOPHARMACY'])

function pad2(n: number): string { return n < 10 ? `0${n}` : String(n) }

/**
 * Deterministic default MRT display name for a new assignment of `fn`, given the
 * existing assignments. First UPTAKE_ROOM => "Uptake 01", second => "Uptake 02";
 * first PET_CT_SCANNER_ROOM => "PET/CT 01"; RADIOPHARMACY => "Radiopharmacy".
 */
export function resolveDefaultClinicalProgramName(input: { clinicalFunction: ClinicalFunction; existingAssignments: readonly ClinicalProgramAssignment[] }): string {
    const fn = input.clinicalFunction
    if (fn === 'UNASSIGNED_EXISTING') return ''
    const base = NAME_BASE[fn] ?? fn.replace(/_/g, ' ')
    const sameFn = input.existingAssignments.filter((a) => a.clinicalFunction === fn)
    if (SINGULAR_FUNCTIONS.has(fn) && sameFn.length === 0) return base
    return `${base} ${pad2(sameFn.length + 1)}`
}

/** Ensure a display name is unique within the assignment set (append a suffix). */
export function ensureUniqueDisplayName(name: string, existing: readonly ClinicalProgramAssignment[], excludeSpaceId?: string): string {
    const taken = new Set(existing.filter((a) => a.bimSpaceId !== excludeSpaceId).map((a) => a.mrtDisplayName))
    if (!taken.has(name)) return name
    let i = 2
    while (taken.has(`${name} (${i})`)) i += 1
    return `${name} (${i})`
}

// ---------------------------------------------------------------------------
// Assignment (pure) — one primary function per BIM space
// ---------------------------------------------------------------------------

export interface BimSpaceRef { bimSpaceId: string; originalBimLabel: string; bimStoreyId?: string }

export type AssignResult =
    | { ok: true; assignments: ClinicalProgramAssignment[]; assignment: ClinicalProgramAssignment }
    | { ok: false; reason: string }

let assignmentSeq = 0
function nextAssignmentId(bimSpaceId: string): string { assignmentSeq += 1; return `cpa_${bimSpaceId}_${assignmentSeq}` }

/**
 * Assign (or update) the single primary clinical function for a BIM space. Any
 * existing primary assignment for that space is REPLACED (max one per space).
 * Assigning UNASSIGNED_EXISTING removes the override (reset). BIM identity and
 * original label are always preserved. Display name defaults deterministically
 * and is made unique.
 */
export function assignClinicalFunction(input: {
    bimSpace: BimSpaceRef
    clinicalFunction: ClinicalFunction
    requestedDisplayName?: string
    existingAssignments: readonly ClinicalProgramAssignment[]
}): AssignResult {
    const { bimSpace, clinicalFunction } = input
    if (!bimSpace.bimSpaceId) return { ok: false, reason: 'NO_BIM_SPACE_ID' }
    if (!CLINICAL_FUNCTIONS.includes(clinicalFunction)) return { ok: false, reason: 'UNKNOWN_FUNCTION' }

    const others = input.existingAssignments.filter((a) => a.bimSpaceId !== bimSpace.bimSpaceId)

    // Reset case: UNASSIGNED_EXISTING removes any override for this space.
    if (clinicalFunction === 'UNASSIGNED_EXISTING') {
        return {
            ok: true, assignments: others.slice(), assignment: {
                assignmentId: nextAssignmentId(bimSpace.bimSpaceId), bimSpaceId: bimSpace.bimSpaceId,
                bimStoreyId: bimSpace.bimStoreyId, originalBimLabel: bimSpace.originalBimLabel,
                clinicalFunction: 'UNASSIGNED_EXISTING', mrtDisplayName: '', status: 'PLANNING_ASSIGNMENT', provenance: 'USER_DEFINED_PLANNING_OVERLAY',
            }
        }
    }

    const wanted = input.requestedDisplayName?.trim() || resolveDefaultClinicalProgramName({ clinicalFunction, existingAssignments: others })
    const unique = ensureUniqueDisplayName(wanted, others, bimSpace.bimSpaceId)

    const assignment: ClinicalProgramAssignment = {
        assignmentId: nextAssignmentId(bimSpace.bimSpaceId),
        bimSpaceId: bimSpace.bimSpaceId,
        bimStoreyId: bimSpace.bimStoreyId,
        originalBimLabel: bimSpace.originalBimLabel, // NEVER altered
        clinicalFunction,
        mrtDisplayName: unique,
        status: 'PLANNING_ASSIGNMENT',
        provenance: 'USER_DEFINED_PLANNING_OVERLAY',
    }
    return { ok: true, assignments: [...others, assignment], assignment }
}

/** Remove a space's program override (return to UNASSIGNED_EXISTING). */
export function resetAssignment(bimSpaceId: string, existing: readonly ClinicalProgramAssignment[]): ClinicalProgramAssignment[] {
    return existing.filter((a) => a.bimSpaceId !== bimSpaceId || a.clinicalFunction === 'UNASSIGNED_EXISTING')
        .filter((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')
}

/** The active assignment for a space (or undefined => UNASSIGNED_EXISTING). */
export function assignmentForSpace(bimSpaceId: string, existing: readonly ClinicalProgramAssignment[]): ClinicalProgramAssignment | undefined {
    return existing.find((a) => a.bimSpaceId === bimSpaceId && a.clinicalFunction !== 'UNASSIGNED_EXISTING')
}

// ---------------------------------------------------------------------------
// Label precedence + overlay visibility
// ---------------------------------------------------------------------------

export type ProgramLabelMode = 'PROGRAM_OVERLAY' | 'BIM'

/**
 * Assigned room => MRT display name is primary; unassigned => original BIM label.
 * Never fabricates a clinical identity for an unassigned room.
 */
export function resolveProgramRoomLabel(input: { originalBimLabel: string; assignment?: ClinicalProgramAssignment }): string {
    const a = input.assignment
    if (a && a.clinicalFunction !== 'UNASSIGNED_EXISTING' && a.mrtDisplayName) return a.mrtDisplayName
    return input.originalBimLabel
}

/**
 * Deterministic overlay-visibility policy for a room label/footprint. Storey
 * filter first; assigned rooms get priority; a bounded density limit keeps the
 * screen from becoming a 269-label wall (assigned rooms win the budget).
 */
export function resolveProgramRoomVisible(input: {
    activeStoreyId?: string
    roomStoreyId?: string
    assigned: boolean
    selected: boolean
    rankAmongVisibleCandidates: number // 0-based order after prioritization
    maxLabels?: number
}): boolean {
    // Storey filter: if a storey is active and the room is on another storey, hide.
    if (input.activeStoreyId && input.roomStoreyId && input.activeStoreyId !== input.roomStoreyId) return false
    const max = input.maxLabels ?? 24
    if (input.selected || input.assigned) return input.rankAmongVisibleCandidates < Math.max(max, 1)
    return input.rankAmongVisibleCandidates < max
}

/** Order candidates so selected + assigned rooms rank first (label priority). */
export function prioritizeProgramLabels<T extends { assigned: boolean; selected: boolean }>(rooms: readonly T[]): T[] {
    return [...rooms].sort((a, b) => {
        const sa = (a.selected ? 2 : 0) + (a.assigned ? 1 : 0)
        const sb = (b.selected ? 2 : 0) + (b.assigned ? 1 : 0)
        return sb - sa
    })
}

// ---------------------------------------------------------------------------
// Program summary + completeness (informational)
// ---------------------------------------------------------------------------

export interface ProgramSummary {
    assignedCount: number
    countByFunction: Partial<Record<ClinicalFunction, number>>
}

export function summarizeProgram(assignments: readonly ClinicalProgramAssignment[]): ProgramSummary {
    const active = assignments.filter((a) => a.clinicalFunction !== 'UNASSIGNED_EXISTING')
    const countByFunction: Partial<Record<ClinicalFunction, number>> = {}
    for (const a of active) countByFunction[a.clinicalFunction] = (countByFunction[a.clinicalFunction] ?? 0) + 1
    return { assignedCount: active.length, countByFunction }
}

/** Basic PET demo needs these functions; informational only (never auto-adds). */
export const BASIC_PET_DEMO_REQUIRED: ClinicalFunction[] = ['RADIOPHARMACY', 'INJECTION_ROOM', 'UPTAKE_ROOM', 'PET_CT_SCANNER_ROOM']

export function checkProgramCompleteness(assignments: readonly ClinicalProgramAssignment[], required: readonly ClinicalFunction[] = BASIC_PET_DEMO_REQUIRED): { complete: boolean; missing: ClinicalFunction[] } {
    const present = new Set(assignments.map((a) => a.clinicalFunction))
    const missing = required.filter((f) => !present.has(f))
    return { complete: missing.length === 0, missing }
}

// ---------------------------------------------------------------------------
// Persistence (localStorage; safe, iModel-scoped)
// ---------------------------------------------------------------------------

const STORAGE_PREFIX = 'mrtpharma.clinicalProgram.v1.'
const FORBIDDEN_KEYS = ['token', 'accessToken', 'access_token', 'refreshToken', 'refresh_token', 'authorization', 'Authorization', 'clientSecret', 'client_secret', 'pkce', 'pkceVerifier', 'verifier']

/** True if the persisted payload contains ONLY safe planning fields. */
export function isSafeProgramPayload(v: unknown): v is ClinicalProgramAssignment[] {
    if (!Array.isArray(v)) return false
    const allowed = new Set(['assignmentId', 'bimSpaceId', 'bimStoreyId', 'originalBimLabel', 'clinicalFunction', 'mrtDisplayName', 'status', 'provenance'])
    return v.every((a) => {
        if (!a || typeof a !== 'object') return false
        const keys = Object.keys(a as Record<string, unknown>)
        if (keys.some((k) => FORBIDDEN_KEYS.includes(k))) return false
        if (!keys.every((k) => allowed.has(k))) return false
        const o = a as Record<string, unknown>
        return typeof o.bimSpaceId === 'string' && typeof o.clinicalFunction === 'string'
    })
}

/** Strip to the safe serializable subset (defensive). */
export function toSafeProgramPayload(assignments: readonly ClinicalProgramAssignment[]): ClinicalProgramAssignment[] {
    return assignments.map((a) => ({
        assignmentId: a.assignmentId, bimSpaceId: a.bimSpaceId, bimStoreyId: a.bimStoreyId,
        originalBimLabel: a.originalBimLabel, clinicalFunction: a.clinicalFunction,
        mrtDisplayName: a.mrtDisplayName, status: a.status, provenance: a.provenance,
    }))
}

export function loadProgramAssignments(iModelId: string, storage?: Pick<Storage, 'getItem'>): ClinicalProgramAssignment[] {
    const s = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined)
    if (!s || !iModelId) return []
    try {
        const raw = s.getItem(STORAGE_PREFIX + iModelId)
        if (!raw) return []
        const parsed = JSON.parse(raw) as unknown
        return isSafeProgramPayload(parsed) ? parsed : []
    } catch { return [] }
}

export function saveProgramAssignments(iModelId: string, assignments: readonly ClinicalProgramAssignment[], storage?: Pick<Storage, 'setItem'>): void {
    const s = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined)
    if (!s || !iModelId) return
    try { s.setItem(STORAGE_PREFIX + iModelId, JSON.stringify(toSafeProgramPayload(assignments))) } catch { /* storage unavailable */ }
}

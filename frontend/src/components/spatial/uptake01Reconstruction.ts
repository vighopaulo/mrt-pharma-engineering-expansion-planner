/**
 * uptake01Reconstruction — pure, Bentley-free, one-time AUTHORIZED reconstruction
 * of the previously accepted Uptake 01 baseline (assignment + planning volume).
 *
 * Only used because the live persistence diagnostic proved
 * PERSISTED_STATE_GENUINELY_ABSENT (no source records to migrate). It is
 * duplicate-guarded and idempotent: reconstructing again over an existing
 * Uptake 01 is a no-op that preserves the already-created stable ids. It never
 * auto-runs on startup — the caller invokes it once, explicitly.
 */
import {
    assignClinicalFunction,
    type ClinicalProgramAssignment,
} from './clinicalProgram'
import {
    makeClinicalVolumeId,
    type ClinicalPlanningVolume,
    type PrismParams,
} from './clinicalPlanningVolume'

/** The previously manually accepted Uptake 01 baseline evidence. */
export const UPTAKE_01_BASELINE = {
    bimSpaceId: '0x200000001f1',
    originalBimLabel: '1AC1 CENTRAL WAITING',
    clinicalFunction: 'UPTAKE_ROOM' as const,
    mrtDisplayName: 'Uptake 01',
    params: { centerX: -9.84, centerY: 30.53, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0 } as PrismParams,
}

export interface ReconstructionInput {
    iModelId: string
    /** Storey id for the assignment (best-effort; optional). */
    storeyId?: string
    existingAssignments: readonly ClinicalProgramAssignment[]
    existingVolumes: readonly ClinicalPlanningVolume[]
}

export interface ReconstructionResult {
    assignments: ClinicalProgramAssignment[]
    volumes: ClinicalPlanningVolume[]
    assignment: ClinicalProgramAssignment
    volume: ClinicalPlanningVolume
    /** True when nothing was created (Uptake 01 already present) — idempotent. */
    alreadyPresent: boolean
    reason?: string
}

/**
 * Reconstruct the Uptake 01 baseline. DUPLICATE-GUARDED: if an assignment + a
 * planning volume already exist for the target parent, returns them unchanged
 * (alreadyPresent = true). Otherwise creates exactly one assignment (via the
 * accepted pure assignment path) and one DRAFT, visible planning volume with the
 * accepted baseline geometry.
 */
export function reconstructUptake01Baseline(input: ReconstructionInput): ReconstructionResult {
    const b = UPTAKE_01_BASELINE
    const existingAssignment = input.existingAssignments.find((a) => a.bimSpaceId === b.bimSpaceId && a.clinicalFunction !== 'UNASSIGNED_EXISTING')
    const existingVolume = input.existingVolumes.find((v) => v.parentBimSpaceId === b.bimSpaceId)

    if (existingAssignment && existingVolume) {
        return {
            assignments: [...input.existingAssignments],
            volumes: [...input.existingVolumes],
            assignment: existingAssignment,
            volume: existingVolume,
            alreadyPresent: true,
            reason: 'ALREADY_PRESENT',
        }
    }

    // Assignment (accepted pure path; deterministic display-name resolution).
    let assignments: ClinicalProgramAssignment[] = [...input.existingAssignments]
    let assignment = existingAssignment
    if (!assignment) {
        const r = assignClinicalFunction({
            bimSpace: { bimSpaceId: b.bimSpaceId, originalBimLabel: b.originalBimLabel, bimStoreyId: input.storeyId },
            clinicalFunction: b.clinicalFunction,
            requestedDisplayName: b.mrtDisplayName,
            existingAssignments: input.existingAssignments,
        })
        if (!r.ok) throw new Error(`Uptake 01 assignment reconstruction failed: ${r.reason}`)
        assignments = r.assignments
        assignment = r.assignment
    }

    // Planning volume (accepted geometry; fresh stable id since original is absent).
    let volume = existingVolume
    let volumes: ClinicalPlanningVolume[] = [...input.existingVolumes]
    if (!volume) {
        const id = makeClinicalVolumeId(input.iModelId, b.bimSpaceId, 'uptake-01')
        volume = {
            id,
            iModelId: input.iModelId,
            parentBimSpaceId: b.bimSpaceId,
            storeyId: input.storeyId,
            clinicalFunction: b.clinicalFunction,
            displayName: b.mrtDisplayName,
            geometryType: 'ORIENTED_RECTANGULAR_PRISM',
            params: { ...b.params },
            lifecycleState: 'DRAFT',
            geometrySource: 'MRT_PLANNING_SUBVOLUME',
            hidden: false,
        }
        volumes = [...input.existingVolumes.filter((v) => v.parentBimSpaceId !== b.bimSpaceId), volume]
    }

    return { assignments, volumes, assignment, volume, alreadyPresent: false }
}

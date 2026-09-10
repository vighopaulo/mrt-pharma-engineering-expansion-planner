/**
 * clinicalVolumeCollection — pure, Bentley-free multi-volume collection
 * operations for the clinical-program composition system.
 *
 * Generalizes the accepted single-Uptake-01 runtime into an independent
 * collection where each ClinicalProgramAssignment owns 0-or-1 planning volume.
 * Every operation returns a NEW array (no hidden mutation) and mutates ONLY the
 * targeted volume — geometry, visibility, and lifecycle are per-volume isolated.
 * No Bentley writes; no camera/screen dependence.
 */
import {
    isValidPrismParams,
    type ClinicalPlanningVolume,
    type PrismParams,
} from './clinicalPlanningVolume'

/** Add or replace the single volume for a parent space (0-or-1 cardinality). */
export function addOrReplacePlanningVolume(vols: readonly ClinicalPlanningVolume[], vol: ClinicalPlanningVolume): ClinicalPlanningVolume[] {
    return [...vols.filter((v) => v.parentBimSpaceId !== vol.parentBimSpaceId), vol]
}

/** Update ONLY the targeted volume's params (rejected if LOCKED or invalid). */
export function updatePlanningVolumeParams(vols: readonly ClinicalPlanningVolume[], parentBimSpaceId: string, params: PrismParams): ClinicalPlanningVolume[] {
    if (!isValidPrismParams(params)) return [...vols]
    return vols.map((v) => (v.parentBimSpaceId === parentBimSpaceId && v.lifecycleState !== 'LOCKED') ? { ...v, params } : v)
}

/** Set per-volume visibility (view-only; never changes geometry/lifecycle). */
export function setPlanningVolumeVisibility(vols: readonly ClinicalPlanningVolume[], parentBimSpaceId: string, visible: boolean): ClinicalPlanningVolume[] {
    return vols.map((v) => v.parentBimSpaceId === parentBimSpaceId ? { ...v, hidden: !visible } : v)
}

/** Set lifecycle for ONLY the targeted volume. */
export function setPlanningVolumeLifecycle(vols: readonly ClinicalPlanningVolume[], parentBimSpaceId: string, state: 'DRAFT' | 'LOCKED'): ClinicalPlanningVolume[] {
    return vols.map((v) => v.parentBimSpaceId === parentBimSpaceId ? { ...v, lifecycleState: state } : v)
}

/**
 * Delete a volume. A LOCKED volume is NOT deletable (unlock first). Returns the
 * new array + whether deletion happened + a reason when rejected.
 */
export function deletePlanningVolume(vols: readonly ClinicalPlanningVolume[], parentBimSpaceId: string): { volumes: ClinicalPlanningVolume[]; deleted: boolean; reason?: string } {
    const v = vols.find((x) => x.parentBimSpaceId === parentBimSpaceId)
    if (!v) return { volumes: [...vols], deleted: false, reason: 'NO_VOLUME' }
    if (v.lifecycleState === 'LOCKED') return { volumes: [...vols], deleted: false, reason: 'LOCKED_MUST_UNLOCK_FIRST' }
    return { volumes: vols.filter((x) => x.parentBimSpaceId !== parentBimSpaceId), deleted: true }
}

/** The volume for a parent space, if any. */
export function findPlanningVolume(vols: readonly ClinicalPlanningVolume[], parentBimSpaceId: string): ClinicalPlanningVolume | undefined {
    return vols.find((v) => v.parentBimSpaceId === parentBimSpaceId)
}

export interface VolumeSummary {
    planningVolumes: number
    draft: number
    locked: number
    visible: number
    hidden: number
}

/** Bounded per-collection counts (lifecycle + visibility). */
export function summarizePlanningVolumes(vols: readonly ClinicalPlanningVolume[]): VolumeSummary {
    let draft = 0, locked = 0, visible = 0, hidden = 0
    for (const v of vols) {
        if (v.lifecycleState === 'LOCKED') locked += 1; else draft += 1
        if (v.hidden) hidden += 1; else visible += 1
    }
    return { planningVolumes: vols.length, draft, locked, visible, hidden }
}

/**
 * clinicalRoomReparent — pure, Bentley-free RE-PARENTING logic for MRT Pharma
 * (Build 1B spatial-foundation correction, Problem A pt2).
 *
 * PROBLEM
 *   A clinical function (e.g. UPTAKE_ROOM "Uptake 01") was parented onto the
 *   WRONG BIM space (a passage/circulation space). Re-parenting moves that
 *   function's assignment onto a DIFFERENT, defensible BIM room the user picked
 *   from the candidate shortlist — and REBUILDS the planning volume from the NEW
 *   parent's own geometry so no stale passage-space coordinates survive.
 *
 * DOCTRINE
 *   - The plan for the NEW parent's volume is REGENERATED from the new parent's
 *     OWN authoritative footprint via seedPrismParamsFromParent. We NEVER
 *     translate the old passage-space prism coordinates onto the new room.
 *   - NO ORPHANS: the OLD parent's planning volume is removed as part of the
 *     re-parent (unless it is LOCKED — a locked volume requires an explicit
 *     unlock first; re-parenting a locked volume is rejected, not silently
 *     discarded).
 *   - NO DUPLICATE ASSIGNMENT: exactly one active assignment per function stays
 *     the invariant; re-parenting REPLACES the parent, it does not add a second.
 *   - Bentley identity/label/range/mesh are never mutated. Pure + deterministic.
 *   - A COMPATIBILITY WARNING is produced (not a hard block) when the chosen new
 *     parent classifies as a default-rejected or geometrically-ineligible host,
 *     so the user can proceed with an explicit override.
 *
 * This module computes the INTENDED re-parent PLAN (what to change) as a pure
 * value. The overlay applies it (mutating module state + persisting) — this file
 * performs no I/O and imports no @itwin.
 */

import type { ClinicalFunction } from './clinicalProgram'
import type { RankedRoomCandidate } from './clinicalRoomCandidate'

// ---------------------------------------------------------------------------
// Compatibility warning (advisory; never a hard block)
// ---------------------------------------------------------------------------

export type ReparentCompatibilityCode =
    | 'COMPATIBLE'
    | 'REJECTED_HOST_KIND' // new parent semantics is a default-rejected host
    | 'GEOMETRY_INELIGIBLE' // new parent geometry is degenerate/unknown
    | 'GEOMETRY_UNVERIFIED' // new parent geometry not yet exact (range approximation)

export interface ReparentCompatibility {
    code: ReparentCompatibilityCode
    /** True when the target is a clean, recommended host (no override needed). */
    compatible: boolean
    /** True when proceeding requires an explicit user override (advisory only). */
    requiresOverride: boolean
    /** Product-facing warning message ('' when compatible). */
    warningMessage: string
}

/**
 * Assess whether re-parenting a function onto a candidate room is a clean,
 * recommended move or requires an explicit override. Advisory only — it NEVER
 * blocks. `GEOMETRY_UNVERIFIED` is a soft note (proceed freely); the two harder
 * cases (rejected host kind, ineligible geometry) set `requiresOverride`.
 */
export function assessReparentCompatibility(candidate: Pick<RankedRoomCandidate,
    'semantic' | 'eligibility' | 'needsExactGeometry' | 'originalBimLabel'>): ReparentCompatibility {
    if (candidate.semantic.rejectedByDefault) {
        return {
            code: 'REJECTED_HOST_KIND', compatible: false, requiresOverride: true,
            warningMessage: `"${candidate.originalBimLabel}" is classified as ${humanKind(candidate.semantic.kind)} — not a recommended clinical host. Re-parent here only if this space is genuinely an enclosed room.`,
        }
    }
    if (!candidate.eligibility.eligible) {
        return {
            code: 'GEOMETRY_INELIGIBLE', compatible: false, requiresOverride: true,
            warningMessage: `"${candidate.originalBimLabel}" geometry is not usable as a host (${candidate.eligibility.code}). Re-parenting may produce a volume that cannot be contained.`,
        }
    }
    if (candidate.needsExactGeometry) {
        return {
            code: 'GEOMETRY_UNVERIFIED', compatible: true, requiresOverride: false,
            warningMessage: `Geometry for "${candidate.originalBimLabel}" is an approximation until the exact room mesh is extracted; containment will be re-verified after re-parenting.`,
        }
    }
    return { code: 'COMPATIBLE', compatible: true, requiresOverride: false, warningMessage: '' }
}

function humanKind(kind: string): string {
    switch (kind) {
        case 'CIRCULATION': return 'circulation/passage space'
        case 'VERTICAL_TRANSPORT': return 'vertical transport'
        case 'SHAFT': return 'a shaft/void'
        case 'SERVICE_SUPPORT': return 'service/plant space'
        case 'SANITARY': return 'sanitary space'
        case 'OPEN_OR_EXTERIOR': return 'open/exterior space'
        default: return kind.toLowerCase()
    }
}

// ---------------------------------------------------------------------------
// Re-parent plan (pure) — what the overlay must apply
// ---------------------------------------------------------------------------

/** Minimal facts about the OLD parent's planning volume (from the overlay). */
export interface OldParentVolumeFact {
    parentBimSpaceId: string
    lifecycleState: 'DRAFT' | 'LOCKED'
}

/** Minimal facts about a target BIM room (the new parent). */
export interface ReparentTargetRoom {
    bimSpaceId: string
    originalBimLabel: string
    storeyId?: string
    /** BIM storey id from the room reference, when present. */
    bimStoreyId?: string
}

export type ReparentBlockCode =
    | 'OLD_VOLUME_LOCKED' // cannot re-parent while old volume is LOCKED
    | 'SAME_PARENT' // target is already the current parent
    | 'NO_TARGET' // no target room resolved
    | 'OVERRIDE_REQUIRED' // compatibility requires an override the caller didn't grant

export type ReparentPlanResult =
    | {
        ok: true
        plan: ReparentPlan
        compatibility: ReparentCompatibility
    }
    | {
        ok: false
        blockCode: ReparentBlockCode
        reason: string
        compatibility: ReparentCompatibility
    }

/**
 * The concrete, pure PLAN the overlay executes to re-parent a function. It never
 * carries geometry — the overlay regenerates the new volume from the new parent's
 * authoritative footprint (the plan only records the INTENT + identities).
 */
export interface ReparentPlan {
    clinicalFunction: ClinicalFunction
    /** The MRT display name to carry over to the new parent (preserved). */
    mrtDisplayName: string
    /** The old parent to unassign + whose volume to remove (undefined if none). */
    oldParentBimSpaceId?: string
    /** Whether the old parent's planning volume must be removed (no orphan). */
    removeOldVolume: boolean
    /** The new parent room to assign the function onto. */
    newParent: ReparentTargetRoom
    /** Whether the user explicitly overrode a compatibility warning. */
    overrideAccepted: boolean
    /** Whether the new volume must be regenerated from the new parent's geometry. */
    regenerateVolumeFromNewParent: true
}

/**
 * Build the pure re-parent plan. Validates the invariants (no locked-old-volume,
 * not a same-parent no-op, target resolved, override honored) and returns either
 * an executable plan or a bounded block reason. Deterministic; no side effects.
 */
export function planReparent(input: {
    clinicalFunction: ClinicalFunction
    mrtDisplayName: string
    /** The current parent for this function (undefined if unparented). */
    oldParent?: OldParentVolumeFact
    /** The chosen new parent room. */
    target?: ReparentTargetRoom
    /** The candidate scoring for the target (drives compatibility). */
    targetCandidate: Pick<RankedRoomCandidate, 'semantic' | 'eligibility' | 'needsExactGeometry' | 'originalBimLabel'>
    /** Whether the user explicitly accepted a compatibility override. */
    overrideAccepted?: boolean
}): ReparentPlanResult {
    const compatibility = assessReparentCompatibility(input.targetCandidate)

    if (!input.target || !input.target.bimSpaceId) {
        return { ok: false, blockCode: 'NO_TARGET', reason: 'No target room resolved for re-parenting.', compatibility }
    }
    if (input.oldParent && input.oldParent.parentBimSpaceId === input.target.bimSpaceId) {
        return { ok: false, blockCode: 'SAME_PARENT', reason: 'The target room is already the current parent.', compatibility }
    }
    if (input.oldParent && input.oldParent.lifecycleState === 'LOCKED') {
        return { ok: false, blockCode: 'OLD_VOLUME_LOCKED', reason: 'Unlock the current planning volume before re-parenting.', compatibility }
    }
    if (compatibility.requiresOverride && !input.overrideAccepted) {
        return { ok: false, blockCode: 'OVERRIDE_REQUIRED', reason: compatibility.warningMessage, compatibility }
    }

    const plan: ReparentPlan = {
        clinicalFunction: input.clinicalFunction,
        mrtDisplayName: input.mrtDisplayName,
        oldParentBimSpaceId: input.oldParent?.parentBimSpaceId,
        removeOldVolume: !!input.oldParent, // DRAFT (locked already blocked above)
        newParent: input.target,
        overrideAccepted: !!input.overrideAccepted,
        regenerateVolumeFromNewParent: true,
    }
    return { ok: true, plan, compatibility }
}

/** Bounded human-readable description of a plan (diagnostic + report). Pure. */
export function describeReparentPlan(plan: ReparentPlan): string {
    const L: string[] = ['=== RE-PARENT PLAN ===']
    L.push(`CLINICAL_FUNCTION = ${plan.clinicalFunction}`)
    L.push(`DISPLAY_NAME = ${plan.mrtDisplayName}`)
    L.push(`OLD_PARENT = ${plan.oldParentBimSpaceId ?? '(none)'}`)
    L.push(`REMOVE_OLD_VOLUME = ${plan.removeOldVolume ? 'YES' : 'NO'}`)
    L.push(`NEW_PARENT = ${plan.newParent.bimSpaceId} (${plan.newParent.originalBimLabel})`)
    L.push(`NEW_PARENT_STOREY = ${plan.newParent.storeyId ?? '(unknown)'}`)
    L.push(`REGENERATE_VOLUME_FROM_NEW_PARENT = YES`)
    L.push(`OVERRIDE_ACCEPTED = ${plan.overrideAccepted ? 'YES' : 'NO'}`)
    L.push(`REUSE_OLD_COORDS = NO`)
    L.push(`BENTLEY_WRITE = NONE`)
    return L.join('\n')
}

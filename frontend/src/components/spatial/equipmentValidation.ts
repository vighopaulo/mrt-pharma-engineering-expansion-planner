/**
 * equipmentValidation — pure, Bentley-free PRODUCT-FACING validation view model
 * for app-owned equipment instances (Build 1B).
 *
 * This is the equipment analogue of `resolvePlanningVolumeValidation`: it maps a
 * containment evaluation into an honest customer-facing state (warning code +
 * message that IDENTIFIES the equipment + room, lock gate + reason, restore
 * availability, secondary technical detail, honest NOT_EVALUATED / approximate-
 * parent labeling). Presentation reads THIS — it never re-derives logic in JSX.
 *
 * It also builds the by-reference CROSSWALK READOUT (capacity / production /
 * cost authority ids + calibration) and a generic DIAGNOSE SELECTED EQUIPMENT
 * text report. No fabricated numbers ever appear here.
 */

import type { ContainmentStatus } from './clinicalPlanningVolume'
import type { EquipmentAssetInstance } from './equipmentInstance'
import { canonicalEquipmentById, type CrosswalkCalibration } from './canonicalEquipmentCatalog'

export type EquipmentAuthorityQuality = 'EXACT_SPACE_GEOMETRY' | 'RANGE_ONLY_APPROXIMATION' | 'NOT_AVAILABLE'

export type EquipmentWarningCode =
    | 'NONE'
    | 'OUTSIDE_PARENT'
    | 'NOT_EVALUATED'
    | 'PARENT_GEOMETRY_UNAVAILABLE'

/** The pure product view model for one equipment instance's validation state. */
export interface EquipmentValidationState {
    equipmentInstanceId: string
    displayLabel: string
    parentBimSpaceId: string
    containmentStatus: ContainmentStatus
    authorityQuality: EquipmentAuthorityQuality
    /** True only when containment PASSes, dims valid, and lifecycle is DRAFT. */
    isLockAllowed: boolean
    warningCode: EquipmentWarningCode
    warningMessage: string
    lockDisabledReason: string
    lastKnownValidAvailable: boolean
    restoreAvailable: boolean
    technicalDetail: string
    /** Whether the parent authority is only an approximation (labeled honestly). */
    approximateParent: boolean
    /** Whether the envelope itself is a GENERIC_ENGINEERING_PLACEHOLDER (honest proxy). */
    envelopeIsPlaceholder: boolean
}

/**
 * Resolve the pure equipment validation view model. Deterministic; no side
 * effects. Mirrors the accepted planning-volume validation semantics.
 */
export function resolveEquipmentValidation(input: {
    instance: EquipmentAssetInstance
    containmentStatus: ContainmentStatus
    authorityQuality: EquipmentAuthorityQuality
    totalSamples: number
    failedSamples: number
    parentMeshAvailable: boolean
}): EquipmentValidationState {
    const name = input.instance.displayLabel || 'This equipment'
    const room = input.instance.parentBimSpaceId
    const approximateParent = input.authorityQuality === 'RANGE_ONLY_APPROXIMATION'
    const envelopeIsPlaceholder = input.instance.placement.envelopeProvenance === 'GENERIC_ENGINEERING_PLACEHOLDER'
    const hasLastKnownValid = !!input.instance.lastKnownValidPlacement
    const locked = input.instance.lifecycleState === 'LOCKED'

    const detailBase = input.containmentStatus === 'PASS'
        ? `Envelope contained (${input.totalSamples - input.failedSamples}/${input.totalSamples} samples inside)`
        : input.containmentStatus === 'FAIL'
            ? `${input.failedSamples}/${input.totalSamples} envelope sample points outside the room`
            : 'Containment not evaluated (no sampled points)'
    const technicalDetail = approximateParent ? `${detailBase} — parent room is a range approximation` : detailBase

    if (input.containmentStatus === 'PASS') {
        return {
            equipmentInstanceId: input.instance.id, displayLabel: name, parentBimSpaceId: room,
            containmentStatus: 'PASS', authorityQuality: input.authorityQuality,
            isLockAllowed: !locked,
            warningCode: 'NONE', warningMessage: '',
            lockDisabledReason: locked ? 'Already locked — unlock to edit.' : '',
            lastKnownValidAvailable: hasLastKnownValid, restoreAvailable: hasLastKnownValid,
            technicalDetail, approximateParent, envelopeIsPlaceholder,
        }
    }

    if (input.containmentStatus === 'FAIL') {
        return {
            equipmentInstanceId: input.instance.id, displayLabel: name, parentBimSpaceId: room,
            containmentStatus: 'FAIL', authorityQuality: input.authorityQuality,
            isLockAllowed: false,
            warningCode: 'OUTSIDE_PARENT',
            warningMessage: `${name} extends outside its parent room. Move, rotate, or resize the equipment until its envelope is fully contained.`,
            lockDisabledReason: `${name} extends outside its parent room — lock is available only when the envelope is fully contained.`,
            lastKnownValidAvailable: hasLastKnownValid,
            restoreAvailable: true,
            technicalDetail, approximateParent, envelopeIsPlaceholder,
        }
    }

    // NOT_EVALUATED — honest; never presented as inside/outside/valid/invalid.
    const parentMissing = !input.parentMeshAvailable
    return {
        equipmentInstanceId: input.instance.id, displayLabel: name, parentBimSpaceId: room,
        containmentStatus: 'NOT_EVALUATED', authorityQuality: input.authorityQuality,
        isLockAllowed: false,
        warningCode: parentMissing ? 'PARENT_GEOMETRY_UNAVAILABLE' : 'NOT_EVALUATED',
        warningMessage: parentMissing
            ? `Parent room geometry for ${name} is not yet available for containment validation.`
            : `Containment for ${name} has not yet been evaluated.`,
        lockDisabledReason: 'Containment must be evaluated and pass before locking.',
        lastKnownValidAvailable: hasLastKnownValid, restoreAvailable: hasLastKnownValid,
        technicalDetail, approximateParent, envelopeIsPlaceholder,
    }
}

export interface EquipmentValidationSummary {
    equipmentCount: number
    valid: number
    needsAttention: number
    notEvaluated: number
    locked: number
    placeholderEnvelopes: number
}

/** Restrained equipment validation program summary (pure). */
export function summarizeEquipmentValidation(input: {
    states: readonly EquipmentValidationState[]
    instances: readonly EquipmentAssetInstance[]
}): EquipmentValidationSummary {
    let valid = 0, needsAttention = 0, notEvaluated = 0, placeholder = 0
    for (const s of input.states) {
        if (s.containmentStatus === 'PASS') valid += 1
        else if (s.containmentStatus === 'FAIL') needsAttention += 1
        else notEvaluated += 1
        if (s.envelopeIsPlaceholder) placeholder += 1
    }
    const locked = input.instances.filter((i) => i.lifecycleState === 'LOCKED').length
    return { equipmentCount: input.states.length, valid, needsAttention, notEvaluated, locked, placeholderEnvelopes: placeholder }
}

// ---------------------------------------------------------------------------
// Crosswalk readout (by reference — WHERE the number lives, never the number)
// ---------------------------------------------------------------------------

export interface CrosswalkReadoutLine {
    label: string
    authorityRef: string
    calibration: CrosswalkCalibration
    note?: string
}

export interface EquipmentCrosswalkReadout {
    canonicalEquipmentId: string
    manufacturer: string
    model: string
    canonicalClass: string
    lines: CrosswalkReadoutLine[]
}

/**
 * Build the capacity/production/cost crosswalk readout for an equipment
 * instance's canonical model. Returns undefined for an unknown canonical id
 * (never fabricates). Every line points at a backend authority; no value is
 * copied into the spatial layer.
 */
export function buildEquipmentCrosswalkReadout(canonicalEquipmentId: string): EquipmentCrosswalkReadout | undefined {
    const m = canonicalEquipmentById(canonicalEquipmentId)
    if (!m) return undefined
    return {
        canonicalEquipmentId: m.catalogModelId,
        manufacturer: m.manufacturer,
        model: m.model,
        canonicalClass: m.canonicalClass,
        lines: [
            { label: 'Capacity', authorityRef: m.capacityCrosswalk.authorityRef, calibration: m.capacityCrosswalk.calibration, note: m.capacityCrosswalk.note },
            { label: 'Production', authorityRef: m.productionCrosswalk.authorityRef, calibration: m.productionCrosswalk.calibration, note: m.productionCrosswalk.note },
            { label: 'Cost', authorityRef: m.costCrosswalk.authorityRef, calibration: m.costCrosswalk.calibration, note: m.costCrosswalk.note },
        ],
    }
}

// ---------------------------------------------------------------------------
// Generic DIAGNOSE SELECTED EQUIPMENT (bounded text report)
// ---------------------------------------------------------------------------

export interface SelectedEquipmentDiagnostic {
    iModelId: string
    equipmentInstanceId: string
    canonicalEquipmentId: string
    canonicalClass: string
    displayLabel: string
    parentBimSpaceId: string
    parentClinicalPlanningVolumeId?: string
    storeyId?: string
    lifecycleState: string
    envelope: { width: number; depth: number; height: number; provenance: string }
    center: { x: number; y: number; zBase: number }
    yaw: number
    containmentStatus: ContainmentStatus
    totalSamples: number
    failedSamples: number
    authorityQuality: EquipmentAuthorityQuality
    lockAllowed: boolean
    crosswalk?: EquipmentCrosswalkReadout
}

export function buildSelectedEquipmentDiagnostic(input: {
    instance: EquipmentAssetInstance
    validation: EquipmentValidationState
    totalSamples: number
    failedSamples: number
}): SelectedEquipmentDiagnostic {
    const p = input.instance.placement
    return {
        iModelId: input.instance.iModelId,
        equipmentInstanceId: input.instance.id,
        canonicalEquipmentId: input.instance.canonicalEquipmentId,
        canonicalClass: input.instance.canonicalClass,
        displayLabel: input.instance.displayLabel,
        parentBimSpaceId: input.instance.parentBimSpaceId,
        parentClinicalPlanningVolumeId: input.instance.parentClinicalPlanningVolumeId,
        storeyId: input.instance.storeyId,
        lifecycleState: input.instance.lifecycleState,
        envelope: { width: p.width, depth: p.depth, height: p.height, provenance: p.envelopeProvenance },
        center: { x: p.centerX, y: p.centerY, zBase: p.zBase },
        yaw: p.yaw,
        containmentStatus: input.validation.containmentStatus,
        totalSamples: input.totalSamples,
        failedSamples: input.failedSamples,
        authorityQuality: input.validation.authorityQuality,
        lockAllowed: input.validation.isLockAllowed,
        crosswalk: buildEquipmentCrosswalkReadout(input.instance.canonicalEquipmentId),
    }
}

/** Format the generic selected-equipment diagnostic as a bounded text report. */
export function formatSelectedEquipmentDiagnostic(d: SelectedEquipmentDiagnostic): string {
    const L: string[] = ['=== SELECTED EQUIPMENT (generic) ===']
    L.push(`IMODEL_ID = ${d.iModelId || '(none)'}`)
    L.push(`EQUIPMENT_INSTANCE_ID = ${d.equipmentInstanceId}`)
    L.push(`CANONICAL_EQUIPMENT_ID = ${d.canonicalEquipmentId}`)
    L.push(`CANONICAL_CLASS = ${d.canonicalClass}`)
    L.push(`DISPLAY_LABEL = ${d.displayLabel}`)
    L.push(`PARENT_BIM_SPACE_ID = ${d.parentBimSpaceId}`)
    L.push(`PARENT_PLANNING_VOLUME_ID = ${d.parentClinicalPlanningVolumeId ?? '(none)'}`)
    L.push(`STOREY_ID = ${d.storeyId ?? '(unknown)'}`)
    L.push(`LIFECYCLE = ${d.lifecycleState}`)
    L.push(`ENVELOPE = ${d.envelope.width.toFixed(2)} x ${d.envelope.depth.toFixed(2)} x ${d.envelope.height.toFixed(2)} m (${d.envelope.provenance})`)
    L.push(`CENTER = (${d.center.x.toFixed(2)}, ${d.center.y.toFixed(2)}, zBase ${d.center.zBase.toFixed(2)})`)
    L.push(`YAW_RAD = ${d.yaw.toFixed(4)}`)
    L.push(`GEOMETRY_AUTHORITY = ${d.authorityQuality}`)
    L.push(`CONTAINMENT_STATUS = ${d.containmentStatus}`)
    L.push(`CONTAINMENT_SAMPLES = ${d.totalSamples - d.failedSamples}/${d.totalSamples} inside`)
    L.push(`LOCK_ALLOWED = ${d.lockAllowed ? 'YES' : 'NO'}`)
    if (d.crosswalk) {
        L.push('--- CROSSWALK (by reference; values live in the backend) ---')
        for (const line of d.crosswalk.lines) {
            L.push(`${line.label.toUpperCase()}: ${line.authorityRef} [${line.calibration}]`)
        }
    }
    L.push(`FABRICATED_COSTS = NO`)
    L.push(`FABRICATED_CAPACITY = NO`)
    L.push(`BENTLEY_WRITE = NONE`)
    return L.join('\n')
}

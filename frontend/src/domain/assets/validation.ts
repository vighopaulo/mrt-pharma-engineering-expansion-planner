/**
 * Deterministic validation for core MRT Pharma asset records. Returns explicit
 * errors — malformed spatial/identity data is never silently accepted.
 */
import {
    ASSET_FAMILY_CLASS,
    type AssetDefinition,
    type AssetDimensions,
    type AssetInstance,
    type GeometryRepresentation,
    type SpatialTransform,
    type ValidationError,
    type ValidationResult,
} from './types'

function isFiniteNumber(n: unknown): n is number {
    return typeof n === 'number' && Number.isFinite(n)
}

function validateDimensions(dims: AssetDimensions, prefix: string, errors: ValidationError[]): void {
    for (const key of ['width', 'depth', 'height'] as const) {
        const v = dims[key]
        if (!isFiniteNumber(v)) errors.push({ field: `${prefix}.${key}`, message: 'must be a finite number' })
        else if (v < 0) errors.push({ field: `${prefix}.${key}`, message: 'must be non-negative' })
    }
    if (dims.unit !== 'METERS') errors.push({ field: `${prefix}.unit`, message: 'must be METERS' })
}

function validateTransform(t: SpatialTransform, errors: ValidationError[]): void {
    const p = t.position, r = t.rotation, s = t.scale
    for (const key of ['x', 'y', 'z'] as const) {
        if (!isFiniteNumber(p[key])) errors.push({ field: `transform.position.${key}`, message: 'must be finite' })
        if (!isFiniteNumber(s[key])) errors.push({ field: `transform.scale.${key}`, message: 'must be finite' })
        else if (s[key] <= 0) errors.push({ field: `transform.scale.${key}`, message: 'must be > 0' })
    }
    for (const key of ['yaw', 'pitch', 'roll'] as const) {
        if (!isFiniteNumber(r[key])) errors.push({ field: `transform.rotation.${key}`, message: 'must be finite' })
    }
}

export function validateGeometryRepresentation(rep: GeometryRepresentation): ValidationResult {
    const errors: ValidationError[] = []
    if (!rep.geometryRepresentationId?.trim()) errors.push({ field: 'geometryRepresentationId', message: 'cannot be blank' })
    validateDimensions(rep.nativeDimensions, 'nativeDimensions', errors)
    return errors.length ? { ok: false, errors } : { ok: true }
}

export function validateAssetDefinition(def: AssetDefinition): ValidationResult {
    const errors: ValidationError[] = []
    if (!def.assetDefinitionId?.trim()) errors.push({ field: 'assetDefinitionId', message: 'cannot be blank' })
    if (!def.displayName?.trim()) errors.push({ field: 'displayName', message: 'cannot be blank' })
    if (!def.defaultGeometryRepresentationId?.trim()) {
        errors.push({ field: 'defaultGeometryRepresentationId', message: 'cannot be blank' })
    }
    // class must match the family's canonical class.
    const expectedClass = ASSET_FAMILY_CLASS[def.assetFamily]
    if (expectedClass && def.assetClass !== expectedClass) {
        errors.push({ field: 'assetClass', message: `must be ${expectedClass} for family ${def.assetFamily}` })
    }
    validateDimensions(def.defaultDimensions, 'defaultDimensions', errors)
    return errors.length ? { ok: false, errors } : { ok: true }
}

/**
 * Validate an instance in isolation (structural). Reference resolution (that
 * the definition/geometry ids resolve, and family compatibility) is done in
 * the registry via validateAssetInstanceAgainstRegistry.
 */
export function validateAssetInstance(inst: AssetInstance): ValidationResult {
    const errors: ValidationError[] = []
    if (!inst.assetInstanceId?.trim()) errors.push({ field: 'assetInstanceId', message: 'cannot be blank' })
    if (!inst.assetDefinitionId?.trim()) errors.push({ field: 'assetDefinitionId', message: 'cannot be blank' })
    if (!inst.geometryRepresentationId?.trim()) errors.push({ field: 'geometryRepresentationId', message: 'cannot be blank' })
    if (!inst.projectId?.trim()) errors.push({ field: 'projectId', message: 'cannot be blank' })
    if (!inst.displayLabel?.trim()) errors.push({ field: 'displayLabel', message: 'cannot be blank' })
    validateTransform(inst.transform, errors)
    validateDimensions(inst.dimensions, 'dimensions', errors)
    return errors.length ? { ok: false, errors } : { ok: true }
}

/**
 * MRT Pharma asset registries + deterministic resolution.
 *
 * Two in-memory registries: GeometryRepresentation and AssetDefinition. A
 * geometry representation may be shared by many definitions (ONE GEOMETRY →
 * MANY ENGINEERING IDENTITIES). Resolution is deterministic and returns an
 * explicit GEOMETRY_NOT_AVAILABLE state rather than silently substituting
 * unrelated geometry.
 */
import {
    ASSET_FAMILY_CLASS,
    type AssetDefinition,
    type AssetInstance,
    type GeometryRepresentation,
    type GeometryResolution,
    type ValidationError,
    type ValidationResult,
} from './types'
import { validateAssetDefinition, validateAssetInstance, validateGeometryRepresentation } from './validation'

export class AssetRegistry {
    private readonly geometry = new Map<string, GeometryRepresentation>()
    private readonly definitions = new Map<string, AssetDefinition>()

    // --- geometry representations ---
    registerGeometryRepresentation(rep: GeometryRepresentation): void {
        const v = validateGeometryRepresentation(rep)
        if (!v.ok) throw new AssetRegistryError('invalid GeometryRepresentation', v.errors)
        this.geometry.set(rep.geometryRepresentationId, rep)
    }

    getGeometryRepresentation(id: string): GeometryRepresentation | undefined {
        return this.geometry.get(id)
    }

    listGeometryRepresentations(): GeometryRepresentation[] {
        return Array.from(this.geometry.values())
    }

    // --- asset definitions ---
    registerAssetDefinition(def: AssetDefinition): void {
        const v = validateAssetDefinition(def)
        if (!v.ok) throw new AssetRegistryError('invalid AssetDefinition', v.errors)
        // A definition's default geometry must resolve and be family-compatible.
        const res = this.resolveGeometryForAssetDefinition(def, /* useLocal */ def)
        if (res.status !== 'RESOLVED') {
            throw new AssetRegistryError('AssetDefinition default geometry does not resolve', [
                { field: 'defaultGeometryRepresentationId', message: `unresolved: ${def.defaultGeometryRepresentationId}` },
            ])
        }
        if (res.representation.assetFamily !== def.assetFamily) {
            throw new AssetRegistryError('geometry family incompatible with definition family', [
                {
                    field: 'assetFamily',
                    message: `definition ${def.assetFamily} != geometry ${res.representation.assetFamily}`,
                },
            ])
        }
        this.definitions.set(def.assetDefinitionId, def)
    }

    getAssetDefinition(id: string): AssetDefinition | undefined {
        return this.definitions.get(id)
    }

    listAssetDefinitions(): AssetDefinition[] {
        return Array.from(this.definitions.values())
    }

    // --- resolution ---
    getGeometryResolution(id: string): GeometryResolution {
        const rep = this.geometry.get(id)
        return rep ? { status: 'RESOLVED', representation: rep } : { status: 'GEOMETRY_NOT_AVAILABLE', requestedId: id }
    }

    /**
     * Resolve the geometry for a definition. Accepts either a definition id or,
     * during registration, the definition object itself (not yet stored).
     */
    resolveGeometryForAssetDefinition(defOrId: string | AssetDefinition, useLocal?: AssetDefinition): GeometryResolution {
        const def = typeof defOrId === 'string' ? this.definitions.get(defOrId) : (useLocal ?? defOrId)
        if (!def) return { status: 'GEOMETRY_NOT_AVAILABLE', requestedId: String(defOrId) }
        return this.getGeometryResolution(def.defaultGeometryRepresentationId)
    }

    /**
     * Structural + reference validation of an instance against this registry:
     * definition resolves, geometry resolves, and geometry family matches the
     * definition family.
     */
    validateAssetInstanceAgainstRegistry(inst: AssetInstance): ValidationResult {
        const structural = validateAssetInstance(inst)
        const errors: ValidationError[] = structural.ok ? [] : [...structural.errors]

        const def = this.definitions.get(inst.assetDefinitionId)
        if (!def) {
            errors.push({ field: 'assetDefinitionId', message: `unresolved definition: ${inst.assetDefinitionId}` })
        }
        const geoRes = this.getGeometryResolution(inst.geometryRepresentationId)
        if (geoRes.status !== 'RESOLVED') {
            errors.push({ field: 'geometryRepresentationId', message: `unresolved geometry: ${inst.geometryRepresentationId}` })
        }
        if (def && geoRes.status === 'RESOLVED') {
            const expectedClass = ASSET_FAMILY_CLASS[def.assetFamily]
            if (geoRes.representation.assetFamily !== def.assetFamily) {
                errors.push({
                    field: 'geometryRepresentationId',
                    message: `geometry family ${geoRes.representation.assetFamily} incompatible with definition family ${def.assetFamily}`,
                })
            }
            if (def.assetClass !== expectedClass) {
                errors.push({ field: 'assetClass', message: `definition class mismatch for family ${def.assetFamily}` })
            }
        }
        return errors.length ? { ok: false, errors } : { ok: true }
    }
}

export class AssetRegistryError extends Error {
    readonly errors: ValidationError[]
    constructor(message: string, errors: ValidationError[]) {
        super(`${message}: ${errors.map((e) => `${e.field} ${e.message}`).join('; ')}`)
        this.name = 'AssetRegistryError'
        this.errors = errors
    }
}

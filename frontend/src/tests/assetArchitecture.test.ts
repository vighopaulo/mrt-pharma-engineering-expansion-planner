/**
 * Offline unit tests for the MRT Pharma 3D asset architecture. No Bentley auth,
 * no network, no @itwin runtime (the pure domain + Bentley-free scannerGeometry
 * module are exercised; the Bentley decorator itself is validated via its pure
 * planning path in a separate concern to avoid importing the @itwin stack here).
 */
import { describe, expect, it } from 'vitest'
import {
    AssetRegistry,
    assignAssetToRoom,
    buildGenericPetCtTestAsset,
    buildGenericPetCtTestInstance,
    computeTestPlacement,
    createAssetInstance,
    createSeedRegistry,
    deserializeAssetInstance,
    GENERIC_PET_CT_DEFINITION,
    GENERIC_PET_CT_DEFINITION_B,
    GENERIC_PET_CT_DEFINITION_B_ID,
    GENERIC_PET_CT_DEFINITION_ID,
    GENERIC_PET_CT_GEOMETRY,
    GENERIC_PET_CT_GEOMETRY_ID,
    moveAsset,
    serializeAssetInstance,
    TEST_ASSET_INSTANCE_ID,
    TEST_PROJECT_ID,
    type AssetInstance,
} from '../domain/assets'
import { buildScannerParts } from '../components/spatial/scannerGeometry'

const NEIGH = { center: { x: 10, y: 20, z: 0 }, diagonal: 33 }

// A — asset-definition creation/validation
describe('asset definition creation/validation', () => {
    it('registers a valid generic PET/CT definition', () => {
        const r = createSeedRegistry()
        const def = r.getAssetDefinition(GENERIC_PET_CT_DEFINITION_ID)
        expect(def).toBeDefined()
        expect(def?.assetFamily).toBe('PET_CT_SCANNER')
        expect(def?.assetClass).toBe('IMAGING')
        expect(def?.manufacturer).toBe('GENERIC')
    })

    it('rejects a definition whose class mismatches its family', () => {
        const r = new AssetRegistry()
        r.registerGeometryRepresentation(GENERIC_PET_CT_GEOMETRY)
        expect(() =>
            r.registerAssetDefinition({ ...GENERIC_PET_CT_DEFINITION, assetClass: 'MRT' }),
        ).toThrow()
    })

    it('rejects a definition whose default geometry does not resolve', () => {
        const r = new AssetRegistry()
        expect(() =>
            r.registerAssetDefinition({ ...GENERIC_PET_CT_DEFINITION, defaultGeometryRepresentationId: 'NOPE' }),
        ).toThrow()
    })
})

// B — asset-instance creation
describe('asset instance creation', () => {
    it('creates a valid instance placed at the given position', () => {
        const r = createSeedRegistry()
        const res = createAssetInstance({
            registry: r,
            assetInstanceId: TEST_ASSET_INSTANCE_ID,
            assetDefinitionId: GENERIC_PET_CT_DEFINITION_ID,
            projectId: TEST_PROJECT_ID,
            position: { x: 1, y: 2, z: 0 },
        })
        expect(res.ok).toBe(true)
        if (res.ok) {
            expect(res.instance.displayLabel).toBe('Generic PET/CT Scanner')
            expect(res.instance.transform.coordinateSpace).toBe('BENTLEY_WORLD_COORDINATES')
            expect(res.event.type).toBe('ASSET_INSTANCE_CREATED')
        }
    })

    it('fails to create an instance from an unresolved definition', () => {
        const r = createSeedRegistry()
        const res = createAssetInstance({
            registry: r,
            assetInstanceId: 'X',
            assetDefinitionId: 'DOES_NOT_EXIST',
            projectId: TEST_PROJECT_ID,
            position: { x: 0, y: 0, z: 0 },
        })
        expect(res.ok).toBe(false)
    })
})

// C — definition → geometry resolution
describe('definition -> geometry resolution', () => {
    it('resolves the shared geometry for the definition', () => {
        const r = createSeedRegistry()
        const res = r.resolveGeometryForAssetDefinition(GENERIC_PET_CT_DEFINITION_ID)
        expect(res.status).toBe('RESOLVED')
        if (res.status === 'RESOLVED') expect(res.representation.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
    })

    it('returns GEOMETRY_NOT_AVAILABLE for an unknown geometry id', () => {
        const r = createSeedRegistry()
        const res = r.getGeometryResolution('UNKNOWN_GEO')
        expect(res.status).toBe('GEOMETRY_NOT_AVAILABLE')
    })
})

// D + 53 — one geometry, many engineering identities
describe('ONE_GEOMETRY_MANY_ENGINEERING_IDENTITIES', () => {
    it('two distinct definitions resolve to the same geometry without duplicating it', () => {
        const r = createSeedRegistry()
        const a = r.resolveGeometryForAssetDefinition(GENERIC_PET_CT_DEFINITION_ID)
        const b = r.resolveGeometryForAssetDefinition(GENERIC_PET_CT_DEFINITION_B_ID)
        expect(a.status).toBe('RESOLVED')
        expect(b.status).toBe('RESOLVED')
        if (a.status === 'RESOLVED' && b.status === 'RESOLVED') {
            expect(a.representation.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
            expect(b.representation.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
            // Same object instance in the registry — geometry metadata not duplicated.
            expect(a.representation).toBe(b.representation)
        }
        // Only one geometry representation registered despite two definitions.
        expect(r.listGeometryRepresentations()).toHaveLength(1)
        expect(r.listAssetDefinitions()).toHaveLength(2)
        expect(GENERIC_PET_CT_DEFINITION.assetDefinitionId).not.toBe(GENERIC_PET_CT_DEFINITION_B.assetDefinitionId)
    })
})

// 52 — identity separation
describe('IDENTITY_SEPARATION', () => {
    it('geometryRepresentationId != assetDefinitionId != assetInstanceId', () => {
        const inst = buildGenericPetCtTestInstance(NEIGH)
        expect(inst.geometryRepresentationId).toBe(GENERIC_PET_CT_GEOMETRY_ID)
        expect(inst.assetDefinitionId).toBe(GENERIC_PET_CT_DEFINITION_ID)
        expect(inst.assetInstanceId).toBe(TEST_ASSET_INSTANCE_ID)
        expect(inst.geometryRepresentationId).not.toBe(inst.assetDefinitionId)
        expect(inst.assetDefinitionId).not.toBe(inst.assetInstanceId)
        expect(inst.geometryRepresentationId).not.toBe(inst.assetInstanceId)
    })
})

// E — transform serialization round-trip
describe('serialization', () => {
    it('serializes and deserializes an instance losslessly', () => {
        const inst = buildGenericPetCtTestInstance(NEIGH)
        const wire = serializeAssetInstance(inst)
        expect(wire.schema).toBe('mrt.asset-instance/v1')
        const back = deserializeAssetInstance(wire)
        expect(back).toEqual(inst)
    })

    it('does not carry any runtime object in the serialized form', () => {
        const inst = buildGenericPetCtTestInstance(NEIGH)
        const wire = serializeAssetInstance(inst)
        expect(JSON.parse(JSON.stringify(wire))).toEqual(wire) // JSON-safe
    })
})

// F — room assignment NOT_ASSIGNED behavior
describe('room assignment', () => {
    it('defaults to NOT_ASSIGNED', () => {
        const inst = buildGenericPetCtTestInstance(NEIGH)
        expect(inst.roomAssignment.state).toBe('NOT_ASSIGNED')
    })

    it('assigns a room immutably', () => {
        const inst = buildGenericPetCtTestInstance(NEIGH)
        const res = assignAssetToRoom(inst, { state: 'ASSIGNED', roomId: 'SCANNER_ROOM_2' })
        expect(res.ok).toBe(true)
        if (res.ok) {
            expect(res.instance.roomAssignment.state).toBe('ASSIGNED')
            expect(res.instance.roomAssignment.roomId).toBe('SCANNER_ROOM_2')
            expect(inst.roomAssignment.state).toBe('NOT_ASSIGNED') // original unchanged
            expect(res.instance).not.toBe(inst) // immutable transition
            expect(res.event.type).toBe('ASSET_ROOM_ASSIGNED')
        }
    })
})

// G — installation state behavior
describe('installation state', () => {
    it('proof instance is PLACED, never inferred from visibility', () => {
        const inst = buildGenericPetCtTestInstance(NEIGH)
        expect(inst.installationState).toBe('PLACED')
        expect(inst.spatialSource).toBe('GENERATED_GENERIC')
    })
})

// H — invalid dimensions rejected
describe('validation of malformed data', () => {
    it('rejects negative/NaN dimensions', () => {
        const r = createSeedRegistry()
        const badInst: AssetInstance = {
            ...buildGenericPetCtTestInstance(NEIGH),
            dimensions: { width: -1, depth: Number.NaN, height: 2, unit: 'METERS', provenance: 'NOT_CALIBRATED' },
        }
        const v = r.validateAssetInstanceAgainstRegistry(badInst)
        expect(v.ok).toBe(false)
    })

    it('rejects zero/negative scale', () => {
        const r = createSeedRegistry()
        const badInst: AssetInstance = {
            ...buildGenericPetCtTestInstance(NEIGH),
            transform: { ...buildGenericPetCtTestInstance(NEIGH).transform, scale: { x: 0, y: 1, z: 1 } },
        }
        const v = r.validateAssetInstanceAgainstRegistry(badInst)
        expect(v.ok).toBe(false)
    })
})

// I — invalid unresolved geometry reference handled explicitly
describe('unresolved geometry reference', () => {
    it('flags an instance whose geometry id does not resolve', () => {
        const r = createSeedRegistry()
        const inst: AssetInstance = { ...buildGenericPetCtTestInstance(NEIGH), geometryRepresentationId: 'NOT_REGISTERED' }
        const v = r.validateAssetInstanceAgainstRegistry(inst)
        expect(v.ok).toBe(false)
        if (!v.ok) expect(v.errors.some((e) => e.field === 'geometryRepresentationId')).toBe(true)
    })
})

// J — deterministic generic PET/CT test instance construction
describe('deterministic test placement', () => {
    it('places within the model neighborhood (bounded offset)', () => {
        const pos = computeTestPlacement(NEIGH)
        // offset = clamp(33*0.15=4.95, [2,15]) = 4.95 → x = 10 + 4.95
        expect(pos.x).toBeCloseTo(14.95, 5)
        expect(pos.y).toBe(20)
        expect(pos.z).toBe(0)
    })

    it('builds the same placement for the same neighborhood (deterministic)', () => {
        const a = buildGenericPetCtTestAsset(NEIGH)
        const b = buildGenericPetCtTestAsset(NEIGH)
        expect(a.result.ok && b.result.ok).toBe(true)
        if (a.result.ok && b.result.ok) expect(a.result.instance.transform.position).toEqual(b.result.instance.transform.position)
    })

    it('clamps a tiny model diagonal to a minimum offset', () => {
        const pos = computeTestPlacement({ center: { x: 0, y: 0, z: 0 }, diagonal: 1 })
        expect(pos.x).toBe(2) // clamp lower bound
    })
})

// command service — move immutability
describe('command service immutability', () => {
    it('moveAsset returns a new instance and does not mutate the original', () => {
        const inst = buildGenericPetCtTestInstance(NEIGH)
        const originalX = inst.transform.position.x
        const res = moveAsset(inst, { x: 5, y: 0, z: 0 })
        expect(res.ok).toBe(true)
        if (res.ok) {
            expect(res.instance.transform.position.x).toBe(originalX + 5)
            expect(inst.transform.position.x).toBe(originalX) // unchanged
        }
    })
})

// scanner geometry plan (Bentley-free) — proves geometry mapping
describe('scanner geometry parts', () => {
    it('produces gantry + bore + patient table parts', () => {
        const inst = buildGenericPetCtTestInstance(NEIGH)
        const parts = buildScannerParts(inst)
        const kinds = parts.map((p) => `${p.part}:${p.kind}`)
        expect(kinds).toContain('GANTRY:BOX')
        expect(kinds).toContain('BORE:CYLINDER')
        expect(kinds).toContain('PATIENT_TABLE:BOX')
        expect(parts).toHaveLength(3)
    })

    it('all part coordinates are finite', () => {
        const inst = buildGenericPetCtTestInstance(NEIGH)
        for (const p of buildScannerParts(inst)) {
            if (p.kind === 'BOX') {
                expect(p.low.every(Number.isFinite)).toBe(true)
                expect(p.high.every(Number.isFinite)).toBe(true)
            } else {
                expect(p.centerA.every(Number.isFinite)).toBe(true)
                expect(p.centerB.every(Number.isFinite)).toBe(true)
                expect(Number.isFinite(p.radius)).toBe(true)
            }
        }
    })
})

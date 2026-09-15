/**
 * Equipment Visual Integration tests — proves the recognizable generic VISUAL
 * geometry (cyclotron / PET-CT / hot-cell) is produced from the SAME
 * authoritative pose as the equipment envelope, that many exact canonical
 * models map to ONE generic visual family, and that canonical ENGINEERING
 * identity is never overwritten by the visual mapping.
 *
 * Bentley-FREE: exercises the pure equipmentGeometry recipe + equipmentInstance
 * persistence + the canonical catalog. No @itwin runtime, no network, no auth.
 */
import { describe, expect, it } from 'vitest'
import {
    buildCyclotronParts,
    buildEquipmentParts,
    buildEquipmentPartsForInstance,
    buildRadiopharmacyParts,
    resolveVisualFamilyForAssetFamily,
    resolveVisualFamilyForCanonical,
    resolveVisualFamilyForGeometryId,
    type EquipmentPose,
} from '../components/spatial/equipmentGeometry'
import {
    canonicalEquipmentById,
} from '../components/spatial/canonicalEquipmentCatalog'
import {
    createEquipmentInstance,
    loadEquipmentInstances,
    saveEquipmentInstances,
    type EquipmentAssetInstance,
} from '../components/spatial/equipmentInstance'
import {
    buildGeDiscoveryMiCatalogTestAsset,
    buildGenericPetCtTestInstance,
} from '../domain/assets'
import type { AssetInstance } from '../domain/assets'

const NEIGH = { center: { x: 10, y: 20, z: 0 }, diagonal: 33 }

// A square 6x6 room footprint centered at (10,20), floor z 0..3.
const ROOM_FOOTPRINT = [
    { x: 7, y: 17 }, { x: 13, y: 17 }, { x: 13, y: 23 }, { x: 7, y: 23 },
]
const ROOM_Z_LOW = 0
const ROOM_Z_HIGH = 3

function makeEquipment(canonicalEquipmentId: string, seq = 1): EquipmentAssetInstance {
    const res = createEquipmentInstance({
        iModelId: 'imodel-A',
        canonicalEquipmentId,
        parentBimSpaceId: 'ROOM-1',
        footprint: ROOM_FOOTPRINT,
        zLow: ROOM_Z_LOW,
        zHigh: ROOM_Z_HIGH,
        seq,
    })
    if (!res.ok) throw new Error(`createEquipmentInstance failed: ${res.reason}`)
    return res.instance
}

function poseFrom(inst: EquipmentAssetInstance): EquipmentPose {
    const p = inst.placement
    return {
        center: [p.centerX, p.centerY, p.zBase],
        width: p.width,
        depth: p.depth,
        height: p.height,
        yawRadians: p.yaw,
    }
}

// ---------------------------------------------------------------------------
// Visual mapping — many canonical models → one generic visual family
// ---------------------------------------------------------------------------
describe('canonical → generic visual family mapping', () => {
    it('two DISTINCT canonical cyclotrons map to the SAME generic cyclotron visual', () => {
        const a = canonicalEquipmentById('GE_PETTRACE_890')!
        const b = canonicalEquipmentById('IBA_CYCLONE_KIUBE')!
        expect(a.catalogModelId).not.toBe(b.catalogModelId) // canonical A != canonical B

        const famA = resolveVisualFamilyForCanonical({ canonicalClass: a.canonicalClass, assetFamily: a.assetFamily })
        const famB = resolveVisualFamilyForCanonical({ canonicalClass: b.canonicalClass, assetFamily: b.assetFamily })
        // EVI-MA-04: canonical cyclotrons now resolve to the medium-LOD V2 family.
        expect(famA).toBe('GENERIC_MEDICAL_CYCLOTRON_V2')
        expect(famB).toBe('GENERIC_MEDICAL_CYCLOTRON_V2')
        expect(famA).toBe(famB) // same generic visual for different canonical models
    })

    it('a canonical scanner maps to the generic PET/CT visual', () => {
        const s = canonicalEquipmentById('GE_DISCOVERY_MI')!
        const fam = resolveVisualFamilyForCanonical({ canonicalClass: s.canonicalClass, assetFamily: s.assetFamily })
        expect(fam).toBe('GENERIC_PET_CT_SCANNER_V1')
    })

    it('asset-family and geometry-id resolvers agree for the scanner family', () => {
        expect(resolveVisualFamilyForAssetFamily('PET_CT_SCANNER')).toBe('GENERIC_PET_CT_SCANNER_V1')
        // EVI-MA-04: CYCLOTRON asset family resolves to the medium-LOD V2 visual.
        expect(resolveVisualFamilyForAssetFamily('CYCLOTRON')).toBe('GENERIC_MEDICAL_CYCLOTRON_V2')
        expect(resolveVisualFamilyForAssetFamily('HOT_CELL')).toBe('GENERIC_RADIOPHARMACY_HOTCELL_V1')
        expect(resolveVisualFamilyForGeometryId('GENERIC_PET_CT_SCANNER_V1')).toBe('GENERIC_PET_CT_SCANNER_V1')
    })
})

// ---------------------------------------------------------------------------
// Canonical identity is never overwritten by the visual mapping
// ---------------------------------------------------------------------------
describe('canonical identity separation', () => {
    it('placing a canonical cyclotron keeps its exact canonicalEquipmentId (visual is separate)', () => {
        const inst = makeEquipment('GE_PETTRACE_890')
        expect(inst.canonicalEquipmentId).toBe('GE_PETTRACE_890')
        expect(inst.canonicalClass).toBe('CYCLOTRON')
        const model = canonicalEquipmentById(inst.canonicalEquipmentId)!
        expect(model.manufacturer).toBe('GE HealthCare')
        expect(model.model).toBe('PETtrace 890')
        // Visual resolution does not mutate the instance identity.
        const fam = resolveVisualFamilyForCanonical({ canonicalClass: inst.canonicalClass, assetFamily: inst.assetFamily })
        expect(fam).toBe('GENERIC_MEDICAL_CYCLOTRON_V2')
        expect(inst.canonicalEquipmentId).toBe('GE_PETTRACE_890')
    })
})

// ---------------------------------------------------------------------------
// Structural geometry composition — each family is recognizable, not one box
// ---------------------------------------------------------------------------
describe('recognizable structural composition per family', () => {
    const basePose: EquipmentPose = { center: [10, 20, 0], width: 2, depth: 2, height: 2, yawRadians: 0 }

    it('PET/CT visual has gantry + bore + table (not a single box)', () => {
        const parts = buildEquipmentParts('GENERIC_PET_CT_SCANNER_V1', basePose)
        const kinds = parts.map((p) => p.part)
        expect(kinds).toContain('GANTRY')
        expect(kinds).toContain('BORE')
        expect(kinds).toContain('PATIENT_TABLE')
        expect(parts.length).toBeGreaterThanOrEqual(3)
        // Must NOT be a single box.
        expect(parts.some((p) => p.kind === 'CYLINDER')).toBe(true)
    })

    it('cyclotron visual has body + shielding + service cabinet (multiple primitives)', () => {
        const parts = buildCyclotronParts(basePose)
        const kinds = parts.map((p) => p.part)
        expect(kinds).toContain('CYCLOTRON_BODY')
        expect(kinds).toContain('CYCLOTRON_SHIELDING')
        expect(kinds).toContain('CYCLOTRON_SERVICE_CABINET')
        expect(parts.length).toBeGreaterThanOrEqual(3)
        // A cyclotron reads as a cylindrical body, not a rectangular box.
        expect(parts.some((p) => p.kind === 'CYLINDER')).toBe(true)
    })

    it('radiopharmacy visual has hot cell + workbench + dispensing (multiple components)', () => {
        const parts = buildRadiopharmacyParts(basePose)
        const kinds = parts.map((p) => p.part)
        expect(kinds).toContain('HOT_CELL')
        expect(kinds).toContain('WORKBENCH')
        expect(kinds).toContain('DISPENSING')
        expect(parts.length).toBeGreaterThanOrEqual(3)
    })

    it('all part coordinates are finite for every family', () => {
        for (const fam of ['GENERIC_PET_CT_SCANNER_V1', 'GENERIC_MEDICAL_CYCLOTRON_V1', 'GENERIC_MEDICAL_CYCLOTRON_V2', 'GENERIC_RADIOPHARMACY_HOTCELL_V1'] as const) {
            for (const p of buildEquipmentParts(fam, basePose)) {
                if (p.kind === 'BOX') {
                    expect(p.low.every(Number.isFinite)).toBe(true)
                    expect(p.high.every(Number.isFinite)).toBe(true)
                } else {
                    expect(p.centerA.every(Number.isFinite)).toBe(true)
                    expect(p.centerB.every(Number.isFinite)).toBe(true)
                    expect(Number.isFinite(p.radius)).toBe(true)
                }
            }
        }
    })
})

// ---------------------------------------------------------------------------
// Pose — visual follows the AssetInstance pose (translation + yaw)
// ---------------------------------------------------------------------------
describe('visual follows equipment pose', () => {
    it('translating the equipment translates the cyclotron visual', () => {
        const p0: EquipmentPose = { center: [0, 0, 0], width: 2, depth: 2, height: 2, yawRadians: 0 }
        const p1: EquipmentPose = { center: [5, 7, 0], width: 2, depth: 2, height: 2, yawRadians: 0 }
        const a = buildCyclotronParts(p0)
        const b = buildCyclotronParts(p1)
        const bodyA = a.find((p) => p.part === 'CYCLOTRON_BODY')! as { centerA: number[] }
        const bodyB = b.find((p) => p.part === 'CYCLOTRON_BODY')! as { centerA: number[] }
        expect(bodyB.centerA[0]).toBeCloseTo(bodyA.centerA[0] + 5, 6)
        expect(bodyB.centerA[1]).toBeCloseTo(bodyA.centerA[1] + 7, 6)
    })

    it('yawing the equipment rotates the cyclotron visual (cylinder endpoints move)', () => {
        const p0: EquipmentPose = { center: [10, 20, 0], width: 3, depth: 2, height: 2, yawRadians: 0 }
        const p90: EquipmentPose = { ...p0, yawRadians: Math.PI / 2 }
        const a = buildCyclotronParts(p0)
        const b = buildCyclotronParts(p90)
        const bodyA = a.find((p) => p.part === 'CYCLOTRON_BODY')! as { centerA: number[] }
        const bodyB = b.find((p) => p.part === 'CYCLOTRON_BODY')! as { centerA: number[] }
        // The body base is offset from center in X; a 90° yaw moves that offset
        // into Y, so the endpoints must differ.
        expect(bodyA.centerA[0]).not.toBeCloseTo(bodyB.centerA[0], 3)
    })

    it('yawing the radiopharmacy visual rotates its hot cell box params (center carried, yaw applied)', () => {
        const p0: EquipmentPose = { center: [10, 20, 0], width: 2, depth: 3, height: 2, yawRadians: 0 }
        const p90: EquipmentPose = { ...p0, yawRadians: Math.PI / 2 }
        const cell0 = buildRadiopharmacyParts(p0).find((p) => p.part === 'HOT_CELL')! as { yawRadians: number }
        const cell90 = buildRadiopharmacyParts(p90).find((p) => p.part === 'HOT_CELL')! as { yawRadians: number }
        expect(cell0.yawRadians).toBe(0)
        expect(cell90.yawRadians).toBeCloseTo(Math.PI / 2, 6)
    })
})

// ---------------------------------------------------------------------------
// Persistence — visual reconstructs deterministically after reload
// ---------------------------------------------------------------------------
describe('persistence reconstructs the same visual after reload', () => {
    it('a persisted cyclotron reloads to the same canonical id, pose and visual family', () => {
        const store = new Map<string, string>()
        const storage = {
            getItem: (k: string) => store.get(k) ?? null,
            setItem: (k: string, v: string) => { store.set(k, v) },
        }
        const inst = makeEquipment('GE_PETTRACE_890')
        saveEquipmentInstances('imodel-A', [inst], storage)

        const reloaded = loadEquipmentInstances('imodel-A', storage)
        expect(reloaded).toHaveLength(1)
        const r = reloaded[0]
        expect(r.canonicalEquipmentId).toBe('GE_PETTRACE_890')
        expect(r.placement.centerX).toBeCloseTo(inst.placement.centerX, 9)
        expect(r.placement.yaw).toBeCloseTo(inst.placement.yaw, 9)

        // The visual is regenerated from family + pose (never stored as a mesh).
        const before = buildCyclotronParts(poseFrom(inst))
        const after = buildCyclotronParts(poseFrom(r))
        expect(JSON.stringify(after)).toBe(JSON.stringify(before))
        // Confirm no rendered mesh leaked into persistence.
        const raw = store.get('mrtpharma.equipment.v1.imodel-A')!
        expect(raw).not.toContain('vertices')
        expect(raw).not.toContain('triangles')
    })
})

// ---------------------------------------------------------------------------
// Lock — locked equipment stays renderable
// ---------------------------------------------------------------------------
describe('locked equipment remains rendered', () => {
    it('a LOCKED cyclotron still produces recognizable geometry', () => {
        const inst = makeEquipment('GE_PETTRACE_890')
        const locked: EquipmentAssetInstance = { ...inst, lifecycleState: 'LOCKED' }
        const parts = buildCyclotronParts(poseFrom(locked))
        expect(parts.length).toBeGreaterThanOrEqual(3) // lock affects lifecycle, not visibility
    })
})

// ---------------------------------------------------------------------------
// Provenance — representative geometry stays representative / non-authoritative
// ---------------------------------------------------------------------------
describe('representative provenance', () => {
    it('a placeholder-envelope cyclotron carries GENERIC_ENGINEERING_PLACEHOLDER provenance', () => {
        // GE PETtrace carries no calibrated envelope in the backend catalog.
        const inst = makeEquipment('GE_PETTRACE_890')
        expect(inst.placement.envelopeProvenance).toBe('GENERIC_ENGINEERING_PLACEHOLDER')
    })

    it('a manufacturer-calibrated cyclotron reflects calibrated provenance (not fabricated)', () => {
        const inst = makeEquipment('IBA_CYCLONE_KIUBE')
        // IBA Cyclone KIUBE has a manufacturer-calibrated envelope in the catalog.
        expect(inst.placement.envelopeProvenance).not.toBe('GENERIC_ENGINEERING_PLACEHOLDER')
    })
})

// ---------------------------------------------------------------------------
// Scanner regression — persisted GE Discovery MI resolves to recognizable PET/CT
// ---------------------------------------------------------------------------
describe('Discovery MI scanner regression', () => {
    it('the GE Discovery MI catalog AssetInstance resolves to recognizable PET/CT geometry', () => {
        const { result } = buildGeDiscoveryMiCatalogTestAsset(NEIGH)
        expect(result.ok).toBe(true)
        if (!result.ok) return
        const inst: AssetInstance = result.instance
        // Exact canonical identity is preserved via the definition/createdFrom.
        expect(inst.geometryRepresentationId).toBe('GENERIC_PET_CT_SCANNER_V1')

        // The visual family resolves to PET/CT — recognizable, not a proxy box.
        expect(resolveVisualFamilyForGeometryId(inst.geometryRepresentationId)).toBe('GENERIC_PET_CT_SCANNER_V1')
        const parts = buildEquipmentPartsForInstance(inst)
        const kinds = parts.map((p) => p.part)
        expect(kinds).toContain('GANTRY')
        expect(kinds).toContain('BORE')
        expect(kinds).toContain('PATIENT_TABLE')
    })

    it('the generic PET/CT AssetInstance also resolves to recognizable PET/CT geometry', () => {
        const inst = buildGenericPetCtTestInstance(NEIGH)
        const parts = buildEquipmentPartsForInstance(inst)
        expect(parts.map((p) => p.part)).toContain('BORE')
    })
})

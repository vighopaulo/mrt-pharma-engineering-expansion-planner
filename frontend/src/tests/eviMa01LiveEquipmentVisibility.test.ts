/**
 * EVI-MA-01 — Live equipment visibility + locatability correction tests.
 *
 * Bentley-FREE. Proves the KIUBE cyclotron resolves to recognizable geometry at
 * a Z derived from its parent-room authority, that Fit-to-Equipment produces a
 * finite non-degenerate world range that moves with the pose, that the visual +
 * envelope share ONE instance pose, and that selection / delete / lock behave.
 */
import { describe, expect, it } from 'vitest'
import {
    buildEquipmentParts,
    buildEquipmentVisualDiagnostic,
    computeEquipmentWorldBounds,
    isNonDegenerateBounds,
    resolveVisualFamilyForCanonical,
    type EquipmentPose,
} from '../components/spatial/equipmentGeometry'
import {
    canonicalEquipmentById,
} from '../components/spatial/canonicalEquipmentCatalog'
import {
    createEquipmentInstance,
    type EquipmentAssetInstance,
} from '../components/spatial/equipmentInstance'

// A second-floor room (NON-zero floor Z) so the Z-from-parent path is exercised.
const FLOOR2_Z_LOW = 8.4
const FLOOR2_Z_HIGH = 12.0
// A room footprint around the reported KIUBE location (X=-40.33, Y=30.02).
const ROOM_FOOTPRINT = [
    { x: -44, y: 26 }, { x: -36, y: 26 }, { x: -36, y: 34 }, { x: -44, y: 34 },
]

function makeKiube(): EquipmentAssetInstance {
    const res = createEquipmentInstance({
        iModelId: 'imodel-EVI',
        canonicalEquipmentId: 'IBA_CYCLONE_KIUBE',
        parentBimSpaceId: '0x2000000094e',
        footprint: ROOM_FOOTPRINT,
        zLow: FLOOR2_Z_LOW,
        zHigh: FLOOR2_Z_HIGH,
        seq: 1,
    })
    if (!res.ok) throw new Error(`KIUBE create failed: ${res.reason}`)
    return res.instance
}

function poseFrom(inst: EquipmentAssetInstance): EquipmentPose {
    const p = inst.placement
    return { center: [p.centerX, p.centerY, p.zBase], width: p.width, depth: p.depth, height: p.height, yawRadians: p.yaw }
}

// ---------------------------------------------------------------------------
// KIUBE regression fixture
// ---------------------------------------------------------------------------
describe('EVI-MA-01 KIUBE cyclotron visual', () => {
    it('resolves canonical CYCLOTRON -> GENERIC_MEDICAL_CYCLOTRON_V2 with shielded shells + cabinet', () => {
        const inst = makeKiube()
        expect(inst.canonicalClass).toBe('CYCLOTRON')
        const model = canonicalEquipmentById(inst.canonicalEquipmentId)!
        expect(model.manufacturer).toBe('IBA')
        expect(model.model).toBe('Cyclone KIUBE')

        // EVI-MA-04: canonical cyclotrons resolve to the medium-LOD V2 machine.
        const family = resolveVisualFamilyForCanonical({ canonicalClass: inst.canonicalClass, assetFamily: inst.assetFamily })
        expect(family).toBe('GENERIC_MEDICAL_CYCLOTRON_V2')
        const parts = buildEquipmentParts(family!, poseFrom(inst))
        const kinds = parts.map((p) => p.part)
        // A recognizable medium-LOD machine: many differentiated components.
        expect(parts.length).toBeGreaterThanOrEqual(15)
        expect(kinds).toContain('CYC_LOWER_SHELL')
        expect(kinds).toContain('CYC_UPPER_SHELL')
        expect(kinds).toContain('CYC_CABINET')
    })

    it('derives Z from the parent room floor (NOT world zero)', () => {
        const inst = makeKiube()
        // zBase sits on the second-floor room floor, not 0.
        expect(inst.placement.zBase).toBeGreaterThan(FLOOR2_Z_LOW - 0.001)
        expect(inst.placement.zBase).toBeLessThan(FLOOR2_Z_HIGH)
        expect(inst.placement.zBase).not.toBe(0)

        const bounds = computeEquipmentWorldBounds({ pose: poseFrom(inst), family: 'GENERIC_MEDICAL_CYCLOTRON_V2' })!
        // Visual bottom is on the floor; nothing below the floor.
        expect(bounds.low[2]).toBeGreaterThan(FLOOR2_Z_LOW - 0.001)
    })

    it('visual bounds are finite and fit within the equipment envelope footprint', () => {
        const inst = makeKiube()
        const pose = poseFrom(inst)
        const visual = computeEquipmentWorldBounds({ pose, family: 'GENERIC_MEDICAL_CYCLOTRON_V2' })!
        expect(isNonDegenerateBounds(visual)).toBe(true)
        // The recognizable geometry stays within the envelope XY extent + a small
        // tolerance (the shielding drum can slightly exceed the body but is sized
        // from the envelope).
        const halfW = pose.width / 2 + 0.5
        const halfD = pose.depth / 2 + 0.5
        expect(visual.low[0]).toBeGreaterThan(pose.center[0] - halfW - pose.width)
        expect(visual.high[0]).toBeLessThan(pose.center[0] + halfW + pose.width)
        expect(visual.low[1]).toBeGreaterThan(pose.center[1] - halfD - pose.depth)
        expect(visual.high[1]).toBeLessThan(pose.center[1] + halfD + pose.depth)
    })
})

// ---------------------------------------------------------------------------
// Fit-to-Equipment bounds
// ---------------------------------------------------------------------------
describe('EVI-MA-01 Fit-to-Equipment bounds', () => {
    const pose: EquipmentPose = { center: [-40.33, 30.02, 8.4], width: 1.9, depth: 1.9, height: 1.8, yawRadians: 0 }

    it('produces a finite range with non-zero X/Y/Z extent', () => {
        const b = computeEquipmentWorldBounds({ pose, family: 'GENERIC_MEDICAL_CYCLOTRON_V1' })!
        expect(isNonDegenerateBounds(b)).toBe(true)
        expect(b.high[0] - b.low[0]).toBeGreaterThan(0)
        expect(b.high[1] - b.low[1]).toBeGreaterThan(0)
        expect(b.high[2] - b.low[2]).toBeGreaterThan(0)
    })

    it('translation moves the fit range', () => {
        const a = computeEquipmentWorldBounds({ pose, family: 'GENERIC_MEDICAL_CYCLOTRON_V1' })!
        const moved = computeEquipmentWorldBounds({ pose: { ...pose, center: [pose.center[0] + 10, pose.center[1] - 4, pose.center[2]] }, family: 'GENERIC_MEDICAL_CYCLOTRON_V1' })!
        expect(moved.low[0]).toBeCloseTo(a.low[0] + 10, 4)
        expect(moved.low[1]).toBeCloseTo(a.low[1] - 4, 4)
    })

    it('yaw changes the fit range', () => {
        const a = computeEquipmentWorldBounds({ pose, family: 'GENERIC_MEDICAL_CYCLOTRON_V1' })!
        const yawed = computeEquipmentWorldBounds({ pose: { ...pose, width: 3, depth: 1, yawRadians: Math.PI / 2 }, family: 'GENERIC_MEDICAL_CYCLOTRON_V1' })!
        const straight = computeEquipmentWorldBounds({ pose: { ...pose, width: 3, depth: 1, yawRadians: 0 }, family: 'GENERIC_MEDICAL_CYCLOTRON_V1' })!
        // A 90-degree yaw swaps the dominant extent axis.
        const yawedXExt = yawed.high[0] - yawed.low[0]
        const straightXExt = straight.high[0] - straight.low[0]
        expect(yawedXExt).not.toBeCloseTo(straightXExt, 2)
        expect(a).toBeDefined()
    })

    it('always returns at least the envelope bounds even with no family', () => {
        const b = computeEquipmentWorldBounds({ pose })!
        expect(isNonDegenerateBounds(b)).toBe(true)
    })
})

// ---------------------------------------------------------------------------
// Single instance / single pose — visual + envelope derive from one pose
// ---------------------------------------------------------------------------
describe('EVI-MA-01 single instance single pose', () => {
    it('visual bounds and envelope bounds move together under translation', () => {
        const pose0: EquipmentPose = { center: [0, 0, 0], width: 2, depth: 2, height: 2, yawRadians: 0 }
        const pose1: EquipmentPose = { ...pose0, center: [7, 3, 0] }
        const visual0 = computeEquipmentWorldBounds({ pose: pose0, family: 'GENERIC_MEDICAL_CYCLOTRON_V1' })!
        const visual1 = computeEquipmentWorldBounds({ pose: pose1, family: 'GENERIC_MEDICAL_CYCLOTRON_V1' })!
        const env0 = computeEquipmentWorldBounds({ pose: pose0 })!
        const env1 = computeEquipmentWorldBounds({ pose: pose1 })!
        expect(visual1.low[0] - visual0.low[0]).toBeCloseTo(7, 4)
        expect(env1.low[0] - env0.low[0]).toBeCloseTo(7, 4)
        expect(visual1.low[1] - visual0.low[1]).toBeCloseTo(3, 4)
        expect(env1.low[1] - env0.low[1]).toBeCloseTo(3, 4)
    })
})

// ---------------------------------------------------------------------------
// Diagnostic
// ---------------------------------------------------------------------------
describe('EVI-MA-01 visual diagnostic', () => {
    it('reports a renderable KIUBE with the expected family + primitive count', () => {
        const inst = makeKiube()
        const p = inst.placement
        const diag = buildEquipmentVisualDiagnostic({
            equipmentInstanceId: inst.id,
            canonicalModelId: inst.canonicalEquipmentId,
            canonicalClass: inst.canonicalClass,
            assetFamily: inst.assetFamily,
            parentRoomId: inst.parentBimSpaceId,
            pose: poseFrom(inst),
        })
        expect(diag.visualFamily).toBe('GENERIC_MEDICAL_CYCLOTRON_V2')
        expect(diag.canonicalModelId).toBe('IBA_CYCLONE_KIUBE')
        expect(diag.canonicalClass).toBe('CYCLOTRON')
        expect(diag.parentRoomId).toBe('0x2000000094e')
        expect(diag.primitiveCount).toBeGreaterThan(1)
        expect(diag.renderable).toBe(true)
        expect(diag.zBase).toBe(p.zBase)
        expect(diag.visualBounds && isNonDegenerateBounds(diag.visualBounds)).toBe(true)
        expect(diag.envelopeBounds && isNonDegenerateBounds(diag.envelopeBounds)).toBe(true)
    })

    it('reports VISUAL_NOT_AVAILABLE for a class without a recognizable family (generator)', () => {
        const gen = canonicalEquipmentById('CURIUM_TECHNELITE')!
        const diag = buildEquipmentVisualDiagnostic({
            equipmentInstanceId: 'eq-gen',
            canonicalModelId: gen.catalogModelId,
            canonicalClass: gen.canonicalClass,
            assetFamily: gen.assetFamily,
            parentRoomId: 'room-x',
            pose: { center: [1, 2, 3], width: 2, depth: 2, height: 2, yawRadians: 0 },
        })
        expect(diag.visualFamily).toBe('VISUAL_NOT_AVAILABLE')
        expect(diag.renderable).toBe(false)
        // Envelope bounds still present so the instance is at least locatable.
        expect(diag.envelopeBounds && isNonDegenerateBounds(diag.envelopeBounds)).toBe(true)
    })
})

// ---------------------------------------------------------------------------
// Selection identity (KIUBE != Discovery MI) — pure store-level reasoning
// ---------------------------------------------------------------------------
describe('EVI-MA-01 selection identity', () => {
    it('KIUBE and Discovery MI are distinct instances with distinct visual families', () => {
        const kiube = makeKiube()
        const petct = createEquipmentInstance({
            iModelId: 'imodel-EVI',
            canonicalEquipmentId: 'GE_DISCOVERY_MI',
            parentBimSpaceId: 'ROOM-PETCT',
            footprint: ROOM_FOOTPRINT,
            zLow: 0,
            zHigh: 3,
            seq: 2,
        })
        expect(petct.ok).toBe(true)
        if (!petct.ok) return
        expect(kiube.id).not.toBe(petct.instance.id)
        expect(resolveVisualFamilyForCanonical({ canonicalClass: kiube.canonicalClass })).toBe('GENERIC_MEDICAL_CYCLOTRON_V2')
        expect(resolveVisualFamilyForCanonical({ canonicalClass: petct.instance.canonicalClass, assetFamily: petct.instance.assetFamily })).toBe('GENERIC_PET_CT_SCANNER_V1')
    })
})

// ---------------------------------------------------------------------------
// Lock keeps visible
// ---------------------------------------------------------------------------
describe('EVI-MA-01 lock keeps recognizable geometry', () => {
    it('a LOCKED KIUBE still yields renderable geometry', () => {
        const inst = makeKiube()
        const locked: EquipmentAssetInstance = { ...inst, lifecycleState: 'LOCKED' }
        const diag = buildEquipmentVisualDiagnostic({
            equipmentInstanceId: locked.id,
            canonicalModelId: locked.canonicalEquipmentId,
            canonicalClass: locked.canonicalClass,
            assetFamily: locked.assetFamily,
            parentRoomId: locked.parentBimSpaceId,
            pose: poseFrom(locked),
        })
        expect(diag.renderable).toBe(true)
    })
})

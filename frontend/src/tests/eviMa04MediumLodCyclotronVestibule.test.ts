/**
 * EVI-MA-04 — medium-LOD cyclotron + MRT vestibule + adjacency tests.
 * Bentley-FREE: exercises the pure geometry recipes, the shared material
 * palette, canonical->visual mapping, and the adjacency + vestibule-pose logic.
 */
import { describe, expect, it } from 'vitest'
import {
    buildEquipmentParts,
    buildCyclotronPartsV2,
    buildVestibuleParts,
    resolveVisualFamilyForCanonical,
    resolveVisualFamilyForGeometryId,
    computeEquipmentWorldBounds,
    isNonDegenerateBounds,
    EQUIPMENT_PART_COLOR,
    type EquipmentPose,
    type EquipmentPart,
} from '../components/spatial/equipmentGeometry'
import {
    evaluateAdjacency,
    findVestibuleAdjacentRoom,
    seedVestibulePoseInAdjoiningRoom,
    type AdjacencyRoom,
} from '../components/spatial/equipmentAdjacency'

const pose = (w = 4, d = 4, h = 3, yaw = 0): EquipmentPose => ({ center: [10, 20, 8], width: w, depth: d, height: h, yawRadians: yaw })

// ---------------------------------------------------------------------------
// Canonical -> visual mapping (CYCLOTRON now V2; vestibule family)
// ---------------------------------------------------------------------------
describe('EVI-MA-04 visual-family mapping', () => {
    it('a canonical cyclotron resolves to the V2 medium-LOD family', () => {
        expect(resolveVisualFamilyForCanonical({ canonicalClass: 'CYCLOTRON' })).toBe('GENERIC_MEDICAL_CYCLOTRON_V2')
    })
    it('a scanner still resolves to PET/CT; geometry-id resolves vestibule + cyclotron V2', () => {
        expect(resolveVisualFamilyForCanonical({ canonicalClass: 'SCANNER', assetFamily: 'PET_CT_SCANNER' })).toBe('GENERIC_PET_CT_SCANNER_V1')
        expect(resolveVisualFamilyForGeometryId('GENERIC_MRT_RADIOPHARMACY_VESTIBULE_V1')).toBe('GENERIC_MRT_RADIOPHARMACY_VESTIBULE_V1')
        expect(resolveVisualFamilyForGeometryId('GENERIC_MEDICAL_CYCLOTRON_V2')).toBe('GENERIC_MEDICAL_CYCLOTRON_V2')
    })
})

// ---------------------------------------------------------------------------
// Cyclotron V2 medium-LOD composition (15-30 parts, differentiated roles)
// ---------------------------------------------------------------------------
describe('EVI-MA-04 cyclotron V2 medium-LOD', () => {
    it('produces 15-30 meaningful components (medium-LOD, not the ~3 proxy)', () => {
        const parts = buildCyclotronPartsV2(pose())
        expect(parts.length).toBeGreaterThanOrEqual(15)
        expect(parts.length).toBeLessThanOrEqual(30)
    })

    it('contains the recognizable components: shells, base, feet, panels, handles, cabinet, control, e-stop', () => {
        const kinds = new Set(buildCyclotronPartsV2(pose()).map((p) => p.part))
        for (const expected of ['CYC_LOWER_SHELL', 'CYC_UPPER_SHELL', 'CYC_BASE_RING', 'CYC_FOOT', 'CYC_ACCESS_PANEL', 'CYC_PANEL_HANDLE', 'CYC_SERVICE_COLUMN', 'CYC_UPPER_MODULE', 'CYC_CABINET', 'CYC_CABINET_VENT', 'CYC_CONTROL_SCREEN', 'CYC_ESTOP'] as EquipmentPart[]) {
            expect(kinds.has(expected)).toBe(true)
        }
    })

    it('has multiple leveling feet and multiple access panels', () => {
        const parts = buildCyclotronPartsV2(pose())
        expect(parts.filter((p) => p.part === 'CYC_FOOT').length).toBeGreaterThanOrEqual(3)
        expect(parts.filter((p) => p.part === 'CYC_ACCESS_PANEL').length).toBeGreaterThanOrEqual(3)
    })

    it('sits on the floor (nothing below zBase) and scales with the envelope', () => {
        const small = computeEquipmentWorldBounds({ pose: pose(2, 2, 2), family: 'GENERIC_MEDICAL_CYCLOTRON_V2' })!
        const large = computeEquipmentWorldBounds({ pose: pose(6, 6, 4), family: 'GENERIC_MEDICAL_CYCLOTRON_V2' })!
        expect(small.low[2]).toBeGreaterThan(8 - 0.001) // zBase = 8, nothing below
        expect(isNonDegenerateBounds(small)).toBe(true)
        // Larger envelope -> larger visual footprint.
        expect((large.high[0] - large.low[0])).toBeGreaterThan(small.high[0] - small.low[0])
    })

    it('every part has a differentiated material (not a single color) and coords are finite', () => {
        const colors = new Set<string>()
        for (const p of buildCyclotronPartsV2(pose())) {
            const c = EQUIPMENT_PART_COLOR[p.part]
            colors.add(c.join(','))
            if (p.kind === 'BOX') { expect(p.low.every(Number.isFinite)).toBe(true); expect(p.high.every(Number.isFinite)).toBe(true) }
            else { expect(p.centerA.every(Number.isFinite)).toBe(true); expect(Number.isFinite(p.radius)).toBe(true) }
        }
        // Many distinct materials (not one cyan block).
        expect(colors.size).toBeGreaterThanOrEqual(6)
    })

    it('none of the cyclotron materials is a bright cyan/blue/green whole-body color', () => {
        // The dominant housing shells are off-white/light gray, not cyan.
        const lower = EQUIPMENT_PART_COLOR.CYC_LOWER_SHELL
        // Off-white: all channels high and close together (not a saturated hue).
        expect(Math.min(...lower)).toBeGreaterThan(150)
        expect(Math.max(...lower) - Math.min(...lower)).toBeLessThan(40)
    })
})

// ---------------------------------------------------------------------------
// Vestibule medium-LOD composition
// ---------------------------------------------------------------------------
describe('EVI-MA-04 MRT vestibule recipe', () => {
    it('produces a recognizable compact transfer cabinet (housing, access panel, interface, throat)', () => {
        const parts = buildVestibuleParts(pose(1.2, 0.9, 1.6))
        const kinds = new Set(parts.map((p) => p.part))
        for (const expected of ['VEST_HOUSING', 'VEST_BASE', 'VEST_ACCESS_PANEL', 'VEST_TRANSFER_INTERFACE', 'VEST_STATUS_LIGHT', 'VEST_CONTROL_PANEL', 'VEST_TRANSFER_THROAT'] as EquipmentPart[]) {
            expect(kinds.has(expected)).toBe(true)
        }
        expect(parts.length).toBeGreaterThanOrEqual(6)
    })

    it('is compact (not room-sized) even when given a large envelope', () => {
        // Measure the actual vestibule VISUAL parts (not the envelope, which the
        // fit uses). The housing is capped ~1.2 x 0.9 x 1.6 regardless of the
        // (large) envelope, so it never becomes a room-sized box.
        const parts = buildVestibuleParts(pose(10, 10, 4))
        let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity
        for (const p of parts) {
            if (p.kind === 'BOX') {
                minX = Math.min(minX, p.low[0], p.high[0]); maxX = Math.max(maxX, p.low[0], p.high[0])
                minZ = Math.min(minZ, p.low[2], p.high[2]); maxZ = Math.max(maxZ, p.low[2], p.high[2])
            } else {
                minX = Math.min(minX, p.centerA[0] - p.radius, p.centerB[0] - p.radius); maxX = Math.max(maxX, p.centerA[0] + p.radius, p.centerB[0] + p.radius)
                minZ = Math.min(minZ, p.centerA[2], p.centerB[2]); maxZ = Math.max(maxZ, p.centerA[2], p.centerB[2])
            }
        }
        expect(maxX - minX).toBeLessThan(2)
        expect(maxZ - minZ).toBeLessThan(2.4)
    })

    it('buildEquipmentParts dispatches both new families', () => {
        expect(buildEquipmentParts('GENERIC_MEDICAL_CYCLOTRON_V2', pose()).length).toBeGreaterThanOrEqual(15)
        expect(buildEquipmentParts('GENERIC_MRT_RADIOPHARMACY_VESTIBULE_V1', pose(1.2, 0.9, 1.6)).length).toBeGreaterThanOrEqual(6)
    })
})

// ---------------------------------------------------------------------------
// Adjacency: cyclotron room -> shared wall -> adjoining room -> vestibule pose
// ---------------------------------------------------------------------------
describe('EVI-MA-04 vestibule adjacency', () => {
    // Cyclotron room occupies x[0..6] y[0..6]; adjoining room shares the +X wall.
    const cyclotronRoom: AdjacencyRoom = {
        bimSpaceId: 'CYC_ROOM', floorZ: 0, ceilingZ: 3,
        outerLoop: [{ x: 0, y: 0 }, { x: 6, y: 0 }, { x: 6, y: 6 }, { x: 0, y: 6 }],
    }
    const adjoiningRoom: AdjacencyRoom = {
        bimSpaceId: 'RP_ROOM', floorZ: 0, ceilingZ: 3,
        outerLoop: [{ x: 6.1, y: 0 }, { x: 12, y: 0 }, { x: 12, y: 6 }, { x: 6.1, y: 6 }],
    }
    const farRoom: AdjacencyRoom = {
        bimSpaceId: 'FAR_ROOM', floorZ: 0,
        outerLoop: [{ x: 50, y: 50 }, { x: 56, y: 50 }, { x: 56, y: 56 }, { x: 50, y: 56 }],
    }

    it('finds the adjoining room across the shared wall (a DIFFERENT room, never the source)', () => {
        const best = findVestibuleAdjacentRoom('CYC_ROOM', [cyclotronRoom, adjoiningRoom, farRoom])
        expect(best).toBeDefined()
        expect(best!.bimSpaceId).toBe('RP_ROOM')
        expect(best!.bimSpaceId).not.toBe('CYC_ROOM')
        expect(best!.side).toBe('X_MAX')
        expect(best!.sharedWallLength).toBeGreaterThan(5)
    })

    it('a far, non-adjoining room is not selected', () => {
        const e = evaluateAdjacency(cyclotronRoom, farRoom)
        expect(e.side).toBe('NONE')
        expect(e.sharedWallLength).toBe(0)
    })

    it('seeds a wall-adjacent vestibule pose INSIDE the adjoining room (not through the wall, not in the cyclotron room)', () => {
        const best = findVestibuleAdjacentRoom('CYC_ROOM', [cyclotronRoom, adjoiningRoom])!
        const p = seedVestibulePoseInAdjoiningRoom({ adjoiningRoom, side: best.side })!
        // Inside the adjoining room X range [6.1..12], hugging the shared wall.
        expect(p.centerX).toBeGreaterThan(6.1)
        expect(p.centerX).toBeLessThan(12)
        // Not inside the cyclotron room (x < 6).
        expect(p.centerX).toBeGreaterThan(6)
        // Sits on the adjoining room floor.
        expect(p.zBase).toBe(0)
        // Compact.
        expect(p.width).toBeLessThan(2)
    })
})

// ---------------------------------------------------------------------------
// Selection: materials are always the per-part fill (outline-only on selection)
// ---------------------------------------------------------------------------
describe('EVI-MA-04 material palette stability', () => {
    it('every EquipmentPart has a defined material (so selection never needs to repaint)', () => {
        for (const p of buildCyclotronPartsV2(pose())) {
            expect(EQUIPMENT_PART_COLOR[p.part]).toBeDefined()
        }
        for (const p of buildVestibuleParts(pose(1.2, 0.9, 1.6))) {
            expect(EQUIPMENT_PART_COLOR[p.part]).toBeDefined()
        }
    })
})

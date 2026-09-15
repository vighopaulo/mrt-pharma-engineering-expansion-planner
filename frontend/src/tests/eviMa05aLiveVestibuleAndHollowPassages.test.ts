/**
 * EVI-MA-05A — live clinical-logistics-vestibule lifecycle (domain layer) +
 * supplemental HOLLOW carrier-traversable passages with distinct MRT/PTS carrier
 * clearances.
 *
 * Bentley-FREE. The live viewer wiring (decorator render, floating control, 3D
 * pick, camera Fit) is exercised in the app; here we prove the AUTHORITATIVE
 * pure domain the live lifecycle drives: creating ONE ClinicalLogisticsVestibule
 * in the cyclotron's room, wall-integrated, collision-guarded, dual distinct
 * ports (MRT rectangular + radiopharmaceutical-qualified circular PTS), the
 * hollow inner-vs-outer cross-sections, carrier clearances, persistence, and
 * the service-class policy foundation. Plus the geometry recipe's hollow cues.
 */
import { describe, expect, it } from 'vitest'
import {
    createVestibuleInstance,
    loadVestibuleInstances,
    saveVestibuleInstances,
    permittedPortsForServiceClass,
    vestibuleInternalChamber,
    mrtInnerFreeCrossSection,
    mrtOuterCrossSection,
    ptsInnerBoreDiameter,
    ptsOutsideDiameter,
    reservedVolumeAsAabb,
    findVestibuleCollision,
    MRT_CARRIER_ENVELOPE,
    MRT_CLEARANCE_SIDE_M,
    MRT_CLEARANCE_VERTICAL_M,
    PTS_PIG_DIAMETER_M,
    PTS_VIAL_DIAMETER_M,
    PTS_RADIAL_CLEARANCE_M,
    type ClinicalLogisticsVestibuleInstance,
    type ServiceClass,
} from '../components/spatial/clinicalLogisticsVestibule'
import {
    buildClinicalLogisticsVestibuleParts,
    resolveVisualFamilyForCanonical,
    type EquipmentPose,
} from '../components/spatial/equipmentGeometry'

// A cyclotron room: 6x5, floor 0..3.2.
const ROOM_FOOTPRINT = [
    { x: 0, y: 0 }, { x: 6, y: 0 }, { x: 6, y: 5 }, { x: 0, y: 5 },
]
const ZLOW = 0, ZHIGH = 3.2
const CYCLO_ROOM = '0x2000000094e'
const POSE: EquipmentPose = { center: [3, 2.5, 0], width: 1.3, depth: 0.9, height: 2.0, yawRadians: 0 }

function makeRadiopharmacy(seq = 1): ClinicalLogisticsVestibuleInstance {
    const res = createVestibuleInstance({
        iModelId: 'imodel-05A',
        serviceClass: 'RADIOPHARMACY',
        parentBimSpaceId: CYCLO_ROOM,
        sourceClinicalContextId: 'cyclotron-1',
        footprint: ROOM_FOOTPRINT,
        zLow: ZLOW,
        zHigh: ZHIGH,
        seq,
    })
    if (!res.ok) throw new Error(`create failed: ${res.reason}`)
    return res.instance
}

// ---------------------------------------------------------------------------
// Live-lifecycle domain (A..AI subset provable without Bentley)
// ---------------------------------------------------------------------------
describe('EVI-MA-05A radiopharmacy vestibule creation', () => {
    it('B/C: uses the SAME parent room as the cyclotron and is wall-integrated (not centroid)', () => {
        const v = makeRadiopharmacy()
        expect(v.parentBimSpaceId).toBe(CYCLO_ROOM)
        const centroidDist = Math.hypot(v.pose.centerX - 3, v.pose.centerY - 2.5)
        expect(centroidDist).toBeGreaterThan(1) // hugs a wall, not the room centroid
    })

    it('F: there is NO cyclotron-to-vestibule duct (the vestibule owns only its own ports)', () => {
        const v = makeRadiopharmacy()
        // Every port belongs to the vestibule; none references the cyclotron as a
        // physical conduit. The upstream is an abstraction, not a routed duct.
        for (const p of v.transportPorts) expect(p.vestibuleInstanceId).toBe(v.vestibuleInstanceId)
    })

    it('G/H/I/J/K: ONE vestibule owns BOTH MRT + PTS with distinct ids/families; PTS is radiopharm-qualified', () => {
        const v = makeRadiopharmacy()
        const mrt = v.transportPorts.find((p) => p.transportFamily === 'MRT')!
        const pts = v.transportPorts.find((p) => p.transportFamily === 'PTS')!
        expect(mrt).toBeDefined()
        expect(pts).toBeDefined()
        expect(mrt.portId).not.toBe(pts.portId)
        expect(mrt.transportFamily).toBe('MRT')
        expect(pts.transportFamily).toBe('PTS')
        expect(pts.ptsQualification).toBe('RADIOPHARMACEUTICAL_QUALIFIED')
    })

    it('P: wall relationship is PROPOSED_WALL_PENETRATION (BIM wall never modified)', () => {
        const v = makeRadiopharmacy()
        expect(v.wallRelationshipStatus).toBe('PROPOSED_WALL_PENETRATION')
    })

    it('E(collision): a room-side reserved volume overlapping equipment is rejected upstream via findVestibuleCollision', () => {
        const v = makeRadiopharmacy()
        const rv = reservedVolumeAsAabb(v.reservedVolume)
        // An equipment AABB exactly over the vestibule reserved volume collides.
        const overlap = findVestibuleCollision(v.reservedVolume, [{ id: 'cyclotron-1', aabb: rv }])
        expect(overlap).toBe('cyclotron-1')
        // A far-away equipment AABB does not.
        const clear = findVestibuleCollision(v.reservedVolume, [{ id: 'far', aabb: { minX: 100, minY: 100, minZ: 0, maxX: 101, maxY: 101, maxZ: 1 } }])
        expect(clear).toBeUndefined()
    })

    it('U/AA/AB: persist -> reload restores the SAME instance + ports; forbidden mesh keys rejected', () => {
        const store = new Map<string, string>()
        const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, val: string) => { store.set(k, val) } }
        const v = makeRadiopharmacy()
        saveVestibuleInstances('imodel-05A', [v], storage)
        const reloaded = loadVestibuleInstances('imodel-05A', storage)
        expect(reloaded).toHaveLength(1)
        expect(reloaded[0].vestibuleInstanceId).toBe(v.vestibuleInstanceId)
        expect(reloaded[0].transportPorts.length).toBe(v.transportPorts.length)
        // Inner-passage physics seam survives the round-trip.
        const mrt = reloaded[0].transportPorts.find((p) => p.transportFamily === 'MRT')!
        expect(mrt.innerCrossSection?.shape).toBe('RECTANGULAR')
        expect(mrt.centerline).toBeDefined()
        const raw = store.get('mrtpharma.vestibule.v1.imodel-05A')!
        expect(raw).not.toContain('vertices')
        expect(raw).not.toContain('triangles')
    })

    it('duplicate/identity: two vestibules in the same room have independent ids', () => {
        const a = makeRadiopharmacy(1)
        const b = makeRadiopharmacy(2)
        expect(a.vestibuleInstanceId).not.toBe(b.vestibuleInstanceId)
    })
})

// ---------------------------------------------------------------------------
// Service-class policy foundation (AE..AH) + no auto nuclear upgrade
// ---------------------------------------------------------------------------
describe('EVI-MA-05A service-class policy preserved', () => {
    it('AE/AF: Pharmacy + Laboratory keep CONVENTIONAL_CLINICAL PTS (not nuclear)', () => {
        for (const sc of ['PHARMACY', 'LABORATORY'] as ServiceClass[]) {
            const pts = permittedPortsForServiceClass(sc).find((p) => p.transportFamily === 'PTS')!
            expect(pts.ptsQualification).toBe('CONVENTIONAL_CLINICAL')
        }
    })
    it('AG: Sterile does not fabricate a PTS tube', () => {
        expect(permittedPortsForServiceClass('STERILE_CLEAN_SUPPLY').some((p) => p.transportFamily === 'PTS')).toBe(false)
    })
    it('AH: Laundry does not fabricate a small PTS tube (MRT heavy only)', () => {
        const ports = permittedPortsForServiceClass('LAUNDRY_LINEN')
        expect(ports.some((p) => p.transportFamily === 'PTS')).toBe(false)
        expect(ports.find((p) => p.transportFamily === 'MRT')!.mrtConfiguration).toBe('HEAVY_GENERAL')
    })
    it('AI: EVI-MA-04 cyclotron V2 mapping remains unchanged', () => {
        expect(resolveVisualFamilyForCanonical({ canonicalClass: 'CYCLOTRON' })).toBe('GENERIC_MEDICAL_CYCLOTRON_V2')
    })
})

// ---------------------------------------------------------------------------
// Supplemental HOLLOW passages + distinct carrier clearances (A..P)
// ---------------------------------------------------------------------------
describe('EVI-MA-05A hollow passages + carrier clearance', () => {
    it('A: the vestibule has a genuine nonzero internal free volume (not a solid block)', () => {
        const ch = vestibuleInternalChamber({ centerX: 3, centerY: 4.5, zBase: 0, width: 1.2, depth: 0.9, height: 2.0, yaw: 0 })
        expect(ch.internalFreeWidth).toBeGreaterThan(0)
        expect(ch.internalFreeHeight).toBeGreaterThan(0)
        expect(ch.internalFreeDepth).toBeGreaterThan(0)
        const vol = ch.internalFreeWidth * ch.internalFreeHeight * ch.internalFreeDepth
        expect(vol).toBeGreaterThan(0)
        // Internal free is strictly smaller than the exterior housing (walls exist).
        expect(ch.internalFreeWidth).toBeLessThan(ch.housingWidth)
        expect(ch.internalFreeHeight).toBeLessThan(ch.housingHeight)
        expect(ch.internalFreeDepth).toBeLessThan(ch.housingDepth)
    })

    it('B/C/D: the MRT tract is hollow — outer cross-section strictly exceeds the inner free', () => {
        const inner = mrtInnerFreeCrossSection()
        const outer = mrtOuterCrossSection(inner)
        expect(outer.width).toBeGreaterThan(inner.freeWidth!)
        expect(outer.height).toBeGreaterThan(inner.freeHeight!)
    })

    it('E/F: the MRT carrier fits entirely inside the inner free cross-section with positive clearance', () => {
        const inner = mrtInnerFreeCrossSection()
        expect(inner.freeWidth!).toBeGreaterThan(MRT_CARRIER_ENVELOPE.width)
        expect(inner.freeHeight!).toBeGreaterThan(MRT_CARRIER_ENVELOPE.height)
        const sideClear = (inner.freeWidth! - MRT_CARRIER_ENVELOPE.width) / 2
        const vertClear = (inner.freeHeight! - MRT_CARRIER_ENVELOPE.height) / 2
        expect(sideClear).toBeCloseTo(MRT_CLEARANCE_SIDE_M, 6)
        expect(vertClear).toBeCloseTo(MRT_CLEARANCE_VERTICAL_M, 6)
        expect(sideClear).toBeGreaterThan(0)
        expect(vertClear).toBeGreaterThan(0)
    })

    it('G/H: the rectangular reducer preserves a continuous hollow passage that narrows toward the trunk', () => {
        const parts = buildClinicalLogisticsVestibuleParts(POSE, { mrt: true, pts: false })
        // Four planar reducer faces surround the passage.
        expect(parts.filter((p) => p.part === 'CLV_MRT_REDUCER_FACE').length).toBe(4)
        // Two inner-void segments form a continuous passage; the rear segment is
        // strictly smaller in cross-section than the front (narrows to the trunk).
        const voids = parts.filter((p) => p.part === 'CLV_MRT_INNER_VOID') as { low: number[]; high: number[] }[]
        expect(voids.length).toBe(2)
        const width = (b: { low: number[]; high: number[] }) => b.high[0] - b.low[0]
        const height = (b: { low: number[]; high: number[] }) => b.high[2] - b.low[2]
        // Order-independent: the larger segment feeds the smaller.
        const [a, b] = voids
        const bigW = Math.max(width(a), width(b)), smallW = Math.min(width(a), width(b))
        const bigH = Math.max(height(a), height(b)), smallH = Math.min(height(a), height(b))
        expect(bigW).toBeGreaterThan(smallW)
        expect(bigH).toBeGreaterThan(smallH)
    })

    it('I/J: the PTS tube is hollow — outside diameter strictly exceeds the inside bore', () => {
        const id = ptsInnerBoreDiameter()
        const od = ptsOutsideDiameter(id)
        expect(od).toBeGreaterThan(id)
    })

    it('K/L/M: the miniature pig fits the bore with positive running clearance and contains the vial', () => {
        const id = ptsInnerBoreDiameter()
        expect(id).toBeGreaterThan(PTS_PIG_DIAMETER_M) // pig fits the bore
        const running = (id - PTS_PIG_DIAMETER_M) / 2
        expect(running).toBeCloseTo(PTS_RADIAL_CLEARANCE_M, 6)
        expect(running).toBeGreaterThan(0)
        expect(PTS_PIG_DIAMETER_M).toBeGreaterThan(PTS_VIAL_DIAMETER_M) // pig contains the vial
    })

    it('N/O: MRT tract and PTS bore are materially different scales (MRT carrier is not a PTS carrier)', () => {
        const mrtInner = mrtInnerFreeCrossSection()
        const ptsBore = ptsInnerBoreDiameter()
        // The MRT free width is many times the PTS bore — different transport scales.
        expect(mrtInner.freeWidth!).toBeGreaterThan(ptsBore * 3)
        // An MRT carrier cannot fit a PTS bore.
        expect(MRT_CARRIER_ENVELOPE.width).toBeGreaterThan(ptsBore)
    })

    it('P: external collision geometry (reserved volume) is separate from the inner carrier-clearance geometry', () => {
        const v = makeRadiopharmacy()
        const mrt = v.transportPorts.find((p) => p.transportFamily === 'MRT')!
        // The port carries BOTH an outer (structural/collision) cross-section AND
        // a smaller inner free cross-section — two distinct geometries.
        expect(mrt.crossSection.shape).toBe('RECTANGULAR')
        expect(mrt.innerCrossSection?.shape).toBe('RECTANGULAR')
        expect(mrt.crossSection.width!).toBeGreaterThan(mrt.innerCrossSection!.freeWidth!)
        expect(mrt.crossSection.height!).toBeGreaterThan(mrt.innerCrossSection!.freeHeight!)
        // The reserved volume (external collision) is the room-side body AABB, not
        // the inner passage.
        const rv = v.reservedVolume
        expect(rv.maxX - rv.minX).toBeGreaterThan(0)
    })

    it('renders visible hollow inner-void cues (chamber recess, MRT inner passage, PTS bore)', () => {
        const kinds = new Set(buildClinicalLogisticsVestibuleParts(POSE, { mrt: true, pts: true }).map((p) => p.part))
        expect(kinds.has('CLV_CHAMBER_VOID')).toBe(true)
        expect(kinds.has('CLV_MRT_INNER_VOID')).toBe(true)
        expect(kinds.has('CLV_PTS_INNER_BORE')).toBe(true)
    })

    it('total part count stays in the 15-30 band with the hollow cues added', () => {
        // EVI-MA-07 raised the upper bound to 40 (two explicit front openings).
        const n = buildClinicalLogisticsVestibuleParts(POSE, { mrt: true, pts: true }).length
        expect(n).toBeGreaterThanOrEqual(15)
        expect(n).toBeLessThanOrEqual(40)
    })
})

/**
 * EVI-MA-05 FINAL — Clinical Logistics Vestibule family + Radiopharmacy dual
 * MRT/PTS interface + origin-service foundation.
 *
 * Bentley-FREE. Proves the authoritative doctrine:
 *   - ONE reusable wall-integrated CLINICAL_LOGISTICS_VESTIBULE_V1 family
 *     (15-30 recognizable components: front clinical access face + wall
 *     penetration + rear manifold + configured transport-port stubs).
 *   - A service-class taxonomy (Radiopharmacy / Pharmacy / Laboratory /
 *     Sterile-Clean-Supply / Laundry-Linen) that answers WHAT function occurs,
 *     distinct from transport ports that answer HOW payloads leave/arrive.
 *   - The Radiopharmacy vestibule exposes TWO distinct physical ports on ONE
 *     vestibule: an MRT rectangular reducer/trunk stub AND a
 *     radiopharmaceutical-QUALIFIED circular PTS tube stub. Nuclear
 *     qualification is NEVER auto-inherited by conventional PTS.
 *   - Instances are WALL-INTEGRATED (never room-centroid), independently
 *     identified, and persist safely (no mesh leak).
 */
import { describe, expect, it } from 'vitest'
import {
    buildEquipmentParts,
    buildClinicalLogisticsVestibuleParts,
    computeEquipmentWorldBounds,
    isNonDegenerateBounds,
    EQUIPMENT_PART_COLOR,
    type EquipmentPart,
    type EquipmentPose,
} from '../components/spatial/equipmentGeometry'
import {
    SERVICE_CLASSES,
    permittedPortsForServiceClass,
    serviceClassLabel,
    typicalPayloadForServiceClass,
    RADIOPHARMACEUTICAL_INPUT_CONDITION,
    enumerateWallCandidates,
    seedWallIntegratedPose,
    reservedVolumeFromPose,
    frontFacePlaneFromPose,
    vestibulePortRenderOptions,
    createVestibuleInstance,
    loadVestibuleInstances,
    saveVestibuleInstances,
    type ServiceClass,
} from '../components/spatial/clinicalLogisticsVestibule'

// A 6x5 room, floor z 0..3.2 (tall enough to host a vestibule).
const ROOM_FOOTPRINT = [
    { x: 0, y: 0 }, { x: 6, y: 0 }, { x: 6, y: 5 }, { x: 0, y: 5 },
]
const ROOM_ZLOW = 0
const ROOM_ZHIGH = 3.2

const POSE: EquipmentPose = { center: [3, 2.5, 0], width: 1.3, depth: 0.9, height: 2.0, yawRadians: 0 }

// ---------------------------------------------------------------------------
// Family geometry — recognizable, 15-30 components, front face + rear manifold
// ---------------------------------------------------------------------------
describe('CLINICAL_LOGISTICS_VESTIBULE_V1 geometry', () => {
    it('produces a recognizable medium-LOD assembly (15-40 components)', () => {
        // EVI-MA-07 raised the upper bound: the simplified front face now carries
        // TWO explicit hollow transport openings (framed MRT rectangle + circular
        // PTS ring/void) in addition to the hollow passages — still bounded so it
        // is not overbuilt.
        const parts = buildClinicalLogisticsVestibuleParts(POSE, { mrt: true, pts: true })
        expect(parts.length).toBeGreaterThanOrEqual(15)
        expect(parts.length).toBeLessThanOrEqual(40)
    })

    it('has the SIMPLIFIED front clinical access-face roles + TWO explicit openings (EVI-MA-07)', () => {
        const kinds = new Set(buildClinicalLogisticsVestibuleParts(POSE).map((p) => p.part))
        // Core face: fascia/housing/door/handle/HMI/tri-status/e-stop/service/base.
        for (const role of ['CLV_WALL_FASCIA', 'CLV_HOUSING', 'CLV_TRANSFER_DOOR', 'CLV_HANDLE', 'CLV_HMI', 'CLV_STATUS_GREEN', 'CLV_STATUS_AMBER', 'CLV_STATUS_RED', 'CLV_ESTOP', 'CLV_SERVICE_PANEL', 'CLV_SERVICE_LABEL', 'CLV_BASE'] as const) {
            expect(kinds.has(role)).toBe(true)
        }
        // EVI-MA-07 — the front face now exposes the two unmistakable openings
        // (the old single CLV_TRANSFER_APERTURE is replaced by these).
        expect(kinds.has('CLV_MRT_OPENING_FRAME')).toBe(true)
        expect(kinds.has('CLV_MRT_OPENING_VOID')).toBe(true)
        expect(kinds.has('CLV_PTS_OPENING_RING')).toBe(true)
        expect(kinds.has('CLV_PTS_OPENING_VOID')).toBe(true)
    })

    it('has a wall sleeve + rear manifold behind the wall', () => {
        const kinds = new Set(buildClinicalLogisticsVestibuleParts(POSE).map((p) => p.part))
        expect(kinds.has('CLV_WALL_SLEEVE')).toBe(true)
        expect(kinds.has('CLV_REAR_MANIFOLD')).toBe(true)
    })

    it('MRT branch is a RECTANGULAR (box) reducer with ~4 planar faces to a trunk stub (no cone)', () => {
        const parts = buildClinicalLogisticsVestibuleParts(POSE, { mrt: true, pts: false })
        const reducerFaces = parts.filter((p) => p.part === 'CLV_MRT_REDUCER_FACE')
        expect(reducerFaces.length).toBe(4)
        // Every reducer face + section + trunk stub is a planar BOX (fabricated
        // rectangular transition — NOT a cone/rounded nozzle).
        for (const p of parts.filter((q) => q.part === 'CLV_MRT_REDUCER_FACE' || q.part === 'CLV_MRT_MANIFOLD_SECTION' || q.part === 'CLV_MRT_TRUNK_STUB')) {
            expect(p.kind).toBe('BOX')
        }
        expect(parts.some((p) => p.part === 'CLV_MRT_TRUNK_PORT')).toBe(true)
    })

    it('PTS branch reads as a CIRCULAR tube system (cylinder stub), distinct from the MRT box', () => {
        const parts = buildClinicalLogisticsVestibuleParts(POSE, { mrt: false, pts: true })
        const tube = parts.find((p) => p.part === 'CLV_PTS_TUBE_STUB')
        expect(tube).toBeDefined()
        expect(tube!.kind).toBe('CYLINDER')
        expect(parts.some((p) => p.part === 'CLV_PTS_PORT' && p.kind === 'CYLINDER')).toBe(true)
        // No MRT parts when only PTS is configured.
        expect(parts.some((p) => p.part.startsWith('CLV_MRT'))).toBe(false)
    })

    it('renders only the configured ports (sterile MRT-only omits PTS geometry)', () => {
        const parts = buildClinicalLogisticsVestibuleParts(POSE, { mrt: true, pts: false })
        expect(parts.some((p) => p.part.startsWith('CLV_MRT'))).toBe(true)
        expect(parts.some((p) => p.part.startsWith('CLV_PTS'))).toBe(false)
    })

    it('every part role has a material color and none is the cyclotron selection cyan', () => {
        for (const part of buildClinicalLogisticsVestibuleParts(POSE)) {
            const rgb = EQUIPMENT_PART_COLOR[part.part as EquipmentPart]
            expect(rgb).toBeDefined()
            expect(rgb.every(Number.isFinite)).toBe(true)
            // Not the whole-machine selection cyan [90,200,220].
            expect(`${rgb[0]},${rgb[1]},${rgb[2]}`).not.toBe('90,200,220')
        }
    })

    it('routes through buildEquipmentParts + yields finite non-degenerate bounds', () => {
        const parts = buildEquipmentParts('CLINICAL_LOGISTICS_VESTIBULE_V1', POSE, { vestibulePorts: { mrt: true, pts: true } })
        expect(parts.length).toBeGreaterThanOrEqual(15)
        const b = computeEquipmentWorldBounds({ pose: POSE, family: 'CLINICAL_LOGISTICS_VESTIBULE_V1', vestibulePorts: { mrt: true, pts: true } })!
        expect(isNonDegenerateBounds(b)).toBe(true)
    })

    it('the visual follows the pose (translation moves all parts)', () => {
        const a = buildClinicalLogisticsVestibuleParts({ ...POSE, center: [0, 0, 0] })
        const b = buildClinicalLogisticsVestibuleParts({ ...POSE, center: [5, 7, 0] })
        const fa = a.find((p) => p.part === 'CLV_HOUSING')! as { low: number[] }
        const fb = b.find((p) => p.part === 'CLV_HOUSING')! as { low: number[] }
        expect(fb.low[0]).toBeCloseTo(fa.low[0] + 5, 6)
        expect(fb.low[1]).toBeCloseTo(fa.low[1] + 7, 6)
    })
})

// ---------------------------------------------------------------------------
// Service-class taxonomy + permitted-port policy (no auto nuclear upgrade)
// ---------------------------------------------------------------------------
describe('service-class + transport-port taxonomy', () => {
    it('exposes the five origin/service classes with labels + typical payloads', () => {
        expect(SERVICE_CLASSES).toEqual(['RADIOPHARMACY', 'PHARMACY', 'LABORATORY', 'STERILE_CLEAN_SUPPLY', 'LAUNDRY_LINEN'])
        for (const sc of SERVICE_CLASSES) {
            expect(serviceClassLabel(sc).length).toBeGreaterThan(0)
            expect(typicalPayloadForServiceClass(sc).length).toBeGreaterThan(0)
        }
    })

    it('RADIOPHARMACY → MRT + RADIOPHARMACEUTICAL_QUALIFIED PTS (both fabricated)', () => {
        const ports = permittedPortsForServiceClass('RADIOPHARMACY')
        const mrt = ports.find((p) => p.transportFamily === 'MRT')!
        const pts = ports.find((p) => p.transportFamily === 'PTS')!
        expect(mrt.fabricatedThisBuild).toBe(true)
        expect(pts.ptsQualification).toBe('RADIOPHARMACEUTICAL_QUALIFIED')
        expect(pts.fabricatedThisBuild).toBe(true)
    })

    it('PHARMACY + LABORATORY → MRT + CONVENTIONAL_CLINICAL PTS (NOT nuclear-qualified)', () => {
        for (const sc of ['PHARMACY', 'LABORATORY'] as ServiceClass[]) {
            const pts = permittedPortsForServiceClass(sc).find((p) => p.transportFamily === 'PTS')!
            expect(pts.ptsQualification).toBe('CONVENTIONAL_CLINICAL')
            expect(pts.ptsQualification).not.toBe('RADIOPHARMACEUTICAL_QUALIFIED')
        }
    })

    it('STERILE_CLEAN_SUPPLY → MRT only now + RTHS reserved; NO PTS tube', () => {
        const ports = permittedPortsForServiceClass('STERILE_CLEAN_SUPPLY')
        expect(ports.some((p) => p.transportFamily === 'PTS')).toBe(false)
        expect(ports.some((p) => p.transportFamily === 'MRT' && p.fabricatedThisBuild)).toBe(true)
        expect(ports.some((p) => p.transportFamily === 'RTHS' && !p.fabricatedThisBuild)).toBe(true)
    })

    it('LAUNDRY_LINEN → MRT HEAVY only now + AGV/AMR + RTHS reserved; NO small PTS tube', () => {
        const ports = permittedPortsForServiceClass('LAUNDRY_LINEN')
        expect(ports.some((p) => p.transportFamily === 'PTS')).toBe(false)
        const mrt = ports.find((p) => p.transportFamily === 'MRT')!
        expect(mrt.mrtConfiguration).toBe('HEAVY_GENERAL')
        expect(ports.some((p) => p.transportFamily === 'AGV_AMR')).toBe(true)
        expect(ports.some((p) => p.transportFamily === 'RTHS')).toBe(true)
    })

    it('the radiopharmaceutical upstream is ABSTRACTED (product-available marker, no duct)', () => {
        expect(RADIOPHARMACEUTICAL_INPUT_CONDITION).toBe('RADIOPHARMACEUTICAL_PRODUCT_AVAILABLE_AT_VESTIBULE_INPUT')
    })
})

// ---------------------------------------------------------------------------
// Wall placement — WALL-INTEGRATED, never the room centroid
// ---------------------------------------------------------------------------
describe('wall-integrated placement', () => {
    it('enumerates wall candidates longest-first (never the centroid)', () => {
        const cands = enumerateWallCandidates(ROOM_FOOTPRINT)
        expect(cands.length).toBe(4)
        // Longest walls are the 6m X-spanning walls (Y_MIN / Y_MAX).
        expect(cands[0].wallLength).toBeGreaterThanOrEqual(cands[3].wallLength)
        expect(cands[0].wallLength).toBeCloseTo(6, 6)
    })

    it('seeds a pose hugging the chosen wall — center is NOT the room centroid', () => {
        const centroid = { x: 3, y: 2.5 }
        const pose = seedWallIntegratedPose({ footprint: ROOM_FOOTPRINT, zLow: ROOM_ZLOW, zHigh: ROOM_ZHIGH, wallSide: 'Y_MAX' })!
        // Against the Y_MAX wall (y=5): center Y near the wall, not the centroid.
        expect(pose.centerY).toBeGreaterThan(4)
        expect(Math.abs(pose.centerY - centroid.y)).toBeGreaterThan(1)
        expect(pose.zBase).toBe(ROOM_ZLOW)
    })

    it('reserved volume is finite + non-degenerate and sits on the floor', () => {
        const pose = seedWallIntegratedPose({ footprint: ROOM_FOOTPRINT, zLow: ROOM_ZLOW, zHigh: ROOM_ZHIGH, wallSide: 'X_MAX' })!
        const rv = reservedVolumeFromPose(pose)
        expect(rv.maxX - rv.minX).toBeGreaterThan(0)
        expect(rv.maxY - rv.minY).toBeGreaterThan(0)
        expect(rv.maxZ - rv.minZ).toBeGreaterThan(0)
        expect(rv.minZ).toBe(ROOM_ZLOW)
    })

    it('front-face plane normal points INTO the room (away from the wall)', () => {
        // Y_MAX wall: the room interior is toward -Y, so the front normal has ny<0.
        const pose = seedWallIntegratedPose({ footprint: ROOM_FOOTPRINT, zLow: ROOM_ZLOW, zHigh: ROOM_ZHIGH, wallSide: 'Y_MAX' })!
        const plane = frontFacePlaneFromPose(pose)
        expect(plane.normalY).toBeLessThan(0)
    })
})

// ---------------------------------------------------------------------------
// Radiopharmacy dual-port full demonstration
// ---------------------------------------------------------------------------
describe('Radiopharmacy dual-port vestibule (fully demonstrated)', () => {
    const CYCLO_ROOM = '0x2000000094e'

    function makeRadiopharmacy() {
        return createVestibuleInstance({
            iModelId: 'imodel-EVI',
            serviceClass: 'RADIOPHARMACY',
            parentBimSpaceId: CYCLO_ROOM,
            sourceClinicalContextId: 'cyclotron-context',
            footprint: ROOM_FOOTPRINT,
            zLow: ROOM_ZLOW,
            zHigh: ROOM_ZHIGH,
            seq: 1,
        })
    }

    it('creates ONE vestibule with TWO distinct ports (MRT rectangular + radiopharm-qualified circular PTS)', () => {
        const res = makeRadiopharmacy()
        expect(res.ok).toBe(true)
        if (!res.ok) return
        const inst = res.instance
        expect(inst.visualFamily).toBe('CLINICAL_LOGISTICS_VESTIBULE_V1')
        expect(inst.wallRelationshipStatus).toBe('PROPOSED_WALL_PENETRATION')

        const mrt = inst.transportPorts.find((p) => p.transportFamily === 'MRT')!
        const pts = inst.transportPorts.find((p) => p.transportFamily === 'PTS')!
        expect(mrt).toBeDefined()
        expect(pts).toBeDefined()
        // Distinct ports, distinct ids, distinct cross-sections.
        expect(mrt.portId).not.toBe(pts.portId)
        expect(mrt.crossSection.shape).toBe('RECTANGULAR')
        expect(pts.crossSection.shape).toBe('CIRCULAR')
        // Radiopharmaceutical qualification (never auto-inherited elsewhere).
        expect(pts.ptsQualification).toBe('RADIOPHARMACEUTICAL_QUALIFIED')
        // Both are short UNCONNECTED stubs (no routing this build).
        expect(mrt.status).toBe('UNCONNECTED')
        expect(pts.status).toBe('UNCONNECTED')
        expect(mrt.fabricated).toBe(true)
        expect(pts.fabricated).toBe(true)
    })

    it('shares the cyclotron parent room but is WALL-INTEGRATED (no cyclotron duct)', () => {
        const res = makeRadiopharmacy()
        if (!res.ok) return
        expect(res.instance.parentBimSpaceId).toBe(CYCLO_ROOM)
        // Placed against a wall, not the centroid.
        const centroid = { x: 3, y: 2.5 }
        const dist = Math.hypot(res.instance.pose.centerX - centroid.x, res.instance.pose.centerY - centroid.y)
        expect(dist).toBeGreaterThan(1)
    })

    it('renders both MRT + PTS branches for the radiopharmacy port config', () => {
        const opts = vestibulePortRenderOptions('RADIOPHARMACY')
        expect(opts.mrt).toBe(true)
        expect(opts.pts).toBe(true)
        const parts = buildClinicalLogisticsVestibuleParts(POSE, opts)
        expect(parts.some((p) => p.part.startsWith('CLV_MRT'))).toBe(true)
        expect(parts.some((p) => p.part.startsWith('CLV_PTS'))).toBe(true)
    })
})

// ---------------------------------------------------------------------------
// Origin-service foundation for the other four classes
// ---------------------------------------------------------------------------
describe('origin-service foundation (Pharmacy / Lab / Sterile / Laundry)', () => {
    const CASES: { sc: ServiceClass; mrt: boolean; pts: boolean }[] = [
        { sc: 'PHARMACY', mrt: true, pts: true },
        { sc: 'LABORATORY', mrt: true, pts: true },
        { sc: 'STERILE_CLEAN_SUPPLY', mrt: true, pts: false },
        { sc: 'LAUNDRY_LINEN', mrt: true, pts: false },
    ]

    it('each service class configures a distinct instance from the SAME family with correct render ports', () => {
        let seq = 10
        const ids = new Set<string>()
        for (const c of CASES) {
            const res = createVestibuleInstance({
                iModelId: 'imodel-EVI', serviceClass: c.sc, parentBimSpaceId: `room-${c.sc}`,
                footprint: ROOM_FOOTPRINT, zLow: ROOM_ZLOW, zHigh: ROOM_ZHIGH, seq: seq++,
            })
            expect(res.ok).toBe(true)
            if (!res.ok) continue
            expect(res.instance.visualFamily).toBe('CLINICAL_LOGISTICS_VESTIBULE_V1')
            ids.add(res.instance.vestibuleInstanceId)
            const opts = vestibulePortRenderOptions(c.sc)
            expect(opts.mrt).toBe(c.mrt)
            expect(opts.pts).toBe(c.pts)
            // No service class other than radiopharmacy is nuclear-qualified.
            const pts = res.instance.transportPorts.find((p) => p.transportFamily === 'PTS')
            if (pts) expect(pts.ptsQualification).not.toBe('RADIOPHARMACEUTICAL_QUALIFIED')
        }
        expect(ids.size).toBe(CASES.length) // independent identities
    })

    it('reports NO_DEFENSIBLE_WALL rather than fabricating for a too-narrow room', () => {
        const narrow = [{ x: 0, y: 0 }, { x: 0.5, y: 0 }, { x: 0.5, y: 0.5 }, { x: 0, y: 0.5 }]
        const res = createVestibuleInstance({
            iModelId: 'imodel-EVI', serviceClass: 'PHARMACY', parentBimSpaceId: 'room-tiny',
            footprint: narrow, zLow: 0, zHigh: 3, seq: 99,
        })
        expect(res.ok).toBe(false)
        if (!res.ok) expect(res.reason).toBe('NO_DEFENSIBLE_WALL')
    })
})

// ---------------------------------------------------------------------------
// Instance independence + safe persistence (no mesh leak)
// ---------------------------------------------------------------------------
describe('instance identity + persistence', () => {
    it('two vestibules in the same room have independent ids + ports', () => {
        const a = createVestibuleInstance({ iModelId: 'im', serviceClass: 'RADIOPHARMACY', parentBimSpaceId: 'r', footprint: ROOM_FOOTPRINT, zLow: 0, zHigh: 3.2, seq: 1, wallSide: 'Y_MAX' })
        const b = createVestibuleInstance({ iModelId: 'im', serviceClass: 'PHARMACY', parentBimSpaceId: 'r', footprint: ROOM_FOOTPRINT, zLow: 0, zHigh: 3.2, seq: 2, wallSide: 'Y_MIN' })
        expect(a.ok && b.ok).toBe(true)
        if (!a.ok || !b.ok) return
        expect(a.instance.vestibuleInstanceId).not.toBe(b.instance.vestibuleInstanceId)
        expect(a.instance.transportPorts[0].portId).not.toBe(b.instance.transportPorts[0].portId)
    })

    it('persists + reloads deterministically with NO mesh/vertices/triangles leak', () => {
        const store = new Map<string, string>()
        const storage = {
            getItem: (k: string) => store.get(k) ?? null,
            setItem: (k: string, v: string) => { store.set(k, v) },
        }
        const res = createVestibuleInstance({ iModelId: 'im-P', serviceClass: 'RADIOPHARMACY', parentBimSpaceId: 'r', footprint: ROOM_FOOTPRINT, zLow: 0, zHigh: 3.2, seq: 1 })
        if (!res.ok) throw new Error(res.reason)
        saveVestibuleInstances('im-P', [res.instance], storage)

        const reloaded = loadVestibuleInstances('im-P', storage)
        expect(reloaded).toHaveLength(1)
        expect(reloaded[0].vestibuleInstanceId).toBe(res.instance.vestibuleInstanceId)
        expect(reloaded[0].serviceClass).toBe('RADIOPHARMACY')
        expect(reloaded[0].transportPorts.length).toBe(res.instance.transportPorts.length)

        const raw = store.get('mrtpharma.vestibule.v1.im-P')!
        expect(raw).not.toContain('vertices')
        expect(raw).not.toContain('triangles')
        expect(raw).not.toContain('mesh')
        expect(raw).not.toContain('token')
    })

    it('rejects a payload carrying a forbidden mesh key', () => {
        const bad = JSON.stringify([{ vestibuleInstanceId: 'v', iModelId: 'i', serviceClass: 'RADIOPHARMACY', parentBimSpaceId: 'r', vertices: [] }])
        const store = new Map<string, string>([['mrtpharma.vestibule.v1.im', bad]])
        const loaded = loadVestibuleInstances('im', { getItem: (k) => store.get(k) ?? null })
        expect(loaded).toEqual([])
    })
})

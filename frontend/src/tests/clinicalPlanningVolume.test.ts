import { describe, it, expect } from 'vitest'
import {
    buildOrientedPlanningPrism,
    isPointInsideClosedMesh,
    validatePlanningVolumeContainment,
    canLockVolume,
    isValidPrismParams,
    isSafeVolumePayload,
    toSafeVolumePayload,
    loadClinicalVolumes,
    saveClinicalVolumes,
    makeClinicalVolumeId,
    MIN_VOLUME_DIM,
    type PrismParams,
    type Mesh,
    type ClinicalPlanningVolume,
    type Vec3,
} from '../components/spatial/clinicalPlanningVolume'

const P = (o: Partial<PrismParams> = {}): PrismParams => ({
    centerX: 0, centerY: 0, zLow: 0, zHigh: 3, width: 4, depth: 2, yaw: 0, ...o,
})

/** A big closed box used as the "parent IfcSpace" for containment tests. */
function boxMesh(lo: Vec3, hi: Vec3): Mesh {
    const v: Vec3[] = [
        { x: lo.x, y: lo.y, z: lo.z }, { x: hi.x, y: lo.y, z: lo.z }, { x: hi.x, y: hi.y, z: lo.z }, { x: lo.x, y: hi.y, z: lo.z },
        { x: lo.x, y: lo.y, z: hi.z }, { x: hi.x, y: lo.y, z: hi.z }, { x: hi.x, y: hi.y, z: hi.z }, { x: lo.x, y: hi.y, z: hi.z },
    ]
    const t = [0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 1, 2, 6, 1, 6, 5, 2, 3, 7, 2, 7, 6, 3, 0, 4, 3, 4, 7]
    return { vertices: v, triangles: t }
}

const PARENT = boxMesh({ x: -20, y: 25, z: 0 }, { x: 0, y: 35, z: 4.5 })

describe('§52 zero-yaw prism', () => {
    it('produces 8 world vertices, 12 triangles, correct dims', () => {
        const g = buildOrientedPlanningPrism(P({ centerX: -10, centerY: 30, width: 4, depth: 2, zLow: 0, zHigh: 3 }))
        expect(g.vertices).toHaveLength(8)
        expect(g.triangles).toHaveLength(36)
        const xs = g.vertices.map((v) => v.x), ys = g.vertices.map((v) => v.y), zs = g.vertices.map((v) => v.z)
        expect(Math.max(...xs) - Math.min(...xs)).toBeCloseTo(4, 6)
        expect(Math.max(...ys) - Math.min(...ys)).toBeCloseTo(2, 6)
        expect(Math.min(...zs)).toBeCloseTo(0, 6)
        expect(Math.max(...zs)).toBeCloseTo(3, 6)
        expect(g.interiorAnchor).toEqual({ x: -10, y: 30, z: 1.5 })
    })
})

describe('§53 rotated prism', () => {
    it('yaw=37° rotates world vertices while preserving dimensions', () => {
        const yaw = (37 * Math.PI) / 180
        const g = buildOrientedPlanningPrism(P({ width: 4, depth: 2, yaw }))
        // Edge 0->1 length is the width (4); edge 1->2 length is the depth (2).
        const d01 = Math.hypot(g.vertices[1].x - g.vertices[0].x, g.vertices[1].y - g.vertices[0].y)
        const d12 = Math.hypot(g.vertices[2].x - g.vertices[1].x, g.vertices[2].y - g.vertices[1].y)
        expect(d01).toBeCloseTo(4, 6)
        expect(d12).toBeCloseTo(2, 6)
        // Not axis-aligned: edge 0->1 has both x and y components.
        expect(Math.abs(g.vertices[1].x - g.vertices[0].x)).toBeGreaterThan(0.1)
        expect(Math.abs(g.vertices[1].y - g.vertices[0].y)).toBeGreaterThan(0.1)
    })
})

describe('§54 camera invariance (pure — no camera parameter exists)', () => {
    it('same params always yield identical world geometry', () => {
        const p = P({ centerX: -10, centerY: 30, yaw: 0.5 })
        const a = buildOrientedPlanningPrism(p)
        const b = buildOrientedPlanningPrism(p)
        expect(b.vertices).toEqual(a.vertices)
        expect(b.footprint).toEqual(a.footprint)
        expect(b.interiorAnchor).toEqual(a.interiorAnchor)
    })
})

describe('§58 dimension validation', () => {
    it('rejects width<=0, depth<=0, zHigh<=zLow, non-finite', () => {
        expect(isValidPrismParams(P({ width: 0 }))).toBe(false)
        expect(isValidPrismParams(P({ depth: -1 }))).toBe(false)
        expect(isValidPrismParams(P({ zLow: 3, zHigh: 3 }))).toBe(false)
        expect(isValidPrismParams(P({ yaw: NaN }))).toBe(false)
        expect(isValidPrismParams(P())).toBe(true)
    })
    it('MIN_VOLUME_DIM is a small numerical-stability bound', () => {
        expect(MIN_VOLUME_DIM).toBeGreaterThan(0)
        expect(MIN_VOLUME_DIM).toBeLessThan(1)
    })
})

describe('§20 point-in-closed-mesh', () => {
    it('center inside, far point outside', () => {
        expect(isPointInsideClosedMesh({ x: -10, y: 30, z: 2 }, PARENT)).toBe(true)
        expect(isPointInsideClosedMesh({ x: 100, y: 100, z: 2 }, PARENT)).toBe(false)
        expect(isPointInsideClosedMesh({ x: -10, y: 30, z: 10 }, PARENT)).toBe(false)
    })
})

describe('§60 prism fully inside parent', () => {
    it('contained = YES', () => {
        const r = validatePlanningVolumeContainment({ params: P({ centerX: -10, centerY: 30, width: 4, depth: 2, zLow: 0.2, zHigh: 3 }), parentMesh: PARENT })
        expect(r.contained).toBe(true)
        expect(r.failedSamples).toBe(0)
    })
})

describe('§61 corner outside parent', () => {
    it('contained = NO when prism exceeds parent bounds', () => {
        const r = validatePlanningVolumeContainment({ params: P({ centerX: -1, centerY: 34, width: 6, depth: 6, zLow: 0.2, zHigh: 3 }), parentMesh: PARENT })
        expect(r.contained).toBe(false)
        expect(r.failedSamples).toBeGreaterThan(0)
    })
})

describe('§63 rotated prism containment uses world geometry', () => {
    it('a rotated prism that fits stays contained; over-rotated one that pokes out fails', () => {
        const fits = validatePlanningVolumeContainment({ params: P({ centerX: -10, centerY: 30, width: 3, depth: 3, yaw: Math.PI / 4, zLow: 0.2, zHigh: 3 }), parentMesh: PARENT })
        expect(fits.contained).toBe(true)
        // A long thin prism rotated so its length pokes past the parent's short axis.
        const pokes = validatePlanningVolumeContainment({ params: P({ centerX: -10, centerY: 30, width: 18, depth: 1, yaw: Math.PI / 2, zLow: 0.2, zHigh: 3 }), parentMesh: PARENT })
        expect(pokes.contained).toBe(false)
    })
})

describe('§64 anchor containment', () => {
    it('interior anchor lies inside both prism and parent', () => {
        const params = P({ centerX: -10, centerY: 30, width: 4, depth: 2, zLow: 0.2, zHigh: 3 })
        const g = buildOrientedPlanningPrism(params)
        expect(isPointInsideClosedMesh(g.interiorAnchor, PARENT)).toBe(true)
    })
})

describe('§65/§66/§67/§68 lifecycle', () => {
    const vol = (state: 'DRAFT' | 'LOCKED', params: PrismParams): ClinicalPlanningVolume => ({
        id: 'v', iModelId: 'clinic', parentBimSpaceId: '0x1', clinicalFunction: 'UPTAKE_ROOM',
        displayName: 'Uptake 01', geometryType: 'ORIENTED_RECTANGULAR_PRISM', params, lifecycleState: state, geometrySource: 'MRT_PLANNING_SUBVOLUME',
    })
    it('valid contained volume can lock', () => {
        expect(canLockVolume(vol('DRAFT', P({ centerX: -10, centerY: 30, width: 4, depth: 2, zLow: 0.2, zHigh: 3 })), PARENT).ok).toBe(true)
    })
    it('non-contained volume cannot lock', () => {
        expect(canLockVolume(vol('DRAFT', P({ centerX: -1, centerY: 34, width: 6, depth: 6, zLow: 0.2, zHigh: 3 })), PARENT).ok).toBe(false)
    })
    it('invalid dimensions cannot lock', () => {
        expect(canLockVolume(vol('DRAFT', P({ width: 0 })), PARENT).ok).toBe(false)
    })
})

describe('§70/§71 persistence + iModel scope + secret safety', () => {
    const store: Record<string, string> = {}
    const storage = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v } }
    const vol: ClinicalPlanningVolume = {
        id: makeClinicalVolumeId('clinic', '0x200000001f1', 'uptake-01'),
        iModelId: 'clinic', parentBimSpaceId: '0x200000001f1', storeyId: 'first',
        clinicalFunction: 'UPTAKE_ROOM', displayName: 'Uptake 01', geometryType: 'ORIENTED_RECTANGULAR_PRISM',
        params: P({ centerX: -10, centerY: 30, width: 4, depth: 2, zLow: 0.2, zHigh: 3, yaw: 0.4 }),
        lifecycleState: 'LOCKED', geometrySource: 'MRT_PLANNING_SUBVOLUME',
    }
    it('roundtrips the volume', () => {
        saveClinicalVolumes('clinic', [vol], storage)
        const back = loadClinicalVolumes('clinic', storage)
        expect(back).toHaveLength(1)
        expect(back[0].params).toEqual(vol.params)
        expect(back[0].lifecycleState).toBe('LOCKED')
        expect(back[0].parentBimSpaceId).toBe('0x200000001f1')
    })
    it('is not loaded under another iModel', () => {
        expect(loadClinicalVolumes('fixture', storage)).toHaveLength(0)
    })
    it('rejects secret-like or raw-geometry keys', () => {
        expect(isSafeVolumePayload([{ ...vol, accessToken: 'x' }])).toBe(false)
        expect(isSafeVolumePayload([{ ...vol, vertices: [] }])).toBe(false)
    })
    it('save omits injected secrets', () => {
        const s2: Record<string, string> = {}
        const st2 = { getItem: (k: string) => s2[k] ?? null, setItem: (k: string, v: string) => { s2[k] = v } }
        saveClinicalVolumes('clinic', [{ ...vol, accessToken: 'SECRET' } as unknown as ClinicalPlanningVolume], st2)
        expect(s2['mrtpharma.clinicalVolume.v1.clinic']).not.toContain('SECRET')
    })
    it('toSafeVolumePayload strips to the safe subset', () => {
        expect(isSafeVolumePayload(toSafeVolumePayload([vol]))).toBe(true)
    })
})

import { resolveContainmentStatus } from '../components/spatial/clinicalPlanningVolume'

describe('§21-25 containment status policy (zero-sample never equals OUTSIDE)', () => {
    it('§22 mesh available, samples>0, no failures => PASS', () => {
        expect(resolveContainmentStatus({ parentMeshAvailable: true, sampleCount: 21, failedSampleCount: 0 })).toBe('PASS')
    })
    it('§23 mesh available, samples>0, failures>0 => FAIL', () => {
        expect(resolveContainmentStatus({ parentMeshAvailable: true, sampleCount: 21, failedSampleCount: 3 })).toBe('FAIL')
    })
    it('§24 mesh available but zero samples => NOT_EVALUATED (never OUTSIDE)', () => {
        expect(resolveContainmentStatus({ parentMeshAvailable: true, sampleCount: 0, failedSampleCount: 0 })).toBe('NOT_EVALUATED')
    })
    it('§25 parent mesh missing => NOT_EVALUATED', () => {
        expect(resolveContainmentStatus({ parentMeshAvailable: false, sampleCount: 0, failedSampleCount: 0 })).toBe('NOT_EVALUATED')
        expect(resolveContainmentStatus({ parentMeshAvailable: false, sampleCount: 21, failedSampleCount: 0 })).toBe('NOT_EVALUATED')
    })
    it('the (0/0) live symptom classifies as NOT_EVALUATED, not FAIL', () => {
        expect(resolveContainmentStatus({ parentMeshAvailable: false, sampleCount: 0, failedSampleCount: 0 })).not.toBe('FAIL')
    })
})

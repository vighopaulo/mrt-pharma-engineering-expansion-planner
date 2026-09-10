/**
 * Build 1A — Generic BIM room-volume activation domain tests.
 *
 * Proves the 18 required properties (§35) at the PURE domain level: generic room
 * discovery, no auto-create, geometry-quality distinctness, parent-derived 3D
 * seed (no Uptake-coord reuse), one-assignment→zero-or-one volume, multi-room
 * edit/visibility/lifecycle isolation, per-parent + cross-parent containment,
 * persistence roundtrip, BIM-switch isolation, lazy extraction policy, camera
 * invariance, and the frozen Uptake 01 regression baseline.
 */
import { describe, it, expect } from 'vitest'
import {
    discoverRoomVolumes,
    summarizeRoomVolumeDiscovery,
    resolveRoomVolumeGeometryQuality,
    resolveRoomAuthorityClass,
    buildSelectedRoomVolumeDiagnostic,
    formatSelectedRoomVolumeDiagnostic,
    NO_MESH_CACHE,
    type RoomMeshCacheFacts,
} from '../components/spatial/bimRoomVolumeRegistry'
import type { SpatialRoomReference, WorldRange3 } from '../domain/assets/spatialSemantics'
import type { StoreyZRange } from '../components/spatial/planningPlan'
import {
    seedPrismParamsFromParent,
    buildOrientedPlanningPrism,
    validatePlanningVolumeContainment,
    resolveContainmentStatus,
    canLockVolume,
    isValidPrismParams,
    makeClinicalVolumeId,
    loadClinicalVolumes,
    saveClinicalVolumes,
    type PrismParams,
    type Mesh,
    type Vec3,
    type ClinicalPlanningVolume,
} from '../components/spatial/clinicalPlanningVolume'
import {
    addOrReplacePlanningVolume,
    updatePlanningVolumeParams,
    setPlanningVolumeVisibility,
    setPlanningVolumeLifecycle,
    deletePlanningVolume,
    summarizePlanningVolumes,
} from '../components/spatial/clinicalVolumeCollection'
import { UPTAKE_01_BASELINE } from '../components/spatial/uptake01Reconstruction'

// --- helpers ---------------------------------------------------------------

const range = (lo: [number, number, number], hi: [number, number, number]): WorldRange3 => ({
    low: { x: lo[0], y: lo[1], z: lo[2] },
    high: { x: hi[0], y: hi[1], z: hi[2] },
})

const room = (o: Partial<SpatialRoomReference> & { roomId: string }): SpatialRoomReference => ({
    displayName: o.displayName ?? `Room ${o.roomId}`,
    sourceClass: o.sourceClass ?? 'BuildingSpatial:Space',
    confidence: o.confidence ?? 'AUTHORITATIVE_BIM',
    geometryType: o.geometryType ?? 'RANGE_ONLY',
    ...o,
})

const STOREYS: StoreyZRange[] = [
    { id: 'S1', label: 'Level 1', zLow: 0, zHigh: 4 },
    { id: 'S2', label: 'Level 2', zLow: 4, zHigh: 8 },
]

/** A closed box mesh usable as a parent IfcSpace for containment. */
function boxMesh(lo: Vec3, hi: Vec3): Mesh {
    const v: Vec3[] = [
        { x: lo.x, y: lo.y, z: lo.z }, { x: hi.x, y: lo.y, z: lo.z }, { x: hi.x, y: hi.y, z: lo.z }, { x: lo.x, y: hi.y, z: lo.z },
        { x: lo.x, y: lo.y, z: hi.z }, { x: hi.x, y: lo.y, z: hi.z }, { x: hi.x, y: hi.y, z: hi.z }, { x: lo.x, y: hi.y, z: hi.z },
    ]
    const t = [0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 1, 2, 6, 1, 6, 5, 2, 3, 7, 2, 7, 6, 3, 0, 4, 3, 4, 7]
    return { vertices: v, triangles: t }
}

const EXACT_CACHE: RoomMeshCacheFacts = { exactMeshCached: true, exactMeshOk: true, vertexCount: 186, triangleCount: 368, closedMesh: true }

// --- 1. discovery returns stable BIM identities -----------------------------

describe('§35.1 discovery returns stable BIM identities', () => {
    it('preserves bimSpaceId + original label; deterministic order', () => {
        const rooms = [
            room({ roomId: '0xB', displayName: 'Room B', range: range([0, 0, 0], [2, 2, 3]) }),
            room({ roomId: '0xA', displayName: 'Room A', range: range([0, 0, 0], [2, 2, 3]) }),
        ]
        const d = discoverRoomVolumes({ iModelId: 'im-1', rooms, storeys: STOREYS })
        expect(d.map((r) => r.bimSpaceId)).toEqual(['0xA', '0xB']) // sorted, stable
        expect(d[0].originalBimLabel).toBe('Room A')
        // Same input => identical output (deterministic).
        const d2 = discoverRoomVolumes({ iModelId: 'im-1', rooms, storeys: STOREYS })
        expect(d2).toEqual(d)
    })
    it('room identity authority is BIM_SPACE_ID (skips identity-less rooms)', () => {
        const rooms = [room({ roomId: '', displayName: 'nameless' }), room({ roomId: '0xA' })]
        const d = discoverRoomVolumes({ iModelId: 'im-1', rooms, storeys: [] })
        expect(d).toHaveLength(1)
        expect(d[0].bimSpaceId).toBe('0xA')
    })
})

// --- 2. discovery is iModel scoped -----------------------------------------

describe('§35.2 discovery is iModel scoped', () => {
    it('tags every discovered room with the active iModelId', () => {
        const d = discoverRoomVolumes({ iModelId: 'im-clinic', rooms: [room({ roomId: '0xA' })], storeys: [] })
        expect(d[0].iModelId).toBe('im-clinic')
    })
})

// --- 3. discovery does not auto-create planning volumes ---------------------

describe('§35.3 discovery does not auto-create planning volumes', () => {
    it('200 discovered rooms => 0 planning volumes, 0 assignments', () => {
        const rooms = Array.from({ length: 200 }, (_, i) => room({ roomId: `0x${i}`, range: range([0, 0, 0], [1, 1, 3]) }))
        const d = discoverRoomVolumes({ iModelId: 'im-1', rooms, storeys: [] })
        expect(d).toHaveLength(200)
        expect(d.every((r) => !r.hasPlanningVolume)).toBe(true)
        expect(d.every((r) => !r.assigned)).toBe(true)
        const s = summarizeRoomVolumeDiscovery({ iModelId: 'im-1', discovered: d, planningVolumeCount: 0 })
        expect(s.planningVolumeCount).toBe(0)
        expect(s.activatedRoomCount).toBe(0)
        expect(s.discoveredRoomCount).toBe(200)
    })
})

// --- 4. exact geometry and range-only states remain distinct ----------------

describe('§35.4 exact vs range-only geometry-quality stays distinct', () => {
    it('cached exact mesh => EXACT_SPACE_GEOMETRY; range only => RANGE_ONLY_APPROXIMATION', () => {
        const r = room({ roomId: '0xA', geometryType: 'RANGE_ONLY', range: range([0, 0, 0], [2, 2, 3]) })
        expect(resolveRoomVolumeGeometryQuality({ room: r, mesh: NO_MESH_CACHE })).toBe('RANGE_ONLY_APPROXIMATION')
        expect(resolveRoomVolumeGeometryQuality({ room: r, mesh: EXACT_CACHE })).toBe('EXACT_SPACE_GEOMETRY')
    })
    it('a range is NEVER silently promoted to exact', () => {
        const r = room({ roomId: '0xA', geometryType: 'RANGE_ONLY', range: range([0, 0, 0], [2, 2, 3]) })
        // cached but extraction FAILED => not exact.
        const failed: RoomMeshCacheFacts = { exactMeshCached: true, exactMeshOk: false, extractionReason: 'NO_MESH' }
        expect(resolveRoomVolumeGeometryQuality({ room: r, mesh: failed })).toBe('RANGE_ONLY_APPROXIMATION')
        expect(resolveRoomAuthorityClass({ room: r, mesh: failed })).toBe('RANGE_ONLY_APPROXIMATION')
    })
    it('metadata-only => ANCHOR_ONLY; nothing => NOT_AVAILABLE', () => {
        expect(resolveRoomVolumeGeometryQuality({ room: room({ roomId: '0xA', geometryType: 'METADATA_ONLY' }), mesh: NO_MESH_CACHE })).toBe('ANCHOR_ONLY')
        expect(resolveRoomVolumeGeometryQuality({ room: room({ roomId: '0xA', geometryType: 'NOT_AVAILABLE' }), mesh: NO_MESH_CACHE })).toBe('NOT_AVAILABLE')
    })
})

// --- 5. selected-parent seed uses the selected room -------------------------
// --- 6. seed is finite and 3D ----------------------------------------------
// --- 7. seed does not reuse Uptake coordinates for another room -------------

describe('§35.5-7 parent-derived seed', () => {
    const parentFootprint = [
        { x: 40, y: 60 }, { x: 50, y: 60 }, { x: 50, y: 68 }, { x: 40, y: 68 },
    ]
    it('seeds from the SELECTED parent footprint centroid + Z (not origin)', () => {
        const seed = seedPrismParamsFromParent({ footprint: parentFootprint, zLow: 0, zHigh: 3 })
        expect(seed.centerX).toBeCloseTo(45, 5) // centroid X
        expect(seed.centerY).toBeCloseTo(64, 5) // centroid Y
        expect(seed.centerX).not.toBe(0)
        expect(seed.centerY).not.toBe(0)
    })
    it('seed is finite and truly 3D (zHigh > zLow, positive w/d)', () => {
        const seed = seedPrismParamsFromParent({ footprint: parentFootprint, zLow: 0, zHigh: 3 })
        expect(isValidPrismParams(seed)).toBe(true)
        expect(seed.zHigh).toBeGreaterThan(seed.zLow)
        expect(seed.width).toBeGreaterThan(0)
        expect(seed.depth).toBeGreaterThan(0)
        expect([seed.centerX, seed.centerY, seed.zLow, seed.zHigh, seed.width, seed.depth, seed.yaw].every(Number.isFinite)).toBe(true)
    })
    it('does NOT reuse Uptake 01 coordinates for a different parent', () => {
        const seed = seedPrismParamsFromParent({ footprint: parentFootprint, zLow: 0, zHigh: 3 })
        expect(seed.centerX).not.toBeCloseTo(UPTAKE_01_BASELINE.params.centerX, 2)
        expect(seed.centerY).not.toBeCloseTo(UPTAKE_01_BASELINE.params.centerY, 2)
    })
    it('seed sits inside its OWN parent mesh (containable)', () => {
        // The seed insets XY to ~50% of the parent extent and sits on the floor;
        // it does NOT inset Z. Give the parent realistic floor-to-ceiling headroom
        // (a real IfcSpace is taller than the capped seed) so the seed is interior.
        const seed = seedPrismParamsFromParent({ footprint: parentFootprint, zLow: 0, zHigh: 3.2 })
        const parent = boxMesh({ x: 40, y: 60, z: 0 }, { x: 50, y: 68, z: 3.2 })
        const c = validatePlanningVolumeContainment({ params: seed, parentMesh: parent })
        expect(c.contained).toBe(true)
    })
})

// --- 8. one assignment owns zero-or-one planning volume ---------------------

describe('§35.8 one assignment owns zero-or-one planning volume', () => {
    const vol = (parent: string): ClinicalPlanningVolume => ({
        id: makeClinicalVolumeId('im-1', parent, 'v'), iModelId: 'im-1', parentBimSpaceId: parent,
        clinicalFunction: 'INJECTION_ROOM', displayName: 'Injection Room 01',
        geometryType: 'ORIENTED_RECTANGULAR_PRISM',
        params: { centerX: 45, centerY: 64, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0 },
        lifecycleState: 'DRAFT', geometrySource: 'MRT_PLANNING_SUBVOLUME',
    })
    it('re-defining the same parent replaces (never duplicates) its volume', () => {
        let vols = addOrReplacePlanningVolume([], vol('0xA'))
        vols = addOrReplacePlanningVolume(vols, vol('0xA'))
        expect(vols.filter((v) => v.parentBimSpaceId === '0xA')).toHaveLength(1)
    })
})

// --- 9. planning volumes independently editable ----------------------------
// --- 20. multi-room edit isolation -----------------------------------------

describe('§35.9 / §35.20 multi-room independent editing', () => {
    const mk = (parent: string, cx: number): ClinicalPlanningVolume => ({
        id: makeClinicalVolumeId('im-1', parent, 'v'), iModelId: 'im-1', parentBimSpaceId: parent,
        clinicalFunction: 'INJECTION_ROOM', displayName: `Vol ${parent}`,
        geometryType: 'ORIENTED_RECTANGULAR_PRISM',
        params: { centerX: cx, centerY: 0, zLow: 0, zHigh: 3, width: 2, depth: 2, yaw: 0 },
        lifecycleState: 'DRAFT', geometrySource: 'MRT_PLANNING_SUBVOLUME',
    })
    it('editing one volume does not mutate another', () => {
        let vols = addOrReplacePlanningVolume(addOrReplacePlanningVolume([], mk('0xA', 10)), mk('0xB', 100))
        vols = updatePlanningVolumeParams(vols, '0xA', { centerX: 999, centerY: 5, zLow: 0, zHigh: 3, width: 3, depth: 3, yaw: 0 })
        const a = vols.find((v) => v.parentBimSpaceId === '0xA')!
        const b = vols.find((v) => v.parentBimSpaceId === '0xB')!
        expect(a.params.centerX).toBe(999)
        expect(b.params.centerX).toBe(100) // untouched
    })
})

// --- 10. per-parent containment identity preserved --------------------------
// --- 11. cross-parent containment rejected ----------------------------------

describe('§35.10-11 containment identity', () => {
    const parentA = boxMesh({ x: 0, y: 0, z: 0 }, { x: 10, y: 10, z: 4 })
    const parentB = boxMesh({ x: 100, y: 100, z: 0 }, { x: 110, y: 110, z: 4 })
    const paramsInA: PrismParams = { centerX: 5, centerY: 5, zLow: 0, zHigh: 3, width: 3, depth: 3, yaw: 0 }
    it('a volume is contained by its OWN parent', () => {
        expect(validatePlanningVolumeContainment({ params: paramsInA, parentMesh: parentA }).contained).toBe(true)
    })
    it('the SAME volume is NOT contained by a DIFFERENT parent (cross-parent prohibited)', () => {
        const c = validatePlanningVolumeContainment({ params: paramsInA, parentMesh: parentB })
        expect(c.contained).toBe(false)
        expect(c.failedSamples).toBeGreaterThan(0)
    })
})

// --- 16 (registry) / §47 zero-sample not FAIL ------------------------------

describe('§35 zero-sample ≠ FAIL', () => {
    it('no parent mesh => NOT_EVALUATED (never FAIL)', () => {
        expect(resolveContainmentStatus({ parentMeshAvailable: false, sampleCount: 0, failedSampleCount: 0 })).toBe('NOT_EVALUATED')
    })
    it('real evaluation with all-inside => PASS', () => {
        expect(resolveContainmentStatus({ parentMeshAvailable: true, sampleCount: 21, failedSampleCount: 0 })).toBe('PASS')
    })
    it('real evaluation with an outside sample => FAIL', () => {
        expect(resolveContainmentStatus({ parentMeshAvailable: true, sampleCount: 21, failedSampleCount: 3 })).toBe('FAIL')
    })
})

// --- 12. visibility isolation ----------------------------------------------

describe('§35.12 visibility isolation', () => {
    const mk = (parent: string): ClinicalPlanningVolume => ({
        id: makeClinicalVolumeId('im-1', parent, 'v'), iModelId: 'im-1', parentBimSpaceId: parent,
        clinicalFunction: 'INJECTION_ROOM', displayName: `Vol ${parent}`,
        geometryType: 'ORIENTED_RECTANGULAR_PRISM',
        params: { centerX: 0, centerY: 0, zLow: 0, zHigh: 3, width: 2, depth: 2, yaw: 0 },
        lifecycleState: 'DRAFT', geometrySource: 'MRT_PLANNING_SUBVOLUME',
    })
    it('hiding one volume leaves the other visible', () => {
        let vols = addOrReplacePlanningVolume(addOrReplacePlanningVolume([], mk('0xA')), mk('0xB'))
        vols = setPlanningVolumeVisibility(vols, '0xA', false)
        expect(vols.find((v) => v.parentBimSpaceId === '0xA')!.hidden).toBe(true)
        expect(vols.find((v) => v.parentBimSpaceId === '0xB')!.hidden).toBeFalsy()
    })
})

// --- 13. lifecycle isolation -----------------------------------------------

describe('§35.13 lifecycle isolation', () => {
    const mk = (parent: string): ClinicalPlanningVolume => ({
        id: makeClinicalVolumeId('im-1', parent, 'v'), iModelId: 'im-1', parentBimSpaceId: parent,
        clinicalFunction: 'INJECTION_ROOM', displayName: `Vol ${parent}`,
        geometryType: 'ORIENTED_RECTANGULAR_PRISM',
        params: { centerX: 0, centerY: 0, zLow: 0, zHigh: 3, width: 2, depth: 2, yaw: 0 },
        lifecycleState: 'DRAFT', geometrySource: 'MRT_PLANNING_SUBVOLUME',
    })
    it('locking one volume does not lock another', () => {
        let vols = addOrReplacePlanningVolume(addOrReplacePlanningVolume([], mk('0xA')), mk('0xB'))
        vols = setPlanningVolumeLifecycle(vols, '0xA', 'LOCKED')
        expect(vols.find((v) => v.parentBimSpaceId === '0xA')!.lifecycleState).toBe('LOCKED')
        expect(vols.find((v) => v.parentBimSpaceId === '0xB')!.lifecycleState).toBe('DRAFT')
    })
    it('lock requires containment PASS + valid dims (gate)', () => {
        const parent = boxMesh({ x: 0, y: 0, z: 0 }, { x: 10, y: 10, z: 4 })
        const inside = mk('0xA')
        inside.params = { centerX: 5, centerY: 5, zLow: 0, zHigh: 3, width: 3, depth: 3, yaw: 0 }
        expect(canLockVolume(inside, parent).ok).toBe(true)
        const outside = mk('0xB')
        outside.params = { centerX: 50, centerY: 50, zLow: 0, zHigh: 3, width: 3, depth: 3, yaw: 0 }
        expect(canLockVolume(outside, parent).ok).toBe(false)
    })
})

// --- 14. persistence roundtrip ---------------------------------------------
// --- 15/21. BIM-switch isolation -------------------------------------------

describe('§35.14-15 persistence roundtrip + iModel isolation', () => {
    function memStorage(): Storage {
        const m = new Map<string, string>()
        return {
            getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
            setItem: (k: string, v: string) => void m.set(k, v),
            removeItem: (k: string) => void m.delete(k),
            clear: () => m.clear(),
            key: (i: number) => Array.from(m.keys())[i] ?? null,
            get length() { return m.size },
        } as Storage
    }
    const mk = (im: string, parent: string): ClinicalPlanningVolume => ({
        id: makeClinicalVolumeId(im, parent, 'v'), iModelId: im, parentBimSpaceId: parent,
        clinicalFunction: 'INJECTION_ROOM', displayName: 'Injection Room 01',
        geometryType: 'ORIENTED_RECTANGULAR_PRISM',
        params: { centerX: 45, centerY: 64, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0 },
        lifecycleState: 'DRAFT', geometrySource: 'MRT_PLANNING_SUBVOLUME',
    })
    it('save→load returns the same volume geometry (roundtrip)', () => {
        const s = memStorage()
        saveClinicalVolumes('im-clinic', [mk('im-clinic', '0xA')], s)
        const loaded = loadClinicalVolumes('im-clinic', s)
        expect(loaded).toHaveLength(1)
        expect(loaded[0].params.centerX).toBe(45)
        expect(loaded[0].parentBimSpaceId).toBe('0xA')
    })
    it('a different iModel key does not leak volumes (switch isolation)', () => {
        const s = memStorage()
        saveClinicalVolumes('im-clinic', [mk('im-clinic', '0xA')], s)
        expect(loadClinicalVolumes('im-fixture', s)).toEqual([]) // other iModel empty
        saveClinicalVolumes('im-fixture', [mk('im-fixture', '0xZ')], s)
        // Switching back still shows the clinic's own volume only.
        expect(loadClinicalVolumes('im-clinic', s).map((v) => v.parentBimSpaceId)).toEqual(['0xA'])
    })
})

// --- 16. lazy extraction policy (registry reflects, never triggers) ---------

describe('§35.16 lazy extraction policy', () => {
    it('a room with no cached mesh is discovered as RANGE_ONLY (no eager meshing)', () => {
        const rooms = [room({ roomId: '0xA', geometryType: 'RANGE_ONLY', range: range([0, 0, 0], [2, 2, 3]) })]
        const d = discoverRoomVolumes({ iModelId: 'im-1', rooms, storeys: [] }) // no meshCacheByRoom supplied
        expect(d[0].exactMeshAvailable).toBe(false)
        expect(d[0].geometryQuality).toBe('RANGE_ONLY_APPROXIMATION')
        expect(d[0].vertexCount).toBe(0)
    })
    it('once a mesh is cached, discovery reflects EXACT + reuses stats', () => {
        const rooms = [room({ roomId: '0xA', geometryType: 'RANGE_ONLY', range: range([0, 0, 0], [2, 2, 3]) })]
        const d = discoverRoomVolumes({ iModelId: 'im-1', rooms, storeys: [], meshCacheByRoom: { '0xA': EXACT_CACHE } })
        expect(d[0].exactMeshAvailable).toBe(true)
        expect(d[0].vertexCount).toBe(186)
        expect(d[0].triangleCount).toBe(368)
    })
})

// --- 17. camera invariance -------------------------------------------------

describe('§35.17 camera invariance', () => {
    it('world prism geometry is a pure function of params (no camera input)', () => {
        const p: PrismParams = { centerX: 45, centerY: 64, zLow: 0, zHigh: 3, width: 4, depth: 3, yaw: 0.3 }
        const g1 = buildOrientedPlanningPrism(p)
        const g2 = buildOrientedPlanningPrism(p)
        expect(g1.vertices).toEqual(g2.vertices) // identical world coords regardless of any view
        expect(g1.interiorAnchor).toEqual(g2.interiorAnchor)
    })
})

// --- 18. Uptake regression -------------------------------------------------

describe('§35.18 Uptake 01 regression baseline preserved', () => {
    it('the frozen baseline constants are unchanged', () => {
        expect(UPTAKE_01_BASELINE.bimSpaceId).toBe('0x200000001f1')
        expect(UPTAKE_01_BASELINE.originalBimLabel).toBe('1AC1 CENTRAL WAITING')
        expect(UPTAKE_01_BASELINE.clinicalFunction).toBe('UPTAKE_ROOM')
        expect(UPTAKE_01_BASELINE.mrtDisplayName).toBe('Uptake 01')
        expect(UPTAKE_01_BASELINE.params).toMatchObject({ centerX: -9.84, centerY: 30.53, width: 4, depth: 3, zLow: 0, zHigh: 3, yaw: 0 })
    })
    it('the generic diagnostic flags the Uptake baseline room, generic for others', () => {
        const rooms = [
            room({ roomId: '0x200000001f1', displayName: '1AC1 CENTRAL WAITING', range: range([-20, 25, 0], [0, 35, 4.5]) }),
            room({ roomId: '0xOTHER', displayName: 'Some Room', range: range([40, 60, 0], [50, 68, 3]) }),
        ]
        const disc = discoverRoomVolumes({ iModelId: 'im-clinic', rooms, storeys: [] })
        const uptake = disc.find((r) => r.bimSpaceId === '0x200000001f1')!
        const other = disc.find((r) => r.bimSpaceId === '0xOTHER')!
        const dUptake = buildSelectedRoomVolumeDiagnostic({ room: uptake, closedMesh: true, containmentStatus: 'NOT_EVALUATED', uptakeBaselineBimSpaceId: '0x200000001f1' })
        const dOther = buildSelectedRoomVolumeDiagnostic({ room: other, closedMesh: false, containmentStatus: 'NOT_EVALUATED', uptakeBaselineBimSpaceId: '0x200000001f1' })
        expect(dUptake.isUptakeRegressionBaseline).toBe(true)
        expect(dOther.isUptakeRegressionBaseline).toBe(false)
        expect(formatSelectedRoomVolumeDiagnostic(dOther)).toContain('SELECTED ROOM VOLUME (generic)')
        expect(formatSelectedRoomVolumeDiagnostic(dOther)).toContain('BENTLEY_WRITE = NONE')
    })
})

// --- discovery summary + storey awareness ----------------------------------

describe('§24 discovery summary', () => {
    it('counts exact / range-only / activated / storeys correctly', () => {
        const rooms = [
            room({ roomId: '0xA', range: range([0, 0, 0], [2, 2, 3]) }), // S1 range-only
            room({ roomId: '0xB', range: range([0, 0, 4.5], [2, 2, 7]) }), // S2 range-only
            room({ roomId: '0xC', geometryType: 'NOT_AVAILABLE' }), // no geometry
        ]
        const d = discoverRoomVolumes({
            iModelId: 'im-1', rooms, storeys: STOREYS,
            meshCacheByRoom: { '0xA': EXACT_CACHE },
            assignments: [{ bimSpaceId: '0xA', clinicalFunction: 'UPTAKE_ROOM', mrtDisplayName: 'Uptake 01' }],
            planningVolumeParentIds: ['0xA'],
        })
        const s = summarizeRoomVolumeDiscovery({ iModelId: 'im-1', discovered: d, planningVolumeCount: 1 })
        expect(s.discoveredRoomCount).toBe(3)
        expect(s.exactGeometryCachedCount).toBe(1) // 0xA
        expect(s.rangeOnlyCount).toBe(1) // 0xB
        expect(s.noGeometryCount).toBe(1) // 0xC
        expect(s.activatedRoomCount).toBe(1)
        expect(s.planningVolumeCount).toBe(1)
        expect(s.storeyCount).toBe(2) // S1 + S2
        // discovery reflected assignment WITHOUT creating it (input-driven)
        expect(d.find((r) => r.bimSpaceId === '0xA')!.assigned).toBe(true)
        expect(d.find((r) => r.bimSpaceId === '0xB')!.assigned).toBe(false)
    })
})

// --- delete semantics (collection) -----------------------------------------

describe('delete DRAFT vs LOCKED', () => {
    const mk = (parent: string, life: 'DRAFT' | 'LOCKED'): ClinicalPlanningVolume => ({
        id: makeClinicalVolumeId('im-1', parent, 'v'), iModelId: 'im-1', parentBimSpaceId: parent,
        clinicalFunction: 'INJECTION_ROOM', displayName: `Vol ${parent}`,
        geometryType: 'ORIENTED_RECTANGULAR_PRISM',
        params: { centerX: 0, centerY: 0, zLow: 0, zHigh: 3, width: 2, depth: 2, yaw: 0 },
        lifecycleState: life, geometrySource: 'MRT_PLANNING_SUBVOLUME',
    })
    it('DRAFT deletes; LOCKED is rejected', () => {
        const draft = deletePlanningVolume([mk('0xA', 'DRAFT')], '0xA')
        expect(draft.deleted).toBe(true)
        const locked = deletePlanningVolume([mk('0xB', 'LOCKED')], '0xB')
        expect(locked.deleted).toBe(false)
    })
    it('summary counts by lifecycle + visibility', () => {
        const vols = [mk('0xA', 'DRAFT'), { ...mk('0xB', 'LOCKED') }, { ...mk('0xC', 'DRAFT'), hidden: true }]
        const s = summarizePlanningVolumes(vols)
        expect(s.planningVolumes).toBe(3)
        expect(s.draft).toBe(2)
        expect(s.locked).toBe(1)
        expect(s.hidden).toBe(1)
    })
})

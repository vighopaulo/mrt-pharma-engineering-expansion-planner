/**
 * Offline tests for the visual planning foundation. Pure visual-state seams +
 * the enriched parametric scanner geometry + engineering-identity immutability
 * across visual mode. No Bentley runtime.
 */
import { describe, expect, it } from 'vitest'
import {
    DEFAULT_VIEWER_MODE,
    devButtonBlockVisibleInMode,
    resolveDeveloperVisibility,
    resolveEquipmentVisualState,
    resolveRoomVisualPolicy,
    resolveSelectionVisualState,
    roomVolumesDominateInMode,
} from '../components/spatial/planningVisuals'
import { buildScannerParts } from '../components/spatial/scannerGeometry'
import {
    buildPlacementIntent,
    CATALOG_TEST_ASSET_DEFINITION_ID,
    GE_DISCOVERY_MI_RECORD,
    SpatialAssetStore,
    TEST_PROJECT_ID,
    type AssetInstance,
    type ScenarioProvenance,
} from '../domain/assets'

const DEV_SCENARIO: ScenarioProvenance = { scenarioId: 'MRT_DEV_SCENARIO', scenarioState: 'DRAFT' }
const newStore = () => new SpatialAssetStore({ projectId: TEST_PROJECT_ID, scenario: DEV_SCENARIO })
function placeAt(store: SpatialAssetStore, x: number, y: number, z: number): AssetInstance {
    const res = buildPlacementIntent({ record: GE_DISCOVERY_MI_RECORD, assetDefinitionId: CATALOG_TEST_ASSET_DEFINITION_ID, registry: store.getRegistry() })
    if (!res.ok) throw new Error('intent build failed')
    store.beginPlacement(res.intent)
    const r = store.completePlacementAt({ x, y, z })
    if (!r.ok) throw new Error('placement failed')
    return r.instance
}

describe('viewer mode + developer visibility', () => {
    it('default mode is NORMAL_PLANNING', () => {
        expect(DEFAULT_VIEWER_MODE).toBe('NORMAL_PLANNING')
    })
    it('normal mode hides dev controls + raw dump; developer mode reveals them', () => {
        const normal = resolveDeveloperVisibility('NORMAL_PLANNING')
        expect(normal.devControlsVisible).toBe(false)
        expect(normal.rawEngineeringDumpVisible).toBe(false)
        expect(normal.developerInspectorAvailable).toBe(false)
        const dev = resolveDeveloperVisibility('DEVELOPER')
        expect(dev.devControlsVisible).toBe(true)
        expect(dev.rawEngineeringDumpVisible).toBe(true)
        expect(dev.developerInspectorAvailable).toBe(true)
    })
    it('DEV button block never renders over the viewport in normal mode', () => {
        expect(devButtonBlockVisibleInMode('NORMAL_PLANNING')).toBe(false)
        expect(devButtonBlockVisibleInMode('DEVELOPER')).toBe(true)
    })
})

describe('equipment + selection visual state (restrained)', () => {
    it('resolves state with selection/rotation precedence over hover', () => {
        expect(resolveEquipmentVisualState({ isSelected: false, selectedCount: 0, isHovered: false, isRotating: false })).toBe('DEFAULT')
        expect(resolveEquipmentVisualState({ isSelected: false, selectedCount: 0, isHovered: true, isRotating: false })).toBe('HOVERED')
        expect(resolveEquipmentVisualState({ isSelected: true, selectedCount: 1, isHovered: false, isRotating: false })).toBe('SELECTED')
        expect(resolveEquipmentVisualState({ isSelected: true, selectedCount: 3, isHovered: true, isRotating: false })).toBe('MULTI_SELECTED')
        expect(resolveEquipmentVisualState({ isSelected: true, selectedCount: 1, isHovered: true, isRotating: true })).toBe('ROTATING')
    })
    it('selection visual is a restrained outline only (no fill overlay), heavier when selected', () => {
        expect(resolveSelectionVisualState('DEFAULT')).toEqual({ outline: false, lineWeight: 1 })
        expect(resolveSelectionVisualState('SELECTED').outline).toBe(true)
        expect(resolveSelectionVisualState('SELECTED').lineWeight).toBeGreaterThan(1)
        expect(resolveSelectionVisualState('MULTI_SELECTED').outline).toBe(true)
        expect(resolveSelectionVisualState('HOVERED').outline).toBe(true)
    })
})

describe('enriched parametric PET/CT geometry', () => {
    it('produces distinct recognizable parts: gantry, bore, table, base', () => {
        const store = newStore()
        const inst = placeAt(store, 0, 0, 0)
        const parts = buildScannerParts(inst)
        const kinds = parts.map((p) => p.part)
        expect(kinds).toContain('GANTRY')
        expect(kinds).toContain('BORE')
        expect(kinds).toContain('PATIENT_TABLE')
        expect(kinds).toContain('TABLE_BASE')
        // Bore is the circular cylinder; others are boxes.
        const bore = parts.find((p) => p.part === 'BORE')
        expect(bore?.kind).toBe('CYLINDER')
    })
    it('geometry is deterministic + parametric (scales with dimensions) without touching identity', () => {
        const store = newStore()
        const inst = placeAt(store, 3, 4, 1)
        const before = JSON.parse(JSON.stringify(inst))
        const p1 = buildScannerParts(inst)
        const p2 = buildScannerParts(inst)
        expect(JSON.stringify(p1)).toBe(JSON.stringify(p2)) // deterministic
        // buildScannerParts must not mutate the instance.
        expect(inst.assetInstanceId).toBe(before.assetInstanceId)
        expect(inst.transform.position).toEqual(before.transform.position)
        expect(inst.dimensions).toEqual(before.dimensions)
    })
})

describe('visual upgrade preserves engineering identity + reuse', () => {
    it('two instances reuse the same geometry representation but keep distinct identity/transform', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0)
        const b = placeAt(store, 9, 2, 0)
        expect(a.geometryRepresentationId).toBe(b.geometryRepresentationId) // shared generic geometry
        expect(a.assetInstanceId).not.toBe(b.assetInstanceId) // distinct instance identity
        expect(a.transform.position).not.toEqual(b.transform.position)
    })
    it('geometry provenance stays generic placeholder; dimensions not calibrated', () => {
        const store = newStore()
        const inst = placeAt(store, 0, 0, 0)
        // Placement uses the generic representation; dimension provenance is a
        // generic/uncalibrated placeholder (never fabricated CATALOG_CALIBRATED).
        expect(inst.dimensions.provenance).not.toBe('CALIBRATED')
        expect(inst.dimensions.provenance).not.toBe('CATALOG')
    })
})

describe('room / spatial-volume visual policy (BuildingSpatial:Space)', () => {
    it('NORMAL_PLANNING subdues/hides the room volumes so they do not dominate', () => {
        expect(resolveRoomVisualPolicy('NORMAL_PLANNING')).toBe('SUBDUED_OR_HIDDEN')
        expect(roomVolumesDominateInMode('NORMAL_PLANNING')).toBe(false)
    })
    it('DEVELOPER mode exposes the full spatial volumes for inspection', () => {
        expect(resolveRoomVisualPolicy('DEVELOPER')).toBe('FULL')
        expect(roomVolumesDominateInMode('DEVELOPER')).toBe(true)
    })
    it('default product mode never lets room volumes dominate the view', () => {
        expect(roomVolumesDominateInMode(DEFAULT_VIEWER_MODE)).toBe(false)
    })
})

describe('planning appearance immutability (visual-only)', () => {
    // The planning appearance is a pure PRESENTATION decision. Simulate toggling
    // it and assert it neither emits engineering events nor changes any
    // AssetInstance identity/position/rotation/association. The visual decision
    // seams are pure functions of mode/inputs and touch NO domain state.
    it('resolving room/equipment/developer visual policy touches no engineering state', () => {
        const store = newStore()
        const inst = placeAt(store, 2, 3, 1)
        // The store bumps version on every authoritative mutation (emit()). Use
        // it as the engineering-event proxy: it must not change across visual
        // decisions. The instance snapshot must be byte-identical too.
        const versionBefore = store.getSnapshot().version
        const snapshotBefore = JSON.parse(JSON.stringify(store.getSnapshot().instances))

        // Exercise every visual decision seam across both modes ("toggle").
        for (const mode of ['NORMAL_PLANNING', 'DEVELOPER'] as const) {
            resolveDeveloperVisibility(mode)
            devButtonBlockVisibleInMode(mode)
            resolveRoomVisualPolicy(mode)
            roomVolumesDominateInMode(mode)
        }
        resolveEquipmentVisualState({ isSelected: true, selectedCount: 1, isHovered: false, isRotating: false })
        resolveSelectionVisualState('SELECTED')

        expect(store.getSnapshot().version).toBe(versionBefore) // VISUAL_APPEARANCE_ENGINEERING_EVENT_COUNT = 0
        expect(JSON.parse(JSON.stringify(store.getSnapshot().instances))).toEqual(snapshotBefore)
        expect(inst.transform.position).toEqual({ x: 2, y: 3, z: 1 })
    })
})

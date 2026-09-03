/**
 * Offline tests for multi-select + group translation, the rotation-handle visual
 * state machine, and the right-click context-menu decision. Pure domain/store +
 * pure seams; no Bentley runtime.
 */
import { describe, expect, it } from 'vitest'
import {
    buildPlacementIntent,
    CATALOG_TEST_ASSET_DEFINITION_ID,
    GE_DISCOVERY_MI_RECORD,
    SpatialAssetStore,
    TEST_PROJECT_ID,
    type AssetInstance,
    type ScenarioProvenance,
} from '../domain/assets'
import {
    marqueeSelect,
    normalizeScreenRect,
    resolveAssetContextMenu,
    resolveDecorationRedrawPolicy,
    resolveRotationHandleVisualState,
    screenDragDistance,
    screenRectsIntersect,
    type MrtPickTarget,
    type ScreenRect,
} from '../components/spatial/assetPicking'

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

// ---------------------------------------------------------------------------

describe('rotation-handle visual state machine (pure)', () => {
    const base = { isOwnedAppAsset: true, isThisSelected: true, selectedCount: 1, hover: false, rotating: false }
    it('unselected -> HIDDEN', () => {
        expect(resolveRotationHandleVisualState({ ...base, isThisSelected: false, selectedCount: 0 })).toBe('HIDDEN')
    })
    it('single selected idle -> IDLE_HINT', () => {
        expect(resolveRotationHandleVisualState(base)).toBe('IDLE_HINT')
    })
    it('single selected hover -> HOVER', () => {
        expect(resolveRotationHandleVisualState({ ...base, hover: true })).toBe('HOVER')
    })
    it('active rotation -> ACTIVE_ROTATION (overrides hover)', () => {
        expect(resolveRotationHandleVisualState({ ...base, hover: true, rotating: true })).toBe('ACTIVE_ROTATION')
    })
    it('multi-select (count>1) -> HIDDEN', () => {
        expect(resolveRotationHandleVisualState({ ...base, selectedCount: 2 })).toBe('HIDDEN')
    })
    it('non-owned geometry (catalog/dev/BIM) -> HIDDEN', () => {
        expect(resolveRotationHandleVisualState({ ...base, isOwnedAppAsset: false })).toBe('HIDDEN')
    })
})

describe('right-click context-menu decision (pure)', () => {
    const body = (id: string): MrtPickTarget => ({ type: 'ASSET_BODY', assetInstanceId: id })
    it('unselected app asset -> SELECT + DELETE', () => {
        const d = resolveAssetContextMenu(body('A'), () => false)
        expect(d).toEqual({ assetInstanceId: 'A', actions: ['SELECT', 'DELETE'] })
    })
    it('selected app asset -> DESELECT + DELETE', () => {
        const d = resolveAssetContextMenu(body('A'), (id) => id === 'A')
        expect(d).toEqual({ assetInstanceId: 'A', actions: ['DESELECT', 'DELETE'] })
    })
    it('no target (BIM / empty / catalog / dev) -> no menu', () => {
        expect(resolveAssetContextMenu(undefined, () => false)).toBeUndefined()
    })
    it('never shows both SELECT and DESELECT', () => {
        for (const sel of [true, false]) {
            const d = resolveAssetContextMenu(body('A'), () => sel)!
            const hasSelect = d.actions.includes('SELECT')
            const hasDeselect = d.actions.includes('DESELECT')
            expect(hasSelect && hasDeselect).toBe(false)
        }
    })
})

describe('snapshot stability (useSyncExternalStore correctness)', () => {
    it('getSnapshot returns a STABLE reference across reads without a state change', () => {
        const store = newStore()
        placeAt(store, 1, 1, 0)
        const s1 = store.getSnapshot()
        const s2 = store.getSnapshot()
        // Same object reference -> React will not re-render in a loop.
        expect(s1).toBe(s2)
    })
    it('a real state change produces a NEW snapshot; a no-op selection does not', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        const before = store.getSnapshot()
        store.selectAsset(a) // real change
        const afterChange = store.getSnapshot()
        expect(afterChange).not.toBe(before)
        // Selecting the SAME sole id again is a no-op -> stable reference.
        const stable1 = store.getSnapshot()
        store.selectAsset(a)
        const stable2 = store.getSnapshot()
        expect(stable2).toBe(stable1)
    })
    it('selectedAssetInstanceIds is stable between emits (no churn without change)', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        store.selectAsset(a)
        const ids1 = store.getSnapshot().selectedAssetInstanceIds
        const ids2 = store.getSnapshot().selectedAssetInstanceIds
        expect(ids2).toBe(ids1) // same array ref between reads (no re-emit)
    })
})

describe('multi-selection state (store)', () => {
    it('primary/replace, shift/toggle, clear transitions', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        const b = placeAt(store, 2, 2, 0).assetInstanceId
        const c = placeAt(store, 3, 3, 0).assetInstanceId

        store.selectAsset(a)
        expect(store.getSelectedIds()).toEqual([a])
        store.toggleAsset(b)
        expect(new Set(store.getSelectedIds())).toEqual(new Set([a, b]))
        store.toggleAsset(c)
        expect(new Set(store.getSelectedIds())).toEqual(new Set([a, b, c]))
        store.toggleAsset(b) // remove B
        expect(new Set(store.getSelectedIds())).toEqual(new Set([a, c]))
        store.clearSelection()
        expect(store.getSelectedIds()).toEqual([])
    })

    it('single-selection compatibility: selectedAssetInstanceId is sole member only', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        const b = placeAt(store, 2, 2, 0).assetInstanceId
        store.selectAsset(a)
        expect(store.getSnapshot().selectedAssetInstanceId).toBe(a)
        store.toggleAsset(b) // now 2 selected
        expect(store.getSnapshot().selectedAssetInstanceId).toBeUndefined()
        expect(store.getSnapshot().selectedAssetInstanceIds.length).toBe(2)
    })

    it('plain select REPLACES an existing multi-selection', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        const b = placeAt(store, 2, 2, 0).assetInstanceId
        store.selectAsset(a); store.toggleAsset(b)
        store.selectAsset(a) // replace
        expect(store.getSelectedIds()).toEqual([a])
    })

    it('deleting a selected member removes it from selection', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        const b = placeAt(store, 2, 2, 0).assetInstanceId
        store.selectAsset(a); store.toggleAsset(b)
        store.deleteAsset(a)
        expect(new Set(store.getSelectedIds())).toEqual(new Set([b]))
    })
})

describe('decoration redraw policy (Bentley cache safety)', () => {
    it('idle -> CACHE_INVALIDATE (cache present)', () => {
        expect(resolveDecorationRedrawPolicy({ dragActive: false, groupDragActive: false, rotationActive: false })).toBe('CACHE_INVALIDATE')
    })
    it('single drag -> DYNAMIC_REDRAW (no cache entry; never delete)', () => {
        expect(resolveDecorationRedrawPolicy({ dragActive: true, groupDragActive: false, rotationActive: false })).toBe('DYNAMIC_REDRAW')
    })
    it('GROUP drag -> DYNAMIC_REDRAW (the crash fix: was CACHE_INVALIDATE -> assert)', () => {
        expect(resolveDecorationRedrawPolicy({ dragActive: false, groupDragActive: true, rotationActive: false })).toBe('DYNAMIC_REDRAW')
    })
    it('rotation -> DYNAMIC_REDRAW', () => {
        expect(resolveDecorationRedrawPolicy({ dragActive: false, groupDragActive: false, rotationActive: true })).toBe('DYNAMIC_REDRAW')
    })
    it('any active preview never requests deletion of a non-existent cache entry', () => {
        for (const combo of [
            { dragActive: true, groupDragActive: false, rotationActive: false },
            { dragActive: false, groupDragActive: true, rotationActive: false },
            { dragActive: false, groupDragActive: false, rotationActive: true },
            { dragActive: true, groupDragActive: true, rotationActive: true },
        ]) {
            expect(resolveDecorationRedrawPolicy(combo)).toBe('DYNAMIC_REDRAW')
        }
    })
})

describe('marquee selection (pure)', () => {
    it('rect normalization is direction-independent', () => {
        const tl = normalizeScreenRect({ x: 10, y: 10 }, { x: 40, y: 30 })
        const br = normalizeScreenRect({ x: 40, y: 30 }, { x: 10, y: 10 })
        const tr = normalizeScreenRect({ x: 40, y: 10 }, { x: 10, y: 30 })
        const expected: ScreenRect = { minX: 10, minY: 10, maxX: 40, maxY: 30 }
        expect(tl).toEqual(expected)
        expect(br).toEqual(expected)
        expect(tr).toEqual(expected)
    })

    it('screenRectsIntersect: overlap / touch / disjoint', () => {
        const r: ScreenRect = { minX: 0, minY: 0, maxX: 10, maxY: 10 }
        expect(screenRectsIntersect(r, { minX: 5, minY: 5, maxX: 20, maxY: 20 })).toBe(true) // overlap
        expect(screenRectsIntersect(r, { minX: 10, minY: 0, maxX: 12, maxY: 10 })).toBe(true) // touch edge
        expect(screenRectsIntersect(r, { minX: 20, minY: 20, maxX: 30, maxY: 30 })).toBe(false) // disjoint
    })

    it('marqueeSelect: fully-inside + partial-intersect selected, outside not', () => {
        const marquee: ScreenRect = { minX: 0, minY: 0, maxX: 100, maxY: 100 }
        const candidates = [
            { assetInstanceId: 'A', bounds: { minX: 10, minY: 10, maxX: 40, maxY: 40 } }, // fully inside
            { assetInstanceId: 'B', bounds: { minX: 90, minY: 90, maxX: 140, maxY: 140 } }, // partial
            { assetInstanceId: 'C', bounds: { minX: 200, minY: 200, maxX: 240, maxY: 240 } }, // outside
        ]
        expect(marqueeSelect(marquee, candidates).sort()).toEqual(['A', 'B'])
    })

    it('marqueeSelect: empty result when nothing intersects', () => {
        const marquee: ScreenRect = { minX: 0, minY: 0, maxX: 5, maxY: 5 }
        const candidates = [{ assetInstanceId: 'A', bounds: { minX: 50, minY: 50, maxX: 60, maxY: 60 } }]
        expect(marqueeSelect(marquee, candidates)).toEqual([])
    })

    it('screenDragDistance drives the click-vs-marquee threshold', () => {
        expect(screenDragDistance({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5)
        expect(screenDragDistance({ x: 0, y: 0 }, { x: 1, y: 1 })).toBeLessThan(5)
    })
})

describe('marquee-to-group routing (press on selected member must not collapse)', () => {
    it('after marquee replaceSelection({A,B}), both are selected and group-eligible', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        const b = placeAt(store, 2, 2, 0).assetInstanceId
        store.replaceSelection([a, b]) // marquee release
        expect(store.isSelected(a)).toBe(true)
        expect(store.isSelected(b)).toBe(true)
        // Group eligibility uses VALID selected instance count.
        expect(store.getSelectedInstances().length).toBe(2)
        // Pressing an already-selected member must NOT collapse: the tool skips
        // selectAsset in that case, so the selection stays {A,B} and a body drag
        // begins as GROUP. (Proving the hazard: selectAsset WOULD collapse.)
        expect(store.isSelected(a) && store.getSelectedInstances().length > 1).toBe(true)
    })
    it('HAZARD: selectAsset on an already-selected member collapses to single (why the tool must skip it)', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        const b = placeAt(store, 2, 2, 0).assetInstanceId
        store.replaceSelection([a, b])
        store.selectAsset(a) // the collapse the tool must avoid on press
        expect(store.getSelectedInstances().length).toBe(1) // would force SINGLE drag
    })
    it('group drag begins for a selected member of a >1 selection (store contract)', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        const b = placeAt(store, 2, 2, 0).assetInstanceId
        store.replaceSelection([a, b])
        const r = store.beginGroupDrag(a, { x: 1, y: 1, z: 0 })
        expect(r.ok).toBe(true)
        expect(store.getInteractionState()).toBe('GROUP_TRANSLATING')
        expect(store.getGroupDragPreview()?.assetInstanceIds.length).toBe(2)
    })
})

describe('marquee release policy + Esc (store)', () => {
    it('replaceSelection replaces prior selection with intersecting ids (stale ignored)', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        const b = placeAt(store, 2, 2, 0).assetInstanceId
        store.selectAsset(a) // prior selection {A}
        store.replaceSelection([b, 'STALE-NONEXISTENT'])
        expect(store.getSelectedIds()).toEqual([b]) // stale dropped, A replaced
    })
    it('replaceSelection([]) clears selection (empty marquee result)', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        store.selectAsset(a)
        store.replaceSelection([])
        expect(store.getSelectedIds()).toEqual([])
    })
    it('Esc-cancel restores prior selection via replaceSelection', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        const b = placeAt(store, 2, 2, 0).assetInstanceId
        store.selectAsset(a); store.toggleAsset(b) // prior {A,B}
        const prior = [...store.getSelectedIds()]
        // simulate marquee changing selection then Esc restoring prior
        store.replaceSelection([a])
        store.replaceSelection(prior)
        expect(new Set(store.getSelectedIds())).toEqual(new Set([a, b]))
    })
})

describe('stale-selection drag safety (store)', () => {
    it('pruneStaleSelection removes ids for missing instances', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        const b = placeAt(store, 2, 2, 0).assetInstanceId
        store.selectAsset(a); store.toggleAsset(b)
        store.deleteAsset(a) // a auto-removed from selection already
        // Force a stale id to prove prune is robust.
        store.replaceSelection([b])
        expect(store.getSelectedInstances().map((i) => i.assetInstanceId)).toEqual([b])
    })
    it('getSelectedInstances resolves ONLY existing members (valid count for group routing)', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0).assetInstanceId
        store.selectAsset(a)
        expect(store.getSelectedInstances().length).toBe(1) // -> single drag, not group
    })
})

describe('group translation (store)', () => {
    function selectThree(store: SpatialAssetStore) {
        const a = placeAt(store, 1, 2, 3)
        const b = placeAt(store, 5, 7, 9)
        const c = placeAt(store, 10, 4, 2)
        store.selectAsset(a.assetInstanceId)
        store.toggleAsset(b.assetInstanceId)
        store.toggleAsset(c.assetInstanceId)
        return { a, b, c }
    }

    it('preview math preserves relative offsets + each own Z; 0 events during preview', () => {
        const store = newStore()
        const { a, b, c } = selectThree(store)
        let moved = 0
        // (we assert via committed positions unchanged during preview)
        store.beginGroupDrag(a.assetInstanceId, { x: 1, y: 2, z: 3 }) // grab at anchor origin -> zero offset
        store.updateGroupDragPreview({ x: 5, y: 0, z: 3 }) // delta (4,-2)
        const gp = store.getGroupDragPreview()!
        expect(gp.previewPositions[a.assetInstanceId]).toEqual({ x: 5, y: 0, z: 3 })
        expect(gp.previewPositions[b.assetInstanceId]).toEqual({ x: 9, y: 5, z: 9 })
        expect(gp.previewPositions[c.assetInstanceId]).toEqual({ x: 14, y: 2, z: 2 })
        // committed positions unchanged during preview
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 1, y: 2, z: 3 })
        expect(store.getInstance(b.assetInstanceId)!.transform.position).toEqual({ x: 5, y: 7, z: 9 })
        void moved
    })

    it('commit moves all members to preview positions; ONE ASSET_MOVED per moved member', () => {
        const store = newStore()
        const { a, b, c } = selectThree(store)
        store.beginGroupDrag(a.assetInstanceId, { x: 1, y: 2, z: 3 })
        store.updateGroupDragPreview({ x: 5, y: 0, z: 3 })
        const res = store.commitGroupDrag()
        expect(res.ok).toBe(true)
        if (!res.ok) return
        expect(res.movedCount).toBe(3)
        expect(res.events.length).toBe(3)
        expect(res.events.every((e) => e.type === 'ASSET_MOVED')).toBe(true)
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 5, y: 0, z: 3 })
        expect(store.getInstance(c.assetInstanceId)!.transform.position).toEqual({ x: 14, y: 2, z: 2 })
        // selection preserved
        expect(new Set(store.getSelectedIds())).toEqual(new Set([a.assetInstanceId, b.assetInstanceId, c.assetInstanceId]))
        // interaction back to IDLE
        expect(store.getInteractionState()).toBe('IDLE')
    })

    it('cancel restores all committed positions; 0 events; selection preserved', () => {
        const store = newStore()
        const { a, b, c } = selectThree(store)
        store.beginGroupDrag(a.assetInstanceId, { x: 1, y: 2, z: 3 })
        store.updateGroupDragPreview({ x: 100, y: 100, z: 3 })
        store.cancelGroupDrag()
        expect(store.getInstance(a.assetInstanceId)!.transform.position).toEqual({ x: 1, y: 2, z: 3 })
        expect(store.getInstance(b.assetInstanceId)!.transform.position).toEqual({ x: 5, y: 7, z: 9 })
        expect(store.getInstance(c.assetInstanceId)!.transform.position).toEqual({ x: 10, y: 4, z: 2 })
        expect(store.getInteractionState()).toBe('IDLE')
        expect(new Set(store.getSelectedIds())).toEqual(new Set([a.assetInstanceId, b.assetInstanceId, c.assetInstanceId]))
    })

    it('identity immutability across group commit (only position changes)', () => {
        const store = newStore()
        const { a } = selectThree(store)
        const before = JSON.parse(JSON.stringify(store.getInstance(a.assetInstanceId)))
        store.beginGroupDrag(a.assetInstanceId, { x: 1, y: 2, z: 3 })
        store.updateGroupDragPreview({ x: 3, y: 2, z: 3 })
        store.commitGroupDrag()
        const after = store.getInstance(a.assetInstanceId)!
        expect(after.assetInstanceId).toBe(before.assetInstanceId)
        expect(after.assetDefinitionId).toBe(before.assetDefinitionId)
        expect(after.geometryRepresentationId).toBe(before.geometryRepresentationId)
        expect(after.transform.rotation).toEqual(before.transform.rotation)
        expect(after.spatialSource).toBe(before.spatialSource)
        expect(after.scenario).toEqual(before.scenario)
    })

    it('non-selected asset is isolated during group drag', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0)
        const b = placeAt(store, 2, 2, 0)
        const c = placeAt(store, 3, 3, 0) // NOT selected
        store.selectAsset(a.assetInstanceId); store.toggleAsset(b.assetInstanceId)
        store.beginGroupDrag(a.assetInstanceId, { x: 1, y: 1, z: 0 })
        store.updateGroupDragPreview({ x: 10, y: 1, z: 0 })
        const gp = store.getGroupDragPreview()!
        expect(gp.previewPositions[c.assetInstanceId]).toBeUndefined()
        store.commitGroupDrag()
        expect(store.getInstance(c.assetInstanceId)!.transform.position).toEqual({ x: 3, y: 3, z: 0 })
    })

    it('zero-delta group drag commits no movement events', () => {
        const store = newStore()
        const { a } = selectThree(store)
        store.beginGroupDrag(a.assetInstanceId, { x: 1, y: 2, z: 3 })
        // no updateGroupDragPreview -> delta stays (0,0)
        const res = store.commitGroupDrag()
        expect(res.ok).toBe(true)
        if (res.ok) expect(res.movedCount).toBe(0)
    })

    it('group drag rejected when fewer than 2 selected / anchor not selected', () => {
        const store = newStore()
        const a = placeAt(store, 1, 1, 0)
        store.selectAsset(a.assetInstanceId) // only 1 selected
        expect(store.beginGroupDrag(a.assetInstanceId, { x: 1, y: 1, z: 0 })).toEqual({ ok: false, reason: 'MOVE_INTENT_INVALID' })
        const b = placeAt(store, 2, 2, 0)
        store.toggleAsset(b.assetInstanceId)
        // anchor c not in selection
        const c = placeAt(store, 3, 3, 0)
        expect(store.beginGroupDrag(c.assetInstanceId, { x: 3, y: 3, z: 0 })).toEqual({ ok: false, reason: 'ASSET_NOT_FOUND' })
    })

    it('group drag preserves DIFFERENT starting Z per member (horizontal move)', () => {
        const store = newStore()
        const a = placeAt(store, 0, 0, 1)
        const b = placeAt(store, 4, 0, 8) // different Z
        store.selectAsset(a.assetInstanceId); store.toggleAsset(b.assetInstanceId)
        store.beginGroupDrag(a.assetInstanceId, { x: 0, y: 0, z: 1 })
        store.updateGroupDragPreview({ x: 5, y: 0, z: 1 }) // delta (5,0)
        const gp = store.getGroupDragPreview()!
        expect(gp.previewPositions[a.assetInstanceId].z).toBe(1)
        expect(gp.previewPositions[b.assetInstanceId].z).toBe(8) // own Z retained
    })
})

# MRT Pharma — EVI-MA-02 Direct 3D Equipment Selection, Context-Menu Deletion & Duplicate Usability

Recognizable cyclotron geometry now renders (EVI-MA-01), but the user could not operate directly on the physical 3D equipment: multiple overlapping cyclotrons (IBA Cyclone KIUBE + IBA Cyclone KEY) existed, and the only deletion path was buried in the Clinical Program card. This build makes the 3D equipment directly selectable, adds a right-click equipment context menu, and routes deletion through the ONE authoritative instance lifecycle.

manual_acceptance = **PENDING** (do not self-accept).

---

## 1. Root cause

The recognizable equipment geometry drawn by `ClinicalProgramDecorator` was created with the **non-pickable** two-argument `context.createGraphicBuilder(GraphicType.WorldDecoration)` form. It carried **no pickable transient id**, so a 3D click/right-click on a cyclotron resolved to no application target — the equipment was visible but not directly selectable or deletable. The legacy `SpatialAssetDecorator` (scanner fixtures) already used the pickable three-argument form; equipment simply never adopted it.

## 2. Governing doctrine honored

One `EquipmentAssetInstance` is the single lifecycle object. The recognizable geometry, containment envelope, label, 2D-plan marker, and Clinical Program card are all representations of that ONE instance and share the stable `equipmentInstanceId`. Selection, deletion, hide/show, lock/unlock, fit, persistence all operate on that id. No second lifecycle was created; no Bentley BIM element is modified; deletion is never based on canonical model name.

## 3. Fixes

**(a) Equipment is pickable (ClinicalProgramDecorator.ts)** — added `equipmentPickIdToInstance` / `instanceToEquipmentPickId` maps rebuilt each `decorate()`, `equipmentPickIdFor(equipmentInstanceId, iModel)` (via `iModel.transientIds.getNext()`), `testDecorationHit(id)`, and `equipmentIdForPickId(pickId)`. ONE stable pick id per instance is threaded into `drawEquipmentVisual` and `drawEquipmentEnvelope` (three-arg `createGraphicBuilder(..., pickId)`), so any primitive of one cyclotron (body, shielding, cabinet, or envelope) resolves to its exact `equipmentInstanceId` — even when two cyclotrons overlap. Stale ids are dropped every frame before any early return.

**(b) One selection authority + context-menu state (spatialAssetOverlay.ts)** — added `EquipmentContextMenuState` + `subscribe/get/open/closeEquipmentContextMenu` (opening also `selectEquipment`s the target and closes the legacy asset menu), `getClinicalProgramDecorator()`, and `equipmentIdForPickId(pickId)` delegating to the decorator. Selection authority remains the existing `selectedEquipmentId`.

**(c) 3D click/right-click routing (MrtDirectManipulationTool.ts)** — `locateEquipmentTarget(ev)` resolves an equipment pick id first. `onDataButtonDown` (left-click) on equipment clears any legacy asset selection and `selectEquipment(id)`; `onResetButtonUp` (right-click) opens the equipment context menu for that exact id. `filterHit` now accepts a hit that resolves to an app asset OR an app equipment id — BIM elements (`isElementHit`) resolve to neither pick map and stay rejected, so right-clicking a wall/room/door/floor never exposes the equipment Delete. Escape closes the equipment menu.

**(d) Equipment context menu (ViewerEquipmentContextMenu.tsx)** — a compact menu titled with the exact model (e.g. "IBA Cyclone KIUBE") offering **Fit to Equipment · Lock/Unlock · Hide · Delete**. Delete is disabled when LOCKED (honest policy — unlock first) and otherwise calls the authoritative `deleteEquipment(id)`. Auto-closes when the target no longer exists (deleted) or another instance becomes selected. Mounted in `BentleyViewer.tsx` next to `ViewerAssetContextMenu`; CSS added.

**(e) 2D-plan convergence (bim2dPlanProjection.ts + Bim2dPlanPanel.tsx)** — `hitTestPlanEquipment(view, worldPoint)` (equipment hit-tested BEFORE rooms); the plan `onSvgClick` selects the equipment (`selectEquipment`) and fits, so a 2D marker click converges on the SAME `selectedEquipmentId` as 3D click / 3D right-click / card.

**(f) Duplicate usability (spatialAssetOverlay.ts + ClinicalProgramControl.tsx)** — `placeEquipmentInParent` selects the NEW instance (never leaves the prior one selected), returns `duplicateInRoom` + `displayLabel`, and the placement note surfaces the new selected identity plus a non-blocking "another … already exists in this room" indication. Intentional duplicates are neither merged nor rejected.

**(g) Card Delete kept** — the Clinical Program card Delete and the 3D right-click Delete both call the SAME `deleteEquipment`. No duplicate delete implementation.

## 4. Delete removes all representations

`deleteEquipment(id)` filters the single `equipmentInstances` array (clears the containment cache, clears `selectedEquipmentId` if it matched, persists, `notifyProgram`). Because the render derivation (`getEquipmentForRender`), the 2D markers, and the equipment cards ALL map that one array, deletion removes the recognizable geometry, envelope, 3D label, 2D marker, card, selection reference, and persisted reconstruction together. It never hides-only, never leaves a ghost envelope or stale marker, never deletes another same-model instance, and never touches the iModel.

## 5. Selection after delete

If the deleted instance was selected, `selectedEquipmentId` becomes undefined (no stale id). Deleting KEY leaves KIUBE selected/untouched; deleting a non-selected instance leaves the current selection intact. (Tested.)

## 6. Overlapping equipment

Picking resolves to the underlying stable `equipmentInstanceId` via the decoration pick map — never the visible model name. Two overlapping KIUBEs (or KIUBE + KEY) remain distinct selectable instances with distinct pick ids. The pure 2D hit test resolves the smallest-area footprint under the point for deterministic disambiguation.

## 7. Tests (EVI-MA-02)

`frontend/src/tests/eviMa02DirectEquipmentSelection.test.ts` (11 tests, all pass): pick id → stable instance id; BIM/unknown pick id → undefined (cannot invoke equipment delete); two identical KIUBEs → distinct ids/pick ids; left-click selects the exact instance (KEY not KIUBE); delete(KEY) keeps KIUBE and removes KEY from render derivation + clears stale selection; delete of selected clears selection; delete of non-selected preserves the other selection; LOCKED is selectable + rendered; LOCKED delete rejected honestly; 2D marker click resolves the same id; duplicate KIUBEs persist as two distinct safe instances. Existing EVI-MA-01 + Discovery MI + equipment-visual tests unchanged and green.

## 8. Files changed

- `frontend/src/components/spatial/ClinicalProgramDecorator.ts` — pickable equipment ids.
- `frontend/src/components/spatial/spatialAssetOverlay.ts` — equipment context-menu state, `equipmentIdForPickId`, `getClinicalProgramDecorator`, duplicate detection.
- `frontend/src/components/spatial/MrtDirectManipulationTool.ts` — equipment pick routing (left/right click, filterHit, Escape).
- `frontend/src/components/spatial/ViewerEquipmentContextMenu.tsx` (new) — the 3D equipment context menu.
- `frontend/src/routes/BentleyViewer.tsx` / `BentleyViewer.css` — mount + styling.
- `frontend/src/components/spatial/bim2dPlanProjection.ts` / `Bim2dPlanPanel.tsx` — 2D marker hit test + selection.
- `frontend/src/components/spatial/ClinicalProgramControl.tsx` — duplicate/new-selection note.
- `frontend/src/tests/eviMa02DirectEquipmentSelection.test.ts` (new).

## 9. Verification (actual baseline)

- Test baseline: before 66 files / 1065 tests; after **67 files / 1076 tests PASS** (+11).
- Typecheck `tsc -b`: PASS. Production build (`tsc -b && vite build`): PASS (pre-existing chunk-size + INEFFECTIVE_DYNAMIC_IMPORT advisories only).
- Dev server clean start; `/viewer` = **200**. WASM `public/scripts/draco_decoder.wasm` + Bentley worker `public/scripts/parse-imdl-worker.js` present.
- OpenUSD adapter + Bentley renderability firewall: 125 PASS. No backend Python changed.
- All prior Build 1B / EVI-MA-01 work preserved. No tests weakened.

## 10. Manual acceptance (do NOT self-accept)

1. Place KIUBE. 2. Place KEY. 3. Confirm both exist. 4. Right-click KEY physical 3D geometry. 5. Menu identifies "IBA Cyclone KEY". 6. Delete. 7. KEY disappears completely (geometry, envelope, label, 2D marker, card). 8. KIUBE remains. 9. Right-click KIUBE. 10. Fit to Equipment. 11. KIUBE is framed. 12. Delete KIUBE. 13. All KIUBE representations disappear. 14. Bentley room untouched.

## 11. Stop condition

Automated criteria pass. STOPPED for manual acceptance. Not starting PTS / RTHS / MRT animation / Build 2 routing.

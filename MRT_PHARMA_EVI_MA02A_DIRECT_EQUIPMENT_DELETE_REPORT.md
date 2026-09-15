# MRT Pharma — EVI-MA-02A Direct 3D Equipment Delete + Spatial Exclusivity

EVI-MA-02 added an equipment pick/context-menu path, but LIVE manual acceptance still failed: right-clicking a cyclotron did not reliably open a usable Delete, forcing the user through the Clinical Program panel. This build fixes the proven live root cause and adds the new hard requirement — equipment spatial exclusivity (no overlapping equipment).

manual_acceptance = **PENDING** (do not self-accept).

---

## 1. Reconciled state

- Branch `main`; HEAD `1de2c5b`; origin/main `1de2c5b`; divergence 0/0.
- All uncommitted Build 1B / EVI-MA work preserved; no revert/reset/checkout/ZIP.
- Test baseline before this build: 67 files / 1076 tests.

## 2. Proven live root cause

The direct-manipulation tool (`MrtDirectManipulationTool`) is the ONLY handler of `onDataButtonDown` (left-click select) and `onResetButtonUp` (right-click context menu). It was armed exclusively by `ViewerAssetLibrary`'s effect:

```
if (placed.length > 0 && interaction === 'IDLE') ensureDirectManipulationReady()
```

`placed` counts **legacy `AssetInstance`** objects. Clinical equipment (`EquipmentAssetInstance`) is a separate store, so placing cyclotrons never increments `placed.length`. In the real scenario (cyclotrons only, zero legacy assets) the tool was **never installed**, so a live right-click never reached the equipment handlers added in EVI-MA-02 — the automated tests passed because they exercised the pure resolution, not tool installation. Traced chain break: `mouse/reset/right-click event → (NO ACTIVE TOOL) → equipmentInstanceId resolution` never ran.

## 3. Fix — arm the tool whenever clinical equipment exists

`ensureDirectManipulationReady()` is idempotent, IDLE-gated, and registers the ClinicalProgramDecorator (equipment pick map). It is now armed:
- on `placeEquipmentInParent` success,
- after equipment hydration in `loadEquipmentForIModel` (persisted cyclotrons after reload),
- from a `ClinicalProgramControl` effect keyed on `equipment.length`.

No dependence on any legacy AssetInstance. Temporary instrumentation used during diagnosis was removed.

## 4. Pick-id architecture (unchanged from EVI-MA-02, now actually reachable)

`ClinicalProgramDecorator` allocates ONE stable pickable transient id per `equipmentInstanceId` (`transientIds.getNext()`), threaded into the recognizable geometry (body / shielding / cabinet, or gantry / bore / table) AND the envelope, so every primitive of one instance resolves to the SAME `equipmentInstanceId`. `testDecorationHit` / `equipmentIdForPickId` resolve a `HitDetail.sourceId` back to the exact instance — never the model name, never the BIM element id.

## 5. Interaction behavior

- **Left-click equipment** → resolve pick → `selectEquipment(id)` (clears any legacy asset selection); the card + 2D marker converge on the same `selectedEquipmentId`. Hover never selects.
- **Right-click equipment** → open the equipment context menu for that exact instance (right-click first selects it).
- **Context-menu title** now shows the EXACT canonical model via `canonicalEquipmentById(...).manufacturer + model` (e.g. "IBA Cyclone KIUBE" / "IBA Cyclone KEY"), never a generic "Cyclotron".
- Menu commands: **Fit to Equipment · Lock/Unlock · Hide · Delete**. Delete disabled when LOCKED (unlock available in the same menu). Menu closes on Delete/Hide success, click elsewhere, Escape, select-other, or target gone.
- **Delete** → `deleteEquipment(equipmentInstanceId)` (the SAME authoritative lifecycle the card uses). Removes recognizable geometry, envelope, label, 2D marker, card, count, selection, persistence. Deleting KEY never deletes KIUBE; deleting one KIUBE never deletes another.
- BIM walls/rooms/doors/slabs resolve to no equipment pick id → no equipment menu, no equipment Delete. BIM stays read-only.

## 6. Equipment spatial exclusivity (§12A–§12F) — NEW

- **Pure oriented-volume test** (`equipmentInstance.ts`): `equipmentVolumesIntersect(a, b)` = 2D OBB Separating-Axis test on the **yaw-respecting footprint** (4 edge-normal axes) AND Z-range overlap, with a 0.02 m boundary tolerance so flush side-by-side placement is allowed but any real interpenetration is a collision. Uses the actual occupied volume (X, Y, Z-base, yaw, W/D/H) — NOT center distance, room membership, or 2D-marker overlap. `findEquipmentCollision` returns the first conflicting instance (id + canonical id); locked instances are included (locked equipment reserves its space).
- **Placement** (`placeEquipmentInParent`): validation order — parent room → pose → volume → containment → equipment collision → create. On collision it REJECTS (creates nothing, no transient instance) and reports the conflicting model. The first placed instance reserves its volume until deleted or moved.
- **Pose edits** (`updateEquipmentPlacement`, the single mutation path for translate / rotate / restore / reset): a move that would overlap another instance is rejected; the existing valid pose is kept. Returns a result so the UI reports it honestly.
- **UI**: the placement note and the pose-edit note surface the rejection with the conflicting model name; nothing is created/moved on rejection; duplicates are never silently merged or auto-rejected when non-overlapping.

## 7. 2D/3D selection convergence

One selection authority, `selectedEquipmentId`. 3D left-click, 3D right-click, 2D-plan marker click, and equipment-card click all resolve to it (2D via `hitTestPlanEquipment`, equipment hit-tested before rooms). Deleting an instance updates the 2D plan immediately (same derived array).

## 8. Preserved (no regression)

Recognizable geometry (PET/CT gantry/bore/table; cyclotron body/shielding/cabinet) unchanged; envelopes remain diagnostic overlays. Fit to Equipment remains view-only (no move / no re-parent / no new instance / no BIM write). Card Delete kept; both paths call the same `deleteEquipment`. Discovery MI + EVI-MA-01 visualization unchanged.

## 9. Files changed

- `frontend/src/components/spatial/equipmentInstance.ts` — oriented-volume collision (`equipmentVolumesIntersect`, `findEquipmentCollision`, `EQUIPMENT_COLLISION_TOLERANCE_M`).
- `frontend/src/components/spatial/spatialAssetOverlay.ts` — tool arming on place/load; placement collision rejection; collision-gated `updateEquipmentPlacement` (+ translate/rotate/restore/reset propagation).
- `frontend/src/components/spatial/ClinicalProgramControl.tsx` — equipment-count arming effect; placement + pose-edit rejection notes.
- `frontend/src/components/spatial/ViewerEquipmentContextMenu.tsx` — canonical model title.
- `frontend/src/tests/eviMa02aEquipmentExclusivity.test.ts` (new).

## 10. Tests

- New `eviMa02aEquipmentExclusivity.test.ts` (18 tests): oriented intersection (identical / separated / partial / flush-tolerance / Z-disjoint / rotation-respected); `findEquipmentCollision` first-conflict + self-exclude + locked-reserves; §12F A–F (first wins; delete-then-reuse; same-model duplicate overlap rejected + moved-clear succeeds with distinct id; rotated collision rejected; non-overlapping both succeed; locked A blocks B); move rejected-on-overlap / clear-move-succeeds; context-menu title = canonical model.
- Full suite: **68 files / 1094 tests PASS** (was 67 / 1076; +18). No tests weakened. EVI-MA-02 select/delete tests unchanged and green.

## 11. Build / runtime

- Typecheck `tsc -b`: PASS. Production build: PASS (pre-existing chunk-size + INEFFECTIVE_DYNAMIC_IMPORT advisories only).
- `/viewer` = **200**. WASM `public/scripts/draco_decoder.wasm` + Bentley worker `public/scripts/parse-imdl-worker.js` present.
- OpenUSD adapter + Bentley renderability firewall: 125 PASS. No backend Python changed.

## 12. Manual acceptance (do NOT self-accept)

Direct delete without the panel:
- A. Left-click KIUBE → selected. B. Right-click KIUBE → menu title "IBA Cyclone KIUBE". C. Fit to Equipment → framed. D. Delete → KIUBE fully disappears (geometry, envelope, label, 2D marker, card). E. KEY remains. F. Right-click KEY → title "IBA Cyclone KEY" → Delete → KEY disappears. BIM room untouched.

Spatial exclusivity (§12G):
- 1. Place IBA Cyclone KIUBE. 2. Attempt to place IBA Cyclone KEY partially inside the KIUBE volume → REJECTED (nothing created; note names the conflict). 3. Delete KIUBE via 3D right-click → Delete. 4. Repeat the exact KEY placement → now ACCEPTED.

## 13. Stop condition

Automated criteria pass. STOPPED for manual acceptance. Not starting PTS / RTHS / MRT animation / Build 2 routing.

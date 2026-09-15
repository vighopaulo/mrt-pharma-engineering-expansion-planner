# MRT Pharma — EVI-MA-02D Equipment Context-Menu Regression + Always-Available Selected-Equipment Control

Right-click on the selected KIUBE stopped opening the context menu reliably (a regression from the EVI-MA-02B bridge). This build fixes the right-click seam AND adds an always-available floating SELECTED EQUIPMENT control so Delete never requires the right-click path or panel scrolling. Selection, geometry, collision, auth, walkthrough, and 2D logic are untouched.

manual_acceptance = **PENDING** (do not self-accept).

---

## 1. Reconciled state

Branch `main`; HEAD `1de2c5b`; origin/main `1de2c5b`; divergence 0/0. All prior EVI work preserved. Test baseline before this build: 71 files / 1126 tests.

## 2. Exact regression seam

`MrtDirectManipulationTool.installEquipmentContextMenuBridge` attached the DOM `contextmenu` listener to `vp.parentDiv` in the **bubble** phase, and it was installed **once** in `onPostInstall`. Two live failure modes:

1. **Stale target after a view reopen.** If the Bentley view opened/reopened after the tool installed (a common lifecycle with the `<Viewer>` remount), `IModelApp.viewManager.selectedView.parentDiv` at `onPostInstall` time was either null or a stale element, so the listener was attached to nothing / the wrong element → right-click never reached the handler.
2. **Phase/target.** The WebGL canvas is a child of the viewport container; a bubble-phase listener on `parentDiv` can be pre-empted, and `parentDiv` is not the element that most reliably receives the interaction.

Left-click keeps working because it flows through the tool's `onDataButtonDown` (a Bentley button event), which is unaffected by the DOM listener target.

## 3. Right-click fix

- **Target + phase:** the bridge now attaches to `vp.vpDiv` (the element hosting the canvas; `parentDiv` fallback) in the **capture** phase, so it runs before Bentley/browser handlers regardless of which child is under the cursor.
- **Robust (re)install:** `installEquipmentContextMenuBridge` is idempotent (guarded by target-element identity) and is re-invoked on every `onDataButtonDown`. Since left-click is proven to fire, the bridge is guaranteed to be attached to the CURRENT viewport element before any right-click — surviving a view reopen.
- **Selection-aware, planning-volume-proof pick:** `onViewportContextMenu` resolves via the new pure `pickEquipmentForContext(ray, equipmentInstances, selectedEquipmentId)`:
  1. the SELECTED equipment when the ray hits its occupied volume (act on what you selected),
  2. else the NEAREST equipment along the ray,
  3. else undefined (no equipment menu).
  Only app-owned equipment instances are ever candidates, so a clinical PLANNING VOLUME / room id (e.g. "Cyclotron 02") can NEVER be returned as an `equipmentInstanceId` — it never opens an equipment menu. `preventDefault` is applied ONLY on an equipment hit; BIM/empty right-click keeps normal behavior.

## 4. Always-available floating SELECTED EQUIPMENT control

New `ViewerSelectedEquipmentControl.tsx` (mounted in `BentleyViewer`, authenticated-only): when `selectedEquipmentId != undefined` it shows a compact floating panel titled with the exact canonical model (e.g. "IBA Cyclone KIUBE") with **Fit · Hide/Show · Lock/Unlock · Delete** (Delete disabled + Unlock offered when locked). It derives entirely from the authoritative `selectedEquipmentId` (subscribes via `subscribeClinicalProgram`) and dispatches to the SAME overlay functions the card / right-click menu / keyboard use — not a second lifecycle. This guarantees Delete is reachable the instant equipment is selected, independent of the right-click path and the Clinical Program panel.

## 5. One delete lifecycle (convergence)

Right-click menu Delete, floating-control Delete, card Delete, and keyboard Delete all call the single authoritative `deleteEquipment(equipmentInstanceId)`. Every interaction surface (3D click, 2D marker, card, right-click, floating control, Delete key) converges on `selectedEquipmentId` / `equipmentInstanceId`.

## 6. Panel- / view-mode-independence

The right-click bridge and the floating control live on the viewport + the overlay module singleton — neither depends on the Clinical Program panel being mounted/expanded, on any legacy AssetInstance count, or on a Bentley reset event. The re-install-on-click keeps the bridge valid after orbit/pan/zoom/Fit (camera navigation never detaches it).

## 7. Files changed

- `frontend/src/components/spatial/equipmentInstance.ts` — pure `pickEquipmentForContext` (selection-aware).
- `frontend/src/components/spatial/MrtDirectManipulationTool.ts` — bridge on `vpDiv` capture phase + robust re-install + selection-aware pick.
- `frontend/src/components/spatial/ViewerSelectedEquipmentControl.tsx` (new) — floating selected-equipment control.
- `frontend/src/routes/BentleyViewer.tsx` / `BentleyViewer.css` — mount + styling.
- `frontend/src/tests/eviMa02dContextMenuRegression.test.ts` (new).

## 8. Tests

`eviMa02dContextMenuRegression.test.ts` (7 tests): ray→KIUBE / empty→none; selected-equipment preference on overlap; nearest-wins with no selection; selected-fallback to nearest hit when the ray misses the selected one; hidden never picked; empty set / planning-volume id can never become an equipment id; canonical title convergence. Full suite: **72 files / 1133 tests PASS** (was 71 / 1126; +7). EVI-MA-01/02/02A/02B/02C/03 suites unchanged and green.

## 9. Verification

- Typecheck `tsc -b`: PASS. Production build: PASS (pre-existing advisories only).
- `/viewer` = **200**. WASM `public/scripts/draco_decoder.wasm` + Bentley worker `public/scripts/parse-imdl-worker.js` present.
- Canonical dev server RUNNING on **port 3000**. No backend Python changed. No tests weakened.

## 10. Manual acceptance (do NOT self-accept)

1. Select IBA Cyclone KIUBE in 3D → highlights. 2. Floating SELECTED EQUIPMENT control appears (title "IBA Cyclone KIUBE"). 3. Right-click KIUBE → menu opens at cursor, title "IBA Cyclone KIUBE". 4. Close; orbit; right-click KIUBE → menu opens. 5. Collapse Clinical Program panel; right-click KIUBE → menu opens. 6. Right-click the Cyclotron 02 planning volume → NO equipment menu. 7. Select KIUBE, press Delete (or floating Delete) → KIUBE deletes. 8. Refresh → KIUBE remains absent.

## 11. Stop condition

Automated verification passes; dev server running on port 3000. STOPPED for manual acceptance. Not starting PTS / RTHS / MRT animation / Build 2.

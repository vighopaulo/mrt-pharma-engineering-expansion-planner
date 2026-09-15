# MRT Pharma — EVI-MA-02B Live Right-Click Fix + Direct Delete-Key UX

The live Bentley BIM is restored (EVI-MA-03) and cyclotron LEFT-click selection works. Manual testing proved RIGHT-click did not open the equipment context menu. This build fixes the live right-click path with a viewport-level contextmenu bridge and adds a direct Delete-key deletion of the selected equipment — converging on the one authoritative `deleteEquipment` lifecycle.

manual_acceptance = **PENDING** (do not self-accept).

---

## 1. Governing observation

Left-click selection working proves the chain `3D geometry → pickable transient id → equipmentIdForPickId → selectedEquipmentId` is correct live. That chain was NOT touched. Equipment geometry, visual-family mapping, persistence, collision/exclusivity, parent-room containment, selection authority, 2D-marker identity, and Bentley auth were all left unchanged.

## 2. Root cause of the live right-click failure

Right-click in an iTwin.js 3D view is delivered as the tool "reset" (`onResetButtonUp`) only when the tool actually receives it — but right-click is frequently consumed by the browser `contextmenu` event and/or Bentley view navigation before the tool's reset handler can open the menu. The EVI-MA-02 handler lived solely on `onResetButtonUp`, which was not firing reliably in the live viewer, so the equipment menu never opened. (Left-click uses `onDataButtonDown`, which does fire — hence the asymmetry.)

## 3. Fix — viewport-level contextmenu bridge with a PURE RAY PICK (no Bentley reset, no doLocate)

Added a persistent DOM `contextmenu` listener on the live viewport element (`MrtDirectManipulationTool.installEquipmentContextMenuBridge`, installed in `onPostInstall`, removed in `onCleanup`). On right-click over the 3D canvas, `locateEquipmentAtClient(vp, clientX, clientY)`:

- builds a world pick RAY from the cursor via the viewport frustum (`viewToNpc` → `npcToWorld` near/far) — the SAME reliable ray construction the working drag path uses;
- resolves the exact `equipmentInstanceId` with the pure `pickNearestEquipment(ray, getEquipmentInstances())` (oriented-box ray test reusing the collision envelope math). This does NOT depend on `IModelApp.locateManager.doLocate`, which does not fire reliably for right-click — the reason the first EVI-MA-02B attempt still failed live.

On an equipment hit: `preventDefault()` + `stopPropagation()` (suppress the browser menu), `selectEquipment(id)` (right-click first selects the exact instance), and `openEquipmentContextMenu({id, screenX, screenY})` at the cursor. On BIM / empty: the equipment menu is not opened and the browser menu is NOT suppressed (§3). The existing `onResetButtonUp` path is retained as belt-and-suspenders. BIM walls/rooms/doors never resolve to an equipment id (the ray tests only app-owned equipment envelopes), so they never expose equipment Delete.

Pick resolution: `rayIntersectEquipment` / `pickNearestEquipment` (pure, in `equipmentInstance.ts`). Nearest-along-ray wins for overlapping equipment; hidden instances are excluded.

## 4. Direct Delete-key UX

- Pure focus-safety decision `shouldHandleEquipmentDeleteKey({key, tagName, isContentEditable})` (in `assetPicking.ts`): returns true only for `Delete`/`Backspace` when NOT typing in `INPUT`/`TEXTAREA`/`SELECT`/contenteditable.
- `BentleyViewer` window `keydown` effect (wired only when `AUTHENTICATED`): when the decision passes and an equipment instance is selected, it `preventDefault()` and calls `deleteEquipment(getSelectedEquipmentId())`. If the instance is `LOCKED`, it surfaces "Unlock equipment before deleting." and deletes nothing. When nothing is selected, the key is a no-op (passes through).

## 5. Three convergent delete entry points — one lifecycle

- A. Clinical Program card → Delete
- B. 3D right-click → context-menu Delete
- C. Selected equipment → keyboard Delete

All three call the SAME authoritative `deleteEquipment(equipmentInstanceId)`. No duplicate delete logic; no second lifecycle. Right-click KEY deletes KEY only; KIUBE remains.

## 6. Spatial exclusivity preserved (EVI-MA-02A)

Collision/exclusivity is untouched. Deleting equipment releases its occupied volume; a subsequent placement in the released space succeeds (tested).

## 7. Files changed

- `frontend/src/components/spatial/equipmentInstance.ts` — pure `rayIntersectEquipment` + `pickNearestEquipment` (oriented-box ray pick reusing the collision envelope math).
- `frontend/src/components/spatial/MrtDirectManipulationTool.ts` — contextmenu bridge (`installEquipmentContextMenuBridge` / `removeEquipmentContextMenuBridge` / `onViewportContextMenu`) now using the pure ray pick in `locateEquipmentAtClient` (no `doLocate`).
- `frontend/src/components/spatial/assetPicking.ts` — `shouldHandleEquipmentDeleteKey` (pure).
- `frontend/src/routes/BentleyViewer.tsx` — Delete/Backspace keydown effect (authenticated-only, focus-safe, lock-aware).
- `frontend/src/tests/eviMa02bRightClickDelete.test.ts` (new).

## 8. Tests

`eviMa02bRightClickDelete.test.ts` (12 tests): focus-safety decision (canvas/body/undefined → handle; input/textarea/select/contenteditable → ignore; non-delete keys → ignore); delete-key deletes the exact selected instance and KEY≠KIUBE; locked selected → rejected (LOCKED); nothing-selected → no-op; delete releases collision volume then re-placement succeeds; distinct canonical titles (KEY vs KIUBE); **right-click ray pick** hit/miss, nearest-of-overlapping wins, hidden excluded, exact-id (KEY vs KIUBE), empty-space → no id. Full suite: **70 files / 1117 tests PASS** (+12). EVI-MA-01/02/02A/03 tests unchanged and green.

## 9. Verification

- Typecheck `tsc -b`: PASS. Production build: PASS (pre-existing advisories only).
- Full suite: 70 files / 1117 tests PASS.
- `/viewer` = **200**. WASM `public/scripts/draco_decoder.wasm` + Bentley worker `public/scripts/parse-imdl-worker.js` present.
- No backend Python changed. No tests weakened.
- Canonical dev server left RUNNING on **port 3000** (HMR applied the changes cleanly).

## 9a. Why the first EVI-MA-02B attempt still failed live

The first attempt resolved the right-click hit via `IModelApp.locateManager.doLocate` with a synthetic world point derived from `viewToWorld({z:0})`. That path is unreliable for a non-button contextmenu event (near-plane world point + a locate that expects a real button pick), so no equipment resolved and the menu never opened. This revision removes the `doLocate` dependency entirely and uses a deterministic pure ray-vs-oriented-box pick against the equipment envelopes — the same envelope math the collision system already trusts — so the resolution no longer depends on Bentley's locate/reset delivery.

## 10. Manual acceptance (do NOT self-accept)

1. Left-click IBA Cyclone KEY → selected. 2. Confirm selected. 3. Press Delete → KEY disappears, KIUBE remains. 4. Right-click KIUBE → context menu appears at cursor. 5. Title = "IBA Cyclone KIUBE". 6. Delete → KIUBE disappears. 7. Right-click a BIM wall → no equipment Delete menu. 8. Place a cyclotron in the released area → succeeds.

## 11. Stop condition

Automated verification passes; dev server running on port 3000. STOPPED for manual acceptance. Not starting PTS / RTHS / MRT animation / Build 2.

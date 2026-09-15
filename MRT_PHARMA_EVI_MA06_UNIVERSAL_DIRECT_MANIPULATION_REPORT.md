# EVI-MA-06 — Universal Application-Object Direct Manipulation

Unified picking + left-click selection + drag/drop + right-click + delete for ALL application-owned equipment and logistics assets.

**Status:** implementation complete · `manual_acceptance = PENDING` (do not self-accept)
**Scope:** the final direct-manipulation architecture build before the repository/engineering-document reconciliation audit. No Build 2, no transport routing/animation.

---

## 1. Reconcile (before any edit)

| Field | Value |
|---|---|
| Branch | `main` |
| HEAD | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| origin/main | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| Divergence | 0 ahead / 0 behind |
| Test baseline (start) | 78 files / 1232 tests passing (EVI-MA-05B) |
| Build / viewer (start) | build PASS · /viewer 200 |

All uncommitted EVI work preserved; no reset/revert/ZIP; no lifecycle-store duplication.

## 2. The problem this build fixes

Interaction was fragmented: scanner (legacy asset path), cyclotron/equipment, and vestibule each had their own target resolution, and right-click/drag repeatedly depended on family-specific event paths. This build establishes ONE resolution used by left-click, right-click, drag, and the Delete key.

> Manual testing is authoritative. Passing unit tests do NOT make this build accepted — `manual_acceptance` stays PENDING until the user tests the live browser interaction. The architecture is designed so live interaction no longer depends on fragile family-specific paths.

## 3. One interaction contract — `AppObjectPickTarget`

New pure module `appObjectPicking.ts`:
- `AppObjectType` = `EQUIPMENT_INSTANCE | CLINICAL_LOGISTICS_VESTIBULE | ASSET_INSTANCE`.
- `AppObjectPickTarget { objectType, instanceId, distance, parentBimSpaceId, draggable, deletable, hidden, locked }`.
- `AppObjectCandidate` carries the WHOLE occupied volume (OBB for equipment, AABB for a vestibule's full room-side + behind-wall extent) so every visual subcomponent resolves the ONE instance.
- `resolveAppObjectPickTarget(ray, candidates, selected?)` — the single resolution. Priority: (1) if the currently SELECTED app object is intersected by the ray, prefer it; else (2) the nearest valid app object (ties → smaller ray-t, never array order). Hidden candidates are excluded. Planning volumes and native BIM are never in the candidate set, so they can never be returned.
- `rayHitAabb` / `rayHitObb` slab tests; `isTextEditingElement` / `isTextEditingFocus` (Delete-key focus safety).

Renderer/decorator ownership is not lifecycle authority — the interaction layer never needs to know which decorator drew an object.

## 4. Unified overlay layer (delegates to existing stores)

In `spatialAssetOverlay.ts`:
- `buildAppObjectCandidates()` snapshots the live equipment (oriented occupied box) + vestibule (full occupied AABB) instances. Planning volumes / native BIM are intentionally excluded.
- `resolveAppObjectAtRay(ray)` = `resolveAppObjectPickTarget(ray, candidates, getSelectedAppObjectRef())`.
- `getSelectedAppObjectRef()` / `selectAppObject(ref)` — one selection notion over the existing per-family selection authorities (selecting one clears the other).
- `deleteAppObject(target)` — ONE dispatcher routing `EQUIPMENT_INSTANCE → deleteEquipment`, `CLINICAL_LOGISTICS_VESTIBULE → deleteVestibule`. No duplicated delete logic, no `window.confirm`. `deleteSelectedAppObject()` backs the Delete key.
- `moveEquipmentToFloorPoint(id, x, y)` → the authoritative `updateEquipmentPlacement` (collision-checked + persisted; Z pinned to the parent-room floor).
- `slideVestibuleToWallPoint(id, x, y)` → wall-tangent slide (front flush, rear behind wall), room-side collision-checked, persisted, rebuilding only its own ports.

## 5. Tool routing (`MrtDirectManipulationTool`)

Left-click selection, the right-click contextmenu bridge (`onViewportContextMenu`), and `onResetButtonUp` now all begin from the SAME `resolveAppObjectAtRay` result and route the menu by `objectType`. The former competing family-specific resolvers (`locateEquipmentAtClient`, `locateVestibuleAtClient`, `locateEquipmentTarget`, `locateVestibuleTarget`) were removed as dead code — proof the fragmentation is gone. Native BIM / planning volumes resolve to nothing, so the browser menu is left untouched (menu only suppressed for an app-owned hit).

Right-click event delivery remains hardened per EVI-MA-05B: capture-phase contextmenu bridge on the active viewport, idempotent re-install on every left-click (survives viewport remount), independent of the Clinical Program panel / equipment cards / a prior left-click.

**Delete key:** `Delete`/`Backspace` deletes the selected app object via `deleteSelectedAppObject`, but only when no gesture is active AND focus is not in an input/textarea/select/contenteditable (focus-safe), and never for a locked object (the lifecycle delete refuses).

## 6. Universal drag

`onMouseStartDrag` first resolves the unified target; if it is a draggable app object, an app-object drag begins (no second family-specific pick):
- **Freestanding equipment (scanner/cyclotron):** drags in the parent-room FLOOR PLANE (cursor ray → Z=floor plane → X/Y candidate; Z pinned to the room floor, no vertical floating). Each motion calls the authoritative collision-checked move; an invalid candidate is rejected and the instance stays at its last valid pose. Escape restores the pre-drag pose.
- **Wall-integrated vestibule:** slides ALONG its attached wall tangent only — the front face stays flush with the wall plane and the rear/manifold/MRT/PTS stay behind the wall (the wall frame is authoritative; it can never be pulled into the room). Clamped to the usable wall span. `evaluateWallSnap` supports a deliberate snap to a different defensible wall in the same room (explicit threshold + hysteresis) while keeping the same `vestibuleInstanceId`.

Existing rotation (numeric / handle) is preserved; drag/drop is not blocked on a new gizmo.

## 7. INDEPENDENT-POSE doctrine (enforced + tested)

Every application-owned instance owns and mutates only its own persisted pose. Dragging one instance never translates, rotates, re-parents, or recreates another:
- `moveEquipmentToFloorPoint`/`updateEquipmentPlacement` mutate only the one instance's `placement`; collision is checked with `excludeId` so an object never collides with its own prior position; on collision the function returns early, leaving the mover AND the neighbor unchanged.
- `slideVestibuleToWallPoint` mutates only the one vestibule (pose/frontFacePlane/reservedVolume/ports); it rebuilds only its own ports; on collision it returns early.
- Escape during an app drag restores only that instance's pre-drag pose.

Tests assert: moving/evaluating one instance leaves another's placement byte-identical; a rejected (colliding) candidate leaves both poses unchanged; `translateEquipment` returns a new placement without mutating its input.

## 8. Preserved (no regression)

Wall-integrated vestibule (EVI-MA-05B), hollow MRT/PTS passages + clearance seam, floating SELECTED EQUIPMENT / SELECTED VESTIBULE controls, per-family context menus (now opened via the one resolver), collision/exclusivity (oriented, hidden+locked reserve space), persistence, 2D markers, Bentley auth, Clinical Program. Native BIM stays immutable and non-manipulable.

## 9. Files

**New**
- `frontend/src/components/spatial/appObjectPicking.ts`
- `frontend/src/tests/eviMa06UniversalDirectManipulation.test.ts` (14 tests)

**Modified**
- `spatialAssetOverlay.ts` — unified candidates/resolve/select/delete dispatcher + equipment floor-move + vestibule wall-slide commit authorities.
- `clinicalLogisticsVestibule.ts` — `slideVestibuleAlongWall` + `evaluateWallSnap` (pure).
- `MrtDirectManipulationTool.ts` — single-resolver left/right/drag routing; Delete key; app-object drag lifecycle + Escape restore; removed the dead family-specific resolvers.

## 10. Verification

| Check | Result |
|---|---|
| `npx tsc -b` | PASS (0 errors) |
| EVI-MA-06 suite | 14 passed |
| Full frontend suite | **79 files / 1246 tests — all pass** (was 78 / 1232; +1 file, +14 tests) |
| `npm run build` | PASS (pre-existing INEFFECTIVE_DYNAMIC_IMPORT + chunk-size warnings only) |
| `/viewer` on :3000 | 200 |

Dev server left running on **port 3000**.

> Honesty note: the live browser pointer-drag, right-click event delivery, and camera-relative picking cannot be verified headlessly. The unified picker, delete dispatcher, focus-safety, equipment floor-move math + collision, vestibule wall-slide/snap math, and the independent-pose invariant are all verified by tests + typecheck + build. Live interaction is the manual acceptance step and remains authoritative.

## 11. Manual acceptance — `manual_acceptance = PENDING`

For a scanner, a cyclotron, and the Radiopharmacy vestibule: left-click selects the exact object (floating control appears); left-drag moves it (equipment in the floor plane, vestibule sliding along its wall) with a valid/invalid indication and no neighbor ever moving; right-click opens the correctly-titled menu (Fit / Hide-Show / Lock-Unlock / Delete) reliably after orbit/pan/zoom/Fit and viewport remount; Delete (menu or key) removes only that instance; locked objects are selectable/Fit/Hide but not draggable and show Delete disabled + Unlock; native BIM (wall/floor/door/furniture) exposes no application menu; persistence survives refresh; deleted objects stay deleted.

**Do not self-accept.** Do not begin PTS/MRT/RTHS/AGV routing, carrier animation, dispatch/scheduling, travel-time, or Build 2. Await explicit confirmation that left-click, drag/drop, right-click, and Delete work universally and reliably in the live browser.

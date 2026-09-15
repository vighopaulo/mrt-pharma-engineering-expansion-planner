# EVI-MA-07 — Final Spatial-Editor UX Correction

Persistent selection + exact action targeting + local object menu + Undo/Redo + canonical vestibule + physical wall openings.

**Status:** implementation complete · `manual_acceptance = PENDING` (do not self-accept)
**Boundary:** no Build 1C, no Build 2, no routing/animation.

---

## 1. Reconcile

Branch `main`, HEAD `1de2c5b`, origin/main `1de2c5b`, 0/0. 126 uncommitted paths preserved (all prior EVI work). Baseline: 80 files / 1254 tests passing, build PASS, /viewer 200. No reset/revert/ZIP.

## 2. Proven live defects (from manual acceptance)

Vestibule selectable but selection visually lost on pointer-leave; a subsequent Hide/Delete could hit the cyclotron instead of the selected vestibule; right-click unreliable; no Undo; action controls geographically disconnected from the object; front face confusing; vestibule behaved like a special subsystem, not a canonical asset.

## 3. Root causes

- **Selection loss / wrong target.** The authoritative selection state was actually already persistent — `selectEquipment`/`selectVestibule` are mutually exclusive and only mutated on explicit click (never on hover/motion), and `getSelectedAppObjectRef()` derived a single ref. The real defect was in the **UI layer**: two family-specific floating controls plus the absence of a single captured-target local menu meant actions could be dispatched against an ambiguous/stale family target, and clicks on controls could pass through to the viewport and re-pick. The fix removes the whole class by construction: one captured-target local menu whose handlers never re-raycast and always `stopPropagation`.

## 4. Authoritative SelectedAppObject + action-target capture (§3–§5, §30, §34)

The single action target is `getSelectedAppObjectRef()` (vestibule-then-equipment, mutually exclusive) surfaced as `getSelectedAppObjectView()` (exact title + hidden/locked + objectType/instanceId). Nothing clears it on hover/pointer-leave; it changes only on selecting another app object, a deliberate empty-space click (`selectAppObjectWithAnchor(undefined)`), delete of the selected object, or Escape. The decorator highlight already reads the persistent selection, so the highlight remains until selection changes. The local menu **captures** `{objectType, instanceId}` per render and every action closes over that captured target — cursor movement can never retarget an action.

## 5. Local action popover (§6, §7, §33)

`ViewerAppObjectMenu.tsx` is the ONE local popover, anchored at the click/right-click point (`selectAppObjectWithAnchor` captures the page anchor; clamped inside the viewport). It shows the exact identity + Fit / Hide-Show / Lock-Unlock / Delete for the captured target, dispatching to `fitCapturedAppObject` / `setCapturedAppObjectVisibility` / `setCapturedAppObjectLock` / `deleteCapturedAppObject`. Every handler `stopPropagation`s (pointerdown/mousedown/click) so a button click never reaches the Bentley viewport behind it — the root cause of "click Hide → acts on the object behind the button." Left-click selection and right-click both open the SAME menu (right-click only changes the anchor); the tool-independent right-click bridge (EVI-MA-06A) still resolves the target and now selects-with-anchor. Left-click remains fully sufficient if Bentley suppresses `contextmenu`.

## 6. Undo / Redo (§12–§15)

`appEditHistory.ts` is a bounded (≤100) app-owned command stack (`AppEditCommand {type, objectType, instanceId, beforeState, afterState, timestamp}`). The overlay records DELETE/HIDE/SHOW/LOCK/UNLOCK/MOVE/ROTATE via the captured-target actions and applies undo/redo through `applyAppEditCommand` (direction-aware). **Undo of DELETE re-inserts the exact snapshot** — same instanceId, canonical id, parent room, pose, yaw, hidden/lock state, ports and reserved volume (never a new id). Undo/Redo touch only app-owned state — never the Bentley iModel, BIM geometry, or camera. `ViewerUndoRedoToolbar.tsx` provides visible Undo/Redo buttons (disabled when empty) + Ctrl/Cmd+Z / Ctrl/Cmd+Shift+Z (ignored while focus is in a text field). Delete shows a non-blocking toast with inline Undo (no browser alert). History is cleared on iModel switch.

## 7. Canonical vestibule (§16–§19)

The vestibule is now an explicit canonical MRTway facility asset: `MRTWAY_CLINICAL_LOGISTICS_VESTIBULE` (family `CLINICAL_LOGISTICS_VESTIBULE`, owner MRTway Systems, visual family `CLINICAL_LOGISTICS_VESTIBULE_V1`, category `FACILITY_LOGISTICS_INTERFACE`) — not GE/IBA medical equipment. Service configurations are independent of the visual family: `MRTWAY_CLV_RADIOPHARMACY` (MRT + radiopharmaceutical-qualified PTS) plus prepared `MRTWAY_CLV_PHARMACY/LABORATORY/STERILE_CLEAN_SUPPLY/LAUNDRY_LINEN`. Each instance carries `canonicalAssetId` + `canonicalConfigId` (persisted; backfilled for pre-canonical records). §19 no-duplicate CTA: when a Radiopharmacy vestibule already exists for a cyclotron's room, the cyclotron control shows "Select Radiopharmacy Vestibule" (select + Fit) instead of a duplicate "Create."

## 8. Simplified front face + two hollow openings (§20–§27, §43)

The room-side face is now a shallow wall-flush unit: fascia, access door + handle, HMI, tri-status, e-stop, service panel — no room-side manifold clutter. It exposes TWO unmistakable, differently-shaped hollow openings, gated by the configured ports:
- **MRT** — a large RECTANGULAR metallic frame (`CLV_MRT_OPENING_FRAME`) around a recessed empty rectangular void (`CLV_MRT_OPENING_VOID`) that reads as actual hollow space.
- **PTS** — a small CIRCULAR metallic ring (`CLV_PTS_OPENING_RING`) around a recessed empty circular bore (`CLV_PTS_OPENING_VOID`).

The PTS bore is substantially smaller than the MRT tract, and they are physically separate. Behind the wall the hollow transfer chamber, MRT rectangular passage → four-planar-face reducer → trunk, and circular PTS bore/OD/ID/pig/clearance are preserved. The medium-LOD part band was raised from 15–30 to 15–40 (documented spec-driven change for the two added front openings), with the same "not overbuilt" upper bound.

## 9. Independent pose, 2D convergence, persistence (§28, §29, §38, §44)

Dragging one instance moves only it (EVI-MA-06 independent-pose doctrine, re-verified): the equipment floor-move and vestibule wall-slide each mutate only their own instance and a rejected move leaves neighbors unchanged. `sourceCyclotronId` is provenance only (no transform parenting / group move / duct). 2D marker clicks converge on the same authoritative selection (`selectVestibule`/`selectEquipment`). Independent poses, hidden/visible, and canonical identity persist across refresh.

## 10. Files

**New:** `appEditHistory.ts`, `ViewerAppObjectMenu.tsx`, `ViewerUndoRedoToolbar.tsx`, `eviMa07SpatialEditorHistoryCanonical.test.ts`, `eviMa07LocalMenuDom.test.tsx`.
**Modified:** `spatialAssetOverlay.ts` (authoritative selection view + anchor, captured-target actions, Undo/Redo + apply, canonical room accessor, history clear-on-switch), `clinicalLogisticsVestibule.ts` (canonical asset + configs + instance ids + persistence/backfill + hollow-opening-aware pose reuse), `equipmentGeometry.ts` (two hollow front-face openings + roles + palette), `MrtDirectManipulationTool.ts` (select-with-anchor on left/right click, empty-space deselect), `ViewerSelectedEquipmentControl.tsx` (no-duplicate CTA), `BentleyViewer.tsx`/`.css` (mount menu + toolbar + styles), plus two EVI-MA-05 test files (part-band + front-face role assertions updated for the simplified face — documented spec-driven, not weakening).

## 11. Tests

- `eviMa07SpatialEditorHistoryCanonical.test.ts` (13): history record/undo/redo/linear-clear/bounded/clear; canonical facility asset + independent service configs + instance canonical ids; two hollow openings (MRT rectangular non-solid void with nonzero w/h; PTS circular non-solid bore; separate; PTS ≪ MRT; gated by configured ports).
- `eviMa07LocalMenuDom.test.tsx` (7, DOM-level): menu renders the captured selection; Hide/Delete dispatch to the CAPTURED target with the exact id; button clicks `stopPropagation` (no viewport passthrough); Delete shows an Undo toast whose Undo calls `undoLastAppEdit`; locked ⇒ Delete disabled + Unlock (no silent no-op); selection persists across a store notify.

> Honesty note: live-browser selection persistence, camera Fit, and undo-delete-restore in the running Bentley viewer are not headlessly verifiable. The authoritative-selection derivation, captured-target dispatch, stopPropagation contract, Undo/Redo stack + exact-snapshot restore, canonical identity, and hollow-opening geometry are all verified by tests + typecheck + build. Live confirmation is the manual step, and it is authoritative.

## 12. Verification

| Check | Result |
|---|---|
| `npx tsc -b` | PASS (0 errors) |
| EVI-MA-07 suites | 20 passed (13 + 7) |
| Full frontend suite | **82 files / 1274 tests — all pass** (was 80 / 1254; +2 files, +20 tests) |
| `npm run build` | PASS (pre-existing INEFFECTIVE_DYNAMIC_IMPORT + chunk-size warnings only) |
| `/viewer` on :3000 | 200 |

Dev server left running on **port 3000**.

## 13. Manual acceptance — `manual_acceptance = PENDING`

Follow §46: select the vestibule and confirm it stays highlighted with the local menu near it after the cursor moves away; Hide/Show/Delete act only on the selected object; Undo restores the same instance/pose; drag moves only the dragged object; the front face shows a shallow wall-flush unit with a large rectangular hollow MRT opening and a small circular hollow PTS opening (visible void); no cyclotron connection; refresh preserves independent poses, hidden/visible, and canonical identities. If right-click is suppressed by the Bentley environment, record it honestly — left-click + the local menu provide full functionality.

**Do not self-accept.** Do not begin Build 1C, Build 2, or any routing/animation. Leave /viewer running and await manual acceptance.

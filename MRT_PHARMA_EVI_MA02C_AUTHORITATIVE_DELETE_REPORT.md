# MRT Pharma — EVI-MA-02C Authoritative Equipment Delete + Persistence

Right-click, the exact-model context menu, and Hide all work from the same menu. The remaining defect was Delete-only: choosing Delete from the context menu did not remove the equipment. This build fixes deletion at its proven root cause and makes it authoritative and persistent, without touching picking, the right-click bridge, geometry, collision, auth, walkthrough, or 2D logic.

manual_acceptance = **PENDING** (do not self-accept).

---

## 1. Proven root cause — exact failing line

`frontend/src/components/spatial/ViewerEquipmentContextMenu.tsx`, `onDelete`:

```ts
closeEquipmentContextMenu()
if (!window.confirm(`Delete ${title}? ...`)) return   // ← blocked / returns false in the embedded viewer host
const res = deleteEquipment(id)                        // ← therefore never reached
```

`window.confirm` is suppressed (returns `false`) in the embedded Bentley viewer host, so the early `return` fired and `deleteEquipment` was **never called**. The menu was also closed *before* the (never-reached) delete. **Hide has no `window.confirm` gate** — that is the exact Hide-vs-Delete divergence the observation pointed to: both paths reach the store mutation identically (`equipmentInstances = ...; persistEquipment(); notifyProgram()`), but Delete's mutation was gated behind a blocked dialog.

`deleteEquipment` itself was correct (it already filtered by id, persisted, and notified); the failure was entirely in the menu handler never invoking it.

## 2. Hide vs Delete comparison (the divergence)

| | Hide (WORKED) | Delete (FAILED before) |
|---|---|---|
| Menu handler | `setEquipmentVisibility(id, false)` directly | `if (!window.confirm(...)) return;` **then** `deleteEquipment(id)` |
| Reached the store? | Yes | **No** (confirm returned false) |
| Store mutation | `equipmentInstances=[...]; persist; notify` | identical — but never invoked |

Fix: make Delete behave like Hide — call the store mutation directly, no blocking dialog.

## 3. Fix

**Menu (`ViewerEquipmentContextMenu.onDelete`)** — calls `deleteEquipment(id)` FIRST (no `window.confirm`). On `ok` it closes the menu; on failure it keeps the menu open and shows the returned `message` (`role="alert"`). Same authoritative lifecycle as the card and keyboard Delete; no second implementation.

**`deleteEquipment` (`spatialAssetOverlay.ts`)** now returns an explicit `DeleteEquipmentResult`:
```ts
| { ok: true; deletedId: string; canonicalModelId: string }
| { ok: false; reason: 'NOT_FOUND' | 'LOCKED' | 'PERSISTENCE_FAILED' | 'INVALID_STATE'; message: string }
```
It deletes strictly by `equipmentInstanceId` (never model/family/room/label/position), asserts the collection decremented by exactly one (`INVALID_STATE` otherwise), drops the containment reservation, clears `selectedEquipmentId` if it referenced the deleted id, closes the equipment context menu if it targeted the deleted id, persists the NEW collection, and notifies subscribers. No silent returns.

## 4. Derived state clears automatically

3D geometry, envelope, 3D label, 2D marker, equipment card, and collision reservation all derive from the single `equipmentInstances` array via `getEquipmentForRender` / `getBim2dPlanView` / the card list. Removing the instance from that array + `notifyProgram()` makes all of them disappear — no separate graphical deletion.

## 5. Persistence + no resurrection

`persistEquipment()` writes the NEW collection to `mrtpharma.equipment.v1.<iModelId>`. `loadEquipmentForIModel` loads persisted instances only — there is NO seed-on-empty path, so a deleted instance is not recreated and an intentionally empty `[]` stays empty after reload. (The only reconstruction path in the overlay is the manual, duplicate-guarded Uptake 01 clinical baseline — assignment + planning volume, not equipment — and it is never triggered by delete/reload.) Proven by a persist → delete → reload test where the deleted ids remain absent.

## 6. Convergent delete entry points (one lifecycle)

- Card Delete (`ClinicalProgramControl.deleteEquipmentRow`) → `deleteEquipment(id)` (result `ok`/`reason` still handled).
- 3D right-click menu Delete → `deleteEquipment(id)`.
- Keyboard Delete (`BentleyViewer`) → `deleteEquipment(getSelectedEquipmentId())`, `LOCKED` → "Unlock equipment before deleting."

All three call the same `deleteEquipment`. No duplicate logic.

## 7. Files changed

- `frontend/src/components/spatial/spatialAssetOverlay.ts` — `DeleteEquipmentResult` + authoritative `deleteEquipment` (explicit result, decrement assertion, menu-clear).
- `frontend/src/components/spatial/ViewerEquipmentContextMenu.tsx` — `onDelete` no longer gated on `window.confirm`; processes the result; inline error.
- `frontend/src/routes/BentleyViewer.css` — context-menu error styling.
- `frontend/src/tests/eviMa02cAuthoritativeDelete.test.ts` (new).

## 8. Tests

`eviMa02cAuthoritativeDelete.test.ts` (9 tests): Hide does not remove / Delete removes exact instance; delete exactly once and only the target (KEY leaves KIUBE + PETtrace); selection clears only if the deleted id was selected; context-menu target clears on delete; NOT_FOUND for unknown id; unlocked deletes / LOCKED rejected + remains; **persist → delete → reload keeps the deleted id absent and empty stays empty**; delete releases the collision volume. Full suite: **71 files / 1126 tests PASS** (was 70 / 1117; +9). EVI-MA-01/02/02A/02B/03 suites unchanged and green.

## 9. Verification

- Typecheck `tsc -b`: PASS. Production build: PASS (pre-existing advisories only).
- `/viewer` = **200**. WASM `public/scripts/draco_decoder.wasm` + Bentley worker `public/scripts/parse-imdl-worker.js` present.
- Canonical dev server RUNNING on **port 3000**. No backend Python changed. No tests weakened.

## 10. Manual acceptance (do NOT self-accept)

1. Right-click IBA Cyclone KEY → Hide → hides. 2. Unhide. 3. Right-click KEY → Delete → KEY disappears immediately from 3D, 2D plan, and equipment cards. 4. KIUBE remains. 5. Refresh → KEY still absent. 6. Delete KIUBE. 7. Refresh → KIUBE still absent. 8. Place equipment in the released space → succeeds (if no other collision).

## 11. Stop condition

Automated verification passes; dev server running on port 3000. STOPPED for manual acceptance. Not starting PTS / RTHS / MRT animation / Build 2.

# MRT Pharma — EVI-MA-02E Hidden-Equipment Recovery (Hide must become Show)

Hide worked, but after hiding KIUBE the floating SELECTED EQUIPMENT control still showed "Hide" instead of "Show", leaving the user no obvious way to restore hidden equipment. This build fixes the stale visibility state and makes hidden equipment fully recoverable everywhere, without touching right-click, picking, Delete, collision, persistence semantics, geometry, auth, or room logic.

manual_acceptance = **PENDING** (do not self-accept).

---

## 1. Reconciled state

Branch `main`; HEAD `1de2c5b`; origin/main `1de2c5b`; divergence 0/0. All prior EVI work preserved. Test baseline before this build: 72 files / 1133 tests.

## 2. Exact stale-state root cause

`ViewerSelectedEquipmentControl` subscribed with:

```ts
const selectedId = useSyncExternalStore(subscribeClinicalProgram, getSelectedEquipmentId)
```

`useSyncExternalStore` bails out of re-rendering when the snapshot value is `Object.is`-equal to the previous. Clicking Hide flips `instance.hidden` but leaves `selectedEquipmentId` **unchanged**, so the snapshot (`getSelectedEquipmentId`) returned the same string → **no re-render** → the `inst.hidden` read below stayed stale → the button kept saying "Hide". The store mutation, persistence, and notify were all correct; only the control's snapshot didn't reflect the change.

## 3. Fix

- **Composite snapshot** (`selectedEquipmentSnapshot()` = `id | hidden | lifecycleState`): the control now re-renders whenever the SELECTED instance's `hidden` or lock state changes, not only when the selected id changes. It resolves the CURRENT instance from the authoritative collection every render (never a retained stale object). Single visibility authority: `EquipmentAssetInstance.hidden`.
- **Hide/Show toggle** on the authoritative field: `hidden===false → "Hide" → setEquipmentVisibility(id, false)`; `hidden===true → "Show" → setEquipmentVisibility(id, true)`. The title shows "· Hidden" when hidden. **Lock never gates Show** — the user can never be trapped with hidden equipment.
- **Right-click menu** Hide is now a Hide/Show toggle keyed on `target.hidden` (same authoritative field).
- **Equipment card** now shows a `Visible` / `Hidden` status; its toggle + label were already correct and re-render via the full-array subscription.
- **2D plan** keeps a SUBDUED / dashed marker for hidden equipment (retains `equipmentInstanceId`, still selectable, flagged `hidden`) instead of dropping it — so hidden equipment is recoverable and honestly shows it still occupies space. `hitTestPlanEquipment` still resolves it.

## 4. Governing semantics preserved

- **Show restores the SAME instance**: only `hidden: true→false` — same id, canonical model, room, X/Y/Z, yaw, lock state, collision reservation. No clone/reseed.
- **Hide is visual only**: hidden equipment remains in the authoritative collection AND still reserves its collision volume (`findEquipmentCollision` never skips hidden). Only Delete releases physical space. Hide ≠ Delete.
- **Persistence**: `hidden` persists (`mrtpharma.equipment.v1.<iModelId>`); Hide → refresh stays hidden, Show → refresh stays visible, same id throughout; no reseed.
- **Delete policy unchanged** (EVI-MA-02C): locked → Delete disabled; recovery path Show → Unlock → Delete (or Unlock → Show → Delete) both possible.

## 5. Files changed

- `frontend/src/components/spatial/ViewerSelectedEquipmentControl.tsx` — composite snapshot + Hide/Show toggle + Hidden title.
- `frontend/src/components/spatial/ViewerEquipmentContextMenu.tsx` — Hide/Show toggle keyed on `target.hidden`.
- `frontend/src/components/spatial/ClinicalProgramControl.tsx` — card `Visible`/`Hidden` status line.
- `frontend/src/components/spatial/bim2dPlanProjection.ts` — `PlanEquipment.hidden`; hidden equipment kept (subdued marker) not dropped.
- `frontend/src/components/spatial/Bim2dPlanPanel.tsx` — subdued/dashed hidden marker.
- `frontend/src/tests/eviMa02eHiddenEquipmentRecovery.test.ts` (new).
- `frontend/src/tests/build1bPlan2d.test.ts` — updated the one 2D projection test to the new (spec-mandated) "hidden stays recoverable" doctrine (not weakened — asserts both equipment present with the hidden one flagged).

## 6. Tests

`eviMa02eHiddenEquipmentRecovery.test.ts` (8 tests): visible→Hide label / hide flips hidden true + label Show / show flips back; same id + pose through Hide/Show; locked+hidden can be shown (lock stays); hidden remains in the collection; hidden still reserves collision (only delete releases); Hide/Show persistence round-trip with same id; 2D hidden marker keeps the same selectable id. Full suite: **73 files / 1141 tests PASS** (was 72 / 1133; +8, and one Build 1B 2D test updated to the new doctrine). All EVI-MA-01/02/02A/02B/02C/02D/03 suites green.

## 7. Verification

- Typecheck `tsc -b`: PASS. Production build: PASS (pre-existing advisories only).
- `/viewer` = **200**. WASM `public/scripts/draco_decoder.wasm` + Bentley worker `public/scripts/parse-imdl-worker.js` present.
- Canonical dev server RUNNING on **port 3000**. No backend Python changed. No tests weakened (one test updated to match the deliberate §9 behavior change).

## 8. Manual acceptance (do NOT self-accept)

1. Select KIUBE. 2. If hidden, control shows `[Fit] [Show] [Unlock] [Delete disabled]`. 3. Click Show → KIUBE reappears; button → Hide immediately. 4. Click Hide → disappears; button → Show immediately (no refresh). 5. Refresh → stays hidden + recoverable. 6. Show → refresh → stays visible. 7. While hidden, attempt overlapping placement → still rejected (collision reserved). 8. Unlock → Delete → KIUBE gone from 3D, 2D, card, floating control. 9. Refresh → absent.

## 9. Stop condition

Automated verification passes; dev server running on port 3000. STOPPED for manual acceptance. Not starting PTS / RTHS / MRT animation / Build 2.

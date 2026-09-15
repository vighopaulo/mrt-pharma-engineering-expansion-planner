# MRT Pharma — Build 1B Manual Acceptance Correction: B1B-MA-03

**Status:** BUILD 1B — IMPLEMENTED / AUTOMATED GREEN / MANUAL RETEST REQUIRED
**manual_acceptance:** PENDING
**Build 1B marked complete:** NO **Build 2 started:** NO
**Baseline commit:** `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` (branch `main`)

Continued from the current working tree only. No restart, revert, redesign, or reimplementation of Build 1A or Build 1B. B1B-MA-01 (parent-derived containment) and B1B-MA-02 (upper-storey walkthrough spawn) are treated as established and preserved.

---

## The two coupled defects (verbatim)

- **B1B-MA-03A** — The Clinical Program panel is persistently open in Walkthrough and cannot be dismissed; it obstructs the 3D scene.
- **B1B-MA-03B** — 2D floor-plan room selection is transient and silently overwritten by hover / inspection. Selecting `Radiopharmacy — 2C17 PROSTH. LAB` (Second Floor) then hovering a corridor/wall (tooltip like `1DC8 CORRIDOR`) or entering Walkthrough made the 2C17 selection disappear.

The user requirement: *select a room once, trust that selection, enter Walkthrough, dismiss the planning UI, inspect the model, and return to the same room context without the application silently forgetting or replacing what was selected.* This was **not** solved by hiding state — the UI and state authorities are made coherent.

---

## Root cause (proven from source)

### B1B-MA-03B — transient selection overwrite

`ClinicalProgramControl.sync()` (the `subscribeClinicalProgram` callback) ran, on **every** program notification:

```ts
if (o.isSelectedRoomOutsideActiveStorey()) o.setClinicalProgramSelectedSpace(undefined)
```

`notifyProgram()` fires on the selection itself, on walker/camera samples, on candidate refresh, on async footprint / exact-mesh extraction completion, on storey-chip filter changes, and on Walkthrough entry. So a deliberately-selected room whose `storeyId` was not in the current storey-chip filter was cleared the instant any of those notifications arrived (e.g. 2C17 on the Second Floor cleared when the filter was First Floor, or when a hover triggered a redraw).

The selection was **already** stored by a stable id (`programState.selectedSpaceId`). The defect was purely this behavioral auto-clear, plus a coupling: `selectedRoom` was resolved only from the storey-filtered option list, so an out-of-filter selection would collapse the room detail UI to "no room".

Not culprits (verified): `Bim2dPlanPanel` hover only sets local `hoveredId` (no store write); `BentleyViewer` `clearSelection` only clears the local Bentley inspection card. The overwrite came exclusively from the `sync()` auto-clear reacting to the redraw notifications those interactions produced.

### B1B-MA-03A — panel not dismissible in Walkthrough

`ClinicalProgramControl` always mounted fully expanded in `viewer-program-bar`, independent of camera mode, with no collapse control and no reaction to Walkthrough entry — so it obstructed the 3D scene during walkthrough with no dismiss affordance.

---

## The fix

### One authoritative selected room (B1B-MA-03B)

- **Removed** the out-of-filter auto-clear from `sync()`. The selection now persists across hover samples, walker samples, candidate refresh, footprint extraction, storey-chip changes, and Walkthrough entry.
- Added `spatialAssetOverlay.getDiscoveredRoomById(bimSpaceId)` — resolves one room from the **immutable base discovery**, independent of the storey filter. `selectedRoom` is resolved from the in-filter option **or** this authoritative fallback, so the room detail / assignment / volume / equipment UI stays intact for the persistent selection.
- The storey chip is a **filter on the dropdown options, not a selection authority**. When the selected room is outside the active filter, the dropdown still renders a labelled option for it (`… (outside current storey filter)`) so the `<select>` reflects the true selection, plus a non-destructive hint. Switching the chip to the room's floor shows it normally.
- `isSelectedRoomOutsideActiveStorey()` is now purely **informational** (drives the hint + the out-of-filter option) and documented as MUST NOT clear the selection.

All input surfaces converge on the single authority `programState.selectedSpaceId`: dropdown, 2D-plan click (`onSvgClick → setClinicalProgramSelectedSpace(hitId)`), candidate acceptance, and direct BIM reparent. **Hover ≠ selection. Panel visibility ≠ selection state.**

### Dismissible panel in Walkthrough (B1B-MA-03A)

- `getClinicalProgramSnapshot()` now returns `cameraMode` (from the existing `activeCameraMode`). Both `applyCameraMode('WALKTHROUGH')` and `enterWalkthroughAtClinicalRoom` already set it and call `notifyProgram()`, so the panel reacts through the existing subscription — no new store.
- Presentation-only `panelCollapsed` state. Entering **Walkthrough auto-collapses** the panel to a compact reopen chip (surfacing the persistent room context); returning to **Planning auto-expands** it. Auto-collapse fires only on the transition into Walkthrough (tracked via a `prevCameraMode` ref), so a user who reopens the panel mid-walkthrough is not fought.
- Explicit collapse control (`×`) + compact reopen chip. While in Walkthrough, an outside pointer-down collapses the panel (ancestry-tested window listener, **no full-screen blocker** — 3D input is never intercepted), mirroring the existing CameraModeControl walkthrough-card pattern.
- **Collapse is presentation-only.** It never resets the selected room, storey filter, assignments, planning volumes, equipment, candidates or summary. Reopening restores the exact same room context.

---

## Tests (reproduce the old overwrite path)

New file `frontend/src/tests/build1bB1bMa03SelectionAndPanel.test.tsx` — **9 tests**. They drive the **real** `ClinicalProgramControl` against a faithful in-memory overlay whose `isSelectedRoomOutsideActiveStorey` uses the real storey-filter rule, and record every write to the selection authority to prove the component never writes `undefined`.

**Reproduction proof:** with the old auto-clear temporarily re-inserted into `sync()`, **4 of the 9 tests fail** (the persistence + out-of-filter cases); with the fix all 9 pass. These are behavioral reproductions, not setter assertions.

Cases: Walkthrough entry preserves 2C17 (§22); hover / repeated notifications preserve 2C17 including the out-of-filter reproduction (§23); out-of-filter selection stays selectable + labelled with a non-destructive hint and resolvable detail, and reappears in-list on storey switch (§20/§21); Walkthrough entry auto-collapses to the chip (§25); collapse→reopen restores 2C17 + Radiopharmacy + Second Floor while still in Walkthrough (§24); explicit `×` is presentation-only (§24); return to Planning auto-expands (§25).

Four pre-existing overlay mocks (`build1a3StoreyFilterUi`, `build1a4ContainmentValidationUi`, `build1bEquipmentBindingUi`, `build1bCandidateAcceptanceUi`) gained `getDiscoveredRoomById` (the new authoritative-resolution call). No behavioral assertions changed.

---

## Verification

| Check | Result |
| --- | --- |
| Typecheck (`tsc -b`) | PASS |
| Full frontend suite | 64 files / **1036 tests**, 0 failures (baseline 63 / 1027 → +1 file, +9 tests) |
| Production build | PASS |
| Worker head | `(()=>{"use strict";f` |
| WASM magic | `0061 736d` |
| `@itwin/core-frontend` | 5.12.5 |
| `/viewer` HTTP (port 3000, clean restart) | 200 |
| Backend tests | Not run — no `.py` files changed by this fix |

Regressions preserved green: B1B-MA-01, B1B-MA-02, scanner acceptance, Radiopharmacy 2C17 assignment, storey-filter UI, candidate acceptance UI, equipment binding UI, containment validation UI.

---

## Scope review

- Changes confined to `frontend/` + this report. No backend / closed-domain (`.py`) changes by this fix.
- Pre-existing untracked `.py` files (`transport_connectivity_composition_authority.py`, `test_transport_connectivity_composition_authority.py`) are unrelated Build 2A work — untouched.
- Pre-existing uncommitted files NOT touched by this fix: `CameraModeControl.tsx`, `ClinicalProgramDecorator.ts`, `clinicalPlanningVolume.ts`, `walkNav.ts`, `walkthroughController.ts`, `LiveItwinViewer.tsx`, `BentleyViewer.tsx`, `build1aWalkthroughControlsPaneUi.test.tsx`.
- `frontend/.env` not modified by this fix (pre-existing ` M`, unstaged).
- Temporary diagnostics removed. **Not staged, not committed, not pushed.**

Files changed by this fix: `ClinicalProgramControl.tsx`, `spatialAssetOverlay.ts`, `BentleyViewer.css`, `build1a3StoreyFilterUi.test.tsx`, `build1a4ContainmentValidationUi.test.tsx`, `build1bEquipmentBindingUi.test.tsx`, `build1bCandidateAcceptanceUi.test.tsx`, `build1bB1bMa03SelectionAndPanel.test.tsx`.

---

## Manual retest path (do not declare acceptance yourself — stop for user retest)

1. Load MRTway Medical Clinic Demo; confirm `/viewer` renders at `http://localhost:3000/viewer`.
2. Select the **Second Floor** storey chip.
3. In the Clinical Program room dropdown, select **Radiopharmacy — 2C17 PROSTH. LAB**.
4. Confirm 2C17 is highlighted in the 2D floor plan and the room detail shows 2C17 / Radiopharmacy.
5. Click **Enter Walkthrough Here**.
6. Confirm the Clinical Program panel **collapses** to a compact `CLINICAL PROGRAM` reopen chip (no longer obstructing the 3D scene) and EXIT WALKTHROUGH remains reachable.
7. **Reopen** the panel via the chip while still in Walkthrough; confirm it still shows 2C17 selected, Radiopharmacy assigned, and the Second Floor filter.
8. Click / hover a corridor or wall (e.g. tooltip `1DC8 CORRIDOR`); confirm the selection is **still 2C17** (it does not disappear).
9. Click a **different** room; confirm only then does the selected room change.
10. Exit Walkthrough back to Planning; confirm the panel auto-expands and 2C17 is still selected.
11. Regression: repeat B1B-MA-01 (`2D18 TECH. OFFICE → PET/CT Scanner Room → Discovery MI`) and B1B-MA-02 (second-floor Enter Walkthrough Here spawns at eye height on the slab) to confirm both still pass.

---

## Limitations

- Auto-collapse keys off the `PLANNING → WALKTHROUGH` transition observed through the snapshot's `cameraMode`; both existing entry paths set `activeCameraMode` and call `notifyProgram()`.
- The out-of-filter selected room is shown as an extra dropdown option plus a hint; the chip still governs the rest of the option list by design (filter, not authority).
- Outside-click collapse is armed only in Walkthrough (the panel is the primary programming surface in Planning) and uses ancestry testing on a window listener, so it never intercepts 3D-scene pointer input.

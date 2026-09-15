# MRT PHARMA — BUILD 1B — TRUE 2D BIM WALKTHROUGH MAP + LABEL-DENSITY + WALKTHROUGH CONTROL UX CORRECTION

**Checkpoint:** `HOLD_FOR_BUILD_1B_UX_MANUAL_ACCEPTANCE`
Continued from the CURRENT Build 1B working tree only — no restart, no revert, no unrelated redesign, no Build 2, no backend/domain/economics/simulation/routing changes. Not staged, not committed, not pushed.

---

## 1. Terminology recorded (§2)

| Flag | Value |
|---|---|
| `PLANNING_EQUALS_PLAN_VIEW` | **NO** |
| `PLANNING_IS_WORKFLOW` | **YES** |
| `TWO_D_PLAN_IS_REPRESENTATION` | **YES** |
| `WALKTHROUGH_IS_NAVIGATION_MODE` | **YES** |

Planning is a *workflow*, not a camera. The 2D plan is a *representation* of the same authoritative BIM facts (joined by `bimSpaceId`), never a bird's-eye 3D camera reused as a plan. Walkthrough is a *navigation mode*.

---

## 2. Observed defects (provenance preserved)

1. **Label mass.** The active storey (~200 BIM spaces) rendered a permanent `<text>` label for every room with a label anchor — an unreadable mass. Runtime provenance: *200 rooms · 2 exact · 198 approx (dashed) · walker live*.
2. **Mini-plan toolbar.** The mini-plan carried a `Fit / ＋ / － / ↑ ↓ ← →` control row plus `zoom`/`panPx`/`autoFit` state. The plan should auto-fit only.
3. **Mini-plan close.** Only a collapse toggle existed (hid the body, kept the panel). No proper close, no compact reopen.
4. **Walkthrough card obstruction.** The **entire** Walkthrough control card rendered unconditionally on `mode === 'WALKTHROUGH'`. Only the small key-controls help subsection was dismissible, so the card obstructed the 3D scene with no way to clear it.

### Root cause
- *Label mass:* `Bim2dPlanPanel` drew a `<text>` for every room with a `labelAnchor`; there was no label-density policy.
- *Walkthrough card:* in `CameraModeControl` the whole `mode === 'WALKTHROUGH'` branch was unconditional; `controlsHelpOpen` governed **only** `.camera-mode-help`, never the card.

---

## 3. Changes (frontend-only)

### 3a. Pure label-density policy — `bim2dPlanProjection.ts`
Added a pure, deterministic policy (no `@itwin`, no DOM):
- `PlanLabelKind` = `'CLINICAL' | 'SELECTED' | 'HOVERED' | 'NONE'`
- `isProgramClinicalFunction(fn)` — `UNASSIGNED_EXISTING` and `undefined` are **not** program assignments.
- `clinicalBadge(fn)` — `[U]`/`[I]`/`[P]`/`[S]`/`[R]`/`[C]`.
- `resolvePlanRoomLabel(room, hoveredId?)` — **CLINICAL** always permanent (badge + name), **SELECTED** always permanent, **HOVERED** transient, else **NONE** (polygon still renders; identity available on hover/click).
- `countPermanentPlanLabels(view)` — permanent (clinical + selected) only; hover excluded.

### 3b. Mini-plan panel — `Bim2dPlanPanel.tsx`
- **Removed** the `Fit / ＋ / － / arrow` toolbar and all `zoom`/`panPx`/`autoFit` state + `fit`/`zoomBy`/`panBy` handlers.
- Labels now come from `resolvePlanRoomLabel` (Clinical Program permanent + badge; selected permanent; hovered transient; the rest unlabelled).
- Transform **always auto-fits** the active storey bounds into a compact canvas (`VIEW_W/H` 360×300 → 260×200; CSS width `clamp(200px, 22vw, 280px)`).
- The collapse toggle is replaced by a proper **× close → compact "2D Plan" reopen chip**. While closed, only the chip renders (no panel body, no SVG) — **no viewport-blocking layer**.
- Added transient hover identity (no store write).
- **Preserved:** room click selects the same `bimSpaceId` (`setClinicalProgramSelectedSpace` + `fitViewToClinicalRoom`) and never moves the walker; *Enter Walkthrough Here* uses `enterWalkthroughAtClinicalRoom` (safe spawn, no teleport-on-click); walker marker from the single walkthrough read-model; exact vs approximate (dashed) provenance and honest counts.

### 3c. Walkthrough control card — `CameraModeControl.tsx`
- Added `walkthroughCardOpen` state collapsing the **whole** walkthrough block (storeys / FOV / turn / reset / EXIT / key-controls) to a compact **"Walkthrough Controls"** reopen chip.
- **×** collapse; **Esc-first** collapse in the capture phase with `stopPropagation` (one Esc = one action) — once collapsed, Esc falls through to the controller's existing pointer-release (`FIRST_ESC_EXITS_WALKTHROUGH = NO`); **outside-click** collapse via a window `pointerdown` + `target.closest('.camera-mode')` test (**no** full-screen invisible blocker).
- **EXIT WALKTHROUGH stays reachable** while collapsed; controller pointer-release semantics untouched when already collapsed; fresh full card on each entry.

### 3d. CSS — `BentleyViewer.css`
- Removed `.bim2d-plan.collapsed` / `.bim2d-plan-collapse` / `.bim2d-plan-toolbar`; shrank plan width and SVG height.
- Added `.bim2d-plan-close`, `.bim2d-plan-reopen`, label-kind styles.
- Added `.camera-mode-walkthrough` (+ head), `.camera-mode-card-close`, `.camera-mode-walkthrough-collapsed`, `.camera-mode-card-reopen`.

---

## 4. Tests

**New:** `build1bLabelDensity.test.ts` (§22/§23/§24), `build1bWalkthroughCardUi.test.tsx` (§25 card).
**Updated:** `build1bPlan2dUi.test.tsx` (retargeted to 260×200; new §PB5 UX assertions), `build1aWalkthroughControlsPaneUi.test.tsx` (inner help pane renamed to *Walkthrough key controls*; card-level Esc/outside-click moved to the §25 suite).

- **§22 label density** — a 200-room floor yields only **2** permanent labels (clinical); **3** when one ordinary room is selected; hover is transient (excluded from `countPermanentPlanLabels`); `UNASSIGNED_EXISTING` is not a program label; badges verified.
- **§23 floor-plan geometry** — all 200 rooms project a polygon regardless of labelling; the policy never alters `ring`/`footprintSource`/`labelAnchor`; exact vs approximate preserved.
- **§24 walker immutability** — resolving every room's label does not mutate the walker read-model; density is independent of walker presence.
- **§25 mini-plan UI** — no `Fit/＋/－/arrow`; only the Clinical Program room permanently labelled (`[U] Uptake 01`); selecting adds exactly one `SELECTED` label; × closes to a compact chip with no body/SVG and reopen restores the walker; click selects same `bimSpaceId` and never moves the walker.
- **§25 walkthrough card UI** — × collapses the whole card (EXIT still reachable, not an exit); first Esc collapses (not exit to PLANNING); outside-click collapses (inside keeps open); reopen restores; EXIT works from the collapsed state.

---

## 5. Verification

| Step | Result |
|---|---|
| `npx tsc -b` | exit 0 |
| `npm run test -- --run` (isolated) | **59 files, 989 tests, all passed** |
| `npm run build` (separate) | built OK (pre-existing chunk-size + ineffective-dynamic-import advisories only) |
| worker `head -c 20 dist/scripts/parse-imdl-worker.js` | `(()=>{"use strict";f` |
| WASM `head -c 4 dist/scripts/draco_decoder.wasm` | `0061 736d` |
| `@itwin/core-frontend` version | `5.12.5` |
| dev server `curl /viewer` | **200** (clean start) |

---

## 6. Required flags

| Flag | Value |
|---|---|
| `ALL_BIM_ROOMS_PERMANENTLY_LABELLED` | NO |
| `CLINICAL_PROGRAM_ROOMS_ALWAYS_LABELLED` | YES |
| `SELECTED_ROOM_ALWAYS_LABELLED` | YES |
| `HOVERED_ROOM_LABELLED_TRANSIENTLY` | YES |
| `BIRDS_EYE_USED_AS_2D_PLAN` | NO |
| `MINI_PLAN_CONTROL_ROW_REMOVED` | YES |
| `MINI_PLAN_AUTO_FITS_ACTIVE_STOREY` | YES |
| `MINI_PLAN_DISMISSIBLE_WITH_REOPEN` | YES |
| `MINI_PLAN_BLOCKS_VIEWPORT_WHEN_CLOSED` | NO |
| `PLAN_ROOM_CLICK_SELECTS_SAME_BIMSPACEID` | YES |
| `PLAN_ROOM_CLICK_TELEPORTS` | NO |
| `WALKTHROUGH_CONTROL_CARD_DISMISSIBLE` | YES |
| `WALKTHROUGH_CARD_ESC_COLLAPSE` | YES |
| `FIRST_ESC_EXITS_WALKTHROUGH` | NO |
| `WALKTHROUGH_CARD_INVISIBLE_BLOCKER` | NO |
| `WALKTHROUGH_EXIT_REACHABLE_WHEN_COLLAPSED` | YES |
| `CANDIDATE_RECOMMENDATION_GUARD_PRESERVED` | YES |
| `EQUIPMENT_BINDING_WORK_PRESERVED` | YES |
| `WALKER_SINGLE_SOURCE_OF_TRUTH` | walkthroughController |
| `ROOM_PIPELINE_REGRESSED_TO_ZERO` | NO |

---

## 7. Preserved prior work
- **Candidate guard** (`clinicalRoomCandidate.ts`: `roomMatchesFunctionAffinity`, `hasFunctionSemanticEvidence`, recommendation cap, RECOMMENDED/SUITABLE/NEEDS_REVIEW/REJECTED) — unchanged.
- **Equipment binding** (`canonicalEquipmentCatalog.ts`, `equipmentInstance.ts`, `equipmentValidation.ts`) — unchanged.
- **Room pipeline** — `projectBim2dPlan` room projection unchanged; 200 / 2 exact / 198 approx preserved. The label policy is additive.

---

## 8. Scope review
- `git status --short`: frontend source + CSS + tests + report files only.
- **Python files changed: 0.** Backend / domain / economics / simulation / routing: **untouched**.
- `frontend/.env`: modified in the working tree from prior Build 1B state (11 added lines); **not touched or staged** by this correction.
- **Not staged, not committed, not pushed.**

---

## STOP — `HOLD_FOR_BUILD_1B_UX_MANUAL_ACCEPTANCE`
Awaiting manual acceptance. The dev server is running for review at `/viewer`.

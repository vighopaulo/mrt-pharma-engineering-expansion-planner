# MRT PHARMA — BUILD 1A WALKTHROUGH LABEL OCCLUSION + VISIBILITY CORRECTION

Manual-acceptance defect correction. Continues the CURRENT Build 1A working tree
(1A + 1A.1 + 1A.2 + 1A.3 + 1A.4 + walkthrough forward-movement/floor-constraint
correction). Build 1A is NOT restarted; Build 1B is NOT started; scope is NOT
expanded. Authority-completion remains DEFERRED pending full manual acceptance.

---

## 1. Defect (user-observed runtime evidence)

MRTway Medical Clinic Demo loaded; Walkthrough entered successfully. The
ClinicalPlanningVolume LABELS — "Uptake 01 (draft)" and "Injection Room 01
(draft)" — remained visible THROUGH walls and ACROSS other rooms while walking.
A label that should be hidden behind a wall (or far across the facility) still
floated on screen, breaking the first-person spatial read.

This is a LABEL DISPLAY defect only. The planning volumes, their world
coordinates, their parent linkage, and all domain state are correct and must not
change. Bird's-eye and Planning label behavior (persistent labels) is accepted.

## 2. Provenance chain (preserved, honest)

1. Walkthrough forward-movement previously FAILED (W dead; S/A/D/turn worked) →
   corrected offline (walkNav proximity-false-block fix; collision kept active) →
   under manual acceptance.
2. During that manual acceptance, a SEPARATE defect was observed: planning-volume
   labels render through walls in Walkthrough.
3. THIS correction fixes the LABEL DISPLAY only. It does not touch movement,
   geometry, coordinates, parent linkage, or domain state.

## 3. Root cause

- `CURRENT_LABEL_RENDERER` = `ClinicalProgramDecorator.drawPlanningLabel`, drawn
  via `context.addHtmlDecoration(div)` — a DOM overlay projected to screen space.
- `CURRENT_LABEL_ANCHOR_SOURCE` = world upper-center of the planning prism,
  projected through the viewport (`worldToView`). Anchor is WORLD-SPACE.
- `CURRENT_LABEL_VISIBILITY_POLICY_PRE_FIX` = **none**. HTML decorations have no
  depth/occlusion test — they always paint if the anchor projects on screen.
- `FIRST_BROKEN_SEAM` = the decorator had no awareness of the active CAMERA mode
  and applied no per-label visibility test.
- `ROOT_CAUSE` = **CameraMode** (`PLANNING` / `WALKTHROUGH` / `BIRDS_EYE_CUTAWAY`,
  in `cameraNav.ts`) is a SEPARATE axis from the decorator's **ViewerMode**
  (`NORMAL_PLANNING` / `DEVELOPER`, in `planningVisuals.ts`). During Walkthrough
  the ViewerMode STAYS `NORMAL_PLANNING`, so the decorator kept drawing labels,
  and HTML decorations are never occluded — hence through-wall labels.

## 4. Fix (view-only, minimum, reuses viewer visibility authority)

### 4.1 New pure policy — `walkthroughLabelVisibility.ts`
`resolveWalkthroughLabelVisibility({ cameraMode, behindCamera, onScreen,
occluded, distance, maxDistance? }) → { visible, reason }`.
- `PLANNING` / `BIRDS_EYE_CUTAWAY` → `MODE_PERSISTENT` (unchanged, always shown).
- `WALKTHROUGH` precedence: behind-camera → `HIDDEN_BEHIND_CAMERA`; off-screen →
  `HIDDEN_OFFSCREEN`; beyond max → `HIDDEN_TOO_FAR`; occluded → `HIDDEN_OCCLUDED`;
  else `VISIBLE_NEARBY`.
- Explicit named constant `WALKTHROUGH_LABEL_MAX_DISTANCE_M = 18` (no magic
  number). Helper `isPersistentLabelMode(mode)`.
- Pure, Bentley-free, deterministic, no input mutation. Anchor is never moved.

### 4.2 Camera-mode tracking — `spatialAssetOverlay.ts`
- Added `activeCameraMode` (default `'PLANNING'`), set in `applyCameraMode`, and
  `notifyProgram()` redraw so labels re-evaluate under the new mode.
- Exported `getActiveCameraMode()`; the decorator reads it via its `getCameraMode`
  input. View concern only — no iModel write, no engineering event.

### 4.3 Walk eye access — `walkthroughController.ts`
- Added `getWalkEye()` so proximity/behind-camera facts use the live walk eye.

### 4.4 Decorator wiring — `ClinicalProgramDecorator.ts`
- In `WALKTHROUGH`, `drawPlanningLabel` computes live viewport facts:
  - behind-camera: `vp.worldToNpc(world).z` outside `[0,1]`,
  - on-screen: anchor within `vp.viewRect`,
  - distance: `vp.view.getEyePoint().distance(world)`,
  - occluded: `vp.pickNearestVisibleGeometry(world)` hit is nearer than the
    anchor by > 0.25 m (fail-open to visible if pick is unavailable).
- Feeds `resolveWalkthroughLabelVisibility`; skips drawing hidden labels and
  records a bounded diagnostic reason. `PLANNING` / `BIRDS_EYE` labels unchanged.
- Anchor stays WORLD-SPACE; prism GEOMETRY still draws in Walkthrough (§14 —
  labels only). No coordinate, parent, or domain mutation.

## 5. What was explicitly NOT done

- No planning-volume move / coordinate / parent change.
- No global label deletion; labels are hidden per-frame per-label in Walkthrough
  only, and remain persistent in Planning / Bird's-eye.
- No volume hiding in Planning / Bird's-eye; no prism geometry change.
- No Bentley/iModel write; no engineering event.
- No wayfinding, no label-layout redesign, no domain-state mutation.
- Closed domains untouched (equipment, routing, transport, operations,
  simulation, animation, OpenUSD, NVIDIA, optimization, economics, What-If,
  Lockdown).
- Authority docs (`MRT_PHARMA_AUTHORITY_INDEX.md`, `MRT_PHARMA_OPEN_GAPS.md`) NOT
  updated. `BUILD_1A_AUTHORITY_COMPLETION_DEFERRED = YES`.

## 6. Verification

- Typecheck: `npx tsc -b` → PASS (0 errors).
- Tests (isolated run): **47 test files / 772 tests, 0 failures, 0 regressions**
  (baseline 45 files / 745 tests → +2 files / +27 tests this step).
  - NEW `build1aWalkthroughLabelVisibility.test.ts` — §20 pure policy (20 props).
  - NEW `build1aWalkthroughLabelVisibilityUi.test.tsx` — §21 camera-mode wiring.
  - Prior forward-fix tests (`build1aWalkthroughForward.test.ts` / `.tsx`) and all
    1A→1A.4 suites remain green.
- Production build: `npm run build` → PASS (only pre-existing benign chunk /
  dynamic-import advisories).
- Worker: `dist/scripts/parse-imdl-worker.js` head = `(()=>{"use strict";f` (real).
- WASM: `dist/scripts/draco_decoder.wasm` magic = `0061 736d` (real).
- `@itwin/core-frontend` = 5.12.5.
- Dev server restarted; `GET /viewer` → 200; left running.

## 7. Git scope

- `HEAD` = `origin/main` = `344d0289723e873c7a2974d0d8d295b38f44a6a3`; divergence 0/0.
- `frontend/.env` modified but UNSTAGED — never touched/staged.
- 0 `.py` files changed.
- This step changed: `walkthroughLabelVisibility.ts` (new), `ClinicalProgramDecorator.ts`,
  `spatialAssetOverlay.ts`, `walkthroughController.ts`, + 2 new test files, +
  this report pair. Prior 1A→1A.4 and forward-fix work preserved.
- Nothing staged, committed, or pushed.

## 8. Manual acceptance gate (STOP)

CHECKPOINT — MANUAL_CONFIRMATION_REQUIRED. Please verify in the running viewer:
- Walkthrough: "Uptake 01 (draft)" / "Injection Room 01 (draft)" no longer show
  through walls or across rooms; a label appears only when its room is genuinely
  in view, in range (≤ 18 m), and unobstructed.
- Planning + Bird's-eye: labels remain persistent (unchanged).
- Forward-fix intact: W/S/A/D + turn + Shift + floor-constraint + wall-collision.
- Clinical Program: Assigned rooms = 2, Planning volumes = 2; Uptake 01 and
  Injection Room 01 preserved.

## 9. Build 1B forward requirement (recorded only — no code this step)

Build 1B must add equipment CONTAINMENT (equipment placed inside its owning
room's planning volume with a containment check), consistent with the 1A.4
containment-validation model. No equipment code is introduced here.

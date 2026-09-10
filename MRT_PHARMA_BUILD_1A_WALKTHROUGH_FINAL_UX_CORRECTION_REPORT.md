# MRT Pharma — Build 1A Walkthrough Final UX Correction (dismissible controls + full look pitch)

**Scope:** two Walkthrough UX defects only. **No new feature; no Build 1B.**
**Precheck:** HEAD = origin/main = `344d0289723e873c7a2974d0d8d295b38f44a6a3`,
divergence `0 0`; all uncommitted Build 1A work preserved; `frontend/.env`
unstaged/excluded; zero `.py` changed; authority docs untouched.

## 1. Defect A — controls/help pane not dismissible

- `CONTROL_PANE_COMPONENT` = `CameraModeControl.tsx` (`.camera-mode-help`).
- `CONTROL_PANE_VISIBILITY_OWNER` (pre-fix) = derived purely from
  `mode === 'WALKTHROUGH'` with no dismiss state.
- `ESC_CURRENT_BEHAVIOR` (pre-fix) = handled only in
  `walkthroughController.onKeyDown` (releases pointer lock); never closed the pane.
- `OUTSIDE_CLICK_CURRENT_BEHAVIOR` (pre-fix) = none.
- `ROOT_CAUSE_CONTROLS_PANE_NOT_DISMISSIBLE` = the pane had no independent
  visibility state and no close / outside-click / Esc handler.

**Fix:** added `controlsHelpOpen` state to `CameraModeControl` (opens fresh on
entering Walkthrough; never auto-reopens on movement). The pane now renders a
`×` Close button; a capture-phase Esc handler closes it on the FIRST Esc and
consumes that keypress (so the controller's Esc pointer-release is untouched when
the pane is already closed); an outside `pointerdown` closes it (clicks inside
keep it open). When closed the pane is NOT in the DOM (a small "Controls ?"
reopen button replaces it) — so there is no invisible pointer-blocking layer.
`CONTROL_PANE_CLOSE_BUTTON = IMPLEMENTED`, `CONTROL_PANE_ESC_DISMISS = YES`,
`CONTROL_PANE_OUTSIDE_CLICK_DISMISS = YES`, `CONTROL_PANE_REOPEN = IMPLEMENTED`,
`CONTROL_PANE_AUTO_REOPENS = NO`, `CLOSED_PANE_BLOCKS_POINTER_INPUT = NO`,
`ESC_POINTER_RELEASE_PRESERVED = YES`.

## 2. Defect B — full look pitch (up + down), floor-constrained

- `CURRENT_PITCH_AUTHORITY` = `firstPerson.clampPitch` (`MAX_PITCH = 1.45` rad ≈
  83°); the controller previously duplicated an inline `Math.max(-1.45,
  min(1.45, …))` in both look paths.
- `CURRENT_PITCH_RANGE` = ±1.45 rad (already symmetric; up was mathematically
  allowed but the constant was duplicated/scattered).

**Fix:** the controller's mouse-look (pointer-lock and drag paths) now routes
pitch through the single named authority `clampPitch(pitch − movementY·SENS)`.
Dragging up (negative `movementY`) increases pitch (look up); down decreases it
(look down) — symmetric, clamped to ±`MAX_PITCH`, never inverting
(`MAX_PITCH < π/2`). `PITCH_LIMIT_AUTHORITY = firstPerson.clampPitch (MAX_PITCH)`,
`CAMERA_INVERSION_ALLOWED = NO`, `WALKTHROUGH_LOOK_UP = YES`,
`WALKTHROUGH_LOOK_DOWN = YES`.

**Floor-constrained pedestrian preserved:** `candidateEye` computes the walk
vector from yaw only (`resolveFirstPersonOrientation(yaw, 0).forwardFlat`, whose
`z = 0`) and keeps `z: eye.z`; the controller re-pins eye Z to
`eyeZForFloor(floorElevation, WALKTHROUGH_EYE_HEIGHT_M)` each frame. So looking up
or down never drives vertical translation and never accumulates Z drift.
`CAMERA_PITCH_CONTROLS_VIEW = YES`, `CAMERA_PITCH_CONTROLS_VERTICAL_TRANSLATION =
NO`, `WALKTHROUGH_MOVEMENT_MODEL = FLOOR_CONSTRAINED_PEDESTRIAN`,
`LOOK_UP_CAUSES_VERTICAL_FLIGHT = NO`, `LOOK_DOWN_CAUSES_FLOOR_PENETRATION = NO`,
`VERTICAL_DRIFT_DURING_LEVEL_WALK = NO`.

## 3. Preserved prior Walkthrough fixes

`INCREMENTAL_ZOOM_FIX_PRESERVED = YES`,
`WALKTHROUGH_LABEL_OCCLUSION_FIX_PRESERVED = YES`,
`WALKTHROUGH_FORWARD_FIX_PRESERVED = YES`,
`WALKTHROUGH_COLLISION_PRESERVED = YES` (solid-wall + floor/slab collision
unchanged; the 58 walkNav/firstPerson/cameraNav tests remain green).

## 4. Offline verification

- TYPECHECK = PASS.
- OFFLINE_TEST_FILE_COUNT = 50 · OFFLINE_TEST_COUNT = 804 · NEW_TEST_COUNT = 17
  (11 pure + 6 UI) · OFFLINE_TEST_REGRESSIONS = 0 (clean isolated run).
- PRODUCTION_BUILD = PASS (only the known harmless INEFFECTIVE_DYNAMIC_IMPORT +
  chunk-size advisories) · CORE_FRONTEND_VERSION = 5.12.5.
- WORKER_ASSET_REAL = YES (`(()=>{"use strict";f`) · DRACO_WASM_ASSET_REAL = YES
  (`0061 736d`).
- VIEWER_HTTP_STATUS = 200 (dev server restarted).

Focused tests (`build1aWalkthroughFinalUx.test.ts` +
`build1aWalkthroughControlsPaneUi.test.tsx`): pitch up/down/clamp/no-inversion;
W/S/A/D keep eye Z stable at any pitch; no Z drift over repeated steps;
`eyeZForFloor` is per-storey (no global hard-coded Z); pane close via ×, outside
click, and Esc; reopen; inside click keeps open; closed pane not in DOM.

## 5. Scope + boundaries

Changed (frontend only): `CameraModeControl.tsx` (dismissible pane),
`walkthroughController.ts` (pitch via `clampPitch`; carries prior forward/zoom/
label/diagnostic work), `walkNav.ts` (carries prior forward-collision fix),
`BentleyViewer.css` (pane close/reopen styles) + the two new test files + this
report pair. `NEW_PRODUCT_SCOPE_INTRODUCED = NO` (no equipment / routing /
transport / storey explosion / simulation / NVIDIA / economics / What-If). Zero
`.py` changed. Authority docs NOT updated (`BUILD_1A_AUTHORITY_COMPLETION_DEFERRED
= YES`; `BUILD_1A_COMPLETE = NO`). Nothing staged, committed, or pushed.

**CHECKPOINT = HOLD_FOR_FINAL_BUILD_1A_MANUAL_ACCEPTANCE.** The next activity is
ONE consolidated Build 1A manual acceptance session; only if it passes do we close
Build 1A, update the authority docs, and proceed to Build 1B (not started here).

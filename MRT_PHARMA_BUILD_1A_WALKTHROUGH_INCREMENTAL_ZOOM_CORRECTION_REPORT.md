# MRT PHARMA — BUILD 1A WALKTHROUGH INCREMENTAL ZOOM / DOLLY CORRECTION REPORT

Continuation of the current Build 1A acceptance tree (Build 1A + 1A.1 + 1A.2 +
1A.3 + 1A.4 + walkthrough forward/collision correction + walkthrough
label-occlusion correction). No new feature, no Build 1B, no scope expansion.

## DEFECT (USER-OBSERVED, VERBATIM PROVENANCE)

- Walkthrough zoom in / zoom out was **too rapid and springy**.
- A single mouse-wheel / trackpad gesture could move the user through several
  useful viewpoints (multi-scene leap).
- Zoom exhibited overshoot and **spring-back / rebound**.
- The user could not obtain small incremental zoom/dolly with immediate control
  after each step.

Desired interaction: `INPUT → BOUNDED INCREMENT → CAMERA STOPS → USER
IMMEDIATELY CHOOSES NEXT ACTION` (no overshoot, no spring-back, immediate
steering after every zoom/dolly step).

## ROOT CAUSE

`WALKTHROUGH_ZOOM_INPUT_PIPELINE_TRACED = YES`

The MRT Pharma walkthrough controller (`walkthroughController.ts`) registered
keydown / keyup / mousemove / pointerdown / pointerup / pointerlockchange
listeners but **never captured the `wheel` event**. During Walkthrough the
canvas wheel/trackpad events therefore fell through to **Bentley's default
viewport navigation** (zoom-toward-target with easing/inertia), which:

- moved the camera large, unbounded distances per gesture (multi-scene leap),
- animated with easing and could spring back / rebound,
- competed with the per-frame first-person `applyCamera()` that re-pins eye Z.

`FIRST_BROKEN_ZOOM_CONTROL_SEAM` = no wheel interception in `enterWalkthrough`.
`ROOT_CAUSE` = the walkthrough never owned the wheel; Bentley's default rapid /
eased zoom-to-target owned it.

## FIX (MINIMUM, AT THE FIRST BROKEN SEAM)

### 1. Pure bounded normalization seam — `walkNav.ts`

Added `normalizeWheelDolly({ deltaY, deltaMode }) -> number` (signed meters,
`+ = forward / zoom-in`) plus named constants:

- `WALKTHROUGH_ZOOM_BASE_STEP_M = 0.25`
- `WALKTHROUGH_ZOOM_MAX_STEP_M = 0.6` (hard per-event clamp — no multi-room leap)
- `WHEEL_LINE_TO_PIXELS = 16`, `WHEEL_PAGE_TO_PIXELS = 100`
- `WHEEL_PIXELS_PER_BASE_STEP = 100`
- `WHEEL_DELTA_MODE_PIXEL/LINE/PAGE = 0/1/2`

Properties: deterministic, finite for all finite inputs, NaN/Infinity → 0,
symmetric in sign, zero delta → zero step, trackpad high-resolution bursts
clamped to `±WALKTHROUGH_ZOOM_MAX_STEP_M`, device delta-mode normalized.

### 2. MRT Pharma Walkthrough now OWNS the wheel — `walkthroughController.ts`

- Registered `canvas.addEventListener('wheel', onWheel, { passive: false })`;
  removed in `exitWalkthrough`.
- `onWheel` calls `preventDefault()` + `stopPropagation()` (stops Bentley's
  default zoom), normalizes to a bounded step, and applies **one** incremental
  forward/back dolly, then `applyCamera()` immediately. No animation frame wait,
  no inertia, no queue, `zoomAnimationActive = false`.
- Extracted a shared `applyMove(input, distance, 'KEY' | 'WHEEL')` closure so
  keyboard walking and wheel dolly use the **identical** collision + wall-slide +
  floor-constrained path (`candidateEye` pins eye Z → no vertical free flight;
  `resolveWalkCollision` still blocks walls/windows/unknown openings/no-floor).
- Shift = faster (bounded ×2), consistent with walking.
- FOV remains on the Normal / Wide / Ultra-wide buttons (wheel is dolly, not FOV).

### 3. Movement diagnostic extended (view-only)

`WalkMovementDiag` / `diagnoseWalkthroughMovement()` now report the last raw
wheel delta, delta mode, normalized step, camera-before/after, zoom collision
result, zoom accepted/rejection reason, and `ZOOM_ANIMATION_ACTIVE = NO`.

## FILES CHANGED (THIS BUILD)

- `frontend/src/components/spatial/walkNav.ts` (pure normalization seam)
- `frontend/src/components/spatial/walkthroughController.ts` (wheel ownership +
  shared `applyMove` + diagnostic)
- `frontend/src/tests/build1aWalkthroughZoom.test.ts` (new, pure §22 + §23)

No `.py` files changed. No Bentley writes. `.env` untouched. Nothing staged.

## VERIFICATION (AUTOMATED)

- TYPECHECK: PASS (`npx tsc -b`).
- FULL ISOLATED SUITE: **48 test files / 787 tests / 0 failures / 0 regressions**
  (baseline 47 / 772 → +1 file, +15 tests).
- PRODUCTION BUILD: PASS (`npm run build`, warnings are pre-existing chunking
  advisories only).
- WORKER: `dist/scripts/parse-imdl-worker.js` head = `(()=>{"use strict";f`.
- DRACO WASM: `dist/scripts/draco_decoder.wasm` magic = `0061 736d`.
- `@itwin/core-frontend` = `5.12.5`.
- DEV SERVER restarted (stale process stopped, fresh started); `/viewer` = 200.

## MANUAL ACCEPTANCE — REQUIRED, NOT PERFORMED BY AGENT

The following runtime gates require a human at the running viewer and are
**MANUAL_CONFIRMATION_REQUIRED** (never auto-marked PASS):

- §31 Incremental zoom: one wheel/trackpad notch = one small bounded dolly step.
- §32 Repeated steps accumulate smoothly (no acceleration, no runaway).
- §33 No spring-back / no rebound / no overshoot after any step.
- §34 Immediate steering (W/A/S/D, arrows turn, drag look) right after a zoom step.
- §35 Floor constraint + wall collision preserved during dolly (no fly, no pass-through).

`CHECKPOINT = HOLD_FOR_BUILD_1A_WALKTHROUGH_ZOOM_MANUAL_ACCEPTANCE`

## PRESERVED (NO REGRESSION)

- Walkthrough forward/collision correction (`resolveWalkCollision`
  approaching-within-band logic) — unchanged.
- Floor-constrained pedestrian (`candidateEye` keeps `z: eye.z`) — unchanged.
- Walkthrough label-occlusion correction — unchanged.
- W/S walk, A/D strafe, ←/→ turn, Shift faster, drag look, Esc release — intact.
- §13 no free flight re-introduced.

## RECORD-ONLY (NOT IMPLEMENTED THIS BUILD)

- §18 / §39 Build 1B equipment-containment requirement — recorded only.
- §38 Storey isolation / exploded-view — recorded as future, not implemented.
- §40 `BUILD_1A_AUTHORITY_COMPLETION_DEFERRED = YES`. Authority index / open-gaps
  docs NOT updated (Build 1A completion is manual-gated per §15/§17).
- `FULL_PET_DEPARTMENT_COMPLETE = NO`, `EQUIPMENT_BINDING_COMPLETE = NO`.
- `NEXT_BUILD = BUILD_1B_COMPLETE_CLINICAL_PROGRAM_AND_EQUIPMENT_BINDING` (not started).

## GIT

- HEAD = origin/main = `344d0289723e873c7a2974d0d8d295b38f44a6a3`; divergence 0/0.
- No stage, no commit, no push. No reset/revert/clean/stash/rebase.

# MRT Pharma — MacBook Walkthrough Steering + Final Navigation Acceptance

Baseline `HEAD = origin/main = b2abe6bf28056d002d140b52fb54e94c9cd417eb`, `0 / 0`, nothing staged. Input-mapping correction only — the accepted first-person camera was **not** rewritten. View-only; no Bentley writes. `NAVIGATION_BASELINE = HOLD_FOR_MANUAL_ACCEPTANCE`; `CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE`.

## MacBook steering — root cause + fix

`MACBOOK_TRACKPAD_FINE_STEERING_ROOT_CAUSE`: steering depended on pointer-lock `movementX`. On Apple trackpads, pointer-lock deltas are unreliable/absent (one-finger motion without a button often produces no `mousemove`; locked deltas are inconsistent on macOS Safari/Chrome). The product cannot rely on pointer lock as the only fine-steering path.

Fix (input mapping; camera architecture unchanged, `FIRST_PERSON_CAMERA_ARCHITECTURE_CHANGED = NO`):
- **Continuous time-based arrow-key yaw** (Left/Right) — the reliable primary steering. `resolveKeyboardYaw` integrates `yaw += dir * yawRate * dt` in the update loop: frame-rate independent, no quantization, no OS key-repeat dependence (keydown marks active, loop integrates by elapsed time, keyup clears). Opposing keys neutral. Rate configurable (1.4 rad/s). Arrow keys `preventDefault` to stop page scroll. `LEFT_RIGHT_ARROW_ROLE = CONTINUOUS_YAW`.
- **Click-drag look fallback** — pointer-down + drag on the canvas rotates first-person yaw/pitch (no pointer lock). `TRACKPAD_CLICK_DRAG_LOOK = IMPLEMENTED`.
- **Pointer lock no longer forced**; an external mouse can still lock by clicking. `WALKTHROUGH_CAMERA_INPUT_OWNER = FIRST_PERSON_CONTROLLER`.
- `WASD_SEMANTICS = PRESERVED` (A/D strafe, arrow-up/down + W/S walk).
- MacBook help line: `W/S Walk · A/D Strafe · ←/→ Turn · Shift Faster · Drag to look · Esc release`.
- `KEYBOARD_PITCH_FALLBACK = DEFERRED_WITH_REASON` (drag-look already gives pitch; a modifier+arrow mapping was deferred to avoid conflicting with accepted arrow-up/down = forward/back).

## Navigation acceptance freeze gate
Pure `resolveNavigationAcceptance(results)` returns `ACCEPTED` only when all 13 mandatory items PASS, else `NOT_ACCEPTED` + explicit blockers. Offline-tested: all-pass ⇒ ACCEPTED; wall / MacBook-steering / cutaway failure ⇒ NOT_ACCEPTED with the blocker. `NAVIGATION_BASELINE = HOLD_FOR_MANUAL_ACCEPTANCE` (becomes `ACCEPTED_FOR_DEMO_BASELINE` only after your manual pass).

## Preserved (regressions = 0)
Wall collision architecture, door-constrained traversal policy, bird's-eye storeys-only selector (`ROOM_BUTTON_COUNT = 0`), storey cutaway, TURN AROUND, FOV presets, Planning input restoration, Project BIM persistence, equipment interaction.

## Machine verification
```
TYPECHECK = PASS   OFFLINE_TEST_COUNT = 427   NEW_TEST_COUNT = 10   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5   WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES   /viewer = 200
BENTLEY_WRITE_API_CALL_COUNT = 0   IMODEL_MODIFIED = NO   ACTIVE_BIM_PERSISTENCE_CHANGED = NO
EQUIPMENT_PIPELINE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO   AUTH_FLOW_CHANGED = NO
WALKTHROUGH_FOUNDATION_REGRESSION = 0   PROJECT_BIM_REGRESSION = 0   EQUIPMENT_INTERACTION_REGRESSION = 0
```
All keyboard-yaw + acceptance offline tests PASS. All MANUAL_* = MANUAL_CONFIRMATION_REQUIRED.

## Manual acceptance (STOP — the freeze gate)
On the MacBook, in Walkthrough: tap Right/Left arrow → small heading correction; hold → smooth continuous turn; partial turn then W walks the new heading; A/D strafe (not turn); drag-look works; solid wall blocks (hold W), real door passes, same wall away from door blocks, window blocks; TURN AROUND; FOV Normal/Wide/Ultra-wide. Bird's-eye: All Building, storeys-only list, First vs Second floor cutaways distinct, All Building restores, return to Planning clean. Only if all mandatory items pass do we set `NAVIGATION_BASELINE = ACCEPTED_FOR_DEMO_BASELINE` and freeze navigation; the next build is the Clinical Program Overlay + Room Repurposing.

## Honest caveats
Arrow-key yaw is the reliable steering; **raw trackpad continuous look is only partial** (works when the browser delivers trackpad `mousemove`) and is not relied upon — the click-drag fallback + arrow keys are the dependable paths. Keyboard-pitch is deferred (drag-look covers pitch). The runtime input/feel runs only in your browser (the yaw math + acceptance policy are fully unit-tested, 427 total, +10) — the on-MacBook feel is the manual-acceptance call; `KEYBOARD_YAW_RATE_RAD_PER_S` and `MOUSE_LOOK_SENSITIVITY` are single tunable constants if turning feels too fast/slow.

Files modified: `walkNav.ts`, `walkNav.test.ts`, `walkthroughController.ts`, `CameraModeControl.tsx`, `BentleyViewer.css`. Nothing staged/committed/pushed.

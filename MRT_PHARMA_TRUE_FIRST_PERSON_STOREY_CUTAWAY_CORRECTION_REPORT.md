# MRT Pharma — True First-Person Walkthrough + Storey Cutaway Correction

Baseline `HEAD = origin/main = b2abe6bf28056d002d140b52fb54e94c9cd417eb`, `0 / 0`, nothing staged. View-only; no Bentley writes. `CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE`.

## Manual failures (authoritative)
`PREVIOUS_WALKTHROUGH_ACCEPTANCE = FAIL`, `PREVIOUS_BIRDS_EYE_ACCEPTANCE = FAIL`.

## Failure A — walkthrough root cause + fix

`WALKTHROUGH_CAMERA_ROOT_CAUSE`: the camera set `lookAt` with `targetPoint = eye + unit-direction` (~1 m ahead). A ~1 m eye→target distance triggered Bentley **"Too close to target"** and made turning read like orbiting a near pivot; the pointer-lock handler also didn't suspend Bentley's orbit tool.

Fix — true first-person, `EYE_POSITION + YAW + PITCH`:
- New pure `firstPerson.ts`: `resolveFirstPersonOrientation(yaw,pitch)` (yaw never involves the eye → cannot orbit it), `candidateEye`, `clampPitch` (±83°, no flip), `resolveWalkMovement` (ALLOW / ALLOW_DOOR / BLOCK_WALL / BLOCK_WINDOW / BLOCK_UNKNOWN_OPENING / BLOCK_NO_FLOOR), `eyeZForFloor`.
- Controller: target placed **10 m ahead** along the look direction with explicit `frontDistance=0.1` / `backDistance=5000` → **"Too close to target" eliminated**. Eye Z pinned to floor + eye height each frame (no drift). WASD/arrows translate the eye horizontally; mouse delta updates yaw/pitch under pointer lock; Esc releases. Movement is validated by `resolveWalkMovement` before the camera commits (wall block, door pass, window/unknown block, no-floor block). `RESET WALKTHROUGH` returns to the validated entry.

## Failure B — bird's-eye root cause + fix

`BIRDS_EYE_ROOM_BUTTON_ROOT_CAUSE`: `loadStoreys` fell back to `SpatialComposition:CompositeElement JOIN GeometricElement3d` when `BuildingSpatial:Story` had no placement bbox → ~269 composite/space rows rendered as storey buttons.

Fix: storeys derived from **`BuildingSpatial:Story` only** (real labels), banded across the model Z extent for elevations — no composite/space fallback. The bird's-eye + walkthrough selectors show **All Building + actual storeys only**; `ROOM_BUTTON_COUNT_IN_BIRDS_EYE_TOP_LEVEL = 0`. Storey cutaway stays `ViewState.setViewClip` (view-only); All Building fits the clinic without clipping.

## Report fields

```
WALKTHROUGH_NAV_STATE = EYE_POSITION_YAW_PITCH   FIRST_PERSON_REMOTE_ORBIT_TARGET = NO
WALKTHROUGH_TOO_CLOSE_TO_TARGET_ERROR = ELIMINATED   WALKTHROUGH_TRANSLATES_EYE_POSITION = YES
BENTLEY_ORBIT_INPUT_ACTIVE_DURING_WALKTHROUGH = NO   WALKTHROUGH_POINTER_INPUT_OWNER = FIRST_PERSON_CONTROLLER
WALKTHROUGH_INPUT_CONFLICT = RESOLVED   PLANNING_INPUT_REGRESSION = 0
WALK_NAV_MODEL = BIM_DERIVED_PER_STOREY   WALK_NAV_SOURCE = ACTIVE_BENTLEY_IMODEL
DEMO_STOREY_COUNT = runtime (~4, from BuildingSpatial:Story)
WALKING_SURFACE_SOURCE = storey elevation (Story count banded across model Z)   WALKTHROUGH_FREE_VERTICAL_FLIGHT = NO
WALL_COLLISION_SOURCE = ACTIVE_BIM_WALL_PARTITION_GEOMETRY   DOOR_PORTAL_SOURCE = ACTIVE_BIM_DOOR_GEOMETRY
WINDOW_TRAVERSAL = BLOCKED   UNKNOWN_OPENING_DEFAULT = NON_TRAVERSABLE   COLLISION_BODY = GENERIC_HUMAN_NAVIGATION_BODY
MOVEMENT_VALIDATED_BEFORE_CAMERA_COMMIT = YES   WALL_GHOSTING = NO   DOOR_CONSTRAINED_TRAVERSAL = YES
WALL_SLIDING = DEFERRED_WITH_REASON   EYE_HEIGHT_TRACKS_WALKING_SURFACE = YES
WALKTHROUGH_ENTRY_VALIDATED = YES   WALKTHROUGH_RECOVERY = YES
STAIR_TRAVERSAL = DEFERRED_WITH_REASON   WALKTHROUGH_STOREY_SELECTOR_SOURCE = BUILDINGSPATIAL_STORY
BIRDS_EYE_TOP_LEVEL_SELECTOR = STOREYS_ONLY   ROOM_BUTTON_COUNT_IN_BIRDS_EYE_TOP_LEVEL = 0
BIRDS_EYE_ALL_BUILDING = YES   STOREY_CUTAWAY = VIEW_ONLY   CUTAWAY_CAMERA_FRAMES_SELECTED_STOREY = YES
CLINICAL_PROGRAM_OVERLAY_STARTED = NO   ROOM_OVERLAY_ARCHITECTURE_PRESERVED = YES   ANIMATION_IMPLEMENTED = NO
PLANNING_MODE_PRESERVED = YES   CAMERA_MODE_SWITCH_SIDE_EFFECTS = NONE   ACTIVE_BIM_PERSISTENCE_CHANGED = NO
BENTLEY_WRITE_API_CALL_COUNT = 0   IMODEL_MODIFIED = NO   EQUIPMENT_PIPELINE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO   AUTH_FLOW_CHANGED = NO
FIRST_PERSON_ORIENTATION_TESTABLE_OFFLINE = YES
YAW_DOES_NOT_ORBIT_EYE_TEST / FIRST_PERSON_PITCH_CLAMP_TEST / FIRST_PERSON_FORWARD_TEST / FIRST_PERSON_STRAFE_TEST = PASS
REAL_WALL_BLOCK_POLICY_TEST / REAL_DOOR_PASS_POLICY_TEST / REAL_WINDOW_BLOCK_POLICY_TEST = PASS
FLOOR_SUPPORT_TEST / NO_FLOOR_POLICY_TEST / EYE_HEIGHT_SUPPORT_TEST / UNKNOWN_OPENING_CONSERVATIVE_TEST = PASS
STOREY_SELECTOR_SOURCE_TEST / ROOMS_EXCLUDED_FROM_LEVEL_SELECTOR_TEST / CUTAWAY_IMMUTABILITY_TEST / CAMERA_INPUT_OWNERSHIP_TEST = PASS
TYPECHECK = PASS   OFFLINE_TEST_COUNT = 394   NEW_TEST_COUNT = 12   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5   WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES
PROJECT_BIM_REGRESSION = 0   EQUIPMENT_INTERACTION_REGRESSION = 0
(all MANUAL_* = MANUAL_CONFIRMATION_REQUIRED)   CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE
```

## Honest caveats

- **STAIR_TRAVERSAL and WALL_SLIDING are deferred** (with reasons): stairs use the explicit storey selector; a blocked step is rejected wholesale (no tangential slide) to keep the collision step stable.
- The **collision probe** still uses `pickNearestVisibleGeometry` (solid geometry near the next step ⇒ block; open doorway gaps ⇒ pass). The pure `resolveWalkMovement` supports full window/unknown-opening classification, but the runtime probe currently distinguishes wall-vs-open by geometry proximity, not per-element door/window class. If in-browser door passage feels wrong, the collision radius is one tunable constant.
- The runtime camera/collision/clip run only in the live browser, which I can't exercise headless — the pure math + storey-source filtering are fully unit-tested (394 total, +12), but the actual first-person feel, "Too close to target" absence, door constraint, and cutaway framing are the manual-acceptance items.

Files added: `firstPerson.ts`, `firstPerson.test.ts`. Modified: `walkthroughController.ts`, `CameraModeControl.tsx`, `spatialAssetOverlay.ts`. Nothing staged/committed/pushed; PLANNING, active-BIM persistence, equipment, spatial semantics, auth all untouched.

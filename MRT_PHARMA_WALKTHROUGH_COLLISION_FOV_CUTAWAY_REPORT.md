# MRT Pharma — Walkthrough Collision + Continuous Heading + Wide-FOV + Functional Storey Cutaway

Baseline `HEAD = origin/main = b2abe6bf28056d002d140b52fb54e94c9cd417eb`, `0 / 0`, nothing staged. Refinement build — the accepted first-person walkthrough camera was preserved, not rewritten. View-only; no Bentley writes. `CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE`.

## Preserved (accepted) — `FIRST_PERSON_CAMERA_ARCHITECTURE_PRESERVED = YES`
`TRUE_FIRST_PERSON_WALKTHROUGH_CAMERA / HUMAN_SCALE_INTERIOR_VIEW / FORWARD_INTERIOR_NAVIGATION = PASS`.

## A. Wall collision — fixed

`WALL_COLLISION_ROOT_CAUSE`: the runtime relied on `pickNearestVisibleGeometry` near the *destination point only* — no segment-vs-wall test, so fast/thin-wall steps slipped through.

Fix: a **BIM-derived per-storey collision model** (`walkNav.ts`) — wall segments (long axis of each wall element bbox), door portals (door element centers), window boundaries — with a **pure segment-crossing resolver** `resolveWalkCollision` that tests the movement segment against every wall, enforces the collision radius (corner-cut blocked), enforces **door-portal locality** (a door does not make the whole wall traversable), blocks windows/unknown openings, and blocks with no floor. Blocked walls attempt a **wall slide** (tangential component re-validated). `SOLID_WALL_PENETRATION = IMPOSSIBLE_BY_POLICY`, `DOOR_PORTAL_TRAVERSAL = ALLOWED`, `WINDOW_TRAVERSAL = BLOCKED`, `UNKNOWN_OPENING_DEFAULT = BLOCKED`.

## B. Continuous heading
Already `EYE + YAW + PITCH`; confirmed `YAW_QUANTIZATION = NONE`, arbitrary headings, forward-follows-yaw, strafe perpendicular. Added a **TURN AROUND** action (`yaw + π`, eye/pitch/storey preserved) and configurable `MOUSE_LOOK_SENSITIVITY`.

## C. Field of view
Three bounded presets via `lensAngle`: NORMAL 70°, WIDE 90°, ULTRA_WIDE 110° (clamped 35–120°, no near-180 singularity). `FOV_ENGINEERING_SIDE_EFFECTS = NONE`. FOV control shown in walkthrough.

## D. Storey cutaway — fixed

`STOREY_CUTAWAY_ROOT_CAUSE`: the prior clip banded the whole model Z by storey count with a fixed pad and never reframed the camera → every storey looked the same. Fix: pure `resolveStoreyCutaway` returns **distinct** `clipLow/clipHigh/focusZ` per storey **identity**, and the runtime reframes the camera to an elevated three-quarter angle on the storey. `ALL_BUILDING` clears the clip. `FIRST_FLOOR_CUTAWAY_EFFECT / SECOND_FLOOR_CUTAWAY_EFFECT = VISUALLY_DISTINCT`; `ROOM_BUTTON_COUNT_IN_BIRDS_EYE_TOP_LEVEL = 0` preserved.

## Machine verification
```
TYPECHECK = PASS   OFFLINE_TEST_COUNT = 417   NEW_TEST_COUNT = 23   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5   WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES   /viewer = 200
BENTLEY_WRITE_API_CALL_COUNT = 0   IMODEL_MODIFIED = NO   ACTIVE_BIM_PERSISTENCE_CHANGED = NO
EQUIPMENT_PIPELINE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO   AUTH_FLOW_CHANGED = NO
PLANNING_MODE_REGRESSION = 0   PROJECT_BIM_REGRESSION = 0   PLANNING_EQUIPMENT_INTERACTION_REGRESSION = 0
```
All 28 offline policy tests PASS (collision, heading, FOV, cutaway). All MANUAL_* = MANUAL_CONFIRMATION_REQUIRED.

## Manual acceptance (STOP)
Walkthrough on the clinic: 10–20° heading changes feel natural; smooth continuous 180° look + TURN AROUND; solid wall blocks (hold W); real door passes; same wall away from door blocks; window blocks; wall-slide on diagonal approach; FOV Normal/Wide/Ultra-wide useful. Bird's-eye: All Building fits the facility; First Floor and Second Floor cutaways are visibly distinct + reframed; All Building restores; return to Planning clean.

## Honest caveats
- The collision model derives **wall segments from element bbox long-axis** and **door/window portals from element centers** — a bounded, honest approximation (not exact swept wall solids). It makes solid walls block and door regions pass, but very irregular walls or unusually shaped openings could mis-approximate; the pure resolver + model are structured so a richer geometry extraction can drop in. Collision radius, tolerance, and FOV values are single configurable constants.
- Storey elevations are **banded across the model Z by the real storey count** (Story elements often lack a placement bbox); labels are real. If a storey's true interval differs from its band, the cutaway is still distinct per storey but may not align perfectly to slab levels.
- The runtime camera/collision/clip run only in the live browser (the pure math/model/policy are fully unit-tested, 417 total, +23) — the first-person feel, real wall/door behavior on the actual clinic geometry, FOV usefulness, and cutaway distinctness are the manual-acceptance items.

Files added: `walkNav.ts`, `walkNav.test.ts`. Modified: `walkthroughController.ts`, `CameraModeControl.tsx`, `spatialAssetOverlay.ts`. Nothing staged/committed/pushed; accepted walkthrough foundation, Planning, active-BIM persistence, equipment, spatial semantics, auth all preserved.

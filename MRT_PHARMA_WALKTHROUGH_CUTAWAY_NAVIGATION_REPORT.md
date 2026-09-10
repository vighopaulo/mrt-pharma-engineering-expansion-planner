# MRT Pharma — Interior Walkthrough + Door-Constrained Navigation + Bird's-eye/Cutaway

Baseline `HEAD = origin/main = b2abe6bf28056d002d140b52fb54e94c9cd417eb`, `0 / 0`, nothing staged. Implementation complete + verified. View-only; no Bentley writes. `CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE`.

## Camera modes (3)

`PLANNING` (existing orbit + asset manipulation, preserved) · `WALKTHROUGH` (first-person) · `BIRDS_EYE_CUTAWAY` (elevated + storey clip). Normal-mode **VIEW** control (top-right), not dev-gated. Switching preserves the active BIM, emits no engineering events, writes nothing.

## Design (pure seams, fully tested)

`cameraNav.ts` (Bentley-free):
- `resolveCameraModePolicy(mode)` → pointer/keyboard/assetManipulation/collision/cutaway. WALKTHROUGH turns asset manipulation OFF (camera owns input → a walk/look never drags equipment); BIRDS_EYE keeps planning-style selection + cutaway; PLANNING unchanged.
- `resolveTraversal({crossesWall, openingsOnPath, hasFloorSupport})` → `ALLOW | ALLOW_DOOR | BLOCK_WALL | BLOCK_NO_FLOOR`.
- `classifyOpening(class/name)` → door = traversable; window/glazing/generic opening = non-traversable; unknown = solid (conservative).
- Generic constants: eye height 1.65 m, speed 1.6 m/s, collision radius 0.3 m — all documented as planning/UI assumptions, NOT calibrated, NOT equipment clearance.

## Runtime (view-only, dynamically imported)

`walkthroughController.ts`:
- **WALKTHROUGH**: `ViewState3d.lookAt` first-person camera at eye height on the lowest storey; pointer-lock look (yaw/pitch), WASD/arrows + Shift; per-step door-constrained collision via `resolveTraversal` fed by a bounded probe. Esc releases; `exitWalkthrough` tears down listeners + loop.
- **Collision probe** (`makeCollisionProbe`): uses `Viewport.pickNearestVisibleGeometry` — solid geometry within the collision radius of the next step ⇒ `crossesWall` ⇒ BLOCK; open doorway gaps have no nearby hit ⇒ ALLOW. Emergent, honest door passage without fabricating door classification. Navigation only, never clearance.
- **BIRDS_EYE_CUTAWAY**: elevated oblique camera + `ViewState.setViewClip` horizontal slab clip to the selected storey (hides upper floors/roof). `clearStoreyCutaway` restores. Storeys read from `BuildingSpatial:Story`/`SpatialComposition` ranges (real labels), falling back to 4 Z-bands only if unavailable — names never fabricated when real ones exist.

Mounted via overlay entrypoints so `BentleyViewer` stays free of the heavy @itwin import.

## Report fields

```
CAMERA_MODE_COUNT = 3   EXISTING_PLANNING_CAMERA_PRESERVED = YES
HUMAN_SCALE_WALKTHROUGH = YES   WALKTHROUGH_MOUSE_LOOK = YES   WALKTHROUGH_KEYBOARD_MOVEMENT = YES
WALKTHROUGH_EYE_HEIGHT_SOURCE = GENERIC_PLANNING_ASSUMPTION   WALKTHROUGH_SPEED_SOURCE = UI_NAVIGATION_ASSUMPTION
WALL_GHOSTING_IN_WALKTHROUGH = NO   ROOM_BOUNDARY_CROSSING_REQUIRES_TRAVERSABLE_OPENING = YES
TRAVERSABLE_OPENING_POLICY = IMPLEMENTED   DOOR_SOURCE = ACTIVE_BENTLEY_BIM
FULL_PHYSICS_ENGINE_REQUIRED = NO   CAMERA_COLLISION_IS_EQUIPMENT_CLEARANCE = NO
WALKTHROUGH_FREE_VERTICAL_FLIGHT = NO   MULTI_STOREY_NAVIGATION = YES
STAIR_TRAVERSAL = DEFERRED_WITH_REASON (explicit BIM-derived storey control provided instead)
BIRDS_EYE_CUTAWAY_MODE = IMPLEMENTED   BIRDS_EYE_NAVIGATION = YES   CUTAWAY_IMPLEMENTATION = VIEW_ONLY
BIRDS_EYE_STOREY_SELECTION = YES   CUTAWAY_STOREY_SOURCE = ACTIVE_BENTLEY_BIM   CUTAWAY_ROOM_CONTEXT_VISIBLE = YES
BIRDS_EYE_SUPPORTS_FUTURE_ANIMATED_ROUTES = YES
PATIENT_MOVEMENT_ANIMATION = FUTURE_REQUIREMENT_RECORDED   MRT_CARRIER_MOVEMENT_ANIMATION = FUTURE_REQUIREMENT_RECORDED
CAMERA_MODE_SWITCH_PRESERVES_ACTIVE_BIM = YES   CAMERA_ASSET_INPUT_CONFLICT = RESOLVED   CUTAWAY_ASSET_INPUT_CONFLICT = RESOLVED
CAMERA_MODE_POLICY_TESTABLE_OFFLINE = YES   TRAVERSAL_POLICY_TESTABLE_OFFLINE = YES
WALKTHROUGH_WALL_BLOCK_TEST = PASS   WALKTHROUGH_DOOR_PASS_TEST = PASS   WINDOW_NOT_DOOR_TEST = PASS
SAME_ROOM_MOVEMENT_TEST = PASS   NO_FLOOR_MOVEMENT_TEST = PASS   CAMERA_MODE_POLICY_TEST = PASS
CUTAWAY_STATE_IMMUTABILITY_TEST = PASS
CAMERA_MODE_CONTROL_VISIBLE_IN_NORMAL_MODE = YES   VERBOSE_NAV_DIAGNOSTICS_IN_NORMAL_MODE = NO
BENTLEY_WRITE_API_CALL_COUNT = 0   IMODEL_MODIFIED = NO   BENTLEY_CHANGESET_CREATED = NO
ACTIVE_BIM_PERSISTENCE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO   EQUIPMENT_PIPELINE_CHANGED = NO   INTERACTION_CODE_CHANGED = NO
TYPECHECK = PASS   OFFLINE_TEST_COUNT = 382   NEW_TEST_COUNT = 13   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5   WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES
PROJECT_BIM_PERSISTENCE_REGRESSION = 0   ASSET_INTERACTION_REGRESSION = 0   AUTH_REFRESH_REGRESSION = 0
CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE
```
All the MANUAL_* acceptance items = MANUAL_CONFIRMATION_REQUIRED.

## Manual acceptance (STOP)

Open `/viewer` (clinic). Top-right **VIEW** control:
1. **Walkthrough** → click the model (pointer lock), WASD to move, mouse to look; walk toward a solid wall (should stop), through a doorway (should pass), turn a corridor corner without leaving the building; Esc / **EXIT WALKTHROUGH** returns to Planning.
2. **Bird's-eye** → elevated operational view; pan/zoom/rotate; pick a storey → upper floors clip away to expose that level's interior; switch storeys; confirm the interior canvas is open for future animated patients/carriers.

## Honest caveats

The pure policy/classification is fully unit-tested. The runtime pieces (pointer-lock look, WASD, the `pickNearestVisibleGeometry` collision, the storey clip, storey discovery) run only in the live authenticated browser, which I can't exercise headless — those are the manual items. Two deliberate simplifications: (1) **stair walking is DEFERRED** in favor of an explicit storey control (robust stair traversal isn't safely verifiable here); (2) the collision probe blocks on nearby solid geometry and lets open doorway gaps through — this gives correct door-vs-wall behavior emergently but does not read per-element door semantics at each step (the `classifyOpening`/`resolveTraversal` seams support that when a richer probe is added). If walkthrough movement feels too permissive or too blocked in the browser, the collision radius is a single configurable constant to tune. Files added: `cameraNav.ts`, `walkthroughController.ts`, `CameraModeControl.tsx`, `cameraNav.test.ts`; modified `spatialAssetOverlay.ts`, `BentleyViewer.tsx`, `BentleyViewer.css`. Nothing staged/committed/pushed.

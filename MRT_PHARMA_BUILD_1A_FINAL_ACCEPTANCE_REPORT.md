# MRT Pharma — Build 1A Final Acceptance + Closure Report (COMPLETE)

**Checkpoint:** Build 1A manual completion gate **PASSED** (user-confirmed).
`BUILD_1A_STATUS = COMPLETE`. This closure consolidates the full Build 1A chain,
records the final manual acceptance, updates the authority documents narrowly, and
authorizes the Build 1A versioning commit/push. It does NOT begin Build 1B and does
NOT mark equipment binding / routing / full PET department complete.

## 1. Build 1A provenance chain (preserved — defect history intact)

| Build | Scope |
|---|---|
| Build 1A | Generic BIM room-volume activation (discovery → registry → inspection → user activation → parent-derived seed → edit → containment → persistence → multi-room). |
| Build 1A.1 | Room-discovery lifecycle correction (200 → 0 collapse) — iModel-owned lifecycle + stale/not-ready guard. |
| Build 1A.2 | Generic diagnostics (DIAGNOSE BIM ROOM DISCOVERY / SELECTED ROOM VOLUME) + lazy exact-geometry inspection + geometry-status synchronization. |
| Build 1A.3 | Storey-filter ↔ room-collection synchronization (First=Second=153 defect). |
| Build 1A.4 | Product-facing containment validation (warning, invalid cue, lock reason, Restore/Reset, last-known-valid, summary). |
| Walkthrough corrections | Forward-movement + collision correction (proximity-false-block; floor-constrained pedestrian), label visibility, incremental zoom, controls/pitch/trackpad hardening. |

## 2. Final manual acceptance (user-confirmed — all PASS)

Room discovery: `MANUAL_ROOM_DISCOVERY_LIFECYCLE = PASS`; `MANUAL_STOREY_MATRIX =
PASS` (All 200, First 153, Second 41, Roof-Main 6, TOF Footing 0). Generic exact
geometry (`1DC1 WAITING / ACTIVITY AREA`, `0x200000001f6`): EXACT, 148 verts / 292
tris, closed — `MANUAL_GENERIC_SELECTED_ROOM_EXACT_GEOMETRY = PASS`. Parent-derived
Injection Room 01 seed (≈ X -31.995513506, Y 32.090989349, W 14.234, D 4.17175,
Z 0..3, yaw 0) — `MANUAL_PARENT_DERIVED_VOLUME_SEED = PASS`, initial containment
PASS 21/21. `MANUAL_CONTAINMENT_PASS_TO_FAIL = PASS` (deliberate invalid FAIL 21/21).
`MANUAL_RESTORE_VALID_POSITION = PASS`; `MANUAL_PRODUCT_CONTAINMENT_WARNING = PASS`;
`MANUAL_RESET_TO_PARENT_DERIVED = PASS`; `MANUAL_WARNING_ISOLATION = PASS`;
`MANUAL_MULTI_VOLUME_CAMERA_INVARIANCE = PASS`; `MANUAL_RELOAD_PERSISTENCE = PASS`;
`MANUAL_BIM_SWITCH_ISOLATION = PASS`; `MANUAL_UPTAKE_01_REGRESSION = PASS`
(`UPTAKE_01_DUPLICATED = NO`).

Walkthrough: forward / backward / strafe / turn = PASS; floor-constraint = PASS;
solid-wall collision = PASS; facility navigation = PASS; incremental zoom = PASS;
no spring-back = PASS; post-zoom immediate steering = PASS; label occlusion +
nearby label = PASS; control-pane dismiss/reopen = PASS; Mac trackpad look
up/down + floor-constraint = PASS. `APPLICATION_CRASHED = NO`.

`BUILD_1A_COMPLETION_GATE = PASS`.

## 3. Walkthrough forward-movement defect + fix (provenance)

Runtime provenance: forward (W) failed while backward/strafe/turn worked; app did
not crash. Root cause (source-traced): `walkNav.resolveWalkCollision` blocked any
candidate landing within `collisionRadius + wall.thickness/2` of ANY whole-building
wall segment — a proximity-only block independent of movement direction. Since the
walker spawns near an interior wall, every forward step (toward the room, ending
near that wall band) was rejected while the opposite backward step (increasing wall
distance) passed. **Minimum fix:** proximity-only contact now blocks only when the
step is NOT moving away from the wall (`nearDist <= band && nearDist <= curDist`);
a true crossing still always blocks. Collision was NOT disabled; solid-wall + door
+ window + no-floor semantics preserved (existing collision tests remain green).
Forward is a yaw-only horizontal `forwardFlat` vector (pitch never drives vertical
translation), so movement is floor-constrained pedestrian, not free flight. A
bounded on-demand walkthrough movement diagnostic was added.

## 4. Authority established (Build 1A)

`GENERIC_BIM_ROOM_DISCOVERY`, `ROOM_DISCOVERY_LIFECYCLE`,
`STOREY_AWARE_ROOM_COLLECTION`, `LAZY_EXACT_IFCSPACE_GEOMETRY`,
`GENERIC_CLINICAL_ROOM_ACTIVATION`, `PARENT_DERIVED_CLINICAL_PLANNING_VOLUME`,
`TRUE_3D_CLINICAL_PLANNING_VOLUME`, `EXACT_PARENT_CONTAINMENT`,
`PRODUCT_CONTAINMENT_VALIDATION`, `MULTI_ROOM_PLANNING_FOUNDATION`,
`WALKTHROUGH_NAVIGATION` = `IMPLEMENTED_AND_INTEGRATED`. `BUILD_1A_STATUS = COMPLETE`.

## 5. Remaining limits (explicit)

`FULL_PET_DEPARTMENT_COMPLETE = NO`; `CANONICAL_EQUIPMENT_BINDING_COMPLETE = NO`;
`AUTOMATIC_SPATIAL_ROUTING_COMPLETE = NO`; `FREE_COMPOSITION_OPTIMIZER_COMPLETE =
NO`; `ANIMATED_SIMULATION_RUNTIME_COMPLETE = NO`; `ECONOMICS_INTEGRATION_COMPLETE =
NO`; `WHAT_IF_UI_COMPLETE = NO`; `NVIDIA_RUNTIME_COMPLETE = NO`;
`TRUE_STOREY_SPATIAL_ISOLATION_COMPLETE = NO`; `EXPLODED_STOREY_VIEW_COMPLETE = NO`.

## 6. Verification (final)

TYPECHECK = PASS · OFFLINE_TEST_FILE_COUNT = 51 · OFFLINE_TEST_COUNT = 815 ·
OFFLINE_TEST_REGRESSIONS = 0 · PRODUCTION_BUILD = PASS (only harmless
INEFFECTIVE_DYNAMIC_IMPORT + chunk-size advisories) · CORE_FRONTEND_VERSION =
5.12.5 · WORKER_ASSET_REAL = YES (`(()=>{"use strict";f`) · DRACO_WASM_ASSET_REAL =
YES (`0061 736d`).

## 7. Next builds (recorded; not started)

`NEXT_MAJOR_BUILD = BUILD_1B_COMPLETE_CLINICAL_PROGRAM_AND_CANONICAL_EQUIPMENT_BINDING`
(existing canonical equipment only; no new classes; room-parented, movable/rotatable,
floor-aware, envelope-contained, warn-on-invalid, lock-blocked-when-invalid,
Restore/Reset, iModel-scoped, crosswalked to existing capacity/production/cost
authority). After 1B: `BUILD_2_AUTOMATIC_FACILITY_CONNECTIVITY_AND_SPATIAL_TRANSPORT_INTEGRATION`
(SIMULATE → infer missions → eligible modes → auto-generate routes → evaluate;
no manual per-connection route forcing in normal simulation).

`BUILD_1A_PROVENANCE_PRESERVED = YES`. `CHECKPOINT = BUILD_1A_COMPLETE_AND_SAFELY_VERSIONED`.

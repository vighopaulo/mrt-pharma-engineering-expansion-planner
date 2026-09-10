# MRT Pharma — Build 1A Walkthrough Forward-Movement Correction

**Continues:** Build 1A + 1A.1 + 1A.2 + 1A.3 + 1A.4 + closure (uncommitted working
tree). Does not restart 1A or begin 1B. **Precheck:** HEAD = origin/main =
`344d0289723e873c7a2974d0d8d295b38f44a6a3`, divergence `0 0`; all prior 1A work
preserved; `frontend/.env` unstaged/excluded. No backend/domain change; no Bentley
writes; no stage/commit/push.

> **Sequencing note:** a Build 1B (Complete Clinical Program + Equipment Binding)
> prompt was received while this correction was in progress. Per the standing
> ordering rule and Build 1B §76, Build 1B was NOT started — Build 1A must pass its
> full manual completion gate first. This report finishes only the walkthrough
> forward-movement defect.

## 1. Preserved runtime provenance

Accepted Build 1A manual evidence (unchanged): room discovery All=200 /
First=153 / Second=41 / Roof=6 / TOF=0; room-discovery lifecycle PASS; storey
filter PASS; generic exact geometry PASS (1DC1 `0x200000001f6`, 148v/292t, closed);
parent-derived Injection Room 01 seed PASS (21/21); containment PASS→FAIL PASS;
Restore Valid Position PASS; program summary Assigned 2 / Volumes 2 / Valid 2.

**Walkthrough defect (this correction):** Walkthrough entered; **strafe (A/D) PASS,
turn (←/→) PASS, backward (S) PASS, forward (W) FAIL**; application did not crash.
`WALKTHROUGH_FORWARD_MOVEMENT_DEFECT = CONFIRMED`.

## 2. Trace + root cause (proven from source)

- `W_KEY_EVENT_RECEIVED = YES`. Mapping in `walkthroughController.step()`:
  `input.forward = (w||arrowup ? 1 : 0) − (s||arrowdown ? 1 : 0)`; `input.strafe =
  (d?1:0) − (a?1:0)`. Symmetric + correct.
- `WALKTHROUGH_FORWARD_VECTOR_SOURCE` = `candidateEye()` →
  `resolveFirstPersonOrientation(yaw, 0).forwardFlat` — **yaw-only horizontal**
  (pitch passed as 0). `FORWARD_VECTOR_VALID = YES`. `candidateEye` keeps
  `z: eye.z`, so camera pitch NEVER drives vertical translation
  (`WALKTHROUGH_MOVEMENT_MODEL = FLOOR_CONSTRAINED_PEDESTRIAN`;
  `CAMERA_PITCH_CONTROLS_VERTICAL_TRANSLATION = NO`). Eye Z is pinned to
  `eyeZForFloor(floorElevation, WALKTHROUGH_EYE_HEIGHT_M)` each frame (no drift;
  no global hard-coded Z; per-storey floor elevation).
- `FORWARD_REQUESTED_DISPLACEMENT_NONZERO = YES` (the input maps correctly; the
  displacement was computed but then rejected downstream).
- **FIRST_ASYMMETRIC_SEAM / FIRST_BROKEN_WALKTHROUGH_SEAM** =
  `resolveWalkCollision` proximity `contact` test in `walkNav.ts`:
  `contact = crosses || nearDist <= collisionRadius + wall.thickness/2`, where
  `nearDist = pointSegmentDistance(candidate, wall.a, wall.b)`.
- **ROOT_CAUSE:** the walker spawns at the model center; the whole-building
  collision model gives each wall a centerline segment spanning its full length
  and a `thickness` = its short-axis bbox extent. The proximity test blocked ANY
  candidate ending within the band of ANY wall — **including steps moving parallel
  to or away from the wall**. From the entry point a forward (+Y) step lands within
  a nearby interior wall's band → `BLOCK_WALL` (and the wall-slide also fails),
  while the backward (−Y) step increases distance into open space → `ALLOW`. That
  is exactly the forward-blocked / backward-works asymmetry, produced with no
  genuine wall crossing. `FORWARD_STEP_REJECTED_BY_COLLISION = YES`;
  `COLLISION_DISABLED_AS_FIX = NO`.

## 3. The fix (minimum, collision-preserving)

In `resolveWalkCollision` (`walkNav.ts`), the proximity-only `contact` now blocks
**only when the step is not moving away from the wall**:

```
band = collisionRadius + wall.thickness/2
approachingWithinBand = nearDist <= band && nearDist <= curDist + 1e-6
contact = crosses || approachingWithinBand
```

- A genuine crossing (`crosses`) still blocks in both directions.
- A candidate that stays at or reduces the wall distance within the band (a real
  approach) still blocks — preserving the accepted `COLLISION_RADIUS` and
  `WALL_CORNER` behaviors.
- A candidate that increases the wall distance (moving away / parallel-outward) is
  no longer proximity-blocked — fixing forward movement into open room space.

No collision was disabled; no wall was made globally non-collidable; door-portal
locality, windows, unknown openings, and no-floor all behave exactly as before.

**Diagnostic (§16):** added `diagnoseWalkthroughMovement()` (controller +
`spatialAssetOverlay.diagnoseWalkthroughMovement` bridge) — a bounded, on-demand
report (WALKTHROUGH_ACTIVE, EYE_POSITION, WALK_DIRECTION, LAST_REQUESTED_DIRECTION,
LAST_REQUESTED_DISPLACEMENT, LAST_CANDIDATE_POSITION, LAST_COLLISION_RESULT,
LAST_MOVEMENT_ACCEPTED, LAST_REJECTION_REASON, ACTIVE_STOREY). No per-frame logging.

## 4. Required behavior after correction

`W = forward`, `S = backward`, `A/D = strafe`, `←/→ = turn`, `Shift = faster`,
`Drag = look`, `Esc = release`. Existing collision remains active; solid walls and
slabs remain non-penetrable; a blocked forward step simply stops the walker
(no crash; finite coordinates). Planning-volume world coordinates are untouched
(`WALKTHROUGH_MUTATES_CLINICAL_VOLUME_COORDINATES = NO`).

## 5. Offline verification

- TYPECHECK = PASS.
- OFFLINE_TEST_FILE_COUNT = 51 · OFFLINE_TEST_COUNT = 815 · NEW_TEST_COUNT = 15
  (this correction's `build1aWalkthroughForward.test.ts`) · OFFLINE_TEST_REGRESSIONS
  = 0 (clean isolated run; the accumulated Build 1A walkthrough test suite —
  forward/zoom/trackpad/label-visibility/controls-pane/final-UX — remains green).
- PRODUCTION_BUILD = PASS (only harmless INEFFECTIVE_DYNAMIC_IMPORT + chunk-size
  advisories) · CORE_FRONTEND_VERSION = 5.12.5.
- WORKER_ASSET_REAL = YES (`(()=>{"use strict";f`) · DRACO_WASM_ASSET_REAL = YES
  (`0061 736d`) · VIEWER_HTTP_STATUS = 200 (dev server restarted).

New tests prove: W=forward nonzero, S=opposite of the same walk vector, A/D strafe;
forwardFlat horizontal + unit at any pitch; W/S/level-walk never change eye Z
(down-look and up-look forward do not descend/climb); no Z drift over repeated
steps; **the fix** (away-from-wall ALLOWED, approach/crossing still BLOCK); door
passage + no-floor preserved; coordinates finite.

## 6. Build 1B equipment requirement — RECORDED ONLY (not implemented)

Per §18, recorded for Build 1B (not started here): every spatially placed canonical
equipment/resource instance must have a parent BIM/clinical room, be translatable/
rotatable within it, remain app-owned, validate against authoritative room
geometry, warn + block lock on invalid placement, preserve other instances, and
persist iModel-scoped — using ONLY equipment/resources already in canonical
authority (no new equipment classes). `BUILD_1B_EQUIPMENT_CONTAINMENT_REQUIREMENT_RECORDED
= YES`; `NEW_EQUIPMENT_CLASSES_INTRODUCED = NO`; `EQUIPMENT_CODE_CHANGED = NO`.
Storey-exploded view NOT implemented (§19).

## 7. Scope + authority

`AUTHORITY_DOCS` untouched — Build 1A completion remains manual-gated
(`BUILD_1A_AUTHORITY_COMPLETION_DEFERRED = YES`). Zero `.py` changed (equipment /
routing / transport / operations / simulation / OpenUSD / NVIDIA / optimization /
economics / What-If / Lockdown untouched). Nothing staged, committed, or pushed.

**CHECKPOINT = HOLD_FOR_BUILD_1A_WALKTHROUGH_MANUAL_ACCEPTANCE** (then resume the
remaining Build 1A closure gates). **Build 1B not started.**

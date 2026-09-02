# MRT Pharma — Controlled Asset Manipulation (SELECT → MOVE → ROTATE)

Continues from authoritative checkpoint `f6dd65dbda2df16cd0f52c84a6ccc5cd78fd488c`.
This build adds the second spatial-planning capability over the proven
catalog/geometry/overlay/placement architecture:

```
PLACED ASSET → SELECT → MOVE → click one new world point → SAME asset / new position
PLACED ASSET → SELECT → ROTATE ±90° → SAME asset / new rotation
```

Governing doctrine: **spatial transform may change; engineering identity must not.**

## Repository baseline

```
PRECHECK_HEAD        = f6dd65dbda2df16cd0f52c84a6ccc5cd78fd488c
PRECHECK_ORIGIN_MAIN = f6dd65dbda2df16cd0f52c84a6ccc5cd78fd488c
PRECHECK_DIVERGENCE  = 0 / 0
```

## Catalog authority (unchanged)

```
EXTERNAL_GE_API_CONNECTED = NO   GE_MANUFACTURER_API_QUERIED = NO
GE_MANUFACTURER_CAD_INGESTED = NO   GE_MANUFACTURER_GEOMETRY_USED = NO
```
`GE HealthCare Discovery MI` remains a repository-catalog-derived identity
(`scanner_equipment_catalog.json#GE_DISCOVERY_MI`); the visual representation
stays `GENERIC_PET_CT_SCANNER_V1`.

## Architecture

```
CONTROLLED_ASSET_SELECTION_IMPLEMENTED = YES  (Placed Assets panel; store-owned selection)
MOVE_MODE_IMPLEMENTED = YES   ROTATE_IMPLEMENTED = YES
```

- **Interaction state**: `SpatialAssetStore.getInteractionState()` returns a
  single, mutually-exclusive `IDLE | PLACING | MOVING`. `beginPlacement` and
  `beginMove` are both rejected with `SPATIAL_INTERACTION_ALREADY_ACTIVE` unless
  the state is `IDLE`, so two Bentley tools never compete for clicks. Rotation is
  rejected while any interaction is active.
- **Move**: `MoveIntent { assetInstanceId, displayLabel, previousPosition }` is
  bound to one instance for the whole move; `completeMoveAt` consumes it once,
  updates only `transform.position` via the immutable `moveAssetTo` command, and
  exits. A UI selection change mid-move does not retarget it.
- **Rotate**: immediate (no Bentley tool). `rotateAssetYaw(id, ±90)` uses the
  immutable `rotateAssetYawBy` command; yaw normalized to `[0, 360)`; pitch/roll
  untouched.
- **Single source of truth**: `SpatialAssetStore` remains the ONE application-
  owned state. No competing arrays; selection stores only an id, resolved from
  the store. Move/rotate replace the same-id instance (identity immutable).

```
MOVE_INPUT_API            = PrimitiveTool + BeButtonEvent + ScreenViewport.pickNearestVisibleGeometry (MrtAssetMoveTool)
MOVE_WORLD_POINT_SOURCE   = PICK_NEAREST_VISIBLE_GEOMETRY (fallback BE_BUTTON_EVENT_WORLD_POINT / VIEW_PLANE_PROJECTION)
MOVE_ONE_CLICK_ONE_TRANSITION = PASS
MOVE_CANCEL_SUPPORTED     = YES (reset/Esc via PrimitiveTool + CANCEL MOVE button)
ROTATION_AXIS             = Z / YAW
ROTATION_UNIT             = DEGREES
ROTATION_STEP             = 90
ROTATION_NORMALIZATION    = PASS (0/90/180/270; -90 -> 270; 450 -> 90)
ASSET_TRANSFORM_ORDER     = local geometry -> scale -> yaw rotation (about instance center) -> translation -> Bentley world
```

## Rendering: rotation is applied in world space

`scannerGeometry.buildScannerParts` applies the instance yaw to all three parts:
the gantry and table boxes carry `yawRadians` (rotated corner-by-corner in the
decorator's `buildBox` via `applyYaw`), and the bore cylinder's axis endpoints
are now pre-rotated about the instance center by the same yaw (previously the
bore was not rotated — corrected here). The reusable `GENERIC_PET_CT_SCANNER_V1`
geometry definition is never mutated; the transform belongs to the AssetInstance.

## Identity immutability + events

```
IDENTITY_IMMUTABLE_DURING_MOVE   = PASS
IDENTITY_IMMUTABLE_DURING_ROTATE = PASS
MOVE_PRESERVES_ROTATION          = PASS
ROTATE_PRESERVES_POSITION        = PASS
ASSET_MOVED_EVENT    = PASS  (detail: assetInstanceId, assetDefinitionId, geometryRepresentationId, prev/new position, yaw, roomAssignment, scenarioId/State)
ASSET_ROTATED_EVENT  = PASS  (detail: identity, prev/new rotation, position, scenarioId/State)
AUTOMATIC_ROOM_ASSIGNMENT = NO   FLOOR_SNAPPING_IMPLEMENTED = NO
```
Move/rotate preserve `roomAssignment=NOT_ASSIGNED`, `installationState=PLACED`,
`spatialSource=USER_PLACED`, catalog provenance, and scenario provenance
(`MRT_DEV_VIEWER_PROJECT / MRT_DEV_SCENARIO / DRAFT`).

## Store observability

```
SPATIAL_ASSET_STATE_SOURCE_OF_TRUTH = ONE
ASSET_TRANSFORM_UI_UPDATE           = EVENT_DRIVEN_OR_EXPLICIT
OVERLAY_STATE_SURVIVES_DECORATOR_DISPOSE = PASS
STRICTMODE_DUPLICATE_MOVE           = NO
```
Move/rotate update the store → subscriber notification → Placed Assets panel
refresh + decorator redraw. No polling, no second transform cache.

## Status cleanup (placement lesson reapplied)

Move status is DERIVED from move-mode transitions via `resolveMoveStatus`
(active → "Moving: …"; success → "Moved: <id>"; cancel → "Move cancelled"),
distinguishing success from cancel by whether the bound instance's position
actually changed. Rotate status is a bounded local string ("Rotated: <id> → N°")
that only shows on success.
```
STALE_MOVING_STATUS_AFTER_SUCCESS = NO
STALE_MOVING_STATUS_AFTER_CANCEL  = NO
```

## Product UI (Placed Assets)

Selecting a placed asset reveals MOVE, ROTATE LEFT 90°, ROTATE RIGHT 90° and a
full inspection (id, label, position, rotation, room, state, scenario, geometry
id) so the user can verify identity stayed constant while the transform changed.
Controls are disabled while an interaction is active. All existing DEV
diagnostics and the Asset Library are preserved and unchanged.

## Machine verification

```
TYPECHECK               = PASS
OFFLINE_TEST_COUNT      = 146
NEW_TEST_COUNT          = 25 (21 assetManipulation.test.ts + 4 placementStatus move-status)
OFFLINE_TEST_REGRESSIONS = 0 (121 baseline preserved)
PRODUCTION_BUILD        = PASS
CORE_FRONTEND_VERSION   = @itwin/core-frontend 5.12.5
WORKER_ASSET_REAL       = YES (text/javascript, /viewer 200)
DRACO_WASM_ASSET_REAL   = YES (\0asm, application/wasm)
```

## Safety

```
AUTH_FLOW_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO   TRANSPARENCY_WORK_RESUMED = NO
CAMERA_BEHAVIOR_CHANGED = NO   IMODEL_MODIFIED = NO   BENTLEY_CHANGESET_CREATED = NO   BENTLEY_RESOURCE_MODIFIED = NO
```

## Manual acceptance (obtained)

```
LIVE_IMODEL_VISIBLE_IN_BROWSER = YES
PLACED_ASSET_SELECTION_VISIBLE = YES
MOVE_CONTROL_VISIBLE           = YES
ROTATE_LEFT_CONTROL_VISIBLE    = YES
ROTATE_RIGHT_CONTROL_VISIBLE   = YES
MOVE_VISIBLE_IN_BROWSER        = YES
MOVE_FUNCTIONALLY_CONFIRMED    = YES   (user: "it works")
ROTATION_VISIBLE_IN_BROWSER    = YES
ROTATION_INSPECTION_VISIBLE    = YES
```

Selected user-created instance observed in the browser:
```
assetInstanceId = PETCT-GE-DISCOVERY-MI-0001
displayLabel    = GE HealthCare Discovery MI
position        = (13.64, 7.00, 5.78)   (inspection before final move evidence)
rotation        = yaw=180 pitch=0 roll=0
roomAssignment  = NOT_ASSIGNED   installationState = PLACED   spatialSource = USER_PLACED
scenario        = MRT_DEV_SCENARIO / DRAFT
```
The browser visibly showed `Rotated: PETCT-GE-DISCOVERY-MI-0001 → 180°`.
```
ROTATION_YAW_OBSERVED = 180   ROTATION_PITCH_OBSERVED = 0   ROTATION_ROLL_OBSERVED = 0
```

### Evidence provenance (manual vs offline — not conflated)

```
MOVE_CANCEL_OFFLINE_VERIFIED                 = YES
MOVE_CANCEL_MANUAL_CONFIRMATION              = NOT_SEPARATELY_CAPTURED
MOVE_PRESERVES_ROTATION_OFFLINE              = PASS
MOVE_AFTER_ROTATE_BROWSER_WORKFLOW_EXERCISED = YES
MOVE_AFTER_ROTATE_FINAL_YAW_MANUAL_INSPECTION = NOT_SEPARATELY_CAPTURED
ROTATE_PRESERVES_POSITION                    = PASS (offline)
```

### UX determination (recorded, not implemented here)

The user accepted the command-based MOVE as a working foundation but wants the
eventual product interaction to be direct object manipulation (click the object,
drag fluidly, release to commit).
```
CURRENT_MANIPULATION_UX                     = CONTROLLED_COMMAND_FOUNDATION
CURRENT_MOVE_INTERACTION                     = CONTROLLED_COMMAND_BASED
CURRENT_MOVE_INTERACTION_ACCEPTED_AS_FOUNDATION = YES
FINAL_DIRECT_MANIPULATION_UX_IMPLEMENTED     = NO
DIRECT_OBJECT_SELECTION_IMPLEMENTED          = NO
FLUID_DRAG_IMPLEMENTED                        = NO
OBJECT_ATTACHED_MANIPULATION_HANDLES_IMPLEMENTED = NO
DIRECT_OBJECT_MANIPULATION_REQUIRED_FUTURE_BUILD = YES
FLUID_DRAG_REQUIRED_FUTURE_BUILD             = YES
```
This UX preference is NOT a failure of the current transform architecture.

### Next build (documented only — NOT implemented in this checkpoint)

Direct object selection + fluid drag manipulation:
```
click MRT Pharma overlay asset → resolve assetInstanceId → select directly
→ begin manipulation → pointer movement updates a TRANSIENT_PREVIEW_TRANSFORM
→ release → ONE authoritative AssetInstance transform commit → ONE ASSET_MOVED event.
```
Critical future doctrine: do NOT emit one permanent domain event per
pointer-move frame; the transient preview updates fluidly, and exactly one
authoritative commit + one `ASSET_MOVED` event fire on release. No drag,
gizmos, or object-attached handles were added in this checkpoint.

This build has passed manual acceptance and is being checkpointed.

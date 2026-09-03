# MRT Pharma — Object-Attached Fluid Yaw Rotation + Controlled Delete Foundation

Continues from authoritative checkpoint `8b5bf5ca3231f8b17e6bffeefd6d559c1d879fa3`.
Adds the two user-required capabilities over the accepted direct-manipulation
foundation:

- **A. Object-attached fluid yaw rotation** — a pickable rotation handle on the
  selected scanner; dragging it previews yaw fluidly and commits once on release.
- **B. Controlled single-asset delete** — explicit, confirmed removal of the
  selected USER_PLACED instance from the store.

## Repository baseline

```
PRECHECK_HEAD        = 8b5bf5ca3231f8b17e6bffeefd6d559c1d879fa3
PRECHECK_ORIGIN_MAIN = 8b5bf5ca3231f8b17e6bffeefd6d559c1d879fa3
PRECHECK_DIVERGENCE  = 0 / 0
```

## Rotation architecture

```
OBJECT_ATTACHED_ROTATION_AFFORDANCE = YES
ROTATION_HANDLE_PICKING_MECHANISM   = native Bentley decoration picking — a separate pickable transient id per selected instance (WorldOverlay Arc3d ring) mapped to ROTATION_HANDLE
DIRECT_ROTATION_TARGET_KEY          = assetInstanceId
DIRECT_ROTATION_AXIS                = Z / YAW
ROTATION_UNIT                       = DEGREES
FLUID_YAW_PREVIEW                   = YES
```

- **Handle**: `SpatialAssetDecorator` draws a horizontal orange ring
  (`Arc3d.createXY`, `GraphicType.WorldOverlay`) above the SELECTED scanner only,
  with its own pickable transient id. Two maps — body (`assetIdForPickId`) and
  handle (`handleAssetIdForPickId`) — plus `testDecorationHit` covering both.
- **Pick decision** (`assetPicking.resolveMrtPickTarget`): handle id →
  `ROTATION_HANDLE`, body id → `ASSET_BODY`, BIM/unknown → ignored. Body drag
  translates; handle drag rotates.
- **Rotation math** (`assetPicking.computePreviewYaw` / `signedAngleXYDeg` /
  `normalizeDeg`): pivot = instance center; `deltaAngle = atan2(cross, dot)` from
  the start grab vector to the current vector in the XY plane;
  `previewYaw = normalize(startYaw + delta)` in `[0, 360)`.
- **Store** (`SpatialAssetStore`): `RotationPreview { assetInstanceId, startYaw,
  previewYaw, center }`; `beginRotate` / `updateRotatePreview` /
  `commitRotate` (one `ASSET_ROTATED`) / `cancelRotate`. `getInteractionState()`
  returns `ROTATING`; mutually exclusive with `PLACING`/`MOVING`.
  `getEffectiveProjectInstances()` applies the preview yaw to the active instance
  only; the decorator renders that (cache dynamic while rotating).

```
ROTATION_PREVIEW_NON_AUTHORITATIVE          = PASS (committed yaw unchanged during preview)
ASSET_ROTATED_EVENTS_DURING_POINTER_MOVE    = 0
ASSET_ROTATED_EVENT_COUNT_SUCCESSFUL_RELEASE = 1
ROTATION_ESC_CANCEL                         = PASS (Esc -> cancelRotate -> restore startYaw, IDLE, selection kept)
ROTATION_CANCEL_REQUIRES_COMPENSATING_ROTATE = NO
DIRECT_ROTATION_PRESERVES_POSITION          = PASS (yaw only; pitch/roll/position unchanged)
DIRECT_ROTATION_IDENTITY_IMMUTABILITY       = PASS
GANTRY/BORE/TABLE_FOLLOWS_ROTATION_PREVIEW  = PASS (whole scanner uses effective yaw)
ROTATION_TARGET_ISOLATION_BY_ASSET_INSTANCE_ID = PASS
ROTATION_PRIMARY_CANCEL_INPUT               = ESC (MacBook trackpad policy; right-click optional)
CONTROLLED_ROTATION_FALLBACK_REGRESSION     = 0 (side-panel ROTATE ±90° retained)
```

## Delete architecture

```
ASSET_DELETE_IMPLEMENTED   = YES
DELETE_TARGET_KEY          = assetInstanceId
DELETE_ALLOWED_SPATIAL_SOURCE = USER_PLACED (DEV fixtures / CATALOG excluded)
DELETE_CONFIRMATION_REQUIRED = YES (window.confirm with label "Delete <displayLabel>? <assetInstanceId>")
DELETE_EVENT               = ASSET_REMOVED   DELETE_EVENT_COUNT_SUCCESS = 1   DELETE_EVENT_COUNT_CANCEL = 0
```

`SpatialAssetStore.deleteAsset(assetInstanceId)` reuses the domain `removeAsset`
command, removes ONE instance, emits one `ASSET_REMOVED` (with prior transform +
scenario detail), clears selection if the deleted instance was selected, and is
rejected (`INTERACTION_ACTIVE`) while any manipulation is active. It never
touches the iModel and preserves everything shared.

```
DELETE_CATALOG_RECORD = NO   DELETE_ASSET_DEFINITION = NO   DELETE_GEOMETRY_REPRESENTATION = NO   DELETE_OTHER_INSTANCES = NO
DELETE_BENTLEY_IMODEL_ELEMENT = NO   IMODEL_MODIFIED = NO   BENTLEY_CHANGESET_CREATED = NO
DELETE_SUCCESS = PASS   DELETE_CANCEL = PASS   DELETE_CLEARS_SELECTION = PASS   DELETE_SINGLE_INSTANCE_ISOLATION = PASS
DELETED_ASSET_PICKABLE_AFTER_REDRAW = NO (pick maps drop stale ids each decorate)
ROTATION_UI_UPDATE = EVENT_DRIVEN_OR_EXPLICIT   DELETE_UI_UPDATE = EVENT_DRIVEN_OR_EXPLICIT
```

DELETE control lives in the product Placed-Assets panel next to MOVE / ROTATE
±90° (shown only for USER_PLACED). All DEV controls preserved; added
`INSPECT ROTATION STATE`.

## State + safety

```
SPATIAL_ASSET_STATE_SOURCE_OF_TRUTH = ONE   OVERLAY_STATE_SOURCE_OF_TRUTH = SpatialAssetStore
EVENT_JOURNAL_UI_IMPLEMENTED = NO   EVENT_JOURNAL_COMPATIBILITY = PASS (ASSET_ROTATED, ASSET_REMOVED descriptors)
AUTOMATIC_ROOM_ASSIGNMENT = NO   ROOM_SNAPPING_IMPLEMENTED = NO   (no floor/collision/clearance)
AUTH_FLOW_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO   TRANSPARENCY_WORK_RESUMED = NO   CAMERA_BEHAVIOR_CHANGED = NO
IMODEL_MODIFIED = NO   BENTLEY_CHANGESET_CREATED = NO   BENTLEY_RESOURCE_MODIFIED = NO
```

## Machine verification

```
TYPECHECK               = PASS
OFFLINE_TEST_COUNT      = 217
NEW_TEST_COUNT          = 31 (objectRotationDelete.test.ts, incl. handle/body id distinctness, two-instance isolation, screen-space ring fallback: on-outline hit, center miss, outside miss, degenerate miss, ringWorldSamples)
OFFLINE_TEST_REGRESSIONS = 0 (186 baseline preserved: translation + fallback rotation + delete unaffected)
PRODUCTION_BUILD        = PASS
CORE_FRONTEND_VERSION   = @itwin/core-frontend 5.12.5
WORKER_ASSET_REAL       = YES (text/javascript, /viewer 200)
DRACO_WASM_ASSET_REAL   = YES (\0asm, application/wasm)
```

## Targeted correction — rotation-handle must be pickable (drag rotates)

First manual acceptance: DELETE passed and the orange ring rendered attached to
the selected scanner, but dragging the ring did NOT rotate — it behaved like a
body drag / did nothing.
```
DELETE_VISIBLE_IN_BROWSER = YES   DELETE_FUNCTIONALLY_CONFIRMED = YES   DELETE_MANUAL_ACCEPTANCE = PASS
OBJECT_ATTACHED_ROTATION_AFFORDANCE = YES   ROTATION_HANDLE_ATTACHED_TO_SELECTED_ASSET = YES
FLUID_ROTATION_VISIBLE_IN_BROWSER = NO (before fix)
PRIMARY_REMAINING_FAILURE_STAGE = ROTATION_HANDLE_PICK_OR_ROTATION_START
```

Root cause: the handle was drawn as a hairline `Arc3d` on a
`GraphicType.WorldOverlay` builder. That curve has negligible practical pick
area and overlay decorations don't participate in locate the same way as world
decorations, so clicking the ring resolved to the scanner BODY underneath (the
body's `WorldDecoration` pick id) → the tool started a translate, not a rotate.
The offline classification (`resolveMrtPickTarget`) was already correct; the
runtime never produced the handle pick id.

Correction (handle-pick only): the handle is now a SOLID `TorusPipe`
(`TorusPipe.createAlongArc(arc, minorRadius, capped)`) drawn on a
`GraphicType.WorldDecoration` builder with its own handle pick id — the SAME
reliable pick path as the body. It is a thin ring (tube ≈ 9% of the radius) that
sits above the scanner top, so it is grabbable while body drag stays available
inside/outside it. It sits nearer the camera than the body, so its pick id wins
when the ring is clicked.
```
ROTATION_HANDLE_PICK_ID_CREATED               = YES (per selected instance)
ROTATION_HANDLE_PICK_ID_UNIQUE_FROM_BODY      = YES (separate transient id + separate map)
ROTATION_HANDLE_GRAPHIC_TYPE                  = WorldDecoration (was WorldOverlay)
ROTATION_HANDLE_PICKABLE_ID_APPLIED           = YES (createGraphicBuilder(..., handlePickId))
ROTATION_HANDLE_PICK_TARGET_USABLE            = YES (TorusPipe solid surface)
DECORATOR_TEST_DECORATION_HIT_ACCEPTS_HANDLE  = YES (covers both body + handle maps)
ROTATION_HANDLE_FILTER_ACCEPTED               = YES (filterHit accepts any decorator-owned pick id)
BODY_TRANSLATION_REMAINS_ACCESSIBLE           = YES
BIM_ELEMENT_ACCEPTED_AS_ROTATION_HANDLE       = NO
```
The bounded `[direct-pick]` diagnostic logs `target=ROTATION_HANDLE|ASSET_BODY|
NONE` to confirm the ring now resolves to the handle in the browser. Rotation
math, preview/commit/cancel, and DELETE are unchanged.

## Diagnosis pass 2 — runtime pick chain + scoped screen-space fallback

Second manual test: the TorusPipe/WorldDecoration handle still did NOT start
rotation when dragged, even though body translation (also WorldDecoration)
works. So the reliable-pick-path theory alone was insufficient — the thin torus
tube loses the native `readPixels` locate to the body underneath at the cursor
aperture (BODY_WINS_PICK_OVER_HANDLE), and clicking the visual center of the
ring (the hole) hits only the body.

This pass adds RUNTIME INSTRUMENTATION so the next browser test is conclusive,
plus a narrowly scoped correction that does not depend on the torus winning the
pixel pick:

Instrumentation (DEV, bounded — never per-frame beyond first 5 rotation frames):
- `[rotation-pick] sourceId=… isDecoration=… bodyAssetId=… handleAssetId=… targetType=… assetInstanceId=… selected=…` — the ACTUAL Bentley sourceId and how it resolved (proves A: NONE / B: body wins / C: handle).
- `[rotation-handle-map] assetInstanceId=… bodyPickId=… handlePickId=… sameId=false handleRegistered=true generation=…` — proves the handle id is distinct + registered in the CURRENT decoration generation.
- `[rotation-start] stage=INPUT|STORE_BEGIN … result=SUCCESS|… rotationPreviewActive=…` — proves onMouseStartDrag sees ROTATION_HANDLE and beginRotate succeeds.
- `[rotation-preview] stage=BEGIN|UPDATE …` — proves preview yaw changes on motion.

Correction (section 34 — scoped screen-space handle fallback):
When native locate does NOT resolve to a ROTATION_HANDLE, the tool projects the
SELECTED asset's rotation ring to view coordinates and resolves
`ROTATION_HANDLE(selectedAssetInstanceId)` when the pointer is within a small
pixel band (14px) of the projected ring outline. Strictly scoped:
- only the currently selected asset, only when its handle is actually rendered
  (`handlePickIdForInstance` present);
- keyed by `assetInstanceId` (never screen pixels as identity);
- the ring HOLE (center) is NOT near the outline → body translation still works
  there;
- never selects BIM, never applies to unselected assets, not a generic raycaster.
Native decoration picking remains the primary path; the fallback only fires when
native locate misses the thin torus. Geometry, rotation math, preview/commit/
cancel, and DELETE are unchanged.

```
ROTATION_FALLBACK_TARGET_KEY                  = assetInstanceId
BODY_TRANSLATION_REMAINS_ACCESSIBLE           = YES (ring hole not near outline)
BIM_ELEMENT_ACCEPTED_AS_ROTATION_HANDLE       = NO
UNKNOWN_DECORATION_ACCEPTED                   = NO
NON_FINITE_ROTATION_PREVIEW                   = IGNORED (finite guard retained)
ROTATION_POINTER_PLANE                        = HORIZONTAL_Z (rotateCenter.z)
```

## Manual acceptance — PASSED (authoritative)

Both principal objectives passed functional browser acceptance on the user's
actual MacBook environment.

Rotation — user's exact assessment: "Rotation is working perfectly."
```
LIVE_IMODEL_VISIBLE_IN_BROWSER              = YES
OBJECT_ATTACHED_ROTATION_AFFORDANCE         = YES
OBJECT_ATTACHED_ROTATION_VISIBLE_IN_BROWSER = YES
ROTATION_HANDLE_ATTACHED_TO_SELECTED_ASSET  = YES
ROTATION_HANDLE_DRAG_FUNCTIONALLY_WORKING   = YES
FLUID_ROTATION_VISIBLE_IN_BROWSER           = YES
OBJECT_ATTACHED_ROTATION_MANUAL_ACCEPTANCE  = PASS
```

Delete — user's exact assessment: "Delete works."
```
DELETE_VISIBLE_IN_BROWSER      = YES
DELETE_FUNCTIONALLY_CONFIRMED  = YES
DELETE_MANUAL_ACCEPTANCE       = PASS
ASSET_DELETE_IMPLEMENTED       = YES
```

## Final working rotation-handle architecture

The historical failure (ring rendered but did not rotate) was traced across two
passes: (1) the original hairline `Arc3d` on `WorldOverlay` had negligible pick
area and the wrong locate path; (2) even a solid `TorusPipe` on `WorldDecoration`
lost the native `readPixels` pick to the body underneath the thin tube at the
cursor aperture. The accepted, working solution keeps the visible object-attached
orange ring and native decoration picking as primary, plus a narrowly scoped
selected-asset screen-space ring fallback for when native thin-ring picking does
not resolve.
```
ROTATION_HANDLE_GRAPHIC_TYPE     = WorldDecoration
ROTATION_HANDLE_GEOMETRY         = TorusPipe.createAlongArc (solid ring), orange
ROTATION_HANDLE_PICKING_PRIMARY  = native Bentley decoration pick (testDecorationHit + HitDetail.sourceId)
ROTATION_HANDLE_PICKING_FALLBACK = scoped selected-asset screen-space projected-ring band (14px), NOT a generic raycaster
ROTATION_FALLBACK_TARGET_KEY     = assetInstanceId
ROTATION_HANDLE_TARGET_KEY       = assetInstanceId
BODY_DRAG = TRANSLATE   ROTATION_HANDLE_DRAG = ROTATE
DIRECT_ROTATION_AXIS = Z / YAW   ROTATION_UNIT = DEGREES   FLUID_YAW_PREVIEW = YES
```

Rotation procedure: select a GE Discovery MI; confirm the orange ring handle
appears on it; drag the BODY → translates; drag the HANDLE → the whole scanner
rotates fluidly about its own axis, position unchanged; release → one committed
yaw, selection kept; begin again and press Esc → returns to prior yaw, no commit.

Delete procedure: with two placed scanners, select one, click DELETE; Cancel the
prompt → nothing removed; DELETE + Confirm → that scanner disappears from the
overlay and Placed Assets (count −1), selection clears, the other scanner and
the shared GE catalog identity / generic geometry remain.

Regression: direct translation, normal release, Esc translation cancel,
side-panel ROTATE ±90°, Asset Library placement, and quiet BIM all still work.

This build is NOT staged, committed, or pushed — implementation stops here for
manual browser acceptance.

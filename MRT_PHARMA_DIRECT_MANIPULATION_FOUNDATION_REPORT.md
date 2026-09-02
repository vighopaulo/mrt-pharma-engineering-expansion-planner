# MRT Pharma — Direct Object Selection + Fluid Drag Manipulation Foundation

Continues from authoritative checkpoint `0de96a408539c5bf1b43de54649aff1ef00b37c5`.
Adds direct-from-the-object interaction over the proven placement/manipulation
architecture:

```
click scanner → resolve assetInstanceId → select/highlight
→ press + drag → TRANSIENT fluid preview → release
→ ONE authoritative transform commit → ONE ASSET_MOVED event
```

Central doctrine: **preview is not commit.** The command-based MOVE/ROTATE
controls remain as the deterministic fallback.

## Repository baseline

```
PRECHECK_HEAD        = 0de96a408539c5bf1b43de54649aff1ef00b37c5
PRECHECK_ORIGIN_MAIN = 0de96a408539c5bf1b43de54649aff1ef00b37c5
PRECHECK_DIVERGENCE  = 0 / 0
```

## Bentley picking API (verified, not guessed)

Installed `@itwin/core-frontend` **5.12.5**. Verified in the type definitions:
- `Decorator.testDecorationHit(id)` — returns true if a picked pickable id
  belongs to the decorator.
- `DecorateContext.createGraphicBuilder(type, transform?, id?)` — the 3rd arg
  makes the graphic **pickable** with a transient Id64.
- `IModelConnection.transientIds` (`getNext()`) — unique ids for pickable
  decorations.
- `ElementLocateManager.doLocate(response, newSearch, testPoint, view, source)`
  → `HitDetail`; `HitDetail.sourceId` is the picked pickable id.
- `PrimitiveTool` drag lifecycle: `onDataButtonDown`, `onMouseStartDrag`,
  `onMouseMotion`, `onMouseEndDrag`, `onResetButtonUp`, `beginDynamics`/
  `endDynamics`, `initLocateElements`.

```
DIRECT_OBJECT_PICKING_MECHANISM = NATIVE_BENTLEY_DECORATION_PICKING
```
The `SpatialAssetDecorator` draws each instance's graphics with a pickable
transient id, keeps a `pickableId ↔ assetInstanceId` map, and implements
`testDecorationHit`. A located `HitDetail.sourceId` maps back to the
application-owned `assetInstanceId`. No fake iModel element ids, no HTML hitbox
layer, no iModel writes. A pure ray-vs-oriented-bounding-box helper
(`assetPicking.ts`) provides the offline-testable nearest-hit math (rotation-
aware) and the drag-plane intersection.

## Architecture

```
DIRECT_OBJECT_SELECTION_IMPLEMENTED = YES
FLUID_DRAG_IMPLEMENTED              = YES
DIRECT_MANIPULATION_TARGET_KEY      = assetInstanceId
```

- **Tool** (`MrtDirectManipulationTool`, bounded `PrimitiveTool`): click →
  locate → select (no move); `onMouseStartDrag` on an asset → begin drag;
  `onMouseMotion` → update transient preview; `onMouseEndDrag` → one commit;
  reset/Esc/cleanup → cancel. Bounded input; no permanent DOM listeners.
- **Transient preview** (`DragPreview` in `SpatialAssetStore`): `assetInstanceId`,
  `startPosition`, `grabOffset`, `previewPosition`. Never persisted, never
  serialized, never journaled. `getEffectiveProjectInstances()` applies the
  preview to the dragged instance only; the decorator renders that.
- **Commit**: `commitDrag()` runs the immutable `moveAssetTo` once → one
  `ASSET_MOVED`. `cancelDrag()` discards the preview (no event, restore).
- **Selection highlight**: amber outline + heavier line weight on the selected
  instance — application render state only, NO geometry-identity change and NO
  transparency.

```
DRAG_PLANE                = horizontal Z = dragStartZ (ray ∩ plane)
FLUID_DRAG_Z_BEHAVIOR     = PRESERVE_START_Z
DRAG_START_OFFSET         = grabOffset = assetPosition - grabWorldPoint (preserved)
DRAG_THRESHOLD            = Bentley platform drag threshold (onMouseStartDrag fires only past it)
DRAG_INPUT_ACTIVE_WHEN_IDLE = NO
DRAG_PREVIEW_RENDER_PATH  = APPLICATION_OWNED_OVERLAY
```

## Preview-is-not-commit invariant

```
ASSET_MOVED_EVENTS_DURING_POINTER_MOVE       = 0
ASSET_MOVED_EVENTS_ON_SUCCESSFUL_DRAG_RELEASE = 1
DRAG_AUTHORITATIVE_COMMIT_COUNT              = 1
ASSET_MOVED_EVENT_COUNT_PER_DRAG             = 1
DRAG_CANCEL_RESTORES_COMMITTED_POSITION      = PASS
```
During a drag the committed AssetInstance is unchanged through every preview
update (offline-tested with 25 preview updates → 0 committed change → 1 commit
on release).

## Identity + immutability

```
DIRECT_DRAG_PRESERVES_ROTATION = PASS
DIRECT_DRAG_PRESERVES_IDENTITY = PASS (assetInstanceId, assetDefinitionId,
  catalogRecordId/createdFrom, geometryRepresentationId, displayLabel,
  dimension provenance, projectId, scenarioId, roomAssignment, installationState,
  spatialSource all preserved)
GEOMETRY_REPRESENTATION_MUTATED = NO (GENERIC_PET_CT_SCANNER_V1 reused; selection
  is render state, not a new geometry id)
AUTOMATIC_ROOM_ASSIGNMENT = NO   FLOOR_SNAPPING_IMPLEMENTED = NO   ROOM_SNAPPING_IMPLEMENTED = NO
```

## State + UI sync

```
SPATIAL_ASSET_STATE_SOURCE_OF_TRUTH = ONE   OVERLAY_STATE_SOURCE_OF_TRUTH = SpatialAssetStore
ASSET_TRANSFORM_UI_UPDATE           = EVENT_DRIVEN_OR_EXPLICIT
DIRECT_SELECTION_UI_SYNCHRONIZATION = PASS (store selection drives Placed Assets + inspection)
OBJECT_CENTRIC_MANIPULATION_FEEDBACK = YES (selection outline + object hint; no gizmo)
```
Direct selection sets `store.selectedAssetInstanceId`; the Placed Assets panel
and inspection follow via the existing subscription (no polling). The command
MOVE / ROTATE LEFT 90° / ROTATE RIGHT 90° controls and all DEV diagnostics are
preserved.

## Mutual exclusivity

Fluid drag counts as `MOVING` in the single `SpatialInteractionState`
(`IDLE | PLACING | MOVING`). Drag cannot start while placing; placement and
command-move cannot start while dragging. The direct-manipulation tool re-arms
only when the interaction returns to `IDLE`.

## Machine verification

```
TYPECHECK               = PASS
OFFLINE_TEST_COUNT      = 185
NEW_TEST_COUNT          = 39 (directManipulation.test.ts: 15 + 6 preview-render + 5 decoration-acceptance + 6 lifecycle + 2 silent-non-MRT + 5 cancellation)
OFFLINE_TEST_REGRESSIONS = 0 (146 baseline preserved)
PRODUCTION_BUILD        = PASS
CORE_FRONTEND_VERSION   = @itwin/core-frontend 5.12.5
WORKER_ASSET_REAL       = YES (text/javascript, /viewer 200)
DRACO_WASM_ASSET_REAL   = YES (\0asm, application/wasm)
```

## Safety

```
AUTH_FLOW_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO   TRANSPARENCY_WORK_RESUMED = NO
CAMERA_BEHAVIOR_CHANGED = NO   IMODEL_MODIFIED = NO   BENTLEY_CHANGESET_CREATED = NO   BENTLEY_RESOURCE_MODIFIED = NO
FLUID_ROTATION_IMPLEMENTED = NO (rotation stays command-based ±90°)
```

## Out of scope (unchanged)

No rotation gizmo, no free 3D vertical drag, no room/floor snapping, no
collision/clearance, no new equipment families, no auth/camera/transparency
work, no iModel writes.

## Targeted correction — drag preview must move the scanner geometry

First manual acceptance found a defect: direct picking, selection, and pointer
tracking worked, and the selection/locate marker moved, but the PET/CT scanner
geometry stayed at its committed position during the drag.

```
DIRECT_OBJECT_SELECTION_VISIBLE_IN_BROWSER = YES
DRAG_POINTER_TRACKING_VISIBLE_IN_BROWSER   = YES
DRAG_PREVIEW_MARKER_MOVES                  = YES
SCANNER_GEOMETRY_FOLLOWS_PREVIEW (before fix) = NO
DIRECT_DRAG_MANUAL_ACCEPTANCE (first)      = FAIL
FAILURE_STAGE                              = TRANSIENT_PREVIEW_RENDERING
```

Root cause (classification D): the preview state updated and
`getEffectiveProjectInstances()` returned the preview transform (proven by
offline tests), but `SpatialAssetDecorator.useCachedDecorations = true` caused
Bentley to reuse the cached decoration graphic at the stale committed position
during the fast drag; the independently pointer-tracked locate marker moved,
the cached scanner did not.

```
TRANSIENT_PREVIEW_ROOT_CAUSE = CACHED_DECORATION_NOT_REBUILT_DURING_DRAG
DRAG_PREVIEW_STATE_UPDATES        = PASS
EFFECTIVE_INSTANCE_USES_PREVIEW   = PASS
DECORATOR_USES_EFFECTIVE_TRANSFORM = PASS
```

Correction (narrow, render-only): `useCachedDecorations` is now a getter —
`true` while idle, `undefined` (no caching) while a drag is active — so the
decorator's `decorate()` runs every frame during a drag and rebuilds the whole
scanner from the preview transform. On each preview update the overlay calls
`viewport.invalidateDecorations()` (drag) or `invalidateCachedDecorations()`
(idle). No decorator re-registration per frame, no viewer/iModel reload, no idle
render loop.

```
DECORATION_CACHE_MODE       = HYBRID (cached idle; dynamic during drag)
DECORATION_INVALIDATION     = PASS (invalidateDecorations during drag; invalidateCachedDecorations idle)
GANTRY_FOLLOWS_DRAG_PREVIEW = PASS (offline: whole effective instance moves)
BORE_FOLLOWS_DRAG_PREVIEW   = PASS
TABLE_FOLLOWS_DRAG_PREVIEW  = PASS
PREVIEW_PRESERVES_ROTATION  = PASS
DRAG_START_OFFSET_PRESERVED = PASS
DIRECT_DRAG_IDLE_RENDER_LOOP = NO
ASSET_MOVED_EVENTS_DURING_POINTER_MOVE = 0
ASSET_MOVED_EVENTS_ON_SUCCESSFUL_DRAG_RELEASE = 1
DRAG_CANCEL_RESTORES_COMMITTED_POSITION = PASS
```

A bounded DEV diagnostic (`[drag-preview]`, first 5 preview updates per drag)
logs committed vs preview vs effective positions to verify the pipeline.

## Second targeted correction — decoration must be valid for the tool

A subsequent manual test revealed the actual PRIMARY blocker (ahead of preview
rendering): Bentley displayed **"Decoration is not valid for this tool"** and the
drag never began. The scanner was recognized as a decoration hit, but the tool's
locate flow rejected it.

```
DECORATION_HIT_DETECTED           = YES
DECORATION_VALID_FOR_ACTIVE_TOOL  = NO (before fix)
BENTLEY_REJECTION_MESSAGE         = "Decoration is not valid for this tool"
PRIMARY_FAILURE_STAGE             = BENTLEY_TOOL_DECORATION_ACCEPTANCE
```

Source-level root cause (classification C — locate excludes decorations):
```
REJECTION_SOURCE_FILE      = @itwin/core-frontend ElementLocateManager (filterHit), lines ~310-318
REJECTION_SOURCE_CONDITION = if (!this.options.allowDecorations && !hit.isElementHit) { out.reason = "LocateFailure.Transient"; return Reject }
LOCALIZATION_KEY           = LocateFailure.Transient -> "Decoration is not valid for this tool"
```
`initLocateElements(...)` calls `initToolLocate()` → `initLocateOptions()` which
resets `LocateOptions.allowDecorations = false`. Tools must opt in to locating
transient (decoration) geometry; ours never did, so every scanner hit was
rejected as `Transient`.

Correction (narrow, tool-acceptance only):
```
DECORATION_ACCEPTANCE_HOOK  = LocateOptions.allowDecorations = true (in onPostInstall) + PrimitiveTool.filterHit override
DECORATION_ACCEPTANCE_SCOPE = MRT_ASSET_DECORATIONS_ONLY
```
- `onPostInstall` sets `IModelApp.locateManager.options.allowDecorations = true`
  after `initLocateElements`, so the transient decoration hit is not rejected.
- `filterHit(hit)` accepts ONLY hits whose `sourceId` resolves to an MRT asset
  via the decorator (`decideHitAcceptance` pure seam); BIM elements
  (`isElementHit`) and unknown/absent ids are rejected → `IMODEL_ELEMENT_DIRECT_DRAG = NO`.
- `onCleanup` restores `allowDecorations = false` so other tools are unaffected.
- Bounded `[direct-pick]` DEV diagnostic logs sourceId / isDecoration / decision.

```
DIRECT_OBJECT_PICKING_MECHANISM        = NATIVE_BENTLEY_DECORATION_PICKING (preserved)
DECORATION_VALID_FOR_ACTIVE_TOOL       = YES (after fix)
ACTIVE_TOOL_DURING_DIRECT_INTERACTION  = MrtDirectManipulationTool
DIRECT_MANIPULATION_TARGET_KEY         = assetInstanceId
STRICTMODE_DUPLICATE_DIRECT_TOOL       = NO
DECORATION_CACHE_MODE                  = HYBRID (cached idle; dynamic during drag) — retained from prior correction
TRANSIENT_PREVIEW_ROOT_CAUSE           = DEFERRED_UNTIL_VALID_DRAG (re-evaluate in browser once the drag begins)
```

The prior dynamic-during-drag cache correction is retained (not reverted); it
only becomes relevant once a valid drag begins, which this fix unblocks.

## Third targeted correction — drag lifecycle termination + clean return to IDLE

Manual testing then confirmed the scanner geometry (gantry, bore, table) now
follows the pointer during a drag:

```
DIRECT_OBJECT_SELECTION_VISIBLE_IN_BROWSER = YES
DIRECT_DRAG_BEGIN_VISIBLE_IN_BROWSER       = YES
SCANNER_GEOMETRY_FOLLOWS_POINTER           = YES
DRAG_PREVIEW_MANUAL_ACCEPTANCE             = PASS
GANTRY/BORE/TABLE_FOLLOWS_DRAG_PREVIEW     = YES
```

But the drag did not terminate cleanly:
```
DIRECT_DRAG_LIFECYCLE_MANUAL_ACCEPTANCE = FAIL
POST_DRAG_INVALID_ELEMENT_MESSAGES      = YES ("Element not valid for tool" on passive motion)
PROJECT_EXTENTS_ERROR_VISIBLE           = YES
ROTATION_AVAILABLE_DURING_STALE_DRAG_STATE = NO
PRIMARY_FAILURE_STAGE                   = DIRECT_DRAG_LIFECYCLE_TERMINATION
```

Source-level root causes (traced in installed @itwin/core-frontend 5.12.5):
```
PROJECT_EXTENTS_ERROR_SOURCE_FILE      = PrimitiveTool.isValidLocation (CoreTools key "ProjectExtents")
PROJECT_EXTENTS_ERROR_SOURCE_CONDITION = isSpatialView && accuSnap.isSnapEnabled && !projectExtents.containsPoint(ev.point)
PROJECT_EXTENTS_ERROR_TRIGGER          = the tool enabled AccuSnap (initLocateElements(true, true)), which activates isValidLocation's extents check
"Element not valid for tool" SOURCE    = AccuSnap continuous locate-on-motion + tool filterHit reject reason surfaced as the cursor crosses BIM
ROTATION_CONTROL_DISABLED_REASON       = interaction != IDLE because a stale dragPreview kept the store in MOVING
```

Correction (lifecycle/tool-acceptance only, no rendering change):
- **AccuSnap disabled**: `initLocateElements(true, /*enableSnap*/ false)`. Snap
  drove the continuous locate-on-motion that surfaced "Element not valid for
  tool" and it is what activated `isValidLocation`'s project-extents check. We
  locate explicitly on click/drag-start instead. → silent non-MRT hits on motion.
- **`isValidLocation()` overridden to return `true`** (scoped to this tool): the
  scanner is application-owned overlay geometry, not an iModel element being
  placed, so Bentley's element-placement extents validator must not govern it.
  Global project-extents validation for other tools is unchanged. Finite-point
  validation happens in the store's move command.
- **Removed Bentley dynamics** (`beginDynamics`/`endDynamics`): the preview is
  rendered by the decorator (invalidated per preview update), so no separate
  dynamics state exists to linger. This removes a stale-state source; the drag
  ends purely by clearing `dragPreview` in the store.
- **Clean termination**: `commitDrag()`/`cancelDrag()` clear `dragPreview` →
  `getInteractionState()` returns IDLE → the ROTATE controls
  (`disabled = interaction !== 'IDLE'`) re-enable automatically via the store
  subscription. Selection (`selectedAssetInstanceId`) is retained through both.
- **Invalid preview updates ignored**: non-finite drag-plane points are skipped
  (keep last valid preview), never committed or errored.
- Bounded `[direct-drag]` DEV diagnostic logs BEGIN/COMMIT/CANCEL/CLEANUP with
  interaction/preview/selection state (first 12 transitions).

```
DRAG_RELEASE_RETURNS_TO_IDLE            = PASS (offline)
DRAG_CANCEL_RETURNS_TO_IDLE             = PASS (offline)
DRAG_PREVIEW_CLEARED_AFTER_COMMIT       = PASS
DRAG_PREVIEW_CLEARED_AFTER_CANCEL       = PASS
SELECTION_PRESERVED_AFTER_DRAG          = PASS
SELECTION_PRESERVED_AFTER_CANCEL        = PASS
BENTLEY_DYNAMICS_ACTIVE_AFTER_DRAG      = NO (dynamics removed)
PASSIVE_MOUSE_MOVE_AFTER_COMMIT_CHANGES_ASSET  = NO (offline)
PASSIVE_MOUSE_MOVE_AFTER_CANCEL_RESTARTS_DRAG  = NO (offline)
PROJECT_EXTENTS_ERROR_DURING_VALID_MRT_DRAG    = NO
IMODEL_PROJECT_EXTENTS_VALIDATION_GLOBALLY_DISABLED = NO
NON_MRT_HIT_BEHAVIOR                    = SILENT_IGNORE_OR_DEFER
ROTATION_CONTROLS_REENABLE_AFTER_DRAG   = PASS (interaction returns to IDLE)
ROTATION_CONTROLS_REENABLE_AFTER_CANCEL = PASS
ASSET_MOVED_EVENT_COUNT_PER_SUCCESSFUL_DRAG = 1
ASSET_MOVED_EVENT_COUNT_PER_CANCELLED_DRAG  = 0
ASSET_MOVED_EVENT_COUNT_DURING_PASSIVE_POINTER_MOVE = 0
CONTROLLED_ROTATION_REGRESSION = 0
```

## Fourth targeted correction — silent non-MRT hits

Manual testing confirmed direct drag and controlled rotation now work end to end:
```
DIRECT_DRAG_FUNCTIONALLY_WORKING       = YES
SCANNER_GEOMETRY_FOLLOWS_POINTER       = YES
CONTROLLED_ROTATION_VISIBLE_IN_BROWSER = YES
ROTATE_LEFT_90_CONTROL_WORKING = YES   ROTATE_RIGHT_90_CONTROL_WORKING = YES
ROTATION_YAW_MANUALLY_OBSERVED = 270   ROTATION_AXIS = Z / YAW
```
The only remaining defect was Bentley showing "Element not valid for tool" as the
cursor crossed ordinary BIM.

Source-level root cause (installed @itwin/core-frontend 5.12.5):
```
INVALID_ELEMENT_MESSAGE_SOURCE_FILE = ElementLocateManager.js (filterHit) line ~337
INVALID_ELEMENT_MESSAGE_KEY         = LocateFailure.ByApp -> "Element not valid for tool"
INVALID_ELEMENT_MESSAGE_TRIGGER     = after the tool's filterHit returns Reject, the manager unconditionally sets out.reason = "ByApp"
REMAINING_NON_MRT_MESSAGE_ROOT_CAUSE = passive AccuSnap/locate-on-motion ran the locate filter on hover; our filterHit rejected the non-MRT hit; AccuSnap then displayed the ByApp reason
```

Correction (silent non-MRT only): the tool no longer enables passive locate or
AccuSnap — `onPostInstall` calls `changeLocateState(false, false)`. Selection is
resolved by an EXPLICIT `doLocate` on click / drag-start (unaffected by the
passive locate state), with `LocateOptions.allowDecorations = true` set for that
explicit locate so MRT decorations are still accepted. Hovering BIM is now
completely quiet — no locate filter runs on motion, so no `ByApp` reason is
produced or displayed. `filterHit` still rejects non-MRT hits (silent; only runs
during our explicit locate).

```
NON_MRT_HIT_BEHAVIOR                = SILENT_IGNORE_OR_DEFER
IMODEL_ELEMENT_DIRECT_DRAG          = NO
BIM_ELEMENT_ACCEPTED_AS_MRT_ASSET   = NO
POST_DRAG_INVALID_ELEMENT_MESSAGES  = NO (browser retest pending)
PROJECT_EXTENTS_ERROR_DURING_VALID_MRT_DRAG = NO (isValidLocation override retained)
```

All prior corrections retained: scanner-follows-pointer, native decoration
picking + allowDecorations, DragPreview transience (one ASSET_MOVED on release),
hybrid decoration cache, clean IDLE termination, selection retention, command
MOVE/ROTATE fallback.

## Next build (documented only — NOT implemented)

```
OBJECT_ATTACHED_ROTATION_REQUIRED   = YES
OBJECT_ATTACHED_ROTATION_IMPLEMENTED = NO
FLUID_YAW_ROTATION_IMPLEMENTED      = NO
CURRENT_ROTATION_CONTROLS           = SIDE_PANEL_90_DEGREE_COMMAND_FALLBACK
FUTURE_PRIMARY_ROTATION_UX          = OBJECT_ATTACHED_ROTATION_HANDLE
NEXT_BUILD                          = OBJECT_ATTACHED_FLUID_YAW_ROTATION_FOUNDATION
```
Future doctrine (same as translation): angular pointer movement updates a
transient `RotationPreview.yaw`; the authoritative `AssetInstance.rotation` is
unchanged until release; release commits once → one `ASSET_ROTATED`; cancel
restores prior yaw. Side-panel ±90° controls remain as the fallback.

## Fifth targeted correction — right-click / Esc cancellation reliability

Manual acceptance confirmed direct drag, successful release, and controlled
rotation all work (two instances placed; yaw 270 observed on
PETCT-GE-DISCOVERY-MI-0002). The only remaining uncertainty was that right-click
and Esc did not reliably cancel an active drag.

Source-level investigation (installed @itwin/core-frontend 5.12.5):
```
RIGHT_CLICK_CALLBACK      = ToolAdmin dispatches BeButton.Reset -> tool.onResetButtonDown (isDown) then onResetButtonUp
RIGHT_CLICK_DEFAULT_BEHAVIOR = delivered to the active tool; no auto-exit
ESC_CALLBACK_PATH         = ToolAdmin.onKeyTransition -> activeTool.onKeyTransition(wentDown, keyEvent); keyEvent.key === "Escape"
ESC_DEFAULT_BEHAVIOR      = if unhandled, ToolSettings.escapeMovesFocusToHome may move focus; the tool never cancelled the drag
ROOT CAUSE                = the tool overrode only onResetButtonUp and did NOT override onKeyTransition, so Esc never reached a cancel path; reset cancellation was also only on UP
```

Correction (cancel reliability only): one application cancellation path
`cancelActiveDirectDrag(reason)` (discards preview, restores committed position,
0 events, IDLE, selection retained) is now invoked from BOTH
`onResetButtonDown` and `onResetButtonUp` (right-click, earliest wins; the other
is a no-op) AND from `onKeyTransition` on `Escape`. No other layer changed.

```
CANCELLATION_APPLICATION_FUNCTION      = cancelActiveDirectDrag(reason) -> store.cancelDrag()
CANCEL_RESTORE_AUTHORITY               = LAST_COMMITTED_ASSET_INSTANCE_POSITION
CANCEL_REQUIRES_COMPENSATING_MOVE      = NO (preview architecture already non-authoritative)
RIGHT_CLICK_CANCEL                     = PASS (offline)
ESC_CANCEL                             = PASS (offline; same store path)
DRAG_PREVIEW_CLEARED_AFTER_RIGHT_CLICK = PASS   DRAG_PREVIEW_CLEARED_AFTER_ESC = PASS
INTERACTION_IDLE_AFTER_RIGHT_CLICK     = PASS   INTERACTION_IDLE_AFTER_ESC = PASS
SELECTION_PRESERVED_AFTER_RIGHT_CLICK_CANCEL = PASS   SELECTION_PRESERVED_AFTER_ESC_CANCEL = PASS
ASSET_MOVED_EVENT_COUNT_RIGHT_CLICK_CANCEL = 0   ASSET_MOVED_EVENT_COUNT_ESC_CANCEL = 0
ASSET_MOVED_EVENT_COUNT_SUCCESSFUL_RELEASE = 1 (release path unchanged)
PASSIVE_MOUSE_MOVE_AFTER_CANCEL_RESTARTS_DRAG = NO
ROTATION_CONTROLS_AVAILABLE_AFTER_CANCEL = YES
CANCEL_RETURNS_TO_MOST_RECENT_COMMIT   = PASS (A -> commit B -> drag toward C -> cancel = B)
DIRECT_TOOL_LOCAL_DRAG_STATE_CLEARED_AFTER_CANCEL = PASS (drag state lives in the store; cleared by cancelDrag)
```

A bounded `[direct-cancel]` DEV diagnostic logs input=RESET/ESC with
preview/interaction/selection state. All prior corrections and the successful
release path are unchanged.

## Diagnosis pass — prove whether right-click / Esc reach the cancel path

The cancellation correction produced no observable effect in the browser, so
before changing cancellation semantics again, bounded input diagnostics were
added to determine conclusively what fires. **No behavior was changed** in this
pass (the `onCleanup` cancel now routes through the same shared function, which
is behaviorally identical).

Current status (manual):
```
DIRECT_DRAG_FUNCTIONALLY_WORKING = YES   SCANNER_GEOMETRY_FOLLOWS_POINTER = YES
NORMAL_DRAG_RELEASE_WORKING = YES        CONTROLLED_ROTATION_FUNCTIONALLY_WORKING = YES
LATEST_ROTATION_YAW_OBSERVED = 90
RIGHT_CLICK_CANCEL = NOT_PROVEN          ESC_CANCEL = NOT_PROVEN
DIRECT_MANIPULATION_FOUNDATION_FINAL_ACCEPTANCE = HOLD
```

Current cancel-related handlers in MrtDirectManipulationTool:
```
CURRENT_RESET_DOWN_HANDLER = PRESENT (onResetButtonDown)
CURRENT_RESET_UP_HANDLER   = PRESENT (onResetButtonUp)
CURRENT_ESCAPE_HANDLER     = PRESENT (onKeyTransition, key === "Escape")
CURRENT_CLEANUP_HANDLER    = PRESENT (onCleanup)
```

Installed input routing (verified in @itwin/core-frontend 5.12.5):
```
RIGHT_CLICK_BENTLEY_CALLBACK_PATH = ToolAdmin (BeButton.Reset) -> activeTool.onResetButtonDown (isDown) then onResetButtonUp
ESC_BENTLEY_CALLBACK_PATH         = ToolAdmin.onKeyTransition -> activeTool.onKeyTransition(wentDown, keyEvent); keyEvent.key === "Escape"
```
Note both route to the **active tool**. A leading hypothesis is that the active
Bentley tool during the interaction is NOT MrtDirectManipulationTool (e.g. the
default select tool regained the viewport), so our callbacks never fire — the
diagnostics log `activeTool=<toolId>` at each callback to confirm or refute this.

Diagnostics added (DEV-only, bounded, never per-frame):
```
DIRECT_INPUT_DIAGNOSTICS_IMPLEMENTED  = YES  ([direct-input] callback=onResetButtonDown/onResetButtonUp/onKeyTransition/onCleanup with dragActive, interaction, activeTool)
DIRECT_CANCEL_DIAGNOSTICS_IMPLEMENTED = YES  ([direct-cancel] stage=ENTER/EXIT with input, preview/interaction/selection before+after)
DIRECT_DRAG_STATE_INSPECTOR           = YES  (INSPECT DIRECT DRAG STATE dev button -> inspectDirectDragState(): activeTool, selected, interaction, committed/preview/effective)
```
Four separate stages are distinguished: INPUT_RECEIVED → CANCEL_FUNCTION_ENTERED
→ STORE_CANCEL_COMPLETED → (render). No raw DOM listeners, no pointer capture,
no context-menu suppression were added — this pass only observes.

```
RIGHT_CLICK_INPUT_CALLBACK_VISIBLE_IN_BROWSER = MANUAL_CONFIRMATION_REQUIRED
ESC_INPUT_CALLBACK_VISIBLE_IN_BROWSER         = MANUAL_CONFIRMATION_REQUIRED
CANCEL_FUNCTION_ENTERED_FROM_RIGHT_CLICK      = MANUAL_CONFIRMATION_REQUIRED
CANCEL_FUNCTION_ENTERED_FROM_ESC              = MANUAL_CONFIRMATION_REQUIRED
STORE_CANCEL_COMPLETED_FROM_RIGHT_CLICK       = MANUAL_CONFIRMATION_REQUIRED
STORE_CANCEL_COMPLETED_FROM_ESC               = MANUAL_CONFIRMATION_REQUIRED
DIRECT_MANIPULATION_FOUNDATION_FINAL_ACCEPTANCE = HOLD
```

Decision tree after the console trace: if the input callback does not fire →
next fix is tool/active-tool ownership; if it fires but cancel doesn't enter →
tool callback logic; if cancel enters but preview stays active → store cancel;
if store completes + IDLE but no visual restore → decorator invalidation.

Offline test count unchanged (instrumentation only): **185**,
OFFLINE_TEST_REGRESSIONS = 0.

## Sixth correction — right-click secondary-button routing to the cancel pipeline

The console trace resolved the diagnosis:
```
ESC_CANCEL_PIPELINE = PASS (onKeyTransition -> cancel -> DRAG_CANCELLED -> IDLE, 0 events, selection kept)
RIGHT_CLICK: no onResetButtonDown/onResetButtonUp fired; the drag ended as DRAG_COMMIT (ASSET_MOVED=1)
RIGHT_CLICK_CANCEL_PIPELINE = FAIL_BEFORE_APPLICATION_CANCEL
PRIMARY_REMAINING_FAILURE_STAGE = BENTLEY_SECONDARY_BUTTON_INPUT_ROUTING
```

Source investigation (installed @itwin/core-frontend 5.12.5): a right mouse
button maps to `BeButton.Reset` (`ToolAdmin.getMouseButton`), routed via
`onButtonDown`/`sendButtonEvent` → `onResetButtonDown`/`onResetButtonUp`.
However, during an active PRIMARY-button drag the browser handles the secondary
button as a `contextmenu` and the Reset callback is not delivered to the active
tool — the console showed the interaction ending as a normal drag commit instead.
```
PHYSICAL_RIGHT_CLICK_BROWSER_EVENT = mousedown(button=2) + contextmenu
PHYSICAL_RIGHT_CLICK_BENTLEY_BUTTON = BeButton.Reset
PHYSICAL_RIGHT_CLICK_TOOL_CALLBACK = onResetButtonDown/Up (NOT delivered during an active data-drag)
RIGHT_CLICK_RESET_CALLBACK_NOT_FIRING_REASON = during a primary-button drag the browser contextmenu/right-press is not routed to the active tool as a Reset; the left-button release ends the drag as a commit
```

Correction (sanctioned narrow fallback, section 8): a viewport-scoped
secondary-button guard is installed ONLY while an MRT direct drag is active.
`installSecondaryButtonGuard(vp)` (called after `beginDrag`) adds capture-phase
`pointerdown` and `contextmenu` listeners on `vp.parentDiv`; a `button === 2`
pointerdown (or the contextmenu) is `preventDefault`+`stopPropagation`ed and
routed to the SAME `cancelActiveDirectDrag('RIGHT_CLICK')` → `store.cancelDrag()`.
The guard is removed on commit, cancel, and cleanup (never double-installed;
StrictMode-safe). Esc's native `onKeyTransition` path is unchanged.
```
RIGHT_CLICK_ROUTING_IMPLEMENTATION = viewport-scoped capture-phase pointerdown/contextmenu guard, active ONLY during a drag
RIGHT_CLICK_FALLBACK_SCOPE = ACTIVE_MRT_DIRECT_DRAG_ONLY
GLOBAL_CONTEXT_MENU_DISABLED = NO
CANCELLATION_IMPLEMENTATION_COUNT = 1 (Esc + right-click converge on cancelActiveDirectDrag)
RIGHT_CLICK_CANCEL = PASS (offline; same store path as Esc)   RIGHT_CLICK_CANCEL_EVENT_COUNT = 0
RIGHT_CLICK_CANCEL_REQUIRES_COMPENSATING_MOVE = NO
RIGHT_CLICK_IDLE_MUTATES_ASSET = NO (guard only active during a drag)
ESC_CANCEL_REGRESSION = 0   DIRECT_DRAG_RELEASE_REGRESSION = 0   CONTROLLED_ROTATION_REGRESSION = 0
```

## Next-build requirements (documented only — NOT implemented)

```
OBJECT_ATTACHED_ROTATION_REQUIRED = YES   OBJECT_ATTACHED_ROTATION_IMPLEMENTED = NO   FLUID_YAW_ROTATION_IMPLEMENTED = NO
ASSET_DELETE_REQUIRED = YES   ASSET_DELETE_IMPLEMENTED = NO
DELETE_TARGET = SELECTED_APPLICATION_OWNED_ASSET_INSTANCE   IMODEL_ELEMENT_DELETE = NO   DELETE_MUST_MODIFY_BENTLEY_IMODEL = NO
NEXT_BUILD = OBJECT_ATTACHED_FLUID_YAW_ROTATION_AND_DELETE_FOUNDATION
```
Future delete doctrine: select → explicit DELETE → remove one AssetInstance from
SpatialAssetStore (keyed by assetInstanceId) → overlay disappears from the same
store transition → selection cleared → one `ASSET_REMOVED`; geometry definition,
catalog record, and other instances sharing the geometry are preserved; iModel
untouched. Side-panel ±90° rotation remains the fallback.

## Acceptance policy + manual acceptance (obtained)

The foundation was manually tested on the user's MacBook trackpad. The user
determined that **simultaneous primary-button drag + secondary-click is not a
natural/reliable trackpad gesture**, so right-click cancel is a deliberate UX
policy decision — NOT a technical failure and NOT a checkpoint gate. **Esc is
the authoritative cancellation mechanism** for this foundation.

```
PRIMARY_DIRECT_DRAG_CANCEL_INPUT              = ESC
ESC_CANCEL                                    = PASS
RIGHT_CLICK_CANCEL_POLICY                     = OPTIONAL_NOT_REQUIRED_FOR_MAC_TRACKPAD
RIGHT_CLICK_CANCEL_BLOCKS_CHECKPOINT          = NO
RIGHT_CLICK_CANCEL_IMPLEMENTATION_STATUS      = OPTIONAL_EXPERIMENTAL_FALLBACK (kept; harmless; not modified further)
RIGHT_CLICK_CANCEL_MANUAL_ACCEPTANCE          = NOT_REQUIRED_FOR_MAC_TRACKPAD
```

Manually demonstrated (PASS):
```
LIVE_IMODEL_VISIBLE_IN_BROWSER          = YES
DIRECT_OBJECT_SELECTION_VISIBLE         = YES
DIRECT_DRAG_VISIBLE / FUNCTIONALLY_WORKING = YES
SCANNER_GEOMETRY_FOLLOWS_POINTER        = YES   GANTRY/BORE/TABLE_FOLLOWS_DRAG_PREVIEW = YES
NORMAL_DRAG_RELEASE_WORKING             = YES
ESC_CANCEL_VISIBLE_IN_BROWSER           = YES   ESC_CANCEL_PIPELINE = PASS
ESC_DRAG_PREVIEW_CLEARED = YES   ESC_INTERACTION_RETURNS_TO_IDLE = YES   ESC_SELECTION_PRESERVED = YES   ESC_ASSET_MOVED_EVENT_COUNT = 0
CONTROLLED_ROTATION_VISIBLE / FUNCTIONALLY_WORKING = YES   (yaw 90 and 270 observed)
NON_MRT_BIM_POINTER_BEHAVIOR            = QUIET
ROTATION_AXIS = Z / YAW   ROTATION_STEP = 90 DEGREES
IMODEL_ELEMENT_DIRECT_DRAG = NO   IMODEL_MODIFIED = NO
DIRECT_MANIPULATION_FOUNDATION_FINAL_ACCEPTANCE = PASS
```

This foundation has passed manual acceptance and is being checkpointed. Offline
test count: **186** (161 + 6 preview-render + 5 decoration-acceptance + 6
lifecycle + 2 silent-non-MRT + 5 cancellation + 1 right-click parity),
OFFLINE_TEST_REGRESSIONS = 0.

Procedure: open `http://localhost:3000/viewer`; place (or reuse) a GE HealthCare
Discovery MI; click the scanner directly in the viewport → it highlights and the
Placed Assets row selects; press and drag the scanner → it follows the cursor
fluidly on its floor plane; release → it stays at the new position and
inspection shows the new committed position (same id/definition/geometry/catalog,
same rotation, same Z); drag again and cancel (right-click/Esc) → it snaps back
to the committed position with no new event; rotate ±90° then drag → yaw
preserved; confirm the command MOVE/ROTATE fallback still works.

This build is NOT staged, committed, or pushed — implementation stops here for
manual browser acceptance.

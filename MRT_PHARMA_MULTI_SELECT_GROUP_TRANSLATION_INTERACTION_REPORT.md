# MRT Pharma — Multi-Select + Group Translation + Rotation-Handle UX + Right-Click Context Menu

From baseline `085159df71b2fa90f903db76f6d88e1011ce65fe`. Three product objectives,
IMPLEMENT → VERIFY → REPORT → STOP (no checkpoint). Auth, spatial semantics,
Developer Inspector, viewer lifecycle, camera, transparency, worker/WASM all
treated as closed and unchanged.

## Selection architecture (ONE authoritative source)

`SpatialAssetStore` now owns a single selection set `selectedIds: Set<string>`
keyed by `assetInstanceId`. `selectedAssetInstanceId` (snapshot) mirrors the sole
member when exactly one is selected (single-selection compatibility) and is
undefined otherwise. New snapshot field `selectedAssetInstanceIds`. Methods:
`selectAsset` (replace/clear), `toggleAsset` (Shift add/remove), `deselectAsset`
(context DESELECT), `clearSelection` (empty click), `isSelected`,
`getSelectedIds`, `getSelectionCount`, `getSelectedInstances`. Bentley BIM
selection remains separate — never converted to MRT selection.
```
ASSET_SELECTION_STATE_SOURCE_OF_TRUTH = SpatialAssetStore.selectedIds
MULTI_SELECT_TARGET_KEY = assetInstanceId   DUPLICATE_SELECTION_IDS = NO
PRIMARY_CLICK_SELECTION = REPLACE   SHIFT_PRIMARY_CLICK_SELECTION = TOGGLE_OR_ADD   CLICK_EMPTY = CLEAR_SELECTION
MULTI_SELECTION_CREATES_NEW_ENGINEERING_IDENTITY = NO   INDIVIDUAL_ASSET_IDENTITIES_PRESERVED = YES
```

## A. Rotation-handle visual state machine

Pure seam `resolveRotationHandleVisualState({isOwnedAppAsset,isThisSelected,
selectedCount,hover,rotating}) -> HIDDEN | IDLE_HINT | HOVER | ACTIVE_ROTATION`.
The decorator draws the ring ONLY for the sole selected application-owned asset,
in neutral GREY (no orange/yellow), prominence via transparency: IDLE_HINT ≈ 205
(extremely faint), HOVER ≈ 70 (subtle), ACTIVE_ROTATION = 0 (clear). The
pick surface is always drawn so the handle stays discoverable; the manipulation
tool sets a hover flag when the pointer nears the projected ring (reusing the
scoped screen-space fallback). Hidden when unselected, when >1 selected, and for
catalog/DEV/BIM geometry (the decorator only ever draws app-owned instances).
```
ROTATION_HANDLE_ORANGE_YELLOW = NO   IDLE_COLOR = VERY_FAINT_GREY   ACTIVE_COLOR = GREY
UNSELECTED_OBJECT_ROTATION_HANDLE_VISIBLE = NO   MULTI_SELECTION_ROTATION_HANDLE_VISIBLE = NO
ROTATION_HANDLE_AFTER_ROTATION_RELEASE = HIDDEN_OR_EXTREMELY_FAINT   AFTER_CLICK_OUTSIDE = HIDDEN
ROTATION_HANDLE_DISCOVERABLE = YES   VISUAL_PROMINENCE_IDLE = LOW
```

## B. Right-click asset context menu

Pure decision `resolveAssetContextMenu(target, isSelected) -> {assetInstanceId,
actions}` — app asset only; unselected → `SELECT + DELETE`, selected →
`DESELECT + DELETE`; undefined for BIM/empty/catalog/DEV. The tool's reset-button
(right-click) is now the OBJECT CONTEXT MENU surface (no longer drag-cancel; Esc
is authoritative cancel). During any active gesture right-click is ignored (DOM
guard suppresses the browser menu). Menu state is UI-only in the overlay
(`{assetInstanceId,screenX,screenY}`), rendered by `ViewerAssetContextMenu`.
DELETE reuses the EXISTING controlled delete (`deleteAsset` + `window.confirm` +
USER_PLACED guard). Auto-closes on action / empty-click / Esc / stale target.
```
RIGHT_CLICK_MRT_ASSET_CONTEXT_MENU = YES   TARGET_KEY = assetInstanceId
UNSELECTED_ACTIONS = SELECT + DELETE   SELECTED_ACTIONS = DESELECT + DELETE
RIGHT_CLICK_SELECT_POLICY = REPLACE_SELECTION_WITH_TARGET
RIGHT_CLICK_DELETE_REUSES_EXISTING_DELETE = YES   DELETE_IMPLEMENTATION_COUNT = 1
RIGHT_CLICK_{BIM,EMPTY,GENERIC_DEV,CATALOG_TEST}_MRT_MENU = NO
ESC_AUTHORITATIVE_CANCEL_INPUT = YES   RIGHT_CLICK_CANCEL_PRIMARY_ROLE = NO
BULK_DELETE_IMPLEMENTED = NO   RIGHT_CLICK_DELETE_WITH_MULTI_SELECTION = DELETE_TARGET_ONLY
```

## C. Multi-select + group translation

Store `GroupDragPreview` (ids, anchor, startPositions, grabOffset,
translationDelta, previewPositions). `beginGroupDrag` (requires anchor selected +
≥2 members), `updateGroupDragPreview` (X/Y delta from anchor grab offset applied
to every member; each keeps its OWN start Z), `commitGroupDrag` (builds all
resulting instances first then applies ONE state update — atomic, no partial
commit; ONE `ASSET_MOVED` per member whose position actually changed; zero-delta
members emit nothing), `cancelGroupDrag`. New interaction state
`GROUP_TRANSLATING` (explicit, mutually exclusive). `getEffectiveProjectInstances`
applies the group preview so all members follow the pointer. The tool routes a
body drag to GROUP when the grabbed member is selected and count>1, else SINGLE;
anchor grab offset preserved (no initial jump).
```
MULTI_ASSET_SELECTION_IMPLEMENTED = YES   GROUP_TRANSLATION_IMPLEMENTED = YES   GROUP_ROTATION_IMPLEMENTED = NO
GROUP_PREVIEW_NON_AUTHORITATIVE = PASS   GROUP_RELATIVE_OFFSETS_PRESERVED = PASS
GROUP_TRANSLATION_Z_BEHAVIOR = PRESERVE_EACH_START_Z
ASSET_MOVED_EVENTS_DURING_GROUP_POINTER_MOVE = 0   GROUP_COMMIT_ASSET_MOVED_EVENT_COUNT = N_MOVED_ASSETS
GROUP_CANCEL_ASSET_MOVED_EVENT_COUNT = 0   PARTIAL_GROUP_COMMIT = NO   GROUP_ZERO_DELTA_EVENT_COUNT = 0
GROUP_SELECTION_PRESERVED_AFTER_COMMIT = YES   AFTER_CANCEL = YES
GROUP_TRANSLATION_IDENTITY_IMMUTABILITY = PASS   GROUP_DRAG_INITIAL_JUMP = NO
AUTHORITATIVE_SPATIAL_ASSOCIATION_CHANGES_DURING_GROUP_PREVIEW = 0   GROUP_COMMIT_REASSOCIATION = DERIVED_AFTER_COMMIT
BIM_ELEMENT_GROUP_TRANSLATION = NO   BENTLEY_CHANGESET_CREATED = NO
```

## Machine verification

```
PRECHECK_HEAD/ORIGIN/DIVERGENCE = 085159d / 085159d / 0-0
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 284   NEW_TEST_COUNT = 22 (multiSelectGroupTranslation.test.ts)   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5
WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES   /viewer = 200
AUTH_FLOW_CHANGED = NO   PKCE_CHANGED = NO   SIGNIN_CALLBACK_BEHAVIOR_CHANGED = NO   AUTH_CLIENT_MEMOIZATION_CHANGED = NO
VIEWER_LIFECYCLE_CHANGED = NO   CAMERA_BEHAVIOR_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO
DEV_INSPECTOR_REGRESSION = 0   VERBOSE_DEV_TEXT_OVER_3D_VIEWPORT = NO
```
Offline tests: rotation visual states, handle ownership, context-menu decision
(select/deselect/delete, no both, no menu for non-target), multi-selection
transitions + single-selection compatibility + replace + delete-removes-from-
selection, group preview math (offsets + own Z), group commit (N events, IDLE,
selection kept), group cancel (0 events, restore), identity immutability,
non-selected isolation, zero-delta no-op, ≥2/anchor guards, per-member Z.

## Manual acceptance (STOP — do not checkpoint)

All MANUAL_CONFIRMATION_REQUIRED. Suggested order: (1) rotation-handle visual
UX — no bright ring; faint/hidden idle grey; hover reveals; clear during
rotate; hidden after release; (2) click-outside deselect hides handle; (3)
right-click unselected → Select+Delete, selected → Deselect+Delete; (4) Delete
Cancel/Confirm; (5) Shift multi-select (place ≥2 scanners); (6) group drag one
selected member moves the group with preserved spacing + own Z, non-selected
isolated, release = N ASSET_MOVED; (7) group Esc cancel restores; (8)
single-asset drag/rotate/±90°/Delete regression; (9) spatial-semantics +
Developer Inspector regression; (10) refresh auth regression. Negative right-
click targets (BIM/empty/catalog/DEV) → no MRT menu.
```
CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE
```

## Regression correction — PLACE IN MODEL stalled at "Signing in with Bentley…"

Manual regression: `PLACE_IN_MODEL_MANUAL_REGRESSION = CONFIRMED`; the viewer
stalled at "Signing in with Bentley…" (`LiveItwinViewer.tsx:180`, rendered while
`!ready`, i.e. `signInSilent()` had not resolved).

Diagnosis (no auth/viewer files were edited by this build —
`INTERACTION_BUILD_DIRECT_AUTH_CHANGE = NO`): the only new element in the viewer
render tree was `<ViewerAssetContextMenu>`, a lazy component initially placed
INSIDE the same viewport `<Suspense>` boundary as `<LiveItwinViewer>`. On first
render its lazy chunk suspends; a suspension can drop the shared boundary to its
fallback and unmount the in-flight `<LiveItwinViewer>`, interrupting the
one-shot Bentley sign-in effect (the exact "stuck on Signing in…" failure mode
documented in that component) — `PLACE_IN_MODEL_STALL_STAGE =
VIEWER_SUBTREE_UNMOUNT_INTERRUPTS_SIGN_IN`. The store's external-store snapshot
was verified referentially stable (`SELECTION_SNAPSHOT_STABLE_WITHOUT_STATE_CHANGE
= PASS`, `CONTEXT_MENU_SNAPSHOT_STABLE = PASS`) so a render loop was ruled out.

Correction (smallest safe change): render `<ViewerAssetContextMenu>` OUTSIDE the
viewer `<Suspense>` boundary, gated on `auth.state === 'AUTHENTICATED'`, so it
only mounts after sign-in completes and can never unmount `LiveItwinViewer` or
interrupt its auth effect. No change to auth, PKCE, the auth-client factory, the
viewer lifecycle, or any spatial/selection/group/rotation code. Interaction work
preserved (`INTERACTION_BUILD_DISCARDED = NO`).
```
ROOT_CAUSE = ViewerAssetContextMenu lazy sibling shared the viewer <Suspense> boundary; its suspension could unmount LiveItwinViewer mid-sign-in
CORRECTION = render the context menu outside the viewer Suspense, gated on auth.state === 'AUTHENTICATED'
INTERACTION_BUILD_DIRECT_AUTH_CHANGE = NO   INTERACTION_BUILD_INDIRECT_VIEWER_LIFECYCLE_CHANGE = NO (now)
PLACE_BUTTON_RESTARTS_AUTH = NO   PLACE_BUTTON_RESTARTS_VIEWER = NO
CONTEXT_MENU_SNAPSHOT_STABLE = PASS   SELECTION_SNAPSHOT_STABLE_WITHOUT_STATE_CHANGE = PASS
INTERACTION_SUBSCRIPTION_LOOP = NO   AUTH_FLOW_CHANGED = NO   PKCE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO   IMODEL_MODIFIED = NO
OFFLINE_TEST_COUNT = 287 (+3 snapshot-stability regression tests)   OFFLINE_TEST_REGRESSIONS = 0   TYPECHECK = PASS   PRODUCTION_BUILD = PASS
PLACE_IN_MODEL_FOUNDATION_RESTORED = MANUAL_CONFIRMATION_REQUIRED
```
Manual re-test required FIRST: open `/viewer`, confirm the BIM loads, click PLACE
IN MODEL → placement proceeds (no "Signing in…" stall), click a position → scanner
appears, Placed Assets increments. Only after that resume the three-objective
acceptance.

## Correction 2 — restore single-asset drag + marquee (bounding-box) multi-select

Manual regression: `SINGLE_SELECTED_ASSET_DRAG_RELIABILITY = FAIL`,
`SHIFT_CLICK_MULTI_SELECT = REJECTED`. Product decision: multi-select is now
primarily **marquee/bounding-box** (`MULTI_SELECT_PRIMARY_METHOD =
BOUNDING_BOX_MARQUEE`; Shift-click optional, not required).

Single-drag root cause: `onMouseStartDrag`'s group-eligibility used raw
`getSelectionCount()`; a stale/multi selection could route a body drag into
`beginGroupDrag`, and if that begin failed (selection resolved to <2 valid
members) the handler returned `EventHandled.No` — the scanner refused to move.
`SINGLE_DRAG_FAILURE_STAGE = group-routing-without-fallback + count-includes-stale-ids`.

Correction (targeted): eligibility now uses `getSelectedInstances().length`
(VALID existing members only); if `beginGroupDrag` fails, the tool FALLS BACK to
single `beginDrag` so a drag is never swallowed. Added store `replaceSelection`
(marquee release; ignores stale ids) + `pruneStaleSelection`. `[interaction-pick]`
diagnostics added. One selected asset always routes to single translation
(`SINGLE_DRAG_USES_GROUP_PREVIEW = NO`).

Marquee (bounding-box) selection:
- pure seams `normalizeScreenRect` / `screenRectsIntersect` / `screenDragDistance`
  / `marqueeSelect` (partial screen-space bounds INTERSECT — no full containment).
- `computeAssetScreenBounds` projects each project AssetInstance's 8 yaw-rotated
  bbox corners via `worldToView` → conservative screen rect (rotated assets
  supported). `MARQUEE_PROJECTED_BOUNDS_SOURCE = AssetInstance transform + dimensions
  projected through the live viewport`.
- Tool: empty-space primary drag → marquee (claims the drag, camera suppressed
  for the gesture); motion updates a UI-only rect (`ViewerMarqueeOverlay`, view px,
  restrained blue); release with drag ≥ 5px → `replaceSelection(intersecting)`
  (empty result clears); below threshold → empty click clear; Esc → restore prior
  selection. Object/handle drags keep priority (marquee only starts on EMPTY).
- Targets application-owned AssetInstances only; never BIM/catalog/DEV/room.

```
MULTI_SELECT_PRIMARY_METHOD = BOUNDING_BOX_MARQUEE   SHIFT_CLICK_MULTI_SELECT_REQUIRED = NO
MARQUEE_START = PRIMARY_DRAG_ON_EMPTY_VIEWPORT   MARQUEE_STEALS_OBJECT_DRAG = NO
MARQUEE_SELECTION_RULE = SCREEN_SPACE_BOUNDS_INTERSECT_SELECTION_RECTANGLE
MARQUEE_RELEASE_SELECTION_POLICY = REPLACE_SELECTION   MARQUEE_MINIMUM_DRAG_THRESHOLD = 5px
MARQUEE_ROTATED_ASSET_SELECTION = SUPPORTED   MARQUEE_{BIM,CATALOG_TEST,GENERIC_DEV}_SELECTION = NO
MARQUEE_ESC_CANCEL = restore-prior   MARQUEE_SELECTION_ENGINEERING_EVENT_COUNT = 0
SINGLE_DRAG_USES_GROUP_PREVIEW = NO   GROUP_DRAG_STALE_MEMBER_POLICY = valid-members-only + single fallback
SELECTED_COUNT_1_BODY_DRAG = SINGLE_TRANSLATION   CAMERA_MOVES_DURING_MARQUEE = NO
GESTURE priority: selected-body -> single/group ; unselected-body -> select+single ; ring -> rotate ; empty -> marquee
TYPECHECK = PASS   OFFLINE_TEST_COUNT = 297 (+10)   OFFLINE_TEST_REGRESSIONS = 0   PRODUCTION_BUILD = PASS   /viewer = 200
AUTH_FLOW_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO   IMODEL_MODIFIED = NO
```
MANUAL_CONFIRMATION_REQUIRED (test single-drag FIRST): single-asset drag,
empty-space marquee (both directions), marquee BIM isolation, multi-select UI,
group translation + Esc cancel, marquee Esc cancel, empty click, body-drag
accessibility vs rotation handle, right-click regression, single rotation
regression, spatial-semantics regression, refresh-auth regression.

## Correction 3 — group translation did not start after marquee selection

Manual evidence: marquee multi-select PASS, rectangle clears PASS, multiple
selection visible PASS — but dragging a selected member did not move the group
(`GROUP_TRANSLATION_START_VISIBLE_IN_BROWSER = FAIL`).

Root cause (traced, suspect C): `onDataButtonDown` fires on the button PRESS,
before `onMouseStartDrag`. Its plain-press branch called
`selectAsset(target)` which REPLACES the selection with that single asset — so a
press on a marquee-selected member collapsed the {A,B} selection to {A} before
`onMouseStartDrag` evaluated group eligibility. `validSelectedCount` was then 1 →
single drag. `MARQUEE_VISIBLE_SELECTION_MATCHES_STORE = PASS` (marquee itself was
fine); the collapse happened at drag-press. `BEGIN_GROUP_DRAG_RESULT` was never
reached for the group.

Correction (narrow, `onDataButtonDown` only): pressing an ALREADY-selected member
no longer collapses the selection — the current selection is preserved so the
ensuing body drag starts as a group drag. Pressing an UNSELECTED asset still
replaces the selection; Shift still toggles; empty press still clears. Added
`[group-drag]` diagnostics (POINTER_DOWN / BEGIN_ATTEMPT / PREVIEW). No change to
marquee, group math, decorator cache (already dynamic during
`isGroupDragActive()`), single-drag, rotation, right-click, auth, or spatial
semantics.

```
ROOT_CAUSE = onDataButtonDown press-branch collapsed the multi-selection (selectAsset replace) before onMouseStartDrag, forcing single drag
CORRECTION = press on an already-selected member preserves the selection; unselected press replaces; shift toggles; empty clears
MARQUEE_VISIBLE_SELECTION_MATCHES_STORE = PASS
GROUP_ELIGIBILITY_RULE = targetSelected && getSelectedInstances().length > 1
GROUP_DRAG_PICK_TARGET = ASSET_BODY   BODY_DRAG_FALSE_ROTATION_HANDLE_PICK = NO   BODY_DRAG_FALSE_EMPTY_PICK = NO
GROUP_INTERACTION_STATE_AFTER_BEGIN = GROUP_TRANSLATING
GROUP_PREVIEW_USED_BY_RENDERER = YES (getEffectiveProjectInstances applies group preview)
CACHED_DECORATIONS_DURING_GROUP_TRANSLATION = NO (useCachedDecorations undefined while isGroupDragActive)
GROUP_TRANSLATION_Z_BEHAVIOR = PRESERVE_EACH_START_Z
TYPECHECK = PASS   OFFLINE_TEST_COUNT = 300 (+3 marquee-to-group routing)   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   /viewer = 200
AUTH_FLOW_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO   IMODEL_MODIFIED = NO
```
Manual re-test: place ≥2 scanners → marquee-select both → drag a selected
scanner body → both move together; release → both stay; group Esc → both restore.
Console `[group-drag] stage=BEGIN_ATTEMPT result=PASS memberCount=2` confirms.
GROUP_TRANSLATION_MANUAL_ACCEPTANCE = MANUAL_CONFIRMATION_REQUIRED.

## Correction 4 — group translation crashed in Bentley decoration-cache invalidation

Decisive runtime evidence: group drag reached the preview update, then threw
`Assert: Programmer Error` in `DecorationsCache.delete` ←
`ScreenViewport.invalidateCachedDecorations` ← `invalidateDecorations` ←
`SpatialAssetStore.emit` ← `updateGroupDragPreview`.

Root cause: the overlay's `invalidateDecorations()` chose its redraw path from
`isDragActive() || isRotationActive()` — it did NOT include `isGroupDragActive()`.
During a group drag the decorator's `useCachedDecorations` returns `undefined`
(cache disabled — group-active was correctly wired there), so there is NO cache
entry. But `invalidateDecorations` fell into the else branch and called
`vp.invalidateCachedDecorations(decorator)`, which asserts in
`DecorationsCache.delete` because there is no cache entry to delete for a
decorator that is not currently caching. `INVALIDATION_CALLED_WHILE_CACHE_DISABLED
= YES` — the direct defect. (Not double-invalidation, not a stale/disposed
viewport, not a store→Bentley coupling.)

Correction (narrow): the redraw decision now goes through a pure seam
`resolveDecorationRedrawPolicy({dragActive, groupDragActive, rotationActive})`
that mirrors `useCachedDecorations` exactly — any active preview (single drag,
GROUP drag, rotation) → `DYNAMIC_REDRAW` (`vp.invalidateDecorations()`, safe, no
cache touch); idle → `CACHE_INVALIDATE` (`vp.invalidateCachedDecorations(decorator)`).
This keeps the redraw path and the caching predicate in lockstep so they can
never drift again. The store stays Bentley-free (`SPATIAL_STORE_BENTLEY_DEPENDENCY_ADDED
= NO`). Bounded `[decor-cache] stage=REDRAW policy=DYNAMIC_REDRAW` diagnostics
(first 6). No change to selection box, group math, single drag, rotation, right-
click, auth, or spatial semantics.

```
ROOT_CAUSE = invalidateDecorations omitted isGroupDragActive() -> called invalidateCachedDecorations on a decorator with no cache entry -> DecorationsCache.delete assert
ACTIVE_PREVIEW_REDRAW_STRATEGY = cache disabled (useCachedDecorations undefined) + vp.invalidateDecorations() (plain redraw)
CORRECTION = resolveDecorationRedrawPolicy seam mirrors useCachedDecorations; group drag -> DYNAMIC_REDRAW
INVALIDATION_CALLED_WHILE_CACHE_DISABLED (before) = YES -> (after) = NO
INVALIDATE_NONEXISTENT_DECORATION_CACHE_ENTRY = NO   DOUBLE_INVALIDATION_PRESENT = NO
VIEWPORT_DISPOSED_DURING_INVALIDATION = NO   DECORATOR_REGISTERED_WITH_VIEWPORT = YES
SINGLE_DRAG_REDRAW_STRATEGY = DYNAMIC_REDRAW (unchanged)   SINGLE_DRAG_DECORATION_ASSERT = NO
ROTATION_PREVIEW_DECORATION_ASSERT = NO   CACHED_DECORATIONS_DURING_GROUP_TRANSLATION = NO
SPATIAL_STORE_BENTLEY_DEPENDENCY_ADDED = NO
TYPECHECK = PASS   OFFLINE_TEST_COUNT = 305 (+5 redraw-policy)   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   /viewer = 200
AUTH_FLOW_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO   IMODEL_MODIFIED = NO
```
Manual re-test: place 2 scanners → selection box both → drag one selected scanner
→ both move together, NO Bentley assert dialog → release both stay → group Esc
restores. `GROUP_PREVIEW_CRASH = NO`, `GROUP_RELEASE_CRASH = NO`,
`GROUP_CANCEL_CRASH = NO`, `GROUP_GEOMETRY_FOLLOWS_POINTER = MANUAL_CONFIRMATION_REQUIRED`.

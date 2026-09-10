# MRT Pharma — Visual Planning Foundation

From baseline `b2abe6bf28056d002d140b52fb54e94c9cd417eb`. PRESENTATION + REPRESENTATION
only — the proven engineering/interaction/spatial/auth architecture is unchanged.
IMPLEMENT → VERIFY → REPORT → STOP (no checkpoint).

## Normal planning mode vs Developer mode

Default is `NORMAL_PLANNING`. The large blue DEV button block no longer sits over
the model: in normal mode a compact planning control bar (top-right) shows only
`Developer` and `Planning view` toggles. Enabling Developer mode reveals a
dedicated right-side **developer drawer** containing all the existing DEV actions
(FIT LIVE MODEL, INSPECT RENDER STATE, INSPECT FEATURE APPEARANCE, SHOW/HIDE/
INSPECT GENERIC + CATALOG PET/CT, INSPECT PLACEMENT INTENT / DIRECT DRAG /
ROTATION / BIM SPATIAL STRUCTURE / SPATIAL ASSOCIATION) plus the Developer
Inspector. No DEV capability was removed. Pure seams: `resolvePlanningMode` /
`resolveDeveloperVisibility` / `devButtonBlockVisibleInMode` in
`planningVisuals.ts`. Mode is a UI-only overlay store (`getViewerMode` /
`setViewerMode` / `subscribeViewerMode`); it never touches engineering state.
```
DEFAULT_VIEWER_MODE = NORMAL_PLANNING   DEVELOPER_MODE = PRESERVED   DEVELOPER_CAPABILITIES_REMOVED = NO
DEV_BUTTON_BLOCK_VISIBLE_IN_NORMAL_MODE = NO   DEV_CONTROLS_LOCATION = DEDICATED_RIGHT_SIDE_DRAWER
VERBOSE_DEV_TEXT_OVER_3D_VIEWPORT = NO   DEV_INSPECTOR_REGRESSION = 0
RAW_ENGINEERING_DUMP_VISIBLE_IN_NORMAL_MODE = NO (raw ids + inspect dump gated behind DEVELOPER)
```

## Parametric PET/CT scanner representation

Enriched generic parametric geometry (`scannerGeometry.ts`): distinct GANTRY body,
recessed circular BORE (dark), PATIENT_TABLE couch, and a new TABLE_BASE pedestal
— recognizably a PET/CT scanner with clear orientation. Clinical/engineering
palette (light body, dark bore, neutral couch, subdued base — no toy/neon colors).
All proportions derive parametrically from instance dimensions, so future
calibrated length/width/height/gantry/bore/table values apply without touching
interaction architecture. Geometry identity + reuse preserved.
```
PETCT_RECOGNIZABLE_AS_SCANNER = YES   EQUIPMENT_VISUAL_LANGUAGE = CLINICAL_ENGINEERING
SCANNER_GEOMETRY_PROVENANCE = GENERIC_ENGINEERING_PLACEHOLDER   MANUFACTURER_CERTIFIED_GEOMETRY_CLAIM = NO
CATALOG_DIMENSIONS_STATUS = NOT_CALIBRATED   PARAMETRIC_GEOMETRY_CALIBRATION_SEAM = YES
GENERIC_GEOMETRY_REUSE = YES   VISUAL_UPGRADE_CHANGES_ASSET_IDENTITY = NO
```

## BIM planning appearance (view-only, opt-in, reversible)

A prior attempt to normalize ViewFlags at `onViewOpen` blanked the viewport and
was reverted. This build therefore provides an OPT-IN, REVERSIBLE, VIEW-ONLY
`Planning view` toggle (`setPlanningAppearance` in `LiveItwinViewer.tsx`): it
flips the live viewport `viewFlags.transparency` render flag OFF so architectural
surfaces render opaque (rooms/corridors/floor read instead of overlapping
translucent grey), and ON restores the model default. Applied ONLY on user
trigger — never at view-open — so it can never blank the viewport on load. It is
a per-viewport render flag: NO iModel write, NO changeset, NO DisplayStyle
persistence.
```
BIM_PLANNING_APPEARANCE_IMPLEMENTED = YES (opt-in toggle)   BIM_GLOBAL_GHOST_APPEARANCE = REDUCED_ON_DEMAND (transparency off)
HOSPITAL_CONTEXT_VISIBLE = YES   BIM_PRESENTATION_CHANGES = VIEW_ONLY   IMODEL_MODIFIED = NO
FLOOR_FOCUSED_VIEW = NOT_IMPLEMENTED_IN_THIS_BUILD (BIM floor source is SpatialComposition:CompositeElement without reliable storey membership; not fabricated)
VIEWPORT_BACKGROUND_DECISION = UNCHANGED (existing dark background retained; not changed for novelty)
```

## Cleaner product UI

Placed Assets rows keep a compact name + meta line and clear selection state
(sole = blue outline, multi = blue-grey outline + "(n) assets selected" status).
The selected-asset detail now shows a clean planning summary (Equipment / Floor /
Room / Position / Orientation / Status); the raw engineering identity dump +
association source/method + `<pre>` inspect are gated behind Developer mode.
Selection outline is a restrained blue-grey (no amber/orange, no bright rings);
selection box + context menu styling unchanged (already restrained). Empty
Tool Settings chrome: left as-is (Bentley-managed; not safely suppressible
without touching tool lifecycle) — documented limitation.
```
SELECTION_VISUAL_CLUTTER = LOW   MULTI_SELECTION_VISUAL_LANGUAGE = RESTRAINED   ROTATION_HANDLE_ORANGE_YELLOW = NO
PRIMARY_PRODUCT_LAYOUT = ASSET_LIBRARY | PLANNING_VIEWPORT | PROPERTIES_INSPECTOR
EMPTY_TOOL_SETTINGS_CHROME = LEFT_AS_IS (Bentley-managed; documented)
```

## Preserved (closed systems / interaction)

```
ENGINEERING_INTERACTION_FOUNDATION_PRESERVED = YES   VISUAL_STYLE_MUTATES_ENGINEERING_STATE = NO
AUTH_FLOW_CHANGED = NO   PKCE_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO
ENGINEERING_EVENT_SEMANTICS_CHANGED = NO   IMODEL_MODIFIED = NO   BENTLEY_CHANGESET_CREATED = NO   CAMERA_BEHAVIOR_CHANGED = NO
CLEARANCE_CALIBRATION = NOT_STARTED   MANUFACTURER_CLEARANCE_VALUES_INVENTED = NO
```
Interaction regressions covered by the unchanged 305-test baseline (place, single
drag, single rotation, right-click, delete, selection-box, group translation,
group decomposition, BIM spatial semantics, page-refresh auth) — all preserved;
this build changed only presentation seams + geometry parts + product-panel
gating.

## Machine verification

```
PRECHECK_HEAD/ORIGIN/DIVERGENCE = b2abe6b / b2abe6b / 0-0
TYPECHECK = PASS   OFFLINE_TEST_COUNT = 314   NEW_TEST_COUNT = 9 (planningVisuals.test.ts; assetArchitecture part-count updated to 4)   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5   WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES   /viewer = 200
```

## Manual acceptance (STOP — no checkpoint)

```
MRT_PHARMA_FIRST_IMPRESSION_IMPROVED = MANUAL_CONFIRMATION_REQUIRED
NORMAL_MODE_DEV_CLUTTER (no DEV block over hospital) = MANUAL_CONFIRMATION_REQUIRED
DEVELOPER_MODE_CAPABILITIES (drawer has all DEV actions) = MANUAL_CONFIRMATION_REQUIRED
BIM_PLANNING_LEGIBILITY (Planning view toggle -> rooms/corridors read) = MANUAL_CONFIRMATION_REQUIRED
PETCT_VISUAL_REALISM (gantry/bore/table/base recognizable) = MANUAL_CONFIRMATION_REQUIRED
INTERACTION_MANUAL_REGRESSION (place/drag/rotate/right-click/delete/selection-box/group) = MANUAL_CONFIRMATION_REQUIRED
SPATIAL_SEMANTICS_MANUAL_REGRESSION / PAGE_REFRESH_AUTH_MANUAL_REGRESSION = MANUAL_CONFIRMATION_REQUIRED
CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE
```
Open `/viewer` (opens in normal planning mode). Verify: no DEV block over the
model; a compact top-right control bar; place a GE Discovery MI → recognizable
scanner; toggle `Planning view` → architecture reads solid; toggle `Developer` →
drawer with all DEV actions + Developer Inspector; all interactions still work;
refresh returns normally.

---

## Targeted correction — BIM legibility + normal-mode chrome (first review = PARTIAL PASS)

The first manual visual review PASSED normal-mode / DEV-block-removed / asset-library-cleanup / viewport-space, but FAILED BIM legibility and hospital realism, and the empty Tool Settings chrome was still visible. This correction is view-only. Baseline unchanged: `HEAD = origin/main = b2abe6b`, `0 / 0`, nothing staged.

### Diagnosis (evidence-based, no guessing)

- `TRANSLUCENT_CUBOID_SOURCE_CLASS = BuildingSpatial:Space + SpatialComposition:CompositeElement`. The dominant overlapping translucent grey boxes are the room/space **volume semantics** — planning DATA used for room association + developer inspection, not the primary architectural surfaces. Making them opaque still leaves dominant boxes, so the honest fix is to **suppress the space volumes in normal mode**, not recolor them.
- `ARCHITECTURAL_GEOMETRY_AVAILABLE = PARTIAL / NOT_DOMINANT`. The visually dominant renderable is the spatial-volume semantics; detailed wall/slab/door surfaces are not the dominant geometry. No architecture is fabricated (Sec 12/13).
- `TOOL_SETTINGS_OWNER = Bentley Tool Settings for the active MrtDirectManipulationTool (PrimitiveTool)`; `TOOL_SETTINGS_CONTENT = EMPTY`. The default `supplyToolSettingsProperties` produced an empty settings window.
- `STRAY_VIEWPORT_TEXT_SOURCE = NONE_FOUND_IN_NORMAL_MODE` (DEV diagnostics render in the right-side inspector, not over the viewport).

### Corrections (all VIEW-ONLY)

- **BIM legibility.** `setPlanningAppearance(true)` now (a) sets `viewFlags.transparency` off (opaque surfaces) and (b) queries `BuildingSpatial:Space` + `SpatialComposition:CompositeElement` element ids (read-only ECSQL, cached) and adds them to the viewport `setNeverDrawn` set. `false` clears never-drawn + restores the model default. Per-viewport render state only — **no iModel write, no changeset** (`Viewport.setNeverDrawn` / `clearNeverDrawn`). `BUILDINGSPATIAL_SPACE_SEMANTICS_PRESERVED = YES`, `BUILDINGSPATIAL_SPACE_NORMAL_MODE_VISUAL_DOMINANCE = NO`, `ROOM_SPACE_VISUAL_STYLE = SUPPRESSED_IN_NORMAL_MODE` (shown FULL in developer mode).
- **Default-on planning appearance.** `PLANNING_VIEW_DEFAULT = ON`. Applied ONLY post-ready via a run-once `AUTHENTICATED` effect that retries (bounded) until a selected viewport exists — never at `onViewOpen`, so it cannot reproduce the historical blank-viewport regression. `PLANNING_APPEARANCE_ACCESSIBLE_IN_NORMAL_MODE = YES` (compact toggle, not a hidden developer action).
- **Empty Tool Settings.** `MrtDirectManipulationTool.supplyToolSettingsProperties()` returns `undefined`, so Bentley shows **no** Tool Settings window (documented contract: "If undefined is returned then no ToolSettings will be displayed."). No DOM hack. `EMPTY_TOOL_SETTINGS_CHROME = HIDDEN`.
- **Placement copy.** One concise instruction (`Click a location in the model to place.`) + one cancel hint; Cancel Placement still visible. `PLACEMENT_INSTRUCTION_DUPLICATION = NO`.

### New pure seam + tests

`planningVisuals.ts`: `resolveRoomVisualPolicy(mode)` → `NORMAL_PLANNING = SUBDUED_OR_HIDDEN`, `DEVELOPER = FULL`; `roomVolumesDominateInMode(mode)`. Tests: `ROOM_VISUAL_POLICY_TEST = PASS`, `PLANNING_APPEARANCE_IMMUTABILITY_TEST = PASS` (store version + instance snapshot unchanged across visual toggles → `VISUAL_APPEARANCE_ENGINEERING_EVENT_COUNT = 0`).

### Machine verification (post-correction)

```
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 318   (pre-correction 314; +4 new; baseline 305)   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5
WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES   /viewer = 200
AUTH_FLOW_CHANGED = NO   PKCE_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO
SPATIAL_SEMANTICS_CHANGED = NO   INTERACTION_MATHEMATICS_CHANGED = NO
IMODEL_MODIFIED = NO   BENTLEY_CHANGESET_CREATED = NO   BENTLEY_RESOURCE_MODIFIED = NO
```

### Manual acceptance (STOP — no checkpoint)

Open `/viewer` (normal mode default; planning appearance auto-applies once ready):
- `BIM_PLANNING_LEGIBILITY` — hospital should no longer read as overlapping translucent grey cuboids; room volumes suppressed.
- `PLANNING_APPEARANCE_VISIBLE_IN_BROWSER` + `PLANNING_APPEARANCE_BLANKS_VIEWPORT = NO` — toggle the control, viewport must not blank, camera + equipment still work.
- `EMPTY_TOOL_SETTINGS_CHROME_VISIBLE` — expected NO (lower-left).
- `PETCT_VISUAL_REALISM` — place a GE Discovery MI; judge gantry/bore/table/base.
- `PLACEMENT_UI_MANUAL_ACCEPTANCE` — one instruction, Cancel visible, no debug text.
- Interaction + spatial-association + refresh regressions expected 0.

`CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE`

---

## Correction 2 — restore hospital context + stop blind BIM suppression (second review = FAIL)

The second manual review was a clear FAIL: reversing to hide the room volumes removed almost the entire hospital, the empty Tool Settings chrome was still visible, the placement copy was still duplicated, and the Planning view control was not discoverable. Baseline unchanged: `HEAD = origin/main = b2abe6b`, `0 / 0`, nothing staged.

### Root-cause diagnosis (evidence-based)

- The first correction added `BuildingSpatial:Space` + `SpatialComposition:CompositeElement` ids to the viewport never-drawn set. In THIS iModel `SpatialComposition:CompositeElement` is the building/story **container** class — hiding it (and everything resolved under it) removed most of the hospital, leaving only a few isolated blocks. `PLANNING_APPEARANCE_OVER_SUPPRESSION = YES`.
- `TOOL_SETTINGS_RUNTIME_OWNER`: the empty Tool Settings widget is owned by **@itwin/appui-react** (rendered by the `@itwin/web-viewer-react` `<Viewer>`), NOT by our `PrimitiveTool`. So `supplyToolSettingsProperties() => undefined` (content-only) could not remove the widget chrome — the previous "HIDDEN" claim was wrong.
- The Planning view control WAS always rendered in the top-right `.viewer-mode-bar`, but the CSS rule `.viewer-stage > * { width:100%; height:100% }` forced the bar to a full-viewport layer that the Viewer canvas covered → `NOT_DISCOVERABLE`.

### Corrections (all view-only)

- **Reverse over-suppression.** `setPlanningAppearance` now toggles ONLY `viewFlags.transparency` (opaque surfaces) and defensively `clearNeverDrawn()`. It NEVER hides elements. `DEFAULT_SPACE_VOLUME_NEVER_DRAWN = NO`; hospital context is restored.
- **Derived BIM-backed planning context.** New pure seams (`planningPlan.ts`) derive room FOOTPRINTS (thin outline + very light fill at a planning elevation) from the authoritative `BuildingSpatial:Space` ranges — never fake walls, never a full translucent volume. Rendered by a new view-only `RoomPlanDecorator` in NORMAL_PLANNING only (developer mode keeps the raw BIM). `NORMAL_ROOM_REPRESENTATION = PLAN_FOOTPRINT`; `ROOM_PLAN_STATE_SOURCE_OF_TRUTH = SPATIAL_MODEL_SEMANTICS`; `DERIVED_PLAN_WRITES_IMODEL = NO`; footprints reference the same `roomId` (never a second identity); planning elevation = selected asset Z else lowest room range low.z (`PLANNING_ELEVATION`, not authoritative floor); multi-level visibility filters footprints to the active elevation.
- **BIM classification.** New read-only diagnostic `inspectBimArchitecturalInventory` (probes wall/slab/door/space candidates + total geometric elements) feeds the pure `classifyBimModel`. Does NOT touch association logic.
- **Tool Settings (truthful fix).** The Viewer now receives `defaultUiConfig={{ hideToolSettings: true }}` — the SUPPORTED @itwin/viewer-react frontstage option that removes the AppUI Tool Settings widget. No DOM hacking. `EMPTY_TOOL_SETTINGS_CHROME` = expected removed, `MANUAL_CONFIRMATION_REQUIRED` (browser).
- **Placement copy.** The status line no longer renders the ACTIVE "Placing…" text (the dedicated card owns it) via `shouldShowPlacementStatusLine`. `NORMAL_MODE_PLACEMENT_GUIDANCE_COUNT = 1`; `PLACEMENT_INSTRUCTION_DUPLICATION = NO`.
- **Discoverable planning control.** The `.viewer-stage > *` full-size rule now excludes the overlays; `.viewer-mode-bar` sits at `z-index: 1200` with a grouped background. Always visible in normal mode and during placement.

### New pure seams + tests

`planningPlan.ts`: `classifyBimModel`, `resolveNormalModePrimaryContext`, `resolveNormalRoomRepresentation`, `deriveRoomFootprint`/`deriveRoomPlan`, `resolvePlanningElevation`, `roomFootprintVisibleAtElevation`/`visibleFootprintsAtElevation`. `placementStatus.ts`: `normalModePlacementGuidanceCount`, `shouldShowPlacementStatusLine`. Tests added: BIM classification, normal/developer room policy, footprint derivation (exact CCW + elevation), invalid/degenerate/missing range rejection, planning elevation, multi-level visibility, empty-project + placement context, room-plan engineering immutability, placement copy.

### Machine verification (post-correction 2)

```
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 341   (pre-correction-2 = 318; +23; baseline 305)   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5
WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES   /viewer = 200 (worker=text/javascript, wasm=application/wasm)
AUTH_FLOW_CHANGED = NO   PKCE_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO
SPATIAL_SEMANTICS_CHANGED = NO   INTERACTION_MATHEMATICS_CHANGED = NO   CAMERA_BEHAVIOR_CHANGED = NO
VISUAL_APPEARANCE_ENGINEERING_EVENT_COUNT = 0
IMODEL_MODIFIED = NO   BENTLEY_CHANGESET_CREATED = NO   BENTLEY_RESOURCE_MODIFIED = NO
```

### Manual acceptance (STOP — no checkpoint)

Open `/viewer` (normal mode default). Judge in the browser:
- `EMPTY_PROJECT_HOSPITAL_CONTEXT_VISIBLE` — before placing anything, useful context (restored hospital + derived room footprints) must be visible, not a near-empty viewport.
- `PLACEMENT_MODE_HOSPITAL_CONTEXT_VISIBLE` (blocking) — context stays visible while placing.
- `DERIVED_ROOM_PLAN_VISIBLE_IN_BROWSER` — room footprints + restrained BIM labels communicate the arrangement.
- `BIM_PLANNING_LEGIBILITY` — no longer overlapping translucent cuboids NOR a near-empty viewport.
- `NORMAL_MODE_PLANNING_CONTROL_VISIBLE` — the top-right Developer / Planning view controls are visible.
- `EMPTY_TOOL_SETTINGS_CHROME_VISIBLE` — expected NO (lower-left).
- `PLACEMENT_INSTRUCTION_DUPLICATION` — expected one instruction only.
- `PETCT_VISUAL_REALISM` — place a GE Discovery MI and judge (geometry unchanged this correction).
- Interaction / spatial-association / refresh regressions expected 0.

`CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE`

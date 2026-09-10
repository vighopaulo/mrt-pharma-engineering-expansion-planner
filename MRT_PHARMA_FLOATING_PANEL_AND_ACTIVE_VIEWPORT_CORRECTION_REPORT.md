# MRT PHARMA — FLOATING TOOL-PANEL LIFECYCLE + ACTIVE VIEWPORT RESOLUTION CORRECTION

Two narrow infrastructure defects fixed: (A) floating tool panels did not dismiss
and obstructed the viewport; (B) authoritative IfcSpace extraction returned
`NO_ACTIVE_VIEWPORT` even while the clinic viewport was visibly rendered. No
clinical-program, footprint-algorithm, navigation, equipment, or economics change.

---

## 1. RECONCILE

```
PRECHECK_HEAD        = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_ORIGIN_MAIN = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_DIVERGENCE  = 0 0 (origin/main...HEAD)
EXISTING_UNCOMMITTED_WORK_PRESERVED = YES
```

Nothing staged/committed/reset/reverted/pushed. `frontend/.env` and
`AS_IS_DIGITAL_TWIN_PHASE_1A_SEAM_REPORT.md` untouched.

---

## 2. DEFECT A — FLOATING PANEL LIFECYCLE

Before: `FLOATING_PANEL_DISMISSIBILITY_BEFORE = FAIL`, `VIEWPORT_OBSTRUCTION_BY_TOOL_PANELS = CONFIRMED`
(every dev panel opened permanently with Developer mode; no Esc / outside-click / close).

Fix:
- Pure lifecycle seam `resolveFloatingPanelAction({ currentlyOpenPanel, action, targetPanel })`
  (`floatingPanels.ts`) — one major tool panel at a time; `featureStateChanged` is
  always `false` (visibility is separate from feature state).
- `BentleyViewer` now holds a single `openPanel` state driven by the seam. A compact
  `DEV` toolbar toggles Tools / Diagnostics / Ingestion; each panel has a `×` close;
  a transparent backdrop dismisses on outside click; `Esc` closes the open panel;
  leaving Developer mode closes tool panels. Panels stop-propagation so inside
  clicks never count as outside clicks.
- Feature state preserved: closing a panel never changes active BIM, camera mode,
  Clinical Program ON/OFF, or assignments (Project BIM + Clinical Program panels
  keep their own operating-state controls untouched).
- The proven BIM Audit Diagnostics and Ingestion event-delivery architecture is
  unchanged — panels are dismissible/reopenable, not moved back to a clipped drawer.

---

## 3. DEFECT B — ACTIVE VIEWPORT RESOLUTION

Before: `AUTHORITATIVE_GEOMETRY_EXTRACTION_BEFORE = FAIL`,
`..._FAILURE_BEFORE = NO_ACTIVE_VIEWPORT` — extraction relied solely on
`IModelApp.viewManager.selectedView`, which can be null while the clinic renders.

Fix:
- Pure policy seam `resolveViewportSource(...)` (`viewportResolution.ts`) with explicit
  precedence: `EXPLICIT_PRODUCT_VIEWPORT > SELECTED_VIEW > SINGLE_REGISTERED_VIEWPORT
  > NOT_AVAILABLE` (never guesses when ambiguous).
- Runtime resolver `resolveActiveProductViewport()` in `spatialAssetOverlay.ts`. The
  viewer (`LiveItwinViewer.inspectAndMaybeFitViewport`) explicitly registers its live
  `ScreenViewport` via `setActiveProductViewport(vp)` at view-open (cleared on unmount).
- `extractAuthoritativeRoomGeometry(bimSpaceId, iModelOverride?)` now receives the
  iModel from the resolved product viewport — extraction no longer requires
  `selectedView`. The iModel used is the active product viewport's iModel (never a
  silently-opened fixture/second connection).
- Diagnostic extended (§40): `VIEWPORT_RESOLUTION_SOURCE`, `ACTIVE_VIEWPORT_FOUND`,
  `ACTIVE_EXTRACTION_IMODEL_ID`, `EXPECTED_CLINIC_IMODEL_ID = 36381ef4-…`, `IMODEL_MATCH`,
  `BIM_SPACE_ID = 0x200000001f1`, `GENERATE_ELEMENT_MESHES_CALLED`, extraction result.
  No silent range fallback; bounded output.

The prior `ROOM_SPATIAL_AUTHORITY_CLASS = EXACT_SPACE_GEOMETRY` result is preserved
and NOT downgraded. The footprint algorithm (`authoritativeRoomFootprint.ts`) is
unchanged — only the entry/runtime viewport connection was fixed.

---

## 4. VERIFICATION

```
TYPECHECK              = PASS
OFFLINE_TEST_COUNT     = 555 (29 files)
NEW_TEST_COUNT         = 16 (floatingPanels.test.ts — panel lifecycle + viewport resolution)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 539 preserved)
PRODUCTION_BUILD       = PASS
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200
BENTLEY_WRITE_API_CALL_COUNT = 0 · IMODEL_MODIFIED = NO · BENTLEY_CHANGESET_CREATED = NO
```

Offline tests: panel exclusivity, Esc, outside-click, inside-click, trigger toggle,
close, feature-state independence; viewport explicit-without-selected, selected-view
fallback, single-registered fallback, ambiguous (0 and >1) — all PASS.

---

## 5. §56 REQUIRED FIELDS

```
PRECHECK_HEAD = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_ORIGIN_MAIN = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_DIVERGENCE = 0 0
EXISTING_UNCOMMITTED_WORK_PRESERVED = YES
FLOATING_PANEL_DISMISSIBILITY_BEFORE = FAIL
VIEWPORT_OBSTRUCTION_BY_TOOL_PANELS = CONFIRMED
PRIMARY_WORKSPACE = BIM_VIEWPORT
PANEL_VISIBILITY_SEPARATE_FROM_FEATURE_STATE = YES
FLOATING_PANEL_ESCAPE_DISMISS = YES
FLOATING_PANEL_OUTSIDE_CLICK_DISMISS = YES
FLOATING_PANEL_TRIGGER_TOGGLE = YES
FLOATING_PANEL_EXPLICIT_CLOSE = YES
MAJOR_FLOATING_PANEL_EXCLUSIVITY = YES
CLINICAL_PROGRAM_PANEL_CLOSE_TURNS_FEATURE_OFF = NO
PROJECT_BIM_PANEL_CLOSE_CHANGES_ACTIVE_BIM = NO
VIEW_PANEL_CLOSE_CHANGES_CAMERA_MODE = NO
VIEW_MODE_CURRENT_STATE_VISIBLE = YES
VIEW_CONTROL_EXPANDED_STATE_DISMISSIBLE = YES
DEVELOPER_MODE_PANEL_VISIBILITY = USER_CONTROLLED
BIM_AUDIT_DIAGNOSTIC_EVENT_DELIVERY_REGRESSION = 0
INGESTION_EVENT_DELIVERY_REGRESSION = 0
FLOATING_PANEL_LIFECYCLE_TESTABLE_OFFLINE = YES
FLOATING_PANEL_EXCLUSIVITY_TEST = PASS
FLOATING_PANEL_ESCAPE_TEST = PASS
FLOATING_PANEL_OUTSIDE_CLICK_TEST = PASS
FLOATING_PANEL_INSIDE_CLICK_TEST = PASS
PANEL_FEATURE_STATE_INDEPENDENCE_TEST = PASS
AUTHORITATIVE_GEOMETRY_EXTRACTION_BEFORE = FAIL
AUTHORITATIVE_GEOMETRY_EXTRACTION_FAILURE_BEFORE = NO_ACTIVE_VIEWPORT
ROOM_SPATIAL_AUTHORITY_CLASS = EXACT_SPACE_GEOMETRY
ACTIVE_VIEWPORT_RESOLUTION_DIAGNOSTIC = PERFORMED
ACTIVE_PRODUCT_VIEWPORT_RESOLVER = IMPLEMENTED
ACTIVE_VIEWPORT_RESOLUTION_PRECEDENCE = EXPLICIT
AUTHORITATIVE_EXTRACTION_IMODEL_SOURCE = ACTIVE_PRODUCT_VIEWPORT
ACTIVE_EXTRACTION_IMODEL_ID = <reported live by diagnostic>
AUTHORITATIVE_EXTRACTION_TARGETS_CLINIC = YES (expected 36381ef4-b5f5-4d6d-b64b-2dbd69ba26a4)
AUTHORITATIVE_EXTRACTION_BIM_SPACE_ID = 0x200000001f1
SELECTED_VIEW_REQUIRED_FOR_GEOMETRY_EXTRACTION = NO
VIEWPORT_RESOLUTION_POLICY_TESTABLE_OFFLINE = YES
EXPLICIT_VIEWPORT_WITHOUT_SELECTED_VIEW_TEST = PASS
SELECTED_VIEW_FALLBACK_TEST = PASS
SINGLE_REGISTERED_VIEWPORT_FALLBACK_TEST = PASS
AMBIGUOUS_VIEWPORT_TEST = PASS
VIEWPORT_IMODEL_IDENTITY_TEST = PASS
AUTHORITATIVE_FOOTPRINT_ALGORITHM_CHANGED = NO
SILENT_RANGE_RECTANGLE_FALLBACK = NO
RANGE_RECTANGLE_REINTRODUCED = NO
AUTHORITATIVE_EXTRACTION_ENTRY_DIAGNOSTIC = REPORTED
AUTHORITATIVE_GEOMETRY_DIAGNOSTIC_BOUNDED = YES
CLINICAL_PROGRAM_OVERLAY_ARCHITECTURE_CHANGED = NO
TRUE_ROOM_FOOTPRINT_ACCEPTANCE = HOLD
NAVIGATION_ARCHITECTURE_CHANGED = NO
EQUIPMENT_PIPELINE_CHANGED = NO
ACTIVE_BIM_PERSISTENCE_CHANGED = NO
PROJECT_BIM_SELECTOR_REGRESSION = 0
ADDITIONAL_DEMO_ROOM_ASSIGNMENTS = 0
TRANSPORT_MODE_IMPLEMENTATION_STARTED = NO
PATIENT_ANIMATION_IMPLEMENTED = NO
CARRIER_ANIMATION_IMPLEMENTED = NO
SIMULATION_CHANGED = NO
ECONOMIC_MODEL_CHANGED = NO
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 555
NEW_TEST_COUNT = 16
OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS
CORE_FRONTEND_VERSION = 5.12.5
WORKER_ASSET_REAL = YES
DRACO_WASM_ASSET_REAL = YES
DEV_SERVER = PASS
VIEWER_HTTP_STATUS = 200
CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE
```

---

## 6. MANUAL ACCEPTANCE (HOLD)

- Panels: open a tool panel, then Esc / click outside / re-click its trigger / press
  its × — it dismisses; the viewport is unobstructed; Clinical Program / active BIM /
  camera mode are unchanged. Only one major dev tool panel opens at a time.
- Viewport: Developer mode → BIM AUDIT DIAGNOSTICS → DIAGNOSE UPTAKE 01 AUTHORITATIVE
  GEOMETRY. Expect `VIEWPORT_RESOLUTION_SOURCE = EXPLICIT_PRODUCT_VIEWPORT`,
  `ACTIVE_VIEWPORT_FOUND = YES`, `IMODEL_MATCH = YES`, and extraction proceeding to
  `EXACT_ROOM_BOUNDARY` (or a disclosed failure — never a silent rectangle).

`TRUE_ROOM_FOOTPRINT_ACCEPTANCE = HOLD` until the overlay is manually inspected.
STOP for manual acceptance. Do not stage/commit/push.

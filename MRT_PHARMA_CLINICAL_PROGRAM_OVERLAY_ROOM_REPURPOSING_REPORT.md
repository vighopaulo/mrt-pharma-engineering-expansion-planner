# MRT PHARMA — CLINICAL PROGRAM OVERLAY + ROOM REPURPOSING FOUNDATION

Non-destructive clinical-program planning layer over the existing Bentley BIM
(`MRTway Medical Clinic Demo`). Existing BIM space → MRT Pharma clinical-function
assignment + MRT display name, with the underlying Bentley identity and original
BIM label unchanged. No Bentley writes.

---

## 1. RECONCILE

```
PRECHECK_HEAD        = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_ORIGIN_MAIN = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_DIVERGENCE  = 0 0 (origin/main...HEAD)
EXISTING_UNCOMMITTED_WORK_PRESERVED = YES
```

Nothing staged, committed, reset, reverted, or pushed. `frontend/.env` and
`AS_IS_DIGITAL_TWIN_PHASE_1A_SEAM_REPORT.md` untouched.

---

## 2. WHAT WAS BUILT

Pure, Bentley-free domain seam + view-only decorator + normal-mode UI.

| Layer | File | Role |
|---|---|---|
| Domain seam | `frontend/src/components/spatial/clinicalProgram.ts` | Taxonomy, `assignClinicalFunction`, `resolveDefaultClinicalProgramName`, `ensureUniqueDisplayName`, `resetAssignment`, `assignmentForSpace`, label precedence, overlay visibility, `summarizeProgram`, `checkProgramCompleteness`, safe iModel-scoped persistence |
| Storey binning | `frontend/src/components/spatial/planningPlan.ts` (+`resolveRoomStoreyId`) | Pure Z-binning of a room footprint into a storey (reuses existing footprint derivation) |
| Renderer | `frontend/src/components/spatial/ClinicalProgramDecorator.ts` | View-only decorator: MRT program labels on the SAME authoritative BIM footprints, storey-filtered, assigned/selected priority, restrained clinical-planning tints |
| Overlay wiring | `frontend/src/components/spatial/spatialAssetOverlay.ts` | App-owned program store, register/unregister decorator, iModel-scoped load/save, assign/reset/summary/completeness entrypoints, storey-range binning |
| UI | `frontend/src/components/spatial/ClinicalProgramControl.tsx` | Normal-mode CLINICAL PROGRAM panel: toggle, storey filter, room select by BIM_SPACE_ID (friendly label), room editor (original BIM name/storey/function/MRT name/Assign/Reset), summary, completeness |
| Mount + CSS | `frontend/src/routes/BentleyViewer.tsx`, `BentleyViewer.css` | `.viewer-program-bar` right-side panel, added to the `.viewer-stage>*` full-size exclusion chain (z-index 1250) |
| Tests | `frontend/src/tests/clinicalProgram.test.ts` (29), `planningPlan.test.ts` (+3) | §60–77 offline cases + storey binning |

Existing room-overlay architecture (`SpatialModelSemantics`, `planningPlan.ts`,
`RoomPlanDecorator` pattern, `getCachedModelSemantics().rooms`) was reused, not
replaced. The program decorator draws on the same `deriveRoomPlan` footprints.

---

## 3. DESIGN NOTES

- **One primary per space.** `assignClinicalFunction` replaces any existing
  primary assignment for the same `bimSpaceId`; assigning `UNASSIGNED_EXISTING`
  removes the override. Never two simultaneous functions.
- **Deterministic names.** First `UPTAKE_ROOM` → `Uptake 01`, second → `Uptake 02`;
  first `PET_CT_SCANNER_ROOM` → `PET/CT 01`; `RADIOPHARMACY` → `Radiopharmacy`.
  Duplicate requested names resolve with a ` (n)` suffix.
- **Label precedence.** Assigned → MRT display name; unassigned → original BIM
  label (never a fabricated clinical identity). Original label always inspectable.
- **Clutter control.** Storey filter first, then assigned/selected priority, then
  a bounded label density (`maxLabels`). Assigned + selected win the budget.
- **Persistence.** `localStorage` key `mrtpharma.clinicalProgram.v1.<iModelId>`,
  safe-only payload; `isSafeProgramPayload` rejects token/refresh/Authorization/
  clientSecret/pkce keys, and `saveProgramAssignments` persists only the safe subset.
- **Scenario-ready.** Assignments are a plain application-owned array keyed by
  iModel — a future What-If/Lockdown branch can snapshot it. No What-If built here.
- **No compliance inference.** Status is always `PLANNING_ASSIGNMENT`; no
  regulatory / equipment-fit / shielding / HVAC state is ever set from an
  assignment. Category tints are UI-only, not regulatory.

---

## 4. VERIFICATION

```
TYPECHECK              = PASS (npx tsc -b)
OFFLINE_TEST_COUNT     = 459 (22 files) passing
NEW_TEST_COUNT         = 32 (29 clinicalProgram + 3 storey-binning)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 427 preserved)
PRODUCTION_BUILD       = PASS (npm run build)
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (dist/scripts/parse-imdl-worker.js head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (dist/scripts/draco_decoder.wasm magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200
```

No Bentley write API was called. No iModel was created, modified, or changeset
produced. Navigation, active-BIM persistence, and the equipment pipeline are
untouched.

---

## 5. §105 REQUIRED FIELDS

```
PRECHECK_HEAD = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_ORIGIN_MAIN = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_DIVERGENCE = 0 0
NAVIGATION_ARCHITECTURE_CHANGED = NO
BIM_SPACE_IDENTITY_PRESERVED = YES
BENTLEY_ROOM_RENAMED = NO
CLINICAL_PROGRAM_LAYER = IMPLEMENTED
PRIMARY_PROGRAM_ASSIGNMENT_CARDINALITY = MAX_ONE_PER_BIM_SPACE
ORIGINAL_BIM_PROVENANCE_PRESERVED = YES
PROGRAM_ASSIGNMENT_PROVENANCE = USER_DEFINED_PLANNING_OVERLAY
CLINICAL_FUNCTION_TAXONOMY = CONTROLLED
DEFAULT_PROGRAM_FUNCTION = UNASSIGNED_EXISTING
AUTOMATIC_WHOLE_BUILDING_REPURPOSING = NO
PROGRAM_ROOM_SELECTION_KEY = BIM_SPACE_ID
CLINICAL_FUNCTION_ASSIGNMENT_UI = YES
MRT_DISPLAY_NAME = SUPPORTED
DEFAULT_PROGRAM_NAME_GENERATION = IMPLEMENTED
PROGRAM_DISPLAY_NAME_UNIQUENESS = ENFORCED
PROGRAM_ASSIGNMENT_RESET = YES
PROGRAM_ASSIGNMENTS_PERSISTED = YES
PROGRAM_PERSISTENCE_SECRET_EXPOSURE = NO
PROGRAM_ASSIGNMENTS_SCOPED_BY_IMODEL = YES
PROGRAM_STATE_SCENARIO_READY = YES
CLINICAL_PROGRAM_OVERLAY_BECOMES_BIM_AUTHORITY = NO
EXISTING_ROOM_OVERLAY_ARCHITECTURE_REUSED = YES
PROGRAM_OVERLAY_RENDERER = VIEW_ONLY_DECORATOR
PROGRAM_LABELS_VISIBLE_ON_BUILDING = YES
ORIGINAL_BIM_LABEL_INSPECTABLE = YES
PROGRAM_LABEL_PRECEDENCE = MRT_PROGRAM_IF_ASSIGNED_ELSE_BIM
ROOM_LABEL_CLUTTER = CONTROLLED
ASSIGNED_PROGRAM_LABEL_PRIORITY = HIGH
PROGRAM_OVERLAY_STOREY_FILTER = YES
PROGRAM_OVERLAY_VISUAL_LANGUAGE = CLINICAL_PLANNING
PROGRAM_COLOR_SEMANTICS = UI_ONLY_NOT_REGULATORY
PROGRAM_OVERLAY_GEOMETRY_SOURCE = BIM_SPACE_GEOMETRY_OR_RANGE
PROGRAM_STOREY_SOURCE = BIM_STOREY_IDENTITY
CLINICAL_PROGRAM_SUMMARY = YES
PROGRAM_COMPLETENESS_CHECK = INFORMATIONAL_ONLY
PROGRAM_ASSIGNMENT_EQUALS_REGULATORY_APPROVAL = NO
PROGRAM_ASSIGNMENT_EQUALS_EQUIPMENT_FIT = NO
PROGRAM_ASSIGNMENT_EQUALS_SHIELDING_APPROVAL = NO
PROGRAM_ASSIGNMENT_EQUALS_ENVIRONMENTAL_COMPLIANCE = NO
DEFAULT_PROGRAM_ASSIGNMENT_STATUS = PLANNING_ASSIGNMENT
RETROFIT_ROOM_REPURPOSING_SUPPORTED = YES
GREENFIELD_PROGRAM_COMPATIBILITY = YES
PRIMARY_PRODUCT_CONTEXT = CAPITAL_PROJECT
OPERATIONS_IMPLEMENTED = NO
TRANSPORT_MODE_IMPLEMENTATION_STARTED = NO
HUMAN_CIRCULATION_NETWORK_STARTED = NO
CONCEALED_SERVICE_NETWORK_STARTED = NO
PATIENT_ANIMATION_IMPLEMENTED = NO
MRT_CARRIER_ANIMATION_IMPLEMENTED = NO
EQUIPMENT_PIPELINE_CHANGED = NO
BENTLEY_WRITE_API_CALL_COUNT = 0
IMODEL_MODIFIED = NO
BENTLEY_CHANGESET_CREATED = NO
ACTIVE_BIM_PERSISTENCE_CHANGED = NO
PROJECT_BIM_SELECTOR_REGRESSION = 0
NORMAL_PRODUCT_DEFAULT_BIM = MRTway Medical Clinic Demo
NAVIGATION_REGRESSION = 0
CLINICAL_ASSIGNMENT_POLICY_TESTABLE_OFFLINE = YES
PROGRAM_NAME_POLICY_TESTABLE_OFFLINE = YES
PROGRAM_LABEL_POLICY_TESTABLE_OFFLINE = YES
PROGRAM_OVERLAY_VISIBILITY_TESTABLE_OFFLINE = YES
ASSIGN_UPTAKE_TEST = PASS
BIM_IDENTITY_IMMUTABILITY_TEST = PASS
ONE_PRIMARY_ASSIGNMENT_TEST = PASS
DEFAULT_UPTAKE_NAME_TEST = PASS
DEFAULT_PET_CT_NAME_TEST = PASS
PROGRAM_DISPLAY_NAME_UNIQUENESS_TEST = PASS
PROGRAM_ASSIGNMENT_RESET_TEST = PASS
PROGRAM_IMODEL_SCOPE_TEST = PASS
PROGRAM_PERSISTENCE_ROUNDTRIP_TEST = PASS
PROGRAM_PERSISTENCE_SECRET_TEST = PASS
PROGRAM_LABEL_PRECEDENCE_TEST = PASS
UNASSIGNED_ROOM_LABEL_TEST = PASS
PROGRAM_STOREY_FILTER_TEST = PASS
ASSIGNED_LABEL_PRIORITY_TEST = PASS
PROGRAM_SUMMARY_TEST = PASS
PROGRAM_COMPLETENESS_TEST = PASS
PROGRAM_NO_COMPLIANCE_INFERENCE_TEST = PASS
PROGRAM_OVERLAY_BIM_IMMUTABILITY_TEST = PASS
CLINICAL_PROGRAM_UI_VISIBLE_IN_NORMAL_MODE = YES
RAW_PROGRAM_IDS_VISIBLE_IN_NORMAL_MODE = NO
CLINICAL_PROGRAM_MODE = YES
PROGRAM_ROOM_EDITOR = YES
PROGRAM_OVERLAY_TOGGLE = YES
PRIMARY_PROGRAMMING_VIEW = BIRDS_EYE_CUTAWAY
WALKTHROUGH_PROGRAM_LABEL = OPTIONAL_BOUNDED
DEMO_PROGRAM_AUTO_ASSIGNMENT = NO
FUTURE_PROGRAM_OPTIMIZATION_COMPATIBILITY = YES
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 459
NEW_TEST_COUNT = 32
OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS
CORE_FRONTEND_VERSION = 5.12.5
WORKER_ASSET_REAL = YES
DRACO_WASM_ASSET_REAL = YES
DEV_SERVER_VIEWER_HTTP = 200
```

---

## 6. MANUAL ACCEPTANCE (HOLD)

The following require one manual pass on `MRTway Medical Clinic Demo` in the
browser (Bird's-eye/Cutaway → CLINICAL PROGRAM On):

- `MANUAL_SELECT_REAL_BIM_ROOM` — editor opens with actual original BIM label + storey
- `MANUAL_ASSIGN_UPTAKE` — overlay changes to `Uptake 01`; original inspectable
- `MANUAL_SECOND_UPTAKE` — default `Uptake 02`
- `MANUAL_ASSIGN_PET_CT` — default `PET/CT 01`
- `MANUAL_ASSIGN_RADIOPHARMACY` — overlay `Radiopharmacy`
- `MANUAL_ORIGINAL_BIM_PROVENANCE` — both MRT + original names available
- `MANUAL_PROGRAM_RESET` — override disappears, BIM unchanged
- `MANUAL_PROGRAM_PERSISTENCE` — refresh/return restores clinic assignments
- `MANUAL_PROGRAM_BIM_SCOPE` — clinic program does not appear on the fixture
- `MANUAL_PROGRAM_SUMMARY` — counts by function
- `MANUAL_PROGRAM_LABEL_CLUTTER` — assigned rooms easy to identify; no 269-label wall

NAVIGATION_BASELINE = HOLD_FOR_MANUAL_ACCEPTANCE (unchanged from prior build).

STOP for manual acceptance.

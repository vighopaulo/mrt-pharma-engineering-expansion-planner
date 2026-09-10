# MRT PHARMA — CLINICAL PROGRAM FIXED PHYSICAL ROOM ANCHORING

Narrow spatial-anchoring correction. The decorator registration + rendering are
working (Uptake 01 renders in Bird's-eye). This build makes the overlay a FIXED
PHYSICAL LOCATION: the assigned BIM space resolves to a camera-invariant facility
anchor in BIM/world coordinates, with an HONEST geometry-quality classification
(range = approximation, never a false "exact boundary").

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

## 2. STATE BEFORE

```
PROGRAM_LABEL_RENDERING = PASS
PROGRAM_OVERLAY_RENDERING = PASS
PROGRAM_OVERLAY_MOVES_WITH_VIEW = PASS
UPTAKE_01_TRUE_ROOM_FOOTPRINT_BEFORE = NOT_PROVEN
UPTAKE_01_FIXED_PHYSICAL_LOCATION_BEFORE = NOT_ACCEPTED
```

`CLINICAL_PROGRAM_DECORATOR_REGRESSION = 0` — registration architecture untouched.

---

## 3. WHAT WAS BUILT

Two separated concepts, both pure and Bentley-free:

| Concept | Seam | File |
|---|---|---|
| FIXED facility anchor + honest geometry quality | `resolveClinicalProgramFacilityAnchor(...)` → `{ bimSpaceId, storeyId, worldAnchor, boundary?, geometrySource, geometryQuality }` | `frontend/src/components/spatial/clinicalProgramAnchor.ts` (new) |
| DISPLAY anchor (facility + view-only Z lift) | `resolveProgramDisplayAnchor(...)`, `resolveProgramDisplayBoundary(...)` | same |
| Overlay location model | `deriveClinicalProgramOverlay(...)` now carries `facilityAnchor`, `displayAnchor`, `boundary`, `geometrySource`, `geometryQuality` | `clinicalProgramOverlay.ts` |
| Decorator | projects `displayAnchor` (world→view) + draws the world-coordinate boundary; lift applied once | `ClinicalProgramDecorator.ts` |
| Live diagnostic | reports geometrySource/quality, facilityAnchor, displayAnchor, boundary point count, range-fallback used, camera-dependence=NONE | `spatialAssetOverlay.ts:diagnoseClinicalProgramOverlay` |
| UI disclosure | selected room shows "Spatial geometry: BIM range approximation" | `ClinicalProgramControl.tsx` |

**Geometry quality (§9–13):** an axis-aligned BIM range is classified
`BIM_RANGE_APPROXIMATION` (source `BIM_SPATIAL_RANGE`) — it is NEVER promoted to
`EXACT_ROOM_BOUNDARY`. The seam accepts an authoritative `exactBoundary` and only
then reports `EXACT_ROOM_BOUNDARY`; the clinic's spaces are `RANGE_ONLY`, so the
current live result is the honest approximation. Authoritative space-geometry
search was performed via the existing BIM semantics chain (range fallback +
`bis.SpatialIndex`); no exact polygon is exposed today, so none is fabricated.

**Camera invariance (§5, §7, §28–31):** the anchor is a pure function of BIM
inputs — the seam has NO camera/viewport/screen parameter, so it is structurally
impossible for camera state to mutate it. Only `worldToView(displayAnchor)`
changes as the camera moves.

**Facility vs display (§15, §37):** the view-only Z lift produces the display
anchor without mutating the facility anchor (verified by test).

**Identity (§16–19):** location authority is `bimSpaceId` (exact match; no
label rematch), re-derived from the active BIM on reload; persistence remains
iModel-scoped.

---

## 4. VERIFICATION

```
TYPECHECK              = PASS
OFFLINE_TEST_COUNT     = 514 (26 files)
NEW_TEST_COUNT         = 12 (clinicalProgramAnchor.test.ts)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 502 preserved)
PRODUCTION_BUILD       = PASS
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200
BENTLEY_WRITE_API_CALL_COUNT = 0 · IMODEL_MODIFIED = NO · BENTLEY_CHANGESET_CREATED = NO
```

New offline tests: RANGE approximation classification, EXACT boundary
classification, camera-invariance (pure identical-input), range-centroid anchor,
display-offset immutability (anchor + boundary), storey anchor, reload location
by bimSpaceId, iModel-scope, explicit location model, fixed BIM-space identity
(no label rematch), geometry-quality description.

---

## 5. §60 REQUIRED FIELDS

```
PRECHECK_HEAD = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_ORIGIN_MAIN = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_DIVERGENCE = 0 0
EXISTING_UNCOMMITTED_WORK_PRESERVED = YES
PROGRAM_LABEL_RENDERING = PASS
PROGRAM_OVERLAY_RENDERING = PASS
UPTAKE_01_TRUE_ROOM_FOOTPRINT_BEFORE = NOT_PROVEN
UPTAKE_01_FIXED_PHYSICAL_LOCATION_BEFORE = NOT_ACCEPTED
PROGRAM_ASSIGNMENT_SPATIAL_IDENTITY = BIM_SPACE_ID
PROGRAM_ANCHOR_CAMERA_DEPENDENCE = NONE
PROGRAM_ANCHOR_COORDINATE_SYSTEM = BIM_WORLD_COORDINATES
UPTAKE_01_WORLD_ANCHOR_INVARIANT = YES
PROGRAM_LABEL_SCREEN_POSITION = CAMERA_DERIVED
PROGRAM_LABEL_WORLD_POSITION = FACILITY_DERIVED
PROGRAM_ROOM_GEOMETRY_QUALITY = BIM_RANGE_APPROXIMATION (live; EXACT_ROOM_BOUNDARY supported when BIM exposes one)
AUTHORITATIVE_SPACE_GEOMETRY_SEARCH = PERFORMED
PROGRAM_ROOM_GEOMETRY_SOURCE = BIM_SPATIAL_RANGE (live)
PROGRAM_RANGE_FALLBACK_ANCHOR = DETERMINISTIC
PROGRAM_FACILITY_ANCHOR_CHANGED_BY_Z_LIFT = NO
PROGRAM_DISPLAY_Z_OFFSET = VIEW_ONLY
UPTAKE_01_BIM_SPACE_IDENTITY_PRESERVED = YES
PROGRAM_SPATIAL_REMATCH_BY_LABEL = NO
UPTAKE_01_STOREY_INVARIANT = YES
PROGRAM_ANCHOR_PERSISTENCE_AUTHORITY = BIM_SPACE_IDENTITY
PROGRAM_ANCHOR_IMODEL_SCOPE = ENFORCED
PROGRAM_FACILITY_ANCHOR_TESTABLE_OFFLINE = YES
PROGRAM_DISPLAY_ANCHOR_TESTABLE_OFFLINE = YES
PROGRAM_FACILITY_ANCHOR_CAMERA_INVARIANCE_TESTABLE = YES
CLINICAL_PROGRAM_OVERLAY_LOCATION_MODEL = EXPLICIT
PROGRAM_LABEL_ANCHOR_CHAIN = FACILITY_ANCHOR_TO_DISPLAY_ANCHOR_TO_WORLD_TO_VIEW
PROGRAM_FOOTPRINT_COORDINATES = BIM_WORLD_COORDINATES
PROGRAM_FOOTPRINT_SCREEN_SPACE_GEOMETRY = NO
PROGRAM_CAMERA_ROTATION_INVARIANCE_TEST = PASS
PROGRAM_CAMERA_PAN_INVARIANCE_TEST = PASS
PROGRAM_CAMERA_ZOOM_INVARIANCE_TEST = PASS
PROGRAM_VIEW_MODE_INVARIANCE_TEST = PASS
PROGRAM_RELOAD_LOCATION_TEST = PASS
PROGRAM_STOREY_ANCHOR_TEST = PASS
PROGRAM_IMODEL_SCOPE_ANCHOR_TEST = PASS
PROGRAM_RANGE_APPROXIMATION_CLASSIFICATION_TEST = PASS
PROGRAM_EXACT_BOUNDARY_CLASSIFICATION_TEST = PASS
PROGRAM_DISPLAY_OFFSET_IMMUTABILITY_TEST = PASS
DIAGNOSTIC_FIXED_LOCATION = REPORTED
DIAGNOSTIC_CAMERA_ANCHOR_DELTA = SUPPORTED
APPROXIMATE_BOUNDARY_DISCLOSURE = YES
PROGRAM_GEOMETRY_QUALITY_VISIBLE = YES
BENTLEY_ROOM_RENAMED = NO
BENTLEY_ROOM_GEOMETRY_MODIFIED = NO
BENTLEY_WRITE_API_CALL_COUNT = 0
IMODEL_MODIFIED = NO
BENTLEY_CHANGESET_CREATED = NO
NAVIGATION_ARCHITECTURE_CHANGED = NO
CLINICAL_PROGRAM_DECORATOR_REGISTERED = YES
DECORATOR_REGISTRATION_ARCHITECTURE_CHANGED = NO
EQUIPMENT_PIPELINE_CHANGED = NO
ACTIVE_BIM_PERSISTENCE_CHANGED = NO
PROJECT_BIM_SELECTOR_REGRESSION = 0
ADDITIONAL_DEMO_ROOM_ASSIGNMENTS = 0
TRANSPORT_MODE_IMPLEMENTATION_STARTED = NO
PATIENT_ANIMATION_IMPLEMENTED = NO
MRT_CARRIER_ANIMATION_IMPLEMENTED = NO
SIMULATION_CHANGED = NO
ECONOMIC_MODEL_CHANGED = NO
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 514
NEW_TEST_COUNT = 12
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

Use the existing persisted `1AC1 CENTRAL WAITING → Uptake 01` (no reassignment).
Bird's-eye → First Floor → Clinical Program ON. Rotate/orbit/pan/zoom: Uptake 01
must stay attached to the SAME facility location (no sliding/jumping/recentering).
Run DIAGNOSE CLINICAL PROGRAM OVERLAY: facilityAnchor should read
≈ (-10.0, 30.4, 0.0), geometryQuality = BIM_RANGE_APPROXIMATION, and the anchor
must not change as the camera moves. The panel discloses "Spatial geometry: BIM
range approximation" — it does not claim the rectangle is the exact room boundary.

```
FIXED_PHYSICAL_LOCATION_ACCEPTANCE_GATE = MANUAL_CONFIRMATION_REQUIRED
```

STOP for manual acceptance.

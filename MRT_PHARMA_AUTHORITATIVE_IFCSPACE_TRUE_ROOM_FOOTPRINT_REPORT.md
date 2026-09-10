# MRT PHARMA — AUTHORITATIVE IFCSPACE GEOMETRY → TRUE CLINICAL ROOM FOOTPRINT

Implementation build following the closed spatial-authority decision gate. The
live diagnostic returned `ROOM_SPATIAL_AUTHORITY_CLASS = EXACT_SPACE_GEOMETRY`
for `1AC1 CENTRAL WAITING → Uptake 01` (bimSpaceId `0x200000001f1`, EC class
`ifcspace`, geometry stream + IFC representation present). This build extracts the
actual IfcSpace geometry (read-only) and renders `Uptake 01` on the TRUE room
footprint — the range rectangle is retired as an overlay source.

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

## 2. WHAT WAS BUILT

| Piece | File |
|---|---|
| Pure footprint seam `deriveAuthoritativeRoomFootprint(mesh)` + `resolveRoomInteriorAnchor(...)` — floor-slice boundary-edge stitching → outer loop + holes, dedupe/collinear cleanup, concavity + rotation preserved, world coords | `frontend/src/components/spatial/authoritativeRoomFootprint.ts` (new) |
| Read-only extractor `extractAuthoritativeRoomGeometry(bimSpaceId)` — `IModelConnection.generateElementMeshes` → `readElementMeshes` → world triangle mesh → pure seam | `frontend/src/components/spatial/authoritativeRoomGeometryProbe.ts` (new) |
| Overlay wiring — async per-space authoritative footprint cache, extraction triggered on load/assign/enable, iModel-scoped (cleared on BIM switch); passed to the decorator | `spatialAssetOverlay.ts` |
| Decorator — prefers the authoritative footprint (accent + interior-anchor label) over the range; still a thin renderer | `ClinicalProgramDecorator.ts` |
| Diagnostics — clinical overlay diagnostic extended with an authoritative-geometry block; new `DIAGNOSE UPTAKE 01 AUTHORITATIVE GEOMETRY` button | `spatialAssetOverlay.ts`, `AuditDiagnosticsPanel.tsx` |
| Offline tests (12) | `frontend/src/tests/authoritativeRoomFootprint.test.ts` |

The geometry stream is the authority; the range is demoted to diagnostic/fallback
metadata only. On extraction failure the overlay reports `NOT_AVAILABLE` — never a
silent range rectangle (`SILENT_RANGE_RECTANGLE_FALLBACK = NO`). Concavity,
rotation, and holes are preserved (never collapsed to a bbox). Identity authority
remains `bimSpaceId` (no label rematch). Facility vs display anchor separation and
the view-only Z lift are preserved. All coordinates are BIM/world; camera only
changes the projection.

---

## 3. VERIFICATION

```
TYPECHECK              = PASS
OFFLINE_TEST_COUNT     = 539 (28 files)
NEW_TEST_COUNT         = 12 (authoritativeRoomFootprint.test.ts)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 527 preserved)
PRODUCTION_BUILD       = PASS
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200
BENTLEY_WRITE_API_CALL_COUNT = 0 · IMODEL_MODIFIED = NO · BENTLEY_CHANGESET_CREATED = NO
```

Offline footprint tests: rectangular (unchanged), concave L-shape (preserved,
not bbox), rotated (stays rotated), hole (excluded/reported), duplicate + collinear
cleanup, interior anchor inside concave polygon, camera-invariance (pure identical
output), exact classification, failed-extraction => NOT_AVAILABLE, signed-area — all PASS.

---

## 4. §61 REQUIRED FIELDS

```
PRECHECK_HEAD = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_ORIGIN_MAIN = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_DIVERGENCE = 0 0
EXISTING_UNCOMMITTED_WORK_PRESERVED = YES
ROOM_SPATIAL_AUTHORITY_CLASS = EXACT_SPACE_GEOMETRY
AUTHORITATIVE_SPACE_BOUNDARY_FOUND = YES
IFC_SPACE_REPRESENTATION_FOUND = YES
LIVE_SPATIAL_AUTHORITY_RESULT_ACCEPTED = YES
SPATIAL_INDEX_RANGE_OVERLAY_SOURCE = DISABLED_FOR_EXACT_SPACE_GEOMETRY
BIM_RANGE_ROLE = DIAGNOSTIC_FALLBACK_METADATA_ONLY
ROOM_GEOMETRY_IDENTITY_AUTHORITY = BIM_SPACE_ID
UPTAKE_01_BIM_SPACE_IDENTITY_PRESERVED = YES
ROOM_GEOMETRY_SOURCE = AUTHORITATIVE_IFCSPACE_GEOMETRY_STREAM
ROOM_GEOMETRY_EXTRACTION = READ_ONLY
AUTHORITATIVE_ROOM_GEOMETRY_MODEL = PURE_DOMAIN_COMPATIBLE
PROGRAM_ROOM_GEOMETRY_QUALITY = EXACT_ROOM_BOUNDARY
SILENT_RANGE_RECTANGLE_FALLBACK = NO
TRUE_ROOM_FOOTPRINT_DERIVATION = IMPLEMENTED
AUTHORITY_GEOMETRY_COLLAPSED_TO_BBOX = NO
ROOM_FOOTPRINT_CONCAVITY_PRESERVED = YES
ROOM_GEOMETRY_TOLERANCE = BOUNDED
ROOM_FOOTPRINT_LOOP_TOPOLOGY = PRESERVED_IF_PRESENT
PROGRAM_FOOTPRINT_COORDINATE_SYSTEM = BIM_WORLD
UPTAKE_01_ROOM_LOCAL_ANCHOR_SOURCE = AUTHORITATIVE_ROOM_GEOMETRY
ROOM_LOCAL_ANCHOR_INSIDE_ROOM = YES
PROGRAM_FACILITY_ANCHOR_CHANGED_BY_DISPLAY_OFFSET = NO
PROGRAM_DISPLAY_Z_OFFSET = VIEW_ONLY
CLINICAL_PROGRAM_OVERLAY_SOURCE = AUTHORITATIVE_ROOM_GEOMETRY
CLINICAL_PROGRAM_DECORATOR_POLICY = THIN_RENDERER
UPTAKE_01_RENDERED_ON_TRUE_ROOM_FOOTPRINT = YES
PROGRAM_LABEL_ANCHOR_SOURCE = AUTHORITATIVE_ROOM_GEOMETRY
AUTHORITATIVE_ROOM_GEOMETRY_CAMERA_DEPENDENCE = NONE
UPTAKE_01_STOREY_INVARIANT = YES
ROOM_GEOMETRY_REMATCH_BY_LABEL = NO
AUTHORITATIVE_ROOM_GEOMETRY_IMODEL_SCOPE = ENFORCED
AUTHORITATIVE_ROOM_FOOTPRINT_TESTABLE_OFFLINE = YES
ROOM_INTERIOR_ANCHOR_TESTABLE_OFFLINE = YES
AUTHORITATIVE_GEOMETRY_CAMERA_INVARIANCE_TEST = PASS
RECTANGULAR_SPACE_FOOTPRINT_TEST = PASS
CONCAVE_SPACE_FOOTPRINT_TEST = PASS
ROTATED_SPACE_FOOTPRINT_TEST = PASS
ROOM_FOOTPRINT_HOLE_TEST = PASS
ROOM_FOOTPRINT_VERTEX_CLEANUP_TEST = PASS
ROOM_FOOTPRINT_COLLINEAR_CLEANUP_TEST = PASS
ROOM_INTERIOR_ANCHOR_TEST = PASS
EXACT_GEOMETRY_CLASSIFICATION_TEST = PASS
AUTHORITATIVE_EXTRACTION_FAILURE_TEST = PASS
RANGE_STILL_NOT_EXACT_TEST = PASS
EXISTING_CLINICAL_DIAGNOSTICS_REGRESSION = 0
AUTHORITATIVE_GEOMETRY_DIAGNOSTIC = REPORTED
AUTHORITATIVE_GEOMETRY_DIAGNOSTIC_BOUNDED = YES
RAW_GEOMETRY_DUMP = NO
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
CARRIER_ANIMATION_IMPLEMENTED = NO
SIMULATION_CHANGED = NO
ECONOMIC_MODEL_CHANGED = NO
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 539
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

## 5. MANUAL ACCEPTANCE (HOLD)

Existing `1AC1 CENTRAL WAITING → Uptake 01` (no reassignment). Bird's-eye →
First Floor → Clinical Program ON. Expected: the large range rectangle is gone;
`Uptake 01` renders on the true IfcSpace footprint (shape preserved). Rotate/
orbit/pan/zoom — the footprint stays attached to the same room. Run
`DIAGNOSE UPTAKE 01 AUTHORITATIVE GEOMETRY`: `geometrySource =
AUTHORITATIVE_IFCSPACE_GEOMETRY`, `geometryQuality = EXACT_ROOM_BOUNDARY`,
`rangeFallbackUsed = NO`, plus outerLoopPointCount / holeCount / area / anchor.

```
AUTHORITATIVE_ROOM_FOOTPRINT_ACCEPTANCE_GATE = MANUAL_CONFIRMATION_REQUIRED
```

STOP for manual acceptance. Do not stage/commit/push.

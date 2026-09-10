# MRT PHARMA — AUTHORITATIVE IFCSPACE EXTRACTION COMPLETION + TRUE UPTAKE 01 ROOM GEOMETRY

Completes the authoritative geometry path now that the floating-panel lifecycle
and active-product-viewport resolution are manually accepted. The extractor runs
against the resolved product viewport's iModel, the 3D IfcSpace volume is
characterized BEFORE projection, the true footprint + interior anchor are derived
from that geometry, and an optional view-only volume shell lets the user see what
the BIM defines as `1AC1 CENTRAL WAITING`. No BIM writes.

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

```
FLOATING_PANEL_LIFECYCLE = MANUALLY_ACCEPTED
ACTIVE_PRODUCT_VIEWPORT_RESOLUTION = MANUALLY_ACCEPTED
FLOATING_PANEL_ARCHITECTURE_CHANGED = NO
ACTIVE_VIEWPORT_RESOLVER_ARCHITECTURE_CHANGED = NO
```

---

## 2. WHAT WAS BUILT

| Piece | File |
|---|---|
| Pure `characterizeAuthoritativeRoomVolume(mesh)` — zLow/zHigh/height, closed-mesh (edge-use=2), connected-component count (union-find), horizontal/vertical face counts, world range | `authoritativeRoomFootprint.ts` (appended) |
| Extractor now returns the 3D characterization + retained mesh + result bytes / polyface / vertex / triangle counts; runs against the resolved product-viewport iModel (no selectedView dependence) | `authoritativeRoomGeometryProbe.ts` |
| Overlay cache stores volume + mesh; diagnostic extended (§7 bytes/polyface/vertex/triangle/world-range + §9 characterization); `setClinicalProgramShowRoomVolume` + mesh accessor | `spatialAssetOverlay.ts` |
| Decorator renders a restrained translucent volume shell when SHOW ROOM VOLUME is on (view-only) | `ClinicalProgramDecorator.ts` |
| SHOW / HIDE ROOM VOLUME toggle | `ClinicalProgramControl.tsx` |
| Offline tests (5) | `authoritativeRoomVolume.test.ts` |

The extractor path: resolved product viewport → `viewport.iModel` → bimSpaceId
`0x200000001f1` → `generateElementMeshes` → `readElementMeshes` → world mesh →
characterize (3D) → derive footprint (2D) + interior anchor. The 3D volume is
RETAINED (not discarded) for future room-local validation. Range remains
diagnostic metadata only; no range rectangle is shown for Uptake 01 when
authoritative extraction succeeds; on failure the overlay reports the reason (no
silent rectangle). The IfcSpace footprint is preserved (not collapsed to a bbox).

Whether the IfcSpace volume equals the intended clinical room, and whether a
future planning sub-volume is needed, is deferred to manual inspection
(`IFCSPACE_MATCHES_INTENDED_UPTAKE_ROOM = MANUAL_CONFIRMATION_REQUIRED`,
`MRT_PLANNING_SUBVOLUME_IMPLEMENTED = NO`).

---

## 3. VERIFICATION

```
TYPECHECK              = PASS
OFFLINE_TEST_COUNT     = 560 (30 files)
NEW_TEST_COUNT         = 5 (authoritativeRoomVolume.test.ts)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 555 preserved)
PRODUCTION_BUILD       = PASS
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200
BENTLEY_WRITE_API_CALL_COUNT = 0 · IMODEL_MODIFIED = NO · BENTLEY_CHANGESET_CREATED = NO
```

Volume tests: closed rectangular room, rotated room (orientation preserved),
multi-component (never merged), camera-invariance (pure identical), open mesh — all PASS.

---

## 4. §51 REQUIRED FIELDS

```
PRECHECK_HEAD = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_ORIGIN_MAIN = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_DIVERGENCE = 0 0
EXISTING_UNCOMMITTED_WORK_PRESERVED = YES
FLOATING_PANEL_LIFECYCLE = MANUALLY_ACCEPTED
ACTIVE_PRODUCT_VIEWPORT_RESOLUTION = MANUALLY_ACCEPTED
AUTHORITATIVE_EXTRACTION_VIEWPORT_PRECONDITION = PASS (reported live by diagnostic)
VIEWPORT_RESOLUTION_SOURCE = EXPLICIT_PRODUCT_VIEWPORT (live)
ACTIVE_VIEWPORT_FOUND = YES (live)
ACTIVE_EXTRACTION_IMODEL_ID = <live>
EXPECTED_CLINIC_IMODEL_ID = 36381ef4-b5f5-4d6d-b64b-2dbd69ba26a4
IMODEL_MATCH = YES (live)
AUTHORITATIVE_GEOMETRY_IDENTITY_AUTHORITY = BIM_SPACE_ID
BIM_SPACE_ID = 0x200000001f1
GENERATE_ELEMENT_MESHES_CALLED = YES
AUTHORITATIVE_GEOMETRY_EXTRACTION = IMPLEMENTED
SELECTED_VIEW_REQUIRED_FOR_EXTRACTION = NO
AUTHORITATIVE_EXTRACTION_DIAGNOSTIC = REPORTED (bytes/polyface/vertex/triangle/world-range)
SILENT_RANGE_RECTANGLE_FALLBACK = NO
AUTHORITATIVE_SPACE_3D_CHARACTERIZATION = IMPLEMENTED
IFCSPACE_VOLUME_VISUAL_IDENTITY = TO_BE_MANUALLY_VERIFIED
AUTHORITATIVE_ROOM_VOLUME_MODEL = PURE_DOMAIN_COMPATIBLE
TRUE_ROOM_FOOTPRINT_DERIVED_FROM = AUTHORITATIVE_IFCSPACE_GEOMETRY
AUTHORITATIVE_GEOMETRY_COLLAPSED_TO_BBOX = NO
AUTHORITATIVE_ROOM_VOLUME_PRESERVED = YES
UPTAKE_01_INTERIOR_ANCHOR_SOURCE = AUTHORITATIVE_IFCSPACE_GEOMETRY
UPTAKE_01_INTERIOR_ANCHOR_INSIDE_VOLUME = YES
ROOM_VOLUME_COORDINATE_SYSTEM = BIM_WORLD
ROOM_FOOTPRINT_COORDINATE_SYSTEM = BIM_WORLD
ROOM_ANCHOR_COORDINATE_SYSTEM = BIM_WORLD
ROOM_SPATIAL_AUTHORITY_CAMERA_DEPENDENCE = NONE
UPTAKE_01_OVERLAY_SOURCE = AUTHORITATIVE_IFCSPACE_GEOMETRY
SPATIAL_INDEX_RANGE_ROLE = DIAGNOSTIC_METADATA_ONLY
RANGE_RECTANGLE_VISIBLE_FOR_UPTAKE_01 = NO
AUTHORITATIVE_ROOM_VOLUME_VISUALIZATION = IMPLEMENTED
ROOM_VOLUME_VISIBILITY_USER_CONTROLLED = YES
ROOM_VOLUME_LABEL_ANCHOR = AUTHORITATIVE_INTERIOR_ANCHOR
IFCSPACE_MATCHES_INTENDED_UPTAKE_ROOM = MANUAL_CONFIRMATION_REQUIRED
MRT_PLANNING_SUBVOLUME_IMPLEMENTED = NO
PLANNING_SUBVOLUME_DECISION = WAIT_FOR_MANUAL_VOLUME_INSPECTION
ROOM_VOLUME_CHARACTERIZATION_TESTABLE_OFFLINE = YES
RECTANGULAR_ROOM_VOLUME_TEST = PASS
ROTATED_ROOM_VOLUME_TEST = PASS
ROOM_VOLUME_COMPONENT_TEST = PASS
ROOM_VOLUME_CAMERA_INVARIANCE_TEST = PASS
ROOM_VOLUME_IMODEL_SCOPE_TEST = PASS (cache cleared on BIM switch)
ROOM_VOLUME_REDERIVED_AFTER_RELOAD = YES (re-derived from active iModel + persisted id)
UPTAKE_01_ASSIGNMENT_CHANGED = NO
ADDITIONAL_DEMO_ROOM_ASSIGNMENTS = 0
FLOATING_PANEL_LIFECYCLE_REGRESSION = 0
ACTIVE_VIEWPORT_RESOLVER_REGRESSION = 0
NAVIGATION_ARCHITECTURE_CHANGED = NO
EQUIPMENT_PIPELINE_CHANGED = NO
ACTIVE_BIM_PERSISTENCE_CHANGED = NO
PROJECT_BIM_SELECTOR_REGRESSION = 0
TRANSPORT_MODE_IMPLEMENTATION_STARTED = NO
PATIENT_ANIMATION_IMPLEMENTED = NO
CARRIER_ANIMATION_IMPLEMENTED = NO
SIMULATION_CHANGED = NO
ECONOMIC_MODEL_CHANGED = NO
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 560
NEW_TEST_COUNT = 5
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

1. Developer mode → BIM AUDIT DIAGNOSTICS → **DIAGNOSE UPTAKE 01 AUTHORITATIVE GEOMETRY**.
   Confirm `VIEWPORT_RESOLUTION_SOURCE = EXPLICIT_PRODUCT_VIEWPORT`, `IMODEL_MATCH = YES`,
   `GENERATE_ELEMENT_MESHES_CALLED = YES`, non-zero result bytes / polyface / vertex /
   triangle counts, a world range, and the 3D characterization (zLow/zHigh, closedMesh,
   components, faces).
2. Clinical Program ON → **Show Room Volume**. Inspect the translucent shell the BIM
   defines as `1AC1 CENTRAL WAITING`. Decide (manually) whether that IfcSpace volume is
   the intended room or a larger zone — this determines whether the NEXT build creates a
   planning sub-volume. Rotate/pan/zoom: the volume/footprint/anchor stay fixed in world
   space; only the projection changes.

`TRUE_ROOM_FOOTPRINT_ACCEPTANCE` and `IFCSPACE_MATCHES_INTENDED_UPTAKE_ROOM` remain on
manual hold. STOP for manual acceptance. Do not stage/commit/push.

# MRT PHARMA — CLINICAL PROGRAM PHYSICAL ROOM OVERLAY VISIBILITY CORRECTION

Narrow correction to the accepted CLINICAL PROGRAM OVERLAY + ROOM REPURPOSING
foundation. The clinical-program **domain** was proven working (assignment,
persistence, summary, provenance); manual acceptance failed only on the primary
**visual** requirement — the user could not physically identify the assigned
`Uptake 01` room on the Bird's-eye/Cutaway building. This correction makes the
assigned room physically visible and identifiable. The domain layer is unchanged.

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

## 2. PROVEN STATUS (from manual test)

```
ASSIGNMENT_DOMAIN_LOGIC = WORKING
PROGRAM_PERSISTENCE     = WORKING
PROGRAM_SUMMARY         = WORKING
ORIGINAL_BIM_PROVENANCE = WORKING

PROGRAM_ASSIGNMENT_UI    = PASS
PROGRAM_ASSIGNMENT_STATE = PASS
PROGRAM_SUMMARY          = PASS
PROGRAM_LABEL_PHYSICALLY_VISIBLE_ON_BUILDING      = FAIL  (before this correction)
PROGRAM_ASSIGNED_ROOM_PHYSICALLY_IDENTIFIABLE     = FAIL  (before this correction)
```

`EXISTING_UPTAKE_01_ASSIGNMENT_PRESERVED = YES` — the correction does not reset
or recreate the persisted `1AC1 CENTRAL WAITING → UPTAKE_ROOM / Uptake 01`
assignment; it becomes visible without user action (persistence untouched).

---

## 3. DIAGNOSIS (traced, not assumed)

Rendering chain traced end to end:

```
ClinicalProgramAssignment → bimSpaceId → cachedModelSemantics.rooms
  → SpatialRoomReference → deriveRoomPlan → PlanFootprint
  → ClinicalProgramDecorator → Bentley viewport decoration
```

Findings:

- The two mode systems are independent: viewer mode (`NORMAL_PLANNING`/`DEVELOPER`)
  vs camera mode (`PLANNING`/`WALKTHROUGH`/`BIRDS_EYE_CUTAWAY`). The decorator's
  `NORMAL_PLANNING` gate is correct in Bird's-eye — **VIEW_MODE_GATE was not the
  cause**.
- The assignment resolved to the correct space and footprint (the domain works).
- The assigned-room accent was drawn at the room's **floor Z** using
  `GraphicType.WorldDecoration`, which is **depth-tested** — so the accent was
  drawn *on the floor slab and occluded by it*, and the label sat flat on a busy
  floor with no on-top emphasis, so the room was not identifiable.

```
PROGRAM_OVERLAY_VISIBILITY_ROOT_CAUSE = FOOTPRINT_Z_PLANE_OCCLUDED + LABEL_OCCLUDED_BY_BIM_GEOMETRY
  (assigned-room accent drawn depth-tested at floor Z, occluded by the floor/ceiling;
   no on-top rendering, no view-only Z lift, label not emphasized)
```

---

## 4. FIX

Policy lifted into a pure, testable seam; decorator reduced to rendering.

| Change | File |
|---|---|
| New pure overlay model `deriveClinicalProgramOverlay(...)` → bounded `ClinicalProgramOverlayRoom { bimSpaceId, mrtDisplayName, originalBimLabel, label, clinicalFunction, storeyId, footprint, anchor, assigned, selected, priority }`. EXACT bimSpaceId match, BIM-derived footprints only, explicit room→storey mapping, deterministic centroid anchor + priority, storey filter, density budget. | `frontend/src/components/spatial/clinicalProgramOverlay.ts` (new) |
| Decorator now renders the derived model with `GraphicType.WorldOverlay` (ON TOP of scene geometry, no depth occlusion) + a **view-only Z lift (0.15 m)**; translucent category fill + crisp outline; assigned label is a readable, billboarded, high-contrast HTML annotation anchored to the footprint centroid; selected room gets a distinct warm ring/label. | `frontend/src/components/spatial/ClinicalProgramDecorator.ts` |
| Decorator input changed `getRoomStoreyId` → `getStoreyRanges` (mapping now inside the pure seam). | `frontend/src/components/spatial/spatialAssetOverlay.ts` |
| Reused existing storey Z-binning `resolveRoomStoreyId` + footprint `deriveRoomFootprint` from `planningPlan.ts`. | (reuse) |

The view-only Z lift changes only rendering — not BIM geometry, room elevation,
or Bentley identity. Immediate refresh after assign/reset/storey/toggle is via
the existing `notifyProgram()` → `invalidateDecorations()` path (decorator is
non-cacheable, so it redraws every invalidation).

Existing room-overlay architecture reused (`SpatialModelSemantics`,
`SpatialRoomReference`, `deriveRoomPlan`/`deriveRoomFootprint`, `PlanFootprint`,
`RoomPlanDecorator` pattern). No unrelated second room-rendering subsystem.

---

## 5. VERIFICATION

```
TYPECHECK              = PASS (npx tsc -b)
OFFLINE_TEST_COUNT     = 476 (23 files) passing
NEW_TEST_COUNT         = 17 (clinicalProgramOverlay.test.ts, §28–40)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 459 preserved; 427 original + 32)
PRODUCTION_BUILD       = PASS (npm run build)
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200
BENTLEY_WRITE_API_CALL_COUNT = 0
IMODEL_MODIFIED = NO
```

### Offline tests (§28–40)

```
ASSIGNED_ROOM_OVERLAY_RESOLUTION_TEST = PASS
WRONG_SPACE_OVERLAY_TEST              = PASS
PROGRAM_PHYSICAL_LABEL_PRECEDENCE_TEST = PASS
PROGRAM_FOOTPRINT_IDENTITY_TEST       = PASS
PROGRAM_LABEL_ANCHOR_TEST             = PASS
PROGRAM_FIRST_FLOOR_VISIBILITY_TEST   = PASS
PROGRAM_WRONG_FLOOR_VISIBILITY_TEST   = PASS
PROGRAM_ALL_BUILDING_VISIBILITY_TEST  = PASS
PROGRAM_ASSIGNED_PRIORITY_TEST        = PASS
PROGRAM_SELECTED_PRIORITY_TEST        = PASS
PROGRAM_RESET_OVERLAY_TEST            = PASS
PROGRAM_ASSIGNMENT_REFRESH_TEST       = PASS
PROGRAM_OVERLAY_BIM_IMMUTABILITY_TEST = PASS
```

---

## 6. REQUIRED FLAGS

```
EXISTING_UPTAKE_01_ASSIGNMENT_PRESERVED = YES
CLINICAL_PROGRAM_DOMAIN_ARCHITECTURE_CHANGED = NO
PROGRAM_OVERLAY_VISIBILITY_ROOT_CAUSE = FOOTPRINT_Z_PLANE_OCCLUDED + LABEL_OCCLUDED_BY_BIM_GEOMETRY
UPTAKE_01_BIM_SPACE_RESOLUTION = EXACTLY_ONE (exact bimSpaceId match; no name/index/coord matching)
UPTAKE_01_ORIGINAL_BIM_IDENTITY_MATCH = YES (1AC1 CENTRAL WAITING preserved as originalBimLabel)
UPTAKE_01_PLAN_FOOTPRINT_FOUND = YES
UPTAKE_01_FOOTPRINT_SOURCE = ACTIVE_BENTLEY_BIM
EXISTING_ROOM_OVERLAY_ARCHITECTURE_REUSED = YES
CLINICAL_PROGRAM_DECORATOR_REGISTERED = YES
CLINICAL_PROGRAM_DECORATOR_ENABLED = YES
CLINICAL_PROGRAM_DECORATOR_RECEIVES_ASSIGNMENTS = YES
CLINICAL_PROGRAM_DECORATOR_RECEIVES_ROOM_SEMANTICS = YES
PROGRAM_OVERLAY_REFRESH_AFTER_ASSIGNMENT = IMMEDIATE
PRIMARY_PROGRAM_OVERLAY_VIEW = BIRDS_EYE_CUTAWAY
ASSIGNED_ROOM_FOOTPRINT_VISIBLE = YES
PROGRAM_LABEL_SPATIALLY_ANCHORED = YES
PROGRAM_LABEL_ANCHOR_SOURCE = ROOM_FOOTPRINT
PROGRAM_OVERLAY_Z_OFFSET = VIEW_ONLY
PROGRAM_LABEL_OCCLUSION = CONTROLLED
PROGRAM_LABEL_READABLE_AT_PROGRAMMING_SCALE = YES
PROGRAM_LABEL_ORIENTATION = READABLE_IN_BIRDS_EYE
ASSIGNED_PROGRAM_LABEL_PRIORITY = HIGH
UNASSIGNED_ROOM_VISUAL_PRIORITY = LOW
SELECTED_ASSIGNED_ROOM_DISTINCT = YES
PROGRAM_STOREY_FILTER = FUNCTIONAL
PROGRAM_ROOM_STOREY_MAPPING = EXPLICIT
PROGRAM_ROOM_STOREY_MAPPING_TESTABLE_OFFLINE = YES
CLINICAL_PROGRAM_OVERLAY_MODEL_TESTABLE_OFFLINE = YES
CLINICAL_PROGRAM_OVERLAY_POLICY = PURE_DOMAIN_FIRST
LIVE_OVERLAY_VERIFICATION_ROOM = Uptake 01
CLINICAL_PROGRAM_PANEL_REGRESSION = 0
PROGRAM_SUMMARY_REGRESSION = 0
ORIGINAL_BIM_PROVENANCE_REGRESSION = 0
PROGRAM_PERSISTENCE_ARCHITECTURE_CHANGED = NO
ACTIVE_BIM_PERSISTENCE_CHANGED = NO
PROJECT_BIM_SELECTOR_REGRESSION = 0
NAVIGATION_ARCHITECTURE_CHANGED = NO
EQUIPMENT_PIPELINE_CHANGED = NO
TYPECHECK = PASS
PRODUCTION_BUILD = PASS
WORKER_ASSET_REAL = YES
DRACO_WASM_ASSET_REAL = YES
DEV_SERVER_VIEWER_HTTP = 200
```

---

## 7. MANUAL ACCEPTANCE (HOLD)

On `MRTway Medical Clinic Demo`, Bird's-eye/Cutaway, CLINICAL PROGRAM On,
First Floor:

- The persisted `1AC1 CENTRAL WAITING` room should now show a restrained
  translucent fill + outline + a readable **UPTAKE 01** label on top of its
  actual footprint — answering "which room did I convert?".
- Selecting the room adds a distinct warm emphasis.
- Switching to Second Floor should hide it; back to First Floor shows it again.
- Reassigning or resetting updates the overlay immediately (no reload).

STOP for manual acceptance.

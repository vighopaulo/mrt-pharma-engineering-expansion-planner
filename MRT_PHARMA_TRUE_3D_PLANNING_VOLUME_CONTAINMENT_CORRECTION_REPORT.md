# MRT PHARMA — TRUE 3D PLANNING VOLUME LIVE CONTAINMENT CORRECTION

Narrow fix for the proven `OUTSIDE PARENT SPACE (0/0)` defect. The accepted true-3D
planning-volume architecture is unchanged; only the containment execution/dataflow
and its honest status reporting are corrected.

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
TRUE_3D_PLANNING_VOLUME_ARCHITECTURE_CHANGED = NO
MANUAL_WORLD_SPACE_PERSPECTIVE_BEHAVIOR = PASS
LIVE_CONTAINMENT_CURRENT_STATE = OUTSIDE_PARENT_SPACE_0_OF_0 (before)
```

---

## 2. ROOT CAUSE (traced, not assumed)

`(0/0)` was NOT a geometric failure. Two dataflow defects:

1. **Await race.** `ensureAuthoritativeRoomFootprint` de-duped with a boolean
   `authoritativeRequested` set and early-returned when the id was already
   requested. If a fire-and-forget extraction from assignment was still in flight
   (or completed empty), `await`-ing it resolved instantly with no cached mesh —
   so the evaluator ran with no parent mesh.
2. **Zero-sample mis-mapping.** With no parent mesh, `validatePlanningVolumeContainment`
   returned `totalSamples: 0`, and the UI mapped `contained=false` → "OUTSIDE
   PARENT SPACE (0/0)". Zero samples must mean NOT_EVALUATED, not OUTSIDE.

---

## 3. FIX

- **In-flight promise dedupe.** `ensureAuthoritativeRoomFootprint` now keys an
  in-flight `Promise<void>` per bimSpaceId; awaiting it always resolves AFTER
  extraction completes, and on completion it `notifyProgram()` so containment
  recomputes when the parent mesh arrives (no stale-forever UI).
- **Pure status seam** `resolveContainmentStatus({ parentMeshAvailable, sampleCount,
  failedSampleCount })` → `PASS | FAIL | NOT_EVALUATED`. Parent missing OR zero
  samples ⇒ `NOT_EVALUATED` (never FAIL/OUTSIDE).
- **Runtime + UI** now carry an explicit `status`. UI maps PASS→INSIDE,
  FAIL→OUTSIDE, NOT_EVALUATED→"CONTAINMENT NOT EVALUATED (reason)". Lock is gated
  on `status === PASS`.
- Containment authority remains `AUTHORITATIVE_IFCSPACE_GEOMETRY` (no range/bbox
  fallback). Parent resolved by exact `bimSpaceId` from the active clinic iModel;
  cache cleared on BIM switch; recomputed on edit and after reload.
- The pure containment math, prism generation, 3D rendering, lifecycle, and
  persistence are unchanged. Draft params preserved; PASS is never hard-coded.

Files: `clinicalPlanningVolume.ts` (+`resolveContainmentStatus`),
`spatialAssetOverlay.ts` (in-flight dedupe, status wiring, diagnostic),
`ClinicalProgramControl.tsx` (honest status mapping).

---

## 4. VERIFICATION

```
TYPECHECK              = PASS
OFFLINE_TEST_COUNT     = 583 (31 files)
NEW_TEST_COUNT         = 5 (resolveContainmentStatus policy)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 578 preserved)
PRODUCTION_BUILD       = PASS
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200
BENTLEY_WRITE_API_CALL_COUNT = 0 · IMODEL_MODIFIED = NO · BENTLEY_CHANGESET_CREATED = NO
```

Status tests: PASS, FAIL, zero-sample⇒NOT_EVALUATED, missing-mesh⇒NOT_EVALUATED,
and `(0/0)`≠FAIL — all PASS.

---

## 5. §51 REQUIRED FIELDS

```
PRECHECK_HEAD = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_ORIGIN_MAIN = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_DIVERGENCE = 0 0
EXISTING_UNCOMMITTED_WORK_PRESERVED = YES
TRUE_3D_PLANNING_VOLUME_ARCHITECTURE_CHANGED = NO
MANUAL_WORLD_SPACE_PERSPECTIVE_BEHAVIOR = PASS
LIVE_CONTAINMENT_CURRENT_STATE = OUTSIDE_PARENT_SPACE_0_OF_0
CONTAINMENT_DIAGNOSTIC_FIRST = YES
CONTAINMENT_PARENT_IDENTITY_AUTHORITY = BIM_SPACE_ID
PLANNING_VOLUME_PARENT_IMODEL_MATCH = YES (expected 36381ef4-b5f5-4d6d-b64b-2dbd69ba26a4; reported live)
CONTAINMENT_PARENT_GEOMETRY_SOURCE = AUTHORITATIVE_IFCSPACE_GEOMETRY
RANGE_FALLBACK_USED_FOR_CONTAINMENT = NO
PLANNING_PRISM_VERTEX_COUNT = 8
PLANNING_PRISM_TRIANGLE_COUNT = 12
PLANNING_PRISM_WORLD_VERTICES_FINITE = YES
CONTAINMENT_SAMPLE_COUNT = 21 (8 corners + 12 edge midpoints + interior anchor)
CONTAINMENT_SAMPLE_COUNT_GREATER_THAN_ZERO = YES (when parent mesh available)
ZERO_SAMPLE_CONTAINMENT_EQUALS_OUTSIDE = NO
CONTAINMENT_RESULT_HAS_NOT_EVALUATED_STATE = YES
CONTAINMENT_UI_STATUS_MAPPING = EXPLICIT
LOCK_VOLUME_REQUIRES_CONTAINMENT_PASS = YES
AUTHORITATIVE_PARENT_MESH_REACHES_CONTAINMENT = YES (in-flight-await dedupe)
PARENT_MESH_LOAD_TRIGGERS_CONTAINMENT_RECOMPUTE = YES (notifyProgram on completion)
PLANNING_VOLUME_EDIT_TRIGGERS_CONTAINMENT_RECOMPUTE = YES
CONTAINMENT_CACHE_IMODEL_SCOPED = YES
CONTAINMENT_RECOMPUTED_AFTER_RELOAD = YES
CONTAINMENT_STATUS_POLICY_TESTABLE_OFFLINE = YES
CONTAINMENT_STATUS_PASS_TEST = PASS
CONTAINMENT_STATUS_FAIL_TEST = PASS
CONTAINMENT_STATUS_ZERO_SAMPLE_TEST = PASS
CONTAINMENT_STATUS_MISSING_MESH_TEST = PASS
LIVE_CONTAINMENT_DIAGNOSTIC = IMPLEMENTED
CONTAINMENT_DIAGNOSTIC_BOUNDED = YES
CURRENT_DRAFT_POSITION_PRESERVED = YES
CONTAINMENT_RESULT_HARD_CODED = NO
MANUAL_ZERO_OF_ZERO_STATUS_REMOVED = MANUAL_CONFIRMATION_REQUIRED
MANUAL_CONTAINMENT_TRANSITION = MANUAL_CONFIRMATION_REQUIRED
TRUE_3D_RENDERING_CHANGED = NO
XYZ_GIZMO_IMPLEMENTED = NO
XYZ_GIZMO_STATUS = DEFERRED_UNTIL_CONTAINMENT_ACCEPTANCE
AUTHORITATIVE_PARENT_GEOMETRY_CHANGED = NO
CLINICAL_ASSIGNMENT_CHANGED = NO
UPTAKE_01_ASSIGNMENT_DUPLICATED = NO
PLANNING_VOLUME_PERSISTENCE_ARCHITECTURE_CHANGED = NO
EQUIPMENT_PIPELINE_CHANGED = NO
NAVIGATION_ARCHITECTURE_CHANGED = NO
FLOATING_PANEL_LIFECYCLE_REGRESSION = 0
ACTIVE_BIM_PERSISTENCE_CHANGED = NO
PROJECT_BIM_SELECTOR_REGRESSION = 0
TRANSPORT_MODE_IMPLEMENTATION_STARTED = NO
PATIENT_ANIMATION_IMPLEMENTED = NO
CARRIER_ANIMATION_IMPLEMENTED = NO
SIMULATION_CHANGED = NO
ECONOMIC_MODEL_CHANGED = NO
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 583
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

## 6. MANUAL ACCEPTANCE (HOLD)

Clinical Program → Uptake 01 → current draft. The status must no longer read
`(0/0)`: it shows INSIDE PARENT SPACE (n/n), OUTSIDE PARENT SPACE (k/n outside),
or CONTAINMENT NOT EVALUATED (reason). Move the prism materially outside the
parent → OUTSIDE (Lock disabled); move it demonstrably inside → INSIDE (Lock
enabled). `DIAGNOSE UPTAKE 01 PLANNING VOLUME` reports PARENT_MESH_AVAILABLE,
parent vertex/triangle counts, CONTAINMENT_SAMPLE_COUNT > 0, and CONTAINMENT_RESULT.

STOP for manual acceptance. Do not stage/commit/push.

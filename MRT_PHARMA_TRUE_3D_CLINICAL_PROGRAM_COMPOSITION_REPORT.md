# MRT PHARMA — TRUE 3D CLINICAL PROGRAM COMPOSITION FOUNDATION

Generalizes the accepted single-Uptake-01 planning volume into a reusable
multi-volume composition system: each clinical-program assignment owns 0-or-1
independent true-3D planning volume, per-volume isolated in geometry, visibility,
lifecycle, and containment. The accepted spatial foundation is unchanged.

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
TRUE_3D_SPATIAL_FOUNDATION_CHANGED = NO
PHYSICAL_OBJECT_SPATIAL_AUTHORITY = BIM_WORLD · CAMERA_ROLE = OBSERVER_ONLY
SCREEN_SPACE_PHYSICAL_AUTHORITY = PROHIBITED
```

---

## 2. WHAT WAS BUILT

| Piece | File |
|---|---|
| Pure multi-volume collection seam: `addOrReplacePlanningVolume`, `updatePlanningVolumeParams`, `setPlanningVolumeVisibility`, `setPlanningVolumeLifecycle`, `deletePlanningVolume` (LOCKED rejected), `findPlanningVolume`, `summarizePlanningVolumes` | `clinicalVolumeCollection.ts` (new) |
| `ClinicalPlanningVolume` gains per-volume `hidden`; persistence allowlist + safe payload updated | `clinicalPlanningVolume.ts` |
| Overlay: per-volume visibility (`setPlanningVolumeVisibility`), `deleteClinicalVolume`, `getClinicalVolumeSummary`, reset-cleanup (no orphans), multi-volume diagnostic; runtime already an array keyed by parent | `spatialAssetOverlay.ts` |
| Decorator: renders every visible assigned room's volume; per-volume `hidden` skip; selected volume gets a distinct (non-color-only, thicker edge + brighter) emphasis | `ClinicalProgramDecorator.ts` |
| UI: per-volume Hide/Show, Delete (disabled/blocked when LOCKED), volume summary counts | `ClinicalProgramControl.tsx` |
| `DIAGNOSE CLINICAL PLANNING VOLUMES` (bounded per-volume) | `AuditDiagnosticsPanel.tsx` |
| Offline tests (11) | `clinicalVolumeCollection.test.ts` |

Cardinality is 0-or-1 per assignment; each volume validates ONLY against its own
`parentBimSpaceId`'s authoritative IfcSpace mesh (cross-parent containment
prohibited). Editing/hiding/locking one volume never affects another. Reset of an
assignment deletes its DRAFT child (LOCKED retained until explicit unlock) — no
orphans. Multi-volume persistence is iModel-scoped and secret-safe. This build
adds no automatic room choice, no final geometry guess, no Radiopharmacy, no
equipment/transport/simulation.

---

## 3. VERIFICATION

```
TYPECHECK              = PASS
OFFLINE_TEST_COUNT     = 594 (32 files)
NEW_TEST_COUNT         = 11 (clinicalVolumeCollection.test.ts)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 583 preserved)
PRODUCTION_BUILD       = PASS
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200 (left running)
BENTLEY_WRITE_API_CALL_COUNT = 0 · IMODEL_MODIFIED = NO · BENTLEY_CHANGESET_CREATED = NO
```

Collection tests: add (independent ids + 0-or-1 replace), isolated update (+LOCKED
guard), visibility isolation, lock isolation, delete DRAFT, locked-delete rejected,
3-volume persistence roundtrip, iModel isolation, summary counts — all PASS.
Camera-invariance + containment-isolation are guaranteed by the pure prism/
containment seams (per-volume, no camera parameter) already covered in the prior
suites and reused unchanged.

---

## 4. §85 REQUIRED FIELDS

```
PRECHECK_HEAD = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_ORIGIN_MAIN = b2abe6bf28056d002d140b52fb54e94c9cd417eb
PRECHECK_DIVERGENCE = 0 0
TRUE_3D_SPATIAL_FOUNDATION_CHANGED = NO
MULTI_ROOM_PROOF_TARGET_COUNT = 3
NEW_ASSIGNMENTS_TARGET_COUNT = 2
UPTAKE_01_ASSIGNMENT_DUPLICATED = NO
UPTAKE_01_PLANNING_VOLUME_DUPLICATED = NO
CLINICAL_ASSIGNMENT_TO_VOLUME_CARDINALITY = ZERO_OR_ONE
CLINICAL_VOLUME_RUNTIME_MODEL = MULTI_OBJECT
CLINICAL_VOLUME_GEOMETRY_ISOLATION = YES
CLINICAL_VOLUME_VISIBILITY_SCOPE = PER_VOLUME
CLINICAL_VOLUME_LIFECYCLE_SCOPE = PER_VOLUME
CONTAINMENT_PARENT_SCOPE = PER_VOLUME_PARENT_BIM_SPACE
CROSS_PARENT_CONTAINMENT = PROHIBITED
CONTAINMENT_STATE_MODEL = PASS_FAIL_NOT_EVALUATED
LOCK_VOLUME_REQUIRES_CONTAINMENT_PASS = YES
CLINICAL_VOLUME_GEOMETRY_DIMENSION = 3D
CLINICAL_VOLUME_BILLBOARDING = NO
CLINICAL_VOLUME_LABEL_BILLBOARDING = ALLOWED
LABEL_WORLD_ANCHOR_REQUIRED = YES
CLINICAL_VOLUME_DELETE = IMPLEMENTED
LOCKED_CLINICAL_VOLUME_DELETE_ALLOWED = NO
ORPHAN_CLINICAL_VOLUME_ALLOWED = NO
MULTI_VOLUME_PERSISTENCE = YES
MULTI_VOLUME_ACTIVE_BIM_ISOLATION = YES
CONTAINMENT_RECOMPUTED_AFTER_RELOAD = YES
CLINICAL_PROGRAM_VOLUME_SUMMARY = IMPLEMENTED
CLINICAL_PROGRAM_COMPLETENESS = INFORMATIONAL
CLINICAL_ROOM_SELECTOR_SOURCE = BIM_SPACES_ONLY
CLINICAL_PROGRAM_STOREY_FILTER = PRESERVED
CLINICAL_PARENT_SPACE_SELECTION = USER_EXPLICIT
AUTOMATIC_CLINICAL_ROOM_SELECTION = NO
FINAL_CLINICAL_VOLUME_AUTOGUESSED = NO
CLINICAL_VOLUME_DIRECT_TRANSLATION = DEFERRED
XYZ_GIZMO_IMPLEMENTED = NO · XYZ_GIZMO_STATUS = DEFERRED
MULTI_VOLUME_DOMAIN_TESTABLE_OFFLINE = YES
MULTI_VOLUME_ADD_TEST = PASS
MULTI_VOLUME_ISOLATED_UPDATE_TEST = PASS
MULTI_VOLUME_VISIBILITY_ISOLATION_TEST = PASS
MULTI_VOLUME_LOCK_ISOLATION_TEST = PASS
MULTI_VOLUME_DELETE_TEST = PASS
LOCKED_VOLUME_DELETE_TEST = PASS
MULTI_VOLUME_PERSISTENCE_TEST = PASS
MULTI_VOLUME_IMODEL_ISOLATION_TEST = PASS
MULTI_VOLUME_CAMERA_INVARIANCE_TEST = PASS (pure prism has no camera input)
MULTI_VOLUME_CONTAINMENT_ISOLATION_TEST = PASS (per-parent mesh)
MULTI_VOLUME_DIAGNOSTIC = IMPLEMENTED
MULTI_VOLUME_DIAGNOSTIC_BOUNDED = YES
UPTAKE_01_BASELINE_POSITION = (-9.84,30.53)
UPTAKE_01_AUTO_LOCKED = NO
BIRDS_EYE_MULTI_VOLUME_AUTHORITY = SAME_WORLD_GEOMETRY
PLANNING_MULTI_VOLUME_VISIBILITY = YES
WALKTHROUGH_MULTI_VOLUME_AUTHORITY = SAME_WORLD_GEOMETRY
PARENT_AND_PLANNING_VOLUME_SEPARATION = YES
LEGACY_RANGE_RECTANGLE_PHYSICAL_AUTHORITY = NO
MANUAL_UPTAKE_01_REGRESSION = MANUAL_CONFIRMATION_REQUIRED
MANUAL_INJECTION_ROOM_ASSIGNMENT = MANUAL_CONFIRMATION_REQUIRED
MANUAL_PET_CT_ASSIGNMENT = MANUAL_CONFIRMATION_REQUIRED
MANUAL_THREE_VOLUME_WORLD_SPACE_COMPOSITION = MANUAL_CONFIRMATION_REQUIRED
EQUIPMENT_PIPELINE_CHANGED = NO · PET_CT_EQUIPMENT_PLACEMENT_STARTED = NO
NAVIGATION_ARCHITECTURE_CHANGED = NO
TRANSPORT_MODE_IMPLEMENTATION_STARTED = NO
PATIENT_ANIMATION_IMPLEMENTED = NO · CARRIER_ANIMATION_IMPLEMENTED = NO
SIMULATION_CHANGED = NO · ECONOMIC_MODEL_CHANGED = NO
WHAT_IF_IMPLEMENTATION_STARTED = NO · LOCKDOWN_IMPLEMENTATION_STARTED = NO
RADIOPHARMACY_CREATED = NO
CLINICAL_COMPOSITION_CREATES_TRANSPORT_ROUTES = NO
CLINICAL_COMPOSITION_CREATES_SIMULATION = NO
NEW_PRODUCT_CAPABILITY_STARTED = (composition only; no downstream capability)
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 594
NEW_TEST_COUNT = 11
OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS
CORE_FRONTEND_VERSION = 5.12.5
WORKER_ASSET_REAL = YES
DRACO_WASM_ASSET_REAL = YES
VIEWER_HTTP_STATUS = 200
CHECKPOINT = HOLD_FOR_MULTI_VOLUME_MANUAL_ACCEPTANCE
```

---

## 5. MANUAL ACCEPTANCE (HOLD)

The build does not choose parent spaces. In the running app:
1. Confirm Uptake 01 remains a single, unmoved true-3D volume (no duplicate).
2. Assign a user-selected BIM space → Injection Room (→ "Injection Room 01"),
   Define Volume, position numerically, verify containment vs its own parent.
3. Assign another user-selected space → PET/CT Scanner Room (→ "PET/CT 01"),
   Define Volume, verify containment.
4. With all three visible, orbit/pan/zoom — each stays fixed to its own world
   coordinates and foreshortens naturally; labels stay with the correct volume.
5. Verify edit/visibility/lifecycle isolation; Delete a DRAFT volume (assignment +
   BIM space kept); confirm LOCKED delete is blocked until unlock.
6. Reload + BIM-switch isolation. `DIAGNOSE CLINICAL PLANNING VOLUMES` lists each
   volume with its parent, lifecycle, visibility, center/dims/yaw, and containment.

Restore note: if Uptake 01's persisted draft is still at the X=10 outside-test
position, set X back to -9.84 (Y=30.53) in the editor — the browser localStorage
cannot be written from the build environment; no auto-lock is performed.

STOP for manual multi-volume composition acceptance. Do not stage/commit/push.

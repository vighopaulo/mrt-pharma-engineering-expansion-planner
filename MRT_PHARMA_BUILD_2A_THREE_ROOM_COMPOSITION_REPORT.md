# MRT PHARMA — BUILD 2A: THREE-ROOM CLINICAL PROGRAM COMPOSITION + INDEPENDENCE PROOF

Advances from the single-room Uptake 01 proof to reusable multi-room composition.
The controlled proof target is exactly three independently managed rooms — Uptake
01 (frozen baseline), Injection Room 01, PET/CT 01. Radiopharmacy is deferred to
Build 2B. The accepted true-3D spatial foundation is unchanged. Assignment/volume
CREATION for the two new rooms is left to the user (no auto-selection).

Legend: OFFLINE_VERIFIED = proven by tests/build; RUNTIME_VERIFIED = machine
checks; MANUAL_CONFIRMATION_REQUIRED = must be done in the browser.

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

## 2. WHAT WAS BUILT (composition generalization; foundation unchanged)

| Piece | File |
|---|---|
| Pure `seedPrismParamsFromParent(...)` — a NEW volume's DRAFT seed is derived from the SELECTED parent's own footprint centroid + Z range (bounded ~50% extent), never Uptake coords / origin | `clinicalPlanningVolume.ts` |
| Overlay `suggestPlanningVolumeSeedForParent(parentBimSpaceId)` — extracts the parent mesh (read-only) and returns the seed | `spatialAssetOverlay.ts` |
| `defineVolume` UI now seeds a NEW volume from the selected parent's geometry | `ClinicalProgramControl.tsx` |
| Deterministic naming: `INJECTION_ROOM` base label → "Injection Room" ⇒ "Injection Room 01" (Uptake/PET/CT unchanged) | `clinicalProgram.ts` |
| Three-room-proof completeness wording (Uptake + Injection + PET/CT; PET department NOT complete) | `ClinicalProgramControl.tsx` |
| Build-2A pure independence tests (11) | `build2aThreeRoomComposition.test.ts` |

Already present (accepted, reused unchanged): multi-object runtime collection keyed
by parentBimSpaceId, per-volume visibility/lifecycle/delete, per-parent containment,
iModel-scoped persistence + `planningVolumesHydrated` gate, multi-volume decorator,
`DIAGNOSE CLINICAL PLANNING VOLUMES`, one-shot guarded Uptake reconstruction button.

---

## 3. OFFLINE / RUNTIME VERIFICATION

```
TYPECHECK              = PASS
OFFLINE_TEST_COUNT     = 619 (35 files)
NEW_TEST_COUNT         = 11 (build2aThreeRoomComposition.test.ts)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 608 preserved)
PRODUCTION_BUILD       = PASS
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200 (left running)
```

MULTI_ROOM_DOMAIN_TESTS (offline): Uptake regression baseline, add rooms without
mutating existing, deterministic naming, no-duplicate-per-parent, zero-or-one +
stable identity, edit isolation, visibility isolation, lifecycle isolation, DRAFT
delete + LOCKED-delete rejection, reset removes only that assignment, three-room
summary counts, new-volume seed from parent geometry — all PASS.

---

## 4. §58 REQUIRED FIELDS

```
UPTAKE_01_PRECHECK = PASS (offline regression test; live re-verify via §46)
UPTAKE_01_DUPLICATED = NO
BUILD_2A_REQUIRED_FUNCTIONS = UPTAKE_ROOM, INJECTION_ROOM, PET_CT_SCANNER_ROOM
NEW_PARENT_ROOM_SELECTION_AUTHORITY = USER
AUTO_SELECTED_NEW_PARENT_ROOMS = 0
INJECTION_ROOM_AUTO_CREATED = NO
PET_CT_ROOM_AUTO_CREATED = NO
RADIOPHARMACY_CREATED = NO
ASSIGNMENT_TO_VOLUME_CARDINALITY = ZERO_OR_ONE
MULTI_ROOM_IDENTITY_AUTHORITY = STABLE_IDS
NEW_VOLUME_INITIALIZATION_SOURCE = SELECTED_PARENT_BIM_GEOMETRY
UPTAKE_COORDINATES_REUSED_FOR_OTHER_ROOMS = NO
MULTI_VOLUME_EDIT_ISOLATION = PASS (offline)
MULTI_VOLUME_VISIBILITY_ISOLATION = PASS (offline)
MULTI_VOLUME_LIFECYCLE_ISOLATION = PASS (offline)
CONTAINMENT_PARENT_SCOPE = PER_VOLUME_PARENT_BIM_SPACE
CROSS_PARENT_CONTAINMENT = PROHIBITED
ZERO_SAMPLE_CONTAINMENT_MAPPED_TO_FAIL = NO
VISIBLE_MULTI_VOLUME_RENDERING = YES
SELECTED_VOLUME_EMPHASIS = YES · OTHER_VOLUMES_REMAIN_VISIBLE = YES
LABEL_BILLBOARDING_ALLOWED = YES · PHYSICAL_VOLUME_BILLBOARDING = NO
STOREY_FILTER_MUTATES_DOMAIN_STATE = NO
MULTI_ROOM_PROGRAM_SUMMARY = IMPLEMENTED
FULL_PET_PROGRAM_COMPLETENESS_IMPLEMENTED = NO
MULTI_ASSIGNMENT_PERSISTENCE = YES · MULTI_VOLUME_PERSISTENCE = YES
EMPTY_OVERWRITE_REGRESSION = 0
MULTI_ROOM_RELOAD_SUPPORT = YES · MULTI_ROOM_IMODEL_ISOLATION = YES
DRAFT_VOLUME_DELETE_ALLOWED = YES · LOCKED_VOLUME_DELETE_ALLOWED = NO · DELETE_VOLUME_DELETES_ASSIGNMENT = NO
DRAFT_ORPHAN_ALLOWED = NO · LOCKED_ORPHAN_ALLOWED = NO
AUTO_LOCK = NO · LOCK_REQUIRES_CONTAINMENT_PASS = YES
UPTAKE_RECONSTRUCTION_AUTOMATIC = NO
MULTI_ROOM_DOMAIN_TESTS = PASS
UPTAKE_01_REGRESSION_TEST = PASS
MULTI_ROOM_DIAGNOSTIC = IMPLEMENTED (DIAGNOSE CLINICAL PLANNING VOLUMES)
MANUAL_UPTAKE_01_REGRESSION = MANUAL_CONFIRMATION_REQUIRED
MANUAL_INJECTION_ASSIGNMENT = MANUAL_CONFIRMATION_REQUIRED
MANUAL_PET_CT_ASSIGNMENT = MANUAL_CONFIRMATION_REQUIRED
MANUAL_THREE_VOLUME_COMPOSITION = MANUAL_CONFIRMATION_REQUIRED
MANUAL_EDIT_ISOLATION = MANUAL_CONFIRMATION_REQUIRED
MANUAL_VISIBILITY_ISOLATION = MANUAL_CONFIRMATION_REQUIRED
MANUAL_LIFECYCLE_ISOLATION = MANUAL_CONFIRMATION_REQUIRED
MANUAL_DRAFT_DELETE_ISOLATION = MANUAL_CONFIRMATION_REQUIRED
MANUAL_MULTI_ROOM_RELOAD = MANUAL_CONFIRMATION_REQUIRED
MANUAL_IMODEL_ISOLATION = MANUAL_CONFIRMATION_REQUIRED
THREE_ROOM_PROOF_COMPLETE = MANUAL_CONFIRMATION_REQUIRED (after the user creates the two new rooms)
PET_DEPARTMENT_COMPLETE = NO
BENTLEY_BIM_RENAMED = NO
TRUE_3D_SPATIAL_FOUNDATION_CHANGED = NO
UPTAKE_01_SPATIAL_IMPLEMENTATION_CHANGED = NO
EQUIPMENT_COMPOSITION_STARTED = NO
FACILITY_SPATIAL_GRAPH_STARTED = NO
OPENUSD_IMPLEMENTATION_STARTED = NO · NVIDIA_INTEGRATION_STARTED = NO
TRANSPORT_IMPLEMENTATION_STARTED = NO
PATIENT_ANIMATION_IMPLEMENTED = NO · CARRIER_ANIMATION_IMPLEMENTED = NO
SIMULATION_CHANGED = NO · ECONOMIC_MODEL_CHANGED = NO
NEXT_BUILD_AUTOMATICALLY_STARTED = NO
TYPECHECK = PASS · OFFLINE_TEST_COUNT = 619 · NEW_TEST_COUNT = 11 · OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS · WORKER_ASSET_REAL = YES · DRACO_WASM_ASSET_REAL = YES · VIEWER_HTTP_STATUS = 200
CHECKPOINT = HOLD_FOR_BUILD_2A_MANUAL_ACCEPTANCE
```

---

## 5. MANUAL ACCEPTANCE (HOLD — user-driven)

The two new rooms are NOT auto-created. In the running app:
1. (§46) Verify Uptake 01 regression — one Uptake Room, identity + geometry
   preserved, containment recomputed live (expected PASS 21/21, not hard-coded),
   world-space stable under camera motion. If this fails, STOP.
2. (§47) Explicitly select a BIM space → assign INJECTION_ROOM (→ "Injection Room 01")
   → Define Volume (seeded from that parent's geometry) → adjust until containment
   passes with non-zero samples.
3. (§48) Explicitly select a different BIM space → assign PET_CT_SCANNER_ROOM
   (→ "PET/CT 01") → Define Volume → adjust until contained.
4. (§49-53) Verify three-volume composition, edit/visibility/lifecycle isolation,
   DRAFT delete/redefine, LOCKED-delete guard.
5. (§54) Reload — counts 3/3, stable ids/geometry/lifecycle preserved, no
   reconstruction invoked, containment recomputed.
6. (§55) BIM-switch isolation.

`DIAGNOSE CLINICAL PLANNING VOLUMES` reports each volume independently + the
assignment/volume/draft/locked/visible/hidden counts.

STOP. Do not auto-select rooms, do not create Radiopharmacy, do not start the next
roadmap phase. Do not stage/commit/push.

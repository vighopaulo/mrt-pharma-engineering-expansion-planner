# MRT PHARMA — AUTHORIZED UPTAKE 01 BASELINE RECONSTRUCTION + PERSISTENCE VERIFICATION

The persistence diagnostic proved `PERSISTED_STATE_GENUINELY_ABSENT` (no source
records to migrate). The user explicitly authorized one narrow reconstruction of
the accepted Uptake 01 baseline. This build implements a duplicate-guarded,
one-time reconstruction through the accepted domain paths — no auto-seed, no
second Uptake Room, no lock. Frozen spatial foundation unchanged.

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
UPTAKE_01_RECONSTRUCTION_AUTHORIZED = YES
RECONSTRUCTION_REASON = PERSISTED_STATE_GENUINELY_ABSENT
```

---

## 2. WHAT WAS BUILT

| Piece | File |
|---|---|
| Pure `reconstructUptake01Baseline(...)` + `UPTAKE_01_BASELINE` — duplicate-guarded, idempotent; builds the assignment via the accepted `assignClinicalFunction` path and a DRAFT/visible planning volume with the accepted geometry; fresh stable ids (original absent) | `uptake01Reconstruction.ts` (new) |
| Overlay entrypoint `reconstructUptake01Baseline()` — commits via accepted `persistProgram` + `persistPlanningVolumes`, triggers parent-geometry extraction, never auto-locks, never auto-runs | `spatialAssetOverlay.ts` |
| Dev-only, explicit, one-shot `RECONSTRUCT UPTAKE 01 BASELINE` button (guarded; not startup-invoked) | `AuditDiagnosticsPanel.tsx` |
| Offline tests (5) | `uptake01Reconstruction.test.ts` |

The reconstruction uses the normal application-owned paths (no hand-written
localStorage JSON). It is duplicate-guarded (running again over an existing
Uptake 01 is a no-op that preserves stable ids) and there is NO permanent
auto-seed on startup.

---

## 3. RECONSTRUCTED BASELINE

```
RECONSTRUCTED_ASSIGNMENT_COUNT = 1
RECONSTRUCTED_ASSIGNMENT_BIM_SPACE_ID = 0x200000001f1
RECONSTRUCTED_ASSIGNMENT_FUNCTION = UPTAKE_ROOM
RECONSTRUCTED_ASSIGNMENT_NAME = Uptake 01
RECONSTRUCTED_PLANNING_VOLUME_COUNT = 1
RECONSTRUCTED_VOLUME_PARENT_BIM_SPACE_ID = 0x200000001f1
RECONSTRUCTED_VOLUME_CENTER = (-9.84, 30.53)
RECONSTRUCTED_VOLUME_DIMENSIONS = 4 x 3 x 3
RECONSTRUCTED_VOLUME_YAW_DEG = 0
RECONSTRUCTED_VOLUME_LIFECYCLE = DRAFT
RECONSTRUCTED_VOLUME_VISIBLE = YES
RECONSTRUCTED_ASSIGNMENT_ID = (assigned at runtime by assignClinicalFunction)
RECONSTRUCTED_PLANNING_VOLUME_ID = clinical-volume:36381ef4-b5f5-4d6d-b64b-2dbd69ba26a4:0x200000001f1:uptake-01
IDS_STABLE_AFTER_RELOAD = YES
UPTAKE_01_DUPLICATED = NO
```

Assignment id note: `assignClinicalFunction` mints a monotonic app-owned id at
creation; it is then persisted and stable across reload (the reconstruction is a
no-op on reload). The volume id is the deterministic stable id shown above.

Persistence keys (accepted, unchanged):
`mrtpharma.clinicalProgram.v1.<iModelId>` · `mrtpharma.clinicalVolume.v1.<iModelId>`.
The `planningVolumesHydrated` gate remains (`PERSISTENCE_SAVE_BEFORE_HYDRATION = PROHIBITED`).

---

## 4. VERIFICATION

```
TYPECHECK              = PASS
OFFLINE_TEST_COUNT     = 608 (34 files)
NEW_TEST_COUNT         = 5 (uptake01Reconstruction.test.ts)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 603 preserved)
PRODUCTION_BUILD       = PASS
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200 (left running)
TRUE_3D_SPATIAL_FOUNDATION_CHANGED = NO
LEGACY_RANGE_RECTANGLE_PHYSICAL_AUTHORITY = NO
PHYSICAL_OBJECT_SPATIAL_AUTHORITY = BIM_WORLD · CAMERA_ROLE = OBSERVER_ONLY · SCREEN_SPACE_PHYSICAL_AUTHORITY = NO
NEW_CLINICAL_ASSIGNMENTS_CREATED = 0 · MULTI_VOLUME_COMPOSITION_RESUMED = NO
EQUIPMENT_PIPELINE_CHANGED = NO · NAVIGATION_ARCHITECTURE_CHANGED = NO
TRANSPORT_MODE_IMPLEMENTATION_STARTED = NO
PATIENT_ANIMATION_IMPLEMENTED = NO · CARRIER_ANIMATION_IMPLEMENTED = NO
SIMULATION_CHANGED = NO · ECONOMIC_MODEL_CHANGED = NO
BENTLEY_WRITE_API_CALL_COUNT = 0 · IMODEL_MODIFIED = NO
PERMANENT_AUTO_SEED_IMPLEMENTED = NO · RECONSTRUCTION_TRIGGER_AUTOMATIC = NO
UPTAKE_01_AUTO_LOCKED = NO
```

Offline tests: authorized reconstruction from empty (baseline geometry, DRAFT,
visible), duplicate guard (idempotent, same stable ids), reload roundtrip (id +
geometry preserved, re-run is no-op), iModel isolation, no auto-lock — all PASS.

---

## 5. LIVE STEPS (run once in the browser)

The runtime reconstruction + persistence + reload + containment recompute execute
in the browser (localStorage is not reachable from the build environment):

1. Developer → BIM AUDIT DIAGNOSTICS → **RECONSTRUCT UPTAKE 01 BASELINE** (once).
   It creates the assignment + DRAFT volume and persists them; reports the ids.
2. **DIAGNOSE CLINICAL PROGRAM PERSISTENCE** — expect `RUNTIME_ASSIGNMENT_COUNT = 1`,
   `RUNTIME_PLANNING_VOLUME_COUNT = 1`, `CURRENT_ASSIGNMENT_STORAGE_PRESENT = YES`
   (recordCount 1), `CURRENT_VOLUME_STORAGE_PRESENT = YES` (recordCount 1),
   `UPTAKE_ASSIGNMENT_FOUND_CURRENT = YES`, `UPTAKE_VOLUME_FOUND_CURRENT = YES`.
3. **DIAGNOSE CLINICAL PLANNING VOLUMES** — one entry "Uptake 01", DRAFT, visible,
   center (-9.84, 30.53), 4×3×3, yaw 0.
4. Reload /viewer — counts stay 1/1; reconstruction is NOT repeated. The
   `DIAGNOSE UPTAKE 01 PLANNING VOLUME` diagnostic recomputes containment from the
   live authoritative IfcSpace mesh (expected historically INSIDE 21/21 — reported
   honestly, not hard-coded; auto-lock not performed).

```
POST_RELOAD_ASSIGNMENT_COUNT / POST_RELOAD_PLANNING_VOLUME_COUNT = 1 / 1 (verify live)
POST_RELOAD_CONTAINMENT_RESULT = <live: expected PASS 21/21; recomputed, not hard-coded>
POST_RECOVERY_PERSISTENCE_DIAGNOSTIC / POST_RECOVERY_MULTI_VOLUME_DIAGNOSTIC = PASS (verify live)
RECONSTRUCTED_STATE_IMODEL_SCOPED = YES
```

`CHECKPOINT = HOLD_FOR_RECONSTRUCTED_UPTAKE_01_MANUAL_ACCEPTANCE`

STOP. Do not resume multi-volume composition. Do not stage/commit/push.

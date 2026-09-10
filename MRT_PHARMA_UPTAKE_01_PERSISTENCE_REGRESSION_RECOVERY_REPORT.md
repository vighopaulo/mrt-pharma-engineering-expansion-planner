# MRT PHARMA — UPTAKE 01 PERSISTENCE REGRESSION DIAGNOSTIC + SAFE RECOVERY

Diagnostic-first task. The Clinical Program panel reported 0 assignments / 0
planning volumes after the multi-volume generalization. This build adds a
read-only persistence diagnostic + pure classifier, fixes the one statically
provable code defect (volume empty-overwrite / hydration race), and does NOT
synthesize Uptake 01 from remembered values. The frozen spatial foundation is
unchanged.

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
MANUAL_UPTAKE_01_REGRESSION = FAIL
ACTIVE_IMODEL_CORRECT = YES (36381ef4-b5f5-4d6d-b64b-2dbd69ba26a4)
EXPECTED_ASSIGNMENT_COUNT = 1 · ACTUAL_ASSIGNMENT_COUNT_PRE_RECOVERY = 0
EXPECTED_PLANNING_VOLUME_COUNT = 1 · ACTUAL_PLANNING_VOLUME_COUNT_PRE_RECOVERY = 0
VISIBILITY_FAILURE = NO · STOREY_FILTER_FAILURE = NO · ACTIVE_BIM_FAILURE = NO
```

---

## 2. PERSISTENCE CHAINS TRACED (from code)

```
CURRENT_ASSIGNMENT_STORAGE_KEY_PATTERN = mrtpharma.clinicalProgram.v1.<iModelId>
CURRENT_VOLUME_STORAGE_KEY_PATTERN     = mrtpharma.clinicalVolume.v1.<iModelId>
```

Assignment chain: `assignClinicalFunction` → `toSafeProgramPayload` →
`saveProgramAssignments` (key above) → reload → `loadProgramAssignments` →
`isSafeProgramPayload` → `programState.assignments`. This module was frozen; its
allowlist is unchanged, so a well-formed persisted assignment is not rejected by
a code change.

Volume chain: define/update → `saveClinicalVolumes` (`clinicalVolume.v1`) →
reload → `loadClinicalVolumes` → `isSafeVolumePayload` → `planningVolumes`.

```
HISTORICAL_ASSIGNMENT_KEY_PATTERNS = mrtpharma.clinicalProgram.v1.<iModelId> (only v1 present in tree)
HISTORICAL_VOLUME_KEY_PATTERNS     = mrtpharma.clinicalVolume.v1.<iModelId> (only v1 present in tree)
HISTORICAL_PERSISTENCE_KEYS_SEARCHED = YES
```

No pre-v1 key names exist in the working tree — so a key/version migration is not
the code-level cause; if data is missing it is either a browser-storage state
issue or the runtime empty-overwrite race below.

---

## 3. PROVEN CODE DEFECT FIXED (empty-overwrite / hydration race)

`loadClinicalProgramForIModel` set `planningVolumes = []` synchronously, then
hydrated volumes ASYNC via a dynamic import. Any `persistPlanningVolumes()` call
in that window (or a stale async bind after a fast BIM switch) could write `[]`
into the active key — an empty-overwrite.

Fix (minimum, proven):
- Added a `planningVolumesHydrated` gate. `persistPlanningVolumes()` no-ops until
  the active iModel's volumes have loaded (`PERSISTENCE_SAVE_BEFORE_HYDRATION = PROHIBITED`).
- `loadPlanningVolumesForIModel` resets the gate, and on async completion binds
  ONLY if `programState.iModelId` still matches the requested id (LOAD → BIND →
  then allow writes; `IMODEL_SWITCH_PERSISTENCE_ORDER = LOAD_BIND_THEN_WRITE`).

Assignments load synchronously and were not part of this race; their loss (if any)
must be confirmed by the live diagnostic against the actual browser storage.

```
EMPTY_STATE_OVERWRITE_PATH_AUDITED = YES
ASSIGNMENT_VOLUME_HYDRATION_ISOLATION = YES (separate keys, separate load paths)
PERSISTENCE_RECOVERY_SCOPE = MINIMUM_PROVEN_FIX
```

---

## 4. DIAGNOSTIC + CLASSIFIER

- Pure `classifyClinicalPersistenceRegression(...)` (`clinicalPersistenceDiagnostic.ts`)
  → one primary class with evidence precedence; `recoveryActionForClass(...)`.
- Read-only live diagnostic `diagnoseClinicalProgramPersistence()` +
  `DIAGNOSE CLINICAL PROGRAM PERSISTENCE` button (proven dismissible panel). It
  scans ONLY `mrtpharma.clinicalProgram.*` / `mrtpharma.clinicalVolume.*` keys,
  reports counts/parse-status/target-space presence (never full payloads or
  tokens), and emits the classification + recovery action.

```
CLINICAL_PERSISTENCE_DIAGNOSTIC = IMPLEMENTED
PERSISTENCE_DIAGNOSTIC_SECRET_SAFE = YES
PERSISTENCE_REGRESSION_CLASSIFIER = IMPLEMENTED (offline-testable)
```

The live class (`PERSISTENCE_REGRESSION_CLASS`) and the current/legacy target-space
findings are reported by the button against the actual browser — they cannot be
read from the build environment. Run it once to obtain:
`CURRENT_ASSIGNMENT_STORAGE_PRESENT`, `CURRENT_ASSIGNMENT_RECORD_COUNT`,
`UPTAKE_ASSIGNMENT_FOUND_CURRENT/LEGACY`, `UPTAKE_VOLUME_FOUND_CURRENT/LEGACY`,
`PERSISTENCE_REGRESSION_CLASS`, `RECOVERY_ACTION`.

---

## 5. RECOVERY POLICY (evidence-based; no synthesis)

- `CURRENT_STORAGE_HAS_DATA_LOADER_FAILED` → fix loader/schema (data untouched).
- `LEGACY_STORAGE_HAS_RECOVERABLE_DATA` → one-time idempotent migration preserving
  stable ids (none present in this tree, so N/A unless the browser holds pre-v1 keys).
- `PERSISTED_STATE_GENUINELY_ABSENT` → `RECONSTRUCTION_REQUIRED`; STOP and wait for
  explicit user approval. Do NOT auto-reconstruct from remembered values.

```
AUTO_RECONSTRUCT_WHEN_PERSISTED_DATA_ABSENT = NO
RECONSTRUCTION_REQUIRES_USER_APPROVAL = YES
MANUAL_VALUES_USED_AS_SYNTHETIC_PERSISTENCE = NO
UPTAKE_01_RECREATED_BEFORE_DIAGNOSIS = NO
RECOVERY_MUTATES_PERSISTED_GEOMETRY = NO · RECOVERY_AUTO_LOCKS_VOLUME = NO
UPTAKE_01_DUPLICATED = NO · NEW_CLINICAL_ASSIGNMENTS_CREATED = 0
```

If the live diagnostic shows the records ARE present in the current key but
runtime is empty, the hydration-race fix + a browser reload should restore them
(`CURRENT_DATA_LOADER_FAILURE_POLICY = FIX_LOADER_NOT_DATA`). If genuinely absent,
recovery is `RECONSTRUCTION_REQUIRED` (user decision).

---

## 6. VERIFICATION

```
TYPECHECK              = PASS
OFFLINE_TEST_COUNT     = 603 (33 files)
NEW_TEST_COUNT         = 9 (clinicalPersistenceDiagnostic.test.ts)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 594 preserved)
PRODUCTION_BUILD       = PASS
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200 (left running)
TRUE_3D_SPATIAL_FOUNDATION_CHANGED = NO
EQUIPMENT_PIPELINE_CHANGED = NO · NAVIGATION_ARCHITECTURE_CHANGED = NO
TRANSPORT_MODE_IMPLEMENTATION_STARTED = NO
PATIENT_ANIMATION_IMPLEMENTED = NO · CARRIER_ANIMATION_IMPLEMENTED = NO
SIMULATION_CHANGED = NO · ECONOMIC_MODEL_CHANGED = NO
BENTLEY_WRITE_API_CALL_COUNT = 0 · IMODEL_MODIFIED = NO
```

Classifier tests: current-loader-failure (+parse-fail), legacy-recovery, genuinely-
absent, partial-assignment, partial-volume, no-failure, recovery-action mapping — PASS.

---

## 7. STATUS

`PERSISTENCE_REGRESSION_CLASS`, `RECOVERY_ACTION`, and all `UPTAKE_*_FOUND_*` /
`POST_RECOVERY_*` fields are obtained by clicking **DIAGNOSE CLINICAL PROGRAM
PERSISTENCE** in the running app (browser localStorage is not reachable from the
build environment). The hydration-race fix prevents further empty-overwrites. No
Uptake 01 record was recreated or mutated.

`CHECKPOINT = HOLD_FOR_PERSISTENCE_RECOVERY_MANUAL_ACCEPTANCE`

STOP. Do not resume multi-volume composition. Do not stage/commit/push.

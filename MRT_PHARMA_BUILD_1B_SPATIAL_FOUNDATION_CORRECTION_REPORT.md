# MRT Pharma — Build 1B Spatial-Foundation Correction — Verification Checkpoint

**Continues:** the current Build 1B working tree only. Does not begin Build 2.
**Precheck:** HEAD = origin/main = `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3`,
divergence `0 0` (the committed Build 1A baseline is preserved). Build 1B equipment
+ spatial-correction work is present uncommitted. `frontend/.env` unstaged/excluded.

This is a VERIFICATION + dev-server checkpoint: no source was changed in this step.
Every value below was independently re-run here (not taken on faith).

## 1. Git scope (final review)

- **BUILD_1A_COMMITTED_BASELINE_PRESERVED = YES** (HEAD/origin/main = `1de2c5b0…`,
  divergence `0 0`).
- **CURRENT_BUILD_1B_EQUIPMENT_WORK_PRESERVED = YES** — uncommitted working tree:
  - New source: `frontend/src/components/spatial/canonicalEquipmentCatalog.ts`,
    `clinicalRoomCandidate.ts`, `clinicalRoomReparent.ts`, `equipmentInstance.ts`,
    `equipmentValidation.ts`, `targetedWalkthroughSpawn.ts`.
  - New tests: `frontend/src/tests/build1bEquipmentBinding.test.ts`,
    `build1bEquipmentBindingUi.test.tsx`, `build1bSpatialCorrection.test.ts`.
  - Modified (frontend): `CameraModeControl.tsx`, `ClinicalProgramControl.tsx`,
    `ClinicalProgramDecorator.ts`, `spatialAssetOverlay.ts`, `walkthroughController.ts`,
    `LiveItwinViewer.tsx`, `routes/BentleyViewer.css`, `routes/BentleyViewer.tsx`,
    `tests/build1a4ContainmentValidationUi.test.tsx`.
  - Reports: `MRT_PHARMA_BUILD_1B_CLINICAL_PROGRAM_EQUIPMENT_BINDING_REPORT.md`
    + data JSON (prior Build 1B report, preserved) and this correction report pair.
- **BUILD_2_STARTED = NO.**
- **PYTHON_FILES_CHANGED = 0** (no backend/domain `.py` touched).
- **FRONTEND_ENV_STAGED = NO** · **FILES_STAGED = NO** · **COMMIT_CREATED = NO** ·
  **PUSH_PERFORMED = NO.**

## 2. Automated verification (independently re-run)

- **TYPECHECK = PASS** (`tsc -b`, exit 0).
- **OFFLINE_TEST_FILE_COUNT = 54** · **OFFLINE_TEST_COUNT = 910** ·
  **OFFLINE_TEST_REGRESSIONS = 0** (clean isolated `vitest run`; not concurrent
  with the build).
- **PRODUCTION_BUILD = PASS** (`tsc -b && vite build`; only the known harmless
  `INEFFECTIVE_DYNAMIC_IMPORT` + chunk-size advisories).
- **CORE_FRONTEND_VERSION = 5.12.5.**
- **WORKER_ASSET_REAL = YES** (`dist/scripts/parse-imdl-worker.js` head
  `(()=>{"use strict";f`).
- **DRACO_WASM_ASSET_REAL = YES** (`dist/scripts/draco_decoder.wasm` magic
  `0061 736d`).
- **VIEWER_HTTP_STATUS = 200** (dev server restarted fresh on port 3000; Vite
  ready; `/viewer` returns 200 and is left running for manual acceptance).

## 3. Checkpoint

Nothing staged, committed, or pushed. The dev server is running for manual
acceptance of the Build 1B spatial-foundation + equipment-binding work.

**CHECKPOINT = HOLD_FOR_BUILD_1B_MANUAL_ACCEPTANCE.**

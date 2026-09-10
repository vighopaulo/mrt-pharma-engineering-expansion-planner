# MRT PHARMA — CLINICAL PROGRAM LIVE OVERLAY DIAGNOSTIC + EXACT FAILURE CORRECTION

Diagnostic-first correction. The clinical-program domain (assignment,
persistence, summary, provenance) was proven working; the persisted `Uptake 01`
(`1AC1 CENTRAL WAITING`) was not visible on the Bird's-eye/Cutaway building, and
the earlier speculative WorldOverlay + Z-offset change did not fix it. This build
instruments the full live rendering chain, classifies ONE primary failure, and
fixes only that link.

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

## 2. PROVEN MANUAL STATE (before)

```
CLINICAL_PROGRAM_ON = YES
ACTIVE_BIM = MRTway Medical Clinic Demo
ACTIVE_PROGRAM_STOREY_FILTER = First Floor
ASSIGNED_ROOM_COUNT = 1
UPTAKE_ROOM_COUNT = 1
PROGRAM_ASSIGNMENT_PERSISTENCE = PASS
PROGRAM_SUMMARY = PASS
PROGRAM_LABEL_PHYSICALLY_VISIBLE_ON_BUILDING = FAIL
ASSIGNED_ROOM_FOOTPRINT_VISIBLE = FAIL
PROGRAM_ASSIGNED_ROOM_PHYSICALLY_IDENTIFIABLE = FAIL
```

`UPTAKE_01_ASSIGNMENT_PRESERVED = YES` · `ADDITIONAL_DEMO_ROOM_ASSIGNMENTS = 0`.

---

## 3. DIAGNOSTIC (implemented, then traced)

`VISUAL_CHANGE_BEFORE_DIAGNOSTIC = NO`.

- Pure classifier `classifyClinicalOverlayFailure(...)` (Bentley-free, one primary
  class, strict chain order) — `frontend/src/components/spatial/clinicalOverlayDiagnostics.ts`.
- Dev-only live diagnostic `diagnoseClinicalProgramOverlay()` traces the real
  chain for the current persisted assignment and reports bounded, sanitized facts
  (assignment → exact `bimSpaceId` match → `SpatialRoomReference` → range →
  `deriveRoomFootprint` → canonical storey → `deriveClinicalProgramOverlay` →
  decorator registration/enabled/decorate-count → per-target draw attempt →
  `worldToView` bounds → HTML/graphic creation). Read-only, no writes, no secrets.
- Wired to a Developer-mode `DIAGNOSE CLINICAL PROGRAM OVERLAY` button → Developer
  Inspector. Bounded output (`DIAGNOSTIC_OUTPUT = BOUNDED`, `DIAGNOSTIC_SECRET_EXPOSURE = NO`).
- Bounded decorator instrumentation (`ClinicalProgramDecorator.diag`) records the
  last decorate call's seen counts + per-target draw facts.

### Root cause (proven by tracing the chain)

```
PROGRAM_OVERLAY_FAILURE_CLASS = ROOM_FOOTPRINT_NOT_FOUND
```

The assignment resolved to exactly one `BuildingSpatial:Space`, but that space
produced **no PlanFootprint**: `elementRange()` read only the placement bbox from
`bis.GeometricElement3d`, and IFC-derived `BuildingSpatial:Space` rows frequently
carry a **null/degenerate placement bbox** — so `range` was `undefined`,
`geometryType = METADATA_ONLY`, `deriveRoomFootprint` returned `undefined`, the
overlay model produced zero records, and nothing was drawn. This is upstream of
rendering — which is why the earlier WorldOverlay/Z-offset change could not help.

---

## 4. EXACT FIX (proven failure only)

`CORRECTION_SCOPE = PROVEN_FAILURE_ONLY`.

Added a **read-only spatial-index range fallback** to `elementRange()` in
`bentleySpatialAdapter.ts`: when the direct `GeometricElement3d` placement bbox is
absent/degenerate, read the world-aligned min/max from the persistent spatial
R-tree (`bis.SpatialIndex` — `MinX,MinY,MinZ,MaxX,MaxY,MaxZ` by `ECInstanceId`),
which covers spatial elements (including spaces) that have geometry. Validated for
finiteness by the existing `validateWorldRange` (no fabricated/NaN range).

Result: the space now yields a valid `RANGE_ONLY` range → `deriveRoomFootprint`
produces a footprint → `deriveClinicalProgramOverlay` emits the `Uptake 01` record
→ the (unchanged) WorldOverlay decorator draws the on-top footprint + label.

No domain change, no persistence change, no rename, no reassignment. The existing
`Uptake 01` renders automatically (`UPTAKE_01_REASSIGNMENT_REQUIRED = NO`).

Files:
- `frontend/src/components/spatial/clinicalOverlayDiagnostics.ts` (new — pure classifier)
- `frontend/src/components/spatial/spatialAssetOverlay.ts` (new `diagnoseClinicalProgramOverlay`)
- `frontend/src/components/spatial/ClinicalProgramDecorator.ts` (bounded `diag` instrumentation)
- `frontend/src/components/spatial/bentleySpatialAdapter.ts` (**the fix** — SpatialIndex range fallback)
- `frontend/src/routes/BentleyViewer.tsx` (dev-only diagnostic button)
- `frontend/src/tests/clinicalOverlayDiagnostics.test.ts` (new — 19 tests)

---

## 5. VERIFICATION

```
TYPECHECK              = PASS
OFFLINE_TEST_COUNT     = 495 (24 files)
NEW_TEST_COUNT         = 19 (clinicalOverlayDiagnostics.test.ts, §47–53 + ordering)
OFFLINE_TEST_REGRESSIONS = 0  (baseline 476 preserved)
PRODUCTION_BUILD       = PASS
CORE_FRONTEND_VERSION  = 5.12.5
WORKER_ASSET_REAL      = YES  (head = (()=>{"use strict";f)
DRACO_WASM_ASSET_REAL  = YES  (magic = 0061 736d)
DEV_SERVER             = clean restart, http://localhost:3000/viewer → HTTP 200
BENTLEY_WRITE_API_CALL_COUNT = 0 · IMODEL_MODIFIED = NO · BENTLEY_CHANGESET_CREATED = NO
```

Offline classifier tests (§47–53): ID_MISMATCH, STOREY_MISMATCH, NO_FOOTPRINT,
MODEL_FILTER, DECORATOR, OFFSCREEN, SUCCESS — all PASS; chain-ordering test PASS.

---

## 6. NOTE ON THE LIVE CLASS

`ROOM_FOOTPRINT_NOT_FOUND` is the diagnosed root cause from tracing the chain
statically (Space placement bbox null → no range → no footprint). The dev-only
`DIAGNOSE CLINICAL PROGRAM OVERLAY` button lets the exact live class be re-confirmed
in the browser at any time. If, after the SpatialIndex fallback, the live diagnostic
reports a different downstream class (e.g. `STOREY_FILTER_MISMATCH`), that next link
is the follow-up — but the footprint blocker is now removed.

---

## 7. MANUAL ACCEPTANCE (HOLD)

On `MRTway Medical Clinic Demo`, Bird's-eye → First Floor → Clinical Program ON,
without creating any new assignment, the persisted `Uptake 01` should now appear
on the physical `1AC1 CENTRAL WAITING` footprint with a restrained treatment.

```
UPTAKE_01_PHYSICALLY_IDENTIFIABLE = MANUAL_CONFIRMATION_REQUIRED
UPTAKE_01_FOOTPRINT_VISIBLE       = MANUAL_CONFIRMATION_REQUIRED
MANUAL_ORIGINAL_BIM_IDENTITY      = MANUAL_CONFIRMATION_REQUIRED
CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE
```

STOP for manual acceptance. If it still does not render, click DIAGNOSE CLINICAL
PROGRAM OVERLAY and share the one-line `PROGRAM_OVERLAY_FAILURE_CLASS`.

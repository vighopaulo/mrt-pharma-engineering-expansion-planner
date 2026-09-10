# MRT Pharma — Build 1A.4: Product-Facing Containment Safety + Validation UX

**Continues:** Build 1A + 1A.1 + 1A.2 + 1A.3 (uncommitted working tree). Does not
restart 1A or begin 1B. **Precheck:** HEAD = origin/main =
`344d0289723e873c7a2974d0d8d295b38f44a6a3`, divergence `0 0`; 1A→1A.3 preserved;
`frontend/.env` unstaged/excluded. **Nature:** frontend validation-UX + pure/UI
tests. No backend/domain change; no Bentley writes; no stage/commit/push.

## 1. Accepted prior evidence (containment engine manually proven)

Injection Room 01 (parent `1DC1 WAITING / ACTIVITY AREA`, bimSpaceId
`0x200000001f6`, `EXACT_SPACE_GEOMETRY`): auto-seed ≈ (-31.995513506, 32.090989349,
14.234, 4.17175, 0, 3, 0) → containment PASS 21/21; a deliberate X≈-10.995513506 →
FAIL 21/21 outside, Lock disabled; zero-sample never a false FAIL. The engine is
proven. Build 1A.4 turns containment into a **product validation experience** so a
normal user never needs developer diagnostics.

## 2. Product safety principle

`CONTAINMENT_FAILURE_CLASS = USER_CORRECTABLE_VALIDATION_STATE`. A failure is a
validation state, never a crash / exception / developer-only / Bentley-geometry
failure. `CONTAINMENT_FAILURE_CRASHES_APPLICATION = NO`.

## 3. What changed

- **NEW pure model** (`bimRoomVolumeRegistry.ts`): `PlanningVolumeValidationState`
  + `resolvePlanningVolumeValidation` (maps containment PASS/FAIL/NOT_EVALUATED +
  authority quality + last-known-valid presence → `warningCode`/`warningMessage`
  that identifies the room, `isLockAllowed`, `lockDisabledReason`, `restoreAvailable`,
  `technicalDetail` (secondary), `approximateParent`) + `summarizePlanningValidation`
  → `{ planningVolumes, valid, needsAttention, notEvaluated }`. No JSX logic.
- **`clinicalPlanningVolume.ts`**: added `lastKnownValidParams?: PrismParams` to
  the type + the persisted safe-payload allow-list (validated as a prism; an
  invalid one is rejected). Mesh/secret keys still forbidden.
- **`spatialAssetOverlay.ts`**: `getClinicalVolumeContainment` records
  `lastKnownValidParams` on PASS and NEVER overwrites it on FAIL; it also writes a
  per-space `containmentStatusCache` (synchronous invalid cue, iModel-scoped,
  cleared on switch). Added `getPlanningVolumeValidation`,
  `getPlanningValidationSummary`, `restoreValidPosition` (this SAME volume's last
  valid geometry, else a parent-derived seed — never Uptake/another room/origin;
  LOCKED-rejected), `resetToParentDerived` (fresh parent-derived seed;
  LOCKED-rejected). `getPlanningVolumeForSpace` now passes an `invalid` flag.
- **`ClinicalProgramDecorator.ts`**: the planning prism + label take an `invalid`
  flag → red fill/edge PLUS a DASHED edge pattern + thicker outline + a textual
  “⚠ … — OUTSIDE PARENT” label badge with a dashed red border. Not color-only.
- **`ClinicalProgramControl.tsx`**: `refreshVolume` (already recomputes containment
  on every edit) now also pulls the pure validation view model + program summary.
  The editor shows a product warning that identifies the room (technical sample
  detail secondary; raw string moved to Developer mode), an honest NOT_EVALUATED
  line, Lock disabled via `isLockAllowed` + a visible `lockDisabledReason`, and
  Restore Valid Position + Reset to Parent-Derived actions. A validation summary
  reports Valid / Needs attention / Not evaluated. None of this requires Developer
  mode.
- **`BentleyViewer.css`**: `.clinical-program-warning` (dashed red border + icon).

Per-volume isolation: each state is resolved from its own volume; one FAIL never
flags another volume (Uptake unaffected by Injection failure). Invalid DRAFT may
exist but is not lockable and is never promoted; no auto-snap without a user
Restore/Reset action. Persistence: DRAFT geometry (incl. invalid) + last-known-valid
persist; containment is RECOMPUTED after reload (never a stored verdict). Exact
parent authority is used when available; range-only is labeled approximate.

## 4. Offline verification (OFFLINE_VERIFIED)

- TYPECHECK = PASS.
- OFFLINE_TEST_FILE_COUNT = 43 · OFFLINE_TEST_COUNT = 726 · NEW_TEST_COUNT = 24
  (18 pure + 6 UI) · OFFLINE_TEST_REGRESSIONS = 0 (clean isolated run; not
  concurrent with the build).
- PRODUCTION_BUILD = PASS (only harmless INEFFECTIVE_DYNAMIC_IMPORT + chunk-size
  advisories) · CORE_FRONTEND_VERSION = 5.12.5.
- WORKER_ASSET_REAL = YES (`(()=>{"use strict";f`) · DRACO_WASM_ASSET_REAL = YES
  (`0061 736d`).

Pure tests (§28) prove all 20 required properties: PASS→no warning; FAIL→warning
naming the volume; NOT_EVALUATED neither PASS nor FAIL; FAIL disables lock (with
reason); PASS allows lock (lifecycle-gated); warning carries a textual code/message
(not color-only); last-known-valid persists + is rejected if invalid; restore uses
the same volume, reset derives from this parent (never Uptake/origin); invalid
DRAFT editable but not lockable; validation recomputes from current containment;
zero samples ≠ FAIL; exact vs approximate labeled; per-volume isolation + summary.
UI tests (§29) prove (no Developer mode): FAIL shows a room-identifying warning;
Lock disabled + reason visible; Restore + Reset offered; Restore clears the warning
and re-enables Lock; PASS shows the fully-inside line with no warning; summary
reports needs-attention.

## 5. Runtime verification (RUNTIME_VERIFIED)

- Dev server restarted cleanly (Vite ready, `http://localhost:3000/`).
- VIEWER_HTTP_STATUS = 200. Left running for manual acceptance.

## 6. Manual acceptance required (MANUAL_CONFIRMATION_REQUIRED)

Browser-only, not self-certified: valid baseline (§35), invalid edit warning +
no crash (§36), Restore Valid Position (§37), Reset to Parent (§38), multi-volume
warning isolation (§39), then the remaining Build 1A acceptance — camera invariance
(§41), reload persistence (§42), BIM-switch isolation (§43) — and finally the Build
1A completion gate (§44). `BUILD_1A_COMPLETION_GATE = MANUAL_CONFIRMATION_REQUIRED`.

## 7. Authority docs + git scope

Per §46, `MRT_PHARMA_AUTHORITY_INDEX.md` / `MRT_PHARMA_OPEN_GAPS.md` are NOT updated
in this build — Build 1A completion is gated on the full manual acceptance, not on
offline tests. `AUTHORITY_DOCS_UPDATED_ONLY_IF_BUILD_1A_COMPLETE = YES`.

Modified (frontend only): `bimRoomVolumeRegistry.ts`, `clinicalPlanningVolume.ts`,
`spatialAssetOverlay.ts`, `ClinicalProgramDecorator.ts`, `ClinicalProgramControl.tsx`,
`routes/BentleyViewer.css`. New: this report pair + Build 1A.4 tests. Build 1A→1A.3
files preserved. `frontend/.env` untouched. Zero `.py` changed (equipment / routing /
transport / operations / simulation / OpenUSD / NVIDIA / optimization / economics /
What-If / Lockdown untouched). Nothing staged, committed, or pushed. The Injection
baseline is NOT hard-coded in product source (Restore/Reset derive per-volume).

**CHECKPOINT = HOLD_FOR_BUILD_1A4_MANUAL_ACCEPTANCE.**
**NEXT_BUILD (only if Build 1A completion gate passes) = BUILD_1B_COMPLETE_CLINICAL_PROGRAM_AND_EQUIPMENT_BINDING** (not started).

---

### Build 1A provenance chain (preserved)

- Build 1A — generic BIM room-volume activation.
- Build 1A.1 — 200→0 room-discovery lifecycle correction.
- Build 1A.2 — generic diagnostics + exact-geometry inspection.
- Build 1A.3 — storey-filter synchronization.
- Build 1A.4 — product-facing containment validation (this build).

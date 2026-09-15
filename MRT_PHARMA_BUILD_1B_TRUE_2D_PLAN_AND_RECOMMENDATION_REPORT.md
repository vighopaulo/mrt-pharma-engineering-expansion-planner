# MRT Pharma — Build 1B Spatial UX Continuation

## Final Recommendation-Semantic Guard + Synchronized True-2D BIM Plan

**Status:** Implementation complete and verified. **Checkpoint:** `HOLD_FOR_BUILD_1B_TRUE_2D_PLAN_AND_RECOMMENDATION_MANUAL_ACCEPTANCE`. **Completion gate:** `MANUAL_CONFIRMATION_REQUIRED`. No stage / commit / push performed.

Continued from the current working tree only. No restart, no revert, no redesign of accepted work. Authority docs were **not** updated (Build completion remains manual-gated).

---

## Goal A — RECOMMENDED was semantically too permissive

### Root cause
Tier resolution capped RECOMMENDED only for `UNKNOWN` / `GENERIC_OCCUPIABLE` rooms. A room whose label is a *dedicated clinical room word for a different function* (`TECH.OFFICE`, `PROSTH.LAB`, `CERAMIC LAB`) classified as `ENCLOSED_ROOM`, scored clinical suitability `0.7` and, with a good geometric fit (`~1.0`), reached a blended score of `0.82 ≥ 0.75` — so **geometry alone promoted a semantically-unrelated room to RECOMMENDED**.

This violates the doctrine: *geometric fit cannot by itself establish that a room is clinically appropriate* (`ELIGIBLE_EQUALS_RECOMMENDED = NO`).

### Fix (`frontend/src/components/spatial/clinicalRoomCandidate.ts`)
- Exported a pure, testable guard `roomMatchesFunctionAffinity(label, fn)` (plus `getFunctionAffinityTokens(fn)`), the single source of truth for "does the room *name* carry affirmative evidence for **this** clinical function?".
- `resolveCandidateTier` gained a `hasFunctionSemanticEvidence` parameter (fail-closed, defaults to `false`). When it is `false`, the tier is **capped at SUITABLE even when the blended score ≥ `TIER_RECOMMENDED_MIN` (0.75)**.
- `scoreRoomCandidate` computes the evidence flag and a `cappedForNoSemanticEvidence` flag, and appends an honest explanation when a high-scoring room is demoted: *"good geometric fit, but the label carries no affirmative `<FUNCTION>` semantic evidence, so geometry alone cannot recommend it. Recommendation capped at SUITABLE."*
- The numeric `score` is **preserved** for within-tier ranking; the two axes (`0.6·clinicalSuitability + 0.4·geometricFit`) remain independent.
- `RankedRoomCandidate` gained `hasFunctionSemanticEvidence` and `cappedForNoSemanticEvidence`. The existing `ClinicalProgramControl` UI renders `c.reasons` and the tier badge from `c.tier`, so the capped SUITABLE result and its explanation surface automatically — no UI change was needed.

### Behavior now
| Room label (for UPTAKE_ROOM) | Before | After |
|---|---|---|
| `Uptake 01` / `Recovery` (function match) | RECOMMENDED | RECOMMENDED (unchanged) |
| `1DC1 WAITING / ACTIVITY AREA` | SUITABLE | SUITABLE (unchanged) |
| `TECH.OFFICE` / `PROSTH.LAB` / `CERAMIC LAB` | **RECOMMENDED (defect)** | **SUITABLE (capped, explained)** |
| `Corridor` / `Toilet` / `Stair` | REJECTED | REJECTED (unchanged) |

---

## Goal B — TRUE 2D BIM floor plan, simultaneous with the 3D Walkthrough

A real orthographic (top-down) plan is now rendered **at the same time** as the first-person Walkthrough. It is **not** a bird's-eye 3D camera reused as a plan (`BIRDS_EYE_USED_AS_2D_PLAN = NO`).

### Shared identity, no duplicate stores
Every plan element is keyed by `bimSpaceId` — the same identity the 3D scene, assignments, planning volumes and equipment already use. The plan reads the existing authorities; it creates no second spatial/equipment/walker store.

- **Walker state (single source).** `walkthroughController.ts` gained `WalkthroughState`, `getWalkthroughState()`, and `subscribeWalkthroughState(listener)`. A `notifyWalkState()` fires at the end of `applyCamera` (every move/look/turn/FOV update) and on exit. The rAF step loop already calls `applyCamera` each frame, so the plan's walker marker tracks the 3D camera live. There is **no duplicate walker-position store** (`DUPLICATE_WALKER_POSITION_STORE = NO`).
- **Pure projection.** `bim2dPlanProjection.ts` (`projectBim2dPlan`) joins rooms + assignments + candidate tiers + equipment envelopes + walker into one flat XY view-model. It **prefers the exact extracted footprint** (`EXACT_ROOM_MESH`) and falls back to the BIM range rectangle **tagged honestly** as `BIM_RANGE_APPROXIMATION` (dashed in the UI) — approximations are never presented as exact.
- **Overlay seam.** `spatialAssetOverlay.getBim2dPlanView(...)` gathers the inputs from the existing authorities and calls the pure projection. The walker read-model is passed in by the panel (which subscribes to the single controller state), keeping the accessor synchronous and duplication-free.

### The panel (`Bim2dPlanPanel.tsx`, mounted as `viewer-plan-bar`)
- Rendered as a lazy sibling bar in `BentleyViewer.tsx`, bottom-left, **simultaneous** with the Walkthrough.
- Collapsible; Fit / zoom / pan are **view-only** (they change only the 2D viewport transform).
- Clicking a room **selects the same `bimSpaceId`** (drives the existing program selection and fits the 3D view) and **never moves the walker**.
- "Enter Walkthrough Here" reuses the safe clinical-room spawn (`enterWalkthroughAtClinicalRoom`) — never a plan teleport.
- Honest provenance line shows exact vs approximate room counts, equipment count, and whether the walker is live.

---

## Verification

| Check | Result |
|---|---|
| `npx tsc -b` | PASS (exit 0) |
| `npm run test` (vitest, isolated) | **57 files / 969 tests / 0 failures / 0 regressions** |
| `npm run build` | PASS (exit 0) |
| Worker `dist/scripts/parse-imdl-worker.js` | head `(()=>{"use strict";f` |
| Draco WASM `dist/scripts/draco_decoder.wasm` | magic `0061 736d` |
| `@itwin/core-frontend` | `5.12.5` |
| Dev server `npm run dev -- --port 3000` | clean start; `GET /viewer` → **200** |

Tests added: `build1bSpatialCorrection.test.ts` §A (10 props, plus 2 pre-existing assertions corrected to the new doctrine); `build1bPlan2d.test.ts` (19 pure props); `build1bPlan2dUi.test.tsx` (10 UI props).

> Build note: `npm run build` prints pre-existing `INEFFECTIVE_DYNAMIC_IMPORT` chunking warnings; a new one now names `equipmentInstance.ts` because the overlay statically imports `buildEquipmentEnvelope`. These are cosmetic bundler chunking hints, not errors, and match the existing pattern for `bimRoomVolumeRegistry.ts` / `clinicalProgramOverlay.ts`.

---

## Git scope (reviewed, nothing staged)

- `HEAD == origin/main == 1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3`; divergence `0 / 0`.
- **Nothing staged.** `0` Python files changed. `frontend/.env` remains modified from before this task — **not staged and not touched** by this work.
- New/modified files are exactly the Build 1A/1B application layer + tests + these reports. Authority docs untouched.

## Preserved provenance

Build 1A / 1A.1 / 1A.2 / 1A.3 / 1A.4 and the prior Build 1B work (candidate discovery, equipment binding, spatial-foundation correction) are preserved uncommitted; nothing was reverted. The earlier `walkNav.ts` forward-movement fix remains in the working tree. No Bentley writes, no Build 2 routing, no equipment-acceptance resume, no auto-reparent of Uptake / Injection.

---

## Manual gates — STOP

- `FINAL_RECOMMENDATION_CALIBRATION_MANUAL` → **MANUAL_CONFIRMATION_REQUIRED**
- `TRUE_2D_PLAN_MANUAL` → **MANUAL_CONFIRMATION_REQUIRED**
- `BUILD_1B_COMPLETION_GATE` → **MANUAL_CONFIRMATION_REQUIRED**

Stopping for manual acceptance. No stage / commit / push has been performed.

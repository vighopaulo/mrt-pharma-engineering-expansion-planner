# MRT PHARMA — BUILD 1B — TRUE 2D BIM WALKTHROUGH MAP: FLOOR-GEOMETRY RESTORATION + LIVE WALKTHROUGH PROGRESSION TRAIL

**Checkpoint:** `HOLD_FOR_BUILD_1B_MANUAL_ACCEPTANCE`

Continued from the CURRENT Build 1B working tree only — no restart, no revert, no unrelated redesign, no Build 2. No backend/domain/economics/simulation/routing/transport/operations/OpenUSD/NVIDIA/What-If/Lockdown changes. **0 `.py` files changed. `frontend/.env` untouched (unstaged). Nothing staged, committed, or pushed.**

---

## 1. Scope + doctrine flags recorded

| Flag | Value |
|---|---|
| `WALKER_SINGLE_SOURCE_OF_TRUTH` | **walkthroughController** |
| `PLAN_CAN_MOVE_WALKER` | **NO** |
| `DUPLICATE_WALKER_STORE` | **NO** |
| `DUPLICATE_ROOM_DISCOVERY_SYSTEM` | **NO** |
| `HEADING_EQUALS_TRAIL` | **NO** |
| `CROSS_STOREY_FALSE_CONNECTOR` | **NO** |
| `ALL_BIM_ROOMS_PERMANENTLY_LABELLED` | **NO** |
| `BUILD_1A_AUTHORITY_COMPLETION_DEFERRED` | **YES** |

The 2D plan is a *representation* of the same authoritative BIM facts (joined by `bimSpaceId`); the trail is *visualization-only history* derived from the single walkthrough read-model. Neither can move the walker or create a second room registry.

---

## 2. Observed defects (provenance preserved)

### Defect 1 — BIM FLOOR GEOMETRY REGRESSED TO ZERO
- Runtime evidence (regressed): footer read **`0 rooms · 0 exact · 0 approx (dashed) · walker live`**.
- Prior healthy evidence: **`200 rooms · 2 exact · 198 approx (dashed)`**.
- The floor plan disappeared whenever **CLINICAL PROGRAM = Off**, which is the normal Walkthrough case.

### Defect 2 — WALKER SHOWS POSITION + DIRECTION BUT NOT PROGRESSION
- The 2D plan showed the live position + heading indicator, but **no travelled path** — there was no START → travelled path → CURRENT trail, and it did not grow as the user walked.

---

## 3. Root cause (proven from source)

### Defect 1 (0 rooms)
`getBim2dPlanView()` (in `spatialAssetOverlay.ts`) builds its room list from
`getDiscoveredRoomVolumes()`, which reads `cachedModelSemantics.rooms`. Those
semantics are only populated by `refreshModelSemantics()`. Previously that refresh
was driven **only** by the Clinical Program's discovery effect, which runs **only
while the Clinical Program is enabled**. With Clinical Program Off during
Walkthrough the semantics were never hydrated ⇒ `getDiscoveredRoomVolumes()`
returned `[]` ⇒ the projection produced **0 rooms** — the `200 → 0` regression.

A second latent seam: `getBim2dPlanView` defaulted `storeyId` to
`programState.activeStoreyId` (the **Clinical Program** storey), not the
**walker's** active storey — so even with rooms present the plan could show the
wrong floor relative to where the user is walking (violating §8 storey truth).

### Defect 2 (no trail)
`Bim2dPlanPanel`'s rebuild projected the walker's position + heading on every
walkthrough state update but **kept no history** — there was no app-owned trail
accumulating the walked path.

---

## 4. Changes (frontend-only, minimal, at the first broken seam)

### 4a. New pure module — `frontend/src/components/spatial/walkthroughTrail.ts`
App-owned, Bentley-free, deterministic **WALKTHROUGH PROGRESSION TRAIL**. Derived
**exclusively** from successive authoritative `WalkthroughState` samples; it is
never a movement authority and holds no `@itwin`/DOM/viewport dependency.
- Types: `WalkthroughTrail`, `TrailSegment`, `TrailPoint`, `TrailSample`.
- `emptyTrail()`, `advanceTrail(trail, sample)` (pure — returns a new trail),
  `breakTrailSegment(trail)`, `trailSegmentsForStorey(trail, storeyId)`,
  `trailPointCountForStorey(...)`.
- Constants: `WALKTHROUGH_TRAIL_MIN_STEP_M = 0.5`, `WALKTHROUGH_TRAIL_JUMP_M = 5`.
- **Sampling rules:** append a point only on ≥ `MIN_STEP_M` XY translation
  (turning in place / pitch / FOV produce zero XY translation ⇒ never extend the
  trail); a **storey change** starts a new segment; a **teleport ≥ JUMP_M** starts
  a new segment with **no connector**; a **new session** (active `false → true`)
  starts a new segment but **keeps** prior history; `breakTrailSegment` forces a
  new segment at the next sample (targeted entry / reset).

### 4b. Defect 1 fix — `spatialAssetOverlay.ts`
- Added `ensureBim2dPlanRoomsHydrated()`: triggers the **existing, idempotent,
  in-flight-guarded** `refreshModelSemantics()` **without** enabling the Clinical
  Program, so the ONE room authority is populated for the plan. Creates **no**
  second room-discovery system (§24). No-ops once rooms are present.
- `getBim2dPlanView` storey precedence changed to
  `opts.storeyId ?? (walker.active ? walker.activeStoreyId : undefined) ?? programState.activeStoreyId`
  — while walking, the plan follows the **walker's** storey (§8), not the Clinical
  Program's.

### 4c. Defects 1 + 2 wiring — `Bim2dPlanPanel.tsx`
- On rebuild, if the projection returns **0 rooms**, call
  `ensureBim2dPlanRoomsHydrated()` once (guarded, no loop) then re-project — the
  floor reappears independent of the Clinical Program.
- Added an app-owned `WalkthroughTrail` React state advanced on every
  authoritative walkthrough sample via `advanceTrail` (subset `{active, eye,
  storeyId}`). This is visualization-only and never moves the walker.
- Render the trail **behind** the bright walker marker: one subdued-green
  `polyline` per **active-storey** segment (`trailSegmentsForStorey`) plus a small
  START dot per segment. The heading indicator remains a **separate** bright arrow
  on the marker (`HEADING_EQUALS_TRAIL = NO`). The trail is storey-scoped so there
  is never a false cross-storey connector (`CROSS_STOREY_FALSE_CONNECTOR = NO`).

**Preserved unchanged:** exact-vs-approximate (dashed) footprint provenance and
honest counts; label-density policy (`ALL_BIM_ROOMS_PERMANENTLY_LABELLED = NO`);
room click selects the same `bimSpaceId` and never moves the walker; *Enter
Walkthrough Here* safe spawn; mini-plan UX (no Fit/＋/− toolbar, × close → reopen
chip); candidate recommendation guard; equipment binding.

---

## 5. Tests

### New pure tests — `build1bWalkthroughTrail.test.ts` (§25 sampling, §26 segments)
- §25: empty start; first active sample seeds spawn; append only on ≥ `MIN_STEP_M`;
  turning in place never extends; walked path accumulates; **purity** (input never
  mutated); **determinism**; non-finite eye ignored.
- §26: storey change → new segment; storey-scoped rendering; teleport → new
  disconnected segment; new session → new segment keeping history; session end
  keeps history; `breakTrailSegment` forces a new segment; per-storey point counts.

### New UI tests — `build1bWalkthroughTrailUi.test.tsx` (§29)
- §29a: trail grows as the walker moves (spawn + steps = accepted points); trail is
  drawn **behind** the walker marker with the heading kept separate; turning in
  place / pitch / FOV never extend it.
- §29b: BIM rooms and the walker/trail render **together**; when the plan first
  projects 0 rooms it hydrates **independent of Clinical Program** and the floor
  geometry reappears (regression `0 → N` fixed).

### Existing coverage relied on (unchanged)
- §27 2D room pipeline / projection — `build1bPlan2d.test.ts` (exact vs
  approximate, storey filter, walker marker, provenance, hit-test).
- Clinical room overlay coexistence — `clinicalProgramOverlay.test.ts` /
  `build1bPlan2dUi.test.tsx`.

---

## 6. Verification

| Gate | Result |
|---|---|
| `npx tsc -b` (typecheck) | **PASS** |
| `npm run test` (isolated) | **PASS — 61 files, 1010 tests, 0 failures** (baseline 59/989 + 2 files/21 new) |
| `npm run build` (production) | **PASS** (pre-existing chunk-size / ineffective-dynamic-import advisories only) |
| Worker `head -c 20 dist/scripts/parse-imdl-worker.js` | `(()=>{"use strict";f` ✓ |
| WASM `head -c 4 dist/scripts/draco_decoder.wasm` | `0061 736d` (`\0asm`) ✓ |
| core-frontend version | `5.12.5` ✓ |
| Dev server `/viewer` | **HTTP 200** (stale dev processes stopped; fresh `npm run dev -- --port 3000`) |

---

## 7. Git scope review

- `HEAD` = `origin/main` = `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3`; divergence `0 0`.
- **Nothing staged / committed / pushed.**
- **`.py` files changed: 0.**
- **`frontend/.env`**: modified in working tree, **UNSTAGED** and never staged.
- Build 1A and prior Build 1B work preserved; this task adds `walkthroughTrail.ts`
  + two test files and edits `Bim2dPlanPanel.tsx` and `spatialAssetOverlay.ts`
  (2D-plan seam only). No equipment/routing/transport/operations/simulation/
  OpenUSD/NVIDIA/economics/What-If/Lockdown logic touched.

---

## 8. Build 1B forward requirement recorded (not implemented)

**Equipment containment (Build 1B):** equipment envelopes must be validated for
containment within their parent room's authoritative geometry and surfaced on the
2D plan (PASS/FAIL cue), reusing the existing equipment validation authority — **to
be implemented in a later Build 1B step; recorded here only, not done in this task.**

---

## 9. Deferred / manual gates

- `BUILD_1A_AUTHORITY_COMPLETION_DEFERRED = YES` — Build 1A is **not** marked
  complete in authority docs; that remains manual-gated.
- **STOP for manual acceptance.** Checkpoint `HOLD_FOR_BUILD_1B_MANUAL_ACCEPTANCE`.
  No stage / commit / push.

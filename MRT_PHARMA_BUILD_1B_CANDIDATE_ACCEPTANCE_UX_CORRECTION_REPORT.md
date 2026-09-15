# MRT Pharma — Build 1B Candidate-Room Acceptance UX + Recommendation Calibration Correction

**Checkpoint:** `HOLD_FOR_BUILD_1B_CANDIDATE_MANUAL_ACCEPTANCE`
**Scope:** frontend only. No Build 2. No re-parent of Uptake 01 / Injection Room 01. Equipment work preserved and paused. No stage / commit / push.

---

## 1. Git reconciliation

| Item | Value |
|------|-------|
| HEAD | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| origin/main | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| Divergence (ahead/behind) | 0 / 0 |
| Staged files | none |
| `.py` files changed | 0 |
| `.env` | `M` (unstaged, untouched by this correction, never staged) |
| Committed / pushed | no / no |

The committed Build 1A baseline is intact; all Build 1B work remains uncommitted in the working tree.

---

## 2. Defects and root causes

### A — 25/25 rooms scoring RECOMMENDED

**Root cause.** `recommended` was a binary derivation in `scoreRoomCandidate`:

```
recommended = !semantic.rejectedByDefault && eligibility.eligible
```

Any room that was neither a default-rejected host kind nor geometrically degenerate became RECOMMENDED. Eligible collapsed into recommended, so a whole storey of usable rooms all read RECOMMENDED.

**Fix.** Introduced an explicit acceptance tier:

- `CandidateTier = 'RECOMMENDED' | 'SUITABLE' | 'NEEDS_REVIEW' | 'REJECTED'`
- `resolveCandidateTier()` maps the blended score onto data-driven bands (no fixed quota):
  `TIER_RECOMMENDED_MIN = 0.75`, `TIER_SUITABLE_MIN = 0.55`, `TIER_NEEDS_REVIEW_MIN = 0.30`.
- `recommended` is now **derived** as `tier === 'RECOMMENDED'` (kept for backward compatibility with the existing sort + summary).
- The data determines the tier. RECOMMENDED is a real minority — a dedicated clinical room that matches the target function *and* has usable geometry.

### B — "1DC1 WAITING / ACTIVITY AREA" scoring 100% suitability

**Root cause.** The token `waiting` was in the `ENCLOSED_ROOM` vocabulary, and `scoreClinicalSuitability(ENCLOSED_ROOM)` returned `1.0`. A waiting/activity area therefore earned full clinical-suitability confidence — WAITING was being treated as proof of UPTAKE-room suitability.

**Fix.** Added a new semantic kind `GENERIC_OCCUPIABLE` for enclosed-but-not-dedicated-clinical spaces and moved `waiting / activity / lounge / reception / day room / bay / store / storage / bare "room"` into it. Dedicated clinical words (`exam`, `injection`, `uptake`, `scanner`, `radiopharmacy`, …) stay `ENCLOSED_ROOM`.

- `GENERIC_OCCUPIABLE` → clinical suitability `0.5` (relevant, not proof).
- `GENERIC_OCCUPIABLE` (and `UNKNOWN`) can **never** be RECOMMENDED — their best tier is SUITABLE, dropping to NEEDS_REVIEW when uncertain.

So WAITING no longer means UPTAKE ROOM, and ACTIVITY AREA no longer proves dedicated clinical-room suitability.

### C — candidate list overflow + preview-reparenting risk

**Fix.**

- Candidate results render in a **dedicated bounded scrollable region** (`max-height: 320px; overflow-y: auto`, `role="listbox"`, `data-testid="candidate-results-region"`).
- **Compact cards** show, per candidate: label, tier badge, storey, suitability %, geometric-fit %, area, geometry authority, and concise reasons (expandable).
- **Fit to Room / Enter Walkthrough Here / Use This Room** are always reachable at the bottom of every card (the list itself scrolls).
- **Preview actions never re-parent.** Fit to Room calls `fitViewToClinicalRoom` (camera-only) and Enter Walkthrough Here calls `enterWalkthroughAtClinicalRoom` (spawn-only). Neither calls `reparentClinicalFunction`. Only **Use This Room** re-parents, and a REJECTED/ineligible candidate requires an explicit override checkbox before it will.

---

## 3. Calibration model (pure, deterministic, no fabricated thresholds)

Two independent axes are kept separate (`CONTAINMENT_EQUALS_CLINICAL_SUITABILITY = NO`):

| Semantic kind | Clinical suitability |
|---------------|----------------------|
| ENCLOSED_ROOM, label matches target function | 1.00 |
| ENCLOSED_ROOM, dedicated but a different function | 0.70 |
| GENERIC_OCCUPIABLE (waiting/activity/generic) | 0.50 |
| UNKNOWN (never auto-rejected, never auto-recommended) | 0.45 |
| SERVICE_SUPPORT | 0.15 |
| CIRCULATION / VERTICAL_TRANSPORT / SHAFT / SANITARY / OPEN | 0.05 |

Blended rank: `score = 0.6 · clinicalSuitability + 0.4 · geometricFit`.
Geometric eligibility uses only honest numerical-sanity floors (area / height / plan-dimension) — no fabricated clinical or radiation-safety minimums. UNKNOWN is neither auto-rejected nor auto-recommended.

---

## 4. Verification

| Check | Result |
|-------|--------|
| Typecheck (`npx tsc -b`) | PASS (exit 0) |
| Full isolated suite (`npx vitest run`) | **55 files, 930 tests, 0 failures** |
| Stated baseline | 54 files, 910 tests, 0 failures |
| Delta | +1 test file, +20 tests (tier §18, score-separation §19, UI §20/§21, corrected UNKNOWN + reason wording) |
| Production build (`npm run build`) | PASS (pre-existing chunk-size + INEFFECTIVE_DYNAMIC_IMPORT warnings only) |
| Worker (`parse-imdl-worker.js`) | head = `(()=>{"use strict";f` ✓ |
| WASM (`draco_decoder.wasm`) | magic = `0061 736d` ✓ |
| `@itwin/core-frontend` | 5.12.5 ✓ |
| Dev server restarted, `/viewer` | HTTP **200** |

New tests added:

- **§18 tier** — RECOMMENDED requires matching dedicated clinical semantics + usable geometry; WAITING/ACTIVITY is never RECOMMENDED and never 100% suitability; corridor/degenerate → REJECTED; a dedicated room for a different function scores 0.7; RECOMMENDED is a strict minority across a mixed model; tier appears in reasons; summary tier counts partition the set.
- **§19 score separation** — high geometric fit does not rescue low clinical suitability; the two axes are reported independently; blended score equals `0.6·suitability + 0.4·fit`.
- **§20 UI** — dedicated bounded scrollable region; compact cards show tier + both scores; WAITING card is not recommended; every card exposes reachable Fit to Room / Enter Walkthrough Here / Use This Room.
- **§21 UI isolation** — Fit to Room and Enter Walkthrough Here never call the re-parent bridge; only Use This Room does; a REJECTED candidate is not re-parentable without an override.

---

## 5. Preservation / scope compliance

- Equipment files unmodified: `canonicalEquipmentCatalog.ts`, `equipmentInstance.ts`, `equipmentValidation.ts`. Equipment acceptance remains **paused**.
- Uptake 01 and Injection Room 01 are **not** re-parented.
- Build 2 not started.
- Authority docs **not** updated (Build 1B closure remains manual-gated).
- 0 `.py` files changed. `.env` never staged.

### Files changed this correction

- `frontend/src/components/spatial/clinicalRoomCandidate.ts` — tiers + GENERIC_OCCUPIABLE + per-function suitability + tier counts.
- `frontend/src/components/spatial/ClinicalProgramControl.tsx` — bounded scroll region, compact tier cards, always-reachable inspection/confirm actions.
- `frontend/src/routes/BentleyViewer.css` — tier badge colors + compact-card meta styling.
- `frontend/src/tests/build1bSpatialCorrection.test.ts` — corrected UNKNOWN expectation + §18/§19 tier + score-separation tests.
- `frontend/src/tests/build1bCandidateAcceptanceUi.test.tsx` — new §20/§21 UI tests.

---

## 6. STOP

Held for Build 1B candidate manual acceptance. No stage, commit, or push has been performed.

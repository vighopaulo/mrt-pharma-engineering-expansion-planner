# MRT PHARMA — BUILD 1B.9

## PHYSICS & ECONOMICS INTEGRITY AUDIT REPORT

**Headless transport / production / clinical / economic regression and visualization-decoupling proof.**

- **Build:** 1B.9 (integrity audit — NOT Build 1C, NOT Build 2)
- **Repository:** `mrt-pharma-engineering-expansion-planner`
- **Branch:** `main`
- **HEAD:** `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3`
- **origin/main:** identical (0 ahead / 0 behind)
- **Date:** 2026-09-12
- **Audit posture:** AUDIT-FIRST — classify and report the CURRENT engineering level honestly. Do NOT invent missing physics. A missing physical model is an AUDIT FINDING, not an instruction to build a solver.
- **`manual_acceptance = PENDING`** — this report is NOT self-accepted. Engineering adjudication is required for the items flagged below.

---

## 0. EXECUTIVE SUMMARY

The physics and economics engine of this repository is **genuinely headless**. Every transport, production, clinical, exposure, and economic model imports and executes with **no dependency** on Bentley/iTwin, `IModelApp`, WebGL, decorators, animation clocks, or frame authority. The `frontend/` TypeScript Bentley viewer is a **downstream consumer** of engine outputs, not a participant in any calculation.

The headless engineering test suite reports **5103 passed, 7 failed, 10 skipped** (pre-audit working tree). After analysis, the 7 failures are **all pre-existing and NOT caused by this audit**:

- **5 are STALE_BENCHMARK** (test assertions that lag a genuine, verified engine upgrade — the free-roaming floor AGV/AMR model). These have been **corrected** in this build with documented comments, because the engine change is real and physics-backed.
- **2 are REPORT-ONLY** (require engineering authority to adjudicate whether the benchmark or the engine is canonical). These are **left failing and documented** — the audit charter forbids forcing code back to old numbers or guessing the intended value.

The audit also surfaced one **terminology / multiple-authority** finding around per-endpoint CapEx that supersedes an earlier provisional finding, and confirms the vestibule economic model has **no double-count**.

Physics maturity across the board is **Level-1 (L1) analytic / kinematic / decay-based**. There is **no** electromagnetic solver, no CFD, no dynamic multi-body trajectory integration, and no network-contention queueing solver. Where a physical quantity is genuinely unknown, the engine reports `NOT_CALIBRATED` rather than substituting a fabricated number or a $0 cost. This honesty is preserved and is treated as correct behavior.

---

## 1. HEADLESS PROOF (VISUALIZATION-DECOUPLING)

**Claim:** the physics/economics engine runs with no viewer, no browser, no GPU, and no animation clock.

**Method + evidence:**

1. **Import-graph proof.** Every audited engine module (transport, production/decay, clinical, exposure, economics) was imported in a pure CPython process (`.venv/bin/python`). None import any of:
   - `bentley`, `itwin`, `IModelApp`, `@itwin/*`
   - WebGL / GPU contexts
   - viewer decorators or scene-graph authorities
   - animation / frame-loop modules
2. **Source scan (engine `.py`, excluding `frontend/`).** No occurrence of frame/animation authority primitives in engine physics/econ code:
   - `requestAnimationFrame` — absent
   - `performance.now` — absent
   - `playbackSpeed` — absent
   - frame-loop / render-tick authority — absent
3. **Determinism.** Audited models are pure functions of their inputs: repeated evaluation yields byte-identical results (no wall-clock, no RNG seeded from time, no frame counter).

These three checks are encoded as automated tests in `test_build1b9_physics_economics_integrity_audit.py` (see §7) and **pass**.

**Conclusion:** `HEADLESS = CONFIRMED`. The engine is fully decoupled from visualization.

---

## 2. ENGINEERING MATURITY MATRIX

Legend for maturity level:
- **L1** — analytic / closed-form / kinematic / decay-based model (first-principles algebra, no numeric field solve).
- **DOCUMENTED_NOT_IMPLEMENTED** — the gap is named and disclosed by the engine; no fabricated model exists.
- **NOT_CALIBRATED** — the model form exists but a specific physical quantity is honestly declared uncalibrated rather than guessed.

| # | Domain / Model | Authority module | Maturity | Physical basis | Notes |
|---|----------------|------------------|----------|----------------|-------|
| 1 | Manual porter transport | `conventional_transport_authority.py` (`compute_manual_mission_timing`, `PorterOperatingPolicy`) | **L1 kinematic** | `T = dispatch + load + horizontal(L/speed) + vertical(transitions × elevator_wait) + wait + unload + symmetric return`; speeds 1.4 / 1.1 / 0.9 m/s | Provenance CONTROLLED_ENGINEERING_ASSUMPTION; wage $17/hr ×1.3 |
| 2 | Conventional pneumatic tube (PTS) | `finance.py` (`PneumaticTubeNetwork`) | **L1 kinematic** | speed 6.0 m/s, dispatch 1.0, station handling 1.5 | Distinct from RP-qualified PTS |
| 3 | RP-qualified PTS | `dedicated_rp_pts_authority.py` | **L1 kinematic** | Radiopharmaceutical-qualified dedicated tube; distinct from conventional PTS | Separate authority; not conflated |
| 4 | Rail-guided hospital transport (RGHT, legacy AGV) | `conventional_transport_authority.AgvModelClass` (`technology_class="RGHT"`) | **L1 kinematic** | Rail-guided; `RGHT != FLOOR_AGV_AMR` invariant enforced | Legacy rail model |
| 5 | Free-roaming floor AGV/AMR | `floor_agv_amr_authority.py` | **L1 kinematic — IMPLEMENTED** | light 1.2 m/s + heavy 1.0 m/s profiles; route/mission physics; CapEx/OpEx | Upgraded from NOT_IMPLEMENTED by KIRO Super-Build 1 (see §5 STALE_BENCHMARK) |
| 6 | MRT transport | MRT authorities (`shared_mrt_multistream_authority.py`, `canonical_spatial_authority.py`) | **L1 kinematic ONLY** | Kinematic timing + CapEx/OpEx | **NO electromagnetic / maglev field solver.** Time-of-flight modeled kinematically only |
| 7 | Radionuclide decay (F-18 etc.) | `f18_decay_model.py`, `radionuclides.json` | **L1 decay** | `retention = 2^(-t / T½)`; F-18 T½ = **109.8 min** (canonical) | Independently reproduced — see §6 |
| 8 | Production / end-of-batch (EOB) activity | production authorities | **L1 decay-based** | Decay-driven activity yield | No reactor/target transport-physics solve |
| 9 | Clinical capacity / scheduling | clinical scheduling authorities | **L1 analytic** | Deterministic capacity + intraday scheduling | See §5 report-only item (carrier shortage) |
| 10 | Radiation exposure | exposure authorities | **L1 analytic** | Dose/exposure algebra | No Monte-Carlo particle transport |
| 11 | CapEx | `finance.py`, `models.py`, `equal_budget.py`, `canonical_spatial_authority.py`, `operational_day_orchestrator.py` | **L1 accounting** | Unit-cost × quantity ledgers | Multiple endpoint concepts — see §4 |
| 12 | OpEx | `finance.py`, `equal_budget.py`, infrastructure OpEx modules | **L1 accounting** | Annual recurring ledgers | — |
| 13 | Payback | `finance.py` (`incremental_financials`), `lifecycle_economics.py` (`_payback_year`) | **L1 accounting** | `payback = CapEx / annual_net_cash_flow` else `inf` | Zero/negative-cash-flow edge cases handled |
| 14 | NPV / IRR / ROI | `finance.py` (`incremental_financials`) | **L1 accounting** | `NPV = -CapEx + Σ CF/(1+r)^y`; ROI ratio | Independently reproduced in audit test |
| 15 | Network contention / directionality | (disclosed gap) | **DOCUMENTED_NOT_IMPLEMENTED** | — | Engine explicitly discloses no contention solver (test_36 in build3 suite) |
| 16 | Routed MRT guideway length | `canonical_spatial_authority.build_mrt_trunk` | **NOT_CALIBRATED** | No canonical routed-length resolver yet | Honest: never substituted with $0 cost |

**Summary:** the entire engine sits at **L1 analytic/kinematic/decay/accounting** maturity. This is internally consistent and honestly disclosed. No higher-fidelity physical solver is claimed anywhere, and none is fabricated.

---

## 3. DEPENDENCY DIAGRAM (CURRENT ARCHITECTURE)

```
                         ┌──────────────────────────────────────────────┐
                         │  HEADLESS PHYSICS & ECONOMICS ENGINE (Python)  │
                         │  pure CPython — no GPU, no browser, no clock   │
                         ├──────────────────────────────────────────────┤
   radionuclides.json ──▶│  Decay:      f18_decay_model  (2^(-t/T½))      │
                         │  Transport:  conventional_transport_authority  │
                         │              finance.PneumaticTubeNetwork      │
                         │              dedicated_rp_pts_authority        │
                         │              floor_agv_amr_authority (L1)      │
                         │              shared_mrt_multistream_authority  │
                         │  Spatial:    canonical_spatial_authority       │
                         │  Clinical:   scheduling / capacity authorities │
                         │  Exposure:   dose authorities                  │
                         │  Economics:  finance.incremental_financials    │
                         │              lifecycle_economics               │
                         │              equal_budget / architecture_opt   │
                         └───────────────────────┬──────────────────────┘
                                                 │  deterministic data
                                                 │  (numbers, ledgers, statuses)
                                                 ▼
                         ┌──────────────────────────────────────────────┐
                         │   frontend/  (TypeScript Bentley/iTwin viewer) │
                         │   DOWNSTREAM CONSUMER — visualization only     │
                         │   Reads engine outputs; performs NO physics    │
                         │   or economics computation of its own          │
                         └──────────────────────────────────────────────┘
```

**Direction of dependency is strictly one-way:** engine → viewer. The viewer never feeds back into any physics or economic calculation. Removing the entire `frontend/` directory would not change any engine result (proven by the headless import + determinism tests).

---

## 4. ECONOMIC INTEGRITY & DOUBLE-COUNT AUDIT

### 4.1 Per-endpoint CapEx — TERMINOLOGY / MULTIPLE-AUTHORITY (report, do NOT change)

**Finding (supersedes earlier provisional finding).** The prompt (§25) references "$1,000 per endpoint." The engine contains **three distinct endpoint-cost concepts**, and the $1,000 figure **is present and honored** in two of them:

| Concept | Location | Value | Meaning |
|---------|----------|-------|---------|
| Light-MRT stream endpoint | `shared_mrt_multistream_authority.py:176` `LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT` | **$1,000** | Ordinary light-MRT endpoint; docstring: "same $1,000/endpoint used elsewhere in this benchmark" |
| Room delivery panel endpoint | `operational_day_orchestrator.py:516` `MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD` | **$1,000** | Per-room MRT exit/delivery I/O panel; explicitly distinct from vestibule CapEx |
| Generic optimizer network endpoint/junction | `models.py:30`, `models.py:210` `endpoint_capex` | **$10,000** | Guideway-network endpoint/junction in the equal-budget / architecture optimizer; a different line item, not the light-MRT/room-panel endpoint |

**Classification:** `TERMINOLOGY_MULTIPLE_AUTHORITY` (not a contradiction). The $1,000 endpoint the prompt refers to exists and is used. The $10,000 `endpoint_capex` in `models.py` is a **separately-named** optimizer network-junction cost, not a competing value for the same physical endpoint. **No change made** — the audit charter forbids guessing which figure the reader intended, and there is no actual conflict once the three concepts are distinguished. Flagged for engineering confirmation that the naming is acceptable.

### 4.2 Vestibule CapEx — NO DOUBLE-COUNT (confirmed)

- `canonical_spatial_authority.py:992` `MRT_VESTIBULE_CAPEX_USD = 30_000.0` — USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION, **per vestibule, vestibule-specific only**.
- One vestibule may contain multiple ports (e.g. a large rectangular MRT opening + a small circular PTS opening). **One vestibule = one $30,000 charge**, regardless of the number of ports it exposes. It is NOT two vestibules and is NOT double-charged.
- `shared_mrt_multistream_authority.py` charges vestibule CapEx as `cyclotron_count × MRT_VESTIBULE_CAPEX_USD` — **one vestibule per cyclotron interface requiring MRT transfer**, explicitly **never** tied to radiopharmacy count, floor count, room count, or endpoint count (Build 2R correction, item 54).
- Related once-per-system charges are also confirmed single-charged and non-regressing on length-only changes (`live_engineering_impact_binding.py:597`): `MRT_CONTROLS_CAPEX_USD = 100,000`, `MRT_INSTALLATION_COMMISSIONING_CAPEX_USD = 300,000`.
- The prior build's $43,000 vestibule figure ($25,000 base + $10,000 install + $8,000 integration) is **SUPERSEDED** by the $30,000 canonical figure; no residual double-count from the old decomposition.

**Classification:** `NO_DOUBLE_COUNT — CONFIRMED`.

### 4.3 Payback / NPV / IRR — INDEPENDENTLY VERIFIED

- `payback = CapEx / annual_net_cash_flow` (else `inf` when net cash flow ≤ 0) — reproduced independently in the audit test, including zero/negative edge cases and CapEx monotonicity.
- `NPV = -CapEx + Σ_y CF_y / (1+r)^y` — reproduced independently.
- These formulas are pure accounting algebra (L1). No hidden time/animation dependence.

---

## 5. DEFECT CLASSIFICATIONS (the 7 pre-existing failures)

None of these failures were introduced by this audit. All exist in the working-tree engine as inherited.

### 5.1 STALE_BENCHMARK — CORRECTED (5 tests)

**Root cause:** `transport_technology_authority.py:52` now declares `FLOOR_AGV_AMR_IMPLEMENTATION_STATUS = "IMPLEMENTED"`. This is a **genuine, physics-backed upgrade**: `floor_agv_amr_authority.py` is a real L1-kinematic free-roaming floor AGV/AMR model (light 1.2 m/s + heavy 1.0 m/s profiles, route/mission physics, CapEx/OpEx), authored by KIRO Super-Build 1 as a DISTINCT authority from legacy rail-guided RGHT. The `RGHT != FLOOR_AGV_AMR` invariant still holds.

The five test assertions still expected the old `"NOT_IMPLEMENTED"` status — they lagged a real implementation. Because the engine change is verified and correct, these benchmarks were updated (each with a documented `# BUILD 1B.9 STALE_BENCHMARK: ...` comment):

| File:line (test) | Old assertion | New assertion |
|---|---|---|
| `test_transport_spatial_authority_build1.py` (`test_6_...`) | `== "NOT_IMPLEMENTED"` | `== "IMPLEMENTED"` |
| `test_transport_spatial_authority_build2.py` (`test_3_...`) | `== "NOT_IMPLEMENTED"` | `== "IMPLEMENTED"` |
| `test_transport_spatial_authority_build3.py` (`test_35_...`) | `== "NOT_IMPLEMENTED"` | `== "IMPLEMENTED"` |
| `test_transport_spatial_authority_build4.py` (`test_50_...`) | `== "NOT_IMPLEMENTED"` | `== "IMPLEMENTED"` |
| `test_build3c1_spatial_route_authority.py` (`test_5_rght_lane_identity`) | `== "NOT_IMPLEMENTED"` | `== "IMPLEMENTED"` |

**Post-fix verification:** all five files re-run → **200 passed** (0.60s).

### 5.2 REPORT-ONLY — LEFT FAILING, REQUIRES ENGINEERING AUTHORITY (2 tests)

These are NOT corrected. The audit charter (do not force code to old numbers, do not guess) requires engineering adjudication.

**(a) Generator benchmark row count — suspected STALE_BENCHMARK**
- Test: `test_conventional_economic_calibration_and_intraday_scheduling.py::test_generator_benchmark_uniform_across_initial_models` (line 215).
- Assertion: `assert len(rows) == 3`. **Actual: 4.**
- Cause: the generator catalog grew from 3 to 4 models; the 4th is a "Sodium chloride eluate (variable CapEx)" model. The delivery-cost uniformity portion of the test still holds for the priced models; only the hard-coded count of 3 is stale.
- **Adjudication needed:** confirm the 4th catalog model is intended, then update the count to 4 (and decide whether the variable-CapEx model belongs in the uniform-delivery-cost assertion). This looks like STALE_BENCHMARK but touches an economic catalog, so it is deferred to engineering authority rather than auto-corrected.

**(b) MRT carrier shortage no longer degrades — ENGINEERING_AUTHORITY_CONFLICT / suspected STALE_BENCHMARK**
- Test: `test_full_operational_capital_qualification.py::test_mrt_carrier_shortage_shows_degraded_service` (line 255).
- Assertion: `assert constrained.late + constrained.unmet > 0`. **Actual: 0 late + 0 unmet.**
- Actual outcome at `installed_carriers=7`: `total_missions=212, on_time=212, late=0, unmet=0, max_wait=2.56 min`. The `test_mrt_carrier_shortage_never_auto_expands` companion still passes (`installed_carriers == 7`, no silent expansion), so the model is **not** cheating by auto-scaling the fleet — 7 MRT carriers genuinely satisfy the 212-mission day within timing tolerance.
- **Adjudication needed:** is 7-carrier sufficiency the correct current engineering result (making the "shortage" benchmark stale), or has a regression removed a real degradation mechanism? Because this concerns whether a physical/operational shortfall should manifest, it requires engineering authority and is **not** auto-corrected. Classified `ENGINEERING_AUTHORITY_CONFLICT` pending that ruling.

### 5.3 Environment-conditional exclusions (NOT engine defects)

Excluded from the headless engine run because they depend on external services, not engine correctness (audit charter §66):
- `test_capital_project_api.py` — requires `fastapi` (not installed in this env).
- `test_bim_itwin_phase2b_live_bentley_binding.py` and `test_bentley_live_imodel_proofs.py` / any `-k live_bentley` — require a live Bentley/iTwin binding.

These are `ENVIRONMENT_CONDITION`, not physics/economics defects.

---

## 6. F-18 DECAY — INDEPENDENT VERIFICATION

- **Canonical provenance:** `radionuclides.json` gives F-18 half-life **T½ = 109.8 min**.
- **Engine model:** `f18_decay_model.py` computes `retention_at_delay_minutes(delay) = 2^(-delay / T½)`.
- **Independent check (audit test):** an independently-written `2^(-t/T½)` reference with T½ = 109.8 min reproduces the engine's retention curve across sampled delays to floating-point tolerance. At one half-life (t = 109.8 min) retention = 0.5 exactly; monotonic decreasing; bounded in (0, 1].
- **Result:** `DECAY_MODEL = VERIFIED` (L1 decay, headless, deterministic).

---

## 7. NEW AUDIT TEST SUITE

`test_build1b9_physics_economics_integrity_audit.py` — **13 tests, all passing** (0.14s). Coverage:
1. Headless import proof (physics/econ modules import no viewer/Bentley/animation deps).
2. F-18 decay vs independent `2^(-t/T½)`, T½ = 109.8 min from `radionuclides.json`.
3. Manual L1 kinematic `t = L/v` reproduction + distance/dwell monotonicity.
4. Route status honesty (`ROUTE_CALIBRATED` / `NOT_CALIBRATED`).
5. Payback `= CapEx / net_cash_flow` + zero/negative edge cases + CapEx monotonicity.
6. NPV independent reproduction.
7. Determinism / visualization-free evaluation.
8. No-animation-clock source scan over engine `.py` (excluding `frontend/`).

---

## 8. TEST / BUILD / VIEWER RESULTS

### 8.1 Headless engineering suite
- **5103 passed, 7 failed, 10 skipped** (~16m41s) with environment-conditional exclusions (§5.3).
- Post-audit: the 5 STALE_BENCHMARK failures are corrected (→ would move to **5108 passed, 2 failed**); the 2 report-only failures remain by design pending engineering adjudication.
- Focused headless subsets re-run clean: decay/transport/production/clinical/infra-capex-opex/lifecycle/equal-budget = **430 passed**; architecture/optimizer/four-arch/transport-parity/dedicated-rp-pts = **293 passed +1 skip**; corrected AGV-status files = **200 passed**; new audit suite = **13 passed**.

### 8.2 Frontend (Bentley viewer — downstream consumer, unaffected by this audit)
- Baseline from EVI-MA-07: **82 files / 1274 tests** pass; `npx tsc -b` PASS; `npm run build` PASS; `/viewer` returns **200** on `:3000`.
- This audit made **no** frontend changes; the viewer baseline is unaffected. (Live re-confirmation of `/viewer=200` is a manual step — see §10.)

---

## 9. ENGINEERING_DOCUMENT_UPDATE_REQUIRED

Items requiring an engineering-authority document decision (NOT auto-applied by this audit):

1. **Generator catalog benchmark** — ratify the 4th generator model ("Sodium chloride eluate, variable CapEx") and update `test_generator_benchmark_uniform_across_initial_models` from `== 3` to `== 4`, clarifying whether the variable-CapEx model participates in the uniform-delivery-cost assertion.
2. **MRT carrier shortage benchmark** — rule on whether 7 carriers correctly satisfying 212 missions (0 late / 0 unmet, max wait 2.56 min) is the intended current result (→ retire/adjust `test_mrt_carrier_shortage_shows_degraded_service`) or a regression to investigate.
3. **Endpoint-CapEx terminology** — confirm the three-way naming (light-MRT endpoint $1,000 / room delivery panel $1,000 / optimizer network junction $10,000) is intentional and non-conflicting, and align prompt/documentation wording to the code.
4. **NOT_CALIBRATED disclosures** — decide whether/when to calibrate the routed MRT guideway length resolver (`canonical_spatial_authority.build_mrt_trunk`) and network-contention model; today's honest `NOT_CALIBRATED` / `DOCUMENTED_NOT_IMPLEMENTED` statuses are correct and should remain until a canonical source exists.

---

## 10. UNRESOLVED GAPS / LIMITATIONS

- **No electromagnetic / maglev field solver** for MRT: transport time is modeled kinematically (L1) only. This is disclosed, not hidden.
- **No CFD, no Monte-Carlo particle transport** for exposure; **no dynamic multi-body trajectory integration**; **no network-contention queueing solver** (`DOCUMENTED_NOT_IMPLEMENTED`).
- **Routed MRT guideway length** is `NOT_CALIBRATED` — no canonical routed-length resolver yet; the engine correctly refuses to substitute a $0 cost.
- **Two report-only test failures** (§5.2) remain unresolved pending engineering authority.
- **Live browser confirmation** of the viewer (`/viewer=200`, right-click/selection UX) is a manual step; this headless audit does not exercise the running browser.

---

## 11. MANUAL ACCEPTANCE

**`manual_acceptance = PENDING`**

This audit is a classification-and-report deliverable. It is **NOT self-accepted**. Engineering authority must adjudicate the items in §9 before acceptance.

**Explicitly NOT started (per charter):** Build 1C, Build 2, transport-network routing, and animation. No routing or animation code was written or modified.

---

*End of Build 1B.9 Physics & Economics Integrity Audit Report.*

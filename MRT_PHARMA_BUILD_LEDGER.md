# MRT Pharma — Build Ledger

**Build:** MRT Pharma Authority Consolidation (governance / traceability layer).
**Purpose:** the physical build history for the Capital-Project authority line,
reconstructed from **actual git history** (`git log`) and physical files. No SHAs,
test counts, or documents are invented; where evidence is not physically
recoverable it is marked as such.

**Method:** SHAs from `git log --oneline`; documentation filenames from the
working tree; test-evidence counts are the number of `def test_` functions
physically present in each focused test file (a recoverable lower-bound count of
test functions, not a pass/fail run record). Companion documents:
`MRT_PHARMA_AUTHORITY_INDEX.md`, `MRT_PHARMA_PRODUCT_DOCTRINE.md`,
`MRT_PHARMA_INTEGRATION_ARCHITECTURE.md`, `MRT_PHARMA_OPEN_GAPS.md`.

This document changes **no** production-engine behavior.

---

## 0. Ledger summary (most recent last)

| Build | Commit SHA | Documentation | Focused test file | `def test_` count |
|---|---|---|---|---|
| Build 3A | `9a04dc5` | (in-commit; see 2R report) | `test_build3a2_identity.py` (shared with 3A.2) | 11 (3A.2 identity) |
| Build 3A.2 | `9a04dc5` (sub-identity, no separate SHA) | — | `test_build3a2_identity.py` | 11 |
| Build 3B | `1d557f0` | `CYCLOTRON_PRODUCTION_DATA_AUTHORITY_BUILD_3B.md` | `test_build3b_production_authority.py` | 16 |
| Build 3C | `a42cb08` | `FIVE_MODE_TRANSPORT_AUTHORITY_BUILD_3C.md` | `test_build3c_transport_authority.py` | 45 |
| Build 3C coverage closure | `85b10a7` | (same 3C doc) | `test_build3c_transport_authority.py` | 45 |
| Build 3C.1 | `95040d5` | `SPATIAL_ROUTE_NETWORK_AUTHORITY_BUILD_3C1.md` | `test_build3c1_spatial_route_authority.py` | 34 |
| Part 3D | `07e861d` | `PHYSICAL_FEASIBILITY_AUTHORITY_PART_3D.md` | `test_part3d_physical_feasibility_closure.py` | 46 |
| Authority Consolidation | `b8e759e` | this ledger + INDEX/DOCTRINE/PRODUCT/INTEGRATION/OPEN_GAPS | `test_mrt_pharma_authority_index.py` | (governance) |
| Cyclotron Production Estimation | `9570308` | `CYCLOTRON_PRODUCTION_ESTIMATION_AUTHORITY.md` | `test_cyclotron_production_estimation_authority.py` | 37 |
| Cyclotron Production Evidence & Calibration Extension | uncommitted (current working tree) | `CYCLOTRON_PRODUCTION_EVIDENCE_SOURCES.md` (+ ESTIMATION_AUTHORITY addendum) | `test_cyclotron_production_evidence_extension.py` | 36 |
| Clinical Radionuclide Portfolio Authority (OG-RAD-1) | uncommitted (current working tree; from `28552cd`) | `CLINICAL_RADIONUCLIDE_PORTFOLIO_AUTHORITY.md` | `test_clinical_radionuclide_portfolio.py` | 52 |

> **Note on test counts:** the count is the number of test functions physically
> present in the file. It is a recoverable structural measure, not a re-run pass
> tally. `test_build3a2_identity.py` was introduced in the Build 3A commit
> (`git log --diff-filter=A` confirms `9a04dc5`), so Build 3A.2 is a sub-identity
> **within** the 3A commit and has no separate SHA.

---

## 1. Build 3A — legacy production ranking correction + MRT no-build identity

- **BUILD:** Build 3A.
- **PURPOSE:** correct legacy production ranking and close the MRT no-build
  identity (the do-nothing / `NO_BUILD_BASELINE` outcome of the equal-budget
  MRT-investment search).
- **COMMIT SHA:** `9a04dc5`.
- **DOCUMENTATION:** no dedicated `BUILD_3A.md` in the working tree; the
  four-architecture economic line is documented in
  `FOUR_ARCHITECTURE_BUILD2R_REDERIVATION_REPORT.md` and the
  `four_architecture_economic_report_*.md` set.
- **FOCUSED TEST:** `test_build3a2_identity.py` (introduced in this commit).
- **TEST EVIDENCE:** 11 `def test_` functions physically present.
- **MAJOR AUTHORITY ESTABLISHED:** the `NO_BUILD_BASELINE` identity
  (zero-backbone, `capex_used == 0.0`) as a real computed baseline in
  `equal_budget.py`.
- **KNOWN CARRIED-FORWARD GAPS:** `NO_BUILD_BASELINE` is a legacy Build-3A
  identity, **not** a first-class fifth four-architecture option (OG-CAP-1).
- **SUPERSEDES / SUPERSEDED BY:** corrects earlier legacy production ranking; not
  superseded.

## 2. Build 3A.2 — no-build identity lock (sub-identity of 3A)

- **BUILD:** Build 3A.2 (physically identifiable via its dedicated test).
- **PURPOSE:** lock the `NO_BUILD_BASELINE` identity behavior test-first.
- **COMMIT SHA:** `9a04dc5` (same commit as Build 3A; **no separate SHA** — do not
  invent one).
- **DOCUMENTATION:** none dedicated.
- **FOCUSED TEST:** `test_build3a2_identity.py`.
- **TEST EVIDENCE:** 11 `def test_` functions.
- **MAJOR AUTHORITY ESTABLISHED:** test-lock that the do-nothing baseline is a
  distinct, non-fabricated identity.
- **KNOWN CARRIED-FORWARD GAPS:** OG-CAP-1.
- **SUPERSEDES / SUPERSEDED BY:** n/a.

## 3. Build 3B — cyclotron production + patient-demand authority

- **BUILD:** Build 3B.
- **PURPOSE:** establish the cyclotron production-capacity resolver/catalog
  authority and the upstream patient-radionuclide demand chain.
- **COMMIT SHA:** `1d557f0`.
- **DOCUMENTATION:** `CYCLOTRON_PRODUCTION_DATA_AUTHORITY_BUILD_3B.md`.
- **FOCUSED TEST:** `test_build3b_production_authority.py`.
- **TEST EVIDENCE:** 16 `def test_` functions.
- **MAJOR AUTHORITY ESTABLISHED:** cyclotron catalog
  (`cyclotron_equipment_catalog.json`, `load_cyclotron_catalog`),
  per-radionuclide capacity resolver (`resolve_fleet_eob_capacity_mbq_per_day`,
  `_resolve_calibrated_eob_by_radionuclide`), the generator catalog (Mo-99 →
  Tc-99m), and the SUPPORTED ≠ CALIBRATED doctrine (GE PETtrace 890 F-18
  CALIBRATED at 648000 MBq; `SUMITOMO_CYPRIS_MP_30` SUPPORTED but NOT_CALIBRATED).
- **KNOWN CARRIED-FORWARD GAPS:** Cyclotron Production Estimation Authority
  PLANNED (OG-CYC-1); Ge-68/Ga-68 generator NOT_MODELED (OG-GEN-1).
- **SUPERSEDES / SUPERSEDED BY:** builds on the earlier calibrated-fleet
  integration; not superseded.

## 4. Build 3C — five-mode transport building-block authority

- **BUILD:** Build 3C.
- **PURPOSE:** establish the five/six transport modes as composable building
  blocks (Manual/Porter, RGHT/RHTS, Ordinary PTS, RP-PTS, MRT), MRT optional.
- **COMMIT SHA:** `a42cb08`.
- **DOCUMENTATION:** `FIVE_MODE_TRANSPORT_AUTHORITY_BUILD_3C.md`.
- **FOCUSED TEST:** `test_build3c_transport_authority.py`.
- **TEST EVIDENCE:** 45 `def test_` functions.
- **MAJOR AUTHORITY ESTABLISHED:** per-mode timing/fleet/carrier/route/CapEx/OPEX/
  energy/maintenance authorities; Ordinary PTS ≠ RP-PTS; RGHT (rail-guided)
  DISTINCT from true free-roaming FLOOR_AGV_AMR.
- **KNOWN CARRIED-FORWARD GAPS:** true free-roaming FLOOR_AGV_AMR NOT_IMPLEMENTED
  (OG-TRN-1); RP-PTS per-sample trajectory PARTIAL (OG-TRN-2).
- **SUPERSEDES / SUPERSEDED BY:** consolidates prior transport spatial builds; not
  superseded.

## 5. Build 3C coverage closure — transport authority regression coverage

- **BUILD:** Build 3C coverage closure.
- **PURPOSE:** complete the Build 3C transport authority's regression coverage.
- **COMMIT SHA:** `85b10a7`.
- **DOCUMENTATION:** same `FIVE_MODE_TRANSPORT_AUTHORITY_BUILD_3C.md`.
- **FOCUSED TEST:** `test_build3c_transport_authority.py` (extended).
- **TEST EVIDENCE:** 45 `def test_` functions (current total in the file).
- **MAJOR AUTHORITY ESTABLISHED:** coverage hardening only; no new engine authority.
- **KNOWN CARRIED-FORWARD GAPS:** as Build 3C.
- **SUPERSEDES / SUPERSEDED BY:** extends Build 3C.

## 6. Build 3C.1 — spatial route + network authority

- **BUILD:** Build 3C.1.
- **PURPOSE:** establish the two-route-family spatial routing / network authority.
- **COMMIT SHA:** `95040d5`.
- **DOCUMENTATION:** `SPATIAL_ROUTE_NETWORK_AUTHORITY_BUILD_3C1.md`.
- **FOCUSED TEST:** `test_build3c1_spatial_route_authority.py`.
- **TEST EVIDENCE:** 34 `def test_` functions.
- **MAJOR AUTHORITY ESTABLISHED:** `resolve_route` over mode-compatible subgraph;
  HUMAN_CIRCULATION_NETWORK vs CONCEALED_SERVICE_TRANSPORT_CORRIDOR; SHARED
  RIGHT-OF-WAY ≠ SHARED TRACK ≠ MODE INSTALLED; installed-network union counts a
  shared segment once.
- **KNOWN CARRIED-FORWARD GAPS:** RP-PTS trajectory sampler (OG-TRN-2).
- **SUPERSEDES / SUPERSEDED BY:** builds on Build 3C; not superseded.

## 7. Part 3D — Unified Physical Feasibility Closure

- **BUILD:** Part 3D.
- **PURPOSE:** make physical feasibility authoritative — connect the
  production/transport/injection/uptake/scanner gates into
  `ArchitectureResult.feasible` (previously hardcoded `True`); add the
  clinical-resource input authority (project-supplied vs 6/6/12 benchmark); bind
  radioactive route-time to decay without double-counting. No new engines.
- **COMMIT SHA:** `07e861d`.
- **DOCUMENTATION:** `PHYSICAL_FEASIBILITY_AUTHORITY_PART_3D.md`.
- **FOCUSED TEST:** `test_part3d_physical_feasibility_closure.py`.
- **TEST EVIDENCE:** 46 `def test_` functions.
- **MAJOR AUTHORITY ESTABLISHED:** `derive_physical_feasibility`,
  `PhysicalFeasibilityResult`, `ClinicalResourceInputs`,
  `BENCHMARK_CLINICAL_RESOURCES` (6/6/12 `CONTROLLED_BENCHMARK`),
  `_resolve_production_gate` (per-radionuclide), `_resolve_transport_gate`,
  `_physical_feasibility_result_fields` (the single `feasible = status !=
  INFEASIBLE` seam consumed by all four canonical evaluators). NOT_CALIBRATED ≠
  ZERO ≠ automatic infeasibility.
- **KNOWN CARRIED-FORWARD GAPS:** `evaluate_light_mrt_dominant` still hardcodes
  `feasible=True` (OG-P3D-1); PORTER/AGV/RGHT/PTS/RP-PTS not yet in the physical
  transport gate (OG-P3D-2).
- **SUPERSEDES / SUPERSEDED BY:** supersedes the hardcoded `feasible=True` in the
  four canonical evaluators; not superseded.

## 8. Authority Consolidation — governance / traceability layer

- **BUILD:** MRT Pharma Authority Consolidation.
- **PURPOSE:** governance / traceability layer — a master authority index, product
  doctrine, integration architecture, this build ledger, open-gaps register,
  governance doctrine, and governance tests. **No engine behavior change.**
- **COMMIT SHA:** `b8e759e`.
- **DOCUMENTATION:** `MRT_PHARMA_AUTHORITY_INDEX.md`,
  `MRT_PHARMA_PRODUCT_DOCTRINE.md`, `MRT_PHARMA_INTEGRATION_ARCHITECTURE.md`,
  `MRT_PHARMA_BUILD_LEDGER.md`, `MRT_PHARMA_OPEN_GAPS.md`,
  `MRT_PHARMA_AUTHORITY_DOCTRINE.md`.
- **FOCUSED TEST:** `test_mrt_pharma_authority_index.py`.
- **TEST EVIDENCE:** see the governance test run in the final report.
- **MAJOR AUTHORITY ESTABLISHED:** authority-first governance rule (VALIDATED
  REPOSITORY AUTHORITY > SESSION MEMORY > PROMPT SHORTHAND); the three classes of
  project truth; the physical scanner-catalog inventory; the ARIA
  doctrine-vs-live split.
- **KNOWN CARRIED-FORWARD GAPS:** all entries in `MRT_PHARMA_OPEN_GAPS.md` remain
  open; Cyclotron Production Estimation Authority and Part 3E Composition
  Optimizer remain PLANNED.
- **SUPERSEDES / SUPERSEDED BY:** supersedes nothing (additive governance layer).

## 9. Cyclotron Production Estimation — current uncommitted build

- **BUILD:** Cyclotron Production Estimation Authority (OG-CYC-1 closure/refinement).
- **PURPOSE:** create the explicit numerical estimation layer for cyclotron
  model × radionuclide production where manufacturer/site output is
  NOT_CALIBRATED — distinguishing SUPPORTED vs CALIBRATED vs NUMERICALLY
  ESTIMABLE, with the evidence hierarchy `SITE_CALIBRATED >
  MANUFACTURER_CALIBRATED > MODELED_ESTIMATE > CONTROLLED_ASSUMPTION >
  NOT_AVAILABLE`. Reuses Build 3B catalog/normalization + generator daughter set
  + canonical half-lives; no second catalog/resolver.
- **COMMIT SHA:** uncommitted (current working tree; not committed per
  instructions).
- **DOCUMENTATION:** `CYCLOTRON_PRODUCTION_ESTIMATION_AUTHORITY.md`.
- **FOCUSED TEST:** `test_cyclotron_production_estimation_authority.py`.
- **TEST EVIDENCE:** 37 `def test_` functions (30 invariants + control proofs
  A–F + unknown-model raise).
- **FILES:** new `cyclotron_production_estimation_authority.py`; narrow additive
  seam in `whole_oncology_four_architecture_optimization.py`
  (`RadionuclideProductionGate.simulation_production_basis`, default
  `UNRESOLVED`); new doc + test; governance updates (this ledger, INDEX §2.9,
  OPEN_GAPS OG-CYC-1).
- **MAJOR AUTHORITY ESTABLISHED:** `estimate_cyclotron_production`,
  `CyclotronProductionEstimate`, `estimate_required_physical_cycles`,
  `resolve_simulation_production_basis`, `stronger_basis`; the saturation
  irradiation-time response `A_EOB = K·I·(1−exp(−λt))` with K fit from the pair's
  own manufacturer-calibrated anchor (never borrowed); MODELED_ESTIMATE never
  changes calibration status; CYPRIS MP-30 + F-18 = SUPPORTED / NOT_CALIBRATED /
  estimation NOT_AVAILABLE; generator daughters OUT_OF_CYCLOTRON_SCOPE.
- **KNOWN CARRIED-FORWARD GAPS:** OG-CYC-1 now PARTIAL (remaining
  model × radionuclide evidence gaps); OG-GEN-1 (Ge-68/Ga-68 generator) unchanged;
  OG-SYNTH-1 unchanged (randomizer untouched).
- **SUPERSEDES / SUPERSEDED BY:** builds on Build 3B + Part 3D; supersedes the
  §2.9 PLANNED placeholder in the authority index; not superseded.

---

*This ledger is a governance / traceability artifact reconstructed from physical
git history. It introduces no production-engine behavior beyond the additive
estimation authority and its narrow Part 3D seam recorded above.*

## 10. Cyclotron Production Evidence & Calibration Extension — current uncommitted build

- **BUILD:** Cyclotron Production Evidence & Calibration Extension.
- **PURPOSE:** close missing model × radionuclide production *evidence* (not
  estimator architecture). Add a traceable evidence registry the existing
  Cyclotron Production Estimation Authority consumes, so SUPPORTED-but-
  NOT_CALIBRATED pairs can gain a defensible numerical `MODELED_ESTIMATE` where
  real physics/literature evidence exists. Evidence honesty over numerical
  completeness.
- **COMMIT SHA:** uncommitted (current working tree; not committed per
  instructions — do not invent a SHA).
- **STARTING AUTHORITY:** HEAD `9570308`, `origin/main == 9570308`, clean, 0/0.
- **DOCUMENTATION:** `CYCLOTRON_PRODUCTION_EVIDENCE_SOURCES.md` (new); addendum
  in `CYCLOTRON_PRODUCTION_ESTIMATION_AUTHORITY.md`; updates to this ledger,
  `MRT_PHARMA_AUTHORITY_INDEX.md` §2.9, `MRT_PHARMA_OPEN_GAPS.md` (OG-CYC-1).
- **FOCUSED TEST:** `test_cyclotron_production_evidence_extension.py` (36 `def
  test_` functions: 34 Section-38 invariants + unknown-model raise +
  missing-registry graceful degradation).
- **FILES CREATED:** `cyclotron_production_evidence.json`,
  `CYCLOTRON_PRODUCTION_EVIDENCE_SOURCES.md`,
  `test_cyclotron_production_evidence_extension.py`.
- **FILES CHANGED (additive only):** `cyclotron_production_estimation_authority.py`
  (evidence-registry seam + additive `evidence_record_id`/`source_reference`),
  `CYCLOTRON_PRODUCTION_ESTIMATION_AUTHORITY.md`, `MRT_PHARMA_AUTHORITY_INDEX.md`,
  `MRT_PHARMA_OPEN_GAPS.md`, this ledger.
- **ENGINE FILES CHANGED:** only `cyclotron_production_estimation_authority.py`
  (no catalog/radionuclide/fleet/transport/scanner/synthetic-generator change).
- **MAJOR AUTHORITY ESTABLISHED:** `cyclotron_production_evidence.json` registry +
  `ProductionEvidenceRecord`, `load_production_evidence_registry`,
  `resolve_evidence_registry_records`, `resolve_evidence_record` /
  `EvidenceResolution` (multi-evidence resolver, no silent averaging),
  `_try_registry_modeled_estimate` seam. Two evidence-closed pairs: **SIEMENS
  Eclipse HP + F-18** and **SIEMENS RDS-111 + F-18**, each → `MODELED_ESTIMATE`
  (LOW; reaction saturation yield 8.3 GBq/µA applied to each model's OWN 60 µA
  current; ≈264 528 MBq at 120 min — identical because both publish 60 µA, not a
  borrow; below GE PETtrace 890 648 000 MBq).
- **EVIDENCE HONESTY:** CYPRIS MP-30 + F-18 **retained `NOT_AVAILABLE`** (no OWN
  beam current; no GE borrowing). Literature/reaction evidence is `MODELED_
  ESTIMATE` only, never manufacturer/site calibrated; calibration status
  unchanged.
- **KNOWN CARRIED-FORWARD GAPS:** OG-CYC-1 stays PARTIAL (most pairs still
  NOT_AVAILABLE; Cu-64/Zr-89/I-123/I-124 lack half-life physics); OG-GEN-1
  unchanged; **OG-SYNTH-1 remains OPEN** (randomizer untouched).
- **SUPERSEDES / SUPERSEDED BY:** extends build 9 (Cyclotron Production
  Estimation); supersedes nothing; not superseded.


---

## Build — Synthetic Patient Radionuclide Source-Capability Binding (OG-SYNTH-1) — CURRENT UNCOMMITTED BUILD

- **STATUS:** CURRENT UNCOMMITTED BUILD (not committed, not pushed; no SHA assigned).
- **STARTING SHA:** `c35bc4e` (Cyclotron Production Evidence & Calibration
  Extension checkpoint); branch `main`; `origin/main = c35bc4e`; working tree
  clean; divergence 0/0 at start.
- **PURPOSE:** advance OG-SYNTH-1 to PARTIAL by implementing the selected-source
  representative binding — bind synthetic patient radionuclide demand to the
  radionuclides the scenario's SELECTED production sources can actually supply,
  **before** patient creation (the default/legacy path stays benchmark-driven,
  so the gap is not globally closed).
  Required chain: SELECTED SOURCES → SOURCE-SUPPORTED SET → ADMISSIBLE SYNTHETIC
  SET → SYNTHETIC PATIENT REQUIREMENTS → (unchanged) PATIENT-AWARE BATCH PLANNING
  → PHYSICAL PRODUCTION REQUIREMENT → CYCLOTRON / GENERATOR AUTHORITY.
- **MAJOR AUTHORITY ESTABLISHED:** `synthetic_radionuclide_source_capability.py`
  — `resolve_admissible_radionuclides(*, modality, selected_cyclotron_ids,
  selected_generator_ids, mode)` → `SyntheticRadionuclideCapabilityResult`
  (`admissible_radionuclides`, `excluded_radionuclides`, `source_by_radionuclide`,
  `status`, `limitations`); `choose_normal_synthetic_radionuclide`;
  `NoCompatibleSourceError`. Admissible = cyclotron `supported_radionuclides`
  (SUPPORT semantics) ∪ generator `daughter_radionuclide`, filtered by clinical
  modality recognition (F-18 → PET, Tc-99m → SPECT). Selected-source specific;
  no global-catalog fallback; source identities preserved and de-duplicated.
- **NORMAL vs STRESS behavior:** NORMAL = source-capability-constrained before
  patient creation (unsupported radionuclide never generated; `NoCompatibleSource`
  raised — no F-18/Tc-99m fallback). STRESS_TEST / explicit demand = preserved and
  exposed downstream as `NO_COMPATIBLE_SOURCE`; never silently mutated.
- **CANONICAL SEMANTICS PRESERVED:** SUPPORTED ≠ CALIBRATED (CYPRIS MP-30 + F-18
  admissible by SUPPORT while `NOT_CALIBRATED` / `NOT_AVAILABLE`); no estimator,
  capacity, or economics consulted; cyclotron/generator APIs remain NOT
  patient-identity-aware; patient cohort ≠ physical production batch; batch
  planning remains patient-aware and downstream.
- **FILES CREATED:** `synthetic_radionuclide_source_capability.py`,
  `test_synthetic_patient_source_capability.py`,
  `SYNTHETIC_PATIENT_SOURCE_CAPABILITY_AUTHORITY.md`.
- **FILES CHANGED (additive / backward-compatible):** `oncology_pet_spect_scenario.py`
  (import + optional `selected_cyclotron_ids` / `selected_generator_ids` / `mode`
  params on `build_representative_day_population` and
  `build_stochastic_representative_day_population`; the two `NuclearProcedureAssignment`
  radionuclide sites now use the source-resolved locals; `None` selected-source
  ids preserve the benchmark F-18/Tc-99m defaults exactly),
  `MRT_PHARMA_AUTHORITY_INDEX.md`, `MRT_PHARMA_OPEN_GAPS.md`,
  `MRT_PHARMA_PRODUCT_DOCTRINE.md`, this ledger.
- **ENGINE FILES CHANGED:** only `oncology_pet_spect_scenario.py` (the synthetic
  generator seam). No cyclotron estimator / catalog / generator / transport /
  scanner / four-architecture / equal_budget change.
- **FOCUSED TESTS:** `test_synthetic_patient_source_capability.py` — 47 passed
  (40 Section-41 invariants + control proofs A–F + patient-aware batch boundary).
- **PRESERVATION REGRESSION (all `/opt/anaconda3/bin/python -m pytest`):** patient
  radionuclide demand + oncology PET/SPECT + inbound + production clinical schedule
  + cyclotron catalog foundation + PET/SPECT generator native + cyclotron production
  estimation + evidence extension = 275 passed; Build 3B + Part 3D = 62 passed;
  `test_equal_budget.py` + `test_mrt_pharma_authority_index.py` = 128 passed; multi-
  cyclotron + production windows + multi-isotope decay = 83 passed; four-architecture
  = 199 passed / 1 skipped; capital project API + cyclotron e2e/fleet = 48 passed.
- **GOVERNANCE:** OG-SYNTH-1 = **PARTIAL** (advanced from PLANNED / PARTIAL, NOT
  globally CLOSED). Implemented + test-locked: the selected-source capability
  resolver, the selected-source-constrained representative NORMAL path, no-source
  `NO_COMPATIBLE_SOURCE` failure, and STRESS_TEST / explicit-demand preservation.
  Still open: the default/legacy synthetic path (no selected-source ids) remains
  benchmark-driven (F-18 / Tc-99m) for backward compatibility, so the constraint
  is opt-in. OG-CYC-1, OG-GEN-1, and all other gaps unchanged.
- **SUPERSEDES / SUPERSEDED BY:** builds on the Cyclotron Production Evidence
  Extension checkpoint; supersedes nothing; not superseded.


---

## CURRENT UNCOMMITTED BUILD — Scanner Authority Review & Part 3E Readiness

- **TYPE:** REVIEW / DOCUMENTATION (audit → authority trace → gap classification
  → Part 3E readiness determination). **No engine code changed.**
- **STARTING SHA:** `a1002ca` (origin/main; clean; divergence 0/0).
- **PURPOSE:** finalize the scanner authority review and the Part 3E readiness
  determination — verify (not restart) the existing review against the physical
  repository, complete the readiness matrix, classify remaining scanner gaps,
  lock conclusions with focused tests, and report. No Part 3E, no Equipment OPEX
  Authority, no scanner optimization, no BIM ingestion, no Operations closure,
  no UI.
- **REVIEW ARTIFACTS (untracked, created):**
  `SCANNER_AUTHORITY_REVIEW_PART_3E_READINESS.md`,
  `test_scanner_authority_review.py`.
- **GOVERNANCE DOCS CHANGED (additive):** `MRT_PHARMA_AUTHORITY_INDEX.md`
  (scanner-review conclusions block), `MRT_PHARMA_OPEN_GAPS.md`
  (OG-SCN-1 refined to PARTIAL; added OG-SCN-2 and OG-OPEX-1),
  `MRT_PHARMA_PRODUCT_DOCTRINE.md` (Section 11A durable scanner doctrine),
  this ledger.
- **SCANNER INVENTORY:** six real models — Siemens Symbia Pro.specta (SPECT),
  Siemens Biograph Vision (PET), GE NM/CT 870 DR (SPECT), GE NM/CT 860 (SPECT),
  GE Discovery MI (PET), Philips BrightView XCT (SPECT, LEGACY_INSTALLED_BASE,
  not a new-purchase candidate). Technical fields `literature_calibrated`;
  economics/power/footprint `NOT_CALIBRATED`.
- **PART 3E READINESS RESULT:** `READY_WITH_DOCUMENTED_LIMITATIONS`.
  `SCANNER_QUANTITY_SELECTION_READY=YES`, `MODALITY_SELECTION_READY=YES`,
  `MODEL_SELECTION_READY=NO`, `PHASE_1_MODE=CLASS_AND_MODALITY`,
  `PHASE_1_READY=YES`. Model-specific scanner optimization deferred (not blocking).
- **OPEX CONCLUSION:** cross-equipment OPEX = PARTIAL. A schedule-derived
  equipment ENERGY authority (`equipment_energy_opex.py`) already exists (duty
  derived from the actual long-horizon plan); the missing layer is monetary
  (per-model power kW + service/unit $). Recorded as OG-OPEX-1.
  `EQUIPMENT_OPEX_AUTHORITY_REQUIRED_BEFORE_PART_3E_PHASE_1 = NO`
  (Phase 1 may use `known_annual_opex_subtotal_usd` with
  `total_annual_opex_usd = NOT_CALIBRATED`).
- **HOSPITAL MASTER CALENDAR FINDING:** long-horizon operational planning
  authority EXISTS (`long_horizon_operational_planning.py`, data-driven horizon,
  single validated day engine per date; scanner resource identity + date-level
  availability + patient→batch→scanner traceability). Intra-day maintenance/
  downtime windows and per-scanner operating hours remain PARTIAL/NOT_MODELED
  (future Operations closure, not this review).
- **HONEST CORRECTION MADE (documentation only):** the FOUR canonical
  architecture evaluators derive `ArchitectureResult.feasible` from the Part 3D
  contract; the separate `evaluate_light_mrt_dominant` variant and
  `ZonalHybridPartitionCandidate` still hardcode `feasible=True` (recorded as
  OG-SCN-2). No engine change made to fix this in a review build.
- **FOCUSED TESTS:** `test_scanner_authority_review.py` — **41 passed**
  (25 scanner-authority + 8 calendar-seam + 7 final-readiness + 1 modality-guard).
- **DIRECTLY-AFFECTED REGRESSION (all `/opt/anaconda3/bin/python -m pytest`):**
  - scanner review + clinical identity + clinical bottleneck + Part 3D closure +
    equipment energy OPEX + oncology PET/SPECT completion = **168 passed**.
  - long-horizon calendar + operating-day scheduler + production-clinical schedule
    + patient radionuclide demand + design-horizon + Build 3B production +
    cyclotron production windows + multi-isotope decay + synthetic source
    capability = **193 passed**.
  - `test_equal_budget.py` + `test_mrt_pharma_authority_index.py`
    (economic + governance PRESERVATION) = **128 passed**.
  - canonical spatial authority closure = **85 passed**; architecture report =
    **2 passed**; `test_spatial_benchmark.py` representative decay/transport
    identity subset = **2 passed** (full 22-test suite is genuinely slow, not
    broken; no engine change affects it).
  - capital project API + Build 3A (identity + MRT patch C) + Build 3C transport +
    Build 3C.1 spatial route + cyclotron catalog foundation + PET/SPECT generator
    native = **185 passed**.
  - four-architecture optimization = **199 passed, 1 skipped**.
- **ENGINE FILES CHANGED:** **NONE.** `git diff --name-only` = three governance
  `.md` docs only (+137/-7); untracked = the two review artifacts. `equal_budget.py`
  untouched; four-architecture / scanner / production / calendar engines untouched.
- **OG-SCN-1 STATUS:** **PARTIAL** (refined from NOT_CALIBRATED headline;
  quantity + modality READY, model-specific ranking NOT_YET_RANKABLE).
- **NO commit. NO push. NO stage.**

---

## Equipment OPEX Authority (uncommitted)

- **Starting authority:** branch `main`, HEAD `df7bf03` (Scanner authority: Part 3E
  readiness boundary), working tree clean, divergence 0/0.
- **Nature:** NARROW engine build. New `equipment_opex_authority.py` COMPOSES the
  existing `equipment_energy_opex.py` (+ cyclotron/generator/scanner catalogs +
  long-horizon production plan) into a componentized physical-driver → annual-OPEX
  authority for SCANNER, CYCLOTRON, GENERATOR. No new duty-cycle engine, no
  physics change, no catalog change, no Part 3E optimizer, no UI.
- **Contract:** `EquipmentOpexComponent` (physical driver + monetary unit cost as
  SEPARATE evidence classes, weakest governs) + `EquipmentOpexResult`
  (`known_annual_opex_subtotal_usd`, `total_annual_opex_status`,
  `comparability_status`, reusing `EconomicComparabilityStatus`).
  `build_opex_component` is the single no-zero-fill choke point (unknown →
  `None`/status, never `$0`).
- **Control proofs (Section 44):** A scanner-unknown-power (duty exists, energy `$`
  withheld); B cyclotron-utilization (2 cycles → 3.0 beam-on hours, no kW from
  beam current); C CYPRIS MP-30 preserved `not_calibrated`, no GE borrowing; D
  generator replacement 27/yr @14-day life CALCULABLE, procurement `$`
  `NOT_CALIBRATED`; E known subtotal `$50,000` while total `NOT_CALIBRATED`; F no
  zero-fill on service/power/price.
- **FOCUSED TESTS:** `test_equipment_opex_authority.py` — **40 passed**
  (34 invariants + 6 control proofs). One real bug fixed:
  `known_annual_opex_subtotal_usd` now `float(sum(...))` (was int `0`).
- **DIRECTLY-AFFECTED REGRESSION (all `/opt/anaconda3/bin/python -m pytest`):**
  - OPEX authority + `equipment_energy_opex` + scanner review = **102 passed**.
  - cyclotron catalog foundation/e2e/fleet/windows/estimation/evidence +
    PET-SPECT generator native + long-horizon planning + production-clinical
    schedule = **224 passed**.
  - multi-isotope decay + F-18 decay + `equal_budget` + authority index =
    **158 passed**.
  - Part 3D physical feasibility = **46 passed**.
  - capital project API = **27 passed**.
  - four-architecture optimization = **199 passed, 1 skipped**.
- **ENGINE FILES CHANGED:** **NONE.** `git diff --stat` empty; untracked =
  `equipment_opex_authority.py`, `test_equipment_opex_authority.py`,
  `EQUIPMENT_OPEX_AUTHORITY.md`; governance `.md` docs refined
  (`MRT_PHARMA_AUTHORITY_INDEX.md` §2.23A, `MRT_PHARMA_OPEN_GAPS.md` OG-OPEX-1,
  `MRT_PHARMA_PRODUCT_DOCTRINE.md` §12A, this ledger).
- **OG-OPEX-1 STATUS:** **PARTIAL** (physical-driver + componentization authority
  IMPLEMENTED; monetary power/service/consumable/procurement `$` inputs still
  unavailable). Part 3E Phase 1 consumable with qualified economics.
- **NO commit. NO push. NO stage.**

---

## Clinical Radionuclide Completeness & Evidence Closure (Pre-Part-3E) — UNCOMMITTED

- **Starting SHA:** `6343ca1` (Clinical Radionuclide Portfolio Authority), branch
  `main`, origin/main = `6343ca1`, divergence 0/0, working tree clean at start.
- **Objective:** COMPLETENESS — determine whether radionuclides excluded from the
  NORMAL portfolio lacked evidence or lacked incorporation, then propagate found
  authoritative evidence into the CANONICAL authorities and recompute the
  portfolio. Architecture/transport/economics-neutral. Not intended to make MRT
  win.
- **NEW FILES:** `clinical_radionuclide_evidence.json` (canonical evidence
  registry, 27 records), `CLINICAL_RADIONUCLIDE_COMPLETENESS_AUTHORITY.md`
  (14 inline tables), `test_clinical_radionuclide_completeness.py` (62 tests).
- **CANONICAL AUTHORITIES UPDATED (evidence-gated, DATA only — no equations):**
  - `radionuclides.json`: half-life table **7 → 15** (added Cu-64=762.0,
    Zr-89=4705.2, Ge-68=390441.6, I-123=792.0, I-124=6012.0, In-111=4038.912,
    Tl-201=4380.624, At-211=432.96 min). Single decay authority; no second table.
  - `synthetic_radionuclide_source_capability.py`: the single canonical clinical
    modality authority `_CLINICALLY_RECOGNIZED_RADIONUCLIDES_BY_MODALITY` extended
    **2 → 12** evidence-gated bindings (PET +C-11/N-13/O-15/Ga-68/Cu-64/Zr-89/
    I-124; SPECT +I-123/In-111/Tl-201). Consumed unchanged-in-shape by the
    portfolio (no competing dict).
  - `generator_equipment_catalog.json`: added `ECKERT_ZIEGLER_GALLIAPHARM`
    (Ge-68 → Ga-68) — OG-GEN-1 pathway closed; economics NOT_CALIBRATED.
- **CONSUMER TESTS UPDATED (test-lock new canonical truth):**
  `test_clinical_radionuclide_portfolio.py` (52 → 54),
  `test_synthetic_patient_source_capability.py` (47),
  `test_pet_spect_generator_native_authority_completion.py` (+Ge-68/Ga-68 test),
  `test_cyclotron_production_estimation_authority.py` /
  `test_cyclotron_production_evidence_extension.py` (Ga-68 now a generator
  daughter → OUT_OF_CYCLOTRON_SCOPE on unsupported cyclotrons; genuine
  NO_COMPATIBLE_SOURCE proofs re-based on cyclotron-only Cu-64).
- **PORTFOLIO RECOMPUTED (emergent):** NORMAL_ADMISSIBLE **2 → 12**, HALF_LIFE
  **7 → 15**, MODALITY **2 → 12**, PART3E_ELIGIBLE **2 → 12**,
  SHORT_HALF_LIFE_ADMISSIBLE **0 → 3**. Excluded honestly: At-211 (THERAPY),
  Ge-68/Mo-99 (generator parents).
- **PHYSICS/ECONOMICS PRESERVED:** decay/generator/cyclotron **equations**
  unchanged (DATA only); Equipment OPEX, scanner timing, transport physics,
  Part 3D, capital/economic engine, `equal_budget` **unchanged**.
- **GOVERNANCE:** OG-GEN-1 → PATHWAY_CLOSED (economics PARTIAL); OG-RAD-1 advanced
  (still PARTIAL — procedure authority + quantitative production + demand-mix
  weighting remain NOT_MODELED). OG-SCN-1 / OG-SYNTH-1 boundaries preserved.
- **NO commit. NO push. NO stage.**

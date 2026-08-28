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
| Authority Consolidation | uncommitted (current working tree) | this ledger + INDEX/DOCTRINE/PRODUCT/INTEGRATION/OPEN_GAPS | `test_mrt_pharma_authority_index.py` | (this build) |

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

## 8. Authority Consolidation — current uncommitted build

- **BUILD:** MRT Pharma Authority Consolidation (this build).
- **PURPOSE:** governance / traceability layer — a master authority index, product
  doctrine, integration architecture, this build ledger, open-gaps register,
  governance doctrine, and governance tests. **No engine behavior change.**
- **COMMIT SHA:** uncommitted (current working tree; not committed per
  instructions).
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

---

*This ledger is a governance / traceability artifact reconstructed from physical
git history. It introduces no production-engine behavior.*

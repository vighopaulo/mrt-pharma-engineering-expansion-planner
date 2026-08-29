# PART 3E — RADIONUCLIDE-AWARE ARCHITECTURE OPTIMIZATION (PHASE 1)

**Self-contained authority report.** Build starting point: `main` @ HEAD
`22082ff` (`origin/main` = `22082ff`, divergence 0/0, working tree clean at
start). Build 3A/3B/3C/3C.1 and Part 3D are complete and not reopened.

This build adds a **narrow orchestration authority** that integrates the
completed Clinical Radionuclide Portfolio into the existing four-architecture
physical/economic framework. It builds **no new physics/scheduling/decay/
production/transport/economic engine** and makes **no change** to `wo4a`
(`whole_oncology_four_architecture_optimization.py`), Part 3D, `equal_budget.py`,
or the `hybrid_optimization` decay math.

Deliverables:
- `part3e_radionuclide_aware_architecture.py` (the Part 3E authority)
- `test_part3e_radionuclide_aware_architecture.py` (67 focused tests)
- this document

**No commit. No push. No stage.**

---

## A. Scope & doctrine

Part 3E Phase 1 answers: *given an EXPLICIT radionuclide demand mix and a set of
selected/installed production sources, which of the four architectures
(MANUAL_CONVENTIONAL, AUTOMATED_CONVENTIONAL, MRT_DOMINANT, HYBRID_MRT) are
physically feasible, and how do they rank — with every radionuclide resolved
against its OWN source, decay, scanner modality, and production status?*

Phase 1 boundaries (all honest, all enforced):
- **Scanner optimization is at CLASS_AND_MODALITY** (modality × quantity), never
  manufacturer/model. Model-specific selection is DEFERRED.
- **The physical timing engine is single-radionuclide.** Mixed scenarios are a
  Phase-1 AGGREGATION, never true joint multi-radionuclide scheduling.
- **No invented prevalence.** The demand mix is always an explicit input.
- **No MRT bonus, no Conventional bonus.** Ranking reuses the existing `wo4a`
  cost-only / Pareto helpers over the same derived `ArchitectureResult`s.

---

## Table 1 — Consumed authorities (reused, never re-implemented)

| Authority | Module | Part 3E use |
|---|---|---|
| Clinical radionuclide portfolio | `clinical_radionuclide_portfolio.resolve_clinical_radionuclide_portfolio` | WHAT demand is legitimate; per-radionuclide source/scanner/decay |
| Per-patient demand primitive | `patient_radionuclide_demand.PatientRadionuclideDemand` | validated per-patient demand (half-life table) |
| Part 3D feasibility contract | `wo4a.derive_physical_feasibility` (via the 4 evaluators) | derived `feasible`/qualification/binding per architecture |
| Radionuclide-specific production gate | `wo4a._resolve_radionuclide_production_gate` | per-radionuclide source + calibration verdict |
| Scanner CLASS_AND_MODALITY sizing | `oncology_pet_spect_scenario.required_scanner_count` | scanner quantity per modality (no model) |
| Decay authority | `diagnostics.load_radionuclide_half_lives` | half-life per radionuclide |
| Equipment OPEX (available, not required Phase 1) | `equipment_opex_authority` | disclosed; class/quantity/modality selected, not $ |
| Ranking / Pareto | `wo4a.rank_cost_only`, `wo4a.compute_pareto_front` | no-bonus architecture ranking |

## Table 2 — New Part 3E frozen read-models

| Type | Purpose |
|---|---|
| `RadionuclideStreamDemand` | one radionuclide's explicit demand (count + activity) |
| `RadionuclideDemandScenario` | the explicit demand mix + selected sources/modalities |
| `RadionuclideStreamResolution` | per-radionuclide source/activity/decay/scanner/production |
| `Phase1Aggregation` | legitimate Phase-1 aggregates (per-modality scanner pools) |
| `MultiRadionuclideSchedulingDisclosure` | mandatory joint-scheduling honesty |
| `Part3EArchitectureResult` | one architecture's derived Part 3D result + context |
| `Part3EScenarioResult` | full scenario result across the 4-architecture bouquet |
| `RadionuclidePatientExportRow` | patient/appointment export seam row |
| `ArchitectureFinancialExportRow` | financial export seam row |

## Table 3 — Demand-source authority (no invented prevalence)

| `demand_source` | Meaning | Prevalence invented? |
|---|---|---|
| `PROJECT_SUPPLIED_PATIENTS` | built from an explicit patient list (`scenario_from_patients`) | NO |
| `PROJECT_SUPPLIED_COUNTS` | built from explicit (radionuclide, count, activity) triples (`scenario_from_counts`) | NO |

There is deliberately **no** stochastic/prevalence demand source. The portfolio's
`multi_radionuclide_weighting_authority == "NOT_MODELED"` is preserved.

## Table 4 — Multi-radionuclide scheduling disclosure (governor)

| Field | Value | Basis |
|---|---|---|
| `SCHEDULING_BASIS` | `SINGLE_RADIONUCLIDE_PER_STREAM_INDEPENDENT` | engine is single-radionuclide |
| `TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING` | **NO** | `evaluate_hybrid_zone_candidate` uses one `production_basis.radionuclide` + one half-life |
| `MULTI_RADIONUCLIDE_PHASE1_AGGREGATION` | **YES** | streams resolved independently, legitimate quantities aggregated |
| `JOINT_OPERATIONAL_FEASIBILITY_STATUS` | scenario-dependent (Table 5) | derived |
| `SHARED_RESOURCE_CONFLICT_VALIDATION` | `NOT_APPLICABLE_SINGLE_RADIONUCLIDE` / `NOT_VALIDATED` | mixed → cannot validate cross-radionuclide conflicts |

## Table 5 — `JOINT_OPERATIONAL_FEASIBILITY_STATUS` derivation

| Scenario shape | Status |
|---|---|
| exactly one radionuclide with demand | `SINGLE_RADIONUCLIDE_VALIDATED` |
| >1 radionuclide, all streams resolvable | `NOT_FULLY_VALIDATED` |
| any demanded stream has no compatible source/scanner | `INFEASIBLE_STREAM_PRESENT` |

## Table 6 — Control scenarios

| Control | Scenario id | Streams |
|---|---|---|
| Baseline | `BASELINE_F18_TC99M` | F-18 (PET, 32), Tc-99m (SPECT, 18) |
| Short half-life | `SHORT_HALF_LIFE_C11_N13_O15` | C-11, N-13, O-15 (all PET) |
| Ga-68 cyclotron arm | `GA68_CYCLOTRON` | Ga-68 (cyclotron `SUMITOMO_CYPRIS_MP_30` selected) |
| Ga-68 generator arm | `GA68_GENERATOR` | Ga-68 (generator `ECKERT_ZIEGLER_GALLIAPHARM` selected) |
| Mixed PET | `MIXED_PET_F18_GA68_C11` | F-18, Ga-68, C-11 |
| Mixed PET+SPECT | `MIXED_PET_SPECT_F18_TC99M_GA68` | F-18, Tc-99m, Ga-68 |
| Unsupported equipment | `UNSUPPORTED_CYPRIS_MP_30` | F-18 (installed CYPRIS MP-30, uncalibrated) |

## Table 7 — Baseline F-18 + Tc-99m per-radionuclide resolution

| Radionuclide | Modality | Source type | Source identity | Production gate | Scanner count | Status |
|---|---|---|---|---|---|---|
| F-18 | PET | CYCLOTRON | PETtrace 890 | PRODUCTION_SUFFICIENT | ≥1 | RESOLVED_ADMISSIBLE |
| Tc-99m | SPECT | GENERATOR | CURIUM_TECHNELITE | PRODUCTION_NOT_CALIBRATED | ≥1 | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |

Mixed → `JOINT_OPERATIONAL_FEASIBILITY_STATUS = NOT_FULLY_VALIDATED`.

## Table 8 — Short half-life C-11 / N-13 / O-15 resolution

| Radionuclide | Modality | Source type | Production gate | Status |
|---|---|---|---|---|
| C-11 | PET | NONE | NO_COMPATIBLE_SOURCE | EXCLUDED_NO_COMPATIBLE_SOURCE |
| N-13 | PET | NONE | NO_COMPATIBLE_SOURCE | EXCLUDED_NO_COMPATIBLE_SOURCE |
| O-15 | PET | NONE | NO_COMPATIBLE_SOURCE | EXCLUDED_NO_COMPATIBLE_SOURCE |

**Proves the calibrated F-18 record never qualifies another radionuclide** (the
benchmark GE PETtrace 890 F-18 fleet does not support C-11/N-13/O-15). Scenario
→ `INFEASIBLE_STREAM_PRESENT`.

## Table 9 — Ga-68 dual pathway (DISTINCT source types)

| Arm | Selected source | Resolved source type | Source identity | Production gate |
|---|---|---|---|---|
| Cyclotron | `SUMITOMO_CYPRIS_MP_30` | CYCLOTRON | CYPRIS MP-30 | PRODUCTION_NOT_CALIBRATED |
| Generator | `ECKERT_ZIEGLER_GALLIAPHARM` | GENERATOR | ECKERT_ZIEGLER_GALLIAPHARM | PRODUCTION_NOT_CALIBRATED |

Same radionuclide, two distinct source types, both honestly NOT_CALIBRATED
(never fabricated). With no cyclotron selected, Ga-68 falls to the generator
daughter path (never fabricated).

## Table 10 — Mixed PET resolution

| Radionuclide | Modality | Source type | Production gate | Status |
|---|---|---|---|---|
| F-18 | PET | CYCLOTRON | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE |
| Ga-68 | PET | GENERATOR | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| C-11 | PET | NONE | NO_COMPATIBLE_SOURCE | EXCLUDED_NO_COMPATIBLE_SOURCE |

Scenario → `INFEASIBLE_STREAM_PRESENT` (C-11 has no source).

## Table 11 — Mixed PET+SPECT resolution

| Radionuclide | Modality | Source type | Production gate | Status |
|---|---|---|---|---|
| F-18 | PET | CYCLOTRON | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE |
| Tc-99m | SPECT | GENERATOR | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| Ga-68 | PET | GENERATOR | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |

All streams resolvable → `NOT_FULLY_VALIDATED` (mixed).

## Table 12 — Unsupported-equipment control (real identity, not fabricated)

| Radionuclide | Selected cyclotron | Source type | Source identity | Production gate | Fabricated capacity? |
|---|---|---|---|---|---|
| F-18 | `SUMITOMO_CYPRIS_MP_30` | CYCLOTRON | CYPRIS MP-30 | PRODUCTION_NOT_CALIBRATED | NO |

CYPRIS MP-30 declares F-18 support but has no calibrated production record, so it
forms no schedulable fleet. The Build 3B seam recognises the **real** equipment
identity and reports `PRODUCTION_NOT_CALIBRATED` (never `NO_COMPATIBLE_SOURCE`,
never a fabricated EOB/cycle/record).

## Table 13 — Phase-1 aggregation rules (what may be aggregated)

| Quantity | Aggregated? | Rule |
|---|---|---|
| Total patient count | YES | sum across streams |
| PET patient count | YES | sum of PET streams only |
| SPECT patient count | YES | sum of SPECT streams only |
| PET scanner requirement | YES (PET pool) | sum of per-PET-stream `required_scanner_count` |
| SPECT scanner requirement | YES (SPECT pool) | sum of per-SPECT-stream `required_scanner_count` |
| Total scanner requirement | YES (physical rooms) | PET + SPECT (never pooled capacity) |
| Prescribed activity | **PER RADIONUCLIDE ONLY** | never one collapsed "total activity" |
| Operational feasibility | **NO** | never claimed from per-stream feasibility |

## Table 14 — Per-modality scanner pool separation (mixed PET+SPECT)

| Pool | Streams counted | Scanner count | Notes |
|---|---|---|---|
| PET | F-18 (24), Ga-68 (6) | 3 | PET streams only |
| SPECT | Tc-99m (16) | 1 | SPECT stream only; no PET spillover |
| Total | — | 4 | PET pool + SPECT pool (distinct rooms) |

PET demand never consumes SPECT capacity and vice versa
(`clinical_resource_identity` doctrine; no silent sharing).

## Table 15 — Four-architecture bouquet (baseline scenario)

| Architecture | Evaluator | `feasible` source | Physical status | Qualification | Lifecycle cost |
|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | `evaluate_manual_conventional` | DERIVED (Part 3D) | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | $11,869,790 |
| AUTOMATED_CONVENTIONAL | `evaluate_automated_conventional` | DERIVED | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | $14,478,032 |
| MRT_DOMINANT | `evaluate_mrt_dominant` → `_evaluate_mrt_style_architecture` | DERIVED | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | $45,522,122 |
| HYBRID_MRT | `evaluate_hybrid_mrt` → `_evaluate_mrt_style_architecture` | DERIVED | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | $52,786,154 |

## Table 16 — Ranking (cost-only, NO bonus)

| Rank | Architecture | Lifecycle cost |
|---|---|---|
| 1 | MANUAL_CONVENTIONAL | $11,869,790 |
| 2 | AUTOMATED_CONVENTIONAL | $14,478,032 |
| 3 | MRT_DOMINANT | $45,522,122 |
| 4 | HYBRID_MRT | $52,786,154 |

Ranking is identical to `wo4a.rank_cost_only` over the same results (test 53).
No architecture family is preferred; MRT is not artificially advanced.

## Table 17 — CLASS_AND_MODALITY scanner scope

| Dimension | Phase 1 |
|---|---|
| Scanner quantity selection | READY (`required_scanner_count`) |
| Scanner modality selection | READY (PET/SPECT pools) |
| Scanner model selection | DEFERRED (`PART_3E_SCANNER_MODEL_SELECTION_READY = NO`) |
| Controlled protocol minutes | PET 25.0 / SPECT 30.0 (CONTROLLED_ENGINEERING_ASSUMPTION) |
| Operating window / availability | 10.0 h/day, 85% (controlled) |

## Table 18 — Decay authority binding

| Aspect | Source | Phase 1 |
|---|---|---|
| Half-life per radionuclide | `diagnostics.load_radionuclide_half_lives` | consumed |
| Route-time → decay (single-radionuclide) | Part 3D hybrid path (already bound, single interval) | preserved, unchanged |
| Multi-radionuclide joint decay | — | NOT modeled (single-radionuclide engine) |

## Table 19 — Equipment OPEX authority disposition

| Equipment class | OPEX authority | Phase 1 requirement |
|---|---|---|
| SCANNER | `compute_scanner_opex` | available; not required for class/modality/quantity selection |
| CYCLOTRON | `compute_cyclotron_opex` | available; most $ NOT_CALIBRATED (no zero-fill) |
| GENERATOR | `compute_generator_opex` | available; procurement $ NOT_CALIBRATED |

Part 3E Phase 1 selects class/quantity/modality, not $ OPEX; the OPEX authority
is consumed only via the four-architecture `ArchitectureResult` economics.

## Table 20 — Export seams

| Seam | Function | Row type | Recomputes engine? |
|---|---|---|---|
| Patient / appointment | `export_patient_appointment_rows` | `RadionuclidePatientExportRow` | NO |
| Forward appointment | (same seam, per-stream projection) | `RadionuclidePatientExportRow` | NO |
| Financial | `export_financial_rows` | `ArchitectureFinancialExportRow` | NO (straight from `ArchitectureResult`) |

## Table 21 — Part 3D preservation

| Evaluator | Feasibility source | Part 3E impact |
|---|---|---|
| `evaluate_manual_conventional` | DERIVED | consumed unchanged |
| `evaluate_automated_conventional` | DERIVED | consumed unchanged |
| `evaluate_mrt_dominant` → `_evaluate_mrt_style_architecture` | DERIVED | consumed unchanged (canonical MRT_DOMINANT) |
| `evaluate_hybrid_mrt` → `_evaluate_mrt_style_architecture` | DERIVED | consumed unchanged |
| `evaluate_light_mrt_dominant` (Build-2R variant) | hardcoded `feasible=True` | **NOT in the Part 3E bouquet** → no contamination |

## Table 22 — Test coverage summary

| Group | Tests | Focus |
|---|---|---|
| Frozen read-model invariants | 01–10 | immutability, validation, `is_mixed` |
| Scenario construction | 11–15 | explicit demand only; no invented prevalence |
| Per-radionuclide resolution | 16–25 | source/decay/scanner; F-18 doesn't qualify others |
| Ga-68 dual pathway | 26–31 | distinct cyclotron vs generator source types |
| Unsupported equipment | 32–34 | real identity NOT_CALIBRATED, not fabricated |
| Scheduling disclosure | 35–41 | TRUE_JOINT=NO, AGG=YES, joint-op status |
| Phase-1 aggregation | 42–48 | PET/SPECT pools distinct; activity per-radionuclide |
| Four-architecture bouquet | 49–57 | Part 3D-derived feasibility; no bonus |
| Export seams | 58–62 | patient/financial projections |
| Part 3D / framework preservation | 63–67 | wo4a unchanged; identity invariants |
| **Total** | **67** | all pass |

## Table 23 — Regression summary (directly affected)

| Suite group | Result |
|---|---|
| Part 3E focused (`test_part3e_radionuclide_aware_architecture.py`) | 67 passed |
| Portfolio + completeness + Part 3D + wo4a four-arch + equipment OPEX + scanner authority + PET/SPECT | 504 passed, 1 pre-existing skip |
| Build 3B/3C/3C.1 + cyclotron windows/fleet + multi-cyclotron + multi-isotope decay + design day | 190 passed |
| Full repo collection | 4176 tests collected, no import errors |

## Table 24 — Phase-1 readiness / deferral matrix

| Capability | Phase 1 |
|---|---|
| Per-radionuclide source resolution (cyclotron/generator/none) | READY |
| Per-radionuclide decay authority | READY |
| Per-radionuclide production calibration status | READY (Build 3B) |
| Ga-68 dual-pathway (cyclotron vs generator) | READY (distinct) |
| Unsupported-but-installed equipment (real identity, NOT_CALIBRATED) | READY |
| Scanner quantity + modality selection | READY (CLASS_AND_MODALITY) |
| Scanner model selection / model economics | DEFERRED |
| Four-architecture feasibility + ranking (no bonus) | READY (Part 3D-derived) |
| Patient / appointment / financial export seams | READY |
| True joint multi-radionuclide scheduling | NOT MODELED (single-radionuclide engine) |
| Real-world prevalence / demand-mix authority | NOT MODELED (explicit input only) |
| Model-specific radionuclide→scanner compatibility | NOT MODELED (modality-level) |

---

## Governance

- **Authority-first.** Every physics/economics/feasibility decision delegates to
  an existing authority (Table 1). Part 3E adds only orchestration + frozen
  read-models + export projections.
- **No engine mutation.** `wo4a`, Part 3D (`derive_physical_feasibility`),
  `equal_budget.py`, and `hybrid_optimization` decay math are unchanged. Verified
  by 504+190 regression tests passing.
- **Honest scheduling.** `TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING = NO` is
  exposed on every scenario; mixed scenarios are Phase-1 AGGREGATION with
  `JOINT_OPERATIONAL_FEASIBILITY_STATUS` and
  `SHARED_RESOURCE_CONFLICT_VALIDATION` disclosed, never overstated.
- **No invented prevalence.** Demand is always explicit; the portfolio's
  `multi_radionuclide_weighting_authority = NOT_MODELED` is preserved.
- **No fabricated production.** NOT_CALIBRATED sources carry their real identity
  and no invented EOB/cycle/record (CYPRIS MP-30 seam).
- **No bonus.** Ranking reuses `wo4a.rank_cost_only`/`compute_pareto_front`.
- **Part 3D residual recorded, non-blocking.** The Light-MRT-variant hardcoded
  `feasible=True` is outside the Part 3E bouquet; no Part 3D change made.

## Final report

- `PART_3E_PHASE_1_STATUS = COMPLETE_WITH_DOCUMENTED_DEFERRALS`
- `TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING = NO`
- `MULTI_RADIONUCLIDE_PHASE1_AGGREGATION = YES`
- `SCANNER_OPTIMIZATION_LEVEL = CLASS_AND_MODALITY`
- `INVENTED_PREVALENCE = NONE`
- `ENGINE_CODE_CHANGED = NO` (wo4a / Part 3D / equal_budget / hybrid decay unchanged)
- `FOUR_ARCHITECTURE_FEASIBILITY_SOURCE = PART_3D_DERIVED`
- `FOCUSED_TESTS = 67 passed`
- `DIRECTLY_AFFECTED_REGRESSION = 694 passed, 1 pre-existing skip`
- `FULL_COLLECTION = 4176 tests, no import errors`
- Files created: `part3e_radionuclide_aware_architecture.py`,
  `test_part3e_radionuclide_aware_architecture.py`,
  `RADIONUCLIDE_AWARE_ARCHITECTURE_AUTHORITY_PART_3E.md` (this document)

**No commit. No push. No stage.**

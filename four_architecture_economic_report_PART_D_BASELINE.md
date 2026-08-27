# Four-Architecture Economic Comparison Report
**Controlled 200-Patient/Day Comparison — Manual Conventional vs Automated Conventional vs MRT vs Hybrid**

Generated from `operational_day_orchestrator.py` (`run_four_architecture_economic_comparison`), reusing all previously-established Operating-Day, carrier-hardware, mass, endpoint-CapEx, and AGV/PTS authorities. No second economics, production, decay, or spatial engine was created.

---

## Part 0 — Three Pre-Existing Failure Diagnoses (investigated this turn)

All three failures were reproduced **individually** (single-test runs, no cross-test contamination possible) and root-caused. All three are **confirmed pre-existing** and **unrelated** to the carrier-mass correction (Part C) or the four-architecture economic comparison (Part D):

| # | Test | Root cause | Files involved | Related to Part C/D? |
|---|---|---|---|---|
| 1 | `test_cyclotron_catalog_e2e_integration.py::test_heterogeneous_fleet_preserves_model_specific_capability_records` | The native decision pipeline's `batch_release_mappings` assigns only `CY-001` (never `CY-002`) for a 2-cyclotron heterogeneous-fleet scenario — a pre-existing cyclotron-batch-assignment distribution defect in `decision_pipeline.py`. | `cyclotron_catalog.py`, `decision_pipeline.py` | No — never imported/called by `operational_day_orchestrator.py` (verified via grep: zero matches). |
| 2 | `test_multi_cyclotron_radionuclide_authority.py::test_decay_model_supports_six_radionuclides` | `diagnostics.load_radionuclide_half_lives()` / `radionuclides.json` already contains **7** radionuclides (including `Mo-99`, needed by the Mo-99/Tc-99m generator system used for SPECT). This test's hardcoded assertion still expects exactly 6 — a stale assertion predating the Mo-99 addition. | `diagnostics.py`, `radionuclides.json` | No — I never modified either file (confirmed via `git status` diff: zero existing-file modifications across all builds this session). |
| 3 | `test_zero_capacity_propagation.py::test_partial_effective_throughput_keeps_raw_and_revenue_distinct_and_preserves_infeasible_patient_trace` | `run_native_decision_pipeline`'s own convergence loop reports `PRODUCTION_REQUIREMENT_DID_NOT_CONVERGE` (14 iterations) for a specific stressed scenario (`target_patients_per_day=50`, `transport_minutes=20.0`, `max_compensation_factor=1.3`) — entirely internal to `decision_pipeline.py`'s native convergence algorithm. | `decision_pipeline.py`, `cycle_relative_production_requirement.py` | No — `operational_day_orchestrator.py` has its own independent event/mission generation and never calls this convergence loop. |

**Verdict:** all three failures pre-date this session's Parts A–D work; none were caused, exposed, or worsened by the carrier-mass correction or the four-architecture economic comparison. No test was modified to force a pass. No production code was touched to "fix" these (per instructions: fix only genuine regressions caused by this work — none exist here).

---

## Part A — Files Changed

| File | Reason |
|---|---|
| `operational_day_orchestrator.py` | Extended (never rewritten) across four builds this session: Operating-Day orchestration → room-level closure → heterogeneous carrier correction → service-specific mass correction → this controlled four-architecture economic comparison. |
| `test_operational_day_orchestration.py` | Extended in lockstep with focused tests for every build above (currently 164 tests). |

No other repository file was modified (confirmed via `git status --short` diff against the pre-build snapshot at every stage of this session).

---

## Part B — Economic Authorities: Controlled/Common Values Actually Used

| Assumption | Value | Provenance |
|---|---|---|
| Required patients/day (`T_required`) | **200** | Section 1 governing principle |
| Operating hours/day | **18.0** | `CommonEconomicBasis.operating_hours_per_day` — USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION |
| Regular shift length | **8.0 h** | `CommonEconomicBasis.regular_shift_hours` |
| Regular coverage (2 shifts) | **16.0 h** | `resolve_shift_hours(18.0, 8.0)` — `floor(18/8)=2` full shifts |
| Overtime coverage | **2.0 h** | `18.0 − 16.0` |
| Overtime multiplier (M_OT) | **1.5×** | `CommonEconomicBasis.overtime_multiplier` |
| Operating days/year | **300** | `CommonEconomicBasis.operating_days_per_year` |
| Manual wage/hour (W) | **$17.00** | `conventional_transport_authority.PorterOperatingPolicy.base_wage_per_hour` (existing authority, reused) |
| Employer cost multiplier | **1.3×** | `PorterOperatingPolicy.loaded_employer_cost_multiplier` |
| Revenue/patient | **$300.00** | `models.PlannerAssumptions.revenue_per_scan` (existing authority, reused) |
| Discount rate | **10.0%** | `models.PlannerAssumptions.discount_rate_pct` |
| Project life | **10 years** | `models.PlannerAssumptions.analysis_years` |
| Electricity cost | **$0.12/kWh** | `CommonEconomicBasis.electricity_cost_per_kwh` — controlled assumption |
| Synthesis yield fraction | **1.0** (100%) | `models.PlannerAssumptions.synthesis_yield_fraction` (existing default) |
| Cyclotron purchase CapEx | **$3,000,000** | `models.PlannerAssumptions.cyclotron_purchase_capex` (existing authority) |
| Cyclotron installation CapEx | **$2,000,000** | `models.PlannerAssumptions.cyclotron_installation_capex` (existing authority) |
| MRT guideway unit cost | $5,000/m | `models.PlannerAssumptions.mrt_guideway_capex_per_m` (unchanged) |
| MRT vestibule cost | $30,000/unit | `canonical_spatial_authority.MRT_VESTIBULE_CAPEX_USD` (unchanged, distinct from endpoint panel) |
| MRT controls / installation | $100,000 / $300,000 (once) | `MRT_CONTROLS_CAPEX_USD` / `MRT_INSTALLATION_COMMISSIONING_CAPEX_USD` (unchanged) |
| MRT endpoint panel cost | **$1,000/endpoint** | `MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD` (established in the room-level closure build, unchanged) |
| Nuclear-shielded carrier CapEx | **$10,000/unit** | `NUCLEAR_SHIELDED_CARRIER_CAPEX_USD` (unchanged) |
| General-light carrier CapEx | **$1,000/unit** | `GENERAL_LIGHT_CARRIER_CAPEX_USD` (unchanged) |
| Nuclear carrier empty mass | **12.0 kg** | `NUCLEAR_SHIELDED_CARRIER_EMPTY_MASS_KG` (unchanged) |
| General-light carrier empty mass | **5.0 kg** | `GENERAL_LIGHT_CARRIER_EMPTY_MASS_KG` (unchanged) |
| Installed cyclotron EOB capacity | **`NOT_CALIBRATED`** | `models.PlannerAssumptions.cyclotron_eob_capacity_mbq_per_day` defaults to `None` in this repository — never fabricated. |
| Clinical labor OPEX | **`NOT_CALIBRATED`** | Scanner/injection/uptake staffing cost model not owned by this comparator (disclosed bounded scope). |
| Production OPEX / maintenance OPEX / consumables OPEX | **`NOT_CALIBRATED`** | No existing calibrated authority for these categories was found. |

`NOT_CALIBRATED` fields above are **never** silently converted to `$0` in any total — they are excluded from sums and reported explicitly (see `capex_components` / `opex_components` dictionaries below).

---

## Part C — Four-Architecture Comparison Results

### Table 1 — Summary

| Metric | Manual Conventional | Automated Conventional | MRT | Hybrid |
|---|---:|---:|---:|---:|
| Required patients/day | 200 | 200 | 200 | 200 |
| Served patients/day | 200 | 200 | 200 | 200 |
| Overall feasible | True | True | True | True |
| Total CapEx | $5,000,000 | $5,795,000 | $5,181,000 | $5,181,000 |
| Annual transport labor OPEX | $503,880 | $503,880 | $125,970 | $125,970 |
| Annual total OPEX | $503,880 | $545,292 | $125,973 | $125,973 |
| Annual revenue | $18,000,000 | $18,000,000 | $18,000,000 | $18,000,000 |
| Annual operating margin | $17,496,120 | $17,454,708 | $17,874,027 | $17,874,027 |
| Cost/patient/year | $8.40 | $9.09 | $2.10 | $2.10 |
| Payback (years) | 0.29 | 0.33 | 0.29 | 0.29 |
| NPV (10yr, 10%) | $102,506,083 | $101,456,625 | $104,647,158 | $104,647,158 |
| IRR | 349.9% | 301.2% | 345.0% | 345.0% |

### Table 2 — CapEx Components (USD)

| Component | Manual | Automated | MRT | Hybrid |
|---|---:|---:|---:|---:|
| transport_equipment | 0 | N/A | N/A | N/A |
| agv_fleet_capex | N/A | 450,000 | N/A | N/A |
| pts_network_capex | N/A | 345,000 | N/A | N/A |
| carrier_hardware_fleet_capex | N/A | N/A | 11,000 | 11,000 |
| room_endpoint_capex (170 rooms × $1,000) | N/A | N/A | 170,000 | 170,000 |
| guideway_capex | N/A | N/A | 0 | 0 |
| controls_installation_capex | N/A | N/A | 0 | 0 |
| cyclotron_capex (shared, common) | 3,000,000 | 3,000,000 | 3,000,000 | 3,000,000 |
| production_equipment_capex (shared, common) | 2,000,000 | 2,000,000 | 2,000,000 | 2,000,000 |
| **Total** | **5,000,000** | **5,795,000** | **5,181,000** | **5,181,000** |

### Table 3 — Annual OPEX Components (USD)

| Component | Manual | Automated | MRT | Hybrid |
|---|---:|---:|---:|---:|
| transport_labor_opex | 503,880 | 503,880 | 125,970 | 125,970 |
| clinical_labor_opex | NOT_CALIBRATED | NOT_CALIBRATED | NOT_CALIBRATED | NOT_CALIBRATED |
| production_opex | NOT_CALIBRATED | NOT_CALIBRATED | NOT_CALIBRATED | NOT_CALIBRATED |
| maintenance_opex | NOT_CALIBRATED | NOT_CALIBRATED | NOT_CALIBRATED | NOT_CALIBRATED |
| electricity_opex (physical, resolved) | 0 | 0 | 3.07 | 3.07 |
| consumables_opex | NOT_CALIBRATED | NOT_CALIBRATED | NOT_CALIBRATED | NOT_CALIBRATED |
| carrier_or_vehicle_opex (AGV/PTS) | 0 | 41,412 | 0 | 0 |
| other_operating_opex | 0 | 0 | 0 | 0 |
| **Total (numeric components only)** | **503,880** | **545,292** | **125,973** | **125,973** |

---

## Part D — Manual Staffing Table

| Item | Value |
|---|---|
| Operating day | 18 hr |
| Regular shift | 8 hr |
| Regular coverage | 16 hr |
| Overtime coverage | 2 hr |
| OT multiplier | 1.5× |

| Architecture | Missions/day | Worker-hours required | Simultaneous positions | Daily regular hrs | Daily OT hrs | FTE equiv. | Daily labor cost | Annual labor cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Manual Conventional | 236 | 66.87 | 4 | 64.0 | 8.0 | 10.38 | $1,679.60 | $503,880 |
| Automated Conventional (residual) | 236 | 70.24 | 4 | 64.0 | 8.0 | 10.38 | $1,679.60 | $503,880 |
| MRT (residual) | 12 | 4.65 | 1 | 16.0 | 2.0 | 2.60 | $419.90 | $125,970 |
| Hybrid (residual) | 30 | 11.63 | 1 | 16.0 | 2.0 | 2.60 | $419.90 | $125,970 |

**Verification of the required arithmetic (section 4):** for 1 simultaneous position at wage $W$: $16W + 2(1.5W) = 19W$. Directly verified: at $W=\$1.00/\text{hr}$, `compute_manual_shift_labor_cost` returns **$19.00/day** exactly. At 2 simultaneous positions: **$38.00/day** exactly (doubled).

**Note (disclosed, not a defect):** MRT and Hybrid report numerically close residual-labor figures (both round to `simultaneous_positions=1`) because both architectures' residual non-MRT workload (4.65h and 11.63h respectively) falls well under the 18-hour operating day even after Hybrid's extra linen stream is added — both saturate at the same minimum 1-position/19W-per-day cost under this bounded, average-workload-based staffing model (not a true timestamped peak-concurrency sweep). A larger demand scenario would differentiate them further.

---

## Part E — Physical Feasibility

| Architecture | Required/day | Served/day | Required EOB (PET, MBq) | Required EOB (SPECT, MBq) | Installed EOB capacity | Clinical bottleneck | Logistics bottleneck | Feasibility |
|---|---:|---:|---:|---:|---|---|---|---|
| Manual Conventional | 200 | 200 | 76,614.4 | 50,029.6 | NOT_CALIBRATED | None (bounded: not independently modeled) | None (0 unmet missions) | Feasible (production feasibility NOT_CALIBRATED, honestly disclosed) |
| Automated Conventional | 200 | 200 | 76,614.4 | 50,029.6 | NOT_CALIBRATED | None | None | Feasible (production feasibility NOT_CALIBRATED) |
| MRT | 200 | 200 | 69,035.7 | 48,465.2 | NOT_CALIBRATED | None | None | Feasible (production feasibility NOT_CALIBRATED) |
| Hybrid | 200 | 200 | 69,035.7 | 48,465.2 | NOT_CALIBRATED | None | None | Feasible (production feasibility NOT_CALIBRATED) |

**Real physical distinction (not fabricated):** MRT/Hybrid require **less** EOB activity than Manual/Automated for the *same* 140 PET + 60 SPECT patients, because MRT's nuclear transport is faster (elapsed EOB→administration ≈45.5 min vs ≈62 min for porter-based Manual/Automated), so less radioactive decay occurs before administration — a genuine, decay-driven economic consequence of architecture choice, derived from `multi_isotope_decay.retained_fraction`/`required_upstream_activity`, never from the obsolete `current_usable_doses_per_day × (1 + blocks×0.10)` formula (confirmed absent from all new code).

Since `models.PlannerAssumptions.cyclotron_eob_capacity_mbq_per_day` is `None` (uncalibrated) in this repository, **production feasibility is honestly reported as `NOT_CALIBRATED`** for every architecture — never fabricated as True or False.

---

## Part F — Five-Stream × Four-Mode Compatibility (unchanged from the room-level closure build, reused here)

| Stream | MANUAL | AGV | PTS | MRT |
|---|---|---|---|---|
| RADIOPHARMACEUTICAL_NUCLEAR | SUPPORTED | NOT_APPLICABLE | NOT_APPLICABLE | SUPPORTED |
| SPECIMEN_BLOOD | SUPPORTED | NOT_APPLICABLE | SUPPORTED | SUPPORTED |
| PHARMACY_INFUSION | SUPPORTED | SUPPORTED | SUPPORTED | NOT_CALIBRATED |
| STERILE_CLEAN_SUPPLY | SUPPORTED | SUPPORTED | NOT_APPLICABLE | NOT_CALIBRATED |
| LAUNDRY_CLEAN_LINEN | SUPPORTED | SUPPORTED | NOT_APPLICABLE | SUPPORTED |

---

## Part G — Test Results

| Suite | Result |
|---|---|
| Focused (`test_operational_day_orchestration.py`) | **164/164 passed** |
| Directly-affected regression (operating-day, MRT service class, live impact, aux systems, canonical spatial ×2, conventional transport ×3, shared MRT, whole-oncology four-architecture, OpenUSD) | **778/778 passed** |
| Full repository regression (excl. spatial benchmark) — combined Part C + Part D | *see live run result appended below* |
| Full spatial benchmark (`test_spatial_benchmark.py`) | *see live run result appended below* |

Three pre-existing failures (diagnosed in Part 0 above) are expected to persist unchanged in the full regression:
- `test_cyclotron_catalog_e2e_integration.py::test_heterogeneous_fleet_preserves_model_specific_capability_records`
- `test_multi_cyclotron_radionuclide_authority.py::test_decay_model_supports_six_radionuclides`
- `test_zero_capacity_propagation.py::test_partial_effective_throughput_keeps_raw_and_revenue_distinct_and_preserves_infeasible_patient_trace`

---

## Part H — Non-Goals Confirmed Untouched

- No UI/UX work performed.
- No second economics/carrier-mass/decay/spatial engine created.
- Universal 20 kg carrier mass **not** restored.
- Obsolete `current_usable_doses_per_day × (1 + blocks×0.10)` capacity formula **not** restored anywhere in new code.
- No fabricated cyclotron capacity, automation pricing, or unlabeled labor rates.
- Hybrid's economics are derived from its **actual** assigned missions (not a 50/50 blend — confirmed by test `test_hybrid_not_a_50_50_blend`).
- Radioactive activity is never treated as revenue; revenue is strictly `served_patients × revenue_per_patient`.
- `NOT_CALIBRATED` is never silently converted to `$0` in any total (verified by test).

---

## Part I — CSV Exports

The following CSV files were generated alongside this report (repository root):
- `four_architecture_summary.csv`
- `four_architecture_capex.csv`
- `four_architecture_opex.csv`
- `manual_staffing.csv`
- `production_chain.csv`
- `five_stream_service_paths.csv`
- `stream_mode_compatibility.csv`


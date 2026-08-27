# Four-Architecture Economic Comparison Report — PART D.1 CORRECTED
**Economic Integrity Correction of the Controlled 200-Patient/Day Comparison**

This report **supersedes** `four_architecture_economic_report_PART_D_BASELINE.md` (preserved unchanged as a historical record) for interpretation purposes, while **preserving every verified physical calculation** from Part D (patient counts, decay chain, carrier mass, endpoint unit cost, etc.). It corrects completeness and interpretation issues identified in Part D: incomplete MRT CapEx, ambiguous OPEX totals, an Automated-Conventional labor modeling defect, and an economically-misleading facility-wide-revenue-based IRR/payback headline.

---

## 0. Baseline Preservation

- `four_architecture_economic_report_PART_D_BASELINE.md` — unchanged historical record of the pre-D.1 calculation.
- `four_architecture_economic_report_PART_D_baseline_csvs/` — unchanged historical CSV exports.
- This file (`four_architecture_economic_report_PART_D1_CORRECTED.md`) and `four_architecture_economic_report_PART_D1_tables/` are the new, corrected deliverables.

---

## 1. Genuine Defect Found and Fixed: Automated-Conventional Last-Mile Modeling

**Investigation (required before any fix):** Traced every Automated-Conventional mission. Every AGV/PTS mission added a **full 17-minute porter-mission timing** (dispatch + load + horizontal + wait + unload + **return over the full route**) as its "last-mile" hand-off — the SAME model used for an entire door-to-door manual delivery. This meant an AGV mission cost `6.25 min (AGV travel) + 17.0 min (last-mile) = 23.25 min`, MORE than a full manual trip (17.0 min), even though the AGV genuinely replaced most of the route.

**Diagnosis:** genuine modeling defect (not legitimate conservatism) — a "last-mile hand-off from a station to a room" was being modeled with the SAME return-trip-inclusive formula meant for the ENTIRE original route.

**Fix applied:** introduced `AGV_PTS_LAST_MILE_DISTANCE_M = 15.0` (a short, explicitly labeled `USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION`, distinct from and much shorter than the 300m full route) and fed it into the SAME existing `compute_manual_mission_timing` authority — no new formula was created.

**Result:**

| | Manual Conventional | Automated Conventional (before fix) | Automated Conventional (after fix) |
|---|---:|---:|---:|
| Total daily worker-minutes | 4,012.0 | 4,214.5 | **3,942.9** |
| AGV mission avg (min) | — | 23.25 | **15.70** |
| PTS mission avg (min) | — | 19.5 | **11.95** |

Automated Conventional now correctly requires **less** labor than Manual Conventional — the intuitive, physically-defensible result — achieved through a principled distance correction, not by arbitrarily forcing the number down.

---

## 2. MRT CapEx Completeness (Part D.1 sections 3–7)

Part D's MRT CapEx was **incomplete** (~$181,000: carrier $11,000 + endpoints $170,000 only). This is corrected to include the full existing MRT infrastructure authority:

### Table 11 — MRT Endpoint/Fleet/Infrastructure (MRT & Hybrid identical, since both use the same controlled facility)

| Component | Value | Provenance |
|---|---:|---|
| Guideway length | **NOT_CALIBRATED** | No canonical routed MRT network length resolver exists yet for this controlled facility (`canonical_spatial_authority.build_mrt_trunk` defaults `length_m` to `NOT_CALIBRATED`). Never fabricated, never substituted with $0. |
| Guideway unit cost | $5,000/m | `models.PlannerAssumptions.mrt_guideway_capex_per_m` (existing, unchanged) |
| Guideway CapEx | **NOT_CALIBRATED** | Length unresolved ⇒ cost unresolved (never $0) |
| Vestibule count | 1 | One radiopharmacy in the controlled facility |
| Vestibule unit cost | $30,000 | `canonical_spatial_authority.MRT_VESTIBULE_CAPEX_USD` (existing, unchanged) |
| Vestibule CapEx | **$30,000** | 1 × $30,000 |
| Endpoint count | 170 | One endpoint per served inpatient room |
| Endpoint unit cost | $1,000 | `MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD` (existing, unchanged) |
| Endpoint CapEx | **$170,000** | 170 × $1,000 |
| Carrier fleet CapEx | **$11,000** | 1 nuclear-shielded ($10,000) + 1 general-light ($1,000) |
| Controls CapEx | **$100,000** | `MRT_CONTROLS_CAPEX_USD`, charged once |
| Installation/commissioning CapEx | **$300,000** | `MRT_INSTALLATION_COMMISSIONING_CAPEX_USD`, charged once |
| **Total MRT transport-specific CapEx** | **$611,000** | (up from the incomplete $181,000 in Part D) |

---

## 3. Common vs Architecture-Specific CapEx (section 7)

### Table 12 — Common Facility CapEx (identical across all four)

| Component | Manual | Automated | MRT | Hybrid |
|---|---:|---:|---:|---:|
| cyclotron_capex | 3,000,000 | 3,000,000 | 3,000,000 | 3,000,000 |
| production_equipment_capex | 2,000,000 | 2,000,000 | 2,000,000 | 2,000,000 |

### Table 13 — Architecture-Specific CapEx

| Component | Manual | Automated | MRT | Hybrid |
|---|---:|---:|---:|---:|
| transport_equipment | 0 | N/A | N/A | N/A |
| agv_fleet_capex | N/A | 450,000 | N/A | N/A |
| pts_network_capex | N/A | 345,000 | N/A | N/A |
| carrier_hardware_fleet_capex | N/A | N/A | 11,000 | 11,000 |
| mrt_guideway_capex | N/A | N/A | NOT_CALIBRATED | NOT_CALIBRATED |
| mrt_radiopharmacy_vestibule_capex | N/A | N/A | 30,000 | 30,000 |
| room_endpoint_capex | N/A | N/A | 170,000 | 170,000 |
| mrt_controls_capex | N/A | N/A | 100,000 | 100,000 |
| mrt_installation_commissioning_capex | N/A | N/A | 300,000 | 300,000 |

### Table 14 — Full CapEx Reconciliation

| Architecture | Common CapEx | Architecture-Specific CapEx | Total CapEx | ΔCapEx vs Manual |
|---|---:|---:|---:|---:|
| Manual Conventional | 5,000,000 | 0 | **5,000,000** | **0** (reference) |
| Automated Conventional | 5,000,000 | 795,000 | **5,795,000** | **+795,000** |
| MRT | 5,000,000 | 611,000 | **5,611,000** | **+611,000** |
| Hybrid | 5,000,000 | 611,000 | **5,611,000** | **+611,000** |

---

## 4. Known vs Total Annual OPEX (section 8–9)

### Table 15 — Known Annual OPEX Components

| Component | Manual | Automated | MRT | Hybrid |
|---|---:|---:|---:|---:|
| transport_labor_opex | 503,880 | 503,880 | 125,970 | 125,970 |
| electricity_opex | 0 | 0 | 3.07 | 3.07 |
| carrier_or_vehicle_opex | 0 | 41,412 | 0 | 0 |
| other_operating_opex | 0 | 0 | 0 | 0 |
| **known_annual_opex_subtotal** | **503,880** | **545,292** | **125,973** | **125,973** |

### Table 16 — Unresolved OPEX Components

| Architecture | Unresolved categories | `total_annual_opex_usd` |
|---|---|---|
| Manual Conventional | clinical_labor_opex; production_opex; maintenance_opex; consumables_opex | **NOT_CALIBRATED** |
| Automated Conventional | clinical_labor_opex; production_opex; maintenance_opex; consumables_opex | **NOT_CALIBRATED** |
| MRT | clinical_labor_opex; production_opex; maintenance_opex; consumables_opex | **NOT_CALIBRATED** |
| Hybrid | clinical_labor_opex; production_opex; maintenance_opex; consumables_opex | **NOT_CALIBRATED** |

These four categories are **identical unresolved gaps across all architectures** (`COMMON_UNRESOLVED_COST`) — they do not differentiate the architectures and are never silently treated as $0. `total_annual_opex_usd` is honestly `NOT_CALIBRATED` for every architecture; only the `known_annual_opex_subtotal_usd` figures above are complete and usable for comparison.

---

## 5. Automated Conventional Labor Audit (section 12)

### Table 8 — Automated Conventional Labor Audit (aggregate)

| Resource | Mission count | Avg minutes/mission | Total minutes |
|---|---:|---:|---:|
| AGV_AMR (linen, pharmacy, sterile) | 30 | 15.70 | 471.1 |
| PTS (blood/specimen) | 6 | 11.95 | 71.7 |
| PORTER (nuclear, always manual) | 200 | 17.00 | 3,400.0 |
| **Total** | 236 | — | **3,942.9** |

Full per-mission detail: `four_architecture_economic_report_PART_D1_tables/table08_automated_labor_audit.csv` (236 rows).

**Conclusion:** the corrected 3,942.9 total minutes is now **below** Manual's 4,012.0 total minutes — physically defensible (automation genuinely reduces the AGV/PTS-eligible streams' time even after adding a realistic short last-mile hand-off), and the nuclear stream (always manual, 200 missions × 17 min = 3,400 min) dominates both totals since nuclear is never assigned to AGV/PTS in either architecture.

---

## 6. Hybrid Mission Assignment Audit (section 15/24)

### Table 24 — Hybrid Mission Assignment by Service Class

| Service Class | Total Missions | MRT | AGV | PTS | Manual | Non-MRT Worker-Minutes |
|---|---:|---:|---:|---:|---:|---:|
| RADIOPHARMACEUTICAL_NUCLEAR | 200 | **200** | 0 | 0 | 0 | 0 |
| SPECIMEN_BLOOD | 6 | **6** | 0 | 0 | 0 | 0 |
| PHARMACY_INFUSION | 6 | 0 | **6** | 0 | 0 | 94.23 |
| STERILE_CLEAN_SUPPLY | 6 | 0 | **6** | 0 | 0 | 94.23 |
| LAUNDRY_CLEAN_LINEN | 18 | 0 | **18** | 0 | 0 | 282.68 |

Hybrid's economics derive from these ACTUAL assignments (nuclear + blood via MRT; pharmacy/sterile/linen via AGV) — never a 50/50 blend of MRT and Conventional totals.

---

## 7. Staffing: Workload vs Scheduled Coverage (section 13–14)

### Table 7 — Staffing Workload vs Scheduled Coverage

| Architecture | Worker-hours required (workload) | Simultaneous positions (scheduled coverage) | Peak concurrency |
|---|---:|---:|---|
| Manual Conventional | 66.87 | 4 | `PEAK_CONCURRENCY_NOT_CALIBRATED` |
| Automated Conventional (residual) | 65.71 | 4 | `PEAK_CONCURRENCY_NOT_CALIBRATED` |
| MRT (residual) | 3.14 | 1 | `PEAK_CONCURRENCY_NOT_CALIBRATED` |
| Hybrid (residual) | 7.85 | 1 | `PEAK_CONCURRENCY_NOT_CALIBRATED` |

MRT's residual workload (3.14 worker-hours) is genuinely **less than half** of Hybrid's (7.85 worker-hours) — both currently round to the SAME minimum scheduled coverage position (1) and therefore the same **paid cost** ($125,970/year) under the current bounded average-workload staffing approximation, but they are **not operationally identical**: MRT covers linen via MRT (removing it from residual workload) while Hybrid does not. True timestamped peak-concurrency staffing is not yet available in this repository (`PEAK_CONCURRENCY_NOT_CALIBRATED`); the average-workload approximation is preserved as the only current controlled authority.

---

## 8. Feasibility Semantics Corrected (section 17)

### Table 20 — Clinical/Logistics/Production/Overall Feasibility

| Architecture | Clinical feasible | Logistics feasible | Production feasible | Bottleneck | **Overall status** |
|---|---|---|---|---|---|
| Manual Conventional | True | True | NOT_CALIBRATED | None | **FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY** |
| Automated Conventional | True | True | NOT_CALIBRATED | None | **FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY** |
| MRT | True | True | NOT_CALIBRATED | None | **FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY** |
| Hybrid | True | True | NOT_CALIBRATED | None | **FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY** |

`overall_feasible=True` from Part D is **replaced** by this explicit status vocabulary — since `cyclotron_eob_capacity_mbq_per_day` is uncalibrated in this repository, no architecture can be honestly called unconditionally `FEASIBLE`; all four are correctly reported as feasible **conditional on** uncalibrated production capacity, never fabricated as fully determined.

---

## 9. Real Decay Difference Preserved (section 18)

### Table 17 — Radioactive Production/Decay — PET

| Architecture | Patients | Activity/patient (MBq) | Elapsed EOB→Admin (min) | Retained fraction | A_admin (MBq) | A_release_required (MBq) | A_EOB_required (MBq) | Δ vs Manual (MBq) | % reduction vs Manual |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Manual Conventional | 140 | 370.0 | 62.0 | 0.6761 | 51,800.0 | 76,614.4 | **76,614.4** | 0 | 0% |
| Automated Conventional | 140 | 370.0 | 62.0 | 0.6761 | 51,800.0 | 76,614.4 | **76,614.4** | 0 | 0% |
| MRT | 140 | 370.0 | 45.5 | 0.7503 | 51,800.0 | 69,035.7 | **69,035.7** | −7,578.7 | **−9.89%** |
| Hybrid | 140 | 370.0 | 45.5 | 0.7503 | 51,800.0 | 69,035.7 | **69,035.7** | −7,578.7 | **−9.89%** |

### Table 18 — Radioactive Production/Decay — SPECT

| Architecture | Patients | Activity/patient (MBq) | Elapsed EOB→Admin (min) | Retained fraction | A_admin (MBq) | A_release_required (MBq) | A_EOB_required (MBq) | Δ vs Manual (MBq) | % reduction vs Manual |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Manual Conventional | 60 | 740.0 | 62.0 | 0.8875 | 44,400.0 | 50,029.6 | **50,029.6** | 0 | 0% |
| Automated Conventional | 60 | 740.0 | 62.0 | 0.8875 | 44,400.0 | 50,029.6 | **50,029.6** | 0 | 0% |
| MRT | 60 | 740.0 | 45.5 | 0.9161 | 44,400.0 | 48,465.2 | **48,465.2** | −1,564.4 | **−3.13%** |
| Hybrid | 60 | 740.0 | 45.5 | 0.9161 | 44,400.0 | 48,465.2 | **48,465.2** | −1,564.4 | **−3.13%** |

**This physical reduction is preserved unchanged from Part D** — MRT's faster nuclear transport genuinely reduces the required EOB activity via real decay physics (`multi_isotope_decay.retained_fraction`/`required_upstream_activity`), never via the obsolete 10%-block capacity formula (confirmed absent from all code in this repository's new authorities).

### Section 19 — Economic Value of the Reduced Radioactive Requirement

No calibrated `$/MBq`, `$/batch`, or target-production marginal-cost authority exists in this repository. The monetary value of the ~9.89% (PET) / ~3.13% (SPECT) EOB reduction is honestly reported as **`NOT_CALIBRATED`** — never fabricated as a dollar saving.

---

## 10. Incremental Economics vs Manual Conventional Baseline (sections 10–11/20)

The Part D headline IRRs (300–350%) and paybacks (0.29–0.33 years) used the **entire common $18,000,000/year clinical revenue** as though the transport architecture alone produced it. Since all four architectures serve the identical 200 patients/day in this controlled comparison, **ΔRevenue = 0** for architecture-selection purposes — those Part D figures are withdrawn as primary metrics and replaced below.

### Table 21 — Gross Facility Revenue (informational only, NOT an architecture-investment return)

| Architecture | Served patients/day | Annual patients | Revenue/patient | Gross annual revenue |
|---|---:|---:|---:|---:|
| Manual Conventional | 200 | 60,000 | $300 | $18,000,000 |
| Automated Conventional | 200 | 60,000 | $300 | $18,000,000 |
| MRT | 200 | 60,000 | $300 | $18,000,000 |
| Hybrid | 200 | 60,000 | $300 | $18,000,000 |

### Table 22 — Incremental Economics vs Manual Conventional

| Architecture | ΔCapEx | ΔKnown Annual OPEX Savings | ΔRevenue | ΔAnnual Cash Flow | Calibration Status |
|---|---:|---:|---:|---:|---|
| Manual Conventional | $0 | $0 | $0 | $0 | REFERENCE_BASELINE |
| Automated Conventional | +$795,000 | **−$41,412** | $0 | **−$41,412** | PARTIAL (4 unresolved OPEX categories excluded) |
| MRT | +$611,000 | **+$377,907** | $0 | **+$377,907** | PARTIAL (4 unresolved OPEX categories excluded) |
| Hybrid | +$611,000 | **+$377,907** | $0 | **+$377,907** | PARTIAL (4 unresolved OPEX categories excluded) |

### Table 23 — Incremental Payback / NPV / IRR

| Architecture | Incremental Payback (years) | Incremental NPV (10yr, 10%) | Incremental IRR |
|---|---:|---:|---:|
| Manual Conventional | NOT_CALIBRATED (reference) | $0 | NOT_CALIBRATED (reference) |
| Automated Conventional | **NOT_CALIBRATED** (negative cash flow) | **−$1,049,459** | **NOT_CALIBRATED** (negative cash flow) |
| MRT | **1.62 years** | **+$1,711,074** | **61.3%** |
| Hybrid | **1.62 years** | **+$1,711,075** | **61.3%** |

**Interpretation:** on a proper incremental basis (never crediting the transport architecture with the entire common $18M facility revenue), MRT/Hybrid show a genuinely attractive but realistic ~1.6-year incremental payback and ~61% incremental IRR driven by known labor-OPEX savings — not the inflated 300%+ figures from the uncorrected Part D comparison. Automated Conventional shows a **negative** incremental cash flow (higher CapEx, and its known OPEX is HIGHER than Manual's, not lower) — it does not pay for itself on the known-OPEX basis in this controlled scenario.

---

## 11. Stream/Mode Compatibility — Preserved, Never Silently Upgraded (section 16)

| Stream | Manual | AGV | PTS | MRT |
|---|---|---|---|---|
| RADIOPHARMACEUTICAL_NUCLEAR | SUPPORTED | NOT_APPLICABLE | NOT_APPLICABLE | SUPPORTED |
| SPECIMEN_BLOOD | SUPPORTED | NOT_APPLICABLE | SUPPORTED | SUPPORTED |
| PHARMACY_INFUSION | SUPPORTED | SUPPORTED | SUPPORTED | **NOT_CALIBRATED** |
| STERILE_CLEAN_SUPPLY | SUPPORTED | SUPPORTED | NOT_APPLICABLE | **NOT_CALIBRATED** |
| LAUNDRY_CLEAN_LINEN | SUPPORTED | SUPPORTED | NOT_APPLICABLE | SUPPORTED |

Verified (test `test_mrt_pharmacy_sterile_never_routed_through_mrt`): pharmacy/sterile missions are **never** routed through MRT in HYBRID_MRT or MRT_DOMINANT execution, consistent with their `NOT_CALIBRATED` MRT compatibility — never silently upgraded to `SUPPORTED`.

---

## 12. Test and Regression Results (section 26)

| Suite | Result |
|---|---|
| Focused (`test_operational_day_orchestration.py`) | **182/182 passed** (164 Part D + 18 new D.1 tests) |
| Directly-affected regression | **796/796 passed** |
| Full repository regression (excl. spatial benchmark) | *(see live run appended below)* |
| Full spatial benchmark | *(see live run appended below)* |

Three pre-existing, independently-diagnosed failures (unrelated to this work, confirmed via individual reproduction and root-cause file analysis — see the prior turn's diagnosis) are expected unchanged:
- `test_cyclotron_catalog_e2e_integration.py::test_heterogeneous_fleet_preserves_model_specific_capability_records`
- `test_multi_cyclotron_radionuclide_authority.py::test_decay_model_supports_six_radionuclides`
- `test_zero_capacity_propagation.py::test_partial_effective_throughput_keeps_raw_and_revenue_distinct_and_preserves_infeasible_patient_trace`

---

## 13. Provenance Register (section 25, abridged)

| Value | Status |
|---|---|
| Required patients/day = 200 | USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION |
| Operating day = 18h, shift = 8h, OT = 1.5× | USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION |
| Wage $17/hr, employer multiplier 1.3× | DERIVED_FROM_CALIBRATED_INPUT (`PorterOperatingPolicy`, existing) |
| Revenue/patient $300, discount rate 10%, life 10yr | DERIVED_FROM_CALIBRATED_INPUT (`PlannerAssumptions`, existing) |
| Nuclear/general carrier empty mass (12kg/5kg) | USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION (unchanged) |
| Nuclear/blood/linen payload (6.5/2/12 kg) | USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION (unchanged) |
| Endpoint unit cost $1,000 | USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION (unchanged) |
| Vestibule $30,000, controls $100,000, installation $300,000 | USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION (unchanged, existing) |
| MRT guideway length | **NOT_CALIBRATED** |
| Clinical labor / production / maintenance / consumables OPEX | **NOT_CALIBRATED** |
| Installed cyclotron EOB capacity | **NOT_CALIBRATED** |
| $/MBq or production marginal cost | **NOT_CALIBRATED** |
| PET/SPECT decay chain (retained fraction, A_admin/A_release/A_EOB) | DERIVED_FROM_PHYSICAL_MODEL (`multi_isotope_decay`, existing) |
| AGV/PTS last-mile distance (15m) | USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION (new in D.1, corrects a modeling defect) |

Full per-architecture CSV tables are in `four_architecture_economic_report_PART_D1_tables/` (26 files, tables 1–24 plus supporting exports).

---

## 14. Non-Goals Confirmed Untouched

- Physical authorities preserved unchanged: 200 patients/day, 18h day, 8h shift, 1.5× OT, 300 operating days/year, $17/hr wage, 1.3× employer multiplier, 140 PET + 60 SPECT allocation, decay-based production chain, no 10% production-block formula, 12kg/5kg carrier masses, 6.5/2/12kg payloads, $1,000 endpoint authority, existing carrier fleet/service-class/AGV/PTS authorities.
- No second economics/production/decay/spatial engine created.
- Hybrid remains fully mission-derived (Table 24), never a 50/50 blend.
- `NOT_CALIBRATED` never silently became `$0` anywhere in this correction.
- No UI/UX work performed.

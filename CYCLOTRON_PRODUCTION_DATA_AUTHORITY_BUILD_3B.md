# CYCLOTRON PRODUCTION DATA AUTHORITY — BUILD 3B

**Status: repository-grounded engineering authority report (audit + focused regression).**
**Baseline: `main` @ `9a04dc5` (Build 3A complete, committed). No production code changed by Build 3B.**

This document records exactly what MRT Pharma **currently knows** about
radionuclide production, patient demand, batch formation, production-source
assignment, and the downstream clinical resource chain. It distinguishes
IMPLEMENTED / CALIBRATED / REFERENCE_POINT / PROJECT_SUPPLIED /
PARTIALLY_CALIBRATED / NOT_CALIBRATED / CONTROLLED_BENCHMARK / DISCONNECTED /
MISSING. It does not describe intended future behavior as existing behavior.
No external data was fabricated; missing data is left `NOT_CALIBRATED` and
listed for controlled future research.

Legend:

| Term | Meaning |
|---|---|
| CALIBRATED | manufacturer/verified numeric production value present |
| REFERENCE_POINT | a single calibrated condition, NOT unconditional daily capacity |
| PROJECT_SUPPLIED | value supplied by project references, not manufacturer-calibrated |
| PARTIALLY_CALIBRATED | some fields present, capacity not fully derivable |
| NOT_CALIBRATED | no defensible numeric production value present |
| CONTROLLED_BENCHMARK | fixed scenario constant, not facility/project-derived |
| DISCONNECTED | authority exists but is not wired into the consuming path |
| MISSING | no authority/field exists |

---

## 0. CANONICAL AUTHORITY MAP

One canonical authority per concern. No parallel catalogs/models were created.

| Concern | Canonical authority | File |
|---|---|---|
| CANONICAL_CYCLOTRON_AUTHORITY | `CyclotronCatalogModel` / `CyclotronCatalog` | `cyclotron_catalog.py` + `cyclotron_equipment_catalog.json` |
| CANONICAL_GENERATOR_AUTHORITY | `GeneratorCatalogModel` / `GeneratorCatalog` | `generator_catalog.py` + `generator_equipment_catalog.json` |
| CANONICAL_PRODUCTION_RECORD_AUTHORITY | `ProductionPerformanceRecord` + `_resolve_calibrated_eob_by_radionuclide` | `cyclotron_catalog.py` |
| CANONICAL_PATIENT_DEMAND_AUTHORITY | `PatientRadionuclideDemand` | `patient_radionuclide_demand.py` |
| CANONICAL_BATCH_AUTHORITY (cyclotron) | `RadionuclideBatchDemand` | `patient_radionuclide_demand.py` |
| CANONICAL_BATCH_AUTHORITY (generator) | `PreparationBatch` | `generator.py` |
| CANONICAL_SCANNER_AUTHORITY | `ScannerCatalogModel` / `ScannerCatalog` | `scanner_catalog.py` + `scanner_equipment_catalog.json` |
| CANONICAL_PRODUCTION_CAPACITY_RESOLVER | `_resolve_physical_eob_capacity_mbq_per_day` → `resolve_fleet_eob_capacity_mbq_per_day` | `equal_budget.py` → `cyclotron_production_windows.py` |
| ACTIVITY CHAIN (per-patient) | `derive_cycle_relative_requirement` | `cycle_relative_production_requirement.py` |
| DECAY PRIMITIVES | `retained_fraction`, `required_upstream_activity` | `multi_isotope_decay.py` |

---

## 1. GOVERNING PRINCIPLE — SUPPORTED ≠ CALIBRATED ≠ CAPACITY

Three independent dimensions are kept strictly separate in code and in this
report:

- **Equipment specification** (energy, current, targets, dimensions) — stored
  in `CyclotronCatalogModel.field_provenance`.
- **Radionuclide production calibration** (cycle minutes, EOB activity,
  performance records) — stored in `production_cycle_minutes_by_radionuclide`
  and `production_performance_records`.
- **Economic/OPEX calibration** — a separate concern (generator economics,
  scanner economics), not part of production capacity.

A model may declare a radionuclide as **supported** yet have its production
capacity **NOT_CALIBRATED**. This is legitimate and is the exact CYPRIS MP-30
case (Section B).

There is **no single "cyclotron calibrated" boolean**. The relevant
`CyclotronCatalogModel` properties are independent:

- `has_calibrated_radionuclide_capability` → `bool(supported_radionuclides)`
  (a SUPPORT flag, **not** a capacity flag).
- `has_production_cycles_for_supported_radionuclides` → all supported isotopes
  have a cycle time.
- `schedulable_radionuclides` → supported ∩ cycle-map.
- `production_calibration_status` → `manufacturer_calibrated` iff a
  manufacturer-calibrated numeric EOB record exists; else `modeled` if
  schedulable; else `not_calibrated`.

---

## A. COMPLETE CYCLOTRON × RADIONUCLIDE TABLE

Every cataloged model and every declared radionuclide from
`cyclotron_equipment_catalog.json` (schema_version `1.1`, 17 models). "Cycle"
= entry present in `production_cycle_minutes_by_radionuclide`. "Reference EOB"
= `ProductionPerformanceRecord.normalized_eob_activity_mbq`. Energy/current are
from `field_provenance` (equipment spec); `—` means not individually declared
for that isotope.

| Manufacturer | Model | Radionuclide | Supported | Beam Energy | Beam Current | Cycle (min) | Reference EOB | Prod. Calibration Status |
|---|---|---|---|---|---|---|---|---|
| GE HealthCare | PETtrace 840 | F-18 | YES | 16.5 MeV | 60 µA | 120.0 | 240,000 MBq (240 GBq) | CALIBRATED (REFERENCE_POINT) |
| GE HealthCare | PETtrace 860 | F-18 | YES | 16.5 MeV | 100 µA | 120.0 | 403,000 MBq (403 GBq) | CALIBRATED (REFERENCE_POINT) |
| GE HealthCare | PETtrace 880 | F-18 | YES | 16.5 MeV | 130 µA | 120.0 | 524,000 MBq (524 GBq) | CALIBRATED (REFERENCE_POINT) |
| GE HealthCare | PETtrace 890 | F-18 | YES | 16.5 MeV | 160 µA | 120.0 | 648,000 MBq (648 GBq) | CALIBRATED (REFERENCE_POINT) |
| GE HealthCare | PETtrace 800 | F-18 | YES | — | — | 50.0 | null | NOT_CALIBRATED (target-system ref only) |
| GE HealthCare | PETtrace 800 | C-11 | YES | — | — | 20.0 | null | NOT_CALIBRATED |
| GE HealthCare | PETtrace 800 | N-13 | YES | — | — | 15.0 | null | NOT_CALIBRATED |
| GE HealthCare | PETtrace 800 | O-15 | YES | — | — | 8.0 | null | NOT_CALIBRATED |
| GE HealthCare | PETtrace 800 | Ga-68 | YES | — | — | 45.0 | null | NOT_CALIBRATED |
| IBA | Cyclone KEY | F-18 | YES | 9.2 MeV | 100 µA | 120.0 | 111,000 MBq (111 GBq) | CALIBRATED (REFERENCE_POINT) |
| IBA | Cyclone KEY | N-13 | YES | 9.2 MeV | 100 µA | — (no cycle) | null | NOT_CALIBRATED (not schedulable) |
| IBA | Cyclone KEY | C-11 | YES | 9.2 MeV | 100 µA | — (no cycle) | null | NOT_CALIBRATED (not schedulable) |
| IBA | Cyclone KIUBE | F-18 | YES | 18.0 MeV | — (null) | 120.0 | 1,406,000 MBq (38 Ci) | CALIBRATED (REFERENCE_POINT; see caveat) |
| IBA | Cyclone KIUBE | Ga-68, Zr-89, Cu-64, N-13, C-11, O-15, I-123, I-124 | YES | 18.0 MeV | — | — (no cycle) | null | NOT_CALIBRATED (not schedulable) |
| IBA | Cyclone IKON | Cu-64, Ge-68, I-123, Tl-201, Zr-89, F-18, Ga-68, I-124 | YES | 13–30 MeV | ≤1500 µA | — (empty) | null | NOT_CALIBRATED |
| IBA | Cyclone 30XP | F-18, Cu-64, Zr-89, Ge-68, I-123, In-111, Tl-201, At-211 | YES | 15–30 MeV (p) | ≤400 µA (p) | — (empty) | null | NOT_CALIBRATED |
| Sumitomo Heavy Industries | CYPRIS HM-12 | F-18, C-11, N-13, O-15, Ga-68, Cu-64, Zr-89, I-123, I-124 | YES | 12 MeV (p) | — | — (empty) | null | NOT_CALIBRATED |
| Sumitomo Heavy Industries | CYPRIS HM-20 | F-18, C-11, N-13, O-15, Ga-68, Cu-64, Zr-89, I-123, I-124 | YES | 20 MeV (p) | — | — (empty) | null | NOT_CALIBRATED |
| **Sumitomo Heavy Industries** | **CYPRIS MP-30** | **F-18, Cu-64, Zr-89, I-123, I-124, Ga-68** | **YES** | **— (literature only)** | **—** | **— (empty)** | **null** | **NOT_CALIBRATED (control case)** |
| Siemens/CTI | Eclipse HP | F-18, C-11, N-13, O-15 | YES | 11 MeV (lit.) | 60 µA (lit.) | — (empty) | null | NOT_CALIBRATED (literature energy only) |
| Siemens/CTI | RDS-111 | F-18, C-11, N-13, O-15 | YES | 11 MeV (lit.) | 60 µA (lit.) | — (empty) | null | NOT_CALIBRATED |
| ACSI | TR-19 | F-18, C-11, N-13, O-15, Cu-64, Zr-89, I-124 | YES | 14–19 MeV | 300 µA (site) | — (empty) | null | NOT_CALIBRATED |
| ACSI | TR-24 | F-18, C-11, N-13, O-15, Cu-64, Zr-89, I-124 | YES | 18–24 MeV | 300 µA | — (empty) | null | NOT_CALIBRATED |
| Best Cyclotron Systems | Best 14p | F-18 | YES | 14 MeV (lit.) | — | — (empty) | null | NOT_CALIBRATED |

### Calibration tier summary

- **CALIBRATED F-18 reference point** (feeds physical capacity): PETtrace
  840 / 860 / 880 / 890, Cyclone KEY, Cyclone KIUBE — **6 models, F-18 only**.
  (Locked by test `test_calibrated_f18_model_set_is_exactly_the_six_known_models`.)
- **KIUBE caveat**: its F-18 record has `beam_current_ua = null`. If a site
  supplies `site_operating_current_ua`, `_resolve_calibrated_eob_by_radionuclide`
  narrows by beam current and would then **exclude** this record. With no site
  current supplied, the record is used.
- **PETtrace 800**: cycle times populated for 5 isotopes, but **every**
  performance record has null yields (`calibration_status: not_calibrated`).
  Schedulable (has cycles) but has **no calibrated EOB** → contributes
  `unknown_assets` to the resolver, never a numeric capacity.
- **All other 10 models**: empty cycle map **and** empty performance records →
  `NOT_CALIBRATED`, not schedulable.

**No radionuclide other than F-18 has any calibrated EOB record anywhere in
the catalog.** (Locked by test
`test_no_non_f18_radionuclide_has_calibrated_eob_anywhere`.)

---

## B. CYPRIS MP-30 CONTROL (Section 8)

Empirically verified from the physical repository; locked by tests
`test_cypris_mp30_f18_supported_but_production_not_calibrated`,
`test_cypris_mp30_builds_no_fleet_and_emits_warning`,
`test_cypris_mp30_never_infers_capacity_from_energy_or_current`.

```
CYPRIS_MP30_F18_SUPPORTED             = YES
CYPRIS_MP30_F18_PRODUCTION_STATUS     = NOT_CALIBRATED
CYPRIS_MP30_F18_REFERENCE_EOB         = null (no performance record)
CYPRIS_MP30_F18_REFERENCE_CYCLE       = null (production_cycle_minutes_by_radionuclide = {})
CYPRIS_MP30_F18_DAILY_CAPACITY_STATUS = NOT_CALIBRATED
```

Mechanism: `supported_radionuclides` non-empty, but
`production_cycle_minutes_by_radionuclide = {}` →
`schedulable_radionuclides = ()` → `build_cyclotron_asset_from_instance`
returns `None` → `build_fleet_from_instances` returns `(None, warning)`:
*"CY-001 (Sumitomo Heavy Industries CYPRIS MP-30) does not have calibrated
radionuclide and cycle data for scheduling."* Physical EOB capacity is **not
applied**; F-18 production is not inferred from MeV or beam-current class.

---

## C. POSITIVE PRODUCTION CONTROL (Section 9)

`GE_PETTRACE_840` (repository evidence only). Locked by test
`test_pettrace_840_positive_control_calibrated_and_resolves`.

| Field | Value |
|---|---|
| manufacturer / model | GE HealthCare / PETtrace 840 |
| radionuclide | F-18 |
| EOB activity | 240,000 MBq (reported 240 GBq) |
| units | GBq → MBq via `_normalize_activity_to_mbq` (×1000) |
| irradiation duration | 120.0 min |
| beam current | 60.0 µA |
| calibration classification | `manufacturer_calibrated` |

Resolved fleet capacity (verified): 1 window → 240,000 MBq/day; 2 windows →
480,000 MBq/day; 5 windows → 1,200,000 MBq/day; status
`schedule_derived_capacity`. The record's own `notes`: *"Calibration input
only; not unconditional facility MBq/day capacity."* — a REFERENCE_POINT.
The 840/860/880/890 records under different beam currents are preserved
**separately**, never flattened.

---

## D. RADIONUCLIDE-SPECIFIC RESOLUTION (Section 7)

`_resolve_calibrated_eob_by_radionuclide` binds a record to an isotope only
when `radionuclide` matches, `calibration_status == "manufacturer_calibrated"`,
`normalized_eob_activity_mbq` is present, `|irradiation_time_minutes −
target_cycle| ≤ 1e-9`, and (if supplied) beam current matches. One
radionuclide's record is never reused for another; a mismatched cycle yields
no capacity. Locked by
`test_calibrated_eob_resolution_is_radionuclide_and_cycle_specific`.

---

## E. PATIENT → RADIONUCLIDE → ACTIVITY → EOB (Sections 10–11)

**Direction is demand-derived** (clinical need → radionuclide), per
`engineering_authority.py` AuthorityRule `PRODUCTION_CHAIN`.

`PatientRadionuclideDemand`:

| Field | Present | Classification |
|---|---|---|
| patient_id | YES | IMPLEMENTED |
| radionuclide | YES (validated vs canonical half-life table) | IMPLEMENTED |
| prescribed_activity_mbq | YES | IMPLEMENTED |
| clinical_resource_mode | YES | IMPLEMENTED |
| administered vs prescribed distinction | NO | MISSING |
| administration time/window | NO (supplied downstream via map) | PARTIAL |
| modality (PET/SPECT) | NO (on `NuclearProcedureAssignment` / `NuclearAppointment`) | RESOLVED elsewhere |

**Activity chain**: per-patient heterogeneous EOB via
`derive_cycle_relative_requirement` (`A_EOB,p = A_admin,p / R(EOB→admin)`,
summed per cycle) — never `patient_count × generic_dose`. The synthesis-yield
three-step `A_admin → A_release → A_EOB` lives in the `equal_budget.py`
aggregate pathway. Locked by
`test_patient_demand_groups_preserve_heterogeneous_activity_sum`,
`test_activity_chain_admin_to_eob_is_decay_compensated_per_patient`,
`test_cycle_relative_requirement_sums_per_patient_eob`.

Classification: **RESOLVED** (per-patient EOB); **PARTIALLY_RESOLVED** (single
unified A_release — two coexisting representations).

---

## F. PATIENTS → BATCHES (Sections 12–13)

`RadionuclideBatchDemand` fields and gaps:

| Concept | On batch record? | Where it lives |
|---|---|---|
| batch_id (int) | YES | — |
| radionuclide | YES | — |
| patient IDs | YES | — |
| patient_count | YES | — |
| total_prescribed_activity_mbq | YES (aggregate prescribed) | — |
| required release activity | GAP | not stored on batch |
| required EOB activity | GAP | `cycle_relative_production_requirement` (per cycle) |
| assigned source | GAP | `BatchCyclotronAssignment` (out-of-band) |
| production start/EOB/release time | GAP | `ProductionWindow` / `CandidateProductionCycle` |
| production status | GAP | `CyclotronFleetProductionSchedule` |

Generator parallel: `PreparationBatch` (`generator.py`), `batch_id` is a
**string** (vs int for cyclotron).

Batch-formation coverage — fallback `partition_facility_day_patient_demand`
vs planner cycle-aware path (`production_clinical_schedule.py` +
`derive_cycle_relative_requirement`):

| Concept | Fallback | Cycle-aware |
|---|---|---|
| radionuclide compatibility | IMPLEMENTED | IMPLEMENTED |
| patient cohort/count | IMPLEMENTED | PARTIAL |
| administration timing | NOT_IMPLEMENTED | IMPLEMENTED |
| required activity | PARTIAL | IMPLEMENTED |
| decay | NOT_IMPLEMENTED | IMPLEMENTED |
| production-cycle timing | NOT_IMPLEMENTED | IMPLEMENTED |
| production-source compatibility | NOT_IMPLEMENTED | PARTIAL |

Locked by `test_batch_partition_is_per_radionuclide_and_preserves_patient_ids`.

---

## G. BATCH → CYCLOTRON / GENERATOR (Section 14)

Cyclotron: `assign_batches_to_cyclotron_fleet` assigns `B_j → CY_k` **only if**
`CY_k` supports the batch radionuclide (else raises), using deterministic
earliest-finish. Window sharing gated by
`simultaneously_compatible_radionuclide_sets` bounded by
`max_simultaneous_production_streams`. Locked by
`test_batch_assignment_requires_radionuclide_support`.

Generator: separate authority
(`assign_spect_patients_to_generator_batch` → one elution → one
`PreparationBatch` → N doses; `SpectDoseLineage`), never forced through
beam/EOB semantics. Source feasibility split:
`evaluate_cyclotron_source_feasibility` vs
`evaluate_generator_source_feasibility` (`nuclear_source.py`).

---

## H. DAILY CAPACITY DERIVATION & CONCURRENCY (Sections 16–18)

- Daily capacity is **not** `24h / cycle × EOB`. It is
  `calibrated_per_cycle × feasible_scheduled_windows`
  (`resolve_fleet_schedule_derived_eob_capacity_mbq`), only when a calibrated
  per-cycle EOB exists. Missing operational assumptions keep the result a
  REFERENCE_POINT / schedule-derived value.
- **Multiple supported radionuclides ≠ simultaneous production.** Concurrency
  is governed by `max_simultaneous_production_streams` and explicit
  `simultaneously_compatible_radionuclide_sets`; never inferred from the length
  of `supported_radionuclides`.

---

## I. GENERATOR PARITY (Section 19)

| Item | Finding |
|---|---|
| Identity/models | Mo-99/Tc-99m only: CURIUM_TECHNELITE, CURIUM_ULTRA_TECHNEKOW_FM, GE_HEALTHCARE_DRYTEC |
| Supported radionuclide | parent Mo-99 → daughter Tc-99m |
| **Ge-68/Ga-68 generator** | **MISSING** — Ga-68 is only cyclotron-produced |
| Availability/preparation | elution → `PreparationBatch` → release after preparation |
| Supply/calibration status | catalog economics `NOT_CALIBRATED`; at best `literature_calibrated` |
| Economic layer | `generator_economics.py`: controlled `$3,500/delivery` OPEX; `generator_delivery_new_study_capex` always `0.0` |

Locked by `test_generator_catalog_is_mo99_tc99m_and_economics_not_calibrated`.

---

## J. END-TO-END TRACEABILITY MATRIX (Sections 20–24)

Chain: Patient → Batch → Source → Release → Transport → Injection → Uptake →
Scanner → Completed Patient.

| Hop | Status | Authority |
|---|---|---|
| patient_id → radionuclide → prescribed activity | RESOLVED | `PatientRadionuclideDemand` |
| → batch_id | RESOLVED | `RadionuclideBatchDemand` / `PreparationBatch` |
| → cyclotron/generator | RESOLVED | `assign_batches_to_cyclotron_fleet` / generator path |
| → required EOB activity | RESOLVED (per cycle) | `derive_cycle_relative_requirement` |
| → release activity/time | PARTIALLY_RESOLVED | timing on cycle; unified A_release split |
| → transport assignment | PARTIALLY_RESOLVED | transport authorities (per architecture) |
| → injection resource | RESOLVED (occupancy) | `compute_clinical_resource_peak_occupancy` (test-only wiring) |
| → uptake resource | RESOLVED (occupancy) | same |
| → scanner + modality | RESOLVED | `clinical_resource_identity` modality-tagged pool |
| → scan time | PARTIAL | `assumptions.scanner_cycle_min` (catalog acquisition minutes not wired) |

### Modality (Section 21)

```
PATIENT_MODALITY_SOURCE            = clinical procedure record
                                     (NuclearProcedureAssignment.modality / NuclearAppointment.modality)
RADIONUCLIDE_TO_MODALITY_AUTHORITY = DOES NOT EXIST (no radionuclide→modality table)
SCANNER_ASSIGNMENT_AUTHORITY       = clinical_resource_identity.py (modality-tagged scanner pool)
```

Modality is **authored on the procedure/patient record** and independently
**declared** on scanner equipment. Never inferred from the radionuclide;
if anything, radionuclide is derived from modality via
`PET_RADIONUCLIDE = "F-18"` / `SPECT_RADIONUCLIDE = "Tc-99m"`
(`oncology_pet_spect_scenario.py`).

### Scanner / injection / uptake resource authority (Sections 22–23)

- Throughput formulas: `engineering.scanner_capacity(n,h,cycle,availability)`,
  `engineering.room_capacity(n,h,service)`.
- In `equal_budget.py` these are **first-class binding constraints**:
  `achieved = min(scanner_cap, injection_cap, uptake_cap, production_cap)`.
- In the four-architecture module the benchmark quantities are **HARDCODED
  literals** in `_nuclear_result`
  (`whole_oncology_four_architecture_optimization.py`, ~line 952):
  `scanners=6, injection_resources=6, uptake_resources=12`.
  Classification: **CONTROLLED_BENCHMARK** functionally, implemented as bare
  inline literals. **Verified from physical code. NOT changed in Build 3B.**

### Throughput join / feasibility wiring (Sections 24–25)

```
PRODUCTION_THROUGHPUT_AUTHORITY   = DISCONNECTED (four-arch); CONNECTED (equal_budget min-join)
TRANSPORT_THROUGHPUT_AUTHORITY    = DISCONNECTED (four-arch, test-only occupancy)
INJECTION_THROUGHPUT_AUTHORITY    = DISCONNECTED (four-arch); CONNECTED (equal_budget)
UPTAKE_THROUGHPUT_AUTHORITY       = DISCONNECTED (four-arch); CONNECTED (equal_budget)
SCANNER_THROUGHPUT_AUTHORITY      = DISCONNECTED (four-arch); CONNECTED (equal_budget)
OVERALL_ARCHITECTURE_FEASIBILITY_JOIN = DISCONNECTED (four-arch)
```

In `whole_oncology_four_architecture_optimization.py`,
`ArchitectureResult.feasible` is the hardcoded literal `True` in all four
evaluators (~lines 1440, 1696, 1917, 2313); `qualified_throughput=1` is
constant. The real `T_max = min(...)` join —
`compute_clinical_resource_peak_occupancy` (~line 1005) — is fully built but
**ORPHANED** (test-only), never reaching `ArchitectureResult.feasible` or
`qualify_architecture`. **Documented, not changed** (Build 3B scope). By
contrast, `equal_budget.py` (Capital Project engine, Build 3A) enforces a
genuine `min()` join and does not fabricate production capacity/CapEx when
uncalibrated.

---

## K. PRODUCTION CAPACITY RESOLVER CORRECTNESS (Section 26)

Resolution order (`equal_budget._resolve_physical_eob_capacity_mbq_per_day` →
`cyclotron_production_windows`):

1. `inputs.current_cyclotron_eob_capacity_mbq_per_day` →
   `input_current_cyclotron_eob_capacity_mbq_per_day`
2. `assumptions.cyclotron_eob_capacity_mbq_per_day` →
   `assumption_cyclotron_eob_capacity_mbq_per_day`
3. `inputs.cyclotron_fleet` (a `CyclotronFleet`) →
   `resolve_fleet_eob_capacity_mbq_per_day` → one of
   `explicit_site_daily_capacity`, `schedule_derived_capacity`,
   `partial_schedule_derived_capacity`, `not_calibrated`.
4. Otherwise → `not_calibrated`.

**Verified**: never falls back to `current_usable_doses_per_day`, never uses
legacy 10% blocks, never uses generic dose counts, never reuses another
radionuclide's performance. **No resolver defect found → no code change made in
Build 3B** (Build 3A already removed the legacy leakage; those corrections are
physically present at HEAD `9a04dc5`). Locked by
`test_resolver_returns_not_calibrated_for_uncalibrated_fleet_isotope`.

---

## L. PROVENANCE (Section 27)

Provenance preserved via `field_provenance` and
`ProductionPerformanceRecord.source` / `evidence_type` / `calibration_status`:

- MANUFACTURER / manufacturer_calibrated: PETtrace 840/860/880/890, Cyclone
  KEY, Cyclone KIUBE (F-18 EOB points).
- manufacturer_specification (equipment specs, not yield): most energy/current.
- technical_literature / literature_calibrated: CYPRIS MP-30 operating
  character, Eclipse HP, RDS-111, TR-19/24 energies, Best 14p.
- operational_installation / site_calibrated: TR-19/24 installed values.
- NOT_CALIBRATED: all null-yield records and empty-record models.

No unsourced value is upgraded to manufacturer authority.

---

## M. KNOWN GAPS / FUTURE CONTROLLED RESEARCH (NOT_CALIBRATED backlog)

1. F-18 production for all non-GE/non-Cyclone models (CYPRIS family, Eclipse
   HP, RDS-111, TR-19/24, Best 14p, IKON, 30XP) — no cycle times, no EOB.
2. **Every non-F-18 radionuclide** across the catalog — no calibrated EOB
   anywhere (Cu-64, Zr-89, Ga-68, I-123, I-124, C-11, N-13, O-15, Ge-68,
   Tl-201, In-111, At-211).
3. Cyclone KIUBE F-18 record lacks `beam_current_ua`.
4. Ge-68/Ga-68 **generator** model — MISSING.
5. Generator economics — `NOT_CALIBRATED` (controlled $3,500 delivery only).
6. Scanner economics — all `NOT_CALIBRATED`; per-model acquisition minutes not
   wired into `scanner_capacity`.
7. Batch record does not persist EOB/release activity, assigned source, timing,
   or status (held out-of-band).
8. Four-architecture `feasible` and clinical/production throughput join —
   `DISCONNECTED` (operational-feasibility calculator built but test-only).
9. Four-architecture 6/6/12 clinical quantities — inline literals, not named
   `CONTROLLED_BENCHMARK` constants.

---

## N. PART 3D INTEGRATION MAP (informational only — not implemented here)

Build 3B does **not** connect production/clinical feasibility to
`ArchitectureResult.feasible`, does not migrate Capital Project to the
four-architecture engine, and does not alter the 6/6/12 benchmark. Existing
seams a future Part 3D would consume:

- Production capacity: `_resolve_physical_eob_capacity_mbq_per_day` /
  `resolve_fleet_eob_capacity_mbq_per_day` (already correct, status-typed).
- Per-patient EOB requirement: `derive_cycle_relative_requirement`.
- Clinical occupancy join (currently orphaned):
  `compute_clinical_resource_peak_occupancy` →
  `ClinicalResourceOperationalFeasibility.operationally_feasible`.
- Feasibility gate that already reads `feasible`: `qualify_architecture`.

Wiring these is explicitly **out of scope** for Build 3B.

---

## O. VERIFICATION SUMMARY (this build)

Interpreter used for regression: `/opt/anaconda3/bin/python` (FastAPI 0.141.1,
pytest 7.4.4). No packages installed.

| Item | Result |
|---|---|
| Build 3A regression preservation (`test_equal_budget.py`) | 78 passed — unchanged |
| Focused Build 3B tests (`test_build3b_production_authority.py`) | 16 passed (new, additive) |
| Capital Project API (`test_capital_project_api.py`) | 27 passed (FastAPI-capable interpreter; no longer blocked) |
| Directly affected regression — cyclotron catalog/e2e/windows/cycle_relative | 75 passed |
| Directly affected regression — patient demand / multi_isotope_decay / production requirement reconciliation | 39 passed |
| Directly affected regression — cyclotron fleet integration / recommendation | 43 passed |
| **Total proven tests** | **278 passed** (78 + 16 + 27 + 75 + 39 + 43) |
| Production code changed | NONE (no authority/binding defect demonstrated) |
| Files added | `test_build3b_production_authority.py`, `CYCLOTRON_PRODUCTION_DATA_AUTHORITY_BUILD_3B.md` |
| Part 3D | NOT started |
| Commit / push | NOT performed |

---

*End of CYCLOTRON_PRODUCTION_DATA_AUTHORITY_BUILD_3B.md*

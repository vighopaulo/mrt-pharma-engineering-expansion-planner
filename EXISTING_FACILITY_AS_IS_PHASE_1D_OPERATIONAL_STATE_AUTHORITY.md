# EXISTING FACILITY / AS-IS DIGITAL TWIN — Phase 1D: Operational-State Reconstruction Authority

## A. Summary

Phase 1D adds the next distinct layer of the existing-facility AS-IS digital twin:
the **operational STATE** of the facility, reconstructed as a read-model that sits
on top of — and never mutates — the Phase 1C AS-IS facility **engineering** object
model.

The governing invariant is **STRUCTURAL MODEL ≠ OPERATIONAL STATE**. A scanner that
_exists_ (Phase 1C) is not the same fact as a scanner that is _available now_; a
cyclotron that is _installed_ is not the same fact as a cyclotron _producing today_;
a room that _exists_ is not a room that is _available_; a patient that _exists_ is
not a patient that is _scheduled_; a staff _category_ that exists is not staff
_available now_.

Operational state is reconstructed **only** from explicitly supplied structured
facts. Missing operational-state facts remain `UNKNOWN` / `NOT_MODELED` /
`NOT_OBSERVED` / `NOT_CALIBRATED` / `UNKNOWN_FRESHNESS` — never silently completed
from a benchmark and never inferred from structural installation.

Phase 1D **STOPS BEFORE BASELINE SIMULATION.** It produces the snapshot that a
future baseline simulation will consume; it does not run one, and it creates no
LOCKDOWN, no What-If, and no live integrations.

- `STARTING_HEAD` = `7d4fe4a` (Phase 1C — Facility Engineering Object Model & Completeness Closure)
- New engine: `existing_facility_operational_state.py`
- New tests: `test_asis_twin_phase1d.py` (43 deterministic invariants, all passing)
- This report: `EXISTING_FACILITY_AS_IS_PHASE_1D_OPERATIONAL_STATE_AUTHORITY.md`
- Files modified: **none** (`git diff --stat` empty)

## B. Physical precheck (Sec 1)

| Field | Value |
|---|---|
| STARTING_HEAD | `7d4fe4a6b42e52eb4814727420af09a7bae83e84` |
| STARTING_BRANCH | `main` |
| ORIGIN_MAIN | `7d4fe4a6b42e52eb4814727420af09a7bae83e84` |
| STARTING_DIVERGENCE | `0 / 0` |
| WORKING_TREE_CLEAN | YES (only the untracked Phase 1A seam report present) |
| STAGED_FILES | none |
| UNSTAGED_FILES | none |
| UNTRACKED_FILES | `AS_IS_DIGITAL_TWIN_PHASE_1A_SEAM_REPORT.md` |
| PHASE_1B_PRESENT_IN_HISTORY | YES (`4bd9930`) |
| PHASE_1C_PRESENT_IN_HISTORY | YES (`7d4fe4a`, HEAD) |
| PART3D_PRESENT_IN_HISTORY | YES (`07e861d`) |
| PART3E_PRESENT_IN_HISTORY | YES (`a6facf9`) |
| PART3E_1_PRESENT_IN_HISTORY | YES (`93bf687`) |
| PART3E_2_PRESENT_IN_HISTORY | YES (`2f22bf3`) |
| PHASE_1A_SEAM_REPORT_PRESENT | YES (untracked, left untouched) |
| UNRELATED_FILES_PRESENT | NO |
| READY_FOR_ASIS_PHASE_1D | YES |

## C. Facility model reference (Sec 3, Sec 51)

- `FACILITY_MODEL_REFERENCE` = `existing_facility_asis_twin.ExistingFacilityAsIsTwinResult`
  (Phase 1C). Phase 1D consumes it **by reference** (`facility_id`) and never
  copies, rebuilds, or mutates it.
- Phase 1C contract preserved unchanged: facility hierarchy, clinical-space
  classification (separate from geometry), engineering-object identity, equipment
  placement bindings, connectivity topology, operational-resource identity
  placeholders, field-level evidence, evidence conflicts, domain completeness, the
  five monotonic readiness gates, no silent benchmark substitution, and — crucially
  for Phase 1D — Phase 1C performs **no** operational-state reconstruction, no
  baseline simulation, no LOCKDOWN, no What-If. Verified by
  `test_phase1c_remains_unchanged_and_consumable` and by the empty `git diff`.

The Phase 1C result already reserved the Phase 1D seam
(`operational_state_reconstruction_implemented=False`,
`AsIsReadinessGates.operational_state_reconstruction_ready=False`). Phase 1D does
**not** flip those flags on the Phase 1C result (that would require modifying Phase
1C); instead it produces its own `AsIsOperationalStateSnapshot`, keeping Phase 1C
byte-for-byte unchanged.

## D. Operational snapshot type & authority (Sec 5, Sec 7)

- `OPERATIONAL_SNAPSHOT_TYPE` = `AsIsOperationalStateSnapshot` (frozen read-model).
- One narrow reconstruction authority: `existing_facility_operational_state.py`.
  Entry point: `reconstruct_operational_state(facility_result, operational_input=None, *, strict_identity_validation=False)`.
- **Snapshot identity independent of facility / scenario / LOCKDOWN / What-If**
  (Sec 7): `snapshot_id` defaults to `OPSNAP::<facility_id>::<effective_time>` so
  the same facility at a different effective time yields a different snapshot,
  without duplicating the facility engineering model. A supplied `snapshot_id` is
  honored. Verified by `test_snapshot_identity_separate_from_facility_identity`,
  `test_supplied_snapshot_id_is_honored`.

## E. Snapshot time authority (Sec 6)

- `SNAPSHOT_TIME_AUTHORITY` = `OperationalTemporalBasis`
  (`kind`, `effective_at`, `observed_at`, `source_updated_at`, `ingested_at`,
  `valid_from`, `valid_until`).
- `kind ∈ {NOW, HISTORICAL_POINT_IN_TIME, FUTURE_PLANNED_STATE, UNKNOWN_TIME}`.
- The module **never reads the wall clock** and **never invents a timestamp**. A
  snapshot with no supplied time is `UNKNOWN_TIME` with `has_temporal_basis=False`,
  and the `TEMPORAL_BASIS` completeness domain is `NOT_MODELED` with `BLOCKING`
  readiness impact. Verified by `test_time_basis_required_for_readiness`,
  `test_time_basis_not_stamped_from_wall_clock`,
  `test_future_planned_state_snapshot_is_supported`.

## F. Per-domain state models (Sec 10–22, Sec 51)

| Sec 51 field | Model |
|---|---|
| RESOURCE_STATE_MODEL | `AsIsResourceOperationalState` (generic; references canonical IDs; `availability_inferred_from_installation`→False) |
| ROOM_STATE_MODEL | `AsIsRoomOperationalState` (`RoomOccupancyStatus`; `availability_inferred_from_existence`→False) |
| PATIENT_STATE_MODEL | `AsIsPatientOperationalState` (references canonical `OncologyPatientRecord.patient_id`; never a second patient identity) |
| APPOINTMENT_STATE_MODEL | `AsIsAppointmentOperationalState` (thin projection; **no** second calendar authority; created only from supplied appointment facts) |
| SCANNER_STATE_MODEL | `AsIsScannerOperationalState` (reuses `scanner_catalog.ScannerOperatingState`; identity/modality/placement kept distinct from current availability) |
| CYCLOTRON_STATE_MODEL | `AsIsCyclotronOperationalState` (reuses `cyclotron_catalog.CyclotronOperatingState`; `current_eob_activity_mbq` default `NOT_MODELED`; `production_state_fabricated`→False) |
| GENERATOR_STATE_MODEL | `AsIsGeneratorOperationalState` (reuses `generator_catalog.GeneratorOperatingState`; `available_daughter_activity_mbq` default `NOT_MODELED`; `generator_state_fabricated`→False) |
| PRODUCTION_BATCH_STATE_MODEL | `AsIsProductionBatchOperationalState` (facts preserved exactly; `production_recalculated`→False; no decay compensation, no missing-activity estimation) |
| STAFF_RESOURCE_STATE_MODEL | `AsIsStaffResourceOperationalState` (category / count / person identity are three separate certainty levels; `staffing_benchmark_inserted`→False) |
| MRT_OPERATIONAL_STATE_MODEL | count on the snapshot; **0** when the facility has no MRT infrastructure; `benchmark_mrt_operational_inserted`→False |

All equipment operating-state vocabularies are **imported from the existing
catalogs**; provenance/calibration/confidence/domain-status vocabularies are
**imported from the Phase 1C authority** (`AsIsProvenance`, `AsIsCalibration`,
`AsIsConfidence`, `AsIsDomainStatus`). No second hierarchy of truth is created.

Identity ownership (referenced, never duplicated): patient identity is owned by
`oncology_pet_spect_scenario.OncologyPatientRecord`; the live actual-state twin and
plan versions are owned by `live_operational_state`; the point-in-time state query
is owned by `digital_twin_simulation_state`; the lockdown/what-if lineage is owned
by `lockdown_what_if_lineage_authority`.

## G. Freshness authority (Sec 26)

- `FRESHNESS_AUTHORITY` = `FreshnessStatus ∈ {CURRENT, STALE, UNKNOWN_FRESHNESS, NOT_APPLICABLE}`
  on `OperationalEvidence`.
- **No universal timeout is invented.** With a timestamp but no supplied,
  resource-specific threshold → `UNKNOWN_FRESHNESS`. With neither timestamp nor
  threshold → `NOT_APPLICABLE`. Staleness is never declared merely because data is
  old by arbitrary model choice. Verified by
  `test_control_h_timestamp_no_threshold_yields_unknown_freshness`,
  `test_control_h_no_timestamp_no_threshold_is_not_applicable`.

## H. Operational conflict authority (Sec 27–28)

- `OPERATIONAL_CONFLICT_AUTHORITY` = `OperationalEvidenceConflict`, populated from
  `ConflictingOperationalStateInput`.
- Both candidate values and sources are **preserved**; nothing is
  last-write-wins / averaged / auto-resolved; an unresolved conflict marks the
  affected domain `CONFLICTED` and reduces readiness. Verified by Control F
  (`test_control_f_operational_conflict_preserved`,
  `test_control_f_conflict_marks_snapshot_and_domain_conflicted`).

## I. Operational completeness domains (Sec 29–30)

`OPERATIONAL_COMPLETENESS_DOMAINS` (never collapsed to one count):
`SNAPSHOT_IDENTITY`, `TEMPORAL_BASIS`, `FACILITY_MODEL_LINKAGE`,
`ROOM_OPERATIONAL_STATE`, `SCANNER_OPERATIONAL_STATE`, `CYCLOTRON_OPERATIONAL_STATE`,
`GENERATOR_OPERATIONAL_STATE`, `MRT_OPERATIONAL_STATE`, `PATIENT_STATE`,
`APPOINTMENT_STATE`, `STAFF_RESOURCE_STATE`, `PRODUCTION_BATCH_STATE`, `PROVENANCE`,
`FRESHNESS`, `EVIDENCE_CONFLICTS`, `BASELINE_SIMULATION_INPUT_READINESS`. Each is an
independent `AsIsOperationalDomainCompleteness` with its own status/counts/impact.
Verified by `test_domain_completeness_never_collapsed_to_one_count`.

## J. Baseline simulation input readiness (Sec 31–32)

- `BASELINE_SIMULATION_INPUT_READINESS` = `AsIsBaselineSimulationInputReadiness`
  with distinct sub-gates: `facility_model_ready` (inherited from the Phase 1C
  engineering gate), `operational_snapshot_normalized`, `resource_state_ready`,
  `patient_appointment_state_ready`, `production_state_ready`, and the overall
  `baseline_simulation_input_ready`.
- Requiredness is physically justified (not every domain is required), but a
  temporal basis and a normalized, conflict-free snapshot are required. **The
  simulation is never run** (`baseline_simulation_run=False`). Verified by
  `test_control_a_baseline_simulation_not_run_and_readiness_honest`,
  `test_baseline_input_ready_can_be_true_with_full_operational_state`.

## K. No-silent-benchmark governor (Sec 35)

All benchmark-insertion flags are always **False**:
`benchmark_patient_population_inserted`, `benchmark_appointments_inserted`,
`benchmark_scanner_availability_inserted`, `benchmark_cyclotron_availability_inserted`,
`benchmark_generator_availability_inserted`, `benchmark_staffing_inserted`,
`benchmark_production_schedule_inserted`, `benchmark_radionuclide_demand_inserted`,
`benchmark_room_occupancy_inserted`, `benchmark_mrt_operational_resource_inserted`.
Verified across Controls A/G and `test_no_benchmark_population_or_staffing_or_production`.

## L. Controls A–H

| Control | Meaning | Result |
|---|---|---|
| A (Sec 36) | Partial operational snapshot: known facts survive, unknown stay unknown, no benchmark fill, sim not run, readiness honest | PASS |
| B (Sec 37) | Installed scanner / unknown availability: identity present, status UNKNOWN, not inferred from installation | PASS |
| C (Sec 38) | Installed cyclotron / unknown production: no radionuclide/batch/EOB invented | PASS |
| D (Sec 39) | Room exists / occupancy unknown: identity + geometry + function survive; occupancy UNKNOWN; no patient inserted | PASS |
| E (Sec 40) | Patient exists / appointment absent: patient survives; no appointment fabricated | PASS |
| F (Sec 41) | Operational conflict: both candidates preserved; no auto-resolution; readiness reduced | PASS |
| G (Sec 42) | No-MRT facility: MRT operational count 0; no benchmark MRT inserted (even if MRT facts supplied) | PASS |
| H (Sec 43) | Stale / unknown freshness: fact preserved; UNKNOWN_FRESHNESS; no invented threshold | PASS |

## M. Out-of-scope disclosure flags

Baseline simulation (Sec 32):
`ASIS_BASELINE_SIMULATION_IMPLEMENTED = NO`,
`SIMULATION_RUN_DURING_PHASE_1D = NO`,
`FOUR_ARCHITECTURE_SIMULATION_CALLED = NO`,
`PART3D_FEASIBILITY_CALLED = NO`,
`PART3E_OPTIMIZATION_CALLED = NO`,
`PART3E1_EXPERIMENTS_CALLED = NO`,
`PART3E2_DECISION_ENVELOPE_CALLED = NO`.

LOCKDOWN / What-If (Sec 33):
`LOCKDOWN_CREATED = NO`, `WHAT_IF_CREATED = NO`,
`LOCKDOWN_AUTHORITY_DUPLICATED = NO`,
`EXISTING_LOCKDOWN_LINEAGE_SEAM_PRESERVED = YES`.

Live integrations (Sec 34):
`LIVE_HOSPITAL_API_IMPLEMENTED = NO`, `ARIA_LIVE_INGESTION_IMPLEMENTED = NO`,
`RIS_LIVE_INGESTION_IMPLEMENTED = NO`, `PACS_LIVE_INGESTION_IMPLEMENTED = NO`,
`EHR_LIVE_INGESTION_IMPLEMENTED = NO`, `STAFF_SYSTEM_LIVE_INGESTION_IMPLEMENTED = NO`,
`FACILITY_BMS_LIVE_INGESTION_IMPLEMENTED = NO`.

Ranking / economics (Sec 44):
`ARCHITECTURE_RANKING_PERFORMED = NO`, `ECONOMIC_OPTIMIZATION_PERFORMED = NO`.

Verified by `test_no_simulation_lockdown_whatif_or_ranking`,
`test_no_live_api_integrations`.

## N. Physics / economics preservation (Sec 49)

Proven **categorically**: `git diff --stat` is empty — no tracked file was modified.
Phase 1D added only two new untracked files. Therefore every listed authority is
byte-for-byte unchanged:

| Authority | Change flag |
|---|---|
| decay physics (`multi_isotope_decay.py`) | NO |
| cyclotron production physics | NO |
| generator physics | NO |
| scanner timing | NO |
| transport physics | NO |
| Part 3D | NO |
| Part 3E / 3E.1 / 3E.2 | NO |
| Equipment OPEX | NO |
| economic engine | NO |
| `equal_budget.py` | NO |
| hybrid decay math | NO |

## O. Existing-facility pipeline status (Sec 45)

```
Facility Evidence
      v
Phase 1B Ingestion                 [done]
      v
Phase 1C Facility Engineering Model [done]
      v
Phase 1D Operational-State Snapshot [THIS BUILD]
      v
[FUTURE] Baseline Simulation
      v
[FUTURE] Validation
      v
[FUTURE] LOCKDOWN
      v
[FUTURE] What-If
```

## P. Test results (Sec 47–48)

Focused Phase 1D suite: `test_asis_twin_phase1d.py` — **43 passed**.

Directly-affected regression (counts per invocation; no fabricated grand total):

| Invocation | Result |
|---|---|
| `test_asis_twin_phase1b.py` + `test_asis_twin_phase1c.py` + `test_asis_twin_phase1d.py` | 86 passed |
| `test_whole_oncology_patient_identity_unification.py` + `test_patient_radionuclide_demand.py` + `test_oncology_patient_pet_spect_nuclear_completion.py` | 91 passed |
| `test_long_horizon_operational_planning.py` + `test_clinical_resource_identity.py` | 26 passed |
| `test_canonical_spatial_authority_closure.py` + `test_cyclotron_catalog_foundation.py` + `test_scanner_authority_review.py` | 156 passed |
| `test_production_clinical_schedule.py` + `test_pet_spect_generator_native_authority_completion.py` | 61 passed |
| `test_build3b_production_authority.py` + `test_whole_oncology_four_architecture_optimization.py` + `test_multi_cyclotron_radionuclide_authority.py` (preservation sample) | 226 passed, 1 skipped |

Python: `/opt/anaconda3/bin/python`.

## Q. Files

- `FILES_CREATED`:
  - `existing_facility_operational_state.py`
  - `test_asis_twin_phase1d.py`
  - `EXISTING_FACILITY_AS_IS_PHASE_1D_OPERATIONAL_STATE_AUTHORITY.md`
- `FILES_CHANGED`: none.

## R. Phase 1A report handling (Sec 50)

`AS_IS_DIGITAL_TWIN_PHASE_1A_SEAM_REPORT.md` remains present and untracked. It was
**not** staged, **not** deleted, and **not** modified. It is not a Phase 1D
deliverable.

## S. Readiness disposition (Sec 51)

- `READY_FOR_ASIS_BASELINE_SIMULATION_BUILD` = **YES** — the repository is ready for
  the next build (the AS-IS baseline simulation build). This is a repository-level
  disposition.
- This is **not** the same as `BASELINE_SIMULATION_INPUT_READY`, which is a
  per-facility operational-data completeness result computed on each snapshot (it is
  `True` only when a specific facility supplies a timed, conflict-free snapshot with
  sufficient resource + patient/appointment state).

## T. Final git state (Sec 52)

| Field | Value |
|---|---|
| ENDING_HEAD | `7d4fe4a6b42e52eb4814727420af09a7bae83e84` (unchanged) |
| ENDING_DIVERGENCE | `0 / 0` |
| FILES_MODIFIED | none |
| FILES_CREATED | `existing_facility_operational_state.py`, `test_asis_twin_phase1d.py`, `EXISTING_FACILITY_AS_IS_PHASE_1D_OPERATIONAL_STATE_AUTHORITY.md` |
| FILES_STAGED | none |
| PHASE_1A_SEAM_REPORT_PRESENT | YES (untracked, untouched) |
| READY_FOR_PHASE_1D_CHECKPOINT | YES |

`git status --short` at completion:

```
?? AS_IS_DIGITAL_TWIN_PHASE_1A_SEAM_REPORT.md
?? existing_facility_operational_state.py
?? test_asis_twin_phase1d.py
```

Nothing staged, nothing committed, nothing pushed. Awaiting review.

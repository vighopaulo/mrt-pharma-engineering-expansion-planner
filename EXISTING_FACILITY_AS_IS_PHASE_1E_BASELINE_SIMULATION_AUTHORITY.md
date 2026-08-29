# Existing Facility / AS-IS Digital Twin — Phase 1E
## Baseline Simulation Readiness & Execution Authority

Self-contained authority document for Phase 1E. Starting committed baseline:
`HEAD = fc6e4f8`, `branch = main`, `origin/main = fc6e4f8`, divergence `0 / 0`.

Phase 1E files (narrow scope):
- `existing_facility_baseline_simulation.py` (authority module)
- `test_asis_twin_phase1e.py` (36 deterministic invariants)
- `EXISTING_FACILITY_AS_IS_PHASE_1E_BASELINE_SIMULATION_AUTHORITY.md` (this doc)

---

### 1. Purpose and boundary

Phase 1E answers ONE governing question: *given what we actually know about
this existing hospital, can MRT Pharma truthfully run an AS-IS baseline
simulation without silently substituting benchmark facts?*

- **YES** → run the EXISTING simulation authorities on the supplied/canonical
  AS-IS facts.
- **NO** → do not simulate; return an explicit readiness failure with the exact
  blocking facts.

Phase 1E is **orchestration + readiness + execution control**. It is NOT a
second simulation engine, NOT a second patient/resource/spatial identity system,
NOT a LOCKDOWN authority, and NOT What-If. It does not modify Phase 1B/1C/1D,
Part 3D/3E/3E.1/3E.2, decay/cyclotron/generator/scanner/transport physics,
economic engines, equipment OPEX, `equal_budget.py`, or hybrid decay math.

The chain: **Phase 1C structural twin → Phase 1D operational snapshot →
Phase 1E simulation readiness → AS-IS baseline simulation → baseline candidate.**
Phase 1E STOPS before validation completion and LOCKDOWN creation.

### 2. Authority trace (`ASIS_SIMULATION_INPUT_TRACE`)

Every dependency was traced and classified before code was written. All are
REUSE; none is a new engine.

| # | Concern | Authority | Class |
|---|---------|-----------|-------|
| A | Phase 1C structural twin | `existing_facility_asis_twin.ExistingFacilityAsIsTwinResult` | REUSE |
| B | Phase 1D operational snapshot | `existing_facility_operational_state.AsIsOperationalStateSnapshot` | REUSE |
| C | Patient identity | `oncology_pet_spect_scenario.OncologyPatientRecord` (+`NuclearProcedureAssignment`) | REUSE |
| D | Clinical resource identity | `clinical_resource_identity` + `ClinicalResourceInputs` (Part 3D) | REUSE |
| E | Geometry / route | `canonical_spatial_authority` (`resolve_route`→`RouteResult`); `BenchmarkGeometry` | REUSE (VIEW for readiness) |
| F | Production / radionuclide | `cyclotron_catalog`/`generator_catalog`/`cyclotron_production_windows` + Part 3D production gate | REUSE |
| G | Scanner | `scanner_catalog` + Phase 1D `AsIsScannerOperationalState` | REUSE |
| H | Staffing | Phase 1D `AsIsStaffResourceOperationalState` | REUSE (VIEW) |
| I | Simulation entry point | `_nuclear_result` → `evaluate_hybrid_zone_candidate` → `schedule_operating_day` | REUSE (the ONE engine) |
| J | Trajectory / movement | `HybridPatientTrace` + `digital_twin_simulation_state` | REUSE (VIEW) |
| K | Simulation result | `hybrid_optimization.HybridEvaluationResult` | REUSE |
| L | Feasibility | `derive_physical_feasibility` → `PhysicalFeasibilityResult` (Part 3D) | REUSE |
| M | Economics | `evaluate_lifecycle_economics` (inside the engine) | REUSE (untouched) |
| N | LOCKDOWN | `lockdown_what_if_lineage_authority` | REFERENCE-ONLY (never called) |

`EXISTING_SIMULATION_ENGINE_REUSED = YES`.

### 3. Phase 1C structural input

`ExistingFacilityAsIsTwinResult` provides the facility identity
(`facility_identity.facility_id`), the canonical `spatial_registry`, the
engineering object model, `connectivity` (route readiness), `readiness_gates`
(`structural_reconstruction_ready`, `engineering_object_model_ready`), and the
hard governor proofs (`benchmark_mrt_inserted`/`benchmark_cyclotron_inserted`
always False, `mrt_infrastructure_count`). Phase 1E consumes it read-only.

### 4. Phase 1D operational input

`AsIsOperationalStateSnapshot` provides the per-domain operational states
(scanner/room/cyclotron/generator/patient/staff/production), the
`temporal_basis` (`has_temporal_basis`), unresolved `conflicts`, and the
no-silent-benchmark proof flags. Critically, availability defaults to `UNKNOWN`
and is **never inferred from installation** — Phase 1E honors this exactly.

### 5. Simulation-scope authority

`AsIsBaselineSimulationScope` names the exact service domain
(`NUCLEAR_MEDICINE_ONCOLOGY`; `WHOLE_HOSPITAL` is declared but NOT_MODELED) and
carries the EXPLICIT AS-IS engine inputs: `asis_baseline`,
`asis_clinical_resources`, `patient_demand_source`, the temporal basis
(`simulation_date`/`simulation_start_minute`/`simulation_horizon_minutes`),
`available_transport_modes`, and `installed_cyclotron_model_ids`. None is
defaulted from a benchmark.

### 6. Required-fact manifest

`AsIsRequiredFact(fact_id, domain, required_for, source, current_status,
blocking_if_missing, reason)` is derived for the selected scope. A fact that is
`MISSING`/`UNKNOWN`/`CONFLICTING` and `blocking_if_missing` blocks the run. This
manifest is the core anti-fabrication mechanism: every blocker is named
explicitly with its reason.

### 7. Readiness domains

`AsIsSimulationReadinessAssessment` reports 14 domains (never one opaque bool),
each `READY` / `PARTIAL` / `BLOCKED` / `NOT_APPLICABLE` / `NOT_MODELED`:

`STRUCTURAL_TWIN_READINESS`, `OPERATIONAL_STATE_READINESS`,
`TEMPORAL_BASIS_READINESS`, `PATIENT_DEMAND_READINESS`,
`CLINICAL_RESOURCE_READINESS`, `ROOM_AVAILABILITY_READINESS`,
`PRODUCTION_READINESS`, `SCANNER_READINESS`, `STAFFING_READINESS`,
`ROUTE_TOPOLOGY_READINESS`, `TRANSPORT_READINESS`, `RADIONUCLIDE_READINESS`,
`CONFLICT_READINESS`, `SIMULATION_INPUT_READINESS` (aggregate).

**Readiness ≠ completeness**: readiness is scoped to REQUIRED facts. A facility
globally incomplete (e.g. hundreds of unrelated rooms unknown) may still be
READY for the narrow nuclear-medicine baseline when all required
nuclear-medicine facts are present (`completeness_distinct_from_readiness` is a
hard True).

### 8. No-silent-benchmark governor

If a required AS-IS fact is absent, Phase 1E **never** silently substitutes
`BENCHMARK_CLINICAL_RESOURCES`, benchmark patients/identities, benchmark
cyclotron/generator/scanner/staffing/geometry/routes/room-occupancy, benchmark
MRT, benchmark production, radionuclide mix, or transport mode. A
`CONTROLLED_BENCHMARK` clinical-resource source is explicitly **rejected** for
AS-IS. Result governor flags (all hard False):

| Flag | Value |
|------|-------|
| `benchmark_patients_inserted` | False |
| `benchmark_resources_inserted` | False |
| `benchmark_geometry_inserted` | False |
| `benchmark_production_inserted` | False |
| `benchmark_mrt_inserted` | False |
| `benchmark_staffing_inserted` | False |

### 9. Temporal-basis rules

A defined simulation time basis is required (Control G). It is satisfied by a
scope-supplied `simulation_date`+`start`+`horizon` OR a Phase 1D snapshot with a
real `temporal_basis`. No time is ever read from `datetime.now()`; no universal
freshness threshold is invented. Missing basis →
`SIMULATION_EXECUTION_STATUS = BLOCKED_TEMPORAL_BASIS`.

### 10. Patient-demand authority

Demand is carried on `scope.asis_baseline.patients` (the canonical
`OncologyPatientRecord` identity) with an explicit `patient_demand_source`
(`PROJECT_SUPPLIED` / `FACILITY_DERIVED` / `CONTROLLED_ASIS_STUDY_INPUT`).
`ABSENT` or an empty nuclear subset blocks; synthetic benchmark patients are
never inserted (`patient_demand_fabricated` = False).

### 11. Radionuclide identity

Each patient carries its own radionuclide via `NuclearProcedureAssignment`;
demand is never collapsed to one generic nuclear-medicine stream. The
per-radionuclide production verdict is delegated to the Part 3D gate.

### 12. Production readiness

When the scope declares an installed cyclotron (`installed_cyclotron_model_ids`),
a required cyclotron with `UNKNOWN` availability blocks (Control I) — installed
is never converted to available (`unknown_cyclotron_inferred_available` = False).
When availability is known, the radionuclide-specific calibration verdict is the
Part 3D gate's job: a SUPPORTED-but-`NOT_CALIBRATED` pair (e.g.
`SUMITOMO_CYPRIS_MP_30` + F-18) yields a **qualified uncertainty**, never a block
and never a promotion to calibrated (`production_calibration_borrowed` = False).

### 13. Scanner readiness

Scanner IDENTITY, MODALITY and AVAILABILITY are distinct. A required scanner
with `UNKNOWN` availability, no state record, or an unresolved conflict blocks
(Control B); identity survives (`unknown_scanner_inferred_available` = False).

### 14. Route / topology readiness

Phase 1C connectivity `route_readiness` gates required movement:
`TOPOLOGY_COMPLETE` → READY; `TOPOLOGY_PARTIAL` / `TOPOLOGY_NOT_MODELED` → BLOCKED
(Control D). No edge is fabricated and no transport time is computed over a
missing route (`route_edge_fabricated` = False,
`transport_time_calculated_over_missing_route` = False).

### 15. Transport-mode readiness

At least one physically available transport mode must be known. `MANUAL`-only is
sufficient; no mode known → block.

### 16. MRT absence semantics

An existing hospital may have MRT count = 0. That is legal. MRT is **never**
required for readiness and never inserted (`mrt_absence_supported` = True). The
honest AS-IS default runs the manual/conventional clinical schedule
(`mrt_floors = frozenset()`).

### 17. Simulation-input adapter

`AsIsSimulationInputMapping` records each auditable AS-IS-fact → engine-field
mapping (clinical-resource counts → `HybridZoneCandidate` fields; patient ids →
`OncologyPatientRecord.patient_id`). Every mapping's `assumption_status` is
`MAPPED_FROM_ASIS_FACT` and its `source_provenance` is never
`CONTROLLED_BENCHMARK`. It is a traceability read-model only; a blocked run
produces zero mappings.

### 18. Simulation execution statuses

`NOT_ATTEMPTED`, `BLOCKED_MISSING_REQUIRED_FACTS`,
`BLOCKED_CONFLICTING_REQUIRED_FACT`, `BLOCKED_INVALID_ROUTE`,
`BLOCKED_TEMPORAL_BASIS`, `READY_NOT_RUN`, `EXECUTED`,
`EXECUTED_WITH_QUALIFIED_UNCERTAINTY`, `FAILED`. Blocked execution is never
hidden behind an empty result; the exact blockers are preserved in
`unresolved_gaps` and the readiness assessment.

### 19. Baseline outputs

When executed, `AsIsBaselineSimulationOutputs` preserves the existing engine
outputs: `patient_trajectories` (the existing `HybridPatientTrace` records),
`retention_qualified_completed`, scanner/injection/uptake peak occupancy and
availability, `radionuclide`, and `operationally_feasible`. Only categories the
existing engine actually produces are exposed.

### 20. Trajectory / movement preservation

Patient movement is preserved as the existing per-patient stage windows
(injection/uptake/scan start-end) plus transport arrival time and destination
room/floor — never replaced by summary timestamps. `patient_movement_visible`
and `patient_trajectory_seam_preserved` prove the seam for the later visual
runtime.

### 21. Validation boundary

A successful first baseline run yields
`BASELINE_VALIDATION_STATUS = VALIDATION_REQUIRED`, never auto-`VALIDATED`.

### 22. LOCKDOWN boundary

`LOCKDOWN_ELIGIBILITY_STATUS` is calculated (`VALIDATION_REQUIRED` on a
successful run, `NOT_ELIGIBLE` on a blocked run) but LOCKDOWN is **never
created** — `create_first_lockdown` is not called. `lockdown_created` = False.

### 23. What-If boundary

`WHAT_IF_CREATED` / `WHAT_IF_EXECUTION_STARTED` / `WHAT_IF_BASELINE_MUTATED` are
all hard False. The baseline candidate is independent of any future What-If
branch.

### 24. Controls A–L

| Control | Scenario | Result |
|---------|----------|--------|
| A | Incomplete facility (missing facts) | `BLOCKED_MISSING_REQUIRED_FACTS`; no engine call; no benchmark |
| B | Unknown scanner state | BLOCKED; identity survives; availability not inferred |
| C | Missing patient demand | BLOCKED; no synthetic patients |
| D | Partial topology | `BLOCKED_INVALID_ROUTE`; no edge fabricated |
| E | No MRT hospital | MRT=0 legal; manual baseline READY/EXECUTED |
| F | Conflicting operational evidence | `BLOCKED_CONFLICTING_REQUIRED_FACT`; both claims preserved |
| G | Temporal basis missing | `BLOCKED_TEMPORAL_BASIS`; no time invented |
| H | Unknown room state | BLOCKED; room availability not inferred |
| I | Unknown cyclotron state | BLOCKED when production required; not inferred available |
| J | Production NOT_CALIBRATED | `EXECUTED_WITH_QUALIFIED_UNCERTAINTY`; support preserved, not promoted; per-radionuclide gate |
| K | Manual-only facility | EXECUTED via manual transport; no automation inserted |
| L | Successful ready baseline | EXECUTED via existing engine; identities+movement preserved; VALIDATION_REQUIRED; no LOCKDOWN/What-If |

All 36 Phase 1E invariants pass. The per-radionuclide production gate confirms a
calibrated F-18 record never qualifies a CYPRIS MP-30 F-18 pair as calibrated
(status `PRODUCTION_NOT_CALIBRATED` / `NO_COMPATIBLE_SOURCE` preserved).

### 25. Unresolved gaps

Blocked runs enumerate every unresolved gap (`fact_id: reason`). A qualified run
lists `qualified_uncertainties` (e.g. `production_capacity_not_calibrated:<radionuclide>`)
— disclosed, never silently made certain.

### 26. Next-step boundary

Phase 1E ends at a `VALIDATION_REQUIRED` baseline candidate. Baseline
validation, LOCKDOWN promotion, and What-If branching are subsequent
authorities. No commit/push, no LOCKDOWN, no What-If, no UI, no live
integrations were performed.

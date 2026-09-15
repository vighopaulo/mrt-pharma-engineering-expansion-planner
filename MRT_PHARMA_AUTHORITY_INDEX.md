# MRT Pharma — Master Authority Index

**Build:** MRT Pharma Authority Consolidation (governance / traceability layer)
**Starting authority:** branch `main`, HEAD `07e861d` ("Part 3D: establish unified
physical feasibility authority"), working tree clean, divergence 0/0.
**Nature of this build:** GOVERNANCE / TRACEABILITY only. It changes **no**
production-engine behavior. Every classification below was verified against the
**physical repository** (source, tests, catalogs), not from session memory.

---

## 0. How to use this index (authority-first governance)

**VALIDATED REPOSITORY AUTHORITY  >  SESSION MEMORY  >  PROMPT SHORTHAND.**

Before any future build creates, redefines, or duplicates an authority:

1. Read this file (`MRT_PHARMA_AUTHORITY_INDEX.md`).
2. Locate the canonical implementation / document for the concern.
3. Inspect its focused tests.
4. Read `MRT_PHARMA_OPEN_GAPS.md` to see whether the concern is already a
   documented gap.
5. Decide whether the new instruction (a) reuses, (b) extends, (c) explicitly
   supersedes an existing authority, or (d) closes a real documented gap.

Do not create a second authority merely because a later prompt uses different
terminology for the same concept. Governance doctrine and the three classes of
project truth are defined in `MRT_PHARMA_AUTHORITY_DOCTRINE.md`.

### Status vocabulary used throughout

| Term | Meaning |
|---|---|
| `IMPLEMENTED` | Behavior physically present in repository code + tests |
| `PARTIAL` | Partially implemented; a real seam/gap is disclosed |
| `PLANNED` | Agreed future behavior, not physically implemented |
| `NOT_MODELED` | Not represented in the repository at all |
| `CALIBRATED` | Backed by manufacturer/site evidence |
| `NOT_CALIBRATED` | Honestly unknown; never fabricated, never silently 0 |
| `CONTROLLED_BENCHMARK` | A fixed controlled scenario assumption |
| `SUPERSEDED` | Replaced by a later authority (kept for lineage) |
| `NOT_APPLICABLE` | Deliberately outside scope |

---

## 1. The product: MRT Pharma = Capital Project + Operations

**MRT PHARMA = CAPITAL PROJECT + OPERATIONS.** These are two products sharing one
set of validated physical/engineering authorities.

- **Capital Project** helps hospital owners, health systems, architects,
  engineers, builders, and planners determine the best facility / equipment /
  transport configuration under user constraints. Transport technologies are
  **building blocks**; MRT is **optional**. Valid solutions include pure MRT,
  MRT + Manual, MRT + PTS, MRT + RP-PTS, Manual + PTS, existing infrastructure
  retained, mostly Manual, no MRT, or **NO BUILD**.
- **Operations** manages / plans the operating facility using actual or planned
  demand and resources (patients, procedures, radionuclides, activity,
  production, batches, release, transport, injection, uptake, scanners, rooms,
  staff, equipment, exceptions, forward schedules).

The two-product boundary is `study_scope.py`:
`StudyScope = CAPITAL_PLANNING | OPERATIONAL_ONLY` and
`TransportArchitecture = CONVENTIONAL | MRT | HYBRID` are **independent,
composable axes** (`StudyScope` only controls whether new-project acquisition/
construction CapEx enters the study objective; it never removes physical
assets/capacity/scheduling/staffing).

---

## 2. Domain authority table

Schema per domain: **Canonical Authority · Primary File(s) · Primary Symbol(s) ·
Primary Test(s) · Authority Type · Implementation Status · Calibration Status ·
Provenance/Build · Supersedes / Superseded By · Known Limitations · Open-Gap Ref.**

Authority types: `IMPLEMENTED_REPOSITORY_AUTHORITY` (B), `LOCKED_PRODUCT_DOCTRINE`
(A), `PLANNED_REQUIREMENT` (C).

---

### 2.1 Capital Project engine

- **Canonical Authority:** Four-Architecture capital optimization engine.
- **Primary Files:** `whole_oncology_four_architecture_optimization.py`,
  `hybrid_optimization.py`, `equal_budget.py`, `architecture_optimizer.py`,
  `capital_project_api.py`.
- **Primary Symbols:** `evaluate_manual_conventional`,
  `evaluate_automated_conventional_final`, `_evaluate_mrt_style_architecture`
  (serves `evaluate_hybrid_mrt` + `evaluate_mrt_dominant`), `ArchitectureResult`;
  `run_equal_budget_capacity_optimization`, `maximize_mrt_capacity`,
  `maximize_conventional_capacity` (equal_budget.py).
- **Primary Tests:** `test_whole_oncology_four_architecture_optimization.py`,
  `test_equal_budget.py`, `test_hybrid_optimization.py`,
  `test_architecture_optimizer.py`, `test_capital_project_api.py`.
- **Authority Type:** B (IMPLEMENTED_REPOSITORY_AUTHORITY).
- **Implementation Status:** IMPLEMENTED.
- **Calibration Status:** Mixed — physics CALIBRATED; several economic inputs are
  `USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION` / `NOT_CALIBRATED` (disclosed in
  the four_architecture reports).
- **Provenance/Build:** Build 2R four-architecture rederivation; Build 3A/3B/3C/
  3C.1; Part 3D feasibility closure.
- **Known Limitations:** The four canonical architectures are
  MANUAL_CONVENTIONAL / AUTOMATED_CONVENTIONAL / HYBRID_MRT / MRT_DOMINANT.
  `NO_BUILD_BASELINE` is a real computed baseline in the `equal_budget.py`
  MRT-investment search (test-locked), but is a **legacy Build-3A identity, not a
  fifth four-architecture option**. See Open-Gaps.
- **Open-Gap Ref:** OG-CAP-1 (NO BUILD not a first-class four-architecture
  option), OG-CAP-2 (composition optimizer PLANNED).

### 2.2 Operations engine

- **Canonical Authority:** Operational-day orchestration + long-horizon planning.
- **Primary Files:** `operational_day_orchestrator.py`,
  `operating_day_scheduler.py`, `long_horizon_operational_planning.py`,
  `intraday_scheduling.py`, `live_operational_state.py`,
  `production_clinical_schedule.py`, `mvp_scenario_runner.py`.
- **Primary Symbols:** `OperatingDayInputs`, `DailyOperationalSummary`,
  `PlanVersion`, `run_long_horizon_operational_plan`.
- **Primary Tests:** `test_operational_day_orchestration.py`,
  `test_operating_day_scheduler.py`, `test_long_horizon_operational_planning.py`,
  `test_intraday_scheduling.py`, `test_live_state_rolling_reoptimization.py`,
  `test_mvp_scenario_runner.py`.
- **Authority Type:** B.
- **Implementation Status:** IMPLEMENTED (as an orchestration/delegation layer —
  it creates NO second patient population, scheduler, decay engine, or economics
  engine; it delegates to the existing authorities).
- **Calibration Status:** Inherits calibration of the delegated authorities.
- **Known Limitations:** The long-horizon `DailyOperationalSummary` is not yet
  wired as a direct input to `operational_day_orchestrator` (self-disclosed
  bounded gap). See OG-OPS-1.
- **Open-Gap Ref:** OG-OPS-1.

### 2.3 Patient-source authority (Capital vs Operations)

- **Capital patient source:** synthetic/modeled population from project demand.
  Files: `oncology_pet_spect_scenario.py`, `patient_radionuclide_demand.py`,
  `inbound_patient_program.py`. Symbols: `PatientRadionuclideDemand`,
  `build_representative_day_population`. **Demand is upstream** — cyclotron,
  generator, scanner, and transport capacity do NOT create patients (test-locked
  `test_excess_capacity_is_headroom_not_extra_patients`).
- **Operations patient source (ARIA):** vendor-neutral adapter foundation.
  Files: `healthcare_integration.py`, `healthcare_adapters.py`,
  `inbound_patient_program.py`. Symbols: `CanonicalIntegrationEvent`,
  `CrossSourceIdentityRegistry`, `build_aria_fixture`, `ingest_aria_fixture`,
  `CanonicalOperationalPatientRecord`.
  Conceptual architecture: **ARIA → MRT Pharma Operational Adapter → canonical
  operational patient representation → MRT Pharma Operations Digital Twin.**
  MRT Pharma does **not** replace ARIA; ARIA-class systems are the upstream
  system-of-record for patient/procedure/appointment truth.
- **Authority Type:** Capital source = B; ARIA integration = C (LIVE) + B
  (fixture adapter).
- **Implementation Status:** Capital synthetic source = IMPLEMENTED. ARIA
  vendor-neutral **fixture** adapter = IMPLEMENTED (synthetic
  `SYNTHETIC_TEST_FIXTURE`, no network/credentials). **Live ARIA integration =
  PLANNED / NOT_MODELED** (no network/API/FHIR/HL7 client; explicitly
  `SECURITY_COMPLIANCE_NOT_IN_SCOPE`, not HIPAA-compliant).
- **Primary Tests:** `test_vendor_neutral_healthcare_integration.py`,
  `test_inbound_patient_program.py`, `test_inbound_pipeline_integration.py`.
- **Open-Gap Ref:** OG-ARIA-1 (live integration PLANNED).

### 2.4 Patient → Radionuclide → Production directional chain

Canonical direction (production does NOT generate patient demand):

> Patient → Procedure → Radionuclide → Administered Activity → Release
> Requirement → Required EOB Activity → Compatible Production Source →
> Production Requirement → Physical Batch/Cycle (where qualified) → Transport →
> Injection → Uptake → Scanner → Completed Patient.

- **Primary Symbols:** `PatientRadionuclideDemand` →
  `cycle_relative_production_requirement.derive_cycle_relative_requirement`
  (administered → required EOB via `required_upstream_activity`) →
  `_resolve_production_gate` (Part 3D) → `RadionuclideBatchDemand` →
  `ProductionWindow` (cyclotron_production_windows.py).
- **Provenance/Build:** Build 3B + Part 3D. **Implementation Status:** IMPLEMENTED.

### 2.5 Radionuclide + half-life + decay authority

- **Canonical Authority:** Single half-life source + canonical decay primitives.
- **Primary Files:** `radionuclides.json` (data), `diagnostics.py`
  (`load_radionuclide_half_lives`), `multi_isotope_decay.py` (primitives),
  `radionuclide.py` (identity dataclass).
- **Primary Symbols:** `retained_fraction(elapsed, half_life) = 2 ** (-t/hl)`,
  `activity_after_decay`, `required_upstream_activity`.
- **Primary Tests:** `test_multi_isotope_decay.py`, `test_f18_decay_model.py`.
- **Authority Type:** B. **Implementation Status:** IMPLEMENTED.
  **Calibration Status:** CALIBRATED (physics constants).
- **Canonical half-lives (minutes):** F-18 109.8 · Ga-68 67.7 · C-11 20.3 ·
  N-13 9.97 · O-15 2.04 · Tc-99m 360.0 · Mo-99 3956.4.
- **Superseded / shims:** `decay_engine.py` and `production_engine.py` are thin
  re-export shims (not authorities). `f18_decay_model.py` is an F-18-only legacy
  MVP evaluator. There is **no** `radionuclides.py` (plural) file.
- **Doctrine:** CALIBRATION FOR RADIONUCLIDE A DOES NOT QUALIFY RADIONUCLIDE B
  (F-18 must never qualify C-11/N-13/O-15/Ga-68/Cu-64/Zr-89/I-123/I-124/Tc-99m).

### 2.6 Cyclotron authority (Build 3B)

- **Canonical Authority:** Cyclotron catalog + per-radionuclide capacity resolver.
- **Primary Files:** `cyclotron_catalog.py`, `cyclotron_equipment_catalog.json`,
  `cyclotron_production_windows.py`, `cyclotron_fleet_recommendation.py`,
  `multi_cyclotron_authority.py`, `pettrace_800_capability.py`, `cyclotron.py`.
- **Primary Symbols:** `CyclotronCatalogModel`, `load_cyclotron_catalog`,
  `FacilityCyclotronInstance`, `build_fleet_from_instances`,
  `_resolve_calibrated_eob_by_radionuclide`,
  `resolve_fleet_eob_capacity_mbq_per_day`,
  `CyclotronCatalogModel.production_calibration_status`.
- **Primary Tests:** `test_build3b_production_authority.py`,
  `test_cyclotron_catalog_foundation.py`,
  `test_cyclotron_catalog_e2e_integration.py`,
  `test_cyclotron_production_windows.py`, `test_cyclotron_fleet_integration.py`,
  `test_multi_cyclotron_radionuclide_authority.py`.
- **Authority Type:** B. **Implementation Status:** IMPLEMENTED.
  **Calibration Status:** per-model **MIXED**.
- **Doctrine preserved:** SUPPORTED ≠ CALIBRATED. Beam specs / supported vs
  schedulable radionuclides / calibrated production are three separate dimensions.
- **Key catalog facts (verified):**
  - GE PETtrace **890** F-18 CALIBRATED at **648000 MBq** (also 840=240000,
    860=403000, 880=524000).
  - `SUMITOMO_CYPRIS_MP_30` **SUPPORTS** F-18/Cu-64/Zr-89/I-123/I-124/Ga-68 but
    `production_performance_records = []` → `production_calibration_status =
    "not_calibrated"`. An explicitly selected CYPRIS MP-30 **cannot borrow**
    PETtrace 890 / 648000 MBq / another model's calibrated capacity (Part 3D
    installed-selection binding).
  - GE PETtrace **800** (legacy) supports 5 isotopes with all-null EOB →
    SUPPORTED but NOT_CALIBRATED.
- **Provenance/Build:** Build 3B (documented in
  `CYCLOTRON_PRODUCTION_DATA_AUTHORITY_BUILD_3B.md`).

### 2.7 Cyclotron normalization authority

- **Primary Symbols:** `cyclotron_catalog._normalize_activity_to_mbq`
  (GBq/Ci → MBq), `_parse_performance_record`. Raw manufacturer evidence →
  canonical radionuclide-specific `normalized_eob_activity_mbq`.
- **Implementation Status:** IMPLEMENTED. Normalization creates common
  engineering units; it does **not** make radionuclides interchangeable
  (`_resolve_calibrated_eob_by_radionuclide` matches `record.radionuclide ==
  isotope` only; a normalized F-18 MBq figure can never become C-11 capacity).

### 2.8 Physical batch vs patient cohort

- **Doctrine:** PATIENT / ADMINISTRATION COHORT ≠ PHYSICAL CYCLOTRON PRODUCTION
  BATCH.
- **Primary File:** `production_clinical_schedule.py`. **Symbols:** cohort =
  `FacilityDayPatientDemand` / `PatientRadionuclideDemand` /
  `ProductionClinicalPatientTrace`; physical batch = `RadionuclideBatchDemand` →
  `ProductionWindow` → `ProductionBatchReleaseMapping` / `ReleasedDoseInventory`.
- **Implementation Status:** IMPLEMENTED (kept structurally separate; a patient
  trace records `batch_id` but the physical batch is scheduled independently by
  cyclotron capacity/windows). Physical batch count is never fabricated.

### 2.9 Cyclotron Production Estimation Authority

- **Canonical Authority:** numerical cyclotron production-estimation layer.
- **Primary File:** `cyclotron_production_estimation_authority.py`.
- **Evidence Registry:** `cyclotron_production_evidence.json` (traceable external
  / reaction-physics `MODELED_ESTIMATE` evidence; sources doc
  `CYCLOTRON_PRODUCTION_EVIDENCE_SOURCES.md`). NEVER holds manufacturer/site
  calibrated output and never changes `production_calibration_status`.
- **Primary Symbols:** `estimate_cyclotron_production`,
  `CyclotronProductionEstimate` (now with additive `evidence_record_id` /
  `source_reference`), `estimate_required_physical_cycles`,
  `CyclotronBatchCycleEstimate`, `resolve_simulation_production_basis`,
  `stronger_basis`; `EvidenceClass`, `EstimationStatus`, `ConfidenceClass`;
  evidence-registry seam: `ProductionEvidenceRecord`,
  `load_production_evidence_registry`, `resolve_evidence_registry_records`,
  `resolve_evidence_record` / `EvidenceResolution`.
- **Primary Tests:** `test_cyclotron_production_estimation_authority.py`
  (37 tests: 30 invariants + control proofs A–F + unknown-model raise);
  `test_cyclotron_production_evidence_extension.py` (34 Section-38 invariants + 2
  additional: unknown-model raise, missing-registry graceful degradation).
- **Documentation:** `CYCLOTRON_PRODUCTION_ESTIMATION_AUTHORITY.md` (with the
  Cyclotron Production Evidence & Calibration Extension addendum),
  `CYCLOTRON_PRODUCTION_EVIDENCE_SOURCES.md`.
- **Authority Type:** B (IMPLEMENTED_REPOSITORY_AUTHORITY).
- **Implementation Status:** IMPLEMENTED (estimation layer). Sits BETWEEN Build
  3B production evidence and downstream batch/capacity planning; creates no
  second catalog / radionuclide authority / capacity resolver.
- **Evidence hierarchy (runtime precedence):** `SITE_CALIBRATED` >
  `MANUFACTURER_CALIBRATED` > `MODELED_ESTIMATE` > `CONTROLLED_ASSUMPTION` >
  `NOT_AVAILABLE`. The result preserves BOTH the evidence status AND the
  numerical value; `MODELED_ESTIMATE` never overwrites calibration status.
- **Methodology:** the sole modeled relationship is the saturation activation
  form `A_EOB = K·I·(1−exp(−λt))` (reused from
  `cyclotron_catalog.calculate_eob_activity_from_calibrated_record`), with `K`
  fit from the pair's OWN manufacturer-calibrated anchor — never borrowed across
  models or radionuclides. Radionuclide-specific throughout; no patient identity;
  no legacy 10% production blocks; no usable-doses fallback; no revenue.
- **Doctrine preserved:** SUPPORTED ≠ CALIBRATED ≠ NUMERICALLY ESTIMABLE.
  `SUMITOMO_CYPRIS_MP_30` + F-18 = SUPPORTED / NOT_CALIBRATED / estimation
  NOT_AVAILABLE (no GE PETtrace 890 / 648000 MBq borrowing). Tc-99m and other
  generator daughters = `OUT_OF_CYCLOTRON_SCOPE`.
- **Part 3D integration:** additive `RadionuclideProductionGate.
  simulation_production_basis` (default `UNRESOLVED`) records the modeled basis
  for a SUPPORTED-but-NOT_CALIBRATED installed model **without** changing the
  `PRODUCTION_NOT_CALIBRATED` evidence verdict.
- **Evidence extension:** the Cyclotron Production Evidence & Calibration
  Extension added the registry above and enabled **two** new numerical pairs —
  **SIEMENS Eclipse HP + F-18** and **SIEMENS RDS-111 + F-18** are each now a
  `MODELED_ESTIMATE` (LOW confidence) from the `18O(p,n)18F` reaction saturation
  yield applied to each model's OWN 60 µA current (identical values because both
  Siemens/CTI models publish the same 60 µA, not a borrow).
  **CYPRIS MP-30 + F-18 remains `NOT_AVAILABLE`**
  (no OWN beam current; no GE borrowing). Calibrated controls (GE PETtrace 890 =
  648 000 MBq) and the Part 3D CYPRIS gate control unchanged.
- **Known Limitations:** most pairs remain `NOT_AVAILABLE` for lack of physical
  evidence; no `SITE_CALIBRATED` cyclotron record and no approved
  `CONTROLLED_ASSUMPTION` currently exist; Cu-64/Zr-89/I-123/I-124 lack canonical
  half-life physics.
- **Open-Gap Ref:** OG-CYC-1 (still PARTIAL — authority + evidence registry
  exist; two pairs evidence-closed; remaining model × radionuclide evidence gaps
  documented).

### 2.10 Generator authority

- **Canonical Authority:** Generator catalog + Bateman physics.
- **Primary Files:** `generator_catalog.py`, `generator_equipment_catalog.json`,
  `generator.py`, `generator_economics.py`.
- **Primary Symbols:** `GeneratorCatalogModel`, `load_generator_catalog`,
  `GeneratorAsset.available_tc99m_activity_mbq` / `.elute()`, `PreparationBatch`.
- **Primary Tests:** `test_pet_spect_generator_native_authority_completion.py`,
  `test_build3b_production_authority.py`.
- **Authority Type:** B. **Implementation Status:** IMPLEMENTED (Mo-99 → Tc-99m;
  Ge-68 → Ga-68 pathway now canonical). **Calibration Status:** physics
  `literature_calibrated`; all economics `NOT_CALIBRATED`.
- **Models:** `CURIUM_TECHNELITE`, `CURIUM_ULTRA_TECHNEKOW_FM`,
  `GE_HEALTHCARE_DRYTEC` (all Mo-99 → Tc-99m, elution 0.85, 2 elutions/day,
  14-day life); `ECKERT_ZIEGLER_GALLIAPHARM` (Ge-68 → Ga-68).
- **Known Limitations:** the Ge-68/Ga-68 generator **pathway identity** is now
  canonical (OG-GEN-1 = `PATHWAY_CLOSED`, Clinical Radionuclide Completeness
  build) — Ga-68 carries BOTH a cyclotron and a generator pathway, kept distinct.
  Generator procurement/production economics (reference activity, useful life,
  elution efficiency, max elutions/day for the Ge-68/Ga-68 unit) remain
  `NOT_CALIBRATED`. See OG-GEN-1.

### 2.11 Transport building-block authority (Build 3C)

- **Doctrine:** Five/six transport modes are composable building blocks; MRT is
  optional.
- **Primary Files / Symbols:**
  - Manual/Porter — `conventional_transport_authority.py`
    (`compute_manual_mission_timing`, `compute_porter_resource_requirement`).
  - RGHT / RHTS (rail-guided) — `rght_spatial_network_authority.py`;
    identity in `transport_technology_authority.py`
    (`RAIL_GUIDED_HOSPITAL_TRANSPORT = "RGHT"`,
    `normalize_transport_technology("AGV_AMR") == "RGHT"`).
  - Ordinary PTS — `pts_spatial_network_authority.py`
    (+ `conventional_transport_authority.PneumaticTubeNetwork`).
  - Dedicated RP-PTS — `dedicated_rp_pts_authority.py` (`compute_rp_pts_mission_cycle`,
    `compute_rp_pts_capex/opex/labor`).
  - MRT — `shared_mrt_multistream_authority.py`, `mrt_carrier_fleet.py`,
    `mrt_auxiliary_systems_authority.py`,
    `mrt_transport_energy_maintenance_authority.py`.
  - Shared bridge — `transport_mission_route_bridge.py`.
- **Primary Tests:** `test_build3c_transport_authority.py`,
  `test_dedicated_rp_pts_authority.py`, `test_mrt_carrier_fleet.py`,
  `test_transport_spatial_authority_build{1..4}.py`.
- **Authority Type:** B. **Implementation Status:** IMPLEMENTED.
- **Distinctness preserved:** Ordinary PTS ≠ RP-PTS (distinct modules/ledgers);
  RGHT (rail-guided) is DISTINCT from true free-roaming `FLOOR_AGV_AMR`.
- **Known Limitations:** true free-roaming `FLOOR_AGV_AMR` =
  `NOT_IMPLEMENTED` (`FLOOR_AGV_AMR_IMPLEMENTATION_STATUS`, no floor
  graph/path-planning/collision/charging model). See OG-TRN-1.
- **Provenance/Build:** Build 3C
  (`FIVE_MODE_TRANSPORT_AUTHORITY_BUILD_3C.md`).

### 2.12 Transport resource authority

- **Dimensions (all IMPLEMENTED with honest NOT_CALIBRATED sentinels):** mission
  timing, fleet sizing / peak concurrency, carrier/vehicle, station/endpoint,
  route, CapEx, OPEX, energy, maintenance.
- **Primary Symbols:** `agv_required_fleet_size`, `pts_required_station_count`,
  `compute_porter_resource_requirement`, `compute_rp_pts_labor`;
  energy/maintenance in `mrt_transport_energy_maintenance_authority.py` +
  `mrt_auxiliary_systems_authority.py` (`compute_mrt_total_electrical_load`,
  `evaluate_site_power_adequacy`, `compute_mrt_*_annual_maintenance_usd`);
  pre-existing `equipment_energy_opex.py`.

### 2.13 Payload / service-class / color authority

- **Primary File:** `mrt_service_class_authority.py`
  (+ `shared_mrt_multistream_authority.py`).
- **Primary Symbols:** `MrtServiceClass`, `ServiceClassProfile`,
  `SERVICE_CLASS_REGISTRY`, `configured_active_color`,
  `effective_display_color`.
- **Primary Tests:** `test_shared_mrt_multistream_authority.py`,
  `test_mrt_multistream_service_class_closure.py`,
  `test_build3c_transport_authority.py`.
- **Authority Type:** B. **Implementation Status:** IMPLEMENTED.
- **Doctrine (enforced in code):** TRANSPORT SHAPE = mechanism; PAYLOAD COLOR =
  substance/service class. **Color is presentation metadata only** — it does not
  determine physics, routing, capacity, eligibility, CapEx, OPEX, or ranking
  (color fields are structurally separate from priority/speed fields). The same
  payload/service class keeps the same color across eligible modes. Carrier
  identity, container identity, payload identity, and service-class identity are
  distinct; patients and rooms do **not** inherit payload color.
- **Service classes:** ACTIVE — RADIOPHARMACEUTICAL_NUCLEAR (VIOLET, P1),
  SPECIMEN_BLOOD (BLUE, P2), PHARMACY_INFUSION (TEAL, P2), STERILE_CLEAN_SUPPLY
  (AMBER, P3), LAUNDRY_CLEAN_LINEN (GOLD, P4); INACTIVE_FUTURE — FOOD_NUTRITION
  (GREEN), WASTE (RED). Uncalibrated speeds are honestly `NOT_CALIBRATED`.

### 2.14 Spatial routing authority (Build 3C.1)

- **Primary Files:** `canonical_spatial_authority.py` (`resolve_route`),
  `human_circulation_authority.py`, `canonical_geometry_shadow_routing_authority.py`,
  `authoritative_geometry_routing_activation.py`, `shared_network.py`.
- **Primary Tests:** `test_build3c1_spatial_route_authority.py`,
  `test_canonical_spatial_authority_closure.py`,
  `test_canonical_geometry_shadow_routing_authority.py`.
- **Authority Type:** B. **Implementation Status:** IMPLEMENTED.
- **Two route families:**
  - **HUMAN_CIRCULATION_NETWORK** — patients, porters/Manual, AGV/AMR follow
    authorized human geometry (corridors/doors/elevators).
  - **CONCEALED_SERVICE_TRANSPORT_CORRIDOR** — MRT, RHTS/RGHT, Ordinary PTS,
    RP-PTS share an architectural service right-of-way concept while retaining
    distinct mode-specific lanes.
- **Enforced doctrine:** SHARED RIGHT-OF-WAY ≠ SHARED TRACK (`resolve_route`
  BFS runs over the mode-compatible subgraph only); SHARED RIGHT-OF-WAY ≠ MODE
  INSTALLED. MISSION_ROUTE_GEOMETRY vs INSTALLED_NETWORK_GEOMETRY are separated
  (`compute_installed_network_union` counts a shared segment once, never a naive
  sum). `SHARED_CORRIDOR_ELIGIBLE_MODES` may borrow the MRT reference corridor
  **distance only**, never its speed/capacity/economics.
- **Provenance/Build:** Build 3C.1
  (`SPATIAL_ROUTE_NETWORK_AUTHORITY_BUILD_3C1.md`).

### 2.15 Movement / trajectory authority

- **Primary File:** `production_trajectory_authority.py`
  (+ `operational_day_trajectory_scene.py`).
- **Primary Symbols:** `build_mrt_trajectory`, `build_rght_trajectory`,
  `build_pts_trajectory`, `build_porter_trajectory`, `build_patient_trajectory`,
  `_build_human_trajectory`, `validate_distance_conservation`,
  `validate_time_conservation`.
- **Primary Tests:** `test_production_trajectory_authority.py`,
  `test_operational_day_trajectory_scene.py`.
- **Authority Type:** B. **Implementation Status:** IMPLEMENTED for
  patients/staff(porters)/MRT/RGHT/PTS; **RP-PTS = PARTIAL** (mission-cycle
  timing implemented, no dedicated per-sample trajectory sampler).
- **Enforced doctrine:** humans cannot move through walls — human-circulation
  entities follow valid human-network edges (`_build_human_trajectory` resolves
  via `resolve_pedestrian_route` + mode-compatible edges; "never
  straight-line-through-walls"); automated systems follow their own networks.
- **Open-Gap Ref:** OG-TRN-2 (RP-PTS trajectory sampler).

### 2.16 Simulation movement contract

- **Authority Type:** A (LOCKED_PRODUCT_DOCTRINE) — the animated-simulation
  runtime contract is largely PLANNED; the trajectory authority (2.15) and the
  presentation bridge (`dynamic_scene_state_authority.py`,
  `to_dynamic_object_trajectory`) implement its foundations.
- **Locked rules:** stationary infrastructure stays stationary (PTS/RP-PTS tubes,
  MRT guideway, RHTS track); carriers/capsule contents move; payload stays with
  the carrier/porter until a valid interface/handoff; after delivery the payload
  may disappear from transport visualization while its digital trace persists;
  patient color and room color do not change because a payload was delivered;
  empty carrier return/reposition is a visible/resource event where modeled.

### 2.17 Bentley / iTwin authority

- **Role:** Bentley / iTwin = facility / engineering / BIM geometry and
  infrastructure context. Conceptual flow: Bentley/BIM/CAD/other geometry →
  MRT Pharma Engineering Object Model → route networks → engineering
  calculations → physical feasibility → optimization. **Bentley does NOT replace
  MRT Pharma.**
- **Primary Files:** `bentley_itwin_client.py`, `bentley_canonical_binding.py`,
  `bentley_access_recovery.py`, `bentley_personal_user_diagnostic.py`,
  `ifc_hospital_proof_model_generator.py`.
- **Primary Symbols:** `BentleyItwinClient`, `BentleyTransport` (injectable),
  `bentley_live_environment_available`, `bind_live_bentley_element`.
- **Primary Tests:** `test_bim_itwin_phase1_bentley_binding.py`,
  `test_bim_itwin_phase2a_hospital_ifc_proof_model.py`,
  `test_bim_itwin_phase2a1_bentley_renderability.py`,
  `test_bim_itwin_phase2b_live_bentley_binding.py`,
  `test_bentley_access_recovery.py`,
  `test_bentley_development_resource_adoption.py`,
  `test_bentley_itwins_v1_contract_correction.py`,
  `test_bentley_personal_user_diagnostic.py`.
- **Authority Type:** B (client scaffold + binding) + C (live connection).
- **Implementation Status:** **PARTIAL.** The typed client, injectable transport,
  and canonical binding are IMPLEMENTED; a real `BentleyHttpTransport` + OAuth
  exist but are opt-in (`# pragma: no cover`, gated by
  `bentley_live_environment_available()`) — **no automated live connection is
  exercised**. IFC proof-model generation is IMPLEMENTED but is a
  **CONTROLLED TEST FIXTURE only** (synthetic IFC4, not a geometry authority).
- **Identity governance:** a Bentley external element identity is **never**
  canonical identity — `bind_live_bentley_element` resolves to an already-existing
  `mrtway_object_id` and refuses to fabricate one.
- **Open-Gap Ref:** OG-BEN-1 (live integration / real BIM ingestion).

### 2.18 NVIDIA / OpenUSD authority

- **Role:** NVIDIA / OpenUSD = visualization / simulation-presentation layer.
  Doctrine: **ENGINEERING ENGINE DECIDES → NVIDIA VISUALIZES.**
- **Primary Files:** `openusd_spatial_adapter.py`, `openusd_yc_demo_binding.py`,
  `dynamic_scene_state_authority.py`, `digital_twin_simulation_state.py`,
  `generate_openusd_hospital_dynamic_foundation_demo.py`,
  `generate_openusd_hospital_visual_demo.py`.
- **Primary Symbols:** `OPENUSD_RUNTIME_AVAILABLE`, `OpenUsdRuntimeNotAvailable`,
  `DynamicObjectTrajectory`, `simulation_minutes_to_usd_timecode`,
  `to_dynamic_object_trajectory`.
- **Primary Tests:** `test_openusd_spatial_adapter.py`,
  `test_openusd_yc_demo_binding.py`, `test_dynamic_scene_state_authority.py`,
  `test_operational_day_trajectory_scene.py`.
- **Authority Type:** B (USD export/presentation) + A (doctrine).
- **Implementation Status:** IMPLEMENTED as **presentation/export** using real
  Pixar `usd-core` (vendored `.usd_runtime/`; raises `OpenUsdRuntimeNotAvailable`
  if absent, never fabricates an SDK). **NO NVIDIA Omniverse/Kit/nucleus runtime
  connection** (zero `omni` imports; "NVIDIA" is the branding for the
  presentation layer, concretely `.usda/.usd` file generation).
- **Enforced doctrine:** visualization never changes simulation physics
  (`OPENUSD_SELECTS_TRANSPORT_SOLUTION = NO`,
  `OPENUSD_BECOMES_ENGINEERING_AUTHORITY = NO`; samples copied verbatim from the
  engine; `USD_PRIM_PATH` is never authoritative). Concealed systems may remain
  visible in X-ray/cutaway/network-isolation/follow-entity views.
- **Open-Gap Ref:** OG-USD-1 (Omniverse runtime PLANNED).

### 2.19 Bentley / MRT Pharma / NVIDIA role separation

- **BENTLEY / iTwin** = engineering/facility geometry context.
- **MRT PHARMA** = engineering logic + physics + optimization + economics +
  operations.
- **NVIDIA / OpenUSD** = visualization / animation / interactive simulation
  presentation.
- **Authority Type:** A (LOCKED_PRODUCT_DOCTRINE). These three layers must never
  be conflated.

### 2.20 Facility input authority

- **Primary Files:** `facility_engineering_model.py`,
  `facility_expansion_authority.py`, `interactive_spatial_authoring.py`,
  `existing_facility_retrofit.py`, `editable_default_authority.py`.
- **Primary Symbols:** `SpatialInputPath` (UPLOAD/MANUAL/BENCHMARK),
  `SpatialSourceType` (IFC/REVIT_BIM/DWG/DXF/PDF/IMAGE/MANUAL/TEMPLATE/BENCHMARK/
  OTHER), `SUBSCRIPTION_CAPABILITY_MAP`, `resolve_subscription_capability_profile`.
- **Primary Tests:** `test_facility_engineering_model.py`,
  `test_facility_expansion_authority_build4{a,b,c}.py`,
  `test_interactive_spatial_authoring.py`, `test_existing_facility_retrofit.py`.
- **Authority Type:** B (taxonomy/authoring) + C (file ingestion).
- **Implementation Status:** **PARTIAL.** IMPLEMENTED: manual/blank authoring
  (`interactive_spatial_authoring.py`), TEMPLATE/BENCHMARK paths, and
  user-supplied-facts retrofit (`existing_facility_retrofit.py`).
  **PLANNED / NOT_MODELED:** actual parsing/reconstruction of IFC/Revit/DWG/DXF/
  PDF/image (these exist only as enum members + subscription/validation
  metadata — no parser code). BIM is NOT mandatory. Geometry is kept separate
  from the engineering object model (design invariant).
- **Open-Gap Ref:** OG-FIN-1 (file ingestion parsers PLANNED).

### 2.21 Lockdown / What-If authority

- **Primary Files:** `lockdown_what_if_lineage_authority.py`,
  `live_engineering_impact_binding.py`,
  `reactive_engineering_economic_consequence_authority.py`,
  `live_operational_state.py`.
- **Primary Symbols:** `CanonicalLockdownRecord`, `CanonicalWhatIfRecord`,
  `LockdownLineageRegistry`, `promote_what_if_to_lockdown`, `PlanVersion`.
- **Primary Tests:** `test_lockdown_what_if_lineage_authority.py`,
  `test_auxiliary_systems_and_unified_what_if_authority.py`,
  `test_live_engineering_impact_binding.py`,
  `test_live_state_rolling_reoptimization.py`.
- **Authority Type:** B. **Implementation Status:** IMPLEMENTED.
- **Doctrine (enforced):** LOCKDOWN = authoritative immutable scenario baseline;
  WHAT-IF = non-authoritative branch that recomputes affected engineering.
  `promote_what_if_to_lockdown` creates a NEW lockdown (parent recorded, prior
  lockdown marked SUPERSEDED, never deleted/overwritten). "Live" means
  synchronous recompute — not hospital telemetry, not a live vendor API.

### 2.22 Physical feasibility authority (Part 3D)

- **Primary File:** `whole_oncology_four_architecture_optimization.py`.
- **Primary Symbols:** `derive_physical_feasibility`, `PhysicalFeasibilityResult`,
  `ClinicalResourceInputs`, `BENCHMARK_CLINICAL_RESOURCES`,
  `_resolve_production_gate`, `_resolve_radionuclide_production_gate`,
  `_resolve_transport_gate`, `compute_clinical_resource_peak_occupancy`,
  `_physical_feasibility_result_fields`.
- **Primary Tests:** `test_part3d_physical_feasibility_closure.py` (46 tests).
- **Authority Type:** B. **Implementation Status:** IMPLEMENTED
  (committed at `07e861d`).
- **Canonical chain:** Patient Demand → Production → Transport → Injection →
  Uptake → Scanner → Completed Patient.
- **Behavior:** `ArchitectureResult.feasible` is **DERIVED** (not hardcoded) via
  the single seam `_physical_feasibility_result_fields` (`feasible =
  status != INFEASIBLE`), consumed by all four canonical evaluators. Gates:
  scanner/injection/uptake (`compute_clinical_resource_peak_occupancy`),
  per-radionuclide production (`_resolve_production_gate`), and mode-specific
  transport (`_resolve_transport_gate` — never a single universal transport
  scalar). Clinical benchmark = **6 scanners / 6 injection / 12 uptake**,
  `CONTROLLED_BENCHMARK`, with project override via `ClinicalResourceInputs`.
- **Doctrine preserved:** NOT_CALIBRATED ≠ ZERO; NOT_CALIBRATED ≠ AUTOMATIC
  INFEASIBILITY (uncalibrated production →
  `FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY` /
  `QUALIFIED_WITH_LIMITATIONS`). Production gate is radionuclide-specific.
- **Known Limitations (self-disclosed, test-locked):**
  `evaluate_light_mrt_dominant` still hardcodes `feasible=True` (not wired to the
  common contract); the physical transport gate directly covers the MRT-carrier
  and conventional-nuclear-transporter searches, while PORTER/AGV/RGHT/PTS/RP-PTS
  are represented economically but not yet in the physical gate. See OG-P3D-1,
  OG-P3D-2.
- **Provenance/Build:** Part 3D
  (`PHYSICAL_FEASIBILITY_AUTHORITY_PART_3D.md`).

### 2.23 Scanner / imaging equipment authority (Section 25A)

- **Canonical Authority:** Unified PET+SPECT scanner equipment catalog.
- **Primary Files:** `scanner_catalog.py`, `scanner_equipment_catalog.json`
  (model authority); `scanner.py` (bare capacity dataclass — no manufacturer/
  model identity); `clinical_resource_identity.py` (`ScannerModality`).
- **Primary Symbols:** `ScannerCatalogModel`, `ScannerCatalog`,
  `load_scanner_catalog`, `FacilityScannerInstance`, `ScannerEconomicRecord`.
- **Primary Tests:** `test_clinical_resource_identity.py`,
  `test_clinical_bottleneck_authority.py` (scanner-count gate via Part 3D).
- **Authority Type:** B. **Implementation Status:** IMPLEMENTED (catalog schema
  mirrors `cyclotron_catalog.py`). **Calibration Status:** technical fields
  `literature_calibrated` (medium confidence); power/dimensions and ALL economics
  (`purchase_capex`, `annual_service_opex`) = `NOT_CALIBRATED`.
- **SCANNER RESOURCE COUNT vs SCANNER MODEL / MODALITY:** distinguished. The
  Part 3D clinical benchmark counts (6 scanners / 6 injection / 12 uptake) are a
  **count** authority (`ClinicalResourceInputs`), separate from this **model**
  authority. Six scanners does not imply six equivalent models — models differ by
  modality, protocol families, acquisition minutes, CT configuration, etc.
- **Manufacturer inventory (verified from `scanner_equipment_catalog.json`):**

  | Manufacturer | Model | Modality | Commercial status | Economics |
  |---|---|---|---|---|
  | Siemens Healthineers | Symbia Pro.specta | SPECT | current | NOT_CALIBRATED |
  | Siemens Healthineers | Biograph Vision | PET | current | NOT_CALIBRATED |
  | GE HealthCare | NM/CT 870 DR | SPECT | current | NOT_CALIBRATED |
  | GE HealthCare | NM/CT 860 | SPECT | current | NOT_CALIBRATED |
  | GE HealthCare | Discovery MI | PET | current | NOT_CALIBRATED |
  | Philips | BrightView XCT | SPECT | LEGACY_INSTALLED_BASE | NOT_CALIBRATED |

  - `SIEMENS_HEALTHINEERS_SCANNER_AUTHORITY` = IMPLEMENTED (in `scanner_catalog.py`).
  - `SIEMENS_HEALTHINEERS_SCANNER_MODELS` = Symbia Pro.specta (SPECT),
    Biograph Vision (PET).
  - `SIEMENS_HEALTHINEERS_SCANNER_DATA_STATUS` = technical fields
    `literature_calibrated`; economics/power/dimensions `NOT_CALIBRATED`.
  - `GE_HEALTHCARE_SCANNER_AUTHORITY` = IMPLEMENTED (NM/CT 870 DR, NM/CT 860,
    Discovery MI).
  - `PHILIPS_SCANNER_AUTHORITY` = IMPLEMENTED (BrightView XCT, LEGACY_INSTALLED_BASE).
  - `OTHER_SCANNER_MANUFACTURER_AUTHORITIES` = none present.
- **Canonical scanner schema:** exists (`ScannerCatalogModel`); economics use the
  same `NOT_CALIBRATED`-honest pattern as the cyclotron/generator catalogs.
- **Known Limitations:** scanner economics/power/footprint uncalibrated; the
  study-level PET scanner cost anchor remains the generic
  `PlannerAssumptions.scanner_capex`. See OG-SCN-1.
- **Scanner Authority Review & Part 3E Readiness** (uncommitted; starting SHA
  `a1002ca`; artifacts `SCANNER_AUTHORITY_REVIEW_PART_3E_READINESS.md` +
  `test_scanner_authority_review.py`). Physically-verified conclusions:
  - Scanner **quantity** authority = READY (`required_scanner_count`,
    demand→count ceiling division); **PET/SPECT modality** authority = READY
    (`check_modality_capacity` enforces separation by construction;
    `scanners_of_modality` excludes untagged scanners from both pools);
    **model-specific** ranking = NOT_YET_RANKABLE (economics/power/geometry
    `NOT_CALIBRATED`/`NOT_MODELED`).
  - Part 3E readiness: `QUANTITY=YES`, `MODALITY=YES`, `MODEL=NO`,
    Phase-1 mode = `CLASS_AND_MODALITY`, `PHASE_1_READY=YES`. Result =
    `READY_WITH_DOCUMENTED_LIMITATIONS`.
  - Part 3D scanner gate is a single aggregate count (modality-agnostic) reading
    `nuclear.candidate.scanners`; `feasible` is DERIVED for the four canonical
    architectures but hardcoded in the `evaluate_light_mrt_dominant` variant and
    `ZonalHybridPartitionCandidate` (OG-SCN-2).
  - Patient-awareness lives in the scheduling/calendar layer
    (`long_horizon_operational_planning.py`, `PatientOperationalPlan`); the
    scanner **catalog** carries NO patient identity (boundary preserved).
  - Long-horizon Hospital-Master-Calendar foundation EXISTS
    (`long_horizon_operational_planning.py`, data-driven horizon, single validated
    day engine per date); scanner availability is date-level; intra-day
    maintenance/downtime windows remain `PARTIAL`/`NOT_MODELED`.
  - A schedule-derived equipment **energy** authority exists
    (`equipment_energy_opex.py`, duty from the actual plan) but the monetary layer
    (per-model power kW + service $) is `NOT_CALIBRATED` (OG-OPEX-1).

### 2.23A Equipment OPEX Authority (physical driver → componentized annual OPEX)

- **Primary Files:** `equipment_opex_authority.py`,
  `test_equipment_opex_authority.py`, `EQUIPMENT_OPEX_AUTHORITY.md` (uncommitted;
  starting SHA `df7bf03`).
- **Primary Symbols:** `EquipmentOpexComponent`, `EquipmentOpexResult`,
  `EquipmentOpexClass` (`SCANNER`/`CYCLOTRON`/`GENERATOR`), `EvidenceStatus`
  ladder, `build_opex_component` (no-zero-fill choke point),
  `weakest_evidence`, `compute_scanner_opex`, `compute_cyclotron_opex`,
  `compute_generator_opex`, `derive_cyclotron_utilization_from_cycles`,
  `derive_generator_replacement_schedule`, `annualize_horizon_quantity`.
- **Nature:** COMPOSES `equipment_energy_opex.py` (and the cyclotron/generator/
  scanner catalogs + the long-horizon production plan) into componentized annual
  OPEX. Introduces NO new duty-cycle engine, NO physics, NO catalog. Reuses the
  existing `EconomicComparabilityStatus` vocabulary and the
  `electricity_cost_per_kwh` (`CONTROLLED_ASSUMPTION`) tariff.
- **Doctrine enforced:** physical driver and monetary unit cost carry SEPARATE
  evidence classes (weakest governs); `annual_cost_usd` is `None` (never `$0`)
  when either side is uncalibrated; `known_annual_opex_subtotal_usd` may be
  numeric while `total_annual_opex_status = NOT_CALIBRATED`; never back-derive `$`
  from EOB activity / `nameplate × 8760` / %-of-CapEx-as-manufacturer.
- **Calibration Status:** physical-driver + componentization layer IMPLEMENTED;
  scanner/cyclotron **power kW**, all **service/consumable/procurement $** remain
  `NOT_CALIBRATED` (OG-OPEX-1 still PARTIAL). Part 3E Phase 1 consumable with
  qualified economics.
- **Boundary:** no patient identity accepted by any class (scanner/cyclotron/
  generator OPEX); patient-aware batch-planning boundary preserved.

### 2.24 Patient / batch / production-equipment awareness boundary

Governance navigation for the synthetic-patient → batch-planning →
cyclotron/generator authority layering (product doctrine: `MRT_PHARMA_PRODUCT_DOCTRINE.md`
§11A). Directional chain (§2.4) is preserved; this row adds the **patient-awareness
boundary** at each layer.

- **Synthetic patient radionuclide generation.**
  - **Primary Files:** `synthetic_radionuclide_source_capability.py`
    (`resolve_admissible_radionuclides` → `SyntheticRadionuclideCapabilityResult`,
    `choose_normal_synthetic_radionuclide`, `NoCompatibleSourceError`) — the
    source-capability resolver; `oncology_pet_spect_scenario.py`
    (`build_representative_day_population`, `build_stochastic_representative_day_population`
    now accept optional `selected_cyclotron_ids` / `selected_generator_ids` /
    `mode`; benchmark constants `PET_RADIONUCLIDE = "F-18"` /
    `SPECT_RADIONUCLIDE = "Tc-99m"` remain the backward-compatible default when no
    selected-source ids are supplied), `patient_radionuclide_demand.py`
    (`PatientRadionuclideDemand`, explicit-demand path),
    `inbound_patient_program.py` (`generate_synthetic_patient_population`,
    explicit-demand path).
  - **Doctrine:** the NORMAL synthetic generator constrains demanded radionuclides
    to the **combined selected production-source capability set** (cyclotron
    `supported_radionuclides` ∪ generator `daughter_radionuclide`, filtered by
    clinical modality), resolved **before patient creation**. EXPLICIT /
    STRESS_TEST demand is preserved and exposed downstream as
    `NO_COMPATIBLE_SOURCE`, never silently mutated.
  - **Authority Type:** B (IMPLEMENTED_REPOSITORY_AUTHORITY) for the resolver and
    the NORMAL representative-path binding.
  - **Implementation Status:** **IMPLEMENTED (normal representative path)** by the
    Synthetic Patient Radionuclide Source-Capability Binding build (OG-SYNTH-1).
    The resolver derives the admissible set from the SELECTED sources (SUPPORT
    semantics; no calibration/estimator/capacity/economics consulted; no
    global-catalog fallback), preserving source identity and de-duplicating.
    `build_representative_day_population` consumes it when selected-source ids are
    supplied and raises `NoCompatibleSourceError` rather than fabricating or
    substituting; with no selected-source ids the representative benchmark
    (F-18 / Tc-99m) is preserved unchanged. Following the Clinical Radionuclide
    Completeness build the canonical modality recognition set is 12 radionuclides
    (PET = F-18/C-11/N-13/O-15/Ga-68/Cu-64/Zr-89/I-124; SPECT = Tc-99m/I-123/
    In-111/Tl-201); any radionuclide still outside the recognition set is reported
    as `SUPPORTED_BUT_NOT_CLINICALLY_MODALITY_CLASSIFIED` (never invented).
    **Focused test:** `test_synthetic_patient_source_capability.py`.
    **Doc:** `SYNTHETIC_PATIENT_SOURCE_CAPABILITY_AUTHORITY.md`.
  - **Open-Gap Ref:** OG-SYNTH-1 = **PARTIAL** (selected-source representative
    binding implemented and test-locked; NOT globally CLOSED because the
    default/legacy path with no selected-source ids remains benchmark-driven, and
    the explicit inbound path is explicit-demand by design).

- **Patient-aware batch-production planning.**
  - **Primary Files:** `production_clinical_schedule.py`,
    `long_horizon_operational_planning.py`, `operational_day_orchestrator.py`,
    `cyclotron_production_windows.py` (physical windows), the Hospital Master
    Calendar / Operational Plan authority.
  - **Doctrine/Status:** batch-production planning **is patient-aware** through the
    Operational Plan / Hospital Master Calendar (patient traces carry `batch_id`;
    the planner groups patient demand into radionuclide-specific batch
    requirements). Propagation chain **Clinical Requirement → Production → Batch →
    Transport → Scanner/Room → Calendar** is preserved. IMPLEMENTED as an
    orchestration layer (delegates to the physical batch/window authorities).

- **Cyclotron patient-awareness boundary.**
  - **Primary Files/Symbols:** `cyclotron_catalog.py`,
    `cyclotron_production_windows.py`
    (`resolve_fleet_eob_capacity_mbq_per_day`), `_resolve_production_gate`
    (Part 3D). The cyclotron authority is **radionuclide-aware and
    physical-batch/window-aware, NOT directly patient-identity-aware** — it
    receives radionuclide / required EOB / production window / equipment identity /
    cycle requirement, never `patient_id` / name / room / scanner assignment.
    IMPLEMENTED (the batch-planning layer translates patient requirements into
    radionuclide-specific physical requirements before they reach the cyclotron).

- **Generator patient-awareness boundary.**
  - **Primary Files/Symbols:** `generator_catalog.py`, `generator.py`
    (`GeneratorAsset.elute`, `.available_tc99m_activity_mbq`),
    `_resolve_radionuclide_production_gate` (Part 3D generator daughter match).
    The generator authority is **source / radionuclide-aware, NOT directly
    patient-identity-aware** — patient awareness stays upstream in the demand /
    batch-planning layer. IMPLEMENTED (Mo-99 → Tc-99m).

- **Cross-cutting doctrine (preserved):** SUPPORTED ≠ CALIBRATED (§2.6, product
  doctrine §10) — a radionuclide may constrain synthetic demand as SUPPORTED while
  its production output is `NOT_CALIBRATED`. PATIENT / ADMINISTRATION COHORT ≠
  PHYSICAL PRODUCTION BATCH (§2.8, product doctrine §11). Unsupported-demand /
  stress-test mode must expose `NO_COMPATIBLE_SOURCE` and never silently mutate
  patient demand (PLANNED; no stress-test engine introduced here).
- **Provenance/Build:** MRT Pharma Authority Consolidation final addendum
  (governance only).

### 2.25 Clinical Radionuclide Portfolio Authority (OG-RAD-1)

- **Canonical Authority:** architecture-neutral clinical radionuclide portfolio —
  "what clinical radionuclide demand is legitimate?"
- **Primary File:** `clinical_radionuclide_portfolio.py`
  (`resolve_clinical_radionuclide_portfolio` →
  `ClinicalRadionuclidePortfolioResult` / `ClinicalRadionuclidePortfolioEntry`,
  `discover_physically_recognized_radionuclides`).
- **Role:** sits conceptually between PHYSICAL SOURCE CAPABILITY and SYNTHETIC
  DEMAND. Discovers the physically-recognized radionuclide universe (**15**) from
  the existing authorities (half-life table ∪ cyclotron `supported_radionuclides`
  ∪ generator daughters/parents) and resolves per radionuclide: decay / clinical
  modality / procedure / selected-source support / production calibration /
  scanner modality compatibility / NORMAL·STRESS·EXPLICIT admissibility. Reuses
  (never duplicates) `diagnostics.load_radionuclide_half_lives`,
  `cyclotron_catalog`, `generator_catalog`, `scanner_catalog` /
  `clinical_resource_identity.ScannerModality`, and the SAME clinical modality
  recognition set as `synthetic_radionuclide_source_capability` (following the
  Clinical Radionuclide Completeness build: PET = F-18/C-11/N-13/O-15/Ga-68/
  Cu-64/Zr-89/I-124; SPECT = Tc-99m/I-123/In-111/Tl-201).
- **Separation preserved:** `PORTFOLIO` (what may be requested) ≠ `DEMAND MIX`
  (how much) ≠ `OPTIMIZER` (Part 3E capital composition). Multi-radionuclide
  weighting is `NOT_MODELED` (no fabricated mix). Never patient-identity-aware.
  No transport/MRT architecture bias (architecture-neutral).
- **Doctrine preserved:** RADIONUCLIDE PHYSICALLY KNOWN ≠ CLINICALLY ADMISSIBLE;
  SUPPORTED ≠ CALIBRATED; CLINICALLY ADMISSIBLE ≠ QUANTITATIVELY CALIBRATED. A
  calibrated F-18 record never qualifies C-11/N-13/O-15/Ga-68/Cu-64/etc. No
  global-catalog fallback; no F-18/Tc-99m substitution; no cross-model borrowing.
- **Counts (physical, after the Clinical Radionuclide Completeness build; NORMAL
  under maximal source control = all compatible cyclotrons + all generators +
  PET/SPECT):** PHYSICALLY_RECOGNIZED = 15, HALF_LIFE_SUPPORTED = 15,
  CLINICALLY_MODALITY_CLASSIFIED = 12, PROCEDURE_AUTHORIZED = 0,
  NORMAL_ADMISSIBLE = 12, SHORT_HALF_LIFE_NORMAL_ADMISSIBLE = 3 (C-11/N-13/O-15).
- **Implementation Status:** IMPLEMENTED (portfolio authority) — procedure
  authority still `NOT_MODELED` for all radionuclides (why OG-RAD-1 stays PARTIAL).
- **Focused test:** `test_clinical_radionuclide_portfolio.py` (52 tests).
  **Doc:** `CLINICAL_RADIONUCLIDE_PORTFOLIO_AUTHORITY.md`.
- **Open-Gap Ref:** OG-RAD-1 = **PARTIAL** (procedure authority still
  `NOT_MODELED`). Reuses OG-SYNTH-1 binding. Following the Clinical Radionuclide
  Completeness & Evidence Closure build the Ge-68/Ga-68 generator pathway is now
  canonical (OG-GEN-1 = `PATHWAY_CLOSED`, economics still `NOT_CALIBRATED`), so
  Ga-68 carries both a cyclotron and a generator pathway; OG-SCN-1 (model-specific
  scanner radionuclide compatibility) remains `NOT_MODELED`.

---

## 3. Provenance — build documents (existing repository docs)

| Document | Scope |
|---|---|
| `CONSTITUTION.md` | V2 product doctrine / engineering specification |
| `CYCLOTRON_PRODUCTION_DATA_AUTHORITY_BUILD_3B.md` | Cyclotron/generator production authority audit |
| `FIVE_MODE_TRANSPORT_AUTHORITY_BUILD_3C.md` | Five transport building blocks |
| `SPATIAL_ROUTE_NETWORK_AUTHORITY_BUILD_3C1.md` | Two-route-family spatial routing |
| `PHYSICAL_FEASIBILITY_AUTHORITY_PART_3D.md` | Unified physical feasibility closure |
| `CLINICAL_RADIONUCLIDE_PORTFOLIO_AUTHORITY.md` | Clinical radionuclide portfolio authority (OG-RAD-1) |
| `FOUR_ARCHITECTURE_BUILD2R_REDERIVATION_REPORT.md` | Four-architecture economic rederivation |
| `four_architecture_economic_report*.md` | Economic baselines |
| `ENGINEERING_IMPLEMENTATION_AUDIT_MILESTONE_ZERO.md` | Milestone-zero audit |
| `ENGINEERING_NOTES.md` / `DEPLOYMENT_CHECKLIST.md` / `README.md` | Engineering notes / deployment / product overview |
| `MRT_PHARMA_AUTHORITY_DOCTRINE.md` | Governance doctrine + three classes of truth (this build) |
| `MRT_PHARMA_PRODUCT_DOCTRINE.md` | Durable product decisions — two products, building blocks, doctrines (this build) |
| `MRT_PHARMA_INTEGRATION_ARCHITECTURE.md` | External-system seam map — ARIA/Bentley/NVIDIA/CAD-BIM/facility/hospital (this build) |
| `MRT_PHARMA_BUILD_LEDGER.md` | Physical git build history 3A→Part 3D + this build (this build) |
| `MRT_PHARMA_OPEN_GAPS.md` | Documented open gaps (this build) |
| `clinical_radionuclide_evidence.json` | Canonical clinical-radionuclide external-evidence registry (raw + normalized, provenance, evidence class) — Completeness build |
| `CLINICAL_RADIONUCLIDE_COMPLETENESS_AUTHORITY.md` | Clinical radionuclide completeness report (14 tables); half-life 7→15, modality 2→12, Ge-68/Ga-68 generator (OG-GEN-1) — Completeness build |
| `test_clinical_radionuclide_completeness.py` | Focused completeness tests (62: 50 invariants + proofs A–I + traceability) |

---

*This index is a governance/traceability artifact. It intentionally introduces
no production-engine behavior. When an authority changes, update the relevant row
here and the corresponding entry in `MRT_PHARMA_OPEN_GAPS.md`.*

---

# September 9 Reconciliation Addendum — Live Bentley / Clinical Program frontend + status re-standardization

**Reconciliation checkpoint:** repository `main`, HEAD
`bdd2103d7e4e189625a6c725bc81e166754df730` (commit *"MRT Pharma: checkpoint BIM
spatial and clinical-program foundation"*), divergence `0 0`. Working tree clean
except the intentionally-unstaged `frontend/.env`.
**Nature:** GOVERNANCE / TRACEABILITY ONLY — reconciles the Aug 29 authority table
(sections 1–2.25 above, HEAD `07e861d`) against the **physical September 4–9
frontend source** now committed. No product-engine or product-UI behavior changed.
Every classification below was verified against the actual `.ts`/`.tsx` source
(and the backend `.py` modules), not from report `.md` files or session memory.

> The Aug 29 sections above remain valid for the **backend Python domains** and
> were re-verified at this checkpoint (see §R.9). This addendum ADDS the frontend
> spatial/clinical layer that did not exist when they were written, and
> re-standardizes status terminology (§R.1). Where a backend row and this addendum
> both describe a concern, this addendum is the September 9 source of truth.

## R.1 Standardized status vocabulary (applies to both authority documents)

To avoid `IMPLEMENTED` overclaiming live integration, the following controlled
vocabulary is used from this checkpoint onward:

| Status | Meaning |
|---|---|
| `IMPLEMENTED_AND_INTEGRATED` | Physically present in code + tests AND wired into a live product surface (the `/viewer` UI, or an executed engine path). |
| `IMPLEMENTED_DOMAIN_AUTHORITY` | Pure domain/engine authority present + unit-tested; consumed by an integration layer but not itself a live UI surface. |
| `IMPLEMENTED_ADAPTER_OR_EXPORT` | An export/presentation/adapter layer (e.g. OpenUSD `.usda` generation, ARIA fixture adapter) — not an engineering authority and not a live runtime. |
| `PARTIAL` | Partially implemented; a specific seam/gap is disclosed. |
| `PLANNED` | Agreed future behavior; no implementation. |
| `NOT_MODELED` | Not represented in the repository at all. |
| `DIAGNOSTIC_ONLY` | Developer/recovery instrument; never a physical authority or product behavior. |
| `SUPERSEDED_OR_FALLBACK` | Kept for lineage/fallback; no longer the primary authority. |
| `MANUAL_ACCEPTANCE_PENDING` | Implemented + offline-verified; awaiting a human live-acceptance step. |

The Aug 29 `IMPLEMENTED` label maps to `IMPLEMENTED_DOMAIN_AUTHORITY` for the
backend engines (they are executed engine paths, not live UI). `CALIBRATED` /
`NOT_CALIBRATED` / `CONTROLLED_BENCHMARK` continue as calibration-evidence
qualifiers orthogonal to the status above.

## R.2 Frontend integration hub

- **Canonical Authority:** `frontend/src/components/spatial/spatialAssetOverlay.ts`
  — the application-owned runtime hub. Owns viewer-mode state, active-product-
  viewport resolution, decorator registration, the Clinical Program runtime, the
  ClinicalPlanningVolume runtime, authoritative-footprint caching, and all
  developer diagnostics. **No Bentley write API is called from this seam.**
- **Live surface:** `frontend/src/routes/BentleyViewer.tsx` (the `/viewer` page)
  + `frontend/src/components/viewer/LiveItwinViewer.tsx` (authenticated Auth-Code
  + PKCE viewer). NORMAL-mode panels (`ProjectBimSelector`, `CameraModeControl`,
  `ClinicalProgramControl`, `ViewerAssetLibrary`) mount unconditionally; DEV-mode
  panels (`AuditDiagnosticsPanel`, `ClinicIngestionPanel`, DEV_TOOLS drawer) are
  gated behind Developer mode.
- **Status (integration hub module):** the `spatialAssetOverlay.ts` hub + `/viewer`
  live surface are wired together and functioning. **Aggregate UI/UX status =
  `PARTIAL`** — `LIVE_BENTLEY_AND_CLINICAL_WORKFLOW_INTEGRATED = YES`;
  `END_TO_END_PRODUCT_WORKFLOW_INTEGRATED = NO` (the deeper engines — optimization,
  operations, economics, What-If/Lockdown, simulation — are not yet joined into one
  coherent customer-facing product workflow). See §R.3 row R and workstream J.
- **Tests:** 35 frontend test files / **619** cases at this checkpoint.

## R.3 Frontend domain authority table (September 4–9)

Schema: **Concern · Canonical file(s) · Key symbols · Test · Status.**

| Concern | Canonical file(s) | Key symbols | Test | Status |
|---|---|---|---|---|
| Project BIM selection + persistence | `lib/projectBim.ts`, `lib/viewerConfig.ts`, `components/spatial/ProjectBimSelector.tsx` | `MEDICAL_CLINIC_DEMO` (clinic `36381ef4-…`), `resolveActiveProjectBim` (URL_OVERRIDE > PERSISTED > PRODUCT_DEFAULT > LEGACY), `ACTIVE_BIM_STORAGE_KEY='mrtpharma.activeProjectBim.v1'`, `isSafePersistedPayload` | `projectBim.test.ts`, `viewerConfigOverride.test.ts` | `IMPLEMENTED_AND_INTEGRATED` |
| Live Medical Clinic Bentley/iTwin viewer + authenticated opening | `components/viewer/LiveItwinViewer.tsx`, `components/spatial/bentleySpatialAdapter.ts`, `routes/BentleyViewer.tsx`, `lib/viewerAuth.ts`, `lib/authCallbackDecision.ts` | `buildSpatialViewState`, `fitLiveModel`, `setPlanningAppearance`, `wireSelection`, `authReducer` | `bentleyViewer.test.tsx`, `authCallbackDecision.test.ts`, `routing.test.tsx` | `IMPLEMENTED_AND_INTEGRATED` |
| Clinic IFC ingestion workflow (real Bentley write) | `components/spatial/bentleyClinicIngestion.ts`, `ClinicIngestionPanel.tsx`, `bentleyPermissionProbe.ts` | `startIngestion`, `preflight`, `checkDemoImodelExists`; pure `classifyBentleyPermissionProbe` | `bentleyPermissionProbe.test.ts` (pure classifier) | `MANUAL_ACCEPTANCE_PENDING` (DEV-gated; the pure permission classifier is `IMPLEMENTED_DOMAIN_AUTHORITY`) |
| Planning / Walkthrough / Bird's-eye / storey cutaway / first-person + collision | pure: `cameraNav.ts`, `walkNav.ts`, `firstPerson.ts`, `planningPlan.ts`, `planningVisuals.ts`, `viewportResolution.ts`, `floatingPanels.ts`; live: `walkthroughController.ts`, `CameraModeControl.tsx`, `RoomPlanDecorator.ts` | `resolveCameraModePolicy`, `resolveWalkCollision`/`slideAlongWall`, `resolveStoreyCutaway`, `resolveFirstPersonOrientation`, `resolveViewportSource`, `resolveFloatingPanelAction`, `applyCameraMode` | `cameraNav.test.ts`, `walkNav.test.ts`, `firstPerson.test.ts`, `planningPlan.test.ts`, `planningVisuals.test.ts`, `floatingPanels.test.ts` | pure seams `IMPLEMENTED_DOMAIN_AUTHORITY`; live controller `IMPLEMENTED_AND_INTEGRATED` (navigation feel `MANUAL_ACCEPTANCE_PENDING`) |
| Clinical Program: taxonomy, BIM-space assignment, MRT naming, persistence, multi-room | `clinicalProgram.ts`, `clinicalProgramAnchor.ts`, `clinicalProgramOverlay.ts`, `clinicalVolumeCollection.ts`, `ClinicalProgramControl.tsx`, `ClinicalProgramDecorator.ts` | `ClinicalFunction`, `assignClinicalFunction`, `resolveProgramRoomLabel`, `checkProgramCompleteness`, key `'mrtpharma.clinicalProgram.v1.'+iModelId`; `deriveClinicalProgramOverlay`; collection ops | `clinicalProgram.test.ts`, `clinicalProgramAnchor.test.ts`, `clinicalProgramOverlay.test.ts`, `clinicalVolumeCollection.test.ts` | `IMPLEMENTED_AND_INTEGRATED` |
| Authoritative IfcSpace geometry + true footprint + true 3D parent room volume | pure: `roomSpatialAuthority.ts`, `authoritativeRoomFootprint.ts`; live: `roomSpatialAuthorityProbe.ts`, `authoritativeRoomGeometryProbe.ts` | `classifyRoomSpatialAuthority` (EXACT_SPACE_GEOMETRY > … > RANGE_ONLY_APPROXIMATION > ANCHOR_ONLY), `deriveAuthoritativeRoomFootprint`, `characterizeAuthoritativeRoomVolume`; live `extractAuthoritativeRoomGeometry` (generateElementMeshes) | `roomSpatialAuthority.test.ts`, `authoritativeRoomFootprint.test.ts`, `authoritativeRoomVolume.test.ts` | footprint/volume math `IMPLEMENTED_DOMAIN_AUTHORITY`; live extraction `IMPLEMENTED_AND_INTEGRATED` (runtime, no unit test by design) |
| True 3D ClinicalPlanningVolume (oriented prism, containment, DRAFT/LOCKED, per-volume visibility, iModel-scoped persistence) | `clinicalPlanningVolume.ts` (+ runtime in `spatialAssetOverlay.ts`) | `buildOrientedPlanningPrism`, `validatePlanningVolumeContainment`/`isPointInsideClosedMesh`, `canLockVolume`, `resolveContainmentStatus` (NOT_EVALUATED≠FAIL), key `'mrtpharma.clinicalVolume.v1.'+iModelId` (FORBIDDEN_KEYS strips mesh/secrets), `seedPrismParamsFromParent` | `clinicalPlanningVolume.test.ts` | `IMPLEMENTED_AND_INTEGRATED` (pure core `IMPLEMENTED_DOMAIN_AUTHORITY`) |
| Build 2A three-room composition (Uptake 01 + Injection Room 01 + PET/CT 01) | `build2aThreeRoomComposition.test.ts`; `seedPrismParamsFromParent`; `suggestPlanningVolumeSeedForParent` (overlay) | new-volume seed from SELECTED parent footprint centroid + Z; deterministic naming | `build2aThreeRoomComposition.test.ts` (11 cases) | multi-room infrastructure `IMPLEMENTED_AND_INTEGRATED` (offline verified); live composition of the two NEW rooms `MANUAL_ACCEPTANCE_PENDING` |
| Uptake 01 reconstruction + persistence diagnostic | `uptake01Reconstruction.ts`; pure `clinicalPersistenceDiagnostic.ts` | `reconstructUptake01Baseline` + `UPTAKE_01_BASELINE` (bimSpaceId `0x200000001f1`); `classifyClinicalPersistenceRegression` | `uptake01Reconstruction.test.ts`, `clinicalPersistenceDiagnostic.test.ts` | reconstruction `DIAGNOSTIC_ONLY`/`TEMPORARY_RECOVERY` (explicit one-time button, duplicate-guarded, never auto-runs); classifier `IMPLEMENTED_DOMAIN_AUTHORITY` |
| Developer diagnostics (BIM content audit, clinical-overlay diagnosis, permission probe, decorator registration) | `bimContentAudit.ts`, `clinicalOverlayDiagnostics.ts`, `decoratorRegistration.ts`, `AuditDiagnosticsPanel.tsx` | live `runBimContentAudit`; pure `classifyClinicalOverlayFailure`, `resolveDecoratorRegistrationAction` | `clinicalOverlayDiagnostics.test.ts`, `decoratorRegistration.test.ts` | `DIAGNOSTIC_ONLY` (pure classifiers `IMPLEMENTED_DOMAIN_AUTHORITY`) |
| **R. UI/UX / Product Integration (aggregate)** | `BentleyViewer.tsx`, `spatialAssetOverlay.ts`, the live `/viewer` panels | live Bentley viewer + Project BIM + Camera/Planning + Clinical Program panels | (component/route tests above) | **`PARTIAL`** — `LIVE_BENTLEY_AND_CLINICAL_WORKFLOW_INTEGRATED = YES`; `END_TO_END_PRODUCT_WORKFLOW_INTEGRATED = NO` (deeper engines not yet joined into one customer-facing workflow) |

## R.4 Spatial representation authority hierarchy (physical clinical planning)

Single canonical chain for **physical clinical planning geometry**:

1. **Parent BIM spatial authority** = authoritative IfcSpace geometry
   (`authoritativeRoomGeometryProbe.extractAuthoritativeRoomGeometry` →
   `authoritativeRoomFootprint.deriveAuthoritativeRoomFootprint` /
   `characterizeAuthoritativeRoomVolume`). Exact room boundary + closed parent mesh.
2. **Application-owned physical planning authority** = `ClinicalPlanningVolume`
   (`clinicalPlanningVolume.ts`) — a true 3D oriented prism, CHILD of the parent
   IfcSpace, contained by the parent mesh (`validatePlanningVolumeContainment`).
3. **Range / bbox** = `DIAGNOSTIC_ONLY` fallback metadata (`BIM_RANGE_APPROXIMATION`)
   used only where exact geometry is not extractable; `roomSpatialAuthority.ts`
   ranks it below exact geometry.
4. **Labels** = view annotations only (billboard text); never physical authority.
5. **Screen space** = NEVER physical authority (`SCREEN_SPACE_AUTHORITY = NO`,
   asserted by the planning-volume diagnostic).

**SUPERSEDED_OR_FALLBACK inventory (kept, not deleted):** range-derived clinical
room rectangles / `BIM_RANGE_APPROXIMATION` anchors (superseded by authoritative
IfcSpace geometry where extractable); legacy 2D overlay-only representations
(superseded by the true-3D decorator); `RoomPlanDecorator` derived room-plan
(view-only planning context, not physical authority).

## R.5 Bentley / BIM reconciliation (supersedes the pessimistic seam language)

The Aug 29 backend row §2.17 (`OG-BEN-1 PARTIAL`, "no automated live connection
exercised") described the **Python** client scaffold. The September 4–9 **frontend**
now provides a genuinely different, live capability, verified in source:

- **Real Medical Clinic iModel registration:** `projectBim.MEDICAL_CLINIC_DEMO`
  (`36381ef4-b5f5-4d6d-b64b-2dbd69ba26a4`, role `PRODUCT_DEMO_BIM`), distinct from
  the `ENGINEERING_REGRESSION_FIXTURE` (`ea9c0558-…`). Roles are separated in code.
- **Authenticated viewer opening:** `LiveItwinViewer.tsx` (Auth-Code + PKCE, no
  client secret) opens the live clinic iModel in the browser.
- **Persistent Project BIM selection:** `mrtpharma.activeProjectBim.v1` localStorage,
  with the invalid-persisted guard and secret-stripping payload.
- **Authoritative IfcSpace extraction:** `extractAuthoritativeRoomGeometry` calls
  `generateElementMeshes` and yields exact footprint + closed parent mesh (Uptake
  01 verified: 186 vertices / 368 triangles / closed / 1 component).
- **IFC ingestion workflow:** `bentleyClinicIngestion.ts` exists as a real
  (DEV-gated) upload/poll workflow — `MANUAL_ACCEPTANCE_PENDING`.

**Reconciled Bentley classification:** the **live viewer + Project BIM + IfcSpace
geometry read path** is `IMPLEMENTED_AND_INTEGRATED`. What remains open is narrow:
(a) automated/credentialed CI exercise of the live connection, and (b) generic
arbitrary-BIM ingestion into the **backend engineering object model** (still the
Python OG-BEN-1 / OG-FIN-1 seam — geometry read in the viewer is NOT the same as
parsing arbitrary IFC/Revit into the engineering model). See OG-BEN-1 (reworded)
and the new OG-FE-* gaps.

## R.6 Clinical Program September 9 state (accurate, non-conflating)

- **Uptake 01** = accepted regression baseline (bimSpaceId `0x200000001f1`,
  '1AC1 CENTRAL WAITING' → "Uptake 01", UPTAKE_ROOM; DRAFT true-3D volume;
  containment INSIDE). Authorized reconstruction available as an explicit
  duplicate-guarded recovery button only.
- **Build 2A multi-room composition infrastructure** = `IMPLEMENTED_AND_INTEGRATED`
  + offline-verified (619 tests). Deterministic naming yields "Injection Room 01"
  and "PET/CT 01"; new volumes seed from the SELECTED parent's own footprint.
- **Injection Room 01 + PET/CT 01 LIVE composition** = `MANUAL_ACCEPTANCE_PENDING`
  — the user selects the parent BIM rooms and defines the volumes; no rooms are
  auto-selected (`AUTO_SELECTED_NEW_PARENT_ROOMS = 0`).
- **Full PET department (incl. Radiopharmacy + support spaces)** = NOT complete
  (deferred). `CLINICAL_PROGRAM_FULL_PET_DEPARTMENT_COMPLETE = NO`.

## R.7 Canonical authority owner review (one owner per concept)

| Concept | Canonical owner |
|---|---|
| BIM physical room geometry | authoritative IfcSpace geometry (`authoritativeRoomGeometryProbe` + `authoritativeRoomFootprint`) |
| Clinical planning geometry | `ClinicalPlanningVolume` (`clinicalPlanningVolume.ts`) |
| Clinical assignment | `ClinicalProgramAssignment` (`clinicalProgram.ts`) |
| Active project BIM identity | `resolveActiveProjectBim` (`projectBim.ts`) |
| Transport eligibility | `transport_mode_eligibility_authority.py` (backend) |
| Scenario baseline | `CanonicalLockdownRecord` (`lockdown_what_if_lineage_authority.py`) |
| What-If branch | `CanonicalWhatIfRecord` (`lockdown_what_if_lineage_authority.py`) |
| OpenUSD | presentation/export adapter (`openusd_spatial_adapter.py`) — NOT an engineering authority |

**DUPLICATE_AUTHORITY_CANDIDATE (for later architecture consolidation, do NOT
refactor now):**
- *Room geometry (frontend):* `roomSpatialAuthority` classification vs
  `authoritativeRoomFootprint` derivation vs `RoomPlanDecorator` range-derived
  plan — clear precedence exists (exact > range), but three modules touch "room
  geometry"; flag for consolidation.
- *Clinical volume:* frontend `ClinicalPlanningVolume` (application-owned physical
  planning) vs backend `interactive_spatial_authoring.py` (engineering authoring)
  — different products/coordinate authorities today; watch for overlap if the
  frontend planning volume ever feeds the backend engineering model.
- *Route/network:* `canonical_spatial_authority.py` vs
  `canonical_geometry_shadow_routing_authority.py` vs `human_circulation_authority.py`
  — layered, but multiple "routing" owners; the live-geometry→route seam is the
  real gap (OG-ROUTE-INT, below), not a second engine.
- *Simulation state:* `digital_twin_simulation_state.py` vs
  `dynamic_scene_state_authority.py` vs `operational_day_trajectory_scene.py` —
  distinct roles (state vs presentation-bridge vs scene), flagged to keep distinct.

## R.8 OpenUSD ≠ NVIDIA, Simulation ≠ Trajectory ≠ Animation (re-verified at this checkpoint)

- `OPENUSD_EXPORT_STATUS = IMPLEMENTED_ADAPTER_OR_EXPORT` — `openusd_spatial_adapter.py`,
  `openusd_yc_demo_binding.py`, `generate_openusd_hospital_visual_demo.py`,
  `generate_openusd_hospital_dynamic_foundation_demo.py` generate real Pixar
  `usd-core` `.usda/.usd`. **Zero `omni` imports** (verified by grep at this
  checkpoint).
- `NVIDIA_OMNIVERSE_RUNTIME_STATUS = PLANNED` — no Kit/Nucleus/live-USD/RTX/Isaac
  runtime. OG-USD-1.
- `SIMULATION_ENGINE_STATUS = IMPLEMENTED_DOMAIN_AUTHORITY` —
  `existing_facility_baseline_simulation.py`, `live_operational_state.py`,
  `operational_day_*`.
- `TRAJECTORY_GENERATION = IMPLEMENTED_DOMAIN_AUTHORITY` —
  `production_trajectory_authority.py` + `operational_day_trajectory_scene.py`
  (RP-PTS sampler still PARTIAL, OG-TRN-2).
- `INTERACTIVE_ANIMATED_RUNTIME = PLANNED` — no interactive patient/carrier
  playback runtime (OG-SIM-1, `LOCKED_PRODUCT_DOCTRINE`).

## R.9 Backend re-verification at HEAD `bdd2103`

Spot-checked in source at this checkpoint (unchanged from Aug 29, still accurate):
What-If/Lockdown domain authority present (`CanonicalLockdownRecord`,
`CanonicalWhatIfRecord`, `promote_what_if_to_lockdown` in
`lockdown_what_if_lineage_authority.py`); the four-architecture engine + equal-budget
search present with **no** free-composition optimizer module (OG-CAP-2 still
PLANNED); trajectory/simulation/dynamic-scene modules present; OpenUSD adapters
present with zero `omni` imports. The Aug 29 backend rows (§§2.1–2.25) are carried
forward unchanged.

## R.10 Revised finish-line master workstreams (source-reconciled)

Ordered, with dependency + demo-criticality (detail in `MRT_PHARMA_OPEN_GAPS.md`):

- **A. Authority consolidation** — THIS TASK (`COMPLETE` at this checkpoint).
- **B. Complete Clinical Program + Equipment Composition** — finish Build 2B (live
  Injection Room 01 + PET/CT 01), then Radiopharmacy/support; bind equipment to
  `ClinicalPlanningVolume` + live room identity. *DEMO_CRITICAL.*
- **C. Bentley geometry → existing canonical spatial/transport integration** — feed
  live IfcSpace geometry into the backend routing authority (OG-ROUTE-INT). Not
  "build routing"; the engine exists. *DEMO_CRITICAL (partial slice).*
- **D. Candidate Facility Composition Optimizer** — OG-CAP-2. *POST_DEMO_IMPORTANT.*
- **E. Unified Operations Execution** — OG-OPS-1 long-horizon→one-day seam.
  *POST_DEMO_IMPORTANT.*
- **F. Interactive Simulation / Animation Runtime** — OG-SIM-1 (trajectory exists;
  playback does not). *POST_DEMO_IMPORTANT.*
- **G. NVIDIA Omniverse Runtime** — OG-USD-1 (OpenUSD export exists). *OPTIONAL_FUTURE
  for first demo.*
- **H. Candidate Economics + Calibration Closure** — OG-CYC-1 / OG-SCN-1 /
  OG-OPEX-1 / OG-GEN-1 economics. *COMMERCIAL_CALIBRATION.*
- **I. Product Workflow + What-If/Lockdown Integration** — domain authority exists;
  live product/UI orchestration is the gap (OG-WIF-UI). *POST_DEMO_IMPORTANT.*
- **J. UI/UX + Reporting + End-to-End Demo** — coherent customer-facing report/export
  + end-to-end Medical Clinic (+ optional NVIDIA) demonstration. *DEMO_CRITICAL (UI
  polish) / POST_DEMO (reporting productization).*

**Dependency order:** A → (B, C can proceed in parallel) → D/E/I → F/G → J; H
(calibration) proceeds in parallel and gates only commercial completeness, never
the first demo. B and the demo slice of C + J are the first-demo critical path.

**This addendum, together with the September 9 section of `MRT_PHARMA_OPEN_GAPS.md`,
is the CURRENT repository authority/gap source of truth as of HEAD `bdd2103`.**
Historical build reports remain provenance and are not retroactively rewritten.

---

# Build 1A Completion Addendum — Generic Spatial Planning Foundation (COMPLETE)

**Checkpoint:** Build 1A manual completion gate PASSED (user-confirmed) on the
working tree following the Build 1A → 1A.4 + Walkthrough-correction chain.
**Nature:** GOVERNANCE update recording the completed Build 1A product authority.
Historical sections above are unchanged; standardized status vocabulary (§R.1) is
preserved. This does NOT mark equipment binding, routing integration, or the full
PET department complete.

## B1A.1 Build 1A authority (frontend clinical spatial planning) — status

| Concern | Canonical source | Status |
|---|---|---|
| Generic BIM room discovery (iModel-scoped) | `bimRoomVolumeRegistry.ts` (`discoverRoomVolumes`) + `spatialAssetOverlay.ts` (`getDiscoveredRoomVolumes`), from `cachedModelSemantics.rooms` | `IMPLEMENTED_AND_INTEGRATED` |
| Room-discovery lifecycle (NOT_BOUND/LOADING/READY/ERROR, iModel-owned, stale-guard) | `roomDiscoveryLifecycle.ts` + guarded `refreshModelSemantics` | `IMPLEMENTED_AND_INTEGRATED` |
| Storey-aware room collection (canonical storey filter) | `bimRoomVolumeRegistry.filterDiscoveredRoomsByStorey` + `getDiscoveredRoomOptions` | `IMPLEMENTED_AND_INTEGRATED` |
| Lazy exact IfcSpace geometry inspection | `authoritativeRoomGeometryProbe.extractAuthoritativeRoomGeometry` (generateElementMeshes) via on-demand `ensureAuthoritativeRoomFootprint` + generic diagnostics | `IMPLEMENTED_AND_INTEGRATED` |
| User-controlled clinical room activation | `clinicalProgram.assignClinicalFunction` (USER authority; no auto-assignment) | `IMPLEMENTED_AND_INTEGRATED` |
| Parent-derived ClinicalPlanningVolume seed | `clinicalPlanningVolume.seedPrismParamsFromParent` + overlay `suggestPlanningVolumeSeedForParent` | `IMPLEMENTED_AND_INTEGRATED` |
| True-3D editable ClinicalPlanningVolume | `clinicalPlanningVolume.ts` (oriented prism, X/Y/W/D/Zlo/Zhi/yaw) | `IMPLEMENTED_AND_INTEGRATED` |
| Exact-parent 3D containment | `validatePlanningVolumeContainment` + `getClinicalVolumeContainment` (EXACT_BIM_SPACE geometry when available; range-only labeled approximate) | `IMPLEMENTED_AND_INTEGRATED` |
| Product-facing containment validation (warning, invalid cue, lock reason, Restore Valid Position, Reset to Parent-Derived, last-known-valid, summary) | `resolvePlanningVolumeValidation` + overlay `restoreValidPosition`/`resetToParentDerived` + `ClinicalProgramControl` + `ClinicalProgramDecorator` | `IMPLEMENTED_AND_INTEGRATED` |
| Multi-room planning foundation (per-room edit/visibility/lifecycle/containment isolation; iModel isolation; persistence) | `clinicalVolumeCollection.ts` + iModel-scoped persistence keys | `IMPLEMENTED_AND_INTEGRATED` |
| Walkthrough facility navigation (floor-constrained pedestrian forward/back/strafe/turn, wall collision + door pass, floor-clearance, incremental zoom/FOV, label visibility, trackpad look) | `walkNav.ts`, `firstPerson.ts`, `walkthroughController.ts`, `walkthroughLabelVisibility.ts` | `IMPLEMENTED_AND_INTEGRATED` |

**BUILD_1A_STATUS = COMPLETE** (manual acceptance gate PASSED; offline: 51 test
files / 815 tests / 0 regressions; production build PASS; core-frontend 5.12.5).

## B1A.2 Explicit remaining limits (NOT complete at Build 1A closure)

`FULL_PET_DEPARTMENT_COMPLETE = NO`; `CANONICAL_EQUIPMENT_BINDING_COMPLETE = NO`;
`AUTOMATIC_SPATIAL_ROUTING_COMPLETE = NO`; `FREE_COMPOSITION_OPTIMIZER_COMPLETE =
NO`; `ANIMATED_SIMULATION_RUNTIME_COMPLETE = NO`; `ECONOMICS_INTEGRATION_COMPLETE
= NO`; `WHAT_IF_UI_COMPLETE = NO`; `NVIDIA_RUNTIME_COMPLETE = NO`;
`TRUE_STOREY_SPATIAL_ISOLATION_COMPLETE = NO`; `EXPLODED_STOREY_VIEW_COMPLETE = NO`.

## B1A.3 Next builds (recorded; not started)

- `BUILD_1B_COMPLETE_CLINICAL_PROGRAM_AND_CANONICAL_EQUIPMENT_BINDING` — complete
  the PET/nuclear-medicine clinical program and bind ONLY existing canonical
  equipment/resources (cyclotron, radionuclide generators, imaging equipment, MRT
  vestibule/endpoints, other currently-canonical resources — verified source-first;
  no new equipment classes) to the true-3D clinical spaces, with room-parented,
  movable/rotatable, floor-aware, envelope-contained, warn-on-invalid,
  lock-blocked-when-invalid, Restore/Reset, iModel-scoped placement crosswalked to
  existing capacity/production/cost authority.
- `BUILD_2_AUTOMATIC_FACILITY_CONNECTIVITY_AND_SPATIAL_TRANSPORT_INTEGRATION` —
  doctrine: SIMULATE → infer required logistics missions → determine eligible
  transport modes → auto-generate feasible spatial connections/routes → evaluate.
  Normal simulation must NOT require the user to manually choose every MRT/PTS
  connection; manual route/mode forcing belongs to future What-If/engineering
  override.


---

## PRE-AWS ENGINEERING AUTHORITY RECONCILIATION (Correction Build)

**Nature:** CONTROLLED CORRECTION BUILD. Not an AWS implementation, not a
Streamlit migration, not Build 1C/2, not a UI redesign, not a refactor. It
corrects four proven engineering-authority defects found by the final pre-AWS
audit, strengthens repository-wide regression protection, and synchronizes the
affected engineering documentation. This section updates the canonical index in
place (per the maintenance protocol) rather than creating a parallel "FINAL"
authority document — the objective is ONE CURRENT ENGINEERING STORY.

### A. Four-quantity production invariant (updates §2.4, §2.6, §2.9)

The following four quantities are **distinct** and must never be conflated on any
authoritative current path:

1. **patient count** (a clinical/administration cohort quantity),
2. **radioactive activity** (MBq — administered → release → EOB-required),
3. **physical production capacity** (installed EOB MBq/day),
4. **production batch/cycle count**.

Dose counts are NOT physical MBq capacity. Production-block percentages are NOT
physical MBq capacity. The authoritative physical chain is:

> PATIENT REQUIREMENT → ADMINISTERED ACTIVITY → RELEASE ACTIVITY → DECAY/PROCESS
> LOSSES → EOB-REQUIRED ACTIVITY → PHYSICAL EOB CAPACITY → PRODUCTION WINDOWS/
> CYCLES → CLINICAL ADMINISTRATION.

**Repository-wide production invariant (regression-locked):** no authoritative
current production-feasibility, optimization, ranking, capacity or CapEx path may
derive physical radioactive-production capacity from `current_usable_doses_per_day`,
`production_blocks`, a `10%`/`0.10` production-block expression, or any equivalent
synthetic capacity expression. Enforced by:

- **STATIC GUARD:** `test_production_capacity_invariant_guard.py` — inspects the
  executable source (comments/strings stripped) of `equal_budget.py`,
  `optimization.py`, `cyclotron_production_estimation_authority.py`,
  `cycle_relative_production_requirement.py`, `operational_day_orchestrator.py`.
- **BEHAVIORAL REGRESSIONS:** `test_production_capacity_behavioral_closure.py` —
  exercises the real Capital Project / equal-budget / optimization / production-
  chain entry points.

### B. Explicit / calibrated EOB capacity behavior (updates §2.1, §2.6)

When an explicit/calibrated physical EOB capacity exists
(`PlannerInputs.current_cyclotron_eob_capacity_mbq_per_day`,
`PlannerAssumptions.cyclotron_eob_capacity_mbq_per_day`, or a calibrated
`CyclotronFleet`), the engine uses **exactly** that installed physical capacity.
Physical feasibility is `A_EOB_required <= A_EOB_installed`. Calibrated capacity
is **never** inflated by 10% dose-count "production blocks". The former
`equal_budget._cyclotron_eob_capacity_mbq_per_day(..., production_block_multiplier)`
helper (which multiplied a calibrated base by `1 + blocks*0.1`) is **REMOVED**.

### C. NOT_CALIBRATED production behavior (updates §2.1, §2.6, §2.9)

When physical EOB capacity is NOT calibrated, status stays `NOT_CALIBRATED`. The
engine still computes and reports `A_EOB_required`, but it does NOT fabricate
`A_EOB_installed`, impose a synthetic dose-count ceiling, convert dose count into
MBq capacity, create synthetic production blocks / 10% upgrades, fabricate
production-upgrade CapEx, or report calibrated physical feasibility. In the
`equal_budget` batch-cohort engine, uncalibrated production is treated as
**non-limiting** (throughput bounded only by physical clinical resources +
unavoidable intra-day decay), which is an operating outcome under unknown
production — not a physical-capacity claim. Unknown capacity remains unknown.

### D. Removal of the legacy dose-count/10%-block fallback (updates §2.1)

The prohibited `current_usable_doses_per_day * (1 + production_blocks * 0.10)`
model has been removed from the authoritative Capital Project paths that still
carried it: `equal_budget._build_mrt_economic_candidate`,
`equal_budget._mrt_production_block_bound` (now always returns 0),
`equal_budget._enumerate_mrt_candidates`, the `equal_budget` decision-summary
reporting path, and `optimization.conventional` / `optimization.mrt` (which had no
calibration gate at all). `PlannerAssumptions.production_expansion_capex_per_10pct`
is retained ONLY as a backward-compatibility field; it is charged $0 and does not
affect capacity/feasibility/ranking/CapEx when production is uncalibrated
(NONAUTHORITATIVE_COMPATIBILITY). `_conventional_baseline_capacity` still uses
`current_usable_doses_per_day` strictly as an OBSERVED CURRENT throughput baseline
reference (no block inflation, never a forward physical-capacity claim).

### E. Physical carrier-concurrency authority (updates §2.11, §2.12)

`shared_mrt_multistream_authority.compute_physical_carrier_peak_concurrency` is the
single canonical physical carrier-availability authority. A carrier is unavailable
for its full physical occupation cycle — loaded-outbound leg PLUS empty-return/
recovery leg — modeled as `duration * (1 + PHYSICAL_CARRIER_RETURN_LEG_MULTIPLIER)`.
The new module constant `PHYSICAL_CARRIER_RETURN_LEG_MULTIPLIER = 1.0` (a disclosed
symmetric-transit assumption, not a measured value) is the SINGLE shared value used
by BOTH fleet sizing (`compute_heterogeneous_shared_carrier_fleet`) and the
carrier-shortage evaluator, so the two can never diverge into independent
approximations.

### F. Carrier-shortage evaluation now uses the canonical occupancy doctrine (updates §2.1, §2.11)

`whole_oncology_four_architecture_optimization.evaluate_mrt_dominant_operational_only_carrier_shortage`
previously bucketed missions round-robin and scheduled each carrier on a
zero-length segment with a ~1-minute headway, which silently omitted the carrier
turnaround/return occupancy (a `MISSING_CONSTRAINT`) and bypassed the canonical
concurrency authority. It is corrected to a multi-server queue in which each
mission occupies a carrier for the full physical cycle. `CarrierShortageOutcome`
now reports `physical_peak_carrier_concurrency`. **Corrected physical fleet
requirement for the common project baseline:** 212 missions, physical peak carrier
concurrency = **9**. A fleet below 9 incurs queuing wait (7 carriers clears the
late/unmet service thresholds but is below the physical peak and still queues,
max wait ≈ 4.56 min); a fleet of 9 has zero carrier-induced queuing. The prior
"7 carriers → all on-time, zero wait" benchmark was an artifact of the omitted
return occupancy. Regression-locked by `test_carrier_shortage_physical_occupancy.py`
and updated cases in `test_full_operational_capital_qualification.py` /
`test_whole_oncology_four_architecture_optimization.py`.

### G. Current generator catalog = 4 models (updates §2.10)

The authoritative generator catalog contains **four** models: three Mo-99 → Tc-99m
(`CURIUM_TECHNELITE`, `CURIUM_ULTRA_TECHNEKOW_FM`, `GE_HEALTHCARE_DRYTEC`) and one
Ge-68 → Ga-68 (`ECKERT_ZIEGLER_GALLIAPHARM`). The stale "3 initial models"
benchmark was updated (renamed to
`test_generator_benchmark_uniform_across_current_catalog_models`, asserts 4). The
fourth generator was NOT removed and the catalog was NOT modified to satisfy the
old count.

**Generator delivery-cost economic-assumption review:** the `$3,500`
`CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_USD` is an explicitly **Tc-99m-SPECIFIC**
controlled assumption. It is applied as a clean controlled assumption ONLY to
Tc-99m generators. For the Ge-68/Ga-68 GalliaPharm (which has no calibrated
delivery cost) the same numeric placeholder is reused with a distinct, honest
basis `CONTROLLED_TC99M_ASSUMPTION_INHERITED_NOT_GENERATOR_SPECIFIC` — no
GalliaPharm-specific price is fabricated; provenance / `NOT_CALIBRATED` semantics
are preserved.

### H. Product/UI/platform doctrine (reaffirms §2.18, §2.19; LOCKED_PRODUCT_DOCTRINE)

- **React/TypeScript = the sole customer-facing commercial MRT Pharma UI.**
- **Streamlit = legacy/internal engineering and validation harness only.**
  Commercially relevant Streamlit-only capabilities remain
  `MIGRATION_REQUIRED_TO_REACT` (later in the Build-to-Finish program).
- **AWS application infrastructure = `PROPOSED_NOT_IMPLEMENTED`** at this
  checkpoint (no Aurora/S3-app/SQS/Fargate/Cognito/CloudFront/ECR/API Gateway/
  Bedrock/SageMaker/CDK/Terraform/CloudFormation). NVIDIA runtime likewise remains
  `PROPOSED_NOT_IMPLEMENTED` (OpenUSD file export only; no Omniverse/Kit/nucleus).
- **GitHub remains the source-code authority.**
- **Bentley / iModel remains the geometry authority.**

### Deferred (recorded as PRE_AWS_SCHEMA_REQUIREMENT — NOT implemented here)

- **Catalog version pinning** — `PRE_AWS_SCHEMA_REQUIREMENT`. The future persistent
  data architecture must allow historical LOCKDOWN states to identify the exact
  canonical catalog version used for physics/capacity/production/performance/
  economics. Not bolted onto today's in-memory architecture.
- **Transport persisted vocabulary** — `PRE_AWS_SCHEMA_REQUIREMENT /
  DESIGN_DECISION_REQUIRED`. Target persisted business taxonomy:
  `MANUAL | PTS | RTHS | AGV_AMR | MRT` with explicit configuration/subtype
  underneath (PTS qualification explicit; AGV/AMR light/heavy configuration
  explicit; RTHS distinct from floor AGV/AMR; MRT distinct). No broad enum
  refactoring performed in this correction.

### EVI / frontend (unchanged in this correction)

EVI interaction behavior is unchanged. `manual_acceptance = PENDING`; the
viewport-darkening issue remains `DIAGNOSTIC_ONLY / MANUAL_ACCEPTANCE_PENDING`
until live verification proves otherwise (not closed on automated tests).

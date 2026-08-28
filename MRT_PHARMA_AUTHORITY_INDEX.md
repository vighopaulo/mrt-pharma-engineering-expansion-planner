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

### 2.9 Future Cyclotron Production Estimation Authority

- **Authority Type:** C (PLANNED_REQUIREMENT). **Implementation Status:**
  PLANNED — **does not exist in the repository.**
- **Intended future role:** numerical engineering estimates for a
  model × radionuclide combination that is SUPPORTED but whose manufacturer/site
  output is NOT_CALIBRATED. Future evidence hierarchy: `SITE_CALIBRATED` >
  `MANUFACTURER_CALIBRATED` > `MODELED_ESTIMATE` > `CONTROLLED_ASSUMPTION` >
  `NOT_AVAILABLE`. Today, SUPPORTED-but-uncalibrated returns NOT_CALIBRATED;
  there is no `MODELED_ESTIMATE` authority. **Do NOT mark MODELED_ESTIMATE as
  implemented.**
- **Open-Gap Ref:** OG-CYC-1.

### 2.10 Generator authority

- **Canonical Authority:** Generator catalog + Bateman physics.
- **Primary Files:** `generator_catalog.py`, `generator_equipment_catalog.json`,
  `generator.py`, `generator_economics.py`.
- **Primary Symbols:** `GeneratorCatalogModel`, `load_generator_catalog`,
  `GeneratorAsset.available_tc99m_activity_mbq` / `.elute()`, `PreparationBatch`.
- **Primary Tests:** `test_pet_spect_generator_native_authority_completion.py`,
  `test_build3b_production_authority.py`.
- **Authority Type:** B. **Implementation Status:** IMPLEMENTED (Mo-99 → Tc-99m).
  **Calibration Status:** physics `literature_calibrated`; all economics
  `NOT_CALIBRATED`.
- **Models:** `CURIUM_TECHNELITE`, `CURIUM_ULTRA_TECHNEKOW_FM`,
  `GE_HEALTHCARE_DRYTEC` (all Mo-99 → Tc-99m, elution 0.85, 2 elutions/day,
  14-day life).
- **Known Limitations:** **Ge-68/Ga-68 generator = NOT_MODELED / ABSENT.** Ge-68
  and Ga-68 appear only as cyclotron-produced isotopes, never as a generator
  parent/daughter. See OG-GEN-1.

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

### 2.24 Patient / batch / production-equipment awareness boundary

Governance navigation for the synthetic-patient → batch-planning →
cyclotron/generator authority layering (product doctrine: `MRT_PHARMA_PRODUCT_DOCTRINE.md`
§11A). Directional chain (§2.4) is preserved; this row adds the **patient-awareness
boundary** at each layer.

- **Synthetic patient radionuclide generation.**
  - **Primary Files:** `oncology_pet_spect_scenario.py`
    (`build_representative_day_population`, `build_stochastic_representative_day_population`,
    constants `PET_RADIONUCLIDE = "F-18"` / `SPECT_RADIONUCLIDE = "Tc-99m"`),
    `patient_radionuclide_demand.py` (`PatientRadionuclideDemand`),
    `inbound_patient_program.py` (`generate_synthetic_patient_population`).
  - **Doctrine:** the synthetic generator should constrain demanded radionuclides
    to the **combined selected production-source capability set** (cyclotron
    supported radionuclides ∪ generator supported radionuclides), not invent
    demand independently of the scenario's production configuration.
  - **Authority Type:** C (PLANNED_REQUIREMENT) for the constraint itself.
  - **Implementation Status:** **PLANNED / PARTIAL.** Today the radionuclide is
    assigned purely by modality (PET → F-18, SPECT → Tc-99m), and
    `PatientRadionuclideDemand` validates only against the canonical half-life /
    decay table (`load_radionuclide_half_lives`), **not** against any selected
    cyclotron/generator capability. There is **no** code path where changing the
    selected production source changes which radionuclides synthetic patients
    demand; a capability mismatch is surfaced only **downstream** at the
    feasibility stage. This is consistent with the test-locked "demand is
    upstream" doctrine (§2.3). **Do NOT describe this constraint as implemented.**
  - **Open-Gap Ref:** OG-SYNTH-1.

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

---

## 3. Provenance — build documents (existing repository docs)

| Document | Scope |
|---|---|
| `CONSTITUTION.md` | V2 product doctrine / engineering specification |
| `CYCLOTRON_PRODUCTION_DATA_AUTHORITY_BUILD_3B.md` | Cyclotron/generator production authority audit |
| `FIVE_MODE_TRANSPORT_AUTHORITY_BUILD_3C.md` | Five transport building blocks |
| `SPATIAL_ROUTE_NETWORK_AUTHORITY_BUILD_3C1.md` | Two-route-family spatial routing |
| `PHYSICAL_FEASIBILITY_AUTHORITY_PART_3D.md` | Unified physical feasibility closure |
| `FOUR_ARCHITECTURE_BUILD2R_REDERIVATION_REPORT.md` | Four-architecture economic rederivation |
| `four_architecture_economic_report*.md` | Economic baselines |
| `ENGINEERING_IMPLEMENTATION_AUDIT_MILESTONE_ZERO.md` | Milestone-zero audit |
| `ENGINEERING_NOTES.md` / `DEPLOYMENT_CHECKLIST.md` / `README.md` | Engineering notes / deployment / product overview |
| `MRT_PHARMA_AUTHORITY_DOCTRINE.md` | Governance doctrine + three classes of truth (this build) |
| `MRT_PHARMA_PRODUCT_DOCTRINE.md` | Durable product decisions — two products, building blocks, doctrines (this build) |
| `MRT_PHARMA_INTEGRATION_ARCHITECTURE.md` | External-system seam map — ARIA/Bentley/NVIDIA/CAD-BIM/facility/hospital (this build) |
| `MRT_PHARMA_BUILD_LEDGER.md` | Physical git build history 3A→Part 3D + this build (this build) |
| `MRT_PHARMA_OPEN_GAPS.md` | Documented open gaps (this build) |

---

*This index is a governance/traceability artifact. It intentionally introduces
no production-engine behavior. When an authority changes, update the relevant row
here and the corresponding entry in `MRT_PHARMA_OPEN_GAPS.md`.*

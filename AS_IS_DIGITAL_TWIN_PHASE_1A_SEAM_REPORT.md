# EXISTING FACILITY / AS-IS DIGITAL TWIN — PHASE 1A PHYSICAL SEAM REPORT

**Task type:** Authority-first repository investigation. READ-ONLY. No implementation, no new
types, no file modifications, no staging, no commit, no push.

**Purpose:** Determine exactly how the *physical* repository already represents projects,
geometry, engineering objects, rooms, routes, clinical operations, provenance, calibration,
baseline/operational state, and scenario/version state — so the future AS-IS Twin *extends*
those authorities instead of creating a parallel architecture. This report is the input to the
subsequent implementation prompt.

> Governing principle honored: the PHYSICAL repository is authoritative. Every claim below was
> verified by reading the actual source at HEAD, not from session memory or product-doctrine
> documents. Where a concept exists only as documentation, a Literal value, a proof model, or a
> test fixture, that distinction is stated explicitly.

---

## 0. MANDATORY PHYSICAL PRECHECK (Sec 1)

```
STARTING_HEAD              = 2f22bf3fae5f0636771b44d4f26ea3e74e248f6f
STARTING_BRANCH            = main
ORIGIN_MAIN                = 2f22bf3fae5f0636771b44d4f26ea3e74e248f6f
STARTING_DIVERGENCE        = 0 / 0  (local main == origin/main)
WORKING_TREE_CLEAN         = YES
STAGED_FILES               = (none)
UNSTAGED_FILES             = (none)
UNTRACKED_FILES            = (none)
PART3D_PRESENT_IN_HISTORY  = YES   (07e861d "Part 3D: establish unified physical feasibility authority")
PART3E_PRESENT_IN_HISTORY  = YES   (a6facf9 "Part 3E: establish radionuclide-aware architecture optimization")
PART3E_1_PRESENT_IN_HISTORY= YES   (93bf687 "Part 3E.1: controlled radionuclide architecture experiment campaign")
PART3E_2_PRESENT_IN_HISTORY= YES   (2f22bf3 "Part 3E.2: decision envelope, crossover & decision-critical calibration analysis" == HEAD)
UNRELATED_FILES_PRESENT    = NO
READY_FOR_ASIS_AUTHORITY_TRACE = YES
```

The checkpoint matches the expected starting authority exactly (Part 3E.2 committed and pushed,
`2f22bf3`). No reset/revert/checkout was needed or performed.

---

## 1. PRODUCT-STATE (Sec 3) — how the repo represents project type / lifecycle / intent

**There is NO single canonical project-state type.** The concept is split across several
independently-defined string `Literal` aliases (the only real `Enum` is `models.Architecture`,
which is a *transport* axis, not lifecycle). Three genuinely distinct axes exist:

| Axis | Type & location | Values | What it MEANS | Consumers |
|---|---|---|---|---|
| **Lifecycle / facility physical state** | `DevelopmentContext = Literal["RETROFIT","GREENFIELD"]` — `whole_oncology_four_architecture_optimization.py:138` (re-declared verbatim `mrt_auxiliary_systems_authority.py:1250`) | RETROFIT, GREENFIELD | **CapEx-attribution binary.** RETROFIT ⇒ common assets are existing/sunk (`common_new_study_capex=0.0`, `EXISTING_RETAINED_COMMON_ASSET`); GREENFIELD ⇒ charged as new (`COMMON_NEW_PROJECT_ASSET`). | `compute_common_project_capex(...)` (`~L541`, only place it changes an output); every architecture evaluator; `StudyConfiguration.development_context`; `ArchitectureResult.development_context`; `compute_retrofit_to_greenfield_transition_impact()` (`~L3456`, the sole lifecycle-transition helper); `mrt_auxiliary_systems_authority.evaluate_auxiliary_provisioning`; `canonical_spatial_authority.transform_registry_for_context` (GREENFIELD ⇒ all PROPOSED, else per-object EXISTING/PROPOSED) |
| **Study intent** | `StudyScope = Literal["CAPITAL_PLANNING","OPERATIONAL_ONLY"]` — `study_scope.py:33` (re-declared `shared_mrt_multistream_authority.py:54`) | CAPITAL_PLANNING, OPERATIONAL_ONLY | **Whether new-project CapEx enters the study objective.** Never removes physical assets/capacity/scheduling/staffing. | `apply_study_scope()`; `StudyConfiguration.study_scope`; `ArchitectureResult.study_scope`; `engineering_authority` AuthorityRule `OPERATIONAL_CAPEX_OFF_ASSET_ON`; `build_installed_existing_pathway_scenario()` |
| **Transport architecture** | `Architecture` enum (`models.py`) | Conventional, MRT (+ MANUAL/AUTOMATED/HYBRID/MRT_DOMINANT variants in wo4a) | Which transport network is modeled. | four-architecture engine |

**Parallel/fragmented mode literals** (the same idea re-spelled per subsystem — important for the
recommendation): `capital_project_api.ProjectType=["GREENFIELD","RETROFIT"]`;
`existing_facility_retrofit.ProjectMode` & `external_supply_hub_spoke.ProjectMode =
["GREENFIELD","EXISTING_FACILITY_EXPANSION"]`; `ui_foundation.ProjectMode =
["UNSPECIFIED","GREENFIELD","EXISTING_FACILITY_RETROFIT"]`; `facility_engineering_model`
`ProjectSpatialMode=["RETROFIT","GREENFIELD"]`, `AdaptiveSpatialMode` adds `ADAPTIVE_REPURPOSING`,
`DevelopmentZone=["EXISTING_CORE","EXISTING_ADJACENT","EXPANSION_ZONE","NEW_BUILDING","UNKNOWN"]`;
`decision_pipeline`/`infrastructure_opex` `deployment_mode=["greenfield","existing_facility_expansion"]`;
`equal_budget` `planning_mode=["existing_facility_expansion","greenfield_requirement_derived"]`.

**No `EXISTING_FACILITY_AS_IS` / "as-is" / "digital-twin" project-level state exists anywhere.**
The nearest existing representations of an already-installed state are (a) the per-asset
`AssetStatus=Literal["EXISTING","PROPOSED"]` (`canonical_spatial_authority.py:63`, plus
scanner/generator variants adding UPGRADE/REPLACEMENT), and (b) the CapEx `deployment_mode =
"existing_facility_expansion"`. `study_scope.py` explicitly reuses the latter as the "as-is"
mechanism rather than inventing a project mode.

**Richest existing as-is descriptor:** `existing_facility_retrofit.py` —
`ExistingFacilityBaseline` / `ExistingFacilityMetadata` /
`ExistingFacilityResourceFact(existing_quantity, operational_quantity, unavailable_quantity,
condition_status, remaining_useful_life_years, planned_retirement_year, knowledge_status)`,
`DataStatus=[KNOWN/USER_ASSUMED/EVIDENCE_BACKED/UNKNOWN/NOT_MODELED]`,
`ResourceDisposition=[RETAIN/REUSE/MODIFY/EXPAND/REPLACE/RETIRE/NEW/NOT_MODELED]`,
`RetrofitFeasibilityStatus` (5 values), and `REQUIRED_BASELINE_RESOURCES` (11 resource
categories). This is a **per-resource** as-is fact model, **not** a project-level lifecycle state.

---

## 2. GEOMETRY IS NOT THE DIGITAL TWIN (Sec 4-5)

`WholeOncologyBaseline` (wo4a) is a **study baseline / benchmark scenario**, NOT a facility
model and NOT an operational-state root. `build_common_project_baseline()` composes a *synthetic*
census + demand + `build_benchmark_geometry()` + default `build_production_basis()` +
`_base_assumptions()` + `SharedNetworkAssumptions()`. `StudyConfiguration` carries
`development_context`, `study_scope`, `architecture` and `baseline_reference =
"WHOLE_ONCOLOGY_CONTROLLED_BENCHMARK_2026"`; `clone_study_configuration` uses `replace()` so a
study switch never mutates the baseline. **It is not suitable as the AS-IS Twin root** simply
because Part 3E uses it — it is a controlled benchmark.

Geometry is represented by **two deliberately separated authorities**:

- **`canonical_spatial_authority.py` — the canonical, platform-neutral spatial identity.**
  `CanonicalSpatialObject(mrtway_object_id, object_type, facility_id, building_id, floor_id,
  space_id, parent_object_id, transform:Transform[pos+euler], geometry_reference,
  coordinate_system[LOCAL_FACILITY/LOCAL_BUILDING/PROJECT_GLOBAL/EXTERNAL_MODEL], asset_status,
  operational_state, spatial_status, provenance, external_reference:ExternalReference[ifc_guid/
  revit_element_id/itwin_element_id/usd_prim_path/cad_entity_id/…], confidence,
  engineering_object_id, dimensions:EngineeringEnvelope[all default NOT_CALIBRATED])`. Held in a
  `SpatialObjectRegistry` keyed by `mrtway_object_id`. Builders: `build_facility_hierarchy` →
  `add_building` → `add_floor` (`default_floor_object_id = "{building}::{floor}"`) → `add_room`.
  Real Euclidean distance from accumulated parent-chain transforms (`resolve_global_position`,
  `compute_global_distance`). MRT infrastructure is first-class.
- **`facility_engineering_model.py` — a BIM/IFC-style, evidence-graded `FacilityObject`
  hierarchy** (Facility/Building/Storey[`elevation_m`]/Zone/Space[`area_m2`,`volume_m3`]/Wall/
  Slab/Door/Corridor/Shaft/Stair/Elevator/EquipmentPlacement…) with `SpatialCoordinate`,
  `CoordinateSystem`, `nodes`/`edges`, and `FacilityEngineeringObjectModel` as the aggregate root.

**All real coordinate numbers in the repo are SYNTHETIC.** `spatial_benchmark.build_benchmark_geometry`
(`FLOOR_COUNT=8`, `ROOMS_PER_FLOOR=10`, 4 m floors, 6 m spacing) stamps every node/space
`evidence_class="BENCHMARK_ASSUMED"`, `source_coordinate_reference="synthetic"`; the base model is
`source_type="BENCHMARK"`, `maturity="CONCEPTUAL"`, `dimension_provenance` default `NOT_CALIBRATED`.
Distances/retention/CapEx are recomputed from these synthetic coordinates on demand.

---

## 3. ENGINEERING OBJECT MODEL (Sec 6) — equipment is decoupled from geometry

Equipment identity lives in **catalog + facility-instance** modules, linked to geometry only by
ID — proven that equipment can exist with no location:

- `cyclotron_catalog.FacilityCyclotronInstance(instance_id, catalog_model_id, installed, site_* overrides)` — **no location field at all**.
- `generator_catalog.FacilityGeneratorInstance(..., location_object_id: str | None = None)` — location is an OPTIONAL anchor; moving it changes route/decay, never identity/economics.
- `scanner_catalog.FacilityScannerInstance(scanner_id, catalog_model_id, modality, ..., location_object_id: str | None = None)`.

The **bridge** is `CanonicalSpatialObject.engineering_object_id` (e.g. `CY-001`, `GEN-001`,
`SCN-PET-001`) plus `canonical_entity_binding_authority.py` — a pure ID↔ID index layer
(`EntityBindingRegistry`: patient↔room, patient↔radionuclide, batch↔cyclotron/generator[separate
indices], equipment↔room, clinical_resource↔room, patient↔scanner, transport_interface↔room…),
with `clone()`/`branch_entity_bindings` mirroring the What-If spatial branch. It "stores ID-to-ID
relationships, never geometry." `bind_equipment_room_from_spatial_registry` resolves a room via
`engineering_object_id` → nearest ROOM parent, returning `None` (never fabricated) if no spatial
object exists yet.

**Conclusion:** Geometry, engineering objects, and bindings are **already three separate,
linked layers.** This directly supports the AS-IS "normalize any input into the same underlying
object types" principle (Sec 22).

---

## 4. CLINICAL SPACE / ROOM FUNCTION (Sec 7) — FOUR competing representations

There is **no single canonical room-function type.** Room meaning is expressed four ways:

1. **`spatial_benchmark.RoomFunction`** (`Literal["NEUTRAL_CANDIDATE_SPACE","INJECTION_ADMINISTRATION","UPTAKE","SCANNER","SUPPORT_UNUSED"]`, `:40`) — **derived per-candidate by the optimizer, not persisted**; coarse (no combined injection+uptake, no PET-vs-SPECT room, no radiopharmacy/cyclotron/patient room).
2. **`facility_engineering_model.SpaceFunctionAssignment`** — **free-text** `source_function`/`proposed_function:str` + `assignment_status:ProgramAssignmentStatus[EXISTING_AS_BUILT/OPTIMIZER_PROPOSED/ACCEPTED_DESIGN]` + `suitability`/structural/shielding/hvac suitability. Vocabulary is *backed by* the rich `EquipmentClass` Literal (Cyclotron/Hot cell/Radiopharmacy/Injection room/Uptake room/PET-CT/PET-MR/SPECT-CT scanner/Control room/…) but `proposed_function` is typed `str`, not `EquipmentClass` (unenforced). `RequiredFacilityProgram` expresses need as per-category COUNTS; `evaluate_required_program_feasibility` string-matches against label sets.
3. **`canonical_spatial_authority.SpatialObjectType`** — folds function INTO the geometry object type (ROOM/INJECTION_ROOM/UPTAKE_ROOM/PATIENT_ROOM/NUCLEAR_MEDICINE_ROOM/CONTROL_ROOM/CYCLOTRON/PET_SCANNER/SPECT_SCANNER/RADIOPHARMACY/…); **stored** as `object_type`.
4. **`clinical_resource_identity.ClinicalResourceType`** (`Literal["INJECTION_ROOM","UPTAKE_ROOM","SCANNER","INBOUND_ROOM"]`) — a **persistent schedulable resource identity** (stable IDs `INJ-001`/`UP-001`/`SCN-001`/`IR-001`), decoupled from geometry; `ClinicalResource` carries optional `building/floor/room_id` and, for scanners only, a `modality:ScannerModality[PET/SPECT]`. `ClinicalResourceInventory` is the persistent facility inventory the long-horizon planner references (daily schedules consume it, never recreate it). **The PET/SPECT distinction lives here, not in RoomFunction.**

Physical geometry is deliberately **function-neutral** (benchmark rooms are all
`NEUTRAL_CANDIDATE_SPACE` until an optimizer or program assignment layers function on top).

---

## 5. ROUTE / CONNECTIVITY (Sec 8) — TWO route authorities

- **Authority 1 — `facility_engineering_model` + `spatial_benchmark` (weighted Dijkstra + the ONLY transport-TIME physics).** `SpatialEdge(length_m:float, vertical_change_m, edge_type[…/ELEVATOR/VERTICAL/…], directionality, evidence_class, route_corridor_class)`. `network_route_distance_m` (Dijkstra, recomputed each call, **raises `ValueError` "No network route exists"** for inaccessible). `_route_metrics_for_rooms` derives distance/vertical/transitions; `_manual_transport_minutes` and `_mrt_transport_minutes` compute transport time (vertical/floor transition = `edge_type ELEVATOR/VERTICAL` + numeric `vertical_change_m`; `_physical_transition_count` = H↔V mode changes on the compressed motion sequence, not graph-edge count). **Do not alter transport physics.**
- **Authority 2 — `canonical_spatial_authority` (mode-aware BFS reachability, no time).** Its OWN `SpatialEdge(length_m:float|NOT_CALIBRATED, compatible_modes:frozenset[TransportMode], vertical:bool)`; `TransportMode=[WALKING_PORTER/AGV_AMR/PNEUMATIC_TUBE/MRT/PATIENT_MOVEMENT]`; `resolve_route(...)→RouteResult(path_edge_ids, distance_m, calibration_status)`; NOT_CALIBRATED length ⇒ `ROUTE_NOT_CALIBRATED`; unreachable ⇒ empty path NOT_CALIBRATED (**does not raise**).

Route topology is **stored** (nodes/edges/graph on the model); route results are always
**recomputed** (no cache). `RouteGeometryStatus=[RECONSTRUCTED/NOT_RECONSTRUCTED]` +
`route_distance_source:EvidenceClass` record whether a routable network has been reconstructed.
Route evidence **can** originate from imported geometry (per-edge `evidence_class` allows
BIM_AUTHORITATIVE/CAD_ENGINEERING/PLAN_DERIVED); the benchmark just stamps everything
BENCHMARK_ASSUMED/synthetic. ⚠️ Gotcha: two same-named `SpatialEdge`/`SpatialNode` types with
different fields.

---

## 6. PROVENANCE vs CALIBRATION / CONFIDENCE (Sec 9-11)

**Many overlapping vocabularies, defined per-subsystem, with no single central enum.** Key ones:

| # | Type / location | Values | Meaning |
|---|---|---|---|
| 1 | `resource_source` on `ClinicalResourceInputs` (wo4a) | PROJECT_SUPPLIED / FACILITY_DERIVED / CONTROLLED_BENCHMARK (default) | Where clinical-resource counts came from. (Degrades Literal→`str` on the Part 3D result object, defaulting `"NOT_EVALUATED"`.) |
| 2 | `Provenance` (`canonical_spatial_authority`) | USER_CREATED/TEMPLATE/IMPORTED_IFC/IMPORTED_CAD/RECONSTRUCTED/API/DERIVED/USER_RELOCATED/IMPORTED_ITWIN | **Origin** of a spatial object. |
| 3 | `SpatialStatus` (`canonical_spatial_authority`) | CALIBRATED/PARTIALLY_CALIBRATED/LOCATION_NOT_CALIBRATED/ORIENTATION_NOT_CALIBRATED/GEOMETRY_NOT_CALIBRATED/DERIVED/USER_PLACED/IMPORTED | **Spatial calibration** state (distinct from origin). |
| 4 | `EvidenceClass` (`facility_engineering_model`) | BIM_AUTHORITATIVE/CAD_ENGINEERING/PLAN_DERIVED/USER_SUPPLIED/TEMPLATE_DERIVED/BENCHMARK_ASSUMED/DERIVED_GEOMETRY | Geometry evidence tier. `SOURCE_PROFILE_BY_TYPE` **couples** source_type→evidence_class (IFC→BIM_AUTHORITATIVE…). `Confidence=[HIGH/MEDIUM/LOW/UNKNOWN]` is a separate field. |
| 5 | `EvidenceClass=str` (`editable_default_authority`, open) | MANUFACTURER_DEFAULT > PUBLISHED_* > PROJECT_CONTROLLED_ASSUMPTION > CONTROLLED_ENGINEERING_ASSUMPTION > NOT_CALIBRATED; CALIBRATED_PROJECT_VALUE reserved/unused | Editable-parameter source hierarchy; `source_type` vs `confidence` cleanly separate; `None ⇒ NOT_CALIBRATED`. |
| 6 | `EvidenceClass` (`cyclotron_production_estimation_authority`) | SITE_CALIBRATED/MANUFACTURER_CALIBRATED/MODELED_ESTIMATE/CONTROLLED_ASSUMPTION/NOT_AVAILABLE (+ `_EVIDENCE_PRECEDENCE` ladder) | Mixes provenance+calibration into one ordinal ladder; `ConfidenceClass` separate ("Confidence NEVER changes calibration"). |
| 7 | `ProvenancedField` (cyclotron/generator/scanner catalogs) | `source` + `evidence_type`(15) + `calibration_status`[manufacturer/site/literature/modeled/not_calibrated] + `confidence`(lowercase) | The **cleanest 4-axis record**. Actual JSON catalog values only use `literature_calibrated`/`not_calibrated`, `technical_literature`/`site_specific`/`not_calibrated`, `medium`/`unknown`. |
| 8 | `DataStatus` (`existing_facility_retrofit`) | KNOWN/USER_ASSUMED/EVIDENCE_BACKED/UNKNOWN/NOT_MODELED | Value-bearing statuses REQUIRE a quantity; UNKNOWN/NOT_MODELED must NOT carry one. |
| 9 | `engineering_evidence.py` | `EngineeringSourceType`(13)→`EvidenceSourceTier`[TIER_1..TIER_4/UNKNOWN]; `SourceQuality`; `ProposalPromotionStatus`[evidence_only→candidate→accepted→rejected→superseded] | **Richest formal provenance-tier ladder**, kept distinct from quality. |
| 10 | `engineering_authority.py` | `AuthorityClassification`[AUTHORITATIVE/DERIVED_VIEW/DIAGNOSTIC_ONLY/LEGACY_COMPATIBILITY/PROJECT_ASSUMPTION/REQUIRES_CALIBRATION/DEPRECATED_ACTIVE_RISK] + `AUTHORITY_REGISTRY` | Governance/ownership registry (who owns each quantity). |

**Does the repo separate PROVENANCE (source) from CALIBRATION/CONFIDENCE (reliability)?**
**Partially — cleanly in places, coupled in others, and duplicated per subsystem.**
Cleanly separated: `ProvenancedField` (4 independent axes), `EditableParameter` (source_type vs
confidence), `CanonicalSpatialObject` (provenance vs spatial_status vs confidence), the cyclotron
estimator. Coupled/collapsed: `SOURCE_PROFILE_BY_TYPE` (source→evidence), the cyclotron
`EvidenceClass` ladder (provenance+calibration), `DataStatus` (provenance+presence). Confidence is
BOTH explicit (dedicated fields) AND implicit (ladders/precedence). Two casings
(`HIGH/…` vs `high/…`) are not reconciled.

**Sec 10 (expected future AS-IS provenance classes):** equivalents already exist —
PROJECT_SUPPLIED / FACILITY_DERIVED (`resource_source`); FACILITY_IMPORTED ≈
`IMPORTED_IFC/IMPORTED_CAD/IMPORTED_ITWIN`; MEASURED/EXTERNAL_SOURCE ≈ `API` +
`site_specific_measured_data`; INFERRED/RECONSTRUCTED ≈ `RECONSTRUCTED`; CONTROLLED_ASSUMPTION
present in multiple vocabularies. **Do NOT create a second provenance hierarchy for AS-IS** —
the minimum need is to *reuse `resource_source` semantics facility-wide* and keep provenance vs
calibration on the two axes `ProvenancedField`/`CanonicalSpatialObject` already model.

---

## 7. INGESTION SEAMS (Sec 12-14) — classification

**The repository has NO production geometry ingestion.** Classification:

| Seam | Classification | Evidence |
|---|---|---|
| `ifc_hospital_proof_model_generator.py` | **SYNTHETIC_PROOF** (generator, not ingester) | `MRTWAY_MODEL_CLASS="SYNTHETIC_TEST_BIM"`, `MRTWAY_MODEL_PURPOSE="BENTLEY_ITWIN_INTEGRATION_PROOF"`; hand-writes IFC4 STEP (no `ifcopenshell`); never touches `SpatialObjectRegistry`; `read_ifc_proof_model` only re-reads its own generated file; hardcoded synthetic dims (30×20 m, 4 m floors). |
| `bentley_itwin_client.py` (+ `bentley_canonical_binding`, `bentley_access_recovery`, `bentley_personal_user_diagnostic`) | **WORKING_PROTOTYPE** (no live call in-repo) | Injectable `BentleyTransport`; "NO LIVE CALL IN THIS PHASE"; deterministic fake only; no hardcoded credentials; returns typed records. Element→canonical mapping is NOT here. |
| `openusd_spatial_adapter.py` (+ `openusd_yc_demo_binding`, `generate_openusd_hospital_*`) | **WORKING_PROTOTYPE, export-only** | Canonical→USD serialization; `usd-core` vendored in gitignored `.usd_runtime`, gated by `OPENUSD_RUNTIME_AVAILABLE`, raises `OpenUsdRuntimeNotAvailable` if absent (never a fake scene). `import_scene` is READ-ONLY reconciliation (USD prim `customData.mrtway_object_id`; flags orphan/duplicate), never creates canonical geometry from USD. |
| `canonical_spatial_authority.normalize_*_import` — 7 of 8 modes | **DOCUMENTED_ONLY / WRAPPER** | `normalize_blank_manual_import`, `_template_`, `_ifc_bim_`("No IFC SDK"), `_cad_`, `_pdf_image_`(`reconstruction_status="NOT_YET_RECONSTRUCTED"` → **NOT_IMPLEMENTED**), `_api_`, `_intelligent_reconstruction_` all just finalize an *already-built* registry into a uniform `NormalizedImportResult`. No parser. |
| `canonical_spatial_authority.normalize_itwin_import` | **WORKING (the ONLY real record→object mapper)** | Iterates `Sequence[BentleyElementRecord]` (typed, already-retrieved), `resolve_bentley_object_type` (first-phase set only, else IGNORED_UNMAPPED), deterministic binding precedence (existing itwin_element_id REUSED; equipment REQUIRES explicit `engineering_object_id` else AMBIGUOUS; exact room_number match; else CREATED; CONFLICT leaves existing untouched); NO fuzzy/nearest-coordinate matching; requires a WhatIfSpatialState registry (never mutates L0). |
| `healthcare_integration.py` + `healthcare_adapters.py` | **TEST_FIXTURE / SYNTHETIC** | "No live connections… `SYNTHETIC_TEST_FIXTURE`"; `SECURITY_COMPLIANCE_NOT_IN_SCOPE` (NOT HIPAA). Produces `CanonicalOperationalPatientRecord` (patient/operational data, NOT geometry). |
| `interactive_spatial_authoring.py` | **WORKING_PROTOTYPE** (manual/structured authoring) | `AuthoringSession` over existing canonical objects: select/move/rotate/stretch/add/remove/copy/connect/undo-redo/palette; `build_proposed_simulation_input → LockedSpatialState`. Accepts structured interactions/coordinates, not files. |
| CSV / JSON / point-cloud / GIS / OCR / Revit / DWG / DXF parsers | **NOT_IMPLEMENTED** | grep for `ifcopenshell`/`ezdxf`/`pdfplumber`/`cv2`/`open3d`/`laspy`/`pyproj`/`fitz`/`pytesseract` = none (outside vendored `.usd_runtime`). Only `registry_to_json`/`registry_from_json` (own canonical registry). |

**Sec 13 verdict:** `SYNTHETIC_TEST_BIM` / `BENTLEY_ITWIN_INTEGRATION_PROOF` is confirmed **NOT
equivalent** to `EXISTING_FACILITY_AS_IS` ingestion.

**Sec 14 / Sec 22 — narrowest parser-free path for already-structured facility facts (confirmed):**
`build_facility_hierarchy` → `add_building` → `add_floor` (`"{building}::{floor}"`) → `add_room`
(with `object_type`, `transform` = coordinates, `engineering_object_id`) →
`build_nuclear_engineering_objects` (cyclotron/scanner/radiopharmacy, where
`mrtway_object_id == engineering_object_id`) + `build_general_logistics_origin_objects`, finalized
by `normalize_blank_manual_import`. Typed records (rooms/equipment/coords) can alternatively flow
through `normalize_itwin_import` via `BentleyElementRecord`. **The input method never becomes the
engineering authority** — every mode normalizes into the same `CanonicalSpatialObject` types.

---

## 8. OPERATIONAL STATE, TRACEABILITY, SIMULATION CONTRACT (Sec 15-18)

**Sec 15 — no single `FacilityOperationalState`/`HospitalOperationalState` object.** State is
deliberately split across five cooperating modules, tied by shared canonical identity
(`internal_model_patient_id`, resource_id `INJ/UP/SCN/IR-xxx`, `cyclotron_id`, `batch_id`):

1. **`long_horizon_operational_planning.py`** — demand + horizon authority.
   `CanonicalOperationalPatientRecord` (identity, `demand_status` COMMITTED/FORECAST, radionuclide,
   prescribed_activity, scheduled_date + mutability + earliest/latest, admission/discharge,
   existing_room_id, scanner appointment, clinical_resource_mode, modality?, clinical_priority?);
   `CanonicalOperationalRecordSource` Protocol = the FHIR/HL7/DICOM adapter boundary (interface
   only). `CyclotronCalendar` (per-date ON/OFF; `build_fleet_for_date` returns None, never raises,
   → UNMET). `run_operating_day_plan(day, records_for_day[single radionuclide], cyclotron_calendar,
   pathway, geometry, assumptions, resource_calendar, distribution_concurrency, …)` → the single
   authoritative day engine (calls `build_production_clinical_schedule`). Horizon:
   day → Weekly → Monthly → `LongHorizonMasterPlan` over `OperatingCalendar`.
2. **`clinical_resource_identity.py`** — persistent `ClinicalResourceInventory` +
   `ResourceAvailabilityCalendar` (per-date; UNAVAILABLE excluded, never deleted).
3. **`live_operational_state.py`** — live event-driven rolling reoptimization. `OperationalStateStore`
   (idempotent events), `PlanVersion` chain (`version_id`/`previous_version_id`, PLAN-0000 →
   PLAN-0001…), `apply_event_and_replan` reuses `run_operating_day_plan` with identity-sticky
   localization (`preserve_resource_indices` + reservations + blocked indices; LEVEL_3 escalation).
4. **`digital_twin_simulation_state.py`** — point-in-time state resolver
   (`digital_twin_state_at_time` → `DigitalTwinStateAtTime`; Transport/Patient/Cyclotron runtime
   state). A derived VIEW (O(missions), horizon-independent), not an authoritative store.
5. **`operational_day_orchestrator.py`** — intra-day trajectory (`DayTrajectorySet.state_at_time`).

**Sec 16 — patient traceability.** Canonical end-to-end lives in ONE place:
`canonical_entity_binding_authority.PatientTraceabilityChain` +
`resolve_patient_radionuclide_chain` (patient → radionuclide → batch/source → cyclotron|generator
+ room → payload → mission → transport_resource → scanner + room), marking any missing hop
`UNRESOLVED` with a reason (never fabricated). **Known gap:** the mission hop is often UNRESOLVED
(`ProductionClinicalPatientTrace.delivery_job_id` has no cross-reference to
`TransportMission.mission_id`); `prescribed_activity` is not on the chain. Component-local traces:
`ProductionClinicalPatientTrace` (PET/cyclotron), `SpectDoseLineage` (SPECT/generator),
`HybridPatientTrace` (`canonical_patient_id` is None unless `attach_canonical_patient_ids` remaps
the synthetic `P1..Pn`).

**Sec 17-18 — simulation contract + benchmark fallbacks (the single most important AS-IS risk).**
`run_operating_day_plan` itself has **no** silent geometry/resource/patient fallback (it raises or
reports UnmetDemand). The silent-substitution risk is concentrated in the `wo4a` + `spatial_benchmark`
builder layer. Every benchmark fallback an AS-IS run must explicitly override:

| # | Fallback | Location |
|---|---|---|
| 1 | Clinical counts **6 / 6 / 12** (`BENCHMARK_SCANNERS/INJECTION/UPTAKE`; `ClinicalResourceInputs` defaults + `resource_source=CONTROLLED_BENCHMARK`; `BENCHMARK_CLINICAL_RESOURCES`; `_nuclear_result` falls back when `clinical_resources=None`) | `whole_oncology_four_architecture_optimization.py` |
| 2 | Synthetic geometry (`build_benchmark_geometry`: 8 floors × 10 rooms, all `BENCHMARK_ASSUMED`/synthetic coords); `PRIMARY_DEMAND=200` | `spatial_benchmark.py` |
| 3 | Default production basis F-18 / `GE_PETTRACE_890` / 71 min / `CY-001` single-cyclotron fleet (`build_production_basis`; **raises** if no calibrated record — the Part 3D seam) | `spatial_benchmark.py` |
| 4 | Default `_base_assumptions` (10-yr, benchmark cycle minutes) | `spatial_benchmark.py` |
| 5 | Synthetic patient populations (`build_common_project_baseline` 200-bed/170-occ; `build_eight_floor_bed_matched_baseline` 80-bed; `build_eight_floor_deterministic_capital_baseline` 30 fixed) via `build_stochastic/representative_day_population`; `baseline_reference="WHOLE_ONCOLOGY_CONTROLLED_BENCHMARK_2026"` | `whole_oncology_four_architecture_optimization.py` |

> AS-IS Twin must supply real geometry, real ProductionBasis/CyclotronCalendar, explicit
> `ClinicalResourceInputs(resource_source=PROJECT_SUPPLIED/FACILITY_DERIVED)`, real assumptions,
> and real `CanonicalOperationalPatientRecord`s — **and produce an explicit completeness/gap
> report** — so it never silently becomes "real geometry + benchmark equipment + benchmark
> staffing + benchmark patients."

---

## 9. LOCKDOWN / SCENARIO / VERSION (Sec 19-21) — FULLY IMPLEMENTED, test-backed

This is a **mature, production-grade seam** (not documentation-only), across three cooperating
authorities + one operational versioning scheme:

- **`canonical_spatial_authority.py`** — `LockedSpatialState` (frozen, "NEVER mutated by what-if");
  `WhatIfSpatialState.branch_from` (dict-clone isolation), `reset_to_locked`, `apply_changeset`
  (mutates only the clone; `ChangeOperation` ADD/REMOVE/MOVE/ROTATE/COPY/CHANGE_QUANTITY/EXTEND/
  SHORTEN/RECONNECT with honest NOT_CALIBRATED CapEx/OPEX impact hooks), `undo_last_change`,
  `compute_delta`, `promote_what_if_to_simulation_input` (explicit; sets `promoted=True`; returns a
  NEW frozen locked state). `apply_camera_rotation` (zero-impact VIEW) vs `apply_engineering_rotation`
  (real changeset).
- **`mrt_auxiliary_systems_authority.py`** — `UnifiedWhatIfScenario` (ONE ordered `active_changes`
  list where SPATIAL + PARAMETER changes coexist), `ActiveChange`, `branch_what_if_scenario`,
  replay-based `reset_what_if_category`/`remove_one_change`/`return_scenario_to_locked`.
- **`lockdown_what_if_lineage_authority.py`** — the binding/lineage layer ("BINDS existing
  identities, never re-derives"). `CanonicalLockdownRecord` (frozen: lockdown_id,
  parent_lockdown_id, source_what_if_id, spatial_state, active_parameters, simulation/engineering/
  economic_result held **by reference**, `status` CURRENT/SUPERSEDED, entity_bindings?).
  `CanonicalWhatIfRecord` (`status` ACTIVE/SAVED_VIEW/DISCARDED/PROMOTED_TO_LOCKDOWN).
  `LockdownLineageRegistry`. `create_first_lockdown` (raises if any exists); `branch_what_if`
  (never touches `current_lockdown_id`); `promote_what_if_to_lockdown` (the ONLY writer of
  `current_lockdown_id`: new record records parent + source lineage, parent → SUPERSEDED via
  `replace()` and **preserved, never deleted**, W1 → PROMOTED_TO_LOCKDOWN); `discard_what_if`
  (preserved DISCARDED, never deleted); `bind_plan_version`.
- **`live_operational_state.py`** — `PlanVersion` chain (separate operational versioning, bridged
  only via `bind_plan_version`).

| Capability | Status |
|---|---|
| Immutable authoritative baseline | **IMPLEMENTED** (frozen `CanonicalLockdownRecord` + frozen `LockedSpatialState`) |
| Scenario / What-If branching off baseline | **IMPLEMENTED** (`branch_from`, dict-clone isolation) |
| Promotion to NEW baseline preserving prior | **IMPLEMENTED** (`promote_what_if_to_lockdown`; parent → SUPERSEDED, preserved) |
| Version history / lineage | **IMPLEMENTED** (parent_lockdown_id chain + PlanVersion chain + JSON serialization) |
| Guard against silent replacement | **IMPLEMENTED** (single-writer of `current_lockdown_id`, `promoted` flag, status transitions, tests in `test_reactive_engineering_economic_consequence_authority.py`, `test_phase2b1_continuation.py`, `test_phase2b2_final_closure.py`) |

**Sec 20 verdict:** the intended future sequence (Evidence → Normalized AS-IS objects →
Validation/gaps → Operational-state reconstruction → Baseline simulation → LOCKDOWN → What-If
branches) maps onto **existing seams**: normalize_* → `SpatialObjectRegistry` → `validate_spatial_registry`
→ `run_operating_day_plan`/hybrid → `create_first_lockdown` → `branch_what_if`/`promote_what_if_to_lockdown`.
LOCKDOWN already means an authoritative fixed baseline (never "latest upload/import/simulation");
a What-If cannot silently replace its parent. **The AS-IS Twin can build on this, not rebuild it.**

---

## 10. REQUIRED FUTURE AS-IS OBJECT LAYERS (Sec 23) — classification

| Layer | Classification | Existing authority |
|---|---|---|
| A. Facility identity | **PARTIAL_EXISTING_AUTHORITY** | `facility_id` on `CanonicalSpatialObject`/`FacilityEngineeringObjectModel`; `ExistingFacilityMetadata`. No project-level facility-identity record unifying them. |
| B. Physical geometry | **EXISTING_CANONICAL_AUTHORITY** | `canonical_spatial_authority` (`CanonicalSpatialObject`/`Transform`/`EngineeringEnvelope`) + `facility_engineering_model` (BIM hierarchy). Real numbers currently BENCHMARK_ONLY. |
| C. Engineering objects / equipment | **EXISTING_CANONICAL_AUTHORITY** | cyclotron/generator/scanner catalogs + `FacilityInstance`s + `engineering_object_id` bridge. |
| D. Clinical space classification | **PARTIAL_EXISTING_AUTHORITY** (fragmented across 4 representations) | `SpatialObjectType`, `SpaceFunctionAssignment`/`EquipmentClass`, `ClinicalResourceType`, `RoomFunction`. |
| E. Connectivity / routes | **EXISTING_CANONICAL_AUTHORITY** | two route authorities (Dijkstra+time; mode-aware BFS). |
| F. Operational resources | **EXISTING_CANONICAL_AUTHORITY** | `ClinicalResourceInventory` + `ResourceAvailabilityCalendar`; `CyclotronCalendar`. |
| G. Patient / appointment state | **EXISTING_CANONICAL_AUTHORITY** | `CanonicalOperationalPatientRecord` + `CanonicalOperationalRecordSource` Protocol. |
| H. Production state | **EXISTING_CANONICAL_AUTHORITY** | `ProductionBasis`/`CyclotronCalendar`/`ProductionClinicalPatientTrace`; `digital_twin_simulation_state` cyclotron/generator runtime state. |
| I. Evidence / provenance | **EXISTING_CANONICAL_AUTHORITY** (fragmented, multiple vocabularies) | `Provenance`, `EvidenceClass`(×3), `ProvenancedField`, `engineering_evidence` tier ladder, `resource_source`. |
| J. Calibration / confidence | **EXISTING_CANONICAL_AUTHORITY** (partially coupled to provenance) | `SpatialStatus`, `calibration_status`, `Confidence`, `DataStatus`, NOT_CALIBRATED sentinels. |
| K. Validation / completeness gaps | **PARTIAL_EXISTING_AUTHORITY** | `validate_spatial_registry`/`SpatialValidationIssue`, `ProgramFeasibilityReport`, `existing_facility_retrofit` gap/disposition tables, `UnmetDemandRecord`. No unified FACILITY-SUPPLIED/DERIVED/INFERRED/ASSUMPTION/MISSING completeness report yet. |
| L. Scenario / version state | **EXISTING_CANONICAL_AUTHORITY** (mature) | lockdown/what-if lineage + PlanVersion (Sec 9 above). |

No layer is `NOT_MODELED`. The AS-IS Twin is overwhelmingly an **extension/orchestration** task
over existing canonical layers, plus one genuinely new artifact (a completeness/gap report, K) and
a project-level starting-state authority (below).

---

## 11. AS-IS STARTING-STATE INSERTION POINT (Sec 24)

```
RECOMMENDED_ASIS_STARTING_STATE_INSERTION_POINT =
    A NEW, single orthogonal canonical "project starting state" authority
    (one closed type), distinct from DevelopmentContext and StudyScope.

EXISTING_TYPE_TO_EXTEND = (none — see WHY_NOT_* below)
NEW_TYPE_REQUIRED       = YES
PROPOSED_TYPE_NAME      = ProjectStartingState  (Literal)
PROPOSED_VALUE          = EXISTING_FACILITY_AS_IS
                          (alongside GREENFIELD, RETROFIT for a complete, non-overloaded axis)
PROPOSED_FIELD_OWNER    = StudyConfiguration (whole_oncology_four_architecture_optimization.py)
                          — the existing project-configuration root that ALREADY composes
                          development_context + study_scope + architecture without mutating the
                          baseline (clone_study_configuration). A new sibling field belongs here.
PROPOSED_FIELD_NAME     = project_starting_state  (default RETROFIT or GREENFIELD to preserve
                          every existing consumer; AS-IS is opt-in only)
CURRENT_EXISTING_VALUES = DevelopmentContext[RETROFIT, GREENFIELD];
                          StudyScope[CAPITAL_PLANNING, OPERATIONAL_ONLY];
                          (no existing value carries AS-IS semantics)
CURRENT_CONSUMERS       = DevelopmentContext: compute_common_project_capex + all 4 evaluators +
                          transform_registry_for_context + transition-impact helper;
                          StudyScope: apply_study_scope + evaluators;
                          A new project_starting_state field starts with ZERO consumers (additive).

SEMANTIC_REASON =
    The three concepts are genuinely different questions:
      - project_starting_state  = "what starting state IS the facility?"  (greenfield site /
        retrofit intervention on an existing facility / reconstruct-what-exists-now with no
        implied upgrade)
      - development_context     = "how should common-asset CapEx be attributed?" (a binary switch)
      - study_scope             = "does new-project CapEx enter the study objective?"
    EXISTING_FACILITY_AS_IS is a starting-state answer, not a CapEx-attribution or study-objective
    answer. An as-is reconstruction may involve NO project intervention at all.

WHY_NOT_PROJECTTYPE =
    "ProjectType" is not one type — it is fragmented across capital_project_api.ProjectType,
    existing_facility_retrofit.ProjectMode, ui_foundation.ProjectMode, facility_engineering_model.
    ProjectSpatialMode, deployment_mode, planning_mode. There is no single canonical ProjectType to
    extend; extending any one of these would still leave the others divergent and would not give a
    project-level lifecycle authority. (A future consolidation is desirable but is NOT this task.)

WHY_NOT_DEVELOPMENTCONTEXT =
    DevelopmentContext's ONLY real behavioral effect is CapEx attribution
    (compute_common_project_capex: RETROFIT ⇒ $0 new / EXISTING_RETAINED; GREENFIELD ⇒ charged).
    Adding EXISTING_FACILITY_AS_IS as a third value would force every existing consumer
    (all four evaluators, transform_registry_for_context, the transition helper) to answer
    "how do I attribute CapEx for AS-IS?" — changing the field's established meaning and risking
    silent mis-attribution. AS-IS is about the facility's starting state, not CapEx treatment;
    it can COMPOSE WITH either RETROFIT or GREENFIELD CapEx attribution as needed.

WHY_NOT_STUDYSCOPE =
    StudyScope is purely "does CapEx enter the objective" (CAPITAL_PLANNING vs OPERATIONAL_ONLY);
    it explicitly "never removes physical assets/capacity/scheduling/staffing." AS-IS is not a
    study-objective toggle. An AS-IS twin will most often run OPERATIONAL_ONLY, but the two are
    independent axes and must remain composable.

BACKWARD_COMPATIBILITY_RISK = LOW
    A new optional field on StudyConfiguration (defaulted to the current lifecycle value) is purely
    additive; no existing consumer reads it, so existing tests and results are byte-for-byte
    unchanged until AS-IS is explicitly selected. The per-asset AssetStatus="EXISTING" and
    deployment_mode="existing_facility_expansion" mechanisms already express "already installed" at
    the asset/CapEx layer and can be reused unchanged by an AS-IS run.

FILES_LIKELY_TO_REQUIRE_NARROW_MODIFICATION =
    whole_oncology_four_architecture_optimization.py (define ProjectStartingState + add the
        optional StudyConfiguration field; NO evaluator behavior change required for the additive
        default) — this is where DevelopmentContext/StudyScope/StudyConfiguration already live.
    (A NEW module, e.g. existing_facility_asis_twin.py, would own the orchestration:
        ingestion → normalized canonical objects → validation/gap report → operational-state
        reconstruction → simulation → lockdown. Created in the IMPLEMENTATION phase, not now.)

FILES_THAT_SHOULD_NOT_BE_MODIFIED =
    equal_budget.py; hybrid_optimization.py (decay math); spatial_benchmark.py transport physics
    (_manual_transport_minutes / _mrt_transport_minutes); canonical_spatial_authority.py
    lockdown/what-if mechanics; the *_equipment_catalog.json calibration data; any Part 3B/3C/3D/3E
    authority. The AS-IS Twin EXTENDS/ORCHESTRATES these; it must not fork or re-derive them.

IMPLEMENTATION_COMPLEXITY = MEDIUM
    LOW for the starting-state field itself (additive Literal + StudyConfiguration field). MEDIUM
    overall because the real work is the orchestration module + the completeness/gap report (Layer
    K) + wiring project-supplied geometry/equipment/resources/patients through the existing
    builders while explicitly overriding the five benchmark fallbacks (Sec 8) — all reuse, no new
    physics.

RECOMMENDATION_CONFIDENCE = HIGH
```

**One-line summary:** add ONE orthogonal `ProjectStartingState` authority
(`GREENFIELD | RETROFIT | EXISTING_FACILITY_AS_IS`) on `StudyConfiguration`; build the AS-IS Twin
as a thin orchestration module that (1) ingests structured facts through the existing manual/iTwin
normalization path into `CanonicalSpatialObject`s, (2) reuses catalogs/`ClinicalResourceInventory`/
`CanonicalOperationalPatientRecord`/`ProductionBasis` as the engineering/operational layers,
(3) explicitly overrides the five `wo4a`/`spatial_benchmark` benchmark fallbacks and emits a
FACILITY-SUPPLIED / FACILITY-DERIVED / INFERRED / CONTROLLED-ASSUMPTION / MISSING completeness
report, and (4) lands the reconstructed state on the existing, mature LOCKDOWN → What-If lineage
seam. **No parallel architecture is required.**

---

## 12. INVESTIGATION CONSTRAINTS HONORED

- Read-only: no source file was created or modified; no new type/enum/parser/state value was added.
- No staging, no commit, no push.
- This report is the sole output artifact (input to the subsequent implementation prompt).
- Every classification distinguishes IMPLEMENTED vs PARTIAL vs DOCUMENTED_ONLY vs
  SYNTHETIC_PROOF/TEST_FIXTURE vs NOT_IMPLEMENTED, per Sec 0's governing principle.

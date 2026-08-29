# Scanner Authority Review & Part 3E Readiness

**Type:** AUDIT → AUTHORITY TRACE → GAP CLASSIFICATION → PART 3E READINESS
**Starting HEAD:** `a1002ca` (origin/main, clean, divergence 0/0)
**Result:** `READY_WITH_DOCUMENTED_LIMITATIONS` (Section 26 class **B**)
**Engine code changed:** **NO** — this is a review-only build (one review doc + one focused test).

> This review does not merely inventory scanner manufacturers/models. It audits
> three separate scanner relationships — patient/clinical-scheduling awareness,
> radionuclide/procedure/modality awareness, and geometric/spatial/facility
> awareness — and classifies each against the *physical* repository, never
> against future doctrine.

---

## 0. Authority-first precheck

```
git status --short                     -> (empty; clean)
git status -sb                         -> ## main...origin/main
git log -2 --oneline --decorate        -> a1002ca (HEAD -> main, origin/main) ...
git rev-list --left-right --count origin/main...main -> 0   0
```

- `STARTING_HEAD = a1002ca`
- `STARTING_BRANCH = main`
- `STARTING_DIVERGENCE = 0 / 0`
- `STARTING_WORKING_TREE_CLEAN = YES`

Authorities physically read: `MRT_PHARMA_AUTHORITY_INDEX.md`,
`MRT_PHARMA_PRODUCT_DOCTRINE.md`, `MRT_PHARMA_OPEN_GAPS.md`,
`MRT_PHARMA_BUILD_LEDGER.md`, `scanner_catalog.py`,
`scanner_equipment_catalog.json`, `clinical_resource_identity.py`,
`oncology_pet_spect_scenario.py`, `whole_oncology_four_architecture_optimization.py`
(Part 3D gate), `canonical_spatial_authority.py`, `openusd_spatial_adapter.py`,
`interactive_spatial_authoring.py`, `digital_twin_simulation_state.py`.

---

## A. Scanner inventory table

Physically verified in `scanner_equipment_catalog.json` (loaded by
`scanner_catalog.load_scanner_catalog`). **Six** models, two modalities.

| catalog_model_id | Manufacturer | Model | Modality | commercial_status | new_purchase_candidate | Model-specific acquisition minutes (literature) |
|---|---|---|---|---|---|---|
| `SIEMENS_SYMBIA_PRO_SPECTA` | Siemens Healthineers | Symbia Pro.specta | SPECT | current | true | mpi 20 / bone 25 / general 20 |
| `GE_NM_CT_870_DR` | GE HealthCare | NM/CT 870 DR | SPECT | current | true | mpi_ct 25 / bone_ct 30 / onc_ct 30 |
| `GE_NM_CT_860` | GE HealthCare | NM/CT 860 | SPECT | current | true | mpi_ct 25 / bone_ct 30 |
| `PHILIPS_BRIGHTVIEW_XCT` | Philips | BrightView XCT | SPECT | **LEGACY_INSTALLED_BASE** | **false** | mpi_ct 25 / bone_ct 30 |
| `GE_DISCOVERY_MI` | GE HealthCare | Discovery MI | PET | current | true | onc_ct 20 / wb_ct 25 |
| `SIEMENS_BIOGRAPH_VISION` | Siemens Healthineers | Biograph Vision | PET | current | true | onc_ct **15** / wb_ct **20** |

Notes:
- Manufacturer/model/modality/commercial-status/provenance are preserved per
  model; the loader never collapses them to a generic "PET scanner"/"SPECT
  scanner" (`scanner_catalog.ScannerCatalogModel`).
- `typical_acquisition_minutes_per_protocol` **is model-specific and differs**
  between models (Biograph Vision oncology 15 min vs Discovery MI 20 min). It is
  honestly `literature_calibrated`, never `manufacturer_calibrated`.
- `dimensions_footprint_notes`, `power_specification_status`, and **all**
  `economics` are `NOT_CALIBRATED` (never fabricated, never `$0`).

---

## B. Patient-awareness boundary

The correct layering is preserved:
`PATIENT → CLINICAL SCHEDULER → SCANNER RESOURCE → SCANNER EQUIPMENT CAPABILITY`.

- `SCANNER_SCHEDULING_PATIENT_AWARE = YES` — patient traces carry
  `scan_start/scan_end`; `digital_twin_simulation_state.py` classifies
  `MOVING_TO_SCANNER`/`IN_SCANNER`/`COMPLETE` per patient from the precomputed
  schedule.
- `SCANNER_CATALOG_PATIENT_IDENTITY_AWARE = NO` — `ScannerCatalogModel` /
  `FacilityScannerInstance` carry no `patient_id`/name/room/calendar identity.
  Correct: equipment capability is patient-identity-independent.
- `SPECIFIC_SCANNER_IDENTITY_ASSIGNED_TO_PATIENT = PARTIAL` — the scheduler
  allocates a scanner *index/resource* (via `_allocate_earliest`, mapped to a
  stable `SCN-xxx` identity by `clinical_resource_identity`), but a patient is
  **not** bound to a specific *catalog model* identity (e.g. "this patient scans
  on the Biograph Vision"). Model identity is not consumed by the patient
  schedule today.

The scheduling/operations layer owns patient-awareness; the scanner equipment
catalog remains patient-identity-independent — as intended.

---

## C. Radionuclide / procedure / modality-awareness boundary

Chain: `PATIENT → RADIONUCLIDE → PROCEDURE/MODALITY → COMPATIBLE SCANNER CLASS → AVAILABLE SCANNER RESOURCE`.

- `SCANNER_MODALITY_AWARE = YES` — canonical `ScannerModality = Literal["PET","SPECT"]`
  (`clinical_resource_identity.py`); every catalog model carries `modality`;
  `models_of_modality()` selects by modality.
- `SCANNER_RADIONUCLIDE_AWARE = PARTIAL (modality-level only)` — the repository
  binds F-18 → PET and Tc-99m → SPECT (OG-SYNTH-1,
  `synthetic_radionuclide_source_capability`), and a catalog model records a
  free-text `supported_radionuclides_or_energy_range_kev`. There is **no**
  per-model radionuclide-compatibility matrix (e.g. "this specific PET model is
  validated for Ga-68 but not Rb-82"). Other cyclotron radionuclides
  (C-11/N-13/O-15/Ga-68/Cu-64/Zr-89/I-123/I-124) are reported as
  `SUPPORTED_BUT_NOT_CLINICALLY_MODALITY_CLASSIFIED`, never invented as
  scanner-compatible.
- `SCANNER_PROCEDURE_AWARE = PARTIAL` — models carry `protocol_families` +
  per-protocol acquisition minutes (procedure-duration awareness), but there is
  no procedure→model eligibility rule beyond duration lookup.
- `RADIONUCLIDE_TO_SCANNER_COMPATIBILITY_AUTHORITY = MODALITY_LEVEL` — enforced
  at the modality boundary, not the model boundary.

**PET ≠ SPECT is enforced, not assumed.** `check_modality_capacity`
(`oncology_pet_spect_scenario.py`) proves by construction that PET demand
consumes only PET scanner capacity and SPECT demand only SPECT capacity;
`ClinicalResourceInventory.scanners_of_modality` excludes untagged
(`modality=None`) scanners from *both* pools (no silent capacity sharing). A
SPECT-only scanner pool cannot satisfy PET demand and vice versa. This is a
generic PET/SPECT distinction and must not be over-reported as full
radionuclide-aware model authority.

`SCANNER_CAPABILITY → PATIENT DEMAND` is **not** created anywhere: excess
scanner capability is headroom (Section 42 / OG-SYNTH-1 preserved).

---

## D. Geometry / spatial-awareness boundary

Verified against current code (not future BIM doctrine).

- `SCANNER_MODEL_TO_FACILITY_OBJECT_BINDING = PARTIAL` — a `FacilityScannerInstance`
  carries an **untyped** `location_object_id: str | None` (default `None`,
  unvalidated). Separately, `canonical_spatial_authority.build_nuclear_engineering_objects`
  creates `PET_SCANNER`/`SPECT_SCANNER` canonical objects keyed by
  `pet_scanner_id`/`spect_scanner_id` and links back to the engineering
  authority by matching `engineering_object_id` **by convention** (matching id
  strings), not via a typed reference to a `ScannerCatalogModel`. Visual
  binding is export-time only (`openusd_spatial_adapter.export_registry_to_stage`
  `catalog_bindings` maps `mrtway_object_id → catalog_model_id` for USD asset
  resolution, not persisted into a facility model). `facility_engineering_model.py`
  has **no** scanner binding at all, and **nothing consumes**
  `FacilityScannerInstance.location_object_id`.
- `SCANNER_INSTANCE_HAS_POSITION = NOT_MODELED`;
  `SCANNER_INSTANCE_HAS_ORIENTATION = NOT_MODELED`;
  `SCANNER_INSTANCE_HAS_ROOM_IDENTITY = NOT_MODELED` — a scanner instance holds
  only a string reference. Any pose lives on the loosely-associated canonical
  object's `Transform`, created at default origin (0,0,0, zero rotation) and
  parented to the **floor**, not a room.
- `SCANNER_INSTANCE_AFFECTS_ROUTE_GEOMETRY = NO`;
  `SCANNER_MOVE_TRIGGERS_ROUTE_RECOMPUTATION = NO` — `scan_start/scan_end` are
  pure cycle-minute scheduling (`digital_twin_simulation_state` explicitly never
  recomputes the schedule). `canonical_spatial_authority.resolve_route` is a BFS
  over edge `length_m`, independent of any scanner `Transform`. Moving a scanner
  changes neither route distance nor scan timing today.
- Equipment `DIMENSIONS/FOOTPRINT/CLEARANCE/FLOOR_LOADING/SHIELDING room-fit =
  NOT_CALIBRATED / NOT_MODELED` — only free-text `dimensions_footprint_notes`;
  `EngineeringEnvelope` defaults every axis to `NOT_CALIBRATED`;
  `interactive_spatial_authoring.validate_drop_placement` hard-codes
  `fit_status="NOT_CALIBRATED"` and `service_clearance_status="NOT_CALIBRATED"`
  ("never fabricates clearance/fit").
- `SCANNER_PATIENT_ROUTE_BINDING = PARTIAL` — generic room-level patient→object
  resolution exists (`resolve_patient_spatial_object`,
  `resync_nuclear_trace_destination`) but resolves to the *patient's* room, not
  a scanner destination, and is not wired to the scan schedule. Scanner-specific
  spatial routing is not implemented.

The scanner authority is **not** geometrically aware merely because a generic
scanner room exists in a floor plan.

---

## E. Scanner throughput findings

- `MODEL_SPECIFIC_THROUGHPUT = PARTIAL (literature-calibrated acquisition minutes only)`.
  Each model carries `typical_acquisition_minutes_per_protocol`, and these
  differ per model (proof: Biograph Vision oncology 15 min vs Discovery MI
  20 min). This feeds real sizing via `required_scanner_count` /
  `required_scanner_counts_for_mixed_population` /
  `scanner_daily_capacity` (`oncology_pet_spect_scenario.py`), which follow the
  correct direction `PATIENT DEMAND → SCANNER WORKLOAD → REQUIRED COUNT` (never
  reversed) using a ceiling-division capacity formula.
- Missing (honestly): patient setup time, room turnover, downtime/maintenance
  downtime as *model-specific* fields; the Part 3D count gate uses a single
  study-level `PlannerAssumptions.scanner_cycle_min`/`scanner_availability_pct`
  rather than per-model acquisition minutes. So `patients/hour` and duty-cycle
  are `MODALITY/STUDY_LEVEL`, not per-model.

---

## F. Scanner site / power findings

- `MODEL_SPECIFIC_POWER = NOT_CALIBRATED` (`power_specification_status =
  "NOT_CALIBRATED"`, `active_power_kw`/`idle_power_kw = null`). No operating-duty
  energy model; annual energy is not derived from any nameplate value (correct).
- `MODEL_SPECIFIC_ROOM_REQUIREMENTS = NOT_CALIBRATED` — dimensions/footprint are
  free-text notes; no machine-usable envelope, clearance, weight, floor-loading,
  shielding, HVAC, or network authority per model.

---

## G. Scanner economics findings

- `MODEL_SPECIFIC_CAPEX = NOT_CALIBRATED`; `MODEL_SPECIFIC_OPEX = NOT_CALIBRATED`
  for every model (purchase_capex / annual_service_opex all `NOT_CALIBRATED`,
  test-locked by `test_no_model_specific_scanner_economics_invented`).
- The authoritative study-level anchor remains the generic
  `PlannerAssumptions.scanner_capex`. This review does **not** promote any
  generic anchor into manufacturer/model pricing (Section 13).

---

## H. Part 3D scanner-gate findings

- The Part 3D physical-feasibility scanner gate is **count-based and
  modality-agnostic**. `compute_clinical_resource_peak_occupancy`
  (`whole_oncology_four_architecture_optimization.py`) reads a single aggregate
  `nuclear.candidate.scanners` integer, computes peak scan occupancy via
  `_sweep_line_peak(scan_intervals)`, and sets
  `scanner_feasible = scanner_peak <= scanner_available`.
- `available scanner count` = `nuclear.candidate.scanners`
  (benchmark `BENCHMARK_SCANNERS = 6`, sourced through `ClinicalResourceInputs`
  with an auditable `resource_source`).
- `peak scanner occupancy` = sweep-line peak of realized `scan_start/scan_end`.
- `scanner feasible/infeasible` = derived (Part 3D), never hardcoded.
- **Scanner model identity does NOT affect the Part 3D gate today**, and the
  controlled 6-scanner benchmark is **not** a fictional model selection. This is
  honest and preserved unchanged by this review.

### H.1 Part 3D `feasible` derivation scope (honest correction)

Physically re-verified this review (against `whole_oncology_four_architecture_optimization.py`):
the Part 3D contract — `derive_physical_feasibility` →
`_physical_feasibility_result_fields` (which sets
`feasible = (physical_feasibility_status != "INFEASIBLE")`) — is consumed by the
**four canonical architecture evaluators**:

| Evaluator | Architecture(s) | `feasible` source |
|---|---|---|
| `evaluate_manual_conventional` | MANUAL_CONVENTIONAL | **DERIVED** via `_physical_feasibility_result_fields(_pf)` |
| `evaluate_automated_conventional` | AUTOMATED_CONVENTIONAL | **DERIVED** |
| `_evaluate_mrt_style_architecture` | HYBRID_MRT | **DERIVED** |
| `_evaluate_mrt_style_architecture` | MRT_DOMINANT | **DERIVED** |

`SCANNER_FEASIBILITY_DERIVED_IN_CANONICAL_FOUR = YES`.

**Two residual hardcoded `feasible=True` sites remain (disclosed, not silently
overstated):**

1. `evaluate_light_mrt_dominant` — a **separate Build 2R Light-MRT design-point
   variant** evaluator (distinct from the canonical four) returns
   `ArchitectureResult(architecture="MRT_DOMINANT", …, feasible=True)` with
   `feasible` **hardcoded**; it does **not** call `derive_physical_feasibility`.
   This is a Light-MRT-specific comparator whose lifecycle result is already
   explicitly labelled `NOT_YET_CALIBRATED` for OPEX; its physical-feasibility
   flag was not migrated onto the Part 3D contract.
2. `ZonalHybridPartitionCandidate` carries a `feasible=True` on the **candidate**
   dataclass (a partition-search intermediate, **not** an `ArchitectureResult`);
   the selected zonal-hybrid *result* is produced through the DERIVED
   `_evaluate_mrt_style_architecture` path.

`SCANNER_FEASIBILITY_DERIVED_IN_LIGHT_MRT_VARIANT = NO (hardcoded)`.

This review is **documentation-only** and makes **no engine change**; migrating
the Light-MRT-dominant variant (and, if desired, the zonal-hybrid candidate
pre-screen) onto the shared Part 3D contract is recorded as a **narrow, non-Part-3E-blocking**
closure (see Section J, gap 7). It does not affect the canonical four-architecture
feasibility gate, and it does not affect Part 3E scanner quantity/modality
readiness.

---

## I. Part 3E readiness matrix (Section 51)

| Dimension | Status |
|---|---|
| Scanner inventory / model identity | **READY** |
| PET/SPECT modality authority | **READY** |
| Radionuclide compatibility | PARTIAL (modality-level) |
| Procedure compatibility | PARTIAL (protocol-duration only) |
| Patient scheduling | **READY** (patient-aware scheduler) |
| Specific scanner assignment (resource) | **READY** (resource index → `SCN-xxx`) |
| Specific scanner **model** assignment to patient | PARTIAL |
| Scanner count sizing | **READY** (`required_scanner_count`, per-modality) |
| Part 3D `feasible` derivation (canonical four) | **READY** (derived via `derive_physical_feasibility`) |
| Part 3D `feasible` derivation (Light-MRT variant / zonal candidate) | PARTIAL (hardcoded `feasible=True`; narrow non-blocking closure — Section H.1) |
| Scanner throughput | PARTIAL (literature acquisition minutes) |
| Equipment dimensions | NOT_CALIBRATED |
| Room / site requirements | NOT_CALIBRATED |
| Position / orientation | NOT_MODELED |
| Patient-route binding | PARTIAL (generic room-level) |
| Service-route binding | NOT_MODELED |
| Power | NOT_CALIBRATED |
| Cooling / HVAC | NOT_MODELED |
| Shielding / site planning | NOT_CALIBRATED |
| Existing-vs-new status | **READY** (`ScannerAssetStatus`, `new_purchase_candidate`, `add_proposed_resources`) |
| Commercial status | **READY** (incl. `LEGACY_INSTALLED_BASE`) |
| CapEx | NOT_CALIBRATED (generic study anchor available) |
| Installation / site-prep CapEx | NOT_CALIBRATED |
| Maintenance / service OPEX | NOT_CALIBRATED |
| Energy OPEX | NOT_CALIBRATED |
| BIM crosswalk readiness | PARTIAL (fields identified below; no ingestion) |
| What-If readiness | PARTIAL (generic add/move/remove exists; scanner-specific spatial recompute NOT_MODELED) |

### Part 3E blocking test (Section 52)

- `PART_3E_SCANNER_QUANTITY_SELECTION_READY = YES`
- `PART_3E_SCANNER_MODALITY_SELECTION_READY = YES`
- `PART_3E_SCANNER_MODEL_SELECTION_READY = NO` — model-specific
  economics/power/geometry are `NOT_CALIBRATED`/`NOT_MODELED`; models are
  `NOT_YET_RANKABLE` beyond modality + acquisition-minute class. This is an
  acceptable, honest Phase 1 outcome (Sections 25, 53): **Phase 1 ready with
  class/modality scanner authority; model-specific scanner optimization
  deferred.**

### Part 3E model eligibility (Section 31, audit classification)

| Model | PART_3E_ELIGIBILITY |
|---|---|
| GE Discovery MI (PET) | `ELIGIBLE_NEW` / `NOT_YET_RANKABLE` |
| Siemens Biograph Vision (PET) | `ELIGIBLE_NEW` / `NOT_YET_RANKABLE` |
| Siemens Symbia Pro.specta (SPECT) | `ELIGIBLE_NEW` / `NOT_YET_RANKABLE` |
| GE NM/CT 870 DR (SPECT) | `ELIGIBLE_NEW` / `NOT_YET_RANKABLE` |
| GE NM/CT 860 (SPECT) | `ELIGIBLE_NEW` / `NOT_YET_RANKABLE` |
| Philips BrightView XCT (SPECT) | `ELIGIBLE_EXISTING_ONLY` (legacy; not a new-purchase candidate) |

---

## J. Remaining scanner gaps

1. Model-specific economics (CapEx/install/service/energy) — `NOT_CALIBRATED`
   (OG-SCN-1). Requires defensible per-model procurement/service evidence.
2. Model-specific power + operating-duty energy model — `NOT_CALIBRATED`.
3. Model-specific room requirements / envelope / clearance / weight / floor
   loading / shielding / HVAC — `NOT_CALIBRATED` / `NOT_MODELED`.
4. Scanner instance position/orientation/room identity — `NOT_MODELED`; scanner
   move does not recompute routes/timing.
5. Per-model radionuclide/procedure compatibility beyond PET/SPECT modality —
   `NOT_MODELED`.
6. Part 3D count gate is a single aggregate count (not split PET vs SPECT) — the
   *sizing layer* separates PET/SPECT, but the four-architecture feasibility gate
   aggregates. Not blocking for Part 3E Phase 1 (quantity+modality selection uses
   the sizing layer); documented for completeness.
7. **Part 3D `feasible`-derivation coverage (Section H.1):** the **canonical four**
   architecture evaluators derive `feasible` from the Part 3D contract, but the
   separate `evaluate_light_mrt_dominant` **variant** and the
   `ZonalHybridPartitionCandidate` **candidate** type still carry a hardcoded
   `feasible=True`. Narrow, non-blocking closure (migrate the variant/candidate
   onto `derive_physical_feasibility`); does not affect the canonical gate or
   Part 3E scanner quantity/modality readiness. **No engine change made in this
   review.**

None of these are Phase 1 blockers for scanner **quantity** or **modality**
selection.

---

## K. Future seams (documented, NOT implemented here)

- **BIM crosswalk (Section 33/49):** `SCANNER MODEL → EQUIPMENT REQUIREMENTS →
  CANONICAL FACILITY OBJECT → BIM OVERLAY/CROSSWALK → SPATIAL FEASIBILITY`. The
  future crosswalk will need, per scanner: stable equipment ID
  (`FacilityScannerInstance.scanner_id`), `catalog_model_id`, room ID, position,
  orientation, footprint/envelope, clearance envelope, service requirements —
  of which only the two IDs and an untyped `location_object_id` exist today.
  Imported objects may later be retained/overridden/replaced/removed/reclassified;
  stable engineering IDs survive the crosswalk. **No BIM ingestion built here.**
- **Operations (Section 34):** `PATIENT/CALENDAR DEMAND → SCANNER WORKLOAD →
  SCANNER ASSIGNMENT → OPERATING SCHEDULE`. The scanner authority is reusable by
  the Operations layer. **Reconciliation note:** a real long-horizon operational
  planning authority (`long_horizon_operational_planning.py`) already exists and
  already binds scanners into a per-date master plan (see Section N below); this
  review neither re-implements nor redesigns it. The full Hospital Master Calendar
  / Operations seam audit is Section N.

---

## L. Decision & exact physical git state

- `SCANNER_AUTHORITY_REVIEW_RESULT = B (READY_WITH_DOCUMENTED_LIMITATIONS)`
- `ENGINE_CODE_CHANGED = NO`
- `MODEL_SPECIFIC_SCANNER_CLOSURE_REQUIRED = NO`
- `READY_FOR_PART_3E_PHASE_1 = YES` (class/modality authority)

Because the audit establishes that scanner **count + modality** are sufficient
for Part 3E Phase 1 while **model-level** geometry/economics/throughput remain
incomplete, the correct outcome is **PART 3E PHASE 1 READY WITH CLASS/MODALITY
SCANNER AUTHORITY; MODEL-SPECIFIC SCANNER OPTIMIZATION = DEFERRED** — a valid
review-only outcome (Section 53). No scanner engine code is modified.

Files created by this build:
- `SCANNER_AUTHORITY_REVIEW_PART_3E_READINESS.md` (this document)
- `test_scanner_authority_review.py` (focused review test)

Authority docs updated: `MRT_PHARMA_AUTHORITY_INDEX.md`,
`MRT_PHARMA_OPEN_GAPS.md` (OG-SCN-1 refined), `MRT_PHARMA_PRODUCT_DOCTRINE.md`
(scanner doctrine), `MRT_PHARMA_BUILD_LEDGER.md` (current uncommitted build).

**No commit. No push. No stage.**

---

## M. Cross-equipment OPEX driver review (Sections 13A–13T)

**Nature of this section:** OPEX *evidence / driver audit* only. No new OPEX
engine is built here; no annual dollar value is fabricated because equipment
specifications exist. The governing distinction is preserved throughout:

```
EQUIPMENT SPECIFICATION  ≠  ANNUAL OPEX
SPECIFICATIONS → PHYSICAL OPEX DRIVERS → OPERATING DUTY/UTILIZATION
              → SITE-SPECIFIC UNIT COSTS → ANNUAL OPEX COMPONENTS
OPEX_annual = OPEX_spec_derived + OPEX_commercial + OPEX_site_specific
```

Provenance is tracked **separately** for the PHYSICAL DRIVER and the MONETARY
UNIT COST: a manufacturer spec may establish power/flow/interval without
establishing annual dollars, so the monetary result may carry a weaker evidence
basis than the physical driver (Section 13D/13P).

### M.1 Evidence hierarchy actually present in the repository (Section 13D)

MRT Pharma already carries a canonical calibration/provenance vocabulary — no
competing hierarchy is created here. Observed status tokens in the repo:

- Equipment catalogs (`field_provenance[*].calibration_status`):
  `manufacturer_calibrated` > `literature_calibrated` > `modeled` >
  `not_calibrated`.
- Economic/revenue authorities (`patient_economics.py`, `equal_budget.py`):
  `PAYMENT_CALIBRATED` / `USER_SUPPLIED` > `CONTROLLED_*_ASSUMPTION` /
  `CONTROLLED_SCENARIO_ASSUMPTION` > `NOT_CALIBRATED`.

Mapped to the Section 13D reference ladder
(`SITE_CALIBRATED > MANUFACTURER_SPECIFIED > COMMERCIAL_QUOTE/CONTRACT >
LITERATURE_DERIVED > MODELED_ESTIMATE > CONTROLLED_ASSUMPTION >
NOT_CALIBRATED/NOT_AVAILABLE`), the repo's existing tokens are conceptually
equivalent; **no new hierarchy is required.**

### M.2 What physical OPEX drivers actually exist (by equipment class)

**Scanners** (`scanner_equipment_catalog.json`, all six models):
- `power_specification_status = NOT_CALIBRATED`; `active_power_kw = null`;
  `idle_power_kw = null` on **every** model → **no connected-load, no operating,
  no standby power evidence.**
- `typical_acquisition_minutes_per_protocol` **is** present (a duty/workload
  driver: scan minutes per protocol family) → scan-hours/year is derivable from
  patient/protocol demand, but no power to convert it to energy.
- All `economics[*]` (`purchase_capex`, `annual_service_opex`) = `NOT_CALIBRATED`.
- Per Section 13G: `CONNECTED_LOAD_AVAILABLE = NO` and
  `ANNUAL_ENERGY_OPEX_CALIBRATED = NO`. `NAMEPLATE × 8760` is expressly avoided
  (there is no nameplate to misuse). No model-specific annual OPEX is inferred
  from the generic `PlannerAssumptions.scanner_capex` anchor (Section 13F).

**Cyclotrons** (`cyclotron_equipment_catalog.json`, PETtrace 8xx / IBA Cyclone):
- Manufacturer-calibrated **physical/workload** drivers present:
  `proton_energy_mev`, `proton_current_ua`, `production_cycle_minutes_by_
  radionuclide`, and per-radionuclide EOB performance records
  (`normalized_eob_activity_mbq`). These are **workload drivers**, not dollars
  (Section 13H).
- **Absent** from the catalog: electrical demand (kW), magnet/RF load, cooling-
  water demand, chiller load, target/foil/ion-source consumable rates, vacuum
  maintenance, QC-consumable rates, preventive/corrective service, waste-handling
  rates. → cyclotron energy/consumable/service OPEX = `NOT_CALIBRATED`.
- Utilization *is* derivable (Section 13I): the patient-aware batch-planning →
  required-EOB → production-cycle chain (`cyclotron_production_windows`,
  `cycle_relative_production_requirement`, `equal_budget.py` capacity resolver)
  yields production-cycles/day and beam-on-minutes/day. The DEMAND → CYCLES
  direction is preserved; CAPACITY → DEMAND is **not** introduced.
- Annual cyclotron OPEX is **not** inferred from EOB production activity alone
  (activity is a workload driver, not a dollar value — Section 13H).

**Radionuclide generators** (`generator_equipment_catalog.json`, Mo-99→Tc-99m:
Curium TechneLite, Curium Ultra-TechneKow FM, GE Drytec):
- Literature-calibrated **physical** drivers present: `useful_life_days = 14`,
  `elution_efficiency_fraction = 0.85`, `max_elutions_per_day = 2`,
  `nominal_reference_activity_options_mbq`, `requires_electrical_power = false`.
- All `economics[*]` (`purchase_capex`, `replacement_cost_per_cycle`,
  `annual_maintenance_opex`) = `NOT_CALIBRATED`.
- Generator commercial behaviour is **recurring replacement**, not permanent
  CapEx (Section 13J): the useful-life/replacement-interval driver exists, so
  the *replacement schedule* (generators/year) is derivable in **units** from
  Tc-99m demand → required activity → elution requirement → useful-life; only the
  per-generator **procurement dollar** is missing. Existing generator decay
  physics is **not modified** (Section 13K).

### M.3 Duty-cycle and monetary-unit-cost authorities (Sections 13E/13N)

- **Duty-cycle authority:** cyclotron = present (production-cycle minutes +
  patient-aware batch planning); scanner = partial (acquisition minutes present,
  but no power to apply them to energy); generator = present (elution/useful-life
  schedule).
- **Local utility price:** an `electricity_cost_per_kwh` tariff concept already
  exists and is reused across `infrastructure_opex.py`, `decision_pipeline.py`,
  `architecture_report.py`, and `mrt_transport_energy_maintenance_authority.py`
  (`MRT_ELECTRICITY_TARIFF_USD_PER_KWH`, $0.12–0.18/kWh) — classified
  `CONTROLLED_ASSUMPTION`, **not** manufacturer-specified, and never hardcoded as
  universal equipment economics (Section 13N). It is a valid *site unit cost*
  awaiting a *physical consumption* it can multiply.
- **Energy-kWh fields in `architecture_report.py`**
  (`annual_scanner_energy_kwh`, `annual_cyclotron_energy_kwh`) are **caller-
  supplied inputs passed straight through** — they are **not** derived from any
  scanner/cyclotron nameplate power or duty cycle (no such power exists in the
  catalogs). They must therefore be treated as `MODELED_ESTIMATE / EXTERNALLY_
  SUPPLIED`, never promoted to `MANUFACTURER_CALIBRATED` (Section 13P).
- **Service/maintenance price:** no real commercial service price exists for
  scanners, cyclotrons, or generators. Any maintenance-%-of-CapEx figure in the
  repo (e.g. legacy guideway 3%/yr) is reported as `CONTROLLED_ASSUMPTION`, not
  `MANUFACTURER_SPECIFIED` (Section 13L).

### M.4 Cross-equipment OPEX driver table (Section 13S)

| Equipment class | Model / source | Physical OPEX driver | Physical-driver evidence status | Duty-cycle authority | Monetary unit-cost authority | Annual OPEX status | Part 3E readiness | Limitation |
|---|---|---|---|---|---|---|---|---|
| Scanner (SPECT) | Siemens Symbia Pro.specta | acquisition min/protocol | `SPECIFICATION_AVAILABLE` (minutes); power `NOT_CALIBRATED` | Partial (scan-hours from demand) | `NOT_CALIBRATED` (no service/energy $) | `NOT_CALIBRATED` | PARTIAL | No power kW → no energy $; no service $ |
| Scanner (SPECT/CT) | GE NM/CT 870 DR | acquisition min/protocol | power `NOT_CALIBRATED` | Partial | `NOT_CALIBRATED` | `NOT_CALIBRATED` | PARTIAL | Same as above |
| Scanner (SPECT/CT) | GE NM/CT 860 | acquisition min/protocol | power `NOT_CALIBRATED` | Partial | `NOT_CALIBRATED` | `NOT_CALIBRATED` | PARTIAL | Same as above |
| Scanner (SPECT/CT) | Philips BrightView XCT (legacy) | acquisition min/protocol | power `NOT_CALIBRATED` | Partial | `NOT_CALIBRATED` | `NOT_CALIBRATED` | PARTIAL | Legacy installed base; no pricing |
| Scanner (PET/CT) | GE Discovery MI | acquisition min/protocol | power `NOT_CALIBRATED` | Partial | `NOT_CALIBRATED` | `NOT_CALIBRATED` | PARTIAL | Same as above |
| Scanner (PET/CT) | Siemens Biograph Vision | acquisition min/protocol | power `NOT_CALIBRATED` | Partial | `NOT_CALIBRATED` | `NOT_CALIBRATED` | PARTIAL | Same as above |
| Cyclotron | GE PETtrace 890 (representative, calibrated) | cycle-min, beam energy/current, EOB record | `MANUFACTURER_SPECIFIED` (workload) | Present (cycles/day, beam-on min) | `NOT_CALIBRATED` (no kW/consumable/service $) | `NOT_CALIBRATED` | PARTIAL | Workload known; power/consumable/service $ absent |
| Cyclotron | GE PETtrace 800 (legacy, multi-isotope) | supported radionuclides; cycle-min modeled | isotope list `MANUFACTURER`; EOB `NOT_CALIBRATED` | Present (cycle-min = modeled default) | `NOT_CALIBRATED` | `NOT_CALIBRATED` | PARTIAL | EOB yields null; energy/consumable $ absent |
| Cyclotron | IBA Cyclone KIUBE (representative, calibrated) | cycle-min, beam energy, EOB record | `MANUFACTURER_SPECIFIED` (workload) | Present | `NOT_CALIBRATED` | `NOT_CALIBRATED` | PARTIAL | Same as PETtrace 890 |
| Generator | Curium TechneLite (Mo-99→Tc-99m, representative) | useful-life 14 d, elution eff 0.85, 2 elutions/day | `LITERATURE_DERIVED` (physical) | Present (replacement schedule in units) | `NOT_CALIBRATED` (no procurement $) | `NOT_CALIBRATED` | PARTIAL | Replacement schedule derivable in units, not $ |
| Generator | Curium Ultra-TechneKow FM | useful-life 14 d, elution eff 0.85 | `LITERATURE_DERIVED` | Present | `NOT_CALIBRATED` | `NOT_CALIBRATED` | PARTIAL | Same as above |
| Generator | GE Drytec | useful-life 14 d, elution eff 0.85 | `LITERATURE_DERIVED` | Present | `NOT_CALIBRATED` | `NOT_CALIBRATED` | PARTIAL | Same as above |

### M.5 Part 3E OPEX readiness (Sections 13Q/13R)

- `SCANNER_OPEX_PART3E_READINESS = PARTIAL` (duty exists; power + $ absent)
- `CYCLOTRON_OPEX_PART3E_READINESS = PARTIAL` (utilization exists; power/consumable/service $ absent)
- `GENERATOR_OPEX_PART3E_READINESS = PARTIAL` (replacement schedule in units; procurement $ absent)
- `CAN_PART3E_COMPARE_SCANNER_OPEX = PARTIAL` (only duty/workload comparable, not $)
- `CAN_PART3E_COMPARE_CYCLOTRON_OPEX = PARTIAL` (utilization comparable, not $)
- `CAN_PART3E_COMPARE_GENERATOR_OPEX = PARTIAL` (replacement units comparable, not $)

**`CROSS_EQUIPMENT_OPEX_AUTHORITY_REQUIRED = YES`** — a *future, narrow*
Equipment OPEX Authority is warranted, but is **not** built in this Scanner
Authority Review (no tiny additive closure is required for Part 3E Phase 1
readiness, which selects equipment *class/quantity/modality*, not $ OPEX). The
future authority would, per equipment class:
1. accept a **physical consumption** driver (scanner scan-hours; cyclotron
   beam-on hours + consumable counts; generator replacement count) computed from
   the existing patient-aware demand/utilization chain;
2. multiply by a **separately-provenanced site unit cost** (reusing the existing
   `electricity_cost_per_kwh` tariff; new `$/service`, `$/generator`,
   `$/consumable` unit costs, each labelled `CONTROLLED_ASSUMPTION` until a
   commercial quote calibrates them);
3. compose `OPEX_annual = OPEX_spec_derived + OPEX_commercial +
   OPEX_site_specific` with **mixed-evidence** provenance (the weakest component
   governs the composite; the strongest never promotes the whole — Section 13P);
4. distinguish **existing** vs **new** equipment OPEX (Section 13O) without
   assuming newer = cheaper and without forcing replacement.

It must **not** back-derive annual dollars from EOB activity, nameplate × 8760,
or a fixed %-of-CapEx presented as manufacturer-specified.

### M.6 Final-report additions (Section 13T)

- `SCANNER_OPEX_DRIVER_AUTHORITY = PARTIAL` (acquisition minutes only; power NOT_CALIBRATED)
- `SCANNER_ANNUAL_OPEX_STATUS = NOT_CALIBRATED`
- `CYCLOTRON_OPEX_DRIVER_AUTHORITY = PARTIAL` (beam/cycle/EOB workload drivers manufacturer-calibrated; energy/consumable/service drivers absent)
- `CYCLOTRON_ANNUAL_OPEX_STATUS = NOT_CALIBRATED`
- `GENERATOR_OPEX_DRIVER_AUTHORITY = PARTIAL` (useful-life/elution literature-derived)
- `GENERATOR_ANNUAL_OPEX_STATUS = NOT_CALIBRATED`
- `SCANNER_ENERGY_OPEX_CALCULABLE = NO` (no connected/operating power; `annual_scanner_energy_kwh` is caller-supplied, not duty-derived)
- `CYCLOTRON_ENERGY_OPEX_CALCULABLE = NO` (no electrical demand in catalog; `annual_cyclotron_energy_kwh` is caller-supplied, not duty-derived)
- `GENERATOR_REPLACEMENT_OPEX_CALCULABLE = PARTIAL` (replacement schedule derivable in UNITS from useful-life + Tc-99m demand; procurement $ NOT_CALIBRATED)
- `SERVICE_CONTRACT_EVIDENCE_STATUS = NOT_CALIBRATED` (no commercial service price for scanner/cyclotron/generator; any %-of-CapEx is CONTROLLED_ASSUMPTION)
- `LOCAL_UTILITY_PRICE_AUTHORITY = CONTROLLED_ASSUMPTION` (`electricity_cost_per_kwh` ~$0.12–0.18/kWh, reused; awaiting a physical consumption to multiply)
- `SCANNER_OPEX_PART3E_READINESS = PARTIAL`
- `CYCLOTRON_OPEX_PART3E_READINESS = PARTIAL`
- `GENERATOR_OPEX_PART3E_READINESS = PARTIAL`
- `CAN_PART3E_COMPARE_SCANNER_OPEX = PARTIAL`
- `CAN_PART3E_COMPARE_CYCLOTRON_OPEX = PARTIAL`
- `CAN_PART3E_COMPARE_GENERATOR_OPEX = PARTIAL`
- `CROSS_EQUIPMENT_OPEX_AUTHORITY_REQUIRED = YES` (future narrow authority described in M.5; NOT built in this review)

No annual dollar value is reported for any equipment class: the physical
repository and evidence chain do not support one. **No engine code changed. No
OPEX engine built. No commit. No push. No stage.**

### M.7 Correction: a schedule-derived equipment ENERGY authority already exists

Physically re-verified this review (`equipment_energy_opex.py` +
`test_equipment_energy_opex.py`): an earlier draft understated the repository by
saying scanner/cyclotron energy is "only a caller-supplied pass-through, not
duty-derived." That is **corrected** here.

`equipment_energy_opex.py` is a **schedule-derived equipment energy authority**:

- **Duty IS derived, not supplied.** `derive_scanner_state_minutes` reads the
  ACTUAL persistent scanner scan intervals from the long-horizon plan
  (`assignments_for_resource`); `derive_cyclotron_state_minutes` reads the ACTUAL
  irradiation cycles (`production_plan_for_cyclotron`). Non-active time is filled
  by an explicitly-labelled `PROJECT_ASSUMPTION` operating-state policy
  (STANDBY/OFF), never real hospital calibration. This IS the
  `CALENDAR/UTILIZATION → EQUIPMENT DUTY` binding — it exists, contrary to the
  earlier "documented, not built" phrasing.
- **Money is honestly gated by calibration.** `compute_equipment_daily_energy`
  only contributes kWh for a state whose power spec is an energy-usable
  *measurement* (`is_energy_usable_measurement`); everything else is preserved as
  `uncalibrated_state_minutes` (duration kept, never silently zeroed). Because the
  **scanner catalog carries no power spec**, every scanner resolves to
  `calibration_status = "NOT_CALIBRATED"`, `calculated_energy_kwh = 0.0`, with all
  time in `uncalibrated_state_minutes`. So the review's *economic* conclusion is
  unchanged and, if anything, strengthened: scanner energy $ is honestly
  uncalibrated **by construction**, not by omission.
- **Comparability is protected.** `_economic_comparability_status` downgrades an
  uncalibrated component to `NOT_COMPARABLE_DUE_TO_UNCALIBRATED_ENERGY` (never a
  silent $0 advantage). `MRT_ENERGY_STATUS = ENERGY_SPECIFICATION_NOT_CALIBRATED`.
- **No double-count.** `reconcile_generic_energy_line_with_schedule_derived` /
  `build_ledger_energy_component` REPLACE the generic annual-kWh line with the
  schedule-derived figure only when `CALIBRATED_FOR_ENERGY`; otherwise the generic
  fallback is retained (tagged `GENERIC_ENERGY_FALLBACK_USED`), never both added.

**Corrected readiness statements:**

- `SCANNER_ENERGY_DUTY_DERIVATION = IMPLEMENTED` (scan-minutes from the actual plan).
- `SCANNER_ENERGY_OPEX_CALCULABLE = NO` — because the **power kW** input is
  `NOT_CALIBRATED` per model, not because the duty/authority is missing.
- `CYCLOTRON_ENERGY_DUTY_DERIVATION = IMPLEMENTED` (irradiation-minutes from the plan).
- `CYCLOTRON_ENERGY_OPEX_CALCULABLE = NO` — same reason (no electrical-demand kW
  in the cyclotron catalog).
- The still-missing evidence is narrowly **per-model power kW** (and per-model
  service $), not the energy computation engine. This refines — does not remove —
  the future Equipment OPEX Authority described in M.5 (its energy-duty layer
  already exists; it needs the power/unit-cost calibration inputs).

**No engine code changed by this review.**

---

## N. Hospital Master Calendar / Operations seam (Sections 26, 26A–26I)

**Nature of this section:** AUDIT → DOCUMENT → PRESERVE SEAM → IDENTIFY GAPS →
STOP. This review does **not** implement or redesign the approximately
six-month Hospital Master Calendar, does **not** create a second calendar
engine, does **not** replace existing calendar files, does **not** redesign
production scheduling, and does **not** begin the Operations build (Section 26H).
It records the scanner-side information the calendar authority requires and the
seam that binds them.

> **Reconciliation:** an earlier draft of this review (Section K) described the
> six-month master calendar as "not built here" in a way that implied it did not
> yet exist. That is **corrected** here: a real long-horizon operational planning
> authority **already exists** and already binds scanners into a per-date master
> plan. The doctrine that this *Scanner Review* must not build/redesign it is
> preserved; the factual claim that no such authority exists is withdrawn.

### N.0 The six-month horizon doctrine is preserved

`SIX_MONTH_HORIZON_DOCTRINE_PRESERVED = YES`. The intended operational planning
horizon remains approximately six months and is **not** reduced to "one
representative day" or "one scanner schedule" (Section 26D). The existing
representative-day engine remains a legitimate computational building block; it
does not replace the long-horizon authority.

Physical evidence: `long_horizon_operational_planning.py` line 1
(*"Long-Horizon Patient-Aware Operational Planning (day/week/month/six-month)"*)
and `run_long_horizon_operational_plan` docstring
(*"builds the six-month (or any explicit-date-range) master plan by orchestrating
the existing validated day engine once per operating date — never a second
scheduler"*). The horizon is **data-driven** via
`OperatingCalendar(planning_start_date, planning_end_date, operating_weekdays,
non_operating_dates)` — there is **no** hardcoded "six month" constant, so any
explicit date range (including six months) is supported without a magic number.

### N.1 Calendar / operations authority file inventory (Section 26E)

`CALENDAR_FILES_IDENTIFIED = YES` — the repository has **more than one**
scheduling/planning authority; they are cleanly layered (a long-horizon
orchestrator that reuses one validated day engine — never a competing
scheduler).

| File | Current role | Patient-aware | Production-aware | Scanner-aware | Planning horizon | Relationship to future six-month Hospital Master Calendar |
|---|---|---|---|---|---|---|
| `long_horizon_operational_planning.py` | **Long-horizon operational master-plan authority.** `OperatingCalendar`, `CyclotronCalendar`, `ResourceAvailabilityCalendar` consumer, `run_long_horizon_operational_plan` (iterates `operating_dates()` → `run_operating_day_plan` per date+radionuclide), `LongHorizonMasterPlan`, `PatientOperationalPlan`. | **YES** (`CanonicalOperationalPatientRecord`: internal id, external ref, COMMITTED/FORECAST, `scheduled_date`, admin window, `existing_scanner_appointment_minute`) | **YES** (binds patient → `cyclotron_id`, `batch_id`, `production_window_id`, `release_time_minutes`) | **YES** (`PatientOperationalPlan.scanner_resource_id` + `scan_window_minutes`; `validate_no_double_resource_assignment` for SCANNER) | Explicit multi-day / **six-month** (date-range driven) | **This is the operational master-calendar authority.** The future Hospital Master Calendar is the maturation of this file, not a replacement. |
| `operating_day_scheduler.py` | Single-operating-day resource allocator (`schedule_operating_day`). Assigns per-patient `scan_start`/`scan_end` + `scanner_resource_index`. | Yes (ordinal `patient_id`) | Partial (consumes `BatchRelease`) | **YES** (allocates scanner slot, tracks occupancy/utilization) | **One** operating day (`operating_day_minutes` default 1080.0) | Reusable per-date building block invoked once per operating date by the long-horizon authority. |
| `production_clinical_schedule.py` | Production→clinical bridge; `build_production_clinical_schedule` → `ProductionClinicalPatientTrace`. | Yes (`patient_id`) | **YES** (radionuclide/cyclotron/batch/window/release) | **YES** (`scan_start`/`scan_end`, `scanner_resource_index`) | One operating day | Supplies the per-day production+clinical+scanner trace the calendar aggregates. |
| `clinical_resource_identity.py` | Scanner **resource identity** + `ResourceAvailabilityCalendar` (per-date `unavailable_by_date`, `active_resource_ids_for_date`). | No | No | **YES** (SCN-xxx identity, optional room/modality; per-date availability) | Multi-day (availability keyed by `date`) | Owns the persistent scanner resource identities and per-date availability the calendar references. |
| `scanner_catalog.py` | Scanner equipment authority; `FacilityScannerInstance` (`scanner_id`, `catalog_model_id`, `modality`, `operating_state`, `location_object_id`). | No | No | **YES** (equipment/asset identity only) | None (static catalog) | Provides equipment identity/capability the calendar's scanner resources map to. |
| `design_horizon_planning.py` | **Multi-YEAR capital** expansion planner (`run_native_design_horizon_planning`, year-by-year demand trajectory + expansion actions). | No (demand trajectory, not patients) | No | No | Multi-**year** capital | **Distinct** from the operational six-month calendar — a capital-planning horizon, not an operations calendar. Documented to avoid conflation. |

Do not conflate the **multi-year capital** `design_horizon_planning.py` with the
**operational six-month** `long_horizon_operational_planning.py`.

### N.2 Scanner calendar requirements (Section 26A)

What the Hospital Master Calendar needs to know for each scanner resource, and
whether the repository currently provides it:

| Scanner calendar field | Status | Physical evidence |
|---|---|---|
| Scanner resource ID | **IMPLEMENTED** | `ClinicalResource.resource_id` (`SCN-xxx`); `FacilityScannerInstance.scanner_id` |
| Scanner catalog model ID | **IMPLEMENTED** | `FacilityScannerInstance.catalog_model_id` → `ScannerCatalogModel` |
| PET/SPECT modality | **IMPLEMENTED** | `ClinicalResource.modality` / `FacilityScannerInstance.modality` (`ScannerModality`) |
| Room ID | **PARTIAL** | `ClinicalResource.room_id`/`floor_id`/`building_id` + `FacilityScannerInstance.location_object_id` — optional, `None` by default, not always populated |
| Availability calendar | **IMPLEMENTED (date-level)** | `ResourceAvailabilityCalendar.unavailable_by_date` + `active_resource_ids_for_date`; UNAVAILABLE is excluded from that date, **never deleted** (identity preserved) |
| Operating hours | **PARTIAL (facility-wide, coarse)** | `operating_day_minutes` (default 1080.0) at day/horizon level; `Scanner.daily_capacity(operating_hours_day)`. **No per-scanner operating-hours window.** |
| Planned maintenance windows | **PARTIAL** | Whole-**date** unavailability via `unavailable_by_date`; `FacilityScannerInstance.operating_state` includes a `MAINTENANCE` enum value. **No intra-day maintenance time-window (start/end minutes).** |
| Unplanned downtime | **NOT_MODELED** | No stochastic breakdown; `ResourceAvailabilityCalendar` is explicitly deterministic-only |
| Patient assignment | **IMPLEMENTED** | `PatientOperationalPlan.scanner_resource_id` per committed patient/day |
| Scan start | **IMPLEMENTED** | `PatientOperationalPlan.scan_window_minutes[0]` ← `PatientSchedule.scan_start` |
| Scan completion | **IMPLEMENTED** | `PatientOperationalPlan.scan_window_minutes[1]` ← `PatientSchedule.scan_end` |
| Acquisition duration | **PARTIAL** | Study-level `scanner_service_minutes` drives the scheduler; per-model `typical_acquisition_minutes_per_protocol` exists in the catalog but is not the day-engine gate driver (Section E) |
| Turnover / setup duration | **NOT_MODELED** | No distinct turnover/setup field; only the single scan-service duration |
| Resource occupancy | **IMPLEMENTED** | Sweep of `scan_start/scan_end`; `scanner_utilization_pct`; `validate_no_double_resource_assignment` |
| Patient arrival / departure time | **PARTIAL** | Injection/uptake/scan windows exist per patient; there is no separate scanner-room arrival/return event distinct from the scan window |

No missing calendar data is fabricated (Section 26A).

### N.3 Patient-aware calendar vs equipment-catalog boundary (Section 26B)

Preserved. The **calendar/scheduling layer is patient-aware**
(`CanonicalOperationalPatientRecord`, `PatientOperationalPlan` know patient
identity, appointment, radionuclide, administration activity, injection/uptake
windows, assigned scanner, assigned room, batch linkage, transport timing),
while the **equipment catalogs are NOT patient-identity databases**:

- `SCANNER CATALOG ≠ PATIENT-IDENTITY DATABASE` — `ScannerCatalogModel` /
  `FacilityScannerInstance` carry no `patient_id`/name (test-locked, Section B).
- `CYCLOTRON CATALOG ≠ PATIENT-IDENTITY DATABASE` and
  `GENERATOR CATALOG ≠ PATIENT-IDENTITY DATABASE` — same boundary; equipment
  authorities carry capability/availability/capacity/physical-requirements/
  operating-state, never patient identity.

The patient-aware calendar and batch-planning authorities bind patient demand to
equipment **requirements**; the equipment authorities stay capability-focused.

### N.4 Calendar production traceability (Section 26C)

`PATIENT_TO_SCANNER_TRACEABILITY = YES` — `PatientOperationalPlan` binds one
committed patient to `scanner_resource_id` + `scan_window_minutes` on a specific
`day`.

`PATIENT_TO_BATCH_TO_SCANNER_TRACEABILITY = YES` — the full chain is physically
present in `ProductionClinicalPatientTrace` and surfaced through
`PatientOperationalPlan`:

```
PATIENT (patient_id / external_patient_reference)
 → RADIONUCLIDE (radionuclide)
 → ASSIGNED PRODUCTION SOURCE (assigned_cyclotron_id, radiopharmacy_origin_id)
 → PHYSICAL PRODUCTION BATCH (batch_id, production_window_id, window start/end)
 → RELEASE / ACTIVITY (batch_release_time_minutes)
 → TRANSPORT RESOURCE (payload_id, delivery_job_id, transport_arrival_time_minutes)
 → INJECTION (injection_window_minutes)
 → UPTAKE (uptake_window_minutes)
 → SCANNER (scanner_resource_id, scan_window_minutes)
 → CLINICAL COMPLETION (completed_within_operating_day)
```

`SCANNER_CALENDAR_IDENTITY_PRESERVED = YES` — persistent `SCN-xxx` identity is
resolved from the day-engine allocation index via
`daily_summary.scanner_resource_id_by_index[trace.scanner_resource_index]`
(never fabricated). Scanner identity **can** currently be inserted into the
calendar traceability chain. No missing calendar orchestration is implemented in
this review.

Honest limitation: "uptake" is a **fixed service duration** in the scheduler, not
a radionuclide-specific biodistribution/decay physiology model; the decay/uptake
physics authorities exist elsewhere and are not the driver of `scan_start`. Scan
timing is causally downstream of a *simplified* production→transport→injection→
uptake chain (Section 9 / Section 26C), which is correct to disclose rather than
overstate.

### N.5 Scanner downtime / maintenance future binding (Section 26F)

`SCANNER COUNT ≠ SCANNERS AVAILABLE AT EVERY MOMENT` is preserved. The calendar
can already represent, at **date** granularity:

- scanner **available** / **occupied** — `active_resource_ids_for_date` +
  occupancy sweep;
- scanner **unavailable** / **planned maintenance** — `unavailable_by_date`
  (whole day) + `operating_state = MAINTENANCE`.

`SCANNER_DOWNTIME_AUTHORITY = PARTIAL` — **date-level** planned unavailability is
modeled; **intra-day** maintenance/service windows, commissioning/replacement
periods with start/end minutes, and unplanned-downtime distributions are
`NOT_MODELED`. No scanner downtime distribution is invented in this review
(Section 26F). This matters for Part 3E vs Operations: Part 3E may select the
equipment composition; Operations must later confirm that composition stays
operationally sufficient across the horizon once intra-day downtime is modeled.

### N.6 OPEX / calendar connection (Section 26G)

The direction is preserved: `PATIENT / OPERATIONAL DEMAND → UTILIZATION → OPEX`
(never `OPEX assumptions → PATIENT DEMAND`).

`CALENDAR_TO_SCANNER_UTILIZATION_BINDING = YES` — scanner operating hours /
scan-hours are derivable from the calendar's realized `scan_window_minutes` and
`scanner_utilization_pct` across operating dates.

`CALENDAR_TO_SCANNER_OPEX_DRIVER_BINDING = PARTIAL` — the calendar supplies the
**physical duty** (scan-hours; cyclotron beam-on hours; generator replacement
frequency), and (correction, see Section M.7) the
`CALENDAR/UTILIZATION → EQUIPMENT DUTY` binding is in fact **built** for energy:
`equipment_energy_opex.py` derives scanner scan-minutes / cyclotron irradiation-
minutes from the actual long-horizon plan. What remains blocked is only the
**monetary** conversion: scanner/cyclotron **power kW** is `NOT_CALIBRATED`, so
that authority correctly returns `calculated_energy_kwh = 0.0` /
`calibration_status = NOT_CALIBRATED` for those classes (never a fabricated $),
and service $ is `NOT_CALIBRATED`. **No annual OPEX is calculated here** — the
missing input is per-model power/unit-cost, not the duty binding
(Sections 26G, M.3/M.5, M.7).

### N.7 This build does not implement the six-month calendar (Section 26H)

Explicitly honored:
`OPERATIONS_CALENDAR_IMPLEMENTATION_STARTED = NO`. No second calendar engine, no
replacement of existing calendar files, no production-scheduling redesign, no
long-horizon optimization, no live ARIA scheduling, no Operations build. This
review audited, documented, preserved the seam, identified gaps, and stops.

### N.8 Required calendar readiness output (Section 26I)

- `HOSPITAL_MASTER_CALENDAR_AUTHORITY_IDENTIFIED = YES` (`long_horizon_operational_planning.py`)
- `SIX_MONTH_HORIZON_DOCTRINE_PRESERVED = YES`
- `SCANNER_CALENDAR_BINDING = IMPLEMENTED (date + per-patient scan window + persistent SCN-xxx identity)`
- `PATIENT_TO_SCANNER_TRACEABILITY = YES`
- `PATIENT_TO_BATCH_TO_SCANNER_TRACEABILITY = YES`
- `SCANNER_AVAILABILITY_CALENDAR = IMPLEMENTED (date-level; ResourceAvailabilityCalendar)`
- `SCANNER_MAINTENANCE_CALENDAR = PARTIAL (date-level unavailability + MAINTENANCE operating_state; no intra-day window)`
- `SCANNER_DOWNTIME_AUTHORITY = PARTIAL (deterministic date-level only; no intra-day / unplanned downtime)`
- `CALENDAR_TO_SCANNER_UTILIZATION_BINDING = YES`
- `CALENDAR_TO_SCANNER_OPEX_DRIVER_BINDING = PARTIAL (duty derivable; monetary units NOT_CALIBRATED — no OPEX computed)`
- `CALENDAR_FILES_IDENTIFIED = YES` (`long_horizon_operational_planning.py`, `operating_day_scheduler.py`, `production_clinical_schedule.py`, `clinical_resource_identity.py`, `scanner_catalog.py`; distinct capital planner `design_horizon_planning.py`)
- `OPERATIONS_CALENDAR_IMPLEMENTATION_STARTED = NO`
- `FUTURE_OPERATIONS_CALENDAR_CLOSURE_REQUIRED = YES` (intra-day scanner downtime/maintenance windows, per-scanner operating hours, scanner-specific spatial routing, and the equipment-OPEX monetary layer remain for the future Operations build — not this review)

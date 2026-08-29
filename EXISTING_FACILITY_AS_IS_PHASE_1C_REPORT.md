# EXISTING FACILITY / AS-IS DIGITAL TWIN — PHASE 1C IMPLEMENTATION REPORT

**Build:** Phase 1C — Facility Engineering Object Model & Completeness Closure.
**Type:** Narrow, additive strengthening of the existing Phase 1B normalization module + one new
test file + this report. No new parallel facility/spatial/equipment/routing/simulation/scenario
engine. Pre-simulation only. No commit / no push.
**Governing principle honored:** the PHYSICAL repository is authoritative; every reused authority
was verified at HEAD, not assumed from session memory.

---

## 0. MANDATORY PHYSICAL PRECHECK (Sec 1)

```
STARTING_HEAD               = 4bd9930032a3b8f85cbf61e25c61ab1fa0bda056
STARTING_BRANCH             = main
ORIGIN_MAIN                 = 4bd9930032a3b8f85cbf61e25c61ab1fa0bda056
STARTING_DIVERGENCE         = 0 / 0  (local main == origin/main)
WORKING_TREE_CLEAN          = YES (only the untracked Phase 1A seam report; no tracked mods at start)
STAGED_FILES                = (none)
UNSTAGED_FILES              = (none, at start)
UNTRACKED_FILES             = AS_IS_DIGITAL_TWIN_PHASE_1A_SEAM_REPORT.md
PHASE_1B_PRESENT_IN_HISTORY = YES (4bd9930 == HEAD)
PART3D_PRESENT_IN_HISTORY   = YES (07e861d, in ancestry)
PART3E_PRESENT_IN_HISTORY   = YES (a6facf9)
PART3E_1_PRESENT_IN_HISTORY = YES (93bf687)
PART3E_2_PRESENT_IN_HISTORY = YES (2f22bf3)
PHASE_1A_SEAM_REPORT_PRESENT= YES (untracked, the known predecessor artifact)
UNRELATED_FILES_PRESENT     = NO
READY_FOR_ASIS_PHASE_1C     = YES
```

The one untracked file at start was the Phase 1A seam report — a known predecessor investigation
artifact — so the Sec 1 STOP condition did not apply. It was **not** deleted, staged, reset,
reverted, or checked out.

---

## 1. AUTHORITY-FIRST OWNERSHIP MAP (Sec 2) — REUSE vs NARROW-NEW

Every concept Phase 1C strengthens was traced to its physical owner before writing code. The rule
was: **extend/reuse where an authority exists; add ONE narrow companion only where a genuine gap
exists.**

| Concept | Physical owner (reused) | Phase 1C action |
|---|---|---|
| Facility hierarchy | `canonical_spatial_authority.SpatialObjectRegistry` (`children_of`/`by_type`, `parent_object_id`, stable `mrtway_object_id`) | REUSE — added a read-only **view** (`AsIsFacilityHierarchyView`), no second registry |
| Clinical-space classification | function was **conflated into** geometry `object_type`; `facility_engineering_model.SpaceFunctionAssignment` is assignment/suitability-oriented | **GAP → narrow-new** `AsIsSpaceClassificationBinding` on a separate axis |
| Engineering-object identity | `FacilityCyclotronInstance` / `FacilityGeneratorInstance` / `FacilityScannerInstance` (`instance_id` + `catalog_model_id`) | REUSE unchanged |
| Equipment ↔ space binding | single scalar `CanonicalSpatialObject.engineering_object_id` | REUSE — added a queryable **read-model** (`AsIsEquipmentSpatialBinding`) over the scalar |
| Connectivity / topology | `canonical_spatial_authority.ConnectivityGraph` / `SpatialEdge` / `resolve_route` | REUSE — added a topology-only **view** (`AsIsConnectivityView`); routing physics NOT invoked |
| Evidence / provenance (4 axes) | `cyclotron_catalog.ProvenancedField`; Phase 1B `AsIsFieldEvidence` mirrors it | REUSE unchanged |
| Evidence conflict | `engineering_evidence.EngineeringEvidenceConflict` (RAG/claim-oriented) | **GAP → narrow-new** AS-IS-facing `AsIsEvidenceConflict` (mirrors its shape; no competing repository) |
| Calibration / confidence | `SpatialStatus` (spatial), `CalibrationStatus` (equipment), `EngineeringEnvelope` sentinels | REUSE — no new global enum |
| Completeness / readiness | Phase 1B `AsIsCompletenessAssessment` (sole owner) | EXTEND — added per-domain `AsIsDomainCompleteness` + distinct `AsIsReadinessGates` |
| Operational-resource identity | `clinical_resource_identity.ClinicalResource(Inventory)` (state separate in `live_operational_state`) | REUSE — added identity-only **placeholders** (`AsIsOperationalResourcePlaceholder`) |
| LOCKDOWN / What-If lineage | `lockdown_what_if_lineage_authority` | PRESERVED as a seam — no lineage created, authority NOT duplicated |

Transport route-time **physics** (`conventional_transport_authority`, `mrt_service_class_authority`,
`spatial_benchmark`) was deliberately **not** invoked — topology is data; travel time is downstream.

---

## 2. WHAT WAS BUILT (all additive to `existing_facility_asis_twin.py`)

### Facility hierarchy (Sec 5)
`AsIsFacilityHierarchyView` / `AsIsHierarchyNode` — an explicit, queryable view over the canonical
registry (FACILITY/BUILDING/FLOOR/ROOM levels, stable IDs, explicit parentage). `site_id`/`campus_id`
are surfaced as identity-only metadata (no campus layer is fabricated where none exists). Room
identity does not depend on geometry; facility identity does not depend on project/scenario identity.

### Clinical-space classification (Sec 6-7)
`AsIsClinicalSpaceClassification` (a superset adding `COMBINED_INJECTION_UPTAKE`, `GENERATOR_AREA`,
`CYCLOTRON_ROOM`, `CORRIDOR`, `ELEVATOR`, `STAIR`, `MECHANICAL`, `OUTPATIENT_ROOM`, `OTHER`,
`NOT_MODELED`, …) + `AsIsSpaceClassificationBinding(spatial_object_id → classification, status,
provenance)`. Classification is held on a **different axis** from geometry `object_type`. An
explicit input wins; otherwise it is derived only from an explicitly-supplied `room_function`; an
unknown function stays UNKNOWN and is **never** inferred from the room name/id. Known-geometry +
unknown-function remains legal.

### Engineering-object model + equipment binding (Sec 8-10)
`AsIsEquipmentSpatialBinding(equipment_instance_id, spatial_object_id|None, binding_status, source,
validation_status)` — a queryable read-model over the `engineering_object_id` scalar. Equipment
identity and placement are decoupled: an UNRESOLVED binding retains the full instance id; a future
drag/drop move changes the `spatial_object_id` without changing the `equipment_instance_id`; no
placement is fabricated and no identity is destroyed.

### Connectivity / topology + route readiness (Sec 11-12)
`AsIsConnectivityView` / `AsIsConnectivityLink` + `AsIsRouteReadiness`
(`TOPOLOGY_COMPLETE`/`TOPOLOGY_PARTIAL`/`TOPOLOGY_NOT_MODELED`). Built only from supplied routes.
Geometry completeness never implies connectivity. `route_distance_fabricated` and
`transport_time_calculated` are **always False** — no distance is computed from coordinates and no
travel time is calculated.

### Operational-resource placeholders + MRT control (Sec 13-14)
`AsIsOperationalResourcePlaceholder` for SCANNER / PRODUCTION_CYCLOTRON / GENERATOR / STAFFING /
TRANSPORT / MRT_CARRIER_ENDPOINT — identity seams only, `operational_state_reconstructed=False`.
`mrt_infrastructure_count` counts real MRT_* objects in the registry (0 when none);
`benchmark_mrt_inserted` and `mrt_required_for_engineering_model_ready` are always False.

### Field evidence + evidence-conflict authority (Sec 15-17)
`AsIsEvidenceConflict` (candidate values + sources + `resolution_status` + `impact_on_readiness`).
An independently-sourced `AsIsConflictingEvidenceInput` that disagrees with the primary room fact
becomes an **UNRESOLVED** conflict: both candidates preserved, no silent overwrite, no last-write-
wins, no auto-resolution; the room's classification binding is marked CONFLICTED and a
BLOCKS_SIMULATION provenance gap is emitted (readiness reduced).

### Domain completeness + readiness gates (Sec 18-20)
`AsIsDomainCompleteness` for all 13 twin domains (status + known/unknown/conflict/blocking/
nonblocking counts + readiness impact) — never one collapsed count. `AsIsReadinessGates` exposes the
FIVE distinct, monotonic gates (NORMALIZED → STRUCTURALLY_RECONSTRUCTABLE → ENGINEERING_MODEL_PARTIAL
→ READY_FOR_OPERATIONAL_STATE_RECONSTRUCTION → READY_FOR_BASELINE_SIMULATION). A later gate is never
True unless every earlier one is.

### Out-of-scope disclosure flags (Sec 21-24)
Added to the result: `patient_state_ingestion_implemented`, `appointment_ingestion_implemented`,
`scanner_calendar_ingestion_implemented`, `staff_roster_ingestion_implemented`,
`production_schedule_ingestion_implemented`, `live_equipment_state_ingestion_implemented`,
`asis_baseline_simulation_implemented`, `simulation_run_during_phase_1c`, `lockdown_authority_duplicated`
(all False) and `existing_lockdown_lineage_seam_preserved` (True).

### No-silent-benchmark governor (Sec 24) — strengthened
No benchmark geometry / room function / equipment / MRT infrastructure / route topology / clinical
counts / patient population / staffing is ever inserted. Missing facts remain MISSING / NOT_MODELED /
NOT_CALIBRATED / PARTIAL.

---

## 3. CONTROLS (Sec 25-29) + CONTRADICTION CONTROL (Sec 17)

### CONTROL A — STRUCTURED FACILITY WITH PARTIAL MODEL (Sec 25)
Facility hierarchy explicit & queryable; some functions known + at least one UNKNOWN; one placed +
one unplaced equipment; partial topology; provenance preserved; calibration independent; **no
benchmark fill**. GEOMETRY=COMPLETE while CLINICAL_SPACE_CLASSIFICATION=PARTIAL;
ENGINEERING_OBJECT_IDENTITY=COMPLETE while EQUIPMENT_PLACEMENT=PARTIAL; CONNECTIVITY_TOPOLOGY=PARTIAL.

### CONTROL B — NO MRT (Sec 26)
```
MRT_INFRASTRUCTURE_COUNT                  = 0
BENCHMARK_MRT_INSERTED                    = NO
MRT_REQUIRED_FOR_ENGINEERING_MODEL_READY  = NO
```
The engineering-object model reaches ready **without any MRT**.

### CONTROL C — GEOMETRY COMPLETE / FUNCTION UNKNOWN (Sec 27)
GEOMETRY=COMPLETE while CLINICAL_SPACE_CLASSIFICATION=PARTIAL/NOT_MODELED — statuses are **not
coupled**. Every classification stays UNKNOWN; geometry `object_type` stays generic `ROOM`.

### CONTROL D — EQUIPMENT INVENTORY WITHOUT PLACEMENT (Sec 28)
ENGINEERING_OBJECT_IDENTITY=COMPLETE/PARTIAL while EQUIPMENT_PLACEMENT=PARTIAL. Unplaced equipment is
**not deleted**; its instance + model identity survive; bindings are UNRESOLVED with `spatial_object_id
= None`. Move-invariant confirmed (identity stable regardless of placement).

### CONTROL E — PARTIAL TOPOLOGY (Sec 29)
```
GEOMETRY_STATUS                       = COMPLETE
CONNECTIVITY_TOPOLOGY_STATUS          = PARTIAL
SUPPLIED_CONNECTION_COUNT             = 1
SUPPLIED_CONNECTIONS_PRESERVED        = YES
MISSING_CONNECTIONS_INFERRED          = NO
FABRICATED_PORTALS_INSERTED           = NO
FABRICATED_VERTICAL_CONNECTIONS_INSERTED = NO
BENCHMARK_TOPOLOGY_INSERTED           = NO
ROUTE_DISTANCE_FABRICATED             = NO
TRANSPORT_TIME_CALCULATED             = NO
NORMALIZATION_SUCCEEDED               = YES
BASELINE_SIMULATION_READY             = NO
```
Known coordinates are **not** equated with known connectivity; no route is constructed from
Euclidean distance.

### CONTRADICTION CONTROL (Sec 17)
```
CONFLICT_CREATED             = YES
CANDIDATE_VALUES_PRESERVED   = YES  (both STORAGE and PET_SCANNER_ROOM)
AUTO_RESOLUTION_OCCURRED     = NO   (resolution_status UNRESOLVED, selected_value None)
READINESS_IMPACT             = REDUCES_READINESS (non-zero)
```
Room identity survives; the classification binding is CONFLICTED (not overwritten);
`engineering_object_model_ready` becomes False while `structural_reconstruction_ready` remains True.

---

## 4. OUT-OF-SCOPE STATUS (Sec 21-23)

```
OPERATIONAL_STATE_RECONSTRUCTION_IMPLEMENTED = NO
PATIENT_STATE_INGESTION_IMPLEMENTED          = NO
APPOINTMENT_INGESTION_IMPLEMENTED            = NO
SCANNER_CALENDAR_INGESTION_IMPLEMENTED       = NO
STAFF_ROSTER_INGESTION_IMPLEMENTED           = NO
PRODUCTION_SCHEDULE_INGESTION_IMPLEMENTED    = NO
LIVE_EQUIPMENT_STATE_INGESTION_IMPLEMENTED   = NO
ASIS_BASELINE_SIMULATION_IMPLEMENTED         = NO
SIMULATION_RUN_DURING_PHASE_1C               = NO
LOCKDOWN_CREATED                             = NO
WHAT_IF_CREATED                              = NO
LOCKDOWN_AUTHORITY_DUPLICATED                = NO
EXISTING_LOCKDOWN_LINEAGE_SEAM_PRESERVED     = YES
```
No four-architecture simulation, Part 3D feasibility, or Part 3E optimization is called from Phase 1C
normalization. The intended sequence remains a seam: Evidence → Normalized AS-IS objects →
Validation/gaps → Operational-state reconstruction → Baseline simulation → LOCKDOWN → What-If.

---

## 5. VERIFICATION

Run with `/opt/anaconda3/bin/python -m pytest`.

| Suite | Result |
|---|---|
| `test_asis_twin_phase1c.py` (new: 22 controls/invariants incl. A–E + contradiction) | **22 passed** |
| `test_asis_twin_phase1b.py` (Phase 1B preservation — unchanged) | **21 passed** |
| `test_canonical_spatial_authority_closure.py` + `test_cyclotron_catalog_foundation.py` + `test_build3b_production_authority.py` | **131 passed** |
| `test_facility_engineering_model.py` + `test_canonical_facility_geometry_spatial_authority.py` | **67 passed** |
| `test_pet_spect_generator_native_authority_completion.py` + `test_scanner_authority_review.py` | **72 passed** |

No existing test was modified. `existing_facility_asis_twin.py` is imported **only** by the two AS-IS
twin test files, so the change has zero production ripple. `test_existing_facility_retrofit.py` runs a
heavy pre-existing simulation and does **not** import the changed module (its runtime is unrelated to
this build).

---

## 6. FILES

Changed / added (all within the workspace):

- `existing_facility_asis_twin.py` — **modified** (additive Phase 1C read-models, result fields,
  seam flags, and `ingest_structured_facility` wiring; +785 lines). No Phase 1B contract changed;
  all new inputs/fields are optional and defaulted.
- `test_asis_twin_phase1c.py` — **new** test file (Sec 25-29 controls + contradiction control +
  classification/binding/readiness/domain/out-of-scope invariants).
- `EXISTING_FACILITY_AS_IS_PHASE_1C_REPORT.md` — this report.

Explicitly NOT modified: `equal_budget.py`, `hybrid_optimization.py` (decay math),
`canonical_spatial_authority.py`, the equipment catalogs / `*_equipment_catalog.json`,
`lockdown_what_if_lineage_authority.py`, and any Part 3B/3C/3D/3E authority.

---

## 7. LIMITATIONS

- MANUAL / PROJECT-SUPPLIED STRUCTURED INGESTION only (no IFC/BIM/CAD/PDF/image/OCR/intelligent
  reconstruction/live feeds).
- Phase 1C strengthens the canonical AS-IS model but remains **pre-simulation**: no routing physics,
  no operational-state reconstruction, no baseline simulation, no LOCKDOWN/What-If lineage.
- Missing facts are reported per-domain; controlled benchmark facts are never substituted.
- The result is a strengthened ENGINEERING twin snapshot, not an operational digital twin.

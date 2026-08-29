# EXISTING FACILITY / AS-IS DIGITAL TWIN — PHASE 1B IMPLEMENTATION REPORT

**Build:** Phase 1B — Canonical Starting State & Structured Ingestion Foundation.
**Type:** Narrow, additive extension + one new orchestration module + one test file + this report.
**Governing principle honored:** the PHYSICAL repository is authoritative; every reused authority
was verified at HEAD, not assumed from session memory. No commit / no push.

---

## 0. MANDATORY PHYSICAL PRECHECK (Sec 1)

```
STARTING_HEAD               = 2f22bf3fae5f0636771b44d4f26ea3e74e248f6f
STARTING_BRANCH             = main
ORIGIN_MAIN                 = 2f22bf3fae5f0636771b44d4f26ea3e74e248f6f
STARTING_DIVERGENCE         = 0 / 0  (local main == origin/main)
WORKING_TREE_CLEAN          = NO (only untracked artifacts; no tracked modifications at start)
STAGED_FILES                = (none)
UNSTAGED_FILES              = (none)
UNTRACKED_FILES             = AS_IS_DIGITAL_TWIN_PHASE_1A_SEAM_REPORT.md
PART3D_PRESENT_IN_HISTORY   = YES (07e861d)
PART3E_PRESENT_IN_HISTORY   = YES (a6facf9)
PART3E_1_PRESENT_IN_HISTORY = YES (93bf687)
PART3E_2_PRESENT_IN_HISTORY = YES (2f22bf3 == HEAD)
PHASE_1A_SEAM_REPORT_PRESENT= YES (untracked, the direct predecessor artifact)
UNRELATED_FILES_PRESENT     = NO (the only untracked file is the Phase 1A seam report)
READY_FOR_ASIS_PHASE_1B     = YES
```

The one untracked file is the Phase 1A seam report — the direct input to THIS build, not an
unrelated file — so the Sec 1 STOP condition did not apply. No reset / revert / checkout / delete
was performed.

---

## 1. PHASE 1A FINDINGS VERIFIED (Sec 2), NOT ASSUMED

Every dependency was physically re-checked at HEAD. All were TRUE; none required a STOP.

| # | Finding | Verified at |
|---|---|---|
| A | `DevelopmentContext = Literal["RETROFIT","GREENFIELD"]` = CapEx attribution only | wo4a `:138`, `mrt_auxiliary_systems_authority :1250` |
| B | `StudyScope = Literal["CAPITAL_PLANNING","OPERATIONAL_ONLY"]` = study objective only | `study_scope.py :33` |
| C | No `EXISTING_FACILITY_AS_IS` / `ProjectStartingState` exists in code | repo-wide grep (only a Part 3E.2 test referencing a report string) |
| D | Canonical spatial authority separates geometry / engineering objects / bindings | `canonical_spatial_authority.CanonicalSpatialObject` (`object_type`, `transform`, `engineering_object_id`) |
| E | Manual canonical spatial builders exist | `build_facility_hierarchy` / `add_building` / `add_floor` / `add_room` |
| F | Most import modes are wrappers/proofs, not production parsers | `normalize_blank_manual_import` + `_finalize_normalized_import` |
| G | IFC/Bentley/USD are proof/prototype, not real ingestion | Phase 1A Sec 7 classification (preserved as flags) |
| H | LOCKDOWN / What-If lineage authority exists separately | `lockdown_what_if_lineage_authority` (`create_first_lockdown`, `promote_what_if_to_lockdown`) |
| I | Benchmark fallbacks exist and must not become AS-IS truth | `ClinicalResourceInputs` 6/6/12, `spatial_benchmark` geometry/production |

---

## 2. WHAT WAS BUILT

### A. ONE orthogonal starting-state authority (Sec 3-4)

Added to the existing canonical project-configuration owner (`StudyConfiguration`), exactly per the
Phase 1A insertion-point recommendation — **not** buried in the new module.

```python
# whole_oncology_four_architecture_optimization.py
ProjectStartingState = Literal["GREENFIELD", "RETROFIT", "EXISTING_FACILITY_AS_IS"]

@dataclass(frozen=True)
class StudyConfiguration:
    ...
    project_starting_state: ProjectStartingState = "RETROFIT"   # additive, opt-in AS-IS
```

- **Orthogonal** to `DevelopmentContext` (CapEx attribution) and `StudyScope` (study objective).
- `EXISTING_FACILITY_AS_IS` does **not** imply RETROFIT/GREENFIELD CapEx, MRT installation, capital
  intervention, or a What-If state. An AS-IS facility MAY later branch into a Retrofit study.
- **Backward compatible:** the field is defaulted, read by no existing consumer, and every existing
  `StudyConfiguration(...)` call site (Part 3D/3E/3E.1/3E.2, benchmark/retrofit/greenfield) is
  unchanged. No historical `DevelopmentContext` value was reinterpreted.

### B. New orchestration / normalization module (Sec 5-21)

`existing_facility_asis_twin.py` — a thin authority that CONSUMES existing canonical layers and
normalizes already-structured, project-supplied facts into them. It creates no competing spatial,
equipment, routing, simulation, or scenario engine.

- **ONE ingestion path** (Sec 6): `ingest_structured_facility(AsIsStructuredFacilityInput, *,
  project_starting_state="EXISTING_FACILITY_AS_IS")`. Manual/project-supplied structured facts only.
  No IFC/DWG/DXF/PDF/image/OCR/point-cloud/GIS parser; no automatic room/wall/equipment recognition;
  no intelligent reconstruction.
- **Structured DTOs** (Sec 9-14, temporary ingestion contracts, stable IDs): `AsIsFacilityIdentityInput`,
  `AsIsBuildingInput`, `AsIsFloorInput`, `AsIsRoomInput`, `AsIsEquipmentInput`,
  `AsIsEquipmentPlacementInput`, `AsIsRouteOrConnectivityInput`, `AsIsStructuredFacilityInput`.
- **Normalization flow** (Sec 7): structured input → evidence/validation → canonical spatial objects
  (`build_facility_hierarchy`/`add_building`/`add_floor`/`add_room`) + canonical engineering objects
  (`FacilityCyclotronInstance`/`FacilityGeneratorInstance`/`FacilityScannerInstance`, validated via
  `catalog.by_id`) + bindings (`engineering_object_id` on the room object) → normalized read model
  (`normalize_blank_manual_import` + `validate_spatial_registry`) → completeness/gap assessment.
- **Geometry ≠ twin** (Sec 8): room geometry, room clinical function, and equipment assignment are
  kept as distinct facts. An unknown-function room is a generic `ROOM` (function-neutral), never
  guessed from its name.
- **Field-level evidence** (Sec 15-16): `AsIsFieldEvidence(fact, provenance, calibration, confidence)`
  keeps ORIGIN and CALIBRATION on independent axes (mirrors the canonical `ProvenancedField`; no new
  provenance hierarchy invented). `AsIsProvenance` reuses the repository's existing origins
  (`PROJECT_SUPPLIED`/`FACILITY_SUPPLIED`/`FACILITY_DERIVED`/`MEASURED`/`EXTERNAL_SOURCE`/`INFERRED`/
  `CONTROLLED_ASSUMPTION`/`MISSING`).
- **Completeness / gap authority** (Sec 18-19): `AsIsCompletenessGap` (gap_id, domain, fact, status,
  severity, reason, object_id, provenance) across domains FACILITY_IDENTITY / GEOMETRY / ROOM_FUNCTION
  / EQUIPMENT_IDENTITY / EQUIPMENT_PLACEMENT / CONNECTIVITY / OPERATIONAL_RESOURCES / PROVENANCE /
  CALIBRATION / SIMULATION_READINESS; deterministic `AsIsCompletenessStatus`
  (STRUCTURALLY_COMPLETE / PARTIALLY_COMPLETE / INSUFFICIENT_FOR_SIMULATION). Never a single boolean.
- **Simulation readiness** (Sec 21): conservative — Phase 1B always returns
  `NOT_READY_FOR_SIMULATION`; no simulation is run.
- **Top-level result** (Sec 20): `ExistingFacilityAsIsTwinResult` (starting state, facility identity,
  canonical spatial registry reference, normalized import, engineering objects, field evidence,
  completeness, readiness, limitations, downstream seam flags). Named as an ENGINEERING twin
  snapshot, explicitly not the full operational twin.

### C. Hard governor — NO silent benchmark fallback (Sec 17)

Missing facility facts stay MISSING / NOT_MODELED / NOT_CALIBRATED. Clinical resource counts and
patient population are always reported as MISSING gaps — the controlled 6/6/12 / benchmark
population is never substituted. Absent connectivity is a CONNECTIVITY gap, never a benchmark
distance. `benchmark_cyclotron_inserted` is always `False`.

---

## 3. NEGATIVE CONTROLS

### Sec 27 — NO CYCLOTRON

```
FACILITY_CYCLOTRON_COUNT   = 0
BENCHMARK_CYCLOTRON_INSERTED = NO
```
No canonical `CYCLOTRON` object is created; a facility supplying no cyclotron keeps that as a
legitimate AS-IS fact.

### Sec 28 — UNKNOWN ROOM FUNCTION

Room `"PET Suite"` supplied with geometry but no function: geometry remains usable
(`dimensions.is_fully_known() == True`), `object_type` stays generic `ROOM` (function is **not**
inferred from the name), and a ROOM_FUNCTION completeness gap is produced.

### Sec 29 — EQUIPMENT LOCATION UNKNOWN

```
EQUIPMENT_IDENTITY_PRESERVED                   = YES
EQUIPMENT_MODEL_IDENTITY_PRESERVED             = YES
EQUIPMENT_PLACEMENT_STATUS                     = UNRESOLVED
FABRICATED_ROOM_ASSIGNMENT                     = NO
BENCHMARK_PLACEMENT_INSERTED                   = NO
EQUIPMENT_PLACEMENT_GAP_CREATED                = YES
INGESTION_SUCCEEDED_WITH_UNRESOLVED_PLACEMENT  = YES
SIMULATION_READINESS_IMPACT                    = remains NOT_READY_FOR_SIMULATION (unchanged; gap noted)
```
Unknown equipment location is treated as a distinct fact from unknown equipment identity: the
catalog instance and model identity survive; no room/nearest/benchmark placement is fabricated;
ingestion succeeds with an EQUIPMENT_PLACEMENT gap. An invalid REQUIRED reference (unknown
`catalog_model_id`, placement to a nonexistent room, room on a nonexistent floor) is the only thing
that raises `AsIsIngestionError`.

---

## 4. OUT-OF-SCOPE STATUS FLAGS (Sec 22-25)

```
OPERATIONAL_STATE_RECONSTRUCTION_IMPLEMENTED    = NO
LOCKDOWN_CREATED                                = NO
WHAT_IF_CREATED                                 = NO
IFC_REAL_HOSPITAL_INGESTION_IMPLEMENTED         = NO
BENTLEY_ITWIN_REAL_HOSPITAL_INGESTION_IMPLEMENTED = NO
PDF_IMAGE_RECONSTRUCTION_IMPLEMENTED            = NO
CAD_DWG_DXF_PARSER_IMPLEMENTED                  = NO
OPENUSD_REAL_HOSPITAL_INGESTION_IMPLEMENTED     = NO
SYNTHETIC_IFC_PROOF_EXISTS                      = YES
BENTLEY_ITWIN_PROOF_SEAM_EXISTS                 = YES
```

The future sequence is preserved as a seam, not bypassed:
Evidence → Normalized AS-IS objects → Validation/gaps → Operational-state reconstruction →
Baseline simulation → LOCKDOWN → What-If. Phase 1B establishes the first two stages plus the
gap report; it creates no lineage records and refers to `lockdown_what_if_lineage_authority` only
as a future downstream seam.

---

## 5. VERIFICATION

Run with `/opt/anaconda3/bin/python -m pytest`.

| Suite | Result |
|---|---|
| `test_asis_twin_phase1b.py` (new: 21 controls/invariants) | **21 passed** |
| `test_part3d_physical_feasibility_closure.py` + `test_part3e*` (3) | passed (within 424) |
| `test_canonical_spatial_authority_closure.py` + `test_canonical_facility_geometry_spatial_authority.py` | passed (within 424) |
| `test_cyclotron_catalog_foundation.py` + `test_build3b_production_authority.py` | passed (within 424) |
| Combined directly-affected regression batch | **424 passed** |
| `test_whole_oncology_four_architecture_optimization.py` + `test_full_operational_capital_qualification.py` | **237 passed, 1 skipped** |

No existing test was modified. The Part 3E.2 report-string assertion still passes (its report was
not modified by this build).

---

## 6. FILES

Changed / added (all within the workspace):

- `whole_oncology_four_architecture_optimization.py` — added `ProjectStartingState` Literal and the
  additive `StudyConfiguration.project_starting_state` field (default `"RETROFIT"`). No behavior
  change for existing consumers.
- `existing_facility_asis_twin.py` — NEW orchestration/normalization module (this build's core).
- `test_asis_twin_phase1b.py` — NEW test file (Sec 26-29 controls + orthogonality/backward-compat +
  governor invariants).
- `EXISTING_FACILITY_AS_IS_PHASE_1B_REPORT.md` — this report.

Explicitly NOT modified (Phase 1A Sec 24): `equal_budget.py`, `hybrid_optimization.py` (decay math),
`spatial_benchmark.py` transport physics, `canonical_spatial_authority.py` lockdown/what-if
mechanics, the `*_equipment_catalog.json` calibration data, and any Part 3B/3C/3D/3E authority.

---

## 7. LIMITATIONS

- MANUAL / PROJECT-SUPPLIED STRUCTURED INGESTION only. No file/drawing parsing of any kind.
- No operational-state reconstruction, no baseline simulation, no LOCKDOWN, no What-If.
- The result is an ENGINEERING twin snapshot, not an operational digital twin.
- Missing operational facts are reported as gaps; controlled benchmark facts are never substituted.

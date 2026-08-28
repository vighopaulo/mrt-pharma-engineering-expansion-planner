# MRT Pharma — Open Gaps Register

**Build:** MRT Pharma Authority Consolidation (governance / traceability).
**Purpose:** the single register of concerns that are **agreed / documented but
not fully implemented**, so no future build mistakes a `PLANNED_REQUIREMENT` for
an `IMPLEMENTED_REPOSITORY_AUTHORITY`.

Every gap below was verified against the physical repository. Each entry names:
the concern, its current honest status, what physically exists today, and what
"closed" would require. See `MRT_PHARMA_AUTHORITY_INDEX.md` for the canonical
authority each gap references.

> **Rule:** Never describe a `PLANNED_REQUIREMENT` as an
> `IMPLEMENTED_REPOSITORY_AUTHORITY`. A gap being listed here does not authorize
> closing it — closing a gap is a separate, explicitly-scoped build.

---

## Status legend

- `PLANNED` — agreed future behavior, no implementation.
- `PARTIAL` — partially implemented; a specific seam is open.
- `NOT_MODELED` — not represented in the repository at all.
- `DISCLOSED_SIMPLIFICATION` — a deliberate, documented modeling choice.

---

## Capital Project

### OG-CAP-1 — "NO BUILD" is not a first-class four-architecture option — PARTIAL
- **Today:** `equal_budget.py`'s MRT-investment search can conclude no MRT is
  needed and returns `candidate_identity="NO_BUILD_BASELINE"` (zero-backbone,
  `capex_used == 0.0`), test-locked in `test_build3a2_identity.py`. This is a
  **legacy Build-3A identity**, deliberately NOT one of the four canonical
  architectures (MANUAL_CONVENTIONAL / AUTOMATED_CONVENTIONAL / HYBRID_MRT /
  MRT_DOMINANT) in `whole_oncology_four_architecture_optimization.py`.
- **Closed would require:** representing "NO BUILD" / do-nothing as a first-class
  comparable option in the four-architecture engine (if that is ever desired).

### OG-CAP-2 — Composition optimizer — PLANNED
- **Today:** the four canonical architectures + the equal-budget search exist;
  there is no free "compose any subset of transport building blocks per service
  class and optimize" engine.
- **Closed would require:** a Part 3E-style composition optimizer. Explicitly out
  of scope for this and the Part 3D build.

---

## Operations

### OG-OPS-1 — Long-horizon plan → one-day execution seam — PARTIAL
- **Today:** `long_horizon_operational_planning.py` produces
  `DailyOperationalSummary`; `operational_day_orchestrator.py` executes a single
  day. The orchestrator does not yet consume `DailyOperationalSummary` as a
  direct input (self-disclosed bounded gap).
- **Closed would require:** wiring the daily summary as a direct orchestrator
  input.

---

## Patient source / ARIA

### OG-ARIA-1 — Live ARIA (and other vendor) integration — PLANNED / NOT_MODELED
- **Today:** `healthcare_integration.py` + `healthcare_adapters.py` provide a
  vendor-neutral adapter foundation with **synthetic** fixtures
  (`SYNTHETIC_TEST_FIXTURE`); `build_aria_fixture`/`ingest_aria_fixture`
  normalize into `CanonicalOperationalPatientRecord`. There is **no** network/
  credentials/API/FHIR/HL7 client. Explicitly `SECURITY_COMPLIANCE_NOT_IN_SCOPE`
  (not HIPAA-compliant). `VARIAN_ARIA` exists only as a `SourceSystem` tag.
- **Design intent:** ARIA-class systems remain the upstream system-of-record;
  MRT Pharma does not replace ARIA. Conceptual flow: ARIA → adapter → canonical
  operational patient → Operations digital twin.
- **Closed would require:** a real, authenticated, compliant vendor integration
  (out of scope here).

---

## Cyclotron / production

### OG-CYC-1 — Cyclotron Production Estimation Authority — PLANNED
- **Today:** a model × radionuclide pair that is SUPPORTED but whose
  manufacturer/site output is not calibrated returns `NOT_CALIBRATED` (e.g.
  `SUMITOMO_CYPRIS_MP_30` + F-18). There is **no** authority that produces a
  numerical `MODELED_ESTIMATE`.
- **Closed would require:** a future estimation authority with the evidence
  hierarchy `SITE_CALIBRATED > MANUFACTURER_CALIBRATED > MODELED_ESTIMATE >
  CONTROLLED_ASSUMPTION > NOT_AVAILABLE`. **Do not mark MODELED_ESTIMATE as
  implemented until such an authority physically exists.**

### OG-SYNTH-1 — Synthetic-patient source-capability constraint — PLANNED / PARTIAL
- **Today:** the CAPITAL PROJECT synthetic patient generator produces radionuclide
  demand **independently** of the scenario's selected production-source
  configuration. `oncology_pet_spect_scenario.build_representative_day_population`
  assigns the radionuclide purely by modality (PET → `PET_RADIONUCLIDE = "F-18"`,
  SPECT → `SPECT_RADIONUCLIDE = "Tc-99m"`);
  `inbound_patient_program.generate_synthetic_patient_population` stamps a
  caller-supplied radionuclide on every patient; and
  `patient_radionuclide_demand.PatientRadionuclideDemand` validates the
  radionuclide **only** against the canonical half-life/decay table
  (`load_radionuclide_half_lives`), not against any cyclotron/generator capability.
  There is **no** code path where changing the selected cyclotron or generator
  changes which radionuclides synthetic patients demand; a capability mismatch is
  surfaced only **downstream** at the feasibility stage
  (`NO_COMPATIBLE_SOURCE` / unmet). This decoupling is consistent with the
  test-locked "demand is upstream" doctrine
  (`test_excess_capacity_is_headroom_not_extra_patients`).
- **Doctrine (product doctrine §11A):** in NORMAL representative synthetic mode,
  synthetic radionuclide demand **should** be constrained to the **combined**
  capability of all selected production sources (cyclotron supported radionuclides
  ∪ generator supported radionuclides — e.g. Tc-99m admissible when a Mo-99/Tc-99m
  generator is present even though the cyclotron does not produce it). SUPPORTED ≠
  CALIBRATED: a supported radionuclide may constrain demand while its production
  output remains `NOT_CALIBRATED`. An OPTIONAL FUTURE STRESS-TEST mode may
  intentionally demand an unproducible radionuclide, in which case the system must
  expose `NO_COMPATIBLE_SOURCE` and must **never** silently alter patient demand
  to make the facility feasible.
- **Closed would require:** a narrow, explicitly-scoped engine build that derives
  the admissible synthetic radionuclide set from the selected cyclotron **and**
  generator capabilities and constrains the generator accordingly (plus the
  optional stress-test/requirement mode). This governance addendum does **not**
  modify the randomizer. **Do not describe this constraint as implemented until
  such a build exists.**

---

## Generator

### OG-GEN-1 — Ge-68 / Ga-68 generator pathway — NOT_MODELED / ABSENT
- **Today:** the generator catalog contains only Mo-99 → Tc-99m models
  (`CURIUM_TECHNELITE`, `CURIUM_ULTRA_TECHNEKOW_FM`, `GE_HEALTHCARE_DRYTEC`).
  Ge-68 and Ga-68 appear only as **cyclotron**-produced isotopes; there is no
  Ge-68/Ga-68 **generator** authority.
- **Closed would require:** a Ge-68/Ga-68 generator catalog + physics authority,
  if a generator Ga-68 pathway is ever needed. Reporting it absent is the correct
  current behavior — never fabricate one.

---

## Transport

### OG-TRN-1 — True free-roaming FLOOR_AGV_AMR — NOT_IMPLEMENTED
- **Today:** `transport_technology_authority.py` sets
  `FLOOR_AGV_AMR_IMPLEMENTATION_STATUS = "NOT_IMPLEMENTED"`; the legacy `AGV_AMR`
  economics are canonically the rail-guided `RGHT` class. There is no floor
  graph / path-planning / collision / charging model.
- **Closed would require:** a separately-calibrated free-roaming floor-navigation
  model. Must never be silently upgraded to reuse RGHT/PTS/MRT assumptions.

### OG-TRN-2 — RP-PTS per-sample trajectory — PARTIAL
- **Today:** RP-PTS mission-cycle **timing** is implemented
  (`compute_rp_pts_mission_cycle`); `production_trajectory_authority.py` has no
  dedicated RP-PTS per-sample trajectory sampler (MRT/RGHT/PTS/porter/patient do).
- **Closed would require:** an RP-PTS trajectory sampler consistent with the
  conservation validators.

---

## Spatial / simulation presentation

### OG-USD-1 — NVIDIA Omniverse runtime — PLANNED
- **Today:** `openusd_spatial_adapter.py` generates real Pixar `usd-core`
  `.usda/.usd` files (presentation/export). There is **no** NVIDIA Omniverse/Kit/
  nucleus runtime connection (zero `omni` imports).
- **Closed would require:** an actual Omniverse runtime integration. The
  engine-decides / visualizer-renders doctrine must be preserved; visualization
  must never change simulation physics.

### OG-SIM-1 — Animated simulation movement runtime — PLANNED (LOCKED_PRODUCT_DOCTRINE)
- **Today:** the trajectory authority (`production_trajectory_authority.py`) and
  the presentation bridge (`dynamic_scene_state_authority.py`) implement the
  foundations; the full interactive animated simulation runtime (Section 19
  contract) is documented doctrine, not a shipped runtime.
- **Closed would require:** the interactive simulation runtime, honoring every
  locked movement rule (stationary infrastructure, payload-attached-until-handoff,
  digital trace persistence, patient/room color invariance).

---

## Facility input

### OG-FIN-1 — CAD / BIM / IFC / Revit / PDF / image ingestion — PLANNED / NOT_MODELED
- **Today:** `facility_engineering_model.py` defines the input taxonomy
  (`SpatialSourceType`), subscription capability gates, and validation metadata,
  and `interactive_spatial_authoring.py` provides full manual authoring;
  TEMPLATE/BENCHMARK and user-supplied-facts retrofit are implemented. There is
  **no parser** that reads an IFC/Revit/DWG/DXF/PDF/image and produces geometry.
- **Closed would require:** actual file-ingestion/reconstruction parsers. BIM is
  not mandatory; geometry stays separate from the engineering object model.

---

## Bentley / iTwin

### OG-BEN-1 — Live Bentley/iTwin integration + real BIM ingestion — PARTIAL
- **Today:** typed client, injectable transport, and canonical binding are
  implemented; a real `BentleyHttpTransport` + OAuth exist but are opt-in
  (`# pragma: no cover`, gated by `bentley_live_environment_available()`). No
  automated live connection is exercised. IFC proof-model generation is a
  CONTROLLED TEST FIXTURE only.
- **Closed would require:** an exercised, credentialed live integration and real
  BIM geometry ingestion into the engineering object model. Bentley identity must
  remain subordinate to canonical identity.

---

## Physical feasibility (Part 3D)

### OG-P3D-1 — Light-MRT dominant not wired to the common contract — PARTIAL
- **Today:** `evaluate_light_mrt_dominant` still hardcodes `feasible=True`
  (test-locked by `test_light_mrt_dominant_is_not_wired_to_common_contract`); the
  four canonical evaluators derive `feasible` from the common contract.
- **Closed would require:** wiring the Light-MRT comparator through
  `derive_physical_feasibility` / `_physical_feasibility_result_fields`.

### OG-P3D-2 — Physical transport gate mode coverage — PARTIAL
- **Today:** `_resolve_transport_gate` directly gates the MRT-carrier and
  conventional-nuclear-transporter searches. PORTER general logistics, AGV/RGHT,
  Ordinary PTS, and RP-PTS are represented economically but not yet in the
  physical transport gate.
- **Closed would require:** extending the physical transport gate to the remaining
  mode-specific resource authorities.

---

## Scanner / imaging equipment

### OG-SCN-1 — Scanner economics / power / footprint calibration — NOT_CALIBRATED
- **Today:** `scanner_catalog.py` + `scanner_equipment_catalog.json` carry six
  real Siemens Healthineers / GE HealthCare / Philips models with
  `literature_calibrated` technical fields; power/dimensions and ALL economics
  are `NOT_CALIBRATED`. The study-level PET scanner cost anchor remains the
  generic `PlannerAssumptions.scanner_capex`.
- **Closed would require:** defensible per-model procurement/service pricing,
  power, and footprint evidence. Never fabricate; keep `NOT_CALIBRATED` until
  evidence exists.

---

*Maintenance: when a gap is genuinely closed by a future build, move it to a
"Closed gaps" section with the closing build/commit, and update the corresponding
row in `MRT_PHARMA_AUTHORITY_INDEX.md`.*

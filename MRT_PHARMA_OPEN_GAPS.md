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

### OG-CYC-1 — Cyclotron Production Estimation Authority — PARTIAL (authority now exists)
- **Today:** the Cyclotron Production Estimation Authority physically exists
  (`cyclotron_production_estimation_authority.py`, focused test
  `test_cyclotron_production_estimation_authority.py`, doc
  `CYCLOTRON_PRODUCTION_ESTIMATION_AUTHORITY.md`). It implements the full
  evidence hierarchy `SITE_CALIBRATED > MANUFACTURER_CALIBRATED >
  MODELED_ESTIMATE > CONTROLLED_ASSUMPTION > NOT_AVAILABLE` and produces a
  defensible numerical `MODELED_ESTIMATE` **only** as an irradiation-time
  response `A_EOB = K·I·(1−exp(−λt))` with `K` fit from the pair's OWN
  manufacturer-calibrated anchor (never borrowed). It is radionuclide-specific,
  accepts no patient identity, and reuses the Build 3B catalog + normalization.
  `SUMITOMO_CYPRIS_MP_30` + F-18 remains `SUPPORTED = YES`,
  `CALIBRATION_STATUS = NOT_CALIBRATED`, `ESTIMATION_STATUS = NOT_AVAILABLE`
  (no beam-current anchor; no GE PETtrace borrowing). The Part 3D per-radionuclide
  gate exposes an additive `simulation_production_basis` that never alters the
  `PRODUCTION_NOT_CALIBRATED` evidence verdict.
- **Evidence extension (Cyclotron Production Evidence & Calibration Extension):**
  a traceable evidence registry (`cyclotron_production_evidence.json`, sources
  doc `CYCLOTRON_PRODUCTION_EVIDENCE_SOURCES.md`) was added and the estimator
  gained a narrow additive seam (`load_production_evidence_registry`,
  `resolve_evidence_record`, `_try_registry_modeled_estimate`) to consume it. It
  carries only `MODELED_ESTIMATE` reaction-physics evidence (the `18O(p,n)18F`
  F-18 thick-target saturation yield, 8.3 GBq/µA measured), applied **only** with
  a model's OWN published beam current. This **closed two model × radionuclide
  pairs**: **SIEMENS Eclipse HP + F-18** and **SIEMENS RDS-111 + F-18** are each
  now a numerical `MODELED_ESTIMATE` (LOW confidence; ≈264 528 MBq at 120 min).
  Each pair uses its OWN published 60 µA beam current with the shared reaction
  saturation yield — the two values coincide because both Siemens/CTI models
  publish the same 60 µA current, not because any capacity was borrowed. Both are
  below GE PETtrace 890's 648 000 MBq (no borrow). Calibration status is
  unchanged; the registry never becomes manufacturer/site calibrated.
- **CYPRIS MP-30 + F-18 SPECIFICALLY REMAINS `NOT_AVAILABLE`** (evidence-honest):
  the model publishes no OWN beam current, so the reaction-yield path cannot
  apply without fabricating/borrowing a current (forbidden). No GE capacity is
  borrowed.
- **Still open (why PARTIAL):** most catalog pairs still cannot produce a
  numerical estimate for lack of physical evidence — CYPRIS MP-30/HM-12/HM-20 (no
  OWN beam current for the reaction-yield path), GE PETtrace 800 (null-yield
  records, no OWN current in `field_provenance`), IBA IKON/30XP (empty records),
  IBA KIUBE irradiation-time response (no published beam current), ACSI
  TR-19/TR-24, BEST 14p (no calibrated EOB anchor), and Cu-64/Zr-89/I-123/I-124
  on any model (absent from the canonical half-life table — no decay physics).
  Site-calibrated production performance records and additional manufacturer EOB
  evidence are not yet present. **Focused test:**
  `test_cyclotron_production_evidence_extension.py`.
- **Closed would require:** manufacturer/site production evidence (beam current +
  irradiation time + normalized EOB, or an explicitly-approved
  `CONTROLLED_ASSUMPTION`) for the remaining pairs, and canonical half-life
  physics for Cu-64/Zr-89/I-123/I-124. **Do not mark a pair as modeled unless a
  defensible estimator can actually be constructed from physical evidence.**
- **Generator boundary preserved:** cyclotron estimation never absorbs the
  generator pathway (Tc-99m → `OUT_OF_CYCLOTRON_SCOPE`); Ge-68/Ga-68 generator
  remains `NOT_MODELED` (OG-GEN-1).

### OG-SYNTH-1 — Synthetic-patient source-capability constraint — PARTIAL (selected-source representative path implemented; default/legacy path still benchmark-driven)
- **Prior status (PLANNED / PARTIAL):** the CAPITAL PROJECT synthetic patient
  generator produced radionuclide demand **independently** of the scenario's
  selected production-source configuration.
  `oncology_pet_spect_scenario.build_representative_day_population` assigned the
  radionuclide purely by modality (PET → `PET_RADIONUCLIDE = "F-18"`, SPECT →
  `SPECT_RADIONUCLIDE = "Tc-99m"`) with no reference to selected equipment; a
  capability mismatch surfaced only downstream at the feasibility stage.
- **Advanced to PARTIAL by:** the Synthetic Patient Radionuclide Source-Capability
  Binding build (selected-source representative path only — the default/legacy
  path remains benchmark-driven, see the "Remaining PARTIAL aspect" below). A
  narrow, independently-testable authority
  (`synthetic_radionuclide_source_capability.py`,
  `resolve_admissible_radionuclides` → `SyntheticRadionuclideCapabilityResult`)
  derives the admissible synthetic radionuclide set from the **SELECTED** cyclotron
  and generator sources (cyclotron `supported_radionuclides` ∪ generator
  `daughter_radionuclide`), filtered by the repository's clinical modality
  recognition (F-18 → PET, Tc-99m → SPECT), preserving each source identity and
  de-duplicating. `build_representative_day_population` (and its stochastic
  wrapper) now consume that admissible set **before patient creation** when
  selected-source ids are supplied. NORMAL synthetic demand for a radionuclide no
  selected source can supply is no longer generated (raises
  `NoCompatibleSourceError` — no F-18/Tc-99m fallback, no global-catalog
  borrowing). **Focused test:** `test_synthetic_patient_source_capability.py`
  (47 tests: 40 Section-41 invariants + control proofs A–F + patient-aware batch
  boundary). **Doc:** `SYNTHETIC_PATIENT_SOURCE_CAPABILITY_AUTHORITY.md`.
- **SUPPORTED ≠ CALIBRATED preserved:** admissibility uses SUPPORT semantics
  only; a radionuclide is admissible when a selected source supports it even while
  its production output is `NOT_CALIBRATED` / `NOT_AVAILABLE` (e.g.
  `SUMITOMO_CYPRIS_MP_30` + F-18). Quantitative sufficiency remains the downstream
  production authority's responsibility — this build consults no estimator,
  capacity, or economics.
- **STRESS_TEST / explicit demand preserved:** a `STRESS_TEST` mode is carried on
  the result contract, and the explicit-demand paths
  (`patient_radionuclide_demand.PatientRadionuclideDemand`,
  `inbound_patient_program.generate_synthetic_patient_population`) remain
  authoritative — a caller-supplied/unsupported radionuclide is never silently
  rewritten; downstream feasibility exposes `NO_COMPATIBLE_SOURCE`.
- **Remaining PARTIAL aspect (why not globally CLOSED):** the constraint is
  **opt-in** — callers that pass no selected-source ids (the default `None`)
  retain the representative benchmark defaults (F-18 / Tc-99m) unchanged for
  backward compatibility, and the explicit inbound path is explicit-demand by
  design. A future build could make selected-source ids mandatory for every
  synthetic entry point. Additionally, only F-18 (PET) and Tc-99m (SPECT) are
  clinically modality-classified today; other cyclotron-supported radionuclides
  (C-11, N-13, O-15, Ga-68, Cu-64, Zr-89, I-123, I-124) are reported as
  `SUPPORTED_BUT_NOT_CLINICALLY_MODALITY_CLASSIFIED` limitations, never invented
  as admissible.

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

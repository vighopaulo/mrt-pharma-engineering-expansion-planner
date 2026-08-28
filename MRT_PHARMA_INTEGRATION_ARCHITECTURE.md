# MRT Pharma — Integration Architecture

**Build:** MRT Pharma Authority Consolidation (governance / traceability layer).
**Purpose:** map every physically identified external-system integration seam, so
no future build mistakes an **established doctrine** for a **live implementation**,
and so each seam's authority boundary is explicit.

This document changes **no** production-engine behavior. Every status below was
verified against the physical repository (source + tests). Companion documents:
`MRT_PHARMA_AUTHORITY_INDEX.md`, `MRT_PHARMA_PRODUCT_DOCTRINE.md`,
`MRT_PHARMA_OPEN_GAPS.md`, `MRT_PHARMA_AUTHORITY_DOCTRINE.md`.

---

## 0. Status vocabulary

| Term | Meaning |
|---|---|
| `ESTABLISHED` | The integration **doctrine / role** is a locked product decision |
| `IMPLEMENTED` | Behavior physically present in repository code + tests |
| `PARTIAL` | Some seam implemented; a real gap disclosed |
| `PLANNED` | Agreed future behavior, not physically implemented |
| `NOT_MODELED` | Not represented in the repository at all |

> **Cardinal distinction preserved throughout:** an **ESTABLISHED doctrine** (the
> role a system plays, and the canonical adapter/binding that anchors it) is NOT
> the same as a **live/exercised connection**. These are recorded as separate
> statuses and never collapsed.

---

## 1. Integration map (overview)

```
                     ┌──────────────────────────────────────────────┐
   ARIA / oncology   │  MRT PHARMA  (the authority that DECIDES)      │
   system-of-record ─┤   physics · decay · production · transport ·  │
   (Operations)      │   routing · economics · feasibility ·         │
                     │   operations                                  │
   Bentley / iTwin   │                                               │
   CAD / BIM / IFC  ─┤   Engineering Object Model → route networks → │
   facility geometry │   engineering calc → feasibility → optimize   │
                     │                                               │
   Hospital systems ─┤                                               │
   (planned)         └───────────────┬───────────────────────────────┘
                                     │  authoritative state
                                     ▼
                     NVIDIA / OpenUSD  (VISUALIZES; never decides)
```

The three-layer separation is locked doctrine: **Bentley/iTwin = geometry
context; MRT Pharma = decides; NVIDIA/OpenUSD = visualizes.** Neither Bentley nor
NVIDIA replaces MRT Pharma.

---

## 2. ARIA (oncology patient / workflow system-of-record)

- **ROLE:** established concrete Operations oncology patient/workflow integration
  target. The upstream **system-of-record** for patient, procedure, and
  appointment truth. MRT Pharma does **not** replace ARIA.
- **DATA IN:** patient / procedure / appointment records (today: a **synthetic**
  `SYNTHETIC_TEST_FIXTURE`, normalized via `build_aria_fixture` /
  `ingest_aria_fixture`).
- **DATA OUT (from MRT Pharma):** none pushed back to ARIA; ARIA is a source, not
  a sink. Internally the seam emits `CanonicalOperationalPatientRecord` into the
  Operations digital twin.
- **AUTHORITY BOUNDARY:** ARIA (and any vendor) identity is normalized into the
  **canonical operational patient**; a vendor identity is never canonical
  identity. `VARIAN_ARIA` exists only as a `SourceSystem` tag today. The Capital
  synthetic/project-demand population is a **separate** patient source and must
  never be merged with the operational source.
- **IMPLEMENTATION STATUS (split — do not collapse):**
  - `ARIA_INTEGRATION_DOCTRINE = ESTABLISHED` — the role, conceptual flow
    (ARIA → adapter → canonical operational patient → Operations digital twin),
    and the vendor-neutral **fixture** adapter + canonical mapping are IMPLEMENTED.
  - `LIVE_ARIA_CONNECTOR = PLANNED / PARTIAL` — there is **no** network /
    credentials / API / FHIR / HL7 client; explicitly
    `SECURITY_COMPLIANCE_NOT_IN_SCOPE` (not HIPAA-compliant). Only synthetic
    fixtures exist.
- **CANONICAL FILES:** `healthcare_integration.py`, `healthcare_adapters.py`,
  `inbound_patient_program.py`. Tests:
  `test_vendor_neutral_healthcare_integration.py`,
  `test_inbound_patient_program.py`, `test_inbound_pipeline_integration.py`.
- **OPEN GAP:** OG-ARIA-1 (a real, authenticated, compliant vendor integration).

---

## 3. Bentley / iTwin (engineering / facility / BIM geometry)

- **ROLE:** engineering / facility / BIM geometry and infrastructure context.
  Conceptual flow: Bentley/BIM/CAD/other geometry → MRT Pharma Engineering Object
  Model → route networks → engineering calculations → physical feasibility →
  optimization. **Bentley does NOT replace MRT Pharma.**
- **DATA IN:** iTwin element / geometry references (today via a typed client with
  injectable transport; live pulls are opt-in and not exercised).
- **DATA OUT:** canonical binding of a Bentley element to an already-existing
  `mrtway_object_id`.
- **AUTHORITY BOUNDARY:** a Bentley external element identity is **never**
  canonical identity — `bind_live_bentley_element` resolves to an existing
  canonical object and refuses to fabricate one. Bentley identity is subordinate
  to canonical identity.
- **IMPLEMENTATION STATUS (split):**
  - `BENTLEY_ENGINEERING_ROLE = ESTABLISHED` — the doctrine and the typed
    client / injectable transport / canonical binding are IMPLEMENTED.
  - `LIVE_BENTLEY_CONNECTION = PARTIAL` — a real `BentleyHttpTransport` + OAuth
    exist but are opt-in (`# pragma: no cover`, gated by
    `bentley_live_environment_available()`); no automated live connection is
    exercised. IFC proof-model generation is a **CONTROLLED TEST FIXTURE only**
    (synthetic IFC4, not a geometry authority).
- **CANONICAL FILES:** `bentley_itwin_client.py`, `bentley_canonical_binding.py`,
  `bentley_access_recovery.py`, `bentley_personal_user_diagnostic.py`,
  `ifc_hospital_proof_model_generator.py`. Tests:
  `test_bim_itwin_phase1_bentley_binding.py`,
  `test_bim_itwin_phase2a_hospital_ifc_proof_model.py`,
  `test_bim_itwin_phase2b_live_bentley_binding.py`,
  `test_bentley_access_recovery.py`.
- **OPEN GAP:** OG-BEN-1 (exercised credentialed live integration + real BIM
  ingestion).

---

## 4. NVIDIA / OpenUSD (visualization / simulation presentation)

- **ROLE:** visualization / animation / interactive simulation-presentation
  layer. Locked doctrine: **ENGINEERING ENGINE DECIDES → NVIDIA VISUALIZES.**
- **DATA IN:** authoritative engine state / trajectories (samples copied verbatim
  from the engine).
- **DATA OUT:** Pixar `usd-core` `.usda` / `.usd` presentation files.
- **AUTHORITY BOUNDARY:** visualization **never** changes simulation physics
  (`OPENUSD_SELECTS_TRANSPORT_SOLUTION = NO`,
  `OPENUSD_BECOMES_ENGINEERING_AUTHORITY = NO`; `USD_PRIM_PATH` is never
  authoritative).
- **IMPLEMENTATION STATUS (split):**
  - `NVIDIA_OPENUSD_VISUALIZATION_ROLE = ESTABLISHED` — the engine-decides /
    visualizer-renders doctrine is locked; USD export is IMPLEMENTED using real
    Pixar `usd-core` (vendored `.usd_runtime/`; raises
    `OpenUsdRuntimeNotAvailable` if absent — never fabricates an SDK).
  - `LIVE_OMNIVERSE_RUNTIME = PLANNED` — **no** NVIDIA Omniverse / Kit / nucleus
    runtime connection (zero `omni` imports). "NVIDIA" concretely means the
    `.usda`/`.usd` file generation presentation layer today.
- **CANONICAL FILES:** `openusd_spatial_adapter.py`, `openusd_yc_demo_binding.py`,
  `dynamic_scene_state_authority.py`, `digital_twin_simulation_state.py`. Tests:
  `test_openusd_spatial_adapter.py`, `test_openusd_yc_demo_binding.py`,
  `test_dynamic_scene_state_authority.py`,
  `test_operational_day_trajectory_scene.py`.
- **OPEN GAP:** OG-USD-1 (Omniverse runtime), OG-SIM-1 (animated simulation
  runtime, LOCKED_PRODUCT_DOCTRINE).

---

## 5. CAD / BIM / IFC / Revit / DWG / DXF / PDF / image (facility file ingestion)

- **ROLE:** external facility-geometry file formats as a potential input path to
  the Engineering Object Model. BIM is **not mandatory**.
- **DATA IN (intended):** IFC / REVIT_BIM / DWG / DXF / PDF / IMAGE facility
  files.
- **DATA OUT:** reconstructed geometry feeding the engineering object model
  (intended).
- **AUTHORITY BOUNDARY:** geometry is kept **separate** from the engineering
  object model (design invariant); a parsed file never becomes an authority by
  itself.
- **IMPLEMENTATION STATUS (split):**
  - `FACILITY_INPUT_TAXONOMY = IMPLEMENTED` — `SpatialSourceType` enum,
    subscription-capability gates, validation metadata, full manual authoring,
    and TEMPLATE/BENCHMARK + user-supplied-facts retrofit are IMPLEMENTED.
  - `FILE_INGESTION_PARSERS = PLANNED / NOT_MODELED` — there is **no** parser that
    reads an IFC/Revit/DWG/DXF/PDF/image and produces geometry (these exist only
    as enum members + subscription/validation metadata).
- **CANONICAL FILES:** `facility_engineering_model.py`,
  `interactive_spatial_authoring.py`, `existing_facility_retrofit.py`,
  `facility_expansion_authority.py`. Tests:
  `test_facility_engineering_model.py`, `test_interactive_spatial_authoring.py`,
  `test_existing_facility_retrofit.py`.
- **OPEN GAP:** OG-FIN-1 (file-ingestion / reconstruction parsers).

---

## 6. Facility / infrastructure APIs (site power, building services)

- **ROLE:** site-level engineering context (electrical load adequacy, auxiliary
  systems) consumed by the transport energy / maintenance authorities.
- **DATA IN:** site power capacity assumptions (today
  `CONTROLLED_ENGINEERING_ASSUMPTION` / `NOT_CALIBRATED` where evidence absent).
- **DATA OUT:** power-adequacy evaluation, energy/maintenance OPEX rows.
- **AUTHORITY BOUNDARY:** these are **internal engineering computations** over
  supplied/assumed site parameters, not a live building-management-system (BMS)
  connection.
- **IMPLEMENTATION STATUS:** `IMPLEMENTED` as internal computation with honest
  `NOT_CALIBRATED` sentinels; **no live facility/BMS API** — `NOT_MODELED`.
- **CANONICAL FILES:** `mrt_auxiliary_systems_authority.py`
  (`compute_mrt_total_electrical_load`, `evaluate_site_power_adequacy`),
  `mrt_transport_energy_maintenance_authority.py`, `equipment_energy_opex.py`.
- **OPEN GAP:** no dedicated gap — live BMS/facility API is out of scope; the
  computation seam is complete for supplied parameters.

---

## 7. Hospital systems (EHR / RIS / PACS / scheduling, beyond ARIA)

- **ROLE:** broader hospital-system integration targets (EHR / RIS / PACS /
  scheduling) that a mature Operations product would consume.
- **DATA IN / OUT:** patient / order / schedule data (intended); nothing today
  beyond the ARIA-class fixture path.
- **AUTHORITY BOUNDARY:** would route through the **same vendor-neutral canonical
  operational patient** model as ARIA — never a private per-vendor schema inside
  the engine.
- **IMPLEMENTATION STATUS:** `PLANNED / NOT_MODELED` — only the vendor-neutral
  adapter foundation (shared with ARIA) exists; no EHR/RIS/PACS clients.
- **CANONICAL FILES:** `healthcare_integration.py`, `healthcare_adapters.py`
  (shared adapter foundation).
- **OPEN GAP:** subsumed by OG-ARIA-1 (real, compliant vendor integrations).

---

## 8. Summary status table

| Seam | Role status | Live/exercised status | Open gap |
|---|---|---|---|
| ARIA | `ESTABLISHED` (doctrine + fixture adapter IMPLEMENTED) | `PLANNED/PARTIAL` (no live connector) | OG-ARIA-1 |
| Bentley / iTwin | `ESTABLISHED` (client + binding IMPLEMENTED) | `PARTIAL` (opt-in, not exercised) | OG-BEN-1 |
| NVIDIA / OpenUSD | `ESTABLISHED` (USD export IMPLEMENTED) | `PLANNED` (no Omniverse runtime) | OG-USD-1, OG-SIM-1 |
| CAD / BIM / IFC / Revit / DWG / DXF / PDF / image | taxonomy `IMPLEMENTED` | parsers `PLANNED/NOT_MODELED` | OG-FIN-1 |
| Facility / infrastructure APIs | computation `IMPLEMENTED` | live BMS `NOT_MODELED` | — |
| Hospital systems (EHR/RIS/PACS) | adapter foundation shared | `PLANNED/NOT_MODELED` | OG-ARIA-1 |

---

## 9. Internal authority flow — patient → batch → cyclotron / generator

This is an **internal authority boundary**, not an external integration seam. It
is recorded here only for clarity of the patient-awareness layering; see
`MRT_PHARMA_PRODUCT_DOCTRINE.md` §11A for the normative doctrine and
`MRT_PHARMA_AUTHORITY_INDEX.md` §2.24 for the navigation.

```
CAPITAL PROJECT SCENARIO
  → SYNTHETIC PATIENT DEMAND        (scenario / source-capability constrained*)
    → PATIENT-AWARE BATCH PLANNING  (patient-aware via Hospital Master Calendar)
      → RADIONUCLIDE / PHYSICAL-BATCH REQUIREMENT
        → CYCLOTRON / GENERATOR PRODUCTION AUTHORITY
                                    (radionuclide- & physical-batch-aware,
                                     NOT directly patient-identity-aware)
```

- **Patient generator** = scenario-aware. \*Constraining synthetic radionuclide
  demand to the combined selected production-source capability set is **PLANNED /
  PARTIAL** today (OG-SYNTH-1); demand is currently generated independently and
  reconciled against capability downstream.
- **Batch-production planner** = patient-aware **and** production-aware; it
  translates patient requirements into radionuclide-specific physical production
  requirements before they reach the cyclotron/generator.
- **Cyclotron** = radionuclide-aware + physical-batch/window-aware, **not**
  directly patient-identity-aware (no `patient_id` / name / room / scanner
  coupling).
- **Generator** = source / radionuclide-aware, **not** directly
  patient-identity-aware.

`SUPPORTED ≠ CALIBRATED` and `PATIENT COHORT ≠ PHYSICAL PRODUCTION BATCH` hold
across this flow. An unsupported-demand / stress-test mode must expose
`NO_COMPATIBLE_SOURCE` and never silently mutate patient demand (PLANNED).

---

*This is a governance / traceability artifact. It introduces no production-engine
behavior. When a seam's status changes, update the row here and the corresponding
entry in `MRT_PHARMA_AUTHORITY_INDEX.md` / `MRT_PHARMA_OPEN_GAPS.md`.*

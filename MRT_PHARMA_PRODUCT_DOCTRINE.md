# MRT Pharma — Product Doctrine

**Build:** MRT Pharma Authority Consolidation (governance / traceability layer).
**Nature:** durable **product decisions**, not a repository inventory. This
document records the `LOCKED_PRODUCT_DOCTRINE` (class A) decisions that constrain
every current and future build. It is companion to:

- `MRT_PHARMA_AUTHORITY_INDEX.md` — the navigation map to the physical authorities.
- `MRT_PHARMA_INTEGRATION_ARCHITECTURE.md` — the external-system seam map.
- `MRT_PHARMA_BUILD_LEDGER.md` — the physical build history.
- `MRT_PHARMA_OPEN_GAPS.md` — what is agreed but not yet implemented.
- `MRT_PHARMA_AUTHORITY_DOCTRINE.md` — the authority-first governance rules and
  the three classes of project truth.

This document changes **no** production-engine behavior. Where a decision has a
concrete repository authority, the canonical file is named for traceability, but
the decision itself is the product truth, not the code.

---

## 1. MRT Pharma has TWO products

> **MRT PHARMA = CAPITAL PROJECT + OPERATIONS.**

They are two distinct products that share one validated set of physical /
engineering / economic authorities. Neither product owns a private copy of the
physics, decay, production, transport, routing, or economics engines.

The product boundary is the study scope axis in `study_scope.py`:
`StudyScope = CAPITAL_PLANNING | OPERATIONAL_ONLY`. Study scope and transport
architecture (`CONVENTIONAL | MRT | HYBRID`) are **independent, composable
axes** — scope only controls whether new-project acquisition/construction CapEx
enters the study objective; it never removes physical assets, capacity,
scheduling, or staffing.

---

## 2. CAPITAL PROJECT — durable decisions

- **What it does:** finds the best facility / equipment / transport composition
  under user constraints (owners, health systems, architects, engineers,
  builders, planners).
- **It is NOT "MRT versus Conventional."** It is a composition problem over
  building blocks, not a binary contest.
- **MRT is OPTIONAL.** A valid recommended solution may contain no MRT at all.
- **Transport technologies are composable BUILDING BLOCKS:**
  - Manual / Porter,
  - AGV / AMR (see the RGHT/RHTS clarification below),
  - RGHT / RHTS (rail-guided hospital transport),
  - Ordinary PTS (pneumatic tube system),
  - RP-PTS (dedicated radiopharmaceutical pneumatic tube system),
  - MRT.
- **"NO BUILD" is a legitimate candidate.** Do-nothing / retain-existing is a
  real outcome, never forced construction. (Today `NO_BUILD_BASELINE` is a
  test-locked legacy Build-3A identity in the equal-budget search, not yet a
  first-class fifth four-architecture option — see `MRT_PHARMA_OPEN_GAPS.md`
  OG-CAP-1.)
- **Patient demand is UPSTREAM.** Production, scanner, and transport capacity do
  **not** create patients. Excess capacity is headroom, never additional
  patients (test-locked `test_excess_capacity_is_headroom_not_extra_patients`).
- **Capital patient source = SYNTHETIC / PROJECT-DEMAND population.** A modeled
  population derived from project demand — never actual patient records.

**Canonical authorities (for traceability, not the decision itself):**
`whole_oncology_four_architecture_optimization.py`, `hybrid_optimization.py`,
`equal_budget.py`, `architecture_optimizer.py`, `capital_project_api.py`.

---

## 3. OPERATIONS — durable decisions

- **What it does:** manages / plans an operating facility using **actual or
  planned operational demand** and resources.
- **Operations patient source = ACTUAL / PLANNED operational patients** — a
  distinct source from the Capital synthetic/project-demand population.
- **ARIA is the established concrete oncology patient / workflow integration
  target.** ARIA-class systems remain the upstream system-of-record for
  patient / procedure / appointment truth; MRT Pharma does **not** replace ARIA.
  Conceptual flow: **ARIA → MRT Pharma operational adapter → canonical
  operational patient → MRT Pharma Operations digital twin.**
- **Synthetic patient capability remains SEPARATE** from the operational patient
  source. The two sources must never be silently merged.
- **Operations links the full physical chain:** patient → radionuclide →
  administered activity → production → batch/release → transport → injection →
  uptake → scanner → completed patient.

**Canonical authorities (for traceability):** `operational_day_orchestrator.py`,
`operating_day_scheduler.py`, `long_horizon_operational_planning.py`,
`intraday_scheduling.py`, `live_operational_state.py`,
`production_clinical_schedule.py`; operational patient ingestion via
`healthcare_integration.py` / `healthcare_adapters.py` /
`inbound_patient_program.py`.

---

## 4. Patient-source doctrine (Capital vs Operations)

> **CAPITAL PROJECT PATIENT SOURCE = synthetic / project-demand population.**
> **OPERATIONS PATIENT SOURCE = actual / planned operational patients.**

- In **Capital Project**, the population is generated from project demand; it is a
  planning abstraction, not real people.
- In **Operations**, the population is the actual/planned operational patients,
  with **ARIA** as the established upstream system-of-record integration target.
- The **ARIA integration doctrine is ESTABLISHED**; the **live ARIA connector is
  PLANNED / PARTIAL** (a vendor-neutral fixture adapter with synthetic fixtures
  exists; there is no authenticated, compliant network connection). These two
  facts must never be collapsed into a single "PLANNED" summary. See
  `MRT_PHARMA_INTEGRATION_ARCHITECTURE.md` and `MRT_PHARMA_OPEN_GAPS.md`
  OG-ARIA-1.

---

## 5. Lockdown / What-If doctrine

- **LOCKDOWN** = an authoritative, immutable scenario baseline.
- **WHAT-IF** = a non-authoritative branch that recomputes only the affected
  engineering and economics.
- Promoting a what-if to lockdown creates a **new** lockdown: the parent is
  recorded, the prior lockdown is marked `SUPERSEDED`, and nothing is deleted or
  overwritten. Lineage is preserved.
- **"Live" means synchronous recompute** — it is not hospital telemetry and not a
  live vendor API feed.

**Canonical authority:** `lockdown_what_if_lineage_authority.py`,
`live_engineering_impact_binding.py`, `live_operational_state.py`.

---

## 6. Two-route-family doctrine

There are exactly two route families, and they must never be conflated:

- **HUMAN_CIRCULATION_NETWORK** — patients, porters / Manual, and AGV / AMR follow
  authorized human geometry (corridors, doors, elevators). Humans cannot move
  through walls.
- **CONCEALED_SERVICE_TRANSPORT_CORRIDOR** — MRT, RHTS / RGHT, Ordinary PTS, and
  RP-PTS share an architectural service right-of-way concept while retaining
  distinct mode-specific lanes.

Enforced sub-doctrines:

- **SHARED RIGHT-OF-WAY ≠ SHARED TRACK** — routing runs over the mode-compatible
  subgraph only.
- **SHARED RIGHT-OF-WAY ≠ MODE INSTALLED** — corridor eligibility does not install
  a mode.
- A shared-corridor-eligible mode may borrow the MRT reference corridor
  **distance only**, never its speed, capacity, or economics.

**Canonical authority:** `canonical_spatial_authority.py`,
`human_circulation_authority.py`, `shared_network.py` (Build 3C.1).

---

## 7. Payload / service-class / color doctrine

- **TRANSPORT SHAPE = mechanism; PAYLOAD COLOR = substance / service class.**
- **Color is presentation metadata only.** It does not determine physics,
  routing, capacity, eligibility, CapEx, OPEX, or ranking. Color fields are
  structurally separate from priority/speed fields.
- The **same payload / service class keeps the same color across eligible
  modes.**
- Service classes (active): RADIOPHARMACEUTICAL_NUCLEAR (VIOLET, P1),
  SPECIMEN_BLOOD (BLUE, P2), PHARMACY_INFUSION (TEAL, P2),
  STERILE_CLEAN_SUPPLY (AMBER, P3), LAUNDRY_CLEAN_LINEN (GOLD, P4). Inactive /
  future: FOOD_NUTRITION (GREEN), WASTE (RED). Uncalibrated speeds stay
  `NOT_CALIBRATED`.

**Canonical authority:** `mrt_service_class_authority.py`,
`shared_mrt_multistream_authority.py`.

---

## 8. Carrier identity vs payload identity

Carrier identity, container identity, payload identity, and service-class identity
are **distinct**. A carrier is not its payload. **Patients and rooms do NOT
inherit payload color** — delivering a violet radiopharmaceutical payload does not
turn the patient or the room violet. The payload stays attached to the
carrier/porter until a valid interface/handoff; after delivery the payload may
disappear from transport visualization while its digital trace persists.

---

## 9. Bentley / MRT Pharma / NVIDIA role separation

Three layers that must **never** be conflated:

- **BENTLEY / iTwin** = engineering / facility / BIM geometry and infrastructure
  context.
- **MRT PHARMA** = engineering logic + physics + optimization + economics +
  operations. **MRT Pharma is the authority that DECIDES.**
- **NVIDIA / OpenUSD** = visualization / animation / interactive
  simulation-presentation. **ENGINEERING ENGINE DECIDES → NVIDIA VISUALIZES.**
  Visualization never changes simulation physics.

Neither Bentley nor NVIDIA replaces MRT Pharma. See
`MRT_PHARMA_INTEGRATION_ARCHITECTURE.md` for the seam-level detail.

---

## 10. SUPPORTED ≠ CALIBRATED

A cyclotron model **supporting** a radionuclide (beam capability) is a different
fact from that model × radionuclide pair being **calibrated** (having
manufacturer/site output evidence). Beam specs, supported-vs-schedulable
radionuclides, and calibrated production are three separate dimensions.

- SUPPORTED but no production evidence → `NOT_CALIBRATED` (e.g.
  `SUMITOMO_CYPRIS_MP_30` + F-18).
- `NOT_CALIBRATED` ≠ ZERO and ≠ automatic infeasibility.
- A calibrated production record for one model/radionuclide can **never** be
  borrowed by another model or another radionuclide.

**Radionuclide-specificity corollary:** calibration for radionuclide A does not
qualify radionuclide B. A calibrated F-18 record must never qualify C-11, N-13,
O-15, Ga-68, Cu-64, Zr-89, I-123, I-124, Tc-99m, or any other radionuclide.
Normalization to common units (MBq) never makes radionuclides interchangeable.

---

## 11. Patient cohort ≠ physical cyclotron production batch

> **PATIENT / ADMINISTRATION COHORT ≠ PHYSICAL CYCLOTRON PRODUCTION BATCH.**

A patient cohort (who is scanned, and when) is scheduled independently from the
physical production batch/cycle (a cyclotron run or a generator elution). A
patient trace may record a `batch_id`, but the physical batch is scheduled by
cyclotron capacity and production windows. **Physical batch count is never
fabricated** to match a patient count.

---

## 11A. Patient / batch / production-equipment boundary

This section codifies the authority layering between synthetic patient demand,
patient-aware batch-production planning, and the (patient-identity-agnostic)
cyclotron / generator production authorities. It is a **governance clarification
of existing layering** — it changes no production-engine behavior.

**Governing layering (top → bottom):**

> CAPITAL PROJECT SCENARIO → SYNTHETIC PATIENT GENERATOR →
> PATIENT / RADIONUCLIDE DEMAND → PATIENT-AWARE BATCH-PRODUCTION PLANNER →
> RADIONUCLIDE / PHYSICAL-BATCH REQUIREMENT →
> CYCLOTRON / GENERATOR PRODUCTION AUTHORITY.

**Authority-awareness boundaries (normative):**

- **Synthetic patient generation is scenario / source-capability constrained.**
  For CAPITAL PROJECT synthetic patients, the randomizer/generator must not
  create radionuclide demand independently of the scenario's production-source
  configuration. Conceptually: SCENARIO PRODUCTION SOURCES → ALLOWED / AVAILABLE
  RADIONUCLIDE SET → SYNTHETIC PATIENT RADIONUCLIDE GENERATION. The available set
  is the **combined capability of ALL selected production sources** — cyclotron(s)
  **and** generator(s) — not merely the selected cyclotron's radionuclides. If a
  Mo-99/Tc-99m generator is present, Tc-99m is admissible even though the
  cyclotron does not produce it. *(Implementation status: **OG-SYNTH-1 = PARTIAL**
  — the selected-source representative binding is **IMPLEMENTED** by the Synthetic
  Patient Radionuclide Source-Capability Binding build, but the gap is NOT
  globally CLOSED. The `synthetic_radionuclide_source_capability.py` resolver
  derives the admissible set from the SELECTED cyclotron + generator sources
  BEFORE patient creation, and
  `oncology_pet_spect_scenario.build_representative_day_population` consumes it
  when selected-source ids are supplied. NORMAL synthetic demand for an
  unsupported radionuclide is no longer generated; STRESS_TEST / explicit demand
  is preserved and exposed downstream as `NO_COMPATIBLE_SOURCE`. The
  default/legacy path (no selected-source ids) remains benchmark-driven
  (F-18 / Tc-99m) for backward compatibility, which is why OG-SYNTH-1 stays
  PARTIAL rather than CLOSED. See
  `SYNTHETIC_PATIENT_SOURCE_CAPABILITY_AUTHORITY.md` and
  `MRT_PHARMA_OPEN_GAPS.md` OG-SYNTH-1.)*
- **NORMAL synthetic demand = source-capability-constrained before patient
  creation; EXPLICIT / STRESS-TEST demand = preserved even if unsupported.**
  Synthetic patient radionuclide demand is constrained by the scenario's
  combined selected production-source capability set (cyclotron supported
  radionuclides ∪ generator daughter radionuclides, filtered by clinical
  modality). The randomizer chooses only within the admissible set; it never
  fabricates or substitutes a radionuclide, and it never falls back to F-18 /
  Tc-99m or borrows from an unselected catalog machine. STRESS_TEST callers may
  deliberately request an unsupported radionuclide, which is preserved and
  surfaced as `NO_COMPATIBLE_SOURCE` — the system must never silently alter
  patient demand to make the facility feasible.
- **Batch production is patient-aware.** The patient-aware batch-production
  planner translates patient clinical requirements into radionuclide-specific
  physical production requirements before those requirements reach the cyclotron
  or generator. Patient awareness flows through the Operational Plan / Hospital
  Master Calendar authority.
- **Cyclotron production is radionuclide-aware and physical-batch-aware, but NOT
  directly patient-identity-aware.** The cyclotron authority receives engineering
  requirements (radionuclide, required EOB activity, required production window,
  selected equipment identity, irradiation/cycle requirement, physical
  batch/cycle requirement) and answers engineering questions (does this model
  support this radionuclide; what calibrated/modeled EOB output exists; how many
  physical cycles/batches are required; do they fit the operating window). It does
  **not** need `patient_id`, patient name, patient room, or scanner assignment.
- **Generator production is source / radionuclide-aware, but NOT directly
  patient-identity-aware.** The generator authority receives a
  radionuclide/source requirement, activity requirement, timing requirement,
  generator identity, and physical source constraints. Patient awareness stays
  upstream in the demand / batch-planning layer.
- **SUPPORTED does not imply CALIBRATED production output.** A radionuclide may be
  a SUPPORTED admissibility constraint for synthetic demand while its physical
  production output remains `NOT_CALIBRATED` (e.g. `SUMITOMO_CYPRIS_MP_30` +
  F-18). The synthetic generator may emit supported demand without claiming the
  selected source is quantitatively qualified for it; calibration, capacity,
  batch output, cycle duration, and production-window feasibility remain the
  downstream production authority's responsibility (see Section 10).
- **Patient cohort does not imply physical production batch.** Grouping demand
  into administration or production windows never means "one cohort = one
  cyclotron batch"; physical batch count depends on the production authority for
  the selected source × radionuclide (see Section 11).

**Do not couple cyclotron/generator production physics to** `patient_id`, patient
name, patient room, scanner assignment, or any other unnecessary patient
identity. The Hospital Master Calendar / batch-planning layer is the single place
patient requirements are translated into radionuclide-specific physical
production requirements.

**Normal mode vs stress-test mode:**

- **NORMAL REPRESENTATIVE SYNTHETIC MODE:** synthetic radionuclide demand is
  constrained by available/selected production-source capabilities (the doctrine
  above).
- **OPTIONAL FUTURE STRESS-TEST / REQUIREMENT MODE:** a user may intentionally
  define demand for a radionuclide the current facility cannot produce. In that
  case the system must expose `NO_COMPATIBLE_SOURCE` (or the appropriate
  physical-feasibility failure/qualification) and **must NOT silently alter the
  patient demand to make the facility feasible.** This stress-test mode is
  **PLANNED** doctrine, not a shipped engine (no new stress-test engine is
  introduced here).

**Hospital Master Calendar / patient-aware production propagation (preserved):**
the Hospital Master Calendar coordinates patient clinical requirements with
radionuclide demand, production cycles, physical batches, cyclotron/generator
schedules, transport, injection, uptake, scanner/room schedules, and staffing.
The patient-facing calendar and the facility/production calendar are different
views of the same coordinated operational state. The propagation chain is
**Clinical Requirement → Production → Batch → Transport → Scanner/Room →
Calendar**; a production delay/shortfall may propagate downstream and require
rescheduling the affected batch, source, transport, scanner time, room/resource,
or patient appointment **while preserving radionuclide-decay physics**.

---

## 11A. Scanner doctrine

> **SCANNER COUNT ≠ SCANNER MODEL ≠ SCANNER CAPABILITY ≠ SCANNER THROUGHPUT.**

These are four distinct authorities and must never be collapsed into one:

- **Scanner count** is a plain requirement integer derived from patient demand
  (`PATIENT DEMAND → SCANNER REQUIREMENT`, ceiling division) — never a model
  selection, never reversed into demand.
- **Scanner model** is a catalog identity (manufacturer / model / modality /
  commercial status). A count carries no model; a model is not ranked by count.
- **Scanner capability** (modality, protocol families, energy range) is
  equipment capability — it never manufactures patient demand. **Excess scanner
  capability / capacity is HEADROOM, not new patients.**
- **Scanner throughput** (per-protocol acquisition minutes) is a workload driver;
  it is not, by itself, a full patients/day figure unless setup/turnover/
  operating-hours authority supports it.

Further durable rules:

- **Patient-awareness belongs to the scheduling / calendar layer, not the scanner
  catalog.** `PATIENT → SCHEDULER/CALENDAR → SCANNER RESOURCE ASSIGNMENT` while
  `SCANNER CATALOG → EQUIPMENT CAPABILITY`. The scanner catalog does **not** need
  `patient_id`, patient name, patient room, or appointment. A scanner **resource**
  (persistent `SCN-xxx` identity) may be assigned to a patient by the calendar;
  the scanner **catalog model** is not bound to a patient.
- **PET ≠ SPECT capacity.** PET demand consumes only PET scanner capacity and
  SPECT demand only SPECT capacity; untagged (modality-unknown) scanners are
  excluded from both pools — no silent capacity sharing.
- **Existing / retain / new-purchase / replacement / legacy-installed-base are
  all legitimate capital choices.** `NO BUILD` and `RETAIN EXISTING EQUIPMENT`
  are valid; a newer model existing is not, by itself, a reason to replace.
- **Patient-aware batch planning → production requirement → clinical schedule →
  scanner assignment** is the operational chain; scanner timing is causally
  downstream of production/transport/injection/uptake.
- **The long-horizon Hospital Master Calendar foundation EXISTS**
  (`long_horizon_operational_planning.py`, data-driven horizon). Full live
  Operations closure (intra-day scanner downtime windows, per-scanner operating
  hours) may remain partial and is a separate future build.
- **Never fabricate scanner economics, power, footprint, room requirements, or
  model-specific throughput.** `NOT_CALIBRATED` / `NOT_MODELED` are preserved
  honestly (see Section 12).

---

## 12. No-fabrication doctrine

Honest unknowns are preserved, never invented:

- Never fabricate production capacity, cycle duration, EOB activity, or a
  production record.
- Never fabricate scanner economics, power, or footprint.
- Never fabricate a transport speed, an SDK/runtime, a BIM geometry parse, or a
  live vendor connection.
- `NOT_CALIBRATED` / `NOT_MODELED` / `PLANNED` are reported honestly and never
  silently coerced to `0`, to `IMPLEMENTED`, or to a false feasibility verdict.
- A `PLANNED_REQUIREMENT` is never described as an
  `IMPLEMENTED_REPOSITORY_AUTHORITY`.

---

## 13. Standing PLANNED product intentions (not yet implemented)

These are durable **product intentions** classified `PLANNED_REQUIREMENT` — named
here so no future build mistakes them for shipped behavior:

- **Cyclotron Production Estimation Authority** — a future numerical estimator for
  SUPPORTED-but-`NOT_CALIBRATED` model × radionuclide pairs, under the evidence
  hierarchy `SITE_CALIBRATED > MANUFACTURER_CALIBRATED > MODELED_ESTIMATE >
  CONTROLLED_ASSUMPTION > NOT_AVAILABLE`. **PLANNED** (OG-CYC-1).
- **Part 3E Composition Optimizer** — a free "compose any subset of transport
  building blocks per service class and optimize" engine, beyond the four
  canonical architectures + equal-budget search. **PLANNED** (OG-CAP-2).

---

*This is a governance artifact. It records product doctrine and introduces no
production-engine behavior.*

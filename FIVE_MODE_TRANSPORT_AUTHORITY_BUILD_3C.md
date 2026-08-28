# FIVE-MODE TRANSPORT AUTHORITY — BUILD 3C

**Status: repository-grounded engineering authority + composition-readiness report (read-only audit).**
**Baseline: `main` @ `1d557f0` (Build 3B complete, committed). No engine code changed by Build 3C.**
**Deliverables: this document + `test_build3c_transport_authority.py` focused tests only.**

Build 3C audits the five transport building blocks as **composable** components
of a Capital Project facility solution. Transport modes are building blocks, not
fixed competing architectures. MRT is one block and is never required. Every
classification below is grounded in physical repository code; classifications
are IMPLEMENTED / PARTIAL / CONTROLLED_ASSUMPTION / NOT_MODELED / NOT_APPLICABLE.

---

## A. EXECUTIVE BUILD 3C FINDING

The repository already contains **five distinct, provenance-tagged transport
authorities** with correct eligibility gating, peak-concurrency fleet sizing,
and honest calibration status. It also already contains a genuine
**per-service-class technology selection** result
(`evaluate_optimized_technology_mix` → `OptimizedTechnologyMixResult.service_technology`)
that spans all five building blocks and checks physical eligibility before
economics. What it lacks is a single **first-class, persisted "candidate facility
solution"** object that (a) holds a per-service-class building-block assignment
across all five modes, (b) holds multi-leg chains as objects, and (c) is what the
Capital Project API surfaces and the ranking authority scores. That is a KNOWN
ARCHITECTURAL GAP for a future free-composition engine — **not** a defect, and
building it is explicitly out of Build 3C scope (Section 37).

**No engine code defect was physically demonstrated, so Build 3C changes no
engine code.** The deliverables are this authority document and a focused test
file that lock the audited invariants.

---

## B. CAPITAL PROJECT BUILDING-BLOCK DOCTRINE

- Transport modes are **composable building blocks**, not fixed architectures.
- A valid candidate may use: only MRT; MRT + Manual; MRT + PTS; MRT + RP-PTS;
  MRT + robotic; PTS + RP-PTS + robotic + Manual with no MRT; mostly Manual; or
  **NO BUILD / retain existing**.
- MRT presence is **not** an optimization objective. The optimizer is
  technology-neutral.
- Ranking is target-bounded (Build 3A): once required demand is served, unused
  capacity is headroom and must not improve the primary score.
- Production capacity (Build 3B) and transport capacity both **constrain**
  patient service; neither **creates** patient demand.

---

## C. COMPLETE MODE × RESOURCE AUTHORITY MATRIX

| Resource dimension | MANUAL | ROBOTIC (RGHT / AGV_AMR) | ORDINARY PTS | RP-PTS | MRT (richer authority) |
|---|---|---|---|---|---|
| Canonical module | `conventional_transport_authority.py` | `conventional_transport_authority.py` + `transport_technology_authority.py` | `conventional_transport_authority.py` | `dedicated_rp_pts_authority.py` + `editable_default_authority.py` | `shared_mrt_multistream_authority.py` + `mrt_carrier_fleet.py` + `mrt_auxiliary_systems_authority.py` + `mrt_transport_energy_maintenance_authority.py` |
| Moving-resource unit | Porter (FTE) | Vehicle (fleet) | Carrier capsule + station | Shielded carrier + station | Carrier (per hardware class) |
| Fleet/count sizing | `compute_porter_resource_requirement` (sweep-line peak) | `agv_required_fleet_size` = max(avg-workload, peak-concurrency) | `pts_required_station_count` (peak-concurrency) | `compute_rp_pts_labor` (workload FTE); stations fixed=2 | `compute_physical_carrier_peak_concurrency` + `compute_heterogeneous_shared_carrier_fleet` (per hardware class) |
| Speed | loaded 1.1 m/s (hand) / 0.9 (cart) | 0.8 m/s | 6.0 m/s | 6.1 m/s | service-class speed (NUCLEAR 10, SPECIMEN 7, LINEN 1; PHARMACY/STERILE NOT_CALIBRATED) |
| Payload capacity | cart 20–80 kg | 150 kg | 2 kg capsule | shielded-carrier mass limit = NOT_CALIBRATED (None) | Light-MRT loaded ceiling 5.0 kg; container-class capacities |
| CapEx authority | cart purchase_capex (PROPOSED only) | vehicle $100k + integration $50k | station $45k + $250/m | $350k system reference (EVIDENCE_BASED_PLANNING_DEFAULT) + shielding delta NOT_CALIBRATED | heavy $6M base/$1M guideway-seg/$350k transition/$10k carrier OR Light $2,000/m + $1,000/endpoint + $5,000 carrier |
| OPEX authority | loaded labor (peak FTE × loaded rate) | maint $4k + energy $1.5k + residual supervision | maint $8k + energy $1k + residual labor | maint $8k + energy $1k + workload labor | carrier maint/energy PROJECT_PLANNING_ASSUMPTION + guideway maint fraction |
| Energy authority | none (human) | lumped CONTROLLED_ASSUMPTION ($1.5k/yr); distance coeff optional | lumped CONTROLLED_ASSUMPTION ($1k/yr); capsule-km coeff optional | reuses ordinary-PTS controlled rate | physics (NOT_CALIBRATED where inputs absent) OR Light-MRT 0.75 kW moving-power CONTROLLED_PLANNING_ASSUMPTION; `MRT_ENERGY_STATUS = ENERGY_SPECIFICATION_NOT_CALIBRATED` |
| Provenance | CONTROLLED_ENGINEERING_ASSUMPTION | CONTROLLED_ENGINEERING_ASSUMPTION (Telelift-class comparator, documentation only) | CONTROLLED_ENGINEERING_ASSUMPTION | EVIDENCE_BASED_PLANNING_DEFAULT + NOT_CALIBRATED shielding | USER_SUPPLIED_CONTROLLED / PROJECT_PLANNING_ASSUMPTION / physics |
| Overall status | IMPLEMENTED | IMPLEMENTED (RGHT); FLOOR_AGV_AMR = NOT_IMPLEMENTED | IMPLEMENTED | IMPLEMENTED (nuclear-only) | IMPLEMENTED (richer); legacy equal_budget carrier CapEx = NOT_MODELED |

---

## D. SERVICE-CLASS ELIGIBILITY MATRIX

Grounded in `conventional_transport_authority.TECHNOLOGY_STREAM_COMPATIBILITY`,
`dedicated_rp_pts_authority.RP_PTS_COMPATIBLE_STREAMS`,
`mrt_service_class_authority.SERVICE_CLASS_REGISTRY`, and
`stream_mode_compatibility.csv`.

| Service class | MANUAL | ROBOTIC (RGHT) | ORDINARY PTS | RP-PTS | MRT |
|---|---|---|---|---|---|
| RADIOPHARMACEUTICAL_NUCLEAR | ELIGIBLE (shielded porter) | INELIGIBLE (never assigned nuclear) | INELIGIBLE | ELIGIBLE (dedicated, nuclear-only) | ELIGIBLE (calibrated speed 10 m/s; shielding validation pending) |
| SPECIMEN_BLOOD | ELIGIBLE | INELIGIBLE | ELIGIBLE | INELIGIBLE | ELIGIBLE (calibrated speed 7 m/s) |
| PHARMACY_INFUSION | ELIGIBLE | ELIGIBLE | ELIGIBLE | INELIGIBLE | NOT_CALIBRATED (speed not established) |
| STERILE_CLEAN_SUPPLY | ELIGIBLE | ELIGIBLE | INELIGIBLE (bulk excluded) | INELIGIBLE | NOT_CALIBRATED (speed not established) |
| LAUNDRY_CLEAN_LINEN | ELIGIBLE | ELIGIBLE | INELIGIBLE (bulk excluded) | INELIGIBLE | ELIGIBLE (calibrated speed 1 m/s) but Light-MRT mass 13.5 kg > 5 kg ceiling → UNSUPPORTED_BY_LIGHT_MRT |

Eligibility is a prerequisite to optimization: lowest cost cannot make an
ineligible mode valid. Ordinary PTS is **not** universally eligible (bulk linen
and sterile totes excluded). RP-PTS is **not** interchangeable with ordinary PTS
(nuclear-only, dedicated infrastructure).

---

## E. MANUAL AUTHORITY

- `PorterOperatingPolicy` (walking/loaded speeds, dispatch/load/unload/wait/
  elevator minutes, shift hours, 85% availability, $17/hr base wage ×1.3
  employer burden — CONTROLLED_ENGINEERING_ASSUMPTION).
- `compute_manual_mission_timing`: T = dispatch + load + horizontal + vertical +
  wait + unload + **return** (symmetric reposition). Route calibrated when
  distance supplied, else `ROUTE_NOT_CALIBRATED` controlled duration.
- `compute_porter_resource_requirement`: FTE from sweep-line **peak concurrency**
  and total labor hours — never `missions/day = porters`. One porter cannot run
  overlapping missions. **IMPLEMENTED.**

---

## F. ROBOTIC / AGV / AMR / RHTS AUTHORITY

- Canonical identity: `transport_technology_authority.py` redirects legacy
  `AGV_AMR` semantic meaning to **RGHT** (Rail-Guided Hospital Transport); the
  true free-roaming `FLOOR_AGV_AMR` is a **distinct, NOT_IMPLEMENTED** class
  (`RGHT != FLOOR_AGV_AMR` invariant).
- `AgvModelClass` / `DEFAULT_AGV_MODEL`: 150 kg, 0.8 m/s, 90% availability,
  vehicle_capex $100k (kept separate from system_integration_capex $50k), maint
  $4k/yr, energy $1.5k/yr, residual supervision 0.1 FTE.
- `agv_required_fleet_size` = max(average-workload-derived, sweep-line peak
  concurrency) — never distance/speed alone. **IMPLEMENTED (RGHT economics as
  CONTROLLED_ENGINEERING_ASSUMPTION).**

---

## G. ORDINARY PTS AUTHORITY

- `PneumaticTubeNetwork` / `DEFAULT_PTS_NETWORK`: 6 stations, 300 m, 2 kg
  capsule, 6.0 m/s, station_capex $45k/unit, network $250/m, maint $8k/yr,
  energy $1k/yr, residual labor 0.2 FTE.
- `pts_new_study_capex` = stations + network length (PROPOSED only).
- `pts_required_station_count` peak-concurrency-derived (never fixed default 6).
- Compatible streams {SPECIMEN_BLOOD, PHARMACY_INFUSION}; bulk explicitly
  excluded. **IMPLEMENTED.**

---

## H. DEDICATED RP-PTS AUTHORITY

- `dedicated_rp_pts_authority.py`: RADIOPHARMACEUTICAL_NUCLEAR only; 2 stations
  (radiopharmacy source + centralized injection suite), 1 served floor.
- Editable defaults: 6.1 m/s, station handling 1.5 min, dispatch 1.0 min,
  shielded-carrier mass limit = **None (NOT_CALIBRATED)**.
- `compute_rp_pts_mission_cycle` = dispatch + source-handling + tube (L/v) +
  destination-handling.
- `compute_rp_pts_capex`: $350k system reference used as
  EVIDENCE_BASED_PLANNING_DEFAULT bundle; shielding/certification delta =
  **NOT_CALIBRATED**, explicitly **not** charged as $0 (break-even bound instead).
- `compute_rp_pts_labor`: workload-derived FTE; peak concurrency disclosed
  separately as a scheduling fact, not annual headcount.
- **Distinct from ordinary PTS. IMPLEMENTED (with disclosed NOT_CALIBRATED
  shielding).**

---

## I. MRT AUTHORITY (richer, not the legacy equal_budget path)

- `shared_mrt_multistream_authority.py`: ONE shared network + ONE shared carrier
  fleet. `MrtContainerClass` (payload container distinct from carrier;
  nuclear container `unit_capex = ALREADY_INCLUDED_IN_EXISTING_MRT_CARRIER_AUTHORITY`
  to prevent double-count). `MrtMissionWindow`, `schedule_missions_on_shared_segment`
  (non-preemptive priority scheduling on ONE `MrtNetworkSegment`).
- Fleet sizing: `compute_physical_carrier_peak_concurrency`
  (return_leg_multiplier=1.0 disclosed symmetric-transit) →
  `compute_heterogeneous_shared_carrier_fleet` sizes NUCLEAR_SHIELDED_CARRIER and
  GENERAL_LIGHT_CARRIER pools **separately** (physically non-interchangeable).
- `mrt_carrier_fleet.resolve_mrt_carrier_fleet`: carrier CapEx/OPEX/energy
  **MODELED** = PROJECT_PLANNING_ASSUMPTION tier.
- Heavy MRT CapEx: `models.PlannerAssumptions` $6M base / $1M guideway-segment /
  $350k transition / $10k carrier + `infrastructure_capex.py` "MRT carriers" line.
- Light MRT CapEx: `LIGHT_MRT_GUIDEWAY_CAPEX_PER_M` $2,000/m +
  `LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT` $1,000 + $5,000 Light carrier
  (`mrt_transport_energy_maintenance_authority.py`), replacing (never adding to)
  the heavy base/transition charges for Light-MRT only.
- Energy: `mrt_auxiliary_systems_authority.py` physics (NOT_CALIBRATED where
  inputs absent) + Light-MRT 0.75 kW moving-power CONTROLLED_PLANNING_ASSUMPTION;
  `equipment_energy_opex.MRT_ENERGY_STATUS = ENERGY_SPECIFICATION_NOT_CALIBRATED`.
- **Build 3A limitation preserved: legacy `equal_budget.py` MRT path has NO
  carrier CapEx line (NOT_MODELED), and is SEPARATE from this richer authority.
  Not reopened.**

---

## J. FLEET / CONCURRENCY AUTHORITY COMPARISON

| Mode | Fleet sizing function | Concurrency basis | Free/unlimited? |
|---|---|---|---|
| MANUAL | `compute_porter_resource_requirement` | sweep-line peak + workload FTE | NO (peak-constrained) |
| ROBOTIC | `agv_required_fleet_size` | max(avg-workload, peak concurrency) | NO |
| ORDINARY PTS | `pts_required_station_count` | max(avg-workload, peak concurrency) | NO |
| RP-PTS | `compute_rp_pts_labor` (labor) | workload FTE; peak disclosed separately | NO |
| MRT | `compute_heterogeneous_shared_carrier_fleet` | physical-cycle peak (outbound + return) per hardware class | NO |

All five size moving resources from actual mission demand and peak concurrency,
not from annual patients or one-carrier-per-patient. **IMPLEMENTED.**

---

## K. END-TO-END MISSION PARITY

- MANUAL is symmetric (includes return/reposition leg).
- ROBOTIC/PTS distribution missions are composed by
  `compute_automated_conventional_distribution_timing`:
  dispatch → automated main leg → landing handoff → **manual last mile** →
  destination handoff.
- MRT carrier occupancy uses the physical cycle (loaded-outbound + empty-return)
  for fleet sizing.
- RP-PTS cycle is source→destination station-to-station because the destination
  station IS the centralized injection suite (no further last mile), explicitly
  disclosed.
- **Finding:** mission-time components are represented per mode, but a single
  unified end-to-end chain object spanning arbitrary modes is **PARTIAL** (see
  Section L). Parity is enforced by convention/authority, not yet by one shared
  chain object.

---

## L. FIRST-MILE / LAST-MILE COMPARISON & MULTI-LEG CHAINS

- `LANDING_POINT_LAST_MILE_DISTANCE_M = 15.0` — a short local hand-off, distinct
  from the automated main leg (never reused as the full leg).
- Automated distribution = manual first mile/handoff + automated trunk + manual
  last mile — a genuine multi-leg chain, but represented as **computed timing**
  (`AutomatedConventionalMissionTiming`), not a first-class persisted chain
  object. Each `TransportMission` carries a single `transport_mode`.
- **MULTI_MODE_CHAIN_AUTHORITY = PARTIAL.**

---

## M. PAYLOAD / MASS AUTHORITY

- Distinct per-stream mass authorities exist:
  `shared_mrt_multistream_authority.LIGHT_MRT_STREAM_PAYLOAD_MASS_KG`
  (SPECIMEN/PHARMACY/STERILE 2.0 kg, CLEAN_LINEN 12.0 kg), nuclear integral
  carrier 5.0 kg, Light-MRT loaded ceiling 5.0 kg, cart 20–80 kg, AGV 150 kg,
  PTS capsule 2.0 kg.
- Empty vs loaded mass distinguished in
  `mrt_transport_energy_maintenance_authority` (empty 2.0 + payload 3.0 = 5.0
  loaded). **IMPLEMENTED** (per-stream, never one universal mass).

---

## N. CAPEX AUTHORITY BY COMPONENT

| Mode | CapEx components | PROPOSED-only gating |
|---|---|---|
| MANUAL | carts (`cart_new_study_capex`) | YES |
| ROBOTIC | vehicles + system integration (`agv_new_study_capex`) | YES |
| ORDINARY PTS | stations + network length (`pts_new_study_capex`) | YES |
| RP-PTS | $350k system bundle; shielding delta NOT_CALIBRATED | reference bundle |
| MRT heavy | base + guideway + endpoints + transitions + carriers (`infrastructure_capex.py`) | via asset_status |
| MRT light | $2,000/m guideway + $1,000/endpoint + $5,000 carrier | via `compute_light_mrt_capex` |

Composite candidate CapEx = sum of selected building-block CapEx. Shared
infrastructure charged once (Section Q). **IMPLEMENTED per mode; composite
aggregation exists only inside `evaluate_optimized_technology_mix` (PARTIAL as a
persisted candidate).**

---

## O. OPEX / MAINTENANCE AUTHORITY

- MANUAL: peak-FTE × loaded annual cost.
- ROBOTIC: `agv_annual_opex` = fleet × (maint + energy) + residual supervision.
- ORDINARY PTS: `pts_annual_opex` = maint + energy + residual labor.
- RP-PTS: `compute_rp_pts_opex` = workload labor + energy + maintenance.
- MRT: carrier maint/energy (PROJECT_PLANNING_ASSUMPTION) + guideway maintenance
  fraction (heavy 3%/yr; Light 10%/yr, distinct scopes).
- Composite OPEX = sum of selected blocks. **IMPLEMENTED per mode.**

---

## P. ENERGY AUTHORITY

| Mode | Classification |
|---|---|
| MANUAL | NOT_APPLICABLE (human) |
| ROBOTIC | CONTROLLED_ASSUMPTION (lumped $1.5k/yr; optional distance coeff, additive not substituted) |
| ORDINARY PTS | CONTROLLED_ASSUMPTION (lumped $1k/yr; optional capsule-km coeff) |
| RP-PTS | CONTROLLED_ASSUMPTION (reuses ordinary-PTS rate) |
| MRT | PHYSICS_DERIVED where inputs calibrated, else NOT_CALIBRATED (`MRT_ENERGY_STATUS`); Light-MRT 0.75 kW moving-power CONTROLLED_PLANNING_ASSUMPTION |

Omitted energy is honestly NOT_CALIBRATED, never physically zero.

---

## Q. SHARED INFRASTRUCTURE & FLEET-SHARING RULES

- Shared MRT guideway/trunk = ONE `MrtNetworkSegment`; nuclear container CapEx
  `ALREADY_INCLUDED_IN_EXISTING_MRT_CARRIER_AUTHORITY` (no double-count).
- Shared carrier pools sized once per hardware class; shared containers pooled
  by class (`compute_container_requirements_by_class`).
- Physically separate systems remain separate: ordinary PTS and dedicated RP-PTS
  are **not** merged despite both being pneumatic.
- **Double-counting prevention: IMPLEMENTED. Fleet sharing: qualified by
  payload/container/hardware-class compatibility.**

---

## R. COMPOSITE SOLUTION EXAMPLES / PROOFS

Proof candidates (illustrative compositions the building blocks can express;
NOT mandatory architecture classes; validated in
`test_build3c_transport_authority.py`):

- **A. No-MRT composite:** NUCLEAR→RP-PTS, SPECIMEN_BLOOD→PTS,
  PHARMACY→RGHT, STERILE→RGHT, LINEN→Manual.
- **B. Mixed-MRT composite:** NUCLEAR→MRT, SPECIMEN_BLOOD→MRT, LINEN→RGHT,
  exceptions→Manual.
- **C. High-MRT composite:** all MRT-eligible streams→MRT, LINEN→RGHT (Light-MRT
  mass-ineligible), exceptions→Manual.
- **D. Mostly-Manual compact facility:** all streams→Manual (valid where volumes
  are low / budget minimal).

`evaluate_optimized_technology_mix.service_technology` produces exactly this
per-service-class mapping across all five blocks with eligibility checked first.

---

## S. RETROFIT NO-BUILD TREATMENT

- `equal_budget.py` NO_BUILD_BASELINE candidate identity (Build 3A.2): a
  zero-backbone MRT-search winner is `NO_BUILD_BASELINE`, carrying the
  conventional transport basis. Retain-existing is a valid outcome; the
  optimizer does not force MRT/PTS/robots merely because they are available.
- `compute_retrofit_to_greenfield_transition_impact` reclassifies existing
  assets to PROPOSED on transition. **NO_BUILD_AUTHORITY = READY (equal_budget
  pathway).**

---

## T. CAPITAL PROJECT OPTIMIZATION READINESS MAP

| Seam | Authority | Status |
|---|---|---|
| PROJECT_CONSTRAINT_AUTHORITY | `capital_project_api.AnalyzeRequest` / `models.PlannerInputs` | PARTIAL (budget/patients/cyclotron present; **bed-count MISSING**) |
| EXISTING_RESOURCE_AUTHORITY | `PlannerInputs` (scanners/rooms/cyclotron/doses/MRT-connectable) | READY |
| MISSION_PORTFOLIO_AUTHORITY | `general_oncology_logistics.py` | READY |
| SERVICE_ELIGIBILITY_AUTHORITY | compatibility matrices + `stream_mode_compatibility.csv` | READY |
| TRANSPORT_BUILDING_BLOCK_AUTHORITY | five modules above | READY |
| TRANSPORT_CHAIN_AUTHORITY | `compute_automated_conventional_distribution_timing` | PARTIAL |
| RESOURCE_SIZING_AUTHORITY | per-mode fleet sizing functions | READY |
| CANDIDATE_COST_AUTHORITY | per-mode CapEx/OPEX + `apply_study_scope` | READY (per mode); PARTIAL (unified composite) |
| CANDIDATE_THROUGHPUT_AUTHORITY | `equal_budget` min-join; four-arch `compute_clinical_resource_peak_occupancy` (orphaned) | PARTIAL |
| CANDIDATE_RANKING_AUTHORITY | `_candidate_tie`; `qualify_architecture`/`compute_pareto_front` | READY |
| NO_BUILD_AUTHORITY | `equal_budget` NO_BUILD_BASELINE | READY |
| TRANSPORT_COMPOSITION_AUTHORITY | `OptimizedTechnologyMixResult.service_technology` | PARTIAL (result object, not persisted candidate) |

---

## U. PART 3D TRANSPORT INTEGRATION MAP

Exact authorities Part 3D should join (do **not** join feasibility yet):

```
PATIENT_DEMAND_AUTHORITY          = patient_radionuclide_demand.PatientRadionuclideDemand (Build 3B)
PRODUCTION_CAPACITY_AUTHORITY     = equal_budget._resolve_physical_eob_capacity_mbq_per_day
                                    -> cyclotron_production_windows.resolve_fleet_eob_capacity_mbq_per_day (Build 3B)
CLINICAL_RESOURCE_AUTHORITY       = whole_oncology_four_architecture_optimization.compute_clinical_resource_peak_occupancy
                                    (6/6/12 benchmark; currently ORPHANED/test-only)
TRANSPORT_COMPOSITION_AUTHORITY   = evaluate_optimized_technology_mix -> OptimizedTechnologyMixResult.service_technology (PARTIAL)
TRANSPORT_CAPACITY_AUTHORITY      = per-mode fleet sizing (porter/agv/pts/rp-pts/mrt heterogeneous fleet)
TRANSPORT_END_TO_END_TIME_AUTHORITY = compute_manual_mission_timing / compute_automated_conventional_distribution_timing
                                    / compute_rp_pts_mission_cycle / MRT mission windows
TRANSPORT_CAPEX_AUTHORITY         = per-mode *_new_study_capex + compute_light_mrt_capex / infrastructure_capex
TRANSPORT_OPEX_AUTHORITY          = per-mode *_annual_opex + compute_rp_pts_opex + MRT carrier/guideway maintenance
ARCHITECTURE_FEASIBILITY_TARGET   = whole_oncology_four_architecture_optimization.ArchitectureResult.feasible
                                    (currently hardcoded True; the join is Part 3D's job, NOT Build 3C's)
```

---

## V. REMAINING CALIBRATION GAPS

1. MRT speed for PHARMACY_INFUSION and STERILE_CLEAN_SUPPLY = NOT_CALIBRATED.
2. RP-PTS shielding/certification delta CapEx = NOT_CALIBRATED (break-even only).
3. MRT carrier/guideway electrical energy = NOT_CALIBRATED (physics unpopulated);
   Light-MRT moving power is a CONTROLLED_PLANNING_ASSUMPTION.
4. RGHT (AGV_AMR) economics = CONTROLLED_ENGINEERING_ASSUMPTION (Telelift-class
   comparator, documentation only). FLOOR_AGV_AMR = NOT_IMPLEMENTED.
5. First-class multi-leg transport chain object = MISSING (chains computed, not
   persisted).
6. Unified per-service-class TransportComposition candidate object surfaced by
   the Capital Project API = MISSING (exists only as
   `OptimizedTechnologyMixResult.service_technology`).
7. Bed-count Capital Project input = MISSING (beds only in internal four-arch
   baselines).
8. Legacy `equal_budget` MRT carrier CapEx = NOT_MODELED (Build 3A limitation,
   deliberately preserved; richer authority models it separately).
9. Four-architecture `ArchitectureResult.feasible` = hardcoded True; clinical/
   production/transport throughput join = DISCONNECTED (Part 3D scope).

---

## P. VISUAL PAYLOAD-IDENTITY DOCTRINE (Build 3C color requirement)

This section records the read-only audit of the **canonical centralized color
registry** and whether payload colors are transport-independent. All findings
are grounded in physically-read code; no palette or animation implementation
was fabricated.

### P.1 Canonical color authority (physically exists)

`mrt_service_class_authority.py` is the canonical color registry:

- `PresentationColor = Literal["VIOLET","BLUE","TEAL","AMBER","GOLD","GREEN","RED","GRAY"]`.
- Color is keyed to **service class = substance/payload identity**, via
  `ServiceClassProfile.configured_active_color` and the `SERVICE_CLASS_REGISTRY`:
  RADIOPHARMACEUTICAL_NUCLEAR → VIOLET, SPECIMEN_BLOOD → BLUE,
  PHARMACY_INFUSION → TEAL, STERILE_CLEAN_SUPPLY → AMBER,
  LAUNDRY_CLEAN_LINEN → GOLD, FOOD_NUTRITION → GREEN (inactive),
  WASTE → RED (inactive).
- `PRESENTATION_LEGEND` is the inverse map (color → service class).
- Module docstring, Section 13: *"COLOR IS PRESENTATION METADATA ONLY ... color
  never determines priority, speed, container, physics, CapEx, or OPEX"*,
  enforced by keeping `configured_active_color` / `effective_display_color`
  structurally separate from `default_priority` / `default_speed_m_per_s`.

Classification: **IMPLEMENTED** (registry); **CONTROLLED_ASSUMPTION** (hues).

### P.2 Transport-independence (verified)

- The color-bearing types (`ServiceClassProfile`, `MrtServiceMission`,
  `CarrierDispatchState`, `CarrierPresentationMetadata`) carry **no
  transport-mode / technology field**. `MrtServiceMission` fields are exactly
  `{mission_id, carrier_id, service_class, route_length_m, start_minutes,
  speed_override_m_per_s, priority_override, deadline_minutes}`.
- The color resolvers take **no transport argument**:
  `ServiceClassProfile.effective_display_color()` takes no parameters;
  `build_carrier_dispatch_state(mission)` derives color solely from
  `mission.service_class`.
- A repository-wide search for any function coupling color to a transport mode
  returns **no matches**.
- `transport_technology_authority.py` (transport-mode identity: MRT / RGHT /
  PNEUMATIC_TUBE / MANUAL_PORTER, plus NOT_IMPLEMENTED FLOOR_AGV_AMR) contains
  **no color field** — transport identity and payload color are separate modules.

Therefore the same F-18 (RADIOPHARMACEUTICAL_NUCLEAR) payload retains **VIOLET**
and the same specimen (SPECIMEN_BLOOD) payload retains **BLUE** regardless of
whether the assigned mode is MRT, PTS/RP-PTS, robotic, or Manual **where that
mode is eligible** (eligibility per Section C, not color).

### P.3 Doctrine — shape/form vs color

- **Transport shape/form identifies the transport mechanism.** In
  `openusd_yc_demo_binding.py`, `_ENTITY_GEOM_TYPE` maps
  MRT_CARRIER/RGHT_VEHICLE → `Cube`, MANUAL_PORTER/PATIENT → `Capsule`.
- **Payload color identifies the substance/service class** —
  `mrt_service_class_authority`.
- **Caveat (documented, not a defect):**
  `openusd_yc_demo_binding._ENTITY_DISPLAY_COLOR` is a **second, separate**
  presentation map keyed to *entity type* (MRT_CARRIER/RGHT_VEHICLE/
  MANUAL_PORTER/PATIENT), used only by the YC demo USD binding. It is labeled
  "presentation-only ... NEVER engineering truth." It is **not** the canonical
  payload-substance registry and does not contradict payload-color
  transport-independence (it colors demo entity glyphs, not service-class
  payloads). A future unified payload visualization should consume
  `mrt_service_class_authority`. Classification: **NOT_APPLICABLE** to payload
  identity.

### P.4 Carrier identity vs payload identity (verified)

- `MrtServiceMission.carrier_id` identifies the PHYSICAL carrier (survives
  reassignment); `mission_id` identifies one mission; service class (color)
  identifies the payload.
- `reassign_carrier(carrier_id, new_mission)` keeps the same `carrier_id` while
  color follows the new mission's service class (verified: `MRT-CARRIER-001`
  reassigned NUCLEAR→SPECIMEN keeps its id while color goes VIOLET→BLUE).
- `CarrierTrajectory` identity is per-MISSION, not per physical carrier.

### P.5 Color never affects physics/routing/capacity/economics/ranking (verified)

- Physics/decay (`compute_nuclear_retained_fraction_for_mission`,
  `compute_mission_duration_minutes`) use effective **speed** and route length,
  never color.
- Priority/speed (`resolve_effective_priority`, `resolve_effective_speed`)
  resolve from service-class defaults/overrides, "never inferred from ... color".
- `compare_nuclear_speed_what_if` confirms a nuclear speed change (10→15 m/s)
  leaves `color_unchanged=True` (and class/priority/container unchanged).
- Transport economics (Section C) and ranking
  (`equal_budget._candidate_tie`; four-arch `qualify_architecture`) take no
  color input. Color appears only in presentation dataclasses and USD
  `customData`.

### P.6 Accessibility

`AccessiblePresentationMetadata` guarantees color is **never the only**
identifier — text label, service-class id, and priority always accompany it.
Inactive classes display **GRAY** while retaining their configured color.

### P.7 Build 3C color-requirement verdicts

```
CANONICAL_COLOR_REGISTRY_EXISTS            = YES (mrt_service_class_authority.py)
PAYLOAD_COLOR_KEYED_TO_SUBSTANCE           = YES (service class)
PAYLOAD_COLOR_TRANSPORT_INDEPENDENT        = YES (no transport-mode field/arg anywhere)
SHAPE_IDENTIFIES_TRANSPORT_MECHANISM       = YES (openusd geom type; transport_technology_authority)
SAME_PAYLOAD_SAME_COLOR_ACROSS_MODES       = YES (color from service class only, where mode eligible)
CARRIER_IDENTITY_SEPARATE_FROM_PAYLOAD     = YES (carrier_id persists; color follows payload)
COLOR_AFFECTS_PHYSICS_ROUTING_CAPACITY_ECON_RANKING = NO (presentation metadata only)
PALETTE_OR_ANIMATION_IMPLEMENTATION_FABRICATED = NO (audited existing authorities only)
SECOND_DEMO_ENTITY_COLOR_MAP_NOTED         = YES (openusd_yc_demo_binding; entity-glyph, not payload)
```

No color-related engine defect was demonstrated. Build 3C adds only focused
tests that lock these invariants; no production code is changed.

---

*End of FIVE_MODE_TRANSPORT_AUTHORITY_BUILD_3C.md*

---

# BUILD 3C ADDENDUM — VISUAL-IDENTITY & ROUTE SEMANTICS

Read-only audit of visualization/color/trajectory/route authorities. No engine
code changed. Every classification below is grounded in physical repository
code. Where an authority is absent it is recorded `NOT_MODELED` — no code was
invented to satisfy a test.

## AA. SHAPE / COLOR / ROUTE SEPARATION (governing doctrine)

Three independent concepts, kept structurally separate in code:

- **SHAPE / FORM** = transport technology (entity_type: MRT_CARRIER,
  RGHT_VEHICLE, MANUAL_PORTER, PATIENT — `openusd_yc_demo_binding._ENTITY_GEOM_TYPE`).
- **PAYLOAD COLOR** = substance / service class
  (`mrt_service_class_authority.PresentationColor`: VIOLET=nuclear, BLUE=specimen,
  TEAL=pharmacy, AMBER=sterile, GOLD=linen). Presentation metadata only; never
  affects physics/priority/speed/CapEx/OPEX.
- **ROUTE NETWORK** = physical path available to that technology (separate
  canonical networks per mode; Section AF/AG).

F-18 via RP-PTS and F-18 via MRT share the same nuclear payload color but differ
in form, route network, timing, and infrastructure — confirmed separable.

## AB. PAYLOAD DELIVERY / COLOR TRANSFER

- Payload delivery-state (delivered/consumed/absorbed): **NOT_MODELED**. The
  scene contract (`dynamic_scene_state_authority.DynamicObjectState` /
  `MovementState`) terminates at motion_state `COMPLETE` — a motion state, not a
  payload-consumption semantic. No payload field, no delivery event.
- Payload/service-class color lives on the **carrier mission**
  (`CarrierDispatchState.effective_display_color`), never on the patient or the
  room. It does **not** transfer on delivery (there is no delivery event and no
  patient/room color state to receive it).

```
PAYLOAD_DELIVERY_COLOR_TRANSFER = DOES_NOT_TRANSFER (payload delivery-state NOT_MODELED; carrier/service-class color never transfers to patient or room)
```

## AC. PATIENT VISUAL IDENTITY

- No canonical patient color palette authority exists. The only patient color is
  a flat presentation constant `openusd_yc_demo_binding._ENTITY_DISPLAY_COLOR["PATIENT"]
  = (0.15, 0.75, 0.30)`, keyed strictly by `entity_type`. It is documented
  "NEVER engineering truth."
- Because color is keyed by entity_type (not payload), a patient never inherits
  F-18 / blood / pharmacy color after interacting with that material.

```
CANONICAL_PATIENT_COLOR_AUTHORITY = NONE (only a per-entity-type demo constant in openusd_yc_demo_binding._ENTITY_DISPLAY_COLOR; no canonical palette)
PATIENT_COLOR_CHANGES_WITH_PAYLOAD = NO
PATIENT_COLOR_AUTHORITY = PARTIAL (flat demo color; no authority)
PATIENT_COLOR_STABLE = YES (keyed by entity_type, independent of payload)
```

Intended (not-yet-implemented) doctrine, documented separately from the current
palette: a neutral/silver patient identity is the intended future canonical
patient color. **NOT_MODELED** today — no final color invented.

## AD. ROOM VISUAL IDENTITY

- No room presentation color/material/appearance authority exists. Rooms in
  `canonical_spatial_authority` carry transform/type/provenance but no color.
- No room recolors when a payload enters (no delivery event, no room color state).

```
ROOM_COLOR_CHANGES_WITH_PAYLOAD = NO
ROOM_COLOR_STABLE = YES (NOT_MODELED — no room color state exists to change)
```

## AE. STAFF / PORTER VISUAL IDENTITY

- Porter color is a distinct demo constant
  `_ENTITY_DISPLAY_COLOR["MANUAL_PORTER"] = (0.95, 0.65, 0.10)` — distinct from
  PATIENT (green) and from the MRT service-class payload palette.
- The porter color identifies the HUMAN RESOURCE; the carried payload color
  identifies the PAYLOAD. A porter carrying F-18 remains porter-colored while the
  payload retains its VIOLET service-class color; the porter is never recolored
  by payload.

```
CANONICAL_STAFF_COLOR_AUTHORITY = NONE (per-entity-type demo constant only; no authority-level staff palette)
STAFF_COLOR_AUTHORITY = PARTIAL (distinct porter demo color)
STAFF_COLOR_DISTINCT_FROM_PATIENT = YES
STAFF_COLOR_DISTINCT_FROM_PAYLOAD_SEMANTICS = YES (entity_type color vs service-class PresentationColor are separate authorities)
STAFF_PAYLOAD_COLOR_SEPARATION = YES
```

## AF. PATIENT / STAFF POSITION TRACKING (XYZT)

- Patient spatial trajectory: **IMPLEMENTED** —
  `production_trajectory_authority.build_patient_trajectory` →
  `_build_human_trajectory` produces `MovingEntityTrajectory` with
  `TrajectorySample(time_minutes, x_m, y_m, z_m, motion_state, route_edge_id,
  progress_fraction)` over the human pedestrian network. Clinical times
  (injection/uptake/scan) also live on `hybrid_optimization.HybridPatientTrace`
  (t + room/floor, no x/y/z).
- Staff/porter spatial trajectory: **IMPLEMENTED** —
  `build_porter_trajectory` uses the same builder with `entity_type="MANUAL_PORTER"`
  / `WALKING_PORTER` mode. Patient and porter are distinct entity types over one
  shared pedestrian network. No dedicated staff-roster spatial model beyond
  porter transport trajectories.

```
PATIENT_XYZT_TRACKING = IMPLEMENTED (spatial trajectory) + clinical times on HybridPatientTrace
STAFF_XYZT_TRACKING = IMPLEMENTED (porter spatial trajectory; no separate staff-roster model)
```

## AG. ROUTE NETWORK AUTHORITIES

- MANUAL: routes over the human-accessible circulation network
  (`human_circulation_authority.resolve_pedestrian_route`, corridors/doors/
  elevators via `canonical_spatial_authority` object types). Explicitly **never
  straight-line-through-walls**, never PTS/MRT geometry.
- Each automated mode routes over its **own distinct** canonical network via the
  one shared BFS solver (`canonical_spatial_authority.resolve_route`, mode-tagged
  edges):

```
MANUAL_ROUTE_NETWORK        = human_circulation_authority pedestrian network (corridors/doors/elevators) — IMPLEMENTED
MANUAL_USES_HUMAN_CORRIDORS = YES
ROBOTIC_ROUTE_NETWORK       = rght_spatial_network_authority (RGHT track/station/switch; mode tag AGV_AMR) — IMPLEMENTED
PTS_ROUTE_NETWORK           = pts_spatial_network_authority (tube/station/junction; route metadata; timing NOT_CALIBRATED) — IMPLEMENTED (geometry), timing NOT_CALIBRATED
RP_PTS_ROUTE_NETWORK        = dedicated_rp_pts_authority (reuses MRT guideway trunk length; no own graph) — PARTIAL
MRT_ROUTE_NETWORK           = MRT network via canonical_spatial_authority.resolve_route(mode=MRT) + production_clinical_schedule._resolve_mrt_route_profile (facility engineering model) — IMPLEMENTED
```

MRT may use concealed/service/shaft/behind-wall routes per the facility
engineering model — the exact route always comes from canonical spatial
authority, never hard-coded HVAC ducts.

## AH. GEOMETRY-CHANGE → ROUTE RECOMPUTATION READINESS

- MRT: **IMPLEMENTED (native, live)** — `production_clinical_schedule._resolve_mrt_route_profile`
  reads `FacilityEngineeringObjectModel` geometry and recomputes
  horizontal/vertical distance + travel time; changing geometry propagates into
  mission distance/time directly.
- AGV / ORDINARY PTS / RP-PTS: **PARTIAL** — resolvable via
  `authoritative_geometry_routing_activation.resolve_automatic_route_distance_m`
  (canonical-graph-derived distance, else shared MRT reference corridor, else
  controlled default) and `transport_mission_route_bridge.resolve_mission_route`,
  but not yet auto-wired into the frozen four-architecture economic pipeline
  (explicit-override / separate-activation only).

```
GEOMETRY_CHANGE_ROUTE_RECOMPUTATION_READINESS = IMPLEMENTED (MRT native/live); PARTIAL (AGV/PTS/RP-PTS resolvable, not auto-wired into frozen economics)
```

Full BIM/What-If spatial recomputation is **not** implemented here (out of scope);
only the existing route/spatial authorities and readiness gaps are identified.

## AI. ADDENDUM SUMMARY

```
PAYLOAD_DELIVERY_COLOR_TRANSFER              = DOES_NOT_TRANSFER (delivery-state NOT_MODELED)
PATIENT_COLOR_AUTHORITY                      = NONE (demo constant only; PARTIAL)
PATIENT_COLOR_STABLE                         = YES
ROOM_COLOR_STABLE                            = YES (room color NOT_MODELED)
STAFF_COLOR_AUTHORITY                        = NONE (demo constant only; PARTIAL, distinct porter color)
STAFF_PAYLOAD_COLOR_SEPARATION               = YES
PATIENT_XYZT_TRACKING                        = IMPLEMENTED
STAFF_XYZT_TRACKING                          = IMPLEMENTED (porter)
MANUAL_ROUTE_NETWORK                         = human corridors (IMPLEMENTED)
ROBOTIC_ROUTE_NETWORK                        = RGHT network (IMPLEMENTED)
PTS_ROUTE_NETWORK                            = PTS tube network (IMPLEMENTED geometry; NOT_CALIBRATED timing)
RP_PTS_ROUTE_NETWORK                         = reuses MRT guideway length (PARTIAL)
MRT_ROUTE_NETWORK                            = MRT network via canonical spatial authority (IMPLEMENTED)
GEOMETRY_CHANGE_ROUTE_RECOMPUTATION_READINESS = IMPLEMENTED (MRT); PARTIAL (automated economic wiring)
```

*End of Build 3C addendum.*

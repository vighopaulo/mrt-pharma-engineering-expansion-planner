# SPATIAL ROUTE / NETWORK AUTHORITY — BUILD 3C.1

**Status: repository-grounded spatial-routing authority report (read-only audit).**
**Baseline: `main` @ `85b10a7` (Build 3C complete, committed). No engine code changed by Build 3C.1.**
**Deliverables: this document + `test_build3c1_spatial_route_authority.py` focused tests only.**

Build 3C.1 audits the spatial routing authority that connects facility geometry
to the transport building blocks from Build 3C, normalized into two canonical
route families. Every classification is grounded in physical repository code
and verified empirically; classifications are IMPLEMENTED / PARTIAL /
CONTROLLED_ASSUMPTION / NOT_MODELED / NOT_APPLICABLE (and CONNECTED / PARTIAL /
DISCONNECTED for propagation seams).

---

## A. EXECUTIVE FINDING

The two-route-family doctrine is **already substantially implemented** in the
repository with strong governance:

- **HUMAN_CIRCULATION_NETWORK** — `human_circulation_authority.py` resolves
  patient and porter routes over one shared pedestrian graph
  (`resolve_pedestrian_route`), and AGV/RGHT rides the same family with
  mode-specific edge eligibility.
- **CONCEALED_SERVICE_TRANSPORT_CORRIDOR** — MRT, RGHT, ordinary PTS, and
  RP-PTS each have distinct first-class network object types and their own
  lane, resolved through `transport_mission_route_bridge.resolve_mission_route`
  over the shared mode-subgraph BFS solver `canonical_spatial_authority.resolve_route`.

The core solver already enforces "shared right-of-way ≠ shared physical track":
edges carry a `compatible_modes` frozenset, and BFS runs over only the
mode-compatible subgraph. Geometry changes recompute routes because
`replace_transform` returns a new registry and `resolve_route` is stateless.
Per-mode XYZT trajectory builders exist. **No genuine route-binding defect was
demonstrated, so Build 3C.1 changes no engine code.** Remaining gaps
(route cache/geometry hash, decay-time-to-route binding, shared civil
right-of-way cost) are documented honestly; the decay-time binding is
deliberately left unwired because Section 26 forbids modifying Build 3B physics.

---

## B. TWO-ROUTE-FAMILY DOCTRINE

```
FACILITY
  HUMAN_CIRCULATION_NETWORK              (human_circulation_authority.py)
      PATIENT     -> TransportMode "PATIENT_MOVEMENT"
      PORTER      -> TransportMode "WALKING_PORTER"
      AGV/AMR     -> TransportMode "AGV_AMR" (RGHT) with mode-specific eligibility
  CONCEALED_SERVICE_TRANSPORT_CORRIDOR   (mode-specific network authorities)
      MRT lane    -> canonical_spatial_authority MRT_* objects, mode "MRT"
      RHTS/RGHT   -> rght_spatial_network_authority.py RGHT_* objects, mode "AGV_AMR"
      PTS lane    -> pts_spatial_network_authority.py PTS_* objects, mode "PNEUMATIC_TUBE"
      RP-PTS lane -> dedicated_rp_pts_authority.py (distinct dedicated tube)
```

Core solver: `canonical_spatial_authority.resolve_route(graph, origin,
destination, mode)` — BFS over `graph.edges_for_mode(mode)` only. Each
`SpatialEdge` carries `compatible_modes: frozenset[TransportMode]`. **Verified
empirically:** with a human corridor edge (40 m, modes {PATIENT_MOVEMENT,
WALKING_PORTER, AGV_AMR}) and a distinct MRT edge (25 m, mode {MRT}) between the
same two rooms, a patient resolves the 40 m human edge and MRT resolves the
25 m concealed edge — they never cross.

---

## C. HUMAN CIRCULATION NETWORK

`human_circulation_authority.py` (Transport Spatial Authority Build 4):
- `resolve_pedestrian_route(registry, graph, subject, origin, destination)` —
  ONE route-resolution function for both PATIENT and PORTER; they differ only in
  which existing `TransportMode` is passed (`PATIENT_MOVEMENT` vs
  `WALKING_PORTER`), never in algorithm.
- Shared human speed: `HUMAN_WALKING_SPEED_M_PER_S` (1.2 m/s) and
  `HUMAN_ELEVATOR_SPEED_M_PER_S` (1.0 m/s) reused verbatim from
  `PlannerAssumptions` — CONTROLLED_ENGINEERING_ASSUMPTION, not a new value.
- Corridors/elevators are canonical objects (`SpatialObjectType` already
  includes CORRIDOR/ELEVATOR/STAIR/DOOR/SHAFT).
- Returns honest `ROUTE_NOT_CALIBRATED` / `ROUTE_UNAVAILABLE` where geometry is
  insufficient — never straight-line-through-walls at spatial fidelity.

**Status: IMPLEMENTED.**

---

## D. PATIENT ROUTING

- Patient uses HUMAN_CIRCULATION_NETWORK (`PATIENT_MOVEMENT`).
- `compute_patient_travel_minutes(route)` — the first production patient-travel
  time authority (horizontal/HUMAN_WALKING + vertical/HUMAN_ELEVATOR); returns
  `NOT_CALIBRATED` when the route is uncalibrated.
- `production_trajectory_authority.build_patient_trajectory` produces full XYZT
  samples with `entity_type="PATIENT"` (never counted as porter labor; never
  fabricates a PATIENT_ROOM→injection leg).
- Clinical scheduling remains separate from spatial routing (unchanged).

**Status: IMPLEMENTED.**

---

## E. PORTER ROUTING

- Porter uses HUMAN_CIRCULATION_NETWORK (`WALKING_PORTER`); payload follows the
  porter trajectory (separate porter/payload/service-class/color identities).
- Distance feeds the existing `conventional_transport_authority.compute_manual_mission_timing`
  (`ROUTE_CALIBRATED` when `horizontal_distance_m` supplied, else
  `ROUTE_NOT_CALIBRATED` controlled duration) and `compute_porter_resource_requirement`.
- `build_porter_trajectory` produces XYZT with an optional dispatch/WAITING
  prefix. Manual distance is the human route, never Euclidean-through-walls.

**Status: IMPLEMENTED.**

---

## F. AGV / AMR ROUTING

- Repository canonical identity: `AGV_AMR` normalizes to **RGHT** (Rail-Guided
  Hospital Transport) via `transport_technology_authority.normalize_transport_technology`;
  the true free-roaming `FLOOR_AGV_AMR` is a DISTINCT class,
  `FLOOR_AGV_AMR_IMPLEMENTED = False`.
- The RGHT installed network (`rght_spatial_network_authority.py`) uses the
  concealed-service family with its own `RGHT_*` object types, tagging edges
  with the `AGV_AMR` `TransportMode`. A human edge existing does not
  automatically make an AGV/RGHT edge eligible — eligibility is per-edge
  `compatible_modes`.

**Status: IMPLEMENTED (RGHT); FLOOR_AGV_AMR = NOT_IMPLEMENTED.**

---

## G. CONCEALED SERVICE TRANSPORT CORRIDOR

Each concealed mode is a first-class canonical network, never a shared installed
track:

- `canonical_spatial_authority.SpatialObjectType` includes `MRT_TRUNK/BRANCH/
  SEGMENT/JUNCTION/ENDPOINT/CARRIER/CONTAINER/VESTIBULE`,
  `RGHT_TRACK_SEGMENT/STATION/SWITCH/VERTICAL_SEGMENT/VEHICLE`,
  `PTS_STATION/TUBE_SEGMENT/JUNCTION/VERTICAL_SEGMENT/CAPSULE`.
- `transport_mission_route_bridge.resolve_mission_route` answers "do we have a
  real calibrated route for this mission?" per mode, honestly reporting
  `SPATIAL_NETWORK_NOT_CALIBRATED` / `ROUTE_NOT_CALIBRATED` / `ROUTE_UNAVAILABLE`
  / `ROUTE_CALIBRATED`. **Verified:** a PTS request with no PTS-eligible edge
  returns `SPATIAL_NETWORK_NOT_CALIBRATED`.

**Status: IMPLEMENTED.**

---

## H. MRT LANE

- Richer MRT spatial authority (`canonical_spatial_authority` MRT objects +
  `production_trajectory_authority.resolve_mrt_route_and_build_mission` /
  `build_mrt_trajectory`) derives `route_length_m` ONLY from `resolve_route`,
  never a hard-coded constant; timing from `mrt_service_class_authority.mission_effective_speed`.
- MRT does not use HUMAN_CIRCULATION_NETWORK as its trunk (distinct `MRT` mode
  edges).

**Status: IMPLEMENTED.**

---

## I. RHTS / RGHT LANE

- `rght_spatial_network_authority.py`: own `RGHT_*` object types, own track,
  vehicle, speed (`DEFAULT_AGV_MODEL.speed_m_per_s`); reuses the common route
  solver via the `AGV_AMR` `TransportMode` value. `MRT_AND_RGHT_SHARE_ENGINEERING_
  INFRASTRUCTURE_OBJECTS = NO`. May run parallel to MRT; never shares MRT
  guideway.

**Status: IMPLEMENTED.**

---

## J. ORDINARY PTS LANE

- `pts_spatial_network_authority.py`: own `PTS_*` object types, own tube;
  reuses the common route solver via `PNEUMATIC_TUBE`. Ordinary-PTS timing is
  the flat `dispatch_minutes + station_handling_minutes` (~2.5 min) doctrine;
  `PTS_ROUTE_BASED_TIMING = NOT_CALIBRATED` (route metadata attached but timing
  numerics unchanged).

**Status: IMPLEMENTED (geometry); route-based timing NOT_CALIBRATED.**

---

## K. RP-PTS LANE

- `dedicated_rp_pts_authority.py`: RADIOPHARMACEUTICAL_NUCLEAR only; distinct
  from ordinary PTS (2-station centralized topology, 6.1 m/s vs 6.0).
- `compute_rp_pts_mission_cycle` DOES add a real route-based term
  `tube_transport = network_length_m / speed` (**verified: 4.607 min at 222 m**).

**Status: IMPLEMENTED (distinct dedicated lane).**

---

## L. PARALLEL-LANE / RIGHT-OF-WAY DOCTRINE

- Shared right-of-way ≠ shared physical track. Each mode owns its object types;
  no shared installed-network object exists.
- `authoritative_geometry_routing_activation.derive_shared_reference_corridor_route`
  and `SHARED_CORRIDOR_ELIGIBLE_MODES` (AGV / ORDINARY_PTS / DEDICATED_RP_PTS)
  let a mode borrow the MRT reference corridor's **distance only**; speed,
  capacity, and economics remain mode-specific.
- Installation state is per lane (a mode is not installed merely because the
  corridor exists) — expressed by whether mode-eligible edges/objects exist.

**Status: IMPLEMENTED (planning-level shared centerline + distinct lane identity).**

---

## M. TRUE-ORIGIN / TRUE-DESTINATION INTERFACES

- Build 3C end-to-end parity is preserved. Mission routes resolve true origin →
  destination via canonical object ids; station/endpoint objects are the
  transfer interfaces.
- Multi-leg transfers (manual first mile → automated trunk → manual last mile)
  are computed in `conventional_transport_authority.compute_automated_conventional_distribution_timing`,
  but a first-class persisted multi-leg chain object is **PARTIAL** (computed
  timing, not a stored chain), consistent with the Build 3C finding.

**Status: PARTIAL (interfaces exist; unified chain object is a known gap).**

---

## N. MULTI-BUILDING ROUTING

- The geometry model is N-building: `add_building`/`add_floor`/`add_room` with
  building-scoped floor ids (`default_floor_object_id`), `resolve_global_position`
  accumulates the parent chain, `compute_global_distance` gives real Euclidean
  distance. Human and concealed-service families may have different path lengths
  between the same buildings (distinct edges).

**Status: IMPLEMENTED.**

---

## O. GEOMETRY-CHANGE INVALIDATION

- `SpatialObjectRegistry.replace_transform` returns a NEW registry (non-mutating;
  children move rigidly via relative transforms). **Verified: moving BLDG-B from
  x=100 to x=300 recomputes distance 100 m → 300 m; the original registry is
  unchanged.**
- `resolve_route` is stateless and recomputes every call, so a changed edge
  length is reflected immediately on the next resolution.

**Status: IMPLEMENTED.**

---

## P. WHAT-IF SPATIAL RECOMPUTATION

- `LockedSpatialState` is never mutated. `WhatIfSpatialState.branch_from` clones
  the registry; `apply_changeset` mutates only the clone; `reset_to_locked` /
  `undo_last_change` are reversible; `promote_what_if_to_simulation_input` is
  explicit. `compute_delta` gives locked-vs-what-if. **Verified: branch does not
  share the base registry object.**
- Scenario/plan version identity: `lockdown_what_if_lineage_authority.py`
  (LockdownStatus CURRENT/SUPERSEDED, PlanVersionScenarioBinding).

**Status: IMPLEMENTED (version semantics; no UI, as required).**

---

## Q. ROUTE → TIME PROPAGATION

| Mode | Authority | Status |
|---|---|---|
| PATIENT | `human_circulation_authority.compute_patient_travel_minutes` | CONNECTED |
| PORTER | `conventional_transport_authority.compute_manual_mission_timing` (`horizontal_distance_m`) | CONNECTED |
| AGV/RGHT | `production_trajectory_authority.build_rght_trajectory` (per-edge speed) | CONNECTED |
| MRT | `mrt_service_class_authority.mission_effective_speed` via `build_mrt_trajectory` | CONNECTED |
| ORDINARY PTS | flat dispatch+handling (~2.5 min); `PTS_ROUTE_BASED_TIMING = NOT_CALIBRATED` | NOT_CALIBRATED |
| RP-PTS | `dedicated_rp_pts_authority.compute_rp_pts_mission_cycle` (`L/v` term) | CONNECTED |

At Level 0/1 controlled analysis, scalar assumptions remain valid and are
labeled accordingly.

---

## R. ROUTE → FLEET / RESOURCE PROPAGATION

- `conventional_transport_authority.agv_required_fleet_size` /
  `pts_required_station_count` / `compute_porter_resource_requirement` all
  consume route-derived `mission_minutes`, so a changed route length/time can
  propagate into fleet/resource sizing.

**Status: CONNECTED (capable — activation depends on caller passing recomputed mission_minutes).**

---

## S. ROUTE → INFRASTRUCTURE PROPAGATION

- `authoritative_geometry_routing_activation.compute_installed_network_union`
  unions unique edges (a shared segment counted once, never `sum(route.distance)`).
- `reconcile_installed_mrt_network` reconciles geometry-derived installed length
  vs the frozen HybridEvaluationResult reference (MATCH / EXPLAINED_DIFFERENCE /
  TRUE_DEFECT).
- RGHT/PTS infrastructure quantities sum `length_m` over mode-tagged edges.

**Status: CONNECTED (MRT/RGHT/PTS); INSTALLED_NETWORK_GEOMETRY distinct from MISSION_ROUTE_GEOMETRY.**

---

## T. ROUTE → CAPEX / OPEX / ENERGY PROPAGATION

- CapEx: `infrastructure_capex` guideway length × `guideway_capex_per_m`;
  `canonical_spatial_authority.mrt_segment_length_capex`;
  `reactive_engineering_economic_consequence_authority.compute_pts_capex_with_installed_length`.
- OPEX: `reactive_engineering_economic_consequence_authority` move-building /
  move-endpoint / move-scanner — guideway maintenance ALWAYS reacts to the
  installed-network CapEx delta; MRT mission energy reacts only when the caller
  proves a genuine mission-distance change (`MrtMissionEnergyInputs`).
- **GOTCHA:** the live four-architecture CapEx/OPEX/NPV pipeline is NOT rewired
  to these functions — that is a separate, protected activation step
  (FROZEN_CANONICAL_QUALIFICATION_CASE). Unit-cost calibration was not changed.
- RP-PTS CapEx is a published-reference bundle, not length-driven → RP-PTS
  route→CapEx = DISCONNECTED.

**Status: CONNECTED (MRT/RGHT/PTS length→CapEx and MRT maintenance OPEX); PARTIAL overall; RP-PTS route→CapEx DISCONNECTED.**

---

## U. RADIOACTIVE-DECAY TIMING LINKAGE

- Decay physics (`multi_isotope_decay.retained_fraction`) takes an
  `elapsed_minutes` scalar. Today that elapsed time is **schedule/handling-derived**
  (`cycle_relative_production_requirement._required_eob_for_cycle` uses
  administration_time − cycle EOB; `external_supply_hub_spoke` uses handling
  minutes), **not** the resolved spatial route time.
- RP-PTS (`compute_rp_pts_mission_cycle`) and patient/porter route times exist
  but are **not wired** into the decay elapsed input.

**Status: DISCONNECTED (documented gap). NOT fixed here: Section 26 forbids
modifying Build 3B production/activity mathematics; only the spatial/time
binding could be established, and doing so safely requires touching the decay
consumer, which is out of Build 3C.1 scope.**

---

## V. HUMAN / AUTOMATED TRAJECTORY READINESS

`production_trajectory_authority.py` — one unified `MovingEntityTrajectory` /
`TrajectorySample` contract + `resolve_entity_state_at_time`:

```
PATIENT_XYZT_TRACKING          = IMPLEMENTED (build_patient_trajectory)
PORTER_XYZT_TRACKING           = IMPLEMENTED (build_porter_trajectory)
AGV_TRAJECTORY_AUTHORITY       = IMPLEMENTED (build_rght_trajectory; RGHT)
MRT_TRAJECTORY_AUTHORITY       = IMPLEMENTED (build_mrt_trajectory)
RHTS_TRAJECTORY_AUTHORITY      = IMPLEMENTED (= RGHT builder)
PTS_TRAJECTORY_AUTHORITY       = PARTIAL (spatial path always; time only if calibrated_start_time supplied)
RP_PTS_TRAJECTORY_AUTHORITY    = PARTIAL (via build_pts_trajectory calibrated path)
FLOOR_AGV_AMR                  = NOT_IMPLEMENTED
```

XYZ come from `resolve_global_position` along resolved route edges; scene
composition via `operational_day_trajectory_scene` / `digital_twin_simulation_state`
/ `dynamic_scene_state_authority`. Colors/forms unchanged (Build 3C doctrine).

---

## W. RETROFIT / GREENFIELD SPATIAL SEMANTICS

- Retrofit: existing corridors/elevators + existing installed lanes (e.g. an
  existing PTS) are retained; an existing concealed service corridor does NOT
  imply an existing MRT (distinct object types). `compute_retrofit_to_greenfield_transition_impact`
  reclassifies existing assets to PROPOSED on transition.
- Greenfield: both families may be designed from the facility program (Build
  3C.1 establishes the route authority, not generative architectural design).

**Status: IMPLEMENTED (lane-state distinction); generative design out of scope.**

---

## X. ROUTE FIDELITY LEVELS

Level 0 (controlled assumption) → Level 1 (benchmark geometry) → Level 2
(facility program) → Level 3 (spatial facility model: actual
HUMAN_CIRCULATION_NETWORK + CONCEALED_SERVICE_TRANSPORT_CORRIDOR routes) →
Level 4 (digital twin with operational state/trajectories). The route result
preserves calibration status (`ROUTE_CALIBRATED` / `ROUTE_NOT_CALIBRATED` /
`SPATIAL_NETWORK_NOT_CALIBRATED` / `ROUTE_UNAVAILABLE`), so a Level 0/1 estimate
is never silently upgraded to Level 3/4 authority.

```
ROUTE_FIDELITY_LEVEL          = per-result (calibration status preserved)
ROUTE_DISTANCE_SOURCE         = canonical_spatial_authority.resolve_route (edge length_m) at Level 3+
ROUTE_GEOMETRY_QUALIFICATION  = ROUTE_CALIBRATED / ROUTE_NOT_CALIBRATED / SPATIAL_NETWORK_NOT_CALIBRATED / ROUTE_UNAVAILABLE
```

---

## Y. CAPITAL PROJECT COMPOSITION INTEGRATION SEAMS

```
ROUTE_FAMILY_SELECTION_AUTHORITY = transport_mission_route_bridge + human_circulation_authority (READY)
LANE_INSTALLATION_AUTHORITY      = per-mode object presence / edges_for_mode (READY)
ROUTE_DISTANCE_AUTHORITY         = canonical_spatial_authority.resolve_route (READY)
ROUTE_TIME_AUTHORITY             = per-mode route→time (READY except ordinary PTS NOT_CALIBRATED)
ROUTE_TO_INFRASTRUCTURE_AUTHORITY= compute_installed_network_union / reconcile_installed_mrt_network (READY)
ROUTE_TO_FLEET_AUTHORITY         = agv_required_fleet_size / pts_required_station_count / porter FTE (PARTIAL — caller must pass recomputed mission_minutes)
ROUTE_TO_CAPEX_AUTHORITY         = infrastructure_capex / mrt_segment_length_capex / compute_pts_capex_with_installed_length (PARTIAL — live four-arch pipeline not rewired)
ROUTE_TO_OPEX_AUTHORITY          = reactive_engineering_economic_consequence_authority (PARTIAL)
```

---

## Z. PART 3D INTEGRATION SEAMS

Build 3C.1 may determine `ROUTE_AVAILABLE` / spatial transport qualification. It
does NOT compute overall `ArchitectureResult.feasible` (production + clinical +
transport + staff + rooms) — that join remains Part 3D. The seams Part 3D will
consume:

```
TRANSPORT_FEASIBILITY_AUTHORITY  = transport_mission_route_bridge.resolve_mission_route route_status
TRANSPORT_CAPACITY_AUTHORITY     = per-mode fleet sizing (Build 3C) fed by route→time
TRANSPORT_COMPOSITION_AUTHORITY  = evaluate_optimized_technology_mix.service_technology (Build 3C, PARTIAL)
ARCHITECTURE_FEASIBILITY_TARGET  = whole_oncology_four_architecture_optimization.ArchitectureResult.feasible (unchanged; Part 3D's job)
```

---

## AA. REMAINING SPATIAL GAPS

1. Route cache = NOT_MODELED (unnecessary today: `resolve_route` is stateless,
   so no stale route can survive a geometry change; but a cache with geometry-
   version keying would be needed for a large digital-twin performance layer).
2. Geometry-content version/hash = PARTIAL (scenario/plan lineage version exists;
   no per-registry content hash to key a future route cache).
3. Radioactive-decay ↔ route-time binding = DISCONNECTED (route/mission times
   exist; decay elapsed is schedule/handling-derived; not wired — Section 26
   forbids changing Build 3B physics here).
4. Ordinary-PTS route-based timing = NOT_CALIBRATED (flat dispatch+handling).
5. RP-PTS route→CapEx = DISCONNECTED (bundle reference, not length-driven).
6. Shared architectural/civil right-of-way cost = NOT_MODELED (no civil shell
   cost line distinct from mode-specific lane cost).
7. FLOOR_AGV_AMR = NOT_IMPLEMENTED (distinct from RGHT; deliberately absent).
8. Live four-architecture CapEx/OPEX pipeline not rewired to the geometry-derived
   length functions (FROZEN_CANONICAL_QUALIFICATION_CASE; separate activation step).
9. First-class multi-leg transport chain object = PARTIAL (chains computed, not
   persisted) — inherited Build 3C gap.

---

*End of SPATIAL_ROUTE_NETWORK_AUTHORITY_BUILD_3C1.md*

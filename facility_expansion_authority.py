"""Facility Expansion Authority (Transport / Facility Spatial Authority
Build 4A): Continuous Horizontal Expansion and Discrete Vertical Functional
Expansion Closure.

GOVERNANCE: this module owns ONLY horizontal expansion requests, vertical
expansion requests, reference-floor replication, expansion lineage, and
expansion validation. It orchestrates EXISTING authorities
(`canonical_spatial_authority.resolve_global_position`/
`compute_global_distance`/`apply_changeset`, `human_circulation_authority`,
`rght_spatial_network_authority`, `pts_spatial_network_authority`,
`canonical_entity_binding_authority.bind_patient_room`,
`oncology_pet_spect_scenario.required_scanner_count`,
`multi_isotope_decay.retained_fraction`/`required_upstream_activity`,
`dedicated_rp_pts_authority.compute_rp_pts_mission_cycle`). It is NOT a
route solver, NOT an economic engine, NOT a clinical scheduler, NOT an
optimizer, and NOT an animation authority.

AUDIT (performed before writing anything):

  Geometry hierarchy -- `canonical_spatial_authority.resolve_global_position`
    already accumulates `x_global = R*x_local + t` up the parent chain
    (object -> floor -> building -> facility). This means a building's own
    `Transform` can be moved WITHOUT touching any descendant's own (locally
    stored) `Transform` -- descendants' GLOBAL positions shift automatically
    (section 28G: "child geometry moves with expanded parent"). This module
    reuses `resolve_global_position`/`compute_global_distance` directly --
    never a second coordinate-accumulation algorithm.

  Route/network rebuilding -- Build 2/3/4's controlled proof-network
    builders (`rght_spatial_network_authority`/`pts_spatial_network_
    authority`/`human_circulation_authority`) compute `SpatialEdge.length_m`
    ONCE at build time from object coordinates; they do not re-resolve
    length dynamically. `rebuild_graph_edge_lengths` below is the SINGLE
    reusable "recompute affected geometry" step demanded by section 3/4 --
    it recomputes EVERY edge's length from the CURRENT registry via
    `compute_global_distance`, so edges whose endpoints did not move are
    provably unchanged (section 4: `UNAFFECTED_NETWORKS_REMAIN_UNCHANGED`)
    without any special-casing per network.

  Patient/room doctrine -- `operational_day_orchestrator.
    build_controlled_room_registry` creates exactly one `PATIENT_ROOM` per
    inpatient (never an independent room/patient count). No existing
    function converts "added room count" into "added patient count"; this
    module's `derive_patient_demand_from_added_capacity` is a NEW, narrow,
    disclosed composition that reuses the EXISTING
    `oncology_pet_spect_scenario.REALISTIC_ONCOLOGY_50.occupancy_fraction`
    (0.85) as the governing occupancy assumption -- never 100% occupancy,
    never a fabricated new constant.

  Scanner sizing -- `oncology_pet_spect_scenario.required_scanner_count`
    already derives required scanner count from patient throughput +
    protocol duration + operating window + availability (never a fixed
    count). Reused verbatim below.

  Decay/EOB chain -- `multi_isotope_decay.retained_fraction`/
    `required_upstream_activity` is the ONE authoritative decay
    implementation (section 5/31: never duplicated here).
    GENUINE GAP FOUND (documented, not fabricated): the existing
    architecture-optimization decay track (`whole_oncology_four_
    architecture_optimization.py`, `hybrid_optimization.py`,
    `decision_pipeline.py`) computes retained fraction from its OWN
    scheduling timestamps (`injection_start`/`release_time`) or its OWN
    `facility_engineering_model` geometry -- NEITHER consumes this
    repository's `canonical_spatial_authority.SpatialObjectRegistry`/
    `ConnectivityGraph` (the Build 1-4/4A track). There is NO existing
    wiring connecting THIS track's canonical horizontal-expansion route
    distance to the decay chain. This module closes that gap ONLY for the
    one case where an existing function already accepts a real distance
    parameter: `dedicated_rp_pts_authority.compute_rp_pts_mission_cycle
    (network_length_m=...)`. `compute_rp_pts_decay_consequence` below feeds
    a REAL canonical RP-PTS route distance into that EXISTING function,
    then feeds its resulting elapsed transport time into the EXISTING
    `retained_fraction`/`required_upstream_activity` -- a genuinely NEW,
    honest, minimal connection, never claimed to generalize to MRT/RGHT/
    ordinary-PTS (whose route-based timing remains NOT_CALIBRATED, section
    16/20, and therefore never feeds a fabricated decay consequence,
    section 35).

  Floor height -- `ifc_hospital_proof_model_generator.
    FLOOR_TO_FLOOR_HEIGHT_M` (4.0 m) is the existing, repository-consistent
    floor-to-floor height constant (also reused by `spatial_benchmark.py`/
    `campus_retrofit_benchmark.py`). Reused verbatim as the default vertical
    expansion floor height; never a second/invented height constant.

VENDOR/ANIMATION NEUTRALITY: no OpenUSD/NVIDIA/Bentley import anywhere in
this module; no trajectory/animation authority is created or consumed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal

import canonical_spatial_authority as csa
import human_circulation_authority as hca
from ifc_hospital_proof_model_generator import FLOOR_TO_FLOOR_HEIGHT_M

HORIZONTAL_EXPANSION_DOMAIN = "CONTINUOUS"
VERTICAL_EXPANSION_DOMAIN = "DISCRETE_INTEGER_FLOORS"
EXPANSION_REQUIRES_CANONICAL_ORIGIN = True
EXPANSION_WITHOUT_ORIGIN_ALLOWED = False
HORIZONTAL_EXPANSION_SOURCE = "CANONICAL_GEOMETRY_TRANSFORMATION"
HORIZONTAL_EXPANSION_CHANGES_RELATIVE_SEPARATION = True
HORIZONTAL_EXPANSION_TRANSLATES_WHOLE_SYSTEM = False
HORIZONTAL_EXPANSION_DEFAULT_DEMAND_CHANGE = "ZERO"
VERTICAL_EXPANSION_INCREMENT = "ONE_WHOLE_FLOOR"
VERTICAL_EXPANSION_REPLICATES_FUNCTIONAL_FLOOR = True
VERTICAL_EXPANSION_MOVES_EXISTING_FLOORS = False
VERTICAL_EXPANSION_APPENDS_NEW_FLOORS = True
MAJOR_EQUIPMENT_REPLICATION_RULE = "REQUIREMENT_DERIVED_NOT_BLIND_COPY"
VERTICAL_EXPANSION_PATIENT_DEMAND = "DERIVED_FROM_REPLICATED_CAPACITY_AND_EXISTING_OCCUPANCY_RULES"
VERTICAL_EXPANSION_PATIENT_ROOM_BINDING = "DETERMINISTIC_AND_NON_PHI"
ELEVATOR_CAPACITY_MODEL = "NOT_IMPLEMENTED"
"""Section 22 audit: no elevator capacity/contention/queueing model exists
anywhere in this repository (confirmed by search) -- never fabricated
here."""
EXPANSION_LAYER_SELECTS_TRANSPORT_TECHNOLOGY = False
DEFAULT_OCCUPANCY_FRACTION = 0.85
"""Reused verbatim from `oncology_pet_spect_scenario.REALISTIC_ONCOLOGY_50.
occupancy_fraction` -- the existing governing realistic-benchmark occupancy
assumption (never 100%, never invented)."""

# Major/shared equipment object types this module NEVER replicates
# floor-by-floor (section 9) -- only floor-LOCAL PATIENT_ROOM capacity is
# replicated; shared equipment quantity is always requirement-derived.
_MAJOR_SHARED_EQUIPMENT_TYPES = frozenset({"CYCLOTRON", "MO99_TC99M_GENERATOR", "PET_SCANNER", "SPECT_SCANNER", "RADIOPHARMACY"})
_REPLICABLE_ROOM_TYPES = frozenset({"PATIENT_ROOM"})


# ===========================================================================
# Section 28A-28F: horizontal expansion request/record.
# ===========================================================================


@dataclass(frozen=True)
class HorizontalExpansionRequest:
    expansion_id: str
    anchor_object_id: str
    target_object_id: str
    expansion_distance_m: float
    direction_vector: tuple[float, float, float] | None = None
    """None -> derive the unit direction from anchor -> target (section 28E)."""

    def __post_init__(self) -> None:
        if self.expansion_distance_m < 0.0:
            raise ValueError("expansion_distance_m must be >= 0.0 (section 1: d >= 0)")
        if self.anchor_object_id == self.target_object_id:
            raise ValueError("anchor_object_id and target_object_id must be distinct")


@dataclass(frozen=True)
class HorizontalExpansionRecord:
    expansion_id: str
    expansion_type: Literal["HORIZONTAL"]
    anchor_object_id: str
    target_object_id: str
    anchor_position_before: tuple[float, float, float]
    anchor_position_after: tuple[float, float, float]
    target_position_before: tuple[float, float, float]
    target_position_after: tuple[float, float, float]
    old_separation_m: float
    new_separation_m: float
    unit_direction: tuple[float, float, float]
    provenance: str = "canonical_spatial_authority.resolve_global_position/apply_changeset (MOVE_OBJECT)"


def apply_horizontal_expansion(what_if: csa.WhatIfSpatialState, request: HorizontalExpansionRequest) -> HorizontalExpansionRecord:
    """Sections 3/28A-28G: moves ONLY `target_object_id`'s own `Transform`
    (translation only) -- anchor is never touched; descendants' own
    (locally stored) transforms are never touched either (they move
    automatically via `resolve_global_position`'s parent-chain
    accumulation, section 28G). Never edits `SpatialEdge.length_m` directly
    (section 3)."""
    registry = what_if.registry
    if request.anchor_object_id not in registry.objects:
        raise ValueError(f"anchor {request.anchor_object_id} not found -- expansion requires an existing canonical origin (section 28A)")
    if request.target_object_id not in registry.objects:
        raise ValueError(f"target {request.target_object_id} not found")

    anchor_before = csa.resolve_global_position(registry, request.anchor_object_id)
    target_before = csa.resolve_global_position(registry, request.target_object_id)
    old_separation = math.sqrt(sum((t - a) ** 2 for a, t in zip(anchor_before, target_before)))

    if request.direction_vector is not None:
        dx, dy, dz = request.direction_vector
        norm = math.sqrt(dx * dx + dy * dy + dz * dz)
        if norm == 0.0:
            raise ValueError("direction_vector must be non-zero")
        unit = (dx / norm, dy / norm, dz / norm)
    else:
        if old_separation == 0.0:
            raise ValueError("anchor and target are coincident -- an explicit direction_vector is required (section 28E)")
        unit = tuple((t - a) / old_separation for a, t in zip(anchor_before, target_before))

    new_separation = old_separation + request.expansion_distance_m
    new_target_global = tuple(anchor_before[i] + unit[i] * new_separation for i in range(3))
    delta = tuple(new_target_global[i] - target_before[i] for i in range(3))

    target_obj = registry.get(request.target_object_id)
    new_local_transform = replace(
        target_obj.transform, position_x=target_obj.transform.position_x + delta[0],
        position_y=target_obj.transform.position_y + delta[1], position_z=target_obj.transform.position_z + delta[2],
    )
    new_target_obj = replace(target_obj, transform=new_local_transform)
    csa.apply_changeset(
        what_if, change_id=f"{request.expansion_id}-MOVE-TARGET", operation="MOVE_OBJECT",
        object_id=request.target_object_id, new_object=new_target_obj,
        note=f"Build 4A horizontal expansion: +{request.expansion_distance_m}m along {unit}",
    )

    anchor_after = csa.resolve_global_position(registry, request.anchor_object_id)
    target_after = csa.resolve_global_position(registry, request.target_object_id)
    return HorizontalExpansionRecord(
        expansion_id=request.expansion_id, expansion_type="HORIZONTAL", anchor_object_id=request.anchor_object_id,
        target_object_id=request.target_object_id, anchor_position_before=anchor_before, anchor_position_after=anchor_after,
        target_position_before=target_before, target_position_after=target_after, old_separation_m=old_separation,
        new_separation_m=new_separation, unit_direction=unit,
    )


def rebuild_graph_edge_lengths(registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph) -> csa.ConnectivityGraph:
    """Section 3-4: the ONE reusable "recompute affected geometry/routes"
    step -- recomputes EVERY edge's `length_m` from the registry's CURRENT
    global positions via `compute_global_distance` (never a manually
    supplied delta). Edges whose endpoints did not move are provably
    unchanged; this is how `UNAFFECTED_NETWORKS_REMAIN_UNCHANGED` holds
    without per-network special-casing."""
    rebuilt = csa.ConnectivityGraph()
    for edge in graph.edges:
        new_length = csa.compute_global_distance(registry, edge.from_object_id, edge.to_object_id)
        rebuilt.add_edge(replace(edge, length_m=new_length))
    return rebuilt


# ===========================================================================
# Section 28H-28I/7-10: vertical (discrete, functional) floor expansion.
# ===========================================================================


@dataclass(frozen=True)
class VerticalExpansionRequest:
    expansion_id: str
    facility_id: str
    building_id: str
    added_floor_count: int
    reference_floor_id: str

    def __post_init__(self) -> None:
        if isinstance(self.added_floor_count, bool) or not isinstance(self.added_floor_count, int):
            raise ValueError("added_floor_count must be an integer (section 1: n is a non-negative INTEGER)")
        if self.added_floor_count < 1:
            raise ValueError("added_floor_count must be >= 1")


@dataclass(frozen=True)
class VerticalExpansionRecord:
    expansion_id: str
    expansion_type: Literal["VERTICAL"]
    building_id: str
    reference_floor_id: str
    created_floor_id: str
    created_room_ids: tuple[str, ...]
    floor_elevation_m: float | Literal["NOT_CALIBRATED"]
    status: Literal["COMPLETE", "FLOOR_HEIGHT_NOT_CALIBRATED"]
    provenance: str = "canonical_spatial_authority.add_floor/add_room (reference-floor replication)"


def _floors_of_building(registry: csa.SpatialObjectRegistry, building_id: str) -> tuple[csa.CanonicalSpatialObject, ...]:
    return tuple(o for o in registry.objects.values() if o.object_type == "FLOOR" and o.building_id == building_id)


def apply_vertical_expansion_increment(
    what_if: csa.WhatIfSpatialState, request: VerticalExpansionRequest, *,
    floor_height_m: float | Literal["NOT_CALIBRATED"] = FLOOR_TO_FLOOR_HEIGHT_M,
) -> VerticalExpansionRecord:
    """Sections 7-10/28H-28I: replicates ONLY `_REPLICABLE_ROOM_TYPES` (never
    `_MAJOR_SHARED_EQUIPMENT_TYPES`, section 9). Existing floors are NEVER
    moved (section 28H) -- the new floor is appended ABOVE the current top
    floor of `building_id`, one whole floor at a time (section 24). New
    floor/room IDs are always distinct (never a duplicate canonical ID,
    section 8/10)."""
    registry = what_if.registry
    if request.building_id not in registry.objects:
        raise ValueError(f"building {request.building_id} not found -- expansion requires an existing canonical origin (section 28A/28H)")
    if request.reference_floor_id not in registry.objects:
        raise ValueError(f"reference floor {request.reference_floor_id} not found")

    if floor_height_m == "NOT_CALIBRATED":
        return VerticalExpansionRecord(
            expansion_id=request.expansion_id, expansion_type="VERTICAL", building_id=request.building_id,
            reference_floor_id=request.reference_floor_id, created_floor_id="", created_room_ids=(),
            floor_elevation_m="NOT_CALIBRATED", status="FLOOR_HEIGHT_NOT_CALIBRATED",
        )

    floors = _floors_of_building(registry, request.building_id)
    existing_local_ids = {f.floor_id for f in floors}
    new_local_floor_id = f"F{len(floors) + 1}"
    if new_local_floor_id in existing_local_ids:
        raise ValueError(f"floor id {new_local_floor_id} already exists in building {request.building_id} -- refusing to duplicate a canonical floor ID")

    top_elevation_m = max((f.transform.position_z for f in floors), default=0.0)
    new_elevation_m = top_elevation_m + float(floor_height_m)
    new_floor_obj = csa.add_floor(
        registry, facility_id=request.facility_id, building_id=request.building_id, floor_id=new_local_floor_id,
        transform=csa.Transform(position_z=new_elevation_m),
    )
    csa.apply_changeset(
        what_if, change_id=f"{request.expansion_id}-ADD-FLOOR", operation="ADD_OBJECT",
        object_id=new_floor_obj.mrtway_object_id, new_object=new_floor_obj,
        note=f"Build 4A vertical expansion: appended {new_local_floor_id} above existing top floor at z={top_elevation_m}",
    )

    ref_rooms = tuple(
        o for o in registry.objects.values()
        if o.parent_object_id == request.reference_floor_id and o.object_type in _REPLICABLE_ROOM_TYPES
    )
    created_room_ids: list[str] = []
    for room in ref_rooms:
        new_room_id = f"{room.mrtway_object_id}-{new_local_floor_id}"
        if new_room_id in registry.objects:
            raise ValueError(f"room id {new_room_id} already exists -- refusing to duplicate a canonical room ID")
        new_room = csa.add_room(
            registry, facility_id=request.facility_id, building_id=request.building_id, floor_id=new_local_floor_id,
            room_id=new_room_id, object_type=room.object_type, transform=room.transform,
        )
        created_room_ids.append(new_room.mrtway_object_id)

    return VerticalExpansionRecord(
        expansion_id=request.expansion_id, expansion_type="VERTICAL", building_id=request.building_id,
        reference_floor_id=request.reference_floor_id, created_floor_id=new_floor_obj.mrtway_object_id,
        created_room_ids=tuple(created_room_ids), floor_elevation_m=new_elevation_m, status="COMPLETE",
    )


# ===========================================================================
# Sections 11-12: patient demand / deterministic non-PHI room binding.
# ===========================================================================


def derive_patient_demand_from_added_capacity(added_room_count: int, *, occupancy_fraction: float = DEFAULT_OCCUPANCY_FRACTION) -> int:
    """Section 11: NEVER assumes 100% occupancy by default -- reuses the
    EXISTING `oncology_pet_spect_scenario.REALISTIC_ONCOLOGY_50.
    occupancy_fraction` (0.85) as the governing scenario assumption."""
    if added_room_count <= 0:
        return 0
    return math.floor(added_room_count * occupancy_fraction)


def bind_derived_patients_to_rooms(binding_registry, room_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Section 12: deterministic, non-PHI synthetic patient IDs -- reuses
    the EXISTING `canonical_entity_binding_authority.bind_patient_room`
    (never a new patient-room binding mechanism)."""
    from canonical_entity_binding_authority import bind_patient_room

    patient_ids: list[str] = []
    for room_id in room_ids:
        patient_id = f"SYN-PATIENT-{room_id}"
        bind_patient_room(binding_registry, patient_id=patient_id, room_id=room_id)
        patient_ids.append(patient_id)
    return tuple(patient_ids)


# ===========================================================================
# Section 5-6: horizontal-expansion radiopharmaceutical decay consequence
# (RP-PTS leg only -- see module docstring for the honest gap disclosure).
# ===========================================================================


@dataclass(frozen=True)
class RpPtsDecayConsequence:
    network_length_m: float
    tube_transport_minutes: float
    total_cycle_minutes: float
    retained_fraction_at_administration: float
    required_upstream_activity_mbq: float
    provenance: str = (
        "dedicated_rp_pts_authority.compute_rp_pts_mission_cycle + "
        "multi_isotope_decay.retained_fraction/required_upstream_activity (existing authorities, newly composed)"
    )


def compute_rp_pts_decay_consequence(*, network_length_m: float, prescribed_activity_mbq: float) -> RpPtsDecayConsequence:
    """Section 5: distance -> transport time -> decay/retention -> required
    upstream activity, using ONLY existing functions (never a duplicate
    decay equation, section 31). Reuses F-18's real half-life from
    `f18_decay_model.load_f18_half_life_minutes()` (radionuclides.json),
    never an invented half-life."""
    from dedicated_rp_pts_authority import compute_rp_pts_mission_cycle
    from f18_decay_model import load_f18_half_life_minutes
    from multi_isotope_decay import required_upstream_activity, retained_fraction

    cycle = compute_rp_pts_mission_cycle(network_length_m=network_length_m)
    half_life_minutes = load_f18_half_life_minutes()
    retained = retained_fraction(cycle.total_minutes, half_life_minutes)
    required_activity = required_upstream_activity(prescribed_activity_mbq, retained)
    return RpPtsDecayConsequence(
        network_length_m=network_length_m, tube_transport_minutes=cycle.tube_transport_minutes,
        total_cycle_minutes=cycle.total_minutes, retained_fraction_at_administration=retained,
        required_upstream_activity_mbq=required_activity,
    )


# ===========================================================================
# Section 41: vertical-expansion activity requirement (throughput-derived,
# NOT distance-derived -- reuses the SAME existing per-patient formula).
# ===========================================================================


def recompute_required_upstream_activity_for_patient_count(
    patient_count: int, *, prescribed_activity_mbq_per_patient: float, elapsed_minutes: float, half_life_minutes: float,
) -> float:
    """Section 15/41 item 54: total required upstream (release) activity for
    `patient_count` patients -- reuses `multi_isotope_decay.
    required_upstream_activity`/`retained_fraction` verbatim, summed once
    per patient (never a legacy dose-count ceiling, section 56)."""
    from multi_isotope_decay import required_upstream_activity, retained_fraction

    if patient_count <= 0:
        return 0.0
    retained = retained_fraction(elapsed_minutes, half_life_minutes)
    return patient_count * required_upstream_activity(prescribed_activity_mbq_per_patient, retained)


# ===========================================================================
# Build 4B: vertical-expansion porter workload / staffing / overtime /
# labor-OPEX closure.
#
# AUDIT FINDING (section 3): Build 4A's `$53,040/year` flat result at every
# floor increment used `ody._estimate_annual_porter_labor_opex(mission_count
# =patients, avg_minutes=10.0, ...)` in its report script/tests --
# `mission_count` blindly equated 1 derived patient = 1 porter mission
# (never derived from the existing transport-demand/stream-assignment
# authority, section 4), and `avg_minutes=10.0` was a fixed literal, never a
# real canonical route resolution (section 7). `_estimate_annual_porter_
# labor_opex` itself is ALSO a simplified average-only sizing helper (its
# own docstring: "disclosed bounded simplification"), NOT the more precise
# existing staffing/overtime authority below. Verdict:
# BUILD4A_PORTER_OPEX_INPUT_STATUS = CONTROLLED_PROOF_PLACEHOLDER.
#
# THE REAL EXISTING AUTHORITIES (never re-derived, only composed here):
#   - `general_oncology_logistics.generate_daily_logistics_demand` ->
#     `consolidate_demands_into_loads` -> `missions_for_architecture`
#     (MANUAL_CONVENTIONAL -> `convert_load_to_manual_missions`) is the
#     EXISTING transport-demand/stream-assignment authority (section 4/6) --
#     CLEAN_LINEN/PHARMACY_INFUSION/SPECIMEN_BLOOD/STERILE_CLEAN_SUPPLY are
#     the only existing general-logistics porter-eligible streams; mission
#     COUNT is demand-consolidation-derived, never 1-per-patient.
#   - The radiopharmaceutical leg (section 5) is modeled separately (it is
#     NOT one of the four general-logistics streams above) using the REAL
#     canonical pedestrian route (`human_circulation_authority.
#     resolve_pedestrian_route`) from the radiopharmacy to each patient's
#     room, fed into the EXISTING `conventional_transport_authority.
#     compute_manual_mission_timing` (never a new timing formula).
#   - `operational_day_orchestrator.compute_manual_transport_workload`/
#     `compute_manual_shift_labor_cost`/`resolve_shift_hours` is the REAL,
#     more precise staffing/overtime authority (18h/day -> 16h regular (2 x
#     8h shifts) + 2h overtime per continuously required position, overtime
#     costed at `basis.overtime_multiplier`) -- distinct from, and more
#     precise than, `_estimate_annual_porter_labor_opex`. This is
#     `PORTER_STAFFING_AUTHORITY` for this build.
#
# General-logistics stream mission MINUTES reuse `convert_load_to_manual_
# missions`'s own EXISTING default `travel_minutes=8.0` (section 7: "use
# real route timing WHERE canonical geometry exists" -- no canonical
# spatial object is registered for LABORATORY/CENTRAL_PHARMACY/CLEAN_LINEN_
# SOURCE/STERILE_CLEAN_SUPPLY_SOURCE role locations in this controlled
# fixture, so no real route exists for those legs; this is disclosed, never
# fabricated). ONLY the radiopharmaceutical leg has real canonical geometry
# established (Build 4), so ONLY it uses real route-derived minutes.
# ===========================================================================

PORTER_REGULAR_SHIFT_HOURS = 8.0
PORTER_REGULAR_DAILY_COVERAGE_HOURS = 16.0
PORTER_OVERTIME_TRIGGER = "hours beyond 16 regular hours within an 18-hour operating day (2h/day per continuously required position)"
PORTER_STAFFING_AUTHORITY = (
    "operational_day_orchestrator.compute_manual_transport_workload/compute_manual_shift_labor_cost/resolve_shift_hours"
)
PORTER_MISSION_COUNT_SOURCE = "EXISTING_TRANSPORT_DEMAND_AND_ASSIGNMENT_AUTHORITY"
PORTER_VERTICAL_EXPANSION_WORKLOAD_USES_REAL_ROUTE_TIMING = True
PATIENT_TRAVEL_COUNTED_AS_PORTER_LABOR = False


@dataclass(frozen=True)
class PorterMissionTrace:
    mission_id: str
    stream: str
    origin: str
    destination: str
    route_distance_m: float | Literal["NOT_CALIBRATED"]
    vertical_transitions: int
    mission_minutes: float
    timing_provenance: str


def generate_vertical_expansion_porter_missions(
    registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph, *, day, created_room_ids: tuple[str, ...],
    radiopharmacy_object_id: str, policy=None,
) -> tuple[PorterMissionTrace, ...]:
    """Sections 4-9 (Build 4B) + role-location closure (Build 4C): derives
    porter-eligible missions from the EXISTING demand/assignment authority
    (general streams) plus the EXISTING pedestrian route authority (both
    the radiopharmaceutical leg and, where a canonical role location is
    bound -- `hospital_logistics_role_location_authority` -- the general-
    logistics legs too). Never 1 patient = 1 mission, never a fixed
    avg_minutes where a real/controlled-proof route exists."""
    from conventional_transport_authority import DEFAULT_GENERAL_CART, DEFAULT_LINEN_CART, PorterOperatingPolicy, compute_manual_mission_timing
    from general_oncology_logistics import consolidate_demands_into_loads, generate_daily_logistics_demand, missions_for_architecture
    from hospital_logistics_role_location_authority import resolve_controlled_proof_roles
    from oncology_pet_spect_scenario import OncologyPatientRecord

    policy = policy or PorterOperatingPolicy()
    synthetic_patients = []
    traces: list[PorterMissionTrace] = []
    ward_representative_rooms: dict[str, str] = {}

    for room_id in created_room_ids:
        room = registry.get(room_id)
        ward_representative_rooms.setdefault(room.floor_id, room_id)
        patient_id = f"SYN-PATIENT-{room_id}"
        synthetic_patients.append(OncologyPatientRecord(
            patient_id=patient_id, patient_type="INPATIENT", admission_date=day, expected_discharge_date=day,
            building_id=room.building_id, floor_id=room.floor_id, room_id=room_id,
        ))
        route = hca.resolve_pedestrian_route(registry, graph, subject="PORTER", origin_object_id=radiopharmacy_object_id, destination_object_id=room_id)
        if route.route_status == "ROUTE_CALIBRATED":
            timing = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=route.total_distance_m, vertical_transitions=route.vertical_transition_count)
            traces.append(PorterMissionTrace(
                mission_id=f"MISSION-RP-{patient_id}", stream="RADIOPHARMACEUTICAL_MANUAL", origin=radiopharmacy_object_id,
                destination=room_id, route_distance_m=route.total_distance_m, vertical_transitions=route.vertical_transition_count,
                mission_minutes=timing.total_minutes, timing_provenance="conventional_transport_authority.compute_manual_mission_timing (real canonical route, human_circulation_authority)",
            ))
        else:
            timing = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER")
            traces.append(PorterMissionTrace(
                mission_id=f"MISSION-RP-{patient_id}", stream="RADIOPHARMACEUTICAL_MANUAL", origin=radiopharmacy_object_id,
                destination=room_id, route_distance_m="NOT_CALIBRATED", vertical_transitions=0, mission_minutes=timing.total_minutes,
                timing_provenance="ROUTE_NOT_CALIBRATED -- controlled scenario default fallback (no fabricated distance)",
            ))

    # Build 4C section 3/17: the EXISTING `generate_daily_logistics_demand`/
    # `consolidate_demands_into_loads` are reused verbatim, only the ROLE
    # LOCATIONS passed to them are extended (CONTROLLED_PROOF_LOCATION for
    # CLEAN_LINEN_SOURCE/STERILE_CLEAN_SUPPLY) -- never a new demand model.
    roles = resolve_controlled_proof_roles()
    demands = generate_daily_logistics_demand(day=day, inpatients=tuple(synthetic_patients), roles=roles)
    loads = consolidate_demands_into_loads(demands=demands, max_quantity_per_load=80.0)
    for load in loads:
        cart_capacity = DEFAULT_LINEN_CART.payload_capacity if load.stream == "CLEAN_LINEN" else DEFAULT_GENERAL_CART.payload_capacity
        missions = missions_for_architecture(load=load, architecture="MANUAL_CONVENTIONAL", cart_capacity=cart_capacity)
        for m in missions:
            origin_id = _resolve_ward_or_role_object_id(m.origin, ward_representative_rooms=ward_representative_rooms)
            destination_id = _resolve_ward_or_role_object_id(m.destination, ward_representative_rooms=ward_representative_rooms)
            route = None
            if origin_id is not None and destination_id is not None and origin_id in registry.objects and destination_id in registry.objects:
                route = hca.resolve_pedestrian_route(registry, graph, subject="PORTER", origin_object_id=origin_id, destination_object_id=destination_id)
            if route is not None and route.route_status == "ROUTE_CALIBRATED":
                timing = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=route.total_distance_m, vertical_transitions=route.vertical_transition_count)
                traces.append(PorterMissionTrace(
                    mission_id=m.mission_id, stream=load.stream, origin=m.origin, destination=m.destination,
                    route_distance_m=route.total_distance_m, vertical_transitions=route.vertical_transition_count, mission_minutes=timing.total_minutes,
                    timing_provenance="conventional_transport_authority.compute_manual_mission_timing (real canonical route, hospital_logistics_role_location_authority binding)",
                ))
            else:
                traces.append(PorterMissionTrace(
                    mission_id=m.mission_id, stream=load.stream, origin=m.origin, destination=m.destination,
                    route_distance_m="NOT_CALIBRATED", vertical_transitions=0, mission_minutes=m.duration_minutes,
                    timing_provenance="general_oncology_logistics.convert_load_to_manual_missions default travel_minutes "
                                      "(no canonical role-location geometry bound for this leg)",
                ))
    return tuple(traces)


def _resolve_ward_or_role_object_id(location: str, *, ward_representative_rooms: dict[str, str]) -> str | None:
    """Build 4C section 10: a ward-level mission endpoint (`"WARD-{floor_id}"`,
    the consolidation granularity `consolidate_demands_into_loads` already
    uses) is approximated by its floor's representative replicated patient
    room for route-resolution purposes -- disclosed, never a fabricated
    ward-corridor object. A role-bound endpoint is already a real canonical
    object id and is returned unchanged; `"LOCATION_NOT_CALIBRATED"` (the
    existing honest placeholder) resolves to `None`."""
    if location == "LOCATION_NOT_CALIBRATED":
        return None
    if location.startswith("WARD-"):
        return ward_representative_rooms.get(location[len("WARD-"):])
    return location


def compute_vertical_expansion_porter_labor_opex(traces: tuple[PorterMissionTrace, ...], *, basis=None):
    """Section 9-10: `W_day = sum(T_mission_i)` fed into the EXISTING
    `operational_day_orchestrator.compute_manual_transport_workload`
    (peak-aware shift/overtime staffing authority) -- never a new staffing
    formula."""
    from operational_day_orchestrator import build_common_economic_basis, compute_manual_transport_workload

    basis = basis or build_common_economic_basis()
    missions_per_day = len(traces)
    avg_minutes = (sum(t.mission_minutes for t in traces) / missions_per_day) if missions_per_day else 0.0
    return compute_manual_transport_workload(missions_per_day=missions_per_day, avg_mission_minutes=avg_minutes, basis=basis)

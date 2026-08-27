"""Human (Patient + Porter) Pedestrian Circulation Authority
(Transport Spatial Authority Build 4).

GOVERNANCE: this module owns ONLY pedestrian route eligibility, corridor/
room-access/elevator connectivity, human route resolution, and the shared
human-speed reference. It is NOT a clinical scheduler, NOT a porter
staffing authority, NOT an economic authority, and NOT an animation/OpenUSD
authority. It never reimplements CapEx/OPEX/labor formulas -- callers feed
the DISTANCE this module resolves into the EXISTING
`conventional_transport_authority.compute_manual_mission_timing`/
`compute_porter_resource_requirement` (porter) or use
`compute_patient_travel_minutes` below (patient, which had no prior
distance-based timing authority at all).

AUDIT (section 4), performed before writing anything:

  Porter speed -- `conventional_transport_authority.PorterOperatingPolicy`
    already defines THREE distinct economic-timing speeds (unloaded 1.4,
    loaded hand-carry 1.1, loaded cart 0.9 m/s) consumed by
    `compute_manual_mission_timing`. That authority is EXISTING and is
    preserved untouched (section 9: "do not replace the existing manual
    timing model").

  Patient speed / shared human speed -- `models.PlannerAssumptions.
    manual_transport_speed_m_per_s` (1.2 m/s) and `.manual_transport_
    elevator_speed_m_per_s` (1.0 m/s) are the pre-existing GOVERNING
    controlled planning values already used, verbatim, as BOTH the
    "PATIENT_WALK" and "MANUAL" route-level pedestrian speed in
    `canonical_geometry_shadow_routing_authority._MODE_SPEED_M_PER_S`
    -- i.e. this exact conflict (multiple existing human speeds) was
    already resolved once in this repository by treating
    `manual_transport_speed_m_per_s`/`manual_transport_elevator_speed_m_per_s`
    as the ONE shared route-level pedestrian speed, distinct from
    `PorterOperatingPolicy`'s own multi-tier ECONOMIC labor-costing speeds.
    Build 4 reuses that exact precedent (section 5: "prefer the existing
    ... speed already present ... do not introduce a new external value")
    rather than inventing a third value.

  Corridor/elevator canonical objects -- `canonical_spatial_authority.
    SpatialObjectType` ALREADY includes "CORRIDOR"/"ELEVATOR"/"STAIR"/
    "DOOR"/"SHAFT" (no Literal extension needed). `add_room(...,
    object_type=...)` already accepts any `SpatialObjectType`, so
    corridor/elevator objects are built by REUSING `add_room` with
    `object_type="CORRIDOR"`/`"ELEVATOR"` -- never a second room-builder.

  Radiopharmacy / patient-room / scanner-room locations -- reused verbatim
    from `ifc_hospital_proof_model_generator.build_hospital_proof_model()`
    (ROOM-RP-101, ROOM-PAT-201, ROOM-SCN-202, COR-F1-001, COR-F2-001,
    VERT-001) -- the SAME coordinate source already used by the BIM Phase
    2A proof model and by `rght_spatial_network_authority`/
    `pts_spatial_network_authority`'s own controlled proof networks. This
    module NEVER introduces a second coordinate source. VERT-001-F2 is an
    ADDITIVE companion object (same X/Y as VERT-001, distinct Z only) --
    the proof model itself documents VERT-001 as one continuous vertical
    space; this module needs a distinct floor-2 landing NODE for the
    connectivity graph, so it reuses VERT-001's own X/Y for that landing
    (never inventing new coordinates), mirroring the SAME two-node
    same-X/Y-different-Z vertical-segment pattern already established by
    `rght_spatial_network_authority`/`pts_spatial_network_authority`.

  Manual route calculation -- `conventional_transport_authority.
    compute_manual_mission_timing` already accepts an optional
    `horizontal_distance_m`, becoming `ROUTE_CALIBRATED` when supplied
    (Transport Spatial Authority Build 1). `operational_day_orchestrator.
    execute_conventional_missions` already resolves a real MANUAL_PORTER/
    PORTER_CART distance via `transport_mission_route_bridge` when a
    registry/graph is supplied (Build 1) -- this module supplies THAT
    registry/graph for the human pedestrian network specifically.

  Patient travel calculation -- NO existing authority computes patient
    travel minutes from real geometry (`canonical_geometry_shadow_
    routing_authority` is documented SHADOW/DIAGNOSTIC ONLY and never
    feeds production timing). `compute_patient_travel_minutes` below is
    therefore the FIRST production patient-travel-time authority, using
    ONLY the existing shared human-speed reference above.

Patients and porters share ONE pedestrian network (this module's
`build_controlled_pedestrian_network`) and ONE route-resolution function
(`resolve_pedestrian_route`, parameterized only by which EXISTING
`canonical_spatial_authority.TransportMode` applies -- "PATIENT_MOVEMENT"
or "WALKING_PORTER" -- never two separate pathfinding algorithms, section
6/1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import canonical_spatial_authority as csa
import ifc_hospital_proof_model_generator as ihpmg
from models import PlannerAssumptions

HumanSubject = Literal["PATIENT", "PORTER"]

_SUBJECT_TO_CSA_MODE: dict[HumanSubject, csa.TransportMode] = {
    "PATIENT": "PATIENT_MOVEMENT",
    "PORTER": "WALKING_PORTER",
}

# ---------------------------------------------------------------------------
# Section 5: ONE shared human speed authority (reused, not invented).
# ---------------------------------------------------------------------------

HUMAN_WALKING_SPEED_M_PER_S: float = PlannerAssumptions().manual_transport_speed_m_per_s
HUMAN_ELEVATOR_SPEED_M_PER_S: float = PlannerAssumptions().manual_transport_elevator_speed_m_per_s
HUMAN_SPEED_STATUS: str = "CONTROLLED_ENGINEERING_ASSUMPTION"

# ---------------------------------------------------------------------------
# Section 2-3: the patient's/porter's ONE movement of clinical interest.
# ---------------------------------------------------------------------------

PATIENT_INJECTION_UPTAKE_LOCATION = "PATIENT_ROOM"
PATIENT_PRIMARY_SCAN_MOVEMENT = "PATIENT_ROOM_TO_SCANNER_ROOM"
RADIOPHARM_PORTER_PRIMARY_MOVEMENT = "RADIOPHARMACY_TO_PATIENT_ROOM"

RouteStatus = Literal["ROUTE_CALIBRATED", "ROUTE_NOT_CALIBRATED", "ROUTE_UNAVAILABLE"]


@dataclass(frozen=True)
class PedestrianRouteResult:
    subject: HumanSubject
    origin_object_id: str
    destination_object_id: str
    route_status: RouteStatus
    horizontal_distance_m: float | None
    vertical_distance_m: float | None
    total_distance_m: float | None
    vertical_transition_count: int
    route_node_ids: tuple[str, ...]
    provenance: str = "canonical_spatial_authority.resolve_route (common route solver, shared corridor/elevator network)"


def _edge_path_to_node_ids(graph: csa.ConnectivityGraph, origin_object_id: str, path_edge_ids: tuple[str, ...]) -> tuple[str, ...]:
    edges_by_id = {e.edge_id: e for e in graph.edges}
    node_ids = [origin_object_id]
    for edge_id in path_edge_ids:
        edge = edges_by_id[edge_id]
        next_node = edge.to_object_id if edge.from_object_id == node_ids[-1] else edge.from_object_id
        node_ids.append(next_node)
    return tuple(node_ids)


def resolve_pedestrian_route(
    registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph, *,
    subject: HumanSubject, origin_object_id: str, destination_object_id: str,
) -> PedestrianRouteResult:
    """Section 6/9-10: the ONE human route-resolution function -- patient
    and porter differ ONLY in which existing `TransportMode` is passed,
    never in algorithm. Reuses `canonical_spatial_authority.resolve_route`
    directly (common route solver); never fabricates a route through
    incompatible/missing geometry (section 7: honest `ROUTE_NOT_CALIBRATED`/
    `ROUTE_UNAVAILABLE` where corridor geometry is insufficient)."""
    if origin_object_id not in registry.objects or destination_object_id not in registry.objects:
        return PedestrianRouteResult(
            subject=subject, origin_object_id=origin_object_id, destination_object_id=destination_object_id,
            route_status="ROUTE_UNAVAILABLE", horizontal_distance_m=None, vertical_distance_m=None,
            total_distance_m=None, vertical_transition_count=0, route_node_ids=(),
        )
    mode = _SUBJECT_TO_CSA_MODE[subject]
    route = csa.resolve_route(graph, origin_object_id=origin_object_id, destination_object_id=destination_object_id, mode=mode)
    if route.calibration_status != "CALIBRATED":
        return PedestrianRouteResult(
            subject=subject, origin_object_id=origin_object_id, destination_object_id=destination_object_id,
            route_status="ROUTE_NOT_CALIBRATED", horizontal_distance_m=None, vertical_distance_m=None,
            total_distance_m=None, vertical_transition_count=0, route_node_ids=(),
        )
    edges_by_id = {e.edge_id: e for e in graph.edges}
    horizontal_m = sum(edges_by_id[eid].length_m for eid in route.path_edge_ids if not edges_by_id[eid].vertical)
    vertical_m = sum(edges_by_id[eid].length_m for eid in route.path_edge_ids if edges_by_id[eid].vertical)
    vertical_count = sum(1 for eid in route.path_edge_ids if edges_by_id[eid].vertical)
    node_ids = _edge_path_to_node_ids(graph, origin_object_id, route.path_edge_ids)
    return PedestrianRouteResult(
        subject=subject, origin_object_id=origin_object_id, destination_object_id=destination_object_id,
        route_status="ROUTE_CALIBRATED", horizontal_distance_m=float(horizontal_m), vertical_distance_m=float(vertical_m),
        total_distance_m=float(route.distance_m), vertical_transition_count=vertical_count, route_node_ids=node_ids,
    )


def compute_patient_travel_minutes(route: PedestrianRouteResult) -> float | Literal["NOT_CALIBRATED"]:
    """Section 10/25: the FIRST production patient-travel-time computation
    -- uses ONLY the shared `HUMAN_WALKING_SPEED_M_PER_S`/
    `HUMAN_ELEVATOR_SPEED_M_PER_S` reference above (same value already used
    for "PATIENT_WALK"/"MANUAL" route speed elsewhere in this repository).
    Never invents injection/uptake/scanner duration -- returns travel time
    only."""
    if route.route_status != "ROUTE_CALIBRATED" or route.horizontal_distance_m is None:
        return "NOT_CALIBRATED"
    horizontal_minutes = route.horizontal_distance_m / HUMAN_WALKING_SPEED_M_PER_S / 60.0
    vertical_minutes = (route.vertical_distance_m or 0.0) / HUMAN_ELEVATOR_SPEED_M_PER_S / 60.0
    return horizontal_minutes + vertical_minutes


def build_controlled_pedestrian_network(
    registry: csa.SpatialObjectRegistry, *, facility_id: str, building_id: str,
) -> tuple[csa.ConnectivityGraph, tuple[csa.CanonicalSpatialObject, ...]]:
    """Section 6-9: CONTROLLED_TEST_GEOMETRY reusing the EXISTING hospital
    proof-model coordinates (`ifc_hospital_proof_model_generator.
    build_hospital_proof_model()`) -- never a second coordinate source.
    Builds RADIOPHARMACY -> F1 corridor -> elevator core -> F2 corridor ->
    PATIENT ROOM / SCANNER ROOM, with corridor/elevator edges shared
    identically by PATIENT_MOVEMENT and WALKING_PORTER (section 1)."""
    model = ihpmg.build_hospital_proof_model()
    by_id = {r.room_id: r for r in model.rooms}
    rp101, cor_f1, vert001, cor_f2, pat201, scn202 = (
        by_id["ROOM-RP-101"], by_id["COR-F1-001"], by_id["VERT-001"], by_id["COR-F2-001"], by_id["ROOM-PAT-201"], by_id["ROOM-SCN-202"],
    )

    def _room(room_id: str, floor_id: str, x: float, y: float, z: float, object_type: str) -> csa.CanonicalSpatialObject:
        return csa.add_room(
            registry, facility_id=facility_id, building_id=building_id, floor_id=floor_id, room_id=room_id,
            object_type=object_type, transform=csa.Transform(position_x=x, position_y=y, position_z=z),
        )

    rp_obj = _room(rp101.room_id, rp101.floor_id, rp101.x_m, rp101.y_m, rp101.z_m, "RADIOPHARMACY")
    cor_f1_obj = _room(cor_f1.room_id, cor_f1.floor_id, cor_f1.x_m, cor_f1.y_m, cor_f1.z_m, "CORRIDOR")
    vert_f1_obj = _room(vert001.room_id, vert001.floor_id, vert001.x_m, vert001.y_m, vert001.z_m, "ELEVATOR")
    vert_f2_obj = _room("VERT-001-F2", "F2", vert001.x_m, vert001.y_m, vert001.z_m + 4.0, "ELEVATOR")
    cor_f2_obj = _room(cor_f2.room_id, cor_f2.floor_id, cor_f2.x_m, cor_f2.y_m, cor_f2.z_m, "CORRIDOR")
    pat_obj = _room(pat201.room_id, pat201.floor_id, pat201.x_m, pat201.y_m, pat201.z_m, "PATIENT_ROOM")
    scn_obj = _room(scn202.room_id, scn202.floor_id, scn202.x_m, scn202.y_m, scn202.z_m, "PET_SCANNER")

    def _dist(a: csa.CanonicalSpatialObject, b: csa.CanonicalSpatialObject) -> float:
        return ((a.transform.position_x - b.transform.position_x) ** 2 + (a.transform.position_y - b.transform.position_y) ** 2) ** 0.5

    shared_modes = frozenset({"WALKING_PORTER", "PATIENT_MOVEMENT"})
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="PED-EDGE-RP-COR1", from_object_id=rp_obj.mrtway_object_id, to_object_id=cor_f1_obj.mrtway_object_id, length_m=_dist(rp_obj, cor_f1_obj), compatible_modes=shared_modes))
    graph.add_edge(csa.SpatialEdge(edge_id="PED-EDGE-COR1-VERT", from_object_id=cor_f1_obj.mrtway_object_id, to_object_id=vert_f1_obj.mrtway_object_id, length_m=_dist(cor_f1_obj, vert_f1_obj), compatible_modes=shared_modes))
    graph.add_edge(csa.SpatialEdge(edge_id="PED-EDGE-VERT-VERTICAL", from_object_id=vert_f1_obj.mrtway_object_id, to_object_id=vert_f2_obj.mrtway_object_id, length_m=4.0, compatible_modes=shared_modes, vertical=True))
    graph.add_edge(csa.SpatialEdge(edge_id="PED-EDGE-VERT-COR2", from_object_id=vert_f2_obj.mrtway_object_id, to_object_id=cor_f2_obj.mrtway_object_id, length_m=_dist(vert_f2_obj, cor_f2_obj), compatible_modes=shared_modes))
    graph.add_edge(csa.SpatialEdge(edge_id="PED-EDGE-COR2-PAT", from_object_id=cor_f2_obj.mrtway_object_id, to_object_id=pat_obj.mrtway_object_id, length_m=_dist(cor_f2_obj, pat_obj), compatible_modes=shared_modes))
    graph.add_edge(csa.SpatialEdge(edge_id="PED-EDGE-COR2-SCN", from_object_id=cor_f2_obj.mrtway_object_id, to_object_id=scn_obj.mrtway_object_id, length_m=_dist(cor_f2_obj, scn_obj), compatible_modes=shared_modes))

    return graph, (rp_obj, cor_f1_obj, vert_f1_obj, vert_f2_obj, cor_f2_obj, pat_obj, scn_obj)

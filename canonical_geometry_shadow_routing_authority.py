"""Canonical Geometry-Derived Routing Shadow Authority (Phase 2A).

GOVERNANCE: SHADOW MODE ONLY. This module derives physical routes,
distances, and travel times from EXISTING canonical spatial geometry for
DIAGNOSTIC COMPARISON ONLY. It never feeds back into, replaces, or is
consumed by any authoritative production/transport-timing/CapEx/OPEX/NPV/IRR
calculation. Every existing timing authority
(`conventional_transport_authority.compute_manual_mission_timing`,
`decision_pipeline._resolve_mrt_transport_minutes`, the fixed AGV/PTS
main-leg constants, the RP-PTS/MRT 222.0m reference) remains untouched and
authoritative:

    CURRENT_RESULT_BEFORE_PHASE_2A == CURRENT_RESULT_AFTER_PHASE_2A

Two existing graph representations are reused, never duplicated:
- `canonical_spatial_authority.ConnectivityGraph`/`resolve_route()` -- used
  whenever a caller has a canonical registry + mode-aware graph (patient/
  manual/AGV/PTS shadow routing, shadow move experiments).
- `facility_engineering_model.FacilityEngineeringObjectModel.nodes`/`.edges`
  (as already built by `spatial_benchmark.build_benchmark_geometry`) -- the
  ONLY place real geometry exists for the frozen eight-floor benchmark
  today. `facility_engineering_model.network_route_distance_m` returns a
  scalar only (no path/segment/horizontal-vertical detail), so a
  path-reconstructing Dijkstra is added HERE -- `facility_engineering_
  model.py` itself is never modified.

No route is ever fabricated: unresolved origins/destinations/networks are
reported as explicit statuses, never invented coordinates.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

import canonical_spatial_authority as csa
from facility_engineering_model import FacilityEngineeringObjectModel, SpatialEdge as FacilitySpatialEdge, SpatialNode as FacilitySpatialNode

ShadowTransportMode = Literal["PATIENT_WALK", "MANUAL", "AGV_AMR", "ORDINARY_PTS", "DEDICATED_RP_PTS", "MRT"]

# Section 3/6: maps the Phase 2A mode vocabulary onto the EXISTING mode-aware
# `canonical_spatial_authority.TransportMode` enum -- never a second mode
# taxonomy. ORDINARY_PTS and DEDICATED_RP_PTS both map to "PNEUMATIC_TUBE"
# (the only tube-network mode the existing graph model has); section 14
# forbids reusing MRT geometry as RP-PTS geometry, NOT distinguishing PTS
# sub-modes at the graph level, which the existing enum does not support.
SHADOW_MODE_TO_CSA_MODE: dict[ShadowTransportMode, csa.TransportMode] = {
    "PATIENT_WALK": "PATIENT_MOVEMENT",
    "MANUAL": "WALKING_PORTER",
    "AGV_AMR": "AGV_AMR",
    "ORDINARY_PTS": "PNEUMATIC_TUBE",
    "DEDICATED_RP_PTS": "PNEUMATIC_TUBE",
    "MRT": "MRT",
}

# Section 18: reuses EXISTING speed authorities only -- never invented.
# (horizontal_m_per_s, vertical_m_per_s | None) -- vertical is None where no
# existing authority defines a vertical speed for that mode.
_MODE_SPEED_M_PER_S: dict[ShadowTransportMode, tuple[float, float | None]] = {
    # models.PlannerAssumptions.manual_transport_speed_m_per_s / _elevator_speed_m_per_s
    "PATIENT_WALK": (1.2, 1.0),
    "MANUAL": (1.2, 1.0),
    # conventional_transport_authority.DEFAULT_AGV_MODEL.speed_m_per_s
    "AGV_AMR": (0.8, None),
    # conventional_transport_authority.DEFAULT_PTS_NETWORK.speed_m_per_s
    "ORDINARY_PTS": (6.0, None),
    # editable_default_authority.RP_PTS_OPERATING_SPEED_M_PER_S.default_value --
    # a DISTINCT, separately-editable value from ordinary PTS's 6.0 m/s
    # (Phase 2B.1 section 9: verified, not assumed equal).
    "DEDICATED_RP_PTS": (6.1, None),
    # models.PlannerAssumptions.mrt_horizontal_speed_m_per_s / _vertical_speed_m_per_s
    "MRT": (3.0, 1.5),
}

RouteStatus = Literal["RESOLVED", "UNRESOLVED_ORIGIN", "UNRESOLVED_DESTINATION", "NO_ROUTE", "ROUTE_GEOMETRY_NOT_AVAILABLE"]
RouteProvenance = Literal[
    "CANONICAL_GRAPH_DERIVED", "FACILITY_ENGINEERING_GRAPH_DERIVED", "BENCHMARK_TEMPLATE_DERIVED", "LEGACY_REFERENCE_ONLY", "UNRESOLVED",
]


@dataclass(frozen=True)
class RouteSegment:
    segment_id: str
    from_node_id: str
    to_node_id: str
    length_m: float
    orientation: Literal["HORIZONTAL", "VERTICAL"]
    floor_or_building_context: str | None = None
    transport_eligible: bool = True


@dataclass(frozen=True)
class CanonicalRouteRequest:
    route_request_id: str
    subject_type: Literal["PATIENT", "PAYLOAD", "CARRIER", "MISSION", "GENERIC"]
    subject_id: str
    transport_mode: ShadowTransportMode
    origin_location_id: str
    destination_location_id: str
    lockdown_id: str | None = None
    what_if_id: str | None = None
    departure_time_minutes: float | None = None


@dataclass(frozen=True)
class ShadowRouteResult:
    route_id: str
    origin_location_id: str
    destination_location_id: str
    transport_mode: ShadowTransportMode
    ordered_node_ids: tuple[str, ...]
    ordered_edge_ids: tuple[str, ...]
    ordered_segments: tuple[RouteSegment, ...]
    horizontal_distance_m: float | None
    vertical_distance_m: float | None
    total_distance_m: float | None
    vertical_transition_count: int
    estimated_movement_time_minutes: float | None
    route_status: RouteStatus
    provenance: RouteProvenance
    lockdown_id: str | None = None
    what_if_id: str | None = None
    note: str = ""


def _movement_time_minutes(mode: ShadowTransportMode, horizontal_m: float, vertical_m: float) -> tuple[float | None, str]:
    horizontal_speed, vertical_speed = _MODE_SPEED_M_PER_S[mode]
    if vertical_m > 0.0 and vertical_speed is None:
        return None, f"no existing vertical-speed authority for {mode}; movement time not computed"
    t_horizontal = horizontal_m / horizontal_speed if horizontal_speed > 0 else 0.0
    t_vertical = (vertical_m / vertical_speed) if vertical_speed and vertical_m > 0.0 else 0.0
    return (t_horizontal + t_vertical) / 60.0, ""


def _unresolved(request: CanonicalRouteRequest, status: RouteStatus, note: str) -> ShadowRouteResult:
    return ShadowRouteResult(
        route_id=request.route_request_id, origin_location_id=request.origin_location_id,
        destination_location_id=request.destination_location_id, transport_mode=request.transport_mode,
        ordered_node_ids=(), ordered_edge_ids=(), ordered_segments=(), horizontal_distance_m=None, vertical_distance_m=None,
        total_distance_m=None, vertical_transition_count=0, estimated_movement_time_minutes=None, route_status=status,
        provenance="UNRESOLVED", lockdown_id=request.lockdown_id, what_if_id=request.what_if_id, note=note,
    )


# ---------------------------------------------------------------------------
# canonical_spatial_authority-based shadow routing (sections 3-14, 20-28)
# ---------------------------------------------------------------------------


def derive_shadow_route(
    graph: csa.ConnectivityGraph, registry: csa.SpatialObjectRegistry, *, request: CanonicalRouteRequest,
) -> ShadowRouteResult:
    """Sections 3-9: derives a shadow route over the EXISTING
    `ConnectivityGraph`/`resolve_route()` authority. Never fabricates a
    route: an origin/destination absent from the registry is reported
    explicitly, never assigned invented coordinates."""
    if request.origin_location_id not in registry.objects:
        return _unresolved(request, "UNRESOLVED_ORIGIN", f"{request.origin_location_id!r} is not a known canonical spatial object")
    if request.destination_location_id not in registry.objects:
        return _unresolved(request, "UNRESOLVED_DESTINATION", f"{request.destination_location_id!r} is not a known canonical spatial object")

    csa_mode = SHADOW_MODE_TO_CSA_MODE[request.transport_mode]
    result = csa.resolve_route(graph, origin_object_id=request.origin_location_id, destination_object_id=request.destination_location_id, mode=csa_mode)

    if not result.path_edge_ids and request.origin_location_id != request.destination_location_id:
        return _unresolved(request, "NO_ROUTE", f"no {csa_mode}-eligible path connects {request.origin_location_id!r} to {request.destination_location_id!r} in the supplied graph")

    edges_by_id = {e.edge_id: e for e in graph.edges}
    segments: list[RouteSegment] = []
    node_ids: list[str] = [request.origin_location_id]
    horizontal_m = 0.0
    vertical_m = 0.0
    vertical_transitions = 0
    for edge_id in result.path_edge_ids:
        edge = edges_by_id[edge_id]
        length_m = edge.length_m if edge.length_m != "NOT_CALIBRATED" else 0.0
        to_node = edge.to_object_id if edge.from_object_id == node_ids[-1] else edge.from_object_id
        orientation: Literal["HORIZONTAL", "VERTICAL"] = "VERTICAL" if edge.vertical else "HORIZONTAL"
        if edge.vertical:
            vertical_m += length_m
            vertical_transitions += 1
        else:
            horizontal_m += length_m
        segments.append(RouteSegment(segment_id=edge_id, from_node_id=node_ids[-1], to_node_id=to_node, length_m=length_m, orientation=orientation))
        node_ids.append(to_node)

    movement_time, time_note = _movement_time_minutes(request.transport_mode, horizontal_m, vertical_m)
    return ShadowRouteResult(
        route_id=request.route_request_id, origin_location_id=request.origin_location_id, destination_location_id=request.destination_location_id,
        transport_mode=request.transport_mode, ordered_node_ids=tuple(node_ids), ordered_edge_ids=result.path_edge_ids,
        ordered_segments=tuple(segments), horizontal_distance_m=horizontal_m, vertical_distance_m=vertical_m,
        total_distance_m=horizontal_m + vertical_m, vertical_transition_count=vertical_transitions,
        estimated_movement_time_minutes=movement_time, route_status="RESOLVED", provenance="CANONICAL_GRAPH_DERIVED",
        lockdown_id=request.lockdown_id, what_if_id=request.what_if_id, note=time_note,
    )


# ---------------------------------------------------------------------------
# Patient routing chain (sections 9-10)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PatientRouteLeg:
    leg: Literal["ROOM_TO_INJECTION", "INJECTION_TO_UPTAKE", "UPTAKE_TO_SCANNER", "SCANNER_TO_RETURN"]
    origin: str | None
    destination: str | None
    route: ShadowRouteResult | None


def derive_patient_shadow_route_chain(
    graph: csa.ConnectivityGraph, registry: csa.SpatialObjectRegistry, *, patient_id: str,
    patient_room_id: str | None, injection_room_id: str | None, uptake_room_id: str | None, scanner_room_id: str | None,
    lockdown_id: str | None = None, what_if_id: str | None = None,
) -> tuple[PatientRouteLeg, ...]:
    """Section 9: shadow-only -- never alters the clinical schedule. Any
    leg with an unresolved endpoint is reported, never skipped silently."""
    legs_spec: tuple[tuple[str, str | None, str | None], ...] = (
        ("ROOM_TO_INJECTION", patient_room_id, injection_room_id),
        ("INJECTION_TO_UPTAKE", injection_room_id, uptake_room_id),
        ("UPTAKE_TO_SCANNER", uptake_room_id, scanner_room_id),
        ("SCANNER_TO_RETURN", scanner_room_id, patient_room_id),
    )
    legs: list[PatientRouteLeg] = []
    for leg_name, origin, destination in legs_spec:
        if origin is None or destination is None:
            legs.append(PatientRouteLeg(leg=leg_name, origin=origin, destination=destination, route=None))
            continue
        request = CanonicalRouteRequest(
            route_request_id=f"PATIENT-{patient_id}-{leg_name}", subject_type="PATIENT", subject_id=patient_id,
            transport_mode="PATIENT_WALK", origin_location_id=origin, destination_location_id=destination,
            lockdown_id=lockdown_id, what_if_id=what_if_id,
        )
        legs.append(PatientRouteLeg(leg=leg_name, origin=origin, destination=destination, route=derive_shadow_route(graph, registry, request=request)))
    return tuple(legs)


# ---------------------------------------------------------------------------
# facility_engineering_model-based shadow routing (sections 15-17, 31) --
# path-reconstructing Dijkstra added HERE (never in facility_engineering_
# model.py); network_route_distance_m() there returns a scalar only.
# ---------------------------------------------------------------------------


def _facility_graph_shortest_path(
    nodes: Mapping[str, FacilitySpatialNode], edges: Sequence[FacilitySpatialEdge], *, start_node_id: str, end_node_id: str,
) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """Dijkstra WITH path reconstruction over the EXISTING `SpatialNode`/
    `SpatialEdge` tuples (as built by `spatial_benchmark.
    build_benchmark_geometry`) -- reuses their `length_m`/`vertical_change_m`
    fields verbatim; adds nothing to the underlying geometry model."""
    adjacency: dict[str, list[tuple[str, str, float]]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source_node_id, []).append((edge.destination_node_id, edge.edge_id, float(edge.length_m)))
        if edge.directionality in {"BIDIRECTIONAL", "ONE_WAY_REVERSE", "UNKNOWN"}:
            adjacency.setdefault(edge.destination_node_id, []).append((edge.source_node_id, edge.edge_id, float(edge.length_m)))

    if start_node_id not in nodes or end_node_id not in nodes:
        return None
    best: dict[str, float] = {start_node_id: 0.0}
    predecessor: dict[str, tuple[str, str]] = {}
    frontier: list[tuple[float, str]] = [(0.0, start_node_id)]
    while frontier:
        dist, node = heapq.heappop(frontier)
        if node == end_node_id:
            break
        if dist > best.get(node, float("inf")):
            continue
        for neighbor, edge_id, length in adjacency.get(node, ()):
            candidate = dist + length
            if candidate < best.get(neighbor, float("inf")):
                best[neighbor] = candidate
                predecessor[neighbor] = (node, edge_id)
                heapq.heappush(frontier, (candidate, neighbor))
    if end_node_id not in best:
        return None
    node_path = [end_node_id]
    edge_path: list[str] = []
    current = end_node_id
    while current != start_node_id:
        prev, edge_id = predecessor[current]
        edge_path.append(edge_id)
        node_path.append(prev)
        current = prev
    node_path.reverse()
    edge_path.reverse()
    return tuple(node_path), tuple(edge_path)


def derive_facility_graph_shadow_route(
    model: FacilityEngineeringObjectModel, *, request: CanonicalRouteRequest,
) -> ShadowRouteResult:
    """Sections 15-17: independently derives a route over the REAL
    benchmark geometry (`spatial_benchmark.build_benchmark_geometry`'s
    `base_model`) -- the only geometry representation that exists for the
    frozen eight-floor benchmark today. Never reads or replaces the frozen
    `mrt_guideway_horizontal_m`/`_vertical_m` reference values."""
    nodes_by_id = {n.node_id: n for n in model.nodes}
    edges_by_id = {e.edge_id: e for e in model.edges}
    origin_node = next((n for n in model.nodes if n.object_id == request.origin_location_id), None)
    destination_node = next((n for n in model.nodes if n.object_id == request.destination_location_id), None)
    if origin_node is None:
        return _unresolved(request, "UNRESOLVED_ORIGIN", f"{request.origin_location_id!r} has no node in the facility engineering graph")
    if destination_node is None:
        return _unresolved(request, "UNRESOLVED_DESTINATION", f"{request.destination_location_id!r} has no node in the facility engineering graph")

    path = _facility_graph_shortest_path(nodes_by_id, model.edges, start_node_id=origin_node.node_id, end_node_id=destination_node.node_id)
    if path is None:
        return _unresolved(request, "NO_ROUTE", f"no network route connects {origin_node.node_id!r} to {destination_node.node_id!r}")
    node_path, edge_path = path

    segments: list[RouteSegment] = []
    horizontal_m = 0.0
    vertical_m = 0.0
    vertical_transitions = 0
    for index, edge_id in enumerate(edge_path):
        edge = edges_by_id[edge_id]
        orientation: Literal["HORIZONTAL", "VERTICAL"] = "VERTICAL" if edge.vertical_change_m else "HORIZONTAL"
        if edge.vertical_change_m:
            vertical_m += abs(edge.vertical_change_m)
            vertical_transitions += 1
        else:
            horizontal_m += edge.length_m
        segments.append(RouteSegment(segment_id=edge_id, from_node_id=node_path[index], to_node_id=node_path[index + 1], length_m=edge.length_m, orientation=orientation))

    movement_time, time_note = _movement_time_minutes(request.transport_mode, horizontal_m, vertical_m)
    return ShadowRouteResult(
        route_id=request.route_request_id, origin_location_id=request.origin_location_id, destination_location_id=request.destination_location_id,
        transport_mode=request.transport_mode, ordered_node_ids=node_path, ordered_edge_ids=edge_path, ordered_segments=tuple(segments),
        horizontal_distance_m=horizontal_m, vertical_distance_m=vertical_m, total_distance_m=horizontal_m + vertical_m,
        vertical_transition_count=vertical_transitions, estimated_movement_time_minutes=movement_time, route_status="RESOLVED",
        provenance="FACILITY_ENGINEERING_GRAPH_DERIVED", lockdown_id=request.lockdown_id, what_if_id=request.what_if_id, note=time_note,
    )


# ---------------------------------------------------------------------------
# MRT 222m reconciliation (sections 15-17, 31)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MrtReconciliationRow:
    metric: str
    frozen_reference: float | int | None
    geometry_shadow: float | int | None
    delta: float | int | None
    interpretation: str


def reconcile_mrt_guideway(
    model: FacilityEngineeringObjectModel, *, frozen_horizontal_m: float, frozen_vertical_m: float,
    production_object_id: str, representative_room_object_id: str,
) -> tuple[MrtReconciliationRow, ...]:
    """Sections 16-17: NEVER overwrites `frozen_horizontal_m`/
    `frozen_vertical_m` (they are passed in from an EXISTING, already-
    computed `HybridEvaluationResult`, never recomputed here). Independently
    derives a SINGLE representative mission route (production -> one
    serviced room) via the path-reconstructing Dijkstra above -- this is
    deliberately a DIFFERENT quantity than the frozen reference's
    deduplicated multi-floor TRUNK total (section 17); the interpretation
    column states this explicitly rather than forcing a false match."""
    request = CanonicalRouteRequest(
        route_request_id="MRT-RECONCILIATION-PROBE", subject_type="GENERIC", subject_id="MRT-GUIDEWAY",
        transport_mode="MRT", origin_location_id=production_object_id, destination_location_id=representative_room_object_id,
    )
    shadow = derive_facility_graph_shadow_route(model, request=request)
    frozen_total = frozen_horizontal_m + frozen_vertical_m
    shadow_total = shadow.total_distance_m

    def _row(metric: str, frozen: float, shadow_value: float | None, interpretation: str) -> MrtReconciliationRow:
        delta = (shadow_value - frozen) if shadow_value is not None else None
        return MrtReconciliationRow(metric=metric, frozen_reference=frozen, geometry_shadow=shadow_value, delta=delta, interpretation=interpretation)

    return (
        _row("horizontal_guideway_length_m", frozen_horizontal_m, shadow.horizontal_distance_m,
             "Frozen value is a DEDUPLICATED multi-floor TRUNK total (compute_inbound_room_guideway_extension, "
             "accumulated once per already-serviced floor); shadow value is a SINGLE representative mission route "
             "(production -> one room) -- these are legitimately different quantities per section 17, not a defect."),
        _row("vertical_guideway_length_m", frozen_vertical_m, shadow.vertical_distance_m,
             "Same scope difference as horizontal: frozen is deduplicated trunk total across all MRT-serviced "
             "floors; shadow is the vertical span of one representative route."),
        _row("total_guideway_or_route_length_m", frozen_total, shadow_total,
             "See above -- comparing a network/trunk total against a single-route shadow is expected to differ; "
             "this row exists to make that difference explicit and measurable, not to force MATCH."),
        MrtReconciliationRow(
            metric="vertical_transitions", frozen_reference=None, geometry_shadow=shadow.vertical_transition_count, delta=None,
            interpretation="No frozen transition-count reference is exposed by HybridEvaluationResult; shadow value shown for disclosure only.",
        ),
    )

"""Transport Spatial Authority Build 1: Mode-Neutral Mission Route Bridge.

GOVERNANCE: this module answers exactly one question per production
mission: "do we have a REAL calibrated spatial route for this mission?" It
is NOT a routing engine -- it never computes a new path-finding algorithm,
reusing `canonical_spatial_authority.resolve_route`/`ConnectivityGraph`
verbatim (the SAME mode-aware BFS route authority already used elsewhere
in this repository). It imports nothing from OpenUSD/pxr, NVIDIA/Omniverse,
or Bentley, and never mutates the supplied registry/graph or any
`LockedSpatialState`/`WhatIfSpatialState`.

WHY NOT `canonical_geometry_shadow_routing_authority.py`: that module is
explicitly documented as SHADOW/DIAGNOSTIC ONLY, with its own governing
invariant `CURRENT_RESULT_BEFORE_PHASE_2A == CURRENT_RESULT_AFTER_PHASE_2A`
-- its results must never feed an authoritative production timing
calculation. Because THIS bridge is explicitly intended to feed real
distance into production mission timing (per this build's requirement), it
deliberately reuses the LOWER-LEVEL `canonical_spatial_authority.
resolve_route`/`ConnectivityGraph` authority directly instead, so as to
never contradict that module's own documented governance.
`canonical_geometry_shadow_routing_authority.py` itself remains completely
untouched and diagnostic-only.

SPATIAL NETWORK AVAILABILITY: MRT and MANUAL_PORTER/PORTER_CART have always
had a first-class canonical spatial network available. Transport Spatial
Authority Build 2 added RGHT (`rght_spatial_network_authority.py`) and
Build 3 added PNEUMATIC_TUBE (`pts_spatial_network_authority.py`) to that
set -- both now resolve a real calibrated route when a caller supplies a
registry/graph containing an actual network (edges tagged with the
existing `"AGV_AMR"`/`"PNEUMATIC_TUBE"` `TransportMode` values,
respectively); they still honestly report `SPATIAL_NETWORK_NOT_CALIBRATED`
when no registry/graph is supplied, OR when the supplied graph contains no
mode-eligible edge at all (i.e. genuinely no network for that technology,
as opposed to `ROUTE_NOT_CALIBRATED`, which means a network exists but this
specific origin/destination pair isn't connected within it). A
`SPATIAL_NETWORK_NOT_CALIBRATED` (or any other not-calibrated) status NEVER
implies operational/economic infeasibility -- that determination remains
entirely owned by the existing operational/economic authorities. PTS
mission TIMING is NEVER changed by attaching route metadata (see
`pts_spatial_network_authority.py`'s module docstring for the timing-audit
finding that led to this decision).
"""


from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import canonical_spatial_authority as csa
import transport_technology_authority as tta

RouteCalibrationStatus = Literal[
    "ROUTE_CALIBRATED", "ROUTE_NOT_CALIBRATED", "SPATIAL_NETWORK_NOT_CALIBRATED", "ROUTE_UNAVAILABLE",
]

_MODE_HAS_SPATIAL_NETWORK: frozenset[str] = frozenset({"MRT", "MANUAL_PORTER", "PORTER_CART", "RGHT", "PNEUMATIC_TUBE"})
"""Only these canonical technologies have a first-class spatial network
today. `PORTER_CART` shares the SAME pedestrian-compatible network as
`MANUAL_PORTER` (there is no separate `canonical_spatial_authority.
TransportMode` for cart-assisted porter movement). `RGHT` was added in
Transport Spatial Authority Build 2 (`rght_spatial_network_authority.py`).
`PNEUMATIC_TUBE` was added in Transport Spatial Authority Build 3
(`pts_spatial_network_authority.py`) -- it resolves a real route ONLY when
a caller supplies a registry/graph containing an actual PTS network
(edges tagged with the existing `"PNEUMATIC_TUBE"` TransportMode); with no
such network supplied it still honestly reports
`SPATIAL_NETWORK_NOT_CALIBRATED` (never inferred from a scalar
`network_length_m`)."""

_REPORTS_SPATIAL_NETWORK_NOT_CALIBRATED_WHEN_NO_NETWORK: frozenset[str] = frozenset({"RGHT", "PNEUMATIC_TUBE"})
"""Build 2/3 section 18/21: RGHT and PNEUMATIC_TUBE specifically must
report `SPATIAL_NETWORK_NOT_CALIBRATED` (not the generic
`ROUTE_NOT_CALIBRATED`) when no registry/graph is supplied, or when the
supplied graph contains no mode-eligible edge at all -- i.e. when NO real
network exists for that technology, as opposed to a network existing but
this particular pair being unconnected within it. MRT/MANUAL_PORTER/
PORTER_CART are unaffected (unchanged from Build 1: they report
`ROUTE_NOT_CALIBRATED` in that same scenario)."""

_MISSION_MODE_TO_CSA_MODE: dict[str, csa.TransportMode] = {
    "MRT": "MRT",
    "MANUAL_PORTER": "WALKING_PORTER",
    "PORTER_CART": "WALKING_PORTER",
    "RGHT": "AGV_AMR",
    "PNEUMATIC_TUBE": "PNEUMATIC_TUBE",
}


@dataclass(frozen=True)
class MissionRouteResolution:
    """The smallest vendor-neutral mission-routing contract -- answers
    'do we have a real spatial route for this mission' only."""

    mission_id: str
    transport_mode: str
    origin_object_id: str
    destination_object_id: str
    route_status: RouteCalibrationStatus
    route_id: str | None
    route_distance_m: float | None
    route_node_ids: tuple[str, ...]
    geometry_authority: str
    provenance: str


def _not_calibrated(
    *, mission_id: str, transport_mode: str, origin_object_id: str, destination_object_id: str,
    route_status: RouteCalibrationStatus, geometry_authority: str, provenance: str,
) -> MissionRouteResolution:
    return MissionRouteResolution(
        mission_id=mission_id, transport_mode=transport_mode, origin_object_id=origin_object_id,
        destination_object_id=destination_object_id, route_status=route_status, route_id=None,
        route_distance_m=None, route_node_ids=(), geometry_authority=geometry_authority, provenance=provenance,
    )


def resolve_mission_route(
    *, mission_id: str, transport_mode: str, origin_object_id: str, destination_object_id: str,
    registry: csa.SpatialObjectRegistry | None = None, graph: csa.ConnectivityGraph | None = None,
) -> MissionRouteResolution:
    """Resolves a mission's spatial route ONLY when a real canonical
    spatial network exists for its technology AND a registry/graph are
    supplied AND the origin/destination are both known canonical objects.
    Never fabricates route geometry for RGHT/PNEUMATIC_TUBE, and never
    claims a route exists merely because a caller forgot to supply a
    registry/graph."""
    canonical_technology = tta.normalize_transport_technology(transport_mode)

    if canonical_technology not in _MODE_HAS_SPATIAL_NETWORK:
        return _not_calibrated(
            mission_id=mission_id, transport_mode=transport_mode, origin_object_id=origin_object_id,
            destination_object_id=destination_object_id, route_status="SPATIAL_NETWORK_NOT_CALIBRATED",
            geometry_authority="NONE",
            provenance=f"{canonical_technology} has no first-class canonical spatial network in this repository",
        )

    not_calibrated_status: RouteCalibrationStatus = (
        "SPATIAL_NETWORK_NOT_CALIBRATED" if canonical_technology in _REPORTS_SPATIAL_NETWORK_NOT_CALIBRATED_WHEN_NO_NETWORK else "ROUTE_NOT_CALIBRATED"
    )

    if registry is None or graph is None:
        return _not_calibrated(
            mission_id=mission_id, transport_mode=transport_mode, origin_object_id=origin_object_id,
            destination_object_id=destination_object_id, route_status=not_calibrated_status,
            geometry_authority="NONE", provenance="no canonical registry/connectivity graph supplied to the route bridge",
        )

    if origin_object_id not in registry.objects or destination_object_id not in registry.objects:
        return _not_calibrated(
            mission_id=mission_id, transport_mode=transport_mode, origin_object_id=origin_object_id,
            destination_object_id=destination_object_id, route_status="ROUTE_UNAVAILABLE",
            geometry_authority="canonical_spatial_authority.resolve_route",
            provenance="origin/destination not present in the supplied canonical registry",
        )

    csa_mode = _MISSION_MODE_TO_CSA_MODE[canonical_technology]
    if not graph.edges_for_mode(csa_mode):
        return _not_calibrated(
            mission_id=mission_id, transport_mode=transport_mode, origin_object_id=origin_object_id,
            destination_object_id=destination_object_id, route_status=not_calibrated_status,
            geometry_authority="canonical_spatial_authority.resolve_route",
            provenance=f"supplied connectivity graph contains no {csa_mode}-eligible edge -- no {canonical_technology} network present",
        )

    result = csa.resolve_route(graph, origin_object_id=origin_object_id, destination_object_id=destination_object_id, mode=csa_mode)
    if result.calibration_status == "CALIBRATED":
        return MissionRouteResolution(
            mission_id=mission_id, transport_mode=transport_mode, origin_object_id=origin_object_id,
            destination_object_id=destination_object_id, route_status="ROUTE_CALIBRATED",
            route_id=("-".join(result.path_edge_ids) or f"{origin_object_id}::{destination_object_id}"),
            route_distance_m=float(result.distance_m), route_node_ids=_edge_path_to_node_ids(graph, origin_object_id, result.path_edge_ids),
            geometry_authority="canonical_spatial_authority.resolve_route", provenance="real canonical connectivity graph BFS resolution",
        )
    return _not_calibrated(
        mission_id=mission_id, transport_mode=transport_mode, origin_object_id=origin_object_id,
        destination_object_id=destination_object_id, route_status="ROUTE_NOT_CALIBRATED",
        geometry_authority="canonical_spatial_authority.resolve_route",
        provenance="a network exists for this technology but no calibrated path connects the supplied origin/destination",
    )


def _edge_path_to_node_ids(graph: csa.ConnectivityGraph, origin_object_id: str, path_edge_ids: tuple[str, ...]) -> tuple[str, ...]:
    edges_by_id = {e.edge_id: e for e in graph.edges}
    node_ids = [origin_object_id]
    for edge_id in path_edge_ids:
        edge = edges_by_id[edge_id]
        next_node = edge.to_object_id if edge.from_object_id == node_ids[-1] else edge.from_object_id
        node_ids.append(next_node)
    return tuple(node_ids)

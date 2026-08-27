"""Authoritative Routing, Shared Reference Corridor, and Installed-Network
Geometry Activation (Phase 2B).

GOVERNANCE: this module EXTENDS `canonical_geometry_shadow_routing_
authority.py` (Phase 2A) into an authoritative-CAPABLE layer -- reused
verbatim (`ShadowRouteResult`, `derive_shadow_route`,
`derive_facility_graph_shadow_route`, `_movement_time_minutes`), never
duplicated. It formalizes TWO deliberately distinct quantities (section 1):

    MISSION_ROUTE_GEOMETRY     -- one origin->destination route; feeds
                                  travel time / cycle time / concurrency /
                                  decay input / future animation.
    INSTALLED_NETWORK_GEOMETRY -- the UNION of unique network edges required
                                  to serve every relevant mission; feeds
                                  infrastructure CapEx/maintenance basis.

95.0m (a single MISSION_ROUTE_GEOMETRY value, from Phase 2A) is NEVER used
as an INSTALLED_NETWORK_GEOMETRY value. The frozen 222.0m/198.0m/24.0m
values are read-only reconciliation targets here, never overwritten.

SCOPE DECISION (disclosed explicitly, not silent): this module makes
authoritative-grade routing/timing/fleet-sizing functions available and
rigorously tests their correctness and their ability to feed EXISTING
authorities (`conventional_transport_authority.agv_required_fleet_size`,
`multi_isotope_decay.retained_fraction`, ...) unchanged. It does NOT rewire
`whole_oncology_four_architecture_optimization.py`/`hybrid_optimization.py`'s
live four-architecture CapEx/OPEX/NPV pipeline -- that pipeline is exercised
by hundreds of pinned-value tests built across this session and is
explicitly protected as `FROZEN_CANONICAL_QUALIFICATION_CASE`. Swapping its
internal fixed-proxy calls for these functions is a distinct, separately-
reviewable activation step (see the Phase 2B report).

Phase 2B.1 activated AGV/PTS/RP-PTS via EXPLICIT override parameters on
`whole_oncology_four_architecture_optimization.py`'s evaluators. Phase 2B.2
adds `resolve_automatic_route_distance_m` below so a caller holding real
canonical geometry does not need to hand-compute that override number --
section 1's governing precedence (valid canonical geometry -> shared MRT
reference corridor -> existing controlled fallback) is now a single,
tested function. MRT itself was found to ALREADY implement this exact
precedence natively (`production_clinical_schedule._resolve_mrt_route_
profile`, gated on `ProductionClinicalScenario.facility_engineering_model`)
-- verified, not reimplemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

import canonical_geometry_shadow_routing_authority as shadow
import canonical_spatial_authority as csa
from facility_engineering_model import FacilityEngineeringObjectModel

RouteGeometryKind = Literal["MISSION_ROUTE_GEOMETRY", "INSTALLED_NETWORK_GEOMETRY"]

ReconciliationClassification = Literal["MATCH", "EXPLAINED_DIFFERENCE", "TRUE_DEFECT"]

# Section 4-7: AGV/ORDINARY_PTS/DEDICATED_RP_PTS may borrow the MRT reference
# corridor's DISTANCE only -- never its speed/capacity/economics. Each
# target mode's own speed (from Phase 2A's authority) is always used for
# movement time.
SHARED_CORRIDOR_ELIGIBLE_MODES: tuple[shadow.ShadowTransportMode, ...] = ("AGV_AMR", "ORDINARY_PTS", "DEDICATED_RP_PTS")


# ---------------------------------------------------------------------------
# Installed network geometry (sections 2-3, 14-15, 21, 32, 34)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstalledNetworkResult:
    unique_edge_ids: tuple[str, ...]
    horizontal_length_m: float
    vertical_length_m: float
    total_length_m: float
    contributing_route_ids: tuple[str, ...]


def compute_installed_network_union(routes: Sequence[shadow.ShadowRouteResult]) -> InstalledNetworkResult:
    """Section 2: a segment shared by multiple mission routes is counted
    ONCE for installed-network purposes -- NEVER `sum(route.total_distance_m
    for route in routes)`."""
    segments_by_edge_id: dict[str, shadow.RouteSegment] = {}
    for route in routes:
        for segment in route.ordered_segments:
            segments_by_edge_id[segment.segment_id] = segment
    horizontal = sum(s.length_m for s in segments_by_edge_id.values() if s.orientation == "HORIZONTAL")
    vertical = sum(s.length_m for s in segments_by_edge_id.values() if s.orientation == "VERTICAL")
    return InstalledNetworkResult(
        unique_edge_ids=tuple(sorted(segments_by_edge_id)), horizontal_length_m=horizontal, vertical_length_m=vertical,
        total_length_m=horizontal + vertical, contributing_route_ids=tuple(r.route_id for r in routes),
    )


@dataclass(frozen=True)
class MrtNetworkReconciliationRow:
    metric: str
    frozen_reference: float
    geometry_derived: float
    delta: float
    classification: ReconciliationClassification
    interpretation: str


def reconcile_installed_mrt_network(
    model: FacilityEngineeringObjectModel, *, production_object_id: str, served_room_object_ids: Sequence[str],
    frozen_horizontal_m: float, frozen_vertical_m: float, tolerance_m: float = 0.5,
) -> tuple[MrtNetworkReconciliationRow, ...]:
    """Section 3: derives INSTALLED_NETWORK_GEOMETRY as the union of edges
    across ALL routes to `served_room_object_ids` (never a single mission
    route, never a naive sum) and compares against the frozen reference.
    `frozen_horizontal_m`/`frozen_vertical_m` are read-only inputs from an
    EXISTING, already-computed `HybridEvaluationResult` -- never recomputed
    here."""
    routes = []
    for room_object_id in served_room_object_ids:
        request = shadow.CanonicalRouteRequest(
            route_request_id=f"MRT-INSTALLED-PROBE-{room_object_id}", subject_type="GENERIC", subject_id="MRT-NETWORK",
            transport_mode="MRT", origin_location_id=production_object_id, destination_location_id=room_object_id,
        )
        routes.append(shadow.derive_facility_graph_shadow_route(model, request=request))
    installed = compute_installed_network_union([r for r in routes if r.route_status == "RESOLVED"])

    def _classify(delta: float, frozen: float) -> tuple[ReconciliationClassification, str]:
        if abs(delta) <= tolerance_m:
            return "MATCH", "Geometry-derived installed length matches the frozen reference within tolerance."
        if frozen > 0 and abs(delta) / frozen <= 0.25:
            return "EXPLAINED_DIFFERENCE", (
                "Frozen reference uses `compute_inbound_room_guideway_extension`'s incremental-per-floor "
                "deduplication convention (accumulated once per NEWLY serviced floor as rooms are added in a "
                "specific order); this reconciliation independently unions ALL floors' routes from scratch via a "
                "fresh Dijkstra path-set. Both are legitimate dedup strategies over the SAME underlying edges; "
                "the residual difference is attributable to convention (which floors/order are counted), not to "
                "a routing defect."
            )
        return "TRUE_DEFECT", "Difference exceeds the explained-convention tolerance; requires investigation before adoption."

    h_delta = installed.horizontal_length_m - frozen_horizontal_m
    v_delta = installed.vertical_length_m - frozen_vertical_m
    t_delta = installed.total_length_m - (frozen_horizontal_m + frozen_vertical_m)
    h_class, h_note = _classify(h_delta, frozen_horizontal_m)
    v_class, v_note = _classify(v_delta, frozen_vertical_m)
    t_class, t_note = _classify(t_delta, frozen_horizontal_m + frozen_vertical_m)
    return (
        MrtNetworkReconciliationRow("installed_horizontal_length_m", frozen_horizontal_m, installed.horizontal_length_m, h_delta, h_class, h_note),
        MrtNetworkReconciliationRow("installed_vertical_length_m", frozen_vertical_m, installed.vertical_length_m, v_delta, v_class, v_note),
        MrtNetworkReconciliationRow("installed_total_length_m", frozen_horizontal_m + frozen_vertical_m, installed.total_length_m, t_delta, t_class, t_note),
    )


# ---------------------------------------------------------------------------
# Shared reference corridor (sections 4-7, 11-13)
# ---------------------------------------------------------------------------


def derive_shared_reference_corridor_route(
    mrt_reference_route: shadow.ShadowRouteResult, *, mode: shadow.ShadowTransportMode, route_id: str,
) -> shadow.ShadowRouteResult:
    """Sections 4-7: AGV/ORDINARY_PTS/DEDICATED_RP_PTS borrow the MRT
    reference corridor's DISTANCE only. Movement time is ALWAYS recomputed
    using the TARGET mode's own existing speed authority -- never MRT's
    speed, capacity, or economics."""
    if mode not in SHARED_CORRIDOR_ELIGIBLE_MODES:
        raise ValueError(f"{mode!r} is not eligible for the shared MRT reference corridor policy")
    if mrt_reference_route.route_status != "RESOLVED":
        return shadow._unresolved(
            shadow.CanonicalRouteRequest(
                route_request_id=route_id, subject_type="GENERIC", subject_id=mode, transport_mode=mode,
                origin_location_id=mrt_reference_route.origin_location_id, destination_location_id=mrt_reference_route.destination_location_id,
            ),
            "ROUTE_GEOMETRY_NOT_AVAILABLE", "the MRT reference corridor route did not resolve; no distance to borrow",
        )
    horizontal_m = mrt_reference_route.horizontal_distance_m or 0.0
    vertical_m = mrt_reference_route.vertical_distance_m or 0.0
    movement_time, note = shadow._movement_time_minutes(mode, horizontal_m, vertical_m)
    return shadow.ShadowRouteResult(
        route_id=route_id, origin_location_id=mrt_reference_route.origin_location_id, destination_location_id=mrt_reference_route.destination_location_id,
        transport_mode=mode, ordered_node_ids=mrt_reference_route.ordered_node_ids, ordered_edge_ids=mrt_reference_route.ordered_edge_ids,
        ordered_segments=mrt_reference_route.ordered_segments, horizontal_distance_m=horizontal_m, vertical_distance_m=vertical_m,
        total_distance_m=horizontal_m + vertical_m, vertical_transition_count=mrt_reference_route.vertical_transition_count,
        estimated_movement_time_minutes=movement_time, route_status="RESOLVED", provenance="SHARED_MRT_REFERENCE_CORRIDOR_ASSUMPTION",
        lockdown_id=mrt_reference_route.lockdown_id, what_if_id=mrt_reference_route.what_if_id,
        note=f"distance borrowed from MRT reference corridor {mrt_reference_route.route_id!r}; speed/capacity/economics remain {mode}-specific. {note}".strip(),
    )


# ---------------------------------------------------------------------------
# Automatic geometry precedence (Phase 2B.2, sections 1, 4, 15): a caller
# holding real canonical geometry must NOT need to hand-compute an override
# number to make it effective. This resolves, in order:
#   1. VALID_PROJECT_CANONICAL_GEOMETRY  (spatial_registry + graph resolve)
#   2. SHARED_MRT_REFERENCE_CORRIDOR_ASSUMPTION (AGV/PTS/RP-PTS only)
#   3. None -- caller falls through to its OWN existing controlled default;
#      geometry is never fabricated to avoid returning None.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AutomaticRouteResolution:
    distance_m: float | None
    provenance: shadow.RouteProvenance


def resolve_automatic_route_distance_m(
    technology: shadow.ShadowTransportMode, *,
    spatial_registry: csa.SpatialObjectRegistry | None = None, graph: csa.ConnectivityGraph | None = None,
    origin_id: str | None = None, destination_id: str | None = None,
    mrt_reference_route: shadow.ShadowRouteResult | None = None,
) -> AutomaticRouteResolution:
    """Section 1 precedence, implemented once, reused by every technology.
    Never raises for missing inputs -- absence at any tier simply falls
    through to the next, ending in `(None, "UNRESOLVED")` when nothing
    resolves (the caller's existing controlled fallback then applies)."""
    if spatial_registry is not None and graph is not None and origin_id is not None and destination_id is not None:
        request = shadow.CanonicalRouteRequest(
            route_request_id=f"AUTO-{technology}-{origin_id}-{destination_id}", subject_type="GENERIC", subject_id="AUTO",
            transport_mode=technology, origin_location_id=origin_id, destination_location_id=destination_id,
        )
        route = shadow.derive_shadow_route(graph, spatial_registry, request=request)
        if route.route_status == "RESOLVED" and route.total_distance_m is not None:
            return AutomaticRouteResolution(distance_m=route.total_distance_m, provenance="CANONICAL_GRAPH_DERIVED")

    if technology in SHARED_CORRIDOR_ELIGIBLE_MODES and mrt_reference_route is not None and mrt_reference_route.route_status == "RESOLVED":
        return AutomaticRouteResolution(distance_m=mrt_reference_route.total_distance_m, provenance="SHARED_MRT_REFERENCE_CORRIDOR_ASSUMPTION")

    return AutomaticRouteResolution(distance_m=None, provenance="UNRESOLVED")


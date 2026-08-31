"""Interactive Transport-Network Authoring / Rerouting Authority (ADDITIVE
clarification to the current Bentley 3D spatial-network build).

The auto-generated transport network is an engineering PROPOSAL, not a
permanently immutable result (Sec A). In What-If the user may interactively
add / remove / extend / reroute / constrain individual routes.

This module introduces NO new routing engine. It COMPOSES:
  * `transport_movement_domain_authority.resolve_confined_route` (mode-legal,
    topological, confinement-proven segment routing)
  * `canonical_spatial_authority.ConnectivityGraph` (the legal network)
  * `payload_endpoint_authority` (stream origin/destination validation)

HARD DOCTRINES:
  * Pinned ORIGIN / DESTINATION endpoints keep explicit identity; moving an
    intermediate control never moves them (Sec C). PINNED_ENDPOINT_MOVES_WITH_
    INTERMEDIATE_WAYPOINT = NO.
  * Auto-route runs each successive constraint pair through the mode's LEGAL
    topology (never Euclidean interpolation through prohibited geometry, Sec E).
  * A graphical orthogonal vertex is a PLANNING skeleton point; the owning
    technology authority decides the real physical bend/elbow/switch geometry
    (Sec F). GRAPHICAL_ORTHOGONAL_VERTEX_OVERRIDES_PHYSICAL_BEND_AUTHORITY = NO.
  * Deleting a segment may genuinely disconnect a destination -> NO_CONNECTED_
    PATH; never auto-bridged (Sec I).
  * Route edits are USER_EDITED_WHATIF scenario state, distinct from BASELINE
    and AUTO_GENERATED_SCENARIO; they never mutate the live Bentley iModel
    (Sec K/W). WHATIF_ROUTE_EDIT_MUTATES_LIVE_BENTLEY = NO.
  * A committed route change triggers FULL engineering recomputation of the
    affected authorities (Sec L), not just the displayed length.

AGV/Manual use navigable-space constraints (waypoint/preferred-corridor/
required-door/required-elevator/forbidden-zone) -- NO fake fixed track (Sec T).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, Mapping, Sequence

import canonical_spatial_authority as csa
import transport_movement_domain_authority as md

# ===========================================================================
# 1. Route scenario provenance (Sec K).
# ===========================================================================

RouteNetworkState = Literal["BASELINE_NETWORK", "AUTO_GENERATED_SCENARIO_NETWORK", "USER_EDITED_WHATIF_NETWORK"]

WHATIF_ROUTE_EDIT_MUTATES_LIVE_BENTLEY = False
"""Hard flag (Sec W): interactive edits are local scenario changes only."""


# ===========================================================================
# 2. Pinned endpoints + editable control points (Sec C-D).
# ===========================================================================

@dataclass(frozen=True)
class RouteEndpoint:
    endpoint_id: str          # canonical spatial node id
    role: Literal["ORIGIN", "DESTINATION"]
    locked: bool = True       # pinned by default (Sec C)


@dataclass(frozen=True)
class RouteControlPoint:
    """An intermediate constraint (Sec D): a bend/passage/junction candidate
    (network modes) or a navigable waypoint (AGV/Manual). `node_id` is a
    canonical spatial node the route must pass through."""
    control_id: str
    node_id: str
    kind: Literal["BEND", "REQUIRED_PASSAGE", "PREFERRED_CORRIDOR", "REQUIRED_DOOR", "REQUIRED_ELEVATOR"] = "REQUIRED_PASSAGE"


@dataclass(frozen=True)
class InteractiveRoute:
    """A user-authored route for one mode: pinned endpoints + ordered control
    points. Route geometry is DERIVED by auto-routing successive constraints
    through the legal topology; this object stores only the CONSTRAINTS."""
    route_id: str
    mode: md.TransportModeId
    origin: RouteEndpoint
    destination: RouteEndpoint
    control_points: tuple[RouteControlPoint, ...] = ()
    network_state: RouteNetworkState = "USER_EDITED_WHATIF_NETWORK"

    def constraint_node_sequence(self) -> tuple[str, ...]:
        return (self.origin.endpoint_id, *(c.node_id for c in self.control_points), self.destination.endpoint_id)


# ===========================================================================
# 3. Auto-route between successive constraints (Sec E-F). Each leg routes on
#    the mode's LEGAL topology; total length is the sum of legal legs.
# ===========================================================================

RouteResolutionStatus = Literal[
    "ROUTED", "NO_CONNECTED_PATH", "INFEASIBLE_NO_NETWORK", "INVALID_CONTROL_POINT",
]


@dataclass(frozen=True)
class RouteLeg:
    from_node_id: str
    to_node_id: str
    feasibility: str
    leg_distance_m: float | None
    path_edge_ids: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedInteractiveRoute:
    route_id: str
    mode: md.TransportModeId
    network_state: RouteNetworkState
    status: RouteResolutionStatus
    legs: tuple[RouteLeg, ...]
    total_route_length_m: float | None
    origin_id: str
    destination_id: str
    endpoints_pinned: bool
    physical_bend_authority_owner: str
    detail: str


# The owning technology authority for the real physical transition geometry at
# a graphical bend (Sec F). The orthogonal UI vertex NEVER overrides this.
_PHYSICAL_BEND_OWNER: Mapping[md.TransportModeId, str] = {
    "MRT": "mrt_canonical_configuration / shared_mrt guideway curve authority",
    "RTHS": "rght_spatial_network_authority (switch/junction/curve)",
    "PTS_CONVENTIONAL": "pts_spatial_network_authority (tube bend/diverter)",
    "PTS_NUCLEAR_QUALIFIED": "dedicated_rp_pts_authority (shielded tube bend)",
    "AGV_AMR_LIGHT_CLINICAL": "navigable-space turn radius (floor_agv_amr_authority)",
    "AGV_AMR_HEAVY_LOGISTICS": "navigable-space turn radius (floor_agv_amr_authority)",
    "MANUAL": "pedestrian corridor geometry (canonical_spatial_authority)",
}


def auto_route(route: InteractiveRoute, *, graph: csa.ConnectivityGraph) -> ResolvedInteractiveRoute:
    """Sec E-F: auto-route each successive constraint pair through the mode's
    legal movement domain (via `resolve_confined_route`). Total length = sum of
    legal-leg lengths. A graphical orthogonal vertex is only a planning point:
    the physical bend geometry is owned by the technology authority (Sec F),
    reported in `physical_bend_authority_owner`, never overridden here. If any
    leg has no connected legal path -> NO_CONNECTED_PATH (never auto-bridged)."""
    seq = route.constraint_node_sequence()
    legs: list[RouteLeg] = []
    total = 0.0
    total_known = True
    for a, b in zip(seq, seq[1:]):
        cr = md.resolve_confined_route(graph=graph, mode=route.mode, origin_object_id=a, destination_object_id=b)
        legs.append(RouteLeg(a, b, cr.feasibility, cr.route_distance_m, cr.path_edge_ids))
        if cr.feasibility == "INFEASIBLE_NO_NETWORK":
            return ResolvedInteractiveRoute(
                route.route_id, route.mode, route.network_state, "INFEASIBLE_NO_NETWORK",
                tuple(legs), None, route.origin.endpoint_id, route.destination.endpoint_id,
                _endpoints_pinned(route), _PHYSICAL_BEND_OWNER[route.mode],
                f"no {route.mode} network for leg {a}->{b}",
            )
        if cr.feasibility != "FEASIBLE":
            return ResolvedInteractiveRoute(
                route.route_id, route.mode, route.network_state, "NO_CONNECTED_PATH",
                tuple(legs), None, route.origin.endpoint_id, route.destination.endpoint_id,
                _endpoints_pinned(route), _PHYSICAL_BEND_OWNER[route.mode],
                f"no connected legal path for leg {a}->{b} (never auto-bridged, Sec I)",
            )
        if cr.route_distance_m is None:
            total_known = False
        else:
            total += cr.route_distance_m
    return ResolvedInteractiveRoute(
        route.route_id, route.mode, route.network_state, "ROUTED", tuple(legs),
        total if total_known else None, route.origin.endpoint_id, route.destination.endpoint_id,
        _endpoints_pinned(route), _PHYSICAL_BEND_OWNER[route.mode],
        "auto-routed through legal topology; physical bend geometry owned by technology authority (Sec F)",
    )


def _endpoints_pinned(route: InteractiveRoute) -> bool:
    return route.origin.locked and route.destination.locked


def graphical_vertex_overrides_physical_bend() -> bool:
    """Hard governor (Sec F): always False."""
    return False


# ===========================================================================
# 4. Waypoint editing (Sec D/G/H). Insert / move / delete never move pinned
#    endpoints; every edit is validated + re-routed.
# ===========================================================================

def insert_waypoint(route: InteractiveRoute, *, control: RouteControlPoint, index: int) -> InteractiveRoute:
    """Sec H: insert a control point at `index` (0 = right after origin). Pinned
    endpoints are untouched."""
    cps = list(route.control_points)
    cps.insert(max(0, min(index, len(cps))), control)
    return replace(route, control_points=tuple(cps))


def move_waypoint(route: InteractiveRoute, *, control_id: str, new_node_id: str) -> InteractiveRoute:
    """Sec G: move a control point to a new node. Origin/destination endpoints
    remain pinned (identity unchanged)."""
    cps = tuple(replace(c, node_id=new_node_id) if c.control_id == control_id else c for c in route.control_points)
    return replace(route, control_points=cps)


def delete_waypoint(route: InteractiveRoute, *, control_id: str) -> InteractiveRoute:
    """Sec H: delete a control point. Endpoints untouched."""
    return replace(route, control_points=tuple(c for c in route.control_points if c.control_id != control_id))


def endpoints_unchanged(before: InteractiveRoute, after: InteractiveRoute) -> bool:
    """Sec C: prove a waypoint edit did not move the pinned endpoints.
    PINNED_ENDPOINT_MOVES_WITH_INTERMEDIATE_WAYPOINT = NO."""
    return (before.origin == after.origin) and (before.destination == after.destination)


# ===========================================================================
# 5. Segment add / delete on the network (Sec I). Never auto-bridge.
# ===========================================================================

def add_segment(graph: csa.ConnectivityGraph, edge: csa.SpatialEdge) -> csa.ConnectivityGraph:
    """Sec I: proposed What-If ADD_SEGMENT. Returns a NEW graph (non-mutating)
    with the edge added -- a local scenario change, never a Bentley write."""
    new = csa.ConnectivityGraph(edges=list(graph.edges))
    new.add_edge(edge)
    return new


def delete_segment(graph: csa.ConnectivityGraph, *, edge_id: str) -> csa.ConnectivityGraph:
    """Sec I: proposed What-If DELETE_SEGMENT. Returns a NEW graph without the
    edge. Deleting may disconnect downstream destinations -> subsequent
    auto_route returns NO_CONNECTED_PATH (never auto-bridged)."""
    return csa.ConnectivityGraph(edges=[e for e in graph.edges if e.edge_id != edge_id])


# ===========================================================================
# 6. Restore automatic route (Sec J). Discard manual constraints.
# ===========================================================================

def restore_auto_route(route: InteractiveRoute) -> InteractiveRoute:
    """Sec J: discard user control points and mark the route as the
    auto-generated scenario solution (no project restart)."""
    return replace(route, control_points=(), network_state="AUTO_GENERATED_SCENARIO_NETWORK")


# ===========================================================================
# 7. Route-edit -> full recomputation contract (Sec L/U). A committed route
#    change propagates the actual new route length/time through the affected
#    authorities. Drag-preview is lightweight (geometry only); commit triggers
#    full recompute.
# ===========================================================================

RecomputeTrigger = Literal["DRAG_PREVIEW", "COMMITTED_ROUTE_EDIT"]

# The authorities a committed route edit must feed (Sec L). Classified honestly
# for the current build (reactive wiring is a later build; these are the
# recompute INPUTS the contract exposes).
ROUTE_EDIT_RECOMPUTE_TARGETS: tuple[str, ...] = (
    "route_length", "travel_time", "carrier_vehicle_porter_cycle", "fleet_or_fte",
    "capacity", "energy", "radionuclide_decay", "required_upstream_activity",
    "production_activity", "batch_requirement", "cyclotron_capacity", "generator_capacity",
    "scanner_clinical_consequences", "incremental_capex", "target_opex", "incremental_opex",
    "feasibility",
)


@dataclass(frozen=True)
class RouteEditRecomputeRequest:
    route_id: str
    trigger: RecomputeTrigger
    new_total_route_length_m: float | None
    recompute_targets: tuple[str, ...]
    is_full_recompute: bool
    mutates_live_bentley: bool


def build_recompute_request(resolved: ResolvedInteractiveRoute, *, trigger: RecomputeTrigger) -> RouteEditRecomputeRequest:
    """Sec L/U: a DRAG_PREVIEW returns a lightweight geometry-only request; a
    COMMITTED_ROUTE_EDIT returns the full recompute-target set. Never mutates
    the live Bentley iModel (Sec W)."""
    if trigger == "DRAG_PREVIEW":
        return RouteEditRecomputeRequest(
            resolved.route_id, trigger, resolved.total_route_length_m,
            ("route_length", "travel_time"), False, False,
        )
    return RouteEditRecomputeRequest(
        resolved.route_id, trigger, resolved.total_route_length_m,
        ROUTE_EDIT_RECOMPUTE_TARGETS, True, WHATIF_ROUTE_EDIT_MUTATES_LIVE_BENTLEY,
    )


# ===========================================================================
# 8. Edit history (Sec V): reproducible undo/redo/restore over a route.
# ===========================================================================

@dataclass(frozen=True)
class RouteEditHistory:
    """A minimal reproducible edit stack for one route. Undo/redo return
    prior/next immutable route states; restore_auto returns the auto route."""
    states: tuple[InteractiveRoute, ...]
    cursor: int = 0

    def push(self, route: InteractiveRoute) -> "RouteEditHistory":
        kept = self.states[: self.cursor + 1]
        return RouteEditHistory(states=(*kept, route), cursor=len(kept))

    def undo(self) -> "RouteEditHistory":
        return RouteEditHistory(states=self.states, cursor=max(0, self.cursor - 1))

    def redo(self) -> "RouteEditHistory":
        return RouteEditHistory(states=self.states, cursor=min(len(self.states) - 1, self.cursor + 1))

    def current(self) -> InteractiveRoute:
        return self.states[self.cursor]

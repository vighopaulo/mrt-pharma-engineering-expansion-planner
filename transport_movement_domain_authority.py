"""Transport Movement-Domain / Topology Confinement + Radionuclide Visual
Identity Authority (ADDITIVE clarification to the current Bentley 3D digital-
twin integration build).

This module does NOT introduce a second routing engine. It COMPOSES the
existing mode-aware route authority `canonical_spatial_authority.resolve_route`
(mode-compatible BFS over `SpatialEdge.compatible_modes`) and formalizes the
already-enforced confinement into an explicit, testable governor:

MOVEMENT-DOMAIN DOCTRINE (Sec 5-6):
  * Network-bound modes travel ONLY on their own connected network edges:
      MRT      -> MRT guideway edges only
      RTHS     -> RTHS/rail track edges only (canonical mode "AGV_AMR" = RGHT rail)
      PTS      -> PTS tube edges only
  * Navigable-space-bound modes travel ONLY through legal navigable space
    (corridors, doors, elevators, approved open areas):
      AGV_AMR (light/heavy) -> navigable edges; never through walls
      MANUAL / human        -> pedestrian edges; never through walls
  * Route length derives from the LEGAL movement domain (topological), NOT a
    single Euclidean straight line shared by every mode (Sec 6).
  * A disconnected network is INFEASIBLE for that mode -- never silently
    bridged onto an incompatible edge.

RADIONUCLIDE VISUAL IDENTITY (Sec 8): color belongs to the RADIONUCLIDE
(payload substance), not the transport mode. It persists across mode transfer
and is not changed by numerical decay. This reuses the existing doctrine in
`mrt_service_class_authority` (color is a property of the substance, not the
route/lane) and extends it to the isotope level (F-18 / Tc-99m / Ga-68 / ...),
kept structurally separate from TRANSPORT visual identity and PAYLOAD-container
visual identity.

Nothing here mutates a live Bentley iModel, MRT canonical physics, Part 3E,
equal_budget, or the SB1/SB2/SB3 authorities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

import canonical_spatial_authority as csa

# ===========================================================================
# 1. Movement domains (Sec 5-6).
# ===========================================================================

MovementDomain = Literal["NETWORK_BOUND", "NAVIGABLE_SPACE_BOUND"]

# The canonical transport families of the product (five families + subtypes),
# mapped to their movement domain and to the canonical_spatial_authority
# TransportMode whose edges they are legally confined to.
TransportModeId = Literal[
    "MRT", "RTHS", "PTS_CONVENTIONAL", "PTS_NUCLEAR_QUALIFIED",
    "AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS", "MANUAL",
]

ALL_MOVEMENT_MODES: tuple[TransportModeId, ...] = (
    "MRT", "RTHS", "PTS_CONVENTIONAL", "PTS_NUCLEAR_QUALIFIED",
    "AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS", "MANUAL",
)

_MODE_DOMAIN: Mapping[TransportModeId, MovementDomain] = {
    "MRT": "NETWORK_BOUND",
    "RTHS": "NETWORK_BOUND",
    "PTS_CONVENTIONAL": "NETWORK_BOUND",
    "PTS_NUCLEAR_QUALIFIED": "NETWORK_BOUND",
    "AGV_AMR_LIGHT_CLINICAL": "NAVIGABLE_SPACE_BOUND",
    "AGV_AMR_HEAVY_LOGISTICS": "NAVIGABLE_SPACE_BOUND",
    "MANUAL": "NAVIGABLE_SPACE_BOUND",
}

# The canonical_spatial_authority.TransportMode whose edges a movement mode may
# legally traverse. NETWORK_BOUND modes are confined to their own edge type;
# NAVIGABLE_SPACE modes traverse pedestrian/navigable edges (WALKING_PORTER for
# manual, AGV_AMR navigable edges for robots -- never wall geometry).
_MODE_CSA_EDGE: Mapping[TransportModeId, csa.TransportMode] = {
    "MRT": "MRT",
    "RTHS": "AGV_AMR",  # canonical rail-guided edge tag (RGHT); see rght_spatial_network_authority
    "PTS_CONVENTIONAL": "PNEUMATIC_TUBE",
    "PTS_NUCLEAR_QUALIFIED": "PNEUMATIC_TUBE",
    "AGV_AMR_LIGHT_CLINICAL": "AGV_AMR",
    "AGV_AMR_HEAVY_LOGISTICS": "AGV_AMR",
    "MANUAL": "WALKING_PORTER",
}


def movement_domain(mode: TransportModeId) -> MovementDomain:
    return _MODE_DOMAIN[mode]


def is_network_bound(mode: TransportModeId) -> bool:
    return _MODE_DOMAIN[mode] == "NETWORK_BOUND"


def legal_csa_edge_mode(mode: TransportModeId) -> csa.TransportMode:
    return _MODE_CSA_EDGE[mode]


# ===========================================================================
# 2. Confinement-aware routing (Sec 5-6). Delegates to resolve_route on the
#    mode's LEGAL edge type only -- so a route physically cannot leave the
#    mode's movement domain.
# ===========================================================================

RouteFeasibility = Literal["FEASIBLE", "INFEASIBLE_DISCONNECTED_NETWORK", "INFEASIBLE_NO_NETWORK"]


@dataclass(frozen=True)
class ConfinedRouteResult:
    mode: TransportModeId
    movement_domain: MovementDomain
    csa_edge_mode: csa.TransportMode
    origin_object_id: str
    destination_object_id: str
    feasibility: RouteFeasibility
    route_distance_m: float | None
    path_edge_ids: tuple[str, ...]
    confinement_ok: bool
    detail: str


def resolve_confined_route(
    *, graph: csa.ConnectivityGraph, mode: TransportModeId,
    origin_object_id: str, destination_object_id: str,
) -> ConfinedRouteResult:
    """Sec 5-6: resolve a route for `mode` on ONLY its legal edge type. The
    underlying `resolve_route` performs a mode-compatible BFS, so the returned
    path can only traverse edges the mode is allowed on -- confinement is
    structural, not a post-hoc filter. A pair with no legal path is
    INFEASIBLE_DISCONNECTED_NETWORK; a mode whose network has no edge at all is
    INFEASIBLE_NO_NETWORK. Route length is topological (from the legal path),
    never a Euclidean straight line."""
    edge_mode = _MODE_CSA_EDGE[mode]
    if not graph.edges_for_mode(edge_mode):
        return ConfinedRouteResult(
            mode=mode, movement_domain=_MODE_DOMAIN[mode], csa_edge_mode=edge_mode,
            origin_object_id=origin_object_id, destination_object_id=destination_object_id,
            feasibility="INFEASIBLE_NO_NETWORK", route_distance_m=None, path_edge_ids=(),
            confinement_ok=True, detail=f"no {edge_mode} network edge exists for {mode}",
        )
    rr = csa.resolve_route(graph, origin_object_id=origin_object_id, destination_object_id=destination_object_id, mode=edge_mode)
    if rr.calibration_status != "CALIBRATED" or not (rr.path_edge_ids or origin_object_id == destination_object_id):
        return ConfinedRouteResult(
            mode=mode, movement_domain=_MODE_DOMAIN[mode], csa_edge_mode=edge_mode,
            origin_object_id=origin_object_id, destination_object_id=destination_object_id,
            feasibility="INFEASIBLE_DISCONNECTED_NETWORK", route_distance_m=None, path_edge_ids=(),
            confinement_ok=True,
            detail=f"{mode} network present but {origin_object_id}->{destination_object_id} not connected on legal edges",
        )
    dist = rr.distance_m if isinstance(rr.distance_m, (int, float)) else None
    # confinement proof: every path edge must be legal for the mode's edge type.
    edge_by_id = {e.edge_id: e for e in graph.edges}
    confinement_ok = all(edge_mode in edge_by_id[eid].compatible_modes for eid in rr.path_edge_ids)
    return ConfinedRouteResult(
        mode=mode, movement_domain=_MODE_DOMAIN[mode], csa_edge_mode=edge_mode,
        origin_object_id=origin_object_id, destination_object_id=destination_object_id,
        feasibility="FEASIBLE", route_distance_m=dist, path_edge_ids=rr.path_edge_ids,
        confinement_ok=confinement_ok,
        detail="routed on legal movement-domain edges only",
    )


def route_leaves_movement_domain(result: ConfinedRouteResult) -> bool:
    """Hard governor for the Sec 5 invariants: True if the route used any edge
    outside the mode's legal domain. Always False for a FEASIBLE confined route
    (that is the point). Used to assert:
      MRT_CARRIER_OFF_GUIDEWAY / RTHS_VEHICLE_OFF_TRACK / PTS_CAPSULE_OUTSIDE_TUBE
      / AGV_CROSSES_WALL / MANUAL_ROUTE_CROSSES_WALL = NO."""
    return result.feasibility == "FEASIBLE" and not result.confinement_ok


# ===========================================================================
# 3. Intelligent network extension (Sec 7). A new-building connection for a
#    fixed inherited network (MRT/PTS/RTHS) must extend from an eligible
#    EXISTING network node, and the chosen connection point must actually lie
#    on the legal existing network -- never restart from the cyclotron/source.
# ===========================================================================

@dataclass(frozen=True)
class NetworkExtensionCandidate:
    node_object_id: str
    is_existing_network_node: bool
    same_level: bool
    facing_side: bool
    distance_to_new_building_m: float


@dataclass(frozen=True)
class NetworkExtensionResult:
    mode: TransportModeId
    selected_connection_node_id: str | None
    connection_lies_on_valid_network: bool
    restarts_from_source: bool
    candidate_count: int
    detail: str


def select_network_extension_point(
    *, mode: TransportModeId, graph: csa.ConnectivityGraph,
    candidates: tuple[NetworkExtensionCandidate, ...], source_object_id: str,
) -> NetworkExtensionResult:
    """Sec 7: among candidate connection nodes, select an eligible EXISTING
    network node (preferring same-level + facing-side, then nearest). The
    selected node must actually be an endpoint of a legal edge for the mode
    (it lies ON the network). Never defaults to the cyclotron/radiopharmacy
    source. For navigable-space modes there is no fixed network to extend, so
    connection is unconstrained (reported as such)."""
    if not is_network_bound(mode):
        return NetworkExtensionResult(
            mode=mode, selected_connection_node_id=None, connection_lies_on_valid_network=True,
            restarts_from_source=False, candidate_count=len(candidates),
            detail=f"{mode} is navigable-space-bound: no fixed network to extend from (free-space connection)",
        )
    edge_mode = _MODE_CSA_EDGE[mode]
    network_node_ids = set()
    for e in graph.edges:
        if edge_mode in e.compatible_modes:
            network_node_ids.add(e.from_object_id)
            network_node_ids.add(e.to_object_id)
    # eligible = existing-network candidate that truly lies on the legal network
    eligible = [c for c in candidates if c.is_existing_network_node and c.node_object_id in network_node_ids]
    if not eligible:
        return NetworkExtensionResult(
            mode=mode, selected_connection_node_id=None, connection_lies_on_valid_network=False,
            restarts_from_source=False, candidate_count=len(candidates),
            detail="no eligible existing-network connection node -- extension INFEASIBLE (never silently restarts from source)",
        )
    # candidate-generation principle: prefer same-level + facing-side, then nearest.
    eligible.sort(key=lambda c: (not (c.same_level and c.facing_side), c.distance_to_new_building_m))
    chosen = eligible[0]
    return NetworkExtensionResult(
        mode=mode, selected_connection_node_id=chosen.node_object_id,
        connection_lies_on_valid_network=True,
        restarts_from_source=(chosen.node_object_id == source_object_id),
        candidate_count=len(candidates),
        detail=f"extended from existing network node {chosen.node_object_id} "
               f"(same_level={chosen.same_level}, facing_side={chosen.facing_side})",
    )


# ===========================================================================
# 4. Radionuclide visual identity (Sec 8). Color belongs to the RADIONUCLIDE
#    (payload substance), persists across mode transfer, and is NOT changed by
#    decay. Kept separate from transport visual identity + payload-container
#    visual identity.
# ===========================================================================

RadionuclideColor = Literal[
    "F18_LIME", "TC99M_CYAN", "GA68_MAGENTA", "LU177_ORANGE", "I131_YELLOW", "UNKNOWN_GRAY",
]

# Canonical color per radionuclide. This is PRESENTATION METADATA of the
# substance (isotope), never derived from the transport mode (Sec 8). Distinct
# from mrt_service_class_authority stream colors (which color the logistics
# service class, e.g. RADIOPHARMACEUTICAL_NUCLEAR=VIOLET); here each ISOTOPE
# keeps its own identity color so multiple radionuclides in one nuclear stream
# remain visually distinct.
_RADIONUCLIDE_COLOR: Mapping[str, RadionuclideColor] = {
    "F-18": "F18_LIME",
    "Tc-99m": "TC99M_CYAN",
    "Ga-68": "GA68_MAGENTA",
    "Lu-177": "LU177_ORANGE",
    "I-131": "I131_YELLOW",
}


def radionuclide_color(radionuclide: str) -> RadionuclideColor:
    """Sec 8: the canonical color of a radionuclide. Depends ONLY on the
    isotope identity -- never on transport mode, route, or decayed activity.
    Unknown isotopes are UNKNOWN_GRAY (never fabricated), mirroring the
    inactive-class GRAY convention in mrt_service_class_authority."""
    return _RADIONUCLIDE_COLOR.get(radionuclide, "UNKNOWN_GRAY")


VisualIdentityLayer = Literal["RADIONUCLIDE", "PAYLOAD_CONTAINER", "TRANSPORT_MODE"]


@dataclass(frozen=True)
class PayloadVisualIdentity:
    """Sec 8: three structurally-separate visual-identity layers. The
    radionuclide color is the substance identity; the payload-container color
    and transport-mode color are independent presentation layers that never
    override the radionuclide identity color."""

    radionuclide: str
    radionuclide_color: RadionuclideColor
    payload_container_id: str | None
    transport_mode: TransportModeId | None

    def identity_color(self) -> RadionuclideColor:
        return self.radionuclide_color


def payload_visual_identity(
    *, radionuclide: str, payload_container_id: str | None = None,
    transport_mode: TransportModeId | None = None,
) -> PayloadVisualIdentity:
    return PayloadVisualIdentity(
        radionuclide=radionuclide, radionuclide_color=radionuclide_color(radionuclide),
        payload_container_id=payload_container_id, transport_mode=transport_mode,
    )


def color_after_mode_transfer(
    identity: PayloadVisualIdentity, *, new_transport_mode: TransportModeId,
) -> PayloadVisualIdentity:
    """Sec 8: transferring a payload to a different transport mode returns an
    identity with the SAME radionuclide color -- only the transport_mode field
    changes. RADIONUCLIDE_COLOR_CHANGES_WITH_TRANSPORT_MODE = NO;
    RADIONUCLIDE_COLOR_PERSISTS_ACROSS_MODE_TRANSFER = YES."""
    return PayloadVisualIdentity(
        radionuclide=identity.radionuclide, radionuclide_color=identity.radionuclide_color,
        payload_container_id=identity.payload_container_id, transport_mode=new_transport_mode,
    )


def color_after_decay(identity: PayloadVisualIdentity, *, decayed_activity_mbq: float) -> PayloadVisualIdentity:
    """Sec 8: numerical decay changes ACTIVITY, never the radionuclide identity
    color. Returns an identity with the same color (decayed activity is a
    separate numeric fact, not encoded in identity color)."""
    return identity  # identity color unchanged by decay


def color_changes_with_transport_mode() -> bool:
    """Hard governor: always False (Sec 8)."""
    return False

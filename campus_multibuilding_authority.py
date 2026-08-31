"""Multi-Building Campus Graph + Per-Mode Connectivity Components + Single/Group
Movement + Dependency-Based Network Reconciliation (ADDITIVE clarification to
the current Bentley 3D spatial-network-response build).

This module introduces NO new spatial transform engine and NO new routing
engine. It COMPOSES:
  * canonical_spatial_authority : Transform / SpatialObjectRegistry /
    replace_transform / resolve_global_position / compute_global_distance /
    ConnectivityGraph / SpatialEdge / resolve_route  (6-DOF poses + mode-aware
    routing already exist).
  * spatial_pose_orchestration_authority : anchor/movable + 6-DOF separation.
  * transport_movement_domain_authority : per-mode legal edge + confined route.

CORE DOCTRINES (this clarification):
  * Every building has its OWN absolute pose in the common campus coordinate
    system. Building 1 is NOT the global parent of all buildings
    (BUILDING_1_IS_GLOBAL_PARENT_OF_ALL_BUILDINGS = NO).
  * Pairwise relationships R_ij = F(B_i, B_j) are DERIVED from current poses,
    never primary ownership.
  * Each transport mode has its OWN connectivity graph + connected components
    (ALL_TRANSPORT_MODES_SHARE_IDENTICAL_CONNECTIVITY_GRAPH = NO).
  * A new/moved building connects to the EXISTING network component, not
    automatically to Building 1 (NEW_BUILDING_ALWAYS_CONNECTS_TO_BUILDING_1 = NO).
  * Moving one building never physically moves another unless explicitly
    grouped (MOVING_BUILDING_C_AUTOMATICALLY_MOVES_A_OR_B = NO); engineering
    REACTION != physical movement.
  * Localized recomputation: only the dependency-affected set reconciles
    (UNRELATED_NETWORK_SEGMENTS_REBUILT_AFTER_LOCAL_MOVE = NO) -- but full
    MISSION physics still uses the COMPLETE actual route
    (INHERITED_NETWORK_ZERO_TRAVEL_TIME = NO;
     DECAY_CALCULATED_ONLY_ON_INCREMENTAL_SEGMENT = NO).
  * Transport connectivity does NOT imply a movement group
    (TRANSPORT_CONNECTIVITY_IMPLIES_MOVEMENT_GROUP = NO).

Nothing here mutates a live Bentley iModel, MRT canonical physics, Part 3E,
equal_budget, or the SB1/SB2/SB3 authorities.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from typing import Literal, Mapping, Sequence

import canonical_spatial_authority as csa
import transport_movement_domain_authority as md

# ===========================================================================
# 1. Campus graph: independent building poses (Sec A-D).
# ===========================================================================

@dataclass(frozen=True)
class BuildingNode:
    """An independently identifiable building with its OWN absolute campus pose.
    Never implicitly parented to another building."""

    building_id: str
    world_pose: csa.Transform
    program: str = "CLINICAL"
    project_classification: str = "INHERITED_EXISTING"
    provenance: str = "PROJECT_SUPPLIED"

    @property
    def position_xyz(self) -> tuple[float, float, float]:
        return (self.world_pose.position_x, self.world_pose.position_y, self.world_pose.position_z)

    @property
    def yaw_deg(self) -> float:
        return self.world_pose.rotation_z


@dataclass(frozen=True)
class CampusGraph:
    """Sec D: nodes = buildings (+ relevant facility objects); the common
    campus coordinate system is the ONE reference. Building 1 is never the
    global parent (each node carries its own world pose)."""

    campus_id: str
    buildings: Mapping[str, BuildingNode]

    def building_ids(self) -> tuple[str, ...]:
        return tuple(self.buildings.keys())

    def with_building_pose(self, building_id: str, new_pose: csa.Transform) -> "CampusGraph":
        """Sec J/U: move ONE building. No other building's pose changes."""
        if building_id not in self.buildings:
            raise ValueError(f"unknown building {building_id}")
        new_map = dict(self.buildings)
        new_map[building_id] = replace(new_map[building_id], world_pose=new_pose)
        return CampusGraph(campus_id=self.campus_id, buildings=new_map)


BUILDING_1_IS_GLOBAL_PARENT_OF_ALL_BUILDINGS = False


# ===========================================================================
# 2. Pairwise derived relationships (Sec C).
# ===========================================================================

@dataclass(frozen=True)
class PairwiseRelationship:
    building_a: str
    building_b: str
    relative_vector_xyz: tuple[float, float, float]
    geometric_separation_m: float
    relative_yaw_deg: float
    elevation_difference_m: float


def derive_pairwise_relationship(campus: CampusGraph, a: str, b: str) -> PairwiseRelationship:
    """Sec C: R_ij = F(B_i, B_j) derived from CURRENT poses -- never stored
    ownership. Symmetric geometry; recomputed on demand."""
    pa = campus.buildings[a].position_xyz
    pb = campus.buildings[b].position_xyz
    rel = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
    sep = (rel[0] ** 2 + rel[1] ** 2 + rel[2] ** 2) ** 0.5
    return PairwiseRelationship(
        building_a=a, building_b=b, relative_vector_xyz=rel, geometric_separation_m=sep,
        relative_yaw_deg=campus.buildings[b].yaw_deg - campus.buildings[a].yaw_deg,
        elevation_difference_m=rel[2],
    )


# ===========================================================================
# 3. Per-mode connectivity components (Sec E-F). One connectivity graph per
#    mode; connected-component analysis over that mode's legal edges only.
# ===========================================================================

@dataclass(frozen=True)
class ModeConnectivityComponents:
    mode: md.TransportModeId
    csa_edge_mode: csa.TransportMode
    components: tuple[frozenset[str], ...]  # each a set of connected node ids

    def component_of(self, node_id: str) -> frozenset[str] | None:
        for c in self.components:
            if node_id in c:
                return c
        return None

    def are_connected(self, a: str, b: str) -> bool:
        c = self.component_of(a)
        return c is not None and b in c


def connected_components_for_mode(graph: csa.ConnectivityGraph, mode: md.TransportModeId) -> ModeConnectivityComponents:
    """Sec F: connected components over ONLY the mode's legal edge subgraph.
    Different modes generally yield different components (Sec E)."""
    edge_mode = md.legal_csa_edge_mode(mode)
    adj: dict[str, set[str]] = {}
    for e in graph.edges:
        if edge_mode in e.compatible_modes:
            adj.setdefault(e.from_object_id, set()).add(e.to_object_id)
            adj.setdefault(e.to_object_id, set()).add(e.from_object_id)
    seen: set[str] = set()
    comps: list[frozenset[str]] = []
    for node in adj:
        if node in seen:
            continue
        # BFS
        comp: set[str] = set()
        q = deque([node])
        seen.add(node)
        while q:
            n = q.popleft()
            comp.add(n)
            for m in adj.get(n, ()):  # neighbors
                if m not in seen:
                    seen.add(m)
                    q.append(m)
        comps.append(frozenset(comp))
    return ModeConnectivityComponents(mode=mode, csa_edge_mode=edge_mode, components=tuple(comps))


ALL_TRANSPORT_MODES_SHARE_IDENTICAL_CONNECTIVITY_GRAPH = False


# ===========================================================================
# 4. New/moved-building connection to EXISTING component (Sec G-I, R, AA-AD).
# ===========================================================================

@dataclass(frozen=True)
class ConnectionCandidate:
    node_id: str            # an existing legal-network node
    building_id: str        # which building the node belongs to
    distance_to_new_building_m: float
    same_level: bool
    facing_side: bool


@dataclass(frozen=True)
class ComponentConnectionResult:
    mode: md.TransportModeId
    new_building_id: str
    selected_node_id: str | None
    selected_via_building_id: str | None
    connected_to_existing_component: bool
    connects_to_building_1: bool
    candidate_count: int
    detail: str


def select_component_connection(
    *, mode: md.TransportModeId, graph: csa.ConnectivityGraph,
    new_building_id: str, candidates: Sequence[ConnectionCandidate],
    building_1_id: str | None = None,
) -> ComponentConnectionResult:
    """Sec G-H/AA-AB: evaluate eligible connection nodes across the EXISTING
    network component (nodes that actually lie on the mode's legal network).
    Prefer facing-side + same-level, then nearest -- NEVER default to Building 1,
    NEVER assume the geometrically nearest building. For navigable-space modes
    there is no fixed component (free navigable connection)."""
    if not md.is_network_bound(mode):
        return ComponentConnectionResult(
            mode=mode, new_building_id=new_building_id, selected_node_id=None,
            selected_via_building_id=None, connected_to_existing_component=True,
            connects_to_building_1=False, candidate_count=len(candidates),
            detail=f"{mode} is navigable-space-bound: connects through legal navigable space, not a fixed component",
        )
    edge_mode = md.legal_csa_edge_mode(mode)
    network_nodes = set()
    for e in graph.edges:
        if edge_mode in e.compatible_modes:
            network_nodes.add(e.from_object_id)
            network_nodes.add(e.to_object_id)
    eligible = [c for c in candidates if c.node_id in network_nodes]
    if not eligible:
        return ComponentConnectionResult(
            mode=mode, new_building_id=new_building_id, selected_node_id=None,
            selected_via_building_id=None, connected_to_existing_component=False,
            connects_to_building_1=False, candidate_count=len(candidates),
            detail="no eligible existing-network node -- connection INFEASIBLE (never silently forced to Building 1)",
        )
    eligible.sort(key=lambda c: (not (c.same_level and c.facing_side), c.distance_to_new_building_m))
    chosen = eligible[0]
    return ComponentConnectionResult(
        mode=mode, new_building_id=new_building_id, selected_node_id=chosen.node_id,
        selected_via_building_id=chosen.building_id,
        connected_to_existing_component=True,
        connects_to_building_1=(building_1_id is not None and chosen.building_id == building_1_id),
        candidate_count=len(candidates),
        detail=f"connected to existing {mode} component via building {chosen.building_id} node {chosen.node_id}",
    )


NEW_BUILDING_ALWAYS_CONNECTS_TO_BUILDING_1 = False
NEAREST_BUILDING_ALWAYS_SELECTED_AS_CONNECTION_PARENT = False


# ===========================================================================
# 5. Movement groups (Sec V-Z, X). Explicit membership; connectivity != group.
# ===========================================================================

@dataclass(frozen=True)
class MovementGroup:
    group_id: str
    member_building_ids: frozenset[str]
    group_reference_pose: csa.Transform


TRANSPORT_CONNECTIVITY_IMPLIES_MOVEMENT_GROUP = False


def move_single_building(campus: CampusGraph, *, building_id: str, new_pose: csa.Transform) -> CampusGraph:
    """Sec U: MOVE_SINGLE_BUILDING -- only that building moves; others fixed."""
    return campus.with_building_pose(building_id, new_pose)


def move_building_group(
    campus: CampusGraph, *, group: MovementGroup, new_group_reference_pose: csa.Transform,
) -> CampusGraph:
    """Sec V-Y: MOVE_BUILDING_GROUP -- members translate/yaw together, preserving
    member-relative geometry; non-members stay fixed. Member new pose = member's
    offset from the old group reference, re-applied to the new group reference
    (rigid translation of the group; yaw handled by delta about group ref)."""
    old_ref = group.group_reference_pose
    dx = new_group_reference_pose.position_x - old_ref.position_x
    dy = new_group_reference_pose.position_y - old_ref.position_y
    dz = new_group_reference_pose.position_z - old_ref.position_z
    dyaw = new_group_reference_pose.rotation_z - old_ref.rotation_z
    new_map = dict(campus.buildings)
    for bid in group.member_building_ids:
        if bid not in new_map:
            raise ValueError(f"group member {bid} not in campus")
        b = new_map[bid]
        t = b.world_pose
        new_map[bid] = replace(b, world_pose=replace(
            t, position_x=t.position_x + dx, position_y=t.position_y + dy,
            position_z=t.position_z + dz, rotation_z=t.rotation_z + dyaw,
        ))
    return CampusGraph(campus_id=campus.campus_id, buildings=new_map)


# ===========================================================================
# 6. Dependency-based reconciliation (Sec L-M, AN). Changed / affected /
#    unchanged sets from the campus + per-mode connectivity.
# ===========================================================================

@dataclass(frozen=True)
class ReconciliationScope:
    changed_building_ids: frozenset[str]
    affected_building_ids: frozenset[str]
    unchanged_building_ids: frozenset[str]
    affected_connections: tuple[tuple[str, str], ...]
    unchanged_connections: tuple[tuple[str, str], ...]


def compute_reconciliation_scope(
    *, campus: CampusGraph, changed_building_ids: frozenset[str],
    mode_components: ModeConnectivityComponents,
) -> ReconciliationScope:
    """Sec M/AN: a changed building affects only the connections that touch it
    (and its network component neighbors); connections between two unchanged
    buildings in an unaffected part of the network are UNCHANGED. Unrelated
    segments are NOT rebuilt."""
    # affected = changed buildings + their direct network component co-members
    affected: set[str] = set(changed_building_ids)
    for bid in changed_building_ids:
        comp = mode_components.component_of(bid)
        if comp:
            affected |= set(comp)
    all_ids = set(campus.building_ids())
    unchanged = all_ids - affected

    affected_conns: list[tuple[str, str]] = []
    unchanged_conns: list[tuple[str, str]] = []
    for comp in mode_components.components:
        members = sorted(comp)
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                pair = (members[i], members[j])
                if members[i] in changed_building_ids or members[j] in changed_building_ids:
                    affected_conns.append(pair)
                else:
                    unchanged_conns.append(pair)
    return ReconciliationScope(
        changed_building_ids=frozenset(changed_building_ids),
        affected_building_ids=frozenset(affected),
        unchanged_building_ids=frozenset(unchanged),
        affected_connections=tuple(affected_conns),
        unchanged_connections=tuple(unchanged_conns),
    )


ENGINEERING_REACTION_IMPLIES_PHYSICAL_MOVEMENT = False
MOVING_BUILDING_C_AUTOMATICALLY_MOVES_A_OR_B = False
UNRELATED_NETWORK_SEGMENTS_REBUILT_AFTER_LOCAL_MOVE = False


# ===========================================================================
# 7. Full-path mission routing (Sec N-Q, P, AK). Mission physics uses the
#    COMPLETE actual route across all traversed buildings, even when only one
#    segment is project-incremental scope.
# ===========================================================================

@dataclass(frozen=True)
class RouteSegment:
    from_node_id: str
    to_node_id: str
    length_m: float
    scope: Literal["INHERITED", "INCREMENTAL"]


@dataclass(frozen=True)
class FullMissionRoute:
    mode: md.TransportModeId
    origin_node_id: str
    destination_node_id: str
    segments: tuple[RouteSegment, ...]

    def full_route_length_m(self) -> float:
        """Sec P/Q: TOTAL physical route across ALL segments (inherited +
        incremental). Used for decay/cycle/capacity."""
        return sum(s.length_m for s in self.segments)

    def incremental_capex_length_m(self) -> float:
        """Sec O/AK: only the INCREMENTAL segments count toward project new
        CapEx (inherited segments have $0 new CapEx but full travel time)."""
        return sum(s.length_m for s in self.segments if s.scope == "INCREMENTAL")

    def inherited_length_m(self) -> float:
        return sum(s.length_m for s in self.segments if s.scope == "INHERITED")


def full_path_travel_time_seconds(route: FullMissionRoute, *, speed_m_per_s: float) -> float:
    """Sec P: decay/cycle use the FULL route length / speed -- never only the
    incremental segment. INHERITED_NETWORK_ZERO_TRAVEL_TIME = NO."""
    if speed_m_per_s <= 0:
        raise ValueError("speed must be positive")
    return route.full_route_length_m() / speed_m_per_s


INHERITED_NETWORK_ZERO_TRAVEL_TIME = False
DECAY_CALCULATED_ONLY_ON_INCREMENTAL_SEGMENT = False
GEOMETRIC_SEPARATION_EQUALS_ALL_TRANSPORT_ROUTE_LENGTHS = False


# ===========================================================================
# 8. Payload-specific campus routing (Sec AE-AG). Missions may originate in
#    different buildings; Building A is NOT the universal logistics origin.
# ===========================================================================

@dataclass(frozen=True)
class CampusMission:
    mission_id: str
    payload_stream: str
    radionuclide: str | None
    origin_building_id: str
    destination_building_id: str


BUILDING_A_IS_UNIVERSAL_LOGISTICS_ORIGIN = False


def mission_origins_are_building_specific(missions: Sequence[CampusMission]) -> bool:
    """Sec AE: proves missions can originate in different buildings (radiopharm
    from A, specimen from E, linen from D, sterile from B)."""
    return len({m.origin_building_id for m in missions}) > 1

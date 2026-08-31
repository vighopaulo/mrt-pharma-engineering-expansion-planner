"""Multi-building campus + per-mode connectivity components + single/group
movement + dependency reconciliation + full-path mission physics tests
(ADDITIVE to the current Bentley 3D spatial-network-response build).

Covers Sec A-AP controls: N-building independence, no forced Building-1 parent,
derived pairwise relationships, per-mode connectivity components, new-building
connection to existing component, connection-can-change-after-move, single vs
group move, connectivity != group, localized reconciliation, full-path decay
(inherited zero-CapEx but full travel time), payload-specific origins, and the
named 3/4/5-building + group-move controls.
"""
from __future__ import annotations

import pytest

import canonical_spatial_authority as csa
import campus_multibuilding_authority as cmp
import spatial_pose_orchestration_authority as pose

T = csa.Transform


# --- fixtures --------------------------------------------------------------

def _campus_5():
    b = {
        "A": cmp.BuildingNode("A", T(position_x=0, position_y=0)),
        "B": cmp.BuildingNode("B", T(position_x=100, position_y=0)),
        "C": cmp.BuildingNode("C", T(position_x=200, position_y=0)),
        "D": cmp.BuildingNode("D", T(position_x=100, position_y=100)),
        "E": cmp.BuildingNode("E", T(position_x=100, position_y=200)),
    }
    return cmp.CampusGraph(campus_id="C5", buildings=b)


def _mrt_chain_graph():
    g = csa.ConnectivityGraph()
    for eid, a, b in [("MRT-AB", "A", "B"), ("MRT-BD", "B", "D"), ("MRT-DE", "D", "E")]:
        g.add_edge(csa.SpatialEdge(edge_id=eid, from_object_id=a, to_object_id=b, length_m=100.0, compatible_modes=frozenset({"MRT"})))
    g.add_edge(csa.SpatialEdge(edge_id="PTS-AB", from_object_id="A", to_object_id="B", length_m=100.0, compatible_modes=frozenset({"PNEUMATIC_TUBE"})))
    g.add_edge(csa.SpatialEdge(edge_id="RTHS-BC", from_object_id="B", to_object_id="C", length_m=100.0, compatible_modes=frozenset({"AGV_AMR"})))
    return g


# --- Sec A-B: independent buildings, no forced parent ---------------------

def test_no_building_1_global_parent():
    assert cmp.BUILDING_1_IS_GLOBAL_PARENT_OF_ALL_BUILDINGS is False


def test_each_building_has_own_absolute_pose():
    c = _campus_5()
    assert c.buildings["A"].position_xyz == (0, 0, 0.0)
    assert c.buildings["E"].position_xyz == (100, 200, 0.0)


def test_n_building_campus_supports_1_through_5():
    for n in range(1, 6):
        ids = "ABCDE"[:n]
        b = {x: cmp.BuildingNode(x, T(position_x=100 * i)) for i, x in enumerate(ids)}
        c = cmp.CampusGraph(campus_id="X", buildings=b)
        assert len(c.building_ids()) == n


# --- Sec C: derived pairwise relationships --------------------------------

def test_pairwise_relationship_derived_from_current_poses():
    c = _campus_5()
    r = cmp.derive_pairwise_relationship(c, "A", "C")
    assert r.geometric_separation_m == 200.0
    assert r.relative_vector_xyz == (200.0, 0.0, 0.0)


def test_pairwise_relationship_recomputes_after_move():
    c = _campus_5()
    r0 = cmp.derive_pairwise_relationship(c, "A", "E")
    moved = cmp.move_single_building(c, building_id="E", new_pose=T(position_x=0, position_y=400))
    r1 = cmp.derive_pairwise_relationship(moved, "A", "E")
    assert r1.geometric_separation_m != r0.geometric_separation_m


# --- Sec E-F: per-mode connectivity components ----------------------------

def test_modes_do_not_share_one_connectivity_graph():
    assert cmp.ALL_TRANSPORT_MODES_SHARE_IDENTICAL_CONNECTIVITY_GRAPH is False


def test_per_mode_components_differ():
    g = _mrt_chain_graph()
    mrt = cmp.connected_components_for_mode(g, "MRT")
    pts = cmp.connected_components_for_mode(g, "PTS_CONVENTIONAL")
    rths = cmp.connected_components_for_mode(g, "RTHS")
    assert mrt.are_connected("A", "E")       # A-B-D-E
    assert not pts.are_connected("A", "D")   # PTS only A-B
    assert rths.are_connected("B", "C")      # RTHS only B-C
    assert not rths.are_connected("A", "C")


def test_mrt_component_membership():
    g = _mrt_chain_graph()
    mrt = cmp.connected_components_for_mode(g, "MRT")
    comp = mrt.component_of("E")
    assert comp == frozenset({"A", "B", "D", "E"})


# --- Sec G-H: new building connects to existing component, not Building 1 --

def test_new_building_does_not_always_connect_to_building_1():
    assert cmp.NEW_BUILDING_ALWAYS_CONNECTS_TO_BUILDING_1 is False


def test_three_building_control_c_connects_via_b():
    # A-B connected by MRT; C introduced near B -> connects via B, not A
    g = csa.ConnectivityGraph()
    g.add_edge(csa.SpatialEdge(edge_id="MRT-AB", from_object_id="A", to_object_id="B", length_m=100.0, compatible_modes=frozenset({"MRT"})))
    cands = (
        cmp.ConnectionCandidate("B", "B", distance_to_new_building_m=30.0, same_level=True, facing_side=True),
        cmp.ConnectionCandidate("A", "A", distance_to_new_building_m=5.0, same_level=False, facing_side=False),
    )
    r = cmp.select_component_connection(mode="MRT", graph=g, new_building_id="C", candidates=cands, building_1_id="A")
    assert r.selected_via_building_id == "B"
    assert not r.connects_to_building_1
    assert r.connected_to_existing_component


def test_connection_infeasible_when_no_existing_network_node():
    g = csa.ConnectivityGraph()
    g.add_edge(csa.SpatialEdge(edge_id="MRT-AB", from_object_id="A", to_object_id="B", length_m=100.0, compatible_modes=frozenset({"MRT"})))
    cands = (cmp.ConnectionCandidate("OFFNET", "X", distance_to_new_building_m=1.0, same_level=True, facing_side=True),)
    r = cmp.select_component_connection(mode="MRT", graph=g, new_building_id="C", candidates=cands, building_1_id="A")
    assert not r.connected_to_existing_component
    assert r.selected_node_id is None


# --- Sec I / AH: connection can change after a move -----------------------

def test_three_building_dynamic_reconnection_control():
    g = csa.ConnectivityGraph()
    for eid, a, b in [("MRT-AB", "A", "B")]:
        g.add_edge(csa.SpatialEdge(edge_id=eid, from_object_id=a, to_object_id=b, length_m=100.0, compatible_modes=frozenset({"MRT"})))
    # C near B initially -> prefers B
    near_b = (
        cmp.ConnectionCandidate("B", "B", distance_to_new_building_m=20.0, same_level=True, facing_side=True),
        cmp.ConnectionCandidate("A", "A", distance_to_new_building_m=250.0, same_level=True, facing_side=False),
    )
    r_before = cmp.select_component_connection(mode="MRT", graph=g, new_building_id="C", candidates=near_b, building_1_id="A")
    assert r_before.selected_via_building_id == "B"
    # C moved near A -> prefers A
    near_a = (
        cmp.ConnectionCandidate("B", "B", distance_to_new_building_m=250.0, same_level=True, facing_side=False),
        cmp.ConnectionCandidate("A", "A", distance_to_new_building_m=20.0, same_level=True, facing_side=True),
    )
    r_after = cmp.select_component_connection(mode="MRT", graph=g, new_building_id="C", candidates=near_a, building_1_id="A")
    assert r_after.selected_via_building_id == "A"
    assert r_before.selected_via_building_id != r_after.selected_via_building_id


# --- Sec J-K: moving one building does not move others; reaction != move ---

def test_moving_c_does_not_move_a_or_b():
    assert cmp.MOVING_BUILDING_C_AUTOMATICALLY_MOVES_A_OR_B is False
    c = _campus_5()
    moved = cmp.move_single_building(c, building_id="C", new_pose=T(position_x=999))
    assert moved.buildings["A"].position_xyz == c.buildings["A"].position_xyz
    assert moved.buildings["B"].position_xyz == c.buildings["B"].position_xyz


def test_engineering_reaction_is_not_physical_movement():
    assert cmp.ENGINEERING_REACTION_IMPLIES_PHYSICAL_MOVEMENT is False


# --- Sec M / AJ: localized reconciliation ---------------------------------

def test_five_building_localized_move_unrelated_unchanged():
    c = _campus_5()
    g = _mrt_chain_graph()
    mrt = cmp.connected_components_for_mode(g, "MRT")
    scope = cmp.compute_reconciliation_scope(campus=c, changed_building_ids=frozenset({"E"}), mode_components=mrt)
    # A-B is not incident to E -> unchanged
    assert ("A", "B") in scope.unchanged_connections
    # E-incident connections are affected
    assert ("D", "E") in scope.affected_connections
    # C (different mode component) fully unchanged
    assert "C" in scope.unchanged_building_ids


def test_unrelated_segments_not_rebuilt_flag():
    assert cmp.UNRELATED_NETWORK_SEGMENTS_REBUILT_AFTER_LOCAL_MOVE is False


# --- Sec O/P/AK: full-path mission physics --------------------------------

def _full_route():
    return cmp.FullMissionRoute(mode="MRT", origin_node_id="A", destination_node_id="E", segments=(
        cmp.RouteSegment("A", "B", 100.0, "INHERITED"),
        cmp.RouteSegment("B", "D", 100.0, "INHERITED"),
        cmp.RouteSegment("D", "E", 145.0, "INCREMENTAL"),
    ))


def test_full_path_length_includes_inherited_segments():
    r = _full_route()
    assert r.full_route_length_m() == 345.0
    assert r.inherited_length_m() == 200.0


def test_incremental_capex_length_only_new_segment():
    assert _full_route().incremental_capex_length_m() == 145.0


def test_full_path_decay_time_uses_complete_route_not_incremental():
    r = _full_route()
    t = cmp.full_path_travel_time_seconds(r, speed_m_per_s=10.0)
    assert t == pytest.approx(34.5)  # 345/10, not 14.5 (145/10)
    assert cmp.DECAY_CALCULATED_ONLY_ON_INCREMENTAL_SEGMENT is False


def test_inherited_network_zero_travel_time_is_no():
    assert cmp.INHERITED_NETWORK_ZERO_TRAVEL_TIME is False
    r = _full_route()
    # inherited segments contribute real travel time
    assert r.inherited_length_m() > 0


def test_geometric_separation_not_equal_to_all_route_lengths():
    assert cmp.GEOMETRIC_SEPARATION_EQUALS_ALL_TRANSPORT_ROUTE_LENGTHS is False


# --- Sec V-Y / AL: group move ---------------------------------------------

def test_group_move_preserves_internal_geometry():
    c = _campus_5()
    grp = cmp.MovementGroup(group_id="G", member_building_ids=frozenset({"B", "C"}), group_reference_pose=T(position_x=100, position_y=0))
    moved = cmp.move_building_group(c, group=grp, new_group_reference_pose=T(position_x=100, position_y=500))
    # B->C internal vector preserved
    bc_before = (c.buildings["C"].position_xyz[0] - c.buildings["B"].position_xyz[0],
                 c.buildings["C"].position_xyz[1] - c.buildings["B"].position_xyz[1])
    bc_after = (moved.buildings["C"].position_xyz[0] - moved.buildings["B"].position_xyz[0],
                moved.buildings["C"].position_xyz[1] - moved.buildings["B"].position_xyz[1])
    assert bc_before == bc_after


def test_group_move_leaves_nonmembers_fixed():
    c = _campus_5()
    grp = cmp.MovementGroup(group_id="G", member_building_ids=frozenset({"B", "C"}), group_reference_pose=T(position_x=100, position_y=0))
    moved = cmp.move_building_group(c, group=grp, new_group_reference_pose=T(position_x=100, position_y=500))
    assert moved.buildings["A"].position_xyz == c.buildings["A"].position_xyz
    assert moved.buildings["D"].position_xyz == c.buildings["D"].position_xyz


def test_connectivity_does_not_imply_group():
    assert cmp.TRANSPORT_CONNECTIVITY_IMPLIES_MOVEMENT_GROUP is False


def test_group_move_translation():
    c = _campus_5()
    grp = cmp.MovementGroup(group_id="G", member_building_ids=frozenset({"B", "C"}), group_reference_pose=T(position_x=100, position_y=0))
    moved = cmp.move_building_group(c, group=grp, new_group_reference_pose=T(position_x=100, position_y=500))
    # both members translated by +500 in y
    assert moved.buildings["B"].position_xyz[1] == c.buildings["B"].position_xyz[1] + 500
    assert moved.buildings["C"].position_xyz[1] == c.buildings["C"].position_xyz[1] + 500


# --- Sec AE-AG: payload-specific origins ----------------------------------

def test_building_a_not_universal_origin():
    assert cmp.BUILDING_A_IS_UNIVERSAL_LOGISTICS_ORIGIN is False


def test_missions_originate_in_different_buildings():
    missions = [
        cmp.CampusMission("M1", "RADIOPHARMACEUTICAL_NUCLEAR", "F-18", "A", "E"),
        cmp.CampusMission("M2", "SPECIMEN_BLOOD", None, "E", "C"),
        cmp.CampusMission("M3", "CLEAN_LINEN", None, "D", "E"),
        cmp.CampusMission("M4", "STERILE_CLEAN_SUPPLY", None, "B", "E"),
    ]
    assert cmp.mission_origins_are_building_specific(missions)


# --- Sec AI: four-building control -----------------------------------------

def test_four_building_uses_existing_component_not_hardcoded_a():
    # A-B, C-D two separate MRT components; connect new via existing nodes
    g = csa.ConnectivityGraph()
    g.add_edge(csa.SpatialEdge(edge_id="MRT-AB", from_object_id="A", to_object_id="B", length_m=100.0, compatible_modes=frozenset({"MRT"})))
    g.add_edge(csa.SpatialEdge(edge_id="MRT-CD", from_object_id="C", to_object_id="D", length_m=100.0, compatible_modes=frozenset({"MRT"})))
    comps = cmp.connected_components_for_mode(g, "MRT")
    assert len(comps.components) == 2  # {A,B} and {C,D}
    # connect a new building near D -> via D (its component), not A
    cands = (
        cmp.ConnectionCandidate("D", "D", distance_to_new_building_m=15.0, same_level=True, facing_side=True),
        cmp.ConnectionCandidate("A", "A", distance_to_new_building_m=400.0, same_level=False, facing_side=False),
    )
    r = cmp.select_component_connection(mode="MRT", graph=g, new_building_id="NEW", candidates=cands, building_1_id="A")
    assert r.selected_via_building_id == "D"


# --- 6-DOF pose orchestration integration (prior module) ------------------

def test_6dof_supported_flag():
    assert pose.SPATIAL_TRANSFORM_SUPPORTS_6DOF is True


def _two_building_registry():
    reg = csa.build_facility_hierarchy(facility_id="F")
    csa.add_building(reg, facility_id="F", building_id="A", transform=T())
    csa.add_building(reg, facility_id="F", building_id="B", transform=T(position_x=100))
    return reg


def test_non_axis_aligned_translation_500m():
    reg = _two_building_registry()
    reg = reg.replace_transform("B", T(position_x=300, position_y=400, position_z=0))
    sep = csa.compute_global_distance(reg, "A", "B")
    assert sep == pytest.approx(500.0)  # (300,400,0) -> 500, proves not X-only


def test_xyz_separation_with_z():
    reg = _two_building_registry()
    reg = reg.replace_transform("B", T(position_x=300, position_y=400, position_z=120))
    s = pose.compute_anchor_movable_separation(reg, anchor_id="A", movable_id="B")
    assert s.delta_x == 300 and s.delta_y == 400 and s.delta_z == 120
    assert s.geometric_separation_m == pytest.approx((300 ** 2 + 400 ** 2 + 120 ** 2) ** 0.5)


def test_six_dof_round_trip_no_drift():
    reg = _two_building_registry()
    res = pose.evaluate_six_dof_round_trip(
        reg, anchor_id="A", movable_id="B",
        intermediate_transform=T(position_x=300, position_y=400, position_z=120, rotation_z=57.0),
        restore_transform=T(position_x=100),
    )
    assert res.anchor_unchanged and res.movable_pose_restored
    assert not res.drift_present

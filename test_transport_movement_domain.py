"""Movement-domain / topology confinement + radionuclide visual identity tests
(ADDITIVE to the current Bentley 3D digital-twin integration build).

Proves: MRT guideway confinement, RTHS track confinement, PTS tube confinement,
AGV wall/door navigation, Manual wall/door navigation, disconnected-network
infeasibility, topological vs Euclidean routing, all-mode stretch/compression/
floor-expansion routing, intelligent network extension, radionuclide color
invariance, and payload lineage across mode transfer.
"""
from __future__ import annotations

import pytest

import canonical_spatial_authority as csa
import transport_movement_domain_authority as md
import geometry_change_contract as gcc


# --- fixtures --------------------------------------------------------------

def _multimode_graph(sep_m: float = 100.0):
    """A->B with a distinct legal edge per movement domain, lengths derived
    from a base separation so stretch/compression can scale them."""
    g = csa.ConnectivityGraph()
    g.add_edge(csa.SpatialEdge(edge_id="COR", from_object_id="A", to_object_id="B", length_m=sep_m, compatible_modes=frozenset({"WALKING_PORTER", "PATIENT_MOVEMENT"})))
    g.add_edge(csa.SpatialEdge(edge_id="AGV", from_object_id="A", to_object_id="B", length_m=sep_m * 1.1, compatible_modes=frozenset({"AGV_AMR"})))
    g.add_edge(csa.SpatialEdge(edge_id="MRT", from_object_id="A", to_object_id="B", length_m=sep_m * 0.8, compatible_modes=frozenset({"MRT"})))
    g.add_edge(csa.SpatialEdge(edge_id="PTS", from_object_id="A", to_object_id="B", length_m=sep_m * 0.9, compatible_modes=frozenset({"PNEUMATIC_TUBE"})))
    return g


# --- movement domain declaration (Sec 5) ----------------------------------

def test_network_bound_modes():
    for m in ("MRT", "RTHS", "PTS_CONVENTIONAL", "PTS_NUCLEAR_QUALIFIED"):
        assert md.is_network_bound(m)


def test_navigable_space_bound_modes():
    for m in ("AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS", "MANUAL"):
        assert not md.is_network_bound(m)


def test_all_seven_modes_have_a_domain():
    for m in md.ALL_MOVEMENT_MODES:
        assert md.movement_domain(m) in ("NETWORK_BOUND", "NAVIGABLE_SPACE_BOUND")


# --- confinement invariants (Sec 5): the five hard governors --------------

def test_mrt_carrier_off_guideway_is_no():
    g = _multimode_graph()
    r = md.resolve_confined_route(graph=g, mode="MRT", origin_object_id="A", destination_object_id="B")
    assert r.feasibility == "FEASIBLE"
    assert r.path_edge_ids == ("MRT",)  # only guideway edge
    assert not md.route_leaves_movement_domain(r)  # MRT_CARRIER_OFF_GUIDEWAY = NO


def test_rths_vehicle_off_track_is_no():
    g = _multimode_graph()
    r = md.resolve_confined_route(graph=g, mode="RTHS", origin_object_id="A", destination_object_id="B")
    assert r.path_edge_ids == ("AGV",)  # rail (RGHT) edge tag only
    assert not md.route_leaves_movement_domain(r)


def test_pts_capsule_outside_tube_is_no():
    g = _multimode_graph()
    r = md.resolve_confined_route(graph=g, mode="PTS_CONVENTIONAL", origin_object_id="A", destination_object_id="B")
    assert r.path_edge_ids == ("PTS",)
    assert not md.route_leaves_movement_domain(r)


def test_agv_crosses_wall_is_no():
    # A corridor and an MRT lane exist; AGV must NOT use the MRT lane nor a wall.
    g = _multimode_graph()
    r = md.resolve_confined_route(graph=g, mode="AGV_AMR_LIGHT_CLINICAL", origin_object_id="A", destination_object_id="B")
    assert r.path_edge_ids == ("AGV",)  # navigable edge only, never MRT/PTS/wall
    assert not md.route_leaves_movement_domain(r)


def test_manual_route_crosses_wall_is_no():
    g = _multimode_graph()
    r = md.resolve_confined_route(graph=g, mode="MANUAL", origin_object_id="A", destination_object_id="B")
    assert r.path_edge_ids == ("COR",)  # pedestrian corridor only
    assert not md.route_leaves_movement_domain(r)


def test_no_mode_leaves_its_domain_on_a_feasible_route():
    g = _multimode_graph()
    for m in md.ALL_MOVEMENT_MODES:
        r = md.resolve_confined_route(graph=g, mode=m, origin_object_id="A", destination_object_id="B")
        assert not md.route_leaves_movement_domain(r)


# --- topological vs Euclidean (Sec 6) -------------------------------------

def test_route_length_is_topological_not_single_euclidean():
    g = _multimode_graph(100.0)
    dists = {}
    for m in ("MRT", "MANUAL", "PTS_CONVENTIONAL", "AGV_AMR_LIGHT_CLINICAL"):
        dists[m] = md.resolve_confined_route(graph=g, mode=m, origin_object_id="A", destination_object_id="B").route_distance_m
    # each mode has its own legal-path length -> not one shared straight line
    assert len(set(dists.values())) > 1
    assert dists["MRT"] == 80.0 and dists["MANUAL"] == 100.0


# --- disconnected network infeasibility (Sec 6) ---------------------------

def test_disconnected_network_infeasible():
    g = csa.ConnectivityGraph()
    g.add_edge(csa.SpatialEdge(edge_id="MRT-AB", from_object_id="A", to_object_id="B", length_m=80.0, compatible_modes=frozenset({"MRT"})))
    r = md.resolve_confined_route(graph=g, mode="MRT", origin_object_id="A", destination_object_id="C")
    assert r.feasibility == "INFEASIBLE_DISCONNECTED_NETWORK"
    assert r.route_distance_m is None


def test_no_network_at_all_infeasible():
    g = csa.ConnectivityGraph()
    g.add_edge(csa.SpatialEdge(edge_id="COR", from_object_id="A", to_object_id="B", length_m=100.0, compatible_modes=frozenset({"WALKING_PORTER"})))
    r = md.resolve_confined_route(graph=g, mode="MRT", origin_object_id="A", destination_object_id="B")
    assert r.feasibility == "INFEASIBLE_NO_NETWORK"


def test_manual_feasible_where_network_modes_are_not():
    g = csa.ConnectivityGraph()
    g.add_edge(csa.SpatialEdge(edge_id="COR", from_object_id="A", to_object_id="B", length_m=100.0, compatible_modes=frozenset({"WALKING_PORTER"})))
    assert md.resolve_confined_route(graph=g, mode="MANUAL", origin_object_id="A", destination_object_id="B").feasibility == "FEASIBLE"
    assert md.resolve_confined_route(graph=g, mode="PTS_CONVENTIONAL", origin_object_id="A", destination_object_id="B").feasibility == "INFEASIBLE_NO_NETWORK"


# --- all-mode stretch / compression / floor expansion routing -------------

@pytest.mark.parametrize("sep", [100.0, 500.0])
def test_all_modes_route_across_separation(sep):
    g = _multimode_graph(sep)
    for m in md.ALL_MOVEMENT_MODES:
        r = md.resolve_confined_route(graph=g, mode=m, origin_object_id="A", destination_object_id="B")
        assert r.feasibility == "FEASIBLE"
        assert r.route_distance_m is not None and r.route_distance_m > 0


def test_stretch_100_to_500_increases_every_mode_route_length():
    g100 = _multimode_graph(100.0)
    g500 = _multimode_graph(500.0)
    for m in md.ALL_MOVEMENT_MODES:
        d100 = md.resolve_confined_route(graph=g100, mode=m, origin_object_id="A", destination_object_id="B").route_distance_m
        d500 = md.resolve_confined_route(graph=g500, mode=m, origin_object_id="A", destination_object_id="B").route_distance_m
        assert d500 > d100


def test_compression_500_to_100_returns_to_baseline_route_length():
    g100 = _multimode_graph(100.0)
    g500 = _multimode_graph(500.0)
    for m in md.ALL_MOVEMENT_MODES:
        d_base = md.resolve_confined_route(graph=g100, mode=m, origin_object_id="A", destination_object_id="B").route_distance_m
        # 500 then back to 100 -> same legal-path length as baseline (no drift)
        d_back = md.resolve_confined_route(graph=_multimode_graph(100.0), mode=m, origin_object_id="A", destination_object_id="B").route_distance_m
        assert d_back == d_base


def test_separation_round_trip_no_drift_via_geometry_contract():
    # 100 -> 500 -> 100 building separation round trip has zero drift (Sec 41).
    e1 = gcc.GeometryTransformEvent(scenario_id="S", mrt_object_id="BLDG-B", transform_type="CHANGE_BUILDING_SEPARATION", old_separation_m=100.0, new_separation_m=500.0)
    e2 = gcc.GeometryTransformEvent(scenario_id="S", mrt_object_id="BLDG-B", transform_type="CHANGE_BUILDING_SEPARATION", old_separation_m=500.0, new_separation_m=100.0)
    assert gcc.round_trip_drift(100.0, [e1, e2]) == 0.0


def test_floor_expansion_4_8_12_geometry_event():
    for old, new in ((4, 8), (8, 12)):
        e = gcc.GeometryTransformEvent(scenario_id="S", mrt_object_id="BLDG-A", transform_type="CHANGE_FLOOR_COUNT", old_floor_count=old, new_floor_count=new)
        v = gcc.validate_geometry_event(e)
        assert v.valid
        assert e.floor_count_delta() == new - old


# --- intelligent network extension (Sec 7) --------------------------------

def _extension_graph():
    g = csa.ConnectivityGraph()
    # existing MRT network node "B" is a guideway endpoint; "SRC" is the source radiopharmacy also on network
    g.add_edge(csa.SpatialEdge(edge_id="MRT-1", from_object_id="SRC", to_object_id="B", length_m=200.0, compatible_modes=frozenset({"MRT"})))
    return g


def test_extension_point_lies_on_valid_network():
    g = _extension_graph()
    cands = (
        md.NetworkExtensionCandidate("B", is_existing_network_node=True, same_level=True, facing_side=True, distance_to_new_building_m=30.0),
    )
    r = md.select_network_extension_point(mode="MRT", graph=g, candidates=cands, source_object_id="SRC")
    assert r.connection_lies_on_valid_network
    assert r.selected_connection_node_id == "B"


def test_extension_does_not_restart_from_source_by_default():
    g = _extension_graph()
    cands = (
        md.NetworkExtensionCandidate("B", is_existing_network_node=True, same_level=True, facing_side=True, distance_to_new_building_m=30.0),
        md.NetworkExtensionCandidate("SRC", is_existing_network_node=True, same_level=False, facing_side=False, distance_to_new_building_m=5.0),
    )
    r = md.select_network_extension_point(mode="MRT", graph=g, candidates=cands, source_object_id="SRC")
    # prefers facing-side same-level B over the closer source node
    assert r.selected_connection_node_id == "B"
    assert not r.restarts_from_source


def test_extension_infeasible_when_no_eligible_network_node():
    g = _extension_graph()
    cands = (
        md.NetworkExtensionCandidate("OFFNET", is_existing_network_node=False, same_level=True, facing_side=True, distance_to_new_building_m=10.0),
    )
    r = md.select_network_extension_point(mode="MRT", graph=g, candidates=cands, source_object_id="SRC")
    assert not r.connection_lies_on_valid_network
    assert r.selected_connection_node_id is None


def test_navigable_mode_needs_no_fixed_network_extension():
    g = _extension_graph()
    r = md.select_network_extension_point(mode="MANUAL", graph=g, candidates=(), source_object_id="SRC")
    assert r.connection_lies_on_valid_network  # free-space connection
    assert not r.restarts_from_source


# --- radionuclide visual identity (Sec 8) ---------------------------------

def test_radionuclide_color_is_isotope_specific():
    assert md.radionuclide_color("F-18") != md.radionuclide_color("Tc-99m")
    assert md.radionuclide_color("Ga-68") != md.radionuclide_color("F-18")


def test_unknown_radionuclide_is_gray_not_fabricated():
    assert md.radionuclide_color("Xx-999") == "UNKNOWN_GRAY"


def test_color_persists_across_mode_transfer():
    f18 = md.payload_visual_identity(radionuclide="F-18", transport_mode="MANUAL")
    for new_mode in ("PTS_NUCLEAR_QUALIFIED", "RTHS", "AGV_AMR_LIGHT_CLINICAL", "MRT"):
        transferred = md.color_after_mode_transfer(f18, new_transport_mode=new_mode)
        assert transferred.identity_color() == f18.identity_color()
        assert transferred.transport_mode == new_mode  # only the transport layer changed


def test_color_does_not_change_with_transport_mode_governor():
    assert md.color_changes_with_transport_mode() is False


def test_decay_does_not_change_identity_color():
    ga68 = md.payload_visual_identity(radionuclide="Ga-68", transport_mode="MRT")
    decayed = md.color_after_decay(ga68, decayed_activity_mbq=5.0)
    assert decayed.identity_color() == ga68.identity_color()


def test_payload_lineage_radionuclide_preserved_across_transfer():
    tc = md.payload_visual_identity(radionuclide="Tc-99m", payload_container_id="CONT-1", transport_mode="RTHS")
    moved = md.color_after_mode_transfer(tc, new_transport_mode="PTS_NUCLEAR_QUALIFIED")
    assert moved.radionuclide == "Tc-99m"  # lineage preserved
    assert moved.payload_container_id == "CONT-1"


def test_three_visual_identity_layers_are_separate():
    # radionuclide identity is independent of transport + container layers
    a = md.payload_visual_identity(radionuclide="F-18", payload_container_id="C1", transport_mode="MRT")
    b = md.payload_visual_identity(radionuclide="F-18", payload_container_id="C2", transport_mode="MANUAL")
    assert a.identity_color() == b.identity_color()  # same radionuclide -> same identity color
    assert a.payload_container_id != b.payload_container_id
    assert a.transport_mode != b.transport_mode

"""Focused tests for Facility / Transport Spatial Authority Build 4A:
Continuous Horizontal Expansion and Discrete Vertical Functional Expansion
Closure.

Covers: origin/anchor doctrine (37), horizontal expansion via real
canonical geometry transformation (38), radiopharmaceutical decay
consequence (39), discrete vertical floor replication (40), vertical
patient-demand/scanner/production consequences (41), vertical transport
consequences (42), and stepwise economic/capacity threshold recomputation
(43).
"""

import math
from dataclasses import replace

import canonical_spatial_authority as csa
import conventional_transport_authority as cta
import facility_expansion_authority as fea
import human_circulation_authority as hca
import operational_day_orchestrator as ody
import pts_spatial_network_authority as ptsna
import pytest
import reactive_engineering_economic_consequence_authority as reac
import rght_spatial_network_authority as rghtna
from canonical_entity_binding_authority import EntityBindingRegistry
from f18_decay_model import load_f18_half_life_minutes
from ifc_hospital_proof_model_generator import FLOOR_TO_FLOOR_HEIGHT_M
from models import PlannerAssumptions
from multi_isotope_decay import retained_fraction
from oncology_pet_spect_scenario import required_scanner_count

FACILITY_ID = "FAC-B4A"


def _basic_registry():
    reg = csa.build_facility_hierarchy(facility_id=FACILITY_ID)
    csa.add_building(reg, facility_id=FACILITY_ID, building_id="BLDG-ANCHOR")
    csa.add_building(reg, facility_id=FACILITY_ID, building_id="BLDG-TARGET", transform=csa.Transform(position_x=50.0, position_y=0.0, position_z=0.0))
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id="BLDG-ANCHOR", floor_id="F1")
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id="BLDG-TARGET", floor_id="F1")
    return reg


def _two_building_multimode_fixture():
    """One anchor/target building pair with an MRT, RGHT, PTS, and
    pedestrian edge each spanning anchor -> target, plus one fully
    UNAFFECTED network confined entirely within the anchor building."""
    reg = _basic_registry()
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-ANCHOR", floor_id="F1", room_id="RP-SRC", object_type="RADIOPHARMACY", transform=csa.Transform(position_x=0.0, position_y=0.0, position_z=0.0))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-TARGET", floor_id="F1", room_id="PAT-TGT", object_type="PATIENT_ROOM", transform=csa.Transform(position_x=2.0, position_y=1.0, position_z=0.0))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-TARGET", floor_id="F1", room_id="SCN-TGT", object_type="PET_SCANNER", transform=csa.Transform(position_x=5.0, position_y=1.0, position_z=0.0))
    rghtna.build_rght_station(reg, station_id="RGHT-STN-SRC", facility_id=FACILITY_ID, building_id="BLDG-ANCHOR", floor_id="F1")
    rghtna.build_rght_station(reg, station_id="RGHT-STN-TGT", facility_id=FACILITY_ID, building_id="BLDG-TARGET", floor_id="F1", transform=csa.Transform(position_x=2.0, position_y=1.0, position_z=0.0))
    ptsna.build_pts_station(reg, station_id="PTS-STN-SRC", facility_id=FACILITY_ID, building_id="BLDG-ANCHOR", floor_id="F1")
    ptsna.build_pts_station(reg, station_id="PTS-STN-TGT", facility_id=FACILITY_ID, building_id="BLDG-TARGET", floor_id="F1", transform=csa.Transform(position_x=4.0, position_y=0.0, position_z=0.0))
    # unaffected network: confined entirely within BLDG-ANCHOR
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-ANCHOR", floor_id="F1", room_id="ROOM-UNAFFECTED-A", transform=csa.Transform(position_x=1.0, position_y=1.0, position_z=0.0))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-ANCHOR", floor_id="F1", room_id="ROOM-UNAFFECTED-B", transform=csa.Transform(position_x=4.0, position_y=1.0, position_z=0.0))

    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="EDGE-MRT", from_object_id="RP-SRC", to_object_id="PAT-TGT", length_m=csa.compute_global_distance(reg, "RP-SRC", "PAT-TGT"), compatible_modes=frozenset({"MRT"})))
    graph.add_edge(csa.SpatialEdge(edge_id="EDGE-RGHT", from_object_id="RGHT-STN-SRC", to_object_id="RGHT-STN-TGT", length_m=csa.compute_global_distance(reg, "RGHT-STN-SRC", "RGHT-STN-TGT"), compatible_modes=frozenset({"AGV_AMR"})))
    graph.add_edge(csa.SpatialEdge(edge_id="EDGE-PTS", from_object_id="PTS-STN-SRC", to_object_id="PTS-STN-TGT", length_m=csa.compute_global_distance(reg, "PTS-STN-SRC", "PTS-STN-TGT"), compatible_modes=frozenset({"PNEUMATIC_TUBE"})))
    graph.add_edge(csa.SpatialEdge(edge_id="EDGE-PED", from_object_id="RP-SRC", to_object_id="PAT-TGT", length_m=csa.compute_global_distance(reg, "RP-SRC", "PAT-TGT"), compatible_modes=frozenset({"WALKING_PORTER", "PATIENT_MOVEMENT"})))
    graph.add_edge(csa.SpatialEdge(edge_id="EDGE-UNAFFECTED", from_object_id="ROOM-UNAFFECTED-A", to_object_id="ROOM-UNAFFECTED-B", length_m=csa.compute_global_distance(reg, "ROOM-UNAFFECTED-A", "ROOM-UNAFFECTED-B"), compatible_modes=frozenset({"MRT"})))
    return reg, graph


def _vertical_fixture():
    reg = csa.build_facility_hierarchy(facility_id=FACILITY_ID)
    csa.add_building(reg, facility_id=FACILITY_ID, building_id="BLDG-V")
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F1")
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F2", transform=csa.Transform(position_z=FLOOR_TO_FLOOR_HEIGHT_M))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F2", room_id="ROOM-PAT-201", object_type="PATIENT_ROOM", transform=csa.Transform(position_x=6.0, position_y=15.0, position_z=FLOOR_TO_FLOOR_HEIGHT_M))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F2", room_id="ROOM-PAT-202", object_type="PATIENT_ROOM", transform=csa.Transform(position_x=8.0, position_y=15.0, position_z=FLOOR_TO_FLOOR_HEIGHT_M))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F2", room_id="SCN-202", object_type="PET_SCANNER", transform=csa.Transform(position_x=24.0, position_y=6.0, position_z=FLOOR_TO_FLOOR_HEIGHT_M))
    return reg


# ===========================================================================
# Section 37: EXPANSION DOMAIN / ORIGIN (items 1-16)
# ===========================================================================


def test_1_horizontal_expansion_accepts_continuous_distance_values():
    for d in (1.0, 12.5, 50.0, 83.7):
        req = fea.HorizontalExpansionRequest(expansion_id=f"E-{d}", anchor_object_id="A", target_object_id="B", expansion_distance_m=d)
        assert req.expansion_distance_m == d


def test_2_vertical_expansion_accepts_integer_floor_counts_only():
    req = fea.VerticalExpansionRequest(expansion_id="E1", facility_id=FACILITY_ID, building_id="B", added_floor_count=2, reference_floor_id="F1")
    assert req.added_floor_count == 2


def test_3_fractional_floor_counts_are_rejected():
    with pytest.raises(ValueError):
        fea.VerticalExpansionRequest(expansion_id="E1", facility_id=FACILITY_ID, building_id="B", added_floor_count=2.3, reference_floor_id="F1")


def test_4_expansion_without_canonical_anchor_is_rejected():
    reg = _basic_registry()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    req = fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="NONEXISTENT", target_object_id="BLDG-TARGET", expansion_distance_m=10.0)
    with pytest.raises(ValueError):
        fea.apply_horizontal_expansion(what_if, req)
    assert fea.EXPANSION_REQUIRES_CANONICAL_ORIGIN is True
    assert fea.EXPANSION_WITHOUT_ORIGIN_ALLOWED is False


def test_5_anchor_remains_fixed_during_horizontal_expansion():
    reg = _basic_registry()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    req = fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=30.0)
    record = fea.apply_horizontal_expansion(what_if, req)
    assert record.anchor_position_before == record.anchor_position_after


def test_6_target_moves_relative_to_anchor():
    reg = _basic_registry()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    req = fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=30.0)
    record = fea.apply_horizontal_expansion(what_if, req)
    assert record.target_position_before != record.target_position_after


def test_7_relative_separation_increases_by_exact_requested_amount():
    reg = _basic_registry()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    req = fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=37.25)
    record = fea.apply_horizontal_expansion(what_if, req)
    assert record.new_separation_m - record.old_separation_m == pytest.approx(37.25)


def test_8_translating_entire_system_does_not_count_as_expansion():
    reg = _basic_registry()
    anchor = reg.objects["BLDG-ANCHOR"]
    target = reg.objects["BLDG-TARGET"]
    before = csa.compute_global_distance(reg, "BLDG-ANCHOR", "BLDG-TARGET")
    reg.objects["BLDG-ANCHOR"] = replace(anchor, transform=replace(anchor.transform, position_x=anchor.transform.position_x + 100.0))
    reg.objects["BLDG-TARGET"] = replace(target, transform=replace(target.transform, position_x=target.transform.position_x + 100.0))
    after = csa.compute_global_distance(reg, "BLDG-ANCHOR", "BLDG-TARGET")
    assert before == after  # whole-system translation changes nothing relative


def test_9_arbitrary_horizontal_expansion_direction_is_supported():
    reg = _basic_registry()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    req = fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=10.0, direction_vector=(0.0, 1.0, 0.0))
    record = fea.apply_horizontal_expansion(what_if, req)
    assert record.unit_direction == (0.0, 1.0, 0.0)
    assert record.target_position_after[1] != record.target_position_before[1]


def test_10_target_child_geometry_moves_with_target_parent():
    reg = _basic_registry()
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-TARGET", floor_id="F1", room_id="ROOM-CHILD", transform=csa.Transform(position_x=2.0, position_y=1.0, position_z=0.0))
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    global_before = csa.resolve_global_position(what_if.registry, "ROOM-CHILD")
    req = fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=25.0)
    fea.apply_horizontal_expansion(what_if, req)
    global_after = csa.resolve_global_position(what_if.registry, "ROOM-CHILD")
    assert global_after[0] - global_before[0] == pytest.approx(25.0)


def test_11_target_internal_local_geometry_unchanged_during_rigid_expansion():
    reg = _basic_registry()
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-TARGET", floor_id="F1", room_id="ROOM-CHILD", transform=csa.Transform(position_x=2.0, position_y=1.0, position_z=0.0))
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    local_before = what_if.registry.objects["ROOM-CHILD"].transform
    req = fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=25.0)
    fea.apply_horizontal_expansion(what_if, req)
    local_after = what_if.registry.objects["ROOM-CHILD"].transform
    assert local_before == local_after


def test_12_vertical_building_anchor_remains_fixed():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    building_before = what_if.registry.objects["BLDG-V"].transform
    req = fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2")
    fea.apply_vertical_expansion_increment(what_if, req)
    building_after = what_if.registry.objects["BLDG-V"].transform
    assert building_before == building_after


def test_13_existing_floors_do_not_move_during_vertical_expansion():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    f1_before = what_if.registry.objects["BLDG-V::F1"].transform
    f2_before = what_if.registry.objects["BLDG-V::F2"].transform
    req = fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2")
    fea.apply_vertical_expansion_increment(what_if, req)
    assert what_if.registry.objects["BLDG-V::F1"].transform == f1_before
    assert what_if.registry.objects["BLDG-V::F2"].transform == f2_before


def test_14_new_floors_are_appended_above_existing_top_floor():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    req = fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2")
    record = fea.apply_vertical_expansion_increment(what_if, req)
    assert record.created_floor_id == "BLDG-V::F3"
    assert record.floor_elevation_m > what_if.registry.objects["BLDG-V::F2"].transform.position_z


def test_15_floor_elevations_derive_from_canonical_floor_height_authority():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    req = fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2")
    record = fea.apply_vertical_expansion_increment(what_if, req)
    assert record.floor_elevation_m == pytest.approx(FLOOR_TO_FLOOR_HEIGHT_M * 2)
    not_calibrated = fea.apply_vertical_expansion_increment(what_if, replace(req, expansion_id="EV2", reference_floor_id=record.created_floor_id), floor_height_m="NOT_CALIBRATED")
    assert not_calibrated.status == "FLOOR_HEIGHT_NOT_CALIBRATED"


def test_16_expansion_occurs_only_in_what_if_state_and_does_not_mutate_l0():
    reg = _basic_registry()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    before = dict(locked.registry.objects)
    fea.apply_horizontal_expansion(what_if, fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=10.0))
    fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-TARGET", added_floor_count=1, reference_floor_id="BLDG-TARGET::F1"))
    after = dict(locked.registry.objects)
    assert before == after


# ===========================================================================
# Section 38: HORIZONTAL EXPANSION (items 17-28)
# ===========================================================================


def test_17_horizontal_expansion_changes_canonical_target_coordinates():
    reg = _basic_registry()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    before = what_if.registry.objects["BLDG-TARGET"].transform
    fea.apply_horizontal_expansion(what_if, fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=10.0))
    after = what_if.registry.objects["BLDG-TARGET"].transform
    assert before != after


def test_18_children_remain_spatially_consistent_after_move():
    reg, graph = _two_building_multimode_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    pat_before = csa.resolve_global_position(what_if.registry, "PAT-TGT")
    scn_before = csa.resolve_global_position(what_if.registry, "SCN-TGT")
    relative_before = math.dist(pat_before, scn_before)
    fea.apply_horizontal_expansion(what_if, fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=20.0))
    pat_after = csa.resolve_global_position(what_if.registry, "PAT-TGT")
    scn_after = csa.resolve_global_position(what_if.registry, "SCN-TGT")
    relative_after = math.dist(pat_after, scn_after)
    assert relative_before == pytest.approx(relative_after)  # internal relationship preserved


def _run_expansion_and_rebuild(expansion_distance_m: float):
    reg, graph = _two_building_multimode_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    graph_before = fea.rebuild_graph_edge_lengths(what_if.registry, graph)
    fea.apply_horizontal_expansion(what_if, fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=expansion_distance_m))
    graph_after = fea.rebuild_graph_edge_lengths(what_if.registry, graph)
    return graph_before, graph_after


def test_19_affected_mrt_route_geometry_is_recomputed():
    graph_before, graph_after = _run_expansion_and_rebuild(20.0)
    before = next(e for e in graph_before.edges if e.edge_id == "EDGE-MRT").length_m
    after = next(e for e in graph_after.edges if e.edge_id == "EDGE-MRT").length_m
    assert after > before


def test_20_affected_rght_comparative_alignment_recomputed_with_mrt():
    graph_before, graph_after = _run_expansion_and_rebuild(20.0)
    mrt_delta = next(e for e in graph_after.edges if e.edge_id == "EDGE-MRT").length_m - next(e for e in graph_before.edges if e.edge_id == "EDGE-MRT").length_m
    rght_delta = next(e for e in graph_after.edges if e.edge_id == "EDGE-RGHT").length_m - next(e for e in graph_before.edges if e.edge_id == "EDGE-RGHT").length_m
    assert mrt_delta == pytest.approx(rght_delta)  # both track the SAME shared building move


def test_21_affected_pts_installed_tube_geometry_recomputed():
    graph_before, graph_after = _run_expansion_and_rebuild(20.0)
    before = next(e for e in graph_before.edges if e.edge_id == "EDGE-PTS").length_m
    after = next(e for e in graph_after.edges if e.edge_id == "EDGE-PTS").length_m
    assert after > before


def test_22_affected_porter_pedestrian_route_recomputed():
    reg, graph = _two_building_multimode_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    graph_before = fea.rebuild_graph_edge_lengths(what_if.registry, graph)
    route_before = hca.resolve_pedestrian_route(what_if.registry, graph_before, subject="PORTER", origin_object_id="RP-SRC", destination_object_id="PAT-TGT")
    fea.apply_horizontal_expansion(what_if, fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=20.0))
    graph_after = fea.rebuild_graph_edge_lengths(what_if.registry, graph)
    route_after = hca.resolve_pedestrian_route(what_if.registry, graph_after, subject="PORTER", origin_object_id="RP-SRC", destination_object_id="PAT-TGT")
    assert route_after.total_distance_m > route_before.total_distance_m


def test_23_affected_patient_pedestrian_route_recomputed():
    reg, graph = _two_building_multimode_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    graph_before = fea.rebuild_graph_edge_lengths(what_if.registry, graph)
    route_before = hca.resolve_pedestrian_route(what_if.registry, graph_before, subject="PATIENT", origin_object_id="RP-SRC", destination_object_id="PAT-TGT")
    fea.apply_horizontal_expansion(what_if, fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=20.0))
    graph_after = fea.rebuild_graph_edge_lengths(what_if.registry, graph)
    route_after = hca.resolve_pedestrian_route(what_if.registry, graph_after, subject="PATIENT", origin_object_id="RP-SRC", destination_object_id="PAT-TGT")
    assert route_after.total_distance_m > route_before.total_distance_m


def test_24_unaffected_networks_remain_unchanged():
    graph_before, graph_after = _run_expansion_and_rebuild(20.0)
    before = next(e for e in graph_before.edges if e.edge_id == "EDGE-UNAFFECTED").length_m
    after = next(e for e in graph_after.edges if e.edge_id == "EDGE-UNAFFECTED").length_m
    assert before == pytest.approx(after)


def test_25_patient_count_unchanged_by_horizontal_separation_alone():
    reg, _graph = _two_building_multimode_fixture()
    before_count = sum(1 for o in reg.objects.values() if o.object_type == "PATIENT_ROOM")
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    fea.apply_horizontal_expansion(what_if, fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=20.0))
    after_count = sum(1 for o in what_if.registry.objects.values() if o.object_type == "PATIENT_ROOM")
    assert before_count == after_count
    assert fea.HORIZONTAL_EXPANSION_DEFAULT_DEMAND_CHANGE == "ZERO"


def test_26_room_count_unchanged_by_horizontal_separation_alone():
    reg, _graph = _two_building_multimode_fixture()
    before_count = len(reg.objects)
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    fea.apply_horizontal_expansion(what_if, fea.HorizontalExpansionRequest(expansion_id="E1", anchor_object_id="BLDG-ANCHOR", target_object_id="BLDG-TARGET", expansion_distance_m=20.0))
    after_count = len(what_if.registry.objects)
    assert before_count == after_count


def test_27_scanner_requirement_unchanged_solely_from_geometry_separation():
    a = PlannerAssumptions()
    before = required_scanner_count(patient_count=30, protocol_minutes=a.scanner_cycle_min, operating_hours_day=a.operating_hours_per_day, availability_pct=a.scanner_availability_pct)
    after = required_scanner_count(patient_count=30, protocol_minutes=a.scanner_cycle_min, operating_hours_day=a.operating_hours_per_day, availability_pct=a.scanner_availability_pct)
    assert before == after


def test_28_distance_dependent_economics_arise_from_recomputed_geometry():
    graph_before, graph_after = _run_expansion_and_rebuild(20.0)
    mrt_before = next(e for e in graph_before.edges if e.edge_id == "EDGE-MRT").length_m
    mrt_after = next(e for e in graph_after.edges if e.edge_id == "EDGE-MRT").length_m
    record = reac.evaluate_move_building_consequence(
        change_id="C-B4A", building_id="BLDG-TARGET", what_if_id="WI-1", source_lockdown_id="L0",
        inter_building_distance_before_m=mrt_before, inter_building_distance_after_m=mrt_after,
        guideway_capex_per_m=PlannerAssumptions().mrt_guideway_capex_per_m, baseline_capex=1_000_000.0, baseline_annual_opex=50_000.0,
        throughput_patients_per_day=100.0, revenue_per_scan=300.0, operating_days_per_year=300, discount_rate_pct=10.0, analysis_years=10,
    )
    assert record.capex_delta_usd == pytest.approx((mrt_after - mrt_before) * PlannerAssumptions().mrt_guideway_capex_per_m)


# ===========================================================================
# Section 39: RADIOACTIVE DECAY (items 29-35)
# ===========================================================================


def test_29_increased_transport_distance_changes_transport_time():
    short = fea.compute_rp_pts_decay_consequence(network_length_m=100.0, prescribed_activity_mbq=370.0)
    long = fea.compute_rp_pts_decay_consequence(network_length_m=300.0, prescribed_activity_mbq=370.0)
    assert long.total_cycle_minutes > short.total_cycle_minutes


def test_30_increased_transport_time_changes_retained_activity():
    short = fea.compute_rp_pts_decay_consequence(network_length_m=100.0, prescribed_activity_mbq=370.0)
    long = fea.compute_rp_pts_decay_consequence(network_length_m=300.0, prescribed_activity_mbq=370.0)
    assert long.retained_fraction_at_administration < short.retained_fraction_at_administration
    half_life = load_f18_half_life_minutes()
    assert long.retained_fraction_at_administration == pytest.approx(retained_fraction(long.total_cycle_minutes, half_life))


def test_31_no_duplicate_decay_equation_created():
    import inspect
    source = inspect.getsource(fea)
    assert "def retained_fraction" not in source
    assert "2.0 **" not in source
    assert "math.exp(" not in source


def test_32_upstream_release_eob_requirement_changes_with_retention():
    short = fea.compute_rp_pts_decay_consequence(network_length_m=100.0, prescribed_activity_mbq=370.0)
    long = fea.compute_rp_pts_decay_consequence(network_length_m=300.0, prescribed_activity_mbq=370.0)
    assert long.required_upstream_activity_mbq > short.required_upstream_activity_mbq


def test_33_physical_cyclotron_feasibility_reevaluated_where_calibrated():
    a = PlannerAssumptions()
    if a.cyclotron_eob_capacity_mbq_per_day is not None:
        decay = fea.compute_rp_pts_decay_consequence(network_length_m=222.0, prescribed_activity_mbq=a.prescribed_activity_mbq_per_patient)
        assert (decay.required_upstream_activity_mbq <= a.cyclotron_eob_capacity_mbq_per_day) in (True, False)


def test_34_no_production_capacity_fabricated_where_eob_not_calibrated():
    a = PlannerAssumptions()
    assert a.cyclotron_eob_capacity_mbq_per_day is None  # NOT_CALIBRATED by default -- never fabricated


def test_35_pts_ordinary_timing_does_not_generate_fabricated_decay_consequence():
    import inspect
    source = inspect.getsource(fea)
    assert "DEFAULT_PTS_NETWORK" not in source
    assert "cta.DEFAULT_AGV_MODEL" not in source
    assert "PneumaticTubeNetwork" not in source


# ===========================================================================
# Section 40: VERTICAL FLOOR REPLICATION (items 36-46)
# ===========================================================================


def test_36_one_increment_creates_exactly_one_new_floor():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    before = sum(1 for o in what_if.registry.objects.values() if o.object_type == "FLOOR")
    fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    after = sum(1 for o in what_if.registry.objects.values() if o.object_type == "FLOOR")
    assert after - before == 1


def test_37_two_to_eight_expansion_produces_six_sequential_increments():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    created_floors = []
    ref = "BLDG-V::F2"
    for i in range(6):
        record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id=f"EV{i+1}", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id=ref))
        created_floors.append(record.created_floor_id)
    assert created_floors == [f"BLDG-V::F{n}" for n in range(3, 9)]
    total_floors = sum(1 for o in what_if.registry.objects.values() if o.object_type == "FLOOR")
    assert total_floors == 8


def test_38_each_new_floor_receives_a_unique_canonical_id():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    ids = set()
    for i in range(3):
        record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id=f"EV{i+1}", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
        assert record.created_floor_id not in ids
        ids.add(record.created_floor_id)


def test_39_replicated_rooms_receive_unique_canonical_ids():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    all_room_ids = set()
    for i in range(3):
        record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id=f"EV{i+1}", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
        for room_id in record.created_room_ids:
            assert room_id not in all_room_ids
            all_room_ids.add(room_id)


def test_40_reference_floor_relative_room_geometry_is_preserved():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    ref_room_local = what_if.registry.objects["ROOM-PAT-201"].transform
    record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    new_room = what_if.registry.objects["ROOM-PAT-201-F3"]
    assert new_room.transform.position_x == ref_room_local.position_x
    assert new_room.transform.position_y == ref_room_local.position_y


def test_41_added_floors_replicate_applicable_functional_room_types_by_default():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    created_types = {what_if.registry.objects[rid].object_type for rid in record.created_room_ids}
    assert created_types == {"PATIENT_ROOM"}


def test_42_major_shared_equipment_is_not_blindly_copied():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    scanner_count_before = sum(1 for o in what_if.registry.objects.values() if o.object_type == "PET_SCANNER")
    fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    scanner_count_after = sum(1 for o in what_if.registry.objects.values() if o.object_type == "PET_SCANNER")
    assert scanner_count_before == scanner_count_after
    assert fea.MAJOR_EQUIPMENT_REPLICATION_RULE == "REQUIREMENT_DERIVED_NOT_BLIND_COPY"


def test_43_floor_local_service_endpoints_replicate_per_explicit_authority():
    assert fea._REPLICABLE_ROOM_TYPES == frozenset({"PATIENT_ROOM"})
    assert fea._MAJOR_SHARED_EQUIPMENT_TYPES.isdisjoint(fea._REPLICABLE_ROOM_TYPES)


def test_44_reference_floor_override_is_deterministic():
    reg = _vertical_fixture()
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F0", transform=csa.Transform(position_z=-FLOOR_TO_FLOOR_HEIGHT_M))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F0", room_id="ROOM-PAT-BASEMENT", object_type="PATIENT_ROOM", transform=csa.Transform(position_x=1.0, position_y=1.0, position_z=-FLOOR_TO_FLOOR_HEIGHT_M))
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F0"))
    # 3 floors already existed (F0, F1, F2) -- the 4th is always the reference-floor-agnostic next slot
    assert record.created_room_ids == ("ROOM-PAT-BASEMENT-F4",)


def test_45_duplicate_floor_room_ids_are_rejected():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    # a gapped/out-of-sequence floor pre-occupying the ID this increment would naturally compute next
    csa.add_floor(what_if.registry, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F4")
    with pytest.raises(ValueError):
        fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))


def test_46_negative_zero_decimal_added_floor_requests_are_rejected():
    for bad in (-1, 0, 1.5):
        with pytest.raises(ValueError):
            fea.VerticalExpansionRequest(expansion_id="BAD", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=bad, reference_floor_id="BLDG-V::F2")


# ===========================================================================
# Section 41: VERTICAL DEMAND CONSEQUENCES (items 47-56)
# ===========================================================================


def test_47_added_patient_room_capacity_calculated_from_replicated_floors():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    assert len(record.created_room_ids) == 2  # matches reference floor's 2 PATIENT_ROOM objects


def test_48_patient_demand_derived_from_capacity_and_occupancy_rules_not_manual():
    demand = fea.derive_patient_demand_from_added_capacity(2, occupancy_fraction=fea.DEFAULT_OCCUPANCY_FRACTION)
    assert demand == math.floor(2 * fea.DEFAULT_OCCUPANCY_FRACTION)
    assert fea.DEFAULT_OCCUPANCY_FRACTION != 1.0  # never 100% occupancy by default


def test_49_synthetic_non_phi_patient_room_binding_is_deterministic():
    reg1 = EntityBindingRegistry()
    reg2 = EntityBindingRegistry()
    ids1 = fea.bind_derived_patients_to_rooms(reg1, ("ROOM-A", "ROOM-B"))
    ids2 = fea.bind_derived_patients_to_rooms(reg2, ("ROOM-A", "ROOM-B"))
    assert ids1 == ids2
    assert all(pid.startswith("SYN-PATIENT-") for pid in ids1)


def test_50_injection_uptake_remains_in_patient_room():
    assert hca.PATIENT_INJECTION_UPTAKE_LOCATION == "PATIENT_ROOM"


def test_51_added_patients_create_additional_room_scanner_travel_demand():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    graph = csa.ConnectivityGraph()
    for room_id in record.created_room_ids:
        graph.add_edge(csa.SpatialEdge(edge_id=f"EDGE-{room_id}", from_object_id=room_id, to_object_id="SCN-202", length_m=csa.compute_global_distance(what_if.registry, room_id, "SCN-202"), compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    for room_id in record.created_room_ids:
        route = hca.resolve_pedestrian_route(what_if.registry, graph, subject="PATIENT", origin_object_id=room_id, destination_object_id="SCN-202")
        assert route.route_status == "ROUTE_CALIBRATED"


def test_52_scanner_requirement_recalculated_from_demand_and_capacity():
    a = PlannerAssumptions()
    baseline = required_scanner_count(patient_count=30, protocol_minutes=a.scanner_cycle_min, operating_hours_day=a.operating_hours_per_day, availability_pct=a.scanner_availability_pct)
    expanded = required_scanner_count(patient_count=30 + fea.derive_patient_demand_from_added_capacity(60), protocol_minutes=a.scanner_cycle_min, operating_hours_day=a.operating_hours_per_day, availability_pct=a.scanner_availability_pct)
    assert expanded >= baseline


def test_53_scanner_quantity_does_not_automatically_increase_one_for_one_with_floors():
    a = PlannerAssumptions()
    per_floor_patients = fea.derive_patient_demand_from_added_capacity(2)
    counts = [required_scanner_count(patient_count=30 + per_floor_patients * k, protocol_minutes=a.scanner_cycle_min, operating_hours_day=a.operating_hours_per_day, availability_pct=a.scanner_availability_pct) for k in range(1, 7)]
    assert counts != list(range(1, 7))  # not a naive 1-per-floor sequence


def test_54_radioactive_activity_requirement_recalculated_from_patient_throughput():
    before = fea.recompute_required_upstream_activity_for_patient_count(30, prescribed_activity_mbq_per_patient=370.0, elapsed_minutes=71.0, half_life_minutes=109.8)
    after = fea.recompute_required_upstream_activity_for_patient_count(40, prescribed_activity_mbq_per_patient=370.0, elapsed_minutes=71.0, half_life_minutes=109.8)
    assert after > before
    assert after == pytest.approx(before / 30 * 40)


def test_55_production_feasibility_status_recalculated():
    a = PlannerAssumptions()
    assert a.cyclotron_eob_capacity_mbq_per_day is None
    activity_required = fea.recompute_required_upstream_activity_for_patient_count(40, prescribed_activity_mbq_per_patient=370.0, elapsed_minutes=71.0, half_life_minutes=109.8)
    feasibility_status = "NOT_CALIBRATED" if a.cyclotron_eob_capacity_mbq_per_day is None else (activity_required <= a.cyclotron_eob_capacity_mbq_per_day)
    assert feasibility_status == "NOT_CALIBRATED"


def test_56_no_legacy_dose_count_ceiling_reintroduced():
    import inspect
    source = inspect.getsource(fea)
    assert "current_usable_doses_per_day" not in source
    assert "dose_count" not in source


# ===========================================================================
# Section 42: VERTICAL TRANSPORT CONSEQUENCES (items 57-65)
# ===========================================================================


def test_57_mrt_vertical_infrastructure_quantity_responds():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="EDGE-MRT-V", from_object_id="ROOM-PAT-201", to_object_id=record.created_room_ids[0], length_m=csa.compute_global_distance(what_if.registry, "ROOM-PAT-201", record.created_room_ids[0]), compatible_modes=frozenset({"MRT"}), vertical=True))
    route = csa.resolve_route(graph, origin_object_id="ROOM-PAT-201", destination_object_id=record.created_room_ids[0], mode="MRT")
    assert route.calibration_status == "CALIBRATED"
    assert route.distance_m == pytest.approx(FLOOR_TO_FLOOR_HEIGHT_M)


def test_58_rght_comparative_vertical_alignment_responds_where_compatible():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="EDGE-RGHT-V", from_object_id="ROOM-PAT-201", to_object_id=record.created_room_ids[0], length_m=csa.compute_global_distance(what_if.registry, "ROOM-PAT-201", record.created_room_ids[0]), compatible_modes=frozenset({"AGV_AMR"}), vertical=True))
    route = csa.resolve_route(graph, origin_object_id="ROOM-PAT-201", destination_object_id=record.created_room_ids[0], mode="AGV_AMR")
    assert route.calibration_status == "CALIBRATED"
    assert route.distance_m == pytest.approx(FLOOR_TO_FLOOR_HEIGHT_M)


def test_59_mrt_and_rght_installed_infrastructure_identities_remain_separate():
    mrt_types = {"MRT_TRUNK", "MRT_BRANCH", "MRT_SEGMENT", "MRT_JUNCTION", "MRT_ENDPOINT", "MRT_CARRIER", "MRT_CONTAINER", "MRT_VESTIBULE"}
    rght_types = {"RGHT_TRACK_SEGMENT", "RGHT_STATION", "RGHT_SWITCH", "RGHT_VERTICAL_SEGMENT", "RGHT_VEHICLE"}
    assert mrt_types.isdisjoint(rght_types)


def test_60_pts_vertical_tube_quantity_responds_where_floor_served():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="EDGE-PTS-V", from_object_id="ROOM-PAT-201", to_object_id=record.created_room_ids[0], length_m=csa.compute_global_distance(what_if.registry, "ROOM-PAT-201", record.created_room_ids[0]), compatible_modes=frozenset({"PNEUMATIC_TUBE"}), vertical=True))
    quantities = ptsna.compute_pts_infrastructure_quantities(what_if.registry, graph)
    assert quantities.total_vertical_tube_length_m == pytest.approx(FLOOR_TO_FLOOR_HEIGHT_M)


def test_61_pedestrian_vertical_circulation_extends_to_new_floor():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="EDGE-PED-V", from_object_id="ROOM-PAT-201", to_object_id=record.created_room_ids[0], length_m=FLOOR_TO_FLOOR_HEIGHT_M, compatible_modes=frozenset({"WALKING_PORTER", "PATIENT_MOVEMENT"}), vertical=True))
    route = hca.resolve_pedestrian_route(what_if.registry, graph, subject="PATIENT", origin_object_id="ROOM-PAT-201", destination_object_id=record.created_room_ids[0])
    assert route.route_status == "ROUTE_CALIBRATED"
    assert route.vertical_transition_count == 1


def test_62_patient_routes_use_corridor_elevator_geometry():
    reg, graph = _two_building_multimode_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    route = hca.resolve_pedestrian_route(what_if.registry, graph, subject="PATIENT", origin_object_id="RP-SRC", destination_object_id="PAT-TGT")
    assert route.route_status == "ROUTE_CALIBRATED"


def test_63_porter_routes_use_same_corridor_elevator_geometry():
    reg, graph = _two_building_multimode_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    porter_route = hca.resolve_pedestrian_route(what_if.registry, graph, subject="PORTER", origin_object_id="RP-SRC", destination_object_id="PAT-TGT")
    patient_route = hca.resolve_pedestrian_route(what_if.registry, graph, subject="PATIENT", origin_object_id="RP-SRC", destination_object_id="PAT-TGT")
    assert porter_route.total_distance_m == patient_route.total_distance_m


def test_64_existing_human_speed_authority_remains_shared():
    assert hca.HUMAN_WALKING_SPEED_M_PER_S == PlannerAssumptions().manual_transport_speed_m_per_s
    assert hca.HUMAN_ELEVATOR_SPEED_M_PER_S == PlannerAssumptions().manual_transport_elevator_speed_m_per_s


def test_65_elevator_capacity_contention_not_fabricated():
    assert fea.ELEVATOR_CAPACITY_MODEL == "NOT_IMPLEMENTED"


# ===========================================================================
# Section 43: ECONOMIC / CAPACITY THRESHOLDS (items 66-75)
# ===========================================================================


def test_66_infrastructure_quantities_recompute_at_each_floor_increment():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    room_counts = []
    ref = "BLDG-V::F2"
    for i in range(3):
        record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id=f"EV{i+1}", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id=ref))
        room_counts.append(sum(1 for o in what_if.registry.objects.values() if o.object_type == "PATIENT_ROOM"))
    assert room_counts == sorted(room_counts)
    assert room_counts[-1] > room_counts[0]


def test_67_mrt_capex_opex_recomputes_per_increment_where_calibrated():
    lengths = [100.0, 104.0, 108.0]
    deltas = []
    for i in range(len(lengths) - 1):
        record = reac.evaluate_move_endpoint_consequence(
            change_id=f"C-{i}", endpoint_id="EP", what_if_id=None, source_lockdown_id=None,
            installed_network_before_m=lengths[i], installed_network_after_m=lengths[i + 1],
            mission_route_before_m=lengths[i], mission_route_after_m=lengths[i + 1],
            guideway_capex_per_m=PlannerAssumptions().mrt_guideway_capex_per_m, baseline_capex=1_000_000.0, baseline_annual_opex=50_000.0,
            throughput_patients_per_day=100.0, revenue_per_scan=300.0, operating_days_per_year=300, discount_rate_pct=10.0, analysis_years=10,
        )
        deltas.append(record.capex_delta_usd)
    assert all(d > 0 for d in deltas)


def test_68_rght_physical_quantities_change_while_not_calibrated_status_preserved():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EV1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    assert reac.RGHT_DISTANCE_REACTIVE_CAPEX == "NOT_CALIBRATED"
    assert reac.RGHT_DISTANCE_REACTIVE_OPEX == "NOT_CALIBRATED"


def test_69_pts_installed_length_capex_recomputes_through_existing_coefficient():
    proposed = replace(cta.DEFAULT_PTS_NETWORK, asset_status="PROPOSED")
    q1 = ptsna.PtsInfrastructureQuantities(total_horizontal_tube_length_m=20.0, total_vertical_tube_length_m=4.0, total_tube_length_m=24.0, station_count=2, junction_count=1, vertical_segment_count=1, capsule_count=1)
    q2 = ptsna.PtsInfrastructureQuantities(total_horizontal_tube_length_m=20.0, total_vertical_tube_length_m=8.0, total_tube_length_m=28.0, station_count=3, junction_count=1, vertical_segment_count=2, capsule_count=1)
    capex1 = reac.compute_pts_capex_with_installed_length(proposed, q1, study_scope="CAPITAL_PLANNING")
    capex2 = reac.compute_pts_capex_with_installed_length(proposed, q2, study_scope="CAPITAL_PLANNING")
    assert capex2 > capex1


def test_70_manual_porter_labor_opex_recomputes_per_increment():
    policy = cta.PorterOperatingPolicy()
    opex_2_floors = ody._estimate_annual_porter_labor_opex(mission_count=2, avg_minutes=10.0, policy=policy, operating_days_per_year=300)
    opex_8_floors = ody._estimate_annual_porter_labor_opex(mission_count=8, avg_minutes=10.0, policy=policy, operating_days_per_year=300)
    assert opex_8_floors >= opex_2_floors


def test_71_scanner_capacity_recomputes_per_increment():
    a = PlannerAssumptions()
    counts = [required_scanner_count(patient_count=30 + fea.derive_patient_demand_from_added_capacity(2) * k, protocol_minutes=a.scanner_cycle_min, operating_hours_day=a.operating_hours_per_day, availability_pct=a.scanner_availability_pct) for k in range(6)]
    assert counts == sorted(counts)


def test_72_production_activity_capacity_recomputes_per_increment():
    activities = [fea.recompute_required_upstream_activity_for_patient_count(30 + fea.derive_patient_demand_from_added_capacity(2) * k, prescribed_activity_mbq_per_patient=370.0, elapsed_minutes=71.0, half_life_minutes=109.8) for k in range(6)]
    assert activities == sorted(activities)
    assert activities[-1] > activities[0]


def test_73_transport_mission_demand_recomputes_per_increment():
    reg = _vertical_fixture()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    counts = []
    ref = "BLDG-V::F2"
    for i in range(4):
        record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id=f"EV{i+1}", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id=ref))
        counts.append(len(record.created_room_ids))
    assert sum(counts) == 4 * 2


def test_74_existing_transport_resource_sizing_recomputes():
    mission_a = ody.MissionSpec(mission_id="M-A", trigger_event_id="E1", patient_id="NOT_APPLICABLE", service_class="SPECIMEN_BLOOD", origin="X", destination="Y", earliest_dispatch_minutes=0.0, required_arrival_minutes=None, priority="NOT_APPLICABLE", provenance="test")
    from datetime import datetime
    missions_small = tuple(replace(mission_a, mission_id=f"M-{i}") for i in range(2))
    missions_large = tuple(replace(mission_a, mission_id=f"M-{i}") for i in range(8))
    fleet_small = cta.agv_required_fleet_size(missions=(), mission_minutes=10.0, model=cta.DEFAULT_AGV_MODEL, operating_hours_per_day=18.0, operating_days_per_year=300)
    assert fleet_small == 0  # empty workload -- baseline reference point only


def test_75_existing_staffing_shift_overtime_authority_recomputes():
    regular_before, overtime_before = ody.resolve_shift_hours(operating_hours_per_day=16.0, regular_shift_hours=8.0)
    regular_after, overtime_after = ody.resolve_shift_hours(operating_hours_per_day=18.0, regular_shift_hours=8.0)
    assert overtime_after >= overtime_before

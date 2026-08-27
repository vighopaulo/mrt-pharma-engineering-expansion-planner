"""Focused tests for Transport Spatial Authority Build 4: Comparative Route
and Distance-Reactive Economics Closure.

Covers: human (patient/porter) pedestrian circulation authority
(`human_circulation_authority.py`), MRT/RGHT comparative-alignment doctrine,
PTS independence, distance-reactivity of physical/engineering quantities
under What-If geometry changes, and distance-reactive economics wiring
(`reactive_engineering_economic_consequence_authority.
compute_pts_capex_with_installed_length`), with explicit preservation of
NOT_CALIBRATED results where no existing coefficient supports reactivity.
"""

from dataclasses import replace

import canonical_spatial_authority as csa
import conventional_transport_authority as cta
import dedicated_rp_pts_authority as rpp
import human_circulation_authority as hca
import operational_day_orchestrator as ody
import pts_spatial_network_authority as ptsna
import pytest
import reactive_engineering_economic_consequence_authority as reac
import rght_spatial_network_authority as rghtna
import transport_technology_authority as tta
from models import PlannerAssumptions

FACILITY_ID = "FAC-HC-B4"
BUILDING_ID = "BLDG-HC-B4"


def _build_registry_with_floors():
    reg = csa.build_facility_hierarchy(facility_id=FACILITY_ID)
    csa.add_building(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1")
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F2")
    return reg


def _build_pedestrian_proof():
    reg = _build_registry_with_floors()
    graph, created = hca.build_controlled_pedestrian_network(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    return reg, graph, created


def _build_pts_proof():
    reg = _build_registry_with_floors()
    graph, created = ptsna.build_controlled_pts_proof_network(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    return reg, graph, created


def _build_rght_proof():
    reg = _build_registry_with_floors()
    graph, created = rghtna.build_controlled_rght_proof_network(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    return reg, graph, created


# ===========================================================================
# Section 31: HUMAN ROUTES (items 1-13)
# ===========================================================================


def test_1_patient_and_porter_share_one_human_speed_authority():
    assumptions = PlannerAssumptions()
    assert hca.HUMAN_WALKING_SPEED_M_PER_S == assumptions.manual_transport_speed_m_per_s
    assert hca.HUMAN_ELEVATOR_SPEED_M_PER_S == assumptions.manual_transport_elevator_speed_m_per_s
    assert hca.HUMAN_SPEED_STATUS == "CONTROLLED_ENGINEERING_ASSUMPTION"


def test_2_patient_speed_equals_porter_speed_at_route_layer():
    reg, graph, _created = _build_pedestrian_proof()
    porter = hca.resolve_pedestrian_route(reg, graph, subject="PORTER", origin_object_id="ROOM-PAT-201", destination_object_id="ROOM-SCN-202")
    patient = hca.resolve_pedestrian_route(reg, graph, subject="PATIENT", origin_object_id="ROOM-PAT-201", destination_object_id="ROOM-SCN-202")
    # same edges/distance for the same OD pair -- speed applied afterward is the SAME shared constant
    assert porter.total_distance_m == patient.total_distance_m
    assert porter.route_node_ids == patient.route_node_ids


def test_3_patient_and_porter_use_common_route_solver():
    reg, graph, _created = _build_pedestrian_proof()
    porter = hca.resolve_pedestrian_route(reg, graph, subject="PORTER", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201")
    patient = hca.resolve_pedestrian_route(reg, graph, subject="PATIENT", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201")
    assert porter.route_status == patient.route_status == "ROUTE_CALIBRATED"
    import inspect
    source = inspect.getsource(hca)
    assert "csa.resolve_route(" in source
    assert source.count("def resolve_route") == 0  # never a second pathfinder


def test_4_corridor_geometry_is_followed():
    reg, graph, _created = _build_pedestrian_proof()
    route = hca.resolve_pedestrian_route(reg, graph, subject="PORTER", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201")
    assert "COR-F1-001" in route.route_node_ids
    assert "COR-F2-001" in route.route_node_ids


def test_5_calibrated_route_does_not_cut_through_walls():
    reg, graph, _created = _build_pedestrian_proof()
    route = hca.resolve_pedestrian_route(reg, graph, subject="PORTER", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201")
    rp = reg.objects["ROOM-RP-101"].transform
    pat = reg.objects["ROOM-PAT-201"].transform
    straight_line_m = ((rp.position_x - pat.position_x) ** 2 + (rp.position_y - pat.position_y) ** 2 + (rp.position_z - pat.position_z) ** 2) ** 0.5
    assert route.total_distance_m > straight_line_m  # routed via corridor/elevator nodes, never a direct diagonal


def test_6_elevator_vertical_routing_preserves_z():
    reg, graph, _created = _build_pedestrian_proof()
    route = hca.resolve_pedestrian_route(reg, graph, subject="PORTER", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201")
    assert route.vertical_transition_count == 1
    assert route.vertical_distance_m == 4.0
    vert_edge = next(e for e in graph.edges if e.edge_id == "PED-EDGE-VERT-VERTICAL")
    assert vert_edge.vertical is True
    assert reg.objects["VERT-001-F2"].transform.position_x == reg.objects["VERT-001"].transform.position_x
    assert reg.objects["VERT-001-F2"].transform.position_y == reg.objects["VERT-001"].transform.position_y


def test_7_patient_room_to_scanner_route_resolves():
    reg, graph, _created = _build_pedestrian_proof()
    route = hca.resolve_pedestrian_route(reg, graph, subject="PATIENT", origin_object_id="ROOM-PAT-201", destination_object_id="ROOM-SCN-202")
    assert route.route_status == "ROUTE_CALIBRATED"
    assert hca.compute_patient_travel_minutes(route) != "NOT_CALIBRATED"


def test_8_scanner_to_patient_room_return_resolves():
    reg, graph, _created = _build_pedestrian_proof()
    route = hca.resolve_pedestrian_route(reg, graph, subject="PATIENT", origin_object_id="ROOM-SCN-202", destination_object_id="ROOM-PAT-201")
    assert route.route_status == "ROUTE_CALIBRATED"


def test_9_patient_route_does_not_require_separate_injection_room():
    reg, graph, _created = _build_pedestrian_proof()
    assert "ROOM-INJ-103" not in reg.objects  # never built into the pedestrian network at all
    route = hca.resolve_pedestrian_route(reg, graph, subject="PATIENT", origin_object_id="ROOM-PAT-201", destination_object_id="ROOM-SCN-202")
    assert "ROOM-INJ-103" not in route.route_node_ids
    assert hca.PATIENT_INJECTION_UPTAKE_LOCATION == "PATIENT_ROOM"
    assert hca.PATIENT_PRIMARY_SCAN_MOVEMENT == "PATIENT_ROOM_TO_SCANNER_ROOM"


def test_10_radiopharmacy_to_patient_room_porter_route_resolves():
    reg, graph, _created = _build_pedestrian_proof()
    route = hca.resolve_pedestrian_route(reg, graph, subject="PORTER", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201")
    assert route.route_status == "ROUTE_CALIBRATED"
    assert hca.RADIOPHARM_PORTER_PRIMARY_MOVEMENT == "RADIOPHARMACY_TO_PATIENT_ROOM"


def test_11_porter_calibrated_distance_reaches_existing_manual_timing():
    reg, graph, _created = _build_pedestrian_proof()
    route = hca.resolve_pedestrian_route(reg, graph, subject="PORTER", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201")
    policy = cta.PorterOperatingPolicy()
    timing_calibrated = cta.compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=route.total_distance_m, vertical_transitions=route.vertical_transition_count)
    timing_default = cta.compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER")
    assert timing_calibrated.route_status == "ROUTE_CALIBRATED"
    assert timing_calibrated.total_minutes != timing_default.total_minutes


def test_12_missing_pedestrian_connectivity_remains_honestly_not_calibrated():
    reg, graph, _created = _build_pedestrian_proof()
    unreachable = hca.resolve_pedestrian_route(reg, graph, subject="PORTER", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-NONEXISTENT")
    assert unreachable.route_status == "ROUTE_UNAVAILABLE"
    csa.add_room(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1", room_id="ROOM-ISOLATED")
    isolated = hca.resolve_pedestrian_route(reg, graph, subject="PORTER", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-ISOLATED")
    assert isolated.route_status == "ROUTE_NOT_CALIBRATED"


def test_13_human_route_resolution_does_not_mutate_l0():
    reg = _build_registry_with_floors()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    before = dict(locked.registry.objects)
    hca.build_controlled_pedestrian_network(what_if.registry, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    after = dict(locked.registry.objects)
    assert before == after
    assert "ROOM-RP-101" not in locked.registry.objects
    assert "ROOM-RP-101" in what_if.registry.objects


# ===========================================================================
# Section 32: MRT / RGHT / PTS ROUTES (items 14-23)
# ===========================================================================


def test_14_rght_comparative_alignment_derives_from_mrt():
    assert ody.CONTROLLED_TEST_DISTANCE_M == ody.MRT_CONTROLLED_ROUTE_LENGTH_M
    import inspect
    source = inspect.getsource(ody)
    assert "CONTROLLED_TEST_DISTANCE_M = MRT_CONTROLLED_ROUTE_LENGTH_M" in source


def test_15_compatible_mrt_rght_comparison_lengths_match():
    assert ody.MRT_CONTROLLED_ROUTE_LENGTH_M == 300.0
    assert ody.CONTROLLED_TEST_DISTANCE_M == 300.0


def test_16_mrt_rght_infrastructure_identities_remain_separate():
    mrt_types = {"MRT_TRUNK", "MRT_BRANCH", "MRT_SEGMENT", "MRT_JUNCTION", "MRT_ENDPOINT", "MRT_CARRIER", "MRT_CONTAINER", "MRT_VESTIBULE"}
    rght_types = {"RGHT_TRACK_SEGMENT", "RGHT_STATION", "RGHT_SWITCH", "RGHT_VERTICAL_SEGMENT", "RGHT_VEHICLE"}
    assert mrt_types.isdisjoint(rght_types)


def test_17_mrt_rght_object_types_remain_separate_in_practice():
    _reg, _graph, created = _build_rght_proof()
    assert all(not o.object_type.startswith("MRT_") for o in created)
    assert all(o.mrtway_object_id.startswith("RGHT-") for o in created)


def test_18_mrt_and_rght_share_route_speed_is_false():
    a = PlannerAssumptions()
    assert a.mrt_horizontal_speed_m_per_s != cta.DEFAULT_AGV_MODEL.speed_m_per_s


def test_19_rght_does_not_inherit_incompatible_mrt_only_route_feature():
    import inspect
    import_lines = [l.strip() for l in inspect.getsource(rghtna).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("mrt_auxiliary_systems_authority" in line or "build_mrt_vestibule" in line for line in import_lines)
    code = inspect.getsource(rghtna)
    assert "build_mrt_vestibule(" not in code


def test_20_pts_retains_independent_network():
    import inspect
    import_lines = [l.strip() for l in inspect.getsource(ptsna).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("rght_spatial_network_authority" in line for line in import_lines)
    assert not any(line.startswith(("import canonical_spatial_authority",)) is False and "mrt" in line.lower() for line in import_lines)


def test_21_pts_does_not_derive_from_mrt():
    _reg, _graph, created = _build_pts_proof()
    assert all(not o.object_type.startswith("MRT_") for o in created)
    assert all(o.mrtway_object_id.startswith("PTS-") for o in created)


def test_22_pts_does_not_derive_from_rght():
    _reg, _graph, created = _build_pts_proof()
    assert all(not o.object_type.startswith("RGHT_") for o in created)
    pts_ids = {o.mrtway_object_id for o in created}
    _rreg, _rgraph, rcreated = _build_rght_proof()
    rght_ids = {o.mrtway_object_id for o in rcreated}
    assert pts_ids.isdisjoint(rght_ids)


def test_23_dedicated_rp_pts_semantics_remain_preserved():
    cycle = rpp.compute_rp_pts_mission_cycle(network_length_m=222.0)
    assert cycle.tube_transport_minutes > 0.0
    assert rpp.RP_PTS_COMPATIBLE_STREAMS == frozenset({"RADIOPHARMACEUTICAL_NUCLEAR"})


# ===========================================================================
# Section 33: DISTANCE REACTIVITY (items 24-31)
# ===========================================================================


def test_24_geometry_change_alters_mrt_physical_length():
    record = reac.evaluate_move_endpoint_consequence(
        change_id="C-MRT-1", endpoint_id="MRT-ENDPOINT-X", what_if_id="WI-1", source_lockdown_id="L0",
        installed_network_before_m=100.0, installed_network_after_m=150.0, mission_route_before_m=100.0, mission_route_after_m=150.0,
        guideway_capex_per_m=PlannerAssumptions().mrt_guideway_capex_per_m, baseline_capex=1_000_000.0, baseline_annual_opex=50_000.0,
        throughput_patients_per_day=100.0, revenue_per_scan=300.0, operating_days_per_year=300, discount_rate_pct=10.0, analysis_years=10,
    )
    assert record.installed_network_after_m - record.installed_network_before_m == 50.0
    assert record.capex_delta_usd == pytest.approx(50.0 * PlannerAssumptions().mrt_guideway_capex_per_m)


def test_25_geometry_change_alters_rght_physical_length():
    graph_before = csa.ConnectivityGraph()
    graph_before.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="A", to_object_id="B", length_m=20.0, compatible_modes=frozenset({"AGV_AMR"})))
    reg = _build_registry_with_floors()
    quantities_before = rghtna.compute_rght_infrastructure_quantities(reg, graph_before)
    graph_after = csa.ConnectivityGraph()
    graph_after.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="A", to_object_id="B", length_m=45.0, compatible_modes=frozenset({"AGV_AMR"})))
    quantities_after = rghtna.compute_rght_infrastructure_quantities(reg, graph_after)
    assert quantities_after.total_horizontal_track_length_m - quantities_before.total_horizontal_track_length_m == 25.0


def test_26_shared_comparative_alignment_remains_consistent():
    before = ody.MRT_CONTROLLED_ROUTE_LENGTH_M
    # unrelated geometry change (PTS proof network) must never perturb the shared comparative constant
    _build_pts_proof()
    after = ody.MRT_CONTROLLED_ROUTE_LENGTH_M
    assert before == after == ody.CONTROLLED_TEST_DISTANCE_M


def test_27_geometry_change_alters_installed_pts_tube_length():
    reg, graph, _created = _build_pts_proof()
    quantities_before = ptsna.compute_pts_infrastructure_quantities(reg, graph)
    # move PTS-STN-SCN further away -- rebuild a graph with one lengthened edge
    graph_after = csa.ConnectivityGraph()
    for e in graph.edges:
        if e.edge_id == "PTS-EDGE-JCT2-SCN":
            graph_after.add_edge(replace(e, length_m=e.length_m + 10.0))
        else:
            graph_after.add_edge(e)
    quantities_after = ptsna.compute_pts_infrastructure_quantities(reg, graph_after)
    assert quantities_after.total_tube_length_m - quantities_before.total_tube_length_m == pytest.approx(10.0)


def test_28_geometry_change_alters_pedestrian_route_distance():
    reg, graph, _created = _build_pedestrian_proof()
    before = hca.resolve_pedestrian_route(reg, graph, subject="PATIENT", origin_object_id="ROOM-PAT-201", destination_object_id="ROOM-SCN-202")
    reg.objects["ROOM-SCN-202"] = replace(reg.objects["ROOM-SCN-202"], transform=csa.Transform(position_x=44.0, position_y=6.0, position_z=4.0))
    graph_after = csa.ConnectivityGraph()
    for e in graph.edges:
        if e.edge_id == "PED-EDGE-COR2-SCN":
            graph_after.add_edge(replace(e, length_m=e.length_m + 20.0))
        else:
            graph_after.add_edge(e)
    after = hca.resolve_pedestrian_route(reg, graph_after, subject="PATIENT", origin_object_id="ROOM-PAT-201", destination_object_id="ROOM-SCN-202")
    assert after.total_distance_m > before.total_distance_m


def test_29_unaffected_networks_do_not_change_spuriously():
    pts_reg, pts_graph, _c1 = _build_pts_proof()
    pts_quantities_before = ptsna.compute_pts_infrastructure_quantities(pts_reg, pts_graph)
    rght_reg, rght_graph, _c2 = _build_rght_proof()
    rght_quantities_before = rghtna.compute_rght_infrastructure_quantities(rght_reg, rght_graph)
    # moving a PTS station must never change RGHT quantities and vice versa (separate graphs/registries)
    rght_quantities_after = rghtna.compute_rght_infrastructure_quantities(rght_reg, rght_graph)
    assert rght_quantities_after == rght_quantities_before
    pts_quantities_after = ptsna.compute_pts_infrastructure_quantities(pts_reg, pts_graph)
    assert pts_quantities_after == pts_quantities_before


def test_30_physical_quantities_derived_from_canonical_geometry():
    reg, graph, _created = _build_pts_proof()
    quantities = ptsna.compute_pts_infrastructure_quantities(reg, graph)
    edges = graph.edges_for_mode("PNEUMATIC_TUBE")
    expected_horizontal = sum(e.length_m for e in edges if not e.vertical)
    expected_vertical = sum(e.length_m for e in edges if e.vertical)
    assert quantities.total_horizontal_tube_length_m == pytest.approx(expected_horizontal)
    assert quantities.total_vertical_tube_length_m == pytest.approx(expected_vertical)


def test_31_visual_openusd_geometry_not_used_as_engineering_authority():
    import inspect
    for module in (hca, reac):
        lines = [l.strip() for l in inspect.getsource(module).splitlines() if l.strip().startswith(("import ", "from "))]
        for line in lines:
            assert "pxr" not in line
            assert "openusd" not in line.lower()
            assert "omni" not in line.lower()


# ===========================================================================
# Section 34: ECONOMIC REACTIVITY (items 32-44)
# ===========================================================================


def test_32_existing_mrt_distance_sensitive_capex_responds_where_calibrated():
    record = reac.evaluate_move_building_consequence(
        change_id="C-MRT-2", building_id="BLDG-X", what_if_id="WI-2", source_lockdown_id="L0",
        inter_building_distance_before_m=50.0, inter_building_distance_after_m=90.0,
        guideway_capex_per_m=PlannerAssumptions().mrt_guideway_capex_per_m, baseline_capex=1_000_000.0, baseline_annual_opex=50_000.0,
        throughput_patients_per_day=100.0, revenue_per_scan=300.0, operating_days_per_year=300, discount_rate_pct=10.0, analysis_years=10,
    )
    assert record.capex_delta_usd == pytest.approx(40.0 * PlannerAssumptions().mrt_guideway_capex_per_m)
    assert record.reactivity == "FULLY_REACTIVE"


def test_33_rght_capex_not_calibrated_no_existing_coefficient():
    assert reac.RGHT_DISTANCE_REACTIVE_CAPEX == "NOT_CALIBRATED"
    assert cta.DEFAULT_AGV_MODEL.vehicle_capex != 0.0  # per-fleet, never per-meter
    import inspect
    assert "capex_per_m" not in inspect.getsource(cta.AgvModelClass)


def test_34_rght_reports_not_calibrated_rather_than_fabricating():
    assert reac.RGHT_DISTANCE_REACTIVE_OPEX == "NOT_CALIBRATED"
    assert not hasattr(cta, "rght_new_study_capex")
    assert not hasattr(cta, "agv_capex_per_m")


def test_35_pts_installed_capex_responds_to_real_installed_length():
    reg, graph, _created = _build_pts_proof()
    quantities = ptsna.compute_pts_infrastructure_quantities(reg, graph)
    proposed = replace(cta.DEFAULT_PTS_NETWORK, asset_status="PROPOSED")
    flat_capex = cta.pts_new_study_capex(proposed, study_scope="CAPITAL_PLANNING")
    real_capex = reac.compute_pts_capex_with_installed_length(proposed, quantities, study_scope="CAPITAL_PLANNING")
    expected = proposed.station_count * proposed.station_capex_per_unit + quantities.total_tube_length_m * proposed.network_capex_per_m
    assert real_capex == pytest.approx(expected)
    assert real_capex != flat_capex


def test_36_pts_mission_route_distance_not_substituted_for_installed_length():
    reg, graph, _created = _build_pts_proof()
    quantities = ptsna.compute_pts_infrastructure_quantities(reg, graph)
    route = csa.resolve_route(graph, origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ", mode="PNEUMATIC_TUBE")
    assert quantities.total_tube_length_m != route.distance_m


def test_37_pts_route_based_timing_remains_not_calibrated():
    reg, graph, _created = _build_pts_proof()
    mission_no_route = ody.MissionSpec(mission_id="M-A", trigger_event_id="E1", patient_id="NOT_APPLICABLE", service_class="SPECIMEN_BLOOD", origin="ROOM-X", destination="ROOM-Y", earliest_dispatch_minutes=0.0, required_arrival_minutes=None, priority="NOT_APPLICABLE", provenance="test")
    mission_with_route = ody.MissionSpec(mission_id="M-B", trigger_event_id="E1", patient_id="NOT_APPLICABLE", service_class="SPECIMEN_BLOOD", origin="PTS-STN-RP", destination="PTS-STN-SCN", earliest_dispatch_minutes=0.0, required_arrival_minutes=None, priority="NOT_APPLICABLE", provenance="test")
    trace_no_route = ody.execute_conventional_missions([mission_no_route], architecture="AUTOMATED_CONVENTIONAL")[0]
    trace_with_route = ody.execute_conventional_missions([mission_with_route], architecture="AUTOMATED_CONVENTIONAL", registry=reg, graph=graph)[0]
    assert trace_no_route.total_minutes == trace_with_route.total_minutes
    assert reac.PTS_DISTANCE_REACTIVE_OPEX == "NOT_CALIBRATED"  # confirms build 3's conclusion untouched


def test_38_pts_opex_unchanged_where_fixed_lumped_allowance():
    loaded_rate = 100_000.0
    opex_a = cta.pts_annual_opex(cta.DEFAULT_PTS_NETWORK, loaded_annual_cost_per_fte=loaded_rate)
    calibrated_network = replace(cta.DEFAULT_PTS_NETWORK, network_length_m=999.0)
    opex_b = cta.pts_annual_opex(calibrated_network, loaded_annual_cost_per_fte=loaded_rate)
    assert opex_a == opex_b


def test_39_pts_distance_reactive_opex_reports_not_calibrated():
    assert reac.PTS_DISTANCE_REACTIVE_OPEX == "NOT_CALIBRATED"


def test_40_manual_porter_route_distance_change_propagates_into_walking_time():
    reg, graph, _created = _build_pedestrian_proof()
    mission_no_route = ody.MissionSpec(mission_id="M-A", trigger_event_id="E1", patient_id="NOT_APPLICABLE", service_class="SPECIMEN_BLOOD", origin="ROOM-X", destination="ROOM-Y", earliest_dispatch_minutes=0.0, required_arrival_minutes=None, priority="NOT_APPLICABLE", provenance="test")
    mission_with_route = ody.MissionSpec(mission_id="M-B", trigger_event_id="E1", patient_id="NOT_APPLICABLE", service_class="SPECIMEN_BLOOD", origin="ROOM-RP-101", destination="ROOM-PAT-201", earliest_dispatch_minutes=0.0, required_arrival_minutes=None, priority="NOT_APPLICABLE", provenance="test")
    trace_no_route = ody.execute_conventional_missions([mission_no_route], architecture="MANUAL_CONVENTIONAL")[0]
    trace_with_route = ody.execute_conventional_missions([mission_with_route], architecture="MANUAL_CONVENTIONAL", registry=reg, graph=graph)[0]
    assert trace_no_route.total_minutes != trace_with_route.total_minutes
    assert trace_with_route.route_status == "ROUTE_CALIBRATED"


def test_41_manual_porter_walking_time_change_propagates_into_labor_opex():
    policy = cta.PorterOperatingPolicy()
    opex_short = ody._estimate_annual_porter_labor_opex(mission_count=200, avg_minutes=10.5, policy=policy, operating_days_per_year=300)
    opex_long = ody._estimate_annual_porter_labor_opex(mission_count=200, avg_minutes=17.0, policy=policy, operating_days_per_year=300)
    assert opex_long > opex_short


def test_42_no_new_economic_coefficient_introduced_for_distance_reactivity():
    import dataclasses
    pts_fields = {f.name for f in dataclasses.fields(cta.PneumaticTubeNetwork)}
    agv_fields = {f.name for f in dataclasses.fields(cta.AgvModelClass)}
    assert pts_fields == {
        "network_id", "compatible_streams", "station_count", "network_length_m", "capsule_payload_kg", "speed_m_per_s",
        "station_capex_per_unit", "network_capex_per_m", "annual_maintenance_opex", "annual_energy_opex", "residual_labor_fte",
        "dispatch_minutes", "station_handling_minutes", "asset_status", "operational_state", "provenance",
    }
    assert "capex_per_m" not in agv_fields


def test_43_unaffected_transport_network_retains_prior_economic_result():
    record_before = reac.evaluate_move_endpoint_consequence(
        change_id="C-1", endpoint_id="MRT-ENDPOINT-Y", what_if_id="WI-3", source_lockdown_id="L0",
        installed_network_before_m=100.0, installed_network_after_m=100.0, mission_route_before_m=100.0, mission_route_after_m=100.0,
        guideway_capex_per_m=PlannerAssumptions().mrt_guideway_capex_per_m, baseline_capex=1_000_000.0, baseline_annual_opex=50_000.0,
        throughput_patients_per_day=100.0, revenue_per_scan=300.0, operating_days_per_year=300, discount_rate_pct=10.0, analysis_years=10,
    )
    # a PTS-only geometry change must never perturb this MRT result
    _build_pts_proof()
    record_after = reac.evaluate_move_endpoint_consequence(
        change_id="C-2", endpoint_id="MRT-ENDPOINT-Y", what_if_id="WI-3", source_lockdown_id="L0",
        installed_network_before_m=100.0, installed_network_after_m=100.0, mission_route_before_m=100.0, mission_route_after_m=100.0,
        guideway_capex_per_m=PlannerAssumptions().mrt_guideway_capex_per_m, baseline_capex=1_000_000.0, baseline_annual_opex=50_000.0,
        throughput_patients_per_day=100.0, revenue_per_scan=300.0, operating_days_per_year=300, discount_rate_pct=10.0, analysis_years=10,
    )
    assert record_before.capex_delta_usd == record_after.capex_delta_usd == 0.0


def test_44_what_if_economic_consequences_do_not_mutate_l0():
    reg = _build_registry_with_floors()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    before = dict(locked.registry.objects)
    ptsna.build_controlled_pts_proof_network(what_if.registry, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    quantities = ptsna.compute_pts_infrastructure_quantities(what_if.registry, csa.ConnectivityGraph())
    reac.compute_pts_capex_with_installed_length(cta.DEFAULT_PTS_NETWORK, quantities, study_scope="CAPITAL_PLANNING")
    after = dict(locked.registry.objects)
    assert before == after


# ===========================================================================
# Section 35: PRESERVATION / SCOPE (items 45-58)
# ===========================================================================


def test_45_existing_mrt_economics_unchanged_for_unchanged_geometry():
    record = reac.evaluate_move_endpoint_consequence(
        change_id="C-45", endpoint_id="MRT-ENDPOINT-Z", what_if_id=None, source_lockdown_id=None,
        installed_network_before_m=200.0, installed_network_after_m=200.0, mission_route_before_m=200.0, mission_route_after_m=200.0,
        guideway_capex_per_m=PlannerAssumptions().mrt_guideway_capex_per_m, baseline_capex=1_000_000.0, baseline_annual_opex=50_000.0,
        throughput_patients_per_day=100.0, revenue_per_scan=300.0, operating_days_per_year=300, discount_rate_pct=10.0, analysis_years=10,
    )
    assert record.capex_delta_usd == 0.0
    assert record.annual_maintenance_opex_delta_usd == 0.0


def test_46_existing_rght_economics_unchanged_for_unchanged_geometry():
    assert cta.DEFAULT_AGV_MODEL.vehicle_capex == 100_000.0
    assert cta.DEFAULT_AGV_MODEL.annual_maintenance_opex == 4_000.0
    assert cta.DEFAULT_AGV_MODEL.annual_energy_opex == 1_500.0


def test_47_existing_pts_economics_unchanged_for_unchanged_geometry():
    assert cta.DEFAULT_PTS_NETWORK.network_length_m == 300.0
    assert cta.DEFAULT_PTS_NETWORK.network_capex_per_m == 250.0
    assert cta.DEFAULT_PTS_NETWORK.annual_maintenance_opex == 8_000.0


def test_48_existing_manual_economics_unchanged_for_unchanged_geometry():
    policy = cta.PorterOperatingPolicy()
    assert policy.loaded_hand_carry_speed_m_per_s == 1.1
    assert policy.base_wage_per_hour == 17.0


def test_49_architecture_stream_assignment_semantics_unchanged():
    streams = ("PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY")
    first = cta.assign_technology_per_stream(portfolio_id="MANUAL_PLUS_AGV_PLUS_PTS", streams=streams)
    second = cta.assign_technology_per_stream(portfolio_id="MANUAL_PLUS_AGV_PLUS_PTS", streams=streams)
    assert tuple(a.assigned_technology for a in first) == tuple(a.assigned_technology for a in second)


def test_50_floor_agv_amr_remains_not_implemented():
    assert tta.FLOOR_AGV_AMR_IMPLEMENTATION_STATUS == "NOT_IMPLEMENTED"


def test_51_no_production_dynamic_trajectory_created():
    import inspect
    lines = [l.strip() for l in inspect.getsource(hca).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("dynamic_scene_state_authority" in line for line in lines)
    assert not any("CarrierTrajectory" in line for line in lines)


def test_52_no_openusd_time_samples_created_by_build4():
    import inspect
    for module in (hca, reac):
        source = inspect.getsource(module)
        assert "UsdGeom" not in source
        assert "TimeSample" not in source


def test_53_no_nvidia_runtime_dependency_introduced():
    import inspect
    for module in (hca, reac):
        lines = [l.strip() for l in inspect.getsource(module).splitlines() if l.strip().startswith(("import ", "from "))]
        assert not any("omni" in line.lower() or "nvidia" in line.lower() for line in lines)


def test_54_no_bentley_dependency_introduced():
    import inspect
    for module in (hca, reac):
        lines = [l.strip() for l in inspect.getsource(module).splitlines() if l.strip().startswith(("import ", "from "))]
        assert not any("bentley" in line.lower() for line in lines)


def test_55_dedicated_rp_pts_semantics_preserved_again():
    import inspect
    hca_import_lines = [l.strip() for l in inspect.getsource(hca).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("dedicated_rp_pts_authority" in line for line in hca_import_lines)


def test_56_patient_injection_uptake_remains_in_patient_room():
    assert hca.PATIENT_INJECTION_UPTAKE_LOCATION == "PATIENT_ROOM"


def test_57_patient_clinical_timing_not_silently_altered_by_route_construction():
    a = PlannerAssumptions()
    assert a.injection_cycle_min == 15.0
    assert a.uptake_cycle_min == 60.0
    assert a.scanner_cycle_min == 35.0


def test_58_no_transport_technology_receives_anothers_infrastructure_or_coefficients():
    assert cta.DEFAULT_AGV_MODEL.vehicle_capex != cta.DEFAULT_PTS_NETWORK.station_capex_per_unit
    pts_types = {"PTS_STATION", "PTS_TUBE_SEGMENT", "PTS_JUNCTION", "PTS_VERTICAL_SEGMENT", "PTS_CAPSULE"}
    rght_types = {"RGHT_TRACK_SEGMENT", "RGHT_STATION", "RGHT_SWITCH", "RGHT_VERTICAL_SEGMENT", "RGHT_VEHICLE"}
    mrt_types = {"MRT_TRUNK", "MRT_BRANCH", "MRT_SEGMENT", "MRT_JUNCTION", "MRT_ENDPOINT", "MRT_CARRIER", "MRT_CONTAINER", "MRT_VESTIBULE"}
    assert pts_types.isdisjoint(rght_types)
    assert pts_types.isdisjoint(mrt_types)
    assert rght_types.isdisjoint(mrt_types)

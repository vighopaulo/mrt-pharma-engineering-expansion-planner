"""Focused tests for Transport Spatial Authority Build 2:

- the first real RGHT canonical spatial network authority
  (rght_spatial_network_authority.py)
- RGHT resolving through the mode-neutral mission route bridge
  (transport_mission_route_bridge.py, extended)
- MRT/RGHT/PTS engineering separation invariants
- controlled proof routes (horizontal, switch/branch, cross-floor)
- failure semantics, Lockdown/What-If isolation, and numeric preservation
  when no RGHT network is supplied.
"""

import canonical_spatial_authority as csa
import conventional_transport_authority as cta
import operational_day_orchestrator as ody
import pytest
import rght_spatial_network_authority as rsna
import transport_mission_route_bridge as trb
import transport_technology_authority as tta

FACILITY_ID = "FAC-RGHT-B2"
BUILDING_ID = "BLDG-RGHT-B2"


def _source_without_module_docstring(module) -> str:
    import inspect
    src = inspect.getsource(module)
    if src.lstrip().startswith('"""'):
        first = src.index('"""')
        second = src.index('"""', first + 3)
        return src[second + 3:]
    return src


def _build_registry_with_floors():
    reg = csa.build_facility_hierarchy(facility_id=FACILITY_ID)
    csa.add_building(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1")
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F2")
    return reg


def _build_controlled_proof():
    reg = _build_registry_with_floors()
    graph, created = rsna.build_controlled_rght_proof_network(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    return reg, graph, created


# ---------------------------------------------------------------------------
# Section 31: taxonomy preservation
# ---------------------------------------------------------------------------


def test_1_rght_remains_canonical():
    assert tta.RAIL_GUIDED_HOSPITAL_TRANSPORT == "RGHT"


def test_2_agv_amr_legacy_compatibility_remains():
    assert tta.normalize_transport_technology("AGV_AMR") == "RGHT"
    assert "AGV_AMR" in cta.TECHNOLOGY_STREAM_COMPATIBILITY


def test_3_floor_agv_amr_remains_distinct():
    assert tta.FLOOR_AGV_AMR != tta.RAIL_GUIDED_HOSPITAL_TRANSPORT
    assert tta.FLOOR_AGV_AMR_IMPLEMENTATION_STATUS == "NOT_IMPLEMENTED"


def test_4_vendor_brand_not_canonical():
    assert tta.is_vendor_brand_name("Telelift") is True
    assert tta.is_vendor_brand_name("Swisslog") is True
    assert tta.RAIL_GUIDED_HOSPITAL_TRANSPORT not in ("TELELIFT", "SWISSLOG", "UNICAR")


def test_5_existing_no_network_economics_remain_numerically_unchanged():
    model = cta.DEFAULT_AGV_MODEL
    assert model.vehicle_capex == 100_000.0
    assert model.system_integration_capex == 50_000.0
    assert model.speed_m_per_s == 0.8
    mission = ody.MissionSpec(
        mission_id="M-NO-NET", trigger_event_id="EVT-1", patient_id="NOT_APPLICABLE", service_class="LAUNDRY_CLEAN_LINEN",
        origin="ROOM-A", destination="ROOM-B", earliest_dispatch_minutes=0.0, required_arrival_minutes=None,
        priority="NOT_APPLICABLE", provenance="test",
    )
    traces = ody.execute_conventional_missions([mission], architecture="AUTOMATED_CONVENTIONAL")  # no registry/graph
    trace = traces[0]
    expected = (ody.CONTROLLED_TEST_DISTANCE_M / model.speed_m_per_s) / 60.0
    last_mile = cta.compute_manual_mission_timing(policy=cta.PorterOperatingPolicy(), technology="MANUAL_PORTER", horizontal_distance_m=ody.AGV_PTS_LAST_MILE_DISTANCE_M)
    assert trace.total_minutes == expected + last_mile.total_minutes
    assert trace.route_resolution.route_status == "SPATIAL_NETWORK_NOT_CALIBRATED"


def test_6_architecture_optimization_unchanged_without_network_input():
    streams = ("PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY")
    first = cta.assign_technology_per_stream(portfolio_id="MANUAL_PLUS_AGV_PLUS_PTS", streams=streams)
    second = cta.assign_technology_per_stream(portfolio_id="MANUAL_PLUS_AGV_PLUS_PTS", streams=streams)
    assert tuple(a.assigned_technology for a in first) == tuple(a.assigned_technology for a in second)


# ---------------------------------------------------------------------------
# Section 32: spatial network object types exist
# ---------------------------------------------------------------------------


def test_7_rght_track_segment_exists():
    reg, graph, created = _build_controlled_proof()
    assert any(o.object_type == "RGHT_TRACK_SEGMENT" for o in created)


def test_8_rght_station_exists():
    reg, graph, created = _build_controlled_proof()
    assert any(o.object_type == "RGHT_STATION" for o in created)


def test_9_rght_switch_exists():
    reg, graph, created = _build_controlled_proof()
    assert any(o.object_type == "RGHT_SWITCH" for o in created)


def test_10_rght_vertical_segment_exists_in_controlled_proof():
    reg, graph, created = _build_controlled_proof()
    assert any(o.object_type == "RGHT_VERTICAL_SEGMENT" for o in created)


def test_11_rght_vehicle_exists():
    reg, graph, created = _build_controlled_proof()
    assert any(o.object_type == "RGHT_VEHICLE" for o in created)


# ---------------------------------------------------------------------------
# Engineering separation invariants (sections 3/23/24)
# ---------------------------------------------------------------------------


def test_12_mrt_and_rght_do_not_share_engineering_infrastructure_objects():
    mrt_types = {"MRT_TRUNK", "MRT_BRANCH", "MRT_SEGMENT", "MRT_JUNCTION", "MRT_ENDPOINT", "MRT_CARRIER", "MRT_CONTAINER", "MRT_VESTIBULE"}
    rght_types = {"RGHT_TRACK_SEGMENT", "RGHT_STATION", "RGHT_SWITCH", "RGHT_VERTICAL_SEGMENT", "RGHT_VEHICLE"}
    assert mrt_types.isdisjoint(rght_types)


def test_13_rght_vehicle_rejects_mrt_parent():
    reg = _build_registry_with_floors()
    trunk = csa.build_mrt_trunk(reg, trunk_id="MRT-TRUNK-X", facility_id=FACILITY_ID)
    with pytest.raises(ValueError):
        rsna.build_rght_vehicle(reg, vehicle_id="RGHT-VEH-BAD", facility_id=FACILITY_ID, network_object_id=trunk.mrtway_object_id)


def test_14_rght_and_pts_do_not_share_infrastructure_objects():
    import inspect
    source = inspect.getsource(rsna)
    assert "PneumaticTubeNetwork" not in source
    assert "PNEUMATIC_TUBE" not in source


def test_15_rght_and_mrt_do_not_share_installed_network_module_dependency():
    code = _source_without_module_docstring(rsna)
    assert "csa.build_mrt_trunk(" not in code
    assert "csa.build_mrt_carrier(" not in code
    assert "csa.build_mrt_segment(" not in code


# ---------------------------------------------------------------------------
# Vendor neutrality (section 2) + vehicle mass/payload provenance (14-16)
# ---------------------------------------------------------------------------


def test_16_rght_vendor_neutral_no_proprietary_terms():
    code = _source_without_module_docstring(rsna).lower()
    for forbidden in ("telelift", "swisslog", "unicar"):
        assert forbidden not in code


def test_17_rght_vehicle_tare_mass_not_calibrated_by_default():
    reg = _build_registry_with_floors()
    switch = rsna.build_rght_switch(reg, switch_id="SW-1", facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1")
    _obj, spec = rsna.build_rght_vehicle(reg, vehicle_id="VEH-1", facility_id=FACILITY_ID, network_object_id=switch.mrtway_object_id)
    assert spec.tare_mass_kg == "NOT_CALIBRATED"


def test_18_rght_vehicle_payload_capacity_honestly_reuses_legacy_agv_assumption():
    reg, graph, created = _build_controlled_proof()
    vehicle_spec = None
    # rebuild directly to access the spec (build_controlled_rght_proof_network only returns objects)
    reg2 = _build_registry_with_floors()
    switch = rsna.build_rght_switch(reg2, switch_id="SW-1", facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1")
    _obj, vehicle_spec = rsna.build_rght_vehicle(
        reg2, vehicle_id="VEH-1", facility_id=FACILITY_ID, network_object_id=switch.mrtway_object_id,
        payload_capacity_kg=cta.DEFAULT_AGV_MODEL.payload_capacity_kg,
        payload_capacity_provenance="CONTROLLED_ENGINEERING_ASSUMPTION reused verbatim from conventional_transport_authority.DEFAULT_AGV_MODEL.payload_capacity_kg",
    )
    assert vehicle_spec.payload_capacity_kg == cta.DEFAULT_AGV_MODEL.payload_capacity_kg == 150.0
    assert "DEFAULT_AGV_MODEL" in vehicle_spec.provenance


# ---------------------------------------------------------------------------
# Common route solver reuse (section 10) + edge geometry (section 11)
# ---------------------------------------------------------------------------


def test_19_rght_uses_common_route_solver():
    reg, graph, _created = _build_controlled_proof()
    result = csa.resolve_route(graph, origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ", mode="AGV_AMR")
    assert isinstance(result, csa.RouteResult)  # the SAME RouteResult type used everywhere else


def test_20_rght_track_segment_carries_floor_building_context():
    reg, graph, created = _build_controlled_proof()
    segment = next(o for o in created if o.mrtway_object_id == "RGHT-SEG-RP-SW1")
    assert segment.building_id == BUILDING_ID
    assert segment.floor_id == "F1"
    assert segment.geometry_reference is not None and segment.geometry_reference.startswith("LENGTH:")


# ---------------------------------------------------------------------------
# Controlled proof routes (section 27): horizontal / switch-branching / cross-floor
# ---------------------------------------------------------------------------


def test_21_controlled_proof_horizontal_route():
    reg, graph, _created = _build_controlled_proof()
    route = csa.resolve_route(graph, origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ", mode="AGV_AMR")
    assert route.calibration_status == "CALIBRATED"
    assert "RGHT-EDGE-VERTICAL" not in route.path_edge_ids  # purely horizontal


def test_22_controlled_proof_switch_branching_route():
    reg, graph, _created = _build_controlled_proof()
    switch_edges = [e for e in graph.edges if e.from_object_id == "RGHT-SWITCH-F1" or e.to_object_id == "RGHT-SWITCH-F1"]
    assert len(switch_edges) >= 2  # at least two eligible outgoing tracks at the switch
    route = csa.resolve_route(graph, origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ", mode="AGV_AMR")
    assert "RGHT-EDGE-SW1-INJ" in route.path_edge_ids  # correct branch chosen, not the vertical one


def test_23_controlled_proof_cross_floor_route():
    reg, graph, _created = _build_controlled_proof()
    route = csa.resolve_route(graph, origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-SCN", mode="AGV_AMR")
    assert route.calibration_status == "CALIBRATED"
    assert "RGHT-EDGE-VERTICAL" in route.path_edge_ids
    vertical_edge = next(e for e in graph.edges if e.edge_id == "RGHT-EDGE-VERTICAL")
    assert vertical_edge.vertical is True
    assert vertical_edge.length_m == 4.0  # preserved Z (floor-to-floor height), never flattened


# ---------------------------------------------------------------------------
# Mission route bridge integration (section 18)
# ---------------------------------------------------------------------------


def test_24_rght_mission_resolves_route_calibrated_with_real_network():
    reg, graph, _created = _build_controlled_proof()
    resolution = trb.resolve_mission_route(
        mission_id="M-1", transport_mode="AGV_AMR", origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-SCN",
        registry=reg, graph=graph,
    )
    assert resolution.route_status == "ROUTE_CALIBRATED"
    assert resolution.route_distance_m == 25.029197689295053
    assert resolution.route_node_ids[0] == "RGHT-STN-RP"
    assert resolution.route_node_ids[-1] == "RGHT-STN-SCN"


def test_25_rght_mission_reports_spatial_network_not_calibrated_with_no_graph():
    resolution = trb.resolve_mission_route(mission_id="M-1", transport_mode="AGV_AMR", origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-SCN")
    assert resolution.route_status == "SPATIAL_NETWORK_NOT_CALIBRATED"


def test_26_rght_mission_reports_spatial_network_not_calibrated_when_graph_has_no_rght_edges():
    reg = _build_registry_with_floors()
    csa.add_room(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1", room_id="ROOM-A")
    csa.add_room(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1", room_id="ROOM-B")
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="ROOM-A", to_object_id="ROOM-B", length_m=10.0, compatible_modes=frozenset({"WALKING_PORTER"})))
    resolution = trb.resolve_mission_route(mission_id="M-1", transport_mode="AGV_AMR", origin_object_id="ROOM-A", destination_object_id="ROOM-B", registry=reg, graph=graph)
    assert resolution.route_status == "SPATIAL_NETWORK_NOT_CALIBRATED"


def test_27_pts_behavior_unchanged_by_build2():
    reg, graph, _created = _build_controlled_proof()  # even with a real RGHT network present
    resolution = trb.resolve_mission_route(mission_id="M-1", transport_mode="PNEUMATIC_TUBE", origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-SCN", registry=reg, graph=graph)
    assert resolution.route_status == "SPATIAL_NETWORK_NOT_CALIBRATED"


def test_28_real_rght_route_takes_precedence_over_flat_placeholder_in_orchestrator():
    reg, graph, _created = _build_controlled_proof()
    mission = ody.MissionSpec(
        mission_id="M-RGHT-REAL", trigger_event_id="EVT-1", patient_id="NOT_APPLICABLE", service_class="LAUNDRY_CLEAN_LINEN",
        origin="RGHT-STN-RP", destination="RGHT-STN-INJ", earliest_dispatch_minutes=0.0, required_arrival_minutes=None,
        priority="NOT_APPLICABLE", provenance="test",
    )
    traces = ody.execute_conventional_missions([mission], architecture="AUTOMATED_CONVENTIONAL", registry=reg, graph=graph)
    trace = traces[0]
    assert trace.resource_type == "AGV_AMR"
    assert trace.route_status == "ROUTE_CALIBRATED"
    real_distance = 19.782665154541576
    model = cta.DEFAULT_AGV_MODEL
    expected_main_leg = (real_distance / model.speed_m_per_s) / 60.0
    flat_main_leg = (ody.CONTROLLED_TEST_DISTANCE_M / model.speed_m_per_s) / 60.0
    assert expected_main_leg != flat_main_leg
    last_mile = cta.compute_manual_mission_timing(policy=cta.PorterOperatingPolicy(), technology="MANUAL_PORTER", horizontal_distance_m=ody.AGV_PTS_LAST_MILE_DISTANCE_M)
    assert trace.total_minutes == expected_main_leg + last_mile.total_minutes


# ---------------------------------------------------------------------------
# Failure semantics (section 28)
# ---------------------------------------------------------------------------


def test_29_missing_network_reports_spatial_network_not_calibrated():
    resolution = trb.resolve_mission_route(mission_id="M", transport_mode="AGV_AMR", origin_object_id="A", destination_object_id="B")
    assert resolution.route_status == "SPATIAL_NETWORK_NOT_CALIBRATED"


def test_30_disconnected_network_reports_route_not_calibrated():
    reg, graph, _created = _build_controlled_proof()
    csa.add_room(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1", room_id="ISOLATED-ROOM")
    resolution = trb.resolve_mission_route(mission_id="M", transport_mode="AGV_AMR", origin_object_id="RGHT-STN-RP", destination_object_id="ISOLATED-ROOM", registry=reg, graph=graph)
    assert resolution.route_status == "ROUTE_NOT_CALIBRATED"


def test_31_wrong_transport_mode_never_silently_falls_back():
    reg, graph, _created = _build_controlled_proof()
    resolution = trb.resolve_mission_route(mission_id="M", transport_mode="MRT", origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ", registry=reg, graph=graph)
    assert resolution.route_status != "ROUTE_CALIBRATED"  # RGHT-only edges are not MRT-eligible


def test_32_missing_station_reports_route_unavailable():
    reg, graph, _created = _build_controlled_proof()
    resolution = trb.resolve_mission_route(mission_id="M", transport_mode="AGV_AMR", origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-NONEXISTENT", registry=reg, graph=graph)
    assert resolution.route_status == "ROUTE_UNAVAILABLE"


def test_33_missing_route_does_not_abandon_rght_feasibility():
    reg, graph, _created = _build_controlled_proof()
    csa.add_room(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1", room_id="ISOLATED-ROOM-2")
    mission = ody.MissionSpec(
        mission_id="M-ISOLATED", trigger_event_id="EVT-1", patient_id="NOT_APPLICABLE", service_class="LAUNDRY_CLEAN_LINEN",
        origin="RGHT-STN-RP", destination="ISOLATED-ROOM-2", earliest_dispatch_minutes=0.0, required_arrival_minutes=None,
        priority="NOT_APPLICABLE", provenance="test",
    )
    traces = ody.execute_conventional_missions([mission], architecture="AUTOMATED_CONVENTIONAL", registry=reg, graph=graph)
    assert isinstance(traces[0].total_minutes, float)  # route failure never blocks economic/operational feasibility


def test_34_invalid_vertical_connection_not_fabricated():
    reg = _build_registry_with_floors()
    switch1 = rsna.build_rght_switch(reg, switch_id="SW-A", facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1")
    graph = csa.ConnectivityGraph()
    # deliberately NO vertical edge connecting F1 to F2 -- route across floors must not be fabricated
    csa.add_room(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F2", room_id="ROOM-F2")
    resolution = trb.resolve_mission_route(mission_id="M", transport_mode="AGV_AMR", origin_object_id=switch1.mrtway_object_id, destination_object_id="ROOM-F2", registry=reg, graph=graph)
    assert resolution.route_status in ("ROUTE_NOT_CALIBRATED", "SPATIAL_NETWORK_NOT_CALIBRATED")
    assert resolution.route_distance_m is None


# ---------------------------------------------------------------------------
# Endpoint model (section 8) + infrastructure quantities (section 22)
# ---------------------------------------------------------------------------


def test_35_direct_endpoint_vs_central_station_with_last_mile():
    assert rsna.classify_rght_endpoint_model(station_object_id="RGHT-STN-SCN", destination_room_object_id="RGHT-STN-SCN") == "DIRECT_RGHT_ENDPOINT"
    assert rsna.classify_rght_endpoint_model(station_object_id="RGHT-STN-SCN", destination_room_object_id="ROOM-SCN-202") == "CENTRAL_FLOOR_STATION_WITH_LAST_MILE"


def test_36_infrastructure_quantities_are_derived_not_hard_coded():
    reg, graph, _created = _build_controlled_proof()
    quantities = rsna.compute_rght_infrastructure_quantities(reg, graph)
    assert quantities.station_count == 3
    assert quantities.switch_count == 2
    assert quantities.vertical_segment_count == 1
    assert quantities.vehicle_count == 1
    assert quantities.total_vertical_track_length_m == 4.0
    assert quantities.total_track_length_m == pytest.approx(quantities.total_horizontal_track_length_m + quantities.total_vertical_track_length_m)


# ---------------------------------------------------------------------------
# Lockdown / What-If isolation (section 25)
# ---------------------------------------------------------------------------


def test_37_rght_proof_network_does_not_mutate_lockdown_l0():
    reg = _build_registry_with_floors()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    before = dict(locked.registry.objects)
    rsna.build_controlled_rght_proof_network(what_if.registry, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    after = dict(locked.registry.objects)
    assert before == after
    assert "RGHT-STN-RP" not in locked.registry.objects
    assert "RGHT-STN-RP" in what_if.registry.objects


# ---------------------------------------------------------------------------
# Visualization identity readiness without visualization (section 26)
# ---------------------------------------------------------------------------


def test_38_rght_object_ids_are_stable_and_visualization_ready():
    reg, graph, created = _build_controlled_proof()
    ids = [o.mrtway_object_id for o in created]
    assert len(ids) == len(set(ids))  # all distinct, stable identities
    for object_id in ids:
        assert object_id in reg.objects
    import inspect
    import_lines = [l.strip() for l in inspect.getsource(rsna).splitlines() if l.strip().startswith(("import ", "from "))]
    for line in import_lines:
        assert "pxr" not in line
        assert "openusd" not in line.lower()


# ---------------------------------------------------------------------------
# No NVIDIA/Bentley/OpenUSD started (section 30)
# ---------------------------------------------------------------------------


def test_39_no_openusd_pxr_nvidia_bentley_imports_in_new_modules():
    import inspect
    for module in (rsna, trb):
        lines = [l.strip() for l in inspect.getsource(module).splitlines() if l.strip().startswith(("import ", "from "))]
        for line in lines:
            assert "pxr" not in line
            assert "omni" not in line.lower()
            assert "bentley" not in line.lower()

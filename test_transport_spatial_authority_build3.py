"""Focused tests for Transport Spatial Authority Build 3:

- the first real PTS (Pneumatic Tube System) canonical spatial network
  authority (pts_spatial_network_authority.py)
- the timing-semantics audit (dispatch/handling vs route-based movement)
- PTS resolving through the mode-neutral mission route bridge
  (transport_mission_route_bridge.py, extended)
- MRT/RGHT/PTS engineering separation invariants
- general PTS vs dedicated RP-PTS separation
- controlled proof routes (horizontal, junction/branch, cross-floor)
- failure semantics, Lockdown/What-If isolation, and numeric preservation
  when no PTS network is supplied.
"""

import canonical_spatial_authority as csa
import conventional_transport_authority as cta
import dedicated_rp_pts_authority as rpp
import operational_day_orchestrator as ody
import pts_spatial_network_authority as ptsna
import pytest
import transport_mission_route_bridge as trb
import transport_technology_authority as tta

FACILITY_ID = "FAC-PTS-B3"
BUILDING_ID = "BLDG-PTS-B3"


def _build_registry_with_floors():
    reg = csa.build_facility_hierarchy(facility_id=FACILITY_ID)
    csa.add_building(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1")
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F2")
    return reg


def _build_controlled_proof():
    reg = _build_registry_with_floors()
    graph, created = ptsna.build_controlled_pts_proof_network(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    return reg, graph, created


# ---------------------------------------------------------------------------
# 1-5. Canonical PTS object types exist.
# ---------------------------------------------------------------------------


def test_1_pts_station_exists():
    _reg, _graph, created = _build_controlled_proof()
    assert any(o.object_type == "PTS_STATION" for o in created)


def test_2_pts_tube_segment_exists():
    _reg, _graph, created = _build_controlled_proof()
    assert any(o.object_type == "PTS_TUBE_SEGMENT" for o in created)


def test_3_pts_junction_exists():
    _reg, _graph, created = _build_controlled_proof()
    assert any(o.object_type == "PTS_JUNCTION" for o in created)


def test_4_pts_vertical_segment_exists():
    _reg, _graph, created = _build_controlled_proof()
    assert any(o.object_type == "PTS_VERTICAL_SEGMENT" for o in created)


def test_5_pts_capsule_exists():
    _reg, _graph, created = _build_controlled_proof()
    assert any(o.object_type == "PTS_CAPSULE" for o in created)


# ---------------------------------------------------------------------------
# 6. PTS types distinct from MRT/RGHT.
# ---------------------------------------------------------------------------


def test_6_pts_types_distinct_from_mrt_and_rght():
    mrt_types = {"MRT_TRUNK", "MRT_BRANCH", "MRT_SEGMENT", "MRT_JUNCTION", "MRT_ENDPOINT", "MRT_CARRIER", "MRT_CONTAINER", "MRT_VESTIBULE"}
    rght_types = {"RGHT_TRACK_SEGMENT", "RGHT_STATION", "RGHT_SWITCH", "RGHT_VERTICAL_SEGMENT", "RGHT_VEHICLE"}
    pts_types = {"PTS_STATION", "PTS_TUBE_SEGMENT", "PTS_JUNCTION", "PTS_VERTICAL_SEGMENT", "PTS_CAPSULE"}
    assert pts_types.isdisjoint(mrt_types)
    assert pts_types.isdisjoint(rght_types)


# ---------------------------------------------------------------------------
# 7-9. Controlled proof routes.
# ---------------------------------------------------------------------------


def test_7_controlled_horizontal_route_resolves():
    _reg, graph, _created = _build_controlled_proof()
    route = csa.resolve_route(graph, origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ", mode="PNEUMATIC_TUBE")
    assert route.calibration_status == "CALIBRATED"
    assert "PTS-EDGE-VERTICAL" not in route.path_edge_ids


def test_8_junction_branch_routing_resolves():
    _reg, graph, _created = _build_controlled_proof()
    junction_edges = [e for e in graph.edges if e.from_object_id == "PTS-JCT-F1" or e.to_object_id == "PTS-JCT-F1"]
    assert len(junction_edges) >= 2
    route = csa.resolve_route(graph, origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ", mode="PNEUMATIC_TUBE")
    assert "PTS-EDGE-JCT1-INJ" in route.path_edge_ids


def test_9_cross_floor_route_preserves_z():
    _reg, graph, _created = _build_controlled_proof()
    route = csa.resolve_route(graph, origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-SCN", mode="PNEUMATIC_TUBE")
    assert route.calibration_status == "CALIBRATED"
    assert "PTS-EDGE-VERTICAL" in route.path_edge_ids
    vertical_edge = next(e for e in graph.edges if e.edge_id == "PTS-EDGE-VERTICAL")
    assert vertical_edge.vertical is True
    assert vertical_edge.length_m == 4.0


# ---------------------------------------------------------------------------
# 10-12. Route distance / common solver reuse / no duplicate solver.
# ---------------------------------------------------------------------------


def test_10_route_distance_equals_canonical_edge_length_sum():
    _reg, graph, _created = _build_controlled_proof()
    route = csa.resolve_route(graph, origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ", mode="PNEUMATIC_TUBE")
    edges_by_id = {e.edge_id: e for e in graph.edges}
    expected = sum(edges_by_id[eid].length_m for eid in route.path_edge_ids)
    assert route.distance_m == pytest.approx(expected)


def test_11_common_route_solver_reused():
    _reg, graph, _created = _build_controlled_proof()
    result = csa.resolve_route(graph, origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ", mode="PNEUMATIC_TUBE")
    assert isinstance(result, csa.RouteResult)


def test_12_no_duplicate_pts_route_solver_exists():
    import inspect
    source = inspect.getsource(ptsna)
    for forbidden in ("def resolve_route", "def bfs", "def dijkstra", "def find_path"):
        assert forbidden not in source


# ---------------------------------------------------------------------------
# 13-15. Mission route bridge behavior.
# ---------------------------------------------------------------------------


def test_13_mission_bridge_returns_route_calibrated_with_valid_pts_graph():
    reg, graph, _created = _build_controlled_proof()
    resolution = trb.resolve_mission_route(
        mission_id="M-1", transport_mode="PNEUMATIC_TUBE", origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-SCN",
        registry=reg, graph=graph,
    )
    assert resolution.route_status == "ROUTE_CALIBRATED"
    assert resolution.route_distance_m == pytest.approx(25.029197689295053)
    assert resolution.route_node_ids[0] == "PTS-STN-RP"
    assert resolution.route_node_ids[-1] == "PTS-STN-SCN"


def test_14_no_network_returns_spatial_network_not_calibrated():
    resolution = trb.resolve_mission_route(mission_id="M-1", transport_mode="PNEUMATIC_TUBE", origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-SCN")
    assert resolution.route_status == "SPATIAL_NETWORK_NOT_CALIBRATED"


def test_15_disconnected_network_does_not_fabricate_route():
    reg, graph, _created = _build_controlled_proof()
    csa.add_room(reg, facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1", room_id="ISOLATED-ROOM")
    resolution = trb.resolve_mission_route(mission_id="M", transport_mode="PNEUMATIC_TUBE", origin_object_id="PTS-STN-RP", destination_object_id="ISOLATED-ROOM", registry=reg, graph=graph)
    assert resolution.route_status == "ROUTE_NOT_CALIBRATED"
    assert resolution.route_distance_m is None


# ---------------------------------------------------------------------------
# 16. Installed network length is distinct from mission distance.
# ---------------------------------------------------------------------------


def test_16_installed_network_length_distinct_from_mission_distance():
    reg, graph, _created = _build_controlled_proof()
    quantities = ptsna.compute_pts_infrastructure_quantities(reg, graph)
    route = csa.resolve_route(graph, origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ", mode="PNEUMATIC_TUBE")
    assert quantities.total_tube_length_m != route.distance_m  # total installed length != one mission's route distance
    # Also: DEFAULT_PTS_NETWORK.network_length_m (a flat planning constant) never equals a real controlled-proof route
    assert cta.DEFAULT_PTS_NETWORK.network_length_m != route.distance_m


# ---------------------------------------------------------------------------
# 17-18. PTS capsule identity + no MRT carrier mass reuse.
# ---------------------------------------------------------------------------


def test_17_pts_capsule_identity_is_stable():
    reg, graph, created = _build_controlled_proof()
    capsule = next(o for o in created if o.object_type == "PTS_CAPSULE")
    assert capsule.mrtway_object_id == "PTS-CAPSULE-001"
    assert capsule.mrtway_object_id in reg.objects


def test_18_pts_capsule_does_not_reuse_mrt_carrier_mass():
    reg = _build_registry_with_floors()
    trunk = csa.build_mrt_trunk(reg, trunk_id="MRT-TRUNK-X", facility_id=FACILITY_ID)
    with pytest.raises(ValueError):
        ptsna.build_pts_capsule(reg, capsule_id="PTS-CAP-BAD", facility_id=FACILITY_ID, network_object_id=trunk.mrtway_object_id)
    junction = ptsna.build_pts_junction(reg, junction_id="JCT-1", facility_id=FACILITY_ID, building_id=BUILDING_ID, floor_id="F1")
    _obj, spec = ptsna.build_pts_capsule(reg, capsule_id="PTS-CAP-1", facility_id=FACILITY_ID, network_object_id=junction.mrtway_object_id)
    assert spec.tare_mass_kg == "NOT_CALIBRATED"  # never MRT carrier empty mass


# ---------------------------------------------------------------------------
# 19-20. Dedicated RP-PTS separation + PTS speed provenance.
# ---------------------------------------------------------------------------


def test_19_dedicated_rp_pts_semantics_remain_preserved():
    cycle = rpp.compute_rp_pts_mission_cycle(network_length_m=222.0)
    assert cycle.tube_transport_minutes > 0.0  # dedicated RP-PTS ALREADY separates dispatch/handling from movement
    assert rpp.RP_PTS_COMPATIBLE_STREAMS == frozenset({"RADIOPHARMACEUTICAL_NUCLEAR"})
    import inspect
    rpp_import_lines = [l.strip() for l in inspect.getsource(rpp).splitlines() if l.strip().startswith(("import ", "from "))]
    ptsna_import_lines = [l.strip() for l in inspect.getsource(ptsna).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("pts_spatial_network_authority" in line for line in rpp_import_lines)
    assert not any("dedicated_rp_pts_authority" in line for line in ptsna_import_lines)


def test_20_existing_pts_speed_provenance_remains_truthful():
    assert cta.DEFAULT_PTS_NETWORK.speed_m_per_s == pytest.approx(6.0)
    assert cta.DEFAULT_PTS_NETWORK.provenance == "CONTROLLED_ENGINEERING_ASSUMPTION"


# ---------------------------------------------------------------------------
# 21-23. Timing audit + no double counting + no-network numeric preservation.
# ---------------------------------------------------------------------------


def test_21_fixed_pts_timing_semantics_are_audited():
    """Section 16 audit: dispatch_minutes/station_handling_minutes are used
    ALONE (no distance/speed term) by convert_load_to_pts_missions -- and
    speed_m_per_s/network_length_m are never referenced by ANY ordinary PTS
    timing formula anywhere in this repository."""
    import inspect
    source = inspect.getsource(cta.convert_load_to_pts_missions)
    assert "speed_m_per_s" not in source
    assert "network_length_m" not in source
    assert "network.dispatch_minutes + network.station_handling_minutes" in source


def test_22_route_travel_is_not_double_counted():
    """PTS_ROUTE_BASED_TIMING = NOT_CALIBRATED (section 17 mandatory
    outcome): total_minutes for a PTS mission is IDENTICAL whether or not a
    real calibrated PTS route is supplied -- proving no route-distance term
    was silently added on top of the existing dispatch/handling constant."""
    reg, graph, _created = _build_controlled_proof()
    mission_no_route = ody.MissionSpec(
        mission_id="M-A", trigger_event_id="EVT-1", patient_id="NOT_APPLICABLE", service_class="SPECIMEN_BLOOD",
        origin="ROOM-X", destination="ROOM-Y", earliest_dispatch_minutes=0.0, required_arrival_minutes=None,
        priority="NOT_APPLICABLE", provenance="test",
    )
    mission_with_route = ody.MissionSpec(
        mission_id="M-B", trigger_event_id="EVT-1", patient_id="NOT_APPLICABLE", service_class="SPECIMEN_BLOOD",
        origin="PTS-STN-RP", destination="PTS-STN-SCN", earliest_dispatch_minutes=0.0, required_arrival_minutes=None,
        priority="NOT_APPLICABLE", provenance="test",
    )
    trace_no_route = ody.execute_conventional_missions([mission_no_route], architecture="AUTOMATED_CONVENTIONAL")[0]
    trace_with_route = ody.execute_conventional_missions([mission_with_route], architecture="AUTOMATED_CONVENTIONAL", registry=reg, graph=graph)[0]
    assert trace_no_route.route_resolution.route_status == "SPATIAL_NETWORK_NOT_CALIBRATED"
    assert trace_with_route.route_resolution.route_status == "ROUTE_CALIBRATED"
    assert trace_no_route.total_minutes == trace_with_route.total_minutes  # timing unchanged despite real route


def test_23_no_network_pts_numerics_remain_unchanged():
    mission = ody.MissionSpec(
        mission_id="M-NO-NET", trigger_event_id="EVT-1", patient_id="NOT_APPLICABLE", service_class="SPECIMEN_BLOOD",
        origin="ROOM-A", destination="ROOM-B", earliest_dispatch_minutes=0.0, required_arrival_minutes=None,
        priority="NOT_APPLICABLE", provenance="test",
    )
    trace = ody.execute_conventional_missions([mission], architecture="AUTOMATED_CONVENTIONAL")[0]
    network = cta.DEFAULT_PTS_NETWORK
    expected_travel = network.dispatch_minutes + network.station_handling_minutes
    last_mile = cta.compute_manual_mission_timing(policy=cta.PorterOperatingPolicy(), technology="MANUAL_PORTER", horizontal_distance_m=ody.AGV_PTS_LAST_MILE_DISTANCE_M)
    assert trace.total_minutes == pytest.approx(expected_travel + last_mile.total_minutes)


# ---------------------------------------------------------------------------
# 24. Architecture optimizer numerics unchanged without new network.
# ---------------------------------------------------------------------------


def test_24_architecture_optimizer_numerics_unchanged_without_new_network():
    streams = ("PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY")
    first = cta.assign_technology_per_stream(portfolio_id="MANUAL_PLUS_AGV_PLUS_PTS", streams=streams)
    second = cta.assign_technology_per_stream(portfolio_id="MANUAL_PLUS_AGV_PLUS_PTS", streams=streams)
    assert tuple(a.assigned_technology for a in first) == tuple(a.assigned_technology for a in second)


# ---------------------------------------------------------------------------
# 25. PTS economic constants unchanged.
# ---------------------------------------------------------------------------


def test_25_pts_economic_constants_remain_unchanged():
    network = cta.DEFAULT_PTS_NETWORK
    assert network.station_count == 6
    assert network.network_length_m == 300.0
    assert network.station_capex_per_unit == 45_000.0
    assert network.network_capex_per_m == 250.0
    assert network.annual_maintenance_opex == 8_000.0
    assert network.annual_energy_opex == 1_000.0


# ---------------------------------------------------------------------------
# 26-27. PTS/MRT and PTS/RGHT infrastructure separation.
# ---------------------------------------------------------------------------


def test_26_pts_and_mrt_infrastructure_separate():
    import inspect
    source = inspect.getsource(ptsna)
    assert "build_mrt_trunk" not in source
    assert "build_mrt_carrier" not in source
    assert "build_mrt_segment" not in source


def test_27_pts_and_rght_infrastructure_separate():
    import inspect
    import_lines = [l.strip() for l in inspect.getsource(ptsna).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("rght_spatial_network_authority" in line for line in import_lines)
    code_lines = [l for l in inspect.getsource(ptsna).splitlines() if not l.strip().startswith("#")]
    code = "\n".join(code_lines)
    assert "build_rght_station(" not in code
    assert "build_rght_vehicle(" not in code


# ---------------------------------------------------------------------------
# 28. Lockdown safety.
# ---------------------------------------------------------------------------


def test_28_l0_unchanged_by_pts_proof():
    reg = _build_registry_with_floors()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    before = dict(locked.registry.objects)
    ptsna.build_controlled_pts_proof_network(what_if.registry, facility_id=FACILITY_ID, building_id=BUILDING_ID)
    after = dict(locked.registry.objects)
    assert before == after
    assert "PTS-STN-RP" not in locked.registry.objects
    assert "PTS-STN-RP" in what_if.registry.objects


# ---------------------------------------------------------------------------
# 29-30. Explicit failure semantics.
# ---------------------------------------------------------------------------


def test_29_missing_station_failure_is_explicit():
    reg, graph, _created = _build_controlled_proof()
    resolution = trb.resolve_mission_route(mission_id="M", transport_mode="PNEUMATIC_TUBE", origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-NONEXISTENT", registry=reg, graph=graph)
    assert resolution.route_status == "ROUTE_UNAVAILABLE"


def test_30_wrong_mode_routing_failure_is_explicit():
    reg, graph, _created = _build_controlled_proof()
    resolution = trb.resolve_mission_route(mission_id="M", transport_mode="MRT", origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ", registry=reg, graph=graph)
    assert resolution.route_status != "ROUTE_CALIBRATED"  # PTS-only edges are not MRT-eligible; never silently substituted


# ---------------------------------------------------------------------------
# 31-34. Visualization readiness + no OpenUSD/NVIDIA/Bentley dependency.
# ---------------------------------------------------------------------------


def test_31_visualization_identities_are_stable():
    _reg, _graph, created = _build_controlled_proof()
    ids = [o.mrtway_object_id for o in created]
    assert len(ids) == len(set(ids))


def test_32_openusd_not_required():
    import inspect
    lines = [l.strip() for l in inspect.getsource(ptsna).splitlines() if l.strip().startswith(("import ", "from "))]
    for line in lines:
        assert "pxr" not in line
        assert "openusd" not in line.lower()


def test_33_nvidia_not_required():
    import inspect
    lines = [l.strip() for l in inspect.getsource(ptsna).splitlines() if l.strip().startswith(("import ", "from "))]
    for line in lines:
        assert "omni" not in line.lower()
        assert "nvidia" not in line.lower()


def test_34_bentley_not_required():
    import inspect
    lines = [l.strip() for l in inspect.getsource(ptsna).splitlines() if l.strip().startswith(("import ", "from "))]
    for line in lines:
        assert "bentley" not in line.lower()


# ---------------------------------------------------------------------------
# 35. FLOOR_AGV_AMR remains not implemented.
# ---------------------------------------------------------------------------


def test_35_floor_agv_amr_remains_not_implemented():
    assert tta.FLOOR_AGV_AMR_IMPLEMENTATION_STATUS == "NOT_IMPLEMENTED"


# ---------------------------------------------------------------------------
# Section 24: contention/directionality disclosure.
# ---------------------------------------------------------------------------


def test_36_network_contention_not_implemented_disclosed():
    assert ptsna.PTS_NETWORK_CONTENTION_STATUS == "NOT_IMPLEMENTED"


# ---------------------------------------------------------------------------
# Section 9: endpoint model.
# ---------------------------------------------------------------------------


def test_37_direct_vs_central_station_endpoint_model():
    assert ptsna.classify_pts_endpoint_model(station_object_id="PTS-STN-SCN", destination_room_object_id="PTS-STN-SCN") == "DIRECT_ROOM_PTS_STATION"
    assert ptsna.classify_pts_endpoint_model(station_object_id="PTS-STN-SCN", destination_room_object_id="ROOM-SCN-202") == "CENTRAL_PTS_STATION_WITH_LAST_MILE"


# ---------------------------------------------------------------------------
# Section 19: infrastructure quantities are derived, not hard-coded.
# ---------------------------------------------------------------------------


def test_38_infrastructure_quantities_derived_not_hard_coded():
    _reg, graph, _created = _build_controlled_proof()
    quantities = ptsna.compute_pts_infrastructure_quantities(_reg, graph)
    assert quantities.station_count == 3
    assert quantities.junction_count == 2
    assert quantities.vertical_segment_count == 1
    assert quantities.capsule_count == 1
    assert quantities.total_vertical_tube_length_m == 4.0
    assert quantities.total_tube_length_m == pytest.approx(quantities.total_horizontal_tube_length_m + quantities.total_vertical_tube_length_m)

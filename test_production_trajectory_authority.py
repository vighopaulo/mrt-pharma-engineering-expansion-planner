"""Focused tests for Production Trajectory Build 1: Unified Moving-Entity
Trajectory Authority (`production_trajectory_authority.py`).

Covers: MRT trajectory built from the REAL ordered route (never the flat
300m placeholder), RGHT's own distinct network/speed, PTS's
spatial-path-vs-time-position distinction (never fake uniform motion),
porter/patient pedestrian trajectories (never straight-line-through-walls,
never conflated identities), the unified `resolve_entity_state_at_time`
boundary semantics, distance/time conservation, the OpenUSD bridge
(`to_dynamic_object_trajectory`), governance/no-mutation/no-vendor-import
invariants, and stable moving-entity identity.
"""

import inspect

import canonical_spatial_authority as csa
import conventional_transport_authority as cta
import dynamic_scene_state_authority as dss
import human_circulation_authority as hca
import mrt_service_class_authority as msc
import production_trajectory_authority as pta
import pts_spatial_network_authority as ptsna
import pytest
import rght_spatial_network_authority as rghtna


# ===========================================================================
# Fixtures / builders
# ===========================================================================


def _mrt_registry_and_graph():
    facility_id = "FAC-MRT-TEST"
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    graph, created = pta.build_controlled_mrt_proof_network(reg, facility_id=facility_id)
    return reg, graph, created, facility_id


def _rght_registry_and_graph():
    facility_id, building_id = "FAC-RGHT-TEST", "BLDG-RGHT-TEST"
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.add_building(reg, facility_id=facility_id, building_id=building_id)
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F1")
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F2")
    graph, created = rghtna.build_controlled_rght_proof_network(reg, facility_id=facility_id, building_id=building_id)
    return reg, graph, created


def _pts_registry_and_graph():
    facility_id, building_id = "FAC-PTS-TEST", "BLDG-PTS-TEST"
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.add_building(reg, facility_id=facility_id, building_id=building_id)
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F1")
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F2")
    graph, created = ptsna.build_controlled_pts_proof_network(reg, facility_id=facility_id, building_id=building_id)
    return reg, graph, created


def _source_without_module_docstring(module) -> str:
    src = inspect.getsource(module)
    if src.lstrip().startswith('"""'):
        first = src.index('"""')
        second = src.index('"""', first + 3)
        return src[second + 3:]
    return src


def _human_registry_and_graph():
    facility_id, building_id = "FAC-HUM-TEST", "BLDG-HUM-TEST"
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.add_building(reg, facility_id=facility_id, building_id=building_id)
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F1")
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F2")
    graph, created = hca.build_controlled_pedestrian_network(reg, facility_id=facility_id, building_id=building_id)
    return reg, graph, created


def _build_mrt_trajectory():
    reg, graph, _created, _fid = _mrt_registry_and_graph()
    route, mission = pta.resolve_mrt_route_and_build_mission(
        graph, mission_id="M-MRT-1", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN", start_minutes=0.0,
    )
    traj = pta.build_mrt_trajectory(
        reg, graph, mission=mission, mrtway_object_id="MRT-CARRIER-001",
        origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN",
    )
    return reg, graph, route, mission, traj


# ===========================================================================
# Section 1/3: governance / time unit / no vendor dependency
# ===========================================================================


def test_1_time_unit_reused_verbatim():
    assert pta.PRODUCTION_TRAJECTORY_TIME_UNIT == "MINUTES"
    assert pta.PRODUCTION_TRAJECTORY_TIME_UNIT == dss.MRT_SIMULATION_TIME_UNIT


def test_2_requires_flags_are_all_no():
    assert pta.PRODUCTION_TRAJECTORY_REQUIRES_OPENUSD is False
    assert pta.PRODUCTION_TRAJECTORY_REQUIRES_BENTLEY is False
    assert pta.PRODUCTION_TRAJECTORY_REQUIRES_NVIDIA is False


def test_3_no_vendor_imports():
    lines = [l.strip() for l in inspect.getsource(pta).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("pxr" in l.lower() or "omni" in l.lower() or "bentley" in l.lower() for l in lines)


def test_4_entity_type_support_flags():
    assert pta.MRT_TRAJECTORY_SUPPORTED is True
    assert pta.RGHT_TRAJECTORY_SUPPORTED is True
    assert pta.PTS_TRAJECTORY_SUPPORTED == "GEOMETRY_READY_TIMING_SUBJECT_TO_EXISTING_CALIBRATION"
    assert pta.PORTER_TRAJECTORY_SUPPORTED is True
    assert pta.PATIENT_TRAJECTORY_SUPPORTED is True
    assert pta.FLOOR_AGV_AMR_IMPLEMENTED is False


# ===========================================================================
# Section 7: MRT trajectory -- real ordered route, real speed authority.
# ===========================================================================


def test_5_mrt_route_length_is_not_the_flat_300m_placeholder():
    _reg, _graph, route, mission, _traj = _build_mrt_trajectory()
    assert mission.route_length_m == route.distance_m
    assert mission.route_length_m != 300.0


def test_6_mrt_trajectory_uses_existing_speed_authority():
    _reg, _graph, _route, mission, traj = _build_mrt_trajectory()
    speed = msc.mission_effective_speed(mission)
    assert isinstance(speed, float)
    expected_duration = mission.route_length_m / speed / 60.0
    assert traj.duration_minutes == pytest.approx(expected_duration)


def test_7_mrt_trajectory_preserves_l_shaped_route_turn():
    _reg, _graph, _route, _mission, traj = _build_mrt_trajectory()
    xs = [s.x_m for s in traj.samples]
    ys = [s.y_m for s in traj.samples]
    assert xs[0] != xs[-1]  # X changes (trunk direction)
    assert ys[0] != ys[-1]  # Y also changes (branch direction) -- proves the "L", not a straight line
    assert len(set(xs)) > 1 and len(set(ys)) > 1


def test_8_mrt_trajectory_start_intermediate_end_proof():
    _reg, _graph, _route, _mission, traj = _build_mrt_trajectory()
    assert len(traj.samples) >= 3
    start, end = traj.samples[0], traj.samples[-1]
    intermediate = traj.samples[len(traj.samples) // 2]
    assert start.time_minutes < intermediate.time_minutes < end.time_minutes
    assert start.route_edge_id is None
    assert end.motion_state == "COMPLETE"


def test_9_mrt_distance_conservation():
    _reg, graph, _route, _mission, traj = _build_mrt_trajectory()
    assert pta.validate_distance_conservation(traj, graph) is True


def test_10_mrt_time_conservation():
    *_rest, traj = _build_mrt_trajectory()
    assert pta.validate_time_conservation(traj) is True


def test_11_mrt_carrier_entity_id_stable_across_two_missions():
    reg, graph, _created, _fid = _mrt_registry_and_graph()
    _route1, mission1 = pta.resolve_mrt_route_and_build_mission(
        graph, mission_id="M-A", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN", start_minutes=0.0,
    )
    traj1 = pta.build_mrt_trajectory(reg, graph, mission=mission1, mrtway_object_id="MRT-CARRIER-001", origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN")
    _route2, mission2 = pta.resolve_mrt_route_and_build_mission(
        graph, mission_id="M-B", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        origin_object_id="MRT-ENDPOINT-SCN", destination_object_id="MRT-ENDPOINT-RP", start_minutes=100.0,
    )
    traj2 = pta.build_mrt_trajectory(reg, graph, mission=mission2, mrtway_object_id="MRT-CARRIER-001", origin_object_id="MRT-ENDPOINT-SCN", destination_object_id="MRT-ENDPOINT-RP")
    assert traj1.entity_id == traj2.entity_id == "MRT-CARRIER-001"
    assert traj1.trajectory_id != traj2.trajectory_id  # trajectory identity per-mission, entity identity stable


# ===========================================================================
# Section 17-18: unified position/time query + boundary semantics.
# ===========================================================================


def test_12_resolve_state_before_start():
    *_rest, traj = _build_mrt_trajectory()
    state = pta.resolve_entity_state_at_time(traj, traj.start_time_minutes - 1000.0)
    first = traj.samples[0]
    assert state.position_x_m == first.x_m and state.position_y_m == first.y_m
    assert state.motion_state == "STATIONARY"


def test_13_resolve_state_exactly_at_start():
    *_rest, traj = _build_mrt_trajectory()
    state = pta.resolve_entity_state_at_time(traj, traj.start_time_minutes)
    assert state.motion_state == traj.samples[0].motion_state


def test_14_resolve_state_during_movement():
    *_rest, traj = _build_mrt_trajectory()
    mid_time = (traj.start_time_minutes + traj.end_time_minutes) / 2.0
    state = pta.resolve_entity_state_at_time(traj, mid_time)
    assert state.motion_state == "MOVING"


def test_15_resolve_state_exactly_at_route_node_transition():
    *_rest, traj = _build_mrt_trajectory()
    transition_sample = traj.samples[1]
    state = pta.resolve_entity_state_at_time(traj, transition_sample.time_minutes)
    assert state.position_x_m == transition_sample.x_m
    assert state.current_route_edge_id == transition_sample.route_edge_id


def test_16_resolve_state_exactly_at_end():
    *_rest, traj = _build_mrt_trajectory()
    state = pta.resolve_entity_state_at_time(traj, traj.end_time_minutes)
    assert state.motion_state == "COMPLETE"
    last = traj.samples[-1]
    assert state.position_x_m == last.x_m and state.position_y_m == last.y_m


def test_17_resolve_state_after_end():
    *_rest, traj = _build_mrt_trajectory()
    state = pta.resolve_entity_state_at_time(traj, traj.end_time_minutes + 999.0)
    assert state.motion_state == "COMPLETE"
    last = traj.samples[-1]
    assert state.position_x_m == last.x_m and state.position_y_m == last.y_m


def test_18_resolve_state_rejects_uncalibrated_time_basis():
    reg, graph, _created = _pts_registry_and_graph()
    traj = pta.build_pts_trajectory(reg, graph, capsule_id="PTS-CAPSULE-001", mission_id="M-PTS-X", origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ")
    with pytest.raises(ValueError):
        pta.resolve_entity_state_at_time(traj, 5.0)


# ===========================================================================
# Section 8: RGHT trajectory -- own network/speed, distinct from MRT.
# ===========================================================================


def test_19_rght_trajectory_uses_own_speed_not_mrt_speed():
    reg, graph, _created = _rght_registry_and_graph()
    rghtna.build_rght_vehicle(reg, vehicle_id="RGHT-VEH-1", facility_id="FAC-RGHT-TEST", network_object_id="RGHT-STN-RP")
    traj = pta.build_rght_trajectory(reg, graph, vehicle_id="RGHT-VEH-1", mission_id="M-RGHT-1", origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ", start_time_minutes=0.0)
    expected_duration = traj.route_distance_m / cta.DEFAULT_AGV_MODEL.speed_m_per_s / 60.0
    assert traj.duration_minutes == pytest.approx(expected_duration)
    assert cta.DEFAULT_AGV_MODEL.speed_m_per_s != 0  # sanity
    _mrt_reg, _mrt_graph, _route, mrt_mission, _mrt_traj = _build_mrt_trajectory()
    mrt_speed = msc.mission_effective_speed(mrt_mission)
    assert cta.DEFAULT_AGV_MODEL.speed_m_per_s != mrt_speed


def test_20_rght_and_mrt_do_not_share_entity_or_network_identity():
    reg, graph, _created = _rght_registry_and_graph()
    rghtna.build_rght_vehicle(reg, vehicle_id="RGHT-VEH-1", facility_id="FAC-RGHT-TEST", network_object_id="RGHT-STN-RP")
    rght_traj = pta.build_rght_trajectory(reg, graph, vehicle_id="RGHT-VEH-1", mission_id="M-RGHT-2", origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ", start_time_minutes=0.0)
    assert rght_traj.entity_type == "RGHT_VEHICLE"
    assert rght_traj.transport_mode == rghtna.RGHT_TRANSPORT_MODE
    assert rght_traj.transport_mode != "MRT"


def test_21_rght_distance_and_time_conservation():
    reg, graph, _created = _rght_registry_and_graph()
    rghtna.build_rght_vehicle(reg, vehicle_id="RGHT-VEH-1", facility_id="FAC-RGHT-TEST", network_object_id="RGHT-STN-RP")
    traj = pta.build_rght_trajectory(reg, graph, vehicle_id="RGHT-VEH-1", mission_id="M-RGHT-3", origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ", start_time_minutes=10.0)
    assert pta.validate_distance_conservation(traj, graph) is True
    assert pta.validate_time_conservation(traj) is True


def test_22_rght_uncalibrated_route_reports_honestly():
    reg, graph, _created = _rght_registry_and_graph()
    traj = pta.build_rght_trajectory(reg, graph, vehicle_id="RGHT-VEH-2", mission_id="M-RGHT-4", origin_object_id="RGHT-STN-RP", destination_object_id="DOES-NOT-EXIST-XYZ", start_time_minutes=0.0)
    assert traj.route_status == "ROUTE_NOT_CALIBRATED"
    assert traj.samples == ()
    assert traj.end_time_minutes == pta.NOT_CALIBRATED


# ===========================================================================
# Section 10: PTS -- spatial path vs time-position distinction.
# ===========================================================================


def test_23_pts_spatial_path_by_default_never_fake_uniform_motion():
    reg, graph, _created = _pts_registry_and_graph()
    traj = pta.build_pts_trajectory(reg, graph, capsule_id="PTS-CAPSULE-001", mission_id="M-PTS-1", origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ")
    assert traj.pts_trajectory_kind == "PTS_SPATIAL_TRAJECTORY_PATH"
    assert traj.start_time_minutes == pta.NOT_CALIBRATED
    assert traj.end_time_minutes == pta.NOT_CALIBRATED
    assert len(traj.samples) >= 2
    assert all(s.time_minutes == pta.NOT_APPLICABLE for s in traj.samples)


def test_24_pts_time_position_only_when_explicitly_asserted_calibrated():
    reg, graph, _created = _pts_registry_and_graph()
    traj = pta.build_pts_trajectory(
        reg, graph, capsule_id="PTS-CAPSULE-001", mission_id="M-PTS-2", origin_object_id="PTS-STN-RP",
        destination_object_id="PTS-STN-INJ", calibrated_start_time_minutes=5.0,
    )
    assert traj.pts_trajectory_kind == "PTS_TIME_POSITION_TRAJECTORY"
    assert traj.start_time_minutes == 5.0
    assert isinstance(traj.end_time_minutes, float)
    expected_duration = traj.route_distance_m / cta.DEFAULT_PTS_NETWORK.speed_m_per_s / 60.0
    assert traj.duration_minutes == pytest.approx(expected_duration)


def test_25_pts_spatial_only_never_uses_dispatch_plus_handling_as_uniform_motion():
    reg, graph, _created = _pts_registry_and_graph()
    traj = pta.build_pts_trajectory(reg, graph, capsule_id="PTS-CAPSULE-001", mission_id="M-PTS-3", origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ")
    flat_total = cta.DEFAULT_PTS_NETWORK.dispatch_minutes + cta.DEFAULT_PTS_NETWORK.station_handling_minutes
    assert traj.duration_minutes != flat_total  # NOT_CALIBRATED (a string), never silently equal to the flat total


def test_26_pts_progress_query_works_without_time_basis():
    reg, graph, _created = _pts_registry_and_graph()
    traj = pta.build_pts_trajectory(reg, graph, capsule_id="PTS-CAPSULE-001", mission_id="M-PTS-4", origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ")
    start_pos = pta.resolve_entity_position_at_progress(traj, 0.0)
    end_pos = pta.resolve_entity_position_at_progress(traj, 1.0)
    assert start_pos != end_pos


def test_27_pts_uncalibrated_route_reports_honestly():
    reg, graph, _created = _pts_registry_and_graph()
    traj = pta.build_pts_trajectory(reg, graph, capsule_id="PTS-CAPSULE-001", mission_id="M-PTS-5", origin_object_id="PTS-STN-RP", destination_object_id="DOES-NOT-EXIST-XYZ")
    assert traj.route_status == "ROUTE_NOT_CALIBRATED"
    assert traj.samples == ()


def test_28_dedicated_pts_variant_uses_its_own_network_not_ordinary_pts():
    reg, graph, _created = _pts_registry_and_graph()
    dedicated_network = cta.PneumaticTubeNetwork(
        network_id="RP-PTS-DEDICATED", compatible_streams=frozenset({"SPECIMEN_BLOOD"}), station_count=2,
        network_length_m=None, capsule_payload_kg=1.0, speed_m_per_s=6.1, station_capex_per_unit=0.0,
        network_capex_per_m=None, annual_maintenance_opex=0.0, annual_energy_opex=0.0, residual_labor_fte=0.0,
    )
    traj = pta.build_pts_trajectory(
        reg, graph, capsule_id="RP-PTS-CAPSULE-001", mission_id="M-RP-PTS-1", origin_object_id="PTS-STN-RP",
        destination_object_id="PTS-STN-INJ", network=dedicated_network, calibrated_start_time_minutes=0.0,
    )
    assert traj.pts_trajectory_kind == "PTS_TIME_POSITION_TRAJECTORY"
    assert "RP-PTS-DEDICATED" in traj.timing_provenance
    assert dedicated_network.speed_m_per_s != cta.DEFAULT_PTS_NETWORK.speed_m_per_s


# ===========================================================================
# Sections 11-13: porter/patient trajectories.
# ===========================================================================


def test_29_porter_trajectory_uses_pedestrian_network_not_straight_line():
    reg, graph, _created = _human_registry_and_graph()
    traj = pta.build_porter_trajectory(reg, graph, porter_id="PORTER-001", mission_id="M-PORTER-1", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201", start_time_minutes=0.0)
    assert traj.route_status == "CALIBRATED"
    assert len(traj.route_node_ids) > 2  # passes through corridor/elevator, never a direct 2-node hop
    assert traj.entity_type == "MANUAL_PORTER"


def test_30_porter_dispatch_dwell_represented_as_waiting_state():
    reg, graph, _created = _human_registry_and_graph()
    traj = pta.build_porter_trajectory(reg, graph, porter_id="PORTER-001", mission_id="M-PORTER-2", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201", start_time_minutes=0.0, dispatch_minutes=2.0)
    assert traj.samples[0].motion_state == "WAITING"
    assert traj.samples[0].time_minutes == 0.0
    assert traj.samples[1].time_minutes == pytest.approx(2.0)


def test_31_patient_trajectory_uses_pedestrian_network():
    reg, graph, _created = _human_registry_and_graph()
    traj = pta.build_patient_trajectory(reg, graph, patient_entity_id="PATIENT-ENTITY-001", mission_id="M-PATIENT-1", patient_id="PT-001", origin_object_id="ROOM-PAT-201", destination_object_id="ROOM-SCN-202", start_time_minutes=0.0)
    assert traj.route_status == "CALIBRATED"
    assert traj.entity_type == "PATIENT"
    assert traj.patient_id == "PT-001"


def test_32_patient_entity_type_never_equals_porter():
    reg, graph, _created = _human_registry_and_graph()
    porter_traj = pta.build_porter_trajectory(reg, graph, porter_id="PORTER-001", mission_id="M-PORTER-3", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201", start_time_minutes=0.0)
    patient_traj = pta.build_patient_trajectory(reg, graph, patient_entity_id="PATIENT-ENTITY-001", mission_id="M-PATIENT-2", patient_id="PT-002", origin_object_id="ROOM-PAT-201", destination_object_id="ROOM-SCN-202", start_time_minutes=0.0)
    assert patient_traj.entity_type != porter_traj.entity_type


def test_33_patient_and_porter_speed_equal():
    reg, graph, _created = _human_registry_and_graph()
    porter_traj = pta.build_porter_trajectory(reg, graph, porter_id="PORTER-001", mission_id="M-PORTER-4", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201", start_time_minutes=0.0)
    patient_traj = pta.build_patient_trajectory(reg, graph, patient_entity_id="PATIENT-ENTITY-001", mission_id="M-PATIENT-3", patient_id="PT-003", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201", start_time_minutes=0.0)
    assert porter_traj.duration_minutes == pytest.approx(patient_traj.duration_minutes)


def test_34_patient_room_to_injection_room_trajectory_never_created():
    source = inspect.getsource(pta)
    assert "injection" not in source.lower() or "PATIENT_ROOM_TO_INJECTION_ROOM_TRAJECTORY_CREATED" not in source


def test_35_porter_and_patient_distance_time_conservation():
    reg, graph, _created = _human_registry_and_graph()
    traj = pta.build_porter_trajectory(reg, graph, porter_id="PORTER-001", mission_id="M-PORTER-5", origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201", start_time_minutes=0.0)
    assert pta.validate_distance_conservation(traj, graph) is True
    assert pta.validate_time_conservation(traj) is True


def test_36_human_uncalibrated_route_reports_honestly():
    reg, graph, _created = _human_registry_and_graph()
    traj = pta.build_porter_trajectory(reg, graph, porter_id="PORTER-001", mission_id="M-PORTER-6", origin_object_id="ROOM-RP-101", destination_object_id="DOES-NOT-EXIST-XYZ", start_time_minutes=0.0)
    assert traj.route_status == "ROUTE_NOT_CALIBRATED"
    assert traj.samples == ()


# ===========================================================================
# Section 26: OpenUSD bridge (proves mapping, never authors production USD).
# ===========================================================================


def test_37_to_dynamic_object_trajectory_bridge():
    *_rest, traj = _build_mrt_trajectory()
    dyn = pta.to_dynamic_object_trajectory(traj)
    assert isinstance(dyn, dss.DynamicObjectTrajectory)
    assert len(dyn.samples) == len(traj.samples)
    assert dyn.canonical_object_id == traj.entity_id
    assert dyn.start_time_minutes == traj.start_time_minutes
    assert dyn.end_time_minutes == traj.end_time_minutes


def test_38_dynamic_object_trajectory_bridge_rejects_uncalibrated():
    reg, graph, _created = _pts_registry_and_graph()
    traj = pta.build_pts_trajectory(reg, graph, capsule_id="PTS-CAPSULE-001", mission_id="M-PTS-6", origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-INJ")
    with pytest.raises(ValueError):
        pta.to_dynamic_object_trajectory(traj)


def test_39_openusd_production_binding_not_started():
    source = _source_without_module_docstring(pta)
    assert "openusd_spatial_adapter" not in source
    assert "author_dynamic_object_trajectory" not in source


# ===========================================================================
# Governance: no mutation, no economics/demand recalculation, no OpenUSD/
# Bentley/NVIDIA authoring, canonical authorities untouched.
# ===========================================================================


def test_40_trajectory_generation_never_mutates_registry():
    reg, graph, _created, _fid = _mrt_registry_and_graph()
    object_count_before = len(reg.objects)
    _route, mission = pta.resolve_mrt_route_and_build_mission(
        graph, mission_id="M-NOMUT", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN", start_minutes=0.0,
    )
    pta.build_mrt_trajectory(reg, graph, mission=mission, mrtway_object_id="MRT-CARRIER-001", origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN")
    assert len(reg.objects) == object_count_before


def test_41_no_economics_or_demand_symbols_referenced():
    source = inspect.getsource(pta)
    for forbidden in ("capex", "opex", "loaded_annual_cost_per_fte", "generate_daily_logistics_demand", "decay"):
        assert forbidden not in source.lower()


def test_42_no_bentley_canonical_binding_reference():
    # PRODUCTION_TRAJECTORY_REQUIRES_BENTLEY is a legitimate required constant
    # (section 27) -- so scan for actual Bentley IMPORTS/module usage, not the
    # bare word "bentley" (which also appears in that constant's own name).
    lines = [l.strip() for l in inspect.getsource(pta).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("bentley" in l.lower() for l in lines)
    assert pta.PRODUCTION_TRAJECTORY_REQUIRES_BENTLEY is False
    assert "canonical_spatial_authority" in inspect.getsource(pta)  # DOES reuse the canonical spatial authority directly


def test_43_no_multimode_playback_engine_started():
    source = _source_without_module_docstring(pta)
    assert "def advance_scene" not in source
    assert "def run_playback" not in source
    assert "concurrent" not in source.lower()


def test_44_no_collision_or_contention_engine():
    source = inspect.getsource(pta)
    for forbidden in ("collision", "contention"):
        assert forbidden not in source.lower()


def test_45_motion_state_vocabulary_reused_not_duplicated():
    assert pta.MotionState is dss.MovementState


def test_46_stable_entity_identity_never_per_timestep():
    *_rest, traj = _build_mrt_trajectory()
    entity_ids = {s.route_edge_id for s in traj.samples}  # sanity: edges vary
    assert len(entity_ids) > 1
    assert traj.entity_id == "MRT-CARRIER-001"  # ONE entity id for the WHOLE trajectory, never per-sample

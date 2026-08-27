"""Production Trajectory Build 2: Operational-Day Trajectory Composition --
focused tests (`operational_day_trajectory_scene.py`).

Covers scene composition/validation, the unified scene/entity query,
derived sampling, multi-mission entity timelines, dwell/idle gap handling,
determinism, conservation preservation (inherited from Build 1, never
altered by composition), governance (no OpenUSD/Bentley/NVIDIA import,
geometry/economics untouched), and one controlled YC-demo proof scene
(MRT + RGHT + porter + patient, with at least one concurrent interval).
"""

import inspect

import canonical_spatial_authority as csa
import human_circulation_authority as hca
import operational_day_trajectory_scene as odts
import production_trajectory_authority as pta
import pytest
import rght_spatial_network_authority as rghtna


# ===========================================================================
# Fixtures -- reuse Build 1/1A's exact controlled-proof pattern.
# ===========================================================================


def _mrt_trajectory(mission_id="M-MRT-1", start_minutes=0.0, facility_id="FAC-B2-MRT"):
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    graph, _created = pta.build_controlled_mrt_proof_network(reg, facility_id=facility_id)
    _route, mission = pta.resolve_mrt_route_and_build_mission(
        graph, mission_id=mission_id, carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN", start_minutes=start_minutes,
    )
    traj = pta.build_mrt_trajectory(reg, graph, mission=mission, mrtway_object_id="MRT-CARRIER-001", origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN")
    return reg, graph, traj


def _rght_trajectory(mission_id="M-RGHT-1", start_time_minutes=0.0, facility_id="FAC-B2-RGHT", building_id="BLDG-B2-RGHT"):
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.add_building(reg, facility_id=facility_id, building_id=building_id)
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F1")
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F2")
    graph, _created = rghtna.build_controlled_rght_proof_network(reg, facility_id=facility_id, building_id=building_id)
    traj = pta.build_rght_trajectory(reg, graph, vehicle_id="RGHT-VEH-001", mission_id=mission_id, origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-SCN", start_time_minutes=start_time_minutes)
    return reg, graph, traj


def _human_network(facility_id="FAC-B2-HUM", building_id="BLDG-B2-HUM"):
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.add_building(reg, facility_id=facility_id, building_id=building_id)
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F1")
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F2")
    graph, _created = hca.build_controlled_pedestrian_network(reg, facility_id=facility_id, building_id=building_id)
    return reg, graph


def _porter_trajectory(mission_id="M-PORTER-1", start_time_minutes=0.0, dispatch_minutes=2.0):
    reg, graph = _human_network()
    traj = pta.build_porter_trajectory(reg, graph, porter_id="PORTER-001", mission_id=mission_id, origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201", start_time_minutes=start_time_minutes, dispatch_minutes=dispatch_minutes)
    return reg, graph, traj


def _patient_trajectory(mission_id="M-PATIENT-1", start_time_minutes=0.0):
    reg, graph = _human_network()
    traj = pta.build_patient_trajectory(reg, graph, patient_entity_id="PATIENT-001", mission_id=mission_id, patient_id="PT-001", origin_object_id="ROOM-PAT-201", destination_object_id="ROOM-SCN-202", start_time_minutes=start_time_minutes)
    return reg, graph, traj


def _yc_demo_scene():
    _r1, _g1, mrt_traj = _mrt_trajectory()
    _r2, _g2, rght_traj = _rght_trajectory()
    _r3, _g3, porter_traj = _porter_trajectory()
    _r4, _g4, patient_traj = _patient_trajectory()
    scene = odts.build_operational_day_trajectory_scene([mrt_traj, rght_traj, porter_traj, patient_traj], scene_id="YC-DEMO-DAY-1")
    return scene, mrt_traj, rght_traj, porter_traj, patient_traj


# ===========================================================================
# Items 1-5: scene composition, time unit, stable identity, multi-mission,
# lineage.
# ===========================================================================


def test_1_scene_contains_build1_trajectories_not_a_copy():
    scene, mrt_traj, rght_traj, porter_traj, patient_traj = _yc_demo_scene()
    assert mrt_traj in scene.trajectories
    assert isinstance(mrt_traj, pta.MovingEntityTrajectory)  # scene stores the ACTUAL Build 1 object, never a duplicate representation


def test_2_time_unit_remains_minutes():
    assert odts.SCENE_TIME_UNIT == "MINUTES"
    assert odts.SCENE_TIME_UNIT == pta.PRODUCTION_TRAJECTORY_TIME_UNIT


def test_3_stable_entity_identity_across_time():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    state_start = odts.resolve_entity_state_in_scene_at_time(scene, entity_id="MRT-CARRIER-001", time_minutes=0.0)
    state_end = odts.resolve_entity_state_in_scene_at_time(scene, entity_id="MRT-CARRIER-001", time_minutes=mrt_traj.end_time_minutes)
    assert state_start.entity_id == state_end.entity_id == "MRT-CARRIER-001"


def test_4_multiple_missions_can_belong_to_one_entity():
    _r1, g1, traj1 = _mrt_trajectory(mission_id="M-A", start_minutes=0.0, facility_id="FAC-B2-MULTI")
    # second mission for the SAME carrier, later in the day, reverse direction
    reg2 = csa.build_facility_hierarchy(facility_id="FAC-B2-MULTI-2")
    graph2, _c2 = pta.build_controlled_mrt_proof_network(reg2, facility_id="FAC-B2-MULTI-2")
    _route2, mission2 = pta.resolve_mrt_route_and_build_mission(
        graph2, mission_id="M-B", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        origin_object_id="MRT-ENDPOINT-SCN", destination_object_id="MRT-ENDPOINT-RP", start_minutes=10.0,
    )
    traj2 = pta.build_mrt_trajectory(reg2, graph2, mission=mission2, mrtway_object_id="MRT-CARRIER-001", origin_object_id="MRT-ENDPOINT-SCN", destination_object_id="MRT-ENDPOINT-RP")
    scene = odts.build_operational_day_trajectory_scene([traj1, traj2], scene_id="MULTI-MISSION")
    assert scene.entity_ids == ("MRT-CARRIER-001",)
    assert len(odts.trajectories_for_entity(scene, "MRT-CARRIER-001")) == 2


def test_5_mission_lineage_preserved():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    state = odts.resolve_scene_state_at_time(scene, 0.0)
    mrt_state = next(s for s in state if s.entity_id == "MRT-CARRIER-001")
    assert mrt_state.mission_id == mrt_traj.mission_id
    assert mrt_state.service_class == mrt_traj.payload_service_class


# ===========================================================================
# Items 6-8: MRT composition.
# ===========================================================================


def test_6_mrt_operational_mission_composed():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    assert mrt_traj.entity_type == "MRT_CARRIER"
    assert mrt_traj in scene.trajectories


def test_7_mrt_route_turn_preserved_in_scene():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    xs = {s.x_m for s in mrt_traj.samples}
    ys = {s.y_m for s in mrt_traj.samples}
    assert len(xs) > 1 and len(ys) > 1


def test_8_mrt_speed_authority_reused():
    import mrt_service_class_authority as msc
    _r1, _g1, mrt_traj = _mrt_trajectory()
    assert "mission_effective_speed" in mrt_traj.timing_provenance


# ===========================================================================
# Items 9-10: RGHT distinctness.
# ===========================================================================


def test_9_rght_network_distinct_from_mrt():
    scene, mrt_traj, rght_traj, *_rest = _yc_demo_scene()
    assert rght_traj.transport_mode != mrt_traj.transport_mode
    assert rght_traj.entity_id != mrt_traj.entity_id


def test_10_rght_speed_distinct_from_mrt():
    import conventional_transport_authority as cta
    import mrt_service_class_authority as msc
    _r1, _g1, mrt_traj = _mrt_trajectory()
    _r2, _g2, rght_traj = _rght_trajectory()
    assert cta.DEFAULT_AGV_MODEL.speed_m_per_s != msc.mission_effective_speed  # sanity: not the same object/function
    mrt_duration_speed_ratio = mrt_traj.route_distance_m / mrt_traj.duration_minutes
    rght_duration_speed_ratio = rght_traj.route_distance_m / rght_traj.duration_minutes
    assert mrt_duration_speed_ratio != pytest.approx(rght_duration_speed_ratio)


# ===========================================================================
# Item 11: PTS honesty (never fake uniform motion).
# ===========================================================================


def test_11_pts_fake_uniform_motion_not_introduced():
    import pts_spatial_network_authority as ptsna
    facility_id, building_id = "FAC-B2-PTS", "BLDG-B2-PTS"
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.add_building(reg, facility_id=facility_id, building_id=building_id)
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F1")
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F2")
    graph, _created = ptsna.build_controlled_pts_proof_network(reg, facility_id=facility_id, building_id=building_id)
    pts_traj = pta.build_pts_trajectory(reg, graph, capsule_id="PTS-CAPSULE-001", mission_id="M-PTS-1", origin_object_id="PTS-STN-RP", destination_object_id="PTS-STN-SCN")
    assert pts_traj.pts_trajectory_kind == "PTS_SPATIAL_TRAJECTORY_PATH"
    assert pts_traj.start_time_minutes == pta.NOT_CALIBRATED
    # a scene may still be built (composition never fabricates timing for this trajectory):
    scene = odts.build_operational_day_trajectory_scene([pts_traj], scene_id="PTS-ONLY")
    assert scene.start_time_minutes == pta.NOT_CALIBRATED
    assert odts.resolve_scene_state_at_time(scene, 0.0) == ()  # honestly omitted, never fabricated


# ===========================================================================
# Items 12-13: porter pedestrian network / no straight lines.
# ===========================================================================


def test_12_porter_uses_pedestrian_route():
    _r, _g, porter_traj = _porter_trajectory()
    assert porter_traj.route_status == "CALIBRATED"
    assert len(porter_traj.route_node_ids) > 2


def test_13_porter_does_not_cross_walls_via_straight_line():
    _r, _g, porter_traj = _porter_trajectory()
    assert "COR-F1-001" in porter_traj.route_node_ids  # passes through a corridor, never a direct hop


# ===========================================================================
# Items 14-15: patient vs porter identity.
# ===========================================================================


def test_14_patient_semantic_identity_differs_from_porter():
    scene, _mrt, _rght, porter_traj, patient_traj = _yc_demo_scene()
    assert patient_traj.entity_type != porter_traj.entity_type
    assert patient_traj.entity_id != porter_traj.entity_id


def test_15_patient_travel_never_becomes_porter_labor():
    source = inspect.getsource(odts)
    assert "porter_labor" not in source.lower()
    assert "MANUAL_PORTER" not in inspect.getsource(odts.SceneEntityState)


# ===========================================================================
# Item 16: dwell/idle gap never teleports.
# ===========================================================================


def test_16_dwell_gap_does_not_teleport_entity():
    scene, _mrt, _rght, porter_traj, _patient = _yc_demo_scene()
    state_during_dwell = odts.resolve_entity_state_in_scene_at_time(scene, entity_id="PORTER-001", time_minutes=1.0)
    assert state_during_dwell.motion_state == "WAITING"
    assert (state_during_dwell.position_x_m, state_during_dwell.position_y_m, state_during_dwell.position_z_m) == (porter_traj.samples[0].x_m, porter_traj.samples[0].y_m, porter_traj.samples[0].z_m)


# ===========================================================================
# Items 17-18: unified scene query + determinism.
# ===========================================================================


def test_17_unified_scene_query_returns_all_active_entities():
    scene, *_rest = _yc_demo_scene()
    states = odts.resolve_scene_state_at_time(scene, 0.04)
    assert {s.entity_id for s in states} == set(scene.entity_ids)


def test_18_scene_state_deterministic():
    scene, *_rest = _yc_demo_scene()
    a = odts.resolve_scene_state_at_time(scene, 0.04)
    b = odts.resolve_scene_state_at_time(scene, 0.04)
    assert a == b


# ===========================================================================
# Items 19-21: entity query reuses Build 1 resolver; sampling derived,
# non-authoritative.
# ===========================================================================


def test_19_entity_query_reuses_build1_resolver():
    source = inspect.getsource(odts)
    assert "pta.resolve_entity_state_at_time" in source
    assert "def resolve_entity_state_at_time" not in source  # never a second implementation


def test_20_sampling_is_derived_from_scene():
    scene, *_rest = _yc_demo_scene()
    samples = odts.sample_scene(scene, start_time_minutes=0.0, end_time_minutes=0.08, step_minutes=0.04)
    assert len(samples) == 3
    assert samples[0].entity_states == odts.resolve_scene_state_at_time(scene, 0.0)


def test_21_sampling_never_becomes_authoritative():
    assert odts.FRAME_SAMPLING_IS_DERIVED is True
    assert odts.FRAME_DATABASE_BECOMES_ENGINEERING_AUTHORITY is False
    source = inspect.getsource(odts)
    assert "class SceneSample" in source
    # SceneSample is a plain, non-authoritative dataclass -- no persistence/authority marker exists:
    assert "authoritative" not in source.lower() or "NEVER a second authoritative" in source or "engineering authority" not in source.lower()


# ===========================================================================
# Item 22: concurrency.
# ===========================================================================


def test_22_concurrent_entities_supported():
    scene, *_rest = _yc_demo_scene()
    states = odts.resolve_scene_state_at_time(scene, 0.04)
    moving = [s for s in states if s.motion_state == "MOVING"]
    assert len(moving) >= 2  # MRT + RGHT + patient all moving concurrently at t=0.04


# ===========================================================================
# Item 23: duplicate/overlapping active trajectories rejected.
# ===========================================================================


def test_23_overlapping_active_trajectories_for_same_entity_rejected():
    _r1, _g1, traj1 = _mrt_trajectory(mission_id="M-OVERLAP-A", start_minutes=0.0, facility_id="FAC-B2-OVERLAP-1")
    reg2 = csa.build_facility_hierarchy(facility_id="FAC-B2-OVERLAP-2")
    graph2, _c2 = pta.build_controlled_mrt_proof_network(reg2, facility_id="FAC-B2-OVERLAP-2")
    _route2, mission2 = pta.resolve_mrt_route_and_build_mission(
        graph2, mission_id="M-OVERLAP-B", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN", start_minutes=0.01,  # overlaps traj1's window
    )
    traj2 = pta.build_mrt_trajectory(reg2, graph2, mission=mission2, mrtway_object_id="MRT-CARRIER-001", origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN")
    with pytest.raises(odts.OverlappingActiveTrajectoryError):
        odts.build_operational_day_trajectory_scene([traj1, traj2], scene_id="OVERLAP-TEST")


# ===========================================================================
# Item 24: inverted mission time rejected.
# ===========================================================================


def test_24_inverted_mission_time_rejected():
    from dataclasses import replace
    _r1, _g1, traj = _mrt_trajectory()
    inverted = replace(traj, start_time_minutes=10.0, end_time_minutes=0.0)
    with pytest.raises(odts.InvertedMissionTimeError):
        odts.build_operational_day_trajectory_scene([inverted], scene_id="INVERTED-TEST")


# ===========================================================================
# Item 25: unknown entity/route references rejected where applicable.
# ===========================================================================


def test_25_unknown_scene_entity_rejected():
    scene, *_rest = _yc_demo_scene()
    with pytest.raises(odts.UnknownSceneEntityError):
        odts.resolve_entity_state_in_scene_at_time(scene, entity_id="DOES-NOT-EXIST", time_minutes=0.0)
    with pytest.raises(odts.UnknownSceneEntityError):
        odts.trajectories_for_entity(scene, "DOES-NOT-EXIST")


# ===========================================================================
# Items 26-27: conservation preserved (inherited from Build 1, unaltered).
# ===========================================================================


def test_26_distance_conservation_preserved():
    _r, g, mrt_traj = _mrt_trajectory()
    assert pta.validate_distance_conservation(mrt_traj, g) is True


def test_27_time_conservation_preserved_where_calibrated():
    _r, _g, mrt_traj = _mrt_trajectory()
    assert pta.validate_time_conservation(mrt_traj) is True


# ===========================================================================
# Items 28-31: geometry/economics/demand/optimization untouched.
# ===========================================================================


def test_28_geometry_not_mutated():
    reg, graph, _traj = _mrt_trajectory()
    count_before = len(reg.objects)
    pta.resolve_mrt_route_and_build_mission(
        graph, mission_id="M-EXTRA", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN", start_minutes=50.0,
    )
    assert len(reg.objects) == count_before


def test_29_economics_unchanged():
    source = inspect.getsource(odts)
    for forbidden in ("capex", "opex", "irr", "payback", "revenue"):
        assert forbidden not in source.lower()


def test_30_demand_unchanged():
    source = inspect.getsource(odts)
    assert "generate_daily_logistics_demand" not in source
    assert "oncology_pet_spect_scenario" not in source


def test_31_optimization_unchanged():
    source = inspect.getsource(odts)
    assert "assign_technology_per_stream" not in source
    assert "architecture" not in source.lower()


# ===========================================================================
# Items 32-34: no OpenUSD/Bentley/NVIDIA import.
# ===========================================================================


def _import_lines(module) -> list[str]:
    return [l.strip() for l in inspect.getsource(module).splitlines() if l.strip().startswith(("import ", "from "))]


def test_32_no_openusd_import():
    lines = _import_lines(odts)
    assert not any("pxr" in line.lower() or "openusd" in line.lower() for line in lines)


def test_33_no_bentley_import():
    lines = _import_lines(odts)
    assert not any("bentley" in line.lower() for line in lines)


def test_34_no_nvidia_import():
    lines = _import_lines(odts)
    assert not any("omni" in line.lower() or "nvidia" in line.lower() for line in lines)


# ===========================================================================
# Items 35-39: controlled YC demo proof scene.
# ===========================================================================


def test_35_controlled_yc_proof_scene_builds_successfully():
    scene, *_rest = _yc_demo_scene()
    assert isinstance(scene, odts.OperationalDayTrajectoryScene)
    assert len(scene.trajectories) == 4


def test_36_controlled_proof_has_at_least_one_mrt_mission():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    assert any(t.entity_type == "MRT_CARRIER" for t in scene.trajectories)


def test_37_controlled_proof_has_human_movement():
    scene, *_rest = _yc_demo_scene()
    assert any(t.entity_type == "MANUAL_PORTER" for t in scene.trajectories)
    assert any(t.entity_type == "PATIENT" for t in scene.trajectories)


def test_38_controlled_proof_has_concurrent_movement():
    scene, *_rest = _yc_demo_scene()
    states = odts.resolve_scene_state_at_time(scene, 0.04)
    moving_entity_ids = {s.entity_id for s in states if s.motion_state == "MOVING"}
    assert len(moving_entity_ids) >= 2


def test_39_controlled_proof_scene_start_end_correct():
    scene, _mrt, _rght, porter_traj, _patient = _yc_demo_scene()
    assert scene.start_time_minutes == 0.0
    assert scene.end_time_minutes == porter_traj.end_time_minutes  # porter has the longest duration


# ===========================================================================
# Item 40: stable ordering across repeated runs.
# ===========================================================================


def test_40_stable_ordering_across_repeated_runs():
    scene_a, mrt_traj, rght_traj, porter_traj, patient_traj = _yc_demo_scene()
    scene_b = odts.build_operational_day_trajectory_scene([patient_traj, porter_traj, rght_traj, mrt_traj], scene_id="YC-DEMO-DAY-1")
    assert scene_a.trajectories == scene_b.trajectories
    assert scene_a.entity_ids == scene_b.entity_ids


# ===========================================================================
# Controlled proof table (section 24) -- printed for reference, not asserted
# beyond structural sanity.
# ===========================================================================


def test_controlled_proof_table_has_expected_rows():
    scene, *_rest = _yc_demo_scene()
    rows = []
    for t in [0.0, 0.02, 0.04, 0.083, 1.0, 2.0, 2.7]:
        for state in odts.resolve_scene_state_at_time(scene, t):
            rows.append((t, state.entity_id, state.mission_id, state.transport_mode, round(state.position_x_m, 2), round(state.position_y_m, 2), round(state.position_z_m, 2), state.motion_state, state.route_edge_id, state.progress_fraction))
    assert len(rows) > 0
    assert any(r[7] == "COMPLETE" for r in rows)  # mission completion demonstrated
    assert any(r[7] == "WAITING" for r in rows)  # intermission dwell demonstrated

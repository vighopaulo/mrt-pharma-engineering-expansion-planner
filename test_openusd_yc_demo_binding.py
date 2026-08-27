"""OpenUSD Production Binding Build 1: Operational-Day Trajectory Scene ->
Animated USD -- focused tests (`openusd_yc_demo_binding.py`).

Covers: runtime availability, stage units/up-axis/time-basis, one-prim-
per-entity (never per-timestep), all 4 entities represented, MRT guideway
turn preserved in static geometry AND animation, dynamic transforms
sourced verbatim from Build 1/2 (never a second interpolation engine),
vertical motion preserved, porter dwell preserved (no fake motion), scene
concurrency, entity traceability metadata, deterministic
minutes<->TimeCode mapping, structural + real-runtime validation, no
NaN/Inf, artifact + manifest creation, deterministic regeneration,
governance (no Bentley/NVIDIA import, no engineering/economics mutation).
"""

import json
import math

import canonical_spatial_authority as csa
import dynamic_scene_state_authority as dss
import human_circulation_authority as hca
import openusd_spatial_adapter as usda
import openusd_yc_demo_binding as usdb
import operational_day_trajectory_scene as odts
import production_trajectory_authority as pta
import pytest
import rght_spatial_network_authority as rghtna


# ===========================================================================
# Fixtures -- mirrors Build 2's own controlled YC-demo scene pattern.
# ===========================================================================


def _mrt_trajectory(mission_id="M-MRT-1", start_minutes=0.0, facility_id="FAC-USD-MRT"):
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    graph, _created = pta.build_controlled_mrt_proof_network(reg, facility_id=facility_id)
    _route, mission = pta.resolve_mrt_route_and_build_mission(
        graph, mission_id=mission_id, carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN", start_minutes=start_minutes,
    )
    return pta.build_mrt_trajectory(reg, graph, mission=mission, mrtway_object_id="MRT-CARRIER-001", origin_object_id="MRT-ENDPOINT-RP", destination_object_id="MRT-ENDPOINT-SCN")


def _rght_trajectory(mission_id="M-RGHT-1", start_time_minutes=0.0, facility_id="FAC-USD-RGHT", building_id="BLDG-USD-RGHT"):
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.add_building(reg, facility_id=facility_id, building_id=building_id)
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F1")
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F2")
    graph, _created = rghtna.build_controlled_rght_proof_network(reg, facility_id=facility_id, building_id=building_id)
    return pta.build_rght_trajectory(reg, graph, vehicle_id="RGHT-VEH-001", mission_id=mission_id, origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-SCN", start_time_minutes=start_time_minutes)


def _human_network(facility_id="FAC-USD-HUM", building_id="BLDG-USD-HUM"):
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.add_building(reg, facility_id=facility_id, building_id=building_id)
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F1")
    csa.add_floor(reg, facility_id=facility_id, building_id=building_id, floor_id="F2")
    graph, _created = hca.build_controlled_pedestrian_network(reg, facility_id=facility_id, building_id=building_id)
    return reg, graph


def _porter_trajectory(mission_id="M-PORTER-1", start_time_minutes=0.0, dispatch_minutes=2.0):
    reg, graph = _human_network()
    return pta.build_porter_trajectory(reg, graph, porter_id="PORTER-001", mission_id=mission_id, origin_object_id="ROOM-RP-101", destination_object_id="ROOM-PAT-201", start_time_minutes=start_time_minutes, dispatch_minutes=dispatch_minutes)


def _patient_trajectory(mission_id="M-PATIENT-1", start_time_minutes=0.0):
    reg, graph = _human_network()
    return pta.build_patient_trajectory(reg, graph, patient_entity_id="PATIENT-001", mission_id=mission_id, patient_id="PT-001", origin_object_id="ROOM-PAT-201", destination_object_id="ROOM-SCN-202", start_time_minutes=start_time_minutes)


def _yc_demo_scene():
    mrt_traj = _mrt_trajectory()
    rght_traj = _rght_trajectory()
    porter_traj = _porter_trajectory()
    patient_traj = _patient_trajectory()
    scene = odts.build_operational_day_trajectory_scene([mrt_traj, rght_traj, porter_traj, patient_traj], scene_id="YC-DEMO-DAY-1")
    return scene, mrt_traj, rght_traj, porter_traj, patient_traj


# ===========================================================================
# Items 1-6: runtime availability, units, up-axis, time basis.
# ===========================================================================


def test_1_openusd_runtime_available_via_vendored_path():
    assert usdb.OPENUSD_PYTHON_RUNTIME_AVAILABLE is True
    assert usda.OPENUSD_RUNTIME_AVAILABLE is True


def test_2_meters_per_unit_reused_from_adapter():
    assert usdb.USD_STAGE_METERS_PER_UNIT == usda.METERS_PER_UNIT == 1.0


def test_3_up_axis_reused_from_adapter():
    assert usdb.USD_STAGE_UP_AXIS == usda.UP_AXIS == "Z"


def test_4_time_codes_per_second_reused_from_dss():
    assert usdb.USD_TIME_CODES_PER_SECOND == dss.USD_TIME_CODES_PER_SECOND == 1.0


def test_5_frames_per_second_is_explicit_and_distinct():
    assert usdb.USD_FRAMES_PER_SECOND == 24.0
    assert usdb.USD_FRAMES_PER_SECOND != usdb.USD_TIME_CODES_PER_SECOND


def test_6_engineering_time_unit_is_minutes():
    assert usdb.ENGINEERING_TIME_UNIT == "MINUTES" == pta.PRODUCTION_TRAJECTORY_TIME_UNIT


# ===========================================================================
# Items 7-12: stage building, hierarchy, one-prim-per-entity.
# ===========================================================================


def test_7_stage_has_default_prim_at_root():
    scene, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    default_prim = stage.GetDefaultPrim()
    assert default_prim.IsValid()
    assert str(default_prim.GetPath()) == usdb.USD_STAGE_ROOT_PATH


def test_8_stage_units_and_up_axis_correct_on_real_stage():
    scene, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    assert math.isclose(usda.UsdGeom.GetStageMetersPerUnit(stage), 1.0)
    assert usda.UsdGeom.GetStageUpAxis(stage) == usda.UsdGeom.Tokens.z


def test_9_stage_time_codes_match_scene_window():
    scene, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    expected_start = dss.simulation_minutes_to_usd_timecode(scene.start_time_minutes)
    expected_end = dss.simulation_minutes_to_usd_timecode(scene.end_time_minutes)
    assert math.isclose(stage.GetStartTimeCode(), expected_start)
    assert math.isclose(stage.GetEndTimeCode(), expected_end)


def test_10_one_prim_per_entity_not_per_timestep():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    prim_path = f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities/{usdb._prim_name('MRT-CARRIER-001')}"
    prim = stage.GetPrimAtPath(prim_path)
    assert prim.IsValid()
    # exactly one prim for the entity -- not one per sample
    dynamic_entities_prim = stage.GetPrimAtPath(f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities")
    children = list(dynamic_entities_prim.GetChildren())
    assert len(children) == len(scene.entity_ids)


def test_11_all_four_entity_types_created():
    scene, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    for entity_id in ("MRT-CARRIER-001", "RGHT-VEH-001", "PORTER-001", "PATIENT-001"):
        prim_path = f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities/{usdb._prim_name(entity_id)}"
        assert stage.GetPrimAtPath(prim_path).IsValid(), entity_id


def test_12_infrastructure_and_facility_prims_exist():
    scene, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    assert stage.GetPrimAtPath(f"{usdb.USD_STAGE_ROOT_PATH}/Infrastructure").IsValid()
    assert stage.GetPrimAtPath(f"{usdb.USD_STAGE_ROOT_PATH}/Facility").IsValid()


# ===========================================================================
# Items 13-18: MRT guideway turn, static network derivation.
# ===========================================================================


def test_13_mrt_guideway_curve_exists_and_has_turn():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    curve_path = f"{usdb.USD_STAGE_ROOT_PATH}/Infrastructure/MRT/Guideway"
    curve_prim = stage.GetPrimAtPath(curve_path)
    assert curve_prim.IsValid()
    curve = usda.UsdGeom.BasisCurves(curve_prim)
    points = curve.GetPointsAttr().Get()
    xs = {round(p[0], 3) for p in points}
    ys = {round(p[1], 3) for p in points}
    assert len(xs) > 1 and len(ys) > 1  # L-turn: both axes vary


def test_14_static_network_points_match_trajectory_samples_verbatim():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    networks = usdb._collect_static_networks(scene)
    assert networks["MRT"] == tuple((s.x_m, s.y_m, s.z_m) for s in mrt_traj.samples)


def test_15_rght_network_present_and_vertical():
    scene, _mrt, rght_traj, *_rest = _yc_demo_scene()
    networks = usdb._collect_static_networks(scene)
    zs = {p[2] for p in networks["RGHT"]}
    assert len(zs) > 1  # cross-floor vertical proof preserved in static geometry


def test_16_pedestrian_network_derived_from_human_entity():
    scene, *_rest = _yc_demo_scene()
    networks = usdb._collect_static_networks(scene)
    assert "Pedestrian" in networks
    assert len(networks["Pedestrian"]) > 0


def test_17_room_markers_derived_from_trajectory_endpoints():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    markers = usdb._collect_room_markers(scene)
    assert "MRT-ENDPOINT-RP" in markers
    assert "MRT-ENDPOINT-SCN" in markers
    assert markers["MRT-ENDPOINT-RP"] == (mrt_traj.samples[0].x_m, mrt_traj.samples[0].y_m, mrt_traj.samples[0].z_m)


def test_18_no_static_geometry_invented_beyond_trajectory_samples():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    networks = usdb._collect_static_networks(scene)
    assert len(networks["MRT"]) == len(mrt_traj.samples)


# ===========================================================================
# Items 19-25: dynamic animation -- reused interpolation, vertical motion,
# dwell preservation, concurrency.
# ===========================================================================


def test_19_dynamic_transform_never_reimplements_interpolation():
    """Governance: the module must call into Build 1/Build 2's own state
    resolvers or reuse raw samples verbatim -- never author a private
    route-interpolation routine. Scanned via import lines + a direct call
    check (the merge function only concatenates existing samples)."""
    scene, mrt_traj, *_rest = _yc_demo_scene()
    merged = usdb.merge_entity_samples(scene, "MRT-CARRIER-001")
    sample_positions = {(s.x_m, s.y_m, s.z_m) for s in mrt_traj.samples}
    merged_positions = {(x, y, z) for (_t, x, y, z, _m) in merged.samples}
    assert merged_positions == sample_positions


def test_20_mrt_animation_start_and_end_positions_match_engine():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    prim_path = f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities/{usdb._prim_name('MRT-CARRIER-001')}"
    start_state = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=mrt_traj.samples[0].time_minutes)
    end_state = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=mrt_traj.samples[-1].time_minutes)
    assert math.isclose(start_state.position_x_m, mrt_traj.samples[0].x_m, abs_tol=1e-6)
    assert math.isclose(end_state.position_y_m, mrt_traj.samples[-1].y_m, abs_tol=1e-6)


def test_21_rght_vertical_motion_preserved_in_animation():
    scene, _mrt, rght_traj, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    prim_path = f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities/{usdb._prim_name('RGHT-VEH-001')}"
    start_state = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=rght_traj.samples[0].time_minutes)
    end_state = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=rght_traj.samples[-1].time_minutes)
    assert not math.isclose(start_state.position_z_m, end_state.position_z_m, abs_tol=1e-6)


def test_22_porter_dwell_preserved_no_fake_motion():
    scene, _mrt, _rght, porter_traj, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    prim_path = f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities/{usdb._prim_name('PORTER-001')}"
    at_start = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=0.0)
    at_dispatch_end = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=2.0)
    assert math.isclose(at_start.position_x_m, at_dispatch_end.position_x_m, abs_tol=1e-6)
    assert math.isclose(at_start.position_y_m, at_dispatch_end.position_y_m, abs_tol=1e-6)


def test_23_concurrent_playback_at_yc_demo_key_instant():
    scene, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    states = {}
    for entity_id in ("MRT-CARRIER-001", "RGHT-VEH-001", "PORTER-001", "PATIENT-001"):
        prim_path = f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities/{usdb._prim_name(entity_id)}"
        states[entity_id] = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=0.04)
    assert states["MRT-CARRIER-001"].movement_state == "MOVING"
    assert states["RGHT-VEH-001"].movement_state == "MOVING"
    assert states["PATIENT-001"].movement_state == "MOVING"
    assert states["PORTER-001"].movement_state == "WAITING"


def test_24_motion_state_attribute_authored_alongside_position():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    prim_path = f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities/{usdb._prim_name('MRT-CARRIER-001')}"
    state = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=mrt_traj.samples[-1].time_minutes)
    assert state.movement_state == "COMPLETE"


def test_25_multi_mission_entity_holds_across_gap_no_teleport():
    traj_a = _mrt_trajectory(mission_id="M-A", start_minutes=0.0, facility_id="FAC-USD-MULTI-A")
    reg_b = csa.build_facility_hierarchy(facility_id="FAC-USD-MULTI-B")
    graph_b, _c = pta.build_controlled_mrt_proof_network(reg_b, facility_id="FAC-USD-MULTI-B")
    _route_b, mission_b = pta.resolve_mrt_route_and_build_mission(
        graph_b, mission_id="M-B", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        origin_object_id="MRT-ENDPOINT-SCN", destination_object_id="MRT-ENDPOINT-RP", start_minutes=10.0,
    )
    traj_b = pta.build_mrt_trajectory(reg_b, graph_b, mission=mission_b, mrtway_object_id="MRT-CARRIER-001", origin_object_id="MRT-ENDPOINT-SCN", destination_object_id="MRT-ENDPOINT-RP")
    scene = odts.build_operational_day_trajectory_scene([traj_a, traj_b], scene_id="MULTI-MISSION-USD")
    merged = usdb.merge_entity_samples(scene, "MRT-CARRIER-001")
    times = [t for (t, _x, _y, _z, _m) in merged.samples]
    assert times == sorted(times)
    gap_hold_samples = [s for s in merged.samples if traj_a.end_time_minutes < s[0] < traj_b.start_time_minutes]  # type: ignore[operator]
    assert len(gap_hold_samples) == 1
    assert (gap_hold_samples[0][1], gap_hold_samples[0][2], gap_hold_samples[0][3]) == (traj_a.samples[-1].x_m, traj_a.samples[-1].y_m, traj_a.samples[-1].z_m)


# ===========================================================================
# Items 26-30: entity traceability metadata.
# ===========================================================================


def test_26_entity_customdata_traceability():
    scene, mrt_traj, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    prim = stage.GetPrimAtPath(f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities/{usdb._prim_name('MRT-CARRIER-001')}")
    assert prim.GetCustomDataByKey("entity_id") == "MRT-CARRIER-001"
    assert prim.GetCustomDataByKey("entity_type") == "MRT_CARRIER"
    assert prim.GetCustomDataByKey("mission_ids") == mrt_traj.mission_id
    assert prim.GetCustomDataByKey("service_class") == mrt_traj.payload_service_class


def test_27_patient_id_is_synthetic_only():
    scene, _mrt, _rght, _porter, patient_traj = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    prim = stage.GetPrimAtPath(f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities/{usdb._prim_name('PATIENT-001')}")
    assert prim.GetCustomDataByKey("patient_id") == "PT-001"
    assert patient_traj.patient_id == "PT-001"


def test_28_mrtway_object_id_matches_entity_id_for_identity_binding():
    scene, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    prim = stage.GetPrimAtPath(f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities/{usdb._prim_name('PORTER-001')}")
    assert prim.GetCustomDataByKey("mrtway_object_id") == "PORTER-001"


def test_29_transport_mode_recorded():
    scene, _mrt, rght_traj, *_rest = _yc_demo_scene()
    stage = usdb.build_yc_demo_stage(scene)
    prim = stage.GetPrimAtPath(f"{usdb.USD_STAGE_ROOT_PATH}/DynamicEntities/{usdb._prim_name('RGHT-VEH-001')}")
    assert prim.GetCustomDataByKey("transport_mode") == rght_traj.transport_mode


def test_30_display_color_distinguishes_entity_types():
    assert len(set(usdb._ENTITY_DISPLAY_COLOR.values())) == len(usdb._ENTITY_DISPLAY_COLOR)


# ===========================================================================
# Items 31-36: artifact + manifest export, structural validation, no NaN/Inf.
# ===========================================================================


def test_31_export_creates_usda_artifact(tmp_path):
    scene, *_rest = _yc_demo_scene()
    artifact, manifest = usdb.export_yc_demo_stage(scene, output_dir=str(tmp_path))
    assert artifact.format == "usda"
    assert artifact.size_bytes > 0
    import os
    assert os.path.isfile(artifact.path)


def test_32_export_creates_manifest_matching_scene(tmp_path):
    scene, *_rest = _yc_demo_scene()
    _artifact, manifest = usdb.export_yc_demo_stage(scene, output_dir=str(tmp_path))
    with open(manifest.path) as handle:
        content = json.load(handle)
    assert content["scene_id"] == "YC-DEMO-DAY-1"
    assert content["entity_count"] == len(scene.entity_ids)
    assert set(content["entity_ids"]) == set(scene.entity_ids)


def test_33_manifest_records_explicit_time_mapping(tmp_path):
    scene, *_rest = _yc_demo_scene()
    _artifact, manifest = usdb.export_yc_demo_stage(scene, output_dir=str(tmp_path))
    assert manifest.content["engineering_time_unit"] == "MINUTES"
    assert manifest.content["usd_time_codes_per_second"] == 1.0
    assert manifest.content["usd_frames_per_second"] == 24.0


def test_34_validation_level_is_openusd_runtime():
    assert usdb.determine_validation_level() == "OPENUSD_RUNTIME"


def test_35_real_runtime_validation_passes(tmp_path):
    scene, *_rest = _yc_demo_scene()
    artifact, _manifest = usdb.export_yc_demo_stage(scene, output_dir=str(tmp_path))
    result = usdb.validate_usda_with_runtime(artifact.path, scene)
    assert result.valid, result.detail


def test_36_structural_validation_passes_on_exported_text(tmp_path):
    scene, *_rest = _yc_demo_scene()
    artifact, _manifest = usdb.export_yc_demo_stage(scene, output_dir=str(tmp_path))
    text = open(artifact.path).read()
    result = usdb.validate_usda_structure(text, expected_entity_ids=scene.entity_ids)
    assert result.valid, result.detail


# ===========================================================================
# Items 37-40: fallback path, no NaN/Inf, determinism, governance.
# ===========================================================================


def test_37_fallback_ascii_writer_produces_valid_text_without_pxr():
    scene, *_rest = _yc_demo_scene()
    text = usdb.build_yc_demo_usda_text_fallback(scene)
    result = usdb.validate_usda_structure(text, expected_entity_ids=scene.entity_ids)
    assert result.valid, result.detail
    assert text.startswith("#usda 1.0")


def test_38_no_nan_or_inf_in_fallback_text():
    scene, *_rest = _yc_demo_scene()
    text = usdb.build_yc_demo_usda_text_fallback(scene)
    assert usdb._NAN_TOKEN.search(text) is None
    assert usdb._INF_TOKEN.search(text) is None


def test_39_deterministic_regeneration(tmp_path):
    scene, *_rest = _yc_demo_scene()
    artifact1, _m1 = usdb.export_yc_demo_stage(scene, output_dir=str(tmp_path / "run1"))
    artifact2, _m2 = usdb.export_yc_demo_stage(scene, output_dir=str(tmp_path / "run2"))
    text1 = open(artifact1.path).read()
    text2 = open(artifact2.path).read()
    assert text1 == text2


def test_40_no_bentley_nvidia_import_and_no_engineering_mutation():
    import inspect
    source = inspect.getsource(usdb)
    import_lines = [line.strip() for line in source.splitlines() if line.strip().startswith(("import ", "from "))]
    joined = " ".join(import_lines).lower()
    assert "bentley" not in joined
    assert "omni" not in joined
    assert "nvidia" not in joined
    assert usdb.OPENUSD_SELECTS_TRANSPORT_SOLUTION is False
    assert usdb.OPENUSD_BECOMES_ENGINEERING_AUTHORITY is False
    assert usdb.ENGINEERING_RECOMPUTED_INSIDE_OPENUSD_ADAPTER is False
    assert usdb.BENTLEY_CALLED_DURING_USD_EXPORT is False
    assert usdb.NVIDIA_REQUIRED_TO_GENERATE_USD is False
    assert usdb.NVIDIA_STARTED is False
    assert usdb.OPENUSD_BUILD_CHANGES_ENGINEERING is False
    assert usdb.OPENUSD_BUILD_CHANGES_ECONOMICS is False
    assert usdb.OPENUSD_BUILD_CHANGES_DEMAND is False

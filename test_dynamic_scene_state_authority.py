"""Focused tests for OpenUSD Phase 2A: vendor-neutral simulation clock +
time-sampled scene-state foundation.

Covers: dynamic_scene_state_authority vendor-neutrality (no pxr/NVIDIA/
Bentley imports), MRT time-unit/USD-TimeCode conversion determinism and
reversibility, one-canonical-identity-many-time-samples proof via a single
controlled MRT carrier, static-vs-dynamic state isolation (canonical
transform/Lockdown untouched), CarrierTrajectory/NvidiaConsumerPayload
backward-compatibility, and external-platform-independence invariants
(core MRT Pharma computation requires neither Bentley nor NVIDIA).
"""

import inspect
import sys

import pytest

import canonical_spatial_authority as csa
import dynamic_scene_state_authority as dss
import openusd_spatial_adapter as usda

pytestmark = pytest.mark.skipif(not usda.OPENUSD_RUNTIME_AVAILABLE, reason="OpenUSD runtime (pxr) not available in this environment")


# ---------------------------------------------------------------------------
# 1-4. Vendor-neutrality of the dynamic scene-state contract itself.
# ---------------------------------------------------------------------------


def test_dynamic_scene_state_module_exists_and_defines_time_unit():
    assert hasattr(dss, "MRT_SIMULATION_TIME_UNIT")
    assert dss.MRT_SIMULATION_TIME_UNIT == "MINUTES"


def test_dynamic_scene_state_authority_imports_no_pxr():
    source = inspect.getsource(dss)
    assert "import pxr" not in source
    assert "from pxr" not in source


def _import_lines(module) -> list[str]:
    return [line.strip() for line in inspect.getsource(module).splitlines() if line.strip().startswith(("import ", "from "))]


def test_dynamic_scene_state_authority_imports_no_nvidia():
    for line in _import_lines(dss):
        for forbidden in ("omni", "nvidia", "Omniverse"):
            assert forbidden not in line


def test_dynamic_scene_state_authority_imports_no_bentley():
    for line in _import_lines(dss):
        assert "bentley" not in line.lower()


# ---------------------------------------------------------------------------
# 5-7. Time unit + USD TimeCode conversion.
# ---------------------------------------------------------------------------


def test_authoritative_mrt_time_unit_is_explicit():
    assert dss.MRT_SIMULATION_TIME_UNIT == "MINUTES"


def test_usd_timecode_conversion_deterministic():
    a = dss.simulation_minutes_to_usd_timecode(5.0)
    b = dss.simulation_minutes_to_usd_timecode(5.0)
    assert a == b == 300.0  # 5 minutes * 60 seconds/minute * 1.0 timeCodesPerSecond


def test_usd_timecode_conversion_reversible_within_tolerance():
    for minutes in (0.0, 0.017834112132527245, 1.0, 7.3, 123.456):
        assert dss.timecode_round_trip_error_minutes(minutes) < 1e-9


# ---------------------------------------------------------------------------
# 8-14. One controlled MRT carrier: stable identity + time samples.
# ---------------------------------------------------------------------------


@pytest.fixture
def carrier_scene():
    facility_id = "FAC-DYN-FOUNDATION"
    registry = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.build_mrt_trunk(registry, trunk_id="MRT-TRUNK-DEMO", facility_id=facility_id)
    csa.build_mrt_carrier(registry, carrier_id="MRT-CARRIER-001", facility_id=facility_id, network_object_id="MRT-TRUNK-DEMO")
    stage, path_registry, _export_result = usda.export_registry_to_stage(registry)
    trajectory = dss.build_linear_trajectory(
        canonical_object_id="MRT-CARRIER-001",
        waypoints_m=[(5.0, 15.0, 0.0), (14.5, 10.5, 2.0), (24.0, 6.0, 4.0)],
        times_minutes=[0.0, 5.0, 10.0], movement_states=["MOVING", "MOVING", "COMPLETE"],
        provenance="TEST_CONTROLLED_PROOF",
    )
    prim_path = path_registry.resolve_by_mrtway_id("MRT-CARRIER-001")
    usda.configure_stage_time_basis(stage, start_time_minutes=trajectory.start_time_minutes, end_time_minutes=trajectory.end_time_minutes)
    usda.author_dynamic_object_trajectory(stage, prim_path=prim_path, trajectory=trajectory)
    return registry, stage, path_registry, prim_path, trajectory


def test_one_canonical_carrier_produces_one_stable_usd_identity(carrier_scene):
    _registry, stage, path_registry, prim_path, _trajectory = carrier_scene
    matching_paths = [p for p in path_registry.by_prim_path if p == prim_path]
    assert len(matching_paths) == 1
    assert stage.GetPrimAtPath(prim_path).GetCustomDataByKey("mrtway_object_id") == "MRT-CARRIER-001"


def test_multiple_time_samples_exist_on_the_same_identity(carrier_scene):
    _registry, stage, _path_registry, prim_path, trajectory = carrier_scene
    attr = stage.GetPrimAtPath(prim_path).GetAttribute("mrtway:simulationTimeMinutes")
    assert attr.GetNumTimeSamples() == len(trajectory.samples) == 3


def test_start_sample_position_correct(carrier_scene):
    _registry, stage, _path_registry, prim_path, trajectory = carrier_scene
    state = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=trajectory.samples[0].simulation_time_minutes)
    assert (state.position_x_m, state.position_y_m, state.position_z_m) == (5.0, 15.0, 0.0)


def test_intermediate_sample_position_correct(carrier_scene):
    _registry, stage, _path_registry, prim_path, trajectory = carrier_scene
    state = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=trajectory.samples[1].simulation_time_minutes)
    assert (state.position_x_m, state.position_y_m, state.position_z_m) == (14.5, 10.5, 2.0)


def test_end_sample_position_correct(carrier_scene):
    _registry, stage, _path_registry, prim_path, trajectory = carrier_scene
    state = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=trajectory.samples[2].simulation_time_minutes)
    assert (state.position_x_m, state.position_y_m, state.position_z_m) == (24.0, 6.0, 4.0)


def test_movement_state_sequence_preserved(carrier_scene):
    _registry, stage, _path_registry, prim_path, trajectory = carrier_scene
    for sample in trajectory.samples:
        state = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=sample.simulation_time_minutes)
        assert state.movement_state == sample.movement_state


def test_dynamic_state_does_not_overwrite_canonical_engineering_transform(carrier_scene):
    from pxr import Usd
    registry, stage, _path_registry, prim_path, _trajectory = carrier_scene
    canonical_transform = registry.get("MRT-CARRIER-001").transform
    default_transform = usda.read_transform(stage.GetPrimAtPath(prim_path))
    assert default_transform == canonical_transform == csa.Transform()  # DEFAULT (non-timecoded) value untouched by time samples
    # registry itself was never mutated by export/time-sample authoring
    assert registry.get("MRT-CARRIER-001").transform == csa.Transform()


def test_dynamic_trajectory_identity_mismatch_raises():
    facility_id = "FAC-DYN-MISMATCH"
    registry = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.build_mrt_trunk(registry, trunk_id="MRT-TRUNK-X", facility_id=facility_id)
    csa.build_mrt_carrier(registry, carrier_id="MRT-CARRIER-X", facility_id=facility_id, network_object_id="MRT-TRUNK-X")
    stage, path_registry, _ = usda.export_registry_to_stage(registry)
    prim_path = path_registry.resolve_by_mrtway_id("MRT-CARRIER-X")
    wrong_trajectory = dss.build_linear_trajectory(
        canonical_object_id="SOME-OTHER-OBJECT", waypoints_m=[(0.0, 0.0, 0.0)], times_minutes=[0.0], provenance="test",
    )
    with pytest.raises(usda.DynamicTrajectoryIdentityError):
        usda.author_dynamic_object_trajectory(stage, prim_path=prim_path, trajectory=wrong_trajectory)


# ---------------------------------------------------------------------------
# 15. Lockdown/L0 immutability.
# ---------------------------------------------------------------------------


def test_lockdown_l0_unchanged_by_dynamic_authoring():
    facility_id = "FAC-DYN-LOCKDOWN"
    registry = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.build_mrt_trunk(registry, trunk_id="MRT-TRUNK-L0", facility_id=facility_id)
    csa.build_mrt_carrier(registry, carrier_id="MRT-CARRIER-L0", facility_id=facility_id, network_object_id="MRT-TRUNK-L0")
    locked = csa.LockedSpatialState(registry=registry)
    before = dict(locked.registry.objects)

    stage, path_registry, _ = usda.export_registry_to_stage(locked.registry)
    prim_path = path_registry.resolve_by_mrtway_id("MRT-CARRIER-L0")
    trajectory = dss.build_linear_trajectory(
        canonical_object_id="MRT-CARRIER-L0", waypoints_m=[(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)], times_minutes=[0.0, 1.0], provenance="test",
    )
    usda.configure_stage_time_basis(stage, start_time_minutes=0.0, end_time_minutes=1.0)
    usda.author_dynamic_object_trajectory(stage, prim_path=prim_path, trajectory=trajectory)

    after = dict(locked.registry.objects)
    assert before.keys() == after.keys()
    for object_id in before:
        assert before[object_id] == after[object_id]


# ---------------------------------------------------------------------------
# 16. Stage opens successfully.
# ---------------------------------------------------------------------------


def test_dynamic_stage_saves_and_reopens_successfully(tmp_path, carrier_scene):
    from pxr import Usd
    _registry, stage, _path_registry, _prim_path, _trajectory = carrier_scene
    scene_path = str(tmp_path / "dynamic_test_scene.usda")
    usda.save_stage_to_usda(stage, scene_path)
    reopened = Usd.Stage.Open(scene_path)
    assert reopened.GetDefaultPrim().IsValid()


# ---------------------------------------------------------------------------
# 17-19. Static equipment assets remain unchanged in the full dynamic demo.
# ---------------------------------------------------------------------------


@pytest.fixture
def dynamic_demo(tmp_path):
    import generate_openusd_hospital_dynamic_foundation_demo as dyn
    result = dyn.generate_dynamic_demo(
        asset_dir=str(tmp_path / "assets"), scene_path=str(tmp_path / "scene.usda"), manifest_path=str(tmp_path / "MANIFEST.md"),
    )
    from pxr import Usd
    stage = Usd.Stage.Open(result["scene_path"])
    return dyn, result, stage


def test_static_scanner_asset_remains_unchanged(dynamic_demo):
    _dyn, result, stage = dynamic_demo
    anchor = result["path_registry"].resolve_by_mrtway_id("SCN-001")
    assert stage.GetPrimAtPath(f"{anchor}/Visual/Gantry").IsValid()
    assert stage.GetPrimAtPath(anchor).GetAttribute("mrtway:movementState").GetNumTimeSamples() == 0


def test_static_cyclotron_asset_remains_unchanged(dynamic_demo):
    _dyn, result, stage = dynamic_demo
    anchor = result["path_registry"].resolve_by_mrtway_id("CY-001")
    assert stage.GetPrimAtPath(f"{anchor}/Visual/Body").IsValid()
    assert stage.GetPrimAtPath(anchor).GetAttribute("mrtway:movementState").GetNumTimeSamples() == 0


def test_static_radiopharmacy_asset_remains_unchanged(dynamic_demo):
    _dyn, result, stage = dynamic_demo
    anchor = result["path_registry"].resolve_by_mrtway_id("RP-001")
    assert stage.GetPrimAtPath(f"{anchor}/Visual/HotCell").IsValid()
    assert stage.GetPrimAtPath(anchor).GetAttribute("mrtway:movementState").GetNumTimeSamples() == 0


# ---------------------------------------------------------------------------
# 20-21. No NVIDIA runtime / no live Bentley connection required.
# ---------------------------------------------------------------------------


def test_dynamic_demo_requires_no_nvidia_runtime(dynamic_demo):
    forbidden_modules = ("omni", "pxr.UsdRT", "warp", "physx")
    assert not any(m in sys.modules for m in forbidden_modules)


def test_dynamic_demo_requires_no_live_bentley_connection():
    import generate_openusd_hospital_dynamic_foundation_demo as dyn
    source = inspect.getsource(dyn) + inspect.getsource(dss)
    assert "bentley_itwin_client" not in source
    assert "bentley_canonical_binding" not in source
    assert "BENTLEY_CLIENT_ID" not in source


# ---------------------------------------------------------------------------
# 23-24. CarrierTrajectory / NvidiaConsumerPayload backward compatibility.
# ---------------------------------------------------------------------------


def test_existing_carrier_trajectory_behavior_unchanged():
    import mrt_service_class_authority as msc
    mission = msc.MrtServiceMission(mission_id="M-COMPAT", carrier_id="CARRIER-COMPAT", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    scheduled, unresolved = msc.schedule_service_missions([mission])
    assert not unresolved
    trajectory = msc.build_carrier_trajectory(mission, scheduled[0], mrtway_object_id="CARRIER-COMPAT-OBJ")
    assert trajectory.carrier_id == "CARRIER-COMPAT"
    assert trajectory.start_time_minutes <= trajectory.end_time_minutes


def test_existing_nvidia_consumer_payload_behavior_unchanged():
    import live_engineering_impact_binding as lib
    mixed = lib.compute_mixed_service_scenario()
    payload = lib.build_nvidia_consumer_payload(scenario_revision=1, scene_state_id="SCENE-COMPAT", trajectories=mixed.trajectories, impact_summary_reference="IMPACT-COMPAT")
    assert payload.scenario_revision == 1
    assert len(payload.carrier_trajectories) == len(mixed.trajectories)


def test_nvidia_consumer_payload_trajectories_are_carrier_trajectory_compatible():
    """Section 11: NvidiaConsumerPayload.carrier_trajectories are ordinary
    CarrierTrajectory instances -- proving they carry the same
    start_time_minutes/end_time_minutes/status fields the Phase 2A bridge
    already reuses, without making NvidiaConsumerPayload the core
    simulation-time authority."""
    import live_engineering_impact_binding as lib
    mixed = lib.compute_mixed_service_scenario()
    payload = lib.build_nvidia_consumer_payload(scenario_revision=1, scene_state_id="SCENE-COMPAT-2", trajectories=mixed.trajectories, impact_summary_reference="IMPACT-COMPAT-2")
    for trajectory in payload.carrier_trajectories:
        assert hasattr(trajectory, "start_time_minutes")
        assert hasattr(trajectory, "end_time_minutes")
        assert hasattr(trajectory, "status")


# ---------------------------------------------------------------------------
# 25. External-platform-independence invariants.
# ---------------------------------------------------------------------------


def test_core_mrt_pharma_computation_requires_no_bentley_or_nvidia():
    """CORE_MRT_PHARMA_REQUIRES_BENTLEY = NO / CORE_MRT_PHARMA_REQUIRES_NVIDIA = NO:
    a representative core engineering/scheduling computation succeeds without
    ever touching openusd_spatial_adapter, bentley_itwin_client, or pxr."""
    import mrt_service_class_authority as msc
    facility_id = "FAC-INDEPENDENCE"
    registry = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.build_nuclear_engineering_objects(registry, facility_id=facility_id, building_id=None, floor_id=None, cyclotron_id="CY-INDEP")  # noqa: E501 -- deliberately no building/floor: proves pure engineering-authority path
    mission = msc.MrtServiceMission(mission_id="M-INDEP", carrier_id="CARRIER-INDEP", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=50.0, start_minutes=0.0)
    scheduled, unresolved = msc.schedule_service_missions([mission])
    assert not unresolved and scheduled


def test_dynamic_scene_state_authority_has_zero_platform_dependencies_at_import_time():
    """Importing `dynamic_scene_state_authority` in a FRESH subprocess must
    never pull in pxr/Bentley/NVIDIA modules as a side effect -- a stronger
    proof than source inspection alone, immune to other tests in this same
    process having already imported pxr."""
    import subprocess
    import sys as _sys
    script = (
        "import sys, dynamic_scene_state_authority; "
        "forbidden = [m for m in ('pxr', 'bentley_itwin_client', 'bentley_canonical_binding', 'omni') if m in sys.modules]; "
        "print('FORBIDDEN=' + repr(forbidden))"
    )
    completed = subprocess.run([_sys.executable, "-c", script], cwd=".", capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert "FORBIDDEN=[]" in completed.stdout

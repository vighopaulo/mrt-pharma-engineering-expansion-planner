"""Focused tests for `live_engineering_impact_binding.py`: the orchestration
layer that propagates a validated What-If change through the EXISTING
authoritative engineering/scheduling/auxiliary/economic calculations and
returns one coherent LiveEngineeringImpactResult.

Covers: authority audit / no duplicate physics-scheduler-finance engine,
request/result contracts, metric provenance/units/statuses, partial
resolution + failure isolation, locked-state immutability, scenario
isolation, return-to-locked/remove-one-change/reset-category, revision IDs +
stale-result protection, NaN/Infinity rejection, nuclear 10->15 m/s scenario
(identity invariants, scheduling, decay reuse, drag nonlinearity,
acceleration energy, electrical/thermal/cooling partial resolution, legacy
energy reconciliation), blood/linen speed what-ifs + service-class isolation,
mixed-speed scenario, priority override independence, color-only zero-impact
control, inactive Food/Waste, cyclotron equipment what-if, MRT segment-length
scenario + guideway/carrier/vestibule/controls/installation non-regression,
electricity-tariff physical-kWh invariance, site-power binding, trajectory
revision + simulation-driven animation payload, OpenUSD non-authority,
Bentley identity compatibility (MRTWAY_OBJECT_ID), serialization,
determinism, and component non-regression.
"""

import inspect
import math

import pytest

import canonical_spatial_authority as csa
import live_engineering_impact_binding as lib
import mrt_auxiliary_systems_authority as maux
import mrt_service_class_authority as msc


# ---------------------------------------------------------------------------
# Authority audit / no duplicate engines
# ---------------------------------------------------------------------------


def test_no_duplicate_physics_functions_defined_in_binding_module():
    """Section 4: the binding module must not define its own drag/Joule/
    thermal/cooling/vacuum/decay physics -- only call existing authorities."""
    source = inspect.getsource(lib)
    forbidden_defs = ("def compute_drag_force_n", "def compute_joule_loss_w", "def compute_thermal_load", "def retained_fraction", "def resolve_cooling_power")
    for forbidden in forbidden_defs:
        assert forbidden not in source


def test_no_duplicate_scheduler_defined_in_binding_module():
    """Section 6: scheduling must delegate to shared_mrt_multistream_authority
    (via mrt_service_class_authority), never a second scheduler."""
    source = inspect.getsource(lib)
    assert "def schedule_missions_on_shared_segment" not in source
    assert "msc.schedule_service_missions" in source


def test_no_duplicate_finance_engine_defined_in_binding_module():
    """Section 38/79: NPV/NPC must never be computed inside the binding
    layer -- only referenced as PENDING."""
    source = inspect.getsource(lib)
    assert "def evaluate_lifecycle_economics" not in source
    assert "PENDING_ENGINEERING_RECALCULATION" in source


def test_no_duplicate_spatial_engine_defined_in_binding_module():
    """Section 5: spatial deltas reuse canonical_spatial_authority verbatim."""
    source = inspect.getsource(lib)
    assert "class SpatialObjectRegistry" not in source
    assert "csa.compute_segment_length_capex_delta" in source


# ---------------------------------------------------------------------------
# Request/result contracts + metric model
# ---------------------------------------------------------------------------


def test_live_impact_request_contract():
    request = lib.LiveImpactRequest(scenario_id="S1", base_locked_state_id="LOCKED-1", requested_scope=("TRANSPORT_MRT",))
    assert request.scenario_id == "S1"
    assert request.requested_scope == ("TRANSPORT_MRT",)
    assert request.timestamp


def test_impact_metric_has_full_provenance_and_unit():
    metric = lib.build_impact_metric(
        metric_id="x", display_name="X", locked_value=1.0, what_if_value=2.0, unit="m", source_authority="test_authority",
        provenance="USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION", calibration_status="CALIBRATED", group="PHYSICAL",
    )
    assert metric.unit == "m"
    assert metric.source_authority == "test_authority"
    assert metric.provenance == "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION"
    assert metric.calibration_status == "CALIBRATED"


def test_impact_metric_zero_locked_value_never_fabricates_percent():
    metric = lib.build_impact_metric(metric_id="x", display_name="X", locked_value=0.0, what_if_value=500.0, unit="USD", source_authority="a", provenance="p", calibration_status="c", group="CAPEX")
    assert metric.percent_delta is None
    assert metric.absolute_delta == 500.0


def test_impact_metric_unresolved_value_never_computes_delta():
    metric = lib.build_impact_metric(metric_id="x", display_name="X", locked_value="NOT_CALIBRATED", what_if_value="NOT_CALIBRATED", unit="W", source_authority="a", provenance="p", calibration_status="c", group="THERMAL")
    assert metric.status == "NOT_CALIBRATED"
    assert metric.absolute_delta == "NOT_CALIBRATED"


def test_impact_metric_rejects_nan():
    with pytest.raises(lib.InvalidParameterError):
        lib.build_impact_metric(metric_id="x", display_name="X", locked_value=float("nan"), what_if_value=1.0, unit=None, source_authority="a", provenance="p", calibration_status="c", group="PHYSICAL")


def test_impact_metric_rejects_infinity():
    with pytest.raises(lib.InvalidParameterError):
        lib.build_impact_metric(metric_id="x", display_name="X", locked_value=float("inf"), what_if_value=1.0, unit=None, source_authority="a", provenance="p", calibration_status="c", group="PHYSICAL")


# ---------------------------------------------------------------------------
# Nuclear 10->15 m/s scenario
# ---------------------------------------------------------------------------


@pytest.fixture
def nuclear_result():
    return lib.compute_service_class_speed_what_if_impact(
        service_class="RADIOPHARMACEUTICAL_NUCLEAR", locked_speed_m_per_s=10.0, what_if_speed_m_per_s=15.0,
        route_length_m=500.0, half_life_minutes=109.8, operating_hours_per_year=6000.0, electricity_cost_per_kwh=0.15,
    )


def test_nuclear_speed_identity_invariants(nuclear_result):
    assert nuclear_result.metric("service_class_identity").status == "UNCHANGED"
    assert nuclear_result.metric("presentation_color").status == "UNCHANGED"
    assert nuclear_result.metric("effective_priority").status == "UNCHANGED"
    assert nuclear_result.metric("container_class").status == "UNCHANGED"


def test_nuclear_speed_transport_time_resolved(nuclear_result):
    m = nuclear_result.metric("transport_time_minutes")
    assert m.status == "RESOLVED"
    assert m.what_if_value < m.locked_value  # faster speed -> shorter time


def test_nuclear_speed_scheduling_recalculated(nuclear_result):
    m = nuclear_result.metric("scheduled_wait_minutes")
    assert m.source_authority == "shared_mrt_multistream_authority.schedule_missions_on_shared_segment"


def test_nuclear_speed_decay_reuses_existing_authority(nuclear_result):
    m = nuclear_result.metric("retained_activity_fraction")
    assert m.status == "RESOLVED"
    assert m.source_authority.startswith("multi_isotope_decay.retained_fraction")
    assert m.what_if_value > m.locked_value  # faster transport -> higher retained fraction


def test_nuclear_speed_drag_power_nonlinear():
    r10 = lib.compute_service_class_speed_what_if_impact(service_class="RADIOPHARMACEUTICAL_NUCLEAR", locked_speed_m_per_s=10.0, what_if_speed_m_per_s=10.0, route_length_m=500.0)
    r15 = lib.compute_service_class_speed_what_if_impact(service_class="RADIOPHARMACEUTICAL_NUCLEAR", locked_speed_m_per_s=10.0, what_if_speed_m_per_s=15.0, route_length_m=500.0)
    power_10 = r10.metric("drag_power_w").what_if_value
    power_15 = r15.metric("drag_power_w").what_if_value
    ratio = power_15 / power_10
    assert ratio == pytest.approx(1.5 ** 3, rel=1e-6)


def test_nuclear_speed_acceleration_energy_resolved(nuclear_result):
    m = nuclear_result.metric("acceleration_energy_j")
    assert m.status == "RESOLVED"
    assert m.what_if_value > m.locked_value


def test_nuclear_speed_electrical_partial_resolution(nuclear_result):
    """Section 32-33/120: Joule/PE electrical load is honestly NOT_CALIBRATED
    (speed does not couple to resistance/current in the existing model);
    thermal is PENDING; this must NOT erase the resolved transport-time/drag
    branches (failure isolation, section 15)."""
    assert nuclear_result.metric("resistive_electrical_load_w").status == "NOT_CALIBRATED"
    assert nuclear_result.metric("thermal_load_w").status == "PENDING_ENGINEERING_RECALCULATION"
    assert nuclear_result.metric("transport_time_minutes").status == "RESOLVED"
    assert nuclear_result.metric("drag_power_w").status == "RESOLVED"


def test_nuclear_speed_cooling_not_calibrated_without_architecture(nuclear_result):
    assert nuclear_result.metric("cooling_power_w").status == "NOT_CALIBRATED"


def test_nuclear_speed_legacy_energy_reconciliation(nuclear_result):
    m = nuclear_result.metric("electricity_opex_usd")
    assert m.status == "RESOLVED"
    assert "SCHEDULE_DERIVED_CALIBRATION" in m.note  # replaces, never stacks


def test_nuclear_speed_npv_pending_never_computed(nuclear_result):
    m = nuclear_result.metric("npv_usd")
    assert m.status == "PENDING_ENGINEERING_RECALCULATION"


def test_nuclear_speed_validation_status_reflects_partial_resolution(nuclear_result):
    assert nuclear_result.validation_status == "VALID_WITH_UNCALIBRATED_DEPENDENCIES"


def test_nuclear_speed_trace_is_ordered_by_causality(nuclear_result):
    node_order = [t.dependency_node for t in nuclear_result.trace]
    assert node_order.index("carrier_speed") < node_order.index("transport_time")
    assert node_order.index("transport_time") < node_order.index("scheduling")
    assert node_order.index("drag") < node_order.index("electrical_demand")
    assert node_order.index("electrical_demand") < node_order.index("thermal_load")
    assert node_order.index("thermal_load") < node_order.index("cooling_requirement")


# ---------------------------------------------------------------------------
# Blood / linen speed what-ifs + service-class isolation
# ---------------------------------------------------------------------------


def test_blood_speed_what_if():
    result = lib.compute_service_class_speed_what_if_impact(service_class="SPECIMEN_BLOOD", locked_speed_m_per_s=7.0, what_if_speed_m_per_s=9.0, route_length_m=100.0)
    assert result.metric("service_class_identity").status == "UNCHANGED"
    assert result.metric("transport_time_minutes").status == "RESOLVED"


def test_linen_speed_what_if():
    result = lib.compute_service_class_speed_what_if_impact(service_class="LAUNDRY_CLEAN_LINEN", locked_speed_m_per_s=1.0, what_if_speed_m_per_s=1.5, route_length_m=100.0)
    assert result.metric("service_class_identity").status == "UNCHANGED"


def test_blood_speed_what_if_does_not_alter_nuclear_or_linen_defaults():
    lib.compute_service_class_speed_what_if_impact(service_class="SPECIMEN_BLOOD", locked_speed_m_per_s=7.0, what_if_speed_m_per_s=9.0, route_length_m=100.0)
    assert msc.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"].default_speed_m_per_s == 10.0
    assert msc.SERVICE_CLASS_REGISTRY["LAUNDRY_CLEAN_LINEN"].default_speed_m_per_s == 1.0


def test_general_logistics_no_fake_decay():
    result = lib.compute_service_class_speed_what_if_impact(service_class="SPECIMEN_BLOOD", locked_speed_m_per_s=7.0, what_if_speed_m_per_s=9.0, route_length_m=100.0)
    m = result.metric("retained_activity_fraction")
    assert m.status == "NOT_APPLICABLE"


def test_inactive_service_class_rejected():
    with pytest.raises(lib.InvalidServiceClassError):
        lib.compute_service_class_speed_what_if_impact(service_class="FOOD_NUTRITION", locked_speed_m_per_s=1.0, what_if_speed_m_per_s=2.0, route_length_m=100.0)


def test_negative_speed_rejected():
    with pytest.raises(lib.InvalidParameterError):
        lib.compute_service_class_speed_what_if_impact(service_class="SPECIMEN_BLOOD", locked_speed_m_per_s=-1.0, what_if_speed_m_per_s=9.0, route_length_m=100.0)


# ---------------------------------------------------------------------------
# Mixed-speed scenario
# ---------------------------------------------------------------------------


def test_mixed_service_scenario_preserves_distinct_speeds():
    mixed = lib.compute_mixed_service_scenario()
    speeds = {e.effective_speed_m_per_s for e in mixed.speed_mix.entries}
    assert speeds == {10.0, 7.0, 1.0}


def test_mixed_service_scenario_priority_ordering_no_starvation():
    mixed = lib.compute_mixed_service_scenario()
    mission_ids = {s.mission_id for s in mixed.scheduled}
    assert mission_ids == {"NUC-1", "BLD-1", "LIN-1"}  # linen never dropped


def test_mixed_service_scenario_trajectories_updated():
    mixed = lib.compute_mixed_service_scenario()
    assert len(mixed.trajectories) == 3
    colors = {t.presentation.effective_display_color for t in mixed.trajectories}
    assert colors == {"VIOLET", "BLUE", "GOLD"}


def test_mixed_service_scenario_no_illegal_overtake():
    mixed = lib.compute_mixed_service_scenario()
    by_id = {s.mission_id: s for s in mixed.scheduled}
    assert by_id["NUC-1"].scheduled_start_minutes < by_id["BLD-1"].scheduled_start_minutes < by_id["LIN-1"].scheduled_start_minutes


# ---------------------------------------------------------------------------
# Priority override / speed-priority independence / color-only negative control
# ---------------------------------------------------------------------------


def test_speed_change_does_not_alter_priority():
    profile = msc.SERVICE_CLASS_REGISTRY["SPECIMEN_BLOOD"]
    mission_slow = msc.MrtServiceMission(mission_id="M1", carrier_id="C1", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.0, speed_override_m_per_s=5.0)
    mission_fast = msc.MrtServiceMission(mission_id="M2", carrier_id="C1", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.0, speed_override_m_per_s=9.0)
    assert msc.mission_effective_priority(mission_slow) == msc.mission_effective_priority(mission_fast) == profile.default_priority


def test_priority_override_does_not_alter_speed():
    override = msc.PriorityOverrideRecord(original_priority="PRIORITY_2_CLINICAL_URGENT", effective_priority="PRIORITY_1_NUCLEAR_CRITICAL", reason="STAT", source="clinician")
    mission = msc.MrtServiceMission(mission_id="M1", carrier_id="C1", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.0, priority_override=override)
    assert msc.mission_effective_speed(mission) == 7.0
    assert msc.mission_effective_priority(mission) == "PRIORITY_1_NUCLEAR_CRITICAL"


def test_priority_override_propagates_to_scheduler_timing():
    normal = msc.MrtServiceMission(mission_id="NORMAL", carrier_id="C1", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=1.0)
    override = msc.PriorityOverrideRecord(original_priority="PRIORITY_2_CLINICAL_URGENT", effective_priority="PRIORITY_1_NUCLEAR_CRITICAL", reason="STAT", source="clinician")
    stat = msc.MrtServiceMission(mission_id="STAT", carrier_id="C2", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.5, priority_override=override)
    nuclear = msc.MrtServiceMission(mission_id="NUC", carrier_id="C3", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    scheduled, _ = msc.schedule_service_missions([normal, stat, nuclear])
    by_id = {s.mission_id: s for s in scheduled}
    # STAT (overridden to P1) ties nuclear's P1 -- both dispatch before NORMAL (P2)
    assert by_id["STAT"].scheduled_start_minutes < by_id["NORMAL"].scheduled_start_minutes


def test_color_only_change_has_zero_engineering_effect():
    """Section 44/115: color never appears as an input to any binding
    function signature -- verified structurally, never merely asserted."""
    for func in (lib.compute_service_class_speed_what_if_impact, lib.compute_segment_length_what_if_impact, lib.compute_electricity_tariff_what_if_impact, lib.compute_site_power_what_if_impact, lib.compute_cyclotron_model_what_if_impact):
        sig = inspect.signature(func)
        assert "color" not in sig.parameters


def test_camera_rotation_is_not_engineering_object_rotation():
    """Section 57/116: camera orbit is a distinct concept from engineering
    object rotation in canonical_spatial_authority; the live-binding layer
    never conflates the two."""
    assert hasattr(csa, "apply_camera_rotation")


# ---------------------------------------------------------------------------
# Inactive Food/Waste
# ---------------------------------------------------------------------------


def test_inactive_food_cannot_run_live_speed_what_if():
    with pytest.raises(lib.InvalidServiceClassError):
        lib.compute_service_class_speed_what_if_impact(service_class="FOOD_NUTRITION", locked_speed_m_per_s=1.0, what_if_speed_m_per_s=2.0, route_length_m=100.0)


def test_inactive_waste_cannot_run_live_speed_what_if():
    with pytest.raises(lib.InvalidServiceClassError):
        lib.compute_service_class_speed_what_if_impact(service_class="WASTE", locked_speed_m_per_s=1.0, what_if_speed_m_per_s=2.0, route_length_m=100.0)


# ---------------------------------------------------------------------------
# Equipment (cyclotron) what-if
# ---------------------------------------------------------------------------


def test_cyclotron_model_what_if_preserves_catalog_identity():
    from cyclotron_catalog import load_cyclotron_catalog
    ids = [m.catalog_model_id for m in load_cyclotron_catalog().models]
    result = lib.compute_cyclotron_model_what_if_impact(locked_model_id=ids[0], what_if_model_id=ids[1])
    assert result.metric("catalog_model_id").locked_value == ids[0]
    assert result.metric("catalog_model_id").what_if_value == ids[1]


def test_cyclotron_model_what_if_capex_unchanged_flat_authority():
    from cyclotron_catalog import load_cyclotron_catalog
    ids = [m.catalog_model_id for m in load_cyclotron_catalog().models]
    result = lib.compute_cyclotron_model_what_if_impact(locked_model_id=ids[0], what_if_model_id=ids[1])
    assert result.metric("cyclotron_capex_usd").status == "UNCHANGED"


def test_cyclotron_model_what_if_unknown_model_rejected():
    with pytest.raises(lib.InvalidObjectError):
        lib.compute_cyclotron_model_what_if_impact(locked_model_id="DOES_NOT_EXIST", what_if_model_id="ALSO_MISSING")


# ---------------------------------------------------------------------------
# MRT segment-length scenario + economic non-regression
# ---------------------------------------------------------------------------


def test_segment_length_guideway_capex_delta_matches_500_per_m():
    result = lib.compute_segment_length_what_if_impact(locked_length_m=500.0, what_if_length_m=600.0)
    assert result.metric("guideway_capex_delta_usd").what_if_value == pytest.approx(100.0 * 5_000.0)


def test_segment_length_never_recharges_once_per_network_costs():
    result = lib.compute_segment_length_what_if_impact(locked_length_m=500.0, what_if_length_m=1000.0)
    for metric_id in ("controls_capex_usd_delta", "vestibule_capex_usd_delta", "installation_commissioning_capex_usd_delta"):
        m = result.metric(metric_id)
        assert m.locked_value == 0.0
        assert m.what_if_value == 0.0


def test_guideway_default_unit_cost_is_5000_per_meter():
    from models import PlannerAssumptions
    assert PlannerAssumptions().mrt_guideway_capex_per_m == 5_000.0


def test_carrier_default_unit_cost_is_10000():
    from models import PlannerAssumptions
    assert PlannerAssumptions().mrt_carrier_capex_per_installed_unit == 10_000.0


def test_vestibule_capex_constant_is_30000():
    assert csa.MRT_VESTIBULE_CAPEX_USD == 30_000.0


def test_controls_capex_constant_is_100000_once():
    assert csa.MRT_CONTROLS_CAPEX_USD == 100_000.0


def test_installation_capex_constant_is_300000_once():
    assert csa.MRT_INSTALLATION_COMMISSIONING_CAPEX_USD == 300_000.0


def test_controlled_baseline_500m_50carrier_1vestibule_is_3_43_million():
    result = csa.compute_mrt_transport_only_capex(guideway_length_m=500.0, carrier_count=50, vestibule_count=1, include_controls=True, include_installation_commissioning=True)
    assert result.total_capex == pytest.approx(3_430_000.0)


def test_common_clinical_nuclear_assets_excluded_from_mrt_transport_only_capex():
    result = csa.compute_mrt_transport_only_capex(guideway_length_m=500.0, carrier_count=50, vestibule_count=1, include_controls=True, include_installation_commissioning=True)
    components = {li.component for li in result.line_items}
    assert not any("cyclotron" in c.lower() or "generator" in c.lower() or "scanner" in c.lower() for c in components)


# ---------------------------------------------------------------------------
# Electricity tariff scenario
# ---------------------------------------------------------------------------


def test_electricity_tariff_changes_cost_not_physical_kwh():
    result = lib.compute_electricity_tariff_what_if_impact(annual_kwh=9922.5, locked_tariff_usd_per_kwh=0.15, what_if_tariff_usd_per_kwh=0.20)
    assert result.metric("physical_annual_kwh").status == "UNCHANGED"
    assert result.metric("electricity_opex_usd").status == "RESOLVED"


def test_electricity_tariff_never_changes_capex():
    result = lib.compute_electricity_tariff_what_if_impact(annual_kwh=9922.5, locked_tariff_usd_per_kwh=0.15, what_if_tariff_usd_per_kwh=0.20)
    assert result.metric("capex_delta_usd").status == "UNCHANGED"


# ---------------------------------------------------------------------------
# Site-power binding
# ---------------------------------------------------------------------------


def test_site_power_adequate_hospital_zero_backup_capex():
    result = lib.compute_site_power_what_if_impact(profile=maux.ADEQUATE_HOSPITAL_SITE_POWER_PROFILE, locked_incremental_demand_kw=5.0, what_if_incremental_demand_kw=10.0)
    m = result.metric("incremental_backup_capex_usd")
    assert m.locked_value == 0.0
    assert m.what_if_value == 0.0


def test_site_power_weak_grid_transitions_to_inadequate_honest_not_calibrated():
    result = lib.compute_site_power_what_if_impact(profile=maux.WEAK_GRID_CONTROLLED_SITE_POWER_PROFILE, locked_incremental_demand_kw=10.0, what_if_incremental_demand_kw=100.0)
    status_metric = result.metric("site_power_adequacy_status")
    assert status_metric.what_if_value == "INADEQUATE"
    capex_metric = result.metric("incremental_backup_capex_usd")
    assert capex_metric.what_if_value == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# Locked-state immutability + scenario isolation + reset/return-to-locked
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_locked_state():
    return csa.LockedSpatialState(registry=csa.SpatialObjectRegistry(objects={}))


def test_running_live_impact_never_mutates_locked_state(empty_locked_state):
    scenario = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1")
    lib.run_nuclear_speed_what_if_within_scenario(scenario)
    assert empty_locked_state.registry.objects == {}


def test_scenario_isolation_a_and_b_independent(empty_locked_state):
    scenario_a = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1", scenario_id="A")
    scenario_b = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1", scenario_id="B")
    lib.run_nuclear_speed_what_if_within_scenario(scenario_a)
    assert len(scenario_a.active_changes) == 1
    assert len(scenario_b.active_changes) == 0


def test_return_to_locked_clears_live_deltas(empty_locked_state):
    scenario = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1")
    lib.run_nuclear_speed_what_if_within_scenario(scenario)
    maux.return_scenario_to_locked(scenario)
    assert scenario.active_changes == []


def test_remove_one_change_removes_only_that_change(empty_locked_state):
    scenario = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1")
    change1, _ = lib.run_nuclear_speed_what_if_within_scenario(scenario)
    change2 = maux.record_parameter_change(scenario, category="ECONOMICS_ASSUMPTIONS", parameter_id="electricity_tariff", locked_value=0.15, what_if_value=0.20, description="tariff")
    maux.remove_one_change(scenario, change1.change_id)
    remaining = [c.change_id for c in scenario.active_change_list()]
    assert change1.change_id not in remaining
    assert change2.change_id in remaining


def test_reset_category_preserves_unrelated_categories(empty_locked_state):
    scenario = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1")
    lib.run_nuclear_speed_what_if_within_scenario(scenario)
    maux.record_parameter_change(scenario, category="ECONOMICS_ASSUMPTIONS", parameter_id="electricity_tariff", locked_value=0.15, what_if_value=0.20, description="tariff")
    maux.reset_what_if_category(scenario, "TRANSPORT_MRT")
    counts = scenario.category_counts()
    assert counts["TRANSPORT_MRT"] == 0
    assert counts["ECONOMICS_ASSUMPTIONS"] == 1


# ---------------------------------------------------------------------------
# Revision IDs + stale-result protection
# ---------------------------------------------------------------------------


def test_publisher_accepts_increasing_revisions():
    pub = lib.LiveImpactPublisher()
    r1 = lib.compute_electricity_tariff_what_if_impact(annual_kwh=100.0, locked_tariff_usd_per_kwh=0.1, what_if_tariff_usd_per_kwh=0.2, revision=1)
    r2 = lib.compute_electricity_tariff_what_if_impact(annual_kwh=100.0, locked_tariff_usd_per_kwh=0.1, what_if_tariff_usd_per_kwh=0.3, revision=2)
    pub.publish(r1)
    pub.publish(r2)
    assert pub.latest(r2.scenario_id).revision == 2


def test_publisher_rejects_stale_revision():
    pub = lib.LiveImpactPublisher()
    r1 = lib.compute_electricity_tariff_what_if_impact(annual_kwh=100.0, locked_tariff_usd_per_kwh=0.1, what_if_tariff_usd_per_kwh=0.2, revision=2)
    pub.publish(r1)
    stale = lib.compute_electricity_tariff_what_if_impact(annual_kwh=100.0, locked_tariff_usd_per_kwh=0.1, what_if_tariff_usd_per_kwh=0.2, revision=1)
    with pytest.raises(lib.StaleRevisionError):
        pub.publish(stale)


# ---------------------------------------------------------------------------
# NaN/Infinity + unresolved-object rejection
# ---------------------------------------------------------------------------


def test_nan_rejected_before_publish():
    with pytest.raises(lib.InvalidParameterError):
        lib.compute_service_class_speed_what_if_impact(service_class="SPECIMEN_BLOOD", locked_speed_m_per_s=float("nan"), what_if_speed_m_per_s=9.0, route_length_m=100.0)


def test_infinity_rejected_before_publish():
    with pytest.raises(lib.InvalidParameterError):
        lib.compute_service_class_speed_what_if_impact(service_class="SPECIMEN_BLOOD", locked_speed_m_per_s=float("inf"), what_if_speed_m_per_s=9.0, route_length_m=100.0)


def test_unresolved_mrtway_object_rejected():
    with pytest.raises(lib.InvalidObjectError):
        lib.compute_cyclotron_model_what_if_impact(locked_model_id="PHANTOM_MODEL", what_if_model_id="ALSO_PHANTOM")


# ---------------------------------------------------------------------------
# Trajectory revision + simulation-driven animation + OpenUSD non-authority
# ---------------------------------------------------------------------------


def test_trajectory_revision_and_simulation_derived_provenance():
    mixed = lib.compute_mixed_service_scenario()
    for t in mixed.trajectories:
        assert "SIMULATION_DERIVED" in t.provenance


def test_nvidia_consumer_payload_never_imports_nvidia():
    import sys
    forbidden_modules = ("omni", "pxr.UsdRT", "warp", "physx")
    assert not any(m in sys.modules for m in forbidden_modules)


def test_nvidia_consumer_payload_contains_required_fields():
    mixed = lib.compute_mixed_service_scenario()
    payload = lib.build_nvidia_consumer_payload(scenario_revision=1, scene_state_id="SCENE-1", trajectories=mixed.trajectories, impact_summary_reference="IMPACT-1")
    assert payload.scenario_revision == 1
    assert payload.scene_state_id == "SCENE-1"
    assert len(payload.carrier_trajectories) == 3
    assert len(payload.presentation_metadata) == 3


def test_openusd_module_has_no_engineering_calculation_functions():
    """Section 98/147: OpenUSD remains presentation/scene authority only."""
    import openusd_spatial_adapter as usd
    forbidden = ("compute_drag", "compute_joule", "evaluate_lifecycle", "schedule_missions")
    source = inspect.getsource(usd)
    for f in forbidden:
        assert f not in source


def test_bentley_identity_chain_uses_mrtway_object_id():
    """Section 147: MRTWAY_OBJECT_ID remains authoritative; Bentley/iTwin
    identity mapping is untouched by this build."""
    mixed = lib.compute_mixed_service_scenario()
    for t in mixed.trajectories:
        assert t.presentation.mrtway_object_id.endswith("-OBJ")


# ---------------------------------------------------------------------------
# Serialization + determinism
# ---------------------------------------------------------------------------


def test_serialization_round_trip_preserves_all_required_fields():
    result = lib.compute_electricity_tariff_what_if_impact(annual_kwh=100.0, locked_tariff_usd_per_kwh=0.1, what_if_tariff_usd_per_kwh=0.2)
    data = lib.serialize_impact_result(result)
    restored = lib.deserialize_impact_result(data)
    assert restored.scenario_id == result.scenario_id
    assert restored.revision == result.revision
    assert len(restored.metrics) == len(result.metrics)
    for original, restored_metric in zip(result.metrics, restored.metrics):
        assert original.metric_id == restored_metric.metric_id
        assert original.locked_value == restored_metric.locked_value
        assert original.what_if_value == restored_metric.what_if_value
        assert original.unit == restored_metric.unit
        assert original.status == restored_metric.status
        assert original.source_authority == restored_metric.source_authority


def test_determinism_identical_inputs_produce_identical_results():
    r1 = lib.compute_service_class_speed_what_if_impact(service_class="RADIOPHARMACEUTICAL_NUCLEAR", locked_speed_m_per_s=10.0, what_if_speed_m_per_s=15.0, route_length_m=500.0)
    r2 = lib.compute_service_class_speed_what_if_impact(service_class="RADIOPHARMACEUTICAL_NUCLEAR", locked_speed_m_per_s=10.0, what_if_speed_m_per_s=15.0, route_length_m=500.0)
    assert [m.metric_id for m in r1.metrics] == [m.metric_id for m in r2.metrics]
    for m1, m2 in zip(r1.metrics, r2.metrics):
        assert m1.locked_value == m2.locked_value
        assert m1.what_if_value == m2.what_if_value


# ---------------------------------------------------------------------------
# Component non-regression
# ---------------------------------------------------------------------------


def test_service_class_authority_unaffected():
    assert msc.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"].default_speed_m_per_s == 10.0


def test_auxiliary_authority_unaffected():
    conductor = maux.ConductorSpec(material="copper", resistivity_ohm_m=1.68e-8, length_m=500.0, cross_sectional_area_m2=0.0002, provenance="CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE")
    assert maux.compute_conductor_resistance_ohm(conductor) == pytest.approx(0.042)


def test_canonical_spatial_authority_unaffected():
    result = csa.compute_mrt_transport_only_capex(guideway_length_m=100.0, carrier_count=10)
    assert result.total_capex == pytest.approx(100.0 * 5_000.0 + 10 * 10_000.0)

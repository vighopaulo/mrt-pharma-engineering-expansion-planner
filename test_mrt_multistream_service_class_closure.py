"""Focused tests for `mrt_service_class_authority.py` (MRT Multi-Stream
Service Classes + Mission-Specific Speed/Priority/Color closure) and its
integration points in `mrt_auxiliary_systems_authority.py`.

Covers: the seven-class registry (five active, two inactive), color/status/
accessibility, speed/priority tables, container mapping, priority override +
provenance, speed override, carrier/container/service-class separation,
shared carrier fleet non-duplication, carrier reassignment, scheduler
integration (mixed speeds, no illegal overtaking, no starvation), route
travel time using effective speed, nuclear decay reuse, general-logistics
no-fake-decay, auxiliary speed-mix energy aggregation, no-universal-10ms
assumption, unified what-if integration (nuclear 10->15 m/s, blood/linen
unaffected), demand-mix what-if, inactive-stream zero-impact, future
activation contract, OpenUSD presentation metadata + identity round-trip,
trajectory/animation contract, and locked/auxiliary-authority non-regression.
"""

import pytest

import mrt_auxiliary_systems_authority as maux
import mrt_service_class_authority as msc
import shared_mrt_multistream_authority as smx


# ---------------------------------------------------------------------------
# Service-class registry
# ---------------------------------------------------------------------------


def test_seven_service_classes_exist():
    assert set(msc.SERVICE_CLASS_REGISTRY.keys()) == {
        "RADIOPHARMACEUTICAL_NUCLEAR", "SPECIMEN_BLOOD", "PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY",
        "LAUNDRY_CLEAN_LINEN", "FOOD_NUTRITION", "WASTE",
    }


def test_five_active_two_inactive():
    active = [sc for sc, p in msc.SERVICE_CLASS_REGISTRY.items() if p.activity_status == "ACTIVE"]
    inactive = [sc for sc, p in msc.SERVICE_CLASS_REGISTRY.items() if p.activity_status == "INACTIVE_FUTURE_CAPABILITY"]
    assert len(active) == 5
    assert set(inactive) == {"FOOD_NUTRITION", "WASTE"}


def test_food_and_waste_inactive():
    assert msc.SERVICE_CLASS_REGISTRY["FOOD_NUTRITION"].activity_status == "INACTIVE_FUTURE_CAPABILITY"
    assert msc.SERVICE_CLASS_REGISTRY["WASTE"].activity_status == "INACTIVE_FUTURE_CAPABILITY"


# ---------------------------------------------------------------------------
# Color / status / accessibility
# ---------------------------------------------------------------------------


def test_inactive_classes_display_gray_but_retain_configured_color():
    food = msc.SERVICE_CLASS_REGISTRY["FOOD_NUTRITION"]
    waste = msc.SERVICE_CLASS_REGISTRY["WASTE"]
    assert food.effective_display_color() == "GRAY"
    assert food.configured_active_color == "GREEN"
    assert waste.effective_display_color() == "GRAY"
    assert waste.configured_active_color == "RED"


def test_active_class_colors():
    assert msc.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"].effective_display_color() == "VIOLET"
    assert msc.SERVICE_CLASS_REGISTRY["SPECIMEN_BLOOD"].effective_display_color() == "BLUE"
    assert msc.SERVICE_CLASS_REGISTRY["PHARMACY_INFUSION"].effective_display_color() == "TEAL"
    assert msc.SERVICE_CLASS_REGISTRY["STERILE_CLEAN_SUPPLY"].effective_display_color() == "AMBER"
    assert msc.SERVICE_CLASS_REGISTRY["LAUNDRY_CLEAN_LINEN"].effective_display_color() == "GOLD"


def test_accessibility_metadata_includes_text_and_priority_not_just_color():
    profile = msc.SERVICE_CLASS_REGISTRY["SPECIMEN_BLOOD"]
    metadata = msc.build_accessible_presentation(profile)
    assert metadata.color == "BLUE"
    assert metadata.text_label == "Specimen / Blood"
    assert metadata.service_class_id == "SPECIMEN_BLOOD"
    assert metadata.priority == "PRIORITY_2_CLINICAL_URGENT"


def test_presentation_legend_contract():
    assert msc.PRESENTATION_LEGEND["VIOLET"] == "RADIOPHARMACEUTICAL_NUCLEAR"
    assert msc.PRESENTATION_LEGEND["GRAY"] == "INACTIVE_FUTURE_CAPABILITY"


# ---------------------------------------------------------------------------
# Speed / priority
# ---------------------------------------------------------------------------


def test_nuclear_default_speed_10():
    assert msc.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"].default_speed_m_per_s == 10.0
    assert msc.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"].speed_provenance == "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION"


def test_blood_default_speed_7():
    assert msc.SERVICE_CLASS_REGISTRY["SPECIMEN_BLOOD"].default_speed_m_per_s == 7.0


def test_linen_default_speed_1():
    assert msc.SERVICE_CLASS_REGISTRY["LAUNDRY_CLEAN_LINEN"].default_speed_m_per_s == 1.0


def test_pharmacy_and_sterile_speed_not_calibrated():
    assert msc.SERVICE_CLASS_REGISTRY["PHARMACY_INFUSION"].default_speed_m_per_s == "NOT_CALIBRATED"
    assert msc.SERVICE_CLASS_REGISTRY["STERILE_CLEAN_SUPPLY"].default_speed_m_per_s == "NOT_CALIBRATED"


def test_priority_ordering_p1_gt_p2_gt_p3_gt_p4():
    assert msc.PRIORITY_RANK["PRIORITY_1_NUCLEAR_CRITICAL"] < msc.PRIORITY_RANK["PRIORITY_2_CLINICAL_URGENT"]
    assert msc.PRIORITY_RANK["PRIORITY_2_CLINICAL_URGENT"] < msc.PRIORITY_RANK["PRIORITY_3_SCHEDULED_CLINICAL"]
    assert msc.PRIORITY_RANK["PRIORITY_3_SCHEDULED_CLINICAL"] < msc.PRIORITY_RANK["PRIORITY_4_ROUTINE_GENERAL"]


def test_priority_reused_from_existing_authority_not_duplicated():
    assert msc.MrtPriorityClass is smx.MrtPriorityClass


# ---------------------------------------------------------------------------
# Carrier / container / service-class separation
# ---------------------------------------------------------------------------


def test_service_class_to_container_mapping():
    assert msc.resolve_container_for_service_class("RADIOPHARMACEUTICAL_NUCLEAR").container_class_id == "NUCLEAR_SHIELDED_CONTAINER"
    assert msc.resolve_container_for_service_class("PHARMACY_INFUSION").container_class_id == "CLINICAL_CLEAN_CONTAINER"
    assert msc.resolve_container_for_service_class("STERILE_CLEAN_SUPPLY").container_class_id == "CLINICAL_CLEAN_CONTAINER"
    assert msc.resolve_container_for_service_class("LAUNDRY_CLEAN_LINEN").container_class_id == "LINEN_CONTAINER"
    assert msc.resolve_container_for_service_class("SPECIMEN_BLOOD").container_class_id == "SPECIMEN_BLOOD_CONTAINER"


def test_food_waste_container_not_fabricated():
    assert msc.resolve_container_for_service_class("FOOD_NUTRITION") == "FUTURE_CONTAINER_CLASS_REQUIRED"
    assert msc.resolve_container_for_service_class("WASTE") == "FUTURE_CONTAINER_CLASS_REQUIRED"


def test_service_class_container_carrier_are_distinct_concepts():
    profile = msc.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"]
    container = msc.resolve_container_for_service_class("RADIOPHARMACEUTICAL_NUCLEAR")
    assert profile.service_class != container.container_class_id
    mission = msc.MrtServiceMission(mission_id="M1", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    assert mission.carrier_id != mission.service_class


# ---------------------------------------------------------------------------
# Priority override + provenance
# ---------------------------------------------------------------------------


def test_priority_override_controlled_case():
    profile = msc.SERVICE_CLASS_REGISTRY["SPECIMEN_BLOOD"]
    normal = msc.resolve_effective_priority(profile)
    assert normal == "PRIORITY_2_CLINICAL_URGENT"

    override = msc.PriorityOverrideRecord(original_priority="PRIORITY_2_CLINICAL_URGENT", effective_priority="PRIORITY_1_NUCLEAR_CRITICAL", reason="STAT blood", source="clinician_override")
    stat = msc.resolve_effective_priority(profile, override=override)
    assert stat == "PRIORITY_1_NUCLEAR_CRITICAL"


def test_priority_override_provenance_retained():
    override = msc.PriorityOverrideRecord(original_priority="PRIORITY_2_CLINICAL_URGENT", effective_priority="PRIORITY_1_NUCLEAR_CRITICAL", reason="STAT blood", source="clinician_override")
    assert override.original_priority == "PRIORITY_2_CLINICAL_URGENT"
    assert override.effective_priority == "PRIORITY_1_NUCLEAR_CRITICAL"
    assert override.reason == "STAT blood"
    assert override.source == "clinician_override"


def test_priority_override_does_not_change_color_speed_service_class():
    mission_normal = msc.MrtServiceMission(mission_id="M1", carrier_id="C1", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.0)
    override = msc.PriorityOverrideRecord(original_priority="PRIORITY_2_CLINICAL_URGENT", effective_priority="PRIORITY_1_NUCLEAR_CRITICAL", reason="STAT", source="test")
    mission_stat = msc.MrtServiceMission(mission_id="M2", carrier_id="C1", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.0, priority_override=override)
    d1 = msc.build_carrier_dispatch_state(mission_normal)
    d2 = msc.build_carrier_dispatch_state(mission_stat)
    assert d1.effective_display_color == d2.effective_display_color == "BLUE"
    assert d1.effective_speed_m_per_s == d2.effective_speed_m_per_s == 7.0
    assert d1.service_class == d2.service_class
    assert d1.effective_priority != d2.effective_priority


# ---------------------------------------------------------------------------
# Speed override + independence
# ---------------------------------------------------------------------------


def test_speed_override_resolution():
    profile = msc.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"]
    assert msc.resolve_effective_speed(profile) == 10.0
    assert msc.resolve_effective_speed(profile, speed_override_m_per_s=15.0) == 15.0


def test_speed_service_color_independence():
    mission_locked = msc.MrtServiceMission(mission_id="M1", carrier_id="C1", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    mission_faster = msc.MrtServiceMission(mission_id="M2", carrier_id="C1", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0, speed_override_m_per_s=15.0)
    d1 = msc.build_carrier_dispatch_state(mission_locked)
    d2 = msc.build_carrier_dispatch_state(mission_faster)
    assert d1.effective_speed_m_per_s != d2.effective_speed_m_per_s
    assert d1.service_class == d2.service_class
    assert d1.effective_display_color == d2.effective_display_color
    assert d1.effective_priority == d2.effective_priority
    assert d1.container_class_id == d2.container_class_id


# ---------------------------------------------------------------------------
# Shared carrier fleet + reassignment
# ---------------------------------------------------------------------------


def test_carrier_reassignment_preserves_identity_changes_mission():
    nuclear = msc.MrtServiceMission(mission_id="NUC-1", carrier_id="MRT-CARRIER-017", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    blood = msc.MrtServiceMission(mission_id="BLD-2", carrier_id="MRT-CARRIER-017", service_class="SPECIMEN_BLOOD", route_length_m=50.0, start_minutes=10.0)
    d1 = msc.build_carrier_dispatch_state(nuclear)
    d2 = msc.reassign_carrier("MRT-CARRIER-017", blood)
    assert d1.carrier_id == d2.carrier_id == "MRT-CARRIER-017"
    assert d1.mission_id != d2.mission_id
    assert d1.service_class != d2.service_class
    assert d1.effective_display_color != d2.effective_display_color


def test_reassign_carrier_rejects_mismatched_carrier_id():
    mission = msc.MrtServiceMission(mission_id="M1", carrier_id="MRT-CARRIER-002", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.0)
    with pytest.raises(ValueError):
        msc.reassign_carrier("MRT-CARRIER-999", mission)


def test_no_duplicate_service_class_fleets():
    """Section 27: service classes never produce separate fleets -- only the
    ONE existing `resolve_mrt_carrier_fleet`/`compute_shared_carrier_fleet`
    authority sizes carriers, and this module never calls a per-class
    equivalent."""
    import inspect
    source = inspect.getsource(msc)
    assert "resolve_mrt_carrier_fleet" not in source  # never re-derives fleet sizing itself


# ---------------------------------------------------------------------------
# Scheduler integration -- mixed speeds, no illegal overtaking, no starvation
# ---------------------------------------------------------------------------


def test_route_travel_time_uses_effective_speed_not_universal_constant():
    nuclear = msc.MrtServiceMission(mission_id="N", carrier_id="C1", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    linen = msc.MrtServiceMission(mission_id="L", carrier_id="C2", service_class="LAUNDRY_CLEAN_LINEN", route_length_m=100.0, start_minutes=0.0)
    nuclear_time = msc.compute_mission_duration_minutes(nuclear)
    linen_time = msc.compute_mission_duration_minutes(linen)
    assert nuclear_time == pytest.approx(100.0 / 10.0 / 60.0)
    assert linen_time == pytest.approx(100.0 / 1.0 / 60.0)
    assert nuclear_time != linen_time


def test_mixed_speed_shared_segment_controlled_case():
    nuclear = msc.MrtServiceMission(mission_id="NUC-1", carrier_id="C1", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=1.0)
    blood = msc.MrtServiceMission(mission_id="BLD-1", carrier_id="C2", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.5)
    linen = msc.MrtServiceMission(mission_id="LIN-1", carrier_id="C3", service_class="LAUNDRY_CLEAN_LINEN", route_length_m=100.0, start_minutes=0.0)
    scheduled, unresolved = msc.schedule_service_missions([nuclear, blood, linen])
    assert unresolved == ()
    by_id = {s.mission_id: s for s in scheduled}
    assert by_id["NUC-1"].scheduled_start_minutes <= by_id["BLD-1"].scheduled_start_minutes
    assert by_id["BLD-1"].scheduled_start_minutes <= by_id["LIN-1"].scheduled_start_minutes


def test_slow_linen_does_not_block_nuclear_via_illegal_overtake():
    """Section 63: nuclear (higher priority) legitimately dispatches ahead of
    an earlier-arriving linen mission -- via priority ordering, never via
    teleportation (single-resource dispatch structurally prevents overtaking)."""
    linen = msc.MrtServiceMission(mission_id="LIN-1", carrier_id="C1", service_class="LAUNDRY_CLEAN_LINEN", route_length_m=100.0, start_minutes=0.0)
    nuclear = msc.MrtServiceMission(mission_id="NUC-1", carrier_id="C2", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.1)
    scheduled, _ = msc.schedule_service_missions([linen, nuclear])
    by_id = {s.mission_id: s for s in scheduled}
    assert by_id["NUC-1"].scheduled_start_minutes < by_id["LIN-1"].scheduled_start_minutes
    assert by_id["NUC-1"].wait_minutes == 0.0


def test_no_starvation_routine_traffic_eventually_dispatched():
    linen = msc.MrtServiceMission(mission_id="LIN-1", carrier_id="C1", service_class="LAUNDRY_CLEAN_LINEN", route_length_m=10.0, start_minutes=0.0)
    nuclear_missions = [
        msc.MrtServiceMission(mission_id=f"NUC-{i}", carrier_id=f"C{i}", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=10.0, start_minutes=float(i))
        for i in range(3)
    ]
    scheduled, unresolved = msc.schedule_service_missions(nuclear_missions + [linen])
    assert unresolved == ()
    mission_ids = {s.mission_id for s in scheduled}
    assert "LIN-1" in mission_ids  # never dropped, eventually dispatched


def test_blood_competitive_speed_case_no_new_pts_assumption():
    """Section 64: SPECIMEN_BLOOD at 7 m/s is a controlled MRT assumption;
    this module does not fabricate a new PTS comparator speed."""
    profile = msc.SERVICE_CLASS_REGISTRY["SPECIMEN_BLOOD"]
    assert profile.default_speed_m_per_s == 7.0
    assert profile.speed_provenance == "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION"


def test_uncalibrated_speed_mission_excluded_from_scheduling_not_defaulted():
    pharm = msc.MrtServiceMission(mission_id="PHARM-1", carrier_id="C1", service_class="PHARMACY_INFUSION", route_length_m=100.0, start_minutes=0.0)
    scheduled, unresolved = msc.schedule_service_missions([pharm])
    assert scheduled == ()
    assert len(unresolved) == 1
    assert unresolved[0].mission_id == "PHARM-1"


# ---------------------------------------------------------------------------
# Nuclear decay reuse / general logistics no fake decay
# ---------------------------------------------------------------------------


def test_nuclear_decay_reuses_existing_formula():
    nuclear = msc.MrtServiceMission(mission_id="N", carrier_id="C1", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    fraction = msc.compute_nuclear_retained_fraction_for_mission(nuclear, half_life_minutes=109.8)
    duration = msc.compute_mission_duration_minutes(nuclear)
    from multi_isotope_decay import retained_fraction
    assert fraction == retained_fraction(duration, 109.8)


def test_nuclear_decay_rejects_non_nuclear_service_class():
    blood = msc.MrtServiceMission(mission_id="B", carrier_id="C1", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.0)
    with pytest.raises(ValueError):
        msc.compute_nuclear_retained_fraction_for_mission(blood, half_life_minutes=109.8)


def test_general_logistics_has_no_decay_field():
    blood = msc.MrtServiceMission(mission_id="B", carrier_id="C1", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.0)
    assert msc.general_logistics_has_no_decay_field(blood) is True


# ---------------------------------------------------------------------------
# Auxiliary speed-mix energy integration
# ---------------------------------------------------------------------------


def test_speed_mix_aggregation_no_universal_speed():
    nuclear = msc.MrtServiceMission(mission_id="N", carrier_id="C1", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    blood = msc.MrtServiceMission(mission_id="B", carrier_id="C2", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.0)
    linen = msc.MrtServiceMission(mission_id="L", carrier_id="C3", service_class="LAUNDRY_CLEAN_LINEN", route_length_m=100.0, start_minutes=0.0)
    result = msc.aggregate_mission_speed_mix_energy([nuclear, blood, linen])
    speeds = {e.effective_speed_m_per_s for e in result.entries}
    assert speeds == {10.0, 7.0, 1.0}
    by_class = {e.service_class: e for e in result.entries}
    assert by_class["RADIOPHARMACEUTICAL_NUCLEAR"].drag_power_w != by_class["SPECIMEN_BLOOD"].drag_power_w != by_class["LAUNDRY_CLEAN_LINEN"].drag_power_w


def test_speed_mix_aggregation_uncalibrated_class_reported_not_fabricated():
    pharm = msc.MrtServiceMission(mission_id="P", carrier_id="C1", service_class="PHARMACY_INFUSION", route_length_m=100.0, start_minutes=0.0)
    result = msc.aggregate_mission_speed_mix_energy([pharm])
    assert result.entries[0].energy_resolution_status == "NOT_CALIBRATED"


def test_no_universal_10ms_production_assumption():
    """Section 71: the mission-mix aggregator groups by ACTUAL effective
    speed -- never assumes every mission travels at 10 m/s."""
    linen = msc.MrtServiceMission(mission_id="L", carrier_id="C1", service_class="LAUNDRY_CLEAN_LINEN", route_length_m=100.0, start_minutes=0.0)
    result = msc.aggregate_mission_speed_mix_energy([linen])
    assert result.entries[0].effective_speed_m_per_s == 1.0
    assert result.entries[0].effective_speed_m_per_s != 10.0


def test_thermal_concurrency_field_present_pending_not_fabricated():
    linen = msc.MrtServiceMission(mission_id="L", carrier_id="C1", service_class="LAUNDRY_CLEAN_LINEN", route_length_m=100.0, start_minutes=0.0)
    result = msc.aggregate_mission_speed_mix_energy([linen])
    assert result.thermal_resolution_status == "PENDING_ENGINEERING_RECALCULATION"


# ---------------------------------------------------------------------------
# Unified what-if integration
# ---------------------------------------------------------------------------


def test_service_class_parameters_registered_under_transport_mrt():
    registry = msc.build_service_class_aware_parameter_registry()
    ids = {d.parameter_id for d in registry.by_category("TRANSPORT_MRT")}
    assert {"service_class_active", "service_class_default_speed", "mission_speed_override", "mission_priority_override"} <= ids


def test_existing_registry_parameters_preserved():
    registry = msc.build_service_class_aware_parameter_registry()
    assert registry.resolve("carrier_speed") is not None
    assert registry.resolve("electricity_tariff") is not None


def test_nuclear_10_to_15_what_if_identity_invariants():
    check, locked, what_if = msc.compare_nuclear_speed_what_if()
    assert check.service_class_unchanged
    assert check.color_unchanged
    assert check.priority_unchanged
    assert check.container_unchanged
    assert msc.mission_effective_speed(locked) == 10.0
    assert msc.mission_effective_speed(what_if) == 15.0


def test_nuclear_what_if_does_not_alter_blood_or_linen_speed():
    blood = msc.SERVICE_CLASS_REGISTRY["SPECIMEN_BLOOD"]
    linen = msc.SERVICE_CLASS_REGISTRY["LAUNDRY_CLEAN_LINEN"]
    _check, _locked, _what_if = msc.compare_nuclear_speed_what_if(what_if_speed_m_per_s=15.0)
    assert blood.default_speed_m_per_s == 7.0
    assert linen.default_speed_m_per_s == 1.0


def test_demand_mix_what_if_only_changes_targeted_class():
    mix = {"RADIOPHARMACEUTICAL_NUCLEAR": 10, "SPECIMEN_BLOOD": 5, "LAUNDRY_CLEAN_LINEN": 20}
    new_mix = msc.apply_demand_mix_change(mix, service_class="SPECIMEN_BLOOD", new_count=8)
    assert mix["SPECIMEN_BLOOD"] == 5  # original untouched
    assert new_mix["SPECIMEN_BLOOD"] == 8
    assert new_mix["RADIOPHARMACEUTICAL_NUCLEAR"] == 10
    assert new_mix["LAUNDRY_CLEAN_LINEN"] == 20


# ---------------------------------------------------------------------------
# Inactive stream non-regression + future activation
# ---------------------------------------------------------------------------


def test_inactive_streams_zero_demand_energy_capex_opex():
    food_mission = msc.MrtServiceMission(mission_id="F1", carrier_id="C1", service_class="FOOD_NUTRITION", route_length_m=100.0, start_minutes=0.0)
    filtered = msc.filter_active_service_class_missions([food_mission])
    assert filtered == ()


def test_food_activation_blocked_without_calibration():
    result = msc.evaluate_stream_activation("FOOD_NUTRITION")
    assert result.overall_status == "ACTIVATION_BLOCKED"
    assert "default_speed_m_per_s" in result.missing_calibration_inputs
    assert "container_class" in result.missing_calibration_inputs


def test_waste_activation_blocked_without_calibration():
    result = msc.evaluate_stream_activation("WASTE", route_available=True)
    assert result.overall_status == "ACTIVATION_BLOCKED"
    assert result.route_readiness is True


def test_active_class_activation_complete():
    result = msc.evaluate_stream_activation("RADIOPHARMACEUTICAL_NUCLEAR", route_available=True)
    assert result.overall_status == "ACTIVATION_COMPLETE"
    assert result.missing_calibration_inputs == ()


# ---------------------------------------------------------------------------
# OpenUSD presentation metadata + trajectory/animation contract
# ---------------------------------------------------------------------------


class _FakePrim:
    def __init__(self):
        self.data = {}

    def SetCustomDataByKey(self, key, value):
        self.data[key] = value


def test_openusd_presentation_metadata_round_trip_identity():
    nuclear = msc.MrtServiceMission(mission_id="N1", carrier_id="MRT-CARRIER-017", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    metadata = msc.build_carrier_presentation_metadata(nuclear, mrtway_object_id="MRT-CARRIER-017-OBJ")
    prim = _FakePrim()
    msc.attach_presentation_metadata_to_prim(prim, metadata)
    assert prim.data["mrtway_object_id"] == "MRT-CARRIER-017-OBJ"
    assert prim.data["service_class"] == "RADIOPHARMACEUTICAL_NUCLEAR"
    assert prim.data["effective_display_color"] == "VIOLET"


def test_color_change_never_affects_mrtway_object_id():
    nuclear = msc.MrtServiceMission(mission_id="N1", carrier_id="MRT-CARRIER-017", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    metadata1 = msc.build_carrier_presentation_metadata(nuclear, mrtway_object_id="MRT-CARRIER-017-OBJ")
    blood = msc.MrtServiceMission(mission_id="N2", carrier_id="MRT-CARRIER-017", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=0.0)
    metadata2 = msc.build_carrier_presentation_metadata(blood, mrtway_object_id="MRT-CARRIER-017-OBJ")
    assert metadata1.mrtway_object_id == metadata2.mrtway_object_id
    assert metadata1.effective_display_color != metadata2.effective_display_color


def test_carrier_trajectory_contract_is_simulation_derived():
    nuclear = msc.MrtServiceMission(mission_id="N1", carrier_id="MRT-CARRIER-017", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    scheduled, _ = msc.schedule_service_missions([nuclear])
    trajectory = msc.build_carrier_trajectory(nuclear, scheduled[0], mrtway_object_id="MRT-CARRIER-017-OBJ", route_id="ROUTE-1", ordered_segment_ids=("SEG-1",))
    assert trajectory.start_time_minutes == scheduled[0].scheduled_start_minutes
    assert trajectory.end_time_minutes == scheduled[0].scheduled_end_minutes
    assert "SIMULATION_DERIVED" in trajectory.provenance


def test_trajectory_identity_is_per_mission_not_per_carrier():
    m1 = msc.MrtServiceMission(mission_id="MISSION-A", carrier_id="MRT-CARRIER-017", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    m2 = msc.MrtServiceMission(mission_id="MISSION-B", carrier_id="MRT-CARRIER-017", service_class="SPECIMEN_BLOOD", route_length_m=100.0, start_minutes=10.0)
    s1, _ = msc.schedule_service_missions([m1])
    s2, _ = msc.schedule_service_missions([m2])
    t1 = msc.build_carrier_trajectory(m1, s1[0], mrtway_object_id="OBJ-017")
    t2 = msc.build_carrier_trajectory(m2, s2[0], mrtway_object_id="OBJ-017")
    assert t1.carrier_id == t2.carrier_id
    assert t1.mission_id != t2.mission_id


def test_wait_status_reflects_held_for_priority():
    linen = msc.MrtServiceMission(mission_id="LIN-1", carrier_id="C1", service_class="LAUNDRY_CLEAN_LINEN", route_length_m=100.0, start_minutes=0.0)
    nuclear = msc.MrtServiceMission(mission_id="NUC-1", carrier_id="C2", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.05)
    scheduled, _ = msc.schedule_service_missions([linen, nuclear])
    by_id = {s.mission_id: s for s in scheduled}
    linen_traj = msc.build_carrier_trajectory(linen, by_id["LIN-1"], mrtway_object_id="OBJ-C1")
    assert by_id["LIN-1"].wait_minutes > 0
    assert linen_traj.status == "HELD_FOR_PRIORITY"


def test_speed_visual_status_distinguishes_configured_from_effective():
    nuclear = msc.MrtServiceMission(mission_id="N", carrier_id="C1", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0, speed_override_m_per_s=8.5)
    status = msc.build_speed_visual_status(nuclear)
    assert status.configured_speed_m_per_s == 10.0
    assert status.effective_speed_m_per_s == 8.5


def test_priority_badge_label():
    assert msc.priority_badge_label("PRIORITY_1_NUCLEAR_CRITICAL") == "P1"
    assert msc.priority_badge_label("PRIORITY_4_ROUTINE_GENERAL") == "P4"
    assert msc.priority_badge_label("NOT_CALIBRATED") == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# Tables (service-class summary, active-mission, scheduler-by-class, priority)
# ---------------------------------------------------------------------------


def test_service_class_summary_table_includes_all_seven_rows():
    rows = msc.build_service_class_summary_table()
    assert len(rows) == 7
    by_class = {r.service_class: r for r in rows}
    assert by_class["FOOD_NUTRITION"].active is False
    assert by_class["WASTE"].active is False
    assert by_class["RADIOPHARMACEUTICAL_NUCLEAR"].active is True


def test_active_mission_table_contract():
    nuclear = msc.MrtServiceMission(mission_id="N", carrier_id="C1", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    rows = msc.build_active_mission_table([nuclear], origins={"N": "RP-001"}, destinations={"N": "NM-SUITE-1"})
    assert rows[0].origin == "RP-001"
    assert rows[0].destination == "NM-SUITE-1"
    assert rows[0].color == "VIOLET"


def test_scheduler_aggregate_by_service_class():
    nuclear = msc.MrtServiceMission(mission_id="N", carrier_id="C1", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    scheduled, _ = msc.schedule_service_missions([nuclear])
    rows = msc.aggregate_scheduler_results_by_service_class(scheduled, service_class_by_mission_id={"N": "RADIOPHARMACEUTICAL_NUCLEAR"})
    assert rows[0].missions == 1
    assert rows[0].on_time == 1


def test_priority_performance_table_all_four_levels_present():
    nuclear = msc.MrtServiceMission(mission_id="N", carrier_id="C1", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    scheduled, _ = msc.schedule_service_missions([nuclear])
    rows = msc.build_priority_performance_table(scheduled)
    priorities = {r.priority_class for r in rows}
    assert priorities == {"PRIORITY_1_NUCLEAR_CRITICAL", "PRIORITY_2_CLINICAL_URGENT", "PRIORITY_3_SCHEDULED_CLINICAL", "PRIORITY_4_ROUTINE_GENERAL"}


def test_service_mission_inspector_contract_complete():
    nuclear = msc.MrtServiceMission(mission_id="N", carrier_id="C1", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=100.0, start_minutes=0.0)
    inspector = msc.build_service_mission_inspector(nuclear, origin="RP-001", destination="NM-SUITE-1")
    assert inspector.carrier_id == "C1"
    assert inspector.service_class_id == "RADIOPHARMACEUTICAL_NUCLEAR"
    assert inspector.effective_display_color == "VIOLET"
    assert inspector.default_priority == "PRIORITY_1_NUCLEAR_CRITICAL"
    assert inspector.priority_override_status == "NONE"


# ---------------------------------------------------------------------------
# Terminology compatibility (LAUNDRY_CLEAN_LINEN <-> CLEAN_LINEN)
# ---------------------------------------------------------------------------


def test_laundry_clean_linen_stream_alias_preserved():
    assert msc.LAUNDRY_CLEAN_LINEN_STREAM_ALIAS == "CLEAN_LINEN"
    assert msc.resolve_service_class_for_existing_stream("CLEAN_LINEN") == "LAUNDRY_CLEAN_LINEN"


def test_resolve_service_class_for_all_existing_streams():
    assert msc.resolve_service_class_for_existing_stream("PHARMACY_INFUSION") == "PHARMACY_INFUSION"
    assert msc.resolve_service_class_for_existing_stream("STERILE_CLEAN_SUPPLY") == "STERILE_CLEAN_SUPPLY"
    assert msc.resolve_service_class_for_existing_stream("SPECIMEN_BLOOD") == "SPECIMEN_BLOOD"
    assert msc.resolve_service_class_for_existing_stream("NUCLEAR") == "RADIOPHARMACEUTICAL_NUCLEAR"


# ---------------------------------------------------------------------------
# Non-regression: existing shared MRT multistream / auxiliary authority
# ---------------------------------------------------------------------------


def test_shared_mrt_multistream_authority_unaffected():
    """Non-regression: this closure never modifies `MrtMissionWindow`,
    `schedule_missions_on_shared_segment`, or container objects."""
    a = smx.MrtMissionWindow(mission_id="A", patient_ids=("P1",), stream_or_nuclear="CLEAN_LINEN", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=0.0, duration_minutes=10.0)
    scheduled = smx.schedule_missions_on_shared_segment((a,))
    assert scheduled[0].mission_id == "A"


def test_auxiliary_authority_previous_functions_unaffected():
    """Non-regression: prior build's core physics functions still work
    exactly as before this closure's additions."""
    conductor = maux.ConductorSpec(material="copper", resistivity_ohm_m=1.68e-8, length_m=500.0, cross_sectional_area_m2=0.0002, provenance="CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE")
    assert maux.compute_conductor_resistance_ohm(conductor) == pytest.approx(0.042)

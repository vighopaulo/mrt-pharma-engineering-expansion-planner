"""Build 3C focused regression: five-mode transport building-block invariants
and the VISUAL PAYLOAD-IDENTITY doctrine.

These tests LOCK the audit findings recorded in
FIVE_MODE_TRANSPORT_AUTHORITY_BUILD_3C.md so they cannot silently regress.
They assert authority BEHAVIOR against the physical repository, never
fabricated values, and they add NO palette/animation implementation of their
own -- they only verify the color authority that already exists in
`mrt_service_class_authority.py`.

Doctrine under test:
  - transport SHAPE/FORM identifies the transport mechanism;
  - payload COLOR identifies the substance / service class;
  - the same payload keeps the same color across MRT / PTS / RP-PTS / robotic /
    Manual (where that mode is eligible);
  - MRT persistent CARRIER identity is separate from PAYLOAD identity;
  - color is visualization metadata ONLY and never affects physics, routing,
    capacity, CapEx/OPEX or ranking.

Scope guard: this file does NOT connect four-architecture feasibility, does NOT
begin Part 3D, does NOT modify the 6/6/12 benchmark, and changes NO production
code. It is additive, read-only-style verification.
"""

from __future__ import annotations

import dataclasses
import inspect

import mrt_service_class_authority as sca
import transport_technology_authority as tta


# ---------------------------------------------------------------------------
# 1. Canonical color registry exists and is keyed to substance/service class
# ---------------------------------------------------------------------------


def test_canonical_color_registry_keyed_to_service_class():
    """P.1: each active service class has a stable configured payload color."""
    expected = {
        "RADIOPHARMACEUTICAL_NUCLEAR": "VIOLET",
        "SPECIMEN_BLOOD": "BLUE",
        "PHARMACY_INFUSION": "TEAL",
        "STERILE_CLEAN_SUPPLY": "AMBER",
        "LAUNDRY_CLEAN_LINEN": "GOLD",
    }
    for service_class, color in expected.items():
        profile = sca.SERVICE_CLASS_REGISTRY[service_class]
        assert profile.configured_active_color == color
        assert profile.effective_display_color() == color


def test_presentation_legend_is_inverse_of_active_registry():
    """P.1: the legend maps color -> service class for the active classes."""
    assert sca.PRESENTATION_LEGEND["VIOLET"] == "RADIOPHARMACEUTICAL_NUCLEAR"
    assert sca.PRESENTATION_LEGEND["BLUE"] == "SPECIMEN_BLOOD"
    assert sca.PRESENTATION_LEGEND["TEAL"] == "PHARMACY_INFUSION"
    assert sca.PRESENTATION_LEGEND["AMBER"] == "STERILE_CLEAN_SUPPLY"
    assert sca.PRESENTATION_LEGEND["GOLD"] == "LAUNDRY_CLEAN_LINEN"


def test_inactive_service_class_displays_gray_but_retains_identity():
    """P.6: inactive classes display GRAY yet never lose their configured color."""
    for service_class in ("FOOD_NUTRITION", "WASTE"):
        profile = sca.SERVICE_CLASS_REGISTRY[service_class]
        assert profile.activity_status == "INACTIVE_FUTURE_CAPABILITY"
        assert profile.effective_display_color() == "GRAY"
        assert profile.configured_active_color != "GRAY"  # identity preserved


# ---------------------------------------------------------------------------
# 2. Color is transport-independent (structural + behavioral)
# ---------------------------------------------------------------------------


def test_mission_type_has_no_transport_mode_field():
    """P.2: the color-bearing mission carries no transport-mode/technology field,
    so color cannot depend on the transport mechanism."""
    field_names = {f.name for f in dataclasses.fields(sca.MrtServiceMission)}
    assert field_names == {
        "mission_id",
        "carrier_id",
        "service_class",
        "route_length_m",
        "start_minutes",
        "speed_override_m_per_s",
        "priority_override",
        "deadline_minutes",
    }
    for name in field_names:
        assert "mode" not in name
        assert "transport" not in name
        assert "technology" not in name


def test_color_resolvers_take_no_transport_argument():
    """P.2: color helpers derive color from service class only -- no mode input."""
    assert list(inspect.signature(sca.ServiceClassProfile.effective_display_color).parameters) == ["self"]
    dispatch_params = list(inspect.signature(sca.build_carrier_dispatch_state).parameters)
    assert dispatch_params == ["mission"]


def test_transport_technology_authority_has_no_color_field():
    """P.3: the transport-MODE identity authority carries no color -- shape/form
    (not color) identifies the transport mechanism. Verified by confirming the
    module exposes technology-class identifiers but no color symbol."""
    source = inspect.getsource(tta)
    assert "MRT" in tta.ACTIVE_TRANSPORT_TECHNOLOGY_CLASSES
    assert "PNEUMATIC_TUBE" in tta.ACTIVE_TRANSPORT_TECHNOLOGY_CLASSES
    assert "MANUAL_PORTER" in tta.ACTIVE_TRANSPORT_TECHNOLOGY_CLASSES
    # No presentation color vocabulary leaks into the transport-mode authority.
    assert "PresentationColor" not in source
    assert "configured_active_color" not in source


def test_same_payload_same_color_across_carriers_and_missions():
    """P.2: the same NUCLEAR payload yields the same VIOLET color on two
    different carriers/missions -- color follows substance, not the carrier or
    the (absent) transport mode."""
    m1 = sca.MrtServiceMission(
        mission_id="M1", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        route_length_m=500.0, start_minutes=0.0,
    )
    m2 = sca.MrtServiceMission(
        mission_id="M2", carrier_id="MRT-CARRIER-002", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        route_length_m=750.0, start_minutes=30.0,
    )
    d1 = sca.build_carrier_dispatch_state(m1)
    d2 = sca.build_carrier_dispatch_state(m2)
    assert d1.effective_display_color == d2.effective_display_color == "VIOLET"
    assert d1.carrier_id != d2.carrier_id  # distinct physical carriers, same payload color


def test_different_payload_different_color_same_carrier():
    """P.2: distinct payloads carried by the SAME carrier get distinct colors."""
    nuclear = sca.MrtServiceMission(
        mission_id="N", carrier_id="MRT-CARRIER-007", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        route_length_m=500.0, start_minutes=0.0,
    )
    specimen = sca.MrtServiceMission(
        mission_id="S", carrier_id="MRT-CARRIER-007", service_class="SPECIMEN_BLOOD",
        route_length_m=500.0, start_minutes=0.0,
    )
    assert sca.build_carrier_dispatch_state(nuclear).effective_display_color == "VIOLET"
    assert sca.build_carrier_dispatch_state(specimen).effective_display_color == "BLUE"


# ---------------------------------------------------------------------------
# 3. Carrier identity separate from payload identity
# ---------------------------------------------------------------------------


def test_carrier_reassignment_preserves_carrier_identity_and_follows_payload_color():
    """P.4: reassigning a physical carrier to a different payload keeps the same
    carrier_id while the color follows the new payload/service class."""
    first = sca.MrtServiceMission(
        mission_id="MIS-1", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        route_length_m=500.0, start_minutes=0.0,
    )
    first_state = sca.build_carrier_dispatch_state(first)
    assert first_state.effective_display_color == "VIOLET"

    second = sca.MrtServiceMission(
        mission_id="MIS-2", carrier_id="MRT-CARRIER-001", service_class="SPECIMEN_BLOOD",
        route_length_m=500.0, start_minutes=60.0,
    )
    reassigned = sca.reassign_carrier("MRT-CARRIER-001", second)
    assert reassigned.carrier_id == "MRT-CARRIER-001"  # carrier identity persists
    assert reassigned.effective_display_color == "BLUE"  # color follows the new payload


def test_reassign_carrier_rejects_mismatched_carrier_id():
    """P.4: carrier identity is authoritative -- a mission for a different carrier
    cannot be reassigned under the wrong carrier_id."""
    mission = sca.MrtServiceMission(
        mission_id="MIS-X", carrier_id="MRT-CARRIER-002", service_class="SPECIMEN_BLOOD",
        route_length_m=500.0, start_minutes=0.0,
    )
    try:
        sca.reassign_carrier("MRT-CARRIER-001", mission)
        assert False, "expected ValueError for mismatched carrier_id"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# 4. Color is visualization metadata only -- never physics/priority/economics
# ---------------------------------------------------------------------------


def test_speed_what_if_leaves_color_unchanged():
    """P.5: the mandatory nuclear 10->15 m/s what-if changes only speed; color,
    service class, priority and container are all unchanged."""
    check, locked, what_if = sca.compare_nuclear_speed_what_if(
        locked_speed_m_per_s=10.0, what_if_speed_m_per_s=15.0, route_length_m=500.0
    )
    assert check.color_unchanged is True
    assert check.service_class_unchanged is True
    assert check.priority_unchanged is True
    assert check.container_unchanged is True
    # And the speed genuinely differs (guard against a no-op false positive).
    assert locked.speed_override_m_per_s != what_if.speed_override_m_per_s


def test_effective_speed_and_priority_are_independent_of_color():
    """P.5: effective speed and priority resolve from service-class defaults /
    overrides, never from color. Two classes with the SAME... (not applicable,
    colors differ) -- instead verify a color change is impossible without a
    service-class change, and speed/priority come from the profile."""
    profile = sca.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"]
    mission = sca.MrtServiceMission(
        mission_id="M", carrier_id="C", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        route_length_m=500.0, start_minutes=0.0,
    )
    assert sca.mission_effective_speed(mission) == profile.default_speed_m_per_s
    assert sca.mission_effective_priority(mission) == profile.default_priority
    # A speed override changes speed but not color.
    faster = dataclasses.replace(mission, speed_override_m_per_s=15.0)
    assert sca.mission_effective_speed(faster) == 15.0
    assert (
        sca.build_carrier_dispatch_state(faster).effective_display_color
        == sca.build_carrier_dispatch_state(mission).effective_display_color
    )


def test_color_not_the_only_identifier_accessibility():
    """P.6: color is always accompanied by text label, service-class id and
    priority (color is never the sole identification mechanism)."""
    profile = sca.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"]
    meta = sca.build_accessible_presentation(profile)
    assert meta.color == "VIOLET"
    assert meta.text_label == profile.display_name
    assert meta.service_class_id == "RADIOPHARMACEUTICAL_NUCLEAR"
    assert meta.priority == profile.default_priority


# ---------------------------------------------------------------------------
# 5. Presentation metadata is customData only (never authoritative geometry)
# ---------------------------------------------------------------------------


class _FakePrim:
    """Duck-typed stand-in exposing SetCustomDataByKey, mirroring the USD prim
    contract the authority targets -- no pxr dependency required."""

    def __init__(self) -> None:
        self.custom_data: dict[str, object] = {}

    def SetCustomDataByKey(self, key: str, value: object) -> None:  # noqa: N802 (USD API name)
        self.custom_data[key] = value


def test_presentation_metadata_written_as_customdata_only():
    """P.5/P.3: carrier presentation (incl. color) is attached as USD customData
    only -- it never becomes authoritative geometry/identity."""
    mission = sca.MrtServiceMission(
        mission_id="MIS-1", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        route_length_m=500.0, start_minutes=0.0,
    )
    metadata = sca.build_carrier_presentation_metadata(mission, mrtway_object_id="MRTWAY-1")
    prim = _FakePrim()
    sca.attach_presentation_metadata_to_prim(prim, metadata)
    assert prim.custom_data["effective_display_color"] == "VIOLET"
    assert prim.custom_data["service_class"] == "RADIOPHARMACEUTICAL_NUCLEAR"
    assert prim.custom_data["mrtway_object_id"] == "MRTWAY-1"


# ===========================================================================
# Build 3C ADDENDUM -- visual-identity & route semantics.
# Tests assert ONLY against physically existing authorities. Where an authority
# is NOT_MODELED (payload delivery-state, room color, canonical patient palette)
# the test asserts the ABSENCE honestly rather than fabricating behavior.
# ===========================================================================

import openusd_yc_demo_binding as ycd
import production_trajectory_authority as pta


# ADD-1. Payload/service-class color is a SEPARATE authority from entity (form) color.
def test_add1_payload_color_separate_from_entity_color():
    # Service-class (payload) palette lives in mrt_service_class_authority.
    nuclear = sca.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"]
    assert nuclear.configured_active_color == "VIOLET"
    # Entity (form) colors are a DIFFERENT mapping keyed by entity_type.
    assert "PATIENT" in ycd._ENTITY_DISPLAY_COLOR
    # The two authorities are structurally distinct (payload color is not an entity color).
    assert nuclear.configured_active_color not in ycd._ENTITY_DISPLAY_COLOR


# ADD-2. Payload delivery-state is NOT_MODELED (assert absence honestly).
def test_add2_payload_delivery_state_not_modeled():
    import dynamic_scene_state_authority as dss
    import dataclasses
    fields = {f.name for f in dataclasses.fields(dss.DynamicObjectState)}
    # No payload / delivered / consumed / absorbed field exists on the scene object state.
    assert not ({"payload", "delivered", "consumed", "absorbed"} & fields)


# ADD-3. Patient color is keyed by entity_type only -> never changes with payload.
def test_add3_patient_color_stable_independent_of_payload():
    # Patient color is a single per-entity-type value; there is no payload argument.
    assert ycd._ENTITY_DISPLAY_COLOR["PATIENT"] == (0.15, 0.75, 0.30)
    # It is distinct from every service-class payload color name (no overlap of authorities).
    assert isinstance(ycd._ENTITY_DISPLAY_COLOR["PATIENT"], tuple)


# ADD-4. Room color is NOT_MODELED (assert absence honestly).
def test_add4_room_color_not_modeled():
    assert "ROOM" not in ycd._ENTITY_DISPLAY_COLOR
    assert "PATIENT_ROOM" not in ycd._ENTITY_DISPLAY_COLOR


# ADD-5. Staff/porter color is distinct from patient color and from payload palette.
def test_add5_staff_color_distinct():
    porter = ycd._ENTITY_DISPLAY_COLOR["MANUAL_PORTER"]
    patient = ycd._ENTITY_DISPLAY_COLOR["PATIENT"]
    assert porter != patient  # human resource identity distinct from patient
    # Payload semantics use a named-literal palette, not RGB entity tuples -> separate authority.
    assert isinstance(porter, tuple) and isinstance(sca.SERVICE_CLASS_REGISTRY["SPECIMEN_BLOOD"].configured_active_color, str)


# ADD-6. Patient and staff/porter XYZT trajectory builders exist and are distinct entity types.
def test_add6_patient_and_staff_xyzt_builders_exist():
    assert callable(pta.build_patient_trajectory)
    assert callable(pta.build_porter_trajectory)
    import inspect
    src = inspect.getsource(pta._build_human_trajectory)
    # Distinct entity types over ONE shared human network (PATIENT_MOVEMENT vs WALKING_PORTER).
    assert "PATIENT_MOVEMENT" in src and "WALKING_PORTER" in src


# ADD-7. Manual route uses the human circulation network, never straight-line-through-walls.
def test_add7_manual_uses_human_corridors_not_straight_line():
    import inspect
    src = inspect.getsource(pta._build_human_trajectory)
    assert "never straight-line-through-walls" in src
    # Manual/porter human trajectory is built via the pedestrian route resolver.
    assert "resolve_pedestrian_route" in src


# ADD-8. Automated route networks are distinct per mode (separate canonical authorities).
def test_add8_automated_route_networks_distinct():
    import rght_spatial_network_authority as rght
    import pts_spatial_network_authority as ptsna
    # Each automated mode has its own canonical transport-mode tag / network authority.
    assert rght.RGHT_TRANSPORT_MODE == "AGV_AMR"
    assert ptsna.PTS_TRANSPORT_MODE == "PNEUMATIC_TUBE"
    assert rght.RGHT_TRANSPORT_MODE != ptsna.PTS_TRANSPORT_MODE


# ADD-9. Geometry-change -> route recomputation readiness exists (MRT native + resolver).
def test_add9_geometry_route_recomputation_readiness():
    import authoritative_geometry_routing_activation as agra
    import transport_mission_route_bridge as tmrb
    # A resolver exists to turn canonical geometry into automatic route distance.
    assert callable(agra.resolve_automatic_route_distance_m)
    # A mode-neutral route front-door exists that recomputes distance from geometry.
    assert callable(tmrb.resolve_mission_route)


# ===========================================================================
# Build 3C TEST-COVERAGE RECONCILIATION ADDENDUM -- transport building-block
# economics/eligibility/sizing invariants (prompt invariants 1-23).
#
# The original committed suite (above) protects the VISUAL payload-identity,
# trajectory and route-semantics doctrine (invariants 24-26). These additional
# tests lock the composable-building-block invariants that were otherwise
# UNPROTECTED. Every assertion is against a physically-existing authority
# verified this session -- no composition-engine behavior is fabricated, and
# no engine code is modified. Where only an underlying authority exists (not a
# unified composition object), the test asserts that underlying authority and
# the doctrine documents the composition gap.
# ===========================================================================

from datetime import datetime as _dt, timedelta as _td

import conventional_transport_authority as _cta
import dedicated_rp_pts_authority as _rp
import mrt_carrier_fleet as _mcf
import shared_mrt_multistream_authority as _smx
from general_oncology_logistics import TransportMission as _TransportMission

_BB_BASE = _dt(2026, 1, 1, 8, 0, 0)


def _bb_missions(mode: str, count: int, minutes: int, prefix: str) -> tuple[_TransportMission, ...]:
    return tuple(
        _TransportMission(
            mission_id=f"{prefix}{i}", load_id=f"L{prefix}{i}", transport_mode=mode, origin="A", destination="B",
            departure_datetime=_BB_BASE, arrival_datetime=_BB_BASE + _td(minutes=minutes), patient_ids=("P",),
        )
        for i in range(count)
    )


# Invariant 1 + 2: transport modes are composable building blocks; MRT not required.
def test_bb01_modes_are_building_blocks_mrt_not_required():
    # Five distinct building-block authorities are independently discoverable.
    assert {"MANUAL_PORTER", "PORTER_CART", "AGV_AMR", "PNEUMATIC_TUBE"} <= set(_cta.TECHNOLOGY_STREAM_COMPATIBILITY)
    assert _rp.RP_PTS_COMPATIBLE_STREAMS  # RP-PTS
    assert _smx.evaluate_light_mrt_stream_compatibility("SPECIMEN_BLOOD").compatible  # MRT
    # MRT is never forced: it is mass-ineligible for bulky linen and speed-uncalibrated
    # for pharmacy/sterile -> a valid solution can exclude it entirely.
    assert not _smx.evaluate_light_mrt_stream_compatibility("CLEAN_LINEN").compatible


# Invariant 4: a no-MRT composition is valid (every assignment is an eligible real block).
def test_bb02_no_mrt_composition_valid():
    no_mrt = {
        "RADIOPHARMACEUTICAL_NUCLEAR": "RP_PTS",
        "SPECIMEN_BLOOD": "PNEUMATIC_TUBE",
        "PHARMACY_INFUSION": "AGV_AMR",
        "CLEAN_LINEN": "MANUAL_PORTER",
    }
    assert "MRT" not in no_mrt.values()
    assert "RADIOPHARMACEUTICAL_NUCLEAR" in _rp.RP_PTS_COMPATIBLE_STREAMS
    assert _cta.is_technology_compatible("PNEUMATIC_TUBE", "SPECIMEN_BLOOD")
    assert _cta.is_technology_compatible("AGV_AMR", "PHARMACY_INFUSION")
    assert _cta.is_technology_compatible("MANUAL_PORTER", "CLEAN_LINEN")


# Invariant 3: a mixed MRT + other-mode composition is valid.
def test_bb03_mixed_mrt_plus_other_mode_valid():
    assert _smx.evaluate_light_mrt_stream_compatibility("SPECIMEN_BLOOD").compatible  # MRT block
    assert _cta.is_technology_compatible("AGV_AMR", "CLEAN_LINEN")                    # non-MRT block
    assert _cta.is_technology_compatible("MANUAL_PORTER", "PHARMACY_INFUSION")        # manual block


# Invariant 5: Manual remains a valid building block with real timing.
def test_bb04_manual_is_valid_building_block():
    assert _cta.is_technology_compatible("MANUAL_PORTER", "CLEAN_LINEN")
    timing = _cta.compute_manual_mission_timing(
        policy=_cta.PorterOperatingPolicy(), technology="MANUAL_PORTER", horizontal_distance_m=None,
    )
    assert timing.total_minutes > 0 and timing.return_minutes > 0


# Invariant 6: service-class eligibility differs by mode (direct matrix assertion).
def test_bb05_eligibility_differs_by_service_class():
    assert _cta.is_technology_compatible("PNEUMATIC_TUBE", "SPECIMEN_BLOOD")
    assert not _cta.is_technology_compatible("PNEUMATIC_TUBE", "CLEAN_LINEN")
    assert _cta.is_technology_compatible("AGV_AMR", "CLEAN_LINEN")
    assert not _cta.is_technology_compatible("AGV_AMR", "SPECIMEN_BLOOD")


# Invariant 7: Ordinary PTS is not universally eligible (bulk streams excluded).
def test_bb06_ordinary_pts_not_universally_eligible():
    assert "CLEAN_LINEN" not in _cta.DEFAULT_PTS_NETWORK.compatible_streams
    assert "STERILE_CLEAN_SUPPLY" not in _cta.DEFAULT_PTS_NETWORK.compatible_streams


# Invariant 8: RP-PTS is distinct from Ordinary PTS (stream eligibility, not just network tag).
def test_bb07_rp_pts_distinct_from_ordinary_pts():
    assert _rp.RP_PTS_COMPATIBLE_STREAMS == frozenset({"RADIOPHARMACEUTICAL_NUCLEAR"})
    assert "RADIOPHARMACEUTICAL_NUCLEAR" not in _cta.DEFAULT_PTS_NETWORK.compatible_streams
    assert _rp.RP_PTS_INSTALLED_STATIONS == 2 and _rp.RP_PTS_SERVED_FLOORS == 1


# Invariant 9: porter concurrency / resource sizing is peak-constrained.
def test_bb08_porter_concurrency_resource_constrained():
    req = _cta.compute_porter_resource_requirement(
        missions=_bb_missions("MANUAL", 3, 20, "BBP"), mission_minutes=20.0,
        policy=_cta.PorterOperatingPolicy(), operating_days_per_year=300,
    )
    assert req.peak_concurrent_porters == 3
    assert req.required_fte >= req.peak_concurrent_porters


# Invariant 10: robotic fleet concurrency / resource sizing.
def test_bb09_robotic_fleet_sizing():
    fleet = _cta.agv_required_fleet_size(
        missions=_bb_missions("AGV_AMR", 3, 30, "BBA"), mission_minutes=30.0, model=_cta.DEFAULT_AGV_MODEL,
        operating_hours_per_day=18.0, operating_days_per_year=300,
    )
    assert fleet >= 1
    assert _cta.agv_required_fleet_size(
        missions=(), mission_minutes=30.0, model=_cta.DEFAULT_AGV_MODEL,
        operating_hours_per_day=18.0, operating_days_per_year=300,
    ) == 0


# Invariant 11: Ordinary PTS carrier/station resource sizing (not free/unlimited).
def test_bb10_pts_station_sizing_not_free():
    n = _cta.pts_required_station_count(
        missions=_bb_missions("PNEUMATIC_TUBE", 4, 5, "BBT"), mission_minutes=5.0, network=_cta.DEFAULT_PTS_NETWORK,
        operating_hours_per_day=18.0, operating_days_per_year=300,
    )
    assert n >= 1
    proposed = _cta.PneumaticTubeNetwork(**{**_cta.DEFAULT_PTS_NETWORK.__dict__, "asset_status": "PROPOSED"})
    assert _cta.pts_new_study_capex(proposed, study_scope="CAPITAL_PLANNING") > 0


# Invariant 12: RP-PTS carrier/infrastructure sizing (not free/unlimited).
def test_bb11_rp_pts_not_free():
    capex = _rp.compute_rp_pts_capex()
    assert capex.total_capex > 0
    assert capex.shielding_certification_delta_capex is None  # NOT_CALIBRATED, never $0


# Invariant 13: authoritative MRT carrier fleet/CapEx exists (richer authority MODELED).
def test_bb12_richer_mrt_carrier_capex_modeled():
    result = _mcf.resolve_mrt_carrier_fleet(distribution_concurrency=3)
    assert result.carrier_capex_modeled and result.carrier_opex_modeled and result.carrier_energy_modeled
    assert "PROJECT_PLANNING_ASSUMPTION" in result.carrier_capex_status


# Invariant 14: legacy equal_budget MRT carrier limitation remains unchanged (NOT_MODELED).
def test_bb13_legacy_equal_budget_mrt_carrier_not_modeled():
    import equal_budget as _eb
    from models import PlannerInputs as _PI, PlannerAssumptions as _PA
    inputs = _PI(
        project_name="t", current_patients_per_day=30.0, target_patients_per_day=45.0,
        maximum_expected_demand_per_day=45.0, current_scanners=2, current_injection_rooms=2,
        current_uptake_rooms=2, has_existing_cyclotron=False, current_usable_doses_per_day=30.0,
        current_average_transport_min=8.0, mrt_transport_min=3.0, conventional_transport_min=8.0,
        existing_mrt_connectable_rooms=2, representative_radionuclide="F-18",
        representative_half_life_min=109.8, selected_cyclotron_radionuclide="F-18", cyclotron_fleet=None,
    )
    mrt = _eb.maximize_mrt_capacity(inputs, _PA(), 109.8, 35_000_000.0)
    components = {item["component"] for item in mrt.capex_ledger}
    assert not any("carrier" in c.lower() for c in components)


# Invariant 15: first-mile/last-mile end-to-end parity (no silent zero last mile).
def test_bb14_first_last_mile_parity():
    policy = _cta.PorterOperatingPolicy()
    manual = _cta.compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=None)
    assert manual.return_minutes > 0
    pts_chain = _cta.compute_automated_conventional_distribution_timing(
        policy=policy, main_leg_technology="PNEUMATIC_TUBE", pts_network=_cta.DEFAULT_PTS_NETWORK,
    )
    assert pts_chain.manual_last_mile_minutes > 0
    assert _cta.LANDING_POINT_LAST_MILE_DISTANCE_M > 0


# Invariant 16: composite CapEx includes all required constituent systems.
def test_bb15_composite_capex_sums_constituents():
    proposed_agv = _cta.AgvModelClass(**{**_cta.DEFAULT_AGV_MODEL.__dict__, "asset_status": "PROPOSED"})
    agv = _cta.agv_new_study_capex(proposed_agv, fleet_size=2, study_scope="CAPITAL_PLANNING")
    proposed_pts = _cta.PneumaticTubeNetwork(**{**_cta.DEFAULT_PTS_NETWORK.__dict__, "asset_status": "PROPOSED"})
    pts = _cta.pts_new_study_capex(proposed_pts, study_scope="CAPITAL_PLANNING")
    rp_capex = _rp.compute_rp_pts_capex().total_capex
    assert agv > 0 and pts > 0 and rp_capex > 0
    assert (agv + pts + rp_capex) > max(agv, pts, rp_capex)


# Invariant 17: composite OPEX includes all required constituent systems.
def test_bb16_composite_opex_sums_constituents():
    loaded = 100_000.0
    agv = _cta.agv_annual_opex(_cta.DEFAULT_AGV_MODEL, fleet_size=2, loaded_annual_cost_per_fte=loaded)
    pts = _cta.pts_annual_opex(_cta.DEFAULT_PTS_NETWORK, loaded_annual_cost_per_fte=loaded)
    rp_opex = _rp.compute_rp_pts_opex(human_labor_annual_opex=0.0, human_labor_fte=0.0).total_calibrated_annual_opex
    assert agv > 0 and pts > 0 and rp_opex > 0


# Invariant 18: shared infrastructure is not double-counted.
def test_bb17_shared_infrastructure_not_double_counted():
    container = _smx.DEFAULT_NUCLEAR_SHIELDED_CONTAINER
    assert container.unit_capex == "ALREADY_INCLUDED_IN_EXISTING_MRT_CARRIER_AUTHORITY"
    assert container.calibration_status == "ALREADY_INCLUDED_ELSEWHERE"


# Invariant 19: separate dedicated systems are not falsely merged.
def test_bb18_separate_systems_not_merged():
    assert _cta.DEFAULT_PTS_NETWORK.compatible_streams != _rp.RP_PTS_COMPATIBLE_STREAMS
    assert "RADIOPHARMACEUTICAL_NUCLEAR" not in _cta.DEFAULT_PTS_NETWORK.compatible_streams


# Invariant 20: transport capacity does not create patient demand.
def test_bb19_transport_capacity_does_not_create_demand():
    assert _cta.agv_required_fleet_size(
        missions=(), mission_minutes=30.0, model=_cta.DEFAULT_AGV_MODEL,
        operating_hours_per_day=18.0, operating_days_per_year=300,
    ) == 0
    assert _cta.pts_required_station_count(
        missions=(), mission_minutes=5.0, network=_cta.DEFAULT_PTS_NETWORK,
        operating_hours_per_day=18.0, operating_days_per_year=300,
    ) == 0


# Invariant 21: excess transport/clinical capacity is headroom, never revenue (Build 3A).
def test_bb20_excess_capacity_is_headroom_not_revenue():
    import equal_budget as _eb
    from models import PlannerInputs as _PI, PlannerAssumptions as _PA
    inputs = _PI(
        project_name="t", current_patients_per_day=30.0, target_patients_per_day=45.0,
        maximum_expected_demand_per_day=45.0, current_scanners=2, current_injection_rooms=2,
        current_uptake_rooms=2, has_existing_cyclotron=False, current_usable_doses_per_day=30.0,
        current_average_transport_min=8.0, mrt_transport_min=3.0, conventional_transport_min=8.0,
        existing_mrt_connectable_rooms=2, representative_radionuclide="F-18",
        representative_half_life_min=109.8, selected_cyclotron_radionuclide="F-18", cyclotron_fleet=None,
    )
    conv = _eb.maximize_conventional_capacity(inputs, _PA(), 109.8, 35_000_000.0)
    assert conv.revenue_generating_throughput_per_day <= 45.0  # capped at demand
    assert conv.reserve_capacity_above_expected_demand_per_day == max(0.0, conv.achieved_capacity_per_day - 45.0)


# Invariant 22: NO_BUILD remains a valid retrofit result (Build 3A.2 identity).
def test_bb21_no_build_baseline_identity_present():
    import equal_budget as _eb
    import inspect as _inspect
    assert "NO_BUILD_BASELINE" in _inspect.getsource(_eb.maximize_mrt_capacity)


# Invariant 23: Build 3B production authority remains preserved (both controls).
def test_bb22_build3b_production_authority_preserved():
    import cyclotron_catalog as _cc
    from cyclotron_production_windows import resolve_fleet_eob_capacity_mbq_per_day as _resolve
    # Uncalibrated CYPRIS MP-30 -> None (no fabricated capacity).
    inst_u = _cc.create_facility_cyclotron_instance(catalog_model_id="SUMITOMO_CYPRIS_MP_30", existing_instances=())
    fleet_u, warns = _cc.build_fleet_from_instances(catalog=_cc.load_cyclotron_catalog(), instances=(inst_u,))
    assert fleet_u is None and warns
    # Calibrated positive control -> schedule-derived capacity.
    inst_c = _cc.create_facility_cyclotron_instance(catalog_model_id="GE_PETTRACE_840", existing_instances=())
    fleet_c, _ = _cc.build_fleet_from_instances(catalog=_cc.load_cyclotron_catalog(), instances=(inst_c,))
    cap, status = _resolve(fleet=fleet_c, radionuclide="F-18", production_batches_per_day=1)
    assert cap == 240000.0 and status == "schedule_derived_capacity"

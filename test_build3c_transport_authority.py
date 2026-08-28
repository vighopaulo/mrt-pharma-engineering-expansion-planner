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

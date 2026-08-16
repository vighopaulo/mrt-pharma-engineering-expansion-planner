from __future__ import annotations

import pytest

from facility_engineering_model import (
    CoordinateSystem,
    SpatialCoordinate,
    build_default_facility_engineering_object_model,
    deserialize_facility_engineering_object_model,
    migrate_legacy_geometry_state,
    network_route_distance_m,
    resolve_subscription_capability_profile,
    serialize_facility_engineering_object_model,
    straight_line_distance_m,
    validate_facility_engineering_object_model,
)


def _coordinate_system(*, scale: float | None = 1.0) -> CoordinateSystem:
    return CoordinateSystem(
        coordinate_system_id="LOCAL-1",
        name="Local engineering coordinates",
        building="Building A",
        storey="Level 1",
        local_coordinate_system="LOCAL",
        source_coordinate_reference="manual definition",
        scale_m_per_unit=scale,
    )


def test_subscription_capability_profile_controls_sources_without_affecting_physics() -> None:
    basic = resolve_subscription_capability_profile("BASIC")
    enterprise = resolve_subscription_capability_profile("ENTERPRISE")

    assert "IFC" not in basic.allowed_spatial_sources
    assert "IFC" in enterprise.allowed_spatial_sources
    assert basic.allowed_analysis_modes == enterprise.allowed_analysis_modes
    assert basic.can_ingest_ifc is False
    assert enterprise.can_ingest_ifc is True


def test_default_facility_model_roundtrip_preserves_spatial_contract() -> None:
    model = build_default_facility_engineering_object_model(
        facility_id="FAC-001",
        facility_name="Spatial Twin",
        project_spatial_mode="GREENFIELD",
        source_type="MANUAL",
        subscription_tier="BASIC",
        coordinate_system=_coordinate_system(),
        room_coordinate=SpatialCoordinate(x_m=12.0, y_m=4.0, z_m=0.0, orientation_deg=90.0, local_coordinate_system="LOCAL", source_coordinate_reference="manual definition"),
        route_distance_m=42.0,
        vertical_change_m=3.0,
        equipment_class="Cyclotron",
        equipment_name="CY-001",
        facility_instance_id="CY-001",
        notes=("manual facility definition",),
    )

    payload = serialize_facility_engineering_object_model(model)
    restored = deserialize_facility_engineering_object_model(payload)

    assert restored is not None
    assert restored.facility_id == "FAC-001"
    assert restored.source_type == "MANUAL"
    assert restored.evidence_class == "USER_SUPPLIED"
    assert restored.facility is not None
    assert len(restored.buildings) == 1
    assert len(restored.storeys) == 1
    assert len(restored.spaces) == 1
    assert len(restored.equipment) == 1
    assert len(restored.nodes) == 2
    assert len(restored.edges) == 1

    route_distance = network_route_distance_m(
        {node.node_id: node for node in restored.nodes},
        restored.edges,
        restored.nodes[0].node_id,
        restored.nodes[1].node_id,
    )
    assert route_distance == pytest.approx(42.0, rel=0.0, abs=1e-9)
    assert route_distance > straight_line_distance_m(restored.nodes[0].coordinate, restored.nodes[1].coordinate)


def test_validation_flags_missing_scale_for_cad_geometry() -> None:
    model = build_default_facility_engineering_object_model(
        facility_id="FAC-002",
        facility_name="CAD Twin",
        project_spatial_mode="RETROFIT",
        source_type="DWG",
        subscription_tier="PROFESSIONAL",
        coordinate_system=_coordinate_system(scale=None),
        route_distance_m=75.0,
        equipment_class="PET/CT scanner",
        equipment_name="PET-01",
    )

    issues = validate_facility_engineering_object_model(model)
    assert any(issue.code == "MISSING_SCALE" for issue in issues)


def test_legacy_geometry_state_migrates_into_canonical_model() -> None:
    model = migrate_legacy_geometry_state(
        {
            "build3::geometry::route_distance_m": "71.0",
            "build3::geometry::floors": "3",
            "build3::geometry::vertical_transfer_m": "4.5",
            "build3::facility_engineering::facility_name": "Legacy Geometry Facility",
            "build3::facility_engineering::project_spatial_mode": "GREENFIELD",
            "build3::facility_engineering::source_type": "MANUAL",
            "build3::facility_engineering::subscription_tier": "BASIC",
        }
    )

    assert model is not None
    assert model.facility_name == "Legacy Geometry Facility"
    assert model.source_type == "MANUAL"
    assert model.maturity == "CONCEPTUAL"
    assert len(model.nodes) == 2
    assert len(model.edges) == 1
    assert network_route_distance_m(
        {node.node_id: node for node in model.nodes},
        model.edges,
        model.nodes[0].node_id,
        model.nodes[1].node_id,
    ) == pytest.approx(71.0, rel=0.0, abs=1e-9)

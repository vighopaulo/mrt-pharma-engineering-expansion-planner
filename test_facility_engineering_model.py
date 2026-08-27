from __future__ import annotations

from dataclasses import replace

import pytest

from facility_engineering_model import (
    CoordinateSystem,
    RequiredFacilityProgram,
    SpatialCoordinate,
    build_default_facility_engineering_object_model,
    build_space_function_assignment,
    deserialize_facility_engineering_object_model,
    evaluate_required_program_feasibility,
    migrate_legacy_geometry_state,
    network_route_distance_m,
    resolve_source_type_for_input_path,
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


def test_input_path_mapping_resolves_expected_source_type() -> None:
    assert resolve_source_type_for_input_path("MANUAL_SPATIAL_DEFINITION") == "MANUAL"
    assert resolve_source_type_for_input_path("BENCHMARK_ASSUMED_FACILITY") == "BENCHMARK"
    assert resolve_source_type_for_input_path("UPLOAD_FACILITY_DOCUMENT") == "IFC"
    assert resolve_source_type_for_input_path("UPLOAD_FACILITY_DOCUMENT", "DWG") == "DWG"


def test_validation_flags_manual_distance_with_reconstructed_nodes() -> None:
    model = build_default_facility_engineering_object_model(
        facility_id="FAC-003",
        facility_name="Manual Route",
        project_spatial_mode="RETROFIT",
        source_type="MANUAL",
        subscription_tier="BASIC",
        coordinate_system=_coordinate_system(),
        route_distance_m=85.0,
        route_geometry_status="NOT_RECONSTRUCTED",
        equipment_class="Cyclotron",
    )

    issues = validate_facility_engineering_object_model(model)
    assert any(issue.code == "MANUAL_DISTANCE_GEOMETRY_MISMATCH" for issue in issues)


def test_validation_flags_cyclotron_not_at_ground_level() -> None:
    model = build_default_facility_engineering_object_model(
        facility_id="FAC-004",
        facility_name="Elevated Cyclotron",
        project_spatial_mode="RETROFIT",
        source_type="MANUAL",
        subscription_tier="BASIC",
        coordinate_system=_coordinate_system(),
        storey_name="Level 2",
        equipment_class="Cyclotron",
    )

    model = replace(model, storeys=(replace(model.storeys[0], elevation_m=4.0),) + tuple(model.storeys[1:]))
    issues = validate_facility_engineering_object_model(model)
    assert any(issue.code == "CYCLOTRON_NOT_GROUND_LEVEL" for issue in issues)


def test_program_feasibility_report_marks_missing_capacity() -> None:
    assignment = build_space_function_assignment(
        space_id="SPACE-1",
        source_name="Office A",
        source_function="Office",
        proposed_name="Injection Room A",
        proposed_function="Injection room",
        assignment_status="OPTIMIZER_PROPOSED",
        suitability="SUITABLE_WITH_MODIFICATION",
    )

    model = build_default_facility_engineering_object_model(
        facility_id="FAC-005",
        facility_name="Program Test",
        project_spatial_mode="RETROFIT",
        source_type="MANUAL",
        subscription_tier="BASIC",
        coordinate_system=_coordinate_system(),
        proposed_space_assignments=(assignment,),
    )
    report = evaluate_required_program_feasibility(
        model=model,
        required_program=RequiredFacilityProgram(
            injection_rooms_required=2,
            uptake_rooms_required=1,
            pet_ct_scanners_required=1,
        ),
    )

    assert report.feasible is False
    assert report.missing_injection_spaces == 1
    assert report.missing_scanner_spaces == 1
    assert report.missing_uptake_spaces == 1
    assert report.notes


def test_builder_creates_second_building_and_distinct_route_destination() -> None:
    model = build_default_facility_engineering_object_model(
        facility_id="FAC-006",
        facility_name="Split Campus",
        project_spatial_mode="RETROFIT",
        source_type="MANUAL",
        subscription_tier="BASIC",
        coordinate_system=_coordinate_system(),
        route_distance_m=120.0,
        clinical_building_name="Main Hospital",
        equipment_class="Cyclotron",
    )

    assert len(model.buildings) == 2
    assert model.primary_route_origin_object_id == "FAC-006:RELEASE"
    assert model.primary_route_destination_object_ids == ("FAC-006:R2",)
    assert len(model.edges) == 1
    assert model.edges[0].destination_node_id == "FAC-006:N2"


def test_retrofit_builder_marks_core_and_expansion_buildings() -> None:
    model = build_default_facility_engineering_object_model(
        facility_id="FAC-007",
        facility_name="Retrofit Zones",
        project_spatial_mode="RETROFIT",
        source_type="MANUAL",
        subscription_tier="BASIC",
        coordinate_system=_coordinate_system(),
        route_distance_m=60.0,
        clinical_building_name="Building B",
        equipment_class="Cyclotron",
    )

    assert model.buildings[0].development_zone == "EXISTING_CORE"
    assert model.buildings[1].development_zone == "EXPANSION_ZONE"

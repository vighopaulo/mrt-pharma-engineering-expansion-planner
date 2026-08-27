"""BIM/iTwin Phase 2A.1 focused tests: Bentley-renderable product geometry,
IFC representation chain validity, placement/manifest reconciliation
preservation, CRS documentation, and protection of the Phase 2A semantic
model and unrelated authorities.
"""

from __future__ import annotations

import json
import os

import pytest

import ifc_hospital_proof_model_generator as gen

_IFC_PATH = os.path.join(os.path.dirname(__file__), "bim_test_assets", "mrt_pharma_hospital_bim_proof.ifc")
_MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "bim_test_assets", "mrt_pharma_hospital_bim_proof_manifest.json")

_VISIBLE_ROOM_IDS = ("ROOM-RP-101", "ROOM-CY-102", "ROOM-INJ-103", "COR-F1-001", "VERT-001", "ROOM-PAT-201", "ROOM-SCN-202", "COR-F2-001")
_VISIBLE_EQUIPMENT_IDS = ("CY-001", "SCN-001", "RP-001")


@pytest.fixture(scope="module")
def generated():
    model = gen.write_hospital_proof_model(ifc_path=_IFC_PATH, manifest_path=_MANIFEST_PATH)
    parsed = gen.read_ifc_proof_model(_IFC_PATH)
    with open(_MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    return model, parsed, manifest


def _room_ref(parsed, room_id):
    return parsed.find_entities_with_property("MRTWAY_ROOM_ID", room_id)[0].ref


def _equipment_ref(parsed, engineering_object_id):
    return parsed.find_entities_with_property("MRTWAY_ENGINEERING_OBJECT_ID", engineering_object_id)[0].ref


# ---------------------------------------------------------------------------
# 1-2. Non-null Representation
# ---------------------------------------------------------------------------


def test_1_every_visible_ifcspace_has_non_null_representation(generated):
    _, parsed, _ = generated
    for room_id in _VISIBLE_ROOM_IDS:
        assert parsed.has_representation(_room_ref(parsed, room_id)), room_id


def test_2_every_visible_ifcbuildingelementproxy_has_non_null_representation(generated):
    _, parsed, _ = generated
    for engineering_object_id in _VISIBLE_EQUIPMENT_IDS:
        assert parsed.has_representation(_equipment_ref(parsed, engineering_object_id)), engineering_object_id


# ---------------------------------------------------------------------------
# 3-9. Representation chain / geometry validity
# ---------------------------------------------------------------------------


def test_3_each_visible_product_resolves_through_full_chain(generated):
    _, parsed, _ = generated
    for room_id in _VISIBLE_ROOM_IDS:
        geo = parsed.resolve_body_geometry(_room_ref(parsed, room_id))
        assert geo is not None, room_id


def test_4_each_body_contains_valid_extruded_area_solid(generated):
    _, parsed, _ = generated
    for room_id in _VISIBLE_ROOM_IDS:
        geo = parsed.resolve_body_geometry(_room_ref(parsed, room_id))
        assert geo.solid_entity_type == "IFCEXTRUDEDAREASOLID"
    for engineering_object_id in _VISIBLE_EQUIPMENT_IDS:
        geo = parsed.resolve_body_geometry(_equipment_ref(parsed, engineering_object_id))
        assert geo.solid_entity_type == "IFCEXTRUDEDAREASOLID"


def test_5_every_extrusion_depth_is_positive(generated):
    _, parsed, _ = generated
    for room_id in _VISIBLE_ROOM_IDS:
        assert parsed.resolve_body_geometry(_room_ref(parsed, room_id)).extrusion_depth_m > 0.0
    for engineering_object_id in _VISIBLE_EQUIPMENT_IDS:
        assert parsed.resolve_body_geometry(_equipment_ref(parsed, engineering_object_id)).extrusion_depth_m > 0.0


def test_6_every_profile_width_is_positive(generated):
    _, parsed, _ = generated
    for room_id in _VISIBLE_ROOM_IDS:
        assert parsed.resolve_body_geometry(_room_ref(parsed, room_id)).width_m > 0.0


def test_7_every_profile_depth_is_positive(generated):
    _, parsed, _ = generated
    for room_id in _VISIBLE_ROOM_IDS:
        assert parsed.resolve_body_geometry(_room_ref(parsed, room_id)).depth_m > 0.0


def test_8_representation_identifier_is_body(generated):
    _, parsed, _ = generated
    for room_id in _VISIBLE_ROOM_IDS:
        assert parsed.resolve_body_geometry(_room_ref(parsed, room_id)).representation_identifier == "Body"


def test_9_representation_type_matches_contained_geometry(generated):
    _, parsed, _ = generated
    for room_id in _VISIBLE_ROOM_IDS:
        assert parsed.resolve_body_geometry(_room_ref(parsed, room_id)).representation_type == "SweptSolid"


def test_10_geometric_representation_context_exists(generated):
    _, parsed, _ = generated
    assert len(parsed.of_type("IFCGEOMETRICREPRESENTATIONCONTEXT")) == 1
    assert len(parsed.of_type("IFCGEOMETRICREPRESENTATIONSUBCONTEXT")) == 1


# ---------------------------------------------------------------------------
# 11-14. Placement/manifest reconciliation unchanged
# ---------------------------------------------------------------------------


def test_11_placement_hierarchy_still_resolves_exactly(generated):
    model, parsed, _ = generated
    for room in model.rooms:
        pos = parsed.resolve_global_position(_room_ref(parsed, room.room_id))
        assert pos == pytest.approx((room.x_m, room.y_m, room.z_m), abs=0.0)


def test_12_room_global_coordinates_equal_manifest_exactly(generated):
    _, parsed, manifest = generated
    for entry in manifest["rooms"]:
        pos = parsed.resolve_global_position(_room_ref(parsed, entry["room_id"]))
        assert pos[0] == entry["x_m"] and pos[1] == entry["y_m"] and pos[2] == entry["z_m"]


def test_13_equipment_global_coordinates_equal_manifest_exactly(generated):
    _, parsed, manifest = generated
    for entry in manifest["equipment"]:
        pos = parsed.resolve_global_position(_equipment_ref(parsed, entry["engineering_object_id"]))
        assert pos[0] == entry["x_m"] and pos[1] == entry["y_m"] and pos[2] == entry["z_m"]


def test_14_storey_elevations_remain_0_and_4(generated):
    _, _, manifest = generated
    elevations = {f["floor_id"]: f["elevation_m"] for f in manifest["floors"]}
    assert elevations["F1"] == pytest.approx(0.0)
    assert elevations["F2"] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# 15-19. Semantic identifiers / units / GlobalIds preserved
# ---------------------------------------------------------------------------


def test_15_metric_units_unchanged(generated):
    _, parsed, manifest = generated
    units = parsed.of_type("IFCSIUNIT")
    assert len(units) == 1
    assert ".METRE." in units[0].raw_args
    assert manifest["model_units"] == "meters"


def test_16_mrtway_room_id_values_unchanged(generated):
    model, parsed, _ = generated
    for room in model.rooms:
        assert len(parsed.find_entities_with_property("MRTWAY_ROOM_ID", room.room_id)) == 1


def test_17_mrtway_engineering_object_id_values_unchanged(generated):
    model, parsed, _ = generated
    for item in model.equipment:
        assert len(parsed.find_entities_with_property("MRTWAY_ENGINEERING_OBJECT_ID", item.engineering_object_id)) == 1


def test_18_mrtway_model_class_and_purpose_unchanged(generated):
    _, parsed, manifest = generated
    assert parsed.property_values().get("MRTWAY_MODEL_CLASS") == "SYNTHETIC_TEST_BIM"
    assert parsed.property_values().get("MRTWAY_MODEL_PURPOSE") == "BENTLEY_ITWIN_INTEGRATION_PROOF"
    assert manifest["mrtway_model_class"] == "SYNTHETIC_TEST_BIM"
    assert manifest["mrtway_model_purpose"] == "BENTLEY_ITWIN_INTEGRATION_PROOF"


def test_19_ifc_globalids_remain_deterministic(generated):
    _, parsed, _ = generated
    text_1 = gen.generate_ifc_text(gen.build_hospital_proof_model())
    text_2 = gen.generate_ifc_text(gen.build_hospital_proof_model())
    assert text_1 == text_2  # deterministic GUID counter -- same input always produces the same output


# ---------------------------------------------------------------------------
# 20-21. Determinism / schema
# ---------------------------------------------------------------------------


def test_20_regeneration_remains_deterministic(generated):
    model = gen.build_hospital_proof_model()
    text_a = gen.generate_ifc_text(model)
    text_b = gen.generate_ifc_text(model)
    assert text_a == text_b


def test_21_generated_ifc_remains_ifc4(generated):
    _, parsed, _ = generated
    assert parsed.schema == "IFC4"


# ---------------------------------------------------------------------------
# 22. Existing Phase 2A tests remain green
# ---------------------------------------------------------------------------


def test_22_existing_phase2a_tests_remain_green():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_bim_itwin_phase2a_hospital_ifc_proof_model.py"],
        cwd=os.path.dirname(__file__), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# 23. Manifest geometry dimensions reconcile with emitted IFC
# ---------------------------------------------------------------------------


def test_23_manifest_geometry_dimensions_reconcile_with_ifc(generated):
    _, parsed, manifest = generated
    for entry in manifest["rooms"]:
        geo = parsed.resolve_body_geometry(_room_ref(parsed, entry["room_id"]))
        assert geo.width_m == pytest.approx(entry["width_m"])
        assert geo.depth_m == pytest.approx(entry["depth_m"])
        assert geo.extrusion_depth_m == pytest.approx(entry["height_m"])
        assert entry["geometry_representation_expected"] is True
    for entry in manifest["equipment"]:
        geo = parsed.resolve_body_geometry(_equipment_ref(parsed, entry["engineering_object_id"]))
        assert geo.width_m == pytest.approx(entry["width_m"])
        assert geo.depth_m == pytest.approx(entry["depth_m"])
        assert geo.extrusion_depth_m == pytest.approx(entry["height_m"])


# ---------------------------------------------------------------------------
# 24-27. No canonical/Bentley/OpenUSD/routing dependency introduced
# ---------------------------------------------------------------------------


def test_24_no_canonical_spatial_authority_imported_or_mutated():
    """The generator's own docstring EXPLAINS (in prose) that it never
    touches `canonical_spatial_authority` -- this checks for an actual
    import statement, not the explanatory prose itself."""
    import inspect

    source = inspect.getsource(gen)
    assert "import canonical_spatial_authority" not in source
    assert "from canonical_spatial_authority" not in source
    assert not hasattr(gen, "canonical_spatial_authority")


def test_25_no_bentley_client_dependency_introduced():
    import inspect

    source = inspect.getsource(gen)
    assert "bentley_itwin_client" not in source


def test_26_no_openusd_dependency_introduced():
    import inspect

    source = inspect.getsource(gen)
    assert "openusd_spatial_adapter" not in source
    assert "pxr" not in source


def test_27_no_routing_economic_clinical_code_introduced():
    import inspect

    source = inspect.getsource(gen)
    forbidden = (
        "canonical_geometry_shadow_routing_authority", "reactive_engineering_economic_consequence_authority",
        "production_clinical_schedule", "patient_radionuclide_demand", "decision_pipeline",
        "mrt_transport_energy_maintenance_authority",
    )
    for term in forbidden:
        assert term not in source


# ---------------------------------------------------------------------------
# CRS documentation (section 7) -- explicit, no fabricated geolocation
# ---------------------------------------------------------------------------


def test_crs_status_is_explicit_local_and_no_geolocation_fabricated(generated):
    _, _, manifest = generated
    assert manifest["coordinate_reference_system"] == "LOCAL_ENGINEERING_NON_GEOREFERENCED"
    with open(_IFC_PATH, "r", encoding="ascii") as f:
        ifc_text = f.read()
    for forbidden in ("IFCPROJECTEDCRS", "IFCMAPCONVERSION", "EPSG"):
        assert forbidden not in ifc_text.upper()

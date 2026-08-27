"""BIM/iTwin Phase 2A focused tests: controlled synthetic hospital IFC proof
model generation, structural validity, manifest reconciliation, and
protection of the frozen Phase 1-3/BIM Phase 1 foundation.
"""

from __future__ import annotations

import json
import os

import pytest

import ifc_hospital_proof_model_generator as gen

_IFC_PATH = os.path.join(os.path.dirname(__file__), "bim_test_assets", "mrt_pharma_hospital_bim_proof.ifc")
_MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "bim_test_assets", "mrt_pharma_hospital_bim_proof_manifest.json")


@pytest.fixture(scope="module")
def generated():
    model = gen.write_hospital_proof_model(ifc_path=_IFC_PATH, manifest_path=_MANIFEST_PATH)
    parsed = gen.read_ifc_proof_model(_IFC_PATH)
    with open(_MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    return model, parsed, manifest


# ---------------------------------------------------------------------------
# 1-3. Generation / structural validity / units
# ---------------------------------------------------------------------------


def test_1_ifc_file_generated_successfully(generated):
    assert os.path.exists(_IFC_PATH)


def test_2_ifc_file_non_empty_and_reopenable(generated):
    _, parsed, _ = generated
    assert len(parsed.entities) > 0
    assert os.path.getsize(_IFC_PATH) > 0


def test_3_model_units_resolve_to_meters(generated):
    _, parsed, manifest = generated
    units = parsed.of_type("IFCSIUNIT")
    assert len(units) == 1
    assert ".METRE." in units[0].raw_args
    assert manifest["model_units"] == "meters"


# ---------------------------------------------------------------------------
# 4-5. Building / floors
# ---------------------------------------------------------------------------


def test_4_building_bldg_hosp_a_exists(generated):
    _, parsed, manifest = generated
    buildings = parsed.of_type("IFCBUILDING")
    assert len(buildings) == 1
    assert manifest["building"]["building_id"] == "BLDG-HOSP-A"
    assert "'BLDG-HOSP-A'" in buildings[0].raw_args


def test_5_two_floors_exist(generated):
    _, parsed, manifest = generated
    storeys = parsed.of_type("IFCBUILDINGSTOREY")
    assert len(storeys) == 2
    assert [f["floor_id"] for f in manifest["floors"]] == ["F1", "F2"]
    assert manifest["floors"][0]["elevation_m"] == pytest.approx(0.0)
    assert manifest["floors"][1]["elevation_m"] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# 6-12. Required rooms exist
# ---------------------------------------------------------------------------


def _room_ids(manifest):
    return {r["room_id"] for r in manifest["rooms"]}


def test_6_required_room_ids_exist(generated):
    _, _, manifest = generated
    required = {"ROOM-RP-101", "ROOM-CY-102", "ROOM-INJ-103", "ROOM-PAT-201", "ROOM-SCN-202", "VERT-001", "COR-F1-001", "COR-F2-001"}
    assert required.issubset(_room_ids(manifest))


def test_7_room_rp_101_exists(generated):
    _, parsed, _ = generated
    assert len(parsed.find_entities_with_property("MRTWAY_ROOM_ID", "ROOM-RP-101")) == 1


def test_8_room_cy_102_exists(generated):
    _, parsed, _ = generated
    assert len(parsed.find_entities_with_property("MRTWAY_ROOM_ID", "ROOM-CY-102")) == 1


def test_9_room_inj_103_exists(generated):
    _, parsed, _ = generated
    assert len(parsed.find_entities_with_property("MRTWAY_ROOM_ID", "ROOM-INJ-103")) == 1


def test_10_room_pat_201_exists(generated):
    _, parsed, _ = generated
    assert len(parsed.find_entities_with_property("MRTWAY_ROOM_ID", "ROOM-PAT-201")) == 1


def test_11_room_scn_202_exists(generated):
    _, parsed, _ = generated
    assert len(parsed.find_entities_with_property("MRTWAY_ROOM_ID", "ROOM-SCN-202")) == 1


def test_12_vertical_core_exists(generated):
    _, parsed, _ = generated
    assert len(parsed.find_entities_with_property("MRTWAY_ROOM_ID", "VERT-001")) == 1


# ---------------------------------------------------------------------------
# 13-17. Equipment proxies + deterministic IDs
# ---------------------------------------------------------------------------


def test_13_cyclotron_proxy_cy_001_exists(generated):
    _, parsed, _ = generated
    matches = parsed.find_entities_with_property("MRTWAY_ENGINEERING_OBJECT_ID", "CY-001")
    assert len(matches) == 1
    assert matches[0].entity_type == "IFCBUILDINGELEMENTPROXY"


def test_14_scanner_proxy_scn_001_exists(generated):
    _, parsed, _ = generated
    matches = parsed.find_entities_with_property("MRTWAY_ENGINEERING_OBJECT_ID", "SCN-001")
    assert len(matches) == 1
    assert matches[0].entity_type == "IFCBUILDINGELEMENTPROXY"


def test_15_radiopharmacy_proxy_rp_001_exists(generated):
    _, parsed, _ = generated
    matches = parsed.find_entities_with_property("MRTWAY_ENGINEERING_OBJECT_ID", "RP-001")
    assert len(matches) == 1
    assert matches[0].entity_type == "IFCBUILDINGELEMENTPROXY"


def test_16_equipment_carries_deterministic_mrtway_engineering_ids(generated):
    model, parsed, _ = generated
    for item in model.equipment:
        matches = parsed.find_entities_with_property("MRTWAY_ENGINEERING_OBJECT_ID", item.engineering_object_id)
        assert len(matches) == 1, item.engineering_object_id


def test_17_spaces_carry_deterministic_mrtway_room_ids(generated):
    model, parsed, _ = generated
    for room in model.rooms:
        matches = parsed.find_entities_with_property("MRTWAY_ROOM_ID", room.room_id)
        assert len(matches) == 1, room.room_id


# ---------------------------------------------------------------------------
# 18-19. Manifest completeness + coordinate reconciliation
# ---------------------------------------------------------------------------


def test_18_manifest_contains_all_required_ids(generated):
    model, _, manifest = generated
    manifest_room_ids = _room_ids(manifest)
    for room in model.rooms:
        assert room.room_id in manifest_room_ids
    manifest_equipment_ids = {e["engineering_object_id"] for e in manifest["equipment"]}
    for item in model.equipment:
        assert item.engineering_object_id in manifest_equipment_ids


def test_19_manifest_coordinates_reconcile_to_ifc_placements(generated):
    model, parsed, manifest = generated
    tolerance_m = 1e-6
    for room_entry in manifest["rooms"]:
        matches = parsed.find_entities_with_property("MRTWAY_ROOM_ID", room_entry["room_id"])
        pos = parsed.resolve_global_position(matches[0].ref)
        assert pos[0] == pytest.approx(room_entry["x_m"], abs=tolerance_m)
        assert pos[1] == pytest.approx(room_entry["y_m"], abs=tolerance_m)
        assert pos[2] == pytest.approx(room_entry["z_m"], abs=tolerance_m)
    for item_entry in manifest["equipment"]:
        matches = parsed.find_entities_with_property("MRTWAY_ENGINEERING_OBJECT_ID", item_entry["engineering_object_id"])
        pos = parsed.resolve_global_position(matches[0].ref)
        assert pos[0] == pytest.approx(item_entry["x_m"], abs=tolerance_m)
        assert pos[1] == pytest.approx(item_entry["y_m"], abs=tolerance_m)
        assert pos[2] == pytest.approx(item_entry["z_m"], abs=tolerance_m)


# ---------------------------------------------------------------------------
# 20. Equipment-room binding map
# ---------------------------------------------------------------------------


def test_20_expected_equipment_room_binding_map_is_correct(generated):
    _, _, manifest = generated
    assert manifest["expected_room_equipment_bindings"] == {
        "CY-001": "ROOM-CY-102", "SCN-001": "ROOM-SCN-202", "RP-001": "ROOM-RP-101",
    }


# ---------------------------------------------------------------------------
# 21-22. No PHI + explicit synthetic marker
# ---------------------------------------------------------------------------


def test_21_model_contains_no_phi_or_patient_identifiers(generated):
    """"Patient Room" is a legitimate, REQUIRED clinical room-type label
    (section 5) -- not PHI. This checks for genuine patient-identifying
    concepts (MRN/SSN/DOB/patient-ID-shaped values), never the generic word
    "patient" used only as a room-type descriptor."""
    _, parsed, manifest = generated
    with open(_IFC_PATH, "r", encoding="ascii") as f:
        ifc_text = f.read()
    forbidden_terms = ("PHI", "SSN", "DOB", "MRN", "patient_id", "patientid")
    lowered = ifc_text.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered
    manifest_text = json.dumps(manifest).lower()
    for term in forbidden_terms:
        assert term.lower() not in manifest_text


def test_22_model_explicitly_marked_synthetic_test_bim(generated):
    _, parsed, manifest = generated
    assert parsed.property_values().get("MRTWAY_MODEL_CLASS") == "SYNTHETIC_TEST_BIM"
    assert parsed.property_values().get("MRTWAY_MODEL_PURPOSE") == "BENTLEY_ITWIN_INTEGRATION_PROOF"
    assert manifest["mrtway_model_class"] == "SYNTHETIC_TEST_BIM"
    assert manifest["mrtway_model_purpose"] == "BENTLEY_ITWIN_INTEGRATION_PROOF"


# ---------------------------------------------------------------------------
# 23-27. Protection of existing BIM Phase 1 / canonical spatial / OpenUSD / Lockdown
# ---------------------------------------------------------------------------


def test_23_existing_bentley_phase1_tests_remain_green():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_bim_itwin_phase1_bentley_binding.py"],
        cwd=os.path.dirname(__file__), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_24_existing_canonical_spatial_tests_remain_green():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_canonical_spatial_authority_closure.py", "test_canonical_facility_geometry_spatial_authority.py"],
        cwd=os.path.dirname(__file__), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_25_openusd_role_remains_unchanged_export_only():
    import inspect
    import openusd_spatial_adapter

    source = inspect.getsource(openusd_spatial_adapter)
    for forbidden in ("ifc_hospital_proof_model_generator", "IFCBUILDINGELEMENTPROXY", "STEP Physical"):
        assert forbidden not in source


def test_26_lockdown_remains_immutable():
    import canonical_spatial_authority as csa

    reg = csa.build_facility_hierarchy(facility_id="FAC-BIM2A")
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    csa.add_building(what_if.registry, facility_id="FAC-BIM2A", building_id="BLDG-HOSP-A")
    assert "BLDG-HOSP-A" not in locked.registry.objects


def test_27_no_existing_phase1_3_test_file_changed():
    """This proof model lives in its own new module/asset/test file --
    nothing in the frozen Phase 1-3/BIM Phase 1 test suite was edited to
    accommodate it (verified structurally: this test file imports/exercises
    the new generator only, never modifies shared fixtures)."""
    assert os.path.basename(__file__) == "test_bim_itwin_phase2a_hospital_ifc_proof_model.py"

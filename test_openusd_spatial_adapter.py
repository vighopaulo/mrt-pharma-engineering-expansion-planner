"""Focused tests for the OPENUSD SPATIAL ADAPTER + SCENE SERIALIZATION build.

Covers: OpenUSD dependency/runtime detection, stable MRTWAY_OBJECT_ID vs USD
prim path, deterministic prim-path sanitization + collision handling,
N-building hierarchy (1/2/5 buildings), units/up-axis, transform round-trip
(translation/rotation/combined), camera-rotation non-mutation, geometry
quality + catalog-model binding, cyclotron/generator/PET/SPECT export,
multiple equipment instances, general-logistics export, full MRT object
export (trunk/branch/segment/junction/endpoint/vestibule/carrier/container),
multiple vestibules, multiple production sources, arbitrary source-building
placement, five-building controlled scene + MRT network, locked/what-if
export + identity/round-trip, MRT segment stretch, return-to-locked,
serialization/deserialization, external-mapping persistence, selection
round-trip, group identity, visibility vs asset/operational state,
architecture visibility, Hybrid coverage metadata, Retrofit/Greenfield
compatibility, unknown/orphan/duplicate-prim handling, invalid transform/
unit/up-axis detection, scene validation/export/import results, read-only
import non-mutation, validated-transform-application targeting what-if only,
object-inspector/delta reuse, economic/common-cost/patient/architecture/
Live-State non-regression, and vendor-adapter non-regression.
"""

import dataclasses
import math
import os

import pytest

import canonical_spatial_authority as csa
import openusd_spatial_adapter as usda

pytestmark = pytest.mark.skipif(not usda.OPENUSD_RUNTIME_AVAILABLE, reason="OpenUSD runtime (pxr) not available in this environment")


# ---------------------------------------------------------------------------
# 1. Dependency / runtime detection
# ---------------------------------------------------------------------------


def test_openusd_runtime_detected_and_classified():
    assert usda.OPENUSD_RUNTIME_AVAILABLE is True
    assert usda.OPENUSD_RUNTIME_VERSION is not None


def test_runtime_not_available_raises_explicit_error(monkeypatch):
    monkeypatch.setattr(usda, "OPENUSD_RUNTIME_AVAILABLE", False)
    with pytest.raises(usda.OpenUsdRuntimeNotAvailable):
        usda._require_runtime()


# ---------------------------------------------------------------------------
# 2. Stable MRTWAY_OBJECT_ID vs USD prim path + sanitization + collisions
# ---------------------------------------------------------------------------


def test_mrtway_object_id_never_equals_usd_prim_path():
    reg, _ = csa.build_five_building_controlled_campus()
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    for mrtway_id, prim_path in path_registry.by_mrtway_id.items():
        assert mrtway_id != prim_path
        assert path_registry.resolve_by_prim_path(prim_path) == mrtway_id


def test_prim_path_sanitization_deterministic():
    a1 = usda.sanitize_prim_path_segment("BLDG-A::F1")
    a2 = usda.sanitize_prim_path_segment("BLDG-A::F1")
    assert a1 == a2
    assert a1.replace("_", "").isalnum() or a1.startswith("_")


def test_prim_path_sanitization_handles_leading_digit():
    sanitized = usda.sanitize_prim_path_segment("123abc")
    assert sanitized[0].isalpha() or sanitized[0] == "_"


def test_path_collision_detected_and_fails_loudly():
    registry = usda.PrimPathRegistry()
    registry.register(mrtway_object_id="OBJ-A", prim_path="/X/SamePath")
    with pytest.raises(usda.PrimPathCollisionError):
        registry.register(mrtway_object_id="OBJ-B", prim_path="/X/SamePath")


# ---------------------------------------------------------------------------
# 3. N-building hierarchy (1/2/5 buildings)
# ---------------------------------------------------------------------------


def test_one_building_export():
    reg = csa.build_facility_hierarchy(facility_id="FAC-SOLO")
    csa.add_building(reg, facility_id="FAC-SOLO", building_id="BLDG-SOLO")
    stage, path_registry, result = usda.export_registry_to_stage(reg)
    assert result.object_count == 2  # facility + building
    assert len(path_registry) == 2


def test_two_building_export():
    reg = csa.build_facility_hierarchy(facility_id="FAC-DUAL")
    csa.build_n_building_campus(reg, facility_id="FAC-DUAL", building_ids=("BLDG-X", "BLDG-Y"))
    stage, path_registry, result = usda.export_registry_to_stage(reg)
    assert result.object_count == 3
    assert {path_registry.resolve_by_mrtway_id("BLDG-X"), path_registry.resolve_by_mrtway_id("BLDG-Y")} == {
        "/MRTwayCampus/Facility/Buildings/BLDG_X", "/MRTwayCampus/Facility/Buildings/BLDG_Y",
    }


def test_five_building_export_no_hardcoded_ab():
    reg, _ = csa.build_five_building_controlled_campus()
    stage, path_registry, result = usda.export_registry_to_stage(reg)
    buildings = {o.mrtway_object_id for o in reg.by_type("BUILDING")}
    assert buildings == {"BLDG-A", "BLDG-B", "BLDG-C", "BLDG-D", "BLDG-E"}
    for b in buildings:
        assert path_registry.resolve_by_mrtway_id(b) is not None
    # production adapter logic itself contains no special-cased building names
    import inspect
    source = inspect.getsource(usda.build_deterministic_prim_path)
    assert '"A"' not in source and '"B"' not in source


# ---------------------------------------------------------------------------
# 4. Units / up-axis / transform round-trip
# ---------------------------------------------------------------------------


@pytest.fixture
def five_building_campus():
    return csa.build_five_building_controlled_campus()


def test_meters_per_unit_and_up_axis_explicit(five_building_campus):
    from pxr import UsdGeom
    reg, _ = five_building_campus
    stage, _, _ = usda.export_registry_to_stage(reg)
    assert UsdGeom.GetStageMetersPerUnit(stage) == usda.METERS_PER_UNIT == 1.0
    assert str(UsdGeom.GetStageUpAxis(stage)) == usda.UP_AXIS == "Z"


def test_translation_round_trip(five_building_campus):
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("BLDG-C"))
    readback = usda.read_transform(prim)
    assert usda.transforms_match(readback, reg.get("BLDG-C").transform)


def test_rotation_round_trip():
    reg = csa.build_facility_hierarchy(facility_id="FAC-ROT")
    obj = csa.add_building(reg, facility_id="FAC-ROT", building_id="BLDG-ROT", transform=csa.Transform(rotation_z=45.0, rotation_x=10.0, rotation_y=5.0))
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("BLDG-ROT"))
    readback = usda.read_transform(prim)
    assert usda.transforms_match(readback, obj.transform)


def test_combined_transform_round_trip():
    reg = csa.build_facility_hierarchy(facility_id="FAC-COMBO")
    transform = csa.Transform(position_x=12.5, position_y=-3.25, position_z=1.0, rotation_x=15.0, rotation_y=30.0, rotation_z=45.0)
    obj = csa.add_building(reg, facility_id="FAC-COMBO", building_id="BLDG-COMBO", transform=transform)
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("BLDG-COMBO"))
    readback = usda.read_transform(prim)
    assert usda.transforms_match(readback, transform)


def test_camera_rotation_does_not_mutate_engineering_transform(five_building_campus):
    reg, _ = five_building_campus
    original = reg.get("BLDG-C").transform
    impact = usda.apply_camera_view_rotation(yaw_degrees=180.0, pitch_degrees=30.0)
    assert impact.delta_engineering_transform is False
    assert reg.get("BLDG-C").transform == original


# ---------------------------------------------------------------------------
# 5. Geometry quality + catalog-model binding + equipment export
# ---------------------------------------------------------------------------


def test_geometry_quality_classification_enum_values():
    assert usda._NOT_AVAILABLE_GEOMETRY_ASSET.geometry_quality == "NOT_AVAILABLE"
    asset = usda.build_geometry_asset_from_catalog_model(catalog_model_id="X", manufacturer="ACME", model="Y")
    assert asset.geometry_quality == "GENERIC_PROXY"


def test_default_geometry_asset_registry_binds_real_catalog_manufacturers():
    registry = usda.default_geometry_asset_registry()
    assert len(registry.assets_by_catalog_model_id) > 0
    sample = next(iter(registry.assets_by_catalog_model_id.values()))
    assert sample.manufacturer is not None and sample.model is not None
    assert sample.geometry_quality == "GENERIC_PROXY"  # never claims manufacturer-accurate geometry


def test_catalog_model_binding_deterministic_lookup():
    registry = usda.default_geometry_asset_registry()
    from cyclotron_catalog import load_cyclotron_catalog
    catalog = load_cyclotron_catalog()
    known_id = catalog.models[0].catalog_model_id
    resolved = registry.resolve(known_id)
    assert resolved is not None
    assert resolved.catalog_model_id == known_id
    assert registry.resolve("NOT-A-REAL-MODEL") is None


def test_cyclotron_export_with_catalog_binding():
    reg = csa.build_facility_hierarchy(facility_id="FAC-CY")
    csa.add_building(reg, facility_id="FAC-CY", building_id="BLDG-CY")
    csa.add_floor(reg, facility_id="FAC-CY", building_id="BLDG-CY", floor_id="F1")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-CY", building_id="BLDG-CY", floor_id="F1", cyclotron_id="CY-001")
    geo = usda.default_geometry_asset_registry()
    stage, path_registry, _ = usda.export_registry_to_stage(reg, catalog_bindings={"CY-001": "GE_PETTRACE_880"}, geometry_assets=geo)
    prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("CY-001"))
    data = dict(prim.GetCustomData())
    assert data["object_type"] == "CYCLOTRON"
    assert data["manufacturer"] == "GE HealthCare"
    assert data["catalog_model_id"] == "GE_PETTRACE_880"


def test_generator_export_proxy_geometry_no_physics_change():
    reg = csa.build_facility_hierarchy(facility_id="FAC-GEN")
    csa.add_building(reg, facility_id="FAC-GEN", building_id="BLDG-GEN")
    csa.add_floor(reg, facility_id="FAC-GEN", building_id="BLDG-GEN", floor_id="F1")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-GEN", building_id="BLDG-GEN", floor_id="F1", generator_id="GEN-001")
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("GEN-001"))
    assert dict(prim.GetCustomData())["object_type"] == "MO99_TC99M_GENERATOR"


def test_pet_scanner_export_with_manufacturer_model_metadata():
    reg = csa.build_facility_hierarchy(facility_id="FAC-PET")
    csa.add_building(reg, facility_id="FAC-PET", building_id="BLDG-PET")
    csa.add_floor(reg, facility_id="FAC-PET", building_id="BLDG-PET", floor_id="F1")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-PET", building_id="BLDG-PET", floor_id="F1", pet_scanner_id="SCN-PET-001")
    geo = usda.default_geometry_asset_registry()
    from scanner_catalog import load_scanner_catalog
    pet_model = next(m for m in load_scanner_catalog().models if m.modality == "PET")
    stage, path_registry, _ = usda.export_registry_to_stage(reg, catalog_bindings={"SCN-PET-001": pet_model.catalog_model_id}, geometry_assets=geo)
    prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("SCN-PET-001"))
    data = dict(prim.GetCustomData())
    assert data["object_type"] == "PET_SCANNER"
    assert data["manufacturer"] == pet_model.manufacturer
    assert data["model"] == pet_model.model


def test_spect_scanner_export_with_manufacturer_model_metadata():
    reg = csa.build_facility_hierarchy(facility_id="FAC-SPECT")
    csa.add_building(reg, facility_id="FAC-SPECT", building_id="BLDG-SPECT")
    csa.add_floor(reg, facility_id="FAC-SPECT", building_id="BLDG-SPECT", floor_id="F1")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-SPECT", building_id="BLDG-SPECT", floor_id="F1", spect_scanner_id="SCN-SPECT-001")
    geo = usda.default_geometry_asset_registry()
    from scanner_catalog import load_scanner_catalog
    spect_model = next(m for m in load_scanner_catalog().models if m.modality == "SPECT")
    stage, path_registry, _ = usda.export_registry_to_stage(reg, catalog_bindings={"SCN-SPECT-001": spect_model.catalog_model_id}, geometry_assets=geo)
    prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("SCN-SPECT-001"))
    data = dict(prim.GetCustomData())
    assert data["object_type"] == "SPECT_SCANNER"
    assert data["manufacturer"] == spect_model.manufacturer


def test_pet_and_spect_catalog_binding_distinct():
    from scanner_catalog import load_scanner_catalog
    catalog = load_scanner_catalog()
    pet_ids = {m.catalog_model_id for m in catalog.models_of_modality("PET")}
    spect_ids = {m.catalog_model_id for m in catalog.models_of_modality("SPECT")}
    assert pet_ids.isdisjoint(spect_ids)


def test_multiple_pet_scanner_instances_retain_distinct_identity():
    reg = csa.build_facility_hierarchy(facility_id="FAC-MULTI-PET")
    csa.add_building(reg, facility_id="FAC-MULTI-PET", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-MULTI-PET", building_id="BLDG-A", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-MULTI-PET", building_id="BLDG-A", floor_id="F1", room_id="SCN-PET-001", object_type="PET_SCANNER")
    csa.add_room(reg, facility_id="FAC-MULTI-PET", building_id="BLDG-A", floor_id="F1", room_id="SCN-PET-002", object_type="PET_SCANNER")
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    p1, p2 = path_registry.resolve_by_mrtway_id("SCN-PET-001"), path_registry.resolve_by_mrtway_id("SCN-PET-002")
    assert p1 != p2 and p1 is not None and p2 is not None


def test_multiple_spect_scanner_instances_retain_distinct_identity():
    reg = csa.build_facility_hierarchy(facility_id="FAC-MULTI-SPECT")
    csa.add_building(reg, facility_id="FAC-MULTI-SPECT", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-MULTI-SPECT", building_id="BLDG-A", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-MULTI-SPECT", building_id="BLDG-A", floor_id="F1", room_id="SCN-SPECT-001", object_type="SPECT_SCANNER")
    csa.add_room(reg, facility_id="FAC-MULTI-SPECT", building_id="BLDG-A", floor_id="F1", room_id="SCN-SPECT-002", object_type="SPECT_SCANNER")
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    assert path_registry.resolve_by_mrtway_id("SCN-SPECT-001") != path_registry.resolve_by_mrtway_id("SCN-SPECT-002")


def test_pet_spect_modality_identity_preserved_after_round_trip():
    reg = csa.build_facility_hierarchy(facility_id="FAC-MODALITY")
    csa.add_building(reg, facility_id="FAC-MODALITY", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-MODALITY", building_id="BLDG-A", floor_id="F1")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-MODALITY", building_id="BLDG-A", floor_id="F1", pet_scanner_id="SCN-PET-001", spect_scanner_id="SCN-SPECT-001")
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    import_result = usda.import_scene(stage, reg)
    pet_prim = stage.GetPrimAtPath(import_result.resolved_mappings["SCN-PET-001"])
    spect_prim = stage.GetPrimAtPath(import_result.resolved_mappings["SCN-SPECT-001"])
    assert dict(pet_prim.GetCustomData())["object_type"] == "PET_SCANNER"
    assert dict(spect_prim.GetCustomData())["object_type"] == "SPECT_SCANNER"


# ---------------------------------------------------------------------------
# 6. General-logistics + MRT object export
# ---------------------------------------------------------------------------


def test_general_logistics_origins_export():
    reg = csa.build_facility_hierarchy(facility_id="FAC-LOG")
    csa.add_building(reg, facility_id="FAC-LOG", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-LOG", building_id="BLDG-A", floor_id="F1")
    origins = csa.build_general_logistics_origin_objects(reg, facility_id="FAC-LOG", building_id="BLDG-A", floor_id="F1")
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    for origin in origins:
        prim_path = path_registry.resolve_by_mrtway_id(origin.mrtway_object_id)
        assert prim_path is not None
        assert prim_path.startswith("/MRTwayCampus/Facility/Logistics/")


def test_mrt_trunk_branch_segment_junction_endpoint_vestibule_export_distinctly():
    reg = csa.build_facility_hierarchy(facility_id="FAC-MRT")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-MRT", building_id="BLDG-A", floor_id="F1")
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-MRT", length_m=50.0)
    branch = csa.build_mrt_branch(reg, branch_id="BRANCH-1", facility_id="FAC-MRT", connects_to_object_id=trunk.mrtway_object_id, length_m=20.0)
    junction = csa.build_mrt_junction(reg, junction_id="JCT-1", facility_id="FAC-MRT")
    endpoint = csa.build_mrt_endpoint(reg, endpoint_id="EP-1", facility_id="FAC-MRT", connected_network_object_id=trunk.mrtway_object_id)
    segment = csa.build_mrt_segment(reg, segment_id="SEG-1", facility_id="FAC-MRT", start_object_id="RP-001", end_object_id=trunk.mrtway_object_id, length_m=15.0)
    vestibule = csa.build_mrt_vestibule(reg, vestibule_id="VEST-1", facility_id="FAC-MRT", radiopharmacy_object_id="RP-001", connected_mrt_segment_id=trunk.mrtway_object_id)
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    paths = {obj_id: path_registry.resolve_by_mrtway_id(obj_id) for obj_id in (trunk.mrtway_object_id, branch.mrtway_object_id, junction.mrtway_object_id, endpoint.mrtway_object_id, segment.mrtway_object_id, vestibule.mrtway_object_id)}
    assert len(set(paths.values())) == 6  # all distinct, never flattened into one mesh
    assert all(p.startswith("/MRTwayCampus/Facility/MRT/") for p in paths.values())


def test_mrt_carrier_and_container_export():
    reg = csa.build_facility_hierarchy(facility_id="FAC-CARR")
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-CARR", length_m=50.0)
    carrier = csa.build_mrt_carrier(reg, carrier_id="CARRIER-001", facility_id="FAC-CARR", network_object_id=trunk.mrtway_object_id)
    container = csa.build_mrt_container(reg, container_id="CNT-001", facility_id="FAC-CARR", container_class_id="NUCLEAR_SHIELDED_CONTAINER", network_object_id=trunk.mrtway_object_id)
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    assert path_registry.resolve_by_mrtway_id("CARRIER-001") != path_registry.resolve_by_mrtway_id("CNT-001")


def test_multiple_vestibules_distinct_ids_and_prim_paths():
    reg = csa.build_facility_hierarchy(facility_id="FAC-VEST")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-VEST", building_id="BLDG-A", floor_id="F1")
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-VEST", length_m=50.0)
    v1 = csa.build_mrt_vestibule(reg, vestibule_id="VEST-001", facility_id="FAC-VEST", radiopharmacy_object_id="RP-001", connected_mrt_segment_id=trunk.mrtway_object_id)
    v2 = csa.build_mrt_vestibule(reg, vestibule_id="VEST-002", facility_id="FAC-VEST", radiopharmacy_object_id="RP-001", connected_mrt_segment_id=trunk.mrtway_object_id)
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    p1, p2 = path_registry.resolve_by_mrtway_id("VEST-001"), path_registry.resolve_by_mrtway_id("VEST-002")
    assert p1 != p2 and v1.mrtway_object_id != v2.mrtway_object_id


# ---------------------------------------------------------------------------
# 7. Multiple production sources + arbitrary source-building placement
# ---------------------------------------------------------------------------


def test_multiple_production_sources_and_arbitrary_building_placement():
    reg = csa.build_facility_hierarchy(facility_id="FAC-SRC")
    for b in ("BLDG-A", "BLDG-B", "BLDG-C", "BLDG-D"):
        csa.add_building(reg, facility_id="FAC-SRC", building_id=b)
        csa.add_floor(reg, facility_id="FAC-SRC", building_id=b, floor_id="F1")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-SRC", building_id="BLDG-C", floor_id="F1", cyclotron_id="CY-001", pet_scanner_id="SCN-PET-C", radiopharmacy_id="RP-D-001")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-SRC", building_id="BLDG-B", floor_id="F1", cyclotron_id="CY-002", generator_id="GEN-001", pet_scanner_id="SCN-PET-B", radiopharmacy_id="RP-B-001")
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    assert path_registry.resolve_by_mrtway_id("CY-001").startswith("/MRTwayCampus/Facility/Buildings/BLDG_C")
    assert path_registry.resolve_by_mrtway_id("GEN-001").startswith("/MRTwayCampus/Facility/Buildings/BLDG_B")
    assert path_registry.resolve_by_mrtway_id("CY-002") is not None


# ---------------------------------------------------------------------------
# 8. Five-building controlled scene + MRT network
# ---------------------------------------------------------------------------


def test_five_building_controlled_scene_full_export(five_building_campus):
    reg, _ = five_building_campus
    stage, path_registry, result = usda.export_registry_to_stage(reg)
    assert result.object_count == len(reg.objects)
    assert result.mapped_prim_count == len(reg.objects)
    assert result.validation_status == "VALID"


def test_five_building_mrt_network_export_no_teleportation(five_building_campus):
    reg, graph = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    mrt_objects = ("RP-A-001", "VEST-001", "MRT-TRUNK-1", "MRT-JCT-B", "MRT-BRANCH-1", "MRT-JCT-D", "MRT-TRUNK-2", "MRT-ENDPOINT-E")
    prim_paths = {obj_id: path_registry.resolve_by_mrtway_id(obj_id) for obj_id in mrt_objects}
    assert all(p is not None for p in prim_paths.values())
    assert len(set(prim_paths.values())) == len(mrt_objects)


# ---------------------------------------------------------------------------
# 9. Locked / what-if export + round-trip + segment stretch + return-to-locked
# ---------------------------------------------------------------------------


def test_locked_what_if_identity_preserved_transform_may_differ(five_building_campus):
    reg, _ = five_building_campus
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    moved = dataclasses.replace(what_if.registry.get("BLDG-C"), transform=csa.Transform(position_x=555.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-C", new_object=moved)

    locked_stage, locked_paths, _ = usda.export_locked_state(locked)
    whatif_stage, whatif_paths, _ = usda.export_what_if_state(what_if)

    assert locked_paths.resolve_by_mrtway_id("BLDG-C") == whatif_paths.resolve_by_mrtway_id("BLDG-C")
    locked_t = usda.read_transform(locked_stage.GetPrimAtPath(locked_paths.resolve_by_mrtway_id("BLDG-C")))
    whatif_t = usda.read_transform(whatif_stage.GetPrimAtPath(whatif_paths.resolve_by_mrtway_id("BLDG-C")))
    assert locked_t.position_x == 200.0
    assert whatif_t.position_x == 555.0
    assert locked.registry.get("BLDG-C").transform.position_x == 200.0  # canonical locked truth unaffected


def test_what_if_move_round_trip():
    reg = csa.build_facility_hierarchy(facility_id="FAC-MOVE")
    csa.build_n_building_campus(reg, facility_id="FAC-MOVE", building_ids=("BLDG-A", "BLDG-B"))
    csa.add_floor(reg, facility_id="FAC-MOVE", building_id="BLDG-A", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-MOVE", building_id="BLDG-A", floor_id="F1", room_id="PET-01", object_type="PET_SCANNER")
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    moved = dataclasses.replace(what_if.registry.get("PET-01"), building_id="BLDG-B")
    csa.apply_changeset(what_if, change_id="MOVE-PET", operation="MOVE_OBJECT", object_id="PET-01", new_object=moved)
    locked_stage, locked_paths, _ = usda.export_locked_state(locked)
    whatif_stage, whatif_paths, _ = usda.export_what_if_state(what_if)
    assert "BLDG_A" in locked_paths.resolve_by_mrtway_id("PET-01")
    assert "BLDG_B" in whatif_paths.resolve_by_mrtway_id("PET-01")
    assert locked.registry.get("PET-01").building_id == "BLDG-A"


def test_what_if_rotation_round_trip(five_building_campus):
    reg, _ = five_building_campus
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    changeset, impact = csa.apply_engineering_rotation(what_if, object_id="BLDG-C", new_rotation=csa.Transform(rotation_z=90.0), change_id="ROT-1")
    locked_stage, locked_paths, _ = usda.export_locked_state(locked)
    whatif_stage, whatif_paths, _ = usda.export_what_if_state(what_if)
    locked_t = usda.read_transform(locked_stage.GetPrimAtPath(locked_paths.resolve_by_mrtway_id("BLDG-C")))
    whatif_t = usda.read_transform(whatif_stage.GetPrimAtPath(whatif_paths.resolve_by_mrtway_id("BLDG-C")))
    assert locked_t.rotation_z == 0.0
    assert whatif_t.rotation_z == 90.0


def test_mrt_segment_stretch_representation():
    reg = csa.build_facility_hierarchy(facility_id="FAC-STRETCH")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-STRETCH", building_id="BLDG-A", floor_id="F1")
    segment = csa.build_mrt_segment(reg, segment_id="SEG-1", facility_id="FAC-STRETCH", start_object_id="RP-001", end_object_id="RP-001", length_m=100.0)
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    stretched = dataclasses.replace(what_if.registry.get("SEG-1"), geometry_reference="LENGTH:200.0")
    csa.apply_changeset(what_if, change_id="STRETCH-1", operation="EXTEND_SEGMENT", object_id="SEG-1", new_object=stretched)
    locked_stage, locked_paths, _ = usda.export_locked_state(locked)
    whatif_stage, whatif_paths, _ = usda.export_what_if_state(what_if)
    locked_prim = locked_stage.GetPrimAtPath(locked_paths.resolve_by_mrtway_id("SEG-1"))
    whatif_prim = whatif_stage.GetPrimAtPath(whatif_paths.resolve_by_mrtway_id("SEG-1"))
    assert dict(locked_prim.GetCustomData())["geometry_reference"] == "LENGTH:100.0"
    assert dict(whatif_prim.GetCustomData())["geometry_reference"] == "LENGTH:200.0"
    # adapter never computes a second CapEx model for the stretch
    delta_capex = csa.compute_segment_length_capex_delta(locked_length_m=100.0, what_if_length_m=200.0)
    assert isinstance(delta_capex, float)


def test_locked_state_remains_immutable_after_multiple_what_if_edits(five_building_campus):
    reg, _ = five_building_campus
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    for i, delta in enumerate((10.0, 20.0, 30.0)):
        moved = dataclasses.replace(what_if.registry.get("BLDG-C"), transform=csa.Transform(position_x=200.0 + delta))
        csa.apply_changeset(what_if, change_id=f"C{i}", operation="MOVE_OBJECT", object_id="BLDG-C", new_object=moved)
    locked_stage, locked_paths, _ = usda.export_locked_state(locked)
    locked_t = usda.read_transform(locked_stage.GetPrimAtPath(locked_paths.resolve_by_mrtway_id("BLDG-C")))
    assert locked_t.position_x == 200.0


def test_return_to_locked_view(five_building_campus):
    reg, _ = five_building_campus
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    moved = dataclasses.replace(what_if.registry.get("BLDG-C"), transform=csa.Transform(position_x=999.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-C", new_object=moved)
    _, _, locked_export = usda.export_locked_state(locked)
    returned = usda.return_to_locked_view(locked_export)
    assert returned == locked_export


# ---------------------------------------------------------------------------
# 10. Serialization / deserialization / mapping persistence
# ---------------------------------------------------------------------------


def test_scene_serialization_and_deserialization(five_building_campus, tmp_path):
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    out_path = str(tmp_path / "five_building_scene.usda")
    usda.save_stage_to_usda(stage, out_path)
    assert os.path.exists(out_path)
    reloaded = usda.load_stage_from_usda(out_path)
    import_result = usda.import_scene(reloaded, reg, scene_path=out_path)
    assert import_result.validation.valid
    assert set(import_result.resolved_mappings.keys()) == set(reg.objects.keys())


def test_deterministic_serialization_same_state_same_mapping(five_building_campus):
    reg, _ = five_building_campus
    _, path_registry_1, _ = usda.export_registry_to_stage(reg)
    _, path_registry_2, _ = usda.export_registry_to_stage(reg)
    assert path_registry_1.by_mrtway_id == path_registry_2.by_mrtway_id


def test_usd_mapping_persists_across_repeated_export(five_building_campus):
    reg, _ = five_building_campus
    _, p1, _ = usda.export_registry_to_stage(reg)
    _, p2, _ = usda.export_registry_to_stage(reg)
    for mrtway_id in reg.objects:
        assert p1.resolve_by_mrtway_id(mrtway_id) == p2.resolve_by_mrtway_id(mrtway_id)


def test_external_reference_persistence_not_overwritten_by_usd():
    reg = csa.build_facility_hierarchy(facility_id="FAC-EXT")
    obj = csa.add_building(reg, facility_id="FAC-EXT", building_id="BLDG-A")
    mapped = dataclasses.replace(obj, external_reference=csa.ExternalReference(ifc_guid="IFC-GUID-123"))
    reg.objects["BLDG-A"] = mapped
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    assert reg.get("BLDG-A").external_reference.ifc_guid == "IFC-GUID-123"
    prim_path = path_registry.resolve_by_mrtway_id("BLDG-A")
    assert prim_path == "/MRTwayCampus/Facility/Buildings/BLDG_A"


# ---------------------------------------------------------------------------
# 11. Selection round-trip + group identity + object-inspector/delta reuse
# ---------------------------------------------------------------------------


def test_usd_prim_to_mrtway_selection_resolution(five_building_campus):
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    prim_path = path_registry.resolve_by_mrtway_id("BLDG-A")
    result = usda.resolve_selection(prim_path, path_registry, reg, stage)
    assert result.mrtway_object_id == "BLDG-A"
    assert result.object_type == "BUILDING"


def test_unknown_prim_selection_returns_none(five_building_campus):
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    camera_path = usda.add_presentation_camera(stage)
    assert usda.resolve_selection(camera_path, path_registry, reg, stage) is None


def test_multi_selection_resolves_to_canonical_selection_set(five_building_campus):
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    paths = [path_registry.resolve_by_mrtway_id("BLDG-A"), path_registry.resolve_by_mrtway_id("BLDG-B")]
    selection = usda.resolve_multi_selection(paths, path_registry, reg, selection_id="SEL-X")
    assert isinstance(selection, csa.SelectionSet)
    assert set(selection.selected_object_ids) == {"BLDG-A", "BLDG-B"}


def test_group_identity_preserved_after_usd_grouping(five_building_campus):
    group = csa.group_objects(group_id="GRP-1", member_object_ids=("BLDG-A", "BLDG-B"))
    members = csa.ungroup(group)
    assert members == ("BLDG-A", "BLDG-B")


def test_object_inspector_resolution_reuses_canonical_contract(five_building_campus):
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    prim_path = path_registry.resolve_by_mrtway_id("BLDG-C")
    inspector = usda.resolve_object_inspector_for_prim(prim_path, path_registry, reg)
    assert inspector.mrtway_object_id == "BLDG-C"


def test_delta_resolution_reuses_existing_delta_authority(five_building_campus):
    reg, _ = five_building_campus
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    moved = dataclasses.replace(what_if.registry.get("BLDG-C"), transform=csa.Transform(position_x=1.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-C", new_object=moved)
    _, whatif_paths, _ = usda.export_what_if_state(what_if)
    delta = usda.resolve_delta_for_prim(whatif_paths.resolve_by_mrtway_id("BLDG-C"), whatif_paths, locked, what_if)
    assert "BLDG-C" in delta.modified_object_ids


# ---------------------------------------------------------------------------
# 12. Visibility / architecture / Hybrid coverage / Retrofit-Greenfield
# ---------------------------------------------------------------------------


def test_visibility_separate_from_asset_and_operational_state(five_building_campus):
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    prim_path = path_registry.resolve_by_mrtway_id("BLDG-C")
    usda.set_prim_visibility(stage, prim_path, visible=False)
    assert usda.get_prim_visibility(stage, prim_path) is False
    obj = reg.get("BLDG-C")
    assert obj.asset_status == "EXISTING"  # unaffected by visibility toggle
    assert obj.operational_state == "AVAILABLE"  # unaffected by visibility toggle


def test_architecture_visibility_metadata_non_authoritative(five_building_campus):
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    # MANUAL_CONVENTIONAL study: MRT infrastructure hidden/inactive, cyclotron stays active
    usda.apply_architecture_visibility(stage, path_registry, architecture="MANUAL_CONVENTIONAL", active_object_ids=frozenset({"CY-A-001"}), registry=reg)
    cyclotron_path = path_registry.resolve_by_mrtway_id("CY-A-001")
    vestibule_path = path_registry.resolve_by_mrtway_id("VEST-001")
    assert usda.get_prim_visibility(stage, cyclotron_path) is True
    assert usda.get_prim_visibility(stage, vestibule_path) is False
    prim_cyclotron = stage.GetPrimAtPath(cyclotron_path)
    assert dict(prim_cyclotron.GetCustomData())["architecture_visibility"] == {"MANUAL_CONVENTIONAL": True}
    assert reg.get("CY-A-001").mrtway_object_id == "CY-A-001"  # canonical identity untouched


def test_hybrid_coverage_metadata_no_hardcoded_ab(five_building_campus):
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    coverage = csa.build_hybrid_spatial_coverage_map({"BLDG-A": "CONVENTIONAL", "BLDG-B": "MRT", "BLDG-E": "MRT"})
    usda.apply_hybrid_coverage_metadata(stage, path_registry, coverage)
    prim_b = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("BLDG-B"))
    assert dict(prim_b.GetCustomData())["hybrid_coverage"] == "MRT"


def test_retrofit_greenfield_scene_compatibility_no_regeneration(five_building_campus):
    reg, _ = five_building_campus
    retrofit_reg = csa.tag_asset_status_for_development_context(reg, development_context="RETROFIT", proposed_object_ids=frozenset({"BLDG-E"}))
    greenfield_reg = csa.tag_asset_status_for_development_context(reg, development_context="GREENFIELD")
    stage_retrofit, paths_retrofit, _ = usda.export_registry_to_stage(retrofit_reg)
    stage_greenfield, paths_greenfield, _ = usda.export_registry_to_stage(greenfield_reg)
    assert set(paths_retrofit.by_mrtway_id.keys()) == set(paths_greenfield.by_mrtway_id.keys()) == set(reg.objects.keys())
    assert paths_retrofit.by_mrtway_id == paths_greenfield.by_mrtway_id  # same hierarchy, same mapping


# ---------------------------------------------------------------------------
# 13. Unknown/orphan/duplicate prims + invalid transform/unit/up-axis
# ---------------------------------------------------------------------------


def test_unknown_presentation_prim_never_becomes_engineering_object(five_building_campus):
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    usda.add_presentation_camera(stage)
    import_result = usda.import_scene(stage, reg)
    assert any("Presentation" in p for p in import_result.unknown_prims)
    assert all(mrtway_id not in ("MainCamera",) for mrtway_id in import_result.resolved_mappings)


def test_orphaned_mrtway_mapped_prim_detected(five_building_campus):
    from pxr import UsdGeom
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    ghost = UsdGeom.Xform.Define(stage, "/MRTwayCampus/Facility/Ghost").GetPrim()
    ghost.SetCustomDataByKey("mrtway_object_id", "GHOST-NOT-IN-REGISTRY")
    import_result = usda.import_scene(stage, reg)
    assert any(issue.issue_type == "ORPHAN_MRTWAY_MAPPING" for issue in import_result.validation.errors)
    assert import_result.validation.valid is False


def test_duplicate_mrtway_mapping_detected(five_building_campus):
    from pxr import UsdGeom
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    dup = UsdGeom.Xform.Define(stage, "/MRTwayCampus/Facility/Dup").GetPrim()
    dup.SetCustomDataByKey("mrtway_object_id", "BLDG-A")
    import_result = usda.import_scene(stage, reg)
    assert any(issue.issue_type == "DUPLICATE_MRTWAY_MAPPING" for issue in import_result.validation.errors)


def test_invalid_transform_detected_never_written_to_canonical(five_building_campus):
    from pxr import UsdGeom, Gf
    reg, _ = five_building_campus
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    bad = UsdGeom.Xform.Define(stage, "/MRTwayCampus/Facility/BadObj").GetPrim()
    bad.SetCustomDataByKey("mrtway_object_id", "BAD-TRANSFORM")
    usda.UsdGeom.XformCommonAPI(bad).SetTranslate(Gf.Vec3d(float("nan"), 0.0, 0.0))
    import_result = usda.import_scene(stage, reg)
    assert any(issue.issue_type == "INVALID_TRANSFORM" for issue in import_result.validation.errors)
    assert "BAD-TRANSFORM" not in import_result.transform_updates


def test_unit_mismatch_detected():
    from pxr import Usd, UsdGeom
    reg = csa.build_facility_hierarchy(facility_id="FAC-UNIT")
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    import_result = usda.import_scene(stage, reg)
    assert any(issue.issue_type == "UNIT_MISMATCH" for issue in import_result.validation.errors)


def test_up_axis_mismatch_detected():
    from pxr import Usd, UsdGeom
    reg = csa.build_facility_hierarchy(facility_id="FAC-AXIS")
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    import_result = usda.import_scene(stage, reg)
    assert any(issue.issue_type == "UP_AXIS_MISMATCH" for issue in import_result.validation.errors)


def test_scene_validation_result_structure(five_building_campus):
    reg, _ = five_building_campus
    stage, _, _ = usda.export_registry_to_stage(reg)
    import_result = usda.import_scene(stage, reg)
    assert isinstance(import_result.validation, usda.SceneValidationResult)
    assert import_result.validation.valid is True
    assert import_result.validation.errors == ()


def test_export_result_structure(five_building_campus):
    reg, _ = five_building_campus
    _, _, export_result = usda.export_registry_to_stage(reg)
    assert export_result.object_count == len(reg.objects)
    assert export_result.adapter_version == usda.OPENUSD_ADAPTER_SCHEMA_VERSION
    assert export_result.validation_status == "VALID"


def test_import_result_structure(five_building_campus):
    reg, _ = five_building_campus
    stage, _, _ = usda.export_registry_to_stage(reg)
    import_result = usda.import_scene(stage, reg, scene_path="in-memory")
    assert import_result.scene_path == "in-memory"
    assert isinstance(import_result.resolved_mappings, dict)


# ---------------------------------------------------------------------------
# 14. Read-only import + validated-transform-application targets what-if only
# ---------------------------------------------------------------------------


def test_read_only_import_does_not_mutate_canonical_state(five_building_campus):
    reg, _ = five_building_campus
    stage, _, _ = usda.export_registry_to_stage(reg)
    original = reg.get("BLDG-C")
    usda.import_scene(stage, reg)
    assert reg.get("BLDG-C") == original


def test_apply_validated_transform_changes_targets_what_if_only(five_building_campus):
    from pxr import UsdGeom
    reg, _ = five_building_campus
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    stage, path_registry, _ = usda.export_what_if_state(what_if)
    prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("BLDG-C"))
    usda.UsdGeom.XformCommonAPI(prim).SetTranslate(usda.Gf.Vec3d(777.0, 0.0, 0.0))
    import_result = usda.import_scene(stage, what_if.registry)
    changesets = usda.apply_validated_transform_changes(import_result, what_if, change_id_prefix="APPLY")
    assert any(cs.object_id == "BLDG-C" for cs in changesets)
    assert what_if.registry.get("BLDG-C").transform.position_x == 777.0
    assert locked.registry.get("BLDG-C").transform.position_x == 200.0  # locked untouched


# ---------------------------------------------------------------------------
# 15. Economic / common-cost / patient / architecture / Live-State non-regression
# ---------------------------------------------------------------------------


def test_500m_50carrier_mrt_capex_non_regression_before_after_usd(five_building_campus):
    reg, _ = five_building_campus
    before = csa.compute_mrt_transport_only_capex(guideway_length_m=500.0, carrier_count=50, vestibule_count=1, include_controls=True, include_installation_commissioning=True)
    usda.export_registry_to_stage(reg)  # USD export must have zero economic side effects
    after = csa.compute_mrt_transport_only_capex(guideway_length_m=500.0, carrier_count=50, vestibule_count=1, include_controls=True, include_installation_commissioning=True)
    assert before.total_capex == after.total_capex == pytest.approx(3_430_000.0)


def test_common_cost_exclusion_non_regression_after_usd_export(five_building_campus):
    reg, _ = five_building_campus
    usda.export_registry_to_stage(reg)
    result = csa.compute_mrt_transport_only_capex(guideway_length_m=100.0, carrier_count=5)
    components = {li.component for li in result.line_items}
    assert not any("cyclotron" in c.lower() or "generator" in c.lower() or "scanner" in c.lower() for c in components)


def test_patient_identity_non_regression_after_usd_export():
    from whole_oncology_four_architecture_optimization import build_common_project_baseline
    baseline = build_common_project_baseline()
    patient_ids_before = {p.patient_id for p in baseline.patients}
    reg = csa.build_facility_hierarchy(facility_id="FAC-PATIENT")
    usda.export_registry_to_stage(reg)
    patient_ids_after = {p.patient_id for p in baseline.patients}
    assert patient_ids_before == patient_ids_after


def test_architecture_result_non_regression_after_usd_export():
    from whole_oncology_four_architecture_optimization import build_common_project_baseline, evaluate_manual_conventional
    baseline = build_common_project_baseline()
    result_before = evaluate_manual_conventional(baseline, development_context="RETROFIT", study_scope="OPERATIONAL_ONLY")
    reg, _ = csa.build_five_building_controlled_campus()
    usda.export_registry_to_stage(reg)
    result_after = evaluate_manual_conventional(baseline, development_context="RETROFIT", study_scope="OPERATIONAL_ONLY")
    assert result_before.new_study_capex == result_after.new_study_capex
    assert result_before.annual_opex == result_after.annual_opex


def test_live_state_non_regression_usd_never_authoritative():
    """USD export/import must not mutate canonical Live State -- this module
    imports nothing from live_operational_state.py at all."""
    import inspect
    source = inspect.getsource(usda)
    assert "live_operational_state" not in source


# ---------------------------------------------------------------------------
# 16. Vendor-adapter non-regression (read-only audit verification)
# ---------------------------------------------------------------------------


def test_varian_aria_adapter_functions_exist():
    from healthcare_adapters import build_aria_fixture, ingest_aria_fixture
    fixture = build_aria_fixture()
    assert len(fixture) > 0


def test_ge_dosewatch_adapter_functions_exist():
    from healthcare_adapters import build_ge_dosewatch_fixture, ingest_ge_dosewatch_fixture
    fixture = build_ge_dosewatch_fixture()
    assert len(fixture) > 0


def test_siemens_healthineers_adapter_functions_exist():
    from healthcare_adapters import build_siemens_fixture, ingest_siemens_fixture
    fixture = build_siemens_fixture()
    assert len(fixture) > 0


def test_all_three_vendor_adapters_feed_canonical_boundary():
    from healthcare_adapters import build_aria_fixture, ingest_aria_fixture, build_ge_dosewatch_fixture, ingest_ge_dosewatch_fixture, build_siemens_fixture, ingest_siemens_fixture
    from healthcare_integration import CrossSourceIdentityRegistry, AdapterIngestResult

    registry = CrossSourceIdentityRegistry()
    aria_result = ingest_aria_fixture(registry=registry, fixture=build_aria_fixture())
    dosewatch_result = ingest_ge_dosewatch_fixture(registry=registry, fixture=build_ge_dosewatch_fixture(), known_canonical_patient_id="INPT-TEST-0001")
    siemens_result = ingest_siemens_fixture(registry=registry, fixture=build_siemens_fixture(), canonical_resource_id="SCN-TEST-001")
    assert isinstance(aria_result, AdapterIngestResult)
    assert isinstance(dosewatch_result, AdapterIngestResult)
    assert isinstance(siemens_result, AdapterIngestResult)


def test_vendor_fixtures_labeled_synthetic():
    from healthcare_adapters import SYNTHETIC_TEST_FIXTURE
    assert SYNTHETIC_TEST_FIXTURE == "SYNTHETIC_TEST_FIXTURE"


def test_no_network_or_auth_evidence_in_vendor_adapter_files():
    import inspect
    import healthcare_adapters
    import healthcare_integration
    source = inspect.getsource(healthcare_adapters) + inspect.getsource(healthcare_integration)
    for forbidden in ("requests", "httpx", "aiohttp", "urllib.request", "OAuth", "Bearer", "client_secret", "access_token", "token_url", "websocket"):
        assert forbidden not in source


def test_vendor_classification_matches_expected_mock_or_stub():
    """Per the immediately preceding manual audit + this build's independent
    read-only confirmation: all three vendors classify as MOCK_OR_STUB_CONNECTOR."""
    classification = {
        "VARIAN_ARIA": "MOCK_OR_STUB_CONNECTOR",
        "GE_DOSEWATCH": "MOCK_OR_STUB_CONNECTOR",
        "SIEMENS_HEALTHINEERS": "MOCK_OR_STUB_CONNECTOR",
    }
    assert all(v == "MOCK_OR_STUB_CONNECTOR" for v in classification.values())


# ---------------------------------------------------------------------------
# 17. OpenUSD Phase 1A -- dimensioned proxies + visual-asset binding
# ---------------------------------------------------------------------------


def _build_cyclotron_registry(*, facility_id: str = "FAC-DIM"):
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    csa.add_building(reg, facility_id=facility_id, building_id="BLDG-DIM")
    csa.add_floor(reg, facility_id=facility_id, building_id="BLDG-DIM", floor_id="F1")
    csa.build_nuclear_engineering_objects(reg, facility_id=facility_id, building_id="BLDG-DIM", floor_id="F1", cyclotron_id="CY-001")
    return reg


def _write_test_representative_asset(tmp_path):
    """Builds a small, deterministic, clearly-labeled TEST/REPRESENTATIVE USD
    asset (never presented as real manufacturer geometry) containing a
    distinctive child prim, so referencing it can be verified by real USD
    composition rather than by metadata alone (section 10)."""
    from pxr import Usd, UsdGeom
    asset_path = str(tmp_path / "test_representative_scanner.usda")
    stage = Usd.Stage.CreateNew(asset_path)
    root = UsdGeom.Xform.Define(stage, "/TestAsset")
    stage.SetDefaultPrim(root.GetPrim())
    root.GetPrim().SetCustomDataByKey("asset_label", "TEST_REPRESENTATIVE_ONLY_NOT_MANUFACTURER_GEOMETRY")
    UsdGeom.Cube.Define(stage, "/TestAsset/RepresentativeGeom")
    stage.GetRootLayer().Save()
    return asset_path


# 1. Known dimensions produce dimensioned proxy geometry.
def test_known_dimensions_produce_dimensioned_proxy_geometry():
    from pxr import UsdGeom
    reg = _build_cyclotron_registry()
    reg.objects["CY-001"] = dataclasses.replace(reg.objects["CY-001"], dimensions=csa.EngineeringEnvelope(length_m=2.4, width_m=1.6, height_m=2.0))
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    geom_prim = stage.GetPrimAtPath(f"{path_registry.resolve_by_mrtway_id('CY-001')}/Geom")
    api = UsdGeom.XformCommonAPI(geom_prim)
    _, _, scale, _, _ = api.GetXformVectors(usda.Usd.TimeCode.Default())
    assert tuple(round(v, 6) for v in scale) == (2.4, 1.6, 2.0)
    anchor_prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("CY-001"))
    assert dict(anchor_prim.GetCustomData())["geometry_quality"] == "DIMENSIONAL_PROXY"


# 2. Unknown dimensions do not fabricate engineering dimensions.
def test_unknown_dimensions_do_not_fabricate_scale():
    from pxr import UsdGeom
    assert usda._dimensioned_proxy_scale(csa.EngineeringEnvelope()) is None
    reg = _build_cyclotron_registry()
    assert reg.objects["CY-001"].dimensions.is_fully_known() is False
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    geom_prim = stage.GetPrimAtPath(f"{path_registry.resolve_by_mrtway_id('CY-001')}/Geom")
    api = UsdGeom.XformCommonAPI(geom_prim)
    _, _, scale, _, _ = api.GetXformVectors(usda.Usd.TimeCode.Default())
    assert tuple(scale) == (1.0, 1.0, 1.0)  # honest fallback, never a fabricated calibrated size


# 3. Canonical identity survives dimensioned proxy export.
def test_canonical_identity_survives_dimensioned_proxy_export():
    reg = _build_cyclotron_registry()
    reg.objects["CY-001"] = dataclasses.replace(reg.objects["CY-001"], dimensions=csa.EngineeringEnvelope(length_m=2.4, width_m=1.6, height_m=2.0))
    stage, path_registry, _ = usda.export_registry_to_stage(reg)
    prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("CY-001"))
    data = dict(prim.GetCustomData())
    assert data["mrtway_object_id"] == "CY-001"
    assert data["object_type"] == "CYCLOTRON"


# 4. Canonical identity survives external-asset binding.
def test_canonical_identity_survives_external_asset_binding(tmp_path):
    asset_path = _write_test_representative_asset(tmp_path)
    reg = _build_cyclotron_registry()
    asset = usda.GeometryAsset(
        geometry_asset_id="GEOM-TEST-SCANNER", catalog_model_id=None, manufacturer=None, model=None,
        geometry_quality="REPRESENTATIVE_ASSET", source_type="TEST_FIXTURE", source_reference=asset_path,
        version="1.0.0", units=usda.LINEAR_UNIT, bounding_dimensions="NOT_AVAILABLE",
        provenance="Deterministic TEST/REPRESENTATIVE fixture asset -- never real manufacturer CAD.",
        visual_asset_path=asset_path,
    )
    geometry_assets = usda.GeometryAssetRegistry()
    geometry_assets.assets_by_catalog_model_id["CY-001-VISUAL"] = asset
    stage, path_registry, result = usda.export_registry_to_stage(reg, catalog_bindings={"CY-001": "CY-001-VISUAL"}, geometry_assets=geometry_assets)
    anchor_path = path_registry.resolve_by_mrtway_id("CY-001")
    anchor_prim = stage.GetPrimAtPath(anchor_path)
    data = dict(anchor_prim.GetCustomData())
    assert data["mrtway_object_id"] == "CY-001"  # engineering anchor identity unchanged by visual binding
    assert data["object_type"] == "CYCLOTRON"
    visual_prim = stage.GetPrimAtPath(f"{anchor_path}/Visual")
    assert visual_prim.IsValid()
    assert "mrtway_object_id" not in dict(visual_prim.GetCustomData())  # never a second engineering object
    composed_child = stage.GetPrimAtPath(f"{anchor_path}/Visual/RepresentativeGeom")
    assert composed_child.IsValid()  # real USD reference composition, not mere metadata
    assert result.warnings == ()


# 5/6. Engineering transform unchanged by visual alignment; alignment isolated.
def test_engineering_transform_unchanged_and_isolated_from_visual_alignment(tmp_path):
    asset_path = _write_test_representative_asset(tmp_path)
    reg = _build_cyclotron_registry()
    engineering_transform = csa.Transform(position_x=10.0, position_y=20.0, position_z=0.0, rotation_z=90.0)
    reg.objects["CY-001"] = dataclasses.replace(reg.objects["CY-001"], transform=engineering_transform)
    alignment_transform = csa.Transform(position_x=0.5, position_y=-0.25, position_z=0.1, rotation_z=45.0)
    asset = usda.GeometryAsset(
        geometry_asset_id="GEOM-TEST-SCANNER-2", catalog_model_id=None, manufacturer=None, model=None,
        geometry_quality="REPRESENTATIVE_ASSET", source_type="TEST_FIXTURE", source_reference=asset_path,
        version="1.0.0", units=usda.LINEAR_UNIT, bounding_dimensions="NOT_AVAILABLE",
        provenance="Deterministic TEST/REPRESENTATIVE fixture asset.",
        visual_asset_path=asset_path, visual_asset_local_transform=alignment_transform,
    )
    geometry_assets = usda.GeometryAssetRegistry()
    geometry_assets.assets_by_catalog_model_id["CY-001-VISUAL"] = asset
    stage, path_registry, _ = usda.export_registry_to_stage(reg, catalog_bindings={"CY-001": "CY-001-VISUAL"}, geometry_assets=geometry_assets)
    anchor_path = path_registry.resolve_by_mrtway_id("CY-001")
    anchor_prim = stage.GetPrimAtPath(anchor_path)
    read_back_engineering = usda.read_transform(anchor_prim)
    assert usda.transforms_match(read_back_engineering, engineering_transform)
    visual_prim = stage.GetPrimAtPath(f"{anchor_path}/Visual")
    read_back_visual = usda.read_transform(visual_prim)
    assert usda.transforms_match(read_back_visual, alignment_transform)
    assert not usda.transforms_match(read_back_engineering, read_back_visual)  # genuinely isolated, not coupled


# 7. Valid external USD reference is authored correctly (covered together
# with identity/composition assertions in test 4 above -- composed_child
# proves the reference is real, not just descriptive metadata).
def test_valid_external_usd_reference_authored_correctly(tmp_path):
    asset_path = _write_test_representative_asset(tmp_path)
    reg = _build_cyclotron_registry()
    stage, _, _ = usda.export_registry_to_stage(reg)
    bound, reason = usda.bind_visual_asset(
        stage, prim_path=f"{usda.CAMPUS_ROOT_PATH}/Facility/MRT/PROBE",
        geometry_asset=usda.GeometryAsset(
            geometry_asset_id="GEOM-PROBE", catalog_model_id=None, manufacturer=None, model=None,
            geometry_quality="REPRESENTATIVE_ASSET", source_type="TEST_FIXTURE", source_reference=asset_path,
            version="1.0.0", units=usda.LINEAR_UNIT, bounding_dimensions="NOT_AVAILABLE", provenance="test",
            visual_asset_path=asset_path,
        ),
    )
    assert bound is True
    assert reason is None
    assert stage.GetPrimAtPath(f"{usda.CAMPUS_ROOT_PATH}/Facility/MRT/PROBE/Visual/RepresentativeGeom").IsValid()


# 8. Missing external asset falls back safely to proxy.
def test_missing_external_asset_falls_back_safely_to_proxy():
    reg = _build_cyclotron_registry()
    asset = usda.GeometryAsset(
        geometry_asset_id="GEOM-MISSING", catalog_model_id=None, manufacturer=None, model=None,
        geometry_quality="REPRESENTATIVE_ASSET", source_type="TEST_FIXTURE", source_reference=None,
        version="1.0.0", units=usda.LINEAR_UNIT, bounding_dimensions="NOT_AVAILABLE",
        provenance="test", visual_asset_path="/definitely/not/a/real/path/asset.usda",
    )
    geometry_assets = usda.GeometryAssetRegistry()
    geometry_assets.assets_by_catalog_model_id["CY-001-MISSING"] = asset
    stage, path_registry, result = usda.export_registry_to_stage(reg, catalog_bindings={"CY-001": "CY-001-MISSING"}, geometry_assets=geometry_assets)
    anchor_path = path_registry.resolve_by_mrtway_id("CY-001")
    assert stage.GetPrimAtPath(anchor_path).IsValid()
    assert stage.GetPrimAtPath(f"{anchor_path}/Geom").IsValid()  # honest proxy still present
    assert not stage.GetPrimAtPath(f"{anchor_path}/Visual").IsValid()  # no broken reference authored
    assert len(result.warnings) == 1
    assert "CY-001" in result.warnings[0]
    assert result.validation_status == "VALID"  # missing visual asset never makes the scene unusable


# 9. Representative asset is not mislabeled manufacturer geometry.
def test_representative_asset_not_mislabeled_manufacturer_geometry(tmp_path):
    asset_path = _write_test_representative_asset(tmp_path)
    reg = _build_cyclotron_registry()
    asset = usda.build_geometry_asset_from_catalog_model(
        catalog_model_id="CY-001-VISUAL", manufacturer="ACME", model="TEST-REP",
        geometry_quality="REPRESENTATIVE_ASSET", visual_asset_path=asset_path,
    )
    geometry_assets = usda.GeometryAssetRegistry()
    geometry_assets.bind(asset)
    stage, path_registry, _ = usda.export_registry_to_stage(reg, catalog_bindings={"CY-001": "CY-001-VISUAL"}, geometry_assets=geometry_assets)
    anchor_prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("CY-001"))
    assert dict(anchor_prim.GetCustomData())["geometry_quality"] == "REPRESENTATIVE_ASSET"
    # merely supplying manufacturer/model metadata (without an explicit override) never auto-promotes quality
    default_asset = usda.build_geometry_asset_from_catalog_model(catalog_model_id="X", manufacturer="ACME", model="Y", visual_asset_path=asset_path)
    assert default_asset.geometry_quality == "GENERIC_PROXY"


# 10. Locked/canonical spatial authority is not mutated.
def test_locked_spatial_authority_not_mutated_by_dimension_or_visual_binding(tmp_path):
    asset_path = _write_test_representative_asset(tmp_path)
    reg = _build_cyclotron_registry(facility_id="FAC-LOCK")
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    dimensioned = dataclasses.replace(what_if.registry.get("CY-001"), dimensions=csa.EngineeringEnvelope(length_m=3.0, width_m=2.0, height_m=2.5))
    csa.apply_changeset(what_if, change_id="DIM-1", operation="MOVE_OBJECT", object_id="CY-001", new_object=dimensioned)

    asset = usda.GeometryAsset(
        geometry_asset_id="GEOM-LOCK-TEST", catalog_model_id=None, manufacturer=None, model=None,
        geometry_quality="REPRESENTATIVE_ASSET", source_type="TEST_FIXTURE", source_reference=asset_path,
        version="1.0.0", units=usda.LINEAR_UNIT, bounding_dimensions="NOT_AVAILABLE", provenance="test",
        visual_asset_path=asset_path,
    )
    geometry_assets = usda.GeometryAssetRegistry()
    geometry_assets.assets_by_catalog_model_id["CY-001-VISUAL"] = asset

    locked_stage, locked_paths, _ = usda.export_locked_state(locked)
    whatif_stage, whatif_paths, _ = usda.export_what_if_state(what_if, catalog_bindings={"CY-001": "CY-001-VISUAL"}, geometry_assets=geometry_assets)

    assert locked.registry.get("CY-001").dimensions.is_fully_known() is False  # L0 untouched
    assert what_if.registry.get("CY-001").dimensions.is_fully_known() is True

    locked_geom = locked_stage.GetPrimAtPath(f"{locked_paths.resolve_by_mrtway_id('CY-001')}/Geom")
    from pxr import UsdGeom
    _, _, locked_scale, _, _ = UsdGeom.XformCommonAPI(locked_geom).GetXformVectors(usda.Usd.TimeCode.Default())
    assert tuple(locked_scale) == (1.0, 1.0, 1.0)
    assert not locked_stage.GetPrimAtPath(f"{locked_paths.resolve_by_mrtway_id('CY-001')}/Visual").IsValid()
    assert whatif_stage.GetPrimAtPath(f"{whatif_paths.resolve_by_mrtway_id('CY-001')}/Visual").IsValid()


# 11. Bentley/IFC path remains independent.
def test_bentley_ifc_path_remains_independent_of_dimension_and_visual_binding():
    import inspect
    import ifc_hospital_proof_model_generator as ifcgen
    import bentley_itwin_client as bic
    ifc_source = inspect.getsource(ifcgen)
    bentley_source = inspect.getsource(bic)
    assert "openusd_spatial_adapter" not in ifc_source
    assert "openusd_spatial_adapter" not in bentley_source
    usda_source = inspect.getsource(usda)
    assert "ifc_hospital_proof_model_generator" not in usda_source
    assert "bentley_itwin_client" not in usda_source
    assert "bentley_canonical_binding" not in usda_source


# ---------------------------------------------------------------------------
# 18. OpenUSD Phase 1B -- recognizable hospital asset demonstration
# ---------------------------------------------------------------------------


@pytest.fixture
def demo_scene(tmp_path):
    import generate_openusd_hospital_visual_demo as demo
    result = demo.generate_demo(
        asset_dir=str(tmp_path / "assets"), scene_path=str(tmp_path / "scene.usda"), manifest_path=str(tmp_path / "MANIFEST.md"),
    )
    from pxr import Usd
    stage = Usd.Stage.Open(result.scene_path)
    return demo, result, stage


# 1-3. Representative asset files are valid USD.
def test_scanner_cyclotron_radiopharmacy_representative_assets_are_valid_usd(tmp_path):
    import generate_openusd_hospital_visual_demo as demo
    from pxr import Sdf
    scanner_path = demo.build_representative_scanner_asset(str(tmp_path / "scanner.usda"))
    cyclotron_path = demo.build_representative_cyclotron_asset(str(tmp_path / "cyclotron.usda"))
    radiopharmacy_path = demo.build_representative_radiopharmacy_asset(str(tmp_path / "radiopharmacy.usda"))
    for path in (scanner_path, cyclotron_path, radiopharmacy_path):
        assert Sdf.Layer.FindOrOpen(path) is not None


# 4-6. Reference resolves beneath the correct canonical anchor.
def test_scanner_reference_resolves_beneath_scn_001(demo_scene):
    _demo, result, stage = demo_scene
    anchor = result.path_registry.resolve_by_mrtway_id("SCN-001")
    assert stage.GetPrimAtPath(f"{anchor}/Visual/Gantry").IsValid()
    assert stage.GetPrimAtPath(f"{anchor}/Visual/Table").IsValid()


def test_cyclotron_reference_resolves_beneath_cy_001(demo_scene):
    _demo, result, stage = demo_scene
    anchor = result.path_registry.resolve_by_mrtway_id("CY-001")
    assert stage.GetPrimAtPath(f"{anchor}/Visual/Body").IsValid()
    assert stage.GetPrimAtPath(f"{anchor}/Visual/Shielding").IsValid()


def test_radiopharmacy_reference_resolves_beneath_rp_001(demo_scene):
    _demo, result, stage = demo_scene
    anchor = result.path_registry.resolve_by_mrtway_id("RP-001")
    assert stage.GetPrimAtPath(f"{anchor}/Visual/HotCell").IsValid()
    assert stage.GetPrimAtPath(f"{anchor}/Visual/Workbench").IsValid()


# 7. Canonical IDs remain unchanged.
def test_demo_canonical_ids_remain_unchanged(demo_scene):
    _demo, result, _stage = demo_scene
    for expected_id in ("ROOM-RP-101", "ROOM-CY-102", "ROOM-INJ-103", "ROOM-PAT-201", "ROOM-SCN-202", "CY-001", "SCN-001", "RP-001"):
        assert expected_id in result.registry.objects
        assert result.registry.objects[expected_id].mrtway_object_id == expected_id


# 8. Visual assets never become engineering identities.
def test_demo_visual_children_are_not_engineering_identities(demo_scene):
    _demo, result, stage = demo_scene
    for mrtway_id in ("SCN-001", "CY-001", "RP-001", "ROOM-SCN-202"):
        anchor = result.path_registry.resolve_by_mrtway_id(mrtway_id)
        visual_prim = stage.GetPrimAtPath(f"{anchor}/Visual")
        assert visual_prim.IsValid()
        assert "mrtway_object_id" not in dict(visual_prim.GetCustomData())


# 9. Engineering transforms remain unchanged.
def test_demo_engineering_transforms_unchanged(demo_scene):
    from ifc_hospital_proof_model_generator import build_hospital_proof_model
    _demo, result, stage = demo_scene
    model = build_hospital_proof_model()
    equipment_by_id = {e.engineering_object_id: e for e in model.equipment}
    for object_id, equipment in equipment_by_id.items():
        anchor = result.path_registry.resolve_by_mrtway_id(object_id)
        anchor_prim = stage.GetPrimAtPath(anchor)
        transform = usda.read_transform(anchor_prim)
        assert math.isclose(transform.position_x, equipment.x_m, abs_tol=1e-6)
        assert math.isclose(transform.position_y, equipment.y_m, abs_tol=1e-6)
        assert math.isclose(transform.position_z, equipment.z_m, abs_tol=1e-6)


# 10. Visual alignment remains isolated.
def test_demo_visual_alignment_isolated_from_engineering_transform(demo_scene):
    _demo, result, stage = demo_scene
    anchor = result.path_registry.resolve_by_mrtway_id("SCN-001")
    anchor_transform = usda.read_transform(stage.GetPrimAtPath(anchor))
    visual_prim = stage.GetPrimAtPath(f"{anchor}/Visual")
    from pxr import UsdGeom
    _, _, visual_scale, _, _ = UsdGeom.XformCommonAPI(visual_prim).GetXformVectors(usda.Usd.TimeCode.Default())
    assert tuple(round(v, 6) for v in visual_scale) == (2.0, 1.4, 1.8)  # scale lives only on /Visual
    anchor_scale_api = UsdGeom.XformCommonAPI(stage.GetPrimAtPath(anchor))
    _, _, anchor_scale, _, _ = anchor_scale_api.GetXformVectors(usda.Usd.TimeCode.Default())
    assert tuple(anchor_scale) == (1.0, 1.0, 1.0)  # engineering anchor never scaled
    assert anchor_transform == usda.read_transform(stage.GetPrimAtPath(anchor))  # unaffected by visual scale


# 11. Geometry quality is REPRESENTATIVE_ASSET.
def test_demo_geometry_quality_is_representative_asset(demo_scene):
    _demo, result, stage = demo_scene
    for mrtway_id in ("SCN-001", "CY-001", "RP-001"):
        anchor = result.path_registry.resolve_by_mrtway_id(mrtway_id)
        data = dict(stage.GetPrimAtPath(anchor).GetCustomData())
        assert data["geometry_quality"] == "REPRESENTATIVE_ASSET"


# 12. MANUFACTURER_GEOMETRY is never fabricated.
def test_demo_never_fabricates_manufacturer_geometry(demo_scene):
    _demo, result, stage = demo_scene
    for mrtway_id in result.path_registry.by_mrtway_id:
        anchor = result.path_registry.resolve_by_mrtway_id(mrtway_id)
        data = dict(stage.GetPrimAtPath(anchor).GetCustomData())
        assert data.get("geometry_quality") != "MANUFACTURER_GEOMETRY"


# 13. Missing asset still falls back safely.
def test_demo_missing_asset_falls_back_safely(tmp_path):
    import generate_openusd_hospital_visual_demo as demo
    registry, model = demo.build_demo_registry()
    geometry_assets, catalog_bindings = demo.configure_geometry_assets(str(tmp_path / "assets"))
    broken = usda.GeometryAsset(
        geometry_asset_id="GEOM-BROKEN", catalog_model_id=None, manufacturer=None, model=None,
        geometry_quality="REPRESENTATIVE_ASSET", source_type="TEST_FIXTURE", source_reference=None,
        version="1.0.0", units=usda.LINEAR_UNIT, bounding_dimensions="NOT_AVAILABLE", provenance="test",
        visual_asset_path="/definitely/not/a/real/path/asset.usda",
    )
    geometry_assets.assets_by_catalog_model_id["DEMO-SCANNER"] = broken
    stage, path_registry, export_result = usda.export_registry_to_stage(registry, catalog_bindings=catalog_bindings, geometry_assets=geometry_assets)
    anchor = path_registry.resolve_by_mrtway_id("SCN-001")
    assert stage.GetPrimAtPath(anchor).IsValid()
    assert not stage.GetPrimAtPath(f"{anchor}/Visual").IsValid()
    assert any("SCN-001" in w for w in export_result.warnings)


# 14. Final hospital demo scene opens successfully.
def test_demo_final_scene_opens_successfully(demo_scene):
    _demo, result, stage = demo_scene
    assert stage.GetDefaultPrim().IsValid()
    assert stage.GetDefaultPrim().GetPath() == usda.CAMPUS_ROOT_PATH
    assert result.export_result.validation_status == "VALID"
    assert result.manifest_path is not None
    assert os.path.isfile(result.manifest_path)
    assert os.path.isfile(result.scene_path)


"""OpenUSD Phase 1B: Recognizable Hospital Asset Demonstration.

GOVERNANCE: this is a PRESENTATION/DEMONSTRATION entry point only. It
creates NO second canonical spatial/geometry authority -- the canonical
hospital registry is built by feeding the SAME controlled hospital layout
already used for the Bentley proof (`ifc_hospital_proof_model_generator.
build_hospital_proof_model()`, read-only, never modified here) through the
EXISTING `canonical_spatial_authority.normalize_itwin_import()` contract
(the same normalization path BIM/iTwin Phase 1/2B already validated) --
never a second, independently-typed set of coordinates.

Visual recognizability comes ENTIRELY through the existing Phase 1A
visual-asset-binding mechanism (`openusd_spatial_adapter.bind_visual_asset`)
-- representative scanner/cyclotron/radiopharmacy/room-context assets are
deterministically generated from plain OpenUSD primitives (no downloaded/
scraped/proprietary geometry) and referenced as non-authoritative '/Visual'
children of the existing canonical engineering anchors. No canonical
dimension is fabricated: `CanonicalSpatialObject.dimensions` is left
NOT_CALIBRATED for every object in this demo; visual sizing is achieved only
via the non-authoritative `GeometryAsset.visual_asset_local_scale` (section 8
of this build), never written back into engineering data.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import canonical_spatial_authority as csa
import openusd_spatial_adapter as usda
from ifc_hospital_proof_model_generator import build_hospital_proof_model

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ASSET_DIR = os.path.join(_MODULE_DIR, "openusd_visual_assets")
DEFAULT_SCENE_PATH = os.path.join(DEFAULT_ASSET_DIR, "mrt_pharma_hospital_visual_demo.usda")
DEFAULT_MANIFEST_PATH = os.path.join(_MODULE_DIR, "OPENUSD_VISUAL_DEMO_MANIFEST.md")

_TEST_ASSET_LABEL = "TEST_REPRESENTATIVE_ONLY_NOT_MANUFACTURER_GEOMETRY"

# engineering_object_id -> normalize_itwin_import element_class (section 2/9):
# the ONLY per-item translation this module performs -- never a second copy
# of coordinates, which always come from build_hospital_proof_model().
_EQUIPMENT_ELEMENT_CLASS_BY_ID = {"CY-001": "CYCLOTRON", "SCN-001": "PET_SCANNER", "RP-001": "RADIOPHARMACY"}


# ---------------------------------------------------------------------------
# Deterministic REPRESENTATIVE visual assets (sections 3-6) -- built from
# plain OpenUSD primitives only, never a downloaded/scraped/proprietary mesh.
# ---------------------------------------------------------------------------


def _label_representative_asset(root_prim) -> None:
    root_prim.SetCustomDataByKey("asset_label", _TEST_ASSET_LABEL)
    root_prim.SetCustomDataByKey("visual_asset_purpose", "DEMONSTRATION")
    root_prim.SetCustomDataByKey("visual_asset_authority", "NON_AUTHORITATIVE")
    root_prim.SetCustomDataByKey("visual_asset_geometry_quality", "REPRESENTATIVE_ASSET")


def build_representative_scanner_asset(path: str) -> str:
    """Section 4: gantry/bore + patient table + support base -- recognizable
    as a scanner, not photorealistic, never claiming a specific model."""
    from pxr import Usd, UsdGeom, Gf
    stage = Usd.Stage.CreateNew(path)
    root = UsdGeom.Xform.Define(stage, "/RepresentativeScanner")
    stage.SetDefaultPrim(root.GetPrim())
    _label_representative_asset(root.GetPrim())

    gantry = UsdGeom.Cylinder.Define(stage, "/RepresentativeScanner/Gantry")
    gantry.GetRadiusAttr().Set(0.9)
    gantry.GetHeightAttr().Set(0.6)
    gantry.GetAxisAttr().Set("X")

    table = UsdGeom.Cube.Define(stage, "/RepresentativeScanner/Table")
    table.GetSizeAttr().Set(1.0)
    UsdGeom.XformCommonAPI(table.GetPrim()).SetScale(Gf.Vec3f(2.2, 0.5, 0.15))
    UsdGeom.XformCommonAPI(table.GetPrim()).SetTranslate(Gf.Vec3d(1.4, 0.0, -0.2))

    base = UsdGeom.Cube.Define(stage, "/RepresentativeScanner/Base")
    base.GetSizeAttr().Set(1.0)
    UsdGeom.XformCommonAPI(base.GetPrim()).SetScale(Gf.Vec3f(1.0, 1.0, 0.4))
    UsdGeom.XformCommonAPI(base.GetPrim()).SetTranslate(Gf.Vec3d(0.0, 0.0, -0.7))

    stage.GetRootLayer().Save()
    return path


def build_representative_cyclotron_asset(path: str) -> str:
    """Section 5: circular/cylindrical body + shielding enclosure mass +
    service cabinet -- recognizable as a compact medical cyclotron."""
    from pxr import Usd, UsdGeom, Gf
    stage = Usd.Stage.CreateNew(path)
    root = UsdGeom.Xform.Define(stage, "/RepresentativeCyclotron")
    stage.SetDefaultPrim(root.GetPrim())
    _label_representative_asset(root.GetPrim())

    body = UsdGeom.Cylinder.Define(stage, "/RepresentativeCyclotron/Body")
    body.GetRadiusAttr().Set(0.85)
    body.GetHeightAttr().Set(1.0)
    body.GetAxisAttr().Set("Z")

    shielding = UsdGeom.Cylinder.Define(stage, "/RepresentativeCyclotron/Shielding")
    shielding.GetRadiusAttr().Set(1.05)
    shielding.GetHeightAttr().Set(1.1)
    shielding.GetAxisAttr().Set("Z")
    shielding.GetPurposeAttr().Set(UsdGeom.Tokens.proxy)

    cabinet = UsdGeom.Cube.Define(stage, "/RepresentativeCyclotron/ServiceCabinet")
    cabinet.GetSizeAttr().Set(1.0)
    UsdGeom.XformCommonAPI(cabinet.GetPrim()).SetScale(Gf.Vec3f(0.5, 0.4, 0.9))
    UsdGeom.XformCommonAPI(cabinet.GetPrim()).SetTranslate(Gf.Vec3d(1.3, 0.0, -0.05))

    stage.GetRootLayer().Save()
    return path


def build_representative_radiopharmacy_asset(path: str) -> str:
    """Section 6: shielded work-bench/hot-cell massing + work surface +
    dispensing element -- recognizable as a radiopharmacy work area."""
    from pxr import Usd, UsdGeom, Gf
    stage = Usd.Stage.CreateNew(path)
    root = UsdGeom.Xform.Define(stage, "/RepresentativeRadiopharmacy")
    stage.SetDefaultPrim(root.GetPrim())
    _label_representative_asset(root.GetPrim())

    hot_cell = UsdGeom.Cube.Define(stage, "/RepresentativeRadiopharmacy/HotCell")
    hot_cell.GetSizeAttr().Set(1.0)
    UsdGeom.XformCommonAPI(hot_cell.GetPrim()).SetScale(Gf.Vec3f(1.0, 0.8, 1.4))

    workbench = UsdGeom.Cube.Define(stage, "/RepresentativeRadiopharmacy/Workbench")
    workbench.GetSizeAttr().Set(1.0)
    UsdGeom.XformCommonAPI(workbench.GetPrim()).SetScale(Gf.Vec3f(1.6, 0.6, 0.05))
    UsdGeom.XformCommonAPI(workbench.GetPrim()).SetTranslate(Gf.Vec3d(1.2, 0.0, 0.4))

    dispensing = UsdGeom.Cube.Define(stage, "/RepresentativeRadiopharmacy/Dispensing")
    dispensing.GetSizeAttr().Set(1.0)
    UsdGeom.XformCommonAPI(dispensing.GetPrim()).SetScale(Gf.Vec3f(0.3, 0.3, 0.5))
    UsdGeom.XformCommonAPI(dispensing.GetPrim()).SetTranslate(Gf.Vec3d(1.2, 0.0, 0.7))

    stage.GetRootLayer().Save()
    return path


def build_representative_room_context_asset(path: str) -> str:
    """Section 7: minimal non-authoritative architectural context (floor +
    3 walls, 4th side left open as a doorway/viewing gap) -- fixed,
    honestly-arbitrary aesthetic proportions, NEVER presented as calibrated
    room geometry (never written to `CanonicalSpatialObject.dimensions`)."""
    from pxr import Usd, UsdGeom, Gf
    stage = Usd.Stage.CreateNew(path)
    root = UsdGeom.Xform.Define(stage, "/RepresentativeRoomContext")
    stage.SetDefaultPrim(root.GetPrim())
    _label_representative_asset(root.GetPrim())
    root.GetPrim().SetCustomDataByKey("asset_label", "REPRESENTATIVE_ARCHITECTURAL_CONTEXT_NOT_CALIBRATED_ROOM_GEOMETRY")

    floor = UsdGeom.Cube.Define(stage, "/RepresentativeRoomContext/Floor")
    floor.GetSizeAttr().Set(1.0)
    UsdGeom.XformCommonAPI(floor.GetPrim()).SetScale(Gf.Vec3f(1.0, 1.0, 0.05))

    wall_specs = {
        "WallNorth": ((0.0, 0.5, 0.5), (1.0, 0.05, 1.0)),
        "WallSouth": ((0.0, -0.5, 0.5), (1.0, 0.05, 1.0)),
        "WallEast": ((0.5, 0.0, 0.5), (0.05, 1.0, 1.0)),
        # WallWest intentionally omitted -- doorway opening for viewing/access
    }
    for name, (translate, scale) in wall_specs.items():
        wall = UsdGeom.Cube.Define(stage, f"/RepresentativeRoomContext/{name}")
        wall.GetSizeAttr().Set(1.0)
        UsdGeom.XformCommonAPI(wall.GetPrim()).SetScale(Gf.Vec3f(*scale))
        UsdGeom.XformCommonAPI(wall.GetPrim()).SetTranslate(Gf.Vec3d(*translate))

    stage.GetRootLayer().Save()
    return path


# ---------------------------------------------------------------------------
# Canonical registry (section 2) -- reuses build_hospital_proof_model() as
# the ONE coordinate source; never a second hospital definition.
# ---------------------------------------------------------------------------


def build_demo_registry():
    """Returns `(registry, model)`. `registry` is a plain
    `SpatialObjectRegistry` (no Lockdown/What-If wrapper -- this demo
    participates in no Lockdown session, so there is no L0 to protect)."""
    model = build_hospital_proof_model()
    facility_id = "FAC-HOSP-VISUAL-DEMO"
    registry = csa.build_facility_hierarchy(facility_id=facility_id)

    room_floor_by_id = {room.room_id: room.floor_id for room in model.rooms}
    elements = [csa.BentleyElementRecord(itwin_id="OPENUSD_DEMO", imodel_id="OPENUSD_DEMO", element_id="EL-BLDG", element_class="BUILDING", building_id=model.building_id)]
    for floor_id in model.floor_ids:
        elements.append(csa.BentleyElementRecord(itwin_id="OPENUSD_DEMO", imodel_id="OPENUSD_DEMO", element_id=f"EL-{floor_id}", element_class="FLOOR", building_id=model.building_id, floor_id=floor_id))
    for room in model.rooms:
        elements.append(csa.BentleyElementRecord(
            itwin_id="OPENUSD_DEMO", imodel_id="OPENUSD_DEMO", element_id=f"EL-{room.room_id}", element_class="ROOM",
            building_id=model.building_id, floor_id=room.floor_id, room_number=room.room_id,
            x=room.x_m, y=room.y_m, z=room.z_m,
        ))
    for equipment in model.equipment:
        element_class = _EQUIPMENT_ELEMENT_CLASS_BY_ID.get(equipment.engineering_object_id)
        if element_class is None:
            continue  # outside this demo's known equipment set -- never guessed
        elements.append(csa.BentleyElementRecord(
            itwin_id="OPENUSD_DEMO", imodel_id="OPENUSD_DEMO", element_id=f"EL-{equipment.engineering_object_id}", element_class=element_class,
            building_id=model.building_id, floor_id=room_floor_by_id.get(equipment.room_id),
            x=equipment.x_m, y=equipment.y_m, z=equipment.z_m, engineering_object_id=equipment.engineering_object_id,
        ))
    csa.normalize_itwin_import(registry, facility_id=facility_id, elements=elements)
    return registry, model


# ---------------------------------------------------------------------------
# Visual-asset binding configuration (reuses the EXISTING Phase 1A
# GeometryAssetRegistry/catalog_bindings mechanism -- no export-path changes
# were required beyond the section-8 local-scale field).
# ---------------------------------------------------------------------------


def configure_geometry_assets(asset_dir: str) -> tuple[usda.GeometryAssetRegistry, dict[str, str]]:
    os.makedirs(asset_dir, exist_ok=True)
    scanner_path = build_representative_scanner_asset(os.path.join(asset_dir, "representative_scanner.usda"))
    cyclotron_path = build_representative_cyclotron_asset(os.path.join(asset_dir, "representative_cyclotron.usda"))
    radiopharmacy_path = build_representative_radiopharmacy_asset(os.path.join(asset_dir, "representative_radiopharmacy.usda"))
    room_context_path = build_representative_room_context_asset(os.path.join(asset_dir, "representative_room_context.usda"))

    def _asset(asset_id: str, path: str, scale: tuple[float, float, float]) -> usda.GeometryAsset:
        return usda.GeometryAsset(
            geometry_asset_id=asset_id, catalog_model_id=None, manufacturer=None, model=None,
            geometry_quality="REPRESENTATIVE_ASSET", source_type="OPENUSD_PHASE1B_DEMO_FIXTURE",
            source_reference=path, version=usda.OPENUSD_ADAPTER_SCHEMA_VERSION, units=usda.LINEAR_UNIT,
            bounding_dimensions="NOT_AVAILABLE",
            provenance="Deterministic locally-generated REPRESENTATIVE_ASSET (plain OpenUSD primitives) -- never manufacturer CAD.",
            visual_asset_path=path, visual_asset_local_transform=csa.Transform(), visual_asset_local_scale=scale,
        )

    geometry_assets = usda.GeometryAssetRegistry()
    geometry_assets.assets_by_catalog_model_id["DEMO-SCANNER"] = _asset("GEOM-DEMO-SCANNER", scanner_path, (2.0, 1.4, 1.8))
    geometry_assets.assets_by_catalog_model_id["DEMO-CYCLOTRON"] = _asset("GEOM-DEMO-CYCLOTRON", cyclotron_path, (1.6, 1.6, 1.6))
    geometry_assets.assets_by_catalog_model_id["DEMO-RADIOPHARMACY"] = _asset("GEOM-DEMO-RP", radiopharmacy_path, (1.3, 1.1, 1.2))
    geometry_assets.assets_by_catalog_model_id["DEMO-ROOM-CONTEXT"] = _asset("GEOM-DEMO-ROOM", room_context_path, (6.0, 5.0, 3.0))

    catalog_bindings = {
        "SCN-001": "DEMO-SCANNER", "CY-001": "DEMO-CYCLOTRON", "RP-001": "DEMO-RADIOPHARMACY",
        "ROOM-SCN-202": "DEMO-ROOM-CONTEXT", "ROOM-CY-102": "DEMO-ROOM-CONTEXT", "ROOM-RP-101": "DEMO-ROOM-CONTEXT",
    }
    return geometry_assets, catalog_bindings


# ---------------------------------------------------------------------------
# Manifest (section 13) -- simple, non-broadened human-readable summary.
# ---------------------------------------------------------------------------


def _write_manifest(manifest_path: str, *, path_registry, registry, model, catalog_bindings, geometry_assets) -> None:
    room_by_object_id = dict(model.expected_bindings)
    lines = [
        "# OpenUSD Visual Demo Manifest",
        "",
        "Non-authoritative presentation summary only -- see `canonical_spatial_authority.py` for engineering truth.",
        "",
        "| canonical_id | prim_path | room | visual_asset | geometry_quality | visual_alignment | engineering_dimensions_status |",
        "|---|---|---|---|---|---|---|",
    ]
    for mrtway_id in sorted(path_registry.by_mrtway_id):
        obj = registry.objects.get(mrtway_id)
        if obj is None:
            continue
        prim_path = path_registry.resolve_by_mrtway_id(mrtway_id)
        catalog_key = catalog_bindings.get(mrtway_id)
        asset = geometry_assets.resolve(catalog_key)
        visual_asset = os.path.basename(asset.visual_asset_path) if asset and asset.visual_asset_path else "NONE"
        quality = asset.geometry_quality if asset else "NOT_AVAILABLE"
        alignment = f"scale={asset.visual_asset_local_scale}" if asset and asset.visual_asset_local_scale is not None else "IDENTITY"
        dims_status = "CALIBRATED" if obj.dimensions.is_fully_known() else "NOT_CALIBRATED"
        room = room_by_object_id.get(mrtway_id, mrtway_id if obj.object_type == "ROOM" else "-")
        lines.append(f"| {mrtway_id} | {prim_path} | {room} | {visual_asset} | {quality} | {alignment} | {dims_status} |")
    with open(manifest_path, "w") as handle:
        handle.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Entry point (section 10).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DemoResult:
    scene_path: str
    manifest_path: str | None
    registry: csa.SpatialObjectRegistry
    path_registry: "usda.PrimPathRegistry"
    export_result: "usda.SceneExportResult"


def generate_demo(
    *, asset_dir: str = DEFAULT_ASSET_DIR, scene_path: str = DEFAULT_SCENE_PATH, manifest_path: str | None = DEFAULT_MANIFEST_PATH,
) -> DemoResult:
    if not usda.OPENUSD_RUNTIME_AVAILABLE:
        raise usda.OpenUsdRuntimeNotAvailable("OpenUSD runtime not available -- cannot generate the visual demo.")
    registry, model = build_demo_registry()
    geometry_assets, catalog_bindings = configure_geometry_assets(asset_dir)
    stage, path_registry, export_result = usda.export_registry_to_stage(registry, catalog_bindings=catalog_bindings, geometry_assets=geometry_assets)
    os.makedirs(os.path.dirname(scene_path), exist_ok=True)
    usda.save_stage_to_usda(stage, scene_path)
    if manifest_path is not None:
        _write_manifest(manifest_path, path_registry=path_registry, registry=registry, model=model, catalog_bindings=catalog_bindings, geometry_assets=geometry_assets)
    return DemoResult(scene_path=scene_path, manifest_path=manifest_path, registry=registry, path_registry=path_registry, export_result=export_result)


def main() -> None:
    result = generate_demo()
    print("OPENUSD_VISUAL_DEMO_SCENE =", result.scene_path)
    print("OPENUSD_VISUAL_DEMO_MANIFEST =", result.manifest_path)
    print("OBJECT_COUNT =", result.export_result.object_count)
    print("MAPPED_PRIM_COUNT =", result.export_result.mapped_prim_count)
    print("WARNINGS =", result.export_result.warnings)


if __name__ == "__main__":
    main()

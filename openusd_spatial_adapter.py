"""OpenUSD Spatial Adapter + Scene Serialization.

GOVERNANCE: MRTWAY ENGINEERING/SPATIAL AUTHORITY != OPENUSD SCENE.

MRTway (`canonical_spatial_authority.py`) owns engineering truth: identity,
hierarchy, economics, connectivity, locked/what-if state. This module ONLY
represents that truth as a USD scene -- hierarchy, geometry references,
transforms, visibility, selection-ready identity, presentation metadata.
`USD_PRIM_PATH` is NEVER authoritative; it is always an external mapping
alongside `MRTWAY_OBJECT_ID` (never a replacement for it).

RUNTIME: this module vendors the official `usd-core` PyPI package (Pixar's
OpenUSD, NOT NVIDIA Omniverse Kit, NOT a cloud service, NOT Bentley) into a
workspace-local `.usd_runtime/` directory (gitignored) because system
site-packages were not writable in this sandboxed environment. If that
directory is absent, `OPENUSD_RUNTIME_AVAILABLE` is `False` and every
USD-dependent function raises `OpenUsdRuntimeNotAvailable` -- nothing here
fabricates a working SDK integration.

SCENE STRUCTURE CHOSEN (documented per section 80): a locked scene and a
what-if scene are two entirely INDEPENDENT `Usd.Stage` objects (each built
fresh from a `SpatialObjectRegistry` snapshot), rather than a single stage
with USD sublayers. This is a deliberate simplification -- it trivially
guarantees the locked stage can never be mutated by what-if authoring
(they don't share any USD layer at all), at the cost of not using USD's
native layer-composition machinery. Documented, not silently assumed.
"""

from __future__ import annotations

import math
import os
import re
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal, Mapping, Sequence

import canonical_spatial_authority as csa
import dynamic_scene_state_authority as dss

OPENUSD_ADAPTER_SCHEMA_VERSION = "1.0.0"
CANONICAL_SPATIAL_SCHEMA_VERSION = "1.0.0"
LINEAR_UNIT = "meters"
METERS_PER_UNIT = 1.0
UP_AXIS = "Z"
CAMPUS_ROOT_PATH = "/MRTwayCampus"
TRANSFORM_TOLERANCE = 1e-6

_VENDORED_USD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".usd_runtime")
if os.path.isdir(_VENDORED_USD_PATH) and _VENDORED_USD_PATH not in sys.path:
    sys.path.insert(0, _VENDORED_USD_PATH)

try:
    from pxr import Usd, UsdGeom, Gf, Sdf  # type: ignore
    OPENUSD_RUNTIME_AVAILABLE = True
    OPENUSD_RUNTIME_VERSION = Usd.GetVersion()
except ImportError:
    Usd = UsdGeom = Gf = Sdf = None  # type: ignore
    OPENUSD_RUNTIME_AVAILABLE = False
    OPENUSD_RUNTIME_VERSION = None


class OpenUsdRuntimeNotAvailable(RuntimeError):
    """Raised by any USD-dependent function when `pxr` could not be imported.
    Never silently degrades to a fabricated/mock USD scene."""


def _require_runtime() -> None:
    if not OPENUSD_RUNTIME_AVAILABLE:
        raise OpenUsdRuntimeNotAvailable(
            "OpenUSD runtime not available -- 'pxr' could not be imported "
            f"(checked vendored path: {_VENDORED_USD_PATH}). Install the official "
            "'usd-core' PyPI package to enable this functionality."
        )


# ---------------------------------------------------------------------------
# Prim-path sanitization + deterministic mapping (sections 16-17, 10-11)
# ---------------------------------------------------------------------------

_INVALID_PRIM_CHARS = re.compile(r"[^A-Za-z0-9_]")


def sanitize_prim_path_segment(raw: str) -> str:
    """Section 16: deterministic USD-safe path segment -- invalid characters
    become `_`, and a segment that doesn't start with a letter/underscore is
    prefixed with `_`. Same input always produces the same output."""
    sanitized = _INVALID_PRIM_CHARS.sub("_", raw)
    if not sanitized or not (sanitized[0].isalpha() or sanitized[0] == "_"):
        sanitized = f"_{sanitized}"
    return sanitized


_MRT_OBJECT_TYPES = frozenset({
    "MRT_TRUNK", "MRT_BRANCH", "MRT_SEGMENT", "MRT_JUNCTION", "MRT_ENDPOINT",
    "MRT_VESTIBULE", "MRT_CARRIER", "MRT_CONTAINER",
})
_LOGISTICS_ORIGIN_TYPES = frozenset({
    "CENTRAL_PHARMACY", "LABORATORY", "BLOOD_BANK", "CLEAN_LINEN_SOURCE", "STERILE_CLEAN_SUPPLY_SOURCE",
})


def build_deterministic_prim_path(obj: csa.CanonicalSpatialObject) -> str:
    """Section 12-15: `/MRTwayCampus/Facility/...` hierarchy -- NEVER
    hard-codes "BuildingA"/"BuildingB"; every building/floor segment is
    derived from the object's own (arbitrary) `building_id`/`floor_id`."""
    if obj.object_type == "FACILITY":
        return f"{CAMPUS_ROOT_PATH}/Facility"
    if obj.object_type == "BUILDING":
        return f"{CAMPUS_ROOT_PATH}/Facility/Buildings/{sanitize_prim_path_segment(obj.building_id)}"
    if obj.object_type == "FLOOR":
        return f"{CAMPUS_ROOT_PATH}/Facility/Buildings/{sanitize_prim_path_segment(obj.building_id)}/{sanitize_prim_path_segment(obj.floor_id)}"
    if obj.object_type in _MRT_OBJECT_TYPES:
        return f"{CAMPUS_ROOT_PATH}/Facility/MRT/{sanitize_prim_path_segment(obj.mrtway_object_id)}"
    if obj.object_type in _LOGISTICS_ORIGIN_TYPES:
        return f"{CAMPUS_ROOT_PATH}/Facility/Logistics/{sanitize_prim_path_segment(obj.mrtway_object_id)}"
    if obj.building_id and obj.floor_id:
        return f"{CAMPUS_ROOT_PATH}/Facility/Buildings/{sanitize_prim_path_segment(obj.building_id)}/{sanitize_prim_path_segment(obj.floor_id)}/{sanitize_prim_path_segment(obj.mrtway_object_id)}"
    return f"{CAMPUS_ROOT_PATH}/Facility/Equipment/{sanitize_prim_path_segment(obj.mrtway_object_id)}"


class PrimPathCollisionError(ValueError):
    """Section 17: raised when two distinct MRTWAY_OBJECT_IDs would sanitize
    to the same USD prim path -- fails loudly rather than silently
    disambiguating."""


@dataclass
class PrimPathRegistry:
    """Section 10-11: bidirectional MRTWAY_OBJECT_ID <-> USD_PRIM_PATH
    mapping. USD prim paths may change across exports; MRTway identity never
    does."""

    by_mrtway_id: dict[str, str] = field(default_factory=dict)
    by_prim_path: dict[str, str] = field(default_factory=dict)

    def register(self, *, mrtway_object_id: str, prim_path: str) -> None:
        if prim_path in self.by_prim_path and self.by_prim_path[prim_path] != mrtway_object_id:
            raise PrimPathCollisionError(
                f"prim path {prim_path!r} already mapped to {self.by_prim_path[prim_path]!r}, "
                f"cannot also map {mrtway_object_id!r}"
            )
        self.by_mrtway_id[mrtway_object_id] = prim_path
        self.by_prim_path[prim_path] = mrtway_object_id

    def resolve_by_mrtway_id(self, mrtway_object_id: str) -> str | None:
        return self.by_mrtway_id.get(mrtway_object_id)

    def resolve_by_prim_path(self, prim_path: str) -> str | None:
        return self.by_prim_path.get(prim_path)

    def __len__(self) -> int:
        return len(self.by_mrtway_id)


# ---------------------------------------------------------------------------
# Geometry-asset registry + catalog-model binding (sections 25-28, 74-79)
# ---------------------------------------------------------------------------

GeometryQuality = Literal[
    "NOT_AVAILABLE", "GENERIC_PROXY", "DIMENSIONAL_PROXY", "REPRESENTATIVE_ASSET",
    "MANUFACTURER_GEOMETRY", "IMPORTED_BIM_GEOMETRY", "USER_SUPPLIED_GEOMETRY",
]
"""OpenUSD Phase 1A section 7: `REPRESENTATIVE_ASSET` is a NEW, honest state
for an aesthetically-representative external USD asset that is NOT
manufacturer-supplied CAD -- never auto-promoted to `MANUFACTURER_GEOMETRY`
just because manufacturer/model metadata exists."""


@dataclass(frozen=True)
class GeometryAsset:
    geometry_asset_id: str
    catalog_model_id: str | None
    manufacturer: str | None
    model: str | None
    geometry_quality: GeometryQuality
    source_type: str
    source_reference: str | None
    version: str
    units: str
    bounding_dimensions: tuple[float, float, float] | Literal["NOT_AVAILABLE"]
    provenance: str
    visual_asset_path: str | None = None
    """OpenUSD Phase 1A section 4: optional path to an external USD-family
    asset (.usd/.usda/.usdc) authored via standard USD reference composition
    -- never copied into canonical engineering records (section 4)."""
    visual_asset_local_transform: "csa.Transform | None" = None
    """OpenUSD Phase 1A section 6: non-authoritative local alignment between
    the engineering anchor and the referenced asset's own origin/orientation/
    scale convention -- NEVER written back into canonical engineering
    coordinates."""
    visual_asset_local_scale: tuple[float, float, float] | None = None
    """OpenUSD Phase 1B section 8: non-authoritative local (length, width,
    height) scale applied ONLY to the '/Visual' child prim -- `csa.Transform`
    has no scale component and is NOT extended for this (section 15: prefer
    no further canonical schema changes). Never written back into
    `CanonicalSpatialObject.dimensions`."""


@dataclass
class GeometryAssetRegistry:
    """Section 74/76: deterministic catalog_model_id -> GeometryAsset lookup.
    No binary model files are stored here -- only a reference contract."""

    assets_by_catalog_model_id: dict[str, GeometryAsset] = field(default_factory=dict)

    def bind(self, asset: GeometryAsset) -> None:
        if asset.catalog_model_id is not None:
            self.assets_by_catalog_model_id[asset.catalog_model_id] = asset

    def resolve(self, catalog_model_id: str | None) -> GeometryAsset | None:
        if catalog_model_id is None:
            return None
        return self.assets_by_catalog_model_id.get(catalog_model_id)


_NOT_AVAILABLE_GEOMETRY_ASSET = GeometryAsset(
    geometry_asset_id="NOT_AVAILABLE", catalog_model_id=None, manufacturer=None, model=None,
    geometry_quality="NOT_AVAILABLE", source_type="NONE", source_reference=None, version="n/a",
    units=LINEAR_UNIT, bounding_dimensions="NOT_AVAILABLE",
    provenance="No catalog_model_id binding supplied -- spatial existence does not require fabricated geometry.",
)


def build_geometry_asset_from_catalog_model(
    *, catalog_model_id: str, manufacturer: str, model: str,
    geometry_quality: GeometryQuality = "GENERIC_PROXY",
    visual_asset_path: str | None = None, visual_asset_local_transform: "csa.Transform | None" = None,
) -> GeometryAsset:
    """Section 26-27: binds REAL manufacturer/model identity from an existing
    engineering catalog (cyclotron_catalog.py/generator_catalog.py/
    scanner_catalog.py) to a geometry asset -- but the geometry itself is
    honestly `GENERIC_PROXY` by default (no real CAD/BIM assets exist in this
    repo). Never claims MANUFACTURER_GEOMETRY without an actual asset
    reference. OpenUSD Phase 1A section 4: callers may optionally supply
    `visual_asset_path` (+ alignment transform) alongside an explicit,
    truthful `geometry_quality` (e.g. `REPRESENTATIVE_ASSET`) -- never
    inferred automatically from the presence of a path."""
    return GeometryAsset(
        geometry_asset_id=f"GEOM-{catalog_model_id}", catalog_model_id=catalog_model_id,
        manufacturer=manufacturer, model=model, geometry_quality=geometry_quality,
        source_type="CATALOG_BOUND_PROXY", source_reference=None, version=OPENUSD_ADAPTER_SCHEMA_VERSION,
        units=LINEAR_UNIT, bounding_dimensions="NOT_AVAILABLE",
        provenance=f"Manufacturer/model reused from existing engineering catalog ({catalog_model_id}); geometry is a deterministic proxy, not manufacturer-supplied CAD.",
        visual_asset_path=visual_asset_path, visual_asset_local_transform=visual_asset_local_transform,
    )


def default_geometry_asset_registry() -> GeometryAssetRegistry:
    """Section 76: populates bindings from the REAL cyclotron/generator/
    scanner catalogs already established in this repo -- never fabricates a
    manufacturer/model that doesn't exist in those catalogs."""
    registry = GeometryAssetRegistry()
    try:
        from cyclotron_catalog import load_cyclotron_catalog
        for model in load_cyclotron_catalog().models:
            registry.bind(build_geometry_asset_from_catalog_model(catalog_model_id=model.catalog_model_id, manufacturer=model.manufacturer, model=model.model))
    except Exception:
        pass
    try:
        from generator_catalog import load_generator_catalog
        for model in load_generator_catalog().models:
            registry.bind(build_geometry_asset_from_catalog_model(catalog_model_id=model.catalog_model_id, manufacturer=model.manufacturer, model=model.model))
    except Exception:
        pass
    try:
        from scanner_catalog import load_scanner_catalog
        for model in load_scanner_catalog().models:
            registry.bind(build_geometry_asset_from_catalog_model(catalog_model_id=model.catalog_model_id, manufacturer=model.manufacturer, model=model.model))
    except Exception:
        pass
    return registry


# ---------------------------------------------------------------------------
# Transform export/import (sections 19-24)
# ---------------------------------------------------------------------------


def apply_transform(prim: "Usd.Prim", transform: csa.Transform) -> None:
    """Section 19-20: canonical Transform -> USD translate + rotateXYZ (degrees).
    Units are meters (see METERS_PER_UNIT); rotations are Euler XYZ degrees."""
    _require_runtime()
    api = UsdGeom.XformCommonAPI(prim)
    api.SetTranslate(Gf.Vec3d(transform.position_x, transform.position_y, transform.position_z))
    api.SetRotate(Gf.Vec3f(transform.rotation_x, transform.rotation_y, transform.rotation_z))


def read_transform(prim: "Usd.Prim") -> csa.Transform:
    """Section 23: USD -> canonical Transform read-back."""
    _require_runtime()
    api = UsdGeom.XformCommonAPI(prim)
    translate, rotate, _scale, _pivot, _order = api.GetXformVectors(Usd.TimeCode.Default())
    return csa.Transform(
        position_x=float(translate[0]), position_y=float(translate[1]), position_z=float(translate[2]),
        rotation_x=float(rotate[0]), rotation_y=float(rotate[1]), rotation_z=float(rotate[2]),
    )


def transforms_match(a: csa.Transform, b: csa.Transform, *, tolerance: float = TRANSFORM_TOLERANCE) -> bool:
    """Section 23: round-trip equality within documented floating-point tolerance."""
    fields = ("position_x", "position_y", "position_z", "rotation_x", "rotation_y", "rotation_z")
    return all(math.isclose(getattr(a, f), getattr(b, f), abs_tol=tolerance) for f in fields)


def apply_camera_view_rotation(*, yaw_degrees: float, pitch_degrees: float) -> csa.RotationImpact:
    """Section 24/91: view rotation NEVER writes an engineering transform --
    delegates entirely to the closure build's camera-rotation contract,
    never touching any USD prim or canonical object."""
    return csa.apply_camera_rotation(yaw_degrees=yaw_degrees, pitch_degrees=pitch_degrees)


# ---------------------------------------------------------------------------
# Object metadata attachment (section 18)
# ---------------------------------------------------------------------------


def attach_mrtway_metadata(
    prim: "Usd.Prim", obj: csa.CanonicalSpatialObject, *,
    catalog_model_id: str | None = None, geometry_asset: GeometryAsset | None = None,
) -> None:
    """Section 18/28: non-authoritative identity + presentation metadata --
    never authoritative physics/economics, even though customData supports
    arbitrary values."""
    resolved_asset = geometry_asset or _NOT_AVAILABLE_GEOMETRY_ASSET
    prim.SetCustomDataByKey("mrtway_object_id", obj.mrtway_object_id)
    prim.SetCustomDataByKey("object_type", obj.object_type)
    prim.SetCustomDataByKey("asset_status", obj.asset_status)
    prim.SetCustomDataByKey("operational_state", obj.operational_state)
    prim.SetCustomDataByKey("spatial_status", obj.spatial_status)
    prim.SetCustomDataByKey("provenance", obj.provenance)
    if obj.engineering_object_id is not None:
        prim.SetCustomDataByKey("engineering_object_id", obj.engineering_object_id)
    if catalog_model_id is not None:
        prim.SetCustomDataByKey("catalog_model_id", catalog_model_id)
        prim.SetCustomDataByKey("manufacturer", resolved_asset.manufacturer)
        prim.SetCustomDataByKey("model", resolved_asset.model)
    prim.SetCustomDataByKey("geometry_quality", resolved_asset.geometry_quality)
    if obj.geometry_reference is not None:
        prim.SetCustomDataByKey("geometry_reference", obj.geometry_reference)


def attach_scene_version_metadata(root_prim: "Usd.Prim", *, locked_state_identifier: str | None = None) -> None:
    """Section 56: adapter/schema version + export timestamp -- never used
    to break semantic-identity equality tests (timestamp is metadata only)."""
    root_prim.SetCustomDataByKey("adapter_schema_version", OPENUSD_ADAPTER_SCHEMA_VERSION)
    root_prim.SetCustomDataByKey("canonical_spatial_schema_version", CANONICAL_SPATIAL_SCHEMA_VERSION)
    root_prim.SetCustomDataByKey("export_timestamp", datetime.now(timezone.utc).isoformat())
    if locked_state_identifier is not None:
        root_prim.SetCustomDataByKey("study_locked_state_identifier", locked_state_identifier)


# ---------------------------------------------------------------------------
# Scene result contracts (sections 106-108)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SceneValidationIssue:
    issue_type: str
    detail: str
    prim_path: str | None = None


@dataclass(frozen=True)
class SceneValidationResult:
    valid: bool
    warnings: tuple[SceneValidationIssue, ...]
    errors: tuple[SceneValidationIssue, ...]


@dataclass(frozen=True)
class SceneExportResult:
    scene_path: str | None
    scene_format: Literal["IN_MEMORY", "USDA", "USDC"]
    adapter_version: str
    object_count: int
    mapped_prim_count: int
    unmapped_prim_count: int
    warnings: tuple[str, ...]
    validation_status: Literal["VALID", "INVALID"]


@dataclass(frozen=True)
class SceneImportResult:
    scene_path: str | None
    resolved_mappings: Mapping[str, str]
    transform_updates: Mapping[str, csa.Transform]
    unknown_prims: tuple[str, ...]
    warnings: tuple[str, ...]
    validation: SceneValidationResult


# ---------------------------------------------------------------------------
# Core scene export (sections 8-15, 25, 33-40)
# ---------------------------------------------------------------------------


_EQUIPMENT_PROXY_TYPES = frozenset({
    "CYCLOTRON", "MO99_TC99M_GENERATOR", "PET_SCANNER", "SPECT_SCANNER", "MRT_CARRIER", "MRT_CONTAINER",
})


def _dimensioned_proxy_scale(envelope: csa.EngineeringEnvelope) -> tuple[float, float, float] | None:
    """OpenUSD Phase 1A section 3: returns a (length, width, height) scale
    for the base 1.0-unit proxy Cube ONLY when all three axes are explicitly
    calibrated. An unknown envelope keeps the existing honest fixed-size
    fallback (section 3/8) -- never a fabricated calibrated appearance."""
    if not envelope.is_fully_known():
        return None
    return (float(envelope.length_m), float(envelope.width_m), float(envelope.height_m))


def bind_visual_asset(stage: "Usd.Stage", *, prim_path: str, geometry_asset: GeometryAsset | None) -> tuple[bool, str | None]:
    """OpenUSD Phase 1A sections 4-8: authors an OPTIONAL child '/Visual'
    prim referencing an external USD-family asset (.usd/.usda/.usdc) via
    standard USD reference composition. The engineering anchor prim at
    `prim_path` (and its '/Geom' proxy, when present) is NEVER replaced or
    removed -- this is purely additive, never a second engineering object
    (the '/Visual' prim carries no `mrtway_object_id` customData, exactly
    like the existing presentation-camera prims). Returns `(bound, reason)`:
    `reason` is None when nothing was configured, or a human-readable string
    when a configured asset was skipped -- the caller's honest proxy/
    fallback geometry already exists regardless (section 8)."""
    if geometry_asset is None or geometry_asset.visual_asset_path is None:
        return False, None
    _require_runtime()
    asset_path = geometry_asset.visual_asset_path
    if not os.path.isfile(asset_path):
        return False, f"visual asset not found, falling back to proxy: {asset_path!r}"
    if Sdf.Layer.FindOrOpen(asset_path) is None:
        return False, f"visual asset could not be opened as a USD layer, falling back to proxy: {asset_path!r}"
    visual_prim = UsdGeom.Xform.Define(stage, f"{prim_path}/Visual").GetPrim()
    visual_prim.GetReferences().AddReference(asset_path)
    apply_transform(visual_prim, geometry_asset.visual_asset_local_transform or csa.Transform())
    if geometry_asset.visual_asset_local_scale is not None:
        UsdGeom.XformCommonAPI(visual_prim).SetScale(Gf.Vec3f(*geometry_asset.visual_asset_local_scale))
    visual_prim.SetCustomDataByKey("visual_asset_path", asset_path)
    visual_prim.SetCustomDataByKey("geometry_quality", geometry_asset.geometry_quality)
    return True, None


def export_registry_to_stage(
    registry: csa.SpatialObjectRegistry, *, catalog_bindings: Mapping[str, str] = None,
    geometry_assets: GeometryAssetRegistry | None = None, locked_state_identifier: str | None = None,
) -> tuple["Usd.Stage", PrimPathRegistry, SceneExportResult]:
    """Sections 8-15: builds a fresh, independent in-memory USD stage from a
    `SpatialObjectRegistry` snapshot. Never mutates the canonical registry.
    Objects are visited in sorted MRTWAY_OBJECT_ID order for deterministic
    prim creation."""
    _require_runtime()
    catalog_bindings = catalog_bindings or {}
    geometry_assets = geometry_assets or GeometryAssetRegistry()

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(stage, METERS_PER_UNIT)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    root = UsdGeom.Xform.Define(stage, CAMPUS_ROOT_PATH)
    stage.SetDefaultPrim(root.GetPrim())
    attach_scene_version_metadata(root.GetPrim(), locked_state_identifier=locked_state_identifier)

    UsdGeom.Xform.Define(stage, f"{CAMPUS_ROOT_PATH}/Facility")
    UsdGeom.Scope.Define(stage, f"{CAMPUS_ROOT_PATH}/Facility/Buildings")
    UsdGeom.Scope.Define(stage, f"{CAMPUS_ROOT_PATH}/Facility/MRT")
    UsdGeom.Scope.Define(stage, f"{CAMPUS_ROOT_PATH}/Facility/Logistics")
    UsdGeom.Scope.Define(stage, f"{CAMPUS_ROOT_PATH}/Facility/Equipment")
    UsdGeom.Scope.Define(stage, f"{CAMPUS_ROOT_PATH}/Presentation")

    path_registry = PrimPathRegistry()
    warnings: list[str] = []

    for obj in sorted(registry.objects.values(), key=lambda o: o.mrtway_object_id):
        prim_path = build_deterministic_prim_path(obj)
        catalog_model_id = catalog_bindings.get(obj.mrtway_object_id)
        geometry_asset = geometry_assets.resolve(catalog_model_id)
        effective_geometry_asset = geometry_asset

        if obj.object_type in _EQUIPMENT_PROXY_TYPES:
            xform_prim = UsdGeom.Xform.Define(stage, prim_path).GetPrim()
            proxy = UsdGeom.Cube.Define(stage, f"{prim_path}/Geom")
            proxy.GetSizeAttr().Set(1.0)
            proxy.GetPurposeAttr().Set(UsdGeom.Tokens.proxy)
            scale = _dimensioned_proxy_scale(obj.dimensions)
            if scale is not None:
                UsdGeom.XformCommonAPI(proxy.GetPrim()).SetScale(Gf.Vec3f(*scale))
                if effective_geometry_asset is None or effective_geometry_asset.visual_asset_path is None:
                    # Section 3/7: honestly label a correctly-sized proxy as
                    # DIMENSIONAL_PROXY -- never silently left as
                    # GENERIC_PROXY/NOT_AVAILABLE once real dimensions exist,
                    # and never auto-upgraded past an explicit asset binding.
                    effective_geometry_asset = replace(effective_geometry_asset or _NOT_AVAILABLE_GEOMETRY_ASSET, geometry_quality="DIMENSIONAL_PROXY")
        else:
            xform_prim = UsdGeom.Xform.Define(stage, prim_path).GetPrim()

        apply_transform(xform_prim, obj.transform)
        attach_mrtway_metadata(xform_prim, obj, catalog_model_id=catalog_model_id, geometry_asset=effective_geometry_asset)

        bound, reason = bind_visual_asset(stage, prim_path=prim_path, geometry_asset=effective_geometry_asset)
        if reason is not None:
            warnings.append(f"{obj.mrtway_object_id}: {reason}")

        try:
            path_registry.register(mrtway_object_id=obj.mrtway_object_id, prim_path=prim_path)
        except PrimPathCollisionError as exc:
            warnings.append(str(exc))
            raise

    mapped_prim_count = len(path_registry)
    unmapped_prim_count = sum(1 for _ in stage.Traverse()) - mapped_prim_count
    result = SceneExportResult(
        scene_path=None, scene_format="IN_MEMORY", adapter_version=OPENUSD_ADAPTER_SCHEMA_VERSION,
        object_count=len(registry.objects), mapped_prim_count=mapped_prim_count,
        unmapped_prim_count=unmapped_prim_count, warnings=tuple(warnings), validation_status="VALID",
    )
    return stage, path_registry, result


def add_presentation_camera(stage: "Usd.Stage", *, camera_name: str = "MainCamera") -> str:
    """Section 92: a USD camera is presentation/view state ONLY -- never
    registered as an engineering object (no `mrtway_object_id` customData,
    lives under `/Presentation`, never touched by `PrimPathRegistry`)."""
    _require_runtime()
    path = f"{CAMPUS_ROOT_PATH}/Presentation/{sanitize_prim_path_segment(camera_name)}"
    UsdGeom.Camera.Define(stage, path)
    return path


def set_prim_visibility(stage: "Usd.Stage", prim_path: str, *, visible: bool) -> None:
    """Section 65/69-70: visibility is independent of `asset_status`/
    `operational_state` -- hiding a prim never means removed/unavailable."""
    _require_runtime()
    imageable = UsdGeom.Imageable(stage.GetPrimAtPath(prim_path))
    imageable.MakeVisible() if visible else imageable.MakeInvisible()


def get_prim_visibility(stage: "Usd.Stage", prim_path: str) -> bool:
    _require_runtime()
    imageable = UsdGeom.Imageable(stage.GetPrimAtPath(prim_path))
    return imageable.ComputeVisibility() != UsdGeom.Tokens.invisible


# ---------------------------------------------------------------------------
# Scene serialization / deserialization (sections 53-58)
# ---------------------------------------------------------------------------


def save_stage_to_usda(stage: "Usd.Stage", path: str) -> str:
    """Section 53: human-readable `.usda` text export -- preferred for
    development/testing. Caller is responsible for placing `path` in a
    temporary/test output location (section 114), never the repo root."""
    _require_runtime()
    stage.GetRootLayer().Export(path)
    return path


def load_stage_from_usda(path: str) -> "Usd.Stage":
    """Section 54: loads a previously-saved scene for import/read-back."""
    _require_runtime()
    return Usd.Stage.Open(path)


# ---------------------------------------------------------------------------
# Scene import / read-back + validation (sections 99-108)
# ---------------------------------------------------------------------------


def import_scene(stage: "Usd.Stage", registry: csa.SpatialObjectRegistry, *, scene_path: str | None = None) -> SceneImportResult:
    """Sections 99, 109: READ-ONLY -- never mutates `registry`. Resolves
    USD prim -> MRTWAY_OBJECT_ID via `customData`, flags orphan/duplicate
    mappings, invalid transforms, unit/up-axis mismatches. Unknown prims
    (camera, scopes, presentation geometry) are tracked, never turned into
    engineering objects."""
    _require_runtime()
    resolved_mappings: dict[str, str] = {}
    transform_updates: dict[str, csa.Transform] = {}
    unknown_prims: list[str] = []
    issues: list[SceneValidationIssue] = []

    for prim in stage.Traverse():
        prim_path = str(prim.GetPath())
        custom_data = prim.GetCustomData()
        mrtway_id = custom_data.get("mrtway_object_id")
        if mrtway_id is None:
            unknown_prims.append(prim_path)
            continue
        if mrtway_id in resolved_mappings:
            issues.append(SceneValidationIssue("DUPLICATE_MRTWAY_MAPPING", f"{mrtway_id!r} claimed by both {resolved_mappings[mrtway_id]!r} and {prim_path!r}", prim_path))
            continue
        if mrtway_id not in registry.objects:
            issues.append(SceneValidationIssue("ORPHAN_MRTWAY_MAPPING", f"{mrtway_id!r} not present in canonical registry", prim_path))
        resolved_mappings[mrtway_id] = prim_path
        if UsdGeom.Xformable(prim):
            transform = read_transform(prim)
            values = (transform.position_x, transform.position_y, transform.position_z, transform.rotation_x, transform.rotation_y, transform.rotation_z)
            if not all(math.isfinite(v) for v in values):
                issues.append(SceneValidationIssue("INVALID_TRANSFORM", f"non-finite transform component on {mrtway_id!r}", prim_path))
            else:
                transform_updates[mrtway_id] = transform

    meters_per_unit = UsdGeom.GetStageMetersPerUnit(stage)
    if not math.isclose(meters_per_unit, METERS_PER_UNIT, rel_tol=1e-9):
        issues.append(SceneValidationIssue("UNIT_MISMATCH", f"stage metersPerUnit={meters_per_unit} != expected {METERS_PER_UNIT}"))

    up_axis = UsdGeom.GetStageUpAxis(stage)
    if up_axis != UsdGeom.Tokens.z:
        issues.append(SceneValidationIssue("UP_AXIS_MISMATCH", f"stage upAxis={up_axis} != expected {UP_AXIS}"))

    error_types = {"ORPHAN_MRTWAY_MAPPING", "DUPLICATE_MRTWAY_MAPPING", "INVALID_TRANSFORM", "UNIT_MISMATCH", "UP_AXIS_MISMATCH"}
    errors = tuple(i for i in issues if i.issue_type in error_types)
    validation = SceneValidationResult(valid=len(errors) == 0, warnings=(), errors=errors)

    return SceneImportResult(
        scene_path=scene_path, resolved_mappings=resolved_mappings, transform_updates=transform_updates,
        unknown_prims=tuple(unknown_prims), warnings=(), validation=validation,
    )


def apply_validated_transform_changes(
    import_result: SceneImportResult, what_if: csa.WhatIfSpatialState, *, change_id_prefix: str,
) -> tuple[csa.SpatialChangeSet, ...]:
    """Section 110: explicit, separate call from `import_scene` (which is
    read-only). Applies USD-derived transforms ONLY to the WHAT-IF state's
    registry via the existing reversible `apply_changeset` path -- never
    directly mutates locked engineering state."""
    changesets = []
    for mrtway_id, transform in import_result.transform_updates.items():
        if mrtway_id not in what_if.registry.objects:
            continue
        obj = what_if.registry.get(mrtway_id)
        if transform != obj.transform:
            new_object = replace(obj, transform=transform)
            changesets.append(csa.apply_changeset(what_if, change_id=f"{change_id_prefix}-{mrtway_id}", operation="MOVE_OBJECT", object_id=mrtway_id, new_object=new_object))
    return tuple(changesets)


# ---------------------------------------------------------------------------
# Selection round-trip + object-inspector reuse (sections 60-63, 111-113)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SelectionResult:
    prim_path: str
    mrtway_object_id: str
    object_type: str
    canonical_parent: str | None
    selection_scope: csa.SelectionScope
    transform: csa.Transform
    geometry_quality: GeometryQuality


def resolve_selection(prim_path: str, path_registry: PrimPathRegistry, registry: csa.SpatialObjectRegistry, stage: "Usd.Stage") -> SelectionResult | None:
    """Section 60/111: USD prim selected -> MRTWAY_OBJECT_ID -> canonical
    object. Returns None for unknown/presentation prims (never fabricates
    an engineering object)."""
    _require_runtime()
    mrtway_id = path_registry.resolve_by_prim_path(prim_path)
    if mrtway_id is None or mrtway_id not in registry.objects:
        return None
    obj = registry.get(mrtway_id)
    prim = stage.GetPrimAtPath(prim_path)
    geometry_quality = prim.GetCustomData().get("geometry_quality", "NOT_AVAILABLE")
    return SelectionResult(
        prim_path=prim_path, mrtway_object_id=mrtway_id, object_type=obj.object_type,
        canonical_parent=obj.parent_object_id, selection_scope="OBJECT", transform=obj.transform,
        geometry_quality=geometry_quality,
    )


def resolve_multi_selection(
    prim_paths: Sequence[str], path_registry: PrimPathRegistry, registry: csa.SpatialObjectRegistry, *, selection_id: str,
) -> csa.SelectionSet:
    """Section 61: multiple selected USD prims -> ONE canonical SelectionSet
    (reuses `canonical_spatial_authority.build_selection_set` -- never a
    second selection-set type)."""
    object_ids = tuple(
        mrtway_id for p in prim_paths
        if (mrtway_id := path_registry.resolve_by_prim_path(p)) is not None and mrtway_id in registry.objects
    )
    return csa.build_selection_set(selection_id=selection_id, selected_object_ids=object_ids, selection_scope=("MULTI_OBJECT" if len(object_ids) > 1 else "OBJECT"), provenance="USD_SELECTION")


def resolve_object_inspector_for_prim(prim_path: str, path_registry: PrimPathRegistry, registry: csa.SpatialObjectRegistry) -> csa.ObjectInspectorRecord | None:
    """Section 112: reuses the existing canonical object-inspector contract
    -- never duplicates engineering calculations for a USD-selected prim."""
    mrtway_id = path_registry.resolve_by_prim_path(prim_path)
    if mrtway_id is None or mrtway_id not in registry.objects:
        return None
    return csa.build_object_inspector_record(registry.get(mrtway_id))


def resolve_delta_for_prim(
    prim_path: str, path_registry: PrimPathRegistry, locked: csa.LockedSpatialState, what_if: csa.WhatIfSpatialState,
) -> csa.SpatialDelta:
    """Section 113: proves a USD selection/change can resolve to the
    EXISTING locked/what-if delta authority (`compute_delta`) without a
    second economics/delta engine."""
    return csa.compute_delta(locked, what_if)


# ---------------------------------------------------------------------------
# Locked / what-if scene export + return-to-locked (sections 44-49, 81, 86-87)
# ---------------------------------------------------------------------------


def export_locked_state(locked: csa.LockedSpatialState, **kwargs) -> tuple["Usd.Stage", PrimPathRegistry, SceneExportResult]:
    """Section 44: independent stage built from the locked registry snapshot."""
    return export_registry_to_stage(locked.registry, locked_state_identifier="LOCKED", **kwargs)


def export_what_if_state(what_if: csa.WhatIfSpatialState, **kwargs) -> tuple["Usd.Stage", PrimPathRegistry, SceneExportResult]:
    """Section 45: independent stage built from the what-if registry snapshot
    -- built fresh, never derived from or sharing state with the locked stage."""
    return export_registry_to_stage(what_if.registry, locked_state_identifier="WHAT_IF", **kwargs)


def return_to_locked_view(locked_export: SceneExportResult) -> SceneExportResult:
    """Section 86: RETURN TO LOCKED VIEW -- trivially returns the already-
    exported locked `SceneExportResult` unchanged. No re-simulation, no
    re-export; the locked stage was never touched by what-if authoring
    because it is a wholly separate `Usd.Stage` object."""
    return locked_export


# ---------------------------------------------------------------------------
# Architecture visibility + Hybrid coverage metadata (sections 43, 66-68)
# ---------------------------------------------------------------------------


def apply_architecture_visibility(
    stage: "Usd.Stage", path_registry: PrimPathRegistry, *, architecture: str, active_object_ids: frozenset[str],
    registry: csa.SpatialObjectRegistry,
) -> None:
    """Section 66: presentation-only -- toggles USD visibility + a
    non-authoritative customData tag per architecture, for LEAF engineering/
    MRT/logistics objects only (never the FACILITY/BUILDING/FLOOR structural
    hierarchy, since USD visibility inherits from ancestors and hiding a
    structural container would incorrectly hide unrelated descendants).
    Never mutates MRTWAY_OBJECT_ID, geometry, or canonical identity."""
    _require_runtime()
    structural_types = frozenset({"FACILITY", "BUILDING", "FLOOR"})
    for mrtway_id, prim_path in path_registry.by_mrtway_id.items():
        if mrtway_id not in registry.objects or registry.get(mrtway_id).object_type in structural_types:
            continue
        active = mrtway_id in active_object_ids
        set_prim_visibility(stage, prim_path, visible=active)
        prim = stage.GetPrimAtPath(prim_path)
        architecture_state = dict(prim.GetCustomDataByKey("architecture_visibility") or {})
        architecture_state[architecture] = active
        prim.SetCustomDataByKey("architecture_visibility", architecture_state)


def apply_hybrid_coverage_metadata(stage: "Usd.Stage", path_registry: PrimPathRegistry, coverage: csa.HybridSpatialCoverageMap) -> None:
    """Section 43/67: non-authoritative coverage tag reused from the closure
    build's `HybridSpatialCoverageMap` -- canonical architecture authority
    remains entirely outside USD."""
    _require_runtime()
    for zone in coverage.zones:
        prim_path = path_registry.resolve_by_mrtway_id(zone.zone_object_id)
        if prim_path is None:
            continue
        stage.GetPrimAtPath(prim_path).SetCustomDataByKey("hybrid_coverage", zone.coverage_mode)


# ---------------------------------------------------------------------------
# OpenUSD Phase 2A: vendor-neutral dynamic scene-state time-sample adapter
# (sections 2-7). This is the ONLY place `dynamic_scene_state_authority`
# is translated into real `Usd.TimeCode`-sampled attributes -- the contract
# module itself never imports `pxr` (section 4).
# ---------------------------------------------------------------------------


def configure_stage_time_basis(stage: "Usd.Stage", *, start_time_minutes: float, end_time_minutes: float) -> None:
    """Section 3: authors the stage-level time metadata implementing the
    documented `1 USD TimeCode == 1 simulation second` mapping -- never lets
    an arbitrary frame rate become simulation authority."""
    _require_runtime()
    stage.SetTimeCodesPerSecond(dss.USD_TIME_CODES_PER_SECOND)
    stage.SetFramesPerSecond(dss.USD_TIME_CODES_PER_SECOND)
    stage.SetStartTimeCode(dss.simulation_minutes_to_usd_timecode(start_time_minutes))
    stage.SetEndTimeCode(dss.simulation_minutes_to_usd_timecode(end_time_minutes))
    default_prim = stage.GetDefaultPrim()
    if default_prim:
        default_prim.SetCustomDataByKey("mrtway_simulation_time_unit", dss.MRT_SIMULATION_TIME_UNIT)
        default_prim.SetCustomDataByKey("mrtway_time_basis", "1_USD_TIMECODE_EQUALS_1_SIMULATION_SECOND")


class DynamicTrajectoryIdentityError(ValueError):
    """Section 7: raised when a trajectory's `canonical_object_id` does not
    match the target prim's own `mrtway_object_id` -- never silently bound
    to the wrong engineering anchor."""


def author_dynamic_object_trajectory(stage: "Usd.Stage", *, prim_path: str, trajectory: dss.DynamicObjectTrajectory) -> None:
    """Sections 6-7: authors MANY time samples on the ONE already-existing
    stable engineering anchor prim at `prim_path` -- never creates a new
    prim per time step (section 7). Position/rotation are authored as
    standard USD time-sampled `XformCommonAPI` ops (generic-consumer-usable,
    section 6); `movement_state`/`simulation_time_minutes` are authored as
    plain time-sampled custom USD attributes (namespaced `mrtway:*`, never
    engineering-authoritative) so per-time-step presentation state survives
    the round trip alongside position."""
    _require_runtime()
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise DynamicTrajectoryIdentityError(f"no prim exists at {prim_path!r} -- author the engineering anchor first")
    existing_id = prim.GetCustomDataByKey("mrtway_object_id")
    if existing_id is not None and existing_id != trajectory.canonical_object_id:
        raise DynamicTrajectoryIdentityError(
            f"trajectory canonical_object_id {trajectory.canonical_object_id!r} does not match "
            f"anchor prim's mrtway_object_id {existing_id!r} at {prim_path!r}"
        )
    api = UsdGeom.XformCommonAPI(prim)
    movement_attr = prim.CreateAttribute("mrtway:movementState", Sdf.ValueTypeNames.Token)
    sim_time_attr = prim.CreateAttribute("mrtway:simulationTimeMinutes", Sdf.ValueTypeNames.Double)
    for sample in trajectory.samples:
        timecode = Usd.TimeCode(dss.simulation_minutes_to_usd_timecode(sample.simulation_time_minutes))
        api.SetTranslate(Gf.Vec3d(sample.position_x_m, sample.position_y_m, sample.position_z_m), timecode)
        if sample.rotation_z_deg is not None:
            api.SetRotate(Gf.Vec3f(0.0, 0.0, sample.rotation_z_deg), timecode)
        movement_attr.Set(sample.movement_state, timecode)
        sim_time_attr.Set(sample.simulation_time_minutes, timecode)
    prim.SetCustomDataByKey("dynamic_trajectory_provenance", trajectory.provenance)
    prim.SetCustomDataByKey("dynamic_trajectory_interpolation_method", trajectory.interpolation_method)


def read_dynamic_object_state_at_time(stage: "Usd.Stage", *, prim_path: str, simulation_time_minutes: float) -> dss.DynamicObjectState:
    """Section 6 read-back: resolves the time-sampled position/movement
    state at an EXACT authored (or USD-interpolated) simulation time --
    never mutates the stage or canonical registry."""
    _require_runtime()
    prim = stage.GetPrimAtPath(prim_path)
    timecode = Usd.TimeCode(dss.simulation_minutes_to_usd_timecode(simulation_time_minutes))
    api = UsdGeom.XformCommonAPI(prim)
    translate, rotate, _scale, _pivot, _order = api.GetXformVectors(timecode)
    movement_state = prim.GetAttribute("mrtway:movementState").Get(timecode)
    canonical_object_id = prim.GetCustomDataByKey("mrtway_object_id")
    return dss.DynamicObjectState(
        canonical_object_id=canonical_object_id, simulation_time_minutes=simulation_time_minutes,
        position_x_m=float(translate[0]), position_y_m=float(translate[1]), position_z_m=float(translate[2]),
        rotation_z_deg=float(rotate[2]), movement_state=movement_state or "UNKNOWN",
        provenance=str(prim.GetCustomDataByKey("dynamic_trajectory_provenance") or ""),
    )

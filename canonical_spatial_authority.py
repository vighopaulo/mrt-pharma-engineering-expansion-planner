"""Canonical Facility Geometry + Spatial Object Authority.

GOVERNANCE (section 1): MRTway owns the canonical engineering/spatial
identity. External platforms (OpenUSD, Omniverse, iTwin, IFC, Revit, CAD,
native viewers) map to MRTway objects through adapters -- external IDs are
NEVER the authoritative identity (section 3-4).

REUSE, NOT DUPLICATION: this module composes existing authorities --
`general_oncology_logistics.FacilityRoleLocation` (general-logistics
origins), `spatial_benchmark.BenchmarkGeometry` (room/floor geometry),
`oncology_pet_spect_scenario.OncologyPatientRecord` (patient spatial
identity), `hybrid_optimization.HybridPatientTrace` (nuclear transport trace,
UNCHANGED) -- rather than reinventing facility/patient/nuclear objects.
MRT_TRUNK/BRANCH/SEGMENT/JUNCTION/ENDPOINT/VESTIBULE are the genuinely NEW
first-class objects this module introduces (section 12-13), since no prior
build modeled them as anything other than a generic length/CapEx-per-meter
figure.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace, asdict
from datetime import datetime, timezone
from typing import Literal, Mapping, Sequence

SpatialObjectType = Literal[
    # Facility hierarchy (section 8-9)
    "FACILITY", "BUILDING", "FLOOR", "ROOM", "CORRIDOR", "ELEVATOR", "STAIR", "DOOR", "SHAFT",
    "SERVICE_ZONE", "EQUIPMENT", "LOGISTICS_ORIGIN", "LOGISTICS_DESTINATION", "MRT_INFRASTRUCTURE",
    # Oncology/nuclear engineering objects (section 10)
    "CYCLOTRON", "MO99_TC99M_GENERATOR", "PET_SCANNER", "SPECT_SCANNER", "RADIOPHARMACY",
    "INJECTION_ROOM", "UPTAKE_ROOM", "PATIENT_ROOM", "NUCLEAR_MEDICINE_ROOM", "CONTROL_ROOM",
    "STORAGE", "UTILITY_SPACE",
    # General logistics origins (section 11)
    "CENTRAL_PHARMACY", "LABORATORY", "BLOOD_BANK", "CLEAN_LINEN_SOURCE", "STERILE_CLEAN_SUPPLY_SOURCE",
    # MRT engineering objects (section 12-13)
    "MRT_TRUNK", "MRT_BRANCH", "MRT_SEGMENT", "MRT_JUNCTION", "MRT_ENDPOINT", "MRT_CARRIER",
    "MRT_CONTAINER", "MRT_VESTIBULE",
    # Transport Spatial Authority Build 2: RGHT (Rail-Guided Hospital Transport) engineering
    # objects -- a DISTINCT installed network from MRT (never shared installed-network
    # objects, see rght_spatial_network_authority.py governance).
    "RGHT_TRACK_SEGMENT", "RGHT_STATION", "RGHT_SWITCH", "RGHT_VERTICAL_SEGMENT", "RGHT_VEHICLE",
    # Transport Spatial Authority Build 3: PTS (Pneumatic Tube System) engineering objects --
    # a DISTINCT installed network from both MRT and RGHT (see
    # pts_spatial_network_authority.py governance).
    "PTS_STATION", "PTS_TUBE_SEGMENT", "PTS_JUNCTION", "PTS_VERTICAL_SEGMENT", "PTS_CAPSULE",
]

CoordinateSystem = Literal["LOCAL_FACILITY", "LOCAL_BUILDING", "PROJECT_GLOBAL", "EXTERNAL_MODEL"]

SpatialStatus = Literal[
    "CALIBRATED", "PARTIALLY_CALIBRATED", "LOCATION_NOT_CALIBRATED", "ORIENTATION_NOT_CALIBRATED",
    "GEOMETRY_NOT_CALIBRATED", "DERIVED", "USER_PLACED", "IMPORTED",
]

Provenance = Literal[
    "USER_CREATED", "TEMPLATE", "IMPORTED_IFC", "IMPORTED_CAD", "RECONSTRUCTED", "API", "DERIVED", "USER_RELOCATED",
    "IMPORTED_ITWIN",
]

AssetStatus = Literal["EXISTING", "PROPOSED"]
OperationalState = Literal["AVAILABLE", "UNAVAILABLE", "MAINTENANCE"]
TransportMode = Literal["WALKING_PORTER", "AGV_AMR", "PNEUMATIC_TUBE", "MRT", "PATIENT_MOVEMENT"]


@dataclass(frozen=True)
class Transform:
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    rotation_x: float = 0.0
    rotation_y: float = 0.0
    rotation_z: float = 0.0


@dataclass(frozen=True)
class EngineeringEnvelope:
    """OpenUSD Phase 1A section 2: optional canonical bounding envelope --
    each axis is explicitly `NOT_CALIBRATED` (unknown) unless supplied by
    canonical data. Never inferred from a visual asset or fabricated to
    improve appearance. Independent of `Transform` (position/rotation only)
    and of the pre-existing free-form `geometry_reference` string."""

    length_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    width_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    height_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"

    def is_fully_known(self) -> bool:
        return all(v != "NOT_CALIBRATED" for v in (self.length_m, self.width_m, self.height_m))


@dataclass(frozen=True)
class ExternalReference:
    """Section 4: mappings only -- never MRTway identity."""

    ifc_guid: str | None = None
    revit_element_id: str | None = None
    itwin_element_id: str | None = None
    usd_prim_path: str | None = None
    cad_entity_id: str | None = None
    source_document_id: str | None = None
    external_project_id: str | None = None
    """Bentley iTwin ID -- model-scope identity, shared by every object from
    the same iTwin project (never a per-object collision-checked field)."""
    external_model_id: str | None = None
    """Bentley iModel ID -- same sharing rule as `external_project_id`."""
    change_reference: str | None = None
    """Bentley changeset/revision identity -- metadata only in this phase
    (no live changeset polling); reuses `itwin_element_id` for element
    identity, never a second element-ID field."""


@dataclass(frozen=True)
class CanonicalSpatialObject:
    """Section 2-3: the ONE stable, platform-neutral spatial identity.
    `mrtway_object_id` survives viewer changes, BIM re-import, architecture
    switching, and study branching -- never array position."""

    mrtway_object_id: str
    object_type: SpatialObjectType
    facility_id: str
    building_id: str | None
    floor_id: str | None
    space_id: str | None
    parent_object_id: str | None
    transform: Transform
    geometry_reference: str | None
    coordinate_system: CoordinateSystem
    asset_status: AssetStatus
    operational_state: OperationalState
    spatial_status: SpatialStatus
    provenance: Provenance
    external_reference: ExternalReference = field(default_factory=ExternalReference)
    confidence: Literal["high", "medium", "low", "unknown"] = "unknown"
    engineering_object_id: str | None = None
    """Section 37: explicit mapping to the existing engineering-authority
    object (e.g. CY-001, GEN-001) where a separate engineering identity
    already exists -- never inferred from a viewer mesh name."""
    dimensions: EngineeringEnvelope = field(default_factory=EngineeringEnvelope)
    """OpenUSD Phase 1A section 2: optional bounding envelope -- defaults to
    fully NOT_CALIBRATED (unknown) for every existing object; never silently
    upgraded to a calibrated value by an adapter/exporter."""


@dataclass
class SpatialObjectRegistry:
    """Section 3/56: objects keyed by `mrtway_object_id` -- never by list
    position."""

    objects: dict[str, CanonicalSpatialObject] = field(default_factory=dict)

    def add(self, obj: CanonicalSpatialObject) -> None:
        if obj.mrtway_object_id in self.objects:
            raise ValueError(f"duplicate mrtway_object_id: {obj.mrtway_object_id}")
        self.objects[obj.mrtway_object_id] = obj

    def get(self, mrtway_object_id: str) -> CanonicalSpatialObject:
        return self.objects[mrtway_object_id]

    def by_type(self, object_type: SpatialObjectType) -> tuple[CanonicalSpatialObject, ...]:
        return tuple(o for o in self.objects.values() if o.object_type == object_type)

    def children_of(self, parent_object_id: str) -> tuple[CanonicalSpatialObject, ...]:
        return tuple(o for o in self.objects.values() if o.parent_object_id == parent_object_id)

    def replace_transform(self, mrtway_object_id: str, transform: "Transform") -> "SpatialObjectRegistry":
        """Build-2 closure (Section 17-18): non-mutating -- returns a NEW
        registry with ONLY this object's transform replaced. Children are
        untouched because their own `transform` fields are already stored
        RELATIVE to their parent's frame (Section 17/18 rigid-body property):
        replacing a building's transform moves/rotates the whole building and
        everything inside it, without touching any child object."""
        new_registry = SpatialObjectRegistry(objects=dict(self.objects))
        new_registry.objects[mrtway_object_id] = replace(self.get(mrtway_object_id), transform=transform)
        return new_registry


def _rotation_matrix(transform: "Transform") -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    """Intrinsic X-then-Y-then-Z Euler rotation matrix (degrees), applied as
    R = Rz @ Ry @ Rx to a local-frame vector. Section 17: `x_global' = R x_local + t`."""
    rx, ry, rz = math.radians(transform.rotation_x), math.radians(transform.rotation_y), math.radians(transform.rotation_z)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    r_x = ((1.0, 0.0, 0.0), (0.0, cx, -sx), (0.0, sx, cx))
    r_y = ((cy, 0.0, sy), (0.0, 1.0, 0.0), (-sy, 0.0, cy))
    r_z = ((cz, -sz, 0.0), (sz, cz, 0.0), (0.0, 0.0, 1.0))

    def matmul(a, b):
        return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))

    return matmul(matmul(r_z, r_y), r_x)


def apply_rigid_transform(local_position: tuple[float, float, float], transform: "Transform") -> tuple[float, float, float]:
    """Section 17: `x_global' = R x_local + t` for ONE transform step. Pure
    geometry, reusing the EXISTING `Transform` dataclass -- never a new
    physics/geometry engine."""
    r = _rotation_matrix(transform)
    x, y, z = local_position
    return (
        r[0][0] * x + r[0][1] * y + r[0][2] * z + transform.position_x,
        r[1][0] * x + r[1][1] * y + r[1][2] * z + transform.position_y,
        r[2][0] * x + r[2][1] * y + r[2][2] * z + transform.position_z,
    )


def resolve_global_position(registry: SpatialObjectRegistry, mrtway_object_id: str) -> tuple[float, float, float]:
    """Section 17 closure (Build 2, confirmed genuine gap): accumulates
    `x_global' = R x_local + t` up the parent chain (object -> floor ->
    building -> facility). The FACILITY root's transform is identity by
    construction (`build_facility_hierarchy`), i.e. PROJECT_GLOBAL. This is
    the SAME `Transform` already stored on every `CanonicalSpatialObject` and
    read/written by `openusd_spatial_adapter.py` -- never a visual-only
    transform disconnected from engineering coordinates (Section 17
    requirement)."""
    chain: list[Transform] = []
    current: CanonicalSpatialObject | None = registry.get(mrtway_object_id)
    while current is not None:
        chain.append(current.transform)
        current = registry.get(current.parent_object_id) if current.parent_object_id else None
    position = (0.0, 0.0, 0.0)
    for transform in chain:
        position = apply_rigid_transform(position, transform)
    return position


def compute_global_distance(registry: SpatialObjectRegistry, object_id_a: str, object_id_b: str) -> float:
    """Section 22-25 closure: real Euclidean distance derived from ACTUAL
    accumulated global coordinates -- never a hardcoded separation constant."""
    ax, ay, az = resolve_global_position(registry, object_id_a)
    bx, by, bz = resolve_global_position(registry, object_id_b)
    return math.sqrt((bx - ax) ** 2 + (by - ay) ** 2 + (bz - az) ** 2)


# ---------------------------------------------------------------------------
# Facility hierarchy builder (section 8-9) -- reuses existing authorities,
# never a duplicate facility model.
# ---------------------------------------------------------------------------


def build_facility_hierarchy(*, facility_id: str = "FAC-001") -> SpatialObjectRegistry:
    registry = SpatialObjectRegistry()
    registry.add(CanonicalSpatialObject(
        mrtway_object_id=facility_id, object_type="FACILITY", facility_id=facility_id, building_id=None, floor_id=None,
        space_id=None, parent_object_id=None, transform=Transform(), geometry_reference=None,
        coordinate_system="PROJECT_GLOBAL", asset_status="EXISTING", operational_state="AVAILABLE",
        spatial_status="CALIBRATED", provenance="USER_CREATED",
    ))
    return registry


def add_building(registry: SpatialObjectRegistry, *, facility_id: str, building_id: str, transform: Transform = Transform()) -> CanonicalSpatialObject:
    obj = CanonicalSpatialObject(
        mrtway_object_id=building_id, object_type="BUILDING", facility_id=facility_id, building_id=building_id,
        floor_id=None, space_id=None, parent_object_id=facility_id, transform=transform, geometry_reference=None,
        coordinate_system="LOCAL_FACILITY", asset_status="EXISTING", operational_state="AVAILABLE",
        spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def default_floor_object_id(building_id: str, floor_id: str) -> str:
    """Section 9/N-BUILDING GENERALITY: floor labels (e.g. "F1") are only
    unique WITHIN a building -- the stable floor object id must be
    building-scoped so N buildings can each have their own "F1" without
    colliding. Callers needing the legacy single-building convention
    (`floor_id` alone) can pass an explicit `floor_object_id` to
    `add_floor`/`add_room` instead."""
    return f"{building_id}::{floor_id}"


def add_floor(registry: SpatialObjectRegistry, *, facility_id: str, building_id: str, floor_id: str, floor_object_id: str | None = None, transform: Transform = Transform()) -> CanonicalSpatialObject:
    resolved_floor_object_id = floor_object_id or default_floor_object_id(building_id, floor_id)
    obj = CanonicalSpatialObject(
        mrtway_object_id=resolved_floor_object_id, object_type="FLOOR", facility_id=facility_id, building_id=building_id,
        floor_id=floor_id, space_id=None, parent_object_id=building_id, transform=transform, geometry_reference=None,
        coordinate_system="LOCAL_BUILDING", asset_status="EXISTING", operational_state="AVAILABLE",
        spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def add_room(
    registry: SpatialObjectRegistry, *, facility_id: str, building_id: str, floor_id: str, room_id: str,
    floor_object_id: str | None = None, object_type: SpatialObjectType = "ROOM", transform: Transform = Transform(),
    spatial_status: SpatialStatus = "CALIBRATED", engineering_object_id: str | None = None,
) -> CanonicalSpatialObject:
    resolved_floor_object_id = floor_object_id or default_floor_object_id(building_id, floor_id)
    obj = CanonicalSpatialObject(
        mrtway_object_id=room_id, object_type=object_type, facility_id=facility_id, building_id=building_id,
        floor_id=floor_id, space_id=room_id, parent_object_id=resolved_floor_object_id, transform=transform, geometry_reference=None,
        coordinate_system="LOCAL_BUILDING", asset_status="EXISTING", operational_state="AVAILABLE",
        spatial_status=spatial_status, provenance="USER_CREATED", engineering_object_id=engineering_object_id,
    )
    registry.add(obj)
    return obj


def build_general_logistics_origin_objects(registry: SpatialObjectRegistry, *, facility_id: str, building_id: str, floor_id: str, floor_object_id: str | None = None) -> tuple[CanonicalSpatialObject, ...]:
    """Section 11: reuses `general_oncology_logistics.build_default_facility_roles`
    -- resolves prior LOCATION_NOT_CALIBRATED roles where real geometry now
    exists, never a duplicate origin model."""
    from general_oncology_logistics import build_default_facility_roles

    resolved_floor_object_id = floor_object_id or default_floor_object_id(building_id, floor_id)
    role_to_object_type: Mapping[str, SpatialObjectType] = {
        "CENTRAL_PHARMACY": "CENTRAL_PHARMACY", "LABORATORY": "LABORATORY", "BLOOD_BANK": "BLOOD_BANK",
        "CLEAN_LINEN_SOURCE": "CLEAN_LINEN_SOURCE", "STERILE_CLEAN_SUPPLY": "STERILE_CLEAN_SUPPLY_SOURCE",
    }
    created = []
    for role in build_default_facility_roles():
        if role.role not in role_to_object_type:
            continue
        object_id = role.object_id or f"{role.role}-NOT-CALIBRATED"
        status: SpatialStatus = "CALIBRATED" if role.location_status == "CALIBRATED" else "LOCATION_NOT_CALIBRATED"
        parent_id = default_floor_object_id(role.building_id, role.floor_id) if (role.building_id and role.floor_id) else resolved_floor_object_id
        obj = CanonicalSpatialObject(
            mrtway_object_id=object_id, object_type=role_to_object_type[role.role], facility_id=facility_id,
            building_id=(role.building_id or building_id), floor_id=(role.floor_id or floor_id), space_id=object_id,
            parent_object_id=parent_id, transform=Transform(), geometry_reference=None,
            coordinate_system="LOCAL_BUILDING", asset_status="EXISTING", operational_state="AVAILABLE",
            spatial_status=status, provenance="DERIVED",
        )
        if obj.mrtway_object_id not in registry.objects:
            registry.add(obj)
        created.append(obj)
    return tuple(created)


def build_nuclear_engineering_objects(
    registry: SpatialObjectRegistry, *, facility_id: str, building_id: str, floor_id: str,
    floor_object_id: str | None = None, cyclotron_id: str = "CY-001", generator_id: str | None = None,
    pet_scanner_id: str = "SCN-PET-001", spect_scanner_id: str | None = None, radiopharmacy_id: str = "RP-001",
) -> tuple[CanonicalSpatialObject, ...]:
    """Section 10: spatial identity for nuclear engineering objects --
    `engineering_object_id` links to the existing (unchanged) engineering
    authority (cyclotron_catalog.py, generator_catalog.py, scanner_catalog.py)."""
    resolved_floor_object_id = floor_object_id or default_floor_object_id(building_id, floor_id)
    created = []
    specs: list[tuple[str, SpatialObjectType, str]] = [
        (cyclotron_id, "CYCLOTRON", cyclotron_id), (pet_scanner_id, "PET_SCANNER", pet_scanner_id),
        (radiopharmacy_id, "RADIOPHARMACY", radiopharmacy_id),
    ]
    if generator_id:
        specs.append((generator_id, "MO99_TC99M_GENERATOR", generator_id))
    if spect_scanner_id:
        specs.append((spect_scanner_id, "SPECT_SCANNER", spect_scanner_id))
    for mrtway_id, object_type, engineering_id in specs:
        obj = CanonicalSpatialObject(
            mrtway_object_id=mrtway_id, object_type=object_type, facility_id=facility_id, building_id=building_id,
            floor_id=floor_id, space_id=mrtway_id, parent_object_id=resolved_floor_object_id, transform=Transform(),
            geometry_reference=None, coordinate_system="LOCAL_BUILDING", asset_status="EXISTING",
            operational_state="AVAILABLE", spatial_status="CALIBRATED", provenance="USER_CREATED",
            engineering_object_id=engineering_id,
        )
        if obj.mrtway_object_id not in registry.objects:
            registry.add(obj)
        created.append(obj)
    return tuple(created)


# ---------------------------------------------------------------------------
# MRT engineering objects (sections 12-17) -- first-class, never generic
# line segments.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MrtSegmentGeometry:
    """Section 16-17: geometric length -- derived from calibrated geometry
    where available, explicit status otherwise (never fabricated)."""

    length_m: float | Literal["NOT_CALIBRATED"]
    status: SpatialStatus


def build_mrt_segment(
    registry: SpatialObjectRegistry, *, segment_id: str, facility_id: str, start_object_id: str, end_object_id: str,
    length_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED", asset_status: AssetStatus = "EXISTING",
) -> CanonicalSpatialObject:
    status: SpatialStatus = "CALIBRATED" if length_m != "NOT_CALIBRATED" else "GEOMETRY_NOT_CALIBRATED"
    obj = CanonicalSpatialObject(
        mrtway_object_id=segment_id, object_type="MRT_SEGMENT", facility_id=facility_id, building_id=None, floor_id=None,
        space_id=None, parent_object_id=None, transform=Transform(), geometry_reference=f"LENGTH:{length_m}",
        coordinate_system="PROJECT_GLOBAL", asset_status=asset_status, operational_state="AVAILABLE",
        spatial_status=status, provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


@dataclass(frozen=True)
class VestibuleEconomics:
    """Section 15 (prior build) / CLOSURE BUILD section 5: vestibule
    economics are DISTINCT from ordinary conduit per-meter pricing, and are
    ALSO distinct from MRT-system-level controls/installation costs (those
    are charged once per network/project -- see `MRT_CONTROLS_CAPEX_USD`/
    `MRT_INSTALLATION_COMMISSIONING_CAPEX_USD` below, never per vestibule)."""

    base_capex: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    installation_capex: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    integration_capex: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    annual_maintenance_opex: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    provenance: str = "NOT_CALIBRATED (no vestibule-specific cost evidence located this session)"

    def total_capex(self) -> float | Literal["NOT_CALIBRATED"]:
        parts = (self.base_capex, self.installation_capex, self.integration_capex)
        if any(p == "NOT_CALIBRATED" for p in parts):
            return "NOT_CALIBRATED"
        return sum(parts)  # type: ignore[arg-type]


CONTROLLED_VESTIBULE_ECONOMICS = VestibuleEconomics(
    base_capex=30_000.0, installation_capex=0.0, integration_capex=0.0, annual_maintenance_opex=1_500.0,
    provenance=(
        "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION: MRT_VESTIBULE_CAPEX_USD = $30,000 per vestibule "
        "(vestibule-specific only). CLOSURE BUILD CORRECTION: the prior build's $43,000 figure "
        "(base $25,000 + installation $10,000 + integration $8,000) is SUPERSEDED -- it conflicted with "
        "this user-supplied value and folded system-level installation/integration cost into a per-vestibule "
        "charge. Installation/commissioning and controls are now tracked ONCE per MRT network/project via "
        "MRT_INSTALLATION_COMMISSIONING_CAPEX_USD / MRT_CONTROLS_CAPEX_USD, never multiplied per vestibule. "
        "Annual maintenance OPEX ($1,500/vestibule/year) is unchanged from the prior build's engineering "
        "estimate -- the user did not revise vestibule OPEX this round."
    ),
)


def build_mrt_vestibule(
    registry: SpatialObjectRegistry, *, vestibule_id: str, facility_id: str, radiopharmacy_object_id: str,
    connected_mrt_segment_id: str, asset_status: AssetStatus = "PROPOSED",
) -> CanonicalSpatialObject:
    """Section 13-14: RADIOPHARMACY -> MRT_VESTIBULE -> MRT_TRUNK/segment --
    the vestibule is a distinct object, never folded into the radiopharmacy
    or the segment."""
    if radiopharmacy_object_id not in registry.objects:
        raise ValueError(f"vestibule {vestibule_id} requires an existing radiopharmacy_object_id: {radiopharmacy_object_id} not found")
    if connected_mrt_segment_id not in registry.objects:
        raise ValueError(f"vestibule {vestibule_id} requires an existing connected_mrt_segment_id: {connected_mrt_segment_id} not found")
    obj = CanonicalSpatialObject(
        mrtway_object_id=vestibule_id, object_type="MRT_VESTIBULE", facility_id=facility_id, building_id=None,
        floor_id=None, space_id=None, parent_object_id=radiopharmacy_object_id, transform=Transform(),
        geometry_reference=None, coordinate_system="LOCAL_BUILDING", asset_status=asset_status,
        operational_state="AVAILABLE", spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def vestibule_new_study_capex(economics: VestibuleEconomics, *, asset_status: AssetStatus, study_scope: Literal["OPERATIONAL_ONLY", "CAPITAL_PLANNING"]) -> float | Literal["NOT_CALIBRATED"]:
    if study_scope == "OPERATIONAL_ONLY" or asset_status != "PROPOSED":
        return 0.0
    return economics.total_capex()


def mrt_segment_length_capex(*, length_m: float, unit_cost_per_length: float) -> float:
    """Section 17: ordinary conduit CapEx = length x unit_cost -- never the
    vestibule treatment."""
    return length_m * unit_cost_per_length


# ---------------------------------------------------------------------------
# Connectivity graph / mode-specific routing (sections 18-24)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpatialEdge:
    edge_id: str
    from_object_id: str
    to_object_id: str
    length_m: float | Literal["NOT_CALIBRATED"]
    compatible_modes: frozenset[TransportMode]
    vertical: bool = False


@dataclass
class ConnectivityGraph:
    """Section 18-19: platform-neutral graph -- edges carry explicit mode
    compatibility, never one flattened edge type for every transport mode."""

    edges: list[SpatialEdge] = field(default_factory=list)

    def add_edge(self, edge: SpatialEdge) -> None:
        self.edges.append(edge)

    def edges_for_mode(self, mode: TransportMode) -> tuple[SpatialEdge, ...]:
        return tuple(e for e in self.edges if mode in e.compatible_modes)


@dataclass(frozen=True)
class RouteResult:
    origin_object_id: str
    destination_object_id: str
    mode: TransportMode
    path_edge_ids: tuple[str, ...]
    distance_m: float | Literal["NOT_CALIBRATED"]
    calibration_status: Literal["CALIBRATED", "ROUTE_NOT_CALIBRATED"]


def resolve_route(graph: ConnectivityGraph, *, origin_object_id: str, destination_object_id: str, mode: TransportMode) -> RouteResult:
    """Section 71-73: BFS over ONLY the mode-compatible subgraph -- never
    routes a mode across an incompatible edge (e.g. PTS along a normal
    pedestrian corridor, AGV along a non-AGV-compatible corridor)."""
    mode_edges = graph.edges_for_mode(mode)
    adjacency: dict[str, list[SpatialEdge]] = {}
    for e in mode_edges:
        adjacency.setdefault(e.from_object_id, []).append(e)
        adjacency.setdefault(e.to_object_id, []).append(e)

    if origin_object_id == destination_object_id:
        return RouteResult(origin_object_id=origin_object_id, destination_object_id=destination_object_id, mode=mode, path_edge_ids=(), distance_m=0.0, calibration_status="CALIBRATED")

    visited = {origin_object_id}
    queue: list[tuple[str, tuple[str, ...], float]] = [(origin_object_id, (), 0.0)]
    calibrated_total = True
    while queue:
        node, path, dist = queue.pop(0)
        for e in adjacency.get(node, ()):
            other = e.to_object_id if e.from_object_id == node else e.from_object_id
            if other in visited:
                continue
            edge_len = e.length_m if e.length_m != "NOT_CALIBRATED" else 0.0
            if e.length_m == "NOT_CALIBRATED":
                calibrated_total = False
            new_path = path + (e.edge_id,)
            if other == destination_object_id:
                return RouteResult(
                    origin_object_id=origin_object_id, destination_object_id=destination_object_id, mode=mode,
                    path_edge_ids=new_path, distance_m=(dist + edge_len) if calibrated_total else "NOT_CALIBRATED",
                    calibration_status="CALIBRATED" if calibrated_total else "ROUTE_NOT_CALIBRATED",
                )
            visited.add(other)
            queue.append((other, new_path, dist + edge_len))
    return RouteResult(origin_object_id=origin_object_id, destination_object_id=destination_object_id, mode=mode, path_edge_ids=(), distance_m="NOT_CALIBRATED", calibration_status="ROUTE_NOT_CALIBRATED")


# ---------------------------------------------------------------------------
# Canonical patient spatial resolution + nuclear trace resync (sections 25-28)
# -- never redesigns patient identity or nuclear physics.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PatientSpatialResolution:
    patient_id: str
    resolved_object_id: str | None
    spatial_status: SpatialStatus
    setting: Literal["INPATIENT", "OUTPATIENT"]


def resolve_patient_spatial_object(patient, registry: SpatialObjectRegistry) -> PatientSpatialResolution:
    """Section 25/28: connects `OncologyPatientRecord` (UNCHANGED) to a
    canonical spatial object where one exists for the patient's real
    room/outpatient origin -- never fabricates a room for an outpatient."""
    location_id = patient.room_id if patient.patient_type == "INPATIENT" else patient.outpatient_origin
    if location_id is not None and location_id in registry.objects:
        return PatientSpatialResolution(patient_id=patient.patient_id, resolved_object_id=location_id, spatial_status="CALIBRATED", setting=patient.patient_type)
    return PatientSpatialResolution(patient_id=patient.patient_id, resolved_object_id=None, spatial_status="LOCATION_NOT_CALIBRATED", setting=patient.patient_type)


@dataclass(frozen=True)
class NuclearTraceSpatialResync:
    """Section 26: canonical patient -> canonical room/object -> route
    authority -> transport time -- NEVER touches decay/qualification physics
    (those remain on `HybridPatientTrace`, unchanged)."""

    patient_id: str
    canonical_destination_object_id: str | None
    legacy_trace_destination_room_id: str
    resync_status: Literal["RESYNCED_TO_CANONICAL_LOCATION", "LEGACY_GEOMETRY_RETAINED"]


def resync_nuclear_trace_destination(trace, *, patient, registry: SpatialObjectRegistry) -> NuclearTraceSpatialResync:
    """Resolves (never mutates) the canonical spatial destination for a
    `HybridPatientTrace` (hybrid_optimization.py, UNCHANGED) whose
    `canonical_patient_id` has already been attached by the identity-
    unification adapter (prior build). Physics/decay/qualification on the
    trace itself are never touched here."""
    resolution = resolve_patient_spatial_object(patient, registry)
    status: Literal["RESYNCED_TO_CANONICAL_LOCATION", "LEGACY_GEOMETRY_RETAINED"] = (
        "RESYNCED_TO_CANONICAL_LOCATION" if resolution.resolved_object_id is not None else "LEGACY_GEOMETRY_RETAINED"
    )
    return NuclearTraceSpatialResync(
        patient_id=patient.patient_id, canonical_destination_object_id=resolution.resolved_object_id,
        legacy_trace_destination_room_id=trace.destination_room_id, resync_status=status,
    )


# ---------------------------------------------------------------------------
# Locked vs What-If spatial state + reversible changesets (sections 29-45)
# ---------------------------------------------------------------------------

ChangeOperation = Literal[
    "ADD_OBJECT", "REMOVE_OBJECT", "MOVE_OBJECT", "ROTATE_OBJECT", "COPY_OBJECT", "CHANGE_QUANTITY",
    "EXTEND_SEGMENT", "SHORTEN_SEGMENT", "RECONNECT_OBJECT",
]

CapexImpact = Literal["NONE", "NEW_CAPEX", "REDUCED_CAPEX", "NOT_CALIBRATED"]
OpexImpact = Literal["NONE", "INCREASED_OPEX", "REDUCED_OPEX", "NOT_CALIBRATED"]


@dataclass(frozen=True)
class SpatialChangeSet:
    """Section 31/40: a single reversible change. `previous_object`/`new_object`
    let undo/reset be exact restorations, never re-derivations."""

    change_id: str
    operation: ChangeOperation
    object_id: str
    previous_object: CanonicalSpatialObject | None
    new_object: CanonicalSpatialObject | None
    capex_impact: CapexImpact = "NOT_CALIBRATED"
    opex_impact: OpexImpact = "NOT_CALIBRATED"
    note: str = ""


@dataclass(frozen=True)
class LockedSpatialState:
    """Section 29: the project-truth registry. NEVER mutated by what-if
    operations (section 32)."""

    registry: SpatialObjectRegistry


@dataclass
class WhatIfSpatialState:
    """Section 30/44: a working clone with an ordered, reversible changeset
    history. `promoted` guards accidental treatment of what-if edits as
    project truth (section 45: promotion is explicit, never automatic)."""

    base: LockedSpatialState
    registry: SpatialObjectRegistry
    history: list[SpatialChangeSet] = field(default_factory=list)
    promoted: bool = False

    @staticmethod
    def branch_from(locked: LockedSpatialState) -> "WhatIfSpatialState":
        cloned = SpatialObjectRegistry(objects=dict(locked.registry.objects))
        return WhatIfSpatialState(base=locked, registry=cloned)

    def reset_to_locked(self) -> None:
        self.registry = SpatialObjectRegistry(objects=dict(self.base.registry.objects))
        self.history = []
        self.promoted = False

    def undo_last_change(self) -> SpatialChangeSet | None:
        if not self.history:
            return None
        last = self.history.pop()
        if last.previous_object is not None:
            self.registry.objects[last.object_id] = last.previous_object
        else:
            self.registry.objects.pop(last.object_id, None)
        return last


def _impact_hooks_for(operation: ChangeOperation) -> tuple[CapexImpact, OpexImpact]:
    """Section 42-43: move/add/rotate/stretch operations may ALL carry BOTH
    CapEx AND OPEX consequences -- deliberately NOT a rigid
    "MOVE=OPEX-only"/"ADD=CapEx-only" table. Every mapping below is a
    controlled assumption pending real cost-estimation reuse per
    operation -- reported as NOT_CALIBRATED where no existing authority
    applies directly.

    CLOSURE BUILD section 64-65: `ROTATE_OBJECT` here means an
    ENGINEERING_OBJECT_ROTATION applied to `WHAT_IF_SPATIAL_STATE` (not a
    3D camera orbit -- see `apply_camera_rotation`, which is unconditionally
    zero-impact and never goes through this changeset path at all). Rotating
    an engineering object MAY affect fit/clearance/connectivity/route
    geometry, so it is intentionally NOT hard-coded to ("NONE", "NONE")."""
    mapping: dict[ChangeOperation, tuple[CapexImpact, OpexImpact]] = {
        "ADD_OBJECT": ("NEW_CAPEX", "NOT_CALIBRATED"),
        "REMOVE_OBJECT": ("REDUCED_CAPEX", "REDUCED_OPEX"),
        "MOVE_OBJECT": ("NOT_CALIBRATED", "NOT_CALIBRATED"),
        "ROTATE_OBJECT": ("NOT_CALIBRATED", "NOT_CALIBRATED"),
        "COPY_OBJECT": ("NEW_CAPEX", "NOT_CALIBRATED"),
        "CHANGE_QUANTITY": ("NOT_CALIBRATED", "NOT_CALIBRATED"),
        "EXTEND_SEGMENT": ("NEW_CAPEX", "NOT_CALIBRATED"),
        "SHORTEN_SEGMENT": ("REDUCED_CAPEX", "NOT_CALIBRATED"),
        "RECONNECT_OBJECT": ("NOT_CALIBRATED", "NOT_CALIBRATED"),
    }
    return mapping[operation]


def apply_changeset(
    state: WhatIfSpatialState, *, change_id: str, operation: ChangeOperation, object_id: str,
    new_object: CanonicalSpatialObject | None, note: str = "",
) -> SpatialChangeSet:
    """Section 32-39: never mutates `state.base` (the locked state) -- only
    `state.registry` (the what-if clone)."""
    previous = state.registry.objects.get(object_id)
    capex_impact, opex_impact = _impact_hooks_for(operation)
    changeset = SpatialChangeSet(
        change_id=change_id, operation=operation, object_id=object_id, previous_object=previous,
        new_object=new_object, capex_impact=capex_impact, opex_impact=opex_impact, note=note,
    )
    if operation == "REMOVE_OBJECT":
        state.registry.objects.pop(object_id, None)
    elif new_object is not None:
        state.registry.objects[object_id] = new_object
    state.history.append(changeset)
    return changeset


@dataclass(frozen=True)
class SpatialDelta:
    added_object_ids: tuple[str, ...]
    removed_object_ids: tuple[str, ...]
    modified_object_ids: tuple[str, ...]


def compute_delta(locked: LockedSpatialState, what_if: WhatIfSpatialState) -> SpatialDelta:
    """Section 46: locked-vs-what-if comparison contract (no UI)."""
    locked_ids = set(locked.registry.objects.keys())
    whatif_ids = set(what_if.registry.objects.keys())
    added = tuple(sorted(whatif_ids - locked_ids))
    removed = tuple(sorted(locked_ids - whatif_ids))
    modified = tuple(sorted(
        oid for oid in (locked_ids & whatif_ids)
        if locked.registry.objects[oid] != what_if.registry.objects[oid]
    ))
    return SpatialDelta(added_object_ids=added, removed_object_ids=removed, modified_object_ids=modified)


def promote_what_if_to_simulation_input(state: WhatIfSpatialState) -> LockedSpatialState:
    """Section 45: promotion is an explicit, separate action -- what-if
    state never automatically becomes project truth."""
    state.promoted = True
    return LockedSpatialState(registry=SpatialObjectRegistry(objects=dict(state.registry.objects)))


# ---------------------------------------------------------------------------
# Object-inspector data contract (section 47-48, no UI)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObjectInspectorRecord:
    mrtway_object_id: str
    object_type: SpatialObjectType
    facility_id: str
    building_id: str | None
    floor_id: str | None
    space_id: str | None
    parent_object_id: str | None
    transform: Transform
    coordinate_system: CoordinateSystem
    asset_status: AssetStatus
    operational_state: OperationalState
    spatial_status: SpatialStatus
    provenance: Provenance
    external_reference: ExternalReference
    engineering_object_id: str | None


def build_object_inspector_record(obj: CanonicalSpatialObject) -> ObjectInspectorRecord:
    return ObjectInspectorRecord(
        mrtway_object_id=obj.mrtway_object_id, object_type=obj.object_type, facility_id=obj.facility_id,
        building_id=obj.building_id, floor_id=obj.floor_id, space_id=obj.space_id,
        parent_object_id=obj.parent_object_id, transform=obj.transform, coordinate_system=obj.coordinate_system,
        asset_status=obj.asset_status, operational_state=obj.operational_state, spatial_status=obj.spatial_status,
        provenance=obj.provenance, external_reference=obj.external_reference,
        engineering_object_id=obj.engineering_object_id,
    )


# ---------------------------------------------------------------------------
# Platform-neutral spatial adapter interface (sections 49-55) -- prepares,
# does NOT implement, OpenUSD/Omniverse/iTwin/native-viewer readiness.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SceneLoadResult:
    registry: SpatialObjectRegistry
    objects_loaded: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SceneExportResult:
    format_hint: Literal["USD", "IFC", "ITWIN", "NATIVE_JSON"]
    object_count: int
    payload: dict


class SpatialAdapterInterface:
    """Section 49-50: the contract every platform-specific adapter (OpenUSD,
    Omniverse, iTwin, native viewer) will implement in a FUTURE build. No
    concrete platform adapter is implemented here -- only the interface and
    a NATIVE_JSON reference implementation to prove the contract is usable."""

    def load_scene(self, source: object) -> SceneLoadResult:  # pragma: no cover - interface only
        raise NotImplementedError

    def export_scene(self, registry: SpatialObjectRegistry) -> SceneExportResult:  # pragma: no cover
        raise NotImplementedError

    def map_external_object(self, obj: CanonicalSpatialObject, external_ref: ExternalReference) -> CanonicalSpatialObject:  # pragma: no cover
        raise NotImplementedError

    def read_transform(self, obj: CanonicalSpatialObject) -> Transform:  # pragma: no cover
        raise NotImplementedError

    def write_transform(self, obj: CanonicalSpatialObject, transform: Transform) -> CanonicalSpatialObject:  # pragma: no cover
        raise NotImplementedError

    def resolve_selection(self, registry: SpatialObjectRegistry, external_id: str, external_id_kind: str) -> CanonicalSpatialObject | None:  # pragma: no cover
        raise NotImplementedError


class NativeJsonSpatialAdapter(SpatialAdapterInterface):
    """Section 51: reference implementation proving the adapter contract
    round-trips without any external platform dependency. This is the ONLY
    adapter implemented in this build -- OpenUSD/Omniverse/iTwin adapters
    are explicitly deferred to the next build."""

    def load_scene(self, source: object) -> SceneLoadResult:
        payload = source if isinstance(source, dict) else json.loads(str(source))
        registry = SpatialObjectRegistry()
        warnings: list[str] = []
        for raw in payload.get("objects", []):
            try:
                registry.add(_object_from_dict(raw))
            except Exception as exc:  # defensive: malformed import row, never crash the whole scene load
                warnings.append(f"skipped object during load: {exc}")
        return SceneLoadResult(registry=registry, objects_loaded=len(registry.objects), warnings=tuple(warnings))

    def export_scene(self, registry: SpatialObjectRegistry) -> SceneExportResult:
        payload = {"objects": [_object_to_dict(o) for o in registry.objects.values()]}
        return SceneExportResult(format_hint="NATIVE_JSON", object_count=len(registry.objects), payload=payload)

    def map_external_object(self, obj: CanonicalSpatialObject, external_ref: ExternalReference) -> CanonicalSpatialObject:
        return replace(obj, external_reference=external_ref)

    def read_transform(self, obj: CanonicalSpatialObject) -> Transform:
        return obj.transform

    def write_transform(self, obj: CanonicalSpatialObject, transform: Transform) -> CanonicalSpatialObject:
        return replace(obj, transform=transform)

    def resolve_selection(self, registry: SpatialObjectRegistry, external_id: str, external_id_kind: str) -> CanonicalSpatialObject | None:
        for obj in registry.objects.values():
            if getattr(obj.external_reference, external_id_kind, None) == external_id:
                return obj
        return None


def resolve_usd_prim_path(obj: CanonicalSpatialObject) -> str:
    """Section 53: deterministic, stable USD prim path derivation -- for the
    NEXT build's OpenUSD adapter to consume. Path derivation only; does not
    write/open any USD stage."""
    parts = [p for p in (obj.facility_id, obj.building_id, obj.floor_id, obj.mrtway_object_id) if p]
    return "/" + "/".join(parts)


# ---------------------------------------------------------------------------
# Validation (section 56-60) -- reuses the repo's existing
# validation-authority pattern (raise/report structured issues, never
# silent failure).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpatialValidationIssue:
    issue_type: str
    object_id: str
    detail: str


def validate_spatial_registry(registry: SpatialObjectRegistry, *, graph: "ConnectivityGraph | None" = None) -> tuple[SpatialValidationIssue, ...]:
    issues: list[SpatialValidationIssue] = []
    seen_external: dict[tuple[str, str], str] = {}
    seen_container_engineering_ids: dict[str, str] = {}

    graph_object_ids: set[str] = set()
    if graph is not None:
        for e in graph.edges:
            graph_object_ids.add(e.from_object_id)
            graph_object_ids.add(e.to_object_id)
            if e.from_object_id not in registry.objects or e.to_object_id not in registry.objects:
                issues.append(SpatialValidationIssue("BROKEN_GRAPH_CONNECTION", e.edge_id, f"edge references missing object(s): {e.from_object_id} / {e.to_object_id}"))

    for obj in registry.objects.values():
        if obj.parent_object_id is not None and obj.parent_object_id not in registry.objects:
            issue_type = {"MRT_BRANCH": "ORPHAN_MRT_BRANCH", "MRT_TRUNK": "ORPHAN_MRT_TRUNK"}.get(obj.object_type, "ORPHAN_HIERARCHY")
            issues.append(SpatialValidationIssue(issue_type, obj.mrtway_object_id, f"parent_object_id {obj.parent_object_id} not found"))
        if obj.coordinate_system is None:
            issues.append(SpatialValidationIssue("MISSING_COORDINATE_SYSTEM", obj.mrtway_object_id, "coordinate_system not set"))

        ext = obj.external_reference
        for field_name in ("ifc_guid", "revit_element_id", "itwin_element_id", "usd_prim_path", "cad_entity_id", "source_document_id"):
            value = getattr(ext, field_name)
            if value is None:
                continue
            key = (field_name, value)
            if key in seen_external:
                issues.append(SpatialValidationIssue("EXTERNAL_MAPPING_COLLISION", obj.mrtway_object_id, f"{field_name}={value} already mapped to {seen_external[key]}"))
            else:
                seen_external[key] = obj.mrtway_object_id

    for seg in registry.by_type("MRT_SEGMENT"):
        if "LENGTH:NOT_CALIBRATED" == seg.geometry_reference:
            issues.append(SpatialValidationIssue("MRT_SEGMENT_GEOMETRY_NOT_CALIBRATED", seg.mrtway_object_id, "segment length not calibrated"))

    for vestibule in registry.by_type("MRT_VESTIBULE"):
        if vestibule.parent_object_id is None or vestibule.parent_object_id not in registry.objects:
            issues.append(SpatialValidationIssue("VESTIBULE_MISSING_RADIOPHARMACY_REFERENCE", vestibule.mrtway_object_id, "vestibule has no valid radiopharmacy parent reference"))
        if vestibule.engineering_object_id is not None and vestibule.engineering_object_id not in registry.objects:
            issues.append(SpatialValidationIssue("VESTIBULE_INVALID_MRT_NETWORK_REFERENCE", vestibule.mrtway_object_id, f"engineering_object_id (MRT network reference) {vestibule.engineering_object_id} not found"))

    if graph is not None:
        for junction in registry.by_type("MRT_JUNCTION"):
            if junction.mrtway_object_id not in graph_object_ids:
                issues.append(SpatialValidationIssue("JUNCTION_WITHOUT_CONNECTED_EDGES", junction.mrtway_object_id, "junction has no connected MRT edges in the supplied graph"))
        for endpoint in registry.by_type("MRT_ENDPOINT"):
            if endpoint.mrtway_object_id not in graph_object_ids:
                issues.append(SpatialValidationIssue("ENDPOINT_WITHOUT_NETWORK_CONNECTION", endpoint.mrtway_object_id, "endpoint has no connected MRT edges in the supplied graph"))

    for carrier in registry.by_type("MRT_CARRIER"):
        if carrier.parent_object_id is not None and carrier.parent_object_id not in registry.objects:
            issues.append(SpatialValidationIssue("CARRIER_INVALID_NETWORK_REFERENCE", carrier.mrtway_object_id, f"parent_object_id (network reference) {carrier.parent_object_id} not found"))

    for container in registry.by_type("MRT_CONTAINER"):
        if container.engineering_object_id not in KNOWN_MRT_CONTAINER_CLASS_IDS:
            issues.append(SpatialValidationIssue("CONTAINER_INVALID_CLASS_RELATIONSHIP", container.mrtway_object_id, f"engineering_object_id (container class) {container.engineering_object_id!r} is not a recognized MRT payload-container class"))
        if container.engineering_object_id in seen_container_engineering_ids:
            pass  # multiple containers of the same class are expected/normal -- not a collision
        seen_container_engineering_ids[container.mrtway_object_id] = container.engineering_object_id or ""

    return tuple(issues)


def validate_no_duplicate_object_ids(registry: SpatialObjectRegistry) -> bool:
    """Duplicate IDs cannot occur post-`SpatialObjectRegistry.add` (it raises
    at insert time) -- this function documents/reconfirms that invariant for
    callers who build a registry via `_object_from_dict` bulk import."""
    ids = [o.mrtway_object_id for o in registry.objects.values()]
    return len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Serialization (sections 61-64) -- reuses the repo's plain
# dataclass-to-dict pattern, never a bespoke schema per object type.
# ---------------------------------------------------------------------------


def _object_to_dict(obj: CanonicalSpatialObject) -> dict:
    d = asdict(obj)
    d["_serialized_at"] = datetime.now(timezone.utc).isoformat()
    return d


def _object_from_dict(raw: dict) -> CanonicalSpatialObject:
    raw = dict(raw)
    raw.pop("_serialized_at", None)
    transform = Transform(**raw.pop("transform"))
    external_reference = ExternalReference(**raw.pop("external_reference", {}) or {})
    dimensions = EngineeringEnvelope(**raw.pop("dimensions", {}) or {})
    return CanonicalSpatialObject(transform=transform, external_reference=external_reference, dimensions=dimensions, **raw)


def registry_to_json(registry: SpatialObjectRegistry) -> str:
    return json.dumps({"objects": [_object_to_dict(o) for o in registry.objects.values()]}, sort_keys=True)


def registry_from_json(payload: str) -> SpatialObjectRegistry:
    data = json.loads(payload)
    registry = SpatialObjectRegistry()
    for raw in data.get("objects", []):
        registry.add(_object_from_dict(raw))
    return registry


# ============================================================================
# CLOSURE BUILD: MRT ECONOMIC RECONCILIATION (sections 3-14, 79-88)
#
# GOVERNANCE: this section audits and REUSES `models.PlannerAssumptions`
# (the existing MRT economic authority) -- it never redeclares guideway or
# carrier unit costs as new constants. Only vestibule/controls/installation
# (concepts with NO prior authority anywhere in the repo) become new
# constants here, and each is explicitly labeled
# USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION per the user's instruction --
# never LITERATURE_CALIBRATED/MANUFACTURER_CALIBRATED/MARKET_CALIBRATED.
# ============================================================================

MRT_VESTIBULE_CAPEX_USD = 30_000.0
"""USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION -- per vestibule, vestibule-specific only (section 4-5)."""

MRT_CONTROLS_CAPEX_USD = 100_000.0
"""USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION -- charged ONCE per relevant MRT system/network (section 4/6)."""

MRT_INSTALLATION_COMMISSIONING_CAPEX_USD = 300_000.0
"""USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION -- charged ONCE per relevant MRT installation/project (section 4/7)."""

KNOWN_MRT_CONTAINER_CLASS_IDS = frozenset({
    "NUCLEAR_SHIELDED_CONTAINER", "CLINICAL_CLEAN_CONTAINER", "LINEN_CONTAINER", "SPECIMEN_BLOOD_CONTAINER",
})
"""Reuses `shared_mrt_multistream_authority`'s existing container-class identities -- never a second taxonomy."""


@dataclass(frozen=True)
class MrtEconomicAuditEntry:
    component: str
    file: str
    authority: str
    value: str
    provenance: str
    actively_used: bool


def audit_mrt_economic_authority() -> tuple[MrtEconomicAuditEntry, ...]:
    """Section 3: the audit REQUIRED before any value change. Reads current
    values directly from `models.PlannerAssumptions` (never re-declares
    them) so this table can never silently drift from the real authority."""
    from models import PlannerAssumptions

    a = PlannerAssumptions()
    return (
        MrtEconomicAuditEntry(
            "Guideway/conduit unit cost", "models.py", "PlannerAssumptions.mrt_guideway_capex_per_m",
            f"${a.mrt_guideway_capex_per_m:,.0f}/m",
            "PROJECT_PLANNING_ASSUMPTION (existing repo default). CONFLICT FOUND: this does NOT match the "
            "user's recollection of $6,000/m -- no $6,000/m value exists anywhere in the repository. Used as "
            "the fallback in infrastructure_capex.py whenever a scenario's own guideway_capex_per_m input is 0.",
            True,
        ),
        MrtEconomicAuditEntry(
            "Guideway per-scenario override (test fixtures)", "many test_*.py files (e.g. test_cyclotron_fleet_recommendation.py)",
            "InfrastructureCapexInputs.guideway_capex_per_m / NativeMrtPathwayScenario", "$12,000/m (most native decision-pipeline fixtures)",
            "TEST_SCENARIO_OVERRIDE -- a legitimate per-scenario CapEx input field, NOT a second competing "
            "global constant; each fixture supplies its own override and falls back to "
            "PlannerAssumptions.mrt_guideway_capex_per_m only when left at 0.0.",
            True,
        ),
        MrtEconomicAuditEntry(
            "Guideway example in the prior spatial-build's report", "prior build's interactive smoke-test only",
            "N/A (report table example, never a module constant)", "$100/m",
            "TEST_EXAMPLE_ONLY -- an ad hoc argument to the generic mrt_segment_length_capex(length_m, "
            "unit_cost_per_length) helper during smoke-testing; never stored in canonical_spatial_authority.py "
            "and never reused as production economics.",
            False,
        ),
        MrtEconomicAuditEntry(
            "Carrier unit cost", "models.py", "PlannerAssumptions.mrt_carrier_capex_per_installed_unit",
            f"${a.mrt_carrier_capex_per_installed_unit:,.0f}/carrier",
            "PROJECT_PLANNING_ASSUMPTION (existing) -- MATCHES the user's recalled $10,000/carrier exactly. "
            "No conflict; reused directly by compute_mrt_transport_only_capex(), never duplicated here.",
            True,
        ),
        MrtEconomicAuditEntry(
            "MRT endpoint (nuclear-trunk clinical room) unit cost", "models.py", "PlannerAssumptions.endpoint_capex",
            f"${a.endpoint_capex:,.0f}/endpoint",
            "PROJECT_PLANNING_ASSUMPTION (existing) -- scoped to nuclear-trunk MRT clinical-room endpoints in "
            "infrastructure_capex.py's 'MRT endpoints' ledger line. Generic campus MRT_JUNCTION/MRT_ENDPOINT "
            "spatial objects introduced by this build are a DIFFERENT granularity (arbitrary network nodes, not "
            "necessarily clinical rooms) and have NO calibrated value of their own -- reported as "
            "NOT_CALIBRATED by compute_mrt_transport_only_capex() unless the caller explicitly supplies one.",
            True,
        ),
        MrtEconomicAuditEntry(
            "MRT base infrastructure (flat)", "models.py", "PlannerAssumptions.mrt_infrastructure_capex",
            f"${a.mrt_infrastructure_capex:,.0f}",
            "PROJECT_PLANNING_ASSUMPTION (existing) -- a flat nuclear-trunk MRT base-infrastructure cost line, "
            "conceptually distinct from this build's new controls/installation figures. Not touched.",
            True,
        ),
        MrtEconomicAuditEntry(
            "Vestibule CapEx (PRIOR spatial-build value, superseded)", "canonical_spatial_authority.py (prior build)",
            "CONTROLLED_VESTIBULE_ECONOMICS (pre-closure)", "$43,000 (base $25,000 + install $10,000 + integration $8,000)",
            "SUPERSEDED_THIS_BUILD -- conflicted with the user-supplied $30,000 vestibule assumption and folded "
            "system-level installation/integration cost into a per-vestibule charge.",
            False,
        ),
        MrtEconomicAuditEntry(
            "Vestibule CapEx (this build)", "canonical_spatial_authority.py",
            "MRT_VESTIBULE_CAPEX_USD / CONTROLLED_VESTIBULE_ECONOMICS.total_capex()",
            f"${MRT_VESTIBULE_CAPEX_USD:,.0f}/vestibule", "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION", True,
        ),
        MrtEconomicAuditEntry(
            "MRT controls (system/network-level, once)", "canonical_spatial_authority.py", "MRT_CONTROLS_CAPEX_USD",
            f"${MRT_CONTROLS_CAPEX_USD:,.0f} once per MRT system/network", "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION", True,
        ),
        MrtEconomicAuditEntry(
            "MRT installation/commissioning (project-level, once)", "canonical_spatial_authority.py",
            "MRT_INSTALLATION_COMMISSIONING_CAPEX_USD", f"${MRT_INSTALLATION_COMMISSIONING_CAPEX_USD:,.0f} once per MRT installation/project",
            "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION", True,
        ),
        MrtEconomicAuditEntry(
            "Generic campus endpoint/junction economics (new spatial objects)", "canonical_spatial_authority.py",
            "N/A", "NOT_CALIBRATED",
            "No controlled or calibrated value exists for generic MRT_JUNCTION/MRT_ENDPOINT campus spatial "
            "objects; spatial existence does not require fabricated economics (section 10).",
            False,
        ),
        MrtEconomicAuditEntry(
            "MRT carrier maintenance/electricity OPEX (per unit-year)", "models.py",
            "PlannerAssumptions.mrt_carrier_maintenance_opex_per_installed_unit_year / "
            "...allocated_electricity_opex_per_operated_unit_year",
            f"${a.mrt_carrier_maintenance_opex_per_installed_unit_year:,.0f} / ${a.mrt_carrier_allocated_electricity_opex_per_operated_unit_year:,.0f}",
            "PROJECT_PLANNING_ASSUMPTION (existing) -- unchanged, reused directly, never duplicated.", True,
        ),
        MrtEconomicAuditEntry(
            "Guideway maintenance OPEX (fraction of CapEx/year)", "models.py",
            "PlannerAssumptions.mrt_guideway_maintenance_fraction_of_capex_per_year", f"{a.mrt_guideway_maintenance_fraction_of_capex_per_year:.0%}/year",
            "PROJECT_PLANNING_ASSUMPTION (existing) -- unchanged, reused directly.", True,
        ),
        MrtEconomicAuditEntry(
            "Nuclear-shielded MRT container CapEx", "shared_mrt_multistream_authority.py", "DEFAULT_NUCLEAR_SHIELDED_CONTAINER.unit_capex",
            "ALREADY_INCLUDED_IN_EXISTING_MRT_CARRIER_AUTHORITY",
            "Explicitly marked as already counted inside the carrier/endpoint/base-infrastructure CapEx above -- "
            "never a second, duplicated cost line (existing authority, unchanged by this build).", True,
        ),
    )


EconomicCategory = Literal[
    "COMMON_CLINICAL_NUCLEAR_BASELINE", "ARCHITECTURE_SPECIFIC_TRANSPORT",
    "ARCHITECTURE_SPECIFIC_FACILITY_INTERVENTION", "NOT_CALIBRATED",
]


@dataclass(frozen=True)
class MrtTransportCapexLineItem:
    component: str
    quantity: float
    unit: str
    unit_cost: float | Literal["NOT_CALIBRATED"]
    capex: float | Literal["NOT_CALIBRATED"]
    economic_category: EconomicCategory
    provenance: str


@dataclass(frozen=True)
class MrtTransportOnlyCapexResult:
    line_items: tuple[MrtTransportCapexLineItem, ...]
    total_capex: float

    def line_item(self, component: str) -> MrtTransportCapexLineItem | None:
        return next((li for li in self.line_items if li.component == component), None)


def compute_mrt_transport_only_capex(
    *, guideway_length_m: float = 0.0, guideway_unit_cost_per_m: float | None = None,
    carrier_count: int = 0, carrier_unit_cost: float | None = None,
    vestibule_count: int = 0, vestibule_unit_cost: float = MRT_VESTIBULE_CAPEX_USD,
    endpoint_count: int = 0, endpoint_unit_cost: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED",
    include_controls: bool = False, include_installation_commissioning: bool = False,
) -> MrtTransportOnlyCapexResult:
    """Section 11/79-88: MRT_TRANSPORT_ONLY_CAPEX = guideway + carriers +
    vestibules + endpoints (where priced) + controls + installation --
    EXCLUDING common clinical/nuclear assets (cyclotron/generator/scanners/
    radiopharmacy clinical equipment/patient rooms/common construction), per
    section 11-12. Controls and installation/commissioning are boolean flags
    charged EXACTLY ONCE regardless of guideway length, carrier count,
    vestibule count, endpoint count, or building count (sections 6-7, 83-84).
    Guideway/carrier unit costs default to the EXISTING `models.PlannerAssumptions`
    authority -- never a second, duplicated economic model."""
    from models import PlannerAssumptions

    a = PlannerAssumptions()
    resolved_guideway_unit_cost = guideway_unit_cost_per_m if guideway_unit_cost_per_m is not None else a.mrt_guideway_capex_per_m
    resolved_carrier_unit_cost = carrier_unit_cost if carrier_unit_cost is not None else a.mrt_carrier_capex_per_installed_unit
    endpoint_capex: float | Literal["NOT_CALIBRATED"] = (endpoint_count * endpoint_unit_cost) if endpoint_unit_cost != "NOT_CALIBRATED" else "NOT_CALIBRATED"

    items: tuple[MrtTransportCapexLineItem, ...] = (
        MrtTransportCapexLineItem(
            "MRT guideway/trunk/branch/segment", guideway_length_m, "meters", resolved_guideway_unit_cost,
            guideway_length_m * resolved_guideway_unit_cost, "ARCHITECTURE_SPECIFIC_TRANSPORT",
            "models.PlannerAssumptions.mrt_guideway_capex_per_m (existing authority)" if guideway_unit_cost_per_m is None else "CALLER_SUPPLIED_UNIT_COST",
        ),
        MrtTransportCapexLineItem(
            "MRT carriers", carrier_count, "carriers", resolved_carrier_unit_cost,
            carrier_count * resolved_carrier_unit_cost, "ARCHITECTURE_SPECIFIC_TRANSPORT",
            "models.PlannerAssumptions.mrt_carrier_capex_per_installed_unit (existing authority)" if carrier_unit_cost is None else "CALLER_SUPPLIED_UNIT_COST",
        ),
        MrtTransportCapexLineItem(
            "MRT vestibules", vestibule_count, "vestibules", vestibule_unit_cost,
            vestibule_count * vestibule_unit_cost, "ARCHITECTURE_SPECIFIC_TRANSPORT",
            "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION (MRT_VESTIBULE_CAPEX_USD)",
        ),
        MrtTransportCapexLineItem(
            "MRT endpoints/junctions", endpoint_count, "endpoints", endpoint_unit_cost, endpoint_capex,
            "ARCHITECTURE_SPECIFIC_TRANSPORT" if endpoint_unit_cost != "NOT_CALIBRATED" else "NOT_CALIBRATED",
            "NOT_CALIBRATED -- no controlled/calibrated generic endpoint value exists" if endpoint_unit_cost == "NOT_CALIBRATED" else "CALLER_SUPPLIED_UNIT_COST",
        ),
        MrtTransportCapexLineItem(
            "MRT controls (system/network, once)", 1.0 if include_controls else 0.0, "system", MRT_CONTROLS_CAPEX_USD,
            MRT_CONTROLS_CAPEX_USD if include_controls else 0.0, "ARCHITECTURE_SPECIFIC_TRANSPORT",
            "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION (MRT_CONTROLS_CAPEX_USD, charged once, never multiplied)",
        ),
        MrtTransportCapexLineItem(
            "MRT installation/commissioning (project, once)", 1.0 if include_installation_commissioning else 0.0, "project",
            MRT_INSTALLATION_COMMISSIONING_CAPEX_USD, MRT_INSTALLATION_COMMISSIONING_CAPEX_USD if include_installation_commissioning else 0.0,
            "ARCHITECTURE_SPECIFIC_TRANSPORT",
            "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION (MRT_INSTALLATION_COMMISSIONING_CAPEX_USD, charged once, never multiplied)",
        ),
    )
    total = sum(li.capex for li in items if li.capex != "NOT_CALIBRATED")  # NOT_CALIBRATED lines excluded, never fabricated
    return MrtTransportOnlyCapexResult(line_items=items, total_capex=float(total))


CommonOrArchitectureSpecific = Literal[
    "COMMON_CLINICAL_NUCLEAR_BASELINE", "ARCHITECTURE_SPECIFIC_TRANSPORT_CAPEX",
    "ARCHITECTURE_SPECIFIC_FACILITY_INTERVENTION", "NOT_CALIBRATED",
]


@dataclass(frozen=True)
class CommonCostClassification:
    asset: str
    category: CommonOrArchitectureSpecific
    included_in_mrt_transport_only_capex: bool
    note: str


def classify_common_vs_architecture_specific_costs() -> tuple[CommonCostClassification, ...]:
    """Section 12/86-88: COMMON_CLINICAL_NUCLEAR_BASELINE vs
    ARCHITECTURE_SPECIFIC_TRANSPORT_CAPEX categorization -- required so
    Manual/Automated/Hybrid/MRT-Dominant can be compared on the same basis
    (never whole-MRT-project cost vs AGV/PTS subsystem cost, section 12)."""
    return (
        CommonCostClassification("Cyclotron (CY-*)", "COMMON_CLINICAL_NUCLEAR_BASELINE", False, "cyclotron_catalog.py/PlannerAssumptions.cyclotron_purchase_capex+installation_capex -- shared across all 4 architectures."),
        CommonCostClassification("Mo-99/Tc-99m generator (GEN-*)", "COMMON_CLINICAL_NUCLEAR_BASELINE", False, "generator_economics.py -- delivery-cadence OPEX, no durable CapEx; shared baseline."),
        CommonCostClassification("PET scanner", "COMMON_CLINICAL_NUCLEAR_BASELINE", False, "scanner_catalog.py/PlannerAssumptions.scanner_capex -- shared across all 4 architectures."),
        CommonCostClassification("SPECT scanner", "COMMON_CLINICAL_NUCLEAR_BASELINE", False, "scanner_catalog.py/PlannerAssumptions.scanner_capex -- shared across all 4 architectures."),
        CommonCostClassification("Radiopharmacy clinical equipment", "COMMON_CLINICAL_NUCLEAR_BASELINE", False, "Common clinical build-out, not transport-specific."),
        CommonCostClassification("Patient rooms / common hospital construction", "COMMON_CLINICAL_NUCLEAR_BASELINE", False, "Common facility construction, independent of transport architecture choice."),
        CommonCostClassification("MRT guideway/trunk/branch/segment", "ARCHITECTURE_SPECIFIC_TRANSPORT_CAPEX", True, "Exists only because MRT/Hybrid-MRT architecture was chosen."),
        CommonCostClassification("MRT carriers", "ARCHITECTURE_SPECIFIC_TRANSPORT_CAPEX", True, "MRT-specific movable asset."),
        CommonCostClassification("MRT vestibules", "ARCHITECTURE_SPECIFIC_TRANSPORT_CAPEX", True, "MRT-specific interface object."),
        CommonCostClassification("MRT controls", "ARCHITECTURE_SPECIFIC_TRANSPORT_CAPEX", True, "MRT-specific system, charged once."),
        CommonCostClassification("MRT installation/commissioning", "ARCHITECTURE_SPECIFIC_TRANSPORT_CAPEX", True, "MRT-specific project cost, charged once."),
        CommonCostClassification("AGV/PTS transport subsystem (Automated Conventional)", "ARCHITECTURE_SPECIFIC_TRANSPORT_CAPEX", False, "Owned by conventional_transport_authority.py -- comparable basis is its OWN transport-only subsystem CapEx, never compared against whole-MRT-project cost (section 12)."),
    )


# ============================================================================
# CLOSURE BUILD: COMPLETE FIRST-CLASS MRT SPATIAL BUILDERS (sections 15-21)
# ============================================================================


def build_mrt_trunk(
    registry: SpatialObjectRegistry, *, trunk_id: str, facility_id: str, network_id: str | None = None,
    length_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED", asset_status: AssetStatus = "PROPOSED",
    transform: Transform = Transform(),
) -> CanonicalSpatialObject:
    """Section 16: a trunk has stable identity, facility identity,
    parent/network identity, geometry reference/status, transform, asset
    status, operational state, provenance -- never merely a label."""
    resolved_network_id = network_id or facility_id
    if resolved_network_id not in registry.objects:
        raise ValueError(f"trunk {trunk_id} requires an existing network_id/facility_id: {resolved_network_id} not found")
    status: SpatialStatus = "CALIBRATED" if length_m != "NOT_CALIBRATED" else "GEOMETRY_NOT_CALIBRATED"
    obj = CanonicalSpatialObject(
        mrtway_object_id=trunk_id, object_type="MRT_TRUNK", facility_id=facility_id, building_id=None, floor_id=None,
        space_id=None, parent_object_id=resolved_network_id, transform=transform, geometry_reference=f"LENGTH:{length_m}",
        coordinate_system="PROJECT_GLOBAL", asset_status=asset_status, operational_state="AVAILABLE",
        spatial_status=status, provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def build_mrt_branch(
    registry: SpatialObjectRegistry, *, branch_id: str, facility_id: str, connects_to_object_id: str,
    length_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED", asset_status: AssetStatus = "PROPOSED",
    transform: Transform = Transform(),
) -> CanonicalSpatialObject:
    """Section 17: a branch must legitimately connect to a trunk, junction,
    segment, or endpoint -- orphan branches are rejected outright."""
    if connects_to_object_id not in registry.objects:
        raise ValueError(f"branch {branch_id} requires an existing connects_to_object_id: {connects_to_object_id} not found")
    parent = registry.get(connects_to_object_id)
    valid_parent_types: frozenset[SpatialObjectType] = frozenset({"MRT_TRUNK", "MRT_JUNCTION", "MRT_SEGMENT", "MRT_ENDPOINT"})
    if parent.object_type not in valid_parent_types:
        raise ValueError(f"branch {branch_id} must connect to one of {sorted(valid_parent_types)}, got {parent.object_type!r} ({connects_to_object_id})")
    status: SpatialStatus = "CALIBRATED" if length_m != "NOT_CALIBRATED" else "GEOMETRY_NOT_CALIBRATED"
    obj = CanonicalSpatialObject(
        mrtway_object_id=branch_id, object_type="MRT_BRANCH", facility_id=facility_id, building_id=None, floor_id=None,
        space_id=None, parent_object_id=connects_to_object_id, transform=transform, geometry_reference=f"LENGTH:{length_m}",
        coordinate_system="PROJECT_GLOBAL", asset_status=asset_status, operational_state="AVAILABLE",
        spatial_status=status, provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def build_mrt_junction(
    registry: SpatialObjectRegistry, *, junction_id: str, facility_id: str, asset_status: AssetStatus = "PROPOSED",
    transform: Transform = Transform(),
) -> CanonicalSpatialObject:
    """Section 18: junctions are pure connectivity nodes -- no CapEx is
    auto-assigned merely because a junction object exists (no economic
    authority exists for generic junctions; see NOT_CALIBRATED endpoint
    treatment in compute_mrt_transport_only_capex())."""
    obj = CanonicalSpatialObject(
        mrtway_object_id=junction_id, object_type="MRT_JUNCTION", facility_id=facility_id, building_id=None,
        floor_id=None, space_id=None, parent_object_id=(facility_id if facility_id in registry.objects else None),
        transform=transform, geometry_reference=None, coordinate_system="PROJECT_GLOBAL", asset_status=asset_status,
        operational_state="AVAILABLE", spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def build_mrt_endpoint(
    registry: SpatialObjectRegistry, *, endpoint_id: str, facility_id: str, connected_network_object_id: str,
    served_object_id: str | None = None, asset_status: AssetStatus = "PROPOSED", transform: Transform = Transform(),
) -> CanonicalSpatialObject:
    """Section 19: endpoints require a connected network object (no
    teleportation) and MAY reference a served spatial object/zone (e.g. a
    clinical room)."""
    if connected_network_object_id not in registry.objects:
        raise ValueError(f"endpoint {endpoint_id} requires an existing connected_network_object_id: {connected_network_object_id} not found")
    if served_object_id is not None and served_object_id not in registry.objects:
        raise ValueError(f"endpoint {endpoint_id} served_object_id {served_object_id} not found")
    served = registry.get(served_object_id) if served_object_id else None
    obj = CanonicalSpatialObject(
        mrtway_object_id=endpoint_id, object_type="MRT_ENDPOINT", facility_id=facility_id,
        building_id=(served.building_id if served else None), floor_id=(served.floor_id if served else None),
        space_id=served_object_id, parent_object_id=connected_network_object_id, transform=transform,
        geometry_reference=None, coordinate_system=("LOCAL_BUILDING" if served else "PROJECT_GLOBAL"),
        asset_status=asset_status, operational_state="AVAILABLE", spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def build_mrt_carrier(
    registry: SpatialObjectRegistry, *, carrier_id: str, facility_id: str, network_object_id: str,
    asset_status: AssetStatus = "PROPOSED", transform: Transform = Transform(),
) -> CanonicalSpatialObject:
    """Section 20: carrier is a movable engineering asset distinct from
    container/guideway/endpoint. Spatial identity ONLY -- fleet sizing
    remains fully owned by mrt_carrier_fleet.py/shared_mrt_multistream_authority.py,
    never a second fleet-sizing formula and never a separate fleet per stream."""
    if network_object_id not in registry.objects:
        raise ValueError(f"carrier {carrier_id} requires an existing network_object_id: {network_object_id} not found")
    obj = CanonicalSpatialObject(
        mrtway_object_id=carrier_id, object_type="MRT_CARRIER", facility_id=facility_id, building_id=None,
        floor_id=None, space_id=None, parent_object_id=network_object_id, transform=transform, geometry_reference=None,
        coordinate_system="PROJECT_GLOBAL", asset_status=asset_status, operational_state="AVAILABLE",
        spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def build_mrt_carrier_fleet_spatial_objects(
    registry: SpatialObjectRegistry, *, facility_id: str, network_object_id: str, carrier_count: int,
    id_prefix: str = "CARRIER", asset_status: AssetStatus = "PROPOSED",
) -> tuple[CanonicalSpatialObject, ...]:
    """Section 20: spatial identity for ONE shared carrier fleet -- never
    creates separate carrier fleets per stream."""
    return tuple(
        build_mrt_carrier(registry, carrier_id=f"{id_prefix}-{i:03d}", facility_id=facility_id, network_object_id=network_object_id, asset_status=asset_status)
        for i in range(1, carrier_count + 1)
    )


def build_mrt_container(
    registry: SpatialObjectRegistry, *, container_id: str, facility_id: str, container_class_id: str,
    network_object_id: str | None = None, asset_status: AssetStatus = "PROPOSED",
) -> CanonicalSpatialObject:
    """Section 21: container remains distinct from carrier -- preserves
    `shared_mrt_multistream_authority`'s existing payload-class semantics
    (container_class_id must be one of its known container classes), never
    collapsing carrier and container into one spatial object."""
    if container_class_id not in KNOWN_MRT_CONTAINER_CLASS_IDS:
        raise ValueError(f"container {container_id} references unknown container_class_id {container_class_id!r}; expected one of {sorted(KNOWN_MRT_CONTAINER_CLASS_IDS)}")
    if network_object_id is not None and network_object_id not in registry.objects:
        raise ValueError(f"container {container_id} network_object_id {network_object_id} not found")
    obj = CanonicalSpatialObject(
        mrtway_object_id=container_id, object_type="MRT_CONTAINER", facility_id=facility_id, building_id=None,
        floor_id=None, space_id=None, parent_object_id=network_object_id, transform=Transform(), geometry_reference=None,
        coordinate_system="PROJECT_GLOBAL", asset_status=asset_status, operational_state="AVAILABLE",
        spatial_status="CALIBRATED", provenance="USER_CREATED", engineering_object_id=container_class_id,
    )
    registry.add(obj)
    return obj


# ============================================================================
# CLOSURE BUILD: N-BUILDING PRODUCTION AUTHORITY + FIVE-BUILDING CONTROLLED
# CAMPUS QUALIFICATION (sections 23-30)
# ============================================================================


def build_n_building_campus(registry: SpatialObjectRegistry, *, facility_id: str, building_ids: Sequence[str]) -> tuple[CanonicalSpatialObject, ...]:
    """Section 23: Campus = {B1..Bn}, n >= 1 -- a plain loop over caller-
    supplied IDs, never a hard-coded "Building A"/"Building B" special case."""
    return tuple(add_building(registry, facility_id=facility_id, building_id=b) for b in building_ids)


def build_five_building_controlled_campus() -> tuple[SpatialObjectRegistry, "ConnectivityGraph"]:
    """Section 24-30: CONTROLLED_TEST_GEOMETRY -- a five-building campus
    (A-B-C-D-E) used ONLY to qualify N-building topology/routing/economics
    beyond the legacy two-building benchmark. NOT a real hospital. Explicit
    topology: A<->B, B<->C, B<->D, D<->E.

    Three separate edge families are added to the SAME graph (never one
    edge shared by every mode):
      - pedestrian/corridor edges (WALKING_PORTER, PATIENT_MOVEMENT) on all
        four connections;
      - AGV-compatible edges on only A<->B, B<->C, D<->E (B<->D is
        deliberately NOT AGV-capable, proving AGV never assumes every
        pedestrian path is AGV-compatible, section 29);
      - a first-class MRT network chain (RADIOPHARMACY in A -> vestibule ->
        trunk -> junction at B -> branch -> junction at D -> trunk ->
        endpoint in E), satisfying section 27's no-teleportation example.
    PTS is deliberately NOT wired into this graph at all -- it remains its
    own fully separate network per section 30.
    """
    facility_id = "FAC-CAMPUS5"
    registry = build_facility_hierarchy(facility_id=facility_id)
    positions = {"BLDG-A": (0.0, 0.0), "BLDG-B": (100.0, 0.0), "BLDG-C": (200.0, 0.0), "BLDG-D": (100.0, 100.0), "BLDG-E": (100.0, 200.0)}
    build_n_building_campus(registry, facility_id=facility_id, building_ids=tuple(positions))
    for building_id, (x, y) in positions.items():
        registry.objects[building_id] = replace(registry.objects[building_id], transform=Transform(position_x=x, position_y=y))
        add_floor(registry, facility_id=facility_id, building_id=building_id, floor_id="F1")
        add_room(registry, facility_id=facility_id, building_id=building_id, floor_id="F1", room_id=f"{building_id}-F1-R01")

    graph = ConnectivityGraph()
    corridor_topology = (("BLDG-A", "BLDG-B", 100.0), ("BLDG-B", "BLDG-C", 100.0), ("BLDG-B", "BLDG-D", 100.0), ("BLDG-D", "BLDG-E", 100.0))
    for i, (b1, b2, length) in enumerate(corridor_topology, start=1):
        graph.add_edge(SpatialEdge(edge_id=f"CORRIDOR-{i:02d}", from_object_id=b1, to_object_id=b2, length_m=length, compatible_modes=frozenset({"WALKING_PORTER", "PATIENT_MOVEMENT"})))
    agv_topology = (("BLDG-A", "BLDG-B", 100.0), ("BLDG-B", "BLDG-C", 100.0), ("BLDG-D", "BLDG-E", 100.0))
    for i, (b1, b2, length) in enumerate(agv_topology, start=1):
        graph.add_edge(SpatialEdge(edge_id=f"AGV-{i:02d}", from_object_id=b1, to_object_id=b2, length_m=length, compatible_modes=frozenset({"AGV_AMR"})))

    build_nuclear_engineering_objects(
        registry, facility_id=facility_id, building_id="BLDG-A", floor_id="F1",
        cyclotron_id="CY-A-001", pet_scanner_id="SCN-PET-A-001", radiopharmacy_id="RP-A-001",
    )
    trunk_1 = build_mrt_trunk(registry, trunk_id="MRT-TRUNK-1", facility_id=facility_id, length_m=100.0)
    vestibule = build_mrt_vestibule(registry, vestibule_id="VEST-001", facility_id=facility_id, radiopharmacy_object_id="RP-A-001", connected_mrt_segment_id=trunk_1.mrtway_object_id)
    junction_b = build_mrt_junction(registry, junction_id="MRT-JCT-B", facility_id=facility_id)
    branch_1 = build_mrt_branch(registry, branch_id="MRT-BRANCH-1", facility_id=facility_id, connects_to_object_id=junction_b.mrtway_object_id, length_m=150.0)
    junction_d = build_mrt_junction(registry, junction_id="MRT-JCT-D", facility_id=facility_id)
    trunk_2 = build_mrt_trunk(registry, trunk_id="MRT-TRUNK-2", facility_id=facility_id, network_id=junction_d.mrtway_object_id, length_m=150.0)
    endpoint_e = build_mrt_endpoint(registry, endpoint_id="MRT-ENDPOINT-E", facility_id=facility_id, connected_network_object_id=trunk_2.mrtway_object_id, served_object_id="BLDG-E-F1-R01")

    mrt_chain = (
        ("EDGE-MRT-01", "RP-A-001", vestibule.mrtway_object_id, 5.0),
        ("EDGE-MRT-02", vestibule.mrtway_object_id, trunk_1.mrtway_object_id, 5.0),
        ("EDGE-MRT-03", trunk_1.mrtway_object_id, junction_b.mrtway_object_id, 100.0),
        ("EDGE-MRT-04", junction_b.mrtway_object_id, branch_1.mrtway_object_id, 0.0),
        ("EDGE-MRT-05", branch_1.mrtway_object_id, junction_d.mrtway_object_id, 150.0),
        ("EDGE-MRT-06", junction_d.mrtway_object_id, trunk_2.mrtway_object_id, 0.0),
        ("EDGE-MRT-07", trunk_2.mrtway_object_id, endpoint_e.mrtway_object_id, 150.0),
    )
    for edge_id, a, b, length in mrt_chain:
        graph.add_edge(SpatialEdge(edge_id=edge_id, from_object_id=a, to_object_id=b, length_m=length, compatible_modes=frozenset({"MRT"})))

    return registry, graph


HybridCoverageMode = Literal["CONVENTIONAL", "MRT"]


@dataclass(frozen=True)
class HybridSpatialCoverageZone:
    zone_object_id: str
    coverage_mode: HybridCoverageMode


@dataclass(frozen=True)
class HybridSpatialCoverageMap:
    zones: tuple[HybridSpatialCoverageZone, ...]

    def coverage_for(self, zone_object_id: str) -> HybridCoverageMode | None:
        return next((z.coverage_mode for z in self.zones if z.zone_object_id == zone_object_id), None)


def build_hybrid_spatial_coverage_map(assignments: Mapping[str, HybridCoverageMode]) -> HybridSpatialCoverageMap:
    """Section 33-34: HYBRID_MRT is spatial COVERAGE (building/floor/zone/
    route/endpoint-level), never a rigid A/B architecture. This is a
    lightweight spatial descriptor only -- it does NOT reimplement
    hybrid_optimization.py's candidate search/economics; it tags which
    canonical spatial zones/objects are MRT-covered vs Conventional. Any
    object id (building, building::floor, room, endpoint) can be a key, so
    floor-level variation needs no facility-schema change."""
    return HybridSpatialCoverageMap(zones=tuple(HybridSpatialCoverageZone(zone_object_id=k, coverage_mode=v) for k, v in assignments.items()))


def tag_asset_status_for_development_context(
    registry: SpatialObjectRegistry, *, development_context: Literal["RETROFIT", "GREENFIELD"],
    proposed_object_ids: frozenset[str] = frozenset(),
) -> SpatialObjectRegistry:
    """Section 35-37: RETROFIT/GREENFIELD is defined by asset/project status,
    not building count or campus regeneration. Returns a NEW registry (never
    mutates the input): RETROFIT -> objects not in `proposed_object_ids`
    stay EXISTING (baseline), listed interventions become PROPOSED;
    GREENFIELD -> every object becomes PROPOSED regardless of campus size.
    Building/room/patient/source/scanner IDENTITY and COUNT are never
    altered by this function -- only `asset_status`."""
    new_objects = {}
    for object_id, obj in registry.objects.items():
        if development_context == "GREENFIELD":
            new_objects[object_id] = replace(obj, asset_status="PROPOSED")
        else:
            new_status: AssetStatus = "PROPOSED" if object_id in proposed_object_ids else "EXISTING"
            new_objects[object_id] = replace(obj, asset_status=new_status)
    return SpatialObjectRegistry(objects=new_objects)


# ============================================================================
# CLOSURE BUILD: IMPORT NORMALIZATION CONTRACTS (sections 47-55)
#
# Section 48: EVERY input mode returns the SAME `NormalizedImportResult`
# shape -- no mode may create a separate engineering model.
# ============================================================================

ImportMode = Literal["BLANK_MANUAL", "ASSISTED_TEMPLATE", "IFC_BIM", "CAD", "PDF_IMAGE", "API", "INTELLIGENT_RECONSTRUCTION", "ITWIN"]


@dataclass(frozen=True)
class NormalizedImportResult:
    import_mode: ImportMode
    registry: SpatialObjectRegistry
    coordinate_system: CoordinateSystem
    provenance: Provenance
    confidence: Literal["high", "medium", "low", "unknown"]
    validation_issues: tuple[SpatialValidationIssue, ...]
    source_metadata: Mapping[str, str] = field(default_factory=dict)


def _finalize_normalized_import(
    *, import_mode: ImportMode, registry: SpatialObjectRegistry, coordinate_system: CoordinateSystem,
    provenance: Provenance, confidence: Literal["high", "medium", "low", "unknown"], source_metadata: Mapping[str, str],
) -> NormalizedImportResult:
    return NormalizedImportResult(
        import_mode=import_mode, registry=registry, coordinate_system=coordinate_system, provenance=provenance,
        confidence=confidence, validation_issues=validate_spatial_registry(registry), source_metadata=source_metadata,
    )


def normalize_blank_manual_import(registry: SpatialObjectRegistry) -> NormalizedImportResult:
    """Section 49: blank manual design creates canonical objects directly
    (via add_building/add_floor/add_room/etc.) -- highest confidence, no
    external source."""
    return _finalize_normalized_import(import_mode="BLANK_MANUAL", registry=registry, coordinate_system="LOCAL_FACILITY", provenance="USER_CREATED", confidence="high", source_metadata={})


def normalize_template_import(registry: SpatialObjectRegistry, *, template_id: str) -> NormalizedImportResult:
    """Section 50: template identity (`template_id`) is metadata only -- it
    NEVER becomes permanent engineering identity (objects still get their
    own stable `mrtway_object_id`s)."""
    return _finalize_normalized_import(import_mode="ASSISTED_TEMPLATE", registry=registry, coordinate_system="LOCAL_FACILITY", provenance="TEMPLATE", confidence="medium", source_metadata={"template_id": template_id})


def normalize_ifc_bim_import(
    registry: SpatialObjectRegistry, *, source_version: str, coordinate_system: CoordinateSystem = "EXTERNAL_MODEL",
) -> NormalizedImportResult:
    """Section 51: IFC/BIM contract -- source type/version + coordinate-
    system metadata prepared; canonical object <-> IFC GUID mapping is via
    `ExternalReference.ifc_guid` (mapping only, never identity). No IFC SDK
    required or used here."""
    return _finalize_normalized_import(import_mode="IFC_BIM", registry=registry, coordinate_system=coordinate_system, provenance="IMPORTED_IFC", confidence="high", source_metadata={"source_type": "IFC", "source_version": source_version})


def normalize_cad_import(
    registry: SpatialObjectRegistry, *, source_layer: str, coordinate_system: CoordinateSystem = "EXTERNAL_MODEL",
) -> NormalizedImportResult:
    """Section 52: CAD entity/block + layer metadata prepared; CAD IDs are
    never made authoritative (mapping only via `ExternalReference.cad_entity_id`)."""
    return _finalize_normalized_import(import_mode="CAD", registry=registry, coordinate_system=coordinate_system, provenance="IMPORTED_CAD", confidence="medium", source_metadata={"source_layer": source_layer})


def normalize_pdf_image_import(registry: SpatialObjectRegistry, *, source_document_id: str) -> NormalizedImportResult:
    """Section 53: source-document reference + reconstruction status only --
    no OCR/reconstruction implemented in this closure build."""
    return _finalize_normalized_import(import_mode="PDF_IMAGE", registry=registry, coordinate_system="LOCAL_FACILITY", provenance="RECONSTRUCTED", confidence="low", source_metadata={"source_document_id": source_document_id, "reconstruction_status": "NOT_YET_RECONSTRUCTED"})


def normalize_api_import(registry: SpatialObjectRegistry, *, source_system: str, source_timestamp: str) -> NormalizedImportResult:
    """Section 54: source system + external object ID + timestamp/version
    metadata; no vendor-specific API integration required."""
    return _finalize_normalized_import(import_mode="API", registry=registry, coordinate_system="EXTERNAL_MODEL", provenance="API", confidence="medium", source_metadata={"source_system": source_system, "source_timestamp": source_timestamp})


def normalize_intelligent_reconstruction_import(
    registry: SpatialObjectRegistry, *, source_evidence: str, confidence: Literal["high", "medium", "low", "unknown"] = "low",
) -> NormalizedImportResult:
    """Section 55: inference is NEVER represented as measured geometry --
    provenance is explicitly RECONSTRUCTED and confidence defaults low."""
    return _finalize_normalized_import(import_mode="INTELLIGENT_RECONSTRUCTION", registry=registry, coordinate_system="LOCAL_FACILITY", provenance="RECONSTRUCTED", confidence=confidence, source_metadata={"source_evidence": source_evidence})


# ============================================================================
# BIM/iTwin PHASE 1: Bentley element normalization (sections 5-15 of the
# BIM/iTwin Phase 1 prompt).
#
# GOVERNANCE: this is the ONLY place Bentley element records become
# CanonicalSpatialObjects. No HTTP/OAuth/ECSQL happens here -- callers
# supply already-retrieved `BentleyElementRecord`s (see bentley_itwin_client.py
# for the separate, thin retrieval boundary). External IDs are NEVER
# canonical identity (section 8) -- `mrtway_object_id` remains authoritative;
# `ExternalReference.itwin_element_id` is reused verbatim for element
# identity (never a second `bentley_element_id` field).
#
# Callers must supply a WhatIfSpatialState's registry (never
# LockedSpatialState.registry directly) so an imported/changed Bentley
# revision can never mutate L0 in place (section 20/42) -- this function
# does not itself branch a WhatIfSpatialState; it only mutates whatever
# registry it is given, exactly like `apply_changeset` already does.
# ============================================================================

FIRST_PHASE_BENTLEY_OBJECT_TYPES: frozenset[SpatialObjectType] = frozenset({
    "BUILDING", "FLOOR", "ROOM", "CYCLOTRON", "PET_SCANNER", "SPECT_SCANNER", "MO99_TC99M_GENERATOR", "RADIOPHARMACY",
})
"""Section 7: FIRST-PHASE supported categories only -- walls/doors/ceilings/
columns/beams/slabs/finishes/furniture/MEP/structural members are never
auto-promoted to canonical objects; anything outside this set is IGNORED_UNMAPPED."""

_EQUIPMENT_BENTLEY_OBJECT_TYPES: frozenset[SpatialObjectType] = frozenset({
    "CYCLOTRON", "PET_SCANNER", "SPECT_SCANNER", "MO99_TC99M_GENERATOR", "RADIOPHARMACY",
})


def resolve_bentley_object_type(element_class: str) -> SpatialObjectType | None:
    """Section 7: narrow, case-insensitive lookup against the first-phase
    category set. Returns None (ignored/unmapped) for anything else --
    never guesses."""
    normalized = element_class.strip().upper()
    if normalized in FIRST_PHASE_BENTLEY_OBJECT_TYPES:
        return normalized  # type: ignore[return-value]
    return None


@dataclass(frozen=True)
class BentleyElementRecord:
    """Section 6: the minimum normalized Bentley element input required by
    the existing repository -- a typed record, never a generic JSON blob.
    Already-retrieved/already-normalized by the caller (e.g.
    bentley_itwin_client.py); this dataclass carries NO vendor-specific
    request/auth concerns."""

    itwin_id: str
    imodel_id: str
    element_id: str
    element_class: str
    change_reference: str | None = None
    element_label: str | None = None
    parent_element_id: str | None = None
    building_id: str | None = None
    floor_id: str | None = None
    room_number: str | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None
    rotation_x: float = 0.0
    rotation_y: float = 0.0
    rotation_z: float = 0.0
    source_scale_m_per_unit: float = 1.0
    source_document_id: str | None = None
    engineering_object_id: str | None = None
    """Section 10: REQUIRED for equipment classes -- an explicit, already-
    existing canonical engineering identifier (e.g. "SCN-002", "CY-001",
    "GEN-001"). Never fabricated from Bentley geometry alone."""


BentleyBindingStatus = Literal["CREATED", "REUSED_EXISTING", "IGNORED_UNMAPPED", "CONFLICT", "AMBIGUOUS"]


@dataclass(frozen=True)
class BentleyBindingOutcome:
    """Section 9/34-35: one deterministic outcome per input element -- never
    a silent guess. `CONFLICT` and `AMBIGUOUS` always leave the existing
    canonical binding untouched."""

    element_id: str
    status: BentleyBindingStatus
    mrtway_object_id: str | None
    detail: str = ""


@dataclass(frozen=True)
class ItwinNormalizedImportResult:
    normalized: NormalizedImportResult
    bindings: tuple[BentleyBindingOutcome, ...]


def compose_project_global_transform(
    *, parent_transform: Transform, local_x: float, local_y: float = 0.0, local_z: float = 0.0,
    rotation_x: float = 0.0, rotation_y: float = 0.0, rotation_z: float = 0.0, scale_m_per_unit: float = 1.0,
) -> Transform:
    """Section 13/15: the MINIMUM safe one-level parent-child transform
    composition -- unit scale, then Z-axis rotation (matching this module's
    existing convention that only `rotation_z` is engineering-meaningful,
    see `apply_engineering_rotation`), then translation by the parent's own
    PROJECT_GLOBAL position. NOT a general-purpose graphics transform engine
    -- resolves exactly one local point through exactly one parent transform."""
    scaled_x = local_x * scale_m_per_unit
    scaled_y = local_y * scale_m_per_unit
    scaled_z = local_z * scale_m_per_unit
    theta = math.radians(parent_transform.rotation_z)
    rotated_x = scaled_x * math.cos(theta) - scaled_y * math.sin(theta)
    rotated_y = scaled_x * math.sin(theta) + scaled_y * math.cos(theta)
    return Transform(
        position_x=parent_transform.position_x + rotated_x,
        position_y=parent_transform.position_y + rotated_y,
        position_z=parent_transform.position_z + scaled_z,
        rotation_x=rotation_x, rotation_y=rotation_y, rotation_z=parent_transform.rotation_z + rotation_z,
    )


def _resolve_bentley_transform(element: BentleyElementRecord, parent_transform_by_building_id: Mapping[str, Transform]) -> Transform:
    if element.x is None:
        return Transform()
    parent_transform = parent_transform_by_building_id.get(element.building_id) if element.building_id else None
    if parent_transform is not None:
        return compose_project_global_transform(
            parent_transform=parent_transform, local_x=element.x, local_y=element.y or 0.0, local_z=element.z or 0.0,
            rotation_x=element.rotation_x, rotation_y=element.rotation_y, rotation_z=element.rotation_z,
            scale_m_per_unit=element.source_scale_m_per_unit,
        )
    s = element.source_scale_m_per_unit
    return Transform(
        position_x=element.x * s, position_y=(element.y or 0.0) * s, position_z=(element.z or 0.0) * s,
        rotation_x=element.rotation_x, rotation_y=element.rotation_y, rotation_z=element.rotation_z,
    )


def _bentley_external_reference(element: BentleyElementRecord, *, preserve: ExternalReference | None = None) -> ExternalReference:
    base = preserve if preserve is not None else ExternalReference()
    return replace(
        base, itwin_element_id=element.element_id, external_project_id=element.itwin_id, external_model_id=element.imodel_id,
        change_reference=element.change_reference, source_document_id=element.source_document_id or base.source_document_id,
    )


def _find_object_by_itwin_element_id(registry: SpatialObjectRegistry, element_id: str) -> CanonicalSpatialObject | None:
    for obj in registry.objects.values():
        if obj.external_reference.itwin_element_id == element_id:
            return obj
    return None


def _apply_bentley_element_to_object(
    existing: CanonicalSpatialObject, element: BentleyElementRecord, parent_transform_by_building_id: Mapping[str, Transform],
) -> CanonicalSpatialObject:
    """Section 8/33: reuses (never duplicates) an already-bound canonical
    object -- a changed transform/change_reference updates it in place
    (still a NEW frozen instance, never a mutation of the original), the
    canonical `mrtway_object_id` never changes."""
    transform = _resolve_bentley_transform(element, parent_transform_by_building_id)
    ext = _bentley_external_reference(element, preserve=existing.external_reference)
    return replace(existing, transform=transform, external_reference=ext, provenance="IMPORTED_ITWIN", coordinate_system="EXTERNAL_MODEL")


def _build_bentley_object(
    *, object_type: SpatialObjectType, mrtway_object_id: str, facility_id: str, element: BentleyElementRecord,
    parent_transform_by_building_id: Mapping[str, Transform],
) -> CanonicalSpatialObject:
    transform = _resolve_bentley_transform(element, parent_transform_by_building_id)
    ext = _bentley_external_reference(element)
    if object_type == "BUILDING":
        parent_object_id: str | None = facility_id
        space_id = None
        engineering_object_id = None
    elif object_type == "FLOOR":
        parent_object_id = element.building_id
        space_id = None
        engineering_object_id = None
    else:
        parent_object_id = (
            default_floor_object_id(element.building_id, element.floor_id)
            if element.building_id and element.floor_id else None
        )
        space_id = mrtway_object_id
        engineering_object_id = element.engineering_object_id
    return CanonicalSpatialObject(
        mrtway_object_id=mrtway_object_id, object_type=object_type, facility_id=facility_id, building_id=element.building_id,
        floor_id=element.floor_id, space_id=space_id, parent_object_id=parent_object_id, transform=transform,
        geometry_reference=None, coordinate_system="EXTERNAL_MODEL", asset_status="EXISTING", operational_state="AVAILABLE",
        spatial_status="CALIBRATED", provenance="IMPORTED_ITWIN", external_reference=ext, confidence="high",
        engineering_object_id=engineering_object_id,
    )


def normalize_itwin_import(
    registry: SpatialObjectRegistry, *, facility_id: str, elements: Sequence[BentleyElementRecord],
    parent_transform_by_building_id: Mapping[str, Transform] | None = None,
) -> ItwinNormalizedImportResult:
    """Section 5: normalizes ALREADY-RETRIEVED Bentley element records into
    canonical spatial objects, following the SAME `_finalize_normalized_import`
    contract every other `normalize_*_import` function uses. Performs NO
    HTTP/OAuth/ECSQL/routing -- normalization and conservative binding only.

    `registry` MUST be a WhatIfSpatialState's registry (never a
    LockedSpatialState's) so a Bentley-derived revision can never mutate L0
    in place (section 20/42) -- exactly the same caller responsibility
    `apply_changeset` already requires.

    Binding precedence (section 9): (1) existing `itwin_element_id` binding
    is reused; (2) equipment REQUIRES an explicit, already-existing
    `engineering_object_id` (section 10-11) -- never fabricated; (3) an exact
    room-number match against an existing canonical ROOM is used only as an
    assisted deterministic match, and only if that room is not already bound
    to a DIFFERENT itwin_element_id (else CONFLICT, section 34); (4)
    otherwise a new canonical object is created. No fuzzy or nearest-
    coordinate matching is ever performed (section 9/24)."""
    parent_transforms = parent_transform_by_building_id or {}
    bindings: list[BentleyBindingOutcome] = []

    for element in elements:
        object_type = resolve_bentley_object_type(element.element_class)
        if object_type is None:
            bindings.append(BentleyBindingOutcome(
                element_id=element.element_id, status="IGNORED_UNMAPPED", mrtway_object_id=None,
                detail=f"element_class {element.element_class!r} is outside the first-phase category set",
            ))
            continue

        existing = _find_object_by_itwin_element_id(registry, element.element_id)
        if existing is not None:
            updated = _apply_bentley_element_to_object(existing, element, parent_transforms)
            registry.objects[existing.mrtway_object_id] = updated
            bindings.append(BentleyBindingOutcome(element_id=element.element_id, status="REUSED_EXISTING", mrtway_object_id=existing.mrtway_object_id))
            continue

        if object_type in _EQUIPMENT_BENTLEY_OBJECT_TYPES:
            if element.engineering_object_id is None:
                bindings.append(BentleyBindingOutcome(
                    element_id=element.element_id, status="AMBIGUOUS", mrtway_object_id=None,
                    detail="equipment element requires an explicit engineering_object_id (section 10) -- none supplied",
                ))
                continue
            target_object_id = element.engineering_object_id
            existing_equipment = registry.objects.get(target_object_id)
            if existing_equipment is not None:
                if existing_equipment.external_reference.itwin_element_id not in (None, element.element_id):
                    bindings.append(BentleyBindingOutcome(
                        element_id=element.element_id, status="CONFLICT", mrtway_object_id=target_object_id,
                        detail=f"{target_object_id} already bound to a different itwin_element_id",
                    ))
                    continue
                updated = _apply_bentley_element_to_object(existing_equipment, element, parent_transforms)
                registry.objects[target_object_id] = updated
                bindings.append(BentleyBindingOutcome(element_id=element.element_id, status="REUSED_EXISTING", mrtway_object_id=target_object_id))
                continue
            new_object = _build_bentley_object(
                object_type=object_type, mrtway_object_id=target_object_id, facility_id=facility_id, element=element,
                parent_transform_by_building_id=parent_transforms,
            )
            registry.add(new_object)
            bindings.append(BentleyBindingOutcome(element_id=element.element_id, status="CREATED", mrtway_object_id=target_object_id))
            continue

        if object_type == "ROOM" and element.room_number is not None:
            candidate = registry.objects.get(element.room_number)
            if candidate is not None and candidate.object_type == "ROOM":
                if candidate.external_reference.itwin_element_id not in (None, element.element_id):
                    bindings.append(BentleyBindingOutcome(
                        element_id=element.element_id, status="CONFLICT", mrtway_object_id=candidate.mrtway_object_id,
                        detail=f"room {candidate.mrtway_object_id} already bound to a different itwin_element_id",
                    ))
                    continue
                updated = _apply_bentley_element_to_object(candidate, element, parent_transforms)
                registry.objects[candidate.mrtway_object_id] = updated
                bindings.append(BentleyBindingOutcome(element_id=element.element_id, status="REUSED_EXISTING", mrtway_object_id=candidate.mrtway_object_id))
                continue

        if object_type == "BUILDING":
            target_object_id = element.building_id or element.element_id
        elif object_type == "FLOOR":
            target_object_id = default_floor_object_id(element.building_id or facility_id, element.floor_id or element.element_id)
        elif object_type == "ROOM":
            target_object_id = element.room_number or element.element_id
        else:
            target_object_id = element.element_id

        if target_object_id in registry.objects:
            existing_obj = registry.objects[target_object_id]
            if existing_obj.external_reference.itwin_element_id not in (None, element.element_id):
                bindings.append(BentleyBindingOutcome(
                    element_id=element.element_id, status="CONFLICT", mrtway_object_id=target_object_id,
                    detail=f"{target_object_id} already bound to a different itwin_element_id",
                ))
                continue
            updated = _apply_bentley_element_to_object(existing_obj, element, parent_transforms)
            registry.objects[target_object_id] = updated
            bindings.append(BentleyBindingOutcome(element_id=element.element_id, status="REUSED_EXISTING", mrtway_object_id=target_object_id))
            continue

        new_object = _build_bentley_object(
            object_type=object_type, mrtway_object_id=target_object_id, facility_id=facility_id, element=element,
            parent_transform_by_building_id=parent_transforms,
        )
        registry.add(new_object)
        bindings.append(BentleyBindingOutcome(element_id=element.element_id, status="CREATED", mrtway_object_id=target_object_id))

    normalized = _finalize_normalized_import(
        import_mode="ITWIN", registry=registry, coordinate_system="EXTERNAL_MODEL", provenance="IMPORTED_ITWIN",
        confidence="high", source_metadata={"source_type": "ITWIN", "element_count": str(len(elements))},
    )
    return ItwinNormalizedImportResult(normalized=normalized, bindings=tuple(bindings))


# ============================================================================
# CLOSURE BUILD: CAMERA VS ENGINEERING ROTATION (sections 64-65)
# ============================================================================


@dataclass(frozen=True)
class RotationImpact:
    rotation_kind: Literal["CAMERA_ROTATION", "ENGINEERING_OBJECT_ROTATION"]
    delta_capex: float | Literal["NOT_CALIBRATED"]
    delta_opex: float | Literal["NOT_CALIBRATED"]
    delta_route_geometry_m: float | Literal["NOT_CALIBRATED"]
    delta_engineering_transform: bool


def apply_camera_rotation(*, yaw_degrees: float, pitch_degrees: float) -> RotationImpact:
    """Section 64: orbiting the 3D camera is a VIEW change only -- it must
    NEVER touch engineering transforms or economics, at any angle. This
    function never touches a `WhatIfSpatialState`/registry at all."""
    return RotationImpact(rotation_kind="CAMERA_ROTATION", delta_capex=0.0, delta_opex=0.0, delta_route_geometry_m=0.0, delta_engineering_transform=False)


def apply_engineering_rotation(
    what_if: WhatIfSpatialState, *, object_id: str, new_rotation: Transform, change_id: str,
) -> tuple[SpatialChangeSet, RotationImpact]:
    """Section 65: physically rotating an engineering object in WHAT_IF
    state IS an engineering change -- routed through the same reversible
    `apply_changeset(... operation="ROTATE_OBJECT")` path as any other
    what-if mutation. Honestly NOT_CALIBRATED on economic/route impact
    (never hard-coded to zero) until a real fit/clearance/route model exists."""
    obj = what_if.registry.get(object_id)
    new_object = replace(obj, transform=new_rotation)
    changeset = apply_changeset(what_if, change_id=change_id, operation="ROTATE_OBJECT", object_id=object_id, new_object=new_object)
    impact = RotationImpact(rotation_kind="ENGINEERING_OBJECT_ROTATION", delta_capex="NOT_CALIBRATED", delta_opex="NOT_CALIBRATED", delta_route_geometry_m="NOT_CALIBRATED", delta_engineering_transform=True)
    return changeset, impact


# ============================================================================
# CLOSURE BUILD: CONNECTIVITY-AWARE TRANSFORM FOUNDATION (sections 66-78)
# ============================================================================

ConnectionType = Literal["MRT", "CORRIDOR_BRIDGE_TUNNEL", "OTHER"]


@dataclass(frozen=True)
class ConnectionImpact:
    connection_id: str
    from_object_id: str
    to_object_id: str
    connection_type: ConnectionType
    length_m: float | Literal["NOT_CALIBRATED"]


def find_affected_connections(graph: ConnectivityGraph, object_id: str) -> tuple[ConnectionImpact, ...]:
    """Section 66/71: returns ALL edges touching `object_id` -- never only
    the first, so B<->C / B<->D / B<->E-style multi-connection objects are
    fully reported before any transform is applied."""
    impacts: list[ConnectionImpact] = []
    for e in graph.edges:
        if e.from_object_id == object_id or e.to_object_id == object_id:
            if "MRT" in e.compatible_modes:
                conn_type: ConnectionType = "MRT"
            elif e.compatible_modes & {"WALKING_PORTER", "PATIENT_MOVEMENT", "AGV_AMR"}:
                conn_type = "CORRIDOR_BRIDGE_TUNNEL"
            else:
                conn_type = "OTHER"
            impacts.append(ConnectionImpact(connection_id=e.edge_id, from_object_id=e.from_object_id, to_object_id=e.to_object_id, connection_type=conn_type, length_m=e.length_m))
    return tuple(impacts)


ConnectionResolution = Literal["PRESERVE_CONNECTION", "MOVE_CONNECTED_ASSEMBLY", "DISCONNECT", "CANCEL_TRANSFORM"]


@dataclass(frozen=True)
class ConnectionResolutionResult:
    connection_id: str
    resolution: ConnectionResolution
    original_length_m: float | Literal["NOT_CALIBRATED"]
    resulting_length_m: float | Literal["NOT_CALIBRATED"]
    delta_length_m: float | Literal["NOT_CALIBRATED"]
    resulting_status: Literal["CONNECTED", "DISCONNECTED", "UNROUTABLE"]


def resolve_connection_preserve(graph: ConnectivityGraph, *, connection_id: str, new_length_m: float) -> ConnectionResolutionResult:
    """Section 68: PRESERVE_CONNECTION -- the connecting geometry (edge
    length) is updated to the new physical distance; original/resulting/
    delta length are all recorded, never silently stretched."""
    idx = next(i for i, e in enumerate(graph.edges) if e.edge_id == connection_id)
    edge = graph.edges[idx]
    original_length = edge.length_m
    graph.edges[idx] = replace(edge, length_m=new_length_m)
    delta: float | Literal["NOT_CALIBRATED"] = (new_length_m - original_length) if original_length != "NOT_CALIBRATED" else "NOT_CALIBRATED"
    return ConnectionResolutionResult(connection_id=connection_id, resolution="PRESERVE_CONNECTION", original_length_m=original_length, resulting_length_m=new_length_m, delta_length_m=delta, resulting_status="CONNECTED")


def resolve_connection_disconnect(graph: ConnectivityGraph, *, connection_id: str) -> ConnectionResolutionResult:
    """Section 70: an honestly-reported DISCONNECTED edge -- removed from
    the routable graph so any dependent route becomes ROUTE_NOT_CALIBRATED;
    no alternate route is ever invented."""
    idx = next(i for i, e in enumerate(graph.edges) if e.edge_id == connection_id)
    edge = graph.edges.pop(idx)
    return ConnectionResolutionResult(connection_id=connection_id, resolution="DISCONNECT", original_length_m=edge.length_m, resulting_length_m="NOT_CALIBRATED", delta_length_m="NOT_CALIBRATED", resulting_status="DISCONNECTED")


def cancel_transform(changeset: SpatialChangeSet, what_if: WhatIfSpatialState) -> SpatialChangeSet | None:
    """Section 67: CANCEL_TRANSFORM -- reuses the existing reversible-undo
    path rather than inventing a second rollback mechanism. Only valid
    immediately after the given changeset is the most recent entry."""
    if not what_if.history or what_if.history[-1] is not changeset:
        raise ValueError("cancel_transform requires the given changeset to be the most recent what-if change")
    return what_if.undo_last_change()


SelectionScope = Literal["OBJECT", "MULTI_OBJECT", "BUILDING", "MULTI_BUILDING", "SUB_CAMPUS", "ENTIRE_CAMPUS"]


@dataclass(frozen=True)
class SelectionSet:
    selection_id: str
    selected_object_ids: tuple[str, ...]
    selection_scope: SelectionScope
    pivot: Transform
    provenance: str


def build_selection_set(
    *, selection_id: str, selected_object_ids: Sequence[str], selection_scope: SelectionScope,
    pivot: Transform = Transform(), provenance: str = "USER_SELECTED",
) -> SelectionSet:
    """Section 72: platform-neutral SelectionSet -- backend contract only."""
    return SelectionSet(selection_id=selection_id, selected_object_ids=tuple(selected_object_ids), selection_scope=selection_scope, pivot=pivot, provenance=provenance)


def _validated_selection_object_ids(registry: SpatialObjectRegistry, object_ids: Sequence[str]) -> tuple[str, ...]:
    missing = [oid for oid in object_ids if oid not in registry.objects]
    if missing:
        raise ValueError(f"selection references unknown object ids: {missing}")
    return tuple(object_ids)


def box_select(registry: SpatialObjectRegistry, *, selection_id: str, object_ids: Sequence[str]) -> SelectionSet:
    """Section 73: BOX_SELECT backend contract -- produces a SelectionSet
    only, no visual box-select graphics."""
    validated = _validated_selection_object_ids(registry, object_ids)
    return build_selection_set(selection_id=selection_id, selected_object_ids=validated, selection_scope=("MULTI_OBJECT" if len(validated) > 1 else "OBJECT"), provenance="BOX_SELECT")


def lasso_select(registry: SpatialObjectRegistry, *, selection_id: str, object_ids: Sequence[str]) -> SelectionSet:
    """Section 73: LASSO_SELECT backend contract -- produces a SelectionSet
    only, no visual lasso graphics."""
    validated = _validated_selection_object_ids(registry, object_ids)
    return build_selection_set(selection_id=selection_id, selected_object_ids=validated, selection_scope=("MULTI_OBJECT" if len(validated) > 1 else "OBJECT"), provenance="LASSO_SELECT")


@dataclass(frozen=True)
class ObjectGroup:
    group_id: str
    member_object_ids: tuple[str, ...]


def group_objects(*, group_id: str, member_object_ids: Sequence[str]) -> ObjectGroup:
    """Section 74: grouping is a transform convenience only -- every member
    KEEPS its own `mrtway_object_id`; grouping never replaces canonical
    identity."""
    return ObjectGroup(group_id=group_id, member_object_ids=tuple(member_object_ids))


def ungroup(group: ObjectGroup) -> tuple[str, ...]:
    """Section 74: ungrouping returns the exact same member IDs -- nothing
    about canonical identity changes."""
    return group.member_object_ids


@dataclass(frozen=True)
class BoundingVolume:
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float
    calibration_status: Literal["COARSE_ESTIMATE", "NOT_CALIBRATED"]


def compute_bounding_volume(registry: SpatialObjectRegistry, object_ids: Sequence[str]) -> BoundingVolume:
    """Section 75: `Transform` carries position only (no size/extent), so
    this is honestly COARSE_ESTIMATE (position envelope) -- never fabricated
    detailed geometry."""
    if not object_ids:
        return BoundingVolume(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "NOT_CALIBRATED")
    xs = [registry.get(oid).transform.position_x for oid in object_ids]
    ys = [registry.get(oid).transform.position_y for oid in object_ids]
    zs = [registry.get(oid).transform.position_z for oid in object_ids]
    return BoundingVolume(min(xs), min(ys), min(zs), max(xs), max(ys), max(zs), "COARSE_ESTIMATE")


def move_connected_assembly(
    what_if: WhatIfSpatialState, *, group: ObjectGroup, delta: Transform, change_id_prefix: str,
) -> tuple[SpatialChangeSet, ...]:
    """Section 69: applies the SAME delta to every member of a rigid
    selected assembly -- preserves internal relative geometry within the
    group."""
    changesets = []
    for object_id in group.member_object_ids:
        obj = what_if.registry.get(object_id)
        new_transform = Transform(
            position_x=obj.transform.position_x + delta.position_x,
            position_y=obj.transform.position_y + delta.position_y,
            position_z=obj.transform.position_z + delta.position_z,
            rotation_x=obj.transform.rotation_x + delta.rotation_x,
            rotation_y=obj.transform.rotation_y + delta.rotation_y,
            rotation_z=obj.transform.rotation_z + delta.rotation_z,
        )
        new_object = replace(obj, transform=new_transform)
        changesets.append(apply_changeset(what_if, change_id=f"{change_id_prefix}-{object_id}", operation="MOVE_OBJECT", object_id=object_id, new_object=new_object))
    return tuple(changesets)


def find_boundary_connections(graph: ConnectivityGraph, group: ObjectGroup) -> tuple[ConnectionImpact, ...]:
    """Section 69/77: connections from the selected group to objects
    OUTSIDE the group -- internal group-to-group edges are excluded since
    those members move rigidly together."""
    member_ids = set(group.member_object_ids)
    impacts: list[ConnectionImpact] = []
    seen_edge_ids: set[str] = set()
    for object_id in member_ids:
        for impact in find_affected_connections(graph, object_id):
            other = impact.to_object_id if impact.from_object_id == object_id else impact.from_object_id
            if other not in member_ids and impact.connection_id not in seen_edge_ids:
                impacts.append(impact)
                seen_edge_ids.add(impact.connection_id)
    return tuple(impacts)


# ============================================================================
# CLOSURE BUILD: SPATIAL ECONOMIC DELTAS (sections 79-81, 90)
# ============================================================================


def compute_segment_length_capex_delta(*, locked_length_m: float, what_if_length_m: float, guideway_unit_cost_per_m: float | None = None) -> float:
    """Section 79/90: ONLY guideway CapEx changes with segment length.
    Controls and installation/commissioning are NEVER recharged merely
    because a segment's length changed -- they are once-per-network/project
    charges (see MRT_CONTROLS_CAPEX_USD / MRT_INSTALLATION_COMMISSIONING_CAPEX_USD),
    entirely absent from this function."""
    from models import PlannerAssumptions

    unit_cost = guideway_unit_cost_per_m if guideway_unit_cost_per_m is not None else PlannerAssumptions().mrt_guideway_capex_per_m
    return (what_if_length_m - locked_length_m) * unit_cost


def compute_vestibule_count_capex_delta(*, locked_count: int, what_if_count: int, vestibule_unit_cost: float = MRT_VESTIBULE_CAPEX_USD) -> float:
    """Section 80-81: vestibule CapEx changes ONLY with vestibule quantity --
    never recharges controls/installation merely because vestibule count
    changed (sections 6-7)."""
    return (what_if_count - locked_count) * vestibule_unit_cost

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import dist
from typing import Any, Literal, Mapping, Sequence

EvidenceClass = Literal[
    "BIM_AUTHORITATIVE",
    "CAD_ENGINEERING",
    "PLAN_DERIVED",
    "USER_SUPPLIED",
    "TEMPLATE_DERIVED",
    "BENCHMARK_ASSUMED",
    "DERIVED_GEOMETRY",
]

Confidence = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
SpatialMaturity = Literal["CONCEPTUAL", "PRELIMINARY", "ENGINEERING", "BIM_VERIFIED"]
SpatialInputPath = Literal["UPLOAD_FACILITY_DOCUMENT", "MANUAL_SPATIAL_DEFINITION", "BENCHMARK_ASSUMED_FACILITY"]
SpatialSourceType = Literal[
    "IFC",
    "REVIT_BIM",
    "DWG",
    "DXF",
    "PDF",
    "IMAGE",
    "MANUAL",
    "TEMPLATE",
    "BENCHMARK",
    "OTHER",
]
ProjectSpatialMode = Literal["RETROFIT", "GREENFIELD"]
AdaptiveSpatialMode = Literal["RETROFIT", "GREENFIELD", "ADAPTIVE_REPURPOSING"]
DevelopmentZone = Literal["EXISTING_CORE", "EXISTING_ADJACENT", "EXPANSION_ZONE", "NEW_BUILDING", "UNKNOWN"]
SubscriptionTier = Literal["BASIC", "PROFESSIONAL", "ENTERPRISE"]
ObjectStatus = Literal[
    "FIXED",
    "MOVABLE",
    "RELOCATABLE_WITH_COST",
    "NEW_CANDIDATE",
    "REMOVABLE",
    "PROTECTED",
]
RelationshipType = Literal[
    "contained_in",
    "adjacent_to",
    "connected_to",
    "serves",
    "requires",
    "restricted_from",
    "must_be_near",
    "must_be_separated_from",
]
QuantityUnitType = Literal["length", "area", "volume", "count", "mass"]
QuantityValueUnit = Literal["m", "m2", "m3", "count", "kg"]
MaterialCategory = Literal[
    "concrete",
    "reinforced concrete",
    "structural steel",
    "masonry / CMU",
    "drywall / gypsum partition",
    "lead shielding",
    "special radiation shielding",
    "glass",
    "floor finish",
    "ceiling system",
    "cleanroom partition",
    "other",
    "unknown",
]
SpatialAccessibility = Literal["PUBLIC", "CONTROLLED", "RESTRICTED", "SERVICE", "UNKNOWN"]
EdgeDirectionality = Literal["BIDIRECTIONAL", "ONE_WAY", "ONE_WAY_REVERSE", "UNKNOWN"]
EdgeType = Literal["HORIZONTAL", "VERTICAL", "DOORWAY", "OPENING", "SHAFT", "STAIR", "ELEVATOR", "OTHER"]
RouteCorridorClass = Literal[
    "EXTERIOR_BUILDING_ENVELOPE",
    "CEILING_SERVICE_ZONE",
    "MECHANICAL_SERVICE_ZONE",
    "UTILITY_CORRIDOR",
    "DEDICATED_SHAFT",
    "EXISTING_SERVICE_SHAFT",
    "ROOF_ROUTE",
    "INTER_BUILDING_LINK",
    "DEDICATED_MRT_SHAFT",
    "EXISTING_SERVICE_SHAFT_CANDIDATE",
    "VERTICAL_GUIDEWAY",
    "HORIZONTAL_VERTICAL_TRANSITION",
    "VERTICAL_HORIZONTAL_TRANSITION",
    "INTERIOR_CLINICAL_PATH",
    "UNCLASSIFIED",
]
SpatialNodeKind = Literal[
    "facility",
    "building",
    "storey",
    "zone",
    "space",
    "boundary",
    "wall",
    "slab",
    "column",
    "beam",
    "door",
    "opening",
    "corridor",
    "shaft",
    "stair",
    "elevator",
    "equipment",
    "mrt_station",
    "guideway_endpoint",
    "guideway_segment",
    "junction",
    "vertical_transition",
    "loading_point",
    "unloading_point",
    "buffer",
    "other",
]
EquipmentClass = Literal[
    "Cyclotron",
    "Cyclotron vault",
    "Target area",
    "Hot cell",
    "Synthesis module",
    "QC laboratory",
    "Dispensing station",
    "Radiopharmacy",
    "Storage",
    "Radioactive waste area",
    "Airlock",
    "Change room",
    "Injection room",
    "Injection station/chair",
    "Uptake room",
    "PET/CT scanner",
    "PET/MR scanner",
    "SPECT/CT scanner",
    "Control room",
    "Patient preparation",
    "Waiting area",
    "Recovery area",
    "MRT station",
    "Guideway endpoint",
    "Guideway segment",
    "Junction",
    "Horizontal/vertical transition",
    "Vertical shaft",
    "Loading point",
    "Unloading point",
    "Buffer",
    "Other",
]
SpaceSuitability = Literal[
    "SUITABLE",
    "SUITABLE_WITH_MODIFICATION",
    "CONDITIONALLY_SUITABLE",
    "NOT_SUITABLE",
    "UNKNOWN",
]
ProgramAssignmentStatus = Literal["EXISTING_AS_BUILT", "OPTIMIZER_PROPOSED", "ACCEPTED_DESIGN"]
SpatialValidationStatus = Literal["PASSED", "WARNINGS", "INCOMPLETE"]
RouteGeometryStatus = Literal["RECONSTRUCTED", "NOT_RECONSTRUCTED"]


@dataclass(frozen=True)
class ProvenanceRecord:
    value: str | None
    source: str | None
    evidence_class: EvidenceClass
    confidence: Confidence
    derivation_method: str
    user_override: bool = False


@dataclass(frozen=True)
class SpatialCoordinate:
    x_m: float | None = None
    y_m: float | None = None
    z_m: float | None = None
    building: str | None = None
    storey: str | None = None
    orientation_deg: float | None = None
    local_coordinate_system: str | None = None
    source_coordinate_reference: str | None = None
    scale_m_per_unit: float | None = 1.0

    def has_position(self) -> bool:
        return self.x_m is not None and self.y_m is not None and self.z_m is not None


@dataclass(frozen=True)
class CoordinateSystem:
    coordinate_system_id: str
    name: str
    units: str = "m"
    origin_x_m: float = 0.0
    origin_y_m: float = 0.0
    origin_z_m: float = 0.0
    orientation_deg: float = 0.0
    building: str | None = None
    storey: str | None = None
    local_coordinate_system: str | None = None
    source_coordinate_reference: str | None = None
    scale_m_per_unit: float | None = 1.0


@dataclass(frozen=True)
class MaterialRecord:
    material_id: str
    name: str
    category: MaterialCategory
    density_kg_per_m3: float | None = None
    thickness_m: float | None = None
    source: str | None = None
    evidence_class: EvidenceClass = "USER_SUPPLIED"
    confidence: Confidence = "UNKNOWN"


@dataclass(frozen=True)
class DerivedQuantityRecord:
    source_object_id: str
    quantity_type: QuantityUnitType
    value: float
    unit: QuantityValueUnit
    derivation_method: str
    evidence_class: EvidenceClass
    confidence: Confidence


@dataclass(frozen=True)
class ConstructionCostItem:
    quantity: float
    quantity_unit: str
    unit_cost: float | None
    currency: str
    cost_year: int | None
    geographic_basis: str | None
    material_system: str | None
    installation_basis: str | None
    source: str | None
    confidence: Confidence

    def total_cost(self) -> float | None:
        if self.unit_cost is None:
            return None
        return self.quantity * self.unit_cost


@dataclass(frozen=True)
class SpatialRelationship:
    relationship_type: RelationshipType
    source_object_id: str
    target_object_id: str
    evidence_class: EvidenceClass
    confidence: Confidence
    source: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class SpatialNode:
    node_id: str
    object_id: str | None
    kind: SpatialNodeKind
    coordinate: SpatialCoordinate | None
    evidence_class: EvidenceClass
    confidence: Confidence
    source_identifier: str | None = None
    building_id: str | None = None
    storey_id: str | None = None
    room_id: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SpatialEdge:
    edge_id: str
    source_node_id: str
    destination_node_id: str
    length_m: float
    vertical_change_m: float = 0.0
    edge_type: EdgeType = "OTHER"
    accessibility: SpatialAccessibility = "UNKNOWN"
    directionality: EdgeDirectionality = "BIDIRECTIONAL"
    evidence_class: EvidenceClass = "DERIVED_GEOMETRY"
    confidence: Confidence = "UNKNOWN"
    route_corridor_class: RouteCorridorClass = "UNCLASSIFIED"
    source_identifier: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeometryEvidenceAssessment:
    source_type: SpatialSourceType
    evidence_class: EvidenceClass
    geometry_confidence: Confidence
    material_confidence: Confidence
    validation_status: SpatialValidationStatus
    data_completeness: Literal["COMPLETE", "PARTIAL", "SPARSE", "UNKNOWN"] = "UNKNOWN"


@dataclass(frozen=True)
class SpaceFunctionAssignment:
    space_id: str
    source_name: str
    source_function: str
    proposed_name: str
    proposed_function: str
    assignment_status: ProgramAssignmentStatus
    suitability: SpaceSuitability = "UNKNOWN"
    structural_suitability: Literal["VERIFIED", "NOT_VERIFIED", "UNKNOWN"] = "UNKNOWN"
    shielding_suitability: Literal["VERIFIED", "NOT_VERIFIED", "UNKNOWN"] = "UNKNOWN"
    hvac_suitability: Literal["VERIFIED", "MODIFICATION_REQUIRED", "UNKNOWN"] = "UNKNOWN"
    recommendation: str | None = None


@dataclass(frozen=True)
class RequiredFacilityProgram:
    cyclotron_production_complex_required: int = 1
    radiopharmacy_required: int = 1
    qc_laboratory_required: int = 1
    injection_rooms_required: int = 0
    uptake_rooms_required: int = 0
    pet_ct_scanners_required: int = 0
    pet_mr_scanners_required: int = 0
    spect_ct_scanners_required: int = 0
    control_rooms_required: int = 0
    mrt_stations_required: int | None = None


@dataclass(frozen=True)
class ProgramFeasibilityReport:
    feasible: bool
    required_scanners: int
    available_scanner_spaces: int
    missing_scanner_spaces: int
    required_injection_rooms: int
    available_injection_spaces: int
    missing_injection_spaces: int
    required_uptake_rooms: int
    available_uptake_spaces: int
    missing_uptake_spaces: int
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class FacilityObject:
    object_id: str
    name: str
    source_identifier: str | None
    evidence_class: EvidenceClass
    confidence: Confidence
    status: ObjectStatus
    building_id: str | None = None
    storey_id: str | None = None
    zone_id: str | None = None
    room_id: str | None = None
    parent_id: str | None = None
    coordinate: SpatialCoordinate | None = None
    orientation_deg: float | None = None
    local_coordinate_system: str | None = None
    source_coordinate_reference: str | None = None
    material_ids: tuple[str, ...] = ()
    related_object_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Facility(FacilityObject):
    kind: Literal["Facility"] = "Facility"
    buildings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Building(FacilityObject):
    kind: Literal["Building"] = "Building"
    storeys: tuple[str, ...] = ()
    development_zone: DevelopmentZone = "UNKNOWN"


@dataclass(frozen=True)
class Storey(FacilityObject):
    kind: Literal["Storey"] = "Storey"
    elevation_m: float | None = None
    zones: tuple[str, ...] = ()
    spaces: tuple[str, ...] = ()


@dataclass(frozen=True)
class Zone(FacilityObject):
    kind: Literal["Zone"] = "Zone"
    spaces: tuple[str, ...] = ()


@dataclass(frozen=True)
class Space(FacilityObject):
    kind: Literal["Space"] = "Space"
    area_m2: float | None = None
    volume_m3: float | None = None
    access_class: SpatialAccessibility = "UNKNOWN"


@dataclass(frozen=True)
class Boundary(FacilityObject):
    kind: Literal["Boundary"] = "Boundary"
    boundary_type: Literal["ROOM", "ZONE", "SITE", "OTHER"] = "OTHER"


@dataclass(frozen=True)
class Wall(FacilityObject):
    kind: Literal["Wall"] = "Wall"
    thickness_m: float | None = None
    height_m: float | None = None
    length_m: float | None = None


@dataclass(frozen=True)
class Slab(FacilityObject):
    kind: Literal["Slab"] = "Slab"
    thickness_m: float | None = None
    area_m2: float | None = None
    volume_m3: float | None = None


@dataclass(frozen=True)
class Column(FacilityObject):
    kind: Literal["Column"] = "Column"
    width_m: float | None = None
    depth_m: float | None = None
    height_m: float | None = None


@dataclass(frozen=True)
class Beam(FacilityObject):
    kind: Literal["Beam"] = "Beam"
    width_m: float | None = None
    depth_m: float | None = None
    length_m: float | None = None


@dataclass(frozen=True)
class Door(FacilityObject):
    kind: Literal["Door"] = "Door"
    clear_width_m: float | None = None
    clear_height_m: float | None = None


@dataclass(frozen=True)
class Opening(FacilityObject):
    kind: Literal["Opening"] = "Opening"
    width_m: float | None = None
    height_m: float | None = None


@dataclass(frozen=True)
class Corridor(FacilityObject):
    kind: Literal["Corridor"] = "Corridor"
    length_m: float | None = None
    clear_width_m: float | None = None


@dataclass(frozen=True)
class Shaft(FacilityObject):
    kind: Literal["Shaft"] = "Shaft"
    cross_section_area_m2: float | None = None
    levels_served: tuple[str, ...] = ()


@dataclass(frozen=True)
class Stair(FacilityObject):
    kind: Literal["Stair"] = "Stair"
    rise_m: float | None = None
    run_m: float | None = None
    storeys_served: tuple[str, ...] = ()


@dataclass(frozen=True)
class Elevator(FacilityObject):
    kind: Literal["Elevator"] = "Elevator"
    capacity_persons: int | None = None
    storeys_served: tuple[str, ...] = ()


@dataclass(frozen=True)
class EquipmentPlacement(FacilityObject):
    kind: Literal["EquipmentPlacement"] = "EquipmentPlacement"
    equipment_class: EquipmentClass = "Other"
    catalog_identity: str | None = None
    facility_instance_id: str | None = None
    manufacturer_catalog_reference: str | None = None
    installation_clearance_m: float | None = None
    required_service_area_m2: float | None = None


@dataclass(frozen=True)
class FacilityEngineeringCapability:
    subscription_tier: SubscriptionTier
    allowed_spatial_sources: tuple[SpatialSourceType, ...]
    allowed_analysis_modes: tuple[str, ...]
    can_ingest_ifc: bool
    can_accept_revit_bim: bool
    can_accept_cad: bool
    can_accept_plan_derivation: bool
    can_accept_manual_definition: bool
    can_accept_templates: bool
    can_accept_benchmark_assumptions: bool


@dataclass(frozen=True)
class FacilityEngineeringObjectModel:
    facility_id: str
    facility_name: str
    project_spatial_mode: ProjectSpatialMode
    source_type: SpatialSourceType
    evidence_class: EvidenceClass
    maturity: SpatialMaturity
    subscription_tier: SubscriptionTier
    coordinate_system: CoordinateSystem
    adaptive_spatial_mode: AdaptiveSpatialMode = "GREENFIELD"
    spatial_input_path: SpatialInputPath = "MANUAL_SPATIAL_DEFINITION"
    geometry_evidence_assessment: GeometryEvidenceAssessment | None = None
    full_engineering_dataset_access: bool = False
    executive_summary_only: bool = True
    provenance: ProvenanceRecord | None = None
    facility: Facility | None = None
    buildings: tuple[Building, ...] = ()
    storeys: tuple[Storey, ...] = ()
    zones: tuple[Zone, ...] = ()
    spaces: tuple[Space, ...] = ()
    boundaries: tuple[Boundary, ...] = ()
    walls: tuple[Wall, ...] = ()
    slabs: tuple[Slab, ...] = ()
    columns: tuple[Column, ...] = ()
    beams: tuple[Beam, ...] = ()
    doors: tuple[Door, ...] = ()
    openings: tuple[Opening, ...] = ()
    corridors: tuple[Corridor, ...] = ()
    shafts: tuple[Shaft, ...] = ()
    stairs: tuple[Stair, ...] = ()
    elevators: tuple[Elevator, ...] = ()
    equipment: tuple[EquipmentPlacement, ...] = ()
    materials: tuple[MaterialRecord, ...] = ()
    relationships: tuple[SpatialRelationship, ...] = ()
    nodes: tuple[SpatialNode, ...] = ()
    edges: tuple[SpatialEdge, ...] = ()
    quantities: tuple[DerivedQuantityRecord, ...] = ()
    construction_cost_items: tuple[ConstructionCostItem, ...] = ()
    source_space_assignments: tuple[SpaceFunctionAssignment, ...] = ()
    proposed_space_assignments: tuple[SpaceFunctionAssignment, ...] = ()
    required_program: RequiredFacilityProgram | None = None
    feasibility_report: ProgramFeasibilityReport | None = None
    primary_route_origin_object_id: str | None = None
    primary_route_destination_object_ids: tuple[str, ...] = ()
    route_geometry_status: RouteGeometryStatus = "RECONSTRUCTED"
    route_distance_source: EvidenceClass = "DERIVED_GEOMETRY"
    clinical_floors_in_scope: int = 1
    scanner_floors: tuple[str, ...] = ()
    injection_floors: tuple[str, ...] = ()
    uptake_floors: tuple[str, ...] = ()
    include_ground_floor: bool = True
    production_building_id: str | None = None
    clinical_building_ids: tuple[str, ...] = ()
    enforce_cyclotron_ground_level: bool = True
    enforce_separate_production_building: bool = True
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SpatialValidationIssue:
    code: str
    severity: Literal["ERROR", "WARNING", "INFO"]
    message: str
    object_id: str | None = None


SOURCE_PROFILE_BY_TYPE: dict[SpatialSourceType, tuple[EvidenceClass, SpatialMaturity, SubscriptionTier]] = {
    "IFC": ("BIM_AUTHORITATIVE", "BIM_VERIFIED", "ENTERPRISE"),
    "REVIT_BIM": ("BIM_AUTHORITATIVE", "BIM_VERIFIED", "ENTERPRISE"),
    "DWG": ("CAD_ENGINEERING", "ENGINEERING", "PROFESSIONAL"),
    "DXF": ("CAD_ENGINEERING", "ENGINEERING", "PROFESSIONAL"),
    "PDF": ("PLAN_DERIVED", "PRELIMINARY", "PROFESSIONAL"),
    "IMAGE": ("PLAN_DERIVED", "PRELIMINARY", "PROFESSIONAL"),
    "MANUAL": ("USER_SUPPLIED", "CONCEPTUAL", "BASIC"),
    "TEMPLATE": ("TEMPLATE_DERIVED", "CONCEPTUAL", "BASIC"),
    "BENCHMARK": ("BENCHMARK_ASSUMED", "CONCEPTUAL", "BASIC"),
    "OTHER": ("USER_SUPPLIED", "CONCEPTUAL", "BASIC"),
}

SUBSCRIPTION_CAPABILITY_MAP: dict[SubscriptionTier, tuple[SpatialSourceType, ...]] = {
    "BASIC": ("MANUAL", "TEMPLATE", "BENCHMARK"),
    "PROFESSIONAL": ("MANUAL", "TEMPLATE", "BENCHMARK", "PDF", "IMAGE", "DWG", "DXF"),
    "ENTERPRISE": ("MANUAL", "TEMPLATE", "BENCHMARK", "PDF", "IMAGE", "DWG", "DXF", "IFC", "REVIT_BIM"),
}

SPATIAL_INPUT_PATH_OPTIONS: tuple[SpatialInputPath, ...] = (
    "UPLOAD_FACILITY_DOCUMENT",
    "MANUAL_SPATIAL_DEFINITION",
    "BENCHMARK_ASSUMED_FACILITY",
)

UPLOAD_SOURCE_OPTIONS: tuple[SpatialSourceType, ...] = (
    "IFC",
    "REVIT_BIM",
    "DWG",
    "DXF",
    "PDF",
)

SOURCE_FAMILY_LABELS: Mapping[SpatialSourceType, str] = {
    "IFC": "IFC / BIM",
    "REVIT_BIM": "Revit-derived BIM",
    "DWG": "CAD / DWG",
    "DXF": "CAD / DXF",
    "PDF": "PDF / Floor Plan",
    "IMAGE": "Image-derived plan",
    "MANUAL": "Manual spatial definition",
    "TEMPLATE": "Template-derived facility",
    "BENCHMARK": "Benchmark / assumed facility",
    "OTHER": "Other",
}


def resolve_default_source_profile(source_type: SpatialSourceType) -> tuple[EvidenceClass, SpatialMaturity, SubscriptionTier]:
    return SOURCE_PROFILE_BY_TYPE[source_type]


def resolve_source_type_for_input_path(input_path: SpatialInputPath, upload_source_type: SpatialSourceType | None = None) -> SpatialSourceType:
    if input_path == "UPLOAD_FACILITY_DOCUMENT":
        if upload_source_type is None:
            return "IFC"
        if upload_source_type not in UPLOAD_SOURCE_OPTIONS:
            raise ValueError("Upload source type must be IFC/REVIT_BIM/DWG/DXF/PDF")
        return upload_source_type
    if input_path == "MANUAL_SPATIAL_DEFINITION":
        return "MANUAL"
    if input_path == "BENCHMARK_ASSUMED_FACILITY":
        return "BENCHMARK"
    raise ValueError(f"Unsupported spatial input path: {input_path}")


def resolve_geometry_evidence_assessment(source_type: SpatialSourceType) -> GeometryEvidenceAssessment:
    evidence_class, _, _ = resolve_default_source_profile(source_type)
    if source_type in {"IFC", "REVIT_BIM"}:
        return GeometryEvidenceAssessment(
            source_type=source_type,
            evidence_class=evidence_class,
            geometry_confidence="HIGH",
            material_confidence="UNKNOWN",
            validation_status="WARNINGS",
            data_completeness="PARTIAL",
        )
    if source_type in {"DWG", "DXF"}:
        return GeometryEvidenceAssessment(
            source_type=source_type,
            evidence_class=evidence_class,
            geometry_confidence="MEDIUM",
            material_confidence="UNKNOWN",
            validation_status="INCOMPLETE",
            data_completeness="PARTIAL",
        )
    if source_type in {"PDF", "IMAGE"}:
        return GeometryEvidenceAssessment(
            source_type=source_type,
            evidence_class=evidence_class,
            geometry_confidence="LOW",
            material_confidence="UNKNOWN",
            validation_status="INCOMPLETE",
            data_completeness="SPARSE",
        )
    if source_type in {"BENCHMARK", "TEMPLATE"}:
        return GeometryEvidenceAssessment(
            source_type=source_type,
            evidence_class=evidence_class,
            geometry_confidence="LOW",
            material_confidence="UNKNOWN",
            validation_status="INCOMPLETE",
            data_completeness="SPARSE",
        )
    return GeometryEvidenceAssessment(
        source_type=source_type,
        evidence_class=evidence_class,
        geometry_confidence="MEDIUM",
        material_confidence="UNKNOWN",
        validation_status="INCOMPLETE",
        data_completeness="PARTIAL",
    )


def resolve_subscription_capability_profile(subscription_tier: SubscriptionTier) -> FacilityEngineeringCapability:
    allowed_sources = SUBSCRIPTION_CAPABILITY_MAP[subscription_tier]
    return FacilityEngineeringCapability(
        subscription_tier=subscription_tier,
        allowed_spatial_sources=allowed_sources,
        allowed_analysis_modes=("DESCRIPTIVE", "VALIDATION", "NETWORK_GEOMETRY", "QUANTITY_DERIVATION"),
        can_ingest_ifc="IFC" in allowed_sources,
        can_accept_revit_bim="REVIT_BIM" in allowed_sources,
        can_accept_cad="DWG" in allowed_sources or "DXF" in allowed_sources,
        can_accept_plan_derivation="PDF" in allowed_sources or "IMAGE" in allowed_sources,
        can_accept_manual_definition="MANUAL" in allowed_sources,
        can_accept_templates="TEMPLATE" in allowed_sources,
        can_accept_benchmark_assumptions="BENCHMARK" in allowed_sources,
    )


PRODUCTION_EQUIPMENT_CLASSES: tuple[EquipmentClass, ...] = (
    "Cyclotron",
    "Cyclotron vault",
    "Target area",
    "Hot cell",
    "Synthesis module",
    "QC laboratory",
    "Dispensing station",
    "Radiopharmacy",
    "Storage",
    "Radioactive waste area",
    "Airlock",
    "Change room",
)
CLINICAL_EQUIPMENT_CLASSES: tuple[EquipmentClass, ...] = (
    "Injection room",
    "Injection station/chair",
    "Uptake room",
    "PET/CT scanner",
    "PET/MR scanner",
    "SPECT/CT scanner",
    "Control room",
    "Patient preparation",
    "Waiting area",
    "Recovery area",
)
MRT_EQUIPMENT_CLASSES: tuple[EquipmentClass, ...] = (
    "MRT station",
    "Guideway endpoint",
    "Guideway segment",
    "Junction",
    "Horizontal/vertical transition",
    "Vertical shaft",
    "Loading point",
    "Unloading point",
    "Buffer",
)
ALL_EQUIPMENT_CLASSES: tuple[EquipmentClass, ...] = PRODUCTION_EQUIPMENT_CLASSES + CLINICAL_EQUIPMENT_CLASSES + MRT_EQUIPMENT_CLASSES + ("Other",)


def build_space_function_assignment(
    *,
    space_id: str,
    source_name: str,
    source_function: str,
    proposed_name: str,
    proposed_function: str,
    assignment_status: ProgramAssignmentStatus,
    suitability: SpaceSuitability = "UNKNOWN",
    structural_suitability: Literal["VERIFIED", "NOT_VERIFIED", "UNKNOWN"] = "UNKNOWN",
    shielding_suitability: Literal["VERIFIED", "NOT_VERIFIED", "UNKNOWN"] = "UNKNOWN",
    hvac_suitability: Literal["VERIFIED", "MODIFICATION_REQUIRED", "UNKNOWN"] = "UNKNOWN",
    recommendation: str | None = None,
) -> SpaceFunctionAssignment:
    return SpaceFunctionAssignment(
        space_id=space_id,
        source_name=source_name,
        source_function=source_function,
        proposed_name=proposed_name,
        proposed_function=proposed_function,
        assignment_status=assignment_status,
        suitability=suitability,
        structural_suitability=structural_suitability,
        shielding_suitability=shielding_suitability,
        hvac_suitability=hvac_suitability,
        recommendation=recommendation,
    )


def evaluate_required_program_feasibility(
    *,
    model: FacilityEngineeringObjectModel,
    required_program: RequiredFacilityProgram,
) -> ProgramFeasibilityReport:
    scanner_labels = {"PET/CT scanner", "PET/MR scanner", "SPECT/CT scanner"}
    injection_labels = {"Injection room", "Injection station/chair"}
    uptake_labels = {"Uptake room"}

    available_scanners = sum(1 for assignment in model.proposed_space_assignments if assignment.proposed_function in scanner_labels)
    available_injection = sum(1 for assignment in model.proposed_space_assignments if assignment.proposed_function in injection_labels)
    available_uptake = sum(1 for assignment in model.proposed_space_assignments if assignment.proposed_function in uptake_labels)

    required_scanners = (
        int(required_program.pet_ct_scanners_required)
        + int(required_program.pet_mr_scanners_required)
        + int(required_program.spect_ct_scanners_required)
    )
    missing_scanners = max(0, required_scanners - available_scanners)
    missing_injection = max(0, int(required_program.injection_rooms_required) - available_injection)
    missing_uptake = max(0, int(required_program.uptake_rooms_required) - available_uptake)

    feasible = missing_scanners == 0 and missing_injection == 0 and missing_uptake == 0
    notes: list[str] = []
    if missing_scanners > 0:
        notes.append(f"Required PET/SPECT scanners: {required_scanners}; maximum feasible in current model: {available_scanners}.")
    if missing_injection > 0:
        notes.append(f"Injection rooms missing: {missing_injection}.")
    if missing_uptake > 0:
        notes.append(f"Uptake rooms missing: {missing_uptake}.")

    return ProgramFeasibilityReport(
        feasible=feasible,
        required_scanners=required_scanners,
        available_scanner_spaces=available_scanners,
        missing_scanner_spaces=missing_scanners,
        required_injection_rooms=int(required_program.injection_rooms_required),
        available_injection_spaces=available_injection,
        missing_injection_spaces=missing_injection,
        required_uptake_rooms=int(required_program.uptake_rooms_required),
        available_uptake_spaces=available_uptake,
        missing_uptake_spaces=missing_uptake,
        notes=tuple(notes),
    )


def straight_line_distance_m(left: SpatialCoordinate, right: SpatialCoordinate) -> float:
    if not left.has_position() or not right.has_position():
        raise ValueError("straight line distance requires coordinates with x, y, and z")
    return dist((float(left.x_m), float(left.y_m), float(left.z_m)), (float(right.x_m), float(right.y_m), float(right.z_m)))


def network_route_distance_m(nodes: Mapping[str, SpatialNode], edges: Sequence[SpatialEdge], start_node_id: str, end_node_id: str) -> float:
    adjacency: dict[str, list[tuple[str, float]]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source_node_id, []).append((edge.destination_node_id, float(edge.length_m)))
        if edge.directionality in {"BIDIRECTIONAL", "ONE_WAY_REVERSE"}:
            adjacency.setdefault(edge.destination_node_id, []).append((edge.source_node_id, float(edge.length_m)))
        elif edge.directionality == "UNKNOWN":
            adjacency.setdefault(edge.destination_node_id, []).append((edge.source_node_id, float(edge.length_m)))

    visited: dict[str, float] = {start_node_id: 0.0}
    frontier: list[tuple[float, str]] = [(0.0, start_node_id)]
    while frontier:
        frontier.sort(reverse=True)
        current_distance, current = frontier.pop()
        if current == end_node_id:
            return current_distance
        for neighbor, edge_length in adjacency.get(current, []):
            candidate = current_distance + edge_length
            if neighbor not in visited or candidate < visited[neighbor]:
                visited[neighbor] = candidate
                frontier.append((candidate, neighbor))
    raise ValueError(f"No network route exists between {start_node_id} and {end_node_id}")


def validate_facility_engineering_object_model(model: FacilityEngineeringObjectModel) -> tuple[SpatialValidationIssue, ...]:
    issues: list[SpatialValidationIssue] = []
    seen_source_ids: set[str] = set()
    node_ids = {node.node_id for node in model.nodes}
    room_ids = {space.object_id for space in model.spaces}

    if model.source_type in {"DWG", "DXF", "PDF", "IMAGE"} and (model.coordinate_system.scale_m_per_unit is None or model.coordinate_system.scale_m_per_unit <= 0.0):
        issues.append(SpatialValidationIssue(code="MISSING_SCALE", severity="ERROR", message="A valid scale is required for non-authoritative drawing/image inputs."))

    if model.source_type == "IFC" and model.evidence_class != "BIM_AUTHORITATIVE":
        issues.append(SpatialValidationIssue(code="IFC_EVIDENCE_MISMATCH", severity="WARNING", message="IFC inputs should normally retain BIM_AUTHORITATIVE evidence."))

    if model.clinical_floors_in_scope < 1:
        issues.append(SpatialValidationIssue(code="INVALID_FLOOR_SCOPE", severity="ERROR", message="At least one clinical floor must be modeled."))

    for collection in (
        model.buildings,
        model.storeys,
        model.zones,
        model.spaces,
        model.boundaries,
        model.walls,
        model.slabs,
        model.columns,
        model.beams,
        model.doors,
        model.openings,
        model.corridors,
        model.shafts,
        model.stairs,
        model.elevators,
        model.equipment,
        model.nodes,
        model.edges,
    ):
        for item in collection:
            source_identifier = getattr(item, "source_identifier", None)
            if source_identifier:
                if source_identifier in seen_source_ids:
                    issues.append(SpatialValidationIssue(code="DUPLICATE_SOURCE_ID", severity="ERROR", message="Duplicate source identifier detected.", object_id=getattr(item, "object_id", None)))
                seen_source_ids.add(source_identifier)

    for item in (*model.equipment, *model.walls, *model.doors, *model.boundaries):
        if item.room_id is None:
            issues.append(SpatialValidationIssue(code="MISSING_FLOOR_ASSIGNMENT", severity="WARNING", message="Object does not carry a room/storey assignment.", object_id=item.object_id))
        elif item.room_id not in room_ids:
            issues.append(SpatialValidationIssue(code="EQUIPMENT_OUTSIDE_ROOM", severity="ERROR", message="Referenced room is not present in the facility model.", object_id=item.object_id))

    if model.spaces and not model.nodes:
        issues.append(SpatialValidationIssue(code="UNCONNECTED_ROOM", severity="WARNING", message="Space objects exist but no spatial graph nodes were provided."))

    if model.nodes:
        adjacency: dict[str, set[str]] = {node.node_id: set() for node in model.nodes}
        for edge in model.edges:
            adjacency.setdefault(edge.source_node_id, set()).add(edge.destination_node_id)
            if edge.directionality in {"BIDIRECTIONAL", "ONE_WAY_REVERSE", "UNKNOWN"}:
                adjacency.setdefault(edge.destination_node_id, set()).add(edge.source_node_id)
        reachable: set[str] = set()
        stack = [model.nodes[0].node_id]
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            stack.extend(adjacency.get(current, ()))
        unreachable = node_ids.difference(reachable)
        if unreachable:
            issues.append(SpatialValidationIssue(code="UNREACHABLE_SPATIAL_NODE", severity="WARNING", message=f"Unreachable spatial nodes: {sorted(unreachable)}"))

    if not model.materials:
        issues.append(SpatialValidationIssue(code="MISSING_MATERIAL", severity="INFO", message="No material records were supplied."))

    for item in model.construction_cost_items:
        if item.quantity_unit not in {"m", "m2", "m3", "count", "kg"}:
            issues.append(SpatialValidationIssue(code="INVALID_QUANTITY_UNIT", severity="ERROR", message=f"Invalid quantity unit: {item.quantity_unit}"))

    if model.facility is not None and not model.facility.buildings:
        issues.append(SpatialValidationIssue(code="INVALID_GEOMETRY", severity="WARNING", message="Facility object exists but contains no building references.", object_id=model.facility.object_id))

    if model.primary_route_origin_object_id is None:
        issues.append(SpatialValidationIssue(code="MISSING_ROUTE_ORIGIN", severity="WARNING", message="Primary route origin should be set to radiopharmacy release / MRT loading."))

    if model.route_geometry_status == "NOT_RECONSTRUCTED" and model.nodes and model.source_type == "MANUAL":
        issues.append(SpatialValidationIssue(code="MANUAL_DISTANCE_GEOMETRY_MISMATCH", severity="WARNING", message="Manual total-distance mode should not fabricate detailed node geometry."))

    if model.enforce_cyclotron_ground_level:
        storey_lookup = {storey.object_id: storey for storey in model.storeys}
        for equipment in model.equipment:
            if equipment.equipment_class != "Cyclotron":
                continue
            storey = storey_lookup.get(equipment.storey_id or "")
            storey_label = "" if storey is None else storey.name
            if not _is_ground_storey_label(storey_label, storey.elevation_m if storey is not None else None):
                issues.append(
                    SpatialValidationIssue(
                        code="CYCLOTRON_NOT_GROUND_LEVEL",
                        severity="ERROR",
                        message="Cyclotron must be placed at ground level under current project engineering constraints.",
                        object_id=equipment.object_id,
                    )
                )

    if model.enforce_separate_production_building and model.production_building_id:
        clinical_buildings = set(model.clinical_building_ids)
        if model.production_building_id in clinical_buildings:
            issues.append(
                SpatialValidationIssue(
                    code="PRODUCTION_BUILDING_NOT_SEPARATE",
                    severity="ERROR",
                    message="Production building must remain distinct from clinical building set under current MRT methodology.",
                    object_id=model.production_building_id,
                )
            )

    return tuple(issues)


def _is_ground_storey_label(storey_name: str, elevation_m: float | None) -> bool:
    normalized = storey_name.strip().lower()
    ground_aliases = {
        "ground",
        "ground floor",
        "g",
        "level 1",
        "floor 1",
        "l1",
        "storey 1",
        "story 1",
    }
    if normalized in ground_aliases:
        return True
    if elevation_m is not None and abs(float(elevation_m)) <= 0.25:
        return True
    return False


def _payload_get(payload: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    if payload is None:
        return default
    return payload.get(key, default)


def _coerce_nested_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    coerced = dict(payload)
    coordinate = coerced.get("coordinate")
    if isinstance(coordinate, Mapping):
        coerced["coordinate"] = SpatialCoordinate(**dict(coordinate))
    return coerced


def _load_tuple(payload: Mapping[str, Any] | None, key: str, item_type):
    raw_items = _payload_get(payload, key, ())
    if raw_items is None:
        return ()
    return tuple(item_type(**_coerce_nested_payload(dict(item))) if isinstance(item, Mapping) else item for item in raw_items)


def _load_optional_dataclass(payload: Mapping[str, Any] | None, key: str, cls):
    raw = _payload_get(payload, key)
    if raw is None:
        return None
    if isinstance(raw, cls):
        return raw
    if isinstance(raw, Mapping):
        return cls(**_coerce_nested_payload(raw))
    raise TypeError(f"Expected mapping for {key}")


def serialize_facility_engineering_object_model(model: FacilityEngineeringObjectModel) -> dict[str, Any]:
    return asdict(model)


def deserialize_facility_engineering_object_model(payload: Mapping[str, Any] | None) -> FacilityEngineeringObjectModel | None:
    if not payload:
        return None
    return FacilityEngineeringObjectModel(
        facility_id=str(payload["facility_id"]),
        facility_name=str(payload["facility_name"]),
        project_spatial_mode=payload["project_spatial_mode"],
        adaptive_spatial_mode=payload.get("adaptive_spatial_mode", payload["project_spatial_mode"]),
        spatial_input_path=payload.get("spatial_input_path", "MANUAL_SPATIAL_DEFINITION"),
        source_type=payload["source_type"],
        evidence_class=payload["evidence_class"],
        maturity=payload["maturity"],
        subscription_tier=payload["subscription_tier"],
        geometry_evidence_assessment=_load_optional_dataclass(payload, "geometry_evidence_assessment", GeometryEvidenceAssessment),
        coordinate_system=CoordinateSystem(**dict(payload["coordinate_system"])),
        full_engineering_dataset_access=bool(payload.get("full_engineering_dataset_access", False)),
        executive_summary_only=bool(payload.get("executive_summary_only", True)),
        provenance=_load_optional_dataclass(payload, "provenance", ProvenanceRecord),
        facility=_load_optional_dataclass(payload, "facility", Facility),
        buildings=_load_tuple(payload, "buildings", Building),
        storeys=_load_tuple(payload, "storeys", Storey),
        zones=_load_tuple(payload, "zones", Zone),
        spaces=_load_tuple(payload, "spaces", Space),
        boundaries=_load_tuple(payload, "boundaries", Boundary),
        walls=_load_tuple(payload, "walls", Wall),
        slabs=_load_tuple(payload, "slabs", Slab),
        columns=_load_tuple(payload, "columns", Column),
        beams=_load_tuple(payload, "beams", Beam),
        doors=_load_tuple(payload, "doors", Door),
        openings=_load_tuple(payload, "openings", Opening),
        corridors=_load_tuple(payload, "corridors", Corridor),
        shafts=_load_tuple(payload, "shafts", Shaft),
        stairs=_load_tuple(payload, "stairs", Stair),
        elevators=_load_tuple(payload, "elevators", Elevator),
        equipment=_load_tuple(payload, "equipment", EquipmentPlacement),
        materials=_load_tuple(payload, "materials", MaterialRecord),
        relationships=_load_tuple(payload, "relationships", SpatialRelationship),
        nodes=_load_tuple(payload, "nodes", SpatialNode),
        edges=_load_tuple(payload, "edges", SpatialEdge),
        quantities=_load_tuple(payload, "quantities", DerivedQuantityRecord),
        construction_cost_items=_load_tuple(payload, "construction_cost_items", ConstructionCostItem),
        source_space_assignments=_load_tuple(payload, "source_space_assignments", SpaceFunctionAssignment),
        proposed_space_assignments=_load_tuple(payload, "proposed_space_assignments", SpaceFunctionAssignment),
        required_program=_load_optional_dataclass(payload, "required_program", RequiredFacilityProgram),
        feasibility_report=_load_optional_dataclass(payload, "feasibility_report", ProgramFeasibilityReport),
        primary_route_origin_object_id=payload.get("primary_route_origin_object_id"),
        primary_route_destination_object_ids=tuple(payload.get("primary_route_destination_object_ids", ())),
        route_geometry_status=payload.get("route_geometry_status", "RECONSTRUCTED"),
        route_distance_source=payload.get("route_distance_source", "DERIVED_GEOMETRY"),
        clinical_floors_in_scope=int(payload.get("clinical_floors_in_scope", 1)),
        scanner_floors=tuple(payload.get("scanner_floors", ())),
        injection_floors=tuple(payload.get("injection_floors", ())),
        uptake_floors=tuple(payload.get("uptake_floors", ())),
        include_ground_floor=bool(payload.get("include_ground_floor", True)),
        production_building_id=payload.get("production_building_id"),
        clinical_building_ids=tuple(payload.get("clinical_building_ids", ())),
        enforce_cyclotron_ground_level=bool(payload.get("enforce_cyclotron_ground_level", True)),
        enforce_separate_production_building=bool(payload.get("enforce_separate_production_building", True)),
        notes=tuple(_payload_get(payload, "notes", ())),
    )


def build_default_facility_engineering_object_model(
    *,
    facility_id: str,
    facility_name: str,
    project_spatial_mode: ProjectSpatialMode,
    source_type: SpatialSourceType,
    subscription_tier: SubscriptionTier,
    coordinate_system: CoordinateSystem,
    spatial_input_path: SpatialInputPath = "MANUAL_SPATIAL_DEFINITION",
    adaptive_spatial_mode: AdaptiveSpatialMode | None = None,
    production_building_development_zone: DevelopmentZone | None = None,
    clinical_building_development_zone: DevelopmentZone | None = None,
    facility_instance_id: str | None = None,
    building_name: str = "Building A",
    clinical_building_name: str | None = None,
    storey_name: str = "Level 1",
    space_name: str = "Primary Room",
    space_id: str | None = None,
    equipment_class: EquipmentClass = "Other",
    equipment_name: str | None = None,
    route_distance_m: float | None = None,
    vertical_change_m: float | None = None,
    route_corridor_class: RouteCorridorClass = "INTERIOR_CLINICAL_PATH",
    route_geometry_status: RouteGeometryStatus = "RECONSTRUCTED",
    room_coordinate: SpatialCoordinate | None = None,
    clinical_floors_in_scope: int = 1,
    scanner_floors: Sequence[str] = (),
    injection_floors: Sequence[str] = (),
    uptake_floors: Sequence[str] = (),
    include_ground_floor: bool = True,
    enforce_cyclotron_ground_level: bool = True,
    enforce_separate_production_building: bool = True,
    materials: Sequence[MaterialRecord] = (),
    source_space_assignments: Sequence[SpaceFunctionAssignment] = (),
    proposed_space_assignments: Sequence[SpaceFunctionAssignment] = (),
    required_program: RequiredFacilityProgram | None = None,
    notes: Sequence[str] = (),
) -> FacilityEngineeringObjectModel:
    evidence_class, maturity, _ = resolve_default_source_profile(source_type)
    capability = resolve_subscription_capability_profile(subscription_tier)
    if source_type not in capability.allowed_spatial_sources:
        raise ValueError(f"Source type {source_type} is not available at subscription tier {subscription_tier}")

    if clinical_floors_in_scope < 1:
        raise ValueError("clinical_floors_in_scope must be at least 1")

    if adaptive_spatial_mode is None:
        adaptive_spatial_mode = "ADAPTIVE_REPURPOSING" if project_spatial_mode == "RETROFIT" else "GREENFIELD"

    if production_building_development_zone is None:
        production_building_development_zone = "EXISTING_CORE" if project_spatial_mode == "RETROFIT" else "NEW_BUILDING"
    if clinical_building_development_zone is None:
        clinical_building_development_zone = "EXPANSION_ZONE" if project_spatial_mode == "RETROFIT" and clinical_building_name else "NEW_BUILDING"

    geometry_assessment = resolve_geometry_evidence_assessment(source_type)

    facility = Facility(
        object_id=facility_id,
        name=facility_name,
        source_identifier=facility_id,
        evidence_class=evidence_class,
        confidence="MEDIUM",
        status="NEW_CANDIDATE" if project_spatial_mode == "GREENFIELD" else "PROTECTED",
        buildings=(f"{facility_id}:B1",) if not clinical_building_name else (f"{facility_id}:B1", f"{facility_id}:B2"),
    )
    building = Building(
        object_id=f"{facility_id}:B1",
        name=building_name,
        source_identifier=f"{facility_id}:B1",
        evidence_class=evidence_class,
        confidence="MEDIUM",
        status="NEW_CANDIDATE" if project_spatial_mode == "GREENFIELD" else "FIXED",
        parent_id=facility.object_id,
        storeys=(f"{facility_id}:S1",),
        development_zone=production_building_development_zone,
    )
    clinical_building: Building | None = None
    clinical_storey: Storey | None = None
    clinical_space: Space | None = None
    if clinical_building_name:
        clinical_building = Building(
            object_id=f"{facility_id}:B2",
            name=clinical_building_name,
            source_identifier=f"{facility_id}:B2",
            evidence_class=evidence_class,
            confidence="MEDIUM",
            status="FIXED" if project_spatial_mode == "RETROFIT" else "NEW_CANDIDATE",
            parent_id=facility.object_id,
            storeys=(f"{facility_id}:S2",),
            development_zone=clinical_building_development_zone,
        )
        clinical_storey = Storey(
            object_id=f"{facility_id}:S2",
            name="Clinical Level 1",
            source_identifier=f"{facility_id}:S2",
            evidence_class=evidence_class,
            confidence="MEDIUM",
            status="FIXED" if project_spatial_mode == "RETROFIT" else "NEW_CANDIDATE",
            building_id=clinical_building.object_id,
            parent_id=clinical_building.object_id,
            elevation_m=0.0,
            spaces=(f"{facility_id}:R2",),
        )
        clinical_space = Space(
            object_id=f"{facility_id}:R2",
            name="Clinical Destination",
            source_identifier=f"{facility_id}:R2",
            evidence_class=evidence_class,
            confidence="MEDIUM",
            status="MOVABLE",
            building_id=clinical_building.object_id,
            storey_id=clinical_storey.object_id,
            parent_id=clinical_storey.object_id,
            coordinate=room_coordinate,
            access_class="CONTROLLED",
        )
    storey = Storey(
        object_id=f"{facility_id}:S1",
        name=storey_name,
        source_identifier=f"{facility_id}:S1",
        evidence_class=evidence_class,
        confidence="MEDIUM",
        status="NEW_CANDIDATE" if project_spatial_mode == "GREENFIELD" else "FIXED",
        building_id=building.object_id,
        parent_id=building.object_id,
        elevation_m=0.0,
        spaces=(space_id or f"{facility_id}:R1",),
    )
    room_id = space_id or f"{facility_id}:R1"
    space = Space(
        object_id=room_id,
        name=space_name,
        source_identifier=room_id,
        evidence_class=evidence_class,
        confidence="MEDIUM",
        status="NEW_CANDIDATE" if project_spatial_mode == "GREENFIELD" else "MOVABLE",
        building_id=building.object_id,
        storey_id=storey.object_id,
        parent_id=storey.object_id,
        coordinate=room_coordinate,
        area_m2=None,
        volume_m3=None,
        access_class="CONTROLLED",
    )
    nodes = (
        SpatialNode(
            node_id=f"{facility_id}:N0",
            object_id=building.object_id,
            kind="corridor",
            coordinate=coordinate_system_to_coordinate(coordinate_system),
            evidence_class=evidence_class,
            confidence="LOW",
            source_identifier=building.object_id,
            building_id=building.object_id,
            storey_id=storey.object_id,
            room_id=None,
            notes=("Route origin / access reference.",),
        ),
        SpatialNode(
            node_id=f"{facility_id}:N1",
            object_id=space.object_id,
            kind="space",
            coordinate=room_coordinate,
            evidence_class=evidence_class,
            confidence="MEDIUM",
            source_identifier=room_id,
            building_id=building.object_id,
            storey_id=storey.object_id,
            room_id=space.object_id,
        ),
    )
    edges: tuple[SpatialEdge, ...] = ()
    if route_distance_m is not None:
        destination_node = nodes[1].node_id
        if clinical_space is not None:
            destination_node = f"{facility_id}:N2"
            nodes = (
                *nodes,
                SpatialNode(
                    node_id=destination_node,
                    object_id=clinical_space.object_id,
                    kind="space",
                    coordinate=room_coordinate,
                    evidence_class=evidence_class,
                    confidence="MEDIUM",
                    source_identifier=clinical_space.object_id,
                    building_id=clinical_space.building_id,
                    storey_id=clinical_space.storey_id,
                    room_id=clinical_space.object_id,
                ),
            )
        edges = (
            SpatialEdge(
                edge_id=f"{facility_id}:E1",
                source_node_id=nodes[0].node_id,
                destination_node_id=destination_node,
                length_m=float(route_distance_m),
                vertical_change_m=0.0 if vertical_change_m is None else float(vertical_change_m),
                edge_type="HORIZONTAL",
                accessibility="CONTROLLED",
                directionality="BIDIRECTIONAL",
                evidence_class="DERIVED_GEOMETRY",
                confidence="MEDIUM",
                route_corridor_class=route_corridor_class,
                source_identifier=facility_id,
            ),
        )
    equipment = (
        EquipmentPlacement(
            object_id=f"{facility_id}:EQ1",
            name=equipment_name or equipment_class,
            source_identifier=facility_instance_id or f"{facility_id}:EQ1",
            evidence_class=evidence_class,
            confidence="MEDIUM",
            status="FIXED" if project_spatial_mode == "RETROFIT" else "NEW_CANDIDATE",
            building_id=building.object_id,
            storey_id=storey.object_id,
            room_id=space.object_id,
            parent_id=space.object_id,
            coordinate=room_coordinate,
            orientation_deg=room_coordinate.orientation_deg if room_coordinate else None,
            local_coordinate_system=room_coordinate.local_coordinate_system if room_coordinate else None,
            source_coordinate_reference=room_coordinate.source_coordinate_reference if room_coordinate else None,
            equipment_class=equipment_class,
            catalog_identity=facility_instance_id,
            facility_instance_id=facility_instance_id,
            manufacturer_catalog_reference=facility_instance_id,
        ),
    )
    feasibility_report = None
    if required_program is not None:
        provisional_model = FacilityEngineeringObjectModel(
            facility_id=facility_id,
            facility_name=facility_name,
            project_spatial_mode=project_spatial_mode,
            source_type=source_type,
            evidence_class=evidence_class,
            maturity=maturity,
            subscription_tier=subscription_tier,
            coordinate_system=coordinate_system,
            proposed_space_assignments=tuple(proposed_space_assignments),
        )
        feasibility_report = evaluate_required_program_feasibility(model=provisional_model, required_program=required_program)

    return FacilityEngineeringObjectModel(
        facility_id=facility_id,
        facility_name=facility_name,
        project_spatial_mode=project_spatial_mode,
        adaptive_spatial_mode=adaptive_spatial_mode,
        spatial_input_path=spatial_input_path,
        source_type=source_type,
        evidence_class=evidence_class,
        maturity=maturity,
        subscription_tier=subscription_tier,
        geometry_evidence_assessment=geometry_assessment,
        coordinate_system=coordinate_system,
        full_engineering_dataset_access=subscription_tier in {"PROFESSIONAL", "ENTERPRISE"},
        executive_summary_only=subscription_tier == "BASIC",
        provenance=ProvenanceRecord(
            value=facility_name,
            source=source_type,
            evidence_class=evidence_class,
            confidence="MEDIUM",
            derivation_method="direct_input" if source_type in {"MANUAL", "TEMPLATE", "BENCHMARK"} else "ingested_source",
            user_override=source_type in {"MANUAL", "TEMPLATE", "BENCHMARK"},
        ),
        facility=facility,
        buildings=(building,) if clinical_building is None else (building, clinical_building),
        storeys=(storey,) if clinical_storey is None else (storey, clinical_storey),
        spaces=(space,) if clinical_space is None else (space, clinical_space),
        equipment=equipment,
        materials=tuple(materials),
        relationships=(
            SpatialRelationship(
                relationship_type="contained_in",
                source_object_id=equipment[0].object_id,
                target_object_id=space.object_id,
                evidence_class=evidence_class,
                confidence="HIGH",
                source=source_type,
            ),
        ),
        nodes=nodes,
        edges=edges,
        source_space_assignments=tuple(source_space_assignments),
        proposed_space_assignments=tuple(proposed_space_assignments),
        required_program=required_program,
        feasibility_report=feasibility_report,
        primary_route_origin_object_id=f"{facility_id}:RELEASE",
        primary_route_destination_object_ids=(space.object_id,) if clinical_space is None else (clinical_space.object_id,),
        route_geometry_status=route_geometry_status,
        route_distance_source="USER_SUPPLIED" if source_type == "MANUAL" else "DERIVED_GEOMETRY",
        clinical_floors_in_scope=int(clinical_floors_in_scope),
        scanner_floors=tuple(scanner_floors),
        injection_floors=tuple(injection_floors),
        uptake_floors=tuple(uptake_floors),
        include_ground_floor=include_ground_floor,
        production_building_id=building.object_id,
        clinical_building_ids=() if clinical_building is None else (clinical_building.object_id,),
        enforce_cyclotron_ground_level=enforce_cyclotron_ground_level,
        enforce_separate_production_building=enforce_separate_production_building,
        notes=tuple(notes),
    )


def coordinate_system_to_coordinate(coordinate_system: CoordinateSystem) -> SpatialCoordinate:
    return SpatialCoordinate(
        x_m=coordinate_system.origin_x_m,
        y_m=coordinate_system.origin_y_m,
        z_m=coordinate_system.origin_z_m,
        building=coordinate_system.building,
        storey=coordinate_system.storey,
        orientation_deg=coordinate_system.orientation_deg,
        local_coordinate_system=coordinate_system.local_coordinate_system,
        source_coordinate_reference=coordinate_system.source_coordinate_reference,
        scale_m_per_unit=coordinate_system.scale_m_per_unit,
    )


def migrate_legacy_geometry_state(saved_or_draft_state: Mapping[str, Any] | None) -> FacilityEngineeringObjectModel | None:
    if not saved_or_draft_state:
        return None
    payload = saved_or_draft_state.get("build3::facility_engineering::model")
    if isinstance(payload, Mapping):
        restored = deserialize_facility_engineering_object_model(payload)
        if restored is not None:
            return restored

    route_distance = saved_or_draft_state.get("build3::geometry::route_distance_m")
    floors = saved_or_draft_state.get("build3::geometry::floors", 1)
    vertical_transfer = saved_or_draft_state.get("build3::geometry::vertical_transfer_m", 0.0)
    if route_distance is None and floors is None and vertical_transfer is None:
        return None
    source_type = saved_or_draft_state.get("build3::facility_engineering::source_type", "MANUAL")
    if source_type not in SOURCE_PROFILE_BY_TYPE:
        source_type = "MANUAL"
    subscription_tier = saved_or_draft_state.get("build3::facility_engineering::subscription_tier", "BASIC")
    if subscription_tier not in SUBSCRIPTION_CAPABILITY_MAP:
        subscription_tier = "BASIC"
    project_spatial_mode = saved_or_draft_state.get("build3::facility_engineering::project_spatial_mode", "GREENFIELD")
    if project_spatial_mode not in {"RETROFIT", "GREENFIELD"}:
        project_spatial_mode = "GREENFIELD"
    spatial_input_path = saved_or_draft_state.get("build3::facility_engineering::input_path", "MANUAL_SPATIAL_DEFINITION")
    if spatial_input_path not in SPATIAL_INPUT_PATH_OPTIONS:
        spatial_input_path = "MANUAL_SPATIAL_DEFINITION"

    route_geometry_status = saved_or_draft_state.get("build3::facility_engineering::route_geometry_status", "RECONSTRUCTED")
    if route_geometry_status not in {"RECONSTRUCTED", "NOT_RECONSTRUCTED"}:
        route_geometry_status = "RECONSTRUCTED"

    coordinate_system = CoordinateSystem(
        coordinate_system_id=str(saved_or_draft_state.get("build3::facility_engineering::coordinate_system_id", "LOCAL-1")),
        name=str(saved_or_draft_state.get("build3::facility_engineering::coordinate_system_name", "Local engineering coordinates")),
        building=str(saved_or_draft_state.get("build3::facility_engineering::building_name", "Building A")),
        storey=str(saved_or_draft_state.get("build3::facility_engineering::storey_name", "Level 1")),
        local_coordinate_system=str(saved_or_draft_state.get("build3::facility_engineering::local_coordinate_system", "LOCAL")),
        source_coordinate_reference=str(saved_or_draft_state.get("build3::facility_engineering::source_coordinate_reference", "legacy geometry inputs")),
        scale_m_per_unit=1.0,
    )
    return build_default_facility_engineering_object_model(
        facility_id=str(saved_or_draft_state.get("build3::facility_engineering::facility_id", "FAC-001")),
        facility_name=str(saved_or_draft_state.get("build3::facility_engineering::facility_name", "Facility Engineering Model")),
        project_spatial_mode=project_spatial_mode,
        source_type=source_type,
        subscription_tier=subscription_tier,
        spatial_input_path=spatial_input_path,
        coordinate_system=coordinate_system,
        facility_instance_id=saved_or_draft_state.get("build3::facility_engineering::facility_instance_id"),
        building_name=str(saved_or_draft_state.get("build3::facility_engineering::building_name", "Building A")),
        storey_name=str(saved_or_draft_state.get("build3::facility_engineering::storey_name", "Level 1")),
        space_name=str(saved_or_draft_state.get("build3::facility_engineering::space_name", "Primary Room")),
        space_id=saved_or_draft_state.get("build3::facility_engineering::space_id"),
        equipment_class=saved_or_draft_state.get("build3::facility_engineering::equipment_class", "Other"),
        equipment_name=saved_or_draft_state.get("build3::facility_engineering::equipment_name"),
        route_distance_m=float(route_distance) if route_distance is not None else None,
        vertical_change_m=float(vertical_transfer) if vertical_transfer is not None else None,
        route_geometry_status=route_geometry_status,
        clinical_floors_in_scope=int(saved_or_draft_state.get("build3::geometry::floors", 1) or 1),
        include_ground_floor=bool(saved_or_draft_state.get("build3::facility_engineering::ground_floor_included", True)),
        scanner_floors=tuple(saved_or_draft_state.get("build3::facility_engineering::scanner_floors", ())),
        injection_floors=tuple(saved_or_draft_state.get("build3::facility_engineering::injection_floors", ())),
        uptake_floors=tuple(saved_or_draft_state.get("build3::facility_engineering::uptake_floors", ())),
        room_coordinate=SpatialCoordinate(
            x_m=_safe_float(saved_or_draft_state.get("build3::facility_engineering::x_m")),
            y_m=_safe_float(saved_or_draft_state.get("build3::facility_engineering::y_m")),
            z_m=_safe_float(saved_or_draft_state.get("build3::facility_engineering::z_m")),
            orientation_deg=_safe_float(saved_or_draft_state.get("build3::facility_engineering::orientation_deg")),
            local_coordinate_system=str(saved_or_draft_state.get("build3::facility_engineering::local_coordinate_system", "LOCAL")),
            source_coordinate_reference=str(saved_or_draft_state.get("build3::facility_engineering::source_coordinate_reference", "legacy geometry inputs")),
        ),
        notes=tuple(saved_or_draft_state.get("build3::facility_engineering::notes", ())),
    )


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

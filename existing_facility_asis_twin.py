"""EXISTING FACILITY / AS-IS DIGITAL TWIN -- PHASE 1B.

The FIRST executable AS-IS foundation. This module is a NARROW
ORCHESTRATION / NORMALIZATION authority. It does NOT own geometry, equipment,
routing, simulation, or scenario engines -- it CONSUMES the existing canonical
authorities and normalizes already-structured, project-supplied facility facts
into them.

Scope of Phase 1B (deliberately narrow):
  * ONE ingestion path only: MANUAL / PROJECT-SUPPLIED STRUCTURED INGESTION.
    Callers hand over already-structured facts (buildings/floors/rooms/coords/
    equipment identities/placements). There is NO parser here:
      - NO IFC/DWG/DXF/PDF/image/OCR/point-cloud/GIS ingestion,
      - NO automatic wall/room/equipment recognition,
      - NO intelligent reconstruction.
  * Normalize into the EXISTING canonical authorities (never a parallel model):
      - canonical_spatial_authority (CanonicalSpatialObject / SpatialObjectRegistry),
      - cyclotron/generator/scanner catalogs (facility equipment instances),
      - canonical_spatial_authority.engineering_object_id as the geometry<->equipment bridge,
      - ProvenancedField (cyclotron_catalog) for field-level evidence,
      - ClinicalResourceInputs.resource_source (Part 3D) provenance semantics.
  * Produce an explicit COMPLETENESS / GAP assessment (the one genuinely new
    artifact).
  * HARD GOVERNOR: never silently substitute controlled BENCHMARK facts as real
    hospital facts. Missing facts stay MISSING / NOT_MODELED / NOT_CALIBRATED.

Explicitly OUT OF SCOPE for Phase 1B (seams only, not implemented):
  * operational-state reconstruction (patients/appointments/batches/calendars/rosters),
  * baseline simulation,
  * LOCKDOWN creation and What-If lineage,
  * BIM/IFC/Bentley/USD real-hospital ingestion (proof code only exists).

The intended future sequence -- preserved as a seam, never bypassed:
  Evidence -> Normalized AS-IS objects -> Validation / unresolved gaps
  -> Operational-state reconstruction -> Baseline simulation -> LOCKDOWN -> What-If.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, Mapping, Sequence

from canonical_spatial_authority import (
    CanonicalSpatialObject,
    NormalizedImportResult,
    SpatialObjectRegistry,
    SpatialObjectType,
    Transform,
    add_building,
    add_floor,
    add_room,
    build_facility_hierarchy,
    normalize_blank_manual_import,
)
from cyclotron_catalog import (
    FacilityCyclotronInstance,
    load_cyclotron_catalog,
)
from generator_catalog import (
    FacilityGeneratorInstance,
    load_generator_catalog,
)
from scanner_catalog import (
    FacilityScannerInstance,
    ScannerModality,
    load_scanner_catalog,
)
from whole_oncology_four_architecture_optimization import ProjectStartingState

# ---------------------------------------------------------------------------
# Sec 15-16: PROVENANCE (origin) vs CALIBRATION/CONFIDENCE (reliability).
# We REUSE the repository's existing vocabularies rather than inventing a
# second hierarchy: resource_source semantics from Part 3D
# (PROJECT_SUPPLIED / FACILITY_DERIVED / CONTROLLED_BENCHMARK) extended with the
# facility-import/measured/external/inferred origins the canonical spatial
# Provenance enum already expresses, plus the NOT_CALIBRATED sentinel used
# everywhere. These are ORIGIN answers only -- kept distinct from calibration.
# ---------------------------------------------------------------------------
AsIsProvenance = Literal[
    "PROJECT_SUPPLIED",       # a project/consultant supplied the structured fact
    "FACILITY_SUPPLIED",      # the facility itself supplied the fact
    "FACILITY_DERIVED",       # derived from other facility-supplied facts
    "MEASURED",               # physically measured on site
    "EXTERNAL_SOURCE",        # an external system/API/document supplied it
    "INFERRED",               # reconstructed/inferred (NOT used to fabricate in 1B)
    "CONTROLLED_ASSUMPTION",  # an explicit, labeled controlled assumption/benchmark
    "MISSING",                # the fact was not supplied at all
]

# Sec 15/19: how strongly a quantitative fact can be relied upon. Distinct axis
# from provenance -- a PROJECT_SUPPLIED fact may still be NOT_CALIBRATED.
AsIsCalibration = Literal[
    "CALIBRATED",
    "PARTIALLY_CALIBRATED",
    "NOT_CALIBRATED",
    "NOT_APPLICABLE",
]

AsIsConfidence = Literal["high", "medium", "low", "unknown"]


@dataclass(frozen=True)
class AsIsFieldEvidence:
    """Sec 16: FIELD-LEVEL evidence. Origin and calibration are independent
    axes so a single record is never falsely promoted to one status when its
    fields have different origins (e.g. room geometry FACILITY_SUPPLIED but
    room function MISSING). Conceptually mirrors the canonical `ProvenancedField`
    4-axis record; kept as a small AS-IS-facing view so ingestion DTOs never
    import engine internals."""

    fact: str
    provenance: AsIsProvenance
    calibration: AsIsCalibration = "NOT_APPLICABLE"
    confidence: AsIsConfidence = "unknown"
    note: str | None = None


# ===========================================================================
# PHASE 1C -- FACILITY ENGINEERING OBJECT MODEL & COMPLETENESS CLOSURE.
# All types below are ADDITIVE, frozen read-models that STRENGTHEN the Phase 1B
# normalized result WITHOUT creating a parallel facility/spatial/equipment/
# routing engine. Every one is a VIEW over, or a narrow companion to, the
# existing canonical authorities (canonical_spatial_authority, the equipment
# catalogs, ProvenancedField, EngineeringEvidenceConflict). See the Phase 1C
# doctrine (Sec 4): the eleven twin domains stay independent but linked.
# ===========================================================================

# ---- Sec 5: FACILITY HIERARCHY (explicit, queryable) ----
# The canonical spatial authority owns FACILITY/BUILDING/FLOOR/ROOM object_types
# (no SITE/CAMPUS object_type). SITE/CAMPUS remain identity-only metadata on
# AsIsFacilityIdentityInput; the hierarchy view surfaces them without requiring
# a campus layer where none exists (Sec 5).
AsIsFacilityLevel = Literal["FACILITY", "SITE", "CAMPUS", "BUILDING", "FLOOR", "ROOM"]


@dataclass(frozen=True)
class AsIsHierarchyNode:
    """Sec 5: one explicit, queryable node in the facility hierarchy. IDs are
    the SAME stable canonical `mrtway_object_id`s -- never array positions.
    Room identity survives geometry changes; equipment identity is NOT stored
    here (it is a separate domain, Sec 8-9)."""

    object_id: str
    level: AsIsFacilityLevel
    parent_object_id: str | None
    child_object_ids: tuple[str, ...]


@dataclass(frozen=True)
class AsIsFacilityHierarchyView:
    """Sec 5: a read-only VIEW over the canonical `SpatialObjectRegistry`. It
    does not own geometry; it exposes parentage/queryability. `site_id`/
    `campus_id` are carried from facility identity (optional; absent where the
    facility has no campus)."""

    facility_id: str
    site_id: str | None
    campus_id: str | None
    nodes: tuple[AsIsHierarchyNode, ...]

    def node(self, object_id: str) -> AsIsHierarchyNode | None:
        return next((n for n in self.nodes if n.object_id == object_id), None)

    def nodes_at_level(self, level: AsIsFacilityLevel) -> tuple[AsIsHierarchyNode, ...]:
        return tuple(n for n in self.nodes if n.level == level)


# ---- Sec 6-7: CLINICAL SPACE CLASSIFICATION (authority separate from geometry) ----
# A superset of AsIsRoomFunction with the additional physically-justified
# functions Sec 6 enumerates. Kept on a DIFFERENT axis from the canonical
# geometry `object_type` (Sec 7): changing a room's clinical function must never
# require replacing its spatial identity, and changing geometry must never
# silently change function.
AsIsClinicalSpaceClassification = Literal[
    "RADIOPHARMACY", "CYCLOTRON_ROOM", "GENERATOR_AREA", "INJECTION_ROOM", "UPTAKE_ROOM",
    "COMBINED_INJECTION_UPTAKE", "PET_SCANNER_ROOM", "SPECT_SCANNER_ROOM", "NUCLEAR_MEDICINE_ROOM",
    "INPATIENT_ROOM", "OUTPATIENT_ROOM", "CORRIDOR", "ELEVATOR", "STAIR", "MECHANICAL", "STORAGE",
    "CONTROL_ROOM", "OTHER", "UNKNOWN", "NOT_MODELED",
]

# DERIVATION from the Phase 1B AsIsRoomFunction (only where a function was
# explicitly supplied). Never guessed from a room name. A room function of
# UNKNOWN maps to classification UNKNOWN (Sec 7: known geometry + unknown
# function is legal).
_ROOM_FUNCTION_TO_CLASSIFICATION: Mapping["AsIsRoomFunction", AsIsClinicalSpaceClassification] = {
    "UNKNOWN": "UNKNOWN",
    "INJECTION_ROOM": "INJECTION_ROOM",
    "UPTAKE_ROOM": "UPTAKE_ROOM",
    "PET_SCANNER": "PET_SCANNER_ROOM",
    "SPECT_SCANNER": "SPECT_SCANNER_ROOM",
    "NUCLEAR_MEDICINE_ROOM": "NUCLEAR_MEDICINE_ROOM",
    "RADIOPHARMACY": "RADIOPHARMACY",
    "CYCLOTRON": "CYCLOTRON_ROOM",
    "CONTROL_ROOM": "CONTROL_ROOM",
    "PATIENT_ROOM": "INPATIENT_ROOM",
    "STORAGE": "STORAGE",
    "UTILITY_SPACE": "MECHANICAL",
}

AsIsClassificationStatus = Literal["KNOWN", "UNKNOWN", "NOT_MODELED", "CONFLICTED"]


@dataclass(frozen=True)
class AsIsSpaceClassificationBinding:
    """Sec 6-7: the explicit `spatial_object_id -> clinical function` binding,
    held on its OWN axis from geometry. `status` distinguishes a genuinely-known
    function from an unknown/absent one; a room may have complete geometry and a
    NOT_MODELED/UNKNOWN classification simultaneously (Sec 27)."""

    spatial_object_id: str
    classification: AsIsClinicalSpaceClassification
    status: AsIsClassificationStatus
    provenance: AsIsProvenance
    calibration: AsIsCalibration = "NOT_APPLICABLE"


# ---- Sec 8-10: EQUIPMENT IDENTITY != PLACEMENT (binding read-model) ----
AsIsBindingStatus = Literal["BOUND", "UNRESOLVED"]
AsIsBindingValidation = Literal["VALIDATED", "UNVALIDATED", "NOT_APPLICABLE"]


@dataclass(frozen=True)
class AsIsEquipmentSpatialBinding:
    """Sec 9-10: the queryable equipment<->space binding read-model over the
    canonical `CanonicalSpatialObject.engineering_object_id` scalar bridge. A
    future drag/drop move changes `spatial_object_id` WITHOUT changing
    `equipment_instance_id` (Sec 9). Identity is never destroyed when placement
    is UNRESOLVED; placement is never fabricated."""

    equipment_instance_id: str
    equipment_class: "AsIsEquipmentClass"
    spatial_object_id: str | None
    binding_status: AsIsBindingStatus
    source: AsIsProvenance
    validation_status: AsIsBindingValidation


# ---- Sec 11-12: CONNECTIVITY / TOPOLOGY (view over canonical graph) ----
AsIsRouteReadiness = Literal["TOPOLOGY_COMPLETE", "TOPOLOGY_PARTIAL", "TOPOLOGY_NOT_MODELED"]


@dataclass(frozen=True)
class AsIsConnectivityLink:
    """Sec 11: one supplied physical connection, normalized as a VIEW over a
    canonical `SpatialEdge`. `length_m` is None/NOT_CALIBRATED when a distance
    was not supplied -- NEVER computed from coordinates (Sec 12/29)."""

    from_object_id: str
    to_object_id: str
    length_calibrated: bool
    provenance: AsIsProvenance


@dataclass(frozen=True)
class AsIsConnectivityView:
    """Sec 11-12: AS-IS connectivity as topology-only data (a thin view over the
    canonical `ConnectivityGraph`), explicitly SEPARATE from transport-physics
    route-time. `route_readiness` reflects whether supplied topology covers the
    modeled spaces -- geometry completeness does NOT imply connectivity (Sec
    12/29). No route distances are fabricated; no travel time is computed."""

    links: tuple[AsIsConnectivityLink, ...]
    route_readiness: AsIsRouteReadiness
    supplied_connection_count: int
    connectable_space_count: int
    # Sec 12: these MUST always be False for the AS-IS twin -- topology authority
    # only; transport physics is a downstream authority.
    route_distance_fabricated: bool = False
    transport_time_calculated: bool = False


# ---- Sec 13-14: OPERATIONAL RESOURCE PLACEHOLDERS + MRT infra control ----
AsIsResourceCategory = Literal[
    "SCANNER", "PRODUCTION_CYCLOTRON", "GENERATOR", "STAFFING", "TRANSPORT", "MRT_CARRIER_ENDPOINT",
]
AsIsResourceIdentityStatus = Literal["IDENTITY_PRESENT", "IDENTITY_ABSENT"]


@dataclass(frozen=True)
class AsIsOperationalResourcePlaceholder:
    """Sec 13: an explicit SEAM for an operational-resource identity. Resource
    IDENTITY may be present while operational STATE remains unknown -- Phase 1C
    reconstructs NO schedules/calendars/rosters/dispatch (Sec 13/21)."""

    resource_category: AsIsResourceCategory
    identity_status: AsIsResourceIdentityStatus
    identity_count: int
    operational_state_reconstructed: bool = False


# ---- Sec 16-17: EVIDENCE CONFLICT (AS-IS-facing read-model) ----
# Mirrors engineering_evidence.EngineeringEvidenceConflict's shape (candidate
# values + sources + resolution status) but scoped to AS-IS facility facts, so
# ingestion DTOs never import the RAG/claim repository internals.
AsIsConflictResolutionStatus = Literal[
    "UNRESOLVED", "RESOLVED_BY_FACILITY", "RESOLVED_BY_MEASUREMENT", "RESOLVED_BY_PROJECT_AUTHORITY",
]


@dataclass(frozen=True)
class AsIsEvidenceConflict:
    """Sec 16-17: two independently sourced facts disagree on ONE field of ONE
    object. Both candidates are preserved; NEITHER is silently overwritten,
    last-write-wins, or auto-resolved to the "more plausible" value. An
    UNRESOLVED conflict reduces simulation readiness (Sec 17)."""

    conflict_id: str
    domain: "AsIsTwinDomain"
    object_id: str
    field_name: str
    candidate_values: tuple[str, ...]
    candidate_sources: tuple[AsIsProvenance, ...]
    resolution_status: AsIsConflictResolutionStatus = "UNRESOLVED"
    selected_value: str | None = None
    resolution_source: AsIsProvenance | None = None
    impact_on_readiness: Literal["NONE", "REDUCES_READINESS"] = "REDUCES_READINESS"


# ---- Sec 18-19: DOMAIN COMPLETENESS ----
AsIsTwinDomain = Literal[
    "FACILITY_IDENTITY", "SPATIAL_HIERARCHY", "GEOMETRY", "CLINICAL_SPACE_CLASSIFICATION",
    "ENGINEERING_OBJECT_IDENTITY", "EQUIPMENT_PLACEMENT", "CONNECTIVITY_TOPOLOGY",
    "OPERATIONAL_RESOURCE_IDENTITY", "PROVENANCE", "CALIBRATION", "EVIDENCE_CONFLICTS",
    "OPERATIONAL_STATE", "SIMULATION_READINESS",
]

AsIsDomainStatus = Literal["COMPLETE", "PARTIAL", "NOT_MODELED", "CONFLICTED", "NOT_APPLICABLE"]


@dataclass(frozen=True)
class AsIsDomainCompleteness:
    """Sec 19: a frozen per-domain assessment -- never collapsed to one count."""

    domain: AsIsTwinDomain
    status: AsIsDomainStatus
    known_count: int = 0
    unknown_count: int = 0
    conflict_count: int = 0
    blocking_gap_count: int = 0
    nonblocking_gap_count: int = 0
    readiness_impact: Literal["NONE", "NONBLOCKING", "BLOCKING"] = "NONE"
    evidence_summary: str | None = None


# ---- Sec 20: OVERALL READINESS GATES (distinct, monotonic progression) ----
AsIsReadinessLevel = Literal[
    "NORMALIZED",
    "STRUCTURALLY_RECONSTRUCTABLE",
    "ENGINEERING_MODEL_PARTIAL",
    "READY_FOR_OPERATIONAL_STATE_RECONSTRUCTION",
    "READY_FOR_BASELINE_SIMULATION",
]


@dataclass(frozen=True)
class AsIsReadinessGates:
    """Sec 20: the FIVE distinct readiness concepts -- NOT equivalent. A later
    gate is never True unless every earlier gate is True (monotonic). Phase 1C
    is pre-simulation, so `baseline_simulation_ready` is always False and
    `operational_state_reconstruction_ready` is always False (Sec 21-22)."""

    normalization_succeeded: bool
    structural_reconstruction_ready: bool
    engineering_object_model_ready: bool
    operational_state_reconstruction_ready: bool
    baseline_simulation_ready: bool
    overall_readiness_level: AsIsReadinessLevel


# ===========================================================================
# Sec 9-14: STRUCTURED INGESTION DTOs (temporary ingestion contracts).
# These are NOT the engineering authority -- they normalize INTO canonical
# objects. Every DTO uses stable IDs; no anonymous positional objects.
# ===========================================================================


@dataclass(frozen=True)
class AsIsFacilityIdentityInput:
    """Sec 10: facility identity, distinct from project/scenario identity.
    Street address / geolocation are NOT required to build the engineering
    twin, and facility metadata is never invented."""

    facility_id: str
    facility_name: str
    site_id: str | None = None
    campus_id: str | None = None


@dataclass(frozen=True)
class AsIsBuildingInput:
    building_id: str
    building_name: str | None = None
    transform: Transform = field(default_factory=Transform)


@dataclass(frozen=True)
class AsIsFloorInput:
    building_id: str
    floor_id: str
    elevation_m: float | None = None
    transform: Transform = field(default_factory=Transform)


# Sec 11: room clinical function is OPTIONAL and, when unknown, is NEVER
# inferred from the room name. UNKNOWN is a first-class value.
AsIsRoomFunction = Literal[
    "UNKNOWN",
    "INJECTION_ROOM",
    "UPTAKE_ROOM",
    "PET_SCANNER",
    "SPECT_SCANNER",
    "NUCLEAR_MEDICINE_ROOM",
    "RADIOPHARMACY",
    "CYCLOTRON",
    "CONTROL_ROOM",
    "PATIENT_ROOM",
    "STORAGE",
    "UTILITY_SPACE",
]

# Maps a KNOWN AS-IS room function to the canonical SpatialObjectType. Unknown
# function -> generic function-neutral "ROOM" (never guessed from a name).
_ROOM_FUNCTION_TO_OBJECT_TYPE: Mapping[AsIsRoomFunction, SpatialObjectType] = {
    "UNKNOWN": "ROOM",
    "INJECTION_ROOM": "INJECTION_ROOM",
    "UPTAKE_ROOM": "UPTAKE_ROOM",
    "PET_SCANNER": "PET_SCANNER",
    "SPECT_SCANNER": "SPECT_SCANNER",
    "NUCLEAR_MEDICINE_ROOM": "NUCLEAR_MEDICINE_ROOM",
    "RADIOPHARMACY": "RADIOPHARMACY",
    "CYCLOTRON": "CYCLOTRON",
    "CONTROL_ROOM": "CONTROL_ROOM",
    "PATIENT_ROOM": "PATIENT_ROOM",
    "STORAGE": "STORAGE",
    "UTILITY_SPACE": "UTILITY_SPACE",
}


@dataclass(frozen=True)
class AsIsRoomInput:
    """Sec 11: a structured room. Geometry (transform/dimensions) is kept
    separate from clinical function; function may be UNKNOWN. Provenance is
    carried per relevant fact.

    Phase 1C (Sec 6-7): `clinical_space_classification` is the OPTIONAL, explicit
    clinical-function fact kept on a DIFFERENT axis from geometry. Left None it
    is DERIVED from `room_function` (backward compatible with Phase 1B); it is
    NEVER inferred from the room name/id. Known geometry with an UNKNOWN/absent
    classification remains legal (Sec 7)."""

    building_id: str
    floor_id: str
    room_id: str
    transform: Transform = field(default_factory=Transform)
    length_m: float | None = None
    width_m: float | None = None
    height_m: float | None = None
    room_function: AsIsRoomFunction = "UNKNOWN"
    geometry_provenance: AsIsProvenance = "PROJECT_SUPPLIED"
    function_provenance: AsIsProvenance = "PROJECT_SUPPLIED"
    # Phase 1C (Sec 6): explicit clinical-space classification, distinct axis
    # from geometry `object_type`. None -> derived from room_function.
    clinical_space_classification: "AsIsClinicalSpaceClassification | None" = None
    classification_provenance: AsIsProvenance = "PROJECT_SUPPLIED"


# Sec 12: equipment class. Identity is decoupled from geometry and from
# placement. Equipment is NEVER created merely because the benchmark contains it.
AsIsEquipmentClass = Literal["CYCLOTRON", "GENERATOR", "PET_SCANNER", "SPECT_SCANNER"]


@dataclass(frozen=True)
class AsIsEquipmentInput:
    """Sec 12: a structured equipment instance. `catalog_model_id` references
    the existing catalog identity (validated on normalization -- an invalid
    reference is an ingestion failure). Placement lives on a separate DTO."""

    equipment_instance_id: str
    equipment_class: AsIsEquipmentClass
    catalog_model_id: str
    modality: ScannerModality | None = None  # required only for scanners
    identity_provenance: AsIsProvenance = "PROJECT_SUPPLIED"


@dataclass(frozen=True)
class AsIsEquipmentPlacementInput:
    """Sec 13: a binding equipment_instance_id -> room/spatial_object_id.
    Known equipment with unknown location is allowed (a completeness gap, not
    a failure) simply by omitting a placement for that instance."""

    equipment_instance_id: str
    room_id: str
    placement_provenance: AsIsProvenance = "PROJECT_SUPPLIED"


@dataclass(frozen=True)
class AsIsRouteOrConnectivityInput:
    """Sec 14: OPTIONAL explicit connectivity. If absent, the gap is reported;
    benchmark route distances are NEVER substituted as facility-derived truth.
    Phase 1B does not run or redesign transport physics here."""

    from_object_id: str
    to_object_id: str
    length_m: float | None = None
    provenance: AsIsProvenance = "PROJECT_SUPPLIED"


@dataclass(frozen=True)
class AsIsConflictingEvidenceInput:
    """Phase 1C (Sec 16-17): a SECOND, independently sourced fact about an
    already-supplied object/field. Supplying one alongside the primary room
    fact creates a deterministic contradiction control: both candidates are
    preserved, neither is silently overwritten, and readiness is reduced until
    the conflict is explicitly resolved (never auto-resolved)."""

    object_id: str
    field_name: str
    candidate_value: str
    source: AsIsProvenance = "EXTERNAL_SOURCE"


@dataclass(frozen=True)
class AsIsStructuredFacilityInput:
    """Sec 9: the top-level structured ingestion contract for the manual path."""

    facility: AsIsFacilityIdentityInput
    buildings: tuple[AsIsBuildingInput, ...] = ()
    floors: tuple[AsIsFloorInput, ...] = ()
    rooms: tuple[AsIsRoomInput, ...] = ()
    equipment: tuple[AsIsEquipmentInput, ...] = ()
    equipment_placements: tuple[AsIsEquipmentPlacementInput, ...] = ()
    routes: tuple[AsIsRouteOrConnectivityInput, ...] = ()
    # Phase 1C (Sec 16-17): optional independently sourced contradicting facts.
    conflicting_evidence: tuple[AsIsConflictingEvidenceInput, ...] = ()


# ===========================================================================
# Sec 18-19: COMPLETENESS / GAP AUTHORITY.
# ===========================================================================
AsIsGapDomain = Literal[
    "FACILITY_IDENTITY",
    "GEOMETRY",
    "ROOM_FUNCTION",
    "EQUIPMENT_IDENTITY",
    "EQUIPMENT_PLACEMENT",
    "CONNECTIVITY",
    "OPERATIONAL_RESOURCES",
    "PROVENANCE",
    "CALIBRATION",
    "SIMULATION_READINESS",
]

AsIsGapStatus = Literal["MISSING", "NOT_MODELED", "NOT_CALIBRATED", "UNRESOLVED"]

AsIsGapSeverity = Literal["INFO", "MINOR", "BLOCKS_SIMULATION"]


@dataclass(frozen=True)
class AsIsCompletenessGap:
    """Sec 18: a single explicit completeness gap. Never reduced to a boolean."""

    gap_id: str
    domain: AsIsGapDomain
    fact: str
    status: AsIsGapStatus
    severity: AsIsGapSeverity
    reason: str
    object_id: str | None = None
    provenance: AsIsProvenance | None = None


AsIsCompletenessStatus = Literal[
    "STRUCTURALLY_COMPLETE",
    "PARTIALLY_COMPLETE",
    "INSUFFICIENT_FOR_SIMULATION",
]


@dataclass(frozen=True)
class AsIsCompletenessAssessment:
    """Sec 18-19: the explicit completeness assessment (the one new artifact)."""

    overall_status: AsIsCompletenessStatus
    gaps: tuple[AsIsCompletenessGap, ...]

    def gaps_in_domain(self, domain: AsIsGapDomain) -> tuple[AsIsCompletenessGap, ...]:
        return tuple(g for g in self.gaps if g.domain == domain)

    @property
    def blocks_simulation(self) -> bool:
        return any(g.severity == "BLOCKS_SIMULATION" for g in self.gaps)


# ===========================================================================
# NORMALIZED EQUIPMENT (identity + placement kept separate -- Sec 12-13).
# ===========================================================================
AsIsPlacementStatus = Literal["KNOWN", "UNRESOLVED"]


@dataclass(frozen=True)
class AsIsNormalizedEquipment:
    """The normalized equipment record: a real facility instance from the
    catalog authority, plus its placement STATUS. Identity survives even when
    placement is UNRESOLVED; no room is ever fabricated to satisfy the record."""

    equipment_instance_id: str
    equipment_class: AsIsEquipmentClass
    catalog_model_id: str
    facility_instance: FacilityCyclotronInstance | FacilityGeneratorInstance | FacilityScannerInstance
    placement_status: AsIsPlacementStatus
    placed_in_room_id: str | None
    identity_evidence: AsIsFieldEvidence
    placement_evidence: AsIsFieldEvidence


# ===========================================================================
# Sec 20: TOP-LEVEL AS-IS RESULT (frozen). NOT yet the full operational twin.
# ===========================================================================
AsIsSimulationReadiness = Literal[
    "NOT_READY_FOR_SIMULATION",
    "READY_WITH_EXPLICIT_CONTROLLED_ASSUMPTIONS",
    "READY_FOR_ASIS_BASELINE_RECONSTRUCTION",
]


@dataclass(frozen=True)
class ExistingFacilityAsIsTwinResult:
    """Sec 20: the normalized AS-IS engineering read model. This is an
    ENGINEERING twin snapshot -- explicitly NOT an operational twin and NOT a
    LOCKDOWN baseline (see the seam flags below)."""

    project_starting_state: ProjectStartingState
    facility_identity: AsIsFacilityIdentityInput

    # Canonical references (reused, never re-modeled).
    spatial_registry: SpatialObjectRegistry
    normalized_import: NormalizedImportResult
    engineering_objects: tuple[AsIsNormalizedEquipment, ...]

    # Evidence / provenance / calibration summaries (kept distinct -- Sec 15).
    field_evidence: tuple[AsIsFieldEvidence, ...]

    # Completeness / readiness.
    completeness: AsIsCompletenessAssessment
    simulation_readiness_status: AsIsSimulationReadiness

    limitations: tuple[str, ...]

    # ---- Sec 22-25: downstream seams -- exposed but NOT implemented. ----
    operational_state_reconstruction_implemented: bool = False
    lockdown_created: bool = False
    what_if_created: bool = False
    ifc_real_hospital_ingestion_implemented: bool = False
    bentley_itwin_real_hospital_ingestion_implemented: bool = False
    pdf_image_reconstruction_implemented: bool = False
    cad_dwg_dxf_parser_implemented: bool = False
    openusd_real_hospital_ingestion_implemented: bool = False
    synthetic_ifc_proof_exists: bool = True
    bentley_itwin_proof_seam_exists: bool = True

    # ---- Phase 1C additive read-models (all defaulted; Phase 1B callers
    # constructing this result directly keep working unchanged). ----
    facility_hierarchy: "AsIsFacilityHierarchyView | None" = None
    space_classifications: tuple["AsIsSpaceClassificationBinding", ...] = ()
    equipment_bindings: tuple["AsIsEquipmentSpatialBinding", ...] = ()
    connectivity: "AsIsConnectivityView | None" = None
    operational_resource_placeholders: tuple["AsIsOperationalResourcePlaceholder", ...] = ()
    evidence_conflicts: tuple["AsIsEvidenceConflict", ...] = ()
    domain_completeness: tuple["AsIsDomainCompleteness", ...] = ()
    readiness_gates: "AsIsReadinessGates | None" = None

    # ---- Phase 1C out-of-scope disclosure flags (Sec 21-24). ----
    patient_state_ingestion_implemented: bool = False
    appointment_ingestion_implemented: bool = False
    scanner_calendar_ingestion_implemented: bool = False
    staff_roster_ingestion_implemented: bool = False
    production_schedule_ingestion_implemented: bool = False
    live_equipment_state_ingestion_implemented: bool = False
    asis_baseline_simulation_implemented: bool = False
    simulation_run_during_phase_1c: bool = False
    lockdown_authority_duplicated: bool = False
    existing_lockdown_lineage_seam_preserved: bool = True

    @property
    def mrt_infrastructure_count(self) -> int:
        """Sec 14/26: count of MRT infrastructure objects present in the
        canonical registry. A facility supplying no MRT keeps this at 0 -- a
        benchmark MRT network is NEVER inserted."""
        mrt_types = {
            "MRT_TRUNK", "MRT_BRANCH", "MRT_SEGMENT", "MRT_JUNCTION", "MRT_ENDPOINT",
            "MRT_CARRIER", "MRT_CONTAINER", "MRT_VESTIBULE",
        }
        return sum(1 for o in self.spatial_registry.objects.values() if o.object_type in mrt_types)

    @property
    def benchmark_mrt_inserted(self) -> bool:
        """HARD GOVERNOR proof (Sec 14/24/26): the AS-IS path NEVER inserts a
        benchmark MRT network. Always False."""
        return False

    @property
    def mrt_required_for_engineering_model_ready(self) -> bool:
        """Sec 26: MRT is NEVER a prerequisite for the engineering-object model
        to be ready. Always False."""
        return False

    @property
    def facility_cyclotron_count(self) -> int:
        return sum(1 for e in self.engineering_objects if e.equipment_class == "CYCLOTRON")

    @property
    def benchmark_cyclotron_inserted(self) -> bool:
        """HARD GOVERNOR proof (Sec 17/27): the AS-IS path NEVER inserts the
        benchmark cyclotron. Always False -- cyclotrons appear only when
        explicitly supplied in the structured input."""
        return False


# ===========================================================================
# INGESTION FAILURE (only for genuinely invalid required references -- Sec 13).
# Unknown placement / unknown function / missing equipment are NOT failures.
# ===========================================================================
class AsIsIngestionError(ValueError):
    """Raised only when a REQUIRED identity reference is invalid (e.g. an
    equipment placement references a room that does not exist, or an equipment
    record references a catalog model id that does not exist). Never raised for
    merely-incomplete facts."""


# ===========================================================================
# NORMALIZATION (Sec 7 flow):
#   Structured input -> evidence/validation -> canonical spatial + engineering
#   objects + bindings -> normalized read model -> completeness/gap assessment.
# ===========================================================================
def ingest_structured_facility(
    structured_input: AsIsStructuredFacilityInput,
    *,
    project_starting_state: ProjectStartingState = "EXISTING_FACILITY_AS_IS",
) -> ExistingFacilityAsIsTwinResult:
    """Normalize already-structured, project-supplied facility facts into the
    existing canonical authorities and produce an explicit completeness/gap
    assessment. NO parser, NO benchmark fallback, NO simulation, NO LOCKDOWN.

    Raises AsIsIngestionError only for invalid REQUIRED identity references."""

    facility = structured_input.facility
    facility_id = facility.facility_id
    gaps: list[AsIsCompletenessGap] = []
    field_evidence: list[AsIsFieldEvidence] = []
    limitations: list[str] = []
    gap_counter = 0

    def _next_gap_id() -> str:
        nonlocal gap_counter
        gap_counter += 1
        return f"GAP-{gap_counter:03d}"

    # ---- Facility identity ----
    if not facility_id or not facility.facility_name:
        raise AsIsIngestionError("facility_id and facility_name are required")
    field_evidence.append(
        AsIsFieldEvidence(fact="facility_identity", provenance="FACILITY_SUPPLIED", calibration="NOT_APPLICABLE", confidence="high")
    )

    # ---- Spatial hierarchy (reuse canonical builders) ----
    registry = build_facility_hierarchy(facility_id=facility_id)

    known_building_ids: set[str] = set()
    for b in structured_input.buildings:
        add_building(registry, facility_id=facility_id, building_id=b.building_id, transform=b.transform)
        known_building_ids.add(b.building_id)
        field_evidence.append(
            AsIsFieldEvidence(fact=f"building:{b.building_id}", provenance="FACILITY_SUPPLIED", calibration="CALIBRATED", confidence="high")
        )

    known_floor_keys: set[tuple[str, str]] = set()
    for fl in structured_input.floors:
        if fl.building_id not in known_building_ids:
            raise AsIsIngestionError(
                f"floor {fl.floor_id} references unknown building {fl.building_id}"
            )
        add_floor(registry, facility_id=facility_id, building_id=fl.building_id, floor_id=fl.floor_id, transform=fl.transform)
        known_floor_keys.add((fl.building_id, fl.floor_id))
        elevation_prov: AsIsProvenance = "FACILITY_SUPPLIED" if fl.elevation_m is not None else "MISSING"
        if fl.elevation_m is None:
            gaps.append(AsIsCompletenessGap(
                gap_id=_next_gap_id(), domain="GEOMETRY", fact="floor_elevation_m", status="MISSING",
                severity="MINOR", reason="floor elevation not supplied", object_id=fl.floor_id,
                provenance="MISSING",
            ))
        field_evidence.append(
            AsIsFieldEvidence(fact=f"floor:{fl.floor_id}", provenance="FACILITY_SUPPLIED", calibration="CALIBRATED", confidence="high", note=None)
        )

    # ---- Rooms: geometry vs clinical function kept SEPARATE (Sec 8/11) ----
    known_room_ids: set[str] = set()
    space_classifications: list[AsIsSpaceClassificationBinding] = []
    for r in structured_input.rooms:
        if (r.building_id, r.floor_id) not in known_floor_keys:
            raise AsIsIngestionError(
                f"room {r.room_id} references unknown floor {r.building_id}/{r.floor_id}"
            )
        object_type = _ROOM_FUNCTION_TO_OBJECT_TYPE[r.room_function]
        # Geometry calibration reflects whether dimensions were supplied.
        dims_known = all(v is not None for v in (r.length_m, r.width_m, r.height_m))
        add_room(
            registry, facility_id=facility_id, building_id=r.building_id, floor_id=r.floor_id,
            room_id=r.room_id, object_type=object_type, transform=r.transform,
            spatial_status="CALIBRATED" if dims_known else "GEOMETRY_NOT_CALIBRATED",
        )
        # Attach real dimensions where supplied (never fabricated).
        if dims_known:
            from canonical_spatial_authority import EngineeringEnvelope

            registry.objects[r.room_id] = replace(
                registry.objects[r.room_id],
                dimensions=EngineeringEnvelope(length_m=r.length_m, width_m=r.width_m, height_m=r.height_m),
            )
        known_room_ids.add(r.room_id)

        # Field-level evidence: geometry and function are INDEPENDENT axes.
        field_evidence.append(AsIsFieldEvidence(
            fact=f"room_geometry:{r.room_id}", provenance=r.geometry_provenance,
            calibration="CALIBRATED" if dims_known else "NOT_CALIBRATED",
            confidence="high" if dims_known else "low",
        ))
        if r.room_function == "UNKNOWN":
            # Sec 28: geometry stays usable; function stays unknown; NO inference
            # from the room name; a completeness gap is produced.
            gaps.append(AsIsCompletenessGap(
                gap_id=_next_gap_id(), domain="ROOM_FUNCTION", fact="room_function", status="NOT_MODELED",
                severity="MINOR", reason="clinical function not supplied; not inferred from room name",
                object_id=r.room_id, provenance="MISSING",
            ))
            field_evidence.append(AsIsFieldEvidence(
                fact=f"room_function:{r.room_id}", provenance="MISSING", calibration="NOT_APPLICABLE", confidence="unknown",
            ))
        else:
            field_evidence.append(AsIsFieldEvidence(
                fact=f"room_function:{r.room_id}", provenance=r.function_provenance, calibration="NOT_APPLICABLE", confidence="high",
            ))

        # ---- Phase 1C (Sec 6-7): clinical-space classification binding on its
        # OWN axis, distinct from geometry object_type. Explicit input wins;
        # otherwise DERIVE from the (explicit) room_function; a genuinely
        # unknown function stays UNKNOWN and NEVER guesses from the room name.
        if r.clinical_space_classification is not None:
            classification = r.clinical_space_classification
            classification_status: AsIsClassificationStatus = (
                "KNOWN" if classification not in ("UNKNOWN", "NOT_MODELED") else
                ("NOT_MODELED" if classification == "NOT_MODELED" else "UNKNOWN")
            )
            classification_prov = r.classification_provenance
        elif r.room_function != "UNKNOWN":
            classification = _ROOM_FUNCTION_TO_CLASSIFICATION[r.room_function]
            classification_status = "KNOWN"
            classification_prov = r.function_provenance
        else:
            classification = "UNKNOWN"
            classification_status = "UNKNOWN"
            classification_prov = "MISSING"
        space_classifications.append(AsIsSpaceClassificationBinding(
            spatial_object_id=r.room_id, classification=classification, status=classification_status,
            provenance=classification_prov,
        ))
        if classification_status in ("UNKNOWN", "NOT_MODELED") and r.room_function != "UNKNOWN":
            # An explicitly UNKNOWN/NOT_MODELED classification supplied over a
            # known geometry is itself a clinical-classification gap (Sec 6).
            gaps.append(AsIsCompletenessGap(
                gap_id=_next_gap_id(), domain="ROOM_FUNCTION", fact="clinical_space_classification",
                status="NOT_MODELED", severity="MINOR",
                reason="clinical-space classification explicitly unknown/not modeled; not inferred",
                object_id=r.room_id, provenance="MISSING",
            ))

        if not dims_known:
            gaps.append(AsIsCompletenessGap(
                gap_id=_next_gap_id(), domain="GEOMETRY", fact="room_dimensions", status="NOT_CALIBRATED",
                severity="MINOR", reason="room dimensions not fully supplied", object_id=r.room_id,
                provenance="MISSING",
            ))

    # ---- Equipment identity (reuse catalogs) + placement bindings (Sec 12-13) ----
    placement_by_instance: dict[str, AsIsEquipmentPlacementInput] = {}
    for p in structured_input.equipment_placements:
        if p.room_id not in known_room_ids:
            raise AsIsIngestionError(
                f"equipment placement for {p.equipment_instance_id} references unknown room {p.room_id}"
            )
        placement_by_instance[p.equipment_instance_id] = p

    cyclotron_catalog = load_cyclotron_catalog()
    generator_catalog = load_generator_catalog()
    scanner_catalog = load_scanner_catalog()

    normalized_equipment: list[AsIsNormalizedEquipment] = []
    equipment_bindings: list[AsIsEquipmentSpatialBinding] = []
    for e in structured_input.equipment:
        # Validate catalog identity -- an invalid REQUIRED reference is a failure.
        instance: FacilityCyclotronInstance | FacilityGeneratorInstance | FacilityScannerInstance
        try:
            if e.equipment_class == "CYCLOTRON":
                cyclotron_catalog.by_id(e.catalog_model_id)  # KeyError if unknown model id
                instance = FacilityCyclotronInstance(instance_id=e.equipment_instance_id, catalog_model_id=e.catalog_model_id)
            elif e.equipment_class == "GENERATOR":
                generator_catalog.by_id(e.catalog_model_id)
                instance = FacilityGeneratorInstance(instance_id=e.equipment_instance_id, catalog_model_id=e.catalog_model_id)
            elif e.equipment_class in ("PET_SCANNER", "SPECT_SCANNER"):
                scanner_catalog.by_id(e.catalog_model_id)
                modality = e.modality or ("PET" if e.equipment_class == "PET_SCANNER" else "SPECT")
                instance = FacilityScannerInstance(
                    scanner_id=e.equipment_instance_id, catalog_model_id=e.catalog_model_id, modality=modality,
                )
            else:  # pragma: no cover - exhaustive over the Literal
                raise AsIsIngestionError(f"unknown equipment_class: {e.equipment_class}")
        except (KeyError, ValueError) as exc:
            # An invalid REQUIRED identity reference is an ingestion failure
            # (Sec 13) -- surfaced as the single AS-IS failure type. We do NOT
            # fabricate an identity or silently drop the equipment record.
            if isinstance(exc, AsIsIngestionError):
                raise
            raise AsIsIngestionError(
                f"equipment {e.equipment_instance_id} references unknown catalog_model_id {e.catalog_model_id!r}"
            ) from exc

        placement = placement_by_instance.get(e.equipment_instance_id)
        if placement is not None:
            placement_status: AsIsPlacementStatus = "KNOWN"
            placed_room = placement.room_id
            placement_prov = placement.placement_provenance
            # Bind geometry<->engineering via the canonical engineering_object_id
            # bridge on the room object (ID<->ID only; never geometry).
            room_obj = registry.objects[placed_room]
            registry.objects[placed_room] = replace(room_obj, engineering_object_id=e.equipment_instance_id)
            placement_evidence = AsIsFieldEvidence(
                fact=f"equipment_placement:{e.equipment_instance_id}", provenance=placement_prov,
                calibration="NOT_APPLICABLE", confidence="high",
            )
        else:
            # Sec 29: known equipment, unknown location. Identity survives;
            # placement UNRESOLVED; NO fabricated/nearest/benchmark room; NOT a failure.
            placement_status = "UNRESOLVED"
            placed_room = None
            placement_evidence = AsIsFieldEvidence(
                fact=f"equipment_placement:{e.equipment_instance_id}", provenance="MISSING",
                calibration="NOT_APPLICABLE", confidence="unknown",
            )
            gaps.append(AsIsCompletenessGap(
                gap_id=_next_gap_id(), domain="EQUIPMENT_PLACEMENT", fact="placement_room",
                status="UNRESOLVED", severity="MINOR",
                reason="equipment identity known but no room placement supplied; not fabricated",
                object_id=e.equipment_instance_id, provenance="MISSING",
            ))

        identity_evidence = AsIsFieldEvidence(
            fact=f"equipment_identity:{e.equipment_instance_id}", provenance=e.identity_provenance,
            calibration="CALIBRATED", confidence="high",
        )
        field_evidence.append(identity_evidence)
        field_evidence.append(placement_evidence)
        normalized_equipment.append(AsIsNormalizedEquipment(
            equipment_instance_id=e.equipment_instance_id, equipment_class=e.equipment_class,
            catalog_model_id=e.catalog_model_id, facility_instance=instance,
            placement_status=placement_status, placed_in_room_id=placed_room,
            identity_evidence=identity_evidence, placement_evidence=placement_evidence,
        ))
        # ---- Phase 1C (Sec 9-10): queryable equipment<->space binding read-model
        # over the engineering_object_id scalar. Identity is decoupled from
        # placement: a UNRESOLVED binding still carries the full instance id.
        equipment_bindings.append(AsIsEquipmentSpatialBinding(
            equipment_instance_id=e.equipment_instance_id, equipment_class=e.equipment_class,
            spatial_object_id=placed_room,
            binding_status="BOUND" if placement_status == "KNOWN" else "UNRESOLVED",
            source=(placement.placement_provenance if placement is not None else "MISSING"),
            validation_status="VALIDATED" if placement_status == "KNOWN" else "NOT_APPLICABLE",
        ))

    # ---- Connectivity / routes (Sec 14): optional; gap when absent ----
    if not structured_input.routes:
        gaps.append(AsIsCompletenessGap(
            gap_id=_next_gap_id(), domain="CONNECTIVITY", fact="route_topology", status="NOT_MODELED",
            severity="BLOCKS_SIMULATION",
            reason="no explicit connectivity supplied; benchmark route distances NOT substituted",
            provenance="MISSING",
        ))
    else:
        for rt in structured_input.routes:
            if rt.length_m is None:
                gaps.append(AsIsCompletenessGap(
                    gap_id=_next_gap_id(), domain="CONNECTIVITY", fact="route_length_m",
                    status="NOT_CALIBRATED", severity="MINOR",
                    reason="connectivity supplied but distance not calibrated; not substituted",
                    object_id=f"{rt.from_object_id}->{rt.to_object_id}", provenance="MISSING",
                ))

    # ---- Operational resources (Sec 17/22): NEVER benchmark-filled ----
    # Clinical resource counts, patient populations, staffing, production basis
    # are NOT supplied by the structured engineering input. They stay MISSING --
    # explicitly NOT the controlled 6/6/12 / GE-cyclotron / 200-patient benchmark.
    gaps.append(AsIsCompletenessGap(
        gap_id=_next_gap_id(), domain="OPERATIONAL_RESOURCES", fact="clinical_resource_counts",
        status="MISSING", severity="BLOCKS_SIMULATION",
        reason="clinical resource counts not supplied; controlled 6/6/12 benchmark NOT substituted",
        provenance="MISSING",
    ))
    gaps.append(AsIsCompletenessGap(
        gap_id=_next_gap_id(), domain="OPERATIONAL_RESOURCES", fact="patient_population",
        status="MISSING", severity="BLOCKS_SIMULATION",
        reason="patient population not supplied; controlled benchmark population NOT substituted",
        provenance="MISSING",
    ))
    if not any(e.equipment_class == "CYCLOTRON" for e in structured_input.equipment):
        # Sec 27 negative control: no cyclotron supplied stays a legitimate fact.
        gaps.append(AsIsCompletenessGap(
            gap_id=_next_gap_id(), domain="EQUIPMENT_IDENTITY", fact="production_source_cyclotron",
            status="NOT_MODELED", severity="INFO",
            reason="facility supplied no cyclotron; benchmark GE cyclotron NOT inserted",
            provenance="MISSING",
        ))

    # ---- Simulation-readiness is ALWAYS a gap in Phase 1B (Sec 21-22) ----
    gaps.append(AsIsCompletenessGap(
        gap_id=_next_gap_id(), domain="SIMULATION_READINESS", fact="operational_state",
        status="NOT_MODELED", severity="BLOCKS_SIMULATION",
        reason="operational-state reconstruction is out of scope for Phase 1B",
        provenance="MISSING",
    ))

    # ---- Spatial validation issues surfaced as provenance/geometry gaps ----
    for issue in registry_validation_issues(registry):
        gaps.append(AsIsCompletenessGap(
            gap_id=_next_gap_id(), domain="GEOMETRY", fact=issue.issue_type, status="UNRESOLVED",
            severity="MINOR", reason=f"spatial validation: {issue.issue_type}", object_id=issue.object_id,
            provenance=None,
        ))

    # =======================================================================
    # PHASE 1C: build the strengthened read-models (Sec 5-20). All of this is
    # additive; the Phase 1B gaps/evidence/registry above are untouched.
    # =======================================================================

    # ---- Sec 11-12: CONNECTIVITY / TOPOLOGY view (topology-only, no physics) ----
    connectivity_links: list[AsIsConnectivityLink] = []
    for rt in structured_input.routes:
        connectivity_links.append(AsIsConnectivityLink(
            from_object_id=rt.from_object_id, to_object_id=rt.to_object_id,
            length_calibrated=rt.length_m is not None, provenance=rt.provenance,
        ))
    # A space is "connectable" if it participates in at least one supplied link.
    connected_object_ids = {l.from_object_id for l in connectivity_links} | {l.to_object_id for l in connectivity_links}
    connectable_space_count = len(known_room_ids & connected_object_ids)
    # Route readiness: geometry completeness NEVER implies connectivity (Sec 12).
    # Topology is COMPLETE only if EVERY modeled room is connected to something;
    # PARTIAL if some connectivity supplied; NOT_MODELED if none.
    if not connectivity_links:
        route_readiness: AsIsRouteReadiness = "TOPOLOGY_NOT_MODELED"
    elif known_room_ids and connectable_space_count < len(known_room_ids):
        route_readiness = "TOPOLOGY_PARTIAL"
    elif known_room_ids and connectable_space_count == len(known_room_ids):
        route_readiness = "TOPOLOGY_COMPLETE"
    else:
        route_readiness = "TOPOLOGY_PARTIAL"
    connectivity = AsIsConnectivityView(
        links=tuple(connectivity_links), route_readiness=route_readiness,
        supplied_connection_count=len(connectivity_links), connectable_space_count=connectable_space_count,
        route_distance_fabricated=False, transport_time_calculated=False,
    )

    # ---- Sec 16-17: EVIDENCE CONFLICTS (no auto-resolution; reduce readiness) ----
    # A supplied room already asserts a clinical function; an independently
    # sourced conflicting_evidence record about the SAME object/field that
    # disagrees becomes an UNRESOLVED conflict. Both candidates are preserved.
    primary_room_function_value: dict[str, str] = {}
    for r in structured_input.rooms:
        # The primary supplied fact for the room_function/classification field.
        primary_room_function_value[r.room_id] = (
            r.clinical_space_classification if r.clinical_space_classification is not None else r.room_function
        )
    evidence_conflicts: list[AsIsEvidenceConflict] = []
    conflict_counter = 0
    for ce in structured_input.conflicting_evidence:
        primary = primary_room_function_value.get(ce.object_id)
        if primary is None or primary == "UNKNOWN":
            # No competing primary fact -> this is just an additional (single)
            # claim, not a contradiction; still recorded as field evidence.
            field_evidence.append(AsIsFieldEvidence(
                fact=f"{ce.field_name}:{ce.object_id}", provenance=ce.source,
                calibration="NOT_APPLICABLE", confidence="medium",
                note="independently sourced claim; no competing primary fact",
            ))
            continue
        if str(primary) == str(ce.candidate_value):
            # Agreement -- not a conflict.
            continue
        conflict_counter += 1
        evidence_conflicts.append(AsIsEvidenceConflict(
            conflict_id=f"CONF-{conflict_counter:03d}",
            domain="CLINICAL_SPACE_CLASSIFICATION" if ce.field_name in ("room_function", "clinical_space_classification") else "GEOMETRY",
            object_id=ce.object_id, field_name=ce.field_name,
            candidate_values=(str(primary), str(ce.candidate_value)),
            candidate_sources=("PROJECT_SUPPLIED", ce.source),
            resolution_status="UNRESOLVED", selected_value=None, resolution_source=None,
            impact_on_readiness="REDUCES_READINESS",
        ))
        # An UNRESOLVED conflict is an explicit completeness gap (Sec 17).
        gaps.append(AsIsCompletenessGap(
            gap_id=_next_gap_id(), domain="PROVENANCE", fact=f"evidence_conflict:{ce.field_name}",
            status="UNRESOLVED", severity="BLOCKS_SIMULATION",
            reason="two independently sourced facts disagree; not auto-resolved; both preserved",
            object_id=ce.object_id, provenance=None,
        ))
        # A CONFLICTED room function also updates that room's classification
        # binding status to CONFLICTED (both candidates remain visible on the
        # conflict record; the binding is NOT silently overwritten).
        for idx, binding in enumerate(space_classifications):
            if binding.spatial_object_id == ce.object_id and ce.field_name in ("room_function", "clinical_space_classification"):
                space_classifications[idx] = replace(binding, status="CONFLICTED")

    # ---- Sec 13-14: OPERATIONAL RESOURCE PLACEHOLDERS (identity seams only) ----
    scanner_identity_count = sum(1 for e in normalized_equipment if e.equipment_class in ("PET_SCANNER", "SPECT_SCANNER"))
    cyclotron_identity_count = sum(1 for e in normalized_equipment if e.equipment_class == "CYCLOTRON")
    generator_identity_count = sum(1 for e in normalized_equipment if e.equipment_class == "GENERATOR")
    mrt_identity_count = sum(
        1 for o in registry.objects.values()
        if o.object_type in {"MRT_TRUNK", "MRT_BRANCH", "MRT_SEGMENT", "MRT_JUNCTION", "MRT_ENDPOINT", "MRT_CARRIER", "MRT_CONTAINER", "MRT_VESTIBULE"}
    )
    operational_resource_placeholders: tuple[AsIsOperationalResourcePlaceholder, ...] = (
        AsIsOperationalResourcePlaceholder(
            resource_category="SCANNER",
            identity_status="IDENTITY_PRESENT" if scanner_identity_count else "IDENTITY_ABSENT",
            identity_count=scanner_identity_count,
        ),
        AsIsOperationalResourcePlaceholder(
            resource_category="PRODUCTION_CYCLOTRON",
            identity_status="IDENTITY_PRESENT" if cyclotron_identity_count else "IDENTITY_ABSENT",
            identity_count=cyclotron_identity_count,
        ),
        AsIsOperationalResourcePlaceholder(
            resource_category="GENERATOR",
            identity_status="IDENTITY_PRESENT" if generator_identity_count else "IDENTITY_ABSENT",
            identity_count=generator_identity_count,
        ),
        # Staffing / transport / MRT-carrier operational identities are NOT
        # supplied by the structured engineering input -> identity absent, state
        # never reconstructed. A benchmark roster/fleet is NEVER substituted.
        AsIsOperationalResourcePlaceholder(resource_category="STAFFING", identity_status="IDENTITY_ABSENT", identity_count=0),
        AsIsOperationalResourcePlaceholder(resource_category="TRANSPORT", identity_status="IDENTITY_ABSENT", identity_count=0),
        AsIsOperationalResourcePlaceholder(
            resource_category="MRT_CARRIER_ENDPOINT",
            identity_status="IDENTITY_PRESENT" if mrt_identity_count else "IDENTITY_ABSENT",
            identity_count=mrt_identity_count,
        ),
    )

    # ---- Sec 5: FACILITY HIERARCHY VIEW (over the canonical registry) ----
    facility_hierarchy = _build_hierarchy_view(registry, facility)

    # ---- Finalize through the canonical manual/structured normalize path ----
    normalized_import = normalize_blank_manual_import(registry)

    # ---- Deterministic overall completeness status (Sec 19) ----
    overall_status = _derive_completeness_status(gaps)

    # ---- Sec 18-19: per-domain completeness (never one collapsed count) ----
    domain_completeness = _build_domain_completeness(
        gaps=gaps, rooms=structured_input.rooms, space_classifications=space_classifications,
        equipment_bindings=equipment_bindings, normalized_equipment=normalized_equipment,
        connectivity=connectivity, evidence_conflicts=evidence_conflicts,
        operational_resource_placeholders=operational_resource_placeholders,
    )

    # ---- Sec 20: distinct, monotonic readiness gates (pre-simulation) ----
    readiness_gates = _derive_readiness_gates(
        gaps=gaps, domain_completeness=domain_completeness, evidence_conflicts=evidence_conflicts,
    )

    # ---- Conservative simulation readiness (Sec 21) ----
    simulation_readiness = "NOT_READY_FOR_SIMULATION"

    limitations.extend([
        "Phase 1B: MANUAL/PROJECT-SUPPLIED STRUCTURED INGESTION only (no BIM/IFC/CAD/PDF/OCR).",
        "No operational-state reconstruction, no baseline simulation, no LOCKDOWN, no What-If.",
        "Missing operational facts are reported as gaps; controlled benchmark facts are never substituted.",
        "This is an ENGINEERING twin snapshot, not an operational digital twin.",
        "Phase 1C: strengthens the canonical AS-IS model (hierarchy, clinical-space "
        "classification, equipment bindings, connectivity/topology, evidence conflicts, "
        "domain completeness, readiness gates) -- still PRE-SIMULATION; no routing physics, "
        "no operational-state reconstruction, no LOCKDOWN/What-If lineage created.",
    ])

    return ExistingFacilityAsIsTwinResult(
        project_starting_state=project_starting_state,
        facility_identity=facility,
        spatial_registry=registry,
        normalized_import=normalized_import,
        engineering_objects=tuple(normalized_equipment),
        field_evidence=tuple(field_evidence),
        completeness=AsIsCompletenessAssessment(overall_status=overall_status, gaps=tuple(gaps)),
        simulation_readiness_status=simulation_readiness,
        limitations=tuple(limitations),
        # Phase 1C read-models.
        facility_hierarchy=facility_hierarchy,
        space_classifications=tuple(space_classifications),
        equipment_bindings=tuple(equipment_bindings),
        connectivity=connectivity,
        operational_resource_placeholders=operational_resource_placeholders,
        evidence_conflicts=tuple(evidence_conflicts),
        domain_completeness=domain_completeness,
        readiness_gates=readiness_gates,
    )


def registry_validation_issues(registry: SpatialObjectRegistry):
    """Thin wrapper over the canonical validator (kept local so callers/tests do
    not import canonical internals directly)."""
    from canonical_spatial_authority import validate_spatial_registry

    return validate_spatial_registry(registry)


def _derive_completeness_status(gaps: Sequence[AsIsCompletenessGap]) -> AsIsCompletenessStatus:
    """Sec 19: deterministic. Ingestion succeeding != simulation ready. Any
    BLOCKS_SIMULATION gap => INSUFFICIENT_FOR_SIMULATION; any other gap =>
    PARTIALLY_COMPLETE; otherwise STRUCTURALLY_COMPLETE."""
    if any(g.severity == "BLOCKS_SIMULATION" for g in gaps):
        return "INSUFFICIENT_FOR_SIMULATION"
    if gaps:
        return "PARTIALLY_COMPLETE"
    return "STRUCTURALLY_COMPLETE"


# ===========================================================================
# PHASE 1C HELPERS (Sec 5, 18-20). All read-only derivations -- no engine.
# ===========================================================================
_OBJECT_TYPE_TO_HIERARCHY_LEVEL: Mapping[str, AsIsFacilityLevel] = {
    "FACILITY": "FACILITY",
    "BUILDING": "BUILDING",
    "FLOOR": "FLOOR",
}


def _build_hierarchy_view(
    registry: SpatialObjectRegistry, facility: AsIsFacilityIdentityInput
) -> AsIsFacilityHierarchyView:
    """Sec 5: an explicit, queryable hierarchy VIEW over the canonical registry.
    FACILITY/BUILDING/FLOOR map to canonical object_types; everything below a
    FLOOR is treated as a ROOM-level node (its clinical function lives on the
    separate classification axis, never here). SITE/CAMPUS remain identity-only
    metadata (Sec 5: no campus layer is required where none exists)."""
    nodes: list[AsIsHierarchyNode] = []
    for obj in registry.objects.values():
        level = _OBJECT_TYPE_TO_HIERARCHY_LEVEL.get(obj.object_type, "ROOM")
        child_ids = tuple(sorted(c.mrtway_object_id for c in registry.children_of(obj.mrtway_object_id)))
        nodes.append(AsIsHierarchyNode(
            object_id=obj.mrtway_object_id, level=level,
            parent_object_id=obj.parent_object_id, child_object_ids=child_ids,
        ))
    return AsIsFacilityHierarchyView(
        facility_id=facility.facility_id, site_id=facility.site_id, campus_id=facility.campus_id,
        nodes=tuple(sorted(nodes, key=lambda n: n.object_id)),
    )


def _domain_from_gap(gap: AsIsCompletenessGap) -> AsIsTwinDomain:
    """Maps a Phase 1B gap domain onto the richer Phase 1C twin-domain vocab."""
    mapping: Mapping[AsIsGapDomain, AsIsTwinDomain] = {
        "FACILITY_IDENTITY": "FACILITY_IDENTITY",
        "GEOMETRY": "GEOMETRY",
        "ROOM_FUNCTION": "CLINICAL_SPACE_CLASSIFICATION",
        "EQUIPMENT_IDENTITY": "ENGINEERING_OBJECT_IDENTITY",
        "EQUIPMENT_PLACEMENT": "EQUIPMENT_PLACEMENT",
        "CONNECTIVITY": "CONNECTIVITY_TOPOLOGY",
        "OPERATIONAL_RESOURCES": "OPERATIONAL_RESOURCE_IDENTITY",
        "PROVENANCE": "EVIDENCE_CONFLICTS",
        "CALIBRATION": "CALIBRATION",
        "SIMULATION_READINESS": "OPERATIONAL_STATE",
    }
    return mapping[gap.domain]


def _build_domain_completeness(
    *,
    gaps: Sequence[AsIsCompletenessGap],
    rooms: Sequence[AsIsRoomInput],
    space_classifications: Sequence[AsIsSpaceClassificationBinding],
    equipment_bindings: Sequence[AsIsEquipmentSpatialBinding],
    normalized_equipment: Sequence[AsIsNormalizedEquipment],
    connectivity: AsIsConnectivityView,
    evidence_conflicts: Sequence[AsIsEvidenceConflict],
    operational_resource_placeholders: Sequence[AsIsOperationalResourcePlaceholder],
) -> tuple[AsIsDomainCompleteness, ...]:
    """Sec 18-19: an explicit per-domain assessment. Domains are independent --
    e.g. GEOMETRY may be COMPLETE while CLINICAL_SPACE_CLASSIFICATION is PARTIAL,
    and CONNECTIVITY_TOPOLOGY may be PARTIAL while GEOMETRY is COMPLETE."""
    # Bucket gaps by twin domain.
    by_domain: dict[AsIsTwinDomain, list[AsIsCompletenessGap]] = {}
    for g in gaps:
        by_domain.setdefault(_domain_from_gap(g), []).append(g)

    def _counts(domain: AsIsTwinDomain) -> tuple[int, int, int]:
        ds = by_domain.get(domain, [])
        blocking = sum(1 for g in ds if g.severity == "BLOCKS_SIMULATION")
        nonblocking = len(ds) - blocking
        return len(ds), blocking, nonblocking

    def _impact(blocking: int, nonblocking: int) -> Literal["NONE", "NONBLOCKING", "BLOCKING"]:
        if blocking:
            return "BLOCKING"
        if nonblocking:
            return "NONBLOCKING"
        return "NONE"

    results: list[AsIsDomainCompleteness] = []

    # FACILITY_IDENTITY -- always supplied (required to normalize at all).
    _, b, nb = _counts("FACILITY_IDENTITY")
    results.append(AsIsDomainCompleteness(
        domain="FACILITY_IDENTITY", status="COMPLETE" if not (b or nb) else "PARTIAL",
        known_count=1, blocking_gap_count=b, nonblocking_gap_count=nb, readiness_impact=_impact(b, nb),
    ))

    # SPATIAL_HIERARCHY -- structurally present once rooms/floors exist.
    _, b, nb = _counts("SPATIAL_HIERARCHY")
    results.append(AsIsDomainCompleteness(
        domain="SPATIAL_HIERARCHY", status="COMPLETE" if rooms else "PARTIAL",
        known_count=len(rooms), blocking_gap_count=b, nonblocking_gap_count=nb, readiness_impact=_impact(b, nb),
    ))

    # GEOMETRY -- driven by room dimensions gaps.
    _, b, nb = _counts("GEOMETRY")
    geometry_known = sum(1 for r in rooms if all(v is not None for v in (r.length_m, r.width_m, r.height_m)))
    geometry_unknown = len(rooms) - geometry_known
    results.append(AsIsDomainCompleteness(
        domain="GEOMETRY",
        status="COMPLETE" if (rooms and geometry_unknown == 0) else ("PARTIAL" if rooms else "NOT_MODELED"),
        known_count=geometry_known, unknown_count=geometry_unknown,
        blocking_gap_count=b, nonblocking_gap_count=nb, readiness_impact=_impact(b, nb),
    ))

    # CLINICAL_SPACE_CLASSIFICATION -- independent of geometry (Sec 7/27).
    _, b, nb = _counts("CLINICAL_SPACE_CLASSIFICATION")
    cls_known = sum(1 for c in space_classifications if c.status == "KNOWN")
    cls_unknown = sum(1 for c in space_classifications if c.status in ("UNKNOWN", "NOT_MODELED"))
    cls_conflicted = sum(1 for c in space_classifications if c.status == "CONFLICTED")
    if not space_classifications:
        cls_status: AsIsDomainStatus = "NOT_MODELED"
    elif cls_conflicted:
        cls_status = "CONFLICTED"
    elif cls_unknown == 0:
        cls_status = "COMPLETE"
    else:
        cls_status = "PARTIAL"
    results.append(AsIsDomainCompleteness(
        domain="CLINICAL_SPACE_CLASSIFICATION", status=cls_status,
        known_count=cls_known, unknown_count=cls_unknown, conflict_count=cls_conflicted,
        blocking_gap_count=b, nonblocking_gap_count=nb, readiness_impact=_impact(b, nb),
    ))

    # ENGINEERING_OBJECT_IDENTITY -- equipment instances.
    _, b, nb = _counts("ENGINEERING_OBJECT_IDENTITY")
    results.append(AsIsDomainCompleteness(
        domain="ENGINEERING_OBJECT_IDENTITY",
        status="COMPLETE" if normalized_equipment else "NOT_MODELED",
        known_count=len(normalized_equipment), blocking_gap_count=b, nonblocking_gap_count=nb,
        readiness_impact=_impact(b, nb),
    ))

    # EQUIPMENT_PLACEMENT -- independent of identity (Sec 9/28).
    _, b, nb = _counts("EQUIPMENT_PLACEMENT")
    placed = sum(1 for e in equipment_bindings if e.binding_status == "BOUND")
    unplaced = sum(1 for e in equipment_bindings if e.binding_status == "UNRESOLVED")
    if not equipment_bindings:
        place_status: AsIsDomainStatus = "NOT_APPLICABLE"
    elif unplaced == 0:
        place_status = "COMPLETE"
    else:
        place_status = "PARTIAL"
    results.append(AsIsDomainCompleteness(
        domain="EQUIPMENT_PLACEMENT", status=place_status, known_count=placed, unknown_count=unplaced,
        blocking_gap_count=b, nonblocking_gap_count=nb, readiness_impact=_impact(b, nb),
    ))

    # CONNECTIVITY_TOPOLOGY -- from the connectivity view (Sec 12/29).
    _, b, nb = _counts("CONNECTIVITY_TOPOLOGY")
    conn_status: AsIsDomainStatus = {
        "TOPOLOGY_COMPLETE": "COMPLETE", "TOPOLOGY_PARTIAL": "PARTIAL", "TOPOLOGY_NOT_MODELED": "NOT_MODELED",
    }[connectivity.route_readiness]
    results.append(AsIsDomainCompleteness(
        domain="CONNECTIVITY_TOPOLOGY", status=conn_status,
        known_count=connectivity.supplied_connection_count, blocking_gap_count=b, nonblocking_gap_count=nb,
        readiness_impact=_impact(b, nb),
    ))

    # OPERATIONAL_RESOURCE_IDENTITY.
    _, b, nb = _counts("OPERATIONAL_RESOURCE_IDENTITY")
    res_present = sum(1 for p in operational_resource_placeholders if p.identity_status == "IDENTITY_PRESENT")
    res_absent = sum(1 for p in operational_resource_placeholders if p.identity_status == "IDENTITY_ABSENT")
    results.append(AsIsDomainCompleteness(
        domain="OPERATIONAL_RESOURCE_IDENTITY",
        status="PARTIAL" if res_present else "NOT_MODELED",
        known_count=res_present, unknown_count=res_absent,
        blocking_gap_count=b, nonblocking_gap_count=nb, readiness_impact=_impact(b, nb),
    ))

    # PROVENANCE -- always present (every fact carries provenance).
    results.append(AsIsDomainCompleteness(domain="PROVENANCE", status="COMPLETE", known_count=1))

    # CALIBRATION.
    _, b, nb = _counts("CALIBRATION")
    results.append(AsIsDomainCompleteness(
        domain="CALIBRATION", status="PARTIAL", blocking_gap_count=b, nonblocking_gap_count=nb,
        readiness_impact=_impact(b, nb),
    ))

    # EVIDENCE_CONFLICTS.
    unresolved = sum(1 for c in evidence_conflicts if c.resolution_status == "UNRESOLVED")
    results.append(AsIsDomainCompleteness(
        domain="EVIDENCE_CONFLICTS",
        status="CONFLICTED" if unresolved else ("COMPLETE" if not evidence_conflicts else "PARTIAL"),
        conflict_count=len(evidence_conflicts),
        blocking_gap_count=unresolved, readiness_impact="BLOCKING" if unresolved else "NONE",
    ))

    # OPERATIONAL_STATE -- out of scope in Phase 1C.
    results.append(AsIsDomainCompleteness(
        domain="OPERATIONAL_STATE", status="NOT_MODELED", blocking_gap_count=1, readiness_impact="BLOCKING",
        evidence_summary="operational-state reconstruction is out of scope for Phase 1C",
    ))

    # SIMULATION_READINESS -- derived summary domain.
    results.append(AsIsDomainCompleteness(
        domain="SIMULATION_READINESS", status="NOT_MODELED", blocking_gap_count=1, readiness_impact="BLOCKING",
        evidence_summary="baseline simulation is out of scope for Phase 1C",
    ))

    return tuple(results)


def _derive_readiness_gates(
    *,
    gaps: Sequence[AsIsCompletenessGap],
    domain_completeness: Sequence[AsIsDomainCompleteness],
    evidence_conflicts: Sequence[AsIsEvidenceConflict],
) -> AsIsReadinessGates:
    """Sec 20: FIVE distinct, MONOTONIC gates. Reaching normalization does NOT
    imply structural reconstruction; a complete engineering object model does
    NOT imply operational-state readiness; and neither implies baseline
    simulation. A later gate is never True unless every earlier one is."""
    by_domain = {d.domain: d for d in domain_completeness}

    # (1) Normalization always succeeds if we reached here (no exception raised).
    normalization_succeeded = True

    # (2) Structurally reconstructable: facility identity + a spatial hierarchy
    # (buildings/floors/rooms) exist and geometry is at least partially present.
    hierarchy = by_domain.get("SPATIAL_HIERARCHY")
    geometry = by_domain.get("GEOMETRY")
    structural_reconstruction_ready = bool(
        normalization_succeeded
        and hierarchy is not None and hierarchy.status in ("COMPLETE", "PARTIAL")
        and geometry is not None and geometry.status in ("COMPLETE", "PARTIAL")
    )

    # (3) Engineering-object model ready: structural readiness PLUS no UNRESOLVED
    # evidence conflict (a contradiction blocks a trustworthy object model). MRT
    # is NEVER required here (Sec 26). Engineering-object identity being
    # NOT_MODELED is acceptable-partial (a facility may have no equipment yet),
    # so this gate does not require equipment, only the absence of contradiction.
    unresolved_conflicts = any(c.resolution_status == "UNRESOLVED" for c in evidence_conflicts)
    engineering_object_model_ready = bool(structural_reconstruction_ready and not unresolved_conflicts)

    # (4-5) Operational-state reconstruction and baseline simulation are OUT OF
    # SCOPE for Phase 1C -- always False (Sec 21-22), never claimed early.
    operational_state_reconstruction_ready = False
    baseline_simulation_ready = False

    # Overall level: the highest gate reached in the monotonic progression.
    if baseline_simulation_ready:
        level: AsIsReadinessLevel = "READY_FOR_BASELINE_SIMULATION"
    elif operational_state_reconstruction_ready:
        level = "READY_FOR_OPERATIONAL_STATE_RECONSTRUCTION"
    elif engineering_object_model_ready:
        level = "ENGINEERING_MODEL_PARTIAL"
    elif structural_reconstruction_ready:
        level = "STRUCTURALLY_RECONSTRUCTABLE"
    else:
        level = "NORMALIZED"

    return AsIsReadinessGates(
        normalization_succeeded=normalization_succeeded,
        structural_reconstruction_ready=structural_reconstruction_ready,
        engineering_object_model_ready=engineering_object_model_ready,
        operational_state_reconstruction_ready=operational_state_reconstruction_ready,
        baseline_simulation_ready=baseline_simulation_ready,
        overall_readiness_level=level,
    )

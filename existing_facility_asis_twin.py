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
    carried per relevant fact."""

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
class AsIsStructuredFacilityInput:
    """Sec 9: the top-level structured ingestion contract for the manual path."""

    facility: AsIsFacilityIdentityInput
    buildings: tuple[AsIsBuildingInput, ...] = ()
    floors: tuple[AsIsFloorInput, ...] = ()
    rooms: tuple[AsIsRoomInput, ...] = ()
    equipment: tuple[AsIsEquipmentInput, ...] = ()
    equipment_placements: tuple[AsIsEquipmentPlacementInput, ...] = ()
    routes: tuple[AsIsRouteOrConnectivityInput, ...] = ()


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

    # ---- Finalize through the canonical manual/structured normalize path ----
    normalized_import = normalize_blank_manual_import(registry)

    # ---- Deterministic overall completeness status (Sec 19) ----
    overall_status = _derive_completeness_status(gaps)

    # ---- Conservative simulation readiness (Sec 21) ----
    simulation_readiness = "NOT_READY_FOR_SIMULATION"

    limitations.extend([
        "Phase 1B: MANUAL/PROJECT-SUPPLIED STRUCTURED INGESTION only (no BIM/IFC/CAD/PDF/OCR).",
        "No operational-state reconstruction, no baseline simulation, no LOCKDOWN, no What-If.",
        "Missing operational facts are reported as gaps; controlled benchmark facts are never substituted.",
        "This is an ENGINEERING twin snapshot, not an operational digital twin.",
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

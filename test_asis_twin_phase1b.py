"""EXISTING FACILITY / AS-IS DIGITAL TWIN -- PHASE 1B controls & invariants.

Deterministic controls for the manual/structured AS-IS ingestion authority
(`existing_facility_asis_twin.ingest_structured_facility`) plus the orthogonal
`ProjectStartingState` starting-state axis. No simulation, no LOCKDOWN, no
benchmark substitution -- these tests assert those governors hold.

Real catalog identities used (never fabricated):
  PET scanner   = GE_DISCOVERY_MI
  SPECT scanner = SIEMENS_SYMBIA_PRO_SPECTA
  cyclotron     = GE_PETTRACE_890
  generator     = CURIUM_TECHNELITE
"""

from __future__ import annotations

import pytest

from existing_facility_asis_twin import (
    AsIsBuildingInput,
    AsIsEquipmentInput,
    AsIsEquipmentPlacementInput,
    AsIsFacilityIdentityInput,
    AsIsFieldEvidence,
    AsIsFloorInput,
    AsIsIngestionError,
    AsIsRoomInput,
    AsIsRouteOrConnectivityInput,
    AsIsStructuredFacilityInput,
    ExistingFacilityAsIsTwinResult,
    ingest_structured_facility,
)
from whole_oncology_four_architecture_optimization import (
    ProjectStartingState,
    StudyConfiguration,
    clone_study_configuration,
)

PET_MODEL = "GE_DISCOVERY_MI"
SPECT_MODEL = "SIEMENS_SYMBIA_PRO_SPECTA"
CYCLOTRON_MODEL = "GE_PETTRACE_890"
GENERATOR_MODEL = "CURIUM_TECHNELITE"


# ===========================================================================
# Sec 3-4: ProjectStartingState orthogonality + backward compatibility.
# ===========================================================================
def test_project_starting_state_values():
    assert set(ProjectStartingState.__args__) == {"GREENFIELD", "RETROFIT", "EXISTING_FACILITY_AS_IS"}


def test_study_configuration_default_is_backward_compatible():
    # Existing callers never pass project_starting_state -> default preserves them.
    cfg = StudyConfiguration(
        study_id="S1", development_context="RETROFIT", architecture="MANUAL_CONVENTIONAL",
        study_scope="CAPITAL_PLANNING", economic_mode="COST_ONLY",
    )
    assert cfg.project_starting_state == "RETROFIT"


def test_starting_state_is_orthogonal_to_context_and_scope():
    cfg = StudyConfiguration(
        study_id="S1", development_context="GREENFIELD", architecture="MRT_DOMINANT",
        study_scope="OPERATIONAL_ONLY", economic_mode="COST_ONLY",
    )
    asis = clone_study_configuration(cfg, project_starting_state="EXISTING_FACILITY_AS_IS")
    # Selecting AS-IS does NOT reinterpret the CapEx-attribution or study-objective axes.
    assert asis.project_starting_state == "EXISTING_FACILITY_AS_IS"
    assert asis.development_context == "GREENFIELD"
    assert asis.study_scope == "OPERATIONAL_ONLY"
    # And the original config is untouched (frozen / clone semantics).
    assert cfg.project_starting_state == "RETROFIT"


def test_as_is_does_not_imply_capex_or_intervention():
    # AS-IS composes with ANY development_context; it carries no CapEx meaning.
    for dc in ("RETROFIT", "GREENFIELD"):
        cfg = StudyConfiguration(
            study_id="S", development_context=dc, architecture="MANUAL_CONVENTIONAL",
            study_scope="OPERATIONAL_ONLY", economic_mode="COST_ONLY",
            project_starting_state="EXISTING_FACILITY_AS_IS",
        )
        assert cfg.development_context == dc  # unchanged by AS-IS


# ===========================================================================
# Sec 26: FIRST executable structured control.
# ===========================================================================
def _first_control_input() -> AsIsStructuredFacilityInput:
    return AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="FAC-MERCY", facility_name="Mercy Nuclear Medicine"),
        buildings=(AsIsBuildingInput(building_id="B1", building_name="Main"),),
        floors=(
            AsIsFloorInput(building_id="B1", floor_id="F1", elevation_m=0.0),
            AsIsFloorInput(building_id="B1", floor_id="F2", elevation_m=4.0),
        ),
        rooms=(
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R-PET", room_function="PET_SCANNER", length_m=6.0, width_m=5.0, height_m=3.0),
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R-SPECT", room_function="SPECT_SCANNER", length_m=6.0, width_m=5.0, height_m=3.0),
            AsIsRoomInput(building_id="B1", floor_id="F2", room_id="R-RPH", room_function="RADIOPHARMACY", length_m=4.0, width_m=4.0, height_m=3.0),
            AsIsRoomInput(building_id="B1", floor_id="F2", room_id="R-XYZ"),  # intentionally missing function + dims
        ),
        equipment=(
            AsIsEquipmentInput(equipment_instance_id="SCN-PET-1", equipment_class="PET_SCANNER", catalog_model_id=PET_MODEL),
            AsIsEquipmentInput(equipment_instance_id="SCN-SPECT-1", equipment_class="SPECT_SCANNER", catalog_model_id=SPECT_MODEL),
        ),
        equipment_placements=(
            AsIsEquipmentPlacementInput(equipment_instance_id="SCN-PET-1", room_id="R-PET"),
            AsIsEquipmentPlacementInput(equipment_instance_id="SCN-SPECT-1", room_id="R-SPECT"),
        ),
    )


def test_first_control_normalizes_successfully():
    r = ingest_structured_facility(_first_control_input())
    assert isinstance(r, ExistingFacilityAsIsTwinResult)
    assert r.project_starting_state == "EXISTING_FACILITY_AS_IS"
    assert r.facility_identity.facility_id == "FAC-MERCY"
    # facility + building + 2 floors + 4 rooms = 8 canonical objects
    assert len(r.spatial_registry.objects) == 8


def test_first_control_geometry_and_engineering_objects_separate():
    r = ingest_structured_facility(_first_control_input())
    # Room object is geometry; equipment identity is a separate catalog instance.
    pet_room = r.spatial_registry.objects["R-PET"]
    assert pet_room.object_type == "PET_SCANNER"
    pet_eq = next(e for e in r.engineering_objects if e.equipment_instance_id == "SCN-PET-1")
    assert pet_eq.facility_instance.catalog_model_id == PET_MODEL
    # The geometry<->equipment link is an ID reference, not merged geometry.
    assert pet_room.engineering_object_id == "SCN-PET-1"


def test_first_control_equipment_placement_is_a_binding():
    r = ingest_structured_facility(_first_control_input())
    for e in r.engineering_objects:
        assert e.placement_status == "KNOWN"
        assert e.placed_in_room_id in {"R-PET", "R-SPECT"}


def test_first_control_provenance_survives_normalization():
    r = ingest_structured_facility(_first_control_input())
    # Field-level evidence records exist for identity/geometry/function.
    facts = {ev.fact for ev in r.field_evidence}
    assert "facility_identity" in facts
    assert "room_geometry:R-PET" in facts
    assert any(ev.fact == "equipment_identity:SCN-PET-1" and ev.provenance == "PROJECT_SUPPLIED" for ev in r.field_evidence)


def test_first_control_missing_information_stays_gaps():
    r = ingest_structured_facility(_first_control_input())
    # R-XYZ: unknown function + no dims produce gaps; nothing is fabricated.
    fn_gaps = r.completeness.gaps_in_domain("ROOM_FUNCTION")
    assert [g.object_id for g in fn_gaps] == ["R-XYZ"]
    assert r.completeness.overall_status == "INSUFFICIENT_FOR_SIMULATION"


def test_first_control_no_simulation_no_lockdown():
    r = ingest_structured_facility(_first_control_input())
    assert r.simulation_readiness_status == "NOT_READY_FOR_SIMULATION"
    assert r.operational_state_reconstruction_implemented is False
    assert r.lockdown_created is False
    assert r.what_if_created is False


# ===========================================================================
# Sec 17/27: NEGATIVE CONTROL -- NO CYCLOTRON.
# ===========================================================================
def test_negative_control_no_cyclotron_not_inserted():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="F", facility_name="F"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R1", room_function="PET_SCANNER"),),
    )
    r = ingest_structured_facility(si)
    assert r.facility_cyclotron_count == 0
    assert r.benchmark_cyclotron_inserted is False
    # No canonical CYCLOTRON object was silently created.
    assert not any(o.object_type == "CYCLOTRON" for o in r.spatial_registry.objects.values())


# ===========================================================================
# Sec 28: NEGATIVE CONTROL -- UNKNOWN ROOM FUNCTION (no name inference).
# ===========================================================================
def test_negative_control_unknown_room_function():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="F", facility_name="F"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        # Name LOOKS like a PET room but function is not supplied.
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F1", room_id="PET Suite", length_m=6.0, width_m=5.0, height_m=3.0),),
    )
    r = ingest_structured_facility(si)
    obj = r.spatial_registry.objects["PET Suite"]
    # Geometry remains usable ...
    assert obj.dimensions.is_fully_known()
    # ... but function is NOT inferred from the name (stays generic ROOM) ...
    assert obj.object_type == "ROOM"
    # ... and a completeness gap is produced.
    assert len(r.completeness.gaps_in_domain("ROOM_FUNCTION")) == 1


# ===========================================================================
# Sec 29: NEGATIVE CONTROL -- EQUIPMENT LOCATION UNKNOWN.
# ===========================================================================
def test_negative_control_equipment_location_unknown():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="F", facility_name="F"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R1", room_function="PET_SCANNER"),),
        equipment=(AsIsEquipmentInput(equipment_instance_id="SCN-1", equipment_class="PET_SCANNER", catalog_model_id=PET_MODEL),),
        # NO placement supplied.
    )
    r = ingest_structured_facility(si)
    eq = next(e for e in r.engineering_objects if e.equipment_instance_id == "SCN-1")

    # EQUIPMENT_IDENTITY_PRESERVED = YES
    assert eq.equipment_instance_id == "SCN-1"
    # EQUIPMENT_MODEL_IDENTITY_PRESERVED = YES
    assert eq.catalog_model_id == PET_MODEL
    assert eq.facility_instance.catalog_model_id == PET_MODEL
    # equipment class survives
    assert eq.equipment_class == "PET_SCANNER"
    # EQUIPMENT_PLACEMENT_STATUS = UNRESOLVED
    assert eq.placement_status == "UNRESOLVED"
    # FABRICATED_ROOM_ASSIGNMENT = NO / no benchmark / no nearest-room / no geometry invented
    assert eq.placed_in_room_id is None
    assert all(o.engineering_object_id != "SCN-1" for o in r.spatial_registry.objects.values())
    # EQUIPMENT_PLACEMENT_GAP_CREATED = YES
    placement_gaps = r.completeness.gaps_in_domain("EQUIPMENT_PLACEMENT")
    assert len(placement_gaps) == 1
    assert placement_gaps[0].status == "UNRESOLVED"
    # INGESTION_SUCCEEDED_WITH_UNRESOLVED_PLACEMENT = YES (a valid result object)
    assert isinstance(r, ExistingFacilityAsIsTwinResult)


def test_unknown_placement_is_not_unknown_identity():
    # These are separate facts with separate completeness consequences.
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="F", facility_name="F"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        equipment=(AsIsEquipmentInput(equipment_instance_id="GEN-1", equipment_class="GENERATOR", catalog_model_id=GENERATOR_MODEL),),
    )
    r = ingest_structured_facility(si)
    eq = r.engineering_objects[0]
    assert eq.identity_evidence.calibration == "CALIBRATED"      # identity known
    assert eq.placement_evidence.provenance == "MISSING"          # placement unknown
    assert eq.placement_status == "UNRESOLVED"


# ===========================================================================
# Sec 13: INVALID REQUIRED REFERENCES are ingestion failures (single type).
# ===========================================================================
def test_invalid_catalog_model_id_is_ingestion_failure():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="F", facility_name="F"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        equipment=(AsIsEquipmentInput(equipment_instance_id="X", equipment_class="CYCLOTRON", catalog_model_id="NOT_A_REAL_MODEL"),),
    )
    with pytest.raises(AsIsIngestionError):
        ingest_structured_facility(si)


def test_placement_to_unknown_room_is_ingestion_failure():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="F", facility_name="F"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R1"),),
        equipment=(AsIsEquipmentInput(equipment_instance_id="SCN-1", equipment_class="PET_SCANNER", catalog_model_id=PET_MODEL),),
        equipment_placements=(AsIsEquipmentPlacementInput(equipment_instance_id="SCN-1", room_id="GHOST"),),
    )
    with pytest.raises(AsIsIngestionError):
        ingest_structured_facility(si)


def test_room_referencing_unknown_floor_is_ingestion_failure():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="F", facility_name="F"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F9", room_id="R1"),),
    )
    with pytest.raises(AsIsIngestionError):
        ingest_structured_facility(si)


# ===========================================================================
# Sec 17: NO SILENT BENCHMARK FALLBACK (operational facts stay MISSING).
# ===========================================================================
def test_no_silent_benchmark_operational_resources():
    r = ingest_structured_facility(_first_control_input())
    op_gaps = r.completeness.gaps_in_domain("OPERATIONAL_RESOURCES")
    facts = {g.fact for g in op_gaps}
    # Clinical counts + patient population are reported MISSING, never 6/6/12 / benchmark pop.
    assert "clinical_resource_counts" in facts
    assert "patient_population" in facts
    for g in op_gaps:
        assert g.status == "MISSING"
        assert g.provenance == "MISSING"


def test_absent_connectivity_reported_not_substituted():
    # _first_control_input supplies NO routes -> a connectivity gap, no benchmark distance.
    r = ingest_structured_facility(_first_control_input())
    conn_gaps = r.completeness.gaps_in_domain("CONNECTIVITY")
    assert any(g.fact == "route_topology" and g.status == "NOT_MODELED" for g in conn_gaps)


# ===========================================================================
# Sec 22-25: downstream seam flags exposed but NOT implemented.
# ===========================================================================
def test_downstream_seam_flags_are_false_or_proof_only():
    r = ingest_structured_facility(_first_control_input())
    assert r.operational_state_reconstruction_implemented is False
    assert r.lockdown_created is False
    assert r.what_if_created is False
    assert r.ifc_real_hospital_ingestion_implemented is False
    assert r.bentley_itwin_real_hospital_ingestion_implemented is False
    assert r.pdf_image_reconstruction_implemented is False
    assert r.cad_dwg_dxf_parser_implemented is False
    assert r.openusd_real_hospital_ingestion_implemented is False
    # Proof/prototype seams exist but are explicitly not production ingestion.
    assert r.synthetic_ifc_proof_exists is True
    assert r.bentley_itwin_proof_seam_exists is True


def test_field_evidence_separates_origin_from_calibration():
    # A PROJECT_SUPPLIED fact may still be NOT_CALIBRATED -- independent axes.
    ev = AsIsFieldEvidence(fact="x", provenance="PROJECT_SUPPLIED", calibration="NOT_CALIBRATED", confidence="low")
    assert ev.provenance == "PROJECT_SUPPLIED"
    assert ev.calibration == "NOT_CALIBRATED"

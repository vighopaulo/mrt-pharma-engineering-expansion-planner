"""PHASE 1D -- OPERATIONAL-STATE RECONSTRUCTION AUTHORITY tests.

These deterministic invariants lock the Phase 1D contract: the operational STATE
of an existing facility is reconstructed as a distinct layer over the Phase 1C
ENGINEERING object model. Structural existence is NEVER converted to operational
availability; missing operational facts remain UNKNOWN/NOT_MODELED; nothing is
benchmark-filled; no simulation / LOCKDOWN / What-If / live API / ranking is run.

Controls A-H (Sec 36-43) are covered explicitly, plus the governing invariants
(Sec 47). Phase 1C contracts are NOT modified (test_asis_twin_phase1c.py covers
those); this suite only asserts Phase 1C is still consumable unchanged.

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
    AsIsFloorInput,
    AsIsRoomInput,
    AsIsStructuredFacilityInput,
    ingest_structured_facility,
)
from existing_facility_operational_state import (
    AppointmentStateInput,
    AsIsStructuredOperationalStateInput,
    ConflictingOperationalStateInput,
    CyclotronStateInput,
    GeneratorStateInput,
    OperationalStateReconstructionError,
    OperationalTemporalBasis,
    PatientStateInput,
    ProductionBatchStateInput,
    ResourceStateInput,
    RoomStateInput,
    ScannerStateInput,
    StaffStateInput,
    reconstruct_operational_state,
)

PET_MODEL = "GE_DISCOVERY_MI"
SPECT_MODEL = "SIEMENS_SYMBIA_PRO_SPECTA"
CYCLOTRON_MODEL = "GE_PETTRACE_890"
GENERATOR_MODEL = "CURIUM_TECHNELITE"

T0 = "2026-08-27T09:00:00+00:00"
T_HIST = "2026-01-15T09:00:00+00:00"


# ===========================================================================
# Shared facility fixtures (Phase 1C engineering models).
# ===========================================================================
def _facility_with_equipment() -> AsIsStructuredFacilityInput:
    """A facility with a PET scanner, a cyclotron, a generator and rooms; NO MRT."""
    return AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="FAC-D", facility_name="Delta Nuclear", site_id="SITE-D"),
        buildings=(AsIsBuildingInput(building_id="B1", building_name="Main"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1", elevation_m=0.0),),
        rooms=(
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R-101", room_function="PET_SCANNER",
                          length_m=6.0, width_m=5.0, height_m=3.0),
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R-CYC", room_function="CYCLOTRON",
                          length_m=8.0, width_m=8.0, height_m=3.5),
        ),
        equipment=(
            AsIsEquipmentInput(equipment_instance_id="SCN-PET-1", equipment_class="PET_SCANNER", catalog_model_id=PET_MODEL),
            AsIsEquipmentInput(equipment_instance_id="CYC-1", equipment_class="CYCLOTRON", catalog_model_id=CYCLOTRON_MODEL),
            AsIsEquipmentInput(equipment_instance_id="GEN-1", equipment_class="GENERATOR", catalog_model_id=GENERATOR_MODEL),
        ),
        equipment_placements=(
            AsIsEquipmentPlacementInput(equipment_instance_id="SCN-PET-1", room_id="R-101"),
            AsIsEquipmentPlacementInput(equipment_instance_id="CYC-1", room_id="R-CYC"),
        ),
    )


def _facility_result():
    return ingest_structured_facility(_facility_with_equipment())


def _now_basis() -> OperationalTemporalBasis:
    return OperationalTemporalBasis(kind="NOW", effective_at=T0)


# ===========================================================================
# CONTROL A (Sec 36) -- PARTIAL OPERATIONAL SNAPSHOT.
# ===========================================================================
def _control_a_input() -> AsIsStructuredOperationalStateInput:
    return AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", operational_status="AVAILABLE", effective_at=T0),),
        rooms=(RoomStateInput(spatial_object_id="R-101", occupancy_status="OCCUPIED", effective_at=T0),),
        patients=(PatientStateInput(patient_id="P-001", care_state="PRESENT_IN_FACILITY", effective_at=T0),),
        appointments=(AppointmentStateInput(appointment_id="APPT-1", patient_id="P-001",
                                             appointment_status="BOOKED", scheduled_start=T0),),
        # Cyclotron identity known but production state unknown.
        cyclotrons=(CyclotronStateInput(cyclotron_id="CYC-1"),),
        # Staff unknown (not supplied) -> no staff facts.
    )


def test_control_a_snapshot_normalizes_known_facts_survive():
    snap = reconstruct_operational_state(_facility_result(), _control_a_input())
    assert snap.snapshot_status == "NORMALIZED"
    assert snap.scanner_states[0].operational_status == "AVAILABLE"
    assert snap.room_states[0].occupancy_status == "OCCUPIED"
    assert snap.patient_states[0].care_state == "PRESENT_IN_FACILITY"
    assert snap.appointment_states[0].appointment_status == "BOOKED"


def test_control_a_unknown_facts_remain_unknown():
    snap = reconstruct_operational_state(_facility_result(), _control_a_input())
    # Cyclotron identity present, production unknown/not fabricated.
    cyc = snap.cyclotron_states[0]
    assert cyc.structural_identity_status == "IDENTITY_PRESENT"
    assert cyc.operational_status == "UNKNOWN"
    assert cyc.current_radionuclide is None
    assert cyc.current_eob_activity_mbq == "NOT_MODELED"
    # Staff not supplied -> no staff facts, domain NOT_MODELED.
    assert snap.staff_states == ()
    assert snap.domain("STAFF_RESOURCE_STATE").status == "NOT_MODELED"


def test_control_a_no_benchmark_completion():
    snap = reconstruct_operational_state(_facility_result(), _control_a_input())
    assert snap.benchmark_patient_population_inserted is False
    assert snap.benchmark_appointments_inserted is False
    assert snap.benchmark_scanner_availability_inserted is False
    assert snap.benchmark_cyclotron_availability_inserted is False
    assert snap.benchmark_staffing_inserted is False
    assert snap.benchmark_production_schedule_inserted is False
    assert snap.benchmark_room_occupancy_inserted is False


def test_control_a_baseline_simulation_not_run_and_readiness_honest():
    snap = reconstruct_operational_state(_facility_result(), _control_a_input())
    assert snap.simulation_run_during_phase_1d is False
    assert snap.asis_baseline_simulation_implemented is False
    r = snap.baseline_simulation_readiness
    assert r is not None
    assert r.baseline_simulation_run is False
    # Production state absent -> production_state_ready False (honest, not forced).
    assert r.production_state_ready is False


# ===========================================================================
# CONTROL B (Sec 37) -- INSTALLED SCANNER / UNKNOWN AVAILABILITY (Sec 11).
# ===========================================================================
def test_control_b_installed_scanner_unknown_availability():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1"),),  # installed, no state supplied
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    sc = snap.scanner_states[0]
    assert sc.structural_identity_status == "IDENTITY_PRESENT"   # SCANNER_IDENTITY_PRESENT = YES
    assert sc.operational_status == "UNKNOWN"                    # SCANNER_OPERATIONAL_STATUS = UNKNOWN
    assert sc.availability_status == "UNKNOWN"                   # SCANNER_AVAILABLE_NOW = UNKNOWN
    assert sc.availability_inferred_from_installation is False   # AVAILABILITY_INFERRED_FROM_INSTALLATION = NO


def test_control_b_scanner_state_impacts_readiness_when_required():
    # With no scanner/room/cyclotron/generator state known at all, resource
    # readiness is not satisfied (non-zero simulation readiness impact).
    op = AsIsStructuredOperationalStateInput(temporal_basis=_now_basis())
    snap = reconstruct_operational_state(_facility_result(), op)
    assert snap.baseline_simulation_readiness.resource_state_ready is False


# ===========================================================================
# CONTROL C (Sec 38) -- INSTALLED CYCLOTRON / UNKNOWN PRODUCTION (Sec 19).
# ===========================================================================
def test_control_c_installed_cyclotron_unknown_production():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        cyclotrons=(CyclotronStateInput(cyclotron_id="CYC-1"),),  # installed, no production supplied
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    cyc = snap.cyclotron_states[0]
    assert cyc.structural_identity_status == "IDENTITY_PRESENT"  # CYCLOTRON_IDENTITY_PRESENT = YES
    assert cyc.operational_status == "UNKNOWN"                   # CYCLOTRON_OPERATIONAL_STATUS = UNKNOWN
    assert cyc.current_radionuclide is None                      # CURRENT_RADIONUCLIDE = UNKNOWN
    assert cyc.current_batch_id is None                          # CURRENT_BATCH = NONE/UNKNOWN
    assert cyc.current_eob_activity_mbq == "NOT_MODELED"         # CURRENT_EOB_ACTIVITY = NOT_MODELED
    assert cyc.production_state_fabricated is False              # PRODUCTION_STATE_FABRICATED = NO


def test_control_c_cyclotron_supports_but_does_not_produce():
    # Even though GE PETtrace 890 SUPPORTS radionuclides, current production is
    # NOT inferred merely from support.
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(), cyclotrons=(CyclotronStateInput(cyclotron_id="CYC-1"),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    assert snap.cyclotron_states[0].current_radionuclide is None


# ===========================================================================
# CONTROL D (Sec 39) -- ROOM EXISTS / OCCUPANCY UNKNOWN (Sec 13).
# ===========================================================================
def test_control_d_room_exists_occupancy_unknown():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        rooms=(RoomStateInput(spatial_object_id="R-101"),),  # known room, no occupancy supplied
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    rm = snap.room_states[0]
    assert rm.occupancy_status == "UNKNOWN"                    # ROOM_OPERATIONAL_STATUS = UNKNOWN
    assert rm.availability_status == "UNKNOWN"                 # ROOM_AVAILABLE_NOW = UNKNOWN
    assert rm.availability_inferred_from_existence is False    # ROOM_AVAILABILITY_INFERRED = NO
    assert rm.current_patient_id is None                      # no patient inserted


def test_control_d_phase1c_room_identity_and_geometry_survive():
    # Room identity / geometry / classification remain in the Phase 1C model,
    # untouched by the operational layer.
    res = _facility_result()
    assert "R-101" in res.spatial_registry.objects            # ROOM_IDENTITY_PRESENT = YES
    cls = next(c for c in res.space_classifications if c.spatial_object_id == "R-101")
    assert cls.classification == "PET_SCANNER_ROOM"           # ROOM_FUNCTION_PRESENT = YES


# ===========================================================================
# CONTROL E (Sec 40) -- PATIENT EXISTS / APPOINTMENT ABSENT (Sec 15).
# ===========================================================================
def test_control_e_patient_exists_appointment_absent():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        patients=(PatientStateInput(patient_id="P-001"),),  # known patient, NO appointment supplied
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    assert snap.patient_states[0].patient_id == "P-001"       # PATIENT_IDENTITY_PRESENT = YES
    assert snap.appointment_states == ()                      # APPOINTMENT_PRESENT = NO
    # PATIENT_SCHEDULED = NO/UNKNOWN as physically justified (default UNKNOWN).
    assert snap.patient_states[0].scheduled_status == "UNKNOWN"


def test_control_e_appointment_never_fabricated_from_patient():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        patients=tuple(PatientStateInput(patient_id=f"P-{i:03d}") for i in range(5)),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    assert len(snap.patient_states) == 5
    assert snap.appointment_states == ()  # APPOINTMENT_FABRICATED = NO


# ===========================================================================
# CONTROL F (Sec 41) -- OPERATIONAL CONFLICT (Sec 27-28).
# ===========================================================================
def test_control_f_operational_conflict_preserved():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", operational_status="AVAILABLE", effective_at=T0),),
        conflicting_evidence=(ConflictingOperationalStateInput(
            domain="SCANNER_OPERATIONAL_STATE", object_id="SCN-PET-1",
            field_name="operational_status", candidate_value="OUT_OF_SERVICE", effective_at=T0),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    assert len(snap.conflicts) == 1                                  # CONFLICT_CREATED = YES
    c = snap.conflicts[0]
    assert c.object_id == "SCN-PET-1"                                # SCANNER_IDENTITY_PRESERVED = YES
    assert set(c.candidate_values) == {"AVAILABLE", "OUT_OF_SERVICE"}  # CANDIDATE_STATUSES_PRESERVED = YES
    assert c.resolution_status == "UNRESOLVED"                       # AUTO_RESOLUTION_OCCURRED = NO
    assert c.impact_on_readiness == "REDUCES_READINESS"              # READINESS_REDUCED = YES


def test_control_f_conflict_marks_snapshot_and_domain_conflicted():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", operational_status="AVAILABLE", effective_at=T0),),
        conflicting_evidence=(ConflictingOperationalStateInput(
            domain="SCANNER_OPERATIONAL_STATE", object_id="SCN-PET-1",
            field_name="operational_status", candidate_value="MAINTENANCE", effective_at=T0),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    assert snap.snapshot_status == "CONFLICTED"
    assert snap.domain("SCANNER_OPERATIONAL_STATE").status == "CONFLICTED"
    # A conflicted snapshot is NOT baseline-simulation-input ready.
    assert snap.baseline_simulation_readiness.operational_snapshot_normalized is False


# ===========================================================================
# CONTROL G (Sec 42) -- NO MRT FACILITY (Sec 23).
# ===========================================================================
def test_control_g_no_mrt_facility_zero_operational_mrt():
    res = _facility_result()
    assert res.mrt_infrastructure_count == 0
    snap = reconstruct_operational_state(res, AsIsStructuredOperationalStateInput(temporal_basis=_now_basis()))
    assert snap.mrt_operational_resource_count == 0                      # MRT_OPERATIONAL_RESOURCE_COUNT = 0
    assert snap.benchmark_mrt_operational_resource_inserted is False     # BENCHMARK_MRT_..._INSERTED = NO
    assert snap.benchmark_mrt_operational_inserted is False


def test_control_g_mrt_facts_ignored_when_no_mrt_infrastructure():
    # Even if MRT operational facts are supplied, a facility with no MRT keeps
    # the operational MRT count at 0 (never invents an MRT network).
    res = _facility_result()
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        resources=(ResourceStateInput(resource_id="MRT-CARRIER-1", resource_class="MRT",
                                      availability_status="AVAILABLE"),),
        staff=(StaffStateInput(staff_category="MRT_OPERATIONS", available_count=2),),
    )
    snap = reconstruct_operational_state(res, op)
    assert snap.mrt_operational_resource_count == 0
    assert any("MRT operational facts were supplied" in lim for lim in snap.limitations)


# ===========================================================================
# CONTROL H (Sec 43) -- STALE / UNKNOWN FRESHNESS (Sec 26).
# ===========================================================================
def test_control_h_timestamp_no_threshold_yields_unknown_freshness():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        resources=(ResourceStateInput(resource_id="SCN-PET-1", resource_class="SCANNER",
                                      observed_at="2026-08-01T00:00:00+00:00"),),  # timestamp, NO threshold
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    ev = snap.resource_states[0].evidence
    assert ev is not None
    assert ev.freshness_status == "UNKNOWN_FRESHNESS"  # fact preserved; freshness UNKNOWN; no invented threshold


def test_control_h_no_timestamp_no_threshold_is_not_applicable():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        resources=(ResourceStateInput(resource_id="SCN-PET-1", resource_class="SCANNER"),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    assert snap.resource_states[0].evidence.freshness_status == "NOT_APPLICABLE"


# ===========================================================================
# GOVERNING INVARIANTS (Sec 47).
# ===========================================================================
def test_snapshot_identity_separate_from_facility_identity():
    res = _facility_result()
    s1 = reconstruct_operational_state(res, AsIsStructuredOperationalStateInput(
        temporal_basis=OperationalTemporalBasis(kind="NOW", effective_at=T0)))
    s2 = reconstruct_operational_state(res, AsIsStructuredOperationalStateInput(
        temporal_basis=OperationalTemporalBasis(kind="HISTORICAL_POINT_IN_TIME", effective_at=T_HIST)))
    # Same facility, different effective time -> different snapshot identity.
    assert s1.facility_id == s2.facility_id == "FAC-D"
    assert s1.snapshot_id != s2.snapshot_id


def test_supplied_snapshot_id_is_honored():
    snap = reconstruct_operational_state(_facility_result(), AsIsStructuredOperationalStateInput(
        snapshot_id="OPSNAP-CUSTOM", temporal_basis=_now_basis()))
    assert snap.snapshot_id == "OPSNAP-CUSTOM"


def test_time_basis_required_for_readiness():
    # No temporal basis supplied -> UNKNOWN_TIME -> temporal domain blocks readiness.
    snap = reconstruct_operational_state(_facility_result(), AsIsStructuredOperationalStateInput())
    assert snap.temporal_basis.has_temporal_basis is False
    assert snap.domain("TEMPORAL_BASIS").status == "NOT_MODELED"
    assert snap.domain("TEMPORAL_BASIS").readiness_impact == "BLOCKING"
    assert snap.baseline_simulation_readiness.baseline_simulation_input_ready is False


def test_time_basis_not_stamped_from_wall_clock():
    # A snapshot with no supplied time must NOT be silently stamped NOW.
    snap = reconstruct_operational_state(_facility_result(), AsIsStructuredOperationalStateInput())
    assert snap.temporal_basis.kind == "UNKNOWN_TIME"
    assert snap.temporal_basis.effective_at is None
    assert snap.temporal_basis.observed_at is None


def test_installed_not_available_across_equipment_classes():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1"),),
        cyclotrons=(CyclotronStateInput(cyclotron_id="CYC-1"),),
        generators=(GeneratorStateInput(generator_id="GEN-1"),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    assert snap.scanner_states[0].availability_status == "UNKNOWN"
    assert snap.cyclotron_states[0].availability_status == "UNKNOWN"
    assert snap.generator_states[0].availability_status == "UNKNOWN"
    assert snap.scanner_states[0].availability_inferred_from_installation is False
    assert snap.cyclotron_states[0].production_state_fabricated is False
    assert snap.generator_states[0].generator_state_fabricated is False


def test_room_identity_distinct_from_occupancy():
    # Supplying occupancy does not touch Phase 1C geometry/classification.
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        rooms=(RoomStateInput(spatial_object_id="R-101", occupancy_status="CLEANING"),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    assert snap.room_states[0].occupancy_status == "CLEANING"
    # The room's clinical classification is still owned by Phase 1C, unchanged.
    res = _facility_result()
    assert any(c.spatial_object_id == "R-101" for c in res.space_classifications)


def test_patient_identity_distinct_from_appointment():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        patients=(PatientStateInput(patient_id="P-001", scheduled_status="SCHEDULED",
                                    appointment_ids=("APPT-9",)),),
        appointments=(AppointmentStateInput(appointment_id="APPT-9", patient_id="P-001",
                                             appointment_status="BOOKED"),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    assert snap.patient_states[0].patient_id == "P-001"
    assert snap.appointment_states[0].appointment_id == "APPT-9"
    assert snap.appointment_states[0].patient_id == "P-001"


def test_equipment_identity_distinct_from_current_state():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", operational_status="IN_USE",
                                    current_assignment="P-001"),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    sc = snap.scanner_states[0]
    assert sc.scanner_id == "SCN-PET-1"
    assert sc.operational_status == "IN_USE"
    assert sc.current_assignment == "P-001"


def test_production_support_distinct_from_current_production():
    # Supplying a batch fact preserves it EXACTLY; no recomputation, no decay.
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        production_batches=(ProductionBatchStateInput(
            batch_id="BATCH-1", radionuclide="F-18", source_id="CYC-1",
            production_stage="RELEASED", release_status="RELEASED",
            eob_at=T0, current_activity_mbq=18000.0),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    pb = snap.production_states[0]
    assert pb.batch_id == "BATCH-1"
    assert pb.radionuclide == "F-18"
    assert pb.current_activity_mbq == 18000.0          # preserved exactly
    assert pb.production_recalculated is False          # no production math run


def test_production_missing_activity_not_estimated():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        production_batches=(ProductionBatchStateInput(batch_id="BATCH-2", radionuclide="F-18"),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    assert snap.production_states[0].current_activity_mbq == "NOT_MODELED"  # never estimated


def test_no_benchmark_population_or_staffing_or_production():
    snap = reconstruct_operational_state(_facility_result(), AsIsStructuredOperationalStateInput(temporal_basis=_now_basis()))
    assert snap.patient_states == ()
    assert snap.staff_states == ()
    assert snap.production_states == ()
    assert snap.benchmark_patient_population_inserted is False
    assert snap.benchmark_staffing_inserted is False
    assert snap.benchmark_production_schedule_inserted is False
    assert snap.benchmark_radionuclide_demand_inserted is False


def test_staff_count_not_converted_to_people():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        staff=(StaffStateInput(staff_category="TECHNOLOGIST", available_count=3),),  # count, no person ids
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    st = snap.staff_states[0]
    assert st.available_count == 3
    assert st.person_ids == ()                        # count NOT converted into people
    assert st.category_identity_present is True
    assert st.staffing_benchmark_inserted is False


def test_no_simulation_lockdown_whatif_or_ranking():
    snap = reconstruct_operational_state(_facility_result(), _control_a_input())
    assert snap.simulation_run_during_phase_1d is False
    assert snap.four_architecture_simulation_called is False
    assert snap.part3d_feasibility_called is False
    assert snap.part3e_optimization_called is False
    assert snap.part3e1_experiments_called is False
    assert snap.part3e2_decision_envelope_called is False
    assert snap.lockdown_created is False
    assert snap.what_if_created is False
    assert snap.lockdown_authority_duplicated is False
    assert snap.existing_lockdown_lineage_seam_preserved is True
    assert snap.architecture_ranking_performed is False
    assert snap.economic_optimization_performed is False


def test_no_live_api_integrations():
    snap = reconstruct_operational_state(_facility_result(), _control_a_input())
    assert snap.live_hospital_api_implemented is False
    assert snap.aria_live_ingestion_implemented is False
    assert snap.ris_live_ingestion_implemented is False
    assert snap.pacs_live_ingestion_implemented is False
    assert snap.ehr_live_ingestion_implemented is False
    assert snap.staff_system_live_ingestion_implemented is False
    assert snap.facility_bms_live_ingestion_implemented is False


def test_phase1c_remains_unchanged_and_consumable():
    # Phase 1C ingestion still works and still reports operational-state
    # reconstruction as unimplemented ON ITS OWN result (Phase 1D does not
    # mutate the Phase 1C result).
    res = _facility_result()
    assert res.operational_state_reconstruction_implemented is False
    assert res.readiness_gates.operational_state_reconstruction_ready is False
    assert res.readiness_gates.baseline_simulation_ready is False
    # And the Phase 1D snapshot links to it without modifying it.
    snap = reconstruct_operational_state(res, _control_a_input())
    assert snap.facility_model_linked is True
    assert res.operational_state_reconstruction_implemented is False  # still untouched


def test_facility_model_readiness_inherited_from_phase1c_gate():
    res = _facility_result()
    snap = reconstruct_operational_state(res, _control_a_input())
    r = snap.baseline_simulation_readiness
    assert r.facility_model_ready == bool(res.readiness_gates.engineering_object_model_ready)


def test_empty_operational_input_is_empty_snapshot_not_error():
    snap = reconstruct_operational_state(_facility_result())
    assert snap.snapshot_status == "EMPTY"
    assert snap.resource_states == ()
    assert snap.baseline_simulation_readiness.baseline_simulation_input_ready is False


def test_domain_completeness_never_collapsed_to_one_count():
    snap = reconstruct_operational_state(_facility_result(), _control_a_input())
    domains = {d.domain for d in snap.domain_completeness}
    # Every required operational completeness domain is independently present.
    for required in (
        "SNAPSHOT_IDENTITY", "TEMPORAL_BASIS", "FACILITY_MODEL_LINKAGE", "ROOM_OPERATIONAL_STATE",
        "SCANNER_OPERATIONAL_STATE", "CYCLOTRON_OPERATIONAL_STATE", "GENERATOR_OPERATIONAL_STATE",
        "MRT_OPERATIONAL_STATE", "PATIENT_STATE", "APPOINTMENT_STATE", "STAFF_RESOURCE_STATE",
        "PRODUCTION_BATCH_STATE", "PROVENANCE", "FRESHNESS", "EVIDENCE_CONFLICTS",
        "BASELINE_SIMULATION_INPUT_READINESS",
    ):
        assert required in domains


def test_strict_identity_validation_rejects_unknown_object():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-DOES-NOT-EXIST"),),
    )
    with pytest.raises(OperationalStateReconstructionError):
        reconstruct_operational_state(_facility_result(), op, strict_identity_validation=True)


def test_non_strict_unknown_object_is_identity_absent_not_error():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-DOES-NOT-EXIST", operational_status="AVAILABLE"),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)  # default: non-strict
    assert snap.scanner_states[0].structural_identity_status == "IDENTITY_ABSENT"


def test_evidence_axes_are_independent():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", operational_status="AVAILABLE",
                                    source="MANUAL_ENTRY", effective_at=T0),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    ev = snap.scanner_states[0].evidence
    assert ev.source == "MANUAL_ENTRY"
    assert ev.provenance == "PROJECT_SUPPLIED"       # provenance independent of source axis
    assert ev.calibration == "NOT_APPLICABLE"        # calibration independent axis
    assert ev.temporal_basis.effective_at == T0      # per-fact temporal basis carried


def test_future_planned_state_snapshot_is_supported():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=OperationalTemporalBasis(kind="FUTURE_PLANNED_STATE", effective_at="2027-01-01T09:00:00+00:00"),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", operational_status="AVAILABLE"),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    assert snap.temporal_basis.kind == "FUTURE_PLANNED_STATE"
    assert snap.temporal_basis.has_temporal_basis is True


def test_generator_state_preserved_when_supplied():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        generators=(GeneratorStateInput(generator_id="GEN-1", operational_status="ELUTED_AWAITING_USE",
                                        last_elution_at=T0),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    gn = snap.generator_states[0]
    assert gn.operational_status == "ELUTED_AWAITING_USE"
    assert gn.last_elution_at == T0
    assert gn.available_daughter_activity_mbq == "NOT_MODELED"  # not fabricated


def test_project_starting_state_propagated_from_phase1c():
    snap = reconstruct_operational_state(_facility_result(), _control_a_input())
    assert snap.project_starting_state == "EXISTING_FACILITY_AS_IS"


def test_baseline_input_ready_can_be_true_with_full_operational_state():
    # A fully-specified, conflict-free, timed snapshot with resource + patient +
    # appointment state can be baseline-simulation-INPUT ready -- WITHOUT running
    # any simulation.
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", operational_status="AVAILABLE"),),
        patients=(PatientStateInput(patient_id="P-001", care_state="PRESENT_IN_FACILITY",
                                    scheduled_status="SCHEDULED"),),
        appointments=(AppointmentStateInput(appointment_id="APPT-1", patient_id="P-001",
                                            appointment_status="BOOKED"),),
    )
    snap = reconstruct_operational_state(_facility_result(), op)
    r = snap.baseline_simulation_readiness
    assert r.resource_state_ready is True
    assert r.patient_appointment_state_ready is True
    assert r.baseline_simulation_run is False  # readiness computed, sim NOT run

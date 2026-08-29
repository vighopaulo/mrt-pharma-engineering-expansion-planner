"""EXISTING FACILITY / AS-IS DIGITAL TWIN -- PHASE 1E controls & invariants.

Phase 1E establishes the first truthful baseline-simulation boundary for an
existing hospital: readiness (a first-class authority, never one bool),
required-fact manifest (the anti-fabrication mechanism), no-silent-benchmark
governor, and -- ONLY when every required fact is present -- reuse of the
EXISTING nuclear simulation engine on the supplied AS-IS facts. Blocked runs
never call the engine, never insert a benchmark fact, never create a LOCKDOWN
and never create a What-If.

These deterministic invariants lock the Sec 29-40 Controls A-L plus the
governing invariants (Sec 4-27, 41-47). They never modify Phase 1B/1C/1D
contracts (their own suites cover those); this suite only asserts those layers
are still consumable unchanged.

Real catalog identities used (never fabricated):
  PET scanner   = GE_DISCOVERY_MI
  cyclotron     = GE_PETTRACE_890  (calibrated F-18)
  CYPRIS MP-30  = SUMITOMO_CYPRIS_MP_30 (supported-but-NOT_CALIBRATED control)
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
    AsIsRouteOrConnectivityInput,
    AsIsStructuredFacilityInput,
    ingest_structured_facility,
)
from existing_facility_operational_state import (
    AsIsStructuredOperationalStateInput,
    ConflictingOperationalStateInput,
    CyclotronStateInput,
    OperationalTemporalBasis,
    RoomStateInput,
    ScannerStateInput,
    StaffStateInput,
    reconstruct_operational_state,
)
from whole_oncology_four_architecture_optimization import (
    ClinicalResourceInputs,
    build_common_project_baseline,
)
from existing_facility_baseline_simulation import (
    AsIsBaselineSimulationScope,
    AsIsBaselineSimulationResult,
    AsIsSimulationReadinessAssessment,
    assess_baseline_simulation_readiness,
    run_asis_baseline_simulation,
)

PET_MODEL = "GE_DISCOVERY_MI"
CYCLOTRON_MODEL = "GE_PETTRACE_890"
CYPRIS_MP_30 = "SUMITOMO_CYPRIS_MP_30"

T0 = "2026-08-27T09:00:00+00:00"


# ===========================================================================
# Shared Phase 1C / 1D fixtures.
# ===========================================================================
def _structural_facility(*, with_route: bool = True) -> AsIsStructuredFacilityInput:
    """A small nuclear-medicine facility: PET scanner room + cyclotron room, NO
    MRT. `with_route` connects both rooms so Phase 1C topology is COMPLETE."""
    routes = ()
    if with_route:
        routes = (AsIsRouteOrConnectivityInput(from_object_id="R-PET", to_object_id="R-CYC", length_m=12.0),)
    return AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="FAC-E", facility_name="Echo Nuclear", site_id="SITE-E"),
        buildings=(AsIsBuildingInput(building_id="B1", building_name="Main"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1", elevation_m=0.0),),
        rooms=(
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R-PET", room_function="PET_SCANNER",
                          length_m=6.0, width_m=5.0, height_m=3.0),
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R-CYC", room_function="CYCLOTRON",
                          length_m=8.0, width_m=8.0, height_m=3.5),
        ),
        equipment=(
            AsIsEquipmentInput(equipment_instance_id="SCN-PET-1", equipment_class="PET_SCANNER", catalog_model_id=PET_MODEL),
            AsIsEquipmentInput(equipment_instance_id="CYC-1", equipment_class="CYCLOTRON", catalog_model_id=CYCLOTRON_MODEL),
        ),
        equipment_placements=(
            AsIsEquipmentPlacementInput(equipment_instance_id="SCN-PET-1", room_id="R-PET"),
            AsIsEquipmentPlacementInput(equipment_instance_id="CYC-1", room_id="R-CYC"),
        ),
        routes=routes,
    )


def _twin(*, with_route: bool = True):
    return ingest_structured_facility(_structural_facility(with_route=with_route))


def _now_basis() -> OperationalTemporalBasis:
    return OperationalTemporalBasis(kind="NOW", effective_at=T0)


def _snapshot(op_input: AsIsStructuredOperationalStateInput, *, with_route: bool = True):
    return reconstruct_operational_state(_twin(with_route=with_route), op_input)


def _all_available_op_input() -> AsIsStructuredOperationalStateInput:
    """Every required resource has a supplied AVAILABLE observation."""
    return AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", operational_status="AVAILABLE",
                                    availability_status="AVAILABLE", effective_at=T0),),
        rooms=(
            RoomStateInput(spatial_object_id="R-PET", occupancy_status="AVAILABLE",
                           availability_status="AVAILABLE", effective_at=T0),
            RoomStateInput(spatial_object_id="R-CYC", occupancy_status="AVAILABLE",
                           availability_status="AVAILABLE", effective_at=T0),
        ),
        staff=(StaffStateInput(staff_category="TECHNOLOGIST", available_count=4,
                               availability_status="AVAILABLE", effective_at=T0),),
    )


def _asis_baseline():
    """An explicit CONTROLLED AS-IS study population (Sec 40 permits explicit
    controlled AS-IS inputs + canonical equipment identities). Reuses the
    canonical whole-oncology baseline as the study input -- NOT a silent
    benchmark completion of a MISSING fact."""
    return build_common_project_baseline()


def _facility_resources() -> ClinicalResourceInputs:
    """AS-IS clinical-resource counts declared as FACILITY_DERIVED (never the
    CONTROLLED_BENCHMARK source)."""
    return ClinicalResourceInputs(scanners=6, injection_resources=6, uptake_resources=12,
                                  resource_source="FACILITY_DERIVED")


def _ready_scope(**overrides) -> AsIsBaselineSimulationScope:
    """The smallest evidence-complete AS-IS scope for a successful baseline."""
    base = dict(
        service_domain="NUCLEAR_MEDICINE_ONCOLOGY",
        asis_baseline=_asis_baseline(),
        asis_clinical_resources=_facility_resources(),
        patient_demand_source="CONTROLLED_ASIS_STUDY_INPUT",
        simulation_date="2026-08-27",
        simulation_start_minute=0.0,
        simulation_horizon_minutes=600.0,
        available_transport_modes=("MANUAL",),
        installed_cyclotron_model_ids=(),
    )
    base.update(overrides)
    return AsIsBaselineSimulationScope(**base)


# ===========================================================================
# GOVERNING INVARIANTS (Sec 4-27).
# ===========================================================================
def test_readiness_is_not_one_opaque_bool():
    """Sec 5: readiness reports every domain, not a single bool."""
    r = assess_baseline_simulation_readiness(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()), scope=_ready_scope(),
        required_scanner_ids=("SCN-PET-1",),
    )
    reported = {d.domain for d in r.domain_assessments}
    assert "STRUCTURAL_TWIN_READINESS" in reported
    assert "TEMPORAL_BASIS_READINESS" in reported
    assert "PATIENT_DEMAND_READINESS" in reported
    assert "SIMULATION_INPUT_READINESS" in reported
    assert len(r.domain_assessments) >= 13


def test_readiness_distinct_from_completeness():
    """Sec 6: readiness is scoped to REQUIRED facts, not global completeness."""
    r = assess_baseline_simulation_readiness(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()), scope=_ready_scope(),
    )
    assert r.completeness_distinct_from_readiness is True


def test_simulation_scope_is_explicit():
    """Sec 7: the simulation scope names the exact service domain."""
    scope = _ready_scope()
    assert scope.service_domain == "NUCLEAR_MEDICINE_ONCOLOGY"


def test_required_fact_manifest_present_when_blocked():
    """Sec 8: a blocked readiness produces an explicit required-fact manifest."""
    scope = _ready_scope(asis_baseline=None, patient_demand_source="ABSENT")
    r = assess_baseline_simulation_readiness(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()), scope=scope,
    )
    assert any(f.domain == "PATIENT_DEMAND_READINESS" and f.blocking_if_missing for f in r.required_facts)


# ===========================================================================
# CONTROL A (Sec 29) -- INCOMPLETE AS-IS FACILITY (missing required facts).
# ===========================================================================
def test_control_a_missing_facts_block_no_engine_no_benchmark():
    scope = _ready_scope(asis_baseline=None, patient_demand_source="ABSENT",
                         asis_clinical_resources=None)
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()), scope=scope,
    )
    assert res.execution_status == "BLOCKED_MISSING_REQUIRED_FACTS"
    assert res.baseline_simulation_executed is False
    assert res.existing_simulation_engine_reused is False
    assert res.outputs is None
    # No benchmark inserted, no LOCKDOWN, no What-If.
    assert res.benchmark_patients_inserted is False
    assert res.benchmark_resources_inserted is False
    assert res.lockdown_created is False
    assert res.what_if_created is False
    assert len(res.unresolved_gaps) >= 1


# ===========================================================================
# CONTROL B (Sec 30) -- UNKNOWN SCANNER STATE.
# ===========================================================================
def test_control_b_unknown_scanner_blocks_identity_survives():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        # Scanner identity present but availability UNKNOWN (default).
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1"),),
        rooms=(
            RoomStateInput(spatial_object_id="R-PET", availability_status="AVAILABLE", effective_at=T0),
            RoomStateInput(spatial_object_id="R-CYC", availability_status="AVAILABLE", effective_at=T0),
        ),
    )
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(op), scope=_ready_scope(),
        required_scanner_ids=("SCN-PET-1",),
    )
    assert res.execution_status == "BLOCKED_MISSING_REQUIRED_FACTS"
    assert res.baseline_simulation_executed is False
    # Scanner identity survives in the snapshot; availability not inferred.
    assert res.unknown_scanner_inferred_available is False
    scanner_domain = res.readiness.domain("SCANNER_READINESS")
    assert scanner_domain.status == "BLOCKED"
    assert res.benchmark_resources_inserted is False


# ===========================================================================
# CONTROL C (Sec 31) -- MISSING PATIENT DEMAND.
# ===========================================================================
def test_control_c_missing_patient_demand_blocks_no_synthetic_patients():
    scope = _ready_scope(asis_baseline=None, patient_demand_source="ABSENT")
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()), scope=scope,
    )
    assert res.baseline_simulation_executed is False
    assert res.patient_demand_fabricated is False
    assert res.benchmark_patients_inserted is False
    assert res.readiness.domain("PATIENT_DEMAND_READINESS").status == "BLOCKED"


# ===========================================================================
# CONTROL D (Sec 32) -- PARTIAL TOPOLOGY.
# ===========================================================================
def test_control_d_partial_topology_blocks_no_edge_fabricated():
    # with_route=False -> Phase 1C topology is NOT_MODELED/PARTIAL for the rooms.
    res = run_asis_baseline_simulation(
        twin=_twin(with_route=False), snapshot=_snapshot(_all_available_op_input(), with_route=False),
        scope=_ready_scope(),
    )
    assert res.execution_status == "BLOCKED_INVALID_ROUTE"
    assert res.route_edge_fabricated is False
    assert res.transport_time_calculated_over_missing_route is False
    assert res.readiness.domain("ROUTE_TOPOLOGY_READINESS").status == "BLOCKED"
    assert res.baseline_simulation_executed is False


# ===========================================================================
# CONTROL E (Sec 33) -- NO MRT EXISTING HOSPITAL.
# ===========================================================================
def test_control_e_no_mrt_is_legal_manual_baseline_ready():
    twin = _twin()
    assert twin.mrt_infrastructure_count == 0
    assert twin.benchmark_mrt_inserted is False
    res = run_asis_baseline_simulation(
        twin=twin, snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(available_transport_modes=("MANUAL",)),
        required_scanner_ids=("SCN-PET-1",),
    )
    # MRT not required for readiness; manual baseline may execute.
    assert res.mrt_absence_supported is True
    assert res.benchmark_mrt_inserted is False
    assert res.available_transport_modes == ("MANUAL",)
    assert res.baseline_simulation_executed is True


# ===========================================================================
# CONTROL F (Sec 34) -- CONFLICTING OPERATIONAL EVIDENCE.
# ===========================================================================
def test_control_f_conflict_blocks_both_claims_survive():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", operational_status="AVAILABLE",
                                    availability_status="AVAILABLE", effective_at=T0),),
        rooms=(
            RoomStateInput(spatial_object_id="R-PET", availability_status="AVAILABLE", effective_at=T0),
            RoomStateInput(spatial_object_id="R-CYC", availability_status="AVAILABLE", effective_at=T0),
        ),
        conflicting_evidence=(ConflictingOperationalStateInput(
            domain="SCANNER_OPERATIONAL_STATE", object_id="SCN-PET-1", field_name="operational_status",
            candidate_value="OUT_OF_SERVICE", effective_at=T0,
        ),),
    )
    snap = _snapshot(op)
    # Both candidate claims are preserved in the Phase 1D conflict record.
    assert len(snap.conflicts) >= 1
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=snap, scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    assert res.execution_status == "BLOCKED_CONFLICTING_REQUIRED_FACT"
    assert res.baseline_simulation_executed is False
    assert res.lockdown_created is False
    assert res.what_if_created is False
    assert res.readiness.domain("CONFLICT_READINESS").status == "BLOCKED"


# ===========================================================================
# CONTROL G (Sec 35) -- TEMPORAL BASIS MISSING.
# ===========================================================================
def test_control_g_missing_temporal_basis_blocks_no_time_invented():
    # Phase 1D snapshot with UNKNOWN_TIME basis AND scope with no supplied time.
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=OperationalTemporalBasis(),  # UNKNOWN_TIME
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", availability_status="AVAILABLE", effective_at=T0),),
        rooms=(
            RoomStateInput(spatial_object_id="R-PET", availability_status="AVAILABLE", effective_at=T0),
            RoomStateInput(spatial_object_id="R-CYC", availability_status="AVAILABLE", effective_at=T0),
        ),
    )
    scope = _ready_scope(simulation_date=None, simulation_start_minute=None, simulation_horizon_minutes=None)
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(op), scope=scope, required_scanner_ids=("SCN-PET-1",),
    )
    assert res.execution_status == "BLOCKED_TEMPORAL_BASIS"
    assert res.baseline_simulation_executed is False
    assert res.readiness.domain("TEMPORAL_BASIS_READINESS").status == "BLOCKED"


def test_control_g_scope_supplied_time_satisfies_basis():
    # Even with UNKNOWN_TIME snapshot, a scope-supplied time basis is valid.
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=OperationalTemporalBasis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", availability_status="AVAILABLE", effective_at=T0),),
        rooms=(
            RoomStateInput(spatial_object_id="R-PET", availability_status="AVAILABLE", effective_at=T0),
            RoomStateInput(spatial_object_id="R-CYC", availability_status="AVAILABLE", effective_at=T0),
        ),
    )
    r = assess_baseline_simulation_readiness(
        twin=_twin(), snapshot=_snapshot(op), scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    assert r.domain("TEMPORAL_BASIS_READINESS").status == "READY"


# ===========================================================================
# CONTROL H (Sec 36) -- UNKNOWN ROOM OPERATIONAL STATE.
# ===========================================================================
def test_control_h_unknown_room_blocks_identity_survives():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", availability_status="AVAILABLE", effective_at=T0),),
        # R-PET availability UNKNOWN (default).
        rooms=(RoomStateInput(spatial_object_id="R-PET"),),
    )
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(op), scope=_ready_scope(),
        required_room_ids=("R-PET",),
    )
    assert res.execution_status == "BLOCKED_MISSING_REQUIRED_FACTS"
    assert res.unknown_room_inferred_available is False
    assert res.readiness.domain("ROOM_AVAILABILITY_READINESS").status == "BLOCKED"


# ===========================================================================
# CONTROL I (Sec 37) -- UNKNOWN CYCLOTRON STATE.
# ===========================================================================
def test_control_i_unknown_cyclotron_blocks_when_production_required():
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", availability_status="AVAILABLE", effective_at=T0),),
        rooms=(
            RoomStateInput(spatial_object_id="R-PET", availability_status="AVAILABLE", effective_at=T0),
            RoomStateInput(spatial_object_id="R-CYC", availability_status="AVAILABLE", effective_at=T0),
        ),
        # Cyclotron identity known, operating/availability UNKNOWN.
        cyclotrons=(CyclotronStateInput(cyclotron_id=CYPRIS_MP_30),),
    )
    scope = _ready_scope(installed_cyclotron_model_ids=(CYPRIS_MP_30,))
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(op), scope=scope, required_scanner_ids=("SCN-PET-1",),
    )
    assert res.execution_status == "BLOCKED_MISSING_REQUIRED_FACTS"
    assert res.unknown_cyclotron_inferred_available is False
    assert res.readiness.domain("PRODUCTION_READINESS").status == "BLOCKED"


def test_control_i_no_local_production_required_is_not_applicable():
    # No installed cyclotron declared -> local production NOT_APPLICABLE.
    r = assess_baseline_simulation_readiness(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()), scope=_ready_scope(),
    )
    assert r.domain("PRODUCTION_READINESS").status == "NOT_APPLICABLE"


# ===========================================================================
# CONTROL J (Sec 38) -- PRODUCTION NOT CALIBRATED (support preserved).
# ===========================================================================
def test_control_j_not_calibrated_production_qualified_not_blocked():
    # Cyclotron declared + AVAILABLE, but CYPRIS MP-30 F-18 is supported-but-
    # NOT_CALIBRATED: the baseline runs with QUALIFIED UNCERTAINTY, never blocked
    # and never promoted to calibrated.
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", availability_status="AVAILABLE", effective_at=T0),),
        rooms=(
            RoomStateInput(spatial_object_id="R-PET", availability_status="AVAILABLE", effective_at=T0),
            RoomStateInput(spatial_object_id="R-CYC", availability_status="AVAILABLE", effective_at=T0),
        ),
        cyclotrons=(CyclotronStateInput(cyclotron_id=CYPRIS_MP_30, operational_status="AVAILABLE",
                                        availability_status="AVAILABLE", effective_at=T0),),
    )
    scope = _ready_scope(installed_cyclotron_model_ids=(CYPRIS_MP_30,))
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(op), scope=scope, required_scanner_ids=("SCN-PET-1",),
    )
    assert res.baseline_simulation_executed is True
    assert res.execution_status == "EXECUTED_WITH_QUALIFIED_UNCERTAINTY"
    assert res.production_calibration_borrowed is False
    # NOT_CALIBRATED preserved as a qualified uncertainty (per radionuclide).
    assert any("not_calibrated" in q.lower() for q in res.qualified_uncertainties)


def test_control_j_production_gate_is_radionuclide_specific():
    """A calibrated F-18 record never qualifies a CYPRIS MP-30 F-18 pair as
    calibrated -- the per-radionuclide gate carries the real identity."""
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1", availability_status="AVAILABLE", effective_at=T0),),
        rooms=(
            RoomStateInput(spatial_object_id="R-PET", availability_status="AVAILABLE", effective_at=T0),
            RoomStateInput(spatial_object_id="R-CYC", availability_status="AVAILABLE", effective_at=T0),
        ),
        cyclotrons=(CyclotronStateInput(cyclotron_id=CYPRIS_MP_30, availability_status="AVAILABLE", effective_at=T0),),
    )
    scope = _ready_scope(installed_cyclotron_model_ids=(CYPRIS_MP_30,))
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(op), scope=scope, required_scanner_ids=("SCN-PET-1",),
    )
    pf = res.physical_feasibility
    assert pf is not None
    gates = pf.per_radionuclide_production_gates
    assert gates, "expected at least one per-radionuclide production gate"
    # At least one gate is NOT_CALIBRATED (not silently promoted to SUFFICIENT).
    statuses = {g.status for g in gates}
    assert "PRODUCTION_NOT_CALIBRATED" in statuses or "NO_COMPATIBLE_SOURCE" in statuses


# ===========================================================================
# CONTROL K (Sec 39) -- MANUAL-ONLY EXISTING FACILITY.
# ===========================================================================
def test_control_k_manual_only_facility_executes():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(available_transport_modes=("MANUAL",)),
        required_scanner_ids=("SCN-PET-1",),
    )
    assert res.available_transport_modes == ("MANUAL",)
    assert res.benchmark_mrt_inserted is False
    assert res.baseline_simulation_executed is True
    assert res.readiness.domain("TRANSPORT_READINESS").status == "READY"


def test_no_transport_mode_blocks():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(available_transport_modes=()),
        required_scanner_ids=("SCN-PET-1",),
    )
    assert res.execution_status == "BLOCKED_MISSING_REQUIRED_FACTS"
    assert res.readiness.domain("TRANSPORT_READINESS").status == "BLOCKED"


# ===========================================================================
# CONTROL L (Sec 40) -- SUCCESSFUL READY BASELINE.
# ===========================================================================
def test_control_l_ready_baseline_executes_via_existing_engine():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    assert res.readiness.simulation_input_ready is True
    assert res.readiness.domain("SIMULATION_INPUT_READINESS").status == "READY"
    assert res.execution_status in ("EXECUTED", "EXECUTED_WITH_QUALIFIED_UNCERTAINTY")
    assert res.baseline_simulation_executed is True
    assert res.existing_simulation_engine_reused is True


def test_control_l_ready_baseline_preserves_identities_and_movement():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    assert res.outputs is not None
    assert len(res.outputs.patient_trajectories) >= 1
    # Patient identity survives (canonical id populated).
    assert all(getattr(t, "canonical_patient_id", None) is not None for t in res.outputs.patient_trajectories)
    # Radionuclide identity survives.
    assert res.outputs.radionuclide != ""
    # Movement/trajectory seam preserved.
    assert res.patient_trajectory_seam_preserved is True
    assert res.outputs.patient_movement_visible is True


def test_control_l_no_benchmark_inserted_all_governor_flags_false():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    assert res.benchmark_patients_inserted is False
    assert res.benchmark_resources_inserted is False
    assert res.benchmark_geometry_inserted is False
    assert res.benchmark_production_inserted is False
    assert res.benchmark_mrt_inserted is False
    assert res.benchmark_staffing_inserted is False


def test_control_l_validation_required_not_auto_validated():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    assert res.validation_status == "VALIDATION_REQUIRED"
    assert res.validation_status != "VALIDATED"


def test_control_l_lockdown_eligibility_but_not_created():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    assert res.lockdown_eligibility_status == "VALIDATION_REQUIRED"
    assert res.lockdown_created is False


def test_control_l_no_what_if_created():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    assert res.what_if_created is False
    assert res.what_if_execution_started is False
    assert res.what_if_baseline_mutated is False


def test_control_l_baseline_candidate_present_and_not_lockdown():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    cand = res.baseline_candidate
    assert cand is not None
    assert cand.facility_id == "FAC-E"
    assert cand.validation_status == "VALIDATION_REQUIRED"
    assert cand.lockdown_eligibility_status == "VALIDATION_REQUIRED"


# ===========================================================================
# SIMULATION INPUT TRACEABILITY (Sec 41) + INPUT ADAPTER (Sec 22).
# ===========================================================================
def test_input_mappings_are_auditable_and_benchmark_free():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    assert len(res.input_mappings) >= 1
    for m in res.input_mappings:
        assert m.assumption_status == "MAPPED_FROM_ASIS_FACT"
        assert m.source_provenance != "CONTROLLED_BENCHMARK"


def test_blocked_run_produces_no_input_mappings():
    scope = _ready_scope(asis_baseline=None, patient_demand_source="ABSENT")
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()), scope=scope,
    )
    assert res.input_mappings == ()


# ===========================================================================
# CLINICAL-RESOURCE INPUT AUTHORITY (Sec 9).
# ===========================================================================
def test_benchmark_clinical_resource_source_rejected_for_asis():
    scope = _ready_scope(asis_clinical_resources=ClinicalResourceInputs())  # CONTROLLED_BENCHMARK default
    r = assess_baseline_simulation_readiness(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()), scope=scope,
        required_scanner_ids=("SCN-PET-1",),
    )
    assert r.domain("CLINICAL_RESOURCE_READINESS").status == "BLOCKED"
    assert r.simulation_input_ready is False


def test_missing_clinical_resources_block():
    scope = _ready_scope(asis_clinical_resources=None)
    r = assess_baseline_simulation_readiness(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()), scope=scope,
    )
    assert r.domain("CLINICAL_RESOURCE_READINESS").status == "BLOCKED"


# ===========================================================================
# ENGINE REUSE + STOP-BOUNDARY (Sec 21, 26-28, 45-47).
# ===========================================================================
def test_engine_reused_only_on_ready_path():
    ready = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    blocked = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(asis_baseline=None, patient_demand_source="ABSENT"),
    )
    assert ready.existing_simulation_engine_reused is True
    assert blocked.existing_simulation_engine_reused is False


def test_blocked_baseline_is_not_eligible_for_lockdown():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(asis_baseline=None, patient_demand_source="ABSENT"),
    )
    assert res.lockdown_eligibility_status == "NOT_ELIGIBLE"
    assert res.validation_status == "NOT_VALIDATED"


def test_radionuclide_identity_preserved_not_collapsed():
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    assert res.readiness.domain("RADIONUCLIDE_READINESS").status == "READY"
    # Every simulated patient carries its own radionuclide via the canonical procedure.
    assert res.outputs.radionuclide != ""


# ===========================================================================
# PHASE 1C / 1D PRESERVATION (Sec 51 spot-check consumability).
# ===========================================================================
def test_phase1c_twin_consumable_unchanged():
    twin = _twin()
    assert twin.facility_identity.facility_id == "FAC-E"
    assert twin.benchmark_mrt_inserted is False
    assert twin.benchmark_cyclotron_inserted is False
    assert twin.mrt_required_for_engineering_model_ready is False


def test_phase1d_snapshot_consumable_unchanged():
    snap = _snapshot(_all_available_op_input())
    assert snap.facility_model_linked is True
    assert snap.benchmark_patient_population_inserted is False
    assert snap.benchmark_scanner_availability_inserted is False
    assert snap.benchmark_mrt_operational_inserted is False


def test_phase1d_unknown_availability_never_inferred_available():
    # A scanner with no availability observation stays UNKNOWN (Phase 1D proof).
    op = AsIsStructuredOperationalStateInput(
        temporal_basis=_now_basis(),
        scanners=(ScannerStateInput(scanner_id="SCN-PET-1"),),
    )
    snap = _snapshot(op)
    assert snap.scanner_states[0].availability_status == "UNKNOWN"
    assert snap.scanner_states[0].availability_inferred_from_installation is False

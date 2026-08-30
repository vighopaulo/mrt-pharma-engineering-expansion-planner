"""Phase 1F -- AS-IS Baseline Validation Authority: deterministic invariants.

These lock the Sec 31-43 Controls A-M plus the governing invariants (Sec 4-30,
44-49). SIMULATION EXECUTION != VALIDATION: a baseline that merely ran is
VALIDATION_INSUFFICIENT until observed evidence supports it. Missing evidence
stays missing; the authority never manufactures agreement.

The Phase 1E baseline candidate is consumed READ-ONLY and never rebuilt, never
mutated, never auto-tuned. Real catalog identities are used (never fabricated):
  PET scanner = GE_DISCOVERY_MI
  cyclotron   = GE_PETTRACE_890  (calibrated F-18)
"""

from __future__ import annotations

import pytest

from existing_facility_asis_twin import (
    AsIsBuildingInput, AsIsEquipmentInput, AsIsEquipmentPlacementInput,
    AsIsFacilityIdentityInput, AsIsFloorInput, AsIsRoomInput,
    AsIsRouteOrConnectivityInput, AsIsStructuredFacilityInput, ingest_structured_facility,
)
from existing_facility_operational_state import (
    AsIsStructuredOperationalStateInput, OperationalTemporalBasis, RoomStateInput,
    ScannerStateInput, StaffStateInput, reconstruct_operational_state,
)
from whole_oncology_four_architecture_optimization import (
    ClinicalResourceInputs, build_common_project_baseline,
)
from existing_facility_baseline_simulation import (
    AsIsBaselineSimulationScope, AsIsBaselineSimulationResult,
    AsIsBaselineSimulationOutputs, run_asis_baseline_simulation,
)
from hybrid_optimization import HybridPatientTrace

import existing_facility_baseline_validation as v
from existing_facility_baseline_validation import (
    AsIsBaselineValidationEvidence, AsIsValidationTolerance,
    AsIsRequiredValidationDimension, validate_asis_baseline,
    default_required_manifest,
)

PET_MODEL = "GE_DISCOVERY_MI"
CYCLOTRON_MODEL = "GE_PETTRACE_890"
T0 = "2026-08-27T09:00:00+00:00"


# ===========================================================================
# Shared fixtures -- a real EXECUTED Phase 1E baseline candidate.
# ===========================================================================
def _structural_facility(*, with_route: bool = True) -> AsIsStructuredFacilityInput:
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


def _all_available_op_input() -> AsIsStructuredOperationalStateInput:
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


def _snapshot(op_input, *, with_route: bool = True):
    return reconstruct_operational_state(_twin(with_route=with_route), op_input)


def _ready_scope(**overrides) -> AsIsBaselineSimulationScope:
    base = dict(
        service_domain="NUCLEAR_MEDICINE_ONCOLOGY",
        asis_baseline=build_common_project_baseline(),
        asis_clinical_resources=ClinicalResourceInputs(
            scanners=6, injection_resources=6, uptake_resources=12, resource_source="FACILITY_DERIVED"),
        patient_demand_source="CONTROLLED_ASIS_STUDY_INPUT",
        simulation_date="2026-08-27", simulation_start_minute=0.0,
        simulation_horizon_minutes=600.0, available_transport_modes=("MANUAL",),
        installed_cyclotron_model_ids=(),
    )
    base.update(overrides)
    return AsIsBaselineSimulationScope(**base)


@pytest.fixture(scope="module")
def executed_baseline() -> AsIsBaselineSimulationResult:
    """A real EXECUTED Phase 1E candidate (carries a NOT_CALIBRATED Tc-99m
    qualified uncertainty -> ceiling is VALIDATED_WITH_QUALIFICATIONS)."""
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()),
        scope=_ready_scope(), required_scanner_ids=("SCN-PET-1",),
    )
    assert res.baseline_simulation_executed is True
    return res


@pytest.fixture(scope="module")
def blocked_baseline() -> AsIsBaselineSimulationResult:
    """A real BLOCKED Phase 1E candidate (no engine call)."""
    scope = _ready_scope(asis_baseline=None, patient_demand_source="ABSENT", asis_clinical_resources=None)
    res = run_asis_baseline_simulation(
        twin=_twin(), snapshot=_snapshot(_all_available_op_input()), scope=scope,
    )
    assert res.baseline_simulation_executed is False
    return res


def _sim_throughput(baseline) -> int:
    return baseline.outputs.retention_qualified_completed


def _sim_scanner_peak(baseline) -> int:
    return baseline.outputs.scanner_peak_occupancy


def _throughput_ev(value, **kw):
    return AsIsBaselineValidationEvidence(
        dimension="PATIENT_THROUGHPUT", observed_value=value, unit="patients",
        source="OBSERVED_OPERATIONAL_RECORD", source_record_id="OBS-THR", **kw)


def _feasibility_ev(value="FEASIBLE", **kw):
    return AsIsBaselineValidationEvidence(
        dimension="OPERATIONAL_FEASIBILITY", observed_value=value, unit="verdict",
        source="OBSERVED_OPERATIONAL_RECORD", source_record_id="OBS-FEAS", **kw)


def _scanner_ev(value, **kw):
    return AsIsBaselineValidationEvidence(
        dimension="SCANNER_UTILIZATION", observed_value=value, unit="peak",
        source="MEASURED", source_record_id="OBS-SCN", object_identity="SCN-PET-1", **kw)


def _all_required_tolerances():
    return (
        AsIsValidationTolerance(dimension="PATIENT_THROUGHPUT", provenance="PROJECT_SUPPLIED", absolute_tolerance=1.0),
        AsIsValidationTolerance(dimension="SCANNER_UTILIZATION", provenance="PROJECT_SUPPLIED", absolute_tolerance=1.0),
    )


def _all_required_pass_evidence(baseline):
    return (
        _throughput_ev(_sim_throughput(baseline)),
        _feasibility_ev("FEASIBLE"),
        _scanner_ev(_sim_scanner_peak(baseline)),
    )


# A controlled clean baseline (empty qualified_uncertainties) built from REAL
# Phase 1E types -- used only for Control M (fully VALIDATED). This is a
# controlled baseline candidate, not fabricated observed evidence.
def _clean_executed_baseline(base: AsIsBaselineSimulationResult) -> AsIsBaselineSimulationResult:
    import dataclasses
    outputs = base.outputs
    clean_outputs = dataclasses.replace(outputs)  # same real values
    return dataclasses.replace(
        base, qualified_uncertainties=(), execution_status="EXECUTED",
        outputs=clean_outputs,
    )


# ===========================================================================
# GOVERNING INVARIANTS (Sec 4-30).
# ===========================================================================
def test_result_consumes_phase1e_candidate_identity(executed_baseline):
    """Sec 4: validation identifies exactly which candidate it validated."""
    r = validate_asis_baseline(baseline_result=executed_baseline)
    assert r.facility_id == executed_baseline.facility_id
    assert r.operational_snapshot_id == executed_baseline.operational_snapshot_id
    assert r.baseline_candidate_execution_status == executed_baseline.execution_status


def test_validation_result_has_stable_identity(executed_baseline):
    """Sec 47: each validation result carries a stable id."""
    r = validate_asis_baseline(baseline_result=executed_baseline)
    assert r.validation_result_id
    assert executed_baseline.facility_id in r.validation_result_id


def test_result_is_not_one_bool(executed_baseline):
    """Sec 25: comparisons, conflicts, coverage, status, gaps are all first-class."""
    r = validate_asis_baseline(baseline_result=executed_baseline)
    assert hasattr(r, "comparisons")
    assert hasattr(r, "conflicts")
    assert hasattr(r, "coverage")
    assert hasattr(r, "validation_gaps")
    assert hasattr(r, "required_manifest")


def test_required_manifest_present(executed_baseline):
    """Sec 29: an explicit required-dimension manifest exists."""
    r = validate_asis_baseline(baseline_result=executed_baseline)
    assert len(r.required_manifest) >= 3
    assert any(m.dimension == "PATIENT_THROUGHPUT" and m.required for m in r.required_manifest)


def test_requiredness_is_declared_not_inferred_from_data(executed_baseline):
    """Sec 29: requiredness is declared; supplying data for an optional dim does
    not make it required."""
    r = validate_asis_baseline(
        baseline_result=executed_baseline,
        evidence=(AsIsBaselineValidationEvidence(
            dimension="PATIENT_TIMING", observed_value=74.0, unit="min",
            source="MEASURED", source_record_id="OBS-T", object_identity="P1"),),
    )
    timing = next(m for m in r.required_manifest if m.dimension == "PATIENT_TIMING")
    assert timing.required is False


def test_dimensions_vocabulary_covers_required_categories():
    """Sec 7: the dimension vocabulary includes the core categories."""
    for d in ("PATIENT_THROUGHPUT", "PATIENT_TIMING", "SCANNER_UTILIZATION",
              "RADIONUCLIDE_ACTIVITY", "PATIENT_TRAJECTORY", "OPERATIONAL_FEASIBILITY"):
        assert d in v.ValidationDimension.__args__


def test_coverage_is_first_class(executed_baseline):
    """Sec 8: coverage reports required/comparable/passed/unresolved separately."""
    r = validate_asis_baseline(baseline_result=executed_baseline)
    cov = r.coverage
    assert cov.required_count >= 3
    assert isinstance(cov.dimensions_passed, tuple)
    assert isinstance(cov.dimensions_unresolved, tuple)


def test_execution_is_not_validation(executed_baseline):
    """Sec 0: a baseline that merely executed is NOT validated with no evidence."""
    r = validate_asis_baseline(baseline_result=executed_baseline)
    assert r.validation_status in ("VALIDATION_INSUFFICIENT", "NOT_VALIDATED")
    assert r.is_lockdown_eligible is False


# ===========================================================================
# OBSERVED vs SIMULATED SEPARATION (Sec 6).
# ===========================================================================
def test_observed_and_simulated_both_preserved(executed_baseline):
    """Sec 6: a comparison preserves BOTH observed and simulated; neither
    overwrites the other."""
    r = validate_asis_baseline(
        baseline_result=executed_baseline,
        evidence=(_throughput_ev(_sim_throughput(executed_baseline)),),
        tolerances=_all_required_tolerances(),
    )
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_THROUGHPUT")
    assert c.observed_value is not None
    assert c.simulated_value is not None
    assert c.difference == 0.0


def test_evidence_provenance_preserved(executed_baseline):
    """Sec 23: provenance (source + record id) survives into the comparison."""
    r = validate_asis_baseline(
        baseline_result=executed_baseline,
        evidence=(_throughput_ev(_sim_throughput(executed_baseline)),),
        tolerances=_all_required_tolerances(),
    )
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_THROUGHPUT")
    assert c.observed_source == "OBSERVED_OPERATIONAL_RECORD"
    assert c.observed_record_id == "OBS-THR"


def test_no_simulation_output_evidence_source():
    """Sec 6: there is deliberately no SIMULATION_OUTPUT evidence source."""
    assert "SIMULATION_OUTPUT" not in v.ValidationEvidenceSource.__args__


# ===========================================================================
# CONTROL A (Sec 31) -- NO VALIDATION EVIDENCE.
# ===========================================================================
def test_control_a_no_evidence_insufficient_not_eligible(executed_baseline):
    r = validate_asis_baseline(baseline_result=executed_baseline)
    assert r.validation_status == "VALIDATION_INSUFFICIENT"
    assert r.lockdown_eligibility_status in ("VALIDATION_INSUFFICIENT", "NOT_ELIGIBLE")
    assert r.is_lockdown_eligible is False
    assert r.coverage.coverage_ratio == 0.0
    # No observations fabricated; every required dim reports a missing-observed gap.
    assert any(g.kind == "MISSING_OBSERVED_EVIDENCE" for g in r.validation_gaps)
    assert r.lockdown_created is False
    assert r.what_if_created is False


# ===========================================================================
# CONTROL B (Sec 32) -- PARTIAL VALIDATION EVIDENCE.
# ===========================================================================
def test_control_b_partial_evidence(executed_baseline):
    # Supply only PATIENT_THROUGHPUT (one of several required); others missing.
    r = validate_asis_baseline(
        baseline_result=executed_baseline,
        evidence=(_throughput_ev(_sim_throughput(executed_baseline)),),
        tolerances=_all_required_tolerances(),
    )
    assert r.validation_status in ("PARTIALLY_VALIDATED", "VALIDATION_INSUFFICIENT")
    # Missing required dimensions remain missing (not passing).
    missing = {g.dimension for g in r.validation_gaps if g.kind == "MISSING_OBSERVED_EVIDENCE"}
    assert "OPERATIONAL_FEASIBILITY" in missing or "SCANNER_UTILIZATION" in missing
    assert r.is_lockdown_eligible is False


# ===========================================================================
# CONTROL C (Sec 33) -- WITHIN-TOLERANCE OBSERVATION.
# ===========================================================================
def test_control_c_within_tolerance(executed_baseline):
    obs = _sim_throughput(executed_baseline)  # exact match
    r = validate_asis_baseline(
        baseline_result=executed_baseline,
        evidence=(_throughput_ev(obs),),
        tolerances=(AsIsValidationTolerance(
            dimension="PATIENT_THROUGHPUT", provenance="PROJECT_SUPPLIED", absolute_tolerance=1.0),),
    )
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_THROUGHPUT")
    assert c.status == "WITHIN_TOLERANCE"
    assert c.difference == 0.0
    assert c.tolerance is not None and c.tolerance.provenance == "PROJECT_SUPPLIED"


# ===========================================================================
# CONTROL D (Sec 34) -- OUTSIDE-TOLERANCE OBSERVATION.
# ===========================================================================
def test_control_d_outside_tolerance(executed_baseline):
    obs = _sim_throughput(executed_baseline) - 10  # far off
    r = validate_asis_baseline(
        baseline_result=executed_baseline,
        evidence=(_throughput_ev(obs),),
        tolerances=(AsIsValidationTolerance(
            dimension="PATIENT_THROUGHPUT", provenance="PROJECT_SUPPLIED", absolute_tolerance=1.0),),
    )
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_THROUGHPUT")
    assert c.status == "OUTSIDE_TOLERANCE"
    assert c.difference is not None and abs(c.difference) >= 10
    # A required-dimension failure blocks eligibility.
    assert r.validation_status == "VALIDATION_INSUFFICIENT"
    assert r.is_lockdown_eligible is False
    # Baseline not adjusted to fit the observation.
    assert r.model_parameters_auto_tuned is False
    assert r.baseline_mutated_by_validation is False


# ===========================================================================
# CONTROL E (Sec 35) -- NO TOLERANCE.
# ===========================================================================
def test_control_e_no_tolerance(executed_baseline):
    obs = _sim_throughput(executed_baseline) - 1
    r = validate_asis_baseline(
        baseline_result=executed_baseline,
        evidence=(_throughput_ev(obs),),
        tolerances=(),  # none supplied
    )
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_THROUGHPUT")
    assert c.status == "TOLERANCE_NOT_MODELED"
    assert c.difference is not None  # difference reported
    # Not automatically pass/fail.
    assert c.status not in ("WITHIN_TOLERANCE", "OUTSIDE_TOLERANCE")
    assert any(g.kind == "TOLERANCE_NOT_MODELED" for g in r.validation_gaps)


# ===========================================================================
# CONTROL F (Sec 36) -- CONFLICTING OBSERVATIONS.
# ===========================================================================
def test_control_f_conflicting_observations(executed_baseline):
    sim = _sim_throughput(executed_baseline)
    ev = (
        AsIsBaselineValidationEvidence(dimension="PATIENT_THROUGHPUT", observed_value=sim, unit="patients",
                                       source="MEASURED", source_record_id="OBS-A"),
        AsIsBaselineValidationEvidence(dimension="PATIENT_THROUGHPUT", observed_value=sim + 7, unit="patients",
                                       source="IMPORTED", source_record_id="OBS-B"),
    )
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev, tolerances=_all_required_tolerances())
    # Both observations survive; not auto-resolved.
    assert len(r.conflicts) == 1
    conf = r.conflicts[0]
    assert conf.resolution_status == "UNRESOLVED"
    assert len(conf.candidate_values) == 2
    # Dimension is CONFLICTED and eligibility blocked (required dimension).
    assert any(c.status == "CONFLICTED_EVIDENCE" for c in r.comparisons)
    assert r.is_lockdown_eligible is False


# ===========================================================================
# CONTROL G (Sec 37) -- INCOMPATIBLE TIME WINDOWS.
# ===========================================================================
def test_control_g_incompatible_windows(executed_baseline):
    other_window = OperationalTemporalBasis(kind="HISTORICAL", effective_at="2019-01-01T00:00:00+00:00")
    ev = (_throughput_ev(_sim_throughput(executed_baseline), observation_window=other_window),)
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev, tolerances=_all_required_tolerances())
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_THROUGHPUT")
    assert c.status == "NOT_COMPARABLE"
    assert any(g.kind == "INCOMPATIBLE_OBSERVATION_WINDOW" for g in r.validation_gaps)
    # No silent rescaling: simulated not filled.
    assert c.simulated_value is None
    assert r.is_lockdown_eligible is False


# ===========================================================================
# CONTROL H (Sec 38) -- MISSING SIMULATED METRIC.
# ===========================================================================
def test_control_h_missing_simulated_metric(executed_baseline):
    # QUEUE_WAIT_TIME is not exposed by the existing engine.
    ev = (AsIsBaselineValidationEvidence(dimension="QUEUE_WAIT_TIME", observed_value=12.0, unit="min",
                                         source="MEASURED", source_record_id="OBS-Q", object_identity="INJ-1"),)
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev)
    c = next(c for c in r.comparisons if c.dimension == "QUEUE_WAIT_TIME")
    assert c.status == "MISSING_SIMULATED_EVIDENCE"
    assert c.observed_value == 12.0  # observed survives
    assert c.simulated_value is None  # never fabricated
    assert any(g.kind == "MISSING_SIMULATED_EVIDENCE" for g in r.validation_gaps)


# ===========================================================================
# CONTROL I (Sec 39) -- MISSING OBSERVED METRIC.
# ===========================================================================
def test_control_i_missing_observed_metric(executed_baseline):
    ev = (_throughput_ev(None),)  # observed value absent
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev, tolerances=_all_required_tolerances())
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_THROUGHPUT")
    assert c.status == "MISSING_OBSERVED_EVIDENCE"
    assert c.observed_value is None
    assert c.simulated_value is not None  # simulated survives
    assert any(g.kind == "MISSING_OBSERVED_EVIDENCE" for g in r.validation_gaps)


# ===========================================================================
# CONTROL J (Sec 40) -- IDENTITY MISMATCH.
# ===========================================================================
def test_control_j_identity_mismatch(executed_baseline):
    # Observed scanner id refers to a scanner not in the simulated trajectories.
    ev = (AsIsBaselineValidationEvidence(dimension="PATIENT_TIMING", observed_value=74.0, unit="min",
                                         source="MEASURED", source_record_id="OBS-ID",
                                         object_identity="PATIENT-DOES-NOT-EXIST"),)
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev)
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_TIMING")
    # No trace matches -> simulated metric not available; no silent pooling.
    assert c.status == "MISSING_SIMULATED_EVIDENCE"
    assert c.simulated_value is None


# ===========================================================================
# CONTROL K (Sec 41) -- RADIONUCLIDE MISMATCH.
# ===========================================================================
def test_control_k_radionuclide_mismatch(executed_baseline):
    # Simulated radionuclide is F-18; supply observed activity for C-11.
    ev = (AsIsBaselineValidationEvidence(dimension="RADIONUCLIDE_ACTIVITY", observed_value=370.0, unit="MBq",
                                         source="MEASURED", source_record_id="OBS-ACT",
                                         radionuclide="C-11", activity_reference_minutes=0.0),)
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev)
    c = next(c for c in r.comparisons if c.dimension == "RADIONUCLIDE_ACTIVITY")
    assert c.status == "NOT_COMPARABLE"
    assert any(g.kind == "RADIONUCLIDE_MISMATCH" for g in r.validation_gaps)
    # No decay conversion used to equate them.
    assert c.simulated_value != 370.0


def test_activity_reference_time_routed_through_decay_authority(executed_baseline):
    """Sec 20: same-radionuclide activity is decay-normalized through the ONE
    authority (retained_fraction); no second decay equation is introduced."""
    ev = (AsIsBaselineValidationEvidence(dimension="RADIONUCLIDE_ACTIVITY", observed_value=370.0, unit="MBq",
                                         source="MEASURED", source_record_id="OBS-ACT2",
                                         radionuclide="F-18", activity_reference_minutes=109.8),)
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev)
    c = next(c for c in r.comparisons if c.dimension == "RADIONUCLIDE_ACTIVITY")
    # Engine exposes no simulated administered-activity metric.
    assert c.status == "MISSING_SIMULATED_EVIDENCE"
    assert "retained=" in c.note
    assert r.existing_decay_authority_reused is True


# ===========================================================================
# CONTROL L (Sec 42) -- QUALIFIED VALIDATION.
# ===========================================================================
def test_control_l_qualified_validation(executed_baseline):
    """All required dimensions pass; the baseline carries a NOT_CALIBRATED
    qualified uncertainty -> VALIDATED_WITH_QUALIFICATIONS / ELIGIBLE_WITH_
    QUALIFICATIONS. LOCKDOWN is NOT created."""
    assert executed_baseline.qualified_uncertainties  # precondition
    r = validate_asis_baseline(
        baseline_result=executed_baseline,
        evidence=_all_required_pass_evidence(executed_baseline),
        tolerances=_all_required_tolerances(),
    )
    assert r.validation_status == "VALIDATED_WITH_QUALIFICATIONS"
    assert r.lockdown_eligibility_status == "ELIGIBLE_WITH_QUALIFICATIONS"
    assert r.lockdown_created is False
    assert r.what_if_created is False
    assert r.remaining_qualifications  # qualifications remain visible


# ===========================================================================
# CONTROL M (Sec 43) -- FULLY VALIDATED CONTROL.
# ===========================================================================
def test_control_m_fully_validated(executed_baseline):
    """The smallest deterministic control that reaches VALIDATED + ELIGIBLE. A
    controlled clean baseline (no qualified uncertainty) with every required
    dimension passing. LOCKDOWN/What-If are NOT created."""
    clean = _clean_executed_baseline(executed_baseline)
    assert clean.qualified_uncertainties == ()
    r = validate_asis_baseline(
        baseline_result=clean,
        evidence=_all_required_pass_evidence(clean),
        tolerances=_all_required_tolerances(),
    )
    assert r.validation_status == "VALIDATED"
    assert r.lockdown_eligibility_status == "ELIGIBLE"
    assert r.is_lockdown_eligible is True
    assert r.lockdown_created is False
    assert r.what_if_created is False


def test_control_m_coverage_full(executed_baseline):
    clean = _clean_executed_baseline(executed_baseline)
    r = validate_asis_baseline(
        baseline_result=clean, evidence=_all_required_pass_evidence(clean),
        tolerances=_all_required_tolerances(),
    )
    assert r.coverage.coverage_ratio == 1.0
    assert r.coverage.all_required_dimensions_passed is True


# ===========================================================================
# BLOCKED BASELINE.
# ===========================================================================
def test_blocked_baseline_not_validated(blocked_baseline):
    """A baseline that never executed cannot be validated."""
    r = validate_asis_baseline(baseline_result=blocked_baseline)
    assert r.validation_status == "NOT_VALIDATED"
    assert r.is_lockdown_eligible is False


def test_blocked_baseline_no_simulated_evidence(blocked_baseline):
    r = validate_asis_baseline(baseline_result=blocked_baseline)
    assert all(c.simulated_value is None for c in r.comparisons)
    assert any(g.kind == "MISSING_SIMULATED_EVIDENCE" for g in r.validation_gaps)


# ===========================================================================
# PATIENT THROUGHPUT / TIMING / TRAJECTORY / TRANSPORT (Sec 12-15).
# ===========================================================================
def test_patient_throughput_compared(executed_baseline):
    r = validate_asis_baseline(
        baseline_result=executed_baseline, evidence=(_throughput_ev(_sim_throughput(executed_baseline)),),
        tolerances=_all_required_tolerances())
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_THROUGHPUT")
    assert float(c.simulated_value) == float(_sim_throughput(executed_baseline))


def test_patient_timing_compared_when_identity_matches(executed_baseline):
    trace = executed_baseline.outputs.patient_trajectories[0]
    identity = trace.canonical_patient_id or trace.patient_id
    ev = (AsIsBaselineValidationEvidence(dimension="PATIENT_TIMING",
            observed_value=trace.injection_start_minutes, unit="min",
            source="MEASURED", source_record_id="OBS-PT", object_identity=identity),)
    tol = (AsIsValidationTolerance(dimension="PATIENT_TIMING", provenance="PROJECT_SUPPLIED", absolute_tolerance=0.5),)
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev, tolerances=tol)
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_TIMING")
    assert c.status == "WITHIN_TOLERANCE"
    assert c.simulated_value == pytest.approx(trace.injection_start_minutes)


def test_patient_trajectory_validation_supported(executed_baseline):
    """Sec 14: trajectory validation compares destination identity (exact)."""
    trace = executed_baseline.outputs.patient_trajectories[0]
    identity = trace.canonical_patient_id or trace.patient_id
    ev = (AsIsBaselineValidationEvidence(dimension="PATIENT_TRAJECTORY",
            observed_value=trace.destination_room_id, unit="room",
            source="OBSERVED_OPERATIONAL_RECORD", source_record_id="OBS-TRAJ", object_identity=identity),)
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev)
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_TRAJECTORY")
    assert c.status == "MATCH"


def test_transport_mode_preserved(executed_baseline):
    """Sec 15: transport mode identity survives (no manual/MRT equating)."""
    trace = executed_baseline.outputs.patient_trajectories[0]
    identity = trace.canonical_patient_id or trace.patient_id
    ev = (AsIsBaselineValidationEvidence(dimension="ROUTE_USAGE",
            observed_value=str(trace.transport_mode), unit="mode",
            source="OBSERVED_OPERATIONAL_RECORD", source_record_id="OBS-RT",
            object_identity=identity, transport_mode=str(trace.transport_mode)),)
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev)
    c = next(c for c in r.comparisons if c.dimension == "ROUTE_USAGE")
    assert c.status == "MATCH"


def test_transport_mode_mismatch_is_mismatch(executed_baseline):
    trace = executed_baseline.outputs.patient_trajectories[0]
    identity = trace.canonical_patient_id or trace.patient_id
    ev = (AsIsBaselineValidationEvidence(dimension="ROUTE_USAGE", observed_value="MRT", unit="mode",
            source="OBSERVED_OPERATIONAL_RECORD", source_record_id="OBS-RT2",
            object_identity=identity, transport_mode="MRT"),)
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev)
    c = next(c for c in r.comparisons if c.dimension == "ROUTE_USAGE")
    # Simulated mode is CONVENTIONAL (not MRT) -> mismatch preserved.
    assert c.status == "MISMATCH"
    assert any(g.kind == "IDENTITY_MISMATCH" for g in r.validation_gaps)


# ===========================================================================
# SCANNER / OPERATIONAL FEASIBILITY (Sec 16).
# ===========================================================================
def test_scanner_utilization_compared(executed_baseline):
    r = validate_asis_baseline(baseline_result=executed_baseline,
        evidence=(_scanner_ev(_sim_scanner_peak(executed_baseline)),),
        tolerances=_all_required_tolerances())
    c = next(c for c in r.comparisons if c.dimension == "SCANNER_UTILIZATION")
    assert c.status == "WITHIN_TOLERANCE"


def test_operational_feasibility_match(executed_baseline):
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=(_feasibility_ev("FEASIBLE"),))
    c = next(c for c in r.comparisons if c.dimension == "OPERATIONAL_FEASIBILITY")
    assert c.status == "MATCH"


def test_operational_feasibility_mismatch(executed_baseline):
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=(_feasibility_ev("INFEASIBLE"),))
    c = next(c for c in r.comparisons if c.dimension == "OPERATIONAL_FEASIBILITY")
    assert c.status == "MISMATCH"


# ===========================================================================
# TOLERANCE AUTHORITY (Sec 10).
# ===========================================================================
def test_tolerance_provenance_required():
    t = AsIsValidationTolerance(dimension="PATIENT_THROUGHPUT", provenance="FACILITY_SUPPLIED", absolute_tolerance=2.0)
    assert t.is_modeled is True
    assert t.provenance == "FACILITY_SUPPLIED"


def test_unmodeled_tolerance_is_not_modeled():
    t = AsIsValidationTolerance(dimension="PATIENT_THROUGHPUT", provenance="PROJECT_SUPPLIED")
    assert t.is_modeled is False


def test_relative_tolerance_applied(executed_baseline):
    sim = _sim_throughput(executed_baseline)
    obs = sim - 1
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=(_throughput_ev(obs),),
        tolerances=(AsIsValidationTolerance(dimension="PATIENT_THROUGHPUT",
            provenance="PROJECT_SUPPLIED", relative_tolerance=0.5),))
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_THROUGHPUT")
    assert c.status == "WITHIN_TOLERANCE"  # 1 <= 0.5*18


# ===========================================================================
# READ-ONLY / NO-TUNING / NO-LOCKDOWN / NO-WHATIF BOUNDARY (Sec 44-49).
# ===========================================================================
def test_baseline_not_mutated(executed_baseline):
    before_throughput = executed_baseline.outputs.retention_qualified_completed
    before_status = executed_baseline.execution_status
    r = validate_asis_baseline(baseline_result=executed_baseline,
        evidence=(_throughput_ev(0),), tolerances=_all_required_tolerances())
    assert executed_baseline.outputs.retention_qualified_completed == before_throughput
    assert executed_baseline.execution_status == before_status
    assert r.baseline_mutated_by_validation is False


def test_no_model_auto_tuning(executed_baseline):
    r = validate_asis_baseline(baseline_result=executed_baseline)
    assert r.model_parameters_auto_tuned is False


def test_no_lockdown_created(executed_baseline):
    r = validate_asis_baseline(baseline_result=executed_baseline,
        evidence=_all_required_pass_evidence(executed_baseline), tolerances=_all_required_tolerances())
    assert r.lockdown_created is False


def test_no_what_if(executed_baseline):
    r = validate_asis_baseline(baseline_result=executed_baseline)
    assert r.what_if_created is False
    assert r.what_if_execution_started is False
    assert r.what_if_baseline_mutated is False


def test_validation_does_not_import_lockdown_mutators():
    """Sec 48: Phase 1F never calls the LOCKDOWN/What-If mutators."""
    import existing_facility_baseline_validation as mod
    src = open(mod.__file__).read()
    for mutator in ("create_first_lockdown", "branch_what_if", "promote_what_if_to_lockdown",
                    "update_what_if_results", "bind_plan_version"):
        assert mutator not in src


def test_engine_reused_read_only_flag(executed_baseline):
    r = validate_asis_baseline(baseline_result=executed_baseline)
    assert r.existing_simulation_engine_reused_read_only is True


# ===========================================================================
# SCOPE-SPECIFIC VALIDATION (Sec 24).
# ===========================================================================
def test_scope_specific_validation_preserved(executed_baseline):
    r = validate_asis_baseline(baseline_result=executed_baseline, validation_scope="NUCLEAR_MEDICINE_ONCOLOGY")
    assert r.validation_scope == "NUCLEAR_MEDICINE_ONCOLOGY"
    assert r.simulation_scope == "NUCLEAR_MEDICINE_ONCOLOGY"


def test_whole_hospital_scope_not_declared_validated(executed_baseline):
    """Sec 24: a whole-hospital scope is not validated from a narrow nuclear run."""
    r = validate_asis_baseline(baseline_result=executed_baseline, validation_scope="WHOLE_HOSPITAL")
    assert r.validation_status in ("VALIDATION_INSUFFICIENT", "NOT_VALIDATED", "PARTIALLY_VALIDATED")
    assert r.is_lockdown_eligible is False


# ===========================================================================
# VALIDATION GAP AUTHORITY (Sec 30).
# ===========================================================================
def test_gaps_are_first_class_not_hidden_in_notes(executed_baseline):
    r = validate_asis_baseline(baseline_result=executed_baseline)
    assert len(r.validation_gaps) >= 1
    assert all(hasattr(g, "kind") and hasattr(g, "dimension") for g in r.validation_gaps)


def test_custom_manifest_respected(executed_baseline):
    manifest = (AsIsRequiredValidationDimension(dimension="PATIENT_THROUGHPUT", required=True,
                    reason="only throughput required", blocking_for_lockdown=True),)
    r = validate_asis_baseline(baseline_result=executed_baseline,
        evidence=(_throughput_ev(_sim_throughput(executed_baseline)),),
        tolerances=_all_required_tolerances(), required_manifest=manifest)
    assert len(r.required_manifest) == 1
    assert r.coverage.required_count == 1


def test_default_manifest_has_blocking_and_nonblocking():
    m = default_required_manifest("NUCLEAR_MEDICINE_ONCOLOGY")
    assert any(d.blocking_for_lockdown for d in m)
    assert any(not d.required for d in m)


# ===========================================================================
# DIFFERENCE ARITHMETIC.
# ===========================================================================
def test_difference_is_simulated_minus_observed(executed_baseline):
    sim = _sim_throughput(executed_baseline)
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=(_throughput_ev(sim - 3),),
        tolerances=(AsIsValidationTolerance(dimension="PATIENT_THROUGHPUT",
            provenance="PROJECT_SUPPLIED", absolute_tolerance=100.0),))
    c = next(c for c in r.comparisons if c.dimension == "PATIENT_THROUGHPUT")
    assert c.difference == 3.0


def test_conflicting_evidence_reduces_coverage(executed_baseline):
    sim = _sim_throughput(executed_baseline)
    ev = (
        _throughput_ev(sim),
        AsIsBaselineValidationEvidence(dimension="PATIENT_THROUGHPUT", observed_value=sim + 5, unit="patients",
                                       source="IMPORTED", source_record_id="OBS-C2"),
    )
    r = validate_asis_baseline(baseline_result=executed_baseline, evidence=ev, tolerances=_all_required_tolerances())
    assert "PATIENT_THROUGHPUT" not in r.coverage.dimensions_passed

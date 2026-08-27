"""Controlled regression coverage for the final production-plan-to-scheduler
authority unification: once the cycle-relative planner finalizes patient-to-cycle
assignments, the production_clinical_schedule.py scheduler must consume that
assignment directly (subject to physical veto) rather than repartitioning patients
or dense-packing production windows independently.
"""

from __future__ import annotations

from dataclasses import replace

from cycle_relative_production_requirement import (
    CandidateCycleUsageSummary,
    CycleRelativeRequirementResult,
    PatientCycleAssignment,
)
from cyclotron_production_windows import CyclotronProductionCapability
from decision_pipeline import NativeDecisionPipelineScenario, run_native_decision_pipeline
from models import SharedNetworkAssumptions
from patient_radionuclide_demand import FacilityDayPatientDemand, PatientRadionuclideDemand
from production_clinical_schedule import ProductionClinicalScenario, build_production_clinical_schedule
from spatial_benchmark import build_benchmark_geometry

import test_decision_pipeline as tdp
import test_production_requirement_reconciliation as tprr


def _patient(patient_id: str, activity: float) -> PatientRadionuclideDemand:
    return PatientRadionuclideDemand(patient_id=patient_id, radionuclide="F-18", prescribed_activity_mbq=activity)


def _assignment(patient_id: str, cycle_id: str, admin_minutes: float, activity: float) -> PatientCycleAssignment:
    return PatientCycleAssignment(
        patient_id=patient_id,
        cycle_id=cycle_id,
        administration_time_minutes=admin_minutes,
        prescribed_activity_mbq=activity,
        elapsed_eob_to_administration_minutes=0.0,
        retained_fraction_at_administration=1.0,
        required_eob_activity_mbq=activity,
        feasible=True,
        infeasibility_reason=None,
    )


def _finalized_two_cycle_result(*, capacity_mbq: float = 1_000_000.0) -> CycleRelativeRequirementResult:
    """Two explicit cycles: P1,P2 -> CYCLE-1 (eob=100); P3,P4 -> CYCLE-2 (eob=400)."""
    assignments = (
        _assignment("P1", "CY:F-18:1", 100.0, 200.0),
        _assignment("P2", "CY:F-18:1", 100.0, 200.0),
        _assignment("P3", "CY:F-18:2", 400.0, 200.0),
        _assignment("P4", "CY:F-18:2", 400.0, 200.0),
    )
    cycle_usages = (
        CandidateCycleUsageSummary(
            cycle_id="CY:F-18:1",
            cyclotron_id="CY",
            radionuclide="F-18",
            start_minutes=0.0,
            eob_minutes=100.0,
            release_minutes=100.0,
            patient_ids=("P1", "P2"),
            required_eob_activity_mbq=400.0,
            available_eob_capacity_mbq=capacity_mbq,
            unused_eob_capacity_mbq=capacity_mbq - 400.0,
            earliest_administration_minutes=100.0,
            latest_administration_minutes=100.0,
            status="SCHEDULED_FEASIBLE" if capacity_mbq >= 400.0 else "SCHEDULED_ACTIVITY_INFEASIBLE",
        ),
        CandidateCycleUsageSummary(
            cycle_id="CY:F-18:2",
            cyclotron_id="CY",
            radionuclide="F-18",
            start_minutes=300.0,
            eob_minutes=400.0,
            release_minutes=400.0,
            patient_ids=("P3", "P4"),
            required_eob_activity_mbq=400.0,
            available_eob_capacity_mbq=capacity_mbq,
            unused_eob_capacity_mbq=capacity_mbq - 400.0,
            earliest_administration_minutes=400.0,
            latest_administration_minutes=400.0,
            status="SCHEDULED_FEASIBLE",
        ),
    )
    return CycleRelativeRequirementResult(
        radionuclide="F-18",
        half_life_minutes=109.8,
        assignments=assignments,
        cycle_usages=cycle_usages,
        required_cycle_count=2,
        unassigned_patient_ids=(),
        total_required_eob_activity_mbq=800.0,
        convergence_status="CONVERGED",
        iterations_used=1,
    )


def _scenario_for_finalized(
    result: CycleRelativeRequirementResult,
    *,
    facility_model=None,
    conventional_payload_capacity_doses: int = 5,
) -> ProductionClinicalScenario:
    patients = FacilityDayPatientDemand(
        patients=tuple(_patient(pid, 200.0) for pid in ("P1", "P2", "P3", "P4"))
    )
    return ProductionClinicalScenario(
        facility_day_demand=patients,
        requested_batch_count_by_radionuclide={"F-18": result.required_cycle_count},
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="CY",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 100.0},
        ),
        transport_minutes=5.0,
        injection_service_minutes=5.0,
        uptake_minutes=5.0,
        scanner_service_minutes=5.0,
        injection_resources=4,
        uptake_resources=4,
        scanners=4,
        distribution_concurrency=2,
        operating_day_minutes=1080.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=500.0,
        pathway="Conventional",
        facility_engineering_model=facility_model,
        conventional_payload_capacity_doses=conventional_payload_capacity_doses,
        finalized_cycle_assignment_by_radionuclide={"F-18": result},
    )


def test_finalized_assignment_preserves_patient_to_cycle_membership() -> None:
    """Section 13 / controlled test 13."""
    result = _finalized_two_cycle_result()
    schedule = build_production_clinical_schedule(_scenario_for_finalized(result))

    membership = {batch.batch_id: set(batch.patient_ids) for batch in schedule.batch_demands}
    assert {"P1", "P2"} in membership.values()
    assert {"P3", "P4"} in membership.values()
    assert len(schedule.unscheduled_batch_demands) == 0


def test_finalized_assignment_timing_is_not_dense_packed() -> None:
    """Section 14 / controlled test 14."""
    result = _finalized_two_cycle_result()
    schedule = build_production_clinical_schedule(_scenario_for_finalized(result))

    windows = schedule.production_schedule.windows
    assert len(windows) == 2
    eobs = sorted(window.end_time_minutes for window in windows)
    # Dense-packing back-to-back from production_start=0 with 100-minute cycles would
    # produce eob=100 and eob=200; the finalized plan's intentional separation (100, 400)
    # must be preserved instead.
    assert eobs == [100.0, 400.0]


def test_physically_impossible_finalized_cycle_is_rejected_not_reshaped() -> None:
    """Section 15 / controlled test 15: capacity-infeasible cycle is vetoed."""
    result = _finalized_two_cycle_result(capacity_mbq=300.0)
    schedule = build_production_clinical_schedule(_scenario_for_finalized(result))

    unscheduled_membership = {frozenset(batch.patient_ids) for batch in schedule.unscheduled_batch_demands}
    assert frozenset({"P1", "P2"}) in unscheduled_membership
    scheduled_membership = {frozenset(batch.patient_ids) for batch in schedule.scheduled_batch_demands}
    assert frozenset({"P3", "P4"}) in scheduled_membership


def test_converged_plan_has_no_planned_only_or_realized_only_cycles() -> None:
    """Section 16 / controlled test 16: planned cycle set == realized cycle set."""
    result = run_native_decision_pipeline(tprr._scenario(target_patients_per_day=60))
    for pathway in (result.conventional, result.mrt):
        rec = pathway.operational_result.production_requirement_reconciliation
        assert rec is not None
        assert sum(1 for row in rec.per_cycle if row.status == "PLANNED_ONLY") == 0
        assert sum(1 for row in rec.per_cycle if row.status == "REALIZED_ONLY") == 0


def test_finalized_cycle_still_generates_multiple_payloads_and_destinations() -> None:
    """Section 17 / controlled test 17: transport granularity is preserved."""
    geometry = build_benchmark_geometry()
    model = replace(geometry.base_model, primary_route_destination_object_ids=("F1-R01", "F2-R01", "F3-R01"))

    single_cycle = CycleRelativeRequirementResult(
        radionuclide="F-18",
        half_life_minutes=109.8,
        assignments=tuple(_assignment(f"PX{i:03d}", "CY:F-18:1", 100.0, 200.0) for i in range(20)),
        cycle_usages=(
            CandidateCycleUsageSummary(
                cycle_id="CY:F-18:1",
                cyclotron_id="CY",
                radionuclide="F-18",
                start_minutes=0.0,
                eob_minutes=100.0,
                release_minutes=100.0,
                patient_ids=tuple(f"PX{i:03d}" for i in range(20)),
                required_eob_activity_mbq=4000.0,
                available_eob_capacity_mbq=1_000_000.0,
                unused_eob_capacity_mbq=996_000.0,
                earliest_administration_minutes=100.0,
                latest_administration_minutes=100.0,
                status="SCHEDULED_FEASIBLE",
            ),
        ),
        required_cycle_count=1,
        unassigned_patient_ids=(),
        total_required_eob_activity_mbq=4000.0,
        convergence_status="CONVERGED",
        iterations_used=1,
    )
    patients = FacilityDayPatientDemand(patients=tuple(_patient(f"PX{i:03d}", 200.0) for i in range(20)))
    scenario = ProductionClinicalScenario(
        facility_day_demand=patients,
        requested_batch_count_by_radionuclide={"F-18": 1},
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="CY",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 100.0},
        ),
        transport_minutes=5.0,
        injection_service_minutes=5.0,
        uptake_minutes=5.0,
        scanner_service_minutes=5.0,
        injection_resources=4,
        uptake_resources=4,
        scanners=4,
        distribution_concurrency=3,
        operating_day_minutes=1080.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=500.0,
        pathway="Conventional",
        facility_engineering_model=model,
        conventional_payload_capacity_doses=5,
        finalized_cycle_assignment_by_radionuclide={"F-18": single_cycle},
    )
    result = build_production_clinical_schedule(scenario)

    assert len(result.batch_release_mappings) == 1
    destination_counts: dict[str, int] = {}
    for payload in result.transport_payloads:
        destination_counts[payload.destination_object_id] = destination_counts.get(payload.destination_object_id, 0) + 1
    assert set(destination_counts.keys()) == {"F1-R01", "F2-R01", "F3-R01"}
    assert len(result.transport_payloads) > 1

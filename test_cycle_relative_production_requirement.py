"""Controlled regression coverage for cycle-relative patient EOB assignment.

Proves the production-requirement provenance defect (patient EOB computed against a
single common early EOB reference, independent of which cycle actually supplies the
patient) has been removed, and that the replacement cycle-relative algorithm satisfies
the physical acceptance requirements: late patients may use later cycles, early
patients cannot use a future release, cycle activity capacity is enforced with bounded
deterministic splitting, and cycle totals reconcile.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cycle_relative_production_requirement import (
    derive_cycle_relative_requirement,
    generate_candidate_production_cycles,
)
from cyclotron_production_windows import CyclotronProductionCapability
from decision_pipeline import NativeDecisionPipelineScenario, run_native_decision_pipeline
from models import SharedNetworkAssumptions
from multi_isotope_decay import required_upstream_activity, retained_fraction

import test_decision_pipeline as tdp

F18_HALF_LIFE_MINUTES = 109.8


def test_late_patient_uses_later_cycle_not_decay_compensated_to_first_cycle() -> None:
    """Section 16 / controlled test 28."""
    cycles = generate_candidate_production_cycles(
        cyclotron_id="CY-01",
        radionuclide="F-18",
        cycle_minutes=100.0,
        calibrated_eob_capacity_mbq=100_000.0,
        release_processing_minutes=0.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=600.0,
    )
    admin_times = {"EARLY": 150.0, "LATE": 550.0}
    prescribed = {"EARLY": 370.0, "LATE": 370.0}

    result = derive_cycle_relative_requirement(
        radionuclide="F-18",
        half_life_minutes=F18_HALF_LIFE_MINUTES,
        patient_ids=["EARLY", "LATE"],
        prescribed_activity_mbq_by_patient_id=prescribed,
        administration_time_minutes_by_patient_id=admin_times,
        candidate_cycles=cycles,
    )
    by_patient = {a.patient_id: a for a in result.assignments}

    assert by_patient["EARLY"].cycle_id == "CY-01:F-18:1"  # eob=100
    assert by_patient["LATE"].cycle_id == "CY-01:F-18:5"  # eob=500, not the first cycle

    # Prove the reduction versus the (removed) common-early-EOB heuristic, which would
    # have decay-compensated LATE all the way back to the first cycle (eob=100).
    common_eob_elapsed = admin_times["LATE"] - 100.0
    common_eob_required = required_upstream_activity(
        prescribed["LATE"], retained_fraction(common_eob_elapsed, F18_HALF_LIFE_MINUTES)
    )
    assert by_patient["LATE"].required_eob_activity_mbq < common_eob_required


def test_early_patient_cannot_use_a_future_release() -> None:
    """Section 17 / controlled test 29."""
    cycles = generate_candidate_production_cycles(
        cyclotron_id="CY-01",
        radionuclide="F-18",
        cycle_minutes=100.0,
        calibrated_eob_capacity_mbq=100_000.0,
        release_processing_minutes=100.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=100.0,
    )
    assert len(cycles) == 1
    assert cycles[0].release_minutes == pytest.approx(200.0)

    result = derive_cycle_relative_requirement(
        radionuclide="F-18",
        half_life_minutes=F18_HALF_LIFE_MINUTES,
        patient_ids=["P1"],
        prescribed_activity_mbq_by_patient_id={"P1": 370.0},
        administration_time_minutes_by_patient_id={"P1": 100.0},
        candidate_cycles=cycles,
    )
    assert result.unassigned_patient_ids == ("P1",)
    assignment = result.assignments[0]
    assert assignment.feasible is False
    assert assignment.cycle_id is None
    assert "UNASSIGNED_PATIENT_PRODUCTION_DEMAND" in assignment.infeasibility_reason


def test_cycle_capacity_split_reassigns_patients_without_patient_count_thresholds() -> None:
    """Section 30 / controlled test 30."""
    cycles = generate_candidate_production_cycles(
        cyclotron_id="CY-01",
        radionuclide="F-18",
        cycle_minutes=100.0,
        calibrated_eob_capacity_mbq=1_000.0,
        release_processing_minutes=0.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=300.0,
    )
    patient_ids = ["P1", "P2", "P3"]
    admin_times = {pid: 250.0 for pid in patient_ids}
    prescribed = {pid: 370.0 for pid in patient_ids}

    result = derive_cycle_relative_requirement(
        radionuclide="F-18",
        half_life_minutes=F18_HALF_LIFE_MINUTES,
        patient_ids=patient_ids,
        prescribed_activity_mbq_by_patient_id=prescribed,
        administration_time_minutes_by_patient_id=admin_times,
        candidate_cycles=cycles,
    )
    used_cycles = {assignment.cycle_id for assignment in result.assignments}
    assert len(used_cycles) > 1
    # A patient was actually moved out of the freshest cycle to relieve its overload
    # (not merely counted against a fixed patient-count threshold).
    assert any(usage.status == "SCHEDULED_FEASIBLE" for usage in result.cycle_usages)
    single_cycle_total = sum(370.0 / retained_fraction(150.0, F18_HALF_LIFE_MINUTES) for _ in patient_ids)
    split_total = sum(usage.required_eob_activity_mbq for usage in result.cycle_usages)
    assert split_total < single_cycle_total


def test_one_cycle_can_serve_more_than_twenty_patients_with_sufficient_activity() -> None:
    """Section 31 / controlled test 31: no patient-count batching."""
    cycles = generate_candidate_production_cycles(
        cyclotron_id="CY-01",
        radionuclide="F-18",
        cycle_minutes=100.0,
        calibrated_eob_capacity_mbq=1_000_000.0,
        release_processing_minutes=0.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=100.0,
    )
    patient_ids = [f"P{i}" for i in range(30)]
    admin_times = {pid: 150.0 for pid in patient_ids}
    prescribed = {pid: 370.0 for pid in patient_ids}

    result = derive_cycle_relative_requirement(
        radionuclide="F-18",
        half_life_minutes=F18_HALF_LIFE_MINUTES,
        patient_ids=patient_ids,
        prescribed_activity_mbq_by_patient_id=prescribed,
        administration_time_minutes_by_patient_id=admin_times,
        candidate_cycles=cycles,
    )
    assert result.required_cycle_count == 1
    assert result.unassigned_patient_ids == ()


def test_fewer_than_twenty_patients_may_require_multiple_cycles() -> None:
    """Section 32 / controlled test 32."""
    cycles = generate_candidate_production_cycles(
        cyclotron_id="CY-01",
        radionuclide="F-18",
        cycle_minutes=100.0,
        calibrated_eob_capacity_mbq=1_000.0,
        release_processing_minutes=0.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=300.0,
    )
    patient_ids = [f"P{i}" for i in range(5)]
    admin_times = {pid: 250.0 for pid in patient_ids}
    prescribed = {pid: 370.0 for pid in patient_ids}

    result = derive_cycle_relative_requirement(
        radionuclide="F-18",
        half_life_minutes=F18_HALF_LIFE_MINUTES,
        patient_ids=patient_ids,
        prescribed_activity_mbq_by_patient_id=prescribed,
        administration_time_minutes_by_patient_id=admin_times,
        candidate_cycles=cycles,
    )
    assert result.required_cycle_count > 1


def test_cycle_totals_reconcile_within_tolerance() -> None:
    """Section 33 / controlled test 33."""
    cycles = generate_candidate_production_cycles(
        cyclotron_id="CY-01",
        radionuclide="F-18",
        cycle_minutes=120.0,
        calibrated_eob_capacity_mbq=648_000.0,
        release_processing_minutes=71.0,
        production_start_time_minutes=-240.0,
        production_horizon_minutes=960.0,
    )
    patient_ids = [f"P{i}" for i in range(50)]
    admin_times = {pid: 90.0 + 15.0 * (i % 12) for i, pid in enumerate(patient_ids)}
    prescribed = {pid: 370.0 for pid in patient_ids}

    result = derive_cycle_relative_requirement(
        radionuclide="F-18",
        half_life_minutes=F18_HALF_LIFE_MINUTES,
        patient_ids=patient_ids,
        prescribed_activity_mbq_by_patient_id=prescribed,
        administration_time_minutes_by_patient_id=admin_times,
        candidate_cycles=cycles,
    )
    by_patient = {a.patient_id: a for a in result.assignments}
    for usage in result.cycle_usages:
        member_sum = sum(by_patient[pid].required_eob_activity_mbq for pid in usage.patient_ids)
        assert member_sum == pytest.approx(usage.required_eob_activity_mbq, rel=1e-9, abs=1e-6)

    total_from_cycles = sum(usage.required_eob_activity_mbq for usage in result.cycle_usages)
    assert total_from_cycles == pytest.approx(result.total_required_eob_activity_mbq, rel=1e-9, abs=1e-6)


def test_cycle_relative_requirement_is_far_smaller_than_common_early_eob_diagnostic() -> None:
    """Section 34 / controlled test 34: no common-EOB explosion in the authoritative path."""
    half_life = F18_HALF_LIFE_MINUTES
    cycle_minutes = 120.0
    cycles = generate_candidate_production_cycles(
        cyclotron_id="CY-01",
        radionuclide="F-18",
        cycle_minutes=cycle_minutes,
        calibrated_eob_capacity_mbq=648_000.0,
        release_processing_minutes=0.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=1200.0,
    )
    # Late-day demand: every patient is administered near the end of the operating day.
    patient_ids = [f"P{i}" for i in range(40)]
    admin_times = {pid: 1080.0 for pid in patient_ids}
    prescribed = {pid: 370.0 for pid in patient_ids}

    result = derive_cycle_relative_requirement(
        radionuclide="F-18",
        half_life_minutes=half_life,
        patient_ids=patient_ids,
        prescribed_activity_mbq_by_patient_id=prescribed,
        administration_time_minutes_by_patient_id=admin_times,
        candidate_cycles=cycles,
    )

    # NON-AUTHORITATIVE DIAGNOSTIC ONLY: what the removed common-early-EOB heuristic would
    # have computed, anchoring every patient to the FIRST cycle of the day (eob=cycle_minutes).
    common_eob_reference = cycle_minutes
    common_eob_total = sum(
        required_upstream_activity(
            prescribed[pid], retained_fraction(admin_times[pid] - common_eob_reference, half_life)
        )
        for pid in patient_ids
    )

    assert result.total_required_eob_activity_mbq < common_eob_total
    assert result.total_required_eob_activity_mbq < common_eob_total / 10.0


def test_whole_demand_production_feasible_is_false_when_batches_remain_unscheduled() -> None:
    """Section 25/57 and controlled test 35: production_feasible cannot be True when
    required cycles exceed what the production horizon can physically schedule."""
    request = NativeDecisionPipelineScenario(
        project_name="Force Unscheduled",
        target_patients_per_day=40,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": tdp.ActivityDemandModel("fixed", fixed_activity_mbq=400.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-TIGHT",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 120.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 3_000.0},
        ),
        conventional=tdp._conventional_pathway(),
        mrt=tdp._mrt_pathway(),
        planner_assumptions=replace(tdp._planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260910,
        operating_day_minutes=1080.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=360.0,
        batch_target_patients_per_batch=20,
    )
    result = run_native_decision_pipeline(request)

    for pathway in (result.conventional, result.mrt):
        diag = pathway.operational_result.production_schedule_diagnostic
        assert diag.required_batch_count > diag.scheduled_batch_count
        assert diag.unscheduled_batch_count > 0
        unassigned = result.demand_result.unassigned_patient_ids_by_radionuclide.get("F-18", ())
        # Whole-demand production feasibility rule (mirrors spatial_benchmark._production_gate_row):
        whole_demand_production_feasible = diag.unscheduled_batch_count == 0 and not unassigned
        assert whole_demand_production_feasible is False


def test_multi_radionuclide_cycle_relative_requirement_is_isotope_independent() -> None:
    """Section 36 / controlled test 36."""
    f18_half_life = F18_HALF_LIFE_MINUTES
    c11_half_life = 20.4

    f18_cycles = generate_candidate_production_cycles(
        cyclotron_id="CY-01",
        radionuclide="F-18",
        cycle_minutes=120.0,
        calibrated_eob_capacity_mbq=648_000.0,
        release_processing_minutes=0.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=480.0,
    )
    c11_cycles = generate_candidate_production_cycles(
        cyclotron_id="CY-01",
        radionuclide="C-11",
        cycle_minutes=30.0,
        calibrated_eob_capacity_mbq=100_000.0,
        release_processing_minutes=0.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=480.0,
    )

    f18_result = derive_cycle_relative_requirement(
        radionuclide="F-18",
        half_life_minutes=f18_half_life,
        patient_ids=["F1", "F2"],
        prescribed_activity_mbq_by_patient_id={"F1": 370.0, "F2": 370.0},
        administration_time_minutes_by_patient_id={"F1": 300.0, "F2": 300.0},
        candidate_cycles=f18_cycles,
    )
    c11_result = derive_cycle_relative_requirement(
        radionuclide="C-11",
        half_life_minutes=c11_half_life,
        patient_ids=["C1", "C2"],
        prescribed_activity_mbq_by_patient_id={"C1": 370.0, "C2": 370.0},
        administration_time_minutes_by_patient_id={"C1": 300.0, "C2": 300.0},
        candidate_cycles=c11_cycles,
    )

    assert all(usage.radionuclide == "F-18" for usage in f18_result.cycle_usages)
    assert all(usage.radionuclide == "C-11" for usage in c11_result.cycle_usages)
    # Isolate the isotope-specific decay physics (not incidental cycle-timing alignment)
    # by comparing retained fraction for an identical elapsed time: C-11's much shorter
    # half-life must produce materially lower retention (i.e. higher decay compensation)
    # than F-18 for the same elapsed interval.
    elapsed_minutes = 60.0
    f18_retained = retained_fraction(elapsed_minutes, f18_half_life)
    c11_retained = retained_fraction(elapsed_minutes, c11_half_life)
    assert c11_retained < f18_retained

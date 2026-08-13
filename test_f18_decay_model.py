from __future__ import annotations

import math

from f18_decay_model import (
    F18ActivityInputs,
    evaluate_f18_operating_day,
    load_f18_half_life_minutes,
    retention_at_delay_minutes,
)
from operating_day_scheduler import BatchRelease, OperatingDayInputs, schedule_operating_day


def _schedule(
    *,
    batches: list[BatchRelease],
    transport: float = 10.0,
    injection: float = 10.0,
    uptake: float = 20.0,
    scan: float = 30.0,
    injection_resources: int = 2,
    uptake_resources: int = 2,
    scanners: int = 2,
    distribution_concurrency: int = 2,
) -> OperatingDayInputs:
    return OperatingDayInputs(
        operating_day_minutes=1080.0,
        batch_releases=batches,
        transport_minutes=transport,
        injection_service_minutes=injection,
        uptake_minutes=uptake,
        scanner_service_minutes=scan,
        injection_resources=injection_resources,
        uptake_resources=uptake_resources,
        scanners=scanners,
        distribution_concurrency=distribution_concurrency,
    )


def _activity_inputs(schedule_result, release_activity_by_batch_id, prescribed_activity=200.0):
    batch_release_times = {
        patient.batch_id: patient.batch_release_time for patient in schedule_result.patient_schedules
    }
    return F18ActivityInputs(
        operating_day_schedule=schedule_result,
        batch_release_times_minutes_by_batch_id=batch_release_times,
        activity_available_at_release_mbq_by_batch_id=release_activity_by_batch_id,
        prescribed_activity_mbq_per_patient=prescribed_activity,
    )


def test_zero_post_release_delay_gives_retention_one():
    assert math.isclose(retention_at_delay_minutes(0.0, load_f18_half_life_minutes()), 1.0, rel_tol=0.0, abs_tol=1e-9)


def test_one_f18_half_life_delay_gives_retention_half():
    half_life = load_f18_half_life_minutes()
    assert math.isclose(retention_at_delay_minutes(half_life, half_life), 0.5, rel_tol=0.0, abs_tol=1e-9)


def test_later_injection_requires_more_release_activity_for_same_prescribed_dose():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2)],
            transport=20.0,
            injection=20.0,
            uptake=20.0,
            scan=5.0,
            injection_resources=1,
            uptake_resources=1,
            scanners=2,
            distribution_concurrency=1,
        )
    )
    result = evaluate_f18_operating_day(
        _activity_inputs(schedule_result, {1: 10_000.0}, prescribed_activity=200.0)
    )
    patient_results = sorted(result.patient_activity_results, key=lambda p: p.injection_time_minutes)
    assert len(patient_results) == 2
    assert patient_results[1].injection_time_minutes > patient_results[0].injection_time_minutes
    assert patient_results[1].required_release_activity_mbq > patient_results[0].required_release_activity_mbq


def test_batch_activity_is_conserved_and_cannot_be_allocated_twice():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2)],
            transport=5.0,
            injection=5.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=1,
            uptake_resources=1,
            scanners=1,
            distribution_concurrency=1,
        )
    )
    result = evaluate_f18_operating_day(
        _activity_inputs(schedule_result, {1: 250.0}, prescribed_activity=200.0)
    )
    batch = result.batch_activity_results[0]
    assert math.isclose(batch.initial_release_activity_mbq, batch.allocated_release_activity_mbq + batch.remaining_release_activity_mbq, rel_tol=0.0, abs_tol=1e-9)
    assert batch.patients_activity_supported == 1
    assert batch.patients_activity_supported_and_completed == 1


def test_insufficient_batch_activity_causes_activity_unsupported_patient():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2)],
            transport=30.0,
            injection=30.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=1,
            uptake_resources=1,
            scanners=2,
            distribution_concurrency=1,
        )
    )
    result = evaluate_f18_operating_day(
        _activity_inputs(schedule_result, {1: 210.0}, prescribed_activity=200.0)
    )
    assert any(not patient.activity_supported for patient in result.patient_activity_results)


def test_activity_supported_completed_patients_never_exceed_scheduler_completed_patients():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=1070.0, patients_in_batch=1)],
            transport=10.0,
            injection=10.0,
            uptake=10.0,
            scan=10.0,
            injection_resources=1,
            uptake_resources=1,
            scanners=1,
            distribution_concurrency=1,
        )
    )
    result = evaluate_f18_operating_day(
        _activity_inputs(schedule_result, {1: 10_000.0}, prescribed_activity=200.0)
    )
    assert result.activity_supported_completed_patients <= result.scheduler_completed_patients
    assert result.activity_supported_completed_patients == 0


def test_scan_completion_after_1080_cannot_become_completed_merely_because_activity_exists():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=1070.0, patients_in_batch=1)],
            transport=10.0,
            injection=10.0,
            uptake=10.0,
            scan=10.0,
            injection_resources=1,
            uptake_resources=1,
            scanners=1,
            distribution_concurrency=1,
        )
    )
    result = evaluate_f18_operating_day(
        _activity_inputs(schedule_result, {1: 10_000.0}, prescribed_activity=200.0)
    )
    assert result.patient_activity_results[0].scheduler_completed_within_operating_day is False
    assert result.patient_activity_results[0].activity_supported_completed_within_operating_day is False


def test_multiple_batches_maintain_separate_activity_inventories():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[
                BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2),
                BatchRelease(batch_id=2, release_time_minutes=0.0, patients_in_batch=2),
            ],
            transport=5.0,
            injection=5.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=2,
            uptake_resources=2,
            scanners=2,
            distribution_concurrency=2,
        )
    )
    result = evaluate_f18_operating_day(
        _activity_inputs(schedule_result, {1: 220.0, 2: 220.0}, prescribed_activity=200.0)
    )
    batch1 = next(batch for batch in result.batch_activity_results if batch.batch_id == 1)
    batch2 = next(batch for batch in result.batch_activity_results if batch.batch_id == 2)
    assert batch1.initial_release_activity_mbq == batch2.initial_release_activity_mbq
    assert batch1.batch_id != batch2.batch_id


def test_later_fresh_batch_can_support_patients_exhausted_earlier_batch_cannot():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[
                BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2),
                BatchRelease(batch_id=2, release_time_minutes=300.0, patients_in_batch=2),
            ],
            transport=20.0,
            injection=20.0,
            uptake=20.0,
            scan=5.0,
            injection_resources=1,
            uptake_resources=1,
            scanners=2,
            distribution_concurrency=1,
        )
    )
    result = evaluate_f18_operating_day(
        _activity_inputs(schedule_result, {1: 220.0, 2: 600.0}, prescribed_activity=200.0)
    )
    batch1 = next(batch for batch in result.batch_activity_results if batch.batch_id == 1)
    batch2 = next(batch for batch in result.batch_activity_results if batch.batch_id == 2)
    assert batch1.patients_activity_supported < batch2.patients_activity_supported


def test_identical_conventional_and_mrt_schedules_produce_identical_f18_results():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=4)],
            transport=10.0,
            injection=10.0,
            uptake=10.0,
            scan=10.0,
            injection_resources=2,
            uptake_resources=2,
            scanners=2,
            distribution_concurrency=2,
        )
    )
    inputs = _activity_inputs(schedule_result, {1: 1_000.0}, prescribed_activity=200.0)
    conventional = evaluate_f18_operating_day(inputs)
    mrt = evaluate_f18_operating_day(inputs)
    assert conventional == mrt


def test_earlier_legitimate_injection_timing_reduces_required_release_activity():
    early_schedule = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2)],
            transport=5.0,
            injection=5.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=2,
            uptake_resources=2,
            scanners=2,
            distribution_concurrency=2,
        )
    )
    late_schedule = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2)],
            transport=5.0,
            injection=5.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=1,
            uptake_resources=2,
            scanners=2,
            distribution_concurrency=1,
        )
    )
    early = evaluate_f18_operating_day(_activity_inputs(early_schedule, {1: 1_000.0}, prescribed_activity=200.0))
    late = evaluate_f18_operating_day(_activity_inputs(late_schedule, {1: 1_000.0}, prescribed_activity=200.0))
    early_patient = min(early.patient_activity_results, key=lambda p: p.injection_time_minutes)
    late_patient = min(late.patient_activity_results, key=lambda p: p.injection_time_minutes)
    assert early_patient.injection_time_minutes <= late_patient.injection_time_minutes
    assert early_patient.required_release_activity_mbq <= late_patient.required_release_activity_mbq


def test_increasing_distribution_concurrency_improves_supported_throughput_only_through_changed_timestamps():
    low_schedule = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=8)],
            transport=60.0,
            injection=5.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=4,
            uptake_resources=4,
            scanners=4,
            distribution_concurrency=1,
        )
    )
    high_schedule = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=8)],
            transport=60.0,
            injection=5.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=4,
            uptake_resources=4,
            scanners=4,
            distribution_concurrency=4,
        )
    )
    low = evaluate_f18_operating_day(_activity_inputs(low_schedule, {1: 1_000.0}, prescribed_activity=200.0))
    high = evaluate_f18_operating_day(_activity_inputs(high_schedule, {1: 1_000.0}, prescribed_activity=200.0))
    assert high.activity_supported_completed_patients >= low.activity_supported_completed_patients
    assert high.patient_activity_results[0].injection_time_minutes <= low.patient_activity_results[0].injection_time_minutes


def test_more_f18_activity_does_not_overcome_scanner_bottleneck():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=40)],
            transport=1.0,
            injection=1.0,
            uptake=1.0,
            scan=60.0,
            injection_resources=5,
            uptake_resources=5,
            scanners=1,
            distribution_concurrency=4,
        )
    )
    low = evaluate_f18_operating_day(_activity_inputs(schedule_result, {1: 10_000.0}, prescribed_activity=200.0))
    high = evaluate_f18_operating_day(_activity_inputs(schedule_result, {1: 100_000.0}, prescribed_activity=200.0))
    assert low.activity_supported_completed_patients == high.activity_supported_completed_patients == schedule_result.completed_patients


def test_additional_batches_do_not_reset_scanners_or_rooms():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[
                BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=4),
                BatchRelease(batch_id=2, release_time_minutes=540.0, patients_in_batch=4),
            ],
            transport=30.0,
            injection=10.0,
            uptake=10.0,
            scan=20.0,
            injection_resources=2,
            uptake_resources=2,
            scanners=2,
            distribution_concurrency=1,
        )
    )
    result = evaluate_f18_operating_day(_activity_inputs(schedule_result, {1: 500.0, 2: 500.0}, prescribed_activity=200.0))
    batch1 = next(batch for batch in result.batch_activity_results if batch.batch_id == 1)
    batch2 = next(batch for batch in result.batch_activity_results if batch.batch_id == 2)
    assert schedule_result.total_patients_considered == 8
    assert batch2.patients_scheduled == 4
    assert result.activity_supported_completed_patients <= schedule_result.completed_patients
    assert batch1.patients_activity_supported >= 0


def test_per_patient_required_release_activity_reconciles_with_batch_allocated_activity():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=3)],
            transport=10.0,
            injection=10.0,
            uptake=10.0,
            scan=5.0,
            injection_resources=1,
            uptake_resources=1,
            scanners=2,
            distribution_concurrency=1,
        )
    )
    result = evaluate_f18_operating_day(_activity_inputs(schedule_result, {1: 1_000.0}, prescribed_activity=200.0))
    batch = result.batch_activity_results[0]
    supported_required_sum = sum(
        patient.required_release_activity_mbq
        for patient in result.patient_activity_results
        if patient.activity_supported
    )
    assert math.isclose(batch.allocated_release_activity_mbq, supported_required_sum, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(batch.initial_release_activity_mbq, batch.allocated_release_activity_mbq + batch.remaining_release_activity_mbq, rel_tol=0.0, abs_tol=1e-9)


def test_total_activity_supported_patient_count_reconciles_with_patient_records():
    schedule_result = schedule_operating_day(
        _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=5)],
            transport=5.0,
            injection=5.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=1,
            uptake_resources=1,
            scanners=1,
            distribution_concurrency=1,
        )
    )
    result = evaluate_f18_operating_day(_activity_inputs(schedule_result, {1: 1_000.0}, prescribed_activity=200.0))
    assert result.activity_supported_patients == sum(1 for patient in result.patient_activity_results if patient.activity_supported)
    assert result.activity_supported_completed_patients == sum(1 for patient in result.patient_activity_results if patient.activity_supported_completed_within_operating_day)


def test_mvp_benchmark_conventional_vs_mrt_results():
    conventional_inputs = _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=6)],
            transport=60.0,
            injection=5.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=3,
            uptake_resources=3,
            scanners=3,
            distribution_concurrency=1,
    )
    mrt_inputs = _schedule(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=6)],
            transport=60.0,
            injection=5.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=3,
            uptake_resources=3,
            scanners=3,
            distribution_concurrency=3,
    )

    conventional_schedule = schedule_operating_day(conventional_inputs)
    mrt_schedule = schedule_operating_day(mrt_inputs)

    conventional = evaluate_f18_operating_day(_activity_inputs(conventional_schedule, {1: 900.0}, prescribed_activity=200.0))
    mrt = evaluate_f18_operating_day(_activity_inputs(mrt_schedule, {1: 900.0}, prescribed_activity=200.0))

    assert conventional_inputs.scanners == mrt_inputs.scanners == 3
    assert conventional_inputs.injection_resources == mrt_inputs.injection_resources == 3
    assert conventional_inputs.uptake_resources == mrt_inputs.uptake_resources == 3
    assert mrt.patient_activity_results[2].injection_time_minutes < conventional.patient_activity_results[2].injection_time_minutes
    assert mrt.patient_activity_results[2].required_release_activity_mbq < conventional.patient_activity_results[2].required_release_activity_mbq
    assert mrt.activity_supported_completed_patients > conventional.activity_supported_completed_patients

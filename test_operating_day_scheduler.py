from __future__ import annotations

import math

from operating_day_scheduler import (
    BatchRelease,
    OperatingDayInputs,
    schedule_operating_day,
)


def _inputs(
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


def test_single_patient_follows_correct_chronological_sequence():
    result = schedule_operating_day(_inputs(batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=1)]))
    p = result.patient_schedules[0]

    assert p.distribution_start >= p.batch_release_time
    assert p.distribution_end >= p.distribution_start
    assert p.injection_start >= p.distribution_end
    assert p.injection_end >= p.injection_start
    assert p.uptake_start >= p.injection_end
    assert p.uptake_end >= p.uptake_start
    assert p.scan_start >= p.uptake_end
    assert p.scan_end >= p.scan_start


def test_scan_completion_after_1080_not_counted_completed():
    result = schedule_operating_day(
        _inputs(
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
    assert result.completed_patients == 0
    assert result.uncompleted_patients == 1
    assert result.patient_schedules[0].scan_end > 1080.0
    assert result.patient_schedules[0].completed_within_operating_day is False


def test_two_scanners_process_patients_simultaneously_when_upstream_permits():
    result = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2)],
            transport=5.0,
            injection=5.0,
            uptake=5.0,
            scan=30.0,
            injection_resources=2,
            uptake_resources=2,
            scanners=2,
            distribution_concurrency=2,
        )
    )
    p1 = result.patient_schedules[0]
    p2 = result.patient_schedules[1]
    assert math.isclose(p1.scan_start, p2.scan_start, rel_tol=0.0, abs_tol=1e-9)


def test_one_scanner_serializes_scan_service():
    result = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2)],
            transport=5.0,
            injection=5.0,
            uptake=5.0,
            scan=30.0,
            injection_resources=2,
            uptake_resources=2,
            scanners=1,
            distribution_concurrency=2,
        )
    )
    p1 = result.patient_schedules[0]
    p2 = result.patient_schedules[1]
    assert p2.scan_start >= p1.scan_end


def test_one_injection_resource_serializes_injections():
    result = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2)],
            transport=5.0,
            injection=20.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=1,
            uptake_resources=2,
            scanners=2,
            distribution_concurrency=2,
        )
    )
    p1 = result.patient_schedules[0]
    p2 = result.patient_schedules[1]
    assert p2.injection_start >= p1.injection_end


def test_one_uptake_resource_serializes_uptake_occupancy():
    result = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2)],
            transport=5.0,
            injection=5.0,
            uptake=25.0,
            scan=5.0,
            injection_resources=2,
            uptake_resources=1,
            scanners=2,
            distribution_concurrency=2,
        )
    )
    p1 = result.patient_schedules[0]
    p2 = result.patient_schedules[1]
    assert p2.uptake_start >= p1.uptake_end


def test_distribution_concurrency_one_serializes_transport():
    result = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2)],
            transport=15.0,
            injection=5.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=2,
            uptake_resources=2,
            scanners=2,
            distribution_concurrency=1,
        )
    )
    p1 = result.patient_schedules[0]
    p2 = result.patient_schedules[1]
    assert p2.distribution_start >= p1.distribution_end


def test_distribution_concurrency_more_than_one_allows_simultaneous_transport():
    result = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2)],
            transport=15.0,
            injection=5.0,
            uptake=5.0,
            scan=5.0,
            injection_resources=2,
            uptake_resources=2,
            scanners=2,
            distribution_concurrency=2,
        )
    )
    p1 = result.patient_schedules[0]
    p2 = result.patient_schedules[1]
    assert math.isclose(p1.distribution_start, p2.distribution_start, rel_tol=0.0, abs_tol=1e-9)


def test_more_distribution_concurrency_no_throughput_gain_when_scanners_bind():
    low = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=40)],
            transport=2.0,
            injection=2.0,
            uptake=2.0,
            scan=60.0,
            injection_resources=5,
            uptake_resources=5,
            scanners=1,
            distribution_concurrency=1,
        )
    )
    high = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=40)],
            transport=2.0,
            injection=2.0,
            uptake=2.0,
            scan=60.0,
            injection_resources=5,
            uptake_resources=5,
            scanners=1,
            distribution_concurrency=8,
        )
    )
    assert low.completed_patients == high.completed_patients


def test_more_scanners_no_throughput_gain_when_uptake_binds():
    low = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=100)],
            transport=1.0,
            injection=1.0,
            uptake=80.0,
            scan=5.0,
            injection_resources=4,
            uptake_resources=1,
            scanners=1,
            distribution_concurrency=4,
        )
    )
    high = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=100)],
            transport=1.0,
            injection=1.0,
            uptake=80.0,
            scan=5.0,
            injection_resources=4,
            uptake_resources=1,
            scanners=4,
            distribution_concurrency=4,
        )
    )
    assert low.completed_patients == high.completed_patients


def test_multiple_batches_share_same_resource_pools():
    result = schedule_operating_day(
        _inputs(
            batches=[
                BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2),
                BatchRelease(batch_id=2, release_time_minutes=0.0, patients_in_batch=2),
            ],
            transport=1.0,
            injection=1.0,
            uptake=1.0,
            scan=100.0,
            injection_resources=2,
            uptake_resources=2,
            scanners=1,
            distribution_concurrency=2,
        )
    )
    batch2_scan_starts = [p.scan_start for p in result.patient_schedules if p.batch_id == 2]
    assert min(batch2_scan_starts) >= result.patient_schedules[0].scan_end


def test_later_batch_does_not_receive_fresh_scanner_or_room_capacity():
    result = schedule_operating_day(
        _inputs(
            batches=[
                BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=30),
                BatchRelease(batch_id=2, release_time_minutes=540.0, patients_in_batch=30),
            ],
            transport=1.0,
            injection=1.0,
            uptake=1.0,
            scan=40.0,
            injection_resources=2,
            uptake_resources=2,
            scanners=1,
            distribution_concurrency=2,
        )
    )
    batch2_completed = sum(1 for p in result.patient_schedules if p.batch_id == 2 and p.completed_within_operating_day)
    assert batch2_completed < 30


def test_batch_release_time_delays_patients_in_that_batch():
    result = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=7, release_time_minutes=200.0, patients_in_batch=1)],
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
    p = result.patient_schedules[0]
    assert p.distribution_start >= 200.0


def test_six_batches_must_still_fit_same_1080_minute_day():
    batches = [BatchRelease(batch_id=i + 1, release_time_minutes=i * 60.0, patients_in_batch=6) for i in range(6)]
    result = schedule_operating_day(
        _inputs(
            batches=batches,
            transport=5.0,
            injection=5.0,
            uptake=10.0,
            scan=15.0,
            injection_resources=3,
            uptake_resources=3,
            scanners=3,
            distribution_concurrency=3,
        )
    )
    assert result.total_patients_considered == 36
    assert result.completed_patients <= 36


def test_utilization_percentages_never_exceed_100():
    result = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=500)],
            transport=20.0,
            injection=20.0,
            uptake=20.0,
            scan=20.0,
            injection_resources=1,
            uptake_resources=1,
            scanners=1,
            distribution_concurrency=1,
        )
    )
    assert result.scanner_utilization_pct <= 100.0 + 1e-9
    assert result.injection_utilization_pct <= 100.0 + 1e-9
    assert result.uptake_utilization_pct <= 100.0 + 1e-9
    assert result.distribution_utilization_pct <= 100.0 + 1e-9


def test_completed_records_count_matches_completed_patients_field():
    result = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=25)],
            transport=5.0,
            injection=5.0,
            uptake=5.0,
            scan=60.0,
            injection_resources=2,
            uptake_resources=2,
            scanners=1,
            distribution_concurrency=2,
        )
    )
    completed_records = sum(1 for p in result.patient_schedules if p.completed_within_operating_day)
    assert completed_records == result.completed_patients


def test_architecture_neutral_identical_inputs_produce_identical_schedule():
    common_inputs = _inputs(
        batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=6)],
        transport=5.0,
        injection=5.0,
        uptake=5.0,
        scan=10.0,
        injection_resources=2,
        uptake_resources=2,
        scanners=2,
        distribution_concurrency=2,
    )
    conventional = schedule_operating_day(common_inputs)
    mrt = schedule_operating_day(common_inputs)
    assert conventional == mrt


def test_higher_distribution_concurrency_improves_throughput_only_when_distribution_bottleneck():
    low = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=80)],
            transport=60.0,
            injection=2.0,
            uptake=2.0,
            scan=2.0,
            injection_resources=6,
            uptake_resources=6,
            scanners=6,
            distribution_concurrency=1,
        )
    )
    high = schedule_operating_day(
        _inputs(
            batches=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=80)],
            transport=60.0,
            injection=2.0,
            uptake=2.0,
            scan=2.0,
            injection_resources=6,
            uptake_resources=6,
            scanners=6,
            distribution_concurrency=4,
        )
    )
    assert high.completed_patients > low.completed_patients

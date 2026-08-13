from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatchRelease:
    batch_id: int
    release_time_minutes: float
    patients_in_batch: int


@dataclass(frozen=True)
class OperatingDayInputs:
    operating_day_minutes: float
    batch_releases: list[BatchRelease]
    transport_minutes: float
    injection_service_minutes: float
    uptake_minutes: float
    scanner_service_minutes: float
    injection_resources: int
    uptake_resources: int
    scanners: int
    distribution_concurrency: int


@dataclass(frozen=True)
class PatientSchedule:
    patient_id: int
    batch_id: int
    batch_release_time: float
    distribution_start: float
    distribution_end: float
    injection_start: float
    injection_end: float
    uptake_start: float
    uptake_end: float
    scan_start: float
    scan_end: float
    completed_within_operating_day: bool


@dataclass(frozen=True)
class OperatingDayScheduleResult:
    completed_patients: int
    uncompleted_patients: int
    total_patients_considered: int
    patient_schedules: list[PatientSchedule]
    scanner_utilization_pct: float
    injection_utilization_pct: float
    uptake_utilization_pct: float
    distribution_utilization_pct: float
    last_scan_completion_minute: float
    operating_day_feasible: bool


def _validate_inputs(inputs: OperatingDayInputs) -> None:
    if inputs.operating_day_minutes <= 0.0:
        raise ValueError("operating_day_minutes must be positive")
    if inputs.transport_minutes < 0.0:
        raise ValueError("transport_minutes must be non-negative")
    if inputs.injection_service_minutes < 0.0:
        raise ValueError("injection_service_minutes must be non-negative")
    if inputs.uptake_minutes < 0.0:
        raise ValueError("uptake_minutes must be non-negative")
    if inputs.scanner_service_minutes < 0.0:
        raise ValueError("scanner_service_minutes must be non-negative")
    if inputs.injection_resources <= 0:
        raise ValueError("injection_resources must be at least 1")
    if inputs.uptake_resources <= 0:
        raise ValueError("uptake_resources must be at least 1")
    if inputs.scanners <= 0:
        raise ValueError("scanners must be at least 1")
    if inputs.distribution_concurrency <= 0:
        raise ValueError("distribution_concurrency must be at least 1")
    for batch in inputs.batch_releases:
        if batch.release_time_minutes < 0.0:
            raise ValueError("batch release_time_minutes must be non-negative")
        if batch.patients_in_batch < 0:
            raise ValueError("batch patients_in_batch must be non-negative")


def _allocate_earliest(availability: list[float], earliest_start: float, duration: float) -> tuple[float, float]:
    chosen_index = 0
    chosen_start = max(earliest_start, availability[0])
    for idx in range(1, len(availability)):
        candidate_start = max(earliest_start, availability[idx])
        if candidate_start < chosen_start:
            chosen_start = candidate_start
            chosen_index = idx
    end_time = chosen_start + duration
    availability[chosen_index] = end_time
    return chosen_start, end_time


def _occupied_minutes_within_day(start: float, end: float, operating_day_minutes: float) -> float:
    overlap_start = max(0.0, min(start, operating_day_minutes))
    overlap_end = max(0.0, min(end, operating_day_minutes))
    return max(0.0, overlap_end - overlap_start)


def schedule_operating_day(inputs: OperatingDayInputs) -> OperatingDayScheduleResult:
    _validate_inputs(inputs)

    distribution_available_at = [0.0] * inputs.distribution_concurrency
    injection_available_at = [0.0] * inputs.injection_resources
    uptake_available_at = [0.0] * inputs.uptake_resources
    scanner_available_at = [0.0] * inputs.scanners

    patient_schedules: list[PatientSchedule] = []
    patient_id = 0

    scanner_occupied_minutes = 0.0
    injection_occupied_minutes = 0.0
    uptake_occupied_minutes = 0.0
    distribution_occupied_minutes = 0.0

    sorted_batches = sorted(inputs.batch_releases, key=lambda b: (b.release_time_minutes, b.batch_id))

    for batch in sorted_batches:
        for _ in range(batch.patients_in_batch):
            patient_id += 1

            distribution_start, distribution_end = _allocate_earliest(
                distribution_available_at,
                batch.release_time_minutes,
                inputs.transport_minutes,
            )
            injection_start, injection_end = _allocate_earliest(
                injection_available_at,
                distribution_end,
                inputs.injection_service_minutes,
            )
            uptake_start, uptake_end = _allocate_earliest(
                uptake_available_at,
                injection_end,
                inputs.uptake_minutes,
            )
            scan_start, scan_end = _allocate_earliest(
                scanner_available_at,
                uptake_end,
                inputs.scanner_service_minutes,
            )

            completed = scan_end <= inputs.operating_day_minutes

            distribution_occupied_minutes += _occupied_minutes_within_day(
                distribution_start,
                distribution_end,
                inputs.operating_day_minutes,
            )
            injection_occupied_minutes += _occupied_minutes_within_day(
                injection_start,
                injection_end,
                inputs.operating_day_minutes,
            )
            uptake_occupied_minutes += _occupied_minutes_within_day(
                uptake_start,
                uptake_end,
                inputs.operating_day_minutes,
            )
            scanner_occupied_minutes += _occupied_minutes_within_day(
                scan_start,
                scan_end,
                inputs.operating_day_minutes,
            )

            patient_schedules.append(
                PatientSchedule(
                    patient_id=patient_id,
                    batch_id=batch.batch_id,
                    batch_release_time=batch.release_time_minutes,
                    distribution_start=distribution_start,
                    distribution_end=distribution_end,
                    injection_start=injection_start,
                    injection_end=injection_end,
                    uptake_start=uptake_start,
                    uptake_end=uptake_end,
                    scan_start=scan_start,
                    scan_end=scan_end,
                    completed_within_operating_day=completed,
                )
            )

    total_patients = len(patient_schedules)
    completed_patients = sum(1 for p in patient_schedules if p.completed_within_operating_day)
    uncompleted_patients = total_patients - completed_patients

    scanner_capacity_minutes = float(inputs.scanners) * inputs.operating_day_minutes
    injection_capacity_minutes = float(inputs.injection_resources) * inputs.operating_day_minutes
    uptake_capacity_minutes = float(inputs.uptake_resources) * inputs.operating_day_minutes
    distribution_capacity_minutes = float(inputs.distribution_concurrency) * inputs.operating_day_minutes

    scanner_utilization_pct = 100.0 * scanner_occupied_minutes / scanner_capacity_minutes
    injection_utilization_pct = 100.0 * injection_occupied_minutes / injection_capacity_minutes
    uptake_utilization_pct = 100.0 * uptake_occupied_minutes / uptake_capacity_minutes
    distribution_utilization_pct = 100.0 * distribution_occupied_minutes / distribution_capacity_minutes

    if patient_schedules:
        last_scan_completion_minute = max(p.scan_end for p in patient_schedules)
    else:
        last_scan_completion_minute = 0.0

    return OperatingDayScheduleResult(
        completed_patients=completed_patients,
        uncompleted_patients=uncompleted_patients,
        total_patients_considered=total_patients,
        patient_schedules=patient_schedules,
        scanner_utilization_pct=min(100.0, scanner_utilization_pct),
        injection_utilization_pct=min(100.0, injection_utilization_pct),
        uptake_utilization_pct=min(100.0, uptake_utilization_pct),
        distribution_utilization_pct=min(100.0, distribution_utilization_pct),
        last_scan_completion_minute=last_scan_completion_minute,
        operating_day_feasible=(uncompleted_patients == 0),
    )

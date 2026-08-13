from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from collections import defaultdict
from typing import Any

from operating_day_scheduler import OperatingDayScheduleResult, PatientSchedule


@dataclass(frozen=True)
class F18ActivityInputs:
    operating_day_schedule: OperatingDayScheduleResult
    batch_release_times_minutes_by_batch_id: dict[int, float] | None
    activity_available_at_release_mbq_by_batch_id: dict[int, float]
    prescribed_activity_mbq_per_patient: float
    radionuclide: str = "F-18"


@dataclass(frozen=True)
class PatientActivityResult:
    patient_id: int
    batch_id: int
    batch_release_time_minutes: float
    injection_time_minutes: float
    post_release_decay_time_minutes: float
    retention_at_injection: float
    prescribed_activity_mbq: float
    required_release_activity_mbq: float
    allocated_release_activity_mbq: float
    activity_supported: bool
    scheduler_completed_within_operating_day: bool
    activity_supported_completed_within_operating_day: bool


@dataclass(frozen=True)
class BatchActivityResult:
    batch_id: int
    release_time_minutes: float
    initial_release_activity_mbq: float
    allocated_release_activity_mbq: float
    remaining_release_activity_mbq: float
    patients_scheduled: int
    patients_activity_supported: int
    patients_activity_supported_and_completed: int
    activity_lost_or_unusable_mbq: float


@dataclass(frozen=True)
class F18OperatingDayResult:
    radionuclide: str
    half_life_minutes: float
    prescribed_activity_mbq_per_patient: float
    scheduler_completed_patients: int
    activity_supported_patients: int
    activity_supported_completed_patients: int
    total_patients_considered: int
    patient_activity_results: list[PatientActivityResult]
    batch_activity_results: list[BatchActivityResult]
    total_initial_release_activity_mbq: float
    total_allocated_release_activity_mbq: float
    total_remaining_release_activity_mbq: float
    total_activity_lost_or_unusable_mbq: float
    operating_day_feasible: bool
    source_schedule: OperatingDayScheduleResult


@lru_cache(maxsize=1)
def load_f18_half_life_minutes() -> float:
    data_path = Path(__file__).with_name("radionuclides.json")
    with data_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if "F-18" not in payload:
        raise ValueError("F-18 half-life is not available in radionuclides.json")
    return float(payload["F-18"]["half_life_min"])


def retention_at_delay_minutes(delay_minutes: float, half_life_minutes: float) -> float:
    if half_life_minutes <= 0.0:
        raise ValueError("half_life_minutes must be positive")
    if delay_minutes < 0.0:
        raise ValueError("delay_minutes must be non-negative")
    return 2.0 ** (-delay_minutes / half_life_minutes)


def _validate_inputs(inputs: F18ActivityInputs) -> None:
    if inputs.radionuclide != "F-18":
        raise ValueError("This MVP only supports F-18")
    if inputs.prescribed_activity_mbq_per_patient <= 0.0:
        raise ValueError("prescribed_activity_mbq_per_patient must be positive")
    if not inputs.activity_available_at_release_mbq_by_batch_id:
        raise ValueError("activity_available_at_release_mbq_by_batch_id must not be empty")
    if inputs.operating_day_schedule.total_patients_considered < 0:
        raise ValueError("operating_day_schedule is invalid")


def _batch_release_times_from_schedule(
    schedule: OperatingDayScheduleResult,
    explicit_release_times: dict[int, float] | None,
) -> dict[int, float]:
    if explicit_release_times is not None:
        return {int(batch_id): float(release_time) for batch_id, release_time in explicit_release_times.items()}

    by_batch: dict[int, list[float]] = defaultdict(list)
    for patient in schedule.patient_schedules:
        by_batch[patient.batch_id].append(patient.batch_release_time)

    release_times: dict[int, float] = {}
    for batch_id, values in by_batch.items():
        if not values:
            raise ValueError(f"No release time available for batch {batch_id}")
        first = values[0]
        for value in values[1:]:
            if abs(value - first) > 1e-9:
                raise ValueError(f"Inconsistent release times detected for batch {batch_id}")
        release_times[batch_id] = float(first)
    return release_times


def _batch_patient_order(schedule: OperatingDayScheduleResult) -> list[PatientSchedule]:
    return sorted(
        schedule.patient_schedules,
        key=lambda patient: (
            patient.injection_start,
            patient.injection_end,
            patient.batch_id,
            patient.patient_id,
        ),
    )


def evaluate_f18_operating_day(inputs: F18ActivityInputs) -> F18OperatingDayResult:
    _validate_inputs(inputs)
    half_life_minutes = load_f18_half_life_minutes()
    schedule = inputs.operating_day_schedule
    release_times = _batch_release_times_from_schedule(schedule, inputs.batch_release_times_minutes_by_batch_id)

    batch_remaining = {
        int(batch_id): float(activity)
        for batch_id, activity in inputs.activity_available_at_release_mbq_by_batch_id.items()
    }
    missing_batches = [batch_id for batch_id in release_times if batch_id not in batch_remaining]
    if missing_batches:
        raise ValueError(f"Missing release activity for batch ids: {missing_batches}")

    patient_results: list[PatientActivityResult] = []
    batch_allocated: dict[int, float] = {batch_id: 0.0 for batch_id in release_times}
    batch_supported: dict[int, int] = {batch_id: 0 for batch_id in release_times}
    batch_supported_completed: dict[int, int] = {batch_id: 0 for batch_id in release_times}

    for patient in _batch_patient_order(schedule):
        batch_id = int(patient.batch_id)
        release_time = release_times[batch_id]
        delay_minutes = max(0.0, patient.injection_start - release_time)
        retention = retention_at_delay_minutes(delay_minutes, half_life_minutes)
        required_release_activity = inputs.prescribed_activity_mbq_per_patient / retention
        remaining_before = batch_remaining[batch_id]
        activity_supported = remaining_before + 1e-12 >= required_release_activity
        allocated_release_activity = required_release_activity if activity_supported else 0.0
        if activity_supported:
            batch_remaining[batch_id] = remaining_before - required_release_activity
            batch_allocated[batch_id] += required_release_activity
            batch_supported[batch_id] += 1
        completed_and_supported = activity_supported and patient.completed_within_operating_day
        if completed_and_supported:
            batch_supported_completed[batch_id] += 1

        patient_results.append(
            PatientActivityResult(
                patient_id=patient.patient_id,
                batch_id=batch_id,
                batch_release_time_minutes=release_time,
                injection_time_minutes=patient.injection_start,
                post_release_decay_time_minutes=delay_minutes,
                retention_at_injection=retention,
                prescribed_activity_mbq=inputs.prescribed_activity_mbq_per_patient,
                required_release_activity_mbq=required_release_activity,
                allocated_release_activity_mbq=allocated_release_activity,
                activity_supported=activity_supported,
                scheduler_completed_within_operating_day=patient.completed_within_operating_day,
                activity_supported_completed_within_operating_day=completed_and_supported,
            )
        )

    batch_results: list[BatchActivityResult] = []
    for batch_id in sorted(release_times):
        initial = float(inputs.activity_available_at_release_mbq_by_batch_id[batch_id])
        allocated = batch_allocated[batch_id]
        remaining = batch_remaining[batch_id]
        batch_results.append(
            BatchActivityResult(
                batch_id=batch_id,
                release_time_minutes=release_times[batch_id],
                initial_release_activity_mbq=initial,
                allocated_release_activity_mbq=allocated,
                remaining_release_activity_mbq=remaining,
                patients_scheduled=sum(1 for patient in schedule.patient_schedules if patient.batch_id == batch_id),
                patients_activity_supported=batch_supported[batch_id],
                patients_activity_supported_and_completed=batch_supported_completed[batch_id],
                activity_lost_or_unusable_mbq=remaining,
            )
        )

    scheduler_completed_patients = schedule.completed_patients
    activity_supported_patients = sum(1 for patient in patient_results if patient.activity_supported)
    activity_supported_completed_patients = sum(
        1 for patient in patient_results if patient.activity_supported_completed_within_operating_day
    )
    total_patients_considered = schedule.total_patients_considered
    total_initial_release_activity_mbq = sum(result.initial_release_activity_mbq for result in batch_results)
    total_allocated_release_activity_mbq = sum(result.allocated_release_activity_mbq for result in batch_results)
    total_remaining_release_activity_mbq = sum(result.remaining_release_activity_mbq for result in batch_results)
    total_activity_lost_or_unusable_mbq = sum(result.activity_lost_or_unusable_mbq for result in batch_results)

    return F18OperatingDayResult(
        radionuclide="F-18",
        half_life_minutes=half_life_minutes,
        prescribed_activity_mbq_per_patient=inputs.prescribed_activity_mbq_per_patient,
        scheduler_completed_patients=scheduler_completed_patients,
        activity_supported_patients=activity_supported_patients,
        activity_supported_completed_patients=activity_supported_completed_patients,
        total_patients_considered=total_patients_considered,
        patient_activity_results=patient_results,
        batch_activity_results=batch_results,
        total_initial_release_activity_mbq=total_initial_release_activity_mbq,
        total_allocated_release_activity_mbq=total_allocated_release_activity_mbq,
        total_remaining_release_activity_mbq=total_remaining_release_activity_mbq,
        total_activity_lost_or_unusable_mbq=total_activity_lost_or_unusable_mbq,
        operating_day_feasible=activity_supported_completed_patients == scheduler_completed_patients,
        source_schedule=schedule,
    )

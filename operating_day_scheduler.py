from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

ClinicalResourceMode = Literal["OUTPATIENT_SHARED", "INBOUND_CENTRALIZED", "INBOUND_INTEGRATED"]
DEDICATED_ROOM_RESOURCE_INDEX = -1
"""Sentinel for injection_resource_index/uptake_resource_index (section 16/17):
the function was performed in the patient's dedicated inbound room, not a
shared INJ-xxx/UP-xxx resource -- never a valid shared-resource array index."""


@dataclass(frozen=True)
class BatchRelease:
    batch_id: int
    release_time_minutes: float
    patients_in_batch: int
    release_unit_id: str | None = None
    # Parallel arrays, one entry per patient in this batch (order matches the
    # patient loop below). Empty tuple = every patient is OUTPATIENT_SHARED
    # with no dedicated room (byte-for-byte existing behavior, section 33).
    patient_clinical_modes: tuple[ClinicalResourceMode, ...] = ()
    patient_inbound_room_ids: tuple[str | None, ...] = ()

    def __post_init__(self) -> None:
        if self.patient_clinical_modes and len(self.patient_clinical_modes) != self.patients_in_batch:
            raise ValueError("patient_clinical_modes length must match patients_in_batch")
        if self.patient_inbound_room_ids and len(self.patient_inbound_room_ids) != self.patients_in_batch:
            raise ValueError("patient_inbound_room_ids length must match patients_in_batch")


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
    clinical_day_start_minute: float = 0.0
    blocked_distribution_indices: frozenset[int] = frozenset()
    blocked_injection_indices: frozenset[int] = frozenset()
    blocked_uptake_indices: frozenset[int] = frozenset()
    blocked_scanner_indices: frozenset[int] = frozenset()
    """Rolling-reoptimization identity-sticky reservation (additive): indices in
    these sets are seeded as busy for the entire operating day instead of free
    at day-start, so they are never selected by `_allocate_earliest` -- WITHOUT
    shrinking/renumbering the array. This keeps every OTHER index's persistent
    resource identity stable across a rerun that only removes one resource
    (e.g. index 0 blocked -- SCN-002/003/004 remain indices 1/2/3, exactly as
    before). Empty (default) is byte-for-byte identical to prior behavior."""
    distribution_reserved_until: Mapping[int, float] = field(default_factory=dict)
    injection_reserved_until: Mapping[int, float] = field(default_factory=dict)
    uptake_reserved_until: Mapping[int, float] = field(default_factory=dict)
    scanner_reserved_until: Mapping[int, float] = field(default_factory=dict)
    """Rolling-reoptimization affected-subset reoptimization (additive): index ->
    the time that index becomes free, reflecting a PRESERVED (not rescheduled
    in this call) patient's actual consumption of that physical resource. Lets
    the day-engine schedule ONLY the directly-affected subset of patients into
    the TRUE residual capacity around already-preserved assignments, without
    re-deriving or disturbing those preserved assignments at all. Empty
    (default) is byte-for-byte identical to prior behavior. Ignored for an
    index also present in the corresponding `blocked_*_indices` set (blocking
    for the whole day takes precedence)."""


@dataclass(frozen=True)
class PatientSchedule:
    patient_id: int
    batch_id: int
    release_unit_id: str | None
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
    distribution_resource_index: int = 0
    injection_resource_index: int = 0
    uptake_resource_index: int = 0
    scanner_resource_index: int = 0
    clinical_resource_mode: ClinicalResourceMode = "OUTPATIENT_SHARED"
    inbound_room_id: str | None = None


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
        if batch.patients_in_batch < 0:
            raise ValueError("batch patients_in_batch must be non-negative")


def _allocate_earliest(availability: list[float], earliest_start: float, duration: float) -> tuple[int, float, float]:
    chosen_index = 0
    chosen_start = max(earliest_start, availability[0])
    for idx in range(1, len(availability)):
        candidate_start = max(earliest_start, availability[idx])
        if candidate_start < chosen_start:
            chosen_start = candidate_start
            chosen_index = idx
    end_time = chosen_start + duration
    availability[chosen_index] = end_time
    return chosen_index, chosen_start, end_time


def _occupied_minutes_within_day(start: float, end: float, clinical_day_start_minute: float, operating_day_minutes: float) -> float:
    clinical_day_end_minute = clinical_day_start_minute + operating_day_minutes
    overlap_start = max(clinical_day_start_minute, min(start, clinical_day_end_minute))
    overlap_end = max(clinical_day_start_minute, min(end, clinical_day_end_minute))
    return max(0.0, overlap_end - overlap_start)


def schedule_operating_day(inputs: OperatingDayInputs) -> OperatingDayScheduleResult:
    _validate_inputs(inputs)

    clinical_day_end_minute = inputs.clinical_day_start_minute + inputs.operating_day_minutes

    def _seed(index: int, blocked: frozenset[int], reserved_until: Mapping[int, float]) -> float:
        if index in blocked:
            return clinical_day_end_minute
        return reserved_until.get(index, inputs.clinical_day_start_minute)

    distribution_available_at = [
        _seed(i, inputs.blocked_distribution_indices, inputs.distribution_reserved_until)
        for i in range(inputs.distribution_concurrency)
    ]
    injection_available_at = [
        _seed(i, inputs.blocked_injection_indices, inputs.injection_reserved_until)
        for i in range(inputs.injection_resources)
    ]
    uptake_available_at = [
        _seed(i, inputs.blocked_uptake_indices, inputs.uptake_reserved_until)
        for i in range(inputs.uptake_resources)
    ]
    scanner_available_at = [
        _seed(i, inputs.blocked_scanner_indices, inputs.scanner_reserved_until)
        for i in range(inputs.scanners)
    ]

    patient_schedules: list[PatientSchedule] = []
    patient_id = 0

    scanner_occupied_minutes = 0.0
    injection_occupied_minutes = 0.0
    uptake_occupied_minutes = 0.0
    distribution_occupied_minutes = 0.0

    sorted_batches = sorted(
        inputs.batch_releases,
        key=lambda b: (b.release_time_minutes, b.batch_id, b.release_unit_id or ""),
    )

    for batch in sorted_batches:
        for patient_index in range(batch.patients_in_batch):
            patient_id += 1
            mode: ClinicalResourceMode = (
                batch.patient_clinical_modes[patient_index] if batch.patient_clinical_modes else "OUTPATIENT_SHARED"
            )
            room_id = batch.patient_inbound_room_ids[patient_index] if batch.patient_inbound_room_ids else None

            distribution_index, distribution_start, distribution_end = _allocate_earliest(
                distribution_available_at,
                batch.release_time_minutes,
                inputs.transport_minutes,
            )

            if mode == "INBOUND_INTEGRATED":
                # Section 16/21: injection performed in the dedicated inbound room --
                # never queues for/occupies a shared INJ-xxx resource.
                injection_index = DEDICATED_ROOM_RESOURCE_INDEX
                injection_start = distribution_end
                injection_end = injection_start + inputs.injection_service_minutes
            else:
                injection_index, injection_start, injection_end = _allocate_earliest(
                    injection_available_at,
                    distribution_end,
                    inputs.injection_service_minutes,
                )

            if mode in ("INBOUND_INTEGRATED", "INBOUND_CENTRALIZED"):
                # Section 17/22: dedicated-room uptake -- never queues for/occupies a
                # shared UP-xxx resource, for both INTEGRATED and CENTRALIZED.
                uptake_index = DEDICATED_ROOM_RESOURCE_INDEX
                uptake_start = injection_end
                uptake_end = uptake_start + inputs.uptake_minutes
            else:
                uptake_index, uptake_start, uptake_end = _allocate_earliest(
                    uptake_available_at,
                    injection_end,
                    inputs.uptake_minutes,
                )

            scanner_index, scan_start, scan_end = _allocate_earliest(
                scanner_available_at,
                uptake_end,
                inputs.scanner_service_minutes,
            )

            completed = scan_end <= clinical_day_end_minute

            distribution_occupied_minutes += _occupied_minutes_within_day(
                distribution_start,
                distribution_end,
                inputs.clinical_day_start_minute,
                inputs.operating_day_minutes,
            )
            if injection_index != DEDICATED_ROOM_RESOURCE_INDEX:
                injection_occupied_minutes += _occupied_minutes_within_day(
                    injection_start,
                    injection_end,
                    inputs.clinical_day_start_minute,
                    inputs.operating_day_minutes,
                )
            if uptake_index != DEDICATED_ROOM_RESOURCE_INDEX:
                uptake_occupied_minutes += _occupied_minutes_within_day(
                    uptake_start,
                    uptake_end,
                    inputs.clinical_day_start_minute,
                    inputs.operating_day_minutes,
                )
            scanner_occupied_minutes += _occupied_minutes_within_day(
                scan_start,
                scan_end,
                inputs.clinical_day_start_minute,
                inputs.operating_day_minutes,
            )

            patient_schedules.append(
                PatientSchedule(
                    patient_id=patient_id,
                    batch_id=batch.batch_id,
                    release_unit_id=batch.release_unit_id,
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
                    distribution_resource_index=distribution_index,
                    injection_resource_index=injection_index,
                    uptake_resource_index=uptake_index,
                    scanner_resource_index=scanner_index,
                    clinical_resource_mode=mode,
                    inbound_room_id=room_id,
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

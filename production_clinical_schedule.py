from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping

from cyclotron_production_windows import (
    CyclotronProductionCapability,
    CyclotronProductionSchedule,
    schedule_cyclotron_production_windows,
)
from operating_day_scheduler import (
    BatchRelease,
    OperatingDayInputs,
    OperatingDayScheduleResult,
    schedule_operating_day,
)
from patient_radionuclide_demand import (
    FacilityDayPatientDemand,
    RadionuclideBatchDemand,
    partition_facility_day_patient_demand,
)


@dataclass(frozen=True)
class ProductionClinicalScenario:
    facility_day_demand: FacilityDayPatientDemand
    requested_batch_count_by_radionuclide: Mapping[str, int]
    cyclotron_capability: CyclotronProductionCapability
    transport_minutes: float
    injection_service_minutes: float
    uptake_minutes: float
    scanner_service_minutes: float
    injection_resources: int
    uptake_resources: int
    scanners: int
    distribution_concurrency: int
    operating_day_minutes: float = 1080.0
    production_start_time_minutes: float = 0.0
    production_horizon_minutes: float | None = None

    def __post_init__(self) -> None:
        if self.operating_day_minutes <= 0.0:
            raise ValueError("operating_day_minutes must be positive")
        if self.production_start_time_minutes < 0.0:
            raise ValueError("production_start_time_minutes must be non-negative")
        if self.production_horizon_minutes is not None and self.production_horizon_minutes < 0.0:
            raise ValueError("production_horizon_minutes must be non-negative when provided")
        if self.transport_minutes < 0.0:
            raise ValueError("transport_minutes must be non-negative")
        if self.injection_service_minutes < 0.0:
            raise ValueError("injection_service_minutes must be non-negative")
        if self.uptake_minutes < 0.0:
            raise ValueError("uptake_minutes must be non-negative")
        if self.scanner_service_minutes < 0.0:
            raise ValueError("scanner_service_minutes must be non-negative")
        if self.injection_resources <= 0:
            raise ValueError("injection_resources must be at least 1")
        if self.uptake_resources <= 0:
            raise ValueError("uptake_resources must be at least 1")
        if self.scanners <= 0:
            raise ValueError("scanners must be at least 1")
        if self.distribution_concurrency <= 0:
            raise ValueError("distribution_concurrency must be at least 1")

        object.__setattr__(self, "requested_batch_count_by_radionuclide", dict(self.requested_batch_count_by_radionuclide))


@dataclass(frozen=True)
class ProductionBatchReleaseMapping:
    batch_id: int
    radionuclide: str
    patient_ids: tuple[str, ...]
    patient_count: int
    total_prescribed_activity_mbq: float
    production_window_id: int
    production_window_start_time_minutes: float
    production_window_end_time_minutes: float
    release_time_minutes: float


@dataclass(frozen=True)
class ProductionClinicalPatientTrace:
    patient_id: str
    radionuclide: str
    batch_id: int
    production_window_id: int
    production_window_start_time_minutes: float
    production_window_end_time_minutes: float
    batch_release_time_minutes: float
    scheduler_patient_id: int
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
class ProductionClinicalScheduleResult:
    scenario: ProductionClinicalScenario
    batch_demands: tuple[RadionuclideBatchDemand, ...]
    production_schedule: CyclotronProductionSchedule
    batch_release_mappings: tuple[ProductionBatchReleaseMapping, ...]
    batch_releases: tuple[BatchRelease, ...]
    operating_day_inputs: OperatingDayInputs
    clinical_schedule: OperatingDayScheduleResult
    patient_traces: tuple[ProductionClinicalPatientTrace, ...]


def _release_processing_minutes(
    capability: CyclotronProductionCapability,
    radionuclide: str,
) -> float:
    if capability.release_processing_minutes_by_radionuclide is None:
        return 0.0
    return float(capability.release_processing_minutes_by_radionuclide.get(radionuclide, 0.0))


def _build_batch_release_mappings(
    batch_demands: tuple[RadionuclideBatchDemand, ...],
    production_schedule: CyclotronProductionSchedule,
    capability: CyclotronProductionCapability,
) -> tuple[ProductionBatchReleaseMapping, ...]:
    window_by_batch_id: dict[int, object] = {}
    for window in production_schedule.windows:
        for batch_id in window.batch_ids:
            window_by_batch_id[batch_id] = window

    mappings: list[ProductionBatchReleaseMapping] = []
    for batch in batch_demands:
        window = window_by_batch_id[batch.batch_id]
        release_time = window.end_time_minutes + _release_processing_minutes(capability, batch.radionuclide)
        mappings.append(
            ProductionBatchReleaseMapping(
                batch_id=batch.batch_id,
                radionuclide=batch.radionuclide,
                patient_ids=batch.patient_ids,
                patient_count=batch.patient_count,
                total_prescribed_activity_mbq=batch.total_prescribed_activity_mbq,
                production_window_id=window.window_id,
                production_window_start_time_minutes=window.start_time_minutes,
                production_window_end_time_minutes=window.end_time_minutes,
                release_time_minutes=release_time,
            )
        )
    return tuple(mappings)


def _build_batch_releases(
    batch_release_mappings: tuple[ProductionBatchReleaseMapping, ...],
) -> tuple[BatchRelease, ...]:
    return tuple(
        BatchRelease(
            batch_id=mapping.batch_id,
            release_time_minutes=mapping.release_time_minutes,
            patients_in_batch=mapping.patient_count,
        )
        for mapping in batch_release_mappings
    )


def _build_patient_traces(
    batch_release_mappings: tuple[ProductionBatchReleaseMapping, ...],
    clinical_schedule: OperatingDayScheduleResult,
) -> tuple[ProductionClinicalPatientTrace, ...]:
    schedules_by_batch_id: dict[int, list[object]] = defaultdict(list)
    for patient_schedule in clinical_schedule.patient_schedules:
        schedules_by_batch_id[patient_schedule.batch_id].append(patient_schedule)

    traces: list[ProductionClinicalPatientTrace] = []
    for mapping in batch_release_mappings:
        batch_schedules = schedules_by_batch_id[mapping.batch_id]
        if len(batch_schedules) != mapping.patient_count:
            raise ValueError(
                f"Clinical schedule patient count for batch {mapping.batch_id} does not match batch demand"
            )
        for patient_id, patient_schedule in zip(mapping.patient_ids, batch_schedules):
            traces.append(
                ProductionClinicalPatientTrace(
                    patient_id=patient_id,
                    radionuclide=mapping.radionuclide,
                    batch_id=mapping.batch_id,
                    production_window_id=mapping.production_window_id,
                    production_window_start_time_minutes=mapping.production_window_start_time_minutes,
                    production_window_end_time_minutes=mapping.production_window_end_time_minutes,
                    batch_release_time_minutes=mapping.release_time_minutes,
                    scheduler_patient_id=patient_schedule.patient_id,
                    distribution_start=patient_schedule.distribution_start,
                    distribution_end=patient_schedule.distribution_end,
                    injection_start=patient_schedule.injection_start,
                    injection_end=patient_schedule.injection_end,
                    uptake_start=patient_schedule.uptake_start,
                    uptake_end=patient_schedule.uptake_end,
                    scan_start=patient_schedule.scan_start,
                    scan_end=patient_schedule.scan_end,
                    completed_within_operating_day=patient_schedule.completed_within_operating_day,
                )
            )
    return tuple(traces)


def build_production_clinical_schedule(
    scenario: ProductionClinicalScenario,
) -> ProductionClinicalScheduleResult:
    batch_demands = tuple(
        partition_facility_day_patient_demand(
            scenario.facility_day_demand,
            scenario.requested_batch_count_by_radionuclide,
        )
    )
    production_schedule = schedule_cyclotron_production_windows(
        batch_demands,
        scenario.cyclotron_capability,
        production_start_time_minutes=scenario.production_start_time_minutes,
        production_horizon_minutes=scenario.production_horizon_minutes,
    )
    batch_release_mappings = _build_batch_release_mappings(
        batch_demands,
        production_schedule,
        scenario.cyclotron_capability,
    )
    batch_releases = _build_batch_releases(batch_release_mappings)

    operating_day_inputs = OperatingDayInputs(
        operating_day_minutes=scenario.operating_day_minutes,
        batch_releases=list(batch_releases),
        transport_minutes=scenario.transport_minutes,
        injection_service_minutes=scenario.injection_service_minutes,
        uptake_minutes=scenario.uptake_minutes,
        scanner_service_minutes=scenario.scanner_service_minutes,
        injection_resources=scenario.injection_resources,
        uptake_resources=scenario.uptake_resources,
        scanners=scenario.scanners,
        distribution_concurrency=scenario.distribution_concurrency,
    )
    clinical_schedule = schedule_operating_day(operating_day_inputs)
    patient_traces = _build_patient_traces(batch_release_mappings, clinical_schedule)

    return ProductionClinicalScheduleResult(
        scenario=scenario,
        batch_demands=batch_demands,
        production_schedule=production_schedule,
        batch_release_mappings=batch_release_mappings,
        batch_releases=batch_releases,
        operating_day_inputs=operating_day_inputs,
        clinical_schedule=clinical_schedule,
        patient_traces=patient_traces,
    )
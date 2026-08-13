from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping

from diagnostics import load_radionuclide_half_lives


@lru_cache(maxsize=1)
def _canonical_radionuclide_lookup() -> dict[str, float]:
    return load_radionuclide_half_lives()


def _canonical_half_life_minutes(radionuclide: str) -> float:
    lookup = _canonical_radionuclide_lookup()
    if radionuclide not in lookup:
        raise ValueError(f"Unknown radionuclide: {radionuclide}")
    return float(lookup[radionuclide])


def _validate_patient_identity(patient_id: str) -> str:
    if not isinstance(patient_id, str):
        raise ValueError("patient_id must be a non-empty string")
    stripped = patient_id.strip()
    if not stripped:
        raise ValueError("patient_id must be a non-empty string")
    return stripped


def _validate_radionuclide(radionuclide: str) -> str:
    if not isinstance(radionuclide, str):
        raise ValueError("radionuclide must be a non-empty string")
    stripped = radionuclide.strip()
    if not stripped:
        raise ValueError("radionuclide must be a non-empty string")
    _canonical_half_life_minutes(stripped)
    return stripped


def _validate_activity(prescribed_activity_mbq: float) -> float:
    activity = float(prescribed_activity_mbq)
    if activity <= 0.0:
        raise ValueError("prescribed_activity_mbq must be greater than zero")
    return activity


@dataclass(frozen=True)
class PatientRadionuclideDemand:
    patient_id: str
    radionuclide: str
    prescribed_activity_mbq: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "patient_id", _validate_patient_identity(self.patient_id))
        object.__setattr__(self, "radionuclide", _validate_radionuclide(self.radionuclide))
        object.__setattr__(self, "prescribed_activity_mbq", _validate_activity(self.prescribed_activity_mbq))


@dataclass(frozen=True)
class FacilityDayPatientDemand:
    patients: tuple[PatientRadionuclideDemand, ...]

    def __post_init__(self) -> None:
        patients = tuple(self.patients)
        seen_patient_ids: set[str] = set()
        distinct_radionuclides: set[str] = set()

        for patient in patients:
            if not isinstance(patient, PatientRadionuclideDemand):
                raise ValueError("patients must contain PatientRadionuclideDemand instances")
            if patient.patient_id in seen_patient_ids:
                raise ValueError(f"Duplicate patient_id in facility day: {patient.patient_id}")
            seen_patient_ids.add(patient.patient_id)
            distinct_radionuclides.add(patient.radionuclide)

        if len(distinct_radionuclides) > 3:
            raise ValueError("Facility day cannot contain more than three distinct radionuclides")

        object.__setattr__(self, "patients", patients)


@dataclass(frozen=True)
class ResolvedPatientRadionuclideDemand:
    patient_id: str
    radionuclide: str
    half_life_minutes: float
    prescribed_activity_mbq: float


@dataclass(frozen=True)
class RadionuclidePatientGroup:
    radionuclide: str
    half_life_minutes: float
    patient_count: int
    total_prescribed_activity_mbq: float
    patient_ids: tuple[str, ...]


@dataclass(frozen=True)
class RadionuclideBatchDemand:
    batch_id: int
    radionuclide: str
    patient_ids: tuple[str, ...]
    patient_count: int
    total_prescribed_activity_mbq: float


def resolve_patient_radionuclide_demand(patient: PatientRadionuclideDemand) -> ResolvedPatientRadionuclideDemand:
    half_life_minutes = _canonical_half_life_minutes(patient.radionuclide)
    return ResolvedPatientRadionuclideDemand(
        patient_id=patient.patient_id,
        radionuclide=patient.radionuclide,
        half_life_minutes=half_life_minutes,
        prescribed_activity_mbq=patient.prescribed_activity_mbq,
    )


def resolve_facility_day_patient_demand(
    facility_day: FacilityDayPatientDemand,
) -> tuple[ResolvedPatientRadionuclideDemand, ...]:
    return tuple(resolve_patient_radionuclide_demand(patient) for patient in facility_day.patients)


def group_patients_by_radionuclide(
    facility_day: FacilityDayPatientDemand,
) -> tuple[RadionuclidePatientGroup, ...]:
    grouped_patients: OrderedDict[str, list[PatientRadionuclideDemand]] = OrderedDict()
    for patient in facility_day.patients:
        grouped_patients.setdefault(patient.radionuclide, []).append(patient)

    groups: list[RadionuclidePatientGroup] = []
    for radionuclide, patients in grouped_patients.items():
        groups.append(
            RadionuclidePatientGroup(
                radionuclide=radionuclide,
                half_life_minutes=_canonical_half_life_minutes(radionuclide),
                patient_count=len(patients),
                total_prescribed_activity_mbq=sum(patient.prescribed_activity_mbq for patient in patients),
                patient_ids=tuple(patient.patient_id for patient in patients),
            )
        )
    return tuple(groups)


def _even_partition_count(total_patients: int, requested_batches: int) -> tuple[int, ...]:
    if requested_batches < 0:
        raise ValueError("Requested batch count must be non-negative")
    if requested_batches == 0:
        if total_patients == 0:
            return ()
        raise ValueError("Requested batch count must be at least 1 when patients are present")

    base = total_patients // requested_batches
    remainder = total_patients % requested_batches
    return tuple(base + 1 if index < remainder else base for index in range(requested_batches))


def partition_facility_day_patient_demand(
    facility_day: FacilityDayPatientDemand,
    requested_batch_count_by_radionuclide: Mapping[str, int],
) -> tuple[RadionuclideBatchDemand, ...]:
    grouped_patients: OrderedDict[str, list[PatientRadionuclideDemand]] = OrderedDict()
    for patient in facility_day.patients:
        grouped_patients.setdefault(patient.radionuclide, []).append(patient)

    batch_demands: list[RadionuclideBatchDemand] = []
    next_batch_id = 1

    for radionuclide, patients in grouped_patients.items():
        if radionuclide not in requested_batch_count_by_radionuclide:
            raise ValueError(f"Missing requested batch count for radionuclide {radionuclide}")

        requested_batches = int(requested_batch_count_by_radionuclide[radionuclide])
        if requested_batches < 1:
            raise ValueError(f"Requested batch count for {radionuclide} must be at least 1")

        counts = _even_partition_count(len(patients), requested_batches)
        cursor = 0
        for batch_size in counts:
            batch_patients = patients[cursor : cursor + batch_size]
            cursor += batch_size
            batch_demands.append(
                RadionuclideBatchDemand(
                    batch_id=next_batch_id,
                    radionuclide=radionuclide,
                    patient_ids=tuple(patient.patient_id for patient in batch_patients),
                    patient_count=len(batch_patients),
                    total_prescribed_activity_mbq=sum(patient.prescribed_activity_mbq for patient in batch_patients),
                )
            )
            next_batch_id += 1

    for radionuclide in requested_batch_count_by_radionuclide:
        requested_batches = int(requested_batch_count_by_radionuclide[radionuclide])
        if requested_batches < 0:
            raise ValueError(f"Requested batch count for {radionuclide} must be non-negative")
        if requested_batches > 0 and radionuclide not in grouped_patients:
            raise ValueError(f"Requested batches for radionuclide {radionuclide} but no patients require it")

    return tuple(batch_demands)
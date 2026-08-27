"""Patient-Specific Nuclear Appointment Calendar Authority.

Section 6-9 closure: a known future PET/SPECT appointment is a persistent,
patient-specific clinical event -- never an anonymous aggregate. Reuses the
existing patient-identity conventions from `long_horizon_operational_planning.py`
(FORECAST- id prefix, DemandStatus-style lifecycle) rather than inventing a
parallel identity scheme.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

AppointmentStatus = Literal["FORECAST", "BOOKED", "CONFIRMED", "ACTUAL"]
NuclearModality = Literal["PET", "SPECT"]


@dataclass(frozen=True)
class NuclearAppointment:
    """Section 6: minimum persistent patient-specific nuclear appointment
    record. A known appointment (status BOOKED/CONFIRMED/ACTUAL) is
    authoritative over stochastic forecast demand for the same date (section
    8) -- forecast demand only fills the REMAINING unscheduled capacity."""

    appointment_id: str
    patient_id: str
    procedure_id: str
    scheduled_datetime: datetime
    patient_type: Literal["INPATIENT", "OUTPATIENT"]
    modality: NuclearModality
    radiopharmaceutical: str
    radionuclide: str
    status: AppointmentStatus
    provenance: str
    room_id: str | None = None
    outpatient_origin: str | None = None
    scanner_requirement: str | None = None

    def __post_init__(self) -> None:
        if not self.appointment_id.strip():
            raise ValueError("appointment_id must be non-empty")
        if not self.patient_id.strip():
            raise ValueError("patient_id must be non-empty")
        if self.patient_type == "INPATIENT" and self.room_id is None:
            raise ValueError(f"{self.appointment_id}: INPATIENT requires room_id (section 11)")
        if self.patient_type == "OUTPATIENT" and self.outpatient_origin is None:
            raise ValueError(f"{self.appointment_id}: OUTPATIENT requires outpatient_origin (section 11)")
        if self.patient_type == "OUTPATIENT" and self.room_id is not None:
            raise ValueError(f"{self.appointment_id}: OUTPATIENT must not carry a room_id")

    def is_known(self) -> bool:
        """Section 8: BOOKED/CONFIRMED/ACTUAL are 'known' -- authoritative
        over forecast demand for the same date. FORECAST is not yet known."""
        return self.status in ("BOOKED", "CONFIRMED", "ACTUAL")


@dataclass(frozen=True)
class DailyDemandReconciliation:
    """Section 8: TOTAL_PLANNED_DEMAND(t) = KNOWN_SCHEDULED_DEMAND(t) +
    FORECAST_DEMAND(t). Known appointments are NEVER overwritten -- forecast
    only supplements the remainder up to the configured target."""

    day: date
    known_pet: int
    known_spect: int
    forecast_pet: int
    forecast_spect: int
    total_planned_pet: int
    total_planned_spect: int
    booked_patient_ids: tuple[str, ...]


def reconcile_known_and_forecast_demand(
    *, day: date, known_appointments: tuple[NuclearAppointment, ...], forecast_pet: int, forecast_spect: int,
) -> DailyDemandReconciliation:
    """Section 8-9: known appointments for `day` are counted first and are
    authoritative; forecast counts are ADDED on top (never subtracted from,
    never used to replace, a known appointment)."""
    day_known = tuple(a for a in known_appointments if a.scheduled_datetime.date() == day and a.is_known())
    known_pet = sum(1 for a in day_known if a.modality == "PET")
    known_spect = sum(1 for a in day_known if a.modality == "SPECT")
    return DailyDemandReconciliation(
        day=day, known_pet=known_pet, known_spect=known_spect,
        forecast_pet=forecast_pet, forecast_spect=forecast_spect,
        total_planned_pet=known_pet + forecast_pet, total_planned_spect=known_spect + forecast_spect,
        booked_patient_ids=tuple(a.patient_id for a in day_known),
    )


def build_six_month_appointment_calendar(
    *, start_date: date, appointments: tuple[NuclearAppointment, ...],
) -> dict[date, tuple[NuclearAppointment, ...]]:
    """Section 10: groups appointments by date across an arbitrary horizon
    (six months = caller passes a 6-month appointment set) -- no new
    scheduling logic, pure grouping/lookup over persistent records."""
    calendar: dict[date, list[NuclearAppointment]] = {}
    for appointment in appointments:
        calendar.setdefault(appointment.scheduled_datetime.date(), []).append(appointment)
    return {day: tuple(items) for day, items in calendar.items()}


def find_patient_appointment(
    *, calendar: dict[date, tuple[NuclearAppointment, ...]], patient_id: str, on_date: date,
) -> NuclearAppointment | None:
    """Section 10: answers 'what nuclear procedure is P-023 scheduled for on
    a future date?' by direct lookup -- no reconstruction/guessing."""
    for appointment in calendar.get(on_date, ()):
        if appointment.patient_id == patient_id:
            return appointment
    return None

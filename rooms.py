from dataclasses import dataclass

@dataclass(frozen=True)
class InjectionRoom:
    service_min_per_patient: float

@dataclass(frozen=True)
class UptakeRoom:
    occupancy_min_per_patient: float

@dataclass(frozen=True)
class MRTInpatientRoom:
    patients_supported_per_day: float
    existing_room: bool = True

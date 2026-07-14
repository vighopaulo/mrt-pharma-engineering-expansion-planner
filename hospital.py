from dataclasses import dataclass
from domain.models import ProjectMode

@dataclass(frozen=True)
class Hospital:
    mode: ProjectMode
    current_patients_day: float
    target_patients_day: float
    operating_hours_day: float
    operating_days_year: int

    def normalized_current_patients(self) -> float:
        return 0.0 if self.mode is ProjectMode.GREENFIELD else self.current_patients_day

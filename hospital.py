from dataclasses import dataclass


@dataclass(frozen=True)
class Hospital:
    current_patients_day: float
    target_patients_day: float
    operating_hours_day: float
    operating_days_year: int

    def incremental_patients_day(self) -> float:
        return max(0.0, self.target_patients_day - self.current_patients_day)

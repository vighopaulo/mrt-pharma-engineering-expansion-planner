from dataclasses import dataclass

@dataclass(frozen=True)
class Scanner:
    cycle_min_per_patient: float
    availability_pct: float

    def daily_capacity(self, operating_hours_day: float) -> float:
        if self.cycle_min_per_patient <= 0:
            return 0.0
        return operating_hours_day * 60.0 / self.cycle_min_per_patient * self.availability_pct / 100.0

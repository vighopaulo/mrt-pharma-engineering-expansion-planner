from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Cyclotron:
    usable_doses_per_batch: float
    production_release_cycle_min: float
    current_batches_day: int = 0

    def max_batches(self, production_window_hours_day: float) -> int:
        if self.production_release_cycle_min <= 0:
            return 0
        return math.floor(production_window_hours_day * 60.0 / self.production_release_cycle_min)

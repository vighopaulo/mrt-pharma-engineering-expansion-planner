from dataclasses import dataclass

@dataclass(frozen=True)
class Radionuclide:
    name: str
    half_life_min: float

    def retained_fraction(self, transport_min: float) -> float:
        if self.half_life_min <= 0:
            raise ValueError('Half-life must be positive.')
        return 2 ** (-transport_min / self.half_life_min)

from dataclasses import dataclass
from domain.models import PRIORITIES

@dataclass(frozen=True)
class DecisionProfile:
    priority_1: str
    priority_2: str
    priority_3: str

    def validate(self) -> None:
        selected = [self.priority_1, self.priority_2, self.priority_3]
        if len(set(selected)) != 3:
            raise ValueError('The top three priorities must be different.')
        unknown = [p for p in selected if p not in PRIORITIES]
        if unknown:
            raise ValueError(f'Unknown decision priorities: {unknown}')

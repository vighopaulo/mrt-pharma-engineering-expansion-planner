from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionProfile:
    name: str
    description: str

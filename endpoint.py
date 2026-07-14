from dataclasses import dataclass

@dataclass(frozen=True)
class Endpoint:
    name: str
    endpoint_type: str
    installation_capex: float
    annual_opex: float

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping


IntegrationStatus = Literal[
    "DIRECT NATIVE CONNECTION",
    "NATIVE BOUNDED ORCHESTRATION",
    "MANUAL/WRAPPER CONNECTION",
    "NOT CONNECTED",
]


@dataclass(frozen=True)
class MrtCarrierFleetInputs:
    distribution_concurrency: int
    installed_carriers: int | None = None
    operated_carriers: int | None = None

    def __post_init__(self) -> None:
        distribution_concurrency = int(self.distribution_concurrency)
        if distribution_concurrency <= 0:
            raise ValueError("distribution_concurrency must be at least 1")

        operated_carriers = distribution_concurrency if self.operated_carriers is None else int(self.operated_carriers)
        installed_carriers = operated_carriers if self.installed_carriers is None else int(self.installed_carriers)

        if operated_carriers <= 0:
            raise ValueError("operated_carriers must be at least 1")
        if installed_carriers < 0:
            raise ValueError("installed_carriers must be non-negative")
        if installed_carriers < operated_carriers:
            raise ValueError("installed_carriers must be greater than or equal to operated_carriers")

        object.__setattr__(self, "distribution_concurrency", distribution_concurrency)
        object.__setattr__(self, "operated_carriers", operated_carriers)
        object.__setattr__(self, "installed_carriers", installed_carriers)

    @property
    def spare_carriers(self) -> int:
        return int(self.installed_carriers) - int(self.operated_carriers)


@dataclass(frozen=True)
class MrtCarrierFleetResult:
    installed_carriers: int
    operated_carriers: int
    spare_carriers: int
    distribution_concurrency: int
    carrier_constrained_throughput: bool
    bottleneck_resource: str | None
    proxy_relationship: str
    carrier_capex_modeled: bool
    carrier_opex_modeled: bool
    carrier_energy_modeled: bool
    carrier_capex_status: str
    carrier_opex_status: str
    carrier_energy_status: str


@dataclass(frozen=True)
class NativeMrtCarrierAudit:
    existing_fields: Mapping[str, str]
    existing_assumptions: Mapping[str, str]
    existing_formulas: Mapping[str, str]
    distribution_concurrency_is_native_equivalent: bool
    carrier_capex_line_item_exists: bool
    carrier_opex_line_item_exists: bool
    carrier_energy_line_item_exists: bool
    carrier_count_changes_throughput_natively: bool
    reporting_exposes_carrier_quantity: bool
    integration_audit: Mapping[str, IntegrationStatus]


def resolve_mrt_carrier_fleet(
    *,
    distribution_concurrency: int,
    installed_carriers: int | None = None,
    operated_carriers: int | None = None,
    bottleneck_resource: str | None = None,
) -> MrtCarrierFleetResult:
    inputs = MrtCarrierFleetInputs(
        distribution_concurrency=distribution_concurrency,
        installed_carriers=installed_carriers,
        operated_carriers=operated_carriers,
    )
    return MrtCarrierFleetResult(
        installed_carriers=int(inputs.installed_carriers),
        operated_carriers=int(inputs.operated_carriers),
        spare_carriers=int(inputs.spare_carriers),
        distribution_concurrency=int(inputs.distribution_concurrency),
        carrier_constrained_throughput=(bottleneck_resource in {"distribution", "carrier_transport"}),
        bottleneck_resource=bottleneck_resource,
        proxy_relationship="operated_mrt_carriers is the physical carrier fleet; distribution_concurrency remains a generic downstream capacity control",
        carrier_capex_modeled=True,
        carrier_opex_modeled=True,
        carrier_energy_modeled=True,
        carrier_capex_status="PROJECT_PLANNING_ASSUMPTION: per-carrier capex is modeled via PlannerAssumptions.mrt_carrier_capex_per_installed_unit.",
        carrier_opex_status="PROJECT_PLANNING_ASSUMPTION: per-carrier maintenance is modeled via PlannerAssumptions.mrt_carrier_maintenance_opex_per_installed_unit_year.",
        carrier_energy_status="PROJECT_PLANNING_ASSUMPTION: allocated carrier electricity is modeled via PlannerAssumptions.mrt_carrier_allocated_electricity_opex_per_operated_unit_year.",
    )


def resized_mrt_carrier_counts(
    *,
    base_distribution_concurrency: int,
    base_installed_carriers: int | None,
    base_operated_carriers: int | None,
    candidate_distribution_concurrency: int,
) -> tuple[int, int]:
    base = MrtCarrierFleetInputs(
        distribution_concurrency=base_distribution_concurrency,
        installed_carriers=base_installed_carriers,
        operated_carriers=base_operated_carriers,
    )
    spare_carriers = base.spare_carriers
    candidate_operated = int(candidate_distribution_concurrency)
    candidate_installed = candidate_operated + int(spare_carriers)
    return candidate_installed, candidate_operated


def audit_native_mrt_carrier_integration() -> NativeMrtCarrierAudit:
    return NativeMrtCarrierAudit(
        existing_fields={
            "distribution_concurrency": "Native scheduler/architecture transport concurrency control.",
            "installed_mrt_endpoints": "MRT endpoint quantity for infrastructure/accounting.",
            "annual_mrt_energy_kwh": "Pathway-level MRT annual energy assumption.",
        },
        existing_assumptions={
            "transport": "Scheduler allocates one transport slot per active concurrent movement.",
            "capex": "MRT CAPEX is currently guideway/endpoints/base infrastructure, not per carrier.",
            "opex": "MRT OPEX is currently guideway/endpoints/base/support labor, not per carrier.",
            "energy": "MRT energy is pathway-level and not parameterized by carrier count.",
        },
        existing_formulas={
            "throughput": "distribution_capacity_minutes = distribution_concurrency * operating_day_minutes",
            "utilization": "distribution_utilization_pct = distribution_occupied_minutes / distribution_capacity_minutes",
            "architecture_sizing": "MRT candidate generation already enumerates distribution_concurrency within explicit bounds",
        },
        distribution_concurrency_is_native_equivalent=False,
        carrier_capex_line_item_exists=True,
        carrier_opex_line_item_exists=True,
        carrier_energy_line_item_exists=True,
        carrier_count_changes_throughput_natively=True,
        reporting_exposes_carrier_quantity=True,
        integration_audit={
            "patient/batch demand -> distribution demand": "DIRECT NATIVE CONNECTION",
            "carrier fleet -> distribution concurrency": "NATIVE BOUNDED ORCHESTRATION",
            "carrier fleet -> throughput": "DIRECT NATIVE CONNECTION",
            "carrier fleet -> reliability": "DIRECT NATIVE CONNECTION",
            "carrier fleet -> CAPEX": "DIRECT NATIVE CONNECTION",
            "carrier fleet -> OPEX": "DIRECT NATIVE CONNECTION",
            "carrier fleet -> energy": "DIRECT NATIVE CONNECTION",
            "carrier fleet -> lifecycle economics": "DIRECT NATIVE CONNECTION",
            "carrier fleet -> architecture recommendation": "NATIVE BOUNDED ORCHESTRATION",
            "carrier fleet -> reporting": "DIRECT NATIVE CONNECTION",
        },
    )
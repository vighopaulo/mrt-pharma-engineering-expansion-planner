from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from models import PlannerAssumptions, SharedNetworkAssumptions


Pathway = Literal["Conventional", "MRT"]
DeploymentMode = Literal["greenfield", "existing_facility_expansion"]


def _validate_non_negative_int(name: str, value: int) -> int:
    count = int(value)
    if count < 0:
        raise ValueError(f"{name} must be non-negative")
    return count


def _validate_non_negative_float(name: str, value: float) -> float:
    amount = float(value)
    if amount < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return amount


def _incremental_quantity(installed: int | float, existing: int | float) -> int | float:
    if existing > installed:
        raise ValueError("existing quantity cannot exceed installed quantity")
    return installed - existing


@dataclass(frozen=True)
class CapexLedgerItem:
    component: str
    category: str
    quantity: float
    unit: str
    unit_cost: float
    subtotal: float
    cost_basis: str


@dataclass(frozen=True)
class InfrastructureCapexInputs:
    pathway: Pathway
    deployment_mode: DeploymentMode
    installed_scanners: int
    existing_scanners: int = 0
    installed_injection_resources: int = 0
    existing_injection_resources: int = 0
    installed_uptake_resources: int = 0
    existing_uptake_resources: int = 0
    installed_cyclotron_units: int = 0
    existing_cyclotron_units: int = 0
    installed_radiopharmacy_units: int = 0
    existing_radiopharmacy_units: int = 0
    radiopharmacy_unit_capex: float = 0.0
    conventional_infrastructure_allowance_units: int = 0
    existing_conventional_infrastructure_allowance_units: int = 0
    conventional_infrastructure_allowance_unit_capex: float = 0.0
    installed_mrt_base_infrastructure_units: int = 0
    existing_mrt_base_infrastructure_units: int = 0
    installed_mrt_endpoints: int = 0
    existing_mrt_endpoints: int = 0
    installed_guideway_length_m: float = 0.0
    existing_guideway_length_m: float = 0.0
    guideway_capex_per_m: float = 0.0
    installed_vertical_transitions: int = 0
    existing_vertical_transitions: int = 0
    installed_building_connections: int = 0
    existing_building_connections: int = 0
    assumptions: PlannerAssumptions | None = None
    network_assumptions: SharedNetworkAssumptions | None = None

    def __post_init__(self) -> None:
        if self.pathway not in {"Conventional", "MRT"}:
            raise ValueError("pathway must be Conventional or MRT")
        if self.deployment_mode not in {"greenfield", "existing_facility_expansion"}:
            raise ValueError("deployment_mode must be greenfield or existing_facility_expansion")

        for field_name in (
            "installed_scanners",
            "existing_scanners",
            "installed_injection_resources",
            "existing_injection_resources",
            "installed_uptake_resources",
            "existing_uptake_resources",
            "installed_cyclotron_units",
            "existing_cyclotron_units",
            "installed_radiopharmacy_units",
            "existing_radiopharmacy_units",
            "conventional_infrastructure_allowance_units",
            "existing_conventional_infrastructure_allowance_units",
            "installed_mrt_base_infrastructure_units",
            "existing_mrt_base_infrastructure_units",
            "installed_mrt_endpoints",
            "existing_mrt_endpoints",
            "installed_vertical_transitions",
            "existing_vertical_transitions",
            "installed_building_connections",
            "existing_building_connections",
        ):
            object.__setattr__(self, field_name, _validate_non_negative_int(field_name, getattr(self, field_name)))

        for field_name in (
            "installed_guideway_length_m",
            "existing_guideway_length_m",
            "guideway_capex_per_m",
            "radiopharmacy_unit_capex",
            "conventional_infrastructure_allowance_unit_capex",
        ):
            object.__setattr__(self, field_name, _validate_non_negative_float(field_name, getattr(self, field_name)))

        _incremental_quantity(self.installed_scanners, self.existing_scanners)
        _incremental_quantity(self.installed_injection_resources, self.existing_injection_resources)
        _incremental_quantity(self.installed_uptake_resources, self.existing_uptake_resources)
        _incremental_quantity(self.installed_cyclotron_units, self.existing_cyclotron_units)
        _incremental_quantity(self.installed_radiopharmacy_units, self.existing_radiopharmacy_units)
        _incremental_quantity(self.conventional_infrastructure_allowance_units, self.existing_conventional_infrastructure_allowance_units)
        _incremental_quantity(self.installed_mrt_base_infrastructure_units, self.existing_mrt_base_infrastructure_units)
        _incremental_quantity(self.installed_mrt_endpoints, self.existing_mrt_endpoints)
        _incremental_quantity(self.installed_guideway_length_m, self.existing_guideway_length_m)
        _incremental_quantity(self.installed_vertical_transitions, self.existing_vertical_transitions)
        _incremental_quantity(self.installed_building_connections, self.existing_building_connections)


@dataclass(frozen=True)
class InfrastructureCapexResult:
    pathway: Pathway
    deployment_mode: DeploymentMode
    installed_quantities: dict[str, float]
    charged_quantities: dict[str, float]
    clinical_capex: float
    production_capex: float
    conventional_specific_capex: float
    mrt_specific_capex: float
    total_capex: float
    ledger: tuple[CapexLedgerItem, ...]


def _ledger_item(
    *,
    component: str,
    category: str,
    quantity: float,
    unit: str,
    unit_cost: float,
    cost_basis: str,
) -> CapexLedgerItem:
    subtotal = float(quantity) * float(unit_cost)
    return CapexLedgerItem(
        component=component,
        category=category,
        quantity=float(quantity),
        unit=unit,
        unit_cost=float(unit_cost),
        subtotal=subtotal,
        cost_basis=cost_basis,
    )


def calculate_infrastructure_capex(inputs: InfrastructureCapexInputs) -> InfrastructureCapexResult:
    assumptions = inputs.assumptions or PlannerAssumptions()
    network_assumptions = inputs.network_assumptions or SharedNetworkAssumptions()

    charged_scanners = _incremental_quantity(inputs.installed_scanners, inputs.existing_scanners)
    charged_injection = _incremental_quantity(inputs.installed_injection_resources, inputs.existing_injection_resources)
    charged_uptake = _incremental_quantity(inputs.installed_uptake_resources, inputs.existing_uptake_resources)
    charged_cyclotrons = _incremental_quantity(inputs.installed_cyclotron_units, inputs.existing_cyclotron_units)
    charged_radiopharmacy = _incremental_quantity(inputs.installed_radiopharmacy_units, inputs.existing_radiopharmacy_units)
    charged_conventional_allowance = _incremental_quantity(
        inputs.conventional_infrastructure_allowance_units,
        inputs.existing_conventional_infrastructure_allowance_units,
    )
    charged_mrt_base = _incremental_quantity(
        inputs.installed_mrt_base_infrastructure_units,
        inputs.existing_mrt_base_infrastructure_units,
    )
    charged_endpoints = _incremental_quantity(inputs.installed_mrt_endpoints, inputs.existing_mrt_endpoints)
    charged_guideway_length = _incremental_quantity(inputs.installed_guideway_length_m, inputs.existing_guideway_length_m)
    charged_vertical_transitions = _incremental_quantity(
        inputs.installed_vertical_transitions,
        inputs.existing_vertical_transitions,
    )
    charged_building_connections = _incremental_quantity(
        inputs.installed_building_connections,
        inputs.existing_building_connections,
    )

    ledger: list[CapexLedgerItem] = [
        _ledger_item(
            component="Scanners",
            category="Clinical",
            quantity=charged_scanners,
            unit="units",
            unit_cost=assumptions.scanner_capex,
            cost_basis="PlannerAssumptions.scanner_capex",
        ),
        _ledger_item(
            component="Injection resources",
            category="Clinical",
            quantity=charged_injection,
            unit="units",
            unit_cost=assumptions.additional_room_capex,
            cost_basis="PlannerAssumptions.additional_room_capex",
        ),
        _ledger_item(
            component="Uptake resources",
            category="Clinical",
            quantity=charged_uptake,
            unit="units",
            unit_cost=assumptions.additional_room_capex,
            cost_basis="PlannerAssumptions.additional_room_capex",
        ),
        _ledger_item(
            component="Cyclotron purchase",
            category="Production",
            quantity=charged_cyclotrons,
            unit="units",
            unit_cost=assumptions.cyclotron_purchase_capex,
            cost_basis="PlannerAssumptions.cyclotron_purchase_capex",
        ),
        _ledger_item(
            component="Cyclotron installation",
            category="Production",
            quantity=charged_cyclotrons,
            unit="units",
            unit_cost=assumptions.cyclotron_installation_capex,
            cost_basis="PlannerAssumptions.cyclotron_installation_capex",
        ),
        _ledger_item(
            component="Radiopharmacy infrastructure",
            category="Production",
            quantity=charged_radiopharmacy,
            unit="units",
            unit_cost=inputs.radiopharmacy_unit_capex,
            cost_basis="Scenario calibrated input",
        ),
    ]

    if inputs.pathway == "Conventional":
        ledger.append(
            _ledger_item(
                component="Conventional infrastructure allowance",
                category="Conventional",
                quantity=charged_conventional_allowance,
                unit="units",
                unit_cost=inputs.conventional_infrastructure_allowance_unit_capex,
                cost_basis="Scenario calibrated input",
            )
        )
    elif inputs.pathway == "MRT":
        ledger.extend(
            [
                _ledger_item(
                    component="MRT base infrastructure",
                    category="MRT",
                    quantity=charged_mrt_base,
                    unit="units",
                    unit_cost=assumptions.mrt_infrastructure_capex,
                    cost_basis="PlannerAssumptions.mrt_infrastructure_capex",
                ),
                _ledger_item(
                    component="MRT endpoints",
                    category="MRT",
                    quantity=charged_endpoints,
                    unit="units",
                    unit_cost=assumptions.endpoint_capex,
                    cost_basis="PlannerAssumptions.endpoint_capex",
                ),
                _ledger_item(
                    component="MRT guideway",
                    category="MRT",
                    quantity=charged_guideway_length,
                    unit="m",
                    unit_cost=inputs.guideway_capex_per_m,
                    cost_basis="Scenario calibrated input",
                ),
                _ledger_item(
                    component="Vertical transitions",
                    category="MRT",
                    quantity=charged_vertical_transitions,
                    unit="units",
                    unit_cost=network_assumptions.vertical_transition_capex,
                    cost_basis="SharedNetworkAssumptions.vertical_transition_capex",
                ),
                _ledger_item(
                    component="Building connections",
                    category="MRT",
                    quantity=charged_building_connections,
                    unit="units",
                    unit_cost=network_assumptions.building_connection_capex,
                    cost_basis="SharedNetworkAssumptions.building_connection_capex",
                ),
            ]
        )

    clinical_capex = sum(item.subtotal for item in ledger if item.category == "Clinical")
    production_capex = sum(item.subtotal for item in ledger if item.category == "Production")
    conventional_specific_capex = sum(item.subtotal for item in ledger if item.category == "Conventional")
    mrt_specific_capex = sum(item.subtotal for item in ledger if item.category == "MRT")
    total_capex = sum(item.subtotal for item in ledger)

    installed_quantities = {
        "installed_scanners": float(inputs.installed_scanners),
        "installed_injection_resources": float(inputs.installed_injection_resources),
        "installed_uptake_resources": float(inputs.installed_uptake_resources),
        "installed_cyclotron_units": float(inputs.installed_cyclotron_units),
        "installed_radiopharmacy_units": float(inputs.installed_radiopharmacy_units),
        "conventional_infrastructure_allowance_units": float(inputs.conventional_infrastructure_allowance_units),
        "installed_mrt_base_infrastructure_units": float(inputs.installed_mrt_base_infrastructure_units),
        "installed_mrt_endpoints": float(inputs.installed_mrt_endpoints),
        "installed_guideway_length_m": float(inputs.installed_guideway_length_m),
        "installed_vertical_transitions": float(inputs.installed_vertical_transitions),
        "installed_building_connections": float(inputs.installed_building_connections),
    }
    charged_quantities = {
        "charged_scanners": float(charged_scanners),
        "charged_injection_resources": float(charged_injection),
        "charged_uptake_resources": float(charged_uptake),
        "charged_cyclotron_units": float(charged_cyclotrons),
        "charged_radiopharmacy_units": float(charged_radiopharmacy),
        "charged_conventional_infrastructure_allowance_units": float(charged_conventional_allowance),
        "charged_mrt_base_infrastructure_units": float(charged_mrt_base),
        "charged_mrt_endpoints": float(charged_endpoints),
        "charged_guideway_length_m": float(charged_guideway_length),
        "charged_vertical_transitions": float(charged_vertical_transitions),
        "charged_building_connections": float(charged_building_connections),
    }

    return InfrastructureCapexResult(
        pathway=inputs.pathway,
        deployment_mode=inputs.deployment_mode,
        installed_quantities=installed_quantities,
        charged_quantities=charged_quantities,
        clinical_capex=clinical_capex,
        production_capex=production_capex,
        conventional_specific_capex=conventional_specific_capex,
        mrt_specific_capex=mrt_specific_capex,
        total_capex=total_capex,
        ledger=tuple(ledger),
    )
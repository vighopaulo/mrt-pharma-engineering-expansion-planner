from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from models import PlannerAssumptions


Pathway = Literal["Conventional", "MRT"]
DeploymentMode = Literal["greenfield", "existing_facility_expansion"]
CostType = Literal["FIXED", "VARIABLE"]


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


@dataclass(frozen=True)
class OpexLedgerItem:
    component: str
    category: str
    cost_type: CostType
    quantity: float
    unit: str
    unit_cost: float
    annual_cost: float
    cost_basis: str


@dataclass(frozen=True)
class InfrastructureOpexInputs:
    pathway: Pathway
    deployment_mode: DeploymentMode
    operated_scanners: int = 0
    operated_injection_resources: int = 0
    operated_uptake_resources: int = 0
    operated_cyclotron_units: int = 0
    operated_radiopharmacy_units: int = 0
    operated_mrt_base_units: int = 0
    operated_mrt_endpoints: int = 0
    operated_guideway_length_m: float = 0.0
    operated_vertical_transitions: int = 0
    operated_building_connections: int = 0
    operating_days_per_year: int | None = None
    scanner_annual_opex_per_unit: float | None = None
    room_annual_opex_per_unit: float | None = None
    endpoint_annual_opex_per_unit: float | None = None
    cyclotron_annual_opex_per_unit: float = 0.0
    radiopharmacy_annual_opex_per_unit: float = 0.0
    annual_conventional_transport_opex_per_day: float | None = None
    annual_conventional_transport_opex: float = 0.0
    mrt_base_annual_opex_per_unit: float = 0.0
    guideway_maintenance_per_m_year: float = 0.0
    vertical_transition_annual_opex_per_unit: float = 0.0
    building_connection_annual_opex_per_unit: float = 0.0
    annual_production_variable_cost: float = 0.0
    annual_scanner_energy_kwh: float = 0.0
    annual_cyclotron_energy_kwh: float = 0.0
    annual_mrt_energy_kwh: float = 0.0
    annual_other_energy_kwh: float = 0.0
    electricity_cost_per_kwh: float = 0.0
    clinical_staff_fte: float = 0.0
    clinical_staff_loaded_cost_per_fte: float = 0.0
    production_staff_fte: float = 0.0
    production_staff_loaded_cost_per_fte: float = 0.0
    conventional_transport_staff_fte: float = 0.0
    conventional_transport_staff_loaded_cost_per_fte: float = 0.0
    mrt_support_staff_fte: float = 0.0
    mrt_support_staff_loaded_cost_per_fte: float = 0.0
    annual_consumable_units: float = 0.0
    consumable_cost_per_unit: float = 0.0
    assumptions: PlannerAssumptions | None = None

    def __post_init__(self) -> None:
        if self.pathway not in {"Conventional", "MRT"}:
            raise ValueError("pathway must be Conventional or MRT")
        if self.deployment_mode not in {"greenfield", "existing_facility_expansion"}:
            raise ValueError("deployment_mode must be greenfield or existing_facility_expansion")

        for field_name in (
            "operated_scanners",
            "operated_injection_resources",
            "operated_uptake_resources",
            "operated_cyclotron_units",
            "operated_radiopharmacy_units",
            "operated_mrt_base_units",
            "operated_mrt_endpoints",
            "operated_vertical_transitions",
            "operated_building_connections",
            "operating_days_per_year",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _validate_non_negative_int(field_name, value))

        for field_name in (
            "operated_guideway_length_m",
            "cyclotron_annual_opex_per_unit",
            "radiopharmacy_annual_opex_per_unit",
            "mrt_base_annual_opex_per_unit",
            "guideway_maintenance_per_m_year",
            "vertical_transition_annual_opex_per_unit",
            "building_connection_annual_opex_per_unit",
            "annual_production_variable_cost",
            "annual_scanner_energy_kwh",
            "annual_cyclotron_energy_kwh",
            "annual_mrt_energy_kwh",
            "annual_other_energy_kwh",
            "electricity_cost_per_kwh",
            "clinical_staff_fte",
            "clinical_staff_loaded_cost_per_fte",
            "production_staff_fte",
            "production_staff_loaded_cost_per_fte",
            "conventional_transport_staff_fte",
            "conventional_transport_staff_loaded_cost_per_fte",
            "mrt_support_staff_fte",
            "mrt_support_staff_loaded_cost_per_fte",
            "annual_consumable_units",
            "consumable_cost_per_unit",
            "annual_conventional_transport_opex",
        ):
            object.__setattr__(self, field_name, _validate_non_negative_float(field_name, getattr(self, field_name)))

        for field_name in (
            "scanner_annual_opex_per_unit",
            "room_annual_opex_per_unit",
            "endpoint_annual_opex_per_unit",
            "annual_conventional_transport_opex_per_day",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _validate_non_negative_float(field_name, value))


@dataclass(frozen=True)
class InfrastructureOpexResult:
    pathway: Pathway
    deployment_mode: DeploymentMode
    operated_quantities: dict[str, float]
    clinical_fixed_opex: float
    production_fixed_opex: float
    conventional_specific_opex: float
    mrt_specific_opex: float
    energy_opex: float
    labor_opex: float
    consumables_opex: float
    fixed_annual_opex: float
    variable_annual_opex: float
    total_annual_opex: float
    ledger: tuple[OpexLedgerItem, ...]


def _ledger_item(
    *,
    component: str,
    category: str,
    cost_type: CostType,
    quantity: float,
    unit: str,
    unit_cost: float,
    cost_basis: str,
) -> OpexLedgerItem:
    annual_cost = float(quantity) * float(unit_cost)
    return OpexLedgerItem(
        component=component,
        category=category,
        cost_type=cost_type,
        quantity=float(quantity),
        unit=unit,
        unit_cost=float(unit_cost),
        annual_cost=annual_cost,
        cost_basis=cost_basis,
    )


def calculate_infrastructure_opex(inputs: InfrastructureOpexInputs) -> InfrastructureOpexResult:
    assumptions = inputs.assumptions or PlannerAssumptions()
    operating_days_per_year = inputs.operating_days_per_year if inputs.operating_days_per_year is not None else assumptions.operating_days_per_year

    scanner_opex_per_unit = assumptions.scanner_incremental_opex if inputs.scanner_annual_opex_per_unit is None else inputs.scanner_annual_opex_per_unit
    room_opex_per_unit = assumptions.room_incremental_opex if inputs.room_annual_opex_per_unit is None else inputs.room_annual_opex_per_unit
    endpoint_opex_per_unit = assumptions.endpoint_incremental_opex if inputs.endpoint_annual_opex_per_unit is None else inputs.endpoint_annual_opex_per_unit

    rows: list[OpexLedgerItem] = [
        _ledger_item(
            component="Scanner annual O&M",
            category="CLINICAL",
            cost_type="FIXED",
            quantity=float(inputs.operated_scanners),
            unit="scanner-year",
            unit_cost=float(scanner_opex_per_unit),
            cost_basis="PlannerAssumptions.scanner_incremental_opex",
        ),
        _ledger_item(
            component="Injection resource annual O&M",
            category="CLINICAL",
            cost_type="FIXED",
            quantity=float(inputs.operated_injection_resources),
            unit="room-year",
            unit_cost=float(room_opex_per_unit),
            cost_basis="PlannerAssumptions.room_incremental_opex",
        ),
        _ledger_item(
            component="Uptake resource annual O&M",
            category="CLINICAL",
            cost_type="FIXED",
            quantity=float(inputs.operated_uptake_resources),
            unit="room-year",
            unit_cost=float(room_opex_per_unit),
            cost_basis="PlannerAssumptions.room_incremental_opex",
        ),
        _ledger_item(
            component="Cyclotron annual fixed O&M",
            category="PRODUCTION",
            cost_type="FIXED",
            quantity=float(inputs.operated_cyclotron_units),
            unit="cyclotron-year",
            unit_cost=float(inputs.cyclotron_annual_opex_per_unit),
            cost_basis="Scenario calibrated input",
        ),
        _ledger_item(
            component="Radiopharmacy annual fixed O&M",
            category="PRODUCTION",
            cost_type="FIXED",
            quantity=float(inputs.operated_radiopharmacy_units),
            unit="radiopharmacy-year",
            unit_cost=float(inputs.radiopharmacy_annual_opex_per_unit),
            cost_basis="Scenario calibrated input",
        ),
        _ledger_item(
            component="Production variable cost",
            category="PRODUCTION",
            cost_type="VARIABLE",
            quantity=1.0,
            unit="year",
            unit_cost=float(inputs.annual_production_variable_cost),
            cost_basis="Scenario calibrated input",
        ),
        _ledger_item(
            component="Scanner energy",
            category="ENERGY",
            cost_type="VARIABLE",
            quantity=float(inputs.annual_scanner_energy_kwh),
            unit="kWh/year",
            unit_cost=float(inputs.electricity_cost_per_kwh),
            cost_basis="Scenario calibrated input",
        ),
        _ledger_item(
            component="Cyclotron energy",
            category="ENERGY",
            cost_type="VARIABLE",
            quantity=float(inputs.annual_cyclotron_energy_kwh),
            unit="kWh/year",
            unit_cost=float(inputs.electricity_cost_per_kwh),
            cost_basis="Scenario calibrated input",
        ),
        _ledger_item(
            component="Other energy",
            category="ENERGY",
            cost_type="VARIABLE",
            quantity=float(inputs.annual_other_energy_kwh),
            unit="kWh/year",
            unit_cost=float(inputs.electricity_cost_per_kwh),
            cost_basis="Scenario calibrated input",
        ),
        _ledger_item(
            component="Clinical labor",
            category="LABOR",
            cost_type="FIXED",
            quantity=float(inputs.clinical_staff_fte),
            unit="FTE-year",
            unit_cost=float(inputs.clinical_staff_loaded_cost_per_fte),
            cost_basis="Scenario calibrated input",
        ),
        _ledger_item(
            component="Production labor",
            category="LABOR",
            cost_type="FIXED",
            quantity=float(inputs.production_staff_fte),
            unit="FTE-year",
            unit_cost=float(inputs.production_staff_loaded_cost_per_fte),
            cost_basis="Scenario calibrated input",
        ),
        _ledger_item(
            component="Consumables",
            category="CONSUMABLES",
            cost_type="VARIABLE",
            quantity=float(inputs.annual_consumable_units),
            unit="unit/year",
            unit_cost=float(inputs.consumable_cost_per_unit),
            cost_basis="Scenario calibrated input",
        ),
    ]

    if inputs.pathway == "Conventional":
        rows.extend(
            [
                _ledger_item(
                    component="Conventional transport and handling allowance",
                    category="CONVENTIONAL",
                    cost_type="FIXED",
                    quantity=1.0,
                    unit="year",
                    unit_cost=float(inputs.annual_conventional_transport_opex),
                    cost_basis="Scenario calibrated input",
                ),
                _ledger_item(
                    component="Conventional transport labor",
                    category="LABOR",
                    cost_type="FIXED",
                    quantity=float(inputs.conventional_transport_staff_fte),
                    unit="FTE-year",
                    unit_cost=float(inputs.conventional_transport_staff_loaded_cost_per_fte),
                    cost_basis="Scenario calibrated input",
                ),
            ]
        )
    elif inputs.pathway == "MRT":
        rows.extend(
            [
                _ledger_item(
                    component="MRT energy",
                    category="ENERGY",
                    cost_type="VARIABLE",
                    quantity=float(inputs.annual_mrt_energy_kwh),
                    unit="kWh/year",
                    unit_cost=float(inputs.electricity_cost_per_kwh),
                    cost_basis="Scenario calibrated input",
                ),
                _ledger_item(
                    component="MRT base annual O&M",
                    category="MRT",
                    cost_type="FIXED",
                    quantity=float(inputs.operated_mrt_base_units),
                    unit="base-year",
                    unit_cost=float(inputs.mrt_base_annual_opex_per_unit),
                    cost_basis="Scenario calibrated input",
                ),
                _ledger_item(
                    component="MRT endpoint annual O&M",
                    category="MRT",
                    cost_type="FIXED",
                    quantity=float(inputs.operated_mrt_endpoints),
                    unit="endpoint-year",
                    unit_cost=float(endpoint_opex_per_unit),
                    cost_basis="PlannerAssumptions.endpoint_incremental_opex",
                ),
                _ledger_item(
                    component="Guideway annual maintenance",
                    category="MRT",
                    cost_type="FIXED",
                    quantity=float(inputs.operated_guideway_length_m),
                    unit="m-year",
                    unit_cost=float(inputs.guideway_maintenance_per_m_year),
                    cost_basis="Scenario calibrated input",
                ),
                _ledger_item(
                    component="Vertical transition annual maintenance",
                    category="MRT",
                    cost_type="FIXED",
                    quantity=float(inputs.operated_vertical_transitions),
                    unit="transition-year",
                    unit_cost=float(inputs.vertical_transition_annual_opex_per_unit),
                    cost_basis="Scenario calibrated input",
                ),
                _ledger_item(
                    component="Building connection annual maintenance",
                    category="MRT",
                    cost_type="FIXED",
                    quantity=float(inputs.operated_building_connections),
                    unit="connection-year",
                    unit_cost=float(inputs.building_connection_annual_opex_per_unit),
                    cost_basis="Scenario calibrated input",
                ),
                _ledger_item(
                    component="MRT support labor",
                    category="LABOR",
                    cost_type="FIXED",
                    quantity=float(inputs.mrt_support_staff_fte),
                    unit="FTE-year",
                    unit_cost=float(inputs.mrt_support_staff_loaded_cost_per_fte),
                    cost_basis="Scenario calibrated input",
                ),
            ]
        )

    clinical_fixed_opex = sum(row.annual_cost for row in rows if row.category == "CLINICAL")
    production_fixed_opex = sum(row.annual_cost for row in rows if row.category == "PRODUCTION" and row.cost_type == "FIXED")
    conventional_specific_opex = sum(row.annual_cost for row in rows if row.category == "CONVENTIONAL")
    mrt_specific_opex = sum(row.annual_cost for row in rows if row.category == "MRT")
    energy_opex = sum(row.annual_cost for row in rows if row.category == "ENERGY")
    labor_opex = sum(row.annual_cost for row in rows if row.category == "LABOR")
    consumables_opex = sum(row.annual_cost for row in rows if row.category == "CONSUMABLES")
    fixed_annual_opex = sum(row.annual_cost for row in rows if row.cost_type == "FIXED")
    variable_annual_opex = sum(row.annual_cost for row in rows if row.cost_type == "VARIABLE")
    total_annual_opex = fixed_annual_opex + variable_annual_opex

    operated_quantities = {
        "operated_scanners": float(inputs.operated_scanners),
        "operated_injection_resources": float(inputs.operated_injection_resources),
        "operated_uptake_resources": float(inputs.operated_uptake_resources),
        "operated_cyclotron_units": float(inputs.operated_cyclotron_units),
        "operated_radiopharmacy_units": float(inputs.operated_radiopharmacy_units),
        "operated_mrt_base_units": float(inputs.operated_mrt_base_units),
        "operated_mrt_endpoints": float(inputs.operated_mrt_endpoints),
        "operated_guideway_length_m": float(inputs.operated_guideway_length_m),
        "operated_vertical_transitions": float(inputs.operated_vertical_transitions),
        "operated_building_connections": float(inputs.operated_building_connections),
        "operating_days_per_year": float(operating_days_per_year),
        "annual_scanner_energy_kwh": float(inputs.annual_scanner_energy_kwh),
        "annual_cyclotron_energy_kwh": float(inputs.annual_cyclotron_energy_kwh),
        "annual_mrt_energy_kwh": float(inputs.annual_mrt_energy_kwh),
        "annual_other_energy_kwh": float(inputs.annual_other_energy_kwh),
        "clinical_staff_fte": float(inputs.clinical_staff_fte),
        "production_staff_fte": float(inputs.production_staff_fte),
        "conventional_transport_staff_fte": float(inputs.conventional_transport_staff_fte),
        "mrt_support_staff_fte": float(inputs.mrt_support_staff_fte),
        "annual_consumable_units": float(inputs.annual_consumable_units),
    }

    return InfrastructureOpexResult(
        pathway=inputs.pathway,
        deployment_mode=inputs.deployment_mode,
        operated_quantities=operated_quantities,
        clinical_fixed_opex=clinical_fixed_opex,
        production_fixed_opex=production_fixed_opex,
        conventional_specific_opex=conventional_specific_opex,
        mrt_specific_opex=mrt_specific_opex,
        energy_opex=energy_opex,
        labor_opex=labor_opex,
        consumables_opex=consumables_opex,
        fixed_annual_opex=fixed_annual_opex,
        variable_annual_opex=variable_annual_opex,
        total_annual_opex=total_annual_opex,
        ledger=tuple(rows),
    )
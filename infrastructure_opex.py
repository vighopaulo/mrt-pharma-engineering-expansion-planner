from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from models import PlannerAssumptions

if TYPE_CHECKING:
    # Deferred to avoid a circular import: equipment_energy_opex.py transitively
    # imports decision_pipeline.py (via long_horizon_operational_planning ->
    # multi_cyclotron_authority -> spatial_benchmark), which imports THIS module.
    # `from __future__ import annotations` makes all annotations below strings,
    # so these names are only needed for static type-checking, never at runtime.
    from equipment_energy_opex import LedgerEnergyComponentInput, PathwayEnergyLedgerInput
    from healthcare_integration import EconomicComparabilityStatus


Pathway = Literal["Conventional", "MRT", "Hybrid"]
"""Section 41 (Hybrid unification): "Hybrid" is a valid `InfrastructureOpexResult.pathway`
value once ledger unification runs `calculate_infrastructure_opex` twice and merges the
results (hybrid_optimization.py::_build_hybrid_opex_result) -- `InfrastructureOpexInputs`
itself still only accepts "Conventional"/"MRT" (each merge call uses one of those two)."""
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
    energy_provenance: str | None = None
    """Section 17: distinguishes SCHEDULE_DERIVED_CALIBRATION from
    GENERIC_ENERGY_FALLBACK for ENERGY-category rows; None for non-energy
    rows or when no `energy_ledger_input` was supplied (legacy behavior)."""


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
    installed_mrt_carriers: int = 0
    operated_mrt_carriers: int = 0
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
    guideway_capex_per_m: float = 0.0
    vertical_transition_annual_opex_per_unit: float = 0.0
    building_connection_annual_opex_per_unit: float = 0.0
    mrt_carrier_allocated_electricity_opex_per_operated_unit_year: float | None = None
    mrt_carrier_maintenance_opex_per_installed_unit_year: float | None = None
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
    energy_ledger_input: PathwayEnergyLedgerInput | None = None
    """Section 7/20: optional calibration-aware schedule-derived electricity
    bridge from equipment_energy_opex.py. None (default) preserves the exact
    prior generic-kWh-only behavior for every existing caller (section 34/62)."""

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
            "installed_mrt_carriers",
            "operated_mrt_carriers",
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
            "guideway_capex_per_m",
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
            "mrt_carrier_allocated_electricity_opex_per_operated_unit_year",
            "mrt_carrier_maintenance_opex_per_installed_unit_year",
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
    economic_comparability_status: EconomicComparabilityStatus | None = None
    """Section 32-33: survives from `InfrastructureOpexInputs.energy_ledger_input`
    into the authoritative result; None when no ledger input was supplied
    (legacy/generic-only run -- comparability was never evaluated)."""


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


def _energy_ledger_item(
    *,
    component: str,
    generic_annual_kwh: float,
    unit_cost: float,
    ledger_component: LedgerEnergyComponentInput | None,
) -> OpexLedgerItem:
    """Sections 5/8-12/17: REPLACES the generic kWh quantity with the
    schedule-derived figure only when CALIBRATED_FOR_ENERGY; otherwise
    retains the pre-existing generic annual-kWh assumption unchanged (never
    added to it, never zeroed) and tags provenance for traceability. With
    `ledger_component=None` (no energy_ledger_input supplied at all) this is
    byte-for-byte identical to the pre-existing generic-only ledger line."""
    if ledger_component is None:
        return _ledger_item(
            component=component, category="ENERGY", cost_type="VARIABLE", quantity=generic_annual_kwh,
            unit="kWh/year", unit_cost=unit_cost, cost_basis="Scenario calibrated input",
        )
    if ledger_component.value_source == "SCHEDULE_DERIVED_CALIBRATION":
        cost_basis = "SCHEDULE_DERIVED_CALIBRATION (equipment_energy_opex.py, CALIBRATED_FOR_ENERGY)"
    else:
        cost_basis = (
            f"GENERIC_ENERGY_FALLBACK_USED: PROJECT_ASSUMPTION retained for economic continuity "
            f"(energy calibration_status={ledger_component.calibration_status}, ENERGY_PHYSICS_NOT_CALIBRATED)"
        )
    row = _ledger_item(
        component=component, category="ENERGY", cost_type="VARIABLE", quantity=ledger_component.annual_kwh,
        unit="kWh/year", unit_cost=unit_cost, cost_basis=cost_basis,
    )
    return replace(row, energy_provenance=ledger_component.value_source)


def calculate_infrastructure_opex(inputs: InfrastructureOpexInputs) -> InfrastructureOpexResult:
    assumptions = inputs.assumptions or PlannerAssumptions()
    operating_days_per_year = inputs.operating_days_per_year if inputs.operating_days_per_year is not None else assumptions.operating_days_per_year

    scanner_opex_per_unit = assumptions.scanner_incremental_opex if inputs.scanner_annual_opex_per_unit is None else inputs.scanner_annual_opex_per_unit
    room_opex_per_unit = assumptions.room_incremental_opex if inputs.room_annual_opex_per_unit is None else inputs.room_annual_opex_per_unit
    endpoint_opex_per_unit = assumptions.endpoint_incremental_opex if inputs.endpoint_annual_opex_per_unit is None else inputs.endpoint_annual_opex_per_unit
    carrier_allocated_electricity = (
        assumptions.mrt_carrier_allocated_electricity_opex_per_operated_unit_year
        if inputs.mrt_carrier_allocated_electricity_opex_per_operated_unit_year is None
        else inputs.mrt_carrier_allocated_electricity_opex_per_operated_unit_year
    )
    carrier_maintenance = (
        assumptions.mrt_carrier_maintenance_opex_per_installed_unit_year
        if inputs.mrt_carrier_maintenance_opex_per_installed_unit_year is None
        else inputs.mrt_carrier_maintenance_opex_per_installed_unit_year
    )
    guideway_maintenance_per_m = (
        inputs.guideway_maintenance_per_m_year
        if inputs.guideway_maintenance_per_m_year > 0.0
        else max(inputs.guideway_capex_per_m, assumptions.mrt_guideway_capex_per_m)
        * assumptions.mrt_guideway_maintenance_fraction_of_capex_per_year
    )

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
        _energy_ledger_item(
            component="Scanner energy",
            generic_annual_kwh=float(inputs.annual_scanner_energy_kwh),
            unit_cost=float(inputs.electricity_cost_per_kwh),
            ledger_component=inputs.energy_ledger_input.scanner if inputs.energy_ledger_input else None,
        ),
        _energy_ledger_item(
            component="Cyclotron energy",
            generic_annual_kwh=float(inputs.annual_cyclotron_energy_kwh),
            unit_cost=float(inputs.electricity_cost_per_kwh),
            ledger_component=inputs.energy_ledger_input.cyclotron if inputs.energy_ledger_input else None,
        ),
        _energy_ledger_item(
            component="Other energy",
            generic_annual_kwh=float(inputs.annual_other_energy_kwh),
            unit_cost=float(inputs.electricity_cost_per_kwh),
            ledger_component=inputs.energy_ledger_input.other if inputs.energy_ledger_input else None,
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
                _energy_ledger_item(
                    component="MRT energy",
                    generic_annual_kwh=float(inputs.annual_mrt_energy_kwh),
                    unit_cost=float(inputs.electricity_cost_per_kwh),
                    ledger_component=inputs.energy_ledger_input.mrt if inputs.energy_ledger_input else None,
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
                    unit_cost=float(guideway_maintenance_per_m),
                    cost_basis=(
                        "Scenario calibrated input"
                        if inputs.guideway_maintenance_per_m_year > 0.0
                        else "PROJECT_PLANNING_ASSUMPTION: 3% of guideway capex per meter"
                    ),
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
                _ledger_item(
                    component="MRT carrier allocated electricity",
                    category="MRT",
                    cost_type="FIXED",
                    quantity=float(inputs.operated_mrt_carriers),
                    unit="carrier-year",
                    unit_cost=float(carrier_allocated_electricity),
                    cost_basis="PROJECT_PLANNING_ASSUMPTION: PlannerAssumptions.mrt_carrier_allocated_electricity_opex_per_operated_unit_year",
                ),
                _ledger_item(
                    component="MRT carrier maintenance",
                    category="MRT",
                    cost_type="FIXED",
                    quantity=float(inputs.installed_mrt_carriers),
                    unit="carrier-year",
                    unit_cost=float(carrier_maintenance),
                    cost_basis="PROJECT_PLANNING_ASSUMPTION: PlannerAssumptions.mrt_carrier_maintenance_opex_per_installed_unit_year",
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
        "installed_mrt_carriers": float(inputs.installed_mrt_carriers),
        "operated_mrt_carriers": float(inputs.operated_mrt_carriers),
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
        economic_comparability_status=inputs.energy_ledger_input.economic_comparability_status() if inputs.energy_ledger_input else None,
    )


# ---------------------------------------------------------------------------
# Ledger composition helpers reused by non-native-pathway callers (e.g. Hybrid
# adapter, section 6/41: "one common ledger semantic", never a second
# authority). These operate on already-computed ledgers/results only -- no
# new physics or pricing.
# ---------------------------------------------------------------------------


def replace_ledger_component(
    *, ledger: tuple[OpexLedgerItem, ...], component: str, computed_annual_cost: float,
    quantity: float | None = None, unit: str | None = None, cost_basis: str | None = None,
) -> tuple[OpexLedgerItem, ...]:
    """Replaces ONE existing ledger row's dollar value with an authoritatively
    computed figure (e.g. workload-derived staffing) -- never adds a second,
    competing row for the same component. Raises if `component` is not
    already present, to avoid silently creating a new line by typo."""
    matches = [row for row in ledger if row.component == component]
    if not matches:
        raise ValueError(f"Component '{component}' not found in ledger -- cannot replace")
    if len(matches) > 1:
        raise ValueError(f"Component '{component}' appears {len(matches)} times -- ambiguous replacement")
    existing = matches[0]
    new_quantity = existing.quantity if quantity is None else quantity
    new_unit = existing.unit if unit is None else unit
    new_unit_cost = (computed_annual_cost / new_quantity) if new_quantity else 0.0
    new_cost_basis = existing.cost_basis if cost_basis is None else cost_basis
    replacement = replace(
        existing, quantity=new_quantity, unit=new_unit, unit_cost=new_unit_cost,
        annual_cost=computed_annual_cost, cost_basis=new_cost_basis,
    )
    return tuple(replacement if row.component == component else row for row in ledger)


def merge_shared_and_mode_specific_ledgers(
    *, shared_and_conventional_ledger: tuple[OpexLedgerItem, ...], mrt_specific_ledger: tuple[OpexLedgerItem, ...],
    mrt_specific_components: frozenset[str],
) -> tuple[OpexLedgerItem, ...]:
    """Section 5-6/41 (Hybrid unification): merges ONE ledger carrying shared +
    Conventional-specific quantities with ONE ledger carrying ONLY the named
    MRT-specific components (all other quantities zeroed by the caller before
    computing `mrt_specific_ledger`, so any non-MRT-specific row in it is
    dropped here rather than trusted at face value -- defense in depth
    against accidental double-counting, section 32)."""
    mrt_rows = tuple(row for row in mrt_specific_ledger if row.component in mrt_specific_components)
    shared_components = {row.component for row in shared_and_conventional_ledger}
    overlap = shared_components & {row.component for row in mrt_rows}
    if overlap:
        raise ValueError(f"Component(s) {sorted(overlap)} present in both ledgers -- would double-count")
    return tuple(shared_and_conventional_ledger) + mrt_rows


def recompute_ledger_totals(ledger: tuple[OpexLedgerItem, ...]) -> dict[str, float]:
    """Recomputes the same category/fixed/variable/total aggregates
    `calculate_infrastructure_opex` produces, from an arbitrary (e.g. merged
    or row-replaced) ledger -- section 35: the authoritative total is always
    SUM(ledger rows), never a separately hand-built figure."""
    return {
        "clinical_fixed_opex": sum(row.annual_cost for row in ledger if row.category == "CLINICAL"),
        "production_fixed_opex": sum(row.annual_cost for row in ledger if row.category == "PRODUCTION" and row.cost_type == "FIXED"),
        "conventional_specific_opex": sum(row.annual_cost for row in ledger if row.category == "CONVENTIONAL"),
        "mrt_specific_opex": sum(row.annual_cost for row in ledger if row.category == "MRT"),
        "energy_opex": sum(row.annual_cost for row in ledger if row.category == "ENERGY"),
        "labor_opex": sum(row.annual_cost for row in ledger if row.category == "LABOR"),
        "consumables_opex": sum(row.annual_cost for row in ledger if row.category == "CONSUMABLES"),
        "fixed_annual_opex": sum(row.annual_cost for row in ledger if row.cost_type == "FIXED"),
        "variable_annual_opex": sum(row.annual_cost for row in ledger if row.cost_type == "VARIABLE"),
        "total_annual_opex": sum(row.annual_cost for row in ledger),
    }
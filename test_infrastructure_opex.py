from __future__ import annotations

import math

import pytest

from infrastructure_opex import (
    InfrastructureOpexInputs,
    calculate_infrastructure_opex,
)
from models import PlannerAssumptions


def _base_inputs(**overrides) -> InfrastructureOpexInputs:
    payload = {
        "pathway": "Conventional",
        "deployment_mode": "greenfield",
        "operated_scanners": 3,
        "operated_injection_resources": 3,
        "operated_uptake_resources": 6,
        "operated_cyclotron_units": 1,
        "operated_radiopharmacy_units": 1,
        "operated_mrt_base_units": 1,
        "operated_mrt_endpoints": 4,
        "operated_guideway_length_m": 500.0,
        "operated_vertical_transitions": 1,
        "operated_building_connections": 1,
        "operating_days_per_year": 300,
        "scanner_annual_opex_per_unit": None,
        "room_annual_opex_per_unit": None,
        "endpoint_annual_opex_per_unit": None,
        "cyclotron_annual_opex_per_unit": 420_000.0,
        "radiopharmacy_annual_opex_per_unit": 180_000.0,
        "annual_conventional_transport_opex_per_day": None,
        "annual_conventional_transport_opex": 750_000.0,
        "mrt_base_annual_opex_per_unit": 600_000.0,
        "guideway_maintenance_per_m_year": 1_200.0,
        "vertical_transition_annual_opex_per_unit": 25_000.0,
        "building_connection_annual_opex_per_unit": 40_000.0,
        "annual_production_variable_cost": 300_000.0,
        "annual_scanner_energy_kwh": 12_000.0,
        "annual_cyclotron_energy_kwh": 120_000.0,
        "annual_mrt_energy_kwh": 25_000.0,
        "annual_other_energy_kwh": 4_000.0,
        "electricity_cost_per_kwh": 0.18,
        "clinical_staff_fte": 4.0,
        "clinical_staff_loaded_cost_per_fte": 95_000.0,
        "production_staff_fte": 2.0,
        "production_staff_loaded_cost_per_fte": 110_000.0,
        "conventional_transport_staff_fte": 1.0,
        "conventional_transport_staff_loaded_cost_per_fte": 80_000.0,
        "mrt_support_staff_fte": 3.0,
        "mrt_support_staff_loaded_cost_per_fte": 105_000.0,
        "annual_consumable_units": 6_000.0,
        "consumable_cost_per_unit": 22.0,
    }
    payload.update(overrides)
    return InfrastructureOpexInputs(**payload)


def _ledger_item(result, component: str):
    for item in result.ledger:
        if item.component == component:
            return item
    raise AssertionError(f"missing ledger item: {component}")


def _category_total(result, category: str) -> float:
    return sum(item.annual_cost for item in result.ledger if item.category == category)


def _cost_type_total(result, cost_type: str) -> float:
    return sum(item.annual_cost for item in result.ledger if item.cost_type == cost_type)


def _expected_total(result) -> float:
    return sum(item.annual_cost for item in result.ledger)


def _sum_components(result, components: tuple[str, ...]) -> float:
    return sum(_ledger_item(result, component).annual_cost for component in components)


def test_one_scanner_annual_om_prices_correctly():
    assumptions = PlannerAssumptions()
    result = calculate_infrastructure_opex(_base_inputs(operated_scanners=1, operated_injection_resources=0, operated_uptake_resources=0))

    scanner = _ledger_item(result, "Scanner annual O&M")
    assert math.isclose(scanner.unit_cost, assumptions.scanner_incremental_opex)
    assert math.isclose(scanner.annual_cost, assumptions.scanner_incremental_opex)


def test_multiple_scanner_om_prices_correctly():
    assumptions = PlannerAssumptions()
    result = calculate_infrastructure_opex(_base_inputs(operated_scanners=3, operated_injection_resources=0, operated_uptake_resources=0))

    scanner = _ledger_item(result, "Scanner annual O&M")
    assert math.isclose(scanner.quantity, 3.0)
    assert math.isclose(scanner.annual_cost, 3.0 * assumptions.scanner_incremental_opex)


def test_injection_resource_om_prices_correctly():
    assumptions = PlannerAssumptions()
    result = calculate_infrastructure_opex(_base_inputs(operated_scanners=0, operated_injection_resources=3, operated_uptake_resources=0))

    injection = _ledger_item(result, "Injection resource annual O&M")
    assert math.isclose(injection.unit_cost, assumptions.room_incremental_opex)
    assert math.isclose(injection.annual_cost, 3.0 * assumptions.room_incremental_opex)


def test_uptake_resource_om_prices_correctly():
    assumptions = PlannerAssumptions()
    result = calculate_infrastructure_opex(_base_inputs(operated_scanners=0, operated_injection_resources=0, operated_uptake_resources=6))

    uptake = _ledger_item(result, "Uptake resource annual O&M")
    assert math.isclose(uptake.unit_cost, assumptions.room_incremental_opex)
    assert math.isclose(uptake.annual_cost, 6.0 * assumptions.room_incremental_opex)


def test_same_clinical_architecture_gives_same_clinical_opex_across_pathways():
    conventional = calculate_infrastructure_opex(_base_inputs(pathway="Conventional"))
    mrt = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    assert math.isclose(conventional.clinical_fixed_opex, mrt.clinical_fixed_opex)
    for component in ("Scanner annual O&M", "Injection resource annual O&M", "Uptake resource annual O&M"):
        assert math.isclose(_ledger_item(conventional, component).annual_cost, _ledger_item(mrt, component).annual_cost)


def test_cyclotron_annual_fixed_om_is_priced():
    result = calculate_infrastructure_opex(_base_inputs())

    cyclotron = _ledger_item(result, "Cyclotron annual fixed O&M")
    assert math.isclose(cyclotron.annual_cost, 420_000.0)


def test_radiopharmacy_annual_fixed_om_is_priced():
    result = calculate_infrastructure_opex(_base_inputs())

    radiopharmacy = _ledger_item(result, "Radiopharmacy annual fixed O&M")
    assert math.isclose(radiopharmacy.annual_cost, 180_000.0)


def test_optional_production_variable_cost_is_ledgerized():
    result = calculate_infrastructure_opex(_base_inputs())

    production_variable = _ledger_item(result, "Production variable cost")
    assert production_variable.cost_type == "VARIABLE"
    assert math.isclose(production_variable.annual_cost, 300_000.0)


def test_conventional_specific_allowance_is_priced():
    result = calculate_infrastructure_opex(_base_inputs())

    allowance = _ledger_item(result, "Conventional transport and handling allowance")
    assert math.isclose(allowance.quantity, 1.0)
    assert math.isclose(allowance.annual_cost, 750_000.0)


def test_mrt_base_annual_om_is_priced():
    result = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    base = _ledger_item(result, "MRT base annual O&M")
    assert math.isclose(base.quantity, 1.0)
    assert math.isclose(base.annual_cost, 600_000.0)


def test_mrt_endpoint_annual_om_is_priced():
    assumptions = PlannerAssumptions()
    result = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    endpoints = _ledger_item(result, "MRT endpoint annual O&M")
    assert math.isclose(endpoints.quantity, 4.0)
    assert math.isclose(endpoints.annual_cost, 4.0 * assumptions.endpoint_incremental_opex)


def test_guideway_m_times_maintenance_per_m_year_is_priced():
    result = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    guideway = _ledger_item(result, "Guideway annual maintenance")
    assert math.isclose(guideway.quantity, 500.0)
    assert math.isclose(guideway.annual_cost, 500.0 * 1_200.0)


def test_zero_guideway_length_gives_zero_guideway_maintenance():
    result = calculate_infrastructure_opex(_base_inputs(pathway="MRT", operated_guideway_length_m=0.0))

    guideway = _ledger_item(result, "Guideway annual maintenance")
    assert math.isclose(guideway.annual_cost, 0.0)


def test_patient_count_does_not_directly_multiply_guideway_maintenance():
    patient_count_low = 10
    patient_count_high = 1_000
    result_low = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))
    result_high = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    assert patient_count_low != patient_count_high
    assert math.isclose(_ledger_item(result_low, "Guideway annual maintenance").annual_cost, _ledger_item(result_high, "Guideway annual maintenance").annual_cost)


def test_carrier_movements_do_not_directly_multiply_guideway_maintenance():
    carrier_movements_low = 1
    carrier_movements_high = 500
    result_low = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))
    result_high = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    assert carrier_movements_low != carrier_movements_high
    assert math.isclose(_ledger_item(result_low, "Guideway annual maintenance").annual_cost, _ledger_item(result_high, "Guideway annual maintenance").annual_cost)


def test_conventional_does_not_receive_mrt_energy_or_mrt_support_labor():
    conventional = calculate_infrastructure_opex(_base_inputs(pathway="Conventional"))

    assert all(item.component != "MRT energy" for item in conventional.ledger)
    assert all(item.component != "MRT support labor" for item in conventional.ledger)


def test_mrt_does_not_receive_conventional_transport_or_conventional_allowance():
    mrt = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    assert all(item.component != "Conventional transport labor" for item in mrt.ledger)
    assert all(item.component != "Conventional transport and handling allowance" for item in mrt.ledger)


def test_mrt_energy_only_exists_on_mrt_when_supplied():
    conventional = calculate_infrastructure_opex(_base_inputs(pathway="Conventional"))
    mrt = calculate_infrastructure_opex(_base_inputs(pathway="MRT", annual_mrt_energy_kwh=25_000.0))

    assert all(item.component != "MRT energy" for item in conventional.ledger)
    assert _ledger_item(mrt, "MRT energy").annual_cost > 0.0


def test_vertical_transition_maintenance_is_priced():
    result = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    transition = _ledger_item(result, "Vertical transition annual maintenance")
    assert math.isclose(transition.annual_cost, 25_000.0)


def test_building_connection_maintenance_is_priced():
    result = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    connection = _ledger_item(result, "Building connection annual maintenance")
    assert math.isclose(connection.annual_cost, 40_000.0)


def test_electricity_kwh_times_cost_per_kwh_is_priced():
    result = calculate_infrastructure_opex(_base_inputs())

    scanner_energy = _ledger_item(result, "Scanner energy")
    assert math.isclose(scanner_energy.annual_cost, 12_000.0 * 0.18)


def test_zero_energy_gives_zero_energy_cost():
    result = calculate_infrastructure_opex(
        _base_inputs(
            annual_scanner_energy_kwh=0.0,
            annual_cyclotron_energy_kwh=0.0,
            annual_mrt_energy_kwh=0.0,
            annual_other_energy_kwh=0.0,
        )
    )

    assert math.isclose(result.energy_opex, 0.0)


def test_scanner_cyclotron_and_mrt_energy_remain_separate_ledger_lines():
    result = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    assert _ledger_item(result, "Scanner energy").category == "ENERGY"
    assert _ledger_item(result, "Cyclotron energy").category == "ENERGY"
    assert _ledger_item(result, "MRT energy").category == "ENERGY"
    assert _ledger_item(result, "Other energy").category == "ENERGY"


def test_clinical_labor_fte_pricing():
    result = calculate_infrastructure_opex(_base_inputs())

    labor = _ledger_item(result, "Clinical labor")
    assert math.isclose(labor.annual_cost, 4.0 * 95_000.0)


def test_production_labor_fte_pricing():
    result = calculate_infrastructure_opex(_base_inputs())

    labor = _ledger_item(result, "Production labor")
    assert math.isclose(labor.annual_cost, 2.0 * 110_000.0)


def test_conventional_transport_labor_pricing():
    result = calculate_infrastructure_opex(_base_inputs())

    labor = _ledger_item(result, "Conventional transport labor")
    assert math.isclose(labor.annual_cost, 1.0 * 80_000.0)


def test_mrt_support_labor_pricing():
    result = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    labor = _ledger_item(result, "MRT support labor")
    assert math.isclose(labor.annual_cost, 3.0 * 105_000.0)


def test_zero_labor_fte_gives_zero_labor_cost():
    result = calculate_infrastructure_opex(
        _base_inputs(
            clinical_staff_fte=0.0,
            production_staff_fte=0.0,
            conventional_transport_staff_fte=0.0,
            mrt_support_staff_fte=0.0,
        )
    )

    assert math.isclose(result.labor_opex, 0.0)


def test_consumable_quantity_times_cost_per_unit_is_priced():
    result = calculate_infrastructure_opex(_base_inputs())

    consumables = _ledger_item(result, "Consumables")
    assert math.isclose(consumables.annual_cost, 6_000.0 * 22.0)


def test_fixed_ledger_reconciliation():
    result = calculate_infrastructure_opex(_base_inputs())

    assert math.isclose(result.fixed_annual_opex, _cost_type_total(result, "FIXED"))


def test_variable_ledger_reconciliation():
    result = calculate_infrastructure_opex(_base_inputs())

    assert math.isclose(result.variable_annual_opex, _cost_type_total(result, "VARIABLE"))


def test_total_ledger_reconciliation():
    result = calculate_infrastructure_opex(_base_inputs())

    assert math.isclose(result.total_annual_opex, _expected_total(result))


def test_negative_quantities_rejected():
    with pytest.raises(ValueError, match="operated_scanners must be non-negative"):
        _base_inputs(operated_scanners=-1)


def test_negative_unit_costs_rejected():
    with pytest.raises(ValueError, match="electricity_cost_per_kwh must be non-negative"):
        _base_inputs(electricity_cost_per_kwh=-0.01)


def test_unsupported_pathway_rejected():
    with pytest.raises(ValueError, match="pathway must be Conventional or MRT"):
        InfrastructureOpexInputs(pathway="Invalid", deployment_mode="greenfield")


def test_cost_basis_is_retained_for_every_ledger_line():
    conventional_result = calculate_infrastructure_opex(_base_inputs(pathway="Conventional"))
    mrt_result = calculate_infrastructure_opex(_base_inputs(pathway="MRT"))

    assert all(item.cost_basis for item in conventional_result.ledger)
    assert all(item.cost_basis for item in mrt_result.ledger)
    assert _ledger_item(conventional_result, "Scanner annual O&M").cost_basis == "PlannerAssumptions.scanner_incremental_opex"
    assert _ledger_item(mrt_result, "Guideway annual maintenance").cost_basis == "Scenario calibrated input"
    assert _ledger_item(conventional_result, "Conventional transport and handling allowance").cost_basis == "Scenario calibrated input"


def test_existing_equipment_can_still_incur_opex():
    existing_mode = calculate_infrastructure_opex(_base_inputs(deployment_mode="existing_facility_expansion"))
    greenfield_mode = calculate_infrastructure_opex(_base_inputs(deployment_mode="greenfield"))

    assert existing_mode.total_annual_opex > 0.0
    assert math.isclose(existing_mode.total_annual_opex, greenfield_mode.total_annual_opex)


def test_identical_common_infrastructure_produces_identical_common_opex():
    conventional = calculate_infrastructure_opex(_base_inputs(pathway="Conventional", annual_conventional_transport_opex_per_day=0.0))
    mrt = calculate_infrastructure_opex(_base_inputs(pathway="MRT", annual_conventional_transport_opex_per_day=0.0))

    assert math.isclose(conventional.clinical_fixed_opex, mrt.clinical_fixed_opex)
    assert math.isclose(conventional.production_fixed_opex, mrt.production_fixed_opex)
    assert math.isclose(_ledger_item(conventional, "Scanner annual O&M").annual_cost, _ledger_item(mrt, "Scanner annual O&M").annual_cost)


def test_mrt_specific_opex_difference_equals_mrt_only_ledger_rows_when_common_costs_are_identical():
    conventional = calculate_infrastructure_opex(
        _base_inputs(
            pathway="Conventional",
            annual_conventional_transport_opex_per_day=0.0,
            annual_conventional_transport_opex=0.0,
            conventional_transport_staff_fte=0.0,
        )
    )
    mrt = calculate_infrastructure_opex(
        _base_inputs(
            pathway="MRT",
            annual_conventional_transport_opex_per_day=0.0,
            annual_conventional_transport_opex=0.0,
            conventional_transport_staff_fte=0.0,
        )
    )

    expected_mrt_only = _sum_components(
        mrt,
        (
            "MRT energy",
            "MRT support labor",
            "MRT base annual O&M",
            "MRT endpoint annual O&M",
            "Guideway annual maintenance",
            "Vertical transition annual maintenance",
            "Building connection annual maintenance",
        ),
    )
    assert math.isclose(mrt.total_annual_opex - conventional.total_annual_opex, expected_mrt_only)


def test_conventional_specific_opex_difference_is_transparent_and_isolated():
    zero_allowance = calculate_infrastructure_opex(_base_inputs(pathway="Conventional", annual_conventional_transport_opex=0.0))
    paid_allowance = calculate_infrastructure_opex(_base_inputs(pathway="Conventional"))

    assert math.isclose(paid_allowance.total_annual_opex - zero_allowance.total_annual_opex, paid_allowance.conventional_specific_opex)


def test_total_opex_is_independent_of_capex_values():
    capex_value_a = 1_000_000.0
    capex_value_b = 99_000_000.0
    first = calculate_infrastructure_opex(_base_inputs())
    second = calculate_infrastructure_opex(_base_inputs())

    assert capex_value_a != capex_value_b
    assert math.isclose(first.total_annual_opex, second.total_annual_opex)


def test_opex_module_does_not_calculate_npv():
    result = calculate_infrastructure_opex(_base_inputs())

    assert not hasattr(result, "npv")
    assert not hasattr(result, "payback_years")

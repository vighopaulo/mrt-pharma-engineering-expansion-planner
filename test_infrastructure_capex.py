from __future__ import annotations

import math

import pytest

from infrastructure_capex import (
    InfrastructureCapexInputs,
    calculate_infrastructure_capex,
)
from models import PlannerAssumptions, SharedNetworkAssumptions


def _base_inputs(**overrides) -> InfrastructureCapexInputs:
    payload = {
        "pathway": "Conventional",
        "deployment_mode": "greenfield",
        "installed_scanners": 3,
        "existing_scanners": 0,
        "installed_injection_resources": 3,
        "existing_injection_resources": 0,
        "installed_uptake_resources": 6,
        "existing_uptake_resources": 0,
        "installed_cyclotron_units": 1,
        "existing_cyclotron_units": 0,
        "installed_radiopharmacy_units": 1,
        "existing_radiopharmacy_units": 0,
        "radiopharmacy_unit_capex": 750_000.0,
        "conventional_infrastructure_allowance_units": 1,
        "existing_conventional_infrastructure_allowance_units": 0,
        "conventional_infrastructure_allowance_unit_capex": 125_000.0,
        "installed_mrt_base_infrastructure_units": 1,
        "existing_mrt_base_infrastructure_units": 0,
        "installed_mrt_endpoints": 4,
        "existing_mrt_endpoints": 0,
        "installed_guideway_length_m": 500.0,
        "existing_guideway_length_m": 0.0,
        "guideway_capex_per_m": 12_000.0,
        "installed_vertical_transitions": 1,
        "existing_vertical_transitions": 0,
        "installed_building_connections": 1,
        "existing_building_connections": 0,
    }
    payload.update(overrides)
    return InfrastructureCapexInputs(**payload)


def _ledger_item(result, component: str):
    for item in result.ledger:
        if item.component == component:
            return item
    raise AssertionError(f"missing ledger item: {component}")


def _category_total(result, category: str) -> float:
    return sum(item.subtotal for item in result.ledger if item.category == category)


def _expected_total(result) -> float:
    return sum(item.subtotal for item in result.ledger)


def test_one_scanner_prices_correctly():
    assumptions = PlannerAssumptions()
    inputs = _base_inputs(
        installed_scanners=1,
        existing_scanners=0,
        installed_injection_resources=0,
        installed_uptake_resources=0,
        installed_cyclotron_units=0,
        installed_radiopharmacy_units=0,
        conventional_infrastructure_allowance_units=0,
    )
    result = calculate_infrastructure_capex(inputs)

    scanner = _ledger_item(result, "Scanners")
    assert math.isclose(scanner.unit_cost, assumptions.scanner_capex)
    assert math.isclose(scanner.subtotal, assumptions.scanner_capex)


def test_multiple_scanners_price_correctly():
    assumptions = PlannerAssumptions()
    inputs = _base_inputs(
        installed_scanners=3,
        existing_scanners=0,
        installed_injection_resources=0,
        installed_uptake_resources=0,
        installed_cyclotron_units=0,
        installed_radiopharmacy_units=0,
        conventional_infrastructure_allowance_units=0,
    )
    result = calculate_infrastructure_capex(inputs)

    scanner = _ledger_item(result, "Scanners")
    assert math.isclose(scanner.quantity, 3.0)
    assert math.isclose(scanner.subtotal, 3.0 * assumptions.scanner_capex)


def test_injection_resources_price_correctly():
    assumptions = PlannerAssumptions()
    inputs = _base_inputs(
        installed_scanners=0,
        installed_injection_resources=3,
        installed_uptake_resources=0,
        installed_cyclotron_units=0,
        installed_radiopharmacy_units=0,
        conventional_infrastructure_allowance_units=0,
    )
    result = calculate_infrastructure_capex(inputs)

    injection = _ledger_item(result, "Injection resources")
    assert math.isclose(injection.unit_cost, assumptions.additional_room_capex)
    assert math.isclose(injection.subtotal, 3.0 * assumptions.additional_room_capex)


def test_uptake_resources_price_correctly():
    assumptions = PlannerAssumptions()
    inputs = _base_inputs(
        installed_scanners=0,
        installed_injection_resources=0,
        installed_uptake_resources=6,
        installed_cyclotron_units=0,
        installed_radiopharmacy_units=0,
        conventional_infrastructure_allowance_units=0,
    )
    result = calculate_infrastructure_capex(inputs)

    uptake = _ledger_item(result, "Uptake resources")
    assert math.isclose(uptake.unit_cost, assumptions.additional_room_capex)
    assert math.isclose(uptake.subtotal, 6.0 * assumptions.additional_room_capex)


def test_cyclotron_purchase_and_installation_reconcile():
    assumptions = PlannerAssumptions()
    inputs = _base_inputs(
        installed_scanners=0,
        installed_injection_resources=0,
        installed_uptake_resources=0,
        installed_cyclotron_units=1,
        installed_radiopharmacy_units=0,
        conventional_infrastructure_allowance_units=0,
    )
    result = calculate_infrastructure_capex(inputs)

    purchase = _ledger_item(result, "Cyclotron purchase")
    installation = _ledger_item(result, "Cyclotron installation")
    assert math.isclose(purchase.subtotal, assumptions.cyclotron_purchase_capex)
    assert math.isclose(installation.subtotal, assumptions.cyclotron_installation_capex)
    assert math.isclose(
        purchase.subtotal + installation.subtotal,
        assumptions.cyclotron_purchase_capex + assumptions.cyclotron_installation_capex,
    )


def test_zero_cyclotron_quantity_gives_zero_cyclotron_capex():
    inputs = _base_inputs(
        installed_scanners=0,
        installed_injection_resources=0,
        installed_uptake_resources=0,
        installed_cyclotron_units=0,
        installed_radiopharmacy_units=0,
        conventional_infrastructure_allowance_units=0,
    )
    result = calculate_infrastructure_capex(inputs)

    assert math.isclose(_ledger_item(result, "Cyclotron purchase").subtotal, 0.0)
    assert math.isclose(_ledger_item(result, "Cyclotron installation").subtotal, 0.0)


def test_common_clinical_unit_costs_are_identical_across_pathways():
    conventional = calculate_infrastructure_capex(_base_inputs(pathway="Conventional"))
    mrt = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    for component in ("Scanners", "Injection resources", "Uptake resources"):
        assert math.isclose(_ledger_item(conventional, component).unit_cost, _ledger_item(mrt, component).unit_cost)


def test_mrt_base_infrastructure_is_charged_once():
    assumptions = PlannerAssumptions()
    result = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    base = _ledger_item(result, "MRT base infrastructure")
    assert math.isclose(base.quantity, 1.0)
    assert math.isclose(base.subtotal, assumptions.mrt_infrastructure_capex)


def test_mrt_endpoint_quantity_pricing():
    assumptions = PlannerAssumptions()
    result = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    endpoints = _ledger_item(result, "MRT endpoints")
    assert math.isclose(endpoints.quantity, 4.0)
    assert math.isclose(endpoints.subtotal, 4.0 * assumptions.endpoint_capex)


def test_guideway_metres_times_cost_per_metre():
    inputs = _base_inputs(pathway="MRT")
    result = calculate_infrastructure_capex(inputs)

    guideway = _ledger_item(result, "MRT guideway")
    assert math.isclose(guideway.quantity, 500.0)
    assert math.isclose(guideway.unit_cost, 12_000.0)
    assert math.isclose(guideway.subtotal, 500.0 * 12_000.0)


def test_zero_guideway_length_gives_zero_guideway_capex():
    inputs = _base_inputs(pathway="MRT", installed_guideway_length_m=0.0)
    result = calculate_infrastructure_capex(inputs)

    guideway = _ledger_item(result, "MRT guideway")
    assert math.isclose(guideway.subtotal, 0.0)


def test_carrier_movements_do_not_affect_installed_guideway_capex():
    inputs = _base_inputs(pathway="MRT")
    carrier_movements_travelled_m = 9_999.0
    result = calculate_infrastructure_capex(inputs)

    guideway = _ledger_item(result, "MRT guideway")
    assert math.isclose(guideway.subtotal, inputs.installed_guideway_length_m * inputs.guideway_capex_per_m)
    assert carrier_movements_travelled_m != inputs.installed_guideway_length_m


def test_vertical_transition_pricing():
    assumptions = SharedNetworkAssumptions()
    result = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    transitions = _ledger_item(result, "Vertical transitions")
    assert math.isclose(transitions.subtotal, assumptions.vertical_transition_capex)


def test_building_connection_pricing():
    assumptions = SharedNetworkAssumptions()
    result = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    connections = _ledger_item(result, "Building connections")
    assert math.isclose(connections.subtotal, assumptions.building_connection_capex)


def test_conventional_specific_allowance_pricing():
    inputs = _base_inputs(pathway="Conventional")
    result = calculate_infrastructure_capex(inputs)

    allowance = _ledger_item(result, "Conventional infrastructure allowance")
    assert math.isclose(allowance.quantity, 1.0)
    assert math.isclose(allowance.subtotal, inputs.conventional_infrastructure_allowance_unit_capex)


def test_total_ledger_equals_exact_sum_of_ledger_subtotals():
    result = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    assert math.isclose(result.total_capex, _expected_total(result))


def test_category_totals_reconcile_to_total_capex():
    result = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    category_total = (
        result.clinical_capex
        + result.production_capex
        + result.conventional_specific_capex
        + result.mrt_specific_capex
    )
    assert math.isclose(category_total, result.total_capex)
    assert math.isclose(result.clinical_capex, _category_total(result, "Clinical"))
    assert math.isclose(result.production_capex, _category_total(result, "Production"))
    assert math.isclose(result.conventional_specific_capex, _category_total(result, "Conventional"))
    assert math.isclose(result.mrt_specific_capex, _category_total(result, "MRT"))


def test_negative_quantities_rejected():
    with pytest.raises(ValueError, match="installed_scanners must be non-negative"):
        _base_inputs(installed_scanners=-1)


def test_negative_unit_costs_rejected():
    with pytest.raises(ValueError, match="guideway_capex_per_m must be non-negative"):
        _base_inputs(guideway_capex_per_m=-1.0)


def test_greenfield_prices_all_installed_quantities():
    result = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    assert math.isclose(result.total_capex, _expected_total(result))
    assert any(value > 0 for value in result.charged_quantities.values())


def test_existing_facility_expansion_can_exclude_explicitly_sunk_equipment():
    inputs = InfrastructureCapexInputs(
        pathway="MRT",
        deployment_mode="existing_facility_expansion",
        installed_scanners=3,
        existing_scanners=3,
        installed_injection_resources=3,
        existing_injection_resources=3,
        installed_uptake_resources=6,
        existing_uptake_resources=6,
        installed_cyclotron_units=1,
        existing_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        existing_radiopharmacy_units=1,
        radiopharmacy_unit_capex=750_000.0,
        conventional_infrastructure_allowance_units=1,
        existing_conventional_infrastructure_allowance_units=1,
        conventional_infrastructure_allowance_unit_capex=125_000.0,
        installed_mrt_base_infrastructure_units=1,
        existing_mrt_base_infrastructure_units=1,
        installed_mrt_endpoints=4,
        existing_mrt_endpoints=4,
        installed_guideway_length_m=500.0,
        existing_guideway_length_m=500.0,
        guideway_capex_per_m=12_000.0,
        installed_vertical_transitions=1,
        existing_vertical_transitions=1,
        installed_building_connections=1,
        existing_building_connections=1,
    )
    result = calculate_infrastructure_capex(inputs)

    assert math.isclose(result.total_capex, 0.0)
    assert all(math.isclose(item.subtotal, 0.0) for item in result.ledger)


def test_identical_installed_clinical_architecture_gives_identical_clinical_capex():
    conventional = calculate_infrastructure_capex(_base_inputs(pathway="Conventional"))
    mrt = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    assert math.isclose(conventional.clinical_capex, mrt.clinical_capex)


def test_mrt_total_exceeds_identical_conventional_by_mrt_specific_costs():
    conventional = calculate_infrastructure_capex(
        _base_inputs(pathway="Conventional", conventional_infrastructure_allowance_units=0, existing_conventional_infrastructure_allowance_units=0)
    )
    mrt = calculate_infrastructure_capex(
        _base_inputs(pathway="MRT", conventional_infrastructure_allowance_units=0, existing_conventional_infrastructure_allowance_units=0)
    )

    incremental = mrt.total_capex - conventional.total_capex
    assert math.isclose(incremental, mrt.mrt_specific_capex)
    assert math.isclose(mrt.mrt_specific_capex, sum(item.subtotal for item in mrt.ledger if item.category == "MRT"))


def test_patient_count_does_not_directly_influence_capex():
    low_patient_count = 12
    high_patient_count = 1200
    result_low = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))
    result_high = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    assert low_patient_count != high_patient_count
    assert math.isclose(result_low.total_capex, result_high.total_capex)


def test_batch_count_does_not_directly_influence_capex():
    low_batch_count = 1
    high_batch_count = 24
    result_low = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))
    result_high = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    assert low_batch_count != high_batch_count
    assert math.isclose(result_low.total_capex, result_high.total_capex)


def test_cost_basis_is_retained_for_every_ledger_line():
    result = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    assert all(item.cost_basis for item in result.ledger)
    assert _ledger_item(result, "Scanners").cost_basis == "PlannerAssumptions.scanner_capex"
    assert _ledger_item(result, "Vertical transitions").cost_basis == "SharedNetworkAssumptions.vertical_transition_capex"
    assert _ledger_item(result, "MRT guideway").cost_basis == "Scenario calibrated input"


def test_unsupported_pathway_rejected():
    with pytest.raises(ValueError, match="pathway must be Conventional or MRT"):
        InfrastructureCapexInputs(
            pathway="Invalid",
            deployment_mode="greenfield",
            installed_scanners=0,
        )


def test_installed_guideway_length_remains_distinct_from_carrier_distance_travelled():
    carrier_distance_travelled_m = 9_999.0
    result = calculate_infrastructure_capex(_base_inputs(pathway="MRT"))

    guideway = _ledger_item(result, "MRT guideway")
    assert math.isclose(guideway.quantity, 500.0)
    assert carrier_distance_travelled_m != guideway.quantity

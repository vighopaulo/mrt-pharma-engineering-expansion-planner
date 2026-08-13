from __future__ import annotations

import math

from architecture_optimizer import (
    FacilityEnvelope,
    OptimizationDemand,
    evaluate_architecture_candidate,
    optimize_fixed_envelope_architecture,
)
from lifecycle_economics import evaluate_lifecycle_economics
from models import PlannerAssumptions


def _assumptions_for_stage1() -> PlannerAssumptions:
    return PlannerAssumptions(
        analysis_years=10,
        discount_rate_pct=8.0,
        operating_days_per_year=300,
        operating_hours_per_day=18.0,
        scanner_cycle_min=35.0,
        scanner_availability_pct=85.0,
        injection_cycle_min=15.0,
        uptake_cycle_min=60.0,
        revenue_per_scan=2000.0,
        scanner_capex=1_000_000.0,
        additional_room_capex=100_000.0,
        scanner_incremental_opex=100_000.0,
        room_incremental_opex=20_000.0,
        mrt_infrastructure_capex=4_000_000.0,
        endpoint_capex=50_000.0,
        endpoint_incremental_opex=5_000.0,
    )


def test_both_pathways_obey_identical_fixed_envelope_scanner_and_room_limits():
    assumptions = _assumptions_for_stage1()
    envelope = FacilityEnvelope(max_scanners=4, max_injection_resources=3, max_uptake_resources=3, max_mrt_endpoints=8)
    demand = OptimizationDemand(starting_demand_per_day=300.0)

    result = optimize_fixed_envelope_architecture(
        envelope=envelope,
        assumptions=assumptions,
        demand=demand,
    )

    conv = result.conventional.optimal_candidate
    mrt = result.mrt.optimal_candidate

    assert conv.scanners <= envelope.max_scanners
    assert conv.injection_resources <= envelope.max_injection_resources
    assert conv.uptake_resources <= envelope.max_uptake_resources
    assert mrt.scanners <= envelope.max_scanners
    assert mrt.injection_resources <= envelope.max_injection_resources
    assert mrt.uptake_resources <= envelope.max_uptake_resources


def test_optimizer_never_selects_resources_outside_envelope():
    assumptions = _assumptions_for_stage1()
    envelope = FacilityEnvelope(max_scanners=3, max_injection_resources=2, max_uptake_resources=2, max_mrt_endpoints=5)
    demand = OptimizationDemand(starting_demand_per_day=200.0)

    result = optimize_fixed_envelope_architecture(
        envelope=envelope,
        assumptions=assumptions,
        demand=demand,
    )

    for candidate in result.conventional.feasible_candidates + result.mrt.feasible_candidates:
        assert 0 <= candidate.scanners <= envelope.max_scanners
        assert 0 <= candidate.injection_resources <= envelope.max_injection_resources
        assert 0 <= candidate.uptake_resources <= envelope.max_uptake_resources

    for candidate in result.mrt.feasible_candidates:
        assert envelope.min_mrt_endpoints <= candidate.endpoints <= envelope.max_mrt_endpoints


def test_more_scanners_do_not_increase_throughput_when_rooms_bind():
    assumptions = _assumptions_for_stage1()
    demand = OptimizationDemand(starting_demand_per_day=500.0)

    low_scanners = evaluate_architecture_candidate(
        pathway="Conventional",
        scanners=1,
        injection_resources=1,
        uptake_resources=1,
        endpoints=0,
        assumptions=assumptions,
        demand=demand,
    )
    high_scanners = evaluate_architecture_candidate(
        pathway="Conventional",
        scanners=5,
        injection_resources=1,
        uptake_resources=1,
        endpoints=0,
        assumptions=assumptions,
        demand=demand,
    )

    assert low_scanners is not None
    assert high_scanners is not None
    assert math.isclose(
        low_scanners.installed_capacity_per_day,
        high_scanners.installed_capacity_per_day,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_more_rooms_do_not_increase_throughput_when_scanners_bind():
    assumptions = _assumptions_for_stage1()
    demand = OptimizationDemand(starting_demand_per_day=500.0)

    fewer_rooms = evaluate_architecture_candidate(
        pathway="Conventional",
        scanners=1,
        injection_resources=2,
        uptake_resources=2,
        endpoints=0,
        assumptions=assumptions,
        demand=demand,
    )
    more_rooms = evaluate_architecture_candidate(
        pathway="Conventional",
        scanners=1,
        injection_resources=6,
        uptake_resources=6,
        endpoints=0,
        assumptions=assumptions,
        demand=demand,
    )

    assert fewer_rooms is not None
    assert more_rooms is not None
    assert math.isclose(
        fewer_rooms.installed_capacity_per_day,
        more_rooms.installed_capacity_per_day,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_demand_caps_revenue_even_when_installed_capacity_is_higher():
    assumptions = _assumptions_for_stage1()
    demand = OptimizationDemand(starting_demand_per_day=10.0)

    candidate = evaluate_architecture_candidate(
        pathway="Conventional",
        scanners=5,
        injection_resources=5,
        uptake_resources=5,
        endpoints=0,
        assumptions=assumptions,
        demand=demand,
    )

    assert candidate is not None
    first_year = candidate.lifecycle.annual_rows[0]
    expected_revenue = 10.0 * assumptions.revenue_per_scan * assumptions.operating_days_per_year
    assert candidate.installed_capacity_per_day > 10.0
    assert math.isclose(first_year.annual_revenue, expected_revenue, rel_tol=0.0, abs_tol=1e-9)


def test_higher_capex_architecture_selected_when_capacity_monetizes_in_high_demand_case():
    assumptions = _assumptions_for_stage1()
    envelope = FacilityEnvelope(max_scanners=3, max_injection_resources=3, max_uptake_resources=3, max_mrt_endpoints=6)
    demand = OptimizationDemand(starting_demand_per_day=250.0)

    small = evaluate_architecture_candidate(
        pathway="Conventional",
        scanners=1,
        injection_resources=1,
        uptake_resources=1,
        endpoints=0,
        assumptions=assumptions,
        demand=demand,
    )
    large = evaluate_architecture_candidate(
        pathway="Conventional",
        scanners=3,
        injection_resources=3,
        uptake_resources=3,
        endpoints=0,
        assumptions=assumptions,
        demand=demand,
    )
    assert small is not None
    assert large is not None
    assert large.capex > small.capex
    assert large.installed_capacity_per_day > small.installed_capacity_per_day
    assert large.final_npv > small.final_npv

    result = optimize_fixed_envelope_architecture(
        envelope=envelope,
        assumptions=assumptions,
        demand=demand,
    )
    optimal = result.conventional.optimal_candidate
    assert optimal.final_npv >= large.final_npv
    assert optimal.final_npv > small.final_npv
    assert optimal.capex > small.capex


def test_higher_capex_architecture_rejected_when_demand_is_too_low():
    assumptions = _assumptions_for_stage1()
    envelope = FacilityEnvelope(max_scanners=3, max_injection_resources=3, max_uptake_resources=3, max_mrt_endpoints=6)
    demand = OptimizationDemand(starting_demand_per_day=5.0)

    small = evaluate_architecture_candidate(
        pathway="Conventional",
        scanners=1,
        injection_resources=1,
        uptake_resources=1,
        endpoints=0,
        assumptions=assumptions,
        demand=demand,
    )
    large = evaluate_architecture_candidate(
        pathway="Conventional",
        scanners=3,
        injection_resources=3,
        uptake_resources=3,
        endpoints=0,
        assumptions=assumptions,
        demand=demand,
    )
    assert small is not None
    assert large is not None
    assert large.capex > small.capex
    assert large.final_npv < small.final_npv

    result = optimize_fixed_envelope_architecture(
        envelope=envelope,
        assumptions=assumptions,
        demand=demand,
    )
    optimal = result.conventional.optimal_candidate
    assert optimal.scanners == small.scanners
    assert optimal.injection_resources == small.injection_resources
    assert optimal.uptake_resources == small.uptake_resources


def test_mrt_endpoints_do_not_multiply_clinical_capacity_in_stage1():
    assumptions = _assumptions_for_stage1()
    demand = OptimizationDemand(starting_demand_per_day=500.0)

    low_endpoints = evaluate_architecture_candidate(
        pathway="MRT",
        scanners=2,
        injection_resources=2,
        uptake_resources=2,
        endpoints=1,
        assumptions=assumptions,
        demand=demand,
    )
    high_endpoints = evaluate_architecture_candidate(
        pathway="MRT",
        scanners=2,
        injection_resources=2,
        uptake_resources=2,
        endpoints=10,
        assumptions=assumptions,
        demand=demand,
    )

    assert low_endpoints is not None
    assert high_endpoints is not None
    assert math.isclose(
        low_endpoints.installed_capacity_per_day,
        high_endpoints.installed_capacity_per_day,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_mrt_base_and_endpoint_capex_are_charged():
    assumptions = _assumptions_for_stage1()
    demand = OptimizationDemand(starting_demand_per_day=100.0)

    candidate = evaluate_architecture_candidate(
        pathway="MRT",
        scanners=2,
        injection_resources=3,
        uptake_resources=4,
        endpoints=5,
        assumptions=assumptions,
        demand=demand,
    )

    assert candidate is not None
    expected_capex = (
        assumptions.mrt_infrastructure_capex
        + 2 * assumptions.scanner_capex
        + (3 + 4) * assumptions.additional_room_capex
        + 5 * assumptions.endpoint_capex
    )
    assert math.isclose(candidate.capex, expected_capex, rel_tol=0.0, abs_tol=1e-9)


def test_conventional_and_mrt_are_independently_optimized_not_forced_equal_capex():
    assumptions = _assumptions_for_stage1()
    envelope = FacilityEnvelope(max_scanners=4, max_injection_resources=4, max_uptake_resources=4, max_mrt_endpoints=6)
    demand = OptimizationDemand(starting_demand_per_day=220.0)

    result = optimize_fixed_envelope_architecture(
        envelope=envelope,
        assumptions=assumptions,
        demand=demand,
    )

    assert not math.isclose(
        result.conventional.optimal_candidate.capex,
        result.mrt.optimal_candidate.capex,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_incremental_npv_equals_difference_between_optimal_pathway_npvs():
    assumptions = _assumptions_for_stage1()
    envelope = FacilityEnvelope(max_scanners=4, max_injection_resources=4, max_uptake_resources=4, max_mrt_endpoints=6)
    demand = OptimizationDemand(starting_demand_per_day=220.0)

    result = optimize_fixed_envelope_architecture(
        envelope=envelope,
        assumptions=assumptions,
        demand=demand,
    )

    expected = result.mrt.optimal_candidate.final_npv - result.conventional.optimal_candidate.final_npv
    assert math.isclose(
        result.incremental_final_npv_mrt_minus_conventional,
        expected,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_existing_lifecycle_benchmark_behavior_remains_intact():
    common = {
        "revenue_per_scan": 2000.0,
        "operating_days_per_year": 300,
        "discount_rate_pct": 8.0,
        "analysis_years": 10,
        "starting_demand_per_day": 120.0,
        "annual_demand_growth_rate": 0.0,
    }

    conventional = evaluate_lifecycle_economics(
        initial_capex=20_000_000.0,
        installed_capacity_per_day=40.0,
        annual_opex=8_000_000.0,
        **common,
    )
    mrt = evaluate_lifecycle_economics(
        initial_capex=50_000_000.0,
        installed_capacity_per_day=100.0,
        annual_opex=20_000_000.0,
        **common,
    )

    assert math.isclose(conventional.final_npv, 87_361_302.38306308, rel_tol=0.0, abs_tol=1e-2)
    assert math.isclose(mrt.final_npv, 218_403_255.9576577, rel_tol=0.0, abs_tol=1e-2)

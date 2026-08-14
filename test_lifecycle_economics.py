from __future__ import annotations

import math

from lifecycle_economics import (
    build_demand_trajectory,
    compare_lifecycle_results,
    evaluate_lifecycle_economics,
)


def test_benchmark_constant_demand_npv_payback_and_crossover():
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
    comparison = compare_lifecycle_results(conventional=conventional, mrt=mrt)

    assert math.isclose(conventional.annual_rows[0].annual_net_cash_flow, 16_000_000.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(mrt.annual_rows[0].annual_net_cash_flow, 40_000_000.0, rel_tol=0.0, abs_tol=1e-9)

    assert math.isclose(conventional.final_npv, 87_361_302.38306308, rel_tol=0.0, abs_tol=1e-2)
    assert math.isclose(mrt.final_npv, 218_403_255.9576577, rel_tol=0.0, abs_tol=1e-2)
    assert math.isclose(
        comparison.incremental_final_npv_mrt_minus_conventional,
        131_041_953.57459462,
        rel_tol=0.0,
        abs_tol=1e-2,
    )

    assert comparison.conventional_payback_year is not None
    assert comparison.mrt_payback_year is not None
    assert comparison.economic_crossover_year is not None
    assert math.isclose(comparison.conventional_payback_year, 1.378, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(comparison.mrt_payback_year, 1.378, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(comparison.economic_crossover_year, 1.378, rel_tol=0.0, abs_tol=1e-6)


def test_explicit_demand_trajectory_takes_precedence_over_growth():
    trajectory = build_demand_trajectory(
        analysis_years=3,
        starting_demand_per_day=100.0,
        annual_growth_rate=0.5,
        explicit_daily_demand_by_year=[60.0, 70.0, 80.0],
    )
    assert trajectory.source == "explicit"
    assert trajectory.daily_demand_by_year == [60.0, 70.0, 80.0]

    result = evaluate_lifecycle_economics(
        initial_capex=0.0,
        installed_capacity_per_day=100.0,
        annual_opex=0.0,
        revenue_per_scan=1.0,
        operating_days_per_year=1,
        discount_rate_pct=0.0,
        analysis_years=3,
        starting_demand_per_day=100.0,
        annual_demand_growth_rate=0.5,
        explicit_daily_demand_by_year=[60.0, 70.0, 80.0],
    )
    assert [row.forecast_demand_per_day for row in result.annual_rows] == [60.0, 70.0, 80.0]


def test_generated_compound_growth_trajectory():
    trajectory = build_demand_trajectory(
        analysis_years=3,
        starting_demand_per_day=100.0,
        annual_growth_rate=0.1,
    )
    assert trajectory.source == "generated"
    assert math.isclose(trajectory.daily_demand_by_year[0], 100.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(trajectory.daily_demand_by_year[1], 110.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(trajectory.daily_demand_by_year[2], 121.0, rel_tol=0.0, abs_tol=1e-9)


def test_capacity_limited_and_demand_limited_years_and_unmet_demand_and_utilization():
    result = evaluate_lifecycle_economics(
        initial_capex=0.0,
        installed_capacity_per_day=100.0,
        annual_opex=0.0,
        revenue_per_scan=10.0,
        operating_days_per_year=1,
        discount_rate_pct=0.0,
        analysis_years=2,
        starting_demand_per_day=0.0,
        explicit_daily_demand_by_year=[120.0, 80.0],
    )

    year1 = result.annual_rows[0]
    assert math.isclose(year1.patients_served_per_day, 100.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year1.unmet_demand_per_day, 20.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year1.capacity_utilization_pct, 100.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year1.annual_revenue, 1000.0, rel_tol=0.0, abs_tol=1e-9)

    year2 = result.annual_rows[1]
    assert math.isclose(year2.patients_served_per_day, 80.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year2.unmet_demand_per_day, 0.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year2.capacity_utilization_pct, 80.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year2.annual_revenue, 800.0, rel_tol=0.0, abs_tol=1e-9)


def test_fractional_payback_interpolation():
    result = evaluate_lifecycle_economics(
        initial_capex=100.0,
        installed_capacity_per_day=60.0,
        annual_opex=0.0,
        revenue_per_scan=1.0,
        operating_days_per_year=1,
        discount_rate_pct=0.0,
        analysis_years=2,
        starting_demand_per_day=60.0,
    )
    # Net cash flow is 60 per year, so cumulative is -40 at year 1 and +20 at year 2.
    assert math.isclose(result.annual_rows[0].cumulative_npv, -40.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(result.annual_rows[1].cumulative_npv, 20.0, rel_tol=0.0, abs_tol=1e-9)
    assert result.payback_year is not None
    assert math.isclose(result.payback_year, 1.6666666666666667, rel_tol=0.0, abs_tol=1e-9)


def test_no_payback_case_returns_none():
    result = evaluate_lifecycle_economics(
        initial_capex=1_000.0,
        installed_capacity_per_day=1.0,
        annual_opex=900.0,
        revenue_per_scan=1.0,
        operating_days_per_year=300,
        discount_rate_pct=0.0,
        analysis_years=10,
        starting_demand_per_day=1.0,
    )
    assert result.payback_year is None


def test_zero_capacity_is_allowed_and_produces_zero_served_zero_revenue_and_no_payback():
    result = evaluate_lifecycle_economics(
        initial_capex=1_000.0,
        installed_capacity_per_day=0.0,
        annual_opex=900.0,
        revenue_per_scan=1.0,
        operating_days_per_year=300,
        discount_rate_pct=0.0,
        analysis_years=2,
        starting_demand_per_day=10.0,
    )

    year1 = result.annual_rows[0]
    year2 = result.annual_rows[1]

    assert math.isclose(year1.installed_capacity_per_day, 0.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year1.patients_served_per_day, 0.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year1.unmet_demand_per_day, 10.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year1.capacity_utilization_pct, 0.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year1.annual_revenue, 0.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year1.annual_net_cash_flow, -900.0, rel_tol=0.0, abs_tol=1e-9)

    assert math.isclose(year2.installed_capacity_per_day, 0.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year2.patients_served_per_day, 0.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year2.unmet_demand_per_day, 10.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year2.capacity_utilization_pct, 0.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(year2.annual_revenue, 0.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(result.final_npv, -2800.0, rel_tol=0.0, abs_tol=1e-9)
    assert result.payback_year is None


def test_crossover_interpolation():
    conventional = evaluate_lifecycle_economics(
        initial_capex=50.0,
        installed_capacity_per_day=30.0,
        annual_opex=0.0,
        revenue_per_scan=1.0,
        operating_days_per_year=1,
        discount_rate_pct=0.0,
        analysis_years=3,
        starting_demand_per_day=30.0,
    )
    mrt = evaluate_lifecycle_economics(
        initial_capex=100.0,
        installed_capacity_per_day=70.0,
        annual_opex=0.0,
        revenue_per_scan=1.0,
        operating_days_per_year=1,
        discount_rate_pct=0.0,
        analysis_years=3,
        starting_demand_per_day=70.0,
    )
    comparison = compare_lifecycle_results(conventional=conventional, mrt=mrt)

    assert comparison.economic_crossover_year is not None
    assert math.isclose(comparison.economic_crossover_year, 1.25, rel_tol=0.0, abs_tol=1e-9)


def test_no_crossover_case_returns_none():
    conventional = evaluate_lifecycle_economics(
        initial_capex=20.0,
        installed_capacity_per_day=10.0,
        annual_opex=0.0,
        revenue_per_scan=1.0,
        operating_days_per_year=1,
        discount_rate_pct=0.0,
        analysis_years=5,
        starting_demand_per_day=10.0,
    )
    mrt = evaluate_lifecycle_economics(
        initial_capex=100.0,
        installed_capacity_per_day=10.0,
        annual_opex=0.0,
        revenue_per_scan=1.0,
        operating_days_per_year=1,
        discount_rate_pct=0.0,
        analysis_years=5,
        starting_demand_per_day=10.0,
    )
    comparison = compare_lifecycle_results(conventional=conventional, mrt=mrt)
    assert comparison.economic_crossover_year is None

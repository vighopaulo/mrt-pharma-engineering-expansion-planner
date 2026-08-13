from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemandTrajectory:
    analysis_years: int
    daily_demand_by_year: list[float]
    source: str


@dataclass(frozen=True)
class AnnualLifecycleRow:
    year: int
    forecast_demand_per_day: float
    installed_capacity_per_day: float
    patients_served_per_day: float
    unmet_demand_per_day: float
    capacity_utilization_pct: float
    annual_revenue: float
    annual_opex: float
    annual_net_cash_flow: float
    discount_factor: float
    discounted_cash_flow: float
    cumulative_npv: float


@dataclass(frozen=True)
class LifecycleEconomicResult:
    initial_capex: float
    analysis_years: int
    discount_rate_pct: float
    annual_rows: list[AnnualLifecycleRow]
    final_npv: float
    payback_year: float | None


@dataclass(frozen=True)
class LifecycleComparisonResult:
    conventional: LifecycleEconomicResult
    mrt: LifecycleEconomicResult
    conventional_payback_year: float | None
    mrt_payback_year: float | None
    economic_crossover_year: float | None
    conventional_final_npv: float
    mrt_final_npv: float
    incremental_final_npv_mrt_minus_conventional: float


def build_demand_trajectory(
    *,
    analysis_years: int,
    starting_demand_per_day: float,
    annual_growth_rate: float,
    explicit_daily_demand_by_year: list[float] | None = None,
) -> DemandTrajectory:
    if analysis_years < 1:
        raise ValueError("analysis_years must be at least 1")

    if explicit_daily_demand_by_year is not None:
        if len(explicit_daily_demand_by_year) != analysis_years:
            raise ValueError("explicit_daily_demand_by_year length must equal analysis_years")
        daily = [float(v) for v in explicit_daily_demand_by_year]
        source = "explicit"
    else:
        start = float(starting_demand_per_day)
        growth = float(annual_growth_rate)
        daily = [start * ((1.0 + growth) ** year_index) for year_index in range(analysis_years)]
        source = "generated"

    if any(v < 0.0 for v in daily):
        raise ValueError("daily demand values must be non-negative")

    return DemandTrajectory(
        analysis_years=analysis_years,
        daily_demand_by_year=daily,
        source=source,
    )


def _interpolate_zero_crossing(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> float | None:
    if y0 == 0.0:
        return x0
    if y1 == 0.0:
        return x1
    if y0 < 0.0 <= y1:
        slope = y1 - y0
        if slope == 0.0:
            return None
        return x0 + (-y0) / slope
    return None


def _payback_year(initial_capex: float, annual_rows: list[AnnualLifecycleRow]) -> float | None:
    previous_year = 0.0
    previous_cumulative = -float(initial_capex)
    if previous_cumulative >= 0.0:
        return 0.0

    for row in annual_rows:
        candidate = _interpolate_zero_crossing(
            previous_year,
            previous_cumulative,
            float(row.year),
            row.cumulative_npv,
        )
        if candidate is not None:
            return candidate
        previous_year = float(row.year)
        previous_cumulative = row.cumulative_npv

    return None


def evaluate_lifecycle_economics(
    *,
    initial_capex: float,
    installed_capacity_per_day: float,
    annual_opex: float,
    revenue_per_scan: float,
    operating_days_per_year: int,
    discount_rate_pct: float,
    analysis_years: int,
    starting_demand_per_day: float,
    annual_demand_growth_rate: float = 0.0,
    explicit_daily_demand_by_year: list[float] | None = None,
) -> LifecycleEconomicResult:
    if analysis_years < 1:
        raise ValueError("analysis_years must be at least 1")
    if installed_capacity_per_day <= 0.0:
        raise ValueError("installed_capacity_per_day must be positive")
    if operating_days_per_year <= 0:
        raise ValueError("operating_days_per_year must be positive")

    demand = build_demand_trajectory(
        analysis_years=analysis_years,
        starting_demand_per_day=starting_demand_per_day,
        annual_growth_rate=annual_demand_growth_rate,
        explicit_daily_demand_by_year=explicit_daily_demand_by_year,
    )

    discount_rate = float(discount_rate_pct) / 100.0
    rows: list[AnnualLifecycleRow] = []
    cumulative_npv = -float(initial_capex)

    for year in range(1, analysis_years + 1):
        forecast = demand.daily_demand_by_year[year - 1]
        capacity = float(installed_capacity_per_day)
        served = min(forecast, capacity)
        unmet = max(0.0, forecast - capacity)
        utilization = 100.0 * served / capacity

        annual_revenue = served * float(revenue_per_scan) * float(operating_days_per_year)
        yearly_opex = float(annual_opex)
        annual_net_cash_flow = annual_revenue - yearly_opex

        discount_factor = 1.0 / ((1.0 + discount_rate) ** year)
        discounted_cash_flow = annual_net_cash_flow * discount_factor
        cumulative_npv += discounted_cash_flow

        rows.append(
            AnnualLifecycleRow(
                year=year,
                forecast_demand_per_day=forecast,
                installed_capacity_per_day=capacity,
                patients_served_per_day=served,
                unmet_demand_per_day=unmet,
                capacity_utilization_pct=utilization,
                annual_revenue=annual_revenue,
                annual_opex=yearly_opex,
                annual_net_cash_flow=annual_net_cash_flow,
                discount_factor=discount_factor,
                discounted_cash_flow=discounted_cash_flow,
                cumulative_npv=cumulative_npv,
            )
        )

    final_npv = rows[-1].cumulative_npv
    return LifecycleEconomicResult(
        initial_capex=float(initial_capex),
        analysis_years=analysis_years,
        discount_rate_pct=float(discount_rate_pct),
        annual_rows=rows,
        final_npv=final_npv,
        payback_year=_payback_year(float(initial_capex), rows),
    )


def _economic_crossover_year(
    conventional: LifecycleEconomicResult,
    mrt: LifecycleEconomicResult,
) -> float | None:
    if conventional.analysis_years != mrt.analysis_years:
        raise ValueError("conventional and mrt analysis_years must match")

    previous_year = 0.0
    previous_diff = (-mrt.initial_capex) - (-conventional.initial_capex)

    for year in range(1, conventional.analysis_years + 1):
        conv_cum = conventional.annual_rows[year - 1].cumulative_npv
        mrt_cum = mrt.annual_rows[year - 1].cumulative_npv
        diff = mrt_cum - conv_cum

        if previous_diff <= 0.0 and diff > 0.0:
            slope = diff - previous_diff
            if slope == 0.0:
                return None
            return previous_year + (-previous_diff) / slope

        previous_year = float(year)
        previous_diff = diff

    return None


def compare_lifecycle_results(
    *,
    conventional: LifecycleEconomicResult,
    mrt: LifecycleEconomicResult,
) -> LifecycleComparisonResult:
    crossover = _economic_crossover_year(conventional, mrt)
    return LifecycleComparisonResult(
        conventional=conventional,
        mrt=mrt,
        conventional_payback_year=conventional.payback_year,
        mrt_payback_year=mrt.payback_year,
        economic_crossover_year=crossover,
        conventional_final_npv=conventional.final_npv,
        mrt_final_npv=mrt.final_npv,
        incremental_final_npv_mrt_minus_conventional=mrt.final_npv - conventional.final_npv,
    )

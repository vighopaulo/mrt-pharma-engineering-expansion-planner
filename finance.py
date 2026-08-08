import math


def incremental_financials(
    capex: float,
    annual_incremental_opex: float,
    throughput_patients_per_day: float,
    revenue_per_scan: float,
    operating_days_per_year: int,
    discount_rate_pct: float,
    analysis_years: int,
) -> tuple[float, float, float, float, float, float]:
    annual_revenue = (
        throughput_patients_per_day
        * operating_days_per_year
        * revenue_per_scan
    )
    annual_net_cash_flow = annual_revenue - annual_incremental_opex
    rate = discount_rate_pct / 100.0
    npv = -capex + sum(
        annual_net_cash_flow / ((1.0 + rate) ** year)
        for year in range(1, analysis_years + 1)
    )
    roi_pct = (
        ((annual_net_cash_flow * analysis_years) - capex) / capex * 100.0
        if capex > 0
        else 0.0
    )
    payback_years = capex / annual_net_cash_flow if annual_net_cash_flow > 0 else math.inf
    return (
        annual_revenue,
        annual_incremental_opex,
        annual_net_cash_flow,
        npv,
        roi_pct,
        payback_years,
    )

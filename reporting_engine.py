from __future__ import annotations

from dataclasses import asdict
import io

import pandas as pd

from models import PlannerAssumptions, PlannerReport
from presentation import cumulative_roi_label, format_currency, format_hours_per_day, format_minutes, format_percent, format_years


ASSUMPTION_LABELS = {
    "mrt_infrastructure_capex": "MRT infrastructure cost",
    "cyclotron_purchase_capex": "Cyclotron purchase cost",
    "cyclotron_installation_capex": "Cyclotron installation cost",
    "additional_room_capex": "Additional room cost",
    "production_expansion_capex_per_10pct": "Conventional production expansion cost",
    "revenue_per_scan": "Revenue per scan",
    "discount_rate_pct": "Discount rate",
    "analysis_years": "Analysis period",
    "operating_days_per_year": "Operating days per year",
    "scanner_availability_pct": "Scanner availability",
    "scanner_cycle_min": "Scanner cycle time",
    "injection_cycle_min": "Injection-room cycle time",
    "uptake_cycle_min": "Uptake-room cycle time",
    "operating_hours_per_day": "Operating hours per day",
    "mrt_transport_default_min": "Default MRT delivery time",
    "scanner_capex": "Scanner cost",
    "endpoint_capex": "Endpoint cost",
    "guideway_segment_capex": "Guideway segment cost",
    "scanner_incremental_opex": "Scanner incremental operating cost",
    "room_incremental_opex": "Room incremental operating cost",
    "endpoint_incremental_opex": "Endpoint incremental operating cost",
    "guideway_incremental_opex": "Guideway incremental operating cost",
}


REPORT_SECTIONS = [
    "1 Executive Summary",
    "2 Existing Facility",
    "3 Requested Expansion",
    "4 Conventional Expansion",
    "5 MRT Expansion",
    "6 Capacity Comparison",
    "7 CapEx Comparison",
    "8 Cumulative ROI",
    "9 Payback",
    "10 Engineering Observations",
    "11 Assumptions",
    "12 Calculation Ledger",
]


def ledger_dataframe(report: PlannerReport) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for key, value in report.conventional.ledger.items():
        rows.append({"Section": "Conventional", "Metric": key, "Value": value})
    for key, value in report.mrt.ledger.items():
        rows.append({"Section": "MRT", "Metric": key, "Value": value})
    return pd.DataFrame(rows)


def comparison_dataframe(report: PlannerReport) -> pd.DataFrame:
    roi_column = cumulative_roi_label(report.assumptions.analysis_years)
    additional_mrt_annual_revenue = max(
        0.0,
        report.mrt.financials.annual_revenue - report.conventional.financials.annual_revenue,
    )
    return pd.DataFrame(
        [
            {
                "Option": "Conventional Expansion",
                "Current Patients/day": report.inputs.current_patients_per_day,
                "Requested Patients/day": report.inputs.target_patients_per_day,
                "Maximum Expected Demand/day": report.inputs.maximum_expected_demand_per_day,
                "CapEx": report.conventional.capex,
                "Revenue Throughput/day": report.conventional.revenue_generating_throughput_per_day,
                "Annual Revenue": report.conventional.financials.annual_revenue,
                "Capacity Achieved/day": report.conventional.achieved_capacity_per_day,
                "Reserve Capacity/day": report.conventional.reserve_capacity_per_day,
                "Retained Activity %": report.conventional.retained_activity_pct,
                "Conventional Production Expansion %": report.conventional.required_production_increase_pct,
                "MRT Production Expansion %": report.mrt.production_increase_pct,
                roi_column: report.conventional.financials.roi_pct,
                "Payback Years": report.conventional.financials.payback_years,
                "Additional MRT Annual Revenue": 0.0,
            },
            {
                "Option": "MRT-enabled Expansion",
                "Current Patients/day": report.inputs.current_patients_per_day,
                "Requested Patients/day": report.inputs.target_patients_per_day,
                "Maximum Expected Demand/day": report.inputs.maximum_expected_demand_per_day,
                "CapEx": report.mrt.capex,
                "Revenue Throughput/day": report.mrt.revenue_generating_throughput_per_day,
                "Annual Revenue": report.mrt.financials.annual_revenue,
                "Capacity Achieved/day": report.mrt.achieved_capacity_per_day,
                "Reserve Capacity/day": report.mrt.reserve_capacity_per_day,
                "Retained Activity %": report.mrt.retained_activity_pct,
                "Conventional Production Expansion %": report.conventional.required_production_increase_pct,
                "MRT Production Expansion %": report.mrt.production_increase_pct,
                roi_column: report.mrt.financials.roi_pct,
                "Payback Years": report.mrt.financials.payback_years,
                "Additional MRT Annual Revenue": additional_mrt_annual_revenue,
            },
        ]
    )


def capex_ledger_dataframe(report: PlannerReport) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for item in report.conventional.capex_ledger:
        rows.append(
            {
                "Pathway": "Conventional Expansion",
                "Component": item["component"],
                "Quantity": item["quantity"],
                "Unit Cost": item["unit_cost"],
                "Subtotal": item["subtotal"],
                "Basis": item["basis"],
                "Assumption Source": item["assumption_source"],
            }
        )
    for item in report.mrt.capex_ledger:
        rows.append(
            {
                "Pathway": "MRT-enabled Expansion",
                "Component": item["component"],
                "Quantity": item["quantity"],
                "Unit Cost": item["unit_cost"],
                "Subtotal": item["subtotal"],
                "Basis": item["basis"],
                "Assumption Source": item["assumption_source"],
            }
        )
    rows.append(
        {
            "Pathway": "Conventional Expansion",
            "Component": "Total",
            "Quantity": "",
            "Unit Cost": "",
            "Subtotal": report.conventional.capex,
            "Basis": "Sum of capex components",
            "Assumption Source": "ConventionalPlan.capex",
        }
    )
    rows.append(
        {
            "Pathway": "MRT-enabled Expansion",
            "Component": "Total",
            "Quantity": "",
            "Unit Cost": "",
            "Subtotal": report.mrt.capex,
            "Basis": "Sum of capex components",
            "Assumption Source": "MRTPlan.capex",
        }
    )
    return pd.DataFrame(rows)


def assumptions_dataframe(assumptions: PlannerAssumptions) -> pd.DataFrame:
    standard = PlannerAssumptions()
    currency_keys = {
        "mrt_infrastructure_capex",
        "cyclotron_purchase_capex",
        "cyclotron_installation_capex",
        "additional_room_capex",
        "production_expansion_capex_per_10pct",
        "revenue_per_scan",
        "scanner_capex",
        "endpoint_capex",
        "guideway_segment_capex",
        "scanner_incremental_opex",
        "room_incremental_opex",
        "endpoint_incremental_opex",
        "guideway_incremental_opex",
    }
    percent_keys = {"discount_rate_pct", "scanner_availability_pct"}
    minute_keys = {
        "scanner_cycle_min",
        "injection_cycle_min",
        "uptake_cycle_min",
        "mrt_transport_default_min",
    }
    hours_keys = {"operating_hours_per_day"}
    year_keys = {"analysis_years"}
    day_keys = {"operating_days_per_year"}

    def format_value(key: str, value: float | int) -> str:
        if key in currency_keys:
            return format_currency(float(value))
        if key in percent_keys:
            return format_percent(float(value))
        if key in minute_keys:
            return format_minutes(float(value))
        if key in hours_keys:
            return format_hours_per_day(float(value))
        if key in year_keys:
            return format_years(float(value))
        if key in day_keys:
            return f"{int(value)} days"
        return str(value)

    rows: list[dict[str, object]] = []
    for key, applied in asdict(assumptions).items():
        baseline = asdict(standard)[key]
        status = "Standard assumption" if applied == baseline else "User-adjusted assumption"
        rows.append(
            {
                "Assumption": ASSUMPTION_LABELS.get(key, key),
                "Applied Value": format_value(key, applied),
                "Standard Value": format_value(key, baseline),
                "Status": status,
            }
        )
    return pd.DataFrame(rows)


def excel_bytes(report: PlannerReport) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        comparison_dataframe(report).to_excel(writer, index=False, sheet_name="Comparison")
        capex_ledger_dataframe(report).to_excel(writer, index=False, sheet_name="CapEx Ledger")
        assumptions_dataframe(report.assumptions).to_excel(writer, index=False, sheet_name="Assumptions")
        ledger_dataframe(report).to_excel(writer, index=False, sheet_name="Calculation Ledger")
    return buffer.getvalue()

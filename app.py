from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from diagnostics import load_radionuclide_half_lives, resolve_half_life_min, validate
from models import PlannerInputs, PlannerReport
from optimization import conventional, mrt
from presentation import (
    cumulative_roi_label,
    format_count,
    format_currency,
    format_minutes,
    format_patients_per_day,
    format_percent,
    format_years,
)
from reporting_engine import REPORT_SECTIONS, assumptions_dataframe, capex_ledger_dataframe, comparison_dataframe, excel_bytes, ledger_dataframe
from ui_logic import (
    MRT_DEFAULT_DELIVERY_SECONDS,
    assumptions_from_values,
    changed_assumption_labels,
    default_assumption_values,
    seconds_to_minutes,
    validate_assumptions,
)
def _right_align_financial(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    return df.style.set_properties(subset=df.columns[1:], **{"text-align": "right"})


def _neutral_summary(conventional_plan, mrt_plan) -> str:
    statements: list[str] = []
    if conventional_plan.capex < mrt_plan.capex:
        statements.append("conventional expansion has the lower initial capital cost")
    elif mrt_plan.capex < conventional_plan.capex:
        statements.append("MRT-enabled expansion has the lower initial capital cost")
    else:
        statements.append("both options have similar initial capital cost")

    if mrt_plan.reserve_capacity_per_day > conventional_plan.reserve_capacity_per_day:
        statements.append("MRT provides greater reserve capacity")
    elif conventional_plan.reserve_capacity_per_day > mrt_plan.reserve_capacity_per_day:
        statements.append("conventional expansion provides greater reserve capacity")

    if mrt_plan.retained_activity_pct > conventional_plan.retained_activity_pct:
        statements.append("MRT provides greater retained activity")
    elif conventional_plan.retained_activity_pct > mrt_plan.retained_activity_pct:
        statements.append("conventional delivery provides greater retained activity")

    if mrt_plan.financials.payback_years < conventional_plan.financials.payback_years:
        statements.append("MRT has the shorter estimated payback")
    elif conventional_plan.financials.payback_years < mrt_plan.financials.payback_years:
        statements.append("conventional expansion has the shorter estimated payback")

    return "For this project, " + ", while ".join(statements) + "."


def _capex_ledger_total(plan) -> float:
    return float(sum(float(item["subtotal"]) for item in plan.capex_ledger))


st.set_page_config(page_title="MRT Pharma Expansion Planner", page_icon="M", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=IBM+Plex+Serif:wght@500;600&display=swap');
    .stApp {
        background: radial-gradient(circle at 0% 0%, #f2f6fb 0%, #e9eff7 45%, #dde8f3 100%);
    }
    .block-container {
        max-width: 1240px;
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        font-family: 'Source Sans 3', sans-serif;
    }
    .app-header {
        background: white;
        border: 1px solid #d3deeb;
        border-radius: 16px;
        padding: 16px 18px;
        box-shadow: 0 10px 24px rgba(26, 52, 81, 0.08);
        margin-bottom: 12px;
    }
    .title {
        font-family: 'IBM Plex Serif', serif;
        color: #173f6b;
        font-size: 2rem;
        margin: 0;
    }
    .stage-pill {
        border: 1px solid #d0dceb;
        border-radius: 999px;
        background: #f3f8fc;
        color: #173f6b;
        text-align: center;
        font-weight: 600;
        padding: 8px 10px;
        font-size: 0.92rem;
    }
    .stage-current {
        border-color: #1f6fb5;
        background: #e6f1fb;
    }
    .card {
        background: white;
        border: 1px solid #d3deeb;
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 12px;
        box-shadow: 0 6px 18px rgba(26, 52, 81, 0.06);
    }
    .card-title {
        color: #173f6b;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .result-card {
        background: white;
        border: 1px solid #bfd5eb;
        border-radius: 14px;
        padding: 12px;
    }
    .result-value {
        font-size: 1.3rem;
        font-weight: 700;
        color: #173f6b;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

half_life_lookup = load_radionuclide_half_lives()

if "assumption_values" not in st.session_state:
    st.session_state.assumption_values = default_assumption_values()
if "maximum_expected_demand_per_day" not in st.session_state:
    st.session_state.maximum_expected_demand_per_day = 180.0

st.markdown("<div class='app-header'>", unsafe_allow_html=True)
st.markdown("<h1 class='title'>MRT Pharma Engineering Expansion Planner</h1>", unsafe_allow_html=True)
st.markdown("A planning application to compare conventional expansion and MRT-enabled expansion for facility growth.")

st.markdown("Progress indicator (read-only)")
p1, p2, p3, p4, p5 = st.columns(5)
p1.markdown("<div class='stage-pill'>1. Project</div>", unsafe_allow_html=True)
p2.markdown("<div class='stage-pill'>2. Current Facility</div>", unsafe_allow_html=True)
p3.markdown("<div class='stage-pill'>3. Expansion Goal</div>", unsafe_allow_html=True)
p4.markdown("<div class='stage-pill stage-current'>4. Compare Options</div>", unsafe_allow_html=True)
p5.markdown("<div class='stage-pill'>5. Results</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("<div class='card-title'>Project Details</div>", unsafe_allow_html=True)
project_name = st.text_input("Project name", value="MRT Expansion Study")
st.markdown("</div>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Current Demand</div>", unsafe_allow_html=True)
    current_patients = st.number_input("Current patients each day", min_value=0.0, value=100.0, step=5.0)
    target_patients = st.number_input("Target patients each day", min_value=1.0, value=180.0, step=5.0)
    if st.session_state.maximum_expected_demand_per_day <= 0:
        st.session_state.maximum_expected_demand_per_day = float(target_patients)
    maximum_expected_demand = st.number_input(
        "Maximum expected patient demand per day",
        min_value=1.0,
        value=float(st.session_state.maximum_expected_demand_per_day),
        step=5.0,
    )
    st.session_state.maximum_expected_demand_per_day = float(maximum_expected_demand)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Transport</div>", unsafe_allow_html=True)
    current_transport = st.number_input("Current average dose-delivery time", min_value=0.0, value=20.0, step=1.0)
    st.caption("Unit: minutes")
    mrt_transport_seconds = st.number_input(
        "Estimated MRT delivery time",
        min_value=1.0,
        value=float(MRT_DEFAULT_DELIVERY_SECONDS),
        step=1.0,
    )
    st.caption("Unit: seconds")
    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Current Capacity</div>", unsafe_allow_html=True)
    current_scanners = st.number_input("Current scanners", min_value=0, value=3, step=1)
    current_injection_rooms = st.number_input("Current injection rooms", min_value=0, value=6, step=1)
    current_uptake_rooms = st.number_input("Current uptake rooms", min_value=0, value=6, step=1)
    current_usable_doses = st.number_input("Usable doses available each day", min_value=1.0, value=120.0, step=5.0)
    has_existing_cyclotron = st.checkbox("Existing cyclotron", value=True)
    existing_connectable_rooms = st.number_input("Existing rooms that MRT could serve", min_value=0, value=2, step=1)
    st.caption("Rooms that could receive radiopharmaceuticals through the proposed MRT network.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Expansion Goal</div>", unsafe_allow_html=True)
    radionuclide = st.selectbox("Representative radionuclide", [""] + sorted(half_life_lookup.keys()))
    half_life_override = st.number_input("Representative half-life", min_value=0.0, value=0.0, step=0.1)
    st.caption("Unit: minutes. Optional if radionuclide is selected.")
    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Customize assumptions", expanded=False):
    st.write("The planner provides standard starting assumptions. Change them only when project-specific information is available.")

    if st.button("Restore standard defaults", use_container_width=False):
        st.session_state.assumption_values = default_assumption_values()

    vals = dict(st.session_state.assumption_values)

    st.markdown("Financial assumptions")
    a1, a2 = st.columns(2)
    with a1:
        vals["mrt_infrastructure_capex"] = st.number_input("MRT infrastructure cost (USD)", min_value=0.0, value=float(vals["mrt_infrastructure_capex"]), step=50_000.0, format="%.0f")
        vals["cyclotron_purchase_capex"] = st.number_input("Cyclotron purchase cost (USD)", min_value=0.0, value=float(vals["cyclotron_purchase_capex"]), step=50_000.0, format="%.0f")
        vals["cyclotron_installation_capex"] = st.number_input("Cyclotron installation cost (USD)", min_value=0.0, value=float(vals["cyclotron_installation_capex"]), step=50_000.0, format="%.0f")
        vals["additional_room_capex"] = st.number_input("Additional room cost (USD per room)", min_value=0.0, value=float(vals["additional_room_capex"]), step=5_000.0, format="%.0f")
    with a2:
        vals["production_expansion_capex_per_10pct"] = st.number_input("Conventional production expansion cost (USD per 10% increment)", min_value=0.0, value=float(vals["production_expansion_capex_per_10pct"]), step=10_000.0, format="%.0f")
        vals["revenue_per_scan"] = st.number_input("Revenue per scan (USD)", min_value=0.0, value=float(vals["revenue_per_scan"]), step=10.0, format="%.0f")
        vals["discount_rate_pct"] = st.number_input("Discount rate (%)", min_value=0.0, max_value=100.0, value=float(vals["discount_rate_pct"]), step=0.5)
        vals["analysis_years"] = st.number_input("Analysis period (years)", min_value=1.0, max_value=50.0, value=float(vals["analysis_years"]), step=1.0)
        vals["operating_days_per_year"] = st.number_input("Operating days per year", min_value=1.0, max_value=366.0, value=float(vals["operating_days_per_year"]), step=1.0)

    st.markdown("Capacity assumptions")
    b1, b2 = st.columns(2)
    with b1:
        vals["scanner_availability_pct"] = st.number_input("Scanner availability (%)", min_value=1.0, max_value=100.0, value=float(vals["scanner_availability_pct"]), step=1.0)
        vals["scanner_cycle_min"] = st.number_input("Scanner cycle time (minutes)", min_value=1.0, value=float(vals["scanner_cycle_min"]), step=1.0)
    with b2:
        vals["injection_cycle_min"] = st.number_input("Injection-room cycle time (minutes)", min_value=1.0, value=float(vals["injection_cycle_min"]), step=1.0)
        vals["uptake_cycle_min"] = st.number_input("Uptake-room cycle time (minutes)", min_value=1.0, value=float(vals["uptake_cycle_min"]), step=1.0)

    st.session_state.assumption_values = vals
    changed = changed_assumption_labels(vals)
    if changed:
        st.info(f"{len(changed)} assumption(s) adjusted from the standard defaults.")
        st.dataframe(
            pd.DataFrame({"Adjusted assumption": changed}),
            hide_index=True,
            use_container_width=True,
        )

assumption_issues = validate_assumptions(st.session_state.assumption_values)
for issue in assumption_issues:
    st.error(issue)

compare = st.button("Compare Expansion Options", type="primary", use_container_width=True, disabled=bool(assumption_issues))

if compare:
    assumptions = assumptions_from_values(st.session_state.assumption_values)

    inputs = PlannerInputs(
        project_name=project_name,
        current_patients_per_day=current_patients,
        target_patients_per_day=target_patients,
        maximum_expected_demand_per_day=maximum_expected_demand,
        current_scanners=int(current_scanners),
        current_injection_rooms=int(current_injection_rooms),
        current_uptake_rooms=int(current_uptake_rooms),
        has_existing_cyclotron=has_existing_cyclotron,
        current_usable_doses_per_day=current_usable_doses,
        current_average_transport_min=current_transport,
        mrt_transport_min=seconds_to_minutes(mrt_transport_seconds),
        existing_mrt_connectable_rooms=int(existing_connectable_rooms),
        representative_radionuclide=radionuclide if radionuclide else None,
        representative_half_life_min=float(half_life_override) if half_life_override > 0 else None,
    )

    issues = validate(inputs, half_life_lookup)
    if issues:
        for issue in issues:
            st.error(issue)
        st.stop()

    half_life_min = resolve_half_life_min(inputs, half_life_lookup)
    conventional_plan = conventional(inputs, assumptions, half_life_min)
    mrt_plan = mrt(inputs, assumptions, half_life_min)

    report = PlannerReport(
        project_name=project_name,
        inputs=inputs,
        assumptions=assumptions,
        conventional=conventional_plan,
        mrt=mrt_plan,
    )

    st.markdown("## Results")
    st.write(_neutral_summary(conventional_plan, mrt_plan))
    st.caption("Conventional: Deterministic expansion of the current operating footprint, adjusted upward where necessary to physically meet the requested target.")
    st.caption("MRT: Minimum-cost feasible MRT configuration that satisfies the requested target under modeled resource constraints.")

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Requested target capacity", format_patients_per_day(inputs.target_patients_per_day))
    k2.metric("Conventional achieved capacity", format_patients_per_day(conventional_plan.achieved_capacity_per_day))
    k3.metric("Conventional reserve capacity", format_patients_per_day(conventional_plan.reserve_capacity_per_day))
    k4.metric("MRT achieved capacity", format_patients_per_day(mrt_plan.achieved_capacity_per_day))
    k5.metric("MRT reserve capacity", format_patients_per_day(mrt_plan.reserve_capacity_per_day))

    r1, r2, r3 = st.columns(3)
    additional_mrt_revenue = max(0.0, mrt_plan.financials.annual_revenue - conventional_plan.financials.annual_revenue)
    r1.metric("Conventional annual revenue", format_currency(conventional_plan.financials.annual_revenue))
    r2.metric("MRT annual revenue", format_currency(mrt_plan.financials.annual_revenue))
    r3.metric("Additional MRT annual revenue", format_currency(additional_mrt_revenue))

    cconv, cmrt = st.columns(2)
    with cconv:
        st.markdown("<div class='result-card'>", unsafe_allow_html=True)
        st.markdown("#### Conventional expansion")
        st.markdown(f"<div class='result-value'>{format_currency(conventional_plan.capex)}</div>", unsafe_allow_html=True)
        st.write("Initial CapEx")
        st.write("Revenue-generating throughput")
        st.write(format_patients_per_day(conventional_plan.revenue_generating_throughput_per_day))
        st.write("Annual revenue")
        st.write(format_currency(conventional_plan.financials.annual_revenue))
        st.write(cumulative_roi_label(assumptions.analysis_years))
        st.write(format_percent(conventional_plan.financials.roi_pct))
        st.write("Payback")
        st.write("Not achieved" if math.isinf(conventional_plan.financials.payback_years) else format_years(conventional_plan.financials.payback_years))
        st.markdown("</div>", unsafe_allow_html=True)

    with cmrt:
        st.markdown("<div class='result-card'>", unsafe_allow_html=True)
        st.markdown("#### MRT-enabled expansion")
        st.markdown(f"<div class='result-value'>{format_currency(mrt_plan.capex)}</div>", unsafe_allow_html=True)
        st.write("Initial CapEx")
        st.write("Revenue-generating throughput")
        st.write(format_patients_per_day(mrt_plan.revenue_generating_throughput_per_day))
        st.write("Annual revenue")
        st.write(format_currency(mrt_plan.financials.annual_revenue))
        st.write(cumulative_roi_label(assumptions.analysis_years))
        st.write(format_percent(mrt_plan.financials.roi_pct))
        st.write("Payback")
        st.write("Not achieved" if math.isinf(mrt_plan.financials.payback_years) else format_years(mrt_plan.financials.payback_years))
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("## Detailed Report")
    for section_name in REPORT_SECTIONS:
        st.markdown(f"### {section_name}")

        if section_name == "1 Executive Summary":
            st.write(_neutral_summary(conventional_plan, mrt_plan))
        elif section_name == "2 Existing Facility":
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Item": "Current patients", "Value": format_patients_per_day(inputs.current_patients_per_day)},
                        {"Item": "Current scanners", "Value": format_count(inputs.current_scanners, "scanners")},
                        {"Item": "Current injection rooms", "Value": format_count(inputs.current_injection_rooms, "injection rooms")},
                        {"Item": "Current uptake rooms", "Value": format_count(inputs.current_uptake_rooms, "uptake rooms")},
                        {"Item": "Existing cyclotron", "Value": "Yes" if inputs.has_existing_cyclotron else "No"},
                        {"Item": "Usable doses available each day", "Value": format_patients_per_day(inputs.current_usable_doses_per_day)},
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        elif section_name == "3 Requested Expansion":
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Item": "Target patients", "Value": format_patients_per_day(inputs.target_patients_per_day)},
                        {"Item": "Maximum expected demand", "Value": format_patients_per_day(inputs.maximum_expected_demand_per_day)},
                        {"Item": "Incremental patients", "Value": format_patients_per_day(inputs.incremental_patients_per_day())},
                        {"Item": "Current average dose-delivery time", "Value": format_minutes(inputs.current_average_transport_min)},
                        {"Item": "Estimated MRT delivery time", "Value": format_minutes(seconds_to_minutes(mrt_transport_seconds))},
                        {"Item": "Representative half-life", "Value": format_minutes(half_life_min)},
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        elif section_name == "4 Conventional Expansion":
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Item": "Capacity increase", "Value": format_percent(conventional_plan.capacity_increase_pct)},
                        {"Item": "Required production increase", "Value": format_percent(conventional_plan.required_production_increase_pct)},
                        {"Item": "Proportional scanner estimate", "Value": format_count(int(conventional_plan.ledger.get("proportional_scanner_estimate", 0)), "scanners")},
                        {"Item": "Physically feasible scanner requirement", "Value": format_count(int(conventional_plan.ledger.get("required_total_scanners", 0)), "scanners")},
                        {"Item": "Scanner capacity", "Value": format_patients_per_day(float(conventional_plan.ledger.get("scanner_capacity_patients_per_day", 0.0)))},
                        {"Item": "Additional scanners", "Value": format_count(conventional_plan.additional_scanners, "scanners")},
                        {"Item": "Proportional injection-room estimate", "Value": format_count(int(conventional_plan.ledger.get("proportional_injection_room_estimate", 0)), "injection rooms")},
                        {"Item": "Physically feasible injection-room requirement", "Value": format_count(int(conventional_plan.ledger.get("required_total_injection_rooms", 0)), "injection rooms")},
                        {"Item": "Injection-room capacity", "Value": format_patients_per_day(float(conventional_plan.ledger.get("injection_capacity_patients_per_day", 0.0)))},
                        {"Item": "Additional injection rooms", "Value": format_count(conventional_plan.additional_injection_rooms, "injection rooms")},
                        {"Item": "Proportional uptake-room estimate", "Value": format_count(int(conventional_plan.ledger.get("proportional_uptake_room_estimate", 0)), "uptake rooms")},
                        {"Item": "Physically feasible uptake-room requirement", "Value": format_count(int(conventional_plan.ledger.get("required_total_uptake_rooms", 0)), "uptake rooms")},
                        {"Item": "Uptake-room capacity", "Value": format_patients_per_day(float(conventional_plan.ledger.get("uptake_capacity_patients_per_day", 0.0)))},
                        {"Item": "Additional uptake rooms", "Value": format_count(conventional_plan.additional_uptake_rooms, "uptake rooms")},
                        {"Item": "Additional rooms", "Value": format_count(conventional_plan.additional_injection_rooms + conventional_plan.additional_uptake_rooms, "rooms")},
                        {"Item": "Cyclotron required", "Value": "Yes" if conventional_plan.cyclotron_required else "No"},
                        {"Item": "Conventional initial CapEx", "Value": format_currency(conventional_plan.capex)},
                        {"Item": "Capacity achieved", "Value": format_patients_per_day(conventional_plan.achieved_capacity_per_day)},
                        {"Item": "Reserve capacity", "Value": format_patients_per_day(conventional_plan.reserve_capacity_per_day)},
                        {"Item": "Revenue-generating throughput", "Value": format_patients_per_day(conventional_plan.revenue_generating_throughput_per_day)},
                        {"Item": "Annual revenue", "Value": format_currency(conventional_plan.financials.annual_revenue)},
                        {"Item": "Retained activity", "Value": format_percent(conventional_plan.retained_activity_pct)},
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        elif section_name == "5 MRT Expansion":
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Item": "Minimum guideway segments", "Value": format_count(mrt_plan.guideway_segments, "segments")},
                        {"Item": "Minimum endpoints", "Value": format_count(mrt_plan.endpoints, "endpoints")},
                        {"Item": "Minimum required rooms", "Value": format_count(mrt_plan.new_mrt_rooms, "rooms")},
                        {"Item": "Minimum scanners", "Value": format_count(mrt_plan.additional_scanners, "scanners")},
                        {"Item": "Minimum infrastructure", "Value": format_count(mrt_plan.infrastructure_units, "units")},
                        {"Item": "MRT initial CapEx", "Value": format_currency(mrt_plan.capex)},
                        {"Item": "Capacity achieved", "Value": format_patients_per_day(mrt_plan.achieved_capacity_per_day)},
                        {"Item": "Reserve capacity", "Value": format_patients_per_day(mrt_plan.reserve_capacity_per_day)},
                        {"Item": "Revenue-generating throughput", "Value": format_patients_per_day(mrt_plan.revenue_generating_throughput_per_day)},
                        {"Item": "Annual revenue", "Value": format_currency(mrt_plan.financials.annual_revenue)},
                        {"Item": "Retained activity", "Value": format_percent(mrt_plan.retained_activity_pct)},
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        elif section_name == "6 Capacity Comparison":
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Option": "Conventional Expansion",
                            "Requested target": format_patients_per_day(inputs.target_patients_per_day),
                            "Capacity achieved": format_patients_per_day(conventional_plan.achieved_capacity_per_day),
                            "Reserve capacity": format_patients_per_day(conventional_plan.reserve_capacity_per_day),
                        },
                        {
                            "Option": "MRT-enabled Expansion",
                            "Requested target": format_patients_per_day(inputs.target_patients_per_day),
                            "Capacity achieved": format_patients_per_day(mrt_plan.achieved_capacity_per_day),
                            "Reserve capacity": format_patients_per_day(mrt_plan.reserve_capacity_per_day),
                        },
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        elif section_name == "7 CapEx Comparison":
            capex_df = pd.DataFrame(
                [
                    {"Option": "Conventional Expansion", "Initial CapEx": format_currency(conventional_plan.capex)},
                    {"Option": "MRT-enabled Expansion", "Initial CapEx": format_currency(mrt_plan.capex)},
                ]
            )
            st.dataframe(_right_align_financial(capex_df), hide_index=True, use_container_width=True)
        elif section_name == "8 Cumulative ROI":
            roi_df = pd.DataFrame(
                [
                    {"Option": "Conventional Expansion", cumulative_roi_label(assumptions.analysis_years): format_percent(conventional_plan.financials.roi_pct)},
                    {"Option": "MRT-enabled Expansion", cumulative_roi_label(assumptions.analysis_years): format_percent(mrt_plan.financials.roi_pct)},
                ]
            )
            st.dataframe(_right_align_financial(roi_df), hide_index=True, use_container_width=True)
        elif section_name == "9 Payback":
            payback_df = pd.DataFrame(
                [
                    {
                        "Option": "Conventional Expansion",
                        "Payback": "Not achieved"
                        if math.isinf(conventional_plan.financials.payback_years)
                        else format_years(conventional_plan.financials.payback_years),
                    },
                    {
                        "Option": "MRT-enabled Expansion",
                        "Payback": "Not achieved"
                        if math.isinf(mrt_plan.financials.payback_years)
                        else format_years(mrt_plan.financials.payback_years),
                    },
                ]
            )
            st.dataframe(_right_align_financial(payback_df), hide_index=True, use_container_width=True)
        elif section_name == "10 Engineering Observations":
            st.markdown(
                "- Conventional expansion provides linear scaling from current operations.\n"
                "- Conventional resources are deterministically increased when needed to physically meet the target capacity.\n"
                "- MRT-enabled expansion is selected from feasible configurations using constrained optimization.\n"
                "- MRT revenue uses demand-capped throughput (minimum of feasible capacity and maximum expected demand).\n"
                "- Base operating expenditure is assumed equal; the comparison uses incremental engineering costs."
            )
        elif section_name == "11 Assumptions":
            st.dataframe(assumptions_dataframe(report.assumptions), hide_index=True, use_container_width=True)
        elif section_name == "12 Calculation Ledger":
            st.dataframe(ledger_dataframe(report), hide_index=True, use_container_width=True)

    st.markdown("### CapEx Component Ledger")
    capex_components = capex_ledger_dataframe(report)
    st.dataframe(capex_components, hide_index=True, use_container_width=True)

    total_check = pd.DataFrame(
        [
            {
                "Pathway": "Conventional Expansion",
                "CapEx from Plan": format_currency(conventional_plan.capex),
                "CapEx from Ledger": format_currency(_capex_ledger_total(conventional_plan)),
            },
            {
                "Pathway": "MRT-enabled Expansion",
                "CapEx from Plan": format_currency(mrt_plan.capex),
                "CapEx from Ledger": format_currency(_capex_ledger_total(mrt_plan)),
            },
        ]
    )
    st.dataframe(total_check, hide_index=True, use_container_width=True)

    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "Download comparison CSV",
            data=comparison_dataframe(report).to_csv(index=False).encode("utf-8"),
            file_name="engineering_expansion_comparison.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            "Download engineering report (Excel)",
            data=excel_bytes(report),
            file_name="engineering_expansion_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

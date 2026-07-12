from __future__ import annotations

import io
from dataclasses import asdict
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from model import Candidate, ModelInputs, optimize


st.set_page_config(
    page_title="MRT Pharma™ Digital Twin",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# APP-LIKE BRANDING AND UI
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --red: #d71920;
        --red2: #ff4249;
        --black: #111111;
        --ink: #252832;
        --line: #e2e3e7;
        --soft: #f6f7f9;
        --green: #269b4a;
        --green-soft: #eaf8ee;
    }

    [data-testid="stHeader"] {
        background: rgba(255,255,255,.88);
        backdrop-filter: blur(10px);
    }

    .stApp {
        background:
            radial-gradient(circle at top right, #fff2f2 0, transparent 35%),
            linear-gradient(180deg, #ffffff 0%, #f7f8fa 100%);
        color: var(--ink);
    }

    .block-container {
        max-width: 1280px;
        padding-top: 2.5rem !important;
        padding-bottom: 3rem;
    }

    .brand-shell {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 24px;
        padding: 24px 28px 20px;
        margin-bottom: 16px;
        box-shadow: 0 16px 40px rgba(20,24,35,.08);
    }

    .brand-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 30px;
        flex-wrap: wrap;
    }

    .brand-name {
        white-space: nowrap;
        font-size: 2.6rem;
        line-height: 1.05;
        font-weight: 950;
        letter-spacing: -1.3px;
    }

    .brand-mrt { color: var(--black); }
    .brand-pharma { color: var(--red); }

    .trademark {
        position: relative;
        top: -.85em;
        margin-left: 2px;
        font-size: .32em;
        font-weight: 900;
        color: var(--red);
    }

    .product-name {
        margin-top: 8px;
        font-size: 1.45rem;
        font-weight: 900;
        color: var(--black);
    }

    .tagline {
        text-align: right;
        font-size: 1.02rem;
        font-weight: 900;
        color: var(--black);
    }

    .subtagline {
        max-width: 620px;
        margin-top: 6px;
        text-align: right;
        color: #666b75;
        font-size: .9rem;
        line-height: 1.5;
    }

    .red-rule {
        height: 6px;
        margin-top: 17px;
        border-radius: 999px;
        background: linear-gradient(90deg,var(--red),var(--red2));
    }

    .section-shell {
        background: rgba(255,255,255,.94);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 20px 22px 8px;
        margin-bottom: 14px;
        box-shadow: 0 10px 30px rgba(20,24,35,.055);
    }

    .section-label {
        display: inline-block;
        margin-bottom: 4px;
        padding: 4px 9px;
        border-radius: 999px;
        background: #111;
        color: #fff;
        font-size: .72rem;
        font-weight: 900;
        letter-spacing: .5px;
    }

    .section-title {
        margin: 3px 0 15px;
        font-size: 1.45rem;
        font-weight: 950;
        color: var(--ink);
    }

    .helper {
        margin: -4px 0 15px;
        color: #6a6e78;
        font-size: .86rem;
    }

    div[data-testid="stNumberInput"] label {
        font-weight: 750;
        color: #292d36;
    }

    div[data-testid="stFormSubmitButton"] > button {
        min-height: 3.15rem;
        width: 100%;
        border: none;
        border-radius: 14px;
        background: linear-gradient(90deg,#a80f15,var(--red));
        color: white;
        font-size: .98rem;
        font-weight: 950;
        box-shadow: 0 9px 24px rgba(215,25,32,.20);
    }

    div[data-testid="stFormSubmitButton"] > button:hover {
        background: linear-gradient(90deg,#8f0c12,#bd141b);
        color: white;
    }

    .results-heading {
        margin: 30px 0 14px;
        font-size: 1.75rem;
        font-weight: 950;
        color: var(--ink);
    }

    .result-card {
        min-height: 260px;
        padding: 21px;
        border: 1px solid var(--line);
        border-top: 7px solid var(--red);
        border-radius: 22px;
        background: linear-gradient(145deg,#ffffff,#f6f7f9);
        box-shadow: 0 14px 34px rgba(20,24,35,.075);
    }

    .winner-card {
        border: 2px solid var(--green);
        border-top: 8px solid var(--green);
        background: linear-gradient(145deg,#f5fff7,var(--green-soft));
        box-shadow: 0 16px 38px rgba(38,155,74,.18);
    }

    .option-title {
        font-size: 1.08rem;
        font-weight: 950;
        color: var(--ink);
    }

    .option-subtitle {
        margin-top: 3px;
        color: #727680;
        font-size: .83rem;
    }

    .winner-badge {
        display: inline-block;
        margin-top: 10px;
        padding: 5px 11px;
        border-radius: 999px;
        background: var(--green);
        color: #fff;
        font-size: .78rem;
        font-weight: 950;
        letter-spacing: .35px;
    }

    .hero-value {
        margin-top: 14px;
        font-size: 1.72rem;
        font-weight: 950;
        color: #111;
        letter-spacing: -.6px;
    }

    .metric-line {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        margin-top: 9px;
        padding-top: 9px;
        border-top: 1px solid rgba(0,0,0,.07);
        font-size: .91rem;
    }

    .metric-label { color: #696e77; }
    .metric-value { font-weight: 900; color: #22252d; }

    .decision-strip {
        margin: 16px 0 12px;
        padding: 18px 22px;
        border-radius: 18px;
        background: linear-gradient(135deg,#111,#2b2d32);
        color: #fff;
        box-shadow: 0 12px 30px rgba(17,17,17,.17);
    }

    .decision-kicker {
        font-size: .78rem;
        font-weight: 900;
        letter-spacing: .6px;
        color: #c9ccd3;
    }

    .decision-name {
        margin-top: 4px;
        font-size: 1.42rem;
        font-weight: 950;
    }

    .decision-copy {
        margin-top: 6px;
        color: #e2e4e8;
        font-size: .9rem;
    }

    .footer {
        margin-top: 16px;
        color: #6d7179;
        font-size: .78rem;
        line-height: 1.45;
    }

    @media (max-width: 900px) {
        .brand-name { font-size: 2.15rem; }
        .tagline, .subtagline { text-align: left; }
        .result-card { min-height: auto; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# One continuous string prevents raw HTML from appearing on screen.
brand_header_html = (
    '<div class="brand-shell">'
    '<div class="brand-row">'
    '<div>'
    '<div class="brand-name">'
    '<span class="brand-mrt">MRT</span> '
    '<span class="brand-pharma">Pharma</span>'
    '<span class="trademark">™</span>'
    '</div>'
    '<div class="product-name">Digital Twin</div>'
    '</div>'
    '<div>'
    '<div class="tagline">Engineering Distributed Precision Oncology Today.</div>'
    '<div class="subtagline">'
    'A streamlined hospital decision platform comparing conventional '
    'cyclotron-centered expansion with MRT-enabled distributed oncology.'
    '</div>'
    '</div>'
    '</div>'
    '<div class="red-rule"></div>'
    '</div>'
)
st.markdown(brand_header_html, unsafe_allow_html=True)


def open_section(number: str, title: str, helper: str) -> None:
    st.markdown(
        (
            '<div class="section-shell">'
            f'<div class="section-label">STEP {number}</div>'
            f'<div class="section-title">{title}</div>'
            f'<div class="helper">{helper}</div>'
        ),
        unsafe_allow_html=True,
    )


def close_section() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def export_excel(results: pd.DataFrame, assumptions: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        results.to_excel(writer, index=False, sheet_name="Ranked Configurations")
        assumptions.to_excel(writer, index=False, sheet_name="Assumptions")
    return buffer.getvalue()


with st.form("simplified_digital_twin"):
    open_section(
        "1",
        "Current Hospital and Future Demand",
        "Enter what the hospital has today and the patient demand it wants to serve.",
    )

    a1, a2, a3, a4 = st.columns(4)
    with a1:
        current_patients_day = st.number_input(
            "Current patients served/day",
            min_value=1.0,
            max_value=2000.0,
            value=50.0,
            step=5.0,
        )
        target_patients_day = st.number_input(
            "Future target patients/day",
            min_value=1.0,
            max_value=2000.0,
            value=200.0,
            step=5.0,
        )
    with a2:
        current_scanners = st.number_input(
            "Current PET scanners",
            min_value=1,
            max_value=30,
            value=2,
            step=1,
        )
        max_additional_scanners = st.number_input(
            "Maximum additional PET scanners",
            min_value=0,
            max_value=30,
            value=10,
            step=1,
        )
    with a3:
        operating_hours_day = st.number_input(
            "Operating hours/day",
            min_value=1.0,
            max_value=24.0,
            value=18.0,
            step=0.5,
        )
        scanner_cycle_minutes = st.number_input(
            "Average scanner cycle/patient (min)",
            min_value=5.0,
            max_value=180.0,
            value=35.0,
            step=5.0,
            help="Scanning plus room turnover time.",
        )
    with a4:
        scanner_availability_pct = st.number_input(
            "Scanner availability (%)",
            min_value=10.0,
            max_value=100.0,
            value=85.0,
            step=1.0,
        )
        current_dose_capacity_day = st.number_input(
            "Current released dose capacity/day",
            min_value=1.0,
            max_value=5000.0,
            value=100.0,
            step=5.0,
            help="Number of patient doses the current cyclotron/radiopharmacy can release per day.",
        )

    close_section()

    open_section(
        "2",
        "Clinical Rooms and Expansion Limits",
        "All injection and uptake room inputs are grouped together. MRT inpatient rooms are entered separately.",
    )

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        current_injection_rooms = st.number_input(
            "Current injection rooms",
            min_value=1,
            max_value=100,
            value=6,
            step=1,
        )
    with b2:
        current_uptake_rooms = st.number_input(
            "Current uptake rooms",
            min_value=1,
            max_value=100,
            value=6,
            step=1,
        )
    with b3:
        max_additional_injection_rooms = st.number_input(
            "Maximum additional injection rooms",
            min_value=0,
            max_value=100,
            value=12,
            step=1,
        )
    with b4:
        max_additional_uptake_rooms = st.number_input(
            "Maximum additional uptake rooms",
            min_value=0,
            max_value=100,
            value=12,
            step=1,
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        patients_per_dedicated_room_day = st.number_input(
            "Patients per dedicated room/day",
            min_value=1.0,
            max_value=100.0,
            value=30.0,
            step=1.0,
            help=(
                "Shared operating-rate assumption for dedicated injection "
                "and uptake rooms. Enter once; the model applies it to both."
            ),
        )
    with c2:
        max_mrt_enabled_inpatient_rooms = st.number_input(
            "MRT-enabled inpatient oncology rooms",
            min_value=0,
            max_value=1000,
            value=40,
            step=1,
        )
    with c3:
        patients_per_enabled_inpatient_room_day = st.number_input(
            "Patients/enabled inpatient room/day",
            min_value=0.1,
            max_value=10.0,
            value=1.0,
            step=0.1,
        )
    with c4:
        max_production_upgrade_pct = st.number_input(
            "Maximum cyclotron production increase (%)",
            min_value=0,
            max_value=300,
            value=150,
            step=5,
        )

    d1, d2 = st.columns(2)
    with d1:
        other_mrt_destinations = st.number_input(
            "Other MRT destinations",
            min_value=0,
            max_value=100,
            value=2,
            step=1,
            help=(
                "Radiopharmacy, waste-return room, treatment rooms, or other "
                "supporting destinations. Scanners and clinical rooms are "
                "counted automatically."
            ),
        )
    with d2:
        st.info(
            "MRT endpoint totals are calculated automatically. "
            "No deliveries-per-point input is required."
        )

    close_section()

    open_section(
        "3",
        "Economics",
        "Enter only the major cost and financial assumptions needed to compare the two architectures.",
    )

    e1, e2, e3, e4 = st.columns(4)
    with e1:
        scanner_capex = st.number_input(
            "CapEx/additional PET scanner (USD)",
            min_value=0.0,
            max_value=20_000_000.0,
            value=2_500_000.0,
            step=100_000.0,
            format="%.0f",
        )
        annual_opex_per_scanner = st.number_input(
            "Annual OpEx/additional scanner (USD)",
            min_value=0.0,
            max_value=10_000_000.0,
            value=300_000.0,
            step=25_000.0,
            format="%.0f",
        )
    with e2:
        injection_room_capex = st.number_input(
            "CapEx/additional injection room (USD)",
            min_value=0.0,
            max_value=10_000_000.0,
            value=250_000.0,
            step=25_000.0,
            format="%.0f",
        )
        uptake_room_capex = st.number_input(
            "CapEx/additional uptake room (USD)",
            min_value=0.0,
            max_value=10_000_000.0,
            value=200_000.0,
            step=25_000.0,
            format="%.0f",
        )
    with e3:
        conventional_upgrade_capex_per_10pct = st.number_input(
            "Conventional production CapEx/10% (USD)",
            min_value=0.0,
            max_value=20_000_000.0,
            value=650_000.0,
            step=50_000.0,
            format="%.0f",
        )
        hybrid_upgrade_capex_per_10pct = st.number_input(
            "Hybrid production CapEx/10% (USD)",
            min_value=0.0,
            max_value=20_000_000.0,
            value=600_000.0,
            step=50_000.0,
            format="%.0f",
        )
    with e4:
        mrt_core_capex = st.number_input(
            "MRT core infrastructure CapEx (USD)",
            min_value=0.0,
            max_value=100_000_000.0,
            value=6_000_000.0,
            step=250_000.0,
            format="%.0f",
        )
        mrt_endpoint_capex = st.number_input(
            "MRT endpoint installation cost (USD)",
            min_value=0.0,
            max_value=5_000_000.0,
            value=10_000.0,
            step=5_000.0,
            format="%.0f",
        )

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        annual_base_opex_conventional = st.number_input(
            "Annual base OpEx — conventional (USD)",
            min_value=0.0,
            max_value=100_000_000.0,
            value=2_000_000.0,
            step=100_000.0,
            format="%.0f",
        )
        annual_base_opex_hybrid = st.number_input(
            "Annual base OpEx — MRT hybrid (USD)",
            min_value=0.0,
            max_value=100_000_000.0,
            value=1_500_000.0,
            step=100_000.0,
            format="%.0f",
        )
    with f2:
        annual_opex_per_injection_room = st.number_input(
            "Annual OpEx/injection room (USD)",
            min_value=0.0,
            max_value=5_000_000.0,
            value=90_000.0,
            step=10_000.0,
            format="%.0f",
        )
        annual_opex_per_uptake_room = st.number_input(
            "Annual OpEx/uptake room (USD)",
            min_value=0.0,
            max_value=5_000_000.0,
            value=70_000.0,
            step=10_000.0,
            format="%.0f",
        )
    with f3:
        annual_mrt_maintenance = st.number_input(
            "Annual MRT maintenance/support (USD)",
            min_value=0.0,
            max_value=50_000_000.0,
            value=450_000.0,
            step=50_000.0,
            format="%.0f",
        )
        annual_opex_per_mrt_endpoint = st.number_input(
            "Annual OpEx/MRT endpoint (USD)",
            min_value=0.0,
            max_value=1_000_000.0,
            value=5_000.0,
            step=5_000.0,
            format="%.0f",
        )
    with f4:
        net_contribution_per_incremental_patient = st.number_input(
            "Net contribution/incremental patient (USD)",
            min_value=0.0,
            max_value=100_000.0,
            value=750.0,
            step=25.0,
        )
        maximum_capex_budget = st.number_input(
            "Maximum available CapEx (USD)",
            min_value=0.0,
            max_value=500_000_000.0,
            value=100_000_000.0,
            step=1_000_000.0,
            format="%.0f",
        )

    g1, g2, g3 = st.columns(3)
    with g1:
        operating_days_year = st.number_input(
            "Operating days/year",
            min_value=1,
            max_value=365,
            value=300,
            step=5,
        )
    with g2:
        analysis_years = st.number_input(
            "Financial analysis period (years)",
            min_value=1,
            max_value=25,
            value=10,
            step=1,
        )
    with g3:
        discount_rate_pct = st.number_input(
            "Discount rate (%)",
            min_value=0.0,
            max_value=50.0,
            value=10.0,
            step=0.5,
        )

    close_section()

    submitted = st.form_submit_button(
        "RUN MRT PHARMA DIGITAL TWIN",
        use_container_width=True,
    )


if submitted:
    inputs = ModelInputs(
        current_patients_day=current_patients_day,
        target_patients_day=target_patients_day,
        current_scanners=current_scanners,
        max_additional_scanners=max_additional_scanners,
        operating_hours_day=operating_hours_day,
        scanner_cycle_minutes=scanner_cycle_minutes,
        scanner_availability_pct=scanner_availability_pct,
        current_injection_rooms=current_injection_rooms,
        current_uptake_rooms=current_uptake_rooms,
        max_additional_injection_rooms=max_additional_injection_rooms,
        max_additional_uptake_rooms=max_additional_uptake_rooms,
        patients_per_injection_room_day=patients_per_dedicated_room_day,
        patients_per_uptake_room_day=patients_per_dedicated_room_day,
        current_dose_capacity_day=current_dose_capacity_day,
        max_production_upgrade_pct=max_production_upgrade_pct,
        max_mrt_enabled_inpatient_rooms=max_mrt_enabled_inpatient_rooms,
        patients_per_enabled_inpatient_room_day=patients_per_enabled_inpatient_room_day,
        other_mrt_destinations=other_mrt_destinations,
        scanner_capex=scanner_capex,
        injection_room_capex=injection_room_capex,
        uptake_room_capex=uptake_room_capex,
        conventional_upgrade_capex_per_10pct=conventional_upgrade_capex_per_10pct,
        hybrid_upgrade_capex_per_10pct=hybrid_upgrade_capex_per_10pct,
        mrt_core_capex=mrt_core_capex,
        mrt_endpoint_capex=mrt_endpoint_capex,
        annual_base_opex_conventional=annual_base_opex_conventional,
        annual_base_opex_hybrid=annual_base_opex_hybrid,
        annual_opex_per_scanner=annual_opex_per_scanner,
        annual_opex_per_injection_room=annual_opex_per_injection_room,
        annual_opex_per_uptake_room=annual_opex_per_uptake_room,
        annual_mrt_maintenance=annual_mrt_maintenance,
        annual_opex_per_mrt_endpoint=annual_opex_per_mrt_endpoint,
        net_contribution_per_incremental_patient=net_contribution_per_incremental_patient,
        operating_days_year=operating_days_year,
        analysis_years=analysis_years,
        discount_rate_pct=discount_rate_pct,
        maximum_capex_budget=maximum_capex_budget,
    )

    results = optimize(inputs)

    st.markdown(
        '<div class="results-heading">Digital Twin Results</div>',
        unsafe_allow_html=True,
    )

    options = [
        (
            "Option 1",
            "Conventional Expansion",
            results.best_conventional,
        ),
        (
            "Option 2",
            "MRT Pharma Hybrid",
            results.best_hybrid,
        ),
    ]
    cards = st.columns(2)

    for card, (option_number, title, candidate) in zip(cards, options):
        is_winner = (
            results.decision is not None
            and candidate is not None
            and candidate.architecture == results.decision.architecture
        )
        css_class = "result-card winner-card" if is_winner else "result-card"

        if candidate is None:
            html = (
                f'<div class="{css_class}">'
                f'<div class="option-title">{option_number} — {title}</div>'
                f'<div class="option-subtitle">Best feasible configuration</div>'
                f'<div class="hero-value">NOT FEASIBLE</div>'
                f'<div class="metric-line">'
                f'<span class="metric-label">Result</span>'
                f'<span class="metric-value">Review limits or economics</span>'
                f'</div>'
                f'</div>'
            )
        else:
            badge = (
                '<div class="winner-badge">✓ WINNER</div>'
                if is_winner
                else ""
            )
            html = (
                f'<div class="{css_class}">'
                f'<div class="option-title">{option_number} — {title}</div>'
                f'<div class="option-subtitle">Best positive-NPV configuration</div>'
                f'{badge}'
                f'<div class="hero-value">${candidate.capex:,.0f}</div>'
                f'<div class="metric-line">'
                f'<span class="metric-label">Installed capacity</span>'
                f'<span class="metric-value">{candidate.installed_capacity_day:.0f}/day</span>'
                f'</div>'
                f'<div class="metric-line">'
                f'<span class="metric-label">NPV</span>'
                f'<span class="metric-value">${candidate.npv:,.0f}</span>'
                f'</div>'
                f'<div class="metric-line">'
                f'<span class="metric-label">Payback</span>'
                f'<span class="metric-value">{candidate.payback_years:.1f} years</span>'
                f'</div>'
                f'<div class="metric-line">'
                f'<span class="metric-label">{analysis_years}-year ROI</span>'
                f'<span class="metric-value">{candidate.roi_pct:.1f}%</span>'
                f'</div>'
                f'</div>'
            )

        card.markdown(html, unsafe_allow_html=True)

    with st.expander(
        "View full side-by-side comparison",
        expanded=False,
    ):
        detail_columns = st.columns(2)

        for column, (_, title, candidate) in zip(detail_columns, options):
            with column:
                st.markdown(f"### {title}")
                if candidate is None:
                    st.warning("No positive-NPV configuration met all selected constraints.")
                    continue

                details = {
                    "Installed capacity": f"{candidate.installed_capacity_day:.0f}/day",
                    "Patients served": f"{candidate.patients_served_day:.0f}/day",
                    "Reserve capacity": f"{candidate.reserve_capacity_day:.0f}/day",
                    "Incremental patients": f"{candidate.incremental_patients_day:.0f}/day",
                    "CapEx": f"${candidate.capex:,.0f}",
                    "Annual OpEx": f"${candidate.annual_opex:,.0f}",
                    "Annual net cash flow": f"${candidate.annual_net_cash_flow:,.0f}",
                    "Production increase": f"{candidate.production_upgrade_pct}%",
                    "Additional scanners": candidate.additional_scanners,
                    "Payback": f"{candidate.payback_years:.1f} years",
                    f"{analysis_years}-year ROI": f"{candidate.roi_pct:.1f}%",
                    "NPV": f"${candidate.npv:,.0f}",
                }

                if candidate.architecture == "Conventional Expansion":
                    details["Additional injection rooms"] = (
                        candidate.additional_injection_rooms
                    )
                    details["Additional uptake rooms"] = (
                        candidate.additional_uptake_rooms
                    )
                    details["MRT-enabled inpatient rooms"] = "Not applicable"
                else:
                    details["MRT-enabled inpatient rooms"] = (
                        candidate.mrt_enabled_inpatient_rooms
                    )
                    details["Total MRT endpoints"] = candidate.mrt_endpoints
                    details["Dedicated rooms avoided"] = (
                        candidate.dedicated_rooms_avoided
                    )
                    details["Additional dedicated rooms"] = 0

                detail_df = pd.DataFrame(
                    [
                        {"Metric": metric, "Value": value}
                        for metric, value in details.items()
                    ]
                )
                st.dataframe(
                    detail_df,
                    hide_index=True,
                    use_container_width=True,
                )

    if results.decision is not None:
        winner = results.decision
        st.markdown(
            (
                '<div class="decision-strip">'
                '<div class="decision-kicker">DIGITAL TWIN DECISION</div>'
                f'<div class="decision-name">✓ {winner.architecture}</div>'
                f'<div class="decision-copy">'
                f'Highest modeled positive NPV: ${winner.npv:,.0f}. '
                f'Installed capacity: {winner.installed_capacity_day:.0f} patients/day. '
                f'Estimated payback: {winner.payback_years:.1f} years.'
                '</div>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )
    else:
        st.warning(
            "Neither option produced a positive-NPV configuration that met "
            "the selected capacity and budget constraints. Increase permitted "
            "scanner, room, or production expansion—or revise the financial assumptions."
        )

    st.markdown("### Model Search")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Configurations evaluated",
        f"{results.conventional_candidates_evaluated + results.hybrid_candidates_evaluated:,}",
    )
    m2.metric(
        "Feasible configurations",
        f"{results.feasible_candidates:,}",
    )
    m3.metric(
        "Positive-NPV configurations",
        f"{results.positive_npv_candidates:,}",
    )
    m4.metric(
        "Current physical capacity",
        f"{results.current_physical_capacity_day:.0f}/day",
    )

    st.markdown("### Discounted Break-even")
    figure = go.Figure()
    years = list(range(analysis_years + 1))
    rate = discount_rate_pct / 100.0

    for title, candidate in [
        ("Conventional Expansion", results.best_conventional),
        ("MRT Pharma Hybrid", results.best_hybrid),
    ]:
        if candidate is None:
            continue

        cumulative = [-candidate.capex]
        total = -candidate.capex
        for year in range(1, analysis_years + 1):
            total += candidate.annual_net_cash_flow / ((1 + rate) ** year)
            cumulative.append(total)

        figure.add_trace(
            go.Scatter(
                x=years,
                y=cumulative,
                mode="lines+markers",
                name=title,
            )
        )

    figure.add_hline(y=0, line_dash="dash", line_color="#d71920")
    figure.update_layout(
        title="Discounted cumulative net cash flow",
        xaxis_title="Year",
        yaxis_title="Discounted cumulative net cash flow (USD)",
        template="plotly_white",
        height=480,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    st.plotly_chart(figure, use_container_width=True)

    ranked_df = pd.DataFrame(
        [asdict(candidate) for candidate in results.ranked_candidates]
    )
    assumptions_df = pd.DataFrame(
        [
            {"Assumption": key, "Value": value}
            for key, value in asdict(inputs).items()
        ]
    )

    if not ranked_df.empty:
        with st.expander("View ranked configurations and downloads"):
            st.dataframe(
                ranked_df.head(20),
                hide_index=True,
                use_container_width=True,
            )
            download1, download2 = st.columns(2)
            with download1:
                st.download_button(
                    "Download results as CSV",
                    ranked_df.to_csv(index=False).encode("utf-8"),
                    "mrt_pharma_simplified_results.csv",
                    "text/csv",
                    use_container_width=True,
                )
            with download2:
                st.download_button(
                    "Download results and assumptions as Excel",
                    export_excel(ranked_df, assumptions_df),
                    "mrt_pharma_simplified_results.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

    st.markdown(
        '<div class="footer">'
        'MRT Pharma™ Digital Twin demonstration model. Outputs are illustrative '
        'and depend on user-entered assumptions. Hospital engineering, clinical, '
        'financial, radiation-safety, and regulatory validation remain required.'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    st.info(
        "Complete the three short sections above and click "
        "**RUN MRT PHARMA DIGITAL TWIN**."
    )

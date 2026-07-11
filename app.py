
import io
import math
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="MRT Pharma™ Digital Twin",
    page_icon="⚙️",
    layout="wide",
)


# ============================================================
# BRANDING AND PAGE STYLING
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --red: #d71920;
        --black: #111111;
        --white: #ffffff;
        --line: #dedede;
    }

    .stApp {
        background:
            linear-gradient(
                135deg,
                #ffffff 0%,
                #f7f7f7 58%,
                #fff1f1 100%
            );
    }

    .block-container {
        max-width: 1360px;
        padding-top: 3.5rem !important;
        padding-bottom: 2rem;
    }

    .brand-shell {
        width: 100%;
        box-sizing: border-box;
        overflow: visible !important;
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 24px 28px 20px;
        margin-top: 0.5rem;
        margin-bottom: 14px;
        box-shadow: 0 8px 24px rgba(17, 17, 17, 0.06);
    }

    .brand-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 28px;
        flex-wrap: wrap;
        overflow: visible !important;
    }

    .brand-name {
        display: block;
        white-space: nowrap;
        overflow: visible !important;
        font-size: 2.75rem;
        font-weight: 900;
        line-height: 1.22;
        letter-spacing: -1px;
        padding-top: 4px;
    }

    .brand-mrt {
        color: var(--black);
    }

    .brand-pharma {
        color: var(--red);
    }

    .trademark {
        position: relative;
        top: -0.75em;
        margin-left: 2px;
        font-size: 0.38em;
        font-weight: 800;
        color: var(--red);
    }

    .product-name {
        margin-top: 4px;
        font-size: 1.55rem;
        line-height: 1.25;
        font-weight: 900;
        color: var(--black);
    }

    .tagline {
        text-align: right;
        font-weight: 850;
        color: var(--black);
        font-size: 1rem;
        line-height: 1.35;
    }

    .subtagline {
        max-width: 650px;
        margin-top: 5px;
        text-align: right;
        color: #666666;
        font-size: 0.88rem;
        line-height: 1.45;
    }

    .red-rule {
        width: 100%;
        height: 6px;
        margin-top: 16px;
        border-radius: 999px;
        background:
            linear-gradient(
                90deg,
                var(--red),
                #ff4c52
            );
    }

    .panel {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 18px 24px;
        box-shadow: 0 8px 24px rgba(17, 17, 17, 0.06);
        margin-bottom: 12px;
    }

    .dark-panel {
        background: var(--black);
        color: #ffffff;
        border-radius: 18px;
        padding: 18px 24px;
        box-shadow: 0 8px 24px rgba(17, 17, 17, 0.13);
        margin-bottom: 12px;
    }

    .result-card {
        border-radius: 18px;
        padding: 18px;
        min-height: 390px;
        background: linear-gradient(135deg, #ffffff, #f2f2f2);
        border: 1px solid rgba(17, 17, 17, 0.10);
        border-top: 7px solid var(--red);
        box-shadow: 0 8px 24px rgba(17, 17, 17, 0.08);
    }

    .decision-card {
        background: linear-gradient(135deg, #111111, #2b2b2b);
        color: #ffffff;
    }

    .decision-card .card-title,
    .decision-card .big,
    .decision-card b {
        color: #ffffff;
    }

    .card-title {
        font-size: 1.08rem;
        font-weight: 900;
        color: #111111;
        margin-bottom: 0.55rem;
    }

    .big {
        font-size: 1.4rem;
        font-weight: 950;
        color: #111111;
        overflow-wrap: anywhere;
    }

    .rationale {
        background: #fff7f7;
        border-left: 5px solid var(--red);
        border-radius: 12px;
        padding: 14px 16px;
    }

    .assumption-note {
        background: #fff8e8;
        border: 1px solid #efd69e;
        border-radius: 12px;
        padding: 11px 14px;
        margin: 8px 0 14px;
        font-size: 0.86rem;
        color: #4a3a13;
    }

    div[data-testid="stNumberInput"] label {
        font-weight: 700;
        color: #202020;
    }

    div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(90deg, #a90f16, var(--red));
        color: #ffffff;
        font-weight: 900;
        border-radius: 12px;
        border: none;
        min-height: 3rem;
        width: 100%;
    }

    div[data-testid="stFormSubmitButton"] > button:hover {
        background: linear-gradient(90deg, #850b10, #bd1118);
        color: #ffffff;
    }

    .footer {
        color: #666666;
        font-size: 0.80rem;
        margin-top: 10px;
    }

    @media (max-width: 900px) {
        .brand-row {
            align-items: flex-start;
        }

        .tagline,
        .subtagline {
            text-align: left;
        }

        .brand-name {
            font-size: 2.25rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# BRAND HEADER
# ============================================================

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
    '<div class="tagline">Engineering Precision Oncology Today.</div>'
    '<div class="subtagline">'
    'Physics-based decision platform for distributed oncology infrastructure, '
    'radiopharmaceutical logistics, capacity planning, and lifecycle economics.'
    '</div>'
    '</div>'
    '</div>'
    '<div class="red-rule"></div>'
    '</div>'
)

st.markdown(
    brand_header_html,
    unsafe_allow_html=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_payback(capex: float, annual_net: float) -> float:
    if annual_net <= 0:
        return float("inf")
    return capex / annual_net


def calculate_npv(
    capex: float,
    annual_net: float,
    years: int,
    rate: float,
) -> float:
    return -capex + sum(
        annual_net / ((1 + rate) ** year)
        for year in range(1, years + 1)
    )


def calculate_roi(
    capex: float,
    annual_net: float,
    years: int,
) -> float:
    if capex <= 0:
        return 0.0
    return (((annual_net * years) - capex) / capex) * 100.0


def discounted_series(
    capex: float,
    annual_net: float,
    years: int,
    rate: float,
) -> List[float]:
    values = [-capex]
    cumulative_total = -capex

    for year in range(1, years + 1):
        cumulative_total += annual_net / ((1 + rate) ** year)
        values.append(cumulative_total)

    return values


def export_excel(
    results: pd.DataFrame,
    assumptions: pd.DataFrame,
) -> bytes:
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        results.to_excel(
            writer,
            index=False,
            sheet_name="Ranked Configurations",
        )
        assumptions.to_excel(
            writer,
            index=False,
            sheet_name="Assumptions",
        )

    return buffer.getvalue()


# ============================================================
# INPUT FORM
# ============================================================

with st.form("digital_twin_form"):
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 1. Clinical Demand and Distributed Oncology")

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        current_scanners = st.number_input(
            "Current PET scanners",
            min_value=1,
            max_value=30,
            value=5,
            step=1,
        )
        target_patients = st.number_input(
            "Target PET patients/day",
            min_value=1,
            max_value=2000,
            value=200,
            step=5,
        )

    with a2:
        operating_hours = st.number_input(
            "Operating hours/day",
            min_value=1.0,
            max_value=24.0,
            value=18.0,
            step=0.5,
        )
        scan_minutes = st.number_input(
            "Scanner occupation time/patient (min)",
            min_value=5.0,
            max_value=180.0,
            value=30.0,
            step=5.0,
        )

    with a3:
        turnover_minutes = st.number_input(
            "Turnover time/patient (min)",
            min_value=0.0,
            max_value=120.0,
            value=15.0,
            step=5.0,
        )
        scanner_availability = st.number_input(
            "Scanner availability (%)",
            min_value=10.0,
            max_value=100.0,
            value=85.0,
            step=1.0,
        )

    with a4:
        max_additional_scanners = st.number_input(
            "Maximum additional PET scanners",
            min_value=0,
            max_value=40,
            value=12,
            step=1,
        )
        maximum_clinical_nodes = st.number_input(
            "Maximum MRT-connected clinical access points",
            min_value=1,
            max_value=100,
            value=8,
            step=1,
            help=(
                "Examples include pediatric oncology wings, adult oncology "
                "wings, outpatient imaging centers, injection suites, "
                "and inpatient oncology service points."
            ),
        )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 2. Injection, Uptake, FDG Production, and Transport")

    b1, b2, b3, b4 = st.columns(4)

    with b1:
        current_injection_rooms = st.number_input(
            "Current injection rooms",
            min_value=1,
            max_value=100,
            value=6,
            step=1,
        )
        patients_per_injection_room = st.number_input(
            "Patients/injection room/day",
            min_value=1.0,
            max_value=200.0,
            value=30.0,
            step=1.0,
        )

    with b2:
        current_uptake_rooms = st.number_input(
            "Current uptake rooms",
            min_value=1,
            max_value=200,
            value=12,
            step=1,
        )
        patients_per_uptake_room = st.number_input(
            "Patients/uptake room/day",
            min_value=1.0,
            max_value=100.0,
            value=15.0,
            step=1.0,
        )

    with b3:
        max_additional_injection_rooms = st.number_input(
            "Maximum additional injection rooms",
            min_value=0,
            max_value=100,
            value=12,
            step=1,
        )
        max_additional_uptake_rooms = st.number_input(
            "Maximum additional uptake rooms",
            min_value=0,
            max_value=200,
            value=24,
            step=1,
        )

    with b4:
        manual_transport_capacity = st.number_input(
            "Manual deliveries/day",
            min_value=1.0,
            max_value=5000.0,
            value=220.0,
            step=10.0,
        )
        mrt_transport_capacity_per_node = st.number_input(
            "MRT deliveries/node/day",
            min_value=1.0,
            max_value=5000.0,
            value=120.0,
            step=10.0,
        )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        eob_gbq_batch = st.number_input(
            "18F activity at EOB/batch (GBq)",
            min_value=0.1,
            max_value=500.0,
            value=30.0,
            step=1.0,
        )
        current_batches = st.number_input(
            "Current FDG batches/day",
            min_value=1,
            max_value=12,
            value=2,
            step=1,
        )

    with c2:
        synthesis_yield = st.number_input(
            "Synthesis yield (%)",
            min_value=1.0,
            max_value=100.0,
            value=75.0,
            step=1.0,
        )
        qc_yield = st.number_input(
            "QC/release yield (%)",
            min_value=1.0,
            max_value=100.0,
            value=95.0,
            step=1.0,
        )

    with c3:
        eob_release_min = st.number_input(
            "EOB-to-release time (min)",
            min_value=0.0,
            max_value=240.0,
            value=45.0,
            step=5.0,
        )
        patient_dose_mbq = st.number_input(
            "FDG dose/patient (MBq)",
            min_value=1.0,
            max_value=1000.0,
            value=300.0,
            step=10.0,
        )

    with c4:
        manual_transport_min = st.number_input(
            "Manual delivery time (min)",
            min_value=0.0,
            max_value=120.0,
            value=10.0,
            step=1.0,
        )
        mrt_distance_m = st.number_input(
            "MRT distance to farthest node (m)",
            min_value=0.0,
            max_value=10000.0,
            value=750.0,
            step=50.0,
        )

    d1, d2, d3, d4 = st.columns(4)

    with d1:
        mrt_load_dock_sec = st.number_input(
            "MRT loading + docking (sec)",
            min_value=0.0,
            max_value=600.0,
            value=50.0,
            step=5.0,
        )

    with d2:
        max_additional_batches = st.number_input(
            "Maximum additional batches/day",
            min_value=0,
            max_value=10,
            value=4,
            step=1,
        )

    with d3:
        max_upgrade_pct = st.number_input(
            "Maximum cyclotron upgrade (%)",
            min_value=0,
            max_value=200,
            value=100,
            step=5,
        )

    with d4:
        half_life_min = st.number_input(
            "18F half-life (min)",
            min_value=1.0,
            max_value=500.0,
            value=109.8,
            step=0.1,
        )

    st.markdown(
        """
        <div class="assumption-note">
            <b>Distributed-workflow assumption:</b>
            The MRT workflow uplift is explicit and editable.
            It represents potential improvements from lower transport
            variability, fewer manual handoffs, improved synchronization,
            and reduced scanner idle time. These values should ultimately
            be validated using hospital-specific operational data.
        </div>
        """,
        unsafe_allow_html=True,
    )

    u1, u2, u3 = st.columns(3)

    with u1:
        distribution_uplift_per_node_pct = st.number_input(
            "Workflow improvement per MRT access point (%)",
            min_value=0.0,
            max_value=20.0,
            value=2.0,
            step=0.5,
        )

    with u2:
        maximum_distribution_uplift_pct = st.number_input(
            "Maximum total MRT workflow improvement (%)",
            min_value=0.0,
            max_value=100.0,
            value=18.0,
            step=1.0,
        )

    with u3:
        baseline_distribution_efficiency_pct = st.number_input(
            "Current hospital distribution efficiency (%)",
            min_value=1.0,
            max_value=100.0,
            value=82.0,
            step=1.0,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="dark-panel">', unsafe_allow_html=True)
    st.markdown("### 3. CapEx, OpEx, Revenue, and Financial Assumptions")

    f1, f2, f3, f4 = st.columns(4)

    with f1:
        new_cyclotron_capex = st.number_input(
            "New cyclotron + radiopharmacy CapEx (USD)",
            min_value=0.0,
            max_value=200_000_000.0,
            value=15_000_000.0,
            step=500_000.0,
            format="%.0f",
        )
        new_cyclotron_release_capacity_gbq_day = st.number_input(
            "New cyclotron released FDG capacity/day (GBq)",
            min_value=0.1,
            max_value=5000.0,
            value=80.0,
            step=5.0,
        )

    with f2:
        scanner_capex = st.number_input(
            "Additional PET scanner CapEx (USD)",
            min_value=0.0,
            max_value=20_000_000.0,
            value=2_500_000.0,
            step=100_000.0,
            format="%.0f",
        )
        injection_room_capex = st.number_input(
            "Additional injection room CapEx (USD)",
            min_value=0.0,
            max_value=10_000_000.0,
            value=250_000.0,
            step=25_000.0,
            format="%.0f",
        )

    with f3:
        uptake_room_capex = st.number_input(
            "Additional uptake room CapEx (USD)",
            min_value=0.0,
            max_value=10_000_000.0,
            value=200_000.0,
            step=25_000.0,
            format="%.0f",
        )
        clinical_node_capex = st.number_input(
            "Clinical access point CapEx (USD)",
            min_value=0.0,
            max_value=20_000_000.0,
            value=400_000.0,
            step=50_000.0,
            format="%.0f",
        )

    with f4:
        pure_upgrade_capex_per_10pct = st.number_input(
            "Conventional upgrade CapEx/10% (USD)",
            min_value=0.0,
            max_value=20_000_000.0,
            value=650_000.0,
            step=50_000.0,
            format="%.0f",
        )
        hybrid_upgrade_capex_per_10pct = st.number_input(
            "Hybrid upgrade CapEx/10% (USD)",
            min_value=0.0,
            max_value=20_000_000.0,
            value=600_000.0,
            step=50_000.0,
            format="%.0f",
        )

    g1, g2, g3, g4 = st.columns(4)

    with g1:
        mrt_capex = st.number_input(
            "MRT Pharma infrastructure CapEx (USD)",
            min_value=0.0,
            max_value=100_000_000.0,
            value=6_000_000.0,
            step=250_000.0,
            format="%.0f",
        )
        revenue_per_incremental_patient = st.number_input(
            "Net contribution/additional patient (USD)",
            min_value=0.0,
            max_value=100_000.0,
            value=750.0,
            step=25.0,
        )

    with g2:
        annual_base_opex_new = st.number_input(
            "Annual base OpEx — new cyclotron (USD)",
            min_value=0.0,
            max_value=100_000_000.0,
            value=5_000_000.0,
            step=100_000.0,
            format="%.0f",
        )
        annual_base_opex_upgrade = st.number_input(
            "Annual base OpEx — conventional upgrade (USD)",
            min_value=0.0,
            max_value=100_000_000.0,
            value=3_800_000.0,
            step=100_000.0,
            format="%.0f",
        )

    with g3:
        annual_base_opex_hybrid = st.number_input(
            "Annual base OpEx — MRT hybrid (USD)",
            min_value=0.0,
            max_value=100_000_000.0,
            value=3_200_000.0,
            step=100_000.0,
            format="%.0f",
        )
        annual_mrt_maintenance = st.number_input(
            "Annual MRT maintenance/support (USD)",
            min_value=0.0,
            max_value=50_000_000.0,
            value=450_000.0,
            step=50_000.0,
            format="%.0f",
        )

    with g4:
        incremental_opex_per_batch = st.number_input(
            "OpEx/additional batch (USD)",
            min_value=0.0,
            max_value=1_000_000.0,
            value=8_000.0,
            step=500.0,
        )
        annual_opex_per_scanner = st.number_input(
            "Annual OpEx/additional scanner (USD)",
            min_value=0.0,
            max_value=10_000_000.0,
            value=300_000.0,
            step=25_000.0,
            format="%.0f",
        )

    h1, h2, h3, h4 = st.columns(4)

    with h1:
        annual_opex_per_injection_room = st.number_input(
            "Annual OpEx/injection room (USD)",
            min_value=0.0,
            max_value=5_000_000.0,
            value=90_000.0,
            step=10_000.0,
            format="%.0f",
        )

    with h2:
        annual_opex_per_uptake_room = st.number_input(
            "Annual OpEx/uptake room (USD)",
            min_value=0.0,
            max_value=5_000_000.0,
            value=70_000.0,
            step=10_000.0,
            format="%.0f",
        )

    with h3:
        operating_days = st.number_input(
            "Operating days/year",
            min_value=1,
            max_value=365,
            value=300,
            step=5,
        )
        analysis_years = st.number_input(
            "Financial analysis period (years)",
            min_value=1,
            max_value=25,
            value=10,
            step=1,
        )

    with h4:
        discount_rate_pct = st.number_input(
            "Discount rate (%)",
            min_value=0.0,
            max_value=50.0,
            value=10.0,
            step=0.5,
        )
        maximum_budget = st.number_input(
            "Maximum available CapEx (USD)",
            min_value=0.0,
            max_value=500_000_000.0,
            value=100_000_000.0,
            step=1_000_000.0,
            format="%.0f",
        )

    st.markdown("</div>", unsafe_allow_html=True)

    submitted = st.form_submit_button(
        "RUN MRT PHARMA DIGITAL TWIN",
        use_container_width=True,
    )


# ============================================================
# MODEL EXECUTION
# ============================================================

if submitted:
    MRT_SPEED_MPS = 50.0

    scanner_cycle = scan_minutes + turnover_minutes

    patients_per_scanner = (
        operating_hours * 60.0 / scanner_cycle
    ) * (
        scanner_availability / 100.0
    )

    decay_to_release = 2 ** (
        -eob_release_min / half_life_min
    )

    released_gbq_per_batch = (
        eob_gbq_batch
        * synthesis_yield / 100.0
        * qc_yield / 100.0
        * decay_to_release
    )

    current_release_day = (
        released_gbq_per_batch
        * current_batches
    )

    manual_survival = 2 ** (
        -manual_transport_min / half_life_min
    )

    mrt_total_min = (
        (mrt_distance_m / MRT_SPEED_MPS)
        + mrt_load_dock_sec
    ) / 60.0

    mrt_survival = 2 ** (
        -mrt_total_min / half_life_min
    )

    current_throughput = min(
        current_scanners * patients_per_scanner,
        current_injection_rooms * patients_per_injection_room,
        current_uptake_rooms * patients_per_uptake_room,
        manual_transport_capacity,
        current_release_day
        * 1000.0
        * manual_survival
        / patient_dose_mbq,
    )

    candidates: List[Dict[str, float]] = []

    total_generated = 0
    physically_evaluated = 0
    met_target = 0
    within_budget = 0

    scanner_values = range(
        max_additional_scanners + 1
    )
    injection_values = range(
        max_additional_injection_rooms + 1
    )
    uptake_values = range(
        max_additional_uptake_rooms + 1
    )
    upgrade_values = range(
        0,
        max_upgrade_pct + 1,
        5,
    )
    batch_values = range(
        max_additional_batches + 1
    )

    def add_financial_candidate(
        architecture: str,
        throughput: float,
        capex: float,
        annual_opex: float,
        upgrade_pct: int,
        added_batches: int,
        add_scanners: int,
        add_injection: int,
        add_uptake: int,
        clinical_nodes: int,
        survival_pct: float,
    ) -> None:
        served_patients = min(throughput, float(target_patients))
        incremental_patients = max(
            0.0,
            served_patients - current_throughput,
        )
        reserve_capacity = max(0.0, throughput - float(target_patients))

        annual_incremental_revenue = (
            incremental_patients
            * operating_days
            * revenue_per_incremental_patient
        )

        annual_net = (
            annual_incremental_revenue
            - annual_opex
        )

        candidates.append(
            {
                "architecture": architecture,
                "throughput": throughput,
                "served_patients_day": served_patients,
                "reserve_capacity_day": reserve_capacity,
                "incremental_patients_day": incremental_patients,
                "capex": capex,
                "annual_opex": annual_opex,
                "annual_incremental_revenue": annual_incremental_revenue,
                "annual_net": annual_net,
                "upgrade_pct": upgrade_pct,
                "added_batches": added_batches,
                "add_scanners": add_scanners,
                "add_injection": add_injection,
                "add_uptake": add_uptake,
                "clinical_nodes": clinical_nodes,
                "fdg_survival_pct": survival_pct,
            }
        )

    # Architecture 1: New Cyclotron
    for add_scanners in scanner_values:
        for add_injection in injection_values:
            for add_uptake in uptake_values:
                total_generated += 1
                physically_evaluated += 1

                throughput = min(
                    (
                        current_scanners
                        + add_scanners
                    ) * patients_per_scanner,
                    (
                        current_injection_rooms
                        + add_injection
                    ) * patients_per_injection_room,
                    (
                        current_uptake_rooms
                        + add_uptake
                    ) * patients_per_uptake_room,
                    manual_transport_capacity,
                    (
                        current_release_day
                        + new_cyclotron_release_capacity_gbq_day
                    )
                    * 1000.0
                    * manual_survival
                    / patient_dose_mbq,
                )

                if throughput < target_patients:
                    continue

                met_target += 1

                capex = (
                    new_cyclotron_capex
                    + add_scanners * scanner_capex
                    + add_injection * injection_room_capex
                    + add_uptake * uptake_room_capex
                )

                if capex > maximum_budget:
                    continue

                within_budget += 1

                annual_opex = (
                    annual_base_opex_new
                    + add_scanners * annual_opex_per_scanner
                    + add_injection * annual_opex_per_injection_room
                    + add_uptake * annual_opex_per_uptake_room
                )

                add_financial_candidate(
                    "New Cyclotron",
                    throughput,
                    capex,
                    annual_opex,
                    0,
                    0,
                    add_scanners,
                    add_injection,
                    add_uptake,
                    1,
                    manual_survival * 100.0,
                )

    # Architecture 2: Conventional Upgrade
    for upgrade_pct in upgrade_values:
        for added_batches in batch_values:
            release = (
                current_release_day
                * (1 + upgrade_pct / 100.0)
                + added_batches
                * released_gbq_per_batch
            )

            fdg_capacity = (
                release
                * 1000.0
                * manual_survival
                / patient_dose_mbq
            )

            for add_scanners in scanner_values:
                for add_injection in injection_values:
                    for add_uptake in uptake_values:
                        total_generated += 1
                        physically_evaluated += 1

                        throughput = min(
                            (
                                current_scanners
                                + add_scanners
                            ) * patients_per_scanner,
                            (
                                current_injection_rooms
                                + add_injection
                            ) * patients_per_injection_room,
                            (
                                current_uptake_rooms
                                + add_uptake
                            ) * patients_per_uptake_room,
                            manual_transport_capacity,
                            fdg_capacity,
                        )

                        if throughput < target_patients:
                            continue

                        met_target += 1

                        capex = (
                            (
                                upgrade_pct
                                / 10.0
                            )
                            * pure_upgrade_capex_per_10pct
                            + add_scanners * scanner_capex
                            + add_injection * injection_room_capex
                            + add_uptake * uptake_room_capex
                        )

                        if capex > maximum_budget:
                            continue

                        within_budget += 1

                        annual_opex = (
                            annual_base_opex_upgrade
                            + added_batches
                            * incremental_opex_per_batch
                            * operating_days
                            + add_scanners
                            * annual_opex_per_scanner
                            + add_injection
                            * annual_opex_per_injection_room
                            + add_uptake
                            * annual_opex_per_uptake_room
                        )

                        add_financial_candidate(
                            "Conventional Upgrade",
                            throughput,
                            capex,
                            annual_opex,
                            upgrade_pct,
                            added_batches,
                            add_scanners,
                            add_injection,
                            add_uptake,
                            1,
                            manual_survival * 100.0,
                        )

    # Architecture 3: MRT Pharma Hybrid
    for upgrade_pct in upgrade_values:
        for added_batches in batch_values:
            release = (
                current_release_day
                * (1 + upgrade_pct / 100.0)
                + added_batches
                * released_gbq_per_batch
            )

            fdg_capacity = (
                release
                * 1000.0
                * mrt_survival
                / patient_dose_mbq
            )

            for node_count in range(
                1,
                maximum_clinical_nodes + 1,
            ):
                uplift = min(
                    maximum_distribution_uplift_pct,
                    distribution_uplift_per_node_pct
                    * node_count,
                )

                distribution_factor = min(
                    1.0,
                    baseline_distribution_efficiency_pct
                    / 100.0
                    + uplift
                    / 100.0,
                )

                transport_capacity = (
                    mrt_transport_capacity_per_node
                    * node_count
                )

                for add_scanners in scanner_values:
                    for add_injection in injection_values:
                        for add_uptake in uptake_values:
                            total_generated += 1
                            physically_evaluated += 1

                            effective_clinical_capacity = min(
                                (
                                    current_scanners
                                    + add_scanners
                                ) * patients_per_scanner,
                                (
                                    current_injection_rooms
                                    + add_injection
                                ) * patients_per_injection_room,
                                (
                                    current_uptake_rooms
                                    + add_uptake
                                ) * patients_per_uptake_room,
                            ) * distribution_factor

                            throughput = min(
                                effective_clinical_capacity,
                                transport_capacity,
                                fdg_capacity,
                            )

                            if throughput < target_patients:
                                continue

                            met_target += 1

                            capex = (
                                (
                                    upgrade_pct
                                    / 10.0
                                )
                                * hybrid_upgrade_capex_per_10pct
                                + mrt_capex
                                + node_count
                                * clinical_node_capex
                                + add_scanners
                                * scanner_capex
                                + add_injection
                                * injection_room_capex
                                + add_uptake
                                * uptake_room_capex
                            )

                            if capex > maximum_budget:
                                continue

                            within_budget += 1

                            annual_opex = (
                                annual_base_opex_hybrid
                                + annual_mrt_maintenance
                                + added_batches
                                * incremental_opex_per_batch
                                * operating_days
                                + add_scanners
                                * annual_opex_per_scanner
                                + add_injection
                                * annual_opex_per_injection_room
                                + add_uptake
                                * annual_opex_per_uptake_room
                            )

                            add_financial_candidate(
                                "MRT Pharma Hybrid",
                                throughput,
                                capex,
                                annual_opex,
                                upgrade_pct,
                                added_batches,
                                add_scanners,
                                add_injection,
                                add_uptake,
                                node_count,
                                mrt_survival * 100.0,
                            )

    rate = discount_rate_pct / 100.0

    for candidate in candidates:
        candidate["payback_years"] = safe_payback(
            candidate["capex"],
            candidate["annual_net"],
        )
        candidate["npv"] = calculate_npv(
            candidate["capex"],
            candidate["annual_net"],
            analysis_years,
            rate,
        )
        candidate["roi_pct"] = calculate_roi(
            candidate["capex"],
            candidate["annual_net"],
            analysis_years,
        )

        if candidate["incremental_patients_day"] > 0:
            candidate[
                "cost_per_incremental_patient"
            ] = (
                candidate["annual_opex"]
                / (
                    candidate["incremental_patients_day"]
                    * operating_days
                )
            )
        else:
            candidate[
                "cost_per_incremental_patient"
            ] = float("inf")

    positive_cash = [
        candidate
        for candidate in candidates
        if (
            candidate["annual_net"] > 0
            and math.isfinite(
                candidate["payback_years"]
            )
        )
    ]

    positive_npv = [
        candidate
        for candidate in positive_cash
        if candidate["npv"] > 0
    ]

    best_by_architecture: Dict[
        str,
        Optional[Dict[str, float]],
    ] = {}

    for architecture_name in [
        "New Cyclotron",
        "Conventional Upgrade",
        "MRT Pharma Hybrid",
    ]:
        rows = [
            candidate
            for candidate in positive_cash
            if candidate["architecture"]
            == architecture_name
        ]

        best_by_architecture[
            architecture_name
        ] = (
            max(
                rows,
                key=lambda candidate: (
                    candidate["npv"],
                    -candidate["capex"],
                ),
            )
            if rows
            else None
        )

    decision = (
        max(
            positive_cash,
            key=lambda candidate: (
                candidate["npv"],
                -candidate["capex"],
            ),
        )
        if positive_cash
        else None
    )

    st.markdown("### Digital Twin Results")
    result_columns = st.columns(4)

    def render_card(
        container,
        title: str,
        candidate: Optional[Dict[str, float]],
        decision_card: bool = False,
    ) -> None:
        css_class = (
            "result-card decision-card"
            if decision_card
            else "result-card"
        )

        if candidate:
            headline = (
                candidate["architecture"]
                if decision_card
                else f"${candidate['capex']:,.0f}"
            )

            if candidate["architecture"] == "New Cyclotron":
                production_detail = (
                    "<div><b>Existing cyclotron upgrade:</b> 0%</div>"
                    f"<div><b>New cyclotron added FDG capacity:</b> "
                    f"{new_cyclotron_release_capacity_gbq_day:,.1f} GBq/day</div>"
                )
                access_detail = "<div><b>MRT-connected access points:</b> Not applicable</div>"
            elif candidate["architecture"] == "Conventional Upgrade":
                production_detail = (
                    f"<div><b>Existing cyclotron production upgrade:</b> "
                    f"{candidate['upgrade_pct']}%</div>"
                )
                access_detail = "<div><b>MRT-connected access points:</b> Not applicable</div>"
            else:
                production_detail = (
                    f"<div><b>Existing cyclotron production upgrade:</b> "
                    f"{candidate['upgrade_pct']}%</div>"
                )
                access_detail = (
                    f"<div><b>MRT-connected access points:</b> "
                    f"{candidate['clinical_nodes']}</div>"
                )

            html = f"""
            <div class="{css_class}">
                <div class="card-title">{title}</div>
                <div class="big">{headline}</div>
                <hr>
                <div><b>Installed capacity:</b> {candidate['throughput']:.0f}/day</div>
                <div><b>Target patients served:</b> {candidate['served_patients_day']:.0f}/day</div>
                <div><b>Reserve capacity:</b> {candidate['reserve_capacity_day']:.0f}/day</div>
                <div><b>Incremental patients:</b> {candidate['incremental_patients_day']:.0f}/day</div>
                <div><b>CapEx:</b> ${candidate['capex']:,.0f}</div>
                <div><b>Annual OpEx:</b> ${candidate['annual_opex']:,.0f}</div>
                {production_detail}
                <div><b>Additional scanners:</b> {candidate['add_scanners']}</div>
                <div><b>Injection rooms added:</b> {candidate['add_injection']}</div>
                <div><b>Uptake rooms added:</b> {candidate['add_uptake']}</div>
                <div><b>Additional batches/day:</b> {candidate['added_batches']}</div>
                {access_detail}
                <div><b>Payback:</b> {candidate['payback_years']:.1f} years</div>
                <div><b>{analysis_years}-year ROI:</b> {candidate['roi_pct']:.1f}%</div>
                <div><b>NPV:</b> ${candidate['npv']:,.0f}</div>
            </div>
            """
        else:
            html = f"""
            <div class="{css_class}">
                <div class="card-title">{title}</div>
                <div class="big">NOT FEASIBLE</div>
                <hr>
                <div>
                    No configuration met the selected physical,
                    throughput, budget, and positive-cash-flow constraints.
                </div>
            </div>
            """

        container.markdown(
            html,
            unsafe_allow_html=True,
        )

    render_card(
        result_columns[0],
        "Option 1 — New Cyclotron",
        best_by_architecture["New Cyclotron"],
    )
    render_card(
        result_columns[1],
        "Option 2 — Conventional Upgrade",
        best_by_architecture["Conventional Upgrade"],
    )
    render_card(
        result_columns[2],
        "Option 3 — MRT Pharma Hybrid",
        best_by_architecture["MRT Pharma Hybrid"],
    )
    render_card(
        result_columns[3],
        "Digital Twin Decision",
        decision,
        decision_card=True,
    )

    st.markdown("### Digital Twin Search Space")
    m1, m2, m3, m4, m5 = st.columns(5)

    m1.metric(
        "Configurations generated",
        f"{total_generated:,}",
    )
    m2.metric(
        "Physically evaluated",
        f"{physically_evaluated:,}",
    )
    m3.metric(
        "Met throughput target",
        f"{met_target:,}",
    )
    m4.metric(
        "Within CapEx budget",
        f"{within_budget:,}",
    )
    m5.metric(
        "Positive NPV",
        f"{len(positive_npv):,}",
    )

    st.markdown(
        "### Discounted Break-even and Cumulative Cash Flow"
    )

    years = list(
        range(
            analysis_years + 1
        )
    )

    figure = go.Figure()

    for (
        architecture_name,
        candidate,
    ) in best_by_architecture.items():
        if candidate is None:
            continue

        figure.add_trace(
            go.Scatter(
                x=years,
                y=discounted_series(
                    candidate["capex"],
                    candidate["annual_net"],
                    analysis_years,
                    rate,
                ),
                mode="lines+markers",
                name=architecture_name,
            )
        )

    figure.add_hline(
        y=0,
        line_dash="dash",
        line_color="#d71920",
    )

    figure.update_layout(
        title=(
            "Discounted cumulative net cash flow "
            "by expansion architecture"
        ),
        xaxis_title="Year",
        yaxis_title=(
            "Discounted cumulative net cash flow (USD)"
        ),
        template="plotly_white",
        height=500,
        legend_title_text="Architecture",
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
    )

    st.markdown(
        "### Why the Digital Twin Selected This Architecture"
    )

    if decision:
        reasons = [
            (
                f"Serves the selected target of {target_patients} PET patients per day; "
                f"installed capacity is {decision['throughput']:.0f}/day."
            ),
            (
                f"Adds approximately "
                f"{decision['incremental_patients_day']:.0f} "
                f"patients per day above modeled baseline capacity."
            ),
            (
                f"Uses {decision['add_scanners']} additional scanners, "
                f"{decision['add_injection']} injection rooms, and "
                f"{decision['add_uptake']} uptake rooms."
            ),
            (
                f"Requires a {decision['upgrade_pct']}% production "
                f"upgrade and {decision['added_batches']} "
                f"additional batches per day."
            ),
            (
                f"Preserves "
                f"{decision['fdg_survival_pct']:.1f}% "
                f"of released FDG activity during modeled transport."
            ),
            (
                f"Has the highest modeled NPV among "
                f"positive-cash-flow configurations: "
                f"${decision['npv']:,.0f}."
            ),
            (
                f"Estimated payback period: "
                f"{decision['payback_years']:.1f} years."
            ),
        ]

        st.markdown(
            '<div class="rationale">'
            + "<br>".join(
                f"✓ {reason}"
                for reason in reasons
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    ranked = sorted(
        positive_cash,
        key=lambda candidate: (
            -candidate["npv"],
            candidate["capex"],
        ),
    )[:50]

    results_df = pd.DataFrame(
        [
            {
                "Architecture": candidate["architecture"],
                "Installed Capacity/Day": candidate["throughput"],
                "Target Patients Served/Day": candidate["served_patients_day"],
                "Reserve Capacity/Day": candidate["reserve_capacity_day"],
                "Incremental Patients/Day": candidate[
                    "incremental_patients_day"
                ],
                "CapEx (USD)": candidate["capex"],
                "Annual OpEx (USD)": candidate[
                    "annual_opex"
                ],
                "Annual Incremental Revenue (USD)": candidate[
                    "annual_incremental_revenue"
                ],
                "Annual Net Cash Flow (USD)": candidate[
                    "annual_net"
                ],
                "Upgrade (%)": candidate["upgrade_pct"],
                "Added Scanners": candidate[
                    "add_scanners"
                ],
                "Added Injection Rooms": candidate[
                    "add_injection"
                ],
                "Added Uptake Rooms": candidate[
                    "add_uptake"
                ],
                "Added Batches/Day": candidate[
                    "added_batches"
                ],
                "Clinical Access Points": candidate[
                    "clinical_nodes"
                ],
                "FDG Survival (%)": candidate[
                    "fdg_survival_pct"
                ],
                "Payback (Years)": candidate[
                    "payback_years"
                ],
                "ROI (%)": candidate["roi_pct"],
                "NPV (USD)": candidate["npv"],
                "Annual OpEx/Incremental Patient (USD)": candidate[
                    "cost_per_incremental_patient"
                ],
            }
            for candidate in ranked
        ]
    )

    assumptions_df = pd.DataFrame(
        [
            {
                "Assumption": "Modeled baseline throughput/day",
                "Value": current_throughput,
            },
            {
                "Assumption": "Target throughput/day",
                "Value": target_patients,
            },
            {
                "Assumption": "Revenue is capped at target demand",
                "Value": "Yes",
            },
            {
                "Assumption": "MRT speed (m/s)",
                "Value": MRT_SPEED_MPS,
            },
            {
                "Assumption": "Manual transport survival (%)",
                "Value": manual_survival * 100.0,
            },
            {
                "Assumption": "MRT transport survival (%)",
                "Value": mrt_survival * 100.0,
            },
            {
                "Assumption": "MRT uplift/access point (%)",
                "Value": distribution_uplift_per_node_pct,
            },
            {
                "Assumption": "Maximum MRT uplift (%)",
                "Value": maximum_distribution_uplift_pct,
            },
            {
                "Assumption": "Baseline distributed efficiency (%)",
                "Value": baseline_distribution_efficiency_pct,
            },
        ]
    )

    st.markdown(
        "### Top Ranked Configurations"
    )

    if not results_df.empty:
        st.dataframe(
            results_df.head(15),
            use_container_width=True,
            hide_index=True,
        )

        d1, d2 = st.columns(2)

        with d1:
            st.download_button(
                label="Download ranked results as CSV",
                data=results_df.to_csv(
                    index=False
                ).encode("utf-8"),
                file_name=(
                    "mrt_pharma_digital_twin_results.csv"
                ),
                mime="text/csv",
                use_container_width=True,
            )

        with d2:
            st.download_button(
                label=(
                    "Download results and assumptions as Excel"
                ),
                data=export_excel(
                    results_df,
                    assumptions_df,
                ),
                file_name=(
                    "mrt_pharma_digital_twin_results.xlsx"
                ),
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True,
            )
    else:
        st.warning(
            "No positive-cash-flow configurations were found. "
            "Review the demand, capacity, revenue, cost, and "
            "budget assumptions."
        )

    st.markdown(
        """
        <div class="footer">
            MRT Pharma™ Digital Twin demonstration model.
            Outputs are illustrative and depend on user-entered assumptions.
            The model evaluates 18F-FDG PET imaging, injection and uptake
            capacity, transport capacity, distributed clinical access points,
            CapEx, OpEx, incremental revenue, ROI, NPV, and discounted
            break-even. It is not a substitute for hospital engineering,
            clinical, financial, or regulatory validation.
        </div>
        """,
        unsafe_allow_html=True,
    )

else:
    st.info(
        "Complete the assumptions above and click "
        "**RUN MRT PHARMA DIGITAL TWIN**."
    )

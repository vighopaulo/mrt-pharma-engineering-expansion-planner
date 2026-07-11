import io
import math
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="MRT Pharma™ Digital Twin", page_icon="⚙️", layout="wide")

st.markdown(
    """
    <style>
    :root {--red:#d71920;--black:#111;--white:#fff;--line:#dedede;}
    .stApp {background:linear-gradient(135deg,#fff 0%,#f7f7f7 58%,#fff1f1 100%);}
    .block-container {max-width:1360px;padding-top:.75rem;padding-bottom:2rem;}
    .brand-shell,.panel{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px 24px;box-shadow:0 8px 24px rgba(17,17,17,.06);margin-bottom:12px;}
    .brand-row{display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap;}
    .brand-name{white-space:nowrap;font-size:2.65rem;font-weight:950;line-height:1;letter-spacing:-1.4px;}
    .brand-mrt{color:var(--black)} .brand-pharma{color:var(--red)}
    .product-name{font-size:1.6rem;font-weight:900;color:var(--black);margin-top:7px;}
    .tagline{text-align:right;font-weight:850;color:var(--black);font-size:1rem;}
    .subtagline{text-align:right;color:#666;font-size:.88rem;max-width:650px;}
    .red-rule{height:6px;border-radius:999px;background:linear-gradient(90deg,var(--red),#ff4c52);margin-top:13px;}
    .dark-panel{background:var(--black);color:#fff;border-radius:18px;padding:16px 20px 10px;box-shadow:0 8px 24px rgba(17,17,17,.13);margin-bottom:.9rem;}
    .result-card{border-radius:18px;padding:18px;min-height:390px;background:linear-gradient(135deg,#fff,#f2f2f2);border:1px solid rgba(17,17,17,.1);border-top:7px solid var(--red);box-shadow:0 8px 24px rgba(17,17,17,.08);}
    .decision-card{background:linear-gradient(135deg,#111,#2b2b2b);color:#fff;}
    .decision-card .card-title,.decision-card .big,.decision-card b{color:#fff;}
    .card-title{font-size:1.08rem;font-weight:900;color:#111;margin-bottom:.55rem;}
    .big{font-size:1.4rem;font-weight:950;color:#111;overflow-wrap:anywhere;}
    .rationale{background:#fff7f7;border-left:5px solid var(--red);border-radius:12px;padding:14px 16px;}
    .assumption-note{background:#fff8e8;border:1px solid #efd69e;border-radius:12px;padding:11px 14px;margin:8px 0 14px;font-size:.86rem;color:#4a3a13;}
    div[data-testid="stNumberInput"] label,div[data-testid="stSelectbox"] label{font-weight:700;color:#202020;}
    div[data-testid="stFormSubmitButton"]>button{background:linear-gradient(90deg,#a90f16,var(--red));color:#fff;font-weight:900;border-radius:12px;border:none;min-height:3rem;width:100%;}
    .footer{color:#666;font-size:.8rem;margin-top:10px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="brand-shell"><div class="brand-row"><div>
    <div class="brand-name"><span class="brand-mrt">MRT</span> <span class="brand-pharma">Pharma™</span></div>
    <div class="product-name">Digital Twin</div></div><div>
    <div class="tagline">Engineering Precision Oncology Today.</div>
    <div class="subtagline">Physics-based decision platform for distributed oncology infrastructure, radiopharmaceutical logistics, capacity planning, and lifecycle economics.</div>
    </div></div><div class="red-rule"></div></div>
    """,
    unsafe_allow_html=True,
)


def safe_payback(capex: float, annual_net: float) -> float:
    return capex / annual_net if annual_net > 0 else float("inf")


def calculate_npv(capex: float, annual_net: float, years: int, rate: float) -> float:
    return -capex + sum(annual_net / ((1 + rate) ** y) for y in range(1, years + 1))


def calculate_roi(capex: float, annual_net: float, years: int) -> float:
    return (((annual_net * years) - capex) / capex * 100) if capex > 0 else 0.0


def discounted_series(capex: float, annual_net: float, years: int, rate: float) -> List[float]:
    values = [-capex]
    total = -capex
    for year in range(1, years + 1):
        total += annual_net / ((1 + rate) ** year)
        values.append(total)
    return values


def export_excel(results: pd.DataFrame, assumptions: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        results.to_excel(writer, index=False, sheet_name="Ranked Configurations")
        assumptions.to_excel(writer, index=False, sheet_name="Assumptions")
    return buffer.getvalue()


with st.form("digital_twin_form"):
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 1. Scenario, Clinical Demand, and Distributed Oncology")
    scenario = st.selectbox("Scenario", ["Conservative", "Baseline", "Aggressive"], index=1)
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        current_scanners = st.number_input("Current PET scanners", 1, 30, 5, 1)
        target_patients = st.number_input("Target PET patients/day", 1, 2000, 200, 5)
    with a2:
        operating_hours = st.number_input("Operating hours/day", 1.0, 24.0, 18.0, .5)
        scan_minutes = st.number_input("Scanner occupation time/patient (min)", 5.0, 180.0, 30.0, 5.0)
    with a3:
        turnover_minutes = st.number_input("Turnover time/patient (min)", 0.0, 120.0, 15.0, 5.0)
        scanner_availability = st.number_input("Scanner availability (%)", 10.0, 100.0, 85.0, 1.0)
    with a4:
        max_additional_scanners = st.number_input("Maximum additional PET scanners", 0, 40, 12, 1)
        maximum_clinical_nodes = st.number_input("Maximum clinical access points", 1, 100, 8, 1)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 2. Injection, Uptake, FDG Production, and Transport")
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        current_injection_rooms = st.number_input("Current injection rooms", 1, 100, 6, 1)
        patients_per_injection_room = st.number_input("Patients/injection room/day", 1.0, 200.0, 30.0, 1.0)
    with b2:
        current_uptake_rooms = st.number_input("Current uptake rooms", 1, 200, 12, 1)
        patients_per_uptake_room = st.number_input("Patients/uptake room/day", 1.0, 100.0, 15.0, 1.0)
    with b3:
        max_additional_injection_rooms = st.number_input("Maximum additional injection rooms", 0, 100, 12, 1)
        max_additional_uptake_rooms = st.number_input("Maximum additional uptake rooms", 0, 200, 24, 1)
    with b4:
        manual_transport_capacity = st.number_input("Manual deliveries/day", 1.0, 5000.0, 220.0, 10.0)
        mrt_transport_capacity_per_node = st.number_input("MRT deliveries/node/day", 1.0, 5000.0, 120.0, 10.0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        eob_gbq_batch = st.number_input("18F activity at EOB/batch (GBq)", .1, 500.0, 30.0, 1.0)
        current_batches = st.number_input("Current FDG batches/day", 1, 12, 2, 1)
    with c2:
        synthesis_yield = st.number_input("Synthesis yield (%)", 1.0, 100.0, 75.0, 1.0)
        qc_yield = st.number_input("QC/release yield (%)", 1.0, 100.0, 95.0, 1.0)
    with c3:
        eob_release_min = st.number_input("EOB-to-release time (min)", 0.0, 240.0, 45.0, 5.0)
        patient_dose_mbq = st.number_input("FDG dose/patient (MBq)", 1.0, 1000.0, 300.0, 10.0)
    with c4:
        manual_transport_min = st.number_input("Manual delivery time (min)", 0.0, 120.0, 10.0, 1.0)
        mrt_distance_m = st.number_input("MRT distance to farthest node (m)", 0.0, 10000.0, 750.0, 50.0)

    d1, d2, d3, d4 = st.columns(4)
    with d1:
        mrt_load_dock_sec = st.number_input("MRT loading + docking (sec)", 0.0, 600.0, 50.0, 5.0)
    with d2:
        max_additional_batches = st.number_input("Maximum additional batches/day", 0, 10, 4, 1)
    with d3:
        max_upgrade_pct = st.number_input("Maximum cyclotron upgrade (%)", 0, 200, 100, 5)
    with d4:
        half_life_min = st.number_input("18F half-life (min)", 1.0, 500.0, 109.8, .1)

    st.markdown('<div class="assumption-note"><b>Distributed-workflow assumption:</b> The MRT workflow uplift is explicit and editable. It should be validated with hospital data.</div>', unsafe_allow_html=True)
    u1, u2, u3 = st.columns(3)
    with u1:
        distribution_uplift_per_node_pct = st.number_input("MRT workflow uplift/access point (%)", 0.0, 20.0, 2.0, .5)
    with u2:
        maximum_distribution_uplift_pct = st.number_input("Maximum MRT workflow uplift (%)", 0.0, 100.0, 18.0, 1.0)
    with u3:
        baseline_distribution_efficiency_pct = st.number_input("Initial distributed efficiency (%)", 1.0, 100.0, 82.0, 1.0)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="dark-panel">', unsafe_allow_html=True)
    st.markdown("### 3. CapEx, OpEx, Revenue, and Financial Assumptions")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        new_cyclotron_capex = st.number_input("New cyclotron + radiopharmacy CapEx (USD)", 0.0, 200_000_000.0, 15_000_000.0, 500_000.0, format="%.0f")
        new_cyclotron_release_capacity_gbq_day = st.number_input("New cyclotron released FDG capacity/day (GBq)", .1, 5000.0, 80.0, 5.0)
    with f2:
        scanner_capex = st.number_input("Additional PET scanner CapEx (USD)", 0.0, 20_000_000.0, 2_500_000.0, 100_000.0, format="%.0f")
        injection_room_capex = st.number_input("Additional injection room CapEx (USD)", 0.0, 10_000_000.0, 250_000.0, 25_000.0, format="%.0f")
    with f3:
        uptake_room_capex = st.number_input("Additional uptake room CapEx (USD)", 0.0, 10_000_000.0, 200_000.0, 25_000.0, format="%.0f")
        clinical_node_capex = st.number_input("Clinical access point CapEx (USD)", 0.0, 20_000_000.0, 400_000.0, 50_000.0, format="%.0f")
    with f4:
        pure_upgrade_capex_per_10pct = st.number_input("Conventional upgrade CapEx/10% (USD)", 0.0, 20_000_000.0, 650_000.0, 50_000.0, format="%.0f")
        hybrid_upgrade_capex_per_10pct = st.number_input("Hybrid upgrade CapEx/10% (USD)", 0.0, 20_000_000.0, 600_000.0, 50_000.0, format="%.0f")

    g1, g2, g3, g4 = st.columns(4)
    with g1:
        mrt_capex = st.number_input("MRT Pharma infrastructure CapEx (USD)", 0.0, 100_000_000.0, 6_000_000.0, 250_000.0, format="%.0f")
        revenue_per_incremental_patient = st.number_input("Net contribution/additional patient (USD)", 0.0, 100_000.0, 750.0, 25.0)
    with g2:
        annual_base_opex_new = st.number_input("Annual base OpEx — new cyclotron (USD)", 0.0, 100_000_000.0, 5_000_000.0, 100_000.0, format="%.0f")
        annual_base_opex_upgrade = st.number_input("Annual base OpEx — conventional upgrade (USD)", 0.0, 100_000_000.0, 3_800_000.0, 100_000.0, format="%.0f")
    with g3:
        annual_base_opex_hybrid = st.number_input("Annual base OpEx — MRT hybrid (USD)", 0.0, 100_000_000.0, 3_200_000.0, 100_000.0, format="%.0f")
        annual_mrt_maintenance = st.number_input("Annual MRT maintenance/support (USD)", 0.0, 50_000_000.0, 450_000.0, 50_000.0, format="%.0f")
    with g4:
        incremental_opex_per_batch = st.number_input("OpEx/additional batch (USD)", 0.0, 1_000_000.0, 8_000.0, 500.0)
        annual_opex_per_scanner = st.number_input("Annual OpEx/additional scanner (USD)", 0.0, 10_000_000.0, 300_000.0, 25_000.0, format="%.0f")

    h1, h2, h3, h4 = st.columns(4)
    with h1:
        annual_opex_per_injection_room = st.number_input("Annual OpEx/injection room (USD)", 0.0, 5_000_000.0, 90_000.0, 10_000.0, format="%.0f")
    with h2:
        annual_opex_per_uptake_room = st.number_input("Annual OpEx/uptake room (USD)", 0.0, 5_000_000.0, 70_000.0, 10_000.0, format="%.0f")
    with h3:
        operating_days = st.number_input("Operating days/year", 1, 365, 300, 5)
        analysis_years = st.number_input("Financial analysis period (years)", 1, 25, 10, 1)
    with h4:
        discount_rate_pct = st.number_input("Discount rate (%)", 0.0, 50.0, 10.0, .5)
        maximum_budget = st.number_input("Maximum available CapEx (USD)", 0.0, 500_000_000.0, 100_000_000.0, 1_000_000.0, format="%.0f")
    st.markdown("</div>", unsafe_allow_html=True)

    submitted = st.form_submit_button("RUN MRT PHARMA DIGITAL TWIN", use_container_width=True)


if submitted:
    MRT_SPEED_MPS = 50.0
    scenario_multipliers: Dict[str, Dict[str, float]] = {
        "Conservative": {"revenue": .90, "opex": 1.10, "availability": .95, "yield": .95},
        "Baseline": {"revenue": 1.00, "opex": 1.00, "availability": 1.00, "yield": 1.00},
        "Aggressive": {"revenue": 1.10, "opex": .95, "availability": 1.03, "yield": 1.03},
    }
    mult = scenario_multipliers[scenario]

    effective_availability = min(100.0, scanner_availability * mult["availability"])
    effective_synthesis_yield = min(100.0, synthesis_yield * mult["yield"])
    effective_qc_yield = min(100.0, qc_yield * mult["yield"])
    effective_revenue = revenue_per_incremental_patient * mult["revenue"]
    opex_multiplier = mult["opex"]

    scanner_cycle = scan_minutes + turnover_minutes
    patients_per_scanner = (operating_hours * 60.0 / scanner_cycle) * (effective_availability / 100.0)
    decay_to_release = 2 ** (-eob_release_min / half_life_min)
    released_gbq_per_batch = eob_gbq_batch * (effective_synthesis_yield / 100.0) * (effective_qc_yield / 100.0) * decay_to_release
    current_release_day = released_gbq_per_batch * current_batches
    manual_survival = 2 ** (-manual_transport_min / half_life_min)
    mrt_total_min = ((mrt_distance_m / MRT_SPEED_MPS) + mrt_load_dock_sec) / 60.0
    mrt_survival = 2 ** (-mrt_total_min / half_life_min)

    current_throughput = min(
        current_scanners * patients_per_scanner,
        current_injection_rooms * patients_per_injection_room,
        current_uptake_rooms * patients_per_uptake_room,
        manual_transport_capacity,
        current_release_day * 1000.0 * manual_survival / patient_dose_mbq,
    )

    candidates: List[Dict[str, float]] = []
    total_generated = physically_evaluated = met_target = within_budget = 0

    scanner_values = range(max_additional_scanners + 1)
    injection_values = range(max_additional_injection_rooms + 1)
    uptake_values = range(max_additional_uptake_rooms + 1)
    upgrade_values = range(0, max_upgrade_pct + 1, 5)
    batch_values = range(max_additional_batches + 1)

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
        incremental_patients = max(0.0, throughput - current_throughput)
        annual_incremental_revenue = incremental_patients * operating_days * effective_revenue
        annual_net = annual_incremental_revenue - annual_opex
        candidates.append({
            "architecture": architecture,
            "throughput": throughput,
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
        })

    # Architecture 1: New cyclotron
    for add_scanners in scanner_values:
        for add_injection in injection_values:
            for add_uptake in uptake_values:
                total_generated += 1
                physically_evaluated += 1
                throughput = min(
                    (current_scanners + add_scanners) * patients_per_scanner,
                    (current_injection_rooms + add_injection) * patients_per_injection_room,
                    (current_uptake_rooms + add_uptake) * patients_per_uptake_room,
                    manual_transport_capacity,
                    (current_release_day + new_cyclotron_release_capacity_gbq_day) * 1000.0 * manual_survival / patient_dose_mbq,
                )
                if throughput < target_patients:
                    continue
                met_target += 1
                capex = new_cyclotron_capex + add_scanners * scanner_capex + add_injection * injection_room_capex + add_uptake * uptake_room_capex
                if capex > maximum_budget:
                    continue
                within_budget += 1
                annual_opex = (annual_base_opex_new + add_scanners * annual_opex_per_scanner + add_injection * annual_opex_per_injection_room + add_uptake * annual_opex_per_uptake_room) * opex_multiplier
                add_financial_candidate("New Cyclotron", throughput, capex, annual_opex, 0, 0, add_scanners, add_injection, add_uptake, 1, manual_survival * 100.0)

    # Architecture 2: Conventional upgrade
    for upgrade_pct in upgrade_values:
        for added_batches in batch_values:
            release = current_release_day * (1 + upgrade_pct / 100.0) + added_batches * released_gbq_per_batch
            fdg_capacity = release * 1000.0 * manual_survival / patient_dose_mbq
            for add_scanners in scanner_values:
                for add_injection in injection_values:
                    for add_uptake in uptake_values:
                        total_generated += 1
                        physically_evaluated += 1
                        throughput = min(
                            (current_scanners + add_scanners) * patients_per_scanner,
                            (current_injection_rooms + add_injection) * patients_per_injection_room,
                            (current_uptake_rooms + add_uptake) * patients_per_uptake_room,
                            manual_transport_capacity,
                            fdg_capacity,
                        )
                        if throughput < target_patients:
                            continue
                        met_target += 1
                        capex = (upgrade_pct / 10.0) * pure_upgrade_capex_per_10pct + add_scanners * scanner_capex + add_injection * injection_room_capex + add_uptake * uptake_room_capex
                        if capex > maximum_budget:
                            continue
                        within_budget += 1
                        annual_opex = (
                            annual_base_opex_upgrade
                            + added_batches * incremental_opex_per_batch * operating_days
                            + add_scanners * annual_opex_per_scanner
                            + add_injection * annual_opex_per_injection_room
                            + add_uptake * annual_opex_per_uptake_room
                        ) * opex_multiplier
                        add_financial_candidate("Conventional Upgrade", throughput, capex, annual_opex, upgrade_pct, added_batches, add_scanners, add_injection, add_uptake, 1, manual_survival * 100.0)

    # Architecture 3: MRT Pharma hybrid
    for upgrade_pct in upgrade_values:
        for added_batches in batch_values:
            release = current_release_day * (1 + upgrade_pct / 100.0) + added_batches * released_gbq_per_batch
            fdg_capacity = release * 1000.0 * mrt_survival / patient_dose_mbq
            for node_count in range(1, maximum_clinical_nodes + 1):
                uplift = min(maximum_distribution_uplift_pct, distribution_uplift_per_node_pct * node_count)
                distribution_factor = min(1.0, baseline_distribution_efficiency_pct / 100.0 + uplift / 100.0)
                transport_capacity = mrt_transport_capacity_per_node * node_count
                for add_scanners in scanner_values:
                    for add_injection in injection_values:
                        for add_uptake in uptake_values:
                            total_generated += 1
                            physically_evaluated += 1
                            effective_clinical = min(
                                (current_scanners + add_scanners) * patients_per_scanner,
                                (current_injection_rooms + add_injection) * patients_per_injection_room,
                                (current_uptake_rooms + add_uptake) * patients_per_uptake_room,
                            ) * distribution_factor
                            throughput = min(effective_clinical, transport_capacity, fdg_capacity)
                            if throughput < target_patients:
                                continue
                            met_target += 1
                            capex = (
                                (upgrade_pct / 10.0) * hybrid_upgrade_capex_per_10pct
                                + mrt_capex
                                + node_count * clinical_node_capex
                                + add_scanners * scanner_capex
                                + add_injection * injection_room_capex
                                + add_uptake * uptake_room_capex
                            )
                            if capex > maximum_budget:
                                continue
                            within_budget += 1
                            annual_opex = (
                                annual_base_opex_hybrid
                                + annual_mrt_maintenance
                                + added_batches * incremental_opex_per_batch * operating_days
                                + add_scanners * annual_opex_per_scanner
                                + add_injection * annual_opex_per_injection_room
                                + add_uptake * annual_opex_per_uptake_room
                            ) * opex_multiplier
                            add_financial_candidate("MRT Pharma Hybrid", throughput, capex, annual_opex, upgrade_pct, added_batches, add_scanners, add_injection, add_uptake, node_count, mrt_survival * 100.0)

    rate = discount_rate_pct / 100.0
    for c in candidates:
        c["payback_years"] = safe_payback(c["capex"], c["annual_net"])
        c["npv"] = calculate_npv(c["capex"], c["annual_net"], analysis_years, rate)
        c["roi_pct"] = calculate_roi(c["capex"], c["annual_net"], analysis_years)
        c["cost_per_incremental_patient"] = c["annual_opex"] / (c["incremental_patients_day"] * operating_days) if c["incremental_patients_day"] > 0 else float("inf")

    positive_cash = [c for c in candidates if c["annual_net"] > 0 and math.isfinite(c["payback_years"])]
    positive_npv = [c for c in positive_cash if c["npv"] > 0]

    best_by_arch: Dict[str, Optional[Dict[str, float]]] = {}
    for arch in ["New Cyclotron", "Conventional Upgrade", "MRT Pharma Hybrid"]:
        rows = [c for c in positive_cash if c["architecture"] == arch]
        best_by_arch[arch] = max(rows, key=lambda x: (x["npv"], -x["capex"])) if rows else None

    decision = max(positive_cash, key=lambda x: (x["npv"], -x["capex"])) if positive_cash else None

    st.markdown("### Digital Twin Results")
    cols = st.columns(4)

    def render_card(container, title: str, c: Optional[Dict[str, float]], decision_card: bool = False) -> None:
        css = "result-card decision-card" if decision_card else "result-card"
        if c:
            headline = c["architecture"] if decision_card else f"${c['capex']:,.0f}"
            html = f'''<div class="{css}"><div class="card-title">{title}</div><div class="big">{headline}</div><hr>
            <div><b>Throughput:</b> {c['throughput']:.0f}/day</div><div><b>Incremental patients:</b> {c['incremental_patients_day']:.0f}/day</div>
            <div><b>CapEx:</b> ${c['capex']:,.0f}</div><div><b>Annual OpEx:</b> ${c['annual_opex']:,.0f}</div>
            <div><b>Upgrade:</b> {c['upgrade_pct']}%</div><div><b>Additional scanners:</b> {c['add_scanners']}</div>
            <div><b>Injection rooms added:</b> {c['add_injection']}</div><div><b>Uptake rooms added:</b> {c['add_uptake']}</div>
            <div><b>Additional batches/day:</b> {c['added_batches']}</div><div><b>Clinical access points:</b> {c['clinical_nodes']}</div>
            <div><b>Payback:</b> {c['payback_years']:.1f} years</div><div><b>{analysis_years}-year ROI:</b> {c['roi_pct']:.1f}%</div><div><b>NPV:</b> ${c['npv']:,.0f}</div></div>'''
        else:
            html = f'''<div class="{css}"><div class="card-title">{title}</div><div class="big">NOT FEASIBLE</div><hr><div>No configuration met the selected physical, throughput, budget, and positive-cash-flow constraints.</div></div>'''
        container.markdown(html, unsafe_allow_html=True)

    render_card(cols[0], "Option 1 — New Cyclotron", best_by_arch["New Cyclotron"])
    render_card(cols[1], "Option 2 — Conventional Upgrade", best_by_arch["Conventional Upgrade"])
    render_card(cols[2], "Option 3 — MRT Pharma Hybrid", best_by_arch["MRT Pharma Hybrid"])
    render_card(cols[3], "Digital Twin Decision", decision, True)

    st.markdown("### Digital Twin Search Space")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Configurations generated", f"{total_generated:,}")
    m2.metric("Physically evaluated", f"{physically_evaluated:,}")
    m3.metric("Met throughput target", f"{met_target:,}")
    m4.metric("Within CapEx budget", f"{within_budget:,}")
    m5.metric("Positive NPV", f"{len(positive_npv):,}")

    st.markdown("### Discounted Break-even and Cumulative Cash Flow")
    years = list(range(analysis_years + 1))
    fig = go.Figure()
    for arch, c in best_by_arch.items():
        if c:
            fig.add_trace(go.Scatter(x=years, y=discounted_series(c["capex"], c["annual_net"], analysis_years, rate), mode="lines+markers", name=arch))
    fig.add_hline(y=0, line_dash="dash", line_color="#d71920")
    fig.update_layout(title="Discounted cumulative net cash flow by expansion architecture", xaxis_title="Year", yaxis_title="Discounted cumulative net cash flow (USD)", template="plotly_white", height=500, legend_title_text="Architecture")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Why the Digital Twin Selected This Architecture")
    if decision:
        reasons = [
            f"Meets the target of {target_patients} PET patients per day.",
            f"Adds approximately {decision['incremental_patients_day']:.0f} patients/day above modeled baseline capacity.",
            f"Uses {decision['add_scanners']} scanners, {decision['add_injection']} injection rooms, and {decision['add_uptake']} uptake rooms.",
            f"Requires a {decision['upgrade_pct']}% production upgrade and {decision['added_batches']} additional batches/day.",
            f"Preserves {decision['fdg_survival_pct']:.1f}% of released FDG activity during modeled transport.",
            f"Has the highest modeled NPV among positive-cash-flow configurations: ${decision['npv']:,.0f}.",
            f"Estimated payback period: {decision['payback_years']:.1f} years.",
        ]
        st.markdown('<div class="rationale">' + '<br>'.join(f'✓ {r}' for r in reasons) + '</div>', unsafe_allow_html=True)

    ranked = sorted(positive_cash, key=lambda x: (-x["npv"], x["capex"]))[:50]
    results_df = pd.DataFrame([{
        "Scenario": scenario,
        "Architecture": c["architecture"],
        "Throughput/Day": c["throughput"],
        "Incremental Patients/Day": c["incremental_patients_day"],
        "CapEx (USD)": c["capex"],
        "Annual OpEx (USD)": c["annual_opex"],
        "Annual Incremental Revenue (USD)": c["annual_incremental_revenue"],
        "Annual Net Cash Flow (USD)": c["annual_net"],
        "Upgrade (%)": c["upgrade_pct"],
        "Added Scanners": c["add_scanners"],
        "Added Injection Rooms": c["add_injection"],
        "Added Uptake Rooms": c["add_uptake"],
        "Added Batches/Day": c["added_batches"],
        "Clinical Access Points": c["clinical_nodes"],
        "FDG Survival (%)": c["fdg_survival_pct"],
        "Payback (Years)": c["payback_years"],
        "ROI (%)": c["roi_pct"],
        "NPV (USD)": c["npv"],
        "Annual OpEx/Incremental Patient (USD)": c["cost_per_incremental_patient"],
    } for c in ranked])

    assumptions_df = pd.DataFrame([
        {"Assumption": "Scenario", "Value": scenario},
        {"Assumption": "Modeled baseline throughput/day", "Value": current_throughput},
        {"Assumption": "Target throughput/day", "Value": target_patients},
        {"Assumption": "MRT speed (m/s)", "Value": MRT_SPEED_MPS},
        {"Assumption": "Manual transport survival (%)", "Value": manual_survival * 100.0},
        {"Assumption": "MRT transport survival (%)", "Value": mrt_survival * 100.0},
        {"Assumption": "MRT uplift/access point (%)", "Value": distribution_uplift_per_node_pct},
        {"Assumption": "Maximum MRT uplift (%)", "Value": maximum_distribution_uplift_pct},
        {"Assumption": "Baseline distributed efficiency (%)", "Value": baseline_distribution_efficiency_pct},
    ])

    st.markdown("### Top Ranked Configurations")
    if not results_df.empty:
        st.dataframe(results_df.head(15), use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download ranked results as CSV", results_df.to_csv(index=False).encode("utf-8"), "mrt_pharma_digital_twin_results.csv", "text/csv", use_container_width=True)
        with c2:
            st.download_button("Download results and assumptions as Excel", export_excel(results_df, assumptions_df), "mrt_pharma_digital_twin_results.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    else:
        st.warning("No positive-cash-flow configurations were found. Review the demand, capacity, revenue, cost, and budget assumptions.")

    st.markdown('<div class="footer">MRT Pharma™ Digital Twin demonstration model. Outputs are illustrative and depend on user-entered assumptions. The model evaluates 18F-FDG PET imaging, injection and uptake capacity, transport capacity, distributed clinical access points, CapEx, OpEx, incremental revenue, ROI, NPV, and discounted break-even. It is not a substitute for hospital engineering, clinical, financial, or regulatory validation.</div>', unsafe_allow_html=True)
else:
    st.info("Complete the assumptions above and click **RUN MRT PHARMA DIGITAL TWIN**.")

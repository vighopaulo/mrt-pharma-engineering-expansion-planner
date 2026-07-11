
import math
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="MRT Pharma™ Hospital Capacity Optimizer",
    page_icon="⚙️",
    layout="wide",
)

st.markdown("""
<style>
:root {
    --mrt-red: #d71920;
    --mrt-black: #111111;
    --mrt-white: #ffffff;
    --mrt-border: #dddddd;
}
.stApp {
    background: linear-gradient(135deg, #ffffff 0%, #f7f7f7 58%, #fff3f3 100%);
}
.block-container {
    max-width: 1240px;
    padding-top: 1rem;
    padding-bottom: 1.6rem;
}
.brand-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 20px;
}
.brand-name {
    font-size: 2.6rem;
    font-weight: 950;
    letter-spacing: -1.4px;
    line-height: 1;
}
.brand-mrt { color: var(--mrt-black); }
.brand-pharma { color: var(--mrt-red); }
.tagline {
    text-align: right;
    color: var(--mrt-black);
    font-weight: 800;
    font-size: 1rem;
}
.subtagline {
    text-align: right;
    color: #666666;
    font-size: .88rem;
}
.red-rule {
    height: 6px;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--mrt-red), #ff4f55);
    margin: 7px 0 16px;
}
.panel {
    background: var(--mrt-white);
    border: 1px solid var(--mrt-border);
    border-radius: 18px;
    padding: 18px 20px 10px;
    box-shadow: 0 8px 24px rgba(17,17,17,.06);
    margin-bottom: .9rem;
}
.dark-panel {
    background: var(--mrt-black);
    color: var(--mrt-white);
    border-radius: 18px;
    padding: 16px 20px 10px;
    box-shadow: 0 8px 24px rgba(17,17,17,.13);
    margin-bottom: .9rem;
}
.result-card {
    border-radius: 18px;
    padding: 20px;
    min-height: 340px;
    border: 1px solid rgba(17,17,17,.10);
    box-shadow: 0 8px 24px rgba(17,17,17,.08);
}
.option-card {
    background: linear-gradient(135deg, #ffffff, #f1f1f1);
    border-top: 7px solid var(--mrt-red);
}
.decision-card {
    background: linear-gradient(135deg, var(--mrt-black), #2b2b2b);
    color: var(--mrt-white);
    border-top: 7px solid var(--mrt-red);
}
.decision-card .card-title,
.decision-card .big,
.decision-card .small,
.decision-card b {
    color: var(--mrt-white);
}
.card-title {
    font-size: 1.18rem;
    font-weight: 900;
    color: var(--mrt-black);
    margin-bottom: .55rem;
}
.big {
    font-size: 1.62rem;
    font-weight: 950;
    color: var(--mrt-black);
}
.small {
    font-size: .86rem;
    color: #5b5b5b;
}
.rationale {
    background: #fff7f7;
    border-left: 5px solid var(--mrt-red);
    border-radius: 12px;
    padding: 14px 16px;
    margin-top: 12px;
}
div[data-testid="stNumberInput"] label {
    font-weight: 700;
    color: #202020;
}
div.stButton > button {
    background: linear-gradient(90deg, #a90f16, var(--mrt-red));
    color: var(--mrt-white);
    font-weight: 900;
    border-radius: 12px;
    border: none;
    height: 3rem;
}
div.stButton > button:hover {
    background: linear-gradient(90deg, #850b10, #bd1118);
    color: var(--mrt-white);
}
.footer-note {
    margin-top: 10px;
    font-size: .82rem;
    color: #5b5b5b;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="brand-row">
    <div class="brand-name">
        <span class="brand-mrt">MRT</span>
        <span class="brand-pharma">Pharma™</span>
    </div>
    <div>
        <div class="tagline">Engineering Precision Oncology Today.</div>
        <div class="subtagline">Operations Research Platform for PET Capacity Planning, FDG Logistics, and Capital Optimization</div>
    </div>
</div>
<div class="red-rule"></div>
""", unsafe_allow_html=True)

st.markdown("## MRT Pharma™ Hospital Capacity Optimizer")
st.caption("Version 2 — physics-linked capacity modeling with integrated CapEx optimization")

st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown("### 1. Hospital Operations and Demand")
c1, c2, c3, c4 = st.columns(4)

with c1:
    current_scanners = st.number_input("Current PET scanners", min_value=1, value=5, step=1)
    target_patients = st.number_input("Target PET patients/day", min_value=1, value=200, step=5)

with c2:
    operating_hours = st.number_input("Operating hours/day", min_value=1.0, max_value=24.0, value=18.0, step=0.5)
    scan_minutes = st.number_input("Scanner occupation time/patient (min)", min_value=5.0, value=30.0, step=5.0)

with c3:
    turnover_minutes = st.number_input("Turnover time/patient (min)", min_value=0.0, value=15.0, step=5.0)
    scanner_availability = st.number_input("Scanner availability (%)", min_value=10.0, max_value=100.0, value=85.0, step=5.0)

with c4:
    max_additional_scanners = st.number_input("Maximum additional PET scanners", min_value=0, value=10, step=1)
    max_upgrade_pct = st.number_input("Maximum existing-cyclotron upgrade (%)", min_value=0, max_value=200, value=100, step=10)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown("### 2. FDG Production, Processing, and Transport")
p1, p2, p3, p4 = st.columns(4)

with p1:
    eob_gbq_per_batch = st.number_input("18F activity at end of bombardment/batch (GBq)", min_value=0.1, value=30.0, step=1.0)
    current_batches_per_day = st.number_input("Current FDG batches/day", min_value=1, value=2, step=1)

with p2:
    synthesis_yield_pct = st.number_input("Synthesis yield (%)", min_value=1.0, max_value=100.0, value=75.0, step=1.0)
    qc_release_yield_pct = st.number_input("QC/release yield (%)", min_value=1.0, max_value=100.0, value=95.0, step=1.0)

with p3:
    production_to_release_min = st.number_input("EOB-to-release time (min)", min_value=0.0, value=45.0, step=5.0)
    patient_dose_mbq = st.number_input("FDG dose per patient (MBq)", min_value=1.0, value=300.0, step=10.0)

with p4:
    manual_transport_minutes = st.number_input("Manual delivery time (min)", min_value=0.0, value=10.0, step=1.0)
    mrt_distance_m = st.number_input("MRT Pharma distance to scanner wing (m)", min_value=0.0, value=750.0, step=50.0)

q1, q2, q3, q4 = st.columns(4)

with q1:
    mrt_load_dock_seconds = st.number_input("MRT loading + docking time (sec)", min_value=0.0, value=50.0, step=5.0)

with q2:
    max_additional_batches = st.number_input("Maximum additional batches/day", min_value=0, value=3, step=1)

with q3:
    added_release_per_10pct_gbq_day = st.number_input(
        "Added released activity per 10% upgrade (GBq/day)",
        min_value=0.1,
        value=4.0,
        step=0.5,
    )

with q4:
    half_life_min = st.number_input("18F half-life (min)", min_value=1.0, value=109.8, step=0.1)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="dark-panel">', unsafe_allow_html=True)
st.markdown("### 3. CapEx Assumptions")
k1, k2, k3, k4 = st.columns(4)

with k1:
    new_cyclotron_cost = st.number_input(
        "New cyclotron + radiopharmacy (USD)",
        min_value=0.0,
        value=15_000_000.0,
        step=500_000.0,
        format="%.0f",
    )

with k2:
    scanner_cost = st.number_input(
        "Additional PET scanner (USD)",
        min_value=0.0,
        value=2_500_000.0,
        step=100_000.0,
        format="%.0f",
    )

with k3:
    upgrade_cost_per_10pct = st.number_input(
        "Cyclotron upgrade per 10% (USD)",
        min_value=0.0,
        value=600_000.0,
        step=50_000.0,
        format="%.0f",
    )

with k4:
    mrt_capex = st.number_input(
        "MRT Pharma infrastructure CapEx (USD)",
        min_value=0.0,
        value=6_000_000.0,
        step=250_000.0,
        format="%.0f",
    )

st.markdown("</div>", unsafe_allow_html=True)

run = st.button("RUN MRT PHARMA OPTIMIZATION", type="primary", use_container_width=True)

if run:
    MRT_SPEED_MPS = 50.0

    scanner_cycle_min = scan_minutes + turnover_minutes
    patients_per_scanner = (
        operating_hours * 60.0 / scanner_cycle_min
    ) * (scanner_availability / 100.0)
    current_scanner_capacity = current_scanners * patients_per_scanner

    decay_to_release = 2 ** (-production_to_release_min / half_life_min)
    released_gbq_per_batch = (
        eob_gbq_per_batch
        * (synthesis_yield_pct / 100.0)
        * (qc_release_yield_pct / 100.0)
        * decay_to_release
    )
    current_released_gbq_day = released_gbq_per_batch * current_batches_per_day

    manual_survival = 2 ** (-manual_transport_minutes / half_life_min)
    mrt_total_minutes = (
        (mrt_distance_m / MRT_SPEED_MPS) + mrt_load_dock_seconds
    ) / 60.0
    mrt_survival = 2 ** (-mrt_total_minutes / half_life_min)

    current_fdg_capacity = (
        current_released_gbq_day * 1000.0 * manual_survival / patient_dose_mbq
    )
    current_modeled_throughput = min(current_scanner_capacity, current_fdg_capacity)

    candidates = []

    for add_scanners in range(max_additional_scanners + 1):
        total_scanners = current_scanners + add_scanners
        scanner_capacity = total_scanners * patients_per_scanner

        if scanner_capacity < target_patients:
            continue

        required_release_gbq_day = (
            target_patients * patient_dose_mbq / manual_survival / 1000.0
        )
        added_release_gbq_day = max(
            0.0,
            required_release_gbq_day - current_released_gbq_day,
        )

        capex = new_cyclotron_cost + add_scanners * scanner_cost

        candidates.append({
            "architecture": "New Cyclotron",
            "capex": capex,
            "add_scanners": add_scanners,
            "upgrade_pct": 0,
            "added_batches": 0,
            "throughput": min(scanner_capacity, target_patients),
            "scanner_capacity": scanner_capacity,
            "fdg_capacity": target_patients,
            "added_release_gbq_day": added_release_gbq_day,
            "transport_survival": manual_survival,
        })

    for upgrade_pct in range(0, max_upgrade_pct + 1, 10):
        upgrade_added_gbq_day = (
            upgrade_pct / 10.0
        ) * added_release_per_10pct_gbq_day

        for added_batches in range(max_additional_batches + 1):
            release_gbq_day = (
                current_released_gbq_day
                + upgrade_added_gbq_day
                + added_batches * released_gbq_per_batch
            )

            fdg_capacity = (
                release_gbq_day * 1000.0 * mrt_survival / patient_dose_mbq
            )

            for add_scanners in range(max_additional_scanners + 1):
                total_scanners = current_scanners + add_scanners
                scanner_capacity = total_scanners * patients_per_scanner
                throughput = min(scanner_capacity, fdg_capacity)

                if throughput < target_patients:
                    continue

                capex = (
                    upgrade_pct / 10.0 * upgrade_cost_per_10pct
                    + mrt_capex
                    + add_scanners * scanner_cost
                )

                candidates.append({
                    "architecture": "Hybrid MRT Pharma",
                    "capex": capex,
                    "add_scanners": add_scanners,
                    "upgrade_pct": upgrade_pct,
                    "added_batches": added_batches,
                    "throughput": throughput,
                    "scanner_capacity": scanner_capacity,
                    "fdg_capacity": fdg_capacity,
                    "added_release_gbq_day": release_gbq_day - current_released_gbq_day,
                    "transport_survival": mrt_survival,
                })

    candidates.sort(key=lambda x: (x["capex"], -x["throughput"]))

    best = candidates[0] if candidates else None
    best_new = next((x for x in candidates if x["architecture"] == "New Cyclotron"), None)
    best_hybrid = next((x for x in candidates if x["architecture"] == "Hybrid MRT Pharma"), None)

    st.markdown("### Optimization Results")
    r1, r2, r3 = st.columns(3)

    with r1:
        if best_new:
            st.markdown(
                f"""
                <div class="result-card option-card">
                    <div class="card-title">Option 1 — New Cyclotron</div>
                    <div class="small">Least-CapEx feasible conventional expansion</div>
                    <div class="big">${best_new['capex']:,.0f}</div>
                    <hr>
                    <div><b>Additional PET scanners:</b> {best_new['add_scanners']}</div>
                    <div><b>Added released FDG capacity:</b> {best_new['added_release_gbq_day']:.1f} GBq/day</div>
                    <div><b>Scanner capacity:</b> {best_new['scanner_capacity']:.0f}/day</div>
                    <div><b>Target throughput:</b> {target_patients}/day</div>
                    <div><b>Status:</b> Feasible</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="result-card option-card">
                    <div class="card-title">Option 1 — New Cyclotron</div>
                    <div class="big">NOT FEASIBLE</div>
                    <hr>
                    <div>The scanner search limit is too low for the selected target.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with r2:
        if best_hybrid:
            st.markdown(
                f"""
                <div class="result-card option-card">
                    <div class="card-title">Option 2 — Hybrid MRT Pharma</div>
                    <div class="small">Least-CapEx feasible distributed expansion</div>
                    <div class="big">${best_hybrid['capex']:,.0f}</div>
                    <hr>
                    <div><b>Cyclotron upgrade:</b> {best_hybrid['upgrade_pct']}%</div>
                    <div><b>Additional batches/day:</b> {best_hybrid['added_batches']}</div>
                    <div><b>Additional PET scanners:</b> {best_hybrid['add_scanners']}</div>
                    <div><b>Modeled throughput:</b> {best_hybrid['throughput']:.0f}/day</div>
                    <div><b>MRT Pharma FDG survival:</b> {best_hybrid['transport_survival']*100:.1f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="result-card option-card">
                    <div class="card-title">Option 2 — Hybrid MRT Pharma</div>
                    <div class="big">NOT FEASIBLE</div>
                    <hr>
                    <div>No hybrid combination reached the target within the selected limits.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with r3:
        if best:
            alternative = best_new if best["architecture"] == "Hybrid MRT Pharma" else best_hybrid
            savings_text = ""
            if alternative:
                savings = alternative["capex"] - best["capex"]
                savings_text = f"Modeled CapEx advantage: ${savings:,.0f}."

            st.markdown(
                f"""
                <div class="result-card decision-card">
                    <div class="card-title">Optimizer Decision</div>
                    <div class="big">{best['architecture'].upper()}</div>
                    <hr>
                    <div>{savings_text}</div>
                    <div style="margin-top:10px;"><b>Current modeled throughput:</b> {current_modeled_throughput:.0f}/day</div>
                    <div><b>Target:</b> {target_patients}/day</div>
                    <div><b>Feasible configurations tested:</b> {len(candidates):,}</div>
                    <div><b>Decision rule:</b> lowest CapEx among feasible configurations</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="result-card decision-card">
                    <div class="card-title">Optimizer Decision</div>
                    <div class="big">NO FEASIBLE CONFIGURATION</div>
                    <hr>
                    <div>Increase the scanner limit, upgrade limit, or additional batch limit.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("### Capacity Diagnostics")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Current scanner capacity", f"{current_scanner_capacity:.0f}/day")
    d2.metric("Current FDG dose capacity", f"{current_fdg_capacity:.0f}/day")
    d3.metric("Manual FDG survival", f"{manual_survival*100:.1f}%")
    d4.metric("MRT Pharma FDG survival", f"{mrt_survival*100:.1f}%")

    st.markdown("### Decision Rationale")
    if best:
        rationale = [
            f"Meets or exceeds the target of {target_patients} PET patients/day.",
            f"Uses {best['add_scanners']} additional PET scanners.",
            f"Requires a {best['upgrade_pct']}% existing-cyclotron upgrade.",
            f"Uses {best['added_batches']} additional FDG batches/day.",
            f"Provides {best['transport_survival']*100:.1f}% modeled activity survival during transport.",
            "Has the lowest modeled CapEx among all feasible configurations searched.",
        ]
        st.markdown(
            '<div class="rationale">' +
            "<br>".join([f"✓ {item}" for item in rationale]) +
            "</div>",
            unsafe_allow_html=True,
        )

    if candidates:
        rows = []
        for row in candidates[:15]:
            rows.append({
                "Architecture": row["architecture"],
                "CapEx (USD)": row["capex"],
                "Cyclotron upgrade (%)": row["upgrade_pct"],
                "Added batches/day": row["added_batches"],
                "Additional scanners": row["add_scanners"],
                "Throughput/day": row["throughput"],
            })

        st.markdown("### Top Feasible Configurations")
        df = pd.DataFrame(rows)
        st.dataframe(
            df.style.format({
                "CapEx (USD)": "${:,.0f}",
                "Throughput/day": "{:,.0f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(
        '<div class="footer-note">'
        'MRT Pharma™ demonstration model only. Released FDG activity is derived from end-of-bombardment activity, '
        'synthesis yield, QC/release yield, and radioactive decay. The model excludes OpEx, staffing, uptake-room '
        'capacity, injection-room capacity, maintenance, financing, and hospital-specific regulatory constraints.'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    st.info("Adjust the inputs, then click **RUN MRT PHARMA OPTIMIZATION**.")

from __future__ import annotations

import io
from dataclasses import asdict
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from model import Inputs, run_comparison

st.set_page_config(
    page_title="MRT Pharma™ Decision-Support Digital Twin",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root{--red:#d71920;--black:#111;--ink:#242833;--muted:#6d727c;--line:#e1e4e8;--green:#24984a;--green-soft:#eaf8ef}
    [data-testid="stHeader"]{background:rgba(255,255,255,.90);backdrop-filter:blur(10px)}
    .stApp{background:radial-gradient(circle at top right,#fff1f2 0,transparent 34%),linear-gradient(180deg,#fff 0%,#f6f7f9 100%)}
    .block-container{max-width:1280px;padding-top:2.4rem!important;padding-bottom:3rem}
    .brand-shell{background:#fff;border:1px solid var(--line);border-radius:24px;padding:24px 28px 20px;margin-bottom:16px;box-shadow:0 16px 42px rgba(20,24,35,.08)}
    .brand-row{display:flex;justify-content:space-between;align-items:center;gap:28px;flex-wrap:wrap}
    .brand-name{font-size:2.62rem;font-weight:950;line-height:1.05;white-space:nowrap;letter-spacing:-1.2px}
    .brand-mrt{color:var(--black)}.brand-pharma{color:var(--red)}
    .tm{position:relative;top:-.82em;font-size:.32em;color:var(--red);font-weight:900}
    .product{margin-top:8px;font-size:1.42rem;font-weight:900;color:var(--black)}
    .tagline{text-align:right;font-weight:900;color:var(--black)}
    .subtagline{max-width:650px;margin-top:6px;text-align:right;color:#666b75;font-size:.9rem;line-height:1.48}
    .red-rule{height:6px;margin-top:17px;border-radius:999px;background:linear-gradient(90deg,var(--red),#ff4b52)}
    .section-head{margin:8px 0 12px}.step{display:inline-block;padding:4px 9px;border-radius:999px;background:#111;color:#fff;font-size:.72rem;font-weight:900;letter-spacing:.5px}
    .section-title{margin:4px 0;font-size:1.38rem;font-weight:950;color:var(--ink)}.section-help{color:var(--muted);font-size:.86rem}
    .result-card{min-height:270px;padding:21px;border:1px solid var(--line);border-top:7px solid var(--red);border-radius:22px;background:linear-gradient(145deg,#fff,#f6f7f9);box-shadow:0 14px 34px rgba(20,24,35,.075)}
    .winner-card{border:2px solid var(--green);border-top:8px solid var(--green);background:linear-gradient(145deg,#f6fff8,var(--green-soft));box-shadow:0 16px 38px rgba(36,152,74,.18)}
    .card-title{font-size:1.12rem;font-weight:950;color:var(--ink)}.card-subtitle{margin-top:3px;color:#737985;font-size:.83rem}
    .winner-badge{display:inline-block;margin-top:10px;padding:5px 11px;border-radius:999px;background:var(--green);color:#fff;font-size:.78rem;font-weight:950}
    .hero-value{margin-top:14px;font-size:1.74rem;font-weight:950;color:#111;letter-spacing:-.5px}
    .metric-line{display:flex;justify-content:space-between;gap:12px;margin-top:9px;padding-top:9px;border-top:1px solid rgba(0,0,0,.07);font-size:.92rem}.metric-line span:last-child{font-weight:900;text-align:right}
    .decision{margin:16px 0 12px;padding:18px 22px;border-radius:18px;background:linear-gradient(135deg,#111,#2b2e34);color:#fff;box-shadow:0 12px 30px rgba(17,17,17,.17)}
    .decision-kicker{font-size:.78rem;font-weight:900;letter-spacing:.6px;color:#c8ccd4}.decision-name{margin-top:4px;font-size:1.45rem;font-weight:950}.decision-copy{margin-top:6px;color:#e3e5e9;line-height:1.45}
    .reason-box{background:#fff7f7;border-left:5px solid var(--red);border-radius:13px;padding:14px 16px;line-height:1.55}
    div[data-testid="stFormSubmitButton"]>button{width:100%;min-height:3.15rem;border:none;border-radius:14px;background:linear-gradient(90deg,#a80f15,var(--red));color:#fff;font-weight:950;box-shadow:0 9px 24px rgba(215,25,32,.20)}
    .footer{margin-top:16px;color:#6c717c;font-size:.78rem;line-height:1.45}
    @media(max-width:900px){.brand-name{font-size:2.15rem}.tagline,.subtagline{text-align:left}.result-card{min-height:auto}}
    </style>
    """,
    unsafe_allow_html=True,
)

brand_header_html = (
    '<div class="brand-shell"><div class="brand-row"><div>'
    '<div class="brand-name"><span class="brand-mrt">MRT</span> '
    '<span class="brand-pharma">Pharma</span><span class="tm">™</span></div>'
    '<div class="product">Decision-Support Digital Twin</div></div><div>'
    '<div class="tagline">Engineering Distributed Precision Oncology Today.</div>'
    '<div class="subtagline">A physics-informed planning model comparing proportional conventional expansion with an optimized MRT Pharma distributed workflow.</div>'
    '</div></div><div class="red-rule"></div></div>'
)
st.markdown(brand_header_html, unsafe_allow_html=True)

PRESETS: dict[str, dict[str, Any]] = {
    "Balanced hospital case": {},
    "Conventional-favoring demonstration": {
        "target_patients": 65, "conventional_delivery_time": 3.0,
        "max_mrt_inpatient_rooms": 2, "capex_mrt_core": 9_000_000.0,
        "capex_conv_upgrade_per_10pct": 150_000.0,
    },
    "MRT-favoring distributed expansion": {
        "target_patients": 220, "conventional_delivery_time": 45.0,
        "mrt_delivery_time": 4.0, "current_doses_per_batch": 60.0,
        "patients_per_dedicated_room": 10.0, "max_mrt_batches_per_day": 4,
        "max_mrt_inpatient_rooms": 200, "capex_per_dedicated_room": 400_000.0,
        "capex_conv_upgrade_per_10pct": 900_000.0,
        "capex_mrt_upgrade_per_10pct": 400_000.0,
        "capex_mrt_core": 2_500_000.0, "max_capex_budget": 90_000_000.0,
        "opex_base_conventional": 250_000.0, "opex_base_mrt": 250_000.0,
        "opex_mrt_maintenance": 350_000.0, "opex_per_endpoint": 2_000.0,
        "net_contribution_per_patient": 650.0, "operating_days_per_year": 250,
    },
    "Neither-feasible stress test": {
        "target_patients": 5000, "current_scanners": 1,
        "max_mrt_batches_per_day": 2, "max_mrt_inpatient_rooms": 3,
        "max_additional_mrt_dedicated_rooms": 1, "max_capex_budget": 2_000_000.0,
    },
}

base = {
    "current_patients": 50.0, "target_patients": 200.0, "current_scanners": 2,
    "operating_hours": 18.0, "scanner_cycle_min": 35.0, "scanner_availability": 85.0,
    "current_injection_rooms": 6, "current_uptake_rooms": 6,
    "patients_per_dedicated_room": 30.0, "current_doses_per_batch": 120.0,
    "conventional_delivery_time": 20.0, "mrt_delivery_time": 1.0,
    "isotope_half_life": 109.8, "max_mrt_batches_per_day": 4,
    "max_mrt_inpatient_rooms": 40, "patients_per_mrt_inpatient_room": 1.0,
    "max_additional_mrt_dedicated_rooms": 6, "supporting_mrt_destinations": 2,
    "capex_per_scanner": 2_500_000.0, "capex_per_dedicated_room": 250_000.0,
    "capex_conv_upgrade_per_10pct": 650_000.0, "capex_mrt_upgrade_per_10pct": 600_000.0,
    "capex_mrt_core": 6_000_000.0, "capex_per_endpoint": 10_000.0,
    "max_capex_budget": 100_000_000.0, "net_contribution_per_patient": 750.0,
    "opex_base_conventional": 2_000_000.0, "opex_base_mrt": 1_500_000.0,
    "opex_per_additional_scanner": 300_000.0,
    "opex_per_additional_dedicated_room": 80_000.0,
    "opex_mrt_maintenance": 450_000.0, "opex_per_endpoint": 5_000.0,
    "annual_cost_per_extra_daily_batch": 500_000.0,
    "operating_days_per_year": 300, "analysis_period_years": 10,
    "discount_rate": 10.0,
}

preset_name = st.selectbox("Demonstration preset", list(PRESETS), index=0)
def dv(key: str):
    return PRESETS[preset_name].get(key, base[key])

with st.form("digital_twin_form"):
    st.markdown('<div class="section-head"><span class="step">STEP 1</span><div class="section-title">Hospital Today and Expansion Goal</div><div class="section-help">Enter present capacity and the future patient target.</div></div>', unsafe_allow_html=True)
    a1,a2,a3,a4=st.columns(4)
    with a1:
        current_patients=st.number_input("Current patients served/day",1.0,5000.0,float(dv("current_patients")),5.0)
        target_patients=st.number_input("Target patients/day",1.0,10000.0,float(dv("target_patients")),5.0)
    with a2:
        current_scanners=st.number_input("Current PET scanners",1,50,int(dv("current_scanners")),1)
        operating_hours=st.number_input("Operating hours/day",1.0,24.0,float(dv("operating_hours")),.5)
    with a3:
        scanner_cycle_min=st.number_input("Average scanner cycle/patient (min)",5.0,180.0,float(dv("scanner_cycle_min")),5.0)
        scanner_availability_pct=st.number_input("Scanner availability (%)",10.0,100.0,float(dv("scanner_availability")),1.0)
    with a4:
        current_injection_rooms=st.number_input("Current injection rooms",1,200,int(dv("current_injection_rooms")),1)
        current_uptake_rooms=st.number_input("Current uptake rooms",1,200,int(dv("current_uptake_rooms")),1)
    b1,b2=st.columns(2)
    with b1:
        patients_per_dedicated_room=st.number_input("Patients supported per dedicated room/day",1.0,100.0,float(dv("patients_per_dedicated_room")),1.0)
    with b2:
        current_doses_per_batch=st.number_input("Usable patient doses at batch release",1.0,5000.0,float(dv("current_doses_per_batch")),5.0,help="Complete patient doses routinely available immediately after release, before internal transport decay.")

    st.markdown('<div class="section-head"><span class="step">STEP 2</span><div class="section-title">Transport and MRT Limits</div><div class="section-help">Conventional uses one batch. The MRT optimizer selects its production increase, batch count and room mix.</div></div>', unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4)
    with c1:
        conventional_delivery_time=st.number_input("Conventional delivery time (min)",0.0,240.0,float(dv("conventional_delivery_time")),1.0)
        mrt_delivery_time=st.number_input("MRT delivery time (min)",0.0,60.0,float(dv("mrt_delivery_time")),.5)
    with c2:
        isotope_half_life=st.number_input("Isotope half-life (min)",1.0,10000.0,float(dv("isotope_half_life")),.1)
        max_mrt_batches_per_day=st.number_input("Maximum MRT batches/day",1,10,int(dv("max_mrt_batches_per_day")),1)
    with c3:
        max_mrt_inpatient_rooms=st.number_input("Maximum MRT-enabled inpatient rooms",0,1000,int(dv("max_mrt_inpatient_rooms")),1)
        patients_per_mrt_inpatient_room=st.number_input("Patients/MRT inpatient room/day",.1,10.0,float(dv("patients_per_mrt_inpatient_room")),.1)
    with c4:
        max_additional_mrt_dedicated_rooms=st.number_input("Maximum additional MRT dedicated rooms",0,200,int(dv("max_additional_mrt_dedicated_rooms")),1)
        supporting_mrt_destinations=st.number_input("Supporting MRT destinations",0,100,int(dv("supporting_mrt_destinations")),1)

    st.markdown('<div class="section-head"><span class="step">STEP 3</span><div class="section-title">Economics</div><div class="section-help">Both options receive the same target-volume revenue. Lifecycle differences determine the winner.</div></div>', unsafe_allow_html=True)
    d1,d2,d3,d4=st.columns(4)
    with d1:
        capex_per_scanner=st.number_input("CapEx/additional PET scanner (USD)",0.0,50_000_000.0,float(dv("capex_per_scanner")),100_000.0,format="%.0f")
        capex_per_dedicated_room=st.number_input("CapEx/additional dedicated room (USD)",0.0,10_000_000.0,float(dv("capex_per_dedicated_room")),25_000.0,format="%.0f")
    with d2:
        capex_conv_upgrade_per_10pct=st.number_input("Conventional production CapEx/10% (USD)",0.0,20_000_000.0,float(dv("capex_conv_upgrade_per_10pct")),50_000.0,format="%.0f")
        capex_mrt_upgrade_per_10pct=st.number_input("MRT production CapEx/10% (USD)",0.0,20_000_000.0,float(dv("capex_mrt_upgrade_per_10pct")),50_000.0,format="%.0f")
    with d3:
        capex_mrt_core=st.number_input("MRT core infrastructure CapEx (USD)",0.0,100_000_000.0,float(dv("capex_mrt_core")),250_000.0,format="%.0f")
        capex_per_endpoint=st.number_input("MRT endpoint installation cost (USD)",0.0,5_000_000.0,float(dv("capex_per_endpoint")),5_000.0,format="%.0f")
    with d4:
        max_capex_budget=st.number_input("Maximum CapEx budget (USD)",0.0,500_000_000.0,float(dv("max_capex_budget")),1_000_000.0,format="%.0f")
        net_contribution_per_patient=st.number_input("Net contribution/incremental patient (USD)",0.0,100_000.0,float(dv("net_contribution_per_patient")),25.0)
    e1,e2,e3,e4=st.columns(4)
    with e1:
        opex_base_conventional=st.number_input("Annual base OpEx — conventional (USD)",0.0,100_000_000.0,float(dv("opex_base_conventional")),100_000.0,format="%.0f")
        opex_base_mrt=st.number_input("Annual base OpEx — MRT (USD)",0.0,100_000_000.0,float(dv("opex_base_mrt")),100_000.0,format="%.0f")
    with e2:
        opex_per_additional_scanner=st.number_input("Annual OpEx/additional scanner (USD)",0.0,10_000_000.0,float(dv("opex_per_additional_scanner")),25_000.0,format="%.0f")
        opex_per_additional_dedicated_room=st.number_input("Annual OpEx/additional dedicated room (USD)",0.0,5_000_000.0,float(dv("opex_per_additional_dedicated_room")),10_000.0,format="%.0f")
    with e3:
        opex_mrt_maintenance=st.number_input("Annual MRT maintenance/support (USD)",0.0,50_000_000.0,float(dv("opex_mrt_maintenance")),50_000.0,format="%.0f")
        opex_per_endpoint=st.number_input("Annual OpEx/MRT endpoint (USD)",0.0,1_000_000.0,float(dv("opex_per_endpoint")),5_000.0,format="%.0f")
    with e4:
        annual_cost_per_extra_daily_batch=st.number_input("Annual cost/additional recurring daily batch (USD)",0.0,20_000_000.0,float(dv("annual_cost_per_extra_daily_batch")),50_000.0,format="%.0f")
        operating_days_per_year=st.number_input("Operating days/year",1,365,int(dv("operating_days_per_year")),5)
    f1,f2=st.columns(2)
    with f1:
        analysis_period_years=st.number_input("Financial analysis period (years)",1,25,int(dv("analysis_period_years")),1)
    with f2:
        discount_rate_pct=st.number_input("Discount rate (%)",0.0,50.0,float(dv("discount_rate")),.5)
    submitted=st.form_submit_button("RUN MRT PHARMA DIGITAL TWIN",use_container_width=True)

if submitted:
    warnings=[]
    if target_patients < current_patients: warnings.append("Target patients are below current patients; this is not an expansion case.")
    if max_mrt_batches_per_day == 1: warnings.append("MRT multi-batch optimization is disabled because the maximum is one batch/day.")
    if max_mrt_inpatient_rooms == 0: warnings.append("MRT distributed inpatient-room capacity is disabled.")
    if capex_mrt_core > max_capex_budget: warnings.append("MRT core CapEx alone exceeds the available budget.")
    if warnings:
        for warning in warnings: st.warning(warning)

    inp=Inputs(
        current_patients=current_patients,target_patients=target_patients,current_scanners=current_scanners,
        operating_hours=operating_hours,scanner_cycle_min=scanner_cycle_min,scanner_availability=scanner_availability_pct/100.0,
        current_injection_rooms=current_injection_rooms,current_uptake_rooms=current_uptake_rooms,
        patients_per_dedicated_room=patients_per_dedicated_room,current_doses_per_batch=current_doses_per_batch,
        conventional_delivery_time=conventional_delivery_time,mrt_delivery_time=mrt_delivery_time,
        isotope_half_life=isotope_half_life,max_mrt_batches_per_day=max_mrt_batches_per_day,
        max_mrt_inpatient_rooms=max_mrt_inpatient_rooms,patients_per_mrt_inpatient_room=patients_per_mrt_inpatient_room,
        max_additional_mrt_dedicated_rooms=max_additional_mrt_dedicated_rooms,supporting_mrt_destinations=supporting_mrt_destinations,
        capex_per_scanner=capex_per_scanner,capex_per_dedicated_room=capex_per_dedicated_room,
        capex_conv_upgrade_per_10pct=capex_conv_upgrade_per_10pct,capex_mrt_upgrade_per_10pct=capex_mrt_upgrade_per_10pct,
        capex_mrt_core=capex_mrt_core,capex_per_endpoint=capex_per_endpoint,max_capex_budget=max_capex_budget,
        net_contribution_per_patient=net_contribution_per_patient,opex_base_conventional=opex_base_conventional,
        opex_base_mrt=opex_base_mrt,opex_per_additional_scanner=opex_per_additional_scanner,
        opex_per_additional_dedicated_room=opex_per_additional_dedicated_room,opex_mrt_maintenance=opex_mrt_maintenance,
        opex_per_endpoint=opex_per_endpoint,annual_cost_per_extra_daily_batch=annual_cost_per_extra_daily_batch,
        operating_days_per_year=operating_days_per_year,analysis_period_years=analysis_period_years,
        discount_rate=discount_rate_pct/100.0,
    )
    result=run_comparison(inp)
    conv,mrt,winner=result.conventional,result.mrt,result.winner

    st.markdown("## Digital Twin Results")
    cards=st.columns(2)
    for column,title,candidate,is_mrt in [
        (cards[0],"Option 1 — Conventional Expansion",conv,False),
        (cards[1],"Option 2 — MRT Pharma Hybrid",mrt,True),
    ]:
        is_winner=(winner==("mrt" if is_mrt else "conventional"))
        css="result-card winner-card" if is_winner else "result-card"
        if not candidate.feasible:
            reason="; ".join(candidate.infeasible_reasons[:2]) or "No feasible plan."
            html=f'<div class="{css}"><div class="card-title">{title}</div><div class="card-subtitle">No feasible positive-NPV plan</div><div class="hero-value">NOT FEASIBLE</div><div class="metric-line"><span>Reason</span><span>{reason}</span></div></div>'
        else:
            badge='<div class="winner-badge">✓ WINNER</div>' if is_winner else ''
            if is_mrt:
                fifth_label,fifth_value="MRT-enabled inpatient rooms",f"{candidate.R_m:.0f}"
                fourth_label,fourth_value="Batches/day",f"{candidate.B_m:.0f}"
                prod=f"{candidate.U_m:.0f}%"
            else:
                fifth_label,fifth_value="Dedicated rooms added",f"{candidate.injection_additional+candidate.uptake_additional:.0f}"
                fourth_label,fourth_value="Additional scanners",f"{candidate.scanner['additional_scanners']:.0f}"
                prod=f"{candidate.U_c:.0f}%"
            html=(f'<div class="{css}"><div class="card-title">{title}</div><div class="card-subtitle">Best plan serving the same target demand</div>{badge}'
                  f'<div class="hero-value">${candidate.capex:,.0f}</div>'
                  f'<div class="metric-line"><span>NPV</span><span>${candidate.npv:,.0f}</span></div>'
                  f'<div class="metric-line"><span>Production increase</span><span>{prod}</span></div>'
                  f'<div class="metric-line"><span>{fourth_label}</span><span>{fourth_value}</span></div>'
                  f'<div class="metric-line"><span>{fifth_label}</span><span>{fifth_value}</span></div></div>')
        column.markdown(html,unsafe_allow_html=True)

    with st.expander("View full side-by-side implementation plan",expanded=False):
        dc1,dc2=st.columns(2)
        def details_df(c,is_mrt):
            rows={
                "Patients served/day":c.served_patients,
                "Installed capacity/day":c.installed_capacity,
                "Reserve capacity/day":max(0,c.installed_capacity-target_patients),
                "Production increase":f"{(c.U_m if is_mrt else c.U_c):.0f}%",
                "Batches/day":c.B_m if is_mrt else 1,
                "Additional scanners":c.scanner["additional_scanners"],
                "Additional dedicated rooms (combined injection/uptake use)":c.R_a if is_mrt else None,
                "Additional injection rooms":None if is_mrt else c.injection_additional,
                "Additional uptake rooms":None if is_mrt else c.uptake_additional,
                "MRT-enabled inpatient rooms":c.R_m if is_mrt else "Not applicable",
                "MRT endpoints":c.n_endpoints if is_mrt else "Not applicable",
                "Activity retained":f"{(c.eta_m if is_mrt else c.eta_c)*100:.1f}%",
                "CapEx":f"${c.capex:,.0f}","Annual OpEx":f"${c.opex:,.0f}",
                "Annual net cash flow":f"${c.ncf:,.0f}",
                "Payback":f"{c.payback:.1f} years" if c.payback else "Not achieved",
                f"{analysis_period_years}-year ROI":f"{c.roi:.1f}%","NPV":f"${c.npv:,.0f}",
            }
            return pd.DataFrame([{"Metric":k,"Value":v} for k,v in rows.items() if v is not None])
        with dc1:
            st.markdown("### Conventional Expansion")
            if conv.feasible: st.dataframe(details_df(conv,False),hide_index=True,use_container_width=True)
            else: st.error("; ".join(conv.infeasible_reasons))
        with dc2:
            st.markdown("### MRT Pharma Hybrid")
            if mrt.feasible: st.dataframe(details_df(mrt,True),hide_index=True,use_container_width=True)
            else:
                st.error("; ".join(mrt.infeasible_reasons))
                if mrt.diagnostic_best_served is not None:
                    st.info(f"Best near-feasible MRT plan serves {mrt.diagnostic_best_served:.0f} patients/day. Binding constraint: {mrt.diagnostic_binding_constraint}.")

    if winner=="mrt":
        rec=(f"Serve {mrt.served_patients:.0f} patients/day using a {mrt.U_m:.0f}% production increase, "
             f"{mrt.B_m} batches/day, {mrt.scanner['additional_scanners']:.0f} additional scanners, "
             f"{mrt.R_m} MRT-enabled inpatient rooms and {mrt.n_endpoints:.0f} connected endpoints.")
        w=mrt;o=conv;name="MRT Pharma Hybrid"
    elif winner=="conventional":
        rec=(f"Serve {conv.served_patients:.0f} patients/day using a {conv.U_c:.0f}% production increase, "
             f"{conv.scanner['additional_scanners']:.0f} additional scanners, {conv.injection_additional:.0f} additional injection rooms and {conv.uptake_additional:.0f} additional uptake rooms.")
        w=conv;o=mrt;name="Conventional Expansion"
    else:
        w=o=None;name="Neither architecture"
        rec="Neither option satisfies the selected physical, budget and financial-return constraints."
    st.markdown(f'<div class="decision"><div class="decision-kicker">DIGITAL TWIN DECISION</div><div class="decision-name">{"✓ " if winner!="neither" else ""}{name}</div><div class="decision-copy">{rec}{f" Highest modeled positive NPV: ${w.npv:,.0f}." if w else ""}</div></div>',unsafe_allow_html=True)

    if w and o and o.feasible:
        reasons=[]
        if w.npv>o.npv: reasons.append(f"Higher NPV by ${w.npv-o.npv:,.0f}.")
        if w.capex<o.capex: reasons.append(f"Lower initial CapEx by ${o.capex-w.capex:,.0f}.")
        if w.opex<o.opex: reasons.append(f"Lower annual OpEx by ${o.opex-w.opex:,.0f}.")
        wup=w.U_m if winner=="mrt" else w.U_c; oup=o.U_c if winner=="mrt" else o.U_m
        if wup<oup: reasons.append(f"Requires {oup-wup:.0f} percentage points less production expansion.")
        if reasons: st.markdown('<div class="reason-box">'+'<br>'.join('✓ '+r for r in reasons[:4])+'</div>',unsafe_allow_html=True)

    st.markdown("### Discounted Break-even")
    fig=go.Figure();years=list(range(analysis_period_years+1));rate=discount_rate_pct/100.0
    for label,c in [("Conventional Expansion",conv),("MRT Pharma Hybrid",mrt)]:
        if not c.feasible: continue
        values=[-c.capex];total=-c.capex
        for year in range(1,analysis_period_years+1):
            total += c.ncf/((1+rate)**year);values.append(total)
        fig.add_trace(go.Scatter(x=years,y=values,mode="lines+markers",name=label))
    fig.add_hline(y=0,line_dash="dash",line_color="#d71920")
    fig.update_layout(template="plotly_white",height=470,xaxis_title="Year",yaxis_title="Discounted cumulative net cash flow (USD)",margin=dict(l=20,r=20,t=30,b=20))
    st.plotly_chart(fig,use_container_width=True)

    results_rows=[]
    if conv: results_rows.append({"Architecture":"Conventional Expansion","Feasible":conv.feasible,"Production Increase (%)":conv.U_c,"Batches/Day":1,"Additional Scanners":conv.scanner.get("additional_scanners",0),"Additional Injection Rooms":conv.injection_additional,"Additional Uptake Rooms":conv.uptake_additional,"MRT Inpatient Rooms":0,"MRT Endpoints":0,"Installed Capacity/Day":conv.installed_capacity,"Patients Served/Day":conv.served_patients,"CapEx (USD)":conv.capex,"Annual OpEx (USD)":conv.opex,"Annual Net Cash Flow (USD)":conv.ncf,"NPV (USD)":conv.npv,"ROI (%)":conv.roi,"Payback (Years)":conv.payback})
    if mrt: results_rows.append({"Architecture":"MRT Pharma Hybrid","Feasible":mrt.feasible,"Production Increase (%)":mrt.U_m,"Batches/Day":mrt.B_m,"Additional Scanners":mrt.scanner.get("additional_scanners",0),"Additional Dedicated Rooms (combined injection/uptake)":mrt.R_a,"MRT Inpatient Rooms":mrt.R_m,"MRT Endpoints":mrt.n_endpoints,"Installed Capacity/Day":mrt.installed_capacity,"Patients Served/Day":mrt.served_patients,"CapEx (USD)":mrt.capex,"Annual OpEx (USD)":mrt.opex,"Annual Net Cash Flow (USD)":mrt.ncf,"NPV (USD)":mrt.npv,"ROI (%)":mrt.roi,"Payback (Years)":mrt.payback})
    result_df=pd.DataFrame(results_rows);assumption_df=pd.DataFrame([{"Assumption":k,"Value":v} for k,v in asdict(inp).items()])
    with st.expander("Download results and assumptions"):
        st.dataframe(result_df,hide_index=True,use_container_width=True)
        buffer=io.BytesIO()
        with pd.ExcelWriter(buffer,engine="openpyxl") as writer:
            result_df.to_excel(writer,index=False,sheet_name="Architecture Comparison")
            assumption_df.to_excel(writer,index=False,sheet_name="Assumptions")
        x1,x2=st.columns(2)
        with x1: st.download_button("Download CSV",result_df.to_csv(index=False).encode("utf-8"),"mrt_pharma_results.csv","text/csv",use_container_width=True)
        with x2: st.download_button("Download Excel",buffer.getvalue(),"mrt_pharma_results.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)

st.markdown('<div class="footer">MRT Pharma™ Decision-Support Digital Twin. Outputs are illustrative and depend on user-entered assumptions. Hospital engineering, clinical, financial, radiation-safety and regulatory validation remain required.</div>',unsafe_allow_html=True)

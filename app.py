from __future__ import annotations

import io
from dataclasses import asdict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from model import Inputs, Candidate, run_model, discounted_cash_flow

st.set_page_config(page_title="MRT Pharma™ Digital Twin", page_icon="⚙️", layout="wide")

st.markdown("""
<style>
:root{--red:#d71920;--black:#111;--line:#dedede;--green:#2e9d50}
.stApp{background:linear-gradient(135deg,#fff 0%,#f7f7f7 58%,#fff1f1 100%)}
.block-container{max-width:1380px;padding-top:3.2rem!important;padding-bottom:2rem}
.brand-shell,.panel{background:#fff;border:1px solid var(--line);border-radius:18px;padding:20px 26px;box-shadow:0 8px 24px rgba(17,17,17,.06);margin-bottom:12px}
.brand-row{display:flex;align-items:center;justify-content:space-between;gap:28px;flex-wrap:wrap;overflow:visible!important}
.brand-name{white-space:nowrap;overflow:visible!important;font-size:2.7rem;font-weight:900;line-height:1.2;letter-spacing:-1px}.brand-mrt{color:#111}.brand-pharma{color:var(--red)}
.trademark{position:relative;top:-.75em;margin-left:2px;font-size:.38em;font-weight:800;color:var(--red)}
.product-name{margin-top:4px;font-size:1.55rem;font-weight:900}.tagline{text-align:right;font-weight:850}.subtagline{max-width:650px;margin-top:5px;text-align:right;color:#666;font-size:.88rem}.red-rule{height:6px;margin-top:16px;border-radius:999px;background:linear-gradient(90deg,var(--red),#ff4c52)}
.result-card{border-radius:18px;padding:18px;min-height:225px;background:linear-gradient(135deg,#fff,#f2f2f2);border:1px solid rgba(17,17,17,.1);border-top:7px solid var(--red);box-shadow:0 8px 24px rgba(17,17,17,.08)}
.winner-card{background:linear-gradient(135deg,#effff3,#dff7e7);border:2px solid var(--green);border-top:8px solid var(--green)}
.winner-badge{display:inline-block;margin-top:8px;padding:5px 11px;border-radius:999px;background:var(--green);color:#fff;font-weight:900;font-size:.82rem}.card-title{font-size:1.08rem;font-weight:900}.big{font-size:1.45rem;font-weight:950}.summary-metric{margin-top:9px;font-size:.98rem}.decision-strip{margin:18px 0 12px;padding:18px 22px;border-radius:16px;background:linear-gradient(135deg,#111,#2b2b2b);color:#fff}.decision-name{font-size:1.45rem;font-weight:950}.note{background:#fff8e8;border:1px solid #efd69e;border-radius:12px;padding:11px 14px;margin:8px 0 14px;font-size:.86rem;color:#4a3a13}
div[data-testid="stFormSubmitButton"]>button{background:linear-gradient(90deg,#a90f16,var(--red));color:#fff;font-weight:900;border-radius:12px;border:none;min-height:3rem;width:100%}
@media(max-width:900px){.tagline,.subtagline{text-align:left}.brand-name{font-size:2.2rem}}
</style>
""", unsafe_allow_html=True)

brand_header_html = (
    '<div class="brand-shell"><div class="brand-row"><div>'
    '<div class="brand-name"><span class="brand-mrt">MRT</span> '
    '<span class="brand-pharma">Pharma</span><span class="trademark">™</span></div>'
    '<div class="product-name">Digital Twin</div></div><div>'
    '<div class="tagline">Engineering Distributed Precision Oncology Today.</div>'
    '<div class="subtagline">Physics-based decision platform for distributed oncology infrastructure, radiopharmaceutical logistics, capacity planning, and lifecycle economics.</div>'
    '</div></div><div class="red-rule"></div></div>'
)
st.markdown(brand_header_html, unsafe_allow_html=True)


def ni(label, minv, maxv, value, step=1, **kwargs):
    return st.number_input(label, min_value=minv, max_value=maxv, value=value, step=step, **kwargs)

with st.form("digital_twin"):
    st.markdown("### 1. Clinical Demand and Distributed Oncology")
    a,b,c,d=st.columns(4)
    with a:
        current_scanners=ni("Current PET scanners",1,30,2)
        target_patients=ni("Target PET patients/day",1,2000,200,5)
    with b:
        operating_hours=ni("Operating hours/day",1.0,24.0,18.0,.5)
        scan_minutes=ni("Scanner occupation time/patient (min)",5.0,180.0,20.0,5.0)
    with c:
        turnover_minutes=ni("Turnover time/patient (min)",0.0,120.0,15.0,5.0)
        scanner_availability_pct=ni("Scanner availability (%)",10.0,100.0,85.0,1.0)
    with d:
        max_additional_scanners=ni("Maximum additional PET scanners",0,40,10)
        max_mrt_delivery_points=ni("Maximum MRT-connected clinical delivery points",1,500,50)

    st.markdown("### 2. Injection, Uptake, FDG Production, and Transport")
    a,b,c,d=st.columns(4)
    with a:
        current_injection_rooms=ni("Current dedicated injection rooms",1,100,6)
        patients_per_injection_room=ni("Patients/injection room/day",1.0,200.0,30.0,1.0)
    with b:
        current_uptake_rooms=ni("Current dedicated uptake rooms",1,200,6)
        patients_per_uptake_room=ni("Patients/uptake room/day",1.0,100.0,15.0,1.0)
    with c:
        max_additional_injection_rooms=ni("Maximum additional injection rooms — conventional",0,100,12)
        max_additional_uptake_rooms=ni("Maximum additional uptake rooms — conventional",0,200,30)
    with d:
        manual_deliveries_day=ni("Manual/conventional deliveries/day",1.0,5000.0,250.0,10.0)
        mrt_deliveries_per_point_day=ni("MRT deliveries/point/day",1.0,5000.0,12.0,1.0)

    st.markdown('<div class="note"><b>MRT room logic:</b> Existing dedicated injection and uptake capacity remains available, while approved inpatient oncology rooms add distributed capacity. Physical rooms are counted once through the inventory constraint.</div>', unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    with a: total_oncology_rooms=ni("Total rooms allocated to oncology functions",1,1000,500)
    with b: shared_injection_uptake_rooms=ni("Injection/uptake rooms physically shared",0,100,0)
    with c: available_inpatient_rooms=ni("Available inpatient oncology rooms",0,1000,170)
    with d: max_enabled_inpatient_rooms=ni("Maximum MRT-enabled inpatient rooms",0,1000,170)
    a,b=st.columns(2)
    with a: patients_per_enabled_room=ni("Patients supported/enabled inpatient room/day",.1,20.0,1.0,.1)
    with b: room_enablement_capex=ni("MRT enablement CapEx/inpatient room (USD)",0.0,5_000_000.0,0.0,5000.0,format="%.0f")

    a,b,c,d=st.columns(4)
    with a:
        eob_gbq_batch=ni("18F activity at EOB/batch (GBq)",.1,500.0,30.0,1.0)
        current_batches=ni("Current FDG batches/day",1,12,2)
    with b:
        synthesis_yield_pct=ni("Synthesis yield (%)",1.0,100.0,75.0,1.0)
        qc_yield_pct=ni("QC/release yield (%)",1.0,100.0,95.0,1.0)
    with c:
        eob_release_min=ni("EOB-to-release time (min)",0.0,240.0,45.0,5.0)
        patient_dose_mbq=ni("FDG dose/patient (MBq)",1.0,1000.0,300.0,10.0)
    with d:
        manual_transport_min=ni("Manual delivery time (min)",0.0,120.0,10.0,1.0)
        mrt_distance_m=ni("MRT distance to farthest point (m)",0.0,10000.0,750.0,50.0)
    a,b,c,d=st.columns(4)
    with a: mrt_load_dock_sec=ni("MRT loading + docking (sec)",0.0,600.0,50.0,5.0)
    with b: max_additional_batches=ni("Maximum additional batches/day",0,10,2)
    with c: max_upgrade_pct=ni("Maximum existing-cyclotron upgrade (%)",0,200,40,5)
    with d: half_life_min=ni("18F half-life (min)",1.0,500.0,109.8,.1)
    a,b,c=st.columns(3)
    with a: uplift_per_point_pct=ni("Workflow improvement/MRT point (%)",0.0,20.0,.5,.5)
    with b: max_uplift_pct=ni("Maximum total MRT workflow improvement (%)",0.0,100.0,10.0,1.0)
    with c: centralized_efficiency_pct=ni("Current centralized workflow efficiency (%)",1.0,100.0,90.0,1.0)

    st.markdown("### 3. CapEx, OpEx, Revenue, and Financial Assumptions")
    a,b,c,d=st.columns(4)
    with a:
        new_cyclotron_capex=ni("New cyclotron + radiopharmacy CapEx (USD)",0.0,200_000_000.0,15_000_000.0,500_000.0,format="%.0f")
        new_cyclotron_added_gbq_day=ni("New cyclotron added FDG capacity/day (GBq)",.1,5000.0,45.0,5.0)
    with b:
        scanner_capex=ni("Additional PET scanner CapEx (USD)",0.0,20_000_000.0,250_000.0,25_000.0,format="%.0f")
        injection_room_capex=ni("Additional injection room CapEx (USD)",0.0,10_000_000.0,25_000.0,5_000.0,format="%.0f")
    with c:
        uptake_room_capex=ni("Additional uptake room CapEx (USD)",0.0,10_000_000.0,20_000.0,5_000.0,format="%.0f")
        mrt_point_capex=ni("MRT clinical delivery-point CapEx (USD)",0.0,20_000_000.0,25_000.0,5_000.0,format="%.0f")
    with d:
        conventional_upgrade_capex_per_10pct=ni("Conventional upgrade CapEx/10% (USD)",0.0,20_000_000.0,1_500_000.0,50_000.0,format="%.0f")
        hybrid_upgrade_capex_per_10pct=ni("Hybrid upgrade CapEx/10% (USD)",0.0,20_000_000.0,600_000.0,50_000.0,format="%.0f")
    a,b,c,d=st.columns(4)
    with a:
        mrt_core_capex=ni("MRT Pharma core infrastructure CapEx (USD)",0.0,100_000_000.0,6_000_000.0,250_000.0,format="%.0f")
        contribution_per_incremental_patient=ni("Net contribution/additional patient served (USD)",0.0,100_000.0,300.0,25.0)
    with b:
        base_opex_new=ni("Annual base OpEx — new cyclotron (USD)",0.0,100_000_000.0,2_000_000.0,100_000.0,format="%.0f")
        base_opex_conventional=ni("Annual base OpEx — conventional upgrade (USD)",0.0,100_000_000.0,2_000_000.0,100_000.0,format="%.0f")
    with c:
        base_opex_hybrid=ni("Annual base OpEx — MRT hybrid (USD)",0.0,100_000_000.0,200_000.0,50_000.0,format="%.0f")
        annual_mrt_maintenance=ni("Annual MRT maintenance/support (USD)",0.0,50_000_000.0,500_000.0,50_000.0,format="%.0f")
    with d:
        opex_per_added_batch=ni("OpEx/additional batch (USD)",0.0,1_000_000.0,8_000.0,500.0)
        annual_opex_per_scanner=ni("Annual OpEx/additional scanner (USD)",0.0,10_000_000.0,100_000.0,25_000.0,format="%.0f")
    a,b,c,d=st.columns(4)
    with a:
        annual_opex_per_injection_room=ni("Annual OpEx/injection room (USD)",0.0,5_000_000.0,90_000.0,10_000.0,format="%.0f")
        annual_opex_per_enabled_room=ni("Annual OpEx/MRT-enabled inpatient room (USD)",0.0,5_000_000.0,0.0,10_000.0,format="%.0f")
    with b:
        annual_opex_per_uptake_room=ni("Annual OpEx/uptake room (USD)",0.0,5_000_000.0,70_000.0,10_000.0,format="%.0f")
        annual_opex_per_mrt_point=ni("Annual OpEx/MRT delivery point (USD)",0.0,5_000_000.0,10_000.0,5_000.0,format="%.0f")
    with c:
        operating_days=ni("Operating days/year",1,365,300,5)
        analysis_years=ni("Financial analysis period (years)",1,25,10)
    with d:
        discount_rate_pct=ni("Discount rate (%)",0.0,50.0,10.0,.5)
        maximum_budget=ni("Maximum available CapEx (USD)",0.0,500_000_000.0,100_000_000.0,1_000_000.0,format="%.0f")

    submitted=st.form_submit_button("RUN MRT PHARMA DIGITAL TWIN",use_container_width=True)

if submitted:
    values=locals().copy()
    allowed={f.name for f in Inputs.__dataclass_fields__.values()}
    x=Inputs(**{k:values[k] for k in allowed})
    with st.spinner("Evaluating expansion architectures..."):
        result=run_model(x)

    st.markdown("### Digital Twin Results")
    names=["New Cyclotron","Conventional Upgrade","MRT Pharma Hybrid"]
    titles={"New Cyclotron":"Option 1 — New Cyclotron","Conventional Upgrade":"Option 2 — Conventional Upgrade","MRT Pharma Hybrid":"Option 3 — MRT Pharma Hybrid"}
    cols=st.columns(3)
    for col,name in zip(cols,names):
        cand=result.best_by_architecture[name]
        win=result.decision is not None and cand is not None and cand.architecture==result.decision.architecture
        css="result-card winner-card" if win else "result-card"
        if cand is None:
            html=f'<div class="{css}"><div class="card-title">{titles[name]}</div><div class="big">NOT FEASIBLE</div><div class="summary-metric">No positive-NPV configuration met the selected constraints.</div></div>'
        else:
            badge='<div class="winner-badge">✓ WINNER</div>' if win else ''
            html=f'<div class="{css}"><div class="card-title">{titles[name]}</div><div class="big">${cand.capex:,.0f}</div>{badge}<div class="summary-metric"><b>Installed capacity:</b> {cand.installed_capacity:.0f}/day</div><div class="summary-metric"><b>NPV:</b> ${cand.npv:,.0f}</div><div class="summary-metric"><b>ROI:</b> {cand.roi_pct:.1f}%</div></div>'
        col.markdown(html,unsafe_allow_html=True)

    with st.expander("View full side-by-side comparison",expanded=False):
        detail_cols=st.columns(3)
        for col,name in zip(detail_cols,names):
            cand=result.best_by_architecture[name]
            with col:
                st.markdown(f"**{titles[name]}**")
                if cand is None:
                    st.warning("Not feasible")
                else:
                    data={
                        "Installed capacity":f"{cand.installed_capacity:.0f}/day","Patients served":f"{cand.patients_served:.0f}/day","Reserve capacity":f"{cand.reserve_capacity:.0f}/day","Incremental patients":f"{cand.incremental_patients_day:.0f}/day","CapEx":f"${cand.capex:,.0f}","Annual OpEx":f"${cand.annual_opex:,.0f}","Cyclotron upgrade":f"{cand.upgrade_pct}%","Additional scanners":cand.added_scanners,"Additional batches/day":cand.added_batches,"Payback":f"{cand.payback_years:.1f} years",f"{x.analysis_years}-year ROI":f"{cand.roi_pct:.1f}%","NPV":f"${cand.npv:,.0f}"
                    }
                    if name=="MRT Pharma Hybrid":
                        data.update({"MRT-connected delivery points":cand.mrt_delivery_points,"MRT-enabled inpatient rooms":cand.enabled_inpatient_rooms,"Dedicated injection rooms added":0,"Dedicated uptake rooms added":0})
                    else:
                        data.update({"Centralized intake points":cand.centralized_intake_points,"Dedicated injection rooms added":cand.added_injection_rooms,"Dedicated uptake rooms added":cand.added_uptake_rooms,"MRT-connected delivery points":"Not applicable"})
                    st.dataframe(pd.DataFrame([{"Metric":k,"Value":v} for k,v in data.items()]),hide_index=True,use_container_width=True)

    if result.decision:
        d=result.decision
        st.markdown(f'<div class="decision-strip"><b>Digital Twin Decision</b><div class="decision-name">✓ {d.architecture}</div><div>Highest modeled positive NPV: ${d.npv:,.0f}. Installed capacity: {d.installed_capacity:.0f}/day.</div></div>',unsafe_allow_html=True)
    else:
        st.warning("No architecture met the selected physical, financial, and throughput constraints.")

    st.markdown("### Digital Twin Search Space")
    a,b,c,d=st.columns(4)
    a.metric("Configurations evaluated",f"{result.candidates_evaluated:,}")
    b.metric("Positive-NPV configurations",f"{len(result.feasible_candidates):,}")
    c.metric("Current modeled throughput",f"{result.current_throughput:.0f}/day")
    d.metric("Target demand",f"{x.target_patients}/day")

    st.markdown("### Discounted Break-even and Cumulative Cash Flow")
    fig=go.Figure(); years=list(range(x.analysis_years+1)); rate=x.discount_rate_pct/100.0
    for name,cand in result.best_by_architecture.items():
        if cand:
            fig.add_trace(go.Scatter(x=years,y=discounted_cash_flow(cand,x.analysis_years,rate),mode="lines+markers",name=name))
    fig.add_hline(y=0,line_dash="dash",line_color="#d71920")
    fig.update_layout(title="Discounted cumulative net cash flow by expansion architecture",xaxis_title="Year",yaxis_title="Discounted cumulative net cash flow (USD)",template="plotly_white",height=500)
    st.plotly_chart(fig,use_container_width=True)

    ranked=sorted(result.feasible_candidates,key=lambda c:(-c.npv,c.capex))[:50]
    results_df=pd.DataFrame([asdict(c) for c in ranked])
    assumptions_df=pd.DataFrame([{"Assumption":k,"Value":v} for k,v in result.assumptions.items()])
    st.markdown("### Top Ranked Configurations")
    if results_df.empty:
        st.warning("No positive-NPV configurations were found.")
    else:
        st.dataframe(results_df.head(15),use_container_width=True,hide_index=True)
        csv=results_df.to_csv(index=False).encode("utf-8")
        buf=io.BytesIO()
        with pd.ExcelWriter(buf,engine="openpyxl") as writer:
            results_df.to_excel(writer,index=False,sheet_name="Ranked Configurations")
            assumptions_df.to_excel(writer,index=False,sheet_name="Assumptions")
        a,b=st.columns(2)
        a.download_button("Download ranked results as CSV",csv,"mrt_pharma_digital_twin_results.csv","text/csv",use_container_width=True)
        b.download_button("Download results and assumptions as Excel",buf.getvalue(),"mrt_pharma_digital_twin_results.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
else:
    st.info("Complete the assumptions above and click **RUN MRT PHARMA DIGITAL TWIN**.")

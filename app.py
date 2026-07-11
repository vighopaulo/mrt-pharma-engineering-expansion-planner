import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='MRT Pharma™ Digital Twin', page_icon='⚙️', layout='wide')

st.markdown('''
<style>
:root{--r:#d71920;--b:#111;--w:#fff}
.stApp{background:linear-gradient(135deg,#fff 0%,#f7f7f7 58%,#fff1f1 100%)}
.block-container{max-width:1320px;padding-top:.7rem;padding-bottom:2rem}
.brand{background:#fff;border:1px solid #e2e2e2;border-radius:18px;padding:18px 24px;box-shadow:0 8px 24px rgba(17,17,17,.06);margin-bottom:12px}
.brandrow{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;flex-wrap:wrap}
.name{font-size:2.6rem;font-weight:950;white-space:nowrap;line-height:1}.mrt{color:#111}.pharma{color:#d71920}.product{font-size:1.5rem;font-weight:900;margin-top:7px}.tag{text-align:right;font-weight:850}.sub{text-align:right;color:#666;font-size:.87rem;max-width:620px}.rule{height:6px;border-radius:999px;background:linear-gradient(90deg,#d71920,#ff4c52);margin-top:13px}
.panel{background:#fff;border:1px solid #dedede;border-radius:18px;padding:18px 20px 10px;box-shadow:0 8px 24px rgba(17,17,17,.06);margin-bottom:.9rem}
.dark{background:#111;color:#fff;border-radius:18px;padding:16px 20px 10px;box-shadow:0 8px 24px rgba(17,17,17,.13);margin-bottom:.9rem}
.card{border-radius:18px;padding:18px;min-height:345px;background:linear-gradient(135deg,#fff,#f2f2f2);border:1px solid rgba(17,17,17,.1);border-top:7px solid #d71920;box-shadow:0 8px 24px rgba(17,17,17,.08)}
.decision{background:linear-gradient(135deg,#111,#2b2b2b);color:#fff}.decision .ct,.decision .big,.decision b{color:#fff}.ct{font-size:1.08rem;font-weight:900}.big{font-size:1.45rem;font-weight:950;color:#111}.rationale{background:#fff7f7;border-left:5px solid #d71920;border-radius:12px;padding:14px 16px}
div[data-testid='stNumberInput'] label{font-weight:700;color:#202020}div.stButton>button{background:linear-gradient(90deg,#a90f16,#d71920);color:#fff;font-weight:900;border-radius:12px;border:none;height:3rem}.footer{color:#666;font-size:.8rem;margin-top:10px}
</style>
''',unsafe_allow_html=True)

st.markdown('''<div class="brand"><div class="brandrow"><div><div class="name"><span class="mrt">MRT</span> <span class="pharma">Pharma™</span></div><div class="product">Digital Twin</div></div><div><div class="tag">Engineering Precision Oncology Today.</div><div class="sub">Physics-based decision platform for distributed oncology infrastructure, radiopharmaceutical logistics, capacity planning, and lifecycle economics.</div></div></div><div class="rule"></div></div>''',unsafe_allow_html=True)

st.markdown('<div class="panel">',unsafe_allow_html=True); st.markdown('### 1. Clinical Demand and Distributed Oncology Network')
a,b,c,d=st.columns(4)
with a:
    current_scanners=st.number_input('Current PET scanners',1,30,5,1)
    target_patients=st.number_input('Target PET patients/day',1,2000,200,5)
with b:
    operating_hours=st.number_input('Operating hours/day',1.0,24.0,18.0,.5)
    scan_minutes=st.number_input('Scanner occupation time/patient (min)',5.0,180.0,30.0,5.0)
with c:
    turnover_minutes=st.number_input('Turnover time/patient (min)',0.0,120.0,15.0,5.0)
    scanner_availability=st.number_input('Scanner availability (%)',10.0,100.0,85.0,5.0)
with d:
    max_additional_scanners=st.number_input('Maximum additional PET scanners',0,40,12,1)
    clinical_nodes=st.number_input('Planned clinical access points',1,100,8,1,help='Examples: pediatric wing, adult oncology wing, outpatient imaging, injection suites.')
st.markdown('</div>',unsafe_allow_html=True)

st.markdown('<div class="panel">',unsafe_allow_html=True); st.markdown('### 2. FDG Production, Processing, and Transport')
a,b,c,d=st.columns(4)
with a:
    eob_gbq=st.number_input('18F activity at EOB/batch (GBq)',.1,500.0,30.0,1.0)
    batches=st.number_input('Current FDG batches/day',1,12,2,1)
with b:
    synth=st.number_input('Synthesis yield (%)',1.0,100.0,75.0,1.0)
    qc=st.number_input('QC/release yield (%)',1.0,100.0,95.0,1.0)
with c:
    eob_release=st.number_input('EOB-to-release time (min)',0.0,240.0,45.0,5.0)
    dose=st.number_input('FDG dose/patient (MBq)',1.0,1000.0,300.0,10.0)
with d:
    manual_min=st.number_input('Manual delivery time (min)',0.0,120.0,10.0,1.0)
    mrt_distance=st.number_input('MRT Pharma distance to farthest node (m)',0.0,10000.0,750.0,50.0)
a,b,c,d=st.columns(4)
with a: mrt_dock=st.number_input('MRT loading + docking (sec)',0.0,600.0,50.0,5.0)
with b: max_batches=st.number_input('Maximum additional batches/day',0,10,4,1)
with c: max_upgrade=st.number_input('Maximum cyclotron upgrade (%)',0,200,100,5)
with d: half_life=st.number_input('18F half-life (min)',1.0,500.0,109.8,.1)
st.markdown('</div>',unsafe_allow_html=True)

st.markdown('<div class="dark">',unsafe_allow_html=True); st.markdown('### 3. CapEx, OpEx, Revenue, and Financial Assumptions')
a,b,c,d=st.columns(4)
with a:
    new_cyclotron=st.number_input('New cyclotron + radiopharmacy CapEx (USD)',0.0,200_000_000.0,15_000_000.0,500_000.0,format='%.0f')
    scanner_capex=st.number_input('Additional PET scanner CapEx (USD)',0.0,20_000_000.0,2_500_000.0,100_000.0,format='%.0f')
with b:
    pure_up_10=st.number_input('Pure upgrade CapEx per 10% (USD)',0.0,20_000_000.0,650_000.0,50_000.0,format='%.0f')
    hybrid_up_10=st.number_input('Hybrid upgrade CapEx per 10% (USD)',0.0,20_000_000.0,600_000.0,50_000.0,format='%.0f')
with c:
    mrt_capex=st.number_input('MRT Pharma infrastructure CapEx (USD)',0.0,100_000_000.0,6_000_000.0,250_000.0,format='%.0f')
    rev_patient=st.number_input('Net revenue contribution/patient (USD)',0.0,100_000.0,750.0,25.0)
with d:
    opex_new=st.number_input('Annual OpEx — new cyclotron (USD)',0.0,100_000_000.0,5_000_000.0,100_000.0,format='%.0f')
    opex_up=st.number_input('Annual OpEx — conventional upgrade (USD)',0.0,100_000_000.0,3_800_000.0,100_000.0,format='%.0f')
a,b,c,d=st.columns(4)
with a: opex_hybrid=st.number_input('Annual OpEx — MRT hybrid (USD)',0.0,100_000_000.0,3_200_000.0,100_000.0,format='%.0f')
with b: operating_days=st.number_input('Operating days/year',1,365,300,5)
with c: years=st.number_input('Financial analysis period (years)',1,25,10,1)
with d: discount=st.number_input('Discount rate (%)',0.0,50.0,10.0,.5)
st.markdown('</div>',unsafe_allow_html=True)

if st.button('RUN MRT PHARMA DIGITAL TWIN',type='primary',use_container_width=True):
    speed=50.0
    pps=(operating_hours*60/(scan_minutes+turnover_minutes))*(scanner_availability/100)
    release_batch=eob_gbq*(synth/100)*(qc/100)*(2**(-eob_release/half_life))
    release_day=release_batch*batches
    manual_survival=2**(-manual_min/half_life)
    mrt_min=((mrt_distance/speed)+mrt_dock)/60
    mrt_survival=2**(-mrt_min/half_life)
    current_scan_cap=current_scanners*pps
    current_fdg_cap=release_day*1000*manual_survival/dose
    current_throughput=min(current_scan_cap,current_fdg_cap)

    candidates=[]; total=phys=meet=0
    for add_sc in range(max_additional_scanners+1):
        total+=1; phys+=1
        scan_cap=(current_scanners+add_sc)*pps
        if scan_cap<target_patients: continue
        meet+=1
        req_release=target_patients*dose/manual_survival/1000
        capex=new_cyclotron+add_sc*scanner_capex
        annual_net=target_patients*operating_days*rev_patient-opex_new
        candidates.append(dict(architecture='New Cyclotron',capex=capex,opex=opex_new,annual_net=annual_net,add_scanners=add_sc,upgrade_pct=0,added_batches=0,nodes=clinical_nodes,throughput=target_patients,survival=manual_survival,added_release=max(0,req_release-release_day)))

    for up in range(0,max_upgrade+1,5):
        for add_b in range(max_batches+1):
            release=release_day*(1+up/100)+add_b*release_batch
            fdg_cap=release*1000*manual_survival/dose
            for add_sc in range(max_additional_scanners+1):
                total+=1; phys+=1
                scan_cap=(current_scanners+add_sc)*pps
                tp=min(fdg_cap,scan_cap)
                if tp<target_patients: continue
                meet+=1
                capex=(up/10)*pure_up_10+add_sc*scanner_capex
                annual_net=target_patients*operating_days*rev_patient-opex_up
                candidates.append(dict(architecture='Conventional Upgrade',capex=capex,opex=opex_up,annual_net=annual_net,add_scanners=add_sc,upgrade_pct=up,added_batches=add_b,nodes=min(clinical_nodes,max(1,current_scanners+add_sc)),throughput=tp,survival=manual_survival,added_release=release-release_day))

    for up in range(0,max_upgrade+1,5):
        for add_b in range(max_batches+1):
            release=release_day*(1+up/100)+add_b*release_batch
            fdg_cap=release*1000*mrt_survival/dose
            for add_sc in range(max_additional_scanners+1):
                for nodes in range(1,clinical_nodes+1):
                    total+=1; phys+=1
                    distributed_eff=min(1.0,.82+.02*nodes)
                    scan_cap=(current_scanners+add_sc)*pps*distributed_eff
                    tp=min(fdg_cap,scan_cap)
                    if tp<target_patients: continue
                    meet+=1
                    capex=(up/10)*hybrid_up_10+mrt_capex+add_sc*scanner_capex
                    annual_net=target_patients*operating_days*rev_patient-opex_hybrid
                    candidates.append(dict(architecture='MRT Pharma Hybrid',capex=capex,opex=opex_hybrid,annual_net=annual_net,add_scanners=add_sc,upgrade_pct=up,added_batches=add_b,nodes=nodes,throughput=tp,survival=mrt_survival,added_release=release-release_day))

    rate=discount/100
    for x in candidates:
        x['payback']=x['capex']/x['annual_net'] if x['annual_net']>0 else float('inf')
        x['npv']=-x['capex']+sum(x['annual_net']/((1+rate)**y) for y in range(1,years+1))
        x['roi']=((x['annual_net']*years-x['capex'])/x['capex']*100) if x['capex']>0 else 0
    feasible=[x for x in candidates if math.isfinite(x['payback'])]
    by_arch={}
    for arch in ['New Cyclotron','Conventional Upgrade','MRT Pharma Hybrid']:
        rows=[x for x in feasible if x['architecture']==arch]
        by_arch[arch]=min(rows,key=lambda x:x['capex']) if rows else None
    decision=max(feasible,key=lambda x:(x['npv'],-x['capex'])) if feasible else None

    st.markdown('### Digital Twin Results')
    cols=st.columns(4)
    def card(col,title,row,decision_card=False):
        cls='card decision' if decision_card else 'card'
        if row:
            html=f'''<div class="{cls}"><div class="ct">{title}</div><div class="big">{row['architecture'] if decision_card else f"${row['capex']:,.0f}"}</div><hr><div><b>CapEx:</b> ${row['capex']:,.0f}</div><div><b>Annual OpEx:</b> ${row['opex']:,.0f}</div><div><b>Upgrade:</b> {row['upgrade_pct']}%</div><div><b>Additional scanners:</b> {row['add_scanners']}</div><div><b>Additional batches/day:</b> {row['added_batches']}</div><div><b>Clinical access points:</b> {row['nodes']}</div><div><b>Payback:</b> {row['payback']:.1f} years</div><div><b>{years}-year ROI:</b> {row['roi']:.1f}%</div><div><b>NPV:</b> ${row['npv']:,.0f}</div></div>'''
        else:
            html=f'''<div class="{cls}"><div class="ct">{title}</div><div class="big">NOT FEASIBLE</div><hr><div>No configuration met the selected constraints.</div></div>'''
        col.markdown(html,unsafe_allow_html=True)
    card(cols[0],'Option 1 — New Cyclotron',by_arch['New Cyclotron'])
    card(cols[1],'Option 2 — Conventional Upgrade',by_arch['Conventional Upgrade'])
    card(cols[2],'Option 3 — MRT Pharma Hybrid',by_arch['MRT Pharma Hybrid'])
    card(cols[3],'Digital Twin Decision',decision,True)

    st.markdown('### Digital Twin Search Space')
    q1,q2,q3,q4=st.columns(4)
    q1.metric('Configurations generated',f'{total:,}')
    q2.metric('Physically feasible',f'{phys:,}')
    q3.metric('Met throughput target',f'{meet:,}')
    q4.metric('Feasible financial cases',f'{len(feasible):,}')

    st.markdown('### Break-even and Cumulative Cash Flow')
    fig=go.Figure()
    for arch,row in by_arch.items():
        if not row: continue
        xs=list(range(years+1)); ys=[-row['capex']+row['annual_net']*y for y in xs]
        fig.add_trace(go.Scatter(x=xs,y=ys,mode='lines+markers',name=arch))
    fig.add_hline(y=0,line_dash='dash',line_color='#d71920')
    fig.update_layout(title='Cumulative net cash flow by expansion architecture',xaxis_title='Year',yaxis_title='Cumulative net cash flow (USD)',template='plotly_white',height=480,legend_title='Architecture',margin=dict(l=20,r=20,t=60,b=20))
    st.plotly_chart(fig,use_container_width=True)

    st.markdown('### Why the Digital Twin Selected This Architecture')
    if decision:
        reasons=[f"Meets the target of {target_patients} PET patients/day.",f"Supports {decision['nodes']} distributed clinical access points.",f"Requires a {decision['upgrade_pct']}% cyclotron upgrade.",f"Adds {decision['add_scanners']} PET scanners and {decision['added_batches']} batches/day.",f"Provides {decision['survival']*100:.1f}% modeled FDG survival during transport.",f"Has the highest modeled NPV: ${decision['npv']:,.0f}.",f"Estimated payback: {decision['payback']:.1f} years."]
        st.markdown('<div class="rationale">'+'<br>'.join('✓ '+r for r in reasons)+'</div>',unsafe_allow_html=True)

    st.markdown('### Top Ranked Configurations')
    top=sorted(feasible,key=lambda x:(-x['npv'],x['capex']))[:15]
    df=pd.DataFrame([{ 'Architecture':x['architecture'],'CapEx (USD)':x['capex'],'Annual OpEx (USD)':x['opex'],'Upgrade (%)':x['upgrade_pct'],'Added Scanners':x['add_scanners'],'Added Batches/Day':x['added_batches'],'Clinical Access Points':x['nodes'],'Payback (Years)':x['payback'],'ROI (%)':x['roi'],'NPV (USD)':x['npv']} for x in top])
    if not df.empty:
        st.dataframe(df.style.format({'CapEx (USD)':'${:,.0f}','Annual OpEx (USD)':'${:,.0f}','Payback (Years)':'{:.1f}','ROI (%)':'{:.1f}%','NPV (USD)':'${:,.0f}'}),use_container_width=True,hide_index=True)
    st.markdown('<div class="footer">MRT Pharma™ Digital Twin demonstration model. Outputs are illustrative and depend on user-entered assumptions. This version models 18F-FDG PET imaging, distributed clinical access points, CapEx, OpEx, ROI, NPV, and break-even. It is not a substitute for hospital engineering, clinical, financial, or regulatory validation.</div>',unsafe_allow_html=True)
else:
    st.info('Adjust the assumptions above, then click **RUN MRT PHARMA DIGITAL TWIN**.')

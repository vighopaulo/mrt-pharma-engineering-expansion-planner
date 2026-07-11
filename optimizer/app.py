import math
import pandas as pd
import streamlit as st

st.set_page_config(page_title='MRT Hospital Capacity Optimizer', page_icon='⚙️', layout='wide')

st.markdown('''
<style>
.stApp {background: linear-gradient(135deg,#f8fafc 0%,#eef2f7 50%,#fff5f5 100%);} 
.block-container {max-width:1220px;padding-top:1rem;padding-bottom:1.5rem;}
h1 {font-size:2.15rem !important;color:#111827;margin-bottom:.1rem !important;}
.subtitle {color:#4b5563;margin-bottom:.8rem;}
.panel {background:white;border:1px solid #e5e7eb;border-radius:18px;padding:18px 20px 10px;box-shadow:0 8px 24px rgba(17,24,39,.06);margin-bottom:.9rem;}
.dark-panel {background:#111827;color:white;border-radius:18px;padding:16px 20px 10px;box-shadow:0 8px 24px rgba(17,24,39,.10);margin-bottom:.9rem;}
.result-card {border-radius:18px;padding:19px;min-height:315px;border:1px solid rgba(17,24,39,.08);box-shadow:0 8px 24px rgba(17,24,39,.08);}
.blue {background:linear-gradient(135deg,#eaf2ff,#dbeafe);} .green {background:linear-gradient(135deg,#ecfdf3,#d1fae5);} .red {background:linear-gradient(135deg,#fff1f2,#fecdd3);} 
.card-title {font-size:1.2rem;font-weight:850;color:#111827;margin-bottom:.55rem;} .big {font-size:1.65rem;font-weight:900;color:#111827;} .small {font-size:.86rem;color:#4b5563;}
div[data-testid='stNumberInput'] label {font-weight:700;color:#1f2937;} div.stButton > button {background:linear-gradient(90deg,#b91c1c,#ef4444);color:white;font-weight:850;border-radius:12px;border:none;height:3rem;} div.stButton > button:hover {background:linear-gradient(90deg,#991b1b,#dc2626);color:white;}
</style>
''', unsafe_allow_html=True)

st.title('MRT Hospital Capacity Optimizer')
st.markdown("<div class='subtitle'>Operations-research search model for 18F-FDG PET expansion — capacity first, CapEx second</div>", unsafe_allow_html=True)

st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.markdown('### 1. Current Hospital and Target')
c1,c2,c3,c4=st.columns(4)
with c1:
    current_scanners=st.number_input('Current PET scanners',min_value=1,value=5,step=1)
    target_patients=st.number_input('Target PET patients/day',min_value=1,value=200,step=5)
with c2:
    operating_hours=st.number_input('Operating hours/day',min_value=1.0,max_value=24.0,value=18.0,step=0.5)
    scan_minutes=st.number_input('Scanner occupation time/patient (min)',min_value=5.0,value=30.0,step=5.0)
with c3:
    turnover_minutes=st.number_input('Turnover time/patient (min)',min_value=0.0,value=15.0,step=5.0)
    scanner_availability=st.number_input('Scanner availability (%)',min_value=10.0,max_value=100.0,value=75.0,step=5.0)
with c4:
    max_additional_scanners=st.number_input('Maximum additional PET scanners',min_value=0,value=10,step=1)
    max_upgrade_pct=st.number_input('Maximum existing-cyclotron upgrade (%)',min_value=0,max_value=200,value=100,step=10)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.markdown('### 2. FDG Production and Transport')
p1,p2,p3,p4=st.columns(4)
with p1:
    released_gbq_per_batch=st.number_input('Released FDG activity/batch (GBq)',min_value=0.1,value=20.0,step=1.0)
    batches_per_day=st.number_input('Current FDG batches/day',min_value=1,value=2,step=1)
with p2:
    patient_dose_mbq=st.number_input('FDG dose per patient (MBq)',min_value=1.0,value=300.0,step=10.0)
    manual_transport_minutes=st.number_input('Manual delivery time (min)',min_value=0.0,value=10.0,step=1.0)
with p3:
    mrt_distance_m=st.number_input('MRT distance to scanner wing (m)',min_value=0.0,value=750.0,step=50.0)
    mrt_load_dock_seconds=st.number_input('MRT loading + docking time (sec)',min_value=0.0,value=50.0,step=5.0)
with p4:
    max_new_batches=st.number_input('Maximum additional batches/day',min_value=0,value=3,step=1)
    batch_capacity_increment_gbq=st.number_input('Added released activity per 10% upgrade (GBq/day)',min_value=0.1,value=4.0,step=0.5)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div class='dark-panel'>", unsafe_allow_html=True)
st.markdown('### 3. CapEx Assumptions')
k1,k2,k3,k4=st.columns(4)
with k1:
    new_cyclotron_cost=st.number_input('New cyclotron + radiopharmacy (USD)',min_value=0.0,value=15000000.0,step=500000.0,format='%.0f')
with k2:
    scanner_cost=st.number_input('Additional PET scanner (USD)',min_value=0.0,value=2500000.0,step=100000.0,format='%.0f')
with k3:
    upgrade_cost_per_10pct=st.number_input('Cyclotron upgrade per 10% (USD)',min_value=0.0,value=600000.0,step=50000.0,format='%.0f')
with k4:
    mrt_capex=st.number_input('MRT infrastructure CapEx (USD)',min_value=0.0,value=6000000.0,step=250000.0,format='%.0f')
st.markdown('</div>', unsafe_allow_html=True)

run=st.button('RUN MRT OPTIMIZATION',type='primary',use_container_width=True)

if run:
    HALF_LIFE_MIN=109.8
    MRT_SPEED_MPS=50.0
    scanner_cycle=scan_minutes+turnover_minutes
    patients_per_scanner=(operating_hours*60.0/scanner_cycle)*(scanner_availability/100.0)
    manual_survival=2**(-manual_transport_minutes/HALF_LIFE_MIN)
    mrt_total_minutes=((mrt_distance_m/MRT_SPEED_MPS)+mrt_load_dock_seconds)/60.0
    mrt_survival=2**(-mrt_total_minutes/HALF_LIFE_MIN)
    current_release_gbq_day=released_gbq_per_batch*batches_per_day
    current_scanner_capacity=current_scanners*patients_per_scanner
    current_fdg_capacity=current_release_gbq_day*1000*manual_survival/patient_dose_mbq
    current_modeled_throughput=min(current_scanner_capacity,current_fdg_capacity)

    candidates=[]
    for add_scanners in range(max_additional_scanners+1):
        total_scanners=current_scanners+add_scanners
        scanner_capacity=total_scanners*patients_per_scanner
        if scanner_capacity<target_patients:
            continue
        required_release_gbq_day=target_patients*patient_dose_mbq/manual_survival/1000.0
        added_release_gbq_day=max(0.0,required_release_gbq_day-current_release_gbq_day)
        capex=new_cyclotron_cost+add_scanners*scanner_cost
        candidates.append(dict(architecture='New Cyclotron',capex=capex,add_scanners=add_scanners,upgrade_pct=0,added_batches=0,throughput=min(scanner_capacity,target_patients),scanner_capacity=scanner_capacity,fdg_capacity=target_patients,added_release_gbq_day=added_release_gbq_day,transport_survival=manual_survival))

    for upgrade_pct in range(0,max_upgrade_pct+1,10):
        upgrade_added_gbq_day=(upgrade_pct/10.0)*batch_capacity_increment_gbq
        for added_batches in range(max_new_batches+1):
            release_gbq_day=current_release_gbq_day+upgrade_added_gbq_day+added_batches*released_gbq_per_batch
            fdg_capacity=release_gbq_day*1000*mrt_survival/patient_dose_mbq
            for add_scanners in range(max_additional_scanners+1):
                total_scanners=current_scanners+add_scanners
                scanner_capacity=total_scanners*patients_per_scanner
                throughput=min(scanner_capacity,fdg_capacity)
                if throughput<target_patients:
                    continue
                capex=(upgrade_pct/10.0)*upgrade_cost_per_10pct+mrt_capex+add_scanners*scanner_cost
                candidates.append(dict(architecture='Hybrid MRT',capex=capex,add_scanners=add_scanners,upgrade_pct=upgrade_pct,added_batches=added_batches,throughput=throughput,scanner_capacity=scanner_capacity,fdg_capacity=fdg_capacity,added_release_gbq_day=release_gbq_day-current_release_gbq_day,transport_survival=mrt_survival))

    candidates.sort(key=lambda x:(x['capex'],-x['throughput']))
    best=candidates[0] if candidates else None
    new_options=[x for x in candidates if x['architecture']=='New Cyclotron']
    hybrid_options=[x for x in candidates if x['architecture']=='Hybrid MRT']
    best_new=new_options[0] if new_options else None
    best_hybrid=hybrid_options[0] if hybrid_options else None

    st.markdown('### Optimization Results')
    r1,r2,r3=st.columns(3)
    with r1:
        if best_new:
            st.markdown(f"""<div class='result-card blue'><div class='card-title'>Option 1 — New Cyclotron</div><div class='small'>Least-CapEx feasible new-cyclotron configuration</div><div class='big'>${best_new['capex']:,.0f}</div><hr><div><b>Additional PET scanners:</b> {best_new['add_scanners']}</div><div><b>Added FDG capacity:</b> {best_new['added_release_gbq_day']:.1f} GBq/day</div><div><b>Scanner capacity:</b> {best_new['scanner_capacity']:.0f}/day</div><div><b>Target throughput:</b> {target_patients}/day</div><div><b>Status:</b> Feasible</div></div>""",unsafe_allow_html=True)
        else:
            st.markdown("<div class='result-card red'><div class='card-title'>Option 1 — New Cyclotron</div><div class='big'>NOT FEASIBLE</div><hr><div>The scanner search limit is too low for the selected target.</div></div>",unsafe_allow_html=True)
    with r2:
        if best_hybrid:
            st.markdown(f"""<div class='result-card green'><div class='card-title'>Option 2 — Hybrid MRT</div><div class='small'>Least-CapEx feasible hybrid configuration</div><div class='big'>${best_hybrid['capex']:,.0f}</div><hr><div><b>Cyclotron upgrade:</b> {best_hybrid['upgrade_pct']}%</div><div><b>Additional batches/day:</b> {best_hybrid['added_batches']}</div><div><b>Additional PET scanners:</b> {best_hybrid['add_scanners']}</div><div><b>Modeled throughput:</b> {best_hybrid['throughput']:.0f}/day</div><div><b>MRT FDG survival:</b> {best_hybrid['transport_survival']*100:.1f}%</div></div>""",unsafe_allow_html=True)
        else:
            st.markdown("<div class='result-card red'><div class='card-title'>Option 2 — Hybrid MRT</div><div class='big'>NOT FEASIBLE</div><hr><div>No hybrid combination reached the target within the selected limits.</div></div>",unsafe_allow_html=True)
    with r3:
        if best:
            decision_class='green' if best['architecture']=='Hybrid MRT' else 'blue'
            alternative=best_new if best['architecture']=='Hybrid MRT' else best_hybrid
            savings_text=''
            if alternative:
                savings=alternative['capex']-best['capex']
                savings_text=f'Modeled CapEx advantage: ${savings:,.0f}.'
            st.markdown(f"""<div class='result-card {decision_class}'><div class='card-title'>Optimizer Decision</div><div class='big'>{best['architecture'].upper()}</div><hr><div>{savings_text}</div><div style='margin-top:10px;'><b>Current modeled throughput:</b> {current_modeled_throughput:.0f}/day</div><div><b>Target:</b> {target_patients}/day</div><div><b>Configurations tested:</b> {len(candidates):,}</div><div><b>Decision rule:</b> lowest CapEx among feasible configurations</div></div>""",unsafe_allow_html=True)
        else:
            st.markdown("<div class='result-card red'><div class='card-title'>Optimizer Decision</div><div class='big'>NO FEASIBLE CONFIGURATION</div><hr><div>Increase the allowed scanner count, cyclotron upgrade limit, or additional batch limit.</div></div>",unsafe_allow_html=True)

    st.markdown('### Capacity Diagnostics')
    d1,d2,d3,d4=st.columns(4)
    d1.metric('Current scanner capacity',f'{current_scanner_capacity:.0f}/day')
    d2.metric('Current FDG dose capacity',f'{current_fdg_capacity:.0f}/day')
    d3.metric('Manual FDG survival',f'{manual_survival*100:.1f}%')
    d4.metric('MRT FDG survival',f'{mrt_survival*100:.1f}%')

    if candidates:
        table_rows=[]
        for row in candidates[:10]:
            table_rows.append({'Architecture':row['architecture'],'CapEx (USD)':row['capex'],'Cyclotron upgrade (%)':row['upgrade_pct'],'Added batches/day':row['added_batches'],'Additional scanners':row['add_scanners'],'Throughput/day':row['throughput']})
        st.markdown('### Top Feasible Configurations')
        df=pd.DataFrame(table_rows)
        st.dataframe(df.style.format({'CapEx (USD)':'${:,.0f}','Throughput/day':'{:,.0f}'}),use_container_width=True,hide_index=True)

    st.markdown("<div class='small' style='margin-top:8px;'>Demonstration model only. The optimizer searches combinations of scanner additions, cyclotron upgrades, added production batches, and MRT installation. It excludes OpEx, staffing, uptake/injection-room constraints, synthesis/QC variability, maintenance, financing, and hospital-specific regulatory limits.</div>",unsafe_allow_html=True)
else:
    st.info('Adjust the inputs, then click **RUN MRT OPTIMIZATION**.')

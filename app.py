from dataclasses import asdict
import io
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from model import Inputs, run_model

st.set_page_config(page_title='MRT Pharma™ Digital Twin',page_icon='⚙️',layout='wide')
st.markdown('''<style>
:root{--red:#d71920;--green:#24984a;--line:#e2e4e8}.stApp{background:linear-gradient(180deg,#fff,#f6f7f9)}.block-container{max-width:1240px;padding-top:2.2rem!important}.brand,.panel{background:#fff;border:1px solid var(--line);border-radius:22px;box-shadow:0 12px 34px rgba(20,24,35,.07)}.brand{padding:24px 28px;margin-bottom:15px}.row{display:flex;justify-content:space-between;gap:25px;flex-wrap:wrap}.name{font-size:2.5rem;font-weight:950}.red{color:var(--red)}.tag{text-align:right;font-weight:900}.sub{text-align:right;color:#666;max-width:650px}.rule{height:6px;background:linear-gradient(90deg,var(--red),#ff4b52);border-radius:99px;margin-top:16px}.panel{padding:18px 22px 8px;margin-bottom:14px}.card{min-height:260px;padding:20px;border:1px solid var(--line);border-top:7px solid var(--red);border-radius:22px;background:linear-gradient(145deg,#fff,#f5f6f8)}.winner{border:2px solid var(--green);border-top:8px solid var(--green);background:#eaf8ef}.badge{display:inline-block;background:var(--green);color:white;border-radius:99px;padding:5px 11px;font-weight:900;margin-top:8px}.big{font-size:1.7rem;font-weight:950;margin-top:12px}.line{display:flex;justify-content:space-between;border-top:1px solid #ddd;padding-top:9px;margin-top:9px}.line span:last-child{font-weight:900}.decision{background:#111;color:white;border-radius:18px;padding:18px 22px;margin:16px 0}div[data-testid="stFormSubmitButton"]>button{width:100%;min-height:3.1rem;background:var(--red);color:white;font-weight:950;border:none;border-radius:14px}
</style>''',unsafe_allow_html=True)
brand_header_html=('<div class="brand"><div class="row"><div><div class="name">MRT <span class="red">Pharma™</span></div><div style="font-size:1.35rem;font-weight:900">Outpatient Decision-Support Digital Twin</div></div><div><div class="tag">Engineering Distributed Precision Oncology Today.</div><div class="sub">Compares proportional conventional expansion with optimized MRT production and batch scheduling.</div></div></div><div class="rule"></div></div>')
st.markdown(brand_header_html,unsafe_allow_html=True)

def section(title,helptext):
    st.markdown(f'<div class="panel"><h3>{title}</h3><div style="color:#6f7480;margin-bottom:12px">{helptext}</div>',unsafe_allow_html=True)
def end(): st.markdown('</div>',unsafe_allow_html=True)



def parse_currency(value: str) -> float:
    cleaned = value.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return 0.0
    try:
        amount = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid currency value: {value}") from exc
    if amount < 0:
        raise ValueError("Currency values cannot be negative.")
    return amount


def currency_input(label: str, default: float, help_text: str | None = None) -> float:
    raw = st.text_input(label, value=f"${default:,.0f}", help=help_text)
    try:
        return parse_currency(raw)
    except ValueError:
        st.error(f"Enter {label} as a valid non-negative USD amount, for example $1,500,000.")
        return float(default)


def money(value: float) -> str:
    return f"${value:,.0f}"

def excel_bytes(results,assumptions):
    b=io.BytesIO()
    with pd.ExcelWriter(b,engine='openpyxl') as w:
        results.to_excel(w,index=False,sheet_name='Results'); assumptions.to_excel(w,index=False,sheet_name='Assumptions')
    return b.getvalue()

with st.form('form'):
    section('1. Hospital Today and Future Target','Enter the present outpatient PET system and future patient target. Units are shown beside every input.')
    a,b,c,d=st.columns(4)
    with a:
        current_patients=st.number_input('Current patients served (patients/day)',1.0,5000.0,50.0,5.0)
        target_patients=st.number_input('Future target (patients/day)',1.0,5000.0,200.0,5.0)
    with b:
        current_scanners=st.number_input('Current PET scanners (count)',1,100,2,1)
        current_injection=st.number_input('Current injection rooms (count)',1,200,6,1)
    with c:
        current_uptake=st.number_input('Current uptake rooms (count)',1,200,6,1)
        doses=st.number_input('Current usable patient-dose capacity (doses/batch)',1.0,5000.0,50.0,5.0, help='Patient-dose equivalents available at batch release. This Version 1.0 model does not use raw GBq directly.')
    with d:
        hours=st.number_input('Operating time (h/day)',1.0,24.0,18.0,.5)
        availability=st.number_input('Scanner availability (%)',10.0,100.0,85.0,1.0)
    end()

    section('2. Operating and Transport Assumptions','Scanner and room counts are outputs; enter only timing and physical assumptions.')
    a,b,c,d=st.columns(4)
    with a:
        scan_cycle=st.number_input('Scanner cycle time (min/patient)',5.0,180.0,35.0,5.0)
        inj_time=st.number_input('Injection-room service time (min/patient)',1.0,180.0,15.0,1.0)
    with b:
        uptake_time=st.number_input('Uptake-room occupancy time (min/patient)',1.0,240.0,60.0,5.0)
        batch_cycle=st.number_input('Production and release cycle (min/batch)',1.0,720.0,180.0,15.0)
    with c:
        conv_transport=st.number_input('Conventional transport time (min)',0.0,240.0,20.0,1.0)
        mrt_transport=st.number_input('MRT transport time (min)',0.0,60.0,1.0,.5)
    with d:
        half_life=st.number_input('Isotope physical half-life (min)',1.0,10000.0,109.8,.1)
        max_batches=st.number_input('Maximum MRT production batches (batches/day)',1,10,4,1)
    e,f=st.columns(2)
    with e: step=st.number_input('MRT production search increment (%)',1,25,5,1)
    with f: include_return=st.checkbox('Include MRT return/disposal endpoint',True)
    end()

    section('3. Capital and Operating Economics','All monetary assumptions are entered in USD and displayed with thousands separators.')
    a,b,c,d=st.columns(4)
    with a:
        scanner_capex=currency_input('CapEx per additional PET scanner (USD)', 2500000)
        inj_capex=currency_input('CapEx per additional injection room (USD)', 250000)
    with b:
        upt_capex=currency_input('CapEx per additional uptake room (USD)', 200000)
        conv_up=currency_input('Conventional production-upgrade CapEx per 10% (USD)', 650000)
    with c:
        mrt_up=currency_input('MRT production-upgrade CapEx per 10% (USD)', 600000)
        mrt_core=currency_input('MRT core infrastructure CapEx (USD)', 6000000)
    with d:
        endpoint_capex=currency_input('MRT endpoint installation CapEx (USD/endpoint)', 10000)
        budget=currency_input('Maximum available CapEx budget (USD)', 100000000)
    a,b,c,d=st.columns(4)
    with a:
        conv_base=currency_input('Annual base OpEx — conventional (USD/year)', 2000000)
        mrt_base=currency_input('Annual base OpEx — MRT (USD/year)', 1500000)
    with b:
        scanner_opex=currency_input('Annual OpEx per additional scanner (USD/year)', 300000)
        inj_opex=currency_input('Annual OpEx per additional injection room (USD/year)', 90000)
    with c:
        upt_opex=currency_input('Annual OpEx per additional uptake room (USD/year)', 70000)
        maintenance=currency_input('Annual MRT maintenance and support (USD/year)', 450000)
    with d:
        endpoint_opex=currency_input('Annual OpEx per MRT endpoint (USD/endpoint/year)', 5000)
        batch_cost=currency_input('Annual cost per additional recurring daily batch (USD/year)', 500000)
    a,b,c,d=st.columns(4)
    with a: contribution=currency_input('Net contribution per incremental patient (USD/patient)', 750)
    with b: days=st.number_input('Operating days/year',1,365,300,5)
    with c: years=st.number_input('Analysis period (years)',1,25,10,1)
    with d: discount=st.number_input('Discount rate (%)',0.0,50.0,10.0,.5)
    end()
    submitted=st.form_submit_button('RUN MRT PHARMA DIGITAL TWIN',use_container_width=True)

if submitted:
    inp=Inputs(current_patients,target_patients,current_scanners,current_injection,current_uptake,hours,scan_cycle,availability,inj_time,uptake_time,batch_cycle,doses,conv_transport,mrt_transport,half_life,max_batches,step,include_return,scanner_capex,inj_capex,upt_capex,conv_up,mrt_up,mrt_core,endpoint_capex,conv_base,mrt_base,scanner_opex,inj_opex,upt_opex,maintenance,endpoint_opex,batch_cost,contribution,days,years,discount,budget)
    r=run_model(inp)
    for w in r.validations: st.warning(w)
    st.markdown('## Digital Twin Results')
    opts=[('Conventional Expansion',r.conventional),('MRT Pharma Hybrid',r.mrt)]
    cols=st.columns(2)
    for col,(name,res) in zip(cols,opts):
        win=r.winner==res.architecture; css='card winner' if win else 'card'; badge='<div class="badge">✓ WINNER</div>' if win else ''
        if res.feasible:
            html=f'<div class="{css}"><b>{name}</b>{badge}<div class="big">${res.capex:,.0f}</div><div class="line"><span>NPV</span><span>${res.npv:,.0f}</span></div><div class="line"><span>Production increase</span><span>{res.production_increase_pct:.0f}%</span></div><div class="line"><span>Total scanners</span><span>{res.total_scanners:,}</span></div><div class="line"><span>Batches/day</span><span>{res.batches_day:,}</span></div></div>'
        else:
            html=f'<div class="{css}"><b>{name}</b><div class="big">NOT FEASIBLE</div><div class="line"><span>Reason</span><span>{res.reason}</span></div></div>'
        col.markdown(html,unsafe_allow_html=True)
    with st.expander('View full side-by-side implementation plan'):
        cs=st.columns(2)
        for c,(name,res) in zip(cs,opts):
            with c:
                st.markdown(f'### {name}')
                d={
                    'Feasible':'Yes' if res.feasible else 'No',
                    'Reason':res.reason,
                    'Patients served':f'{res.patients_served_day:,.0f} patients/day',
                    'Installed capacity':f'{res.installed_capacity_day:,.1f} patients/day',
                    'Production increase':f'{res.production_increase_pct:,.0f}%',
                    'Production batches':f'{res.batches_day:,} batches/day',
                    'Total PET scanners':f'{res.total_scanners:,}',
                    'Additional PET scanners':f'{res.additional_scanners:,}',
                    'Total injection rooms':f'{res.total_injection_rooms:,}',
                    'Additional injection rooms':f'{res.additional_injection_rooms:,}',
                    'Total uptake rooms':f'{res.total_uptake_rooms:,}',
                    'Additional uptake rooms':f'{res.additional_uptake_rooms:,}',
                    'MRT endpoints':f'{res.mrt_endpoints:,}' if res.architecture=='MRT Pharma Hybrid' else 'N/A',
                    'Activity retained at delivery':f'{res.retained_activity_pct:,.1f}%',
                    'CapEx':money(res.capex),
                    'Annual OpEx':money(res.annual_opex) + '/year',
                    'Annual net cash flow':money(res.annual_net_cash_flow) + '/year',
                    'NPV':money(res.npv),
                    'ROI':f'{res.roi_pct:,.1f}%',
                    'Payback':'Not achieved' if res.payback_years == float('inf') else f'{res.payback_years:,.1f} years'
                }
                st.dataframe(pd.DataFrame([{'Metric':k,'Value':v} for k,v in d.items()]),hide_index=True,use_container_width=True)
    if r.winner:
        w=r.mrt if r.winner=='MRT Pharma Hybrid' else r.conventional
        st.markdown(f'<div class="decision"><b>DIGITAL TWIN DECISION</b><h3>✓ {w.architecture}</h3><div>Highest modeled positive NPV: ${w.npv:,.0f}. Production increase: {w.production_increase_pct:.0f}%. Batches/day: {w.batches_day}. Total scanners: {w.total_scanners}.</div></div>',unsafe_allow_html=True)
    else: st.warning('Neither architecture produced a feasible positive-NPV plan.')
    m1,m2,m3,m4=st.columns(4); m1.metric('MRT configurations evaluated',f'{r.mrt_configurations_evaluated:,}'); m2.metric('Feasible MRT plans',f'{r.mrt_feasible_configurations:,}'); m3.metric('Positive-NPV MRT plans',f'{r.mrt_positive_npv_configurations:,}'); m4.metric('Future target (patients/day)',f'{target_patients:.0f}')
    fig=go.Figure(); xs=list(range(years+1)); rate=discount/100
    for name,res in opts:
        if not res.feasible: continue
        vals=[-res.capex]; total=-res.capex
        for y in range(1,years+1): total+=res.annual_net_cash_flow/((1+rate)**y); vals.append(total)
        fig.add_trace(go.Scatter(x=xs,y=vals,mode='lines+markers',name=name))
    fig.add_hline(y=0,line_dash='dash',line_color='#d71920'); fig.update_layout(template='plotly_white',height=470,xaxis_title='Year',yaxis_title='Discounted cumulative net cash flow (USD)'); st.plotly_chart(fig,use_container_width=True)
    rdf=pd.DataFrame([{'Option':'Conventional Expansion',**asdict(r.conventional)},{'Option':'MRT Pharma Hybrid',**asdict(r.mrt)}]); adf=pd.DataFrame([{'Assumption':k,'Value':v} for k,v in asdict(inp).items()])
    c1,c2=st.columns(2)
    with c1: st.download_button('Download CSV',rdf.to_csv(index=False).encode(),'mrt_pharma_results.csv','text/csv',use_container_width=True)
    with c2: st.download_button('Download Excel',excel_bytes(rdf,adf),'mrt_pharma_results.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
else:
    st.info('Complete the three sections and click **RUN MRT PHARMA DIGITAL TWIN**.')

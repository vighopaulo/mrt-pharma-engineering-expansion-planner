from dataclasses import asdict
import io,math,pandas as pd,plotly.graph_objects as go,streamlit as st
from model import *
from scoring import *
from diagnostics import *

st.set_page_config(page_title='MRT Pharma™ Digital Twin V2',page_icon='⚙️',layout='wide')
st.markdown("""<style>
:root{--red:#d71920;--green:#24984a;--line:#e2e4e8}.stApp{background:linear-gradient(180deg,#fff,#f6f7f9)}.block-container{max-width:1280px;padding-top:2.2rem!important}.brand,.panel{background:#fff;border:1px solid var(--line);border-radius:22px;box-shadow:0 12px 34px rgba(20,24,35,.07)}.brand{padding:24px 28px;margin-bottom:15px}.row{display:flex;justify-content:space-between;gap:30px;flex-wrap:wrap}.name{font-size:2.5rem;font-weight:950}.red{color:var(--red)}.rule{height:6px;background:linear-gradient(90deg,var(--red),#ff4b52);border-radius:99px;margin-top:16px}.panel{padding:18px 22px 8px;margin-bottom:14px}.card{min-height:300px;padding:20px;border:1px solid var(--line);border-top:7px solid var(--red);border-radius:22px;background:linear-gradient(145deg,#fff,#f5f6f8)}.winner{border:2px solid var(--green);border-top:8px solid var(--green);background:#eaf8ef}.badge{display:inline-block;background:var(--green);color:#fff;border-radius:99px;padding:5px 11px;font-weight:900;margin-top:8px}.big{font-size:1.65rem;font-weight:950;margin-top:12px}.line{display:flex;justify-content:space-between;border-top:1px solid #ddd;padding-top:9px;margin-top:9px;gap:15px}.line span:last-child{font-weight:900;text-align:right}.decision{background:#111;color:#fff;border-radius:18px;padding:18px 22px;margin:16px 0}div[data-testid="stFormSubmitButton"]>button{width:100%;min-height:3.1rem;background:var(--red);color:#fff;font-weight:950;border:none;border-radius:14px}
</style>""",unsafe_allow_html=True)
brand=('<div class="brand"><div class="row"><div><div class="name">MRT <span class="red">Pharma™</span></div><div style="font-size:1.35rem;font-weight:900">Decision-Support Digital Twin V2</div></div><div style="text-align:right"><b>Engineering Distributed Precision Oncology Today.</b><br><span style="color:#666">Expansion and greenfield planning with independent optimization and transparent scoring.</span></div></div><div class="rule"></div></div>')
st.markdown(brand,unsafe_allow_html=True)
def section(t,h):st.markdown(f'<div class="panel"><h3>{t}</h3><div style="color:#6f7480;margin-bottom:12px">{h}</div>',unsafe_allow_html=True)
def end():st.markdown('</div>',unsafe_allow_html=True)
def money(x):return f'${x:,.0f}'
def cur(label,default):
    s=st.text_input(label,value=f'${default:,.0f}')
    try:return float(s.replace('$','').replace(',',''))
    except:st.error(f'Enter a valid value for {label}.');return float(default)
def excel_bytes(a,b,c,d,e,f):
    x=io.BytesIO()
    with pd.ExcelWriter(x,engine='openpyxl') as w:
      a.to_excel(w,index=False,sheet_name='Selected Plans');b.to_excel(w,index=False,sheet_name='Assumptions');c.to_excel(w,index=False,sheet_name='Decision Score');d.to_excel(w,index=False,sheet_name='Conventional Ranked');e.to_excel(w,index=False,sheet_name='MRT Ranked');f.to_excel(w,index=False,sheet_name='Validations')
    return x.getvalue()

with st.form('form'):
 section('1. Project Mode, Hospital Today and Target','Greenfield mode permits zero current capacity.')
 a,b,c,d=st.columns(4)
 with a: mode=st.selectbox('Project type',['Expansion','Greenfield']);target=st.number_input('Future target patients/day',1.,5000.,200.,5.)
 with b: cp=st.number_input('Current patients/day',0.,5000.,50. if mode=='Expansion' else 0.,5.);cs=st.number_input('Current PET scanners',0,100,2 if mode=='Expansion' else 0,1)
 with c: ci=st.number_input('Current injection rooms',0,200,6 if mode=='Expansion' else 0,1);cu=st.number_input('Current uptake rooms',0,200,6 if mode=='Expansion' else 0,1)
 with d: cb=st.number_input('Current batches/day',0,20,2 if mode=='Expansion' else 0,1);doses=st.number_input('Usable patient doses/batch',1.,5000.,50.,5.)
 end()
 section('2. Operations, Production and Transport','Conventional and MRT batches are optimized independently.')
 a,b,c,d=st.columns(4)
 with a:hours=st.number_input('Clinical operating hours/day',1.,24.,18.,.5);pwin=st.number_input('Production window hours/day',1.,24.,18.,.5)
 with b:scycle=st.number_input('Scanner cycle min/patient',5.,180.,35.,5.);avail=st.number_input('Scanner availability %',10.,100.,85.,1.)
 with c:itime=st.number_input('Injection service min/patient',1.,180.,15.,1.);utime=st.number_input('Uptake occupancy min/patient',1.,240.,60.,5.)
 with d:bcycle=st.number_input('Production/release cycle min/batch',1.,720.,180.,15.);hl=st.number_input('Isotope half-life min',1.,10000.,109.8,.1)
 a,b,c,d=st.columns(4)
 with a:ct=st.number_input('Conventional transport min',0.,240.,20.,1.);mt=st.number_input('MRT transport min',0.,60.,1.,.5)
 with b:maxcb=st.number_input('Max conventional batches/day',1,20,4,1);maxmb=st.number_input('Max MRT batches/day',1,20,5,1)
 with c:maxcu=st.number_input('Max conventional production increase %',0,500,300,5);maxmu=st.number_input('Max MRT production increase %',0,500,300,5)
 with d:step=st.number_input('Production search increment %',1,25,5,1);ret=st.checkbox('Include MRT return/disposal endpoint',True)
 end()
 section('3. MRT Distributed-Care Limits','Existing inpatient rooms can be retrofitted; new rooms carry full costs.')
 a,b,c,d=st.columns(4)
 with a:mer=st.number_input('Max existing MRT inpatient rooms',0,500,40,1);mnr=st.number_input('Max new MRT inpatient rooms',0,500,0,1)
 with b:ppr=st.number_input('Patients/MRT inpatient room/day',.1,10.,1.,.1);mai=st.number_input('Max additional MRT injection rooms',0,100,6,1)
 with c:mau=st.number_input('Max additional MRT uptake rooms',0,100,6,1);support=st.number_input('Other MRT support endpoints',0,100,1,1)
 with d:cman=st.number_input('Conventional manual minutes/delivery',0.,120.,10.,1.);mman=st.number_input('MRT residual manual minutes/delivery',0.,120.,1.,.5)
 end()
 section('4. Hospital Decision Priorities','Select the three outcomes the hospital considers most important. The software converts the ranking into transparent normalized weights.')
 p1=st.selectbox('Priority 1 — most important',PRIORITY_OPTIONS,index=PRIORITY_OPTIONS.index('CapEx'))
 p2_options=[x for x in PRIORITY_OPTIONS if x!=p1]
 p2_default='NPV' if 'NPV' in p2_options else p2_options[0]
 p2=st.selectbox('Priority 2',p2_options,index=p2_options.index(p2_default))
 p3_options=[x for x in p2_options if x!=p2]
 p3_default='ROI' if 'ROI' in p3_options else p3_options[0]
 p3=st.selectbox('Priority 3',p3_options,index=p3_options.index(p3_default))
 end()
 section('5. Capital and Incremental Operating Economics','Expansion uses incremental economics; Greenfield uses total project economics.')
 a,b,c,d=st.columns(4)
 with a:scap=cur('CapEx/PET scanner',2500000);icap=cur('CapEx/injection room',250000)
 with b:ucap=cur('CapEx/uptake room',200000);cucap=cur('Conventional production CapEx/10%',650000)
 with c:mucap=cur('MRT production CapEx/10%',600000);mcore=cur('MRT core infrastructure CapEx',6000000)
 with d:ecap=cur('MRT endpoint installation CapEx',10000);budget=cur('Maximum CapEx budget',100000000)
 a,b,c,d=st.columns(4)
 with a:retro=cur('Retrofit CapEx/existing MRT room',20000);newcap=cur('CapEx/new MRT inpatient room',500000)
 with b:cofix=cur('Annual fixed incremental OpEx conventional',2000000);mofix=cur('Annual fixed incremental OpEx MRT',1500000)
 with c:sopex=cur('Annual OpEx/additional scanner',300000);iopex=cur('Annual OpEx/additional injection room',90000)
 with d:uopex=cur('Annual OpEx/additional uptake room',70000);maint=cur('Annual MRT maintenance',450000)
 a,b,c,d=st.columns(4)
 with a:eopex=cur('Annual OpEx/MRT endpoint',5000);nropex=cur('Annual OpEx/new MRT inpatient room',80000)
 with b:cbcost=cur('Annual cost/additional conventional daily batch',500000);mbcost=cur('Annual cost/additional MRT daily batch',500000)
 with c:contrib=cur('Net contribution/incremental patient',750);days=st.number_input('Operating days/year',1,365,300,5)
 with d:years=st.number_input('Analysis years',1,25,10,1);disc=st.number_input('Discount rate %',0.,50.,10.,.5)
 end()
 submitted=st.form_submit_button('RUN MRT PHARMA DIGITAL TWIN',use_container_width=True)

if submitted:
 if mode=='Greenfield':cp=0.;cs=ci=cu=cb=0
 inp=Inputs(mode,cp,target,cs,ci,cu,cb,doses,hours,pwin,scycle,avail,itime,utime,bcycle,ct,mt,hl,maxcb,maxmb,maxcu,maxmu,step,mer,mnr,ppr,mai,mau,ret,support,scap,icap,ucap,cucap,mucap,mcore,ecap,retro,newcap,budget,cofix,mofix,sopex,iopex,uopex,maint,eopex,nropex,cbcost,mbcost,cman,mman,contrib,days,years,disc)
 warnings=validate_inputs(inp)
 for w in warnings:st.warning(w)
 conv,cstats,cranked,cnear=optimize_conventional(inp);mrt,mstats,mranked,mnear=optimize_mrt(inp)
 decision_weights=build_priority_weights(p1,p2,p3)
 csco,msco,rows=compute_scores(conv,mrt,decision_weights);strength=recommendation_strength(csco,msco)
 winner='Conventional Expansion' if csco>msco else 'MRT Pharma Hybrid' if msco>csco else None
 st.markdown('## Digital Twin Results')
 st.caption(f'Decision profile: 1) {p1} · 2) {p2} · 3) {p3}')
 opts=[('Conventional Expansion',conv,csco),('MRT Pharma Hybrid',mrt,msco)];cols=st.columns(2)
 for col,(name,r,s) in zip(cols,opts):
  win=winner==name;css='card winner' if win else 'card';badge='<div class="badge">✓ RECOMMENDED</div>' if win else ''
  if r.feasible:
   pb='Not achieved' if math.isinf(r.payback_years) else f'{r.payback_years:.1f} years'
   html=f'<div class="{css}"><b>{name}</b>{badge}<div class="big">{s:.1f}/100</div><div class="line"><span>CapEx</span><span>{money(r.capex)}</span></div><div class="line"><span>NPV</span><span>{money(r.npv)}</span></div><div class="line"><span>ROI</span><span>{r.roi_pct:.1f}%</span></div><div class="line"><span>Payback</span><span>{pb}</span></div><div class="line"><span>Batches/day</span><span>{r.batches_day}</span></div></div>'
  else:html=f'<div class="{css}"><b>{name}</b><div class="big">NOT FEASIBLE</div><div class="line"><span>Reason</span><span>{r.reason}</span></div><div class="line"><span>Binding constraint</span><span>{r.binding_constraint}</span></div></div>'
  col.markdown(html,unsafe_allow_html=True)
 with st.expander('View full side-by-side implementation plan'):
  dc=st.columns(2)
  for col,(name,r,s) in zip(dc,opts):
   with col:
    st.markdown(f'### {name}')
    data={'Feasible':'Yes' if r.feasible else 'No','Reason':r.reason,'Decision score':f'{s:.1f}/100','Patients served/day':f'{r.patients_served_day:.1f}','Installed capacity/day':f'{r.installed_capacity_day:.1f}','Reserve/day':f'{r.reserve_capacity_day:.1f}','Binding constraint':r.binding_constraint,'Production increase':f'{r.production_increase_pct:.0f}%','Batches/day':r.batches_day,'Total scanners':r.total_scanners,'Additional scanners':r.additional_scanners,'Total injection rooms':r.total_injection_rooms,'Additional injection rooms':r.additional_injection_rooms,'Total uptake rooms':r.total_uptake_rooms,'Additional uptake rooms':r.additional_uptake_rooms,'Existing MRT inpatient rooms':r.existing_mrt_inpatient_rooms if r.architecture.startswith('MRT') else 'N/A','New MRT inpatient rooms':r.new_mrt_inpatient_rooms if r.architecture.startswith('MRT') else 'N/A','MRT endpoints':r.mrt_endpoints if r.architecture.startswith('MRT') else 'N/A','Activity retained':f'{r.retained_activity_pct:.2f}%','Annual logistics hours':f'{r.annual_logistics_hours:,.0f}','CapEx':money(r.capex),'Annual OpEx':money(r.annual_opex),'Annual net cash flow':money(r.annual_net_cash_flow),'NPV':money(r.npv),'ROI':f'{r.roi_pct:.1f}%','Payback':'Not achieved' if math.isinf(r.payback_years) else f'{r.payback_years:.1f} years'}
    st.dataframe(pd.DataFrame([{'Metric':k,'Value':v} for k,v in data.items()]),hide_index=True,use_container_width=True)
 with st.expander('How the decision score was calculated'):
  sdf=pd.DataFrame(rows);sdf['Weight']=sdf['Weight'].map(lambda x:f'{x:.0%}');st.dataframe(sdf,hide_index=True,use_container_width=True)
 if winner:
  wr=conv if winner=='Conventional Expansion' else mrt;ws=csco if winner=='Conventional Expansion' else msco;ls=msco if winner=='Conventional Expansion' else csco
  st.markdown(f'<div class="decision"><b>DIGITAL TWIN DECISION</b><h3>✓ {winner}</h3><div>{strength} under the hospital-selected priorities: {p1}, {p2}, and {p3}. Score {ws:.1f} versus {ls:.1f}. Selected plan serves {wr.patients_served_day:.0f} patients/day using {wr.batches_day} batches/day, {wr.total_scanners} scanners and a {wr.production_increase_pct:.0f}% production increase.</div></div>',unsafe_allow_html=True)
 else:
  st.warning('Neither architecture produced a feasible positive-NPV plan.');st.info('Conventional: '+near_feasible_message(cnear,inp));st.info('MRT: '+near_feasible_message(mnear,inp))
 st.markdown('### Search Statistics');st.dataframe(pd.DataFrame([{'Architecture':'Conventional Expansion',**asdict(cstats)},{'Architecture':'MRT Pharma Hybrid',**asdict(mstats)}]),hide_index=True,use_container_width=True)
 st.markdown('### Discounted Cumulative Cash Flow');fig=go.Figure();xs=list(range(years+1));rate=disc/100
 for name,r,_ in opts:
  if not r.feasible:continue
  vals=[-r.capex];total=-r.capex
  for y in range(1,years+1):total+=r.annual_net_cash_flow/((1+rate)**y);vals.append(total)
  fig.add_trace(go.Scatter(x=xs,y=vals,mode='lines+markers',name=name))
 fig.add_hline(y=0,line_dash='dash',line_color='#d71920');fig.update_layout(template='plotly_white',height=470,xaxis_title='Year',yaxis_title='Discounted cumulative net cash flow (USD)');st.plotly_chart(fig,use_container_width=True)
 selected=pd.DataFrame([{'Option':'Conventional Expansion',**asdict(conv),'Decision Score':csco},{'Option':'MRT Pharma Hybrid',**asdict(mrt),'Decision Score':msco}]);ass_rows=[{'Assumption':k,'Value':v} for k,v in asdict(inp).items()]
 ass_rows += [{'Assumption':'Priority 1','Value':p1},{'Assumption':'Priority 2','Value':p2},{'Assumption':'Priority 3','Value':p3}]
 ass_rows += [{'Assumption':f'Decision weight — {k}','Value':v} for k,v in decision_weights.items()]
 ass=pd.DataFrame(ass_rows);cr=pd.DataFrame([asdict(x) for x in cranked]);mr=pd.DataFrame([asdict(x) for x in mranked]);wd=pd.DataFrame({'Validation':warnings})
 c1,c2=st.columns(2)
 with c1:st.download_button('Download CSV',selected.to_csv(index=False).encode(),'mrt_pharma_v2_results.csv','text/csv',use_container_width=True)
 with c2:st.download_button('Download Excel',excel_bytes(selected,ass,pd.DataFrame(rows),cr,mr,wd),'mrt_pharma_v2_results.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
else:st.info('Complete the assumptions and click **RUN MRT PHARMA DIGITAL TWIN**.')

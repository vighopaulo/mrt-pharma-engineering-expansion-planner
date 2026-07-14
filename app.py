from dataclasses import asdict
import io,math,pandas as pd,plotly.graph_objects as go,streamlit as st
from domain.models import ModelInputs, ProjectMode, PRIORITY_METRICS
from engines.optimization import conventional,mrt
from engines.decision import weights,decide
from engines.diagnostics import validate
from ui.state import initialize_project_state, apply_project_mode

st.set_page_config(page_title="MRT Pharma V2",page_icon="⚙️",layout="wide")
st.markdown("""<style>
.stApp{background:linear-gradient(180deg,#fff,#f6f7f9)}.block-container{max-width:1280px;padding-top:2rem}
.brand,.panel{background:#fff;border:1px solid #e2e4e8;border-radius:22px;box-shadow:0 12px 34px rgba(20,24,35,.07)}
.brand{padding:24px 28px;margin-bottom:15px}.name{font-size:2.5rem;font-weight:950}.red{color:#d71920}.rule{height:6px;background:#d71920;border-radius:99px;margin-top:16px}
.panel{padding:18px 22px 8px;margin-bottom:14px}.card{min-height:280px;padding:20px;border:1px solid #e2e4e8;border-top:7px solid #d71920;border-radius:22px;background:#fff}
.winner{border:2px solid #24984a;border-top:8px solid #24984a;background:#eaf8ef}.badge{display:inline-block;background:#24984a;color:#fff;border-radius:99px;padding:5px 11px;font-weight:900}
.big{font-size:1.7rem;font-weight:950;margin-top:12px}.line{display:flex;justify-content:space-between;border-top:1px solid #ddd;padding-top:9px;margin-top:9px}.line span:last-child{font-weight:900}
.decision{background:#111;color:#fff;border-radius:18px;padding:18px 22px;margin:16px 0}div[data-testid="stFormSubmitButton"]>button{width:100%;min-height:3.1rem;background:#d71920;color:#fff;font-weight:950}
</style>""",unsafe_allow_html=True)
st.markdown('<div class="brand"><div class="name">MRT <span class="red">Pharma™</span></div><h3>Decision-Support Digital Twin V2</h3><div>Ground-up expansion and greenfield planning.</div><div class="rule"></div></div>',unsafe_allow_html=True)

def section(t,s):st.markdown(f'<div class="panel"><h3>{t}</h3><div style="color:#6f7480">{s}</div>',unsafe_allow_html=True)
def end():st.markdown("</div>",unsafe_allow_html=True)
def pmoney(x):return float(x.replace("$","").replace(",","") or 0)
def money(label,default,key):
    try:return pmoney(st.text_input(label,f"${default:,.0f}",key=key))
    except:st.error("Enter a valid amount");return default
initialize_project_state(st.session_state)
section("1. Project Mode, Hospital Today and Target","Greenfield stores the Expansion baseline, then sets and locks all current values at zero.")
mode=st.selectbox("Project type",["Expansion","Greenfield"],key="mode",on_change=apply_project_mode,args=(st.session_state,))
apply_project_mode(st.session_state)
green=mode=="Greenfield"
a,b,c,d=st.columns(4)
with a:cp=st.number_input("Current patients/day",0.0,5000.0,key="cp",disabled=green);target=st.number_input("Target patients/day",1.0,5000.0,200.0,5.0)
with b:cs=st.number_input("Current scanners",0,100,key="cs",disabled=green);ci=st.number_input("Current injection rooms",0,200,key="ci",disabled=green)
with c:cu=st.number_input("Current uptake rooms",0,200,key="cu",disabled=green);cb=st.number_input("Current batches/day",0,20,key="cb",disabled=green)
with d:doses=st.number_input("Reference usable doses/batch",1.0,5000.0,50.0,5.0)
end()

with st.form("f"):
 section("2. Hospital Decision Profile","Choose three different priorities.")
 a,b,c=st.columns(3)
 with a:p1=st.selectbox("Priority 1",PRIORITY_METRICS,index=0)
 with b:p2=st.selectbox("Priority 2",PRIORITY_METRICS,index=1)
 with c:p3=st.selectbox("Priority 3",PRIORITY_METRICS,index=2)
 end()
 section("3. Operations and Production","Batch counts are optimized independently.")
 a,b,c,d=st.columns(4)
 with a:h=st.number_input("Operating hours/day",1.0,24.0,18.0,.5);pw=st.number_input("Production window hours/day",1.0,24.0,18.0,.5)
 with b:sc=st.number_input("Scanner cycle min",5.0,180.0,35.0,5.0);av=st.number_input("Scanner availability %",10.0,100.0,85.0,1.0)
 with c:it=st.number_input("Injection min",1.0,180.0,15.0,1.0);ut=st.number_input("Uptake min",1.0,240.0,60.0,5.0)
 with d:bc=st.number_input("Batch cycle min",1.0,720.0,180.0,15.0);hl=st.number_input("Half-life min",1.0,10000.0,109.8,.1)
 a,b,c,d=st.columns(4)
 with a:ct=st.number_input("Conventional transport min",0.0,240.0,20.0,1.0);mt=st.number_input("MRT transport min",0.0,60.0,1.0,.5)
 with b:maxcb=st.number_input("Max conventional batches",1,20,4);maxmb=st.number_input("Max MRT batches",1,20,5)
 with c:maxcu=st.number_input("Max conventional increase %",0,500,300,5);maxmu=st.number_input("Max MRT increase %",0,500,300,5)
 with d:step=st.number_input("Search step %",1,25,5);ret=st.checkbox("Include return endpoint",True)
 end()
 section("4. MRT Distributed Care","Scanners are not endpoints by default.")
 a,b,c,d=st.columns(4)
 with a:mer=st.number_input("Max existing MRT rooms",0,100,20);mnr=st.number_input("Max new MRT rooms",0,100,0)
 with b:ppr=st.number_input("Patients/MRT room/day",.1,10.0,1.0,.1);mai=st.number_input("Max additional MRT injection rooms",0,20,2)
 with c:mau=st.number_input("Max additional MRT uptake rooms",0,20,2);oe=st.number_input("Other endpoints",0,50,1)
 with d:iue=st.checkbox("Carrier serves uptake rooms",False);cm=st.number_input("Conventional manual min/delivery",0.0,120.0,10.0);mm=st.number_input("MRT manual min/delivery",0.0,120.0,1.0)
 end()
 section("5. Economics","Expansion is incremental; Greenfield is total-project economics.")
 a,b,c,d=st.columns(4)
 with a:sca=money("Scanner CapEx",2500000,"sca");ica=money("Injection-room CapEx",250000,"ica")
 with b:uca=money("Uptake-room CapEx",200000,"uca");cuc=money("Conventional upgrade CapEx/10%",650000,"cuc")
 with c:muc=money("MRT upgrade CapEx/10%",600000,"muc");mcore=money("MRT core CapEx",6000000,"mcore")
 with d:eca=money("Endpoint CapEx",10000,"eca");budget=money("CapEx budget",100000000,"budget")
 a,b,c,d=st.columns(4)
 with a:rca=money("Existing-room retrofit CapEx",20000,"rca");nrc=money("New MRT-room CapEx",500000,"nrc")
 with b:cfo=money("Conventional fixed OpEx",2000000,"cfo");mfo=money("MRT fixed OpEx",1500000,"mfo")
 with c:so=money("Scanner OpEx",300000,"so");io=money("Injection-room OpEx",90000,"io")
 with d:uo=money("Uptake-room OpEx",70000,"uo");maint=money("MRT maintenance",450000,"maint")
 a,b,c,d=st.columns(4)
 with a:eo=money("Endpoint OpEx",5000,"eo");nro=money("New MRT-room OpEx",80000,"nro")
 with b:cbc=money("Extra conventional batch OpEx",500000,"cbc");mbc=money("Extra MRT batch OpEx",500000,"mbc")
 with c:contrib=money("Contribution/patient",750,"contrib");days=st.number_input("Operating days/year",1,365,300,5)
 with d:years=st.number_input("Analysis years",1,25,10);disc=st.number_input("Discount rate %",0.0,50.0,10.0,.5)
 end()
 run=st.form_submit_button("RUN MRT PHARMA DIGITAL TWIN",use_container_width=True)

if run:
 inp=ModelInputs(project_mode=ProjectMode.GREENFIELD if green else ProjectMode.EXPANSION,current_patients=cp,target_patients=target,current_scanners=cs,current_injection_rooms=ci,current_uptake_rooms=cu,current_batches=cb,doses_per_batch=doses,operating_hours=h,production_window_hours=pw,scan_cycle_min=sc,scanner_availability_pct=av,injection_min=it,uptake_min=ut,batch_cycle_min=bc,conventional_transport_min=ct,mrt_transport_min=mt,half_life_min=hl,max_conventional_batches=maxcb,max_mrt_batches=maxmb,max_conventional_upgrade_pct=maxcu,max_mrt_upgrade_pct=maxmu,upgrade_step_pct=step,max_existing_mrt_rooms=mer,max_new_mrt_rooms=mnr,patients_per_mrt_room=ppr,max_additional_mrt_injection_rooms=mai,max_additional_mrt_uptake_rooms=mau,include_uptake_endpoints=iue,include_return_endpoint=ret,other_mrt_endpoints=oe,scanner_capex=sca,injection_capex=ica,uptake_capex=uca,conventional_upgrade_capex_per_10pct=cuc,mrt_upgrade_capex_per_10pct=muc,mrt_core_capex=mcore,endpoint_capex=eca,existing_mrt_room_retrofit_capex=rca,new_mrt_room_capex=nrc,capex_budget=budget,conventional_fixed_opex=cfo,mrt_fixed_opex=mfo,scanner_opex=so,injection_opex=io,uptake_opex=uo,mrt_maintenance=maint,endpoint_opex=eo,new_mrt_room_opex=nro,conventional_extra_batch_opex=cbc,mrt_extra_batch_opex=mbc,conventional_manual_min=cm,mrt_manual_min=mm,contribution_per_patient=contrib,operating_days=days,analysis_years=years,discount_rate_pct=disc,priority_1=p1,priority_2=p2,priority_3=p3).normalized()
 issues=validate(inp)
 if issues:
  for x in issues:st.error(x)
  st.stop()
 c,csx,_=conventional(inp);m,msx,_=mrt(inp);d=decide(inp,c,m)
 st.markdown("## Results");cols=st.columns(2)
 for col,(name,r,s) in zip(cols,[("Conventional Expansion",c,d.conventional_score),("MRT Pharma Hybrid",m,d.mrt_score)]):
  win=d.recommendation and d.recommendation.value==name;cls="card winner" if win else "card";badge='<div class="badge">✓ RECOMMENDED</div>' if win else ""
  if r.feasible:
   pb="Not achieved" if math.isinf(r.payback_years) else f"{r.payback_years:.1f} years"
   html=f'<div class="{cls}"><b>{name}</b>{badge}<div class="big">{s:.1f}/100</div><div class="line"><span>CapEx</span><span>${r.capex:,.0f}</span></div><div class="line"><span>NPV</span><span>${r.npv:,.0f}</span></div><div class="line"><span>ROI</span><span>{r.roi_pct:.1f}%</span></div><div class="line"><span>Payback</span><span>{pb}</span></div></div>'
  else:html=f'<div class="{cls}"><b>{name}</b><div class="big">NOT FEASIBLE</div><div class="line"><span>Reason</span><span>{r.reason}</span></div></div>'
  col.markdown(html,unsafe_allow_html=True)
 st.dataframe(pd.DataFrame([{"Metric":k,"Weight":v} for k,v in sorted(weights(p1,p2,p3).items(),key=lambda x:-x[1])]),hide_index=True,use_container_width=True)
 with st.expander("Full comparison"):
  st.dataframe(pd.DataFrame([{"Option":"Conventional",**asdict(c)},{"Option":"MRT",**asdict(m)}]),hide_index=True,use_container_width=True)
 with st.expander("Score breakdown"):st.dataframe(pd.DataFrame(d.breakdown),hide_index=True,use_container_width=True)
 st.dataframe(pd.DataFrame(d.sensitivity),hide_index=True,use_container_width=True)
 if d.recommendation:
  st.markdown(f'<div class="decision"><h3>✓ {d.recommendation.value}</h3><div>{d.strength}. Financial winner: {d.financial_winner.value if d.financial_winner else "None"}.</div></div>',unsafe_allow_html=True)
 else:st.warning("Neither architecture is feasible.")
 rdf=pd.DataFrame([{"Option":"Conventional",**asdict(c)},{"Option":"MRT",**asdict(m)}])
 assumptions=pd.DataFrame([{"Assumption":k,"Value":v} for k,v in asdict(inp).items()])
 stats_df=pd.DataFrame([{"Architecture":"Conventional",**asdict(csx)},{"Architecture":"MRT",**asdict(msx)}])
 st.markdown("### Search Statistics")
 st.dataframe(stats_df,hide_index=True,use_container_width=True)
 x1,x2=st.columns(2)
 with x1:
  st.download_button("Download CSV",rdf.to_csv(index=False).encode(),"mrt_v2_results.csv","text/csv",use_container_width=True)
 with x2:
  buffer=io.BytesIO()
  with pd.ExcelWriter(buffer,engine="openpyxl") as writer:
   rdf.to_excel(writer,index=False,sheet_name="Results")
   assumptions.to_excel(writer,index=False,sheet_name="Assumptions")
   pd.DataFrame(d.breakdown).to_excel(writer,index=False,sheet_name="Decision Score")
   pd.DataFrame(d.sensitivity).to_excel(writer,index=False,sheet_name="Sensitivity")
   stats_df.to_excel(writer,index=False,sheet_name="Search Statistics")
  st.download_button("Download Excel",buffer.getvalue(),"mrt_v2_results.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)

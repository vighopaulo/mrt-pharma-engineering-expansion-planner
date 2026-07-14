from dataclasses import replace
from domain.models import Inputs,ProjectMode,Architecture
from engines.optimization import conventional,mrt
from engines.decision import weights,decide

def base():
 return Inputs(ProjectMode.EXPANSION,50,100,2,6,6,2,50,18,18,35,85,15,60,180,20,1,109.8,4,5,200,200,5,20,0,1,2,2,False,True,1,2500000,250000,200000,650000,600000,6000000,10000,20000,500000,100000000,2000000,1500000,300000,90000,70000,450000,5000,80000,500000,500000,10,1,750,300,10,10,"Net Present Value","Lowest Capital Expenditure","Highest ROI")
def test_greenfield_zero():
 i=replace(base(),project_mode=ProjectMode.GREENFIELD).normalized()
 assert (i.current_patients,i.current_scanners,i.current_injection_rooms,i.current_uptake_rooms,i.current_batches)==(0,0,0,0,0)
def test_greenfield_runs():
 i=replace(base(),project_mode=ProjectMode.GREENFIELD).normalized();assert conventional(i)[0] and mrt(i)[0]
def test_weights():
 assert abs(sum(weights("Net Present Value","Lowest Capital Expenditure","Highest ROI").values())-1)<1e-9
def test_conventional_wins():
 i=replace(base(),target_patients=75,mrt_core_capex=25000000,conventional_transport_min=3);d=decide(i,conventional(i)[0],mrt(i)[0]);assert d.recommendation==Architecture.CONVENTIONAL
def test_mrt_wins():
 i=replace(base(),target_patients=75,conventional_upgrade_capex_per_10pct=4000000,mrt_upgrade_capex_per_10pct=100000,mrt_core_capex=100000,mrt_fixed_opex=100000,mrt_maintenance=10000,endpoint_opex=100,mrt_extra_batch_opex=10000,conventional_transport_min=60,priority_1="Lowest Annual OpEx",priority_2="Highest Activity Retention",priority_3="Lowest Logistics Labor Burden")
 c=conventional(i)[0];m=mrt(i)[0];d=decide(i,c,m);assert m.feasible and d.recommendation==Architecture.MRT
def test_neither():
 i=replace(base(),target_patients=500,capex_budget=1000000);assert not conventional(i)[0].feasible and not mrt(i)[0].feasible
def test_equal_revenue():
 i=base();assert conventional(i)[0].annual_revenue==mrt(i)[0].annual_revenue
def test_scanners_not_endpoints():
 i=replace(base(),max_existing_mrt_rooms=0,max_new_mrt_rooms=0,max_additional_mrt_injection_rooms=0,max_additional_mrt_uptake_rooms=0,other_mrt_endpoints=0)
 x=mrt(i)[0];assert x.mrt_endpoints==1+i.current_injection_rooms+1

def test_greenfield_state_zero_and_restore():
 from ui.state import initialize_project_state,apply_project_mode
 state={"mode":"Expansion","cp":75.0,"cs":3,"ci":8,"cu":9,"cb":3}
 initialize_project_state(state)
 state["mode"]="Greenfield";apply_project_mode(state)
 assert (state["cp"],state["cs"],state["ci"],state["cu"],state["cb"])==(0.0,0,0,0,0)
 state["mode"]="Expansion";apply_project_mode(state)
 assert (state["cp"],state["cs"],state["ci"],state["cu"],state["cb"])==(75.0,3,8,9,3)

def test_batch_cost_baseline_not_charged_at_current_batches():
 i=base()
 x=conventional(i)[0]
 assert x.batches>=i.current_batches

def test_input_construction_uses_named_fields():
 i=base()
 assert i.project_mode==ProjectMode.EXPANSION
 assert i.current_patients==50

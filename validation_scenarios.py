from model import Inputs, run_model

def base_inputs():
    return Inputs(50,200,2,6,6,18,35,85,15,60,180,50,20,1,109.8,4,5,True,2500000,250000,200000,650000,600000,6000000,10000,2000000,1500000,300000,90000,70000,450000,5000,500000,750,300,10,10,100000000)

def replace(x,**kw):
    d=x.__dict__.copy(); d.update(kw); return Inputs(**d)

def scenario_conventional_wins():
    r=run_model(replace(base_inputs(),target_patients_day=75,mrt_core_capex=20000000,conventional_transport_min=3))
    assert r.winner=='Conventional Expansion',r

def scenario_mrt_wins():
    r=run_model(replace(base_inputs(),conventional_upgrade_capex_per_10pct=2000000,mrt_core_capex=2500000,annual_cost_per_additional_daily_batch=150000,conventional_transport_min=35))
    assert r.winner=='MRT Pharma Hybrid',r

def scenario_neither_feasible():
    r=run_model(replace(base_inputs(),target_patients_day=500,maximum_capex_budget=1000000))
    assert r.winner is None,r

if __name__=='__main__':
    scenario_conventional_wins(); scenario_mrt_wins(); scenario_neither_feasible(); print('All validation scenarios passed.')

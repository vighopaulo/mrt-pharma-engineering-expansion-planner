import math
def metrics(capex,opex,inp):
    revenue=max(0,inp.target_patients-inp.current_patients)*inp.operating_days*inp.contribution_per_patient
    ncf=revenue-opex
    r=inp.discount_rate_pct/100
    npv=-capex+sum(ncf/((1+r)**y) for y in range(1,inp.analysis_years+1))
    roi=(((ncf*inp.analysis_years)-capex)/capex*100) if capex>0 else 0
    payback=capex/ncf if ncf>0 else math.inf
    return revenue,ncf,npv,roi,payback

import math
from domain.models import PRIORITIES,Architecture,Decision
MAP={"Net Present Value":("npv","higher"),"Lowest Capital Expenditure":("capex","lower"),"Highest ROI":("roi_pct","higher"),
"Fastest Payback":("payback_years","lower"),"Lowest Annual OpEx":("annual_opex","lower"),
"Highest Activity Retention":("retained_activity_pct","higher"),"Highest Reserve Capacity":("reserve_capacity","higher"),
"Greatest Batch Flexibility":("feasible_batch_count","higher"),"Lowest Production Increase":("production_increase_pct","lower"),
"Fewest Additional Dedicated Rooms":("rooms","lower"),"Lowest Logistics Labor Burden":("annual_logistics_hours","lower"),
"Highest Resilience":("resilience_ratio","higher")}

def weights(p1,p2,p3):
    if len({p1,p2,p3})!=3:raise ValueError("Priorities must be different")
    w={m:0 for m in PRIORITIES};w[p1]=.30;w[p2]=.20;w[p3]=.15
    r=[m for m in PRIORITIES if m not in {p1,p2,p3}]
    for m in r:w[m]=.35/len(r)
    return w

def pre(name):
    if name=="Financial only":
        w={m:0 for m in PRIORITIES};w["Net Present Value"]=1;return w
    if name=="Capital constrained":return weights("Lowest Capital Expenditure","Lowest Annual OpEx","Fastest Payback")
    return {m:1/len(PRIORITIES) for m in PRIORITIES}

def raw(x,m):
    k,_=MAP[m]
    return x.additional_injection_rooms+x.additional_uptake_rooms if k=="rooms" else float(getattr(x,k))

def norm(a,b,d):
    if d=="higher":
        if a<=0 and b<=0:return 0,0
        z=max(a,b);return max(0,a)/z,max(0,b)/z
    if a==b:return 1,1
    if a==0:return 1,0
    if b==0:return 0,1
    if math.isinf(a):return 0,1
    if math.isinf(b):return 1,0
    z=min(a,b);return z/a,z/b

def score(c,m,w):
    if c.feasible and not m.feasible:return 100,0,[]
    if m.feasible and not c.feasible:return 0,100,[]
    if not c.feasible and not m.feasible:return 0,0,[]
    cs=ms=0;rows=[]
    for metric,wt in w.items():
        a,b=raw(c,metric),raw(m,metric);cn,mn=norm(a,b,MAP[metric][1]);cp,mp=cn*wt*100,mn*wt*100;cs+=cp;ms+=mp
        rows.append({"Metric":metric,"Weight":wt,"Conventional Raw":a,"MRT Raw":b,"Conventional Points":cp,"MRT Points":mp})
    return cs,ms,rows

def choose(c,m,cs,ms):
    if c.feasible and not m.feasible:return Architecture.CONVENTIONAL
    if m.feasible and not c.feasible:return Architecture.MRT
    if not c.feasible and not m.feasible:return None
    return Architecture.CONVENTIONAL if cs>ms else Architecture.MRT if ms>cs else None

def decide(inp,c,m):
    cs,ms,rows=score(c,m,weights(inp.priority_1,inp.priority_2,inp.priority_3))
    fw=choose(c,m,c.npv,m.npv)
    overall=choose(c,m,cs,ms);d=abs(cs-ms);strength="Essentially tied" if d<3 else "Moderate preference" if d<8 else "Strong preference"
    sens=[]
    for name in ["Financial only","Capital constrained","Balanced"]:
        a,b,_=score(c,m,pre(name));w=choose(c,m,a,b);sens.append({"Profile":name,"Conventional Score":a,"MRT Score":b,"Winner":w.value if w else "No winner"})
    return Decision(fw,overall,cs,ms,strength,rows,sens)

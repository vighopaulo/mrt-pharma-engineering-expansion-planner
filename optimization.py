from domain.models import Architecture,Result,Stats
from engines.engineering import retention,scanner_capacity,room_capacity,required_scanners,required_rooms,max_batches
from engines.finance import metrics

def make_result(arch,inp,caps,upgrade,batches,ts,ads,ti,ai,tu,au,er,nr,endpoints,ret,logistics,capex,opex):
    installed=min(caps.values()); revenue,ncf,npv,roi,payback=metrics(capex,opex,inp)
    if installed+1e-9<inp.target_patients: feasible=False; reason=f"{min(caps,key=caps.get)} capacity is below target."
    elif capex>inp.capex_budget: feasible=False; reason="CapEx exceeds budget."
    elif ncf<=0: feasible=False; reason="Annual net cash flow is non-positive."
    elif npv<=0: feasible=False; reason="NPV is non-positive."
    else: feasible=True; reason="Feasible."
    return Result(arch,feasible,reason,min(caps,key=caps.get),installed,min(installed,inp.target_patients),
                  max(0,installed-inp.target_patients),caps["Dose"],caps["Scanner"],caps["Injection"],caps["Uptake"],
                  upgrade,batches,ts,ads,ti,ai,tu,au,er,nr,endpoints,ret*100,logistics,
                  max(0,(caps["Scanner"]-inp.target_patients)/max(1,inp.target_patients)),0,
                  capex,opex,revenue,ncf,npv,roi,payback)

def best(cands):
    f=[x for x in cands if x.feasible]
    if f:
        f.sort(key=lambda x:(-x.npv,x.capex,-x.roi_pct,x.payback_years)); return f[0]
    cands.sort(key=lambda x:(x.served_patients,-x.capex),reverse=True)
    return cands[0] if cands else None

def conventional(inp):
    inp=inp.normalized(); stats=Stats(); cands=[]; batches_ok=set()
    ret=retention(inp.conventional_transport_min,inp.half_life_min)
    ts=required_scanners(inp.target_patients,inp.operating_hours,inp.scan_cycle_min,inp.scanner_availability_pct)
    ads=max(0,ts-inp.current_scanners)
    for b in range(max(1,inp.current_batches),min(inp.max_conventional_batches,max_batches(inp.production_window_hours,inp.batch_cycle_min))+1):
        ti=max(inp.current_injection_rooms,required_rooms(inp.target_patients,b,inp.operating_hours,inp.injection_min))
        tu=max(inp.current_uptake_rooms,required_rooms(inp.target_patients,b,inp.operating_hours,inp.uptake_min))
        ai,au=max(0,ti-inp.current_injection_rooms),max(0,tu-inp.current_uptake_rooms)
        for u in range(0,inp.max_conventional_upgrade_pct+1,max(1,inp.upgrade_step_pct)):
            stats.generated+=1
            caps={"Dose":inp.doses_per_batch*(1+u/100)*b*ret,
                  "Scanner":scanner_capacity(ts,inp.operating_hours,inp.scan_cycle_min,inp.scanner_availability_pct),
                  "Injection":room_capacity(ti,inp.operating_hours,inp.injection_min),
                  "Uptake":room_capacity(tu,inp.operating_hours,inp.uptake_min)}
            capex=ads*inp.scanner_capex+ai*inp.injection_capex+au*inp.uptake_capex+(u/10)*inp.conventional_upgrade_capex_per_10pct
            opex=inp.conventional_fixed_opex+ads*inp.scanner_opex+ai*inp.injection_opex+au*inp.uptake_opex+max(0,b-inp.current_batches)*inp.conventional_extra_batch_opex
            r=make_result(Architecture.CONVENTIONAL,inp,caps,u,b,ts,ads,ti,ai,tu,au,0,0,0,ret,inp.target_patients*inp.operating_days*inp.conventional_manual_min/60,capex,opex)
            cands.append(r)
            if r.installed_capacity>=inp.target_patients: stats.physical+=1; batches_ok.add(b)
            if capex<=inp.capex_budget:stats.budget+=1
            if r.annual_ncf>0:stats.positive_cash_flow+=1
            if r.npv>0:stats.positive_npv+=1
    stats.feasible_batch_counts=len(batches_ok); x=best(cands)
    if x:x.feasible_batch_count=len(batches_ok);x.evaluated=stats.generated
    return x,stats,cands

def mrt(inp):
    inp=inp.normalized(); stats=Stats(); cands=[]; batches_ok=set()
    ret=retention(inp.mrt_transport_min,inp.half_life_min)
    ts=required_scanners(inp.target_patients,inp.operating_hours,inp.scan_cycle_min,inp.scanner_availability_pct)
    ads=max(0,ts-inp.current_scanners)
    for b in range(max(1,inp.current_batches),min(inp.max_mrt_batches,max_batches(inp.production_window_hours,inp.batch_cycle_min))+1):
      for u in range(0,inp.max_mrt_upgrade_pct+1,max(1,inp.upgrade_step_pct)):
       dose=inp.doses_per_batch*(1+u/100)*b*ret
       scan=scanner_capacity(ts,inp.operating_hours,inp.scan_cycle_min,inp.scanner_availability_pct)
       for er in range(inp.max_existing_mrt_rooms+1):
        for nr in range(inp.max_new_mrt_rooms+1):
         distributed=(er+nr)*inp.patients_per_mrt_room
         for ai in range(inp.max_additional_mrt_injection_rooms+1):
          for au in range(inp.max_additional_mrt_uptake_rooms+1):
           stats.generated+=1; ti=inp.current_injection_rooms+ai;tu=inp.current_uptake_rooms+au
           caps={"Dose":dose,"Scanner":scan,"Injection":room_capacity(ti,inp.operating_hours,inp.injection_min)+distributed,
                 "Uptake":room_capacity(tu,inp.operating_hours,inp.uptake_min)+distributed}
           endpoints=1+ti+(tu if inp.include_uptake_endpoints else 0)+er+nr+inp.other_mrt_endpoints+(1 if inp.include_return_endpoint else 0)
           capex=ads*inp.scanner_capex+ai*inp.injection_capex+au*inp.uptake_capex+(u/10)*inp.mrt_upgrade_capex_per_10pct+inp.mrt_core_capex+endpoints*inp.endpoint_capex+er*inp.existing_mrt_room_retrofit_capex+nr*inp.new_mrt_room_capex
           opex=inp.mrt_fixed_opex+inp.mrt_maintenance+ads*inp.scanner_opex+ai*inp.injection_opex+au*inp.uptake_opex+endpoints*inp.endpoint_opex+nr*inp.new_mrt_room_opex+max(0,b-inp.current_batches)*inp.mrt_extra_batch_opex
           r=make_result(Architecture.MRT,inp,caps,u,b,ts,ads,ti,ai,tu,au,er,nr,endpoints,ret,inp.target_patients*inp.operating_days*inp.mrt_manual_min/60,capex,opex)
           cands.append(r)
           if r.installed_capacity>=inp.target_patients:stats.physical+=1;batches_ok.add(b)
           if capex<=inp.capex_budget:stats.budget+=1
           if r.annual_ncf>0:stats.positive_cash_flow+=1
           if r.npv>0:stats.positive_npv+=1
    stats.feasible_batch_counts=len(batches_ok);x=best(cands)
    if x:x.feasible_batch_count=len(batches_ok);x.evaluated=stats.generated
    return x,stats,cands

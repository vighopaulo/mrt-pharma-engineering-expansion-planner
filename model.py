from __future__ import annotations
import math
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Tuple

@dataclass(frozen=True)
class Inputs:
    project_mode:str
    current_patients_day:float; target_patients_day:float
    current_scanners:int; current_injection_rooms:int; current_uptake_rooms:int
    current_batches_day:int; current_usable_doses_per_batch:float
    operating_hours_day:float; production_window_hours_day:float
    scanner_cycle_min:float; scanner_availability_pct:float
    injection_service_min:float; uptake_occupancy_min:float
    production_release_cycle_min:float
    conventional_transport_min:float; mrt_transport_min:float; isotope_half_life_min:float
    max_conventional_batches_day:int; max_mrt_batches_day:int
    max_conventional_upgrade_pct:int; max_mrt_upgrade_pct:int; production_search_step_pct:int
    max_existing_mrt_inpatient_rooms:int; max_new_mrt_inpatient_rooms:int
    patients_per_mrt_inpatient_room_day:float
    max_additional_mrt_injection_rooms:int; max_additional_mrt_uptake_rooms:int
    include_return_disposal_endpoint:bool; other_mrt_support_endpoints:int
    scanner_capex:float; injection_room_capex:float; uptake_room_capex:float
    conventional_upgrade_capex_per_10pct:float; mrt_upgrade_capex_per_10pct:float
    mrt_core_capex:float; mrt_endpoint_capex:float
    existing_mrt_room_retrofit_capex:float; new_mrt_inpatient_room_capex:float
    maximum_capex_budget:float
    conventional_fixed_incremental_opex:float; mrt_fixed_incremental_opex:float
    annual_opex_per_scanner:float; annual_opex_per_injection_room:float; annual_opex_per_uptake_room:float
    annual_mrt_maintenance:float; annual_opex_per_mrt_endpoint:float; annual_opex_per_new_mrt_inpatient_room:float
    annual_cost_per_additional_conventional_daily_batch:float
    annual_cost_per_additional_mrt_daily_batch:float
    conventional_manual_minutes_per_delivery:float; mrt_residual_manual_minutes_per_delivery:float
    contribution_per_incremental_patient:float
    operating_days_year:int; analysis_years:int; discount_rate_pct:float

@dataclass
class ArchitectureResult:
    architecture:str; feasible:bool; reason:str; binding_constraint:str
    patients_served_day:float; installed_capacity_day:float; reserve_capacity_day:float
    dose_capacity_day:float; scanner_capacity_day:float; injection_capacity_day:float; uptake_capacity_day:float
    production_increase_pct:float; batches_day:int
    total_scanners:int; additional_scanners:int
    total_injection_rooms:int; additional_injection_rooms:int
    total_uptake_rooms:int; additional_uptake_rooms:int
    existing_mrt_inpatient_rooms:int; new_mrt_inpatient_rooms:int; mrt_endpoints:int
    retained_activity_pct:float; activity_loss_pct:float; annual_logistics_hours:float
    capex:float; annual_opex:float; annual_incremental_revenue:float; annual_net_cash_flow:float
    npv:float; roi_pct:float; payback_years:float
    feasible_batch_count:int=0; configurations_evaluated:int=0

@dataclass
class SearchStats:
    generated:int; physically_feasible:int; within_budget:int
    positive_cash_flow:int; positive_npv:int; feasible_batch_counts:int

def retained_fraction(t,hl): return 2**(-t/hl)
def scanner_capacity(n,h,cycle,avail): return 0.0 if n<=0 else n*h*60/cycle*avail/100
def room_capacity(n,h,service): return 0.0 if n<=0 else n*h*60/service
def min_scanners(inp): return math.ceil(inp.target_patients_day/scanner_capacity(1,inp.operating_hours_day,inp.scanner_cycle_min,inp.scanner_availability_pct))
def avg_rooms(q,h,t): return math.ceil(q*t/(h*60))
def cohort_rooms(q,b,h,t): return math.ceil(math.ceil(q/max(1,b))*t/(h*60/max(1,b)))
def required_rooms(q,b,h,t): return max(avg_rooms(q,h,t),cohort_rooms(q,b,h,t))
def bind(caps): return min(caps,key=caps.get)

def financials(capex,opex,inp):
    inc=max(0,inp.target_patients_day-inp.current_patients_day)
    rev=inc*inp.operating_days_year*inp.contribution_per_incremental_patient
    net=rev-opex; r=inp.discount_rate_pct/100
    npv=-capex+sum(net/((1+r)**y) for y in range(1,inp.analysis_years+1))
    roi=(((net*inp.analysis_years)-capex)/capex*100) if capex>0 else 0
    pay=capex/net if net>0 else math.inf
    return rev,net,npv,roi,pay

def validate_inputs(inp):
    w=[]
    if inp.target_patients_day<=0:w.append('Target patients/day must be positive.')
    if inp.project_mode=='Expansion' and inp.target_patients_day<inp.current_patients_day:w.append('Target is below current patients/day.')
    tm=math.floor(inp.production_window_hours_day*60/inp.production_release_cycle_min)
    if tm<1:w.append('Production cycle exceeds daily production window.')
    if inp.max_conventional_batches_day<max(1,inp.current_batches_day):w.append('Maximum conventional batches/day is below current batches/day.')
    if inp.max_mrt_batches_day<max(1,inp.current_batches_day):w.append('Maximum MRT batches/day is below current batches/day.')
    if inp.mrt_core_capex>inp.maximum_capex_budget:w.append('MRT core CapEx alone exceeds budget.')
    return w

def build_result(arch,inp,caps,upgrade,batches,ts,ads,ti,ai,tu,au,er,nr,endpoints,ret,lh,capex,opex):
    installed=min(caps.values()); physical=installed+1e-9>=inp.target_patients_day
    rev,net,npv,roi,pay=financials(capex,opex,inp)
    feasible=physical and capex<=inp.maximum_capex_budget and net>0 and npv>0
    if not physical: reason=f'{bind(caps)} capacity is below target.'
    elif capex>inp.maximum_capex_budget: reason='CapEx exceeds budget.'
    elif net<=0: reason='Annual net cash flow is non-positive.'
    elif npv<=0: reason='NPV is non-positive.'
    else: reason='Feasible.'
    return ArchitectureResult(
        arch,feasible,reason,bind(caps),min(installed,inp.target_patients_day),installed,max(0,installed-inp.target_patients_day),
        caps['Dose'],caps['Scanner'],caps['Injection'],caps['Uptake'],upgrade,batches,ts,ads,ti,ai,tu,au,er,nr,endpoints,
        ret*100,(1-ret)*100,lh,capex,opex,rev,net,npv,roi,pay)

def optimize_conventional(inp):
    ret=retained_fraction(inp.conventional_transport_min,inp.isotope_half_life_min)
    bmin=max(1,inp.current_batches_day); bmax=min(inp.max_conventional_batches_day,max(1,math.floor(inp.production_window_hours_day*60/inp.production_release_cycle_min)))
    ts=min_scanners(inp); ads=max(0,ts-inp.current_scanners)
    gen=phys=bud=cash=npvpos=0; bs=set(); cand=[]; near=None; bestgap=1e99
    for b in range(bmin,bmax+1):
        ti=max(inp.current_injection_rooms,required_rooms(inp.target_patients_day,b,inp.operating_hours_day,inp.injection_service_min))
        tu=max(inp.current_uptake_rooms,required_rooms(inp.target_patients_day,b,inp.operating_hours_day,inp.uptake_occupancy_min))
        ai=max(0,ti-inp.current_injection_rooms); au=max(0,tu-inp.current_uptake_rooms)
        for u in range(0,inp.max_conventional_upgrade_pct+1,max(1,inp.production_search_step_pct)):
            gen+=1
            caps={'Dose':inp.current_usable_doses_per_batch*(1+u/100)*b*ret,
                  'Scanner':scanner_capacity(ts,inp.operating_hours_day,inp.scanner_cycle_min,inp.scanner_availability_pct),
                  'Injection':room_capacity(ti,inp.operating_hours_day,inp.injection_service_min),
                  'Uptake':room_capacity(tu,inp.operating_hours_day,inp.uptake_occupancy_min)}
            capex=ads*inp.scanner_capex+ai*inp.injection_room_capex+au*inp.uptake_room_capex+(u/10)*inp.conventional_upgrade_capex_per_10pct
            opex=inp.conventional_fixed_incremental_opex+ads*inp.annual_opex_per_scanner+ai*inp.annual_opex_per_injection_room+au*inp.annual_opex_per_uptake_room+max(0,b-inp.current_batches_day)*inp.annual_cost_per_additional_conventional_daily_batch
            lh=inp.target_patients_day*inp.operating_days_year*inp.conventional_manual_minutes_per_delivery/60
            r=build_result('Conventional Expansion',inp,caps,u,b,ts,ads,ti,ai,tu,au,0,0,0,ret,lh,capex,opex); r.configurations_evaluated=gen
            if min(caps.values())>=inp.target_patients_day: phys+=1; bs.add(b)
            if capex<=inp.maximum_capex_budget:bud+=1
            if r.annual_net_cash_flow>0:cash+=1
            if r.npv>0:npvpos+=1
            if r.feasible:cand.append(r)
            gap=max(0,inp.target_patients_day-r.installed_capacity_day)
            if gap<bestgap or (gap==bestgap and (near is None or r.capex<near.capex)):bestgap=gap;near=r
    if cand:
        cand.sort(key=lambda x:(-x.npv,x.capex,-x.roi_pct,x.payback_years)); best=cand[0];best.feasible_batch_count=len(bs)
    else: best=near
    return best,SearchStats(gen,phys,bud,cash,npvpos,len(bs)),cand[:200],near

def optimize_mrt(inp):
    ret=retained_fraction(inp.mrt_transport_min,inp.isotope_half_life_min)
    bmin=max(1,inp.current_batches_day); bmax=min(inp.max_mrt_batches_day,max(1,math.floor(inp.production_window_hours_day*60/inp.production_release_cycle_min)))
    ts=min_scanners(inp); ads=max(0,ts-inp.current_scanners)
    gen=phys=bud=cash=npvpos=0; bs=set(); cand=[]; near=None; bestgap=1e99
    for b in range(bmin,bmax+1):
      for u in range(0,inp.max_mrt_upgrade_pct+1,max(1,inp.production_search_step_pct)):
       dose=inp.current_usable_doses_per_batch*(1+u/100)*b*ret
       sc= scanner_capacity(ts,inp.operating_hours_day,inp.scanner_cycle_min,inp.scanner_availability_pct)
       for er in range(inp.max_existing_mrt_inpatient_rooms+1):
        for nr in range(inp.max_new_mrt_inpatient_rooms+1):
         dist=(er+nr)*inp.patients_per_mrt_inpatient_room_day
         for ai in range(inp.max_additional_mrt_injection_rooms+1):
          for au in range(inp.max_additional_mrt_uptake_rooms+1):
           gen+=1
           ti=inp.current_injection_rooms+ai;tu=inp.current_uptake_rooms+au
           caps={'Dose':dose,'Scanner':sc,
                 'Injection':room_capacity(ti,inp.operating_hours_day,inp.injection_service_min)+dist,
                 'Uptake':room_capacity(tu,inp.operating_hours_day,inp.uptake_occupancy_min)+dist}
           endpoints=1+ti+tu+ts+er+nr+inp.other_mrt_support_endpoints+(1 if inp.include_return_disposal_endpoint else 0)
           capex=ads*inp.scanner_capex+ai*inp.injection_room_capex+au*inp.uptake_room_capex+(u/10)*inp.mrt_upgrade_capex_per_10pct+inp.mrt_core_capex+endpoints*inp.mrt_endpoint_capex+er*inp.existing_mrt_room_retrofit_capex+nr*inp.new_mrt_inpatient_room_capex
           opex=inp.mrt_fixed_incremental_opex+inp.annual_mrt_maintenance+ads*inp.annual_opex_per_scanner+ai*inp.annual_opex_per_injection_room+au*inp.annual_opex_per_uptake_room+endpoints*inp.annual_opex_per_mrt_endpoint+nr*inp.annual_opex_per_new_mrt_inpatient_room+max(0,b-inp.current_batches_day)*inp.annual_cost_per_additional_mrt_daily_batch
           lh=inp.target_patients_day*inp.operating_days_year*inp.mrt_residual_manual_minutes_per_delivery/60
           r=build_result('MRT Pharma Hybrid',inp,caps,u,b,ts,ads,ti,ai,tu,au,er,nr,endpoints,ret,lh,capex,opex);r.configurations_evaluated=gen
           if min(caps.values())>=inp.target_patients_day:phys+=1;bs.add(b)
           if capex<=inp.maximum_capex_budget:bud+=1
           if r.annual_net_cash_flow>0:cash+=1
           if r.npv>0:npvpos+=1
           if r.feasible:cand.append(r)
           gap=max(0,inp.target_patients_day-r.installed_capacity_day)
           if gap<bestgap or (gap==bestgap and (near is None or r.capex<near.capex)):bestgap=gap;near=r
    if cand:
        cand.sort(key=lambda x:(-x.npv,x.capex,-x.roi_pct,x.payback_years));best=cand[0];best.feasible_batch_count=len(bs)
    else:best=near
    return best,SearchStats(gen,phys,bud,cash,npvpos,len(bs)),cand[:200],near

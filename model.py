from __future__ import annotations
import math
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple

@dataclass(frozen=True)
class Inputs:
    current_patients_day: float
    target_patients_day: float
    current_scanners: int
    current_injection_rooms: int
    current_uptake_rooms: int
    operating_hours_day: float
    scanner_cycle_min: float
    scanner_availability_pct: float
    injection_service_min: float
    uptake_occupancy_min: float
    production_release_cycle_min: float
    current_usable_doses_per_batch: float
    conventional_transport_min: float
    mrt_transport_min: float
    isotope_half_life_min: float
    max_mrt_batches_day: int
    mrt_upgrade_step_pct: int
    include_return_disposal_endpoint: bool
    scanner_capex: float
    injection_room_capex: float
    uptake_room_capex: float
    conventional_upgrade_capex_per_10pct: float
    mrt_upgrade_capex_per_10pct: float
    mrt_core_capex: float
    mrt_endpoint_capex: float
    conventional_base_opex: float
    mrt_base_opex: float
    annual_opex_per_scanner: float
    annual_opex_per_injection_room: float
    annual_opex_per_uptake_room: float
    annual_mrt_maintenance: float
    annual_opex_per_mrt_endpoint: float
    annual_cost_per_additional_daily_batch: float
    contribution_per_incremental_patient: float
    operating_days_year: int
    analysis_years: int
    discount_rate_pct: float
    maximum_capex_budget: float

@dataclass
class ArchitectureResult:
    architecture: str
    feasible: bool
    reason: str
    patients_served_day: float
    installed_capacity_day: float
    reserve_capacity_day: float
    production_increase_pct: float
    batches_day: int
    total_scanners: int
    additional_scanners: int
    total_injection_rooms: int
    additional_injection_rooms: int
    total_uptake_rooms: int
    additional_uptake_rooms: int
    mrt_endpoints: int
    retained_activity_pct: float
    capex: float
    annual_opex: float
    annual_incremental_revenue: float
    annual_net_cash_flow: float
    npv: float
    roi_pct: float
    payback_years: float

@dataclass
class ModelResults:
    conventional: ArchitectureResult
    mrt: ArchitectureResult
    winner: Optional[str]
    validations: List[str]
    mrt_configurations_evaluated: int
    mrt_feasible_configurations: int
    mrt_positive_npv_configurations: int
    ranked_mrt: List[ArchitectureResult]

def retained_fraction(minutes: float, half_life_minutes: float) -> float:
    return 2 ** (-minutes / half_life_minutes)

def annual_financials(capex, annual_opex, current_patients, served_patients, operating_days, contribution, years, discount_rate_pct):
    incremental=max(0.0,served_patients-current_patients)
    revenue=incremental*operating_days*contribution
    net=revenue-annual_opex
    r=discount_rate_pct/100.0
    npv=-capex+sum(net/((1+r)**y) for y in range(1,years+1))
    roi=(((net*years)-capex)/capex*100.0) if capex>0 else 0.0
    payback=capex/net if net>0 else math.inf
    return revenue,net,npv,roi,payback

def scanner_requirement(inp: Inputs):
    per=inp.operating_hours_day*60/inp.scanner_cycle_min*inp.scanner_availability_pct/100
    total=math.ceil(inp.target_patients_day/per)
    return total,max(0,total-inp.current_scanners),total*per

def service_time_rooms(patients, hours, service_min):
    return max(1,math.ceil(patients*service_min/(hours*60)))

def cohort_rooms(target,batches,hours,service_min):
    cohort=math.ceil(target/batches)
    interval=hours*60/batches
    return max(1,math.ceil(cohort*service_min/interval))

def make_result(arch,feasible,reason,capacity,upgrade,batches,total_scanners,add_scanners,total_inj,add_inj,total_upt,add_upt,endpoints,retention,capex,opex,inp):
    served=min(capacity,inp.target_patients_day) if feasible else 0.0
    reserve=max(0.0,capacity-inp.target_patients_day) if feasible else 0.0
    revenue,net,npv,roi,payback=annual_financials(capex,opex,inp.current_patients_day,served,inp.operating_days_year,inp.contribution_per_incremental_patient,inp.analysis_years,inp.discount_rate_pct)
    if not feasible:
        revenue=net=npv=roi=0.0; payback=math.inf
    return ArchitectureResult(arch,feasible,reason,served,capacity,reserve,upgrade,batches,total_scanners,add_scanners,total_inj,add_inj,total_upt,add_upt,endpoints,retention*100,capex,opex,revenue,net,npv,roi,payback)

def validate_inputs(inp: Inputs):
    warnings=[]
    if inp.target_patients_day<inp.current_patients_day: warnings.append('Target patients/day is below current patients/day.')
    if inp.max_mrt_batches_day<=1: warnings.append('MRT multi-batch optimization is disabled because maximum batches/day is 1.')
    if inp.mrt_core_capex>inp.maximum_capex_budget: warnings.append('MRT core CapEx alone exceeds the selected budget.')
    return warnings

def conventional_benchmark(inp: Inputs):
    scale=inp.target_patients_day/inp.current_patients_day
    linear_upgrade=max(0.0,(scale-1)*100)
    ret=retained_fraction(inp.conventional_transport_min,inp.isotope_half_life_min)
    dose_required_upgrade=max(0.0,(inp.target_patients_day/(inp.current_usable_doses_per_batch*ret)-1)*100)
    upgrade=max(linear_upgrade,dose_required_upgrade)
    ts,ads,scan_cap=scanner_requirement(inp)
    prop_inj=math.ceil(inp.current_injection_rooms*scale)
    prop_upt=math.ceil(inp.current_uptake_rooms*scale)
    svc_inj=service_time_rooms(inp.target_patients_day,inp.operating_hours_day,inp.injection_service_min)
    svc_upt=service_time_rooms(inp.target_patients_day,inp.operating_hours_day,inp.uptake_occupancy_min)
    ti=max(prop_inj,svc_inj); tu=max(prop_upt,svc_upt)
    ai=max(0,ti-inp.current_injection_rooms); au=max(0,tu-inp.current_uptake_rooms)
    dose_cap=inp.current_usable_doses_per_batch*(1+upgrade/100)*ret
    inj_cap=ti*inp.operating_hours_day*60/inp.injection_service_min
    upt_cap=tu*inp.operating_hours_day*60/inp.uptake_occupancy_min
    cap=min(dose_cap,scan_cap,inj_cap,upt_cap)
    capex=ads*inp.scanner_capex+ai*inp.injection_room_capex+au*inp.uptake_room_capex+(upgrade/10)*inp.conventional_upgrade_capex_per_10pct
    opex=inp.conventional_base_opex+ads*inp.annual_opex_per_scanner+ai*inp.annual_opex_per_injection_room+au*inp.annual_opex_per_uptake_room
    feasible=cap>=inp.target_patients_day and capex<=inp.maximum_capex_budget
    reason='Feasible.' if feasible else ('Installed capacity below target.' if cap<inp.target_patients_day else 'CapEx exceeds budget.')
    r=make_result('Conventional Expansion',feasible,reason,cap,upgrade,1,ts,ads,ti,ai,tu,au,0,ret,capex,opex,inp)
    if r.feasible and r.annual_net_cash_flow<=0: r.feasible=False; r.reason='Annual net cash flow is non-positive.'
    if r.feasible and r.npv<=0: r.feasible=False; r.reason='NPV is non-positive.'
    return r

def optimize_mrt(inp: Inputs, conventional: ArchitectureResult):
    ts,ads,scan_cap=scanner_requirement(inp)
    ret=retained_fraction(inp.mrt_transport_min,inp.isotope_half_life_min)
    step=max(1,int(inp.mrt_upgrade_step_pct))
    upgrades=list(range(0,max(0,math.ceil(conventional.production_increase_pct)),step)) or [0]
    max_batches=min(inp.max_mrt_batches_day,max(1,math.floor(inp.operating_hours_day*60/inp.production_release_cycle_min)))
    evaluated=feasible_count=positive_count=0
    candidates=[]; near=None
    for u in upgrades:
        for b in range(1,max_batches+1):
            evaluated+=1
            ti=cohort_rooms(inp.target_patients_day,b,inp.operating_hours_day,inp.injection_service_min)
            tu=cohort_rooms(inp.target_patients_day,b,inp.operating_hours_day,inp.uptake_occupancy_min)
            ai=max(0,ti-inp.current_injection_rooms); au=max(0,tu-inp.current_uptake_rooms)
            dose_cap=inp.current_usable_doses_per_batch*(1+u/100)*b*ret
            inj_cap=ti*inp.operating_hours_day*60/inp.injection_service_min
            upt_cap=tu*inp.operating_hours_day*60/inp.uptake_occupancy_min
            cap=min(dose_cap,scan_cap,inj_cap,upt_cap)
            endpoints=1+ti+ts+(1 if inp.include_return_disposal_endpoint else 0)
            capex=ads*inp.scanner_capex+ai*inp.injection_room_capex+au*inp.uptake_room_capex+(u/10)*inp.mrt_upgrade_capex_per_10pct+inp.mrt_core_capex+endpoints*inp.mrt_endpoint_capex
            opex=inp.mrt_base_opex+ads*inp.annual_opex_per_scanner+ai*inp.annual_opex_per_injection_room+au*inp.annual_opex_per_uptake_room+inp.annual_mrt_maintenance+endpoints*inp.annual_opex_per_mrt_endpoint+max(0,b-1)*inp.annual_cost_per_additional_daily_batch
            if cap<inp.target_patients_day or capex>inp.maximum_capex_budget:
                reason='Installed capacity below target.' if cap<inp.target_patients_day else 'CapEx exceeds budget.'
                rr=make_result('MRT Pharma Hybrid',False,reason,cap,u,b,ts,ads,ti,ai,tu,au,endpoints,ret,capex,opex,inp)
                gap=max(0,inp.target_patients_day-cap)
                if near is None or gap<near[0]: near=(gap,rr)
                continue
            feasible_count+=1
            rr=make_result('MRT Pharma Hybrid',True,'Feasible.',cap,u,b,ts,ads,ti,ai,tu,au,endpoints,ret,capex,opex,inp)
            if rr.annual_net_cash_flow>0 and rr.npv>0:
                positive_count+=1; candidates.append(rr)
    if candidates:
        candidates.sort(key=lambda r:(-r.npv,r.capex,r.annual_opex))
        return candidates[0],evaluated,feasible_count,positive_count,candidates[:100]
    if near: return near[1],evaluated,feasible_count,positive_count,[]
    return make_result('MRT Pharma Hybrid',False,'No MRT configuration generated.',0,0,0,ts,ads,inp.current_injection_rooms,0,inp.current_uptake_rooms,0,0,ret,0,0,inp),evaluated,feasible_count,positive_count,[]

def run_model(inp: Inputs):
    validations=validate_inputs(inp)
    conventional=conventional_benchmark(inp)
    mrt,e,f,p,ranked=optimize_mrt(inp,conventional)
    feasible=[x for x in (conventional,mrt) if x.feasible and x.npv>0]
    winner=max(feasible,key=lambda r:(r.npv,-r.capex)).architecture if feasible else None
    return ModelResults(conventional,mrt,winner,validations,e,f,p,ranked)

def result_to_dict(result): return asdict(result)

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

class ProjectMode(str, Enum):
    EXPANSION="Expansion"
    GREENFIELD="Greenfield"

class Architecture(str, Enum):
    CONVENTIONAL="Conventional Expansion"
    MRT="MRT Pharma Hybrid"

PRIORITIES=[
"Net Present Value","Lowest Capital Expenditure","Highest ROI","Fastest Payback",
"Lowest Annual OpEx","Highest Activity Retention","Highest Reserve Capacity",
"Greatest Batch Flexibility","Lowest Production Increase",
"Fewest Additional Dedicated Rooms","Lowest Logistics Labor Burden","Highest Resilience"]

@dataclass(frozen=True)
class Inputs:
    project_mode: ProjectMode
    current_patients: float
    target_patients: float
    current_scanners: int
    current_injection_rooms: int
    current_uptake_rooms: int
    current_batches: int
    doses_per_batch: float
    operating_hours: float
    production_window_hours: float
    scan_cycle_min: float
    scanner_availability_pct: float
    injection_min: float
    uptake_min: float
    batch_cycle_min: float
    conventional_transport_min: float
    mrt_transport_min: float
    half_life_min: float
    max_conventional_batches: int
    max_mrt_batches: int
    max_conventional_upgrade_pct: int
    max_mrt_upgrade_pct: int
    upgrade_step_pct: int
    max_existing_mrt_rooms: int
    max_new_mrt_rooms: int
    patients_per_mrt_room: float
    max_additional_mrt_injection_rooms: int
    max_additional_mrt_uptake_rooms: int
    include_uptake_endpoints: bool
    include_return_endpoint: bool
    other_mrt_endpoints: int
    scanner_capex: float
    injection_capex: float
    uptake_capex: float
    conventional_upgrade_capex_per_10pct: float
    mrt_upgrade_capex_per_10pct: float
    mrt_core_capex: float
    endpoint_capex: float
    existing_mrt_room_retrofit_capex: float
    new_mrt_room_capex: float
    capex_budget: float
    conventional_fixed_opex: float
    mrt_fixed_opex: float
    scanner_opex: float
    injection_opex: float
    uptake_opex: float
    mrt_maintenance: float
    endpoint_opex: float
    new_mrt_room_opex: float
    conventional_extra_batch_opex: float
    mrt_extra_batch_opex: float
    conventional_manual_min: float
    mrt_manual_min: float
    contribution_per_patient: float
    operating_days: int
    analysis_years: int
    discount_rate_pct: float
    priority_1: str
    priority_2: str
    priority_3: str

    def normalized(self):
        if self.project_mode is ProjectMode.GREENFIELD:
            d=asdict(self)
            d.update(project_mode=ProjectMode.GREENFIELD,current_patients=0.0,current_scanners=0,
                     current_injection_rooms=0,current_uptake_rooms=0,current_batches=0)
            return Inputs(**d)
        return self

@dataclass
class Result:
    architecture: Architecture
    feasible: bool
    reason: str
    binding_constraint: str
    installed_capacity: float
    served_patients: float
    reserve_capacity: float
    dose_capacity: float
    scanner_capacity: float
    injection_capacity: float
    uptake_capacity: float
    production_increase_pct: float
    batches: int
    total_scanners: int
    additional_scanners: int
    total_injection_rooms: int
    additional_injection_rooms: int
    total_uptake_rooms: int
    additional_uptake_rooms: int
    existing_mrt_rooms: int
    new_mrt_rooms: int
    mrt_endpoints: int
    retained_activity_pct: float
    annual_logistics_hours: float
    resilience_ratio: float
    feasible_batch_count: int
    capex: float
    annual_opex: float
    annual_revenue: float
    annual_ncf: float
    npv: float
    roi_pct: float
    payback_years: float
    evaluated: int=0

@dataclass
class Stats:
    generated:int=0
    physical:int=0
    budget:int=0
    positive_cash_flow:int=0
    positive_npv:int=0
    feasible_batch_counts:int=0

@dataclass
class Decision:
    financial_winner: Optional[Architecture]
    recommendation: Optional[Architecture]
    conventional_score: float
    mrt_score: float
    strength: str
    breakdown:list[dict]=field(default_factory=list)
    sensitivity:list[dict]=field(default_factory=list)

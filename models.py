from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Architecture(str, Enum):
    CONVENTIONAL = "Conventional Expansion"
    MRT = "MRT-enabled Expansion"


@dataclass(frozen=True)
class PlannerAssumptions:
    mrt_infrastructure_capex: float = 6_000_000.0
    cyclotron_purchase_capex: float = 3_000_000.0
    cyclotron_installation_capex: float = 2_000_000.0
    additional_room_capex: float = 25_000.0
    production_expansion_capex_per_10pct: float = 500_000.0
    discount_rate_pct: float = 10.0
    analysis_years: int = 10
    operating_days_per_year: int = 300
    scanner_availability_pct: float = 85.0
    scanner_cycle_min: float = 35.0
    injection_cycle_min: float = 15.0
    uptake_cycle_min: float = 60.0
    operating_hours_per_day: float = 18.0
    mrt_transport_default_min: float = 0.5
    scanner_capex: float = 2_500_000.0
    endpoint_capex: float = 10_000.0
    guideway_segment_capex: float = 1_000_000.0
    scanner_incremental_opex: float = 300_000.0
    room_incremental_opex: float = 80_000.0
    endpoint_incremental_opex: float = 5_000.0
    guideway_incremental_opex: float = 150_000.0
    conventional_extra_batch_opex_per_day: float = 2_500.0
    mrt_extra_batch_opex_per_day: float = 2_000.0
    revenue_per_scan: float = 300.0
    prescribed_activity_mbq_per_patient: float = 370.0
    synthesis_processing_time_min: float = 0.0
    synthesis_yield_fraction: float = 1.0
    cyclotron_eob_capacity_mbq_per_day: float | None = None
    decay_feasibility_min_retained_fraction: float = 0.0
    decay_feasibility_max_compensation_factor: float | None = None
    default_clinical_administration_cohorts_per_day: int = 6
    common_administration_wait_min: float = 71.0
    manual_transport_speed_m_per_s: float = 1.2
    manual_transport_pickup_minutes: float = 0.5
    manual_transport_handoff_minutes: float = 0.5
    manual_transport_elevator_wait_minutes: float = 1.0
    manual_transport_elevator_loading_minutes: float = 0.5
    manual_transport_elevator_speed_m_per_s: float = 1.0
    mrt_horizontal_speed_m_per_s: float = 3.0
    mrt_vertical_speed_m_per_s: float = 1.5
    mrt_transition_time_seconds: float = 8.0
    mrt_station_loading_time_seconds: float = 30.0
    mrt_station_unloading_time_seconds: float = 30.0
    mrt_carrier_capex_per_installed_unit: float = 10_000.0
    mrt_carrier_allocated_electricity_opex_per_operated_unit_year: float = 250.0
    mrt_carrier_maintenance_opex_per_installed_unit_year: float = 500.0
    mrt_guideway_capex_per_m: float = 5_000.0
    mrt_guideway_maintenance_fraction_of_capex_per_year: float = 0.03
    # PROJECT DESIGN CRITERION (not an FDA/regulatory/universal clinical requirement):
    # minimum fraction of administered activity that must remain from RELEASE (not EOB)
    # to actual administration for a room/location to be spatial-retention-feasible.
    minimum_release_to_administration_retention_fraction: float = 0.90
    # Section 53: SPECT/generator economics remain explicitly NOT_CALIBRATED (None)
    # until a legitimate value is supplied -- no invented CapEx/OPEX figures.
    generator_purchase_capex: float | None = None
    generator_installation_capex: float | None = None
    generator_annual_maintenance_opex: float | None = None
    spect_scanner_capex: float | None = None
    spect_scanner_incremental_opex: float | None = None

    def __post_init__(self) -> None:
        if not (0.0 < self.minimum_release_to_administration_retention_fraction <= 1.0):
            raise ValueError("minimum_release_to_administration_retention_fraction must be within (0, 1]")


@dataclass(frozen=True)
class PlannerInputs:
    project_name: str
    current_patients_per_day: float
    target_patients_per_day: float
    maximum_expected_demand_per_day: float
    current_scanners: int
    current_injection_rooms: int
    current_uptake_rooms: int
    has_existing_cyclotron: bool
    current_usable_doses_per_day: float
    current_average_transport_min: float
    mrt_transport_min: float | None
    existing_mrt_connectable_rooms: int
    representative_radionuclide: str | None
    representative_half_life_min: float | None
    conventional_transport_min: float | None = None
    current_cyclotron_eob_capacity_mbq_per_day: float | None = None
    cyclotron_fleet: Any | None = None
    selected_cyclotron_radionuclide: str | None = None

    def incremental_patients_per_day(self) -> float:
        return max(0.0, self.target_patients_per_day - self.current_patients_per_day)


@dataclass
class PlanFinancials:
    annual_revenue: float
    annual_incremental_opex: float
    annual_net_cash_flow: float
    npv: float
    roi_pct: float
    payback_years: float


@dataclass
class ConventionalPlan:
    capacity_increase_pct: float
    required_production_increase_pct: float
    additional_scanners: int
    additional_injection_rooms: int
    additional_uptake_rooms: int
    cyclotron_required: bool
    retained_activity_pct: float
    achieved_capacity_per_day: float
    reserve_capacity_per_day: float
    revenue_generating_throughput_per_day: float
    capex: float
    financials: PlanFinancials
    capex_ledger: list[dict[str, Any]] = field(default_factory=list)
    ledger: dict[str, Any] = field(default_factory=dict)


@dataclass
class MRTPlan:
    production_increase_pct: float
    additional_scanners: int
    new_mrt_rooms: int
    additional_injection_rooms: int
    additional_uptake_rooms: int
    guideway_segments: int
    endpoints: int
    infrastructure_units: int
    retained_activity_pct: float
    achieved_capacity_per_day: float
    reserve_capacity_per_day: float
    revenue_generating_throughput_per_day: float
    capex: float
    financials: PlanFinancials
    capex_ledger: list[dict[str, Any]] = field(default_factory=list)
    ledger: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerReport:
    project_name: str
    inputs: PlannerInputs
    assumptions: PlannerAssumptions
    conventional: ConventionalPlan
    mrt: MRTPlan


@dataclass(frozen=True)
class NetworkProfile:
    study_name: str
    facility_name: str
    baseline_current_patients_per_day: float
    baseline_max_expected_demand_per_day: float
    baseline_scanners: int
    baseline_injection_rooms: int
    baseline_uptake_rooms: int
    baseline_usable_doses_per_day: float
    has_existing_cyclotron: bool
    existing_backbone_installed: bool = False
    initial_guideway_segments: int = 0
    initial_endpoints: int = 0
    initial_connected_rooms: int = 0
    initial_vertical_transitions: int = 0
    initial_building_connections: int = 0


@dataclass(frozen=True)
class DevelopmentPhase:
    phase_name: str
    year: int
    service_group: str
    representative_radionuclide: str
    incremental_target_patients_per_day: float
    maximum_expected_demand_per_day: float
    existing_rooms_to_connect: int
    new_rooms_to_construct: int
    cumulative_guideway_segments_required: int
    cumulative_endpoints_required: int
    cumulative_vertical_transitions_required: int = 0
    cumulative_building_connections_required: int = 0
    existing_rooms_to_renovate: int = 0
    additional_scanners_manual: int = 0
    production_demand_multiplier: float = 1.0
    conventional_new_cyclotron_required: bool = False
    mrt_new_cyclotron_required: bool = False
    can_use_existing_backbone_capacity: bool = True
    new_rooms_require_connection_modification: bool = True
    conventional_existing_rooms_to_renovate: int = 0
    mrt_new_rooms_requiring_connection_modification: int = 0


@dataclass(frozen=True)
class SharedNetworkAssumptions:
    shared_backbone_cost: float = 6_000_000.0
    guideway_segment_capex: float = 1_000_000.0
    endpoint_capex: float = 10_000.0
    vertical_transition_capex: float = 350_000.0
    building_connection_capex: float = 500_000.0
    new_room_construction_capex: float = 25_000.0
    room_renovation_modification_capex: float = 18_000.0
    room_connection_modification_capex: float = 12_500.0
    production_expansion_capex_per_10pct: float = 500_000.0
    cyclotron_purchase_capex: float = 3_000_000.0
    cyclotron_installation_capex: float = 2_000_000.0
    scanner_capex: float = 2_500_000.0
    revenue_per_scan: float = 300.0
    discount_rate_pct: float = 10.0
    analysis_years: int = 10
    operating_days_per_year: int = 300
    operating_hours_per_day: float = 18.0
    scanner_availability_pct: float = 85.0
    scanner_cycle_min: float = 35.0
    injection_cycle_min: float = 15.0
    uptake_cycle_min: float = 60.0
    conventional_transport_min: float = 20.0
    mrt_transport_min: float = 0.5


@dataclass
class SharedNetworkPhaseResult:
    phase_name: str
    year: int
    service_group: str
    conventional_incremental_capex: float
    mrt_incremental_capex: float
    phase_capex_difference: float
    conventional_cumulative_capex: float
    mrt_cumulative_capex: float
    cumulative_capex_difference: float
    conventional_phase_revenue: float
    mrt_phase_revenue: float
    conventional_cumulative_revenue: float
    mrt_cumulative_revenue: float
    conventional_achieved_capacity_per_day: float
    mrt_achieved_capacity_per_day: float
    conventional_retained_activity_pct: float
    mrt_retained_activity_pct: float
    conventional_production_expansion_pct: float
    mrt_production_expansion_pct: float
    capex_difference: float
    cumulative_economic_difference: float
    backbone_charged_this_phase: bool
    cumulative_departments_connected: int
    cumulative_endpoints: int
    cumulative_guideway_segments: int
    cumulative_connected_rooms: int
    cumulative_supported_patients_per_day: float
    network_utilization_pct: float


@dataclass
class SharedNetworkReport:
    network_profile: NetworkProfile
    development_phases: list[DevelopmentPhase]
    assumptions: SharedNetworkAssumptions
    phase_results: list[SharedNetworkPhaseResult]
    phase_ledger: list[dict[str, Any]] = field(default_factory=list)
    network_state: list[dict[str, Any]] = field(default_factory=list)
    cumulative_conventional_capex: float = 0.0
    cumulative_mrt_capex: float = 0.0
    cumulative_conventional_revenue: float = 0.0
    cumulative_mrt_revenue: float = 0.0
    capex_crossover_phase: str | None = None
    capex_crossover_year: int | None = None
    capex_crossover_summary: str = ""
    economic_crossover_phase: str | None = None
    economic_crossover_year: int | None = None
    allocated_backbone_cost_per_service_group: float = 0.0

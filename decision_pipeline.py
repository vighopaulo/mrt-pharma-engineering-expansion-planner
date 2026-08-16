from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from cyclotron_production_windows import CyclotronFleet, CyclotronProductionCapability, build_single_cyclotron_fleet
from infrastructure_capex import InfrastructureCapexInputs, InfrastructureCapexResult, calculate_infrastructure_capex
from infrastructure_opex import InfrastructureOpexInputs, InfrastructureOpexResult, calculate_infrastructure_opex
from lifecycle_economics import LifecycleComparisonResult, LifecycleEconomicResult, compare_lifecycle_results, evaluate_lifecycle_economics
from models import PlannerAssumptions, SharedNetworkAssumptions
from mrt_carrier_fleet import MrtCarrierFleetResult, audit_native_mrt_carrier_integration, resolve_mrt_carrier_fleet
from multi_isotope_decay import PathwayDecaySummary, evaluate_pathway_decay
from patient_radionuclide_demand import (
    FacilityDayPatientDemand,
    RadionuclideBatchDemand,
    partition_facility_day_patient_demand,
)
from production_clinical_schedule import ProductionClinicalScheduleResult, ProductionClinicalScenario, build_production_clinical_schedule
from stochastic_design_day import ActivityDemandModel, DayType, DesignDaySimulationResult, DesignDayDemandScenario, generate_design_day_demand


Pathway = Literal["Conventional", "MRT"]
DeploymentMode = Literal["greenfield", "existing_facility_expansion"]


@dataclass(frozen=True)
class NativePathwayScenario:
    pathway: Pathway
    deployment_mode: DeploymentMode = "greenfield"
    scanners: int = 0
    existing_scanners: int = 0
    injection_resources: int = 0
    existing_injection_resources: int = 0
    uptake_resources: int = 0
    existing_uptake_resources: int = 0
    distribution_concurrency: int = 1
    transport_minutes: float = 0.0
    installed_cyclotron_units: int = 1
    existing_cyclotron_units: int = 0
    installed_radiopharmacy_units: int = 1
    existing_radiopharmacy_units: int = 0
    radiopharmacy_unit_capex: float = 0.0
    conventional_infrastructure_allowance_units: int = 0
    existing_conventional_infrastructure_allowance_units: int = 0
    conventional_infrastructure_allowance_unit_capex: float = 0.0
    installed_mrt_base_infrastructure_units: int = 0
    existing_mrt_base_infrastructure_units: int = 0
    installed_mrt_endpoints: int = 0
    existing_mrt_endpoints: int = 0
    installed_guideway_length_m: float = 0.0
    existing_guideway_length_m: float = 0.0
    guideway_capex_per_m: float = 0.0
    installed_vertical_transitions: int = 0
    existing_vertical_transitions: int = 0
    installed_building_connections: int = 0
    existing_building_connections: int = 0
    installed_mrt_carriers: int | None = None
    operated_cyclotron_units: int = 1
    operated_radiopharmacy_units: int = 1
    operated_mrt_base_units: int = 0
    operated_mrt_endpoints: int = 0
    operated_guideway_length_m: float = 0.0
    operated_vertical_transitions: int = 0
    operated_building_connections: int = 0
    operated_mrt_carriers: int | None = None
    annual_conventional_transport_opex: float = 0.0
    annual_production_variable_cost: float = 0.0
    cyclotron_annual_opex_per_unit: float = 0.0
    conventional_transport_staff_fte: float = 0.0
    conventional_transport_staff_loaded_cost_per_fte: float = 0.0
    mrt_base_annual_opex_per_unit: float = 0.0
    guideway_maintenance_per_m_year: float = 0.0
    vertical_transition_annual_opex_per_unit: float = 0.0
    building_connection_annual_opex_per_unit: float = 0.0
    mrt_support_staff_fte: float = 0.0
    mrt_support_staff_loaded_cost_per_fte: float = 0.0
    annual_scanner_energy_kwh: float = 0.0
    annual_cyclotron_energy_kwh: float = 0.0
    annual_mrt_energy_kwh: float = 0.0
    annual_other_energy_kwh: float = 0.0
    electricity_cost_per_kwh: float = 0.0
    clinical_staff_fte: float = 0.0
    clinical_staff_loaded_cost_per_fte: float = 0.0
    production_staff_fte: float = 0.0
    production_staff_loaded_cost_per_fte: float = 0.0
    annual_consumable_units: float = 0.0
    consumable_cost_per_unit: float = 0.0

    def __post_init__(self) -> None:
        if self.pathway not in {"Conventional", "MRT"}:
            raise ValueError("pathway must be Conventional or MRT")
        if self.deployment_mode not in {"greenfield", "existing_facility_expansion"}:
            raise ValueError("deployment_mode must be greenfield or existing_facility_expansion")
        if self.scanners <= 0:
            raise ValueError("scanners must be at least 1")
        if self.injection_resources <= 0:
            raise ValueError("injection_resources must be at least 1")
        if self.uptake_resources <= 0:
            raise ValueError("uptake_resources must be at least 1")
        if self.distribution_concurrency <= 0:
            raise ValueError("distribution_concurrency must be at least 1")
        if self.transport_minutes < 0.0:
            raise ValueError("transport_minutes must be non-negative")
        if self.existing_scanners < 0:
            raise ValueError("existing_scanners must be non-negative")
        if self.existing_scanners > self.scanners:
            raise ValueError("existing_scanners cannot exceed scanners")
        if self.existing_injection_resources < 0:
            raise ValueError("existing_injection_resources must be non-negative")
        if self.existing_injection_resources > self.injection_resources:
            raise ValueError("existing_injection_resources cannot exceed injection_resources")
        if self.existing_uptake_resources < 0:
            raise ValueError("existing_uptake_resources must be non-negative")
        if self.existing_uptake_resources > self.uptake_resources:
            raise ValueError("existing_uptake_resources cannot exceed uptake_resources")
        if self.installed_cyclotron_units < 0:
            raise ValueError("installed_cyclotron_units must be non-negative")
        if self.existing_cyclotron_units < 0:
            raise ValueError("existing_cyclotron_units must be non-negative")
        if self.existing_cyclotron_units > self.installed_cyclotron_units:
            raise ValueError("existing_cyclotron_units cannot exceed installed_cyclotron_units")
        if self.installed_radiopharmacy_units < 0:
            raise ValueError("installed_radiopharmacy_units must be non-negative")
        if self.existing_radiopharmacy_units < 0:
            raise ValueError("existing_radiopharmacy_units must be non-negative")
        if self.existing_radiopharmacy_units > self.installed_radiopharmacy_units:
            raise ValueError("existing_radiopharmacy_units cannot exceed installed_radiopharmacy_units")
        if self.existing_conventional_infrastructure_allowance_units < 0:
            raise ValueError("existing_conventional_infrastructure_allowance_units must be non-negative")
        if self.existing_conventional_infrastructure_allowance_units > self.conventional_infrastructure_allowance_units:
            raise ValueError("existing_conventional_infrastructure_allowance_units cannot exceed conventional_infrastructure_allowance_units")
        if self.installed_mrt_base_infrastructure_units < 0:
            raise ValueError("installed_mrt_base_infrastructure_units must be non-negative")
        if self.existing_mrt_base_infrastructure_units < 0:
            raise ValueError("existing_mrt_base_infrastructure_units must be non-negative")
        if self.existing_mrt_base_infrastructure_units > self.installed_mrt_base_infrastructure_units:
            raise ValueError("existing_mrt_base_infrastructure_units cannot exceed installed_mrt_base_infrastructure_units")
        if self.installed_mrt_endpoints < 0:
            raise ValueError("installed_mrt_endpoints must be non-negative")
        if self.existing_mrt_endpoints < 0:
            raise ValueError("existing_mrt_endpoints must be non-negative")
        if self.existing_mrt_endpoints > self.installed_mrt_endpoints:
            raise ValueError("existing_mrt_endpoints cannot exceed installed_mrt_endpoints")
        if self.installed_guideway_length_m < 0.0:
            raise ValueError("installed_guideway_length_m must be non-negative")
        if self.existing_guideway_length_m < 0.0:
            raise ValueError("existing_guideway_length_m must be non-negative")
        if self.existing_guideway_length_m > self.installed_guideway_length_m:
            raise ValueError("existing_guideway_length_m cannot exceed installed_guideway_length_m")
        if self.installed_vertical_transitions < 0:
            raise ValueError("installed_vertical_transitions must be non-negative")
        if self.existing_vertical_transitions < 0:
            raise ValueError("existing_vertical_transitions must be non-negative")
        if self.existing_vertical_transitions > self.installed_vertical_transitions:
            raise ValueError("existing_vertical_transitions cannot exceed installed_vertical_transitions")
        if self.installed_building_connections < 0:
            raise ValueError("installed_building_connections must be non-negative")
        if self.existing_building_connections < 0:
            raise ValueError("existing_building_connections must be non-negative")
        if self.existing_building_connections > self.installed_building_connections:
            raise ValueError("existing_building_connections cannot exceed installed_building_connections")
        if self.installed_mrt_carriers is not None and self.installed_mrt_carriers < 0:
            raise ValueError("installed_mrt_carriers must be non-negative")
        if self.operated_cyclotron_units < 0:
            raise ValueError("operated_cyclotron_units must be non-negative")
        if self.operated_radiopharmacy_units < 0:
            raise ValueError("operated_radiopharmacy_units must be non-negative")
        if self.operated_mrt_base_units < 0:
            raise ValueError("operated_mrt_base_units must be non-negative")
        if self.operated_mrt_endpoints < 0:
            raise ValueError("operated_mrt_endpoints must be non-negative")
        if self.operated_guideway_length_m < 0.0:
            raise ValueError("operated_guideway_length_m must be non-negative")
        if self.operated_vertical_transitions < 0:
            raise ValueError("operated_vertical_transitions must be non-negative")
        if self.operated_building_connections < 0:
            raise ValueError("operated_building_connections must be non-negative")
        if self.operated_mrt_carriers is not None and self.operated_mrt_carriers < 0:
            raise ValueError("operated_mrt_carriers must be non-negative")
        if self.annual_production_variable_cost < 0.0:
            raise ValueError("annual_production_variable_cost must be non-negative")
        if self.cyclotron_annual_opex_per_unit < 0.0:
            raise ValueError("cyclotron_annual_opex_per_unit must be non-negative")

        if self.pathway == "MRT":
            carrier_fleet = resolve_mrt_carrier_fleet(
                distribution_concurrency=self.distribution_concurrency,
                installed_carriers=self.installed_mrt_carriers,
                operated_carriers=self.operated_mrt_carriers,
            )
            object.__setattr__(self, "installed_mrt_carriers", carrier_fleet.installed_carriers)
            object.__setattr__(self, "operated_mrt_carriers", carrier_fleet.operated_carriers)
        else:
            object.__setattr__(self, "installed_mrt_carriers", 0 if self.installed_mrt_carriers is None else int(self.installed_mrt_carriers))
            object.__setattr__(self, "operated_mrt_carriers", 0 if self.operated_mrt_carriers is None else int(self.operated_mrt_carriers))


@dataclass(frozen=True)
class NativeDecisionPipelineScenario:
    project_name: str
    target_patients_per_day: int
    radionuclide_mix: Mapping[str, float]
    activity_distribution_by_radionuclide: Mapping[str, ActivityDemandModel]
    cyclotron_capability: CyclotronProductionCapability
    conventional: NativePathwayScenario
    mrt: NativePathwayScenario
    planner_assumptions: PlannerAssumptions = field(default_factory=PlannerAssumptions)
    shared_network_assumptions: SharedNetworkAssumptions = field(default_factory=SharedNetworkAssumptions)
    day_type: DayType = "typical"
    peak_patient_multiplier: float = 1.0
    peak_activity_multiplier: float = 1.0
    seed: int = 0
    cyclotron_fleet: CyclotronFleet | None = None
    operating_day_minutes: float = 1080.0
    batch_target_patients_per_batch: int = 20
    lifecycle_throughput_mode: Literal["actual_completed"] = "actual_completed"

    def __post_init__(self) -> None:
        if not isinstance(self.project_name, str) or not self.project_name.strip():
            raise ValueError("project_name must be a non-empty string")
        if int(self.target_patients_per_day) <= 0:
            raise ValueError("target_patients_per_day must be greater than zero")
        if not self.radionuclide_mix:
            raise ValueError("radionuclide_mix must not be empty")
        if not self.activity_distribution_by_radionuclide:
            raise ValueError("activity_distribution_by_radionuclide must not be empty")
        if self.day_type not in {"typical", "peak"}:
            raise ValueError("day_type must be 'typical' or 'peak'")
        if float(self.peak_patient_multiplier) <= 0.0:
            raise ValueError("peak_patient_multiplier must be greater than zero")
        if float(self.peak_activity_multiplier) <= 0.0:
            raise ValueError("peak_activity_multiplier must be greater than zero")
        if self.day_type == "peak" and self.peak_patient_multiplier == 1.0 and self.peak_activity_multiplier == 1.0:
            raise ValueError("peak day requires an explicit peak multiplier greater than 1.0")
        if self.operating_day_minutes <= 0.0:
            raise ValueError("operating_day_minutes must be positive")
        if self.batch_target_patients_per_batch <= 0:
            raise ValueError("batch_target_patients_per_batch must be at least 1")
        if self.lifecycle_throughput_mode != "actual_completed":
            raise ValueError("lifecycle_throughput_mode must be actual_completed in this build")
        if self.conventional.pathway != "Conventional":
            raise ValueError("conventional pathway config must use Conventional")
        if self.mrt.pathway != "MRT":
            raise ValueError("mrt pathway config must use MRT")

        object.__setattr__(self, "target_patients_per_day", int(self.target_patients_per_day))
        object.__setattr__(self, "seed", int(self.seed))


@dataclass(frozen=True)
class NativeBottleneckSummary:
    resource: str
    utilization_pct: float
    near_binding_resources: tuple[str, ...]
    utilization_by_resource: Mapping[str, float]


@dataclass(frozen=True)
class NativeDemandResult:
    simulation: DesignDaySimulationResult
    requested_batch_count_by_radionuclide: Mapping[str, int]
    batch_demands: tuple[RadionuclideBatchDemand, ...]
    patient_ids_by_radionuclide: Mapping[str, tuple[str, ...]]
    fleet_supported_radionuclides: tuple[str, ...]
    trace_id: str
    batch_policy_description: str


@dataclass(frozen=True)
class NativeOperationalResult:
    pathway: Pathway
    pathway_config: NativePathwayScenario
    demand_result: NativeDemandResult
    production_clinical_result: ProductionClinicalScheduleResult
    scheduled_patients: int
    schedule_completed_patients: int
    decay_feasible_scheduled_patients: int
    decay_feasible_completed_patients: int
    production_activity_feasible_scheduled_patients: int
    production_activity_feasible_completed_patients: int
    production_activity_infeasible_patients: int
    decay_infeasible_patients: int
    effective_completion_percentage: float
    patients_considered: int
    patients_completed: int
    patients_incomplete: int
    completion_percentage: float
    production_elapsed_minutes: float
    final_scan_completion_time_minutes: float
    scanner_utilization_pct: float
    injection_utilization_pct: float
    uptake_utilization_pct: float
    distribution_utilization_pct: float
    bottleneck: NativeBottleneckSummary
    mrt_carrier_fleet: MrtCarrierFleetResult | None
    decay_summary: PathwayDecaySummary
    activity_capacity_warnings: tuple[str, ...]
    trace_id: str


@dataclass(frozen=True)
class NativePathwayResult:
    pathway: Pathway
    operational_result: NativeOperationalResult
    capex_result: InfrastructureCapexResult
    opex_result: InfrastructureOpexResult
    lifecycle_result: LifecycleEconomicResult
    actual_lifecycle_throughput_per_day: float
    annual_completed_scans: float
    annual_revenue: float
    annual_opex: float
    decay_summary: PathwayDecaySummary
    trace_id: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NativeIntegrationAudit:
    demand_to_patients: str
    patients_to_isotope_batching: str
    batches_to_production: str
    production_to_clinical_schedule: str
    resource_quantities_to_capex: str
    resource_quantities_to_opex: str
    actual_clinical_completion_to_lifecycle_throughput: str
    capex_to_lifecycle: str
    opex_to_lifecycle: str
    lifecycle_to_conventional_mrt_comparison: str
    missing_capabilities: tuple[str, ...]


@dataclass(frozen=True)
class NativePipelineProvenance:
    request: NativeDecisionPipelineScenario
    scenario_trace_id: str
    demand_trace_id: str
    fleet_id: str
    fleet_asset_ids: tuple[str, ...]
    fleet_supported_radionuclides: tuple[str, ...]
    conventional_trace_id: str
    mrt_trace_id: str
    comparison_trace_id: str
    batch_policy_description: str
    source_modules: tuple[str, ...] = (
        "stochastic_design_day",
        "patient_radionuclide_demand",
        "production_clinical_schedule",
        "infrastructure_capex",
        "infrastructure_opex",
        "lifecycle_economics",
    )


@dataclass(frozen=True)
class NativeDecisionComparisonResult:
    request: NativeDecisionPipelineScenario
    demand_result: NativeDemandResult
    conventional: NativePathwayResult
    mrt: NativePathwayResult
    batch_policy_description: str
    throughput_difference: int
    conventional_capex: float
    mrt_capex: float
    incremental_mrt_capex: float
    conventional_annual_opex: float
    mrt_annual_opex: float
    incremental_mrt_opex: float
    conventional_lifecycle_result: LifecycleEconomicResult
    mrt_lifecycle_result: LifecycleEconomicResult
    lifecycle_comparison_result: LifecycleComparisonResult
    incremental_npv: float
    economic_winner: Pathway | Literal["Tie"]
    bottleneck_information: Mapping[Pathway, NativeBottleneckSummary]
    provenance: NativePipelineProvenance
    integration_audit: NativeIntegrationAudit
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]


def _trace_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _bottleneck_summary(schedule_result) -> NativeBottleneckSummary:
    utilization = {
        "scanner": float(schedule_result.scanner_utilization_pct),
        "injection": float(schedule_result.injection_utilization_pct),
        "uptake": float(schedule_result.uptake_utilization_pct),
        "distribution": float(schedule_result.distribution_utilization_pct),
    }
    resource = max(utilization, key=utilization.get)
    resource_utilization = utilization[resource]
    near_binding = tuple(
        sorted(name for name, value in utilization.items() if resource_utilization - value <= 5.0)
    )
    return NativeBottleneckSummary(
        resource=resource,
        utilization_pct=resource_utilization,
        near_binding_resources=near_binding,
        utilization_by_resource=utilization,
    )


def _batch_policy_description(batch_target_patients_per_batch: int) -> str:
    return f"PIPELINE BATCH POLICY: ceil(patient_count / {int(batch_target_patients_per_batch)}) per radionuclide"


def _resolved_cyclotron_fleet(request: NativeDecisionPipelineScenario) -> CyclotronFleet:
    if request.cyclotron_fleet is not None:
        return request.cyclotron_fleet
    return build_single_cyclotron_fleet(request.cyclotron_capability)


def _derive_requested_batch_counts(
    simulation: DesignDaySimulationResult,
    batch_target_patients_per_batch: int,
) -> dict[str, int]:
    requested: dict[str, int] = {}
    for radionuclide in simulation.scenario.radionuclide_mix:
        count = int(simulation.patient_count_by_radionuclide.get(radionuclide, 0))
        requested[radionuclide] = 0 if count == 0 else max(1, math.ceil(count / float(batch_target_patients_per_batch)))
    return requested


def _patient_ids_by_radionuclide(facility_day: FacilityDayPatientDemand) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for patient in facility_day.patients:
        grouped.setdefault(patient.radionuclide, []).append(patient.patient_id)
    return {radionuclide: tuple(patient_ids) for radionuclide, patient_ids in grouped.items()}


def _build_demand_result(request: NativeDecisionPipelineScenario) -> NativeDemandResult:
    fleet = _resolved_cyclotron_fleet(request)
    scenario = DesignDayDemandScenario(
        target_patients_per_day=request.target_patients_per_day,
        radionuclide_mix=request.radionuclide_mix,
        activity_distribution_by_radionuclide=request.activity_distribution_by_radionuclide,
        day_type=request.day_type,
        available_radionuclides=fleet.fleet_supported_radionuclides,
        unsupported_radionuclide_policy="reject",
        peak_patient_multiplier=request.peak_patient_multiplier,
        peak_activity_multiplier=request.peak_activity_multiplier,
        seed=request.seed,
    )
    simulation = generate_design_day_demand(scenario)
    requested = _derive_requested_batch_counts(simulation, request.batch_target_patients_per_batch)
    batch_demands = partition_facility_day_patient_demand(simulation.generated_demand, requested)
    demand_trace_id = _trace_id(
        {
            "project_name": request.project_name,
            "seed": request.seed,
            "target_patients_per_day": request.target_patients_per_day,
            "day_type": request.day_type,
            "patient_count": simulation.patient_count,
            "fleet_id": fleet.fleet_id,
            "fleet_asset_ids": tuple(asset.cyclotron_id for asset in fleet.assets),
            "fleet_supported_radionuclides": tuple(fleet.fleet_supported_radionuclides),
            "patient_count_by_radionuclide": dict(simulation.patient_count_by_radionuclide),
            "total_activity_by_radionuclide": dict(simulation.total_activity_by_radionuclide),
            "requested_batch_count_by_radionuclide": requested,
        }
    )
    return NativeDemandResult(
        simulation=simulation,
        requested_batch_count_by_radionuclide=requested,
        batch_demands=batch_demands,
        patient_ids_by_radionuclide=_patient_ids_by_radionuclide(simulation.generated_demand),
        fleet_supported_radionuclides=fleet.fleet_supported_radionuclides,
        trace_id=demand_trace_id,
        batch_policy_description=_batch_policy_description(request.batch_target_patients_per_batch),
    )


def _build_capex_inputs(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
) -> InfrastructureCapexInputs:
    fleet_size = _resolved_cyclotron_fleet(request).asset_count
    if pathway_config.existing_cyclotron_units > fleet_size:
        raise ValueError("existing_cyclotron_units cannot exceed selected fleet size")
    return InfrastructureCapexInputs(
        pathway=pathway_config.pathway,
        deployment_mode=pathway_config.deployment_mode,
        installed_scanners=pathway_config.scanners,
        existing_scanners=pathway_config.existing_scanners,
        installed_injection_resources=pathway_config.injection_resources,
        existing_injection_resources=pathway_config.existing_injection_resources,
        installed_uptake_resources=pathway_config.uptake_resources,
        existing_uptake_resources=pathway_config.existing_uptake_resources,
        installed_cyclotron_units=fleet_size,
        existing_cyclotron_units=pathway_config.existing_cyclotron_units,
        installed_radiopharmacy_units=pathway_config.installed_radiopharmacy_units,
        existing_radiopharmacy_units=pathway_config.existing_radiopharmacy_units,
        radiopharmacy_unit_capex=pathway_config.radiopharmacy_unit_capex,
        conventional_infrastructure_allowance_units=pathway_config.conventional_infrastructure_allowance_units,
        existing_conventional_infrastructure_allowance_units=pathway_config.existing_conventional_infrastructure_allowance_units,
        conventional_infrastructure_allowance_unit_capex=pathway_config.conventional_infrastructure_allowance_unit_capex,
        installed_mrt_base_infrastructure_units=pathway_config.installed_mrt_base_infrastructure_units,
        existing_mrt_base_infrastructure_units=pathway_config.existing_mrt_base_infrastructure_units,
        installed_mrt_endpoints=pathway_config.installed_mrt_endpoints,
        existing_mrt_endpoints=pathway_config.existing_mrt_endpoints,
        installed_guideway_length_m=pathway_config.installed_guideway_length_m,
        existing_guideway_length_m=pathway_config.existing_guideway_length_m,
        guideway_capex_per_m=pathway_config.guideway_capex_per_m,
        installed_vertical_transitions=pathway_config.installed_vertical_transitions,
        existing_vertical_transitions=pathway_config.existing_vertical_transitions,
        installed_building_connections=pathway_config.installed_building_connections,
        existing_building_connections=pathway_config.existing_building_connections,
        assumptions=request.planner_assumptions,
        network_assumptions=request.shared_network_assumptions,
    )


def _build_opex_inputs(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
) -> InfrastructureOpexInputs:
    fleet_size = _resolved_cyclotron_fleet(request).asset_count
    return InfrastructureOpexInputs(
        pathway=pathway_config.pathway,
        deployment_mode=pathway_config.deployment_mode,
        operated_scanners=pathway_config.scanners,
        operated_injection_resources=pathway_config.injection_resources,
        operated_uptake_resources=pathway_config.uptake_resources,
        operated_cyclotron_units=fleet_size,
        operated_radiopharmacy_units=pathway_config.operated_radiopharmacy_units,
        operated_mrt_base_units=pathway_config.operated_mrt_base_units,
        operated_mrt_endpoints=pathway_config.operated_mrt_endpoints,
        operated_guideway_length_m=pathway_config.operated_guideway_length_m,
        operated_vertical_transitions=pathway_config.operated_vertical_transitions,
        operated_building_connections=pathway_config.operated_building_connections,
        operating_days_per_year=request.planner_assumptions.operating_days_per_year,
        annual_conventional_transport_opex=pathway_config.annual_conventional_transport_opex,
        conventional_transport_staff_fte=pathway_config.conventional_transport_staff_fte,
        conventional_transport_staff_loaded_cost_per_fte=pathway_config.conventional_transport_staff_loaded_cost_per_fte,
        mrt_base_annual_opex_per_unit=pathway_config.mrt_base_annual_opex_per_unit,
        guideway_maintenance_per_m_year=pathway_config.guideway_maintenance_per_m_year,
        vertical_transition_annual_opex_per_unit=pathway_config.vertical_transition_annual_opex_per_unit,
        building_connection_annual_opex_per_unit=pathway_config.building_connection_annual_opex_per_unit,
        annual_production_variable_cost=pathway_config.annual_production_variable_cost,
        cyclotron_annual_opex_per_unit=pathway_config.cyclotron_annual_opex_per_unit,
        annual_scanner_energy_kwh=pathway_config.annual_scanner_energy_kwh,
        annual_cyclotron_energy_kwh=pathway_config.annual_cyclotron_energy_kwh,
        annual_mrt_energy_kwh=pathway_config.annual_mrt_energy_kwh,
        annual_other_energy_kwh=pathway_config.annual_other_energy_kwh,
        electricity_cost_per_kwh=pathway_config.electricity_cost_per_kwh,
        clinical_staff_fte=pathway_config.clinical_staff_fte,
        clinical_staff_loaded_cost_per_fte=pathway_config.clinical_staff_loaded_cost_per_fte,
        production_staff_fte=pathway_config.production_staff_fte,
        production_staff_loaded_cost_per_fte=pathway_config.production_staff_loaded_cost_per_fte,
        mrt_support_staff_fte=pathway_config.mrt_support_staff_fte,
        mrt_support_staff_loaded_cost_per_fte=pathway_config.mrt_support_staff_loaded_cost_per_fte,
        annual_consumable_units=pathway_config.annual_consumable_units,
        consumable_cost_per_unit=pathway_config.consumable_cost_per_unit,
        assumptions=request.planner_assumptions,
    )


def _decay_feasibility_guard(request: NativeDecisionPipelineScenario) -> tuple[float, float | None]:
    minimum_retained = float(request.planner_assumptions.decay_feasibility_min_retained_fraction)
    if minimum_retained < 0.0 or minimum_retained > 1.0:
        raise ValueError("planner_assumptions.decay_feasibility_min_retained_fraction must be within [0.0, 1.0]")
    max_compensation = request.planner_assumptions.decay_feasibility_max_compensation_factor
    if max_compensation is not None and float(max_compensation) < 1.0:
        raise ValueError("planner_assumptions.decay_feasibility_max_compensation_factor must be at least 1.0")
    return minimum_retained, (None if max_compensation is None else float(max_compensation))


def _build_schedule_for_batches(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
    facility_day_demand: FacilityDayPatientDemand,
    requested_batch_count_by_radionuclide: Mapping[str, int],
) -> ProductionClinicalScheduleResult:
    fleet = _resolved_cyclotron_fleet(request)
    schedule = ProductionClinicalScenario(
        facility_day_demand=facility_day_demand,
        requested_batch_count_by_radionuclide=requested_batch_count_by_radionuclide,
        cyclotron_fleet=fleet,
        transport_minutes=pathway_config.transport_minutes,
        injection_service_minutes=request.planner_assumptions.injection_cycle_min,
        uptake_minutes=request.planner_assumptions.uptake_cycle_min,
        scanner_service_minutes=request.planner_assumptions.scanner_cycle_min,
        injection_resources=pathway_config.injection_resources,
        uptake_resources=pathway_config.uptake_resources,
        scanners=pathway_config.scanners,
        distribution_concurrency=pathway_config.distribution_concurrency,
        operating_day_minutes=request.operating_day_minutes,
    )
    return build_production_clinical_schedule(schedule)


def _optimize_batches_for_decay_feasibility(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
    demand_result: NativeDemandResult,
) -> tuple[ProductionClinicalScheduleResult, PathwayDecaySummary]:
    minimum_retained, max_compensation = _decay_feasibility_guard(request)
    requested = {key: int(value) for key, value in demand_result.requested_batch_count_by_radionuclide.items()}
    max_batches_by_isotope = {
        isotope: max(1, int(count))
        for isotope, count in demand_result.simulation.patient_count_by_radionuclide.items()
        if int(count) > 0
    }

    seen: set[tuple[tuple[str, int], ...]] = set()
    best_schedule = _build_schedule_for_batches(
        request,
        pathway_config,
        demand_result.simulation.generated_demand,
        requested,
    )
    best_decay = evaluate_pathway_decay(
        pathway=pathway_config.pathway,
        generated_patients=demand_result.simulation.generated_demand.patients,
        patient_traces=best_schedule.patient_traces,
        min_retained_fraction_for_feasibility=minimum_retained,
        max_decay_compensation_factor=max_compensation,
    )
    baseline_completed_patients = best_schedule.clinical_schedule.completed_patients

    for _ in range(64):
        key = tuple(sorted(requested.items()))
        if key in seen:
            break
        seen.add(key)

        schedule = _build_schedule_for_batches(
            request,
            pathway_config,
            demand_result.simulation.generated_demand,
            requested,
        )
        decay_summary = evaluate_pathway_decay(
            pathway=pathway_config.pathway,
            generated_patients=demand_result.simulation.generated_demand.patients,
            patient_traces=schedule.patient_traces,
            min_retained_fraction_for_feasibility=minimum_retained,
            max_decay_compensation_factor=max_compensation,
        )

        completed_patients = schedule.clinical_schedule.completed_patients
        if completed_patients >= baseline_completed_patients:
            if decay_summary.decay_infeasible_patient_count < best_decay.decay_infeasible_patient_count or (
                decay_summary.decay_infeasible_patient_count == best_decay.decay_infeasible_patient_count
                and decay_summary.mean_retained_fraction > best_decay.mean_retained_fraction
            ):
                best_schedule = schedule
                best_decay = decay_summary

        if decay_summary.decay_infeasible_patient_count == 0:
            return schedule, decay_summary

        increments = 0
        for isotope, count in sorted(decay_summary.decay_infeasible_by_isotope.items(), key=lambda item: item[1], reverse=True):
            if count <= 0:
                continue
            current = requested.get(isotope, 0)
            maximum = max_batches_by_isotope.get(isotope, current)
            if current < maximum:
                requested[isotope] = current + 1
                increments += 1

        if increments == 0:
            break

    return best_schedule, best_decay


def _build_operational_result(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
    demand_result: NativeDemandResult,
) -> tuple[ProductionClinicalScheduleResult, NativeOperationalResult]:
    production_result, decay_summary = _optimize_batches_for_decay_feasibility(request, pathway_config, demand_result)
    clinical_result = production_result.clinical_schedule
    scheduled_patients = clinical_result.total_patients_considered
    schedule_completed_patients = clinical_result.completed_patients
    decay_feasible_scheduled_patients = decay_summary.decay_feasible_patient_count
    decay_feasible_completed_patients = decay_summary.feasible_completed_patients
    (
        production_feasible_patient_ids,
        production_activity_feasible_scheduled_patients,
        production_activity_feasible_completed_patients,
        activity_capacity_warnings,
    ) = _apply_production_activity_capacity_guard(
        request=request,
        pathway=pathway_config.pathway,
        production_result=production_result,
        decay_summary=decay_summary,
    )
    effective_completed_patients = production_activity_feasible_completed_patients
    production_activity_infeasible_patients = max(0, decay_feasible_scheduled_patients - production_activity_feasible_scheduled_patients)
    decay_infeasible_patients = decay_summary.decay_infeasible_patient_count
    effective_completion_percentage = (100.0 * effective_completed_patients / scheduled_patients) if scheduled_patients > 0 else 0.0
    bottleneck = _bottleneck_summary(clinical_result)
    mrt_carrier_fleet = (
        resolve_mrt_carrier_fleet(
            distribution_concurrency=pathway_config.distribution_concurrency,
            installed_carriers=pathway_config.installed_mrt_carriers,
            operated_carriers=pathway_config.operated_mrt_carriers,
            bottleneck_resource=bottleneck.resource,
        )
        if pathway_config.pathway == "MRT"
        else None
    )
    operational_trace_id = _trace_id(
        {
            "demand_trace_id": demand_result.trace_id,
            "pathway": pathway_config.pathway,
            "completed_patients": decay_feasible_completed_patients,
            "production_activity_feasible_patient_ids": tuple(sorted(production_feasible_patient_ids)),
            "scheduled_patients": scheduled_patients,
            "schedule_completed_patients": schedule_completed_patients,
            "uncompleted_patients": clinical_result.uncompleted_patients,
            "production_elapsed_minutes": production_result.production_schedule.total_elapsed_production_minutes,
            "final_scan_completion_time_minutes": clinical_result.last_scan_completion_minute,
            "bottleneck": bottleneck.resource,
            "utilization": bottleneck.utilization_by_resource,
            "mrt_carrier_fleet": (
                None
                if mrt_carrier_fleet is None
                else {
                    "installed_carriers": mrt_carrier_fleet.installed_carriers,
                    "operated_carriers": mrt_carrier_fleet.operated_carriers,
                    "spare_carriers": mrt_carrier_fleet.spare_carriers,
                    "distribution_concurrency": mrt_carrier_fleet.distribution_concurrency,
                    "carrier_constrained_throughput": mrt_carrier_fleet.carrier_constrained_throughput,
                }
            ),
            "batch_release_mappings": [
                {
                    "batch_id": mapping.batch_id,
                    "production_window_id": mapping.production_window_id,
                    "release_time_minutes": mapping.release_time_minutes,
                }
                for mapping in production_result.batch_release_mappings
            ],
            "decay_overall_loss_mbq": decay_summary.overall_decay_loss_mbq,
            "decay_mean_retained_fraction": decay_summary.mean_retained_fraction,
            "dose_insufficient_if_no_upstream_adjustment": decay_summary.dose_insufficient_patient_count_if_no_upstream_adjustment,
        }
    )
    operational = NativeOperationalResult(
        pathway=pathway_config.pathway,
        pathway_config=pathway_config,
        demand_result=demand_result,
        production_clinical_result=production_result,
        scheduled_patients=scheduled_patients,
        schedule_completed_patients=schedule_completed_patients,
        decay_feasible_scheduled_patients=decay_feasible_scheduled_patients,
        decay_feasible_completed_patients=decay_feasible_completed_patients,
        production_activity_feasible_scheduled_patients=production_activity_feasible_scheduled_patients,
        production_activity_feasible_completed_patients=production_activity_feasible_completed_patients,
        production_activity_infeasible_patients=production_activity_infeasible_patients,
        decay_infeasible_patients=decay_infeasible_patients,
        effective_completion_percentage=effective_completion_percentage,
        patients_considered=scheduled_patients,
        patients_completed=effective_completed_patients,
        patients_incomplete=max(0, scheduled_patients - effective_completed_patients),
        completion_percentage=effective_completion_percentage,
        production_elapsed_minutes=production_result.production_schedule.total_elapsed_production_minutes,
        final_scan_completion_time_minutes=clinical_result.last_scan_completion_minute,
        scanner_utilization_pct=clinical_result.scanner_utilization_pct,
        injection_utilization_pct=clinical_result.injection_utilization_pct,
        uptake_utilization_pct=clinical_result.uptake_utilization_pct,
        distribution_utilization_pct=clinical_result.distribution_utilization_pct,
        bottleneck=bottleneck,
        mrt_carrier_fleet=mrt_carrier_fleet,
        decay_summary=decay_summary,
        activity_capacity_warnings=activity_capacity_warnings,
        trace_id=operational_trace_id,
    )
    return production_result, operational


def _asset_uses_catalog_strict_activity_basis(capability_provenance: str | None) -> bool:
    if capability_provenance is None:
        return False
    marker = capability_provenance.strip()
    if not marker:
        return False
    if marker.lower() == "test":
        return False
    return True


def _apply_production_activity_capacity_guard(
    *,
    request: NativeDecisionPipelineScenario,
    pathway: Pathway,
    production_result: ProductionClinicalScheduleResult,
    decay_summary: PathwayDecaySummary,
) -> tuple[set[str], int, int, tuple[str, ...]]:
    fleet = _resolved_cyclotron_fleet(request)
    asset_by_id = {asset.cyclotron_id: asset for asset in fleet.assets}

    decay_by_batch: dict[int, list[object]] = {}
    for trace in decay_summary.patient_traces:
        decay_by_batch.setdefault(trace.batch_id, []).append(trace)
    for traces in decay_by_batch.values():
        traces.sort(key=lambda item: (item.injection_start_minutes, item.patient_id))

    remaining_daily_capacity_by_cyclotron: dict[str, float] = {}
    for asset in fleet.assets:
        if asset.capability.site_eob_capacity_mbq_per_day is not None:
            remaining_daily_capacity_by_cyclotron[asset.cyclotron_id] = float(asset.capability.site_eob_capacity_mbq_per_day)

    feasible_patient_ids: set[str] = set()
    warnings: list[str] = []

    ordered_mappings = sorted(
        production_result.batch_release_mappings,
        key=lambda item: (item.release_time_minutes, item.batch_id),
    )
    for mapping in ordered_mappings:
        asset = asset_by_id[mapping.assigned_cyclotron_id]
        capability = asset.capability
        batch_traces = decay_by_batch.get(mapping.batch_id, [])
        if not batch_traces:
            continue

        strict_catalog_mode = _asset_uses_catalog_strict_activity_basis(asset.capability_provenance)
        site_daily_capacity = capability.site_eob_capacity_mbq_per_day
        calibrated_map = capability.calibrated_eob_activity_mbq_by_radionuclide or {}
        calibrated_batch_capacity = calibrated_map.get(mapping.radionuclide)

        if strict_catalog_mode and site_daily_capacity is None and calibrated_batch_capacity is None:
            warnings.append(
                f"{pathway} {mapping.assigned_cyclotron_id} lacks calibrated EOB activity for {mapping.radionuclide}; production remains not_calibrated for this batch."
            )
            continue

        batch_used_eob_mbq = 0.0
        for trace in batch_traces:
            if not trace.decay_feasible:
                continue
            required_eob = float(trace.required_upstream_activity_for_prescribed_mbq)
            if not math.isfinite(required_eob) or required_eob <= 0.0:
                continue

            if site_daily_capacity is not None:
                remaining = remaining_daily_capacity_by_cyclotron.get(mapping.assigned_cyclotron_id, float(site_daily_capacity))
                if required_eob > remaining + 1e-9:
                    continue
                remaining_daily_capacity_by_cyclotron[mapping.assigned_cyclotron_id] = max(0.0, remaining - required_eob)
                feasible_patient_ids.add(trace.patient_id)
                continue

            if calibrated_batch_capacity is None:
                feasible_patient_ids.add(trace.patient_id)
                continue

            if batch_used_eob_mbq + required_eob <= float(calibrated_batch_capacity) + 1e-9:
                batch_used_eob_mbq += required_eob
                feasible_patient_ids.add(trace.patient_id)

    scheduled_decay_feasible = [trace for trace in decay_summary.patient_traces if trace.decay_feasible]
    completed_decay_feasible = [trace for trace in scheduled_decay_feasible if trace.completed_within_operating_day]
    scheduled_final = [trace for trace in scheduled_decay_feasible if trace.patient_id in feasible_patient_ids]
    completed_final = [trace for trace in completed_decay_feasible if trace.patient_id in feasible_patient_ids]

    return (
        feasible_patient_ids,
        len(scheduled_final),
        len(completed_final),
        tuple(dict.fromkeys(warnings)),
    )


def _limitations() -> tuple[str, ...]:
    return (
        "Batch counts are derived from explicit batch_target_patients_per_batch; no canonical repository policy exists.",
        "No spatially derived guideway length.",
        "No floor-area/floor-count resource placement.",
        "MRT carrier quantity is represented via distribution_concurrency; no authoritative separate per-carrier CAPEX/OPEX/energy coefficients exist in the repository baseline.",
        "Decay physics is natively integrated, but direct monetization of activity loss requires an authoritative isotope-production cost model.",
        "No detailed MRT energy physics.",
        "No demand-driven staffing inference.",
        "Cyclotron manufacturer/model library is not implemented as a permanent repository object.",
        "Model-specific beam energy, target yields, target-change constraints, and synthesis/QC yield curves are not represented in this native build.",
    )


def _warnings(request: NativeDecisionPipelineScenario, pathway_config: NativePathwayScenario) -> tuple[str, ...]:
    notes = [
        _limitations()[0],
    ]
    if pathway_config.pathway == "MRT":
        if pathway_config.installed_guideway_length_m <= 0.0:
            notes.append("MRT guideway length must be provided explicitly; this build does not derive it from geometry.")
        if pathway_config.guideway_capex_per_m <= 0.0:
            notes.append("MRT guideway CapEx per meter must be provided explicitly.")
        notes.append(
            "MRT carrier quantity is modeled through distribution_concurrency; separate per-carrier CAPEX/OPEX/energy remain not yet modeled in this build."
        )
    supported = set(_resolved_cyclotron_fleet(request).fleet_supported_radionuclides)
    unsupported = set(request.radionuclide_mix).difference(supported)
    if unsupported:
        notes.append(
            f"Cyclotron capability does not support requested radionuclides: {sorted(unsupported)}"
        )
    if pathway_config.installed_cyclotron_units != _resolved_cyclotron_fleet(request).asset_count:
        notes.append(
            f"Pathway installed_cyclotron_units ({pathway_config.installed_cyclotron_units}) differs from selected fleet size ({_resolved_cyclotron_fleet(request).asset_count}); fleet size is authoritative for CAPEX/OPEX cyclotron unit counts in this build."
        )
    if pathway_config.operated_cyclotron_units != _resolved_cyclotron_fleet(request).asset_count:
        notes.append(
            f"Pathway operated_cyclotron_units ({pathway_config.operated_cyclotron_units}) differs from selected fleet size ({_resolved_cyclotron_fleet(request).asset_count}); fleet size is authoritative for CAPEX/OPEX cyclotron unit counts in this build."
        )
    return tuple(notes)


def _build_pathway_result(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
    demand_result: NativeDemandResult,
) -> NativePathwayResult:
    _, operational_result = _build_operational_result(request, pathway_config, demand_result)
    capex_inputs = _build_capex_inputs(request, pathway_config)
    opex_inputs = _build_opex_inputs(request, pathway_config)
    capex_result = calculate_infrastructure_capex(capex_inputs)
    opex_result = calculate_infrastructure_opex(opex_inputs)

    completed_per_day = float(operational_result.patients_completed)
    lifecycle_result = evaluate_lifecycle_economics(
        initial_capex=capex_result.total_capex,
        installed_capacity_per_day=completed_per_day,
        annual_opex=opex_result.total_annual_opex,
        revenue_per_scan=request.planner_assumptions.revenue_per_scan,
        operating_days_per_year=request.planner_assumptions.operating_days_per_year,
        discount_rate_pct=request.planner_assumptions.discount_rate_pct,
        analysis_years=request.planner_assumptions.analysis_years,
        starting_demand_per_day=completed_per_day,
        annual_demand_growth_rate=0.0,
    )

    pathway_trace_id = _trace_id(
        {
            "operational_trace_id": operational_result.trace_id,
            "capex_total": capex_result.total_capex,
            "opex_total": opex_result.total_annual_opex,
            "lifecycle_final_npv": lifecycle_result.final_npv,
            "lifecycle_payback_year": lifecycle_result.payback_year,
        }
    )
    annual_completed_scans = completed_per_day * float(request.planner_assumptions.operating_days_per_year)
    annual_revenue = lifecycle_result.annual_rows[0].annual_revenue if lifecycle_result.annual_rows else 0.0
    annual_opex = opex_result.total_annual_opex

    return NativePathwayResult(
        pathway=pathway_config.pathway,
        operational_result=operational_result,
        capex_result=capex_result,
        opex_result=opex_result,
        lifecycle_result=lifecycle_result,
        actual_lifecycle_throughput_per_day=completed_per_day,
        annual_completed_scans=annual_completed_scans,
        annual_revenue=annual_revenue,
        annual_opex=annual_opex,
        decay_summary=operational_result.decay_summary,
        trace_id=pathway_trace_id,
        warnings=_warnings(request, pathway_config)
        + operational_result.activity_capacity_warnings
        + ((
            f"{pathway_config.pathway} pathway potential dose-insufficient patients without upstream activity adjustment: "
            f"{operational_result.decay_summary.dose_insufficient_patient_count_if_no_upstream_adjustment}"
        ), (
            f"{pathway_config.pathway} pathway decay-infeasible patients under configured guard: "
            f"{operational_result.decay_summary.decay_infeasible_patient_count}"
        ), (
            f"{pathway_config.pathway} pathway raw schedule-completed patients: {operational_result.schedule_completed_patients}; "
            f"effective decay-feasible completed patients: {operational_result.decay_feasible_completed_patients}"
        )),
    )


def run_native_pathway_pipeline(
    request: NativeDecisionPipelineScenario,
    pathway: Pathway,
    demand_result: NativeDemandResult | None = None,
) -> NativePathwayResult:
    if demand_result is None:
        demand_result = _build_demand_result(request)
    pathway_config = request.conventional if pathway == "Conventional" else request.mrt
    return _build_pathway_result(request, pathway_config, demand_result)


def run_native_decision_pipeline(request: NativeDecisionPipelineScenario) -> NativeDecisionComparisonResult:
    demand_result = _build_demand_result(request)
    conventional_result = _build_pathway_result(request, request.conventional, demand_result)
    mrt_result = _build_pathway_result(request, request.mrt, demand_result)

    comparison_trace_id = _trace_id(
        {
            "scenario_trace_id": _trace_id(
                {
                    "project_name": request.project_name,
                    "target_patients_per_day": request.target_patients_per_day,
                    "radionuclide_mix": dict(request.radionuclide_mix),
                    "seed": request.seed,
                    "day_type": request.day_type,
                    "batch_target_patients_per_batch": request.batch_target_patients_per_batch,
                }
            ),
            "demand_trace_id": demand_result.trace_id,
            "conventional_trace_id": conventional_result.trace_id,
            "mrt_trace_id": mrt_result.trace_id,
            "incremental_npv": mrt_result.lifecycle_result.final_npv - conventional_result.lifecycle_result.final_npv,
        }
    )
    scenario_trace_id = _trace_id(
        {
            "project_name": request.project_name,
            "target_patients_per_day": request.target_patients_per_day,
            "radionuclide_mix": dict(request.radionuclide_mix),
            "seed": request.seed,
            "day_type": request.day_type,
            "batch_target_patients_per_batch": request.batch_target_patients_per_batch,
        }
    )
    provenance = NativePipelineProvenance(
        request=request,
        scenario_trace_id=scenario_trace_id,
        demand_trace_id=demand_result.trace_id,
        fleet_id=_resolved_cyclotron_fleet(request).fleet_id,
        fleet_asset_ids=tuple(asset.cyclotron_id for asset in _resolved_cyclotron_fleet(request).assets),
        fleet_supported_radionuclides=_resolved_cyclotron_fleet(request).fleet_supported_radionuclides,
        conventional_trace_id=conventional_result.trace_id,
        mrt_trace_id=mrt_result.trace_id,
        comparison_trace_id=comparison_trace_id,
        batch_policy_description=demand_result.batch_policy_description,
    )

    limitations = _limitations()
    warnings = tuple(dict.fromkeys(conventional_result.warnings + mrt_result.warnings + (limitations[0],)))
    audit = NativeIntegrationAudit(
        demand_to_patients="DIRECT NATIVE CONNECTION",
        patients_to_isotope_batching="DIRECT NATIVE CONNECTION",
        batches_to_production="DIRECT NATIVE CONNECTION",
        production_to_clinical_schedule="DIRECT NATIVE CONNECTION (WITH PER-PATIENT DECAY TRACE)",
        resource_quantities_to_capex="DIRECT NATIVE CONNECTION",
        resource_quantities_to_opex="DIRECT NATIVE CONNECTION",
        actual_clinical_completion_to_lifecycle_throughput="DIRECT NATIVE CONNECTION",
        capex_to_lifecycle="DIRECT NATIVE CONNECTION",
        opex_to_lifecycle="DIRECT NATIVE CONNECTION",
        lifecycle_to_conventional_mrt_comparison="DIRECT NATIVE CONNECTION",
        missing_capabilities=limitations[1:],
    )
    bottlenecks = {
        "Conventional": conventional_result.operational_result.bottleneck,
        "MRT": mrt_result.operational_result.bottleneck,
    }
    comparison = compare_lifecycle_results(
        conventional=conventional_result.lifecycle_result,
        mrt=mrt_result.lifecycle_result,
    )
    incremental_npv = mrt_result.lifecycle_result.final_npv - conventional_result.lifecycle_result.final_npv
    economic_winner: Pathway | Literal["Tie"]
    if incremental_npv > 0.0:
        economic_winner = "MRT"
    elif incremental_npv < 0.0:
        economic_winner = "Conventional"
    else:
        economic_winner = "Tie"

    return NativeDecisionComparisonResult(
        request=request,
        demand_result=demand_result,
        conventional=conventional_result,
        mrt=mrt_result,
        batch_policy_description=demand_result.batch_policy_description,
        throughput_difference=mrt_result.operational_result.patients_completed - conventional_result.operational_result.patients_completed,
        conventional_capex=conventional_result.capex_result.total_capex,
        mrt_capex=mrt_result.capex_result.total_capex,
        incremental_mrt_capex=mrt_result.capex_result.total_capex - conventional_result.capex_result.total_capex,
        conventional_annual_opex=conventional_result.opex_result.total_annual_opex,
        mrt_annual_opex=mrt_result.opex_result.total_annual_opex,
        incremental_mrt_opex=mrt_result.opex_result.total_annual_opex - conventional_result.opex_result.total_annual_opex,
        conventional_lifecycle_result=conventional_result.lifecycle_result,
        mrt_lifecycle_result=mrt_result.lifecycle_result,
        lifecycle_comparison_result=comparison,
        incremental_npv=incremental_npv,
        economic_winner=economic_winner,
        bottleneck_information=bottlenecks,
        provenance=provenance,
        integration_audit=audit,
        warnings=warnings,
        limitations=limitations,
    )

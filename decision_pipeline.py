from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from cyclotron_production_windows import CyclotronProductionCapability
from infrastructure_capex import InfrastructureCapexInputs, InfrastructureCapexResult, calculate_infrastructure_capex
from infrastructure_opex import InfrastructureOpexInputs, InfrastructureOpexResult, calculate_infrastructure_opex
from lifecycle_economics import LifecycleComparisonResult, LifecycleEconomicResult, compare_lifecycle_results, evaluate_lifecycle_economics
from models import PlannerAssumptions, SharedNetworkAssumptions
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
    injection_resources: int = 0
    uptake_resources: int = 0
    distribution_concurrency: int = 1
    transport_minutes: float = 0.0
    installed_cyclotron_units: int = 1
    installed_radiopharmacy_units: int = 1
    radiopharmacy_unit_capex: float = 0.0
    conventional_infrastructure_allowance_units: int = 0
    conventional_infrastructure_allowance_unit_capex: float = 0.0
    installed_mrt_base_infrastructure_units: int = 0
    installed_mrt_endpoints: int = 0
    installed_guideway_length_m: float = 0.0
    guideway_capex_per_m: float = 0.0
    installed_vertical_transitions: int = 0
    installed_building_connections: int = 0
    operated_cyclotron_units: int = 1
    operated_radiopharmacy_units: int = 1
    operated_mrt_base_units: int = 0
    operated_mrt_endpoints: int = 0
    operated_guideway_length_m: float = 0.0
    operated_vertical_transitions: int = 0
    operated_building_connections: int = 0
    annual_conventional_transport_opex: float = 0.0
    annual_production_variable_cost: float = 0.0
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
        if self.installed_cyclotron_units < 0:
            raise ValueError("installed_cyclotron_units must be non-negative")
        if self.installed_radiopharmacy_units < 0:
            raise ValueError("installed_radiopharmacy_units must be non-negative")
        if self.installed_mrt_base_infrastructure_units < 0:
            raise ValueError("installed_mrt_base_infrastructure_units must be non-negative")
        if self.installed_mrt_endpoints < 0:
            raise ValueError("installed_mrt_endpoints must be non-negative")
        if self.installed_guideway_length_m < 0.0:
            raise ValueError("installed_guideway_length_m must be non-negative")
        if self.installed_vertical_transitions < 0:
            raise ValueError("installed_vertical_transitions must be non-negative")
        if self.installed_building_connections < 0:
            raise ValueError("installed_building_connections must be non-negative")
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
        if self.annual_production_variable_cost < 0.0:
            raise ValueError("annual_production_variable_cost must be non-negative")


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
    trace_id: str
    batch_policy_description: str


@dataclass(frozen=True)
class NativeOperationalResult:
    pathway: Pathway
    pathway_config: NativePathwayScenario
    demand_result: NativeDemandResult
    production_clinical_result: ProductionClinicalScheduleResult
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
    scenario = DesignDayDemandScenario(
        target_patients_per_day=request.target_patients_per_day,
        radionuclide_mix=request.radionuclide_mix,
        activity_distribution_by_radionuclide=request.activity_distribution_by_radionuclide,
        day_type=request.day_type,
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
        trace_id=demand_trace_id,
        batch_policy_description=_batch_policy_description(request.batch_target_patients_per_batch),
    )


def _build_capex_inputs(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
) -> InfrastructureCapexInputs:
    return InfrastructureCapexInputs(
        pathway=pathway_config.pathway,
        deployment_mode=pathway_config.deployment_mode,
        installed_scanners=pathway_config.scanners,
        installed_injection_resources=pathway_config.injection_resources,
        installed_uptake_resources=pathway_config.uptake_resources,
        installed_cyclotron_units=pathway_config.installed_cyclotron_units,
        installed_radiopharmacy_units=pathway_config.installed_radiopharmacy_units,
        radiopharmacy_unit_capex=pathway_config.radiopharmacy_unit_capex,
        conventional_infrastructure_allowance_units=pathway_config.conventional_infrastructure_allowance_units,
        conventional_infrastructure_allowance_unit_capex=pathway_config.conventional_infrastructure_allowance_unit_capex,
        installed_mrt_base_infrastructure_units=pathway_config.installed_mrt_base_infrastructure_units,
        installed_mrt_endpoints=pathway_config.installed_mrt_endpoints,
        installed_guideway_length_m=pathway_config.installed_guideway_length_m,
        guideway_capex_per_m=pathway_config.guideway_capex_per_m,
        installed_vertical_transitions=pathway_config.installed_vertical_transitions,
        installed_building_connections=pathway_config.installed_building_connections,
        assumptions=request.planner_assumptions,
        network_assumptions=request.shared_network_assumptions,
    )


def _build_opex_inputs(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
) -> InfrastructureOpexInputs:
    return InfrastructureOpexInputs(
        pathway=pathway_config.pathway,
        deployment_mode=pathway_config.deployment_mode,
        operated_scanners=pathway_config.scanners,
        operated_injection_resources=pathway_config.injection_resources,
        operated_uptake_resources=pathway_config.uptake_resources,
        operated_cyclotron_units=pathway_config.operated_cyclotron_units,
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


def _build_operational_result(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
    demand_result: NativeDemandResult,
) -> tuple[ProductionClinicalScheduleResult, NativeOperationalResult]:
    schedule = ProductionClinicalScenario(
        facility_day_demand=demand_result.simulation.generated_demand,
        requested_batch_count_by_radionuclide=demand_result.requested_batch_count_by_radionuclide,
        cyclotron_capability=request.cyclotron_capability,
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
    production_result = build_production_clinical_schedule(schedule)
    clinical_result = production_result.clinical_schedule
    bottleneck = _bottleneck_summary(clinical_result)
    operational_trace_id = _trace_id(
        {
            "demand_trace_id": demand_result.trace_id,
            "pathway": pathway_config.pathway,
            "completed_patients": clinical_result.completed_patients,
            "uncompleted_patients": clinical_result.uncompleted_patients,
            "production_elapsed_minutes": production_result.production_schedule.total_elapsed_production_minutes,
            "final_scan_completion_time_minutes": clinical_result.last_scan_completion_minute,
            "bottleneck": bottleneck.resource,
            "utilization": bottleneck.utilization_by_resource,
            "batch_release_mappings": [
                {
                    "batch_id": mapping.batch_id,
                    "production_window_id": mapping.production_window_id,
                    "release_time_minutes": mapping.release_time_minutes,
                }
                for mapping in production_result.batch_release_mappings
            ],
        }
    )
    operational = NativeOperationalResult(
        pathway=pathway_config.pathway,
        pathway_config=pathway_config,
        demand_result=demand_result,
        production_clinical_result=production_result,
        patients_considered=clinical_result.total_patients_considered,
        patients_completed=clinical_result.completed_patients,
        patients_incomplete=clinical_result.uncompleted_patients,
        completion_percentage=(100.0 * clinical_result.completed_patients / clinical_result.total_patients_considered) if clinical_result.total_patients_considered else 0.0,
        production_elapsed_minutes=production_result.production_schedule.total_elapsed_production_minutes,
        final_scan_completion_time_minutes=clinical_result.last_scan_completion_minute,
        scanner_utilization_pct=clinical_result.scanner_utilization_pct,
        injection_utilization_pct=clinical_result.injection_utilization_pct,
        uptake_utilization_pct=clinical_result.uptake_utilization_pct,
        distribution_utilization_pct=clinical_result.distribution_utilization_pct,
        bottleneck=bottleneck,
        trace_id=operational_trace_id,
    )
    return production_result, operational


def _limitations() -> tuple[str, ...]:
    return (
        "Batch counts are derived from explicit batch_target_patients_per_batch; no canonical repository policy exists.",
        "No spatially derived guideway length.",
        "No floor-area/floor-count resource placement.",
        "No multi-isotope decay-adjusted economics.",
        "No detailed MRT energy physics.",
        "No demand-driven staffing inference.",
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
        trace_id=pathway_trace_id,
        warnings=_warnings(request, pathway_config),
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
        production_to_clinical_schedule="DIRECT NATIVE CONNECTION",
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

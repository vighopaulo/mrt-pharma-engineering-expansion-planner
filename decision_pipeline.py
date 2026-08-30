from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Literal, Mapping

from cycle_relative_production_requirement import (
    CycleRelativeRequirementResult,
    derive_cycle_relative_requirement,
    generate_candidate_production_cycles,
)
from cyclotron_production_windows import CyclotronFleet, CyclotronProductionCapability, build_single_cyclotron_fleet
from diagnostics import load_radionuclide_half_lives
from infrastructure_capex import InfrastructureCapexInputs, InfrastructureCapexResult, calculate_infrastructure_capex
from infrastructure_opex import InfrastructureOpexInputs, InfrastructureOpexResult, calculate_infrastructure_opex
from lifecycle_economics import LifecycleComparisonResult, LifecycleEconomicResult, compare_lifecycle_results, evaluate_lifecycle_economics
from facility_engineering_model import FacilityEngineeringObjectModel, SpatialEdge
from models import PlannerAssumptions, SharedNetworkAssumptions
from mrt_carrier_fleet import MrtCarrierFleetResult, audit_native_mrt_carrier_integration, resolve_mrt_carrier_fleet
from multi_isotope_decay import PathwayDecaySummary, evaluate_pathway_decay, required_upstream_activity, retained_fraction
from patient_radionuclide_demand import (
    FacilityDayPatientDemand,
    RadionuclideBatchDemand,
    partition_facility_day_patient_demand,
)
from production_clinical_schedule import (
    MRTCarrierTransportScheduleResult,
    ProductionClinicalScheduleResult,
    ProductionClinicalScenario,
    build_production_clinical_schedule,
)
from stochastic_design_day import ActivityDemandModel, DayType, DesignDaySimulationResult, DesignDayDemandScenario, generate_design_day_demand

if TYPE_CHECKING:
    # Deferred to avoid a circular import: equipment_energy_opex.py transitively
    # imports THIS module (via long_horizon_operational_planning ->
    # multi_cyclotron_authority -> spatial_benchmark -> decision_pipeline).
    # `from __future__ import annotations` makes annotations strings, so this
    # name is only needed for static type-checking, never at runtime.
    from equipment_energy_opex import PathwayEnergyLedgerInput


Pathway = Literal["Conventional", "MRT"]
ProductProfile = Literal["MRT_ENABLED", "CONVENTIONAL_ONLY"]
DeploymentMode = Literal["greenfield", "existing_facility_expansion"]
PrimaryUnmetDemandCause = Literal[
    "NONE",
    "PRODUCTION_SCHEDULE_CAPACITY",
    "PRODUCTION_ACTIVITY_CAPACITY",
    "RELEASE_TOO_LATE_FOR_CLINICAL_DAY",
    "TRANSPORT_RESOURCE_CAPACITY",
    "INJECTION_RESOURCE_CAPACITY",
    "UPTAKE_RESOURCE_CAPACITY",
    "SCANNER_RESOURCE_CAPACITY",
    "CLINICAL_DAY_END_TRUNCATION",
    "ROOM_PROGRAM_CAPACITY",
    "UNKNOWN",
]

# Numerical tolerance (MBq) used throughout planned/realized/final-reconciled EOB
# comparisons and capacity checks. Not a semantic equivalence: planned and realized
# quantities are allowed to legitimately differ; this tolerance only governs
# floating-point noise in equality/capacity comparisons.
RECONCILIATION_TOLERANCE_MBQ = 1e-6

CycleReconciliationStatus = Literal[
    "RECONCILED_FEASIBLE",
    "RECONCILIATION_REQUIRED",
    "CAPACITY_EXCEEDED",
    "PLANNED_ONLY",
    "REALIZED_ONLY",
]


@dataclass(frozen=True)
class CycleEobReconciliationRow:
    """Per-cycle comparison of PLANNED_EOB_REQUIREMENT vs REALIZED_EOB_REQUIREMENT.

    PLANNED: from the demand-layer cycle-relative assignment (provisional admin
    timing, freshest-candidate-cycle assignment; see cycle_relative_production_requirement.py).
    REALIZED: from the actual scheduled production window and the actual patient
    traces produced by the executed production/transport/clinical schedule (same
    authoritative decay engine, applied to the batch the scheduler actually built).
    These represent two different (both legitimate) patient-to-cycle groupings, not
    two measurements of the same group.
    """

    eob_minutes: float
    planned_required_eob_mbq: float
    realized_required_eob_mbq: float
    difference_mbq: float
    relative_difference: float
    calibrated_available_eob_mbq: float | None
    status: CycleReconciliationStatus


@dataclass(frozen=True)
class ProductionRequirementReconciliation:
    """FINAL_RECONCILED_EOB_REQUIREMENT and supporting per-cycle evidence.

    final_reconciled_eob_activity_mbq is the physically authoritative requirement:
    the realized requirement AFTER the bounded schedule-refinement loop
    (`_optimize_batches_for_decay_feasibility`) has converged (no scheduled cycle
    exceeds calibrated capacity). It intentionally is NOT forced to equal the
    planned value.
    """

    planned_eob_activity_mbq: float
    realized_eob_activity_mbq: float
    final_reconciled_eob_activity_mbq: float
    per_cycle: tuple[CycleEobReconciliationRow, ...]
    convergence_status: Literal["CONVERGED", "PRODUCTION_REQUIREMENT_DID_NOT_CONVERGE"]
    iterations_used: int
    tolerance_mbq: float
    max_relative_difference: float


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
    conventional_payload_capacity_doses: int = 5
    mrt_payload_capacity_doses: int = 1
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
    existing_mrt_carriers: int = 0
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
    transport_minutes_source: str = "USER_SUPPLIED_TRANSPORT_TIME"
    energy_ledger_input: PathwayEnergyLedgerInput | None = None
    """Section 7/20: optional calibration-aware schedule-derived electricity
    bridge (equipment_energy_opex.py -> infrastructure_opex.py). None (default)
    preserves the exact prior generic-kWh-only OPEX/NPV behavior."""

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
        if self.conventional_payload_capacity_doses <= 0:
            raise ValueError("conventional_payload_capacity_doses must be at least 1")
        if self.mrt_payload_capacity_doses <= 0:
            raise ValueError("mrt_payload_capacity_doses must be at least 1")
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
        if self.existing_mrt_carriers < 0:
            raise ValueError("existing_mrt_carriers must be non-negative")
        if self.installed_mrt_carriers is not None and self.existing_mrt_carriers > self.installed_mrt_carriers:
            raise ValueError("existing_mrt_carriers cannot exceed installed_mrt_carriers")
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
    mrt: NativePathwayScenario | None = None
    product_profile: ProductProfile = "MRT_ENABLED"
    planner_assumptions: PlannerAssumptions = field(default_factory=PlannerAssumptions)
    shared_network_assumptions: SharedNetworkAssumptions = field(default_factory=SharedNetworkAssumptions)
    day_type: DayType = "typical"
    peak_patient_multiplier: float = 1.0
    peak_activity_multiplier: float = 1.0
    seed: int = 0
    cyclotron_fleet: CyclotronFleet | None = None
    facility_engineering_model: FacilityEngineeringObjectModel | None = None
    clinical_day_start_time_minutes: float = 0.0
    operating_day_minutes: float = 1080.0
    production_start_time_minutes: float = 0.0
    production_horizon_minutes: float | None = None
    batch_target_patients_per_batch: int = 20
    lifecycle_throughput_mode: Literal["actual_completed"] = "actual_completed"
    # RUNTIME MIGRATION (SPEED): canonical STRAIGHT/HORIZONTAL route-time cruise
    # speed override (m/s). When None (default) every legacy caller preserves the
    # heavy PlannerAssumptions.mrt_horizontal_speed_m_per_s (3.0 m/s) unchanged.
    # When set (canonical current-runtime = 10.0 m/s) only the horizontal segment
    # time is affected; vertical (1.5 m/s) / curve / transition are NOT touched.
    mrt_straight_speed_m_per_s_override: float | None = None

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
        if self.production_horizon_minutes is not None and self.production_horizon_minutes < self.production_start_time_minutes:
            raise ValueError("production_horizon_minutes must be at least production_start_time_minutes when provided")
        if self.batch_target_patients_per_batch <= 0:
            raise ValueError("batch_target_patients_per_batch must be at least 1")
        if self.lifecycle_throughput_mode != "actual_completed":
            raise ValueError("lifecycle_throughput_mode must be actual_completed in this build")
        if self.conventional.pathway != "Conventional":
            raise ValueError("conventional pathway config must use Conventional")
        if self.product_profile not in {"MRT_ENABLED", "CONVENTIONAL_ONLY"}:
            raise ValueError("product_profile must be MRT_ENABLED or CONVENTIONAL_ONLY")
        if self.product_profile == "MRT_ENABLED":
            if self.mrt is None:
                raise ValueError("mrt pathway config is required when product_profile is MRT_ENABLED")
            if self.mrt.pathway != "MRT":
                raise ValueError("mrt pathway config must use MRT")
        elif self.mrt is not None and self.mrt.pathway != "MRT":
            raise ValueError("mrt pathway config must use MRT")

        object.__setattr__(self, "target_patients_per_day", int(self.target_patients_per_day))
        object.__setattr__(self, "seed", int(self.seed))

    @property
    def mrt_enabled(self) -> bool:
        return self.product_profile == "MRT_ENABLED"


@dataclass(frozen=True)
class NativeBottleneckSummary:
    resource: str
    utilization_pct: float
    near_binding_resources: tuple[str, ...]
    utilization_by_resource: Mapping[str, float]


@dataclass(frozen=True)
class NativeProductionScheduleDiagnostic:
    production_horizon_start_minute: float
    production_horizon_end_minute: float | None
    required_batch_count: int
    scheduled_batch_count: int
    unscheduled_batch_count: int
    first_unscheduled_batch_id: int | None
    total_scheduled_irradiation_minutes: float
    maximum_parallel_streams_used: int


@dataclass(frozen=True)
class NativeUnmetDemandDiagnostic:
    resource_utilization_bottleneck: str
    primary_unmet_demand_cause: PrimaryUnmetDemandCause
    first_failing_batch_id: int | None
    first_incomplete_patient_id: str | None
    failure_stage: str | None
    failure_time_minutes: float | None
    clinical_end_minute: float
    minutes_beyond_clinical_close: float | None


@dataclass(frozen=True)
class NativeDemandResult:
    simulation: DesignDaySimulationResult
    requested_batch_count_by_radionuclide: Mapping[str, int]
    batch_demands: tuple[RadionuclideBatchDemand, ...]
    patient_ids_by_radionuclide: Mapping[str, tuple[str, ...]]
    fleet_supported_radionuclides: tuple[str, ...]
    trace_id: str
    batch_policy_description: str
    required_administered_activity_mbq_by_radionuclide: Mapping[str, float] = field(default_factory=dict)
    required_eob_activity_mbq_by_radionuclide: Mapping[str, float] = field(default_factory=dict)
    activity_derived_cycle_count_by_radionuclide: Mapping[str, int] = field(default_factory=dict)
    temporal_derived_cycle_count_by_radionuclide: Mapping[str, int] = field(default_factory=dict)
    required_cycle_count_by_radionuclide: Mapping[str, int] = field(default_factory=dict)
    production_requirement_mode: str = "LEGACY_PATIENT_COUNT_HEURISTIC"
    production_requirement_bypasses: tuple[str, ...] = ()
    cycle_relative_requirement_by_radionuclide: Mapping[str, CycleRelativeRequirementResult] = field(default_factory=dict)
    unassigned_patient_ids_by_radionuclide: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    non_authoritative_common_early_eob_activity_mbq_by_radionuclide: Mapping[str, float] = field(default_factory=dict)
    non_authoritative_common_early_eob_implied_cycle_count_by_radionuclide: Mapping[str, int] = field(default_factory=dict)


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
    production_schedule_diagnostic: NativeProductionScheduleDiagnostic
    unmet_demand_diagnostic: NativeUnmetDemandDiagnostic
    primary_unmet_demand_cause: PrimaryUnmetDemandCause
    mrt_carrier_fleet: MrtCarrierFleetResult | None
    decay_summary: PathwayDecaySummary
    activity_capacity_warnings: tuple[str, ...]
    trace_id: str
    production_requirement_reconciliation: ProductionRequirementReconciliation | None = None


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


@dataclass(frozen=True)
class NativeConventionalOnlyResult:
    request: NativeDecisionPipelineScenario
    demand_result: NativeDemandResult
    conventional: NativePathwayResult
    product_profile: ProductProfile
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]


def _trace_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _node_ids_by_object_id(model: FacilityEngineeringObjectModel) -> dict[str, str]:
    node_ids: dict[str, str] = {}
    for node in model.nodes:
        node_ids[node.node_id] = node.node_id
        if node.object_id:
            node_ids[node.object_id] = node.node_id
    return node_ids


def _network_route_path_edges(
    model: FacilityEngineeringObjectModel,
    start_node_id: str,
    end_node_id: str,
) -> tuple[SpatialEdge, ...]:
    adjacency: dict[str, list[tuple[str, SpatialEdge, float]]] = {}
    for edge in model.edges:
        adjacency.setdefault(edge.source_node_id, []).append((edge.destination_node_id, edge, float(edge.length_m)))
        if edge.directionality in {"BIDIRECTIONAL", "ONE_WAY_REVERSE", "UNKNOWN"}:
            adjacency.setdefault(edge.destination_node_id, []).append((edge.source_node_id, edge, float(edge.length_m)))

    frontier: list[tuple[float, str]] = [(0.0, start_node_id)]
    best_cost: dict[str, float] = {start_node_id: 0.0}
    previous_edge: dict[str, SpatialEdge] = {}
    previous_node: dict[str, str] = {}

    while frontier:
        frontier.sort(reverse=True)
        current_cost, current_node = frontier.pop()
        if current_node == end_node_id:
            break
        for neighbor_node, edge, edge_cost in adjacency.get(current_node, []):
            candidate_cost = current_cost + edge_cost
            if neighbor_node not in best_cost or candidate_cost < best_cost[neighbor_node]:
                best_cost[neighbor_node] = candidate_cost
                previous_edge[neighbor_node] = edge
                previous_node[neighbor_node] = current_node
                frontier.append((candidate_cost, neighbor_node))

    if end_node_id not in best_cost:
        raise ValueError(f"No route exists between {start_node_id} and {end_node_id}")

    path_edges: list[SpatialEdge] = []
    cursor = end_node_id
    while cursor != start_node_id:
        edge = previous_edge.get(cursor)
        prior = previous_node.get(cursor)
        if edge is None or prior is None:
            raise ValueError(f"No route exists between {start_node_id} and {end_node_id}")
        path_edges.append(edge)
        cursor = prior
    path_edges.reverse()
    return tuple(path_edges)


def _resolve_conventional_transport_minutes(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
) -> tuple[float, str]:
    if pathway_config.pathway != "Conventional":
        return pathway_config.transport_minutes, pathway_config.transport_minutes_source

    model = request.facility_engineering_model
    if model is None or not model.nodes or not model.edges:
        return pathway_config.transport_minutes, pathway_config.transport_minutes_source

    node_ids = _node_ids_by_object_id(model)
    destination_node_id: str | None = None
    for object_id in model.primary_route_destination_object_ids:
        destination_node_id = node_ids.get(object_id)
        if destination_node_id is not None:
            break
    if destination_node_id is None:
        destination_node_id = model.edges[0].destination_node_id

    origin_node_id = None
    if model.primary_route_origin_object_id is not None:
        origin_node_id = node_ids.get(model.primary_route_origin_object_id)
    if origin_node_id is None:
        origin_node_id = model.edges[0].source_node_id

    path_edges = _network_route_path_edges(model, origin_node_id, destination_node_id)
    route_distance_m = sum(float(edge.length_m) for edge in path_edges)
    vertical_change_m = sum(abs(float(edge.vertical_change_m)) for edge in path_edges)
    horizontal_distance_m = max(0.0, route_distance_m - vertical_change_m)

    assumptions = request.planner_assumptions
    horizontal_minutes = horizontal_distance_m / max(assumptions.manual_transport_speed_m_per_s * 60.0, 1e-12)
    elevator_minutes = 0.0
    if vertical_change_m > 0.0:
        elevator_minutes = (
            assumptions.manual_transport_elevator_wait_minutes
            + assumptions.manual_transport_elevator_loading_minutes
            + vertical_change_m / max(assumptions.manual_transport_elevator_speed_m_per_s * 60.0, 1e-12)
        )

    transport_minutes = (
        assumptions.manual_transport_pickup_minutes
        + horizontal_minutes
        + elevator_minutes
        + assumptions.manual_transport_handoff_minutes
    )

    if model.source_type == "BENCHMARK":
        transport_source = "BENCHMARK_ASSUMPTION"
    elif model.route_distance_source == "USER_SUPPLIED":
        transport_source = "USER_SUPPLIED_DISTANCE_DERIVED"
    elif model.route_geometry_status == "RECONSTRUCTED":
        transport_source = "VERIFIED_GEOMETRY_DERIVED"
    else:
        transport_source = "USER_SUPPLIED_DISTANCE_DERIVED"

    return transport_minutes, transport_source


def _resolve_mrt_transport_minutes(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
) -> tuple[float, str]:
    if pathway_config.pathway != "MRT":
        return pathway_config.transport_minutes, pathway_config.transport_minutes_source

    if pathway_config.transport_minutes_source == "SITE_CALIBRATED":
        return pathway_config.transport_minutes, pathway_config.transport_minutes_source

    model = request.facility_engineering_model
    if model is None or not model.nodes or not model.edges:
        if model is not None and model.source_type == "BENCHMARK":
            return pathway_config.transport_minutes, "BENCHMARK_ASSUMPTION"
        return pathway_config.transport_minutes, pathway_config.transport_minutes_source

    node_ids = _node_ids_by_object_id(model)
    destination_node_id: str | None = None
    for object_id in model.primary_route_destination_object_ids:
        destination_node_id = node_ids.get(object_id)
        if destination_node_id is not None:
            break
    if destination_node_id is None:
        destination_node_id = model.edges[0].destination_node_id

    origin_node_id = None
    if model.primary_route_origin_object_id is not None:
        origin_node_id = node_ids.get(model.primary_route_origin_object_id)
    if origin_node_id is None:
        origin_node_id = model.edges[0].source_node_id

    path_edges = _network_route_path_edges(model, origin_node_id, destination_node_id)
    route_distance_m = sum(float(edge.length_m) for edge in path_edges)
    vertical_distance_m = sum(abs(float(edge.vertical_change_m)) for edge in path_edges)
    horizontal_distance_m = max(0.0, route_distance_m - vertical_distance_m)
    hv_transition_count = sum(2 for edge in path_edges if abs(float(edge.vertical_change_m)) > 0.0)

    assumptions = request.planner_assumptions
    horizontal_seconds = horizontal_distance_m / max(assumptions.mrt_horizontal_speed_m_per_s, 1e-12)
    vertical_seconds = vertical_distance_m / max(assumptions.mrt_vertical_speed_m_per_s, 1e-12)
    transition_seconds = hv_transition_count * assumptions.mrt_transition_time_seconds
    station_seconds = assumptions.mrt_station_loading_time_seconds + assumptions.mrt_station_unloading_time_seconds
    transport_minutes = (horizontal_seconds + vertical_seconds + transition_seconds + station_seconds) / 60.0

    if model.route_geometry_status == "RECONSTRUCTED":
        source = "VERIFIED_GEOMETRY_DERIVED"
    elif model.route_distance_source == "USER_SUPPLIED":
        source = "USER_SUPPLIED_DISTANCE_DERIVED"
    elif model.source_type == "BENCHMARK":
        source = "BENCHMARK_ASSUMPTION"
    else:
        source = pathway_config.transport_minutes_source

    return transport_minutes, source


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


def _batch_policy_description(mode: str) -> str:
    if mode == "REQUIREMENT_DERIVED_WITH_LEGACY_COMPATIBILITY_BYPASS":
        return "PIPELINE BATCH POLICY: cycle-relative requirement, with LEGACY_COMPATIBILITY_BATCH_HEURISTIC_ACTIVE fallback for uncalibrated radionuclides"
    return "PIPELINE BATCH POLICY: cycle-relative requirement (patient EOB computed against the supplying production cycle)"


def _resolved_cyclotron_fleet(request: NativeDecisionPipelineScenario) -> CyclotronFleet:
    if request.cyclotron_fleet is not None:
        return request.cyclotron_fleet
    return build_single_cyclotron_fleet(request.cyclotron_capability)


def _fleet_calibrated_per_cycle_eob_by_radionuclide(fleet: CyclotronFleet) -> dict[str, float]:
    calibrated: dict[str, float] = {}
    for asset in fleet.assets:
        calibrated_map = asset.capability.calibrated_eob_activity_mbq_by_radionuclide or {}
        for radionuclide, value in calibrated_map.items():
            calibrated[radionuclide] = max(calibrated.get(radionuclide, 0.0), float(value))
    return calibrated


def _fleet_min_cycle_minutes_by_radionuclide(fleet: CyclotronFleet) -> dict[str, float]:
    minimums: dict[str, float] = {}
    for asset in fleet.assets:
        for radionuclide, cycle_minutes in asset.capability.production_cycle_minutes_by_radionuclide.items():
            numeric = float(cycle_minutes)
            if numeric <= 0.0:
                continue
            current = minimums.get(radionuclide)
            if current is None or numeric < current:
                minimums[radionuclide] = numeric
    return minimums


def _required_activity_cycle_count(required_eob_activity_mbq: float, per_cycle_eob_activity_mbq: float) -> int:
    required = float(required_eob_activity_mbq)
    available = float(per_cycle_eob_activity_mbq)
    if available <= 0.0:
        raise ValueError("per_cycle_eob_activity_mbq must be greater than zero")
    if required <= 0.0:
        return 0
    return int(math.ceil(required / available))


def _common_early_eob_diagnostic_only(
    *,
    request: NativeDecisionPipelineScenario,
    simulation: DesignDaySimulationResult,
    cycle_minutes_by_radionuclide: Mapping[str, float],
) -> dict[str, float]:
    """NON-AUTHORITATIVE DIAGNOSTIC ONLY.

    Reproduces the previous (now removed) common-early-EOB heuristic that summed
    every patient's decay compensation against a single provisional EOB reference
    time, before any physical production-cycle assignment existed. This routinely
    produced an aggregate requirement many times larger than physically necessary
    because late-administered patients were decay-compensated all the way back to
    the first production cycle of the day. This function is retained only so the
    old and new figures can be compared for regression evidence (see
    `_cycle_relative_requirement_by_radionuclide` for the authoritative path). Its
    output must never feed production scheduling, feasibility, economics,
    throughput, or optimization.
    """
    half_life_lookup = load_radionuclide_half_lives()
    cohort_count = max(1, int(request.planner_assumptions.default_clinical_administration_cohorts_per_day))

    per_radionuclide_patients: dict[str, list[object]] = {}
    for patient in simulation.generated_demand.patients:
        per_radionuclide_patients.setdefault(patient.radionuclide, []).append(patient)

    required_eob_by_radionuclide: dict[str, float] = {}
    for radionuclide, patients in per_radionuclide_patients.items():
        half_life = float(half_life_lookup.get(radionuclide, 1e9))
        cycle_minutes = float(cycle_minutes_by_radionuclide.get(radionuclide, 0.0))
        eob_reference_minutes = float(request.production_start_time_minutes) + max(0.0, cycle_minutes)
        administration_offsets = _deterministic_admin_offsets_minutes(
            len(patients),
            operating_day_minutes=request.operating_day_minutes,
            cohort_count=cohort_count,
        )

        total_required_eob = 0.0
        for patient, injection_time_minutes in zip(patients, administration_offsets):
            elapsed_eob_to_injection = max(0.0, float(injection_time_minutes) - eob_reference_minutes)
            retained = retained_fraction(elapsed_eob_to_injection, half_life)
            retained = max(retained, 1e-12)
            total_required_eob += required_upstream_activity(float(patient.prescribed_activity_mbq), retained)

        required_eob_by_radionuclide[radionuclide] = float(total_required_eob)

    for radionuclide in simulation.scenario.radionuclide_mix:
        required_eob_by_radionuclide.setdefault(radionuclide, 0.0)
    return required_eob_by_radionuclide


def _fleet_release_processing_minutes(
    asset_capability: CyclotronProductionCapability,
    radionuclide: str,
) -> float:
    mapping = asset_capability.release_processing_minutes_by_radionuclide
    if mapping is None:
        return 0.0
    return float(mapping.get(radionuclide, 0.0))


def _cycle_relative_requirement_by_radionuclide(
    *,
    request: NativeDecisionPipelineScenario,
    simulation: DesignDaySimulationResult,
    fleet: CyclotronFleet,
) -> dict[str, CycleRelativeRequirementResult]:
    """AUTHORITATIVE production requirement: patient EOB relative to the supplying cycle.

    For every radionuclide, candidate production cycles are generated from each
    capable fleet asset across the configured production horizon (independent of
    any patient count), and patients are assigned to the freshest candidate cycle
    whose release is early enough to meet their required administration time.
    Cycle activity capacity is enforced with a deterministic, bounded
    reassignment loop. See `cycle_relative_production_requirement.py`.
    """
    half_life_lookup = load_radionuclide_half_lives()
    configured_horizon_end = request.production_horizon_minutes

    per_radionuclide_patients: dict[str, list[object]] = {}
    for patient in simulation.generated_demand.patients:
        per_radionuclide_patients.setdefault(patient.radionuclide, []).append(patient)

    cohort_count = max(1, int(request.planner_assumptions.default_clinical_administration_cohorts_per_day))

    results: dict[str, CycleRelativeRequirementResult] = {}
    for radionuclide, patients in per_radionuclide_patients.items():
        half_life = float(half_life_lookup.get(radionuclide, 1e9))
        administration_offsets = _deterministic_admin_offsets_minutes(
            len(patients),
            operating_day_minutes=request.operating_day_minutes,
            cohort_count=cohort_count,
        )

        candidate_cycles = []
        for asset in fleet.assets:
            capability = asset.capability
            if radionuclide not in capability.supported_radionuclides:
                continue
            calibrated_map = capability.calibrated_eob_activity_mbq_by_radionuclide or {}
            calibrated_capacity = calibrated_map.get(radionuclide)
            if calibrated_capacity is None:
                continue
            cycle_minutes = float(capability.production_cycle_minutes_by_radionuclide[radionuclide])
            release_processing_minutes = _fleet_release_processing_minutes(capability, radionuclide)
            # An unset production horizon means no explicit end time is configured. Bound
            # candidate generation deterministically: far enough to reach the latest
            # patient administration time (so late patients have a fresh candidate cycle
            # available) and with enough distinct cycles for capacity splitting (one
            # cycle per patient in the worst case).
            latest_administration_minutes = max(administration_offsets) if administration_offsets else request.production_start_time_minutes
            horizon_end = (
                configured_horizon_end
                if configured_horizon_end is not None
                else max(
                    request.production_start_time_minutes + cycle_minutes * max(1, len(patients)),
                    latest_administration_minutes + cycle_minutes,
                )
            )
            candidate_cycles.extend(
                generate_candidate_production_cycles(
                    cyclotron_id=asset.cyclotron_id,
                    radionuclide=radionuclide,
                    cycle_minutes=cycle_minutes,
                    calibrated_eob_capacity_mbq=float(calibrated_capacity),
                    release_processing_minutes=release_processing_minutes,
                    production_start_time_minutes=request.production_start_time_minutes,
                    production_horizon_minutes=horizon_end,
                )
            )

        if not candidate_cycles:
            # No calibrated fleet asset for this radionuclide: legacy compatibility bypass handles sizing.
            continue

        prescribed_by_patient_id = {patient.patient_id: float(patient.prescribed_activity_mbq) for patient in patients}
        admin_time_by_patient_id = {
            patient.patient_id: float(offset) for patient, offset in zip(patients, administration_offsets)
        }

        results[radionuclide] = derive_cycle_relative_requirement(
            radionuclide=radionuclide,
            half_life_minutes=half_life,
            patient_ids=[patient.patient_id for patient in patients],
            prescribed_activity_mbq_by_patient_id=prescribed_by_patient_id,
            administration_time_minutes_by_patient_id=admin_time_by_patient_id,
            candidate_cycles=candidate_cycles,
        )

    return results


def _patient_activity_by_radionuclide(simulation: DesignDaySimulationResult) -> dict[str, float]:
    totals: dict[str, float] = {}
    for patient in simulation.generated_demand.patients:
        totals[patient.radionuclide] = totals.get(patient.radionuclide, 0.0) + float(patient.prescribed_activity_mbq)
    return totals


def _deterministic_admin_offsets_minutes(
    patient_count: int,
    operating_day_minutes: float,
    cohort_count: int,
) -> tuple[float, ...]:
    if patient_count <= 0:
        return ()
    if cohort_count <= 1:
        midpoint = float(operating_day_minutes) / 2.0
        return tuple(midpoint for _ in range(patient_count))

    offsets: list[float] = []
    slot = float(operating_day_minutes) / float(cohort_count)
    for index in range(patient_count):
        cohort_index = min(cohort_count - 1, int(index * cohort_count / max(patient_count, 1)))
        offsets.append((cohort_index + 0.5) * slot)
    return tuple(offsets)


def _temporal_segment_count(
    administration_offsets: tuple[float, ...],
    *,
    half_life_minutes: float,
    min_retained_fraction: float,
) -> int:
    if not administration_offsets:
        return 0
    if min_retained_fraction <= 0.0:
        return 1

    max_span_minutes = half_life_minutes * math.log2(1.0 / min_retained_fraction)
    if max_span_minutes <= 0.0:
        return len(administration_offsets)

    sorted_offsets = sorted(float(value) for value in administration_offsets)
    segments = 1
    current_start = sorted_offsets[0]
    for offset in sorted_offsets[1:]:
        if offset - current_start > max_span_minutes:
            segments += 1
            current_start = offset
    return segments


def _derive_requirement_driven_batch_counts(
    *,
    request: NativeDecisionPipelineScenario,
    simulation: DesignDaySimulationResult,
    fleet: CyclotronFleet,
) -> tuple[
    dict[str, int],
    dict[str, float],
    dict[str, float],
    dict[str, int],
    dict[str, int],
    dict[str, int],
    tuple[str, ...],
    str,
    dict[str, CycleRelativeRequirementResult],
    dict[str, tuple[str, ...]],
    dict[str, float],
    dict[str, int],
]:
    required_admin_activity = _patient_activity_by_radionuclide(simulation)
    calibrated_per_cycle = _fleet_calibrated_per_cycle_eob_by_radionuclide(fleet)
    cycle_minutes_by_radionuclide = _fleet_min_cycle_minutes_by_radionuclide(fleet)

    # AUTHORITATIVE: patient EOB requirement relative to the supplying production cycle.
    cycle_relative_results = _cycle_relative_requirement_by_radionuclide(
        request=request,
        simulation=simulation,
        fleet=fleet,
    )
    # NON-AUTHORITATIVE DIAGNOSTIC ONLY: retained for regression comparison, never used for sizing below.
    diagnostic_common_eob_activity = _common_early_eob_diagnostic_only(
        request=request,
        simulation=simulation,
        cycle_minutes_by_radionuclide=cycle_minutes_by_radionuclide,
    )

    supported = set(fleet.fleet_supported_radionuclides)
    unsupported_positive_mix = sorted(
        radionuclide
        for radionuclide, weight in request.radionuclide_mix.items()
        if float(weight) > 0.0 and radionuclide not in supported
    )
    if unsupported_positive_mix:
        affected_patients = sum(
            int(simulation.patient_count_by_radionuclide.get(radionuclide, 0))
            for radionuclide in unsupported_positive_mix
        )
        raise ValueError(
            "RADIONUCLIDE_NOT_SUPPORTED_BY_INSTALLED_FLEET: "
            f"radionuclides={unsupported_positive_mix}, affected_patients={affected_patients}, "
            f"fleet_id={fleet.fleet_id}, assets={tuple(asset.cyclotron_id for asset in fleet.assets)}"
        )

    max_comp = request.planner_assumptions.decay_feasibility_max_compensation_factor
    min_retained = float(request.planner_assumptions.decay_feasibility_min_retained_fraction)
    if max_comp is not None:
        min_retained = max(min_retained, 1.0 / float(max_comp))
    min_retained = min(max(min_retained, 0.0), 1.0)

    cohort_count = max(1, int(request.planner_assumptions.default_clinical_administration_cohorts_per_day))
    half_life_lookup = load_radionuclide_half_lives()

    patients_by_isotope: dict[str, list[object]] = {}
    for patient in simulation.generated_demand.patients:
        patients_by_isotope.setdefault(patient.radionuclide, []).append(patient)

    requested: dict[str, int] = {}
    activity_cycles_by_radionuclide: dict[str, int] = {}
    temporal_cycles_by_radionuclide: dict[str, int] = {}
    required_cycles: dict[str, int] = {}
    required_eob_activity: dict[str, float] = {}
    unassigned_patient_ids_by_radionuclide: dict[str, tuple[str, ...]] = {}
    diagnostic_common_eob_implied_cycle_count: dict[str, int] = {}
    bypasses: list[str] = []

    for radionuclide in simulation.scenario.radionuclide_mix:
        patients = patients_by_isotope.get(radionuclide, [])
        patient_count = len(patients)
        per_cycle_eob = float(calibrated_per_cycle.get(radionuclide, 0.0))
        diagnostic_common_eob = float(diagnostic_common_eob_activity.get(radionuclide, 0.0))
        diagnostic_common_eob_implied_cycle_count[radionuclide] = (
            _required_activity_cycle_count(diagnostic_common_eob, per_cycle_eob) if per_cycle_eob > 0.0 else 0
        )

        if patient_count == 0:
            requested[radionuclide] = 0
            activity_cycles_by_radionuclide[radionuclide] = 0
            temporal_cycles_by_radionuclide[radionuclide] = 0
            required_cycles[radionuclide] = 0
            required_eob_activity[radionuclide] = 0.0
            unassigned_patient_ids_by_radionuclide[radionuclide] = ()
            continue

        administration_offsets = _deterministic_admin_offsets_minutes(
            patient_count,
            operating_day_minutes=request.operating_day_minutes,
            cohort_count=cohort_count,
        )
        half_life = float(half_life_lookup.get(radionuclide, 1e9))
        temporal_segments = _temporal_segment_count(
            administration_offsets,
            half_life_minutes=half_life,
            min_retained_fraction=min_retained,
        )

        cycle_relative_result = cycle_relative_results.get(radionuclide)
        if cycle_relative_result is not None:
            # Pure capacity-driven diagnostic: how many cycles would the authoritative
            # (correct, cycle-relative) aggregate activity alone require, ignoring the
            # distinct timing groups actually used. This is a lower bound, reported
            # separately from the real physically-assigned cycle count below.
            activity_cycles = max(
                1,
                _required_activity_cycle_count(cycle_relative_result.total_required_eob_activity_mbq, per_cycle_eob)
                if per_cycle_eob > 0.0
                else cycle_relative_result.required_cycle_count,
            )
            cycles = max(cycle_relative_result.required_cycle_count, activity_cycles, temporal_segments)
            required_eob_activity[radionuclide] = cycle_relative_result.total_required_eob_activity_mbq
            unassigned_patient_ids_by_radionuclide[radionuclide] = cycle_relative_result.unassigned_patient_ids
        else:
            legacy_cycles = max(1, math.ceil(patient_count / float(request.batch_target_patients_per_batch)))
            activity_cycles = legacy_cycles
            cycles = max(legacy_cycles, temporal_segments)
            required_eob_activity[radionuclide] = 0.0
            unassigned_patient_ids_by_radionuclide[radionuclide] = ()
            bypasses.append(
                "LEGACY_COMPATIBILITY_BATCH_HEURISTIC_ACTIVE: "
                f"radionuclide={radionuclide}, reason=missing_calibrated_per_cycle_eob_activity"
            )

        requested[radionuclide] = int(cycles)
        activity_cycles_by_radionuclide[radionuclide] = int(activity_cycles)
        temporal_cycles_by_radionuclide[radionuclide] = int(max(1, temporal_segments))
        required_cycles[radionuclide] = int(cycles)

    mode = "REQUIREMENT_DERIVED_ACTIVITY_AND_TIME" if not bypasses else "REQUIREMENT_DERIVED_WITH_LEGACY_COMPATIBILITY_BYPASS"
    return (
        requested,
        required_admin_activity,
        required_eob_activity,
        activity_cycles_by_radionuclide,
        temporal_cycles_by_radionuclide,
        required_cycles,
        tuple(dict.fromkeys(bypasses)),
        mode,
        cycle_relative_results,
        unassigned_patient_ids_by_radionuclide,
        diagnostic_common_eob_activity,
        diagnostic_common_eob_implied_cycle_count,
    )


def _patient_ids_by_radionuclide(facility_day: FacilityDayPatientDemand) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for patient in facility_day.patients:
        grouped.setdefault(patient.radionuclide, []).append(patient.patient_id)
    return {radionuclide: tuple(patient_ids) for radionuclide, patient_ids in grouped.items()}


def _build_demand_result(request: NativeDecisionPipelineScenario) -> NativeDemandResult:
    fleet = _resolved_cyclotron_fleet(request)
    try:
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
    except ValueError as exc:
        if "unavailable in the installed cyclotron fleet" in str(exc):
            raise ValueError(
                "RADIONUCLIDE_NOT_SUPPORTED_BY_INSTALLED_FLEET: "
                f"{exc}"
            ) from exc
        raise
    simulation = generate_design_day_demand(scenario)
    (
        requested,
        required_admin_activity,
        required_eob_activity,
        activity_cycles,
        temporal_cycles,
        required_cycles,
        bypasses,
        requirement_mode,
        cycle_relative_results,
        unassigned_patient_ids_by_radionuclide,
        diagnostic_common_eob_activity,
        diagnostic_common_eob_implied_cycle_count,
    ) = _derive_requirement_driven_batch_counts(
        request=request,
        simulation=simulation,
        fleet=fleet,
    )
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
            "required_administered_activity_mbq_by_radionuclide": required_admin_activity,
            "required_eob_activity_mbq_by_radionuclide": required_eob_activity,
            "activity_derived_cycle_count_by_radionuclide": activity_cycles,
            "temporal_derived_cycle_count_by_radionuclide": temporal_cycles,
            "required_cycle_count_by_radionuclide": required_cycles,
            "production_requirement_mode": requirement_mode,
            "production_requirement_bypasses": bypasses,
        }
    )
    return NativeDemandResult(
        simulation=simulation,
        requested_batch_count_by_radionuclide=requested,
        batch_demands=batch_demands,
        patient_ids_by_radionuclide=_patient_ids_by_radionuclide(simulation.generated_demand),
        fleet_supported_radionuclides=fleet.fleet_supported_radionuclides,
        trace_id=demand_trace_id,
        batch_policy_description=_batch_policy_description(requirement_mode),
        required_administered_activity_mbq_by_radionuclide=required_admin_activity,
        required_eob_activity_mbq_by_radionuclide=required_eob_activity,
        activity_derived_cycle_count_by_radionuclide=activity_cycles,
        temporal_derived_cycle_count_by_radionuclide=temporal_cycles,
        required_cycle_count_by_radionuclide=required_cycles,
        production_requirement_mode=requirement_mode,
        production_requirement_bypasses=bypasses,
        cycle_relative_requirement_by_radionuclide=cycle_relative_results,
        unassigned_patient_ids_by_radionuclide=unassigned_patient_ids_by_radionuclide,
        non_authoritative_common_early_eob_activity_mbq_by_radionuclide=diagnostic_common_eob_activity,
        non_authoritative_common_early_eob_implied_cycle_count_by_radionuclide=diagnostic_common_eob_implied_cycle_count,
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
        installed_mrt_carriers=pathway_config.installed_mrt_carriers or 0,
        existing_mrt_carriers=pathway_config.existing_mrt_carriers,
        installed_guideway_length_m=pathway_config.installed_guideway_length_m,
        existing_guideway_length_m=pathway_config.existing_guideway_length_m,
        guideway_capex_per_m=(
            pathway_config.guideway_capex_per_m
            if pathway_config.guideway_capex_per_m > 0.0
            else request.planner_assumptions.mrt_guideway_capex_per_m
        ),
        mrt_carrier_capex_per_unit=request.planner_assumptions.mrt_carrier_capex_per_installed_unit,
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
        installed_mrt_carriers=pathway_config.installed_mrt_carriers or 0,
        operated_mrt_carriers=pathway_config.operated_mrt_carriers or 0,
        operated_guideway_length_m=pathway_config.operated_guideway_length_m,
        operated_vertical_transitions=pathway_config.operated_vertical_transitions,
        operated_building_connections=pathway_config.operated_building_connections,
        operating_days_per_year=request.planner_assumptions.operating_days_per_year,
        annual_conventional_transport_opex=pathway_config.annual_conventional_transport_opex,
        conventional_transport_staff_fte=pathway_config.conventional_transport_staff_fte,
        conventional_transport_staff_loaded_cost_per_fte=pathway_config.conventional_transport_staff_loaded_cost_per_fte,
        mrt_base_annual_opex_per_unit=pathway_config.mrt_base_annual_opex_per_unit,
        guideway_maintenance_per_m_year=pathway_config.guideway_maintenance_per_m_year,
        guideway_capex_per_m=(
            pathway_config.guideway_capex_per_m
            if pathway_config.guideway_capex_per_m > 0.0
            else request.planner_assumptions.mrt_guideway_capex_per_m
        ),
        vertical_transition_annual_opex_per_unit=pathway_config.vertical_transition_annual_opex_per_unit,
        building_connection_annual_opex_per_unit=pathway_config.building_connection_annual_opex_per_unit,
        mrt_carrier_allocated_electricity_opex_per_operated_unit_year=request.planner_assumptions.mrt_carrier_allocated_electricity_opex_per_operated_unit_year,
        mrt_carrier_maintenance_opex_per_installed_unit_year=request.planner_assumptions.mrt_carrier_maintenance_opex_per_installed_unit_year,
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
        energy_ledger_input=pathway_config.energy_ledger_input,
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
    finalized_cycle_assignment_by_radionuclide: Mapping[str, CycleRelativeRequirementResult] | None = None,
) -> ProductionClinicalScheduleResult:
    fleet = _resolved_cyclotron_fleet(request)
    schedule = ProductionClinicalScenario(
        facility_day_demand=facility_day_demand,
        requested_batch_count_by_radionuclide=requested_batch_count_by_radionuclide,
        cyclotron_fleet=fleet,
        clinical_day_start_minute=request.clinical_day_start_time_minutes,
        transport_minutes=pathway_config.transport_minutes,
        injection_service_minutes=request.planner_assumptions.injection_cycle_min,
        uptake_minutes=request.planner_assumptions.uptake_cycle_min,
        scanner_service_minutes=request.planner_assumptions.scanner_cycle_min,
        injection_resources=pathway_config.injection_resources,
        uptake_resources=pathway_config.uptake_resources,
        scanners=pathway_config.scanners,
        distribution_concurrency=pathway_config.distribution_concurrency,
        operating_day_minutes=request.operating_day_minutes,
        production_start_time_minutes=request.production_start_time_minutes,
        production_horizon_minutes=request.production_horizon_minutes,
        pathway=pathway_config.pathway,
        facility_engineering_model=request.facility_engineering_model,
        planner_assumptions=request.planner_assumptions,
        mrt_operated_carriers=(pathway_config.operated_mrt_carriers if pathway_config.pathway == "MRT" else None),
        transport_minutes_source=pathway_config.transport_minutes_source,
        conventional_payload_capacity_doses=pathway_config.conventional_payload_capacity_doses,
        mrt_payload_capacity_doses=pathway_config.mrt_payload_capacity_doses,
        finalized_cycle_assignment_by_radionuclide=finalized_cycle_assignment_by_radionuclide,
        mrt_straight_speed_m_per_s_override=request.mrt_straight_speed_m_per_s_override,
    )
    return build_production_clinical_schedule(schedule)


def _build_production_requirement_reconciliation(
    *,
    demand_result: NativeDemandResult,
    decay_summary: PathwayDecaySummary,
    fleet: CyclotronFleet,
    iterations_used: int,
    converged: bool,
) -> ProductionRequirementReconciliation:
    """Reconcile PLANNED_EOB_REQUIREMENT (demand-layer, cycle_relative_requirement_by_radionuclide)
    against REALIZED_EOB_REQUIREMENT (actual scheduled production windows and patient traces),
    per production cycle, and establish FINAL_RECONCILED_EOB_REQUIREMENT.
    """
    calibrated = _fleet_calibrated_per_cycle_eob_by_radionuclide(fleet)

    planned_by_key: dict[tuple[float, str], float] = {}
    for radionuclide, result in demand_result.cycle_relative_requirement_by_radionuclide.items():
        for usage in result.cycle_usages:
            key = (round(usage.eob_minutes, 6), radionuclide)
            planned_by_key[key] = planned_by_key.get(key, 0.0) + usage.required_eob_activity_mbq

    realized_by_key: dict[tuple[float, str], float] = {}
    for trace in decay_summary.patient_traces:
        key = (round(trace.production_window_end_time_minutes, 6), trace.radionuclide)
        realized_by_key[key] = realized_by_key.get(key, 0.0) + float(trace.required_upstream_activity_for_prescribed_mbq)

    rows: list[CycleEobReconciliationRow] = []
    for key in sorted(set(planned_by_key) | set(realized_by_key)):
        eob_minutes, radionuclide = key
        planned = planned_by_key.get(key, 0.0)
        realized = realized_by_key.get(key)
        available = calibrated.get(radionuclide)

        if realized is None:
            rows.append(
                CycleEobReconciliationRow(
                    eob_minutes=eob_minutes,
                    planned_required_eob_mbq=planned,
                    realized_required_eob_mbq=0.0,
                    difference_mbq=0.0,
                    relative_difference=0.0,
                    calibrated_available_eob_mbq=available,
                    status="PLANNED_ONLY",
                )
            )
            continue

        difference = realized - planned
        relative = abs(difference) / max(realized, RECONCILIATION_TOLERANCE_MBQ)
        # Capacity violation is checked first: exceeding calibrated per-cycle capacity is
        # the physically critical condition regardless of whether a matching planned
        # entry exists for this cycle.
        if available is not None and realized > available + RECONCILIATION_TOLERANCE_MBQ:
            status: CycleReconciliationStatus = "CAPACITY_EXCEEDED"
        elif key not in planned_by_key:
            status = "REALIZED_ONLY"
        elif relative > RECONCILIATION_TOLERANCE_MBQ:
            status = "RECONCILIATION_REQUIRED"
        else:
            status = "RECONCILED_FEASIBLE"

        rows.append(
            CycleEobReconciliationRow(
                eob_minutes=eob_minutes,
                planned_required_eob_mbq=planned,
                realized_required_eob_mbq=realized,
                difference_mbq=difference,
                relative_difference=relative,
                calibrated_available_eob_mbq=available,
                status=status,
            )
        )

    planned_total = sum(planned_by_key.values())
    realized_total = sum(realized_by_key.values())
    max_relative_difference = max((row.relative_difference for row in rows), default=0.0)

    return ProductionRequirementReconciliation(
        planned_eob_activity_mbq=planned_total,
        realized_eob_activity_mbq=realized_total,
        # FINAL_RECONCILED_EOB_REQUIREMENT: the realized requirement of the schedule that
        # the bounded refinement loop actually converged on (never the planned value).
        final_reconciled_eob_activity_mbq=realized_total,
        per_cycle=tuple(rows),
        convergence_status="CONVERGED" if converged else "PRODUCTION_REQUIREMENT_DID_NOT_CONVERGE",
        iterations_used=iterations_used,
        tolerance_mbq=RECONCILIATION_TOLERANCE_MBQ,
        max_relative_difference=max_relative_difference,
    )


def _scheduled_cycle_capacity_violations_by_isotope(
    decay_summary: PathwayDecaySummary,
    fleet: CyclotronFleet,
) -> dict[str, int]:
    """Bounded convergence check: does any ACTUALLY SCHEDULED cycle's real aggregate
    required EOB activity exceed its calibrated per-cycle capacity? The cycle-relative
    sizing step assumes freshest-fit placement; the downstream scheduler places batches
    back-to-back from production start, which can differ. This closes that loop by
    triggering an extra required cycle for the affected radionuclide when needed.
    """
    calibrated = _fleet_calibrated_per_cycle_eob_by_radionuclide(fleet)
    totals_by_batch: dict[tuple[int, str], float] = {}
    for trace in decay_summary.patient_traces:
        key = (trace.batch_id, trace.radionuclide)
        totals_by_batch[key] = totals_by_batch.get(key, 0.0) + float(trace.required_upstream_activity_for_prescribed_mbq)

    violations: dict[str, int] = {}
    for (batch_id, radionuclide), total in totals_by_batch.items():
        capacity = calibrated.get(radionuclide, 0.0)
        if capacity > 0.0 and total > capacity + 1e-6:
            violations[radionuclide] = violations.get(radionuclide, 0) + 1
    return violations


def _optimize_batches_for_decay_feasibility(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
    demand_result: NativeDemandResult,
) -> tuple[ProductionClinicalScheduleResult, PathwayDecaySummary, int, bool]:
    minimum_retained, max_compensation = _decay_feasibility_guard(request)
    requested = {key: int(value) for key, value in demand_result.requested_batch_count_by_radionuclide.items()}
    max_batches_by_isotope = {
        isotope: max(1, int(count))
        for isotope, count in demand_result.simulation.patient_count_by_radionuclide.items()
        if int(count) > 0
    }
    fleet = _resolved_cyclotron_fleet(request)

    def _scheduled_patients_for(schedule: ProductionClinicalScheduleResult):
        scheduled_patient_ids = {
            patient_id
            for batch in schedule.scheduled_batch_demands
            for patient_id in batch.patient_ids
        }
        return tuple(
            patient
            for patient in demand_result.simulation.generated_demand.patients
            if patient.patient_id in scheduled_patient_ids
        )

    seen: set[tuple[tuple[str, int], ...]] = set()
    best_schedule = _build_schedule_for_batches(
        request,
        pathway_config,
        demand_result.simulation.generated_demand,
        requested,
        demand_result.cycle_relative_requirement_by_radionuclide,
    )
    best_decay = evaluate_pathway_decay(
        pathway=pathway_config.pathway,
        generated_patients=_scheduled_patients_for(best_schedule),
        patient_traces=best_schedule.patient_traces,
        min_retained_fraction_for_feasibility=minimum_retained,
        max_decay_compensation_factor=max_compensation,
    )
    baseline_completed_patients = best_schedule.clinical_schedule.completed_patients

    iterations_used = 0
    for _ in range(64):
        iterations_used += 1
        key = tuple(sorted(requested.items()))
        if key in seen:
            break
        seen.add(key)

        schedule = _build_schedule_for_batches(
            request,
            pathway_config,
            demand_result.simulation.generated_demand,
            requested,
            demand_result.cycle_relative_requirement_by_radionuclide,
        )
        decay_summary = evaluate_pathway_decay(
            pathway=pathway_config.pathway,
            generated_patients=_scheduled_patients_for(schedule),
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

        capacity_violations = _scheduled_cycle_capacity_violations_by_isotope(decay_summary, fleet)
        if decay_summary.decay_infeasible_patient_count == 0 and not capacity_violations:
            return schedule, decay_summary, iterations_used, True

        increments = 0
        for isotope, count in sorted(decay_summary.decay_infeasible_by_isotope.items(), key=lambda item: item[1], reverse=True):
            if count <= 0:
                continue
            current = requested.get(isotope, 0)
            maximum = max_batches_by_isotope.get(isotope, current)
            if current < maximum:
                requested[isotope] = current + 1
                increments += 1

        for isotope in sorted(capacity_violations):
            current = requested.get(isotope, 0)
            maximum = max_batches_by_isotope.get(isotope, current)
            if current < maximum:
                requested[isotope] = current + 1
                increments += 1

        if increments == 0:
            break

    return best_schedule, best_decay, iterations_used, False


def _production_schedule_diagnostic(
    request: NativeDecisionPipelineScenario,
    production_result: ProductionClinicalScheduleResult,
) -> NativeProductionScheduleDiagnostic:
    first_unscheduled = (
        production_result.unscheduled_batch_demands[0].batch_id
        if production_result.unscheduled_batch_demands
        else None
    )
    return NativeProductionScheduleDiagnostic(
        production_horizon_start_minute=request.production_start_time_minutes,
        production_horizon_end_minute=request.production_horizon_minutes,
        required_batch_count=len(production_result.batch_demands),
        scheduled_batch_count=len(production_result.scheduled_batch_demands),
        unscheduled_batch_count=len(production_result.unscheduled_batch_demands),
        first_unscheduled_batch_id=first_unscheduled,
        total_scheduled_irradiation_minutes=production_result.production_schedule.total_elapsed_production_minutes,
        maximum_parallel_streams_used=production_result.production_schedule.max_simultaneous_streams_used,
    )


def _clinical_day_end_minute(request: NativeDecisionPipelineScenario) -> float:
    return request.clinical_day_start_time_minutes + request.operating_day_minutes


def _unmet_demand_diagnostic(
    request: NativeDecisionPipelineScenario,
    production_result: ProductionClinicalScheduleResult,
    production_feasible_patient_ids: set[str],
    decay_summary: PathwayDecaySummary,
    bottleneck: NativeBottleneckSummary,
) -> NativeUnmetDemandDiagnostic:
    clinical_end_minute = _clinical_day_end_minute(request)

    if production_result.unscheduled_batch_demands:
        first_batch = production_result.unscheduled_batch_demands[0]
        first_patient_id = first_batch.patient_ids[0] if first_batch.patient_ids else None
        return NativeUnmetDemandDiagnostic(
            resource_utilization_bottleneck=bottleneck.resource,
            primary_unmet_demand_cause="PRODUCTION_SCHEDULE_CAPACITY",
            first_failing_batch_id=first_batch.batch_id,
            first_incomplete_patient_id=first_patient_id,
            failure_stage="production_schedule",
            failure_time_minutes=request.production_horizon_minutes,
            clinical_end_minute=clinical_end_minute,
            minutes_beyond_clinical_close=None,
        )

    for trace in sorted(decay_summary.patient_traces, key=lambda item: (item.batch_id, item.patient_id)):
        if trace.decay_feasible and trace.patient_id not in production_feasible_patient_ids:
            return NativeUnmetDemandDiagnostic(
                resource_utilization_bottleneck=bottleneck.resource,
                primary_unmet_demand_cause="PRODUCTION_ACTIVITY_CAPACITY",
                first_failing_batch_id=trace.batch_id,
                first_incomplete_patient_id=trace.patient_id,
                failure_stage="production_activity_capacity",
                failure_time_minutes=trace.production_window_end_time_minutes,
                clinical_end_minute=clinical_end_minute,
                minutes_beyond_clinical_close=None,
            )

    for trace in sorted(production_result.patient_traces, key=lambda item: (item.batch_id, item.patient_id)):
        if trace.completed_within_operating_day:
            continue
        minutes_beyond = max(0.0, trace.scan_end - clinical_end_minute)
        if trace.batch_release_time_minutes > clinical_end_minute:
            cause: PrimaryUnmetDemandCause = "RELEASE_TOO_LATE_FOR_CLINICAL_DAY"
            stage = "release"
            failure_time = trace.batch_release_time_minutes
            minutes_beyond = trace.batch_release_time_minutes - clinical_end_minute
        else:
            cause = "CLINICAL_DAY_END_TRUNCATION"
            stage = "scan_completion"
            failure_time = trace.scan_end
        return NativeUnmetDemandDiagnostic(
            resource_utilization_bottleneck=bottleneck.resource,
            primary_unmet_demand_cause=cause,
            first_failing_batch_id=trace.batch_id,
            first_incomplete_patient_id=trace.patient_id,
            failure_stage=stage,
            failure_time_minutes=failure_time,
            clinical_end_minute=clinical_end_minute,
            minutes_beyond_clinical_close=minutes_beyond,
        )

    return NativeUnmetDemandDiagnostic(
        resource_utilization_bottleneck=bottleneck.resource,
        primary_unmet_demand_cause="NONE",
        first_failing_batch_id=None,
        first_incomplete_patient_id=None,
        failure_stage=None,
        failure_time_minutes=None,
        clinical_end_minute=clinical_end_minute,
        minutes_beyond_clinical_close=None,
    )


def _build_operational_result(
    request: NativeDecisionPipelineScenario,
    pathway_config: NativePathwayScenario,
    demand_result: NativeDemandResult,
) -> tuple[ProductionClinicalScheduleResult, NativeOperationalResult]:
    production_result, decay_summary, reconciliation_iterations_used, reconciliation_converged = _optimize_batches_for_decay_feasibility(
        request, pathway_config, demand_result
    )
    fleet_for_reconciliation = _resolved_cyclotron_fleet(request)
    production_requirement_reconciliation = _build_production_requirement_reconciliation(
        demand_result=demand_result,
        decay_summary=decay_summary,
        fleet=fleet_for_reconciliation,
        iterations_used=reconciliation_iterations_used,
        converged=reconciliation_converged,
    )
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
    if pathway_config.pathway == "MRT" and isinstance(production_result.transport_schedule, MRTCarrierTransportScheduleResult):
        carrier_schedule = production_result.transport_schedule
        carrier_pressure = (
            carrier_schedule.average_carrier_queue_wait_minutes > 0.0
            or carrier_schedule.carrier_utilization_pct >= 95.0
        )
        if carrier_pressure:
            utilization = dict(bottleneck.utilization_by_resource)
            utilization["carrier_transport"] = carrier_schedule.carrier_utilization_pct
            bottleneck = NativeBottleneckSummary(
                resource="carrier_transport",
                utilization_pct=carrier_schedule.carrier_utilization_pct,
                near_binding_resources=tuple(
                    sorted(
                        name
                        for name, value in utilization.items()
                        if carrier_schedule.carrier_utilization_pct - value <= 5.0
                    )
                ),
                utilization_by_resource=utilization,
            )
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
    production_schedule_diagnostic = _production_schedule_diagnostic(request, production_result)
    unmet_demand_diagnostic = _unmet_demand_diagnostic(
        request,
        production_result,
        production_feasible_patient_ids,
        decay_summary,
        bottleneck,
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
            "production_schedule_diagnostic": production_schedule_diagnostic.__dict__,
            "primary_unmet_demand_cause": unmet_demand_diagnostic.primary_unmet_demand_cause,
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
        production_schedule_diagnostic=production_schedule_diagnostic,
        unmet_demand_diagnostic=unmet_demand_diagnostic,
        primary_unmet_demand_cause=unmet_demand_diagnostic.primary_unmet_demand_cause,
        mrt_carrier_fleet=mrt_carrier_fleet,
        decay_summary=decay_summary,
        activity_capacity_warnings=activity_capacity_warnings,
        trace_id=operational_trace_id,
        production_requirement_reconciliation=production_requirement_reconciliation,
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
        "batch_target_patients_per_batch (patient-count batching) is used only as a LEGACY_COMPATIBILITY "
        "fallback when a fleet asset lacks calibrated per-cycle EOB activity; the authoritative production "
        "requirement is otherwise cycle-relative (patient EOB computed against the specific supplying cycle).",
        "No spatially derived guideway length.",
        "No floor-area/floor-count resource placement.",
        "MRT carrier economics and route timing use provisional planning assumptions and should be replaced with validated site-calibrated parameters.",
        "Decay physics is natively integrated, but direct monetization of activity loss requires an authoritative isotope-production cost model.",
        "No detailed MRT energy physics.",
        "No demand-driven staffing inference.",
        "Cyclotron manufacturer/model library is not implemented as a permanent repository object.",
        "Model-specific beam energy, target yields, target-change constraints, and synthesis/QC yield curves are not represented in this native build.",
    )


def _warnings(request: NativeDecisionPipelineScenario, pathway_config: NativePathwayScenario) -> tuple[str, ...]:
    notes: list[str] = []
    if pathway_config.pathway == "MRT":
        if pathway_config.installed_guideway_length_m <= 0.0:
            notes.append("MRT guideway length must be provided explicitly; this build does not derive it from geometry.")
        notes.append(
            "MRT carrier count is modeled as a physical fleet through operated_mrt_carriers; transport queueing and utilization now use MRT carrier scheduling semantics."
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
    resolved_transport_minutes, transport_source = _resolve_conventional_transport_minutes(request, pathway_config)
    if pathway_config.pathway == "MRT":
        resolved_transport_minutes, transport_source = _resolve_mrt_transport_minutes(request, pathway_config)

    if (
        resolved_transport_minutes != pathway_config.transport_minutes
        or transport_source != pathway_config.transport_minutes_source
    ):
        pathway_config = replace(
            pathway_config,
            transport_minutes=resolved_transport_minutes,
            transport_minutes_source=transport_source,
        )

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

    legacy_batching_notes = (
        (
            f"LEGACY_COMPATIBILITY_BATCH_HEURISTIC_ACTIVE for this run (uses explicit batch_target_patients_per_batch="
            f"{request.batch_target_patients_per_batch}): {'; '.join(demand_result.production_requirement_bypasses)}",
        )
        if demand_result.production_requirement_bypasses
        else ()
    )

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
        + legacy_batching_notes
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
    if pathway_config is None:
        raise ValueError("Requested pathway is not configured in this scenario")
    return _build_pathway_result(request, pathway_config, demand_result)


def run_native_conventional_only_pipeline(request: NativeDecisionPipelineScenario) -> NativeConventionalOnlyResult:
    if request.product_profile != "CONVENTIONAL_ONLY":
        raise ValueError("run_native_conventional_only_pipeline requires product_profile=CONVENTIONAL_ONLY")

    demand_result = _build_demand_result(request)
    conventional_result = _build_pathway_result(request, request.conventional, demand_result)
    limitations = _limitations()
    warnings = tuple(dict.fromkeys(conventional_result.warnings + (limitations[0],)))

    return NativeConventionalOnlyResult(
        request=request,
        demand_result=demand_result,
        conventional=conventional_result,
        product_profile=request.product_profile,
        warnings=warnings,
        limitations=limitations,
    )


def run_native_decision_pipeline(request: NativeDecisionPipelineScenario) -> NativeDecisionComparisonResult:
    if not request.mrt_enabled:
        raise ValueError("MRT pathway is disabled in this scenario; use run_native_conventional_only_pipeline")

    if request.mrt is None:
        raise ValueError("MRT pathway config is required for run_native_decision_pipeline")

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

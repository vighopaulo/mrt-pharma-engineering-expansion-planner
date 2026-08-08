from __future__ import annotations

from dataclasses import dataclass, field
import math

from engineering import retention, room_capacity, scanner_capacity
from finance import incremental_financials
from models import ConventionalPlan, PlannerAssumptions, PlannerInputs
from optimization import conventional


@dataclass(frozen=True)
class PathwayBudgetResult:
    pathway: str
    budget: float
    capex_used: float
    unused_budget: float
    achieved_capacity_per_day: float
    increase_above_current_capacity_per_day: float
    patients_gained_per_1m_capex: float
    capex_per_incremental_patient_per_day: float
    revenue_generating_throughput_per_day: float
    reserve_capacity_above_expected_demand_per_day: float
    annual_revenue: float
    retained_activity_pct: float
    production_expansion_pct: float
    gross_required_doses_per_day: float
    binding_constraint: str
    additional_scanners: int
    new_rooms_constructed: int
    existing_rooms_renovated: int
    existing_rooms_connected_to_mrt: int
    guideway_segments: int
    endpoints: int
    vertical_transitions: int
    building_connections: int
    backbone_charged: bool
    capex_ledger: list[dict[str, object]]
    npv: float = 0.0
    roi_pct: float = 0.0
    payback_years: float = math.inf
    operating_day_feasible: bool = True


@dataclass(frozen=True)
class EqualBudgetResult:
    common_budget: float
    budget_source: str
    conventional: PathwayBudgetResult
    mrt: PathwayBudgetResult
    annual_revenue_difference_mrt_minus_conventional: float


@dataclass(frozen=True)
class MultiBatchPathwayResult:
    pathway: str
    budget: float
    batches_per_day: int
    operating_hours_per_day: float
    transport_minutes: float
    useful_service_window_per_batch_minutes: float
    achieved_capacity_per_day: float
    increase_above_current_capacity_per_day: float
    patients_gained_per_1m_capex: float
    capex_per_incremental_patient_per_day: float
    revenue_generating_throughput_per_day: float
    capex_used: float
    unused_budget: float
    reserve_capacity_above_expected_demand_per_day: float
    annual_incremental_batch_opex: float
    total_annual_modelled_opex: float
    annual_net_operating_contribution: float
    annual_revenue: float
    retained_activity_pct: float
    production_expansion_pct: float
    gross_required_doses_per_day: float
    gross_required_doses_per_batch: float
    patients_per_batch: float
    scanner_hours_used_per_day: float
    scanner_hours_used_per_batch: float
    injection_room_hours_used_per_day: float
    injection_room_hours_used_per_batch: float
    uptake_room_hours_used_per_day: float
    uptake_room_hours_used_per_batch: float
    binding_constraint: str
    additional_scanners: int
    new_rooms_constructed: int
    existing_rooms_renovated: int
    existing_rooms_connected_to_mrt: int
    guideway_segments: int
    endpoints: int
    vertical_transitions: int
    building_connections: int
    backbone_charged: bool
    capex_ledger: list[dict[str, object]]
    production_expansion_capex_charged: bool = False
    gross_production_doses_per_day_at_release: float = 0.0
    gross_production_doses_per_batch_at_release: float = 0.0
    transport_only_retention_fraction: float = 0.0
    administration_retention_fraction: float = 0.0
    transport_only_gross_required_doses_per_day: float = 0.0
    transport_only_gross_required_doses_per_batch: float = 0.0
    administration_cohorts_per_day: int = 1
    prescribed_activity_mbq_per_patient: float = 0.0
    activity_required_at_administration_mbq_per_day: float = 0.0
    activity_required_at_release_mbq_per_day: float = 0.0
    activity_required_at_eob_mbq_per_day: float = 0.0
    activity_decay_loss_post_release_mbq_per_day: float = 0.0
    synthesis_yield_fraction: float = 1.0
    synthesis_processing_time_min: float = 0.0
    synthesis_retention_fraction: float = 1.0
    cyclotron_activity_capacity_mbq_per_day: float = 0.0
    cyclotron_activity_capacity_status: str = "not_calibrated"
    cyclotron_utilization_pct: float = 0.0
    cyclotron_headroom_mbq_per_day: float = 0.0
    production_upgrade_required: bool = False
    legacy_production_capacity_assumption_status: str = "legacy_not_mapped"
    usable_doses_per_day: float = 0.0
    batch_release_times_minutes: list[float] = field(default_factory=list)
    per_batch_mean_administration_wait_minutes: list[float] = field(default_factory=list)
    per_batch_decay_time_minutes: list[float] = field(default_factory=list)
    per_batch_usable_doses: list[float] = field(default_factory=list)
    per_batch_completed_patients: list[float] = field(default_factory=list)
    per_batch_queue_wait_minutes: list[float] = field(default_factory=list)
    per_batch_transport_minutes: list[float] = field(default_factory=list)
    binding_constraint_calibration: str = "engineering_assumption"
    annual_incremental_opex: float = 0.0
    npv: float = 0.0
    roi_pct: float = 0.0
    payback_years: float = math.inf
    operating_day_feasible: bool = True
    weighted_score: float = 0.0
    score_components: dict[str, float] = field(default_factory=dict)
    score_weights: dict[str, float] = field(default_factory=dict)
    decision_view: str = ""


@dataclass(frozen=True)
class EqualBudgetMultiBatchResult:
    common_budget: float
    budget_source: str
    conventional: MultiBatchPathwayResult
    mrt: MultiBatchPathwayResult
    capacity_difference_mrt_minus_conventional: float
    revenue_difference_mrt_minus_conventional: float
    opex_difference_mrt_minus_conventional: float


@dataclass(frozen=True)
class EqualBudgetEconomicDecisionResult:
    common_budget: float
    budget_source: str
    conventional_reference: ConventionalPlan
    conventional_reference_mode: str
    conventional_reference_resource_summary: dict[str, float | int | bool | str]
    conventional_existing_sunk_infrastructure_capex: float
    conventional_incremental_expansion_capex: float
    initial_budget: float
    conventional_reference_capex: float
    conventional_budget_difference_vs_initial: float
    comparison_budget_confirmed: bool
    confirmed_comparison_budget: float | None
    comparison_budget_options: dict[str, float]
    growth_max: MultiBatchPathwayResult | None
    economic_value: MultiBatchPathwayResult | None
    balanced: MultiBatchPathwayResult | None
    unconstrained_economic_optimum: MultiBatchPathwayResult | None
    minimum_service_compliant_design: MultiBatchPathwayResult | None
    primary_service_compliant_economic_optimum: MultiBatchPathwayResult | None
    primary_feasible_economic_recommendation: MultiBatchPathwayResult | None
    best_achievable_candidate: MultiBatchPathwayResult | None
    primary_feasible_candidate_count: int
    requirement_normalized_comparison: "RequirementNormalizedEconomicComparison" | None = None
    full_capacity_mrt_opportunity: "FullCapacityMRTOpportunity" | None = None
    mrt_batch_economics_rows: list["MRTBatchEconomicsRow"] = field(default_factory=list)
    mrt_batch_economics_transitions: list["MRTBatchEconomicsTransition"] = field(default_factory=list)
    minimum_service_compliant_mrt_batch_count: int | None = None
    primary_service_compliant_economic_batch_count: int | None = None
    highest_throughput_mrt_batch_count: int | None = None
    first_economically_unjustified_additional_batch: int | None = None
    no_feasible_mrt_message: str = ""
    policy_max_batches_per_day: int = 6
    shared_project_unit_cost_basis: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RequirementNormalizedPathwayResult:
    pathway: str
    required_throughput_per_day: float
    revenue_throughput_per_day: float
    installed_capacity_per_day: float
    operating_batches_per_day: int
    annual_revenue: float
    fixed_annual_opex: float
    utilization_sensitive_annual_opex: float
    annual_incremental_opex: float
    annual_net_operating_value: float
    capex_used: float


@dataclass(frozen=True)
class RequirementNormalizedEconomicComparison:
    required_throughput_per_day: float
    conventional: RequirementNormalizedPathwayResult
    mrt: RequirementNormalizedPathwayResult
    minimum_operating_batches_required_for_required_service: int


@dataclass(frozen=True)
class FullCapacityMRTOpportunity:
    installed_capacity_per_day: float
    required_throughput_per_day: float
    capacity_headroom_per_day: float
    operating_batches_per_day: int
    annual_revenue: float
    annual_incremental_opex: float
    annual_net_operating_value: float
    roi_pct: float
    npv: float
    payback_years: float
    capex_used: float


@dataclass(frozen=True)
class MRTBatchEconomicsRow:
    batches_per_day: int
    clinical_administration_cohorts_per_day: int
    completed_patients_per_day: float
    revenue_generating_patients_per_day: float
    gross_activity_required_at_release_per_day: float
    usable_activity_at_administration_per_day: float
    decay_activity_loss_per_day: float
    retention_fraction_at_administration: float
    transport_only_retention_fraction: float
    activity_required_at_administration_mbq_per_day: float
    activity_required_at_release_mbq_per_day: float
    activity_required_at_eob_mbq_per_day: float
    activity_decay_economic_value_status: str
    synthesis_yield_fraction: float
    synthesis_retention_fraction: float
    cyclotron_activity_capacity_mbq_per_day: float
    cyclotron_activity_capacity_status: str
    cyclotron_utilization_pct: float
    cyclotron_headroom_mbq_per_day: float
    production_upgrade_required: bool
    gross_activity_required_at_release_per_batch: float
    usable_activity_at_administration_per_batch: float
    scanners: int
    injection_resources: int
    uptake_resources: int
    mrt_rooms: int
    guideway_segments: int
    endpoints: int
    actual_production_capacity_requirement_per_day: float
    production_capacity_upgrade_status: str
    production_expansion_pct_field: float
    capex: float
    budget_change: float
    base_annual_opex: float
    incremental_batch_annual_opex: float
    total_annual_opex: float
    annual_revenue: float
    annual_net_operating_value: float
    roi_pct: float
    npv: float
    payback_years: float
    binding_constraint: str
    meets_service_floor: bool


@dataclass(frozen=True)
class MRTBatchEconomicsTransition:
    from_batches_per_day: int
    to_batches_per_day: int
    delta_completed_patients_per_day: float
    delta_annual_revenue: float
    delta_annual_opex: float
    delta_capex: float
    delta_annual_net_operating_value: float
    incremental_revenue_per_additional_patient: float | None
    incremental_opex_per_additional_patient: float | None


def _ledger_item(component: str, quantity: float, unit_cost: float, basis: str) -> dict[str, object]:
    return {
        "component": component,
        "quantity": quantity,
        "unit_cost": unit_cost,
        "subtotal": quantity * unit_cost,
        "basis": basis,
    }


def _conventional_transport_min(inputs: PlannerInputs) -> float:
    return inputs.conventional_transport_min if inputs.conventional_transport_min is not None else inputs.current_average_transport_min


def _conventional_baseline_capacity(inputs: PlannerInputs, assumptions: PlannerAssumptions, half_life_min: float) -> float:
    retained = retention(_conventional_transport_min(inputs), half_life_min)
    production_cap = inputs.current_usable_doses_per_day * retained
    scanner_cap = scanner_capacity(
        inputs.current_scanners,
        assumptions.operating_hours_per_day,
        assumptions.scanner_cycle_min,
        assumptions.scanner_availability_pct,
    )
    injection_cap = room_capacity(
        inputs.current_injection_rooms,
        assumptions.operating_hours_per_day,
        assumptions.injection_cycle_min,
    )
    uptake_cap = room_capacity(
        inputs.current_uptake_rooms,
        assumptions.operating_hours_per_day,
        assumptions.uptake_cycle_min,
    )
    return min(scanner_cap, injection_cap, uptake_cap, production_cap)


def _safe_gain_per_million(increase: float, capex_used: float) -> float:
    if capex_used <= 0:
        return 0.0
    return increase / (capex_used / 1_000_000.0)


def _safe_capex_per_patient(increase: float, capex_used: float) -> float:
    if increase <= 0:
        return float("inf")
    return capex_used / increase


def _scanner_hours_used_per_day(throughput: float, assumptions: PlannerAssumptions) -> float:
    availability = max(assumptions.scanner_availability_pct / 100.0, 1e-12)
    return throughput * assumptions.scanner_cycle_min / 60.0 / availability


def _room_hours_used_per_day(throughput: float, cycle_minutes: float) -> float:
    return throughput * cycle_minutes / 60.0


def _time_cohort_throughput(
    *,
    day_minutes: float,
    batches_per_day: int,
    transport_minutes: float,
    half_life_min: float,
    gross_doses_per_day: float,
    scanners_total: int,
    injection_rooms_total: int,
    uptake_rooms_total: int,
    guideway_cap: float,
    assumptions: PlannerAssumptions,
) -> tuple[
    float,
    float,
    float,
    float,
    float,
    list[float],
    list[float],
    list[float],
    list[float],
    list[float],
    list[float],
    list[float],
    str,
]:
    scanner_cap = scanner_capacity(
        scanners_total,
        assumptions.operating_hours_per_day,
        assumptions.scanner_cycle_min,
        assumptions.scanner_availability_pct,
    )
    injection_cap = room_capacity(
        injection_rooms_total,
        assumptions.operating_hours_per_day,
        assumptions.injection_cycle_min,
    )
    uptake_cap = room_capacity(
        uptake_rooms_total,
        assumptions.operating_hours_per_day,
        assumptions.uptake_cycle_min,
    )

    gross_per_batch = gross_doses_per_day / batches_per_day
    service_rate_per_minute = _clinical_service_rate_per_minute(
        scanners_total,
        injection_rooms_total,
        uptake_rooms_total,
        guideway_cap,
        assumptions,
    )
    used_scanner = 0.0
    used_injection = 0.0
    used_uptake = 0.0
    used_guideway = 0.0
    completed = 0.0
    per_batch_completed: list[float] = []
    per_batch_mean_wait_minutes: list[float] = []
    per_batch_decay_minutes: list[float] = []
    per_batch_usable_doses: list[float] = []
    release_times_minutes: list[float] = []
    per_batch_queue_wait_minutes: list[float] = []
    per_batch_transport_minutes: list[float] = []
    usable_doses_total = 0.0
    administration_cursor = 0.0

    batch_interval = day_minutes / batches_per_day
    for batch_index in range(batches_per_day):
        release_time = batch_index * batch_interval + transport_minutes
        release_times_minutes.append(release_time)
        per_batch_transport_minutes.append(transport_minutes)
        remaining_minutes = day_minutes - release_time
        if remaining_minutes <= 0.0:
            per_batch_completed.append(0.0)
            per_batch_usable_doses.append(0.0)
            per_batch_mean_wait_minutes.append(0.0)
            per_batch_decay_minutes.append(transport_minutes)
            per_batch_queue_wait_minutes.append(0.0)
            continue

        scanner_remaining = max(0.0, scanner_cap - used_scanner)
        injection_remaining = max(0.0, injection_cap - used_injection)
        uptake_remaining = max(0.0, uptake_cap - used_uptake)
        guideway_remaining = max(0.0, guideway_cap - used_guideway)

        queue_wait = max(0.0, administration_cursor - release_time)
        per_batch_queue_wait_minutes.append(queue_wait)
        remaining_after_queue = max(0.0, remaining_minutes - queue_wait)

        if service_rate_per_minute <= 0.0:
            per_batch_completed.append(0.0)
            per_batch_usable_doses.append(0.0)
            per_batch_mean_wait_minutes.append(queue_wait)
            per_batch_decay_minutes.append(transport_minutes + queue_wait)
            continue

        capacity_limit = min(
            scanner_remaining,
            injection_remaining,
            uptake_remaining,
            guideway_remaining,
            service_rate_per_minute * remaining_after_queue,
        )
        if capacity_limit <= 0.0:
            per_batch_completed.append(0.0)
            per_batch_usable_doses.append(0.0)
            per_batch_mean_wait_minutes.append(queue_wait)
            per_batch_decay_minutes.append(transport_minutes + queue_wait)
            continue

        usable_doses_batch = gross_per_batch
        mean_wait_after_release = queue_wait
        for _ in range(16):
            mean_wait_after_release = queue_wait + usable_doses_batch / (2.0 * service_rate_per_minute)
            effective_retention = retention(transport_minutes + mean_wait_after_release, half_life_min)
            next_usable = gross_per_batch * effective_retention
            if abs(next_usable - usable_doses_batch) <= 1e-9:
                usable_doses_batch = next_usable
                break
            usable_doses_batch = next_usable

        mean_wait_after_release = queue_wait + usable_doses_batch / (2.0 * service_rate_per_minute)
        effective_retention = retention(transport_minutes + mean_wait_after_release, half_life_min)
        usable_doses_batch = gross_per_batch * effective_retention
        per_batch_mean_wait_minutes.append(mean_wait_after_release)
        per_batch_decay_minutes.append(transport_minutes + mean_wait_after_release)
        per_batch_usable_doses.append(usable_doses_batch)
        usable_doses_total += usable_doses_batch

        cohort_completed = min(
            usable_doses_batch,
            scanner_remaining,
            injection_remaining,
            uptake_remaining,
            guideway_remaining,
            service_rate_per_minute * remaining_after_queue,
        )
        cohort_completed = max(0.0, cohort_completed)

        used_scanner += cohort_completed
        used_injection += cohort_completed
        used_uptake += cohort_completed
        used_guideway += cohort_completed
        completed += cohort_completed
        per_batch_completed.append(cohort_completed)
        administration_cursor = max(administration_cursor, release_time) + (cohort_completed / service_rate_per_minute)

    constraints = {
        "dose_availability": usable_doses_total,
        "scanner": scanner_cap,
        "injection_rooms": injection_cap,
        "uptake_rooms": uptake_cap,
        "guideway_network": guideway_cap,
    }
    binding = _binding_constraint_name(constraints, completed)
    return (
        completed,
        usable_doses_total,
        scanner_cap,
        injection_cap,
        uptake_cap,
        per_batch_mean_wait_minutes,
        per_batch_decay_minutes,
        per_batch_usable_doses,
        per_batch_completed,
        release_times_minutes,
        per_batch_queue_wait_minutes,
        per_batch_transport_minutes,
        binding,
    )


def _base_annual_opex_conventional(result: PathwayBudgetResult, assumptions: PlannerAssumptions) -> float:
    room_units = result.new_rooms_constructed + result.existing_rooms_renovated
    return (
        result.additional_scanners * assumptions.scanner_incremental_opex
        + room_units * assumptions.room_incremental_opex
    )


def _base_annual_opex_mrt(result: PathwayBudgetResult, assumptions: PlannerAssumptions) -> float:
    room_units = result.new_rooms_constructed + result.existing_rooms_connected_to_mrt + result.existing_rooms_renovated
    return (
        result.additional_scanners * assumptions.scanner_incremental_opex
        + room_units * assumptions.room_incremental_opex
        + result.endpoints * assumptions.endpoint_incremental_opex
        + result.guideway_segments * assumptions.guideway_incremental_opex
    )


def _batch_annual_opex(pathway: str, batches_per_day: int, assumptions: PlannerAssumptions) -> float:
    extra_batches = max(0, batches_per_day - 1)
    if extra_batches <= 0:
        return 0.0
    if pathway == "Conventional":
        return extra_batches * assumptions.conventional_extra_batch_opex_per_day * assumptions.operating_days_per_year
    return extra_batches * assumptions.mrt_extra_batch_opex_per_day * assumptions.operating_days_per_year


def _prescribed_activity_mbq_per_patient(assumptions: PlannerAssumptions) -> float:
    return max(assumptions.prescribed_activity_mbq_per_patient, 1e-12)


def _synthesis_yield_fraction(assumptions: PlannerAssumptions) -> float:
    return min(max(assumptions.synthesis_yield_fraction, 1e-9), 1.0)


def _synthesis_retention_fraction(assumptions: PlannerAssumptions, half_life_min: float) -> float:
    synthesis_min = max(0.0, assumptions.synthesis_processing_time_min)
    return retention(synthesis_min, half_life_min)


def _cyclotron_eob_capacity_mbq_per_day(
    *,
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    gross_release_doses_per_day_capacity: float,
    synthesis_retention_fraction: float,
    synthesis_yield_fraction: float,
    production_block_multiplier: float,
) -> tuple[float, str]:
    if inputs.current_cyclotron_eob_capacity_mbq_per_day is not None:
        base = float(inputs.current_cyclotron_eob_capacity_mbq_per_day)
        return base, "input_current_cyclotron_eob_capacity_mbq_per_day"
    if assumptions.cyclotron_eob_capacity_mbq_per_day is not None:
        base = float(assumptions.cyclotron_eob_capacity_mbq_per_day)
        return base, "assumption_cyclotron_eob_capacity_mbq_per_day"
    return 0.0, "not_calibrated"


def _candidate_tie(candidate: MultiBatchPathwayResult) -> tuple[float, float, float, float, int, int, int, int, int]:
    return (
        candidate.revenue_generating_throughput_per_day,
        candidate.achieved_capacity_per_day,
        -candidate.capex_used,
        -candidate.total_annual_modelled_opex,
        -candidate.additional_scanners,
        -candidate.new_rooms_constructed,
        -candidate.batches_per_day,
        -candidate.guideway_segments,
        -candidate.endpoints,
    )


def _binding_constraint_name(values: dict[str, float], achieved: float) -> str:
    tol = 1e-9
    binding = [name for name, value in values.items() if math.isclose(value, achieved, rel_tol=0.0, abs_tol=tol)]
    if not binding:
        return "none"
    return "/".join(sorted(binding))


def _clinical_service_rate_per_minute(
    scanners_total: int,
    injection_rooms_total: int,
    uptake_rooms_total: int,
    guideway_cap: float,
    assumptions: PlannerAssumptions,
) -> float:
    scanner_rate = 0.0 if scanners_total <= 0 else scanners_total * assumptions.scanner_availability_pct / 100.0 / assumptions.scanner_cycle_min
    injection_rate = 0.0 if injection_rooms_total <= 0 else injection_rooms_total / assumptions.injection_cycle_min
    uptake_rate = 0.0 if uptake_rooms_total <= 0 else uptake_rooms_total / assumptions.uptake_cycle_min
    guideway_rate = float("inf") if math.isinf(guideway_cap) else max(0.0, guideway_cap / (assumptions.operating_hours_per_day * 60.0))
    return min(scanner_rate, injection_rate, uptake_rate, guideway_rate)


def conventional_anchor_budget(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
) -> float:
    return conventional(inputs, assumptions, half_life_min).capex


def maximize_conventional_capacity(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    common_budget: float,
) -> PathwayBudgetResult:
    retained = retention(inputs.current_average_transport_min, half_life_min)
    baseline_capacity = _conventional_baseline_capacity(inputs, assumptions, half_life_min)

    max_add_scanners = int(common_budget // assumptions.scanner_capex) + 2
    max_prod_blocks = int(common_budget // assumptions.production_expansion_capex_per_10pct) + 2

    max_scanner_capacity = scanner_capacity(
        inputs.current_scanners + max_add_scanners,
        assumptions.operating_hours_per_day,
        assumptions.scanner_cycle_min,
        assumptions.scanner_availability_pct,
    )
    max_production_capacity = inputs.current_usable_doses_per_day * (1.0 + 0.1 * max_prod_blocks) * retained
    upper_room_target = min(max_scanner_capacity, max_production_capacity)

    required_injection_total = math.ceil(
        upper_room_target * assumptions.injection_cycle_min / (assumptions.operating_hours_per_day * 60.0)
    )
    required_uptake_total = math.ceil(
        upper_room_target * assumptions.uptake_cycle_min / (assumptions.operating_hours_per_day * 60.0)
    )
    max_add_injection = max(0, required_injection_total - inputs.current_injection_rooms) + 2
    max_add_uptake = max(0, required_uptake_total - inputs.current_uptake_rooms) + 2

    best_payload: dict[str, object] | None = None

    for add_scanners in range(0, max_add_scanners + 1):
        total_scanners = inputs.current_scanners + add_scanners
        scanner_cap = scanner_capacity(
            total_scanners,
            assumptions.operating_hours_per_day,
            assumptions.scanner_cycle_min,
            assumptions.scanner_availability_pct,
        )

        for add_injection in range(0, max_add_injection + 1):
            total_injection = inputs.current_injection_rooms + add_injection
            injection_cap = room_capacity(
                total_injection,
                assumptions.operating_hours_per_day,
                assumptions.injection_cycle_min,
            )

            for add_uptake in range(0, max_add_uptake + 1):
                total_uptake = inputs.current_uptake_rooms + add_uptake
                uptake_cap = room_capacity(
                    total_uptake,
                    assumptions.operating_hours_per_day,
                    assumptions.uptake_cycle_min,
                )

                for prod_blocks in range(0, max_prod_blocks + 1):
                    production_expansion_pct = prod_blocks * 10.0
                    production_cap = inputs.current_usable_doses_per_day * (1.0 + prod_blocks * 0.1) * retained
                    cyclotron_needed = (not inputs.has_existing_cyclotron) and prod_blocks > 0

                    capex = (
                        add_scanners * assumptions.scanner_capex
                        + (add_injection + add_uptake) * assumptions.additional_room_capex
                        + prod_blocks * assumptions.production_expansion_capex_per_10pct
                        + (
                            assumptions.cyclotron_purchase_capex + assumptions.cyclotron_installation_capex
                            if cyclotron_needed
                            else 0.0
                        )
                    )
                    if capex > common_budget + 1e-9:
                        continue

                    achieved = min(scanner_cap, injection_cap, uptake_cap, production_cap)

                    tie = (
                        achieved,
                        -capex,
                        -(add_injection + add_uptake),
                        -add_scanners,
                        -production_expansion_pct,
                        0,
                    )
                    if best_payload is None or tie > best_payload["tie"]:
                        best_payload = {
                            "tie": tie,
                            "capex": capex,
                            "achieved": achieved,
                            "scanner_cap": scanner_cap,
                            "injection_cap": injection_cap,
                            "uptake_cap": uptake_cap,
                            "production_cap": production_cap,
                            "add_scanners": add_scanners,
                            "add_injection": add_injection,
                            "add_uptake": add_uptake,
                            "prod_blocks": prod_blocks,
                            "production_expansion_pct": production_expansion_pct,
                            "cyclotron_needed": cyclotron_needed,
                        }

    if best_payload is None:
        raise ValueError("No feasible conventional configuration found under the common budget.")

    achieved = float(best_payload["achieved"])
    capex = float(best_payload["capex"])
    revenue_throughput = min(achieved, inputs.maximum_expected_demand_per_day)
    annual_revenue = revenue_throughput * assumptions.revenue_per_scan * assumptions.operating_days_per_year
    increase = achieved - baseline_capacity

    constraints = {
        "scanner": float(best_payload["scanner_cap"]),
        "injection_rooms": float(best_payload["injection_cap"]),
        "uptake_rooms": float(best_payload["uptake_cap"]),
        "production_after_decay": float(best_payload["production_cap"]),
    }
    binding = _binding_constraint_name(constraints, achieved)

    prod_cap = float(best_payload["production_cap"])
    gross_required_doses = achieved / max(retained, 1e-12)

    capex_ledger = [
        _ledger_item(
            "Additional scanners",
            float(best_payload["add_scanners"]),
            assumptions.scanner_capex,
            "decision variable",
        ),
        _ledger_item(
            "Additional injection rooms",
            float(best_payload["add_injection"]),
            assumptions.additional_room_capex,
            "decision variable",
        ),
        _ledger_item(
            "Additional uptake rooms",
            float(best_payload["add_uptake"]),
            assumptions.additional_room_capex,
            "decision variable",
        ),
        _ledger_item(
            "Production expansion blocks (10%)",
            float(best_payload["prod_blocks"]),
            assumptions.production_expansion_capex_per_10pct,
            "decision variable",
        ),
        _ledger_item(
            "Cyclotron purchase",
            1.0 if bool(best_payload["cyclotron_needed"]) else 0.0,
            assumptions.cyclotron_purchase_capex,
            "required only if no existing cyclotron and production expanded",
        ),
        _ledger_item(
            "Cyclotron installation",
            1.0 if bool(best_payload["cyclotron_needed"]) else 0.0,
            assumptions.cyclotron_installation_capex,
            "required only if no existing cyclotron and production expanded",
        ),
    ]

    return PathwayBudgetResult(
        pathway="Conventional",
        budget=common_budget,
        capex_used=capex,
        unused_budget=max(0.0, common_budget - capex),
        achieved_capacity_per_day=achieved,
        increase_above_current_capacity_per_day=increase,
        patients_gained_per_1m_capex=_safe_gain_per_million(increase, capex),
        capex_per_incremental_patient_per_day=_safe_capex_per_patient(increase, capex),
        revenue_generating_throughput_per_day=revenue_throughput,
        reserve_capacity_above_expected_demand_per_day=max(0.0, achieved - inputs.maximum_expected_demand_per_day),
        annual_revenue=annual_revenue,
        retained_activity_pct=retained * 100.0,
        production_expansion_pct=float(best_payload["production_expansion_pct"]),
        gross_required_doses_per_day=min(gross_required_doses, prod_cap / max(retained, 1e-12)),
        binding_constraint=binding,
        additional_scanners=int(best_payload["add_scanners"]),
        new_rooms_constructed=int(best_payload["add_injection"]) + int(best_payload["add_uptake"]),
        existing_rooms_renovated=0,
        existing_rooms_connected_to_mrt=0,
        guideway_segments=0,
        endpoints=0,
        vertical_transitions=0,
        building_connections=0,
        backbone_charged=False,
        capex_ledger=capex_ledger,
    )


def maximize_mrt_capacity(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    common_budget: float,
) -> PathwayBudgetResult:
    baseline_capacity = _conventional_baseline_capacity(inputs, assumptions, half_life_min)

    retained_no_backbone = retention(inputs.current_average_transport_min, half_life_min)
    baseline_production = inputs.current_usable_doses_per_day * retained_no_backbone
    baseline_scanner = scanner_capacity(
        inputs.current_scanners,
        assumptions.operating_hours_per_day,
        assumptions.scanner_cycle_min,
        assumptions.scanner_availability_pct,
    )
    baseline_room = room_capacity(
        inputs.current_injection_rooms + inputs.current_uptake_rooms,
        assumptions.operating_hours_per_day,
        assumptions.uptake_cycle_min,
    )
    baseline_achieved = min(baseline_production, baseline_scanner, baseline_room)

    best_payload: dict[str, object] = {
        "tie": (baseline_achieved, -0.0, -0, -0, -0.0, -0),
        "capex": 0.0,
        "achieved": baseline_achieved,
        "retained": retained_no_backbone,
        "scanner_cap": baseline_scanner,
        "room_cap": baseline_room,
        "production_cap": baseline_production,
        "guideway_cap": float("inf"),
        "add_scanners": 0,
        "new_rooms": 0,
        "existing_connected": 0,
        "guideway": 0,
        "endpoints": 0,
        "infra_units": 0,
        "prod_blocks": 0,
        "prod_pct": 0.0,
        "cyclotron_needed": False,
        "backbone": False,
        "transport_min": inputs.current_average_transport_min,
    }

    if common_budget >= assumptions.mrt_infrastructure_capex:
        mrt_transport_min = assumptions.mrt_transport_default_min if inputs.mrt_transport_min is None else inputs.mrt_transport_min
        retained = retention(mrt_transport_min, half_life_min)
        max_add_scanners = int(common_budget // assumptions.scanner_capex) + 2
        max_prod_blocks = int(common_budget // assumptions.production_expansion_capex_per_10pct) + 2
        max_new_rooms = int(common_budget // assumptions.additional_room_capex) + 2

        current_total_rooms = inputs.current_injection_rooms + inputs.current_uptake_rooms

        for prod_blocks in range(0, max_prod_blocks + 1):
            production_cap = inputs.current_usable_doses_per_day * (1.0 + prod_blocks * 0.1) * retained
            production_pct = prod_blocks * 10.0

            for add_scanners in range(0, max_add_scanners + 1):
                total_scanners = inputs.current_scanners + add_scanners
                scanner_cap = scanner_capacity(
                    total_scanners,
                    assumptions.operating_hours_per_day,
                    assumptions.scanner_cycle_min,
                    assumptions.scanner_availability_pct,
                )

                for new_rooms in range(0, max_new_rooms + 1):
                    connectable_rooms = inputs.existing_mrt_connectable_rooms + new_rooms
                    total_rooms = current_total_rooms + connectable_rooms
                    room_cap = room_capacity(
                        total_rooms,
                        assumptions.operating_hours_per_day,
                        assumptions.uptake_cycle_min,
                    )

                    for infra_units in range(1, 9):
                        guideway_segments = infra_units + max(1, connectable_rooms // 4)
                        endpoints = 2 + connectable_rooms
                        guideway_cap = endpoints * (8.0 + 2.0 * infra_units)

                        cyclotron_needed = (not inputs.has_existing_cyclotron) and prod_blocks > 0
                        capex = (
                            assumptions.mrt_infrastructure_capex
                            + guideway_segments * assumptions.guideway_segment_capex
                            + endpoints * assumptions.endpoint_capex
                            + add_scanners * assumptions.scanner_capex
                            + connectable_rooms * assumptions.additional_room_capex
                            + prod_blocks * assumptions.production_expansion_capex_per_10pct
                            + (
                                assumptions.cyclotron_purchase_capex + assumptions.cyclotron_installation_capex
                                if cyclotron_needed
                                else 0.0
                            )
                        )
                        if capex > common_budget + 1e-9:
                            continue

                        achieved = min(production_cap, scanner_cap, room_cap, guideway_cap)
                        tie = (
                            achieved,
                            -capex,
                            -new_rooms,
                            -add_scanners,
                            -production_pct,
                            -(guideway_segments + endpoints),
                        )
                        if tie > best_payload["tie"]:
                            best_payload = {
                                "tie": tie,
                                "capex": capex,
                                "achieved": achieved,
                                "retained": retained,
                                "scanner_cap": scanner_cap,
                                "room_cap": room_cap,
                                "production_cap": production_cap,
                                "guideway_cap": guideway_cap,
                                "add_scanners": add_scanners,
                                "new_rooms": new_rooms,
                                "existing_connected": connectable_rooms,
                                "guideway": guideway_segments,
                                "endpoints": endpoints,
                                "infra_units": infra_units,
                                "prod_blocks": prod_blocks,
                                "prod_pct": production_pct,
                                "cyclotron_needed": cyclotron_needed,
                                "backbone": True,
                                "transport_min": mrt_transport_min,
                            }

    achieved = float(best_payload["achieved"])
    capex = float(best_payload["capex"])
    revenue_throughput = min(achieved, inputs.maximum_expected_demand_per_day)
    annual_revenue = revenue_throughput * assumptions.revenue_per_scan * assumptions.operating_days_per_year
    increase = achieved - baseline_capacity

    constraints = {
        "scanner": float(best_payload["scanner_cap"]),
        "rooms": float(best_payload["room_cap"]),
        "production_after_decay": float(best_payload["production_cap"]),
        "guideway_network": float(best_payload["guideway_cap"]),
    }
    binding = _binding_constraint_name(constraints, achieved)

    retained = float(best_payload["retained"])
    gross_required_doses = achieved / max(retained, 1e-12)

    capex_ledger = [
        _ledger_item(
            "MRT base infrastructure",
            1.0 if bool(best_payload["backbone"]) else 0.0,
            assumptions.mrt_infrastructure_capex,
            "charged once when MRT backbone is selected",
        ),
        _ledger_item(
            "Guideway segments",
            float(best_payload["guideway"]),
            assumptions.guideway_segment_capex,
            "infra_units + max(1, connectable_rooms // 4)",
        ),
        _ledger_item(
            "Endpoints",
            float(best_payload["endpoints"]),
            assumptions.endpoint_capex,
            "2 + connectable_rooms",
        ),
        _ledger_item(
            "Additional scanners",
            float(best_payload["add_scanners"]),
            assumptions.scanner_capex,
            "decision variable",
        ),
        _ledger_item(
            "Connected/added MRT rooms",
            float(best_payload["existing_connected"]),
            assumptions.additional_room_capex,
            "existing connectable + new rooms under accepted MRT structure",
        ),
        _ledger_item(
            "Production expansion blocks (10%)",
            float(best_payload["prod_blocks"]),
            assumptions.production_expansion_capex_per_10pct,
            "decision variable",
        ),
        _ledger_item(
            "Cyclotron purchase",
            1.0 if bool(best_payload["cyclotron_needed"]) else 0.0,
            assumptions.cyclotron_purchase_capex,
            "required only if no existing cyclotron and production expanded",
        ),
        _ledger_item(
            "Cyclotron installation",
            1.0 if bool(best_payload["cyclotron_needed"]) else 0.0,
            assumptions.cyclotron_installation_capex,
            "required only if no existing cyclotron and production expanded",
        ),
    ]

    return PathwayBudgetResult(
        pathway="MRT",
        budget=common_budget,
        capex_used=capex,
        unused_budget=max(0.0, common_budget - capex),
        achieved_capacity_per_day=achieved,
        increase_above_current_capacity_per_day=increase,
        patients_gained_per_1m_capex=_safe_gain_per_million(increase, capex),
        capex_per_incremental_patient_per_day=_safe_capex_per_patient(increase, capex),
        revenue_generating_throughput_per_day=revenue_throughput,
        reserve_capacity_above_expected_demand_per_day=max(0.0, achieved - inputs.maximum_expected_demand_per_day),
        annual_revenue=annual_revenue,
        retained_activity_pct=retained * 100.0,
        production_expansion_pct=float(best_payload["prod_pct"]),
        gross_required_doses_per_day=gross_required_doses,
        binding_constraint=binding,
        additional_scanners=int(best_payload["add_scanners"]),
        new_rooms_constructed=int(best_payload["new_rooms"]),
        existing_rooms_renovated=0,
        existing_rooms_connected_to_mrt=int(best_payload["existing_connected"]) if bool(best_payload["backbone"]) else 0,
        guideway_segments=int(best_payload["guideway"]),
        endpoints=int(best_payload["endpoints"]),
        vertical_transitions=0,
        building_connections=0,
        backbone_charged=bool(best_payload["backbone"]),
        capex_ledger=capex_ledger,
    )


def run_equal_budget_capacity_optimization(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    explicit_budget: float | None = None,
) -> EqualBudgetResult:
    if explicit_budget is None:
        common_budget = conventional_anchor_budget(inputs, assumptions, half_life_min)
        budget_source = "conventional_target_cost_anchor"
    else:
        common_budget = float(explicit_budget)
        budget_source = "explicit_budget"

    conv = maximize_conventional_capacity(inputs, assumptions, half_life_min, common_budget)
    mrt_result = maximize_mrt_capacity(inputs, assumptions, half_life_min, common_budget)

    return EqualBudgetResult(
        common_budget=common_budget,
        budget_source=budget_source,
        conventional=conv,
        mrt=mrt_result,
        annual_revenue_difference_mrt_minus_conventional=mrt_result.annual_revenue - conv.annual_revenue,
    )


def evaluate_equal_budget_multibatch_pathway(
    pathway: str,
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    common_budget: float,
    batches_per_day: int,
) -> MultiBatchPathwayResult:
    if batches_per_day < 1:
        raise ValueError("batches_per_day must be at least 1.")

    if pathway == "Conventional":
        base = maximize_conventional_capacity(inputs, assumptions, half_life_min, common_budget)
        transport_minutes = _conventional_transport_min(inputs)
        base_annual_opex = _base_annual_opex_conventional(base, assumptions)
    elif pathway == "MRT":
        base = maximize_mrt_capacity(inputs, assumptions, half_life_min, common_budget)
        transport_minutes = assumptions.mrt_transport_default_min if inputs.mrt_transport_min is None else inputs.mrt_transport_min
        base_annual_opex = _base_annual_opex_mrt(base, assumptions)
    else:
        raise ValueError("pathway must be Conventional or MRT.")

    useful_window_per_batch = max(0.0, assumptions.operating_hours_per_day * 60.0 / batches_per_day - transport_minutes)
    if useful_window_per_batch <= 0.0:
        raise ValueError("batches_per_day leaves no useful service window.")

    scanner_hours_used = _scanner_hours_used_per_day(base.achieved_capacity_per_day, assumptions)
    injection_room_hours_used = _room_hours_used_per_day(base.achieved_capacity_per_day, assumptions.injection_cycle_min)
    uptake_room_hours_used = _room_hours_used_per_day(base.achieved_capacity_per_day, assumptions.uptake_cycle_min)
    annual_batch_opex = _batch_annual_opex(pathway, batches_per_day, assumptions)
    total_annual_opex = base_annual_opex + annual_batch_opex
    revenue_throughput = min(base.achieved_capacity_per_day, inputs.maximum_expected_demand_per_day)
    annual_revenue = revenue_throughput * assumptions.revenue_per_scan * assumptions.operating_days_per_year
    annual_net_contribution = annual_revenue - total_annual_opex
    increase = base.achieved_capacity_per_day - _conventional_baseline_capacity(inputs, assumptions, half_life_min)

    return MultiBatchPathwayResult(
        pathway=pathway,
        budget=common_budget,
        batches_per_day=batches_per_day,
        operating_hours_per_day=assumptions.operating_hours_per_day,
        transport_minutes=transport_minutes,
        useful_service_window_per_batch_minutes=useful_window_per_batch,
        achieved_capacity_per_day=base.achieved_capacity_per_day,
        increase_above_current_capacity_per_day=increase,
        patients_gained_per_1m_capex=_safe_gain_per_million(increase, base.capex_used),
        capex_per_incremental_patient_per_day=_safe_capex_per_patient(increase, base.capex_used),
        revenue_generating_throughput_per_day=revenue_throughput,
        capex_used=base.capex_used,
        unused_budget=max(0.0, common_budget - base.capex_used),
        reserve_capacity_above_expected_demand_per_day=max(0.0, base.achieved_capacity_per_day - inputs.maximum_expected_demand_per_day),
        annual_incremental_batch_opex=annual_batch_opex,
        total_annual_modelled_opex=total_annual_opex,
        annual_net_operating_contribution=annual_net_contribution,
        annual_revenue=annual_revenue,
        retained_activity_pct=base.retained_activity_pct,
        production_expansion_pct=base.production_expansion_pct,
        gross_required_doses_per_day=base.gross_required_doses_per_day,
        gross_required_doses_per_batch=base.gross_required_doses_per_day / batches_per_day,
        patients_per_batch=revenue_throughput / batches_per_day,
        scanner_hours_used_per_day=scanner_hours_used,
        scanner_hours_used_per_batch=scanner_hours_used / batches_per_day,
        injection_room_hours_used_per_day=injection_room_hours_used,
        injection_room_hours_used_per_batch=injection_room_hours_used / batches_per_day,
        uptake_room_hours_used_per_day=uptake_room_hours_used,
        uptake_room_hours_used_per_batch=uptake_room_hours_used / batches_per_day,
        binding_constraint=base.binding_constraint,
        additional_scanners=base.additional_scanners,
        new_rooms_constructed=base.new_rooms_constructed,
        existing_rooms_renovated=base.existing_rooms_renovated,
        existing_rooms_connected_to_mrt=base.existing_rooms_connected_to_mrt,
        guideway_segments=base.guideway_segments,
        endpoints=base.endpoints,
        vertical_transitions=base.vertical_transitions,
        building_connections=base.building_connections,
        backbone_charged=base.backbone_charged,
        capex_ledger=base.capex_ledger,
        usable_doses_per_day=base.gross_required_doses_per_day * base.retained_activity_pct / 100.0,
        binding_constraint_calibration="engineering_assumption",
    )


def run_equal_budget_multibatch_optimization(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    explicit_budget: float | None = None,
    max_batches_per_day: int = 6,
) -> EqualBudgetMultiBatchResult:
    if max_batches_per_day < 1:
        raise ValueError("max_batches_per_day must be at least 1.")

    if explicit_budget is None:
        common_budget = conventional_anchor_budget(inputs, assumptions, half_life_min)
        budget_source = "conventional_target_cost_anchor"
    else:
        common_budget = float(explicit_budget)
        budget_source = "explicit_budget"

    conventional_candidates = [
        candidate
        for batches in range(1, max_batches_per_day + 1)
        for candidate in [
            evaluate_equal_budget_multibatch_pathway(
                "Conventional",
                inputs,
                assumptions,
                half_life_min,
                common_budget,
                batches_per_day=batches,
            )
        ]
        if candidate.useful_service_window_per_batch_minutes > 0.0
    ]
    mrt_candidates = [
        candidate
        for batches in range(1, max_batches_per_day + 1)
        for candidate in [
            evaluate_equal_budget_multibatch_pathway(
                "MRT",
                inputs,
                assumptions,
                half_life_min,
                common_budget,
                batches_per_day=batches,
            )
        ]
        if candidate.useful_service_window_per_batch_minutes > 0.0
    ]

    conventional_result = max(conventional_candidates, key=_candidate_tie)
    mrt_result = max(mrt_candidates, key=_candidate_tie)

    return EqualBudgetMultiBatchResult(
        common_budget=common_budget,
        budget_source=budget_source,
        conventional=conventional_result,
        mrt=mrt_result,
        capacity_difference_mrt_minus_conventional=mrt_result.achieved_capacity_per_day - conventional_result.achieved_capacity_per_day,
        revenue_difference_mrt_minus_conventional=mrt_result.annual_revenue - conventional_result.annual_revenue,
        opex_difference_mrt_minus_conventional=mrt_result.total_annual_modelled_opex - conventional_result.total_annual_modelled_opex,
    )


_GROWTH_MAX_SCORE_WEIGHTS: dict[str, float] = {
    "demand_capture": 0.35,
    "reserve_headroom": 0.20,
    "capacity": 0.15,
    "npv": 0.10,
    "roi": 0.10,
    "payback": 0.05,
    "opex_efficiency": 0.05,
}

_ECONOMIC_VALUE_SCORE_WEIGHTS: dict[str, float] = {
    "npv": 0.35,
    "roi": 0.25,
    "payback": 0.20,
    "opex_efficiency": 0.10,
    "demand_capture": 0.10,
}

_BALANCED_SCORE_WEIGHTS: dict[str, float] = {
    "demand_capture": 0.20,
    "reserve_headroom": 0.10,
    "npv": 0.25,
    "roi": 0.20,
    "payback": 0.15,
    "opex_efficiency": 0.10,
}


def _annual_financials(
    capex: float,
    annual_incremental_opex: float,
    revenue_throughput_per_day: float,
    assumptions: PlannerAssumptions,
) -> tuple[float, float, float, float, float, float]:
    return incremental_financials(
        capex=capex,
        annual_incremental_opex=annual_incremental_opex,
        throughput_patients_per_day=revenue_throughput_per_day,
        revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=assumptions.operating_days_per_year,
        discount_rate_pct=assumptions.discount_rate_pct,
        analysis_years=assumptions.analysis_years,
    )


def _normalized_score_component(value: float, scale: float) -> float:
    if scale <= 0.0:
        return 0.0
    return max(0.0, min(1.0, value / scale))


def _weighted_score(components: dict[str, float], weights: dict[str, float]) -> float:
    return sum(components.get(name, 0.0) * weight for name, weight in weights.items())


def _score_components(
    candidate: MultiBatchPathwayResult,
    inputs: PlannerInputs,
    common_budget: float,
) -> dict[str, float]:
    demand_scale = max(inputs.maximum_expected_demand_per_day, 1e-9)
    capex_scale = max(common_budget, 1e-9)
    annual_revenue_scale = max(demand_scale * 300.0, 1.0)
    return {
        "demand_capture": _normalized_score_component(candidate.revenue_generating_throughput_per_day, demand_scale),
        "reserve_headroom": _normalized_score_component(candidate.reserve_capacity_above_expected_demand_per_day, demand_scale),
        "capacity": _normalized_score_component(candidate.achieved_capacity_per_day, demand_scale),
        "npv": _normalized_score_component(max(0.0, candidate.npv), capex_scale),
        "roi": _normalized_score_component(max(0.0, candidate.roi_pct), 100.0),
        "payback": 0.0 if math.isinf(candidate.payback_years) else 1.0 / (1.0 + max(candidate.payback_years, 0.0)),
        "opex_efficiency": 1.0 / (1.0 + candidate.annual_incremental_opex / annual_revenue_scale),
        "capex_utilization": _normalized_score_component(candidate.capex_used, capex_scale),
        "feasibility": 1.0 if candidate.operating_day_feasible else 0.0,
    }


def _build_mrt_economic_candidate(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    common_budget: float,
    batches_per_day: int,
    backbone_selected: bool,
    transport_minutes: float,
    add_scanners: int,
    connected_rooms: int,
    guideway_segments: int,
    endpoints: int,
    production_blocks: int,
    infra_units: int,
) -> MultiBatchPathwayResult | None:
    retained = retention(transport_minutes, half_life_min)
    gross_production_per_day = inputs.current_usable_doses_per_day * (1.0 + production_blocks * 0.1)
    prescribed_activity_mbq = _prescribed_activity_mbq_per_patient(assumptions)
    synthesis_yield = _synthesis_yield_fraction(assumptions)
    synthesis_retention = _synthesis_retention_fraction(assumptions, half_life_min)
    synthesis_factor = max(synthesis_retention * synthesis_yield, 1e-12)
    production_block_multiplier = 1.0 + production_blocks * 0.1
    scanner_cap = scanner_capacity(
        inputs.current_scanners + add_scanners,
        assumptions.operating_hours_per_day,
        assumptions.scanner_cycle_min,
        assumptions.scanner_availability_pct,
    )
    total_injection_rooms = inputs.current_injection_rooms + connected_rooms
    total_uptake_rooms = inputs.current_uptake_rooms + connected_rooms
    guideway_cap = endpoints * (8.0 + 2.0 * infra_units) if backbone_selected else float("inf")
    useful_service_window = max(0.0, assumptions.operating_hours_per_day * 60.0 / batches_per_day - transport_minutes)
    if useful_service_window <= 0.0:
        return None

    day_minutes = assumptions.operating_hours_per_day * 60.0
    (
        achieved,
        usable_doses_total,
        scanner_cap,
        injection_cap,
        uptake_cap,
        per_batch_mean_wait_minutes,
        per_batch_decay_minutes,
        per_batch_usable_doses,
        per_batch_completed,
        release_times_minutes,
        per_batch_queue_wait_minutes,
        per_batch_transport_minutes,
        binding_constraint,
    ) = _time_cohort_throughput(
        day_minutes=day_minutes,
        batches_per_day=batches_per_day,
        transport_minutes=transport_minutes,
        half_life_min=half_life_min,
        gross_doses_per_day=gross_production_per_day,
        scanners_total=inputs.current_scanners + add_scanners,
        injection_rooms_total=total_injection_rooms,
        uptake_rooms_total=total_uptake_rooms,
        guideway_cap=guideway_cap,
        assumptions=assumptions,
    )

    achieved = min(achieved, scanner_cap, injection_cap, uptake_cap, guideway_cap)
    administration_retention = 0.0 if gross_production_per_day <= 0.0 else usable_doses_total / gross_production_per_day
    effective_retained = administration_retention
    gross_required_doses_per_day_admin = 0.0 if administration_retention <= 0.0 else achieved / administration_retention
    gross_required_doses_per_batch_admin = gross_required_doses_per_day_admin / batches_per_day
    gross_required_doses_per_day_transport = 0.0 if retained <= 0.0 else achieved / retained
    gross_required_doses_per_batch_transport = gross_required_doses_per_day_transport / batches_per_day

    activity_required_at_admin = achieved * prescribed_activity_mbq
    activity_required_at_release = 0.0 if administration_retention <= 0.0 else activity_required_at_admin / administration_retention
    activity_required_at_eob = activity_required_at_release / synthesis_factor

    available_eob_capacity, cyclotron_capacity_status = _cyclotron_eob_capacity_mbq_per_day(
        inputs=inputs,
        assumptions=assumptions,
        gross_release_doses_per_day_capacity=gross_production_per_day,
        synthesis_retention_fraction=synthesis_retention,
        synthesis_yield_fraction=synthesis_yield,
        production_block_multiplier=production_block_multiplier,
    )
    baseline_eob_capacity, _ = _cyclotron_eob_capacity_mbq_per_day(
        inputs=inputs,
        assumptions=assumptions,
        gross_release_doses_per_day_capacity=inputs.current_usable_doses_per_day,
        synthesis_retention_fraction=synthesis_retention,
        synthesis_yield_fraction=synthesis_yield,
        production_block_multiplier=1.0,
    )
    capacity_is_calibrated = cyclotron_capacity_status != "not_calibrated"
    production_upgrade_required = capacity_is_calibrated and (activity_required_at_eob > baseline_eob_capacity + 1e-9)
    if capacity_is_calibrated and activity_required_at_eob > available_eob_capacity + 1e-9:
        return None

    activity_decay_loss_post_release = max(0.0, activity_required_at_release - activity_required_at_admin)

    revenue_throughput = min(achieved, inputs.maximum_expected_demand_per_day)
    charged_production_blocks = production_blocks if (production_upgrade_required or not capacity_is_calibrated) else 0
    production_block_capex = charged_production_blocks * assumptions.production_expansion_capex_per_10pct
    capex = (
        (assumptions.mrt_infrastructure_capex if backbone_selected else 0.0)
        + guideway_segments * assumptions.guideway_segment_capex
        + endpoints * assumptions.endpoint_capex
        + add_scanners * assumptions.scanner_capex
        + connected_rooms * assumptions.additional_room_capex
        + production_block_capex
        + (
            assumptions.cyclotron_purchase_capex + assumptions.cyclotron_installation_capex
            if (not inputs.has_existing_cyclotron and charged_production_blocks > 0)
            else 0.0
        )
    )
    if capex > common_budget + 1e-9:
        return None

    daily_scanner_hours = _scanner_hours_used_per_day(achieved, assumptions)
    daily_injection_hours = _room_hours_used_per_day(achieved, assumptions.injection_cycle_min)
    daily_uptake_hours = _room_hours_used_per_day(achieved, assumptions.uptake_cycle_min)
    operating_day_feasible = True

    annual_incremental_batch_opex = _batch_annual_opex("MRT", batches_per_day, assumptions)
    base_annual_opex = (
        add_scanners * assumptions.scanner_incremental_opex
        + connected_rooms * assumptions.room_incremental_opex
        + endpoints * assumptions.endpoint_incremental_opex
        + guideway_segments * assumptions.guideway_incremental_opex
    )
    total_annual_opex = base_annual_opex + annual_incremental_batch_opex
    annual_revenue, annual_incremental_opex, annual_net_cash_flow, npv, roi, payback = _annual_financials(
        capex,
        total_annual_opex,
        revenue_throughput,
        assumptions,
    )
    baseline_capacity = _conventional_baseline_capacity(inputs, assumptions, half_life_min)
    reserve = max(0.0, achieved - inputs.maximum_expected_demand_per_day)
    cyclotron_utilization_pct = (
        0.0
        if (not capacity_is_calibrated or available_eob_capacity <= 0.0)
        else 100.0 * activity_required_at_eob / available_eob_capacity
    )
    cyclotron_headroom_mbq = 0.0 if not capacity_is_calibrated else (available_eob_capacity - activity_required_at_eob)
    binding_calibration = "heuristic_network_capacity" if "guideway_network" in binding_constraint.split("/") else "engineering_assumption"
    return MultiBatchPathwayResult(
        pathway="MRT",
        budget=common_budget,
        batches_per_day=batches_per_day,
        operating_hours_per_day=assumptions.operating_hours_per_day,
        transport_minutes=transport_minutes,
        useful_service_window_per_batch_minutes=useful_service_window,
        achieved_capacity_per_day=achieved,
        increase_above_current_capacity_per_day=achieved - baseline_capacity,
        patients_gained_per_1m_capex=_safe_gain_per_million(achieved - baseline_capacity, capex),
        capex_per_incremental_patient_per_day=_safe_capex_per_patient(achieved - baseline_capacity, capex),
        revenue_generating_throughput_per_day=revenue_throughput,
        capex_used=capex,
        unused_budget=max(0.0, common_budget - capex),
        reserve_capacity_above_expected_demand_per_day=reserve,
        annual_incremental_batch_opex=annual_incremental_batch_opex,
        total_annual_modelled_opex=total_annual_opex,
        annual_revenue=annual_revenue,
        retained_activity_pct=effective_retained * 100.0,
        production_expansion_pct=float(production_blocks * 10.0),
        production_expansion_capex_charged=charged_production_blocks > 0,
        gross_required_doses_per_day=gross_required_doses_per_day_admin,
        gross_required_doses_per_batch=gross_required_doses_per_batch_admin,
        patients_per_batch=sum(per_batch_completed) / max(1, batches_per_day),
        scanner_hours_used_per_day=daily_scanner_hours,
        scanner_hours_used_per_batch=daily_scanner_hours / batches_per_day,
        injection_room_hours_used_per_day=daily_injection_hours,
        injection_room_hours_used_per_batch=daily_injection_hours / batches_per_day,
        uptake_room_hours_used_per_day=daily_uptake_hours,
        uptake_room_hours_used_per_batch=daily_uptake_hours / batches_per_day,
        binding_constraint=binding_constraint,
        additional_scanners=add_scanners,
        new_rooms_constructed=connected_rooms,
        existing_rooms_renovated=0,
        existing_rooms_connected_to_mrt=connected_rooms if backbone_selected else 0,
        guideway_segments=guideway_segments,
        endpoints=endpoints,
        vertical_transitions=0,
        building_connections=0,
        backbone_charged=backbone_selected,
        capex_ledger=[
            _ledger_item(
                "MRT base infrastructure",
                1.0 if backbone_selected else 0.0,
                assumptions.mrt_infrastructure_capex,
                "charged once when MRT backbone is selected",
            ),
            _ledger_item("Guideway segments", float(guideway_segments), assumptions.guideway_segment_capex, "decision variable"),
            _ledger_item("Endpoints", float(endpoints), assumptions.endpoint_capex, "decision variable"),
            _ledger_item("Additional scanners", float(add_scanners), assumptions.scanner_capex, "decision variable"),
            _ledger_item("Connected MRT rooms", float(connected_rooms), assumptions.additional_room_capex, "decision variable"),
            _ledger_item("Production expansion blocks (10%)", float(charged_production_blocks), assumptions.production_expansion_capex_per_10pct, "charged only when EOB activity capacity shortfall exists"),
            _ledger_item(
                "Cyclotron purchase",
                1.0 if (not inputs.has_existing_cyclotron and charged_production_blocks > 0) else 0.0,
                assumptions.cyclotron_purchase_capex,
                "required only if no existing cyclotron and production activity upgrade is charged",
            ),
            _ledger_item(
                "Cyclotron installation",
                1.0 if (not inputs.has_existing_cyclotron and charged_production_blocks > 0) else 0.0,
                assumptions.cyclotron_installation_capex,
                "required only if no existing cyclotron and production activity upgrade is charged",
            ),
        ],
        gross_production_doses_per_day_at_release=gross_production_per_day,
        gross_production_doses_per_batch_at_release=gross_production_per_day / batches_per_day,
        transport_only_retention_fraction=retained,
        administration_retention_fraction=administration_retention,
        transport_only_gross_required_doses_per_day=gross_required_doses_per_day_transport,
        transport_only_gross_required_doses_per_batch=gross_required_doses_per_batch_transport,
        administration_cohorts_per_day=batches_per_day,
        prescribed_activity_mbq_per_patient=prescribed_activity_mbq,
        activity_required_at_administration_mbq_per_day=activity_required_at_admin,
        activity_required_at_release_mbq_per_day=activity_required_at_release,
        activity_required_at_eob_mbq_per_day=activity_required_at_eob,
        activity_decay_loss_post_release_mbq_per_day=activity_decay_loss_post_release,
        synthesis_yield_fraction=synthesis_yield,
        synthesis_processing_time_min=max(0.0, assumptions.synthesis_processing_time_min),
        synthesis_retention_fraction=synthesis_retention,
        cyclotron_activity_capacity_mbq_per_day=available_eob_capacity,
        cyclotron_activity_capacity_status=cyclotron_capacity_status,
        cyclotron_utilization_pct=cyclotron_utilization_pct,
        cyclotron_headroom_mbq_per_day=cyclotron_headroom_mbq,
        production_upgrade_required=production_upgrade_required,
        legacy_production_capacity_assumption_status=(
            "legacy_10pct_throughput_blocks_capacity_not_calibrated"
            if cyclotron_capacity_status == "not_calibrated"
            else "explicit_cyclotron_activity_capacity"
        ),
        usable_doses_per_day=usable_doses_total,
        batch_release_times_minutes=release_times_minutes,
        per_batch_mean_administration_wait_minutes=per_batch_mean_wait_minutes,
        per_batch_decay_time_minutes=per_batch_decay_minutes,
        per_batch_usable_doses=per_batch_usable_doses,
        per_batch_completed_patients=per_batch_completed,
        per_batch_queue_wait_minutes=per_batch_queue_wait_minutes,
        per_batch_transport_minutes=per_batch_transport_minutes,
        binding_constraint_calibration=binding_calibration,
        annual_incremental_opex=annual_incremental_opex,
        annual_net_operating_contribution=annual_net_cash_flow,
        npv=npv,
        roi_pct=roi,
        payback_years=payback,
        operating_day_feasible=True,
    )


def part2b3a_mrt_batch_audit(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    explicit_budget: float | None = None,
    max_batches_per_day: int = 6,
) -> list[dict[str, object]]:
    if explicit_budget is None:
        common_budget = conventional(inputs, assumptions, half_life_min).capex
    else:
        common_budget = float(explicit_budget)

    rows: list[dict[str, object]] = []
    transport_minutes = assumptions.mrt_transport_default_min if inputs.mrt_transport_min is None else inputs.mrt_transport_min
    max_add_scanners, max_connected_rooms = _mrt_search_bounds(
        inputs,
        assumptions,
        half_life_min,
        common_budget,
    )

    for batches_per_day in range(1, max_batches_per_day + 1):
        best: MultiBatchPathwayResult | None = None
        best_score = -math.inf
        best_tie: tuple[float, float, float, float, int, int, int, int, int] | None = None

        for backbone_selected in (False, True):
            if not backbone_selected and batches_per_day > 1:
                continue

            if backbone_selected:
                for add_scanners in range(0, max_add_scanners + 1):
                    for connected_rooms in range(0, max_connected_rooms + 1):
                        max_prod_blocks = _mrt_production_block_bound(
                            inputs,
                            assumptions,
                            half_life_min,
                            common_budget,
                            batches_per_day,
                        )
                        for production_blocks in range(0, max_prod_blocks + 1):
                            for infra_units in range(1, 5):
                                guideway_segments = infra_units + max(1, connected_rooms // 4)
                                endpoints = 2 + connected_rooms
                                candidate = _build_mrt_economic_candidate(
                                    inputs,
                                    assumptions,
                                    half_life_min,
                                    common_budget,
                                    batches_per_day,
                                    True,
                                    transport_minutes,
                                    add_scanners,
                                    connected_rooms,
                                    guideway_segments,
                                    endpoints,
                                    production_blocks,
                                    infra_units,
                                )
                                if candidate is None:
                                    continue
                                components = _score_components(candidate, inputs, common_budget)
                                score = _weighted_score(components, _BALANCED_SCORE_WEIGHTS)
                                tie = _candidate_tie(candidate)
                                if best_tie is None or tie > best_tie:
                                    best = candidate
                                    best_tie = tie
                                    best_score = score
            else:
                candidate = _build_mrt_economic_candidate(
                    inputs,
                    assumptions,
                    half_life_min,
                    common_budget,
                    batches_per_day,
                    False,
                    inputs.current_average_transport_min,
                    0,
                    0,
                    0,
                    0,
                    0,
                    1,
                )
                if candidate is not None:
                    components = _score_components(candidate, inputs, common_budget)
                    score = _weighted_score(components, _BALANCED_SCORE_WEIGHTS)
                    tie = _candidate_tie(candidate)
                    if best_tie is None or tie > best_tie:
                        best = candidate
                        best_tie = tie
                        best_score = score

        if best is None:
            continue

        scanner_cap = scanner_capacity(
            inputs.current_scanners + best.additional_scanners,
            assumptions.operating_hours_per_day,
            assumptions.scanner_cycle_min,
            assumptions.scanner_availability_pct,
        )
        injection_cap = room_capacity(
            inputs.current_injection_rooms + best.new_rooms_constructed,
            assumptions.operating_hours_per_day,
            assumptions.injection_cycle_min,
        )
        uptake_cap = room_capacity(
            inputs.current_uptake_rooms + best.new_rooms_constructed,
            assumptions.operating_hours_per_day,
            assumptions.uptake_cycle_min,
        )

        rows.append(
            {
                "batches_per_day": best.batches_per_day,
                "usable_doses_per_day": best.usable_doses_per_day,
                "gross_doses_per_day": best.gross_required_doses_per_day,
                "batch_release_times_minutes": list(best.batch_release_times_minutes),
                "mean_administration_wait_minutes": list(best.per_batch_mean_administration_wait_minutes),
                "decay_time_minutes": list(best.per_batch_decay_time_minutes),
                "completed_patients_per_day": best.achieved_capacity_per_day,
                "scanner_utilization_pct": 0.0 if scanner_cap <= 0 else 100.0 * best.achieved_capacity_per_day / scanner_cap,
                "injection_utilization_pct": 0.0 if injection_cap <= 0 else 100.0 * best.achieved_capacity_per_day / injection_cap,
                "uptake_utilization_pct": 0.0 if uptake_cap <= 0 else 100.0 * best.achieved_capacity_per_day / uptake_cap,
                "binding_constraint": best.binding_constraint,
                "binding_constraint_calibration": best.binding_constraint_calibration,
                "annual_revenue": best.annual_revenue,
                "annual_opex": best.annual_incremental_opex,
                "capex_used": best.capex_used,
                "budget_available": common_budget,
                "budget_change": common_budget - best.capex_used,
                "balanced_weighted_score": best_score,
            }
        )

    return rows


def _select_best_view(
    candidates: list[MultiBatchPathwayResult],
    weights: dict[str, float],
    view_name: str,
    inputs: PlannerInputs,
    common_budget: float,
) -> MultiBatchPathwayResult:
    best_candidate: MultiBatchPathwayResult | None = None
    best_key: tuple[float, float, float, float, int] | None = None

    for candidate in candidates:
        components = _score_components(candidate, inputs, common_budget)
        score = _weighted_score(components, weights)
        payload = dict(candidate.__dict__)
        payload["weighted_score"] = score
        payload["score_components"] = components
        payload["score_weights"] = dict(weights)
        payload["decision_view"] = view_name
        enriched = MultiBatchPathwayResult(**payload)
        tie = (
            enriched.weighted_score,
            enriched.achieved_capacity_per_day,
            enriched.annual_net_operating_contribution,
            -enriched.capex_used,
            -enriched.batches_per_day,
        )
        if best_key is None or tie > best_key:
            best_candidate = enriched
            best_key = tie

    if best_candidate is None:
        raise ValueError(f"No feasible MRT candidate found for {view_name}.")
    return best_candidate


def _shared_project_unit_cost_basis(assumptions: PlannerAssumptions) -> dict[str, float]:
    return {
        "scanner_capex": assumptions.scanner_capex,
        "room_capex": assumptions.additional_room_capex,
        "production_expansion_capex_per_10pct": assumptions.production_expansion_capex_per_10pct,
        "cyclotron_purchase_capex": assumptions.cyclotron_purchase_capex,
        "cyclotron_installation_capex": assumptions.cyclotron_installation_capex,
    }


def _mrt_search_bounds(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    common_budget: float,
) -> tuple[int, int]:
    # Bound enumeration by the highest throughput that can matter for service floor/revenue decisions.
    useful_throughput = max(inputs.target_patients_per_day, inputs.maximum_expected_demand_per_day)
    useful_throughput = max(useful_throughput, 1.0)
    # Timing-coupled decay means higher clinical service rates can still improve
    # usable-dose realization, so allow modest headroom beyond direct demand.
    bounded_search_throughput = 1.5 * useful_throughput

    per_scanner = scanner_capacity(
        1,
        assumptions.operating_hours_per_day,
        assumptions.scanner_cycle_min,
        assumptions.scanner_availability_pct,
    )
    max_total_scanners = 0 if per_scanner <= 0.0 else math.ceil(bounded_search_throughput / per_scanner)
    max_add_scanners = max(0, max_total_scanners - inputs.current_scanners)

    injection_needed_total = math.ceil(
        bounded_search_throughput * assumptions.injection_cycle_min / (assumptions.operating_hours_per_day * 60.0)
    )
    uptake_needed_total = math.ceil(
        bounded_search_throughput * assumptions.uptake_cycle_min / (assumptions.operating_hours_per_day * 60.0)
    )
    clinical_connected_need = max(
        0,
        injection_needed_total - inputs.current_injection_rooms,
        uptake_needed_total - inputs.current_uptake_rooms,
    )

    max_infra_units = 4
    max_per_endpoint_guideway = 8.0 + 2.0 * max_infra_units
    endpoints_needed = math.ceil(bounded_search_throughput / max_per_endpoint_guideway)
    guideway_connected_need = max(0, endpoints_needed - 2)
    max_connected_rooms = max(clinical_connected_need, guideway_connected_need)

    return max_add_scanners, max_connected_rooms


def _mrt_production_block_bound(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    common_budget: float,
    batches_per_day: int,
) -> int:
    useful_throughput = max(inputs.target_patients_per_day, inputs.maximum_expected_demand_per_day)
    useful_throughput = max(useful_throughput, 1.0)
    # `current_usable_doses_per_day` is treated as the usable-dose baseline for
    # expansion blocks, so bound growth directly to useful throughput demand.
    required_usable_doses = useful_throughput
    if inputs.current_usable_doses_per_day <= 0.0:
        max_prod_blocks = 0
    else:
        required_growth = max(0.0, required_usable_doses / inputs.current_usable_doses_per_day - 1.0)
        max_prod_blocks = math.ceil(required_growth / 0.1)
    budget_limited_prod_blocks = int(common_budget // max(assumptions.production_expansion_capex_per_10pct, 1e-9))
    return min(max_prod_blocks, budget_limited_prod_blocks)


def _enumerate_mrt_candidates(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    common_budget: float,
    max_batches_per_day: int,
) -> list[MultiBatchPathwayResult]:
    mrt_candidates: list[MultiBatchPathwayResult] = []
    transport_minutes = assumptions.mrt_transport_default_min if inputs.mrt_transport_min is None else inputs.mrt_transport_min
    max_add_scanners, max_connected_rooms = _mrt_search_bounds(
        inputs,
        assumptions,
        half_life_min,
        common_budget,
    )

    for batches_per_day in range(1, max_batches_per_day + 1):
        for backbone_selected in (False, True):
            if not backbone_selected and batches_per_day > 1:
                continue

            if backbone_selected:
                for add_scanners in range(0, max_add_scanners + 1):
                    scanner_cap_total = scanner_capacity(
                        inputs.current_scanners + add_scanners,
                        assumptions.operating_hours_per_day,
                        assumptions.scanner_cycle_min,
                        assumptions.scanner_availability_pct,
                    )
                    if add_scanners > 0:
                        scanner_cap_prev = scanner_capacity(
                            inputs.current_scanners + add_scanners - 1,
                            assumptions.operating_hours_per_day,
                            assumptions.scanner_cycle_min,
                            assumptions.scanner_availability_pct,
                        )
                        if scanner_cap_prev >= inputs.maximum_expected_demand_per_day and scanner_cap_total >= scanner_cap_prev:
                            continue
                    for connected_rooms in range(0, max_connected_rooms + 1):
                        injection_cap_total = room_capacity(
                            inputs.current_injection_rooms + connected_rooms,
                            assumptions.operating_hours_per_day,
                            assumptions.injection_cycle_min,
                        )
                        uptake_cap_total = room_capacity(
                            inputs.current_uptake_rooms + connected_rooms,
                            assumptions.operating_hours_per_day,
                            assumptions.uptake_cycle_min,
                        )
                        if connected_rooms > 0:
                            injection_cap_prev = room_capacity(
                                inputs.current_injection_rooms + connected_rooms - 1,
                                assumptions.operating_hours_per_day,
                                assumptions.injection_cycle_min,
                            )
                            uptake_cap_prev = room_capacity(
                                inputs.current_uptake_rooms + connected_rooms - 1,
                                assumptions.operating_hours_per_day,
                                assumptions.uptake_cycle_min,
                            )
                            if (
                                injection_cap_prev >= inputs.maximum_expected_demand_per_day
                                and uptake_cap_prev >= inputs.maximum_expected_demand_per_day
                                and injection_cap_total >= injection_cap_prev
                                and uptake_cap_total >= uptake_cap_prev
                            ):
                                continue
                        max_prod_blocks = _mrt_production_block_bound(
                            inputs,
                            assumptions,
                            half_life_min,
                            common_budget,
                            batches_per_day,
                        )
                        for production_blocks in range(0, max_prod_blocks + 1):
                            retained = retention(transport_minutes, half_life_min)
                            gross_capacity = inputs.current_usable_doses_per_day * (1.0 + production_blocks * 0.1)
                            usable_capacity = gross_capacity * retained
                            if production_blocks > 0:
                                prev_gross_capacity = inputs.current_usable_doses_per_day * (1.0 + (production_blocks - 1) * 0.1)
                                prev_usable_capacity = prev_gross_capacity * retained
                                if prev_usable_capacity >= inputs.maximum_expected_demand_per_day and usable_capacity >= prev_usable_capacity:
                                    continue
                            for infra_units in range(1, 5):
                                guideway_segments = infra_units + max(1, connected_rooms // 4)
                                endpoints = 2 + connected_rooms
                                candidate = _build_mrt_economic_candidate(
                                    inputs,
                                    assumptions,
                                    half_life_min,
                                    common_budget,
                                    batches_per_day,
                                    True,
                                    transport_minutes,
                                    add_scanners,
                                    connected_rooms,
                                    guideway_segments,
                                    endpoints,
                                    production_blocks,
                                    infra_units,
                                )
                                if candidate is not None:
                                    mrt_candidates.append(candidate)
            else:
                candidate = _build_mrt_economic_candidate(
                    inputs,
                    assumptions,
                    half_life_min,
                    common_budget,
                    batches_per_day,
                    False,
                    inputs.current_average_transport_min,
                    0,
                    0,
                    0,
                    0,
                    0,
                    1,
                )
                if candidate is not None:
                    mrt_candidates.append(candidate)

    return mrt_candidates


def _primary_recommendation_tie(candidate: MultiBatchPathwayResult) -> tuple[float, float, float, int, float, int, int, int, int]:
    return (
        candidate.annual_net_operating_contribution,
        candidate.achieved_capacity_per_day,
        -candidate.capex_used,
        -candidate.batches_per_day,
        candidate.revenue_generating_throughput_per_day,
        -candidate.additional_scanners,
        -candidate.new_rooms_constructed,
        -candidate.guideway_segments,
        -candidate.endpoints,
    )


def _best_mrt_candidate_by_batch(
    mrt_candidates: list[MultiBatchPathwayResult],
    batches_per_day: int,
) -> MultiBatchPathwayResult | None:
    batch_candidates = [c for c in mrt_candidates if c.batches_per_day == batches_per_day]
    if not batch_candidates:
        return None
    return max(batch_candidates, key=_primary_recommendation_tie)


def _production_upgrade_status(candidate: MultiBatchPathwayResult) -> str:
    if not candidate.production_upgrade_required:
        return "not_required_by_activity_capacity"
    if not candidate.production_expansion_capex_charged:
        return "required_but_not_charged"
    if candidate.production_expansion_pct <= 1e-9:
        return "no_upgrade"
    blocks = max(0, int(round(candidate.production_expansion_pct / 10.0)))
    return f"{blocks}x_10pct_blocks_activity_capacity"


def _build_mrt_batch_economics_rows(
    mrt_candidates: list[MultiBatchPathwayResult],
    common_budget: float,
    max_batches_per_day: int,
    service_floor: float,
) -> list[MRTBatchEconomicsRow]:
    rows: list[MRTBatchEconomicsRow] = []
    for batches in range(1, max_batches_per_day + 1):
        candidate = _best_mrt_candidate_by_batch(mrt_candidates, batches)
        if candidate is None:
            continue
        gross_per_day = candidate.gross_required_doses_per_day
        usable_per_day = candidate.achieved_capacity_per_day
        gross_per_batch = 0.0 if candidate.batches_per_day <= 0 else gross_per_day / candidate.batches_per_day
        usable_per_batch = 0.0 if candidate.batches_per_day <= 0 else usable_per_day / candidate.batches_per_day
        decay_loss = max(0.0, gross_per_day - usable_per_day)
        total_scanners = candidate.additional_scanners
        total_injection_resources = candidate.new_rooms_constructed
        total_uptake_resources = candidate.new_rooms_constructed
        total_mrt_rooms = candidate.new_rooms_constructed + candidate.existing_rooms_connected_to_mrt
        base_annual_opex = max(0.0, candidate.total_annual_modelled_opex - candidate.annual_incremental_batch_opex)
        rows.append(
            MRTBatchEconomicsRow(
                batches_per_day=candidate.batches_per_day,
                clinical_administration_cohorts_per_day=candidate.administration_cohorts_per_day,
                completed_patients_per_day=candidate.achieved_capacity_per_day,
                revenue_generating_patients_per_day=candidate.revenue_generating_throughput_per_day,
                gross_activity_required_at_release_per_day=gross_per_day,
                usable_activity_at_administration_per_day=usable_per_day,
                decay_activity_loss_per_day=decay_loss,
                retention_fraction_at_administration=candidate.administration_retention_fraction,
                transport_only_retention_fraction=candidate.transport_only_retention_fraction,
                activity_required_at_administration_mbq_per_day=candidate.activity_required_at_administration_mbq_per_day,
                activity_required_at_release_mbq_per_day=candidate.activity_required_at_release_mbq_per_day,
                activity_required_at_eob_mbq_per_day=candidate.activity_required_at_eob_mbq_per_day,
                activity_decay_economic_value_status="not_calibrated",
                synthesis_yield_fraction=candidate.synthesis_yield_fraction,
                synthesis_retention_fraction=candidate.synthesis_retention_fraction,
                cyclotron_activity_capacity_mbq_per_day=candidate.cyclotron_activity_capacity_mbq_per_day,
                cyclotron_activity_capacity_status=candidate.cyclotron_activity_capacity_status,
                cyclotron_utilization_pct=candidate.cyclotron_utilization_pct,
                cyclotron_headroom_mbq_per_day=candidate.cyclotron_headroom_mbq_per_day,
                production_upgrade_required=candidate.production_upgrade_required,
                gross_activity_required_at_release_per_batch=gross_per_batch,
                usable_activity_at_administration_per_batch=usable_per_batch,
                scanners=total_scanners,
                injection_resources=total_injection_resources,
                uptake_resources=total_uptake_resources,
                mrt_rooms=total_mrt_rooms,
                guideway_segments=candidate.guideway_segments,
                endpoints=candidate.endpoints,
                actual_production_capacity_requirement_per_day=candidate.activity_required_at_eob_mbq_per_day,
                production_capacity_upgrade_status=_production_upgrade_status(candidate),
                production_expansion_pct_field=candidate.production_expansion_pct,
                capex=candidate.capex_used,
                budget_change=common_budget - candidate.capex_used,
                base_annual_opex=base_annual_opex,
                incremental_batch_annual_opex=candidate.annual_incremental_batch_opex,
                total_annual_opex=candidate.total_annual_modelled_opex,
                annual_revenue=candidate.annual_revenue,
                annual_net_operating_value=candidate.annual_net_operating_contribution,
                roi_pct=candidate.roi_pct,
                npv=candidate.npv,
                payback_years=candidate.payback_years,
                binding_constraint=candidate.binding_constraint,
                meets_service_floor=candidate.achieved_capacity_per_day + 1e-9 >= service_floor,
            )
        )
    return rows


def _build_mrt_batch_economics_transitions(rows: list[MRTBatchEconomicsRow]) -> list[MRTBatchEconomicsTransition]:
    transitions: list[MRTBatchEconomicsTransition] = []
    sorted_rows = sorted(rows, key=lambda r: r.batches_per_day)
    for idx in range(1, len(sorted_rows)):
        prev_row = sorted_rows[idx - 1]
        row = sorted_rows[idx]
        delta_patients = row.completed_patients_per_day - prev_row.completed_patients_per_day
        delta_revenue = row.annual_revenue - prev_row.annual_revenue
        delta_opex = row.total_annual_opex - prev_row.total_annual_opex
        delta_capex = row.capex - prev_row.capex
        delta_nov = row.annual_net_operating_value - prev_row.annual_net_operating_value
        per_patient_revenue = None if abs(delta_patients) <= 1e-12 else delta_revenue / delta_patients
        per_patient_opex = None if abs(delta_patients) <= 1e-12 else delta_opex / delta_patients
        transitions.append(
            MRTBatchEconomicsTransition(
                from_batches_per_day=prev_row.batches_per_day,
                to_batches_per_day=row.batches_per_day,
                delta_completed_patients_per_day=delta_patients,
                delta_annual_revenue=delta_revenue,
                delta_annual_opex=delta_opex,
                delta_capex=delta_capex,
                delta_annual_net_operating_value=delta_nov,
                incremental_revenue_per_additional_patient=per_patient_revenue,
                incremental_opex_per_additional_patient=per_patient_opex,
            )
        )
    return transitions


def _first_economically_unjustified_additional_batch(
    rows: list[MRTBatchEconomicsRow],
    transitions: list[MRTBatchEconomicsTransition],
) -> int | None:
    rows_by_batch = {row.batches_per_day: row for row in rows}
    for transition in transitions:
        from_row = rows_by_batch.get(transition.from_batches_per_day)
        if from_row is None:
            continue
        if from_row.meets_service_floor and transition.delta_annual_net_operating_value < 0.0:
            return transition.to_batches_per_day
    return None


def _minimum_service_compliant_tie(
    candidate: MultiBatchPathwayResult,
    required_throughput: float,
) -> tuple[float, float, int, float]:
    return (
        abs(candidate.achieved_capacity_per_day - required_throughput),
        candidate.capex_used,
        candidate.batches_per_day,
        -candidate.annual_net_operating_contribution,
    )


def _candidate_production_blocks(candidate: MultiBatchPathwayResult) -> int:
    return max(0, int(round(candidate.production_expansion_pct / 10.0)))


def _candidate_infra_units(candidate: MultiBatchPathwayResult) -> int:
    base = max(1, candidate.new_rooms_constructed // 4)
    inferred = candidate.guideway_segments - base
    return max(1, inferred)


def _evaluate_same_installed_mrt_at_batches(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    common_budget: float,
    installed: MultiBatchPathwayResult,
    batches_per_day: int,
) -> MultiBatchPathwayResult | None:
    return _build_mrt_economic_candidate(
        inputs=inputs,
        assumptions=assumptions,
        half_life_min=half_life_min,
        common_budget=common_budget,
        batches_per_day=batches_per_day,
        backbone_selected=installed.backbone_charged,
        transport_minutes=installed.transport_minutes,
        add_scanners=installed.additional_scanners,
        connected_rooms=installed.new_rooms_constructed,
        guideway_segments=installed.guideway_segments,
        endpoints=installed.endpoints,
        production_blocks=_candidate_production_blocks(installed),
        infra_units=_candidate_infra_units(installed),
    )


def _minimum_batches_for_required_service(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    common_budget: float,
    installed: MultiBatchPathwayResult,
    policy_max_batches_per_day: int,
) -> tuple[int, MultiBatchPathwayResult] | None:
    floor = inputs.target_patients_per_day
    for batches in range(1, max(1, policy_max_batches_per_day) + 1):
        candidate = _evaluate_same_installed_mrt_at_batches(
            inputs,
            assumptions,
            half_life_min,
            common_budget,
            installed,
            batches,
        )
        if candidate is None:
            continue
        if candidate.achieved_capacity_per_day + 1e-9 >= floor:
            return batches, candidate
    return None


def _build_requirement_normalized_comparison(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    common_budget: float,
    conventional_reference: ConventionalPlan,
    installed_mrt: MultiBatchPathwayResult,
    policy_max_batches_per_day: int,
) -> RequirementNormalizedEconomicComparison | None:
    min_batch_payload = _minimum_batches_for_required_service(
        inputs,
        assumptions,
        half_life_min,
        common_budget,
        installed_mrt,
        policy_max_batches_per_day,
    )
    if min_batch_payload is None:
        return None

    min_batches, mrt_at_required_service = min_batch_payload
    required_throughput = inputs.target_patients_per_day
    revenue_throughput = min(required_throughput, inputs.maximum_expected_demand_per_day)
    annual_revenue_required = revenue_throughput * assumptions.revenue_per_scan * assumptions.operating_days_per_year

    conventional_financials = getattr(conventional_reference, "financials", None)
    conventional_fixed_opex = float(getattr(conventional_financials, "annual_incremental_opex", 0.0))
    conventional_variable_opex = 0.0
    conventional_total_opex = conventional_fixed_opex + conventional_variable_opex

    mrt_variable_opex = _batch_annual_opex("MRT", min_batches, assumptions)
    mrt_fixed_opex = max(0.0, installed_mrt.total_annual_modelled_opex - installed_mrt.annual_incremental_batch_opex)
    mrt_total_opex = mrt_fixed_opex + mrt_variable_opex

    conventional_row = RequirementNormalizedPathwayResult(
        pathway="Conventional",
        required_throughput_per_day=required_throughput,
        revenue_throughput_per_day=revenue_throughput,
        installed_capacity_per_day=conventional_reference.achieved_capacity_per_day,
        operating_batches_per_day=1,
        annual_revenue=annual_revenue_required,
        fixed_annual_opex=conventional_fixed_opex,
        utilization_sensitive_annual_opex=conventional_variable_opex,
        annual_incremental_opex=conventional_total_opex,
        annual_net_operating_value=annual_revenue_required - conventional_total_opex,
        capex_used=conventional_reference.capex,
    )

    mrt_row = RequirementNormalizedPathwayResult(
        pathway="MRT",
        required_throughput_per_day=required_throughput,
        revenue_throughput_per_day=revenue_throughput,
        installed_capacity_per_day=installed_mrt.achieved_capacity_per_day,
        operating_batches_per_day=min_batches,
        annual_revenue=annual_revenue_required,
        fixed_annual_opex=mrt_fixed_opex,
        utilization_sensitive_annual_opex=mrt_variable_opex,
        annual_incremental_opex=mrt_total_opex,
        annual_net_operating_value=annual_revenue_required - mrt_total_opex,
        capex_used=installed_mrt.capex_used,
    )

    return RequirementNormalizedEconomicComparison(
        required_throughput_per_day=required_throughput,
        conventional=conventional_row,
        mrt=mrt_row,
        minimum_operating_batches_required_for_required_service=mrt_at_required_service.batches_per_day,
    )


def _build_full_capacity_mrt_opportunity(
    inputs: PlannerInputs,
    installed_mrt: MultiBatchPathwayResult,
) -> FullCapacityMRTOpportunity:
    return FullCapacityMRTOpportunity(
        installed_capacity_per_day=installed_mrt.achieved_capacity_per_day,
        required_throughput_per_day=inputs.target_patients_per_day,
        capacity_headroom_per_day=max(0.0, installed_mrt.achieved_capacity_per_day - inputs.target_patients_per_day),
        operating_batches_per_day=installed_mrt.batches_per_day,
        annual_revenue=installed_mrt.annual_revenue,
        annual_incremental_opex=installed_mrt.annual_incremental_opex,
        annual_net_operating_value=installed_mrt.annual_net_operating_contribution,
        roi_pct=installed_mrt.roi_pct,
        npv=installed_mrt.npv,
        payback_years=installed_mrt.payback_years,
        capex_used=installed_mrt.capex_used,
    )


def _greenfield_conventional_reference(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
) -> ConventionalPlan:
    # Greenfield requirement-derived mode treats the reference as a from-scratch design.
    # The non-physical seed keeps the legacy percentage-based production model from
    # treating a near-zero baseline as a real existing facility.
    synthetic_inputs = PlannerInputs(
        project_name=inputs.project_name,
        current_patients_per_day=1.0,
        target_patients_per_day=inputs.target_patients_per_day,
        maximum_expected_demand_per_day=inputs.maximum_expected_demand_per_day,
        current_scanners=0,
        current_injection_rooms=0,
        current_uptake_rooms=0,
        has_existing_cyclotron=False,
        current_usable_doses_per_day=inputs.target_patients_per_day,
        current_average_transport_min=inputs.current_average_transport_min,
        mrt_transport_min=inputs.mrt_transport_min,
        conventional_transport_min=inputs.conventional_transport_min,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide=inputs.representative_radionuclide,
        representative_half_life_min=inputs.representative_half_life_min,
    )
    return conventional(synthetic_inputs, assumptions, half_life_min)


def _conventional_administration_timing_diagnostics(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    reference: ConventionalPlan,
    mode: str,
) -> dict[str, float | list[float] | str]:
    total_scanners = reference.additional_scanners if mode == "greenfield_requirement_derived" else inputs.current_scanners + reference.additional_scanners
    total_injection_rooms = (
        reference.additional_injection_rooms
        if mode == "greenfield_requirement_derived"
        else inputs.current_injection_rooms + reference.additional_injection_rooms
    )
    total_uptake_rooms = (
        reference.additional_uptake_rooms
        if mode == "greenfield_requirement_derived"
        else inputs.current_uptake_rooms + reference.additional_uptake_rooms
    )
    transport_min = _conventional_transport_min(inputs)
    transport_retention = retention(transport_min, half_life_min)

    ledger_gross = 0.0
    if isinstance(reference.ledger, dict):
        ledger_gross = float(reference.ledger.get("required_gross_doses_per_day", 0.0))
    if ledger_gross <= 0.0:
        ledger_gross = reference.achieved_capacity_per_day / max(transport_retention, 1e-12)

    clinical_cohorts = max(1, assumptions.default_clinical_administration_cohorts_per_day)

    (
        completed,
        usable,
        _scanner_cap,
        _injection_cap,
        _uptake_cap,
        mean_wait,
        decay_minutes,
        per_batch_usable,
        per_batch_completed,
        release_times,
        queue_wait,
        per_batch_transport,
        binding_constraint,
    ) = _time_cohort_throughput(
        day_minutes=assumptions.operating_hours_per_day * 60.0,
        batches_per_day=clinical_cohorts,
        transport_minutes=transport_min,
        half_life_min=half_life_min,
        gross_doses_per_day=ledger_gross,
        scanners_total=total_scanners,
        injection_rooms_total=total_injection_rooms,
        uptake_rooms_total=total_uptake_rooms,
        guideway_cap=float("inf"),
        assumptions=assumptions,
    )

    administration_retention = 0.0 if ledger_gross <= 0.0 else usable / ledger_gross
    return {
        "administration_timing_method": "cohort_fixed_point",
        "administration_cohorts_per_day": float(clinical_cohorts),
        "timed_completed_patients_per_day": completed,
        "timed_usable_doses_per_day": usable,
        "transport_only_retention_fraction": transport_retention,
        "administration_retention_fraction": administration_retention,
        "mean_administration_wait_minutes": mean_wait,
        "per_batch_queue_wait_minutes": queue_wait,
        "per_batch_transport_minutes": per_batch_transport,
        "per_batch_decay_time_minutes": decay_minutes,
        "per_batch_usable_doses": per_batch_usable,
        "per_batch_completed_patients": per_batch_completed,
        "batch_release_times_minutes": release_times,
        "binding_constraint": binding_constraint,
    }


def _conventional_reference_summary(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    reference: ConventionalPlan,
    mode: str,
) -> tuple[dict[str, float | int | bool | str], float, float, float]:
    total_scanners = reference.additional_scanners if mode == "greenfield_requirement_derived" else inputs.current_scanners + reference.additional_scanners
    total_injection_rooms = reference.additional_injection_rooms if mode == "greenfield_requirement_derived" else inputs.current_injection_rooms + reference.additional_injection_rooms
    total_uptake_rooms = reference.additional_uptake_rooms if mode == "greenfield_requirement_derived" else inputs.current_uptake_rooms + reference.additional_uptake_rooms
    retained_fraction = float(reference.ledger.get("retained_activity_fraction", 0.0)) if isinstance(reference.ledger, dict) else 0.0
    gross_required_doses = 0.0 if retained_fraction <= 0.0 else reference.achieved_capacity_per_day / retained_fraction

    total_capex = float(reference.capex)
    existing_sunk = 0.0
    incremental = float(reference.capex)
    if mode == "greenfield_requirement_derived":
        existing_sunk = 0.0
        incremental = 0.0

    summary: dict[str, float | int | bool | str] = {
        "mode": mode,
        "greenfield_seed_is_non_physical": mode == "greenfield_requirement_derived",
        "greenfield_seed_current_patients_per_day": inputs.current_patients_per_day,
        "greenfield_seed_current_usable_doses_per_day": inputs.target_patients_per_day if mode == "greenfield_requirement_derived" else inputs.current_usable_doses_per_day,
        "required_patients_per_day": inputs.target_patients_per_day,
        "estimated_completed_patients_per_day": reference.achieved_capacity_per_day,
        "total_scanners_required": int(total_scanners),
        "patients_per_scanner_per_day": 0.0 if total_scanners <= 0 else reference.achieved_capacity_per_day / total_scanners,
        "total_scanner_capex": float(reference.additional_scanners) * assumptions.scanner_capex,
        "total_injection_resources_required": int(total_injection_rooms),
        "total_injection_resource_capex": float(reference.additional_injection_rooms) * assumptions.additional_room_capex,
        "total_uptake_resources_required": int(total_uptake_rooms),
        "total_uptake_resource_capex": float(reference.additional_uptake_rooms) * assumptions.additional_room_capex,
        "total_radiopharmacy_production_capacity_required": gross_required_doses,
        "production_expansion_pct": float(reference.required_production_increase_pct),
        "estimated_batches_per_day": int(math.ceil(max(reference.required_production_increase_pct, 0.0) / 10.0)),
        "production_configuration": f"{math.ceil(max(reference.required_production_increase_pct, 0.0) / 10.0)} expansion blocks (10%)",
        "cyclotron_required": bool(reference.cyclotron_required),
        "transport_assumption_min": _conventional_transport_min(inputs),
        "total_modeled_conventional_capex": total_capex,
        "existing_sunk_infrastructure_value": existing_sunk,
        "incremental_expansion_capex": incremental,
    }
    timing = _conventional_administration_timing_diagnostics(inputs, assumptions, half_life_min, reference, mode)
    summary["administration_timing_method"] = str(timing["administration_timing_method"])
    summary["administration_cohorts_per_day"] = int(float(timing["administration_cohorts_per_day"]))
    summary["timed_completed_patients_per_day"] = float(timing["timed_completed_patients_per_day"])
    summary["timed_usable_doses_per_day"] = float(timing["timed_usable_doses_per_day"])
    summary["transport_only_retention_fraction"] = float(timing["transport_only_retention_fraction"])
    summary["administration_retention_fraction"] = float(timing["administration_retention_fraction"])
    summary["timed_binding_constraint"] = str(timing["binding_constraint"])

    prescribed_activity_mbq = _prescribed_activity_mbq_per_patient(assumptions)
    synthesis_yield = _synthesis_yield_fraction(assumptions)
    synthesis_retention = _synthesis_retention_fraction(assumptions, half_life_min)
    synthesis_factor = max(synthesis_retention * synthesis_yield, 1e-12)
    completed_required = float(inputs.target_patients_per_day)
    activity_required_at_admin = completed_required * prescribed_activity_mbq
    admin_retention = float(timing["administration_retention_fraction"])
    if admin_retention <= 0.0:
        admin_retention = max(float(timing["transport_only_retention_fraction"]), 1e-12)
    activity_required_at_release = activity_required_at_admin / max(admin_retention, 1e-12)
    activity_required_at_eob = activity_required_at_release / synthesis_factor
    production_blocks = 0
    if isinstance(reference.ledger, dict):
        production_blocks = int(reference.ledger.get("production_expansion_blocks_10pct", 0))
    gross_release_capacity = 0.0
    if isinstance(reference.ledger, dict):
        gross_release_capacity = float(reference.ledger.get("expanded_gross_production_capacity_per_day", 0.0))
    if gross_release_capacity <= 0.0:
        gross_release_capacity = inputs.current_usable_doses_per_day * (1.0 + 0.1 * production_blocks)

    available_eob_capacity, cyclotron_capacity_status = _cyclotron_eob_capacity_mbq_per_day(
        inputs=inputs,
        assumptions=assumptions,
        gross_release_doses_per_day_capacity=gross_release_capacity,
        synthesis_retention_fraction=synthesis_retention,
        synthesis_yield_fraction=synthesis_yield,
        production_block_multiplier=1.0 + 0.1 * production_blocks,
    )
    baseline_eob_capacity, _ = _cyclotron_eob_capacity_mbq_per_day(
        inputs=inputs,
        assumptions=assumptions,
        gross_release_doses_per_day_capacity=inputs.current_usable_doses_per_day,
        synthesis_retention_fraction=synthesis_retention,
        synthesis_yield_fraction=synthesis_yield,
        production_block_multiplier=1.0,
    )
    capacity_is_calibrated = cyclotron_capacity_status != "not_calibrated"
    cyclotron_utilization_pct = 0.0 if (not capacity_is_calibrated or available_eob_capacity <= 0.0) else 100.0 * activity_required_at_eob / available_eob_capacity
    cyclotron_headroom = 0.0 if not capacity_is_calibrated else (available_eob_capacity - activity_required_at_eob)
    summary["activity_accounting_status"] = "assumption_based_activity_contract"
    summary["prescribed_activity_mbq_per_patient"] = prescribed_activity_mbq
    summary["activity_required_at_administration_mbq_per_day"] = activity_required_at_admin
    summary["activity_required_at_release_mbq_per_day"] = activity_required_at_release
    summary["activity_decay_loss_post_release_mbq_per_day"] = max(0.0, activity_required_at_release - activity_required_at_admin)
    summary["synthesis_yield_fraction"] = synthesis_yield
    summary["synthesis_processing_time_min"] = max(0.0, assumptions.synthesis_processing_time_min)
    summary["synthesis_retention_fraction"] = synthesis_retention
    summary["activity_required_at_eob_mbq_per_day"] = activity_required_at_eob
    summary["cyclotron_activity_capacity_mbq_per_day"] = available_eob_capacity
    summary["cyclotron_activity_capacity_status"] = cyclotron_capacity_status
    summary["cyclotron_utilization_pct"] = cyclotron_utilization_pct
    summary["cyclotron_headroom_mbq_per_day"] = cyclotron_headroom
    summary["production_upgrade_required"] = bool(capacity_is_calibrated and (activity_required_at_eob > baseline_eob_capacity + 1e-9))
    summary["activity_decay_economic_value"] = "not_calibrated"
    return summary, total_capex, existing_sunk, incremental


def run_equal_budget_economic_decision_optimization(
    inputs: PlannerInputs,
    assumptions: PlannerAssumptions,
    half_life_min: float,
    explicit_budget: float | None = None,
    max_batches_per_day: int = 6,
    comparison_budget_confirmed: bool = False,
    confirmed_comparison_budget: float | None = None,
    planning_mode: str = "existing_facility_expansion",
) -> EqualBudgetEconomicDecisionResult:
    if max_batches_per_day < 1:
        raise ValueError("max_batches_per_day must be at least 1.")

    if planning_mode not in {"existing_facility_expansion", "greenfield_requirement_derived"}:
        raise ValueError("planning_mode must be existing_facility_expansion or greenfield_requirement_derived.")

    if planning_mode == "greenfield_requirement_derived":
        conventional_reference = _greenfield_conventional_reference(inputs, assumptions, half_life_min)
    else:
        conventional_reference = conventional(inputs, assumptions, half_life_min)

    (
        conventional_summary,
        conventional_reference_capex,
        conventional_existing_sunk,
        conventional_incremental,
    ) = _conventional_reference_summary(inputs, assumptions, half_life_min, conventional_reference, planning_mode)

    if explicit_budget is None:
        initial_budget = conventional_reference_capex
        budget_source = "conventional_target_cost_anchor"
    else:
        initial_budget = float(explicit_budget)
        budget_source = "explicit_budget"

    comparison_budget_options = {
        "strict_original_budget": initial_budget,
        "full_requirement_budget": conventional_reference_capex,
    }
    if not comparison_budget_confirmed:
        return EqualBudgetEconomicDecisionResult(
            common_budget=initial_budget,
            budget_source="comparison_budget_unconfirmed",
            conventional_reference=conventional_reference,
            conventional_reference_mode=planning_mode,
            conventional_reference_resource_summary=conventional_summary,
            conventional_existing_sunk_infrastructure_capex=conventional_existing_sunk,
            conventional_incremental_expansion_capex=conventional_incremental,
            initial_budget=initial_budget,
            conventional_reference_capex=conventional_reference_capex,
            conventional_budget_difference_vs_initial=conventional_reference_capex - initial_budget,
            comparison_budget_confirmed=False,
            confirmed_comparison_budget=None,
            comparison_budget_options=comparison_budget_options,
            growth_max=None,
            economic_value=None,
            balanced=None,
            unconstrained_economic_optimum=None,
            minimum_service_compliant_design=None,
            primary_service_compliant_economic_optimum=None,
            primary_feasible_economic_recommendation=None,
            best_achievable_candidate=None,
            primary_feasible_candidate_count=0,
            requirement_normalized_comparison=None,
            full_capacity_mrt_opportunity=None,
            no_feasible_mrt_message="Comparison budget must be confirmed before primary MRT optimization.",
            policy_max_batches_per_day=max_batches_per_day,
            shared_project_unit_cost_basis=_shared_project_unit_cost_basis(assumptions),
        )

    common_budget = initial_budget if confirmed_comparison_budget is None else float(confirmed_comparison_budget)
    if common_budget < 0.0:
        raise ValueError("confirmed_comparison_budget must be non-negative.")

    mrt_candidates = _enumerate_mrt_candidates(inputs, assumptions, half_life_min, common_budget, max_batches_per_day)
    if not mrt_candidates:
        raise ValueError("No feasible MRT economic decision candidates found.")

    growth_max = _select_best_view(mrt_candidates, _GROWTH_MAX_SCORE_WEIGHTS, "Growth-Max", inputs, common_budget)
    economic_value = _select_best_view(mrt_candidates, _ECONOMIC_VALUE_SCORE_WEIGHTS, "Economic-Value", inputs, common_budget)
    balanced = _select_best_view(mrt_candidates, _BALANCED_SCORE_WEIGHTS, "Balanced MRT", inputs, common_budget)
    unconstrained_economic_optimum = max(mrt_candidates, key=_primary_recommendation_tie)

    floor = inputs.target_patients_per_day
    feasible_primary = [
        c
        for c in mrt_candidates
        if c.achieved_capacity_per_day + 1e-9 >= floor and c.capex_used <= common_budget + 1e-9
    ]
    minimum_service_compliant_design = (
        min(feasible_primary, key=lambda c: _minimum_service_compliant_tie(c, floor))
        if feasible_primary
        else None
    )
    primary_recommendation = max(feasible_primary, key=_primary_recommendation_tie) if feasible_primary else None
    best_achievable = max(mrt_candidates, key=lambda c: (c.achieved_capacity_per_day, c.annual_net_operating_contribution, -c.capex_used))
    mrt_batch_rows = _build_mrt_batch_economics_rows(mrt_candidates, common_budget, max_batches_per_day, floor)
    mrt_batch_transitions = _build_mrt_batch_economics_transitions(mrt_batch_rows)
    minimum_service_compliant_batch_count = None
    for row in sorted(mrt_batch_rows, key=lambda r: r.batches_per_day):
        if row.meets_service_floor:
            minimum_service_compliant_batch_count = row.batches_per_day
            break
    highest_throughput_batch_count = None
    if mrt_batch_rows:
        highest_throughput_batch_count = max(
            mrt_batch_rows,
            key=lambda r: (r.completed_patients_per_day, r.annual_net_operating_value, -r.capex),
        ).batches_per_day
    first_unjustified_batch = _first_economically_unjustified_additional_batch(mrt_batch_rows, mrt_batch_transitions)
    primary_service_compliant_batch_count = None if primary_recommendation is None else primary_recommendation.batches_per_day
    requirement_normalized_comparison = None
    full_capacity_mrt_opportunity = None
    if primary_recommendation is not None:
        requirement_normalized_comparison = _build_requirement_normalized_comparison(
            inputs,
            assumptions,
            half_life_min,
            common_budget,
            conventional_reference,
            primary_recommendation,
            max_batches_per_day,
        )
        full_capacity_mrt_opportunity = _build_full_capacity_mrt_opportunity(inputs, primary_recommendation)
    no_feasible_message = ""
    if primary_recommendation is None:
        if "guideway_network" in best_achievable.binding_constraint.split("/") and best_achievable.binding_constraint_calibration == "heuristic_network_capacity":
            no_feasible_message = (
                "No MRT candidate reached the required throughput within the confirmed budget under the current search and constraints. "
                "The best candidate is provisionally limited by a heuristic guideway-capacity relationship and should not be interpreted "
                "as a validated physical impossibility without guideway calibration."
            )
        else:
            no_feasible_message = (
                "No feasible MRT configuration in the evaluated design space satisfies the required patient throughput "
                "within the available capital budget."
            )

    return EqualBudgetEconomicDecisionResult(
        common_budget=common_budget,
        budget_source=budget_source,
        conventional_reference=conventional_reference,
        conventional_reference_mode=planning_mode,
        conventional_reference_resource_summary=conventional_summary,
        conventional_existing_sunk_infrastructure_capex=conventional_existing_sunk,
        conventional_incremental_expansion_capex=conventional_incremental,
        initial_budget=initial_budget,
        conventional_reference_capex=conventional_reference_capex,
        conventional_budget_difference_vs_initial=conventional_reference_capex - initial_budget,
        comparison_budget_confirmed=True,
        confirmed_comparison_budget=common_budget,
        comparison_budget_options=comparison_budget_options,
        growth_max=growth_max,
        economic_value=economic_value,
        balanced=balanced,
        unconstrained_economic_optimum=unconstrained_economic_optimum,
        minimum_service_compliant_design=minimum_service_compliant_design,
        primary_service_compliant_economic_optimum=primary_recommendation,
        primary_feasible_economic_recommendation=primary_recommendation,
        best_achievable_candidate=best_achievable,
        primary_feasible_candidate_count=len(feasible_primary),
        requirement_normalized_comparison=requirement_normalized_comparison,
        full_capacity_mrt_opportunity=full_capacity_mrt_opportunity,
        mrt_batch_economics_rows=mrt_batch_rows,
        mrt_batch_economics_transitions=mrt_batch_transitions,
        minimum_service_compliant_mrt_batch_count=minimum_service_compliant_batch_count,
        primary_service_compliant_economic_batch_count=primary_service_compliant_batch_count,
        highest_throughput_mrt_batch_count=highest_throughput_batch_count,
        first_economically_unjustified_additional_batch=first_unjustified_batch,
        no_feasible_mrt_message=no_feasible_message,
        policy_max_batches_per_day=max_batches_per_day,
        shared_project_unit_cost_basis=_shared_project_unit_cost_basis(assumptions),
    )

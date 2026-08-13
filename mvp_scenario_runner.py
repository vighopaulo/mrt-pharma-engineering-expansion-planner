from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from architecture_optimizer import ArchitectureCandidate, FacilityEnvelope, OptimizationDemand, evaluate_architecture_candidate
from f18_decay_model import F18ActivityInputs, F18OperatingDayResult, evaluate_f18_operating_day, load_f18_half_life_minutes
from lifecycle_economics import DemandTrajectory, LifecycleEconomicResult, build_demand_trajectory, compare_lifecycle_results, evaluate_lifecycle_economics
from models import PlannerAssumptions
from operating_day_scheduler import BatchRelease, OperatingDayInputs, OperatingDayScheduleResult, schedule_operating_day


Pathway = Literal["Conventional", "MRT"]


@dataclass(frozen=True)
class MVPScenarioInput:
    project_name: str
    daily_demand_patients: int
    analysis_years: int
    discount_rate_pct: float
    operating_days_per_year: int
    revenue_per_scan: float
    prescribed_activity_mbq_per_patient: float
    batch_count: int
    batch_release_activity_mbq: float
    max_scanners: int
    max_injection_resources: int
    max_uptake_resources: int
    max_mrt_endpoints: int
    max_conventional_distribution_concurrency: int
    max_mrt_distribution_concurrency: int
    conventional_transport_minutes: float
    mrt_transport_minutes: float
    injection_service_minutes: float
    uptake_minutes: float
    scanner_service_minutes: float
    operating_day_minutes: float = 1080.0
    annual_demand_growth_rate: float = 0.0
    explicit_daily_demand_by_year: tuple[float, ...] | None = None
    batch_release_times_minutes: tuple[float, ...] | None = None
    min_scanners: int = 1
    min_injection_resources: int = 1
    min_uptake_resources: int = 1
    min_mrt_endpoints: int = 1


@dataclass(frozen=True)
class MVPArchitectureCandidate:
    pathway: Pathway
    scanners: int
    injection_resources: int
    uptake_resources: int
    endpoints: int
    distribution_concurrency: int
    batch_count: int
    batch_release_times_minutes: tuple[float, ...]
    batch_patient_counts: tuple[int, ...]
    theoretical_clinical_capacity_per_day: float
    scheduler_completed_patients_per_day: int
    f18_activity_supported_completed_patients_per_day: int
    lifecycle_installed_capacity_per_day: float
    lifecycle_revenue_throughput_per_day: float
    capex: float
    annual_opex: float
    lifecycle: LifecycleEconomicResult
    final_npv: float
    payback_year: float | None
    schedule_result: OperatingDayScheduleResult
    f18_result: F18OperatingDayResult
    trace: tuple[str, ...]


@dataclass(frozen=True)
class MVPPathwayResult:
    pathway: Pathway
    optimal_candidate: MVPArchitectureCandidate
    feasible_candidate_count: int
    evaluated_candidates: tuple[MVPArchitectureCandidate, ...]


@dataclass(frozen=True)
class MVPScenarioComparisonResult:
    incremental_capex_mrt_minus_conventional: float
    incremental_annual_opex_mrt_minus_conventional: float
    incremental_completed_patients_per_day_mrt_minus_conventional: int
    incremental_final_npv_mrt_minus_conventional: float
    economic_crossover_year: float | None
    winning_pathway_by_10_year_npv: Pathway


@dataclass(frozen=True)
class MVPScenarioRunResult:
    scenario_summary: dict[str, Any]
    demand_trajectory: DemandTrajectory
    conventional: MVPPathwayResult
    mrt: MVPPathwayResult
    comparison: MVPScenarioComparisonResult
    f18_half_life_minutes: float


def _ensure_tuple_floats(values: tuple[float, ...] | list[float] | None) -> tuple[float, ...] | None:
    if values is None:
        return None
    return tuple(float(value) for value in values)


def _ensure_tuple_ints(values: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    return tuple(int(value) for value in values)


def _build_even_batch_schedule(scenario: MVPScenarioInput) -> tuple[list[BatchRelease], tuple[float, ...], tuple[int, ...]]:
    if scenario.batch_count < 1:
        raise ValueError("batch_count must be at least 1")
    if scenario.batch_release_times_minutes is not None and len(scenario.batch_release_times_minutes) != scenario.batch_count:
        raise ValueError("batch_release_times_minutes length must equal batch_count")

    if scenario.batch_release_times_minutes is None:
        interval = scenario.operating_day_minutes / scenario.batch_count
        release_times = tuple(index * interval for index in range(scenario.batch_count))
    else:
        release_times = tuple(float(value) for value in scenario.batch_release_times_minutes)

    total_patients = int(scenario.daily_demand_patients)
    base = total_patients // scenario.batch_count
    remainder = total_patients % scenario.batch_count
    batch_counts = tuple(base + 1 if index < remainder else base for index in range(scenario.batch_count))

    batch_releases = [
        BatchRelease(batch_id=index + 1, release_time_minutes=release_times[index], patients_in_batch=batch_counts[index])
        for index in range(scenario.batch_count)
    ]
    return batch_releases, release_times, batch_counts


def _build_demand_trajectory(scenario: MVPScenarioInput) -> DemandTrajectory:
    explicit = _ensure_tuple_floats(scenario.explicit_daily_demand_by_year)
    return build_demand_trajectory(
        analysis_years=scenario.analysis_years,
        starting_demand_per_day=float(scenario.daily_demand_patients),
        annual_growth_rate=scenario.annual_demand_growth_rate,
        explicit_daily_demand_by_year=list(explicit) if explicit is not None else None,
    )


def _build_lifecycle_result(
    *,
    scenario: MVPScenarioInput,
    actual_completed_patients_per_day: int,
    capex: float,
    annual_opex: float,
    demand_trajectory: DemandTrajectory,
) -> LifecycleEconomicResult:
    return evaluate_lifecycle_economics(
        initial_capex=capex,
        installed_capacity_per_day=float(actual_completed_patients_per_day),
        annual_opex=annual_opex,
        revenue_per_scan=scenario.revenue_per_scan,
        operating_days_per_year=scenario.operating_days_per_year,
        discount_rate_pct=scenario.discount_rate_pct,
        analysis_years=scenario.analysis_years,
        starting_demand_per_day=float(scenario.daily_demand_patients),
        annual_demand_growth_rate=scenario.annual_demand_growth_rate,
        explicit_daily_demand_by_year=list(demand_trajectory.daily_demand_by_year),
    )


def _candidate_trace(
    *,
    pathway: Pathway,
    scanners: int,
    injection_resources: int,
    uptake_resources: int,
    endpoints: int,
    distribution_concurrency: int,
    theoretical_capacity: float,
    scheduler_completed: int,
    f18_supported_completed: int,
    lifecycle_revenue_throughput: float,
    final_npv: float,
) -> tuple[str, ...]:
    return (
        f"Architecture: {pathway} scanners={scanners}, injection={injection_resources}, uptake={uptake_resources}, endpoints={endpoints}, distribution_concurrency={distribution_concurrency}",
        f"Theoretical clinical capacity/day: {theoretical_capacity}",
        f"Scheduler completed/day: {scheduler_completed}",
        f"F-18-supported completed/day: {f18_supported_completed}",
        f"Lifecycle revenue throughput/day: {lifecycle_revenue_throughput}",
        f"Final 10-year NPV: {final_npv}",
    )


def evaluate_mvp_candidate(
    *,
    scenario: MVPScenarioInput,
    pathway: Pathway,
    scanners: int,
    injection_resources: int,
    uptake_resources: int,
    endpoints: int,
    distribution_concurrency: int,
    demand_trajectory: DemandTrajectory | None = None,
    batch_releases: list[BatchRelease] | None = None,
    release_times_minutes: tuple[float, ...] | None = None,
    batch_counts: tuple[int, ...] | None = None,
) -> MVPArchitectureCandidate | None:
    if demand_trajectory is None:
        demand_trajectory = _build_demand_trajectory(scenario)
    if batch_releases is None or release_times_minutes is None or batch_counts is None:
        batch_releases, release_times_minutes, batch_counts = _build_even_batch_schedule(scenario)

    assumptions = PlannerAssumptions(
        analysis_years=scenario.analysis_years,
        discount_rate_pct=scenario.discount_rate_pct,
        operating_days_per_year=scenario.operating_days_per_year,
        revenue_per_scan=scenario.revenue_per_scan,
        scanner_cycle_min=scenario.scanner_service_minutes,
        injection_cycle_min=scenario.injection_service_minutes,
        uptake_cycle_min=scenario.uptake_minutes,
        operating_hours_per_day=scenario.operating_day_minutes / 60.0,
    )

    optimization_demand = OptimizationDemand(
        starting_demand_per_day=float(scenario.daily_demand_patients),
        annual_growth_rate=scenario.annual_demand_growth_rate,
        explicit_daily_demand_by_year=list(demand_trajectory.daily_demand_by_year),
    )
    base_architecture = evaluate_architecture_candidate(
        pathway=pathway,
        scanners=scanners,
        injection_resources=injection_resources,
        uptake_resources=uptake_resources,
        endpoints=endpoints,
        assumptions=assumptions,
        demand=optimization_demand,
    )
    if base_architecture is None:
        return None

    transport_minutes = scenario.conventional_transport_minutes if pathway == "Conventional" else scenario.mrt_transport_minutes
    schedule_inputs = OperatingDayInputs(
        operating_day_minutes=scenario.operating_day_minutes,
        batch_releases=batch_releases,
        transport_minutes=transport_minutes,
        injection_service_minutes=scenario.injection_service_minutes,
        uptake_minutes=scenario.uptake_minutes,
        scanner_service_minutes=scenario.scanner_service_minutes,
        injection_resources=injection_resources,
        uptake_resources=uptake_resources,
        scanners=scanners,
        distribution_concurrency=distribution_concurrency,
    )
    schedule_result = schedule_operating_day(schedule_inputs)
    release_activity = {batch.batch_id: float(scenario.batch_release_activity_mbq) for batch in batch_releases}
    release_time_lookup = {batch.batch_id: batch.release_time_minutes for batch in batch_releases}
    f18_result = evaluate_f18_operating_day(
        F18ActivityInputs(
            operating_day_schedule=schedule_result,
            batch_release_times_minutes_by_batch_id=release_time_lookup,
            activity_available_at_release_mbq_by_batch_id=release_activity,
            prescribed_activity_mbq_per_patient=scenario.prescribed_activity_mbq_per_patient,
        )
    )
    actual_completed = f18_result.activity_supported_completed_patients
    if actual_completed <= 0:
        return None

    lifecycle = _build_lifecycle_result(
        scenario=scenario,
        actual_completed_patients_per_day=actual_completed,
        capex=base_architecture.capex,
        annual_opex=base_architecture.annual_opex,
        demand_trajectory=demand_trajectory,
    )
    lifecycle_revenue_throughput = lifecycle.annual_rows[0].patients_served_per_day if lifecycle.annual_rows else 0.0
    trace = _candidate_trace(
        pathway=pathway,
        scanners=scanners,
        injection_resources=injection_resources,
        uptake_resources=uptake_resources,
        endpoints=endpoints,
        distribution_concurrency=distribution_concurrency,
        theoretical_capacity=base_architecture.installed_capacity_per_day,
        scheduler_completed=schedule_result.completed_patients,
        f18_supported_completed=actual_completed,
        lifecycle_revenue_throughput=lifecycle_revenue_throughput,
        final_npv=lifecycle.final_npv,
    )

    return MVPArchitectureCandidate(
        pathway=pathway,
        scanners=scanners,
        injection_resources=injection_resources,
        uptake_resources=uptake_resources,
        endpoints=endpoints,
        distribution_concurrency=distribution_concurrency,
        batch_count=scenario.batch_count,
        batch_release_times_minutes=release_times_minutes,
        batch_patient_counts=batch_counts,
        theoretical_clinical_capacity_per_day=base_architecture.installed_capacity_per_day,
        scheduler_completed_patients_per_day=schedule_result.completed_patients,
        f18_activity_supported_completed_patients_per_day=actual_completed,
        lifecycle_installed_capacity_per_day=float(actual_completed),
        lifecycle_revenue_throughput_per_day=lifecycle_revenue_throughput,
        capex=base_architecture.capex,
        annual_opex=base_architecture.annual_opex,
        lifecycle=lifecycle,
        final_npv=lifecycle.final_npv,
        payback_year=lifecycle.payback_year,
        schedule_result=schedule_result,
        f18_result=f18_result,
        trace=trace,
    )


def _optimize_pathway(
    *,
    scenario: MVPScenarioInput,
    pathway: Pathway,
    demand_trajectory: DemandTrajectory,
    batch_releases: list[BatchRelease],
    release_times_minutes: tuple[float, ...],
    batch_counts: tuple[int, ...],
) -> MVPPathwayResult:
    evaluated_candidates: list[MVPArchitectureCandidate] = []

    if pathway == "Conventional":
        for scanners in range(scenario.min_scanners, scenario.max_scanners + 1):
            for injection_resources in range(scenario.min_injection_resources, scenario.max_injection_resources + 1):
                for uptake_resources in range(scenario.min_uptake_resources, scenario.max_uptake_resources + 1):
                    for distribution_concurrency in range(1, scenario.max_conventional_distribution_concurrency + 1):
                        candidate = evaluate_mvp_candidate(
                            scenario=scenario,
                            pathway=pathway,
                            scanners=scanners,
                            injection_resources=injection_resources,
                            uptake_resources=uptake_resources,
                            endpoints=0,
                            distribution_concurrency=distribution_concurrency,
                            demand_trajectory=demand_trajectory,
                            batch_releases=batch_releases,
                            release_times_minutes=release_times_minutes,
                            batch_counts=batch_counts,
                        )
                        if candidate is not None:
                            evaluated_candidates.append(candidate)
    else:
        for scanners in range(scenario.min_scanners, scenario.max_scanners + 1):
            for injection_resources in range(scenario.min_injection_resources, scenario.max_injection_resources + 1):
                for uptake_resources in range(scenario.min_uptake_resources, scenario.max_uptake_resources + 1):
                    for endpoints in range(scenario.min_mrt_endpoints, scenario.max_mrt_endpoints + 1):
                        max_concurrency = min(scenario.max_mrt_distribution_concurrency, endpoints)
                        for distribution_concurrency in range(1, max_concurrency + 1):
                            candidate = evaluate_mvp_candidate(
                                scenario=scenario,
                                pathway=pathway,
                                scanners=scanners,
                                injection_resources=injection_resources,
                                uptake_resources=uptake_resources,
                                endpoints=endpoints,
                                distribution_concurrency=distribution_concurrency,
                                demand_trajectory=demand_trajectory,
                                batch_releases=batch_releases,
                                release_times_minutes=release_times_minutes,
                                batch_counts=batch_counts,
                            )
                            if candidate is not None:
                                evaluated_candidates.append(candidate)

    if not evaluated_candidates:
        raise ValueError(f"No feasible {pathway} candidates found for the MVP scenario.")

    optimal = max(
        evaluated_candidates,
        key=lambda candidate: (
            candidate.final_npv,
            candidate.f18_activity_supported_completed_patients_per_day,
            candidate.scheduler_completed_patients_per_day,
            -candidate.capex,
            -candidate.annual_opex,
            -candidate.endpoints,
            -candidate.distribution_concurrency,
        ),
    )

    return MVPPathwayResult(
        pathway=pathway,
        optimal_candidate=optimal,
        feasible_candidate_count=len(evaluated_candidates),
        evaluated_candidates=tuple(evaluated_candidates),
    )


def run_mvp_scenario(scenario: MVPScenarioInput) -> MVPScenarioRunResult:
    demand_trajectory = _build_demand_trajectory(scenario)
    batch_releases, release_times_minutes, batch_counts = _build_even_batch_schedule(scenario)

    conventional = _optimize_pathway(
        scenario=scenario,
        pathway="Conventional",
        demand_trajectory=demand_trajectory,
        batch_releases=batch_releases,
        release_times_minutes=release_times_minutes,
        batch_counts=batch_counts,
    )
    mrt = _optimize_pathway(
        scenario=scenario,
        pathway="MRT",
        demand_trajectory=demand_trajectory,
        batch_releases=batch_releases,
        release_times_minutes=release_times_minutes,
        batch_counts=batch_counts,
    )

    lifecycle_comparison = compare_lifecycle_results(
        conventional=conventional.optimal_candidate.lifecycle,
        mrt=mrt.optimal_candidate.lifecycle,
    )

    winning_pathway = "MRT" if mrt.optimal_candidate.final_npv > conventional.optimal_candidate.final_npv else "Conventional"

    comparison = MVPScenarioComparisonResult(
        incremental_capex_mrt_minus_conventional=mrt.optimal_candidate.capex - conventional.optimal_candidate.capex,
        incremental_annual_opex_mrt_minus_conventional=mrt.optimal_candidate.annual_opex - conventional.optimal_candidate.annual_opex,
        incremental_completed_patients_per_day_mrt_minus_conventional=(
            mrt.optimal_candidate.f18_activity_supported_completed_patients_per_day
            - conventional.optimal_candidate.f18_activity_supported_completed_patients_per_day
        ),
        incremental_final_npv_mrt_minus_conventional=mrt.optimal_candidate.final_npv - conventional.optimal_candidate.final_npv,
        economic_crossover_year=lifecycle_comparison.economic_crossover_year,
        winning_pathway_by_10_year_npv=winning_pathway,
    )

    scenario_summary = {
        "project_name": scenario.project_name,
        "operating_day_minutes": scenario.operating_day_minutes,
        "daily_demand_patients": scenario.daily_demand_patients,
        "analysis_years": scenario.analysis_years,
        "discount_rate_pct": scenario.discount_rate_pct,
        "operating_days_per_year": scenario.operating_days_per_year,
        "revenue_per_scan": scenario.revenue_per_scan,
        "prescribed_activity_mbq_per_patient": scenario.prescribed_activity_mbq_per_patient,
        "batch_count": scenario.batch_count,
        "batch_release_activity_mbq": scenario.batch_release_activity_mbq,
        "batch_release_times_minutes": tuple(release_times_minutes),
        "batch_patient_counts": tuple(batch_counts),
        "f18_half_life_minutes": load_f18_half_life_minutes(),
        "demand_trajectory": tuple(demand_trajectory.daily_demand_by_year),
        "demand_source": demand_trajectory.source,
        "fixed_envelope": {
            "max_scanners": scenario.max_scanners,
            "max_injection_resources": scenario.max_injection_resources,
            "max_uptake_resources": scenario.max_uptake_resources,
            "max_mrt_endpoints": scenario.max_mrt_endpoints,
        },
    }

    return MVPScenarioRunResult(
        scenario_summary=scenario_summary,
        demand_trajectory=demand_trajectory,
        conventional=conventional,
        mrt=mrt,
        comparison=comparison,
        f18_half_life_minutes=load_f18_half_life_minutes(),
    )

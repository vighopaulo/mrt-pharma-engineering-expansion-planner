from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from statistics import mean
from typing import Any, Iterable, Literal, Mapping, Sequence

from decision_pipeline import (
    NativeBottleneckSummary,
    NativeDecisionComparisonResult,
    NativeDecisionPipelineScenario,
    Pathway,
    run_native_decision_pipeline,
)
from infrastructure_capex import InfrastructureCapexResult
from infrastructure_opex import InfrastructureOpexResult
from lifecycle_economics import LifecycleComparisonResult, LifecycleEconomicResult, compare_lifecycle_results, evaluate_lifecycle_economics


ReliabilityThroughputCase = Literal["mean", "p50", "p5"]


@dataclass(frozen=True)
class NativeReliabilityDistributionSummary:
    observations: tuple[float, ...]
    run_count: int
    mean: float
    minimum: float
    maximum: float
    p5: float
    p50: float
    p90: float
    p95: float
    p99: float


@dataclass(frozen=True)
class NativeReliabilityRunReference:
    seed: int
    comparison_trace_id: str
    demand_trace_id: str
    pathway_trace_ids: Mapping[Pathway, str]
    completed_patients_per_day_by_pathway: Mapping[Pathway, int] = field(default_factory=dict)
    completion_percentage_by_pathway: Mapping[Pathway, float] = field(default_factory=dict)
    bottleneck_by_pathway: Mapping[Pathway, NativeBottleneckSummary] = field(default_factory=dict)
    raw_schedule_completed_patients_per_day_by_pathway: Mapping[Pathway, int] = field(default_factory=dict)
    effective_completed_patients_per_day_by_pathway: Mapping[Pathway, int] = field(default_factory=dict)
    decay_infeasible_patients_by_pathway: Mapping[Pathway, int] = field(default_factory=dict)


@dataclass(frozen=True)
class NativeReliabilityRunResult:
    seed: int
    native_result: NativeDecisionComparisonResult
    reference: NativeReliabilityRunReference


@dataclass(frozen=True)
class NativeReliabilityPathwaySummary:
    pathway: Pathway
    throughput_distribution: NativeReliabilityDistributionSummary
    raw_schedule_completed_distribution: NativeReliabilityDistributionSummary
    completion_percentage_distribution: NativeReliabilityDistributionSummary
    probability_meeting_target_demand: float
    probability_below_thresholds: Mapping[float, float]
    bottleneck_counts: Mapping[str, int]
    bottleneck_frequencies: Mapping[str, float]
    worst_runs: tuple[NativeReliabilityRunReference, ...]
    throughput_supportable_at_90pct_reliability: float
    throughput_supportable_at_95pct_reliability: float
    throughput_supportable_at_99pct_reliability: float
    decay_loss_distribution_mbq: NativeReliabilityDistributionSummary
    retained_fraction_distribution: NativeReliabilityDistributionSummary
    potential_shortfall_distribution_mbq: NativeReliabilityDistributionSummary
    capex_result: InfrastructureCapexResult
    opex_result: InfrastructureOpexResult
    source_run_reference: NativeReliabilityRunReference


@dataclass(frozen=True)
class NativeReliabilityLifecycleCase:
    label: ReliabilityThroughputCase
    conventional_throughput_per_day: float
    mrt_throughput_per_day: float
    conventional_lifecycle_result: LifecycleEconomicResult
    mrt_lifecycle_result: LifecycleEconomicResult
    lifecycle_comparison_result: LifecycleComparisonResult
    economic_winner: Pathway | Literal["Tie"]


@dataclass(frozen=True)
class NativeReliabilityProvenance:
    request: NativeDecisionPipelineScenario
    seeds: tuple[int, ...]
    run_references_by_seed: Mapping[int, NativeReliabilityRunReference]
    aggregate_trace_id: str
    source_modules: tuple[str, ...] = ("decision_pipeline", "lifecycle_economics")


@dataclass(frozen=True)
class NativeReliabilityComparisonResult:
    request: NativeDecisionPipelineScenario
    seeds: tuple[int, ...]
    run_count: int
    run_results: tuple[NativeReliabilityRunResult, ...]
    conventional: NativeReliabilityPathwaySummary
    mrt: NativeReliabilityPathwaySummary
    lifecycle_cases: tuple[NativeReliabilityLifecycleCase, ...]
    economic_winner_by_case: Mapping[ReliabilityThroughputCase, Pathway | Literal["Tie"]]
    stable_economic_preference: bool
    provenance: NativeReliabilityProvenance
    trace_id: str
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]


def _trace_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _quantile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(float(value) for value in values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (len(sorted_values) - 1) * float(percentile) / 100.0
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = rank - lower
    return float(sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction)


def _validate_seeds(seeds: Iterable[int]) -> tuple[int, ...]:
    seed_values = tuple(seeds)
    if not seed_values:
        raise ValueError("seeds must not be empty")
    for seed in seed_values:
        if not isinstance(seed, int):
            raise TypeError("seeds must contain integers")
    return seed_values


def _validate_thresholds(thresholds: Sequence[float]) -> tuple[float, ...]:
    threshold_values = tuple(float(value) for value in thresholds)
    for threshold in threshold_values:
        if threshold < 0.0:
            raise ValueError("throughput thresholds must be non-negative")
    return threshold_values


def _distribution_summary(values: Sequence[float]) -> NativeReliabilityDistributionSummary:
    observations = tuple(float(value) for value in values)
    return NativeReliabilityDistributionSummary(
        observations=observations,
        run_count=len(observations),
        mean=mean(observations) if observations else 0.0,
        minimum=min(observations) if observations else 0.0,
        maximum=max(observations) if observations else 0.0,
        p5=_quantile(observations, 5.0),
        p50=_quantile(observations, 50.0),
        p90=_quantile(observations, 90.0),
        p95=_quantile(observations, 95.0),
        p99=_quantile(observations, 99.0),
    )


def _actual_throughput_supportable_at_reliability(values: Sequence[float], reliability_pct: float) -> float:
    return _quantile(values, 100.0 - float(reliability_pct))


def _limit_worst_run_count(worst_run_count: int, available: int) -> int:
    if worst_run_count < 1:
        raise ValueError("worst_run_count must be at least 1")
    return min(int(worst_run_count), available)


def _run_reference(run_result: NativeReliabilityRunResult) -> NativeReliabilityRunReference:
    return run_result.reference


def _decay_metrics_from_native(run_result: NativeReliabilityRunResult, pathway: Pathway) -> tuple[float, float, float]:
    pathway_result = run_result.native_result.conventional if pathway == "Conventional" else run_result.native_result.mrt
    decay_summary = getattr(pathway_result, "decay_summary", None)
    if decay_summary is None:
        return 0.0, 1.0, 0.0
    return (
        float(getattr(decay_summary, "overall_physical_decay_loss_mbq", getattr(decay_summary, "overall_decay_loss_mbq", 0.0))),
        float(getattr(decay_summary, "mean_retained_fraction", 1.0)),
        float(getattr(decay_summary, "total_potential_shortfall_mbq_if_no_upstream_adjustment", 0.0)),
    )


def _build_run_result(request: NativeDecisionPipelineScenario, seed: int) -> NativeReliabilityRunResult:
    native_result = run_native_decision_pipeline(replace(request, seed=seed))
    conventional_operational = native_result.conventional.operational_result
    mrt_operational = native_result.mrt.operational_result

    conventional_raw_completed = int(getattr(conventional_operational, "schedule_completed_patients", conventional_operational.patients_completed))
    mrt_raw_completed = int(getattr(mrt_operational, "schedule_completed_patients", mrt_operational.patients_completed))
    conventional_effective_completed = int(getattr(conventional_operational, "decay_feasible_completed_patients", conventional_operational.patients_completed))
    mrt_effective_completed = int(getattr(mrt_operational, "decay_feasible_completed_patients", mrt_operational.patients_completed))
    conventional_infeasible = int(getattr(conventional_operational, "decay_infeasible_patients", 0))
    mrt_infeasible = int(getattr(mrt_operational, "decay_infeasible_patients", 0))

    reference = NativeReliabilityRunReference(
        seed=seed,
        comparison_trace_id=native_result.provenance.comparison_trace_id,
        demand_trace_id=native_result.provenance.demand_trace_id,
        pathway_trace_ids={
            "Conventional": native_result.conventional.trace_id,
            "MRT": native_result.mrt.trace_id,
        },
        completed_patients_per_day_by_pathway={
            "Conventional": conventional_effective_completed,
            "MRT": mrt_effective_completed,
        },
        raw_schedule_completed_patients_per_day_by_pathway={
            "Conventional": conventional_raw_completed,
            "MRT": mrt_raw_completed,
        },
        effective_completed_patients_per_day_by_pathway={
            "Conventional": conventional_effective_completed,
            "MRT": mrt_effective_completed,
        },
        decay_infeasible_patients_by_pathway={
            "Conventional": conventional_infeasible,
            "MRT": mrt_infeasible,
        },
        completion_percentage_by_pathway={
            "Conventional": conventional_operational.completion_percentage,
            "MRT": mrt_operational.completion_percentage,
        },
        bottleneck_by_pathway={
            "Conventional": native_result.bottleneck_information["Conventional"],
            "MRT": native_result.bottleneck_information["MRT"],
        },
    )
    return NativeReliabilityRunResult(seed=seed, native_result=native_result, reference=reference)


def _build_pathway_summary(
    *,
    request: NativeDecisionPipelineScenario,
    pathway: Pathway,
    run_results: Sequence[NativeReliabilityRunResult],
    thresholds: Sequence[float],
    worst_run_count: int,
) -> NativeReliabilityPathwaySummary:
    completed_values = [float(run.reference.completed_patients_per_day_by_pathway[pathway]) for run in run_results]
    raw_schedule_completed_values = [float(run.reference.raw_schedule_completed_patients_per_day_by_pathway[pathway]) for run in run_results]
    completion_percentages = [float(run.reference.completion_percentage_by_pathway[pathway]) for run in run_results]
    bottlenecks = [run.reference.bottleneck_by_pathway[pathway].resource for run in run_results]
    decay_triplets = [_decay_metrics_from_native(run, pathway) for run in run_results]
    decay_loss_values = [triple[0] for triple in decay_triplets]
    retained_fraction_values = [triple[1] for triple in decay_triplets]
    shortfall_values = [triple[2] for triple in decay_triplets]

    threshold_probabilities = {
        threshold: (sum(1 for throughput in completed_values if throughput < threshold) / len(completed_values))
        for threshold in thresholds
    }

    bottleneck_counts: dict[str, int] = {}
    for resource in bottlenecks:
        bottleneck_counts[resource] = bottleneck_counts.get(resource, 0) + 1

    bottleneck_frequencies = {resource: count / len(run_results) for resource, count in bottleneck_counts.items()}
    worst_count = _limit_worst_run_count(worst_run_count, len(run_results))
    worst_runs = tuple(
        _run_reference(run)
        for run in sorted(
            run_results,
            key=lambda run: (
                float(run.reference.completed_patients_per_day_by_pathway[pathway]),
                run.seed,
            ),
        )[:worst_count]
    )

    source_run_reference = _run_reference(run_results[0])
    source_native_result = run_results[0].native_result
    if pathway == "Conventional":
        capex_result = source_native_result.conventional.capex_result
        opex_result = source_native_result.conventional.opex_result
    else:
        capex_result = source_native_result.mrt.capex_result
        opex_result = source_native_result.mrt.opex_result

    throughput_distribution = _distribution_summary(completed_values)
    raw_schedule_completed_distribution = _distribution_summary(raw_schedule_completed_values)
    completion_distribution = _distribution_summary(completion_percentages)
    decay_loss_distribution = _distribution_summary(decay_loss_values)
    retained_fraction_distribution = _distribution_summary(retained_fraction_values)
    shortfall_distribution = _distribution_summary(shortfall_values)

    return NativeReliabilityPathwaySummary(
        pathway=pathway,
        throughput_distribution=throughput_distribution,
        raw_schedule_completed_distribution=raw_schedule_completed_distribution,
        completion_percentage_distribution=completion_distribution,
        probability_meeting_target_demand=sum(1 for throughput in completed_values if throughput >= request.target_patients_per_day) / len(completed_values),
        probability_below_thresholds=threshold_probabilities,
        bottleneck_counts=bottleneck_counts,
        bottleneck_frequencies=bottleneck_frequencies,
        worst_runs=worst_runs,
        throughput_supportable_at_90pct_reliability=_actual_throughput_supportable_at_reliability(completed_values, 90.0),
        throughput_supportable_at_95pct_reliability=_actual_throughput_supportable_at_reliability(completed_values, 95.0),
        throughput_supportable_at_99pct_reliability=_actual_throughput_supportable_at_reliability(completed_values, 99.0),
        decay_loss_distribution_mbq=decay_loss_distribution,
        retained_fraction_distribution=retained_fraction_distribution,
        potential_shortfall_distribution_mbq=shortfall_distribution,
        capex_result=capex_result,
        opex_result=opex_result,
        source_run_reference=source_run_reference,
    )


def _build_lifecycle_case(
    *,
    request: NativeDecisionPipelineScenario,
    label: ReliabilityThroughputCase,
    conventional_pathway: NativeReliabilityPathwaySummary,
    mrt_pathway: NativeReliabilityPathwaySummary,
    conventional_throughput_per_day: float,
    mrt_throughput_per_day: float,
) -> NativeReliabilityLifecycleCase:
    conventional_lifecycle_result = evaluate_lifecycle_economics(
        initial_capex=conventional_pathway.capex_result.total_capex,
        installed_capacity_per_day=conventional_throughput_per_day,
        annual_opex=conventional_pathway.opex_result.total_annual_opex,
        revenue_per_scan=request.planner_assumptions.revenue_per_scan,
        operating_days_per_year=request.planner_assumptions.operating_days_per_year,
        discount_rate_pct=request.planner_assumptions.discount_rate_pct,
        analysis_years=request.planner_assumptions.analysis_years,
        starting_demand_per_day=conventional_throughput_per_day,
        annual_demand_growth_rate=0.0,
    )
    mrt_lifecycle_result = evaluate_lifecycle_economics(
        initial_capex=mrt_pathway.capex_result.total_capex,
        installed_capacity_per_day=mrt_throughput_per_day,
        annual_opex=mrt_pathway.opex_result.total_annual_opex,
        revenue_per_scan=request.planner_assumptions.revenue_per_scan,
        operating_days_per_year=request.planner_assumptions.operating_days_per_year,
        discount_rate_pct=request.planner_assumptions.discount_rate_pct,
        analysis_years=request.planner_assumptions.analysis_years,
        starting_demand_per_day=mrt_throughput_per_day,
        annual_demand_growth_rate=0.0,
    )
    lifecycle_comparison = compare_lifecycle_results(
        conventional=conventional_lifecycle_result,
        mrt=mrt_lifecycle_result,
    )

    incremental_npv = lifecycle_comparison.incremental_final_npv_mrt_minus_conventional
    if incremental_npv > 0.0:
        economic_winner: Pathway | Literal["Tie"] = "MRT"
    elif incremental_npv < 0.0:
        economic_winner = "Conventional"
    else:
        economic_winner = "Tie"

    return NativeReliabilityLifecycleCase(
        label=label,
        conventional_throughput_per_day=conventional_throughput_per_day,
        mrt_throughput_per_day=mrt_throughput_per_day,
        conventional_lifecycle_result=conventional_lifecycle_result,
        mrt_lifecycle_result=mrt_lifecycle_result,
        lifecycle_comparison_result=lifecycle_comparison,
        economic_winner=economic_winner,
    )


def _limitations() -> tuple[str, ...]:
    return (
        "Empirical reliability statistics depend on the supplied seed set and are not a parametric confidence interval.",
        "Decay physics is integrated; required upstream activity and decay burden are technical outputs, while monetization requires an authoritative isotope-production cost model.",
        "No spatially derived guideway geometry.",
        "No detailed MRT energy physics.",
        "No demand-driven staffing inference.",
        "No architecture optimization in this build.",
    )


def _warnings(run_results: Sequence[NativeReliabilityRunResult]) -> tuple[str, ...]:
    warning_lines: list[str] = []
    for run_result in run_results:
        warning_lines.extend(run_result.native_result.warnings)
    return tuple(dict.fromkeys(warning_lines))


def run_native_reliability_engine(
    request: NativeDecisionPipelineScenario,
    seeds: Iterable[int],
    *,
    throughput_thresholds_per_day: Sequence[float] = (),
    worst_run_count: int = 3,
) -> NativeReliabilityComparisonResult:
    seed_values = _validate_seeds(seeds)
    threshold_values = _validate_thresholds(throughput_thresholds_per_day)

    run_results = tuple(_build_run_result(request, seed) for seed in seed_values)

    conventional = _build_pathway_summary(
        request=request,
        pathway="Conventional",
        run_results=run_results,
        thresholds=threshold_values,
        worst_run_count=worst_run_count,
    )
    mrt = _build_pathway_summary(
        request=request,
        pathway="MRT",
        run_results=run_results,
        thresholds=threshold_values,
        worst_run_count=worst_run_count,
    )

    lifecycle_cases = (
        _build_lifecycle_case(
            request=request,
            label="mean",
            conventional_pathway=conventional,
            mrt_pathway=mrt,
            conventional_throughput_per_day=conventional.throughput_distribution.mean,
            mrt_throughput_per_day=mrt.throughput_distribution.mean,
        ),
        _build_lifecycle_case(
            request=request,
            label="p50",
            conventional_pathway=conventional,
            mrt_pathway=mrt,
            conventional_throughput_per_day=conventional.throughput_distribution.p50,
            mrt_throughput_per_day=mrt.throughput_distribution.p50,
        ),
        _build_lifecycle_case(
            request=request,
            label="p5",
            conventional_pathway=conventional,
            mrt_pathway=mrt,
            conventional_throughput_per_day=conventional.throughput_distribution.p5,
            mrt_throughput_per_day=mrt.throughput_distribution.p5,
        ),
    )

    economic_winner_by_case = {case.label: case.economic_winner for case in lifecycle_cases}
    stable_economic_preference = len(set(economic_winner_by_case.values())) == 1

    run_references_by_seed = {run_result.seed: run_result.reference for run_result in run_results}
    provenance = NativeReliabilityProvenance(
        request=request,
        seeds=seed_values,
        run_references_by_seed=run_references_by_seed,
        aggregate_trace_id=_trace_id(
            {
                "project_name": request.project_name,
                "seed_values": seed_values,
                "run_comparison_trace_ids": [run_result.reference.comparison_trace_id for run_result in run_results],
                "throughput_thresholds_per_day": threshold_values,
                "lifecycle_cases": [
                    {
                        "label": case.label,
                        "conventional_throughput_per_day": case.conventional_throughput_per_day,
                        "mrt_throughput_per_day": case.mrt_throughput_per_day,
                        "incremental_npv": case.lifecycle_comparison_result.incremental_final_npv_mrt_minus_conventional,
                        "economic_winner": case.economic_winner,
                    }
                    for case in lifecycle_cases
                ],
            }
        ),
    )

    trace_id = _trace_id(
        {
            "request_trace_id": provenance.aggregate_trace_id,
            "run_count": len(run_results),
            "conventional_throughput_mean": conventional.throughput_distribution.mean,
            "mrt_throughput_mean": mrt.throughput_distribution.mean,
            "economic_winner_by_case": dict(economic_winner_by_case),
        }
    )

    return NativeReliabilityComparisonResult(
        request=request,
        seeds=seed_values,
        run_count=len(run_results),
        run_results=run_results,
        conventional=conventional,
        mrt=mrt,
        lifecycle_cases=lifecycle_cases,
        economic_winner_by_case=economic_winner_by_case,
        stable_economic_preference=stable_economic_preference,
        provenance=provenance,
        trace_id=trace_id,
        warnings=_warnings(run_results),
        limitations=_limitations(),
    )
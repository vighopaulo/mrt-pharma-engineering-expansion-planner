from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Mapping, Sequence

from decision_pipeline import (
    NativeDecisionComparisonResult,
    NativeDecisionPipelineScenario,
    NativePathwayScenario,
    Pathway,
    run_native_decision_pipeline,
)
from lifecycle_economics import (
    DemandTrajectory,
    LifecycleComparisonResult,
    LifecycleEconomicResult,
    build_demand_trajectory,
    compare_lifecycle_results,
    evaluate_lifecycle_economics,
)
from mrt_carrier_fleet import resized_mrt_carrier_counts
from reliability_engine import NativeReliabilityComparisonResult, NativeReliabilityPathwaySummary, run_native_reliability_engine


DemandMode = Literal["constant", "compound", "explicit", "milestone"]
PlanningStrategy = Literal["phased", "build_ahead"]


@dataclass(frozen=True)
class HorizonExpansionAction:
    year: int
    pathway: Pathway
    resource: str
    step: int
    annual_capex_delta: float
    annual_opex_delta: float
    throughput_gain_per_day: float
    reason: str
    trace_id: str


@dataclass(frozen=True)
class DesignHorizonPathwayYearResult:
    pathway: Pathway
    demand_per_day: float
    installed_capacity_per_day: float
    patients_served_per_day: float
    unmet_demand_per_day: float
    headroom_per_day: float
    capacity_utilization_pct: float
    reliability_probability_meeting_target: float
    binding_bottleneck_resource: str
    annual_opex: float
    annual_capex: float
    expansion_actions: tuple[HorizonExpansionAction, ...]


@dataclass(frozen=True)
class DesignHorizonYearResult:
    year: int
    demand_per_day: float
    conventional: DesignHorizonPathwayYearResult
    mrt: DesignHorizonPathwayYearResult


@dataclass(frozen=True)
class PathwayHorizonSummary:
    pathway: Pathway
    exhaustion_year: int | None
    minimum_headroom_per_day: float
    maximum_unmet_demand_per_day: float
    bottleneck_by_year: Mapping[int, str]
    bottleneck_migration_timeline: tuple[str, ...]


@dataclass(frozen=True)
class DesignHorizonStrategyEconomics:
    strategy: PlanningStrategy
    conventional_lifecycle: LifecycleEconomicResult
    mrt_lifecycle: LifecycleEconomicResult
    pathway_comparison: LifecycleComparisonResult


@dataclass(frozen=True)
class PathwayStrategyComparison:
    pathway: Pathway
    phased_final_npv: float
    build_ahead_final_npv: float
    incremental_npv_build_ahead_minus_phased: float
    preferred_strategy: PlanningStrategy | Literal["tie"]
    build_ahead_feasible: bool
    build_ahead_infeasibility_reason: str | None


@dataclass(frozen=True)
class BuildAheadPathwayStatus:
    pathway: Pathway
    feasible: bool
    achieved_capacity_per_day: float
    target_capacity_per_day: float
    infeasibility_reason: str | None


@dataclass(frozen=True)
class DesignHorizonPlanningRequest:
    pipeline_template: NativeDecisionPipelineScenario
    seeds: Sequence[int]
    analysis_years: int | None = None
    demand_mode: DemandMode = "constant"
    constant_daily_demand: float | None = None
    annual_growth_rate: float = 0.0
    explicit_daily_demand_by_year: Sequence[float] | None = None
    milestone_daily_demand_by_year: Mapping[int, float] | None = None
    throughput_thresholds_per_day: Sequence[float] = ()
    worst_run_count: int = 3
    max_expansion_actions_per_year: int = 2
    max_total_build_ahead_actions: int = 8
    allowed_expansion_resources: Mapping[Pathway, Sequence[str]] = field(
        default_factory=lambda: {
            "Conventional": ("scanner", "injection", "uptake", "distribution"),
            "MRT": ("scanner", "injection", "uptake", "distribution", "endpoint"),
        }
    )
    resource_step_sizes: Mapping[str, int] = field(
        default_factory=lambda: {
            "scanner": 1,
            "injection": 1,
            "uptake": 1,
            "distribution": 1,
            "endpoint": 1,
        }
    )

    def __post_init__(self) -> None:
        if not self.seeds:
            raise ValueError("seeds must not be empty")
        if any(not isinstance(seed, int) for seed in self.seeds):
            raise TypeError("seeds must contain integers")
        if self.analysis_years is not None and int(self.analysis_years) < 1:
            raise ValueError("analysis_years must be at least 1")
        if int(self.max_expansion_actions_per_year) < 0:
            raise ValueError("max_expansion_actions_per_year must be non-negative")
        if int(self.max_total_build_ahead_actions) < 0:
            raise ValueError("max_total_build_ahead_actions must be non-negative")
        if self.demand_mode not in {"constant", "compound", "explicit", "milestone"}:
            raise ValueError("unsupported demand_mode")

        for key, value in self.resource_step_sizes.items():
            if int(value) < 1:
                raise ValueError(f"resource step size for {key} must be at least 1")


def _trace_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _pathway_summary(result: NativeReliabilityComparisonResult, pathway: Pathway) -> NativeReliabilityPathwaySummary:
    return result.conventional if pathway == "Conventional" else result.mrt


def _resource_step(request: DesignHorizonPlanningRequest, resource: str) -> int:
    return int(request.resource_step_sizes.get(resource, 1))


def _annual_capex_opex(
    decision_result: NativeDecisionComparisonResult,
    pathway: Pathway,
) -> tuple[float, float]:
    if pathway == "Conventional":
        return (
            float(decision_result.conventional.capex_result.total_capex),
            float(decision_result.conventional.opex_result.total_annual_opex),
        )
    return (
        float(decision_result.mrt.capex_result.total_capex),
        float(decision_result.mrt.opex_result.total_annual_opex),
    )


def _with_target(request: NativeDecisionPipelineScenario, demand_per_day: float) -> NativeDecisionPipelineScenario:
    return replace(request, target_patients_per_day=max(1, int(math.ceil(demand_per_day))))


def _capacity_probe(
    request: NativeDecisionPipelineScenario,
    seeds: Sequence[int],
    demand_probe_per_day: float,
    thresholds: Sequence[float],
    worst_run_count: int,
    pathway: Pathway,
) -> float:
    probe_request = _with_target(request, demand_probe_per_day)
    reliability = run_native_reliability_engine(
        probe_request,
        seeds,
        throughput_thresholds_per_day=thresholds,
        worst_run_count=worst_run_count,
    )
    return float(_pathway_summary(reliability, pathway).throughput_distribution.mean)


def _apply_resource_step(pathway: Pathway, architecture: NativePathwayScenario, resource: str, step: int) -> NativePathwayScenario:
    if resource.startswith("combo(") and resource.endswith(")"):
        payload = resource[6:-1].strip()
        if not payload:
            raise ValueError("combo resource payload must not be empty")
        next_architecture = architecture
        for token in payload.split(","):
            component = token.strip()
            if "=" not in component:
                raise ValueError("combo resource payload must use resource=step format")
            component_resource, component_step = component.split("=", 1)
            next_architecture = _apply_resource_step(
                pathway,
                next_architecture,
                component_resource.strip(),
                int(component_step.strip()),
            )
        return next_architecture

    if resource == "scanner":
        return replace(architecture, scanners=architecture.scanners + step)
    if resource == "injection":
        return replace(architecture, injection_resources=architecture.injection_resources + step)
    if resource == "uptake":
        return replace(architecture, uptake_resources=architecture.uptake_resources + step)
    if resource == "distribution":
        if pathway == "MRT":
            candidate_distribution = architecture.distribution_concurrency + step
            installed, operated = resized_mrt_carrier_counts(
                base_distribution_concurrency=architecture.distribution_concurrency,
                base_installed_carriers=architecture.installed_mrt_carriers,
                base_operated_carriers=architecture.operated_mrt_carriers,
                candidate_distribution_concurrency=candidate_distribution,
            )
            return replace(
                architecture,
                distribution_concurrency=candidate_distribution,
                installed_mrt_carriers=installed,
                operated_mrt_carriers=operated,
            )
        return replace(architecture, distribution_concurrency=architecture.distribution_concurrency + step)
    if resource == "endpoint":
        if pathway != "MRT":
            raise ValueError("endpoint expansion is only valid for MRT")
        return replace(
            architecture,
            installed_mrt_endpoints=architecture.installed_mrt_endpoints + step,
            operated_mrt_endpoints=architecture.operated_mrt_endpoints + step,
        )
    raise ValueError(f"unsupported expansion resource: {resource}")


def _scenario_with_architecture(
    scenario: NativeDecisionPipelineScenario,
    pathway: Pathway,
    architecture: NativePathwayScenario,
) -> NativeDecisionPipelineScenario:
    if pathway == "Conventional":
        return replace(scenario, conventional=architecture)
    return replace(scenario, mrt=architecture)


def _evaluate_pathway_for_demand(
    scenario: NativeDecisionPipelineScenario,
    pathway: Pathway,
    demand_per_day: float,
    seeds: Sequence[int],
    thresholds: Sequence[float],
    worst_run_count: int,
) -> tuple[NativeReliabilityComparisonResult, NativeReliabilityPathwaySummary]:
    eval_request = _with_target(scenario, demand_per_day)
    reliability = run_native_reliability_engine(
        eval_request,
        seeds,
        throughput_thresholds_per_day=thresholds,
        worst_run_count=worst_run_count,
    )
    summary = _pathway_summary(reliability, pathway)
    return reliability, summary


def _choose_expansion_action(
    *,
    request: DesignHorizonPlanningRequest,
    scenario: NativeDecisionPipelineScenario,
    pathway: Pathway,
    demand_per_day: float,
    current_capacity: float,
) -> tuple[NativePathwayScenario, HorizonExpansionAction, float] | None:
    base_architecture = scenario.conventional if pathway == "Conventional" else scenario.mrt
    base_decision = run_native_decision_pipeline(_with_target(scenario, demand_per_day))
    base_capex, base_opex = _annual_capex_opex(base_decision, pathway)

    single_candidates: list[dict[str, Any]] = []

    def _evaluate_candidate(
        candidate_architecture: NativePathwayScenario,
        *,
        resource_label: str,
        decision_kind: str,
    ) -> dict[str, Any] | None:
        candidate_scenario = _scenario_with_architecture(scenario, pathway, candidate_architecture)
        _, candidate_summary = _evaluate_pathway_for_demand(
            candidate_scenario,
            pathway,
            demand_per_day,
            request.seeds,
            request.throughput_thresholds_per_day,
            request.worst_run_count,
        )
        candidate_capacity = float(candidate_summary.throughput_distribution.mean)
        served_gain = min(demand_per_day, candidate_capacity) - min(demand_per_day, current_capacity)
        if served_gain <= 0.0:
            return None

        candidate_decision = run_native_decision_pipeline(_with_target(candidate_scenario, demand_per_day))
        candidate_capex, candidate_opex = _annual_capex_opex(candidate_decision, pathway)
        capex_delta = max(0.0, candidate_capex - base_capex)
        opex_delta = max(0.0, candidate_opex - base_opex)
        return {
            "served_gain": served_gain,
            "capex_delta": capex_delta,
            "opex_delta": opex_delta,
            "resource_label": resource_label,
            "candidate_architecture": candidate_architecture,
            "candidate_capacity": candidate_capacity,
            "qualifies": candidate_capacity >= demand_per_day,
            "decision_kind": decision_kind,
        }

    for resource in request.allowed_expansion_resources[pathway]:
        step = _resource_step(request, resource)
        candidate_architecture = _apply_resource_step(pathway, base_architecture, resource, step)
        candidate = _evaluate_candidate(candidate_architecture, resource_label=resource, decision_kind="single")
        if candidate is not None:
            single_candidates.append(candidate)

    if not single_candidates:
        return None

    qualifying_singles = [candidate for candidate in single_candidates if candidate["qualifies"]]
    selected_candidate: dict[str, Any] | None = None

    if qualifying_singles:
        selected_candidate = min(
            qualifying_singles,
            key=lambda item: (item["capex_delta"], item["opex_delta"], -item["served_gain"], item["resource_label"]),
        )
    else:
        qualifying_combinations: list[dict[str, Any]] = []
        resources = tuple(request.allowed_expansion_resources[pathway])
        for left_index in range(len(resources)):
            for right_index in range(left_index + 1, len(resources)):
                left_resource = resources[left_index]
                right_resource = resources[right_index]
                left_step = _resource_step(request, left_resource)
                right_step = _resource_step(request, right_resource)
                candidate_architecture = _apply_resource_step(pathway, base_architecture, left_resource, left_step)
                candidate_architecture = _apply_resource_step(pathway, candidate_architecture, right_resource, right_step)
                combo_label = f"combo({left_resource}={left_step},{right_resource}={right_step})"
                candidate = _evaluate_candidate(candidate_architecture, resource_label=combo_label, decision_kind="combo")
                if candidate is not None and candidate["qualifies"]:
                    qualifying_combinations.append(candidate)

        if qualifying_combinations:
            selected_candidate = min(
                qualifying_combinations,
                key=lambda item: (item["capex_delta"], item["opex_delta"], -item["served_gain"], item["resource_label"]),
            )

    if selected_candidate is None:
        selected_candidate = max(
            single_candidates,
            key=lambda item: (item["served_gain"], -item["capex_delta"], -item["opex_delta"], item["resource_label"]),
        )

    best_gain = float(selected_candidate["served_gain"])
    best_capex_delta = float(selected_candidate["capex_delta"])
    best_opex_delta = float(selected_candidate["opex_delta"])
    best_resource = str(selected_candidate["resource_label"])
    best_architecture = selected_candidate["candidate_architecture"]
    best_capacity = float(selected_candidate["candidate_capacity"])
    decision_kind = str(selected_candidate["decision_kind"])

    if decision_kind == "combo":
        reason = (
            "No bounded single-resource action met demand; selected minimum-CapEx qualifying "
            f"multi-resource combination {best_resource}."
        )
        action_step = 0
    else:
        reason = f"Increase {best_resource} to close unmet demand under bounded expansion search."
        action_step = _resource_step(request, best_resource)

    action = HorizonExpansionAction(
        year=0,
        pathway=pathway,
        resource=best_resource,
        step=action_step,
        annual_capex_delta=best_capex_delta,
        annual_opex_delta=best_opex_delta,
        throughput_gain_per_day=best_gain,
        reason=reason,
        trace_id=_trace_id(
            {
                "pathway": pathway,
                "resource": best_resource,
                "step": action_step,
                "demand": demand_per_day,
                "served_gain": best_gain,
                "capex_delta": best_capex_delta,
                "opex_delta": best_opex_delta,
                "decision_kind": decision_kind,
            }
        ),
    )
    return best_architecture, action, best_capacity


def _expand_pathway_for_year(
    *,
    request: DesignHorizonPlanningRequest,
    scenario: NativeDecisionPipelineScenario,
    pathway: Pathway,
    year: int,
    demand_per_day: float,
) -> tuple[NativeDecisionPipelineScenario, tuple[HorizonExpansionAction, ...]]:
    actions: list[HorizonExpansionAction] = []
    working_scenario = scenario

    for _ in range(request.max_expansion_actions_per_year):
        _, summary = _evaluate_pathway_for_demand(
            working_scenario,
            pathway,
            demand_per_day,
            request.seeds,
            request.throughput_thresholds_per_day,
            request.worst_run_count,
        )
        current_capacity = float(summary.throughput_distribution.mean)
        if current_capacity >= demand_per_day:
            break

        selected = _choose_expansion_action(
            request=request,
            scenario=working_scenario,
            pathway=pathway,
            demand_per_day=demand_per_day,
            current_capacity=current_capacity,
        )
        if selected is None:
            break

        next_architecture, raw_action, _ = selected
        action = replace(raw_action, year=year)
        actions.append(action)
        working_scenario = _scenario_with_architecture(working_scenario, pathway, next_architecture)

    return working_scenario, tuple(actions)


def _build_pathway_year_result(
    *,
    pathway: Pathway,
    demand_per_day: float,
    installed_capacity_per_day: float,
    reliability_probability_meeting_target: float,
    bottleneck_resource: str,
    annual_opex: float,
    annual_capex: float,
    actions: Sequence[HorizonExpansionAction],
) -> DesignHorizonPathwayYearResult:
    served = min(demand_per_day, installed_capacity_per_day)
    unmet = max(0.0, demand_per_day - installed_capacity_per_day)
    headroom = installed_capacity_per_day - demand_per_day
    utilization = 100.0 * served / installed_capacity_per_day if installed_capacity_per_day > 0.0 else 0.0
    return DesignHorizonPathwayYearResult(
        pathway=pathway,
        demand_per_day=demand_per_day,
        installed_capacity_per_day=installed_capacity_per_day,
        patients_served_per_day=served,
        unmet_demand_per_day=unmet,
        headroom_per_day=headroom,
        capacity_utilization_pct=utilization,
        reliability_probability_meeting_target=reliability_probability_meeting_target,
        binding_bottleneck_resource=bottleneck_resource,
        annual_opex=annual_opex,
        annual_capex=annual_capex,
        expansion_actions=tuple(actions),
    )


def _demand_trajectory(request: DesignHorizonPlanningRequest) -> DemandTrajectory:
    years = int(request.analysis_years or request.pipeline_template.planner_assumptions.analysis_years)
    start = float(request.constant_daily_demand or request.pipeline_template.target_patients_per_day)

    if request.demand_mode == "constant":
        explicit = [start for _ in range(years)]
        return build_demand_trajectory(
            analysis_years=years,
            starting_demand_per_day=start,
            annual_growth_rate=0.0,
            explicit_daily_demand_by_year=explicit,
        )
    if request.demand_mode == "compound":
        return build_demand_trajectory(
            analysis_years=years,
            starting_demand_per_day=start,
            annual_growth_rate=float(request.annual_growth_rate),
        )
    if request.demand_mode == "explicit":
        if request.explicit_daily_demand_by_year is None:
            raise ValueError("explicit_daily_demand_by_year is required for explicit demand mode")
        return build_demand_trajectory(
            analysis_years=years,
            starting_demand_per_day=start,
            annual_growth_rate=0.0,
            explicit_daily_demand_by_year=[float(v) for v in request.explicit_daily_demand_by_year],
        )
    if request.milestone_daily_demand_by_year is None:
        raise ValueError("milestone_daily_demand_by_year is required for milestone demand mode")
    return build_demand_trajectory(
        analysis_years=years,
        starting_demand_per_day=start,
        annual_growth_rate=0.0,
        milestone_daily_demand_by_year=request.milestone_daily_demand_by_year,
    )


def _summarize_pathway(pathway: Pathway, year_results: Sequence[DesignHorizonYearResult]) -> PathwayHorizonSummary:
    pathway_rows = [row.conventional if pathway == "Conventional" else row.mrt for row in year_results]
    exhaustion_year = next((row_index + 1 for row_index, row in enumerate(pathway_rows) if row.unmet_demand_per_day > 0.0), None)
    min_headroom = min((row.headroom_per_day for row in pathway_rows), default=0.0)
    max_unmet = max((row.unmet_demand_per_day for row in pathway_rows), default=0.0)
    bottleneck_by_year = {idx + 1: row.binding_bottleneck_resource for idx, row in enumerate(pathway_rows)}

    migrations: list[str] = []
    previous: str | None = None
    for year, resource in bottleneck_by_year.items():
        if previous is None:
            migrations.append(f"Y{year}: {resource}")
        elif resource != previous:
            migrations.append(f"Y{year}: {previous} -> {resource}")
        previous = resource

    return PathwayHorizonSummary(
        pathway=pathway,
        exhaustion_year=exhaustion_year,
        minimum_headroom_per_day=min_headroom,
        maximum_unmet_demand_per_day=max_unmet,
        bottleneck_by_year=bottleneck_by_year,
        bottleneck_migration_timeline=tuple(migrations),
    )


def _lifecycle_for_pathway(
    *,
    request: DesignHorizonPlanningRequest,
    demand_series: Sequence[float],
    base_capex: float,
    capacity_by_year: Sequence[float],
    opex_by_year: Sequence[float],
    capex_by_year: Sequence[float],
) -> LifecycleEconomicResult:
    return evaluate_lifecycle_economics(
        initial_capex=base_capex,
        installed_capacity_per_day=float(capacity_by_year[0]),
        annual_opex=float(opex_by_year[0]),
        revenue_per_scan=request.pipeline_template.planner_assumptions.revenue_per_scan,
        operating_days_per_year=request.pipeline_template.planner_assumptions.operating_days_per_year,
        discount_rate_pct=request.pipeline_template.planner_assumptions.discount_rate_pct,
        analysis_years=len(demand_series),
        starting_demand_per_day=float(demand_series[0]),
        explicit_daily_demand_by_year=[float(value) for value in demand_series],
        installed_capacity_per_day_by_year=[float(value) for value in capacity_by_year],
        annual_opex_by_year=[float(value) for value in opex_by_year],
        annual_capex_by_year=[float(value) for value in capex_by_year],
    )


def _run_build_ahead_strategy(
    *,
    request: DesignHorizonPlanningRequest,
    demand_series: Sequence[float],
) -> tuple[
    NativeDecisionPipelineScenario,
    Mapping[Pathway, tuple[HorizonExpansionAction, ...]],
    Mapping[Pathway, BuildAheadPathwayStatus],
]:
    max_demand = max(float(value) for value in demand_series)
    scenario = request.pipeline_template
    actions_by_pathway: dict[Pathway, list[HorizonExpansionAction]] = {"Conventional": [], "MRT": []}
    feasibility_by_pathway: dict[Pathway, BuildAheadPathwayStatus] = {}

    for pathway in ("Conventional", "MRT"):
        working = scenario
        for _ in range(request.max_total_build_ahead_actions):
            _, summary = _evaluate_pathway_for_demand(
                working,
                pathway,
                max_demand,
                request.seeds,
                request.throughput_thresholds_per_day,
                request.worst_run_count,
            )
            current_capacity = float(summary.throughput_distribution.mean)
            if current_capacity >= max_demand:
                break
            selected = _choose_expansion_action(
                request=request,
                scenario=working,
                pathway=pathway,
                demand_per_day=max_demand,
                current_capacity=current_capacity,
            )
            if selected is None:
                break
            candidate_architecture, action, _ = selected
            actions_by_pathway[pathway].append(replace(action, year=1, reason="Build-ahead capacity placement for horizon peak demand."))
            working = _scenario_with_architecture(working, pathway, candidate_architecture)
        _, final_summary = _evaluate_pathway_for_demand(
            working,
            pathway,
            max_demand,
            request.seeds,
            request.throughput_thresholds_per_day,
            request.worst_run_count,
        )
        final_capacity = float(final_summary.throughput_distribution.mean)
        feasible = final_capacity >= max_demand
        reason = None
        if not feasible:
            reason = (
                f"Unable to meet horizon peak demand {max_demand:.2f} with bounded build-ahead sizing; "
                f"achieved {final_capacity:.2f}."
            )
        feasibility_by_pathway[pathway] = BuildAheadPathwayStatus(
            pathway=pathway,
            feasible=feasible,
            achieved_capacity_per_day=final_capacity,
            target_capacity_per_day=max_demand,
            infeasibility_reason=reason,
        )
        scenario = working

    return scenario, {key: tuple(value) for key, value in actions_by_pathway.items()}, feasibility_by_pathway


def run_native_design_horizon_planning(request: DesignHorizonPlanningRequest) -> DesignHorizonPlanningResult:
    trajectory = _demand_trajectory(request)
    demand_series = [float(value) for value in trajectory.daily_demand_by_year]
    peak_demand = max(demand_series)

    scenario = request.pipeline_template
    year_results: list[DesignHorizonYearResult] = []

    conventional_opex_series: list[float] = []
    mrt_opex_series: list[float] = []
    conventional_capex_series: list[float] = []
    mrt_capex_series: list[float] = []
    conventional_capacity_probe_series: list[float] = []
    mrt_capacity_probe_series: list[float] = []

    for year_index, demand_per_day in enumerate(demand_series, start=1):
        scenario, conventional_actions = _expand_pathway_for_year(
            request=request,
            scenario=scenario,
            pathway="Conventional",
            year=year_index,
            demand_per_day=demand_per_day,
        )
        scenario, mrt_actions = _expand_pathway_for_year(
            request=request,
            scenario=scenario,
            pathway="MRT",
            year=year_index,
            demand_per_day=demand_per_day,
        )

        reliability, _ = _evaluate_pathway_for_demand(
            scenario,
            "Conventional",
            demand_per_day,
            request.seeds,
            request.throughput_thresholds_per_day,
            request.worst_run_count,
        )
        conventional_summary = reliability.conventional
        mrt_summary = reliability.mrt

        conventional_capacity_probe = _capacity_probe(
            scenario,
            request.seeds,
            peak_demand,
            request.throughput_thresholds_per_day,
            request.worst_run_count,
            "Conventional",
        )
        mrt_capacity_probe = _capacity_probe(
            scenario,
            request.seeds,
            peak_demand,
            request.throughput_thresholds_per_day,
            request.worst_run_count,
            "MRT",
        )

        annual_conventional_capex = sum(action.annual_capex_delta for action in conventional_actions)
        annual_mrt_capex = sum(action.annual_capex_delta for action in mrt_actions)

        conventional_row = _build_pathway_year_result(
            pathway="Conventional",
            demand_per_day=demand_per_day,
            installed_capacity_per_day=conventional_capacity_probe,
            reliability_probability_meeting_target=float(conventional_summary.probability_meeting_target_demand),
            bottleneck_resource=conventional_summary.source_run_reference.bottleneck_by_pathway["Conventional"].resource,
            annual_opex=float(conventional_summary.opex_result.total_annual_opex),
            annual_capex=float(annual_conventional_capex),
            actions=conventional_actions,
        )
        mrt_row = _build_pathway_year_result(
            pathway="MRT",
            demand_per_day=demand_per_day,
            installed_capacity_per_day=mrt_capacity_probe,
            reliability_probability_meeting_target=float(mrt_summary.probability_meeting_target_demand),
            bottleneck_resource=mrt_summary.source_run_reference.bottleneck_by_pathway["MRT"].resource,
            annual_opex=float(mrt_summary.opex_result.total_annual_opex),
            annual_capex=float(annual_mrt_capex),
            actions=mrt_actions,
        )
        year_results.append(
            DesignHorizonYearResult(
                year=year_index,
                demand_per_day=demand_per_day,
                conventional=conventional_row,
                mrt=mrt_row,
            )
        )

        conventional_opex_series.append(conventional_row.annual_opex)
        mrt_opex_series.append(mrt_row.annual_opex)
        conventional_capex_series.append(conventional_row.annual_capex)
        mrt_capex_series.append(mrt_row.annual_capex)
        conventional_capacity_probe_series.append(conventional_row.installed_capacity_per_day)
        mrt_capacity_probe_series.append(mrt_row.installed_capacity_per_day)

    base_decision = run_native_decision_pipeline(_with_target(request.pipeline_template, demand_series[0]))
    base_conventional_capex, _ = _annual_capex_opex(base_decision, "Conventional")
    base_mrt_capex, _ = _annual_capex_opex(base_decision, "MRT")

    phased_conventional_lifecycle = _lifecycle_for_pathway(
        request=request,
        demand_series=demand_series,
        base_capex=base_conventional_capex,
        capacity_by_year=conventional_capacity_probe_series,
        opex_by_year=conventional_opex_series,
        capex_by_year=conventional_capex_series,
    )
    phased_mrt_lifecycle = _lifecycle_for_pathway(
        request=request,
        demand_series=demand_series,
        base_capex=base_mrt_capex,
        capacity_by_year=mrt_capacity_probe_series,
        opex_by_year=mrt_opex_series,
        capex_by_year=mrt_capex_series,
    )
    phased_comparison = compare_lifecycle_results(
        conventional=phased_conventional_lifecycle,
        mrt=phased_mrt_lifecycle,
    )

    build_ahead_scenario, build_ahead_actions, build_ahead_feasibility = _run_build_ahead_strategy(
        request=request,
        demand_series=demand_series,
    )

    build_ahead_reliability, _ = _evaluate_pathway_for_demand(
        build_ahead_scenario,
        "Conventional",
        peak_demand,
        request.seeds,
        request.throughput_thresholds_per_day,
        request.worst_run_count,
    )
    build_ahead_conventional_capacity = float(build_ahead_reliability.conventional.throughput_distribution.mean)
    build_ahead_mrt_capacity = float(build_ahead_reliability.mrt.throughput_distribution.mean)
    build_ahead_conventional_opex = float(build_ahead_reliability.conventional.opex_result.total_annual_opex)
    build_ahead_mrt_opex = float(build_ahead_reliability.mrt.opex_result.total_annual_opex)

    build_ahead_conventional_capex_series = [0.0 for _ in demand_series]
    build_ahead_mrt_capex_series = [0.0 for _ in demand_series]
    build_ahead_conventional_capex_series[0] = sum(action.annual_capex_delta for action in build_ahead_actions["Conventional"])
    build_ahead_mrt_capex_series[0] = sum(action.annual_capex_delta for action in build_ahead_actions["MRT"])

    build_ahead_conventional_lifecycle = _lifecycle_for_pathway(
        request=request,
        demand_series=demand_series,
        base_capex=base_conventional_capex,
        capacity_by_year=[build_ahead_conventional_capacity for _ in demand_series],
        opex_by_year=[build_ahead_conventional_opex for _ in demand_series],
        capex_by_year=build_ahead_conventional_capex_series,
    )
    build_ahead_mrt_lifecycle = _lifecycle_for_pathway(
        request=request,
        demand_series=demand_series,
        base_capex=base_mrt_capex,
        capacity_by_year=[build_ahead_mrt_capacity for _ in demand_series],
        opex_by_year=[build_ahead_mrt_opex for _ in demand_series],
        capex_by_year=build_ahead_mrt_capex_series,
    )
    build_ahead_comparison = compare_lifecycle_results(
        conventional=build_ahead_conventional_lifecycle,
        mrt=build_ahead_mrt_lifecycle,
    )

    strategy_comparison: dict[Pathway, PathwayStrategyComparison] = {}
    for pathway in ("Conventional", "MRT"):
        phased_lifecycle = phased_conventional_lifecycle if pathway == "Conventional" else phased_mrt_lifecycle
        build_lifecycle = build_ahead_conventional_lifecycle if pathway == "Conventional" else build_ahead_mrt_lifecycle
        build_status = build_ahead_feasibility[pathway]
        delta = build_lifecycle.final_npv - phased_lifecycle.final_npv
        if not build_status.feasible:
            preferred: PlanningStrategy | Literal["tie"] = "phased"
        elif delta > 0.0:
            preferred: PlanningStrategy | Literal["tie"] = "build_ahead"
        elif delta < 0.0:
            preferred = "phased"
        else:
            preferred = "tie"
        strategy_comparison[pathway] = PathwayStrategyComparison(
            pathway=pathway,
            phased_final_npv=phased_lifecycle.final_npv,
            build_ahead_final_npv=build_lifecycle.final_npv,
            incremental_npv_build_ahead_minus_phased=delta,
            preferred_strategy=preferred,
            build_ahead_feasible=build_status.feasible,
            build_ahead_infeasibility_reason=build_status.infeasibility_reason,
        )

    return DesignHorizonPlanningResult(
        request=request,
        demand_trajectory=trajectory,
        year_results=tuple(year_results),
        phased_strategy=DesignHorizonStrategyEconomics(
            strategy="phased",
            conventional_lifecycle=phased_conventional_lifecycle,
            mrt_lifecycle=phased_mrt_lifecycle,
            pathway_comparison=phased_comparison,
        ),
        build_ahead_strategy=DesignHorizonStrategyEconomics(
            strategy="build_ahead",
            conventional_lifecycle=build_ahead_conventional_lifecycle,
            mrt_lifecycle=build_ahead_mrt_lifecycle,
            pathway_comparison=build_ahead_comparison,
        ),
        conventional_summary=_summarize_pathway("Conventional", year_results),
        mrt_summary=_summarize_pathway("MRT", year_results),
        strategy_comparison_by_pathway=strategy_comparison,
        trace_id=_trace_id(
            {
                "project": request.pipeline_template.project_name,
                "demand": demand_series,
                "seed_set": tuple(request.seeds),
                "phased_conv_npv": phased_conventional_lifecycle.final_npv,
                "phased_mrt_npv": phased_mrt_lifecycle.final_npv,
                "build_conv_npv": build_ahead_conventional_lifecycle.final_npv,
                "build_mrt_npv": build_ahead_mrt_lifecycle.final_npv,
            }
        ),
    )


@dataclass(frozen=True)
class DesignHorizonPlanningResult:
    request: DesignHorizonPlanningRequest
    demand_trajectory: DemandTrajectory
    year_results: tuple[DesignHorizonYearResult, ...]
    phased_strategy: DesignHorizonStrategyEconomics
    build_ahead_strategy: DesignHorizonStrategyEconomics
    conventional_summary: PathwayHorizonSummary
    mrt_summary: PathwayHorizonSummary
    strategy_comparison_by_pathway: Mapping[Pathway, PathwayStrategyComparison]
    trace_id: str

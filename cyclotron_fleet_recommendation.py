from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from itertools import product
from typing import Any, Iterable, Literal, Mapping, Sequence

from architecture_recommendation import (
    ArchitectureRecommendationRequest,
    ArchitectureRecommendationResult,
    ConventionalArchitectureBounds,
    MrtArchitectureBounds,
    run_native_architecture_recommendation,
)
from cyclotron_production_windows import CyclotronAsset, CyclotronFleet, CyclotronProductionCapability
from decision_pipeline import NativeBottleneckSummary, NativeDecisionPipelineScenario, Pathway


RecommendationObjective = Literal[
    "minimum_capex_qualifying",
    "minimum_annual_opex_qualifying",
    "maximum_npv_qualifying",
    "minimum_lifecycle_cost_qualifying",
    "minimum_fleet_size_qualifying",
]

RecommendedNextActionType = Literal[
    "NONE",
    "ADD_CYCLOTRON",
    "CHANGE_FLEET",
    "ADD_SCANNER",
    "INCREASE_INJECTION_CAPACITY",
    "INCREASE_UPTAKE_CAPACITY",
    "INCREASE_DISTRIBUTION_CAPACITY",
    "MANUAL_REVIEW_REQUIRED",
]


def _trace_id(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _normalize_radionuclide(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("radionuclide names must be non-empty strings")
    return name.strip()


def _sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for value in values:
        seen[_normalize_radionuclide(value)] = None
    return tuple(seen.keys())


@dataclass(frozen=True)
class CyclotronModelSpec:
    model_id: str
    capability: CyclotronProductionCapability
    manufacturer: str | None = None
    model_identifier: str | None = None
    min_quantity: int = 0
    max_quantity: int = 1

    def __post_init__(self) -> None:
        model_id = self.model_id.strip() if isinstance(self.model_id, str) else ""
        if not model_id:
            raise ValueError("model_id must be a non-empty string")
        if self.min_quantity < 0:
            raise ValueError("min_quantity must be non-negative")
        if self.max_quantity < 1:
            raise ValueError("max_quantity must be at least 1")
        if self.max_quantity < self.min_quantity:
            raise ValueError("max_quantity must be greater than or equal to min_quantity")
        object.__setattr__(self, "model_id", model_id)
        object.__setattr__(self, "min_quantity", int(self.min_quantity))
        object.__setattr__(self, "max_quantity", int(self.max_quantity))


@dataclass(frozen=True)
class CyclotronFleetRecommendationRequest:
    project_name: str
    target_patients_per_day: int
    required_radionuclides: tuple[str, ...]
    optional_radionuclides: tuple[str, ...]
    radionuclide_mix: Mapping[str, float]
    activity_distribution_by_radionuclide: Mapping[str, Any]
    candidate_models: tuple[CyclotronModelSpec, ...]
    max_fleet_size: int
    minimum_reliability: float
    analysis_assumptions: Any
    pipeline_template: NativeDecisionPipelineScenario
    conventional_bounds: ConventionalArchitectureBounds
    mrt_bounds: MrtArchitectureBounds
    seeds: tuple[int, ...]
    candidate_generation_max_count: int = 64
    objective: RecommendationObjective = "maximum_npv_qualifying"
    current_fleet: CyclotronFleet | None = None
    incremental_expansion_only: bool = False
    throughputs_for_reliability: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.project_name, str) or not self.project_name.strip():
            raise ValueError("project_name must be a non-empty string")
        if int(self.target_patients_per_day) <= 0:
            raise ValueError("target_patients_per_day must be greater than zero")
        if int(self.max_fleet_size) <= 0:
            raise ValueError("max_fleet_size must be greater than zero")
        if int(self.candidate_generation_max_count) <= 0:
            raise ValueError("candidate_generation_max_count must be greater than zero")
        if not (0.0 < float(self.minimum_reliability) <= 1.0):
            raise ValueError("minimum_reliability must be greater than zero and at most 1.0")
        if not self.candidate_models:
            raise ValueError("candidate_models must not be empty")
        if not self.required_radionuclides:
            raise ValueError("required_radionuclides must not be empty")

        required = _sorted_unique(self.required_radionuclides)
        optional = _sorted_unique(self.optional_radionuclides)
        if set(required).intersection(optional):
            raise ValueError("required_radionuclides and optional_radionuclides must be disjoint")
        object.__setattr__(self, "required_radionuclides", required)
        object.__setattr__(self, "optional_radionuclides", optional)

        mix = { _normalize_radionuclide(name): float(weight) for name, weight in self.radionuclide_mix.items() }
        if not mix:
            raise ValueError("radionuclide_mix must not be empty")
        allowed_mix = set(required).union(optional)
        unsupported_mix = sorted(name for name, weight in mix.items() if weight > 0.0 and name not in allowed_mix)
        if unsupported_mix:
            raise ValueError(f"radionuclide_mix includes isotopes outside required/optional sets: {unsupported_mix}")
        object.__setattr__(self, "radionuclide_mix", mix)

        if not self.seeds:
            raise ValueError("seeds must not be empty")
        for seed in self.seeds:
            if not isinstance(seed, int):
                raise TypeError("seeds must contain integers")
        object.__setattr__(self, "seeds", tuple(self.seeds))
        object.__setattr__(self, "throughputs_for_reliability", tuple(float(value) for value in self.throughputs_for_reliability))


@dataclass(frozen=True)
class NativeFleetCandidateArchitectureSummary:
    architecture_recommendation_result: ArchitectureRecommendationResult
    recommended_pathway: Pathway | Literal["NONE"]
    recommended_architecture_id: str | None
    effective_throughput_per_day_at_reliability: float
    raw_completed_patients_per_day: float
    decay_infeasible_patients_per_day: float
    reliability: float
    capex: float
    annual_opex: float
    annual_revenue: float
    lifecycle_npv: float
    payback_year: float | None
    bottleneck: NativeBottleneckSummary | None


@dataclass(frozen=True)
class NativeFleetCandidateResult:
    candidate_id: str
    fleet: CyclotronFleet
    model_counts: Mapping[str, int]
    supported_radionuclides: tuple[str, ...]
    qualification_status: Literal["QUALIFIED", "REJECTED"]
    rejection_reason: str | None
    architecture_summary: NativeFleetCandidateArchitectureSummary | None
    reliability_trace_id: str | None
    demand_trace_id: str | None
    comparison_trace_id: str | None
    direct_pipeline_trace_id: str | None
    fleet_trace_id: str
    objective_value: float | None
    recommended_next_action_type: RecommendedNextActionType
    recommendation_reason: str | None
    demand_mix_note: str | None


@dataclass(frozen=True)
class NativeFleetIncrementalExpansionResult:
    base_fleet_candidate: NativeFleetCandidateResult | None
    evaluated_expansion_candidates: tuple[NativeFleetCandidateResult, ...]
    best_expansion_candidate: NativeFleetCandidateResult | None
    capex_delta: float | None
    annual_opex_delta: float | None
    annual_revenue_delta: float | None
    lifecycle_npv_delta: float | None
    reliability_delta: float | None
    effective_throughput_delta: float | None
    bottleneck_change: tuple[str | None, str | None] | None


@dataclass(frozen=True)
class NativeFleetRecommendationProvenance:
    request: CyclotronFleetRecommendationRequest
    candidate_trace_ids_by_candidate_id: Mapping[str, str]
    selected_candidate_trace_id: str | None
    runner_up_candidate_trace_id: str | None
    report_trace_id: str


@dataclass(frozen=True)
class NativeFleetRecommendationResult:
    request: CyclotronFleetRecommendationRequest
    candidate_count_evaluated: int
    candidate_count_qualified: int
    candidate_count_rejected: int
    candidate_results: tuple[NativeFleetCandidateResult, ...]
    qualified_candidates: tuple[NativeFleetCandidateResult, ...]
    rejected_candidates: tuple[NativeFleetCandidateResult, ...]
    recommended_candidate: NativeFleetCandidateResult | None
    runner_up_candidate: NativeFleetCandidateResult | None
    recommended_fleet: CyclotronFleet | None
    recommended_architecture_summary: NativeFleetCandidateArchitectureSummary | None
    recommendation_reason: str
    objective: RecommendationObjective
    incremental_expansion: NativeFleetIncrementalExpansionResult | None
    provenance: NativeFleetRecommendationProvenance
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class NativeFleetRecommendationCandidateRow:
    candidate_id: str
    fleet_id: str
    fleet_size: int
    fleet_asset_ids: tuple[str, ...]
    supported_radionuclides: tuple[str, ...]
    qualification_status: Literal["QUALIFIED", "REJECTED"]
    rejection_reason: str | None
    recommended_pathway: Pathway | Literal["NONE"]
    effective_throughput_per_day_at_reliability: float
    reliability: float
    capex: float
    annual_opex: float
    annual_revenue: float
    lifecycle_npv: float
    payback_year: float | None
    bottleneck_resource: str | None


@dataclass(frozen=True)
class NativeFleetRecommendationReportData:
    request: CyclotronFleetRecommendationRequest
    candidate_rows: tuple[NativeFleetRecommendationCandidateRow, ...]
    selected_candidate_row: NativeFleetRecommendationCandidateRow | None
    runner_up_candidate_row: NativeFleetRecommendationCandidateRow | None
    incremental_expansion: NativeFleetIncrementalExpansionResult | None
    recommendation_reason: str
    provenance: NativeFleetRecommendationProvenance
    limitations: tuple[str, ...]


def _candidate_trace_id(candidate: CyclotronFleet, model_counts: Mapping[str, int], supported_radionuclides: Sequence[str]) -> str:
    return _trace_id(
        {
            "fleet_id": candidate.fleet_id,
            "asset_ids": tuple(asset.cyclotron_id for asset in candidate.assets),
            "model_counts": dict(sorted(model_counts.items())),
            "supported_radionuclides": tuple(supported_radionuclides),
        }
    )


def _clone_capability_for_asset(capability: CyclotronProductionCapability, cyclotron_id: str) -> CyclotronProductionCapability:
    return CyclotronProductionCapability(
        cyclotron_id=cyclotron_id,
        supported_radionuclides=capability.supported_radionuclides,
        max_simultaneous_production_streams=capability.max_simultaneous_production_streams,
        production_cycle_minutes_by_radionuclide=dict(capability.production_cycle_minutes_by_radionuclide),
        simultaneously_compatible_radionuclide_sets=capability.simultaneously_compatible_radionuclide_sets,
        release_processing_minutes_by_radionuclide=(
            None
            if capability.release_processing_minutes_by_radionuclide is None
            else dict(capability.release_processing_minutes_by_radionuclide)
        ),
    )


def _asset_model_id(asset: CyclotronAsset, specs: Sequence[CyclotronModelSpec]) -> str | None:
    if asset.capability_provenance:
        for spec in specs:
            if spec.model_id == asset.capability_provenance:
                return spec.model_id
    for spec in specs:
        if (
            asset.capability.supported_radionuclides == spec.capability.supported_radionuclides
            and asset.capability.max_simultaneous_production_streams == spec.capability.max_simultaneous_production_streams
            and dict(asset.capability.production_cycle_minutes_by_radionuclide) == dict(spec.capability.production_cycle_minutes_by_radionuclide)
            and asset.capability.simultaneously_compatible_radionuclide_sets == spec.capability.simultaneously_compatible_radionuclide_sets
        ):
            return spec.model_id
    return None


def _fleet_model_counts(fleet: CyclotronFleet, candidate_models: Sequence[CyclotronModelSpec]) -> dict[str, int]:
    counts: dict[str, int] = {spec.model_id: 0 for spec in candidate_models}
    for asset in fleet.assets:
        model_id = _asset_model_id(asset, candidate_models)
        if model_id is not None:
            counts[model_id] += 1
    return counts


def _validate_candidate_fleet(
    fleet: CyclotronFleet,
    request: CyclotronFleetRecommendationRequest,
) -> tuple[bool, str | None]:
    if not fleet.assets:
        return False, "Candidate fleet must contain at least one asset"
    if len(fleet.assets) > request.max_fleet_size:
        return False, f"Candidate fleet size {len(fleet.assets)} exceeds maximum {request.max_fleet_size}"
    supported = set(fleet.fleet_supported_radionuclides)
    missing_required = [radionuclide for radionuclide in request.required_radionuclides if radionuclide not in supported]
    if missing_required:
        return False, f"Missing required radionuclide: {missing_required[0]}"
    if len(set(asset.cyclotron_id for asset in fleet.assets)) != len(fleet.assets):
        return False, "Candidate fleet contains duplicate cyclotron asset IDs"
    return True, None


def _candidate_mix_for_fleet(
    request: CyclotronFleetRecommendationRequest,
    fleet: CyclotronFleet,
) -> tuple[dict[str, float], dict[str, Any], tuple[str, ...]]:
    supported = set(fleet.fleet_supported_radionuclides)
    allowed = set(request.required_radionuclides).union(request.optional_radionuclides)
    filtered_mix: dict[str, float] = {}
    filtered_models: dict[str, Any] = {}
    dropped_optional_positive: list[str] = []
    for radionuclide, weight in request.radionuclide_mix.items():
        if radionuclide not in allowed:
            continue
        if radionuclide in supported and weight > 0.0:
            filtered_mix[radionuclide] = float(weight)
            filtered_models[radionuclide] = request.activity_distribution_by_radionuclide[radionuclide]
        elif radionuclide in request.optional_radionuclides and weight > 0.0:
            dropped_optional_positive.append(radionuclide)
    if not filtered_mix:
        raise ValueError("No supported radionuclides remain after fleet filtering")
    return filtered_mix, filtered_models, tuple(sorted(dropped_optional_positive))


def _objective_value(candidate: NativeFleetCandidateResult, objective: RecommendationObjective, analysis_years: int) -> float:
    if candidate.architecture_summary is None:
        return float("inf")
    summary = candidate.architecture_summary
    if objective == "minimum_capex_qualifying":
        return summary.capex
    if objective == "minimum_annual_opex_qualifying":
        return summary.annual_opex
    if objective == "maximum_npv_qualifying":
        return -summary.lifecycle_npv
    if objective == "minimum_lifecycle_cost_qualifying":
        return summary.capex + summary.annual_opex * float(analysis_years)
    if objective == "minimum_fleet_size_qualifying":
        return float(candidate.fleet.asset_count)
    raise ValueError(f"Unsupported objective: {objective}")


def _candidate_better_than(
    left: NativeFleetCandidateResult,
    right: NativeFleetCandidateResult,
    objective: RecommendationObjective,
    analysis_years: int,
) -> bool:
    left_value = _objective_value(left, objective, analysis_years)
    right_value = _objective_value(right, objective, analysis_years)
    if left_value != right_value:
        return left_value < right_value
    if left.architecture_summary is None or right.architecture_summary is None:
        return left.candidate_id < right.candidate_id
    if not left.architecture_summary.reliability == right.architecture_summary.reliability:
        return left.architecture_summary.reliability > right.architecture_summary.reliability
    if left.architecture_summary.effective_throughput_per_day_at_reliability != right.architecture_summary.effective_throughput_per_day_at_reliability:
        return left.architecture_summary.effective_throughput_per_day_at_reliability > right.architecture_summary.effective_throughput_per_day_at_reliability
    if left.architecture_summary.capex != right.architecture_summary.capex:
        return left.architecture_summary.capex < right.architecture_summary.capex
    if left.architecture_summary.annual_opex != right.architecture_summary.annual_opex:
        return left.architecture_summary.annual_opex < right.architecture_summary.annual_opex
    if left.fleet.asset_count != right.fleet.asset_count:
        return left.fleet.asset_count < right.fleet.asset_count
    return left.candidate_id < right.candidate_id


def _recommend_next_action(candidate: NativeFleetCandidateResult | None, request: CyclotronFleetRecommendationRequest) -> RecommendedNextActionType:
    if candidate is None or candidate.architecture_summary is None:
        return "MANUAL_REVIEW_REQUIRED"
    bottleneck = candidate.architecture_summary.bottleneck
    if bottleneck is None:
        return "MANUAL_REVIEW_REQUIRED"
    if bottleneck.resource in {"scanner", "injection", "uptake", "distribution"}:
        return {
            "scanner": "ADD_SCANNER",
            "injection": "INCREASE_INJECTION_CAPACITY",
            "uptake": "INCREASE_UPTAKE_CAPACITY",
            "distribution": "INCREASE_DISTRIBUTION_CAPACITY",
        }[bottleneck.resource]
    if bottleneck.resource == "production" and len(request.candidate_models) > candidate.fleet.asset_count:
        return "ADD_CYCLOTRON"
    if bottleneck.resource == "production":
        return "CHANGE_FLEET"
    return "MANUAL_REVIEW_REQUIRED"


def _build_candidate_result(
    request: CyclotronFleetRecommendationRequest,
    candidate_id: str,
    fleet: CyclotronFleet,
    model_counts: Mapping[str, int],
) -> NativeFleetCandidateResult:
    is_qualified, rejection_reason = _validate_candidate_fleet(fleet, request)
    if not is_qualified:
        return NativeFleetCandidateResult(
            candidate_id=candidate_id,
            fleet=fleet,
            model_counts=dict(model_counts),
            supported_radionuclides=tuple(fleet.fleet_supported_radionuclides),
            qualification_status="REJECTED",
            rejection_reason=rejection_reason,
            architecture_summary=None,
            reliability_trace_id=None,
            demand_trace_id=None,
            comparison_trace_id=None,
            direct_pipeline_trace_id=None,
            fleet_trace_id=_candidate_trace_id(fleet, model_counts, fleet.fleet_supported_radionuclides),
            objective_value=None,
            recommended_next_action_type="MANUAL_REVIEW_REQUIRED",
            recommendation_reason=rejection_reason,
            demand_mix_note=None,
        )

    filtered_mix, filtered_models, dropped_optional_positive = _candidate_mix_for_fleet(request, fleet)
    candidate_pipeline = replace(
        request.pipeline_template,
        project_name=request.project_name,
        target_patients_per_day=request.target_patients_per_day,
        radionuclide_mix=filtered_mix,
        activity_distribution_by_radionuclide=filtered_models,
        cyclotron_capability=fleet.assets[0].capability,
        cyclotron_fleet=fleet,
        planner_assumptions=request.analysis_assumptions,
        seed=request.seeds[0],
    )
    architecture_request = ArchitectureRecommendationRequest(
        target_patients_per_day=request.target_patients_per_day,
        minimum_reliability=request.minimum_reliability,
        seeds=request.seeds,
        pipeline_template=candidate_pipeline,
        conventional_bounds=request.conventional_bounds,
        mrt_bounds=request.mrt_bounds,
        max_candidate_count=request.candidate_generation_max_count,
        throughput_thresholds_per_day=request.throughputs_for_reliability or (float(request.target_patients_per_day),),
        worst_run_count=3,
    )
    architecture_result = run_native_architecture_recommendation(architecture_request)
    recommended_architecture = architecture_result.recommended_architecture
    if recommended_architecture is None:
        summary = NativeFleetCandidateArchitectureSummary(
            architecture_recommendation_result=architecture_result,
            recommended_pathway="NONE",
            recommended_architecture_id=None,
            effective_throughput_per_day_at_reliability=0.0,
            raw_completed_patients_per_day=0.0,
            decay_infeasible_patients_per_day=0.0,
            reliability=0.0,
            capex=0.0,
            annual_opex=0.0,
            annual_revenue=0.0,
            lifecycle_npv=0.0,
            payback_year=None,
            bottleneck=None,
        )
        return NativeFleetCandidateResult(
            candidate_id=candidate_id,
            fleet=fleet,
            model_counts=dict(model_counts),
            supported_radionuclides=tuple(fleet.fleet_supported_radionuclides),
            qualification_status="REJECTED",
            rejection_reason="No architecture met the minimum reliability requirement.",
            architecture_summary=summary,
            reliability_trace_id=architecture_result.provenance.aggregate_trace_id,
            demand_trace_id=None,
            comparison_trace_id=None,
            direct_pipeline_trace_id=None,
            fleet_trace_id=_candidate_trace_id(fleet, model_counts, fleet.fleet_supported_radionuclides),
            objective_value=None,
            recommended_next_action_type="MANUAL_REVIEW_REQUIRED",
            recommendation_reason="No qualifying architecture met the minimum reliability requirement.",
            demand_mix_note=(
                None
                if not dropped_optional_positive
                else (
                    "Dropped unsupported optional radionuclides with positive requested weight: "
                    f"{list(dropped_optional_positive)}"
                )
            ),
        )

    recommendation_reason = architecture_result.recommendation_reason
    if dropped_optional_positive:
        recommendation_reason = (
            f"{recommendation_reason} "
            f"Dropped unsupported optional radionuclides with positive requested weight: {list(dropped_optional_positive)}."
        )
    selected_pathway = architecture_result.recommended_pathway
    summary = NativeFleetCandidateArchitectureSummary(
        architecture_recommendation_result=architecture_result,
        recommended_pathway=selected_pathway,
        recommended_architecture_id=recommended_architecture.candidate_id,
        effective_throughput_per_day_at_reliability=float(recommended_architecture.effective_completed_patients_per_day),
        raw_completed_patients_per_day=float(recommended_architecture.raw_schedule_completed_patients_per_day),
        decay_infeasible_patients_per_day=float(recommended_architecture.decay_infeasible_patients_per_day),
        reliability=float(recommended_architecture.measured_reliability),
        capex=float(recommended_architecture.capex_result.total_capex),
        annual_opex=float(recommended_architecture.opex_result.total_annual_opex),
        annual_revenue=float(recommended_architecture.direct_decision_result.conventional.annual_revenue if selected_pathway == "Conventional" else recommended_architecture.direct_decision_result.mrt.annual_revenue),
        lifecycle_npv=float(recommended_architecture.lifecycle_npv),
        payback_year=recommended_architecture.lifecycle_result.payback_year,
        bottleneck=recommended_architecture.bottleneck_summary,
    )
    objective_value = _objective_value(
        NativeFleetCandidateResult(
            candidate_id=candidate_id,
            fleet=fleet,
            model_counts=dict(model_counts),
            supported_radionuclides=tuple(fleet.fleet_supported_radionuclides),
            qualification_status="QUALIFIED",
            rejection_reason=None,
            architecture_summary=summary,
            reliability_trace_id=None,
            demand_trace_id=None,
            comparison_trace_id=None,
            direct_pipeline_trace_id=None,
            fleet_trace_id="",
            objective_value=None,
            recommended_next_action_type="NONE",
            recommendation_reason=None,
            demand_mix_note=None,
        ),
        request.objective,
        request.analysis_assumptions.analysis_years,
    )
    next_action = _recommend_next_action(
        NativeFleetCandidateResult(
            candidate_id=candidate_id,
            fleet=fleet,
            model_counts=dict(model_counts),
            supported_radionuclides=tuple(fleet.fleet_supported_radionuclides),
            qualification_status="QUALIFIED",
            rejection_reason=None,
            architecture_summary=summary,
            reliability_trace_id=None,
            demand_trace_id=None,
            comparison_trace_id=None,
            direct_pipeline_trace_id=None,
            fleet_trace_id="",
            objective_value=None,
            recommended_next_action_type="NONE",
            recommendation_reason=None,
            demand_mix_note=None,
        ),
        request,
    )
    return NativeFleetCandidateResult(
        candidate_id=candidate_id,
        fleet=fleet,
        model_counts=dict(model_counts),
        supported_radionuclides=tuple(fleet.fleet_supported_radionuclides),
        qualification_status="QUALIFIED",
        rejection_reason=None,
        architecture_summary=summary,
        reliability_trace_id=architecture_result.provenance.aggregate_trace_id,
        demand_trace_id=recommended_architecture.provenance.direct_demand_trace_id,
        comparison_trace_id=recommended_architecture.provenance.direct_comparison_trace_id,
        direct_pipeline_trace_id=recommended_architecture.provenance.direct_pipeline_trace_id,
        fleet_trace_id=_candidate_trace_id(fleet, model_counts, fleet.fleet_supported_radionuclides),
        objective_value=objective_value,
        recommended_next_action_type=next_action,
        recommendation_reason=recommendation_reason,
        demand_mix_note=(
            None
            if not dropped_optional_positive
            else (
                "Dropped unsupported optional radionuclides with positive requested weight: "
                f"{list(dropped_optional_positive)}"
            )
        ),
    )


def _build_candidate_fleet_from_counts(
    request: CyclotronFleetRecommendationRequest,
    counts: Mapping[str, int],
    *,
    fleet_id: str,
    base_assets: Sequence[CyclotronAsset] = (),
) -> CyclotronFleet:
    assets: list[CyclotronAsset] = list(base_assets)
    for spec in request.candidate_models:
        quantity = int(counts.get(spec.model_id, 0))
        for index in range(quantity):
            asset_id = f"{fleet_id}-{spec.model_id}-{index + 1}"
            assets.append(
                CyclotronAsset(
                    cyclotron_id=asset_id,
                    capability=_clone_capability_for_asset(spec.capability, asset_id),
                    model_identifier=spec.model_identifier,
                    manufacturer=spec.manufacturer,
                    capability_provenance=spec.model_id,
                )
            )
    return CyclotronFleet(assets=tuple(assets), fleet_id=fleet_id)


def _enumerate_candidate_counts(request: CyclotronFleetRecommendationRequest) -> tuple[dict[str, int], ...]:
    model_ids = tuple(spec.model_id for spec in request.candidate_models)
    combinations: list[dict[str, int]] = []

    def recurse(index: int, remaining: int, current: dict[str, int]) -> None:
        if index == len(model_ids):
            total = sum(current.values())
            if 0 < total <= request.max_fleet_size and all(current.get(spec.model_id, 0) >= spec.min_quantity for spec in request.candidate_models):
                combinations.append(dict(current))
            return
        spec = request.candidate_models[index]
        min_qty = spec.min_quantity
        max_qty = min(spec.max_quantity, remaining)
        for quantity in range(min_qty, max_qty + 1):
            current[spec.model_id] = quantity
            recurse(index + 1, remaining - quantity, current)
        current.pop(spec.model_id, None)

    recurse(0, request.max_fleet_size, {})
    unique: list[dict[str, int]] = []
    seen: set[tuple[tuple[str, int], ...]] = set()
    for counts in combinations:
        key = tuple(sorted((model_id, quantity) for model_id, quantity in counts.items() if quantity > 0))
        if key in seen:
            continue
        seen.add(key)
        unique.append(dict(counts))
    return tuple(unique)


def _enumerate_candidate_fleets(request: CyclotronFleetRecommendationRequest) -> tuple[tuple[dict[str, int], CyclotronFleet], ...]:
    if request.incremental_expansion_only and request.current_fleet is None:
        raise ValueError("current_fleet must be provided when incremental_expansion_only is enabled")

    fleets: list[tuple[dict[str, int], CyclotronFleet]] = []
    if request.current_fleet is not None:
        current_counts = _fleet_model_counts(request.current_fleet, request.candidate_models)
        fleets.append((current_counts, request.current_fleet))
        if request.incremental_expansion_only:
            for spec in request.candidate_models:
                if request.current_fleet.asset_count + 1 > request.max_fleet_size:
                    continue
                expanded_assets = list(request.current_fleet.assets)
                asset_id = f"{request.current_fleet.fleet_id}-{spec.model_id}-ADD1"
                expanded_assets.append(
                    CyclotronAsset(
                        cyclotron_id=asset_id,
                        capability=_clone_capability_for_asset(spec.capability, asset_id),
                        model_identifier=spec.model_identifier,
                        manufacturer=spec.manufacturer,
                        capability_provenance=spec.model_id,
                    )
                )
                expanded_fleet = CyclotronFleet(assets=tuple(expanded_assets), fleet_id=f"{request.current_fleet.fleet_id}+{spec.model_id}")
                fleets.append((_fleet_model_counts(expanded_fleet, request.candidate_models), expanded_fleet))
            return tuple(fleets)

    for index, counts in enumerate(_enumerate_candidate_counts(request), start=1):
        fleet = _build_candidate_fleet_from_counts(request, counts, fleet_id=f"FLEET-{index:03d}")
        fleets.append((counts, fleet))
    return tuple(fleets)


def _best_candidate(candidates: Sequence[NativeFleetCandidateResult], request: CyclotronFleetRecommendationRequest) -> NativeFleetCandidateResult | None:
    qualified = [candidate for candidate in candidates if candidate.qualification_status == "QUALIFIED"]
    if not qualified:
        return None
    best = qualified[0]
    for candidate in qualified[1:]:
        if _candidate_better_than(candidate, best, request.objective, request.analysis_assumptions.analysis_years):
            best = candidate
    return best


def _runner_up_candidate(
    candidates: Sequence[NativeFleetCandidateResult],
    request: CyclotronFleetRecommendationRequest,
    winner: NativeFleetCandidateResult | None,
) -> NativeFleetCandidateResult | None:
    if winner is None:
        return None
    others = [candidate for candidate in candidates if candidate.qualification_status == "QUALIFIED" and candidate.candidate_id != winner.candidate_id]
    if not others:
        return None
    return sorted(
        others,
        key=lambda candidate: (
            _objective_value(candidate, request.objective, request.analysis_assumptions.analysis_years),
            -candidate.architecture_summary.reliability if candidate.architecture_summary else 0.0,
            -candidate.architecture_summary.effective_throughput_per_day_at_reliability if candidate.architecture_summary else 0.0,
            candidate.candidate_id,
        ),
    )[0]


def _candidate_row(candidate: NativeFleetCandidateResult) -> NativeFleetRecommendationCandidateRow:
    summary = candidate.architecture_summary
    if summary is None:
        return NativeFleetRecommendationCandidateRow(
            candidate_id=candidate.candidate_id,
            fleet_id=candidate.fleet.fleet_id,
            fleet_size=candidate.fleet.asset_count,
            fleet_asset_ids=tuple(asset.cyclotron_id for asset in candidate.fleet.assets),
            supported_radionuclides=candidate.supported_radionuclides,
            qualification_status=candidate.qualification_status,
            rejection_reason=candidate.rejection_reason,
            recommended_pathway="NONE",
            effective_throughput_per_day_at_reliability=0.0,
            reliability=0.0,
            capex=0.0,
            annual_opex=0.0,
            annual_revenue=0.0,
            lifecycle_npv=0.0,
            payback_year=None,
            bottleneck_resource=None,
        )
    return NativeFleetRecommendationCandidateRow(
        candidate_id=candidate.candidate_id,
        fleet_id=candidate.fleet.fleet_id,
        fleet_size=candidate.fleet.asset_count,
        fleet_asset_ids=tuple(asset.cyclotron_id for asset in candidate.fleet.assets),
        supported_radionuclides=candidate.supported_radionuclides,
        qualification_status=candidate.qualification_status,
        rejection_reason=candidate.rejection_reason,
        recommended_pathway=summary.recommended_pathway,
        effective_throughput_per_day_at_reliability=summary.effective_throughput_per_day_at_reliability,
        reliability=summary.reliability,
        capex=summary.capex,
        annual_opex=summary.annual_opex,
        annual_revenue=summary.annual_revenue,
        lifecycle_npv=summary.lifecycle_npv,
        payback_year=summary.payback_year,
        bottleneck_resource=None if summary.bottleneck is None else summary.bottleneck.resource,
    )


def run_native_cyclotron_fleet_recommendation(
    request: CyclotronFleetRecommendationRequest,
) -> NativeFleetRecommendationResult:
    candidate_pairs = _enumerate_candidate_fleets(request)
    if len(candidate_pairs) > request.candidate_generation_max_count:
        raise ValueError(
            f"candidate count {len(candidate_pairs)} exceeds candidate_generation_max_count {request.candidate_generation_max_count}"
        )

    candidate_results: list[NativeFleetCandidateResult] = []
    trace_ids_by_candidate_id: dict[str, str] = {}
    for index, (model_counts, fleet) in enumerate(candidate_pairs, start=1):
        candidate_id = f"CAND-{index:03d}"
        result = _build_candidate_result(request, candidate_id, fleet, model_counts)
        candidate_results.append(result)
        trace_ids_by_candidate_id[result.candidate_id] = result.fleet_trace_id

    qualified_candidates = tuple(candidate for candidate in candidate_results if candidate.qualification_status == "QUALIFIED")
    rejected_candidates = tuple(candidate for candidate in candidate_results if candidate.qualification_status == "REJECTED")
    recommended_candidate = _best_candidate(candidate_results, request)
    runner_up_candidate = _runner_up_candidate(candidate_results, request, recommended_candidate)

    incremental = None
    if request.current_fleet is not None:
        base_candidate = next((candidate for candidate in candidate_results if candidate.fleet.fleet_id == request.current_fleet.fleet_id), None)
        expansion_candidates = tuple(
            candidate
            for candidate in candidate_results
            if candidate.fleet.fleet_id != request.current_fleet.fleet_id
        )
        best_expansion = _best_candidate(expansion_candidates, request)
        if base_candidate is not None and best_expansion is not None and base_candidate.architecture_summary is not None and best_expansion.architecture_summary is not None:
            incremental = NativeFleetIncrementalExpansionResult(
                base_fleet_candidate=base_candidate,
                evaluated_expansion_candidates=expansion_candidates,
                best_expansion_candidate=best_expansion,
                capex_delta=best_expansion.architecture_summary.capex - base_candidate.architecture_summary.capex,
                annual_opex_delta=best_expansion.architecture_summary.annual_opex - base_candidate.architecture_summary.annual_opex,
                annual_revenue_delta=best_expansion.architecture_summary.annual_revenue - base_candidate.architecture_summary.annual_revenue,
                lifecycle_npv_delta=best_expansion.architecture_summary.lifecycle_npv - base_candidate.architecture_summary.lifecycle_npv,
                reliability_delta=best_expansion.architecture_summary.reliability - base_candidate.architecture_summary.reliability,
                effective_throughput_delta=best_expansion.architecture_summary.effective_throughput_per_day_at_reliability - base_candidate.architecture_summary.effective_throughput_per_day_at_reliability,
                bottleneck_change=(
                    None if base_candidate.architecture_summary.bottleneck is None else base_candidate.architecture_summary.bottleneck.resource,
                    None if best_expansion.architecture_summary.bottleneck is None else best_expansion.architecture_summary.bottleneck.resource,
                ),
            )

    recommendation_reason = (
        "No candidate fleet qualified."
        if recommended_candidate is None
        else f"Selected {recommended_candidate.candidate_id} because it best satisfied the requested objective {request.objective}."
    )
    provenance = NativeFleetRecommendationProvenance(
        request=request,
        candidate_trace_ids_by_candidate_id=trace_ids_by_candidate_id,
        selected_candidate_trace_id=None if recommended_candidate is None else recommended_candidate.fleet_trace_id,
        runner_up_candidate_trace_id=None if runner_up_candidate is None else runner_up_candidate.fleet_trace_id,
        report_trace_id=_trace_id(
            {
                "project_name": request.project_name,
                "target_patients_per_day": request.target_patients_per_day,
                "candidate_ids": [candidate.candidate_id for candidate in candidate_results],
                "selected_candidate_id": None if recommended_candidate is None else recommended_candidate.candidate_id,
                "runner_up_candidate_id": None if runner_up_candidate is None else runner_up_candidate.candidate_id,
            }
        ),
    )
    return NativeFleetRecommendationResult(
        request=request,
        candidate_count_evaluated=len(candidate_results),
        candidate_count_qualified=len(qualified_candidates),
        candidate_count_rejected=len(rejected_candidates),
        candidate_results=tuple(candidate_results),
        qualified_candidates=qualified_candidates,
        rejected_candidates=rejected_candidates,
        recommended_candidate=recommended_candidate,
        runner_up_candidate=runner_up_candidate,
        recommended_fleet=None if recommended_candidate is None else recommended_candidate.fleet,
        recommended_architecture_summary=None if recommended_candidate is None else recommended_candidate.architecture_summary,
        recommendation_reason=recommendation_reason,
        objective=request.objective,
        incremental_expansion=incremental,
        provenance=provenance,
        limitations=(
            "Candidate model library is caller-supplied; the repository does not maintain a native manufacturer catalog.",
            "No geometry-derived guideway routing.",
            "No staffing inference.",
            "No isotope reimbursement model.",
            "No unlimited combinatorial optimization.",
        ),
    )


def build_native_cyclotron_fleet_recommendation_report_data(
    recommendation_result: NativeFleetRecommendationResult,
) -> NativeFleetRecommendationReportData:
    candidate_rows = tuple(_candidate_row(candidate) for candidate in recommendation_result.candidate_results)
    selected_row = None if recommendation_result.recommended_candidate is None else _candidate_row(recommendation_result.recommended_candidate)
    runner_up_row = None if recommendation_result.runner_up_candidate is None else _candidate_row(recommendation_result.runner_up_candidate)
    return NativeFleetRecommendationReportData(
        request=recommendation_result.request,
        candidate_rows=candidate_rows,
        selected_candidate_row=selected_row,
        runner_up_candidate_row=runner_up_row,
        incremental_expansion=recommendation_result.incremental_expansion,
        recommendation_reason=recommendation_result.recommendation_reason,
        provenance=recommendation_result.provenance,
        limitations=recommendation_result.limitations,
    )
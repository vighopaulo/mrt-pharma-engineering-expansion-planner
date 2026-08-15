from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Literal, Mapping, Sequence

from decision_pipeline import (
    NativeBottleneckSummary,
    NativeDecisionComparisonResult,
    NativeDecisionPipelineScenario,
    NativePathwayScenario,
    Pathway,
    run_native_decision_pipeline,
)
from infrastructure_capex import InfrastructureCapexResult
from infrastructure_opex import InfrastructureOpexResult
from lifecycle_economics import LifecycleEconomicResult
from mrt_carrier_fleet import resized_mrt_carrier_counts
from reliability_engine import (
    NativeReliabilityComparisonResult,
    NativeReliabilityDistributionSummary,
    NativeReliabilityLifecycleCase,
    NativeReliabilityRunReference,
    run_native_reliability_engine,
)


RecommendationPathway = Literal["Conventional", "MRT", "NONE"]


def _trace_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _validate_int_values(name: str, values: Sequence[int], *, minimum: int = 1) -> tuple[int, ...]:
    normalized = tuple(int(value) for value in values)
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must contain unique values")
    for value in normalized:
        if value < minimum:
            raise ValueError(f"{name} values must be at least {minimum}")
    return normalized


def _validate_float_values(name: str, values: Sequence[float], *, minimum: float = 0.0) -> tuple[float, ...]:
    normalized = tuple(float(value) for value in values)
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must contain unique values")
    for value in normalized:
        if value < minimum:
            raise ValueError(f"{name} values must be at least {minimum}")
    return normalized


def _resource_count(pathway_config: NativePathwayScenario) -> int:
    return (
        pathway_config.scanners
        + pathway_config.injection_resources
        + pathway_config.uptake_resources
        + pathway_config.distribution_concurrency
        + pathway_config.installed_mrt_endpoints
    )


def _architecture_signature(pathway: Pathway, pathway_config: NativePathwayScenario) -> str:
    return _trace_id(
        {
            "pathway": pathway,
            "scanners": pathway_config.scanners,
            "injection_resources": pathway_config.injection_resources,
            "uptake_resources": pathway_config.uptake_resources,
            "distribution_concurrency": pathway_config.distribution_concurrency,
            "transport_minutes": pathway_config.transport_minutes,
            "installed_mrt_endpoints": pathway_config.installed_mrt_endpoints,
            "operated_mrt_endpoints": pathway_config.operated_mrt_endpoints,
            "installed_mrt_carriers": pathway_config.installed_mrt_carriers,
            "operated_mrt_carriers": pathway_config.operated_mrt_carriers,
        }
    )


@dataclass(frozen=True)
class ConventionalArchitectureBounds:
    scanners: Sequence[int]
    injection_resources: Sequence[int]
    uptake_resources: Sequence[int]
    distribution_concurrency: Sequence[int]
    transport_minutes: Sequence[float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "scanners", _validate_int_values("scanners", self.scanners))
        object.__setattr__(self, "injection_resources", _validate_int_values("injection_resources", self.injection_resources))
        object.__setattr__(self, "uptake_resources", _validate_int_values("uptake_resources", self.uptake_resources))
        object.__setattr__(self, "distribution_concurrency", _validate_int_values("distribution_concurrency", self.distribution_concurrency))
        object.__setattr__(self, "transport_minutes", _validate_float_values("transport_minutes", self.transport_minutes, minimum=0.0))


@dataclass(frozen=True)
class MrtArchitectureBounds:
    scanners: Sequence[int]
    injection_resources: Sequence[int]
    uptake_resources: Sequence[int]
    distribution_concurrency: Sequence[int]
    installed_mrt_endpoints: Sequence[int]
    transport_minutes: Sequence[float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "scanners", _validate_int_values("scanners", self.scanners))
        object.__setattr__(self, "injection_resources", _validate_int_values("injection_resources", self.injection_resources))
        object.__setattr__(self, "uptake_resources", _validate_int_values("uptake_resources", self.uptake_resources))
        object.__setattr__(self, "distribution_concurrency", _validate_int_values("distribution_concurrency", self.distribution_concurrency))
        object.__setattr__(self, "installed_mrt_endpoints", _validate_int_values("installed_mrt_endpoints", self.installed_mrt_endpoints, minimum=0))
        object.__setattr__(self, "transport_minutes", _validate_float_values("transport_minutes", self.transport_minutes, minimum=0.0))


@dataclass(frozen=True)
class ArchitectureRecommendationRequest:
    target_patients_per_day: int
    minimum_reliability: float
    seeds: Sequence[int]
    pipeline_template: NativeDecisionPipelineScenario
    conventional_bounds: ConventionalArchitectureBounds
    mrt_bounds: MrtArchitectureBounds
    max_candidate_count: int = 64
    throughput_thresholds_per_day: Sequence[float] = ()
    worst_run_count: int = 3

    def __post_init__(self) -> None:
        if int(self.target_patients_per_day) <= 0:
            raise ValueError("target_patients_per_day must be greater than zero")
        if not (0.0 < float(self.minimum_reliability) <= 1.0):
            raise ValueError("minimum_reliability must be greater than zero and at most 1.0")
        if int(self.max_candidate_count) <= 0:
            raise ValueError("max_candidate_count must be greater than zero")
        if int(self.worst_run_count) <= 0:
            raise ValueError("worst_run_count must be greater than zero")

        normalized_seeds = tuple(self.seeds)
        if not normalized_seeds:
            raise ValueError("seeds must not be empty")
        for seed in normalized_seeds:
            if not isinstance(seed, int):
                raise TypeError("seeds must contain integers")
        object.__setattr__(self, "seeds", normalized_seeds)

        normalized_thresholds = tuple(float(value) for value in self.throughput_thresholds_per_day)
        for threshold in normalized_thresholds:
            if threshold < 0.0:
                raise ValueError("throughput_thresholds_per_day must be non-negative")
        object.__setattr__(self, "throughput_thresholds_per_day", normalized_thresholds)

        object.__setattr__(self, "target_patients_per_day", int(self.target_patients_per_day))
        object.__setattr__(self, "minimum_reliability", float(self.minimum_reliability))
        object.__setattr__(self, "max_candidate_count", int(self.max_candidate_count))
        object.__setattr__(self, "worst_run_count", int(self.worst_run_count))


@dataclass(frozen=True)
class ArchitectureCandidateProvenance:
    candidate_id: str
    pathway: Pathway
    architecture_signature: str
    architecture_quantities: Mapping[str, Any]
    seed_set: tuple[int, ...]
    fleet_id: str
    fleet_asset_ids: tuple[str, ...]
    fleet_supported_radionuclides: tuple[str, ...]
    direct_pipeline_trace_id: str
    direct_demand_trace_id: str
    direct_comparison_trace_id: str
    reliability_trace_id: str
    reliability_run_references: Mapping[int, NativeReliabilityRunReference]
    selected_lifecycle_case_label: str


@dataclass(frozen=True)
class ArchitectureCandidateResult:
    candidate_id: str
    pathway: Pathway
    architecture: NativePathwayScenario
    status: Literal["QUALIFIED", "REJECTED_RELIABILITY"]
    measured_reliability: float
    reliability_margin: float
    throughput_distribution: NativeReliabilityDistributionSummary
    completion_percentage_distribution: NativeReliabilityDistributionSummary
    probability_below_thresholds: Mapping[float, float]
    bottleneck_summary: NativeBottleneckSummary
    capex_result: InfrastructureCapexResult
    opex_result: InfrastructureOpexResult
    lifecycle_case: NativeReliabilityLifecycleCase
    lifecycle_result: LifecycleEconomicResult
    lifecycle_npv: float
    direct_decision_result: NativeDecisionComparisonResult
    reliability_result: NativeReliabilityComparisonResult
    provenance: ArchitectureCandidateProvenance
    selection_reason: str
    rejection_reason: str | None
    resource_intelligence: tuple[str, ...]
    decay_total_loss_mbq: float = 0.0
    decay_mean_retained_fraction: float = 1.0
    decay_loss_mbq_per_completed_patient: float = 0.0
    effective_completed_patients_per_day: float = 0.0
    raw_schedule_completed_patients_per_day: float = 0.0
    decay_infeasible_patients_per_day: float = 0.0


@dataclass(frozen=True)
class ArchitectureRecommendationProvenance:
    request: ArchitectureRecommendationRequest
    aggregate_trace_id: str
    winning_candidate_id: str | None
    candidate_provenance_by_id: Mapping[str, ArchitectureCandidateProvenance]
    source_modules: tuple[str, ...] = ("decision_pipeline", "reliability_engine", "lifecycle_economics")


@dataclass(frozen=True)
class ArchitectureRecommendationResult:
    request: ArchitectureRecommendationRequest
    candidate_count_evaluated: int
    candidate_count_by_pathway: Mapping[Pathway, int]
    qualified_candidate_count_by_pathway: Mapping[Pathway, int]
    rejected_candidate_count_by_pathway: Mapping[Pathway, int]
    conventional_candidates: tuple[ArchitectureCandidateResult, ...]
    mrt_candidates: tuple[ArchitectureCandidateResult, ...]
    best_qualifying_conventional: ArchitectureCandidateResult | None
    best_qualifying_mrt: ArchitectureCandidateResult | None
    recommended_pathway: RecommendationPathway
    recommended_architecture: ArchitectureCandidateResult | None
    economic_advantage: float | None
    reliability_margin: float | None
    recommendation_reason: str
    provenance: ArchitectureRecommendationProvenance
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]


def _candidate_count(bounds: ConventionalArchitectureBounds | MrtArchitectureBounds) -> int:
    total = 1
    for values in bounds.__dict__.values():
        total *= len(values)
    return total


def _conventional_candidate_architectures(
    base: NativePathwayScenario,
    bounds: ConventionalArchitectureBounds,
) -> tuple[NativePathwayScenario, ...]:
    candidates: list[NativePathwayScenario] = []
    for scanners, injection_resources, uptake_resources, distribution_concurrency, transport_minutes in itertools.product(
        bounds.scanners,
        bounds.injection_resources,
        bounds.uptake_resources,
        bounds.distribution_concurrency,
        bounds.transport_minutes,
    ):
        candidates.append(
            replace(
                base,
                scanners=scanners,
                injection_resources=injection_resources,
                uptake_resources=uptake_resources,
                distribution_concurrency=distribution_concurrency,
                transport_minutes=transport_minutes,
                installed_cyclotron_units=base.installed_cyclotron_units,
                installed_radiopharmacy_units=base.installed_radiopharmacy_units,
                operated_cyclotron_units=base.operated_cyclotron_units,
                operated_radiopharmacy_units=base.operated_radiopharmacy_units,
            )
        )
    return tuple(candidates)


def _mrt_candidate_architectures(
    base: NativePathwayScenario,
    bounds: MrtArchitectureBounds,
) -> tuple[NativePathwayScenario, ...]:
    candidates: list[NativePathwayScenario] = []
    for scanners, injection_resources, uptake_resources, distribution_concurrency, installed_mrt_endpoints, transport_minutes in itertools.product(
        bounds.scanners,
        bounds.injection_resources,
        bounds.uptake_resources,
        bounds.distribution_concurrency,
        bounds.installed_mrt_endpoints,
        bounds.transport_minutes,
    ):
        installed_mrt_carriers, operated_mrt_carriers = resized_mrt_carrier_counts(
            base_distribution_concurrency=base.distribution_concurrency,
            base_installed_carriers=base.installed_mrt_carriers,
            base_operated_carriers=base.operated_mrt_carriers,
            candidate_distribution_concurrency=distribution_concurrency,
        )
        candidates.append(
            replace(
                base,
                scanners=scanners,
                injection_resources=injection_resources,
                uptake_resources=uptake_resources,
                distribution_concurrency=distribution_concurrency,
                transport_minutes=transport_minutes,
                installed_mrt_endpoints=installed_mrt_endpoints,
                operated_mrt_endpoints=installed_mrt_endpoints,
                installed_mrt_carriers=installed_mrt_carriers,
                operated_mrt_carriers=operated_mrt_carriers,
                installed_cyclotron_units=base.installed_cyclotron_units,
                installed_radiopharmacy_units=base.installed_radiopharmacy_units,
                operated_cyclotron_units=base.operated_cyclotron_units,
                operated_radiopharmacy_units=base.operated_radiopharmacy_units,
            )
        )
    return tuple(candidates)


def _selected_lifecycle_case(result: NativeReliabilityComparisonResult) -> NativeReliabilityLifecycleCase:
    for case in result.lifecycle_cases:
        if case.label == "mean":
            return case
    raise ValueError("Native reliability result does not contain a mean lifecycle case")


def _candidate_better_than(left: ArchitectureCandidateResult, right: ArchitectureCandidateResult) -> bool:
    if not math.isclose(left.lifecycle_npv, right.lifecycle_npv, rel_tol=1e-9, abs_tol=1e-6):
        return left.lifecycle_npv > right.lifecycle_npv
    if not math.isclose(left.capex_result.total_capex, right.capex_result.total_capex, rel_tol=1e-9, abs_tol=1e-6):
        return left.capex_result.total_capex < right.capex_result.total_capex
    if not math.isclose(left.opex_result.total_annual_opex, right.opex_result.total_annual_opex, rel_tol=1e-9, abs_tol=1e-6):
        return left.opex_result.total_annual_opex < right.opex_result.total_annual_opex
    if _resource_count(left.architecture) != _resource_count(right.architecture):
        return _resource_count(left.architecture) < _resource_count(right.architecture)
    return left.candidate_id < right.candidate_id


def _candidate_reason(
    candidate: ArchitectureCandidateResult,
    *,
    winner: ArchitectureCandidateResult | None,
    minimum_reliability: float,
) -> tuple[str, str | None]:
    if candidate.status == "REJECTED_RELIABILITY":
        reason = f"Rejected because measured reliability {candidate.measured_reliability:.3f} fell below minimum {minimum_reliability:.3f}."
        return (reason, reason)
    if winner is None or candidate.candidate_id == winner.candidate_id:
        reason = (
            f"Selected as best qualifying {candidate.pathway} architecture by mean-case 10-year NPV "
            f"at reliability {candidate.measured_reliability:.3f}."
        )
        return (reason, None)
    reason = (
        f"Qualified but not selected; mean-case 10-year NPV {candidate.lifecycle_npv:.2f} was below {winner.candidate_id}."
    )
    return (reason, None)


def _resource_intelligence_notes(
    selected: ArchitectureCandidateResult,
    peer_candidates: Sequence[ArchitectureCandidateResult],
) -> tuple[str, ...]:
    notes: list[str] = []
    for peer in peer_candidates:
        if peer.candidate_id == selected.candidate_id:
            continue
        selected_counts = _resource_count(selected.architecture)
        peer_counts = _resource_count(peer.architecture)
        larger_or_equal = peer_counts >= selected_counts
        if not larger_or_equal:
            continue
        if peer.lifecycle_npv <= selected.lifecycle_npv and peer.throughput_distribution.mean <= selected.throughput_distribution.mean:
            notes.append(
                f"Candidate {peer.candidate_id} added resources without improving throughput or 10-year NPV."
            )
        elif peer.lifecycle_npv <= selected.lifecycle_npv and peer.throughput_distribution.mean > selected.throughput_distribution.mean:
            notes.append(
                f"Candidate {peer.candidate_id} increased throughput but did not justify higher CapEx/OPEX."
            )
        if peer.bottleneck_summary.resource == selected.bottleneck_summary.resource:
            notes.append(
                f"Candidate {peer.candidate_id} left {selected.bottleneck_summary.resource} as the binding resource."
            )
    return tuple(dict.fromkeys(notes))


def _decay_metrics_for_pathway(direct_decision_result: NativeDecisionComparisonResult, pathway: Pathway) -> tuple[float, float, float]:
    pathway_result = direct_decision_result.conventional if pathway == "Conventional" else direct_decision_result.mrt
    decay_summary = getattr(pathway_result, "decay_summary", None)
    if decay_summary is None:
        return 0.0, 1.0, 0.0
    return (
        float(getattr(decay_summary, "overall_physical_decay_loss_mbq", getattr(decay_summary, "overall_decay_loss_mbq", 0.0))),
        float(getattr(decay_summary, "mean_retained_fraction", 1.0)),
        float(getattr(decay_summary, "physical_decay_loss_mbq_per_feasible_completed_patient", getattr(decay_summary, "decay_loss_mbq_per_completed_patient", 0.0))),
    )


def _evaluate_candidate(
    request: ArchitectureRecommendationRequest,
    candidate_id: str,
    pathway: Pathway,
    candidate_architecture: NativePathwayScenario,
) -> ArchitectureCandidateResult:
    candidate_request = replace(
        request.pipeline_template,
        target_patients_per_day=request.target_patients_per_day,
        seed=request.seeds[0],
        conventional=candidate_architecture if pathway == "Conventional" else request.pipeline_template.conventional,
        mrt=candidate_architecture if pathway == "MRT" else request.pipeline_template.mrt,
    )
    direct_decision_result = run_native_decision_pipeline(candidate_request)
    reliability_result = run_native_reliability_engine(
        candidate_request,
        request.seeds,
        throughput_thresholds_per_day=request.throughput_thresholds_per_day or (request.target_patients_per_day,),
        worst_run_count=request.worst_run_count,
    )

    pathway_summary = reliability_result.conventional if pathway == "Conventional" else reliability_result.mrt
    selected_case = _selected_lifecycle_case(reliability_result)
    selected_lifecycle_result = selected_case.conventional_lifecycle_result if pathway == "Conventional" else selected_case.mrt_lifecycle_result

    measured_reliability = pathway_summary.probability_meeting_target_demand
    status: Literal["QUALIFIED", "REJECTED_RELIABILITY"] = (
        "QUALIFIED" if measured_reliability >= request.minimum_reliability else "REJECTED_RELIABILITY"
    )
    architecture_signature = _architecture_signature(pathway, candidate_architecture)
    provenance = ArchitectureCandidateProvenance(
        candidate_id=candidate_id,
        pathway=pathway,
        architecture_signature=architecture_signature,
        architecture_quantities={
            "scanners": candidate_architecture.scanners,
            "injection_resources": candidate_architecture.injection_resources,
            "uptake_resources": candidate_architecture.uptake_resources,
            "distribution_concurrency": candidate_architecture.distribution_concurrency,
            "transport_minutes": candidate_architecture.transport_minutes,
            "installed_mrt_endpoints": candidate_architecture.installed_mrt_endpoints,
            "installed_mrt_carriers": candidate_architecture.installed_mrt_carriers,
            "operated_mrt_carriers": candidate_architecture.operated_mrt_carriers,
            "spare_mrt_carriers": candidate_architecture.installed_mrt_carriers - candidate_architecture.operated_mrt_carriers,
        },
        seed_set=tuple(request.seeds),
        fleet_id=getattr(direct_decision_result.provenance, "fleet_id", "PRIMARY_FLEET"),
        fleet_asset_ids=tuple(getattr(direct_decision_result.provenance, "fleet_asset_ids", ())),
        fleet_supported_radionuclides=tuple(getattr(direct_decision_result.provenance, "fleet_supported_radionuclides", ())),
        direct_pipeline_trace_id=direct_decision_result.provenance.comparison_trace_id,
        direct_demand_trace_id=direct_decision_result.provenance.demand_trace_id,
        direct_comparison_trace_id=direct_decision_result.provenance.comparison_trace_id,
        reliability_trace_id=reliability_result.trace_id,
        reliability_run_references=reliability_result.provenance.run_references_by_seed,
        selected_lifecycle_case_label=selected_case.label,
    )

    selection_reason = ""
    rejection_reason: str | None = None
    if status == "REJECTED_RELIABILITY":
        rejection_reason = (
            f"Rejected because measured reliability {measured_reliability:.3f} fell below minimum {request.minimum_reliability:.3f}."
        )
    else:
        decay_loss_mbq, decay_mean_retained_fraction, _ = _decay_metrics_for_pathway(direct_decision_result, pathway)
        selection_reason = (
            f"Qualified on empirical reliability {measured_reliability:.3f}; selection uses the mean-case 10-year NPV from the native reliability engine. "
            f"Decay audit: mean retained fraction {decay_mean_retained_fraction:.4f}, total loss {decay_loss_mbq:.2f} MBq."
        )

    decay_total_loss_mbq, decay_mean_retained_fraction, decay_loss_mbq_per_completed_patient = _decay_metrics_for_pathway(direct_decision_result, pathway)
    pathway_result = direct_decision_result.conventional if pathway == "Conventional" else direct_decision_result.mrt
    operational_result = getattr(pathway_result, "operational_result", None)
    effective_completed = float(
        getattr(
            operational_result,
            "decay_feasible_completed_patients",
            getattr(operational_result, "patients_completed", pathway_summary.throughput_distribution.mean),
        )
    )
    raw_completed = float(getattr(operational_result, "schedule_completed_patients", effective_completed))
    decay_infeasible = float(getattr(operational_result, "decay_infeasible_patients", max(0.0, raw_completed - effective_completed)))

    return ArchitectureCandidateResult(
        candidate_id=candidate_id,
        pathway=pathway,
        architecture=candidate_architecture,
        status=status,
        measured_reliability=measured_reliability,
        reliability_margin=measured_reliability - request.minimum_reliability,
        throughput_distribution=pathway_summary.throughput_distribution,
        completion_percentage_distribution=pathway_summary.completion_percentage_distribution,
        probability_below_thresholds=pathway_summary.probability_below_thresholds,
        bottleneck_summary=pathway_summary.source_run_reference.bottleneck_by_pathway[pathway],
        capex_result=pathway_summary.capex_result,
        opex_result=pathway_summary.opex_result,
        lifecycle_case=selected_case,
        lifecycle_result=selected_lifecycle_result,
        lifecycle_npv=selected_lifecycle_result.final_npv,
        direct_decision_result=direct_decision_result,
        reliability_result=reliability_result,
        provenance=provenance,
        selection_reason=selection_reason,
        rejection_reason=rejection_reason,
        resource_intelligence=(),
        decay_total_loss_mbq=decay_total_loss_mbq,
        decay_mean_retained_fraction=decay_mean_retained_fraction,
        decay_loss_mbq_per_completed_patient=decay_loss_mbq_per_completed_patient,
        effective_completed_patients_per_day=effective_completed,
        raw_schedule_completed_patients_per_day=raw_completed,
        decay_infeasible_patients_per_day=decay_infeasible,
    )


def _evaluate_pathway_candidates(
    request: ArchitectureRecommendationRequest,
    pathway: Pathway,
    candidate_architectures: Sequence[NativePathwayScenario],
) -> tuple[ArchitectureCandidateResult, ...]:
    evaluated: list[ArchitectureCandidateResult] = []
    for index, architecture in enumerate(candidate_architectures, start=1):
        candidate_id = f"{pathway[:3].upper()}-{index:03d}"
        evaluated.append(_evaluate_candidate(request, candidate_id, pathway, architecture))
    return tuple(evaluated)


def _best_qualifying_candidate(candidates: Sequence[ArchitectureCandidateResult]) -> ArchitectureCandidateResult | None:
    qualifying = [candidate for candidate in candidates if candidate.status == "QUALIFIED"]
    if not qualifying:
        return None
    best = qualifying[0]
    for candidate in qualifying[1:]:
        if _candidate_better_than(candidate, best):
            best = candidate
    return best


def _count_by_status(candidates: Sequence[ArchitectureCandidateResult], status: str) -> int:
    return sum(1 for candidate in candidates if candidate.status == status)


def _limit_candidate_count(request: ArchitectureRecommendationRequest, candidate_count: int) -> None:
    if candidate_count > request.max_candidate_count:
        raise ValueError(
            f"candidate count {candidate_count} exceeds max_candidate_count {request.max_candidate_count}"
        )


def _selection_result(
    conventional_best: ArchitectureCandidateResult | None,
    mrt_best: ArchitectureCandidateResult | None,
) -> tuple[RecommendationPathway, ArchitectureCandidateResult | None, float | None, float | None, str]:
    if conventional_best is None and mrt_best is None:
        return (
            "NONE",
            None,
            None,
            None,
            "No candidate met the minimum reliability requirement.",
        )
    if conventional_best is not None and mrt_best is None:
        return (
            "Conventional",
            conventional_best,
            None,
            conventional_best.reliability_margin,
            f"Only Conventional candidates qualified; selected {conventional_best.candidate_id}.",
        )
    if mrt_best is not None and conventional_best is None:
        return (
            "MRT",
            mrt_best,
            None,
            mrt_best.reliability_margin,
            f"Only MRT candidates qualified; selected {mrt_best.candidate_id}.",
        )

    assert conventional_best is not None and mrt_best is not None
    if _candidate_better_than(conventional_best, mrt_best):
        advantage = conventional_best.lifecycle_npv - mrt_best.lifecycle_npv
        return (
            "Conventional",
            conventional_best,
            advantage,
            conventional_best.reliability_margin,
            f"Selected {conventional_best.candidate_id} because it had the highest qualifying mean-case 10-year NPV.",
        )
    if _candidate_better_than(mrt_best, conventional_best):
        advantage = mrt_best.lifecycle_npv - conventional_best.lifecycle_npv
        return (
            "MRT",
            mrt_best,
            advantage,
            mrt_best.reliability_margin,
            f"Selected {mrt_best.candidate_id} because it had the highest qualifying mean-case 10-year NPV.",
        )
    if conventional_best.candidate_id < mrt_best.candidate_id:
        chosen = conventional_best
        other = mrt_best
        pathway = "Conventional"
    else:
        chosen = mrt_best
        other = conventional_best
        pathway = "MRT"
    return (
        pathway,
        chosen,
        chosen.lifecycle_npv - other.lifecycle_npv,
        chosen.reliability_margin,
        f"Selected {chosen.candidate_id} after deterministic tie-breaking on CapEx, OPEX, resource count, and candidate ID.",
    )


def run_native_architecture_recommendation(
    request: ArchitectureRecommendationRequest,
) -> ArchitectureRecommendationResult:
    conventional_architectures = _conventional_candidate_architectures(
        request.pipeline_template.conventional,
        request.conventional_bounds,
    )
    mrt_architectures = _mrt_candidate_architectures(
        request.pipeline_template.mrt,
        request.mrt_bounds,
    )

    conventional_count = len(conventional_architectures)
    mrt_count = len(mrt_architectures)
    total_count = conventional_count + mrt_count
    _limit_candidate_count(request, total_count)

    conventional_candidates = _evaluate_pathway_candidates(request, "Conventional", conventional_architectures)
    mrt_candidates = _evaluate_pathway_candidates(request, "MRT", mrt_architectures)

    conventional_best = _best_qualifying_candidate(conventional_candidates)
    mrt_best = _best_qualifying_candidate(mrt_candidates)

    recommended_pathway, recommended_architecture, economic_advantage, reliability_margin, recommendation_reason = _selection_result(
        conventional_best,
        mrt_best,
    )

    candidate_provenance_by_id = {
        candidate.provenance.candidate_id: candidate.provenance
        for candidate in conventional_candidates + mrt_candidates
    }
    provenance = ArchitectureRecommendationProvenance(
        request=request,
        aggregate_trace_id=_trace_id(
            {
                "target_patients_per_day": request.target_patients_per_day,
                "minimum_reliability": request.minimum_reliability,
                "candidate_ids": list(candidate_provenance_by_id),
                "recommended_pathway": recommended_pathway,
                "recommended_candidate_id": None if recommended_architecture is None else recommended_architecture.candidate_id,
            }
        ),
        winning_candidate_id=None if recommended_architecture is None else recommended_architecture.candidate_id,
        candidate_provenance_by_id=candidate_provenance_by_id,
    )

    conventional_candidates = tuple(
        replace(
            candidate,
            selection_reason=(
                _candidate_reason(candidate, winner=conventional_best, minimum_reliability=request.minimum_reliability)[0]
                if candidate.status == "QUALIFIED"
                else candidate.rejection_reason or ""
            ),
            rejection_reason=(candidate.rejection_reason if candidate.status == "REJECTED_RELIABILITY" else None),
        )
        for candidate in conventional_candidates
    )
    mrt_candidates = tuple(
        replace(
            candidate,
            selection_reason=(
                _candidate_reason(candidate, winner=mrt_best, minimum_reliability=request.minimum_reliability)[0]
                if candidate.status == "QUALIFIED"
                else candidate.rejection_reason or ""
            ),
            rejection_reason=(candidate.rejection_reason if candidate.status == "REJECTED_RELIABILITY" else None),
        )
        for candidate in mrt_candidates
    )

    final_conventional_best = _best_qualifying_candidate(conventional_candidates)
    final_mrt_best = _best_qualifying_candidate(mrt_candidates)

    if final_conventional_best is not None:
        conventional_notes = _resource_intelligence_notes(final_conventional_best, conventional_candidates)
        conventional_candidates = tuple(
            replace(
                candidate,
                resource_intelligence=(conventional_notes if candidate.candidate_id == final_conventional_best.candidate_id else candidate.resource_intelligence),
            )
            for candidate in conventional_candidates
        )
        final_conventional_best = next(candidate for candidate in conventional_candidates if candidate.candidate_id == final_conventional_best.candidate_id)
    if final_mrt_best is not None:
        mrt_notes = _resource_intelligence_notes(final_mrt_best, mrt_candidates)
        mrt_candidates = tuple(
            replace(
                candidate,
                resource_intelligence=(mrt_notes if candidate.candidate_id == final_mrt_best.candidate_id else candidate.resource_intelligence),
            )
            for candidate in mrt_candidates
        )
        final_mrt_best = next(candidate for candidate in mrt_candidates if candidate.candidate_id == final_mrt_best.candidate_id)

    recommended_pathway, recommended_architecture, economic_advantage, reliability_margin, recommendation_reason = _selection_result(
        final_conventional_best,
        final_mrt_best,
    )

    if recommended_architecture is not None:
        selected_pool = conventional_candidates if recommended_architecture.pathway == "Conventional" else mrt_candidates
        recommended_architecture = next(candidate for candidate in selected_pool if candidate.candidate_id == recommended_architecture.candidate_id)

    qualified_conventional = _count_by_status(conventional_candidates, "QUALIFIED")
    qualified_mrt = _count_by_status(mrt_candidates, "QUALIFIED")

    warnings = tuple(dict.fromkeys(
        [
            "Recommendation layer delegates all engineering calculations to the native decision and reliability engines.",
            "Candidate generation is explicitly bounded by caller-supplied value sets.",
        ]
    ))
    limitations = (
        "No spatially derived guideway geometry.",
        "No multi-isotope decay economics.",
        "No detailed MRT energy physics.",
        "No demand-driven staffing inference.",
        "No architecture optimization beyond bounded candidate selection.",
    )

    return ArchitectureRecommendationResult(
        request=request,
        candidate_count_evaluated=total_count,
        candidate_count_by_pathway={"Conventional": conventional_count, "MRT": mrt_count},
        qualified_candidate_count_by_pathway={"Conventional": qualified_conventional, "MRT": qualified_mrt},
        rejected_candidate_count_by_pathway={
            "Conventional": conventional_count - qualified_conventional,
            "MRT": mrt_count - qualified_mrt,
        },
        conventional_candidates=conventional_candidates,
        mrt_candidates=mrt_candidates,
        best_qualifying_conventional=final_conventional_best,
        best_qualifying_mrt=final_mrt_best,
        recommended_pathway=recommended_pathway,
        recommended_architecture=recommended_architecture,
        economic_advantage=economic_advantage,
        reliability_margin=reliability_margin,
        recommendation_reason=recommendation_reason,
        provenance=provenance,
        warnings=warnings,
        limitations=limitations,
    )
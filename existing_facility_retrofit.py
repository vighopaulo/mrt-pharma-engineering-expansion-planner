from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from typing import Any, Literal, Mapping, Sequence

from architecture_recommendation import (
    ArchitectureCandidateResult,
    ArchitectureRecommendationRequest,
    ArchitectureRecommendationResult,
    ConventionalArchitectureBounds,
    MrtArchitectureBounds,
    run_native_architecture_recommendation,
)
from decision_pipeline import NativeDecisionComparisonResult, NativeDecisionPipelineScenario, NativePathwayScenario, run_native_decision_pipeline
from design_horizon_planning import DesignHorizonPlanningRequest
from engineering_evidence import EngineeringAssumptionProposal
from reliability_engine import NativeReliabilityComparisonResult, run_native_reliability_engine


ProjectMode = Literal["GREENFIELD", "EXISTING_FACILITY_EXPANSION"]
DataStatus = Literal["KNOWN", "USER_ASSUMED", "EVIDENCE_BACKED", "UNKNOWN", "NOT_MODELED"]
ResourceDisposition = Literal["RETAIN", "REUSE", "MODIFY", "EXPAND", "REPLACE", "RETIRE", "NEW", "NOT_MODELED"]
RetrofitFeasibilityStatus = Literal[
    "FEASIBLE",
    "FEASIBLE_WITH_EXPANSION",
    "INFEASIBLE_WITHIN_BOUNDS",
    "INSUFFICIENT_BASELINE_DATA",
    "MODIFICATION_FEASIBILITY_NOT_MODELED",
]


REQUIRED_BASELINE_RESOURCES: tuple[str, ...] = (
    "scanners",
    "injection_resources",
    "uptake_resources",
    "distribution_concurrency",
    "cyclotron_units",
    "radiopharmacy_units",
    "mrt_base_infrastructure_units",
    "mrt_endpoints",
    "guideway_length_m",
    "vertical_transitions",
    "building_connections",
)


def _trace_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ExistingFacilityMetadata:
    facility_id: str
    facility_name: str
    location: str | None
    baseline_year: int
    provenance_reference_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExistingFacilityResourceFact:
    resource: str
    existing_quantity: float | None
    knowledge_status: DataStatus
    operational_quantity: float | None = None
    unavailable_quantity: float | None = None
    installation_year: int | None = None
    condition_status: str = "UNKNOWN"
    remaining_useful_life_years: float | None = None
    planned_retirement_year: int | None = None
    source_claim_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    provenance_trace_id: str | None = None

    def __post_init__(self) -> None:
        if self.knowledge_status in {"KNOWN", "USER_ASSUMED", "EVIDENCE_BACKED"} and self.existing_quantity is None:
            raise ValueError(f"{self.resource} requires existing_quantity when status is {self.knowledge_status}")
        if self.knowledge_status in {"UNKNOWN", "NOT_MODELED"} and self.existing_quantity is not None:
            raise ValueError(f"{self.resource} must not carry a numeric quantity when status is {self.knowledge_status}")

        if self.existing_quantity is not None and float(self.existing_quantity) < 0.0:
            raise ValueError(f"{self.resource} existing_quantity must be non-negative")
        if self.operational_quantity is not None and float(self.operational_quantity) < 0.0:
            raise ValueError(f"{self.resource} operational_quantity must be non-negative")
        if self.unavailable_quantity is not None and float(self.unavailable_quantity) < 0.0:
            raise ValueError(f"{self.resource} unavailable_quantity must be non-negative")

        if self.existing_quantity is not None and self.operational_quantity is not None:
            if float(self.operational_quantity) > float(self.existing_quantity):
                raise ValueError(f"{self.resource} operational_quantity cannot exceed existing_quantity")


@dataclass(frozen=True)
class ExistingFacilityBaseline:
    metadata: ExistingFacilityMetadata
    current_patients_per_day: float
    resources: Mapping[str, ExistingFacilityResourceFact]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if float(self.current_patients_per_day) <= 0.0:
            raise ValueError("current_patients_per_day must be positive")


@dataclass(frozen=True)
class ExistingFacilityRetrofitRequest:
    project_mode: ProjectMode
    baseline: ExistingFacilityBaseline
    target_patients_per_day: int
    pipeline_template: NativeDecisionPipelineScenario
    conventional_bounds: ConventionalArchitectureBounds
    mrt_bounds: MrtArchitectureBounds
    minimum_reliability: float
    seeds: Sequence[int]
    max_candidate_count: int = 64
    throughput_thresholds_per_day: Sequence[float] = ()
    worst_run_count: int = 3

    def __post_init__(self) -> None:
        if self.project_mode not in {"GREENFIELD", "EXISTING_FACILITY_EXPANSION"}:
            raise ValueError("project_mode must be GREENFIELD or EXISTING_FACILITY_EXPANSION")
        if int(self.target_patients_per_day) <= 0:
            raise ValueError("target_patients_per_day must be greater than zero")
        if not (0.0 < float(self.minimum_reliability) <= 1.0):
            raise ValueError("minimum_reliability must be within (0, 1]")
        if not self.seeds:
            raise ValueError("seeds must not be empty")
        if any(not isinstance(seed, int) for seed in self.seeds):
            raise TypeError("seeds must contain integers")


@dataclass(frozen=True)
class ExistingFacilityOperationalBaseline:
    effective_throughput_per_day: float
    reliability_probability_meeting_target: float
    headroom_per_day: float
    bottleneck_resource: str
    scanner_utilization_pct: float
    injection_utilization_pct: float
    uptake_utilization_pct: float
    distribution_utilization_pct: float
    annual_revenue: float
    annual_opex: float
    lifecycle_npv: float


@dataclass(frozen=True)
class ResourceDispositionRecord:
    resource: str
    evidence_status: DataStatus
    baseline_existing_quantity: float | None
    baseline_operational_quantity: float | None
    baseline_unavailable_quantity: float | None
    conventional_additional_quantity: float | None
    conventional_final_quantity: float | None
    conventional_disposition: ResourceDisposition
    mrt_additional_quantity: float | None
    mrt_final_quantity: float | None
    mrt_disposition: ResourceDisposition


@dataclass(frozen=True)
class PathwayRetrofitResult:
    pathway: Literal["Conventional", "MRT"]
    feasibility_status: RetrofitFeasibilityStatus
    feasibility_reason: str
    candidate_id: str | None
    annual_revenue: float | None
    annual_opex: float | None
    annual_net_cash_flow: float | None
    effective_throughput_per_day: float | None
    reliability_probability_meeting_target: float | None
    bottleneck_resource: str | None
    incremental_capex: float | None
    incremental_annual_opex: float | None
    incremental_annual_revenue: float | None
    incremental_effective_throughput_per_day: float | None
    incremental_npv: float | None
    payback_years: float | None
    final_quantities: Mapping[str, float | None]
    additional_quantities: Mapping[str, float | None]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class RetrofitEconomicRow:
    metric: str
    baseline: float | None
    conventional_future: float | None
    mrt_future: float | None
    conventional_delta_from_baseline: float | None
    mrt_delta_from_baseline: float | None


@dataclass(frozen=True)
class ExistingFacilityRetrofitResult:
    report_trace_id: str
    project_mode: ProjectMode
    baseline: ExistingFacilityBaseline
    baseline_operational: ExistingFacilityOperationalBaseline | None
    baseline_decision_result: NativeDecisionComparisonResult | None
    baseline_reliability_result: NativeReliabilityComparisonResult | None
    recommendation_result: ArchitectureRecommendationResult | None
    conventional: PathwayRetrofitResult
    mrt: PathwayRetrofitResult
    resource_disposition_table: tuple[ResourceDispositionRecord, ...]
    economics_table: tuple[RetrofitEconomicRow, ...]
    bottleneck_migration: Mapping[str, str | None]
    evidence_gaps: tuple[str, ...]
    horizon_compatible_template: NativeDecisionPipelineScenario | None
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class ExistingFacilityRetrofitReportData:
    metadata: Mapping[str, Any]
    baseline_inventory: Mapping[str, ExistingFacilityResourceFact]
    baseline_operational: ExistingFacilityOperationalBaseline | None
    conventional: PathwayRetrofitResult
    mrt: PathwayRetrofitResult
    resource_rows: tuple[ResourceDispositionRecord, ...]
    economics_rows: tuple[RetrofitEconomicRow, ...]
    bottleneck_migration: Mapping[str, str | None]
    feasibility_and_limitations: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    chart_series: Mapping[str, tuple[tuple[float, float], ...]]


def _status_for_value(fact: ExistingFacilityResourceFact) -> bool:
    return fact.knowledge_status in {"KNOWN", "USER_ASSUMED", "EVIDENCE_BACKED"}


def _resource_quantity(baseline: ExistingFacilityBaseline, resource: str) -> float | None:
    fact = baseline.resources.get(resource)
    if fact is None:
        return None
    return None if fact.existing_quantity is None else float(fact.existing_quantity)


def _resource_operational_quantity(baseline: ExistingFacilityBaseline, resource: str) -> float | None:
    fact = baseline.resources.get(resource)
    if fact is None:
        return None
    if fact.operational_quantity is None:
        return None if fact.existing_quantity is None else float(fact.existing_quantity)
    return float(fact.operational_quantity)


def _resource_unavailable_quantity(baseline: ExistingFacilityBaseline, resource: str) -> float | None:
    fact = baseline.resources.get(resource)
    if fact is None:
        return None
    if fact.unavailable_quantity is not None:
        return float(fact.unavailable_quantity)
    if fact.existing_quantity is None:
        return None
    operational = fact.operational_quantity if fact.operational_quantity is not None else fact.existing_quantity
    return max(0.0, float(fact.existing_quantity) - float(operational))


def _missing_required_data(baseline: ExistingFacilityBaseline) -> tuple[str, ...]:
    missing: list[str] = []
    for resource in REQUIRED_BASELINE_RESOURCES:
        fact = baseline.resources.get(resource)
        if fact is None:
            missing.append(resource)
            continue
        if not _status_for_value(fact) or fact.existing_quantity is None:
            missing.append(resource)
    return tuple(missing)


def _as_int(value: float | None, *, default: int = 0) -> int:
    if value is None:
        return int(default)
    return int(round(float(value)))


def _as_float(value: float | None, *, default: float = 0.0) -> float:
    if value is None:
        return float(default)
    return float(value)


def _bounds_at_or_above_baseline(request: ExistingFacilityRetrofitRequest) -> None:
    baseline = request.baseline
    scanners = _as_int(_resource_operational_quantity(baseline, "scanners"), default=1)
    injection = _as_int(_resource_operational_quantity(baseline, "injection_resources"), default=1)
    uptake = _as_int(_resource_operational_quantity(baseline, "uptake_resources"), default=1)
    distribution = _as_int(_resource_operational_quantity(baseline, "distribution_concurrency"), default=1)
    mrt_endpoints = _as_int(_resource_operational_quantity(baseline, "mrt_endpoints"), default=0)

    if min(request.conventional_bounds.scanners) < scanners:
        raise ValueError("conventional_bounds.scanners cannot be below baseline scanners")
    if min(request.conventional_bounds.injection_resources) < injection:
        raise ValueError("conventional_bounds.injection_resources cannot be below baseline injection resources")
    if min(request.conventional_bounds.uptake_resources) < uptake:
        raise ValueError("conventional_bounds.uptake_resources cannot be below baseline uptake resources")
    if min(request.conventional_bounds.distribution_concurrency) < distribution:
        raise ValueError("conventional_bounds.distribution_concurrency cannot be below baseline distribution concurrency")

    if min(request.mrt_bounds.scanners) < scanners:
        raise ValueError("mrt_bounds.scanners cannot be below baseline scanners")
    if min(request.mrt_bounds.injection_resources) < injection:
        raise ValueError("mrt_bounds.injection_resources cannot be below baseline injection resources")
    if min(request.mrt_bounds.uptake_resources) < uptake:
        raise ValueError("mrt_bounds.uptake_resources cannot be below baseline uptake resources")
    if min(request.mrt_bounds.distribution_concurrency) < distribution:
        raise ValueError("mrt_bounds.distribution_concurrency cannot be below baseline distribution concurrency")
    if min(request.mrt_bounds.installed_mrt_endpoints) < mrt_endpoints:
        raise ValueError("mrt_bounds.installed_mrt_endpoints cannot be below baseline mrt_endpoints")


def _baseline_pathway_from_inventory(
    pathway_template: NativePathwayScenario,
    baseline: ExistingFacilityBaseline,
    pathway: Literal["Conventional", "MRT"],
) -> NativePathwayScenario:
    scanners = _as_int(_resource_operational_quantity(baseline, "scanners"), default=pathway_template.scanners)
    injection = _as_int(_resource_operational_quantity(baseline, "injection_resources"), default=pathway_template.injection_resources)
    uptake = _as_int(_resource_operational_quantity(baseline, "uptake_resources"), default=pathway_template.uptake_resources)
    distribution = _as_int(_resource_operational_quantity(baseline, "distribution_concurrency"), default=pathway_template.distribution_concurrency)

    cyclotron_existing = _as_int(_resource_quantity(baseline, "cyclotron_units"), default=pathway_template.installed_cyclotron_units)
    radiopharmacy_existing = _as_int(_resource_quantity(baseline, "radiopharmacy_units"), default=pathway_template.installed_radiopharmacy_units)
    mrt_base_existing = _as_int(_resource_quantity(baseline, "mrt_base_infrastructure_units"), default=pathway_template.installed_mrt_base_infrastructure_units)
    mrt_endpoint_existing = _as_int(_resource_quantity(baseline, "mrt_endpoints"), default=pathway_template.installed_mrt_endpoints)
    guideway_existing = _as_float(_resource_quantity(baseline, "guideway_length_m"), default=pathway_template.installed_guideway_length_m)
    vertical_existing = _as_int(_resource_quantity(baseline, "vertical_transitions"), default=pathway_template.installed_vertical_transitions)
    connection_existing = _as_int(_resource_quantity(baseline, "building_connections"), default=pathway_template.installed_building_connections)

    conventional_allowance_existing = pathway_template.conventional_infrastructure_allowance_units

    installed_carriers = pathway_template.installed_mrt_carriers
    operated_carriers = pathway_template.operated_mrt_carriers
    if pathway == "MRT":
        carrier_fact = baseline.resources.get("mrt_carriers")
        if carrier_fact is not None and _status_for_value(carrier_fact):
            installed_carriers = _as_int(_resource_quantity(baseline, "mrt_carriers"), default=distribution)
            operated_carriers = _as_int(_resource_operational_quantity(baseline, "mrt_carriers"), default=distribution)
        else:
            # Keep the native equivalence between distribution concurrency and active carriers.
            installed_carriers = distribution
            operated_carriers = distribution

    return replace(
        pathway_template,
        deployment_mode="existing_facility_expansion",
        scanners=scanners,
        existing_scanners=scanners,
        injection_resources=injection,
        existing_injection_resources=injection,
        uptake_resources=uptake,
        existing_uptake_resources=uptake,
        distribution_concurrency=distribution,
        installed_cyclotron_units=cyclotron_existing,
        existing_cyclotron_units=cyclotron_existing,
        installed_radiopharmacy_units=radiopharmacy_existing,
        existing_radiopharmacy_units=radiopharmacy_existing,
        operated_cyclotron_units=cyclotron_existing,
        operated_radiopharmacy_units=radiopharmacy_existing,
        conventional_infrastructure_allowance_units=conventional_allowance_existing,
        existing_conventional_infrastructure_allowance_units=conventional_allowance_existing,
        installed_mrt_base_infrastructure_units=mrt_base_existing,
        existing_mrt_base_infrastructure_units=mrt_base_existing,
        installed_mrt_endpoints=mrt_endpoint_existing,
        existing_mrt_endpoints=mrt_endpoint_existing,
        operated_mrt_endpoints=mrt_endpoint_existing,
        installed_guideway_length_m=guideway_existing,
        existing_guideway_length_m=guideway_existing,
        operated_guideway_length_m=guideway_existing,
        installed_vertical_transitions=vertical_existing,
        existing_vertical_transitions=vertical_existing,
        operated_vertical_transitions=vertical_existing,
        installed_building_connections=connection_existing,
        existing_building_connections=connection_existing,
        operated_building_connections=connection_existing,
        installed_mrt_carriers=installed_carriers,
        operated_mrt_carriers=operated_carriers,
    )


def _build_baseline_template(request: ExistingFacilityRetrofitRequest) -> NativeDecisionPipelineScenario:
    return replace(
        request.pipeline_template,
        target_patients_per_day=max(1, int(math.ceil(request.baseline.current_patients_per_day))),
        conventional=_baseline_pathway_from_inventory(request.pipeline_template.conventional, request.baseline, "Conventional"),
        mrt=_baseline_pathway_from_inventory(request.pipeline_template.mrt, request.baseline, "MRT"),
    )


def _safe_payback(incremental_capex: float | None, incremental_net_cash_flow: float | None) -> float | None:
    if incremental_capex is None or incremental_net_cash_flow is None:
        return None
    if incremental_net_cash_flow <= 0.0:
        return None
    return float(incremental_capex) / float(incremental_net_cash_flow)


def _classify_disposition(resource: str, existing: float | None, final: float | None) -> ResourceDisposition:
    if existing is None or final is None:
        return "NOT_MODELED"
    if final > existing:
        if existing == 0.0:
            return "NEW"
        return "EXPAND"
    if final < existing:
        return "RETIRE"
    if resource in {"cyclotron_units", "radiopharmacy_units"} and existing > 0.0:
        return "REUSE"
    return "RETAIN"


def _modification_feasibility_note(additional_quantities: Mapping[str, float | None]) -> tuple[str, ...]:
    physical_resources = {
        "scanners",
        "injection_resources",
        "uptake_resources",
        "mrt_endpoints",
        "guideway_length_m",
        "vertical_transitions",
        "building_connections",
    }
    for resource, delta in additional_quantities.items():
        if resource in physical_resources and delta is not None and delta > 0.0:
            return ("MODIFICATION_FEASIBILITY_NOT_MODELED",)
    return ()


def _candidate_pathway_result(candidate: ArchitectureCandidateResult, pathway: Literal["Conventional", "MRT"]) -> NativeDecisionComparisonResult:
    return candidate.direct_decision_result


def _final_quantity_for_resource(candidate: ArchitectureCandidateResult, resource: str) -> float | None:
    architecture = candidate.architecture
    if resource == "scanners":
        return float(architecture.scanners)
    if resource == "injection_resources":
        return float(architecture.injection_resources)
    if resource == "uptake_resources":
        return float(architecture.uptake_resources)
    if resource == "distribution_concurrency":
        return float(architecture.distribution_concurrency)
    if resource == "cyclotron_units":
        return float(candidate.capex_result.installed_quantities["installed_cyclotron_units"])
    if resource == "radiopharmacy_units":
        return float(architecture.installed_radiopharmacy_units)
    if resource == "mrt_base_infrastructure_units":
        return float(architecture.installed_mrt_base_infrastructure_units)
    if resource == "mrt_endpoints":
        return float(architecture.installed_mrt_endpoints)
    if resource == "guideway_length_m":
        return float(architecture.installed_guideway_length_m)
    if resource == "vertical_transitions":
        return float(architecture.installed_vertical_transitions)
    if resource == "building_connections":
        return float(architecture.installed_building_connections)
    if resource == "mrt_carriers":
        if architecture.installed_mrt_carriers is None:
            return None
        return float(architecture.installed_mrt_carriers)
    return None


def _build_pathway_result(
    *,
    pathway: Literal["Conventional", "MRT"],
    candidate: ArchitectureCandidateResult | None,
    baseline_operational: ExistingFacilityOperationalBaseline,
    baseline_lifecycle_npv: float,
    baseline_quantities: Mapping[str, float | None],
) -> PathwayRetrofitResult:
    if candidate is None:
        return PathwayRetrofitResult(
            pathway=pathway,
            feasibility_status="INFEASIBLE_WITHIN_BOUNDS",
            feasibility_reason="No qualifying architecture met the minimum reliability within bounded retrofit search.",
            candidate_id=None,
            annual_revenue=None,
            annual_opex=None,
            annual_net_cash_flow=None,
            effective_throughput_per_day=None,
            reliability_probability_meeting_target=None,
            bottleneck_resource=None,
            incremental_capex=None,
            incremental_annual_opex=None,
            incremental_annual_revenue=None,
            incremental_effective_throughput_per_day=None,
            incremental_npv=None,
            payback_years=None,
            final_quantities={resource: None for resource in baseline_quantities},
            additional_quantities={resource: None for resource in baseline_quantities},
            limitations=("Bounded search did not find a qualifying configuration.",),
        )

    pathway_result = _candidate_pathway_result(candidate, pathway)
    selected = pathway_result.conventional if pathway == "Conventional" else pathway_result.mrt
    annual_revenue = float(selected.annual_revenue)
    annual_opex = float(selected.annual_opex)
    annual_net_cash_flow = annual_revenue - annual_opex
    effective_throughput = float(selected.actual_lifecycle_throughput_per_day)
    reliability = float(candidate.measured_reliability)
    incremental_capex = float(candidate.capex_result.total_capex)
    incremental_annual_opex = annual_opex - baseline_operational.annual_opex
    incremental_annual_revenue = annual_revenue - baseline_operational.annual_revenue
    incremental_effective_throughput = effective_throughput - baseline_operational.effective_throughput_per_day
    incremental_npv = float(candidate.lifecycle_npv - baseline_lifecycle_npv)

    final_quantities: dict[str, float | None] = {}
    additional_quantities: dict[str, float | None] = {}
    for resource, existing in baseline_quantities.items():
        final_value = _final_quantity_for_resource(candidate, resource)
        final_quantities[resource] = final_value
        if existing is None or final_value is None:
            additional_quantities[resource] = None
        else:
            additional_quantities[resource] = float(final_value - existing)

    modification_limits = _modification_feasibility_note(additional_quantities)
    feasibility_status: RetrofitFeasibilityStatus
    if modification_limits:
        feasibility_status = "MODIFICATION_FEASIBILITY_NOT_MODELED"
    elif any((value is not None and value > 0.0) for value in additional_quantities.values()):
        feasibility_status = "FEASIBLE_WITH_EXPANSION"
    else:
        feasibility_status = "FEASIBLE"

    return PathwayRetrofitResult(
        pathway=pathway,
        feasibility_status=feasibility_status,
        feasibility_reason=(
            "Retrofit expansion is numerically feasible, but physical modification feasibility is not modeled."
            if feasibility_status == "MODIFICATION_FEASIBILITY_NOT_MODELED"
            else "Retrofit pathway qualified under native bounded recommendation search."
        ),
        candidate_id=candidate.candidate_id,
        annual_revenue=annual_revenue,
        annual_opex=annual_opex,
        annual_net_cash_flow=annual_net_cash_flow,
        effective_throughput_per_day=effective_throughput,
        reliability_probability_meeting_target=reliability,
        bottleneck_resource=str(candidate.bottleneck_summary.resource),
        incremental_capex=incremental_capex,
        incremental_annual_opex=incremental_annual_opex,
        incremental_annual_revenue=incremental_annual_revenue,
        incremental_effective_throughput_per_day=incremental_effective_throughput,
        incremental_npv=incremental_npv,
        payback_years=_safe_payback(incremental_capex, incremental_annual_revenue - incremental_annual_opex),
        final_quantities=final_quantities,
        additional_quantities=additional_quantities,
        limitations=modification_limits,
    )


def _build_resource_disposition_table(
    baseline: ExistingFacilityBaseline,
    conventional: PathwayRetrofitResult,
    mrt: PathwayRetrofitResult,
) -> tuple[ResourceDispositionRecord, ...]:
    rows: list[ResourceDispositionRecord] = []
    tracked_resources = dict(baseline.resources)
    tracked_resources.setdefault("mrt_carriers", ExistingFacilityResourceFact(resource="mrt_carriers", existing_quantity=None, knowledge_status="NOT_MODELED"))

    for resource, fact in tracked_resources.items():
        existing = _resource_quantity(baseline, resource)
        operational = _resource_operational_quantity(baseline, resource)
        unavailable = _resource_unavailable_quantity(baseline, resource)

        conv_final = conventional.final_quantities.get(resource)
        conv_add = conventional.additional_quantities.get(resource)
        mrt_final = mrt.final_quantities.get(resource)
        mrt_add = mrt.additional_quantities.get(resource)

        rows.append(
            ResourceDispositionRecord(
                resource=resource,
                evidence_status=fact.knowledge_status,
                baseline_existing_quantity=existing,
                baseline_operational_quantity=operational,
                baseline_unavailable_quantity=unavailable,
                conventional_additional_quantity=conv_add,
                conventional_final_quantity=conv_final,
                conventional_disposition=_classify_disposition(resource, existing, conv_final),
                mrt_additional_quantity=mrt_add,
                mrt_final_quantity=mrt_final,
                mrt_disposition=_classify_disposition(resource, existing, mrt_final),
            )
        )

    return tuple(sorted(rows, key=lambda row: row.resource))


def _economic_table(
    baseline: ExistingFacilityOperationalBaseline,
    conventional: PathwayRetrofitResult,
    mrt: PathwayRetrofitResult,
) -> tuple[RetrofitEconomicRow, ...]:
    def row(metric: str, b: float | None, c: float | None, m: float | None) -> RetrofitEconomicRow:
        return RetrofitEconomicRow(
            metric=metric,
            baseline=b,
            conventional_future=c,
            mrt_future=m,
            conventional_delta_from_baseline=(None if b is None or c is None else c - b),
            mrt_delta_from_baseline=(None if b is None or m is None else m - b),
        )

    return (
        row("effective_throughput_per_day", baseline.effective_throughput_per_day, conventional.effective_throughput_per_day, mrt.effective_throughput_per_day),
        row("reliability_probability_meeting_target", baseline.reliability_probability_meeting_target, conventional.reliability_probability_meeting_target, mrt.reliability_probability_meeting_target),
        row("annual_revenue", baseline.annual_revenue, conventional.annual_revenue, mrt.annual_revenue),
        row("annual_opex", baseline.annual_opex, conventional.annual_opex, mrt.annual_opex),
        row("lifecycle_npv", baseline.lifecycle_npv, (None if conventional.incremental_npv is None else baseline.lifecycle_npv + conventional.incremental_npv), (None if mrt.incremental_npv is None else baseline.lifecycle_npv + mrt.incremental_npv)),
        row("incremental_capex", 0.0, conventional.incremental_capex, mrt.incremental_capex),
    )


def _baseline_operational(
    baseline_decision: NativeDecisionComparisonResult,
    baseline_reliability: NativeReliabilityComparisonResult,
    baseline_target: float,
) -> ExistingFacilityOperationalBaseline:
    conventional_path = baseline_decision.conventional
    reliability_summary = baseline_reliability.conventional
    headroom = float(reliability_summary.throughput_distribution.mean) - float(baseline_target)
    return ExistingFacilityOperationalBaseline(
        effective_throughput_per_day=float(conventional_path.actual_lifecycle_throughput_per_day),
        reliability_probability_meeting_target=float(reliability_summary.probability_meeting_target_demand),
        headroom_per_day=headroom,
        bottleneck_resource=str(conventional_path.operational_result.bottleneck.resource),
        scanner_utilization_pct=float(conventional_path.operational_result.scanner_utilization_pct),
        injection_utilization_pct=float(conventional_path.operational_result.injection_utilization_pct),
        uptake_utilization_pct=float(conventional_path.operational_result.uptake_utilization_pct),
        distribution_utilization_pct=float(conventional_path.operational_result.distribution_utilization_pct),
        annual_revenue=float(conventional_path.annual_revenue),
        annual_opex=float(conventional_path.annual_opex),
        lifecycle_npv=float(conventional_path.lifecycle_result.final_npv),
    )


def run_native_existing_facility_retrofit(
    request: ExistingFacilityRetrofitRequest,
) -> ExistingFacilityRetrofitResult:
    if request.project_mode == "GREENFIELD":
        recommendation = run_native_architecture_recommendation(
            ArchitectureRecommendationRequest(
                target_patients_per_day=int(request.target_patients_per_day),
                minimum_reliability=float(request.minimum_reliability),
                seeds=tuple(int(seed) for seed in request.seeds),
                pipeline_template=request.pipeline_template,
                conventional_bounds=request.conventional_bounds,
                mrt_bounds=request.mrt_bounds,
                max_candidate_count=int(request.max_candidate_count),
                throughput_thresholds_per_day=tuple(float(value) for value in request.throughput_thresholds_per_day),
                worst_run_count=int(request.worst_run_count),
            )
        )
        empty_path = PathwayRetrofitResult(
            pathway="Conventional",
            feasibility_status="FEASIBLE",
            feasibility_reason="GREENFIELD mode bypasses retrofit baseline modeling.",
            candidate_id=None,
            annual_revenue=None,
            annual_opex=None,
            annual_net_cash_flow=None,
            effective_throughput_per_day=None,
            reliability_probability_meeting_target=None,
            bottleneck_resource=None,
            incremental_capex=None,
            incremental_annual_opex=None,
            incremental_annual_revenue=None,
            incremental_effective_throughput_per_day=None,
            incremental_npv=None,
            payback_years=None,
            final_quantities={},
            additional_quantities={},
            limitations=("Greenfield pass-through mode.",),
        )
        return ExistingFacilityRetrofitResult(
            report_trace_id=_trace_id({"project_mode": request.project_mode, "target": request.target_patients_per_day}),
            project_mode=request.project_mode,
            baseline=request.baseline,
            baseline_operational=None,
            baseline_decision_result=None,
            baseline_reliability_result=None,
            recommendation_result=recommendation,
            conventional=empty_path,
            mrt=replace(empty_path, pathway="MRT"),
            resource_disposition_table=(),
            economics_table=(),
            bottleneck_migration={},
            evidence_gaps=(),
            horizon_compatible_template=request.pipeline_template,
            limitations=("GREENFIELD mode intentionally leaves existing-facility retrofit calculations disabled.",),
        )

    missing = _missing_required_data(request.baseline)
    if missing:
        insuff = PathwayRetrofitResult(
            pathway="Conventional",
            feasibility_status="INSUFFICIENT_BASELINE_DATA",
            feasibility_reason=(
                "Cannot compute retrofit economics because required baseline resources are missing: "
                f"{sorted(missing)}"
            ),
            candidate_id=None,
            annual_revenue=None,
            annual_opex=None,
            annual_net_cash_flow=None,
            effective_throughput_per_day=None,
            reliability_probability_meeting_target=None,
            bottleneck_resource=None,
            incremental_capex=None,
            incremental_annual_opex=None,
            incremental_annual_revenue=None,
            incremental_effective_throughput_per_day=None,
            incremental_npv=None,
            payback_years=None,
            final_quantities={resource: None for resource in request.baseline.resources},
            additional_quantities={resource: None for resource in request.baseline.resources},
            limitations=("UNKNOWN baseline resource quantities are not automatically converted to zero.",),
        )
        return ExistingFacilityRetrofitResult(
            report_trace_id=_trace_id({"project_mode": request.project_mode, "missing": sorted(missing)}),
            project_mode=request.project_mode,
            baseline=request.baseline,
            baseline_operational=None,
            baseline_decision_result=None,
            baseline_reliability_result=None,
            recommendation_result=None,
            conventional=insuff,
            mrt=replace(insuff, pathway="MRT"),
            resource_disposition_table=(),
            economics_table=(),
            bottleneck_migration={},
            evidence_gaps=tuple(sorted(missing)),
            horizon_compatible_template=None,
            limitations=("Retrofit analysis halted due to insufficient baseline data.",),
        )

    _bounds_at_or_above_baseline(request)

    baseline_template = _build_baseline_template(request)
    baseline_decision = run_native_decision_pipeline(baseline_template)
    baseline_target = float(request.baseline.current_patients_per_day)
    baseline_reliability = run_native_reliability_engine(
        baseline_template,
        tuple(int(seed) for seed in request.seeds),
        throughput_thresholds_per_day=tuple(float(value) for value in (request.throughput_thresholds_per_day or (baseline_target,))),
        worst_run_count=int(request.worst_run_count),
    )
    baseline_operational = _baseline_operational(baseline_decision, baseline_reliability, baseline_target)

    expansion_template = replace(
        baseline_template,
        target_patients_per_day=int(request.target_patients_per_day),
    )
    recommendation = run_native_architecture_recommendation(
        ArchitectureRecommendationRequest(
            target_patients_per_day=int(request.target_patients_per_day),
            minimum_reliability=float(request.minimum_reliability),
            seeds=tuple(int(seed) for seed in request.seeds),
            pipeline_template=expansion_template,
            conventional_bounds=request.conventional_bounds,
            mrt_bounds=request.mrt_bounds,
            max_candidate_count=int(request.max_candidate_count),
            throughput_thresholds_per_day=tuple(float(value) for value in request.throughput_thresholds_per_day),
            worst_run_count=int(request.worst_run_count),
        )
    )

    baseline_quantities = {
        resource: _resource_quantity(request.baseline, resource)
        for resource in tuple(request.baseline.resources.keys()) + ("mrt_carriers",)
    }

    conventional = _build_pathway_result(
        pathway="Conventional",
        candidate=recommendation.best_qualifying_conventional,
        baseline_operational=baseline_operational,
        baseline_lifecycle_npv=baseline_operational.lifecycle_npv,
        baseline_quantities=baseline_quantities,
    )
    mrt = _build_pathway_result(
        pathway="MRT",
        candidate=recommendation.best_qualifying_mrt,
        baseline_operational=baseline_operational,
        baseline_lifecycle_npv=baseline_operational.lifecycle_npv,
        baseline_quantities=baseline_quantities,
    )

    resource_rows = _build_resource_disposition_table(request.baseline, conventional, mrt)
    economics_rows = _economic_table(baseline_operational, conventional, mrt)

    bottleneck_migration = {
        "baseline": baseline_operational.bottleneck_resource,
        "conventional_future": conventional.bottleneck_resource,
        "mrt_future": mrt.bottleneck_resource,
    }

    limitations = (
        "RESIDUAL_VALUE_NOT_MODELED",
        "Carrier CAPEX/OPEX/energy are not inferred when authoritative per-carrier coefficients are unavailable.",
    )

    return ExistingFacilityRetrofitResult(
        report_trace_id=_trace_id(
            {
                "facility_id": request.baseline.metadata.facility_id,
                "project_mode": request.project_mode,
                "baseline_year": request.baseline.metadata.baseline_year,
                "current_patients_per_day": request.baseline.current_patients_per_day,
                "target_patients_per_day": request.target_patients_per_day,
                "baseline_trace": baseline_decision.provenance.comparison_trace_id,
                "recommendation_trace": recommendation.provenance.aggregate_trace_id,
            }
        ),
        project_mode=request.project_mode,
        baseline=request.baseline,
        baseline_operational=baseline_operational,
        baseline_decision_result=baseline_decision,
        baseline_reliability_result=baseline_reliability,
        recommendation_result=recommendation,
        conventional=conventional,
        mrt=mrt,
        resource_disposition_table=resource_rows,
        economics_table=economics_rows,
        bottleneck_migration=bottleneck_migration,
        evidence_gaps=(),
        horizon_compatible_template=baseline_template,
        limitations=limitations,
    )


def build_native_existing_facility_retrofit_report_data(
    result: ExistingFacilityRetrofitResult,
) -> ExistingFacilityRetrofitReportData:
    metadata = {
        "report_trace_id": result.report_trace_id,
        "project_mode": result.project_mode,
        "facility_id": result.baseline.metadata.facility_id,
        "facility_name": result.baseline.metadata.facility_name,
        "location": result.baseline.metadata.location,
        "baseline_year": result.baseline.metadata.baseline_year,
        "current_patients_per_day": result.baseline.current_patients_per_day,
    }

    chart_series: dict[str, tuple[tuple[float, float], ...]] = {
        "throughput": (
            (0.0, 0.0 if result.baseline_operational is None else result.baseline_operational.effective_throughput_per_day),
            (1.0, 0.0 if result.conventional.effective_throughput_per_day is None else result.conventional.effective_throughput_per_day),
            (2.0, 0.0 if result.mrt.effective_throughput_per_day is None else result.mrt.effective_throughput_per_day),
        ),
        "reliability": (
            (0.0, 0.0 if result.baseline_operational is None else result.baseline_operational.reliability_probability_meeting_target),
            (1.0, 0.0 if result.conventional.reliability_probability_meeting_target is None else result.conventional.reliability_probability_meeting_target),
            (2.0, 0.0 if result.mrt.reliability_probability_meeting_target is None else result.mrt.reliability_probability_meeting_target),
        ),
        "incremental_capex": (
            (1.0, 0.0 if result.conventional.incremental_capex is None else result.conventional.incremental_capex),
            (2.0, 0.0 if result.mrt.incremental_capex is None else result.mrt.incremental_capex),
        ),
    }

    feasibility_and_limitations = tuple(
        [
            f"Conventional feasibility: {result.conventional.feasibility_status}",
            f"MRT feasibility: {result.mrt.feasibility_status}",
            *result.conventional.limitations,
            *result.mrt.limitations,
            *result.limitations,
        ]
    )

    return ExistingFacilityRetrofitReportData(
        metadata=metadata,
        baseline_inventory=dict(result.baseline.resources),
        baseline_operational=result.baseline_operational,
        conventional=result.conventional,
        mrt=result.mrt,
        resource_rows=result.resource_disposition_table,
        economics_rows=result.economics_table,
        bottleneck_migration=dict(result.bottleneck_migration),
        feasibility_and_limitations=feasibility_and_limitations,
        evidence_gaps=result.evidence_gaps,
        chart_series=chart_series,
    )


def build_design_horizon_request_from_existing_facility_retrofit(
    result: ExistingFacilityRetrofitResult,
    *,
    analysis_years: int,
    demand_mode: Literal["constant", "compound", "explicit", "milestone"] = "constant",
    constant_daily_demand: float | None = None,
) -> DesignHorizonPlanningRequest:
    if result.horizon_compatible_template is None:
        raise ValueError("horizon_compatible_template is unavailable for this retrofit result")
    return DesignHorizonPlanningRequest(
        pipeline_template=result.horizon_compatible_template,
        seeds=tuple(result.recommendation_result.request.seeds) if result.recommendation_result is not None else (20260813,),
        analysis_years=int(analysis_years),
        demand_mode=demand_mode,
        constant_daily_demand=constant_daily_demand,
    )


def apply_accepted_proposal_to_baseline_resource(
    baseline: ExistingFacilityBaseline,
    *,
    resource: str,
    proposal: EngineeringAssumptionProposal,
) -> ExistingFacilityBaseline:
    if proposal.promotion_status != "accepted":
        raise ValueError("proposal must be accepted before baseline promotion")
    if proposal.conflict_status in {"conflict", "not_comparable"}:
        raise ValueError("conflicted proposal cannot be promoted into baseline")
    if resource not in baseline.resources:
        raise ValueError(f"unknown baseline resource: {resource}")

    value = float(proposal.proposed_value)
    existing = baseline.resources[resource]
    updated_fact = replace(
        existing,
        existing_quantity=value,
        operational_quantity=value if existing.operational_quantity is None else existing.operational_quantity,
        knowledge_status="EVIDENCE_BACKED",
        source_claim_ids=tuple(dict.fromkeys(existing.source_claim_ids + tuple(proposal.supporting_claim_ids))),
        provenance_trace_id=proposal.trace_id,
    )
    updated_resources = dict(baseline.resources)
    updated_resources[resource] = updated_fact
    return replace(baseline, resources=updated_resources)

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import hashlib
import json
from typing import Any, Literal, Mapping, Protocol, Sequence

from decision_pipeline import NativeDecisionComparisonResult
from engineering_evidence import (
    ComparableProjectEvidence,
    EngineeringEvidenceClaim,
    EngineeringEvidenceConflict,
    EngineeringEvidenceRepository,
    EngineeringEvidenceSource,
)


ImageAvailabilityStatus = Literal[
    "VERIFIED_PROJECT_IMAGE",
    "VERIFIED_FACILITY_IMAGE",
    "VERIFIED_COMPONENT_IMAGE",
    "SOURCE_PAGE_HAS_IMAGE",
    "IMAGE_NOT_FOUND",
    "IMAGE_IDENTITY_UNCERTAIN",
    "IMAGE_NOT_APPLICABLE",
]
ComparisonConfidenceLabel = Literal["HIGH", "MODERATE", "LOW", "INSUFFICIENT_EVIDENCE"]
ProjectValueBasis = Literal["actual", "estimate", "tender", "quote", "inferred", "unknown"]
OperationalStatus = Literal["planned", "operational", "commissioning", "unknown"]


def _trace_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _safe_ratio(value: float, reference: float) -> float:
    denom = max(abs(reference), abs(value), 1.0)
    return min(1.0, max(0.0, 1.0 - (abs(value - reference) / denom)))


def _as_set(values: Sequence[str] | None) -> set[str]:
    return {value.strip() for value in (values or ()) if value and value.strip()}


@dataclass(frozen=True)
class ProjectImageReference:
    image_reference_id: str
    image_source_url: str | None
    image_page_url: str | None
    image_source_organization: str | None
    image_caption: str | None
    image_provenance: str | None
    image_retrieval_date: date | None
    image_status: ImageAvailabilityStatus
    image_confidence: float | None


@dataclass(frozen=True)
class ComparableProjectIdentity:
    project_id: str
    facility_name: str
    owner_organization: str | None
    city: str | None
    state_or_province: str | None
    country: str | None
    region: str | None
    facility_type: str | None
    operational_status: OperationalStatus
    opening_year: int | None
    description: str | None


@dataclass(frozen=True)
class ComparableProjectClinicalScale:
    patients_per_day: float | None = None
    patients_per_year: float | None = None
    pet_scans_per_day: float | None = None
    spect_scans_per_day: float | None = None
    scanner_count: int | None = None
    pet_ct_count: int | None = None
    pet_mr_count: int | None = None
    uptake_rooms: int | None = None
    injection_resources: int | None = None
    operating_hours_per_day: float | None = None


@dataclass(frozen=True)
class ComparableProjectProduction:
    cyclotron_count: int | None = None
    cyclotron_manufacturer: str | None = None
    cyclotron_model: str | None = None
    beam_energy_mev: float | None = None
    target_stations: int | None = None
    radiopharmacy_presence: bool | None = None
    production_suites: int | None = None
    hot_cells: int | None = None
    supported_radionuclides: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComparableProjectFacility:
    facility_area_m2: float | None = None
    radiopharmacy_area_m2: float | None = None
    number_of_floors: int | None = None
    campus_arrangement: str | None = None
    internal_transport_approach: str | None = None
    shielding_descriptor: str | None = None


@dataclass(frozen=True)
class ComparableProjectEconomics:
    reported_project_capex: float | None = None
    reported_cyclotron_capex: float | None = None
    reported_radiopharmacy_capex: float | None = None
    reported_construction_cost: float | None = None
    reported_annual_opex: float | None = None
    currency: str | None = None
    currency_year: int | None = None
    value_basis: ProjectValueBasis = "unknown"


@dataclass(frozen=True)
class ComparableProjectPerformance:
    reported_patient_capacity_per_day: float | None = None
    reported_throughput_per_day: float | None = None
    utilization_pct: float | None = None
    production_capacity_descriptor: str | None = None


@dataclass(frozen=True)
class ComparableProjectEvidenceRecord:
    identity: ComparableProjectIdentity
    clinical: ComparableProjectClinicalScale = field(default_factory=ComparableProjectClinicalScale)
    production: ComparableProjectProduction = field(default_factory=ComparableProjectProduction)
    facility: ComparableProjectFacility = field(default_factory=ComparableProjectFacility)
    economics: ComparableProjectEconomics = field(default_factory=ComparableProjectEconomics)
    performance: ComparableProjectPerformance = field(default_factory=ComparableProjectPerformance)
    source_ids: tuple[str, ...] = ()
    document_ids: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()
    source_urls: tuple[str, ...] = ()
    source_tiers: tuple[str, ...] = ()
    evidence_dates: tuple[date | None, ...] = ()
    conflicts: tuple[EngineeringEvidenceConflict, ...] = ()
    missing_fields: tuple[str, ...] = ()
    confidence: float | None = None
    image_reference: ProjectImageReference | None = None

    @property
    def comparable_but_not_visually_complete(self) -> bool:
        return self.image_reference is None or self.image_reference.image_status in {
            "IMAGE_NOT_FOUND",
            "IMAGE_IDENTITY_UNCERTAIN",
        }


@dataclass(frozen=True)
class NormalizedComparableProjectProfile:
    project: ComparableProjectEvidenceRecord
    known_dimensions: Mapping[str, Any]
    range_dimensions: Mapping[str, tuple[float | None, float | None]]
    inferred_dimensions: Mapping[str, Any]
    conflicting_dimensions: Mapping[str, tuple[Any, ...]]
    missing_dimensions: tuple[str, ...]


@dataclass(frozen=True)
class TargetConventionalProjectProfile:
    project_name: str
    target_patients_per_day: float | None
    annual_patients: float | None
    scanner_count: int | None
    injection_resources: int | None
    uptake_resources: int | None
    cyclotron_count: int | None
    radionuclides: tuple[str, ...]
    radiopharmacy_units: int | None
    distribution_concurrency: int | None
    operating_hours_per_day: float | None
    conventional_capex: float | None
    conventional_annual_opex: float | None
    conventional_annual_revenue: float | None
    conventional_currency: str | None
    conventional_currency_year: int | None
    conventional_reliability: float | None
    conventional_effective_throughput: float | None
    horizon_years: int | None
    location_region: str | None = None
    location_country: str | None = None


@dataclass(frozen=True)
class SimilarityDimensionScore:
    dimension: str
    score_pct: float | None
    weighted_contribution: float
    weight: float
    compared: bool
    reason: str


@dataclass(frozen=True)
class ComparableSimilarityResult:
    project_id: str
    similarity_pct: float
    evidence_coverage_pct: float
    comparison_confidence_score: float
    confidence_label: ComparisonConfidenceLabel
    component_scores: tuple[SimilarityDimensionScore, ...]
    strongest_matches: tuple[str, ...]
    meaningful_differences: tuple[str, ...]
    unavailable_dimensions: tuple[str, ...]
    unresolved_conflicts: tuple[str, ...]
    evidence_limitations: tuple[str, ...]
    similarity_summary: str
    why_ranked_here: str


@dataclass(frozen=True)
class SimilarityEngineConfig:
    dimension_weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "patients_per_day": 1.5,
            "annual_patients": 1.0,
            "scanner_count": 1.5,
            "cyclotron_count": 1.5,
            "radionuclides": 1.5,
            "radiopharmacy_presence": 1.0,
            "facility_area_m2": 0.8,
            "project_capex": 1.2,
            "annual_opex": 1.2,
            "operating_hours_per_day": 0.8,
            "facility_type": 0.8,
            "country": 0.4,
        }
    )


@dataclass(frozen=True)
class ProjectRankingOptions:
    top_n: int = 5
    minimum_similarity_pct: float = 0.0
    minimum_evidence_coverage_pct: float = 0.0
    minimum_confidence_score: float = 0.0
    region_filter: str | None = None
    country_filter: str | None = None
    facility_type_filter: str | None = None
    operational_status_filter: OperationalStatus | None = None
    required_image_status_for_display_ready: ImageAvailabilityStatus | None = None


@dataclass(frozen=True)
class RankedComparableProject:
    rank: int
    project: ComparableProjectEvidenceRecord
    normalized_profile: NormalizedComparableProjectProfile
    similarity: ComparableSimilarityResult


@dataclass(frozen=True)
class ConventionalVsMrtDelta:
    capex_delta_mrt_minus_conventional: float | None
    annual_opex_delta_mrt_minus_conventional: float | None
    annual_revenue_delta_mrt_minus_conventional: float | None
    effective_throughput_delta_mrt_minus_conventional: float | None
    reliability_delta_mrt_minus_conventional: float | None
    npv_delta_mrt_minus_conventional: float | None
    payback_year_delta_mrt_minus_conventional: float | None
    scanner_count_delta_mrt_minus_conventional: int | None
    cyclotron_count_delta_mrt_minus_conventional: int | None


@dataclass(frozen=True)
class ComparableProjectReportData:
    target_conventional_summary: TargetConventionalProjectProfile
    top_comparable_projects: tuple[RankedComparableProject, ...]
    project_source_links: Mapping[str, tuple[str, ...]]
    claim_citations: Mapping[str, tuple[str, ...]]
    conventional_native_metrics: Mapping[str, float | int | None]
    mrt_native_metrics: Mapping[str, float | int | None]
    conventional_vs_mrt_deltas: ConventionalVsMrtDelta
    limitations: tuple[str, ...]
    provenance_trace_id: str


class ComparableProjectEvidenceProvider(Protocol):
    def list_projects(self) -> tuple[ComparableProjectEvidenceRecord, ...]:
        ...


@dataclass(frozen=True)
class StaticEvidenceProvider:
    projects: tuple[ComparableProjectEvidenceRecord, ...]

    def list_projects(self) -> tuple[ComparableProjectEvidenceRecord, ...]:
        return self.projects


class LocalEvidenceProvider:
    def __init__(
        self,
        *,
        repository: EngineeringEvidenceRepository,
        projects: Sequence[ComparableProjectEvidenceRecord],
    ) -> None:
        self._repository = repository
        self._projects = tuple(projects)

    def list_projects(self) -> tuple[ComparableProjectEvidenceRecord, ...]:
        return self._projects

    def retrieve_project_evidence(self, *, query: str) -> Mapping[str, tuple[str, ...]]:
        hits = self._repository.retrieve(query=query)
        by_project: dict[str, list[str]] = {project.identity.project_id: [] for project in self._projects}
        claim_lookup = self._repository.claims

        for hit in hits:
            chunk_id = hit.chunk_id
            for claim in claim_lookup.values():
                if claim.chunk_id != chunk_id:
                    continue
                for project in self._projects:
                    if claim.claim_id in project.claim_ids:
                        by_project[project.identity.project_id].append(claim.claim_id)
        return {project_id: tuple(sorted(set(values))) for project_id, values in by_project.items()}


def deduplicate_projects(projects: Sequence[ComparableProjectEvidenceRecord]) -> tuple[ComparableProjectEvidenceRecord, ...]:
    merged: dict[str, ComparableProjectEvidenceRecord] = {}
    for project in projects:
        key = "|".join(
            [
                (project.identity.facility_name or "").strip().lower(),
                (project.identity.owner_organization or "").strip().lower(),
                (project.identity.city or "").strip().lower(),
                (project.identity.country or "").strip().lower(),
                str(project.identity.opening_year or ""),
            ]
        )
        if key not in merged:
            merged[key] = project
            continue

        prior = merged[key]
        combined_claim_ids = tuple(sorted(set(prior.claim_ids).union(project.claim_ids)))
        combined_source_ids = tuple(sorted(set(prior.source_ids).union(project.source_ids)))
        combined_doc_ids = tuple(sorted(set(prior.document_ids).union(project.document_ids)))
        combined_urls = tuple(sorted(set(prior.source_urls).union(project.source_urls)))
        combined_tiers = tuple(sorted(set(prior.source_tiers).union(project.source_tiers)))
        combined_dates = tuple(sorted(set(prior.evidence_dates), key=lambda value: (value is None, value)))
        combined_conflicts = tuple({conflict.conflict_id: conflict for conflict in prior.conflicts + project.conflicts}.values())
        combined_missing = tuple(sorted(set(prior.missing_fields).intersection(project.missing_fields)))

        merged[key] = ComparableProjectEvidenceRecord(
            identity=prior.identity,
            clinical=prior.clinical,
            production=prior.production,
            facility=prior.facility,
            economics=prior.economics,
            performance=prior.performance,
            source_ids=combined_source_ids,
            document_ids=combined_doc_ids,
            claim_ids=combined_claim_ids,
            source_urls=combined_urls,
            source_tiers=combined_tiers,
            evidence_dates=combined_dates,
            conflicts=combined_conflicts,
            missing_fields=combined_missing,
            confidence=max(value for value in [prior.confidence, project.confidence] if value is not None)
            if any(value is not None for value in [prior.confidence, project.confidence])
            else None,
            image_reference=prior.image_reference or project.image_reference,
        )
    return tuple(sorted(merged.values(), key=lambda record: record.identity.project_id))


def normalize_comparable_project(project: ComparableProjectEvidenceRecord) -> NormalizedComparableProjectProfile:
    known: dict[str, Any] = {}
    ranges: dict[str, tuple[float | None, float | None]] = {}
    inferred: dict[str, Any] = {}
    conflicts: dict[str, tuple[Any, ...]] = {}
    missing: list[str] = []

    def assign(name: str, value: Any) -> None:
        if value is None:
            missing.append(name)
        else:
            known[name] = value

    assign("patients_per_day", project.clinical.patients_per_day)
    assign("patients_per_year", project.clinical.patients_per_year)
    assign("scanner_count", project.clinical.scanner_count)
    assign("cyclotron_count", project.production.cyclotron_count)
    assign("supported_radionuclides", tuple(project.production.supported_radionuclides))
    assign("radiopharmacy_presence", project.production.radiopharmacy_presence)
    assign("facility_area_m2", project.facility.facility_area_m2)
    assign("project_capex", project.economics.reported_project_capex)
    assign("annual_opex", project.economics.reported_annual_opex)
    assign("operating_hours_per_day", project.clinical.operating_hours_per_day)
    assign("facility_type", project.identity.facility_type)
    assign("country", project.identity.country)

    if project.economics.reported_project_capex is not None and project.economics.reported_cyclotron_capex is None:
        inferred["cyclotron_capex_inferred_missing"] = True

    for conflict in project.conflicts:
        conflicts[f"{conflict.subject}:{conflict.field}"] = tuple(conflict.candidate_values)

    if project.economics.reported_project_capex is not None:
        ranges["project_capex"] = (project.economics.reported_project_capex, project.economics.reported_project_capex)

    return NormalizedComparableProjectProfile(
        project=project,
        known_dimensions=known,
        range_dimensions=ranges,
        inferred_dimensions=inferred,
        conflicting_dimensions=conflicts,
        missing_dimensions=tuple(sorted(set(missing).union(project.missing_fields))),
    )


def build_target_profile_from_native(result: NativeDecisionComparisonResult) -> TargetConventionalProjectProfile:
    request = result.request
    conventional = result.conventional
    assumptions = request.planner_assumptions

    annual_patients = conventional.actual_lifecycle_throughput_per_day * float(assumptions.operating_days_per_year)
    radionuclides = tuple(sorted(request.radionuclide_mix.keys()))

    return TargetConventionalProjectProfile(
        project_name=request.project_name,
        target_patients_per_day=float(request.target_patients_per_day),
        annual_patients=annual_patients,
        scanner_count=int(request.conventional.scanners),
        injection_resources=int(request.conventional.injection_resources),
        uptake_resources=int(request.conventional.uptake_resources),
        cyclotron_count=int(request.conventional.installed_cyclotron_units),
        radionuclides=radionuclides,
        radiopharmacy_units=int(request.conventional.installed_radiopharmacy_units),
        distribution_concurrency=int(request.conventional.distribution_concurrency),
        operating_hours_per_day=float(assumptions.operating_hours_per_day),
        conventional_capex=float(conventional.capex_result.total_capex),
        conventional_annual_opex=float(conventional.annual_opex),
        conventional_annual_revenue=float(conventional.annual_revenue),
        conventional_currency=None,
        conventional_currency_year=None,
        conventional_reliability=None,
        conventional_effective_throughput=float(conventional.actual_lifecycle_throughput_per_day),
        horizon_years=int(assumptions.analysis_years),
    )


def _numeric_dimension(
    *,
    name: str,
    target: float | None,
    candidate: float | None,
    weight: float,
) -> SimilarityDimensionScore:
    if target is None or candidate is None:
        return SimilarityDimensionScore(name, None, 0.0, weight, False, "unavailable")
    score = _safe_ratio(float(candidate), float(target))
    return SimilarityDimensionScore(name, 100.0 * score, weight * score, weight, True, "numeric_distance")


def _categorical_dimension(
    *,
    name: str,
    target: str | None,
    candidate: str | None,
    weight: float,
) -> SimilarityDimensionScore:
    if not target or not candidate:
        return SimilarityDimensionScore(name, None, 0.0, weight, False, "unavailable")
    score = 1.0 if target.strip().lower() == candidate.strip().lower() else 0.0
    return SimilarityDimensionScore(name, 100.0 * score, weight * score, weight, True, "categorical_match")


def _set_dimension(
    *,
    name: str,
    target: Sequence[str],
    candidate: Sequence[str],
    weight: float,
) -> SimilarityDimensionScore:
    a = _as_set(target)
    b = _as_set(candidate)
    if not a or not b:
        return SimilarityDimensionScore(name, None, 0.0, weight, False, "unavailable")
    intersection = a.intersection(b)
    union = a.union(b)
    score = len(intersection) / len(union)
    return SimilarityDimensionScore(name, 100.0 * score, weight * score, weight, True, "set_overlap")


def compute_similarity(
    *,
    target: TargetConventionalProjectProfile,
    normalized_project: NormalizedComparableProjectProfile,
    config: SimilarityEngineConfig,
) -> ComparableSimilarityResult:
    project = normalized_project.project
    k = normalized_project.known_dimensions
    w = config.dimension_weights

    dimension_scores = (
        _numeric_dimension(name="patients_per_day", target=target.target_patients_per_day, candidate=k.get("patients_per_day"), weight=w["patients_per_day"]),
        _numeric_dimension(name="annual_patients", target=target.annual_patients, candidate=k.get("patients_per_year"), weight=w["annual_patients"]),
        _numeric_dimension(name="scanner_count", target=float(target.scanner_count) if target.scanner_count is not None else None, candidate=float(k.get("scanner_count")) if k.get("scanner_count") is not None else None, weight=w["scanner_count"]),
        _numeric_dimension(name="cyclotron_count", target=float(target.cyclotron_count) if target.cyclotron_count is not None else None, candidate=float(k.get("cyclotron_count")) if k.get("cyclotron_count") is not None else None, weight=w["cyclotron_count"]),
        _set_dimension(name="radionuclides", target=target.radionuclides, candidate=k.get("supported_radionuclides") or (), weight=w["radionuclides"]),
        _categorical_dimension(name="facility_type", target="conventional", candidate=k.get("facility_type"), weight=w["facility_type"]),
        _numeric_dimension(name="facility_area_m2", target=None, candidate=k.get("facility_area_m2"), weight=w["facility_area_m2"]),
        _categorical_dimension(name="country", target=target.location_country, candidate=k.get("country"), weight=w["country"]),
    )

    # Cost dimensions require explicit same-currency/year unless caller pre-normalizes.
    project_currency = project.economics.currency
    project_currency_year = project.economics.currency_year
    same_currency_and_year = (
        target.conventional_currency is not None
        and target.conventional_currency_year is not None
        and project_currency is not None
        and project_currency_year is not None
        and target.conventional_currency.strip().upper() == project_currency.strip().upper()
        and int(target.conventional_currency_year) == int(project_currency_year)
    )

    if target.conventional_capex is not None and project.economics.reported_project_capex is not None and same_currency_and_year:
        capex_score = _numeric_dimension(
            name="project_capex",
            target=target.conventional_capex,
            candidate=project.economics.reported_project_capex,
            weight=w["project_capex"],
        )
    else:
        capex_score = SimilarityDimensionScore("project_capex", None, 0.0, w["project_capex"], False, "cross_currency_or_missing")

    if target.conventional_annual_opex is not None and project.economics.reported_annual_opex is not None and same_currency_and_year:
        opex_score = _numeric_dimension(
            name="annual_opex",
            target=target.conventional_annual_opex,
            candidate=project.economics.reported_annual_opex,
            weight=w["annual_opex"],
        )
    else:
        opex_score = SimilarityDimensionScore("annual_opex", None, 0.0, w["annual_opex"], False, "cross_currency_or_missing")

    hours_score = _numeric_dimension(
        name="operating_hours_per_day",
        target=target.operating_hours_per_day,
        candidate=k.get("operating_hours_per_day"),
        weight=w["operating_hours_per_day"],
    )

    all_scores = tuple(dimension_scores + (capex_score, opex_score, hours_score))
    compared = tuple(score for score in all_scores if score.compared)
    compared_weight = sum(score.weight for score in compared)
    weighted_score = sum(score.weighted_contribution for score in compared)

    similarity_pct = 0.0 if compared_weight == 0.0 else 100.0 * (weighted_score / compared_weight)
    evidence_coverage_pct = 100.0 * (len(compared) / len(all_scores))

    tier_bonus = 0.0
    if "TIER_1" in project.source_tiers:
        tier_bonus += 0.15
    if "TIER_2" in project.source_tiers:
        tier_bonus += 0.10

    conflict_penalty = 0.2 if project.conflicts else 0.0
    image_penalty = 0.2 if project.comparable_but_not_visually_complete else 0.0
    base_conf = (evidence_coverage_pct / 100.0) + tier_bonus - conflict_penalty - image_penalty
    comparison_confidence_score = min(1.0, max(0.0, base_conf))

    if comparison_confidence_score >= 0.8:
        label: ComparisonConfidenceLabel = "HIGH"
    elif comparison_confidence_score >= 0.6:
        label = "MODERATE"
    elif comparison_confidence_score >= 0.35:
        label = "LOW"
    else:
        label = "INSUFFICIENT_EVIDENCE"

    strongest = tuple(score.dimension for score in compared if (score.score_pct or 0.0) >= 85.0)
    differences = tuple(score.dimension for score in compared if (score.score_pct or 0.0) < 60.0)
    unavailable = tuple(score.dimension for score in all_scores if not score.compared)
    unresolved_conflicts = tuple(f"{conflict.subject}:{conflict.field}" for conflict in project.conflicts)

    limitations: list[str] = []
    if project.economics.currency is None or project.economics.currency_year is None:
        limitations.append("Cost currency/year incomplete; direct cost comparison excluded where required.")
    if project.comparable_but_not_visually_complete:
        limitations.append("Comparable but not visually complete.")
    if unresolved_conflicts:
        limitations.append("Contains unresolved evidence conflicts.")

    summary = (
        f"{project.identity.facility_name} matched on {len(strongest)} strong dimensions with "
        f"{len(unavailable)} unavailable dimensions."
    )
    why_ranked = (
        f"Ranked by weighted similarity {similarity_pct:.1f}%, coverage {evidence_coverage_pct:.1f}%, "
        f"confidence {comparison_confidence_score:.2f}."
    )

    return ComparableSimilarityResult(
        project_id=project.identity.project_id,
        similarity_pct=similarity_pct,
        evidence_coverage_pct=evidence_coverage_pct,
        comparison_confidence_score=comparison_confidence_score,
        confidence_label=label,
        component_scores=all_scores,
        strongest_matches=strongest,
        meaningful_differences=differences,
        unavailable_dimensions=unavailable,
        unresolved_conflicts=unresolved_conflicts,
        evidence_limitations=tuple(limitations),
        similarity_summary=summary,
        why_ranked_here=why_ranked,
    )


def rank_comparable_projects(
    *,
    target: TargetConventionalProjectProfile,
    projects: Sequence[ComparableProjectEvidenceRecord],
    config: SimilarityEngineConfig | None = None,
    options: ProjectRankingOptions | None = None,
) -> tuple[RankedComparableProject, ...]:
    use_config = config or SimilarityEngineConfig()
    use_options = options or ProjectRankingOptions()

    filtered: list[ComparableProjectEvidenceRecord] = []
    for project in projects:
        identity = project.identity
        if use_options.region_filter is not None and (identity.region or "").lower() != use_options.region_filter.lower():
            continue
        if use_options.country_filter is not None and (identity.country or "").lower() != use_options.country_filter.lower():
            continue
        if use_options.facility_type_filter is not None and (identity.facility_type or "").lower() != use_options.facility_type_filter.lower():
            continue
        if use_options.operational_status_filter is not None and identity.operational_status != use_options.operational_status_filter:
            continue
        if (
            use_options.required_image_status_for_display_ready is not None
            and (
                project.image_reference is None
                or project.image_reference.image_status != use_options.required_image_status_for_display_ready
            )
        ):
            continue
        filtered.append(project)

    scored: list[tuple[ComparableProjectEvidenceRecord, NormalizedComparableProjectProfile, ComparableSimilarityResult]] = []
    for project in filtered:
        normalized = normalize_comparable_project(project)
        similarity = compute_similarity(target=target, normalized_project=normalized, config=use_config)
        if similarity.similarity_pct < use_options.minimum_similarity_pct:
            continue
        if similarity.evidence_coverage_pct < use_options.minimum_evidence_coverage_pct:
            continue
        if similarity.comparison_confidence_score < use_options.minimum_confidence_score:
            continue
        scored.append((project, normalized, similarity))

    scored.sort(
        key=lambda row: (
            -row[2].similarity_pct,
            -row[2].evidence_coverage_pct,
            -row[2].comparison_confidence_score,
            -(1 if "TIER_1" in row[0].source_tiers else 0),
            row[0].identity.project_id,
        )
    )

    ranked: list[RankedComparableProject] = []
    for index, (project, normalized, similarity) in enumerate(scored[: use_options.top_n], start=1):
        ranked.append(
            RankedComparableProject(
                rank=index,
                project=project,
                normalized_profile=normalized,
                similarity=similarity,
            )
        )
    return tuple(ranked)


def build_conventional_vs_mrt_delta(result: NativeDecisionComparisonResult) -> ConventionalVsMrtDelta:
    conventional_payback = result.conventional.lifecycle_result.payback_year
    mrt_payback = result.mrt.lifecycle_result.payback_year

    return ConventionalVsMrtDelta(
        capex_delta_mrt_minus_conventional=float(result.mrt.capex_result.total_capex - result.conventional.capex_result.total_capex),
        annual_opex_delta_mrt_minus_conventional=float(result.mrt.annual_opex - result.conventional.annual_opex),
        annual_revenue_delta_mrt_minus_conventional=float(result.mrt.annual_revenue - result.conventional.annual_revenue),
        effective_throughput_delta_mrt_minus_conventional=float(
            result.mrt.actual_lifecycle_throughput_per_day - result.conventional.actual_lifecycle_throughput_per_day
        ),
        reliability_delta_mrt_minus_conventional=None,
        npv_delta_mrt_minus_conventional=float(
            result.mrt.lifecycle_result.final_npv - result.conventional.lifecycle_result.final_npv
        ),
        payback_year_delta_mrt_minus_conventional=(
            float(mrt_payback - conventional_payback)
            if mrt_payback is not None and conventional_payback is not None
            else None
        ),
        scanner_count_delta_mrt_minus_conventional=int(result.request.mrt.scanners - result.request.conventional.scanners),
        cyclotron_count_delta_mrt_minus_conventional=int(
            result.request.mrt.installed_cyclotron_units - result.request.conventional.installed_cyclotron_units
        ),
    )


def build_comparable_project_report(
    *,
    native_result: NativeDecisionComparisonResult,
    provider: ComparableProjectEvidenceProvider,
    config: SimilarityEngineConfig | None = None,
    options: ProjectRankingOptions | None = None,
) -> ComparableProjectReportData:
    target = build_target_profile_from_native(native_result)
    deduped = deduplicate_projects(provider.list_projects())
    ranked = rank_comparable_projects(target=target, projects=deduped, config=config, options=options)

    source_links = {
        project.project.identity.project_id: tuple(project.project.source_urls)
        for project in ranked
    }
    claim_citations = {
        project.project.identity.project_id: tuple(project.project.claim_ids)
        for project in ranked
    }

    conventional_native_metrics = {
        "capex": float(native_result.conventional.capex_result.total_capex),
        "annual_opex": float(native_result.conventional.annual_opex),
        "annual_revenue": float(native_result.conventional.annual_revenue),
        "effective_throughput": float(native_result.conventional.actual_lifecycle_throughput_per_day),
        "final_npv": float(native_result.conventional.lifecycle_result.final_npv),
        "payback_year": native_result.conventional.lifecycle_result.payback_year,
    }
    mrt_native_metrics = {
        "capex": float(native_result.mrt.capex_result.total_capex),
        "annual_opex": float(native_result.mrt.annual_opex),
        "annual_revenue": float(native_result.mrt.annual_revenue),
        "effective_throughput": float(native_result.mrt.actual_lifecycle_throughput_per_day),
        "final_npv": float(native_result.mrt.lifecycle_result.final_npv),
        "payback_year": native_result.mrt.lifecycle_result.payback_year,
    }

    trace_id = _trace_id(
        {
            "comparison_trace_id": native_result.provenance.comparison_trace_id,
            "target_project": target.project_name,
            "ranked_project_ids": [item.project.identity.project_id for item in ranked],
        }
    )

    limitations = (
        "External live web retrieval is NOT CONNECTED in this build. Comparable-project ranking uses provided local/static evidence providers.",
    )

    return ComparableProjectReportData(
        target_conventional_summary=target,
        top_comparable_projects=ranked,
        project_source_links=source_links,
        claim_citations=claim_citations,
        conventional_native_metrics=conventional_native_metrics,
        mrt_native_metrics=mrt_native_metrics,
        conventional_vs_mrt_deltas=build_conventional_vs_mrt_delta(native_result),
        limitations=limitations,
        provenance_trace_id=trace_id,
    )

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from typing import Any, Iterable, Literal, Mapping, Sequence

from comparable_project_similarity import (
    ComparableProjectClinicalScale,
    ComparableProjectEconomics,
    ComparableProjectEvidenceProvider,
    ComparableProjectEvidenceRecord,
    ComparableProjectFacility,
    ComparableProjectIdentity,
    ComparableProjectPerformance,
    ComparableProjectProduction,
    ComparableSimilarityResult,
    ComparableProjectReportData as ComparableProjectSimilarityReportData,
    ComparisonConfidenceLabel,
    ProjectImageReference,
    ProjectRankingOptions,
    RankedComparableProject,
    SimilarityDimensionScore,
    SimilarityEngineConfig,
    TargetConventionalProjectProfile,
    build_conventional_vs_mrt_delta,
    build_target_profile_from_native,
)
from decision_pipeline import NativeDecisionComparisonResult
from engineering_evidence import (
    EngineeringEvidenceChunk,
    EngineeringEvidenceClaim,
    EngineeringEvidenceConflict,
    EngineeringEvidenceDocument,
    EngineeringEvidenceRepository,
    EngineeringEvidenceSource,
)


ComparisonStatus = Literal[
    "COMPARABLE",
    "PARTIALLY_COMPARABLE",
    "NOT_COMPARABLE",
    "MISSING_TARGET",
    "MISSING_COMPARABLE",
    "CONFLICTED",
]
ComparisonKind = Literal["numeric", "set", "text", "boolean"]
CostComparabilityPolicyId = Literal[
    "same_currency_same_year_same_scope_required",
]
EvidencePolicyId = Literal[
    "native_repository_lineage_plus_project_aggregates",
]
RankingMethodId = Literal["native_similarity_weighted_v1"]
SimilarityScale = Literal["0-100 weighted percentage"]


def _trace_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _non_empty_sequence(values: Sequence[Any] | None) -> tuple[Any, ...]:
    return tuple(value for value in (values or ()) if value is not None)


def _first_non_empty(*values: Any) -> Any | None:
    for value in values:
        if value not in (None, "", (), []):
            return value
    return None


def _safe_percentage_difference(target: float | None, comparable: float | None) -> float | None:
    if target in (None, 0.0) or comparable is None:
        return None
    return ((comparable - target) / target) * 100.0


def _safe_difference(target: float | None, comparable: float | None) -> float | None:
    if target is None or comparable is None:
        return None
    return comparable - target


def _stable_text(values: Iterable[Any]) -> str:
    return "; ".join(str(value) for value in values if value not in (None, "", (), []))


@dataclass(frozen=True)
class ComparableProjectReportMetadata:
    target_project_identifier: str | None
    target_project_name: str | None
    report_trace_id: str
    similarity_run_trace_id: str
    evidence_repository_trace_id: str | None
    generated_candidate_count: int
    ranked_project_count: int
    returned_project_count: int
    top_n: int | None
    ranking_method: RankingMethodId
    similarity_scale: SimilarityScale
    deterministic: bool
    requested_filters: Mapping[str, Any]
    applied_filters: Mapping[str, Any]
    minimum_confidence_threshold: float | None
    cost_comparability_policy: CostComparabilityPolicyId
    evidence_policy: EvidencePolicyId
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class ComparableProjectEvidenceReference:
    source_id: str | None
    source_type: str | None
    source_tier: str | None
    document_id: str | None
    chunk_id: str | None
    claim_id: str | None
    title: str | None
    publisher_or_organization: str | None
    publication_date: date | None
    url_or_reference: str | None
    provenance_trace_id: str | None
    confidence: float | None
    evidence_status: str
    claim_subject: str | None = None
    claim_predicate: str | None = None


@dataclass(frozen=True)
class ComparableProjectImageReference:
    image_available: bool
    image_reference_id: str | None
    image_status: str | None
    image_source_url: str | None
    image_page_url: str | None
    image_source_organization: str | None
    image_caption: str | None
    image_provenance: str | None
    image_retrieval_date: date | None
    image_confidence: float | None
    primary_image: bool


@dataclass(frozen=True)
class ComparableProjectConflictSummary:
    conflict_detected: bool
    conflict_count: int
    resolution_status: str
    candidate_values: tuple[str, ...]
    source_references: tuple[ComparableProjectEvidenceReference, ...]
    warning: str | None


@dataclass(frozen=True)
class ComparableProjectMissingDataSummary:
    missing_fields: tuple[str, ...]
    missing_cost_fields: tuple[str, ...]
    missing_engineering_fields: tuple[str, ...]
    no_usable_image: bool
    missing_count: int
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ComparableProjectEngineeringProfile:
    project_id: str
    facility_name: str | None
    facility_type: str | None
    project_type: str | None
    city: str | None
    state_or_province: str | None
    region: str | None
    country: str | None
    organization: str | None
    project_description: str | None
    project_status: str | None
    commissioning_or_opening_year: int | None
    patients_per_day: float | None
    annual_patients: float | None
    scanner_count: int | None
    scanner_type_or_modality: str | None
    cyclotron_count: int | None
    cyclotron_manufacturer: str | None
    cyclotron_model: str | None
    cyclotron_energy_mev: float | None
    supported_radionuclides: tuple[str, ...]
    radiopharmacy_capability: bool | None
    production_capacity_descriptor: str | None
    operating_hours_per_day: float | None
    transport_minutes: float | None
    guideway_length_m: float | None
    carrier_count: int | None
    facility_area_m2: float | None
    construction_scope: str | None


@dataclass(frozen=True)
class ComparableProjectTargetComparison:
    field_name: str
    comparison_kind: ComparisonKind
    target_value: Any
    comparable_value: Any
    absolute_difference: float | None
    percentage_difference: float | None
    comparison_status: ComparisonStatus
    reason: str | None
    shared_values: tuple[str, ...]
    target_only_values: tuple[str, ...]
    comparable_only_values: tuple[str, ...]


@dataclass(frozen=True)
class ComparableProjectCostEvidence:
    cost_field: str
    amount: float | None
    currency: str | None
    currency_year: int | None
    reported_year: int | None
    cost_scope: str | None
    cost_category: str
    estimated: bool
    source_references: tuple[ComparableProjectEvidenceReference, ...]
    confidence: float | None
    conflict_status: str
    comparability_status: ComparisonStatus
    comparability_reason: str | None


@dataclass(frozen=True)
class ComparableProjectCostComparison:
    cost_field: str
    target: ComparableProjectCostEvidence | None
    comparable: ComparableProjectCostEvidence | None
    absolute_difference: float | None
    percentage_difference: float | None
    comparison_status: ComparisonStatus
    reason: str | None


@dataclass(frozen=True)
class ComparableProjectSimilarityBreakdown:
    total_score: float
    similarity_percentage: float
    confidence_label: ComparisonConfidenceLabel
    comparison_confidence_score: float
    ranking_position: int
    explanation: str
    similarity_summary: str
    why_ranked_here: str
    component_scores: tuple[SimilarityDimensionScore, ...]
    matched_variables: tuple[str, ...]
    partially_matched_variables: tuple[str, ...]
    unavailable_variables: tuple[str, ...]
    excluded_variables: tuple[str, ...]
    evidence_quality_contribution: float | None
    deterministic: bool


@dataclass(frozen=True)
class ComparableProjectChartPoint:
    project_id: str
    rank: int
    project_name: str
    field_name: str
    value: float | None
    comparison_status: ComparisonStatus
    evidence_status: str
    label: str | None = None


@dataclass(frozen=True)
class ComparableProjectChartSeries:
    similarity_ranking: tuple[ComparableProjectChartPoint, ...]
    patients_per_day_comparison: tuple[ComparableProjectChartPoint, ...]
    scanner_count_comparison: tuple[ComparableProjectChartPoint, ...]
    cyclotron_count_comparison: tuple[ComparableProjectChartPoint, ...]
    directly_comparable_project_cost: tuple[ComparableProjectChartPoint, ...]
    annual_opex_comparison: tuple[ComparableProjectChartPoint, ...]


@dataclass(frozen=True)
class ComparableProjectReportRow:
    rank: int
    project_id: str
    facility_name: str | None
    city: str | None
    state_or_province: str | None
    region: str | None
    country: str | None
    facility_type: str | None
    project_type: str | None
    organization: str | None
    project_description: str | None
    project_status: str | None
    commissioning_or_opening_year: int | None
    source_availability: tuple[str, ...]
    similarity: ComparableProjectSimilarityBreakdown
    engineering_profile: ComparableProjectEngineeringProfile
    target_comparisons: tuple[ComparableProjectTargetComparison, ...]
    cost_evidence: tuple[ComparableProjectCostEvidence, ...]
    cost_comparisons: tuple[ComparableProjectCostComparison, ...]
    evidence_references: tuple[ComparableProjectEvidenceReference, ...]
    conflict_summary: ComparableProjectConflictSummary
    missing_data: ComparableProjectMissingDataSummary
    image_reference: ComparableProjectImageReference
    chart_points: tuple[ComparableProjectChartPoint, ...]
    row_trace_id: str


@dataclass(frozen=True)
class ComparableProjectEvidenceReportData:
    metadata: ComparableProjectReportMetadata
    target_profile: ComparableProjectEngineeringProfile
    target_cost_evidence: tuple[ComparableProjectCostEvidence, ...]
    rows: tuple[ComparableProjectReportRow, ...]
    chart_series: ComparableProjectChartSeries
    provenance_trace_id: str
    limitations: tuple[str, ...]


def _repository_trace_id(repository: EngineeringEvidenceRepository | None) -> str | None:
    if repository is None:
        return None
    payload = {
        "sources": sorted(repository.sources.keys()),
        "documents": sorted(repository.documents.keys()),
        "chunks": sorted(repository.chunks.keys()),
        "claims": sorted(repository.claims.keys()),
        "conflicts": sorted(repository.conflicts.keys()),
    }
    return _trace_id(payload)


def _reference_from_claim(
    claim: EngineeringEvidenceClaim,
    *,
    repository: EngineeringEvidenceRepository | None,
) -> ComparableProjectEvidenceReference:
    source = repository.sources.get(claim.source_id) if repository is not None else None
    document = repository.documents.get(claim.document_id) if repository is not None and claim.document_id is not None else None
    chunk = repository.chunks.get(claim.chunk_id) if repository is not None and claim.chunk_id is not None else None
    return ComparableProjectEvidenceReference(
        source_id=claim.source_id,
        source_type=None if source is None else source.source_type,
        source_tier=claim.source_tier,
        document_id=claim.document_id,
        chunk_id=claim.chunk_id,
        claim_id=claim.claim_id,
        title=None if source is None else source.title,
        publisher_or_organization=None if source is None else source.publisher_or_organization,
        publication_date=None if source is None else source.publication_date,
        url_or_reference=(None if source is None else source.url_or_locator) or (None if document is None else document.url_or_locator),
        provenance_trace_id=_trace_id(
            {
                "source_id": claim.source_id,
                "document_id": claim.document_id,
                "chunk_id": claim.chunk_id,
                "claim_id": claim.claim_id,
                "claim_confidence": claim.confidence,
                "claim_status": claim.conflict_status,
            }
        ),
        confidence=claim.confidence,
        evidence_status=claim.verification_status,
        claim_subject=claim.subject,
        claim_predicate=claim.predicate,
    )


def _reference_from_aggregate(
    *,
    project: ComparableProjectEvidenceRecord,
    repository: EngineeringEvidenceRepository | None,
    index: int,
) -> ComparableProjectEvidenceReference:
    source_id = project.source_ids[index] if index < len(project.source_ids) else None
    document_id = project.document_ids[index] if index < len(project.document_ids) else None
    source = repository.sources.get(source_id) if repository is not None and source_id is not None else None
    document = repository.documents.get(document_id) if repository is not None and document_id is not None else None
    claim_id = project.claim_ids[index] if index < len(project.claim_ids) else None
    claim = repository.claims.get(claim_id) if repository is not None and claim_id is not None else None
    return ComparableProjectEvidenceReference(
        source_id=source_id,
        source_type=None if source is None else source.source_type,
        source_tier=project.source_tiers[index] if index < len(project.source_tiers) else None,
        document_id=document_id,
        chunk_id=None if claim is None else claim.chunk_id,
        claim_id=claim_id,
        title=None if source is None else source.title,
        publisher_or_organization=None if source is None else source.publisher_or_organization,
        publication_date=None if source is None else source.publication_date,
        url_or_reference=(None if source is None else source.url_or_locator) or (None if document is None else document.url_or_locator) or project.source_urls[index] if index < len(project.source_urls) else None,
        provenance_trace_id=_trace_id(
            {
                "project_id": project.identity.project_id,
                "source_id": source_id,
                "document_id": document_id,
                "claim_id": claim_id,
            }
        ),
        confidence=project.confidence if project.confidence is not None else None,
        evidence_status=("conflicted" if project.conflicts else "verified" if source is not None else "unknown"),
        claim_subject=None if claim is None else claim.subject,
        claim_predicate=None if claim is None else claim.predicate,
    )


def _project_evidence_references(
    project: ComparableProjectEvidenceRecord,
    *,
    repository: EngineeringEvidenceRepository | None,
) -> tuple[ComparableProjectEvidenceReference, ...]:
    references: list[ComparableProjectEvidenceReference] = []
    for index in range(max(len(project.source_ids), len(project.document_ids), len(project.claim_ids), len(project.source_urls), 1)):
        if repository is not None and index < len(project.claim_ids):
            claim = repository.claims.get(project.claim_ids[index])
            if claim is not None:
                references.append(_reference_from_claim(claim, repository=repository))
                continue
        references.append(_reference_from_aggregate(project=project, repository=repository, index=index))
    return tuple(references)


def _target_profile_from_native(native_result: NativeDecisionComparisonResult) -> ComparableProjectEngineeringProfile:
    target = build_target_profile_from_native(native_result)
    return ComparableProjectEngineeringProfile(
        project_id=native_result.request.project_name,
        facility_name=native_result.request.project_name,
        facility_type="conventional",
        project_type="conventional",
        city=None,
        state_or_province=None,
        region=target.location_region,
        country=target.location_country,
        organization=None,
        project_description=None,
        project_status="modeled",
        commissioning_or_opening_year=None,
        patients_per_day=target.target_patients_per_day,
        annual_patients=target.annual_patients,
        scanner_count=target.scanner_count,
        scanner_type_or_modality=None,
        cyclotron_count=target.cyclotron_count,
        cyclotron_manufacturer=None,
        cyclotron_model=None,
        cyclotron_energy_mev=None,
        supported_radionuclides=target.radionuclides,
        radiopharmacy_capability=target.radiopharmacy_units is not None and target.radiopharmacy_units > 0,
        production_capacity_descriptor=None,
        operating_hours_per_day=target.operating_hours_per_day,
        transport_minutes=None,
        guideway_length_m=None,
        carrier_count=None,
        facility_area_m2=None,
        construction_scope="modeled target",
    )


def _source_availability(project: ComparableProjectEvidenceRecord) -> tuple[str, ...]:
    status = ["evidence_available" if project.source_ids or project.claim_ids else "evidence_partial_or_missing"]
    if project.image_reference is None or project.image_reference.image_status == "IMAGE_NOT_FOUND":
        status.append("image_missing")
    elif project.image_reference.image_status == "IMAGE_IDENTITY_UNCERTAIN":
        status.append("image_uncertain")
    else:
        status.append("image_available")
    return tuple(status)


def _engineering_profile(project: ComparableProjectEvidenceRecord) -> ComparableProjectEngineeringProfile:
    return ComparableProjectEngineeringProfile(
        project_id=project.identity.project_id,
        facility_name=project.identity.facility_name,
        facility_type=project.identity.facility_type,
        project_type=project.identity.facility_type,
        city=project.identity.city,
        state_or_province=project.identity.state_or_province,
        region=project.identity.region,
        country=project.identity.country,
        organization=project.identity.owner_organization,
        project_description=project.identity.description,
        project_status=project.identity.operational_status,
        commissioning_or_opening_year=project.identity.opening_year,
        patients_per_day=project.clinical.patients_per_day,
        annual_patients=project.clinical.patients_per_year,
        scanner_count=project.clinical.scanner_count,
        scanner_type_or_modality=None,
        cyclotron_count=project.production.cyclotron_count,
        cyclotron_manufacturer=project.production.cyclotron_manufacturer,
        cyclotron_model=project.production.cyclotron_model,
        cyclotron_energy_mev=project.production.beam_energy_mev,
        supported_radionuclides=project.production.supported_radionuclides,
        radiopharmacy_capability=project.production.radiopharmacy_presence,
        production_capacity_descriptor=project.performance.production_capacity_descriptor,
        operating_hours_per_day=project.clinical.operating_hours_per_day,
        transport_minutes=None,
        guideway_length_m=None,
        carrier_count=None,
        facility_area_m2=project.facility.facility_area_m2,
        construction_scope=project.facility.shielding_descriptor,
    )


def _comparison_status(
    target: Any,
    comparable: Any,
    *,
    same_scope: bool,
    same_currency: bool = True,
    same_year: bool = True,
    is_conflicted: bool = False,
) -> ComparisonStatus:
    if is_conflicted:
        return "CONFLICTED"
    if target is None and comparable is None:
        return "MISSING_TARGET"
    if target is None:
        return "MISSING_TARGET"
    if comparable is None:
        return "MISSING_COMPARABLE"
    if not same_scope or not same_currency or not same_year:
        return "NOT_COMPARABLE"
    return "COMPARABLE"


def _target_comparison_for_numeric(
    *,
    field_name: str,
    target: float | None,
    comparable: float | None,
    comparable_status: ComparisonStatus,
    reason: str | None = None,
) -> ComparableProjectTargetComparison:
    if comparable_status != "COMPARABLE":
        return ComparableProjectTargetComparison(
            field_name=field_name,
            comparison_kind="numeric",
            target_value=target,
            comparable_value=comparable,
            absolute_difference=None,
            percentage_difference=None,
            comparison_status=comparable_status,
            reason=reason,
            shared_values=(),
            target_only_values=(),
            comparable_only_values=(),
        )
    return ComparableProjectTargetComparison(
        field_name=field_name,
        comparison_kind="numeric",
        target_value=target,
        comparable_value=comparable,
        absolute_difference=_safe_difference(target, comparable),
        percentage_difference=_safe_percentage_difference(target, comparable),
        comparison_status=comparable_status,
        reason=reason,
        shared_values=(),
        target_only_values=(),
        comparable_only_values=(),
    )


def _target_comparison_for_set(
    *,
    field_name: str,
    target: Sequence[str] | None,
    comparable: Sequence[str] | None,
    comparable_status: ComparisonStatus,
    reason: str | None = None,
) -> ComparableProjectTargetComparison:
    target_values = tuple(value for value in (target or ()) if value)
    comparable_values = tuple(value for value in (comparable or ()) if value)
    shared = tuple(sorted(set(target_values).intersection(comparable_values)))
    target_only = tuple(sorted(set(target_values).difference(comparable_values)))
    comparable_only = tuple(sorted(set(comparable_values).difference(target_values)))
    overlap_pct = None
    if target_values and comparable_values and comparable_status == "COMPARABLE":
        union = len(set(target_values).union(comparable_values))
        overlap_pct = 100.0 * len(shared) / union if union else None
    return ComparableProjectTargetComparison(
        field_name=field_name,
        comparison_kind="set",
        target_value=target_values,
        comparable_value=comparable_values,
        absolute_difference=None,
        percentage_difference=overlap_pct,
        comparison_status=comparable_status,
        reason=reason,
        shared_values=shared,
        target_only_values=target_only,
        comparable_only_values=comparable_only,
    )


def _cost_field_label(field_name: str) -> str:
    labels = {
        "reported_project_capex": "total_project_cost",
        "reported_cyclotron_capex": "cyclotron_capex",
        "reported_radiopharmacy_capex": "radiopharmacy_project_cost",
        "reported_construction_cost": "construction_contract_value",
        "reported_annual_opex": "annual_opex",
    }
    return labels.get(field_name, field_name)


def _build_cost_evidence(
    *,
    project: ComparableProjectEvidenceRecord,
    evidence_references: tuple[ComparableProjectEvidenceReference, ...],
) -> tuple[ComparableProjectCostEvidence, ...]:
    cost_items: list[tuple[str, ComparableProjectEconomics, str, str]] = [
        ("reported_project_capex", project.economics, "total_project_cost", "project_capex"),
        ("reported_cyclotron_capex", project.economics, "cyclotron_capex", "cyclotron_capex"),
        ("reported_radiopharmacy_capex", project.economics, "radiopharmacy_project_cost", "radiopharmacy_capex"),
        ("reported_construction_cost", project.economics, "construction_contract_value", "construction_cost"),
        ("reported_annual_opex", project.economics, "annual_opex", "annual_opex"),
    ]
    result: list[ComparableProjectCostEvidence] = []
    for field_name, economics, cost_scope, cost_category in cost_items:
        amount = getattr(economics, field_name)
        comparability = "MISSING_COMPARABLE" if amount is None else "NOT_COMPARABLE"
        result.append(
            ComparableProjectCostEvidence(
                cost_field=field_name,
                amount=amount,
                currency=economics.currency,
                currency_year=economics.currency_year,
                reported_year=economics.currency_year,
                cost_scope=cost_scope,
                cost_category=cost_category,
                estimated=economics.value_basis in {"estimate", "quote", "inferred"},
                source_references=evidence_references,
                confidence=None,
                conflict_status="conflicted" if project.conflicts else "none",
                comparability_status=comparability,
                comparability_reason="target context required for direct comparison",
            )
        )
    return tuple(result)


def _build_cost_comparisons(
    *,
    target_cost_evidence: Mapping[str, ComparableProjectCostEvidence],
    comparable_cost_evidence: tuple[ComparableProjectCostEvidence, ...],
) -> tuple[ComparableProjectCostComparison, ...]:
    comparisons: list[ComparableProjectCostComparison] = []
    for comparable_item in comparable_cost_evidence:
        target_item = target_cost_evidence.get(comparable_item.cost_field)
        if target_item is None:
            comparisons.append(
                ComparableProjectCostComparison(
                    cost_field=comparable_item.cost_field,
                    target=None,
                    comparable=comparable_item,
                    absolute_difference=None,
                    percentage_difference=None,
                    comparison_status="MISSING_TARGET",
                    reason="target cost context missing",
                )
            )
            continue

        if target_item.amount is None:
            comparisons.append(
                ComparableProjectCostComparison(
                    cost_field=comparable_item.cost_field,
                    target=target_item,
                    comparable=comparable_item,
                    absolute_difference=None,
                    percentage_difference=None,
                    comparison_status="MISSING_TARGET",
                    reason="target monetary amount missing",
                )
            )
            continue

        if comparable_item.amount is None:
            comparisons.append(
                ComparableProjectCostComparison(
                    cost_field=comparable_item.cost_field,
                    target=target_item,
                    comparable=comparable_item,
                    absolute_difference=None,
                    percentage_difference=None,
                    comparison_status="MISSING_COMPARABLE",
                    reason="comparable monetary amount missing",
                )
            )
            continue

        same_currency = (target_item.currency or "").upper() == (comparable_item.currency or "").upper() and target_item.currency is not None and comparable_item.currency is not None
        same_year = target_item.currency_year is not None and comparable_item.currency_year is not None and int(target_item.currency_year) == int(comparable_item.currency_year)
        same_scope = (target_item.cost_scope or "").strip().lower() == (comparable_item.cost_scope or "").strip().lower()
        same_category = (target_item.cost_category or "").strip().lower() == (comparable_item.cost_category or "").strip().lower()
        if target_item.conflict_status == "conflicted" or comparable_item.conflict_status == "conflicted":
            status: ComparisonStatus = "CONFLICTED"
        elif not same_currency or not same_year or not same_scope or not same_category:
            status = "NOT_COMPARABLE"
        else:
            status = "COMPARABLE"
        comparisons.append(
            ComparableProjectCostComparison(
                cost_field=comparable_item.cost_field,
                target=target_item,
                comparable=comparable_item,
                absolute_difference=(
                    _safe_difference(target_item.amount, comparable_item.amount) if status == "COMPARABLE" else None
                ),
                percentage_difference=(
                    _safe_percentage_difference(target_item.amount, comparable_item.amount) if status == "COMPARABLE" else None
                ),
                comparison_status=status,
                reason=(
                    None
                    if status == "COMPARABLE"
                    else "currency/year/scope/category mismatch or conflict"
                ),
            )
        )
    return tuple(comparisons)


def _similarity_breakdown(row: RankedComparableProject) -> ComparableProjectSimilarityBreakdown:
    similarity = row.similarity
    return ComparableProjectSimilarityBreakdown(
        total_score=similarity.similarity_pct,
        similarity_percentage=similarity.similarity_pct,
        confidence_label=similarity.confidence_label,
        comparison_confidence_score=similarity.comparison_confidence_score,
        ranking_position=row.rank,
        explanation=similarity.similarity_summary + " " + similarity.why_ranked_here,
        similarity_summary=similarity.similarity_summary,
        why_ranked_here=similarity.why_ranked_here,
        component_scores=similarity.component_scores,
        matched_variables=similarity.strongest_matches,
        partially_matched_variables=similarity.meaningful_differences,
        unavailable_variables=similarity.unavailable_dimensions,
        excluded_variables=similarity.unresolved_conflicts,
        evidence_quality_contribution=similarity.evidence_coverage_pct,
        deterministic=True,
    )


def _row_trace_id(
    *,
    target_name: str | None,
    row: RankedComparableProject,
    evidence_references: tuple[ComparableProjectEvidenceReference, ...],
    cost_comparisons: tuple[ComparableProjectCostComparison, ...],
) -> str:
    payload = {
        "target_name": target_name,
        "project_id": row.project.identity.project_id,
        "rank": row.rank,
        "similarity": row.similarity.similarity_pct,
        "evidence": [reference.provenance_trace_id for reference in evidence_references],
        "cost_status": [comparison.comparison_status for comparison in cost_comparisons],
    }
    return _trace_id(payload)


def _requested_filters(options: ProjectRankingOptions | None) -> Mapping[str, Any]:
    if options is None:
        return {}
    return {
        key: value
        for key, value in {
            "top_n": options.top_n,
            "minimum_similarity_pct": options.minimum_similarity_pct,
            "minimum_evidence_coverage_pct": options.minimum_evidence_coverage_pct,
            "minimum_confidence_score": options.minimum_confidence_score,
            "region_filter": options.region_filter,
            "country_filter": options.country_filter,
            "facility_type_filter": options.facility_type_filter,
            "operational_status_filter": options.operational_status_filter,
            "required_image_status_for_display_ready": options.required_image_status_for_display_ready,
        }.items()
        if value not in (None, 0, 0.0, "")
    }


def _applied_filters(options: ProjectRankingOptions | None) -> Mapping[str, Any]:
    return _requested_filters(options)


def _limitations(repository: EngineeringEvidenceRepository | None) -> tuple[str, ...]:
    limitations = [
        "Reporting contract is observational and does not rerun similarity.",
        "No inflation, FX, or base-year normalization is invented in this build.",
        "No image retrieval is performed.",
    ]
    if repository is None:
        limitations.append("Evidence repository was not supplied; provenance references remain aggregate-only.")
    return tuple(limitations)


def build_native_comparable_project_report_data(
    *,
    native_result: NativeDecisionComparisonResult,
    ranked_projects: Sequence[RankedComparableProject],
    provider: ComparableProjectEvidenceProvider,
    repository: EngineeringEvidenceRepository | None = None,
    target_cost_evidence: Mapping[str, ComparableProjectCostEvidence] | None = None,
    top_n: int | None = None,
    config: SimilarityEngineConfig | None = None,
    options: ProjectRankingOptions | None = None,
) -> ComparableProjectEvidenceReportData:
    target_profile = _target_profile_from_native(native_result)
    candidate_count = len(tuple(provider.list_projects()))
    selected_rows = tuple(ranked_projects if top_n is None else ranked_projects[:top_n])
    similarity_run_trace_id = _trace_id(
        {
            "target_project": native_result.request.project_name,
            "ranked": [(row.rank, row.project.identity.project_id, row.similarity.similarity_pct) for row in selected_rows],
            "top_n": top_n,
            "ranking_method": "native_similarity_weighted_v1",
        }
    )
    repository_trace_id = _repository_trace_id(repository)

    rows: list[ComparableProjectReportRow] = []
    similarity_points: list[ComparableProjectChartPoint] = []
    throughput_points: list[ComparableProjectChartPoint] = []
    scanner_points: list[ComparableProjectChartPoint] = []
    cyclotron_points: list[ComparableProjectChartPoint] = []
    direct_cost_points: list[ComparableProjectChartPoint] = []
    opex_points: list[ComparableProjectChartPoint] = []
    target_cost_map = dict(target_cost_evidence or {})
    if target_cost_map:
        # Make sure the target side carries a deterministic source chain as well.
        target_cost_map = dict(sorted(target_cost_map.items(), key=lambda item: item[0]))

    target_cost_evidences: list[ComparableProjectCostEvidence] = tuple(target_cost_map.values()) if target_cost_map else []
    if isinstance(target_cost_evidences, tuple):
        target_cost_evidence_tuple = target_cost_evidences
    else:
        target_cost_evidence_tuple = tuple(target_cost_evidences)

    target_cost_lookup = dict(target_cost_map)

    for row in selected_rows:
        project = row.project
        evidence_refs = _project_evidence_references(project, repository=repository)
        cost_evidence = _build_cost_evidence(project=project, evidence_references=evidence_refs)
        cost_comparisons = _build_cost_comparisons(target_cost_evidence=target_cost_lookup, comparable_cost_evidence=cost_evidence)
        target_comparisons = (
            _target_comparison_for_numeric(
                field_name="patients_per_day",
                target=target_profile.patients_per_day,
                comparable=project.clinical.patients_per_day,
                comparable_status=("COMPARABLE" if target_profile.patients_per_day is not None and project.clinical.patients_per_day is not None else "MISSING_TARGET" if target_profile.patients_per_day is None else "MISSING_COMPARABLE"),
            ),
            _target_comparison_for_numeric(
                field_name="scanner_count",
                target=float(target_profile.scanner_count) if target_profile.scanner_count is not None else None,
                comparable=float(project.clinical.scanner_count) if project.clinical.scanner_count is not None else None,
                comparable_status=("COMPARABLE" if target_profile.scanner_count is not None and project.clinical.scanner_count is not None else "MISSING_TARGET" if target_profile.scanner_count is None else "MISSING_COMPARABLE"),
            ),
            _target_comparison_for_numeric(
                field_name="cyclotron_count",
                target=float(target_profile.cyclotron_count) if target_profile.cyclotron_count is not None else None,
                comparable=float(project.production.cyclotron_count) if project.production.cyclotron_count is not None else None,
                comparable_status=("COMPARABLE" if target_profile.cyclotron_count is not None and project.production.cyclotron_count is not None else "MISSING_TARGET" if target_profile.cyclotron_count is None else "MISSING_COMPARABLE"),
            ),
            _target_comparison_for_set(
                field_name="radionuclides",
                target=target_profile.supported_radionuclides,
                comparable=project.production.supported_radionuclides,
                comparable_status=("COMPARABLE" if target_profile.supported_radionuclides and project.production.supported_radionuclides else "MISSING_TARGET" if not target_profile.supported_radionuclides else "MISSING_COMPARABLE"),
            ),
            _target_comparison_for_numeric(
                field_name="annual_opex",
                target=target_cost_lookup.get("reported_annual_opex").amount if target_cost_lookup.get("reported_annual_opex") is not None else None,
                comparable=project.economics.reported_annual_opex,
                comparable_status=("COMPARABLE" if target_cost_lookup.get("reported_annual_opex") is not None and project.economics.reported_annual_opex is not None and _build_cost_comparisons(target_cost_evidence=target_cost_lookup, comparable_cost_evidence=cost_evidence)[-1].comparison_status == "COMPARABLE" else "MISSING_TARGET" if target_cost_lookup.get("reported_annual_opex") is None else "MISSING_COMPARABLE"),
                reason=(None if target_cost_lookup.get("reported_annual_opex") is not None and project.economics.reported_annual_opex is not None else "target cost context missing or comparable cost unavailable"),
            ),
        )
        missing_fields = tuple(sorted(set(project.missing_fields).union(score.dimension for score in row.similarity.component_scores if not score.compared)))
        missing_cost_fields = tuple(sorted(field.cost_field for field in cost_evidence if field.comparability_status == "MISSING_COMPARABLE" or field.amount is None))
        missing_engineering_fields = tuple(sorted(field for field in ("patients_per_day", "scanner_count", "cyclotron_count", "radionuclides") if field in {comparison.field_name for comparison in target_comparisons if comparison.comparison_status != "COMPARABLE"}))
        conflict_values: list[str] = []
        conflict_refs: list[ComparableProjectEvidenceReference] = []
        for conflict in project.conflicts:
            conflict_values.extend(str(value) for value in conflict.candidate_values)
            if repository is not None:
                for claim_id in conflict.source_claim_ids:
                    claim = repository.claims.get(claim_id)
                    if claim is not None:
                        conflict_refs.append(_reference_from_claim(claim, repository=repository))
        conflict_summary = ComparableProjectConflictSummary(
            conflict_detected=bool(project.conflicts),
            conflict_count=len(project.conflicts),
            resolution_status=project.conflicts[0].resolution_status if project.conflicts else "resolved_by_policy",
            candidate_values=tuple(dict.fromkeys(conflict_values)),
            source_references=tuple(dict.fromkeys(conflict_refs)),
            warning="unresolved evidence conflict" if project.conflicts else None,
        )
        image = project.image_reference
        image_reference = ComparableProjectImageReference(
            image_available=image is not None and image.image_status not in {"IMAGE_NOT_FOUND", "IMAGE_IDENTITY_UNCERTAIN"},
            image_reference_id=None if image is None else image.image_reference_id,
            image_status=None if image is None else image.image_status,
            image_source_url=None if image is None else image.image_source_url,
            image_page_url=None if image is None else image.image_page_url,
            image_source_organization=None if image is None else image.image_source_organization,
            image_caption=None if image is None else image.image_caption,
            image_provenance=None if image is None else image.image_provenance,
            image_retrieval_date=None if image is None else image.image_retrieval_date,
            image_confidence=None if image is None else image.image_confidence,
            primary_image=bool(image is not None and image.image_status == "VERIFIED_PROJECT_IMAGE"),
        )
        engineering_profile = _engineering_profile(project)
        similarity_breakdown = _similarity_breakdown(row)
        row_points = (
            ComparableProjectChartPoint(project_id=project.identity.project_id, rank=row.rank, project_name=project.identity.facility_name, field_name="similarity", value=row.similarity.similarity_pct, comparison_status="COMPARABLE", evidence_status=similarity_breakdown.confidence_label, label=project.identity.facility_name),
            ComparableProjectChartPoint(project_id=project.identity.project_id, rank=row.rank, project_name=project.identity.facility_name, field_name="patients_per_day", value=project.clinical.patients_per_day, comparison_status=next(item.comparison_status for item in target_comparisons if item.field_name == "patients_per_day"), evidence_status=project.confidence and "available" or "unknown", label=project.identity.facility_name),
            ComparableProjectChartPoint(project_id=project.identity.project_id, rank=row.rank, project_name=project.identity.facility_name, field_name="scanner_count", value=float(project.clinical.scanner_count) if project.clinical.scanner_count is not None else None, comparison_status=next(item.comparison_status for item in target_comparisons if item.field_name == "scanner_count"), evidence_status=project.confidence and "available" or "unknown", label=project.identity.facility_name),
            ComparableProjectChartPoint(project_id=project.identity.project_id, rank=row.rank, project_name=project.identity.facility_name, field_name="cyclotron_count", value=float(project.production.cyclotron_count) if project.production.cyclotron_count is not None else None, comparison_status=next(item.comparison_status for item in target_comparisons if item.field_name == "cyclotron_count"), evidence_status=project.confidence and "available" or "unknown", label=project.identity.facility_name),
        )
        rows.append(
            ComparableProjectReportRow(
                rank=row.rank,
                project_id=project.identity.project_id,
                facility_name=project.identity.facility_name,
                city=project.identity.city,
                state_or_province=project.identity.state_or_province,
                region=project.identity.region,
                country=project.identity.country,
                facility_type=project.identity.facility_type,
                project_type=project.identity.facility_type,
                organization=project.identity.owner_organization,
                project_description=project.identity.description,
                project_status=project.identity.operational_status,
                commissioning_or_opening_year=project.identity.opening_year,
                source_availability=_source_availability(project),
                similarity=similarity_breakdown,
                engineering_profile=engineering_profile,
                target_comparisons=target_comparisons,
                cost_evidence=cost_evidence,
                cost_comparisons=cost_comparisons,
                evidence_references=evidence_refs,
                conflict_summary=conflict_summary,
                missing_data=ComparableProjectMissingDataSummary(
                    missing_fields=missing_fields,
                    missing_cost_fields=missing_cost_fields,
                    missing_engineering_fields=missing_engineering_fields,
                    no_usable_image=not image_reference.image_available,
                    missing_count=len(missing_fields),
                    notes=tuple(filter(None, ["project amount not reported" if not cost_evidence else None, "no usable image" if not image_reference.image_available else None])),
                ),
                image_reference=image_reference,
                chart_points=row_points,
                row_trace_id=_row_trace_id(
                    target_name=native_result.request.project_name,
                    row=row,
                    evidence_references=evidence_refs,
                    cost_comparisons=cost_comparisons,
                ),
            )
        )
        similarity_points.append(
            ComparableProjectChartPoint(
                project_id=project.identity.project_id,
                rank=row.rank,
                project_name=project.identity.facility_name,
                field_name="similarity",
                value=row.similarity.similarity_pct,
                comparison_status="COMPARABLE",
                evidence_status=similarity_breakdown.confidence_label,
                label=project.identity.facility_name,
            )
        )
        throughput_points.append(
            ComparableProjectChartPoint(
                project_id=project.identity.project_id,
                rank=row.rank,
                project_name=project.identity.facility_name,
                field_name="patients_per_day",
                value=project.clinical.patients_per_day,
                comparison_status=next(item.comparison_status for item in target_comparisons if item.field_name == "patients_per_day"),
                evidence_status="available" if project.clinical.patients_per_day is not None else "missing",
                label=project.identity.facility_name,
            )
        )
        scanner_points.append(
            ComparableProjectChartPoint(
                project_id=project.identity.project_id,
                rank=row.rank,
                project_name=project.identity.facility_name,
                field_name="scanner_count",
                value=float(project.clinical.scanner_count) if project.clinical.scanner_count is not None else None,
                comparison_status=next(item.comparison_status for item in target_comparisons if item.field_name == "scanner_count"),
                evidence_status="available" if project.clinical.scanner_count is not None else "missing",
                label=project.identity.facility_name,
            )
        )
        cyclotron_points.append(
            ComparableProjectChartPoint(
                project_id=project.identity.project_id,
                rank=row.rank,
                project_name=project.identity.facility_name,
                field_name="cyclotron_count",
                value=float(project.production.cyclotron_count) if project.production.cyclotron_count is not None else None,
                comparison_status=next(item.comparison_status for item in target_comparisons if item.field_name == "cyclotron_count"),
                evidence_status="available" if project.production.cyclotron_count is not None else "missing",
                label=project.identity.facility_name,
            )
        )
        direct_cost_target = target_cost_lookup.get("reported_project_capex")
        if direct_cost_target is not None and any(item.cost_field == "reported_project_capex" and item.comparison_status == "COMPARABLE" for item in cost_comparisons):
            direct_cost_points.append(
                ComparableProjectChartPoint(
                    project_id=project.identity.project_id,
                    rank=row.rank,
                    project_name=project.identity.facility_name,
                    field_name="reported_project_capex",
                    value=project.economics.reported_project_capex,
                    comparison_status="COMPARABLE",
                    evidence_status="available" if project.economics.reported_project_capex is not None else "missing",
                    label=project.identity.facility_name,
                )
            )
        annual_opex_target = target_cost_lookup.get("reported_annual_opex")
        opex_status = next((item.comparison_status for item in cost_comparisons if item.cost_field == "reported_annual_opex"), "MISSING_TARGET")
        if annual_opex_target is not None and opex_status == "COMPARABLE":
            opex_points.append(
                ComparableProjectChartPoint(
                    project_id=project.identity.project_id,
                    rank=row.rank,
                    project_name=project.identity.facility_name,
                    field_name="reported_annual_opex",
                    value=project.economics.reported_annual_opex,
                    comparison_status="COMPARABLE",
                    evidence_status="available" if project.economics.reported_annual_opex is not None else "missing",
                    label=project.identity.facility_name,
                )
            )

    chart_series = ComparableProjectChartSeries(
        similarity_ranking=tuple(sorted(similarity_points, key=lambda point: point.rank)),
        patients_per_day_comparison=tuple(sorted(throughput_points, key=lambda point: point.rank)),
        scanner_count_comparison=tuple(sorted(scanner_points, key=lambda point: point.rank)),
        cyclotron_count_comparison=tuple(sorted(cyclotron_points, key=lambda point: point.rank)),
        directly_comparable_project_cost=tuple(sorted(direct_cost_points, key=lambda point: point.rank)),
        annual_opex_comparison=tuple(sorted(opex_points, key=lambda point: point.rank)),
    )

    rows_sorted = tuple(rows)
    report_trace_id = _trace_id(
        {
            "similarity_run_trace_id": similarity_run_trace_id,
            "rows": [row.row_trace_id for row in rows_sorted],
            "target": native_result.request.project_name,
            "top_n": top_n,
            "repository_trace_id": repository_trace_id,
        }
    )
    metadata = ComparableProjectReportMetadata(
        target_project_identifier=native_result.request.project_name,
        target_project_name=native_result.request.project_name,
        report_trace_id=report_trace_id,
        similarity_run_trace_id=similarity_run_trace_id,
        evidence_repository_trace_id=repository_trace_id,
        generated_candidate_count=candidate_count,
        ranked_project_count=len(tuple(ranked_projects)),
        returned_project_count=len(rows_sorted),
        top_n=top_n,
        ranking_method="native_similarity_weighted_v1",
        similarity_scale="0-100 weighted percentage",
        deterministic=True,
        requested_filters=_requested_filters(options),
        applied_filters=_applied_filters(options),
        minimum_confidence_threshold=None if options is None else options.minimum_confidence_score,
        cost_comparability_policy="same_currency_same_year_same_scope_required",
        evidence_policy="native_repository_lineage_plus_project_aggregates",
        limitations=_limitations(repository),
    )

    provenance_trace_id = _trace_id(
        {
            "report_trace_id": report_trace_id,
            "similarity_run_trace_id": similarity_run_trace_id,
            "repository_trace_id": repository_trace_id,
            "row_trace_ids": [row.row_trace_id for row in rows_sorted],
        }
    )

    return ComparableProjectEvidenceReportData(
        metadata=metadata,
        target_profile=target_profile,
        target_cost_evidence=target_cost_evidence_tuple,
        rows=rows_sorted,
        chart_series=chart_series,
        provenance_trace_id=provenance_trace_id,
        limitations=metadata.limitations,
    )

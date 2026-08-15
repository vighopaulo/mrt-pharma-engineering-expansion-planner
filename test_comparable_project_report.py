from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from comparable_project_report import (
    ComparableProjectCostEvidence,
    ComparableProjectEvidenceReportData,
    ComparableProjectReportMetadata,
    build_native_comparable_project_report_data,
)
from comparable_project_similarity import (
    ComparableProjectClinicalScale,
    ComparableProjectEconomics,
    ComparableProjectEvidenceRecord,
    ComparableProjectFacility,
    ComparableProjectIdentity,
    ComparableProjectPerformance,
    ComparableProjectProduction,
    ProjectRankingOptions,
    RankedComparableProject,
    SimilarityEngineConfig,
    build_target_profile_from_native,
    rank_comparable_projects,
)
from decision_pipeline import run_native_decision_pipeline
from engineering_evidence import EngineeringEvidenceConflict, EngineeringEvidenceRepository
from test_comparable_project_similarity import _native_result, _synthetic_projects
from test_decision_pipeline import _request as baseline_request


def _seed_repository_for_projects(projects: tuple[ComparableProjectEvidenceRecord, ...]) -> EngineeringEvidenceRepository:
    repository = EngineeringEvidenceRepository()
    for project in projects:
        for index, source_id in enumerate(project.source_ids):
            source = repository.register_source(
                source_id=source_id,
                source_type="project_document",
                title=f"{project.identity.facility_name} source {index + 1}",
                publisher_or_organization=project.identity.owner_organization,
                publication_date=date(2026, 1, 1),
                source_tier=project.source_tiers[index] if index < len(project.source_tiers) else "UNKNOWN",
                source_quality="high",
                source_status="active",
                url_or_locator=project.source_urls[index] if index < len(project.source_urls) else None,
            )
            document = repository.register_document(
                source_id=source.source_id,
                document_id=project.document_ids[index] if index < len(project.document_ids) else None,
                title=f"{project.identity.facility_name} document {index + 1}",
                format="txt",
                content=f"{project.identity.facility_name} evidence line {index + 1}",
                url_or_locator=project.source_urls[index] if index < len(project.source_urls) else None,
            )
            chunk = repository.register_chunk(
                document_id=document.document_id,
                chunk_id=project.claim_ids[index] if index < len(project.claim_ids) else None,
                content=f"{project.identity.facility_name} claim text {index + 1}",
                metadata={"project_id": project.identity.project_id, "domain": "project"},
            )
            repository.register_claim(
                source_id=source.source_id,
                document_id=document.document_id,
                chunk_id=chunk.chunk_id,
                claim_id=project.claim_ids[index] if index < len(project.claim_ids) else None,
                claim_type="qualitative",
                subject=project.identity.facility_name,
                predicate=f"attribute_{index + 1}",
                raw_value=str(index + 1),
                normalized_value=index + 1,
                unit=None,
                confidence=project.confidence,
                source_tier=source.source_tier,
                verification_status="verified",
                parameter_type="project",
            )
    return repository


def _cost_evidence(
    *,
    amount: float | None,
    currency: str | None,
    currency_year: int | None,
    cost_scope: str,
    cost_category: str,
    status: str,
    source_id: str,
    claim_id: str,
    document_id: str,
) -> ComparableProjectCostEvidence:
    return ComparableProjectCostEvidence(
        cost_field=cost_category,
        amount=amount,
        currency=currency,
        currency_year=currency_year,
        reported_year=currency_year,
        cost_scope=cost_scope,
        cost_category=cost_category,
        estimated=False,
        source_references=(),
        confidence=0.9 if amount is not None else None,
        conflict_status=status,
        comparability_status="COMPARABLE" if amount is not None and currency is not None and currency_year is not None else "MISSING_COMPARABLE",
        comparability_reason=None,
    )


def _target_cost_map() -> dict[str, ComparableProjectCostEvidence]:
    return {
        "reported_project_capex": _cost_evidence(
            amount=68_000_000.0,
            currency="USD",
            currency_year=2026,
            cost_scope="total_project_cost",
            cost_category="project_capex",
            status="none",
            source_id="target-src",
            claim_id="target-clm",
            document_id="target-doc",
        ),
        "reported_annual_opex": _cost_evidence(
            amount=4_600_000.0,
            currency="USD",
            currency_year=2026,
            cost_scope="annual_opex",
            cost_category="annual_opex",
            status="none",
            source_id="target-src",
            claim_id="target-clm",
            document_id="target-doc",
        ),
    }


def _native_and_ranked(top_n: int | None = None) -> tuple[ComparableProjectEvidenceReportData, tuple[RankedComparableProject, ...], tuple[ComparableProjectEvidenceRecord, ...]]:
    native = _native_result()
    projects = _synthetic_projects()
    ranked = rank_comparable_projects(
        target=build_target_profile_from_native(native),
        projects=projects,
        config=SimilarityEngineConfig(),
        options=ProjectRankingOptions(top_n=6),
    )
    repository = _seed_repository_for_projects(projects)
    report = build_native_comparable_project_report_data(
        native_result=native,
        ranked_projects=ranked,
        provider=type("Provider", (), {"list_projects": lambda self: projects})(),
        repository=repository,
        target_cost_evidence=_target_cost_map(),
        top_n=top_n,
        options=ProjectRankingOptions(top_n=6),
    )
    return report, ranked, projects


def test_ranking_preserved_exactly_and_top_n_slices_without_reranking():
    report, ranked, _ = _native_and_ranked()
    assert [row.project_id for row in report.rows] == [item.project.identity.project_id for item in ranked]

    top5 = build_native_comparable_project_report_data(
        native_result=_native_result(),
        ranked_projects=ranked,
        provider=type("Provider", (), {"list_projects": lambda self: _synthetic_projects()})(),
        repository=_seed_repository_for_projects(_synthetic_projects()),
        target_cost_evidence=_target_cost_map(),
        top_n=5,
        options=ProjectRankingOptions(top_n=5),
    )
    assert len(top5.rows) == 5
    assert [row.project_id for row in top5.rows] == [item.project.identity.project_id for item in ranked[:5]]
    assert [row.similarity.similarity_percentage for row in top5.rows] == [item.similarity.similarity_pct for item in ranked[:5]]


def test_deterministic_report_assembly_and_similarity_passthrough():
    native = _native_result()
    projects = _synthetic_projects()
    ranked = rank_comparable_projects(target=build_target_profile_from_native(native), projects=projects, options=ProjectRankingOptions(top_n=6))
    repository = _seed_repository_for_projects(projects)
    provider = type("Provider", (), {"list_projects": lambda self: projects})()

    first = build_native_comparable_project_report_data(
        native_result=native,
        ranked_projects=ranked,
        provider=provider,
        repository=repository,
        target_cost_evidence=_target_cost_map(),
        top_n=None,
        options=ProjectRankingOptions(top_n=6),
    )
    second = build_native_comparable_project_report_data(
        native_result=native,
        ranked_projects=ranked,
        provider=provider,
        repository=repository,
        target_cost_evidence=_target_cost_map(),
        top_n=None,
        options=ProjectRankingOptions(top_n=6),
    )

    assert first == second
    assert first.metadata.deterministic is True
    assert [row.similarity.similarity_percentage for row in first.rows] == [item.similarity.similarity_pct for item in ranked]
    assert [row.similarity.confidence_label for row in first.rows] == [item.similarity.confidence_label for item in ranked]


def test_report_metadata_and_provenance_are_populated():
    report, ranked, _ = _native_and_ranked()
    assert isinstance(report.metadata, ComparableProjectReportMetadata)
    assert report.metadata.target_project_name == _native_result().request.project_name
    assert report.metadata.generated_candidate_count == 6
    assert report.metadata.returned_project_count == 6
    assert report.metadata.ranking_method == "native_similarity_weighted_v1"
    assert report.metadata.similarity_scale == "0-100 weighted percentage"
    assert report.provenance_trace_id
    assert report.rows[0].row_trace_id
    assert report.rows[0].evidence_references
    assert report.rows[0].evidence_references[0].claim_id is not None
    assert report.rows[0].evidence_references[0].document_id is not None


def test_similarity_components_and_explanations_reconcile():
    report, ranked, _ = _native_and_ranked()
    for row, native_row in zip(report.rows, ranked):
        assert row.similarity.total_score == pytest.approx(native_row.similarity.similarity_pct)
        assert row.similarity.similarity_percentage == pytest.approx(native_row.similarity.similarity_pct)
        assert row.similarity.component_scores == native_row.similarity.component_scores
        assert row.similarity.explanation
        assert row.similarity.matched_variables == native_row.similarity.strongest_matches
        assert row.similarity.unavailable_variables == native_row.similarity.unavailable_dimensions


def test_missing_data_and_conflicts_remain_explicit():
    report, _, _ = _native_and_ranked()
    sparse = next(row for row in report.rows if row.project_id == "SYN-D")
    conflict = next(row for row in report.rows if row.project_id == "SYN-E")

    assert "reported_project_capex" in sparse.missing_data.missing_fields
    assert sparse.missing_data.no_usable_image is False
    assert conflict.conflict_summary.conflict_detected is True
    assert conflict.conflict_summary.candidate_values
    assert conflict.conflict_summary.resolution_status == "unresolved"


def test_image_contract_and_no_invented_geometry():
    report, _, _ = _native_and_ranked()
    sparse = next(row for row in report.rows if row.project_id == "SYN-F")
    assert sparse.image_reference.image_available is False
    assert sparse.image_reference.image_status == "IMAGE_NOT_FOUND"
    assert sparse.engineering_profile.guideway_length_m is None
    assert sparse.engineering_profile.carrier_count is None


def test_cost_comparability_blocks_cross_currency_year_and_scope():
    native = _native_result()
    base_project = _synthetic_projects()[0]
    projects = (
        base_project,
        replace(base_project, identity=replace(base_project.identity, project_id="SYN-Y", facility_name="Synthetic Year Shift"), economics=replace(base_project.economics, currency="USD", currency_year=2021)),
        replace(base_project, identity=replace(base_project.identity, project_id="SYN-EUR", facility_name="Synthetic Euro Shift"), economics=replace(base_project.economics, currency="EUR", currency_year=2026)),
        replace(base_project, identity=replace(base_project.identity, project_id="SYN-SCOPE", facility_name="Synthetic Scope Shift"), economics=replace(base_project.economics, reported_project_capex=70_000_000.0, currency="USD", currency_year=2026, value_basis="actual")),
    )
    ranked = rank_comparable_projects(target=build_target_profile_from_native(native), projects=projects, options=ProjectRankingOptions(top_n=6))
    repository = _seed_repository_for_projects(projects)
    provider = type("Provider", (), {"list_projects": lambda self: projects})()

    report = build_native_comparable_project_report_data(
        native_result=native,
        ranked_projects=ranked,
        provider=provider,
        repository=repository,
        target_cost_evidence=_target_cost_map(),
        top_n=None,
        options=ProjectRankingOptions(top_n=6),
    )

    comparable_row = next(row for row in report.rows if row.project_id == "SYN-A")
    capex_comparison = next(item for item in comparable_row.cost_comparisons if item.cost_field == "reported_project_capex")
    assert capex_comparison.comparison_status == "COMPARABLE"
    assert capex_comparison.absolute_difference is not None
    assert capex_comparison.percentage_difference is not None

    year_shift = next(row for row in report.rows if row.project_id == "SYN-Y")
    year_cost = next(item for item in year_shift.cost_comparisons if item.cost_field == "reported_project_capex")
    assert year_cost.comparison_status == "NOT_COMPARABLE"
    assert year_cost.absolute_difference is None
    assert year_cost.percentage_difference is None

    eur_shift = next(row for row in report.rows if row.project_id == "SYN-EUR")
    eur_cost = next(item for item in eur_shift.cost_comparisons if item.cost_field == "reported_project_capex")
    assert eur_cost.comparison_status == "NOT_COMPARABLE"
    assert eur_cost.absolute_difference is None
    assert eur_cost.percentage_difference is None

    scope_project = replace(base_project, identity=replace(base_project.identity, project_id="SYN-SCOPE", facility_name="Synthetic Scope Shift"), economics=replace(base_project.economics, reported_project_capex=70_000_000.0, currency="USD", currency_year=2026, value_basis="actual"))
    scope_ranked = rank_comparable_projects(target=build_target_profile_from_native(native), projects=(scope_project,), options=ProjectRankingOptions(top_n=1))
    scope_report = build_native_comparable_project_report_data(
        native_result=native,
        ranked_projects=scope_ranked,
        provider=type("Provider", (), {"list_projects": lambda self: (scope_project,)})(),
        repository=_seed_repository_for_projects((scope_project,)),
        target_cost_evidence={
            "reported_project_capex": _cost_evidence(
                amount=68_000_000.0,
                currency="USD",
                currency_year=2026,
                cost_scope="different_scope_than_comparable",
                cost_category="project_capex",
                status="none",
                source_id="target-src",
                claim_id="target-clm",
                document_id="target-doc",
            )
        },
        top_n=None,
        options=ProjectRankingOptions(top_n=1),
    )
    scope_shift = scope_report.rows[0]
    scope_cost = next(item for item in scope_shift.cost_comparisons if item.cost_field == "reported_project_capex")
    assert scope_cost.comparison_status == "NOT_COMPARABLE"
    assert scope_cost.absolute_difference is None
    assert scope_cost.percentage_difference is None

    conflict_project = replace(base_project, identity=replace(base_project.identity, project_id="SYN-CONFLICT", facility_name="Synthetic Conflict"), conflicts=(EngineeringEvidenceConflict(
        conflict_id="cnf-project-capex",
        subject="Synthetic Conflict",
        field="project_capex",
        candidate_values=(60_000_000.0, 70_000_000.0),
        source_claim_ids=("clm-conflict-1", "clm-conflict-2"),
        source_tiers=("TIER_1", "TIER_3"),
        dates=(date(2025, 1, 1), date(2026, 1, 1)),
        units=("USD",),
        conflict_status="conflict",
        resolution_status="unresolved",
    ),))
    conflict_ranked = rank_comparable_projects(target=build_target_profile_from_native(native), projects=(conflict_project,), options=ProjectRankingOptions(top_n=1))
    conflict_report = build_native_comparable_project_report_data(
        native_result=native,
        ranked_projects=conflict_ranked,
        provider=type("Provider", (), {"list_projects": lambda self: (conflict_project,)})(),
        repository=_seed_repository_for_projects((conflict_project,)),
        target_cost_evidence=_target_cost_map(),
        top_n=None,
        options=ProjectRankingOptions(top_n=1),
    )
    conflict_cost = next(item for item in conflict_report.rows[0].cost_comparisons if item.cost_field == "reported_project_capex")
    assert conflict_cost.comparison_status == "CONFLICTED"
    assert conflict_cost.absolute_difference is None
    assert conflict_cost.percentage_difference is None

    missing_comparable_project = replace(base_project, identity=replace(base_project.identity, project_id="SYN-MISSING-COMP", facility_name="Synthetic Missing Comparable"), economics=replace(base_project.economics, reported_project_capex=None))
    missing_comparable_ranked = rank_comparable_projects(target=build_target_profile_from_native(native), projects=(missing_comparable_project,), options=ProjectRankingOptions(top_n=1))
    missing_comparable_report = build_native_comparable_project_report_data(
        native_result=native,
        ranked_projects=missing_comparable_ranked,
        provider=type("Provider", (), {"list_projects": lambda self: (missing_comparable_project,)})(),
        repository=_seed_repository_for_projects((missing_comparable_project,)),
        target_cost_evidence=_target_cost_map(),
        top_n=None,
        options=ProjectRankingOptions(top_n=1),
    )
    missing_comparable_cost = next(item for item in missing_comparable_report.rows[0].cost_comparisons if item.cost_field == "reported_project_capex")
    assert missing_comparable_cost.comparison_status == "MISSING_COMPARABLE"
    assert missing_comparable_cost.absolute_difference is None
    assert missing_comparable_cost.percentage_difference is None
    assert not missing_comparable_report.chart_series.directly_comparable_project_cost

    missing_target_report = build_native_comparable_project_report_data(
        native_result=native,
        ranked_projects=ranked,
        provider=provider,
        repository=repository,
        target_cost_evidence={
            "reported_project_capex": _cost_evidence(
                amount=None,
                currency="USD",
                currency_year=2026,
                cost_scope="total_project_cost",
                cost_category="project_capex",
                status="none",
                source_id="target-src",
                claim_id="target-clm",
                document_id="target-doc",
            )
        },
        top_n=None,
        options=ProjectRankingOptions(top_n=6),
    )
    missing_target_cost = next(item for item in missing_target_report.rows[0].cost_comparisons if item.cost_field == "reported_project_capex")
    assert missing_target_cost.comparison_status == "MISSING_TARGET"
    assert missing_target_cost.absolute_difference is None
    assert missing_target_cost.percentage_difference is None
    assert not missing_target_report.chart_series.directly_comparable_project_cost


def test_chart_series_reconcile_to_rows_and_exclude_non_comparable_cost_points():
    report, _, _ = _native_and_ranked()
    assert [point.project_id for point in report.chart_series.similarity_ranking] == [row.project_id for row in report.rows]
    assert [point.project_id for point in report.chart_series.patients_per_day_comparison] == [row.project_id for row in report.rows]
    assert [point.project_id for point in report.chart_series.scanner_count_comparison] == [row.project_id for row in report.rows]
    assert [point.project_id for point in report.chart_series.cyclotron_count_comparison] == [row.project_id for row in report.rows]
    assert all(point.comparison_status == "COMPARABLE" for point in report.chart_series.similarity_ranking)
    direct_cost_rows = {row.project_id: next(item for item in row.cost_comparisons if item.cost_field == "reported_project_capex").comparison_status for row in report.rows}
    assert all(direct_cost_rows[point.project_id] == "COMPARABLE" for point in report.chart_series.directly_comparable_project_cost)


def test_limitations_and_top_five_match_first_five_native_rankings():
    report, ranked, _ = _native_and_ranked(top_n=5)
    assert len(report.rows) == 5
    assert [row.project_id for row in report.rows] == [item.project.identity.project_id for item in ranked[:5]]
    assert "No inflation, FX, or base-year normalization" in report.limitations[1]


def test_report_does_not_mutate_similarity_result_and_can_be_reused():
    native = _native_result()
    projects = _synthetic_projects()
    ranked = rank_comparable_projects(target=build_target_profile_from_native(native), projects=projects, options=ProjectRankingOptions(top_n=6))
    snapshot = tuple((item.rank, item.project.identity.project_id, item.similarity.similarity_pct) for item in ranked)
    repository = _seed_repository_for_projects(projects)
    provider = type("Provider", (), {"list_projects": lambda self: projects})()
    build_native_comparable_project_report_data(
        native_result=native,
        ranked_projects=ranked,
        provider=provider,
        repository=repository,
        target_cost_evidence=_target_cost_map(),
        top_n=None,
        options=ProjectRankingOptions(top_n=6),
    )
    assert snapshot == tuple((item.rank, item.project.identity.project_id, item.similarity.similarity_pct) for item in ranked)

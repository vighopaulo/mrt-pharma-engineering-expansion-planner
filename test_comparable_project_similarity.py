from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from comparable_project_similarity import (
    ComparableProjectClinicalScale,
    ComparableProjectEconomics,
    ComparableProjectEvidenceRecord,
    ComparableProjectFacility,
    ComparableProjectIdentity,
    ComparableProjectPerformance,
    ComparableProjectProduction,
    LocalEvidenceProvider,
    ProjectImageReference,
    ProjectRankingOptions,
    SimilarityEngineConfig,
    build_comparable_project_report,
    build_target_profile_from_native,
    deduplicate_projects,
    rank_comparable_projects,
)
from decision_pipeline import run_native_decision_pipeline
from engineering_evidence import EngineeringEvidenceRepository, EngineeringEvidenceConflict
from test_decision_pipeline import _request as baseline_request


def _image(status: str, suffix: str) -> ProjectImageReference:
    return ProjectImageReference(
        image_reference_id=f"img-{suffix}",
        image_source_url=f"https://images.example/{suffix}.jpg" if status != "IMAGE_NOT_FOUND" else None,
        image_page_url=f"https://source.example/{suffix}" if status != "IMAGE_NOT_FOUND" else None,
        image_source_organization="Synthetic Fixtures Lab",
        image_caption=f"Synthetic fixture image {suffix}",
        image_provenance="synthetic-fixture",
        image_retrieval_date=date(2026, 8, 14),
        image_status=status,  # type: ignore[arg-type]
        image_confidence=0.95 if "VERIFIED" in status else 0.4,
    )


def _project(
    *,
    project_id: str,
    facility_name: str,
    country: str,
    patients_per_day: float | None,
    scanner_count: int | None,
    cyclotron_count: int | None,
    radionuclides: tuple[str, ...],
    capex: float | None,
    opex: float | None,
    source_tiers: tuple[str, ...],
    claim_ids: tuple[str, ...],
    source_urls: tuple[str, ...],
    image_status: str,
    conflicts: tuple[EngineeringEvidenceConflict, ...] = (),
    missing_fields: tuple[str, ...] = (),
    confidence: float | None = None,
    city: str = "Test City",
    owner: str = "Test Health",
    facility_type: str = "conventional",
    operational_status: str = "operational",
    opening_year: int | None = 2022,
    operating_hours_per_day: float | None = 18.0,
    facility_area_m2: float | None = None,
) -> ComparableProjectEvidenceRecord:
    return ComparableProjectEvidenceRecord(
        identity=ComparableProjectIdentity(
            project_id=project_id,
            facility_name=facility_name,
            owner_organization=owner,
            city=city,
            state_or_province=None,
            country=country,
            region="North America" if country in {"US", "CA"} else "Other",
            facility_type=facility_type,
            operational_status=operational_status,  # type: ignore[arg-type]
            opening_year=opening_year,
            description="Synthetic test fixture project",
        ),
        clinical=ComparableProjectClinicalScale(
            patients_per_day=patients_per_day,
            patients_per_year=(patients_per_day * 300.0 if patients_per_day is not None else None),
            scanner_count=scanner_count,
            uptake_rooms=7 if scanner_count is not None else None,
            injection_resources=2 if scanner_count is not None else None,
            operating_hours_per_day=operating_hours_per_day,
        ),
        production=ComparableProjectProduction(
            cyclotron_count=cyclotron_count,
            cyclotron_manufacturer="SyntheticCo" if cyclotron_count is not None else None,
            cyclotron_model="SYN-X" if cyclotron_count is not None else None,
            radiopharmacy_presence=True if cyclotron_count is not None else None,
            supported_radionuclides=radionuclides,
        ),
        facility=ComparableProjectFacility(
            facility_area_m2=facility_area_m2,
            internal_transport_approach="manual",
        ),
        economics=ComparableProjectEconomics(
            reported_project_capex=capex,
            reported_annual_opex=opex,
            currency="USD" if (capex is not None or opex is not None) else None,
            currency_year=2026 if (capex is not None or opex is not None) else None,
            value_basis="actual" if capex is not None else "unknown",
        ),
        performance=ComparableProjectPerformance(
            reported_patient_capacity_per_day=patients_per_day,
            reported_throughput_per_day=patients_per_day,
        ),
        source_ids=tuple(f"src-{project_id}-{i}" for i, _ in enumerate(source_tiers, start=1)),
        document_ids=tuple(f"doc-{project_id}-{i}" for i, _ in enumerate(source_tiers, start=1)),
        claim_ids=claim_ids,
        source_urls=source_urls,
        source_tiers=source_tiers,
        evidence_dates=(date(2026, 1, 1),) * len(source_tiers),
        conflicts=conflicts,
        missing_fields=missing_fields,
        confidence=confidence,
        image_reference=_image(image_status, project_id),
    )


def _synthetic_projects() -> tuple[ComparableProjectEvidenceRecord, ...]:
    # Project A: extremely similar, strong evidence, verified image.
    project_a = _project(
        project_id="SYN-A",
        facility_name="Synthetic Alpha",
        country="US",
        patients_per_day=200.0,
        scanner_count=3,
        cyclotron_count=1,
        radionuclides=("F-18", "Ga-68", "Tc-99m"),
        capex=6_000_000.0,
        opex=4_600_000.0,
        source_tiers=("TIER_1", "TIER_1", "TIER_2"),
        claim_ids=("clm-a1", "clm-a2", "clm-a3"),
        source_urls=("https://src/a1", "https://src/a2", "https://src/a3"),
        image_status="VERIFIED_FACILITY_IMAGE",
        confidence=0.95,
    )

    # Project B: similar volume, different cyclotron count.
    project_b = _project(
        project_id="SYN-B",
        facility_name="Synthetic Beta",
        country="US",
        patients_per_day=195.0,
        scanner_count=3,
        cyclotron_count=2,
        radionuclides=("F-18", "Ga-68", "Tc-99m"),
        capex=8_000_000.0,
        opex=5_200_000.0,
        source_tiers=("TIER_1", "TIER_2"),
        claim_ids=("clm-b1", "clm-b2"),
        source_urls=("https://src/b1", "https://src/b2"),
        image_status="VERIFIED_PROJECT_IMAGE",
        confidence=0.9,
    )

    # Project C: similar CAPEX, poor clinical similarity.
    project_c = _project(
        project_id="SYN-C",
        facility_name="Synthetic Gamma",
        country="US",
        patients_per_day=80.0,
        scanner_count=1,
        cyclotron_count=1,
        radionuclides=("F-18",),
        capex=6_100_000.0,
        opex=2_000_000.0,
        source_tiers=("TIER_2",),
        claim_ids=("clm-c1",),
        source_urls=("https://src/c1",),
        image_status="VERIFIED_COMPONENT_IMAGE",
        confidence=0.75,
    )

    # Project D: high similarity but sparse evidence.
    project_d = _project(
        project_id="SYN-D",
        facility_name="Synthetic Delta",
        country="CA",
        patients_per_day=198.0,
        scanner_count=None,
        cyclotron_count=1,
        radionuclides=("F-18", "Ga-68", "Tc-99m"),
        capex=None,
        opex=None,
        source_tiers=("TIER_3",),
        claim_ids=("clm-d1",),
        source_urls=("https://src/d1",),
        image_status="SOURCE_PAGE_HAS_IMAGE",
        missing_fields=("scanner_count", "reported_project_capex", "reported_annual_opex"),
        confidence=0.45,
    )

    # Project E: conflicting cost evidence.
    conflict = EngineeringEvidenceConflict(
        conflict_id="cnf-e-capex",
        subject="Synthetic Epsilon",
        field="project_capex",
        candidate_values=(80_000_000.0, 95_000_000.0),
        source_claim_ids=("clm-e1", "clm-e2"),
        source_tiers=("TIER_1", "TIER_3"),
        dates=(date(2025, 1, 1), date(2026, 1, 1)),
        units=("USD",),
        conflict_status="conflict",
        resolution_status="unresolved",
    )
    project_e = _project(
        project_id="SYN-E",
        facility_name="Synthetic Epsilon",
        country="US",
        patients_per_day=205.0,
        scanner_count=3,
        cyclotron_count=1,
        radionuclides=("F-18", "Ga-68", "Tc-99m"),
        capex=80_000_000.0,
        opex=4_700_000.0,
        source_tiers=("TIER_1", "TIER_3"),
        claim_ids=("clm-e1", "clm-e2"),
        source_urls=("https://src/e1", "https://src/e2"),
        image_status="VERIFIED_FACILITY_IMAGE",
        conflicts=(conflict,),
        confidence=0.8,
    )

    # Project F: strong engineering similarity but image unavailable.
    project_f = _project(
        project_id="SYN-F",
        facility_name="Synthetic Zeta",
        country="US",
        patients_per_day=202.0,
        scanner_count=3,
        cyclotron_count=1,
        radionuclides=("F-18", "Ga-68", "Tc-99m"),
        capex=6_200_000.0,
        opex=4_650_000.0,
        source_tiers=("TIER_1", "TIER_2"),
        claim_ids=("clm-f1", "clm-f2"),
        source_urls=("https://src/f1", "https://src/f2"),
        image_status="IMAGE_NOT_FOUND",
        confidence=0.85,
    )

    return (project_a, project_b, project_c, project_d, project_e, project_f)


def _native_result() -> NativeDecisionComparisonResult:
    # Deterministic target profile sourced from existing native pipeline.
    req = baseline_request(seed=20260813)
    return run_native_decision_pipeline(req)


def test_target_profile_builds_from_native_result():
    native = _native_result()
    target = build_target_profile_from_native(native)
    assert target.target_patients_per_day == float(native.request.target_patients_per_day)
    assert target.scanner_count == native.request.conventional.scanners
    assert target.cyclotron_count == native.request.conventional.installed_cyclotron_units
    assert target.conventional_capex == pytest.approx(native.conventional.capex_result.total_capex)


def test_deduplication_merges_same_facility_identity():
    project = _synthetic_projects()[0]
    duplicate = replace(
        project,
        claim_ids=project.claim_ids + ("clm-a4",),
        source_urls=project.source_urls + ("https://src/a4",),
    )
    merged = deduplicate_projects((project, duplicate))
    assert len(merged) == 1
    assert "clm-a4" in merged[0].claim_ids


def test_similarity_ranking_deterministic_and_tie_breaking():
    native = _native_result()
    target = build_target_profile_from_native(native)
    projects = _synthetic_projects()

    ranked_one = rank_comparable_projects(target=target, projects=projects)
    ranked_two = rank_comparable_projects(target=target, projects=projects)

    sig_one = [(row.rank, row.project.identity.project_id, round(row.similarity.similarity_pct, 6)) for row in ranked_one]
    sig_two = [(row.rank, row.project.identity.project_id, round(row.similarity.similarity_pct, 6)) for row in ranked_two]
    assert sig_one == sig_two


def test_sparse_evidence_reduces_coverage_and_confidence():
    native = _native_result()
    target = build_target_profile_from_native(native)
    projects = _synthetic_projects()
    ranked = rank_comparable_projects(target=target, projects=projects)

    sparse = next(item for item in ranked if item.project.identity.project_id == "SYN-D")
    assert sparse.similarity.evidence_coverage_pct < 80.0
    assert sparse.similarity.confidence_label in {"LOW", "INSUFFICIENT_EVIDENCE", "MODERATE"}


def test_conflict_project_exposes_unresolved_conflict_without_silent_average():
    native = _native_result()
    target = build_target_profile_from_native(native)
    ranked = rank_comparable_projects(target=target, projects=_synthetic_projects())

    conflict_project = next(item for item in ranked if item.project.identity.project_id == "SYN-E")
    assert conflict_project.similarity.unresolved_conflicts
    assert any("project_capex" in value for value in conflict_project.similarity.unresolved_conflicts)


def test_missing_values_not_treated_as_zero():
    native = _native_result()
    target = build_target_profile_from_native(native)
    ranked = rank_comparable_projects(target=target, projects=_synthetic_projects())

    sparse = next(item for item in ranked if item.project.identity.project_id == "SYN-D")
    capex_dim = next(score for score in sparse.similarity.component_scores if score.dimension == "project_capex")
    assert capex_dim.compared is False
    assert capex_dim.score_pct is None


def test_ranking_filters_and_display_ready_image_requirement():
    native = _native_result()
    target = build_target_profile_from_native(native)
    projects = _synthetic_projects()

    options = ProjectRankingOptions(
        top_n=10,
        minimum_similarity_pct=0.0,
        minimum_evidence_coverage_pct=0.0,
        minimum_confidence_score=0.0,
        country_filter="US",
        required_image_status_for_display_ready="VERIFIED_FACILITY_IMAGE",
    )
    ranked = rank_comparable_projects(target=target, projects=projects, options=options)
    assert ranked
    assert all(item.project.identity.country == "US" for item in ranked)
    assert all(
        item.project.image_reference is not None and item.project.image_reference.image_status == "VERIFIED_FACILITY_IMAGE"
        for item in ranked
    )


def test_provider_boundary_and_report_contract():
    native = _native_result()
    projects = _synthetic_projects()

    repository = EngineeringEvidenceRepository()
    provider = LocalEvidenceProvider(repository=repository, projects=projects)

    report = build_comparable_project_report(native_result=native, provider=provider)
    assert report.top_comparable_projects
    assert "External live web retrieval is NOT CONNECTED" in report.limitations[0]
    assert report.provenance_trace_id
    assert report.conventional_vs_mrt_deltas.capex_delta_mrt_minus_conventional is not None


def test_cross_currency_or_missing_cost_is_excluded_dimension():
    native = _native_result()
    target = build_target_profile_from_native(native)
    eur_project = replace(
        _synthetic_projects()[0],
        economics=replace(_synthetic_projects()[0].economics, currency="EUR", currency_year=2018),
    )

    ranked_default = rank_comparable_projects(target=target, projects=(eur_project,))
    capex_dim_default = next(score for score in ranked_default[0].similarity.component_scores if score.dimension == "project_capex")
    assert capex_dim_default.compared is False

    usd_project = replace(
        _synthetic_projects()[0],
        economics=replace(_synthetic_projects()[0].economics, currency="USD", currency_year=2026),
    )
    target_with_currency = replace(target, conventional_currency="USD", conventional_currency_year=2026)
    ranked_compatible = rank_comparable_projects(target=target_with_currency, projects=(usd_project,))
    capex_dim_compatible = next(score for score in ranked_compatible[0].similarity.component_scores if score.dimension == "project_capex")
    assert capex_dim_compatible.compared is True


def test_synthetic_demonstration_printout_for_six_projects(capsys):
    native = _native_result()
    target = build_target_profile_from_native(native)
    projects = _synthetic_projects()

    ranked = rank_comparable_projects(
        target=target,
        projects=projects,
        config=SimilarityEngineConfig(),
        options=ProjectRankingOptions(top_n=6),
    )

    for row in ranked:
        print(
            row.rank,
            row.project.identity.project_id,
            row.project.identity.facility_name,
            row.project.identity.country,
            f"{row.similarity.similarity_pct:.2f}",
        )

    output = capsys.readouterr().out.strip().splitlines()
    assert len(output) == 6
    assert output[0].startswith("1 ")
    assert any("SYN-A" in line for line in output)

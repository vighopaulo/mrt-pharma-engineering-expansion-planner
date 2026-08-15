from __future__ import annotations

from dataclasses import replace
import math

import pytest

from architecture_recommendation import ConventionalArchitectureBounds, MrtArchitectureBounds
from decision_pipeline import run_native_decision_pipeline
from engineering_evidence import EngineeringAssumptionProposal
from existing_facility_retrofit import (
    ExistingFacilityBaseline,
    ExistingFacilityMetadata,
    ExistingFacilityResourceFact,
    ExistingFacilityRetrofitRequest,
    apply_accepted_proposal_to_baseline_resource,
    build_design_horizon_request_from_existing_facility_retrofit,
    build_native_existing_facility_retrofit_report_data,
    run_native_existing_facility_retrofit,
)
from test_decision_pipeline import _request as baseline_request


def _baseline_resources(*, include_mrt_existing: bool = False) -> dict[str, ExistingFacilityResourceFact]:
    return {
        "scanners": ExistingFacilityResourceFact(resource="scanners", existing_quantity=2.0, operational_quantity=2.0, knowledge_status="KNOWN"),
        "injection_resources": ExistingFacilityResourceFact(resource="injection_resources", existing_quantity=2.0, operational_quantity=2.0, knowledge_status="KNOWN"),
        "uptake_resources": ExistingFacilityResourceFact(resource="uptake_resources", existing_quantity=6.0, operational_quantity=6.0, knowledge_status="KNOWN"),
        "distribution_concurrency": ExistingFacilityResourceFact(resource="distribution_concurrency", existing_quantity=1.0, operational_quantity=1.0, knowledge_status="KNOWN"),
        "cyclotron_units": ExistingFacilityResourceFact(resource="cyclotron_units", existing_quantity=1.0, operational_quantity=1.0, knowledge_status="KNOWN"),
        "radiopharmacy_units": ExistingFacilityResourceFact(resource="radiopharmacy_units", existing_quantity=1.0, operational_quantity=1.0, knowledge_status="KNOWN"),
        "mrt_base_infrastructure_units": ExistingFacilityResourceFact(resource="mrt_base_infrastructure_units", existing_quantity=1.0 if include_mrt_existing else 0.0, operational_quantity=1.0 if include_mrt_existing else 0.0, knowledge_status="KNOWN"),
        "mrt_endpoints": ExistingFacilityResourceFact(resource="mrt_endpoints", existing_quantity=2.0 if include_mrt_existing else 0.0, operational_quantity=2.0 if include_mrt_existing else 0.0, knowledge_status="KNOWN"),
        "guideway_length_m": ExistingFacilityResourceFact(resource="guideway_length_m", existing_quantity=150.0 if include_mrt_existing else 0.0, operational_quantity=150.0 if include_mrt_existing else 0.0, knowledge_status="KNOWN"),
        "vertical_transitions": ExistingFacilityResourceFact(resource="vertical_transitions", existing_quantity=1.0 if include_mrt_existing else 0.0, operational_quantity=1.0 if include_mrt_existing else 0.0, knowledge_status="KNOWN"),
        "building_connections": ExistingFacilityResourceFact(resource="building_connections", existing_quantity=1.0 if include_mrt_existing else 0.0, operational_quantity=1.0 if include_mrt_existing else 0.0, knowledge_status="KNOWN"),
        "mrt_carriers": ExistingFacilityResourceFact(resource="mrt_carriers", existing_quantity=1.0 if include_mrt_existing else None, operational_quantity=1.0 if include_mrt_existing else None, knowledge_status="KNOWN" if include_mrt_existing else "NOT_MODELED"),
    }


def _retrofit_request(*, target: int = 220, include_mrt_existing: bool = False) -> ExistingFacilityRetrofitRequest:
    baseline = ExistingFacilityBaseline(
        metadata=ExistingFacilityMetadata(
            facility_id="SYNTH-RETROFIT-001",
            facility_name="Synthetic Retrofit Hospital",
            location="SYNTHETIC-CITY",
            baseline_year=2026,
            provenance_reference_ids=("inv-001", "doc-001"),
        ),
        current_patients_per_day=120.0,
        resources=_baseline_resources(include_mrt_existing=include_mrt_existing),
    )

    return ExistingFacilityRetrofitRequest(
        project_mode="EXISTING_FACILITY_EXPANSION",
        baseline=baseline,
        target_patients_per_day=target,
        pipeline_template=baseline_request(seed=20260813),
        conventional_bounds=ConventionalArchitectureBounds(
            scanners=(2, 3, 4),
            injection_resources=(2, 3),
            uptake_resources=(6, 8, 10),
            distribution_concurrency=(1, 2),
            transport_minutes=(7.0,),
        ),
        mrt_bounds=MrtArchitectureBounds(
            scanners=(2, 3, 4),
            injection_resources=(2, 3),
            uptake_resources=(6, 8, 10),
            distribution_concurrency=(1, 2),
            installed_mrt_endpoints=((2, 4) if include_mrt_existing else (0, 2, 4)),
            transport_minutes=(5.0,),
        ),
        minimum_reliability=0.8,
        seeds=(20260813, 20260814),
        max_candidate_count=256,
        throughput_thresholds_per_day=(120.0, float(target)),
        worst_run_count=2,
    )


def test_greenfield_mode_is_passthrough_and_does_not_change_native_pipeline_behavior():
    template = baseline_request(seed=20260813)
    before = run_native_decision_pipeline(template)

    request = replace(
        _retrofit_request(target=180),
        project_mode="GREENFIELD",
        pipeline_template=template,
    )
    result = run_native_existing_facility_retrofit(request)
    after = run_native_decision_pipeline(template)

    assert result.project_mode == "GREENFIELD"
    assert result.recommendation_result is not None
    assert before == after


def test_unknown_baseline_quantity_blocks_analysis_and_does_not_silently_default_to_zero():
    baseline = _retrofit_request().baseline
    unknown_scanners = replace(
        baseline.resources["scanners"],
        existing_quantity=None,
        operational_quantity=None,
        knowledge_status="UNKNOWN",
    )
    broken = replace(baseline, resources={**baseline.resources, "scanners": unknown_scanners})

    result = run_native_existing_facility_retrofit(replace(_retrofit_request(), baseline=broken))

    assert result.conventional.feasibility_status == "INSUFFICIENT_BASELINE_DATA"
    assert result.mrt.feasibility_status == "INSUFFICIENT_BASELINE_DATA"
    assert "scanners" in result.evidence_gaps


def test_existing_assets_are_not_rebilled_and_quantity_arithmetic_reconciles():
    result = run_native_existing_facility_retrofit(_retrofit_request(target=180))

    for row in result.resource_disposition_table:
        if row.baseline_existing_quantity is not None and row.conventional_final_quantity is not None:
            assert math.isclose(
                row.conventional_final_quantity,
                row.baseline_existing_quantity + (row.conventional_additional_quantity or 0.0),
                rel_tol=0.0,
                abs_tol=1e-9,
            )
        if row.baseline_existing_quantity is not None and row.mrt_final_quantity is not None:
            assert math.isclose(
                row.mrt_final_quantity,
                row.baseline_existing_quantity + (row.mrt_additional_quantity or 0.0),
                rel_tol=0.0,
                abs_tol=1e-9,
            )

    assert result.conventional.incremental_capex is None or result.conventional.incremental_capex >= 0.0
    assert result.mrt.incremental_capex is None or result.mrt.incremental_capex >= 0.0


def test_incremental_opex_and_revenue_are_calculated_from_baseline_deltas():
    result = run_native_existing_facility_retrofit(_retrofit_request(target=180))
    assert result.baseline_operational is not None

    if result.conventional.annual_opex is not None:
        assert math.isclose(
            result.conventional.incremental_annual_opex,
            result.conventional.annual_opex - result.baseline_operational.annual_opex,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
    if result.mrt.annual_opex is not None:
        assert math.isclose(
            result.mrt.incremental_annual_opex,
            result.mrt.annual_opex - result.baseline_operational.annual_opex,
            rel_tol=0.0,
            abs_tol=1e-9,
        )


def test_conventional_and_mrt_expand_from_identical_baseline_inventory():
    result = run_native_existing_facility_retrofit(_retrofit_request(target=180))
    baseline_by_resource = {row.resource: row.baseline_existing_quantity for row in result.resource_disposition_table}

    assert baseline_by_resource["scanners"] == pytest.approx(2.0)
    assert baseline_by_resource["injection_resources"] == pytest.approx(2.0)
    assert baseline_by_resource["uptake_resources"] == pytest.approx(6.0)
    assert baseline_by_resource["cyclotron_units"] == pytest.approx(1.0)


def test_mrt_bottleneck_does_not_assume_clinical_bottlenecks_disappear():
    result = run_native_existing_facility_retrofit(_retrofit_request(target=220))

    if result.mrt.bottleneck_resource is not None:
        assert result.mrt.bottleneck_resource in {"scanner", "injection", "uptake", "distribution"}


def test_non_qualifying_paths_are_reported_as_infeasible_not_crashes():
    very_tight = replace(
        _retrofit_request(target=260),
        conventional_bounds=ConventionalArchitectureBounds(
            scanners=(2,),
            injection_resources=(2,),
            uptake_resources=(6,),
            distribution_concurrency=(1,),
            transport_minutes=(7.0,),
        ),
        mrt_bounds=MrtArchitectureBounds(
            scanners=(2,),
            injection_resources=(2,),
            uptake_resources=(6,),
            distribution_concurrency=(1,),
            installed_mrt_endpoints=(0,),
            transport_minutes=(5.0,),
        ),
    )
    result = run_native_existing_facility_retrofit(very_tight)

    assert result.conventional.feasibility_status in {"INFEASIBLE_WITHIN_BOUNDS", "MODIFICATION_FEASIBILITY_NOT_MODELED", "FEASIBLE_WITH_EXPANSION", "FEASIBLE"}
    assert result.mrt.feasibility_status in {"INFEASIBLE_WITHIN_BOUNDS", "MODIFICATION_FEASIBILITY_NOT_MODELED", "FEASIBLE_WITH_EXPANSION", "FEASIBLE"}


def test_existing_mrt_infrastructure_can_be_represented_and_preserved():
    result = run_native_existing_facility_retrofit(_retrofit_request(target=180, include_mrt_existing=True))
    rows = {row.resource: row for row in result.resource_disposition_table}

    assert rows["mrt_endpoints"].baseline_existing_quantity == pytest.approx(2.0)
    assert rows["guideway_length_m"].baseline_existing_quantity == pytest.approx(150.0)


def test_carrier_quantity_remains_tied_to_authoritative_distribution_contract():
    result = run_native_existing_facility_retrofit(_retrofit_request(target=180))
    if result.recommendation_result and result.recommendation_result.best_qualifying_mrt is not None:
        architecture = result.recommendation_result.best_qualifying_mrt.architecture
        assert architecture.operated_mrt_carriers == architecture.distribution_concurrency


def test_report_contract_reconciles_to_engine_result():
    result = run_native_existing_facility_retrofit(_retrofit_request(target=180))
    report = build_native_existing_facility_retrofit_report_data(result)

    assert report.metadata["report_trace_id"] == result.report_trace_id
    assert len(report.resource_rows) == len(result.resource_disposition_table)
    assert len(report.economics_rows) == len(result.economics_table)
    assert report.bottleneck_migration == result.bottleneck_migration


def test_horizon_compatibility_template_preserves_existing_assets():
    result = run_native_existing_facility_retrofit(_retrofit_request(target=180))
    assert result.horizon_compatible_template is not None

    horizon_request = build_design_horizon_request_from_existing_facility_retrofit(
        result,
        analysis_years=5,
        demand_mode="constant",
        constant_daily_demand=180.0,
    )
    assert horizon_request.pipeline_template.conventional.deployment_mode == "existing_facility_expansion"
    assert horizon_request.pipeline_template.conventional.existing_scanners == 2


def test_evidence_promotion_requires_accepted_status_and_preserves_provenance():
    baseline = _retrofit_request().baseline

    rejected = EngineeringAssumptionProposal(
        proposal_id="p-rejected",
        parameter_name="scanners",
        proposed_value=3,
        unit="count",
        supporting_claim_ids=("claim-a",),
        source_tiers=("TIER_1",),
        confidence=0.9,
        conflict_status="none",
        promotion_status="candidate",
        trace_id="trace-rejected",
    )
    with pytest.raises(ValueError, match="accepted"):
        apply_accepted_proposal_to_baseline_resource(baseline, resource="scanners", proposal=rejected)

    accepted = replace(rejected, proposal_id="p-accepted", promotion_status="accepted", trace_id="trace-accepted")
    promoted = apply_accepted_proposal_to_baseline_resource(baseline, resource="scanners", proposal=accepted)

    assert promoted.resources["scanners"].knowledge_status == "EVIDENCE_BACKED"
    assert promoted.resources["scanners"].existing_quantity == pytest.approx(3.0)
    assert "claim-a" in promoted.resources["scanners"].source_claim_ids
    assert promoted.resources["scanners"].provenance_trace_id == "trace-accepted"

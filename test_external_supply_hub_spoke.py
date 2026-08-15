from __future__ import annotations

import math
from dataclasses import replace

import pytest

from decision_pipeline import run_native_decision_pipeline
from existing_facility_retrofit import (
    ExistingFacilityBaseline,
    ExistingFacilityMetadata,
    ExistingFacilityResourceFact,
    ExistingFacilityRetrofitRequest,
    run_native_existing_facility_retrofit,
)
from architecture_recommendation import ConventionalArchitectureBounds, MrtArchitectureBounds
from external_supply_hub_spoke import (
    ExternalSupplyEconomicInputs,
    ExternalSupplyScenario,
    ExternalSupplySource,
    ExternalSupplyTransportSegment,
    build_receiving_workflow_from_retrofit_resource_facts,
    run_external_supply_hub_spoke,
)
from test_decision_pipeline import _request as decision_request


def _source() -> ExternalSupplySource:
    return ExternalSupplySource(
        source_id="SRC-UPSTREAM-001",
        source_name="Synthetic Upstream Hub",
        source_type="CYCLOTRON",
        location_label="SYNTHETIC_UPSTREAM_REGION",
        supported_radionuclides=("F-18", "Ga-68"),
        production_mode="EXTERNAL",
        provenance_status="USER_ASSUMED",
    )


def _workflow(*, on_site_cyclotron_units: int = 0):
    return build_receiving_workflow_from_retrofit_resource_facts(
        {
            "radiopharmacy_units": 1,
            "injection_resources": 2,
            "uptake_resources": 3,
            "scanners": 2,
            "cyclotron_units": on_site_cyclotron_units,
        },
        conventional_internal_distribution_minutes=18.0,
        mrt_internal_distribution_minutes=6.0,
        administration_minutes=12.0,
        provenance_status="USER_ASSUMED",
    )


def _common_segments(*, destination_label: str = "SYNTHETIC_DESTINATION_AIRPORT") -> tuple[ExternalSupplyTransportSegment, ...]:
    return (
        ExternalSupplyTransportSegment(
            segment_id="seg-origin-handling",
            segment_type="ORIGIN_HANDLING",
            designation="COMMON_PREFIX",
            origin_label="UPSTREAM_HUB",
            destination_label="UPSTREAM_RELEASE",
            distance_km=0.0,
            duration_minutes=20.0,
            handling_minutes=10.0,
            transport_mode="GROUND",
            assumption_label="SYNTHETIC DEMONSTRATION ASSUMPTION",
        ),
        ExternalSupplyTransportSegment(
            segment_id="seg-air-transport",
            segment_type="AIR_TRANSPORT",
            designation="COMMON_PREFIX",
            origin_label="UPSTREAM_AIRPORT",
            destination_label=destination_label,
            distance_km=None,
            duration_minutes=45.0,
            handling_minutes=0.0,
            transport_mode="AIR",
            assumption_label="SYNTHETIC DEMONSTRATION ASSUMPTION",
        ),
        ExternalSupplyTransportSegment(
            segment_id="seg-destination-handling",
            segment_type="DESTINATION_HANDLING",
            designation="COMMON_PREFIX",
            origin_label=destination_label,
            destination_label="AIRPORT_RELEASE_POINT",
            distance_km=0.0,
            duration_minutes=15.0,
            handling_minutes=10.0,
            transport_mode="GROUND",
            assumption_label="SYNTHETIC DEMONSTRATION ASSUMPTION",
        ),
    )


def _last_mile_conventional(*, minutes: float = 18.0, handling_minutes: float = 5.0, distance_km: float = 0.7) -> ExternalSupplyTransportSegment:
    return ExternalSupplyTransportSegment(
        segment_id="seg-last-mile-conventional",
        segment_type="LAST_MILE_TRANSFER",
        designation="CONVENTIONAL_LAST_MILE",
        origin_label="SYNTHETIC_DESTINATION_AIRPORT",
        destination_label="SYNTHETIC_RECEIVING_HOSPITAL",
        distance_km=distance_km,
        duration_minutes=minutes,
        handling_minutes=handling_minutes,
        transport_mode="GROUND",
        assumption_label="SYNTHETIC DEMONSTRATION ASSUMPTION",
    )


def _last_mile_mrt(*, minutes: float = 10.0, handling_minutes: float = 5.0, distance_km: float = 0.7) -> ExternalSupplyTransportSegment:
    return ExternalSupplyTransportSegment(
        segment_id="seg-last-mile-mrt",
        segment_type="LAST_MILE_TRANSFER",
        designation="MRT_LAST_MILE",
        origin_label="SYNTHETIC_DESTINATION_AIRPORT",
        destination_label="SYNTHETIC_RECEIVING_HOSPITAL",
        distance_km=distance_km,
        duration_minutes=minutes,
        handling_minutes=handling_minutes,
        transport_mode="MRT",
        assumption_label="SYNTHETIC DEMONSTRATION ASSUMPTION",
    )


def _scenario(
    *,
    project_mode: str = "GREENFIELD",
    conventional_minutes: float = 10.0,
    mrt_minutes: float = 10.0,
    conventional_handling_minutes: float = 5.0,
    mrt_handling_minutes: float = 5.0,
    conventional_distance_km: float = 0.7,
    mrt_distance_km: float = 0.7,
    capacity_mbq_per_day: float | None = None,
    planned_upstream_mbq_per_day: float | None = None,
    fixed_upstream_mbq_per_day: float | None = None,
    radionuclide: str = "F-18",
    patients_per_day: float = 30.0,
    prescribed_mbq_per_patient: float = 370.0,
    on_site_cyclotron_units: int = 0,
    revenue_per_scan: float | None = 2000.0,
) -> ExternalSupplyScenario:
    existing_map = {
        "scanners": 0.0,
        "radiopharmacy_units": 0.0,
        "injection_resources": 0.0,
        "uptake_resources": 0.0,
        "cyclotron_units": float(on_site_cyclotron_units),
    }
    existing_status = {
        "scanners": "KNOWN",
        "radiopharmacy_units": "KNOWN",
        "injection_resources": "KNOWN",
        "uptake_resources": "KNOWN",
        "cyclotron_units": "KNOWN",
    }
    if project_mode == "EXISTING_FACILITY_EXPANSION":
        existing_map.update(
            {
                "scanners": 2.0,
                "radiopharmacy_units": 1.0,
                "injection_resources": 2.0,
                "uptake_resources": 3.0,
            }
        )
    return ExternalSupplyScenario(
        scenario_id="EXT-SYNTH-001",
        project_mode=project_mode,
        project_supply_mode="EXTERNAL_SUPPLY",
        radionuclide=radionuclide,
        patients_per_day=patients_per_day,
        prescribed_activity_mbq_per_patient=prescribed_mbq_per_patient,
        source=_source(),
        common_prefix_segments=_common_segments(),
        conventional_last_mile_segment=_last_mile_conventional(
            minutes=conventional_minutes,
            handling_minutes=conventional_handling_minutes,
            distance_km=conventional_distance_km,
        ),
        mrt_last_mile_segment=_last_mile_mrt(
            minutes=mrt_minutes,
            handling_minutes=mrt_handling_minutes,
            distance_km=mrt_distance_km,
        ),
        receiving_workflow=_workflow(on_site_cyclotron_units=on_site_cyclotron_units),
        explicit_upstream_release_capacity_mbq_per_day=capacity_mbq_per_day,
        planned_upstream_release_activity_mbq_per_day=planned_upstream_mbq_per_day,
        fixed_upstream_release_activity_mbq_per_day=fixed_upstream_mbq_per_day,
        revenue_per_scan=revenue_per_scan,
        operating_days_per_year=300,
        resource_existing_quantities=existing_map,
        resource_existing_statuses=existing_status,
        resource_final_required_quantities={
            "scanners": 2.0,
            "radiopharmacy_units": 1.0,
            "injection_resources": 2.0,
            "uptake_resources": 3.0,
            "cyclotron_units": float(on_site_cyclotron_units),
        },
        economics=ExternalSupplyEconomicInputs(
            external_product_supply_cost_per_year=1_400_000.0,
            air_transport_cost_per_year=240_000.0,
            airport_handling_cost_per_year=120_000.0,
            conventional_last_mile_cost_per_year=90_000.0,
            mrt_last_mile_incremental_capex=800_000.0,
            mrt_last_mile_opex_per_year=70_000.0,
            receiving_infrastructure_incremental_capex=500_000.0,
            discount_rate_pct=10.0,
            analysis_years=10,
        ),
        assumptions=(
            "SYNTHETIC DEMONSTRATION ASSUMPTION: all durations are explicit engineering placeholders.",
            "SYNTHETIC DEMONSTRATION ASSUMPTION: destination airport-to-hospital distance is 0.7 km.",
        ),
    )


def _retrofit_request() -> ExistingFacilityRetrofitRequest:
    baseline = ExistingFacilityBaseline(
        metadata=ExistingFacilityMetadata(
            facility_id="SYNTH-RETROFIT-EXT-001",
            facility_name="Synthetic External Supply Retrofit",
            location="SYNTH-LOCATION",
            baseline_year=2026,
            provenance_reference_ids=("retrofit-source-1",),
        ),
        current_patients_per_day=120.0,
        resources={
            "scanners": ExistingFacilityResourceFact(resource="scanners", existing_quantity=2.0, operational_quantity=2.0, knowledge_status="KNOWN"),
            "injection_resources": ExistingFacilityResourceFact(resource="injection_resources", existing_quantity=2.0, operational_quantity=2.0, knowledge_status="KNOWN"),
            "uptake_resources": ExistingFacilityResourceFact(resource="uptake_resources", existing_quantity=6.0, operational_quantity=6.0, knowledge_status="KNOWN"),
            "distribution_concurrency": ExistingFacilityResourceFact(resource="distribution_concurrency", existing_quantity=1.0, operational_quantity=1.0, knowledge_status="KNOWN"),
            "cyclotron_units": ExistingFacilityResourceFact(resource="cyclotron_units", existing_quantity=1.0, operational_quantity=1.0, knowledge_status="KNOWN"),
            "radiopharmacy_units": ExistingFacilityResourceFact(resource="radiopharmacy_units", existing_quantity=1.0, operational_quantity=1.0, knowledge_status="KNOWN"),
            "mrt_base_infrastructure_units": ExistingFacilityResourceFact(resource="mrt_base_infrastructure_units", existing_quantity=0.0, operational_quantity=0.0, knowledge_status="KNOWN"),
            "mrt_endpoints": ExistingFacilityResourceFact(resource="mrt_endpoints", existing_quantity=0.0, operational_quantity=0.0, knowledge_status="KNOWN"),
            "guideway_length_m": ExistingFacilityResourceFact(resource="guideway_length_m", existing_quantity=0.0, operational_quantity=0.0, knowledge_status="KNOWN"),
            "vertical_transitions": ExistingFacilityResourceFact(resource="vertical_transitions", existing_quantity=0.0, operational_quantity=0.0, knowledge_status="KNOWN"),
            "building_connections": ExistingFacilityResourceFact(resource="building_connections", existing_quantity=0.0, operational_quantity=0.0, knowledge_status="KNOWN"),
        },
    )
    return ExistingFacilityRetrofitRequest(
        project_mode="EXISTING_FACILITY_EXPANSION",
        baseline=baseline,
        target_patients_per_day=220,
        pipeline_template=decision_request(seed=20260813),
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
            installed_mrt_endpoints=(0, 2, 4),
            transport_minutes=(5.0,),
        ),
        minimum_reliability=0.8,
        seeds=(20260813, 20260814),
        max_candidate_count=256,
        throughput_thresholds_per_day=(120.0, 220.0),
        worst_run_count=2,
    )


def test_zero_elapsed_transport_produces_zero_transport_decay():
    scenario = _scenario(conventional_minutes=0.0, mrt_minutes=0.0)
    scenario = replace(
        scenario,
        common_prefix_segments=tuple(
            replace(segment, duration_minutes=0.0, handling_minutes=0.0)
            for segment in scenario.common_prefix_segments
        ),
        conventional_last_mile_segment=replace(scenario.conventional_last_mile_segment, handling_minutes=0.0),
        mrt_last_mile_segment=replace(scenario.mrt_last_mile_segment, handling_minutes=0.0),
    )
    report = run_external_supply_hub_spoke(scenario)

    assert report.conventional.total_external_decay_loss_mbq == pytest.approx(0.0)
    assert report.mrt.total_external_decay_loss_mbq == pytest.approx(0.0)


def test_longer_elapsed_time_produces_lower_retained_activity():
    fast = run_external_supply_hub_spoke(_scenario(conventional_minutes=5.0, mrt_minutes=5.0))
    slow = run_external_supply_hub_spoke(_scenario(conventional_minutes=35.0, mrt_minutes=35.0))

    assert slow.conventional.total_external_retained_fraction < fast.conventional.total_external_retained_fraction


def test_identical_elapsed_time_yields_identical_decay_for_mrt_and_conventional():
    scenario = _scenario(conventional_minutes=12.0, mrt_minutes=12.0)
    scenario = replace(
        scenario,
        conventional_last_mile_segment=_last_mile_conventional(minutes=12.0, handling_minutes=3.0),
        mrt_last_mile_segment=_last_mile_mrt(minutes=12.0, handling_minutes=3.0),
    )
    report = run_external_supply_hub_spoke(scenario)

    assert report.conventional.total_external_elapsed_minutes == pytest.approx(report.mrt.total_external_elapsed_minutes)
    assert report.conventional.total_external_retained_fraction == pytest.approx(report.mrt.total_external_retained_fraction)


def test_shorter_mrt_elapsed_time_preserves_more_activity_than_conventional():
    report = run_external_supply_hub_spoke(_scenario(conventional_minutes=20.0, mrt_minutes=4.0))

    assert report.mrt.total_external_retained_fraction > report.conventional.total_external_retained_fraction
    assert report.mrt.required_upstream_activity_mbq_per_day < report.conventional.required_upstream_activity_mbq_per_day


def test_distance_alone_has_no_decay_advantage_when_duration_is_equal():
    scenario = _scenario(
        conventional_minutes=10.0,
        mrt_minutes=10.0,
        conventional_distance_km=5.0,
        mrt_distance_km=0.7,
    )
    scenario = replace(
        scenario,
        conventional_last_mile_segment=_last_mile_conventional(minutes=10.0, handling_minutes=4.0, distance_km=5.0),
        mrt_last_mile_segment=_last_mile_mrt(minutes=10.0, handling_minutes=4.0, distance_km=0.7),
    )
    report = run_external_supply_hub_spoke(scenario)

    assert report.mrt.total_external_retained_fraction == pytest.approx(report.conventional.total_external_retained_fraction)


def test_chain_retained_fraction_matches_segment_product():
    report = run_external_supply_hub_spoke(_scenario())

    for pathway in (report.conventional, report.mrt):
        product = 1.0
        for row in pathway.transport_rows:
            if row.retained_fraction is not None:
                product *= row.retained_fraction
        assert pathway.total_external_retained_fraction == pytest.approx(product)


def test_total_external_decay_loss_reconciles_with_activity_difference():
    report = run_external_supply_hub_spoke(_scenario())

    for pathway in (report.conventional, report.mrt):
        assert pathway.total_external_decay_loss_mbq == pytest.approx(
            pathway.activity_at_source_release_mbq_per_day - pathway.activity_at_hospital_receipt_mbq_per_day
        )


def test_required_upstream_activity_increases_with_total_elapsed_time():
    short = run_external_supply_hub_spoke(_scenario(conventional_minutes=5.0, mrt_minutes=5.0))
    long = run_external_supply_hub_spoke(_scenario(conventional_minutes=25.0, mrt_minutes=25.0))

    assert long.conventional.required_upstream_activity_mbq_per_day > short.conventional.required_upstream_activity_mbq_per_day


def test_patient_count_and_mbq_are_kept_as_distinct_quantities():
    report = run_external_supply_hub_spoke(_scenario(patients_per_day=30.0, prescribed_mbq_per_patient=350.0))

    expected = 30.0 * 350.0
    assert report.total_prescribed_activity_mbq_per_day == pytest.approx(expected)
    assert report.conventional.patients_per_day == pytest.approx(30.0)


def test_extra_supplied_mbq_without_additional_patients_does_not_create_extra_revenue():
    base = run_external_supply_hub_spoke(_scenario(capacity_mbq_per_day=1_000_000.0, planned_upstream_mbq_per_day=None))
    extra = run_external_supply_hub_spoke(_scenario(capacity_mbq_per_day=1_000_000.0, planned_upstream_mbq_per_day=2_000_000.0))

    assert extra.mrt.activity_at_source_release_mbq_per_day > base.mrt.activity_at_source_release_mbq_per_day
    assert extra.mrt.economics.annual_revenue == pytest.approx(base.mrt.economics.annual_revenue)


def test_unsupported_radionuclide_is_explicit():
    report = run_external_supply_hub_spoke(_scenario(radionuclide="Tc-99m"))

    assert report.conventional.external_supply_feasibility_status == "UNSUPPORTED_RADIONUCLIDE"
    assert report.mrt.external_supply_feasibility_status == "UNSUPPORTED_RADIONUCLIDE"


def test_missing_transport_duration_is_explicit_not_calibrated():
    scenario = _scenario()
    broken_common = list(scenario.common_prefix_segments)
    broken_common[1] = replace(broken_common[1], duration_minutes=None)
    report = run_external_supply_hub_spoke(replace(scenario, common_prefix_segments=tuple(broken_common)))

    assert report.conventional.external_supply_feasibility_status == "TRANSPORT_TIME_NOT_CALIBRATED"
    assert report.mrt.external_supply_feasibility_status == "TRANSPORT_TIME_NOT_CALIBRATED"


def test_missing_upstream_capacity_is_not_calibrated_but_required_activity_is_reported():
    report = run_external_supply_hub_spoke(_scenario(capacity_mbq_per_day=None))

    assert report.conventional.external_supply_feasibility_status == "SUPPLY_CAPACITY_NOT_CALIBRATED"
    assert report.conventional.required_upstream_activity_mbq_per_day is not None
    assert report.conventional.upstream_capacity_status == "NOT_CALIBRATED"


def test_explicit_upstream_capacity_is_not_inflated():
    report = run_external_supply_hub_spoke(_scenario(capacity_mbq_per_day=2_000_000.0))

    assert report.conventional.activity_at_source_release_mbq_per_day == pytest.approx(
        report.conventional.required_upstream_activity_mbq_per_day
    )


def test_required_activity_greater_than_capacity_produces_shortfall():
    report = run_external_supply_hub_spoke(_scenario(capacity_mbq_per_day=8_000.0))

    assert report.conventional.external_supply_feasibility_status == "INSUFFICIENT_UPSTREAM_ACTIVITY"
    assert report.conventional.operational_state == "CAPACITY_SHORTFALL"


def test_existing_on_site_production_pipeline_behavior_remains_unchanged():
    req = decision_request(seed=20260813)
    before = run_native_decision_pipeline(req)

    run_external_supply_hub_spoke(_scenario())

    after = run_native_decision_pipeline(req)
    assert before == after


def test_external_supply_does_not_require_on_site_cyclotron():
    report = run_external_supply_hub_spoke(_scenario(on_site_cyclotron_units=0, capacity_mbq_per_day=1_000_000.0))

    assert report.receiving_workflow.on_site_cyclotron_units == 0
    assert report.conventional.external_supply_feasibility_status in {"FEASIBLE", "SUPPLY_CAPACITY_NOT_CALIBRATED"}


def test_receiving_hospital_resources_remain_in_model():
    report = run_external_supply_hub_spoke(_scenario())

    assert report.receiving_workflow.receiving_radiopharmacy_units == 1
    assert report.receiving_workflow.injection_resources == 2
    assert report.receiving_workflow.uptake_resources == 3
    assert report.receiving_workflow.scanners == 2


def test_external_supply_can_coexist_with_retrofit_semantics():
    retrofit = run_native_existing_facility_retrofit(_retrofit_request())
    workflow = build_receiving_workflow_from_retrofit_resource_facts(
        retrofit.baseline.resources,
        conventional_internal_distribution_minutes=18.0,
        mrt_internal_distribution_minutes=6.0,
        administration_minutes=12.0,
    )
    report = run_external_supply_hub_spoke(
        replace(
            _scenario(project_mode="EXISTING_FACILITY_EXPANSION", capacity_mbq_per_day=1_000_000.0),
            receiving_workflow=workflow,
            resource_existing_quantities={
                "scanners": 2.0,
                "radiopharmacy_units": 1.0,
                "injection_resources": 2.0,
                "uptake_resources": 6.0,
                "cyclotron_units": 1.0,
            },
            resource_existing_statuses={
                "scanners": "KNOWN",
                "radiopharmacy_units": "KNOWN",
                "injection_resources": "KNOWN",
                "uptake_resources": "KNOWN",
                "cyclotron_units": "KNOWN",
            },
        )
    )

    assert report.receiving_workflow.scanners >= 2
    assert report.receiving_workflow.injection_resources >= 2
    assert report.receiving_workflow.uptake_resources >= 6


def test_retained_existing_resources_are_not_repurchased_by_external_supply_model():
    retrofit = run_native_existing_facility_retrofit(_retrofit_request())
    workflow = build_receiving_workflow_from_retrofit_resource_facts(
        retrofit.baseline.resources,
        conventional_internal_distribution_minutes=18.0,
        mrt_internal_distribution_minutes=6.0,
        administration_minutes=12.0,
    )
    scenario = replace(
        _scenario(project_mode="EXISTING_FACILITY_EXPANSION", capacity_mbq_per_day=1_000_000.0),
        receiving_workflow=workflow,
        resource_existing_quantities={
            "scanners": 2.0,
            "radiopharmacy_units": 1.0,
            "injection_resources": 2.0,
            "uptake_resources": 6.0,
            "cyclotron_units": 1.0,
        },
        resource_existing_statuses={
            "scanners": "KNOWN",
            "radiopharmacy_units": "KNOWN",
            "injection_resources": "KNOWN",
            "uptake_resources": "KNOWN",
            "cyclotron_units": "KNOWN",
        },
        economics=ExternalSupplyEconomicInputs(
            external_product_supply_cost_per_year=1_400_000.0,
            air_transport_cost_per_year=240_000.0,
            airport_handling_cost_per_year=120_000.0,
            conventional_last_mile_cost_per_year=90_000.0,
            mrt_last_mile_incremental_capex=800_000.0,
            mrt_last_mile_opex_per_year=70_000.0,
            receiving_infrastructure_incremental_capex=250_000.0,
            discount_rate_pct=10.0,
            analysis_years=10,
        ),
    )
    report = run_external_supply_hub_spoke(scenario)

    assert report.conventional.economics.incremental_capex == pytest.approx(250_000.0)


def test_external_supply_is_usable_for_greenfield():
    workflow = build_receiving_workflow_from_retrofit_resource_facts(
        {
            "scanners": 0,
            "injection_resources": 0,
            "uptake_resources": 0,
            "radiopharmacy_units": 0,
            "cyclotron_units": 0,
        },
        conventional_internal_distribution_minutes=18.0,
        mrt_internal_distribution_minutes=6.0,
        administration_minutes=12.0,
    )
    scenario = replace(_scenario(capacity_mbq_per_day=1_000_000.0), receiving_workflow=workflow)
    report = run_external_supply_hub_spoke(scenario)

    assert report.project_supply_mode == "EXTERNAL_SUPPLY"
    assert report.conventional.external_supply_feasibility_status == "FEASIBLE"


def test_report_rows_reconcile_to_native_chain_results():
    report = run_external_supply_hub_spoke(_scenario())

    for pathway in (report.conventional, report.mrt):
        sum_elapsed = sum(row.elapsed_segment_minutes for row in pathway.transport_rows if row.elapsed_segment_minutes is not None)
        assert pathway.total_external_elapsed_minutes == pytest.approx(sum_elapsed)


def test_common_prefix_is_identical_for_conventional_and_mrt_branches():
    report = run_external_supply_hub_spoke(_scenario())

    n = len(report.common_prefix_segment_ids)
    conv_prefix = report.conventional.transport_rows[:n]
    mrt_prefix = report.mrt.transport_rows[:n]

    assert [row.segment_id for row in conv_prefix] == [row.segment_id for row in mrt_prefix]
    assert [row.elapsed_segment_minutes for row in conv_prefix] == pytest.approx(
        [row.elapsed_segment_minutes for row in mrt_prefix]
    )
    assert [row.retained_fraction for row in conv_prefix] == pytest.approx(
        [row.retained_fraction for row in mrt_prefix]
    )


def test_conventional_and_mrt_rejoin_same_downstream_patient_requirement():
    report = run_external_supply_hub_spoke(_scenario())

    assert report.conventional.total_prescribed_activity_mbq_per_day == pytest.approx(
        report.mrt.total_prescribed_activity_mbq_per_day
    )


def test_revenue_tracks_effective_patients_not_shipped_activity():
    report = run_external_supply_hub_spoke(_scenario(capacity_mbq_per_day=8_000.0))

    if report.conventional.effective_patients_per_day is not None:
        expected = report.conventional.effective_patients_per_day * 2000.0 * 300
        assert report.conventional.economics.annual_revenue == pytest.approx(expected)


def test_700m_mrt_demo_leg_is_explicit_in_fixture():
    report = run_external_supply_hub_spoke(_scenario())

    mrt_last = report.mrt.transport_rows[-1]
    assert mrt_last.distance_km == pytest.approx(0.7)
    assert mrt_last.designation == "MRT_LAST_MILE"


def test_trace_ids_are_present_for_report_and_pathways():
    report = run_external_supply_hub_spoke(_scenario())

    assert isinstance(report.trace_id, str) and len(report.trace_id) == 16
    assert isinstance(report.conventional.trace_id, str) and len(report.conventional.trace_id) == 16
    assert isinstance(report.mrt.trace_id, str) and len(report.mrt.trace_id) == 16


def test_pathway_state_labels_are_aligned_with_feasibility_status():
    feasible = run_external_supply_hub_spoke(_scenario(capacity_mbq_per_day=1_000_000.0))
    shortfall = run_external_supply_hub_spoke(_scenario(capacity_mbq_per_day=4_000.0))
    not_calibrated = run_external_supply_hub_spoke(_scenario(capacity_mbq_per_day=None))

    assert feasible.conventional.operational_state == "PHYSICALLY_FEASIBLE"
    assert shortfall.conventional.operational_state == "CAPACITY_SHORTFALL"
    assert not_calibrated.conventional.operational_state == "CAPACITY_NOT_CALIBRATED"


def test_project_mode_and_supply_architecture_are_orthogonal_dimensions():
    greenfield_external = run_external_supply_hub_spoke(
        _scenario(project_mode="GREENFIELD", capacity_mbq_per_day=1_000_000.0)
    )
    retrofit_external = run_external_supply_hub_spoke(
        _scenario(project_mode="EXISTING_FACILITY_EXPANSION", capacity_mbq_per_day=1_000_000.0)
    )

    assert greenfield_external.project_mode == "GREENFIELD"
    assert retrofit_external.project_mode == "EXISTING_FACILITY_EXPANSION"
    assert greenfield_external.project_supply_mode == "EXTERNAL_SUPPLY"
    assert retrofit_external.project_supply_mode == "EXTERNAL_SUPPLY"


def test_retrofit_external_supply_with_known_zero_cyclotrons_is_valid_and_not_auto_purchased():
    scenario = _scenario(
        project_mode="EXISTING_FACILITY_EXPANSION",
        on_site_cyclotron_units=0,
        capacity_mbq_per_day=1_000_000.0,
    )
    scenario = replace(
        scenario,
        resource_existing_quantities={
            "scanners": 2.0,
            "radiopharmacy_units": 1.0,
            "injection_resources": 2.0,
            "uptake_resources": 3.0,
            "cyclotron_units": 0.0,
        },
        resource_existing_statuses={
            "scanners": "KNOWN",
            "radiopharmacy_units": "KNOWN",
            "injection_resources": "KNOWN",
            "uptake_resources": "KNOWN",
            "cyclotron_units": "KNOWN",
        },
        resource_final_required_quantities={
            "scanners": 2.0,
            "radiopharmacy_units": 1.0,
            "injection_resources": 2.0,
            "uptake_resources": 3.0,
            "cyclotron_units": 0.0,
        },
    )
    report = run_external_supply_hub_spoke(scenario)

    assert report.conventional.external_supply_feasibility_status == "FEASIBLE"
    cyclotron_row = next(row for row in report.resource_delta_rows if row.resource == "cyclotron_units")
    assert cyclotron_row.existing_quantity_status == "KNOWN"
    assert cyclotron_row.existing_quantity == pytest.approx(0.0)
    assert cyclotron_row.additional_required_quantity == pytest.approx(0.0)


def test_retrofit_external_supply_with_existing_cyclotron_preserves_asset_without_duplicate_purchase():
    scenario = _scenario(
        project_mode="EXISTING_FACILITY_EXPANSION",
        on_site_cyclotron_units=1,
        capacity_mbq_per_day=1_000_000.0,
    )
    scenario = replace(
        scenario,
        resource_existing_quantities={
            "scanners": 2.0,
            "radiopharmacy_units": 1.0,
            "injection_resources": 2.0,
            "uptake_resources": 3.0,
            "cyclotron_units": 1.0,
        },
        resource_existing_statuses={
            "scanners": "KNOWN",
            "radiopharmacy_units": "KNOWN",
            "injection_resources": "KNOWN",
            "uptake_resources": "KNOWN",
            "cyclotron_units": "KNOWN",
        },
        resource_final_required_quantities={
            "scanners": 2.0,
            "radiopharmacy_units": 1.0,
            "injection_resources": 2.0,
            "uptake_resources": 3.0,
            "cyclotron_units": 1.0,
        },
    )
    report = run_external_supply_hub_spoke(scenario)

    cyclotron_row = next(row for row in report.resource_delta_rows if row.resource == "cyclotron_units")
    assert cyclotron_row.existing_quantity == pytest.approx(1.0)
    assert cyclotron_row.additional_required_quantity == pytest.approx(0.0)


def test_greenfield_external_supply_zero_cyclotron_is_valid_architecture():
    report = run_external_supply_hub_spoke(
        _scenario(project_mode="GREENFIELD", on_site_cyclotron_units=0, capacity_mbq_per_day=1_000_000.0)
    )

    assert report.conventional.external_supply_feasibility_status == "FEASIBLE"
    cyclotron_row = next(row for row in report.resource_delta_rows if row.resource == "cyclotron_units")
    assert cyclotron_row.existing_quantity == pytest.approx(0.0)


def test_known_zero_vs_unknown_cyclotron_inventory_status_is_preserved():
    known_zero = run_external_supply_hub_spoke(
        _scenario(project_mode="EXISTING_FACILITY_EXPANSION", on_site_cyclotron_units=0, capacity_mbq_per_day=1_000_000.0)
    )
    unknown_inventory = run_external_supply_hub_spoke(
        replace(
            _scenario(project_mode="EXISTING_FACILITY_EXPANSION", on_site_cyclotron_units=0, capacity_mbq_per_day=1_000_000.0),
            resource_existing_statuses={"cyclotron_units": "UNKNOWN"},
            receiving_workflow=replace(_workflow(on_site_cyclotron_units=0), on_site_cyclotron_inventory_status="UNKNOWN"),
        )
    )

    known_row = next(row for row in known_zero.resource_delta_rows if row.resource == "cyclotron_units")
    unknown_row = next(row for row in unknown_inventory.resource_delta_rows if row.resource == "cyclotron_units")
    assert known_row.existing_quantity_status == "KNOWN"
    assert unknown_row.existing_quantity_status == "UNKNOWN"
    assert unknown_row.additional_required_quantity is None


def test_equal_external_speed_and_handling_yields_equal_external_retention():
    report = run_external_supply_hub_spoke(
        _scenario(
            conventional_minutes=10.0,
            mrt_minutes=10.0,
            conventional_handling_minutes=4.0,
            mrt_handling_minutes=4.0,
            conventional_distance_km=0.7,
            mrt_distance_km=0.7,
        )
    )

    assert report.conventional.total_external_retained_fraction == pytest.approx(
        report.mrt.total_external_retained_fraction
    )


def test_requirement_derived_mbq_preserved_metric_is_not_reported_as_benefit():
    report = run_external_supply_hub_spoke(_scenario(conventional_minutes=18.0, mrt_minutes=6.0))

    assert report.difference_mbq_preserved_at_hospital_receipt_mrt_vs_conventional is None
    assert report.difference_required_upstream_mbq_avoided_mrt_vs_conventional is not None


def test_fixed_source_comparison_reports_mbq_preserved_at_receipt():
    report = run_external_supply_hub_spoke(
        _scenario(
            conventional_minutes=18.0,
            mrt_minutes=6.0,
            fixed_upstream_mbq_per_day=30_000.0,
        )
    )

    assert report.fixed_source_upstream_release_mbq_per_day == pytest.approx(30_000.0)
    assert report.fixed_source_mbq_preserved_at_hospital_receipt_mrt_vs_conventional is not None
    assert report.fixed_source_supported_patient_capacity_mrt is not None
    assert report.fixed_source_supported_patient_capacity_conventional is not None
    assert report.fixed_source_actual_effective_patients_served_mrt is not None
    assert report.fixed_source_actual_effective_patients_served_conventional is not None


def test_near_zero_differences_are_normalized_to_zero():
    report = run_external_supply_hub_spoke(_scenario())
    assert report.difference_minutes_saved_mrt_vs_conventional == pytest.approx(0.0)


def test_revenue_per_scan_default_and_override_provenance_are_exposed():
    default_case = run_external_supply_hub_spoke(_scenario(revenue_per_scan=None))
    override_case = run_external_supply_hub_spoke(_scenario(revenue_per_scan=300.0))

    assert default_case.revenue_per_scan_provenance.value == pytest.approx(2000.0)
    assert default_case.revenue_per_scan_provenance.value_status == "DEFAULT_MODEL_VALUE"
    assert override_case.revenue_per_scan_provenance.value == pytest.approx(300.0)
    assert override_case.revenue_per_scan_provenance.value_status == "USER_OVERRIDE"


def test_revenue_override_changes_economics_not_physics():
    case_a = run_external_supply_hub_spoke(_scenario(capacity_mbq_per_day=1_000_000.0, revenue_per_scan=2000.0))
    case_b = run_external_supply_hub_spoke(_scenario(capacity_mbq_per_day=1_000_000.0, revenue_per_scan=300.0))

    assert case_a.conventional.total_external_elapsed_minutes == pytest.approx(case_b.conventional.total_external_elapsed_minutes)
    assert case_a.conventional.required_upstream_activity_mbq_per_day == pytest.approx(case_b.conventional.required_upstream_activity_mbq_per_day)
    assert case_a.conventional.activity_at_hospital_receipt_mbq_per_day == pytest.approx(case_b.conventional.activity_at_hospital_receipt_mbq_per_day)
    assert case_a.conventional.economics.annual_revenue != case_b.conventional.economics.annual_revenue


def test_fixed_source_capacity_vs_actual_served_for_30_patient_fixture():
    report = run_external_supply_hub_spoke(
        _scenario(
            conventional_minutes=10.0,
            mrt_minutes=10.0,
            conventional_handling_minutes=5.0,
            mrt_handling_minutes=5.0,
            fixed_upstream_mbq_per_day=30_000.0,
            patients_per_day=30.0,
        )
    )

    assert report.fixed_source_supported_patient_capacity_conventional == pytest.approx(32.46268761637582)
    assert report.fixed_source_supported_patient_capacity_mrt == pytest.approx(35.017402306438754)
    assert report.fixed_source_actual_effective_patients_served_conventional <= 30.0
    assert report.fixed_source_actual_effective_patients_served_mrt <= 30.0
    assert report.fixed_source_actual_effective_patients_served_conventional == pytest.approx(30.0)
    assert report.fixed_source_actual_effective_patients_served_mrt == pytest.approx(30.0)


def test_fixed_source_high_demand_makes_capacity_binding_and_distinction_operational():
    report = run_external_supply_hub_spoke(
        _scenario(
            conventional_minutes=10.0,
            mrt_minutes=10.0,
            conventional_handling_minutes=5.0,
            mrt_handling_minutes=5.0,
            fixed_upstream_mbq_per_day=30_000.0,
            patients_per_day=40.0,
        )
    )

    assert report.fixed_source_supported_patient_capacity_conventional < 40.0
    assert report.fixed_source_supported_patient_capacity_mrt < 40.0
    assert report.fixed_source_actual_effective_patients_served_conventional == pytest.approx(
        report.fixed_source_supported_patient_capacity_conventional
    )
    assert report.fixed_source_actual_effective_patients_served_mrt == pytest.approx(
        report.fixed_source_supported_patient_capacity_mrt
    )

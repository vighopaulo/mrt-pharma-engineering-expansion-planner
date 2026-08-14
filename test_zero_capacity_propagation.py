from __future__ import annotations

import math
from dataclasses import replace

import pytest

from architecture_recommendation import (
    ArchitectureRecommendationRequest,
    ConventionalArchitectureBounds,
    MrtArchitectureBounds,
    run_native_architecture_recommendation,
)
from architecture_report import build_native_design_horizon_report_data
from cyclotron_production_windows import CyclotronAsset, CyclotronFleet, CyclotronProductionCapability
from decision_pipeline import run_native_decision_pipeline
from design_horizon_planning import DesignHorizonPlanningRequest, run_native_design_horizon_planning
from stochastic_design_day import ActivityDemandModel
from test_decision_pipeline import _request as baseline_request


def _capability(cyclotron_id: str, supported: tuple[str, ...], cycles: dict[str, float]) -> CyclotronProductionCapability:
    compatible_sets = (frozenset(("F-18", "Ga-68")),) if {"F-18", "Ga-68"}.issubset(set(supported)) else ()
    return CyclotronProductionCapability(
        cyclotron_id=cyclotron_id,
        supported_radionuclides=supported,
        max_simultaneous_production_streams=2,
        production_cycle_minutes_by_radionuclide=cycles,
        simultaneously_compatible_radionuclide_sets=compatible_sets,
    )


def _asset(cyclotron_id: str, model_id: str, supported: tuple[str, ...], cycles: dict[str, float]) -> CyclotronAsset:
    return CyclotronAsset(
        cyclotron_id=cyclotron_id,
        capability=_capability(cyclotron_id, supported, cycles),
        manufacturer="StressDemo",
        model_identifier=model_id,
        capability_provenance=model_id,
    )


def _fleet_with_optional_c11() -> CyclotronFleet:
    return CyclotronFleet(
        fleet_id="FLEET-ABC",
        assets=(
            _asset("CY-A1", "A", ("F-18", "Ga-68"), {"F-18": 30.0, "Ga-68": 20.0}),
            _asset("CY-B1", "B", ("N-13", "O-15"), {"N-13": 15.0, "O-15": 12.0}),
            _asset("CY-C1", "C", ("C-11",), {"C-11": 18.0}),
        ),
    )


def _extended_activity_models() -> dict[str, ActivityDemandModel]:
    return {
        "F-18": ActivityDemandModel("bounded_normal", mean_activity_mbq=200.0, stddev_activity_mbq=20.0, lower_bound_mbq=160.0, upper_bound_mbq=240.0),
        "Ga-68": ActivityDemandModel("bounded_normal", mean_activity_mbq=150.0, stddev_activity_mbq=15.0, lower_bound_mbq=120.0, upper_bound_mbq=180.0),
        "N-13": ActivityDemandModel("bounded_normal", mean_activity_mbq=180.0, stddev_activity_mbq=10.0, lower_bound_mbq=150.0, upper_bound_mbq=210.0),
        "O-15": ActivityDemandModel("bounded_normal", mean_activity_mbq=160.0, stddev_activity_mbq=8.0, lower_bound_mbq=140.0, upper_bound_mbq=180.0),
        "C-11": ActivityDemandModel("bounded_normal", mean_activity_mbq=220.0, stddev_activity_mbq=12.0, lower_bound_mbq=190.0, upper_bound_mbq=250.0),
    }


def _stressed_request(*, target_patients_per_day: int, transport_minutes: float, max_compensation_factor: float):
    base = baseline_request(seed=20260813)
    fleet = _fleet_with_optional_c11()
    planner_assumptions = replace(
        base.planner_assumptions,
        decay_feasibility_max_compensation_factor=max_compensation_factor,
    )
    return replace(
        base,
        target_patients_per_day=target_patients_per_day,
        radionuclide_mix={"F-18": 0.40, "Ga-68": 0.22, "N-13": 0.18, "O-15": 0.15, "C-11": 0.05},
        activity_distribution_by_radionuclide=_extended_activity_models(),
        cyclotron_fleet=fleet,
        cyclotron_capability=fleet.assets[0].capability,
        planner_assumptions=planner_assumptions,
        conventional=replace(base.conventional, transport_minutes=transport_minutes, cyclotron_annual_opex_per_unit=420_000.0),
        mrt=replace(base.mrt, transport_minutes=transport_minutes, cyclotron_annual_opex_per_unit=420_000.0),
    )


def _fixed_architecture_request(template):
    return ArchitectureRecommendationRequest(
        target_patients_per_day=template.target_patients_per_day,
        minimum_reliability=0.95,
        seeds=(20260813,),
        pipeline_template=template,
        conventional_bounds=ConventionalArchitectureBounds(
            scanners=(template.conventional.scanners,),
            injection_resources=(template.conventional.injection_resources,),
            uptake_resources=(template.conventional.uptake_resources,),
            distribution_concurrency=(template.conventional.distribution_concurrency,),
            transport_minutes=(template.conventional.transport_minutes,),
        ),
        mrt_bounds=MrtArchitectureBounds(
            scanners=(template.mrt.scanners,),
            injection_resources=(template.mrt.injection_resources,),
            uptake_resources=(template.mrt.uptake_resources,),
            distribution_concurrency=(template.mrt.distribution_concurrency,),
            installed_mrt_endpoints=(template.mrt.installed_mrt_endpoints,),
            transport_minutes=(template.mrt.transport_minutes,),
        ),
        max_candidate_count=2,
        throughput_thresholds_per_day=(float(template.target_patients_per_day),),
    )


def test_zero_effective_throughput_propagates_without_crashing_and_preserves_costs():
    request = _stressed_request(target_patients_per_day=50, transport_minutes=120.0, max_compensation_factor=1.2)

    result = run_native_decision_pipeline(request)

    for pathway_result in (result.conventional, result.mrt):
        operational = pathway_result.operational_result
        assert operational.schedule_completed_patients > 0
        assert operational.decay_feasible_completed_patients == 0
        assert operational.decay_feasible_completed_patients <= operational.schedule_completed_patients
        assert pathway_result.actual_lifecycle_throughput_per_day == 0.0
        assert pathway_result.annual_revenue == pytest.approx(0.0)
        assert pathway_result.capex_result.total_capex > 0.0
        assert pathway_result.annual_opex > 0.0
        assert math.isfinite(pathway_result.lifecycle_result.final_npv)
        assert pathway_result.lifecycle_result.payback_year is None
        first_year = pathway_result.lifecycle_result.annual_rows[0]
        assert first_year.installed_capacity_per_day == pytest.approx(0.0)
        assert first_year.patients_served_per_day == pytest.approx(0.0)
        assert first_year.annual_revenue == pytest.approx(0.0)

    recommendation = run_native_architecture_recommendation(_fixed_architecture_request(request))
    assert recommendation.recommended_pathway == "NONE"
    assert recommendation.recommended_architecture is None
    assert recommendation.best_qualifying_conventional is None
    assert recommendation.best_qualifying_mrt is None
    assert recommendation.conventional_candidates[0].status == "REJECTED_RELIABILITY"
    assert recommendation.mrt_candidates[0].status == "REJECTED_RELIABILITY"


def test_partial_effective_throughput_keeps_raw_and_revenue_distinct_and_preserves_infeasible_patient_trace():
    request = _stressed_request(target_patients_per_day=50, transport_minutes=20.0, max_compensation_factor=1.3)

    result = run_native_decision_pipeline(request)
    mrt = result.mrt
    operational = mrt.operational_result

    assert operational.schedule_completed_patients > operational.decay_feasible_completed_patients > 0
    assert operational.decay_infeasible_patients > 0
    assert mrt.actual_lifecycle_throughput_per_day == pytest.approx(float(operational.decay_feasible_completed_patients))
    expected_revenue = (
        float(operational.decay_feasible_completed_patients)
        * float(request.planner_assumptions.operating_days_per_year)
        * float(request.planner_assumptions.revenue_per_scan)
    )
    assert mrt.annual_revenue == pytest.approx(expected_revenue)

    infeasible = next(trace for trace in mrt.decay_summary.patient_traces if not trace.decay_feasible)
    assert infeasible.completed_within_operating_day is True
    assert infeasible.activity_at_injection_mbq < infeasible.prescribed_activity_mbq
    assert infeasible.unmet_prescribed_activity_mbq > 0.0
    assert infeasible.retained_fraction_at_administration < (1.0 / 1.3)


def test_horizon_and_reporting_preserve_zero_capacity_years_and_continue_series():
    template = _stressed_request(target_patients_per_day=50, transport_minutes=120.0, max_compensation_factor=1.2)
    planning = run_native_design_horizon_planning(
        DesignHorizonPlanningRequest(
            pipeline_template=template,
            seeds=(20260813,),
            analysis_years=2,
            demand_mode="milestone",
            milestone_daily_demand_by_year={1: 50.0, 2: 55.0},
        )
    )
    report = build_native_design_horizon_report_data(planning)

    assert len(planning.year_results) == 2
    assert len(report.conventional_year_rows) == 2
    assert len(report.mrt_year_rows) == 2
    assert len(report.chart_series.conventional_capacity) == 2
    assert len(report.chart_series.mrt_capacity) == 2

    first_conventional = planning.year_results[0].conventional
    first_mrt = planning.year_results[0].mrt
    assert first_conventional.installed_capacity_per_day == pytest.approx(0.0)
    assert first_conventional.patients_served_per_day == pytest.approx(0.0)
    assert first_conventional.unmet_demand_per_day == pytest.approx(50.0)
    assert first_conventional.headroom_per_day == pytest.approx(-50.0)
    assert first_conventional.reliability_probability_meeting_target == pytest.approx(0.0)
    assert first_mrt.installed_capacity_per_day == pytest.approx(0.0)
    assert first_mrt.patients_served_per_day == pytest.approx(0.0)
    assert first_mrt.unmet_demand_per_day == pytest.approx(50.0)
    assert first_mrt.headroom_per_day == pytest.approx(-50.0)
    assert first_mrt.reliability_probability_meeting_target == pytest.approx(0.0)

    assert report.conventional_year_rows[0].installed_reliable_effective_capacity_patients_per_day == pytest.approx(0.0)
    assert report.conventional_year_rows[0].annual_revenue == pytest.approx(0.0)
    assert report.conventional_year_rows[0].headroom_per_day == pytest.approx(-50.0)
    assert report.mrt_year_rows[0].installed_reliable_effective_capacity_patients_per_day == pytest.approx(0.0)
    assert report.mrt_year_rows[0].annual_revenue == pytest.approx(0.0)
    assert report.mrt_year_rows[0].headroom_per_day == pytest.approx(-50.0)
    assert report.chart_series.conventional_capacity[0].y == pytest.approx(0.0)
    assert report.chart_series.mrt_capacity[0].y == pytest.approx(0.0)
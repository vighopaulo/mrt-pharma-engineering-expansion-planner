from __future__ import annotations

from dataclasses import replace

import pytest

from architecture_report import build_native_design_horizon_report_data
from design_horizon_planning import DesignHorizonPlanningRequest, run_native_design_horizon_planning
from test_decision_pipeline import _request as baseline_request


def _horizon_result():
    request = DesignHorizonPlanningRequest(
        pipeline_template=baseline_request(seed=20260813),
        seeds=tuple(range(20260813, 20260823)),
        analysis_years=10,
        demand_mode="milestone",
        milestone_daily_demand_by_year={1: 180.0, 3: 205.0, 5: 235.0, 7: 270.0, 10: 310.0},
    )
    return run_native_design_horizon_planning(request)


def test_demand_trajectory_and_pathway_rows_reconcile_exactly_to_native_horizon():
    result = _horizon_result()
    report = build_native_design_horizon_report_data(result)

    expected_demand = tuple(float(value) for value in result.demand_trajectory.daily_demand_by_year)
    actual_demand = tuple(row.demand_patients_per_day for row in report.demand_trajectory_rows)
    assert actual_demand == expected_demand

    assert len(report.conventional_year_rows) == len(result.year_results)
    assert len(report.mrt_year_rows) == len(result.year_results)

    for index, native_year in enumerate(result.year_results):
        conventional_row = report.conventional_year_rows[index]
        mrt_row = report.mrt_year_rows[index]

        assert conventional_row.year == native_year.year
        assert mrt_row.year == native_year.year
        assert conventional_row.installed_reliable_effective_capacity_patients_per_day == pytest.approx(native_year.conventional.installed_capacity_per_day)
        assert mrt_row.installed_reliable_effective_capacity_patients_per_day == pytest.approx(native_year.mrt.installed_capacity_per_day)
        assert conventional_row.headroom_per_day == pytest.approx(native_year.conventional.headroom_per_day)
        assert mrt_row.headroom_per_day == pytest.approx(native_year.mrt.headroom_per_day)
        assert conventional_row.probability_meeting_target_demand == pytest.approx(native_year.conventional.reliability_probability_meeting_target)
        assert mrt_row.probability_meeting_target_demand == pytest.approx(native_year.mrt.reliability_probability_meeting_target)
        assert conventional_row.binding_bottleneck_resource == native_year.conventional.binding_bottleneck_resource
        assert mrt_row.binding_bottleneck_resource == native_year.mrt.binding_bottleneck_resource
        assert conventional_row.annual_expansion_capex == pytest.approx(native_year.conventional.annual_capex)
        assert mrt_row.annual_expansion_capex == pytest.approx(native_year.mrt.annual_capex)


def test_combo_actions_stay_coherent_and_build_ahead_semantics_preserved():
    result = _horizon_result()
    report = build_native_design_horizon_report_data(result)

    combo_actions = [
        decision
        for decision in report.conventional_expansion_decisions + report.mrt_expansion_decisions
        if decision.action_type == "multi_resource_combo"
    ]
    assert combo_actions
    assert all(decision.action_identifier.startswith("combo(") for decision in combo_actions)
    assert all(len(decision.resources_changed) >= 2 for decision in combo_actions)

    conventional_strategy = report.strategy_comparison_by_pathway["Conventional"]
    mrt_strategy = report.strategy_comparison_by_pathway["MRT"]

    assert conventional_strategy.build_ahead_feasible is False
    assert mrt_strategy.build_ahead_feasible is True
    assert report.build_ahead_conventional.expansion_intervention_count == 0
    assert report.build_ahead_mrt.expansion_intervention_count == 0
    assert report.build_ahead_conventional.expansion_intervention_years == ()
    assert report.build_ahead_mrt.expansion_intervention_years == ()

    assert report.build_ahead_conventional.final_modeled_capacity < report.build_ahead_conventional.horizon_peak_demand
    assert report.build_ahead_mrt.final_modeled_capacity >= report.build_ahead_mrt.horizon_peak_demand

    assert conventional_strategy.preferred_strategy == result.strategy_comparison_by_pathway["Conventional"].preferred_strategy
    assert mrt_strategy.preferred_strategy == result.strategy_comparison_by_pathway["MRT"].preferred_strategy


def test_strategy_financials_carriers_chart_reconciliation_determinism_and_no_replanning(monkeypatch):
    result = _horizon_result()

    # Reporting contract must not trigger another planning simulation.
    monkeypatch.setattr(
        "architecture_report.run_native_design_horizon_planning",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("reporting must not call planner")),
        raising=False,
    )

    report_a = build_native_design_horizon_report_data(result)
    report_b = build_native_design_horizon_report_data(result)

    assert report_a == report_b

    assert report_a.phased_conventional.lifecycle_npv == pytest.approx(result.phased_strategy.conventional_lifecycle.final_npv)
    assert report_a.phased_mrt.lifecycle_npv == pytest.approx(result.phased_strategy.mrt_lifecycle.final_npv)
    assert report_a.phased_conventional.payback_year == result.phased_strategy.conventional_lifecycle.payback_year
    assert report_a.phased_mrt.payback_year == result.phased_strategy.mrt_lifecycle.payback_year

    native_conventional_years = tuple(year.year for year in result.year_results if year.conventional.expansion_actions)
    native_mrt_years = tuple(year.year for year in result.year_results if year.mrt.expansion_actions)
    assert report_a.phased_conventional.expansion_intervention_years == native_conventional_years
    assert report_a.phased_mrt.expansion_intervention_years == native_mrt_years

    final_native_conventional = result.year_results[-1].conventional
    final_native_mrt = result.year_results[-1].mrt
    assert report_a.final_comparison.conventional_final_capacity == pytest.approx(final_native_conventional.installed_capacity_per_day)
    assert report_a.final_comparison.mrt_final_capacity == pytest.approx(final_native_mrt.installed_capacity_per_day)

    assert len(report_a.chart_series.demand) == len(report_a.demand_trajectory_rows)
    assert len(report_a.chart_series.conventional_capacity) == len(report_a.conventional_year_rows)
    assert len(report_a.chart_series.mrt_capacity) == len(report_a.mrt_year_rows)
    assert report_a.chart_series.demand[0].y == pytest.approx(report_a.demand_trajectory_rows[0].demand_patients_per_day)
    assert report_a.chart_series.demand[-1].y == pytest.approx(report_a.demand_trajectory_rows[-1].demand_patients_per_day)
    assert report_a.chart_series.conventional_capacity[0].y == pytest.approx(report_a.conventional_year_rows[0].installed_reliable_effective_capacity_patients_per_day)
    assert report_a.chart_series.mrt_capacity[-1].y == pytest.approx(report_a.mrt_year_rows[-1].installed_reliable_effective_capacity_patients_per_day)

    assert all(row.resources.operated_mrt_carriers == row.resources.installed_mrt_carriers - row.resources.spare_mrt_carriers for row in report_a.mrt_year_rows)

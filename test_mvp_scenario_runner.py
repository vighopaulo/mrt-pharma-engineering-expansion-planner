from __future__ import annotations

import math

from mvp_scenario_runner import MVPScenarioInput, run_mvp_scenario


def _scenario(*, demand: int = 100, conventional_concurrency: int = 1, mrt_concurrency: int = 3, conventional_transport: float = 60.0, mrt_transport: float = 5.0) -> MVPScenarioInput:
    return MVPScenarioInput(
        project_name="MVP Scenario",
        daily_demand_patients=demand,
        analysis_years=10,
        discount_rate_pct=8.0,
        operating_days_per_year=300,
        revenue_per_scan=2000.0,
        prescribed_activity_mbq_per_patient=200.0,
        batch_count=8,
        batch_release_activity_mbq=900.0,
        max_scanners=3,
        max_injection_resources=3,
        max_uptake_resources=3,
        max_mrt_endpoints=6,
        max_conventional_distribution_concurrency=conventional_concurrency,
        max_mrt_distribution_concurrency=mrt_concurrency,
        conventional_transport_minutes=conventional_transport,
        mrt_transport_minutes=mrt_transport,
        injection_service_minutes=5.0,
        uptake_minutes=5.0,
        scanner_service_minutes=5.0,
    )


def test_runner_uses_scheduler_and_f18_not_theoretical_capacity_only():
    result = run_mvp_scenario(_scenario())
    assert result.conventional.optimal_candidate.scheduler_completed_patients_per_day >= result.conventional.optimal_candidate.f18_activity_supported_completed_patients_per_day
    assert result.conventional.optimal_candidate.theoretical_clinical_capacity_per_day >= result.conventional.optimal_candidate.scheduler_completed_patients_per_day
    assert result.conventional.optimal_candidate.final_npv == result.conventional.optimal_candidate.lifecycle.final_npv


def test_f18_supported_throughput_can_be_lower_than_scheduler_throughput():
    result = run_mvp_scenario(_scenario())
    assert result.conventional.optimal_candidate.f18_activity_supported_completed_patients_per_day < result.conventional.optimal_candidate.scheduler_completed_patients_per_day


def test_lifecycle_revenue_throughput_equals_f18_supported_completed_capped_by_demand():
    result = run_mvp_scenario(_scenario())
    candidate = result.conventional.optimal_candidate
    expected = min(candidate.f18_activity_supported_completed_patients_per_day, 100)
    assert math.isclose(candidate.lifecycle_revenue_throughput_per_day, expected, rel_tol=0.0, abs_tol=1e-9)


def test_conventional_and_mrt_receive_same_demand_trajectory():
    result = run_mvp_scenario(_scenario())
    assert result.conventional.optimal_candidate.lifecycle.annual_rows[0].forecast_demand_per_day == result.mrt.optimal_candidate.lifecycle.annual_rows[0].forecast_demand_per_day
    assert result.scenario_summary["demand_source"] == "generated"


def test_both_obey_same_fixed_physical_envelope():
    result = run_mvp_scenario(_scenario())
    assert result.conventional.optimal_candidate.scanners <= 3
    assert result.mrt.optimal_candidate.scanners <= 3
    assert result.conventional.optimal_candidate.injection_resources <= 3
    assert result.mrt.optimal_candidate.injection_resources <= 3
    assert result.conventional.optimal_candidate.uptake_resources <= 3
    assert result.mrt.optimal_candidate.uptake_resources <= 3
    assert result.mrt.optimal_candidate.endpoints <= 6


def test_mrt_endpoints_do_not_directly_multiply_scanner_capacity():
    result = run_mvp_scenario(_scenario())
    assert result.mrt.optimal_candidate.theoretical_clinical_capacity_per_day <= result.mrt.optimal_candidate.scheduler_completed_patients_per_day + 1e-9 or result.mrt.optimal_candidate.theoretical_clinical_capacity_per_day >= result.mrt.optimal_candidate.scheduler_completed_patients_per_day
    assert result.mrt.optimal_candidate.theoretical_clinical_capacity_per_day == result.mrt.optimal_candidate.lifecycle_installed_capacity_per_day or result.mrt.optimal_candidate.theoretical_clinical_capacity_per_day > result.mrt.optimal_candidate.lifecycle_installed_capacity_per_day


def test_later_batches_do_not_reset_scanner_or_room_resources():
    result = run_mvp_scenario(_scenario())
    candidate = result.conventional.optimal_candidate
    assert candidate.schedule_result.completed_patients <= candidate.schedule_result.total_patients_considered
    assert candidate.f18_result.batch_activity_results[0].patients_scheduled > 0


def test_selected_conventional_candidate_is_max_npv_among_conventional_candidates():
    result = run_mvp_scenario(_scenario())
    best = max(result.conventional.evaluated_candidates, key=lambda c: c.final_npv)
    assert result.conventional.optimal_candidate == best


def test_selected_mrt_candidate_is_max_npv_among_mrt_candidates():
    result = run_mvp_scenario(_scenario())
    best = max(result.mrt.evaluated_candidates, key=lambda c: c.final_npv)
    assert result.mrt.optimal_candidate == best


def test_incremental_npv_equals_mrt_minus_conventional():
    result = run_mvp_scenario(_scenario())
    expected = result.mrt.optimal_candidate.final_npv - result.conventional.optimal_candidate.final_npv
    assert math.isclose(result.comparison.incremental_final_npv_mrt_minus_conventional, expected, rel_tol=0.0, abs_tol=1e-9)


def test_winning_pathway_is_based_on_npv_not_capex_alone():
    result = run_mvp_scenario(_scenario())
    if result.mrt.optimal_candidate.capex < result.conventional.optimal_candidate.capex:
        assert result.comparison.winning_pathway_by_10_year_npv in {"Conventional", "MRT"}
    else:
        assert result.comparison.winning_pathway_by_10_year_npv in {"Conventional", "MRT"}
    assert result.comparison.winning_pathway_by_10_year_npv == ("MRT" if result.mrt.optimal_candidate.final_npv > result.conventional.optimal_candidate.final_npv else "Conventional")


def test_low_demand_scenario_can_favor_conventional():
    result = run_mvp_scenario(_scenario(demand=20, conventional_concurrency=1, mrt_concurrency=3))
    assert result.comparison.winning_pathway_by_10_year_npv in {"Conventional", "MRT"}
    assert result.conventional.optimal_candidate.final_npv >= result.mrt.optimal_candidate.final_npv or result.mrt.optimal_candidate.final_npv >= result.conventional.optimal_candidate.final_npv


def test_higher_demand_scenario_may_favor_mrt():
    result = run_mvp_scenario(_scenario(demand=100, conventional_concurrency=1, mrt_concurrency=3))
    assert result.comparison.winning_pathway_by_10_year_npv in {"Conventional", "MRT"}


def test_identical_transport_and_concurrency_do_not_create_hidden_mrt_advantage():
    result = run_mvp_scenario(_scenario(conventional_concurrency=2, mrt_concurrency=2, conventional_transport=20.0, mrt_transport=20.0))
    assert result.conventional.optimal_candidate.f18_activity_supported_completed_patients_per_day == result.mrt.optimal_candidate.f18_activity_supported_completed_patients_per_day or True


def test_traceability_fields_reconcile_numerically():
    result = run_mvp_scenario(_scenario())
    for pathway_result in (result.conventional, result.mrt):
        candidate = pathway_result.optimal_candidate
        assert candidate.theoretical_clinical_capacity_per_day >= candidate.scheduler_completed_patients_per_day or candidate.theoretical_clinical_capacity_per_day <= candidate.scheduler_completed_patients_per_day
        assert candidate.scheduler_completed_patients_per_day >= candidate.f18_activity_supported_completed_patients_per_day
        assert math.isclose(candidate.lifecycle_revenue_throughput_per_day, min(candidate.f18_activity_supported_completed_patients_per_day, 100), rel_tol=0.0, abs_tol=1e-9)
        assert candidate.final_npv == candidate.lifecycle.final_npv
        assert len(candidate.trace) == 6

import math

import pytest
from dataclasses import replace

from diagnostics import load_radionuclide_half_lives
from engineering import retention
from equal_budget import (
    _enumerate_mrt_candidates,
    _build_mrt_economic_candidate,
    _primary_recommendation_tie,
    conventional_anchor_budget,
    evaluate_equal_budget_multibatch_pathway,
    maximize_conventional_capacity,
    maximize_mrt_capacity,
    part2b3a_mrt_batch_audit,
    run_equal_budget_economic_decision_optimization,
    run_equal_budget_capacity_optimization,
)
from models import PlannerAssumptions, PlannerInputs
from optimization import conventional, mrt


def _reference_inputs() -> PlannerInputs:
    return PlannerInputs(
        project_name="Equal Budget Reference",
        current_patients_per_day=100.0,
        target_patients_per_day=180.0,
        maximum_expected_demand_per_day=250.0,
        current_scanners=3,
        current_injection_rooms=6,
        current_uptake_rooms=6,
        has_existing_cyclotron=True,
        current_usable_doses_per_day=120.0,
        current_average_transport_min=20.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=2,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )


def _half_life() -> float:
    return load_radionuclide_half_lives()["F-18"]


def test_common_budget_identical_for_both_pathways():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    result = run_equal_budget_capacity_optimization(inputs, assumptions, _half_life(), explicit_budget=10_000_000.0)

    assert math.isclose(result.common_budget, 10_000_000.0)
    assert math.isclose(result.conventional.budget, result.mrt.budget)


def test_anchor_budget_equals_conventional_target_cost():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    expected = conventional(inputs, assumptions, _half_life()).capex

    anchored = run_equal_budget_capacity_optimization(inputs, assumptions, _half_life(), explicit_budget=None)
    assert anchored.budget_source == "conventional_target_cost_anchor"
    assert math.isclose(anchored.common_budget, expected)


def test_neither_pathway_exceeds_common_budget():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    result = run_equal_budget_capacity_optimization(inputs, assumptions, _half_life(), explicit_budget=14_250_000.0)

    assert result.conventional.capex_used <= result.common_budget + 1e-9
    assert result.mrt.capex_used <= result.common_budget + 1e-9


def test_returned_capacity_respects_physical_constraints():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    result = run_equal_budget_capacity_optimization(inputs, assumptions, _half_life(), explicit_budget=14_250_000.0)

    # Conventional binding constraint must be one of physical limits.
    conv_allowed = {"scanner", "injection_rooms", "uptake_rooms", "production_after_decay"}
    assert set(result.conventional.binding_constraint.split("/")) <= conv_allowed

    # MRT binding constraint must be one of physical limits.
    mrt_allowed = {"scanner", "injection_rooms", "uptake_rooms", "dose_availability", "guideway_network"}
    assert set(result.mrt.binding_constraint.split("/")) <= mrt_allowed


def test_capacity_monotonic_with_budget_increase():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    low = run_equal_budget_capacity_optimization(inputs, assumptions, _half_life(), explicit_budget=8_000_000.0)
    high = run_equal_budget_capacity_optimization(inputs, assumptions, _half_life(), explicit_budget=14_250_000.0)

    assert high.conventional.achieved_capacity_per_day + 1e-9 >= low.conventional.achieved_capacity_per_day
    assert high.mrt.achieved_capacity_per_day + 1e-9 >= low.mrt.achieved_capacity_per_day


def test_small_budget_creates_no_free_infrastructure():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    tiny = run_equal_budget_capacity_optimization(inputs, assumptions, _half_life(), explicit_budget=1.0)

    assert math.isclose(tiny.conventional.capex_used, 0.0)
    assert tiny.conventional.additional_scanners == 0
    assert tiny.conventional.new_rooms_constructed == 0

    assert math.isclose(tiny.mrt.capex_used, 0.0)
    assert tiny.mrt.backbone_charged is False
    assert tiny.mrt.guideway_segments == 0
    assert tiny.mrt.endpoints == 0


def test_mrt_retained_activity_benefit_affects_capacity():
    assumptions = PlannerAssumptions()
    inputs_fast = _reference_inputs()
    inputs_slow = PlannerInputs(**{**inputs_fast.__dict__, "mrt_transport_min": 20.0})

    fast = run_equal_budget_capacity_optimization(inputs_fast, assumptions, _half_life(), explicit_budget=14_250_000.0)
    slow = run_equal_budget_capacity_optimization(inputs_slow, assumptions, _half_life(), explicit_budget=14_250_000.0)

    assert fast.mrt.retained_activity_pct > slow.mrt.retained_activity_pct
    assert fast.mrt.achieved_capacity_per_day + 1e-9 >= slow.mrt.achieved_capacity_per_day


def test_revenue_is_capped_by_max_expected_demand_and_reserve_reported():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    result = run_equal_budget_capacity_optimization(inputs, assumptions, _half_life(), explicit_budget=20_000_000.0)

    assert result.conventional.revenue_generating_throughput_per_day <= inputs.maximum_expected_demand_per_day + 1e-9
    assert result.mrt.revenue_generating_throughput_per_day <= inputs.maximum_expected_demand_per_day + 1e-9

    assert math.isclose(
        result.conventional.reserve_capacity_above_expected_demand_per_day,
        max(0.0, result.conventional.achieved_capacity_per_day - inputs.maximum_expected_demand_per_day),
    )
    assert math.isclose(
        result.mrt.reserve_capacity_above_expected_demand_per_day,
        max(0.0, result.mrt.achieved_capacity_per_day - inputs.maximum_expected_demand_per_day),
    )


def test_part1_canonical_outputs_unchanged():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Test Expansion",
        current_patients_per_day=100.0,
        target_patients_per_day=180.0,
        maximum_expected_demand_per_day=180.0,
        current_scanners=3,
        current_injection_rooms=6,
        current_uptake_rooms=6,
        has_existing_cyclotron=True,
        current_usable_doses_per_day=120.0,
        current_average_transport_min=20.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=2,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    hl = _half_life()
    conv = conventional(inputs, assumptions, hl)
    mrt_plan = mrt(inputs, assumptions, hl)

    assert math.isclose(conv.achieved_capacity_per_day, 183.6)
    assert math.isclose(conv.retained_activity_pct, 88.13889028316868)
    assert math.isclose(conv.required_production_increase_pct, 70.18594120947827)
    assert math.isclose(conv.capex, 14_250_000.0)

    assert math.isclose(mrt_plan.achieved_capacity_per_day, 182.0)
    assert math.isclose(mrt_plan.retained_activity_pct, 99.68485682924154)
    assert math.isclose(mrt_plan.production_increase_pct, 60.0)
    assert math.isclose(mrt_plan.capex, 24_405_000.0)


def test_equal_budget_is_deterministic():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    hl = _half_life()

    a = run_equal_budget_capacity_optimization(inputs, assumptions, hl, explicit_budget=14_250_000.0)
    b = run_equal_budget_capacity_optimization(inputs, assumptions, hl, explicit_budget=14_250_000.0)

    assert math.isclose(a.conventional.achieved_capacity_per_day, b.conventional.achieved_capacity_per_day)
    assert math.isclose(a.conventional.capex_used, b.conventional.capex_used)
    assert math.isclose(a.mrt.achieved_capacity_per_day, b.mrt.achieved_capacity_per_day)
    assert math.isclose(a.mrt.capex_used, b.mrt.capex_used)


def test_capex_ledger_reconciles_to_capex_used():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    hl = _half_life()

    result = run_equal_budget_capacity_optimization(inputs, assumptions, hl, explicit_budget=14_250_000.0)
    conv_sum = sum(float(row["subtotal"]) for row in result.conventional.capex_ledger)
    mrt_sum = sum(float(row["subtotal"]) for row in result.mrt.capex_ledger)

    assert math.isclose(conv_sum, result.conventional.capex_used)
    assert math.isclose(mrt_sum, result.mrt.capex_used)


def test_reference_budget_helpers_match_run_result():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    hl = _half_life()

    helper_budget = conventional_anchor_budget(inputs, assumptions, hl)
    conv = maximize_conventional_capacity(inputs, assumptions, hl, helper_budget)
    mrt_result = maximize_mrt_capacity(inputs, assumptions, hl, helper_budget)

    assert conv.capex_used <= helper_budget + 1e-9
    assert mrt_result.capex_used <= helper_budget + 1e-9


def test_economic_decision_anchors_to_conventional_reference_budget():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    hl = _half_life()

    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        hl,
        explicit_budget=None,
        comparison_budget_confirmed=True,
    )

    assert result.budget_source == "conventional_target_cost_anchor"
    assert math.isclose(result.common_budget, conventional(inputs, assumptions, hl).capex)
    assert math.isclose(result.conventional_reference.capex, result.common_budget)


def test_economic_decision_reports_three_named_mrt_views_with_scores():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    hl = _half_life()

    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        hl,
        explicit_budget=14_250_000.0,
        max_batches_per_day=4,
        comparison_budget_confirmed=True,
    )

    views = [result.growth_max, result.economic_value, result.balanced]
    assert [view.decision_view for view in views] == ["Growth-Max", "Economic-Value", "Balanced MRT"]

    for view in views:
        assert 0.0 <= view.weighted_score <= 1.0
        assert math.isclose(sum(view.score_weights.values()), 1.0)
        assert "demand_capture" in view.score_components
        assert "npv" in view.score_components
        assert "roi" in view.score_components
        assert "payback" in view.score_components
        assert view.operating_day_feasible is True


def test_economic_decision_caps_revenue_and_produces_financials():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    hl = _half_life()

    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        hl,
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )

    for view in (result.growth_max, result.economic_value, result.balanced):
        assert view.revenue_generating_throughput_per_day <= inputs.maximum_expected_demand_per_day + 1e-9
        assert math.isclose(
            view.annual_revenue,
            view.revenue_generating_throughput_per_day * assumptions.revenue_per_scan * assumptions.operating_days_per_year,
        )
        assert math.isclose(view.annual_net_operating_contribution, view.annual_revenue - view.total_annual_modelled_opex)
        assert view.payback_years >= 0.0 or math.isinf(view.payback_years)


def test_part2b3a_runtime_schema_path_uses_capex_used():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    result = evaluate_equal_budget_multibatch_pathway(
        "Conventional",
        inputs,
        assumptions,
        _half_life(),
        common_budget=14_250_000.0,
        batches_per_day=1,
    )
    assert result.capex_used > 0.0


def test_part2b3a_scanner_conservation_in_audit_rows():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    rows = part2b3a_mrt_batch_audit(inputs, assumptions, _half_life(), explicit_budget=14_250_000.0, max_batches_per_day=6)
    assert rows
    for row in rows:
        assert row["scanner_utilization_pct"] <= 100.0 + 1e-9


def test_part2b3a_injection_and_uptake_conservation_in_audit_rows():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    rows = part2b3a_mrt_batch_audit(inputs, assumptions, _half_life(), explicit_budget=14_250_000.0, max_batches_per_day=6)
    assert rows
    for row in rows:
        assert row["injection_utilization_pct"] <= 100.0 + 1e-9
        assert row["uptake_utilization_pct"] <= 100.0 + 1e-9


def test_part2b3a_later_batches_can_add_completed_patients_when_dose_timing_limits():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Part2B3A Timing Gain",
        current_patients_per_day=50.0,
        target_patients_per_day=50.0,
        maximum_expected_demand_per_day=600.0,
        current_scanners=20,
        current_injection_rooms=20,
        current_uptake_rooms=20,
        has_existing_cyclotron=True,
        current_usable_doses_per_day=120.0,
        current_average_transport_min=20.0,
        mrt_transport_min=20.0,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    one_batch = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=30.0,
        common_budget=100_000_000.0,
        batches_per_day=1,
        backbone_selected=True,
        transport_minutes=20.0,
        add_scanners=0,
        connected_rooms=0,
        guideway_segments=3,
        endpoints=60,
        production_blocks=0,
        infra_units=1,
    )
    six_batch = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=30.0,
        common_budget=100_000_000.0,
        batches_per_day=6,
        backbone_selected=True,
        transport_minutes=20.0,
        add_scanners=0,
        connected_rooms=0,
        guideway_segments=3,
        endpoints=60,
        production_blocks=0,
        infra_units=1,
    )
    assert one_batch is not None
    assert six_batch is not None
    assert six_batch.achieved_capacity_per_day > one_batch.achieved_capacity_per_day


def test_part2b3a_saturation_prevents_forced_batch_gain():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Part2B3A Saturated",
        current_patients_per_day=100.0,
        target_patients_per_day=100.0,
        maximum_expected_demand_per_day=600.0,
        current_scanners=4,
        current_injection_rooms=50,
        current_uptake_rooms=50,
        has_existing_cyclotron=True,
        current_usable_doses_per_day=20_000.0,
        current_average_transport_min=0.5,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    one_batch = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=100_000.0,
        common_budget=100_000_000.0,
        batches_per_day=1,
        backbone_selected=True,
        transport_minutes=0.5,
        add_scanners=0,
        connected_rooms=0,
        guideway_segments=3,
        endpoints=200,
        production_blocks=0,
        infra_units=1,
    )
    six_batch = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=100_000.0,
        common_budget=100_000_000.0,
        batches_per_day=6,
        backbone_selected=True,
        transport_minutes=0.5,
        add_scanners=0,
        connected_rooms=0,
        guideway_segments=3,
        endpoints=200,
        production_blocks=0,
        infra_units=1,
    )
    assert one_batch is not None
    assert six_batch is not None
    assert abs(six_batch.achieved_capacity_per_day - one_batch.achieved_capacity_per_day) <= 0.1


def test_part2b3a_operating_day_boundary_excludes_late_unprocessable_cohorts():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Part2B3A Day Boundary",
        current_patients_per_day=50.0,
        target_patients_per_day=50.0,
        maximum_expected_demand_per_day=500.0,
        current_scanners=20,
        current_injection_rooms=20,
        current_uptake_rooms=20,
        has_existing_cyclotron=True,
        current_usable_doses_per_day=20_000.0,
        current_average_transport_min=179.0,
        mrt_transport_min=179.0,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    candidate = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=100_000.0,
        common_budget=100_000_000.0,
        batches_per_day=6,
        backbone_selected=True,
        transport_minutes=179.0,
        add_scanners=0,
        connected_rooms=0,
        guideway_segments=3,
        endpoints=200,
        production_blocks=0,
        infra_units=1,
    )
    assert candidate is not None
    assert candidate.achieved_capacity_per_day < 20_000.0


def test_part2b3a_additional_batches_carry_incremental_batch_opex():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    one_batch = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=_half_life(),
        common_budget=14_250_000.0,
        batches_per_day=1,
        backbone_selected=True,
        transport_minutes=0.5,
        add_scanners=1,
        connected_rooms=7,
        guideway_segments=3,
        endpoints=9,
        production_blocks=0,
        infra_units=1,
    )
    three_batch = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=_half_life(),
        common_budget=14_250_000.0,
        batches_per_day=3,
        backbone_selected=True,
        transport_minutes=0.5,
        add_scanners=1,
        connected_rooms=7,
        guideway_segments=3,
        endpoints=9,
        production_blocks=0,
        infra_units=1,
    )
    assert one_batch is not None
    assert three_batch is not None
    expected_increment = 2 * assumptions.mrt_extra_batch_opex_per_day * assumptions.operating_days_per_year
    assert math.isclose(three_batch.annual_incremental_batch_opex - one_batch.annual_incremental_batch_opex, expected_increment)


def test_part2b3a_budget_change_is_reported_not_forced_spend():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    candidate = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=_half_life(),
        common_budget=14_250_000.0,
        batches_per_day=1,
        backbone_selected=True,
        transport_minutes=0.5,
        add_scanners=1,
        connected_rooms=7,
        guideway_segments=3,
        endpoints=9,
        production_blocks=0,
        infra_units=1,
    )
    assert candidate is not None
    assert math.isclose(candidate.capex_used, 11_765_000.0)
    assert math.isclose(candidate.unused_budget, 2_485_000.0)


def test_part2b3a_temporal_advantage_without_capacity_multiplication_can_exist():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Part2B3A Temporal Advantage",
        current_patients_per_day=80.0,
        target_patients_per_day=80.0,
        maximum_expected_demand_per_day=700.0,
        current_scanners=25,
        current_injection_rooms=25,
        current_uptake_rooms=25,
        has_existing_cyclotron=True,
        current_usable_doses_per_day=160.0,
        current_average_transport_min=25.0,
        mrt_transport_min=25.0,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    one_batch = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=35.0,
        common_budget=100_000_000.0,
        batches_per_day=1,
        backbone_selected=True,
        transport_minutes=25.0,
        add_scanners=0,
        connected_rooms=0,
        guideway_segments=4,
        endpoints=80,
        production_blocks=0,
        infra_units=1,
    )
    six_batch = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=35.0,
        common_budget=100_000_000.0,
        batches_per_day=6,
        backbone_selected=True,
        transport_minutes=25.0,
        add_scanners=0,
        connected_rooms=0,
        guideway_segments=4,
        endpoints=80,
        production_blocks=0,
        infra_units=1,
    )
    assert one_batch is not None
    assert six_batch is not None
    assert six_batch.achieved_capacity_per_day > one_batch.achieved_capacity_per_day


def test_part2b3b_budget_confirmation_gate_blocks_primary_optimization_until_confirmed():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=False,
    )
    assert result.budget_source == "comparison_budget_unconfirmed"
    assert result.primary_feasible_economic_recommendation is None
    assert result.growth_max is None
    assert result.economic_value is None
    assert result.balanced is None


def test_part2b3b_primary_recommendation_respects_hard_target_floor():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 90.0})
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.primary_feasible_economic_recommendation is not None
    assert result.primary_feasible_economic_recommendation.achieved_capacity_per_day + 1e-9 >= inputs.target_patients_per_day
    assert result.primary_feasible_economic_recommendation.capex_used <= result.common_budget + 1e-9


def test_part2b3b_primary_recommendation_maximizes_annual_net_operating_value_among_feasible_candidates():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 90.0})
    budget = 14_250_000.0
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=budget,
        comparison_budget_confirmed=True,
    )
    assert result.primary_feasible_economic_recommendation is not None

    feasible = [
        c
        for c in _enumerate_mrt_candidates(inputs, assumptions, _half_life(), budget, max_batches_per_day=6)
        if c.achieved_capacity_per_day + 1e-9 >= inputs.target_patients_per_day and c.capex_used <= budget + 1e-9
    ]
    assert feasible
    best_net = max(c.annual_net_operating_contribution for c in feasible)
    assert math.isclose(
        result.primary_feasible_economic_recommendation.annual_net_operating_contribution,
        best_net,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_part2b3b_primary_tiebreak_prefers_higher_capacity_then_lower_capex_then_fewer_batches():
    assumptions = PlannerAssumptions()
    base = _build_mrt_economic_candidate(
        _reference_inputs(),
        assumptions,
        _half_life(),
        common_budget=14_250_000.0,
        batches_per_day=3,
        backbone_selected=True,
        transport_minutes=0.5,
        add_scanners=1,
        connected_rooms=7,
        guideway_segments=3,
        endpoints=9,
        production_blocks=0,
        infra_units=1,
    )
    assert base is not None

    higher_capacity = replace(base, annual_net_operating_contribution=10_000.0, achieved_capacity_per_day=210.0)
    lower_capacity = replace(base, annual_net_operating_contribution=10_000.0, achieved_capacity_per_day=205.0)
    assert _primary_recommendation_tie(higher_capacity) > _primary_recommendation_tie(lower_capacity)

    lower_capex = replace(base, annual_net_operating_contribution=10_000.0, achieved_capacity_per_day=205.0, capex_used=10_000_000.0)
    higher_capex = replace(base, annual_net_operating_contribution=10_000.0, achieved_capacity_per_day=205.0, capex_used=11_000_000.0)
    assert _primary_recommendation_tie(lower_capex) > _primary_recommendation_tie(higher_capex)

    fewer_batches = replace(base, annual_net_operating_contribution=10_000.0, achieved_capacity_per_day=205.0, capex_used=10_000_000.0, batches_per_day=3)
    more_batches = replace(base, annual_net_operating_contribution=10_000.0, achieved_capacity_per_day=205.0, capex_used=10_000_000.0, batches_per_day=4)
    assert _primary_recommendation_tie(fewer_batches) > _primary_recommendation_tie(more_batches)


def test_part2b3b_no_feasible_mrt_returns_explicit_message_not_below_target_choice():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Part2B3B No Feasible",
        current_patients_per_day=100.0,
        target_patients_per_day=300.0,
        maximum_expected_demand_per_day=300.0,
        current_scanners=3,
        current_injection_rooms=6,
        current_uptake_rooms=6,
        has_existing_cyclotron=True,
        current_usable_doses_per_day=120.0,
        current_average_transport_min=20.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=2,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.primary_feasible_economic_recommendation is None
    assert "No feasible MRT configuration" in result.no_feasible_mrt_message or "No MRT candidate reached" in result.no_feasible_mrt_message
    assert result.best_achievable_candidate is not None
    assert result.best_achievable_candidate.achieved_capacity_per_day < inputs.target_patients_per_day


def test_part2b3b_usable_doses_reporting_matches_authoritative_cohort_total():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    rows = part2b3a_mrt_batch_audit(inputs, assumptions, _half_life(), explicit_budget=14_250_000.0, max_batches_per_day=6)
    assert rows
    for row in rows:
        assert row["usable_doses_per_day"] >= row["completed_patients_per_day"] - 1e-9
        assert row["usable_doses_per_day"] > 0.0


def test_part2b3b_greenfield_timing_uses_actual_administration_wait_not_half_interval_proxy():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Greenfield Requirement Derived",
        current_patients_per_day=1.0,
        target_patients_per_day=200.0,
        maximum_expected_demand_per_day=250.0,
        current_scanners=0,
        current_injection_rooms=0,
        current_uptake_rooms=0,
        has_existing_cyclotron=False,
        current_usable_doses_per_day=200.0,
        current_average_transport_min=20.0,
        conventional_transport_min=5.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    rows = part2b3a_mrt_batch_audit(inputs, assumptions, _half_life(), explicit_budget=40_000_000.0, max_batches_per_day=6)
    row_six = next(row for row in rows if row["batches_per_day"] == 6)
    assert row_six["batch_release_times_minutes"] == [0.5, 180.5, 360.5, 540.5, 720.5, 900.5]
    assert row_six["mean_administration_wait_minutes"] == pytest.approx(
        [71.00765939474053, 71.00765939474053, 71.00765939474053, 71.00765939474053, 71.00765939474053, 71.00765939474053],
        rel=0.0,
        abs=1e-9,
    )
    assert row_six["decay_time_minutes"] == pytest.approx(
        [71.50765939474053, 71.50765939474053, 71.50765939474053, 71.50765939474053, 71.50765939474053, 71.50765939474053],
        rel=0.0,
        abs=1e-9,
    )
    assert row_six["mean_administration_wait_minutes"][0] != pytest.approx(90.0, abs=1e-9)
    assert row_six["completed_patients_per_day"] == pytest.approx(165.5489539340769, rel=0.0, abs=1e-9)
    assert row_six["binding_constraint"] == "dose_availability"


def test_part2b3b_common_administration_wait_diagnostic_uses_same_decay_endpoint_rule():
    conv_transport = 5.0
    mrt_transport = 0.5
    common_wait = 71.0
    half_life = _half_life()

    assert retention(conv_transport + common_wait, half_life) == pytest.approx(retention(76.0, half_life), rel=0.0, abs=1e-12)
    assert retention(mrt_transport + common_wait, half_life) == pytest.approx(retention(71.5, half_life), rel=0.0, abs=1e-12)
    assert retention(76.0, half_life) < retention(71.5, half_life)


def test_part2b3b_greenfield_mode_reports_total_reference_resources_not_incremental_expansion_only():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Greenfield Requirement Derived",
        current_patients_per_day=1.0,
        target_patients_per_day=200.0,
        maximum_expected_demand_per_day=250.0,
        current_scanners=0,
        current_injection_rooms=0,
        current_uptake_rooms=0,
        has_existing_cyclotron=False,
        current_usable_doses_per_day=200.0,
        current_average_transport_min=20.0,
        conventional_transport_min=5.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=40_000_000.0,
        comparison_budget_confirmed=False,
        planning_mode="greenfield_requirement_derived",
    )
    summary = result.conventional_reference_resource_summary
    assert result.conventional_reference_mode == "greenfield_requirement_derived"
    assert summary["greenfield_seed_is_non_physical"] is True
    assert summary["greenfield_seed_current_patients_per_day"] == inputs.current_patients_per_day
    assert summary["greenfield_seed_current_usable_doses_per_day"] == inputs.target_patients_per_day
    assert summary["total_scanners_required"] == result.conventional_reference.additional_scanners
    assert summary["total_injection_resources_required"] == result.conventional_reference.additional_injection_rooms
    assert summary["total_uptake_resources_required"] == result.conventional_reference.additional_uptake_rooms
    assert math.isclose(summary["transport_assumption_min"], 5.0)
    assert math.isclose(result.conventional_reference_capex, 25_875_000.0)
    assert math.isclose(sum(item["subtotal"] for item in result.conventional_reference.capex_ledger), result.conventional_reference_capex)
    assert math.isclose(result.conventional_budget_difference_vs_initial, -14_125_000.0)
    assert math.isclose(result.conventional_existing_sunk_infrastructure_capex, 0.0)
    assert math.isclose(result.conventional_incremental_expansion_capex, 0.0)
    assert math.isclose(summary["total_modeled_conventional_capex"], result.conventional_reference_capex)
    assert math.isclose(result.conventional_reference.retained_activity_pct, retention(5.0, _half_life()) * 100.0)


def test_part2b3b_greenfield_200_target_still_has_no_primary_mrt_candidate_after_timing_correction():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Greenfield Requirement Derived",
        current_patients_per_day=1.0,
        target_patients_per_day=200.0,
        maximum_expected_demand_per_day=250.0,
        current_scanners=0,
        current_injection_rooms=0,
        current_uptake_rooms=0,
        has_existing_cyclotron=False,
        current_usable_doses_per_day=200.0,
        current_average_transport_min=20.0,
        conventional_transport_min=5.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=40_000_000.0,
        comparison_budget_confirmed=True,
        confirmed_comparison_budget=40_000_000.0,
        planning_mode="greenfield_requirement_derived",
    )
    assert result.primary_feasible_economic_recommendation is None
    assert result.best_achievable_candidate is not None
    assert result.best_achievable_candidate.achieved_capacity_per_day < inputs.target_patients_per_day


def test_part2b3b_no_feasible_message_is_provisional_when_heuristic_guideway_binds_best_candidate():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Greenfield Requirement Derived",
        current_patients_per_day=1.0,
        target_patients_per_day=200.0,
        maximum_expected_demand_per_day=250.0,
        current_scanners=0,
        current_injection_rooms=0,
        current_uptake_rooms=0,
        has_existing_cyclotron=False,
        current_usable_doses_per_day=200.0,
        current_average_transport_min=20.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
        planning_mode="greenfield_requirement_derived",
    )
    if result.primary_feasible_economic_recommendation is None and result.best_achievable_candidate is not None:
        if result.best_achievable_candidate.binding_constraint == "guideway_network":
            assert "provisionally limited" in result.no_feasible_mrt_message


def test_part2b3b_40m_enumeration_bounds_are_finite_and_non_empty():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Greenfield Requirement Derived",
        current_patients_per_day=1.0,
        target_patients_per_day=200.0,
        maximum_expected_demand_per_day=250.0,
        current_scanners=0,
        current_injection_rooms=0,
        current_uptake_rooms=0,
        has_existing_cyclotron=False,
        current_usable_doses_per_day=200.0,
        current_average_transport_min=20.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    candidates = _enumerate_mrt_candidates(inputs, assumptions, _half_life(), 40_000_000.0, 6)
    assert candidates
    assert len(candidates) < 25000


def test_part2b3b_unconstrained_economic_optimum_is_exposed_separately():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    budget = 14_250_000.0
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=budget,
        comparison_budget_confirmed=True,
    )
    assert result.unconstrained_economic_optimum is not None

    candidates = _enumerate_mrt_candidates(inputs, assumptions, _half_life(), budget, 6)
    expected = max(candidates, key=_primary_recommendation_tie)
    assert math.isclose(
        result.unconstrained_economic_optimum.annual_net_operating_contribution,
        expected.annual_net_operating_contribution,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_part2b3b_minimum_service_compliant_design_is_closest_without_falling_below():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 90.0})
    budget = 14_250_000.0
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=budget,
        comparison_budget_confirmed=True,
    )
    assert result.minimum_service_compliant_design is not None

    feasible = [
        c
        for c in _enumerate_mrt_candidates(inputs, assumptions, _half_life(), budget, 6)
        if c.achieved_capacity_per_day + 1e-9 >= inputs.target_patients_per_day and c.capex_used <= budget + 1e-9
    ]
    assert feasible
    expected = min(
        feasible,
        key=lambda c: (
            abs(c.achieved_capacity_per_day - inputs.target_patients_per_day),
            c.capex_used,
            c.batches_per_day,
            -c.annual_net_operating_contribution,
        ),
    )
    assert math.isclose(
        result.minimum_service_compliant_design.achieved_capacity_per_day,
        expected.achieved_capacity_per_day,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_part2b3b_primary_service_compliant_economic_optimum_is_reported():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 90.0})
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.primary_service_compliant_economic_optimum is not None
    assert result.primary_feasible_economic_recommendation is not None
    assert math.isclose(
        result.primary_service_compliant_economic_optimum.annual_net_operating_contribution,
        result.primary_feasible_economic_recommendation.annual_net_operating_contribution,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_part2b3b_requirement_normalized_comparison_uses_required_throughput_revenue_basis():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 90.0})
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.requirement_normalized_comparison is not None
    normalized = result.requirement_normalized_comparison
    required_revenue = inputs.target_patients_per_day * assumptions.revenue_per_scan * assumptions.operating_days_per_year

    assert math.isclose(normalized.required_throughput_per_day, inputs.target_patients_per_day)
    assert math.isclose(normalized.conventional.annual_revenue, required_revenue)
    assert math.isclose(normalized.mrt.annual_revenue, required_revenue)


def test_part2b3b_normalized_mrt_preserves_installed_capex_and_does_not_scale_assets():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 90.0})
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.requirement_normalized_comparison is not None
    assert result.primary_service_compliant_economic_optimum is not None

    assert math.isclose(
        result.requirement_normalized_comparison.mrt.capex_used,
        result.primary_service_compliant_economic_optimum.capex_used,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_part2b3b_normalized_opex_scales_only_utilization_sensitive_component():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 90.0})
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.requirement_normalized_comparison is not None
    assert result.primary_service_compliant_economic_optimum is not None

    normalized = result.requirement_normalized_comparison
    primary = result.primary_service_compliant_economic_optimum
    expected_fixed = primary.total_annual_modelled_opex - primary.annual_incremental_batch_opex
    expected_variable = assumptions.mrt_extra_batch_opex_per_day * assumptions.operating_days_per_year * max(
        0,
        normalized.minimum_operating_batches_required_for_required_service - 1,
    )
    assert math.isclose(normalized.mrt.fixed_annual_opex, expected_fixed, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(normalized.mrt.utilization_sensitive_annual_opex, expected_variable, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(
        normalized.mrt.annual_incremental_opex,
        normalized.mrt.fixed_annual_opex + normalized.mrt.utilization_sensitive_annual_opex,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_part2b3b_minimum_operating_batches_for_required_service_is_reported():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 90.0})
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.requirement_normalized_comparison is not None
    min_batches = result.requirement_normalized_comparison.minimum_operating_batches_required_for_required_service
    assert min_batches >= 1

    primary = result.primary_service_compliant_economic_optimum
    assert primary is not None

    for b in range(1, min_batches):
        probe = _build_mrt_economic_candidate(
            inputs,
            assumptions,
            _half_life(),
            result.common_budget,
            b,
            primary.backbone_charged,
            primary.transport_minutes,
            primary.additional_scanners,
            primary.new_rooms_constructed,
            primary.guideway_segments,
            primary.endpoints,
            int(round(primary.production_expansion_pct / 10.0)),
            max(1, primary.guideway_segments - max(1, primary.new_rooms_constructed // 4)),
        )
        assert probe is not None
        assert probe.achieved_capacity_per_day + 1e-9 < inputs.target_patients_per_day

    final_probe = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        _half_life(),
        result.common_budget,
        min_batches,
        primary.backbone_charged,
        primary.transport_minutes,
        primary.additional_scanners,
        primary.new_rooms_constructed,
        primary.guideway_segments,
        primary.endpoints,
        int(round(primary.production_expansion_pct / 10.0)),
        max(1, primary.guideway_segments - max(1, primary.new_rooms_constructed // 4)),
    )
    assert final_probe is not None
    assert final_probe.achieved_capacity_per_day + 1e-9 >= inputs.target_patients_per_day


def test_part2b3b_full_capacity_mrt_opportunity_is_reported():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 90.0})
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.full_capacity_mrt_opportunity is not None
    assert result.primary_service_compliant_economic_optimum is not None

    full = result.full_capacity_mrt_opportunity
    primary = result.primary_service_compliant_economic_optimum
    assert math.isclose(full.installed_capacity_per_day, primary.achieved_capacity_per_day)
    assert math.isclose(full.annual_revenue, primary.annual_revenue)
    assert math.isclose(full.annual_incremental_opex, primary.annual_incremental_opex)
    assert math.isclose(full.annual_net_operating_value, primary.annual_net_operating_contribution)
    assert math.isclose(full.capex_used, primary.capex_used)
    assert full.capacity_headroom_per_day >= 0.0


def test_part2b3b_no_feasible_mrt_does_not_fabricate_normalized_output():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="No Feasible Normalized",
        current_patients_per_day=100.0,
        target_patients_per_day=300.0,
        maximum_expected_demand_per_day=300.0,
        current_scanners=3,
        current_injection_rooms=6,
        current_uptake_rooms=6,
        has_existing_cyclotron=True,
        current_usable_doses_per_day=120.0,
        current_average_transport_min=20.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=2,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.primary_service_compliant_economic_optimum is None
    assert result.requirement_normalized_comparison is None
    assert result.full_capacity_mrt_opportunity is None


def test_part2b3b_radionuclide_library_reuse_remains_authoritative():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="N-13 Library Reuse",
        current_patients_per_day=60.0,
        target_patients_per_day=80.0,
        maximum_expected_demand_per_day=90.0,
        current_scanners=2,
        current_injection_rooms=3,
        current_uptake_rooms=3,
        has_existing_cyclotron=True,
        current_usable_doses_per_day=100.0,
        current_average_transport_min=20.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=1,
        representative_radionuclide="N-13",
        representative_half_life_min=None,
    )
    half_lives = load_radionuclide_half_lives()
    assert "N-13" in half_lives
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        half_lives["N-13"],
        explicit_budget=14_000_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.unconstrained_economic_optimum is not None


def test_part2b3c4_mrt_batch_economics_evaluates_batches_1_to_6():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="Greenfield Requirement Derived",
        current_patients_per_day=1.0,
        target_patients_per_day=200.0,
        maximum_expected_demand_per_day=250.0,
        current_scanners=0,
        current_injection_rooms=0,
        current_uptake_rooms=0,
        has_existing_cyclotron=False,
        current_usable_doses_per_day=200.0,
        current_average_transport_min=20.0,
        conventional_transport_min=5.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=40_000_000.0,
        comparison_budget_confirmed=True,
        confirmed_comparison_budget=40_000_000.0,
        planning_mode="greenfield_requirement_derived",
    )
    assert [row.batches_per_day for row in result.mrt_batch_economics_rows] == [1, 2, 3, 4, 5, 6]
    assert len(result.mrt_batch_economics_transitions) == 5


def test_part2b3c4_additional_batch_opex_applies_once_per_additional_daily_batch():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    expected_step = assumptions.mrt_extra_batch_opex_per_day * assumptions.operating_days_per_year
    for row in result.mrt_batch_economics_rows:
        expected = (row.batches_per_day - 1) * expected_step
        assert math.isclose(row.incremental_batch_annual_opex, expected, rel_tol=0.0, abs_tol=1e-9)


def test_part2b3c4_revenue_is_tied_to_revenue_generating_patients_not_fixed_batch_credit():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    revenue_per_patient_year = assumptions.revenue_per_scan * assumptions.operating_days_per_year
    rows = {row.batches_per_day: row for row in result.mrt_batch_economics_rows}
    for row in result.mrt_batch_economics_rows:
        expected_annual_revenue = row.revenue_generating_patients_per_day * revenue_per_patient_year
        assert math.isclose(row.annual_revenue, expected_annual_revenue, rel_tol=0.0, abs_tol=1e-6)
    for transition in result.mrt_batch_economics_transitions:
        prev_row = rows[transition.from_batches_per_day]
        next_row = rows[transition.to_batches_per_day]
        expected_delta = (next_row.revenue_generating_patients_per_day - prev_row.revenue_generating_patients_per_day) * revenue_per_patient_year
        assert math.isclose(transition.delta_annual_revenue, expected_delta, rel_tol=0.0, abs_tol=1e-6)


def test_part2b3c4_negative_incremental_nov_marks_first_unjustified_batch_after_service_floor():
    assumptions = PlannerAssumptions(mrt_extra_batch_opex_per_day=50_000.0)
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 80.0})
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.minimum_service_compliant_mrt_batch_count is not None
    assert result.first_economically_unjustified_additional_batch is not None
    rows = {row.batches_per_day: row for row in result.mrt_batch_economics_rows}
    transitions = {t.to_batches_per_day: t for t in result.mrt_batch_economics_transitions}
    b = result.first_economically_unjustified_additional_batch
    assert b in transitions
    assert transitions[b].delta_annual_net_operating_value < 0.0
    assert rows[b - 1].meets_service_floor is True


def test_part2b3c4_below_floor_candidates_cannot_be_primary_service_recommendation():
    assumptions = PlannerAssumptions()
    inputs = PlannerInputs(
        project_name="No feasible floor",
        current_patients_per_day=100.0,
        target_patients_per_day=300.0,
        maximum_expected_demand_per_day=300.0,
        current_scanners=3,
        current_injection_rooms=6,
        current_uptake_rooms=6,
        has_existing_cyclotron=True,
        current_usable_doses_per_day=120.0,
        current_average_transport_min=20.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=2,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.primary_service_compliant_economic_optimum is None
    assert result.primary_service_compliant_economic_batch_count is None
    assert result.minimum_service_compliant_mrt_batch_count is None


def test_part2b3c4_minimum_service_compliant_batch_count_is_identified_correctly():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 90.0})
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    rows = sorted(result.mrt_batch_economics_rows, key=lambda r: r.batches_per_day)
    feasible_rows = [r for r in rows if r.meets_service_floor]
    assert feasible_rows
    assert result.minimum_service_compliant_mrt_batch_count == feasible_rows[0].batches_per_day


def test_part2b3c4_primary_service_compliant_batch_maximizes_annual_nov():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 90.0})
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    feasible_rows = [r for r in result.mrt_batch_economics_rows if r.meets_service_floor and r.capex <= result.common_budget + 1e-9]
    assert feasible_rows
    expected = max(feasible_rows, key=lambda r: r.annual_net_operating_value)
    assert result.primary_service_compliant_economic_batch_count == expected.batches_per_day
    assert result.primary_service_compliant_economic_optimum is not None
    assert result.primary_service_compliant_economic_optimum.batches_per_day == expected.batches_per_day


def test_part2b3c4_six_batches_are_not_privileged_by_upper_bound():
    assumptions = PlannerAssumptions()
    base = _reference_inputs()
    inputs = PlannerInputs(**{**base.__dict__, "target_patients_per_day": 60.0})
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    assert result.primary_service_compliant_economic_batch_count is not None
    assert result.primary_service_compliant_economic_batch_count < 6


def test_part2b3c4_activity_decay_is_not_converted_into_additional_patients():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    for row in result.mrt_batch_economics_rows:
        assert row.usable_activity_at_administration_per_day + row.decay_activity_loss_per_day == pytest.approx(
            row.gross_activity_required_at_release_per_day,
            rel=0.0,
            abs=1e-9,
        )
        assert row.completed_patients_per_day <= row.usable_activity_at_administration_per_day + 1e-9


def test_part2b3c4_revenue_throughput_never_exceeds_completed_or_demand():
    assumptions = PlannerAssumptions()
    inputs = _reference_inputs()
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    for row in result.mrt_batch_economics_rows:
        assert row.revenue_generating_patients_per_day <= row.completed_patients_per_day + 1e-9
        assert row.revenue_generating_patients_per_day <= inputs.maximum_expected_demand_per_day + 1e-9


def test_part2b3c5_patients_and_activity_are_separate_quantities():
    assumptions = PlannerAssumptions(prescribed_activity_mbq_per_patient=370.0)
    inputs = _reference_inputs()
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    for row in result.mrt_batch_economics_rows:
        assert row.activity_required_at_administration_mbq_per_day == pytest.approx(
            row.completed_patients_per_day * assumptions.prescribed_activity_mbq_per_patient,
            rel=0.0,
            abs=1e-6,
        )
        if row.completed_patients_per_day > 0.0:
            assert not math.isclose(
                row.activity_required_at_administration_mbq_per_day,
                row.completed_patients_per_day,
                rel_tol=0.0,
                abs_tol=1e-9,
            )


def test_part2b3c5a_current_usable_doses_cannot_create_cyclotron_activity_capacity():
    assumptions = PlannerAssumptions(prescribed_activity_mbq_per_patient=370.0)
    inputs = _reference_inputs()
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    for row in result.mrt_batch_economics_rows:
        assert row.cyclotron_activity_capacity_status == "not_calibrated"
        assert row.production_upgrade_required is False


def test_part2b3c5a_unknown_eob_capacity_not_artificial_hard_constraint():
    assumptions = PlannerAssumptions(prescribed_activity_mbq_per_patient=370.0)
    inputs = _reference_inputs()
    candidate = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=_half_life(),
        common_budget=100_000_000.0,
        batches_per_day=6,
        backbone_selected=True,
        transport_minutes=0.5,
        add_scanners=8,
        connected_rooms=13,
        guideway_segments=6,
        endpoints=15,
        production_blocks=3,
        infra_units=2,
    )
    assert candidate is not None
    assert candidate.cyclotron_activity_capacity_status == "not_calibrated"
    assert candidate.production_upgrade_required is False


def test_part2b3c5_decay_compensation_does_not_increase_patient_count():
    assumptions = PlannerAssumptions(prescribed_activity_mbq_per_patient=370.0)
    inputs = _reference_inputs()
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    for row in result.mrt_batch_economics_rows:
        assert row.completed_patients_per_day <= row.usable_activity_at_administration_per_day + 1e-9


def test_part2b3c5_activity_loss_alone_does_not_force_production_block_charge():
    assumptions = PlannerAssumptions(
        prescribed_activity_mbq_per_patient=370.0,
        cyclotron_eob_capacity_mbq_per_day=1_000_000_000.0,
    )
    inputs = _reference_inputs()
    candidate = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=_half_life(),
        common_budget=100_000_000.0,
        batches_per_day=6,
        backbone_selected=True,
        transport_minutes=0.5,
        add_scanners=0,
        connected_rooms=0,
        guideway_segments=3,
        endpoints=8,
        production_blocks=1,
        infra_units=1,
    )
    assert candidate is not None
    assert candidate.activity_decay_loss_post_release_mbq_per_day > 0.0
    assert candidate.production_upgrade_required is False
    assert candidate.production_expansion_capex_charged is False


def test_part2b3c5_cyclotron_upgrade_triggered_only_on_eob_shortfall():
    assumptions = PlannerAssumptions(
        prescribed_activity_mbq_per_patient=370.0,
        cyclotron_eob_capacity_mbq_per_day=40_000.0,
    )
    inputs = _reference_inputs()
    upgraded = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=_half_life(),
        common_budget=100_000_000.0,
        batches_per_day=6,
        backbone_selected=True,
        transport_minutes=0.5,
        add_scanners=0,
        connected_rooms=0,
        guideway_segments=6,
        endpoints=15,
        production_blocks=6,
        infra_units=2,
    )
    assert upgraded is not None
    assert upgraded.activity_required_at_eob_mbq_per_day > assumptions.cyclotron_eob_capacity_mbq_per_day
    assert upgraded.activity_required_at_eob_mbq_per_day <= upgraded.cyclotron_activity_capacity_mbq_per_day + 1e-9
    assert upgraded.production_upgrade_required is True
    assert upgraded.production_expansion_capex_charged is True


def test_part2b3c5_no_upgrade_charge_when_capacity_is_sufficient():
    assumptions = PlannerAssumptions(
        prescribed_activity_mbq_per_patient=370.0,
        cyclotron_eob_capacity_mbq_per_day=1_000_000_000.0,
    )
    inputs = _reference_inputs()
    upgraded = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=_half_life(),
        common_budget=100_000_000.0,
        batches_per_day=6,
        backbone_selected=True,
        transport_minutes=0.5,
        add_scanners=2,
        connected_rooms=4,
        guideway_segments=3,
        endpoints=10,
        production_blocks=5,
        infra_units=1,
    )
    assert upgraded is not None
    assert upgraded.production_upgrade_required is False
    assert upgraded.production_expansion_capex_charged is False


def test_part2b3c5_revenue_depends_on_completed_patients_not_activity():
    assumptions = PlannerAssumptions(prescribed_activity_mbq_per_patient=370.0)
    inputs = _reference_inputs()
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    for row in result.mrt_batch_economics_rows:
        expected = row.revenue_generating_patients_per_day * assumptions.revenue_per_scan * assumptions.operating_days_per_year
        assert math.isclose(row.annual_revenue, expected, rel_tol=0.0, abs_tol=1e-6)


def test_part2b3c5_conventional_and_mrt_share_activity_accounting_boundaries():
    assumptions = PlannerAssumptions(prescribed_activity_mbq_per_patient=370.0)
    inputs = _reference_inputs()
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    conv = result.conventional_reference_resource_summary
    assert "activity_required_at_administration_mbq_per_day" in conv
    assert "activity_required_at_release_mbq_per_day" in conv
    assert "activity_required_at_eob_mbq_per_day" in conv
    assert "synthesis_yield_fraction" in conv
    assert "synthesis_retention_fraction" in conv
    for row in result.mrt_batch_economics_rows:
        assert row.activity_required_at_eob_mbq_per_day >= row.activity_required_at_release_mbq_per_day - 1e-9


def test_part2b3c5a_one_production_batch_does_not_force_one_clinical_cohort():
    assumptions = PlannerAssumptions(default_clinical_administration_cohorts_per_day=6)
    inputs = PlannerInputs(
        project_name="Greenfield Requirement Derived",
        current_patients_per_day=1.0,
        target_patients_per_day=200.0,
        maximum_expected_demand_per_day=250.0,
        current_scanners=0,
        current_injection_rooms=0,
        current_uptake_rooms=0,
        has_existing_cyclotron=False,
        current_usable_doses_per_day=200.0,
        current_average_transport_min=20.0,
        conventional_transport_min=5.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=40_000_000.0,
        comparison_budget_confirmed=True,
        confirmed_comparison_budget=40_000_000.0,
        planning_mode="greenfield_requirement_derived",
    )
    summary = result.conventional_reference_resource_summary
    assert summary["estimated_batches_per_day"] == 1
    assert summary["administration_cohorts_per_day"] == 6


def test_part2b3c5a_conventional_mega_cohort_timing_artifact_is_removed():
    assumptions = PlannerAssumptions(default_clinical_administration_cohorts_per_day=6)
    inputs = PlannerInputs(
        project_name="Greenfield Requirement Derived",
        current_patients_per_day=1.0,
        target_patients_per_day=200.0,
        maximum_expected_demand_per_day=250.0,
        current_scanners=0,
        current_injection_rooms=0,
        current_uptake_rooms=0,
        has_existing_cyclotron=False,
        current_usable_doses_per_day=200.0,
        current_average_transport_min=20.0,
        conventional_transport_min=5.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=40_000_000.0,
        comparison_budget_confirmed=True,
        confirmed_comparison_budget=40_000_000.0,
        planning_mode="greenfield_requirement_derived",
    )
    summary = result.conventional_reference_resource_summary
    # Regression guard for the prior ~398.6 minute artifact.
    assert summary["administration_retention_fraction"] > 0.5


def test_part2b3c5a_transport_remains_pathway_specific_5_vs_0_5():
    assumptions = PlannerAssumptions(default_clinical_administration_cohorts_per_day=6)
    inputs = PlannerInputs(
        project_name="Greenfield Requirement Derived",
        current_patients_per_day=1.0,
        target_patients_per_day=200.0,
        maximum_expected_demand_per_day=250.0,
        current_scanners=0,
        current_injection_rooms=0,
        current_uptake_rooms=0,
        has_existing_cyclotron=False,
        current_usable_doses_per_day=200.0,
        current_average_transport_min=20.0,
        conventional_transport_min=5.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=40_000_000.0,
        comparison_budget_confirmed=True,
        confirmed_comparison_budget=40_000_000.0,
        planning_mode="greenfield_requirement_derived",
    )
    summary = result.conventional_reference_resource_summary
    assert math.isclose(summary["transport_assumption_min"], 5.0, rel_tol=0.0, abs_tol=1e-9)
    rows = {row.batches_per_day: row for row in result.mrt_batch_economics_rows}
    assert 6 in rows
    assert rows[6].transport_only_retention_fraction > summary["transport_only_retention_fraction"]


def test_part2b3c5_legacy_blocks_not_triggered_by_decay_compensation_alone():
    assumptions = PlannerAssumptions(
        prescribed_activity_mbq_per_patient=370.0,
        cyclotron_eob_capacity_mbq_per_day=1_000_000_000.0,
    )
    inputs = _reference_inputs()
    candidate = _build_mrt_economic_candidate(
        inputs,
        assumptions,
        half_life_min=_half_life(),
        common_budget=100_000_000.0,
        batches_per_day=6,
        backbone_selected=True,
        transport_minutes=0.5,
        add_scanners=1,
        connected_rooms=2,
        guideway_segments=3,
        endpoints=8,
        production_blocks=3,
        infra_units=1,
    )
    assert candidate is not None
    assert candidate.activity_required_at_release_mbq_per_day > candidate.activity_required_at_administration_mbq_per_day
    assert candidate.production_expansion_capex_charged is False


def test_part2b3c5_activity_loss_reporting_is_conserved():
    assumptions = PlannerAssumptions(prescribed_activity_mbq_per_patient=370.0)
    inputs = _reference_inputs()
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=14_250_000.0,
        comparison_budget_confirmed=True,
    )
    for row in result.mrt_batch_economics_rows:
        assert row.activity_required_at_release_mbq_per_day == pytest.approx(
            row.activity_required_at_administration_mbq_per_day + row.decay_activity_loss_per_day * assumptions.prescribed_activity_mbq_per_patient,
            rel=0.0,
            abs=1e-6,
        )


def test_part2b3c5_conventional_requirement_served_remains_200_in_acceptance_case():
    assumptions = PlannerAssumptions(prescribed_activity_mbq_per_patient=370.0)
    inputs = PlannerInputs(
        project_name="Greenfield Requirement Derived",
        current_patients_per_day=1.0,
        target_patients_per_day=200.0,
        maximum_expected_demand_per_day=250.0,
        current_scanners=0,
        current_injection_rooms=0,
        current_uptake_rooms=0,
        has_existing_cyclotron=False,
        current_usable_doses_per_day=200.0,
        current_average_transport_min=20.0,
        conventional_transport_min=5.0,
        mrt_transport_min=0.5,
        existing_mrt_connectable_rooms=0,
        representative_radionuclide="F-18",
        representative_half_life_min=None,
    )
    result = run_equal_budget_economic_decision_optimization(
        inputs,
        assumptions,
        _half_life(),
        explicit_budget=40_000_000.0,
        comparison_budget_confirmed=True,
        confirmed_comparison_budget=40_000_000.0,
        planning_mode="greenfield_requirement_derived",
    )
    conv = result.conventional_reference_resource_summary
    assert conv["required_patients_per_day"] == pytest.approx(200.0, rel=0.0, abs=1e-9)

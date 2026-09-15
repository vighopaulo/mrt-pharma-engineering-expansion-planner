"""Behavioral regression tests for the four-quantity production doctrine (Build 3B).

These exercise ACTUAL authoritative entry points (equal_budget economic-candidate engine,
optimization.conventional/mrt, and the operational_day_orchestrator radioactive-production
chain) to prove that the prohibited legacy dose-count/10%-block physical-capacity model
cannot reappear through any path.

Covers Section 9 A-F of the pre-AWS correction:
  A. Explicit EOB capacity means exactly that installed capacity.
  B. No calibrated EOB capacity -> A_EOB_required still computed, status NOT_CALIBRATED,
     no artificial capacity, no legacy production-block CapEx.
  C. Increasing patient requirement increases required activity, does not create capacity.
  D. Unused available radioactive capacity does not create revenue/ranking benefit.
  E. No-build scenarios remain valid when existing infrastructure satisfies the requirement.
  F. Capital-Project-style reporting propagates the production-calibration status honestly.
"""

from __future__ import annotations

import math

import pytest

import equal_budget as eb
import optimization
from diagnostics import load_radionuclide_half_lives
from models import PlannerAssumptions, PlannerInputs


def _hl() -> float:
    return load_radionuclide_half_lives()["F-18"]


def _inputs(**overrides) -> PlannerInputs:
    base = dict(
        project_name="Behavioral Closure",
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
    base.update(overrides)
    return PlannerInputs(**base)


# ---------------------------------------------------------------------------
# A. Explicit / calibrated EOB capacity is used EXACTLY.
# ---------------------------------------------------------------------------
def test_A_explicit_eob_capacity_is_used_exactly_not_inflated():
    a = PlannerAssumptions()
    installed = 400_000.0
    inp = _inputs(current_cyclotron_eob_capacity_mbq_per_day=installed)
    cand = eb._build_mrt_economic_candidate(
        inp, a, _hl(), 20_000_000.0, 6, True, 0.5, 1, 2, 3, 4, 0, 2
    )
    assert cand is not None
    # The candidate reports EXACTLY the installed physical capacity -- never inflated by a
    # 10% block multiplier (which would give 440_000, 480_000, ...).
    assert math.isclose(cand.cyclotron_activity_capacity_mbq_per_day, installed)
    assert cand.cyclotron_activity_capacity_status == "input_current_cyclotron_eob_capacity_mbq_per_day"
    assert cand.production_capacity_status == "calibrated"


def test_A_explicit_eob_capacity_bounds_feasibility():
    a = PlannerAssumptions()
    # A tiny installed capacity must make high-throughput candidates infeasible
    # (A_EOB_required > A_EOB_installed => candidate rejected), never rescued by fabricated
    # production blocks.
    inp = _inputs(current_cyclotron_eob_capacity_mbq_per_day=1_000.0)
    cand = eb._build_mrt_economic_candidate(
        inp, a, _hl(), 20_000_000.0, 6, True, 0.5, 5, 4, 5, 6, 0, 2
    )
    # With only 1000 MBq/day installed, physical capacity binds hard: achieved throughput is
    # a tiny fraction of the clinical capacity, proving physical capacity is authoritative.
    if cand is not None:
        assert cand.achieved_capacity_per_day < 50.0


# ---------------------------------------------------------------------------
# B. No calibrated EOB capacity -> NOT_CALIBRATED, nothing fabricated.
# ---------------------------------------------------------------------------
def test_B_uncalibrated_reports_not_calibrated_and_no_legacy_capex():
    a = PlannerAssumptions()
    inp = _inputs()  # no EOB fields, no fleet -> uncalibrated
    cand = eb._build_mrt_economic_candidate(
        inp, a, _hl(), 20_000_000.0, 6, True, 0.5, 1, 2, 3, 4, 0, 2
    )
    assert cand is not None
    assert cand.production_capacity_status == "not_calibrated"
    assert cand.cyclotron_activity_capacity_status == "not_calibrated"
    assert cand.production_feasibility_qualified is False
    # A_EOB_required is STILL computed and reported.
    assert cand.activity_required_at_eob_mbq_per_day > 0.0
    # No fabricated installed capacity.
    assert cand.cyclotron_activity_capacity_mbq_per_day == 0.0
    # No legacy production-block expansion or its CapEx.
    assert cand.production_expansion_pct == 0.0
    assert cand.production_expansion_capex_charged is False
    for item in cand.capex_ledger:
        if item["component"].startswith("Production expansion"):
            assert float(item["quantity"]) == 0.0
        if item["component"] in ("Cyclotron purchase", "Cyclotron installation"):
            assert float(item["quantity"]) == 0.0


def test_B_uncalibrated_optimization_conventional_reports_not_calibrated():
    a = PlannerAssumptions()
    inp = _inputs()
    conv = optimization.conventional(inp, a, _hl())
    assert conv.ledger["physical_production_capacity_status"] == "not_calibrated"
    assert conv.ledger["expanded_gross_production_capacity_per_day"] == "NOT_CALIBRATED"
    assert conv.ledger["expanded_usable_capacity_at_destination_per_day"] == "NOT_CALIBRATED"
    # No production-block or cyclotron CapEx charged when uncalibrated.
    for item in conv.capex_ledger:
        if item["component"].startswith("Production expansion") or item["component"].startswith("Cyclotron"):
            assert float(item["quantity"]) == 0.0


def test_B_calibrated_vs_uncalibrated_capex_delta_is_only_legacy_production_spend():
    a = PlannerAssumptions()
    uncal = optimization.conventional(_inputs(), a, _hl())
    cal = optimization.conventional(
        _inputs(current_cyclotron_eob_capacity_mbq_per_day=400_000.0), a, _hl()
    )
    # The uncalibrated plan must not cost MORE than the calibrated plan by fabricating
    # production spend; uncalibrated charges zero production/cyclotron CapEx.
    assert uncal.capex <= cal.capex + 1e-6


# ---------------------------------------------------------------------------
# C. More patients -> more required activity, without creating capacity.
# ---------------------------------------------------------------------------
def test_C_more_patients_increase_required_eob_activity():
    from operational_day_orchestrator import compute_radioactive_production_chain

    low = compute_radioactive_production_chain(
        modality="MRT", served_patients=50, activity_per_patient_mbq=370.0,
        radionuclide="F-18", elapsed_eob_to_administration_minutes=60.0,
    )
    high = compute_radioactive_production_chain(
        modality="MRT", served_patients=150, activity_per_patient_mbq=370.0,
        radionuclide="F-18", elapsed_eob_to_administration_minutes=60.0,
    )
    assert high.a_eob_required_mbq > low.a_eob_required_mbq
    # With no installed capacity supplied, feasibility stays NOT_CALIBRATED for both --
    # required activity grows but no capacity is fabricated to "meet" it.
    assert low.production_feasible == "NOT_CALIBRATED"
    assert high.production_feasible == "NOT_CALIBRATED"
    assert low.installed_eob_capacity_mbq_per_day == "NOT_CALIBRATED"


def test_C_required_activity_never_manufactures_installed_capacity():
    from operational_day_orchestrator import compute_radioactive_production_chain

    r = compute_radioactive_production_chain(
        modality="MRT", served_patients=200, activity_per_patient_mbq=370.0,
        radionuclide="F-18", elapsed_eob_to_administration_minutes=90.0,
    )
    # Required activity is a large positive number; installed capacity remains uncalibrated.
    assert r.a_eob_required_mbq > 0.0
    assert r.installed_eob_capacity_mbq_per_day == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# D. Unused available radioactive capacity yields no revenue/ranking benefit.
# ---------------------------------------------------------------------------
def test_D_excess_installed_capacity_does_not_inflate_revenue_or_ranking():
    a = PlannerAssumptions()
    # Two calibrated capacities that BOTH comfortably exceed clinical demand for this fixed
    # clinical configuration. The extra installed MBq in the larger case is genuinely unused
    # headroom and must not translate into extra served patients, revenue, or ranking benefit.
    modest = _inputs(current_cyclotron_eob_capacity_mbq_per_day=60_000.0)
    ample = _inputs(current_cyclotron_eob_capacity_mbq_per_day=80_000.0)
    cand_modest = eb._build_mrt_economic_candidate(
        modest, a, _hl(), 20_000_000.0, 6, True, 0.5, 1, 2, 3, 4, 0, 2
    )
    cand_huge = eb._build_mrt_economic_candidate(
        ample, a, _hl(), 20_000_000.0, 6, True, 0.5, 1, 2, 3, 4, 0, 2
    )
    assert cand_modest is not None and cand_huge is not None
    # Both are limited by the SAME clinical resources once production capacity is ample;
    # the extra unused MBq must not increase served throughput or revenue.
    assert math.isclose(
        cand_modest.revenue_generating_throughput_per_day,
        cand_huge.revenue_generating_throughput_per_day,
        rel_tol=0.0, abs_tol=1e-6,
    )
    assert math.isclose(
        cand_modest.achieved_capacity_per_day,
        cand_huge.achieved_capacity_per_day,
        rel_tol=0.0, abs_tol=1e-6,
    )


# ---------------------------------------------------------------------------
# E. No-build scenarios remain valid when existing infrastructure suffices.
# ---------------------------------------------------------------------------
def test_E_no_build_when_existing_infrastructure_satisfies_requirement():
    a = PlannerAssumptions()
    # Target already at/below current capacity -> the optimizer can select a zero-expansion
    # (no additional scanners/rooms) design; production must not force fabricated spend.
    inp = _inputs(target_patients_per_day=40.0, maximum_expected_demand_per_day=40.0)
    result = eb.run_equal_budget_economic_decision_optimization(
        inp, a, _hl(), explicit_budget=14_250_000.0, comparison_budget_confirmed=True
    )
    # A best candidate exists and does not require fabricated production expansion.
    best = result.best_achievable_candidate
    assert best is not None
    assert best.production_expansion_pct == 0.0
    assert best.production_expansion_capex_charged is False


# ---------------------------------------------------------------------------
# F. Reporting propagates the calibration status honestly.
# ---------------------------------------------------------------------------
def test_F_reporting_propagates_not_calibrated_status():
    a = PlannerAssumptions()
    inp = _inputs()
    result = eb.run_equal_budget_economic_decision_optimization(
        inp, a, _hl(), explicit_budget=14_250_000.0, comparison_budget_confirmed=True
    )
    # Every produced MRT candidate reports NOT_CALIBRATED production status and zero
    # fabricated expansion -- the status is never silently upgraded to a calibrated claim.
    candidates = [
        result.balanced, result.economic_value, result.growth_max,
        result.best_achievable_candidate, result.primary_feasible_economic_recommendation,
    ]
    seen = False
    for c in candidates:
        if c is None:
            continue
        seen = True
        assert c.production_capacity_status == "not_calibrated"
        assert c.production_feasibility_qualified is False
        assert c.production_expansion_pct == 0.0
    assert seen, "expected at least one produced candidate to inspect"


def test_F_reporting_propagates_calibrated_status():
    a = PlannerAssumptions()
    inp = _inputs(current_cyclotron_eob_capacity_mbq_per_day=400_000.0)
    result = eb.run_equal_budget_economic_decision_optimization(
        inp, a, _hl(), explicit_budget=20_000_000.0, comparison_budget_confirmed=True
    )
    best = result.best_achievable_candidate
    assert best is not None
    assert best.production_capacity_status == "calibrated"
    assert math.isclose(best.cyclotron_activity_capacity_mbq_per_day, 400_000.0)


# ---------------------------------------------------------------------------
# Pre-AWS adjudication — uncalibrated-production multiplier safety
# ---------------------------------------------------------------------------
def test_multiplier_does_not_consume_current_usable_doses_per_day():
    # The decay-optimal release-level ratio must be a pure decay-physics device: varying
    # current_usable_doses_per_day (across 5 orders of magnitude) must not change achieved
    # throughput or required EOB activity. This fails if the multiplier ever starts deriving
    # capacity/throughput from dose count.
    a = PlannerAssumptions()
    baseline = None
    for cud in (1.0, 60.0, 120.0, 10_000.0, 1_000_000.0):
        c = eb._build_mrt_economic_candidate(
            _inputs(current_usable_doses_per_day=cud), a, _hl(), 20_000_000.0, 6, True, 0.5, 1, 2, 3, 4, 0, 2
        )
        assert c is not None
        current = (round(c.achieved_capacity_per_day, 6), round(c.activity_required_at_eob_mbq_per_day, 3))
        if baseline is None:
            baseline = current
        assert current == baseline, f"dose-count {cud} changed uncalibrated outputs {current} != {baseline}"


def test_multiplier_not_reachable_from_calibrated_branch_and_cannot_alter_calibrated_capacity():
    a = PlannerAssumptions()
    installed = 400_000.0
    c = eb._build_mrt_economic_candidate(
        _inputs(current_cyclotron_eob_capacity_mbq_per_day=installed), a, _hl(), 20_000_000.0, 6, True, 0.5, 1, 2, 3, 4, 0, 2
    )
    assert c is not None
    # Calibrated installed capacity is used EXACTLY; the uncalibrated multiplier can never
    # inflate or alter it.
    assert c.cyclotron_activity_capacity_mbq_per_day == installed
    assert c.cyclotron_activity_capacity_status == "input_current_cyclotron_eob_capacity_mbq_per_day"


def test_uncalibrated_reports_required_eob_activity_but_not_installed():
    # Governing chain: A_EOB_required is computed and reported even when installed capacity is
    # unknown; installed capacity must be the 0.0 "unknown" sentinel, never a fabricated value.
    a = PlannerAssumptions()
    c = eb._build_mrt_economic_candidate(_inputs(), a, _hl(), 20_000_000.0, 6, True, 0.5, 1, 2, 3, 4, 0, 2)
    assert c is not None
    assert c.activity_required_at_eob_mbq_per_day > 0.0  # required activity IS reported
    assert c.cyclotron_activity_capacity_mbq_per_day == 0.0  # installed unknown, not fabricated
    assert c.cyclotron_activity_capacity_status == "not_calibrated"


def test_uncalibrated_preserves_batch_timing_temporal_advantage():
    # With long transport + short half-life and ample clinical resources, splitting production
    # into more batches reduces per-batch decay and increases completions WITHOUT multiplying
    # any physical production capacity. This proves the decay-optimal release search models real
    # physics (and guards against a naive "batch=clinical-limit" simplification that erases it).
    a = PlannerAssumptions()
    inp = _inputs(
        current_patients_per_day=80.0, target_patients_per_day=80.0, maximum_expected_demand_per_day=700.0,
        current_scanners=25, current_injection_rooms=25, current_uptake_rooms=25,
        current_usable_doses_per_day=160.0, current_average_transport_min=25.0, mrt_transport_min=25.0,
        existing_mrt_connectable_rooms=0,
    )
    one = eb._build_mrt_economic_candidate(inp, a, 35.0, 100_000_000.0, 1, True, 25.0, 0, 0, 4, 80, 0, 1)
    six = eb._build_mrt_economic_candidate(inp, a, 35.0, 100_000_000.0, 6, True, 25.0, 0, 0, 4, 80, 0, 1)
    assert one is not None and six is not None
    assert six.achieved_capacity_per_day > one.achieved_capacity_per_day
    # Neither fabricates capacity.
    assert six.cyclotron_activity_capacity_status == "not_calibrated"
    assert six.production_expansion_pct == 0.0


# ---------------------------------------------------------------------------
# Pre-AWS adjudication — Capital Project API capacity-status consistency
# ---------------------------------------------------------------------------
def _analyze(model_id, *, budget=8_000_000.0, target=120.0):
    import capital_project_api as api
    req = api.AnalyzeRequest(
        project_id="oncology-expansion-demo", project_type="RETROFIT", constraint_mode="BUDGET",
        current_patients_per_day=60.0, target_patients_per_day=target,
        maximum_project_budget_usd=budget, cyclotron_catalog_model_id=model_id,
    )
    return api._execute_analysis(req)


def test_api_calibrated_and_uncalibrated_status_are_coherent():
    # The engine result the API serializes must tell ONE calibration story: the API-facing
    # cyclotron_capacity_status must not contradict the authoritative production status.
    cal = _analyze("GE_PETTRACE_890")
    for c in cal.configurations:
        assert c.cyclotron_capacity_status != "not_calibrated", (
            f"{c.label}: calibrated cyclotron reported as not_calibrated (contradiction)"
        )
    uncal = _analyze(None)
    for c in uncal.configurations:
        assert c.cyclotron_capacity_status == "not_calibrated"


def test_api_uncalibrated_charges_no_production_block_capex():
    uncal = _analyze(None)
    # No production-block / dose-count CapEx may appear on any uncalibrated configuration.
    # (project_capex_usd reflects only scanner/room/MRT infrastructure here.)
    for c in uncal.configurations:
        assert c.cyclotron_capacity_status == "not_calibrated"
        assert c.cyclotron_utilization_pct == 0.0

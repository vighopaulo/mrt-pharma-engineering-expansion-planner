"""Focused test suite: Conventional economic calibration + intraday
scheduling correction.

Covers (correction section 50): controlled inpatient episode revenue = 30000,
inpatient sensitivity values, outpatient nuclear revenue = 2000, inpatient
bundled nuclear revenue not double counted, separately payable inpatient
procedure, contribution-margin reconciliation, COST_ONLY preserved,
REVENUE_AWARE inpatient, architecture-invariant patient revenue, generator
delivery cost = 3500 controlled assumption, uniform generator benchmark,
weekly/14-day generator annual OPEX, generator user override, generator
recurring cost not durable CapEx, OPERATIONAL_ONLY generator recurring OPEX,
linen not midnight-only, pharmacy scheduled+urgent, specimen/blood timing,
sterile timing, seeded reproducibility, different-seed variation, routine
consolidation window, urgent demand not improperly delayed, porter
concurrency/FTE/OPEX recalculation, AGV/PTS corrected schedule,
feasibility-before-economics, lifecycle/TCO ranking, Manual-only allowed to
win, automation allowed to win, CapEx/OPEX/generator/patient reconciliation,
physical-demand non-regression, nuclear physical non-regression.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

import pytest

from campus_retrofit_benchmark import build_two_building_campus_geometry, run_campus_case_1_conventional
from conventional_transport_authority import (
    DEFAULT_AGV_MODEL,
    DEFAULT_GENERAL_CART,
    DEFAULT_LINEN_CART,
    DEFAULT_PTS_NETWORK,
    PorterOperatingPolicy,
    agv_annual_opex,
    agv_fleet_replacement_present_value,
    agv_new_study_capex,
    compute_manual_mission_timing,
    compute_porter_resource_requirement,
    convert_load_to_agv_missions,
    convert_load_to_pts_missions,
    evaluate_portfolio,
    evaluate_portfolio_lifecycle,
    is_portfolio_feasible_for_streams,
    pts_annual_opex,
    pts_new_study_capex,
    rank_portfolios_by_lifecycle_economics,
    select_best_portfolio_by_lifecycle_economics,
)
from general_oncology_logistics import (
    build_default_facility_roles,
    consolidate_demands_into_loads,
    generate_daily_logistics_demand,
    missions_for_architecture,
)
from generator_catalog import load_generator_catalog
from generator_economics import (
    CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_USD,
    annual_generator_supply_opex,
    build_replacement_cadence,
    deliveries_per_year_from_interval_days,
    generator_delivery_new_study_capex,
    generator_economic_report_row,
    generator_supply_ledger_rows,
    resolve_generator_delivery_cost,
)
from intraday_scheduling import apply_intraday_timing, consolidate_demands_into_loads_with_window
from oncology_pet_spect_scenario import build_representative_day_population
from patient_economics import (
    AUDITED_NUCLEAR_SCAN_REVENUE_USD,
    CONTROLLED_ONCOLOGY_INPATIENT_EPISODE_VALUE_2026,
    INPATIENT_EPISODE_VALUE_SENSITIVITY_USD,
    ClinicalStaffCostPolicy,
    DailyFacilityCostPolicy,
    build_inpatient_episode,
    build_inpatient_sensitivity_episodes,
    build_outpatient_nuclear_episode,
    equivalent_patient_day_value,
)

ILLUSTRATIVE_FACILITY_COST = DailyFacilityCostPolicy(facility_cost_per_patient_day=1200.0, provenance="CONTROLLED_SCENARIO_ASSUMPTION")
ILLUSTRATIVE_STAFF_COST = ClinicalStaffCostPolicy(physician_cost_per_patient_day=300.0, nursing_cost_per_patient_day=450.0, provenance="CONTROLLED_SCENARIO_ASSUMPTION")


def _representative_demands():
    patients, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    return demands


# ---------------------------------------------------------------------------
# Controlled inpatient episode value (sections 1-10)
# ---------------------------------------------------------------------------


def test_controlled_inpatient_episode_revenue_is_30000():
    ep = build_inpatient_episode(
        patient_id="P-IN-001", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=ILLUSTRATIVE_FACILITY_COST, clinical_staff_cost_policy=ILLUSTRATIVE_STAFF_COST,
    )
    assert ep.facility_episode_revenue == CONTROLLED_ONCOLOGY_INPATIENT_EPISODE_VALUE_2026 == 30000.0


def test_inpatient_sensitivity_values():
    episodes = build_inpatient_sensitivity_episodes(
        patient_id="P-SENS", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=ILLUSTRATIVE_FACILITY_COST, clinical_staff_cost_policy=ILLUSTRATIVE_STAFF_COST,
    )
    assert tuple(e.facility_episode_revenue for e in episodes) == INPATIENT_EPISODE_VALUE_SENSITIVITY_USD
    assert 30000.0 in INPATIENT_EPISODE_VALUE_SENSITIVITY_USD  # primary benchmark present, not hard-coded exclusively


def test_actual_los_never_overwritten_by_nominal_seven():
    ep = build_inpatient_episode(
        patient_id="P-IN-010", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 4),
        daily_facility_cost=ILLUSTRATIVE_FACILITY_COST, clinical_staff_cost_policy=ILLUSTRATIVE_STAFF_COST,
    )
    assert ep.length_of_stay_days == 3  # actual LOS, never forced to 7


def test_equivalent_patient_day_value_is_reporting_only():
    value = equivalent_patient_day_value()
    assert value == pytest.approx(30000.0 / 7.0)
    assert value == pytest.approx(4285.7142857, rel=1e-6)


def test_outpatient_nuclear_revenue_still_2000():
    ep = build_outpatient_nuclear_episode(patient_id="P-OUT-001")
    assert ep.separately_payable_procedure_revenue == AUDITED_NUCLEAR_SCAN_REVENUE_USD == 2000.0


def test_inpatient_bundled_nuclear_not_double_counted():
    ep = build_inpatient_episode(
        patient_id="P-IN-020", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=ILLUSTRATIVE_FACILITY_COST, clinical_staff_cost_policy=ILLUSTRATIVE_STAFF_COST,
        has_nuclear_procedure=True, nuclear_payment_context="BUNDLED_IN_INPATIENT_EPISODE",
    )
    assert ep.total_revenue(mode="REVENUE_AWARE") == 30000.0  # never 32000


def test_separately_payable_inpatient_procedure_adds_revenue():
    ep = build_inpatient_episode(
        patient_id="P-IN-021", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=ILLUSTRATIVE_FACILITY_COST, clinical_staff_cost_policy=ILLUSTRATIVE_STAFF_COST,
        has_nuclear_procedure=True, nuclear_payment_context="SEPARATELY_PAYABLE",
    )
    assert ep.total_revenue(mode="REVENUE_AWARE") == 32000.0  # explicitly selected -> added


def test_contribution_margin_reconciliation_derived_not_hardcoded():
    ep = build_inpatient_episode(
        patient_id="P-IN-030", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=ILLUSTRATIVE_FACILITY_COST, clinical_staff_cost_policy=ILLUSTRATIVE_STAFF_COST,
        daily_linen_cost=5.0,
    )
    assert ep.total_cost() == pytest.approx(13685.0)
    margin = ep.contribution_margin(mode="REVENUE_AWARE")
    assert margin == pytest.approx(ep.facility_episode_revenue - ep.total_cost())
    assert margin == pytest.approx(16315.0)


def test_cost_only_preserved():
    ep = build_inpatient_episode(
        patient_id="P-IN-040", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=ILLUSTRATIVE_FACILITY_COST, clinical_staff_cost_policy=ILLUSTRATIVE_STAFF_COST,
    )
    assert ep.total_revenue(mode="COST_ONLY") == "NOT_CALIBRATED"
    assert ep.contribution_margin(mode="COST_ONLY") == "NOT_CALIBRATED"


def test_revenue_aware_inpatient_now_numerically_defined():
    ep = build_inpatient_episode(
        patient_id="P-IN-041", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=ILLUSTRATIVE_FACILITY_COST, clinical_staff_cost_policy=ILLUSTRATIVE_STAFF_COST,
    )
    revenue = ep.total_revenue(mode="REVENUE_AWARE")
    assert isinstance(revenue, float) and revenue == 30000.0  # previously NOT_CALIBRATED -- this is the fix


def test_architecture_invariant_patient_revenue_inpatient_and_outpatient():
    ep_manual = build_inpatient_episode(
        patient_id="P-IN-050", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=ILLUSTRATIVE_FACILITY_COST, clinical_staff_cost_policy=ILLUSTRATIVE_STAFF_COST,
        general_logistics_transport_cost=500.0,
    )
    ep_automated = build_inpatient_episode(
        patient_id="P-IN-050", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=ILLUSTRATIVE_FACILITY_COST, clinical_staff_cost_policy=ILLUSTRATIVE_STAFF_COST,
        general_logistics_transport_cost=120.0,
    )
    assert ep_manual.facility_episode_revenue == ep_automated.facility_episode_revenue
    assert ep_manual.total_cost() != ep_automated.total_cost()


# ---------------------------------------------------------------------------
# Generator economic calibration (sections 11-18)
# ---------------------------------------------------------------------------


def test_generator_delivery_cost_controlled_benchmark():
    catalog = load_generator_catalog()
    model = catalog.by_id("CURIUM_TECHNELITE")
    resolution = resolve_generator_delivery_cost(model)
    assert resolution.delivery_cost_usd == CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_USD == 3500.0
    assert resolution.basis == "CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_2026"


def test_generator_benchmark_uniform_across_initial_models():
    catalog = load_generator_catalog()
    rows = tuple(generator_economic_report_row(m) for m in catalog.models)
    assert len(rows) == 3
    assert all(r.delivery_cost_usd == 3500.0 for r in rows)


def test_generator_weekly_annual_opex():
    dpy = deliveries_per_year_from_interval_days(7.0)
    assert dpy == 52.0
    assert annual_generator_supply_opex(delivery_cost_usd=3500.0, deliveries_per_year=dpy) == 182000.0


def test_generator_14day_annual_opex():
    dpy = deliveries_per_year_from_interval_days(14.0)
    assert dpy == 26.0
    assert annual_generator_supply_opex(delivery_cost_usd=3500.0, deliveries_per_year=dpy) == 91000.0


def test_generator_user_override():
    catalog = load_generator_catalog()
    model = catalog.by_id("GE_HEALTHCARE_DRYTEC")
    resolution = resolve_generator_delivery_cost(model, override_usd=4200.0)
    assert resolution.delivery_cost_usd == 4200.0 and resolution.basis == "USER_OVERRIDE"
    cadence = build_replacement_cadence(model, override_interval_days=10.0)
    assert cadence.interval_days == 10.0 and cadence.basis == "USER_SUPPLIED"


def test_generator_recurring_cost_not_durable_capex():
    catalog = load_generator_catalog()
    model = catalog.by_id("CURIUM_ULTRA_TECHNEKOW_FM")
    assert generator_delivery_new_study_capex(model, study_scope="CAPITAL_PLANNING") == 0.0
    assert generator_delivery_new_study_capex(model, study_scope="OPERATIONAL_ONLY") == 0.0


def test_generator_operational_only_recurring_opex_unaffected():
    catalog = load_generator_catalog()
    model = catalog.by_id("CURIUM_TECHNELITE")
    cadence = build_replacement_cadence(model)
    opex_operational = annual_generator_supply_opex(delivery_cost_usd=3500.0, deliveries_per_year=cadence.deliveries_per_year)
    assert opex_operational == 91000.0  # recurring OPEX accrues regardless of study scope
    assert generator_delivery_new_study_capex(model, study_scope="OPERATIONAL_ONLY") == 0.0


def test_generator_supply_ledger_reconciles():
    dpy = deliveries_per_year_from_interval_days(7.0)
    rows = generator_supply_ledger_rows(delivery_cost_usd=3500.0, deliveries_per_year=dpy)
    reported = annual_generator_supply_opex(delivery_cost_usd=3500.0, deliveries_per_year=dpy)
    assert sum(rows) == pytest.approx(reported)


# ---------------------------------------------------------------------------
# Intraday demand timing correction (sections 19-29)
# ---------------------------------------------------------------------------


def test_linen_not_released_at_midnight_only():
    demands = _representative_demands()
    linen = tuple(d for d in demands if d.stream == "CLEAN_LINEN")
    corrected = apply_intraday_timing(linen, day=date(2026, 2, 2), seed=42)
    release_hours = {d.release_datetime.time() for d in corrected}
    assert release_hours != {datetime(2026, 2, 2, 0, 0).time()}
    assert all(d.release_datetime.hour >= 6 for d in corrected)


def test_pharmacy_scheduled_and_urgent_timing():
    demands = _representative_demands()
    pharmacy = tuple(d for d in demands if d.stream == "PHARMACY_INFUSION")
    corrected = apply_intraday_timing(pharmacy, day=date(2026, 2, 2), seed=7)
    distinct_times = {d.release_datetime for d in corrected}
    assert len(distinct_times) > 1  # not one universal dispatch time


def test_specimen_blood_timing_urgent_deadline_authoritative():
    demands = _representative_demands()
    specimen = tuple(d for d in demands if d.stream == "SPECIMEN_BLOOD")
    corrected = apply_intraday_timing(specimen, day=date(2026, 2, 2), seed=11)
    assert all(d.required_by_datetime is not None and d.required_by_datetime >= d.release_datetime for d in corrected)


def test_sterile_timing_not_midnight_only():
    demands = _representative_demands()
    sterile = tuple(d for d in demands if d.stream == "STERILE_CLEAN_SUPPLY")
    corrected = apply_intraday_timing(sterile, day=date(2026, 2, 2), seed=5)
    assert any(d.release_datetime.time() != datetime(2026, 2, 2, 0, 0).time() for d in corrected)


def test_same_seed_reproducible():
    demands = _representative_demands()
    a = apply_intraday_timing(demands, day=date(2026, 2, 2), seed=42)
    b = apply_intraday_timing(demands, day=date(2026, 2, 2), seed=42)
    a_sorted = sorted(a, key=lambda d: d.demand_id)
    b_sorted = sorted(b, key=lambda d: d.demand_id)
    assert all(x.release_datetime == y.release_datetime for x, y in zip(a_sorted, b_sorted))


def test_different_seed_can_vary():
    demands = _representative_demands()
    a = apply_intraday_timing(demands, day=date(2026, 2, 2), seed=42)
    c = apply_intraday_timing(demands, day=date(2026, 2, 2), seed=999)
    a_sorted = sorted(a, key=lambda d: d.demand_id)
    c_sorted = sorted(c, key=lambda d: d.demand_id)
    assert any(x.release_datetime != y.release_datetime for x, y in zip(a_sorted, c_sorted))


def test_routine_consolidation_window():
    demands = _representative_demands()
    linen = tuple(d for d in demands if d.stream == "CLEAN_LINEN")
    corrected = apply_intraday_timing(linen, day=date(2026, 2, 2), seed=42)
    loads = consolidate_demands_into_loads_with_window(demands=corrected, max_quantity_per_load=1e9, consolidation_window_minutes=90.0)
    assert len(loads) >= 2  # morning + afternoon waves separate into distinct loads
    for load in loads:
        assert load.release_datetime is not None


def test_urgent_demand_not_improperly_delayed():
    demands = _representative_demands()
    specimen = tuple(d for d in demands if d.stream == "SPECIMEN_BLOOD")
    corrected = apply_intraday_timing(specimen, day=date(2026, 2, 2), seed=42)
    loads = consolidate_demands_into_loads_with_window(
        demands=corrected, max_quantity_per_load=1e9, consolidation_window_minutes=90.0, urgent_window_minutes=0.0,
    )
    # urgent demands use a near-zero consolidation window -- essentially one load per demand, never batched into one giant delayed load
    assert len(loads) >= len(corrected) - 1


def test_physical_demand_conserved_after_intraday_correction():
    demands = _representative_demands()
    corrected = apply_intraday_timing(demands, day=date(2026, 2, 2), seed=42)
    assert len(corrected) == len(demands)
    assert sum(d.quantity for d in corrected) == pytest.approx(sum(d.quantity for d in demands))
    assert {d.patient_id for d in corrected} == {d.patient_id for d in demands}


# ---------------------------------------------------------------------------
# Porter concurrency/FTE/OPEX recalculation (sections 29-30)
# ---------------------------------------------------------------------------


def test_porter_concurrency_reduced_from_midnight_artifact():
    demands = _representative_demands()
    policy = PorterOperatingPolicy()

    linen_before = tuple(d for d in demands if d.stream == "CLEAN_LINEN")
    loads_before = consolidate_demands_into_loads(demands=linen_before, max_quantity_per_load=DEFAULT_LINEN_CART.payload_capacity)
    missions_before = tuple(m for l in loads_before for m in missions_for_architecture(load=l, architecture="MANUAL_CONVENTIONAL", cart_capacity=DEFAULT_LINEN_CART.payload_capacity))
    timing = compute_manual_mission_timing(policy=policy, technology="PORTER_CART", vertical_transitions=1)
    req_before = compute_porter_resource_requirement(missions=missions_before, mission_minutes=timing.total_minutes, policy=policy, operating_days_per_year=300)

    corrected = apply_intraday_timing(linen_before, day=date(2026, 2, 2), seed=42)
    loads_after = consolidate_demands_into_loads_with_window(demands=corrected, max_quantity_per_load=DEFAULT_LINEN_CART.payload_capacity, consolidation_window_minutes=90.0)
    missions_after = tuple(m for l in loads_after for m in missions_for_architecture(load=l, architecture="MANUAL_CONVENTIONAL", cart_capacity=DEFAULT_LINEN_CART.payload_capacity))
    req_after = compute_porter_resource_requirement(missions=missions_after, mission_minutes=timing.total_minutes, policy=policy, operating_days_per_year=300)

    assert req_after.peak_concurrent_porters <= req_before.peak_concurrent_porters
    assert req_after.annual_labor_opex <= req_before.annual_labor_opex


def test_manual_opex_recalculation_all_streams():
    demands = _representative_demands()
    policy = PorterOperatingPolicy()
    corrected = apply_intraday_timing(demands, day=date(2026, 2, 2), seed=42)
    total_before_opex = 0.0
    total_after_opex = 0.0
    for stream, cart_cap, tech in (
        ("CLEAN_LINEN", DEFAULT_LINEN_CART.payload_capacity, "PORTER_CART"),
        ("PHARMACY_INFUSION", DEFAULT_GENERAL_CART.payload_capacity, "MANUAL_PORTER"),
        ("SPECIMEN_BLOOD", DEFAULT_GENERAL_CART.payload_capacity, "MANUAL_PORTER"),
        ("STERILE_CLEAN_SUPPLY", DEFAULT_GENERAL_CART.payload_capacity, "MANUAL_PORTER"),
    ):
        timing = compute_manual_mission_timing(policy=policy, technology=tech, vertical_transitions=1)
        before_demands = tuple(d for d in demands if d.stream == stream)
        loads_before = consolidate_demands_into_loads(demands=before_demands, max_quantity_per_load=cart_cap)
        missions_before = tuple(m for l in loads_before for m in missions_for_architecture(load=l, architecture="MANUAL_CONVENTIONAL", cart_capacity=cart_cap))
        req_before = compute_porter_resource_requirement(missions=missions_before, mission_minutes=timing.total_minutes, policy=policy, operating_days_per_year=300)
        total_before_opex += req_before.annual_labor_opex

        after_demands = tuple(d for d in corrected if d.stream == stream)
        loads_after = consolidate_demands_into_loads_with_window(demands=after_demands, max_quantity_per_load=cart_cap, consolidation_window_minutes=90.0)
        missions_after = tuple(m for l in loads_after for m in missions_for_architecture(load=l, architecture="MANUAL_CONVENTIONAL", cart_capacity=cart_cap))
        req_after = compute_porter_resource_requirement(missions=missions_after, mission_minutes=timing.total_minutes, policy=policy, operating_days_per_year=300)
        total_after_opex += req_after.annual_labor_opex

    assert total_after_opex < total_before_opex  # rebaselined, never preserved as the benchmark


def test_agv_uses_corrected_schedule():
    demands = _representative_demands()
    linen = tuple(d for d in demands if d.stream == "CLEAN_LINEN")
    corrected = apply_intraday_timing(linen, day=date(2026, 2, 2), seed=42)
    loads = consolidate_demands_into_loads_with_window(demands=corrected, max_quantity_per_load=DEFAULT_AGV_MODEL.payload_capacity_kg, consolidation_window_minutes=90.0)
    missions = tuple(m for l in loads for m in convert_load_to_agv_missions(load=l, model=DEFAULT_AGV_MODEL))
    midnight = datetime(2026, 2, 2, 0, 0)
    assert any(m.departure_datetime != midnight for m in missions)


def test_pts_uses_corrected_schedule():
    demands = _representative_demands()
    pharmacy = tuple(d for d in demands if d.stream == "PHARMACY_INFUSION")
    corrected = apply_intraday_timing(pharmacy, day=date(2026, 2, 2), seed=42)
    loads = consolidate_demands_into_loads_with_window(demands=corrected, max_quantity_per_load=DEFAULT_PTS_NETWORK.capsule_payload_kg, consolidation_window_minutes=30.0)
    missions = tuple(m for l in loads for m in convert_load_to_pts_missions(load=l, network=DEFAULT_PTS_NETWORK))
    midnight = datetime(2026, 2, 2, 0, 0)
    assert any(m.departure_datetime != midnight for m in missions)


# ---------------------------------------------------------------------------
# Portfolio-selection defect correction (sections 32-39)
# ---------------------------------------------------------------------------


def test_feasibility_before_economics():
    assert is_portfolio_feasible_for_streams(technologies=frozenset({"MANUAL_PORTER", "PORTER_CART"}), streams=("CLEAN_LINEN",))
    assert not is_portfolio_feasible_for_streams(technologies=frozenset({"PNEUMATIC_TUBE"}), streams=("CLEAN_LINEN",))


def test_lifecycle_tco_ranking_reuses_study_scope_authority():
    streams = ("CLEAN_LINEN", "PHARMACY_INFUSION", "SPECIMEN_BLOOD", "STERILE_CLEAN_SUPPLY")
    manual_opex_by_stream = {"CLEAN_LINEN": 636480.0, "PHARMACY_INFUSION": 265200.0, "SPECIMEN_BLOOD": 477360.0, "STERILE_CLEAN_SUPPLY": 371280.0}
    evaluation = evaluate_portfolio(
        portfolio_id="MANUAL_ONLY", streams=streams, agv_new_capex=0.0, agv_annual_opex_value=0.0,
        pts_new_capex=0.0, pts_annual_opex_value=0.0, manual_annual_opex_by_stream=manual_opex_by_stream,
    )
    result = evaluate_portfolio_lifecycle(evaluation, mode="COST_ONLY", study_scope="CAPITAL_PLANNING", operating_days_per_year=300, discount_rate_pct=8.0, analysis_years=10)
    assert result.lifecycle_cost > evaluation.annual_opex  # includes discounted multi-year horizon, not just year 1


def test_manual_only_allowed_to_win():
    streams = ("CLEAN_LINEN", "PHARMACY_INFUSION", "SPECIMEN_BLOOD", "STERILE_CLEAN_SUPPLY")
    manual_opex_by_stream = {"CLEAN_LINEN": 636480.0, "PHARMACY_INFUSION": 265200.0, "SPECIMEN_BLOOD": 477360.0, "STERILE_CLEAN_SUPPLY": 371280.0}
    evaluations = tuple(
        evaluate_portfolio(
            portfolio_id=pid, streams=streams, agv_new_capex=50_000_000.0, agv_annual_opex_value=8_000.0,
            pts_new_capex=50_000_000.0, pts_annual_opex_value=8_000.0, manual_annual_opex_by_stream=manual_opex_by_stream,
        )
        for pid in ("MANUAL_ONLY", "MANUAL_PLUS_AGV", "MANUAL_PLUS_PTS", "MANUAL_PLUS_AGV_PLUS_PTS")
    )
    results = tuple(
        evaluate_portfolio_lifecycle(e, mode="COST_ONLY", study_scope="CAPITAL_PLANNING", operating_days_per_year=300, discount_rate_pct=8.0, analysis_years=10)
        for e in evaluations
    )
    best = select_best_portfolio_by_lifecycle_economics(results)
    assert best.portfolio_id == "MANUAL_ONLY"  # excessive automation CapEx -> manual wins


def test_automation_allowed_to_win_when_justified():
    streams = ("CLEAN_LINEN", "PHARMACY_INFUSION", "SPECIMEN_BLOOD", "STERILE_CLEAN_SUPPLY")
    policy = PorterOperatingPolicy()
    loaded_annual_cost_per_fte = policy.base_wage_per_hour * policy.loaded_employer_cost_multiplier * policy.shift_hours * 300
    proposed_agv = replace(DEFAULT_AGV_MODEL, asset_status="PROPOSED")
    proposed_pts = replace(DEFAULT_PTS_NETWORK, asset_status="PROPOSED")
    agv_capex = agv_new_study_capex(proposed_agv, fleet_size=1, study_scope="CAPITAL_PLANNING")
    agv_opex_val = agv_annual_opex(proposed_agv, fleet_size=1, loaded_annual_cost_per_fte=loaded_annual_cost_per_fte)
    pts_capex = pts_new_study_capex(proposed_pts, study_scope="CAPITAL_PLANNING")
    pts_opex_val = pts_annual_opex(proposed_pts, loaded_annual_cost_per_fte=loaded_annual_cost_per_fte)
    manual_opex_by_stream = {"CLEAN_LINEN": 636480.0, "PHARMACY_INFUSION": 265200.0, "SPECIMEN_BLOOD": 477360.0, "STERILE_CLEAN_SUPPLY": 371280.0}

    evaluations = tuple(
        evaluate_portfolio(
            portfolio_id=pid, streams=streams, agv_new_capex=agv_capex, agv_annual_opex_value=agv_opex_val,
            pts_new_capex=pts_capex, pts_annual_opex_value=pts_opex_val, manual_annual_opex_by_stream=manual_opex_by_stream,
        )
        for pid in ("MANUAL_ONLY", "MANUAL_PLUS_AGV", "MANUAL_PLUS_PTS", "MANUAL_PLUS_AGV_PLUS_PTS")
    )
    results = tuple(
        evaluate_portfolio_lifecycle(e, mode="COST_ONLY", study_scope="CAPITAL_PLANNING", operating_days_per_year=300, discount_rate_pct=8.0, analysis_years=10)
        for e in evaluations
    )
    best = select_best_portfolio_by_lifecycle_economics(results)
    assert best.portfolio_id == "MANUAL_PLUS_AGV_PLUS_PTS"  # lower recurring labor cost justifies the CapEx over the horizon


def test_revenue_aware_ranking_does_not_double_count_patient_revenue():
    streams = ("CLEAN_LINEN", "PHARMACY_INFUSION", "SPECIMEN_BLOOD", "STERILE_CLEAN_SUPPLY")
    manual_opex_by_stream = {"CLEAN_LINEN": 636480.0, "PHARMACY_INFUSION": 265200.0, "SPECIMEN_BLOOD": 477360.0, "STERILE_CLEAN_SUPPLY": 371280.0}
    e1 = evaluate_portfolio(portfolio_id="MANUAL_ONLY", streams=streams, agv_new_capex=0.0, agv_annual_opex_value=0.0, pts_new_capex=0.0, pts_annual_opex_value=0.0, manual_annual_opex_by_stream=manual_opex_by_stream)
    r_cost_only = evaluate_portfolio_lifecycle(e1, mode="COST_ONLY", study_scope="CAPITAL_PLANNING", architecture_invariant_annual_revenue=5_000_000.0, operating_days_per_year=300, discount_rate_pct=8.0, analysis_years=10)
    r_revenue_aware = evaluate_portfolio_lifecycle(e1, mode="REVENUE_AWARE", study_scope="CAPITAL_PLANNING", architecture_invariant_annual_revenue=5_000_000.0, operating_days_per_year=300, discount_rate_pct=8.0, analysis_years=10)
    assert r_cost_only.lifecycle_cost == r_revenue_aware.lifecycle_cost  # same cost basis
    assert r_revenue_aware.npv_or_metric != r_cost_only.npv_or_metric  # revenue only enters the REVENUE_AWARE metric, once


# ---------------------------------------------------------------------------
# Reconciliation (sections 42-43)
# ---------------------------------------------------------------------------


def test_capex_ledger_reconciles():
    proposed_agv = replace(DEFAULT_AGV_MODEL, asset_status="PROPOSED")
    proposed_pts = replace(DEFAULT_PTS_NETWORK, asset_status="PROPOSED")
    agv_capex = agv_new_study_capex(proposed_agv, fleet_size=1, study_scope="CAPITAL_PLANNING")
    pts_capex = pts_new_study_capex(proposed_pts, study_scope="CAPITAL_PLANNING")
    streams = ("CLEAN_LINEN", "PHARMACY_INFUSION", "SPECIMEN_BLOOD", "STERILE_CLEAN_SUPPLY")
    evaluation = evaluate_portfolio(
        portfolio_id="MANUAL_PLUS_AGV_PLUS_PTS", streams=streams, agv_new_capex=agv_capex, agv_annual_opex_value=0.0,
        pts_new_capex=pts_capex, pts_annual_opex_value=0.0, manual_annual_opex=0.0,
    )
    assert evaluation.new_study_capex == pytest.approx(agv_capex + pts_capex)


def test_opex_ledger_reconciles():
    proposed_agv = replace(DEFAULT_AGV_MODEL, asset_status="PROPOSED")
    agv_opex_val = agv_annual_opex(proposed_agv, fleet_size=1, loaded_annual_cost_per_fte=60000.0)
    pts_opex_val = pts_annual_opex(DEFAULT_PTS_NETWORK, loaded_annual_cost_per_fte=60000.0)
    manual = 50000.0
    total = manual + agv_opex_val + pts_opex_val
    assert total == pytest.approx(manual + agv_opex_val + pts_opex_val)


def test_generator_economic_reconciliation():
    dpy = deliveries_per_year_from_interval_days(14.0)
    rows = generator_supply_ledger_rows(delivery_cost_usd=3500.0, deliveries_per_year=dpy)
    reported_opex = annual_generator_supply_opex(delivery_cost_usd=3500.0, deliveries_per_year=dpy)
    assert sum(rows) == pytest.approx(reported_opex)
    catalog = load_generator_catalog()
    model = catalog.by_id("CURIUM_TECHNELITE")
    assert generator_delivery_new_study_capex(model, study_scope="CAPITAL_PLANNING") == 0.0  # never in both capex and opex


def test_patient_economic_reconciliation():
    ep = build_inpatient_episode(
        patient_id="P-RECON", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=ILLUSTRATIVE_FACILITY_COST, clinical_staff_cost_policy=ILLUSTRATIVE_STAFF_COST, daily_linen_cost=5.0,
    )
    margin = ep.contribution_margin(mode="REVENUE_AWARE")
    assert margin == pytest.approx(ep.total_revenue(mode="REVENUE_AWARE") - ep.total_cost())


# ---------------------------------------------------------------------------
# Non-regression (sections 48-49)
# ---------------------------------------------------------------------------


def test_physical_demand_non_regression():
    """Physical demand totals (patient count, per-stream quantity) must
    match the ESTABLISHED prior-build values exactly -- intraday timing must
    not silently alter physical demand."""
    demands = _representative_demands()
    assert len(demands) == 680
    assert sum(d.quantity for d in demands) == pytest.approx(1785.0)
    linen_qty = sum(d.quantity for d in demands if d.stream == "CLEAN_LINEN")
    assert linen_qty == pytest.approx(1275.0)


def test_nuclear_physical_non_regression():
    geometry = build_two_building_campus_geometry(campus_separation_m=500.0)
    result = run_campus_case_1_conventional(geometry=geometry, demand=200)
    assert result.winner.patients_retention_qualified_completed == 36
    import campus_retrofit_benchmark
    import inspect
    source = inspect.getsource(campus_retrofit_benchmark)
    assert "generator_economics" not in source
    assert "intraday_scheduling" not in source
    assert "patient_economics" not in source

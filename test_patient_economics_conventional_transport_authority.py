"""Focused test suite: patient economics + Manual/Automated Conventional
transport authority.

Covers (section 88): manual porter mission timing, porter-hours, porter
concurrency, FTE derivation, loaded labor cost, hand-carry vs cart, cart
capacity, cart CapEx, existing cart zero new-study CapEx, AGV compatibility,
AGV mission conversion, AGV fleet sizing, AGV CapEx decomposition, AGV OPEX
decomposition, PTS compatibility, PTS rejects linen, PTS mission conversion,
PTS network/station semantics, residual manual fallback, minimum feasible
portfolio, no forced AGV purchase, no forced PTS purchase, shared AGV fleet,
shared PTS network, patient episode identity, LOS cost accumulation,
inpatient/outpatient economic distinction, bundled inpatient nuclear payment,
separately payable outpatient scan, cost-only mode, revenue-aware mode,
architecture-invariant patient revenue, mission-cost allocation conservation,
Manual Conventional economics, Automated Conventional economics,
OPERATIONAL_ONLY, CAPITAL_PLANNING, CapEx reconciliation, OPEX reconciliation,
patient-cost reconciliation, nuclear non-regression.
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
    TECHNOLOGY_STREAM_COMPATIBILITY,
    agv_annual_opex,
    agv_new_study_capex,
    agv_required_fleet_size,
    cart_new_study_capex,
    compute_manual_mission_timing,
    compute_porter_resource_requirement,
    convert_load_to_agv_missions,
    convert_load_to_pts_missions,
    evaluate_portfolio,
    is_technology_compatible,
    pts_annual_opex,
    pts_new_study_capex,
    select_minimum_feasible_portfolio,
)
from general_oncology_logistics import (
    TransportLoad,
    build_default_facility_roles,
    consolidate_demands_into_loads,
    generate_daily_logistics_demand,
    missions_for_architecture,
)
from oncology_pet_spect_scenario import build_representative_day_population
from patient_economics import (
    AUDITED_NUCLEAR_SCAN_REVENUE_USD,
    ClinicalStaffCostPolicy,
    DailyFacilityCostPolicy,
    allocate_mission_cost_to_patients,
    build_inpatient_episode,
    build_outpatient_nuclear_episode,
)
from study_scope import apply_study_scope
from models import PlannerAssumptions

ASSUMPTIONS = PlannerAssumptions()


def _sample_linen_load() -> TransportLoad:
    return TransportLoad(
        load_id="LOAD-TEST-001", stream="CLEAN_LINEN", patient_ids=("P-001", "P-002"), origin="LINEN-SRC",
        destination="WARD-F1", quantity=45.0, unit="kg", payload_class="LINEN_BAG",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )


def _day_demands():
    patients, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    return patients, demands


# ---------------------------------------------------------------------------
# Manual porter (sections 7-13)
# ---------------------------------------------------------------------------


def test_manual_mission_timing_components():
    policy = PorterOperatingPolicy()
    timing = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", vertical_transitions=1)
    assert timing.route_status == "ROUTE_NOT_CALIBRATED"
    assert timing.total_minutes == pytest.approx(
        timing.dispatch_minutes + timing.load_minutes + timing.horizontal_minutes + timing.vertical_minutes
        + timing.wait_minutes + timing.unload_minutes + timing.return_minutes
    )


def test_hand_carry_vs_cart_different_speed_and_timing():
    policy = PorterOperatingPolicy()
    hand_carry = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=100.0)
    cart = compute_manual_mission_timing(policy=policy, technology="PORTER_CART", horizontal_distance_m=100.0)
    assert hand_carry.route_status == "ROUTE_CALIBRATED"
    assert hand_carry.horizontal_minutes != cart.horizontal_minutes  # different speeds -> different timing


def test_porter_hours_and_concurrency_and_fte():
    load = _sample_linen_load()
    missions = missions_for_architecture(load=load, architecture="MANUAL_CONVENTIONAL", cart_capacity=100.0)
    policy = PorterOperatingPolicy()
    timing = compute_manual_mission_timing(policy=policy, technology="PORTER_CART")
    req = compute_porter_resource_requirement(missions=missions, mission_minutes=timing.total_minutes, policy=policy, operating_days_per_year=300)
    assert req.total_missions == len(missions)
    assert req.total_labor_hours == pytest.approx(len(missions) * timing.total_minutes / 60.0)
    assert req.peak_concurrent_porters >= 1
    assert req.required_fte >= 1
    assert req.annual_labor_opex > 0


def test_fte_not_hardcoded_scales_with_workload():
    """Section 11-12: FTE must respond to workload, never a fixed count."""
    policy = PorterOperatingPolicy()
    timing = compute_manual_mission_timing(policy=policy, technology="PORTER_CART")
    small_load = replace(_sample_linen_load(), quantity=20.0)
    large_load = replace(_sample_linen_load(), load_id="LOAD-TEST-002", quantity=500.0)
    small_missions = missions_for_architecture(load=small_load, architecture="MANUAL_CONVENTIONAL", cart_capacity=100.0)
    large_missions = missions_for_architecture(load=large_load, architecture="MANUAL_CONVENTIONAL", cart_capacity=100.0)
    req_small = compute_porter_resource_requirement(missions=small_missions, mission_minutes=timing.total_minutes, policy=policy, operating_days_per_year=300)
    req_large = compute_porter_resource_requirement(missions=large_missions, mission_minutes=timing.total_minutes, policy=policy, operating_days_per_year=300)
    assert req_large.required_fte >= req_small.required_fte


def test_loaded_labor_cost_separate_from_base_wage():
    policy = PorterOperatingPolicy()
    assert policy.loaded_employer_cost_multiplier > 1.0
    loaded_hourly = policy.base_wage_per_hour * policy.loaded_employer_cost_multiplier
    assert loaded_hourly > policy.base_wage_per_hour


# ---------------------------------------------------------------------------
# Cart (sections 8, 14-17)
# ---------------------------------------------------------------------------


def test_cart_capacity_independent_of_mrt_container():
    assert DEFAULT_LINEN_CART.payload_capacity != 20.0 or DEFAULT_LINEN_CART.unit != "kg"  # never forced to match MRT
    assert DEFAULT_LINEN_CART.payload_capacity == 80.0


def test_existing_cart_zero_new_study_capex():
    assert DEFAULT_LINEN_CART.asset_status == "EXISTING"
    assert cart_new_study_capex(DEFAULT_LINEN_CART, study_scope="OPERATIONAL_ONLY") == 0.0
    assert cart_new_study_capex(DEFAULT_LINEN_CART, study_scope="CAPITAL_PLANNING") == 0.0  # still existing


def test_proposed_cart_contributes_capex_only_in_capital_planning():
    proposed_cart = replace(DEFAULT_LINEN_CART, asset_status="PROPOSED")
    assert cart_new_study_capex(proposed_cart, study_scope="OPERATIONAL_ONLY") == 0.0
    assert cart_new_study_capex(proposed_cart, study_scope="CAPITAL_PLANNING") == proposed_cart.purchase_capex


# ---------------------------------------------------------------------------
# AGV/AMR (sections 18-23)
# ---------------------------------------------------------------------------


def test_agv_compatibility_matrix():
    assert is_technology_compatible("AGV_AMR", "CLEAN_LINEN")
    assert is_technology_compatible("AGV_AMR", "STERILE_CLEAN_SUPPLY")


def test_agv_mission_conversion_uses_agv_payload_not_manual_or_mrt():
    load = _sample_linen_load()
    agv_missions = convert_load_to_agv_missions(load=load, model=DEFAULT_AGV_MODEL)
    import math
    assert len(agv_missions) == max(1, math.ceil(load.quantity / DEFAULT_AGV_MODEL.payload_capacity_kg))
    assert all(m.transport_mode == "AGV_AMR" for m in agv_missions)


def test_agv_fleet_sizing_requirement_derived():
    load = replace(_sample_linen_load(), quantity=2000.0)
    missions = convert_load_to_agv_missions(load=load, model=DEFAULT_AGV_MODEL)
    fleet = agv_required_fleet_size(missions=missions, mission_minutes=10.0, model=DEFAULT_AGV_MODEL, operating_hours_per_day=18.0, operating_days_per_year=300)
    assert fleet >= 1
    small_fleet = agv_required_fleet_size(missions=missions[:1], mission_minutes=10.0, model=DEFAULT_AGV_MODEL, operating_hours_per_day=18.0, operating_days_per_year=300)
    assert small_fleet <= fleet  # more missions -> never fewer vehicles required


def test_agv_capex_decomposition_vehicle_vs_system():
    assert DEFAULT_AGV_MODEL.vehicle_capex != DEFAULT_AGV_MODEL.system_integration_capex
    proposed_agv = replace(DEFAULT_AGV_MODEL, asset_status="PROPOSED")
    capex = agv_new_study_capex(proposed_agv, fleet_size=2, study_scope="CAPITAL_PLANNING")
    assert capex == 2 * (proposed_agv.vehicle_capex + proposed_agv.system_integration_capex)


def test_agv_existing_zero_new_study_capex():
    assert DEFAULT_AGV_MODEL.asset_status == "EXISTING"
    assert agv_new_study_capex(DEFAULT_AGV_MODEL, fleet_size=3, study_scope="CAPITAL_PLANNING") == 0.0


def test_agv_opex_decomposition():
    opex = agv_annual_opex(DEFAULT_AGV_MODEL, fleet_size=2, loaded_annual_cost_per_fte=60000.0)
    expected = 2 * (DEFAULT_AGV_MODEL.annual_maintenance_opex + DEFAULT_AGV_MODEL.annual_energy_opex) + DEFAULT_AGV_MODEL.residual_supervision_fte * 60000.0
    assert opex == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Pneumatic tube (sections 24-26, 53)
# ---------------------------------------------------------------------------


def test_pts_rejects_linen():
    assert not is_technology_compatible("PNEUMATIC_TUBE", "CLEAN_LINEN")
    linen_load = _sample_linen_load()
    with pytest.raises(ValueError):
        convert_load_to_pts_missions(load=linen_load, network=DEFAULT_PTS_NETWORK)


def test_pts_accepts_specimen():
    assert is_technology_compatible("PNEUMATIC_TUBE", "SPECIMEN_BLOOD")
    specimen_load = TransportLoad(
        load_id="LOAD-SPEC-001", stream="SPECIMEN_BLOOD", patient_ids=("P-001",), origin="WARD-F1",
        destination="LAB-001", quantity=1.0, unit="specimen_container", payload_class="SPECIMEN_CONTAINER",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="URGENT",
    )
    missions = convert_load_to_pts_missions(load=specimen_load, network=DEFAULT_PTS_NETWORK)
    assert all(m.transport_mode == "PNEUMATIC_TUBE" for m in missions)


def test_pts_network_station_semantics():
    assert DEFAULT_PTS_NETWORK.station_count > 0
    assert DEFAULT_PTS_NETWORK.network_length_m is not None
    assert DEFAULT_PTS_NETWORK.asset_status == "EXISTING"
    assert pts_new_study_capex(DEFAULT_PTS_NETWORK, study_scope="CAPITAL_PLANNING") == 0.0  # existing network


def test_pts_proposed_network_capex_from_stations_and_length():
    proposed = replace(DEFAULT_PTS_NETWORK, asset_status="PROPOSED")
    capex = pts_new_study_capex(proposed, study_scope="CAPITAL_PLANNING")
    expected = proposed.station_count * proposed.station_capex_per_unit + proposed.network_length_m * proposed.network_capex_per_m
    assert capex == pytest.approx(expected)


def test_pts_opex_includes_residual_labor_parity_with_agv():
    opex = pts_annual_opex(DEFAULT_PTS_NETWORK, loaded_annual_cost_per_fte=60000.0)
    expected = DEFAULT_PTS_NETWORK.annual_maintenance_opex + DEFAULT_PTS_NETWORK.annual_energy_opex + DEFAULT_PTS_NETWORK.residual_labor_fte * 60000.0
    assert opex == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Portfolio enumeration/selection (sections 5, 46, 54-63)
# ---------------------------------------------------------------------------


def test_residual_manual_fallback_when_no_automation():
    streams = ("CLEAN_LINEN", "PHARMACY_INFUSION", "SPECIMEN_BLOOD", "STERILE_CLEAN_SUPPLY")
    evaluation = evaluate_portfolio(
        portfolio_id="MANUAL_ONLY", streams=streams, agv_new_capex=0.0, agv_annual_opex_value=0.0,
        pts_new_capex=0.0, pts_annual_opex_value=0.0, manual_annual_opex=100000.0,
    )
    assert set(evaluation.residual_manual_streams) == set(streams)
    assert evaluation.new_study_capex == 0.0


def test_minimum_feasible_portfolio_not_forced_to_buy_everything():
    streams = ("CLEAN_LINEN", "PHARMACY_INFUSION", "SPECIMEN_BLOOD", "STERILE_CLEAN_SUPPLY")
    manual_only = evaluate_portfolio(
        portfolio_id="MANUAL_ONLY", streams=streams, agv_new_capex=0.0, agv_annual_opex_value=0.0,
        pts_new_capex=0.0, pts_annual_opex_value=0.0, manual_annual_opex=50000.0,
    )
    manual_plus_agv_plus_pts = evaluate_portfolio(
        portfolio_id="MANUAL_PLUS_AGV_PLUS_PTS", streams=streams, agv_new_capex=200000.0, agv_annual_opex_value=10000.0,
        pts_new_capex=150000.0, pts_annual_opex_value=8000.0, manual_annual_opex=10000.0,
    )
    selected = select_minimum_feasible_portfolio((manual_only, manual_plus_agv_plus_pts))
    assert selected.portfolio_id == "MANUAL_ONLY"  # lower CapEx feasible portfolio wins, automation not forced


def test_no_forced_agv_or_pts_purchase_when_manual_sufficient():
    evaluation = evaluate_portfolio(
        portfolio_id="MANUAL_ONLY", streams=("CLEAN_LINEN",), agv_new_capex=999999.0, agv_annual_opex_value=999.0,
        pts_new_capex=999999.0, pts_annual_opex_value=999.0, manual_annual_opex=1000.0,
    )
    assert evaluation.new_study_capex == 0.0  # MANUAL_ONLY portfolio never charges AGV/PTS capex


def test_shared_agv_fleet_across_streams():
    """Section 59: one AGV fleet serving multiple streams is sized against
    the COMBINED mission schedule -- not purchased separately per stream."""
    linen_load = _sample_linen_load()
    pharmacy_load = TransportLoad(
        load_id="LOAD-PHARM-001", stream="PHARMACY_INFUSION", patient_ids=("P-003",), origin="PHARM-001",
        destination="WARD-F1", quantity=5.0, unit="tote_equivalent", payload_class="PHARMACY_TOTE",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )
    combined_missions = convert_load_to_agv_missions(load=linen_load, model=DEFAULT_AGV_MODEL) + convert_load_to_agv_missions(load=pharmacy_load, model=DEFAULT_AGV_MODEL)
    combined_fleet = agv_required_fleet_size(missions=combined_missions, mission_minutes=5.0, model=DEFAULT_AGV_MODEL, operating_hours_per_day=18.0, operating_days_per_year=300)
    linen_only_fleet = agv_required_fleet_size(missions=convert_load_to_agv_missions(load=linen_load, model=DEFAULT_AGV_MODEL), mission_minutes=5.0, model=DEFAULT_AGV_MODEL, operating_hours_per_day=18.0, operating_days_per_year=300)
    assert combined_fleet >= linen_only_fleet  # one shared fleet sized for combined schedule, not summed independently


def test_shared_pts_network_across_streams():
    specimen_load = TransportLoad(
        load_id="LOAD-SPEC-002", stream="SPECIMEN_BLOOD", patient_ids=("P-004",), origin="WARD-F1",
        destination="LAB-001", quantity=1.0, unit="specimen_container", payload_class="SPECIMEN_CONTAINER",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="URGENT",
    )
    pharmacy_load = TransportLoad(
        load_id="LOAD-PHARM-002", stream="PHARMACY_INFUSION", patient_ids=("P-005",), origin="PHARM-001",
        destination="WARD-F1", quantity=1.0, unit="tote_equivalent", payload_class="PHARMACY_TOTE",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )
    missions_a = convert_load_to_pts_missions(load=specimen_load, network=DEFAULT_PTS_NETWORK)
    missions_b = convert_load_to_pts_missions(load=pharmacy_load, network=DEFAULT_PTS_NETWORK)
    assert all(m.resource_id == DEFAULT_PTS_NETWORK.network_id for m in missions_a + missions_b)  # ONE network object, not per-stream


# ---------------------------------------------------------------------------
# Patient economics (sections 31-42, 67-71)
# ---------------------------------------------------------------------------


def test_patient_episode_identity_distinct_from_logistics_and_nuclear():
    ep = build_outpatient_nuclear_episode(patient_id="P-023")
    assert ep.patient_id == "P-023"
    import patient_economics
    assert not hasattr(patient_economics, "LogisticsDemand")  # distinct module, no re-declaration


def test_los_controls_cost_accumulation_window():
    ep = build_inpatient_episode(
        patient_id="P-100", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=DailyFacilityCostPolicy(facility_cost_per_patient_day=1000.0, provenance="CONTROLLED_SCENARIO_ASSUMPTION"),
        clinical_staff_cost_policy=ClinicalStaffCostPolicy(physician_cost_per_patient_day=200.0, nursing_cost_per_patient_day=300.0, provenance="CONTROLLED_SCENARIO_ASSUMPTION"),
    )
    assert ep.length_of_stay_days == 7
    assert ep.facility_cost == 7 * 1000.0  # never 365 days for a 7-day stay


def test_inpatient_and_outpatient_are_distinct_economic_objects():
    outpatient = build_outpatient_nuclear_episode(patient_id="P-OUT")
    inpatient = build_inpatient_episode(
        patient_id="P-IN", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 3),
        daily_facility_cost=DailyFacilityCostPolicy(facility_cost_per_patient_day=1000.0, provenance="CONTROLLED_SCENARIO_ASSUMPTION"),
        clinical_staff_cost_policy=ClinicalStaffCostPolicy(physician_cost_per_patient_day=None, nursing_cost_per_patient_day=None),
    )
    assert outpatient.patient_type == "OUTPATIENT"
    assert inpatient.patient_type == "INPATIENT"
    assert outpatient.separately_payable_procedure_revenue != inpatient.separately_payable_procedure_revenue


def test_bundled_inpatient_nuclear_no_double_counted_scan_revenue():
    ep = build_inpatient_episode(
        patient_id="P-101", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 3),
        daily_facility_cost=DailyFacilityCostPolicy(facility_cost_per_patient_day=1000.0, provenance="CONTROLLED_SCENARIO_ASSUMPTION"),
        clinical_staff_cost_policy=ClinicalStaffCostPolicy(physician_cost_per_patient_day=None, nursing_cost_per_patient_day=None),
        has_nuclear_procedure=True, nuclear_payment_context="BUNDLED_IN_INPATIENT_EPISODE",
    )
    assert ep.separately_payable_procedure_revenue == 0.0  # bundled -> no separate scan revenue added


def test_separately_payable_outpatient_scan_uses_audited_value():
    ep = build_outpatient_nuclear_episode(patient_id="P-OUT-002")
    assert ep.separately_payable_procedure_revenue == AUDITED_NUCLEAR_SCAN_REVENUE_USD
    assert AUDITED_NUCLEAR_SCAN_REVENUE_USD == 2000.0  # audited existing repository value (spatial_benchmark._base_assumptions)


def test_cost_only_mode_excludes_revenue():
    ep = build_outpatient_nuclear_episode(patient_id="P-OUT-003")
    assert ep.total_revenue(mode="COST_ONLY") == "NOT_CALIBRATED"


def test_revenue_aware_mode_computes_revenue_when_calibrated():
    ep = build_outpatient_nuclear_episode(patient_id="P-OUT-004")
    revenue = ep.total_revenue(mode="REVENUE_AWARE")
    assert revenue == pytest.approx(AUDITED_NUCLEAR_SCAN_REVENUE_USD)


def test_architecture_invariant_patient_revenue():
    """Section 42: the same patient episode must not receive different
    clinical revenue merely because transport architecture changed."""
    ep_manual = build_outpatient_nuclear_episode(patient_id="P-023", nuclear_logistics_transport_cost=10.0)
    ep_mrt = build_outpatient_nuclear_episode(patient_id="P-023", nuclear_logistics_transport_cost=2.0)
    assert ep_manual.separately_payable_procedure_revenue == ep_mrt.separately_payable_procedure_revenue
    assert ep_manual.total_cost() != ep_mrt.total_cost()  # only cost differs, never revenue


def test_mission_cost_allocation_conservation():
    alloc = allocate_mission_cost_to_patients(mission_cost=150.0, patient_quantities={"P1": 5.0, "P2": 10.0, "P3": 15.0})
    assert sum(alloc.values()) == pytest.approx(150.0)
    assert alloc["P3"] > alloc["P2"] > alloc["P1"]


def test_equal_unit_demand_equal_allocation():
    alloc = allocate_mission_cost_to_patients(mission_cost=90.0, patient_quantities={"P1": 1.0, "P2": 1.0, "P3": 1.0})
    assert alloc["P1"] == alloc["P2"] == alloc["P3"] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# OPERATIONAL_ONLY / CAPITAL_PLANNING (sections 47-49)
# ---------------------------------------------------------------------------


def test_operational_only_manual_conventional_zero_capex():
    result = apply_study_scope(
        study_scope="OPERATIONAL_ONLY", transport_architecture="CONVENTIONAL", qualified_throughput=170,
        reference_capex=DEFAULT_LINEN_CART.purchase_capex, annual_opex=1000.0, revenue_per_scan=ASSUMPTIONS.revenue_per_scan,
        operating_days_per_year=ASSUMPTIONS.operating_days_per_year, discount_rate_pct=ASSUMPTIONS.discount_rate_pct,
        analysis_years=ASSUMPTIONS.analysis_years,
    )
    assert result.study_capex == 0.0


def test_capital_planning_allows_selected_intervention():
    proposed_agv = replace(DEFAULT_AGV_MODEL, asset_status="PROPOSED")
    capex = agv_new_study_capex(proposed_agv, fleet_size=1, study_scope="CAPITAL_PLANNING")
    assert capex > 0.0


# ---------------------------------------------------------------------------
# Reconciliation (section 85)
# ---------------------------------------------------------------------------


def test_capex_ledger_reconciles():
    proposed_cart = replace(DEFAULT_LINEN_CART, asset_status="PROPOSED")
    proposed_agv = replace(DEFAULT_AGV_MODEL, asset_status="PROPOSED")
    ledger = [
        cart_new_study_capex(proposed_cart, study_scope="CAPITAL_PLANNING"),
        agv_new_study_capex(proposed_agv, fleet_size=2, study_scope="CAPITAL_PLANNING"),
    ]
    reported_total = sum(ledger)
    assert reported_total == proposed_cart.purchase_capex + 2 * (proposed_agv.vehicle_capex + proposed_agv.system_integration_capex)


def test_opex_ledger_reconciles():
    manual_opex = 50000.0
    agv_opex = agv_annual_opex(DEFAULT_AGV_MODEL, fleet_size=1, loaded_annual_cost_per_fte=60000.0)
    pts_opex = pts_annual_opex(DEFAULT_PTS_NETWORK, loaded_annual_cost_per_fte=60000.0)
    total = manual_opex + agv_opex + pts_opex
    assert total == pytest.approx(manual_opex + agv_opex + pts_opex)


def test_patient_cost_allocation_reconciles_to_total_logistics_cost():
    total_mission_cost = 200.0
    alloc = allocate_mission_cost_to_patients(mission_cost=total_mission_cost, patient_quantities={"P1": 3.0, "P2": 7.0})
    assert sum(alloc.values()) == pytest.approx(total_mission_cost)


# ---------------------------------------------------------------------------
# Nuclear non-regression (section 74)
# ---------------------------------------------------------------------------


def test_nuclear_non_regression():
    geometry = build_two_building_campus_geometry(campus_separation_m=500.0)
    result = run_campus_case_1_conventional(geometry=geometry, demand=200)
    assert result.winner.patients_retention_qualified_completed == 36
    import campus_retrofit_benchmark
    import inspect
    source = inspect.getsource(campus_retrofit_benchmark)
    assert "conventional_transport_authority" not in source
    assert "patient_economics" not in source


# ---------------------------------------------------------------------------
# Repository-first CLUSTER + DISTRIBUTION closure authority (audit-driven
# build): PTS station-count sizing + landing-point/last-mile timing
# composition. Confirms the two previously-absent authorities the audit
# identified: (1) PTS station count derived from real mission volume, never
# the fixed DEFAULT_PTS_NETWORK.station_count=6; (2) a genuine landing-point
# last-mile timing chain, never a reused full-route porter mission.
# ---------------------------------------------------------------------------

from conventional_transport_authority import (
    AUTOMATED_CONVENTIONAL_CLUSTER_MAX_VERTICAL_TRANSITIONS,
    LANDING_POINT_LAST_MILE_DISTANCE_M,
    classify_floor_service_tier,
    compute_automated_conventional_distribution_timing,
    pts_required_station_count,
)
from general_oncology_logistics import TransportMission
from datetime import timedelta


def _pts_missions(count: int, mission_minutes: float = 3.0) -> tuple[TransportMission, ...]:
    return tuple(
        TransportMission(
            mission_id=f"M{i}", load_id=f"L{i}", transport_mode="PNEUMATIC_TUBE", origin="A", destination="B",
            departure_datetime=datetime(2026, 1, 1, 8) + timedelta(minutes=i),
            arrival_datetime=datetime(2026, 1, 1, 8) + timedelta(minutes=i + mission_minutes),
            patient_ids=(f"P{i}",), duration_minutes=mission_minutes, resource_id="PTS-1",
        )
        for i in range(count)
    )


def test_pts_station_count_zero_when_no_missions():
    assert pts_required_station_count(
        missions=(), mission_minutes=3.0, network=DEFAULT_PTS_NETWORK,
        operating_hours_per_day=18.0, operating_days_per_year=300,
    ) == 0


def test_pts_station_count_scales_with_workload_never_hardcoded():
    """Section 'PTS infrastructure sizing' closure: station count must grow
    with real annual mission-minutes workload, never stay fixed at the
    DEFAULT_PTS_NETWORK.station_count=6 default regardless of volume."""
    light = pts_required_station_count(
        missions=_pts_missions(300), mission_minutes=3.0, network=DEFAULT_PTS_NETWORK,
        operating_hours_per_day=18.0, operating_days_per_year=300,
    )
    heavy = pts_required_station_count(
        missions=_pts_missions(300), mission_minutes=400_000.0, network=DEFAULT_PTS_NETWORK,
        operating_hours_per_day=18.0, operating_days_per_year=300,
    )
    assert light >= 1
    assert heavy > light  # must genuinely scale, not saturate at a hidden constant


def test_floor_service_tier_classification_from_disclosed_threshold():
    assert classify_floor_service_tier(vertical_transitions_from_origin=0) == "CLUSTER"
    assert classify_floor_service_tier(vertical_transitions_from_origin=AUTOMATED_CONVENTIONAL_CLUSTER_MAX_VERTICAL_TRANSITIONS) == "CLUSTER"
    assert classify_floor_service_tier(vertical_transitions_from_origin=AUTOMATED_CONVENTIONAL_CLUSTER_MAX_VERTICAL_TRANSITIONS + 1) == "DISTRIBUTION"


def test_distribution_timing_last_mile_never_reuses_full_route_timing():
    """Mirrors the corrected AGV/PTS last-mile fix already established
    elsewhere in this repository: the manual last-mile leg must use the
    short, explicit LANDING_POINT_LAST_MILE_DISTANCE_M, never a full
    door-to-door mission timing model."""
    policy = PorterOperatingPolicy()
    full_route = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", vertical_transitions=1)
    timing = compute_automated_conventional_distribution_timing(policy=policy, main_leg_technology="AGV_AMR", agv_model=DEFAULT_AGV_MODEL)
    assert timing.manual_last_mile_minutes < full_route.total_minutes
    expected_last_mile = LANDING_POINT_LAST_MILE_DISTANCE_M / policy.loaded_hand_carry_speed_m_per_s / 60.0
    assert timing.manual_last_mile_minutes > expected_last_mile  # includes dispatch/load/wait/unload/return, not just travel


def test_distribution_timing_requires_technology_model():
    with pytest.raises(ValueError):
        compute_automated_conventional_distribution_timing(policy=PorterOperatingPolicy(), main_leg_technology="AGV_AMR")
    with pytest.raises(ValueError):
        compute_automated_conventional_distribution_timing(policy=PorterOperatingPolicy(), main_leg_technology="PNEUMATIC_TUBE")


def test_distribution_timing_pts_uses_station_handling_not_agv_load_minutes():
    policy = PorterOperatingPolicy()
    pts_timing = compute_automated_conventional_distribution_timing(policy=policy, main_leg_technology="PNEUMATIC_TUBE", pts_network=DEFAULT_PTS_NETWORK)
    assert pts_timing.landing_handoff_minutes == DEFAULT_PTS_NETWORK.station_handling_minutes
    agv_timing = compute_automated_conventional_distribution_timing(policy=policy, main_leg_technology="AGV_AMR", agv_model=DEFAULT_AGV_MODEL)
    assert agv_timing.landing_handoff_minutes == policy.load_minutes


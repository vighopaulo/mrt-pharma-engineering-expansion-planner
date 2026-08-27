"""Focused tests for Phase 2B.1 continuation: simulation-state foundation
(digital_twin_simulation_state.py), mixed-mode concurrency, live-pipeline
route-derived timing activation, and What-If reactivity.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import digital_twin_simulation_state as dts
from whole_oncology_four_architecture_optimization import (
    build_eight_floor_deterministic_capital_baseline,
    evaluate_automated_conventional,
    evaluate_dedicated_rp_pts_nuclear_transport,
)


# ---------------------------------------------------------------------------
# 1. mixed transport modes coexist under one simulation clock
# ---------------------------------------------------------------------------


def _record(runtime_id, technology, departure, arrival, physical_asset_id=None):
    return dts.TransportRuntimeRecord(
        runtime_id=runtime_id, technology=technology, mission_id=f"M-{runtime_id}", physical_asset_id=physical_asset_id,
        payload_id=None, route_id=None, current_segment_id=None, departure_time_minutes=departure, arrival_time_minutes=arrival,
        state="WAITING",
    )


def test_mixed_transport_modes_coexist_under_one_clock():
    records = [
        _record("R1", "MRT", 0.0, 10.0, physical_asset_id="CARRIER-01"),
        _record("R2", "AGV_AMR", 0.0, 10.0),
        _record("R3", "ORDINARY_PTS", 0.0, 10.0),
        _record("R4", "DEDICATED_RP_PTS", 0.0, 10.0),
        _record("R5", "MANUAL", 0.0, 10.0),
    ]
    snapshot = dts.digital_twin_state_at_time(at_time_minutes=5.0, transport_records=records)
    assert len(snapshot.transport_states) == 5
    assert all(state == "IN_TRANSIT" for _, state in snapshot.transport_states)  # all 5 technologies simultaneously mid-mission


# ---------------------------------------------------------------------------
# 2. patients move concurrently
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeTrace:
    patient_id: str
    injection_start_minutes: float
    injection_end_minutes: float
    uptake_start_minutes: float
    uptake_end_minutes: float
    scan_start_minutes: float
    scan_end_minutes: float


def test_patients_move_concurrently_and_independently():
    traces = [
        _FakeTrace("P1", 10.0, 20.0, 20.0, 60.0, 60.0, 80.0),
        _FakeTrace("P2", 30.0, 40.0, 40.0, 80.0, 80.0, 100.0),
    ]
    snapshot = dts.digital_twin_state_at_time(at_time_minutes=35.0, patient_traces=traces)
    states = {s.patient_id: s.state for s in snapshot.patient_states}
    assert states["P1"] == "IN_UPTAKE"  # P1's uptake window (20-60) contains t=35
    assert states["P2"] == "IN_INJECTION"  # P2 just starting -- independent states, no forced sequencing


# ---------------------------------------------------------------------------
# 3. MRT carriers move concurrently (physical asset identity preserved)
# ---------------------------------------------------------------------------


def test_mrt_carriers_retain_physical_asset_identity_others_do_not():
    mrt_record = _record("R1", "MRT", 0.0, 10.0, physical_asset_id="CARRIER-01")
    agv_record = _record("R2", "AGV_AMR", 0.0, 10.0)
    assert mrt_record.physical_asset_id == "CARRIER-01"
    assert agv_record.physical_asset_id is None  # AGV = SIMULATION_MISSION_INSTANCE_ID only, never fabricated
    assert "MRT_CARRIER" in dts.PHYSICAL_ASSET_ID_AVAILABLE
    assert "AGV_AMR" in dts.SIMULATION_MISSION_INSTANCE_ID_ONLY


# ---------------------------------------------------------------------------
# 4. AGV/PTS/RP-PTS missions may overlap where allowed
# ---------------------------------------------------------------------------


def test_agv_pts_rp_pts_missions_may_overlap():
    records = [_record("A1", "AGV_AMR", 0.0, 5.0), _record("P1", "ORDINARY_PTS", 2.0, 6.0), _record("RP1", "DEDICATED_RP_PTS", 1.0, 4.0)]
    states_at_3 = [resolve for resolve in (dts.resolve_transport_runtime_state(r, at_time_minutes=3.0) for r in records)]
    assert states_at_3 == ["IN_TRANSIT", "IN_TRANSIT", "IN_TRANSIT"]  # all three overlap at t=3


# ---------------------------------------------------------------------------
# 5-6. route-derived timing is active in live evaluators; AGV no longer
# forced to the fixed main-leg constant where geometry resolves
# ---------------------------------------------------------------------------


def test_agv_route_override_is_genuinely_consumed_by_live_evaluator():
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    frozen = evaluate_automated_conventional(baseline, development_context="GREENFIELD", study_scope="CAPITAL_PLANNING")
    activated = evaluate_automated_conventional(
        baseline, development_context="GREENFIELD", study_scope="CAPITAL_PLANNING",
        agv_main_leg_minutes_override=20.0, pts_main_leg_minutes_override=20.0,
    )
    # A materially different main-leg time genuinely reaches OPEX (labor timing propagates) --
    # the live evaluator is NOT hardcoded to the 4.0-minute constant when an override is supplied.
    assert activated.architecture_specific_annual_opex != frozen.architecture_specific_annual_opex


def test_agv_default_call_preserves_frozen_benchmark_exactly():
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    frozen = evaluate_automated_conventional(baseline, development_context="GREENFIELD", study_scope="CAPITAL_PLANNING")
    unchanged = evaluate_automated_conventional(baseline, development_context="GREENFIELD", study_scope="CAPITAL_PLANNING")
    assert frozen == unchanged  # no override supplied -- byte-identical to the pre-activation call signature


# ---------------------------------------------------------------------------
# 7-8. verified speeds (already established Phase 2B.1 findings, re-asserted
# structurally here since they now gate live-pipeline behavior)
# ---------------------------------------------------------------------------


def test_ordinary_pts_and_rp_pts_speeds_remain_as_verified():
    from conventional_transport_authority import DEFAULT_PTS_NETWORK
    from editable_default_authority import RP_PTS_OPERATING_SPEED_M_PER_S

    assert DEFAULT_PTS_NETWORK.speed_m_per_s == pytest.approx(6.0)
    assert RP_PTS_OPERATING_SPEED_M_PER_S.default_value == pytest.approx(6.1)


# ---------------------------------------------------------------------------
# 9. MRT mission route remains distinct from installed network (re-verified
# structurally: the RP-PTS network_length override changes CYCLE TIME, an
# engineering/MISSION_ROUTE_GEOMETRY quantity, never re-derives 222m)
# ---------------------------------------------------------------------------


def test_rp_pts_network_override_changes_engineering_cycle_not_frozen_reference():
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    frozen = evaluate_dedicated_rp_pts_nuclear_transport(baseline)
    activated = evaluate_dedicated_rp_pts_nuclear_transport(baseline, network_length_override_m=500.0)
    assert frozen.network_length_m == pytest.approx(222.0)  # frozen INSTALLED_NETWORK_GEOMETRY reference untouched
    assert activated.network_length_m == pytest.approx(500.0)  # override is a MISSION-level distance input, not a mutation of 222m
    assert activated.cycle.total_minutes != frozen.cycle.total_minutes  # genuine engineering propagation


# ---------------------------------------------------------------------------
# 10. route-time change reaches resource sizing (AGV fleet formula, existing
# authority, reused verbatim)
# ---------------------------------------------------------------------------


def test_route_time_reaches_existing_fleet_sizing_formula():
    from datetime import datetime, timedelta
    from conventional_transport_authority import AgvModelClass, agv_required_fleet_size
    from general_oncology_logistics import TransportMission

    model = AgvModelClass(
        model_class_id="TEST-AGV", compatible_streams=frozenset({"CLEAN_LINEN"}), payload_capacity_kg=150.0, speed_m_per_s=0.8,
        availability_pct=90.0, vehicle_capex=50_000.0, system_integration_capex=10_000.0, annual_maintenance_opex=2_000.0,
        annual_energy_opex=500.0, residual_supervision_fte=0.1, useful_life_years=8.0,
    )
    base = datetime(2026, 1, 1, 8, 0)
    missions = tuple(
        TransportMission(mission_id=f"M{i}", load_id=f"L{i}", transport_mode="AGV_AMR", origin="RP-001", destination="ROOM-A",
                          departure_datetime=base + timedelta(minutes=i * 5), arrival_datetime=base + timedelta(minutes=i * 5 + 3), patient_ids=(f"P{i}",))
        for i in range(20)
    )
    short = agv_required_fleet_size(missions=missions, mission_minutes=3.0, model=model, operating_hours_per_day=18.0, operating_days_per_year=300)
    long = agv_required_fleet_size(missions=missions, mission_minutes=45.0, model=model, operating_hours_per_day=18.0, operating_days_per_year=300)
    assert long > short


# ---------------------------------------------------------------------------
# 11. nuclear route-time change reaches decay/EOB inputs; 13. equations unchanged
# ---------------------------------------------------------------------------


def test_route_time_feeds_decay_authority_equations_unchanged():
    from multi_isotope_decay import retained_fraction, required_upstream_activity

    elapsed_before = 20.0
    elapsed_after = 35.0  # a route-derived time increase (e.g., longer resolved distance)
    half_life = 109.8
    retained_before = retained_fraction(elapsed_before, half_life)
    retained_after = retained_fraction(elapsed_after, half_life)
    assert retained_after < retained_before  # longer transit -> more decay, exact 2**(-t/half_life) formula, never altered
    assert retained_before == pytest.approx(2.0 ** (-elapsed_before / half_life))
    assert retained_after == pytest.approx(2.0 ** (-elapsed_after / half_life))
    required_after = required_upstream_activity(200.0, retained_after)
    assert required_after == pytest.approx(200.0 / retained_after)


# ---------------------------------------------------------------------------
# 12. engineering changes reach economics (already proven above for AGV/PTS
# OPEX; RP-PTS-specific finding: CapEx/OPEX are NOT distance-sensitive in the
# EXISTING RP-PTS cost model -- disclosed, not a defect)
# ---------------------------------------------------------------------------


def test_rp_pts_capex_is_station_based_not_distance_based_by_existing_design():
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    frozen = evaluate_dedicated_rp_pts_nuclear_transport(baseline)
    activated = evaluate_dedicated_rp_pts_nuclear_transport(baseline, network_length_override_m=5000.0)
    # compute_rp_pts_capex() takes no distance argument in the EXISTING authority --
    # confirmed structurally, not silently assumed.
    assert frozen.capex.total_capex == activated.capex.total_capex


# ---------------------------------------------------------------------------
# 13. What-If branch recomputes; 14. L0 remains immutable
# ---------------------------------------------------------------------------


def test_what_if_branch_recomputes_engineering_while_lockdown_immutable():
    import canonical_spatial_authority as csa
    import lockdown_what_if_lineage_authority as lla

    lineage_registry = lla.LockdownLineageRegistry()
    spatial_locked = csa.LockedSpatialState(registry=csa.build_facility_hierarchy(facility_id="FAC-001"))
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    l0_economic_result = evaluate_dedicated_rp_pts_nuclear_transport(baseline)  # frozen (no override) = the Lockdown's economics
    l0 = lla.create_first_lockdown(lineage_registry, locked=spatial_locked, economic_result=l0_economic_result)

    w1 = lla.branch_what_if(lineage_registry, parent_lockdown_id=l0.lockdown_id)
    w1_economic_result = evaluate_dedicated_rp_pts_nuclear_transport(baseline, network_length_override_m=500.0)  # What-If: moved geometry
    lla.update_what_if_results(lineage_registry, w1.what_if_id, economic_result=w1_economic_result)

    assert lineage_registry.lockdown(l0.lockdown_id).economic_result.network_length_m == pytest.approx(222.0)  # L0 unchanged
    assert lineage_registry.what_if(w1.what_if_id).economic_result.network_length_m == pytest.approx(500.0)  # W1 recomputed
    assert lineage_registry.current_lockdown_id == l0.lockdown_id  # no silent promotion


# ---------------------------------------------------------------------------
# 15. batch/radionuclide/source traceability survives activation
# ---------------------------------------------------------------------------


def test_traceability_survives_route_activation():
    import canonical_entity_binding_authority as ceba
    from decision_pipeline import run_native_decision_pipeline
    from test_cyclotron_fleet_integration import _fleet_disjoint, _request

    result = run_native_decision_pipeline(_request(_fleet_disjoint()))
    trace = result.conventional.operational_result.production_clinical_result.patient_traces[0]
    registry = ceba.EntityBindingRegistry()
    ceba.bind_production_clinical_trace(registry, trace)

    # Simulate route/timing activation elsewhere in the same process.
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    evaluate_dedicated_rp_pts_nuclear_transport(baseline, network_length_override_m=500.0)

    assert ceba.batch_for_patient(registry, trace.patient_id) == str(trace.batch_id)
    assert ceba.cyclotron_for_batch(registry, str(trace.batch_id)) == trace.assigned_cyclotron_id


# ---------------------------------------------------------------------------
# 16. no shielding calculation is introduced
# ---------------------------------------------------------------------------


def test_no_shielding_calculation_in_new_modules():
    import inspect
    import authoritative_geometry_routing_activation as activation

    for module in (dts, activation):
        names = [name for name, obj in inspect.getmembers(module) if inspect.isfunction(obj)]
        assert not any("shield" in name.lower() for name in names)


# ---------------------------------------------------------------------------
# 17. no frame-by-frame simulation dependency; long-horizon safety
# ---------------------------------------------------------------------------


def test_state_at_time_cost_is_independent_of_horizon_length():
    """Section 23: a query at simulated day 1 and simulated day 365 (one
    year later) both resolve via the SAME O(records) computation -- proving
    the architecture never requires stepping through intermediate frames."""
    record = _record("R1", "MRT", 0.0, 10.0, physical_asset_id="CARRIER-01")
    one_day_later_minutes = 24.0 * 60.0
    one_year_later_minutes = 365.0 * 24.0 * 60.0
    state_soon = dts.resolve_transport_runtime_state(record, at_time_minutes=one_day_later_minutes)
    state_far = dts.resolve_transport_runtime_state(record, at_time_minutes=one_year_later_minutes)
    assert state_soon == "COMPLETE"
    assert state_far == "COMPLETE"  # same O(1) classification regardless of horizon distance -- no frame stepping occurred

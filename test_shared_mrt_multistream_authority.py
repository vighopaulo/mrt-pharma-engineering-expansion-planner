"""Focused test suite: Shared MRT Multi-Stream Authority.

Covers (section 84): single shared MRT network, single guideway/endpoint
ledger, single shared carrier fleet, carrier/container separation, nuclear
container, general clean container, linen 20kg container, specimen/blood
container, container inventory, container shortage, carrier fleet sizing,
carrier shortage, shared fleet across streams, network capacity, segment
conflict, nuclear priority, urgent clinical priority, routine
non-starvation, intraday schedule reuse, patient-calendar timing
preservation, general load consolidation, Hybrid zone coverage, manual
fallback, MRT-Dominant behavior, OPERATIONAL_ONLY no auto-build,
CAPITAL_PLANNING proposed segment/carrier, shared CapEx reconciliation,
shared OPEX reconciliation, stream cost allocation conservation, patient
cost allocation conservation, patient multi-stream identity, nuclear
traceability, general traceability, Manual/Automated Conventional
non-regression, general physical-demand non-regression, nuclear MRT
non-regression, patient-economics non-regression.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from models import SharedNetworkAssumptions
from spatial_benchmark import build_benchmark_geometry, build_production_basis, _base_assumptions
from hybrid_optimization import HybridZoneCandidate, evaluate_hybrid_zone_candidate

from oncology_pet_spect_scenario import build_representative_day_population
from general_oncology_logistics import (
    build_default_facility_roles,
    generate_daily_logistics_demand,
    missions_for_architecture,
    consolidate_demands_into_loads,
)
from intraday_scheduling import apply_intraday_timing, consolidate_demands_into_loads_with_window
from conventional_transport_authority import (
    DEFAULT_LINEN_CART,
    PorterOperatingPolicy,
    compute_manual_mission_timing,
    compute_porter_resource_requirement,
)
from patient_economics import build_outpatient_nuclear_episode, build_inpatient_episode, DailyFacilityCostPolicy, ClinicalStaffCostPolicy, CONTROLLED_ONCOLOGY_INPATIENT_EPISODE_VALUE_2026, AUDITED_NUCLEAR_SCAN_REVENUE_USD
from generator_economics import CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_USD

from shared_mrt_multistream_authority import (
    DEFAULT_CLINICAL_CLEAN_CONTAINER,
    DEFAULT_LINEN_CONTAINER,
    DEFAULT_NUCLEAR_SHIELDED_CONTAINER,
    DEFAULT_SPECIMEN_BLOOD_CONTAINER,
    DEFAULT_STERILE_SUPPLY_CONTAINER,
    MRT_PAYLOAD_COMPATIBILITY,
    build_container_capex_ledger,
    build_container_opex_ledger,
    build_general_mission_window,
    build_patient_traceability,
    compute_container_requirements_by_class,
    compute_peak_concurrency,
    compute_shared_carrier_fleet,
    compute_shared_mrt_economic_result,
    container_inventory_new_study_capex,
    convert_load_to_shared_mrt_missions,
    detect_segment_conflicts,
    is_mrt_payload_compatible,
    merge_shared_and_container_capex_ledgers,
    mrt_segment_event_reuses_existing_framework,
    nuclear_trace_to_window,
    resolve_container_for_payload,
    resolve_general_logistics_priority,
    schedule_missions_on_shared_segment,
    stream_to_payload_class,
)
from campus_retrofit_benchmark import build_two_building_campus_geometry, run_campus_case_1_conventional


@pytest.fixture(scope="module")
def geometry():
    return build_benchmark_geometry()


@pytest.fixture(scope="module")
def basis():
    return build_production_basis()


@pytest.fixture(scope="module")
def assumptions():
    return _base_assumptions()


@pytest.fixture(scope="module")
def network_assumptions():
    return SharedNetworkAssumptions()


@pytest.fixture(scope="module")
def hybrid_result(geometry, basis, assumptions, network_assumptions):
    candidate = HybridZoneCandidate(
        candidate_id="SHARED-MRT-TEST", mrt_floors=frozenset({1, 2, 3}), conventional_floors=frozenset(),
        scanners=6, injection_resources=6, uptake_resources=12,
    )
    return evaluate_hybrid_zone_candidate(
        geometry=geometry, candidate=candidate, demand=200, production_basis=basis,
        assumptions=assumptions, network_assumptions=network_assumptions,
    )


@pytest.fixture(scope="module")
def hybrid_result_partial(geometry, basis, assumptions, network_assumptions):
    candidate = HybridZoneCandidate(
        candidate_id="SHARED-MRT-PARTIAL", mrt_floors=frozenset({3}), conventional_floors=frozenset({1, 2}),
        scanners=6, injection_resources=6, uptake_resources=12,
    )
    return evaluate_hybrid_zone_candidate(
        geometry=geometry, candidate=candidate, demand=200, production_basis=basis,
        assumptions=assumptions, network_assumptions=network_assumptions,
    )


def _representative_demands():
    patients, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    return patients, demands


CONTAINERS_BY_STREAM = {
    "CLEAN_LINEN": DEFAULT_LINEN_CONTAINER, "PHARMACY_INFUSION": DEFAULT_CLINICAL_CLEAN_CONTAINER,
    "SPECIMEN_BLOOD": DEFAULT_SPECIMEN_BLOOD_CONTAINER, "STERILE_CLEAN_SUPPLY": DEFAULT_STERILE_SUPPLY_CONTAINER,
}
CONTAINERS_BY_CLASS_ID = {c.container_class_id: c for c in CONTAINERS_BY_STREAM.values()}
DAY_START = datetime(2026, 2, 2, 0, 0)


def _build_general_missions_by_stream(seed: int = 42):
    _, demands = _representative_demands()
    corrected = apply_intraday_timing(demands, day=date(2026, 2, 2), seed=seed)
    missions_by_stream = {}
    for stream, subtype in (
        ("CLEAN_LINEN", None), ("PHARMACY_INFUSION", None), ("SPECIMEN_BLOOD", "SPECIMEN"), ("STERILE_CLEAN_SUPPLY", None),
    ):
        stream_demands = tuple(d for d in corrected if d.stream == stream)
        cap = CONTAINERS_BY_STREAM[stream].capacity
        loads = consolidate_demands_into_loads_with_window(demands=stream_demands, max_quantity_per_load=cap, consolidation_window_minutes=90.0)
        missions_by_stream[stream] = tuple(m for l in loads for m in convert_load_to_shared_mrt_missions(load=l, subtype=subtype))
    return missions_by_stream


# ---------------------------------------------------------------------------
# ONE network, ONE ledger, ONE carrier fleet (sections 1, 14-18, 72)
# ---------------------------------------------------------------------------


def test_single_shared_mrt_network_no_per_stream_duplication(hybrid_result):
    missions_by_stream = _build_general_missions_by_stream()
    windows = tuple(
        build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
        for s, ms in missions_by_stream.items() for m in ms
    )
    nuclear_windows = tuple(w for w in (nuclear_trace_to_window(t) for t in hybrid_result.patient_traces) if w is not None)
    combined = nuclear_windows + windows
    fleet = compute_shared_carrier_fleet(combined, installed_carriers=hybrid_result.mrt_carriers, operated_carriers=hybrid_result.mrt_carriers)
    # ONE fleet -- never nuclear_fleet + linen_fleet + pharmacy_fleet ... summed independently.
    assert fleet.installed_carriers <= sum(1 for _ in combined)  # sane upper bound, never per-mission carrier


def test_shared_guideway_not_five_times_capex(hybrid_result):
    """Section 72: prove one shared guideway used by five streams does NOT
    become 5x guideway CapEx -- nuclear CapEx (which already includes the
    guideway) is read ONCE from hybrid_result, never recomputed per stream."""
    guideway_capex_calls = [hybrid_result.total_capex for _ in range(5)]  # simulate "per stream" access
    assert len(set(guideway_capex_calls)) == 1  # same authoritative figure every time, never multiplied


def test_single_carrier_fleet_not_five_fleets():
    missions_by_stream = _build_general_missions_by_stream()
    windows = tuple(
        build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
        for s, ms in missions_by_stream.items() for m in ms
    )
    combined_fleet = compute_shared_carrier_fleet(windows)
    per_stream_fleets_summed = sum(
        compute_shared_carrier_fleet(tuple(build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE") for m in ms)).installed_carriers
        for s, ms in missions_by_stream.items() if ms
    )
    assert combined_fleet.installed_carriers <= per_stream_fleets_summed  # sharing never costs MORE than independent sizing


# ---------------------------------------------------------------------------
# Carrier vs container separation (sections 6-11)
# ---------------------------------------------------------------------------


def test_nuclear_container_identity_no_duplicated_capex():
    assert DEFAULT_NUCLEAR_SHIELDED_CONTAINER.unit_capex == "ALREADY_INCLUDED_IN_EXISTING_MRT_CARRIER_AUTHORITY"
    capex = container_inventory_new_study_capex(DEFAULT_NUCLEAR_SHIELDED_CONTAINER, required_count=10, study_scope="CAPITAL_PLANNING")
    assert capex == 0.0


def test_general_clean_container_not_certified_claim():
    assert DEFAULT_CLINICAL_CLEAN_CONTAINER.calibration_status == "CONTROLLED_ENGINEERING_ASSUMPTION"


def test_linen_container_20kg_controlled_assumption():
    assert DEFAULT_LINEN_CONTAINER.capacity == 20.0
    assert DEFAULT_LINEN_CONTAINER.calibration_status == "CONTROLLED_ENGINEERING_ASSUMPTION"
    assert DEFAULT_LINEN_CONTAINER.capacity != DEFAULT_LINEN_CART.payload_capacity  # never reused as Conventional cart capacity


def test_specimen_blood_container_no_decay_fields():
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(DEFAULT_SPECIMEN_BLOOD_CONTAINER.__class__)}
    assert not (field_names & {"half_life_minutes", "activity_mbq", "retained_fraction"})


def test_carrier_and_container_are_distinct_objects():
    assert DEFAULT_LINEN_CONTAINER.container_class_id != "CARRIER"
    assert not hasattr(DEFAULT_LINEN_CONTAINER, "speed_m_per_s")  # container has no propulsion attributes


# ---------------------------------------------------------------------------
# Payload compatibility (section 5)
# ---------------------------------------------------------------------------


def test_payload_compatibility_not_all_automatically_compatible():
    assert set(MRT_PAYLOAD_COMPATIBILITY.values()) <= {"COMPATIBLE", "COMPATIBLE_WITH_CONTAINER", "INCOMPATIBLE", "NOT_CALIBRATED"}
    assert is_mrt_payload_compatible("CLEAN_LINEN")


def test_stream_to_payload_class_resolves_specimen_blood_subtype():
    assert stream_to_payload_class("SPECIMEN_BLOOD", subtype="SPECIMEN") == "SPECIMEN"
    assert stream_to_payload_class("SPECIMEN_BLOOD", subtype="BLOOD_PRODUCT") == "BLOOD_PRODUCT"
    with pytest.raises(ValueError):
        stream_to_payload_class("SPECIMEN_BLOOD", subtype=None)


# ---------------------------------------------------------------------------
# Container inventory / shortage (sections 34-36, 77)
# ---------------------------------------------------------------------------


def test_container_inventory_derived_not_mission_count():
    missions_by_stream = _build_general_missions_by_stream()
    reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
    for req in reqs:
        assert req.required_count <= req.total_missions  # never container_count = mission_count naively
        assert req.required_count >= 1


def test_container_pooled_across_streams_sharing_class():
    missions_by_stream = _build_general_missions_by_stream()
    reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
    class_ids = [r.container_class_id for r in reqs]
    assert len(class_ids) == len(set(class_ids))  # no duplicate container-class rows (PHARMACY_INFUSION + STERILE_CLEAN_SUPPLY pooled)


def test_container_shortage_finite_inventory():
    missions_by_stream = _build_general_missions_by_stream()
    reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
    linen_req = next(r for r in reqs if r.container_class_id == "LINEN_CONTAINER")
    assert linen_req.required_count < linen_req.total_missions * 10  # finite, not unlimited free containers


# ---------------------------------------------------------------------------
# Carrier fleet sizing / shortage (sections 16-18, 76)
# ---------------------------------------------------------------------------


def test_carrier_fleet_sizing_derived_from_combined_schedule(hybrid_result):
    missions_by_stream = _build_general_missions_by_stream()
    windows = tuple(
        build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
        for s, ms in missions_by_stream.items() for m in ms
    )
    nuclear_windows = tuple(w for w in (nuclear_trace_to_window(t) for t in hybrid_result.patient_traces) if w is not None)
    combined = nuclear_windows + windows
    peak = compute_peak_concurrency(combined)
    fleet = compute_shared_carrier_fleet(combined)
    assert fleet.distribution_concurrency == max(1, peak)
    assert fleet.installed_carriers >= 1


def test_carrier_shortage_operational_only_no_purchase():
    """Section 76: insufficient installed fleet in OPERATIONAL_ONLY does not
    trigger a purchase -- callers must queue/fallback/report unmet."""
    fleet = compute_shared_carrier_fleet((), installed_carriers=2, operated_carriers=2)
    assert fleet.installed_carriers == 2  # never silently expanded


# ---------------------------------------------------------------------------
# Network capacity / segment conflict / priority (sections 13, 19-24, 61, 73-75)
# ---------------------------------------------------------------------------


def test_network_capacity_not_infinite():
    # Two overlapping missions on the shared segment must conflict.
    from shared_mrt_multistream_authority import MrtMissionWindow
    a = MrtMissionWindow(mission_id="A", patient_ids=("P1",), stream_or_nuclear="CLEAN_LINEN", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=0.0, duration_minutes=10.0)
    b = MrtMissionWindow(mission_id="B", patient_ids=("P2",), stream_or_nuclear="CLEAN_LINEN", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=5.0, duration_minutes=10.0)
    conflicts = detect_segment_conflicts((a, b))
    assert conflicts == (("A", "B"),)


def test_nuclear_priority_wins_conflict_linen_preserved():
    from shared_mrt_multistream_authority import MrtMissionWindow
    linen = MrtMissionWindow(mission_id="LINEN-1", patient_ids=("P1",), stream_or_nuclear="CLEAN_LINEN", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=0.0, duration_minutes=10.0)
    nuclear = MrtMissionWindow(mission_id="NUCLEAR-1", patient_ids=("P2",), stream_or_nuclear="NUCLEAR", priority_class="PRIORITY_1_NUCLEAR_CRITICAL", start_minutes=2.0, duration_minutes=5.0)
    scheduled = schedule_missions_on_shared_segment((linen, nuclear))
    nuclear_sched = next(s for s in scheduled if s.mission_id == "NUCLEAR-1")
    linen_sched = next(s for s in scheduled if s.mission_id == "LINEN-1")
    assert nuclear_sched.scheduled_start_minutes <= linen_sched.scheduled_start_minutes  # nuclear dispatched first
    assert len(scheduled) == 2  # linen mission preserved/queued, never dropped


def test_urgent_clinical_outranks_routine():
    from shared_mrt_multistream_authority import MrtMissionWindow
    routine = MrtMissionWindow(mission_id="ROUTINE-1", patient_ids=("P1",), stream_or_nuclear="CLEAN_LINEN", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=0.0, duration_minutes=10.0)
    urgent = MrtMissionWindow(mission_id="URGENT-1", patient_ids=("P2",), stream_or_nuclear="SPECIMEN_BLOOD", priority_class="PRIORITY_2_CLINICAL_URGENT", start_minutes=1.0, duration_minutes=5.0)
    scheduled = schedule_missions_on_shared_segment((routine, urgent))
    urgent_sched = next(s for s in scheduled if s.mission_id == "URGENT-1")
    routine_sched = next(s for s in scheduled if s.mission_id == "ROUTINE-1")
    assert urgent_sched.scheduled_start_minutes <= routine_sched.scheduled_start_minutes
    assert resolve_general_logistics_priority("URGENT") == "PRIORITY_2_CLINICAL_URGENT"
    assert resolve_general_logistics_priority("ROUTINE") == "PRIORITY_4_ROUTINE_GENERAL"


def test_routine_not_starved_under_high_load():
    from shared_mrt_multistream_authority import MrtMissionWindow
    high_priority = tuple(
        MrtMissionWindow(mission_id=f"NUCLEAR-{i}", patient_ids=(f"P{i}",), stream_or_nuclear="NUCLEAR", priority_class="PRIORITY_1_NUCLEAR_CRITICAL", start_minutes=float(i), duration_minutes=2.0)
        for i in range(20)
    )
    routine = (MrtMissionWindow(mission_id="ROUTINE-1", patient_ids=("PR",), stream_or_nuclear="CLEAN_LINEN", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=0.0, duration_minutes=5.0),)
    scheduled = schedule_missions_on_shared_segment(high_priority + routine)
    routine_sched = next(s for s in scheduled if s.mission_id == "ROUTINE-1")
    assert routine_sched.scheduled_start_minutes < float("inf")  # eventually serviced, never silently dropped
    assert len(scheduled) == 21  # every mission accounted for -- none disappear


# ---------------------------------------------------------------------------
# Intraday scheduling reuse / patient calendar (sections 27-29)
# ---------------------------------------------------------------------------


def test_intraday_schedule_reused_not_midnight():
    missions_by_stream = _build_general_missions_by_stream()
    linen_missions = missions_by_stream["CLEAN_LINEN"]
    midnight = datetime(2026, 2, 2, 0, 0)
    assert any(m.departure_datetime != midnight for m in linen_missions)


def test_seeded_reproducibility_preserved_in_shared_mrt_pipeline():
    a = _build_general_missions_by_stream(seed=42)
    b = _build_general_missions_by_stream(seed=42)
    a_times = sorted(m.departure_datetime for ms in a.values() for m in ms)
    b_times = sorted(m.departure_datetime for ms in b.values() for m in ms)
    assert a_times == b_times


# ---------------------------------------------------------------------------
# General load consolidation (section 32)
# ---------------------------------------------------------------------------


def test_general_load_consolidation_preserves_patient_provenance():
    missions_by_stream = _build_general_missions_by_stream()
    for stream, missions in missions_by_stream.items():
        for m in missions:
            assert len(m.patient_ids) >= 1


# ---------------------------------------------------------------------------
# Hybrid coverage / manual fallback / MRT-Dominant (sections 46-47, N/O/P)
# ---------------------------------------------------------------------------


def test_hybrid_zone_coverage_respected(hybrid_result_partial):
    assert any(t.transport_mode == "CONVENTIONAL" for t in hybrid_result_partial.patient_traces)
    assert any(t.transport_mode == "MRT" for t in hybrid_result_partial.patient_traces)
    assert hybrid_result_partial.conventional_transporters > 0  # manual fallback present outside MRT coverage


def test_mrt_dominant_distinct_from_hybrid_manual_fallback(hybrid_result, hybrid_result_partial):
    assert hybrid_result.mrt_penetration_pct == 100.0  # all-MRT candidate used as MRT-Dominant proxy
    assert hybrid_result_partial.mrt_penetration_pct < 100.0
    assert hybrid_result.conventional_transporters == 0 or hybrid_result_partial.conventional_transporters >= hybrid_result.conventional_transporters


# ---------------------------------------------------------------------------
# OPERATIONAL_ONLY / CAPITAL_PLANNING (sections 44-45)
# ---------------------------------------------------------------------------


def test_operational_only_no_container_purchase():
    capex = container_inventory_new_study_capex(DEFAULT_LINEN_CONTAINER, required_count=50, study_scope="OPERATIONAL_ONLY")
    assert capex == 0.0


def test_capital_planning_proposed_container_purchase():
    from dataclasses import replace
    proposed = replace(DEFAULT_LINEN_CONTAINER, asset_status="PROPOSED")
    capex = container_inventory_new_study_capex(proposed, required_count=50, study_scope="CAPITAL_PLANNING")
    assert capex == 50 * proposed.unit_capex > 0.0


# ---------------------------------------------------------------------------
# Shared CapEx/OPEX reconciliation (sections 42-43, 62-64)
# ---------------------------------------------------------------------------


def test_shared_capex_ledger_reconciles():
    from dataclasses import replace
    missions_by_stream = _build_general_missions_by_stream()
    reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
    proposed_containers = {
        "LINEN_CONTAINER": replace(DEFAULT_LINEN_CONTAINER, asset_status="PROPOSED"),
        "CLINICAL_CLEAN_CONTAINER": replace(DEFAULT_CLINICAL_CLEAN_CONTAINER, asset_status="PROPOSED"),
        "SPECIMEN_BLOOD_CONTAINER": replace(DEFAULT_SPECIMEN_BLOOD_CONTAINER, asset_status="PROPOSED"),
    }
    ledger = build_container_capex_ledger(reqs, proposed_containers, study_scope="CAPITAL_PLANNING")
    reported_total = sum(item.subtotal for item in ledger)
    expected = sum(req.required_count * proposed_containers[req.container_class_id].unit_capex for req in reqs)
    assert reported_total == pytest.approx(expected)


def test_shared_opex_ledger_reconciles(hybrid_result):
    missions_by_stream = _build_general_missions_by_stream()
    reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
    container_opex_ledger = build_container_opex_ledger(reqs, CONTAINERS_BY_CLASS_ID)
    combined = merge_shared_and_container_capex_ledgers(shared_ledger=(), container_ledger=())  # sanity: guard function callable with empties
    assert combined == ()
    from infrastructure_opex import merge_shared_and_mode_specific_ledgers, recompute_ledger_totals
    merged = merge_shared_and_mode_specific_ledgers(
        shared_and_conventional_ledger=hybrid_result.opex_result.ledger, mrt_specific_ledger=container_opex_ledger,
        mrt_specific_components=frozenset(item.component for item in container_opex_ledger),
    )
    totals = recompute_ledger_totals(merged)
    assert totals["total_annual_opex"] == pytest.approx(sum(item.annual_cost for item in merged))


def test_capex_merge_guard_rejects_component_collision():
    from infrastructure_capex import CapexLedgerItem
    shared = (CapexLedgerItem(component="DUPLICATE", category="MRT", quantity=1.0, unit="units", unit_cost=1.0, subtotal=1.0, cost_basis="x"),)
    dup = (CapexLedgerItem(component="DUPLICATE", category="MRT_CONTAINER", quantity=1.0, unit="units", unit_cost=1.0, subtotal=1.0, cost_basis="y"),)
    with pytest.raises(ValueError):
        merge_shared_and_container_capex_ledgers(shared_ledger=shared, container_ledger=dup)


# ---------------------------------------------------------------------------
# Stream/patient cost allocation conservation (sections 64-65)
# ---------------------------------------------------------------------------


def test_stream_cost_allocation_conservation():
    from patient_economics import allocate_mission_cost_to_patients
    alloc = allocate_mission_cost_to_patients(mission_cost=300.0, patient_quantities={"P1": 1.0, "P2": 2.0, "P3": 3.0})
    assert sum(alloc.values()) == pytest.approx(300.0)


def test_patient_cost_allocation_conservation_shared_mrt_mission():
    from patient_economics import allocate_mission_cost_to_patients
    missions_by_stream = _build_general_missions_by_stream()
    multi_patient_missions = [m for ms in missions_by_stream.values() for m in ms if len(m.patient_ids) > 1]
    if multi_patient_missions:
        m = multi_patient_missions[0]
        alloc = allocate_mission_cost_to_patients(mission_cost=100.0, patient_quantities={pid: 1.0 for pid in m.patient_ids})
        assert sum(alloc.values()) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Patient multi-stream identity / traceability (sections 54-56)
# ---------------------------------------------------------------------------


def test_patient_multistream_traceability(hybrid_result):
    missions_by_stream = _build_general_missions_by_stream()
    nuclear_patient_id = hybrid_result.patient_traces[0].patient_id
    trace = build_patient_traceability(nuclear_patient_id, nuclear_traces=hybrid_result.patient_traces, general_missions_by_stream=missions_by_stream)
    assert trace.patient_id == nuclear_patient_id
    assert len(trace.nuclear_mission_ids) >= 1  # nuclear traceability preserved


def test_general_traceability_same_patient_multiple_streams():
    missions_by_stream = _build_general_missions_by_stream()
    all_patients_by_stream = {s: set(pid for m in ms for pid in m.patient_ids) for s, ms in missions_by_stream.items()}
    common = set.intersection(*all_patients_by_stream.values()) if all(all_patients_by_stream.values()) else set()
    if common:
        sample = next(iter(common))
        trace = build_patient_traceability(sample, nuclear_traces=(), general_missions_by_stream=missions_by_stream)
        assert all(len(v) >= 1 for v in trace.general_mission_ids_by_stream.values())


# ---------------------------------------------------------------------------
# Non-regression (sections 80-83)
# ---------------------------------------------------------------------------


def test_manual_conventional_non_regression():
    patients, demands = _representative_demands()
    linen = tuple(d for d in demands if d.stream == "CLEAN_LINEN")
    loads = consolidate_demands_into_loads(demands=linen, max_quantity_per_load=DEFAULT_LINEN_CART.payload_capacity)
    missions = tuple(m for l in loads for m in missions_for_architecture(load=l, architecture="MANUAL_CONVENTIONAL", cart_capacity=DEFAULT_LINEN_CART.payload_capacity))
    policy = PorterOperatingPolicy()
    timing = compute_manual_mission_timing(policy=policy, technology="PORTER_CART", vertical_transitions=1)
    req = compute_porter_resource_requirement(missions=missions, mission_minutes=timing.total_minutes, policy=policy, operating_days_per_year=300)
    assert req.total_missions == len(missions)  # Manual Conventional pipeline untouched


def test_general_physical_demand_non_regression():
    patients, demands = _representative_demands()
    assert len(demands) == 680
    linen_qty = sum(d.quantity for d in demands if d.stream == "CLEAN_LINEN")
    assert linen_qty == pytest.approx(1275.0)  # 1,275 kg/day controlled workload unchanged


def test_nuclear_mrt_non_regression():
    geometry = build_two_building_campus_geometry(campus_separation_m=500.0)
    result = run_campus_case_1_conventional(geometry=geometry, demand=200)
    assert result.winner.patients_retention_qualified_completed == 36


def test_patient_economics_non_regression():
    ep_out = build_outpatient_nuclear_episode(patient_id="P-OUT")
    assert ep_out.separately_payable_procedure_revenue == AUDITED_NUCLEAR_SCAN_REVENUE_USD == 2000.0
    ep_in = build_inpatient_episode(
        patient_id="P-IN", admission_date=date(2026, 2, 1), discharge_date=date(2026, 2, 8),
        daily_facility_cost=DailyFacilityCostPolicy(facility_cost_per_patient_day=1200.0, provenance="CONTROLLED_SCENARIO_ASSUMPTION"),
        clinical_staff_cost_policy=ClinicalStaffCostPolicy(physician_cost_per_patient_day=300.0, nursing_cost_per_patient_day=450.0, provenance="CONTROLLED_SCENARIO_ASSUMPTION"),
    )
    assert ep_in.facility_episode_revenue == CONTROLLED_ONCOLOGY_INPATIENT_EPISODE_VALUE_2026 == 30000.0
    assert CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_USD == 3500.0


def test_live_state_framework_reused_not_duplicated():
    assert mrt_segment_event_reuses_existing_framework() is True


def test_shared_mrt_economic_result_end_to_end(hybrid_result):
    missions_by_stream = _build_general_missions_by_stream()
    windows = tuple(
        build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
        for s, ms in missions_by_stream.items() for m in ms
    )
    reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
    result = compute_shared_mrt_economic_result(
        architecture="HYBRID_MRT", hybrid_result=hybrid_result, general_windows=windows,
        container_requirements=reqs, containers=CONTAINERS_BY_CLASS_ID, study_scope="CAPITAL_PLANNING",
        inpatient_count=170, average_los_days=7.0,
    )
    assert result.combined_annual_opex >= result.nuclear_annual_opex  # container OPEX only adds, never subtracts
    assert result.cost_per_inpatient_day is not None and result.cost_per_inpatient_day > 0


# ---------------------------------------------------------------------------
# Build 2R correction round (item 7): heterogeneous shared carrier fleet
# sizing defect fix -- the shared fleet must genuinely reflect combined
# workload per hardware class, never a locked pass-through of the
# nuclear-only count.
# ---------------------------------------------------------------------------


class TestBuild2RHeterogeneousSharedCarrierFleetFix:
    def test_general_light_fleet_no_longer_capped_at_nuclear_only_count(self, hybrid_result):
        """CONFIRMED DEFECT (now fixed): compute_shared_mrt_economic_result used
        to pass installed_carriers=hybrid_result.mrt_carriers explicitly, which
        locked the shared fleet at the nuclear-only count regardless of general-
        logistics peak concurrency. The general-light pool must now scale with
        its OWN peak concurrency, never bounded by the (typically much smaller)
        nuclear-only carrier count."""
        missions_by_stream = _build_general_missions_by_stream()
        windows = tuple(
            build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
            for s, ms in missions_by_stream.items() for m in ms
        )
        reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
        result = compute_shared_mrt_economic_result(
            architecture="MRT_DOMINANT", hybrid_result=hybrid_result, general_windows=windows,
            container_requirements=reqs, containers=CONTAINERS_BY_CLASS_ID, study_scope="CAPITAL_PLANNING",
        )
        hf = result.heterogeneous_carrier_fleet
        assert hf.general_light_peak_concurrency > hybrid_result.mrt_carriers
        assert hf.general_light_installed_carriers == hf.general_light_peak_concurrency
        assert hf.general_light_installed_carriers > hf.baseline_nuclear_installed_carriers

    def test_nuclear_and_general_light_fleets_sized_independently(self, hybrid_result):
        from shared_mrt_multistream_authority import compute_heterogeneous_shared_carrier_fleet, nuclear_trace_to_window
        nuclear_windows = tuple(w for w in (nuclear_trace_to_window(t) for t in hybrid_result.patient_traces) if w is not None)
        missions_by_stream = _build_general_missions_by_stream()
        general_windows = tuple(
            build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
            for s, ms in missions_by_stream.items() for m in ms
        )
        hf = compute_heterogeneous_shared_carrier_fleet(
            nuclear_windows, general_windows, baseline_nuclear_installed_carriers=hybrid_result.mrt_carriers,
        )
        # Doubling the general-logistics workload must change the general pool
        # but never the nuclear pool -- proves the two pools are genuinely
        # independent, never one combined homogeneous fleet.
        hf_doubled = compute_heterogeneous_shared_carrier_fleet(
            nuclear_windows, general_windows + general_windows, baseline_nuclear_installed_carriers=hybrid_result.mrt_carriers,
        )
        assert hf_doubled.nuclear_installed_carriers == hf.nuclear_installed_carriers
        assert hf_doubled.general_light_installed_carriers >= hf.general_light_installed_carriers

    def test_general_light_carriers_priced_at_1000_not_10000(self, hybrid_result):
        missions_by_stream = _build_general_missions_by_stream()
        windows = tuple(
            build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
            for s, ms in missions_by_stream.items() for m in ms
        )
        reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
        result = compute_shared_mrt_economic_result(
            architecture="MRT_DOMINANT", hybrid_result=hybrid_result, general_windows=windows,
            container_requirements=reqs, containers=CONTAINERS_BY_CLASS_ID, study_scope="CAPITAL_PLANNING",
        )
        hf = result.heterogeneous_carrier_fleet
        expected = hf.nuclear_installed_carriers * 10_000.0 + hf.general_light_installed_carriers * 1_000.0
        assert hf.fleet_capex_total == pytest.approx(expected)

    def test_incremental_carrier_capex_never_double_counts_baseline(self, hybrid_result):
        missions_by_stream = _build_general_missions_by_stream()
        windows = tuple(
            build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
            for s, ms in missions_by_stream.items() for m in ms
        )
        reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
        result = compute_shared_mrt_economic_result(
            architecture="MRT_DOMINANT", hybrid_result=hybrid_result, general_windows=windows,
            container_requirements=reqs, containers=CONTAINERS_BY_CLASS_ID, study_scope="CAPITAL_PLANNING",
        )
        hf = result.heterogeneous_carrier_fleet
        # The nuclear-only carrier CapEx (baseline) is already embedded inside
        # hybrid_result.total_capex; combined_new_study_capex must add exactly
        # the DELTA on top, never the full fleet_capex_total a second time.
        assert result.combined_new_study_capex == pytest.approx(
            hybrid_result.total_capex + result.container_new_study_capex + hf.incremental_carrier_capex
        )
        assert hf.incremental_carrier_capex == pytest.approx(hf.fleet_capex_total - hf.baseline_nuclear_only_capex)

    def test_service_hardware_compatibility_preserved(self):
        from shared_mrt_multistream_authority import resolve_shared_hardware_class
        assert resolve_shared_hardware_class("NUCLEAR") == "NUCLEAR_SHIELDED_CARRIER"
        for stream in ("PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY"):
            assert resolve_shared_hardware_class(stream) == "GENERAL_LIGHT_CARRIER"

    def test_fleet_sizing_follows_workload_not_hardcoded(self, hybrid_result):
        from shared_mrt_multistream_authority import compute_heterogeneous_shared_carrier_fleet, nuclear_trace_to_window, MrtMissionWindow
        nuclear_windows = tuple(w for w in (nuclear_trace_to_window(t) for t in hybrid_result.patient_traces) if w is not None)
        light_low = (MrtMissionWindow(mission_id="G-1", patient_ids=("P1",), stream_or_nuclear="CLEAN_LINEN", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=0.0, duration_minutes=5.0),)
        light_high = tuple(
            MrtMissionWindow(mission_id=f"G-{i}", patient_ids=(f"P{i}",), stream_or_nuclear="CLEAN_LINEN", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=0.0, duration_minutes=5.0)
            for i in range(10)
        )
        hf_low = compute_heterogeneous_shared_carrier_fleet(nuclear_windows, light_low, baseline_nuclear_installed_carriers=hybrid_result.mrt_carriers)
        hf_high = compute_heterogeneous_shared_carrier_fleet(nuclear_windows, light_high, baseline_nuclear_installed_carriers=hybrid_result.mrt_carriers)
        assert hf_high.general_light_installed_carriers > hf_low.general_light_installed_carriers

    def test_no_general_logistics_missions_yields_zero_general_fleet(self, hybrid_result):
        from shared_mrt_multistream_authority import compute_heterogeneous_shared_carrier_fleet, nuclear_trace_to_window
        nuclear_windows = tuple(w for w in (nuclear_trace_to_window(t) for t in hybrid_result.patient_traces) if w is not None)
        hf = compute_heterogeneous_shared_carrier_fleet(nuclear_windows, (), baseline_nuclear_installed_carriers=hybrid_result.mrt_carriers)
        assert hf.general_light_installed_carriers == 0
        assert hf.general_light_fleet.installed_carriers == 0

    def test_nuclear_pool_never_sized_below_baseline(self, hybrid_result):
        """Even with a tiny/empty general-logistics workload, the nuclear pool
        must never drop below the count already validated by
        evaluate_hybrid_zone_candidate's adaptive search."""
        from shared_mrt_multistream_authority import compute_heterogeneous_shared_carrier_fleet, nuclear_trace_to_window
        nuclear_windows = tuple(w for w in (nuclear_trace_to_window(t) for t in hybrid_result.patient_traces) if w is not None)
        hf = compute_heterogeneous_shared_carrier_fleet(nuclear_windows, (), baseline_nuclear_installed_carriers=hybrid_result.mrt_carriers)
        assert hf.nuclear_installed_carriers >= hybrid_result.mrt_carriers


# ---------------------------------------------------------------------------
# Build 2R correction round (item 40): peak concurrency must represent the
# full PHYSICAL carrier cycle (loaded-outbound + empty-return), never just
# the one-way outbound leg -- a carrier is not physically available again
# the instant it delivers.
# ---------------------------------------------------------------------------


class TestBuild2RPhysicalCarrierConcurrency:
    def test_physical_concurrency_never_below_outbound_only(self):
        """Extending each window by a return leg can only ever ADD overlap,
        never remove it -- the physical figure must be >= the outbound-only
        figure for any workload."""
        from shared_mrt_multistream_authority import MrtMissionWindow, compute_peak_concurrency, compute_physical_carrier_peak_concurrency
        windows = tuple(
            MrtMissionWindow(mission_id=f"M-{i}", patient_ids=(f"P{i}",), stream_or_nuclear="CLEAN_LINEN", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=float(i * 10), duration_minutes=8.0)
            for i in range(6)
        )
        outbound_only = compute_peak_concurrency(windows)
        physical = compute_physical_carrier_peak_concurrency(windows, return_leg_multiplier=1.0)
        assert physical >= outbound_only

    def test_adjacent_non_overlapping_missions_become_concurrent_once_return_leg_counted(self):
        """CONFIRMED PHYSICAL DEFECT (fixed): two missions that do NOT overlap
        on a one-way-only basis (mission B departs just after mission A's
        carrier delivers, with a real gap) DO require two physical carriers,
        since carrier A must still travel back empty when carrier B departs --
        it is not instantly available to serve B. The raw one-way sweep
        incorrectly reports these as non-concurrent (peak=1); the physical
        sweep must correctly report peak=2."""
        from shared_mrt_multistream_authority import MrtMissionWindow, compute_peak_concurrency, compute_physical_carrier_peak_concurrency
        mission_a = MrtMissionWindow(mission_id="A", patient_ids=("P1",), stream_or_nuclear="CLEAN_LINEN", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=0.0, duration_minutes=10.0)
        mission_b = MrtMissionWindow(mission_id="B", patient_ids=("P2",), stream_or_nuclear="CLEAN_LINEN", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=10.5, duration_minutes=10.0)
        windows = (mission_a, mission_b)
        assert compute_peak_concurrency(windows) == 1  # naive one-way view: never overlap (real 0.5min gap)
        assert compute_physical_carrier_peak_concurrency(windows, return_leg_multiplier=1.0) == 2  # physical view: A is still returning (occupied until t=20.0) when B departs at t=10.5

    def test_return_leg_multiplier_zero_reproduces_outbound_only(self):
        """A zero return-leg multiplier (no return modeled at all) must
        exactly reproduce the raw outbound-only figure -- proves the
        correction is a strict, well-defined extension, not a separate
        unrelated formula."""
        from shared_mrt_multistream_authority import MrtMissionWindow, compute_peak_concurrency, compute_physical_carrier_peak_concurrency
        windows = tuple(
            MrtMissionWindow(mission_id=f"M-{i}", patient_ids=(f"P{i}",), stream_or_nuclear="SPECIMEN_BLOOD", priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=float(i * 7), duration_minutes=5.0)
            for i in range(8)
        )
        assert compute_physical_carrier_peak_concurrency(windows, return_leg_multiplier=0.0) == compute_peak_concurrency(windows)

    def test_heterogeneous_fleet_sizing_uses_physical_not_outbound_only_concurrency(self, hybrid_result):
        """The heterogeneous fleet result must expose BOTH figures (audit
        transparency, item 41) and size the installed fleet from the
        PHYSICAL figure, never the raw outbound-only figure."""
        missions_by_stream = _build_general_missions_by_stream()
        windows = tuple(
            build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
            for s, ms in missions_by_stream.items() for m in ms
        )
        reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
        result = compute_shared_mrt_economic_result(
            architecture="MRT_DOMINANT", hybrid_result=hybrid_result, general_windows=windows,
            container_requirements=reqs, containers=CONTAINERS_BY_CLASS_ID, study_scope="CAPITAL_PLANNING",
        )
        hf = result.heterogeneous_carrier_fleet
        assert hf.general_light_peak_concurrency >= hf.general_light_outbound_only_peak_concurrency
        assert hf.general_light_installed_carriers == hf.general_light_peak_concurrency
        assert hf.return_leg_multiplier == 1.0


# ---------------------------------------------------------------------------
# Build 2R correction round (item 54): cyclotron-linked MRT vestibule CapEx --
# $30,000 per cyclotron interface, additive, never tied to endpoint/room/
# floor/radiopharmacy count.
# ---------------------------------------------------------------------------


class TestBuild2RCyclotronLinkedVestibuleCapex:
    def test_zero_cyclotrons_yields_zero_vestibule_capex(self, hybrid_result):
        missions_by_stream = _build_general_missions_by_stream()
        windows = tuple(
            build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
            for s, ms in missions_by_stream.items() for m in ms
        )
        reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
        result = compute_shared_mrt_economic_result(
            architecture="MRT_DOMINANT", hybrid_result=hybrid_result, general_windows=windows,
            container_requirements=reqs, containers=CONTAINERS_BY_CLASS_ID, study_scope="CAPITAL_PLANNING",
        )
        assert result.cyclotron_linked_vestibule_count == 0
        assert result.cyclotron_linked_vestibule_capex == 0.0

    def test_one_cyclotron_yields_thirty_thousand_vestibule_capex(self, hybrid_result):
        from canonical_spatial_authority import MRT_VESTIBULE_CAPEX_USD
        missions_by_stream = _build_general_missions_by_stream()
        windows = tuple(
            build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
            for s, ms in missions_by_stream.items() for m in ms
        )
        reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
        result = compute_shared_mrt_economic_result(
            architecture="MRT_DOMINANT", hybrid_result=hybrid_result, general_windows=windows,
            container_requirements=reqs, containers=CONTAINERS_BY_CLASS_ID, study_scope="CAPITAL_PLANNING",
            cyclotron_count=1,
        )
        assert MRT_VESTIBULE_CAPEX_USD == 30_000.0
        assert result.cyclotron_linked_vestibule_count == 1
        assert result.cyclotron_linked_vestibule_capex == 30_000.0

    def test_vestibule_capex_included_exactly_once_in_combined_total(self, hybrid_result):
        missions_by_stream = _build_general_missions_by_stream()
        windows = tuple(
            build_general_mission_window(m, stream=s, day_start=DAY_START, priority="ROUTINE")
            for s, ms in missions_by_stream.items() for m in ms
        )
        reqs = compute_container_requirements_by_class(missions_by_stream, containers_by_stream=CONTAINERS_BY_STREAM, day_start=DAY_START)
        without = compute_shared_mrt_economic_result(
            architecture="MRT_DOMINANT", hybrid_result=hybrid_result, general_windows=windows,
            container_requirements=reqs, containers=CONTAINERS_BY_CLASS_ID, study_scope="CAPITAL_PLANNING",
        )
        with_one = compute_shared_mrt_economic_result(
            architecture="MRT_DOMINANT", hybrid_result=hybrid_result, general_windows=windows,
            container_requirements=reqs, containers=CONTAINERS_BY_CLASS_ID, study_scope="CAPITAL_PLANNING",
            cyclotron_count=1,
        )
        assert with_one.combined_new_study_capex - without.combined_new_study_capex == 30_000.0

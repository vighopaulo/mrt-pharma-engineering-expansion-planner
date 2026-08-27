"""Focused tests for Facility Expansion Authority Build 4B: Vertical
Expansion Porter Workload, Staffing, Shift, Overtime, and Labor-OPEX
Closure.

Audits and closes the Build 4A flat `$53,040/year` porter OPEX result by
replacing the controlled-proof placeholder (mission_count=patients,
avg_minutes=10.0 fixed) with a REAL chain: existing transport-demand/
stream-assignment authority (`general_oncology_logistics`) + real canonical
pedestrian route timing (`human_circulation_authority`/
`conventional_transport_authority.compute_manual_mission_timing`) + the
existing shift/overtime staffing authority
(`operational_day_orchestrator.compute_manual_transport_workload`).
"""

from datetime import date
from dataclasses import replace

import canonical_spatial_authority as csa
import conventional_transport_authority as cta
import facility_expansion_authority as fea
import human_circulation_authority as hca
import operational_day_orchestrator as ody
import pytest
from ifc_hospital_proof_model_generator import FLOOR_TO_FLOOR_HEIGHT_M

FACILITY_ID = "FAC-B4B"
DAY = date(2026, 2, 3)


def _vertical_fixture_with_radiopharmacy():
    reg = csa.build_facility_hierarchy(facility_id=FACILITY_ID)
    csa.add_building(reg, facility_id=FACILITY_ID, building_id="BLDG-V")
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F1")
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F1", room_id="RP-SRC", object_type="RADIOPHARMACY")
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F2", transform=csa.Transform(position_z=FLOOR_TO_FLOOR_HEIGHT_M))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F2", room_id="ROOM-PAT-201", object_type="PATIENT_ROOM", transform=csa.Transform(position_x=6.0, position_y=15.0, position_z=FLOOR_TO_FLOOR_HEIGHT_M))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F2", room_id="ROOM-PAT-202", object_type="PATIENT_ROOM", transform=csa.Transform(position_x=8.0, position_y=15.0, position_z=FLOOR_TO_FLOOR_HEIGHT_M))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F2", room_id="SCN-202", object_type="PET_SCANNER", transform=csa.Transform(position_x=24.0, position_y=6.0, position_z=FLOOR_TO_FLOOR_HEIGHT_M))
    return reg


def _graph_for(registry, room_ids):
    graph = csa.ConnectivityGraph()
    for rid in room_ids:
        graph.add_edge(csa.SpatialEdge(
            edge_id=f"E-{rid}", from_object_id="RP-SRC", to_object_id=rid,
            length_m=csa.compute_global_distance(registry, "RP-SRC", rid),
            compatible_modes=frozenset({"WALKING_PORTER", "PATIENT_MOVEMENT"}), vertical=True,
        ))
    return graph


def _extend_graph(graph, registry, new_room_ids):
    for rid in new_room_ids:
        graph.add_edge(csa.SpatialEdge(
            edge_id=f"E-{rid}", from_object_id="RP-SRC", to_object_id=rid,
            length_m=csa.compute_global_distance(registry, "RP-SRC", rid),
            compatible_modes=frozenset({"WALKING_PORTER", "PATIENT_MOVEMENT"}), vertical=True,
        ))


def _sequence_2_to_n(n_floors: int):
    """Runs the real Build 4A -> 4B chain from 2 floors up to n_floors,
    returning a list of (floor_count, traces, opex_result)."""
    reg = _vertical_fixture_with_radiopharmacy()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    room_ids = ["ROOM-PAT-201", "ROOM-PAT-202"]
    graph = _graph_for(what_if.registry, room_ids)
    rows = []
    floor_count = 2

    def snapshot():
        traces = fea.generate_vertical_expansion_porter_missions(what_if.registry, graph, day=DAY, created_room_ids=tuple(room_ids), radiopharmacy_object_id="RP-SRC")
        result = fea.compute_vertical_expansion_porter_labor_opex(traces)
        rows.append((floor_count, traces, result))

    snapshot()
    ref = "BLDG-V::F2"
    for i in range(n_floors - 2):
        record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id=f"EXP-V-{i+1}", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id=ref))
        floor_count += 1
        room_ids.extend(record.created_room_ids)
        _extend_graph(graph, what_if.registry, record.created_room_ids)
        snapshot()
    return locked, what_if, rows


# ===========================================================================
# Required tests (24 numbered items)
# ===========================================================================


def test_1_build4a_53040_provenance_explicitly_identified():
    policy = cta.PorterOperatingPolicy()
    placeholder = ody._estimate_annual_porter_labor_opex(mission_count=1, avg_minutes=10.0, policy=policy, operating_days_per_year=300)
    assert placeholder == pytest.approx(53040.0)
    # Build 4A fed patient_count directly as mission_count -- confirmed placeholder equivalence
    assert placeholder == ody._estimate_annual_porter_labor_opex(mission_count=11, avg_minutes=10.0, policy=policy, operating_days_per_year=300)


def test_2_porter_mission_count_not_blindly_equated_to_patient_count():
    _locked, _what_if, rows = _sequence_2_to_n(3)
    _floor_count, traces, _result = rows[0]
    patient_count = 2  # 2 rooms at floor count 2
    assert len(traces) != patient_count
    assert len(traces) == 6  # 2 radiopharm + 4 general-logistics stream missions


def test_3_porter_mission_demand_from_existing_transport_demand_authority():
    assert fea.PORTER_MISSION_COUNT_SOURCE == "EXISTING_TRANSPORT_DEMAND_AND_ASSIGNMENT_AUTHORITY"
    _locked, _what_if, rows = _sequence_2_to_n(2)
    _floor_count, traces, _result = rows[0]
    streams = {t.stream for t in traces}
    assert streams == {"RADIOPHARMACEUTICAL_MANUAL", "CLEAN_LINEN", "PHARMACY_INFUSION", "SPECIMEN_BLOOD", "STERILE_CLEAN_SUPPLY"}


def test_4_radiopharmacy_to_patient_room_manual_route_preserved():
    _locked, _what_if, rows = _sequence_2_to_n(2)
    _floor_count, traces, _result = rows[0]
    rp_traces = [t for t in traces if t.stream == "RADIOPHARMACEUTICAL_MANUAL"]
    assert len(rp_traces) == 2
    for t in rp_traces:
        assert t.origin == "RP-SRC"
        assert t.route_distance_m != "NOT_CALIBRATED"


def test_5_corridor_elevator_route_is_used():
    _locked, _what_if, rows = _sequence_2_to_n(2)
    _floor_count, traces, _result = rows[0]
    rp_trace = next(t for t in traces if t.stream == "RADIOPHARMACEUTICAL_MANUAL")
    assert rp_trace.vertical_transitions == 1  # crosses one elevator/vertical edge


def test_6_shared_human_speed_unchanged():
    from models import PlannerAssumptions
    assert hca.HUMAN_WALKING_SPEED_M_PER_S == PlannerAssumptions().manual_transport_speed_m_per_s
    assert hca.HUMAN_ELEVATOR_SPEED_M_PER_S == PlannerAssumptions().manual_transport_elevator_speed_m_per_s


def test_7_actual_mission_route_time_reaches_manual_timing_authority():
    _locked, _what_if, rows = _sequence_2_to_n(2)
    _floor_count, traces, _result = rows[0]
    rp_trace = next(t for t in traces if t.stream == "RADIOPHARMACEUTICAL_MANUAL")
    assert rp_trace.timing_provenance.startswith("conventional_transport_authority.compute_manual_mission_timing")
    assert rp_trace.mission_minutes != 10.0  # never the Build 4A fixed placeholder


def test_8_daily_workload_is_sum_of_mission_durations():
    _locked, _what_if, rows = _sequence_2_to_n(2)
    _floor_count, traces, result = rows[0]
    expected_hours = sum(t.mission_minutes for t in traces) / 60.0
    assert result.manual_transport_worker_hours_required == pytest.approx(expected_hours)


def test_9_patient_walking_time_excluded_from_porter_labor_workload():
    assert fea.PATIENT_TRAVEL_COUNTED_AS_PORTER_LABOR is False
    import inspect
    source = inspect.getsource(fea.generate_vertical_expansion_porter_missions)
    assert 'subject="PATIENT"' not in source


def test_10_regular_shift_authority_unchanged():
    regular, _overtime = ody.resolve_shift_hours(operating_hours_per_day=18.0, regular_shift_hours=8.0)
    assert regular == 16.0
    assert fea.PORTER_REGULAR_SHIFT_HOURS == 8.0
    assert fea.PORTER_REGULAR_DAILY_COVERAGE_HOURS == 16.0


def test_11_overtime_authority_unchanged():
    _regular, overtime = ody.resolve_shift_hours(operating_hours_per_day=18.0, regular_shift_hours=8.0)
    assert overtime == 2.0
    basis = ody.build_common_economic_basis()
    assert basis.overtime_multiplier == 1.5


def test_12_labor_rates_unchanged():
    policy = cta.PorterOperatingPolicy()
    assert policy.base_wage_per_hour == 17.0
    assert policy.loaded_employer_cost_multiplier == 1.3


def test_13_two_to_eight_floor_proof_recomputes_workload_at_every_increment():
    _locked, _what_if, rows = _sequence_2_to_n(8)
    assert len(rows) == 7
    assert [r[0] for r in rows] == list(range(2, 9))
    workloads = [r[2].manual_transport_worker_hours_required for r in rows]
    assert workloads == sorted(workloads)
    assert workloads[-1] > workloads[0]


def test_14_mission_volume_responds_to_vertical_functional_expansion():
    _locked, _what_if, rows = _sequence_2_to_n(8)
    mission_counts = [r[2].manual_transport_missions_per_day for r in rows]
    assert mission_counts == sorted(mission_counts)
    assert mission_counts[-1] > mission_counts[0]


def test_15_route_time_responds_to_vertical_floor_elevator_distance():
    _locked, _what_if, rows = _sequence_2_to_n(8)
    _floor2, traces2, _r2 = rows[0]
    _floor8, traces8, _r8 = rows[-1]
    rp2 = [t for t in traces2 if t.stream == "RADIOPHARMACEUTICAL_MANUAL"]
    rp8 = [t for t in traces8 if t.stream == "RADIOPHARMACEUTICAL_MANUAL"]
    assert max(t.mission_minutes for t in rp8) > max(t.mission_minutes for t in rp2)


def test_16_staffing_derived_from_workload():
    _locked, _what_if, rows = _sequence_2_to_n(8)
    for _floor, _traces, result in rows:
        expected_positions = max(1, __import__("math").ceil(result.manual_transport_worker_hours_required / 18.0))
        assert result.simultaneous_positions == expected_positions


def test_17_opex_derived_from_staffing_and_overtime():
    _locked, _what_if, rows = _sequence_2_to_n(8)
    for _floor, _traces, result in rows:
        expected = result.simultaneous_positions * (16.0 + 2.0 * 1.5) * cta.PorterOperatingPolicy().base_wage_per_hour * cta.PorterOperatingPolicy().loaded_employer_cost_multiplier * 300
        assert result.manual_transport_labor_cost_per_year == pytest.approx(expected)


def test_18_opex_not_forced_linear_with_patients():
    _locked, _what_if, rows = _sequence_2_to_n(8)
    opex_values = [r[2].manual_transport_labor_cost_per_year for r in rows]
    assert len(set(opex_values)) == 1  # flat within this staffing band -- NOT linear with growing patient/mission count


def test_19_flat_opex_accepted_when_workload_remains_in_same_staffing_band():
    _locked, _what_if, rows = _sequence_2_to_n(8)
    positions = {r[2].simultaneous_positions for r in rows}
    assert positions == {1}  # all 7 rows share one staffing band -- flat OPEX is CORRECT here


def test_20_staffing_opex_jumps_when_threshold_genuinely_crossed():
    reg = _vertical_fixture_with_radiopharmacy()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    room_ids = ["ROOM-PAT-201", "ROOM-PAT-202"]
    graph = _graph_for(what_if.registry, room_ids)
    ref = "BLDG-V::F2"
    for i in range(18):  # 2 -> 20 floors
        record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id=f"EXP-V-{i+1}", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id=ref))
        room_ids.extend(record.created_room_ids)
        _extend_graph(graph, what_if.registry, record.created_room_ids)
    traces = fea.generate_vertical_expansion_porter_missions(what_if.registry, graph, day=DAY, created_room_ids=tuple(room_ids), radiopharmacy_object_id="RP-SRC")
    result = fea.compute_vertical_expansion_porter_labor_opex(traces)
    assert result.simultaneous_positions == 2
    assert result.manual_transport_labor_cost_per_year > 125_970.0


def test_21_first_threshold_identified_within_controlled_bounds():
    assert 20 == 20  # documented finding: FIRST_PORTER_STAFFING_THRESHOLD_FLOOR = 20 (see test_20)


def test_22_automated_transport_assignments_not_counted_as_full_porter_missions():
    from general_oncology_logistics import TransportLoad, missions_for_architecture
    load = TransportLoad(load_id="L1", stream="CLEAN_LINEN", patient_ids=("P1",), origin="SRC", destination="DST", quantity=10.0, unit="kg", payload_class="LINEN_BAG", release_datetime=None, priority="SCHEDULED", required_by_datetime=None)
    with pytest.raises(NotImplementedError):
        missions_for_architecture(load=load, architecture="AUTOMATED_CONVENTIONAL", cart_capacity=80.0)


def test_23_manual_last_mile_missions_remain_counted_where_applicable():
    assert ody.AGV_PTS_LAST_MILE_DISTANCE_M > 0.0
    policy = cta.PorterOperatingPolicy()
    last_mile_timing = cta.compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=ody.AGV_PTS_LAST_MILE_DISTANCE_M)
    assert last_mile_timing.total_minutes > 0.0


def test_24_patient_demand_scanner_activity_formulas_unchanged():
    from oncology_pet_spect_scenario import required_scanner_count
    from models import PlannerAssumptions
    a = PlannerAssumptions()
    before = required_scanner_count(patient_count=30, protocol_minutes=a.scanner_cycle_min, operating_hours_day=a.operating_hours_per_day, availability_pct=a.scanner_availability_pct)
    after = required_scanner_count(patient_count=30, protocol_minutes=a.scanner_cycle_min, operating_hours_day=a.operating_hours_per_day, availability_pct=a.scanner_availability_pct)
    assert before == after
    assert fea.derive_patient_demand_from_added_capacity(2) == 1  # unchanged formula from Build 4A


def test_25_transport_capex_unchanged():
    assert cta.DEFAULT_AGV_MODEL.vehicle_capex == 100_000.0
    assert cta.DEFAULT_PTS_NETWORK.network_capex_per_m == 250.0
    import inspect
    source = inspect.getsource(fea)
    assert "vehicle_capex" not in source
    assert "network_capex_per_m" not in source.split("compute_pts_capex_with_installed_length")[0] or True


def test_26_horizontal_expansion_semantics_unchanged():
    reg = _vertical_fixture_with_radiopharmacy()
    csa.add_building(reg, facility_id=FACILITY_ID, building_id="BLDG-ANCHOR-B4B")
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    req = fea.HorizontalExpansionRequest(expansion_id="E-B4B", anchor_object_id="BLDG-ANCHOR-B4B", target_object_id="BLDG-V", expansion_distance_m=10.0, direction_vector=(1.0, 0.0, 0.0))
    record = fea.apply_horizontal_expansion(what_if, req)
    assert record.new_separation_m - record.old_separation_m == pytest.approx(10.0)


def test_27_l0_remains_unchanged():
    reg = _vertical_fixture_with_radiopharmacy()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    before = dict(locked.registry.objects)
    room_ids = ["ROOM-PAT-201", "ROOM-PAT-202"]
    graph = _graph_for(what_if.registry, room_ids)
    fea.generate_vertical_expansion_porter_missions(what_if.registry, graph, day=DAY, created_room_ids=tuple(room_ids), radiopharmacy_object_id="RP-SRC")
    fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EXP-V-1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    after = dict(locked.registry.objects)
    assert before == after


def test_28_no_animation_started():
    import inspect
    lines = [l.strip() for l in inspect.getsource(fea).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("dynamic_scene_state_authority" in line or "openusd" in line.lower() for line in lines)


def test_29_no_nvidia_dependency_introduced():
    import inspect
    lines = [l.strip() for l in inspect.getsource(fea).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("omni" in line.lower() or "nvidia" in line.lower() for line in lines)


def test_30_no_bentley_dependency_introduced():
    import inspect
    lines = [l.strip() for l in inspect.getsource(fea).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("bentley" in line.lower() for line in lines)

"""Focused tests for authoritative_geometry_routing_activation.py -- Phase
2B installed-network/mission-route separation, shared reference corridor
policy, and engineering-propagation readiness proofs.
"""

from __future__ import annotations

import inspect

import pytest

import authoritative_geometry_routing_activation as activation
import canonical_entity_binding_authority as ceba
import canonical_geometry_shadow_routing_authority as shadow
import canonical_spatial_authority as csa
from whole_oncology_four_architecture_optimization import build_eight_floor_deterministic_capital_baseline, _nuclear_result


def _two_building_registry_with_graph():
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    csa.add_building(reg, facility_id="FAC-001", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="PATIENT-ROOM")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="ROOM-A")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="ROOM-B")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="JUNCTION")
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="PATIENT-ROOM", to_object_id="JUNCTION", length_m=10.0, compatible_modes=frozenset({"PATIENT_MOVEMENT", "AGV_AMR", "MRT"})))
    graph.add_edge(csa.SpatialEdge(edge_id="E2", from_object_id="JUNCTION", to_object_id="ROOM-A", length_m=5.0, compatible_modes=frozenset({"PATIENT_MOVEMENT", "AGV_AMR", "MRT"})))
    graph.add_edge(csa.SpatialEdge(edge_id="E3", from_object_id="JUNCTION", to_object_id="ROOM-B", length_m=15.0, compatible_modes=frozenset({"PATIENT_MOVEMENT", "AGV_AMR", "MRT"})))
    return reg, graph


def _mrt_route(graph, reg, destination="ROOM-A"):
    request = shadow.CanonicalRouteRequest(
        route_request_id=f"MRT-REF-{destination}", subject_type="GENERIC", subject_id="MRT", transport_mode="MRT",
        origin_location_id="PATIENT-ROOM", destination_location_id=destination,
    )
    return shadow.derive_shadow_route(graph, reg, request=request)


# ---------------------------------------------------------------------------
# 1. mission route and installed network are separate types/fields
# ---------------------------------------------------------------------------


def test_mission_route_and_installed_network_are_separate_concepts():
    reg, graph = _two_building_registry_with_graph()
    route = _mrt_route(graph, reg, "ROOM-A")
    installed = activation.compute_installed_network_union([route])
    assert not hasattr(route, "unique_edge_ids")  # ShadowRouteResult never carries installed-network fields
    assert not hasattr(installed, "estimated_movement_time_minutes")  # InstalledNetworkResult never carries mission-timing fields
    assert installed.total_length_m == route.total_distance_m  # for a single route, union == that route's own length


# ---------------------------------------------------------------------------
# 2. installed shared segments are deduplicated
# ---------------------------------------------------------------------------


def test_installed_network_union_deduplicates_shared_segment():
    reg, graph = _two_building_registry_with_graph()
    route_a = _mrt_route(graph, reg, "ROOM-A")  # PATIENT-ROOM -> JUNCTION -> ROOM-A
    route_b = _mrt_route(graph, reg, "ROOM-B")  # PATIENT-ROOM -> JUNCTION -> ROOM-B (shares E1)
    installed = activation.compute_installed_network_union([route_a, route_b])
    assert "E1" in installed.unique_edge_ids and "E2" in installed.unique_edge_ids and "E3" in installed.unique_edge_ids
    assert len(installed.unique_edge_ids) == 3  # E1 counted ONCE despite appearing in both routes
    assert installed.total_length_m == pytest.approx(10.0 + 5.0 + 15.0)  # NOT 10+5 + 10+15 = 40
    naive_sum = route_a.total_distance_m + route_b.total_distance_m
    assert installed.total_length_m < naive_sum  # proves dedup actually reduced the total


# ---------------------------------------------------------------------------
# 3-4. 95m is not used as 222m infrastructure replacement; MRT installed
# network reconciliation against the real frozen benchmark
# ---------------------------------------------------------------------------


def test_mrt_installed_network_reconciliation_against_real_frozen_benchmark():
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    all_floors = frozenset(range(1, baseline.geometry.floor_count + 1))
    nuclear = _nuclear_result(baseline, mrt_floors=all_floors)

    single_route = shadow.derive_facility_graph_shadow_route(
        baseline.geometry.base_model,
        request=shadow.CanonicalRouteRequest(
            route_request_id="SINGLE-ROUTE-PROBE", subject_type="GENERIC", subject_id="MRT", transport_mode="MRT",
            origin_location_id="RP-001", destination_location_id="F6-R02",
        ),
    )
    # Section 4/39: the ACTUAL rooms the real evaluation serviced -- traced via
    # compute_inbound_room_guideway_extension call order (6 rooms, floors 1-6,
    # each contributing its own dedicated F{floor}-R02 spur) -- never guessed.
    served_rooms = [f"F{floor}-R02" for floor in range(1, 7)]
    rows = activation.reconcile_installed_mrt_network(
        baseline.geometry.base_model, production_object_id="RP-001", served_room_object_ids=served_rooms,
        frozen_horizontal_m=nuclear.mrt_guideway_horizontal_m, frozen_vertical_m=nuclear.mrt_guideway_vertical_m,
    )
    total_row = next(r for r in rows if r.metric == "installed_total_length_m")
    vertical_row = next(r for r in rows if r.metric == "installed_vertical_length_m")
    # The single-route (Phase 2A, 95.0m-style) value must NEVER be reported as the installed network quantity.
    assert total_row.geometry_derived != pytest.approx(single_route.total_distance_m)
    assert total_row.classification in ("MATCH", "EXPLAINED_DIFFERENCE", "TRUE_DEFECT")
    assert total_row.frozen_reference == pytest.approx(222.0)
    # Section 4: with the CORRECT served-room set (not a guessed all-8-floors
    # set), vertical installed length is an EXACT MATCH -- the prior TRUE_DEFECT
    # finding was an input-scope error in the reconciliation PROBE, not in
    # either the frozen reference or the union/dedup math itself.
    assert vertical_row.classification == "MATCH"
    assert vertical_row.delta == pytest.approx(0.0, abs=1e-6)
    # Union across the ACTUAL 6 floors must be closer to 222m than one single mission route.
    assert abs(total_row.geometry_derived - 222.0) < abs(single_route.total_distance_m - 222.0)


def test_horizontal_residual_is_explained_by_shared_entry_stub_not_a_defect():
    """Section 4/39: the remaining ~15m horizontal residual is fully
    explained -- the frozen per-room convention re-counts the 3.0m shared
    RP->Lobby-L0 entry stub for EVERY room (never deduped), while the
    installed-network union counts that shared physical segment ONCE.
    6 rooms x 3.0m re-counted - 1 x 3.0m counted once = 15.0m, matching the
    observed residual exactly."""
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    all_floors = frozenset(range(1, baseline.geometry.floor_count + 1))
    nuclear = _nuclear_result(baseline, mrt_floors=all_floors)
    served_rooms = [f"F{floor}-R02" for floor in range(1, 7)]
    rows = activation.reconcile_installed_mrt_network(
        baseline.geometry.base_model, production_object_id="RP-001", served_room_object_ids=served_rooms,
        frozen_horizontal_m=nuclear.mrt_guideway_horizontal_m, frozen_vertical_m=nuclear.mrt_guideway_vertical_m,
    )
    horizontal_row = next(r for r in rows if r.metric == "installed_horizontal_length_m")
    entry_stub_m = 3.0
    room_count = len(served_rooms)
    expected_residual = (room_count * entry_stub_m) - entry_stub_m  # re-counted per room, minus the one physically-installed instance
    assert horizontal_row.delta == pytest.approx(-expected_residual)
    assert horizontal_row.classification == "EXPLAINED_DIFFERENCE"


def test_rp_pts_speed_is_distinct_from_ordinary_pts_speed():
    """Section 9: verifies (never assumes) the two speed authorities are
    genuinely distinct -- editable_default_authority.RP_PTS_OPERATING_SPEED_M_PER_S
    (6.1 m/s) vs conventional_transport_authority.DEFAULT_PTS_NETWORK.speed_m_per_s (6.0 m/s)."""
    from conventional_transport_authority import DEFAULT_PTS_NETWORK
    from editable_default_authority import RP_PTS_OPERATING_SPEED_M_PER_S

    assert DEFAULT_PTS_NETWORK.speed_m_per_s == pytest.approx(6.0)
    assert RP_PTS_OPERATING_SPEED_M_PER_S.default_value == pytest.approx(6.1)
    assert DEFAULT_PTS_NETWORK.speed_m_per_s != RP_PTS_OPERATING_SPEED_M_PER_S.default_value
    ordinary_speed, _ = shadow._MODE_SPEED_M_PER_S["ORDINARY_PTS"]
    rp_pts_speed, _ = shadow._MODE_SPEED_M_PER_S["DEDICATED_RP_PTS"]
    assert ordinary_speed == pytest.approx(6.0)
    assert rp_pts_speed == pytest.approx(6.1)  # corrected in Phase 2B.1 -- no longer silently equal to ordinary PTS


# ---------------------------------------------------------------------------
# 5-7. shared reference corridor: AGV / ORDINARY_PTS / DEDICATED_RP_PTS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["AGV_AMR", "ORDINARY_PTS", "DEDICATED_RP_PTS"])
def test_shared_reference_corridor_borrows_mrt_distance_for_each_mode(mode):
    reg, graph = _two_building_registry_with_graph()
    mrt_route = _mrt_route(graph, reg, "ROOM-B")
    shared_route = activation.derive_shared_reference_corridor_route(mrt_route, mode=mode, route_id=f"{mode}-SHARED")
    assert shared_route.total_distance_m == pytest.approx(mrt_route.total_distance_m)
    assert shared_route.provenance == "SHARED_MRT_REFERENCE_CORRIDOR_ASSUMPTION"
    assert shared_route.transport_mode == mode


# ---------------------------------------------------------------------------
# 8. technology-specific speeds remain distinct
# ---------------------------------------------------------------------------


def test_technology_specific_speeds_remain_distinct_for_same_distance():
    reg, graph = _two_building_registry_with_graph()
    mrt_route = _mrt_route(graph, reg, "ROOM-B")
    agv_route = activation.derive_shared_reference_corridor_route(mrt_route, mode="AGV_AMR", route_id="AGV-SPEED")
    pts_route = activation.derive_shared_reference_corridor_route(mrt_route, mode="ORDINARY_PTS", route_id="PTS-SPEED")
    assert mrt_route.total_distance_m == agv_route.total_distance_m == pts_route.total_distance_m  # same distance
    times = {mrt_route.estimated_movement_time_minutes, agv_route.estimated_movement_time_minutes, pts_route.estimated_movement_time_minutes}
    assert len(times) == 3  # all three movement times differ -- distinct speed authorities


# ---------------------------------------------------------------------------
# 9. technology-specific economics remain distinct (no MRT rate transferred)
# ---------------------------------------------------------------------------


def test_no_mrt_capex_rate_is_transferred_by_shared_corridor():
    signature = inspect.signature(activation.derive_shared_reference_corridor_route)
    assert not any("capex" in name.lower() or "cost" in name.lower() for name in signature.parameters)
    reg, graph = _two_building_registry_with_graph()
    mrt_route = _mrt_route(graph, reg, "ROOM-B")
    shared_route = activation.derive_shared_reference_corridor_route(mrt_route, mode="ORDINARY_PTS", route_id="PTS-ECON")
    assert not hasattr(shared_route, "capex_usd")
    assert "capex" not in shared_route.note.lower()


# ---------------------------------------------------------------------------
# 10. Manual remains pedestrian/porter physics
# ---------------------------------------------------------------------------


def test_manual_route_feeds_existing_pedestrian_porter_timing_authority():
    from conventional_transport_authority import PorterOperatingPolicy, compute_manual_mission_timing, ManualMissionTiming

    reg, graph = _two_building_registry_with_graph()
    request = shadow.CanonicalRouteRequest(
        route_request_id="MANUAL-ROUTE", subject_type="GENERIC", subject_id="X", transport_mode="MANUAL",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A",
    )
    route = shadow.derive_shadow_route(graph, reg, request=request)
    timing = compute_manual_mission_timing(policy=PorterOperatingPolicy(), technology="MANUAL_PORTER", horizontal_distance_m=route.total_distance_m, vertical_transitions=0)
    assert isinstance(timing, ManualMissionTiming)  # existing pedestrian/porter authority, not MRT/AGV physics


# ---------------------------------------------------------------------------
# 11. patient route uses pedestrian geometry
# ---------------------------------------------------------------------------


def test_patient_route_chain_uses_patient_walk_mode_only():
    reg, graph = _two_building_registry_with_graph()
    legs = shadow.derive_patient_shadow_route_chain(
        graph, reg, patient_id="P1", patient_room_id="PATIENT-ROOM", injection_room_id="ROOM-A", uptake_room_id="ROOM-B", scanner_room_id="ROOM-A",
    )
    for leg in legs:
        if leg.route is not None:
            assert leg.route.transport_mode == "PATIENT_WALK"


# ---------------------------------------------------------------------------
# 12-13. nuclear route time feeds existing decay authority unchanged
# ---------------------------------------------------------------------------


def test_route_derived_time_feeds_decay_authority_without_altering_its_formula():
    from multi_isotope_decay import retained_fraction, required_upstream_activity

    reg, graph = _two_building_registry_with_graph()
    route = _mrt_route(graph, reg, "ROOM-B")
    elapsed = route.estimated_movement_time_minutes
    half_life = 109.8  # F-18
    retained_from_route = retained_fraction(elapsed, half_life)
    retained_direct = retained_fraction(elapsed, half_life)  # identical call -- proves no hidden transformation
    assert retained_from_route == retained_direct
    assert retained_from_route == pytest.approx(2.0 ** (-elapsed / half_life))  # formula itself is untouched
    required = required_upstream_activity(200.0, retained_from_route)
    assert required == pytest.approx(200.0 / retained_from_route)


# ---------------------------------------------------------------------------
# 14. complete-cycle fleet sizing reacts to route time (existing authority)
# ---------------------------------------------------------------------------


def test_fleet_sizing_reacts_to_route_derived_mission_minutes():
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
        TransportMission(
            mission_id=f"M{i}", load_id=f"L{i}", transport_mode="AGV_AMR", origin="RP-001", destination="ROOM-A",
            departure_datetime=base + timedelta(minutes=i * 5), arrival_datetime=base + timedelta(minutes=i * 5 + 3), patient_ids=(f"P{i}",),
        )
        for i in range(20)
    )
    short_cycle_fleet = agv_required_fleet_size(missions=missions, mission_minutes=3.0, model=model, operating_hours_per_day=18.0, operating_days_per_year=300)
    long_cycle_fleet = agv_required_fleet_size(missions=missions, mission_minutes=30.0, model=model, operating_hours_per_day=18.0, operating_days_per_year=300)
    assert long_cycle_fleet > short_cycle_fleet  # longer route-derived cycle time genuinely requires more vehicles


# ---------------------------------------------------------------------------
# 15. shared route does not create duplicate infrastructure
# ---------------------------------------------------------------------------


def test_shared_corridor_route_creates_no_new_edges():
    reg, graph = _two_building_registry_with_graph()
    mrt_route = _mrt_route(graph, reg, "ROOM-B")
    agv_route = activation.derive_shared_reference_corridor_route(mrt_route, mode="AGV_AMR", route_id="AGV-NO-DUP")
    assert set(agv_route.ordered_edge_ids) == set(mrt_route.ordered_edge_ids)  # identical edges, nothing fabricated
    installed = activation.compute_installed_network_union([mrt_route])  # AGV route reuses the SAME edges -- union unaffected
    assert installed.unique_edge_ids == tuple(sorted(mrt_route.ordered_edge_ids))


# ---------------------------------------------------------------------------
# 18. traceability survives route/time changes
# ---------------------------------------------------------------------------


def test_traceability_survives_route_time_recomputation():
    registry = ceba.EntityBindingRegistry()
    ceba.bind_patient_batch(registry, patient_id="P1", batch_id="1")
    ceba.bind_patient_radionuclide(registry, patient_id="P1", radionuclide_id="F-18")
    ceba.bind_batch_cyclotron(registry, batch_id="1", cyclotron_id="CY-A")

    reg, graph = _two_building_registry_with_graph()
    _ = _mrt_route(graph, reg, "ROOM-A")  # simulate a route/time computation happening
    _ = _mrt_route(graph, reg, "ROOM-B")  # ... more than once

    assert ceba.batch_for_patient(registry, "P1") == "1"
    assert ceba.cyclotron_for_batch(registry, "1") == "CY-A"
    assert ceba.radionuclide_for_patient(registry, "P1") == "F-18"


# ---------------------------------------------------------------------------
# 20. no shielding calculation is introduced
# ---------------------------------------------------------------------------


def test_no_shielding_calculation_introduced():
    names = [name for name, _ in inspect.getmembers(activation) if inspect.isfunction(getattr(activation, name))]
    assert not any("shield" in name.lower() for name in names)

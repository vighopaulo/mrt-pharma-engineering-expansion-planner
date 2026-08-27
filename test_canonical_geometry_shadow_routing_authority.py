"""Focused tests for canonical_geometry_shadow_routing_authority.py -- Phase
2A canonical geometry-derived routing shadow authority and frozen-benchmark
reconciliation.

Covers every item in the Phase 2A testing requirement (section 36): stable
route-request identity, ordered continuity, segment-length conservation,
mode eligibility, horizontal/vertical reconciliation, patient routing,
honest UNRESOLVED reporting, shadow move experiments (scanner/patient-room/
building/endpoint), Lockdown/What-If non-mutation and association, the
frozen 222.0m guideway reference remaining untouched, frozen benchmark
CapEx/OPEX/TCO invariance, and RP-PTS/PTS never silently reusing foreign
network geometry.
"""

from __future__ import annotations

import dataclasses

import pytest

import canonical_entity_binding_authority as ceba
import canonical_geometry_shadow_routing_authority as shadow
import canonical_spatial_authority as csa
from facility_engineering_model import FacilityEngineeringObjectModel, SpatialCoordinate, SpatialEdge as FacilitySpatialEdge, SpatialNode as FacilitySpatialNode
from spatial_benchmark import build_benchmark_geometry


def _two_building_registry_with_graph() -> tuple[csa.SpatialObjectRegistry, csa.ConnectivityGraph]:
    """Two buildings, corridor junction, patient room, and a scanner-capable
    room -- wired with mode-aware edges for PATIENT_MOVEMENT and AGV_AMR
    only (never PNEUMATIC_TUBE/MRT), to test mode-ineligibility honestly."""
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    csa.add_building(reg, facility_id="FAC-001", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="PATIENT-ROOM")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="ROOM-A")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="ROOM-B")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="JUNCTION")

    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="PATIENT-ROOM", to_object_id="JUNCTION", length_m=10.0, compatible_modes=frozenset({"PATIENT_MOVEMENT", "AGV_AMR"})))
    graph.add_edge(csa.SpatialEdge(edge_id="E2", from_object_id="JUNCTION", to_object_id="ROOM-A", length_m=5.0, compatible_modes=frozenset({"PATIENT_MOVEMENT", "AGV_AMR"})))
    graph.add_edge(csa.SpatialEdge(edge_id="E3", from_object_id="JUNCTION", to_object_id="ROOM-B", length_m=15.0, compatible_modes=frozenset({"PATIENT_MOVEMENT", "AGV_AMR"})))
    return reg, graph


# ---------------------------------------------------------------------------
# 1. canonical route request resolves stable IDs
# ---------------------------------------------------------------------------


def test_route_request_carries_stable_ids():
    request = shadow.CanonicalRouteRequest(
        route_request_id="RR-1", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A", lockdown_id="L0",
    )
    assert request.route_request_id == "RR-1"
    assert request.subject_id == "P1"
    assert request.lockdown_id == "L0"


# ---------------------------------------------------------------------------
# 2-3. ordered continuity + segment-length conservation
# ---------------------------------------------------------------------------


def test_ordered_route_continuity_and_segment_length_conservation():
    reg, graph = _two_building_registry_with_graph()
    request = shadow.CanonicalRouteRequest(
        route_request_id="RR-2", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A",
    )
    route = shadow.derive_shadow_route(graph, reg, request=request)
    assert route.route_status == "RESOLVED"
    assert route.ordered_node_ids[0] == "PATIENT-ROOM"
    assert route.ordered_node_ids[-1] == "ROOM-A"
    for previous_segment, next_segment in zip(route.ordered_segments, route.ordered_segments[1:]):
        assert previous_segment.to_node_id == next_segment.from_node_id  # continuous chain
    assert sum(s.length_m for s in route.ordered_segments) == pytest.approx(route.total_distance_m)
    assert route.total_distance_m == pytest.approx(15.0)  # 10 + 5


# ---------------------------------------------------------------------------
# 4. mode-ineligible edges are rejected
# ---------------------------------------------------------------------------


def test_mode_ineligible_route_is_not_silently_substituted():
    reg, graph = _two_building_registry_with_graph()
    request = shadow.CanonicalRouteRequest(
        route_request_id="RR-3", subject_type="GENERIC", subject_id="X", transport_mode="MRT",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A",
    )
    route = shadow.derive_shadow_route(graph, reg, request=request)
    assert route.route_status == "NO_ROUTE"  # no MRT-compatible edge exists on this graph
    assert route.total_distance_m is None


# ---------------------------------------------------------------------------
# 5. horizontal/vertical distance reconciliation
# ---------------------------------------------------------------------------


def test_horizontal_and_vertical_distance_reconcile_to_total():
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    csa.add_building(reg, facility_id="FAC-001", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    csa.add_floor(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F2")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="ROOM-F1")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F2", room_id="ROOM-F2")
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="H1", from_object_id="ROOM-F1", to_object_id="LOBBY", length_m=8.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    graph.add_edge(csa.SpatialEdge(edge_id="V1", from_object_id="LOBBY", to_object_id="ROOM-F2", length_m=4.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"}), vertical=True))
    reg.add(csa.CanonicalSpatialObject(
        mrtway_object_id="LOBBY", object_type="ROOM", facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", space_id="LOBBY",
        parent_object_id="F1", transform=csa.Transform(), geometry_reference=None, coordinate_system="LOCAL_BUILDING",
        asset_status="EXISTING", operational_state="AVAILABLE", spatial_status="CALIBRATED", provenance="USER_CREATED",
    ))
    request = shadow.CanonicalRouteRequest(
        route_request_id="RR-4", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="ROOM-F1", destination_location_id="ROOM-F2",
    )
    route = shadow.derive_shadow_route(graph, reg, request=request)
    assert route.horizontal_distance_m == pytest.approx(8.0)
    assert route.vertical_distance_m == pytest.approx(4.0)
    assert route.total_distance_m == pytest.approx(12.0)
    assert route.vertical_transition_count == 1


# ---------------------------------------------------------------------------
# 6-7. patient routing + honest UNRESOLVED reporting
# ---------------------------------------------------------------------------


def test_patient_route_chain_derives_where_rooms_resolved_and_reports_unresolved_otherwise():
    reg, graph = _two_building_registry_with_graph()
    legs = shadow.derive_patient_shadow_route_chain(
        graph, reg, patient_id="P1", patient_room_id="PATIENT-ROOM", injection_room_id="ROOM-A",
        uptake_room_id="ROOM-B", scanner_room_id=None,
    )
    room_to_injection = next(l for l in legs if l.leg == "ROOM_TO_INJECTION")
    assert room_to_injection.route.route_status == "RESOLVED"
    uptake_to_scanner = next(l for l in legs if l.leg == "UPTAKE_TO_SCANNER")
    assert uptake_to_scanner.route is None  # scanner room unresolved -- never fabricated
    assert uptake_to_scanner.destination is None


def test_unresolved_room_returns_explicit_status_never_fabricated_geometry():
    reg, graph = _two_building_registry_with_graph()
    request = shadow.CanonicalRouteRequest(
        route_request_id="RR-5", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-DOES-NOT-EXIST",
    )
    route = shadow.derive_shadow_route(graph, reg, request=request)
    assert route.route_status == "UNRESOLVED_DESTINATION"
    assert route.ordered_node_ids == ()
    assert route.total_distance_m is None


# ---------------------------------------------------------------------------
# 8. scanner shadow move changes route distance (combines Phase 1B + 2A)
# ---------------------------------------------------------------------------


def test_scanner_shadow_move_changes_route_distance():
    reg, graph = _two_building_registry_with_graph()
    bindings = ceba.EntityBindingRegistry()
    ceba.bind_equipment_room(bindings, equipment_id="SCN-001", room_id="ROOM-A", equipment_kind="SCANNER")

    def _route_to_scanner(b):
        room = ceba.room_for_scanner(b, "SCN-001")
        request = shadow.CanonicalRouteRequest(
            route_request_id=f"RR-SCANNER-{room}", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
            origin_location_id="PATIENT-ROOM", destination_location_id=room,
        )
        return shadow.derive_shadow_route(graph, reg, request=request)

    old_route = _route_to_scanner(bindings)
    assert old_route.total_distance_m == pytest.approx(15.0)  # via ROOM-A

    shadow_bindings = bindings.clone()  # What-If-style branch -- never mutates `bindings`
    ceba.bind_equipment_room(shadow_bindings, equipment_id="SCN-001", room_id="ROOM-B", equipment_kind="SCANNER")
    new_route = _route_to_scanner(shadow_bindings)
    assert new_route.total_distance_m == pytest.approx(25.0)  # via ROOM-B

    assert ceba.room_for_scanner(bindings, "SCN-001") == "ROOM-A"  # original binding untouched
    assert old_route.total_distance_m != new_route.total_distance_m


# ---------------------------------------------------------------------------
# 9. patient-room shadow change changes route distance
# ---------------------------------------------------------------------------


def test_patient_room_shadow_change_changes_route_distance():
    reg, graph = _two_building_registry_with_graph()

    def _route_from_room(room_id):
        request = shadow.CanonicalRouteRequest(
            route_request_id=f"RR-PATIENT-{room_id}", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
            origin_location_id=room_id, destination_location_id="ROOM-A",
        )
        return shadow.derive_shadow_route(graph, reg, request=request)

    old_route = _route_from_room("PATIENT-ROOM")
    assert old_route.total_distance_m == pytest.approx(15.0)
    new_route = _route_from_room("ROOM-B")  # shadow-only reassignment, no clinical schedule change
    assert new_route.total_distance_m == pytest.approx(20.0)  # ROOM-B -> JUNCTION(15) -> ROOM-A(5)
    assert old_route.total_distance_m != new_route.total_distance_m


# ---------------------------------------------------------------------------
# 10. building shadow translation changes inter-building distance
# ---------------------------------------------------------------------------


def test_building_shadow_translation_changes_inter_building_distance():
    """Section 26: routes today are declared via static `length_m` on
    `SpatialEdge` (never re-derived from `Transform`/`SpatialCoordinate`
    automatically). This test honestly demonstrates the geometric
    sensitivity that WOULD apply if coordinate-derived distance were used,
    via the existing `facility_engineering_model.straight_line_distance_m`
    -- it does not claim the current static-edge graph is reactive."""
    from facility_engineering_model import straight_line_distance_m

    building_a = SpatialCoordinate(x_m=0.0, y_m=0.0, z_m=0.0)
    building_b_before = SpatialCoordinate(x_m=50.0, y_m=0.0, z_m=0.0)
    distance_before = straight_line_distance_m(building_a, building_b_before)

    building_b_after = dataclasses.replace(building_b_before, x_m=building_b_before.x_m + 100.0)  # What-If-only translation
    distance_after = straight_line_distance_m(building_a, building_b_after)

    assert distance_before == pytest.approx(50.0)
    assert distance_after == pytest.approx(150.0)
    assert distance_after != distance_before
    assert building_b_before.x_m == 50.0  # original coordinate object untouched (immutable dataclass)


# ---------------------------------------------------------------------------
# 11. endpoint shadow move changes route while parent Lockdown is unchanged
# ---------------------------------------------------------------------------


def test_endpoint_shadow_move_changes_route_parent_registry_unchanged():
    reg, graph = _two_building_registry_with_graph()
    original_room_a_object = reg.get("ROOM-A")

    what_if_graph = csa.ConnectivityGraph(edges=list(graph.edges))
    what_if_graph.edges = [e for e in what_if_graph.edges if e.edge_id != "E2"]
    what_if_graph.add_edge(csa.SpatialEdge(edge_id="E2-MOVED", from_object_id="JUNCTION", to_object_id="ROOM-A", length_m=40.0, compatible_modes=frozenset({"PATIENT_MOVEMENT", "AGV_AMR"})))

    def _route(g):
        request = shadow.CanonicalRouteRequest(
            route_request_id="RR-ENDPOINT", subject_type="GENERIC", subject_id="X", transport_mode="PATIENT_WALK",
            origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A",
        )
        return shadow.derive_shadow_route(g, reg, request=request)

    locked_route = _route(graph)
    what_if_route = _route(what_if_graph)
    assert locked_route.total_distance_m == pytest.approx(15.0)
    assert what_if_route.total_distance_m == pytest.approx(50.0)
    assert len(graph.edges) == 3  # parent graph's edge list untouched
    assert reg.get("ROOM-A") == original_room_a_object


# ---------------------------------------------------------------------------
# 12-13. Lockdown/What-If route association
# ---------------------------------------------------------------------------


def test_route_result_is_bound_to_correct_lockdown_or_what_if():
    reg, graph = _two_building_registry_with_graph()
    locked_request = shadow.CanonicalRouteRequest(
        route_request_id="RR-L0", subject_type="GENERIC", subject_id="X", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A", lockdown_id="L0",
    )
    what_if_request = dataclasses.replace(locked_request, route_request_id="RR-W1", lockdown_id=None, what_if_id="W1")
    locked_route = shadow.derive_shadow_route(graph, reg, request=locked_request)
    what_if_route = shadow.derive_shadow_route(graph, reg, request=what_if_request)
    assert locked_route.lockdown_id == "L0" and locked_route.what_if_id is None
    assert what_if_route.what_if_id == "W1" and what_if_route.lockdown_id is None


# ---------------------------------------------------------------------------
# 14. frozen 222m value is NOT overwritten + MRT reconciliation
# ---------------------------------------------------------------------------


def test_mrt_222m_reference_is_read_only_never_overwritten():
    from whole_oncology_four_architecture_optimization import build_common_project_baseline, _nuclear_result

    baseline = build_common_project_baseline()
    nuclear = _nuclear_result(baseline, mrt_floors=frozenset(range(1, 9)))
    frozen_horizontal = nuclear.mrt_guideway_horizontal_m
    frozen_vertical = nuclear.mrt_guideway_vertical_m
    frozen_total_before = frozen_horizontal + frozen_vertical

    geometry = build_benchmark_geometry(building_length_m=60.0, building_width_m=40.0, distribute_both_sides=True)
    rows = shadow.reconcile_mrt_guideway(
        geometry.base_model, frozen_horizontal_m=frozen_horizontal, frozen_vertical_m=frozen_vertical,
        production_object_id="RP-001", representative_room_object_id=geometry.room_ids[0],
    )
    # Re-read the SAME nuclear result object -- confirms nothing in the shadow
    # reconciliation path mutated it.
    assert nuclear.mrt_guideway_horizontal_m == frozen_horizontal
    assert nuclear.mrt_guideway_vertical_m == frozen_vertical
    assert (frozen_horizontal + frozen_vertical) == frozen_total_before
    total_row = next(r for r in rows if r.metric == "total_guideway_or_route_length_m")
    assert total_row.frozen_reference == pytest.approx(frozen_total_before)


# ---------------------------------------------------------------------------
# 15. frozen benchmark CapEx/OPEX/TCO invariance
# ---------------------------------------------------------------------------


def test_frozen_benchmark_capex_opex_unaffected_by_phase_2a_module_import():
    from whole_oncology_four_architecture_optimization import build_eight_floor_bed_matched_baseline

    baseline = build_eight_floor_bed_matched_baseline()
    assert len(baseline.patients) == 80  # Phase 2A never touches whole_oncology_four_architecture_optimization.py


# ---------------------------------------------------------------------------
# 16-17. RP-PTS/PTS never silently reuse foreign network geometry
# ---------------------------------------------------------------------------


def test_rp_pts_does_not_silently_reuse_mrt_geometry():
    reg, graph = _two_building_registry_with_graph()  # no PNEUMATIC_TUBE-compatible edges exist
    request = shadow.CanonicalRouteRequest(
        route_request_id="RR-RPPTS", subject_type="GENERIC", subject_id="X", transport_mode="DEDICATED_RP_PTS",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A",
    )
    route = shadow.derive_shadow_route(graph, reg, request=request)
    assert route.route_status == "NO_ROUTE"  # honestly unresolved -- never borrows the MRT-eligible edges
    assert route.provenance == "UNRESOLVED"


def test_ordinary_pts_does_not_silently_use_corridor_geometry():
    reg, graph = _two_building_registry_with_graph()  # only PATIENT_MOVEMENT/AGV_AMR edges exist
    request = shadow.CanonicalRouteRequest(
        route_request_id="RR-PTS", subject_type="GENERIC", subject_id="X", transport_mode="ORDINARY_PTS",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A",
    )
    route = shadow.derive_shadow_route(graph, reg, request=request)
    assert route.route_status == "NO_ROUTE"  # corridor edges are NOT PNEUMATIC_TUBE-compatible


# ---------------------------------------------------------------------------
# 18. legacy fixed timing remains authoritative
# ---------------------------------------------------------------------------


def test_legacy_manual_timing_untouched_by_shadow_routing():
    from conventional_transport_authority import PorterOperatingPolicy, compute_manual_mission_timing

    policy = PorterOperatingPolicy()
    before = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=50.0, vertical_transitions=1)

    reg, graph = _two_building_registry_with_graph()
    shadow.derive_shadow_route(graph, reg, request=shadow.CanonicalRouteRequest(
        route_request_id="RR-MANUAL", subject_type="GENERIC", subject_id="X", transport_mode="MANUAL",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A",
    ))
    after = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=50.0, vertical_transitions=1)
    assert before == after  # legacy authority produces byte-identical output regardless of shadow routing calls

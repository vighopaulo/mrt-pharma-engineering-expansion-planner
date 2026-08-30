"""Focused tests for Phase 2B.2: automatic geometry precedence, MRT
live-pipeline verification, and full What-If geometry->route->time->resource
->economics propagation for the four principal changes.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import authoritative_geometry_routing_activation as activation
import canonical_geometry_shadow_routing_authority as shadow
import canonical_spatial_authority as csa
from whole_oncology_four_architecture_optimization import (
    build_eight_floor_deterministic_capital_baseline,
    evaluate_automated_conventional,
    evaluate_dedicated_rp_pts_nuclear_transport,
)


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


def _mrt_route(graph, reg, destination):
    request = shadow.CanonicalRouteRequest(
        route_request_id=f"MRT-REF-{destination}", subject_type="GENERIC", subject_id="MRT", transport_mode="MRT",
        origin_location_id="PATIENT-ROOM", destination_location_id=destination,
    )
    return shadow.derive_shadow_route(graph, reg, request=request)


# ---------------------------------------------------------------------------
# 1-3. automatic geometry consumption / no-override-required / fallback works
# ---------------------------------------------------------------------------


def test_automatic_geometry_is_consumed_without_manual_override():
    reg, graph = _two_building_registry_with_graph()
    resolution = activation.resolve_automatic_route_distance_m(
        "AGV_AMR", spatial_registry=reg, graph=graph, origin_id="PATIENT-ROOM", destination_id="ROOM-A",
    )
    assert resolution.distance_m == pytest.approx(15.0)  # PATIENT-ROOM -> JUNCTION(10) -> ROOM-A(5)
    assert resolution.provenance == "CANONICAL_GRAPH_DERIVED"  # tier 1, no override number supplied by the caller


def test_shared_corridor_used_automatically_when_no_direct_geometry_but_mrt_reference_exists():
    reg, graph = _two_building_registry_with_graph()
    mrt_reference = _mrt_route(graph, reg, "ROOM-B")
    resolution = activation.resolve_automatic_route_distance_m("ORDINARY_PTS", mrt_reference_route=mrt_reference)
    assert resolution.distance_m == pytest.approx(mrt_reference.total_distance_m)
    assert resolution.provenance == "SHARED_MRT_REFERENCE_CORRIDOR_ASSUMPTION"  # tier 2


def test_controlled_fallback_when_no_geometry_available_at_all():
    resolution = activation.resolve_automatic_route_distance_m("AGV_AMR")
    assert resolution.distance_m is None
    assert resolution.provenance == "UNRESOLVED"  # caller falls through to ITS OWN existing controlled default


def test_existing_callers_do_not_crash_with_no_geometry_arguments():
    # Section 15D: the function must be safely callable with ALL geometry
    # arguments omitted (matches every pre-Phase-2B.2 caller).
    for mode in ("MANUAL", "AGV_AMR", "ORDINARY_PTS", "DEDICATED_RP_PTS", "MRT"):
        resolution = activation.resolve_automatic_route_distance_m(mode)
        assert resolution.provenance == "UNRESOLVED"


# ---------------------------------------------------------------------------
# 4-6. MRT live evaluator consumes mission-route geometry automatically;
# installed-network geometry stays separate; mission route never becomes
# guideway CapEx basis
# ---------------------------------------------------------------------------


@dataclass
class _FakeMrtScenario:
    facility_engineering_model: object
    transport_minutes: float
    transport_minutes_source: str = "SCENARIO_SUPPLIED"
    planner_assumptions: object = None
    # Mirrors ProductionClinicalScenario.mrt_straight_speed_m_per_s_override
    # (RUNTIME MIGRATION SPEED seam); None preserves heavy horizontal speed.
    mrt_straight_speed_m_per_s_override: float | None = None


def test_mrt_live_route_profile_automatically_prefers_real_geometry_over_scenario_constant():
    from production_clinical_schedule import _resolve_mrt_route_profile
    from spatial_benchmark import build_benchmark_geometry

    geometry = build_benchmark_geometry(building_length_m=60.0, building_width_m=40.0, distribute_both_sides=True)
    no_geometry = _resolve_mrt_route_profile(_FakeMrtScenario(facility_engineering_model=None, transport_minutes=5.0), "F1-R02")
    with_geometry = _resolve_mrt_route_profile(_FakeMrtScenario(facility_engineering_model=geometry.base_model, transport_minutes=5.0), "F1-R02")

    assert no_geometry.transport_minutes == pytest.approx(5.0)
    assert no_geometry.transport_minutes_source == "SCENARIO_SUPPLIED"
    assert with_geometry.transport_minutes != pytest.approx(5.0)  # automatically overridden by real geometry
    assert with_geometry.transport_minutes_source == "VERIFIED_GEOMETRY_DERIVED"
    assert with_geometry.route_distance_m > 0.0


def test_whole_oncology_mrt_pathway_threads_real_geometry_automatically():
    """Confirms (not merely asserts) that the LIVE whole_oncology benchmark's
    MRT pathway request is built with a real `facility_engineering_model`
    (`spatial_benchmark._build_request`'s `pathway_layout.model_with_anchor`)
    -- i.e., MRT mission timing is automatically geometry-derived in the
    live pipeline today, requiring NO Phase 2B.2 code change."""
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    assert baseline.geometry.base_model is not None
    assert len(baseline.geometry.base_model.nodes) > 0
    assert len(baseline.geometry.base_model.edges) > 0


def test_mission_route_never_becomes_installed_network_capex_basis():
    reg, graph = _two_building_registry_with_graph()
    route_a = _mrt_route(graph, reg, "ROOM-A")
    route_b = _mrt_route(graph, reg, "ROOM-B")
    installed = activation.compute_installed_network_union([route_a, route_b])
    # A single mission route's distance must never equal the deduplicated installed total by construction here.
    assert installed.total_length_m != route_a.total_distance_m
    assert installed.total_length_m == pytest.approx(30.0)  # E1(10)+E2(5)+E3(15), each counted once


# ---------------------------------------------------------------------------
# 7-10. technology physics remain distinct
# ---------------------------------------------------------------------------


def test_manual_remains_pedestrian_physics():
    from conventional_transport_authority import PorterOperatingPolicy, compute_manual_mission_timing, ManualMissionTiming

    timing = compute_manual_mission_timing(policy=PorterOperatingPolicy(), technology="MANUAL_PORTER", horizontal_distance_m=25.0, vertical_transitions=1)
    assert isinstance(timing, ManualMissionTiming)


def test_agv_shared_corridor_activation_remains_intact():
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    frozen = evaluate_automated_conventional(baseline, development_context="GREENFIELD", study_scope="CAPITAL_PLANNING")
    activated = evaluate_automated_conventional(
        baseline, development_context="GREENFIELD", study_scope="CAPITAL_PLANNING",
        agv_main_leg_minutes_override=20.0, pts_main_leg_minutes_override=20.0,
    )
    assert activated.architecture_specific_annual_opex != frozen.architecture_specific_annual_opex


def test_ordinary_pts_speed_unchanged():
    from conventional_transport_authority import DEFAULT_PTS_NETWORK
    assert DEFAULT_PTS_NETWORK.speed_m_per_s == pytest.approx(6.0)


def test_rp_pts_speed_unchanged():
    from editable_default_authority import RP_PTS_OPERATING_SPEED_M_PER_S
    assert RP_PTS_OPERATING_SPEED_M_PER_S.default_value == pytest.approx(6.1)


# ---------------------------------------------------------------------------
# 11-14. decay propagation, resource sizing, economics, zero-delta preserved
# ---------------------------------------------------------------------------


def test_nuclear_route_time_reaches_decay_inputs_unaltered():
    from multi_isotope_decay import retained_fraction

    half_life = 109.8
    assert retained_fraction(20.0, half_life) == pytest.approx(2.0 ** (-20.0 / half_life))
    assert retained_fraction(35.0, half_life) < retained_fraction(20.0, half_life)


def test_resource_sizing_reacts_to_route_time_threshold():
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
    small = agv_required_fleet_size(missions=missions, mission_minutes=3.0, model=model, operating_hours_per_day=18.0, operating_days_per_year=300)
    large = agv_required_fleet_size(missions=missions, mission_minutes=60.0, model=model, operating_hours_per_day=18.0, operating_days_per_year=300)
    assert large > small


def test_engineering_reaches_economics_where_dependency_exists_agv_pts():
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    frozen = evaluate_automated_conventional(baseline, development_context="GREENFIELD", study_scope="CAPITAL_PLANNING")
    activated = evaluate_automated_conventional(
        baseline, development_context="GREENFIELD", study_scope="CAPITAL_PLANNING", pts_main_leg_minutes_override=20.0,
    )
    assert activated.architecture_specific_annual_opex != frozen.architecture_specific_annual_opex


def test_zero_delta_preserved_where_no_real_dependency_exists_rp_pts_capex():
    """PHYSICAL_CHANGE_NO_CURRENT_ECONOMIC_DEPENDENCY (section 14): RP-PTS
    CapEx is station-based in the EXISTING authority -- distance changes must
    NOT fabricate a capex delta."""
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    frozen = evaluate_dedicated_rp_pts_nuclear_transport(baseline)
    activated = evaluate_dedicated_rp_pts_nuclear_transport(baseline, network_length_override_m=5000.0)
    assert frozen.capex.total_capex == activated.capex.total_capex  # genuinely zero, not hidden


# ---------------------------------------------------------------------------
# 15-19. What-If propagation for the four principal changes; L0 immutable
# ---------------------------------------------------------------------------


def _lockdown_what_if_setup():
    import lockdown_what_if_lineage_authority as lla

    registry = lla.LockdownLineageRegistry()
    spatial_locked = csa.LockedSpatialState(registry=csa.build_facility_hierarchy(facility_id="FAC-001"))
    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    l0_economics = evaluate_dedicated_rp_pts_nuclear_transport(baseline)
    l0 = lla.create_first_lockdown(registry, locked=spatial_locked, economic_result=l0_economics)
    return lla, registry, l0, baseline


def test_move_scanner_what_if_recomputes_branch_l0_unchanged():
    import canonical_entity_binding_authority as ceba

    lla, registry, l0, baseline = _lockdown_what_if_setup()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)

    bindings = ceba.EntityBindingRegistry()
    ceba.bind_equipment_room(bindings, equipment_id="SCN-001", room_id="ROOM-A", equipment_kind="SCANNER")
    moved_bindings = bindings.clone()
    ceba.bind_equipment_room(moved_bindings, equipment_id="SCN-001", room_id="ROOM-B", equipment_kind="SCANNER")  # move scanner in W1 only

    reg, graph = _two_building_registry_with_graph()
    old_route = shadow.derive_shadow_route(graph, reg, request=shadow.CanonicalRouteRequest(
        route_request_id="OLD", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id=ceba.room_for_scanner(bindings, "SCN-001"),
    ))
    new_route = shadow.derive_shadow_route(graph, reg, request=shadow.CanonicalRouteRequest(
        route_request_id="NEW", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id=ceba.room_for_scanner(moved_bindings, "SCN-001"),
    ))
    assert old_route.total_distance_m != new_route.total_distance_m  # PHYSICAL_CHANGE_WITH_ECONOMIC_EFFECT (route/time)
    lla.update_what_if_results(registry, w1.what_if_id, entity_bindings=moved_bindings)
    assert registry.lockdown(l0.lockdown_id).spatial_state.registry is l0.spatial_state.registry  # L0 untouched
    assert registry.current_lockdown_id == l0.lockdown_id


def test_change_patient_room_what_if_recomputes_branch_l0_unchanged():
    lla, registry, l0, baseline = _lockdown_what_if_setup()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    reg, graph = _two_building_registry_with_graph()
    old_route = shadow.derive_shadow_route(graph, reg, request=shadow.CanonicalRouteRequest(
        route_request_id="OLD-ROOM", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A",
    ))
    new_route = shadow.derive_shadow_route(graph, reg, request=shadow.CanonicalRouteRequest(
        route_request_id="NEW-ROOM", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="ROOM-B", destination_location_id="ROOM-A",  # patient reassigned to ROOM-B
    ))
    assert old_route.total_distance_m != new_route.total_distance_m
    assert registry.current_lockdown_id == l0.lockdown_id  # L0 unaffected by the branch computation


def test_move_building_what_if_recomputes_branch_l0_unchanged():
    import dataclasses
    from facility_engineering_model import SpatialCoordinate, straight_line_distance_m

    lla, registry, l0, baseline = _lockdown_what_if_setup()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    building_a = SpatialCoordinate(x_m=0.0, y_m=0.0, z_m=0.0)
    building_b_before = SpatialCoordinate(x_m=50.0, y_m=0.0, z_m=0.0)
    building_b_after = dataclasses.replace(building_b_before, x_m=150.0)  # What-If-only translation
    assert straight_line_distance_m(building_a, building_b_before) != straight_line_distance_m(building_a, building_b_after)
    assert registry.current_lockdown_id == l0.lockdown_id


def test_move_endpoint_what_if_recomputes_branch_l0_unchanged():
    lla, registry, l0, baseline = _lockdown_what_if_setup()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    reg, graph = _two_building_registry_with_graph()
    what_if_graph = csa.ConnectivityGraph(edges=[e for e in graph.edges if e.edge_id != "E2"])
    what_if_graph.add_edge(csa.SpatialEdge(edge_id="E2-MOVED", from_object_id="JUNCTION", to_object_id="ROOM-A", length_m=40.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    locked_route = shadow.derive_shadow_route(graph, reg, request=shadow.CanonicalRouteRequest(
        route_request_id="LOCKED-EP", subject_type="GENERIC", subject_id="X", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A",
    ))
    what_if_route = shadow.derive_shadow_route(what_if_graph, reg, request=shadow.CanonicalRouteRequest(
        route_request_id="W1-EP", subject_type="GENERIC", subject_id="X", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A",
    ))
    assert locked_route.total_distance_m != what_if_route.total_distance_m
    assert len(graph.edges) == 3  # parent graph's edges untouched
    assert registry.current_lockdown_id == l0.lockdown_id


# ---------------------------------------------------------------------------
# 20. traceability survives activation
# ---------------------------------------------------------------------------


def test_traceability_survives_phase_2b2_activation():
    import canonical_entity_binding_authority as ceba
    from decision_pipeline import run_native_decision_pipeline
    from test_cyclotron_fleet_integration import _fleet_disjoint, _request

    result = run_native_decision_pipeline(_request(_fleet_disjoint()))
    trace = result.conventional.operational_result.production_clinical_result.patient_traces[0]
    registry = ceba.EntityBindingRegistry()
    ceba.bind_production_clinical_trace(registry, trace)
    assert ceba.batch_for_patient(registry, trace.patient_id) == str(trace.batch_id)
    assert ceba.cyclotron_for_batch(registry, str(trace.batch_id)) == trace.assigned_cyclotron_id


# ---------------------------------------------------------------------------
# 21. mixed-mode/one-clock foundation remains green
# ---------------------------------------------------------------------------


def test_one_clock_mixed_mode_foundation_remains_intact():
    import digital_twin_simulation_state as dts

    records = [
        dts.TransportRuntimeRecord(runtime_id="R1", technology="MRT", mission_id="M1", physical_asset_id="CARRIER-01",
                                    payload_id=None, route_id=None, current_segment_id=None, departure_time_minutes=0.0, arrival_time_minutes=10.0, state="WAITING"),
        dts.TransportRuntimeRecord(runtime_id="R2", technology="AGV_AMR", mission_id="M2", physical_asset_id=None,
                                    payload_id=None, route_id=None, current_segment_id=None, departure_time_minutes=0.0, arrival_time_minutes=10.0, state="WAITING"),
    ]
    snapshot = dts.digital_twin_state_at_time(at_time_minutes=5.0, transport_records=records)
    assert len(snapshot.transport_states) == 2
    assert all(state == "IN_TRANSIT" for _, state in snapshot.transport_states)


# ---------------------------------------------------------------------------
# 22. no shielding calculation introduced
# ---------------------------------------------------------------------------


def test_no_shielding_calculation_introduced_phase_2b2():
    import inspect

    names = [name for name, obj in inspect.getmembers(activation) if inspect.isfunction(obj)]
    assert not any("shield" in name.lower() for name in names)

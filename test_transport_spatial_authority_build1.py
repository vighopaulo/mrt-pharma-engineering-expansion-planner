"""Focused tests for Transport Spatial Authority Build 1:

- RGHT taxonomy resolution + legacy AGV_AMR compatibility
  (transport_technology_authority.py)
- mode-neutral canonical mission-routing bridge
  (transport_mission_route_bridge.py)
- MRT/manual operational-mission wiring in operational_day_orchestrator.py

Covers items 1-12 (taxonomy) and 13-31 (routing bridge) from the Transport
Spatial Authority Build 1 specification.
"""

from datetime import datetime

import pytest

import canonical_spatial_authority as csa
import conventional_transport_authority as cta
import operational_day_orchestrator as ody
import transport_mission_route_bridge as trb
import transport_technology_authority as tta

DAY_START = datetime(2026, 2, 3, 7, 0)


def _build_test_registry_and_graph():
    reg = csa.build_facility_hierarchy(facility_id="FAC-TSAB1")
    csa.add_building(reg, facility_id="FAC-TSAB1", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-TSAB1", building_id="BLDG-A", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-TSAB1", building_id="BLDG-A", floor_id="F1", room_id="ROOM-ORIGIN")
    csa.add_room(reg, facility_id="FAC-TSAB1", building_id="BLDG-A", floor_id="F1", room_id="ROOM-DEST")
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(
        edge_id="E1", from_object_id="ROOM-ORIGIN", to_object_id="ROOM-DEST", length_m=42.0,
        compatible_modes=frozenset({"MRT", "WALKING_PORTER", "AGV_AMR", "PNEUMATIC_TUBE"}),
    ))
    return reg, graph


def _test_event(*, source_object_id="ROOM-ORIGIN", destination_object_id="ROOM-DEST", service_class="RADIOPHARMACEUTICAL_NUCLEAR"):
    return ody.OperationalDayEvent(
        event_id="EVT-1", simulation_time=DAY_START, sequence=1, event_type="TEST", trigger_type="CALENDAR_SCHEDULED",
        determinism="FIXED_SCHEDULED", patient_id="NOT_APPLICABLE", service_class=service_class,
        source_object_id=source_object_id, destination_object_id=destination_object_id, payload_reference=None,
        priority="NOT_APPLICABLE", provenance="test",
    )


# ---------------------------------------------------------------------------
# Taxonomy (items 1-12)
# ---------------------------------------------------------------------------


def test_1_canonical_rght_identity_exists():
    assert tta.RAIL_GUIDED_HOSPITAL_TRANSPORT == "RGHT"


def test_2_rail_guided_hospital_transport_label_exists():
    assert tta.RGHT_LABEL == "RAIL_GUIDED_HOSPITAL_TRANSPORT"


def test_3_legacy_agv_amr_normalizes_to_rght():
    assert tta.normalize_transport_technology("AGV_AMR") == "RGHT"


def test_4_existing_serialized_legacy_agv_value_remains_accepted():
    assert "AGV_AMR" in cta.TECHNOLOGY_STREAM_COMPATIBILITY
    assert cta.is_technology_compatible("AGV_AMR", "CLEAN_LINEN") is True
    assert cta.is_technology_compatible("AGV_AMR", "SPECIMEN_BLOOD") is False


def test_5_rght_and_floor_agv_amr_are_distinct():
    assert tta.RAIL_GUIDED_HOSPITAL_TRANSPORT != tta.FLOOR_AGV_AMR


def test_6_floor_agv_amr_remains_not_implemented():
    assert tta.FLOOR_AGV_AMR_IMPLEMENTATION_STATUS == "NOT_IMPLEMENTED"


def test_7_telelift_not_used_as_canonical_transport_type():
    assert tta.is_vendor_brand_name("Telelift") is True
    assert tta.RAIL_GUIDED_HOSPITAL_TRANSPORT != "TELELIFT"
    assert "TELELIFT" not in (tta.RAIL_GUIDED_HOSPITAL_TRANSPORT, tta.RGHT_LABEL, tta.FLOOR_AGV_AMR)


def test_8_swisslog_not_used_as_canonical_transport_type():
    assert tta.is_vendor_brand_name("Swisslog") is True
    assert tta.RAIL_GUIDED_HOSPITAL_TRANSPORT != "SWISSLOG"
    assert "SWISSLOG" not in (tta.RAIL_GUIDED_HOSPITAL_TRANSPORT, tta.RGHT_LABEL, tta.FLOOR_AGV_AMR)


def test_9_current_rght_economics_remain_numerically_unchanged():
    model = cta.DEFAULT_AGV_MODEL
    assert model.vehicle_capex == 100_000.0
    assert model.system_integration_capex == 50_000.0
    assert model.annual_maintenance_opex == 4_000.0
    assert model.annual_energy_opex == 1_500.0
    assert model.speed_m_per_s == 0.8
    # additive provenance fields carry the required status, without changing any economic value
    assert model.technology_class == "RGHT"
    assert model.commercial_calibration_status == tta.RGHT_VENDOR_QUOTE_CALIBRATION
    assert model.vendor_comparator_basis == tta.RGHT_VENDOR_COMPARATOR_BASIS


def test_10_architecture_optimization_ranking_unchanged_for_unchanged_inputs():
    streams = ("PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY")
    first = cta.assign_technology_per_stream(portfolio_id="MANUAL_PLUS_AGV_PLUS_PTS", streams=streams)
    second = cta.assign_technology_per_stream(portfolio_id="MANUAL_PLUS_AGV_PLUS_PTS", streams=streams)
    assert tuple(a.assigned_technology for a in first) == tuple(a.assigned_technology for a in second)
    assert tuple(a.assigned_technology for a in first) == ("AGV_AMR", "PNEUMATIC_TUBE", "AGV_AMR", "AGV_AMR")


def test_11_existing_stream_compatibility_unchanged_except_semantic_normalization():
    assert cta.TECHNOLOGY_STREAM_COMPATIBILITY["AGV_AMR"] == frozenset({"CLEAN_LINEN", "STERILE_CLEAN_SUPPLY", "PHARMACY_INFUSION"})
    assert cta.TECHNOLOGY_STREAM_COMPATIBILITY["PNEUMATIC_TUBE"] == frozenset({"SPECIMEN_BLOOD", "PHARMACY_INFUSION"})
    # normalization is a separate, non-mutating reporting layer
    assert tta.normalize_transport_technology("AGV_AMR") == "RGHT"
    assert cta.TECHNOLOGY_STREAM_COMPATIBILITY["AGV_AMR"] == frozenset({"CLEAN_LINEN", "STERILE_CLEAN_SUPPLY", "PHARMACY_INFUSION"})


def test_12_user_facing_semantic_output_can_report_rght():
    reg, graph = _build_test_registry_and_graph()
    resolution = trb.resolve_mission_route(
        mission_id="M-1", transport_mode="AGV_AMR", origin_object_id="ROOM-ORIGIN", destination_object_id="ROOM-DEST",
        registry=reg, graph=graph,
    )
    display_name = tta.normalize_transport_technology(resolution.transport_mode)
    assert display_name == "RGHT"


# ---------------------------------------------------------------------------
# Routing bridge (items 13-31)
# ---------------------------------------------------------------------------


def test_13_route_resolution_distinguishes_calibrated_vs_not_calibrated():
    reg, graph = _build_test_registry_and_graph()
    calibrated = trb.resolve_mission_route(mission_id="M", transport_mode="MRT", origin_object_id="ROOM-ORIGIN", destination_object_id="ROOM-DEST", registry=reg, graph=graph)
    not_calibrated = trb.resolve_mission_route(mission_id="M", transport_mode="MRT", origin_object_id="ROOM-ORIGIN", destination_object_id="ROOM-DEST")
    assert calibrated.route_status == "ROUTE_CALIBRATED"
    assert not_calibrated.route_status == "ROUTE_NOT_CALIBRATED"


def test_14_mrt_mission_with_canonical_route_receives_that_route():
    reg, graph = _build_test_registry_and_graph()
    event = _test_event()
    mission = ody.build_mission_from_event(event, registry=reg, graph=graph)
    assert mission.route_resolution is not None
    assert mission.route_resolution.route_status == "ROUTE_CALIBRATED"


def test_15_mrt_route_distance_equals_canonical_route_authority_distance():
    reg, graph = _build_test_registry_and_graph()
    event = _test_event()
    mission = ody.build_mission_from_event(event, registry=reg, graph=graph)
    assert mission.route_resolution.route_distance_m == 42.0
    assert mission.mrt_mission.route_length_m == 42.0


def test_16_mrt_canonical_route_takes_precedence_over_flat_placeholder():
    reg, graph = _build_test_registry_and_graph()
    event = _test_event()
    mission = ody.build_mission_from_event(event, registry=reg, graph=graph)
    assert mission.mrt_mission.route_length_m != ody.MRT_CONTROLLED_ROUTE_LENGTH_M
    assert mission.mrt_mission.route_length_m == 42.0


def test_17_mrt_route_node_path_trace_preserved_where_available():
    reg, graph = _build_test_registry_and_graph()
    event = _test_event()
    mission = ody.build_mission_from_event(event, registry=reg, graph=graph)
    assert mission.route_resolution.route_node_ids == ("ROOM-ORIGIN", "ROOM-DEST")


def test_18_mrt_mission_without_route_does_not_fabricate_geometry():
    event = _test_event()
    mission = ody.build_mission_from_event(event)
    assert mission.route_resolution is not None
    assert mission.route_resolution.route_status == "ROUTE_NOT_CALIBRATED"
    assert mission.route_resolution.route_distance_m is None
    assert mission.mrt_mission.route_length_m == ody.MRT_CONTROLLED_ROUTE_LENGTH_M


def test_19_manual_mission_receives_real_canonical_distance_where_available():
    reg, graph = _build_test_registry_and_graph()
    mission = ody.MissionSpec(
        mission_id="M-MANUAL", trigger_event_id="EVT-1", patient_id="NOT_APPLICABLE", service_class="CLEAN_LINEN",
        origin="ROOM-ORIGIN", destination="ROOM-DEST", earliest_dispatch_minutes=0.0, required_arrival_minutes=None,
        priority="NOT_APPLICABLE", provenance="test",
    )
    traces = ody.execute_conventional_missions([mission], architecture="MANUAL_CONVENTIONAL", registry=reg, graph=graph)
    assert traces[0].route_status == "ROUTE_CALIBRATED"
    assert traces[0].route_resolution.route_distance_m == 42.0


def test_20_manual_mission_without_canonical_route_remains_honestly_not_calibrated():
    mission = ody.MissionSpec(
        mission_id="M-MANUAL-2", trigger_event_id="EVT-1", patient_id="NOT_APPLICABLE", service_class="CLEAN_LINEN",
        origin="ROOM-ORIGIN", destination="ROOM-DEST", earliest_dispatch_minutes=0.0, required_arrival_minutes=None,
        priority="NOT_APPLICABLE", provenance="test",
    )
    traces = ody.execute_conventional_missions([mission], architecture="MANUAL_CONVENTIONAL")
    assert traces[0].route_status == "ROUTE_NOT_CALIBRATED"


def test_21_rght_mission_resolves_when_a_real_rght_network_is_supplied():
    # Transport Spatial Authority Build 2 deliberately supersedes Build 1's premise
    # that RGHT never has a spatial network: a graph with a real AGV_AMR-tagged
    # connected edge now legitimately produces ROUTE_CALIBRATED (see
    # rght_spatial_network_authority.py / test_transport_spatial_authority_build2.py
    # for the "genuinely no RGHT network" -> SPATIAL_NETWORK_NOT_CALIBRATED proof).
    reg, graph = _build_test_registry_and_graph()  # graph has an AGV_AMR-compatible edge
    resolution = trb.resolve_mission_route(mission_id="M", transport_mode="AGV_AMR", origin_object_id="ROOM-ORIGIN", destination_object_id="ROOM-DEST", registry=reg, graph=graph)
    assert resolution.route_status == "ROUTE_CALIBRATED"


def test_22_pts_mission_resolves_when_a_real_pts_network_is_supplied():
    # Transport Spatial Authority Build 3 deliberately supersedes Build 1's premise
    # that PTS never has a spatial network: a graph with a real PNEUMATIC_TUBE-tagged
    # connected edge now legitimately produces ROUTE_CALIBRATED (see
    # pts_spatial_network_authority.py / test_transport_spatial_authority_build3.py
    # for the "genuinely no PTS network" -> SPATIAL_NETWORK_NOT_CALIBRATED proof).
    reg, graph = _build_test_registry_and_graph()  # graph has a PNEUMATIC_TUBE-compatible edge
    resolution = trb.resolve_mission_route(mission_id="M", transport_mode="PNEUMATIC_TUBE", origin_object_id="ROOM-ORIGIN", destination_object_id="ROOM-DEST", registry=reg, graph=graph)
    assert resolution.route_status == "ROUTE_CALIBRATED"


def test_23_not_calibrated_rght_does_not_become_infeasible():
    # Transport Spatial Authority Build 2: this scenario's graph HAS a real
    # AGV_AMR-connected edge, so it now legitimately resolves ROUTE_CALIBRATED
    # (see test_transport_spatial_authority_build2.py for the genuinely-not-
    # calibrated feasibility proof). Feasibility (a computed, non-None
    # total_minutes) is what this test still verifies either way.
    reg, graph = _build_test_registry_and_graph()
    mission = ody.MissionSpec(
        mission_id="M-RGHT", trigger_event_id="EVT-1", patient_id="NOT_APPLICABLE", service_class="LAUNDRY_CLEAN_LINEN",
        origin="ROOM-ORIGIN", destination="ROOM-DEST", earliest_dispatch_minutes=0.0, required_arrival_minutes=None,
        priority="NOT_APPLICABLE", provenance="test",
    )
    traces = ody.execute_conventional_missions([mission], architecture="AUTOMATED_CONVENTIONAL", registry=reg, graph=graph)
    trace = traces[0]
    assert trace.resource_type == "AGV_AMR"
    assert trace.route_resolution.route_status == "ROUTE_CALIBRATED"
    assert isinstance(trace.total_minutes, float)  # still feasible/computed, never blocked


def test_24_not_calibrated_pts_does_not_become_infeasible():
    # Transport Spatial Authority Build 3: this scenario's graph HAS a real
    # PNEUMATIC_TUBE-connected edge, so it now legitimately resolves ROUTE_CALIBRATED
    # (see test_transport_spatial_authority_build3.py for the genuinely-not-
    # calibrated feasibility proof). Feasibility (a computed, non-None
    # total_minutes) is what this test still verifies either way.
    reg, graph = _build_test_registry_and_graph()
    mission = ody.MissionSpec(
        mission_id="M-PTS", trigger_event_id="EVT-1", patient_id="NOT_APPLICABLE", service_class="SPECIMEN_BLOOD",
        origin="ROOM-ORIGIN", destination="ROOM-DEST", earliest_dispatch_minutes=0.0, required_arrival_minutes=None,
        priority="NOT_APPLICABLE", provenance="test",
    )
    traces = ody.execute_conventional_missions([mission], architecture="AUTOMATED_CONVENTIONAL", registry=reg, graph=graph)
    trace = traces[0]
    assert trace.resource_type == "PTS"
    assert trace.route_resolution.route_status == "ROUTE_CALIBRATED"
    assert isinstance(trace.total_minutes, float)  # still feasible/computed, never blocked; timing itself is UNCHANGED by route calibration (Build 3 section 17/22)


def test_25_controlled_existing_timing_economic_fallback_remains_available():
    mission = ody.MissionSpec(
        mission_id="M-FLAT", trigger_event_id="EVT-1", patient_id="NOT_APPLICABLE", service_class="LAUNDRY_CLEAN_LINEN",
        origin="ROOM-ORIGIN", destination="ROOM-DEST", earliest_dispatch_minutes=0.0, required_arrival_minutes=None,
        priority="NOT_APPLICABLE", provenance="test",
    )
    traces = ody.execute_conventional_missions([mission], architecture="AUTOMATED_CONVENTIONAL")
    trace = traces[0]
    assert trace.resource_type == "AGV_AMR"
    expected_travel = (ody.CONTROLLED_TEST_DISTANCE_M / cta.DEFAULT_AGV_MODEL.speed_m_per_s) / 60.0
    last_mile = cta.compute_manual_mission_timing(policy=cta.PorterOperatingPolicy(), technology="MANUAL_PORTER", horizontal_distance_m=ody.AGV_PTS_LAST_MILE_DISTANCE_M)
    assert trace.total_minutes == pytest.approx(expected_travel + last_mile.total_minutes)


def test_26_visualization_not_imported_by_routing_bridge():
    import inspect
    lines = [l.strip() for l in inspect.getsource(trb).splitlines() if l.strip().startswith(("import ", "from "))]
    for line in lines:
        assert "openusd" not in line.lower()
        assert "usda" not in line.lower()


def test_27_openusd_not_imported_by_routing_bridge():
    import inspect
    lines = [l.strip() for l in inspect.getsource(trb).splitlines() if l.strip().startswith(("import ", "from "))]
    for line in lines:
        assert "pxr" not in line
        assert "openusd" not in line.lower()


def test_28_nvidia_not_imported_by_routing_bridge():
    import inspect
    source = inspect.getsource(trb)
    lines = [l.strip() for l in source.splitlines() if l.strip().startswith(("import ", "from "))]
    for line in lines:
        assert "omni" not in line.lower()
        assert "nvidia" not in line.lower()


def test_29_bentley_not_imported_by_routing_bridge():
    import inspect
    lines = [l.strip() for l in inspect.getsource(trb).splitlines() if l.strip().startswith(("import ", "from "))]
    for line in lines:
        assert "bentley" not in line.lower()


def test_30_route_bridge_does_not_mutate_canonical_geometry():
    reg, graph = _build_test_registry_and_graph()
    before = dict(reg.objects)
    trb.resolve_mission_route(mission_id="M", transport_mode="MRT", origin_object_id="ROOM-ORIGIN", destination_object_id="ROOM-DEST", registry=reg, graph=graph)
    after = dict(reg.objects)
    assert before.keys() == after.keys()
    for object_id in before:
        assert before[object_id] == after[object_id]


def test_31_route_bridge_does_not_mutate_lockdown_l0():
    reg, graph = _build_test_registry_and_graph()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    before = dict(locked.registry.objects)
    trb.resolve_mission_route(mission_id="M", transport_mode="MRT", origin_object_id="ROOM-ORIGIN", destination_object_id="ROOM-DEST", registry=what_if.registry, graph=graph)
    after = dict(locked.registry.objects)
    assert before.keys() == after.keys()
    for object_id in before:
        assert before[object_id] == after[object_id]

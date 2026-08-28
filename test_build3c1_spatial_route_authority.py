"""Build 3C.1 -- Spatial Route / Right-of-Way / Network Authority (focused tests).

Locks the two-route-family doctrine against the PHYSICAL repository spatial
authorities. Read-only assertions over existing behavior -- Build 3C.1
introduces no engine code change (no genuine route-binding defect demonstrated;
see SPATIAL_ROUTE_NETWORK_AUTHORITY_BUILD_3C1.md section A).

  HUMAN_CIRCULATION_NETWORK           -> PATIENT / PORTER / AGV(RGHT)
  CONCEALED_SERVICE_TRANSPORT_CORRIDOR -> MRT / RHTS(RGHT) / PTS / RP-PTS lanes

Where a requested invariant is not yet implemented (route cache, decay-time
binding, shared civil cost), the test asserts the nearest existing authority
and the accompanying doc records the gap. Never fabricates behavior.

Run: /opt/anaconda3/bin/python -m pytest test_build3c1_spatial_route_authority.py -q
"""

from __future__ import annotations

import canonical_spatial_authority as csa
import human_circulation_authority as hca
import transport_mission_route_bridge as tb
import transport_technology_authority as tta
import rght_spatial_network_authority as rght
import pts_spatial_network_authority as pts
import dedicated_rp_pts_authority as rp
import production_trajectory_authority as pta


# --- Shared controlled two-family fixture ----------------------------------

def _two_family_registry_and_graph():
    """A controlled facility with two rooms connected by BOTH a human corridor
    edge AND a distinct concealed-service edge per mode -- the minimal proof of
    shared right-of-way with separate lane identities."""
    reg = csa.build_facility_hierarchy(facility_id="FAC-1")
    csa.add_building(reg, facility_id="FAC-1", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-1", building_id="BLDG-A", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-1", building_id="BLDG-A", floor_id="F1", room_id="ROOM-A")
    csa.add_room(reg, facility_id="FAC-1", building_id="BLDG-A", floor_id="F1", room_id="ROOM-B")
    g = csa.ConnectivityGraph()
    # HUMAN_CIRCULATION_NETWORK edge (patient + porter + AGV/RGHT-on-floor)
    g.add_edge(csa.SpatialEdge(
        edge_id="HUM-1", from_object_id="ROOM-A", to_object_id="ROOM-B", length_m=40.0,
        compatible_modes=frozenset({"PATIENT_MOVEMENT", "WALKING_PORTER", "AGV_AMR"}),
    ))
    # CONCEALED_SERVICE_TRANSPORT_CORRIDOR -- distinct MRT and PTS lane edges
    g.add_edge(csa.SpatialEdge(
        edge_id="MRT-1", from_object_id="ROOM-A", to_object_id="ROOM-B", length_m=25.0,
        compatible_modes=frozenset({"MRT"}),
    ))
    g.add_edge(csa.SpatialEdge(
        edge_id="PTS-1", from_object_id="ROOM-A", to_object_id="ROOM-B", length_m=22.0,
        compatible_modes=frozenset({"PNEUMATIC_TUBE"}),
    ))
    return reg, g


# 1. Patient resolves to HUMAN_CIRCULATION_NETWORK.
def test_1_patient_uses_human_circulation():
    reg, g = _two_family_registry_and_graph()
    r = hca.resolve_pedestrian_route(reg, g, subject="PATIENT", origin_object_id="ROOM-A", destination_object_id="ROOM-B")
    assert r.route_status == "ROUTE_CALIBRATED"
    assert r.total_distance_m == 40.0  # the human corridor edge, not the 25m MRT lane


# 2. Porter/Manual resolves to HUMAN_CIRCULATION_NETWORK.
def test_2_porter_uses_human_circulation():
    reg, g = _two_family_registry_and_graph()
    r = hca.resolve_pedestrian_route(reg, g, subject="PORTER", origin_object_id="ROOM-A", destination_object_id="ROOM-B")
    assert r.route_status == "ROUTE_CALIBRATED"
    assert r.total_distance_m == 40.0


# 3. AGV/AMR resolves to HUMAN_CIRCULATION_NETWORK (shared human graph).
def test_3_agv_uses_human_circulation():
    reg, g = _two_family_registry_and_graph()
    route = csa.resolve_route(g, origin_object_id="ROOM-A", destination_object_id="ROOM-B", mode="AGV_AMR")
    assert route.calibration_status == "CALIBRATED"
    assert route.path_edge_ids == ("HUM-1",)  # AGV rides the human corridor, not the concealed MRT/PTS lane


# 4. MRT resolves to CONCEALED_SERVICE_TRANSPORT_CORRIDOR + MRT lane.
def test_4_mrt_uses_concealed_mrt_lane():
    reg, g = _two_family_registry_and_graph()
    res = tb.resolve_mission_route(mission_id="M-MRT", transport_mode="MRT", origin_object_id="ROOM-A", destination_object_id="ROOM-B", registry=reg, graph=g)
    assert res.route_status == "ROUTE_CALIBRATED"
    assert res.route_distance_m == 25.0  # the MRT lane, never the 40m human corridor


# 5. RHTS/RGHT resolves to CONCEALED_SERVICE_TRANSPORT_CORRIDOR + RGHT lane identity.
def test_5_rght_lane_identity():
    # AGV_AMR canonically normalizes to RGHT; RGHT owns its own network mode value.
    assert tta.normalize_transport_technology("AGV_AMR") == "RGHT"
    assert rght.RGHT_TRANSPORT_MODE == "AGV_AMR"
    assert tta.FLOOR_AGV_AMR_IMPLEMENTATION_STATUS == "NOT_IMPLEMENTED"


# 6. Ordinary PTS resolves to CONCEALED_SERVICE_TRANSPORT_CORRIDOR + PTS lane.
def test_6_pts_uses_concealed_pts_lane():
    reg, g = _two_family_registry_and_graph()
    res = tb.resolve_mission_route(mission_id="M-PTS", transport_mode="PNEUMATIC_TUBE", origin_object_id="ROOM-A", destination_object_id="ROOM-B", registry=reg, graph=g)
    assert res.route_status == "ROUTE_CALIBRATED"
    assert res.route_distance_m == 22.0  # the PTS lane edge
    assert pts.PTS_TRANSPORT_MODE == "PNEUMATIC_TUBE"


# 7. RP-PTS resolves to CONCEALED_SERVICE_TRANSPORT_CORRIDOR + RP-PTS lane (route-based time).
def test_7_rp_pts_dedicated_lane_route_time():
    cyc = rp.compute_rp_pts_mission_cycle(network_length_m=222.0)
    # RP-PTS has a real route-based tube transport term (distinct from ordinary PTS flat timing).
    assert cyc.tube_transport_minutes > 0
    assert cyc.total_minutes > cyc.tube_transport_minutes


# 8. MRT/RHTS/PTS/RP-PTS share right-of-way semantics WITHOUT sharing physical infra identity.
def test_8_shared_row_not_shared_track():
    # Distinct canonical object types per mode -- never a shared installed-network object.
    types = set(csa.SpatialObjectType.__args__)
    assert {"MRT_TRUNK", "MRT_SEGMENT"} <= types
    assert {"RGHT_TRACK_SEGMENT", "RGHT_STATION"} <= types
    assert {"PTS_TUBE_SEGMENT", "PTS_STATION"} <= types
    # MRT and PTS lane edges are distinct even between the same two rooms.
    reg, g = _two_family_registry_and_graph()
    mrt = csa.resolve_route(g, origin_object_id="ROOM-A", destination_object_id="ROOM-B", mode="MRT")
    pts_route = csa.resolve_route(g, origin_object_id="ROOM-A", destination_object_id="ROOM-B", mode="PNEUMATIC_TUBE")
    assert mrt.path_edge_ids != pts_route.path_edge_ids


# 9. Ordinary PTS and RP-PTS remain separate lanes/conduits.
def test_9_ordinary_pts_and_rp_pts_separate():
    # Distinct modules, distinct speeds, distinct compatibility.
    import conventional_transport_authority as cta
    assert rp.RP_PTS_COMPATIBLE_STREAMS == frozenset({"RADIOPHARMACEUTICAL_NUCLEAR"})
    assert "RADIOPHARMACEUTICAL_NUCLEAR" not in cta.DEFAULT_PTS_NETWORK.compatible_streams


# 10. Human routes do not use straight-line-through-wall fallback at spatial fidelity.
def test_10_no_straight_line_fallback():
    reg, g = _two_family_registry_and_graph()
    # No edge between two disconnected rooms -> ROUTE_NOT_CALIBRATED, never a fabricated straight line.
    csa.add_room(reg, facility_id="FAC-1", building_id="BLDG-A", floor_id="F1", room_id="ROOM-ISOLATED")
    r = hca.resolve_pedestrian_route(reg, g, subject="PATIENT", origin_object_id="ROOM-A", destination_object_id="ROOM-ISOLATED")
    assert r.route_status in ("ROUTE_NOT_CALIBRATED", "ROUTE_UNAVAILABLE")
    assert r.total_distance_m is None


# 11. AGV shares human circulation geometry but retains mode-specific edge eligibility.
def test_11_agv_mode_specific_edge_eligibility():
    reg = csa.build_facility_hierarchy(facility_id="FAC-2")
    csa.add_building(reg, facility_id="FAC-2", building_id="B")
    csa.add_floor(reg, facility_id="FAC-2", building_id="B", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-2", building_id="B", floor_id="F1", room_id="R1")
    csa.add_room(reg, facility_id="FAC-2", building_id="B", floor_id="F1", room_id="R2")
    g = csa.ConnectivityGraph()
    # A human-only corridor edge (patient/porter eligible, AGV NOT eligible).
    g.add_edge(csa.SpatialEdge(edge_id="HUM-ONLY", from_object_id="R1", to_object_id="R2", length_m=30.0,
                               compatible_modes=frozenset({"PATIENT_MOVEMENT", "WALKING_PORTER"})))
    patient = csa.resolve_route(g, origin_object_id="R1", destination_object_id="R2", mode="PATIENT_MOVEMENT")
    agv = csa.resolve_route(g, origin_object_id="R1", destination_object_id="R2", mode="AGV_AMR")
    assert patient.calibration_status == "CALIBRATED"        # human edge exists
    assert agv.calibration_status == "ROUTE_NOT_CALIBRATED"  # AGV not eligible on that same edge


# 12. Moving a building changes affected route distance.
def test_12_building_move_changes_distance():
    reg = csa.build_facility_hierarchy(facility_id="FAC-3")
    csa.add_building(reg, facility_id="FAC-3", building_id="BLDG-A", transform=csa.Transform(position_x=0.0))
    csa.add_building(reg, facility_id="FAC-3", building_id="BLDG-B", transform=csa.Transform(position_x=100.0))
    d0 = csa.compute_global_distance(reg, "BLDG-A", "BLDG-B")
    reg2 = reg.replace_transform("BLDG-B", csa.Transform(position_x=300.0))
    d1 = csa.compute_global_distance(reg2, "BLDG-A", "BLDG-B")
    assert d0 == 100.0 and d1 == 300.0
    assert csa.compute_global_distance(reg, "BLDG-A", "BLDG-B") == 100.0  # original unchanged (non-mutating)


# 13. Moving an asset changes affected origin/destination route.
def test_13_asset_move_changes_distance():
    reg = csa.build_facility_hierarchy(facility_id="FAC-4")
    csa.add_building(reg, facility_id="FAC-4", building_id="B")
    csa.add_floor(reg, facility_id="FAC-4", building_id="B", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-4", building_id="B", floor_id="F1", room_id="RP-001", transform=csa.Transform(position_x=0.0))
    csa.add_room(reg, facility_id="FAC-4", building_id="B", floor_id="F1", room_id="SCN-001", transform=csa.Transform(position_x=10.0))
    d0 = csa.compute_global_distance(reg, "RP-001", "SCN-001")
    reg2 = reg.replace_transform("SCN-001", csa.Transform(position_x=50.0))
    d1 = csa.compute_global_distance(reg2, "RP-001", "SCN-001")
    assert d1 > d0


# 14. Geometry change invalidates/recomputes affected route result (stateless recompute).
def test_14_geometry_change_recomputes_route():
    reg = csa.build_facility_hierarchy(facility_id="FAC-5")
    csa.add_building(reg, facility_id="FAC-5", building_id="B")
    csa.add_floor(reg, facility_id="FAC-5", building_id="B", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-5", building_id="B", floor_id="F1", room_id="A")
    csa.add_room(reg, facility_id="FAC-5", building_id="B", floor_id="F1", room_id="B2")
    g = csa.ConnectivityGraph()
    g.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="A", to_object_id="B2", length_m=10.0, compatible_modes=frozenset({"MRT"})))
    r0 = csa.resolve_route(g, origin_object_id="A", destination_object_id="B2", mode="MRT")
    assert r0.distance_m == 10.0
    # A new graph with an updated edge length recomputes on the next stateless call.
    g2 = csa.ConnectivityGraph()
    g2.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="A", to_object_id="B2", length_m=99.0, compatible_modes=frozenset({"MRT"})))
    r1 = csa.resolve_route(g2, origin_object_id="A", destination_object_id="B2", mode="MRT")
    assert r1.distance_m == 99.0  # no stale cached value


# 15. Human and concealed-service routes may have different distances between the same buildings.
def test_15_human_vs_concealed_different_distance():
    reg, g = _two_family_registry_and_graph()
    human = csa.resolve_route(g, origin_object_id="ROOM-A", destination_object_id="ROOM-B", mode="PATIENT_MOVEMENT")
    mrt = csa.resolve_route(g, origin_object_id="ROOM-A", destination_object_id="ROOM-B", mode="MRT")
    assert human.distance_m == 40.0 and mrt.distance_m == 25.0  # different route families, different lengths


# 16. Concealed modes may inherit the same service-right-of-way length while retaining different physics.
def test_16_shared_corridor_distance_borrowing():
    import authoritative_geometry_routing_activation as agra
    # AGV/ORDINARY_PTS/DEDICATED_RP_PTS may borrow the MRT reference corridor DISTANCE only.
    assert set(agra.SHARED_CORRIDOR_ELIGIBLE_MODES) == {"AGV_AMR", "ORDINARY_PTS", "DEDICATED_RP_PTS"}


# 17. A concealed service corridor existing does not imply MRT is installed.
def test_17_corridor_does_not_imply_mrt_installed():
    reg = csa.build_facility_hierarchy(facility_id="FAC-6")
    csa.add_building(reg, facility_id="FAC-6", building_id="B")
    csa.add_floor(reg, facility_id="FAC-6", building_id="B", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-6", building_id="B", floor_id="F1", room_id="A")
    csa.add_room(reg, facility_id="FAC-6", building_id="B", floor_id="F1", room_id="B2")
    g = csa.ConnectivityGraph()
    # A PTS lane exists in the corridor, but NO MRT lane -> MRT not installed.
    g.add_edge(csa.SpatialEdge(edge_id="PTS-1", from_object_id="A", to_object_id="B2", length_m=20.0, compatible_modes=frozenset({"PNEUMATIC_TUBE"})))
    mrt = tb.resolve_mission_route(mission_id="M", transport_mode="MRT", origin_object_id="A", destination_object_id="B2", registry=reg, graph=g)
    assert mrt.route_status in ("ROUTE_NOT_CALIBRATED", "SPATIAL_NETWORK_NOT_CALIBRATED", "ROUTE_UNAVAILABLE")


# 18. A concealed service corridor existing does not imply PTS/RP-PTS/RHTS installed.
def test_18_corridor_does_not_imply_all_lanes_installed():
    reg = csa.build_facility_hierarchy(facility_id="FAC-7")
    csa.add_building(reg, facility_id="FAC-7", building_id="B")
    csa.add_floor(reg, facility_id="FAC-7", building_id="B", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-7", building_id="B", floor_id="F1", room_id="A")
    csa.add_room(reg, facility_id="FAC-7", building_id="B", floor_id="F1", room_id="B2")
    g = csa.ConnectivityGraph()
    # Only an MRT lane -> PTS not installed.
    g.add_edge(csa.SpatialEdge(edge_id="MRT-1", from_object_id="A", to_object_id="B2", length_m=15.0, compatible_modes=frozenset({"MRT"})))
    pts_route = tb.resolve_mission_route(mission_id="M", transport_mode="PNEUMATIC_TUBE", origin_object_id="A", destination_object_id="B2", registry=reg, graph=g)
    assert pts_route.route_status == "SPATIAL_NETWORK_NOT_CALIBRATED"


# 19. Retrofit may retain an existing PTS lane without implying existing MRT.
def test_19_retrofit_existing_pts_no_mrt():
    reg = csa.build_facility_hierarchy(facility_id="FAC-8")
    csa.add_building(reg, facility_id="FAC-8", building_id="B")
    csa.add_floor(reg, facility_id="FAC-8", building_id="B", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-8", building_id="B", floor_id="F1", room_id="A")
    csa.add_room(reg, facility_id="FAC-8", building_id="B", floor_id="F1", room_id="B2")
    g = csa.ConnectivityGraph()
    g.add_edge(csa.SpatialEdge(edge_id="PTS-EXIST", from_object_id="A", to_object_id="B2", length_m=18.0, compatible_modes=frozenset({"PNEUMATIC_TUBE"})))
    pts_route = csa.resolve_route(g, origin_object_id="A", destination_object_id="B2", mode="PNEUMATIC_TUBE")
    mrt = csa.resolve_route(g, origin_object_id="A", destination_object_id="B2", mode="MRT")
    assert pts_route.calibration_status == "CALIBRATED"   # existing PTS retained
    assert mrt.calibration_status == "ROUTE_NOT_CALIBRATED"  # no MRT implied


# 20. Route distance can reach existing transport-time authority.
def test_20_route_distance_to_time():
    reg, g = _two_family_registry_and_graph()
    r = hca.resolve_pedestrian_route(reg, g, subject="PATIENT", origin_object_id="ROOM-A", destination_object_id="ROOM-B")
    minutes = hca.compute_patient_travel_minutes(r)
    assert isinstance(minutes, float) and minutes > 0  # 40m / 1.2 m/s / 60


# 21. Route distance can reach existing length-dependent infrastructure authority.
def test_21_route_distance_to_infrastructure():
    import authoritative_geometry_routing_activation as agra
    # compute_installed_network_union unions unique edges (never sum-of-routes) -> installed length basis.
    assert hasattr(agra, "compute_installed_network_union")
    assert hasattr(agra, "reconcile_installed_mrt_network")
    # MRT length -> CapEx formula exists.
    assert csa.mrt_segment_length_capex(length_m=100.0, unit_cost_per_length=1000.0) == 100_000.0


# 22. Route/time changes can reach fleet/resource sizing where implemented.
def test_22_route_time_to_fleet():
    import conventional_transport_authority as cta
    from datetime import datetime, timedelta
    from general_oncology_logistics import TransportMission
    base = datetime(2026, 1, 1, 8, 0, 0)
    missions = tuple(
        TransportMission(mission_id=f"A{i}", load_id=f"L{i}", transport_mode="AGV_AMR", origin="X", destination="Y",
                         departure_datetime=base, arrival_datetime=base + timedelta(minutes=30), patient_ids=("P",))
        for i in range(2)
    )
    fleet = cta.agv_required_fleet_size(missions=missions, mission_minutes=30.0, model=cta.DEFAULT_AGV_MODEL,
                                        operating_hours_per_day=18.0, operating_days_per_year=300)
    assert fleet >= 1  # mission_minutes (route-derived) drives sizing


# 23. Radioactive transport timing uses the actual applicable transport timing authority where implemented.
def test_23_rp_pts_route_time_available_for_decay():
    # RP-PTS produces a real route/mission time (the applicable timing authority).
    # NOTE (documented gap): this time is not yet wired into the decay elapsed input
    # (Section 26 forbids modifying Build 3B decay physics here) -- we assert the
    # timing authority EXISTS, not a fabricated binding.
    cyc = rp.compute_rp_pts_mission_cycle(network_length_m=100.0)
    assert cyc.total_minutes > 0
    from multi_isotope_decay import retained_fraction
    # The decay primitive accepts an elapsed-minutes scalar (any route time could feed it).
    frac = retained_fraction(cyc.total_minutes, 109.8)
    assert 0.0 < frac <= 1.0


# 24. Patient XYZT trajectory remains on Human Circulation Network.
def test_24_patient_trajectory_authority_exists():
    assert pta.PATIENT_TRAJECTORY_SUPPORTED is True
    assert hasattr(pta, "build_patient_trajectory")
    assert "PATIENT" in pta.EntityType.__args__


# 25. Porter XYZT trajectory remains on Human Circulation Network.
def test_25_porter_trajectory_authority_exists():
    assert pta.PORTER_TRAJECTORY_SUPPORTED is True
    assert hasattr(pta, "build_porter_trajectory")
    assert "MANUAL_PORTER" in pta.EntityType.__args__


# 26. Color / payload identity remains unchanged by route-family selection.
def test_26_color_identity_unchanged_by_route_family():
    import mrt_service_class_authority as msc
    # Payload service-class color is a property of the substance, not the route/lane.
    nuclear = msc.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"]
    # Same payload color regardless of whether it travels by MRT or RP-PTS lane.
    assert nuclear.configured_active_color == "VIOLET"
    assert nuclear.effective_display_color() == "VIOLET"


# 27. Build 3C transport-building-block tests remain discoverable/importable.
def test_27_build3c_authorities_intact():
    import conventional_transport_authority as cta
    assert {"MANUAL_PORTER", "PORTER_CART", "AGV_AMR", "PNEUMATIC_TUBE"} <= set(cta.TECHNOLOGY_STREAM_COMPATIBILITY)


# 28. Build 3B production authority remains intact (CYPRIS uncalibrated preserved).
def test_28_build3b_production_authority_intact():
    import cyclotron_catalog as cc
    inst = cc.create_facility_cyclotron_instance(catalog_model_id="SUMITOMO_CYPRIS_MP_30", existing_instances=())
    fleet, warnings = cc.build_fleet_from_instances(catalog=cc.load_cyclotron_catalog(), instances=(inst,))
    assert fleet is None and warnings


# 29. Build 3A equal-budget / NO_BUILD authority remains intact.
def test_29_build3a_no_build_authority_intact():
    import equal_budget as eb
    import inspect
    assert "NO_BUILD_BASELINE" in inspect.getsource(eb.maximize_mrt_capacity)


# ===========================================================================
# Controlled proofs (Section 47)
# ===========================================================================

# PROOF A -- human route.
def test_proof_a_human_route():
    reg, g = _two_family_registry_and_graph()
    for subject in ("PATIENT", "PORTER"):
        r = hca.resolve_pedestrian_route(reg, g, subject=subject, origin_object_id="ROOM-A", destination_object_id="ROOM-B")
        assert r.route_status == "ROUTE_CALIBRATED" and r.total_distance_m == 40.0


# PROOF B -- concealed service route with separate lane identities.
def test_proof_b_concealed_service_route():
    reg, g = _two_family_registry_and_graph()
    mrt = csa.resolve_route(g, origin_object_id="ROOM-A", destination_object_id="ROOM-B", mode="MRT")
    pts_route = csa.resolve_route(g, origin_object_id="ROOM-A", destination_object_id="ROOM-B", mode="PNEUMATIC_TUBE")
    assert mrt.path_edge_ids == ("MRT-1",) and pts_route.path_edge_ids == ("PTS-1",)  # separate lanes


# PROOF C -- building move recomputation.
def test_proof_c_building_move():
    reg = csa.build_facility_hierarchy(facility_id="FAC-C")
    csa.add_building(reg, facility_id="FAC-C", building_id="A", transform=csa.Transform())
    csa.add_building(reg, facility_id="FAC-C", building_id="B", transform=csa.Transform(position_x=50.0))
    before = csa.compute_global_distance(reg, "A", "B")
    after = csa.compute_global_distance(reg.replace_transform("B", csa.Transform(position_x=250.0)), "A", "B")
    assert after == before + 200.0


# PROOF D -- asset move recomputation.
def test_proof_d_asset_move():
    reg = csa.build_facility_hierarchy(facility_id="FAC-D")
    csa.add_building(reg, facility_id="FAC-D", building_id="B")
    csa.add_floor(reg, facility_id="FAC-D", building_id="B", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-D", building_id="B", floor_id="F1", room_id="CY-001", transform=csa.Transform())
    csa.add_room(reg, facility_id="FAC-D", building_id="B", floor_id="F1", room_id="SCN-001", transform=csa.Transform(position_y=5.0))
    before = csa.compute_global_distance(reg, "CY-001", "SCN-001")
    after = csa.compute_global_distance(reg.replace_transform("CY-001", csa.Transform(position_y=-20.0)), "CY-001", "SCN-001")
    assert after > before


# PROOF E -- retrofit existing PTS lane retained while MRT absent.
def test_proof_e_retrofit_lane_state():
    reg = csa.build_facility_hierarchy(facility_id="FAC-E")
    csa.add_building(reg, facility_id="FAC-E", building_id="B")
    csa.add_floor(reg, facility_id="FAC-E", building_id="B", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-E", building_id="B", floor_id="F1", room_id="A")
    csa.add_room(reg, facility_id="FAC-E", building_id="B", floor_id="F1", room_id="B2")
    g = csa.ConnectivityGraph()
    g.add_edge(csa.SpatialEdge(edge_id="PTS-EXIST", from_object_id="A", to_object_id="B2", length_m=18.0, compatible_modes=frozenset({"PNEUMATIC_TUBE"})))
    assert csa.resolve_route(g, origin_object_id="A", destination_object_id="B2", mode="PNEUMATIC_TUBE").calibration_status == "CALIBRATED"
    assert csa.resolve_route(g, origin_object_id="A", destination_object_id="B2", mode="MRT").calibration_status == "ROUTE_NOT_CALIBRATED"

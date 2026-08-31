"""Interactive route-authoring + payload endpoint tests (ADDITIVE to the
current Bentley 3D spatial-network build). Covers Sec X.1-20 controls + the
payload-stream origin/destination authority.
"""
from __future__ import annotations

import pytest

import canonical_spatial_authority as csa
import interactive_route_authoring_authority as ira
import payload_endpoint_authority as pe


# --- graph fixtures --------------------------------------------------------

def _mrt_line():
    """O-M1-M2-D guideway (50m each) + a direct O-D short guideway (60m)."""
    g = csa.ConnectivityGraph(edges=[])
    for a, b, l in [("O", "M1", 50.0), ("M1", "M2", 50.0), ("M2", "D", 50.0)]:
        g.add_edge(csa.SpatialEdge(edge_id=f"MRT-{a}-{b}", from_object_id=a, to_object_id=b, length_m=l, compatible_modes=frozenset({"MRT"})))
    g.add_edge(csa.SpatialEdge(edge_id="MRT-O-D", from_object_id="O", to_object_id="D", length_m=60.0, compatible_modes=frozenset({"MRT"})))
    return g


def _pts_stations():
    g = csa.ConnectivityGraph(edges=[])
    for a, b, l in [("S1", "S2", 40.0), ("S2", "S3", 40.0)]:
        g.add_edge(csa.SpatialEdge(edge_id=f"PTS-{a}-{b}", from_object_id=a, to_object_id=b, length_m=l, compatible_modes=frozenset({"PNEUMATIC_TUBE"})))
    return g


def _rths_line():
    g = csa.ConnectivityGraph(edges=[])
    for a, b, l in [("T0", "T1", 70.0), ("T1", "T2", 70.0)]:
        g.add_edge(csa.SpatialEdge(edge_id=f"RTHS-{a}-{b}", from_object_id=a, to_object_id=b, length_m=l, compatible_modes=frozenset({"AGV_AMR"})))
    return g


def _agv_navigable():
    """O-C-D navigable corridor (via C); no edge through 'WALL'."""
    g = csa.ConnectivityGraph(edges=[])
    g.add_edge(csa.SpatialEdge(edge_id="AGV-O-C", from_object_id="O", to_object_id="C", length_m=60.0, compatible_modes=frozenset({"AGV_AMR"})))
    g.add_edge(csa.SpatialEdge(edge_id="AGV-C-D", from_object_id="C", to_object_id="D", length_m=60.0, compatible_modes=frozenset({"AGV_AMR"})))
    g.add_edge(csa.SpatialEdge(edge_id="AGV-O-D", from_object_id="O", to_object_id="D", length_m=100.0, compatible_modes=frozenset({"AGV_AMR"})))
    return g


def _manual_corridor():
    g = csa.ConnectivityGraph(edges=[])
    g.add_edge(csa.SpatialEdge(edge_id="COR-O-C", from_object_id="O", to_object_id="C", length_m=55.0, compatible_modes=frozenset({"WALKING_PORTER"})))
    g.add_edge(csa.SpatialEdge(edge_id="COR-C-D", from_object_id="C", to_object_id="D", length_m=55.0, compatible_modes=frozenset({"WALKING_PORTER"})))
    g.add_edge(csa.SpatialEdge(edge_id="COR-O-D", from_object_id="O", to_object_id="D", length_m=100.0, compatible_modes=frozenset({"WALKING_PORTER"})))
    return g


def _route(mode, route_id="R", origin="O", dest="D", controls=()):
    return ira.InteractiveRoute(
        route_id=route_id, mode=mode,
        origin=ira.RouteEndpoint(origin, "ORIGIN"), destination=ira.RouteEndpoint(dest, "DESTINATION"),
        control_points=tuple(controls),
    )


# --- Sec X.1 MRT pin + auto-route -----------------------------------------

def test_x1_mrt_pin_endpoints_auto_route():
    res = ira.auto_route(_route("MRT"), graph=_mrt_line())
    assert res.status == "ROUTED"
    assert res.endpoints_pinned
    assert res.total_route_length_m == 60.0  # shortest legal guideway (direct)


# --- Sec X.2 insert waypoint changes length; endpoints pinned -------------

def test_x2_mrt_waypoint_changes_length_endpoints_pinned():
    base = _route("MRT")
    routed = ira.insert_waypoint(base, control=ira.RouteControlPoint("C1", "M2"), index=0)
    res = ira.auto_route(routed, graph=_mrt_line())
    # forcing via M2: O->M2 (shortest legal) + M2->D(50) -> longer than direct 60
    assert res.status == "ROUTED"
    assert res.total_route_length_m != 60.0
    assert ira.endpoints_unchanged(base, routed)


# --- Sec X.3 delete required segment -> disconnected ----------------------

def test_x3_delete_segment_disconnects_destination():
    g = _mrt_line()
    g2 = ira.delete_segment(g, edge_id="MRT-O-D")
    g3 = ira.delete_segment(g2, edge_id="MRT-M2-D")
    res = ira.auto_route(_route("MRT"), graph=g3)
    assert res.status == "NO_CONNECTED_PATH"  # never auto-bridged


# --- Sec X.4 PTS station-to-station ---------------------------------------

def test_x4_pts_station_to_station_auto_route():
    res = ira.auto_route(_route("PTS_CONVENTIONAL", origin="S1", dest="S3"), graph=_pts_stations())
    assert res.status == "ROUTED"
    assert res.total_route_length_m == 80.0


# --- Sec X.5 PTS bend move; physical bend authority retained --------------

def test_x5_pts_bend_move_keeps_physical_bend_authority():
    base = _route("PTS_CONVENTIONAL", origin="S1", dest="S3", controls=(ira.RouteControlPoint("B1", "S2", "BEND"),))
    moved = ira.move_waypoint(base, control_id="B1", new_node_id="S2")
    res = ira.auto_route(moved, graph=_pts_stations())
    assert res.status == "ROUTED"
    assert "pts_spatial_network_authority" in res.physical_bend_authority_owner
    assert not ira.graphical_vertex_overrides_physical_bend()


# --- Sec X.6 RTHS intermediate control recomputes -------------------------

def test_x6_rths_control_recomputes_track_route():
    res = ira.auto_route(_route("RTHS", origin="T0", dest="T2", controls=(ira.RouteControlPoint("C1", "T1"),)), graph=_rths_line())
    assert res.status == "ROUTED"
    assert res.total_route_length_m == 140.0


# --- Sec X.7 AGV corridor waypoint changes route --------------------------

def test_x7_agv_corridor_waypoint_changes_route():
    base = _route("AGV_AMR_LIGHT_CLINICAL")
    direct = ira.auto_route(base, graph=_agv_navigable())
    via_c = ira.auto_route(ira.insert_waypoint(base, control=ira.RouteControlPoint("W1", "C", "PREFERRED_CORRIDOR"), index=0), graph=_agv_navigable())
    assert direct.total_route_length_m == 100.0
    assert via_c.total_route_length_m == 120.0  # forced via C


# --- Sec X.8 AGV waypoint in wall/non-navigable rejected ------------------

def test_x8_agv_wall_waypoint_rejected():
    r = _route("AGV_AMR_LIGHT_CLINICAL", controls=(ira.RouteControlPoint("W1", "WALL"),))
    res = ira.auto_route(r, graph=_agv_navigable())
    assert res.status == "NO_CONNECTED_PATH"  # WALL not on navigable graph


# --- Sec X.9 Manual preferred corridor waypoint changes route -------------

def test_x9_manual_corridor_waypoint_changes_route():
    base = _route("MANUAL")
    direct = ira.auto_route(base, graph=_manual_corridor())
    via_c = ira.auto_route(ira.insert_waypoint(base, control=ira.RouteControlPoint("W1", "C"), index=0), graph=_manual_corridor())
    assert direct.total_route_length_m == 100.0
    assert via_c.total_route_length_m == 110.0


# --- Sec X.10 Manual impossible wall-crossing rejected --------------------

def test_x10_manual_wall_crossing_rejected():
    r = _route("MANUAL", controls=(ira.RouteControlPoint("W1", "WALL"),))
    res = ira.auto_route(r, graph=_manual_corridor())
    assert res.status == "NO_CONNECTED_PATH"


# --- Sec X.11 restore automatic route -------------------------------------

def test_x11_restore_auto_route():
    edited = _route("MRT", controls=(ira.RouteControlPoint("C1", "M1"), ira.RouteControlPoint("C2", "M2")))
    restored = ira.restore_auto_route(edited)
    assert restored.control_points == ()
    assert restored.network_state == "AUTO_GENERATED_SCENARIO_NETWORK"
    res = ira.auto_route(restored, graph=_mrt_line())
    assert res.total_route_length_m == 60.0  # back to optimized direct


# --- Sec X.12 endpoint pinned while intermediate control moves ------------

def test_x12_endpoint_pinned_while_control_moves():
    base = _route("MRT", controls=(ira.RouteControlPoint("C1", "M1"),))
    moved = ira.move_waypoint(base, control_id="C1", new_node_id="M2")
    assert ira.endpoints_unchanged(base, moved)
    assert base.origin.endpoint_id == moved.origin.endpoint_id == "O"
    assert base.destination.endpoint_id == moved.destination.endpoint_id == "D"


def test_pinned_endpoint_moves_with_waypoint_is_no():
    base = _route("MRT", controls=(ira.RouteControlPoint("C1", "M1"),))
    moved = ira.move_waypoint(base, control_id="C1", new_node_id="M2")
    # PINNED_ENDPOINT_MOVES_WITH_INTERMEDIATE_WAYPOINT = NO
    assert moved.origin.endpoint_id == "O" and moved.origin.locked
    assert moved.destination.endpoint_id == "D" and moved.destination.locked


# --- Sec X.13 route edit recomputes CapEx/OPEX inputs ---------------------

def test_x13_route_edit_triggers_full_recompute_including_capex_opex():
    res = ira.auto_route(_route("MRT"), graph=_mrt_line())
    req = ira.build_recompute_request(res, trigger="COMMITTED_ROUTE_EDIT")
    assert req.is_full_recompute
    for target in ("incremental_capex", "target_opex", "incremental_opex"):
        assert target in req.recompute_targets


# --- Sec X.14 nuclear route edit recomputes time + decay ------------------

def test_x14_nuclear_route_edit_recomputes_time_and_decay():
    res = ira.auto_route(_route("PTS_NUCLEAR_QUALIFIED", origin="S1", dest="S3"), graph=_pts_stations())
    req = ira.build_recompute_request(res, trigger="COMMITTED_ROUTE_EDIT")
    assert "travel_time" in req.recompute_targets
    assert "radionuclide_decay" in req.recompute_targets
    assert "required_upstream_activity" in req.recompute_targets


# --- Sec X.15 route change can alter fleet/carrier/FTE --------------------

def test_x15_route_change_can_alter_fleet_threshold():
    res = ira.auto_route(_route("MRT"), graph=_mrt_line())
    req = ira.build_recompute_request(res, trigger="COMMITTED_ROUTE_EDIT")
    assert "fleet_or_fte" in req.recompute_targets
    assert "carrier_vehicle_porter_cycle" in req.recompute_targets


# --- drag preview vs committed (Sec U) ------------------------------------

def test_drag_preview_is_lightweight_commit_is_full():
    res = ira.auto_route(_route("MRT"), graph=_mrt_line())
    preview = ira.build_recompute_request(res, trigger="DRAG_PREVIEW")
    commit = ira.build_recompute_request(res, trigger="COMMITTED_ROUTE_EDIT")
    assert not preview.is_full_recompute and set(preview.recompute_targets) == {"route_length", "travel_time"}
    assert commit.is_full_recompute and len(commit.recompute_targets) > len(preview.recompute_targets)


# --- Sec W whatif edit does not mutate bentley ----------------------------

def test_whatif_route_edit_does_not_mutate_bentley():
    assert ira.WHATIF_ROUTE_EDIT_MUTATES_LIVE_BENTLEY is False
    res = ira.auto_route(_route("MRT"), graph=_mrt_line())
    req = ira.build_recompute_request(res, trigger="COMMITTED_ROUTE_EDIT")
    assert req.mutates_live_bentley is False


def test_route_default_state_is_user_edited_whatif():
    assert _route("MRT").network_state == "USER_EDITED_WHATIF_NETWORK"


# --- Sec V edit history ----------------------------------------------------

def test_edit_history_undo_redo_reproducible():
    r0 = _route("MRT")
    r1 = ira.insert_waypoint(r0, control=ira.RouteControlPoint("C1", "M1"), index=0)
    h = ira.RouteEditHistory(states=(r0,)).push(r1)
    assert h.current() == r1
    assert h.undo().current() == r0
    assert h.undo().redo().current() == r1


# --- Sec I add segment -----------------------------------------------------

def test_add_segment_enables_previously_disconnected_route():
    g = csa.ConnectivityGraph(edges=[csa.SpatialEdge(edge_id="MRT-O-M1", from_object_id="O", to_object_id="M1", length_m=50.0, compatible_modes=frozenset({"MRT"}))])
    disconnected = ira.auto_route(_route("MRT", dest="D"), graph=g)
    assert disconnected.status == "NO_CONNECTED_PATH"
    g2 = ira.add_segment(g, csa.SpatialEdge(edge_id="MRT-M1-D", from_object_id="M1", to_object_id="D", length_m=50.0, compatible_modes=frozenset({"MRT"})))
    connected = ira.auto_route(_route("MRT", dest="D"), graph=g2)
    assert connected.status == "ROUTED" and connected.total_route_length_m == 100.0


# ===========================================================================
# PAYLOAD ENDPOINT AUTHORITY (Sec M-S)
# ===========================================================================

def test_six_canonical_payload_streams():
    assert pe.CANONICAL_PAYLOAD_STREAMS == (
        "RADIOPHARMACEUTICAL", "CONVENTIONAL_MEDICATION", "CLEAN_LINEN",
        "STERILE_SUPPLY", "SPECIMEN", "LAB_SUPPLY",
    )


# --- Sec X.17 / N radiopharm release origin != cyclotron production -------

def test_x17_radiopharm_release_origin_differs_from_cyclotron():
    assert pe.radiopharmaceutical_transport_origin() == "RADIOPHARMACY_RELEASE"
    assert pe.radiopharmaceutical_production_origin() == "CYCLOTRON_GENERATOR_PRODUCTION"
    assert not pe.production_origin_equals_transport_origin()


def test_radiopharm_transport_origin_default_is_release():
    ep = pe.default_endpoints("RADIOPHARMACEUTICAL", "OUTBOUND")
    assert ep.origin_role == "RADIOPHARMACY_RELEASE"
    assert ep.origin_role != "CYCLOTRON_GENERATOR_PRODUCTION"


def test_radiopharm_origin_chain_keeps_production_and_transport_separate():
    chain = pe.RADIOPHARM_ORIGIN_CHAIN
    assert chain.index("CYCLOTRON_GENERATOR_PRODUCTION") < chain.index("RADIOPHARMACY_RELEASE")


# --- Sec X.18 / Q specimen patient -> lab ---------------------------------

def test_x18_specimen_patient_to_lab_direction():
    ep = pe.default_endpoints("SPECIMEN", "OUTBOUND")
    assert ep.origin_role == "COLLECTION_POINT"
    assert ep.destination_role == "LABORATORY"


def test_specimen_origin_not_always_lab():
    # lab-originating supply travels the OTHER direction
    lab_supply = pe.default_endpoints("LAB_SUPPLY", "OUTBOUND")
    assert lab_supply.origin_role == "LABORATORY"
    assert lab_supply.destination_role != "LABORATORY"


# --- Sec X.19 / P linen laundry -> room -----------------------------------

def test_x19_linen_laundry_to_room_direction():
    ep = pe.default_endpoints("CLEAN_LINEN", "OUTBOUND")
    assert ep.origin_role == "LAUNDRY_LINEN_SERVICE"
    assert ep.destination_role == "PATIENT_CLINICAL_ROOM"


def test_linen_return_room_to_laundry():
    ep = pe.default_endpoints("CLEAN_LINEN", "RETURN")
    assert ep.origin_role == "PATIENT_CLINICAL_ROOM"
    assert ep.destination_role == "LAUNDRY_LINEN_SERVICE"


# --- Sec X.20 / P sterile CSSD -> clinical --------------------------------

def test_x20_sterile_cssd_to_clinical_direction():
    ep = pe.default_endpoints("STERILE_SUPPLY", "OUTBOUND")
    assert ep.origin_role == "CSSD_STERILE_PROCESSING"
    assert ep.destination_role == "PATIENT_CLINICAL_ROOM"


def test_sterile_origin_not_always_laundry():
    assert pe.default_endpoints("STERILE_SUPPLY", "OUTBOUND").origin_role != "LAUNDRY_LINEN_SERVICE"


def test_conventional_medication_from_pharmacy_not_radiopharmacy():
    ep = pe.default_endpoints("CONVENTIONAL_MEDICATION", "OUTBOUND")
    assert ep.origin_role == "CENTRAL_PHARMACY"
    assert ep.origin_role != "RADIOPHARMACY_RELEASE"


def test_destination_not_universally_patient_room():
    # specimen destination is lab, not patient room
    assert pe.default_endpoints("SPECIMEN").destination_role == "LABORATORY"
    assert pe.default_endpoints("CLEAN_LINEN", "RETURN").destination_role == "LAUNDRY_LINEN_SERVICE"


# --- Sec X.16 / S endpoint validation -------------------------------------

def test_x16_endpoint_validation_radiopharm_on_conventional_pts_invalid():
    v = pe.validate_endpoints(stream="RADIOPHARMACEUTICAL", mode="PTS_CONVENTIONAL",
                              origin_node_id="RP", destination_node_id="ROOM",
                              origin_has_mode_interface=True, destination_has_mode_interface=True)
    assert v.status == "INVALID_STREAM_MODE"
    assert not v.valid


def test_endpoint_validation_mrt_to_room_without_endpoint_invalid():
    v = pe.validate_endpoints(stream="RADIOPHARMACEUTICAL", mode="MRT",
                              origin_node_id="RP", destination_node_id="ROOM",
                              origin_has_mode_interface=True, destination_has_mode_interface=False,
                              nuclear_qualification_present=True)
    assert v.status == "INVALID_NO_ENDPOINT_INTERFACE"


def test_endpoint_validation_rths_unconnected_station_invalid():
    v = pe.validate_endpoints(stream="STERILE_SUPPLY", mode="RTHS",
                              origin_node_id="T0", destination_node_id="T9",
                              origin_has_mode_interface=True, destination_has_mode_interface=True,
                              destination_reachable_on_network=False)
    assert v.status == "INVALID_UNCONNECTED_STATION"


def test_endpoint_validation_nuclear_qualification_missing_invalid():
    v = pe.validate_endpoints(stream="RADIOPHARMACEUTICAL", mode="PTS_NUCLEAR_QUALIFIED",
                              origin_node_id="RP", destination_node_id="ROOM",
                              origin_has_mode_interface=True, destination_has_mode_interface=True,
                              nuclear_qualification_present=False)
    assert v.status == "INVALID_QUALIFICATION_MISSING"


def test_endpoint_validation_valid_pair():
    v = pe.validate_endpoints(stream="SPECIMEN", mode="MANUAL",
                              origin_node_id="ROOM", destination_node_id="LAB",
                              origin_has_mode_interface=True, destination_has_mode_interface=True)
    assert v.valid

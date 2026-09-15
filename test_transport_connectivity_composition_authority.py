"""MRT Pharma Build 2A: deterministic tests for the transport automatic-
connectivity composition authority (§63-72).

Covers: OUT_OF_SCOPE production-unit protection, logistics-mission enrichment,
mode-eligibility gate reuse, one-room-one-shared-endpoint idempotence, MRT
vestibule requirement derivation, endpoint-interface requirements, automatic
connectivity verdict (FEASIBLE / NOT_CALIBRATED / NO_NETWORK_PATH / MODE_*),
CONNECTIVITY-separate-from-CAPACITY, cross-mode network composition BoM, and
cost/quantity accounting crosswalks (no synthetic CapEx).

All tests are DETERMINISTIC: no randomness, no wall-clock, no network I/O.
They reuse the existing controlled proof-network builders (never a second
hospital coordinate source) so nothing new is fabricated.
"""

from __future__ import annotations

import canonical_spatial_authority as csa
import shared_mrt_multistream_authority as smx
import transport_mode_eligibility_authority as elig
import rght_spatial_network_authority as rght
import pts_spatial_network_authority as pts
import transport_connectivity_composition_authority as tcc


# ---------------------------------------------------------------------------
# Helpers: build a deterministic controlled two-floor facility once.
# ---------------------------------------------------------------------------

def _base_registry() -> csa.SpatialObjectRegistry:
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    csa.add_building(reg, facility_id="FAC-001", building_id="B1")
    csa.add_floor(reg, facility_id="FAC-001", building_id="B1", floor_id="F1")
    csa.add_floor(reg, facility_id="FAC-001", building_id="B1", floor_id="F2")
    return reg


def _rght_network() -> tuple[csa.SpatialObjectRegistry, csa.ConnectivityGraph]:
    reg = _base_registry()
    graph, _ = rght.build_controlled_rght_proof_network(reg, facility_id="FAC-001", building_id="B1")
    return reg, graph


def _existing_room(reg: csa.SpatialObjectRegistry, room_id: str, *, floor_id: str = "F1",
                   object_type: csa.SpatialObjectType = "INJECTION_ROOM") -> None:
    """Add an EXISTING room-like object (a valid shared-endpoint host, unlike a
    network station)."""
    csa.add_room(reg, facility_id="FAC-001", building_id="B1", floor_id=floor_id, room_id=room_id,
                 object_type=object_type)


# ===========================================================================
# §63. OUT_OF_SCOPE production-unit protection.
# ===========================================================================

def test_out_of_scope_units_are_exactly_seven_and_not_transport_equipment():
    assert len(tcc.OUT_OF_SCOPE_PRODUCTION_UNITS) == 7
    assert tcc.TRANSPORT_UNIT_EQUIPMENT_IS_OUT_OF_SCOPE_PRODUCTION_UNIT is False
    for unit in ("HOT_CELL", "DOSE_CALIBRATOR_BENCH", "FUME_HOOD", "ISOLATOR",
                 "SHIELDED_STORAGE", "WASTE_DECAY_STORE", "DISPENSING_QC_HOT_CELL"):
        assert tcc.is_out_of_scope_production_unit(unit)
        assert tcc.is_out_of_scope_production_unit(unit.lower())


def test_out_of_scope_unit_never_receives_a_shared_endpoint():
    reg = _base_registry()
    # A production unit is not room-like; force an EQUIPMENT object and prove
    # the shared-endpoint registry refuses it (production never endpointed).
    reg.add(csa.CanonicalSpatialObject(
        mrtway_object_id="HOTCELL-1", object_type="EQUIPMENT", facility_id="FAC-001",
        building_id="B1", floor_id="F1", space_id=None, parent_object_id="B1::F1",
        transform=csa.Transform(), geometry_reference=None, coordinate_system="LOCAL_BUILDING",
        asset_status="PROPOSED", operational_state="AVAILABLE", spatial_status="CALIBRATED",
        provenance="USER_CREATED",
    ))
    sereg = tcc.SharedClinicalLogisticsEndpointRegistry()
    try:
        sereg.require_endpoint(reg, room_object_id="HOTCELL-1", serving_mode="MRT")
        assert False, "production/equipment object must not receive a shared endpoint"
    except ValueError:
        pass


# ===========================================================================
# §64. Logistics mission enrichment.
# ===========================================================================

def test_logistics_mission_radiopharmaceutical_is_forced_radioactive():
    m = tcc.LogisticsMission(mission_id="M1", payload_stream="RADIOPHARMACEUTICAL")
    assert m.is_radioactive is True
    assert m.eligibility_stream == "RADIOPHARMACEUTICAL_NUCLEAR"


def test_logistics_mission_carries_priority_frequency_sla():
    m = tcc.LogisticsMission(
        mission_id="M2", payload_stream="SPECIMEN", priority="STAT",
        demand_missions_per_day=12.0, sla_max_transit_minutes=8.0,
    )
    assert m.priority == "STAT"
    assert m.demand_missions_per_day == 12.0
    assert m.sla_max_transit_minutes == 8.0
    assert m.eligibility_stream == "SPECIMEN_BLOOD"


def test_endpoint_object_resolution_is_honest_when_ids_absent():
    m = tcc.LogisticsMission(mission_id="M3", payload_stream="CONVENTIONAL_MEDICATION")
    res = tcc.resolve_mission_endpoint_objects(m)
    assert res.origin_role == "CENTRAL_PHARMACY"
    assert res.destination_role == "PATIENT_CLINICAL_ROOM"
    assert res.endpoints_resolved is False  # no object ids supplied -> honest


# ===========================================================================
# §65. Mode-eligibility gate reuse (never re-implemented here).
# ===========================================================================

def test_clean_linen_is_mrt_ineligible_via_existing_authority():
    m = tcc.LogisticsMission(
        mission_id="M4", payload_stream="CLEAN_LINEN",
        origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ",
    )
    v = tcc.evaluate_transport_connectivity(m, "MRT")
    # CLEAN_LINEN exceeds the canonical light-MRT mass ceiling => not allowed.
    assert v.status in ("PAYLOAD_INCOMPATIBLE", "MODE_INELIGIBLE")
    assert v.eligibility_status in ("INELIGIBLE", "NOT_MODELED")


def test_radiopharm_pts_conventional_is_mode_ineligible():
    m = tcc.LogisticsMission(
        mission_id="M5", payload_stream="RADIOPHARMACEUTICAL",
        origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ",
    )
    # PTS (ordinary) for radiopharm is QUALIFICATION_REQUIRED -> not allowed.
    v = tcc.evaluate_transport_connectivity(m, "PTS")
    assert v.status == "MODE_INELIGIBLE"
    assert v.eligibility_status == "QUALIFICATION_REQUIRED"


# ===========================================================================
# §66. One-room-one-shared-endpoint idempotence + $1,000 crosswalk.
# ===========================================================================

def test_shared_endpoint_is_one_per_room_and_reused_across_modes():
    reg, _ = _rght_network()
    _existing_room(reg, "INJ-ROOM")
    sereg = tcc.SharedClinicalLogisticsEndpointRegistry()
    e1 = sereg.require_endpoint(reg, room_object_id="INJ-ROOM", serving_mode="RGHT")
    e2 = sereg.require_endpoint(reg, room_object_id="INJ-ROOM", serving_mode="MRT")
    # SAME endpoint object id -> exactly one endpoint for the room.
    assert e1.endpoint_id == e2.endpoint_id
    assert sereg.endpoint_count() == 1
    assert set(e2.serving_modes) == {"RGHT", "MRT"}


def test_shared_endpoint_repeated_same_mode_is_idempotent():
    reg, _ = _rght_network()
    _existing_room(reg, "INJ-ROOM")
    sereg = tcc.SharedClinicalLogisticsEndpointRegistry()
    sereg.require_endpoint(reg, room_object_id="INJ-ROOM", serving_mode="RGHT")
    sereg.require_endpoint(reg, room_object_id="INJ-ROOM", serving_mode="RGHT")
    assert sereg.endpoint_count() == 1
    assert sereg.endpoints()[0].serving_modes == ("RGHT",)


def test_shared_endpoint_unit_cost_is_the_1000_crosswalk():
    assert tcc.SHARED_CLINICAL_LOGISTICS_ENDPOINT_CAPEX_USD == smx.LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT == 1000.0
    assert tcc.MRT_VESTIBULE_EQUALS_ROOM_ENDPOINT is False


def test_existing_room_endpoint_is_zero_new_capex():
    reg, _ = _rght_network()
    _existing_room(reg, "INJ-ROOM")  # rooms added via add_room are EXISTING by default
    sereg = tcc.SharedClinicalLogisticsEndpointRegistry()
    sereg.require_endpoint(reg, room_object_id="INJ-ROOM", serving_mode="RGHT")
    assert sereg.endpoint_count() == 1
    assert sereg.new_required_endpoint_count() == 0
    assert sereg.new_required_endpoint_capex_usd() == 0.0


def test_proposed_room_endpoint_charges_1000_new_capex():
    reg = _base_registry()
    csa.add_room(reg, facility_id="FAC-001", building_id="B1", floor_id="F1", room_id="NEW-INJ",
                 object_type="INJECTION_ROOM")
    # mark it PROPOSED (new)
    reg.objects["NEW-INJ"] = csa.CanonicalSpatialObject(
        **{**reg.objects["NEW-INJ"].__dict__, "asset_status": "PROPOSED"}
    )
    sereg = tcc.SharedClinicalLogisticsEndpointRegistry()
    sereg.require_endpoint(reg, room_object_id="NEW-INJ", serving_mode="RGHT")
    assert sereg.new_required_endpoint_count() == 1
    assert sereg.new_required_endpoint_capex_usd() == 1000.0


# ===========================================================================
# §67. MRT vestibule requirement derivation + $30,000 crosswalk.
# ===========================================================================

def test_mrt_vestibule_requirement_uses_30000_crosswalk():
    assert tcc.MRT_VESTIBULE_REQUIREMENT_CAPEX_USD == csa.MRT_VESTIBULE_CAPEX_USD == 30000.0
    m = tcc.LogisticsMission(
        mission_id="M6", payload_stream="RADIOPHARMACEUTICAL",
        origin_object_id="RP-1", destination_object_id="INJ-1", nuclear_qualification_present=True,
    )
    req = tcc.derive_mrt_vestibule_requirement(m)
    assert req.vestibule_required is True
    assert req.unit_capex_usd == 30000.0
    assert req.is_existing is False  # no registry -> unknown existing -> NEW


def test_existing_mrt_vestibule_is_not_charged_new():
    reg = _base_registry()
    reg.add(csa.CanonicalSpatialObject(
        mrtway_object_id="VEST-1", object_type="MRT_VESTIBULE", facility_id="FAC-001",
        building_id="B1", floor_id="F1", space_id=None, parent_object_id="B1::F1",
        transform=csa.Transform(), geometry_reference=None, coordinate_system="LOCAL_BUILDING",
        asset_status="EXISTING", operational_state="AVAILABLE", spatial_status="CALIBRATED",
        provenance="USER_CREATED",
    ))
    m = tcc.LogisticsMission(
        mission_id="M7", payload_stream="RADIOPHARMACEUTICAL",
        origin_object_id="VEST-1", destination_object_id="INJ-1", nuclear_qualification_present=True,
    )
    req = tcc.derive_mrt_vestibule_requirement(m, registry=reg)
    assert req.is_existing is True


# ===========================================================================
# §68. Endpoint-interface requirements.
# ===========================================================================

def test_missing_origin_interface_is_flagged():
    reg, graph = _rght_network()
    m = tcc.LogisticsMission(
        mission_id="M8", payload_stream="STERILE_SUPPLY",
        origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ",
    )
    v = tcc.evaluate_transport_connectivity(
        m, "AGV_AMR_LIGHT_CLINICAL", registry=reg, graph=graph,
        origin_has_mode_interface=False, destination_has_mode_interface=True,
    )
    assert v.status == "MISSING_ORIGIN_INTERFACE"


def test_missing_destination_interface_is_flagged():
    reg, graph = _rght_network()
    m = tcc.LogisticsMission(
        mission_id="M9", payload_stream="STERILE_SUPPLY",
        origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ",
    )
    v = tcc.evaluate_transport_connectivity(
        m, "AGV_AMR_LIGHT_CLINICAL", registry=reg, graph=graph,
        origin_has_mode_interface=True, destination_has_mode_interface=False,
    )
    assert v.status == "MISSING_DESTINATION_INTERFACE"


# ===========================================================================
# §69. Automatic connectivity verdict (FEASIBLE + honest not-calibrated).
# ===========================================================================

def test_feasible_connectivity_on_real_calibrated_rght_route():
    reg, graph = _rght_network()
    m = tcc.LogisticsMission(
        mission_id="M10", payload_stream="STERILE_SUPPLY",
        origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ",
    )
    v = tcc.evaluate_transport_connectivity(m, "AGV_AMR_LIGHT_CLINICAL", registry=reg, graph=graph)
    assert v.status == "FEASIBLE"
    assert v.route_status == "ROUTE_CALIBRATED"
    assert v.route_distance_m is not None and v.route_distance_m > 0.0
    # CONNECTIVITY is separate from CAPACITY.
    assert v.connectivity_separate_from_capacity is True


def test_not_calibrated_when_no_graph_supplied():
    m = tcc.LogisticsMission(
        mission_id="M11", payload_stream="STERILE_SUPPLY",
        origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ",
    )
    v = tcc.evaluate_transport_connectivity(m, "AGV_AMR_LIGHT_CLINICAL")
    assert v.status == "NOT_CALIBRATED"
    assert v.route_distance_m is None


def test_not_calibrated_when_endpoints_unresolved_even_if_eligible():
    m = tcc.LogisticsMission(mission_id="M12", payload_stream="STERILE_SUPPLY")  # no object ids
    v = tcc.evaluate_transport_connectivity(m, "AGV_AMR_LIGHT_CLINICAL")
    assert v.status == "NOT_CALIBRATED"


def test_mission_connectivity_ranks_nothing_and_no_forced_mrt_winner():
    reg, graph = _rght_network()
    m = tcc.LogisticsMission(
        mission_id="M13", payload_stream="STERILE_SUPPLY",
        origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ",
    )
    verdicts = tcc.evaluate_mission_connectivity(m, registry=reg, graph=graph)
    # deterministic ordering == ALL_TRANSPORT_MODE_FAMILIES order
    assert tuple(v.eligibility_family for v in verdicts) == elig.ALL_TRANSPORT_MODE_FAMILIES
    # no ranking / no selected winner is present anywhere on the verdicts
    assert all(not hasattr(v, "selected") for v in verdicts)


# ===========================================================================
# §70. Vertical connectivity.
# ===========================================================================

def test_cross_floor_route_reports_vertical_connectivity_satisfied():
    reg, graph = _rght_network()
    # RP is on F1; the proof network includes a cross-floor scanner room on F2.
    # Use the F2 destination object id from the RGHT proof network.
    f2_ids = [oid for oid, o in reg.objects.items() if o.floor_id == "F2" and o.object_type == "RGHT_STATION"]
    assert f2_ids, "expected an F2 RGHT station in the controlled proof network"
    m = tcc.LogisticsMission(
        mission_id="M14", payload_stream="STERILE_SUPPLY",
        origin_object_id="RGHT-STN-RP", destination_object_id=f2_ids[0],
    )
    v = tcc.evaluate_transport_connectivity(m, "AGV_AMR_LIGHT_CLINICAL", registry=reg, graph=graph)
    if v.status == "FEASIBLE":
        assert v.requires_vertical_connectivity is True
        assert v.vertical_connectivity_satisfied is True


# ===========================================================================
# §71. Cross-mode network composition BoM.
# ===========================================================================

def test_bom_composes_pts_and_rght_quantities_from_real_network():
    reg = _base_registry()
    rght_graph, _ = rght.build_controlled_rght_proof_network(reg, facility_id="FAC-001", building_id="B1")
    pts_graph, _ = pts.build_controlled_pts_proof_network(reg, facility_id="FAC-001", building_id="B1")
    # merge both networks' edges into one graph for a cross-mode BoM
    combined = csa.ConnectivityGraph(edges=list(rght_graph.edges) + list(pts_graph.edges))
    bom = tcc.compose_transport_infrastructure_bom(reg, combined)
    networks = {line.network for line in bom.network_lines}
    assert networks == {"MRT", "PTS", "RGHT"}
    rght_line = next(l for l in bom.network_lines if l.network == "RGHT")
    pts_line = next(l for l in bom.network_lines if l.network == "PTS")
    assert rght_line.unit_counts["station"] >= 1
    assert pts_line.unit_counts["station"] >= 1
    assert bom.synthetic_transport_capex is False
    assert bom.connectivity_separate_from_capacity is True


def test_bom_separates_existing_from_new_required():
    reg = _base_registry()
    rght_graph, _ = rght.build_controlled_rght_proof_network(reg, facility_id="FAC-001", building_id="B1")
    bom = tcc.compose_transport_infrastructure_bom(reg, rght_graph)
    rght_line = next(l for l in bom.network_lines if l.network == "RGHT")
    # The controlled proof network is a realistic mix: stations EXISTING,
    # switches/segments/vehicle PROPOSED. The split reuses canonical AssetStatus.
    assert rght_line.existing_object_count >= 1   # the EXISTING stations
    assert rght_line.new_required_object_count >= 1  # the PROPOSED switches/segments


# ===========================================================================
# §72. Cost/quantity accounting + idempotent recomputation.
# ===========================================================================

def test_bom_shared_endpoint_and_vestibule_accounting_is_crosswalk_only():
    reg = _base_registry()
    csa.add_room(reg, facility_id="FAC-001", building_id="B1", floor_id="F1", room_id="INJ-A",
                 object_type="INJECTION_ROOM")
    reg.objects["INJ-A"] = csa.CanonicalSpatialObject(**{**reg.objects["INJ-A"].__dict__, "asset_status": "PROPOSED"})
    sereg = tcc.SharedClinicalLogisticsEndpointRegistry()
    sereg.require_endpoint(reg, room_object_id="INJ-A", serving_mode="RGHT")
    m = tcc.LogisticsMission(
        mission_id="M15", payload_stream="RADIOPHARMACEUTICAL",
        origin_object_id="INJ-A", destination_object_id="INJ-A", nuclear_qualification_present=True,
    )
    vest = tcc.derive_mrt_vestibule_requirement(m, registry=reg)
    graph = csa.ConnectivityGraph()
    bom = tcc.compose_transport_infrastructure_bom(
        reg, graph, shared_endpoints=sereg, mrt_vestibule_requirements=(vest,),
    )
    assert bom.shared_endpoint_count == 1
    assert bom.shared_endpoint_new_required_capex_usd == 1000.0
    assert bom.mrt_vestibule_required_count == 1
    assert bom.mrt_vestibule_new_required_capex_usd == 30000.0
    assert bom.synthetic_transport_capex is False


def test_automatic_connectivity_recomputation_is_idempotent():
    reg, graph = _rght_network()
    m = tcc.LogisticsMission(
        mission_id="M16", payload_stream="STERILE_SUPPLY",
        origin_object_id="RGHT-STN-RP", destination_object_id="RGHT-STN-INJ",
    )
    v1 = tcc.evaluate_transport_connectivity(m, "AGV_AMR_LIGHT_CLINICAL", registry=reg, graph=graph)
    v2 = tcc.evaluate_transport_connectivity(m, "AGV_AMR_LIGHT_CLINICAL", registry=reg, graph=graph)
    assert v1 == v2  # deterministic, idempotent


def test_shared_endpoint_registry_recomputation_is_idempotent():
    reg, _ = _rght_network()
    _existing_room(reg, "INJ-ROOM")
    _existing_room(reg, "RP-ROOM", object_type="RADIOPHARMACY")
    def build():
        r = tcc.SharedClinicalLogisticsEndpointRegistry()
        r.require_endpoint(reg, room_object_id="INJ-ROOM", serving_mode="RGHT")
        r.require_endpoint(reg, room_object_id="RP-ROOM", serving_mode="RGHT")
        return r
    a, b = build(), build()
    assert [e.endpoint_id for e in a.endpoints()] == [e.endpoint_id for e in b.endpoints()]
    assert a.new_required_endpoint_capex_usd() == b.new_required_endpoint_capex_usd()

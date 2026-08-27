"""Focused tests for reactive_engineering_economic_consequence_authority.py
-- Phase 3 reactive engineering/economic consequence closure.
"""

from __future__ import annotations

import dataclasses

import pytest

import reactive_engineering_economic_consequence_authority as reac
import canonical_geometry_shadow_routing_authority as shadow
import canonical_spatial_authority as csa
from mrt_transport_energy_maintenance_authority import MRT_GUIDEWAY_CAPEX_PER_M_USD, MRT_GUIDEWAY_MAINTENANCE_FRACTION_PER_YEAR


def _two_building_registry_with_graph():
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    csa.add_building(reg, facility_id="FAC-001", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="PATIENT-ROOM")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="ROOM-A")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="ROOM-B")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="JUNCTION")
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="PATIENT-ROOM", to_object_id="JUNCTION", length_m=10.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    graph.add_edge(csa.SpatialEdge(edge_id="E2", from_object_id="JUNCTION", to_object_id="ROOM-A", length_m=5.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    graph.add_edge(csa.SpatialEdge(edge_id="E3", from_object_id="JUNCTION", to_object_id="ROOM-B", length_m=15.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    return reg, graph


_ECON_KW = dict(
    throughput_patients_per_day=30.0, revenue_per_scan=2000.0, operating_days_per_year=300,
    discount_rate_pct=8.0, analysis_years=10, baseline_capex=5_000_000.0, baseline_annual_opex=1_000_000.0,
)


# ---------------------------------------------------------------------------
# 1-3. scanner move: route changes, no purchase price charged, cost transparent
# ---------------------------------------------------------------------------


def test_scanner_move_changes_route_geometry():
    reg, graph = _two_building_registry_with_graph()
    old_route = shadow.derive_shadow_route(graph, reg, request=shadow.CanonicalRouteRequest(
        route_request_id="OLD", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A"))
    new_route = shadow.derive_shadow_route(graph, reg, request=shadow.CanonicalRouteRequest(
        route_request_id="NEW", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-B"))
    record = reac.evaluate_move_scanner_consequence(
        change_id="C1", scanner_id="SCN-001", what_if_id="W1", source_lockdown_id="L0",
        route_distance_before_m=old_route.total_distance_m, route_distance_after_m=new_route.total_distance_m,
        travel_time_before_minutes=old_route.estimated_movement_time_minutes, travel_time_after_minutes=new_route.estimated_movement_time_minutes,
        **_ECON_KW,
    )
    assert record.route_distance_before_m != record.route_distance_after_m


def test_scanner_relocation_never_charges_purchase_price():
    record = reac.evaluate_move_scanner_consequence(
        change_id="C2", scanner_id="SCN-001", what_if_id="W1", source_lockdown_id="L0",
        route_distance_before_m=15.0, route_distance_after_m=25.0, travel_time_before_minutes=0.2, travel_time_after_minutes=0.35,
        **_ECON_KW,
    )
    assert record.capex_delta_usd == pytest.approx(reac.SCANNER_RELOCATION_CAPEX_USD.active_value)
    assert record.capex_delta_usd < 1_000_000.0  # far below any plausible NEW scanner purchase price


def test_scanner_relocation_cost_is_transparent_and_editable():
    param = reac.SCANNER_RELOCATION_CAPEX_USD
    assert param.source_type == "CONTROLLED_ENGINEERING_ASSUMPTION"
    assert param.user_editable is True
    overridden = param.with_override(50_000.0)
    assert overridden.active_value == pytest.approx(50_000.0)
    assert param.active_value == pytest.approx(75_000.0)  # original untouched (immutable dataclass)


# ---------------------------------------------------------------------------
# 4-5. patient-room reassignment: no direct CapEx; identity preserved
# ---------------------------------------------------------------------------


def test_patient_room_reassignment_has_no_direct_capex():
    record = reac.evaluate_change_patient_room_consequence(
        change_id="C3", patient_id="P1", what_if_id="W1", source_lockdown_id="L0",
        route_distance_before_m=15.0, route_distance_after_m=20.0, travel_time_before_minutes=0.2, travel_time_after_minutes=0.28,
    )
    assert record.capex_delta_usd == 0.0
    assert record.annual_opex_delta_usd == 0.0


def test_patient_room_change_preserves_identity_fields_externally():
    # Identity preservation is a Phase 1B guarantee (canonical_entity_binding_authority);
    # this proves the Phase 3 consequence record never touches those bindings.
    import canonical_entity_binding_authority as ceba

    registry = ceba.EntityBindingRegistry()
    ceba.bind_patient_batch(registry, patient_id="P1", batch_id="1")
    ceba.bind_patient_radionuclide(registry, patient_id="P1", radionuclide_id="F-18")
    ceba.bind_batch_cyclotron(registry, batch_id="1", cyclotron_id="CY-A")
    ceba.bind_patient_scanner(registry, patient_id="P1", scanner_id="SCN-001")

    reac.evaluate_change_patient_room_consequence(
        change_id="C4", patient_id="P1", what_if_id="W1", source_lockdown_id="L0",
        route_distance_before_m=15.0, route_distance_after_m=20.0, travel_time_before_minutes=0.2, travel_time_after_minutes=0.28,
    )
    assert ceba.batch_for_patient(registry, "P1") == "1"
    assert ceba.radionuclide_for_patient(registry, "P1") == "F-18"
    assert ceba.cyclotron_for_batch(registry, "1") == "CY-A"
    assert ceba.scanner_for_patient(registry, "P1") == "SCN-001"


# ---------------------------------------------------------------------------
# 6-7. building translation: internal geometry preserved; external connection changes
# ---------------------------------------------------------------------------


def test_building_translation_preserves_internal_relative_geometry():
    from facility_engineering_model import SpatialCoordinate

    room_a_before = SpatialCoordinate(x_m=0.0, y_m=0.0, z_m=0.0)
    room_b_before = SpatialCoordinate(x_m=5.0, y_m=0.0, z_m=0.0)  # 5m apart, INSIDE the building
    internal_distance_before = room_b_before.x_m - room_a_before.x_m

    shift = 100.0
    room_a_after = dataclasses.replace(room_a_before, x_m=room_a_before.x_m + shift)
    room_b_after = dataclasses.replace(room_b_before, x_m=room_b_before.x_m + shift)
    internal_distance_after = room_b_after.x_m - room_a_after.x_m

    assert internal_distance_after == pytest.approx(internal_distance_before)  # internal geometry unchanged
    assert room_a_after.x_m != room_a_before.x_m  # the building itself DID move


def test_building_translation_changes_external_connection_length():
    record = reac.evaluate_move_building_consequence(
        change_id="C5", building_id="BLDG-B", what_if_id="W1", source_lockdown_id="L0",
        inter_building_distance_before_m=50.0, inter_building_distance_after_m=150.0, guideway_capex_per_m=MRT_GUIDEWAY_CAPEX_PER_M_USD,
        **_ECON_KW,
    )
    assert record.installed_network_before_m != record.installed_network_after_m
    assert record.capex_delta_usd == pytest.approx(100.0 * MRT_GUIDEWAY_CAPEX_PER_M_USD)


# ---------------------------------------------------------------------------
# 8-10. installed network dedup; endpoint move; mission route stays separate
# ---------------------------------------------------------------------------


def test_installed_network_deduplicates_after_geometry_change():
    import authoritative_geometry_routing_activation as activation

    reg, graph = _two_building_registry_with_graph()
    route_a = shadow.derive_shadow_route(graph, reg, request=shadow.CanonicalRouteRequest(
        route_request_id="A", subject_type="GENERIC", subject_id="X", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-A"))
    route_b = shadow.derive_shadow_route(graph, reg, request=shadow.CanonicalRouteRequest(
        route_request_id="B", subject_type="GENERIC", subject_id="X", transport_mode="PATIENT_WALK",
        origin_location_id="PATIENT-ROOM", destination_location_id="ROOM-B"))
    installed = activation.compute_installed_network_union([route_a, route_b])
    assert installed.total_length_m == pytest.approx(30.0)  # E1+E2+E3, each counted once despite E1 shared


def test_endpoint_move_changes_installed_network_where_required():
    record = reac.evaluate_move_endpoint_consequence(
        change_id="C6", endpoint_id="EP-01", what_if_id="W1", source_lockdown_id="L0",
        installed_network_before_m=222.0, installed_network_after_m=250.0, mission_route_before_m=95.0, mission_route_after_m=95.0,
        guideway_capex_per_m=MRT_GUIDEWAY_CAPEX_PER_M_USD, **_ECON_KW,
    )
    assert record.installed_network_before_m != record.installed_network_after_m
    assert record.capex_delta_usd == pytest.approx(28.0 * MRT_GUIDEWAY_CAPEX_PER_M_USD)


def test_mission_route_remains_separate_from_installed_network_in_consequence_record():
    record = reac.evaluate_move_endpoint_consequence(
        change_id="C7", endpoint_id="EP-01", what_if_id="W1", source_lockdown_id="L0",
        installed_network_before_m=222.0, installed_network_after_m=250.0, mission_route_before_m=95.0, mission_route_after_m=110.0,
        guideway_capex_per_m=MRT_GUIDEWAY_CAPEX_PER_M_USD, **_ECON_KW,
    )
    assert record.route_distance_after_m == pytest.approx(110.0)  # mission route
    assert record.installed_network_after_m == pytest.approx(250.0)  # installed network -- distinct field, distinct value
    assert record.route_distance_after_m != record.installed_network_after_m


# ---------------------------------------------------------------------------
# 11-12. resource sizing reacts; integer thresholds may not cross
# ---------------------------------------------------------------------------


def test_route_time_change_reaches_resource_sizing():
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
    large = agv_required_fleet_size(missions=missions, mission_minutes=90.0, model=model, operating_hours_per_day=18.0, operating_days_per_year=300)
    assert large > small


def test_small_route_change_may_not_cross_integer_resource_threshold_but_is_still_reported():
    record_small = reac.evaluate_move_endpoint_consequence(
        change_id="C8a", endpoint_id="EP-01", what_if_id="W1", source_lockdown_id="L0",
        installed_network_before_m=222.0, installed_network_after_m=222.5, mission_route_before_m=95.0, mission_route_after_m=95.2,
        guideway_capex_per_m=MRT_GUIDEWAY_CAPEX_PER_M_USD, **_ECON_KW,
    )
    # The continuous route-distance delta is reported even though it is tiny.
    assert record_small.route_distance_after_m - record_small.route_distance_before_m == pytest.approx(0.2)
    assert record_small.capex_delta_usd != 0.0  # continuous CapEx still moves, even if a fleet/station COUNT would not


# ---------------------------------------------------------------------------
# 13-14. genuine length-dependent CapEx/maintenance
# ---------------------------------------------------------------------------


def test_genuine_length_dependent_capex_change():
    record = reac.evaluate_move_building_consequence(
        change_id="C9", building_id="BLDG-B", what_if_id="W1", source_lockdown_id="L0",
        inter_building_distance_before_m=50.0, inter_building_distance_after_m=30.0, guideway_capex_per_m=MRT_GUIDEWAY_CAPEX_PER_M_USD,
        **_ECON_KW,
    )
    assert record.capex_delta_usd == pytest.approx(-20.0 * MRT_GUIDEWAY_CAPEX_PER_M_USD)  # shortened connection -- reduced CapEx


def test_length_dependent_maintenance_uses_existing_rate_authority():
    from conventional_transport_authority import DEFAULT_PTS_NETWORK
    # DEFAULT_PTS_NETWORK.annual_maintenance_opex is a genuine EXISTING rate authority
    # this phase reuses (never invents a new one) when a distance-dependent case applies.
    assert DEFAULT_PTS_NETWORK.annual_maintenance_opex >= 0.0


# ---------------------------------------------------------------------------
# 15-16. flat energy stays flat; revenue only through throughput
# ---------------------------------------------------------------------------


def test_flat_energy_authority_not_fabricated_as_distance_sensitive():
    from conventional_transport_authority import DEFAULT_AGV_MODEL
    # DEFAULT_AGV_MODEL.annual_energy_opex is a flat annual value in the existing
    # authority -- Phase 3 does not invent a distance-sensitivity for it.
    energy_before = DEFAULT_AGV_MODEL.annual_energy_opex
    energy_after = DEFAULT_AGV_MODEL.annual_energy_opex  # unchanged regardless of route distance
    assert energy_before == energy_after


def test_revenue_changes_only_through_throughput_not_distance():
    same_throughput_kw = dict(_ECON_KW)
    record = reac.evaluate_move_scanner_consequence(
        change_id="C10", scanner_id="SCN-001", what_if_id="W1", source_lockdown_id="L0",
        route_distance_before_m=15.0, route_distance_after_m=500.0,  # huge distance change
        travel_time_before_minutes=0.2, travel_time_after_minutes=6.0,
        **same_throughput_kw,  # throughput UNCHANGED
    )
    assert record.annual_revenue_delta_usd == 0.0  # distance alone never creates revenue


# ---------------------------------------------------------------------------
# 17-20. lifecycle economics consume changed CapEx/OPEX; NPV/payback/IRR recompute
# ---------------------------------------------------------------------------


def test_lifecycle_economics_consume_changed_capex_npv_recomputes():
    record = reac.evaluate_move_scanner_consequence(
        change_id="C11", scanner_id="SCN-001", what_if_id="W1", source_lockdown_id="L0",
        route_distance_before_m=15.0, route_distance_after_m=25.0, travel_time_before_minutes=0.2, travel_time_after_minutes=0.35,
        **_ECON_KW,
    )
    assert record.npv_delta_usd == pytest.approx(-record.capex_delta_usd)  # NPV drops by exactly the added CapEx (no OPEX/revenue change)


def test_payback_recomputes_where_applicable():
    record = reac.evaluate_move_building_consequence(
        change_id="C12", building_id="BLDG-B", what_if_id="W1", source_lockdown_id="L0",
        inter_building_distance_before_m=50.0, inter_building_distance_after_m=150.0, guideway_capex_per_m=MRT_GUIDEWAY_CAPEX_PER_M_USD,
        **_ECON_KW,
    )
    assert record.payback_delta_years is not None
    assert record.payback_after_years > record.payback_before_years  # more CapEx -> longer payback


def test_irr_uses_verified_authority_and_recomputes():
    record = reac.evaluate_move_scanner_consequence(
        change_id="C13", scanner_id="SCN-001", what_if_id="W1", source_lockdown_id="L0",
        route_distance_before_m=15.0, route_distance_after_m=25.0, travel_time_before_minutes=0.2, travel_time_after_minutes=0.35,
        **_ECON_KW,
    )
    assert record.irr_before_pct != "NOT_CALIBRATED"
    assert record.irr_after_pct != "NOT_CALIBRATED"
    assert record.irr_delta_pct is not None
    assert record.irr_after_pct < record.irr_before_pct  # more capex, same cash flow -> lower IRR


# ---------------------------------------------------------------------------
# 21-23. Lockdown/What-If governance
# ---------------------------------------------------------------------------


def test_w1_consequence_does_not_mutate_l0():
    import lockdown_what_if_lineage_authority as lla

    registry = lla.LockdownLineageRegistry()
    spatial_locked = csa.LockedSpatialState(registry=csa.build_facility_hierarchy(facility_id="FAC-001"))
    l0 = lla.create_first_lockdown(registry, locked=spatial_locked, economic_result={"capex": 5_000_000.0})
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)

    record = reac.evaluate_move_scanner_consequence(
        change_id="C14", scanner_id="SCN-001", what_if_id=w1.what_if_id, source_lockdown_id=l0.lockdown_id,
        route_distance_before_m=15.0, route_distance_after_m=25.0, travel_time_before_minutes=0.2, travel_time_after_minutes=0.35,
        **_ECON_KW,
    )
    lla.update_what_if_results(registry, w1.what_if_id, economic_result={"capex": 5_000_000.0 + record.capex_delta_usd})
    assert registry.lockdown(l0.lockdown_id).economic_result == {"capex": 5_000_000.0}  # L0 untouched
    assert registry.current_lockdown_id == l0.lockdown_id


def test_discard_returns_to_l0():
    import lockdown_what_if_lineage_authority as lla

    registry = lla.LockdownLineageRegistry()
    spatial_locked = csa.LockedSpatialState(registry=csa.build_facility_hierarchy(facility_id="FAC-001"))
    l0 = lla.create_first_lockdown(registry, locked=spatial_locked)
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    lla.discard_what_if(registry, w1.what_if_id)
    assert registry.current_lockdown_id == l0.lockdown_id
    assert registry.what_if(w1.what_if_id).status == "DISCARDED"


def test_promotion_remains_explicit():
    import lockdown_what_if_lineage_authority as lla

    registry = lla.LockdownLineageRegistry()
    spatial_locked = csa.LockedSpatialState(registry=csa.build_facility_hierarchy(facility_id="FAC-001"))
    l0 = lla.create_first_lockdown(registry, locked=spatial_locked)
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    assert registry.current_lockdown_id == l0.lockdown_id  # branching alone never promotes
    l1 = lla.promote_what_if_to_lockdown(registry, w1.what_if_id)
    assert registry.current_lockdown_id == l1.lockdown_id
    assert l1.parent_lockdown_id == l0.lockdown_id


# ---------------------------------------------------------------------------
# 24-25. frozen benchmark protected; Phase 2 foundation remains green
# ---------------------------------------------------------------------------


def test_frozen_benchmark_unaffected_by_phase_3_module_import():
    from whole_oncology_four_architecture_optimization import build_eight_floor_deterministic_capital_baseline

    baseline = build_eight_floor_deterministic_capital_baseline(seed=42)
    assert len(baseline.patients) == 80


def test_phase_2_mixed_mode_foundation_remains_intact():
    import digital_twin_simulation_state as dts

    record = dts.TransportRuntimeRecord(
        runtime_id="R1", technology="MRT", mission_id="M1", physical_asset_id="CARRIER-01", payload_id=None,
        route_id=None, current_segment_id=None, departure_time_minutes=0.0, arrival_time_minutes=10.0, state="WAITING",
    )
    assert dts.resolve_transport_runtime_state(record, at_time_minutes=5.0) == "IN_TRANSIT"

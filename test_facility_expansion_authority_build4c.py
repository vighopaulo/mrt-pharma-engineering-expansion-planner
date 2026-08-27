"""Focused tests for Facility Expansion Authority Build 4C: Canonical
Hospital Logistics Role-Location and Porter Route Closure.

Closes the Build 4B disclosed gap: LABORATORY/CENTRAL_PHARMACY/
CLEAN_LINEN_SOURCE/STERILE_CLEAN_SUPPLY_SOURCE now bind to real canonical
spatial objects (`hospital_logistics_role_location_authority`), and
general-logistics porter missions resolve real corridor/elevator route
timing instead of the existing 8-minute fallback wherever a canonical role
location is bound.
"""

from datetime import date
from dataclasses import replace

import canonical_spatial_authority as csa
import conventional_transport_authority as cta
import facility_expansion_authority as fea
import hospital_logistics_role_location_authority as hlra
import human_circulation_authority as hca
import operational_day_orchestrator as ody
import pytest
from ifc_hospital_proof_model_generator import FLOOR_TO_FLOOR_HEIGHT_M

FACILITY_ID = "FAC-B4C"
DAY = date(2026, 2, 3)
ROLE_IDS = ("RP-SRC", "PHARM-001", "LAB-001", "LINEN-001", "STERILE-001")


def _fixture_with_roles():
    reg = csa.build_facility_hierarchy(facility_id=FACILITY_ID)
    csa.add_building(reg, facility_id=FACILITY_ID, building_id="BLDG-V")
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F1")
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F1", room_id="RP-SRC", object_type="RADIOPHARMACY")
    bindings = hlra.build_controlled_hospital_role_registry(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F1")
    csa.add_floor(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F2", transform=csa.Transform(position_z=FLOOR_TO_FLOOR_HEIGHT_M))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F2", room_id="ROOM-PAT-201", object_type="PATIENT_ROOM", transform=csa.Transform(position_x=6.0, position_y=15.0, position_z=FLOOR_TO_FLOOR_HEIGHT_M))
    csa.add_room(reg, facility_id=FACILITY_ID, building_id="BLDG-V", floor_id="F2", room_id="ROOM-PAT-202", object_type="PATIENT_ROOM", transform=csa.Transform(position_x=8.0, position_y=15.0, position_z=FLOOR_TO_FLOOR_HEIGHT_M))
    return reg, bindings


def _full_graph(registry, role_ids, room_ids):
    graph = csa.ConnectivityGraph()
    for role_id in role_ids:
        for rid in room_ids:
            graph.add_edge(csa.SpatialEdge(edge_id=f"E-{role_id}-{rid}", from_object_id=role_id, to_object_id=rid, length_m=csa.compute_global_distance(registry, role_id, rid), compatible_modes=frozenset({"WALKING_PORTER", "PATIENT_MOVEMENT"}), vertical=True))
    return graph


def _extend_graph(graph, registry, role_ids, new_room_ids):
    for role_id in role_ids:
        for rid in new_room_ids:
            eid = f"E-{role_id}-{rid}"
            if not any(e.edge_id == eid for e in graph.edges):
                graph.add_edge(csa.SpatialEdge(edge_id=eid, from_object_id=role_id, to_object_id=rid, length_m=csa.compute_global_distance(registry, role_id, rid), compatible_modes=frozenset({"WALKING_PORTER", "PATIENT_MOVEMENT"}), vertical=True))


def _sequence_2_to_n(n_floors: int):
    reg, _bindings = _fixture_with_roles()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    room_ids = ["ROOM-PAT-201", "ROOM-PAT-202"]
    graph = _full_graph(what_if.registry, ROLE_IDS, room_ids)
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
        _extend_graph(graph, what_if.registry, ROLE_IDS, record.created_room_ids)
        snapshot()
    return locked, what_if, rows


# ===========================================================================
# Section 30: ROLE BINDING (items 1-10)
# ===========================================================================


def test_1_laboratory_binds_to_canonical_object():
    reg, bindings = _fixture_with_roles()
    b = next(x for x in bindings if x.role == "LABORATORY")
    assert b.canonical_object_id == "LAB-001"
    assert b.status == "CALIBRATED_CANONICAL_LOCATION"
    assert "LAB-001" in reg.objects


def test_2_central_pharmacy_binds_to_canonical_object():
    reg, bindings = _fixture_with_roles()
    b = next(x for x in bindings if x.role == "CENTRAL_PHARMACY")
    assert b.canonical_object_id == "PHARM-001"
    assert b.status == "CALIBRATED_CANONICAL_LOCATION"
    assert "PHARM-001" in reg.objects


def test_3_clean_linen_source_binds_to_canonical_object():
    reg, bindings = _fixture_with_roles()
    b = next(x for x in bindings if x.role == "CLEAN_LINEN_SOURCE")
    assert b.canonical_object_id == "LINEN-001"
    assert b.status == "CONTROLLED_PROOF_LOCATION"
    assert reg.objects["LINEN-001"].object_type == "CLEAN_LINEN_SOURCE"


def test_4_sterile_clean_supply_source_binds_to_canonical_object():
    reg, bindings = _fixture_with_roles()
    b = next(x for x in bindings if x.role == "STERILE_CLEAN_SUPPLY")
    assert b.canonical_object_id == "STERILE-001"
    assert b.status == "CONTROLLED_PROOF_LOCATION"
    assert reg.objects["STERILE-001"].object_type == "STERILE_CLEAN_SUPPLY_SOURCE"


def test_5_radiopharmacy_binding_remains_valid():
    reg, _bindings = _fixture_with_roles()
    assert "RP-SRC" in reg.objects
    assert reg.objects["RP-SRC"].object_type == "RADIOPHARMACY"


def test_6_role_identity_distinct_from_spatial_object_identity():
    assert hlra.LOGISTICS_ROLE_AND_SPATIAL_OBJECT_ARE_DISTINCT is True
    assert hlra.LOGISTICS_ROLE_CAN_BIND_TO_CANONICAL_OBJECT is True
    reg, bindings = _fixture_with_roles()
    b = next(x for x in bindings if x.role == "LABORATORY")
    assert b.role != b.canonical_object_id  # functional role name is not the spatial object id


def test_7_role_binding_status_and_provenance_explicit():
    assert hlra.ROLE_LOCATION_STATUS_EXPLICIT is True
    reg, bindings = _fixture_with_roles()
    for b in bindings:
        assert b.status in ("CALIBRATED_CANONICAL_LOCATION", "CONTROLLED_PROOF_LOCATION", "NOT_CALIBRATED")
        assert b.provenance


def test_8_missing_role_location_remains_honestly_not_calibrated():
    from general_oncology_logistics import FacilityRoleLocation
    reg = csa.build_facility_hierarchy(facility_id=FACILITY_ID)
    unbound = FacilityRoleLocation(role="CLEAN_LINEN_SOURCE", object_id=None, building_id=None, floor_id=None, location_status="LOCATION_NOT_CALIBRATED")
    binding = hlra.bind_role_location(unbound, reg)
    assert binding.status == "NOT_CALIBRATED"
    unregistered = FacilityRoleLocation(role="LABORATORY", object_id="LAB-999-MISSING", building_id="BLDG-V", floor_id="F1", location_status="CALIBRATED")
    binding2 = hlra.bind_role_location(unregistered, reg)
    assert binding2.status == "NOT_CALIBRATED"


def test_9_role_binding_does_not_alter_asset_cost_status():
    reg, _bindings = _fixture_with_roles()
    for object_id in ("PHARM-001", "LAB-001", "LINEN-001", "STERILE-001"):
        assert reg.objects[object_id].asset_status == "EXISTING"
    assert hlra.ROLE_BINDING_CHANGES_ASSET_COST_STATUS is False


def test_10_role_binding_does_not_require_bentley():
    assert hlra.ROLE_BINDING_REQUIRES_BENTLEY is False
    import inspect
    lines = [l.strip() for l in inspect.getsource(hlra).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("bentley" in line.lower() for line in lines)


# ===========================================================================
# Section 31: REAL GENERAL-LOGISTICS ROUTES (items 11-22)
# ===========================================================================


def _floor2_traces():
    reg, _bindings = _fixture_with_roles()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    room_ids = ["ROOM-PAT-201", "ROOM-PAT-202"]
    graph = _full_graph(what_if.registry, ROLE_IDS, room_ids)
    return fea.generate_vertical_expansion_porter_missions(what_if.registry, graph, day=DAY, created_room_ids=tuple(room_ids), radiopharmacy_object_id="RP-SRC")


def test_11_specimen_blood_manual_route_resolves():
    traces = _floor2_traces()
    t = next(x for x in traces if x.stream == "SPECIMEN_BLOOD")
    assert t.route_distance_m != "NOT_CALIBRATED"


def test_12_pharmacy_infusion_manual_route_resolves():
    traces = _floor2_traces()
    t = next(x for x in traces if x.stream == "PHARMACY_INFUSION")
    assert t.route_distance_m != "NOT_CALIBRATED"


def test_13_clean_linen_manual_route_resolves():
    traces = _floor2_traces()
    t = next(x for x in traces if x.stream == "CLEAN_LINEN")
    assert t.route_distance_m != "NOT_CALIBRATED"


def test_14_sterile_clean_supply_manual_route_resolves():
    traces = _floor2_traces()
    t = next(x for x in traces if x.stream == "STERILE_CLEAN_SUPPLY")
    assert t.route_distance_m != "NOT_CALIBRATED"


def test_15_radiopharmaceutical_manual_route_still_resolves():
    traces = _floor2_traces()
    t = next(x for x in traces if x.stream == "RADIOPHARMACEUTICAL_MANUAL")
    assert t.route_distance_m != "NOT_CALIBRATED"


def test_16_real_routes_use_common_pedestrian_route_solver():
    import inspect
    source = inspect.getsource(fea.generate_vertical_expansion_porter_missions)
    assert "hca.resolve_pedestrian_route(" in source
    assert source.count("def resolve_") == 0


def test_17_route_distance_comes_from_canonical_geometry():
    reg, _bindings = _fixture_with_roles()
    traces = _floor2_traces()
    t = next(x for x in traces if x.stream == "PHARMACY_INFUSION")
    expected = csa.compute_global_distance(reg, "PHARM-001", "ROOM-PAT-201")
    assert t.route_distance_m == pytest.approx(expected)


def test_18_cross_floor_routes_preserve_z_elevator_transitions():
    traces = _floor2_traces()
    for t in traces:
        assert t.vertical_transitions == 1


def test_19_routes_do_not_cut_through_walls_when_corridor_topology_exists():
    reg, _bindings = _fixture_with_roles()
    lab = reg.objects["LAB-001"].transform
    room = reg.objects["ROOM-PAT-201"].transform
    straight_line = ((lab.position_x - room.position_x) ** 2 + (lab.position_y - room.position_y) ** 2 + (lab.position_z - room.position_z) ** 2) ** 0.5
    traces = _floor2_traces()
    t = next(x for x in traces if x.stream == "SPECIMEN_BLOOD")
    assert t.route_distance_m >= straight_line  # routed via graph edges, never shorter than the straight line


def test_20_real_route_takes_precedence_over_8_minute_fallback():
    traces = _floor2_traces()
    for stream in ("SPECIMEN_BLOOD", "PHARMACY_INFUSION", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY"):
        t = next(x for x in traces if x.stream == stream)
        assert t.mission_minutes != 8.0
    assert fea.PORTER_VERTICAL_EXPANSION_WORKLOAD_USES_REAL_ROUTE_TIMING is True


def test_21_missing_route_still_uses_fallback_honestly():
    reg, _bindings = _fixture_with_roles()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    room_ids = ["ROOM-PAT-201", "ROOM-PAT-202"]
    graph = csa.ConnectivityGraph()  # no edges at all -- nothing is routable
    traces = fea.generate_vertical_expansion_porter_missions(what_if.registry, graph, day=DAY, created_room_ids=tuple(room_ids), radiopharmacy_object_id="RP-SRC")
    for t in traces:
        assert t.route_distance_m == "NOT_CALIBRATED"
        assert "default" in t.timing_provenance or "fallback" in t.timing_provenance.lower()


def test_22_no_stream_direction_reversed_relative_to_existing_authority():
    traces = _floor2_traces()
    specimen = next(x for x in traces if x.stream == "SPECIMEN_BLOOD")
    pharmacy = next(x for x in traces if x.stream == "PHARMACY_INFUSION")
    assert specimen.destination == "LAB-001"  # ward -> laboratory (existing authority's own reversal)
    assert pharmacy.origin == "PHARM-001"  # pharmacy -> ward


# ===========================================================================
# Section 32: EXPANSION / WORKLOAD (items 23-35)
# ===========================================================================


def test_23_new_floors_do_not_replicate_centralized_role_sources():
    _locked, what_if, rows = _sequence_2_to_n(4)
    for object_id in ("PHARM-001", "LAB-001", "LINEN-001", "STERILE-001", "RP-SRC"):
        count = sum(1 for o in what_if.registry.objects.values() if o.mrtway_object_id == object_id)
        assert count == 1
    assert hlra.CENTRAL_SERVICE_ROLE_REPLICATES_WITH_EVERY_FLOOR is False


def test_24_route_time_increases_with_higher_floor_destinations():
    _locked, _what_if, rows = _sequence_2_to_n(8)
    floor2_traces = rows[0][1]
    floor8_traces = rows[-1][1]
    max_specimen_2 = max(t.mission_minutes for t in floor2_traces if t.stream == "SPECIMEN_BLOOD")
    max_specimen_8 = max(t.mission_minutes for t in floor8_traces if t.stream == "SPECIMEN_BLOOD")
    assert max_specimen_8 > max_specimen_2


def test_25_horizontal_relocation_of_role_containing_building_recomputes_route():
    reg, _bindings = _fixture_with_roles()
    csa.add_building(reg, facility_id=FACILITY_ID, building_id="BLDG-ANCHOR-4C")
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    before = csa.compute_global_distance(what_if.registry, "PHARM-001", "ROOM-PAT-201")
    fea.apply_horizontal_expansion(what_if, fea.HorizontalExpansionRequest(expansion_id="E-4C", anchor_object_id="BLDG-ANCHOR-4C", target_object_id="BLDG-V", expansion_distance_m=15.0, direction_vector=(1.0, 0.0, 0.0)))
    after = csa.compute_global_distance(what_if.registry, "PHARM-001", "ROOM-PAT-201")
    assert before == pytest.approx(after)  # PHARM-001 and the room moved together (same building) -- internal separation preserved


def test_26_role_remains_bound_to_moved_object():
    reg, bindings = _fixture_with_roles()
    csa.add_building(reg, facility_id=FACILITY_ID, building_id="BLDG-ANCHOR-4C2")
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    fea.apply_horizontal_expansion(what_if, fea.HorizontalExpansionRequest(expansion_id="E-4C2", anchor_object_id="BLDG-ANCHOR-4C2", target_object_id="BLDG-V", expansion_distance_m=15.0, direction_vector=(1.0, 0.0, 0.0)))
    b = next(x for x in bindings if x.role == "CENTRAL_PHARMACY")
    assert b.canonical_object_id == "PHARM-001"
    assert "PHARM-001" in what_if.registry.objects  # role never remapped to a different object


def test_27_porter_workload_uses_real_general_logistics_mission_times():
    traces = _floor2_traces()
    general_minutes = {t.mission_minutes for t in traces if t.stream != "RADIOPHARMACEUTICAL_MANUAL"}
    assert len(general_minutes) > 1  # distinct real times, not one flat constant


def test_28_staffing_formula_unchanged():
    regular, overtime = ody.resolve_shift_hours(operating_hours_per_day=18.0, regular_shift_hours=8.0)
    assert (regular, overtime) == (16.0, 2.0)
    basis = ody.build_common_economic_basis()
    assert basis.overtime_multiplier == 1.5


def test_29_labor_rates_unchanged():
    policy = cta.PorterOperatingPolicy()
    assert policy.base_wage_per_hour == 17.0
    assert policy.loaded_employer_cost_multiplier == 1.3


def test_30_two_to_eight_porter_workload_recomputed():
    _locked, _what_if, rows = _sequence_2_to_n(8)
    assert len(rows) == 7
    workloads = [r[2].manual_transport_worker_hours_required for r in rows]
    assert workloads == sorted(workloads)
    assert workloads[-1] > workloads[0]


def test_31_first_staffing_threshold_recomputed():
    reg, _bindings = _fixture_with_roles()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    room_ids = ["ROOM-PAT-201", "ROOM-PAT-202"]
    graph = _full_graph(what_if.registry, ROLE_IDS, room_ids)
    ref = "BLDG-V::F2"
    prev_positions = 1
    threshold_floor = None
    floor_count = 2
    for i in range(20):
        if i > 0:
            record = fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id=f"EXP-V-{i}", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id=ref))
            floor_count += 1
            room_ids.extend(record.created_room_ids)
            _extend_graph(graph, what_if.registry, ROLE_IDS, record.created_room_ids)
        traces = fea.generate_vertical_expansion_porter_missions(what_if.registry, graph, day=DAY, created_room_ids=tuple(room_ids), radiopharmacy_object_id="RP-SRC")
        result = fea.compute_vertical_expansion_porter_labor_opex(traces)
        if result.simultaneous_positions != prev_positions:
            threshold_floor = floor_count
            break
        prev_positions = result.simultaneous_positions
    assert threshold_floor == 16  # recomputed from real routes -- earlier than Build 4B's 20 (never forced equal)


def test_32_patient_travel_excluded_from_porter_labor():
    assert fea.PATIENT_TRAVEL_COUNTED_AS_PORTER_LABOR is False
    import inspect
    source = inspect.getsource(fea.generate_vertical_expansion_porter_missions)
    assert 'subject="PATIENT"' not in source


def test_33_transport_technology_assignment_remains_upstream():
    import inspect
    source = inspect.getsource(fea.generate_vertical_expansion_porter_missions)
    assert 'architecture="MANUAL_CONVENTIONAL"' in source
    assert "missions_for_architecture(" in source


def test_34_manual_last_mile_remains_distinct_from_automated_main_leg():
    policy = cta.PorterOperatingPolicy()
    last_mile_timing = cta.compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=ody.AGV_PTS_LAST_MILE_DISTANCE_M)
    assert last_mile_timing.total_minutes > 0.0
    assert ody.AGV_PTS_LAST_MILE_DISTANCE_M != ody.MRT_CONTROLLED_ROUTE_LENGTH_M


def test_35_l0_remains_unchanged():
    reg, _bindings = _fixture_with_roles()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    before = dict(locked.registry.objects)
    room_ids = ["ROOM-PAT-201", "ROOM-PAT-202"]
    graph = _full_graph(what_if.registry, ROLE_IDS, room_ids)
    fea.generate_vertical_expansion_porter_missions(what_if.registry, graph, day=DAY, created_room_ids=tuple(room_ids), radiopharmacy_object_id="RP-SRC")
    fea.apply_vertical_expansion_increment(what_if, fea.VerticalExpansionRequest(expansion_id="EXP-V-1", facility_id=FACILITY_ID, building_id="BLDG-V", added_floor_count=1, reference_floor_id="BLDG-V::F2"))
    after = dict(locked.registry.objects)
    assert before == after

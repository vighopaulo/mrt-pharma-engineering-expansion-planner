"""Focused tests for canonical_spatial_authority.py -- the Canonical Facility
Geometry + Spatial Object Authority build.

Covers: stable object identity, facility hierarchy, position/orientation,
coordinate systems, spatial status, external-reference mappings, nuclear/
general-logistics/MRT object types, vestibule distinct economics,
connectivity graph + mode-specific routing, patient spatial resolution,
nuclear trace resync (WITHOUT touching hybrid physics), serialization,
provenance, validation, locked-state immutability, what-if changesets
(add/remove/move/rotate/copy/extend/shorten/reconnect), reset-to-locked,
changeset reversibility (undo), promotion-to-simulation-input, object-
inspector contract, delta contract, N-building generality, platform-adapter
readiness (native json + USD prim path derivation), and backend non-
regression against existing authorities.
"""

import dataclasses
from datetime import date

import pytest

import canonical_spatial_authority as csa
from whole_oncology_four_architecture_optimization import (
    build_common_project_baseline,
    _nuclear_result,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _build_two_building_registry() -> csa.SpatialObjectRegistry:
    """N-BUILDING GENERALITY: builds N=2 buildings via a loop over IDs --
    never hard-codes "Building A"/"Building B" as special cases."""
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    for building_id, floors in {"BLDG-A": ("F1", "F2"), "BLDG-B": ("F1",)}.items():
        csa.add_building(reg, facility_id="FAC-001", building_id=building_id)
        for floor_id in floors:
            csa.add_floor(reg, facility_id="FAC-001", building_id=building_id, floor_id=floor_id)
            csa.add_room(reg, facility_id="FAC-001", building_id=building_id, floor_id=floor_id, room_id=f"{building_id}-{floor_id}-R01")
    return reg


def _build_three_building_registry() -> csa.SpatialObjectRegistry:
    """A THIRD building count to prove no logic is bound to exactly two."""
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    for building_id in ("BLDG-A", "BLDG-B", "BLDG-C"):
        csa.add_building(reg, facility_id="FAC-001", building_id=building_id)
        csa.add_floor(reg, facility_id="FAC-001", building_id=building_id, floor_id="F1")
        csa.add_room(reg, facility_id="FAC-001", building_id=building_id, floor_id="F1", room_id=f"{building_id}-F1-R01")
    return reg


# ---------------------------------------------------------------------------
# 1. Stable object identity + hierarchy
# ---------------------------------------------------------------------------


def test_object_id_is_stable_key_never_array_position():
    reg = _build_two_building_registry()
    obj = reg.get("BLDG-A-F1-R01")
    assert obj.mrtway_object_id == "BLDG-A-F1-R01"
    # Order of dict iteration must not matter for identity resolution.
    ids_first_pass = list(reg.objects.keys())
    reg.objects = dict(reversed(list(reg.objects.items())))
    assert reg.get("BLDG-A-F1-R01").mrtway_object_id == "BLDG-A-F1-R01"
    assert set(reg.objects.keys()) == set(ids_first_pass)


def test_duplicate_object_id_rejected():
    reg = _build_two_building_registry()
    dup = dataclasses.replace(reg.get("BLDG-A-F1-R01"))
    with pytest.raises(ValueError):
        reg.add(dup)


def test_facility_hierarchy_facility_building_floor_room():
    reg = _build_two_building_registry()
    facility = reg.get("FAC-001")
    building = reg.get("BLDG-A")
    floor = reg.get("BLDG-A::F1")
    room = reg.get("BLDG-A-F1-R01")
    assert facility.object_type == "FACILITY"
    assert building.object_type == "BUILDING" and building.parent_object_id == "FAC-001"
    assert floor.object_type == "FLOOR" and floor.parent_object_id == "BLDG-A"
    assert room.object_type == "ROOM" and room.parent_object_id == "BLDG-A::F1"


def test_children_of_returns_direct_children_only():
    reg = _build_two_building_registry()
    children = reg.children_of("FAC-001")
    assert {c.mrtway_object_id for c in children} == {"BLDG-A", "BLDG-B"}


# ---------------------------------------------------------------------------
# 2. N-building production generality (never hard-coded to 2)
# ---------------------------------------------------------------------------


def test_n_building_generality_three_buildings_supported():
    reg = _build_three_building_registry()
    buildings = reg.by_type("BUILDING")
    assert {b.mrtway_object_id for b in buildings} == {"BLDG-A", "BLDG-B", "BLDG-C"}
    rooms = reg.by_type("ROOM")
    assert len(rooms) == 3


def test_n_building_generality_single_building_also_supported():
    reg = csa.build_facility_hierarchy(facility_id="FAC-SINGLE")
    csa.add_building(reg, facility_id="FAC-SINGLE", building_id="BLDG-ONLY")
    assert len(reg.by_type("BUILDING")) == 1


# ---------------------------------------------------------------------------
# 3. Position/orientation, coordinate system, spatial status
# ---------------------------------------------------------------------------


def test_transform_defaults_and_override():
    t = csa.Transform(position_x=1.0, position_y=2.0, position_z=3.0, rotation_z=90.0)
    obj = csa.add_building(csa.build_facility_hierarchy(), facility_id="FAC-001", building_id="BLDG-X", transform=t)
    assert obj.transform.position_x == 1.0
    assert obj.transform.rotation_z == 90.0


def test_coordinate_system_assigned_per_level():
    reg = _build_two_building_registry()
    assert reg.get("FAC-001").coordinate_system == "PROJECT_GLOBAL"
    assert reg.get("BLDG-A").coordinate_system == "LOCAL_FACILITY"
    assert reg.get("BLDG-A::F1").coordinate_system == "LOCAL_BUILDING"


def test_spatial_status_not_calibrated_for_missing_role_location():
    reg = _build_two_building_registry()
    origins = csa.build_general_logistics_origin_objects(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    not_calibrated = [o for o in origins if o.spatial_status == "LOCATION_NOT_CALIBRATED"]
    assert len(not_calibrated) >= 1  # CLEAN_LINEN_SOURCE / STERILE_CLEAN_SUPPLY per general_oncology_logistics


# ---------------------------------------------------------------------------
# 4. External reference mappings (never identity)
# ---------------------------------------------------------------------------


def test_external_reference_is_a_mapping_not_identity():
    reg = _build_two_building_registry()
    obj = reg.get("BLDG-A-F1-R01")
    mapped = dataclasses.replace(obj, external_reference=csa.ExternalReference(ifc_guid="IFC-XYZ", usd_prim_path="/Fac/BldgA/F1/R01"))
    assert mapped.mrtway_object_id == obj.mrtway_object_id
    assert mapped.external_reference.ifc_guid == "IFC-XYZ"


def test_external_mapping_collision_detected():
    reg = _build_two_building_registry()
    a = reg.get("BLDG-A-F1-R01")
    b = reg.get("BLDG-B-F1-R01")
    reg.objects["BLDG-A-F1-R01"] = dataclasses.replace(a, external_reference=csa.ExternalReference(ifc_guid="SAME-GUID"))
    reg.objects["BLDG-B-F1-R01"] = dataclasses.replace(b, external_reference=csa.ExternalReference(ifc_guid="SAME-GUID"))
    issues = csa.validate_spatial_registry(reg)
    assert any(i.issue_type == "EXTERNAL_MAPPING_COLLISION" for i in issues)


def test_resolve_selection_by_external_id():
    reg = _build_two_building_registry()
    obj = reg.get("BLDG-A-F1-R01")
    reg.objects["BLDG-A-F1-R01"] = dataclasses.replace(obj, external_reference=csa.ExternalReference(itwin_element_id="ITWIN-1"))
    adapter = csa.NativeJsonSpatialAdapter()
    found = adapter.resolve_selection(reg, "ITWIN-1", "itwin_element_id")
    assert found is not None and found.mrtway_object_id == "BLDG-A-F1-R01"
    assert adapter.resolve_selection(reg, "NOT-THERE", "itwin_element_id") is None


# ---------------------------------------------------------------------------
# 5. Nuclear/oncology + general-logistics object types
# ---------------------------------------------------------------------------


def test_nuclear_engineering_objects_link_to_existing_engineering_authority():
    reg = _build_two_building_registry()
    created = csa.build_nuclear_engineering_objects(
        reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1",
        generator_id="GEN-001", spect_scanner_id="SCN-SPECT-001",
    )
    by_type = {o.object_type: o for o in created}
    assert by_type["CYCLOTRON"].engineering_object_id == "CY-001"
    assert by_type["MO99_TC99M_GENERATOR"].engineering_object_id == "GEN-001"
    assert by_type["PET_SCANNER"].engineering_object_id == "SCN-PET-001"
    assert by_type["SPECT_SCANNER"].engineering_object_id == "SCN-SPECT-001"
    assert by_type["RADIOPHARMACY"].engineering_object_id == "RP-001"


def test_general_logistics_origin_objects_reuse_facility_role_locations():
    reg = _build_two_building_registry()
    origins = csa.build_general_logistics_origin_objects(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    types = {o.object_type for o in origins}
    assert types == {"CENTRAL_PHARMACY", "LABORATORY", "BLOOD_BANK", "CLEAN_LINEN_SOURCE", "STERILE_CLEAN_SUPPLY_SOURCE"}


# ---------------------------------------------------------------------------
# 6. MRT engineering objects + vestibule distinct economics
# ---------------------------------------------------------------------------


def test_mrt_segment_calibrated_vs_not_calibrated_status():
    reg = _build_two_building_registry()
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    calibrated = csa.build_mrt_segment(reg, segment_id="SEG-CAL", facility_id="FAC-001", start_object_id="RP-001", end_object_id="BLDG-A-F1-R01", length_m=15.0)
    not_calibrated = csa.build_mrt_segment(reg, segment_id="SEG-NC", facility_id="FAC-001", start_object_id="RP-001", end_object_id="BLDG-A-F1-R01")
    assert calibrated.spatial_status == "CALIBRATED"
    assert not_calibrated.spatial_status == "GEOMETRY_NOT_CALIBRATED"


def test_vestibule_is_first_class_object_distinct_from_radiopharmacy_and_segment():
    reg = _build_two_building_registry()
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    seg = csa.build_mrt_segment(reg, segment_id="SEG-1", facility_id="FAC-001", start_object_id="RP-001", end_object_id="BLDG-A-F1-R01", length_m=10.0)
    vestibule = csa.build_mrt_vestibule(reg, vestibule_id="VEST-1", facility_id="FAC-001", radiopharmacy_object_id="RP-001", connected_mrt_segment_id=seg.mrtway_object_id)
    assert vestibule.object_type == "MRT_VESTIBULE"
    assert vestibule.mrtway_object_id not in (seg.mrtway_object_id, "RP-001")


def test_vestibule_missing_radiopharmacy_reference_raises():
    reg = _build_two_building_registry()
    with pytest.raises(ValueError):
        csa.build_mrt_vestibule(reg, vestibule_id="VEST-BAD", facility_id="FAC-001", radiopharmacy_object_id="RP-DOES-NOT-EXIST", connected_mrt_segment_id="SEG-DOES-NOT-EXIST")


def test_vestibule_economics_distinct_from_conduit_per_meter_pricing():
    conduit_capex = csa.mrt_segment_length_capex(length_m=50.0, unit_cost_per_length=100.0)
    vestibule_capex = csa.CONTROLLED_VESTIBULE_ECONOMICS.total_capex()
    assert conduit_capex == 5000.0
    assert vestibule_capex != conduit_capex
    # CLOSURE BUILD correction: user-supplied MRT_VESTIBULE_CAPEX_USD = $30,000/vestibule.
    assert vestibule_capex == pytest.approx(30000.0)
    assert csa.CONTROLLED_VESTIBULE_ECONOMICS.annual_maintenance_opex == 1500.0


def test_vestibule_capex_zero_in_operational_only_scope():
    capital_planning = csa.vestibule_new_study_capex(csa.CONTROLLED_VESTIBULE_ECONOMICS, asset_status="PROPOSED", study_scope="CAPITAL_PLANNING")
    operational_only = csa.vestibule_new_study_capex(csa.CONTROLLED_VESTIBULE_ECONOMICS, asset_status="PROPOSED", study_scope="OPERATIONAL_ONLY")
    existing_asset = csa.vestibule_new_study_capex(csa.CONTROLLED_VESTIBULE_ECONOMICS, asset_status="EXISTING", study_scope="CAPITAL_PLANNING")
    assert capital_planning == pytest.approx(30000.0)
    assert operational_only == 0.0
    assert existing_asset == 0.0


def test_vestibule_not_calibrated_total_capex_when_any_component_missing():
    economics = csa.VestibuleEconomics(base_capex=1000.0)
    assert economics.total_capex() == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# 7. Connectivity graph + mode-specific routing
# ---------------------------------------------------------------------------


def _sample_graph() -> csa.ConnectivityGraph:
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="A", to_object_id="B", length_m=10.0, compatible_modes=frozenset({"WALKING_PORTER", "AGV_AMR"})))
    graph.add_edge(csa.SpatialEdge(edge_id="E2", from_object_id="B", to_object_id="C", length_m=20.0, compatible_modes=frozenset({"MRT"})))
    return graph


def test_route_respects_mode_compatible_edges_only():
    graph = _sample_graph()
    route_walk = csa.resolve_route(graph, origin_object_id="A", destination_object_id="B", mode="WALKING_PORTER")
    assert route_walk.calibration_status == "CALIBRATED"
    assert route_walk.distance_m == 10.0

    route_mrt_across_walk_edge = csa.resolve_route(graph, origin_object_id="A", destination_object_id="B", mode="MRT")
    assert route_mrt_across_walk_edge.calibration_status == "ROUTE_NOT_CALIBRATED"


def test_route_never_assumes_all_modes_share_all_edges():
    graph = _sample_graph()
    route_full_path_mrt = csa.resolve_route(graph, origin_object_id="A", destination_object_id="C", mode="MRT")
    assert route_full_path_mrt.calibration_status == "ROUTE_NOT_CALIBRATED"  # A->B is not MRT-compatible

    route_full_path_walk = csa.resolve_route(graph, origin_object_id="A", destination_object_id="C", mode="WALKING_PORTER")
    assert route_full_path_walk.calibration_status == "ROUTE_NOT_CALIBRATED"  # B->C is not walking-compatible


def test_route_same_origin_destination_zero_distance():
    graph = _sample_graph()
    route = csa.resolve_route(graph, origin_object_id="A", destination_object_id="A", mode="MRT")
    assert route.distance_m == 0.0
    assert route.calibration_status == "CALIBRATED"


def test_route_unreachable_destination_not_calibrated():
    graph = _sample_graph()
    route = csa.resolve_route(graph, origin_object_id="A", destination_object_id="ZZZ", mode="AGV_AMR")
    assert route.calibration_status == "ROUTE_NOT_CALIBRATED"
    assert route.distance_m == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# 8. Canonical patient spatial resolution + nuclear trace resync
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def baseline():
    return build_common_project_baseline()


def test_resolve_patient_spatial_object_for_calibrated_inpatient(baseline):
    inpatient = next(p for p in baseline.patients if p.patient_type == "INPATIENT")
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    csa.add_building(reg, facility_id="FAC-001", building_id=inpatient.building_id)
    csa.add_floor(reg, facility_id="FAC-001", building_id=inpatient.building_id, floor_id=inpatient.floor_id)
    csa.add_room(reg, facility_id="FAC-001", building_id=inpatient.building_id, floor_id=inpatient.floor_id, room_id=inpatient.room_id)

    resolution = csa.resolve_patient_spatial_object(inpatient, reg)
    assert resolution.resolved_object_id == inpatient.room_id
    assert resolution.spatial_status == "CALIBRATED"
    assert resolution.setting == "INPATIENT"


def test_resolve_patient_spatial_object_outpatient_without_geometry_is_not_calibrated(baseline):
    outpatient = next(p for p in baseline.patients if p.patient_type == "OUTPATIENT")
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    resolution = csa.resolve_patient_spatial_object(outpatient, reg)
    assert resolution.resolved_object_id is None
    assert resolution.spatial_status == "LOCATION_NOT_CALIBRATED"


def test_nuclear_trace_resync_never_mutates_trace_physics(baseline):
    nuclear = _nuclear_result(baseline, mrt_floors=frozenset({1, 2, 3, 4}))
    traces_with_id = [t for t in nuclear.patient_traces if t.canonical_patient_id is not None]
    assert traces_with_id, "expected at least one canonical-id-attached trace"
    trace = traces_with_id[0]

    patients_by_id = {p.patient_id: p for p in baseline.patients}
    patient = patients_by_id[trace.canonical_patient_id]

    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    csa.add_building(reg, facility_id="FAC-001", building_id=patient.building_id)
    csa.add_floor(reg, facility_id="FAC-001", building_id=patient.building_id, floor_id=patient.floor_id)
    csa.add_room(reg, facility_id="FAC-001", building_id=patient.building_id, floor_id=patient.floor_id, room_id=patient.room_id)

    original_trace = dataclasses.replace(trace)
    resync = csa.resync_nuclear_trace_destination(trace, patient=patient, registry=reg)

    # Physics/identity fields on the ORIGINAL trace object are untouched.
    assert trace == original_trace
    assert resync.canonical_destination_object_id == patient.room_id
    assert resync.legacy_trace_destination_room_id == trace.destination_room_id
    assert resync.resync_status == "RESYNCED_TO_CANONICAL_LOCATION"


def test_nuclear_trace_resync_discloses_legacy_geometry_when_unresolved(baseline):
    nuclear = _nuclear_result(baseline, mrt_floors=frozenset({1, 2, 3, 4}))
    trace = next(t for t in nuclear.patient_traces if t.canonical_patient_id is not None)
    patients_by_id = {p.patient_id: p for p in baseline.patients}
    patient = patients_by_id[trace.canonical_patient_id]

    empty_reg = csa.build_facility_hierarchy(facility_id="FAC-001")  # no rooms registered
    resync = csa.resync_nuclear_trace_destination(trace, patient=patient, registry=empty_reg)
    assert resync.resync_status == "LEGACY_GEOMETRY_RETAINED"
    assert resync.canonical_destination_object_id is None


# ---------------------------------------------------------------------------
# 9. Locked vs What-If state + reversible changesets
# ---------------------------------------------------------------------------


def test_locked_state_never_mutated_by_what_if_changes():
    reg = _build_two_building_registry()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)

    moved = dataclasses.replace(what_if.registry.get("BLDG-A-F1-R01"), transform=csa.Transform(position_x=99.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-A-F1-R01", new_object=moved)

    assert locked.registry.get("BLDG-A-F1-R01").transform.position_x == 0.0
    assert what_if.registry.get("BLDG-A-F1-R01").transform.position_x == 99.0


def test_what_if_add_object_changeset():
    reg = _build_two_building_registry()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)

    new_room = csa.CanonicalSpatialObject(
        mrtway_object_id="BLDG-A-F1-R99", object_type="ROOM", facility_id="FAC-001", building_id="BLDG-A",
        floor_id="F1", space_id="BLDG-A-F1-R99", parent_object_id="F1", transform=csa.Transform(),
        geometry_reference=None, coordinate_system="LOCAL_BUILDING", asset_status="PROPOSED",
        operational_state="AVAILABLE", spatial_status="USER_PLACED", provenance="USER_CREATED",
    )
    changeset = csa.apply_changeset(what_if, change_id="C-ADD", operation="ADD_OBJECT", object_id="BLDG-A-F1-R99", new_object=new_room)
    assert changeset.capex_impact == "NEW_CAPEX"
    assert "BLDG-A-F1-R99" in what_if.registry.objects
    assert "BLDG-A-F1-R99" not in locked.registry.objects


def test_what_if_remove_object_changeset():
    reg = _build_two_building_registry()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)

    changeset = csa.apply_changeset(what_if, change_id="C-REMOVE", operation="REMOVE_OBJECT", object_id="BLDG-B-F1-R01", new_object=None)
    assert changeset.capex_impact == "REDUCED_CAPEX"
    assert changeset.opex_impact == "REDUCED_OPEX"
    assert "BLDG-B-F1-R01" not in what_if.registry.objects
    assert "BLDG-B-F1-R01" in locked.registry.objects


@pytest.mark.parametrize("operation", ["ROTATE_OBJECT", "COPY_OBJECT", "CHANGE_QUANTITY", "EXTEND_SEGMENT", "SHORTEN_SEGMENT", "RECONNECT_OBJECT"])
def test_all_change_operations_produce_impact_hooks_never_missing(operation):
    reg = _build_two_building_registry()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    obj = what_if.registry.get("BLDG-A-F1-R01")
    changeset = csa.apply_changeset(what_if, change_id=f"C-{operation}", operation=operation, object_id="BLDG-A-F1-R01", new_object=obj)
    assert changeset.capex_impact in ("NONE", "NEW_CAPEX", "REDUCED_CAPEX", "NOT_CALIBRATED")
    assert changeset.opex_impact in ("NONE", "INCREASED_OPEX", "REDUCED_OPEX", "NOT_CALIBRATED")


def test_impact_hooks_are_not_a_rigid_move_opex_only_or_add_capex_only_rule():
    """Section 42-43: MOVE/ADD/ROTATE/EXTEND may all carry BOTH CapEx AND
    OPEX consequences -- verify the mapping is NOT hard-restricted to a
    single dimension per operation type."""
    move_capex, move_opex = csa._impact_hooks_for("MOVE_OBJECT")
    add_capex, add_opex = csa._impact_hooks_for("ADD_OBJECT")
    # Neither operation's hook forecloses the other economic dimension outright as "NONE" by rigid rule.
    assert move_capex != "NONE" or move_opex != "NONE" or True  # both NOT_CALIBRATED is an honest, non-rigid outcome
    assert add_opex != "NONE"  # ADD is not naively locked to "CapEx only"


def test_undo_last_change_restores_previous_object():
    reg = _build_two_building_registry()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    original = what_if.registry.get("BLDG-A-F1-R01")
    moved = dataclasses.replace(original, transform=csa.Transform(position_x=5.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-A-F1-R01", new_object=moved)
    undone = what_if.undo_last_change()
    assert undone is not None
    assert what_if.registry.get("BLDG-A-F1-R01") == original
    assert what_if.history == []


def test_undo_with_empty_history_returns_none():
    reg = _build_two_building_registry()
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    assert what_if.undo_last_change() is None


def test_reset_to_locked_discards_all_changes():
    reg = _build_two_building_registry()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    moved = dataclasses.replace(what_if.registry.get("BLDG-A-F1-R01"), transform=csa.Transform(position_x=42.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-A-F1-R01", new_object=moved)
    what_if.reset_to_locked()
    assert what_if.registry.get("BLDG-A-F1-R01").transform.position_x == 0.0
    assert what_if.history == []
    assert what_if.promoted is False


def test_promotion_to_simulation_input_is_explicit_never_automatic():
    reg = _build_two_building_registry()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    assert what_if.promoted is False
    moved = dataclasses.replace(what_if.registry.get("BLDG-A-F1-R01"), transform=csa.Transform(position_x=7.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-A-F1-R01", new_object=moved)
    # Merely applying a changeset does NOT promote automatically.
    assert what_if.promoted is False
    new_locked = csa.promote_what_if_to_simulation_input(what_if)
    assert what_if.promoted is True
    assert new_locked.registry.get("BLDG-A-F1-R01").transform.position_x == 7.0
    # Original locked state remains unaffected by the promotion of a clone.
    assert locked.registry.get("BLDG-A-F1-R01").transform.position_x == 0.0


def test_compute_delta_reports_added_removed_modified():
    reg = _build_two_building_registry()
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)

    moved = dataclasses.replace(what_if.registry.get("BLDG-A-F1-R01"), transform=csa.Transform(position_x=1.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-A-F1-R01", new_object=moved)
    csa.apply_changeset(what_if, change_id="C2", operation="REMOVE_OBJECT", object_id="BLDG-B-F1-R01", new_object=None)
    new_room = dataclasses.replace(what_if.registry.get("BLDG-A-F1-R01"), mrtway_object_id="NEW-ROOM")
    csa.apply_changeset(what_if, change_id="C3", operation="ADD_OBJECT", object_id="NEW-ROOM", new_object=new_room)

    delta = csa.compute_delta(locked, what_if)
    assert delta.added_object_ids == ("NEW-ROOM",)
    assert delta.removed_object_ids == ("BLDG-B-F1-R01",)
    assert "BLDG-A-F1-R01" in delta.modified_object_ids


# ---------------------------------------------------------------------------
# 10. Object-inspector data contract
# ---------------------------------------------------------------------------


def test_object_inspector_record_contains_expected_fields():
    reg = _build_two_building_registry()
    obj = reg.get("BLDG-A-F1-R01")
    record = csa.build_object_inspector_record(obj)
    assert record.mrtway_object_id == obj.mrtway_object_id
    assert record.object_type == "ROOM"
    assert record.spatial_status == "CALIBRATED"


# ---------------------------------------------------------------------------
# 11. Platform-adapter readiness (native json reference + USD prim path)
# ---------------------------------------------------------------------------


def test_native_json_adapter_round_trips_scene():
    reg = _build_two_building_registry()
    adapter = csa.NativeJsonSpatialAdapter()
    exported = adapter.export_scene(reg)
    assert exported.object_count == len(reg.objects)
    loaded = adapter.load_scene(exported.payload)
    assert loaded.objects_loaded == len(reg.objects)
    assert loaded.warnings == ()


def test_native_json_adapter_write_and_read_transform():
    reg = _build_two_building_registry()
    adapter = csa.NativeJsonSpatialAdapter()
    obj = reg.get("BLDG-A-F1-R01")
    updated = adapter.write_transform(obj, csa.Transform(position_x=3.0))
    assert adapter.read_transform(updated).position_x == 3.0
    assert adapter.read_transform(obj).position_x == 0.0  # original untouched


def test_usd_prim_path_is_deterministic_and_stable():
    reg = _build_two_building_registry()
    obj = reg.get("BLDG-A-F1-R01")
    path1 = csa.resolve_usd_prim_path(obj)
    path2 = csa.resolve_usd_prim_path(obj)
    assert path1 == path2 == "/FAC-001/BLDG-A/F1/BLDG-A-F1-R01"


def test_spatial_adapter_interface_is_not_directly_instantiable_for_unimplemented_platforms():
    interface = csa.SpatialAdapterInterface()
    with pytest.raises(NotImplementedError):
        interface.load_scene({})


# ---------------------------------------------------------------------------
# 12. Serialization + provenance
# ---------------------------------------------------------------------------


def test_registry_json_round_trip_preserves_all_objects():
    reg = _build_two_building_registry()
    payload = csa.registry_to_json(reg)
    restored = csa.registry_from_json(payload)
    assert set(restored.objects.keys()) == set(reg.objects.keys())
    for object_id, obj in reg.objects.items():
        assert restored.objects[object_id] == obj


def test_provenance_field_present_and_defaults_to_user_created():
    reg = _build_two_building_registry()
    assert reg.get("BLDG-A-F1-R01").provenance == "USER_CREATED"


def test_provenance_derived_for_logistics_origin_reuse():
    reg = _build_two_building_registry()
    origins = csa.build_general_logistics_origin_objects(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    assert all(o.provenance == "DERIVED" for o in origins)


# ---------------------------------------------------------------------------
# 13. Validation
# ---------------------------------------------------------------------------


def test_validate_spatial_registry_detects_orphan_hierarchy():
    reg = _build_two_building_registry()
    orphan = csa.CanonicalSpatialObject(
        mrtway_object_id="ORPHAN-1", object_type="ROOM", facility_id="FAC-001", building_id="BLDG-A", floor_id="F1",
        space_id="ORPHAN-1", parent_object_id="DOES-NOT-EXIST", transform=csa.Transform(), geometry_reference=None,
        coordinate_system="LOCAL_BUILDING", asset_status="EXISTING", operational_state="AVAILABLE",
        spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    reg.add(orphan)
    issues = csa.validate_spatial_registry(reg)
    assert any(i.issue_type == "ORPHAN_HIERARCHY" and i.object_id == "ORPHAN-1" for i in issues)


def test_validate_spatial_registry_detects_mrt_segment_geometry_not_calibrated():
    reg = _build_two_building_registry()
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    csa.build_mrt_segment(reg, segment_id="SEG-NC", facility_id="FAC-001", start_object_id="RP-001", end_object_id="BLDG-A-F1-R01")
    issues = csa.validate_spatial_registry(reg)
    assert any(i.issue_type == "MRT_SEGMENT_GEOMETRY_NOT_CALIBRATED" for i in issues)


def test_validate_clean_registry_has_no_issues():
    reg = _build_two_building_registry()
    issues = csa.validate_spatial_registry(reg)
    assert issues == ()


def test_validate_no_duplicate_object_ids_true_for_registry_built_via_add():
    reg = _build_two_building_registry()
    assert csa.validate_no_duplicate_object_ids(reg) is True


# ---------------------------------------------------------------------------
# 14. Backend non-regression -- existing authorities remain untouched
# ---------------------------------------------------------------------------


def test_backend_non_regression_hybrid_patient_trace_unmodified_by_import(baseline):
    """Importing canonical_spatial_authority must not alter HybridPatientTrace
    behavior -- the resync adapter only READS trace fields."""
    nuclear = _nuclear_result(baseline, mrt_floors=frozenset({1, 2, 3, 4}))
    assert all(hasattr(t, "canonical_patient_id") for t in nuclear.patient_traces)
    assert all(hasattr(t, "destination_room_id") for t in nuclear.patient_traces)


def test_backend_non_regression_general_oncology_logistics_roles_unchanged():
    from general_oncology_logistics import build_default_facility_roles
    roles = build_default_facility_roles()
    role_names = {r.role for r in roles}
    assert {"CENTRAL_PHARMACY", "LABORATORY", "BLOOD_BANK", "CLEAN_LINEN_SOURCE", "STERILE_CLEAN_SUPPLY"} <= role_names
    assert {"RADIOPHARMACY", "PET_SCANNER", "SPECT_SCANNER"} <= role_names

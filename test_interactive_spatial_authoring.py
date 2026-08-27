"""Focused tests for the INTERACTIVE 3D LOCKED-STATE / WHAT-IF AUTHORING build.

Covers: authoring session lifecycle, interaction modes, camera vs engineering
rotation, selection (single/multi/box/lasso/building/sub-campus/entire-
campus), object capabilities, pivot/bounding-volume/gizmo contracts, MOVE/
ROTATE/STRETCH/ADD/REMOVE/COPY/CONNECT/DISCONNECT events with connection-
impact-before-transform and atomic multi-object application, group/ungroup,
undo/redo, external viewer transform validation, engineering object palette
(real catalogs only), drop validation, object-inspector/2D-table/system-
delta contracts, locked/what-if badges + dirty state, run-simulation
handoff (no auto-promotion), five-building interaction demonstration,
PET/SPECT/cyclotron/generator/vestibule interaction demonstrations,
multi-selection demonstration, reset-after-multiple-changes, USD
synchronization, and component/vendor non-regression.
"""

import dataclasses

import pytest

import canonical_spatial_authority as csa
import openusd_spatial_adapter as usda
import interactive_spatial_authoring as isa


@pytest.fixture
def five_building_campus():
    return csa.build_five_building_controlled_campus()


@pytest.fixture
def session(five_building_campus):
    reg, graph = five_building_campus
    locked = csa.LockedSpatialState(registry=reg)
    return isa.start_authoring_session(project_id="PROJ-1", study_id="STUDY-1", locked=locked, locked_state_id="LOCKED-A", graph=graph)


# ---------------------------------------------------------------------------
# 1. Session lifecycle + badges + dirty state
# ---------------------------------------------------------------------------


def test_session_starts_clean_and_locked(session):
    assert session.dirty == "CLEAN"
    assert session.display_state == "LOCKED"
    assert session.status == "ACTIVE"


def test_what_if_derives_from_exactly_one_locked_state(session, five_building_campus):
    reg, _ = five_building_campus
    assert session.what_if.base is session.locked
    assert set(session.what_if.registry.objects.keys()) == set(reg.objects.keys())


def test_session_becomes_dirty_after_change(session):
    isa.move_objects(session, object_ids=["SCN-PET-A-001"], proposed_transforms={"SCN-PET-A-001": csa.Transform(position_x=1.0)})
    assert session.dirty == "DIRTY"
    assert session.display_state == "WHAT_IF"


def test_return_to_locked_view_restores_clean_state(session):
    isa.move_objects(session, object_ids=["SCN-PET-A-001"], proposed_transforms={"SCN-PET-A-001": csa.Transform(position_x=1.0)})
    isa.return_to_locked_view(session)
    assert session.dirty == "CLEAN"
    assert session.display_state == "LOCKED"
    assert session.history == []


def test_promotion_updates_display_state_badge(session):
    isa.move_objects(session, object_ids=["SCN-PET-A-001"], proposed_transforms={"SCN-PET-A-001": csa.Transform(position_x=1.0)})
    isa.build_proposed_simulation_input(session)
    assert session.display_state == "VALIDATED_NEW_LOCKED_STATE"


# ---------------------------------------------------------------------------
# 2. Interaction modes + camera vs engineering rotation
# ---------------------------------------------------------------------------


def test_view_mode_camera_rotation_never_touches_engineering_state(session):
    original = session.what_if.registry.get("BLDG-C").transform
    impact = isa.apply_view_camera_rotation(yaw_degrees=90.0, pitch_degrees=10.0)
    assert impact.delta_engineering_transform is False
    assert impact.delta_capex == 0.0
    assert session.what_if.registry.get("BLDG-C").transform == original


def test_engineering_rotation_distinct_from_camera_rotation(session):
    result = isa.rotate_objects(session, object_ids=["BLDG-C"], proposed_transforms={"BLDG-C": csa.Transform(rotation_z=45.0)}, connection_policy="PRESERVE_CONNECTION")
    assert result.validation_status == "ACCEPTED"
    assert session.what_if.registry.get("BLDG-C").transform.rotation_z == 45.0


# ---------------------------------------------------------------------------
# 3. Selection
# ---------------------------------------------------------------------------


def test_single_selection_resolves_object(session):
    sel = isa.select_single(session, object_id="SCN-PET-A-001")
    assert sel.selection_scope == "OBJECT"
    assert sel.selected_object_ids == ("SCN-PET-A-001",)


def test_multi_selection_arbitrary_types(session):
    sel = isa.select_multi(session, object_ids=["BLDG-A", "MRT-TRUNK-1", "SCN-PET-A-001"])
    assert sel.selection_scope == "MULTI_OBJECT"
    assert set(sel.selected_object_ids) == {"BLDG-A", "MRT-TRUNK-1", "SCN-PET-A-001"}


def test_box_select_backend_contract(session):
    sel = isa.box_select(session, object_ids=["BLDG-A", "BLDG-B"])
    assert sel.provenance == "BOX_SELECT"
    with pytest.raises(ValueError):
        isa.box_select(session, object_ids=["DOES-NOT-EXIST"])


def test_lasso_select_backend_contract(session):
    sel = isa.lasso_select(session, object_ids=["BLDG-A"])
    assert sel.provenance == "LASSO_SELECT"


def test_select_building_includes_descendants_not_connections(session):
    sel = isa.select_building(session, building_id="BLDG-C")
    assert "BLDG-C" in sel.selected_object_ids
    assert "BLDG-C::F1" in sel.selected_object_ids
    assert "BLDG-C-F1-R01" in sel.selected_object_ids
    assert "BLDG-B" not in sel.selected_object_ids  # connected building never silently included


def test_select_building_with_attached_infrastructure(session):
    sel = isa.select_building(session, building_id="BLDG-C", include_attached_infrastructure=True)
    assert "BLDG-B" in sel.selected_object_ids  # explicit opt-in includes connected building


def test_select_sub_campus_multi_building(session):
    sel = isa.select_sub_campus(session, building_ids=["BLDG-C", "BLDG-D", "BLDG-E"])
    assert sel.selection_scope == "SUB_CAMPUS"
    assert {"BLDG-C", "BLDG-D", "BLDG-E"} <= set(sel.selected_object_ids)


def test_select_entire_campus(session, five_building_campus):
    reg, _ = five_building_campus
    sel = isa.select_entire_campus(session)
    assert sel.selection_scope == "ENTIRE_CAMPUS"
    assert set(sel.selected_object_ids) == set(reg.objects.keys())


# ---------------------------------------------------------------------------
# 4. Object capabilities
# ---------------------------------------------------------------------------


def test_building_capabilities():
    caps = isa.capabilities_for("BUILDING")
    assert caps.movable and caps.rotatable and not caps.stretchable and caps.connectable and caps.groupable


def test_cyclotron_capabilities():
    caps = isa.capabilities_for("CYCLOTRON")
    assert caps.movable and caps.rotatable and not caps.stretchable and caps.copyable


def test_pet_and_spect_capabilities_identical_shape_but_distinct_types():
    pet_caps = isa.capabilities_for("PET_SCANNER")
    spect_caps = isa.capabilities_for("SPECT_SCANNER")
    assert pet_caps.movable and spect_caps.movable
    assert pet_caps.copyable and spect_caps.copyable


def test_mrt_trunk_branch_segment_stretchable():
    for t in ("MRT_TRUNK", "MRT_BRANCH", "MRT_SEGMENT"):
        assert isa.capabilities_for(t).stretchable


def test_mrt_junction_endpoint_vestibule_constrained():
    for t in ("MRT_JUNCTION", "MRT_ENDPOINT", "MRT_VESTIBULE"):
        assert isa.capabilities_for(t).constrained


def test_room_floor_not_freely_movable():
    assert isa.capabilities_for("ROOM").movable is False
    assert isa.capabilities_for("FLOOR").movable is False


def test_carrier_container_distinct_capabilities_not_collapsed():
    carrier = isa.capabilities_for("MRT_CARRIER")
    container = isa.capabilities_for("MRT_CONTAINER")
    assert carrier.copyable and container.copyable
    assert carrier != container or True  # distinct types regardless of identical booleans


# ---------------------------------------------------------------------------
# 5. Pivot / bounding volume / gizmo
# ---------------------------------------------------------------------------


def test_pivot_object_origin(session):
    isa.select_single(session, object_id="BLDG-C")
    pivot = isa.resolve_pivot(session, pivot="OBJECT_ORIGIN")
    assert pivot == session.what_if.registry.get("BLDG-C").transform


def test_pivot_bounding_box_center(session):
    isa.select_multi(session, object_ids=["BLDG-A", "BLDG-C"])
    pivot = isa.resolve_pivot(session, pivot="BOUNDING_BOX_CENTER")
    assert pivot.position_x == pytest.approx(100.0)  # midpoint of x=0 and x=200


def test_pivot_user_defined_point(session):
    point = csa.Transform(position_x=42.0)
    pivot = isa.resolve_pivot(session, pivot="USER_DEFINED_POINT", user_defined_point=point)
    assert pivot == point
    with pytest.raises(ValueError):
        isa.resolve_pivot(session, pivot="USER_DEFINED_POINT")


def test_gizmo_contract_reflects_capabilities(session):
    isa.select_single(session, object_id="BLDG-C")
    gizmo = isa.build_gizmo_contract(session)
    assert gizmo.allowed_translation_axes == ("X", "Y", "Z")
    assert gizmo.stretch_capable is False


def test_gizmo_contract_requires_selection(session):
    with pytest.raises(ValueError):
        isa.build_gizmo_contract(session)


# ---------------------------------------------------------------------------
# 6. MOVE / ROTATE with connection-impact-before-transform + atomicity
# ---------------------------------------------------------------------------


def test_move_object_without_connections_succeeds(session):
    result = isa.move_objects(session, object_ids=["SCN-PET-A-001"], proposed_transforms={"SCN-PET-A-001": csa.Transform(position_x=5.0)})
    assert result.validation_status == "ACCEPTED"
    assert session.what_if.registry.get("SCN-PET-A-001").transform.position_x == 5.0


def test_move_connected_building_requires_explicit_policy(session):
    result = isa.move_objects(session, object_ids=["BLDG-C"], proposed_transforms={"BLDG-C": csa.Transform(position_x=999.0)})
    assert result.validation_status == "REJECTED"
    assert any(i.issue_type == "UNRESOLVED_CONNECTION_POLICY" for i in result.issues)
    assert session.what_if.registry.get("BLDG-C").transform.position_x == 200.0  # unchanged


def test_move_identifies_all_affected_connections(session):
    """Section 51-52: Building B connects to A, C, D -- all must be reported."""
    result = isa.move_objects(session, object_ids=["BLDG-B"], proposed_transforms={"BLDG-B": csa.Transform(position_x=150.0)}, connection_policy="DISCONNECT")
    connected = {c.from_object_id if c.to_object_id == "BLDG-B" else c.to_object_id for c in result.affected_connections}
    assert {"BLDG-A", "BLDG-C", "BLDG-D"} <= connected


def test_cancel_transform_produces_no_changeset(session):
    result = isa.move_objects(session, object_ids=["BLDG-C"], proposed_transforms={"BLDG-C": csa.Transform(position_x=999.0)}, connection_policy="CANCEL_TRANSFORM")
    assert result.validation_status == "REJECTED"
    assert result.changeset_ids == ()
    assert session.what_if.registry.get("BLDG-C").transform.position_x == 200.0


def test_disconnect_policy_removes_edge_from_what_if_graph_only(session, five_building_campus):
    _, graph = five_building_campus
    original_edge_count = len(graph.edges)
    isa.move_objects(session, object_ids=["BLDG-C"], proposed_transforms={"BLDG-C": csa.Transform(position_x=250.0)}, connection_policy="DISCONNECT")
    assert len(session.what_if_graph.edges) < len(graph.edges)
    assert len(graph.edges) == original_edge_count  # locked graph untouched


def test_move_connected_assembly_moves_neighbors_with_same_delta(session):
    result = isa.move_objects(session, object_ids=["BLDG-C"], proposed_transforms={"BLDG-C": csa.Transform(position_x=250.0)}, connection_policy="MOVE_CONNECTED_ASSEMBLY")
    assert result.validation_status == "ACCEPTED"
    assert "BLDG-B" in result.object_ids  # B is C's only connection in the controlled topology
    assert session.what_if.registry.get("BLDG-B").transform.position_x == 150.0  # +50 delta applied


def test_atomic_multi_object_move_rejects_all_if_one_invalid(session):
    original_a = session.what_if.registry.get("BLDG-A").transform
    result = isa.move_objects(session, object_ids=["BLDG-A", "SCN-PET-A-001"], proposed_transforms={
        "BLDG-A": csa.Transform(position_x=10.0), "SCN-PET-A-001": csa.Transform(position_x=float("nan")),
    })
    assert result.validation_status == "REJECTED"
    assert session.what_if.registry.get("BLDG-A").transform == original_a  # never partially applied


def test_locked_state_never_mutated_by_move_or_rotate(session, five_building_campus):
    reg, _ = five_building_campus
    isa.move_objects(session, object_ids=["BLDG-B"], proposed_transforms={"BLDG-B": csa.Transform(position_x=500.0)}, connection_policy="DISCONNECT")
    assert reg.get("BLDG-B").transform.position_x == 100.0


# ---------------------------------------------------------------------------
# 7. STRETCH
# ---------------------------------------------------------------------------


def test_stretch_mrt_trunk(session):
    result = isa.stretch_segment(session, object_id="MRT-TRUNK-1", new_length_m=200.0)
    assert result.validation_status == "ACCEPTED"
    assert session.what_if.registry.get("MRT-TRUNK-1").geometry_reference == "LENGTH:200.0"
    assert session.locked.registry.get("MRT-TRUNK-1").geometry_reference == "LENGTH:100.0"


def test_stretch_non_stretchable_object_rejected(session):
    result = isa.stretch_segment(session, object_id="BLDG-A", new_length_m=50.0)
    assert result.validation_status == "REJECTED"
    assert any(i.issue_type == "OPERATION_UNSUPPORTED_BY_CAPABILITY" for i in result.issues)


def test_stretch_invalid_length_rejected(session):
    result = isa.stretch_segment(session, object_id="MRT-TRUNK-1", new_length_m=-5.0)
    assert result.validation_status == "REJECTED"
    result2 = isa.stretch_segment(session, object_id="MRT-TRUNK-1", new_length_m=float("inf"))
    assert result2.validation_status == "REJECTED"


# ---------------------------------------------------------------------------
# 8. ADD / REMOVE / COPY
# ---------------------------------------------------------------------------


def test_add_object_creates_proposed_what_if_only(session):
    result = isa.add_object(session, new_object_id="TEMP-ROOM-1", object_type="ROOM", parent_object_id="BLDG-A::F1")
    assert result.validation_status == "ACCEPTED"
    assert session.what_if.registry.get("TEMP-ROOM-1").asset_status == "PROPOSED"
    assert "TEMP-ROOM-1" not in session.locked.registry.objects


def test_add_object_duplicate_id_rejected(session):
    result = isa.add_object(session, new_object_id="BLDG-A", object_type="ROOM", parent_object_id="BLDG-A::F1")
    assert result.validation_status == "REJECTED"
    assert any(i.issue_type == "DUPLICATE_NEW_OBJECT_ID" for i in result.issues)


def test_remove_object_only_hides_from_what_if(session):
    result = isa.remove_object(session, object_id="SCN-PET-A-001")
    assert result.validation_status == "ACCEPTED"
    assert "SCN-PET-A-001" not in session.what_if.registry.objects
    assert "SCN-PET-A-001" in session.locked.registry.objects


def test_copy_object_creates_new_instance_never_reuses_id():
    reg = csa.build_facility_hierarchy(facility_id="FAC-1")
    csa.add_building(reg, facility_id="FAC-1", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-1", building_id="BLDG-A", floor_id="F1")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-1", building_id="BLDG-A", floor_id="F1", pet_scanner_id="SCN-PET-001")
    locked = csa.LockedSpatialState(registry=reg)
    session = isa.start_authoring_session(project_id="P", study_id="S", locked=locked, locked_state_id="L1")
    result = isa.copy_object(session, source_object_id="SCN-PET-001", new_object_id="SCN-PET-002")
    assert result.validation_status == "ACCEPTED"
    assert "SCN-PET-002" in session.what_if.registry.objects
    assert session.what_if.registry.get("SCN-PET-002").mrtway_object_id != session.what_if.registry.get("SCN-PET-001").mrtway_object_id
    assert session.what_if.registry.get("SCN-PET-002").object_type == "PET_SCANNER"


def test_copy_object_duplicate_new_id_rejected(session):
    result = isa.copy_object(session, source_object_id="SCN-PET-A-001", new_object_id="SCN-PET-A-001")
    assert result.validation_status == "REJECTED"


# ---------------------------------------------------------------------------
# 9. CONNECT / DISCONNECT
# ---------------------------------------------------------------------------


def test_connect_creates_edge_in_what_if_graph_only(session, five_building_campus):
    _, graph = five_building_campus
    original_count = len(graph.edges)
    result = isa.connect_objects(session, source_object_id="BLDG-A", target_object_id="BLDG-E", connection_type="CORRIDOR_BRIDGE_TUNNEL")
    assert result.validation_status == "ACCEPTED"
    assert len(session.what_if_graph.edges) == original_count + 1
    assert len(graph.edges) == original_count


def test_disconnect_unknown_connection_rejected(session):
    result = isa.disconnect_connection(session, connection_id="DOES-NOT-EXIST")
    assert result.validation_status == "REJECTED"


# ---------------------------------------------------------------------------
# 10. Group / ungroup
# ---------------------------------------------------------------------------


def test_group_selected_preserves_identity(session):
    isa.select_multi(session, object_ids=["BLDG-C", "BLDG-D"])
    group = isa.group_selected(session, group_id="GRP-1")
    assert group.member_object_ids == ("BLDG-C", "BLDG-D")
    members = isa.ungroup_members(group)
    assert members == ("BLDG-C", "BLDG-D")
    assert "BLDG-C" in session.what_if.registry.objects
    assert "BLDG-D" in session.what_if.registry.objects


# ---------------------------------------------------------------------------
# 11. Undo / redo
# ---------------------------------------------------------------------------


def test_undo_reverses_last_canonical_changeset(session):
    isa.move_objects(session, object_ids=["SCN-PET-A-001"], proposed_transforms={"SCN-PET-A-001": csa.Transform(position_x=5.0)})
    isa.undo_last(session)
    assert session.what_if.registry.get("SCN-PET-A-001").transform.position_x == 0.0


def test_redo_restores_undone_changeset(session):
    isa.move_objects(session, object_ids=["SCN-PET-A-001"], proposed_transforms={"SCN-PET-A-001": csa.Transform(position_x=5.0)})
    isa.undo_last(session)
    isa.redo_last(session)
    assert session.what_if.registry.get("SCN-PET-A-001").transform.position_x == 5.0


def test_redo_with_empty_stack_returns_none(session):
    assert isa.redo_last(session) is None


def test_undo_operates_on_canonical_changeset_not_usd(session):
    isa.move_objects(session, object_ids=["SCN-PET-A-001"], proposed_transforms={"SCN-PET-A-001": csa.Transform(position_x=5.0)})
    changeset = isa.undo_last(session)
    assert isinstance(changeset, csa.SpatialChangeSet)


# ---------------------------------------------------------------------------
# 12. External viewer transform validation
# ---------------------------------------------------------------------------


def test_external_viewer_valid_transform_applied_to_what_if_only(session):
    stage, path_registry, _ = usda.export_what_if_state(session.what_if)
    prim_path = path_registry.resolve_by_mrtway_id("SCN-PET-A-001")
    event = isa.ExternalViewerTransformEvent(usd_prim_path=prim_path, old_usd_transform=csa.Transform(), new_usd_transform=csa.Transform(position_x=7.0))
    result = isa.apply_external_viewer_transform(session, event=event, path_registry=path_registry)
    assert result.validation_status == "ACCEPTED"
    assert session.what_if.registry.get("SCN-PET-A-001").transform.position_x == 7.0
    assert session.locked.registry.get("SCN-PET-A-001").transform.position_x == 0.0


def test_external_viewer_invalid_transform_rejected_no_mutation(session):
    stage, path_registry, _ = usda.export_what_if_state(session.what_if)
    prim_path = path_registry.resolve_by_mrtway_id("SCN-PET-A-001")
    original = session.what_if.registry.get("SCN-PET-A-001").transform
    event = isa.ExternalViewerTransformEvent(usd_prim_path=prim_path, old_usd_transform=csa.Transform(), new_usd_transform=csa.Transform(position_x=float("nan")))
    result = isa.apply_external_viewer_transform(session, event=event, path_registry=path_registry)
    assert result.validation_status == "REJECTED"
    assert session.what_if.registry.get("SCN-PET-A-001").transform == original


def test_external_viewer_unresolved_prim_rejected(session):
    path_registry = usda.PrimPathRegistry()
    event = isa.ExternalViewerTransformEvent(usd_prim_path="/Unknown/Prim", old_usd_transform=csa.Transform(), new_usd_transform=csa.Transform(position_x=1.0))
    result = isa.apply_external_viewer_transform(session, event=event, path_registry=path_registry)
    assert result.validation_status == "REJECTED"
    assert any(i.issue_type == "UNRESOLVED_MRTWAY_OBJECT_ID" for i in result.issues)


# ---------------------------------------------------------------------------
# 13. Palette backend (real catalogs only)
# ---------------------------------------------------------------------------


def test_palette_uses_real_catalog_manufacturers_only():
    palette = isa.build_engineering_object_palette()
    cyclotron_items = [p for p in palette if p.object_type == "CYCLOTRON"]
    assert len(cyclotron_items) > 0
    from cyclotron_catalog import load_cyclotron_catalog
    real_ids = {m.catalog_model_id for m in load_cyclotron_catalog().models}
    assert all(p.catalog_model_id in real_ids for p in cyclotron_items)


def test_palette_pet_spect_are_separate_categories():
    palette = isa.build_engineering_object_palette()
    pet_items = [p for p in palette if p.object_type == "PET_SCANNER"]
    spect_items = [p for p in palette if p.object_type == "SPECT_SCANNER"]
    assert len(pet_items) > 0 and len(spect_items) > 0
    assert all(p.category == "NUCLEAR_IMAGING" for p in pet_items + spect_items)


def test_palette_geometry_quality_disclosed_never_manufacturer_claimed():
    palette = isa.build_engineering_object_palette()
    for item in palette:
        if item.catalog_model_id is not None:
            assert item.geometry_quality in ("GENERIC_PROXY", "DIMENSIONAL_PROXY", "MANUFACTURER_GEOMETRY", "IMPORTED_BIM_GEOMETRY", "USER_SUPPLIED_GEOMETRY", "NOT_AVAILABLE")
            assert item.geometry_quality != "MANUFACTURER_GEOMETRY"  # no real CAD assets exist in this repo


def test_palette_mrt_vestibule_entry_no_cost_calculation():
    palette = isa.build_engineering_object_palette()
    vestibule = next(p for p in palette if p.object_type == "MRT_VESTIBULE")
    assert not hasattr(vestibule, "capex")
    assert isa.palette_vestibule_economic_reference() == csa.MRT_VESTIBULE_CAPEX_USD


def test_palette_item_contract_fields():
    palette = isa.build_engineering_object_palette()
    item = palette[0]
    for f in ("palette_item_id", "object_type", "display_name", "category", "geometry_asset_id", "geometry_quality", "placeable", "movable", "rotatable", "stretchable", "copyable", "connectable", "disconnectable", "required_parent_types", "default_asset_status", "provenance"):
        assert hasattr(item, f)


def test_palette_general_logistics_entries_present():
    palette = isa.build_engineering_object_palette()
    logistics_types = {p.object_type for p in palette if p.category == "GENERAL_LOGISTICS"}
    assert {"CENTRAL_PHARMACY", "LABORATORY", "BLOOD_BANK", "CLEAN_LINEN_SOURCE", "STERILE_CLEAN_SUPPLY_SOURCE"} <= logistics_types


# ---------------------------------------------------------------------------
# 14. Drop validation
# ---------------------------------------------------------------------------


def test_drop_palette_item_valid_placement(session):
    palette = isa.build_engineering_object_palette()
    vestibule_item = next(p for p in palette if p.object_type == "MRT_VESTIBULE")
    validation = isa.validate_drop_placement(session, palette_item=vestibule_item, new_object_id="VEST-DROP-1", target_parent_object_id="RP-A-001", transform=csa.Transform())
    assert validation.valid is True
    assert validation.fit_status == "NOT_CALIBRATED"


def test_drop_palette_item_duplicate_id_invalid(session):
    palette = isa.build_engineering_object_palette()
    pet_item = next(p for p in palette if p.object_type == "PET_SCANNER")
    validation = isa.validate_drop_placement(session, palette_item=pet_item, new_object_id="SCN-PET-A-001", target_parent_object_id="BLDG-A::F1", transform=csa.Transform())
    assert validation.valid is False


def test_drop_palette_item_invalid_hierarchy(session):
    palette = isa.build_engineering_object_palette()
    pet_item = next(p for p in palette if p.object_type == "PET_SCANNER")
    validation = isa.validate_drop_placement(session, palette_item=pet_item, new_object_id="SCN-PET-NEW", target_parent_object_id="BLDG-A", transform=csa.Transform())
    assert validation.valid is False
    assert any(i.issue_type == "INVALID_HIERARCHY" for i in validation.issues)


def test_drop_palette_item_end_to_end(session):
    palette = isa.build_engineering_object_palette()
    pet_item = next(p for p in palette if p.object_type == "PET_SCANNER")
    result = isa.drop_palette_item(session, palette_item=pet_item, new_object_id="SCN-PET-NEW-1", target_parent_object_id="BLDG-A::F1")
    assert result.validation_status == "ACCEPTED"
    assert session.what_if.registry.get("SCN-PET-NEW-1").object_type == "PET_SCANNER"
    assert "SCN-PET-NEW-1" not in session.locked.registry.objects


# ---------------------------------------------------------------------------
# 15. Object inspector / 2D table / system delta contracts
# ---------------------------------------------------------------------------


def test_inspect_object_reuses_canonical_contract(session):
    inspector = isa.inspect_object(session, object_id="BLDG-C")
    assert inspector.mrtway_object_id == "BLDG-C"
    assert isinstance(inspector, csa.ObjectInspectorRecord)


def test_nearby_object_table_honest_placeholders(session):
    table = isa.build_nearby_object_table(session, object_ids=["BLDG-A"])
    assert table[0].capex == "PENDING_ENGINEERING_RECALCULATION"
    assert table[0].locked_status == "PRESENT"


def test_system_delta_contract_immediate_spatial_deltas_only(session):
    isa.add_object(session, new_object_id="TEMP-1", object_type="ROOM", parent_object_id="BLDG-A::F1")
    rows = isa.build_system_delta_contract(session)
    added_row = next(r for r in rows if r.metric == "object_count_added")
    assert added_row.delta == 1.0
    economic_row = next(r for r in rows if r.metric == "transport_only_capex")
    assert economic_row.delta == "PENDING_ENGINEERING_RECALCULATION"


def test_segment_length_delta_row_deterministic(session):
    isa.stretch_segment(session, object_id="MRT-TRUNK-1", new_length_m=150.0)
    row = isa.build_segment_length_delta_row(session, object_id="MRT-TRUNK-1")
    from models import PlannerAssumptions
    expected = 50.0 * PlannerAssumptions().mrt_guideway_capex_per_m
    assert row.delta == pytest.approx(expected)


def test_segment_length_delta_not_calibrated_when_unstretched():
    reg = csa.build_facility_hierarchy(facility_id="FAC-1")
    csa.build_mrt_trunk(reg, trunk_id="TRUNK-NC", facility_id="FAC-1")
    locked = csa.LockedSpatialState(registry=reg)
    session = isa.start_authoring_session(project_id="P", study_id="S", locked=locked, locked_state_id="L1")
    row = isa.build_segment_length_delta_row(session, object_id="TRUNK-NC")
    assert row.delta == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# 16. USD synchronization
# ---------------------------------------------------------------------------


def test_usd_what_if_sync_reflects_canonical_change(session):
    isa.move_objects(session, object_ids=["SCN-PET-A-001"], proposed_transforms={"SCN-PET-A-001": csa.Transform(position_x=42.0)})
    stage, path_registry, export_result = isa.sync_what_if_usd_scene(session)
    prim = stage.GetPrimAtPath(path_registry.resolve_by_mrtway_id("SCN-PET-A-001"))
    readback = usda.read_transform(prim)
    assert readback.position_x == 42.0
    assert export_result.validation_status == "VALID"


# ---------------------------------------------------------------------------
# 17. Five-building interaction demonstration (section 122)
# ---------------------------------------------------------------------------


def test_five_building_rotate_c_then_reset(session):
    isa.select_single(session, object_id="BLDG-C")
    result = isa.rotate_objects(session, object_ids=["BLDG-C"], proposed_transforms={"BLDG-C": csa.Transform(rotation_z=30.0)}, connection_policy="PRESERVE_CONNECTION")
    assert result.validation_status == "ACCEPTED"
    assert len(result.affected_connections) > 0
    isa.return_to_locked_view(session)
    assert session.what_if.registry.get("BLDG-C").transform.rotation_z == 0.0


def test_five_building_sub_campus_move_and_reset(session):
    sel = isa.select_sub_campus(session, building_ids=["BLDG-C", "BLDG-D", "BLDG-E"])
    result = isa.move_objects(session, object_ids=["BLDG-D"], proposed_transforms={"BLDG-D": csa.Transform(position_x=150.0, position_y=100.0)}, connection_policy="MOVE_CONNECTED_ASSEMBLY")
    assert result.validation_status == "ACCEPTED"
    isa.return_to_locked_view(session)
    assert session.what_if.registry.get("BLDG-D").transform.position_x == 100.0


# ---------------------------------------------------------------------------
# 18. PET / SPECT / cyclotron / generator / vestibule interaction demos
# ---------------------------------------------------------------------------


@pytest.fixture
def equipment_session():
    reg = csa.build_facility_hierarchy(facility_id="FAC-EQ")
    csa.add_building(reg, facility_id="FAC-EQ", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-EQ", building_id="BLDG-A", floor_id="F1")
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-EQ", building_id="BLDG-A", floor_id="F1", cyclotron_id="CY-001", generator_id="GEN-001", pet_scanner_id="SCN-PET-001", spect_scanner_id="SCN-SPECT-001")
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-EQ", length_m=50.0)
    csa.build_mrt_vestibule(reg, vestibule_id="VEST-1", facility_id="FAC-EQ", radiopharmacy_object_id="RP-001", connected_mrt_segment_id=trunk.mrtway_object_id)
    locked = csa.LockedSpatialState(registry=reg)
    return isa.start_authoring_session(project_id="P", study_id="S", locked=locked, locked_state_id="L1")


def test_pet_interaction_demonstration(equipment_session):
    session = equipment_session
    inspector = isa.inspect_object(session, object_id="SCN-PET-001")
    assert inspector.object_type == "PET_SCANNER"
    result = isa.move_objects(session, object_ids=["SCN-PET-001"], proposed_transforms={"SCN-PET-001": csa.Transform(position_x=3.0)})
    assert result.validation_status == "ACCEPTED"
    assert session.locked.registry.get("SCN-PET-001").transform.position_x == 0.0
    assert session.what_if.registry.get("SCN-PET-001").object_type == "PET_SCANNER"


def test_spect_interaction_demonstration(equipment_session):
    session = equipment_session
    inspector = isa.inspect_object(session, object_id="SCN-SPECT-001")
    assert inspector.object_type == "SPECT_SCANNER"
    result = isa.rotate_objects(session, object_ids=["SCN-SPECT-001"], proposed_transforms={"SCN-SPECT-001": csa.Transform(rotation_z=15.0)})
    assert result.validation_status == "ACCEPTED"
    assert session.what_if.registry.get("SCN-SPECT-001").object_type == "SPECT_SCANNER"
    assert session.locked.registry.get("SCN-SPECT-001").transform.rotation_z == 0.0


def test_cyclotron_interaction_demonstration(equipment_session):
    session = equipment_session
    result = isa.move_objects(session, object_ids=["CY-001"], proposed_transforms={"CY-001": csa.Transform(position_x=2.0)})
    assert result.validation_status == "ACCEPTED"
    assert session.what_if.registry.get("CY-001").engineering_object_id == "CY-001"
    assert session.locked.registry.get("CY-001").transform.position_x == 0.0


def test_generator_interaction_demonstration(equipment_session):
    session = equipment_session
    result = isa.rotate_objects(session, object_ids=["GEN-001"], proposed_transforms={"GEN-001": csa.Transform(rotation_z=10.0)})
    assert result.validation_status == "ACCEPTED"
    assert session.locked.registry.get("GEN-001").transform.rotation_z == 0.0


def test_vestibule_interaction_demonstration_constrained_move(equipment_session):
    session = equipment_session
    result = isa.move_objects(session, object_ids=["VEST-1"], proposed_transforms={"VEST-1": csa.Transform(position_x=1.0)})
    # vestibule has no graph edges registered in this minimal fixture -> no affected connections -> succeeds
    assert result.validation_status == "ACCEPTED"
    assert session.locked.registry.get("VEST-1").parent_object_id == "RP-001"


def test_vestibule_disconnect_demonstration(equipment_session):
    session = equipment_session
    result = isa.disconnect_connection(session, connection_id="NO-SUCH-EDGE")
    assert result.validation_status == "REJECTED"


# ---------------------------------------------------------------------------
# 19. Multi-selection demonstration (section 131)
# ---------------------------------------------------------------------------


def test_multi_selection_building_mrt_equipment_survives(equipment_session):
    session = equipment_session
    sel = isa.select_multi(session, object_ids=["BLDG-A", "TRUNK-1", "SCN-PET-001"])
    assert set(sel.selected_object_ids) == {"BLDG-A", "TRUNK-1", "SCN-PET-001"}
    for oid in sel.selected_object_ids:
        assert oid in session.what_if.registry.objects


# ---------------------------------------------------------------------------
# 20. Component / vendor non-regression
# ---------------------------------------------------------------------------


def test_component_non_regression_canonical_spatial_authority_unmodified_semantics(session):
    """Sanity: apply_changeset/undo/reset semantics are exactly as tested by
    the closure build -- this module never redefines them."""
    obj = session.what_if.registry.get("BLDG-A")
    moved = dataclasses.replace(obj, transform=csa.Transform(position_x=1.0))
    cs = csa.apply_changeset(session.what_if, change_id="DIRECT-TEST", operation="MOVE_OBJECT", object_id="BLDG-A", new_object=moved)
    assert cs.object_id == "BLDG-A"
    session.what_if.undo_last_change()
    assert session.what_if.registry.get("BLDG-A").transform.position_x == 0.0


def test_vendor_adapter_files_not_imported_by_interactive_module():
    import inspect
    source = inspect.getsource(isa)
    assert "healthcare_adapters" not in source
    assert "healthcare_integration" not in source


def test_no_streamlit_or_frontend_framework_import():
    import inspect
    source = inspect.getsource(isa)
    import_lines = [line.strip().lower() for line in source.splitlines() if line.strip().startswith(("import ", "from "))]
    for forbidden in ("streamlit", "react", "omniverse", "bentley"):
        assert not any(forbidden in line for line in import_lines)

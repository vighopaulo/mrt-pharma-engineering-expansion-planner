"""Bentley Live iModel Binding + Geometry-Change Contract tests (offline,
deterministic). These NEVER require Bentley network, credentials, or
.env.bentley (Sec 50). Live proofs live in a separate opt-in gated test.

Covers: binding schema/identity/statuses, stale-version + disappearance,
Bentley-change != project-economic-change, present != new CapEx, Super-Build 3
composition; geometry event serialization/validation/absolute-state/no-drift,
100->500 / 500->100 / 4->8 / 8->12 controls, 3D->2D result schema, unknown
preservation, and no-fake-reactive-engine.
"""
from __future__ import annotations

import math
import pytest

import bentley_mrt_binding_authority as b
import geometry_change_contract as g
import capital_project_inheritance_authority as cap


def _ref(**kw):
    base = dict(
        itwin_id="bdf29ecd-b4a4-404d-861a-ac3061c7b12f",
        imodel_id="ea9c0558-45a3-40b8-91a9-f4075b826925",
        changeset_id="cs_A", model_id="m1", element_id="0x20000000123",
        class_name="IfcSpace", federation_guid="fg-1", label="Room 101",
    )
    base.update(kw)
    return b.BentleyExternalReference(**base)


# --- external reference / stable identity (Sec 9/32) ----------------------

def test_source_platform_is_bentley():
    assert _ref().source_platform == "BENTLEY_ITWIN"


def test_stable_identity_prefers_element_id_not_label():
    assert _ref().stable_identity_key() == "0x20000000123"


def test_stable_identity_falls_back_to_federation_guid():
    r = _ref(element_id=None)
    assert r.stable_identity_key() == "fg-1"


def test_stable_identity_falls_back_to_model_id():
    r = _ref(element_id=None, federation_guid=None)
    assert r.stable_identity_key() == "m1"


def test_no_stable_identity_when_only_label():
    r = _ref(element_id=None, federation_guid=None, model_id=None)
    assert not r.has_stable_identity()


def test_label_never_used_as_identity():
    r = _ref(element_id=None, federation_guid=None, model_id=None, label="Room 101")
    assert r.stable_identity_key() is None  # label ignored


# --- binding statuses (Sec 14) --------------------------------------------

def test_binding_status_vocabulary_complete():
    assert set(b.CANONICAL_BINDING_STATUSES) == {
        "BOUND", "UNBOUND", "IGNORED", "AMBIGUOUS", "UNSUPPORTED_CLASS",
        "MISSING_REQUIRED_PROPERTY", "STALE_SOURCE_VERSION", "SOURCE_ELEMENT_MISSING",
    }


def test_classify_bindability_missing_identity():
    assert b.classify_bindability(_ref(element_id=None, federation_guid=None, model_id=None)) == "MISSING_REQUIRED_PROPERTY"


def test_classify_bindability_unsupported_class():
    assert b.classify_bindability(_ref(class_name="IfcAnnotation")) == "UNSUPPORTED_CLASS"


def test_classify_bindability_bindable_is_unbound():
    assert b.classify_bindability(_ref()) == "UNBOUND"


def test_create_binding_bound():
    bd = b.create_binding(external_reference=_ref(), mrt_object_id="RM-101", mrt_object_type="ROOM")
    assert bd.binding_status == "BOUND" and bd.mrt_object_id == "RM-101"


def test_create_binding_records_bound_changeset():
    bd = b.create_binding(external_reference=_ref(changeset_id="cs_A"), mrt_object_id="RM-101")
    assert bd.bound_at_changeset_id == "cs_A"


def test_create_binding_unbound_no_mrt_object_not_silent():
    bd = b.create_binding(external_reference=_ref(), mrt_object_id=None)
    assert bd.binding_status == "UNBOUND" and bd.mrt_object_id is None


def test_create_binding_missing_identity_status():
    bd = b.create_binding(external_reference=_ref(element_id=None, federation_guid=None, model_id=None), mrt_object_id="X")
    assert bd.binding_status == "MISSING_REQUIRED_PROPERTY"


def test_create_binding_unsupported_class_status():
    bd = b.create_binding(external_reference=_ref(class_name="IfcAnnotation"), mrt_object_id="X")
    assert bd.binding_status == "UNSUPPORTED_CLASS"


# --- present != new CapEx + Super-Build 3 composition (Sec 15-16/38) ------

def test_bound_inherited_does_not_imply_new_capex():
    cls = cap.AssetClassification(origin="EXISTING_BASELINE", action="RETAINED_NO_CHANGE")
    bd = b.create_binding(external_reference=_ref(), mrt_object_id="RM-101", asset_classification=cls)
    assert bd.implies_new_capex() is False
    assert bd.economic_state() == "RETAINED_NO_CHANGE"


def test_bound_new_asset_implies_new_capex():
    cls = cap.AssetClassification(origin="NEW_TO_PROJECT", action="NEW")
    bd = b.create_binding(external_reference=_ref(), mrt_object_id="RM-NEW", asset_classification=cls)
    assert bd.implies_new_capex() is True
    assert bd.economic_state() == "NEW"


def test_bound_modify_does_not_imply_full_new_capex():
    cls = cap.AssetClassification(origin="EXISTING_BASELINE", action="MODIFY")
    bd = b.create_binding(external_reference=_ref(), mrt_object_id="RM-1", asset_classification=cls)
    assert bd.implies_new_capex() is False  # MODIFY charges only modification, not full new


def test_binding_without_classification_leaves_economics_undecided():
    bd = b.create_binding(external_reference=_ref(), mrt_object_id="RM-1")
    assert bd.economic_state() is None
    assert bd.implies_new_capex() is False  # never defaulted to NEW


def test_present_in_imodel_never_forces_new_capex_across_all_states():
    for origin, action, expect_capex in [
        ("EXISTING_BASELINE", "RETAINED_NO_CHANGE", False),
        ("EXISTING_BASELINE", "MODIFY", False),
        ("EXISTING_BASELINE", "REPLACE", True),
        ("EXISTING_BASELINE", "REMOVE", False),
        ("NEW_TO_PROJECT", "NEW", True),
        ("OUT_OF_BASELINE_SCOPE", "OUT_OF_SCOPE", False),
    ]:
        cls = cap.AssetClassification(origin=origin, action=action)
        bd = b.create_binding(external_reference=_ref(), mrt_object_id="RM", asset_classification=cls)
        assert bd.implies_new_capex() is expect_capex, (origin, action)


# --- staleness (Sec 36) ---------------------------------------------------

def test_stale_source_version_detected_not_deleted():
    bd = b.create_binding(external_reference=_ref(changeset_id="cs_A"), mrt_object_id="RM-101")
    stale = b.evaluate_source_version(bd, current_changeset_id="cs_B")
    assert stale.binding_status == "STALE_SOURCE_VERSION"
    assert stale.mrt_object_id == "RM-101"  # not deleted


def test_same_changeset_not_stale():
    bd = b.create_binding(external_reference=_ref(changeset_id="cs_A"), mrt_object_id="RM-101")
    assert b.evaluate_source_version(bd, current_changeset_id="cs_A").binding_status == "BOUND"


def test_stale_only_applies_to_bound():
    bd = b.create_binding(external_reference=_ref(element_id=None, federation_guid=None, model_id=None), mrt_object_id="X")
    assert b.evaluate_source_version(bd, current_changeset_id="cs_B").binding_status == "MISSING_REQUIRED_PROPERTY"


# --- disappearance (Sec 37) -----------------------------------------------

def test_element_disappearance_is_missing_not_remove():
    bd = b.create_binding(external_reference=_ref(), mrt_object_id="RM-101")
    out = b.evaluate_element_presence(bd, element_present_in_current_source=False, current_changeset_id="cs_B")
    assert out.binding_status == "SOURCE_ELEMENT_MISSING"
    assert "not project remove" in out.detail.lower()


def test_element_present_unchanged():
    bd = b.create_binding(external_reference=_ref(), mrt_object_id="RM-101")
    assert b.evaluate_element_presence(bd, element_present_in_current_source=True, current_changeset_id="cs_B").binding_status == "BOUND"


# --- Bentley change != project economic change (Sec 38) -------------------

@pytest.mark.parametrize("sc", ["ADDED", "GEOMETRY_CHANGED", "PROPERTY_CHANGED", "REMOVED"])
def test_source_change_requires_explicit_decision(sc):
    r = b.reconcile_source_change(sc)
    assert r.proposed_project_action is None
    assert r.requires_explicit_decision is True


def test_unchanged_needs_no_reconciliation():
    r = b.reconcile_source_change("UNCHANGED")
    assert not r.requires_explicit_decision


@pytest.mark.parametrize("sc", ["ADDED", "GEOMETRY_CHANGED", "PROPERTY_CHANGED", "REMOVED", "UNCHANGED"])
def test_source_change_never_implies_project_action(sc):
    assert b.source_change_implies_project_action(sc) is False


# --- geometry event: absolute state + deltas (Sec 20/40/46) ---------------

def test_separation_event_preserves_absolute_old_and_new():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="CHANGE_BUILDING_SEPARATION",
                                 old_separation_m=100.0, new_separation_m=500.0)
    assert e.old_separation_m == 100.0 and e.new_separation_m == 500.0
    assert e.separation_delta_m() == 400.0


def test_floor_count_event_absolute_and_delta():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="CHANGE_FLOOR_COUNT",
                                 old_floor_count=4, new_floor_count=8)
    assert e.old_floor_count == 4 and e.new_floor_count == 8 and e.floor_count_delta() == 4


def test_translation_distance():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="TRANSLATE",
                                 old_position_xyz=(0.0, 0.0, 0.0), new_position_xyz=(3.0, 4.0, 0.0))
    assert e.translation_distance_m() == 5.0


def test_supported_transform_types():
    assert set(g.SUPPORTED_TRANSFORM_TYPES) == {
        "TRANSLATE", "ROTATE", "CHANGE_ELEVATION", "CHANGE_BUILDING_SEPARATION",
        "CHANGE_FLOOR_COUNT", "CHANGE_FLOOR_HEIGHT", "RESIZE_FOOTPRINT",
        "RELOCATE_ROOM", "RELOCATE_EQUIPMENT",
    }


# --- validation (Sec 39) --------------------------------------------------

def test_valid_event_accepted():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="CHANGE_BUILDING_SEPARATION",
                                 old_separation_m=100.0, new_separation_m=500.0)
    assert g.validate_geometry_event(e).valid
    assert g.accept_geometry_event(e) is e


def test_missing_scenario_rejected():
    e = g.GeometryTransformEvent(scenario_id="", mrt_object_id="B", transform_type="TRANSLATE",
                                 old_position_xyz=(0, 0, 0), new_position_xyz=(1, 0, 0))
    assert not g.validate_geometry_event(e).valid


def test_missing_object_rejected():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="", transform_type="TRANSLATE",
                                 old_position_xyz=(0, 0, 0), new_position_xyz=(1, 0, 0))
    assert not g.validate_geometry_event(e).valid


def test_negative_floor_count_rejected():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="CHANGE_FLOOR_COUNT",
                                 old_floor_count=4, new_floor_count=-1)
    assert not g.validate_geometry_event(e).valid


def test_zero_floor_height_rejected():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="CHANGE_FLOOR_HEIGHT",
                                 old_floor_height_m=4.0, new_floor_height_m=0.0)
    assert not g.validate_geometry_event(e).valid


def test_non_finite_coordinate_rejected():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="TRANSLATE",
                                 old_position_xyz=(0, 0, 0), new_position_xyz=(float("inf"), 0, 0))
    assert not g.validate_geometry_event(e).valid


def test_unsupported_transform_rejected():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="WARP")  # type: ignore[arg-type]
    assert not g.validate_geometry_event(e).valid


def test_bentley_bound_missing_identity_rejected():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="TRANSLATE",
                                 source_platform="BENTLEY_ITWIN", old_position_xyz=(0, 0, 0), new_position_xyz=(1, 0, 0))
    assert not g.validate_geometry_event(e).valid


def test_bentley_bound_with_identity_valid():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="TRANSLATE",
                                 source_platform="BENTLEY_ITWIN", itwin_id="t", imodel_id="i", element_id="0x1",
                                 old_position_xyz=(0, 0, 0), new_position_xyz=(1, 0, 0))
    assert g.validate_geometry_event(e).valid


def test_missing_required_old_new_rejected():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="CHANGE_BUILDING_SEPARATION",
                                 old_separation_m=100.0)  # new missing
    assert not g.validate_geometry_event(e).valid


def test_negative_separation_rejected():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="CHANGE_BUILDING_SEPARATION",
                                 old_separation_m=100.0, new_separation_m=-5.0)
    assert not g.validate_geometry_event(e).valid


# --- building-separation controls (Sec 23-24) ----------------------------

def test_control_100_to_500_separation_delta_plus_400():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="BLDG-B", transform_type="CHANGE_BUILDING_SEPARATION",
                                 old_separation_m=100.0, new_separation_m=500.0)
    assert e.separation_delta_m() == 400.0


def test_control_500_to_100_separation_delta_minus_400():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="BLDG-B", transform_type="CHANGE_BUILDING_SEPARATION",
                                 old_separation_m=500.0, new_separation_m=100.0)
    assert e.separation_delta_m() == -400.0


# --- reversibility / no drift (Sec 41) ------------------------------------

def test_round_trip_100_500_100_no_drift():
    e1 = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="CHANGE_BUILDING_SEPARATION",
                                  old_separation_m=100.0, new_separation_m=500.0)
    e2 = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B", transform_type="CHANGE_BUILDING_SEPARATION",
                                  old_separation_m=500.0, new_separation_m=100.0)
    assert g.apply_events_to_separation(100.0, [e1, e2]) == 100.0
    assert g.round_trip_drift(100.0, [e1, e2]) == 0.0


def test_long_sequence_uses_absolute_not_accumulated_delta():
    seq = []
    vals = [100.0, 500.0, 250.0, 900.0, 100.0]
    for old, new in zip(vals, vals[1:]):
        seq.append(g.GeometryTransformEvent(scenario_id="S", mrt_object_id="B",
                                            transform_type="CHANGE_BUILDING_SEPARATION",
                                            old_separation_m=old, new_separation_m=new))
    assert g.apply_events_to_separation(100.0, seq) == 100.0  # last absolute, no drift


# --- floor-count controls (Sec 25/42) -------------------------------------

def test_control_4_to_8_floor_delta():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="A", transform_type="CHANGE_FLOOR_COUNT",
                                 old_floor_count=4, new_floor_count=8)
    assert e.floor_count_delta() == 4


def test_control_8_to_12_floor_delta():
    e = g.GeometryTransformEvent(scenario_id="S", mrt_object_id="A", transform_type="CHANGE_FLOOR_COUNT",
                                 old_floor_count=8, new_floor_count=12)
    assert e.floor_count_delta() == 4


def test_floor_expansion_composes_capital_inheritance_only_new_floors_charged():
    # 4->8: existing 4 inherited ($0), 4 new charged (Super-Build 3 capacity-delta)
    r = cap.compute_capacity_delta(cap.CapacityDeltaInputs(
        resource="floor", existing_usable_units=4, target_required_units=8, unit_capex_usd=3_000_000.0))
    assert r.new_units_required == 4
    assert r.new_capex_usd == 12_000_000.0  # not 8 * 3M


# --- 3D -> 2D analytical result contract (Sec 21/45-47) -------------------

def test_analytical_result_geometry_calibrated():
    e = g.GeometryTransformEvent(scenario_id="S1", mrt_object_id="BLDG-B", transform_type="CHANGE_BUILDING_SEPARATION",
                                 old_separation_m=100.0, new_separation_m=500.0)
    res = g.build_geometry_metric_result(e, baseline_scenario_id="BASE", geometry_change_id="GC1")
    sep = res.metric("building_separation")
    assert sep.target_value == 500.0 and sep.delta_vs_baseline == 400.0 and sep.status == "CALIBRATED"


def test_analytical_result_absolute_and_delta_both_present():
    e = g.GeometryTransformEvent(scenario_id="S1", mrt_object_id="A", transform_type="CHANGE_FLOOR_COUNT",
                                 old_floor_count=4, new_floor_count=8)
    res = g.build_geometry_metric_result(e, baseline_scenario_id="BASE", geometry_change_id="GC2")
    fc = res.metric("floor_count")
    assert fc.target_value == 8.0 and fc.delta_vs_baseline == 4.0


def test_analytical_result_downstream_not_zero_filled():
    e = g.GeometryTransformEvent(scenario_id="S1", mrt_object_id="B", transform_type="CHANGE_BUILDING_SEPARATION",
                                 old_separation_m=100.0, new_separation_m=500.0)
    res = g.build_geometry_metric_result(e, baseline_scenario_id="BASE", geometry_change_id="GC3")
    cap_metric = res.metric("incremental_transport_capex")
    assert cap_metric.target_value is None  # NOT zero-filled
    assert cap_metric.status == "NOT_YET_INTEGRATED"
    assert "incremental_transport_capex" in res.unknown_components()


def test_analytical_result_carries_baseline_and_scenario_ids():
    e = g.GeometryTransformEvent(scenario_id="S1", mrt_object_id="B", transform_type="CHANGE_BUILDING_SEPARATION",
                                 old_separation_m=100.0, new_separation_m=500.0)
    res = g.build_geometry_metric_result(e, baseline_scenario_id="BASE", geometry_change_id="GC4")
    assert res.scenario_id == "S1" and res.baseline_scenario_id == "BASE" and res.geometry_change_id == "GC4"


# --- consumer routing (Sec 22/43-44) --------------------------------------

def test_no_fake_reactive_engine():
    assert g.GENERALIZED_REACTIVE_ENGINE_INTEGRATED_NOW is False


def test_building_separation_consumers_classified():
    for c in g.BUILDING_SEPARATION_CONSUMERS:
        assert c.readiness in ("RUNTIME_CONSUMED_NOW", "ADAPTER_AVAILABLE", "NOT_YET_INTEGRATED", "NOT_CALIBRATED")


def test_building_separation_consumers_not_falsely_runtime():
    # honest: none is falsely claimed RUNTIME_CONSUMED_NOW (reactive engine not built)
    assert all(c.readiness != "RUNTIME_CONSUMED_NOW" for c in g.BUILDING_SEPARATION_CONSUMERS)


def test_floor_count_consumers_classified():
    assert len(g.FLOOR_COUNT_CONSUMERS) >= 10
    for c in g.FLOOR_COUNT_CONSUMERS:
        assert c.readiness in ("RUNTIME_CONSUMED_NOW", "ADAPTER_AVAILABLE", "NOT_YET_INTEGRATED", "NOT_CALIBRATED")


def test_transport_consumers_include_all_five_families():
    names = " ".join(c.consequence for c in g.BUILDING_SEPARATION_CONSUMERS)
    for fam in ("Manual", "PTS", "RTHS", "AGV", "MRT"):
        assert fam in names


# --- live mutation remains out of scope (Sec 48) --------------------------

def test_no_live_bentley_mutation_capability_in_contract_module():
    # the geometry contract module imports NO Bentley HTTP client and defines
    # no network transport -- it is a pure local contract (Sec 48).
    import inspect
    src = inspect.getsource(g)
    assert "bentley_itwin_client" not in src
    assert "urllib" not in src and "BentleyHttpTransport" not in src
    # and the binding authority never writes (no post/put/delete HTTP methods)
    bsrc = inspect.getsource(b)
    assert "urllib" not in bsrc and "def post" not in bsrc


# --- offline requirement (Sec 50) -----------------------------------------

def test_modules_import_without_bentley_credentials(monkeypatch):
    for var in ("BENTLEY_CLIENT_ID", "BENTLEY_CLIENT_SECRET", "BENTLEY_ITWIN_ID", "BENTLEY_IMODEL_ID"):
        monkeypatch.delenv(var, raising=False)
    import importlib
    importlib.reload(b)
    importlib.reload(g)
    # constructing binding + geometry objects needs no network/creds
    ref = b.BentleyExternalReference(itwin_id="t", imodel_id="i", changeset_id="c", model_id="m", element_id="e", class_name="IfcSpace")
    assert b.create_binding(external_reference=ref, mrt_object_id="O").binding_status == "BOUND"

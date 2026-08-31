"""Whole-building upright/equilibrium placement policy tests (ADDITIVE to the
current Bentley 3D spatial build). Sec H controls + hard gates.
"""
from __future__ import annotations

import pytest

import building_placement_policy_authority as bp
import canonical_spatial_authority as csa


def _pose(x=0.0, y=0.0, z=0.0, yaw=0.0, roll=0.0, pitch=0.0):
    return bp.BuildingPose(position_x=x, position_y=y, position_z=z, yaw_deg=yaw, roll_deg=roll, pitch_deg=pitch)


# --- default DOF policy (Sec A/G) -----------------------------------------

def test_engine_supports_6dof_substrate():
    assert bp.ENGINE_SPATIAL_SUBSTRATE_SUPPORTS_6DOF
    assert bp.ENGINE_SUPPORTS_ROLL_PITCH
    # canonical Transform genuinely carries roll/pitch/yaw
    t = csa.Transform(rotation_x=5.0, rotation_y=3.0, rotation_z=90.0)
    assert (t.rotation_x, t.rotation_y, t.rotation_z) == (5.0, 3.0, 90.0)


def test_whole_building_roll_pitch_locked_yaw_free():
    assert bp.whole_building_roll_locked()
    assert bp.whole_building_pitch_locked()
    assert bp.whole_building_yaw_free()


def test_whole_building_translation_xy_free():
    assert bp.whole_building_dof_permission("TRANSLATION_X") == "FREE"
    assert bp.whole_building_dof_permission("TRANSLATION_Y") == "FREE"


def test_whole_building_z_subject_to_support():
    assert bp.whole_building_dof_permission("TRANSLATION_Z") == "SUBJECT_TO_SUPPORT_POLICY"


def test_default_policy_locks_roll_and_pitch_but_not_yaw():
    assert bp.WHOLE_BUILDING_DEFAULT_DOF_POLICY["ROLL"] == "LOCKED"
    assert bp.WHOLE_BUILDING_DEFAULT_DOF_POLICY["PITCH"] == "LOCKED"
    assert bp.WHOLE_BUILDING_DEFAULT_DOF_POLICY["YAW"] == "FREE"


# --- Sec H control 1: move X/Y + yaw 135 -> roll/pitch stay 0 -------------

def test_control1_move_and_yaw_keeps_upright():
    raw = _pose(x=250.0, y=-80.0, yaw=135.0, roll=0.0, pitch=0.0)
    c = bp.resolve_building_placement(raw_pose=raw, support_surface_z=0.0)
    assert c.resolved_pose.roll_deg == 0.0
    assert c.resolved_pose.pitch_deg == 0.0
    assert c.resolved_pose.yaw_deg == 135.0
    assert c.resolved_pose.position_x == 250.0 and c.resolved_pose.position_y == -80.0


# --- Sec H control 2: raw tilt roll=12 pitch=-7 -> resolved 0/0 -----------

def test_control2_raw_tilt_resolves_to_upright():
    raw = _pose(x=10.0, y=10.0, yaw=0.0, roll=12.0, pitch=-7.0)
    c = bp.resolve_building_placement(raw_pose=raw, support_surface_z=0.0)
    assert c.resolved_pose.roll_deg == 0.0
    assert c.resolved_pose.pitch_deg == 0.0
    # corrections exposed, not hidden (Sec F)
    fields = {a.field for a in c.adjustments}
    assert "roll_deg" in fields and "pitch_deg" in fields
    assert bp.committed_pose_is_upright(c)


def test_control2_release_cannot_leave_unintended_roll_or_pitch():
    c = bp.resolve_building_placement(raw_pose=_pose(roll=30.0, pitch=15.0), support_surface_z=0.0)
    assert c.resolved_pose.roll_deg == 0.0 and c.resolved_pose.pitch_deg == 0.0


# --- Sec H control 3: yaw 0 -> 90 -> 270 stays upright --------------------

@pytest.mark.parametrize("yaw", [0.0, 90.0, 270.0, 360.0, 450.0])
def test_control3_yaw_sequence_stays_upright(yaw):
    c = bp.resolve_building_placement(raw_pose=_pose(yaw=yaw), support_surface_z=0.0)
    assert c.resolved_pose.roll_deg == 0.0 and c.resolved_pose.pitch_deg == 0.0
    assert 0.0 <= c.resolved_pose.yaw_deg < 360.0


def test_yaw_normalized_to_range():
    c = bp.resolve_building_placement(raw_pose=_pose(yaw=450.0), support_surface_z=0.0)
    assert c.resolved_pose.yaw_deg == 90.0


# --- Sec C: yaw triggers connection recomputation -------------------------

def test_yaw_rotation_triggers_connection_recompute():
    c = bp.resolve_building_placement(raw_pose=_pose(yaw=90.0), support_surface_z=0.0, yaw_changed=True)
    assert c.yaw_triggers_connection_recompute


# --- Sec H control 4: floating Z settles to support -----------------------

def test_control4_floating_z_settles_to_support():
    raw = _pose(x=0.0, y=0.0, z=42.0, yaw=0.0)  # dragged to floating 42m
    c = bp.resolve_building_placement(raw_pose=raw, support_surface_z=5.0, support_source="TERRAIN")
    assert c.support_status == "SETTLED_TO_SUPPORT_SURFACE"
    assert c.resolved_pose.position_z == 5.0
    assert any(a.field == "position_z" for a in c.adjustments)


# --- Sec H control 5: no support model -> NOT_CALIBRATED, no invented Z ----

def test_control5_no_support_model_reports_not_calibrated():
    raw = _pose(z=42.0)
    c = bp.resolve_building_placement(raw_pose=raw, support_surface_z=None)
    assert c.support_status == "SUPPORT_ELEVATION_NOT_CALIBRATED"
    assert c.resolved_pose.position_z is None  # Z NOT invented
    assert not bp.unsupported_floating_building_accepted(c)


def test_explicit_elevated_structure_keeps_raw_z():
    raw = _pose(z=30.0)
    c = bp.resolve_building_placement(raw_pose=raw, support_surface_z=0.0, allow_explicit_elevated=True)
    assert c.support_status == "EXPLICIT_ELEVATED_STRUCTURE"
    assert c.resolved_pose.position_z == 30.0


# --- Sec H control 6: round trip no drift ---------------------------------

def test_control6_move_yaw_return_no_drift():
    original = _pose(x=100.0, y=50.0, z=0.0, yaw=45.0)
    c0 = bp.resolve_building_placement(raw_pose=original, support_surface_z=0.0)
    # move + yaw away
    _c1 = bp.resolve_building_placement(raw_pose=_pose(x=600.0, y=-200.0, z=0.0, yaw=210.0), support_surface_z=0.0)
    # return to original raw pose
    c_back = bp.resolve_building_placement(raw_pose=original, support_surface_z=0.0)
    assert c_back.resolved_pose == c0.resolved_pose  # deterministic, no drift


# --- raw vs resolved exposure (Sec F) -------------------------------------

def test_raw_and_resolved_pose_both_exposed():
    raw = _pose(roll=9.0, pitch=4.0, yaw=400.0, z=20.0)
    c = bp.resolve_building_placement(raw_pose=raw, support_surface_z=2.0)
    assert c.raw_pose.roll_deg == 9.0 and c.raw_pose.pitch_deg == 4.0  # raw preserved
    assert c.resolved_pose.roll_deg == 0.0 and c.resolved_pose.pitch_deg == 0.0  # resolved upright
    assert c.adjustments  # placement adjustments visible


def test_committed_pose_bridges_to_canonical_transform():
    c = bp.resolve_building_placement(raw_pose=_pose(x=1.0, y=2.0, z=3.0, yaw=90.0), support_surface_z=3.0)
    t = c.resolved_pose.to_transform()
    assert t.rotation_z == 90.0 and t.rotation_x == 0.0 and t.rotation_y == 0.0  # yaw only
    assert (t.position_x, t.position_y, t.position_z) == (1.0, 2.0, 3.0)


# --- Sec G: engine keeps roll/pitch for non-building object classes --------

def test_engine_retains_roll_pitch_capability_for_other_classes():
    # a non-building object (e.g. sloped track) can still carry roll/pitch
    tilted = csa.Transform(rotation_x=15.0, rotation_y=8.0, rotation_z=0.0)
    assert tilted.rotation_x == 15.0 and tilted.rotation_y == 8.0
    # but the whole-building USER policy locks them
    assert bp.whole_building_roll_locked() and bp.whole_building_pitch_locked()

"""6-DOF anchor/movable pose orchestration tests (ADDITIVE to the current
Bentley 3D digital-twin integration + spatial-network-response build).

Proves: 6-DOF-capable substrate (not X-only), anchor/movable no-drift,
arbitrary-direction (300,400,0)->500m, true XYZ (300,400,120) separation,
yaw-with-fixed-origin (center unchanged, child interfaces move, connection
candidates recompute), child transforms follow parent, geometric separation !=
transport route length, permitted-DOF policy, and 6-DOF round-trip no-drift.

Composes the EXISTING canonical_spatial_authority 6-DOF primitives; no new
transform engine.
"""
from __future__ import annotations

import math
import pytest

import canonical_spatial_authority as csa
import spatial_pose_orchestration_authority as spo


# --- fixtures --------------------------------------------------------------

def _two_building_registry(b_pos=(100.0, 0.0, 0.0)):
    """Building A anchor at origin; Building B movable at b_pos; B has a child
    door at local offset (10, 5, 0)."""
    reg = csa.build_facility_hierarchy(facility_id="FAC")
    csa.add_building(reg, facility_id="FAC", building_id="BLDG-A", transform=csa.Transform())
    csa.add_building(reg, facility_id="FAC", building_id="BLDG-B",
                     transform=csa.Transform(position_x=b_pos[0], position_y=b_pos[1], position_z=b_pos[2]))
    csa.add_floor(reg, facility_id="FAC", building_id="BLDG-B", floor_id="F1")
    csa.add_room(reg, facility_id="FAC", building_id="BLDG-B", floor_id="F1", room_id="B-DOOR",
                 transform=csa.Transform(position_x=10.0, position_y=5.0, position_z=0.0))
    return reg


# --- 6-DOF substrate (not single-axis) ------------------------------------

def test_spatial_transform_supports_6dof():
    assert spo.SPATIAL_TRANSFORM_SUPPORTS_6DOF is True
    t = csa.Transform(position_x=1, position_y=2, position_z=3, rotation_x=4, rotation_y=5, rotation_z=6)
    # all six DOF are independent fields
    assert (t.position_x, t.position_y, t.position_z, t.rotation_x, t.rotation_y, t.rotation_z) == (1, 2, 3, 4, 5, 6)


def test_default_policy_is_full_6dof_not_single_axis():
    p = spo.full_6dof_policy()
    assert p.is_full_6dof()
    for dof in spo.ALL_DOF:
        assert p.allows(dof)


def test_building_translation_not_restricted_to_single_axis():
    # moving B in Y and Z (not just X) is permitted by default policy
    reg = _two_building_registry()
    moved = spo.move_movable(reg, movable_id="BLDG-B", new_transform=csa.Transform(position_x=100.0, position_y=250.0, position_z=40.0))
    sep = spo.compute_anchor_movable_separation(moved, anchor_id="BLDG-A", movable_id="BLDG-B")
    assert sep.delta_y == 250.0 and sep.delta_z == 40.0  # Y and Z honored


# --- anchor / movable no drift --------------------------------------------

def test_anchor_does_not_drift_when_movable_moves():
    reg = _two_building_registry()
    anchor_ref = csa.resolve_global_position(reg, "BLDG-A")
    moved = spo.move_movable(reg, movable_id="BLDG-B", new_transform=csa.Transform(position_x=500.0))
    sep = spo.compute_anchor_movable_separation(moved, anchor_id="BLDG-A", movable_id="BLDG-B", anchor_reference_position=anchor_ref)
    assert not sep.anchor_drifted
    assert sep.anchor_pose.position_xyz == anchor_ref


# --- arbitrary-direction control (300,400,0) -> 500 -----------------------

def test_non_axis_aligned_translation_control():
    reg = _two_building_registry((100.0, 0.0, 0.0))
    moved = spo.move_movable(reg, movable_id="BLDG-B", new_transform=csa.Transform(position_x=300.0, position_y=400.0, position_z=0.0))
    sep = spo.compute_anchor_movable_separation(moved, anchor_id="BLDG-A", movable_id="BLDG-B")
    assert sep.geometric_separation_m == pytest.approx(500.0)  # sqrt(300^2+400^2)
    assert (sep.delta_x, sep.delta_y, sep.delta_z) == (300.0, 400.0, 0.0)


# --- true XYZ control (300,400,120) ---------------------------------------

def test_xyz_separation_control():
    reg = _two_building_registry((0.0, 0.0, 0.0))
    moved = spo.move_movable(reg, movable_id="BLDG-B", new_transform=csa.Transform(position_x=300.0, position_y=400.0, position_z=120.0))
    sep = spo.compute_anchor_movable_separation(moved, anchor_id="BLDG-A", movable_id="BLDG-B")
    assert sep.delta_x == 300.0 and sep.delta_y == 400.0 and sep.delta_z == 120.0
    assert sep.geometric_separation_m == pytest.approx(math.sqrt(300**2 + 400**2 + 120**2))
    assert sep.delta_z != 0.0  # Z not flattened


# --- yaw rotation with fixed origin ---------------------------------------

def test_rotation_with_fixed_origin_control():
    reg = _two_building_registry((500.0, 0.0, 0.0))
    before = reg
    after = spo.move_movable(reg, movable_id="BLDG-B", new_transform=csa.Transform(position_x=500.0, rotation_z=90.0))
    impact = spo.evaluate_rotation_impact(before, after, anchor_id="BLDG-A", movable_id="BLDG-B", interface_ids=("B-DOOR",))
    assert impact.center_separation_unchanged           # origin fixed -> center distance same
    assert impact.any_interface_world_position_changed  # child door world coords moved
    assert impact.connection_candidates_must_recompute
    assert "B-DOOR" in impact.moved_interface_ids


def test_building_rotation_not_ignored_by_connection_engine():
    reg = _two_building_registry((500.0, 0.0, 0.0))
    door_before = csa.resolve_global_position(reg, "B-DOOR")
    rotated = spo.move_movable(reg, movable_id="BLDG-B", new_transform=csa.Transform(position_x=500.0, rotation_z=90.0))
    door_after = csa.resolve_global_position(rotated, "B-DOOR")
    assert door_before != door_after  # SAME_CENTER_DISTANCE != SAME_ENGINEERING_RESULT


# --- child transforms follow parent ---------------------------------------

def test_child_connection_point_transform_follows_parent_translation():
    reg = _two_building_registry((100.0, 0.0, 0.0))
    before = csa.resolve_global_position(reg, "B-DOOR")  # (110,5,0)
    moved = spo.move_movable(reg, movable_id="BLDG-B", new_transform=csa.Transform(position_x=600.0))
    after = csa.resolve_global_position(moved, "B-DOOR")
    assert after[0] - before[0] == pytest.approx(500.0)  # door followed building by same delta
    assert after[1] == before[1]


def test_child_interface_world_positions_resolved():
    reg = _two_building_registry((100.0, 0.0, 0.0))
    ifaces = spo.resolve_child_interface_world_positions(reg, ("B-DOOR",))
    assert ifaces[0].interface_id == "B-DOOR"
    assert ifaces[0].world_position_xyz == (110.0, 5.0, 0.0)


# --- geometric separation != transport route length -----------------------

def test_geometric_separation_not_equal_all_transport_routes():
    cmp = spo.compare_geometric_vs_transport(
        geometric_separation_m=500.0,
        transport_route_lengths_m={"MRT": 400.0, "MANUAL": 520.0, "PTS_CONVENTIONAL": 450.0},
    )
    assert not cmp.geometric_equals_all_routes


def test_geometric_equals_routes_only_in_degenerate_case():
    cmp = spo.compare_geometric_vs_transport(
        geometric_separation_m=500.0, transport_route_lengths_m={"MRT": 500.0},
    )
    assert cmp.geometric_equals_all_routes  # degenerate: equal by coincidence


# --- permitted-DOF policy --------------------------------------------------

def test_ground_plane_policy_forbids_z_change():
    reg = _two_building_registry((100.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        spo.move_movable(reg, movable_id="BLDG-B",
                         new_transform=csa.Transform(position_x=100.0, position_z=50.0),
                         policy=spo.ground_plane_policy(),
                         current_transform=csa.Transform(position_x=100.0))


def test_ground_plane_policy_allows_planar_and_yaw():
    reg = _two_building_registry((100.0, 0.0, 0.0))
    # TX + TY + YAW allowed
    moved = spo.move_movable(reg, movable_id="BLDG-B",
                             new_transform=csa.Transform(position_x=200.0, position_y=50.0, rotation_z=45.0),
                             policy=spo.ground_plane_policy(),
                             current_transform=csa.Transform(position_x=100.0))
    assert csa.resolve_global_position(moved, "BLDG-B")[0] == 200.0


# --- 6-DOF round-trip no drift --------------------------------------------

def test_six_dof_round_trip_no_drift():
    reg = _two_building_registry((100.0, 0.0, 0.0))
    initial = csa.Transform(position_x=100.0)
    intermediate = csa.Transform(position_x=300.0, position_y=400.0, position_z=120.0, rotation_z=90.0)
    result = spo.evaluate_six_dof_round_trip(
        reg, anchor_id="BLDG-A", movable_id="BLDG-B",
        intermediate_transform=intermediate, restore_transform=initial,
        interface_ids=("B-DOOR",),
    )
    assert result.anchor_unchanged
    assert result.movable_pose_restored
    assert result.child_world_positions_restored
    assert not result.drift_present
    assert result.max_drift_m <= 1e-6


def test_six_dof_round_trip_anchor_never_moves():
    reg = _two_building_registry((100.0, 0.0, 0.0))
    result = spo.evaluate_six_dof_round_trip(
        reg, anchor_id="BLDG-A", movable_id="BLDG-B",
        intermediate_transform=csa.Transform(position_x=900.0, position_y=250.0, rotation_z=30.0),
        restore_transform=csa.Transform(position_x=100.0),
        interface_ids=("B-DOOR",),
    )
    assert result.anchor_unchanged

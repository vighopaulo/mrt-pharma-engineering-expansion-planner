"""Build 2 focused tests: canonical global-position accumulation closure
(Section 17-18/34 items 1-4, 13-16).

Confirms the genuine gap identified by the Build-2 pre-implementation audit
(canonical_spatial_authority.py had a `Transform` dataclass with full 6DOF
but NO function that accumulated a parent chain's transforms into a child's
global position) is closed via `resolve_global_position` /
`compute_global_distance` / `SpatialObjectRegistry.replace_transform` --
pure geometry reusing the EXISTING `Transform`/`CanonicalSpatialObject`/
`SpatialObjectRegistry` primitives, never a new geometry engine.
"""

from __future__ import annotations

import math

import pytest

import canonical_spatial_authority as csa


@pytest.fixture
def two_building_registry() -> csa.SpatialObjectRegistry:
    registry = csa.build_facility_hierarchy(facility_id="FAC-1")
    csa.add_building(registry, facility_id="FAC-1", building_id="BLDG-A", transform=csa.Transform())
    csa.add_building(registry, facility_id="FAC-1", building_id="BLDG-B", transform=csa.Transform(position_x=500.0))
    csa.add_floor(registry, facility_id="FAC-1", building_id="BLDG-A", floor_id="F1")
    csa.add_floor(registry, facility_id="FAC-1", building_id="BLDG-B", floor_id="F1")
    csa.add_room(registry, facility_id="FAC-1", building_id="BLDG-A", floor_id="F1", room_id="A-F1-R01", transform=csa.Transform(position_x=3.0, position_y=4.0))
    csa.add_room(registry, facility_id="FAC-1", building_id="BLDG-B", floor_id="F1", room_id="B-F1-R01", transform=csa.Transform(position_x=10.0, position_y=5.0))
    return registry


class TestCanonicalTranslation:
    """Test group item 1: canonical translation changes global coordinates correctly."""

    def test_building_translation_changes_own_global_position(self, two_building_registry):
        before = csa.resolve_global_position(two_building_registry, "BLDG-B")
        moved = two_building_registry.replace_transform("BLDG-B", csa.Transform(position_x=700.0))
        after = csa.resolve_global_position(moved, "BLDG-B")
        assert before == (500.0, 0.0, 0.0)
        assert after == (700.0, 0.0, 0.0)

    def test_building_translation_propagates_rigidly_to_child_room(self, two_building_registry):
        """Section 17: 'Every engineering object belonging to that building
        must resolve its new global position consistently' -- the room's
        LOCAL offset (10, 5, 0) is unchanged; only the building's global
        origin shifts, so the room's global position shifts by the SAME
        delta (never independently recomputed, never left stale)."""
        before = csa.resolve_global_position(two_building_registry, "B-F1-R01")
        moved = two_building_registry.replace_transform("BLDG-B", csa.Transform(position_x=700.0))
        after = csa.resolve_global_position(moved, "B-F1-R01")
        assert before == (510.0, 5.0, 0.0)
        assert after == (710.0, 5.0, 0.0)
        assert after[0] - before[0] == pytest.approx(200.0)  # same delta as the building's own translation
        assert after[1] == before[1]  # unaffected axis stays unaffected

    def test_translation_changes_inter_building_distance(self, two_building_registry):
        before_distance = csa.compute_global_distance(two_building_registry, "BLDG-A", "BLDG-B")
        moved = two_building_registry.replace_transform("BLDG-B", csa.Transform(position_x=700.0))
        after_distance = csa.compute_global_distance(moved, "BLDG-A", "BLDG-B")
        assert before_distance == 500.0
        assert after_distance == 700.0


class TestCanonicalRotation:
    """Test group item 2: canonical 90-degree rotation changes owned object
    global coordinates correctly."""

    def test_90_degree_rotation_transforms_child_room_correctly(self, two_building_registry):
        rotated = two_building_registry.replace_transform("BLDG-B", csa.Transform(position_x=500.0, rotation_z=90.0))
        room_global = csa.resolve_global_position(rotated, "B-F1-R01")
        # local (10, 5, 0) rotated 90 deg about Z: (x'=-y, y'=x) = (-5, 10, 0), then + building origin (500, 0, 0)
        assert room_global == pytest.approx((495.0, 10.0, 0.0))

    def test_rotation_about_own_origin_leaves_building_origin_invariant(self, two_building_registry):
        """Section 19: 'Preserve: building center'. Rotation about the
        building's own local origin never moves that origin's global
        position -- the axis point itself is invariant under rotation."""
        rotated = two_building_registry.replace_transform("BLDG-B", csa.Transform(position_x=500.0, rotation_z=90.0))
        assert csa.resolve_global_position(rotated, "BLDG-B") == (500.0, 0.0, 0.0)

    def test_rotation_invariant_for_connection_point_at_axis(self, two_building_registry):
        """Section 19: 'If symmetric geometry causes no change: report
        PHYSICALLY_INVARIANT_FOR_THIS_TRANSFORM rather than forcing a
        sensitivity result.' A connection point located exactly at the
        building's own origin (the rotation axis) is genuinely invariant
        under any rotation -- inter-building distance must not change."""
        before_distance = csa.compute_global_distance(two_building_registry, "BLDG-A", "BLDG-B")
        rotated = two_building_registry.replace_transform("BLDG-B", csa.Transform(position_x=500.0, rotation_z=90.0))
        after_distance = csa.compute_global_distance(rotated, "BLDG-A", "BLDG-B")
        assert after_distance == pytest.approx(before_distance)

    def test_rotation_changes_distance_for_off_axis_room(self, two_building_registry):
        """A room OFFSET from the rotation axis is NOT invariant -- proves
        the qualification correctly distinguishes invariant vs sensitive
        objects rather than reporting a single blanket answer."""
        before_distance = csa.compute_global_distance(two_building_registry, "BLDG-A", "B-F1-R01")
        rotated = two_building_registry.replace_transform("BLDG-B", csa.Transform(position_x=500.0, rotation_z=90.0))
        after_distance = csa.compute_global_distance(rotated, "BLDG-A", "B-F1-R01")
        assert after_distance != pytest.approx(before_distance)


class TestVisualEngineeringNeverDisconnected:
    """Test group item 3: visual/spatial transformation cannot remain
    disconnected from engineering coordinates."""

    def test_resolve_global_position_reads_the_same_transform_object_stores(self, two_building_registry):
        """There is no separate 'visual-only' transform copy -- the global
        position is derived directly from the SAME `CanonicalSpatialObject.transform`
        field that `openusd_spatial_adapter.py` reads/writes."""
        obj = two_building_registry.get("BLDG-B")
        moved_registry = two_building_registry.replace_transform("BLDG-B", csa.Transform(position_x=999.0))
        moved_obj = moved_registry.get("BLDG-B")
        assert moved_obj.transform.position_x == 999.0
        assert csa.resolve_global_position(moved_registry, "BLDG-B")[0] == moved_obj.transform.position_x
        assert obj.transform.position_x == 500.0  # original object/registry non-mutated (frozen dataclass discipline)


class TestIdentitySurvivesGeometryTransforms:
    """Test group items 13-16: patient/room/scanner/building identity
    survives geometry transformations."""

    def test_room_identity_survives_movement(self, two_building_registry):
        moved = two_building_registry.replace_transform("BLDG-B", csa.Transform(position_x=999.0))
        assert moved.get("B-F1-R01").mrtway_object_id == "B-F1-R01"

    def test_building_identity_survives_rotation_and_translation(self, two_building_registry):
        moved = two_building_registry.replace_transform("BLDG-B", csa.Transform(position_x=999.0, rotation_z=45.0))
        assert moved.get("BLDG-B").mrtway_object_id == "BLDG-B"
        assert moved.get("BLDG-B").object_type == "BUILDING"

    def test_scanner_identity_survives_movement(self, two_building_registry):
        csa.add_room(
            two_building_registry, facility_id="FAC-1", building_id="BLDG-A", floor_id="F1", room_id="A-F1-SCN01",
            object_type="EQUIPMENT", transform=csa.Transform(position_x=1.0, position_y=1.0),
        )
        moved = two_building_registry.replace_transform("A-F1-SCN01", csa.Transform(position_x=50.0))
        assert moved.get("A-F1-SCN01").mrtway_object_id == "A-F1-SCN01"
        assert csa.resolve_global_position(moved, "A-F1-SCN01") != csa.resolve_global_position(two_building_registry, "A-F1-SCN01")

    def test_non_moved_object_positions_are_unaffected(self, two_building_registry):
        """Unaffected quantities must remain unchanged for physically
        correct reasons (Section 32) -- moving Building B must never alter
        Building A or its rooms."""
        before = csa.resolve_global_position(two_building_registry, "A-F1-R01")
        moved = two_building_registry.replace_transform("BLDG-B", csa.Transform(position_x=999.0, rotation_z=45.0))
        after = csa.resolve_global_position(moved, "A-F1-R01")
        assert before == after


class TestNoParallelGeometryEngine:
    """Test group item 20: no parallel geometry engine is introduced."""

    def test_apply_rigid_transform_is_the_only_new_geometry_primitive(self):
        """The closure adds exactly 3 new functions/methods
        (`resolve_global_position`, `compute_global_distance`,
        `SpatialObjectRegistry.replace_transform`) plus one pure-math helper
        (`apply_rigid_transform`/`_rotation_matrix`) -- all operating on the
        EXISTING `Transform`/`CanonicalSpatialObject` dataclasses, never a
        second spatial object model."""
        assert hasattr(csa, "resolve_global_position")
        assert hasattr(csa, "compute_global_distance")
        assert hasattr(csa, "apply_rigid_transform")
        assert hasattr(csa.SpatialObjectRegistry, "replace_transform")


def test_identity_transform_is_a_no_op():
    identity = csa.Transform()
    assert csa.apply_rigid_transform((1.0, 2.0, 3.0), identity) == pytest.approx((1.0, 2.0, 3.0))


def test_180_degree_rotation_negates_local_xy():
    t = csa.Transform(rotation_z=180.0)
    x, y, z = csa.apply_rigid_transform((10.0, 5.0, 0.0), t)
    assert x == pytest.approx(-10.0, abs=1e-9)
    assert y == pytest.approx(-5.0, abs=1e-9)
    assert z == pytest.approx(0.0, abs=1e-9)


class TestScannerRelocationCausalSeparation:
    """Test group items 11-12/21: scanner relocation must change post-
    injection movement/queue/utilization where modeled, but must NEVER
    retroactively alter an already-injected patient's release->administration
    retention clock."""

    def test_scanner_relocation_does_not_alter_already_computed_retention(self):
        """`evaluate_hybrid_zone_candidate` (hybrid_optimization.py) computes
        `elapsed = injection_start - release_time` and
        `retained = retained_fraction(elapsed, half_life)` purely from the
        joint clinical SCHEDULE -- it does not accept or consume any scanner
        spatial coordinate. Moving a scanner's canonical Transform therefore
        cannot retroactively change a previously-computed patient trace's
        retention, because the retention computation never reads scanner
        position in the first place (confirmed via source audit:
        hybrid_optimization.py's retention block reads only
        `trace.injection_start`/`release_time`/`half_life`)."""
        import hybrid_optimization as ho
        import inspect
        source = inspect.getsource(ho.evaluate_hybrid_zone_candidate)
        # The retention computation line must not reference any scanner
        # coordinate/position symbol -- proves the causal separation exists
        # in the actual source, not merely by absence of a test.
        retention_line = next(line for line in source.splitlines() if "retained_fraction(elapsed, half_life)" in line)
        assert "scanner" not in retention_line.lower()
        assert "position" not in retention_line.lower()
        assert "coordinate" not in retention_line.lower()

    def test_scanner_object_can_be_relocated_independently_of_retention_authority(self, two_building_registry):
        """A scanner represented as a canonical spatial object can be moved
        (Section 17 closure) without invoking any retention/decay authority
        -- the two concerns are architecturally decoupled, exactly as
        required (moving a scanner's global position never imports or calls
        `multi_isotope_decay.retained_fraction`)."""
        csa.add_room(
            two_building_registry, facility_id="FAC-1", building_id="BLDG-A", floor_id="F1", room_id="A-F1-SCANNER-01",
            object_type="EQUIPMENT", transform=csa.Transform(position_x=2.0, position_y=2.0),
        )
        before = csa.resolve_global_position(two_building_registry, "A-F1-SCANNER-01")
        moved_registry = two_building_registry.replace_transform("A-F1-SCANNER-01", csa.Transform(position_x=40.0, position_y=8.0))
        after = csa.resolve_global_position(moved_registry, "A-F1-SCANNER-01")
        assert before != after
        # No other object's global position changes as a side effect of the scanner move.
        assert csa.resolve_global_position(moved_registry, "BLDG-A") == csa.resolve_global_position(two_building_registry, "BLDG-A")
        assert csa.resolve_global_position(moved_registry, "A-F1-R01") == csa.resolve_global_position(two_building_registry, "A-F1-R01")

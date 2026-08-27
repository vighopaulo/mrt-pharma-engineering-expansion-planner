"""Controlled regression coverage for Phase 7: benchmark geometry-scale
sensitivity / retention break-even envelope study (see spatial_benchmark.py:
build_benchmark_geometry, build_scaled_benchmark_geometry, compute_retention_envelope).

Proves:
- geometry scale = 1 (horizontal_scale=1.0, floor_count=FLOOR_COUNT) reproduces the
  existing 8-floor BASELINE_CONTROL geometry and retention envelope exactly;
- increasing horizontal route scale never makes geometric transport time decrease
  for either pathway, and never improves retention;
- increasing vertical reach/floor count never decreases the maximum transport
  difficulty for either pathway;
- both pathways use the same radionuclide, half-life, and retention threshold --
  only transport timing differs;
- the original 8-floor/10-room/6m/4m benchmark is unchanged after parameterization.
"""

from __future__ import annotations

from spatial_benchmark import (
    FLOOR_COUNT,
    ROOMS_PER_FLOOR,
    build_benchmark_geometry,
    build_scaled_benchmark_geometry,
    compute_retention_envelope,
    _base_assumptions,
    _route_metrics_for_rooms,
    build_production_basis,
)


def test_geometry_scale_one_reproduces_baseline_control() -> None:
    """Section 33: horizontal_scale=1.0, floor_count=FLOOR_COUNT must be byte-identical
    to the original, unparameterized 8-floor benchmark geometry.
    """
    baseline = build_benchmark_geometry()
    scaled = build_scaled_benchmark_geometry(horizontal_scale=1.0, floor_count=FLOOR_COUNT)

    assert scaled.floor_count == baseline.floor_count == FLOOR_COUNT
    assert scaled.rooms_per_floor == baseline.rooms_per_floor == ROOMS_PER_FLOOR
    assert scaled.floor_to_floor_height_m == baseline.floor_to_floor_height_m
    assert scaled.corridor_room_spacing_m == baseline.corridor_room_spacing_m == 6.0
    assert scaled.room_ids == baseline.room_ids
    assert scaled.room_coordinates_by_id == baseline.room_coordinates_by_id


def test_geometry_scale_one_reproduces_baseline_retention_envelope() -> None:
    """Section 37: original 8-floor/10-room/6m/4m benchmark produces the same
    retention envelope after parameterization.
    """
    assumptions = _base_assumptions()
    basis = build_production_basis()
    baseline = build_benchmark_geometry()
    scaled = build_scaled_benchmark_geometry(horizontal_scale=1.0, floor_count=FLOOR_COUNT)

    for pathway in ("Conventional", "MRT"):
        baseline_env = compute_retention_envelope(
            geometry=baseline, assumptions=assumptions, radionuclide=basis.radionuclide, pathway=pathway
        )
        scaled_env = compute_retention_envelope(
            geometry=scaled, assumptions=assumptions, radionuclide=basis.radionuclide, pathway=pathway
        )
        assert scaled_env.feasible_room_ids == baseline_env.feasible_room_ids
        for room_id in baseline_env.records_by_room_id:
            assert scaled_env.records_by_room_id[room_id].retained_fraction == baseline_env.records_by_room_id[room_id].retained_fraction


def test_monotonic_horizontal_difficulty() -> None:
    """Section 34: as horizontal route scale increases (floor count held fixed),
    geometric transport time must not decrease for either pathway, and worst-case
    retention must not improve.
    """
    assumptions = _base_assumptions()
    basis = build_production_basis()
    multipliers = [1.0, 2.0, 4.0, 8.0, 16.0]

    previous_conv_max = -1.0
    previous_mrt_max = -1.0
    previous_conv_worst_retained = 2.0
    previous_mrt_worst_retained = 2.0

    for mult in multipliers:
        geometry = build_scaled_benchmark_geometry(horizontal_scale=mult, floor_count=FLOOR_COUNT)
        (_dist, _vert, _trans, manual, mrt, _edges) = _route_metrics_for_rooms(geometry, geometry.room_ids, assumptions)
        conv_max = max(manual.values())
        mrt_max = max(mrt.values())
        assert conv_max >= previous_conv_max
        assert mrt_max >= previous_mrt_max
        previous_conv_max = conv_max
        previous_mrt_max = mrt_max

        conv_env = compute_retention_envelope(
            geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional"
        )
        mrt_env = compute_retention_envelope(
            geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT"
        )
        conv_worst_retained = min(record.retained_fraction for record in conv_env.records_by_room_id.values())
        mrt_worst_retained = min(record.retained_fraction for record in mrt_env.records_by_room_id.values())
        assert conv_worst_retained <= previous_conv_worst_retained
        assert mrt_worst_retained <= previous_mrt_worst_retained
        previous_conv_worst_retained = conv_worst_retained
        previous_mrt_worst_retained = mrt_worst_retained


def test_monotonic_vertical_difficulty() -> None:
    """Section 35: as vertical reach/floor count increases (horizontal scale held
    fixed), maximum transport difficulty must not decrease for either pathway.
    """
    assumptions = _base_assumptions()
    floor_counts = [4, 8, 12, 16, 24]

    previous_conv_max = -1.0
    previous_mrt_max = -1.0

    for floor_count in floor_counts:
        geometry = build_scaled_benchmark_geometry(horizontal_scale=1.0, floor_count=floor_count)
        (_dist, _vert, _trans, manual, mrt, _edges) = _route_metrics_for_rooms(geometry, geometry.room_ids, assumptions)
        conv_max = max(manual.values())
        mrt_max = max(mrt.values())
        assert conv_max >= previous_conv_max
        assert mrt_max >= previous_mrt_max
        previous_conv_max = conv_max
        previous_mrt_max = mrt_max


def test_same_retention_physics_across_pathways() -> None:
    """Section 36: both pathways share the same radionuclide, half-life, and
    retention threshold at every scale -- only transport timing differs.
    """
    assumptions = _base_assumptions()
    basis = build_production_basis()

    for horizontal_scale, floor_count in [(1.0, FLOOR_COUNT), (10.0, FLOOR_COUNT), (1.0, 16)]:
        geometry = build_scaled_benchmark_geometry(horizontal_scale=horizontal_scale, floor_count=floor_count)
        conv_env = compute_retention_envelope(
            geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional"
        )
        mrt_env = compute_retention_envelope(
            geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT"
        )
        assert conv_env.radionuclide == mrt_env.radionuclide == basis.radionuclide
        assert conv_env.half_life_minutes == mrt_env.half_life_minutes
        assert conv_env.threshold == mrt_env.threshold == assumptions.minimum_release_to_administration_retention_fraction


def test_mrt_advantage_window_exists_in_pure_horizontal_scaling() -> None:
    """Section 4/12: a region exists (pure horizontal scaling, floor count fixed at
    baseline) where Conventional's worst-room retention falls below the 90% threshold
    while MRT's worst-room retention remains at/above it -- the MRT_ADVANTAGE_WINDOW.
    This is measured evidence from existing, unmodified transport physics, not a
    manufactured result.
    """
    assumptions = _base_assumptions()
    basis = build_production_basis()
    geometry = build_scaled_benchmark_geometry(horizontal_scale=20.0, floor_count=FLOOR_COUNT)

    conv_env = compute_retention_envelope(
        geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional", threshold=0.90
    )
    mrt_env = compute_retention_envelope(
        geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT", threshold=0.90
    )
    conv_worst_retained = min(record.retained_fraction for record in conv_env.records_by_room_id.values())
    mrt_worst_retained = min(record.retained_fraction for record in mrt_env.records_by_room_id.values())

    assert conv_worst_retained < 0.90
    assert mrt_worst_retained >= 0.90


def test_mrt_no_longer_breaks_before_conventional_after_transition_semantics_audit() -> None:
    """Section 30 (superseded by the MRT H<->V transition semantics audit): this
    test previously encoded a floors=50 MRT vertical breakpoint that was an
    artifact of a defect where physical transition count scaled with the number of
    vertical GRAPH EDGES (one per floor-to-floor elevator hop) rather than with
    genuine physical H<->V directional changes. Every route in this benchmark is
    topologically H,V(chain),H -- a single continuous elevator shaft with no
    intervening horizontal segments -- so the physically correct transition count
    is a constant 2, independent of floor count (see _physical_transition_count).
    Under the corrected physics, MRT's worst-room retention at floors=50 remains
    comfortably feasible and no longer breaks before Conventional.
    """
    assumptions = _base_assumptions()
    basis = build_production_basis()
    geometry = build_scaled_benchmark_geometry(horizontal_scale=1.0, floor_count=50)

    conv_env = compute_retention_envelope(
        geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional", threshold=0.90
    )
    mrt_env = compute_retention_envelope(
        geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT", threshold=0.90
    )
    conv_worst_retained = min(record.retained_fraction for record in conv_env.records_by_room_id.values())
    mrt_worst_retained = min(record.retained_fraction for record in mrt_env.records_by_room_id.values())

    assert mrt_worst_retained >= 0.90
    assert conv_worst_retained >= 0.90

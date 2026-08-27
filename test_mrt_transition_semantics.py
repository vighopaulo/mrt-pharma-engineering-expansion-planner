"""Controlled regression coverage for the MRT H<->V transition semantics audit
(see spatial_benchmark.py: _physical_motion_mode_sequence, _physical_transition_count).

Proves:
- graph edges and physical directional transitions are explicitly distinguished;
- transition count follows physical motion-mode changes, not the number of
  vertical graph edges traversed (segmentation invariance);
- genuine multiple H<->V excursions remain counted in full;
- pure horizontal and pure vertical routes are handled correctly;
- the baseline 8-floor benchmark's representative routes use the corrected
  (constant, floor-count-independent) physical transition count.
"""

from __future__ import annotations

from facility_engineering_model import SpatialEdge
from spatial_benchmark import (
    _physical_motion_mode_sequence,
    _physical_transition_count,
    _route_metrics_for_rooms,
    _base_assumptions,
    build_benchmark_geometry,
    build_scaled_benchmark_geometry,
)


def _edge(edge_id: str, vertical_change_m: float, length_m: float = 1.0) -> SpatialEdge:
    return SpatialEdge(
        edge_id=edge_id,
        source_node_id=f"{edge_id}-SRC",
        destination_node_id=f"{edge_id}-DST",
        length_m=length_m,
        vertical_change_m=vertical_change_m,
    )


def test_continuous_vertical_shaft_compresses_to_single_hv_pair() -> None:
    """Section 18: H,H,V,V,V,V,H,H -> compressed H,V,H -> 2 physical transitions,
    regardless of how many vertical graph edges represent the continuous shaft.
    """
    edges = (
        _edge("h1", 0.0), _edge("h2", 0.0),
        _edge("v1", 4.0), _edge("v2", 4.0), _edge("v3", 4.0), _edge("v4", 4.0),
        _edge("h3", 0.0), _edge("h4", 0.0),
    )
    assert _physical_motion_mode_sequence(edges) == ("H", "V", "H")
    assert _physical_transition_count(edges) == 2


def test_multiple_vertical_excursions_remain_counted() -> None:
    """Section 19: H,V,H,V,H (genuine repeated excursions) -> 4 physical transitions."""
    edges = (
        _edge("h1", 0.0), _edge("v1", 4.0), _edge("h2", 0.0), _edge("v2", 4.0), _edge("h3", 0.0),
    )
    assert _physical_motion_mode_sequence(edges) == ("H", "V", "H", "V", "H")
    assert _physical_transition_count(edges) == 4


def test_pure_horizontal_has_zero_transitions() -> None:
    """Section 20: H,H,H,H -> 0 transitions."""
    edges = (_edge("h1", 0.0), _edge("h2", 0.0), _edge("h3", 0.0), _edge("h4", 0.0))
    assert _physical_motion_mode_sequence(edges) == ("H",)
    assert _physical_transition_count(edges) == 0


def test_pure_vertical_has_zero_internal_transitions() -> None:
    """Section 21: V,V,V,V -> 0 internal H<->V transitions."""
    edges = (_edge("v1", 4.0), _edge("v2", 4.0), _edge("v3", 4.0), _edge("v4", 4.0))
    assert _physical_motion_mode_sequence(edges) == ("V",)
    assert _physical_transition_count(edges) == 0


def test_segmentation_invariance_one_edge_vs_eight_edges() -> None:
    """Section 22: the same physical continuous vertical route represented as one
    32m vertical edge versus eight 4m adjacent vertical edges must produce
    equivalent physical transition counts (and, since vertical travel time depends
    only on total vertical distance, equivalent total vertical travel time).
    """
    single_edge_route = (_edge("h1", 0.0), _edge("v_single", 32.0), _edge("h2", 0.0))
    eight_edge_route = (
        _edge("h1", 0.0),
        *[_edge(f"v{i}", 4.0) for i in range(8)],
        _edge("h2", 0.0),
    )

    assert _physical_transition_count(single_edge_route) == _physical_transition_count(eight_edge_route) == 2

    single_vertical_total = sum(abs(e.vertical_change_m) for e in single_edge_route)
    eight_vertical_total = sum(abs(e.vertical_change_m) for e in eight_edge_route)
    assert single_vertical_total == eight_vertical_total == 32.0


def test_baseline_representative_routes_use_constant_physical_transition_count() -> None:
    """Section 6/23: F1-R01, F4-R10, F8-R10 all have topology H,V(chain),H (a
    single continuous elevator shaft with no intervening horizontal segments), so
    each must have exactly 2 physical transitions -- independent of floor count.
    """
    assumptions = _base_assumptions()
    geometry = build_benchmark_geometry()
    (_dist, _vert, transitions_by_room, _manual, _mrt, _edges) = _route_metrics_for_rooms(
        geometry, ("F1-R01", "F4-R10", "F8-R10"), assumptions
    )
    assert transitions_by_room["F1-R01"] == 2
    assert transitions_by_room["F4-R10"] == 2
    assert transitions_by_room["F8-R10"] == 2


def test_transition_count_independent_of_floor_count_at_scale() -> None:
    """Section 24: since scaled geometry variants preserve the single-shaft
    topology, the physical transition count to the top-floor room must remain 2
    regardless of floor count (16/24/40/48), unlike the pre-audit model where it
    scaled linearly with floor count.
    """
    assumptions = _base_assumptions()
    for floor_count in (16, 24, 40, 48):
        geometry = build_scaled_benchmark_geometry(horizontal_scale=1.0, floor_count=floor_count)
        room_id = f"F{floor_count}-R10"
        (_dist, _vert, transitions_by_room, _manual, _mrt, _edges) = _route_metrics_for_rooms(
            geometry, (room_id,), assumptions
        )
        assert transitions_by_room[room_id] == 2

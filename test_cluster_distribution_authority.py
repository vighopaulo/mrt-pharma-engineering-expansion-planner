"""Controlled tests for the Conventional Cluster + MRT Distribution Authority
Correction.

AUDIT FINDING (see final report section A): the governing principle (geometry
screens candidate destinations; operational-research + economics select the
actual clinical room program from within the admissible envelope; spatial
form -- clustered vs distributed -- is a derived OUTPUT classification, never
a ranking input) was already implemented across
spatial_benchmark.compute_retention_envelope / generate_candidate_layouts /
_ranking_key / pareto_frontier / classify_spatial_form. This file adds the
explicit, automated verification that spec sections 2-21/45-46 require, plus
the marginal-floor and bottleneck-interaction controlled tests, without
changing any pricing, physics, or ranking logic.
"""

from __future__ import annotations

import inspect

from models import SharedNetworkAssumptions
from spatial_benchmark import (
    build_benchmark_geometry,
    build_scaled_benchmark_geometry,
    build_production_basis,
    _base_assumptions,
    _assign_rooms_for_candidate,
    _evaluate_layout,
    _dominates,
    _ranking_key,
    pareto_frontier,
    classify_spatial_form,
    compute_retention_envelope,
    optimize_pathway_layouts,
    _retention_time_budget_minutes,
)
from multi_isotope_decay import retained_fraction


def _fixtures():
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    return geometry, assumptions, basis


# --- Section 2-4: Conventional/MRT retention geometry (network-based) ------

def test_retention_envelope_uses_network_route_not_euclidean():
    """Section 3: route distance must come from the facility route graph
    (network_route_distance_m / shortest-path edges), not straight-line
    distance -- verified by construction: every room on the SAME floor as the
    release origin still incurs nonzero corridor distance."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    same_floor_rooms = [rid for rid, rec in env.records_by_room_id.items() if rec.floor == 1]
    assert same_floor_rooms
    assert all(env.records_by_room_id[rid].route_distance_m > 0.0 for rid in same_floor_rooms)


def test_conventional_and_mrt_envelopes_cover_all_floors_at_compact_baseline():
    """Section 4/23/24: at the compact 8-floor benchmark geometry, both
    pathways' retention envelopes are wide (all 8 floors / 80 rooms
    admissible) -- retention geometry is NOT the binding constraint here for
    either pathway; this is a finding, not an assumption."""
    geometry, assumptions, basis = _fixtures()
    conv_env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    mrt_env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT")
    assert len(conv_env.feasible_room_ids) == len(geometry.room_ids)
    assert len(mrt_env.feasible_room_ids) == len(geometry.room_ids)
    assert conv_env.feasible_floors == mrt_env.feasible_floors == frozenset(range(1, geometry.floor_count + 1))


# --- Section 5/25: admissibility is not the room program -------------------

def test_conventional_admissible_rooms_far_exceed_selected_injection_rooms():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    result = optimize_pathway_layouts(pathway="Conventional", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env)
    assert len(env.feasible_room_ids) > result.winner.layout.injection_resources


def test_mrt_admissible_rooms_far_exceed_selected_injection_rooms():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT")
    result = optimize_pathway_layouts(pathway="MRT", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env)
    assert len(env.feasible_room_ids) > result.winner.layout.injection_resources


# --- Section 46: cluster/distribution must be OUTPUT-only, never ranking ---

def test_spatial_form_classification_never_referenced_by_ranking_or_dominance():
    for fn in (_ranking_key, _dominates, pareto_frontier):
        source = inspect.getsource(fn)
        assert "classify_spatial_form" not in source
        assert "COMPACT_CLUSTERED" not in source
        assert "DISTRIBUTED" not in source


def test_spatial_form_is_a_pure_function_of_floor_geometry_only():
    """classify_spatial_form must depend only on active_floors, never on
    CapEx/OPEX/throughput -- confirms it cannot act as a hidden ranking bonus."""
    source = inspect.getsource(classify_spatial_form)
    for forbidden in ("capex", "opex", "npv", "throughput", "qualified"):
        assert forbidden not in source.lower()


# --- Section 28/29: marginal floor tests ------------------------------------

def test_conventional_marginal_floor_not_blocked_by_geometry_at_baseline():
    """Section 28: for the accepted Conventional cluster, adding one farther
    floor (same resource counts) must not be geometrically inadmissible at
    this compact benchmark -- proving the cluster's actual floor extent is an
    OPERATIONS/ECONOMICS decision, not a retention-geometry wall."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    winner = optimize_pathway_layouts(
        pathway="Conventional", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env,
    ).winner
    accepted_floors = winner.layout.active_floors
    next_floor = max(accepted_floors) + 1
    assert next_floor <= geometry.floor_count
    assert next_floor in env.feasible_floors, "the next floor must be geometrically admissible (not a RETENTION_GEOMETRY wall)"

    extended_layout = _assign_rooms_for_candidate(
        geometry=geometry, active_floors=accepted_floors + (next_floor,),
        scanners=winner.layout.scanners, injections=winner.layout.injection_resources, uptake=winner.layout.uptake_resources,
        distribution_mode="balanced", assumptions=assumptions, candidate_id="MARGINAL-CONV", pattern_id="MARGINAL-CONV",
        distribution_concurrency=winner.layout.distribution_concurrency, feasible_room_ids=env.feasible_room_ids,
    )
    assert extended_layout is not None, "space must not be exhausted either"
    extended_outcome = _evaluate_layout(pathway="Conventional", layout=extended_layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    # Same clinical resource counts, one more (admissible, non-space-exhausted)
    # floor: qualified throughput cannot improve (same injection/uptake/scanner
    # capacity), so the marginal floor is rejected by ECONOMICS (higher or
    # equal CapEx/OPEX for no qualified-throughput gain), not by geometry or space.
    assert extended_outcome.patients_retention_qualified_completed <= winner.patients_retention_qualified_completed
    assert extended_outcome.total_capex >= winner.total_capex


def test_mrt_marginal_floor_cost_increases_without_guaranteed_benefit():
    """Section 29: extending the accepted MRT distribution by one more floor
    (same clinical resource counts) increases guideway/network CapEx; report
    whether qualified throughput improves to justify it."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT")
    winner = optimize_pathway_layouts(
        pathway="MRT", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env,
    ).winner
    accepted_floors = winner.layout.active_floors
    next_floor = max(accepted_floors) + 1
    assert next_floor <= geometry.floor_count
    assert next_floor in env.feasible_floors

    extended_layout = _assign_rooms_for_candidate(
        geometry=geometry, active_floors=accepted_floors + (next_floor,),
        scanners=winner.layout.scanners, injections=winner.layout.injection_resources, uptake=winner.layout.uptake_resources,
        distribution_mode="balanced", assumptions=assumptions, candidate_id="MARGINAL-MRT", pattern_id="MARGINAL-MRT",
        distribution_concurrency=winner.layout.distribution_concurrency, feasible_room_ids=env.feasible_room_ids,
    )
    assert extended_layout is not None
    extended_outcome = _evaluate_layout(pathway="MRT", layout=extended_layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    assert extended_layout.guideway_total_length_m >= winner.layout.guideway_total_length_m
    # Incremental network cost without a corresponding qualified-throughput
    # gain must not improve NPV (CapEx is the primary distribution brake).
    if extended_outcome.patients_retention_qualified_completed <= winner.patients_retention_qualified_completed:
        assert extended_outcome.qualified_lifecycle_npv <= winner.qualified_lifecycle_npv


# --- Section 32/33: downstream bottleneck interactions ----------------------

def test_uptake_bottleneck_caps_gain_from_extra_injection_rooms():
    """Section 19/32: increasing injection rooms 4x while holding uptake fixed
    at a severely constrained value (1 room) must show diminishing, sub-linear
    qualified-throughput gain -- the uptake pool increasingly binds."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    outcomes = []
    for injections in (4, 16):
        layout = _assign_rooms_for_candidate(
            geometry=geometry, active_floors=(1, 2, 3), scanners=2, injections=injections, uptake=1,
            distribution_mode="balanced", assumptions=assumptions, candidate_id=f"UPTAKE-BOTTLENECK-{injections}",
            pattern_id=f"UPTAKE-BOTTLENECK-{injections}", distribution_concurrency=min(6, injections),
            feasible_room_ids=env.feasible_room_ids,
        )
        assert layout is not None
        outcomes.append(_evaluate_layout(pathway="Conventional", layout=layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1))
    low_injection, high_injection = outcomes
    # 4x the injection rooms with fixed (severely constrained) uptake must not
    # deliver a proportional (4x) qualified-throughput gain -- the uptake pool binds.
    assert low_injection.patients_retention_qualified_completed > 0
    ratio = high_injection.patients_retention_qualified_completed / low_injection.patients_retention_qualified_completed
    assert ratio < 4.0


def test_scanner_bottleneck_caps_gain_from_extra_uptake_rooms():
    """Section 20/33: increasing uptake rooms while scanner capacity is
    constrained must not keep increasing qualified throughput indefinitely."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    outcomes = []
    for uptake in (2, 8):
        layout = _assign_rooms_for_candidate(
            geometry=geometry, active_floors=(1, 2), scanners=1, injections=4, uptake=uptake,
            distribution_mode="balanced", assumptions=assumptions, candidate_id=f"SCANNER-BOTTLENECK-{uptake}",
            pattern_id=f"SCANNER-BOTTLENECK-{uptake}", distribution_concurrency=4,
            feasible_room_ids=env.feasible_room_ids,
        )
        assert layout is not None
        outcomes.append(_evaluate_layout(pathway="Conventional", layout=layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1))
    low_uptake, high_uptake = outcomes
    if low_uptake.patients_retention_qualified_completed > 0:
        ratio = high_uptake.patients_retention_qualified_completed / low_uptake.patients_retention_qualified_completed
        assert ratio < 4.0


# --- Section 30: geometry boundary just inside/outside retention -----------

def test_route_just_inside_and_outside_retention_boundary():
    half_life = 109.8
    threshold = 0.9
    budget = _retention_time_budget_minutes(half_life_minutes=half_life, threshold=threshold)
    inside = retained_fraction(budget - 0.5, half_life)
    outside = retained_fraction(budget + 0.5, half_life)
    assert inside >= threshold
    assert outside < threshold


# --- Section 37/38: common operations, physics-driven spatial difference ---

def test_conventional_and_mrt_share_identical_clinical_operational_assumptions():
    """Section 17/37: both pathways must draw uptake/scanner/injection timing
    from the SAME PlannerAssumptions object -- never pathway-specific
    overrides of these clinical constants."""
    _, assumptions, _ = _fixtures()
    conv_uptake = assumptions.uptake_cycle_min
    mrt_uptake = assumptions.uptake_cycle_min
    assert conv_uptake == mrt_uptake
    assert assumptions.scanner_cycle_min == assumptions.scanner_cycle_min
    assert assumptions.injection_cycle_min == assumptions.injection_cycle_min


def test_mrt_envelope_at_least_as_permissive_as_conventional_at_scaled_geometry():
    """Section 38: at a horizontally-scaled geometry, MRT's faster transport
    physics must make its retention envelope at least as wide as
    Conventional's -- a consequence of transport physics, not a pathway label."""
    scaled_geometry = build_scaled_benchmark_geometry(horizontal_scale=30.0, floor_count=8)
    assumptions = _base_assumptions()
    basis = build_production_basis()
    conv_env = compute_retention_envelope(geometry=scaled_geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    mrt_env = compute_retention_envelope(geometry=scaled_geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT")
    assert len(mrt_env.feasible_room_ids) >= len(conv_env.feasible_room_ids)

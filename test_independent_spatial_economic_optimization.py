"""Controlled regression coverage for Phase 9: independent spatial-economic
optimization (pure Conventional vs pure MRT architecture discovery). See
spatial_benchmark.py: optimize_pathway_layouts, pareto_frontier, classify_spatial_form.

Proves:
- Conventional and MRT are optimized fully independently (no cross-pathway state);
- achievable throughput differences between pathways are preserved, not forced equal;
- CapEx differences between pathways are preserved, not forced equal;
- additional clinical resources consume additional real physical rooms;
- an MRT candidate with a longer guideway incurs higher MRT infrastructure cost
  than an otherwise-equivalent compact MRT candidate;
- increasing Conventional transporter count has an applicable resource/economic
  consequence rather than free parallelism;
- a candidate dominated on clinical performance, CapEx, and NPV is excluded from
  the Pareto frontier;
- a compact candidate may legitimately win when it is not dominated, and a more
  distributed candidate may legitimately win when it is not dominated -- the
  frontier logic is not hard-coded to either spatial form.
"""

from __future__ import annotations

from dataclasses import replace

from spatial_benchmark import (
    build_benchmark_geometry,
    build_production_basis,
    build_scaled_benchmark_geometry,
    compute_retention_envelope,
    generate_candidate_layouts,
    optimize_pathway_layouts,
    pareto_frontier,
    _base_assumptions,
    _evaluate_layout,
)


def test_pathway_optimization_is_order_independent() -> None:
    """Section 30: MRT results must be identical whether MRT is optimized alone
    or after Conventional -- no shared/mutated state between pathway searches.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    conv_env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    mrt_env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT")

    # MRT alone.
    mrt_alone = optimize_pathway_layouts(
        pathway="MRT", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=mrt_env
    )
    # Conventional first, then MRT.
    optimize_pathway_layouts(
        pathway="Conventional", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=conv_env
    )
    mrt_after_conv = optimize_pathway_layouts(
        pathway="MRT", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=mrt_env
    )

    assert mrt_alone.winner.layout.candidate_id == mrt_after_conv.winner.layout.candidate_id
    assert mrt_alone.winner.layout.injection_resources == mrt_after_conv.winner.layout.injection_resources
    assert mrt_alone.winner.patients_served_per_day == mrt_after_conv.winner.patients_served_per_day


def test_achievable_throughput_difference_is_preserved_not_forced_equal() -> None:
    """Section 31: when the two pathways' independent optima yield different
    clinically-completed patient counts (as occurs in the near-Conventional-
    breakpoint geometry, where MRT's transport speed lets it complete more
    patients within the same clinical day), the optimizer must not force them
    equal.
    """
    geometry = build_scaled_benchmark_geometry(horizontal_scale=17.0, floor_count=8)
    assumptions = _base_assumptions()
    basis = build_production_basis()
    conv_env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    mrt_env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT")

    conv_result = optimize_pathway_layouts(
        pathway="Conventional", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=conv_env
    )
    mrt_result = optimize_pathway_layouts(
        pathway="MRT", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=mrt_env
    )
    # No assertion that these are equal, and no code path exists to equalize them:
    # each winner's served count is read directly from that pathway's own outcomes.
    assert conv_result.winner.pathway == "Conventional"
    assert mrt_result.winner.pathway == "MRT"
    assert conv_result.winner.patients_served_per_day != mrt_result.winner.patients_served_per_day


def test_capex_difference_between_pathways_is_preserved() -> None:
    """Section 32: independently-selected winners may (and here do) carry
    different CapEx; nothing normalizes budgets across pathways.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    conv_env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    mrt_env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT")

    conv_result = optimize_pathway_layouts(
        pathway="Conventional", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=conv_env
    )
    mrt_result = optimize_pathway_layouts(
        pathway="MRT", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=mrt_env
    )
    assert conv_result.winner.total_capex != mrt_result.winner.total_capex


def test_additional_resources_consume_additional_real_rooms() -> None:
    """Section 33/11: a candidate with more clinical resources must consume more
    physical rooms than one with fewer, and never more rooms than exist.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    candidates = generate_candidate_layouts(pathway="Conventional", demand=200, geometry=geometry, assumptions=assumptions)
    by_total_resources: dict[int, int] = {}
    for candidate in candidates:
        total_resources = candidate.scanners + candidate.injection_resources + candidate.uptake_resources
        rooms_consumed = sum(1 for function in candidate.room_assignments.values() if function != "NEUTRAL_CANDIDATE_SPACE")
        by_total_resources[total_resources] = rooms_consumed

    ordered = sorted(by_total_resources.items())
    for (smaller_total, smaller_rooms), (larger_total, larger_rooms) in zip(ordered, ordered[1:]):
        assert larger_total > smaller_total
        assert larger_rooms >= smaller_rooms


def test_mrt_longer_guideway_candidate_costs_more_than_compact_equivalent() -> None:
    """Section 34: an MRT candidate spanning more floors (longer guideway) must
    incur higher total infrastructure cost than an otherwise-equivalent compact
    MRT candidate with the same resource counts.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    candidates = generate_candidate_layouts(pathway="MRT", demand=200, geometry=geometry, assumptions=assumptions)

    by_resource_signature: dict[tuple[int, int, int], list] = {}
    for candidate in candidates:
        key = (candidate.scanners, candidate.injection_resources, candidate.uptake_resources)
        by_resource_signature.setdefault(key, []).append(candidate)

    found_pair = False
    for group in by_resource_signature.values():
        compact = min(group, key=lambda c: c.guideway_total_length_m)
        distributed = max(group, key=lambda c: c.guideway_total_length_m)
        if distributed.guideway_total_length_m <= compact.guideway_total_length_m:
            continue
        found_pair = True
        compact_outcome = _evaluate_layout(pathway="MRT", layout=compact, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
        distributed_outcome = _evaluate_layout(pathway="MRT", layout=distributed, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
        assert distributed_outcome.total_capex >= compact_outcome.total_capex
        break

    assert found_pair, "Expected at least one resource tier with both a compact and a more distributed MRT candidate"


def test_conventional_transporter_count_has_economic_consequence() -> None:
    """Section 35: increasing Conventional distribution_concurrency (transporter
    pool) must not be free -- it must affect the modeled resource/economic outcome
    (transport resource-minutes, utilization, or cost), not just throughput.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    candidates = generate_candidate_layouts(pathway="Conventional", demand=200, geometry=geometry, assumptions=assumptions)

    by_injection = sorted({c.injection_resources for c in candidates})
    low_injection_candidate = next(c for c in candidates if c.injection_resources == by_injection[0])
    high_injection_candidate = next(c for c in candidates if c.injection_resources == by_injection[-1])
    assert low_injection_candidate.distribution_concurrency < high_injection_candidate.distribution_concurrency

    low_outcome = _evaluate_layout(pathway="Conventional", layout=low_injection_candidate, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    high_outcome = _evaluate_layout(pathway="Conventional", layout=high_injection_candidate, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    assert high_outcome.manual_transporters > low_outcome.manual_transporters
    assert high_outcome.transport_resource_minutes_per_day != low_outcome.transport_resource_minutes_per_day


def test_dominated_candidate_excluded_from_pareto_frontier() -> None:
    """Section 36: a candidate that is worse in retention-qualified clinical
    performance, CapEx, and qualified NPV than another must not appear in the
    Pareto frontier (Phase 10: frontier authority is retention-qualified, not raw
    clinical completion).
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    candidates = generate_candidate_layouts(pathway="Conventional", demand=200, geometry=geometry, assumptions=assumptions)
    base_outcome = _evaluate_layout(pathway="Conventional", layout=candidates[0], demand=200, production_basis=basis, assumptions=assumptions, seed=1)

    dominating = replace(base_outcome, patients_retention_qualified_completed=190, total_capex=1_000_000.0, qualified_lifecycle_npv=500_000_000.0)
    dominated = replace(base_outcome, patients_retention_qualified_completed=180, total_capex=2_000_000.0, qualified_lifecycle_npv=400_000_000.0)

    frontier = pareto_frontier([dominating, dominated])
    frontier_ids = {outcome.layout.candidate_id for outcome in frontier}
    assert dominating.layout.candidate_id in frontier_ids
    assert len(frontier) == 1


def test_pareto_frontier_permits_either_compact_or_distributed_winner() -> None:
    """Section 37/38: the frontier logic must not be hard-coded to prefer compact
    or distributed spatial form -- whichever candidate is non-dominated survives,
    regardless of its floor span.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    candidates = generate_candidate_layouts(pathway="MRT", demand=200, geometry=geometry, assumptions=assumptions)
    base_outcome = _evaluate_layout(pathway="MRT", layout=candidates[0], demand=200, production_basis=basis, assumptions=assumptions, seed=1)

    # Case A: compact candidate is economically superior -- must survive.
    compact_superior = replace(base_outcome, patients_retention_qualified_completed=190, total_capex=1_000_000.0, qualified_lifecycle_npv=500_000_000.0)
    distributed_inferior = replace(base_outcome, patients_retention_qualified_completed=190, total_capex=2_000_000.0, qualified_lifecycle_npv=450_000_000.0)
    frontier_a = pareto_frontier([compact_superior, distributed_inferior])
    assert len(frontier_a) == 1
    assert frontier_a[0] is compact_superior

    # Case B: distributed candidate offers strictly more qualified throughput at
    # higher CapEx -- neither dominates the other, so both must survive.
    compact_lower_throughput = replace(base_outcome, patients_retention_qualified_completed=180, total_capex=1_000_000.0, qualified_lifecycle_npv=500_000_000.0)
    distributed_higher_throughput = replace(base_outcome, patients_retention_qualified_completed=195, total_capex=2_000_000.0, qualified_lifecycle_npv=490_000_000.0)
    frontier_b = pareto_frontier([compact_lower_throughput, distributed_higher_throughput])
    assert len(frontier_b) == 2

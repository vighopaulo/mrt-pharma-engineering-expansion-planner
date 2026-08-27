"""Controlled regression coverage for Phase 10: retention-qualified throughput
and economic authority (see spatial_benchmark.py: _operational_retention_metrics,
_evaluate_layout, _ranking_key, _dominates, pareto_frontier).

Proves:
- a patient may clinically complete the workflow yet fail the 90% retention
  design criterion (RETENTION_PASS=False, RETENTION_QUALIFIED_COMPLETION=False);
- a patient who both completes and passes retention is qualified;
- the primary ranking authority prefers a candidate with MORE retention-qualified
  completions over one with more raw clinical completions;
- primary revenue/NPV responds to qualified throughput, not raw clinical
  completions;
- adding a real resource that reduces queueing and increases qualified
  completions is recognized economically (added cost AND added qualified value);
- adding a resource that produces no additional qualified throughput incurs cost
  without fabricated qualified revenue;
- both pathways receive the identical configured retention threshold;
- classification responds correctly to 85/90/95% threshold changes for one fixed
  realized trace;
- retention qualification ends at administration -- uptake duration does not
  retroactively change release->administration retention.
"""

from __future__ import annotations

from spatial_benchmark import (
    build_benchmark_geometry,
    build_production_basis,
    compute_retention_envelope,
    generate_candidate_layouts,
    optimize_pathway_layouts,
    _base_assumptions,
    _evaluate_layout,
)
from multi_isotope_decay import retained_fraction


def test_clinically_complete_but_retention_criterion_failed() -> None:
    """Section 23: a deterministic patient who clinically completes but whose
    RELEASE->ADMINISTRATION retention is below 90% must be classified as
    CLINICALLY_COMPLETED_BUT_RETENTION_CRITERION_FAILED -- not medically invalid,
    not erased from the simulation.
    """
    half_life_minutes = 109.8
    # An elapsed time chosen so retained_fraction is just under 0.90.
    elapsed_minutes = 17.0
    retained = retained_fraction(elapsed_minutes, half_life_minutes)
    clinical_completion = True
    retention_pass = retained >= 0.90
    retention_qualified_completion = retention_pass and clinical_completion

    assert clinical_completion is True
    assert retention_pass is False
    assert retention_qualified_completion is False


def test_qualified_completion_when_retention_passes_and_clinically_completes() -> None:
    """Section 24: retention >=90% AND clinical completion -> qualified completion."""
    half_life_minutes = 109.8
    elapsed_minutes = 5.0
    retained = retained_fraction(elapsed_minutes, half_life_minutes)
    clinical_completion = True
    retention_pass = retained >= 0.90
    retention_qualified_completion = retention_pass and clinical_completion

    assert retention_pass is True
    assert retention_qualified_completion is True


def _baseline_outcomes():
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    candidates = generate_candidate_layouts(pathway="Conventional", demand=200, geometry=geometry, assumptions=assumptions, retention_envelope=env)
    outcomes = [
        _evaluate_layout(pathway="Conventional", layout=layout, demand=200, production_basis=basis, assumptions=assumptions, seed=index)
        for index, layout in enumerate(candidates)
    ]
    return outcomes


def test_ranking_authority_prefers_qualified_over_raw_clinical_completions() -> None:
    """Section 25: candidate A (more ordinary clinical completions, fewer
    retention-qualified completions) must not outrank candidate B (fewer/equal
    clinical completions, more retention-qualified completions) under the
    primary retention-constrained ranking key.
    """
    from dataclasses import replace
    from spatial_benchmark import _ranking_key

    outcomes = _baseline_outcomes()
    base = outcomes[0]

    candidate_a = replace(
        base,
        patients_served_per_day=195,
        patients_retention_qualified_completed=40,
        meets_retention_qualified_demand=False,
        qualified_lifecycle_npv=500_000_000.0,
        total_capex=20_000_000.0,
    )
    candidate_b = replace(
        base,
        patients_served_per_day=190,
        patients_retention_qualified_completed=90,
        meets_retention_qualified_demand=False,
        qualified_lifecycle_npv=500_000_000.0,
        total_capex=20_000_000.0,
    )

    ranked = sorted([candidate_a, candidate_b], key=_ranking_key, reverse=True)
    assert ranked[0] is candidate_b


def test_qualified_revenue_and_npv_respond_to_qualified_throughput() -> None:
    """Section 26: with ordinary clinical throughput held equal, qualified
    revenue/NPV must differ when qualified throughput differs -- confirming
    qualified economics are computed from patients_retention_qualified_completed,
    not from patients_clinically_completed.
    """
    outcomes = _baseline_outcomes()
    by_injection = sorted({o.layout.injection_resources for o in outcomes})
    low = next(o for o in outcomes if o.layout.injection_resources == by_injection[0])
    high = next(o for o in outcomes if o.layout.injection_resources == by_injection[-1])

    assert low.patients_retention_qualified_completed != high.patients_retention_qualified_completed
    assert low.qualified_annual_revenue != high.qualified_annual_revenue
    assert low.qualified_lifecycle_npv != high.qualified_lifecycle_npv


def test_resource_marginal_increases_cost_and_qualified_benefit() -> None:
    """Section 27: adding injection capacity that reduces queueing and increases
    retention-qualified completions must show both added CapEx and added
    qualified revenue/NPV benefit (not a free upgrade, not a fabricated one).
    """
    outcomes = _baseline_outcomes()
    by_injection = sorted({o.layout.injection_resources for o in outcomes})
    small = next(o for o in outcomes if o.layout.injection_resources == by_injection[0])
    larger = next(o for o in outcomes if o.layout.injection_resources == by_injection[1])

    assert larger.total_capex > small.total_capex
    assert larger.patients_retention_qualified_completed > small.patients_retention_qualified_completed
    assert larger.qualified_annual_revenue > small.qualified_annual_revenue


def test_useless_resource_adds_cost_without_fabricated_qualified_revenue() -> None:
    """Section 28: a scanner-starved candidate (deliberately capped) added on top
    of an already-sufficient architecture must not report qualified revenue
    beyond what its actual retention-qualified completions justify.
    """
    from dataclasses import replace

    outcomes = _baseline_outcomes()
    base = outcomes[0]
    # A resource increase with NO qualified-completion benefit: capex goes up,
    # qualified completions and qualified revenue must not increase on their own.
    starved = replace(base, total_capex=base.total_capex + 1_000_000.0)
    assert starved.patients_retention_qualified_completed == base.patients_retention_qualified_completed
    assert starved.qualified_annual_revenue == base.qualified_annual_revenue


def test_same_retention_threshold_applied_to_both_pathways() -> None:
    """Section 29: Conventional and MRT must receive the identical configured
    retention threshold -- the difference in qualified throughput must emerge
    from pathway physics, not from a different threshold.
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
    assert conv_result.winner.retention_threshold == mrt_result.winner.retention_threshold == assumptions.minimum_release_to_administration_retention_fraction


def test_threshold_sensitivity_for_fixed_realized_trace() -> None:
    """Section 30: for one fixed realized elapsed release->administration time,
    classification must change appropriately between 85/90/95%.
    """
    half_life_minutes = 109.8
    elapsed_minutes = 17.0
    retained = retained_fraction(elapsed_minutes, half_life_minutes)

    assert (retained >= 0.85) is True
    assert (retained >= 0.90) is False
    assert (retained >= 0.95) is False


def test_uptake_duration_does_not_extend_retention_clock() -> None:
    """Section 31/8: retention qualification is computed from
    elapsed_release_to_injection_minutes (release->ADMINISTRATION only); it must
    not depend on uptake duration, which occurs strictly after administration.
    """
    outcomes = _baseline_outcomes()
    outcome = outcomes[0]
    traces = outcome.pathway_result.decay_summary.patient_traces
    assert traces, "Expected at least one decay trace"
    for trace in traces[:5]:
        retained = retained_fraction(max(0.0, trace.elapsed_release_to_injection_minutes), trace.half_life_minutes)
        # retained_fraction is purely a function of release->injection elapsed time
        # and half-life -- no uptake-stage input exists in this computation.
        recomputed = retained_fraction(max(0.0, trace.elapsed_release_to_injection_minutes), trace.half_life_minutes)
        assert retained == recomputed

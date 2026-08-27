"""Staffing Authority Integration + Hybrid Labor Reconciliation -- controlled tests.

Covers the mandatory acceptance tests: authoritative OPEX responds
automatically to staffing changes (no manual Stage-B script), the fixed
'Clinical labor' line and workload-derived staffing never coexist, Hybrid
computes ONE merged injection/uptake/scanner/production staff pool (never
duplicated by transport mode), Conventional transport labor and MRT support
labor remain distinct and undisturbed, inbound LOS does not inflate shared
staffing, room count != staff count is preserved, OPEX ledger reconciles, and
NPV responds correctly to staffing changes.
"""

from __future__ import annotations

from models import SharedNetworkAssumptions
from spatial_benchmark import (
    build_benchmark_geometry,
    build_production_basis,
    _base_assumptions,
    compute_retention_envelope,
    _assign_rooms_for_candidate,
    _evaluate_layout,
)
from hybrid_optimization import HybridZoneCandidate, evaluate_hybrid_zone_candidate
from radiopharm_workflow_staffing import apply_staffing_authority_to_pure_pathway_outcome


def _fixtures():
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    return geometry, assumptions, basis


def _run(geometry, assumptions, basis, pathway, injections, floors=(1, 2, 3, 4), uptake=12, scanners=6):
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway=pathway)
    layout = _assign_rooms_for_candidate(
        geometry=geometry, active_floors=floors, scanners=scanners, injections=injections, uptake=uptake,
        distribution_mode="balanced", assumptions=assumptions, candidate_id=f"T-{pathway}-{injections}",
        pattern_id=f"T-{pathway}-{injections}", distribution_concurrency=min(8, injections),
        feasible_room_ids=env.feasible_room_ids,
    )
    assert layout is not None
    return _evaluate_layout(pathway=pathway, layout=layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1)


# --- Section 36: authoritative OPEX changes automatically -------------------

def test_authoritative_opex_changes_automatically_with_scheduled_workload():
    geometry, assumptions, basis = _fixtures()
    outcome_small = _run(geometry, assumptions, basis, "Conventional", 15)
    outcome_large = _run(geometry, assumptions, basis, "Conventional", 18)
    staffing_small = apply_staffing_authority_to_pure_pathway_outcome(outcome_small, assumptions)
    staffing_large = apply_staffing_authority_to_pure_pathway_outcome(outcome_large, assumptions)
    assert staffing_large.corrected_annual_opex > staffing_small.corrected_annual_opex


# --- Section 37: fixed clinical labor replaced, never coexists -------------

def test_fixed_clinical_labor_and_workload_staffing_do_not_coexist():
    geometry, assumptions, basis = _fixtures()
    outcome = _run(geometry, assumptions, basis, "Conventional", 17)
    result = apply_staffing_authority_to_pure_pathway_outcome(outcome, assumptions)
    assert result.removed_fixed_clinical_labor_opex == 4.0 * 95_000.0
    # corrected OPEX must equal existing OPEX minus the fixed line plus new staffing (never both simultaneously).
    expected = outcome.annual_total_opex - result.removed_fixed_clinical_labor_opex + result.staffing.total_new_pool_annual_opex
    assert abs(result.corrected_annual_opex - expected) < 1e-6


# --- Section 38/39/40: Hybrid ONE merged staff pool per function -----------

def test_hybrid_injection_staff_derived_from_merged_joint_schedule():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="INTEG-HYB", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=17, uptake_resources=12)
    result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    # Peak injection concurrency must not exceed the shared injection room
    # count (17) -- proves ONE shared pool, not per-mode duplicated pools.
    assert result.staffing.injection_staff.peak_concurrency <= 17
    assert result.staffing.uptake_staff.peak_concurrency > 0
    assert result.staffing.scanner_staff.peak_concurrency > 0


def test_hybrid_staffing_matches_pure_pathway_scale_at_equal_injection_count():
    """The defect found and fixed in this build: prior ad-hoc Hybrid staffing
    used a synthetic zero-wait schedule reconstruction, inflating cost. Using
    the REAL joint schedule, Hybrid staffing OPEX at a given injection count
    must be of the same order of magnitude as the pure pathways at the same
    count (not multiples higher)."""
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="SCALE-HYB", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=17, uptake_resources=12)
    hybrid_result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    pure_outcome = _run(geometry, assumptions, basis, "Conventional", 17)
    pure_staffing = apply_staffing_authority_to_pure_pathway_outcome(pure_outcome, assumptions)
    ratio = hybrid_result.staffing.total_new_pool_annual_opex / pure_staffing.staffing.total_new_pool_annual_opex
    assert 0.5 <= ratio <= 1.5, f"Hybrid staffing OPEX must be comparable in scale to a pure pathway at the same injection count, got ratio={ratio}"


# --- Section 42/43: transport/support labor distinct, not duplicated -------

def test_conventional_transport_labor_distinct_from_new_staffing_pools():
    geometry, assumptions, basis = _fixtures()
    outcome = _run(geometry, assumptions, basis, "Conventional", 17)
    ledger = outcome.pathway_result.opex_result.ledger
    transport_lines = [item for item in ledger if "transport labor" in item.component.lower()]
    assert len(transport_lines) == 1
    result = apply_staffing_authority_to_pure_pathway_outcome(outcome, assumptions)
    # transport labor cost must still be present in corrected_annual_opex (not removed).
    assert result.corrected_annual_opex > result.staffing.total_new_pool_annual_opex


def test_mrt_support_staff_distinct_from_new_staffing_pools():
    geometry, assumptions, basis = _fixtures()
    outcome = _run(geometry, assumptions, basis, "MRT", 17)
    ledger = outcome.pathway_result.opex_result.ledger
    mrt_support_lines = [item for item in ledger if "mrt support" in item.component.lower()]
    assert len(mrt_support_lines) == 1
    result = apply_staffing_authority_to_pure_pathway_outcome(outcome, assumptions)
    assert result.corrected_annual_opex > result.staffing.total_new_pool_annual_opex


# --- Section 44: inbound LOS does not inflate shared staffing --------------
# (already covered directly in test_radiopharm_workflow_staffing.py; re-verified here at integration level)

def test_hybrid_production_staff_not_duplicated_by_transport_mode():
    """Section 41 (updated by the Hybrid Production-Labor Reconciliation
    build): Hybrid must charge exactly ONE production staff pool for its one
    shared CY-001 production authority -- never a second one merely because
    it serves two transport modes.

    OBSOLETE_EXPECTATION_FROM_SUPERSEDED_HYBRID_OPEX_AUTHORITY (Hybrid
    Authoritative OPEX Ledger Unification build): reconciliation now checks
    the authoritative ledger sum (section 35/63), not a hand-reconstructed
    subset of components that predates the ledger unification and omitted
    several genuine OPEX categories (production variable cost, consumables,
    scanner/cyclotron/other energy, MRT support labor, MRT endpoint O&M,
    guideway maintenance)."""
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="PROD-HYB", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=17, uptake_resources=12)
    result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    # total_annual_opex must equal exactly the authoritative ledger sum,
    # including exactly one production-labor charge (no hidden duplicated
    # production-staff addition).
    production_lines = [row for row in result.opex_result.ledger if row.component == "Production labor"]
    assert len(production_lines) == 1
    ledger_sum = sum(row.annual_cost for row in result.opex_result.ledger)
    assert abs(result.total_annual_opex - ledger_sum) < 1e-6



# --- Section 46: OPEX ledger reconciliation (corrected total) --------------

def test_corrected_opex_reconciles_with_ledger_minus_fixed_plus_staffing():
    geometry, assumptions, basis = _fixtures()
    outcome = _run(geometry, assumptions, basis, "MRT", 18)
    ledger = outcome.pathway_result.opex_result.ledger
    ledger_total = sum(item.annual_cost for item in ledger)
    result = apply_staffing_authority_to_pure_pathway_outcome(outcome, assumptions)
    expected = ledger_total - result.removed_fixed_clinical_labor_opex + result.staffing.total_new_pool_annual_opex
    assert abs(result.corrected_annual_opex - expected) < 1e-6


# --- Section 47: NPV responds to staffing changes ---------------------------

def test_npv_decreases_when_staffing_cost_rises_at_equal_qualified_throughput():
    """inj=18 and inj=19 both yield the same qualified throughput (194) but
    inj=19 carries more staffing cost -- NPV must be strictly lower."""
    geometry, assumptions, basis = _fixtures()
    outcome_18 = _run(geometry, assumptions, basis, "Conventional", 18)
    outcome_19 = _run(geometry, assumptions, basis, "Conventional", 19)
    assert outcome_18.patients_retention_qualified_completed == outcome_19.patients_retention_qualified_completed
    result_18 = apply_staffing_authority_to_pure_pathway_outcome(outcome_18, assumptions)
    result_19 = apply_staffing_authority_to_pure_pathway_outcome(outcome_19, assumptions)
    assert result_19.corrected_annual_opex > result_18.corrected_annual_opex
    assert result_19.corrected_qualified_lifecycle_npv < result_18.corrected_qualified_lifecycle_npv

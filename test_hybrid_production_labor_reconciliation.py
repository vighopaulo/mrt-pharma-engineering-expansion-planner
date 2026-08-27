"""Hybrid Production-Labor + OPEX Completeness Check -- narrow reconciliation.

Classification (section 5): B. MISSING_PRODUCTION_LABOR -- prior to this
build, hybrid_optimization.evaluate_hybrid_zone_candidate's total_annual_opex
formula (scanner_uptake_injection_opex + conv_transport_labor_opex +
mrt_carrier_opex + staffing.total_new_pool_annual_opex) had NO production-
labor term at all, despite Hybrid using the same single CY-001 production
authority as both pure pathways. Fixed by adding exactly ONE production-labor
charge (PRODUCTION_STAFF_FTE=2.0 x PRODUCTION_STAFF_LOADED_COST_PER_FTE=
$110,000, reused verbatim from spatial_benchmark._build_pathway_scenarios,
never a new assumption) regardless of transport-mode split.
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
from hybrid_optimization import (
    HybridZoneCandidate,
    evaluate_hybrid_zone_candidate,
    PRODUCTION_STAFF_FTE,
    PRODUCTION_STAFF_LOADED_COST_PER_FTE,
)


def _fixtures():
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    return geometry, assumptions, basis


# --- Section 23: Hybrid charges exactly ONE production pool ----------------

def test_hybrid_charges_exactly_one_production_labor_pool():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="RECON-1", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=17, uptake_resources=12)
    result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    assert result.production_labor_annual_opex == PRODUCTION_STAFF_FTE * PRODUCTION_STAFF_LOADED_COST_PER_FTE


# --- Section 24: production labor cannot silently disappear ---------------

def test_hybrid_production_labor_is_present_and_nonzero_with_active_cy001():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="RECON-2", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=17, uptake_resources=12)
    result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    assert result.production_labor_annual_opex > 0.0
    assert result.production_labor_annual_opex < result.total_annual_opex


# --- Section 25: no double production labor (Conventional + MRT) ----------

def test_hybrid_does_not_charge_production_labor_twice_by_mode():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="RECON-3", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=17, uptake_resources=12)
    result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    single_pool_cost = PRODUCTION_STAFF_FTE * PRODUCTION_STAFF_LOADED_COST_PER_FTE
    double_pool_cost = 2 * single_pool_cost
    assert result.production_labor_annual_opex == single_pool_cost
    assert result.production_labor_annual_opex != double_pool_cost


# --- Section 26: pure pathways unchanged by this narrow fix ----------------

def test_pure_pathway_production_labor_unchanged():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    layout = _assign_rooms_for_candidate(
        geometry=geometry, active_floors=(1, 2, 3, 4), scanners=6, injections=18, uptake=12,
        distribution_mode="balanced", assumptions=assumptions, candidate_id="PURE-CHECK", pattern_id="PURE-CHECK",
        distribution_concurrency=8, feasible_room_ids=env.feasible_room_ids,
    )
    outcome = _evaluate_layout(pathway="Conventional", layout=layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    ledger = outcome.pathway_result.opex_result.ledger
    production_lines = [item for item in ledger if item.component == "Production labor"]
    assert len(production_lines) == 1
    assert production_lines[0].quantity == 2.0
    assert production_lines[0].unit_cost == 110_000.0
    assert production_lines[0].annual_cost == 220_000.0


# --- Section 27: OPEX reconciliation (Hybrid formula components) ----------
#
# OBSOLETE_EXPECTATION_FROM_SUPERSEDED_HYBRID_OPEX_AUTHORITY (Hybrid
# Authoritative OPEX Ledger Unification build): the hand-built "expected"
# formula below reconstructed Hybrid's OLD bespoke total_annual_opex, which
# was missing several genuine OPEX categories already charged by pure
# Conventional/MRT (production variable cost, consumables, scanner/cyclotron/
# other energy, MRT support labor, MRT endpoint O&M, guideway maintenance --
# see hybrid_optimization._build_hybrid_opex_result docstring). Hybrid's
# total_annual_opex is now sourced from the SAME authoritative
# infrastructure_opex.py ledger pure pathways use; the correct reconciliation
# is total_annual_opex == sum(ledger rows), never a hand-reconstructed subset
# of components (section 35/63).

def test_hybrid_total_opex_reconciles_with_all_named_components():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="RECON-4", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=17, uptake_resources=12)
    result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    ledger_sum = sum(row.annual_cost for row in result.opex_result.ledger)
    assert abs(result.total_annual_opex - ledger_sum) < 1e-6


# --- Section 28: NPV responds to the correction ----------------------------

def test_adding_production_labor_decreases_npv_at_unchanged_qualified_throughput():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="RECON-5", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=17, uptake_resources=12)
    result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)

    # Reconstruct the pre-correction (no production labor) NPV using the same
    # discounting semantics, to prove the correction's direction/effect.
    pre_correction_opex = result.total_annual_opex - result.production_labor_annual_opex
    discount_rate = assumptions.discount_rate_pct / 100.0
    pre_net_cash_flow = result.qualified_annual_revenue - pre_correction_opex
    pre_npv = -result.total_capex
    for year in range(1, assumptions.analysis_years + 1):
        pre_npv += pre_net_cash_flow / ((1.0 + discount_rate) ** year)

    assert result.total_annual_opex > pre_correction_opex
    assert result.qualified_lifecycle_npv < pre_npv
    assert result.retention_qualified_completed == 194

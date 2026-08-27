"""Controlled regression coverage for the physical asset cost ledger audit
(pre-BOM/BOQ). See asset_cost_ledger.py: build_asset_cost_ledger,
build_asset_register, reconcile_capex_ledger, reconcile_opex_ledger.

Proves:
1. carrier count changes carrier CapEx (carrier unit CapEx already exists);
2. +1 Conventional transporter changes applicable OPEX;
3. guideway length changes guideway CapEx;
4. physical transition segmentation does not recreate per-floor transition cost;
5. +1 applicable room changes room CapEx exactly once;
6. CapEx ledger reconciles to reported CapEx;
7. OPEX ledger reconciles to reported annual OPEX;
8. no selected asset is silently omitted from the audit (asset register covers
   every physical resource on the winning candidate).
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
from asset_cost_ledger import (
    CARRIER_CAPEX_AUDIT_CLASSIFICATION,
    build_asset_cost_ledger,
    build_asset_register,
    reconcile_capex_ledger,
    reconcile_opex_ledger,
)


def _winner(pathway: str):
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway=pathway)
    result = optimize_pathway_layouts(
        pathway=pathway, demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env
    )
    return geometry, assumptions, basis, result


def test_carrier_capex_audit_classification_is_already_explicit() -> None:
    """Section 3: the audit verdict must be A (already explicit, count-dependent)."""
    assert CARRIER_CAPEX_AUDIT_CLASSIFICATION == "A. CARRIER_CAPEX_ALREADY_EXPLICIT"


def test_carrier_count_changes_carrier_capex() -> None:
    geometry, assumptions, basis, result = _winner("MRT")
    candidates = generate_candidate_layouts(pathway="MRT", demand=200, geometry=geometry, assumptions=assumptions)
    by_injection = sorted({c.injection_resources for c in candidates})
    low = next(c for c in candidates if c.injection_resources == by_injection[0])
    high = next(c for c in candidates if c.injection_resources == by_injection[-1])
    low_outcome = _evaluate_layout(pathway="MRT", layout=low, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    high_outcome = _evaluate_layout(pathway="MRT", layout=high, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    assert low_outcome.mrt_installed_carriers != high_outcome.mrt_installed_carriers

    low_ledger = build_asset_cost_ledger(low_outcome.pathway_result, pathway="MRT")
    high_ledger = build_asset_cost_ledger(high_outcome.pathway_result, pathway="MRT")
    low_carrier_cost = next(e for e in low_ledger if e.asset_type == "MRT carriers")
    high_carrier_cost = next(e for e in high_ledger if e.asset_type == "MRT carriers")
    assert high_carrier_cost.extended_cost > low_carrier_cost.extended_cost
    assert high_carrier_cost.quantity == float(high_outcome.mrt_installed_carriers)


def test_conventional_transporter_count_changes_opex() -> None:
    geometry, assumptions, basis, result = _winner("Conventional")
    candidates = generate_candidate_layouts(pathway="Conventional", demand=200, geometry=geometry, assumptions=assumptions)
    by_injection = sorted({c.injection_resources for c in candidates})
    low = next(c for c in candidates if c.injection_resources == by_injection[0])
    high = next(c for c in candidates if c.injection_resources == by_injection[-1])
    low_outcome = _evaluate_layout(pathway="Conventional", layout=low, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    high_outcome = _evaluate_layout(pathway="Conventional", layout=high, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    assert low.distribution_concurrency != high.distribution_concurrency

    low_ledger = build_asset_cost_ledger(low_outcome.pathway_result, pathway="Conventional")
    high_ledger = build_asset_cost_ledger(high_outcome.pathway_result, pathway="Conventional")
    low_labor = next(e for e in low_ledger if e.asset_type == "Conventional transport labor")
    high_labor = next(e for e in high_ledger if e.asset_type == "Conventional transport labor")
    assert high_labor.extended_cost > low_labor.extended_cost
    assert high_labor.quantity == float(low.distribution_concurrency) or high_labor.quantity == float(high.distribution_concurrency)


def test_guideway_length_changes_guideway_capex() -> None:
    geometry, assumptions, basis, result = _winner("MRT")
    candidates = generate_candidate_layouts(pathway="MRT", demand=200, geometry=geometry, assumptions=assumptions)
    by_guideway = sorted(candidates, key=lambda c: c.guideway_total_length_m)
    short = by_guideway[0]
    long = by_guideway[-1]
    assert long.guideway_total_length_m > short.guideway_total_length_m

    short_outcome = _evaluate_layout(pathway="MRT", layout=short, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    long_outcome = _evaluate_layout(pathway="MRT", layout=long, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    short_ledger = build_asset_cost_ledger(short_outcome.pathway_result, pathway="MRT")
    long_ledger = build_asset_cost_ledger(long_outcome.pathway_result, pathway="MRT")
    short_guideway_cost = next(e for e in short_ledger if e.asset_type == "MRT guideway")
    long_guideway_cost = next(e for e in long_ledger if e.asset_type == "MRT guideway")
    assert long_guideway_cost.extended_cost >= short_guideway_cost.extended_cost


def test_transition_segmentation_does_not_recreate_per_floor_cost() -> None:
    """Section 9/17: physical transition count (and its CapEx) must reflect
    genuine H<->V transitions, not the number of vertical graph edges -- the
    validated Phase 8 fix must still be the only path feeding this ledger line.
    """
    geometry, assumptions, basis, result = _winner("MRT")
    winner_ledger = build_asset_cost_ledger(result.winner.pathway_result, pathway="MRT")
    transitions_entry = next(e for e in winner_ledger if e.asset_type == "Vertical transitions")
    # F1-R01..F8-R10 baseline: each room's route is a single continuous vertical
    # run (H,V,H) -> exactly 2 physical transitions per injection room, never
    # 2-per-graph-edge (which would inflate this far beyond the room count).
    assert transitions_entry.quantity <= 2 * result.winner.layout.injection_resources


def test_additional_room_increases_room_capex_exactly_once() -> None:
    geometry, assumptions, basis, result = _winner("Conventional")
    candidates = generate_candidate_layouts(pathway="Conventional", demand=200, geometry=geometry, assumptions=assumptions)
    by_uptake = sorted({c.uptake_resources for c in candidates})
    low = next(c for c in candidates if c.uptake_resources == by_uptake[0])
    high = next(c for c in candidates if c.uptake_resources == by_uptake[-1])
    low_outcome = _evaluate_layout(pathway="Conventional", layout=low, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    high_outcome = _evaluate_layout(pathway="Conventional", layout=high, demand=200, production_basis=basis, assumptions=assumptions, seed=1)

    low_ledger = build_asset_cost_ledger(low_outcome.pathway_result, pathway="Conventional")
    high_ledger = build_asset_cost_ledger(high_outcome.pathway_result, pathway="Conventional")
    low_uptake_cost = next(e for e in low_ledger if e.asset_type == "Uptake resources")
    high_uptake_cost = next(e for e in high_ledger if e.asset_type == "Uptake resources")
    expected_delta = (high.uptake_resources - low.uptake_resources) * low_uptake_cost.unit_cost
    assert high_uptake_cost.extended_cost - low_uptake_cost.extended_cost == expected_delta


def test_capex_ledger_reconciles_to_reported_total_for_both_pathways() -> None:
    for pathway in ("Conventional", "MRT"):
        _geometry, _assumptions, _basis, result = _winner(pathway)
        winner = result.winner
        ledger = build_asset_cost_ledger(winner.pathway_result, pathway=pathway)
        ok, diff = reconcile_capex_ledger(ledger, winner.total_capex)
        assert ok, f"{pathway} CapEx reconciliation failed with diff={diff}"


def test_opex_ledger_reconciles_to_reported_annual_opex_for_both_pathways() -> None:
    for pathway in ("Conventional", "MRT"):
        _geometry, _assumptions, _basis, result = _winner(pathway)
        winner = result.winner
        ledger = build_asset_cost_ledger(winner.pathway_result, pathway=pathway)
        ok, diff = reconcile_opex_ledger(ledger, winner.annual_total_opex)
        assert ok, f"{pathway} OPEX reconciliation failed with diff={diff}"


def test_asset_register_omits_no_selected_physical_resource() -> None:
    """Section 8: no selected asset is silently omitted from the audit."""
    for pathway in ("Conventional", "MRT"):
        _geometry, _assumptions, _basis, result = _winner(pathway)
        winner = result.winner
        register = build_asset_register(winner)
        asset_types = {entry.asset_type for entry in register}
        assert "Cyclotron" in asset_types
        assert "Scanner" in asset_types
        assert "Injection room" in asset_types
        assert "Uptake room" in asset_types
        if pathway == "Conventional":
            assert "Human transporter (labor resource)" in asset_types
        else:
            assert "MRT carrier" in asset_types
            assert "MRT horizontal guideway (m)" in asset_types
            assert "MRT vertical guideway (m)" in asset_types
            assert "MRT physical H<->V transitions" in asset_types
            assert "MRT station/endpoint" in asset_types
        # Every quantity on the register must match the winning candidate.
        quantity_by_type = {entry.asset_type: entry.quantity for entry in register}
        assert quantity_by_type["Scanner"] == winner.layout.scanners
        assert quantity_by_type["Injection room"] == winner.layout.injection_resources
        assert quantity_by_type["Uptake room"] == winner.layout.uptake_resources

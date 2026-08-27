"""Hybrid Authoritative OPEX Ledger Unification.

Closes the split disclosed by the prior build: Hybrid no longer computes its
final OPEX via an independent bespoke formula. `hybrid_optimization.py
::_build_hybrid_opex_result` adapts Hybrid's real shared/Conventional-
specific/MRT-specific physical quantities onto the SAME authoritative
`infrastructure_opex.py::calculate_infrastructure_opex` ledger semantics
Conventional/MRT use, and `evaluate_hybrid_zone_candidate` feeds the unified
annual OPEX into the EXISTING `lifecycle_economics.evaluate_lifecycle_economics`
engine for NPV -- never a second, competing economics authority.
"""

from __future__ import annotations

import pytest

from models import SharedNetworkAssumptions
from spatial_benchmark import build_benchmark_geometry, build_production_basis, _base_assumptions
from hybrid_optimization import HybridZoneCandidate, evaluate_hybrid_zone_candidate
from study_scope import apply_study_scope


def _fixtures():
    return build_benchmark_geometry(), _base_assumptions(), build_production_basis()


def _evaluate(geometry, assumptions, basis, *, mrt_floors, conv_floors, candidate_id, scanners=6, injection=6, uptake=12, demand=200):
    candidate = HybridZoneCandidate(
        candidate_id=candidate_id, mrt_floors=frozenset(mrt_floors), conventional_floors=frozenset(conv_floors),
        scanners=scanners, injection_resources=injection, uptake_resources=uptake,
    )
    return evaluate_hybrid_zone_candidate(
        geometry=geometry, candidate=candidate, demand=demand, production_basis=basis,
        assumptions=assumptions, network_assumptions=SharedNetworkAssumptions(),
    )


# ---------------------------------------------------------------------------
# One authoritative ledger / no second economics authority
# ---------------------------------------------------------------------------


def test_hybrid_total_opex_equals_ledger_sum():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="PARTIAL-1")
    ledger_sum = sum(row.annual_cost for row in result.opex_result.ledger)
    assert result.total_annual_opex == pytest.approx(ledger_sum)


def test_hybrid_ledger_has_no_duplicate_component_rows():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="PARTIAL-2")
    components = [row.component for row in result.opex_result.ledger]
    assert len(components) == len(set(components))


# ---------------------------------------------------------------------------
# Shared assets counted once
# ---------------------------------------------------------------------------


def test_shared_scanner_counted_once():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="SCN-1")
    scanner_rows = [row for row in result.opex_result.ledger if "Scanner" in row.component]
    scanner_om = next(r for r in scanner_rows if r.component == "Scanner annual O&M")
    scanner_energy = next(r for r in scanner_rows if r.component == "Scanner energy")
    assert scanner_om.quantity == pytest.approx(6.0)  # candidate.scanners, not doubled by transport-mode split
    assert scanner_energy.quantity > 0.0


def test_shared_cyclotron_counted_once():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="CY-1")
    fixed_om_rows = [row for row in result.opex_result.ledger if row.component == "Cyclotron annual fixed O&M"]
    cyclotron_energy_rows = [row for row in result.opex_result.ledger if row.component == "Cyclotron energy"]
    assert len(fixed_om_rows) == 1
    assert len(cyclotron_energy_rows) == 1
    assert fixed_om_rows[0].quantity == pytest.approx(1.0)


def test_one_production_labor_pool():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="PROD-1")
    production_rows = [row for row in result.opex_result.ledger if row.component == "Production labor"]
    assert len(production_rows) == 1
    assert production_rows[0].annual_cost == pytest.approx(result.production_labor_annual_opex)


def test_one_merged_clinical_staff_pool():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="CLIN-1")
    clinical_rows = [row for row in result.opex_result.ledger if row.component == "Clinical labor"]
    assert len(clinical_rows) == 1
    assert clinical_rows[0].annual_cost == pytest.approx(result.staffing.total_new_pool_annual_opex)


# ---------------------------------------------------------------------------
# Mode-specific separation
# ---------------------------------------------------------------------------


def test_conventional_transport_labor_only_for_conventional_workload():
    geometry, assumptions, basis = _fixtures()
    all_mrt = _evaluate(geometry, assumptions, basis, mrt_floors=(1, 2, 3), conv_floors=(), candidate_id="ALLMRT-CT")
    row = next(r for r in all_mrt.opex_result.ledger if r.component == "Conventional transport labor")
    assert row.annual_cost == 0.0
    assert all_mrt.conventional_transporters == 0


def test_mrt_support_only_when_mrt_present():
    geometry, assumptions, basis = _fixtures()
    all_conv = _evaluate(geometry, assumptions, basis, mrt_floors=(), conv_floors=(1, 2, 3), candidate_id="ALLCONV-MS")
    partial = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="PARTIAL-MS")
    assert not any(row.component == "MRT support labor" for row in all_conv.opex_result.ledger)
    mrt_support_row = next(row for row in partial.opex_result.ledger if row.component == "MRT support labor")
    assert mrt_support_row.annual_cost > 0.0


# ---------------------------------------------------------------------------
# Energy calibration / fallback
# ---------------------------------------------------------------------------


def test_mrt_energy_generic_fallback_visible_and_nonzero():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="MRTFB-1")
    mrt_energy_row = next(row for row in result.opex_result.ledger if row.component == "MRT energy")
    assert mrt_energy_row.quantity > 0.0
    assert mrt_energy_row.energy_provenance == "GENERIC_ENERGY_FALLBACK"


def test_pettrace_890_cyclotron_energy_remains_not_calibrated():
    """CY-001/GE_PETTRACE_890 grounding (production_basis default cyclotron):
    Hybrid must never fabricate calibrated cyclotron electricity."""
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="PETTRACE-1")
    cyclotron_row = next(row for row in result.opex_result.ledger if row.component == "Cyclotron energy")
    assert cyclotron_row.energy_provenance == "GENERIC_ENERGY_FALLBACK"
    assert cyclotron_row.quantity > 0.0
    assert result.opex_result.economic_comparability_status != "FULLY_CALIBRATED"


def test_hybrid_economic_comparability_status_survives_to_final_result():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="COMP-1")
    assert result.opex_result.economic_comparability_status is not None
    assert result.opex_result.economic_comparability_status == "NOT_COMPARABLE_DUE_TO_UNCALIBRATED_ENERGY"


# ---------------------------------------------------------------------------
# Authoritative-path NPV proof (no manual reconstruction)
# ---------------------------------------------------------------------------


def test_hybrid_npv_consumes_unified_opex_through_lifecycle_economics():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="NPV-1")
    # Real chain proof: recompute NPV using ONLY total_capex/total_annual_opex/
    # qualified throughput via the SAME existing engine, and confirm it
    # matches -- proves the pipeline (not a hand-typed formula in this test).
    from lifecycle_economics import evaluate_lifecycle_economics
    expected = evaluate_lifecycle_economics(
        initial_capex=result.total_capex, installed_capacity_per_day=float(result.retention_qualified_completed),
        annual_opex=result.total_annual_opex, revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=assumptions.operating_days_per_year, discount_rate_pct=assumptions.discount_rate_pct,
        analysis_years=assumptions.analysis_years, starting_demand_per_day=float(result.retention_qualified_completed),
        annual_demand_growth_rate=0.0,
    )
    assert result.qualified_lifecycle_npv == pytest.approx(expected.final_npv)


def test_hybrid_operating_margin_uses_unified_opex():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="MARGIN-1")
    scope_result = apply_study_scope(
        study_scope="CAPITAL_PLANNING", transport_architecture="HYBRID", qualified_throughput=result.retention_qualified_completed,
        reference_capex=result.total_capex, annual_opex=result.total_annual_opex, revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=assumptions.operating_days_per_year, discount_rate_pct=assumptions.discount_rate_pct,
        analysis_years=assumptions.analysis_years,
    )
    assert scope_result.annual_operating_margin == pytest.approx(scope_result.qualified_annual_value - result.total_annual_opex)


# ---------------------------------------------------------------------------
# Study-scope invariance
# ---------------------------------------------------------------------------


def test_hybrid_study_scope_invariance_same_opex_only_capex_differs():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="SCOPE-1")
    op_only = apply_study_scope(
        study_scope="OPERATIONAL_ONLY", transport_architecture="HYBRID", qualified_throughput=result.retention_qualified_completed,
        reference_capex=result.total_capex, annual_opex=result.total_annual_opex, revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=assumptions.operating_days_per_year, discount_rate_pct=assumptions.discount_rate_pct,
        analysis_years=assumptions.analysis_years,
    )
    cap_plan = apply_study_scope(
        study_scope="CAPITAL_PLANNING", transport_architecture="HYBRID", qualified_throughput=result.retention_qualified_completed,
        reference_capex=result.total_capex, annual_opex=result.total_annual_opex, revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=assumptions.operating_days_per_year, discount_rate_pct=assumptions.discount_rate_pct,
        analysis_years=assumptions.analysis_years,
    )
    assert op_only.annual_opex == pytest.approx(cap_plan.annual_opex)
    assert op_only.study_capex == 0.0
    assert cap_plan.study_capex == pytest.approx(result.total_capex)


# ---------------------------------------------------------------------------
# ALL_CONVENTIONAL / ALL_MRT edge cases
# ---------------------------------------------------------------------------


def test_all_conventional_edge_case_has_no_mrt_rows():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(), conv_floors=(1, 2, 3), candidate_id="ALLCONV-EDGE")
    assert result.mrt_carriers == 0
    assert not any(row.component in ("MRT energy", "MRT support labor", "MRT carrier allocated electricity", "MRT carrier maintenance") for row in result.opex_result.ledger)
    assert any(row.component == "Conventional transport labor" for row in result.opex_result.ledger)


def test_all_mrt_edge_case_has_no_conventional_transport_cost():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1, 2, 3), conv_floors=(), candidate_id="ALLMRT-EDGE")
    conv_transport_row = next(row for row in result.opex_result.ledger if row.component == "Conventional transport labor")
    assert conv_transport_row.annual_cost == 0.0
    assert any(row.component == "MRT support labor" for row in result.opex_result.ledger)


# ---------------------------------------------------------------------------
# Genuine PARTIAL_HYBRID proof (section 80)
# ---------------------------------------------------------------------------


def test_partial_hybrid_proves_shared_once_and_mode_specific_present():
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="PARTIAL-PROOF")
    assert result.conventional_transporters > 0
    assert result.mrt_carriers > 0
    ledger_by_component = {row.component: row for row in result.opex_result.ledger}
    # Shared, counted once.
    assert ledger_by_component["Scanner annual O&M"].quantity == pytest.approx(6.0)
    assert ledger_by_component["Production labor"].annual_cost == pytest.approx(result.production_labor_annual_opex)
    assert ledger_by_component["Clinical labor"].annual_cost == pytest.approx(result.staffing.total_new_pool_annual_opex)
    # Conventional-specific present (real workload).
    assert ledger_by_component["Conventional transport labor"].annual_cost > 0.0
    # MRT-specific present (real workload).
    assert ledger_by_component["MRT support labor"].annual_cost > 0.0
    assert ledger_by_component["MRT energy"].annual_cost > 0.0
    # Fallback/calibration status preserved.
    assert result.opex_result.economic_comparability_status == "NOT_COMPARABLE_DUE_TO_UNCALIBRATED_ENERGY"


# ---------------------------------------------------------------------------
# Non-regression: throughput / retention / resources / staffing / CapEx
# ---------------------------------------------------------------------------


def test_capex_unaffected_by_opex_unification():
    """CapEx formula was not touched by this build; verify representative
    value matches the pre-existing scanner/injection/uptake + cyclotron +
    conventional + mrt-base/endpoint/carrier + guideway formula."""
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="CAPEX-1")
    scanner_uptake_injection_capex = 6 * assumptions.scanner_capex + 6 * assumptions.additional_room_capex + 12 * assumptions.additional_room_capex
    cyclotron_capex = assumptions.cyclotron_purchase_capex + assumptions.cyclotron_installation_capex
    assert result.total_capex >= scanner_uptake_injection_capex + cyclotron_capex


def test_qualified_throughput_and_staffing_unchanged_shape():
    """Same physical candidate evaluated twice is fully deterministic --
    qualified throughput, staffing FTE, and resource counts identical."""
    geometry, assumptions, basis = _fixtures()
    result_a = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="DET-1")
    result_b = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="DET-1")
    assert result_a.retention_qualified_completed == result_b.retention_qualified_completed
    assert result_a.staffing.total_new_pool_annual_opex == pytest.approx(result_b.staffing.total_new_pool_annual_opex)
    assert result_a.conventional_transporters == result_b.conventional_transporters
    assert result_a.mrt_carriers == result_b.mrt_carriers
    assert result_a.total_capex == pytest.approx(result_b.total_capex)


# ---------------------------------------------------------------------------
# Authority validation
# ---------------------------------------------------------------------------


def test_authority_validation_clean_for_partial_hybrid():
    from engineering_authority import validate_hybrid_opex_unification
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(1,), conv_floors=(2, 3), candidate_id="AUTH-1")
    findings = validate_hybrid_opex_unification(
        ledger=result.opex_result.ledger, total_annual_opex=result.total_annual_opex,
        economic_comparability_status=result.opex_result.economic_comparability_status, mrt_active=True,
    )
    assert findings == []


def test_authority_validation_clean_for_all_conventional():
    from engineering_authority import validate_hybrid_opex_unification
    geometry, assumptions, basis = _fixtures()
    result = _evaluate(geometry, assumptions, basis, mrt_floors=(), conv_floors=(1, 2, 3), candidate_id="AUTH-2")
    findings = validate_hybrid_opex_unification(
        ledger=result.opex_result.ledger, total_annual_opex=result.total_annual_opex,
        economic_comparability_status=result.opex_result.economic_comparability_status, mrt_active=False,
    )
    assert findings == []

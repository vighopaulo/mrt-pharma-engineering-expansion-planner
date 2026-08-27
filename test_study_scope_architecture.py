"""Study Scope Architecture -- CAPITAL_PLANNING vs OPERATIONAL_ONLY controlled tests.

Covers the six-combination matrix (StudyScope x TransportArchitecture),
architecture purity (no MRT leakage into Conventional, no Conventional
leakage into MRT), CapEx-off/asset-on invariants (scanner, cyclotron,
guideway, carriers), staff OPEX remaining active, operating margin / OPEX-
per-patient formulas, physical-result invariance between scopes, and Hybrid's
shared-pool semantics under OPERATIONAL_ONLY.
"""

from __future__ import annotations

from dataclasses import replace

from models import SharedNetworkAssumptions
from spatial_benchmark import (
    build_benchmark_geometry,
    build_production_basis,
    _base_assumptions,
    compute_retention_envelope,
    _assign_rooms_for_candidate,
    _evaluate_layout,
    _build_request,
    run_native_pathway_pipeline,
)
from hybrid_optimization import HybridZoneCandidate, evaluate_hybrid_zone_candidate
from radiopharm_workflow_staffing import apply_staffing_authority_to_pure_pathway_outcome
from study_scope import apply_study_scope, build_installed_existing_pathway_scenario


def _fixtures():
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    return geometry, assumptions, basis


def _pure_pathway(pathway, geometry, assumptions, basis, floors=(1, 2, 3, 4), injections=18, uptake=12, scanners=6):
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway=pathway)
    layout = _assign_rooms_for_candidate(
        geometry=geometry, active_floors=floors, scanners=scanners, injections=injections, uptake=uptake,
        distribution_mode="balanced", assumptions=assumptions, candidate_id=f"SS-{pathway}", pattern_id=f"SS-{pathway}",
        distribution_concurrency=8, feasible_room_ids=env.feasible_room_ids,
    )
    assert layout is not None
    capital_outcome = _evaluate_layout(pathway=pathway, layout=layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1)
    request = _build_request(demand=200, pathway_layout=layout, production_basis=basis, assumptions=assumptions, seed=1)
    conv_op, mrt_op = build_installed_existing_pathway_scenario(layout)
    operational_request = replace(request, conventional=conv_op, mrt=mrt_op)
    operational_pathway_result = run_native_pathway_pipeline(operational_request, pathway=pathway)
    return capital_outcome, operational_pathway_result


# --- Section 5: six-combination matrix --------------------------------------

def test_six_combination_matrix_all_succeed():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()

    for pathway in ("Conventional", "MRT"):
        capital_outcome, operational_result = _pure_pathway(pathway, geometry, assumptions, basis)
        assert capital_outcome.total_capex > 0.0
        assert operational_result.capex_result.total_capex == 0.0
        assert operational_result.operational_result.patients_completed > 0

    candidate = HybridZoneCandidate(candidate_id="SS-HYB", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=17, uptake_resources=12)
    hybrid_result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    capital_scope = apply_study_scope(
        study_scope="CAPITAL_PLANNING", transport_architecture="HYBRID", qualified_throughput=hybrid_result.retention_qualified_completed,
        reference_capex=hybrid_result.total_capex, annual_opex=hybrid_result.total_annual_opex, revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=int(assumptions.operating_days_per_year), discount_rate_pct=assumptions.discount_rate_pct, analysis_years=assumptions.analysis_years,
    )
    operational_scope = apply_study_scope(
        study_scope="OPERATIONAL_ONLY", transport_architecture="HYBRID", qualified_throughput=hybrid_result.retention_qualified_completed,
        reference_capex=hybrid_result.total_capex, annual_opex=hybrid_result.total_annual_opex, revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=int(assumptions.operating_days_per_year), discount_rate_pct=assumptions.discount_rate_pct, analysis_years=assumptions.analysis_years,
    )
    assert capital_scope.study_capex == hybrid_result.total_capex
    assert operational_scope.study_capex == 0.0
    assert operational_scope.installed_asset_reference_capex == hybrid_result.total_capex


# --- Section 45/56: physical results match between scopes; capital mode unchanged --

def test_physical_results_identical_between_capital_and_operational_scope():
    geometry, assumptions, basis = _fixtures()
    for pathway in ("Conventional", "MRT"):
        capital_outcome, operational_result = _pure_pathway(pathway, geometry, assumptions, basis)
        assert capital_outcome.patients_retention_qualified_completed == operational_result.operational_result.patients_completed \
            or capital_outcome.pathway_result.operational_result.patients_completed == operational_result.operational_result.patients_completed


def test_capital_planning_reference_values_unchanged_by_study_scope_threading():
    """Section 56: pin representative reference values; StudyScope threading
    must not alter CAPITAL_PLANNING results."""
    geometry, assumptions, basis = _fixtures()
    capital_outcome, _ = _pure_pathway("Conventional", geometry, assumptions, basis)
    assert capital_outcome.patients_retention_qualified_completed == 194
    assert abs(capital_outcome.total_capex - 21_625_000.0) < 1.0


# --- Section 46-49: CapEx off, asset/capacity on ---------------------------

def test_operational_scanner_capacity_on_capex_off():
    geometry, assumptions, basis = _fixtures()
    _, operational_result = _pure_pathway("Conventional", geometry, assumptions, basis)
    scanner_capex_lines = [item for item in operational_result.capex_result.ledger if "scanner" in item.component.lower()]
    assert all(item.subtotal == 0.0 for item in scanner_capex_lines)
    assert operational_result.operational_result.pathway_config.scanners == 6


def test_operational_cyclotron_capex_off_capacity_on():
    geometry, assumptions, basis = _fixtures()
    _, operational_result = _pure_pathway("Conventional", geometry, assumptions, basis)
    cyclotron_capex_lines = [item for item in operational_result.capex_result.ledger if "cyclotron" in item.component.lower()]
    assert all(item.subtotal == 0.0 for item in cyclotron_capex_lines)
    # Production capacity must remain active: patients still production-feasible.
    assert operational_result.operational_result.production_activity_feasible_scheduled_patients > 0


def test_operational_mrt_guideway_capex_off_network_on():
    geometry, assumptions, basis = _fixtures()
    _, operational_result = _pure_pathway("MRT", geometry, assumptions, basis)
    guideway_lines = [item for item in operational_result.capex_result.ledger if "guideway" in item.component.lower()]
    assert all(item.subtotal == 0.0 for item in guideway_lines)
    assert operational_result.operational_result.pathway_config.installed_guideway_length_m > 0.0


def test_operational_mrt_carrier_capex_off_fleet_finite():
    geometry, assumptions, basis = _fixtures()
    _, operational_result = _pure_pathway("MRT", geometry, assumptions, basis)
    carrier_capex_lines = [item for item in operational_result.capex_result.ledger if "carrier" in item.component.lower() and "capex" not in item.category.lower() or "carrier" in item.component.lower()]
    assert all(item.subtotal == 0.0 for item in operational_result.capex_result.ledger if "carrier" in item.component.lower())
    assert operational_result.operational_result.mrt_carrier_fleet is not None
    assert operational_result.operational_result.mrt_carrier_fleet.installed_carriers > 0


# --- Section 50: staff OPEX remains active ----------------------------------

def test_staff_opex_remains_nonzero_in_operational_mode():
    geometry, assumptions, basis = _fixtures()
    capital_outcome, operational_result = _pure_pathway("Conventional", geometry, assumptions, basis)
    staffing_result = apply_staffing_authority_to_pure_pathway_outcome(capital_outcome, assumptions)
    assert staffing_result.staffing.total_new_pool_annual_opex > 0.0
    # Production/clinical staff lines remain present in the operational OPEX ledger.
    labor_lines = [item for item in operational_result.opex_result.ledger if item.category == "LABOR"]
    assert len(labor_lines) > 0
    assert sum(item.annual_cost for item in labor_lines) > 0.0


# --- Section 52: MRT disabled for OPERATIONAL_ONLY + CONVENTIONAL ----------

def test_operational_conventional_has_zero_mrt_dependency():
    geometry, assumptions, basis = _fixtures()
    _, operational_result = _pure_pathway("Conventional", geometry, assumptions, basis)
    ledger = operational_result.capex_result.ledger + tuple(operational_result.opex_result.ledger)
    mrt_terms = ("guideway", "carrier", "mrt")
    assert not any(any(term in item.component.lower() for term in mrt_terms) for item in ledger)


def test_operational_mrt_has_zero_conventional_transporter_dependency():
    geometry, assumptions, basis = _fixtures()
    _, operational_result = _pure_pathway("MRT", geometry, assumptions, basis)
    ledger = tuple(operational_result.opex_result.ledger)
    assert not any("conventional transport" in item.component.lower() for item in ledger)


# --- Section 53: Hybrid operational shared resources -----------------------

def test_hybrid_operational_shared_pools_still_single_pool():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="SS-HYB-OPS", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=17, uptake_resources=12)
    result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    # Shared pools are computed once regardless of study scope (study scope is
    # purely an economic CapEx-inclusion decision, applied AFTER physical/
    # staffing computation) -- peak injection concurrency bounded by shared room count.
    assert result.staffing.injection_staff.peak_concurrency <= candidate.injection_resources
    conv_patients = {t.patient_id for t in result.patient_traces if t.transport_mode == "CONVENTIONAL"}
    mrt_patients = {t.patient_id for t in result.patient_traces if t.transport_mode == "MRT"}
    assert conv_patients and mrt_patients
    assert conv_patients.isdisjoint(mrt_patients)


# --- Section 54/55: operating margin, OPEX/patient --------------------------

def test_operating_margin_formula():
    result = apply_study_scope(
        study_scope="OPERATIONAL_ONLY", transport_architecture="CONVENTIONAL", qualified_throughput=194,
        reference_capex=21_625_000.0, annual_opex=9_164_605.0, revenue_per_scan=2000.0,
        operating_days_per_year=300, discount_rate_pct=8.0, analysis_years=10,
    )
    expected_annual_value = 194 * 2000.0 * 300
    assert result.qualified_annual_value == expected_annual_value
    assert result.annual_operating_margin == expected_annual_value - 9_164_605.0


def test_opex_per_qualified_patient_handles_zero_throughput():
    result = apply_study_scope(
        study_scope="OPERATIONAL_ONLY", transport_architecture="CONVENTIONAL", qualified_throughput=0,
        reference_capex=1_000_000.0, annual_opex=500_000.0, revenue_per_scan=2000.0,
        operating_days_per_year=300, discount_rate_pct=8.0, analysis_years=10,
    )
    assert result.opex_per_qualified_patient is None
    assert result.annual_operating_margin == -500_000.0


def test_capital_project_npv_only_populated_for_capital_planning():
    operational_result = apply_study_scope(
        study_scope="OPERATIONAL_ONLY", transport_architecture="MRT", qualified_throughput=194,
        reference_capex=42_795_000.0, annual_opex=8_223_155.0, revenue_per_scan=2000.0,
        operating_days_per_year=300, discount_rate_pct=8.0, analysis_years=10,
    )
    capital_result = apply_study_scope(
        study_scope="CAPITAL_PLANNING", transport_architecture="MRT", qualified_throughput=194,
        reference_capex=42_795_000.0, annual_opex=8_223_155.0, revenue_per_scan=2000.0,
        operating_days_per_year=300, discount_rate_pct=8.0, analysis_years=10,
    )
    assert operational_result.capital_project_npv is None
    assert capital_result.capital_project_npv is not None
    assert operational_result.operating_horizon_present_value > capital_result.operating_horizon_present_value

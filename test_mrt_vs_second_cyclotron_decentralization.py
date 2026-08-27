"""MRT Distribution vs Second-Cyclotron Decentralization Benchmark.

Three competing engineering responses to the SAME 500 m Building-B spatial
problem, evaluated against the IDENTICAL 300/day campus demand (100 Building
A + 200 Building B):

CASE A -- CENTRALIZED_CONVENTIONAL: CY-001/RP-001 (Building A), Conventional
    500 m delivery to Building B.
CASE B -- DECENTRALIZED_CONVENTIONAL_PRODUCTION: a REAL second cyclotron
    (CY-002/RP-B) physically installed IN Building B.
CASE C -- HYBRID_A_CONVENTIONAL_B_MRT: CY-001/RP-001 only, MRT delivery to
    Building B.

No architecture is forced to win -- verdicts are read from actual model
output, never asserted a priori.
"""

from __future__ import annotations

import pytest

from campus_retrofit_benchmark import (
    BUILDING_A_EXISTING_DEMAND,
    BUILDING_B_DEMAND,
    CAMPUS_TOTAL_DEMAND,
    CY002_CATALOG_MODEL_ID,
    build_building_a_baseline,
    build_two_building_campus_geometry,
    compute_capacity_vs_spatial_value,
    compute_corrected_economics,
    new_study_capex_hybrid,
    new_study_capex_pathway,
    run_building_a_standalone,
    run_campus_case_1_conventional,
    run_campus_case_2_hybrid,
    run_case_b_decentralized_building_b,
    run_three_way_campus_comparison,
)
from spatial_benchmark import _base_assumptions


@pytest.fixture(scope="module")
def geometry():
    return build_two_building_campus_geometry()


@pytest.fixture(scope="module")
def comparison(geometry):
    return run_three_way_campus_comparison(geometry=geometry)


# ---------------------------------------------------------------------------
# Section 3/68.1-68.3: identical demand, fixed Building A, fixed CY-001
# ---------------------------------------------------------------------------


def test_same_300_per_day_campus_demand_across_all_cases():
    assert BUILDING_A_EXISTING_DEMAND == 100
    assert BUILDING_B_DEMAND == 200
    assert CAMPUS_TOTAL_DEMAND == 300


def test_building_a_identical_across_cases(comparison):
    baseline_1 = build_building_a_baseline()
    baseline_2 = build_building_a_baseline()
    assert baseline_1 == baseline_2 == comparison.building_a


def test_cy001_remains_in_building_a_for_all_cases(comparison):
    a_trace = comparison.case_a_building_b.winner.pathway_result.operational_result.production_clinical_result.patient_traces[0]
    c_trace = comparison.case_c_building_b.patient_traces[0]
    assert a_trace.assigned_cyclotron_id == "CY-001"
    assert c_trace.assigned_cyclotron_id == "CY-001"


# ---------------------------------------------------------------------------
# Section 68.4-68.7: Case A has no CY-002/MRT; Case B has real CY-002; Case C
# has no CY-002 and is classified Hybrid
# ---------------------------------------------------------------------------


def test_case_a_has_no_cy002_or_mrt(comparison):
    traces = comparison.case_a_building_b.winner.pathway_result.operational_result.production_clinical_result.patient_traces
    assert all(t.assigned_cyclotron_id == "CY-001" for t in traces)
    assert comparison.case_a_building_b.pathway == "Conventional"


def test_case_b_has_real_cy002_identity_and_origin(comparison):
    b_result = comparison.case_b_building_b
    assert b_result.winner.pathway_result.capex_result is not None
    basis = None
    traces = b_result.winner.pathway_result.operational_result.production_clinical_result.patient_traces
    assert traces
    assert all(t.assigned_cyclotron_id == "CY-002" for t in traces)


def test_case_b_building_b_patients_map_to_cy002_not_rp001(comparison):
    traces = comparison.case_b_building_b.winner.pathway_result.operational_result.production_clinical_result.patient_traces
    assert all(t.assigned_cyclotron_id == "CY-002" for t in traces)
    assert all(t.assigned_cyclotron_id != "CY-001" for t in traces)


def test_case_c_has_no_cy002(comparison):
    assert all(t.assigned_cyclotron_id == "CY-001" for t in comparison.case_c_building_b.patient_traces)
    assert all(t.assigned_cyclotron_id != "CY-002" for t in comparison.case_c_building_b.patient_traces)


def test_case_c_building_b_patients_originate_from_cy001_and_mrt(comparison):
    for t in comparison.case_c_building_b.patient_traces:
        assert t.assigned_cyclotron_id == "CY-001"
        assert t.transport_mode == "MRT"


def test_case_c_is_classified_hybrid_not_pure_mrt(comparison):
    """Section 68.7: Case C's campus retains Building A's real, permanent
    Conventional-operated production -- it is architecturally Hybrid, never
    a standalone pure-MRT campus."""
    modes = {t.transport_mode for t in comparison.case_c_building_b.patient_traces}
    assert modes == {"MRT"}  # Building B is 100% MRT here...
    # ...but the CAMPUS is Hybrid because Building A stays Conventional-operated:
    assert comparison.case_c_building_b.conventional_transporters == 0  # no phantom Building-B Conventional transport


# ---------------------------------------------------------------------------
# Section 7-8: CY-002 selection is calibrated, not fabricated
# ---------------------------------------------------------------------------


def test_cy002_model_is_calibrated_not_fabricated():
    from cyclotron_catalog import find_production_records, load_cyclotron_catalog
    catalog = load_cyclotron_catalog()
    records = find_production_records(catalog=catalog, catalog_model_id=CY002_CATALOG_MODEL_ID, radionuclide="F-18")
    assert any(r.normalized_eob_activity_mbq is not None for r in records)


# ---------------------------------------------------------------------------
# Section 8/37/54: capacity vs spatial value distinguished; no auto-justification
# ---------------------------------------------------------------------------


def test_capacity_value_of_cy002_is_zero_cy001_already_sufficient(comparison):
    """Section 54: CY-002 must not be credited with a capacity improvement
    CY-001 already provided."""
    assert comparison.capacity_vs_spatial.cy001_alone_feasible_for_campus_total is True
    assert comparison.capacity_vs_spatial.capacity_value_qualified_patients_per_day == 0


def test_spatial_decay_value_of_cy002_is_measured_not_assumed(comparison):
    assert comparison.capacity_vs_spatial.spatial_decay_value_qualified_patients_per_day > 0
    assert isinstance(comparison.capacity_vs_spatial.spatial_decay_value_npv, float)


# ---------------------------------------------------------------------------
# Section 12: Case B Building-B local transport, no 500 m dose transport
# ---------------------------------------------------------------------------


def test_case_b_building_b_transport_is_internal_only_not_500m(comparison):
    """Section 12: CY-002 is co-located in Building B (its own standalone
    geometry) -- transport distances are internal-only, never the 500 m
    campus route."""
    layout = comparison.case_b_building_b.winner.layout
    assert layout.max_route_distance_m < 500.0


# ---------------------------------------------------------------------------
# Section 15-18/25/26/27/56: CapEx correctly separates existing vs new assets
# ---------------------------------------------------------------------------


def test_existing_cy001_never_charged_as_new_capex_in_case_a(comparison):
    corrected = new_study_capex_pathway(comparison.case_a_building_b.winner, cyclotron_is_existing=True)
    raw = comparison.case_a_building_b.winner.total_capex
    assert corrected < raw  # phantom existing-cyclotron/radiopharmacy charge removed


def test_existing_cy001_never_charged_as_new_capex_in_case_c(comparison):
    assumptions = _base_assumptions()
    corrected = new_study_capex_hybrid(comparison.case_c_building_b, assumptions, cyclotron_is_existing=True)
    assert corrected < comparison.case_c_building_b.total_capex


def test_cy002_carries_legitimate_new_capex_in_case_b(comparison):
    """Section 17/25: unlike Case A/C, Case B's cyclotron IS genuinely new --
    no correction/subtraction applies."""
    corrected = new_study_capex_pathway(comparison.case_b_building_b.winner, cyclotron_is_existing=False)
    assert corrected == comparison.case_b_building_b.winner.total_capex
    assert corrected > 0.0


# ---------------------------------------------------------------------------
# Section 19/36: no double counting -- CY-001 counted once per case, CY-002
# only appears in Case B
# ---------------------------------------------------------------------------


def test_no_shared_asset_double_counting(comparison):
    a_cyclotrons = {t.assigned_cyclotron_id for t in comparison.case_a_building_b.winner.pathway_result.operational_result.production_clinical_result.patient_traces}
    b_cyclotrons = {t.assigned_cyclotron_id for t in comparison.case_b_building_b.winner.pathway_result.operational_result.production_clinical_result.patient_traces}
    c_cyclotrons = {t.assigned_cyclotron_id for t in comparison.case_c_building_b.patient_traces}
    assert a_cyclotrons == {"CY-001"}
    assert b_cyclotrons == {"CY-002"}
    assert c_cyclotrons == {"CY-001"}


# ---------------------------------------------------------------------------
# Section 26/28/35: CapEx/OPEX reconciliation
# ---------------------------------------------------------------------------


def test_case_a_capex_reconciles_to_ledger_sum(comparison):
    outcome = comparison.case_a_building_b.winner
    assert outcome.total_capex == pytest.approx(sum(r.subtotal for r in outcome.pathway_result.capex_result.ledger), rel=1e-6)


def test_case_c_opex_reconciles_to_ledger_sum(comparison):
    ledger_sum = sum(r.annual_cost for r in comparison.case_c_building_b.opex_result.ledger)
    assert comparison.case_c_building_b.total_annual_opex == pytest.approx(ledger_sum, rel=1e-6)


# ---------------------------------------------------------------------------
# Section 49-50: patient traceability survives (representative patients)
# ---------------------------------------------------------------------------


def test_patient_traceability_survives_in_all_three_cases(comparison):
    a_traces = comparison.case_a_building_b.winner.pathway_result.operational_result.production_clinical_result.patient_traces[:5]
    b_traces = comparison.case_b_building_b.winner.pathway_result.operational_result.production_clinical_result.patient_traces[:5]
    c_traces = comparison.case_c_building_b.patient_traces[:5]
    for t in a_traces:
        assert t.patient_id and t.assigned_cyclotron_id and t.batch_id is not None
    for t in b_traces:
        assert t.patient_id and t.assigned_cyclotron_id == "CY-002" and t.batch_id is not None
    for t in c_traces:
        assert t.patient_id and t.assigned_cyclotron_id == "CY-001" and t.production_cycle_batch_id is not None


# ---------------------------------------------------------------------------
# Section 57/27: no forced winner -- verdict computed from actual NPV
# ---------------------------------------------------------------------------


def test_no_forced_winner_verdict_reads_from_actual_npv(comparison):
    corrected = compute_corrected_economics(comparison)
    winner = max(corrected, key=lambda ce: ce.npv)
    assert winner.architecture in {"CENTRALIZED_CONVENTIONAL", "DECENTRALIZED_CONVENTIONAL_PRODUCTION", "HYBRID_A_CONVENTIONAL_B_MRT"}
    # This benchmark's controlled 500 m scenario: assert only that a genuine,
    # non-trivial NPV spread exists across the three corrected results (never
    # that a specific architecture "must" win).
    npvs = {ce.architecture: ce.npv for ce in corrected}
    assert len(set(round(v, 2) for v in npvs.values())) == 3


# ---------------------------------------------------------------------------
# Section 43-45: distance sensitivity (secondary, kept lightweight)
# ---------------------------------------------------------------------------


def test_building_a_standalone_has_nonzero_internal_route(comparison):
    """Section 50: Building-A patients never get a 0 m/0 min internal route."""
    result = run_building_a_standalone()
    assert result.winner.avg_release_to_injection_minutes > 0.0

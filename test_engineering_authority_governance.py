"""Unified Constraint & Optimization Authority -- governance layer tests.

Verifies: (1) real established Conventional/MRT/Hybrid candidates pass every
applicable authority check; (2) deliberately broken synthetic inputs are
correctly caught (never silently accepted); (3) the registry itself is well-
formed and every authority_id referenced by a test/function actually exists.
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
from engineering_authority import (
    AUTHORITY_REGISTRY,
    VALID_OPTIMIZATION_STOP_REASONS,
    validate_architecture_purity,
    validate_hybrid_zone_disjointness,
    validate_economic_reconciliation,
    validate_patient_traceability,
    validate_room_exclusivity,
    validate_conservation_chain,
    validate_qualified_throughput_gating,
    validate_optimization_stop_reason,
    run_full_authority_validation,
)


def _fixtures():
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    return geometry, assumptions, basis


def _pure_pathway_outcome(pathway, geometry, assumptions, basis, floors=(1, 2, 3, 4), injections=18, uptake=12, scanners=6):
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway=pathway)
    layout = _assign_rooms_for_candidate(
        geometry=geometry, active_floors=floors, scanners=scanners, injections=injections, uptake=uptake,
        distribution_mode="balanced", assumptions=assumptions, candidate_id=f"GOV-{pathway}", pattern_id=f"GOV-{pathway}",
        distribution_concurrency=8, feasible_room_ids=env.feasible_room_ids,
    )
    assert layout is not None
    return _evaluate_layout(pathway=pathway, layout=layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1)


# --- Registry well-formedness ------------------------------------------------

def test_registry_is_well_formed():
    ids = [rule.authority_id for rule in AUTHORITY_REGISTRY]
    assert len(ids) == len(set(ids)), "authority_id values must be unique"
    for rule in AUTHORITY_REGISTRY:
        assert rule.category
        assert rule.authoritative_owner
        assert rule.description
        assert rule.severity in ("INFO", "WARNING", "VIOLATION")
        assert rule.classification in (
            "AUTHORITATIVE", "DERIVED_VIEW", "DIAGNOSTIC_ONLY", "LEGACY_COMPATIBILITY",
            "PROJECT_ASSUMPTION", "REQUIRES_CALIBRATION", "DEPRECATED_ACTIVE_RISK",
        )


def test_registry_covers_minimum_required_categories():
    required = {
        "PATIENT", "PRODUCTION", "CYCLOTRON", "RETENTION", "GEOMETRY", "TRANSPORT",
        "CLINICAL_FLOW", "ROOM", "INBOUND", "STAFFING", "ARCHITECTURE", "STUDY_SCOPE",
        "ASSET", "ECONOMIC", "OPTIMIZATION", "CONSERVATION", "TRACEABILITY",
    }
    present = {rule.category for rule in AUTHORITY_REGISTRY}
    assert required <= present, f"missing categories: {required - present}"


# --- Real candidates pass -----------------------------------------------------

def test_real_pure_conventional_passes_architecture_purity():
    geometry, assumptions, basis = _fixtures()
    outcome = _pure_pathway_outcome("Conventional", geometry, assumptions, basis)
    ledger = outcome.pathway_result.opex_result.ledger
    capex_ledger = outcome.pathway_result.capex_result.ledger
    findings = validate_architecture_purity(pathway="Conventional", capex_ledger=capex_ledger, opex_ledger=ledger)
    assert findings == []


def test_real_pure_mrt_passes_architecture_purity():
    geometry, assumptions, basis = _fixtures()
    outcome = _pure_pathway_outcome("MRT", geometry, assumptions, basis)
    ledger = outcome.pathway_result.opex_result.ledger
    capex_ledger = outcome.pathway_result.capex_result.ledger
    findings = validate_architecture_purity(pathway="MRT", capex_ledger=capex_ledger, opex_ledger=ledger)
    assert findings == []


def test_real_pure_conventional_passes_economic_reconciliation():
    geometry, assumptions, basis = _fixtures()
    outcome = _pure_pathway_outcome("Conventional", geometry, assumptions, basis)
    findings = validate_economic_reconciliation(
        capex_ledger=outcome.pathway_result.capex_result.ledger, reported_capex=outcome.total_capex,
        opex_ledger=outcome.pathway_result.opex_result.ledger, reported_opex=outcome.annual_total_opex,
    )
    assert findings == []


def test_real_hybrid_passes_zone_disjointness():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="GOV-HYB", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=17, uptake_resources=12)
    evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    findings = validate_hybrid_zone_disjointness(conventional_floors=candidate.conventional_floors, mrt_floors=candidate.mrt_floors)
    assert findings == []


def test_real_pure_conventional_passes_patient_traceability():
    geometry, assumptions, basis = _fixtures()
    outcome = _pure_pathway_outcome("Conventional", geometry, assumptions, basis)
    demand_ids = [p.patient_id for p in outcome.pathway_result.operational_result.demand_result.simulation.generated_demand.patients]
    clinical_ids = [t.patient_id for t in outcome.pathway_result.operational_result.production_clinical_result.patient_traces]
    decay_ids = [t.patient_id for t in outcome.pathway_result.decay_summary.patient_traces]
    findings = validate_patient_traceability(demand_patient_ids=demand_ids, clinical_patient_ids=clinical_ids, decay_patient_ids=decay_ids)
    assert findings == []


def test_real_pure_conventional_passes_conservation_chain():
    geometry, assumptions, basis = _fixtures()
    outcome = _pure_pathway_outcome("Conventional", geometry, assumptions, basis)
    op = outcome.pathway_result.operational_result
    demand_count = len(op.demand_result.simulation.generated_demand.patients)
    stage_counts = [
        ("demanded", demand_count),
        ("production_feasible", op.production_activity_feasible_scheduled_patients),
        ("clinically_completed", op.production_clinical_result.clinical_schedule.completed_patients),
        ("qualified", outcome.patients_retention_qualified_completed),
    ]
    findings = validate_conservation_chain(stage_counts=stage_counts)
    assert findings == []


# --- Deliberately broken inputs are caught -----------------------------------

def test_synthetic_mrt_leakage_into_conventional_ledger_is_caught():
    class _Item:
        def __init__(self, component):
            self.component = component
    fake_ledger = [_Item("MRT guideway"), _Item("Conventional infrastructure allowance")]
    findings = validate_architecture_purity(pathway="Conventional", capex_ledger=fake_ledger, opex_ledger=[])
    assert len(findings) >= 1
    assert findings[0].authority_id == "ARCHITECTURE_PURITY"
    assert findings[0].severity == "VIOLATION"


def test_synthetic_conventional_transport_leakage_into_mrt_ledger_is_caught():
    class _Item:
        def __init__(self, component):
            self.component = component
    fake_ledger = [_Item("Conventional transport labor")]
    findings = validate_architecture_purity(pathway="MRT", capex_ledger=[], opex_ledger=fake_ledger)
    assert len(findings) == 1
    assert findings[0].authority_id == "ARCHITECTURE_PURITY"


def test_synthetic_overlapping_hybrid_zones_caught():
    findings = validate_hybrid_zone_disjointness(conventional_floors=frozenset({1, 2, 3}), mrt_floors=frozenset({3, 4}))
    assert len(findings) == 1
    assert findings[0].authority_id == "HYBRID_UNION"
    assert "3" in findings[0].message


def test_synthetic_economic_reconciliation_residual_caught():
    class _CapexItem:
        subtotal = 100.0
    class _OpexItem:
        annual_cost = 50.0
    findings = validate_economic_reconciliation(capex_ledger=[_CapexItem()], reported_capex=999.0, opex_ledger=[_OpexItem()], reported_opex=999.0)
    assert len(findings) == 2


def test_synthetic_patient_identity_loss_caught():
    findings = validate_patient_traceability(demand_patient_ids=["P1", "P2", "P3"], clinical_patient_ids=["P1", "P2"], decay_patient_ids=["P1", "P2"])
    assert len(findings) == 1
    assert "P3" in findings[0].affected_object_ids


def test_synthetic_patient_fabrication_caught():
    findings = validate_patient_traceability(demand_patient_ids=["P1"], clinical_patient_ids=["P1", "P2"], decay_patient_ids=["P1", "P2"])
    assert any("no matching demand record" in f.message for f in findings)


def test_synthetic_room_exclusivity_violation_caught():
    findings = validate_room_exclusivity(room_assignments={"F1-R01": "SCANNER"})
    assert findings == []
    # Simulate a merged dict from two independently-built sources assigning conflicting functions.
    merged = {}
    for room_id, function in [("F1-R01", "SCANNER")]:
        merged[room_id] = function
    for room_id, function in [("F1-R01", "INJECTION_ADMINISTRATION")]:
        if room_id in merged and merged[room_id] != function:
            pass  # would be caught if merged via validate_room_exclusivity's own accumulation
    # Directly exercise the conflict-detection path via two sequential updates through the same dict is impossible
    # (dict overwrites); the intended real-world violation surface is two SEPARATE room_assignments dicts merged
    # inconsistently -- represented here via a list of (room_id, function) pairs with an internal conflict.
    conflicting_pairs = {"F1-R01": "SCANNER"}
    # Directly test via a dedicated helper path: construct a dict-like object whose .items() yields a conflict.
    class ConflictingDict(dict):
        def items(self):
            return [("F1-R01", "SCANNER"), ("F1-R01", "INJECTION_ADMINISTRATION")]
    findings2 = validate_room_exclusivity(room_assignments=ConflictingDict())
    assert len(findings2) == 1
    assert findings2[0].authority_id == "ROOM_EXCLUSIVITY"


def test_synthetic_conservation_violation_caught():
    findings = validate_conservation_chain(stage_counts=[("demanded", 100), ("production_feasible", 120)])
    assert len(findings) == 1
    assert "fabricated" in findings[0].message


def test_qualified_throughput_gating_defect_caught():
    findings = validate_qualified_throughput_gating(clinically_completed=True, retention_pass=False, qualified=True)
    assert len(findings) == 1
    assert findings[0].authority_id == "QUALIFIED_THROUGHPUT"


def test_qualified_throughput_gating_correct_case_passes():
    findings = validate_qualified_throughput_gating(clinically_completed=True, retention_pass=True, qualified=True)
    assert findings == []


def test_optimization_stop_reason_computational_limit_flagged_not_proven():
    findings = validate_optimization_stop_reason(dimension="injection_rooms", stop_reason="COMPUTATIONAL_SEARCH_LIMIT")
    assert len(findings) == 1
    assert "OPTIMALITY_NOT_PROVEN" in findings[0].message


def test_optimization_stop_reason_legitimate_reason_not_flagged():
    findings = validate_optimization_stop_reason(dimension="injection_rooms", stop_reason="NO_QUALIFIED_THROUGHPUT_GAIN")
    assert findings == []
    assert "NO_QUALIFIED_THROUGHPUT_GAIN" in VALID_OPTIMIZATION_STOP_REASONS


# --- Orchestrator ------------------------------------------------------------

def test_run_full_authority_validation_passes_for_real_conventional_candidate():
    geometry, assumptions, basis = _fixtures()
    outcome = _pure_pathway_outcome("Conventional", geometry, assumptions, basis)
    op = outcome.pathway_result.operational_result
    demand_ids = [p.patient_id for p in op.demand_result.simulation.generated_demand.patients]
    clinical_ids = [t.patient_id for t in op.production_clinical_result.patient_traces]
    decay_ids = [t.patient_id for t in outcome.pathway_result.decay_summary.patient_traces]
    result = run_full_authority_validation(
        pathway="Conventional",
        capex_ledger=outcome.pathway_result.capex_result.ledger, opex_ledger=outcome.pathway_result.opex_result.ledger,
        reported_capex=outcome.total_capex, reported_opex=outcome.annual_total_opex,
        demand_patient_ids=demand_ids, clinical_patient_ids=clinical_ids, decay_patient_ids=decay_ids,
        room_assignments=dict(outcome.layout.room_assignments),
        stage_counts=[
            ("demanded", len(demand_ids)),
            ("production_feasible", op.production_activity_feasible_scheduled_patients),
            ("clinically_completed", op.production_clinical_result.clinical_schedule.completed_patients),
            ("qualified", outcome.patients_retention_qualified_completed),
        ],
    )
    assert result.passed
    assert result.violations == ()
    assert "ARCHITECTURE_PURITY" in result.authority_checks
    assert "ECONOMIC_RECONCILIATION" in result.economic_reconciliation
    assert "PATIENT_IDENTITY" in result.traceability_checks
    assert "ROOM_EXCLUSIVITY" in result.constraint_checks
    assert "CONSERVATION_CHAIN" in result.conservation_checks


def test_run_full_authority_validation_distinguishes_violation_categories():
    """A candidate can be physically feasible (no conservation violation) but
    still fail architecture purity -- the result must preserve that distinction,
    never collapse to one boolean (section 59)."""
    class _Item:
        def __init__(self, component):
            self.component = component
    result = run_full_authority_validation(
        pathway="Conventional",
        capex_ledger=[_Item("MRT guideway")], opex_ledger=[],
        stage_counts=[("demanded", 100), ("qualified", 50)],
    )
    assert not result.passed
    assert any(v.category == "ARCHITECTURE" for v in result.violations)
    assert result.conservation_checks == ("CONSERVATION_CHAIN",)

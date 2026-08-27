"""Global Engineering Authority Reconciliation + End-to-End Consistency Audit.

This is an AUDIT test file, not a new feature. It captures, as permanent
regression evidence, the cross-module consistency findings from the system-
wide authority audit: patient identity survives end-to-end; CapEx/OPEX ledgers
reconcile exactly; Hybrid payload IDs never collide after merge; inbound
patient activity is fully accounted for in total demand; MRT is genuinely
optional (Conventional-only runs never touch MRT CapEx/OPEX lines); and the
one demonstrated NOT-yet-proven-optimal finding (injection-room search bound)
is pinned so it cannot silently regress or be forgotten.
"""

from __future__ import annotations

from models import SharedNetworkAssumptions
from spatial_benchmark import (
    build_benchmark_geometry,
    build_production_basis,
    _base_assumptions,
    compute_retention_envelope,
    optimize_pathway_layouts,
    _assign_rooms_for_candidate,
    _evaluate_layout,
)
from hybrid_optimization import HybridZoneCandidate, evaluate_hybrid_zone_candidate
from asset_cost_ledger import build_asset_cost_ledger, reconcile_capex_ledger, reconcile_opex_ledger
from inbound_patient_program import attach_patient_type_and_los


def _fixtures():
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    return geometry, assumptions, basis


# --- Section 6: patient identity survives end-to-end ------------------------

def test_representative_patients_survive_identity_end_to_end():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    winner = optimize_pathway_layouts(pathway="Conventional", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env).winner

    demand_patients = winner.pathway_result.operational_result.demand_result.simulation.generated_demand.patients
    clinical_by_id = {t.patient_id: t for t in winner.pathway_result.operational_result.production_clinical_result.patient_traces}
    decay_by_id = {t.patient_id: t for t in winner.pathway_result.decay_summary.patient_traces}
    demand_by_id = {p.patient_id: p for p in demand_patients}

    assert len(demand_patients) == 200
    for target in ("P1", "P17", "P25", "P50"):
        assert target in demand_by_id, f"{target} missing from demand population"
        assert target in clinical_by_id, f"{target} identity lost before clinical schedule"
        assert target in decay_by_id, f"{target} identity lost before decay/retention evaluation"
        clinical = clinical_by_id[target]
        decay = decay_by_id[target]
        assert clinical.patient_id == target == decay.patient_id
        assert clinical.batch_id > 0
        assert clinical.payload_id


# --- Section 44/45: CapEx/OPEX reconciliation --------------------------------

def test_pure_conventional_capex_opex_reconcile_exactly():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    winner = optimize_pathway_layouts(pathway="Conventional", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env).winner
    ledger = build_asset_cost_ledger(winner.pathway_result, pathway="Conventional")
    capex_ok, capex_diff = reconcile_capex_ledger(ledger, winner.total_capex)
    opex_ok, opex_diff = reconcile_opex_ledger(ledger, winner.annual_total_opex)
    assert capex_ok and capex_diff == 0.0
    assert opex_ok and opex_diff == 0.0


def test_pure_mrt_capex_opex_reconcile_exactly():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT")
    winner = optimize_pathway_layouts(pathway="MRT", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env).winner
    ledger = build_asset_cost_ledger(winner.pathway_result, pathway="MRT")
    capex_ok, capex_diff = reconcile_capex_ledger(ledger, winner.total_capex)
    opex_ok, opex_diff = reconcile_opex_ledger(ledger, winner.annual_total_opex)
    assert capex_ok and capex_diff == 0.0
    assert opex_ok and opex_diff == 0.0


def test_mrt_only_capex_lines_absent_from_conventional_ledger():
    """Section 53: MRT must be genuinely optional -- a Conventional-only ledger
    must never carry guideway/carrier/station cost lines."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    winner = optimize_pathway_layouts(pathway="Conventional", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env).winner
    ledger = build_asset_cost_ledger(winner.pathway_result, pathway="Conventional")
    mrt_terms = ("guideway", "carrier", "mrt")
    assert not any(any(term in entry.asset_type.lower() for term in mrt_terms) for entry in ledger)


# --- Section 18: Hybrid payload-ID uniqueness after merge -------------------

def test_hybrid_payload_and_patient_ids_never_collide_after_merge():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="AUDIT-MERGE", mrt_floors=frozenset({3}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=6, uptake_resources=12)
    result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    patient_ids = [t.patient_id for t in result.patient_traces]
    assert len(patient_ids) == len(set(patient_ids)) == 200
    conv_payloads = {t.payload_id for t in result.patient_traces if t.transport_mode == "CONVENTIONAL"}
    mrt_payloads = {t.payload_id for t in result.patient_traces if t.transport_mode == "MRT"}
    assert conv_payloads.isdisjoint(mrt_payloads)
    assert all(p.startswith("CONV-") for p in conv_payloads)
    assert all(p.startswith("MRT-") for p in mrt_payloads)


# --- Section 28/29: Hybrid union rule, zone exclusivity ---------------------

def test_hybrid_zones_are_disjoint_and_form_a_union_not_a_duplicate():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="AUDIT-UNION", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=6, uptake_resources=12)
    result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    conv_floors = {t.destination_floor for t in result.patient_traces if t.transport_mode == "CONVENTIONAL"}
    mrt_floors = {t.destination_floor for t in result.patient_traces if t.transport_mode == "MRT"}
    assert conv_floors.isdisjoint(mrt_floors), "a destination floor must not be double-assigned to both transport zones"
    assert conv_floors <= {1, 2}
    assert mrt_floors <= {3, 4}


# --- Section 8: inbound patients affect production activity accounting -----

def test_inbound_and_outpatient_activity_sum_to_total_demand():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    winner = optimize_pathway_layouts(pathway="Conventional", demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env).winner
    demand_patients = winner.pathway_result.operational_result.demand_result.simulation.generated_demand.patients
    synthetic = attach_patient_type_and_los(demand_patients)
    inbound_activity = sum(p.prescribed_activity_mbq for p, s in zip(demand_patients, synthetic) if s.patient_type == "INBOUND_PATIENT")
    outpatient_activity = sum(p.prescribed_activity_mbq for p, s in zip(demand_patients, synthetic) if s.patient_type == "OUTPATIENT")
    total_activity = sum(p.prescribed_activity_mbq for p in demand_patients)
    assert abs(total_activity - inbound_activity - outpatient_activity) < 1e-6
    assert inbound_activity > 0.0
    assert outpatient_activity > 0.0


# --- Section 39/40: search-bound closure (the known unresolved issue) ------

def test_injection_room_search_bound_is_not_yet_proven_optimal():
    """Section 39: pins the demonstrated finding as a permanent regression
    check rather than a silent, unverified assumption. The Phase-14 pure-
    Conventional winner (6 injection rooms on floors 1-3) is NOT resource-
    bound-optimal: qualified throughput and qualified NPV continue to improve
    sharply (not merely marginally) up to the physical space limit of this
    3-floor/10-room layout (~12 injection rooms given scanners=6/uptake=12
    fixed), and the search only stopped because spatial_benchmark's profile
    sweep caps at a 3.0x injection multiplier -- a computational search bound,
    not a genuine DEMAND_SATURATED / NO_QUALIFIED_THROUGHPUT_GAIN /
    NPV_DECLINED / PHYSICAL_LIMIT stop. Classification: OPTIMALITY_NOT_PROVEN.
    This test intentionally does NOT change spatial_benchmark's profile
    search bounds (out of scope for an audit-only build); it exists so this
    finding cannot silently disappear or be re-asserted as resolved without
    updating this test.
    """
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")

    def _evaluate(injections):
        layout = _assign_rooms_for_candidate(
            geometry=geometry, active_floors=(1, 2, 3), scanners=6, injections=injections, uptake=12,
            distribution_mode="balanced", assumptions=assumptions, candidate_id=f"AUDIT-INJ-{injections}", pattern_id=f"AUDIT-INJ-{injections}",
            distribution_concurrency=min(8, injections), feasible_room_ids=env.feasible_room_ids,
        )
        assert layout is not None
        return _evaluate_layout(pathway="Conventional", layout=layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1)

    at_profile_max = _evaluate(6)  # Phase 14's reported "final reference" injection count.
    beyond_profile_max = _evaluate(12)  # still physically space-feasible on this 3-floor layout.

    assert beyond_profile_max.patients_retention_qualified_completed > at_profile_max.patients_retention_qualified_completed, (
        "if this fails because the two are now equal or beyond_profile_max is worse, the injection search bound "
        "may have been resolved -- update this test's docstring/classification instead of deleting it"
    )
    assert beyond_profile_max.qualified_lifecycle_npv > at_profile_max.qualified_lifecycle_npv

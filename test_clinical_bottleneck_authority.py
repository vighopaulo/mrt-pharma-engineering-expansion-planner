"""Clinical Bottleneck Authority Audit -- Production -> Injection -> Uptake -> Scanner.

READ-ONLY AUDIT FINDING (see final report): the Phase-"Global Engineering
Authority Reconciliation" observation that qualified throughput rose
72 -> 108 -> 144 as injection rooms increased 6 -> 9 -> 12 (uptake=12,
scanners=6 held fixed) is LEGITIMATE, not a defect. Evidence:

  - clinical_schedule.completed_patients (raw clinical completion) is IDENTICAL
    (194/200) at every injection count tested -- injection expansion never
    fabricates additional clinical completions.
  - patients_retention_qualified_completed EXACTLY equals the authoritative
    release->injection retention-pass count at every level (72, 108, 144) --
    confirms qualification is retention-gated, not injection-gated, and there
    is no counting-before-completion defect (section 10).
  - uptake_utilization_pct (69.4%) and scanner_utilization_pct (~60%) are
    IDENTICAL across all three injection counts -- confirms real, unexploited
    headroom in both downstream pools; injection expansion does not create
    fabricated capacity anywhere downstream.
  - Root mechanism: MORE injection rooms shrink injection QUEUEING delay
    (avg_injection_wait: 20.70 -> 13.27 -> 7.73 minutes), which shortens each
    patient's release->injection elapsed time, which is exactly the retention
    design criterion -- so more of the SAME 194 clinically-completed patients
    now also clear the 90% retention threshold. This is the intended physical
    lever of the whole benchmark (logistics speed -> retention), not a
    fabricated throughput gain.

Classification (section 22): A. LEGITIMATE_UPTAKE_HEADROOM (uptake/scanner
slack allows the retention-timing benefit to be realized without a downstream
queue absorbing it back).

True injection stopping point (section 42, evidence gathered, not
implemented as a code change): with uptake=12/scanners=6 held fixed and
active floors expanded to relieve space (1-3 -> 1-4), qualified throughput
climbs 144 (inj=12) -> 177 (inj=15) -> 194 (inj=18, floors 1-4) and then
PLATEAUS exactly at 194 (the raw clinical-completion ceiling: all completions
also become retention-qualified) -- classification NO_QUALIFIED_THROUGHPUT_GAIN
/ DEMAND_SATURATED at inj=18. Expanding further (inj=21 on floors 1-4 is
SPACE_EXHAUSTED; spreading onto floors 5-6 to fit more injection rooms
actively REDUCES qualified throughput to 164 then 146) because balanced
distribution then places injection rooms on floors farther from the release
origin, increasing average transport distance and degrading retention for a
growing share of patients -- a genuine RETENTION_LIMIT / distance trade-off,
not a new defect. This audit does not change spatial_benchmark's search
bounds (out of scope for an audit-only build); it pins the evidence as a
permanent regression check.
"""

from __future__ import annotations

from multi_isotope_decay import retained_fraction
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


def _fixtures():
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    return geometry, assumptions, basis


def _run(geometry, assumptions, basis, pathway, floors, injections, uptake, scanners, feasible_room_ids):
    layout = _assign_rooms_for_candidate(
        geometry=geometry, active_floors=floors, scanners=scanners, injections=injections, uptake=uptake,
        distribution_mode="balanced", assumptions=assumptions, candidate_id=f"BOTTLENECK-{pathway}-{injections}",
        pattern_id=f"BOTTLENECK-{pathway}-{injections}", distribution_concurrency=min(8, injections),
        feasible_room_ids=feasible_room_ids,
    )
    if layout is None:
        return None
    return _evaluate_layout(pathway=pathway, layout=layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1)


# --- Section 4/6/7: configured durations are real model parameters ---------

def test_configured_service_durations_are_model_parameters_not_hardcoded():
    _, assumptions, _ = _fixtures()
    # Section 4/6: report actual configured values -- uptake is 45 minutes in
    # this benchmark, NOT a hardcoded 60 (assertion pins the real value).
    assert assumptions.uptake_cycle_min == 45.0
    assert assumptions.injection_cycle_min == 10.0
    assert assumptions.scanner_cycle_min == 20.0
    # Section 5: uptake duration is an explicit configurable field, not a
    # module-level constant -- changing the assumptions object changes it.
    from dataclasses import replace
    alternate = replace(assumptions, uptake_cycle_min=90.0)
    assert alternate.uptake_cycle_min == 90.0
    assert assumptions.uptake_cycle_min == 45.0


# --- Section 9/10/22: 6/9/12 legitimacy evidence, no counting defect -------

def test_injection_expansion_never_fabricates_clinical_completions():
    """Raw clinical completion (schedule_completed) must stay constant while
    injection count increases -- confirms no fabricated throughput."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    completions = []
    for injections in (6, 9, 12):
        outcome = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), injections, 12, 6, env.feasible_room_ids)
        assert outcome is not None
        completions.append(outcome.pathway_result.operational_result.production_clinical_result.clinical_schedule.completed_patients)
    assert len(set(completions)) == 1, "raw clinical completion must not change with injection count alone"


def test_qualified_completion_exactly_equals_authoritative_retention_pass_count():
    """Section 10: no CLINICAL_COMPLETION_AUTHORITY_DEFECT -- qualified count
    must equal the retention-pass count computed from the authoritative
    release->injection elapsed time, confirming completion+retention gating
    (never injection-only gating)."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    threshold = assumptions.minimum_release_to_administration_retention_fraction
    for injections in (6, 9, 12):
        outcome = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), injections, 12, 6, env.feasible_room_ids)
        decay_traces = outcome.pathway_result.decay_summary.patient_traces
        retention_pass_and_completed = sum(
            1 for t in decay_traces
            if retained_fraction(max(0.0, t.elapsed_release_to_injection_minutes), t.half_life_minutes) >= threshold
            and t.completed_within_operating_day
        )
        assert outcome.patients_retention_qualified_completed == retention_pass_and_completed


def test_uptake_and_scanner_utilization_unchanged_across_injection_expansion():
    """Confirms genuine headroom (classification A): the SAME 194 patients
    flow through uptake/scanner regardless of injection count, so utilization
    is identical -- injection expansion only shortens queueing delay, it does
    not create new downstream load."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    utilizations = []
    for injections in (6, 9, 12):
        outcome = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), injections, 12, 6, env.feasible_room_ids)
        sched = outcome.pathway_result.operational_result.production_clinical_result.clinical_schedule
        utilizations.append((round(sched.uptake_utilization_pct, 1), round(sched.scanner_utilization_pct, 1)))
    assert len(set(utilizations)) == 1


def test_injection_expansion_reduces_injection_queueing_delay():
    """Root causal mechanism: more injection rooms must reduce average
    injection queueing wait, which is what improves retention pass rate."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    waits = []
    for injections in (6, 12):
        outcome = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), injections, 12, 6, env.feasible_room_ids)
        schedules = outcome.pathway_result.operational_result.production_clinical_result.clinical_schedule.patient_schedules
        avg_wait = sum(max(0.0, ps.injection_start - ps.distribution_end) for ps in schedules) / len(schedules)
        waits.append(avg_wait)
    assert waits[1] < waits[0]


# --- Section 26/27: uptake room exclusivity, no infinite holding -----------

def test_uptake_room_cannot_host_overlapping_patients():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    outcome = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), 12, 2, 6, env.feasible_room_ids)
    schedules = outcome.pathway_result.operational_result.production_clinical_result.clinical_schedule.patient_schedules
    # With only 2 uptake rooms and many patients, verify no more than 2
    # patients ever hold overlapping uptake intervals simultaneously.
    events = []
    for ps in schedules:
        events.append((ps.uptake_start, 1))
        events.append((ps.uptake_end, -1))
    events.sort()
    active = 0
    peak = 0
    for _, delta in events:
        active += delta
        peak = max(peak, active)
    assert peak <= 2, f"uptake occupancy peak {peak} exceeds the 2 physical rooms available"


def test_scarce_uptake_does_not_permit_unbounded_injection_throughput():
    """Section 27: many injection rooms but ONE uptake room must not allow
    unlimited simultaneous administered-but-unheld patients; queueing must
    delay uptake start, never bypass the shared pool."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    outcome = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), 10, 1, 4, env.feasible_room_ids)
    assert outcome is not None
    schedules = outcome.pathway_result.operational_result.production_clinical_result.clinical_schedule.patient_schedules
    events = []
    for ps in schedules:
        events.append((ps.uptake_start, 1))
        events.append((ps.uptake_end, -1))
    events.sort()
    active, peak = 0, 0
    for _, delta in events:
        active += delta
        peak = max(peak, active)
    assert peak <= 1


# --- Section 28/29: uptake bottleneck emerges and responds to expansion ---

def test_uptake_eventually_becomes_binding_and_expansion_relieves_it():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    tiny_uptake = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), 10, 1, 4, env.feasible_room_ids)
    more_uptake = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), 10, 4, 4, env.feasible_room_ids)
    assert more_uptake.patients_retention_qualified_completed >= tiny_uptake.patients_retention_qualified_completed


# --- Section 30/31: scanner bottleneck and expansion -----------------------

def test_scanner_bottleneck_limits_and_expansion_can_relieve_it():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    tiny_scanner = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), 10, 10, 1, env.feasible_room_ids)
    more_scanner = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), 10, 10, 4, env.feasible_room_ids)
    assert more_scanner.patients_retention_qualified_completed >= tiny_scanner.patients_retention_qualified_completed


# --- Section 32: production bound cannot be bypassed by clinical resources -

def test_abundant_clinical_resources_cannot_exceed_production_feasible_patients():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    outcome = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), 12, 12, 6, env.feasible_room_ids)
    demand_count = len(outcome.pathway_result.operational_result.demand_result.simulation.generated_demand.patients)
    assert outcome.patients_retention_qualified_completed <= demand_count


# --- Section 33: retention qualification defect check ----------------------

def test_completed_scan_still_fails_qualification_below_retention_threshold():
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    threshold = assumptions.minimum_release_to_administration_retention_fraction
    outcome = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), 6, 12, 6, env.feasible_room_ids)
    decay_traces = outcome.pathway_result.decay_summary.patient_traces
    found_completed_but_failed_retention = False
    for t in decay_traces:
        if not t.completed_within_operating_day:
            continue
        retained = retained_fraction(max(0.0, t.elapsed_release_to_injection_minutes), t.half_life_minutes)
        if retained < threshold:
            found_completed_but_failed_retention = True
            break
    assert found_completed_but_failed_retention, "must find at least one clinically-completed patient failing retention (P25 in the audited trace)"


# --- Section 38/39/40: Conventional/MRT/Hybrid share identical chain logic -

def test_mrt_exhibits_the_same_injection_retention_relationship_as_conventional():
    geometry, assumptions, basis = _fixtures()
    conv_env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    mrt_env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="MRT")
    conv_results = [
        _run(geometry, assumptions, basis, "Conventional", (1, 2, 3), inj, 12, 6, conv_env.feasible_room_ids).patients_retention_qualified_completed
        for inj in (6, 9, 12)
    ]
    mrt_results = [
        _run(geometry, assumptions, basis, "MRT", (1, 2, 3), inj, 12, 6, mrt_env.feasible_room_ids).patients_retention_qualified_completed
        for inj in (6, 9, 12)
    ]
    assert conv_results == mrt_results == [72, 108, 144]


def test_hybrid_exhibits_the_same_injection_retention_relationship():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    results = []
    for injections in (6, 9, 12):
        cand = HybridZoneCandidate(candidate_id=f"HYB-{injections}", mrt_floors=frozenset({3}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=injections, uptake_resources=12)
        r = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=cand, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
        results.append(r.retention_qualified_completed)
    assert results == [72, 108, 144]


# --- Section 42 (pinned evidence): true stopping point ---------------------

def test_true_injection_stopping_point_is_demand_saturated_at_194():
    """Pins the evidence gathered for section 42: with uptake=12/scanners=6
    fixed and floors expanded to relieve space, qualified throughput climbs
    to exactly 194 (the raw clinical-completion ceiling) at 18 injection
    rooms (floors 1-4) and does not exceed it -- NO_QUALIFIED_THROUGHPUT_GAIN
    / DEMAND_SATURATED, not an arbitrary search-bound stop."""
    geometry, assumptions, basis = _fixtures()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional")
    outcome_18 = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3, 4), 18, 12, 6, env.feasible_room_ids)
    clinical_completed = outcome_18.pathway_result.operational_result.production_clinical_result.clinical_schedule.completed_patients
    assert outcome_18.patients_retention_qualified_completed == clinical_completed == 194

    outcome_24 = _run(geometry, assumptions, basis, "Conventional", (1, 2, 3, 4, 5), 24, 12, 6, env.feasible_room_ids)
    assert outcome_24.patients_retention_qualified_completed <= 194, "expansion beyond the clinical-completion ceiling must not fabricate more qualified patients"

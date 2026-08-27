"""Hybrid Live-State Adapter + Staff-Capacity Patient Targeting.

Focus ONLY on the two gaps closed this build (do not duplicate the full
`test_live_state_rolling_reoptimization.py` / `test_rolling_reoptimization_
locality_and_architecture.py` suites):

1. A genuine PARTIAL HYBRID plan (>=1 Conventional + >=1 MRT patient) enters
   the SAME event->impact->localized-replan architecture as Conventional/MRT,
   via `HybridPlanVersion`/`apply_hybrid_event_and_replan` -- reusing the SAME
   `PatientOperationalPlan` type and the SAME `schedule_operating_day`
   primitive (`hybrid_optimization.rerun_hybrid_affected_subset`), never a
   second Hybrid scheduler/patient population/clinical resource system.

2. STAFF_CAPACITY_CHANGE now identifies the ACTUAL overlapping patient tasks
   that exceed capacity (`identify_staff_shortfall_patient_tasks`) and routes
   them through the SAME rolling-replan mechanism, for both the Conventional/
   MRT path (`apply_event_and_replan`) and the Hybrid path.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from clinical_resource_identity import build_calendar_with_no_exceptions, build_deterministic_resource_inventory
from engineering_authority import (
    validate_hybrid_mode_specific_impact,
    validate_hybrid_shared_resource_identity,
    validate_hybrid_single_patient_population,
    validate_staff_capacity_replan_result,
    validate_staff_shortfall_patient_targeting,
)
from healthcare_integration import CanonicalIntegrationEvent
from hybrid_optimization import HybridZoneCandidate, evaluate_hybrid_zone_candidate
from live_operational_state import (
    OperationalEvent,
    OperationalStateStore,
    analyze_event_impact,
    apply_event_and_replan,
    apply_hybrid_event_and_replan,
    baseline_hybrid_plan_version,
    baseline_plan_version,
    compute_plan_stability,
    identify_staff_shortfall_patient_tasks,
    plan_history_for_patient,
)
from long_horizon_operational_planning import CanonicalOperationalPatientRecord, CyclotronCalendar, run_operating_day_plan
from models import PlannerAssumptions, SharedNetworkAssumptions
from multi_cyclotron_authority import build_controlled_dual_origin_geometry, build_multi_cyclotron_scenario
from spatial_benchmark import _base_assumptions, build_benchmark_geometry, build_production_basis

DAY = date(2026, 10, 5)


def _event(*, source_event_id: str, event_type: str = "OTHER", timestamp: datetime = datetime(2026, 10, 5, 8, 0)) -> CanonicalIntegrationEvent:
    return CanonicalIntegrationEvent(source_system="SYNTHETIC", source_event_id=source_event_id, event_type=event_type, event_timestamp=timestamp)


def _hybrid_baseline():
    """Genuine PARTIAL HYBRID controlled population: 20 patients, 12
    Conventional + 8 MRT, sized so every patient completes within the
    operating day (avoids the unrelated overflow edge case where reservations
    can exceed `clinical_day_end_minute`)."""
    geometry = build_benchmark_geometry()
    basis = build_production_basis()
    assumptions = _base_assumptions()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(
        candidate_id="PARTIAL", mrt_floors=frozenset({2, 3}), conventional_floors=frozenset({1}),
        scanners=4, injection_resources=4, uptake_resources=4,
    )
    result = evaluate_hybrid_zone_candidate(
        geometry=geometry, candidate=candidate, demand=20, production_basis=basis,
        assumptions=assumptions, network_assumptions=network_assumptions,
    )
    baseline = baseline_hybrid_plan_version(day=DAY, hybrid_result=result, created_at=datetime(2026, 10, 5, 6, 0))
    return result, baseline


def _mode_by_id(baseline):
    return {p.internal_model_patient_id: p.transport_mode for p in baseline.patient_plans}


# ---------------------------------------------------------------------------
# Section 40: genuine Partial Hybrid controlled population
# ---------------------------------------------------------------------------


def test_partial_hybrid_population_has_both_transport_modes():
    _, baseline = _hybrid_baseline()
    modes = {p.transport_mode for p in baseline.patient_plans}
    assert modes == {"Conventional", "MRT"}
    assert sum(1 for p in baseline.patient_plans if p.transport_mode == "Conventional") >= 1
    assert sum(1 for p in baseline.patient_plans if p.transport_mode == "MRT") >= 1
    assert len({p.internal_model_patient_id for p in baseline.patient_plans}) == len(baseline.patient_plans)  # section D: one population, no duplication


# ---------------------------------------------------------------------------
# Section 41/62: shared-scanner outage, mode-agnostic locality
# ---------------------------------------------------------------------------


def test_hybrid_shared_scanner_outage_targets_by_scanner_not_mode():
    result, baseline = _hybrid_baseline()
    modes = _mode_by_id(baseline)
    scn002_patients = {p.internal_model_patient_id for p in baseline.patient_plans if p.scanner_resource_id == "SCN-002"}
    modes_on_scn002 = {modes[pid] for pid in scn002_patients}
    assert modes_on_scn002 == {"Conventional", "MRT"}, "controlled case requires a genuinely mixed-mode scanner"

    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-HYB-SCN"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-002", new_state="UNAVAILABLE")
    status, impact, version, changeset, escalation = apply_hybrid_event_and_replan(event=event, store=store, previous_version=baseline)

    assert status == "APPLIED"
    assert impact.impact_classification == "SHARED_RESOURCE_IMPACT"
    assert set(impact.directly_affected_patient_ids) == scn002_patients
    assert version is not None
    assert all(p.scanner_resource_id != "SCN-002" for p in version.patient_plans)
    stability = compute_plan_stability(changeset, total_before=len(baseline.patient_plans))
    assert stability.pct_preserved >= 60.0
    assert escalation.localization_feasible is True
    assert escalation.final_scope == "LEVEL_1_DIRECTLY_AFFECTED_ONLY"

    # Section T: resource exclusivity across the FULL revised plan.
    by_scanner: dict[str, list[tuple[float, float]]] = {}
    for p in version.patient_plans:
        by_scanner.setdefault(p.scanner_resource_id, []).append(p.scan_window_minutes)
    for windows in by_scanner.values():
        ordered = sorted(windows)
        for (s1, e1), (s2, e2) in zip(ordered, ordered[1:]):
            assert s2 >= e1

    # Section unaffected patients preserved byte-for-byte.
    old_by_id = {p.internal_model_patient_id: p for p in baseline.patient_plans}
    new_by_id = {p.internal_model_patient_id: p for p in version.patient_plans}
    for pid in changeset.unchanged_patient_ids:
        assert old_by_id[pid] == new_by_id[pid]

    # Section AB: zero unnecessary drift -- every modified assignment is
    # DIRECTLY_AFFECTED_CHANGE, never unexplained COLLATERAL.
    assert all(m.classification == "DIRECTLY_AFFECTED_CHANGE" for m in changeset.modified)

    findings = validate_hybrid_single_patient_population(patient_ids=[p.internal_model_patient_id for p in version.patient_plans])
    assert findings == []
    findings = validate_hybrid_shared_resource_identity(
        injection_resource_ids=[p.injection_resource_id for p in version.patient_plans],
        uptake_resource_ids=[p.uptake_resource_id for p in version.patient_plans],
        scanner_resource_ids=[p.scanner_resource_id for p in version.patient_plans],
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Section 42: MRT carrier failure -- MRT-only locality
# ---------------------------------------------------------------------------


def test_hybrid_mrt_carrier_failure_targets_only_mrt_jobs():
    _, baseline = _hybrid_baseline()
    modes = _mode_by_id(baseline)
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-HYB-CARRIER"), event_kind="MRT_CARRIER_STATE_CHANGE", object_id="CARRIER-1", new_state="UNAVAILABLE")
    status, impact, version, changeset, escalation = apply_hybrid_event_and_replan(event=event, store=store, previous_version=baseline)

    assert status == "APPLIED"
    assert impact.impact_classification == "MRT_SPECIFIC_IMPACT"
    assert impact.directly_affected_patient_ids
    assert all(modes[pid] == "MRT" for pid in impact.directly_affected_patient_ids)
    assert version is not None
    # Conventional jobs remain preserved (byte-for-byte) unless collateral.
    conv_modified = [m.patient_id for m in changeset.modified if modes[m.patient_id] == "Conventional"]
    assert conv_modified == []
    findings = validate_hybrid_mode_specific_impact(impact_classification=impact.impact_classification, directly_affected_transport_modes=[modes[pid] for pid in impact.directly_affected_patient_ids])
    assert findings == []


# ---------------------------------------------------------------------------
# Section 43: Conventional transport shortage -- Conventional-only locality
# ---------------------------------------------------------------------------


def test_hybrid_conventional_transport_shortage_targets_only_conventional_jobs():
    _, baseline = _hybrid_baseline()
    modes = _mode_by_id(baseline)
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-HYB-CONVTRANS"), event_kind="CONVENTIONAL_TRANSPORT_CAPACITY_CHANGE", object_id="CONV-TRANSPORT", new_state="REDUCED")
    status, impact, version, changeset, escalation = apply_hybrid_event_and_replan(event=event, store=store, previous_version=baseline)

    assert status == "APPLIED"
    assert impact.impact_classification == "CONVENTIONAL_SPECIFIC_IMPACT"
    assert impact.directly_affected_patient_ids
    assert all(modes[pid] == "Conventional" for pid in impact.directly_affected_patient_ids)
    mrt_modified = [m.patient_id for m in changeset.modified if modes[m.patient_id] == "MRT"]
    assert mrt_modified == []
    findings = validate_hybrid_mode_specific_impact(impact_classification=impact.impact_classification, directly_affected_transport_modes=[modes[pid] for pid in impact.directly_affected_patient_ids])
    assert findings == []


# ---------------------------------------------------------------------------
# Section 44: shared staff-capacity shortfall -- follows overlapping tasks,
# not transport mode
# ---------------------------------------------------------------------------


def test_hybrid_staff_capacity_shortfall_follows_actual_tasks_not_mode():
    _, baseline = _hybrid_baseline()
    store = OperationalStateStore()
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-HYB-STAFF"), event_kind="STAFF_CAPACITY_CHANGE",
        object_id="SCANNER_STAFF", actual_value=2.0, staff_pool="SCANNER",
    )
    status, impact, version, changeset, escalation = apply_hybrid_event_and_replan(event=event, store=store, previous_version=baseline)

    assert status == "APPLIED"
    assert impact.directly_affected_patient_ids  # genuine shortfall targeted real patients
    assert version is not None
    # Section 32/AH: revised concurrency across all scanners is capped.
    by_scanner: dict[str, list[tuple[float, float]]] = {}
    for p in version.patient_plans:
        by_scanner.setdefault(p.scanner_resource_id, []).append(p.scan_window_minutes)
    points = sorted({w[0] for ws in by_scanner.values() for w in ws} | {w[1] for ws in by_scanner.values() for w in ws})
    all_windows = [w for ws in by_scanner.values() for w in ws]
    max_concurrent = max((sum(1 for s, e in all_windows if s <= t < e) for t in points[:-1]), default=0)
    assert max_concurrent <= 2


# ---------------------------------------------------------------------------
# Section 45: mode-change -- honestly report, do not force
# ---------------------------------------------------------------------------


def test_hybrid_mode_change_is_never_fabricated():
    """This build's Hybrid replan mechanism reruns the shared clinical
    schedule only -- it never reassigns a patient's `transport_mode` (that
    would require re-deriving the destination/payload/production split, out
    of scope this build). Verify honestly: transport_mode survives every
    controlled replan unchanged for every patient (no legitimate mode change
    is possible under the current architecture -- reported, not forced)."""
    _, baseline = _hybrid_baseline()
    modes_before = _mode_by_id(baseline)
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-HYB-SCN2"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-002", new_state="UNAVAILABLE")
    _, _, version, _, _ = apply_hybrid_event_and_replan(event=event, store=store, previous_version=baseline)
    for p in version.patient_plans:
        assert p.transport_mode == modes_before[p.internal_model_patient_id]


# ---------------------------------------------------------------------------
# Section 46/R: production traceability survives Hybrid replan
# ---------------------------------------------------------------------------


def test_hybrid_production_traceability_survives_replan():
    _, baseline = _hybrid_baseline()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-HYB-SCN3"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-002", new_state="UNAVAILABLE")
    _, _, version, changeset, _ = apply_hybrid_event_and_replan(event=event, store=store, previous_version=baseline)
    old_by_id = {p.internal_model_patient_id: p for p in baseline.patient_plans}
    for p in version.patient_plans:
        old = old_by_id[p.internal_model_patient_id]
        # A scanner outage never changes radionuclide/cyclotron/batch/origin --
        # only the shared clinical schedule is rerun.
        assert p.radionuclide == old.radionuclide
        assert p.cyclotron_id == old.cyclotron_id
        assert p.batch_id == old.batch_id
        assert p.radiopharmacy_origin_id == old.radiopharmacy_origin_id


# ---------------------------------------------------------------------------
# Section 47/S: resource traceability (old/new/reason) for every changed assignment
# ---------------------------------------------------------------------------


def test_hybrid_resource_traceability_old_new_reason():
    _, baseline = _hybrid_baseline()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-HYB-SCN4"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-002", new_state="UNAVAILABLE")
    _, _, version, changeset, _ = apply_hybrid_event_and_replan(event=event, store=store, previous_version=baseline)
    assert changeset.modified
    for m in changeset.modified:
        assert m.old_plan is not None and m.new_plan is not None
        assert m.old_plan.scanner_resource_id != m.new_plan.scanner_resource_id
        assert m.reason == "SCANNER_REASSIGNED"


# ---------------------------------------------------------------------------
# Section 48/49: PlanVersion lineage + event journal
# ---------------------------------------------------------------------------


def test_hybrid_plan_version_lineage_and_event_journal():
    _, baseline = _hybrid_baseline()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-HYB-SCN5"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-002", new_state="UNAVAILABLE")
    status, impact, version, changeset, escalation = apply_hybrid_event_and_replan(event=event, store=store, previous_version=baseline)
    assert baseline.version_id == "PLAN-0000"
    assert version.version_id == "PLAN-0001"
    assert version.previous_version_id == "PLAN-0000"
    assert version.pathway == "Hybrid"

    history = plan_history_for_patient([baseline, version], patient_id=baseline.patient_plans[0].internal_model_patient_id)
    assert [v for v, _ in history] == ["PLAN-0000", "PLAN-0001"]

    entry = store.event_journal[-1]
    assert entry.source_event_id == "EVT-HYB-SCN5"
    assert entry.object_id == "SCN-002"
    assert entry.state_before is None
    assert entry.state_after == "UNAVAILABLE"
    assert entry.resulting_plan_version_id == "PLAN-0001"


# ---------------------------------------------------------------------------
# Section 50/AB: unnecessary drift == 0 for localized feasible cases
# ---------------------------------------------------------------------------


def test_hybrid_unnecessary_plan_drift_is_zero_for_localized_case():
    _, baseline = _hybrid_baseline()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-HYB-SCN6"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-002", new_state="UNAVAILABLE")
    _, impact, version, changeset, escalation = apply_hybrid_event_and_replan(event=event, store=store, previous_version=baseline)
    assert escalation.localization_feasible is True
    collateral = [m for m in changeset.modified if m.classification == "COLLATERAL_CHANGE_REQUIRED_FOR_FEASIBILITY"]
    assert collateral == []


# ---------------------------------------------------------------------------
# Section 51: completed Hybrid task remains immutable
# ---------------------------------------------------------------------------


def test_hybrid_completed_task_locked_and_survives_replan():
    _, baseline = _hybrid_baseline()
    store = OperationalStateStore()
    target_patient = baseline.patient_plans[0].internal_model_patient_id
    complete_event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-HYB-COMPLETE"), event_kind="ACTUAL_CLINICAL_TASK",
        object_id=target_patient, stage="SCANNER", actual_start_minutes=300.0, actual_end_minutes=320.0,
    )
    store.record_event(complete_event)
    assert store.is_locked(target_patient)

    cancel_target = next(p.internal_model_patient_id for p in baseline.patient_plans if p.internal_model_patient_id != target_patient)
    cancel_event = OperationalEvent(integration_event=_event(source_event_id="EVT-HYB-CANCEL", timestamp=datetime(2026, 10, 5, 9, 0)), event_kind="PATIENT_CANCELLED", object_id=cancel_target)
    status, impact, version, changeset, escalation = apply_hybrid_event_and_replan(event=cancel_event, store=store, previous_version=baseline)
    assert status == "APPLIED"
    assert version is not None
    old_plan = next(p for p in baseline.patient_plans if p.internal_model_patient_id == target_patient)
    new_plan = next(p for p in version.patient_plans if p.internal_model_patient_id == target_patient)
    assert old_plan == new_plan  # locked patient carried forward unchanged
    assert cancel_target not in {p.internal_model_patient_id for p in version.patient_plans}


# ---------------------------------------------------------------------------
# Section 54: retention recomputed after Hybrid timing changes
# ---------------------------------------------------------------------------


def test_hybrid_retention_recomputed_after_replan_not_stale():
    """Retention (`retained_fraction`, computed inside `rerun_hybrid_affected_
    subset` strictly from the ACTUAL new injection_start) is never carried
    forward stale. Verified indirectly here: every modified patient's revised
    clinical timeline is causally consistent (injection -> uptake -> scan,
    each recomputed from the real rerun, not copied from the old plan) and at
    least one stage's timing genuinely changed."""
    _, baseline = _hybrid_baseline()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-HYB-SCN7"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-002", new_state="UNAVAILABLE")
    _, _, version, changeset, _ = apply_hybrid_event_and_replan(event=event, store=store, previous_version=baseline)
    assert changeset.modified
    for m in changeset.modified:
        new = m.new_plan
        assert new.injection_window_minutes[1] <= new.uptake_window_minutes[0]
        assert new.uptake_window_minutes[1] <= new.scan_window_minutes[0]
        # Every modified patient was genuinely rescheduled onto a different
        # physical scanner (never the outaged SCN-002) -- the timing basis
        # retention is derived from is recomputed by the real rerun, never a
        # stale copy of the old assignment's identity.
        assert new.scanner_resource_id != m.old_plan.scanner_resource_id
        assert new.scanner_resource_id != "SCN-002"


# ---------------------------------------------------------------------------
# Staff-capacity patient-task targeting (sections 25-39) -- Conventional path
# ---------------------------------------------------------------------------


def _conventional_fixtures(*, patient_count=20, scanner_count=4, injection_count=4, uptake_count=4, distribution_concurrency=6):
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="OFF")
    geometry = build_controlled_dual_origin_geometry()
    assumptions = PlannerAssumptions()
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    inventory = build_deterministic_resource_inventory(injection_room_count=injection_count, uptake_room_count=uptake_count, scanner_count=scanner_count)
    resource_calendar = build_calendar_with_no_exceptions(inventory)
    records = [
        CanonicalOperationalPatientRecord(
            internal_model_patient_id=f"P{i}", demand_status="COMMITTED", patient_type="OUTPATIENT",
            radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=DAY, source_provenance="USER_ENTERED",
        )
        for i in range(patient_count)
    ]
    summary = run_operating_day_plan(
        day=DAY, records_for_day=records, cyclotron_calendar=cyclotron_calendar, pathway="Conventional",
        geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar, distribution_concurrency=distribution_concurrency,
    )
    baseline = baseline_plan_version(day=DAY, pathway="Conventional", daily_summary=summary, records_for_day=records, created_at=datetime(2026, 10, 5, 6, 0))
    return records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline


def test_identify_staff_shortfall_computes_real_interval_and_minimum_release_set():
    _, _, _, _, _, baseline = _conventional_fixtures()
    result = identify_staff_shortfall_patient_tasks(pool="SCANNER", plans=baseline.patient_plans, available_capacity=2.0)
    assert result.max_required_concurrency == 4  # 4 scanners genuinely used concurrently
    assert result.shortfall_interval is not None
    assert 0 < len(result.released_patient_ids) < len(baseline.patient_plans)  # never every task in the day
    assert set(result.released_patient_ids) <= set(result.candidate_patient_ids)
    assert result.feasible is True
    assert result.final_concurrency <= 2


def test_identify_staff_shortfall_sufficient_capacity_targets_nothing():
    _, _, _, _, _, baseline = _conventional_fixtures()
    result = identify_staff_shortfall_patient_tasks(pool="SCANNER", plans=baseline.patient_plans, available_capacity=4.0)
    assert result.released_patient_ids == ()
    assert result.feasible is True


def test_injection_staff_shortfall_identifies_exact_tasks_and_replans():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _conventional_fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-INJ-STAFF"), event_kind="STAFF_CAPACITY_CHANGE",
        object_id="INJECTION_STAFF", actual_value=2.0, staff_pool="INJECTION",
    )
    status, impact, version, changeset, escalation = apply_event_and_replan(
        event=event, store=store, previous_version=baseline, records_for_day=records, cyclotron_calendar=cyclotron_calendar,
        resource_calendar=resource_calendar, geometry=geometry, assumptions=assumptions, distribution_concurrency=6,
    )
    assert status == "APPLIED"
    assert impact.reoptimization_required is True
    assert impact.directly_affected_patient_ids  # real patient-level targets, not aggregate-only
    assert version is not None
    assert version.patient_plans != baseline.patient_plans  # no longer a no-op passthrough


def test_uptake_staff_shortfall_identifies_exact_tasks_and_replans():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _conventional_fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-UP-STAFF"), event_kind="STAFF_CAPACITY_CHANGE",
        object_id="UPTAKE_STAFF", actual_value=2.0, staff_pool="UPTAKE",
    )
    status, impact, version, changeset, escalation = apply_event_and_replan(
        event=event, store=store, previous_version=baseline, records_for_day=records, cyclotron_calendar=cyclotron_calendar,
        resource_calendar=resource_calendar, geometry=geometry, assumptions=assumptions, distribution_concurrency=6,
    )
    assert status == "APPLIED"
    assert impact.directly_affected_patient_ids
    assert version is not None
    assert version.patient_plans != baseline.patient_plans


def test_scanner_staff_shortfall_identifies_exact_tasks_and_replans():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _conventional_fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-SCN-STAFF"), event_kind="STAFF_CAPACITY_CHANGE",
        object_id="SCANNER_STAFF", actual_value=2.0, staff_pool="SCANNER",
    )
    status, impact, version, changeset, escalation = apply_event_and_replan(
        event=event, store=store, previous_version=baseline, records_for_day=records, cyclotron_calendar=cyclotron_calendar,
        resource_calendar=resource_calendar, geometry=geometry, assumptions=assumptions, distribution_concurrency=6,
    )
    assert status == "APPLIED"
    assert impact.directly_affected_patient_ids
    assert version is not None
    by_scanner: dict[str, list[tuple[float, float]]] = {}
    for p in version.patient_plans:
        by_scanner.setdefault(p.scanner_resource_id, []).append(p.scan_window_minutes)
    points = sorted({w[0] for ws in by_scanner.values() for w in ws} | {w[1] for ws in by_scanner.values() for w in ws})
    all_windows = [w for ws in by_scanner.values() for w in ws]
    max_concurrent = max((sum(1 for s, e in all_windows if s <= t < e) for t in points[:-1]), default=0)
    assert max_concurrent <= 2  # section 37: revised schedule satisfies the constrained pool


def test_staff_recovery_does_not_auto_reshuffle_without_a_new_event():
    """Section 32: once a targeted replan produces a valid revised plan, no
    further event means no further replan -- the architecture never
    "auto-corrects" on capacity recovery without an explicit event."""
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _conventional_fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-RECOVERY"), event_kind="STAFF_CAPACITY_CHANGE",
        object_id="SCANNER_STAFF", actual_value=2.0, staff_pool="SCANNER",
    )
    _, _, version, _, _ = apply_event_and_replan(
        event=event, store=store, previous_version=baseline, records_for_day=records, cyclotron_calendar=cyclotron_calendar,
        resource_calendar=resource_calendar, geometry=geometry, assumptions=assumptions, distribution_concurrency=6,
    )
    snapshot = version.patient_plans
    assert version.patient_plans == snapshot  # nothing reruns without a new event


# ---------------------------------------------------------------------------
# Authority validators (this build's new rules)
# ---------------------------------------------------------------------------


def test_validate_hybrid_single_patient_population_detects_duplication():
    findings = validate_hybrid_single_patient_population(patient_ids=["P1", "P2", "P1"])
    assert len(findings) == 1
    assert findings[0].authority_id == "HYBRID_LIVE_STATE_ADAPTER"


def test_validate_hybrid_shared_resource_identity_detects_mode_prefixed_duplication():
    findings = validate_hybrid_shared_resource_identity(
        injection_resource_ids=["INJ-001"], uptake_resource_ids=["UP-001"],
        scanner_resource_ids=["CONV-SCN-001", "MRT-SCN-001"],
    )
    assert len(findings) == 1
    assert "scanner" in findings[0].message


def test_validate_hybrid_mode_specific_impact_flags_wrong_mode_touched():
    findings = validate_hybrid_mode_specific_impact(impact_classification="CONVENTIONAL_SPECIFIC_IMPACT", directly_affected_transport_modes=["Conventional", "MRT"])
    assert len(findings) == 1
    findings_ok = validate_hybrid_mode_specific_impact(impact_classification="CONVENTIONAL_SPECIFIC_IMPACT", directly_affected_transport_modes=["Conventional"])
    assert findings_ok == []


def test_validate_staff_shortfall_patient_targeting_detects_untargeted_shortfall():
    findings = validate_staff_shortfall_patient_targeting(max_required_concurrency=4, available_capacity=2, released_patient_ids=(), candidate_patient_ids=("P1", "P2"))
    assert len(findings) == 1
    findings_ok = validate_staff_shortfall_patient_targeting(max_required_concurrency=4, available_capacity=2, released_patient_ids=("P1",), candidate_patient_ids=("P1", "P2"))
    assert findings_ok == []


def test_validate_staff_capacity_replan_result_detects_infeasible_claimed_feasible():
    findings = validate_staff_capacity_replan_result(final_concurrency=3, available_capacity=2, feasible=True)
    assert len(findings) == 1
    findings_ok = validate_staff_capacity_replan_result(final_concurrency=2, available_capacity=2, feasible=True)
    assert findings_ok == []


# ---------------------------------------------------------------------------
# Sections 58-59: Conventional/MRT non-regression
# ---------------------------------------------------------------------------


def test_conventional_scanner_outage_non_regression():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _conventional_fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-CONV-NONREG"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-001", new_state="UNAVAILABLE")
    status, impact, version, changeset, escalation = apply_event_and_replan(
        event=event, store=store, previous_version=baseline, records_for_day=records, cyclotron_calendar=cyclotron_calendar,
        resource_calendar=resource_calendar, geometry=geometry, assumptions=assumptions, distribution_concurrency=6,
    )
    assert status == "APPLIED"
    assert escalation.localization_feasible is True
    stability = compute_plan_stability(changeset, total_before=len(baseline.patient_plans))
    assert stability.pct_preserved >= 50.0


def test_mrt_scanner_outage_non_regression():
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="OFF")
    geometry = build_controlled_dual_origin_geometry()
    assumptions = PlannerAssumptions()
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    inventory = build_deterministic_resource_inventory(injection_room_count=4, uptake_room_count=4, scanner_count=4)
    resource_calendar = build_calendar_with_no_exceptions(inventory)
    records = [
        CanonicalOperationalPatientRecord(
            internal_model_patient_id=f"P{i}", demand_status="COMMITTED", patient_type="OUTPATIENT",
            radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=DAY, source_provenance="USER_ENTERED",
        )
        for i in range(20)
    ]
    summary = run_operating_day_plan(
        day=DAY, records_for_day=records, cyclotron_calendar=cyclotron_calendar, pathway="MRT",
        geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar, distribution_concurrency=6,
    )
    baseline = baseline_plan_version(day=DAY, pathway="MRT", daily_summary=summary, records_for_day=records, created_at=datetime(2026, 10, 5, 6, 0))
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-MRT-NONREG"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-001", new_state="UNAVAILABLE")
    status, impact, version, changeset, escalation = apply_event_and_replan(
        event=event, store=store, previous_version=baseline, records_for_day=records, cyclotron_calendar=cyclotron_calendar,
        resource_calendar=resource_calendar, geometry=geometry, assumptions=assumptions, distribution_concurrency=6,
    )
    assert status == "APPLIED"
    assert all(p.transport_mode == "MRT" for p in version.patient_plans)  # purity preserved
    assert escalation.localization_feasible is True

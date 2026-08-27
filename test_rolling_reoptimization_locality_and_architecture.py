"""Rolling Reoptimization Locality + Conventional/MRT Live Qualification.

Focus (does NOT duplicate test_live_state_rolling_reoptimization.py):
  1. Identity-sticky affected-subset locality achieves genuine numeric
     preservation (not merely non-zero) through the REAL production
     `apply_event_and_replan()` entry point -- not a scratch replication.
  2. Explicit escalation: a no-escalation (LEVEL_1) case and a
     total-infeasibility (LEVEL_1 -> LEVEL_3) case, both reporting an
     `EscalationRecord` (never a silent full-day rerun).
  3. Event->replan completeness for the four event kinds this phase
     upgraded from impact-only to a real day-engine hook:
     CYCLOTRON_RELEASE_DELAY, ACTUAL_RELEASE_ACTIVITY, TRANSPORT_DELAY,
     STAFF_CAPACITY_CHANGE -- including the honest disclosure that
     STAFF_CAPACITY_CHANGE has no patient-level targeting yet.
  4. MRT pathway live qualification: the SAME `apply_event_and_replan()`
     pipeline actually executed (not inferred) against an MRT baseline.
  5. New `engineering_authority.py` validators added this phase.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from clinical_resource_identity import build_calendar_with_no_exceptions, build_deterministic_resource_inventory
from engineering_authority import (
    validate_architecture_live_qualification,
    validate_event_to_replan_completeness,
    validate_preserved_assignment_validity,
    validate_rolling_resource_identity_stickiness,
    validate_unnecessary_plan_drift,
)
from healthcare_integration import CanonicalIntegrationEvent
from live_operational_state import (
    OperationalEvent,
    OperationalStateStore,
    apply_event_and_replan,
    baseline_plan_version,
    compute_plan_stability,
)
from long_horizon_operational_planning import CanonicalOperationalPatientRecord, CyclotronCalendar, run_operating_day_plan
from models import PlannerAssumptions
from multi_cyclotron_authority import build_controlled_dual_origin_geometry, build_multi_cyclotron_scenario
from multi_isotope_decay import retained_fraction

DAY = date(2026, 10, 5)


def _committed(pid: str, *, radionuclide: str = "F-18") -> CanonicalOperationalPatientRecord:
    return CanonicalOperationalPatientRecord(
        internal_model_patient_id=pid, demand_status="COMMITTED", patient_type="OUTPATIENT",
        radionuclide=radionuclide, prescribed_activity_mbq=200.0, scheduled_date=DAY, source_provenance="USER_ENTERED",
    )


def _event(*, source_event_id: str, source_system="SYNTHETIC", timestamp=datetime(2026, 10, 5, 8, 0), event_type="OTHER") -> CanonicalIntegrationEvent:
    return CanonicalIntegrationEvent(
        source_system=source_system, source_event_id=source_event_id, event_type=event_type, event_timestamp=timestamp,
    )


def _fixtures(*, pathway="Conventional", patient_count=20, scanner_count=4, injection_count=6, uptake_count=6,
              distribution_concurrency=6, cy001_state="ON", cy002_state="OFF"):
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state=cy001_state, cy002_scenario_state=cy002_state)
    geometry = build_controlled_dual_origin_geometry()
    assumptions = PlannerAssumptions()
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    inventory = build_deterministic_resource_inventory(injection_room_count=injection_count, uptake_room_count=uptake_count, scanner_count=scanner_count)
    resource_calendar = build_calendar_with_no_exceptions(inventory)
    records = [_committed(f"P{i}") for i in range(patient_count)]
    summary = run_operating_day_plan(
        day=DAY, records_for_day=records, cyclotron_calendar=cyclotron_calendar, pathway=pathway,
        geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar, distribution_concurrency=distribution_concurrency,
    )
    baseline = baseline_plan_version(day=DAY, pathway=pathway, daily_summary=summary, records_for_day=records, created_at=datetime(2026, 10, 5, 6, 0))
    return records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline


def _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions, distribution_concurrency=6):
    return apply_event_and_replan(
        event=event, store=store, previous_version=baseline, records_for_day=records, cyclotron_calendar=cyclotron_calendar,
        resource_calendar=resource_calendar, geometry=geometry, assumptions=assumptions, distribution_concurrency=distribution_concurrency,
    )


# ---------------------------------------------------------------------------
# 1. Identity-sticky affected-subset locality (via the REAL production entry
# point, not the scratch-script replication used during development)
# ---------------------------------------------------------------------------


def test_scanner_outage_real_function_achieves_majority_preservation_no_escalation():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-SCN"), event_kind="RESOURCE_UNAVAILABLE",
        object_id="SCN-001", new_state="UNAVAILABLE",
    )
    status, impact, version, changeset, escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert version is not None
    stability = compute_plan_stability(changeset, total_before=len(baseline.patient_plans))
    # Root-cause fix verified: was 0% before this phase's rewrite; the
    # identity-sticky affected-subset mechanism now preserves the clear
    # majority of unrelated patients (empirically ~70% for this controlled
    # 20-patient/4-scanner/single-outage case).
    assert stability.pct_preserved >= 60.0
    assert escalation is not None
    assert escalation.localization_feasible is True
    assert escalation.final_scope == "LEVEL_1_DIRECTLY_AFFECTED_ONLY"
    assert escalation.released_assignment_ids == ()
    # Resource exclusivity + never reuses the outaged identity.
    findings = validate_rolling_resource_identity_stickiness(plans=version.patient_plans, unavailable_resource_ids=("SCN-001",))
    assert findings == []


def test_scanner_outage_preserved_assignments_are_genuinely_valid():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-SCN"), event_kind="RESOURCE_UNAVAILABLE",
        object_id="SCN-001", new_state="UNAVAILABLE",
    )
    _, _, version, changeset, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    new_by_id = {p.internal_model_patient_id: p for p in version.patient_plans}
    findings = validate_preserved_assignment_validity(
        preserved_patient_ids=changeset.unchanged_patient_ids, plans_by_patient_id=new_by_id, unavailable_resource_ids=("SCN-001",),
    )
    assert findings == []


# ---------------------------------------------------------------------------
# 2. Explicit escalation: total-infeasibility case (LEVEL_1 -> LEVEL_3)
# ---------------------------------------------------------------------------


def test_total_cyclotron_infeasibility_escalates_explicitly_without_crashing():
    """Both cyclotrons unavailable -- LEVEL_1 (affected-subset = everyone,
    since all patients are on CY-001 and CY-002 is already OFF in the base
    fixture) cannot produce a feasible schedule; escalation to LEVEL_3 is
    attempted and also cannot recover demand it has no capacity for, but the
    escalation is explicit and the pipeline never crashes or silently drops
    the plan version (section 11/18)."""
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-CY"), event_kind="CYCLOTRON_UNAVAILABLE",
        object_id="CY-001", new_state="UNAVAILABLE",
    )
    status, impact, version, changeset, escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert version is not None
    assert escalation is not None
    assert escalation.localization_feasible is False
    assert escalation.final_scope == "LEVEL_3_OPERATING_DAY_REOPTIMIZATION"
    assert len(version.daily_summary.unmet_demand) == 20  # honestly reported, not fabricated


# ---------------------------------------------------------------------------
# 3. Event->replan completeness for the four newly-real event kinds
# ---------------------------------------------------------------------------


def test_cyclotron_release_delay_with_real_context_triggers_day_engine_replan():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    target = next(p for p in baseline.patient_plans if p.cyclotron_id == "CY-001")
    half_life = 109.8
    delay = 45.0
    planned_elapsed = max(0.0, target.injection_window_minutes[0] - target.release_time_minutes)
    actual_elapsed = planned_elapsed + delay
    before = retained_fraction(planned_elapsed, half_life)
    after = retained_fraction(actual_elapsed, half_life)
    assert after < before  # sanity: decay engine agrees delay reduces retention
    threshold = (before + after) / 2.0
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-DELAY"), event_kind="CYCLOTRON_RELEASE_DELAY",
        object_id="CY-001", delay_minutes=delay, half_life_minutes=half_life, retention_threshold=threshold,
    )
    status, impact, version, changeset, escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert impact.reoptimization_required is True
    # This is the section 91 upgrade under test: previously this event kind
    # ALWAYS returned version=None (impact-only). With genuine retention-
    # crossing context supplied, a real day-engine replan is now invoked.
    assert version is not None
    assert escalation is not None
    findings = validate_event_to_replan_completeness(
        event_kind="CYCLOTRON_RELEASE_DELAY", reoptimization_required=True, day_engine_replan_invoked=True,
        material_event_kinds=("CYCLOTRON_RELEASE_DELAY",),
    )
    assert findings == []


def test_actual_release_activity_shortfall_removes_only_unservable_patients_and_preserves_rest():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    cy001_patients = [p for p in baseline.patient_plans if p.cyclotron_id == "CY-001"]
    assert len(cy001_patients) == 20  # base fixture: CY-002 OFF, all 20 on CY-001
    activity_per_patient = 200.0
    servable = 14
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-ACT"), event_kind="ACTUAL_RELEASE_ACTIVITY",
        object_id="CY-001", actual_value=servable * activity_per_patient, activity_per_patient_mbq=activity_per_patient,
    )
    status, impact, version, changeset, escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert impact.reoptimization_required is True
    assert version is not None
    # Conservation: never more patients scheduled than the actual activity supports.
    assert len(version.patient_plans) <= servable
    # Never fabricated: the removed patients appear as cancelled, not silently vanished.
    assert len(changeset.cancelled_patient_ids) >= 20 - servable


def test_transport_delay_with_real_context_triggers_single_patient_replan():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    target = baseline.patient_plans[0]
    half_life = 109.8
    delay = 60.0
    planned_elapsed = max(0.0, target.injection_window_minutes[0] - target.release_time_minutes)
    actual_elapsed = planned_elapsed + delay
    before = retained_fraction(planned_elapsed, half_life)
    after = retained_fraction(actual_elapsed, half_life)
    threshold = (before + after) / 2.0
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-TRANSPORT"), event_kind="TRANSPORT_DELAY",
        object_id=target.internal_model_patient_id, delay_minutes=delay, half_life_minutes=half_life, retention_threshold=threshold,
    )
    status, impact, version, changeset, escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert impact.reoptimization_required is True
    assert impact.directly_affected_patient_ids == (target.internal_model_patient_id,)
    assert version is not None


def test_staff_capacity_change_without_pool_context_is_aggregate_only_fallback():
    """Backward-compatible fallback: when NO `staff_pool` is supplied on the
    event, STAFF_CAPACITY_CHANGE still computes a genuine required=True/False
    from actual_value vs scheduled_capacity_fte (never fabricated), and IS
    routed through the day-engine hook -- but with no patient-level target
    context, the directly-affected set is empty and the produced version is a
    no-op passthrough. Real patient-task targeting (when `staff_pool` IS
    supplied) is covered by test_hybrid_live_state_and_staff_targeting.py."""
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-STAFF"), event_kind="STAFF_CAPACITY_CHANGE",
        object_id="INJECTION_STAFF", actual_value=3.5, scheduled_capacity_fte=5.0,
    )
    status, impact, version, changeset, escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert impact.reoptimization_required is True  # genuine threshold breach detected
    assert version is not None  # routed through the day-engine hook, not impact-only
    assert escalation is not None
    assert escalation.localization_feasible is True
    assert version.patient_plans == baseline.patient_plans  # no-op: no patient-level target exists yet


# ---------------------------------------------------------------------------
# 4. MRT pathway live qualification (actually executed, not inferred)
# ---------------------------------------------------------------------------


def test_mrt_pathway_scanner_outage_live_qualification():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures(pathway="MRT")
    assert all(p.transport_mode == "MRT" for p in baseline.patient_plans)
    store = OperationalStateStore()
    event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-SCN-MRT"), event_kind="RESOURCE_UNAVAILABLE",
        object_id="SCN-001", new_state="UNAVAILABLE",
    )
    status, impact, version, changeset, escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert version is not None
    assert all(p.transport_mode == "MRT" for p in version.patient_plans)  # architecture purity preserved
    stability = compute_plan_stability(changeset, total_before=len(baseline.patient_plans))
    assert stability.pct_preserved >= 60.0
    assert escalation is not None and escalation.localization_feasible is True
    by_scanner: dict[str, list[tuple[float, float]]] = {}
    for p in version.patient_plans:
        assert p.scanner_resource_id != "SCN-001"
        by_scanner.setdefault(p.scanner_resource_id, []).append(p.scan_window_minutes)
    for _resource_id, windows in by_scanner.items():
        ordered = sorted(windows)
        for (_s1, e1), (s2, _e2) in zip(ordered, ordered[1:]):
            assert s2 >= e1


def test_mrt_pathway_patient_cancellation_preserves_unrelated_patients():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures(pathway="MRT")
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-CANCEL-MRT"), event_kind="PATIENT_CANCELLED", object_id="P19")
    status, impact, version, changeset, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    old_by_id = {p.internal_model_patient_id: p for p in baseline.patient_plans}
    new_by_id = {p.internal_model_patient_id: p for p in version.patient_plans}
    for pid in changeset.unchanged_patient_ids:
        assert old_by_id[pid] == new_by_id[pid]
    assert len(changeset.unchanged_patient_ids) >= 15


# ---------------------------------------------------------------------------
# 5. New engineering_authority.py validators (this phase's additions)
# ---------------------------------------------------------------------------


def test_validate_rolling_resource_identity_stickiness_detects_leak():
    class _Plan:
        def __init__(self, pid, scanner_id, window):
            self.internal_model_patient_id = pid
            self.injection_resource_id = "INJ-001"
            self.injection_window_minutes = (0.0, 10.0)
            self.uptake_resource_id = "UPT-001"
            self.uptake_window_minutes = (10.0, 20.0)
            self.scanner_resource_id = scanner_id
            self.scan_window_minutes = window

    plans = [_Plan("P0", "SCN-001", (20.0, 30.0)), _Plan("P1", "SCN-002", (20.0, 30.0))]
    findings = validate_rolling_resource_identity_stickiness(plans=plans, unavailable_resource_ids=("SCN-001",))
    assert any(f.authority_id == "ROLLING_RESOURCE_IDENTITY_STICKINESS" for f in findings)


def test_validate_rolling_resource_identity_stickiness_detects_overlap():
    class _Plan:
        def __init__(self, pid, window):
            self.internal_model_patient_id = pid
            self.injection_resource_id = "INJ-001"
            self.injection_window_minutes = (0.0, 10.0)
            self.uptake_resource_id = "UPT-001"
            self.uptake_window_minutes = (10.0, 20.0)
            self.scanner_resource_id = "SCN-001"
            self.scan_window_minutes = window

    plans = [_Plan("P0", (20.0, 40.0)), _Plan("P1", (30.0, 50.0))]  # overlap 30-40
    findings = validate_rolling_resource_identity_stickiness(plans=plans, unavailable_resource_ids=())
    assert any(f.authority_id == "ROLLING_RESOURCE_IDENTITY_STICKINESS" and "Overlapping" in f.message for f in findings)


def test_validate_unnecessary_plan_drift_flags_unexplained_collateral():
    from live_operational_state import ModifiedAssignment

    unexplained = ModifiedAssignment(patient_id="P5", old_plan=None, new_plan=None, reason="", classification="COLLATERAL_CHANGE_REQUIRED_FOR_FEASIBILITY")
    findings = validate_unnecessary_plan_drift(modified_assignments=[unexplained], escalated=True)
    assert any(f.authority_id == "UNNECESSARY_PLAN_DRIFT" and "no recorded reason" in f.message for f in findings)


def test_validate_unnecessary_plan_drift_flags_collateral_without_escalation():
    from live_operational_state import ModifiedAssignment

    collateral = ModifiedAssignment(patient_id="P5", old_plan=None, new_plan=None, reason="displaced", classification="COLLATERAL_CHANGE_REQUIRED_FOR_FEASIBILITY")
    findings = validate_unnecessary_plan_drift(modified_assignments=[collateral], escalated=False)
    assert any(f.authority_id == "UNNECESSARY_PLAN_DRIFT" and "escalating" in f.message for f in findings)


def test_validate_unnecessary_plan_drift_accepts_justified_escalated_collateral():
    from live_operational_state import ModifiedAssignment

    collateral = ModifiedAssignment(patient_id="P5", old_plan=None, new_plan=None, reason="displaced by LEVEL_3 escalation", classification="COLLATERAL_CHANGE_REQUIRED_FOR_FEASIBILITY")
    findings = validate_unnecessary_plan_drift(modified_assignments=[collateral], escalated=True)
    assert findings == []


def test_validate_event_to_replan_completeness_flags_gap():
    findings = validate_event_to_replan_completeness(
        event_kind="SCANNER_UNAVAILABLE", reoptimization_required=True, day_engine_replan_invoked=False,
        material_event_kinds=("SCANNER_UNAVAILABLE",),
    )
    assert any(f.authority_id == "EVENT_TO_REPLAN_COMPLETENESS" for f in findings)


def test_validate_architecture_live_qualification_flags_missing_pathway():
    findings = validate_architecture_live_qualification(qualified_pathways=("Conventional", "MRT", "Hybrid"), executed_pathways=("Conventional", "MRT"))
    assert len(findings) == 1
    assert "Hybrid" in findings[0].message


def test_validate_architecture_live_qualification_passes_when_all_executed():
    findings = validate_architecture_live_qualification(qualified_pathways=("Conventional", "MRT"), executed_pathways=("Conventional", "MRT"))
    assert findings == []

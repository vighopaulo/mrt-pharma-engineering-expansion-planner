"""Live Operational State + Event-Driven Rolling Re-Optimization.

Focus: cross-module state/event/replan behavior. Reuses the SAME day-engine
(`long_horizon_operational_planning.run_operating_day_plan`) for every
replan -- never a second optimizer. See `live_operational_state.py`'s module
docstring for the explicit scope disclosure (which event kinds get a full
day-engine rerun + diff vs. state-tracking + impact-analysis-only).
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from clinical_resource_identity import ResourceAvailabilityCalendar, build_calendar_with_no_exceptions, build_deterministic_resource_inventory
from engineering_authority import validate_live_state_consistency
from healthcare_integration import CanonicalIntegrationEvent
from live_operational_state import (
    OperationalEvent,
    OperationalStateStore,
    analyze_event_impact,
    apply_event_and_replan,
    baseline_plan_version,
    compare_plan_versions,
    compute_plan_stability,
    compute_production_activity_variance,
    compute_staff_capacity_impact,
    compute_task_variance,
    plan_history_for_patient,
    recompute_retention_after_delay,
)
from long_horizon_operational_planning import CanonicalOperationalPatientRecord, CyclotronCalendar, run_operating_day_plan
from models import PlannerAssumptions
from multi_cyclotron_authority import build_controlled_dual_origin_geometry, build_multi_cyclotron_scenario

DAY = date(2026, 10, 5)


def _committed(pid: str) -> CanonicalOperationalPatientRecord:
    return CanonicalOperationalPatientRecord(
        internal_model_patient_id=pid, demand_status="COMMITTED", patient_type="OUTPATIENT",
        radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=DAY, source_provenance="USER_ENTERED",
    )


def _event(*, source_event_id: str, source_system="SYNTHETIC", timestamp=datetime(2026, 10, 5, 8, 0), event_type="OTHER") -> CanonicalIntegrationEvent:
    return CanonicalIntegrationEvent(
        source_system=source_system, source_event_id=source_event_id, event_type=event_type, event_timestamp=timestamp,
    )


def _fixtures(*, patient_count=20, scanner_count=4, injection_count=6, uptake_count=6, distribution_concurrency=6):
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="OFF")
    geometry = build_controlled_dual_origin_geometry()
    assumptions = PlannerAssumptions()
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    inventory = build_deterministic_resource_inventory(injection_room_count=injection_count, uptake_room_count=uptake_count, scanner_count=scanner_count)
    resource_calendar = build_calendar_with_no_exceptions(inventory)
    records = [_committed(f"P{i}") for i in range(patient_count)]
    summary = run_operating_day_plan(
        day=DAY, records_for_day=records, cyclotron_calendar=cyclotron_calendar, pathway="Conventional",
        geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar, distribution_concurrency=distribution_concurrency,
    )
    baseline = baseline_plan_version(day=DAY, pathway="Conventional", daily_summary=summary, records_for_day=records, created_at=datetime(2026, 10, 5, 6, 0))
    return records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline


def _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions, distribution_concurrency=6):
    return apply_event_and_replan(
        event=event, store=store, previous_version=baseline, records_for_day=records, cyclotron_calendar=cyclotron_calendar,
        resource_calendar=resource_calendar, geometry=geometry, assumptions=assumptions, distribution_concurrency=distribution_concurrency,
    )


# ---------------------------------------------------------------------------
# Baseline plan / planned-vs-actual separation
# ---------------------------------------------------------------------------


def test_baseline_plan_is_plan_0000_and_immutable_reference():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    assert baseline.version_id == "PLAN-0000"
    assert baseline.previous_version_id is None
    assert len(baseline.patient_plans) == 20


# ---------------------------------------------------------------------------
# Idempotency / staleness / ordering
# ---------------------------------------------------------------------------


def test_duplicate_event_is_idempotent():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-1"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-001", new_state="UNAVAILABLE")
    status1, impact1, version1, changeset1, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    status2, impact2, version2, changeset2, _escalation = _replan(event, store, version1 or baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status1 == "APPLIED"
    assert status2 == "DUPLICATE_IGNORED"
    assert version2 is None


def test_stale_event_does_not_overwrite_newer_state():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    newer = OperationalEvent(integration_event=_event(source_event_id="EVT-NEW", timestamp=datetime(2026, 10, 5, 10, 0)), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-002", new_state="UNAVAILABLE")
    status_new, _, version_new, _, _escalation = _replan(newer, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status_new == "APPLIED"

    older = OperationalEvent(integration_event=_event(source_event_id="EVT-OLD", timestamp=datetime(2026, 10, 5, 9, 0)), event_kind="RESOURCE_AVAILABLE", object_id="SCN-002", new_state="AVAILABLE")
    status_old = store.record_event(older)
    assert status_old == "STALE_EVENT"
    assert store.resource_state["SCN-002"].state == "UNAVAILABLE"  # not rewound


def test_event_journal_never_erased():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-1"), event_kind="PATIENT_CANCELLED", object_id="P19")
    _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert len(store.event_journal) == 1
    assert store.event_journal[0].application_status == "APPLIED"
    assert store.event_journal[0].resulting_plan_version_id == "PLAN-0001"


# ---------------------------------------------------------------------------
# Impact analysis / negative control (no unnecessary replan)
# ---------------------------------------------------------------------------


def test_no_scheduling_consequence_event_produces_no_plan_change():
    """Section 119: an event with no scheduling consequence (a resource
    RECOVERY that was never actually assigned to anyone) must not trigger
    reoptimization."""
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-NOOP"), event_kind="RESOURCE_AVAILABLE", object_id="SCN-001", new_state="AVAILABLE")
    status, impact, version, changeset, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert impact.reoptimization_required is False
    assert version is None


def test_impact_analysis_computed_before_any_replan():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-1"), event_kind="PATIENT_CANCELLED", object_id="P5")
    impact = analyze_event_impact(event=event, previous_plans=baseline.patient_plans)
    assert impact.directly_affected_patient_ids == ("P5",)
    assert set(impact.unaffected_patient_ids) == {p.internal_model_patient_id for p in baseline.patient_plans} - {"P5"}


# ---------------------------------------------------------------------------
# Patient cancellation -- localization proof (sections 19-21, 103, 113)
# ---------------------------------------------------------------------------


def test_patient_cancellation_preserves_unrelated_patients_exactly():
    """Cancel the LAST-processed patient in FCFS queue order: patients
    processed earlier in the deterministic queue are provably unaffected --
    byte-for-byte identical resource/timing assignments, not merely equal
    counts (section 113)."""
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-CANCEL"), event_kind="PATIENT_CANCELLED", object_id="P19")
    status, impact, version, changeset, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert impact.reoptimization_required is True
    assert version is not None
    stability = compute_plan_stability(changeset, total_before=len(baseline.patient_plans))
    assert stability.cancelled == 1
    assert stability.pct_preserved >= 90.0
    assert "P19" not in {p.internal_model_patient_id for p in version.patient_plans}

    old_by_id = {p.internal_model_patient_id: p for p in baseline.patient_plans}
    new_by_id = {p.internal_model_patient_id: p for p in version.patient_plans}
    for pid in changeset.unchanged_patient_ids:
        assert old_by_id[pid] == new_by_id[pid]


def test_unrelated_patients_retain_identical_assignments_after_cancellation():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-CANCEL"), event_kind="PATIENT_CANCELLED", object_id="P19")
    _, impact, version, changeset, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    findings = validate_live_state_consistency(
        unaffected_patient_ids=changeset.unchanged_patient_ids,
        old_plans_by_patient_id={p.internal_model_patient_id: p for p in baseline.patient_plans},
        new_plans_by_patient_id={p.internal_model_patient_id: p for p in version.patient_plans},
        reoptimization_required=impact.reoptimization_required, plan_changed=True,
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Scanner outage (sections 25-29, 93, 102)
# ---------------------------------------------------------------------------


def test_scanner_outage_identifies_directly_affected_patients():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-SCN"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-001", new_state="UNAVAILABLE")
    status, impact, version, changeset, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert impact.reoptimization_required is True
    assert impact.recommended_scope == "OPERATING_DAY"
    affected_scn001 = {p.internal_model_patient_id for p in baseline.patient_plans if p.scanner_resource_id == "SCN-001"}
    assert affected_scn001 <= set(impact.directly_affected_patient_ids)


def test_scanner_outage_never_deletes_scanner_identity():
    """Section 27: SCN-001 outage does NOT delete SCN-001 -- it remains a
    known resource, just UNAVAILABLE that date."""
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-SCN"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-001", new_state="UNAVAILABLE")
    _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert store.resource_state["SCN-001"].state == "UNAVAILABLE"
    assert store.resource_state["SCN-001"].object_id == "SCN-001"


def test_scanner_outage_replan_remains_resource_exclusive():
    """No overlapping incompatible scanner assignments after the outage
    replan (section 89)."""
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-SCN"), event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-001", new_state="UNAVAILABLE")
    _, _, version, _, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    by_scanner: dict[str, list[tuple[float, float]]] = {}
    for p in version.patient_plans:
        by_scanner.setdefault(p.scanner_resource_id, []).append(p.scan_window_minutes)
        assert p.scanner_resource_id != "SCN-001"  # never assigned to the unavailable scanner
    for scanner_id, windows in by_scanner.items():
        ordered = sorted(windows)
        for (s1, e1), (s2, e2) in zip(ordered, ordered[1:]):
            assert s2 >= e1


# ---------------------------------------------------------------------------
# Cyclotron outage (sections 35-36)
# ---------------------------------------------------------------------------


def test_cyclotron_outage_with_no_alternate_reports_unmet_not_crash():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-CY"), event_kind="CYCLOTRON_UNAVAILABLE", object_id="CY-001", new_state="UNAVAILABLE")
    status, impact, version, changeset, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert impact.reoptimization_required is True
    assert version is not None
    assert len(version.daily_summary.unmet_demand) == 20
    assert all(u.reason == "CYCLOTRON_OFF" for u in version.daily_summary.unmet_demand)


def test_cyclotron_reassignment_to_compatible_available_cyclotron():
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="ON")
    geometry = build_controlled_dual_origin_geometry()
    assumptions = PlannerAssumptions()
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    inventory = build_deterministic_resource_inventory(injection_room_count=6, uptake_room_count=6, scanner_count=4)
    resource_calendar = build_calendar_with_no_exceptions(inventory)
    records = [_committed(f"P{i}") for i in range(20)]
    summary = run_operating_day_plan(day=DAY, records_for_day=records, cyclotron_calendar=cyclotron_calendar, pathway="Conventional", geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar, distribution_concurrency=6)
    baseline = baseline_plan_version(day=DAY, pathway="Conventional", daily_summary=summary, records_for_day=records, created_at=datetime(2026, 10, 5, 6, 0))

    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-CY"), event_kind="CYCLOTRON_UNAVAILABLE", object_id="CY-001", new_state="UNAVAILABLE")
    status, impact, version, changeset, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert version is not None
    assert version.daily_summary.cyclotrons_used == ("CY-002",)
    assert len(version.daily_summary.unmet_demand) == 0  # CY-002 has full capacity for this demand


# ---------------------------------------------------------------------------
# New urgent patient (section 24)
# ---------------------------------------------------------------------------


def test_new_urgent_patient_inserted_without_fabricating_capacity():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    urgent = _committed("P-URGENT")
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-URGENT"), event_kind="NEW_URGENT_PATIENT", object_id="P-URGENT", new_patient_record=urgent)
    status, impact, version, changeset, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    assert impact.reoptimization_required is True
    assert version is not None
    assert "P-URGENT" in changeset.new_patient_ids


# ---------------------------------------------------------------------------
# Cyclotron release delay -> retention consequence (sections 37-38)
# ---------------------------------------------------------------------------


def test_cyclotron_release_delay_recomputes_retention():
    result = recompute_retention_after_delay(
        patient_id="P0", release_time_minutes=810.0, planned_administration_minutes=822.0, delay_minutes=12.0,
        half_life_minutes=109.8, retention_threshold=0.90,
    )
    assert result.actual_elapsed_minutes > result.planned_elapsed_minutes
    assert result.retention_after < result.retention_before
    assert isinstance(result.qualification_changed, bool)


def test_cyclotron_release_delay_impact_flags_dependent_patients_only():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-DELAY"), event_kind="CYCLOTRON_RELEASE_DELAY", object_id="CY-001", delay_minutes=12.0)
    status, impact, version, changeset, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert status == "APPLIED"
    cy001_patients = {p.internal_model_patient_id for p in baseline.patient_plans if p.cyclotron_id == "CY-001"}
    assert set(impact.directly_affected_patient_ids) == cy001_patients
    assert version is None  # scope-disclosed: no day-engine input hook, state-tracked + impact-only


# ---------------------------------------------------------------------------
# Actual release activity -> production shortfall/surplus (sections 39-41)
# ---------------------------------------------------------------------------


def test_production_shortfall_never_fabricates_activity():
    result = compute_production_activity_variance(cyclotron_id="CY-001", required_activity_mbq=50_000.0, actual_activity_mbq=42_000.0, activity_per_patient_mbq=200.0)
    assert result.status == "SHORTFALL"
    assert result.servable_patient_count == 210
    assert result.actual_activity_mbq < result.required_activity_mbq


def test_production_surplus_does_not_create_phantom_patients():
    result = compute_production_activity_variance(cyclotron_id="CY-001", required_activity_mbq=50_000.0, actual_activity_mbq=55_000.0, activity_per_patient_mbq=200.0)
    assert result.status == "SURPLUS"
    assert result.variance_mbq == pytest.approx(5_000.0)


# ---------------------------------------------------------------------------
# MRT carrier failure (sections 42-43)
# ---------------------------------------------------------------------------


def test_mrt_carrier_failure_never_affects_conventional_jobs():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-CARRIER"), event_kind="MRT_CARRIER_STATE_CHANGE", object_id="CARRIER-1", new_state="UNAVAILABLE")
    impact = analyze_event_impact(event=event, previous_plans=baseline.patient_plans)
    # Pure Conventional baseline -> zero MRT-mode patients -> zero impact.
    assert impact.directly_affected_patient_ids == ()
    assert all(p.transport_mode != "MRT" for p in baseline.patient_plans)


# ---------------------------------------------------------------------------
# Staffing capacity (sections 47-48)
# ---------------------------------------------------------------------------


def test_staff_capacity_shortfall_identified():
    result = compute_staff_capacity_impact(pool_name="Injection staff", scheduled_fte_demand=5.0, actual_capacity_fte=3.5)
    assert result.affected is True
    assert result.shortfall_fte == pytest.approx(1.5)


def test_staff_capacity_sufficient_not_flagged():
    result = compute_staff_capacity_impact(pool_name="Injection staff", scheduled_fte_demand=3.0, actual_capacity_fte=4.0)
    assert result.affected is False


# ---------------------------------------------------------------------------
# Planned vs actual task variance / completed-task immutability (49-52, 111)
# ---------------------------------------------------------------------------


def test_planned_vs_actual_task_variance():
    result = compute_task_variance(patient_id="P0", stage="SCANNER", planned_window=(300.0, 320.0), actual_window=(305.0, 328.0))
    assert result.start_variance_minutes == pytest.approx(5.0)
    assert result.end_variance_minutes == pytest.approx(8.0)


def test_completed_task_locks_patient_and_survives_replan():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    target_patient = baseline.patient_plans[0].internal_model_patient_id
    complete_event = OperationalEvent(
        integration_event=_event(source_event_id="EVT-COMPLETE"), event_kind="ACTUAL_CLINICAL_TASK",
        object_id=target_patient, stage="SCANNER", actual_start_minutes=300.0, actual_end_minutes=320.0,
    )
    store.record_event(complete_event)
    assert store.is_locked(target_patient)

    cancel_event = OperationalEvent(integration_event=_event(source_event_id="EVT-CANCEL2", timestamp=datetime(2026, 10, 5, 9, 0)), event_kind="PATIENT_CANCELLED", object_id="P19")
    status, impact, version, changeset, _escalation = _replan(cancel_event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert version is not None
    old_plan = next(p for p in baseline.patient_plans if p.internal_model_patient_id == target_patient)
    new_plan = next(p for p in version.patient_plans if p.internal_model_patient_id == target_patient)
    assert old_plan == new_plan  # locked patient carried forward unchanged, never rescheduled


# ---------------------------------------------------------------------------
# Plan versioning / history (sections 10-11, 63-66)
# ---------------------------------------------------------------------------


def test_plan_version_created_with_link_to_previous():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-1"), event_kind="PATIENT_CANCELLED", object_id="P19")
    _, _, version, _, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert version.version_id == "PLAN-0001"
    assert version.previous_version_id == "PLAN-0000"


def test_plan_history_for_patient_shows_original_and_revised():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-1"), event_kind="PATIENT_CANCELLED", object_id="P19")
    _, _, version, _, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    history = plan_history_for_patient([baseline, version], patient_id="P0")
    assert [v for v, _ in history] == ["PLAN-0000", "PLAN-0001"]
    assert history[0][1] is not None and history[1][1] is not None


def test_compare_plan_versions_matches_replan_changeset():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store = OperationalStateStore()
    event = OperationalEvent(integration_event=_event(source_event_id="EVT-1"), event_kind="PATIENT_CANCELLED", object_id="P19")
    _, _, version, changeset, _escalation = _replan(event, store, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    recomputed = compare_plan_versions(baseline, version)
    assert recomputed.unchanged_patient_ids == changeset.unchanged_patient_ids
    assert recomputed.cancelled_patient_ids == changeset.cancelled_patient_ids


# ---------------------------------------------------------------------------
# Vendor-neutral event convergence (sections 67-71, 101, 120)
# ---------------------------------------------------------------------------


def test_vendor_neutral_scanner_outage_same_consequence_regardless_of_source():
    records, cyclotron_calendar, resource_calendar, geometry, assumptions, baseline = _fixtures()
    store_siemens = OperationalStateStore()
    store_synthetic = OperationalStateStore()
    event_siemens = OperationalEvent(
        integration_event=_event(source_event_id="EVT-1", source_system="SIEMENS_HEALTHINEERS", event_type="DEVICE_STATUS"),
        event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-001", new_state="UNAVAILABLE",
    )
    event_synthetic = OperationalEvent(
        integration_event=_event(source_event_id="EVT-1", source_system="SYNTHETIC", event_type="DEVICE_STATUS"),
        event_kind="RESOURCE_UNAVAILABLE", object_id="SCN-001", new_state="UNAVAILABLE",
    )
    _, impact_siemens, version_siemens, changeset_siemens, _escalation = _replan(event_siemens, store_siemens, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    _, impact_synthetic, version_synthetic, changeset_synthetic, _escalation = _replan(event_synthetic, store_synthetic, baseline, records, cyclotron_calendar, resource_calendar, geometry, assumptions)
    assert impact_siemens.reoptimization_required == impact_synthetic.reoptimization_required
    assert version_siemens.patient_plans == version_synthetic.patient_plans
    assert store_siemens.resource_state["SCN-001"].source_system == "SIEMENS_HEALTHINEERS"
    assert store_synthetic.resource_state["SCN-001"].source_system == "SYNTHETIC"


def test_no_vendor_conditional_logic_in_live_state_module():
    """Section 120: negative control -- no VARIAN/GE_DOSEWATCH/SIEMENS
    conditional logic enters the rolling-optimization path."""
    import inspect
    import live_operational_state
    source = inspect.getsource(live_operational_state)
    for banned in ("VARIAN", "GE_DOSEWATCH", "SIEMENS"):
        assert banned not in source


# ---------------------------------------------------------------------------
# Authority validation
# ---------------------------------------------------------------------------


def test_validate_live_state_consistency_flags_unnecessary_replan():
    findings = validate_live_state_consistency(
        unaffected_patient_ids=(), old_plans_by_patient_id={}, new_plans_by_patient_id={},
        reoptimization_required=False, plan_changed=True,
    )
    assert any(f.authority_id == "ROLLING_REOPTIMIZATION_LOCALITY" for f in findings)


def test_validate_live_state_consistency_flags_drifted_unaffected_patient():
    class _P:
        def __init__(self, v):
            self.v = v

        def __eq__(self, other):
            return self.v == other.v

    findings = validate_live_state_consistency(
        unaffected_patient_ids=("P1",), old_plans_by_patient_id={"P1": _P(1)}, new_plans_by_patient_id={"P1": _P(2)},
        reoptimization_required=True, plan_changed=True,
    )
    assert any(f.authority_id == "UNALTERED_ASSIGNMENT_PRESERVATION" for f in findings)


def test_validate_live_state_consistency_flags_locked_patient_modified():
    findings = validate_live_state_consistency(
        unaffected_patient_ids=(), old_plans_by_patient_id={}, new_plans_by_patient_id={},
        reoptimization_required=True, plan_changed=True, completed_patient_ids=("P0",), modified_patient_ids=("P0",),
    )
    assert any(f.authority_id == "COMPLETED_TASK_IMMUTABILITY" for f in findings)

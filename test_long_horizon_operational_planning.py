"""Controlled tests: Long-Horizon Patient-Aware Operational Planning.

Covers: operating calendar, canonical operational patient record (committed vs
forecast), multi-day orchestration reusing the existing day engine, cyclotron
ON/OFF-by-date reassignment, multi-day patient continuity, weekly/monthly
aggregation, and horizon-level validation (duplicate scheduling, inbound room
overlap, persistent asset identity).
"""

from __future__ import annotations

from datetime import date

import pytest

from clinical_resource_identity import build_calendar_with_no_exceptions, build_deterministic_resource_inventory
from long_horizon_operational_planning import (
    CanonicalOperationalPatientRecord,
    CyclotronCalendar,
    OperatingCalendar,
    is_synthetic_forecast_id,
    run_long_horizon_operational_plan,
    validate_inbound_room_no_overlap,
    validate_no_duplicate_committed_scheduling,
)
from models import PlannerAssumptions
from multi_cyclotron_authority import build_controlled_dual_origin_geometry, build_multi_cyclotron_scenario


def _geometry_and_calendar():
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="ON")
    geometry = build_controlled_dual_origin_geometry()
    return geometry, configured


def _resource_calendar(*, scanners: int = 2, injection_resources: int = 2, uptake_resources: int = 2):
    inventory = build_deterministic_resource_inventory(
        injection_room_count=injection_resources, uptake_room_count=uptake_resources, scanner_count=scanners,
    )
    return build_calendar_with_no_exceptions(inventory)


def _committed(patient_id: str, day: date, radionuclide: str = "F-18", patient_type: str = "OUTPATIENT", **kwargs) -> CanonicalOperationalPatientRecord:
    return CanonicalOperationalPatientRecord(
        internal_model_patient_id=patient_id, demand_status="COMMITTED", patient_type=patient_type,
        radionuclide=radionuclide, prescribed_activity_mbq=200.0, scheduled_date=day,
        source_provenance="USER_ENTERED", **kwargs,
    )


def test_operating_calendar_respects_weekdays_and_explicit_exceptions() -> None:
    calendar = OperatingCalendar(
        planning_start_date=date(2026, 10, 5), planning_end_date=date(2026, 10, 11),
        non_operating_dates=frozenset({date(2026, 10, 7)}),
    )
    operating = calendar.operating_dates()
    assert date(2026, 10, 5) in operating  # Monday
    assert date(2026, 10, 7) not in operating  # explicit exception (Wednesday)
    assert date(2026, 10, 10) not in operating  # Saturday, not in default operating_weekdays
    assert date(2026, 10, 11) not in operating  # Sunday


def test_forecast_record_requires_synthetic_identifier() -> None:
    assert is_synthetic_forecast_id("FORECAST-2026-10-15-F18-001")
    assert not is_synthetic_forecast_id("P17")
    with pytest.raises(ValueError):
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P17", demand_status="FORECAST", patient_type="OUTPATIENT",
            radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5),
            source_provenance="FORECAST_MODEL",
        )


def test_cyclotron_off_day_reassigns_to_compatible_on_cyclotron_without_losing_demand() -> None:
    """Sections 23-25: CY-001 OFF on one date must not delete patient demand
    -- production reassigns to CY-002, still ON."""
    geometry, configured = _geometry_and_calendar()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=date(2026, 10, 5), planning_end_date=date(2026, 10, 6))
    cyclotron_calendar = CyclotronCalendar(
        configured_cyclotrons=configured,
        scenario_state_overrides_by_date={date(2026, 10, 6): {"CY-001": "OFF"}},
    )
    records = [_committed(f"P{i}", day) for i, day in enumerate((date(2026, 10, 5), date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 6)))]

    plan = run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar,
        pathway="Conventional", geometry=geometry, assumptions=assumptions,
        resource_calendar=_resource_calendar(scanners=2, injection_resources=2, uptake_resources=2), distribution_concurrency=2,
    )
    by_day = {s.day: s for s in plan.daily_summaries}
    assert by_day[date(2026, 10, 5)].cyclotrons_used == ("CY-001",)
    assert by_day[date(2026, 10, 6)].cyclotrons_used == ("CY-002",)
    # No patient demand lost -- same committed count both days.
    assert by_day[date(2026, 10, 5)].committed_demand_count == by_day[date(2026, 10, 6)].committed_demand_count == 2
    assert plan.horizon_passed


def test_committed_vs_forecast_never_conflated() -> None:
    geometry, configured = _geometry_and_calendar()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=date(2026, 10, 5), planning_end_date=date(2026, 10, 5))
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    records = [
        _committed("P1", date(2026, 10, 5)),
        _committed("P2", date(2026, 10, 5)),
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="FORECAST-2026-10-05-F18-001", demand_status="FORECAST",
            patient_type="OUTPATIENT", radionuclide="F-18", prescribed_activity_mbq=200.0,
            scheduled_date=date(2026, 10, 5), source_provenance="FORECAST_MODEL",
        ),
    ]
    plan = run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar,
        pathway="Conventional", geometry=geometry, assumptions=assumptions,
        resource_calendar=_resource_calendar(scanners=2, injection_resources=2, uptake_resources=2), distribution_concurrency=2,
    )
    assert plan.committed_patient_count == 2
    assert plan.forecast_demand_count == 1
    # Forecast demand is never exposed as a named committed patient plan.
    assert {p.internal_model_patient_id for p in plan.patient_plans} == {"P1", "P2"}


def test_multi_day_patient_continuity_and_weekly_monthly_aggregation() -> None:
    geometry, configured = _geometry_and_calendar()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=date(2026, 10, 5), planning_end_date=date(2026, 10, 9))
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    records = []
    for i, day in enumerate(calendar.operating_dates()):
        records.append(_committed(f"P{i}", day))

    plan = run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar,
        pathway="Conventional", geometry=geometry, assumptions=assumptions,
        resource_calendar=_resource_calendar(scanners=2, injection_resources=2, uptake_resources=2), distribution_concurrency=2,
    )
    assert len(plan.daily_summaries) == 5
    assert len(plan.weekly_summaries) == 1
    assert plan.weekly_summaries[0].committed_demand_count == 5
    assert len(plan.monthly_summaries) == 1
    assert plan.monthly_summaries[0].committed_demand_count == 5
    # Each patient appears exactly once across the whole horizon.
    plan_ids = [p.internal_model_patient_id for p in plan.patient_plans]
    assert len(plan_ids) == len(set(plan_ids)) == 5


def test_duplicate_committed_scheduling_detected() -> None:
    """Section 42: a committed (patient, protocol) pair scheduled on two
    dates is a conservation violation."""
    records = [
        _committed("P17", date(2026, 10, 5), protocol_id="PROTO-A"),
        _committed("P17", date(2026, 10, 6), protocol_id="PROTO-A"),
    ]
    findings = validate_no_duplicate_committed_scheduling(records)
    assert len(findings) == 1
    assert "P17" in findings[0].affected_object_ids


def test_repeated_procedures_for_same_patient_are_not_flagged() -> None:
    """Section 43: distinct procedures (different protocol_id) for the same
    patient are legitimate, not a duplicate-scheduling violation."""
    records = [
        _committed("P17", date(2026, 10, 5), protocol_id="PROTO-A"),
        _committed("P17", date(2026, 10, 6), protocol_id="PROTO-B"),
    ]
    assert validate_no_duplicate_committed_scheduling(records) == []


def test_inbound_room_overlap_detected_across_day_boundaries() -> None:
    """Section 18/41: inbound occupancy spans days; overlapping admission
    intervals in the same fixed room are a violation."""
    records = [
        _committed(
            "P1", date(2026, 10, 1), patient_type="INBOUND_PATIENT",
            admission_datetime=date(2026, 10, 1), expected_discharge_date=date(2026, 10, 7),
            existing_room_id="IR-03",
        ),
        _committed(
            "P2", date(2026, 10, 5), patient_type="INBOUND_PATIENT",
            admission_datetime=date(2026, 10, 5), expected_discharge_date=date(2026, 10, 10),
            existing_room_id="IR-03",
        ),
    ]
    findings = validate_inbound_room_no_overlap(records)
    assert len(findings) == 1
    assert "IR-03" in findings[0].affected_object_ids


def test_inbound_room_non_overlapping_intervals_pass() -> None:
    records = [
        _committed(
            "P1", date(2026, 10, 1), patient_type="INBOUND_PATIENT",
            admission_datetime=date(2026, 10, 1), expected_discharge_date=date(2026, 10, 5),
            existing_room_id="IR-03",
        ),
        _committed(
            "P2", date(2026, 10, 5), patient_type="INBOUND_PATIENT",
            admission_datetime=date(2026, 10, 5), expected_discharge_date=date(2026, 10, 10),
            existing_room_id="IR-03",
        ),
    ]
    assert validate_inbound_room_no_overlap(records) == []


def test_operational_only_study_scope_supported() -> None:
    """Section 34: the planner works under OPERATIONAL_ONLY without any
    CapEx dependency."""
    geometry, configured = _geometry_and_calendar()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=date(2026, 10, 5), planning_end_date=date(2026, 10, 5))
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    records = [_committed("P1", date(2026, 10, 5))]
    plan = run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar,
        pathway="Conventional", geometry=geometry, assumptions=assumptions,
        resource_calendar=_resource_calendar(scanners=1, injection_resources=1, uptake_resources=1), distribution_concurrency=1,
        study_scope="OPERATIONAL_ONLY",
    )
    assert plan.study_scope == "OPERATIONAL_ONLY"
    assert plan.horizon_passed


def test_mrt_pathway_long_horizon_mode() -> None:
    """Section 37: MRT-only long-horizon mode works through the same
    orchestration."""
    geometry, configured = _geometry_and_calendar()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=date(2026, 10, 5), planning_end_date=date(2026, 10, 5))
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    records = [_committed("P1", date(2026, 10, 5)), _committed("P2", date(2026, 10, 5))]
    plan = run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar,
        pathway="MRT", geometry=geometry, assumptions=assumptions,
        resource_calendar=_resource_calendar(scanners=1, injection_resources=1, uptake_resources=1), distribution_concurrency=1,
    )
    assert plan.pathway == "MRT"
    assert plan.daily_summaries[0].pathway == "MRT"
    assert plan.horizon_passed

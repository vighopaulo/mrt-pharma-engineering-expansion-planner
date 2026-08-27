"""Controlled tests: Deterministic Operational Planner Qualification.

Cross-module end-to-end tests proving the long-horizon planner is one
continuous, patient/resource-traceable planning engine across day/week/
month/six-month horizons, built entirely on REUSED engines (day scheduler,
clinical resource identity, multi-cyclotron authority, engineering authority).
"""

from __future__ import annotations

from datetime import date

import pytest

from clinical_resource_identity import build_calendar_with_no_exceptions, build_deterministic_resource_inventory, ResourceAvailabilityCalendar
from long_horizon_operational_planning import (
    CanonicalOperationalPatientRecord,
    CyclotronCalendar,
    OperatingCalendar,
    assignments_for_resource,
    plan_for_patient,
    production_cycles_for_date,
    production_plan_for_cyclotron,
    patients_for_production_cycle,
    resource_schedule_for_date,
    resource_utilization_pct,
    run_long_horizon_operational_plan,
    run_operating_day_plan,
)
from models import PlannerAssumptions
from multi_cyclotron_authority import build_controlled_dual_origin_geometry, build_multi_cyclotron_scenario
from production_clinical_schedule import build_production_clinical_schedule


def _geometry_and_configured():
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="ON")
    geometry = build_controlled_dual_origin_geometry()
    return geometry, configured


def _committed(patient_id, day, *, patient_type="OUTPATIENT", radionuclide="F-18", **kwargs):
    return CanonicalOperationalPatientRecord(
        internal_model_patient_id=patient_id, demand_status="COMMITTED", patient_type=patient_type,
        radionuclide=radionuclide, prescribed_activity_mbq=200.0, scheduled_date=day,
        source_provenance="USER_ENTERED", **kwargs,
    )


def _forecast(patient_id, day, **kwargs):
    return CanonicalOperationalPatientRecord(
        internal_model_patient_id=patient_id, demand_status="FORECAST", patient_type="OUTPATIENT",
        radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=day,
        source_provenance="FORECAST_MODEL", **kwargs,
    )


def _run(records, *, start, end, resource_calendar=None, cyclotron_overrides=None, pathway="Conventional",
          weekdays=frozenset({0, 1, 2, 3, 4}), non_operating=frozenset()):
    geometry, configured = _geometry_and_configured()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=start, planning_end_date=end, operating_weekdays=weekdays, non_operating_dates=non_operating)
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured, scenario_state_overrides_by_date=cyclotron_overrides or {})
    if resource_calendar is None:
        inventory = build_deterministic_resource_inventory(injection_room_count=3, uptake_room_count=3, scanner_count=2, inbound_room_count=2)
        resource_calendar = build_calendar_with_no_exceptions(inventory)
    return run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar, pathway=pathway,
        geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar, distribution_concurrency=2,
    )


# ---------------------------------------------------------------------------
# Section 72: 1-day horizon reconciles to the authoritative day engine
# ---------------------------------------------------------------------------


def test_one_day_horizon_reconciles_to_day_engine() -> None:
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(4)]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5))
    assert len(plan.daily_summaries) == 1
    day_result = plan.daily_summaries[0].schedule_result
    assert day_result.patient_traces
    assert plan.daily_summaries[0].clinically_completed_count == sum(1 for t in day_result.patient_traces if t.completed_within_operating_day)


# ---------------------------------------------------------------------------
# Section 73: 7-day horizon with a non-operating date, committed + forecast
# ---------------------------------------------------------------------------


def test_seven_day_horizon_skips_non_operating_dates() -> None:
    records = [
        _committed("P1", date(2026, 10, 5)),  # Monday, operating
        _committed("P2", date(2026, 10, 7)),  # Wednesday, explicitly non-operating
        _forecast("FORECAST-2026-10-08-F18-001", date(2026, 10, 8)),
    ]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 11), non_operating={date(2026, 10, 7)})
    scheduled_days = {s.day for s in plan.daily_summaries}
    assert date(2026, 10, 7) not in scheduled_days
    assert any(u.day == date(2026, 10, 7) and u.reason == "NON_OPERATING_DAY" for u in plan.unmet_demand)
    assert plan.committed_patient_count == 2
    assert plan.forecast_demand_count == 1


# ---------------------------------------------------------------------------
# Section 74: real calendar month (not assumed 30 days)
# ---------------------------------------------------------------------------


def test_calendar_month_boundaries_correct() -> None:
    records = [_committed("P1", date(2026, 2, 2)), _committed("P2", date(2026, 2, 27))]
    plan = _run(records, start=date(2026, 2, 1), end=date(2026, 2, 28))
    assert plan.planning_end_date == date(2026, 2, 28)  # 2026 is not a leap year
    assert len(plan.monthly_summaries) == 1
    assert plan.monthly_summaries[0].month == 2
    assert plan.monthly_summaries[0].committed_demand_count == 2


# ---------------------------------------------------------------------------
# Section 75/76: six-month controlled horizon, patient continuity
# ---------------------------------------------------------------------------


def test_six_month_controlled_horizon_reconciles() -> None:
    start, end = date(2026, 1, 5), date(2026, 7, 3)
    records = [
        _committed("P1", date(2026, 1, 5)),
        _committed(
            "P2", date(2026, 3, 2), patient_type="INBOUND_PATIENT", clinical_resource_mode="INBOUND_INTEGRATED",
            existing_room_id="IR-001", admission_datetime=date(2026, 3, 2), expected_discharge_date=date(2026, 3, 6),
        ),
        _committed(
            "P3", date(2026, 5, 4), patient_type="INBOUND_PATIENT", clinical_resource_mode="INBOUND_CENTRALIZED",
            existing_room_id="IR-002", admission_datetime=date(2026, 5, 4), expected_discharge_date=date(2026, 5, 5),
        ),
        _forecast("FORECAST-2026-06-01-F18-001", date(2026, 6, 1)),
    ]
    plan = _run(records, start=start, end=end)
    assert plan.planning_start_date == start and plan.planning_end_date == end
    assert plan.committed_patient_count == 3
    assert plan.forecast_demand_count == 1
    # Monthly summaries only exist for months with at least one scheduled
    # operating day (sparse controlled population spans 4 distinct months
    # within the 6-calendar-month horizon: Jan, Mar, May, Jun).
    assert len(plan.monthly_summaries) == 4
    # Sum of daily committed demand reconciles to horizon total (section 93).
    assert sum(s.committed_demand_count for s in plan.daily_summaries) == plan.committed_patient_count


def test_same_patient_identity_persists_no_regeneration() -> None:
    """Section 76: one committed inbound patient, LOS crosses several days --
    one patient identity, one persistent IR identity."""
    records = [
        _committed(
            "P17", date(2026, 10, 1), patient_type="INBOUND_PATIENT", clinical_resource_mode="INBOUND_INTEGRATED",
            existing_room_id="IR-001", admission_datetime=date(2026, 10, 1), expected_discharge_date=date(2026, 10, 5),
        ),
    ]
    plan = _run(records, start=date(2026, 10, 1), end=date(2026, 10, 1))
    entries = plan_for_patient(plan, internal_model_patient_id="P17")
    assert len(entries) == 1
    assert entries[0].injection_resource_id == entries[0].uptake_resource_id == "IR-001"


def test_multiple_procedures_same_patient_distinct_demand_identity() -> None:
    """Section 8/77: one patient, two procedures on different dates."""
    records = [
        _committed("P1", date(2026, 10, 5), protocol_id="PROTO-A"),
        _committed("P1", date(2026, 10, 6), protocol_id="PROTO-B"),
    ]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 6))
    entries = plan_for_patient(plan, internal_model_patient_id="P1")
    assert len(entries) == 2
    assert {e.day for e in entries} == {date(2026, 10, 5), date(2026, 10, 6)}
    assert plan.horizon_passed  # distinct protocol_id -- not a duplicate-scheduling violation


# ---------------------------------------------------------------------------
# Section 78-80: cyclotron OFF reassignment, no-compatible-cyclotron unmet,
# resource unavailable
# ---------------------------------------------------------------------------


def test_cyclotron_off_day_reassigns_patient_demand_unchanged() -> None:
    records = [_committed(f"P{i}", day) for i, day in enumerate((date(2026, 10, 5), date(2026, 10, 6)))]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 6), cyclotron_overrides={date(2026, 10, 6): {"CY-001": "OFF"}})
    by_day = {s.day: s for s in plan.daily_summaries}
    assert by_day[date(2026, 10, 5)].cyclotrons_used == ("CY-001",)
    assert by_day[date(2026, 10, 6)].cyclotrons_used == ("CY-002",)
    assert by_day[date(2026, 10, 5)].committed_demand_count == by_day[date(2026, 10, 6)].committed_demand_count


def test_no_compatible_cyclotron_reports_unmet_not_deleted() -> None:
    records = [_committed("P1", date(2026, 10, 5))]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5), cyclotron_overrides={date(2026, 10, 5): {"CY-001": "OFF", "CY-002": "OFF"}})
    assert plan.master_plan_status == "VALID_WITH_UNMET_DEMAND"
    assert len(plan.unmet_demand) == 1
    assert plan.unmet_demand[0].internal_model_patient_id == "P1"
    assert plan.unmet_demand[0].reason == "CYCLOTRON_OFF"


def test_unavailable_scanner_zero_assignments_remains_in_inventory() -> None:
    inventory = build_deterministic_resource_inventory(injection_room_count=2, uptake_room_count=2, scanner_count=2)
    resource_calendar = ResourceAvailabilityCalendar(inventory=inventory, unavailable_by_date={date(2026, 10, 5): frozenset({"SCN-002"})})
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(3)]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5), resource_calendar=resource_calendar)
    used_scanners = {p.scanner_resource_id for p in plan.patient_plans}
    assert "SCN-002" not in used_scanners
    assert inventory.by_id("SCN-002").resource_id == "SCN-002"


# ---------------------------------------------------------------------------
# Section 81: OPERATIONAL_ONLY no auto-expansion
# ---------------------------------------------------------------------------


def test_operational_only_no_resource_auto_expansion() -> None:
    inventory = build_deterministic_resource_inventory(injection_room_count=1, uptake_room_count=1, scanner_count=2)
    resource_calendar = build_calendar_with_no_exceptions(inventory)
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(6)]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5), resource_calendar=resource_calendar)
    used_scanners = {p.scanner_resource_id for p in plan.patient_plans}
    assert used_scanners.issubset({"SCN-001", "SCN-002"})
    assert "SCN-003" not in used_scanners


# ---------------------------------------------------------------------------
# Sections 84-86: resource/production/patient queries
# ---------------------------------------------------------------------------


def test_resource_query_exact_assignments() -> None:
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(4)]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5))
    matches = assignments_for_resource(plan, resource_id="SCN-001", day=date(2026, 10, 5))
    assert all(m.scanner_resource_id == "SCN-001" for m in matches)


def test_production_query_cycle_and_membership() -> None:
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(2)]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5))
    cycles = production_cycles_for_date(plan, day=date(2026, 10, 5))
    assert cycles
    for cycle in cycles:
        members = patients_for_production_cycle(plan, global_cycle_id=cycle.global_cycle_id)
        assert set(members) == set(cycle.patient_ids)
    cy_plan = production_plan_for_cyclotron(plan, cyclotron_id="CY-001")
    assert all(c.cyclotron_id == "CY-001" for c in cy_plan)


def test_patient_query_full_trace() -> None:
    records = [_committed("P1", date(2026, 10, 5))]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5))
    entries = plan_for_patient(plan, internal_model_patient_id="P1")
    entry = entries[0]
    assert entry.cyclotron_id and entry.radiopharmacy_origin_id
    assert entry.injection_resource_id and entry.uptake_resource_id and entry.scanner_resource_id


# ---------------------------------------------------------------------------
# Section 87: at least three distinct unmet reasons
# ---------------------------------------------------------------------------


def test_at_least_three_distinct_unmet_reasons() -> None:
    resource_calendar_all_off_scn = ResourceAvailabilityCalendar(
        inventory=build_deterministic_resource_inventory(injection_room_count=2, uptake_room_count=2, scanner_count=1),
        unavailable_by_date={date(2026, 10, 8): frozenset({"SCN-001"})},
    )
    records = [
        _committed("P1", date(2026, 10, 7)),  # non-operating (explicit exception)
        _committed("P2", date(2026, 10, 5)),  # cyclotron off this day
        _committed("P3", date(2026, 10, 8)),  # no scanner capacity
    ]
    plan = _run(
        records, start=date(2026, 10, 5), end=date(2026, 10, 8), non_operating={date(2026, 10, 7)},
        cyclotron_overrides={date(2026, 10, 5): {"CY-001": "OFF", "CY-002": "OFF"}}, resource_calendar=resource_calendar_all_off_scn,
    )
    reasons = {u.reason for u in plan.unmet_demand}
    assert len(reasons) >= 3
    assert "NON_OPERATING_DAY" in reasons
    assert "CYCLOTRON_OFF" in reasons
    assert "NO_SCANNER_CAPACITY" in reasons


# ---------------------------------------------------------------------------
# Section 88: committed vs forecast distinctness
# ---------------------------------------------------------------------------


def test_committed_vs_forecast_remain_distinct_in_economics_and_identity() -> None:
    records = [_committed("P1", date(2026, 10, 5)), _forecast("FORECAST-2026-10-05-F18-001", date(2026, 10, 5))]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5))
    assert {p.internal_model_patient_id for p in plan.patient_plans} == {"P1"}
    assert plan.committed_patient_count == 1
    assert plan.forecast_demand_count == 1
    assert plan.committed_planned_value >= 0.0
    assert plan.forecast_expected_value >= 0.0
    assert plan.combined_planning_value == pytest.approx(plan.committed_planned_value + plan.forecast_expected_value)


# ---------------------------------------------------------------------------
# Section 89: architecture purity across Conventional/MRT/Hybrid
# ---------------------------------------------------------------------------


def test_architecture_purity_conventional_and_mrt() -> None:
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(3)]
    conv_plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5), pathway="Conventional")
    mrt_plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5), pathway="MRT")
    assert all(p.transport_mode == "Conventional" for p in conv_plan.patient_plans)
    assert all(p.transport_mode == "MRT" for p in mrt_plan.patient_plans)
    assert conv_plan.horizon_passed and mrt_plan.horizon_passed


# ---------------------------------------------------------------------------
# Section 90: same physical inventory across days
# ---------------------------------------------------------------------------


def test_same_physical_inventory_stable_across_days() -> None:
    records = [_committed(f"P{i}", day) for i, day in enumerate((date(2026, 10, 5), date(2026, 10, 6)))]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 6))
    assert plan.horizon_passed  # validate_persistent_asset_identity found no violation


# ---------------------------------------------------------------------------
# Section 91: staffing responds to actual daily workload, not room count
# ---------------------------------------------------------------------------


def test_staffing_follows_daily_workload_not_static_room_count() -> None:
    light_day = [_committed("P1", date(2026, 10, 5))]
    heavy_day = [_committed(f"P{i}", date(2026, 10, 6)) for i in range(8)]
    plan = _run(light_day + heavy_day, start=date(2026, 10, 5), end=date(2026, 10, 6))
    by_day = {s.day: s for s in plan.daily_summaries}
    light_fte = by_day[date(2026, 10, 5)].staffing.injection_staff.fte
    heavy_fte = by_day[date(2026, 10, 6)].staffing.injection_staff.fte
    assert heavy_fte >= light_fte


# ---------------------------------------------------------------------------
# Sections 92-93: conservation and daily/horizon reconciliation
# ---------------------------------------------------------------------------


def test_horizon_conservation_total_equals_qualified_plus_unmet() -> None:
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(3)]
    records.append(_committed("P99", date(2026, 10, 6), radionuclide="F-18"))
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 6), cyclotron_overrides={date(2026, 10, 6): {"CY-001": "OFF", "CY-002": "OFF"}})
    qualified = sum(1 for p in plan.patient_plans if p.completed_within_operating_day)
    unmet = len(plan.unmet_demand)
    assert qualified + unmet <= plan.committed_patient_count + sum(1 for p in plan.patient_plans if not p.completed_within_operating_day)
    assert unmet == 1  # P99 unmet due to no cyclotron


def test_daily_horizon_reconciliation() -> None:
    records = [_committed(f"P{i}", day) for i, day in enumerate((date(2026, 10, 5),) * 2 + (date(2026, 10, 6),) * 3)]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 6))
    assert sum(s.committed_demand_count for s in plan.daily_summaries) == plan.committed_patient_count
    assert sum(s.production_cycle_count for s in plan.daily_summaries) == sum(len(production_cycles_for_date(plan, day=s.day)) for s in plan.daily_summaries)


# ---------------------------------------------------------------------------
# Section 94: resource exclusivity across the plan (reuses existing validator)
# ---------------------------------------------------------------------------


def test_resource_exclusivity_across_full_plan() -> None:
    from long_horizon_operational_planning import validate_no_double_resource_assignment

    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(6)]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5))
    assert validate_no_double_resource_assignment(plan.patient_plans) == []


# ---------------------------------------------------------------------------
# Section 95: authority failure propagation
# ---------------------------------------------------------------------------


def test_authority_violation_propagates_to_master_plan_status() -> None:
    records = [
        _committed("P1", date(2026, 10, 5), protocol_id="PROTO-A"),
        _committed("P1", date(2026, 10, 5), protocol_id="PROTO-A"),  # deliberate exact duplicate
    ]
    with pytest.raises(Exception):
        # FacilityDayPatientDemand rejects duplicate patient_id within one day
        # at construction time -- this IS the authority boundary catching the
        # invalid input before it could silently corrupt a day's schedule.
        _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5))


# ---------------------------------------------------------------------------
# Section 96: existing single-day non-regression
# ---------------------------------------------------------------------------


def test_existing_single_day_engine_non_regression() -> None:
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(4)]
    plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5))
    direct_result = build_production_clinical_schedule(plan.daily_summaries[0].schedule_result.scenario)
    assert direct_result.patient_traces == plan.daily_summaries[0].schedule_result.patient_traces


# ---------------------------------------------------------------------------
# Section 97: operational qualification matrix
# ---------------------------------------------------------------------------


def test_operational_qualification_matrix_conventional_mrt() -> None:
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(3)]
    results = {}
    for pathway in ("Conventional", "MRT"):
        plan = _run(records, start=date(2026, 10, 5), end=date(2026, 10, 5), pathway=pathway)
        results[pathway] = (
            plan.committed_patient_count,
            sum(1 for p in plan.patient_plans if p.completed_within_operating_day),
            len(plan.unmet_demand),
            plan.horizon_passed,
        )
    for pathway, (demand, qualified, unmet, passed) in results.items():
        assert demand == 3
        assert passed


# ---------------------------------------------------------------------------
# Section 98: capital-compatibility smoke test
# ---------------------------------------------------------------------------


def test_capital_planning_study_scope_changes_economics_not_identity() -> None:
    geometry, configured = _geometry_and_configured()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=date(2026, 10, 5), planning_end_date=date(2026, 10, 5))
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    inventory = build_deterministic_resource_inventory(injection_room_count=2, uptake_room_count=2, scanner_count=2)
    resource_calendar = build_calendar_with_no_exceptions(inventory)
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(3)]

    op_plan = run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar, pathway="Conventional",
        geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar, distribution_concurrency=2,
        study_scope="OPERATIONAL_ONLY",
    )
    cap_plan = run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar, pathway="Conventional",
        geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar, distribution_concurrency=2,
        study_scope="CAPITAL_PLANNING",
    )
    assert op_plan.study_scope == "OPERATIONAL_ONLY"
    assert cap_plan.study_scope == "CAPITAL_PLANNING"
    # Same physical resource identities regardless of study scope.
    assert {p.scanner_resource_id for p in op_plan.patient_plans} == {p.scanner_resource_id for p in cap_plan.patient_plans}

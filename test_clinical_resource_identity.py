"""Controlled tests: Persistent Clinical Resource Identity + Assignment Authority.

Covers sections 55-68: identical throughput before/after identity assignment,
count<->ID conservation, resource exclusivity (scanner/injection/uptake),
persistence across days, temporary unavailability, OPERATIONAL_ONLY no
auto-expansion, CAPITAL_PLANNING proposed-resource identity, hybrid shared
inventory, long-horizon resource/patient queries.
"""

from __future__ import annotations

from datetime import date

import pytest

from clinical_resource_identity import (
    add_proposed_resources,
    build_calendar_with_no_exceptions,
    build_deterministic_resource_inventory,
    resource_id_for_index,
    ResourceAvailabilityCalendar,
)
from long_horizon_operational_planning import (
    CanonicalOperationalPatientRecord,
    CyclotronCalendar,
    OperatingCalendar,
    assignments_for_resource,
    plan_for_patient,
    resource_schedule_for_date,
    run_long_horizon_operational_plan,
    validate_no_double_resource_assignment,
)
from models import PlannerAssumptions
from multi_cyclotron_authority import build_controlled_dual_origin_geometry, build_multi_cyclotron_scenario
from operating_day_scheduler import OperatingDayInputs, schedule_operating_day
from production_clinical_schedule import ProductionBatchReleaseMapping  # noqa: F401 (documents patient trace context)


def _geometry_and_configured():
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="ON")
    geometry = build_controlled_dual_origin_geometry()
    return geometry, configured


def _committed(patient_id: str, day: date, radionuclide: str = "F-18", patient_type: str = "OUTPATIENT", **kwargs) -> CanonicalOperationalPatientRecord:
    return CanonicalOperationalPatientRecord(
        internal_model_patient_id=patient_id, demand_status="COMMITTED", patient_type=patient_type,
        radionuclide=radionuclide, prescribed_activity_mbq=200.0, scheduled_date=day,
        source_provenance="USER_ENTERED", **kwargs,
    )


# ---------------------------------------------------------------------------
# Low-level clinical_resource_identity.py tests (sections 5-8, 56, 68)
# ---------------------------------------------------------------------------


def test_deterministic_ids_stable_and_not_random() -> None:
    assert resource_id_for_index("SCANNER", 0) == "SCN-001"
    assert resource_id_for_index("SCANNER", 5) == "SCN-006"
    assert resource_id_for_index("INJECTION_ROOM", 0) == "INJ-001"
    assert resource_id_for_index("UPTAKE_ROOM", 11) == "UP-012"
    # Same index -> same id every time (no randomness).
    assert resource_id_for_index("SCANNER", 2) == resource_id_for_index("SCANNER", 2)


def test_six_scanners_produce_exactly_six_ids() -> None:
    """Section 56: 6 scanners = 6 IDs, no hidden extras."""
    inventory = build_deterministic_resource_inventory(injection_room_count=18, uptake_room_count=12, scanner_count=6)
    assert len(inventory.scanners) == 6
    assert {r.resource_id for r in inventory.scanners} == {f"SCN-{i:03d}" for i in range(1, 7)}
    assert len(inventory.injection_rooms) == 18
    assert len(inventory.uptake_rooms) == 12


def test_count_id_conservation_no_hidden_extras() -> None:
    inventory = build_deterministic_resource_inventory(injection_room_count=3, uptake_room_count=4, scanner_count=2)
    assert len(inventory.injection_rooms) == 3
    assert len(inventory.uptake_rooms) == 4
    assert len(inventory.scanners) == 2


def test_capital_planning_proposed_resources_get_identity() -> None:
    """Section 45: proposed additional resources receive identities too,
    preserving existing/proposed asset state distinctly."""
    inventory = build_deterministic_resource_inventory(injection_room_count=1, uptake_room_count=1, scanner_count=6)
    expanded = add_proposed_resources(inventory, resource_type="SCANNER", additional_count=1)
    assert len(expanded.scanners) == 7
    assert expanded.scanners[-1].resource_id == "SCN-007"
    assert expanded.scanners[-1].asset_state == "PROPOSED"
    assert all(r.asset_state == "EXISTING" for r in expanded.scanners[:6])


def test_resource_not_deleted_when_temporarily_unavailable() -> None:
    """Section 20-22: an unavailable resource remains in inventory; it just
    receives zero assignments and drops out of the active count for that
    date."""
    inventory = build_deterministic_resource_inventory(injection_room_count=1, uptake_room_count=1, scanner_count=3)
    day = date(2026, 10, 6)
    calendar = ResourceAvailabilityCalendar(inventory=inventory, unavailable_by_date={day: frozenset({"SCN-002"})})
    assert calendar.state_on(resource_id="SCN-002", day=day) == "UNAVAILABLE"
    active = calendar.active_resource_ids_for_date(resource_type="SCANNER", day=day)
    assert "SCN-002" not in active
    assert len(active) == 2
    # SCN-002's identity is preserved in the inventory even while unavailable.
    assert inventory.by_id("SCN-002").resource_id == "SCN-002"
    # Another date with no exception has all 3 available.
    other_day = date(2026, 10, 7)
    assert len(calendar.active_resource_ids_for_date(resource_type="SCANNER", day=other_day)) == 3


# ---------------------------------------------------------------------------
# End-to-end via long_horizon_operational_planning (sections 55, 57-68)
# ---------------------------------------------------------------------------


def _run(*, records, resource_calendar, pathway="Conventional", start=date(2026, 10, 5), end=date(2026, 10, 5),
          cyclotron_overrides=None):
    geometry, configured = _geometry_and_configured()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=start, planning_end_date=end)
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured, scenario_state_overrides_by_date=cyclotron_overrides or {})
    return run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar,
        pathway=pathway, geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar,
        distribution_concurrency=2,
    )


def test_identical_throughput_before_and_after_identity_assignment() -> None:
    """Section 55/7: adding identity must not change completions/production --
    compare the long-horizon result (identity-aware) against a direct
    schedule_operating_day() call with the SAME raw counts."""
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(6)]
    inventory = build_deterministic_resource_inventory(injection_room_count=2, uptake_room_count=2, scanner_count=2)
    calendar = build_calendar_with_no_exceptions(inventory)
    plan = _run(records=records, resource_calendar=calendar)
    identity_completed = plan.daily_summaries[0].clinically_completed_count

    # Direct raw-count comparison using the exact same scenario shape.
    scenario = plan.daily_summaries[0].schedule_result.scenario
    raw_result = schedule_operating_day(OperatingDayInputs(
        operating_day_minutes=scenario.operating_day_minutes,
        batch_releases=list(plan.daily_summaries[0].schedule_result.batch_releases),
        transport_minutes=scenario.transport_minutes,
        injection_service_minutes=scenario.injection_service_minutes,
        uptake_minutes=scenario.uptake_minutes,
        scanner_service_minutes=scenario.scanner_service_minutes,
        injection_resources=scenario.injection_resources,
        uptake_resources=scenario.uptake_resources,
        scanners=scenario.scanners,
        distribution_concurrency=scenario.distribution_concurrency,
    ))
    assert raw_result.completed_patients == identity_completed


def test_scanner_exclusivity_never_double_booked() -> None:
    """Section 57/12: one scanner ID is never assigned overlapping patients."""
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(8)]
    inventory = build_deterministic_resource_inventory(injection_room_count=4, uptake_room_count=4, scanner_count=2)
    calendar = build_calendar_with_no_exceptions(inventory)
    plan = _run(records=records, resource_calendar=calendar)
    assert validate_no_double_resource_assignment(plan.patient_plans) == []
    assert {p.scanner_resource_id for p in plan.patient_plans}.issubset({"SCN-001", "SCN-002"})


def test_injection_and_uptake_exclusivity() -> None:
    """Section 58/59/10/11."""
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(10)]
    inventory = build_deterministic_resource_inventory(injection_room_count=3, uptake_room_count=3, scanner_count=3)
    calendar = build_calendar_with_no_exceptions(inventory)
    plan = _run(records=records, resource_calendar=calendar)
    assert validate_no_double_resource_assignment(plan.patient_plans) == []
    assert {p.injection_resource_id for p in plan.patient_plans}.issubset({"INJ-001", "INJ-002", "INJ-003"})
    assert {p.uptake_resource_id for p in plan.patient_plans}.issubset({"UP-001", "UP-002", "UP-003"})


def test_resource_persistence_across_days() -> None:
    """Section 60/17: SCN-002 on day 1 and SCN-002 on a later day are the
    SAME persistent physical resource (one inventory object reused)."""
    records = [_committed(f"P{i}", day) for i, day in enumerate((date(2026, 10, 5), date(2026, 10, 6)))]
    inventory = build_deterministic_resource_inventory(injection_room_count=1, uptake_room_count=1, scanner_count=1)
    calendar = build_calendar_with_no_exceptions(inventory)
    plan = _run(records=records, resource_calendar=calendar, start=date(2026, 10, 5), end=date(2026, 10, 6))
    assert {p.scanner_resource_id for p in plan.patient_plans} == {"SCN-001"}
    day1_scanner = next(p.scanner_resource_id for p in plan.patient_plans if p.day == date(2026, 10, 5))
    day2_scanner = next(p.scanner_resource_id for p in plan.patient_plans if p.day == date(2026, 10, 6))
    assert day1_scanner == day2_scanner == "SCN-001"


def test_temporary_unavailability_zero_assignments_that_day() -> None:
    """Section 61: SCN-002 unavailable on Oct 6 -- remains in inventory but
    receives zero assignments that day."""
    records = [_committed(f"P{i}", day) for i, day in enumerate((date(2026, 10, 5), date(2026, 10, 6)))]
    inventory = build_deterministic_resource_inventory(injection_room_count=1, uptake_room_count=1, scanner_count=2)
    calendar = ResourceAvailabilityCalendar(inventory=inventory, unavailable_by_date={date(2026, 10, 6): frozenset({"SCN-002"})})
    plan = _run(records=records, resource_calendar=calendar, start=date(2026, 10, 5), end=date(2026, 10, 6))
    day6_scanners = {p.scanner_resource_id for p in plan.patient_plans if p.day == date(2026, 10, 6)}
    assert "SCN-002" not in day6_scanners
    assert inventory.by_id("SCN-002").resource_id == "SCN-002"  # identity preserved


def test_operational_only_no_scanner_auto_expansion() -> None:
    """Section 62/44: 2 installed scanners -- no SCN-003 fabricated even
    though more demand exists."""
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(6)]
    inventory = build_deterministic_resource_inventory(injection_room_count=2, uptake_room_count=2, scanner_count=2)
    calendar = build_calendar_with_no_exceptions(inventory)
    plan = _run(records=records, resource_calendar=calendar)
    assert {p.scanner_resource_id for p in plan.patient_plans}.issubset({"SCN-001", "SCN-002"})
    assert "SCN-003" not in {p.scanner_resource_id for p in plan.patient_plans}


def test_hybrid_shared_resource_inventory_across_transport_modes() -> None:
    """Section 49/63: Conventional-run and MRT-run patients draw from the
    SAME clinical resource inventory -- no CONV-INJ-xxx/MRT-INJ-xxx
    duplication."""
    inventory = build_deterministic_resource_inventory(injection_room_count=2, uptake_room_count=2, scanner_count=2)
    calendar = build_calendar_with_no_exceptions(inventory)
    conv_records = [_committed(f"C{i}", date(2026, 10, 5)) for i in range(3)]
    mrt_records = [_committed(f"M{i}", date(2026, 10, 5)) for i in range(3)]

    conv_plan = _run(records=conv_records, resource_calendar=calendar, pathway="Conventional")
    mrt_plan = _run(records=mrt_records, resource_calendar=calendar, pathway="MRT")

    conv_ids = {p.injection_resource_id for p in conv_plan.patient_plans} | {p.scanner_resource_id for p in conv_plan.patient_plans}
    mrt_ids = {p.injection_resource_id for p in mrt_plan.patient_plans} | {p.scanner_resource_id for p in mrt_plan.patient_plans}
    all_valid_ids = {r.resource_id for r in inventory.injection_rooms + inventory.scanners}
    assert conv_ids.issubset(all_valid_ids)
    assert mrt_ids.issubset(all_valid_ids)
    # No mode-specific duplicate resource naming exists anywhere.
    assert not any(rid.startswith("CONV-") or rid.startswith("MRT-") for rid in conv_ids | mrt_ids)


def test_long_horizon_resource_query_returns_exact_assignments() -> None:
    """Section 66/37: query one resource on one date and get exact
    patient/time assignments."""
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(4)]
    inventory = build_deterministic_resource_inventory(injection_room_count=2, uptake_room_count=2, scanner_count=2)
    calendar = build_calendar_with_no_exceptions(inventory)
    plan = _run(records=records, resource_calendar=calendar)
    matches = assignments_for_resource(plan, resource_id="SCN-001", day=date(2026, 10, 5))
    assert all(p.scanner_resource_id == "SCN-001" for p in matches)
    assert all(p.day == date(2026, 10, 5) for p in matches)
    # Every match corresponds to a real committed patient in this run.
    assert {p.internal_model_patient_id for p in matches}.issubset({r.internal_model_patient_id for r in records})


def test_patient_query_exposes_full_resource_trace() -> None:
    """Section 67/38: patient query exposes cyclotron/cycle/transport
    mode/injection/uptake/scanner resource identity."""
    records = [_committed("P1", date(2026, 10, 5))]
    inventory = build_deterministic_resource_inventory(injection_room_count=1, uptake_room_count=1, scanner_count=1)
    calendar = build_calendar_with_no_exceptions(inventory)
    plan = _run(records=records, resource_calendar=calendar)
    entries = plan_for_patient(plan, internal_model_patient_id="P1")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.cyclotron_id == "CY-001"
    assert entry.transport_mode == "Conventional"
    assert entry.injection_resource_id == "INJ-001"
    assert entry.uptake_resource_id == "UP-001"
    assert entry.scanner_resource_id == "SCN-001"


def test_date_centric_resource_schedule_query() -> None:
    """Section 39: date-centric query returns every assignment for that
    date."""
    records = [_committed(f"P{i}", date(2026, 10, 5)) for i in range(3)]
    inventory = build_deterministic_resource_inventory(injection_room_count=2, uptake_room_count=2, scanner_count=2)
    calendar = build_calendar_with_no_exceptions(inventory)
    plan = _run(records=records, resource_calendar=calendar)
    entries = resource_schedule_for_date(plan, day=date(2026, 10, 5))
    assert len(entries) == 3
    assert all(p.day == date(2026, 10, 5) for p in entries)

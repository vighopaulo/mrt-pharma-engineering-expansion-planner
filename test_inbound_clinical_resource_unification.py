"""Controlled tests: Inbound Clinical Resource Unification.

Covers sections 59-77: OUTPATIENT/CENTRALIZED/INTEGRATED resource consumption
made authoritative in the SAME day engine, shared-queue exclusion for
dedicated-room functions, scanner remaining a common bottleneck, resource
persistence/occupancy across the long horizon, authority violation detection,
and non-regression of the existing all-outpatient benchmark.
"""

from __future__ import annotations

from datetime import date

import pytest

from clinical_resource_identity import build_calendar_with_no_exceptions, build_deterministic_resource_inventory
from cyclotron_production_windows import CyclotronProductionCapability
from engineering_authority import validate_clinical_resource_mode_consistency
from long_horizon_operational_planning import (
    CanonicalOperationalPatientRecord,
    CyclotronCalendar,
    OperatingCalendar,
    run_long_horizon_operational_plan,
    validate_inbound_room_no_overlap,
    validate_no_double_resource_assignment,
)
from models import PlannerAssumptions
from multi_cyclotron_authority import build_controlled_dual_origin_geometry, build_multi_cyclotron_scenario
from operating_day_scheduler import BatchRelease, DEDICATED_ROOM_RESOURCE_INDEX, OperatingDayInputs, schedule_operating_day
from patient_radionuclide_demand import FacilityDayPatientDemand, PatientRadionuclideDemand
from production_clinical_schedule import ProductionClinicalScenario, build_production_clinical_schedule


# ---------------------------------------------------------------------------
# Low-level operating_day_scheduler.py tests (sections 59-61, 66)
# ---------------------------------------------------------------------------


def _inputs(patient_clinical_modes, patient_inbound_room_ids, *, injection_resources=1, uptake_resources=1, scanners=1, distribution_concurrency=4):
    n = len(patient_clinical_modes)
    return OperatingDayInputs(
        operating_day_minutes=1080.0,
        batch_releases=[
            BatchRelease(
                batch_id=1, release_time_minutes=0.0, patients_in_batch=n, release_unit_id="PL-1",
                patient_clinical_modes=tuple(patient_clinical_modes),
                patient_inbound_room_ids=tuple(patient_inbound_room_ids),
            ),
        ],
        transport_minutes=5.0, injection_service_minutes=10.0, uptake_minutes=45.0, scanner_service_minutes=20.0,
        injection_resources=injection_resources, uptake_resources=uptake_resources, scanners=scanners,
        distribution_concurrency=distribution_concurrency,
    )


def test_outpatient_uses_shared_injection_uptake_scanner() -> None:
    """Section 59."""
    result = schedule_operating_day(_inputs(["OUTPATIENT_SHARED"], [None]))
    ps = result.patient_schedules[0]
    assert ps.injection_resource_index != DEDICATED_ROOM_RESOURCE_INDEX
    assert ps.uptake_resource_index != DEDICATED_ROOM_RESOURCE_INDEX
    assert ps.inbound_room_id is None


def test_centralized_inbound_uses_shared_injection_dedicated_uptake() -> None:
    """Section 60."""
    result = schedule_operating_day(_inputs(["INBOUND_CENTRALIZED"], ["IR-001"]))
    ps = result.patient_schedules[0]
    assert ps.injection_resource_index != DEDICATED_ROOM_RESOURCE_INDEX  # shared INJ
    assert ps.uptake_resource_index == DEDICATED_ROOM_RESOURCE_INDEX  # dedicated IR
    assert ps.inbound_room_id == "IR-001"


def test_integrated_inbound_uses_dedicated_injection_and_uptake() -> None:
    """Section 61/66: same dedicated room for both injection and uptake."""
    result = schedule_operating_day(_inputs(["INBOUND_INTEGRATED"], ["IR-002"]))
    ps = result.patient_schedules[0]
    assert ps.injection_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
    assert ps.uptake_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
    assert ps.inbound_room_id == "IR-002"


def test_integrated_does_not_queue_for_congested_shared_injection() -> None:
    """Section 62: heavily congested shared injection pool (1 resource, 3
    outpatients ahead) -- the INTEGRATED patient must not wait for it."""
    modes = ["OUTPATIENT_SHARED"] * 3 + ["INBOUND_INTEGRATED"]
    rooms = [None] * 3 + ["IR-005"]
    result = schedule_operating_day(_inputs(modes, rooms, injection_resources=1, uptake_resources=1))
    integrated = result.patient_schedules[3]
    # Injection starts immediately after distribution (5.0), NOT after waiting
    # for the 3 congested outpatients (who occupy INJ-001 serially: 5-15,15-25,25-35).
    assert integrated.injection_start == 5.0


def test_centralized_competes_legitimately_for_shared_injection() -> None:
    """Section 63: CENTRALIZED must wait behind congested shared injection,
    unlike INTEGRATED."""
    modes = ["OUTPATIENT_SHARED"] * 3 + ["INBOUND_CENTRALIZED"]
    rooms = [None] * 3 + ["IR-006"]
    result = schedule_operating_day(_inputs(modes, rooms, injection_resources=1, uptake_resources=1))
    centralized = result.patient_schedules[3]
    assert centralized.injection_start > 5.0  # queued behind the 3 outpatients
    assert centralized.injection_resource_index != DEDICATED_ROOM_RESOURCE_INDEX


def test_dedicated_uptake_bypasses_congested_shared_uptake_outpatient_still_waits() -> None:
    """Section 64."""
    modes = ["OUTPATIENT_SHARED"] * 3 + ["INBOUND_CENTRALIZED", "INBOUND_INTEGRATED"]
    rooms = [None] * 3 + ["IR-007", "IR-008"]
    result = schedule_operating_day(_inputs(modes, rooms, injection_resources=4, uptake_resources=1))
    centralized, integrated = result.patient_schedules[3], result.patient_schedules[4]
    assert centralized.uptake_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
    assert integrated.uptake_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
    # Neither dedicated-room patient waited behind the 3 outpatients' 45-min shared uptake queue.
    assert centralized.uptake_start == centralized.injection_end
    assert integrated.uptake_start == integrated.injection_end
    outpatients = result.patient_schedules[:3]
    assert outpatients[1].uptake_start >= outpatients[0].uptake_end  # outpatient queue is real


def test_scanner_remains_common_bottleneck_across_all_modes() -> None:
    """Section 65/23: one shared scanner inventory serves every clinical
    mode -- no clinical mode receives fabricated scanner capacity."""
    modes = ["OUTPATIENT_SHARED", "INBOUND_CENTRALIZED", "INBOUND_INTEGRATED"]
    rooms = [None, "IR-009", "IR-010"]
    result = schedule_operating_day(_inputs(modes, rooms, injection_resources=3, uptake_resources=3, scanners=1))
    scan_intervals = sorted((ps.scan_start, ps.scan_end) for ps in result.patient_schedules)
    for (s1, e1), (s2, e2) in zip(scan_intervals, scan_intervals[1:]):
        assert s2 >= e1  # never overlapping -- one shared scanner


def test_dedicated_room_functions_never_contribute_to_shared_utilization() -> None:
    """Section 21-22: shared injection/uptake utilization excludes dedicated-
    room functions entirely."""
    modes = ["INBOUND_INTEGRATED"]
    rooms = ["IR-011"]
    result = schedule_operating_day(_inputs(modes, rooms, injection_resources=2, uptake_resources=2))
    assert result.injection_utilization_pct == 0.0
    assert result.uptake_utilization_pct == 0.0


def test_backward_compatible_empty_clinical_mode_arrays() -> None:
    """Section 33: omitting the new arrays reproduces default all-outpatient
    behavior exactly."""
    inputs = OperatingDayInputs(
        operating_day_minutes=1080.0,
        batch_releases=[BatchRelease(batch_id=1, release_time_minutes=0.0, patients_in_batch=2, release_unit_id="PL-1")],
        transport_minutes=5.0, injection_service_minutes=10.0, uptake_minutes=45.0, scanner_service_minutes=20.0,
        injection_resources=1, uptake_resources=1, scanners=1, distribution_concurrency=1,
    )
    result = schedule_operating_day(inputs)
    assert all(ps.clinical_resource_mode == "OUTPATIENT_SHARED" for ps in result.patient_schedules)
    assert all(ps.inbound_room_id is None for ps in result.patient_schedules)


# ---------------------------------------------------------------------------
# End-to-end production_clinical_schedule.py (sections 24-27, 70-71, 75, 77)
# ---------------------------------------------------------------------------


def _mixed_scenario(patients, *, injection_resources=2, uptake_resources=2, scanners=2):
    return ProductionClinicalScenario(
        facility_day_demand=FacilityDayPatientDemand(patients=tuple(patients)),
        requested_batch_count_by_radionuclide={"F-18": 1},
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="CY-001", supported_radionuclides=("F-18",), max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
        ),
        transport_minutes=5.0, injection_service_minutes=10.0, uptake_minutes=45.0, scanner_service_minutes=20.0,
        injection_resources=injection_resources, uptake_resources=uptake_resources, scanners=scanners,
        distribution_concurrency=2, operating_day_minutes=1080.0, production_horizon_minutes=1080.0,
    )


def test_production_demand_unchanged_across_clinical_modes() -> None:
    """Section 70/56: switching CENTRALIZED<->INTEGRATED does not remove the
    patient's prescribed radionuclide need -- production/activity requirement
    is identical."""
    centralized = PatientRadionuclideDemand(patient_id="P1", radionuclide="F-18", prescribed_activity_mbq=200.0,
                                              clinical_resource_mode="INBOUND_CENTRALIZED", inbound_room_id="IR-001")
    integrated = PatientRadionuclideDemand(patient_id="P1", radionuclide="F-18", prescribed_activity_mbq=200.0,
                                             clinical_resource_mode="INBOUND_INTEGRATED", inbound_room_id="IR-001")
    result_c = build_production_clinical_schedule(_mixed_scenario([centralized]))
    result_i = build_production_clinical_schedule(_mixed_scenario([integrated]))
    assert result_c.batch_demands[0].total_prescribed_activity_mbq == result_i.batch_demands[0].total_prescribed_activity_mbq == 200.0


def test_end_to_end_traceability_for_all_three_modes() -> None:
    """Section 75."""
    patients = [
        PatientRadionuclideDemand(patient_id="P1", radionuclide="F-18", prescribed_activity_mbq=200.0),
        PatientRadionuclideDemand(patient_id="P2", radionuclide="F-18", prescribed_activity_mbq=200.0,
                                   clinical_resource_mode="INBOUND_CENTRALIZED", inbound_room_id="IR-001"),
        PatientRadionuclideDemand(patient_id="P3", radionuclide="F-18", prescribed_activity_mbq=200.0,
                                   clinical_resource_mode="INBOUND_INTEGRATED", inbound_room_id="IR-002"),
    ]
    result = build_production_clinical_schedule(_mixed_scenario(patients))
    traces_by_id = {t.patient_id: t for t in result.patient_traces}
    assert traces_by_id["P1"].clinical_resource_mode == "OUTPATIENT_SHARED"
    assert traces_by_id["P2"].clinical_resource_mode == "INBOUND_CENTRALIZED"
    assert traces_by_id["P3"].clinical_resource_mode == "INBOUND_INTEGRATED"
    for trace in result.patient_traces:
        assert trace.assigned_cyclotron_id == "CY-001"
        assert trace.batch_id >= 1


def test_hybrid_no_duplicated_inbound_room_namespace() -> None:
    """Section 52/74: one physical IR-xxx serves patients regardless of
    which transport architecture supplied their radionuclide."""
    from dataclasses import replace

    conv_patient = PatientRadionuclideDemand(patient_id="P1", radionuclide="F-18", prescribed_activity_mbq=200.0,
                                               clinical_resource_mode="INBOUND_INTEGRATED", inbound_room_id="IR-100")
    mrt_patient = PatientRadionuclideDemand(patient_id="P2", radionuclide="F-18", prescribed_activity_mbq=200.0,
                                              clinical_resource_mode="INBOUND_INTEGRATED", inbound_room_id="IR-100")
    conv_result = build_production_clinical_schedule(_mixed_scenario([conv_patient]))
    mrt_result = build_production_clinical_schedule(replace(_mixed_scenario([mrt_patient]), pathway="MRT"))
    conv_room = conv_result.patient_traces[0].inbound_room_id
    mrt_room = mrt_result.patient_traces[0].inbound_room_id
    assert conv_room == mrt_room == "IR-100"
    assert not conv_room.startswith("CONV-") and not mrt_room.startswith("MRT-")


# ---------------------------------------------------------------------------
# Authority validation (section 76)
# ---------------------------------------------------------------------------


def test_authority_detects_integrated_assigned_shared_injection() -> None:
    findings = validate_clinical_resource_mode_consistency(
        patient_ids=["P1"], clinical_resource_modes=["INBOUND_INTEGRATED"],
        injection_resource_ids=["INJ-001"], uptake_resource_ids=["IR-001"], inbound_room_ids=["IR-001"],
    )
    assert len(findings) == 1
    assert findings[0].authority_id == "INTEGRATED_SHARED_QUEUE_EXCLUSION"


def test_authority_detects_centralized_assigned_shared_uptake() -> None:
    findings = validate_clinical_resource_mode_consistency(
        patient_ids=["P1"], clinical_resource_modes=["INBOUND_CENTRALIZED"],
        injection_resource_ids=["INJ-001"], uptake_resource_ids=["UP-002"], inbound_room_ids=["IR-001"],
    )
    assert len(findings) == 1
    assert findings[0].authority_id == "CENTRALIZED_SHARED_UPTAKE_EXCLUSION"


def test_authority_passes_correct_assignments() -> None:
    findings = validate_clinical_resource_mode_consistency(
        patient_ids=["P1", "P2", "P3"],
        clinical_resource_modes=["OUTPATIENT_SHARED", "INBOUND_CENTRALIZED", "INBOUND_INTEGRATED"],
        injection_resource_ids=["INJ-001", "INJ-002", "IR-003"],
        uptake_resource_ids=["UP-001", "IR-002", "IR-003"],
        inbound_room_ids=[None, "IR-002", "IR-003"],
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Long-horizon persistence + occupancy (sections 37-38, 67, 72-73)
# ---------------------------------------------------------------------------


def _geometry_and_configured():
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="ON")
    geometry = build_controlled_dual_origin_geometry()
    return geometry, configured


def test_ir_identity_persists_across_days_in_patient_plan() -> None:
    """Section 37/67."""
    geometry, configured = _geometry_and_configured()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=date(2026, 10, 5), planning_end_date=date(2026, 10, 6))
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    inventory = build_deterministic_resource_inventory(injection_room_count=1, uptake_room_count=1, scanner_count=1, inbound_room_count=1)
    resource_calendar = build_calendar_with_no_exceptions(inventory)
    records = [
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P17", demand_status="COMMITTED", patient_type="INBOUND_PATIENT",
            radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5),
            source_provenance="USER_ENTERED", clinical_resource_mode="INBOUND_INTEGRATED",
            existing_room_id="IR-001", admission_datetime=date(2026, 10, 5), expected_discharge_date=date(2026, 10, 6),
        ),
    ]
    plan = run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar,
        pathway="Conventional", geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar,
        distribution_concurrency=2,
    )
    entry = plan.patient_plans[0]
    assert entry.clinical_resource_mode == "INBOUND_INTEGRATED"
    assert entry.injection_resource_id == entry.uptake_resource_id == "IR-001"


def test_inbound_room_occupancy_rejects_overlap_then_frees_after_discharge() -> None:
    """Section 67: overlap rejected; room available after discharge."""
    overlapping = [
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P17", demand_status="COMMITTED", patient_type="INBOUND_PATIENT",
            radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 1),
            source_provenance="USER_ENTERED", clinical_resource_mode="INBOUND_INTEGRATED",
            existing_room_id="IR-003", admission_datetime=date(2026, 10, 1), expected_discharge_date=date(2026, 10, 5),
        ),
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P18", demand_status="COMMITTED", patient_type="INBOUND_PATIENT",
            radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 3),
            source_provenance="USER_ENTERED", clinical_resource_mode="INBOUND_INTEGRATED",
            existing_room_id="IR-003", admission_datetime=date(2026, 10, 3), expected_discharge_date=date(2026, 10, 8),
        ),
    ]
    findings = validate_inbound_room_no_overlap(overlapping)
    assert len(findings) == 1

    non_overlapping = [
        overlapping[0],
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P19", demand_status="COMMITTED", patient_type="INBOUND_PATIENT",
            radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5),
            source_provenance="USER_ENTERED", clinical_resource_mode="INBOUND_INTEGRATED",
            existing_room_id="IR-003", admission_datetime=date(2026, 10, 5), expected_discharge_date=date(2026, 10, 8),
        ),
    ]
    assert validate_inbound_room_no_overlap(non_overlapping) == []


def test_outpatient_cannot_use_inbound_room() -> None:
    """Section 68/43: OUTPATIENT record with an existing_room_id and
    default clinical_resource_mode is rejected."""
    with pytest.raises(ValueError):
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P1", demand_status="COMMITTED", patient_type="OUTPATIENT",
            radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5),
            source_provenance="USER_ENTERED", existing_room_id="IR-001",
        )


def test_no_double_resource_assignment_covers_dedicated_rooms() -> None:
    """Section 20/41: inbound-room exclusivity is also checked by the
    generic no-double-resource-assignment validator (same field carries the
    resolved IR-xxx id)."""
    geometry, configured = _geometry_and_configured()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=date(2026, 10, 5), planning_end_date=date(2026, 10, 5))
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    inventory = build_deterministic_resource_inventory(injection_room_count=2, uptake_room_count=2, scanner_count=2, inbound_room_count=1)
    resource_calendar = build_calendar_with_no_exceptions(inventory)
    records = [
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P1", demand_status="COMMITTED", patient_type="INBOUND_PATIENT",
            radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5),
            source_provenance="USER_ENTERED", clinical_resource_mode="INBOUND_INTEGRATED",
            existing_room_id="IR-001", admission_datetime=date(2026, 10, 5), expected_discharge_date=date(2026, 10, 5),
        ),
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P2", demand_status="COMMITTED", patient_type="OUTPATIENT",
            radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5),
            source_provenance="USER_ENTERED",
        ),
    ]
    plan = run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar,
        pathway="Conventional", geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar,
        distribution_concurrency=2,
    )
    assert validate_no_double_resource_assignment(plan.patient_plans) == []


# ---------------------------------------------------------------------------
# Non-regression (section 77)
# ---------------------------------------------------------------------------


def test_existing_all_outpatient_benchmark_non_regression() -> None:
    patients = [PatientRadionuclideDemand(patient_id=f"P{i}", radionuclide="F-18", prescribed_activity_mbq=200.0) for i in range(6)]
    result = build_production_clinical_schedule(_mixed_scenario(patients))
    assert all(t.clinical_resource_mode == "OUTPATIENT_SHARED" for t in result.patient_traces)
    assert all(t.inbound_room_id is None for t in result.patient_traces)
    completed = sum(1 for t in result.patient_traces if t.completed_within_operating_day)
    assert completed == len(result.patient_traces)

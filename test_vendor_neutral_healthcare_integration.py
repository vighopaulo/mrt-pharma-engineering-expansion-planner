"""Controlled tests: Vendor-Neutral Healthcare Integration Foundation.

Covers ARIA/GE DoseWatch/Siemens Healthineers adapters, cross-source identity
reconciliation, idempotency, source conflicts, planner round-trip, synthetic
non-regression, optimizer vendor-independence, and equipment
specification/energy-model readiness (no energy calculated).
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from clinical_resource_identity import build_calendar_with_no_exceptions, build_deterministic_resource_inventory
from healthcare_adapters import (
    build_aria_fixture,
    build_ge_dosewatch_fixture,
    build_siemens_fixture,
    ingest_aria_fixture,
    ingest_ge_dosewatch_fixture,
    ingest_siemens_fixture,
)
from healthcare_integration import (
    RADIONUCLIDE_NOT_SUPPLIED,
    SECURITY_COMPLIANCE_NOT_IN_SCOPE,
    CanonicalIntegrationEvent,
    CrossSourceIdentityRegistry,
    EquipmentIdentityRecord,
    SourceConflict,
    classify_existing_opex_line_electricity_inclusion,
    run_integration_validation,
)
from long_horizon_operational_planning import CyclotronCalendar, OperatingCalendar, plan_for_patient, run_long_horizon_operational_plan
from models import PlannerAssumptions
from multi_cyclotron_authority import build_controlled_dual_origin_geometry, build_multi_cyclotron_scenario
from patient_radionuclide_demand import PatientRadionuclideDemand


def _geometry_and_configured():
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="ON")
    geometry = build_controlled_dual_origin_geometry()
    return geometry, configured


def _run_planner(records):
    geometry, configured = _geometry_and_configured()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=date(2026, 10, 5), planning_end_date=date(2026, 10, 5))
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    inventory = build_deterministic_resource_inventory(injection_room_count=2, uptake_room_count=2, scanner_count=2, inbound_room_count=2)
    resource_calendar = build_calendar_with_no_exceptions(inventory)
    return run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar, pathway="Conventional",
        geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar, distribution_concurrency=2,
    )


# ---------------------------------------------------------------------------
# Section 57: ARIA round-trip
# ---------------------------------------------------------------------------


def test_aria_fixture_normalizes_and_round_trips_through_planner() -> None:
    registry = CrossSourceIdentityRegistry()
    result = ingest_aria_fixture(registry=registry)
    assert len(result.canonical_records) == 2
    assert not result.rejected_events
    plan = _run_planner(result.canonical_records)
    assert plan.horizon_passed
    outpatient = next(r for r in result.canonical_records if r.patient_type == "OUTPATIENT")
    entries = plan_for_patient(plan, internal_model_patient_id=outpatient.internal_model_patient_id)
    assert len(entries) == 1
    assert entries[0].completed_within_operating_day


def test_aria_fixed_appointment_preserves_mutability() -> None:
    """Section 69."""
    registry = CrossSourceIdentityRegistry()
    result = ingest_aria_fixture(registry=registry)
    outpatient = next(r for r in result.canonical_records if r.patient_type == "OUTPATIENT")
    assert outpatient.scheduled_date_mutability == "FIXED"


def test_aria_flexible_window_preserved() -> None:
    """Section 70."""
    registry = CrossSourceIdentityRegistry()
    result = ingest_aria_fixture(registry=registry)
    inbound = next(r for r in result.canonical_records if r.patient_type == "INBOUND_PATIENT")
    assert inbound.scheduled_date_mutability == "OPTIMIZABLE_WITHIN_WINDOW"


def test_radionuclide_not_guessed_when_missing() -> None:
    """Section 49/71: a procedure order lacking radionuclide must never be
    guessed as F-18 or any isotope."""
    fixture = (
        {"fixture_label": "SYNTHETIC_TEST_FIXTURE", "event_type": "PATIENT", "external_patient_reference": "ARIA-PAT-099", "patient_type": "OUTPATIENT"},
        {"fixture_label": "SYNTHETIC_TEST_FIXTURE", "event_type": "APPOINTMENT", "external_patient_reference": "ARIA-PAT-099", "scheduled_date": date(2026, 10, 5), "appointment_mutability": "FIXED"},
    )
    registry = CrossSourceIdentityRegistry()
    result = ingest_aria_fixture(registry=registry, fixture=fixture)
    assert result.canonical_records == ()
    assert any(RADIONUCLIDE_NOT_SUPPLIED in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Section 58/60/61: GE DoseWatch reconciliation + three-source convergence
# ---------------------------------------------------------------------------


def test_ge_dosewatch_reconciles_to_existing_patient_no_duplicate() -> None:
    registry = CrossSourceIdentityRegistry()
    aria_result = ingest_aria_fixture(registry=registry)
    canonical_patient_id = aria_result.canonical_records[0].internal_model_patient_id
    canonical_procedure_id = aria_result.canonical_records[0].protocol_id

    dw_result = ingest_ge_dosewatch_fixture(registry=registry, known_canonical_patient_id=canonical_patient_id, known_canonical_procedure_id=canonical_procedure_id)
    assert dw_result.canonical_records == ()  # DoseWatch never independently produces a new patient record
    assert not dw_result.rejected_events
    # Same canonical patient, not a second one.
    patient_refs = registry.external_references_for_patient(canonical_patient_id)
    assert ("VARIAN_ARIA", "ARIA-PAT-001") in patient_refs
    assert ("GE_DOSEWATCH", "DW-PAT-001") in patient_refs
    assert len({ref for _, ref in patient_refs}) == 2  # two distinct external refs, one canonical patient


def test_dosewatch_without_known_patient_is_unresolved() -> None:
    """Section 66: DoseWatch/Siemens event referencing an unknown external
    patient must not fabricate a canonical patient."""
    registry = CrossSourceIdentityRegistry()
    result = ingest_ge_dosewatch_fixture(registry=registry, known_canonical_patient_id=None)
    assert result.accepted_events == ()
    assert all(reason == "UNRESOLVED_EXTERNAL_IDENTITY" for _, reason in result.rejected_events)


def test_three_source_convergence_one_patient_one_procedure_one_scanner() -> None:
    """Sections 42, 60-61."""
    registry = CrossSourceIdentityRegistry()
    aria_result = ingest_aria_fixture(registry=registry)
    canonical_patient_id = aria_result.canonical_records[0].internal_model_patient_id
    canonical_procedure_id = aria_result.canonical_records[0].protocol_id

    dw_result = ingest_ge_dosewatch_fixture(registry=registry, known_canonical_patient_id=canonical_patient_id, known_canonical_procedure_id=canonical_procedure_id)
    siemens_result = ingest_siemens_fixture(registry=registry, canonical_resource_id="SCN-001", known_canonical_procedure_id=canonical_procedure_id)

    validation = run_integration_validation(registry=registry, adapter_results=[aria_result, dw_result, siemens_result])
    assert validation.passed

    # ONE canonical patient.
    assert len({ref for src, ref in registry.external_references_for_patient(canonical_patient_id) if src == "VARIAN_ARIA"}) == 1
    # ONE canonical procedure, referenced by DoseWatch AND Siemens.
    procedure_refs = registry.external_references_for_procedure(canonical_procedure_id)
    assert ("GE_DOSEWATCH", "DW-STUDY-001") in procedure_refs
    assert ("SIEMENS_HEALTHINEERS", "SIEMENS-ACC-001") in procedure_refs
    # ONE canonical scanner.
    resource_refs = registry.external_references_for_resource("SCN-001")
    assert ("SIEMENS_HEALTHINEERS", "SIEMENS-DEVICE-001") in resource_refs


def test_cross_source_provenance_distinct_per_object() -> None:
    """Section 43/61: patient/order provenance, dose/imaging provenance, and
    scanner/device provenance remain independently reportable, never
    collapsed into one vendor label."""
    registry = CrossSourceIdentityRegistry()
    aria_result = ingest_aria_fixture(registry=registry)
    canonical_patient_id = aria_result.canonical_records[0].internal_model_patient_id
    canonical_procedure_id = aria_result.canonical_records[0].protocol_id
    ingest_ge_dosewatch_fixture(registry=registry, known_canonical_patient_id=canonical_patient_id, known_canonical_procedure_id=canonical_procedure_id)
    ingest_siemens_fixture(registry=registry, canonical_resource_id="SCN-001", known_canonical_procedure_id=canonical_procedure_id)

    patient_sources = {src for src, _ in registry.external_references_for_patient(canonical_patient_id)}
    procedure_sources = {src for src, _ in registry.external_references_for_procedure(canonical_procedure_id)}
    resource_sources = {src for src, _ in registry.external_references_for_resource("SCN-001")}
    assert patient_sources == {"VARIAN_ARIA", "GE_DOSEWATCH"}
    assert procedure_sources == {"GE_DOSEWATCH", "SIEMENS_HEALTHINEERS"}
    assert resource_sources == {"SIEMENS_HEALTHINEERS"}


# ---------------------------------------------------------------------------
# Section 62: source-conflict controlled test
# ---------------------------------------------------------------------------


def test_source_conflict_recorded_not_silently_overwritten() -> None:
    registry = CrossSourceIdentityRegistry()
    registry.record_source_conflict(SourceConflict(
        canonical_object_id="P-ARIA-001", field_or_event="prescribed_activity_mbq",
        source_a="VARIAN_ARIA", value_a=200.0, source_b="GE_DOSEWATCH", value_b=250.0,
    ))
    validation = run_integration_validation(registry=registry, adapter_results=[])
    assert not validation.passed
    assert len(validation.unresolved_source_conflicts) == 1
    assert validation.unresolved_source_conflicts[0].resolution_status == "SOURCE_CONFLICT"


# ---------------------------------------------------------------------------
# Section 63-65: idempotency + identity conflict tests
# ---------------------------------------------------------------------------


def test_duplicate_event_ingestion_is_idempotent() -> None:
    registry = CrossSourceIdentityRegistry()
    first = ingest_aria_fixture(registry=registry)
    second = ingest_aria_fixture(registry=registry)  # same fixture, same event ids
    assert len(first.canonical_records) == 2
    assert second.accepted_events == ()  # every event already processed
    assert len(second.warnings) == len(build_aria_fixture())


def test_external_patient_identity_conflict_detected() -> None:
    """Section 64."""
    registry = CrossSourceIdentityRegistry()
    registry.resolve_or_register_patient(source_system="VARIAN_ARIA", external_reference="ARIA-PAT-001", new_canonical_patient_id="P-A")
    registry.resolve_or_register_patient(source_system="VARIAN_ARIA", external_reference="ARIA-PAT-001", known_canonical_patient_id="P-B")
    assert len(registry.identity_conflicts) == 1
    assert registry.identity_conflicts[0].kind == "PATIENT"


def test_external_device_identity_conflict_detected() -> None:
    """Section 65."""
    registry = CrossSourceIdentityRegistry()
    registry.resolve_device(source_system="SIEMENS_HEALTHINEERS", external_reference="SIEMENS-DEVICE-001", canonical_resource_id="SCN-001")
    registry.resolve_device(source_system="SIEMENS_HEALTHINEERS", external_reference="SIEMENS-DEVICE-001", canonical_resource_id="SCN-002")
    assert len(registry.identity_conflicts) == 1
    assert registry.identity_conflicts[0].kind == "DEVICE"


def test_two_external_devices_map_to_same_scanner_no_duplication() -> None:
    """Section 38/73."""
    registry = CrossSourceIdentityRegistry()
    registry.resolve_device(source_system="SIEMENS_HEALTHINEERS", external_reference="SIEMENS-DEVICE-001", canonical_resource_id="SCN-003")
    registry.resolve_device(source_system="GE_DOSEWATCH", external_reference="DW-DEVICE-77", canonical_resource_id="SCN-003")
    assert registry.external_references_for_resource("SCN-003") == (
        ("SIEMENS_HEALTHINEERS", "SIEMENS-DEVICE-001"), ("GE_DOSEWATCH", "DW-DEVICE-77"),
    )
    assert registry.identity_conflicts == []


# ---------------------------------------------------------------------------
# Section 67-68: synthetic+connected coexistence, optimizer independence
# ---------------------------------------------------------------------------


def test_synthetic_and_external_and_forecast_coexist_in_one_horizon() -> None:
    from long_horizon_operational_planning import CanonicalOperationalPatientRecord

    registry = CrossSourceIdentityRegistry()
    aria_result = ingest_aria_fixture(registry=registry)
    synthetic_record = CanonicalOperationalPatientRecord(
        internal_model_patient_id="P-SYNTH-1", demand_status="COMMITTED", patient_type="OUTPATIENT",
        radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5), source_provenance="USER_ENTERED",
    )
    forecast_record = CanonicalOperationalPatientRecord(
        internal_model_patient_id="FORECAST-2026-10-05-F18-999", demand_status="FORECAST", patient_type="OUTPATIENT",
        radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5), source_provenance="FORECAST_MODEL",
    )
    records = list(aria_result.canonical_records) + [synthetic_record, forecast_record]
    plan = _run_planner(records)
    assert plan.committed_patient_count == 3  # 2 ARIA + 1 synthetic
    assert plan.forecast_demand_count == 1
    assert {r.internal_model_patient_id for r in aria_result.canonical_records}.issubset({p.internal_model_patient_id for p in plan.patient_plans})
    assert "FORECAST-2026-10-05-F18-999" not in {p.internal_model_patient_id for p in plan.patient_plans}


def test_optimizer_modules_contain_no_vendor_conditionals() -> None:
    """Section 68: no VARIAN_ARIA/GE_DOSEWATCH/SIEMENS_HEALTHINEERS string
    literals inside optimizer-facing modules."""
    import inspect

    import production_clinical_schedule
    import operating_day_scheduler
    import decision_pipeline
    import radiopharm_workflow_staffing

    vendor_terms = ("VARIAN_ARIA", "GE_DOSEWATCH", "SIEMENS_HEALTHINEERS")
    for module in (production_clinical_schedule, operating_day_scheduler, decision_pipeline, radiopharm_workflow_staffing):
        source = inspect.getsource(module)
        for term in vendor_terms:
            assert term not in source, f"{module.__name__} contains vendor-specific term {term}"


# ---------------------------------------------------------------------------
# Section 86: synthetic non-regression
# ---------------------------------------------------------------------------


def test_synthetic_planning_path_non_regression() -> None:
    from long_horizon_operational_planning import CanonicalOperationalPatientRecord

    records = [
        CanonicalOperationalPatientRecord(
            internal_model_patient_id=f"P{i}", demand_status="COMMITTED", patient_type="OUTPATIENT",
            radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5), source_provenance="USER_ENTERED",
        )
        for i in range(4)
    ]
    plan = _run_planner(records)
    assert plan.committed_patient_count == 4
    assert plan.horizon_passed
    assert sum(1 for p in plan.patient_plans if p.completed_within_operating_day) == 4


# ---------------------------------------------------------------------------
# Sections 74A-74C, 41: equipment specification / energy-model readiness
# ---------------------------------------------------------------------------


def test_cyclotron_identity_ready_for_specification_without_changing_calibration() -> None:
    """Section 74A: CY-001 gains manufacturer/model/spec readiness without
    altering its calibrated production capability or creating a second
    catalog."""
    from cyclotron_catalog import load_cyclotron_catalog

    catalog = load_cyclotron_catalog()
    model = catalog.by_id("GE_PETTRACE_890")
    equipment_record = EquipmentIdentityRecord(
        canonical_equipment_id="CY-001", equipment_class="CYCLOTRON",
        manufacturer=model.manufacturer, model=model.model, specification_provenance="cyclotron_catalog.py::CyclotronCatalogModel",
    )
    assert equipment_record.manufacturer == "GE HealthCare"
    assert equipment_record.model == "PETtrace 890"
    # No power specification yet -- honest NOT_CALIBRATED (section 74B), matching the
    # audited fact that GE_PETTRACE_890's field_provenance has no power_kw entry.
    assert equipment_record.energy_specification_status() == "ENERGY_SPECIFICATION_NOT_CALIBRATED"
    # Calibrated production capability (F-18 cycle time) is untouched by this record.
    assert model.production_cycle_minutes_by_radionuclide["F-18"] == 120.0


def test_scanner_ready_for_specification_no_power_fabrication() -> None:
    """Section 74B/D."""
    equipment_record = EquipmentIdentityRecord(canonical_equipment_id="SCN-001", equipment_class="SCANNER")
    assert equipment_record.manufacturer == "UNKNOWN"
    assert equipment_record.model == "UNKNOWN"
    assert equipment_record.energy_specification_status() == "ENERGY_SPECIFICATION_NOT_CALIBRATED"


def test_opex_electricity_double_counting_classification() -> None:
    """Section 74C/Q1: existing OPEX lines classified so a future energy
    engine does not double-count electricity."""
    assert classify_existing_opex_line_electricity_inclusion("Cyclotron annual fixed O&M") == "ELECTRICITY_EXCLUDED"
    assert classify_existing_opex_line_electricity_inclusion("Cyclotron energy") == "ELECTRICITY_INCLUDED"
    assert classify_existing_opex_line_electricity_inclusion("Scanner energy") == "ELECTRICITY_INCLUDED"
    assert classify_existing_opex_line_electricity_inclusion("Some unrecognized future line") == "MIXED_OR_UNKNOWN"


def test_security_compliance_not_claimed() -> None:
    """Section 93."""
    assert "SECURITY_COMPLIANCE_NOT_IN_SCOPE" in SECURITY_COMPLIANCE_NOT_IN_SCOPE
    assert "HIPAA" not in SECURITY_COMPLIANCE_NOT_IN_SCOPE.upper().replace("NOT A HIPAA-COMPLIANT", "")


# ---------------------------------------------------------------------------
# Section 94: adapter extensibility (a minimal fake OTHER_VENDOR adapter)
# ---------------------------------------------------------------------------


def test_future_adapter_can_reuse_same_registry_interface() -> None:
    registry = CrossSourceIdentityRegistry()
    canonical_id = registry.resolve_or_register_patient(
        source_system="OTHER", external_reference="OTHER-PAT-001", new_canonical_patient_id="P-OTHER-1",
    )
    assert canonical_id == "P-OTHER-1"
    assert ("OTHER", "OTHER-PAT-001") in registry.external_references_for_patient("P-OTHER-1")

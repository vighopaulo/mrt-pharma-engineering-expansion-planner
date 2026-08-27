"""Vendor-specific adapter boundary (ARIA / GE DoseWatch / Siemens Healthineers).

Each adapter here ONLY knows how to read a synthetic, standards-compatible
fixture shape and normalize it into the vendor-neutral canonical model
(`healthcare_integration.CanonicalIntegrationEvent` +
`long_horizon_operational_planning.CanonicalOperationalPatientRecord`). No
adapter makes network calls, requires credentials, or claims official vendor
certification -- fixtures are clearly labeled SYNTHETIC_TEST_FIXTURE.

Vendor-specific logic terminates HERE. `run_long_horizon_operational_plan`
and every production/transport/clinical/staffing module remain completely
unaware which adapter (if any) produced a given canonical record.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Mapping, Sequence

from healthcare_integration import (
    RADIONUCLIDE_NOT_SUPPLIED,
    AdapterIngestResult,
    CanonicalIntegrationEvent,
    CrossSourceIdentityRegistry,
    SourceConflict,
)
from long_horizon_operational_planning import CanonicalOperationalPatientRecord

SYNTHETIC_TEST_FIXTURE = "SYNTHETIC_TEST_FIXTURE"


# ---------------------------------------------------------------------------
# 1. Varian ARIA-compatible adapter (sections 22-26, 69-71)
# ---------------------------------------------------------------------------


def build_aria_fixture() -> tuple[Mapping[str, object], ...]:
    """Deterministic synthetic ARIA-like fixture (section 24) -- NOT a real
    ARIA export, NOT proprietary data. Produces one committed outpatient with
    a FIXED appointment and one committed inbound patient with an
    OPTIMIZABLE_WITHIN_WINDOW appointment."""
    return (
        {
            "fixture_label": SYNTHETIC_TEST_FIXTURE, "event_type": "PATIENT",
            "external_patient_reference": "ARIA-PAT-001", "patient_type": "OUTPATIENT",
        },
        {
            "fixture_label": SYNTHETIC_TEST_FIXTURE, "event_type": "PROCEDURE_ORDER",
            "external_patient_reference": "ARIA-PAT-001", "external_procedure_reference": "ARIA-ORD-001",
            "radionuclide": "F-18", "prescribed_activity_mbq": 200.0,
        },
        {
            "fixture_label": SYNTHETIC_TEST_FIXTURE, "event_type": "APPOINTMENT",
            "external_patient_reference": "ARIA-PAT-001", "external_procedure_reference": "ARIA-ORD-001",
            "scheduled_date": date(2026, 10, 5), "appointment_mutability": "FIXED",
        },
        {
            "fixture_label": SYNTHETIC_TEST_FIXTURE, "event_type": "PATIENT",
            "external_patient_reference": "ARIA-PAT-002", "patient_type": "INBOUND_PATIENT",
        },
        {
            "fixture_label": SYNTHETIC_TEST_FIXTURE, "event_type": "ADMISSION",
            "external_patient_reference": "ARIA-PAT-002", "admission_date": date(2026, 10, 5),
            "expected_discharge_date": date(2026, 10, 8), "existing_room_id": "IR-001",
        },
        {
            "fixture_label": SYNTHETIC_TEST_FIXTURE, "event_type": "PROCEDURE_ORDER",
            "external_patient_reference": "ARIA-PAT-002", "external_procedure_reference": "ARIA-ORD-002",
            "radionuclide": "F-18", "prescribed_activity_mbq": 200.0,
        },
        {
            "fixture_label": SYNTHETIC_TEST_FIXTURE, "event_type": "APPOINTMENT",
            "external_patient_reference": "ARIA-PAT-002", "external_procedure_reference": "ARIA-ORD-002",
            "scheduled_date": date(2026, 10, 5), "appointment_mutability": "OPTIMIZABLE_WITHIN_WINDOW",
        },
    )


def ingest_aria_fixture(
    *, registry: CrossSourceIdentityRegistry, fixture: Sequence[Mapping[str, object]] | None = None,
    known_canonical_patient_id_by_external_ref: Mapping[str, str] | None = None,
) -> AdapterIngestResult:
    """Section 25-26: normalizes the ARIA-like fixture into
    CanonicalOperationalPatientRecord instances the EXISTING planner accepts
    unchanged. `known_canonical_patient_id_by_external_ref` simulates an
    explicit, deterministic crosswalk (section 14) -- never fuzzy matching."""
    rows = fixture if fixture is not None else build_aria_fixture()
    known_map = known_canonical_patient_id_by_external_ref or {}
    accepted: list[CanonicalIntegrationEvent] = []
    rejected: list[tuple[Mapping[str, object], str]] = []
    warnings: list[str] = []
    identity_resolutions: list[tuple[str, str]] = []
    records_by_patient: dict[str, dict[str, object]] = {}

    for index, row in enumerate(rows):
        source_event_id = f"ARIA-EVT-{index:03d}"
        if registry.already_processed(source_system="VARIAN_ARIA", source_event_id=source_event_id):
            warnings.append(f"{source_event_id}: already ingested, skipped (idempotent)")
            continue
        external_patient_reference = row.get("external_patient_reference")
        if not external_patient_reference:
            rejected.append((row, "missing external_patient_reference"))
            continue
        canonical_patient_id = registry.resolve_or_register_patient(
            source_system="VARIAN_ARIA", external_reference=str(external_patient_reference),
            known_canonical_patient_id=known_map.get(str(external_patient_reference)),
            new_canonical_patient_id=str(external_patient_reference).replace("ARIA-PAT-", "P-ARIA-"),
        )
        identity_resolutions.append(("PATIENT", canonical_patient_id))
        event = CanonicalIntegrationEvent(
            source_system="VARIAN_ARIA", source_event_id=source_event_id, event_type=row["event_type"],
            event_timestamp=datetime(2026, 10, 5), external_patient_reference=str(external_patient_reference),
            external_procedure_reference=str(row["external_procedure_reference"]) if row.get("external_procedure_reference") else None,
            canonical_patient_id=canonical_patient_id, payload=row,
        )
        registry.mark_processed(source_system="VARIAN_ARIA", source_event_id=source_event_id, event=event)
        accepted.append(event)

        state = records_by_patient.setdefault(canonical_patient_id, {
            "internal_model_patient_id": canonical_patient_id,
            "external_patient_reference": str(external_patient_reference),
            "patient_type": "OUTPATIENT",
        })
        if row["event_type"] == "PATIENT":
            state["patient_type"] = row.get("patient_type", "OUTPATIENT")
        elif row["event_type"] == "PROCEDURE_ORDER":
            state["radionuclide"] = row.get("radionuclide", RADIONUCLIDE_NOT_SUPPLIED)
            state["prescribed_activity_mbq"] = row.get("prescribed_activity_mbq")
            state["protocol_id"] = row.get("external_procedure_reference")
            if "modality" in row:
                state["modality"] = row["modality"]
            if "clinical_priority" in row:
                state["clinical_priority"] = row["clinical_priority"]
        elif row["event_type"] == "APPOINTMENT":
            state["scheduled_date"] = row.get("scheduled_date")
            state["scheduled_date_mutability"] = row.get("appointment_mutability", "OPTIMIZABLE_WITHIN_WINDOW")
            if "earliest_scheduled_date" in row:
                state["earliest_scheduled_date"] = row["earliest_scheduled_date"]
            if "latest_scheduled_date" in row:
                state["latest_scheduled_date"] = row["latest_scheduled_date"]
        elif row["event_type"] == "ADMISSION":
            state["admission_datetime"] = row.get("admission_date")
            state["expected_discharge_date"] = row.get("expected_discharge_date")
            state["existing_room_id"] = row.get("existing_room_id")

    canonical_records: list[CanonicalOperationalPatientRecord] = []
    for state in records_by_patient.values():
        if state.get("radionuclide") in (None, RADIONUCLIDE_NOT_SUPPLIED):
            warnings.append(f"{state['internal_model_patient_id']}: {RADIONUCLIDE_NOT_SUPPLIED} -- no procedure order supplied a radionuclide")
            continue
        if state.get("scheduled_date") is None:
            warnings.append(f"{state['internal_model_patient_id']}: no appointment date supplied, cannot schedule")
            continue
        is_inbound = state["patient_type"] == "INBOUND_PATIENT"
        canonical_records.append(CanonicalOperationalPatientRecord(
            internal_model_patient_id=state["internal_model_patient_id"],
            demand_status="COMMITTED",
            patient_type=state["patient_type"],
            radionuclide=state["radionuclide"],
            prescribed_activity_mbq=float(state["prescribed_activity_mbq"]),
            scheduled_date=state["scheduled_date"],
            source_provenance="EHR",
            external_patient_reference=state["external_patient_reference"],
            protocol_id=state.get("protocol_id"),
            scheduled_date_mutability=state.get("scheduled_date_mutability", "OPTIMIZABLE_WITHIN_WINDOW"),
            admission_datetime=state.get("admission_datetime") if is_inbound else None,
            expected_discharge_date=state.get("expected_discharge_date") if is_inbound else None,
            existing_room_id=state.get("existing_room_id") if is_inbound else None,
            clinical_resource_mode="INBOUND_CENTRALIZED" if is_inbound else "OUTPATIENT_SHARED",
            earliest_scheduled_date=state.get("earliest_scheduled_date"),
            latest_scheduled_date=state.get("latest_scheduled_date"),
            modality=state.get("modality"),
            clinical_priority=state.get("clinical_priority"),
        ))

    return AdapterIngestResult(
        adapter_name="VARIAN_ARIA", accepted_events=tuple(accepted), rejected_events=tuple(rejected),
        warnings=tuple(warnings), identity_resolutions=tuple(identity_resolutions),
        identity_conflicts=tuple(registry.identity_conflicts), source_conflicts=tuple(registry.source_conflicts),
        canonical_records=tuple(canonical_records),
    )


# ---------------------------------------------------------------------------
# 2. GE DoseWatch-compatible adapter (sections 27-31, 58)
# ---------------------------------------------------------------------------


def build_ge_dosewatch_fixture(*, external_patient_reference: str = "DW-PAT-001", external_procedure_reference: str = "DW-STUDY-001") -> tuple[Mapping[str, object], ...]:
    """Deterministic synthetic HL7/DICOM-derived-style fixture (section 29).
    DoseWatch is NOT assumed to supply LOS/inbound-room/cyclotron/billing
    information (section 28) -- only imaging/dose-event/device/status data."""
    return (
        {
            "fixture_label": SYNTHETIC_TEST_FIXTURE, "event_type": "IMAGING_STUDY",
            "external_patient_reference": external_patient_reference, "external_procedure_reference": external_procedure_reference,
            "external_device_reference": "GE-DEVICE-77",
            "procedure_status": "COMPLETED", "actual_procedure_time": datetime(2026, 10, 5, 14, 30),
        },
        {
            "fixture_label": SYNTHETIC_TEST_FIXTURE, "event_type": "DOSE_EVENT",
            "external_patient_reference": external_patient_reference, "external_procedure_reference": external_procedure_reference,
            "dose_event_note": "generic imaging dose-index information -- NOT radionuclide production activity",
        },
    )


def ingest_ge_dosewatch_fixture(
    *, registry: CrossSourceIdentityRegistry, fixture: Sequence[Mapping[str, object]] | None = None,
    known_canonical_patient_id: str, known_canonical_procedure_id: str | None = None,
) -> AdapterIngestResult:
    """Section 30/58: DoseWatch events must reconcile to an ALREADY-KNOWN
    canonical patient/procedure (e.g. previously introduced by ARIA) -- never
    a new patient fabricated merely because the source differs. Callers MUST
    supply `known_canonical_patient_id`; without it the event is rejected
    with UNRESOLVED_EXTERNAL_IDENTITY (section 66)."""
    rows = fixture if fixture is not None else build_ge_dosewatch_fixture()
    accepted: list[CanonicalIntegrationEvent] = []
    rejected: list[tuple[Mapping[str, object], str]] = []
    warnings: list[str] = []
    identity_resolutions: list[tuple[str, str]] = []

    for index, row in enumerate(rows):
        source_event_id = f"DW-EVT-{index:03d}"
        if registry.already_processed(source_system="GE_DOSEWATCH", source_event_id=source_event_id):
            warnings.append(f"{source_event_id}: already ingested, skipped (idempotent)")
            continue
        external_patient_reference = row.get("external_patient_reference")
        if not external_patient_reference:
            rejected.append((row, "missing external_patient_reference"))
            continue
        if known_canonical_patient_id is None:
            rejected.append((row, "UNRESOLVED_EXTERNAL_IDENTITY"))
            continue
        canonical_patient_id = registry.resolve_or_register_patient(
            source_system="GE_DOSEWATCH", external_reference=str(external_patient_reference),
            known_canonical_patient_id=known_canonical_patient_id,
        )
        identity_resolutions.append(("PATIENT", canonical_patient_id))
        canonical_procedure_id = None
        if row.get("external_procedure_reference"):
            canonical_procedure_id = registry.resolve_or_register_procedure(
                source_system="GE_DOSEWATCH", external_reference=str(row["external_procedure_reference"]),
                known_canonical_procedure_id=known_canonical_procedure_id,
                new_canonical_procedure_id=known_canonical_procedure_id or str(row["external_procedure_reference"]),
            )
            identity_resolutions.append(("PROCEDURE", canonical_procedure_id))
        event = CanonicalIntegrationEvent(
            source_system="GE_DOSEWATCH", source_event_id=source_event_id, event_type=row["event_type"],
            event_timestamp=row.get("actual_procedure_time", datetime(2026, 10, 5)),
            external_patient_reference=str(external_patient_reference),
            external_procedure_reference=str(row["external_procedure_reference"]) if row.get("external_procedure_reference") else None,
            external_device_reference=str(row["external_device_reference"]) if row.get("external_device_reference") else None,
            canonical_patient_id=canonical_patient_id, canonical_procedure_id=canonical_procedure_id, payload=row,
        )
        registry.mark_processed(source_system="GE_DOSEWATCH", source_event_id=source_event_id, event=event)
        accepted.append(event)

    return AdapterIngestResult(
        adapter_name="GE_DOSEWATCH", accepted_events=tuple(accepted), rejected_events=tuple(rejected),
        warnings=tuple(warnings), identity_resolutions=tuple(identity_resolutions),
        identity_conflicts=tuple(registry.identity_conflicts), source_conflicts=tuple(registry.source_conflicts),
        canonical_records=(),  # DoseWatch never independently produces a schedulable canonical patient record.
    )


# ---------------------------------------------------------------------------
# 3. Siemens Healthineers-compatible adapter (sections 32-38, 59)
# ---------------------------------------------------------------------------


def build_siemens_fixture(*, external_device_reference: str = "SIEMENS-DEVICE-001", external_procedure_reference: str = "SIEMENS-ACC-001") -> tuple[Mapping[str, object], ...]:
    """Deterministic synthetic DICOM/vendor-platform-style fixture (section
    35). Siemens integration is product/interface-specific (section 32) --
    this fixture represents a generic accession/study + device-status event,
    not a claim about any specific Siemens product's live API."""
    return (
        {
            "fixture_label": SYNTHETIC_TEST_FIXTURE, "event_type": "DEVICE_STATUS",
            "external_device_reference": external_device_reference, "manufacturer": "Siemens Healthineers", "model": "UNKNOWN",
        },
        {
            "fixture_label": SYNTHETIC_TEST_FIXTURE, "event_type": "IMAGING_STUDY",
            "external_procedure_reference": external_procedure_reference, "external_device_reference": external_device_reference,
            "study_status": "COMPLETED", "procedure_start": datetime(2026, 10, 5, 14, 0), "procedure_completion": datetime(2026, 10, 5, 14, 30),
        },
    )


def ingest_siemens_fixture(
    *, registry: CrossSourceIdentityRegistry, fixture: Sequence[Mapping[str, object]] | None = None,
    canonical_resource_id: str, known_canonical_procedure_id: str | None = None,
) -> AdapterIngestResult:
    """Section 36/59: maps the external Siemens device reference to an
    EXISTING persistent canonical resource (e.g. "SCN-003") -- the caller
    supplies which physical resource this device reference represents
    (an explicit facility crosswalk); the adapter never invents a new
    scanner (section 90)."""
    rows = fixture if fixture is not None else build_siemens_fixture()
    accepted: list[CanonicalIntegrationEvent] = []
    rejected: list[tuple[Mapping[str, object], str]] = []
    warnings: list[str] = []
    identity_resolutions: list[tuple[str, str]] = []

    for index, row in enumerate(rows):
        source_event_id = f"SIEMENS-EVT-{index:03d}"
        if registry.already_processed(source_system="SIEMENS_HEALTHINEERS", source_event_id=source_event_id):
            warnings.append(f"{source_event_id}: already ingested, skipped (idempotent)")
            continue
        resolved_resource_id = None
        if row.get("external_device_reference"):
            resolved_resource_id = registry.resolve_device(
                source_system="SIEMENS_HEALTHINEERS", external_reference=str(row["external_device_reference"]),
                canonical_resource_id=canonical_resource_id,
            )
            if resolved_resource_id is None:
                rejected.append((row, "UNRESOLVED_EXTERNAL_IDENTITY"))
                continue
            identity_resolutions.append(("DEVICE", resolved_resource_id))
        canonical_procedure_id = None
        if row.get("external_procedure_reference"):
            canonical_procedure_id = registry.resolve_or_register_procedure(
                source_system="SIEMENS_HEALTHINEERS", external_reference=str(row["external_procedure_reference"]),
                known_canonical_procedure_id=known_canonical_procedure_id,
                new_canonical_procedure_id=known_canonical_procedure_id or str(row["external_procedure_reference"]),
            )
            identity_resolutions.append(("PROCEDURE", canonical_procedure_id))
        event = CanonicalIntegrationEvent(
            source_system="SIEMENS_HEALTHINEERS", source_event_id=source_event_id, event_type=row["event_type"],
            event_timestamp=row.get("procedure_completion", datetime(2026, 10, 5)),
            external_procedure_reference=str(row["external_procedure_reference"]) if row.get("external_procedure_reference") else None,
            external_device_reference=str(row["external_device_reference"]) if row.get("external_device_reference") else None,
            canonical_procedure_id=canonical_procedure_id, payload=row,
        )
        registry.mark_processed(source_system="SIEMENS_HEALTHINEERS", source_event_id=source_event_id, event=event)
        accepted.append(event)

    return AdapterIngestResult(
        adapter_name="SIEMENS_HEALTHINEERS", accepted_events=tuple(accepted), rejected_events=tuple(rejected),
        warnings=tuple(warnings), identity_resolutions=tuple(identity_resolutions),
        identity_conflicts=tuple(registry.identity_conflicts), source_conflicts=tuple(registry.source_conflicts),
        canonical_records=(),  # Siemens device/study events never independently produce a schedulable canonical patient record.
    )

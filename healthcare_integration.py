"""Vendor-Neutral Healthcare Integration Foundation.

GOVERNING PRINCIPLE (section 3): the optimizer must never know which vendor
supplied data. This module -- and its sibling `healthcare_adapters.py` -- form
the ONLY layer where vendor-specific interpretation happens. Nothing here
touches production/transport/clinical-scheduling/staffing/economics logic;
adapters only ever produce the EXISTING
`long_horizon_operational_planning.CanonicalOperationalPatientRecord`.

No live connections, no credentials, no network calls (sections: "DO NOT
connect to live hospital systems"). All adapter fixtures are synthetic,
explicitly labeled `SYNTHETIC_TEST_FIXTURE`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping, Sequence

SourceSystem = Literal[
    "SYNTHETIC", "MANUAL", "FORECAST", "VARIAN_ARIA", "GE_DOSEWATCH", "SIEMENS_HEALTHINEERS", "OTHER",
]
IntegrationEventType = Literal[
    "PATIENT", "PROCEDURE_ORDER", "APPOINTMENT", "ENCOUNTER", "ADMISSION", "DISCHARGE",
    "IMAGING_STUDY", "PROCEDURE_STATUS", "DEVICE_STATUS", "DOSE_EVENT", "RESOURCE_SCHEDULE", "OTHER",
]
FieldProvenanceClass = Literal["SOURCE_TRUTH", "OPTIMIZER_DERIVED", "PROJECT_ASSUMPTION", "FORECAST", "UNKNOWN"]

RADIONUCLIDE_NOT_SUPPLIED = "RADIONUCLIDE_NOT_SUPPLIED"
UNRESOLVED_EXTERNAL_IDENTITY = "UNRESOLVED_EXTERNAL_IDENTITY"

SECURITY_COMPLIANCE_NOT_IN_SCOPE = (
    "SECURITY_COMPLIANCE_NOT_IN_SCOPE: this foundation implements no authentication, authorization, "
    "encryption, audit logging, PHI governance, or BAA/compliance controls. A real deployment requires all "
    "of these before connecting to any live hospital system. This is NOT a HIPAA-compliant system."
)


# ---------------------------------------------------------------------------
# Canonical integration event (section 5-8)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalIntegrationEvent:
    """Vendor-neutral event envelope (section 5). Fields are optional except
    the minimum needed for idempotent identity (`source_system` +
    `source_event_id`) -- not every event carries every reference."""

    source_system: SourceSystem
    source_event_id: str
    event_type: IntegrationEventType
    event_timestamp: datetime
    received_timestamp: datetime | None = None
    external_patient_reference: str | None = None
    external_procedure_reference: str | None = None
    external_encounter_reference: str | None = None
    external_device_reference: str | None = None
    canonical_patient_id: str | None = None
    canonical_procedure_id: str | None = None
    payload: Mapping[str, object] = field(default_factory=dict)
    """Opaque unmapped vendor fields (section 55) -- retained for audit only,
    never consulted by engineering calculations."""


@dataclass(frozen=True)
class IdentityConflict:
    """Section 15/64/65: one external identity mapped to two canonical objects."""

    kind: Literal["PATIENT", "PROCEDURE", "DEVICE"]
    source_system: SourceSystem
    external_reference: str
    existing_canonical_id: str
    attempted_canonical_id: str


@dataclass(frozen=True)
class SourceConflict:
    """Section 44-45: two sources disagree on the same SOURCE_TRUTH field --
    never silently overwritten."""

    canonical_object_id: str
    field_or_event: str
    source_a: SourceSystem
    value_a: object
    source_b: SourceSystem
    value_b: object
    resolution_status: str = "SOURCE_CONFLICT"


# ---------------------------------------------------------------------------
# Cross-source identity registry (sections 10-17)
# ---------------------------------------------------------------------------


@dataclass
class CrossSourceIdentityRegistry:
    """Deterministic (section 14: NO fuzzy/PHI matching) crosswalk from
    (source_system, external_reference) to one canonical identity, for
    patients, procedures, and physical resources (scanners/cyclotrons)."""

    _patient_map: dict[tuple[SourceSystem, str], str] = field(default_factory=dict)
    _procedure_map: dict[tuple[SourceSystem, str], str] = field(default_factory=dict)
    _device_map: dict[tuple[SourceSystem, str], str] = field(default_factory=dict)
    _processed_event_ids: set[tuple[SourceSystem, str]] = field(default_factory=set)
    _event_journal: list[CanonicalIntegrationEvent] = field(default_factory=list)
    identity_conflicts: list[IdentityConflict] = field(default_factory=list)
    source_conflicts: list[SourceConflict] = field(default_factory=list)

    def already_processed(self, *, source_system: SourceSystem, source_event_id: str) -> bool:
        """Section 16: idempotency key = source_system + source_event_id."""
        return (source_system, source_event_id) in self._processed_event_ids

    def mark_processed(self, *, source_system: SourceSystem, source_event_id: str, event: CanonicalIntegrationEvent) -> None:
        self._processed_event_ids.add((source_system, source_event_id))
        self._event_journal.append(event)

    def resolve_or_register_patient(
        self, *, source_system: SourceSystem, external_reference: str, known_canonical_patient_id: str | None = None,
        new_canonical_patient_id: str | None = None,
    ) -> str:
        """Section 11/13: first sight of an external ref registers a new
        canonical patient (id supplied by caller/adapter, deterministic --
        never invented from name/DOB); a later source may explicitly
        reconcile to an ALREADY KNOWN canonical id via `known_canonical_patient_id`
        (simulating an explicit crosswalk, never automatic fuzzy matching,
        section 14). Returns the resolved canonical_patient_id; raises on conflict."""
        return self._resolve_or_register(
            registry=self._patient_map, kind="PATIENT", source_system=source_system, external_reference=external_reference,
            known_canonical_id=known_canonical_patient_id, new_canonical_id=new_canonical_patient_id,
        )

    def resolve_or_register_procedure(
        self, *, source_system: SourceSystem, external_reference: str, known_canonical_procedure_id: str | None = None,
        new_canonical_procedure_id: str | None = None,
    ) -> str:
        return self._resolve_or_register(
            registry=self._procedure_map, kind="PROCEDURE", source_system=source_system, external_reference=external_reference,
            known_canonical_id=known_canonical_procedure_id, new_canonical_id=new_canonical_procedure_id,
        )

    def resolve_device(self, *, source_system: SourceSystem, external_reference: str, canonical_resource_id: str | None) -> str | None:
        """Section 36-38/90: a device reference may ONLY resolve to an
        EXISTING, explicitly-supplied canonical_resource_id (e.g. "SCN-003")
        -- it never fabricates a new physical resource. Returns None
        (UNRESOLVED_EXTERNAL_IDENTITY) if no mapping exists and none is
        supplied this call."""
        key = (source_system, external_reference)
        if key in self._device_map:
            existing = self._device_map[key]
            if canonical_resource_id is not None and canonical_resource_id != existing:
                self.identity_conflicts.append(IdentityConflict(
                    kind="DEVICE", source_system=source_system, external_reference=external_reference,
                    existing_canonical_id=existing, attempted_canonical_id=canonical_resource_id,
                ))
                return existing
            return existing
        if canonical_resource_id is None:
            return None
        self._device_map[key] = canonical_resource_id
        return canonical_resource_id

    def _resolve_or_register(
        self, *, registry: dict[tuple[SourceSystem, str], str], kind: Literal["PATIENT", "PROCEDURE"],
        source_system: SourceSystem, external_reference: str, known_canonical_id: str | None, new_canonical_id: str | None,
    ) -> str:
        key = (source_system, external_reference)
        if key in registry:
            existing = registry[key]
            if known_canonical_id is not None and known_canonical_id != existing:
                self.identity_conflicts.append(IdentityConflict(
                    kind=kind, source_system=source_system, external_reference=external_reference,
                    existing_canonical_id=existing, attempted_canonical_id=known_canonical_id,
                ))
                return existing
            return existing
        canonical_id = known_canonical_id or new_canonical_id
        if canonical_id is None:
            raise ValueError(f"Cannot register a new {kind} without new_canonical_id or known_canonical_id")
        registry[key] = canonical_id
        return canonical_id

    def external_references_for_patient(self, canonical_patient_id: str) -> tuple[tuple[SourceSystem, str], ...]:
        return tuple(key for key, value in self._patient_map.items() if value == canonical_patient_id)

    def external_references_for_procedure(self, canonical_procedure_id: str) -> tuple[tuple[SourceSystem, str], ...]:
        return tuple(key for key, value in self._procedure_map.items() if value == canonical_procedure_id)

    def external_references_for_resource(self, canonical_resource_id: str) -> tuple[tuple[SourceSystem, str], ...]:
        return tuple(key for key, value in self._device_map.items() if value == canonical_resource_id)

    def events_for_patient(self, canonical_patient_id: str) -> tuple[CanonicalIntegrationEvent, ...]:
        """Section 76: canonical event journal query."""
        return tuple(e for e in self._event_journal if e.canonical_patient_id == canonical_patient_id)

    def record_source_conflict(self, conflict: SourceConflict) -> None:
        self.source_conflicts.append(conflict)


# ---------------------------------------------------------------------------
# Adapter ingestion / integration validation results (sections 53, 88)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdapterIngestResult:
    adapter_name: str
    accepted_events: tuple[CanonicalIntegrationEvent, ...]
    rejected_events: tuple[tuple[Mapping[str, object], str], ...]
    """(raw fixture row, rejection reason) pairs -- never a bare exception."""
    warnings: tuple[str, ...]
    identity_resolutions: tuple[tuple[str, str], ...]
    """(kind, canonical_id) pairs, one per resolved identity this ingestion touched."""
    identity_conflicts: tuple[IdentityConflict, ...]
    source_conflicts: tuple[SourceConflict, ...]
    canonical_records: tuple[object, ...]
    """CanonicalOperationalPatientRecord instances produced (section 25/58/59)."""


@dataclass(frozen=True)
class IntegrationValidationResult:
    passed: bool
    violations: tuple[str, ...]
    warnings: tuple[str, ...]
    unresolved_identity_conflicts: tuple[IdentityConflict, ...]
    unresolved_source_conflicts: tuple[SourceConflict, ...]
    adapter_failures: tuple[str, ...]


def run_integration_validation(*, registry: CrossSourceIdentityRegistry, adapter_results: Sequence[AdapterIngestResult]) -> IntegrationValidationResult:
    violations: list[str] = []
    warnings: list[str] = []
    adapter_failures: list[str] = []
    for result in adapter_results:
        warnings.extend(result.warnings)
        if result.rejected_events:
            adapter_failures.append(f"{result.adapter_name}: {len(result.rejected_events)} rejected event(s)")
    if registry.identity_conflicts:
        violations.append(f"{len(registry.identity_conflicts)} unresolved identity conflict(s)")
    if registry.source_conflicts:
        violations.append(f"{len(registry.source_conflicts)} unresolved source conflict(s)")
    return IntegrationValidationResult(
        passed=not violations,
        violations=tuple(violations),
        warnings=tuple(warnings),
        unresolved_identity_conflicts=tuple(registry.identity_conflicts),
        unresolved_source_conflicts=tuple(registry.source_conflicts),
        adapter_failures=tuple(adapter_failures),
    )


# ---------------------------------------------------------------------------
# Equipment specification / energy-model readiness (sections 39-41, 74A-74C)
# NOT an energy calculation -- identity/specification hooks only.
# ---------------------------------------------------------------------------

EquipmentClass = Literal["CYCLOTRON", "SCANNER", "MRT_CARRIER", "MRT_GUIDEWAY"]
PowerUnit = Literal["kW", "kVA", "kWh"]
"""Section 41A: kW (real power) != kVA (apparent power/electrical service
demand) != kWh (energy) -- never silently converted between these."""
MeasurementType = Literal[
    "RATED_MAXIMUM", "MEASURED_OPERATING", "NAMEPLATE_ELECTRICAL_SERVICE", "UNKNOWN",
    "MAXIMUM_DEMAND", "AVERAGE_ACTIVE_POWER", "IDLE_POWER", "STANDBY_POWER", "OFF_POWER",
    "COMPONENT_RATING", "SERVICE_REQUIREMENT",
]
"""Section 41B/10-11: a rating (RATED_MAXIMUM/MAXIMUM_DEMAND/COMPONENT_RATING/
SERVICE_REQUIREMENT/NAMEPLATE_ELECTRICAL_SERVICE) is never automatically
treated as measured average operating consumption."""
CalibrationStatus = Literal["MANUFACTURER_CALIBRATED", "SITE_CALIBRATED", "NOT_CALIBRATED"]
EquipmentEnergyCalibrationStatus = Literal["CALIBRATED_FOR_ENERGY", "PARTIALLY_CALIBRATED", "NOT_CALIBRATED", "NOT_APPLICABLE"]
EconomicComparabilityStatus = Literal["FULLY_CALIBRATED", "PARTIALLY_CALIBRATED", "NOT_COMPARABLE_DUE_TO_UNCALIBRATED_ENERGY"]

_ENERGY_USABLE_MEASUREMENT_TYPES = frozenset({"MEASURED_OPERATING", "AVERAGE_ACTIVE_POWER", "IDLE_POWER", "STANDBY_POWER", "OFF_POWER"})


def is_energy_usable_measurement(measurement_type: MeasurementType, power_unit: PowerUnit) -> bool:
    """Section 9/15: only a real-power (kW) value whose measurement meaning
    legitimately represents an operating-state consumption (not a rating/
    maximum-demand/service-requirement value, and never kVA without an
    explicit, separately-preserved conversion basis) may contribute to a
    calculated kWh."""
    return power_unit == "kW" and measurement_type in _ENERGY_USABLE_MEASUREMENT_TYPES
ElectricityInclusionStatus = Literal["ELECTRICITY_EXCLUDED", "ELECTRICITY_INCLUDED", "MIXED_OR_UNKNOWN"]

ENERGY_SPECIFICATION_NOT_CALIBRATED = "ENERGY_SPECIFICATION_NOT_CALIBRATED"


@dataclass(frozen=True)
class EquipmentPowerStateSpecification:
    """One documented power value for one named operating state (section 41).
    `operating_state` is a free string because different equipment
    classes/manufacturers publish different, non-universal state vocabularies
    (e.g. cyclotron IRRADIATING/STANDBY vs scanner SCANNING/IDLE) -- never
    invented if undocumented."""

    equipment_class: EquipmentClass
    manufacturer: str
    model: str
    operating_state: str
    power_value: float
    power_unit: PowerUnit
    measurement_type: MeasurementType
    source_document: str
    source_provenance: str
    calibration_status: CalibrationStatus


@dataclass(frozen=True)
class EquipmentIdentityRecord:
    """Attaches manufacturer/model/specification-provenance to an EXISTING
    persistent canonical equipment identity (CY-xxx / SCN-xxx) without
    creating a second catalog or changing that identity's calibrated
    production/scheduling capability (section 39, 74A)."""

    canonical_equipment_id: str
    equipment_class: EquipmentClass
    manufacturer: str = "UNKNOWN"
    model: str = "UNKNOWN"
    specification_provenance: str = "UNKNOWN"
    power_state_specifications: tuple[EquipmentPowerStateSpecification, ...] = ()

    def energy_specification_status(self) -> str:
        """Section 74B: honest NOT_CALIBRATED rather than a fabricated value."""
        if not self.power_state_specifications:
            return ENERGY_SPECIFICATION_NOT_CALIBRATED
        return "; ".join(f"{spec.operating_state}={spec.power_value}{spec.power_unit}({spec.calibration_status})" for spec in self.power_state_specifications)

    def power_state_spec(self, operating_state: str) -> EquipmentPowerStateSpecification | None:
        return next((spec for spec in self.power_state_specifications if spec.operating_state == operating_state), None)


_OPEX_LINE_ELECTRICITY_CLASSIFICATION: Mapping[str, ElectricityInclusionStatus] = {
    # Evidence: infrastructure_opex.py builds these as DISTINCT ENERGY-category
    # ledger lines, separate from the FIXED "Cyclotron annual fixed O&M" line
    # (decision_pipeline.py NativePathwayScenario.cyclotron_annual_opex_per_unit).
    "Cyclotron annual fixed O&M": "ELECTRICITY_EXCLUDED",
    "Scanner energy": "ELECTRICITY_INCLUDED",
    "Cyclotron energy": "ELECTRICITY_INCLUDED",
    "MRT energy": "ELECTRICITY_INCLUDED",
    "Other energy": "ELECTRICITY_INCLUDED",
}


def classify_existing_opex_line_electricity_inclusion(opex_line_name: str) -> ElectricityInclusionStatus:
    """Section 74C/Q1: audits whether a named existing OPEX ledger line
    already contains electricity, so a future schedule-derived energy engine
    does not double-count it. Unrecognized line names are conservatively
    classified MIXED_OR_UNKNOWN rather than assumed excluded."""
    return _OPEX_LINE_ELECTRICITY_CLASSIFICATION.get(opex_line_name, "MIXED_OR_UNKNOWN")

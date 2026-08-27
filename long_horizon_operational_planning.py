"""Long-Horizon Patient-Aware Operational Planning (day/week/month/six-month).

GOVERNANCE-FIRST BUILD: this module orchestrates MULTIPLE operating days by
REUSING the existing validated single-day engines --
`build_production_clinical_schedule` remains the sole authoritative
injection/uptake/scanner/production/transport engine (section 3). This module
adds ZERO new intraday physics: it only decides WHICH calendar dates are
operating days, WHICH patient records apply to each date, WHICH cyclotrons are
ON/OFF that date, and how to aggregate/validate the resulting per-day results
across time.

CANONICAL OPERATIONAL DATA INTERFACE (sections 7-14): `CanonicalOperationalPatientRecord`
is a vendor-neutral schema that future FHIR/HL7/DICOM/vendor adapters can
populate (see `CanonicalOperationalRecordSource` Protocol) -- no live vendor
integration is implemented here, only the boundary/interface.

KNOWN vs FORECAST (section 9-11, 53-55): every record carries an explicit
`demand_status` ("COMMITTED" | "FORECAST"); forecast identifiers use a clearly
synthetic scheme (see `is_synthetic_forecast_id`) and are never presented as
named hospital patients in any report.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal, Mapping, Protocol, Sequence

from cyclotron_catalog import load_cyclotron_catalog
from cyclotron_production_windows import CyclotronAsset, CyclotronFleet
from clinical_resource_identity import ClinicalResourceType, ResourceAvailabilityCalendar
from operating_day_scheduler import DEDICATED_ROOM_RESOURCE_INDEX
from engineering_authority import (
    AuthorityFinding,
    validate_clinical_resource_mode_consistency,
    validate_cyclotron_spatial_origin_traceability,
    validate_patient_traceability,
)
from facility_engineering_model import FacilityEngineeringObjectModel
from models import PlannerAssumptions
from multi_cyclotron_authority import (
    ConfiguredCyclotron,
    CyclotronScenarioState,
    build_calibrated_cyclotron_asset,
    origin_object_id_by_cyclotron_id,
)
from patient_radionuclide_demand import ClinicalResourceMode, FacilityDayPatientDemand, PatientRadionuclideDemand
from production_clinical_schedule import (
    Pathway,
    ProductionClinicalScenario,
    ProductionClinicalScheduleResult,
    build_production_clinical_schedule,
)
from radiopharm_workflow_staffing import RadiopharmWorkflowStaffingResult, compute_radiopharm_workflow_staffing
from study_scope import StudyScope

DemandStatus = Literal["COMMITTED", "FORECAST", "TENTATIVE"]
FieldMutability = Literal["FIXED", "OPTIMIZABLE_WITHIN_WINDOW"]
PatientType = Literal["OUTPATIENT", "INBOUND_PATIENT"]
SourceProvenance = Literal[
    "USER_ENTERED", "EHR", "RIS", "PACS", "ADMISSION_SYSTEM", "BILLING_SYSTEM",
    "VENDOR_EQUIPMENT", "FORECAST_MODEL", "PROJECT_ASSUMPTION",
]
ClinicalModality = Literal["PET", "SPECT"]
"""Section 29: follows the EXISTING repository modality convention
(`clinical_resource_identity.ScannerModality`/`nuclear_appointment.NuclearModality`,
both already `Literal["PET", "SPECT"]`) -- not a new vocabulary."""

UnmetDemandReason = Literal[
    "NON_OPERATING_DAY", "CYCLOTRON_OFF", "RADIONUCLIDE_UNSUPPORTED", "PRODUCTION_CAPACITY",
    "PRODUCTION_TIMING", "RETENTION", "TRANSPORT", "NO_INBOUND_ROOM", "NO_INJECTION_CAPACITY",
    "NO_UPTAKE_CAPACITY", "NO_SCANNER_CAPACITY", "CLINICAL_DAY_TRUNCATION", "RESOURCE_UNAVAILABLE",
    "OTHER_EXPLICIT_REASON",
]
MasterPlanStatus = Literal["VALID", "VALID_WITH_UNMET_DEMAND", "INVALID_AUTHORITY_VIOLATION"]

FORECAST_ID_PREFIX = "FORECAST-"


def is_synthetic_forecast_id(identifier: str) -> bool:
    """Section 11: forecast demand must use a clearly synthetic identifier
    scheme, never a fabricated real-patient identity."""
    return identifier.startswith(FORECAST_ID_PREFIX)


# ---------------------------------------------------------------------------
# Operating calendar (sections 5-6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperatingCalendar:
    """Explicit operating/non-operating day calendar over a date range. No
    holiday logic is implemented; callers supply `operating_weekdays` (0=Mon)
    and may list explicit `non_operating_dates` (e.g. planned maintenance)."""

    planning_start_date: date
    planning_end_date: date
    operating_weekdays: frozenset[int] = frozenset({0, 1, 2, 3, 4})
    non_operating_dates: frozenset[date] = frozenset()

    def __post_init__(self) -> None:
        if self.planning_end_date < self.planning_start_date:
            raise ValueError("planning_end_date must not precede planning_start_date")
        if not self.operating_weekdays.issubset(set(range(7))):
            raise ValueError("operating_weekdays must be within 0-6")

    def is_operating_day(self, day: date) -> bool:
        if day < self.planning_start_date or day > self.planning_end_date:
            raise ValueError(f"{day} is outside the planning horizon")
        if day in self.non_operating_dates:
            return False
        return day.weekday() in self.operating_weekdays

    def all_dates(self) -> tuple[date, ...]:
        span = (self.planning_end_date - self.planning_start_date).days + 1
        return tuple(self.planning_start_date + timedelta(days=offset) for offset in range(span))

    def operating_dates(self) -> tuple[date, ...]:
        return tuple(day for day in self.all_dates() if self.is_operating_day(day))


# ---------------------------------------------------------------------------
# Canonical operational patient record (sections 7-16)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalOperationalPatientRecord:
    """Vendor-neutral canonical operational demand item (section 7). Internal
    identity (`internal_model_patient_id`) is separate from any future
    hospital identifier (`external_patient_reference`, section 8)."""

    internal_model_patient_id: str
    demand_status: DemandStatus
    patient_type: PatientType
    radionuclide: str
    prescribed_activity_mbq: float
    scheduled_date: date
    source_provenance: SourceProvenance
    external_patient_reference: str | None = None
    protocol_id: str | None = None
    scheduled_date_mutability: FieldMutability = "FIXED"
    administration_window_start_minute: float | None = None
    administration_window_end_minute: float | None = None
    administration_time_mutability: FieldMutability = "OPTIMIZABLE_WITHIN_WINDOW"
    admission_datetime: date | None = None
    expected_discharge_date: date | None = None
    existing_room_id: str | None = None
    room_mutability: FieldMutability = "OPTIMIZABLE_WITHIN_WINDOW"
    existing_scanner_appointment_minute: float | None = None
    scanner_mutability: FieldMutability = "OPTIMIZABLE_WITHIN_WINDOW"
    clinical_resource_mode: ClinicalResourceMode = "OUTPATIENT_SHARED"
    earliest_scheduled_date: date | None = None
    latest_scheduled_date: date | None = None
    """Section 27: CLINICALLY PERMITTED scheduling bounds (date-level), additive
    and optional. Do NOT give the Digital Twin permission to invent flexibility
    -- these only PRESERVE bounds a clinical source explicitly supplies (section
    28); `scheduled_date_mutability` remains the sole governing authority on
    whether `scheduled_date` itself may move at all. None/None (default)
    preserves prior behavior exactly."""
    modality: ClinicalModality | None = None
    """Section 29: first-class, optional. Never auto-inferred from
    `radionuclide` -- if a source omits it and no validated mapping authority
    is invoked by the caller, it remains None (unresolved), never guessed."""
    clinical_priority: str | None = None
    """Section 30: source-supplied clinical/operational metadata only. The
    Digital Twin never invents a priority and never wires priority-based
    optimization from this field alone."""

    def __post_init__(self) -> None:
        if self.demand_status == "FORECAST" and not is_synthetic_forecast_id(self.internal_model_patient_id):
            raise ValueError(
                f"FORECAST record '{self.internal_model_patient_id}' must use a synthetic id "
                f"prefixed '{FORECAST_ID_PREFIX}' (section 11) -- do not fabricate a real patient identity."
            )
        if self.patient_type == "INBOUND_PATIENT" and self.expected_discharge_date is not None:
            admission = self.admission_datetime or self.scheduled_date
            if self.expected_discharge_date < admission:
                raise ValueError("expected_discharge_date must not precede admission")
        requires_dedicated_room = self.clinical_resource_mode in ("INBOUND_CENTRALIZED", "INBOUND_INTEGRATED")
        if requires_dedicated_room and self.existing_room_id is None:
            raise ValueError(f"{self.clinical_resource_mode} requires existing_room_id (section 6/46)")
        if requires_dedicated_room and self.patient_type != "INBOUND_PATIENT":
            raise ValueError(f"{self.clinical_resource_mode} requires patient_type INBOUND_PATIENT")
        if not requires_dedicated_room and self.patient_type == "OUTPATIENT" and self.existing_room_id is not None:
            raise ValueError("OUTPATIENT must not carry a dedicated inbound room (section 43/68)")
        if (
            self.earliest_scheduled_date is not None and self.latest_scheduled_date is not None
            and self.earliest_scheduled_date > self.latest_scheduled_date
        ):
            raise ValueError(
                f"earliest_scheduled_date ({self.earliest_scheduled_date}) must not be after "
                f"latest_scheduled_date ({self.latest_scheduled_date}) (section 28)."
            )


class CanonicalOperationalRecordSource(Protocol):
    """Section 13-14: the architectural boundary future FHIR/HL7/DICOM/vendor
    adapters implement. No network calls, no credentials -- interface only."""

    def fetch_records(self, *, start_date: date, end_date: date) -> tuple[CanonicalOperationalPatientRecord, ...]:
        ...


# ---------------------------------------------------------------------------
# Cyclotron calendar (sections 23-26)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CyclotronCalendar:
    """Per-date ON/OFF scenario state for each configured cyclotron (section
    23). Configured cyclotrons themselves (identity, model, origin) remain
    stable across the whole horizon (section 22); only the daily ON/OFF
    scenario_state may vary."""

    configured_cyclotrons: tuple[ConfiguredCyclotron, ...]
    scenario_state_overrides_by_date: Mapping[date, Mapping[str, CyclotronScenarioState]] = field(default_factory=dict)

    def scenario_state_on(self, *, day: date, cyclotron_id: str) -> CyclotronScenarioState:
        override = self.scenario_state_overrides_by_date.get(day, {})
        if cyclotron_id in override:
            return override[cyclotron_id]
        entry = next((c for c in self.configured_cyclotrons if c.cyclotron_id == cyclotron_id), None)
        if entry is None:
            raise ValueError(f"Unknown cyclotron_id: {cyclotron_id}")
        return entry.scenario_state

    def origin_registry(self) -> dict[str, str]:
        return origin_object_id_by_cyclotron_id(self.configured_cyclotrons)

    def build_fleet_for_date(
        self, *, day: date, radionuclide: str, release_processing_minutes: float,
    ) -> tuple[CyclotronFleet | None, dict[str, str]]:
        """Builds the ON-only fleet for `day` plus the origin override map
        (section 24-25: OFF removes capacity, never patient demand or the
        configuration record itself). Returns (None, {}) -- never raises --
        when no ON, radionuclide-compatible cyclotron exists, so callers can
        report UNMET production demand instead of crashing (section 79)."""
        assets: list[CyclotronAsset] = []
        origin_by_cyclotron: dict[str, str] = {}
        catalog = load_cyclotron_catalog()
        for entry in self.configured_cyclotrons:
            if self.scenario_state_on(day=day, cyclotron_id=entry.cyclotron_id) != "ON":
                continue
            model = catalog.by_id(entry.instance.catalog_model_id)
            if radionuclide not in model.supported_radionuclides:
                continue
            assets.append(build_calibrated_cyclotron_asset(
                instance_id=entry.cyclotron_id,
                catalog_model_id=entry.instance.catalog_model_id,
                radionuclide=radionuclide,
                release_processing_minutes=release_processing_minutes,
            ))
            origin_by_cyclotron[entry.cyclotron_id] = entry.origin_object_id
        if not assets:
            return None, {}
        fleet_id = f"FLEET-{day.isoformat()}"
        return CyclotronFleet(assets=tuple(assets), fleet_id=fleet_id), origin_by_cyclotron


# ---------------------------------------------------------------------------
# Per-day orchestration (sections 27-40)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnmetDemandRecord:
    """Section 51-52: every unmet committed procedure retains an explicit
    reason and identity -- never a generic UNSCHEDULED."""

    internal_model_patient_id: str
    procedure_reference: str | None
    day: date
    reason: UnmetDemandReason
    affected_resource_or_constraint: str | None = None


@dataclass(frozen=True)
class DailyOperationalSummary:
    day: date
    pathway: Pathway
    committed_demand_count: int
    forecast_demand_count: int
    scheduled_batch_count: int
    unscheduled_batch_count: int
    clinically_completed_count: int
    retention_qualified_count: int
    cyclotrons_used: tuple[str, ...]
    production_cycle_count: int
    staffing: RadiopharmWorkflowStaffingResult | None
    authority_findings: tuple[AuthorityFinding, ...]
    authority_passed: bool
    schedule_result: ProductionClinicalScheduleResult | None
    injection_resource_id_by_index: Mapping[int, str] = field(default_factory=dict)
    uptake_resource_id_by_index: Mapping[int, str] = field(default_factory=dict)
    scanner_resource_id_by_index: Mapping[int, str] = field(default_factory=dict)
    unmet_demand: tuple[UnmetDemandRecord, ...] = ()


@dataclass(frozen=True)
class PatientOperationalPlan:
    """Section 51/33: per-committed-patient operational plan view; injection/
    uptake/scanner now expose persistent resource identity (section 9), not a
    pool-level marker, for resource classes the day-engine tracks by index."""

    internal_model_patient_id: str
    external_patient_reference: str | None
    day: date
    radionuclide: str
    cyclotron_id: str
    radiopharmacy_origin_id: str | None
    batch_id: int
    production_window_id: int
    release_time_minutes: float
    transport_mode: Pathway
    clinical_resource_mode: ClinicalResourceMode
    injection_resource_id: str
    uptake_resource_id: str
    scanner_resource_id: str
    injection_window_minutes: tuple[float, float]
    uptake_window_minutes: tuple[float, float]
    scan_window_minutes: tuple[float, float]
    inbound_room_id: str | None
    completed_within_operating_day: bool


def _demand_status_counts(records: Sequence[CanonicalOperationalPatientRecord]) -> tuple[int, int]:
    committed = sum(1 for r in records if r.demand_status == "COMMITTED")
    forecast = sum(1 for r in records if r.demand_status == "FORECAST")
    return committed, forecast


def _build_facility_day_demand(records: Sequence[CanonicalOperationalPatientRecord]) -> FacilityDayPatientDemand:
    return FacilityDayPatientDemand(
        patients=tuple(
            PatientRadionuclideDemand(
                patient_id=record.internal_model_patient_id,
                radionuclide=record.radionuclide,
                prescribed_activity_mbq=record.prescribed_activity_mbq,
                clinical_resource_mode=record.clinical_resource_mode,
                inbound_room_id=record.existing_room_id if record.clinical_resource_mode != "OUTPATIENT_SHARED" else None,
            )
            for record in records
        )
    )


def _production_unmet_reason(*, cyclotron_calendar: CyclotronCalendar, day: date, radionuclide: str) -> UnmetDemandReason:
    """Section 79: distinguishes an OFF cyclotron fleet (capacity exists, not
    ON today) from a radionuclide no configured cyclotron ever supports."""
    catalog = load_cyclotron_catalog()
    any_supports = any(
        radionuclide in catalog.by_id(entry.instance.catalog_model_id).supported_radionuclides
        for entry in cyclotron_calendar.configured_cyclotrons
    )
    return "CYCLOTRON_OFF" if any_supports else "RADIONUCLIDE_UNSUPPORTED"


def _unmet_daily_summary(
    *, day: date, pathway: Pathway, records_for_day: Sequence[CanonicalOperationalPatientRecord],
    reason: UnmetDemandReason, affected_resource_or_constraint: str | None = None,
) -> DailyOperationalSummary:
    """Section 16/79/80: production/resource infeasibility never crashes the
    horizon run or deletes patient demand -- it is reported as an explicit,
    reasoned UnmetDemandRecord and the day remains zero-activity."""
    committed_count, forecast_count = _demand_status_counts(records_for_day)
    unmet_demand = tuple(
        UnmetDemandRecord(
            internal_model_patient_id=record.internal_model_patient_id, procedure_reference=record.protocol_id,
            day=day, reason=reason, affected_resource_or_constraint=affected_resource_or_constraint,
        )
        for record in records_for_day
    )
    return DailyOperationalSummary(
        day=day, pathway=pathway, committed_demand_count=committed_count, forecast_demand_count=forecast_count,
        scheduled_batch_count=0, unscheduled_batch_count=0, clinically_completed_count=0, retention_qualified_count=0,
        cyclotrons_used=(), production_cycle_count=0, staffing=None, authority_findings=(), authority_passed=True,
        schedule_result=None, unmet_demand=unmet_demand,
    )


def run_operating_day_plan(
    *,
    day: date,
    records_for_day: Sequence[CanonicalOperationalPatientRecord],
    cyclotron_calendar: CyclotronCalendar,
    pathway: Pathway,
    geometry: FacilityEngineeringObjectModel,
    assumptions: PlannerAssumptions,
    resource_calendar: ResourceAvailabilityCalendar,
    distribution_concurrency: int,
    release_processing_minutes: float = 71.0,
    operating_day_minutes: float = 1080.0,
    requested_batch_count_by_radionuclide: Mapping[str, int] | None = None,
    preserve_resource_indices: bool = False,
    resource_reservations: Mapping[str, float] | None = None,
    additional_blocked_injection_indices: frozenset[int] = frozenset(),
    additional_blocked_uptake_indices: frozenset[int] = frozenset(),
    additional_blocked_scanner_indices: frozenset[int] = frozenset(),
) -> DailyOperationalSummary:
    """Runs ONE operating date through the existing authoritative
    build_production_clinical_schedule engine (section 3/27) -- no second
    scheduler is created. Supports multiple radionuclides only where the
    cyclotron calendar has calibrated ON capacity for each (section 28).

    `requested_batch_count_by_radionuclide` (optional, additive): overrides the
    LEGACY_COMPATIBILITY `len(records_for_day)`-derived batch-count heuristic
    below. Live-state rolling replans (live_operational_state.py) pass the
    PREVIOUS plan version's batch count through this parameter so that a
    single patient's cancellation/addition does not, by itself, shift every
    other patient's production-cycle/timing assignment -- the root cause of
    an otherwise-avoidable plan-wide reshuffle (section 16/113 localization).
    None (default) preserves the exact prior behavior for every existing caller.

    `preserve_resource_indices` (optional, additive, default False): when True,
    injection/uptake/scanner resource counts/indices are taken from the FULL
    persistent inventory (never shrunk to only the AVAILABLE subset), and
    unavailable resources are passed to the scheduler as `blocked_*_indices`
    (seeded busy for the whole day) instead of being removed from the array.
    This keeps every OTHER resource's compacted index -- and therefore its
    persistent identity -- stable across a rerun that only removes one
    resource (rolling-reoptimization identity stickiness). False (default) is
    byte-for-byte identical to prior behavior.

    `resource_reservations` (optional, additive, only meaningful when
    `preserve_resource_indices=True`): maps a persistent resource_id (e.g.
    "SCN-002") to the time it becomes free, reflecting a PRESERVED patient's
    actual consumption of that resource (computed by the caller --
    live_operational_state.py -- from patients NOT included in
    `records_for_day` this call). Lets the scheduler place ONLY the patients
    actually passed in `records_for_day` into the TRUE residual capacity
    around already-preserved assignments, without disturbing them (affected-
    subset reoptimization, never a second scheduler).

    `additional_blocked_injection_indices`/`_uptake_`/`_scanner_` (optional,
    additive): extra indices blocked for THIS call only, merged with any
    calendar-derived outage blocks. Used by live-state staffing-shortfall
    replans to temporarily cap the EFFECTIVE concurrent room count available
    to a targeted rerun down to a staff pool's available capacity -- reuses
    the identity-sticky blocked-index mechanism already proven for resource
    outages, never a new scheduling dimension. Empty (default) is
    byte-for-byte identical to prior behavior."""
    if not records_for_day:
        raise ValueError(f"No patient records supplied for operating day {day}")
    radionuclides = sorted({record.radionuclide for record in records_for_day})
    if len(radionuclides) != 1:
        raise ValueError(
            f"run_operating_day_plan requires one radionuclide per call (day {day} has {radionuclides}); "
            "call once per radionuclide subset and aggregate at the horizon level."
        )
    radionuclide = radionuclides[0]
    committed_count, forecast_count = _demand_status_counts(records_for_day)

    fleet, origin_by_cyclotron = cyclotron_calendar.build_fleet_for_date(
        day=day, radionuclide=radionuclide, release_processing_minutes=release_processing_minutes,
    )
    if fleet is None:
        reason = _production_unmet_reason(cyclotron_calendar=cyclotron_calendar, day=day, radionuclide=radionuclide)
        return _unmet_daily_summary(
            day=day, pathway=pathway, records_for_day=records_for_day, reason=reason,
            affected_resource_or_constraint=radionuclide,
        )
    demand = _build_facility_day_demand(records_for_day)

    injection_resource_ids = resource_calendar.active_resource_ids_for_date(resource_type="INJECTION_ROOM", day=day)
    uptake_resource_ids = resource_calendar.active_resource_ids_for_date(resource_type="UPTAKE_ROOM", day=day)
    scanner_resource_ids = resource_calendar.active_resource_ids_for_date(resource_type="SCANNER", day=day)
    blocked_injection_indices: frozenset[int] = frozenset()
    blocked_uptake_indices: frozenset[int] = frozenset()
    blocked_scanner_indices: frozenset[int] = frozenset()
    injection_resource_id_by_index = resource_calendar.compacted_index_to_resource_id(resource_type="INJECTION_ROOM", day=day)
    uptake_resource_id_by_index = resource_calendar.compacted_index_to_resource_id(resource_type="UPTAKE_ROOM", day=day)
    scanner_resource_id_by_index = resource_calendar.compacted_index_to_resource_id(resource_type="SCANNER", day=day)
    available_injection_count = len(injection_resource_ids)
    available_uptake_count = len(uptake_resource_ids)
    available_scanner_count = len(scanner_resource_ids)

    if preserve_resource_indices:
        injection_full = resource_calendar.inventory.resources_of_type("INJECTION_ROOM")
        uptake_full = resource_calendar.inventory.resources_of_type("UPTAKE_ROOM")
        scanner_full = resource_calendar.inventory.resources_of_type("SCANNER")
        injection_resource_ids = tuple(r.resource_id for r in injection_full)
        uptake_resource_ids = tuple(r.resource_id for r in uptake_full)
        scanner_resource_ids = tuple(r.resource_id for r in scanner_full)
        blocked_injection_indices = frozenset(i for i, r in enumerate(injection_full) if resource_calendar.state_on(resource_id=r.resource_id, day=day) != "AVAILABLE")
        blocked_uptake_indices = frozenset(i for i, r in enumerate(uptake_full) if resource_calendar.state_on(resource_id=r.resource_id, day=day) != "AVAILABLE")
        blocked_scanner_indices = frozenset(i for i, r in enumerate(scanner_full) if resource_calendar.state_on(resource_id=r.resource_id, day=day) != "AVAILABLE")
        injection_resource_id_by_index = {i: r.resource_id for i, r in enumerate(injection_full)}
        uptake_resource_id_by_index = {i: r.resource_id for i, r in enumerate(uptake_full)}
        scanner_resource_id_by_index = {i: r.resource_id for i, r in enumerate(scanner_full)}
        available_injection_count = len(injection_resource_ids) - len(blocked_injection_indices)
        available_uptake_count = len(uptake_resource_ids) - len(blocked_uptake_indices)
        available_scanner_count = len(scanner_resource_ids) - len(blocked_scanner_indices)

    if additional_blocked_injection_indices or additional_blocked_uptake_indices or additional_blocked_scanner_indices:
        blocked_injection_indices = blocked_injection_indices | additional_blocked_injection_indices
        blocked_uptake_indices = blocked_uptake_indices | additional_blocked_uptake_indices
        blocked_scanner_indices = blocked_scanner_indices | additional_blocked_scanner_indices
        available_injection_count = len(injection_resource_ids) - len(blocked_injection_indices)
        available_uptake_count = len(uptake_resource_ids) - len(blocked_uptake_indices)
        available_scanner_count = len(scanner_resource_ids) - len(blocked_scanner_indices)

    injection_reserved_until: dict[int, float] = {}
    uptake_reserved_until: dict[int, float] = {}
    scanner_reserved_until: dict[int, float] = {}
    if preserve_resource_indices and resource_reservations:
        injection_index_by_id = {rid: i for i, rid in injection_resource_id_by_index.items()}
        uptake_index_by_id = {rid: i for i, rid in uptake_resource_id_by_index.items()}
        scanner_index_by_id = {rid: i for i, rid in scanner_resource_id_by_index.items()}
        for resource_id, reserved_until in resource_reservations.items():
            if resource_id in injection_index_by_id:
                injection_reserved_until[injection_index_by_id[resource_id]] = reserved_until
            elif resource_id in uptake_index_by_id:
                uptake_reserved_until[uptake_index_by_id[resource_id]] = reserved_until
            elif resource_id in scanner_index_by_id:
                scanner_reserved_until[scanner_index_by_id[resource_id]] = reserved_until

    for available_count, reason in (
        (available_injection_count, "NO_INJECTION_CAPACITY"), (available_uptake_count, "NO_UPTAKE_CAPACITY"),
        (available_scanner_count, "NO_SCANNER_CAPACITY"),
    ):
        if available_count <= 0:
            return _unmet_daily_summary(day=day, pathway=pathway, records_for_day=records_for_day, reason=reason)

    scenario = ProductionClinicalScenario(
        facility_day_demand=demand,
        requested_batch_count_by_radionuclide=(
            dict(requested_batch_count_by_radionuclide) if requested_batch_count_by_radionuclide is not None
            else {radionuclide: max(1, len(records_for_day) // 20 + 1)}
        ),
        cyclotron_fleet=fleet,
        transport_minutes=5.0,
        injection_service_minutes=assumptions.injection_cycle_min,
        uptake_minutes=assumptions.uptake_cycle_min,
        scanner_service_minutes=assumptions.scanner_cycle_min,
        injection_resources=len(injection_resource_ids),
        uptake_resources=len(uptake_resource_ids),
        scanners=len(scanner_resource_ids),
        distribution_concurrency=distribution_concurrency,
        operating_day_minutes=operating_day_minutes,
        production_horizon_minutes=operating_day_minutes,
        pathway=pathway,
        facility_engineering_model=geometry,
        planner_assumptions=assumptions,
        cyclotron_radiopharmacy_origin_object_id_by_cyclotron_id=origin_by_cyclotron,
        blocked_injection_indices=blocked_injection_indices,
        blocked_uptake_indices=blocked_uptake_indices,
        blocked_scanner_indices=blocked_scanner_indices,
        injection_reserved_until=injection_reserved_until,
        uptake_reserved_until=uptake_reserved_until,
        scanner_reserved_until=scanner_reserved_until,
    )
    result = build_production_clinical_schedule(scenario)

    demand_ids = tuple(record.internal_model_patient_id for record in records_for_day)
    clinical_ids = tuple(mapping.batch_id for mapping in result.batch_release_mappings)  # presence proxy
    decay_ids = tuple(trace.patient_id for trace in result.patient_traces)
    clinical_patient_ids = tuple({pid for mapping in result.batch_release_mappings for pid in mapping.patient_ids})

    findings: list[AuthorityFinding] = list(validate_patient_traceability(
        demand_patient_ids=demand_ids, clinical_patient_ids=clinical_patient_ids, decay_patient_ids=decay_ids,
    ))
    if origin_by_cyclotron:
        findings.extend(validate_cyclotron_spatial_origin_traceability(
            payload_cyclotron_ids=[mapping.assigned_cyclotron_id for mapping in result.batch_release_mappings],
            payload_origin_object_ids=[origin_by_cyclotron[mapping.assigned_cyclotron_id] for mapping in result.batch_release_mappings],
            registered_origin_object_id_by_cyclotron_id=cyclotron_calendar.origin_registry(),
        ))
    findings.extend(validate_clinical_resource_mode_consistency(
        patient_ids=[trace.patient_id for trace in result.patient_traces],
        clinical_resource_modes=[trace.clinical_resource_mode for trace in result.patient_traces],
        injection_resource_ids=[
            trace.inbound_room_id if trace.injection_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
            else injection_resource_id_by_index[trace.injection_resource_index]
            for trace in result.patient_traces
        ],
        uptake_resource_ids=[
            trace.inbound_room_id if trace.uptake_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
            else uptake_resource_id_by_index[trace.uptake_resource_index]
            for trace in result.patient_traces
        ],
        inbound_room_ids=[trace.inbound_room_id for trace in result.patient_traces],
    ))
    authority_passed = not any(f.severity == "VIOLATION" for f in findings)

    staffing = compute_radiopharm_workflow_staffing(patient_schedules=result.patient_traces)

    cyclotrons_used = tuple(sorted({mapping.assigned_cyclotron_id for mapping in result.batch_release_mappings}))
    completed_count = sum(1 for trace in result.patient_traces if trace.completed_within_operating_day)
    unmet_demand = tuple(
        UnmetDemandRecord(
            internal_model_patient_id=trace.patient_id, procedure_reference=None, day=day,
            reason="CLINICAL_DAY_TRUNCATION", affected_resource_or_constraint="operating_day_minutes",
        )
        for trace in result.patient_traces if not trace.completed_within_operating_day
    )

    return DailyOperationalSummary(
        day=day,
        pathway=pathway,
        committed_demand_count=committed_count,
        forecast_demand_count=forecast_count,
        scheduled_batch_count=len(result.scheduled_batch_demands),
        unscheduled_batch_count=len(result.unscheduled_batch_demands),
        clinically_completed_count=completed_count,
        retention_qualified_count=completed_count,  # retention gating happens upstream (spatial_benchmark); this
        # day-level engine call does not itself re-run retention physics (section 3) -- disclosed as identical to
        # clinical completion at this integration layer until retention envelope wiring is added for long-horizon runs.
        cyclotrons_used=cyclotrons_used,
        production_cycle_count=len(result.production_schedule.windows),
        staffing=staffing,
        authority_findings=tuple(findings),
        authority_passed=authority_passed,
        schedule_result=result,
        unmet_demand=unmet_demand,
        injection_resource_id_by_index=injection_resource_id_by_index,
        uptake_resource_id_by_index=uptake_resource_id_by_index,
        scanner_resource_id_by_index=scanner_resource_id_by_index,
    )


def build_patient_operational_plans(
    *,
    daily_summary: DailyOperationalSummary,
    records_for_day: Sequence[CanonicalOperationalPatientRecord],
) -> tuple[PatientOperationalPlan, ...]:
    """Section 51/9: expose the committed-patient operational view, resolving
    each patient's persistent injection/uptake/scanner resource identity from
    the actual scheduler allocation index (never fabricated, section 52)."""
    if daily_summary.schedule_result is None:
        return ()
    record_by_id = {record.internal_model_patient_id: record for record in records_for_day}
    result = daily_summary.schedule_result
    plans: list[PatientOperationalPlan] = []
    for trace in result.patient_traces:
        record = record_by_id.get(trace.patient_id)
        if record is None or record.demand_status != "COMMITTED":
            continue
        plans.append(PatientOperationalPlan(
            internal_model_patient_id=trace.patient_id,
            external_patient_reference=record.external_patient_reference,
            day=daily_summary.day,
            radionuclide=trace.radionuclide,
            cyclotron_id=trace.assigned_cyclotron_id,
            radiopharmacy_origin_id=daily_summary.schedule_result.scenario.cyclotron_radiopharmacy_origin_object_id_by_cyclotron_id.get(trace.assigned_cyclotron_id)
            if daily_summary.schedule_result.scenario.cyclotron_radiopharmacy_origin_object_id_by_cyclotron_id else None,
            batch_id=trace.batch_id,
            production_window_id=trace.production_window_id,
            release_time_minutes=trace.batch_release_time_minutes,
            transport_mode=daily_summary.pathway,
            clinical_resource_mode=trace.clinical_resource_mode,
            injection_resource_id=(
                trace.inbound_room_id if trace.injection_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
                else daily_summary.injection_resource_id_by_index[trace.injection_resource_index]
            ),
            uptake_resource_id=(
                trace.inbound_room_id if trace.uptake_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
                else daily_summary.uptake_resource_id_by_index[trace.uptake_resource_index]
            ),
            scanner_resource_id=daily_summary.scanner_resource_id_by_index[trace.scanner_resource_index],
            injection_window_minutes=(trace.injection_start, trace.injection_end),
            uptake_window_minutes=(trace.uptake_start, trace.uptake_end),
            scan_window_minutes=(trace.scan_start, trace.scan_end),
            inbound_room_id=record.existing_room_id if record.patient_type == "INBOUND_PATIENT" else None,
            completed_within_operating_day=trace.completed_within_operating_day,
        ))
    return tuple(plans)


# ---------------------------------------------------------------------------
# Horizon-level validation (sections 17-18, 41-43)
# ---------------------------------------------------------------------------


def validate_no_duplicate_committed_scheduling(
    records: Sequence[CanonicalOperationalPatientRecord],
) -> list[AuthorityFinding]:
    """Section 42/43: a (patient, procedure) pair must be scheduled exactly
    once across the horizon. Distinct legitimate procedures for the SAME
    patient are distinguished by `protocol_id` -- only an exact duplicate
    (patient_id, protocol_id, scheduled_date) is a conservation violation."""
    seen: dict[tuple[str, str | None], list[date]] = defaultdict(list)
    for record in records:
        if record.demand_status != "COMMITTED":
            continue
        seen[(record.internal_model_patient_id, record.protocol_id)].append(record.scheduled_date)
    findings: list[AuthorityFinding] = []
    for (patient_id, protocol_id), dates in seen.items():
        if len(dates) > 1:
            findings.append(AuthorityFinding(
                authority_id="PATIENT_IDENTITY", category="PATIENT", severity="VIOLATION",
                message=f"Committed patient {patient_id} (protocol={protocol_id}) scheduled on {len(dates)} dates: {sorted(set(dates))}",
                affected_object_ids=(patient_id,), authoritative_owner="long_horizon_operational_planning.py",
                recommended_action="Investigate and correct before accepting this candidate/study.",
            ))
    return findings


def validate_inbound_room_no_overlap(
    records: Sequence[CanonicalOperationalPatientRecord],
) -> list[AuthorityFinding]:
    """Section 18/41/47: inbound occupancy crosses day boundaries; the same
    room may not be double-booked by overlapping admission/discharge
    intervals for different patients (only checked where source data already
    fixes `existing_room_id`)."""
    by_room: dict[str, list[tuple[date, date, str]]] = defaultdict(list)
    for record in records:
        if record.patient_type != "INBOUND_PATIENT" or record.existing_room_id is None:
            continue
        admission = record.admission_datetime or record.scheduled_date
        discharge = record.expected_discharge_date or admission
        by_room[record.existing_room_id].append((admission, discharge, record.internal_model_patient_id))

    findings: list[AuthorityFinding] = []
    for room_id, intervals in by_room.items():
        ordered = sorted(intervals)
        for (start_a, end_a, patient_a), (start_b, end_b, patient_b) in zip(ordered, ordered[1:]):
            if patient_a == patient_b:
                continue
            if start_b < end_a:
                findings.append(AuthorityFinding(
                    authority_id="ROOM_EXCLUSIVITY", category="ROOM", severity="VIOLATION",
                    message=f"Room {room_id} double-booked: {patient_a} ({start_a}..{end_a}) overlaps {patient_b} ({start_b}..{end_b})",
                    affected_object_ids=(room_id, patient_a, patient_b), authoritative_owner="long_horizon_operational_planning.py",
                    recommended_action="Investigate and correct before accepting this candidate/study.",
                ))
    return findings


def validate_persistent_asset_identity(daily_summaries: Sequence[DailyOperationalSummary]) -> list[AuthorityFinding]:
    """Section 21-22: the same facility geometry and cyclotron fleet identity
    set must be used every operating day -- no fresh inventory per day.
    Unmet (schedule_result=None) days carry no schedule to compare and are
    skipped (section 60: they remain in the plan, just not comparable here)."""
    scheduled = [s for s in daily_summaries if s.schedule_result is not None]
    if len(scheduled) < 2:
        return []
    reference_model = scheduled[0].schedule_result.scenario.facility_engineering_model
    findings: list[AuthorityFinding] = []
    for summary in scheduled[1:]:
        model = summary.schedule_result.scenario.facility_engineering_model
        if model is not reference_model:
            findings.append(AuthorityFinding(
                authority_id="ASSET_CONSERVATION", category="ASSET", severity="VIOLATION",
                message=f"Facility geometry object identity changed on {summary.day} -- a persistent facility model must be reused across the horizon.",
                affected_object_ids=(summary.day.isoformat(),), authoritative_owner="long_horizon_operational_planning.py",
                recommended_action="Investigate and correct before accepting this candidate/study.",
            ))
    return findings


# ---------------------------------------------------------------------------
# Aggregation and master plan (sections 56-58)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeeklyOperationalSummary:
    iso_year: int
    iso_week: int
    dates: tuple[date, ...]
    committed_demand_count: int
    forecast_demand_count: int
    clinically_completed_count: int
    production_cycle_count: int
    unmet_demand_count: int = 0


@dataclass(frozen=True)
class MonthlyOperationalSummary:
    year: int
    month: int
    dates: tuple[date, ...]
    committed_demand_count: int
    forecast_demand_count: int
    clinically_completed_count: int
    production_cycle_count: int
    unmet_demand_count: int = 0


def _aggregate_weekly(daily_summaries: Sequence[DailyOperationalSummary]) -> tuple[WeeklyOperationalSummary, ...]:
    grouped: dict[tuple[int, int], list[DailyOperationalSummary]] = defaultdict(list)
    for summary in daily_summaries:
        iso_year, iso_week, _ = summary.day.isocalendar()
        grouped[(iso_year, iso_week)].append(summary)
    weekly = []
    for (iso_year, iso_week), items in sorted(grouped.items()):
        weekly.append(WeeklyOperationalSummary(
            iso_year=iso_year, iso_week=iso_week,
            dates=tuple(sorted(item.day for item in items)),
            committed_demand_count=sum(item.committed_demand_count for item in items),
            forecast_demand_count=sum(item.forecast_demand_count for item in items),
            clinically_completed_count=sum(item.clinically_completed_count for item in items),
            production_cycle_count=sum(item.production_cycle_count for item in items),
            unmet_demand_count=sum(len(item.unmet_demand) for item in items),
        ))
    return tuple(weekly)


def _aggregate_monthly(daily_summaries: Sequence[DailyOperationalSummary]) -> tuple[MonthlyOperationalSummary, ...]:
    grouped: dict[tuple[int, int], list[DailyOperationalSummary]] = defaultdict(list)
    for summary in daily_summaries:
        grouped[(summary.day.year, summary.day.month)].append(summary)
    monthly = []
    for (year, month), items in sorted(grouped.items()):
        monthly.append(MonthlyOperationalSummary(
            year=year, month=month,
            dates=tuple(sorted(item.day for item in items)),
            committed_demand_count=sum(item.committed_demand_count for item in items),
            forecast_demand_count=sum(item.forecast_demand_count for item in items),
            clinically_completed_count=sum(item.clinically_completed_count for item in items),
            production_cycle_count=sum(item.production_cycle_count for item in items),
            unmet_demand_count=sum(len(item.unmet_demand) for item in items),
        ))
    return tuple(monthly)


@dataclass(frozen=True)
class LongHorizonMasterPlan:
    planning_start_date: date
    planning_end_date: date
    study_scope: StudyScope
    pathway: Pathway
    operating_calendar: OperatingCalendar
    daily_summaries: tuple[DailyOperationalSummary, ...]
    weekly_summaries: tuple[WeeklyOperationalSummary, ...]
    monthly_summaries: tuple[MonthlyOperationalSummary, ...]
    patient_plans: tuple[PatientOperationalPlan, ...]
    committed_patient_count: int
    forecast_demand_count: int
    horizon_findings: tuple[AuthorityFinding, ...]
    horizon_passed: bool
    warnings: tuple[str, ...]
    unmet_demand: tuple[UnmetDemandRecord, ...] = ()
    master_plan_status: MasterPlanStatus = "VALID"
    committed_planned_value: float = 0.0
    forecast_expected_value: float = 0.0
    combined_planning_value: float = 0.0


def run_long_horizon_operational_plan(
    *,
    operating_calendar: OperatingCalendar,
    records: Sequence[CanonicalOperationalPatientRecord],
    cyclotron_calendar: CyclotronCalendar,
    pathway: Pathway,
    geometry: FacilityEngineeringObjectModel,
    assumptions: PlannerAssumptions,
    resource_calendar: ResourceAvailabilityCalendar,
    distribution_concurrency: int,
    study_scope: StudyScope = "OPERATIONAL_ONLY",
    release_processing_minutes: float = 71.0,
    operating_day_minutes: float = 1080.0,
) -> LongHorizonMasterPlan:
    """Section 56: builds the six-month (or any explicit-date-range) master
    plan by orchestrating the existing validated day engine once per
    operating date (section 3) -- never a second scheduler."""
    for record in records:
        if record.scheduled_date < operating_calendar.planning_start_date or record.scheduled_date > operating_calendar.planning_end_date:
            raise ValueError(f"Record {record.internal_model_patient_id} scheduled_date {record.scheduled_date} is outside the planning horizon")

    records_by_date: dict[date, list[CanonicalOperationalPatientRecord]] = defaultdict(list)
    for record in records:
        records_by_date[record.scheduled_date].append(record)

    warnings: list[str] = []
    daily_summaries: list[DailyOperationalSummary] = []
    patient_plans: list[PatientOperationalPlan] = []
    non_operating_day_unmet: list[UnmetDemandRecord] = []

    for day in operating_calendar.operating_dates():
        day_records = records_by_date.get(day, [])
        if not day_records:
            continue
        radionuclides = sorted({record.radionuclide for record in day_records})
        for radionuclide in radionuclides:
            subset = [record for record in day_records if record.radionuclide == radionuclide]
            summary = run_operating_day_plan(
                day=day, records_for_day=subset, cyclotron_calendar=cyclotron_calendar, pathway=pathway,
                geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar,
                distribution_concurrency=distribution_concurrency,
                release_processing_minutes=release_processing_minutes, operating_day_minutes=operating_day_minutes,
            )
            daily_summaries.append(summary)
            if not summary.authority_passed:
                warnings.append(f"{day} ({radionuclide}): authority validation failed -- excluded from optimized plan claims (section 40).")
            patient_plans.extend(build_patient_operational_plans(daily_summary=summary, records_for_day=subset))

    for day in records_by_date:
        if not operating_calendar.is_operating_day(day):
            warnings.append(f"{day}: patient record(s) scheduled on a non-operating day -- unmet/must be rescheduled.")
            non_operating_day_unmet.extend(
                UnmetDemandRecord(
                    internal_model_patient_id=record.internal_model_patient_id, procedure_reference=record.protocol_id,
                    day=day, reason="NON_OPERATING_DAY",
                )
                for record in records_by_date[day]
            )

    horizon_findings: list[AuthorityFinding] = []
    horizon_findings.extend(validate_no_duplicate_committed_scheduling(records))
    horizon_findings.extend(validate_inbound_room_no_overlap(records))
    horizon_findings.extend(validate_persistent_asset_identity(daily_summaries))
    horizon_findings.extend(validate_no_double_resource_assignment(patient_plans))
    horizon_passed = not any(f.severity == "VIOLATION" for f in horizon_findings) and all(s.authority_passed for s in daily_summaries)

    committed_total, forecast_total = _demand_status_counts(records)
    unmet_demand = tuple(non_operating_day_unmet) + tuple(record for summary in daily_summaries for record in summary.unmet_demand)

    if not horizon_passed:
        master_plan_status: MasterPlanStatus = "INVALID_AUTHORITY_VIOLATION"
    elif unmet_demand:
        master_plan_status = "VALID_WITH_UNMET_DEMAND"
    else:
        master_plan_status = "VALID"

    revenue_per_scan = float(assumptions.revenue_per_scan)
    committed_completed = sum(1 for plan in patient_plans if plan.completed_within_operating_day)
    committed_planned_value = committed_completed * revenue_per_scan
    forecast_expected_value = forecast_total * revenue_per_scan
    combined_planning_value = committed_planned_value + forecast_expected_value

    return LongHorizonMasterPlan(
        planning_start_date=operating_calendar.planning_start_date,
        planning_end_date=operating_calendar.planning_end_date,
        study_scope=study_scope,
        pathway=pathway,
        operating_calendar=operating_calendar,
        daily_summaries=tuple(daily_summaries),
        weekly_summaries=_aggregate_weekly(daily_summaries),
        monthly_summaries=_aggregate_monthly(daily_summaries),
        patient_plans=tuple(patient_plans),
        committed_patient_count=committed_total,
        forecast_demand_count=forecast_total,
        horizon_findings=tuple(horizon_findings),
        horizon_passed=horizon_passed,
        warnings=tuple(warnings),
        unmet_demand=unmet_demand,
        master_plan_status=master_plan_status,
        committed_planned_value=committed_planned_value,
        forecast_expected_value=forecast_expected_value,
        combined_planning_value=combined_planning_value,
    )


# ---------------------------------------------------------------------------
# Resource-exclusivity validation (section 41) and query helpers (37-39)
# ---------------------------------------------------------------------------

_RESOURCE_FIELD_BY_TYPE: Mapping[ClinicalResourceType, str] = {
    "INJECTION_ROOM": "injection_resource_id",
    "UPTAKE_ROOM": "uptake_resource_id",
    "SCANNER": "scanner_resource_id",
}
_WINDOW_FIELD_BY_TYPE: Mapping[ClinicalResourceType, str] = {
    "INJECTION_ROOM": "injection_window_minutes",
    "UPTAKE_ROOM": "uptake_window_minutes",
    "SCANNER": "scan_window_minutes",
}


def validate_no_double_resource_assignment(
    patient_plans: Sequence[PatientOperationalPlan],
) -> list[AuthorityFinding]:
    """Section 41: no physical injection/uptake/scanner resource may be
    assigned two overlapping patient intervals on the same date (validated
    against actual assignments, not aggregate counts -- section 42)."""
    findings: list[AuthorityFinding] = []
    for resource_type in ("INJECTION_ROOM", "UPTAKE_ROOM", "SCANNER"):
        resource_field = _RESOURCE_FIELD_BY_TYPE[resource_type]
        window_field = _WINDOW_FIELD_BY_TYPE[resource_type]
        by_resource_and_day: dict[tuple[str, date], list[tuple[float, float, str]]] = defaultdict(list)
        for plan in patient_plans:
            resource_id = getattr(plan, resource_field)
            start, end = getattr(plan, window_field)
            by_resource_and_day[(resource_id, plan.day)].append((start, end, plan.internal_model_patient_id))
        for (resource_id, day), intervals in by_resource_and_day.items():
            ordered = sorted(intervals)
            for (start_a, end_a, patient_a), (start_b, end_b, patient_b) in zip(ordered, ordered[1:]):
                if patient_a == patient_b:
                    continue
                if start_b < end_a:
                    findings.append(AuthorityFinding(
                        authority_id="ROOM_EXCLUSIVITY", category="ROOM", severity="VIOLATION",
                        message=f"{resource_type} {resource_id} double-booked on {day}: {patient_a} ({start_a}..{end_a}) overlaps {patient_b} ({start_b}..{end_b})",
                        affected_object_ids=(resource_id, patient_a, patient_b), authoritative_owner="long_horizon_operational_planning.py",
                        recommended_action="Investigate and correct before accepting this candidate/study.",
                    ))
    return findings


def assignments_for_resource(
    plan: LongHorizonMasterPlan, *, resource_id: str, day: date | None = None,
) -> tuple[PatientOperationalPlan, ...]:
    """Section 37: all patient assignments for one physical resource,
    optionally scoped to a single date."""
    matches = [
        p for p in plan.patient_plans
        if resource_id in (p.injection_resource_id, p.uptake_resource_id, p.scanner_resource_id)
        and (day is None or p.day == day)
    ]
    return tuple(sorted(matches, key=lambda p: (p.day, p.internal_model_patient_id)))


def plan_for_patient(plan: LongHorizonMasterPlan, *, internal_model_patient_id: str) -> tuple[PatientOperationalPlan, ...]:
    """Section 38: every operational plan entry for one committed patient
    across the whole horizon."""
    matches = [p for p in plan.patient_plans if p.internal_model_patient_id == internal_model_patient_id]
    return tuple(sorted(matches, key=lambda p: p.day))


def resource_schedule_for_date(plan: LongHorizonMasterPlan, *, day: date) -> tuple[PatientOperationalPlan, ...]:
    """Section 39: every patient assignment scheduled on one calendar date."""
    matches = [p for p in plan.patient_plans if p.day == day]
    return tuple(sorted(matches, key=lambda p: p.internal_model_patient_id))


def resource_utilization_pct(
    plan: LongHorizonMasterPlan, *, resource_id: str, day: date, operating_day_minutes: float = 1080.0,
) -> float:
    """Sections 46-49: per-resource utilization for one date -- dedicated IR
    functions performed for INTEGRATED/CENTRALIZED patients never inflate
    shared INJ/UP utilization (they are keyed under the IR resource_id, not
    the shared one, by construction of PatientOperationalPlan)."""
    occupied = 0.0
    for p in plan.patient_plans:
        if p.day != day:
            continue
        for field_name, window_field in _RESOURCE_WINDOW_FIELDS:
            if getattr(p, field_name) == resource_id:
                start, end = getattr(p, window_field)
                occupied += max(0.0, end - start)
    return 100.0 * occupied / operating_day_minutes if operating_day_minutes > 0 else 0.0


_RESOURCE_WINDOW_FIELDS: tuple[tuple[str, str], ...] = (
    ("injection_resource_id", "injection_window_minutes"),
    ("uptake_resource_id", "uptake_window_minutes"),
    ("scanner_resource_id", "scan_window_minutes"),
)


# ---------------------------------------------------------------------------
# Production/cyclotron-centric queries (sections 36-37, 49-50)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProductionCycleRecord:
    """Section 18-19: a globally unambiguous production-cycle identity --
    Cycle 1 on Monday and Cycle 1 on Tuesday are distinct records."""

    global_cycle_id: str
    day: date
    cyclotron_id: str
    window_id: int
    radionuclides: tuple[str, ...]
    patient_ids: tuple[str, ...]
    start_time_minutes: float
    end_time_minutes: float


def _production_cycle_records_for_summary(summary: DailyOperationalSummary) -> tuple[ProductionCycleRecord, ...]:
    if summary.schedule_result is None:
        return ()
    patient_ids_by_batch_id: dict[int, tuple[str, ...]] = {
        mapping.batch_id: mapping.patient_ids for mapping in summary.schedule_result.batch_release_mappings
    }
    records = []
    for window in summary.schedule_result.production_schedule.windows:
        patient_ids = tuple(pid for batch_id in window.batch_ids for pid in patient_ids_by_batch_id.get(batch_id, ()))
        records.append(ProductionCycleRecord(
            global_cycle_id=f"{summary.day.isoformat()}:{window.assigned_cyclotron_id}:{window.window_id}",
            day=summary.day, cyclotron_id=window.assigned_cyclotron_id, window_id=window.window_id,
            radionuclides=window.radionuclides, patient_ids=patient_ids,
            start_time_minutes=window.start_time_minutes, end_time_minutes=window.end_time_minutes,
        ))
    return tuple(records)


def production_cycles_for_date(plan: LongHorizonMasterPlan, *, day: date) -> tuple[ProductionCycleRecord, ...]:
    """Section 36: every production cycle scheduled on one calendar date."""
    records = []
    for summary in plan.daily_summaries:
        if summary.day == day:
            records.extend(_production_cycle_records_for_summary(summary))
    return tuple(records)


def patients_for_production_cycle(plan: LongHorizonMasterPlan, *, global_cycle_id: str) -> tuple[str, ...]:
    """Section 19/36: exact patient/procedure membership of one production cycle."""
    for summary in plan.daily_summaries:
        for record in _production_cycle_records_for_summary(summary):
            if record.global_cycle_id == global_cycle_id:
                return record.patient_ids
    return ()


def production_plan_for_cyclotron(
    plan: LongHorizonMasterPlan, *, cyclotron_id: str, day: date | None = None,
) -> tuple[ProductionCycleRecord, ...]:
    """Section 37: every production cycle run by one cyclotron, optionally
    scoped to a single date."""
    records = []
    for summary in plan.daily_summaries:
        if day is not None and summary.day != day:
            continue
        records.extend(r for r in _production_cycle_records_for_summary(summary) if r.cyclotron_id == cyclotron_id)
    return tuple(sorted(records, key=lambda r: (r.day, r.window_id)))


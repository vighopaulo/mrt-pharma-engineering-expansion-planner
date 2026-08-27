"""Patient-Aware General Oncology Logistics Foundation.

GOVERNING PRINCIPLE (section 1): general logistics uses the SAME persistent
oncology patient population already established by the nuclear model
(`oncology_pet_spect_scenario.OncologyPatientRecord`/
`build_representative_day_population`) -- no second patient universe.

PROTECTED NUCLEAR BRANCH (section 2): PET/SPECT/cyclotron/generator/decay/
patient-dose/scanner semantics are UNCHANGED and UNTOUCHED by this module.
This module adds a SIMPLER, separate branch:

    PATIENT -> GENERAL LOGISTICS DEMAND -> AGGREGATION/LOAD -> TRANSPORT
    MISSION -> DELIVERY -> OPERATIONAL/ECONOMIC RESULT.

General-logistics demand is patient-aware but explicitly NOT radionuclide-
aware, cyclotron-batch-aware, generator-elution-aware, or decay-aware
(section 3-4). Loads/missions are never called "production batches" (section
6) -- that term is reserved for the nuclear branch's `PreparationBatch`
(generator.py) and cyclotron production batches.

ONE ENGINE, NOT FOUR (section 22): a single canonical demand/load/mission
model serves all four streams (PHARMACY_INFUSION, SPECIMEN_BLOOD,
CLEAN_LINEN, STERILE_CLEAN_SUPPLY) via stream-specific parameters, not
duplicated per-stream engines.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal, Mapping, Sequence

from oncology_pet_spect_scenario import OncologyPatientRecord

LogisticsStream = Literal["PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY"]
SpecimenBloodSubtype = Literal["SPECIMEN", "BLOOD_PRODUCT"]
LogisticsPriority = Literal["ROUTINE", "SCHEDULED", "URGENT", "CRITICAL"]
DemandProvenance = Literal[
    "OBSERVED_DATA", "PUBLISHED_ESTIMATE", "USER_SUPPLIED", "DERIVED_FROM_PUBLISHED_DATA",
    "CONTROLLED_SCENARIO_ASSUMPTION", "NOT_CALIBRATED",
]
DemandStatus = Literal["PLANNED", "CONSOLIDATED", "IN_TRANSIT", "DELIVERED", "DEFERRED"]
TransportMode = Literal["MANUAL", "MRT", "AGV_AMR", "PNEUMATIC_TUBE"]
ArchitectureMode = Literal["MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT"]
FacilityRole = Literal[
    "RADIOPHARMACY", "CENTRAL_PHARMACY", "LABORATORY", "BLOOD_BANK", "CLEAN_LINEN_SOURCE",
    "STERILE_CLEAN_SUPPLY", "PATIENT_ROOM", "OUTPATIENT_ORIGIN", "PET_SCANNER", "SPECT_SCANNER",
]
TechnologyStatus = Literal["IMPLEMENTATION_PENDING", "PERFORMANCE_NOT_CALIBRATED", "ECONOMICS_NOT_CALIBRATED"]
LocationStatus = Literal["CALIBRATED", "LOCATION_NOT_CALIBRATED"]


# ---------------------------------------------------------------------------
# Facility roles (section 36-38) -- lightweight, additive; does NOT modify
# the existing BIM `facility_engineering_model.EquipmentClass`.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FacilityRoleLocation:
    """Section 37-38: a real, shared origin/destination for ALL architecture
    modes -- explicit LOCATION_NOT_CALIBRATED where a real location is not
    yet defined, never a silently-invented adjacency."""

    role: FacilityRole
    object_id: str | None
    building_id: str | None
    floor_id: str | None
    location_status: LocationStatus
    streams_served: tuple[LogisticsStream, ...] = ()

    def __post_init__(self) -> None:
        if self.location_status == "CALIBRATED" and self.object_id is None:
            raise ValueError(f"{self.role}: CALIBRATED location_status requires an object_id")


def build_default_facility_roles() -> tuple[FacilityRoleLocation, ...]:
    """Section 38: ONE physical set of role locations shared by every
    architecture mode -- MANUAL_CONVENTIONAL and MRT never receive different
    department coordinates."""
    return (
        FacilityRoleLocation(role="RADIOPHARMACY", object_id="RP-001", building_id="BLDG-A", floor_id="F1",
                              location_status="CALIBRATED", streams_served=()),
        FacilityRoleLocation(role="CENTRAL_PHARMACY", object_id="PHARM-001", building_id="BLDG-A", floor_id="F1",
                              location_status="CALIBRATED", streams_served=("PHARMACY_INFUSION",)),
        FacilityRoleLocation(role="LABORATORY", object_id="LAB-001", building_id="BLDG-A", floor_id="F1",
                              location_status="CALIBRATED", streams_served=("SPECIMEN_BLOOD",)),
        FacilityRoleLocation(role="BLOOD_BANK", object_id="BB-001", building_id="BLDG-A", floor_id="F1",
                              location_status="CALIBRATED", streams_served=("SPECIMEN_BLOOD",)),
        FacilityRoleLocation(role="CLEAN_LINEN_SOURCE", object_id=None, building_id=None, floor_id=None,
                              location_status="LOCATION_NOT_CALIBRATED", streams_served=("CLEAN_LINEN",)),
        FacilityRoleLocation(role="STERILE_CLEAN_SUPPLY", object_id=None, building_id=None, floor_id=None,
                              location_status="LOCATION_NOT_CALIBRATED", streams_served=("STERILE_CLEAN_SUPPLY",)),
        FacilityRoleLocation(role="PET_SCANNER", object_id="SCN-001", building_id="BLDG-A", floor_id="F1",
                              location_status="CALIBRATED", streams_served=()),
        FacilityRoleLocation(role="SPECT_SCANNER", object_id="SCN-005", building_id="BLDG-A", floor_id="F1",
                              location_status="CALIBRATED", streams_served=()),
    )


def resolve_role_location(roles: tuple[FacilityRoleLocation, ...], role: FacilityRole) -> FacilityRoleLocation:
    for r in roles:
        if r.role == role:
            return r
    raise ValueError(f"Unknown facility role: {role}")


# ---------------------------------------------------------------------------
# Canonical general-logistics demand (section 7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LogisticsDemand:
    demand_id: str
    patient_id: str
    stream: LogisticsStream
    origin: str
    destination: str
    quantity: float
    unit: str
    release_datetime: datetime
    priority: LogisticsPriority
    payload_class: str
    provenance: DemandProvenance
    calibration_status: Literal["CALIBRATED", "NOT_CALIBRATED"]
    required_by_datetime: datetime | None = None
    handling_requirements: tuple[str, ...] = ()
    status: DemandStatus = "PLANNED"
    subtype: SpecimenBloodSubtype | None = None
    """Section 17: SPECIMEN vs BLOOD_PRODUCT -- only meaningful for the
    SPECIMEN_BLOOD stream."""
    ward_id: str | None = None
    """Section 5/52: the patient's ward/floor -- the consolidation
    granularity multiple patients' demands are grouped at (never the exact
    room, which would prevent any real consolidation across patients)."""

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(f"{self.demand_id}: quantity must be positive")
        if self.required_by_datetime is not None and self.required_by_datetime < self.release_datetime:
            raise ValueError(f"{self.demand_id}: required_by_datetime must not precede release_datetime")
        if self.stream == "SPECIMEN_BLOOD" and self.subtype is None:
            raise ValueError(f"{self.demand_id}: SPECIMEN_BLOOD demand requires a subtype (SPECIMEN|BLOOD_PRODUCT)")
        if self.stream != "SPECIMEN_BLOOD" and self.subtype is not None:
            raise ValueError(f"{self.demand_id}: subtype only applies to SPECIMEN_BLOOD")


# ---------------------------------------------------------------------------
# Transport load / mission (sections 23-24)
# ---------------------------------------------------------------------------



@dataclass(frozen=True)
class TransportLoad:
    """Section 5/23: multiple patient demands consolidated into ONE load --
    patient provenance (`patient_ids`) always survives aggregation."""

    load_id: str
    stream: LogisticsStream
    patient_ids: tuple[str, ...]
    origin: str
    destination: str
    quantity: float
    unit: str
    payload_class: str
    release_datetime: datetime
    priority: LogisticsPriority
    required_by_datetime: datetime | None = None
    compatibility_requirements: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.patient_ids:
            raise ValueError(f"{self.load_id}: must retain at least one patient_id")
        if self.quantity <= 0:
            raise ValueError(f"{self.load_id}: quantity must be positive")


@dataclass(frozen=True)
class TransportMission:
    mission_id: str
    load_id: str
    transport_mode: TransportMode
    origin: str
    destination: str
    departure_datetime: datetime
    arrival_datetime: datetime
    patient_ids: tuple[str, ...]
    status: Literal["PLANNED", "IN_TRANSIT", "DELIVERED"] = "PLANNED"
    resource_id: str | None = None
    distance_m: float | None = None
    duration_minutes: float | None = None

    def __post_init__(self) -> None:
        if self.arrival_datetime < self.departure_datetime:
            raise ValueError(f"{self.mission_id}: arrival must not precede departure")
        if not self.patient_ids:
            raise ValueError(f"{self.mission_id}: must retain at least one patient_id")


# ---------------------------------------------------------------------------
# Demand generation (sections 10-21) -- inpatient-focused, calendar-aware,
# ONE generic generator reused per stream (section 22).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StreamDemandPolicy:
    """Section 13/19/67: stream-specific coefficient, always provenance-
    tagged -- never silently promoted from assumption to calibrated fact."""

    stream: LogisticsStream
    quantity_per_patient_day: float
    unit: str
    payload_class: str
    priority: LogisticsPriority
    provenance: DemandProvenance
    handling_requirements: tuple[str, ...] = ()
    subtype: SpecimenBloodSubtype | None = None
    required_by_hours: float | None = None


DEFAULT_STREAM_POLICIES: tuple[StreamDemandPolicy, ...] = (
    StreamDemandPolicy(stream="CLEAN_LINEN", quantity_per_patient_day=7.5, unit="kg", payload_class="LINEN_BAG",
                        priority="SCHEDULED", provenance="CONTROLLED_SCENARIO_ASSUMPTION"),
    StreamDemandPolicy(stream="PHARMACY_INFUSION", quantity_per_patient_day=1.0, unit="tote_equivalent",
                        payload_class="PHARMACY_TOTE", priority="SCHEDULED", provenance="CONTROLLED_SCENARIO_ASSUMPTION",
                        required_by_hours=4.0),
    StreamDemandPolicy(stream="SPECIMEN_BLOOD", quantity_per_patient_day=1.0, unit="specimen_container",
                        payload_class="SPECIMEN_CONTAINER", priority="URGENT", provenance="CONTROLLED_SCENARIO_ASSUMPTION",
                        subtype="SPECIMEN", required_by_hours=2.0),
    StreamDemandPolicy(stream="STERILE_CLEAN_SUPPLY", quantity_per_patient_day=1.0, unit="supply_tote",
                        payload_class="STERILE_TOTE", priority="ROUTINE", provenance="CONTROLLED_SCENARIO_ASSUMPTION"),
)


def generate_daily_logistics_demand(
    *,
    day: date,
    inpatients: tuple[OncologyPatientRecord, ...],
    roles: tuple[FacilityRoleLocation, ...],
    policies: tuple[StreamDemandPolicy, ...] = DEFAULT_STREAM_POLICIES,
) -> tuple[LogisticsDemand, ...]:
    """Sections 10-21: ONE generic generator -- for each ACTIVE inpatient
    (admission <= day <= discharge, section 20) and each stream policy,
    create ONE patient-attributed `LogisticsDemand`. Outpatients never
    receive general-logistics demand in this build (section 10) merely
    because they have a nuclear appointment."""
    demands: list[LogisticsDemand] = []
    role_by_stream = {
        "CLEAN_LINEN": "CLEAN_LINEN_SOURCE", "PHARMACY_INFUSION": "CENTRAL_PHARMACY",
        "SPECIMEN_BLOOD": "LABORATORY", "STERILE_CLEAN_SUPPLY": "STERILE_CLEAN_SUPPLY",
    }
    for patient in inpatients:
        if patient.patient_type != "INPATIENT":
            continue  # section 10: inpatient focus, never outpatient by default
        admission = patient.admission_date or day
        discharge = patient.expected_discharge_date or day
        if not (admission <= day <= discharge):
            continue  # section 20-21: demand only while the patient is actually present
        for policy in policies:
            role = resolve_role_location(roles, role_by_stream[policy.stream])
            origin, destination = (role.object_id or "LOCATION_NOT_CALIBRATED"), patient.room_id or "LOCATION_NOT_CALIBRATED"
            if policy.stream == "SPECIMEN_BLOOD":
                origin, destination = destination, origin  # patient/room -> laboratory (section 11)
            required_by = (datetime.combine(day, datetime.min.time()) + timedelta(hours=policy.required_by_hours)) if policy.required_by_hours else None
            demands.append(LogisticsDemand(
                demand_id=f"DEM-{policy.stream}-{patient.patient_id}-{day.isoformat()}",
                patient_id=patient.patient_id, stream=policy.stream, origin=origin, destination=destination,
                quantity=policy.quantity_per_patient_day, unit=policy.unit,
                release_datetime=datetime.combine(day, datetime.min.time()),
                required_by_datetime=required_by, priority=policy.priority, payload_class=policy.payload_class,
                provenance=policy.provenance, calibration_status="NOT_CALIBRATED",
                handling_requirements=policy.handling_requirements, subtype=policy.subtype,
                ward_id=patient.floor_id,
            ))
    return tuple(demands)


# ---------------------------------------------------------------------------
# Consolidation into loads (sections 5, 52) -- patient provenance survives.
# ---------------------------------------------------------------------------


def consolidate_demands_into_loads(
    *, demands: tuple[LogisticsDemand, ...], max_quantity_per_load: float,
) -> tuple[TransportLoad, ...]:
    """Section 5/52: multiple patient demands for the SAME stream/ward/
    priority consolidate into one load up to `max_quantity_per_load` -- never
    one load per patient merely because demand is patient-aware. Ward-level
    (not exact-room) grouping is required because each patient's exact room
    is unique -- grouping by exact room would silently prevent any real
    cross-patient consolidation."""
    by_key: dict[tuple, list[LogisticsDemand]] = {}
    for d in demands:
        by_key.setdefault((d.stream, d.ward_id, d.priority), []).append(d)

    loads: list[TransportLoad] = []
    load_index = 0
    for (stream, ward_id, priority), group in by_key.items():
        # Section 11: exactly one side (origin or destination) is the shared
        # facility role and is IDENTICAL across the whole group by construction;
        # the patient-varying side is represented at ward granularity.
        sample = group[0]
        ward_label = f"WARD-{ward_id}" if ward_id else "LOCATION_NOT_CALIBRATED"
        # Determine which side varies per-patient by checking whether it equals a facility role constant across the group.
        origins = {d.origin for d in group}
        destinations = {d.destination for d in group}
        if len(origins) == 1:
            origin, destination = sample.origin, ward_label
        else:
            origin, destination = ward_label, sample.destination

        current_patients: list[str] = []
        current_quantity = 0.0
        current_deadline: datetime | None = None
        current_release: datetime | None = None

        def _flush():
            nonlocal load_index, current_patients, current_quantity, current_deadline, current_release
            if not current_patients:
                return
            load_index += 1
            loads.append(TransportLoad(
                load_id=f"LOAD-{stream}-{load_index:04d}", stream=stream, patient_ids=tuple(current_patients),
                origin=origin, destination=destination, quantity=current_quantity, unit=group[0].unit,
                payload_class=group[0].payload_class, release_datetime=current_release, priority=priority,
                required_by_datetime=current_deadline,
            ))
            current_patients = []
            current_quantity = 0.0
            current_deadline = None
            current_release = None

        for d in sorted(group, key=lambda x: x.release_datetime):
            if current_quantity + d.quantity > max_quantity_per_load and current_patients:
                _flush()
            current_patients.append(d.patient_id)
            current_quantity += d.quantity
            current_release = d.release_datetime if current_release is None else min(current_release, d.release_datetime)
            if d.required_by_datetime is not None:
                current_deadline = d.required_by_datetime if current_deadline is None else min(current_deadline, d.required_by_datetime)
        _flush()
    return tuple(loads)


# ---------------------------------------------------------------------------
# Mission conversion (sections 13-15, 46-48) -- architecture-specific.
# Physical demand (loads) is architecture-independent; only mission COUNT
# and mode vary by architecture (section 12, 51, 68).
# ---------------------------------------------------------------------------


def convert_load_to_manual_missions(
    *, load: TransportLoad, cart_capacity: float, travel_minutes: float = 8.0,
) -> tuple[TransportMission, ...]:
    """Section 15/47: Conventional cart capacity is INDEPENDENTLY
    configurable -- never forced to match the MRT container size."""
    if cart_capacity <= 0:
        raise ValueError("cart_capacity must be positive")
    trips = max(1, math.ceil(load.quantity / cart_capacity))
    missions = []
    for i in range(trips):
        departure = load.release_datetime
        arrival = departure + timedelta(minutes=travel_minutes)
        missions.append(TransportMission(
            mission_id=f"MISSION-MANUAL-{load.load_id}-{i+1:02d}", load_id=load.load_id, transport_mode="MANUAL",
            origin=load.origin, destination=load.destination, departure_datetime=departure, arrival_datetime=arrival,
            patient_ids=load.patient_ids, duration_minutes=travel_minutes,
        ))
    return tuple(missions)


def convert_load_to_mrt_missions(
    *, load: TransportLoad, container_capacity_kg: float = 20.0, travel_minutes: float = 3.0,
) -> tuple[TransportMission, ...]:
    """Section 14: controlled MRT linen/general-payload container capacity
    -- CONTROLLED_ENGINEERING_ASSUMPTION, not a universal certified payload."""
    if container_capacity_kg <= 0:
        raise ValueError("container_capacity_kg must be positive")
    trips = max(1, math.ceil(load.quantity / container_capacity_kg))
    missions = []
    for i in range(trips):
        departure = load.release_datetime
        arrival = departure + timedelta(minutes=travel_minutes)
        missions.append(TransportMission(
            mission_id=f"MISSION-MRT-{load.load_id}-{i+1:02d}", load_id=load.load_id, transport_mode="MRT",
            origin=load.origin, destination=load.destination, departure_datetime=departure, arrival_datetime=arrival,
            patient_ids=load.patient_ids, duration_minutes=travel_minutes,
        ))
    return tuple(missions)


# ---------------------------------------------------------------------------
# Architecture modes (sections 25-34, 57-59) -- semantic in this foundation
# build; AGV/PTS are structural placeholders only (section 58).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArchitectureSemantics:
    architecture: ArchitectureMode
    nuclear_transport: str
    general_logistics: str
    mrt_present: bool
    incumbent_automation_allowed: bool
    manual_fallback: bool


ARCHITECTURE_SEMANTICS: tuple[ArchitectureSemantics, ...] = (
    ArchitectureSemantics(
        architecture="MANUAL_CONVENTIONAL", nuclear_transport="Existing specialized/manual Conventional authority",
        general_logistics="Porter/human transport + appropriate carts/trolleys", mrt_present=False,
        incumbent_automation_allowed=False, manual_fallback=True,
    ),
    ArchitectureSemantics(
        architecture="AUTOMATED_CONVENTIONAL", nuclear_transport="Existing specialized/manual Conventional authority",
        general_logistics="Portfolio: manual/cart + AGV/AMR + pneumatic tube (structural only this build)",
        mrt_present=False, incumbent_automation_allowed=True, manual_fallback=True,
    ),
    ArchitectureSemantics(
        architecture="HYBRID_MRT", nuclear_transport="Existing Conventional + MRT (section 29-30 building/floor coverage)",
        general_logistics="Conventional in non-MRT zones, MRT in covered zones", mrt_present=True,
        incumbent_automation_allowed=False, manual_fallback=True,
    ),
    ArchitectureSemantics(
        architecture="MRT_DOMINANT", nuclear_transport="MRT principal for compatible nuclear loads",
        general_logistics="MRT principal for compatible general-logistics loads", mrt_present=True,
        incumbent_automation_allowed=False, manual_fallback=True,
    ),
)


@dataclass(frozen=True)
class TechnologyPlaceholder:
    """Section 27-28/58: explicit identifiers for future AUTOMATED_CONVENTIONAL
    portfolio members -- no fabricated performance/economics."""

    technology: Literal["AGV_AMR", "PNEUMATIC_TUBE"]
    performance_status: TechnologyStatus
    economics_status: TechnologyStatus


AUTOMATED_CONVENTIONAL_TECHNOLOGY_PLACEHOLDERS: tuple[TechnologyPlaceholder, ...] = (
    TechnologyPlaceholder(technology="AGV_AMR", performance_status="PERFORMANCE_NOT_CALIBRATED", economics_status="ECONOMICS_NOT_CALIBRATED"),
    TechnologyPlaceholder(technology="PNEUMATIC_TUBE", performance_status="PERFORMANCE_NOT_CALIBRATED", economics_status="ECONOMICS_NOT_CALIBRATED"),
)


def missions_for_architecture(
    *, load: TransportLoad, architecture: ArchitectureMode, cart_capacity: float, mrt_container_capacity_kg: float = 20.0,
    mrt_coverage: frozenset[str] = frozenset(),
) -> tuple[TransportMission, ...]:
    """Section 46/61: MANUAL_CONVENTIONAL/MRT_DOMINANT/HYBRID_MRT fully
    convert missions in this build; AUTOMATED_CONVENTIONAL remains a
    structural mode (section 46) -- raises to make that explicit rather than
    fabricating AGV/PTS missions.

    HYBRID_MRT respects real MRT zone coverage (section 61): a load whose
    destination is NOT in `mrt_coverage` falls back to manual, never an
    unconnected MRT trip."""
    if architecture == "MANUAL_CONVENTIONAL":
        return convert_load_to_manual_missions(load=load, cart_capacity=cart_capacity)
    if architecture == "MRT_DOMINANT":
        return convert_load_to_mrt_missions(load=load, container_capacity_kg=mrt_container_capacity_kg)
    if architecture == "HYBRID_MRT":
        if load.destination in mrt_coverage:
            return convert_load_to_mrt_missions(load=load, container_capacity_kg=mrt_container_capacity_kg)
        return convert_load_to_manual_missions(load=load, cart_capacity=cart_capacity)
    if architecture == "AUTOMATED_CONVENTIONAL":
        raise NotImplementedError(
            "AUTOMATED_CONVENTIONAL mission conversion is a structural/compatibility boundary in this "
            "foundation build (section 46) -- full AGV/AMR/pneumatic-tube conversion is a future build."
        )
    raise ValueError(f"Unknown architecture: {architecture}")

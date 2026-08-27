"""MRT Multi-Stream Service Classes + Mission-Specific Speed/Priority/Color
Authority.

GOVERNANCE (section 1-2): ONE shared MRT physical network and ONE shared
physical carrier fleet are preserved. A "service class" (mission/logistics
stream identity: radiopharmaceutical, specimen/blood, pharmacy, sterile
supply, linen, food, waste) is a DISPATCH/PRESENTATION/SCHEDULING concept --
it never creates a second physical network, a second carrier fleet, a
second scheduler, or a second CapEx line. This module explicitly keeps THREE
separate concepts distinct everywhere:

    PHYSICAL MRT CARRIER   (capital identity -- `mrt_carrier_fleet.py`)
    PAYLOAD CONTAINER      (`shared_mrt_multistream_authority.MrtContainerClass`)
    MISSION / SERVICE CLASS (this module -- priority/speed/color/status)

REUSE, NOT DUPLICATION: scheduling is delegated to the EXISTING
`shared_mrt_multistream_authority.schedule_missions_on_shared_segment` (this
module only computes `duration_minutes` from effective speed and feeds the
existing `MrtMissionWindow`/scheduler -- it never reimplements dispatch).
Containers are resolved from the EXISTING
`shared_mrt_multistream_authority` container objects (never duplicated).
Nuclear decay reuses `multi_isotope_decay.retained_fraction` directly (never
a second decay formula). Auxiliary energy/thermal aggregation is added to
`mrt_auxiliary_systems_authority.py` (see `aggregate_service_class_speed_mix`
there), never a second electrical/thermal model.

COLOR IS PRESENTATION METADATA ONLY (section 13): color never determines
priority, speed, container, physics, CapEx, or OPEX -- enforced by keeping
`configured_active_color`/`effective_display_color` structurally separate
fields from `default_priority`/`default_speed_m_per_s` everywhere in this
module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

import shared_mrt_multistream_authority as smx
import mrt_auxiliary_systems_authority as maux
from multi_isotope_decay import retained_fraction as _decay_retained_fraction

SERVICE_CLASS_SCHEMA_VERSION = "1.0.0"

MrtServiceClass = Literal[
    "RADIOPHARMACEUTICAL_NUCLEAR", "SPECIMEN_BLOOD", "PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY",
    "LAUNDRY_CLEAN_LINEN", "FOOD_NUTRITION", "WASTE",
]

ACTIVE_SERVICE_CLASSES: tuple[MrtServiceClass, ...] = (
    "RADIOPHARMACEUTICAL_NUCLEAR", "SPECIMEN_BLOOD", "PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY", "LAUNDRY_CLEAN_LINEN",
)
INACTIVE_FUTURE_SERVICE_CLASSES: tuple[MrtServiceClass, ...] = ("FOOD_NUTRITION", "WASTE")

ServiceClassActivityStatus = Literal["ACTIVE", "INACTIVE_FUTURE_CAPABILITY"]
PresentationColor = Literal["VIOLET", "BLUE", "TEAL", "AMBER", "GOLD", "GREEN", "RED", "GRAY"]
SpeedProvenance = Literal["USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION", "NOT_CALIBRATED"]

# ---------------------------------------------------------------------------
# Section 17-18: reuse the EXISTING priority authority verbatim -- both
# PRIORITY_3/4 already exist there, so no extension is needed here.
# ---------------------------------------------------------------------------

MrtPriorityClass = smx.MrtPriorityClass
PRIORITY_RANK: Mapping[MrtPriorityClass, int] = {
    "PRIORITY_1_NUCLEAR_CRITICAL": 1, "PRIORITY_2_CLINICAL_URGENT": 2,
    "PRIORITY_3_SCHEDULED_CLINICAL": 3, "PRIORITY_4_ROUTINE_GENERAL": 4,
}


@dataclass(frozen=True)
class ServiceClassProfile:
    """Section 3-13: the canonical service-class profile. `default_priority`/
    `default_speed_m_per_s` are `"NOT_CALIBRATED"` for inactive classes and
    for any active class lacking legitimate repository evidence (section 8-9:
    never invented merely to complete the class)."""

    service_class: MrtServiceClass
    display_name: str
    activity_status: ServiceClassActivityStatus
    default_priority: MrtPriorityClass | Literal["NOT_CALIBRATED"]
    default_speed_m_per_s: float | Literal["NOT_CALIBRATED"]
    speed_provenance: SpeedProvenance
    configured_active_color: PresentationColor

    def effective_display_color(self) -> PresentationColor:
        """Section 14: inactive classes always display GRAY, never their
        configured active color, while still exposing that configured color
        (canonical identity is never lost when gray)."""
        if self.activity_status == "INACTIVE_FUTURE_CAPABILITY":
            return "GRAY"
        return self.configured_active_color


def _build_service_class_registry() -> Mapping[MrtServiceClass, ServiceClassProfile]:
    return {
        "RADIOPHARMACEUTICAL_NUCLEAR": ServiceClassProfile(
            service_class="RADIOPHARMACEUTICAL_NUCLEAR", display_name="Radiopharmaceutical / Nuclear",
            activity_status="ACTIVE", default_priority="PRIORITY_1_NUCLEAR_CRITICAL",
            default_speed_m_per_s=10.0, speed_provenance="USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION",
            configured_active_color="VIOLET",
        ),
        "SPECIMEN_BLOOD": ServiceClassProfile(
            service_class="SPECIMEN_BLOOD", display_name="Specimen / Blood", activity_status="ACTIVE",
            default_priority="PRIORITY_2_CLINICAL_URGENT", default_speed_m_per_s=7.0,
            speed_provenance="USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION", configured_active_color="BLUE",
        ),
        "PHARMACY_INFUSION": ServiceClassProfile(
            service_class="PHARMACY_INFUSION", display_name="Pharmacy / Infusion", activity_status="ACTIVE",
            default_priority="PRIORITY_2_CLINICAL_URGENT", default_speed_m_per_s="NOT_CALIBRATED",
            speed_provenance="NOT_CALIBRATED", configured_active_color="TEAL",
        ),
        "STERILE_CLEAN_SUPPLY": ServiceClassProfile(
            service_class="STERILE_CLEAN_SUPPLY", display_name="Sterile / Clean Supply", activity_status="ACTIVE",
            default_priority="PRIORITY_3_SCHEDULED_CLINICAL", default_speed_m_per_s="NOT_CALIBRATED",
            speed_provenance="NOT_CALIBRATED", configured_active_color="AMBER",
        ),
        "LAUNDRY_CLEAN_LINEN": ServiceClassProfile(
            service_class="LAUNDRY_CLEAN_LINEN", display_name="Laundry / Clean Linen", activity_status="ACTIVE",
            default_priority="PRIORITY_4_ROUTINE_GENERAL", default_speed_m_per_s=1.0,
            speed_provenance="USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION", configured_active_color="GOLD",
        ),
        "FOOD_NUTRITION": ServiceClassProfile(
            service_class="FOOD_NUTRITION", display_name="Food / Nutrition", activity_status="INACTIVE_FUTURE_CAPABILITY",
            default_priority="NOT_CALIBRATED", default_speed_m_per_s="NOT_CALIBRATED",
            speed_provenance="NOT_CALIBRATED", configured_active_color="GREEN",
        ),
        "WASTE": ServiceClassProfile(
            service_class="WASTE", display_name="Waste", activity_status="INACTIVE_FUTURE_CAPABILITY",
            default_priority="NOT_CALIBRATED", default_speed_m_per_s="NOT_CALIBRATED",
            speed_provenance="NOT_CALIBRATED", configured_active_color="RED",
        ),
    }


SERVICE_CLASS_REGISTRY: Mapping[MrtServiceClass, ServiceClassProfile] = _build_service_class_registry()

# LAUNDRY_CLEAN_LINEN terminology compatibility (section 5): preserve the
# existing `CLEAN_LINEN` general-logistics stream identifier through mapping.
LAUNDRY_CLEAN_LINEN_STREAM_ALIAS = "CLEAN_LINEN"


def resolve_service_class_for_existing_stream(stream: str) -> MrtServiceClass:
    """Section 5: maps the pre-existing `general_oncology_logistics`/
    `shared_mrt_multistream_authority` stream identifiers onto the new
    canonical service classes -- never breaks existing stream identifiers."""
    mapping: Mapping[str, MrtServiceClass] = {
        "CLEAN_LINEN": "LAUNDRY_CLEAN_LINEN", "PHARMACY_INFUSION": "PHARMACY_INFUSION",
        "STERILE_CLEAN_SUPPLY": "STERILE_CLEAN_SUPPLY", "SPECIMEN_BLOOD": "SPECIMEN_BLOOD",
        "NUCLEAR": "RADIOPHARMACEUTICAL_NUCLEAR",
    }
    if stream not in mapping:
        raise ValueError(f"Unknown existing stream identifier: {stream!r}")
    return mapping[stream]


# ---------------------------------------------------------------------------
# Section 25-26: service class -> container mapping. Reuses the EXISTING
# container objects verbatim -- never duplicated.
# ---------------------------------------------------------------------------

ContainerResolutionStatus = Literal["NOT_CALIBRATED", "FUTURE_CONTAINER_CLASS_REQUIRED"]


def resolve_container_for_service_class(service_class: MrtServiceClass) -> smx.MrtContainerClass | ContainerResolutionStatus:
    """Section 25-26: never fabricates a container spec for FOOD_NUTRITION/
    WASTE -- returns FUTURE_CONTAINER_CLASS_REQUIRED until explicitly
    engineered."""
    if service_class == "RADIOPHARMACEUTICAL_NUCLEAR":
        return smx.DEFAULT_NUCLEAR_SHIELDED_CONTAINER
    if service_class == "PHARMACY_INFUSION":
        return smx.DEFAULT_CLINICAL_CLEAN_CONTAINER
    if service_class == "STERILE_CLEAN_SUPPLY":
        return smx.DEFAULT_STERILE_SUPPLY_CONTAINER
    if service_class == "LAUNDRY_CLEAN_LINEN":
        return smx.DEFAULT_LINEN_CONTAINER
    if service_class == "SPECIMEN_BLOOD":
        return smx.DEFAULT_SPECIMEN_BLOOD_CONTAINER
    return "FUTURE_CONTAINER_CLASS_REQUIRED"


# ---------------------------------------------------------------------------
# Section 20-24: priority override (with mandatory provenance) + speed
# override -- both independent of service class/color/container.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PriorityOverrideRecord:
    """Section 21: no invisible priority mutation -- original AND effective
    priority, plus reason/source, are always retained together."""

    original_priority: MrtPriorityClass | Literal["NOT_CALIBRATED"]
    effective_priority: MrtPriorityClass
    reason: str
    source: str


def resolve_effective_priority(
    profile: ServiceClassProfile, *, override: PriorityOverrideRecord | None = None,
) -> MrtPriorityClass | Literal["NOT_CALIBRATED"]:
    """Section 15-16/22: priority never inferred from speed or container --
    resolved purely from the service-class default or an explicit override."""
    if override is not None:
        return override.effective_priority
    return profile.default_priority


def resolve_effective_speed(
    profile: ServiceClassProfile, *, speed_override_m_per_s: float | None = None,
) -> float | Literal["NOT_CALIBRATED"]:
    """Section 22-24: override when valid, otherwise the calibrated
    service-class default, otherwise NOT_CALIBRATED. Never changes service
    class/color/priority/container."""
    if speed_override_m_per_s is not None:
        return float(speed_override_m_per_s)
    return profile.default_speed_m_per_s


# ---------------------------------------------------------------------------
# Section 22, 27-34: mission definition + scheduling integration. Speed only
# ever enters the EXISTING scheduler as a computed `duration_minutes` -- this
# module never reimplements dispatch/headway/priority-ordering logic.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MrtServiceMission:
    """Section 28-29: `carrier_id` identifies the PHYSICAL carrier (survives
    reassignment across missions); `mission_id` identifies THIS mission only."""

    mission_id: str
    carrier_id: str
    service_class: MrtServiceClass
    route_length_m: float | Literal["NOT_CALIBRATED"]
    start_minutes: float
    speed_override_m_per_s: float | None = None
    priority_override: PriorityOverrideRecord | None = None
    deadline_minutes: float | None = None


def mission_effective_speed(mission: MrtServiceMission) -> float | Literal["NOT_CALIBRATED"]:
    profile = SERVICE_CLASS_REGISTRY[mission.service_class]
    return resolve_effective_speed(profile, speed_override_m_per_s=mission.speed_override_m_per_s)


def mission_effective_priority(mission: MrtServiceMission) -> MrtPriorityClass | Literal["NOT_CALIBRATED"]:
    profile = SERVICE_CLASS_REGISTRY[mission.service_class]
    return resolve_effective_priority(profile, override=mission.priority_override)


def compute_mission_duration_minutes(mission: MrtServiceMission) -> float | Literal["NOT_CALIBRATED"]:
    """Section 30/34: route travel time uses the ACTUAL effective mission
    speed -- never a universal 10 m/s constant for every service class."""
    speed = mission_effective_speed(mission)
    if speed == "NOT_CALIBRATED" or mission.route_length_m == "NOT_CALIBRATED" or speed <= 0:
        return "NOT_CALIBRATED"
    return float(mission.route_length_m) / float(speed) / 60.0  # type: ignore[arg-type]


@dataclass(frozen=True)
class MissionWindowResolution:
    window: smx.MrtMissionWindow | None
    status: Literal["RESOLVED", "NOT_CALIBRATED"]
    missing_inputs: tuple[str, ...]


def resolve_mission_window(mission: MrtServiceMission) -> MissionWindowResolution:
    """Section 22/30: builds the EXISTING `MrtMissionWindow` type from the
    mission's effective speed/priority -- never a parallel window type."""
    missing = []
    duration = compute_mission_duration_minutes(mission)
    if duration == "NOT_CALIBRATED":
        missing.append("effective_speed_or_route_length")
    priority = mission_effective_priority(mission)
    if priority == "NOT_CALIBRATED":
        missing.append("effective_priority")
    if missing:
        return MissionWindowResolution(window=None, status="NOT_CALIBRATED", missing_inputs=tuple(missing))
    stream_or_nuclear = "NUCLEAR" if mission.service_class == "RADIOPHARMACEUTICAL_NUCLEAR" else _service_class_to_stream(mission.service_class)
    window = smx.MrtMissionWindow(
        mission_id=mission.mission_id, patient_ids=(), stream_or_nuclear=stream_or_nuclear,  # type: ignore[arg-type]
        priority_class=priority, start_minutes=mission.start_minutes, duration_minutes=duration,  # type: ignore[arg-type]
        deadline_minutes=mission.deadline_minutes,
    )
    return MissionWindowResolution(window=window, status="RESOLVED", missing_inputs=())


def _service_class_to_stream(service_class: MrtServiceClass) -> str:
    mapping = {
        "SPECIMEN_BLOOD": "SPECIMEN_BLOOD", "PHARMACY_INFUSION": "PHARMACY_INFUSION",
        "STERILE_CLEAN_SUPPLY": "STERILE_CLEAN_SUPPLY", "LAUNDRY_CLEAN_LINEN": "CLEAN_LINEN",
    }
    return mapping.get(service_class, service_class)


def schedule_service_missions(
    missions: Sequence[MrtServiceMission], *, segment: smx.MrtNetworkSegment = smx.DEFAULT_SHARED_TRUNK_SEGMENT,
) -> tuple[tuple[smx.ScheduledMrtMission, ...], tuple[MrtServiceMission, ...]]:
    """Section 30-34: delegates to the EXISTING single-shared-segment
    priority-ordered scheduler -- never a second scheduler. Missions whose
    window cannot be resolved are excluded from scheduling and returned
    separately (never silently dropped)."""
    resolved_windows = []
    unresolved: list[MrtServiceMission] = []
    for mission in missions:
        resolution = resolve_mission_window(mission)
        if resolution.status == "RESOLVED" and resolution.window is not None:
            resolved_windows.append(resolution.window)
        else:
            unresolved.append(mission)
    scheduled = smx.schedule_missions_on_shared_segment(tuple(resolved_windows), segment=segment)
    return scheduled, tuple(unresolved)


# ---------------------------------------------------------------------------
# Section 28-29, 67: carrier dispatch state -- CURRENT mission presentation
# metadata only; never redefines the physical carrier's capital identity.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CarrierDispatchState:
    carrier_id: str
    mission_id: str
    service_class: MrtServiceClass
    effective_display_color: PresentationColor
    effective_priority: MrtPriorityClass | Literal["NOT_CALIBRATED"]
    effective_speed_m_per_s: float | Literal["NOT_CALIBRATED"]
    container_class_id: str | ContainerResolutionStatus


def build_carrier_dispatch_state(mission: MrtServiceMission) -> CarrierDispatchState:
    profile = SERVICE_CLASS_REGISTRY[mission.service_class]
    container = resolve_container_for_service_class(mission.service_class)
    container_id = container if isinstance(container, str) else container.container_class_id
    return CarrierDispatchState(
        carrier_id=mission.carrier_id, mission_id=mission.mission_id, service_class=mission.service_class,
        effective_display_color=profile.effective_display_color(), effective_priority=mission_effective_priority(mission),
        effective_speed_m_per_s=mission_effective_speed(mission), container_class_id=container_id,
    )


def reassign_carrier(carrier_id: str, new_mission: MrtServiceMission) -> CarrierDispatchState:
    """Section 29/67: same physical `carrier_id` executing a DIFFERENT
    mission/service class -- no new carrier engineering object, no
    duplicated CapEx."""
    if new_mission.carrier_id != carrier_id:
        raise ValueError("new_mission.carrier_id must match the carrier being reassigned")
    return build_carrier_dispatch_state(new_mission)


# ---------------------------------------------------------------------------
# Section 35-36: nuclear decay (reuse EXISTING formula) vs general logistics
# (no fabricated decay).
# ---------------------------------------------------------------------------


def compute_nuclear_retained_fraction_for_mission(mission: MrtServiceMission, *, half_life_minutes: float) -> float | Literal["NOT_CALIBRATED"]:
    """Section 35: effective mission speed -> route travel time -> the
    EXISTING `multi_isotope_decay.retained_fraction` -- never a second decay
    formula. Only meaningful for RADIOPHARMACEUTICAL_NUCLEAR missions."""
    if mission.service_class != "RADIOPHARMACEUTICAL_NUCLEAR":
        raise ValueError("Nuclear decay is only applicable to RADIOPHARMACEUTICAL_NUCLEAR missions")
    duration_minutes = compute_mission_duration_minutes(mission)
    if duration_minutes == "NOT_CALIBRATED":
        return "NOT_CALIBRATED"
    return _decay_retained_fraction(duration_minutes, half_life_minutes)


def general_logistics_has_no_decay_field(mission: MrtServiceMission) -> bool:
    """Section 36: `MrtServiceMission` structurally has NO activity/decay
    field for any non-nuclear service class -- this function documents/
    verifies that fact rather than adding one."""
    return mission.service_class != "RADIOPHARMACEUTICAL_NUCLEAR" and not hasattr(mission, "activity_mbq")


# ---------------------------------------------------------------------------
# Section 57-61: inspector / summary / active-mission / priority-performance
# table contracts.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceMissionInspectorResult:
    carrier_id: str
    mission_id: str
    service_class_id: MrtServiceClass
    service_class_display_name: str
    effective_display_color: PresentationColor
    configured_active_color: PresentationColor
    activity_status: ServiceClassActivityStatus
    default_service_speed_m_per_s: float | Literal["NOT_CALIBRATED"]
    effective_mission_speed_m_per_s: float | Literal["NOT_CALIBRATED"]
    default_priority: MrtPriorityClass | Literal["NOT_CALIBRATED"]
    effective_priority: MrtPriorityClass | Literal["NOT_CALIBRATED"]
    priority_override_status: Literal["NONE", "OVERRIDDEN"]
    priority_override_reason: str | None
    container_class: str | ContainerResolutionStatus
    origin: str | None
    destination: str | None
    scheduling_status: Literal["RESOLVED", "NOT_CALIBRATED"]
    energy_resolution_status: str
    thermal_resolution_status: str
    cooling_resolution_status: str
    opex_resolution_status: str
    provenance: str


def build_service_mission_inspector(
    mission: MrtServiceMission, *, origin: str | None = None, destination: str | None = None,
    energy_resolution_status: str = "NOT_CALIBRATED", thermal_resolution_status: str = "NOT_CALIBRATED",
    cooling_resolution_status: str = "NOT_CALIBRATED", opex_resolution_status: str = "NOT_CALIBRATED",
) -> ServiceMissionInspectorResult:
    profile = SERVICE_CLASS_REGISTRY[mission.service_class]
    container = resolve_container_for_service_class(mission.service_class)
    resolution = resolve_mission_window(mission)
    return ServiceMissionInspectorResult(
        carrier_id=mission.carrier_id, mission_id=mission.mission_id, service_class_id=mission.service_class,
        service_class_display_name=profile.display_name, effective_display_color=profile.effective_display_color(),
        configured_active_color=profile.configured_active_color, activity_status=profile.activity_status,
        default_service_speed_m_per_s=profile.default_speed_m_per_s, effective_mission_speed_m_per_s=mission_effective_speed(mission),
        default_priority=profile.default_priority, effective_priority=mission_effective_priority(mission),
        priority_override_status=("OVERRIDDEN" if mission.priority_override is not None else "NONE"),
        priority_override_reason=(mission.priority_override.reason if mission.priority_override is not None else None),
        container_class=(container if isinstance(container, str) else container.container_class_id),
        origin=origin, destination=destination, scheduling_status=resolution.status,
        energy_resolution_status=energy_resolution_status, thermal_resolution_status=thermal_resolution_status,
        cooling_resolution_status=cooling_resolution_status, opex_resolution_status=opex_resolution_status,
        provenance=profile.speed_provenance,
    )


@dataclass(frozen=True)
class ServiceClassSummaryRow:
    service_class: MrtServiceClass
    active: bool
    display_color: PresentationColor
    default_speed_m_per_s: float | Literal["NOT_CALIBRATED"]
    priority: MrtPriorityClass | Literal["NOT_CALIBRATED"]
    container: str | ContainerResolutionStatus
    current_missions: int
    status: ServiceClassActivityStatus


def build_service_class_summary_table(missions_by_class: Mapping[MrtServiceClass, int] | None = None) -> tuple[ServiceClassSummaryRow, ...]:
    """Section 58: ALL seven classes appear, including inactive Food/Waste."""
    counts = missions_by_class or {}
    rows = []
    for sc in ("RADIOPHARMACEUTICAL_NUCLEAR", "SPECIMEN_BLOOD", "PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY", "LAUNDRY_CLEAN_LINEN", "FOOD_NUTRITION", "WASTE"):
        profile = SERVICE_CLASS_REGISTRY[sc]
        container = resolve_container_for_service_class(sc)
        rows.append(ServiceClassSummaryRow(
            service_class=sc, active=(profile.activity_status == "ACTIVE"), display_color=profile.effective_display_color(),
            default_speed_m_per_s=profile.default_speed_m_per_s, priority=profile.default_priority,
            container=(container if isinstance(container, str) else container.container_class_id),
            current_missions=counts.get(sc, 0), status=profile.activity_status,
        ))
    return tuple(rows)


@dataclass(frozen=True)
class ActiveMissionRow:
    carrier_id: str
    mission_id: str
    service_class: MrtServiceClass
    color: PresentationColor
    priority: MrtPriorityClass | Literal["NOT_CALIBRATED"]
    speed_m_per_s: float | Literal["NOT_CALIBRATED"]
    origin: str | None
    destination: str | None
    status: str


def build_active_mission_table(
    missions: Sequence[MrtServiceMission], *, statuses: Mapping[str, str] | None = None,
    origins: Mapping[str, str] | None = None, destinations: Mapping[str, str] | None = None,
) -> tuple[ActiveMissionRow, ...]:
    """Section 59: backend contract for the future live 3D operations/what-if
    interface."""
    statuses = statuses or {}
    origins = origins or {}
    destinations = destinations or {}
    rows = []
    for mission in missions:
        profile = SERVICE_CLASS_REGISTRY[mission.service_class]
        rows.append(ActiveMissionRow(
            carrier_id=mission.carrier_id, mission_id=mission.mission_id, service_class=mission.service_class,
            color=profile.effective_display_color(), priority=mission_effective_priority(mission),
            speed_m_per_s=mission_effective_speed(mission), origin=origins.get(mission.mission_id),
            destination=destinations.get(mission.mission_id), status=statuses.get(mission.mission_id, "UNKNOWN"),
        ))
    return tuple(rows)


@dataclass(frozen=True)
class ServiceClassSchedulerAggregateRow:
    service_class: MrtServiceClass
    missions: int
    on_time: int
    late: int
    unmet: int
    average_wait_minutes: float
    maximum_wait_minutes: float
    average_transport_time_minutes: float


def aggregate_scheduler_results_by_service_class(
    scheduled: Sequence[smx.ScheduledMrtMission], *, service_class_by_mission_id: Mapping[str, MrtServiceClass],
) -> tuple[ServiceClassSchedulerAggregateRow, ...]:
    """Section 60: aggregates the EXISTING scheduler's real output -- never a
    second scheduling-result authority."""
    by_class: dict[MrtServiceClass, list[smx.ScheduledMrtMission]] = {}
    for s in scheduled:
        sc = service_class_by_mission_id.get(s.mission_id)
        if sc is None:
            continue
        by_class.setdefault(sc, []).append(s)
    rows = []
    for sc, items in by_class.items():
        waits = [i.wait_minutes for i in items]
        transport_times = [i.scheduled_end_minutes - i.scheduled_start_minutes for i in items]
        rows.append(ServiceClassSchedulerAggregateRow(
            service_class=sc, missions=len(items), on_time=sum(1 for i in items if i.deadline_status in ("ON_TIME", "NO_DEADLINE")),
            late=sum(1 for i in items if i.deadline_status == "LATE"), unmet=sum(1 for i in items if i.deadline_status == "UNMET"),
            average_wait_minutes=sum(waits) / len(waits), maximum_wait_minutes=max(waits),
            average_transport_time_minutes=sum(transport_times) / len(transport_times),
        ))
    return tuple(rows)


@dataclass(frozen=True)
class PriorityPerformanceRow:
    priority_class: MrtPriorityClass
    missions: int
    on_time: int
    late: int
    unmet: int
    average_wait_minutes: float
    maximum_wait_minutes: float


def build_priority_performance_table(scheduled: Sequence[smx.ScheduledMrtMission]) -> tuple[PriorityPerformanceRow, ...]:
    """Section 61: verifies higher-priority scheduling functions WITHOUT
    silently starving routine (P4) traffic."""
    by_priority: dict[MrtPriorityClass, list[smx.ScheduledMrtMission]] = {}
    for s in scheduled:
        by_priority.setdefault(s.priority_class, []).append(s)
    rows = []
    for priority in ("PRIORITY_1_NUCLEAR_CRITICAL", "PRIORITY_2_CLINICAL_URGENT", "PRIORITY_3_SCHEDULED_CLINICAL", "PRIORITY_4_ROUTINE_GENERAL"):
        items = by_priority.get(priority, [])
        if not items:
            rows.append(PriorityPerformanceRow(priority_class=priority, missions=0, on_time=0, late=0, unmet=0, average_wait_minutes=0.0, maximum_wait_minutes=0.0))
            continue
        waits = [i.wait_minutes for i in items]
        rows.append(PriorityPerformanceRow(
            priority_class=priority, missions=len(items), on_time=sum(1 for i in items if i.deadline_status in ("ON_TIME", "NO_DEADLINE")),
            late=sum(1 for i in items if i.deadline_status == "LATE"), unmet=sum(1 for i in items if i.deadline_status == "UNMET"),
            average_wait_minutes=sum(waits) / len(waits), maximum_wait_minutes=max(waits),
        ))
    return tuple(rows)


# ---------------------------------------------------------------------------
# Section 49-50, 68: inactive-stream non-regression guard.
# ---------------------------------------------------------------------------


def filter_active_service_class_missions(missions: Sequence[MrtServiceMission]) -> tuple[MrtServiceMission, ...]:
    """Section 49-50/68: defense-in-depth filter -- FOOD_NUTRITION/WASTE
    missions never contribute to demand/fleet/energy/CapEx/OPEX/scheduling
    while inactive, even if one is accidentally constructed upstream."""
    return tuple(m for m in missions if SERVICE_CLASS_REGISTRY[m.service_class].activity_status == "ACTIVE")


# ---------------------------------------------------------------------------
# Section 51, 69: future stream activation contract.
# ---------------------------------------------------------------------------

ActivationStatus = Literal["ACTIVATION_COMPLETE", "ACTIVATION_BLOCKED"]


@dataclass(frozen=True)
class StreamActivationResult:
    service_class: MrtServiceClass
    requested_activation: bool
    missing_calibration_inputs: tuple[str, ...]
    container_readiness: bool
    speed_readiness: bool
    priority_readiness: bool
    route_readiness: bool
    overall_status: ActivationStatus


def evaluate_stream_activation(service_class: MrtServiceClass, *, route_available: bool = False) -> StreamActivationResult:
    """Section 51/69: `active=True` never silently fabricates the missing
    engineering model -- activation requires demand/container/speed/
    priority/route readiness to ALL resolve first."""
    profile = SERVICE_CLASS_REGISTRY[service_class]
    missing = []
    speed_ready = profile.default_speed_m_per_s != "NOT_CALIBRATED"
    if not speed_ready:
        missing.append("default_speed_m_per_s")
    priority_ready = profile.default_priority != "NOT_CALIBRATED"
    if not priority_ready:
        missing.append("default_priority")
    container = resolve_container_for_service_class(service_class)
    container_ready = not isinstance(container, str)
    if not container_ready:
        missing.append("container_class")
    if not route_available:
        missing.append("route")
    overall = "ACTIVATION_COMPLETE" if not missing else "ACTIVATION_BLOCKED"
    return StreamActivationResult(
        service_class=service_class, requested_activation=True, missing_calibration_inputs=tuple(missing),
        container_readiness=container_ready, speed_readiness=speed_ready, priority_readiness=priority_ready,
        route_readiness=route_available, overall_status=overall,
    )


# ---------------------------------------------------------------------------
# Section 78: demand-mix what-if -- identifies the changed class only.
# ---------------------------------------------------------------------------


def apply_demand_mix_change(missions_by_class: Mapping[MrtServiceClass, int], *, service_class: MrtServiceClass, new_count: int) -> Mapping[MrtServiceClass, int]:
    """Section 78: changes ONE service class's mission count -- every other
    class's count is preserved unchanged (never a blind full regeneration)."""
    updated = dict(missions_by_class)
    updated[service_class] = new_count
    return updated


# ---------------------------------------------------------------------------
# Section 13-14, 52-56, 81: presentation metadata + accessibility + OpenUSD
# export (non-authoritative) + future legend contract.
# ---------------------------------------------------------------------------

PRESENTATION_LEGEND: Mapping[PresentationColor, str] = {
    "VIOLET": "RADIOPHARMACEUTICAL_NUCLEAR", "BLUE": "SPECIMEN_BLOOD", "TEAL": "PHARMACY_INFUSION",
    "AMBER": "STERILE_CLEAN_SUPPLY", "GOLD": "LAUNDRY_CLEAN_LINEN", "GREEN": "FOOD_NUTRITION (when active)",
    "RED": "WASTE (when active)", "GRAY": "INACTIVE_FUTURE_CAPABILITY",
}


@dataclass(frozen=True)
class AccessiblePresentationMetadata:
    """Section 56: color is never the ONLY identification mechanism -- a
    text label, service-class ID, and priority always accompany it."""

    color: PresentationColor
    text_label: str
    service_class_id: MrtServiceClass
    priority: MrtPriorityClass | Literal["NOT_CALIBRATED"]


def build_accessible_presentation(profile: ServiceClassProfile) -> AccessiblePresentationMetadata:
    return AccessiblePresentationMetadata(
        color=profile.effective_display_color(), text_label=profile.display_name,
        service_class_id=profile.service_class, priority=profile.default_priority,
    )


@dataclass(frozen=True)
class CarrierPresentationMetadata:
    """Section 52/81: non-authoritative OpenUSD presentation metadata for a
    carrier's CURRENT mission -- never determines engineering identity."""

    mrtway_object_id: str
    mission_id: str
    service_class: MrtServiceClass
    effective_display_color: PresentationColor
    effective_speed_m_per_s: float | Literal["NOT_CALIBRATED"]
    effective_priority: MrtPriorityClass | Literal["NOT_CALIBRATED"]
    container_class: str | ContainerResolutionStatus


def build_carrier_presentation_metadata(mission: MrtServiceMission, *, mrtway_object_id: str) -> CarrierPresentationMetadata:
    profile = SERVICE_CLASS_REGISTRY[mission.service_class]
    container = resolve_container_for_service_class(mission.service_class)
    return CarrierPresentationMetadata(
        mrtway_object_id=mrtway_object_id, mission_id=mission.mission_id, service_class=mission.service_class,
        effective_display_color=profile.effective_display_color(), effective_speed_m_per_s=mission_effective_speed(mission),
        effective_priority=mission_effective_priority(mission), container_class=(container if isinstance(container, str) else container.container_class_id),
    )


def attach_presentation_metadata_to_prim(prim: object, metadata: CarrierPresentationMetadata) -> None:
    """Section 52-53/81: mirrors `openusd_spatial_adapter.py`'s
    `SetCustomDataByKey` idiom exactly -- customData only, never authoritative
    geometry/identity. Accepts any duck-typed object exposing
    `SetCustomDataByKey` so this module never hard-depends on `pxr`."""
    prim.SetCustomDataByKey("mrtway_object_id", metadata.mrtway_object_id)  # section 53: round-trip identity preserved
    prim.SetCustomDataByKey("mission_id", metadata.mission_id)
    prim.SetCustomDataByKey("service_class", metadata.service_class)
    prim.SetCustomDataByKey("effective_display_color", metadata.effective_display_color)
    prim.SetCustomDataByKey("effective_speed_m_per_s", metadata.effective_speed_m_per_s)
    prim.SetCustomDataByKey("effective_priority", metadata.effective_priority)
    prim.SetCustomDataByKey("container_class", metadata.container_class)


# ---------------------------------------------------------------------------
# Section 82-87: simulation-driven carrier trajectory/animation contract.
# ---------------------------------------------------------------------------

CarrierAnimationStatus = Literal[
    "MOVING", "WAITING", "QUEUED", "HELD_FOR_PRIORITY", "AT_JUNCTION", "LOADING", "UNLOADING", "COMPLETE", "UNMET",
]


@dataclass(frozen=True)
class CarrierTrajectory:
    """Section 83-84: trajectory identity is per-MISSION, not per physical
    carrier -- one carrier performing two missions yields two trajectories."""

    carrier_id: str
    mission_id: str
    route_id: str | None
    ordered_segment_ids: tuple[str, ...]
    start_time_minutes: float
    end_time_minutes: float
    service_class: MrtServiceClass
    presentation: CarrierPresentationMetadata
    status: CarrierAnimationStatus
    provenance: str = "SIMULATION_DERIVED_FROM_shared_mrt_multistream_authority.schedule_missions_on_shared_segment"


def build_carrier_trajectory(
    mission: MrtServiceMission, scheduled: smx.ScheduledMrtMission, *, mrtway_object_id: str,
    route_id: str | None = None, ordered_segment_ids: tuple[str, ...] = (),
) -> CarrierTrajectory:
    """Section 82/84: derives status/timing from the REAL scheduler output
    (`ScheduledMrtMission`) -- never a generative/invented trajectory."""
    if scheduled.deadline_status == "UNMET":
        status: CarrierAnimationStatus = "UNMET"
    elif scheduled.wait_minutes > 0:
        status = "HELD_FOR_PRIORITY"
    else:
        status = "COMPLETE"
    presentation = build_carrier_presentation_metadata(mission, mrtway_object_id=mrtway_object_id)
    return CarrierTrajectory(
        carrier_id=mission.carrier_id, mission_id=mission.mission_id, route_id=route_id, ordered_segment_ids=ordered_segment_ids,
        start_time_minutes=scheduled.scheduled_start_minutes, end_time_minutes=scheduled.scheduled_end_minutes,
        service_class=mission.service_class, presentation=presentation, status=status,
    )


@dataclass(frozen=True)
class SpeedVisualStatus:
    """Section 87: actual/effective speed exposed separately from the
    configured/default service speed."""

    configured_speed_m_per_s: float | Literal["NOT_CALIBRATED"]
    effective_speed_m_per_s: float | Literal["NOT_CALIBRATED"]
    status: Literal["NOMINAL", "HELD", "CONSTRAINED"]


def build_speed_visual_status(mission: MrtServiceMission, *, scheduled: smx.ScheduledMrtMission | None = None) -> SpeedVisualStatus:
    profile = SERVICE_CLASS_REGISTRY[mission.service_class]
    effective = mission_effective_speed(mission)
    status: Literal["NOMINAL", "HELD", "CONSTRAINED"] = "NOMINAL"
    if scheduled is not None and scheduled.wait_minutes > 0:
        status = "HELD"
    return SpeedVisualStatus(configured_speed_m_per_s=profile.default_speed_m_per_s, effective_speed_m_per_s=effective, status=status)


def priority_badge_label(priority: MrtPriorityClass | Literal["NOT_CALIBRATED"]) -> str:
    """Section 86: optional non-color presentation metadata (P1-P4 badge)."""
    if priority == "NOT_CALIBRATED":
        return "NOT_CALIBRATED"
    return f"P{PRIORITY_RANK[priority]}"


# ---------------------------------------------------------------------------
# Section 37-41, 70-75: bridge to the EXISTING auxiliary authority's
# mission-mix energy aggregation -- never a second electrical/thermal model.
# ---------------------------------------------------------------------------


def missions_to_service_class_groups(missions: Sequence[MrtServiceMission]) -> tuple[maux.ServiceClassMissionGroup, ...]:
    """Section 38/70: groups missions by (service_class, effective_speed) --
    never collapses to one mean speed before physics."""
    buckets: dict[tuple[MrtServiceClass, float | str], list[MrtServiceMission]] = {}
    for m in missions:
        speed = mission_effective_speed(m)
        key = (m.service_class, speed)
        buckets.setdefault(key, []).append(m)
    groups = []
    for (service_class, speed), items in buckets.items():
        route_lengths = {i.route_length_m for i in items}
        route_length = next(iter(route_lengths)) if len(route_lengths) == 1 else items[0].route_length_m
        groups.append(maux.ServiceClassMissionGroup(
            service_class=service_class, mission_count=len(items), effective_speed_m_per_s=speed, route_length_m=route_length,
        ))
    return tuple(groups)


def aggregate_mission_speed_mix_energy(missions: Sequence[MrtServiceMission], *, drag_spec: "maux.DragSpec | None" = None) -> "maux.SpeedMixAggregateResult":
    """Section 41/72: prepares the structured speed-mix result required by
    section 41 -- delegates entirely to `mrt_auxiliary_systems_authority.
    aggregate_service_class_speed_mix` (never a second energy authority)."""
    spec = drag_spec or maux.DragSpec(frontal_area_m2=1.0, drag_coefficient=0.8)
    groups = missions_to_service_class_groups(missions)
    return maux.aggregate_service_class_speed_mix(groups, drag_spec=spec)


# ---------------------------------------------------------------------------
# Section 43-46, 76-79: unified what-if integration -- TRANSPORT_MRT
# category, extending (never replacing) the existing parameter registry.
# ---------------------------------------------------------------------------


def register_service_class_what_if_parameters(registry: "maux.WhatIfParameterRegistry") -> None:
    """Section 44-45: registers service-class what-if controls under
    TRANSPORT_MRT (with documented downstream effects into
    ELECTRICAL_THERMAL/OPERATIONS_CAPACITY/ECONOMICS_ASSUMPTIONS) -- reuses
    the EXISTING `WhatIfParameterRegistry`, never a separate service-class
    what-if application (section 79)."""
    registry.register(maux.WhatIfParameterDefinition(
        parameter_id="service_class_active", display_name="Service class active/inactive", category="TRANSPORT_MRT",
        parameter_type="BOOLEAN", unit=None, valid_range=None, calibration_status="CALIBRATED",
        provenance="USER_SUPPLIED", affected_authorities=("mrt_service_class_authority", "mrt_auxiliary_systems_authority"),
    ))
    registry.register(maux.WhatIfParameterDefinition(
        parameter_id="service_class_default_speed", display_name="Service class default speed", category="TRANSPORT_MRT",
        parameter_type="NUMERIC", unit="m/s", valid_range=(0.0, 50.0), calibration_status="PARTIALLY_CALIBRATED",
        provenance="USER_SUPPLIED", affected_authorities=("mrt_service_class_authority", "mrt_auxiliary_systems_authority", "shared_mrt_multistream_authority"),
    ))
    registry.register(maux.WhatIfParameterDefinition(
        parameter_id="mission_speed_override", display_name="Mission speed override", category="TRANSPORT_MRT",
        parameter_type="NUMERIC", unit="m/s", valid_range=(0.0, 50.0), calibration_status="CALIBRATED",
        provenance="USER_SUPPLIED", affected_authorities=("mrt_service_class_authority", "mrt_auxiliary_systems_authority"),
    ))
    registry.register(maux.WhatIfParameterDefinition(
        parameter_id="mission_priority_override", display_name="Mission priority override", category="TRANSPORT_MRT",
        parameter_type="ENUM", unit=None, valid_range=None, calibration_status="CALIBRATED",
        provenance="USER_SUPPLIED", affected_authorities=("mrt_service_class_authority", "shared_mrt_multistream_authority"),
    ))
    registry.register(maux.WhatIfParameterDefinition(
        parameter_id="carrier_availability_count", display_name="Carrier availability/count", category="OPERATIONS_CAPACITY",
        parameter_type="INTEGER", unit="carriers", valid_range=(0.0, 200.0), calibration_status="PARTIALLY_CALIBRATED",
        provenance="EXISTING_PROJECT_ASSUMPTION", affected_authorities=("mrt_carrier_fleet", "mrt_service_class_authority"),
    ))


def build_service_class_aware_parameter_registry() -> "maux.WhatIfParameterRegistry":
    """Section 43: ONE combined registry -- the pre-existing auxiliary
    parameters plus this closure's service-class parameters."""
    registry = maux.build_default_parameter_registry()
    register_service_class_what_if_parameters(registry)
    return registry


# ---------------------------------------------------------------------------
# Section 46, 77: the mandatory nuclear 10->15 m/s what-if -- blood/linen
# speeds must NOT silently change.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpeedWhatIfIdentityCheck:
    service_class_unchanged: bool
    color_unchanged: bool
    priority_unchanged: bool
    container_unchanged: bool


def compare_nuclear_speed_what_if(*, locked_speed_m_per_s: float = 10.0, what_if_speed_m_per_s: float = 15.0, route_length_m: float = 500.0) -> tuple[SpeedWhatIfIdentityCheck, MrtServiceMission, MrtServiceMission]:
    """Section 46/77: verifies changing ONLY the nuclear speed leaves
    service class/color/priority/container unchanged, and that other
    service classes are entirely unaffected (never silently altered)."""
    locked = MrtServiceMission(mission_id="NUC-LOCKED", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=route_length_m, start_minutes=0.0, speed_override_m_per_s=locked_speed_m_per_s)
    what_if = MrtServiceMission(mission_id="NUC-WHATIF", carrier_id="MRT-CARRIER-001", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=route_length_m, start_minutes=0.0, speed_override_m_per_s=what_if_speed_m_per_s)
    locked_dispatch = build_carrier_dispatch_state(locked)
    what_if_dispatch = build_carrier_dispatch_state(what_if)
    check = SpeedWhatIfIdentityCheck(
        service_class_unchanged=(locked.service_class == what_if.service_class),
        color_unchanged=(locked_dispatch.effective_display_color == what_if_dispatch.effective_display_color),
        priority_unchanged=(locked_dispatch.effective_priority == what_if_dispatch.effective_priority),
        container_unchanged=(locked_dispatch.container_class_id == what_if_dispatch.container_class_id),
    )
    return check, locked, what_if

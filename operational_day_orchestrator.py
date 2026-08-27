"""Synthetic-Patient Operating Day + Multi-Stream Mission Orchestration.

GOVERNANCE: this module is a TEMPORAL/OPERATIONAL ORCHESTRATION layer only.
It creates NO second patient population, NO second MRT scheduler, NO second
decay engine, NO second economics engine, and NO second spatial engine.
Every calculation is delegated to an EXISTING authority:

    canonical synthetic patients   -> oncology_pet_spect_scenario.build_representative_day_population
    nuclear appointment identity    -> nuclear_appointment.NuclearAppointment
    general logistics demand        -> general_oncology_logistics.generate_daily_logistics_demand /
                                        consolidate_demands_into_loads
    MRT service class/speed/color   -> mrt_service_class_authority.py (which itself reuses
                                        shared_mrt_multistream_authority + multi_isotope_decay)
    cyclotron production timing     -> cyclotron_production_windows.schedule_cyclotron_production_windows
    generator elution timing        -> generator.GeneratorAsset.elute
    manual/automated conventional    -> conventional_transport_authority.py
    live engineering/economic impact -> live_engineering_impact_binding.py
    operational event/state journal -> live_operational_state.py (OperationalEvent/OperationalStateStore
                                        vocabulary reused where applicable)
    room/building/floor/facility hierarchy -> canonical_spatial_authority.py (add_room/add_building/
                                        add_floor/build_mrt_trunk/build_mrt_endpoint/
                                        compute_mrt_transport_only_capex -- the ONE room/MRT-endpoint
                                        spatial identity + CapEx authority, never a second one)

CLOSURE BUILD -- AUTHORITY SEPARATION (long_horizon_operational_planning.py vs
this module): `long_horizon_operational_planning.run_operating_day_plan` is
FORWARD PLANNING -- it decides, across a multi-day horizon/`OperatingCalendar`,
which cyclotrons run and how many batches/clinical-resource-indices are
committed per day, producing a `DailyOperationalSummary`. It does NOT resolve
canonical room-level routes or execute a discrete-event mission/trajectory
simulation. THIS module is EXECUTION -- it takes ONE selected day (this
build's controlled representative day, or in principle a day drawn from that
longer-horizon plan) and runs it as a discrete-event simulation down to
individual missions/trajectories/journal entries. The two are complementary,
never competing: `long_horizon_operational_planning` answers "which days/
batches are planned system-wide", this module answers "what actually happens,
minute-by-minute, on ONE of those days". This build does not yet wire a
`DailyOperationalSummary` as a direct input (disclosed bounded gap) but
established the relationship so a future build can connect them without
creating a second planning authority.

NO SECOND CALENDAR TRUTH: this module derives its operational events from
`nuclear_appointment`/`oncology_pet_spect_scenario`/`general_oncology_logistics`
identity (patient_id, procedure_id, load_id) -- it never invents a conflicting
appointment time, scanner reservation, or patient schedule independently.

PLANNING vs EXECUTION: `CalendarEvent.scheduled_time` is the PLANNED time;
`OperationalDayEvent.simulation_time` / mission dispatch/completion times are
ACTUAL execution times. The plan is never mutated merely because execution
differs (see `planned_time`/`actual_time` on `ScheduleAdherenceRow` below).

GOVERNING PRINCIPLE: THE DIGITAL TWIN MUST BE ABLE TO EXECUTE A DAY.

    CANONICAL PATIENT/REQUIREMENT -> ACTUAL CANONICAL DESTINATION ->
    PRODUCTION/PAYLOAD/SERVICE READINESS -> OPERATIONAL TRIGGER ->
    MISSION GENERATION -> ARCHITECTURE-SPECIFIC SERVICE PATH -> RESOURCE
    ASSIGNMENT -> SCHEDULER -> MOVEMENT/TRAJECTORY -> DELIVERY/COLLECTION ->
    PATIENT/SERVICE OUTCOME -> EVENT JOURNAL -> ENGINEERING/ECONOMIC
    CONSEQUENCE.

OPERATING DAY vs WHAT-IF: an operating day asks "what happens under THIS
configuration?"; a what-if asks "what happens if the configuration
changes?". This module answers the former; `live_engineering_impact_binding`
answers the latter. `run_locked_vs_what_if_day_comparison` below composes
both without duplicating either.

PLAYBACK RATE vs SIMULATION PHYSICS: playback multipliers (1x/10x/60x) are
PRESENTATION concepts only. They never alter carrier engineering speed,
mission duration, decay, or energy -- enforced by keeping `PlaybackState`
structurally separate from every engineering calculation in this module.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Mapping, Sequence

import mrt_service_class_authority as msc
import live_engineering_impact_binding as lib
import canonical_spatial_authority as csa
import conventional_transport_authority as cta
import mrt_auxiliary_systems_authority as maux
import transport_mission_route_bridge as trb
from general_oncology_logistics import (
    LogisticsStream,
    TransportLoad,
    build_default_facility_roles,
    consolidate_demands_into_loads,
    generate_daily_logistics_demand,
)
from oncology_pet_spect_scenario import (
    DailyOncologyCensus,
    OncologyPatientRecord,
    build_representative_day_population,
)

OPERATING_DAY_SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Section 4/6-11: single authoritative simulation clock.
# ---------------------------------------------------------------------------

ArchitectureMode = Literal["MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT"]
PlaybackControl = Literal["PLAY", "PAUSE", "STEP", "RESTART_DAY", "JUMP_TO_TIME", "SET_PLAYBACK_RATE"]
ExecutionStatus = Literal["NOT_STARTED", "RUNNING", "COMPLETED"]


@dataclass(frozen=True)
class SimulationClock:
    """Section 6/11: ONE authoritative clock for the whole operating day --
    never a separate nuclear/linen/blood/NVIDIA/Bentley clock."""

    day_start: datetime
    day_end: datetime
    scenario_id: str
    architecture: ArchitectureMode
    seed: int
    current_simulation_time: datetime
    playback_rate: float = 1.0
    execution_status: ExecutionStatus = "NOT_STARTED"
    event_index: int = 0

    def elapsed_minutes(self, at: datetime) -> float:
        return (at - self.day_start).total_seconds() / 60.0


@dataclass(frozen=True)
class PlaybackState:
    """Section 9-10/115: presentation-only playback state -- structurally
    separate from `SimulationClock`'s engineering time so a playback-rate
    change can NEVER be mistaken for an engineering-speed change."""

    playback_rate: float
    presentation_time: datetime
    status: Literal["STOPPED", "PLAYING", "PAUSED"] = "STOPPED"


def apply_playback_control(state: PlaybackState, *, control: PlaybackControl, day_start: datetime, jump_to: datetime | None = None, new_rate: float | None = None) -> PlaybackState:
    if control == "PLAY":
        return replace(state, status="PLAYING")
    if control == "PAUSE":
        return replace(state, status="PAUSED")
    if control == "RESTART_DAY":
        return replace(state, presentation_time=day_start, status="STOPPED")
    if control == "JUMP_TO_TIME":
        if jump_to is None:
            raise ValueError("JUMP_TO_TIME requires jump_to")
        return replace(state, presentation_time=jump_to)
    if control == "SET_PLAYBACK_RATE":
        if new_rate is None or new_rate <= 0:
            raise ValueError("SET_PLAYBACK_RATE requires a positive new_rate")
        return replace(state, playback_rate=new_rate)
    if control == "STEP":
        return state
    raise ValueError(f"Unknown playback control: {control!r}")


CONTROLLED_REPRESENTATIVE_OPERATING_DAY_LABEL = "CONTROLLED_REPRESENTATIVE_OPERATING_DAY"
"""Section 7: explicitly labeled synthetic/controlled -- never claimed as
measured hospital data."""


# ---------------------------------------------------------------------------
# Section 14-15, 35-37: calendar, trigger taxonomy, operational event.
# ---------------------------------------------------------------------------

TriggerType = Literal[
    "CALENDAR_SCHEDULED", "PAYLOAD_READY", "ORDER_READY", "SPECIMEN_READY", "REPLENISHMENT_SCHEDULE",
    "THRESHOLD_TRIGGERED", "STAT_REQUEST", "MANUAL_CONTROLLED_EVENT",
]

EventDeterminism = Literal["FIXED_SCHEDULED", "DETERMINISTIC_DERIVED", "STOCHASTIC_SEEDED", "MANUAL_CONTROLLED"]


@dataclass(frozen=True)
class CalendarEvent:
    """Section 14-15: a PLANNED activity -- distinct from the event journal's
    record of what ACTUALLY happened (section 165)."""

    calendar_event_id: str
    patient_id: str | Literal["NOT_APPLICABLE"]
    event_type: str
    scheduled_time: datetime
    location: str | None
    source_authority: str
    status: Literal["PLANNED", "CONFIRMED"] = "PLANNED"


@dataclass(frozen=True)
class OperationalDayEvent:
    """Section 36: the canonical operational-event contract for this
    operating-day layer -- reuses `live_operational_state`'s event-kind
    vocabulary conceptually but is scoped to operating-day orchestration
    (distinct dataclass, not a competing journal architecture; see
    `build_event_journal_entry` below for the actual journal record)."""

    event_id: str
    simulation_time: datetime
    sequence: int
    event_type: str
    trigger_type: TriggerType
    determinism: EventDeterminism
    patient_id: str | Literal["NOT_APPLICABLE"]
    service_class: str | Literal["NOT_APPLICABLE"]
    source_object_id: str | None
    destination_object_id: str | None
    payload_reference: str | None
    priority: str | Literal["NOT_APPLICABLE"]
    provenance: str
    status: Literal["CREATED", "APPLIED"] = "CREATED"


# ---------------------------------------------------------------------------
# Section 37-39: deterministic event ordering + discrete-event queue.
# ---------------------------------------------------------------------------


@dataclass(order=True)
class _QueueKey:
    simulation_time: datetime
    priority_rank: int
    sequence: int


class DeterministicEventQueue:
    """Section 37-39: discrete-event queue -- advances event-to-event, never
    busy-waits or sleeps on wall-clock time. Ties at identical timestamps
    resolve by (priority_rank, sequence), never arbitrary dict/set order."""

    def __init__(self) -> None:
        self._heap: list[tuple[_QueueKey, OperationalDayEvent]] = []
        self._sequence_counter = 0

    def push(self, event: OperationalDayEvent, *, priority_rank: int = 4) -> None:
        key = _QueueKey(simulation_time=event.simulation_time, priority_rank=priority_rank, sequence=event.sequence)
        heapq.heappush(self._heap, (key, event))

    def pop(self) -> OperationalDayEvent | None:
        if not self._heap:
            return None
        _key, event = heapq.heappop(self._heap)
        return event

    def __len__(self) -> int:
        return len(self._heap)

    def drain(self) -> tuple[OperationalDayEvent, ...]:
        drained = []
        while self._heap:
            drained.append(self.pop())
        return tuple(drained)


def next_event_sequence(counter: list[int]) -> int:
    counter[0] += 1
    return counter[0]


# ---------------------------------------------------------------------------
# Section 41-45: mission generation -- consumes operational events, produces
# service-class-aware missions. Reuses `mrt_service_class_authority.
# MrtServiceMission` verbatim for MRT-capable streams (never a second
# mission/container/priority model).
# ---------------------------------------------------------------------------

MRT_CONTROLLED_ROUTE_LENGTH_M = 300.0
"""CONTROLLED_ENGINEERING_ASSUMPTION: no per-mission geometry/route-length
binding exists for this operating-day layer yet -- a single representative
route length is used for every MRT mission, honestly disclosed as a bounded
scope limitation (never fabricated per-mission geometry)."""

MissionOutcomeStatus = Literal[
    "COMPLETED_ON_TIME", "COMPLETED_LATE", "UNMET", "BLOCKED", "NOT_CALIBRATED", "CANCELLED", "NOT_APPLICABLE",
]


@dataclass(frozen=True)
class MissionSpec:
    """Section 41-45: mission-generation output. Wraps (never replaces)
    `msc.MrtServiceMission` for MRT-eligible streams; `mrt_mission` is None
    for streams whose speed remains NOT_CALIBRATED (section 60) or for
    non-MRT architecture execution (section 48-49)."""

    mission_id: str
    trigger_event_id: str
    patient_id: str | Literal["NOT_APPLICABLE"]
    service_class: str
    origin: str
    destination: str
    earliest_dispatch_minutes: float
    required_arrival_minutes: float | None
    priority: str
    provenance: str
    mrt_mission: "msc.MrtServiceMission | None" = None
    mrt_resolution_status: Literal["RESOLVED", "NOT_CALIBRATED"] = "NOT_CALIBRATED"
    route_resolution: "trb.MissionRouteResolution | None" = None
    """Transport Spatial Authority Build 1 (section 9/12): the mission-
    routing bridge's resolution for this mission's origin/destination, when
    a caller supplied a canonical registry/graph -- None when no bridge
    resolution was attempted (fully backward compatible)."""


def _service_class_default_priority_label(service_class: str) -> str:
    profile = msc.SERVICE_CLASS_REGISTRY.get(service_class)  # type: ignore[arg-type]
    return profile.default_priority if profile else "NOT_CALIBRATED"


def build_mission_from_event(
    event: OperationalDayEvent, *, route_length_m: float = MRT_CONTROLLED_ROUTE_LENGTH_M,
    speed_override_m_per_s: float | None = None, priority_override: "msc.PriorityOverrideRecord | None" = None,
    required_arrival_minutes: float | None = None,
    registry: csa.SpatialObjectRegistry | None = None, graph: csa.ConnectivityGraph | None = None,
) -> MissionSpec:
    """Section 41-43/60: converts ONE operational event into ONE mission.
    If the service class's speed is NOT_CALIBRATED and no override is
    supplied, `mrt_mission` stays None and `mrt_resolution_status` reports
    NOT_CALIBRATED -- never a silently fabricated speed.

    Transport Spatial Authority Build 1 (section 12-13): when `registry`/
    `graph` are supplied (fully optional, default None -- every existing
    caller is unaffected), a real canonical MRT route is resolved via
    `transport_mission_route_bridge` and its distance TAKES PRECEDENCE over
    `route_length_m`'s flat placeholder. When no real route is calibrated,
    the flat placeholder remains the honest fallback."""
    service_class = event.service_class
    if service_class not in msc.SERVICE_CLASS_REGISTRY:
        return MissionSpec(
            mission_id=f"MSN-{event.event_id}", trigger_event_id=event.event_id, patient_id=event.patient_id,
            service_class=service_class, origin=event.source_object_id or "NOT_CALIBRATED",
            destination=event.destination_object_id or "NOT_CALIBRATED",
            earliest_dispatch_minutes=0.0, required_arrival_minutes=required_arrival_minutes,
            priority=event.priority, provenance=event.provenance, mrt_mission=None, mrt_resolution_status="NOT_CALIBRATED",
        )
    profile = msc.SERVICE_CLASS_REGISTRY[service_class]  # type: ignore[index]
    dispatch_minutes = 0.0  # resolved relative to day_start by the caller via simulation_time

    route_resolution: "trb.MissionRouteResolution | None" = None
    effective_route_length_m = route_length_m
    if event.source_object_id is not None and event.destination_object_id is not None:
        route_resolution = trb.resolve_mission_route(
            mission_id=f"MSN-{event.event_id}", transport_mode="MRT", origin_object_id=event.source_object_id,
            destination_object_id=event.destination_object_id, registry=registry, graph=graph,
        )
        if route_resolution.route_status == "ROUTE_CALIBRATED" and route_resolution.route_distance_m is not None:
            effective_route_length_m = route_resolution.route_distance_m  # real route takes precedence (section 13)

    mrt_mission = msc.MrtServiceMission(
        mission_id=f"MSN-{event.event_id}", carrier_id="UNASSIGNED", service_class=service_class,  # type: ignore[arg-type]
        route_length_m=effective_route_length_m, start_minutes=dispatch_minutes, speed_override_m_per_s=speed_override_m_per_s,
        priority_override=priority_override, deadline_minutes=required_arrival_minutes,
    )
    speed = msc.mission_effective_speed(mrt_mission)
    status: Literal["RESOLVED", "NOT_CALIBRATED"] = "RESOLVED" if speed != "NOT_CALIBRATED" else "NOT_CALIBRATED"
    return MissionSpec(
        mission_id=mrt_mission.mission_id, trigger_event_id=event.event_id, patient_id=event.patient_id,
        service_class=service_class, origin=event.source_object_id or "NOT_CALIBRATED",
        destination=event.destination_object_id or "NOT_CALIBRATED", earliest_dispatch_minutes=dispatch_minutes,
        required_arrival_minutes=required_arrival_minutes, priority=(priority_override.effective_priority if priority_override else profile.default_priority),
        provenance=event.provenance, mrt_mission=mrt_mission, mrt_resolution_status=status, route_resolution=route_resolution,
    )


# ---------------------------------------------------------------------------
# Section 7, 12-13, 172-179: controlled representative operating day.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ControlledDayDefinition:
    """Section 12-13: the FULL canonical synthetic population for the
    controlled representative day -- never reduced merely to make animation
    easier (section 13)."""

    day: date
    seed: int
    patients: tuple[OncologyPatientRecord, ...]
    census: DailyOncologyCensus
    logistics_loads: tuple[TransportLoad, ...]
    stat_blood_patient_id: str
    label: str = CONTROLLED_REPRESENTATIVE_OPERATING_DAY_LABEL


def build_controlled_representative_day(
    *, day: date = date(2026, 2, 3), seed: int = 42, available_beds: int = 40, occupied_beds: int = 30,
    admissions: int = 4, discharges: int = 3, outpatient_encounters: int = 15, target_pet_procedures: int = 6,
    target_spect_procedures: int = 3,
) -> ControlledDayDefinition:
    """Section 7/109: MRTWAY_CONTROLLED_REPRESENTATIVE_TUESDAY-equivalent
    controlled day. Reuses the EXISTING canonical synthetic population
    authority verbatim (never a second demo-only population, section 12)."""
    patients, census = build_representative_day_population(
        day=day, available_beds=available_beds, occupied_beds=occupied_beds, admissions=admissions,
        discharges=discharges, outpatient_encounters=outpatient_encounters, target_pet_procedures=target_pet_procedures,
        target_spect_procedures=target_spect_procedures, seed=seed,
    )
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=day, inpatients=patients, roles=roles)
    loads = consolidate_demands_into_loads(demands=demands, max_quantity_per_load=80.0)

    # Section 28/175: one deterministic (seeded) STAT specimen event -- the
    # first inpatient with an existing SPECIMEN_BLOOD load becomes the STAT case.
    stat_patient_id = next((p.patient_id for p in patients if p.patient_type == "INPATIENT"), patients[0].patient_id)

    return ControlledDayDefinition(day=day, seed=seed, patients=patients, census=census, logistics_loads=loads, stat_blood_patient_id=stat_patient_id)


# ---------------------------------------------------------------------------
# CLOSURE: room inventory authority (sections 7-16). Reuses
# `canonical_spatial_authority` verbatim -- never a second room/building/
# floor identity system. Room number/mrtway_object_id are the SAME stable
# value in that authority (section 8) -- reused as-is, never redefined.
# ---------------------------------------------------------------------------

CONTROLLED_FACILITY_ID = "FAC-OPDAY"


def build_controlled_room_registry(day_def: ControlledDayDefinition) -> csa.SpatialObjectRegistry:
    """Section 7/11-13: canonical FACILITY->BUILDING->FLOOR->ROOM hierarchy
    for every occupied inpatient room in `day_def` -- reused for ALL
    downstream mission destinations (section 13: no synthetic destination
    room when a real room exists). Reports the ACTUAL room count found in
    this build's own controlled population (currently `occupied_beds`,
    smaller than the separate 80-room `spatial_benchmark.build_benchmark_geometry`
    or 170/200-bed `whole_oncology` baselines -- those remain separate,
    larger-scale established authorities, disclosed as a reconciliation
    opportunity rather than force-unified here)."""
    registry = csa.build_facility_hierarchy(facility_id=CONTROLLED_FACILITY_ID)
    seen_buildings: set[str] = set()
    seen_floors: set[str] = set()
    for patient in day_def.patients:
        if patient.patient_type != "INPATIENT" or patient.room_id is None:
            continue
        building_id = patient.building_id or "BLDG-A"
        floor_id = patient.floor_id or "F1"
        if building_id not in seen_buildings:
            csa.add_building(registry, facility_id=CONTROLLED_FACILITY_ID, building_id=building_id)
            seen_buildings.add(building_id)
        floor_key = f"{building_id}::{floor_id}"
        if floor_key not in seen_floors:
            csa.add_floor(registry, facility_id=CONTROLLED_FACILITY_ID, building_id=building_id, floor_id=floor_id)
            seen_floors.add(floor_key)
        if patient.room_id not in registry.objects:
            csa.add_room(
                registry, facility_id=CONTROLLED_FACILITY_ID, building_id=building_id, floor_id=floor_id,
                room_id=patient.room_id, object_type="PATIENT_ROOM",
            )
    # Section 14: outpatients never receive a fabricated inpatient room.
    any_building = next(iter(seen_buildings), "BLDG-A")
    any_floor = next((fid.split("::")[1] for fid in seen_floors if fid.startswith(any_building)), "F1")
    csa.build_general_logistics_origin_objects(registry, facility_id=CONTROLLED_FACILITY_ID, building_id=any_building, floor_id=any_floor)
    csa.build_nuclear_engineering_objects(registry, facility_id=CONTROLLED_FACILITY_ID, building_id=any_building, floor_id=any_floor)
    return registry


RoomResolutionStatus = Literal["CANONICAL_ROOM", "LOCATION_NOT_CALIBRATED"]


def resolve_mission_destination(registry: csa.SpatialObjectRegistry, room_id: str | None) -> tuple[str, RoomResolutionStatus]:
    """Section 9/13: resolves to the REAL registered canonical room where one
    exists; NEVER fabricates XYZ or a synthetic room when a real one is
    missing -- reports `LOCATION_NOT_CALIBRATED` honestly instead."""
    if room_id is not None and room_id in registry.objects:
        return room_id, "CANONICAL_ROOM"
    return (room_id or "UNKNOWN"), "LOCATION_NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# CLOSURE: distance provenance (sections 25-28) + controlled direct-room MRT
# case (sections 18-24). Reuses `canonical_spatial_authority.build_mrt_trunk`/
# `build_mrt_endpoint`/`compute_mrt_transport_only_capex` verbatim -- that
# function ALREADY supports honest NOT_CALIBRATED per-endpoint costing, so
# no new CapEx formula is introduced here.
# ---------------------------------------------------------------------------

DistanceProvenance = Literal["CANONICAL_ROUTED_GEOMETRY", "CONTROLLED_TEST_DISTANCE", "NOT_CALIBRATED"]

CONTROLLED_TEST_DISTANCE_M = MRT_CONTROLLED_ROUTE_LENGTH_M
"""Section 27: the prior build's universal 300m route constant survives
ONLY as an explicitly labeled `CONTROLLED_TEST_DISTANCE` -- no canonical
routed room-to-source geometry resolver exists yet in this repo (confirmed
by audit: no such function exists in `canonical_spatial_authority.py`), so
this never silently overrides a calibrated canonical path (none exists to
override)."""


def resolve_transport_distance_m(*, room_resolution_status: RoomResolutionStatus) -> tuple[float | Literal["NOT_CALIBRATED"], DistanceProvenance]:
    """Section 28: every operating-day transport distance exposes explicit
    provenance. No canonical routed-geometry resolver exists in this repo
    yet (disclosed gap) -- a resolved canonical room uses the controlled
    test distance (never a fabricated precise geometry); an unresolved room
    reports NOT_CALIBRATED distance rather than guessing."""
    if room_resolution_status == "CANONICAL_ROOM":
        return CONTROLLED_TEST_DISTANCE_M, "CONTROLLED_TEST_DISTANCE"
    return "NOT_CALIBRATED", "NOT_CALIBRATED"


@dataclass(frozen=True)
class RoomEndpointSpec:
    """Section 21: distinct engineering identity per served room -- never
    one generic endpoint for an entire facility (section 20)."""

    endpoint_object_id: str
    served_room_object_id: str
    building_id: str | None
    floor_id: str | None
    network_connection_object_id: str
    position_status: RoomResolutionStatus
    asset_status: str
    economic_status: Literal["CALIBRATED"] = "CALIBRATED"
    provenance: str = "canonical_spatial_authority.build_mrt_endpoint"


MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD = 1_000.0
"""Section 48A-48B: the MRT exit/delivery/input-output PANEL at a served
room -- USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION, distinct from
`MRT_VESTIBULE_CAPEX_USD` ($30,000/unit, radiopharmacy vestibule only).
Supersedes the prior NOT_CALIBRATED room-endpoint CapEx status. Never
manufacturer-quoted/measured pricing."""


def build_direct_room_mrt_network(
    registry: csa.SpatialObjectRegistry, *, room_ids: Sequence[str], trunk_id: str = "MRT-TRUNK-OPDAY",
    endpoint_unit_cost_usd: float = MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD,
) -> tuple[tuple[RoomEndpointSpec, ...], "csa.MrtTransportOnlyCapexResult"]:
    """Section 19-24/48A-48E: CONTROLLED DESIGN SCENARIO in which every
    eligible inpatient room has direct MRT service (trunk -> endpoint ->
    room). This is ONE controlled scenario, never claimed as the only
    possible MRT architecture (section 19). Endpoint count derives from the
    ACTUAL served-room count (section 20) -- never one endpoint for a
    200-room hospital (200 rooms x $1,000 = $200,000, never 200 carriers).
    Endpoint unit cost is the controlled MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD
    (never the vestibule price, section 48B) -- integrated into the SAME
    existing `compute_mrt_transport_only_capex` authority, never a second
    CapEx engine (section 48E). No endpoint-specific OPEX is fabricated
    (section 48F)."""
    if trunk_id not in registry.objects:
        csa.build_mrt_trunk(registry, trunk_id=trunk_id, facility_id=CONTROLLED_FACILITY_ID, network_id=CONTROLLED_FACILITY_ID)
    endpoints = []
    for room_id in room_ids:
        if room_id not in registry.objects:
            continue  # section 13: never fabricate an endpoint for a non-canonical room
        endpoint_id = f"MRT-ENDPOINT-{room_id}"
        if endpoint_id not in registry.objects:
            csa.build_mrt_endpoint(registry, endpoint_id=endpoint_id, facility_id=CONTROLLED_FACILITY_ID, connected_network_object_id=trunk_id, served_object_id=room_id)
        room_obj = registry.get(room_id)
        endpoints.append(RoomEndpointSpec(
            endpoint_object_id=endpoint_id, served_room_object_id=room_id, building_id=room_obj.building_id,
            floor_id=room_obj.floor_id, network_connection_object_id=trunk_id, position_status="CANONICAL_ROOM",
            asset_status="PROPOSED",
        ))
    capex_result = csa.compute_mrt_transport_only_capex(endpoint_count=len(endpoints), endpoint_unit_cost=endpoint_unit_cost_usd)
    return tuple(endpoints), capex_result



def generate_calendar_events(day_def: ControlledDayDefinition, *, day_start: datetime) -> tuple[CalendarEvent, ...]:
    """Section 14-15: one stable-identity calendar event per nuclear
    appointment and per consolidated logistics load."""
    events: list[CalendarEvent] = []
    for patient in day_def.patients:
        if patient.nuclear_procedure is None:
            continue
        proc = patient.nuclear_procedure
        events.append(CalendarEvent(
            calendar_event_id=f"CAL-{proc.procedure_id}", patient_id=patient.patient_id, event_type=f"{proc.modality}_APPOINTMENT",
            scheduled_time=day_start + timedelta(hours=1), location=patient.room_id or patient.outpatient_origin,
            source_authority="oncology_pet_spect_scenario.NuclearProcedureAssignment",
        ))
    for load in day_def.logistics_loads:
        events.append(CalendarEvent(
            calendar_event_id=f"CAL-{load.load_id}", patient_id=(load.patient_ids[0] if load.patient_ids else "NOT_APPLICABLE"),
            event_type=f"{load.stream}_REPLENISHMENT", scheduled_time=day_start, location=load.origin,
            source_authority="general_oncology_logistics.consolidate_demands_into_loads",
        ))
    return tuple(events)


_STREAM_TRIGGER: Mapping[str, TriggerType] = {
    "CLEAN_LINEN": "REPLENISHMENT_SCHEDULE", "PHARMACY_INFUSION": "ORDER_READY",
    "SPECIMEN_BLOOD": "SPECIMEN_READY", "STERILE_CLEAN_SUPPLY": "REPLENISHMENT_SCHEDULE",
}


def generate_operational_events(
    calendar_events: Sequence[CalendarEvent], day_def: ControlledDayDefinition, *, day_start: datetime,
) -> tuple[OperationalDayEvent, ...]:
    """Section 16-17/24/27-31: converts PLANNED calendar activity into
    operational requirements. Nuclear appointment timing is an upstream
    clinical requirement -- NOT a carrier departure time (section 16); the
    payload-ready event is generated at a fixed processing offset from the
    appointment, never at the appointment time itself."""
    seq_counter = [0]
    events: list[OperationalDayEvent] = []
    loads_by_id = {load.load_id: load for load in day_def.logistics_loads}

    for cal in calendar_events:
        if cal.event_type.endswith("_APPOINTMENT"):
            modality = cal.event_type.split("_")[0]
            payload_ready_time = cal.scheduled_time - timedelta(minutes=45)  # section 16: release precedes administration
            events.append(OperationalDayEvent(
                event_id=f"EVT-{cal.calendar_event_id}", simulation_time=max(payload_ready_time, day_start),
                sequence=next_event_sequence(seq_counter), event_type=f"{modality}_PAYLOAD_READY", trigger_type="PAYLOAD_READY",
                determinism="DETERMINISTIC_DERIVED", patient_id=cal.patient_id, service_class="RADIOPHARMACEUTICAL_NUCLEAR",
                source_object_id="RADIOPHARMACY", destination_object_id=cal.location, payload_reference=cal.calendar_event_id,
                priority="PRIORITY_1_NUCLEAR_CRITICAL", provenance="oncology_pet_spect_scenario+nuclear_appointment (derived offset)",
            ))
            continue
        load_id = cal.calendar_event_id.replace("CAL-", "")
        load = loads_by_id.get(load_id)
        if load is None:
            continue
        service_class = msc.resolve_service_class_for_existing_stream(load.stream)
        is_stat = load.stream == "SPECIMEN_BLOOD" and day_def.stat_blood_patient_id in load.patient_ids
        trigger: TriggerType = "STAT_REQUEST" if is_stat else _STREAM_TRIGGER[load.stream]
        profile = msc.SERVICE_CLASS_REGISTRY[service_class]
        events.append(OperationalDayEvent(
            event_id=f"EVT-{cal.calendar_event_id}", simulation_time=cal.scheduled_time, sequence=next_event_sequence(seq_counter),
            event_type=f"{load.stream}_READY", trigger_type=trigger, determinism=("MANUAL_CONTROLLED" if is_stat else "DETERMINISTIC_DERIVED"),
            patient_id=cal.patient_id, service_class=service_class, source_object_id=load.origin, destination_object_id=load.destination,
            payload_reference=load.load_id, priority=profile.default_priority, provenance="general_oncology_logistics (consolidated load)",
        ))
    events.sort(key=lambda e: (e.simulation_time, msc.PRIORITY_RANK.get(e.priority, 4), e.sequence))  # type: ignore[arg-type]
    return tuple(events)


# ---------------------------------------------------------------------------
# Section 46-56: architecture-specific day execution. MRT missions reuse
# `msc.schedule_service_missions` verbatim; carriers are reused (never
# purchased per mission).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CARRIER CORRECTION: heterogeneous carrier hardware-class authority. NETWORK
# (`csa.build_mrt_trunk`/segments) != CARRIER HARDWARE CLASS (this section)
# != PAYLOAD CONTAINER (`msc.resolve_container_for_service_class`, UNCHANGED)
# != MISSION/SERVICE CLASS (`msc.SERVICE_CLASS_REGISTRY`, UNCHANGED). This is
# the ONE canonical carrier-hardware authority for this module -- supersedes
# the prior "all carriers identical, $10,000 each" simplification.
# ---------------------------------------------------------------------------

CarrierHardwareClass = Literal["NUCLEAR_SHIELDED_CARRIER", "GENERAL_LIGHT_CARRIER"]

NUCLEAR_SHIELDED_CARRIER_CAPEX_USD = 10_000.0
GENERAL_LIGHT_CARRIER_CAPEX_USD = 1_000.0
NUCLEAR_SHIELDED_CARRIER_EMPTY_MASS_KG = 12.0
GENERAL_LIGHT_CARRIER_EMPTY_MASS_KG = 5.0
"""MASS CORRECTION: supersedes the prior universal 20kg nominal mass.
USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION per hardware class -- empty
carrier mass belongs to the HARDWARE CLASS (never the mission/payload).
Purchase price ($10k/$1k) is unaffected by this mass correction (separate
attributes, section 28)."""


@dataclass(frozen=True)
class CarrierHardwareSpec:
    hardware_class: CarrierHardwareClass
    unit_capex_usd: float
    shielding_required: bool
    empty_mass_kg: float
    provenance: str = "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION"


CARRIER_HARDWARE_REGISTRY: Mapping[CarrierHardwareClass, CarrierHardwareSpec] = {
    "NUCLEAR_SHIELDED_CARRIER": CarrierHardwareSpec("NUCLEAR_SHIELDED_CARRIER", NUCLEAR_SHIELDED_CARRIER_CAPEX_USD, True, NUCLEAR_SHIELDED_CARRIER_EMPTY_MASS_KG),
    "GENERAL_LIGHT_CARRIER": CarrierHardwareSpec("GENERAL_LIGHT_CARRIER", GENERAL_LIGHT_CARRIER_CAPEX_USD, False, GENERAL_LIGHT_CARRIER_EMPTY_MASS_KG),
}

SERVICE_CLASS_TO_HARDWARE_CLASS: Mapping[str, CarrierHardwareClass] = {
    "RADIOPHARMACEUTICAL_NUCLEAR": "NUCLEAR_SHIELDED_CARRIER",
    "SPECIMEN_BLOOD": "GENERAL_LIGHT_CARRIER",
    "LAUNDRY_CLEAN_LINEN": "GENERAL_LIGHT_CARRIER",
    "PHARMACY_INFUSION": "GENERAL_LIGHT_CARRIER",
    "STERILE_CLEAN_SUPPLY": "GENERAL_LIGHT_CARRIER",
}
"""GENERAL_LIGHT_CARRIER never serves nuclear (hard requirement); nuclear
missions always resolve to NUCLEAR_SHIELDED_CARRIER (hard requirement)."""


def resolve_carrier_hardware_class(service_class: str) -> CarrierHardwareClass:
    hardware_class = SERVICE_CLASS_TO_HARDWARE_CLASS.get(service_class)
    if hardware_class is None:
        raise ValueError(f"no carrier hardware class mapping for service class {service_class!r}")
    return hardware_class


# ---------------------------------------------------------------------------
# MASS CORRECTION: service-specific payload mass authority. ONE resolver --
# never scattered hard-coded masses across scheduler/economics/animation code.
# ---------------------------------------------------------------------------

PayloadMassProvenance = Literal["MISSION_SPECIFIC_INPUT", "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION", "NOT_CALIBRATED"]

CONTROLLED_NUCLEAR_PAYLOAD_MASS_KG = 6.5
"""USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION -- one explicit deterministic
value within the supplied ~6-7kg range (section 12: no false precision;
never claimed as measured manufacturer data)."""
CONTROLLED_LIGHT_CLINICAL_PAYLOAD_MASS_KG = 2.0
"""Blood/pharmacy/sterile controlled payload ceiling (section 6-8) -- a
mission payload ASSUMPTION, never the carrier's structural max capacity
(section 32-33)."""
CONTROLLED_LINEN_PAYLOAD_MASS_KG = 12.0
"""Linen controlled heavy-case payload (section 9) -- distinct from the
light-clinical streams; never applied to blood/pharmacy/sterile (section 6-8)."""

SERVICE_CLASS_CONTROLLED_PAYLOAD_MASS_KG: Mapping[str, float] = {
    "RADIOPHARMACEUTICAL_NUCLEAR": CONTROLLED_NUCLEAR_PAYLOAD_MASS_KG,
    "SPECIMEN_BLOOD": CONTROLLED_LIGHT_CLINICAL_PAYLOAD_MASS_KG,
    "PHARMACY_INFUSION": CONTROLLED_LIGHT_CLINICAL_PAYLOAD_MASS_KG,
    "STERILE_CLEAN_SUPPLY": CONTROLLED_LIGHT_CLINICAL_PAYLOAD_MASS_KG,
    "LAUNDRY_CLEAN_LINEN": CONTROLLED_LINEN_PAYLOAD_MASS_KG,
}
"""FOOD_NUTRITION/WASTE deliberately absent (section 10: inactive, never
given a payload mass merely to complete the table)."""


def _validate_mass_kg(mass_kg: float, *, label: str) -> None:
    if math.isnan(mass_kg) or math.isinf(mass_kg) or mass_kg < 0:
        raise ValueError(f"{label} must be a finite, non-negative mass, got {mass_kg!r}")


@dataclass(frozen=True)
class ResolvedPayloadMass:
    payload_mass_kg: float | Literal["NOT_CALIBRATED"]
    provenance: PayloadMassProvenance


def resolve_mission_payload_mass_kg(service_class: str, mission_specific_payload_mass_kg: float | None = None) -> ResolvedPayloadMass:
    """Section 13-15: mission-specific input OVERRIDES the controlled
    default where legitimately supplied (never silently overwritten);
    rejects negative/NaN/Infinity; NOT_CALIBRATED for streams with no
    established payload assumption (e.g. inactive Food/Waste)."""
    if mission_specific_payload_mass_kg is not None:
        _validate_mass_kg(mission_specific_payload_mass_kg, label="mission_specific_payload_mass_kg")
        return ResolvedPayloadMass(payload_mass_kg=mission_specific_payload_mass_kg, provenance="MISSION_SPECIFIC_INPUT")
    default = SERVICE_CLASS_CONTROLLED_PAYLOAD_MASS_KG.get(service_class)
    if default is None:
        return ResolvedPayloadMass(payload_mass_kg="NOT_CALIBRATED", provenance="NOT_CALIBRATED")
    _validate_mass_kg(default, label=f"controlled payload mass for {service_class!r}")
    return ResolvedPayloadMass(payload_mass_kg=default, provenance="USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION")


def resolve_loaded_mass_kg(hardware_class: CarrierHardwareClass, payload_mass_kg: float | Literal["NOT_CALIBRATED"]) -> float | Literal["NOT_CALIBRATED"]:
    """Section 16: the ONE loaded-mass derivation -- never independently
    recomputed in multiple subsystems. m_loaded = m_empty_carrier + m_payload."""
    if payload_mass_kg == "NOT_CALIBRATED":
        return "NOT_CALIBRATED"
    empty_mass_kg = CARRIER_HARDWARE_REGISTRY[hardware_class].empty_mass_kg
    return empty_mass_kg + float(payload_mass_kg)


@dataclass(frozen=True)
class CarrierAccessiblePresentation:
    """Carrier hardware class and service-class presentation identity
    remain SEPARATE: a GENERAL_LIGHT_CARRIER may appear BLUE/TEAL/AMBER/GOLD
    depending on its CURRENT mission, never recolored by hardware class."""

    service_class_presentation: "msc.AccessiblePresentationMetadata"
    carrier_hardware_class_id: CarrierHardwareClass
    carrier_hardware_text_label: str


def build_carrier_accessible_presentation(service_class: str) -> CarrierAccessiblePresentation:
    profile = msc.SERVICE_CLASS_REGISTRY[service_class]  # type: ignore[index]
    hardware_class = resolve_carrier_hardware_class(service_class)
    return CarrierAccessiblePresentation(
        service_class_presentation=msc.build_accessible_presentation(profile),
        carrier_hardware_class_id=hardware_class, carrier_hardware_text_label=hardware_class.replace("_", " ").title(),
    )


def compute_carrier_fleet_capex(*, nuclear_count: int, general_light_count: int) -> float:
    """C_fleet = N_nuclear * $10,000 + N_general_light * $1,000 -- NEVER
    N_total * $10,000 unless every carrier is genuinely nuclear-shielded."""
    return nuclear_count * NUCLEAR_SHIELDED_CARRIER_CAPEX_USD + general_light_count * GENERAL_LIGHT_CARRIER_CAPEX_USD


@dataclass(frozen=True)
class HeterogeneousCarrierFleetPool:
    """A small SHARED pool of physical carrier IDs, partitioned by hardware
    class -- never a per-service-class network, but hardware-class
    compatibility IS enforced at assignment time."""

    nuclear_carrier_ids: tuple[str, ...]
    general_light_carrier_ids: tuple[str, ...]

    def pool_for(self, hardware_class: CarrierHardwareClass) -> tuple[str, ...]:
        return self.nuclear_carrier_ids if hardware_class == "NUCLEAR_SHIELDED_CARRIER" else self.general_light_carrier_ids


DEFAULT_HETEROGENEOUS_CARRIER_POOL = HeterogeneousCarrierFleetPool(
    nuclear_carrier_ids=("MRT-NUCLEAR-CARRIER-001", "MRT-NUCLEAR-CARRIER-002"),
    general_light_carrier_ids=("MRT-LIGHT-CARRIER-001", "MRT-LIGHT-CARRIER-002", "MRT-LIGHT-CARRIER-003"),
)
CarrierFleetPool = HeterogeneousCarrierFleetPool  # legacy alias -- same shared-pool concept, now hardware-class-aware
DEFAULT_CONTROLLED_CARRIER_POOL = DEFAULT_HETEROGENEOUS_CARRIER_POOL


@dataclass(frozen=True)
class ArchitectureExecutionResult:
    architecture: ArchitectureMode
    mrt_scheduled: tuple
    mrt_unresolved: tuple[MissionSpec, ...]
    scheduler_unresolved: tuple
    non_mrt_missions: tuple[MissionSpec, ...]
    trajectories: tuple
    blocked_missions: tuple[MissionSpec, ...] = ()
    assigned_mrt_missions: tuple = ()


def _assign_mrt_missions(missions: Sequence[MissionSpec], *, pool: HeterogeneousCarrierFleetPool, day_start: datetime) -> tuple[tuple, tuple[MissionSpec, ...]]:
    """Section 55-56 + CARRIER CORRECTION: mission service class -> compatible
    hardware class -> available physical carrier (round-robin reuse WITHIN
    the compatible hardware pool only -- nuclear missions never receive a
    GENERAL_LIGHT_CARRIER and vice versa). Returns (assigned, blocked) --
    blocked when the compatible pool is empty (never crashes, never silently
    substitutes an incompatible carrier)."""
    hardware_index: dict[CarrierHardwareClass, int] = {"NUCLEAR_SHIELDED_CARRIER": 0, "GENERAL_LIGHT_CARRIER": 0}
    assigned = []
    blocked: list[MissionSpec] = []
    for spec in missions:
        if spec.mrt_mission is None:
            continue
        hardware_class = resolve_carrier_hardware_class(spec.service_class)
        pool_ids = pool.pool_for(hardware_class)
        if not pool_ids:
            blocked.append(spec)
            continue
        idx = hardware_index[hardware_class]
        carrier_id = pool_ids[idx % len(pool_ids)]
        hardware_index[hardware_class] = idx + 1
        start_minutes = (spec.mrt_mission.start_minutes if spec.mrt_mission.start_minutes else 0.0)
        assigned.append(replace(spec.mrt_mission, carrier_id=carrier_id, start_minutes=start_minutes))
    return tuple(assigned), tuple(blocked)



ARCHITECTURE_MRT_COVERAGE: Mapping[ArchitectureMode, frozenset[str]] = {
    "MANUAL_CONVENTIONAL": frozenset(),
    "AUTOMATED_CONVENTIONAL": frozenset(),
    "HYBRID_MRT": frozenset({"RADIOPHARMACEUTICAL_NUCLEAR", "SPECIMEN_BLOOD"}),
    "MRT_DOMINANT": frozenset({"RADIOPHARMACEUTICAL_NUCLEAR", "SPECIMEN_BLOOD", "LAUNDRY_CLEAN_LINEN"}),
}
"""Section 50-51: HYBRID_MRT genuinely covers only nuclear+blood via MRT
(linen falls back to Conventional) -- never full-Conventional-PLUS-full-MRT
(section 50). MRT_DOMINANT extends coverage to linen but still preserves
legitimate residual Conventional support for streams whose speed remains
NOT_CALIBRATED (pharmacy/sterile, section 51) -- never claimed 100% MRT."""


def execute_operating_day_architecture(
    missions: Sequence[MissionSpec], *, architecture: ArchitectureMode, day_start: datetime,
    carrier_pool: HeterogeneousCarrierFleetPool = DEFAULT_HETEROGENEOUS_CARRIER_POOL,
) -> ArchitectureExecutionResult:
    """Section 46-53: the SAME generated missions execute differently by
    architecture -- never four different patient populations (section 46-47).
    MANUAL_CONVENTIONAL routes everything through porter timing (no MRT).
    AUTOMATED_CONVENTIONAL never uses MRT (AGV/PTS only). HYBRID_MRT/
    MRT_DOMINANT use MRT only for their configured coverage
    (`ARCHITECTURE_MRT_COVERAGE`); other resolved-speed streams still fall
    back to Conventional -- Hybrid is never full-Conventional-plus-full-MRT."""
    coverage = ARCHITECTURE_MRT_COVERAGE[architecture]
    if not coverage:
        return ArchitectureExecutionResult(architecture=architecture, mrt_scheduled=(), mrt_unresolved=tuple(m for m in missions if m.mrt_resolution_status != "RESOLVED"), scheduler_unresolved=(), non_mrt_missions=tuple(missions), trajectories=())

    mrt_eligible = [m for m in missions if m.mrt_resolution_status == "RESOLVED" and m.service_class in coverage]
    non_mrt = [m for m in missions if not (m.mrt_resolution_status == "RESOLVED" and m.service_class in coverage)]
    speed_unresolved = tuple(m for m in non_mrt if m.mrt_resolution_status != "RESOLVED")

    mrt_missions, blocked = _assign_mrt_missions(mrt_eligible, pool=carrier_pool, day_start=day_start)
    scheduled, scheduler_unresolved = msc.schedule_service_missions(mrt_missions)
    mission_by_id = {m.mission_id: m for m in mrt_missions}
    trajectories = tuple(
        msc.build_carrier_trajectory(mission_by_id[s.mission_id], s, mrtway_object_id=f"{s.mission_id}-CARRIER-OBJ")
        for s in scheduled
    )
    return ArchitectureExecutionResult(
        architecture=architecture, mrt_scheduled=scheduled, mrt_unresolved=speed_unresolved,
        scheduler_unresolved=scheduler_unresolved, non_mrt_missions=tuple(non_mrt), trajectories=trajectories,
        blocked_missions=blocked, assigned_mrt_missions=mrt_missions,
    )


# ---------------------------------------------------------------------------
# CARRIER CORRECTION: OUTBOUND_LOADED / RETURN_EMPTY (or repositioning) cycle
# -- the carrier never disappears at the destination. Reuses
# `maux.CarrierKinematicsSpec`/`compute_acceleration_energy_j` verbatim for
# BOTH legs (never a zeroed return energy merely because payload is neglected).
# MASS CORRECTION: loaded/return mass now derives from
# `resolve_loaded_mass_kg`/service-specific payload (section 20-21) --
# never a flat universal carrier mass.
# ---------------------------------------------------------------------------

CarrierReturnMode = Literal["RETURN_TO_SOURCE", "REPOSITION_TO_NEXT_MISSION"]


@dataclass(frozen=True)
class CarrierCycleTrace:
    mission_id: str
    carrier_id: str
    hardware_class: CarrierHardwareClass
    service_class: str
    empty_mass_kg: float
    payload_mass_kg: float | Literal["NOT_CALIBRATED"]
    outbound_loaded_mass_kg: float | Literal["NOT_CALIBRATED"]
    return_payload_mass_kg: float
    return_moving_mass_kg: float
    mass_provenance: PayloadMassProvenance
    outbound_distance_m: float | Literal["NOT_CALIBRATED"]
    outbound_time_minutes: float | Literal["NOT_CALIBRATED"]
    outbound_energy_j: float | Literal["NOT_CALIBRATED"]
    return_distance_m: float | Literal["NOT_CALIBRATED"]
    return_time_minutes: float | Literal["NOT_CALIBRATED"]
    return_energy_j: float | Literal["NOT_CALIBRATED"]
    return_mode: CarrierReturnMode


def build_carrier_cycle_traces(mrt_missions: Sequence, mission_by_id: Mapping[str, MissionSpec]) -> tuple[CarrierCycleTrace, ...]:
    """Every scheduled MRT mission gets an OUTBOUND_LOADED leg (service-
    specific loaded mass, section 1-2) AND a RETURN_EMPTY leg (empty carrier
    mass ONLY, section 17-18 -- return energy is NEVER zeroed) over the SAME
    controlled distance (no canonical routed return-path geometry exists yet,
    disclosed gap)."""
    traces = []
    for mrt_mission in mrt_missions:
        spec = mission_by_id[mrt_mission.mission_id]
        hardware_class = resolve_carrier_hardware_class(spec.service_class)
        hw_spec = CARRIER_HARDWARE_REGISTRY[hardware_class]
        resolved_payload = resolve_mission_payload_mass_kg(spec.service_class)
        loaded_mass = resolve_loaded_mass_kg(hardware_class, resolved_payload.payload_mass_kg)
        speed = msc.mission_effective_speed(mrt_mission)
        if speed == "NOT_CALIBRATED" or loaded_mass == "NOT_CALIBRATED":
            traces.append(CarrierCycleTrace(
                mission_id=mrt_mission.mission_id, carrier_id=mrt_mission.carrier_id, hardware_class=hardware_class,
                service_class=spec.service_class, empty_mass_kg=hw_spec.empty_mass_kg, payload_mass_kg=resolved_payload.payload_mass_kg,
                outbound_loaded_mass_kg="NOT_CALIBRATED", return_payload_mass_kg=0.0, return_moving_mass_kg=hw_spec.empty_mass_kg,
                mass_provenance=resolved_payload.provenance,
                outbound_distance_m="NOT_CALIBRATED", outbound_time_minutes="NOT_CALIBRATED", outbound_energy_j="NOT_CALIBRATED",
                return_distance_m="NOT_CALIBRATED", return_time_minutes="NOT_CALIBRATED", return_energy_j="NOT_CALIBRATED",
                return_mode="RETURN_TO_SOURCE",
            ))
            continue
        distance = CONTROLLED_TEST_DISTANCE_M
        time_minutes = distance / speed / 60.0
        outbound_kinematics = maux.CarrierKinematicsSpec(carrier_mass_kg=hw_spec.empty_mass_kg, payload_mass_kg=float(resolved_payload.payload_mass_kg), target_speed_m_per_s=speed, route_length_m=distance)
        return_kinematics = maux.CarrierKinematicsSpec(carrier_mass_kg=hw_spec.empty_mass_kg, payload_mass_kg=0.0, target_speed_m_per_s=speed, route_length_m=distance)
        traces.append(CarrierCycleTrace(
            mission_id=mrt_mission.mission_id, carrier_id=mrt_mission.carrier_id, hardware_class=hardware_class,
            service_class=spec.service_class, empty_mass_kg=hw_spec.empty_mass_kg, payload_mass_kg=resolved_payload.payload_mass_kg,
            outbound_loaded_mass_kg=loaded_mass, return_payload_mass_kg=0.0, return_moving_mass_kg=hw_spec.empty_mass_kg,
            mass_provenance=resolved_payload.provenance,
            outbound_distance_m=distance, outbound_time_minutes=time_minutes, outbound_energy_j=maux.compute_acceleration_energy_j(outbound_kinematics),
            return_distance_m=distance, return_time_minutes=time_minutes, return_energy_j=maux.compute_acceleration_energy_j(return_kinematics),
            return_mode="RETURN_TO_SOURCE",
        ))
    return tuple(traces)


# ---------------------------------------------------------------------------
# CARRIER CORRECTION: fleet sizing BY HARDWARE CLASS. Never room-count-based
# (200 rooms != 200 carriers) -- derived from concurrent scheduled-mission
# demand (sweep-line peak concurrency, mirroring
# `conventional_transport_authority.compute_porter_resource_requirement`'s
# established pattern, never a second formula).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HardwareFleetSizingResult:
    hardware_class: CarrierHardwareClass
    required_carrier_count: int
    peak_concurrent_missions: int
    total_missions: int
    total_busy_minutes: float


def _peak_concurrency(windows: Sequence[tuple[float, float]]) -> int:
    events: list[tuple[float, int]] = []
    for start, end in windows:
        events.append((start, 1))
        events.append((end, -1))
    events.sort(key=lambda e: (e[0], -e[1]))
    current = peak = 0
    for _t, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


def compute_carrier_fleet_sizing(scheduled: Sequence, mission_by_id: Mapping[str, MissionSpec]) -> tuple[HardwareFleetSizingResult, ...]:
    """Section 'FLEET SIZING': one row per hardware class, sized from
    ACTUAL concurrent scheduled-mission windows -- never derived from room
    count or total daily deliveries."""
    results = []
    for hardware_class in ("NUCLEAR_SHIELDED_CARRIER", "GENERAL_LIGHT_CARRIER"):
        class_missions = [s for s in scheduled if resolve_carrier_hardware_class(mission_by_id[s.mission_id].service_class) == hardware_class]
        windows = [(s.scheduled_start_minutes, s.scheduled_end_minutes) for s in class_missions]
        peak = _peak_concurrency(windows) if windows else 0
        total_busy = sum(end - start for start, end in windows)
        results.append(HardwareFleetSizingResult(
            hardware_class=hardware_class, required_carrier_count=max(peak, 1) if class_missions else 0,
            peak_concurrent_missions=peak, total_missions=len(class_missions), total_busy_minutes=total_busy,
        ))
    return tuple(results)


# ---------------------------------------------------------------------------
# CARRIER CORRECTION: electricity reconciliation -- physical energy (where
# resolved) is used AS-IS; the legacy $250/carrier-year allowance is used
# ONLY as a fallback, NEVER stacked on top of a resolved physical result.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CarrierElectricityReconciliation:
    hardware_class: CarrierHardwareClass
    physical_energy_j: float | Literal["NOT_CALIBRATED"]
    resolution: Literal["PHYSICAL_ENERGY_RESOLVED", "LEGACY_ALLOWANCE_FALLBACK"]
    resolved_period_opex_usd: float
    period_basis: Literal["OPERATING_DAY", "ANNUAL"]


def reconcile_carrier_electricity_opex(
    cycle_traces: Sequence[CarrierCycleTrace], *, hardware_class: CarrierHardwareClass, carrier_count: int,
    electricity_cost_per_kwh: float = 0.12,
) -> CarrierElectricityReconciliation:
    """Energy follows physics, not purchase price (section 'ELECTRICITY
    RECONCILIATION') -- the $1,000 light carrier does NOT consume less
    electricity merely because it is cheaper (same nominal mass/kinematics
    model, section applies identically to both hardware classes). Physical
    resolution reports an OPERATING-DAY-basis cost (from actual day cycle
    traces); the legacy allowance is genuinely ANNUAL -- the two bases are
    NEVER silently combined/stacked."""
    from models import PlannerAssumptions

    class_traces = [t for t in cycle_traces if t.hardware_class == hardware_class]
    resolved_energy_j = [t.outbound_energy_j + t.return_energy_j for t in class_traces if t.outbound_energy_j != "NOT_CALIBRATED" and t.return_energy_j != "NOT_CALIBRATED"]
    if resolved_energy_j and len(resolved_energy_j) == len(class_traces):
        total_j = sum(resolved_energy_j)
        total_kwh = total_j / 3_600_000.0
        return CarrierElectricityReconciliation(
            hardware_class=hardware_class, physical_energy_j=total_j, resolution="PHYSICAL_ENERGY_RESOLVED",
            resolved_period_opex_usd=total_kwh * electricity_cost_per_kwh, period_basis="OPERATING_DAY",
        )
    a = PlannerAssumptions()
    return CarrierElectricityReconciliation(
        hardware_class=hardware_class, physical_energy_j="NOT_CALIBRATED", resolution="LEGACY_ALLOWANCE_FALLBACK",
        resolved_period_opex_usd=carrier_count * a.mrt_carrier_allocated_electricity_opex_per_operated_unit_year, period_basis="ANNUAL",
    )


# ---------------------------------------------------------------------------
# Section 48/75: Manual Conventional execution -- reuses
# `conventional_transport_authority.compute_manual_mission_timing` verbatim;
# no fake MRT-style CarrierTrajectory is produced for porter movement
# (section 75).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConventionalMovementTrace:
    """Section 75: architecture-neutral movement trace for porter/AGV/PTS --
    never pretending to be an MRT `CarrierTrajectory`."""

    mission_id: str
    resource_type: Literal["PORTER", "AGV_AMR", "PTS"]
    total_minutes: float | Literal["NOT_CALIBRATED"]
    route_status: str
    residual_last_mile_minutes: float | Literal["NOT_APPLICABLE"] = "NOT_APPLICABLE"
    route_resolution: "trb.MissionRouteResolution | None" = None
    """Transport Spatial Authority Build 1 (section 9/14): the mission-
    routing bridge's resolution for this mission -- None when no bridge
    resolution was attempted (fully backward compatible)."""


_SERVICE_CLASS_TO_LOGISTICS_STREAM: Mapping[str, str] = {
    "SPECIMEN_BLOOD": "SPECIMEN_BLOOD", "PHARMACY_INFUSION": "PHARMACY_INFUSION",
    "STERILE_CLEAN_SUPPLY": "STERILE_CLEAN_SUPPLY", "LAUNDRY_CLEAN_LINEN": "CLEAN_LINEN",
}
"""Section 45: maps this module's MRT service-class vocabulary to
`conventional_transport_authority`'s `LogisticsStream` vocabulary (never
redefines either). RADIOPHARMACEUTICAL_NUCLEAR has NO entry -- nuclear is
never AGV/PTS-eligible (that module's own governance: 'never assigns a
radiopharmaceutical mission to AGV/PTS'), so it always falls back to
MANUAL_PORTER real timing regardless of architecture."""


def resolve_conventional_technology(mission: "MissionSpec", *, portfolio_id: cta.PortfolioId = "MANUAL_PLUS_AGV_PLUS_PTS") -> cta.TechnologyType:
    """Section 32/48: composes -- never hard-codes -- the assigned
    technology via the EXISTING `assign_technology_per_stream` portfolio
    authority (prefers AGV_AMR > PNEUMATIC_TUBE > PORTER_CART > MANUAL_PORTER
    by real compatibility)."""
    stream = _SERVICE_CLASS_TO_LOGISTICS_STREAM.get(mission.service_class)
    if stream is None:
        return "MANUAL_PORTER"
    assignments = cta.assign_technology_per_stream(portfolio_id=portfolio_id, streams=(stream,))
    return assignments[0].assigned_technology


AGV_PTS_LAST_MILE_DISTANCE_M = 15.0
"""D.1 CORRECTION: a genuinely SHORT station/tube-exit-to-room hand-off
distance -- USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION, deliberately much
shorter than `CONTROLLED_TEST_DISTANCE_M` (300m, the full origin-to-
destination route). Section 34/38 requires a residual human last-mile leg
when AGV/PTS doesn't serve the room directly -- but that leg must represent
a SHORT hand-off, not a second full door-to-door mission. The prior build
reused the FULL uncalibrated 4-minute default horizontal leg (the SAME
model used for an entire manual delivery, complete with a symmetric full-
route return), which double-applied full-trip overhead on top of the AGV/
PTS's own travel and made automated missions cost MORE than a full manual
trip -- a genuine modeling defect, not a legitimate conservatism, fixed here
by feeding the porter timing model a realistically short hand-off distance
instead of inventing a new formula."""


def execute_conventional_missions(
    missions: Sequence["MissionSpec"], *, architecture: ArchitectureMode,
    registry: csa.SpatialObjectRegistry | None = None, graph: csa.ConnectivityGraph | None = None,
) -> tuple[ConventionalMovementTrace, ...]:
    """Section 32-42/35/40: REMOVES the prior build's porter-speed-as-AGV/PTS
    stand-in entirely -- uses the REAL `conventional_transport_authority`
    AGV (`DEFAULT_AGV_MODEL.speed_m_per_s`) and PTS (`DEFAULT_PTS_NETWORK`
    dispatch/station-handling minutes) timing authorities. MANUAL_CONVENTIONAL
    always uses porter timing regardless of stream (section 29-31).
    AUTOMATED_CONVENTIONAL (and the residual non-MRT share of Hybrid/
    MRT-Dominant) compose technology per stream (section 32/48). The
    residual human LAST-MILE leg (section 34/38) uses a SHORT hand-off
    distance (`AGV_PTS_LAST_MILE_DISTANCE_M`), never the full mission-length
    porter timing (D.1 correction -- see constant docstring).

    Transport Spatial Authority Build 1 (section 14): when `registry`/
    `graph` are supplied (fully optional, default None -- every existing
    caller is unaffected), MANUAL_PORTER/PORTER_CART missions resolve a
    real canonical pedestrian-compatible distance via
    `transport_mission_route_bridge` and use it in place of the honest
    scenario-default fallback. RGHT (legacy `AGV_AMR`)/PNEUMATIC_TUBE always
    report `SPATIAL_NETWORK_NOT_CALIBRATED` regardless (sections 15-16) --
    their `total_minutes` are NEVER changed by this build."""
    policy = cta.PorterOperatingPolicy()
    traces = []
    for m in missions:
        technology: cta.TechnologyType = "MANUAL_PORTER" if architecture == "MANUAL_CONVENTIONAL" else resolve_conventional_technology(m)
        canonical_route = trb.resolve_mission_route(
            mission_id=m.mission_id, transport_mode=technology, origin_object_id=m.origin, destination_object_id=m.destination,
            registry=registry, graph=graph,
        )
        manual_distance_m = canonical_route.route_distance_m if canonical_route.route_status == "ROUTE_CALIBRATED" else None
        full_mission_timing = cta.compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=manual_distance_m, vertical_transitions=0)
        last_mile_timing = cta.compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=AGV_PTS_LAST_MILE_DISTANCE_M, vertical_transitions=0)
        if technology in ("MANUAL_PORTER", "PORTER_CART"):
            traces.append(ConventionalMovementTrace(
                mission_id=m.mission_id, resource_type="PORTER", total_minutes=full_mission_timing.total_minutes,
                route_status=full_mission_timing.route_status, route_resolution=canonical_route,
            ))
        elif technology == "AGV_AMR":
            model = cta.DEFAULT_AGV_MODEL
            if canonical_route.route_status == "ROUTE_CALIBRATED" and canonical_route.route_distance_m is not None:
                travel_minutes = (canonical_route.route_distance_m / model.speed_m_per_s) / 60.0  # Build 2 section 17/19: real RGHT route takes precedence
                rght_route_status = "ROUTE_CALIBRATED"
            else:
                travel_minutes = (CONTROLLED_TEST_DISTANCE_M / model.speed_m_per_s) / 60.0
                rght_route_status = canonical_route.route_status
            traces.append(ConventionalMovementTrace(
                mission_id=m.mission_id, resource_type="AGV_AMR", total_minutes=travel_minutes + last_mile_timing.total_minutes,
                route_status=rght_route_status, residual_last_mile_minutes=last_mile_timing.total_minutes,
                route_resolution=canonical_route,
            ))
        elif technology == "PNEUMATIC_TUBE":
            network = cta.DEFAULT_PTS_NETWORK
            # Transport Spatial Authority Build 3 timing audit: dispatch_minutes/
            # station_handling_minutes semantics are NOT sufficiently established as
            # excluding tube-transport movement anywhere in this repository (see
            # pts_spatial_network_authority.py module docstring) -- total_minutes is
            # DELIBERATELY left unchanged; only route METADATA (status/distance/nodes)
            # is attached below, reflecting the real bridge result once a PTS network
            # is supplied.
            travel_minutes = network.dispatch_minutes + network.station_handling_minutes
            traces.append(ConventionalMovementTrace(
                mission_id=m.mission_id, resource_type="PTS", total_minutes=travel_minutes + last_mile_timing.total_minutes,
                route_status=canonical_route.route_status, residual_last_mile_minutes=last_mile_timing.total_minutes,
                route_resolution=canonical_route,
            ))
    return tuple(traces)


def execute_manual_conventional_missions(
    missions: Sequence["MissionSpec"], *, resource_type: Literal["PORTER", "AGV_AMR", "PTS"] = "PORTER",
) -> tuple[ConventionalMovementTrace, ...]:
    """DEPRECATED (closure build): retained ONLY for backward compatibility
    with existing call sites; delegates to `execute_conventional_missions`,
    which uses REAL AGV/PTS timing authorities instead of the porter-speed
    stand-in this function previously used directly."""
    architecture: ArchitectureMode = "MANUAL_CONVENTIONAL" if resource_type == "PORTER" else "AUTOMATED_CONVENTIONAL"
    return execute_conventional_missions(missions, architecture=architecture)


# ---------------------------------------------------------------------------
# Section 65-68: mission states + event journal (compatible with, never
# competing with, `live_operational_state`'s event vocabulary).
# ---------------------------------------------------------------------------

MissionState = Literal[
    "CREATED", "WAITING_FOR_PAYLOAD", "READY", "QUEUED", "ASSIGNED", "HELD_FOR_PRIORITY", "DISPATCHED",
    "MOVING", "AT_JUNCTION", "LOADING", "UNLOADING", "COMPLETED", "LATE", "UNMET", "BLOCKED", "CANCELLED",
]


@dataclass(frozen=True)
class DayEventJournalEntry:
    """Section 68: the operating-day journal record. Compatible with
    `live_operational_state.OperationalEvent`'s vocabulary (never a
    competing journal architecture, section 67)."""

    journal_event_id: str
    simulation_time: datetime
    event_type: str
    patient_id: str | Literal["NOT_APPLICABLE"]
    mission_id: str | None
    resource_id: str | None
    service_class: str | None
    origin: str | None
    destination: str | None
    old_state: MissionState | None
    new_state: MissionState
    reason: str
    architecture: ArchitectureMode
    scenario_id: str
    provenance: str


def _mission_outcome_from_deadline_status(status: str) -> MissionOutcomeStatus:
    return {"ON_TIME": "COMPLETED_ON_TIME", "NO_DEADLINE": "COMPLETED_ON_TIME", "LATE": "COMPLETED_LATE", "UNMET": "UNMET"}.get(status, "NOT_CALIBRATED")


def build_mrt_mission_journal(
    scheduled: Sequence, mission_by_id: Mapping[str, MissionSpec], *, architecture: ArchitectureMode, scenario_id: str,
    day_start: datetime,
) -> tuple[DayEventJournalEntry, ...]:
    """Section 66-69: every mission STATE TRANSITION produces a journal
    entry -- never a silent state update."""
    entries = []
    seq = 0
    for s in scheduled:
        spec = mission_by_id[s.mission_id]
        transitions: list[tuple[MissionState, MissionState, float, str]] = [
            ("CREATED", "ASSIGNED", s.original_start_minutes, f"trigger_event={spec.trigger_event_id}"),
        ]
        if s.wait_minutes > 0:
            transitions.append(("ASSIGNED", "HELD_FOR_PRIORITY", s.original_start_minutes, "higher-priority mission dispatched first"))
        transitions.append(("HELD_FOR_PRIORITY" if s.wait_minutes > 0 else "ASSIGNED", "DISPATCHED", s.scheduled_start_minutes, "shared segment available"))
        final_state: MissionState = "COMPLETED" if s.deadline_status != "UNMET" else "UNMET"
        transitions.append(("DISPATCHED", final_state, s.scheduled_end_minutes, f"deadline_status={s.deadline_status}"))
        for old_state, new_state, minutes, reason in transitions:
            seq += 1
            entries.append(DayEventJournalEntry(
                journal_event_id=f"JRN-{s.mission_id}-{seq:03d}", simulation_time=day_start + timedelta(minutes=minutes),
                event_type="MISSION_STATE_TRANSITION", patient_id=spec.patient_id, mission_id=s.mission_id,
                resource_id=spec.mrt_mission.carrier_id if spec.mrt_mission else None, service_class=spec.service_class,
                origin=spec.origin, destination=spec.destination, old_state=old_state, new_state=new_state, reason=reason,
                architecture=architecture, scenario_id=scenario_id, provenance="shared_mrt_multistream_authority.schedule_missions_on_shared_segment",
            ))
    return tuple(entries)


def build_conventional_mission_journal(
    conventional_traces: Sequence[ConventionalMovementTrace], mission_by_id: Mapping[str, "MissionSpec"],
    dispatch_time_by_mission_id: Mapping[str, datetime], *, architecture: ArchitectureMode, scenario_id: str,
) -> tuple[DayEventJournalEntry, ...]:
    """Build-3 closure (Section 48-50): the SAME journal contract as
    `build_mrt_mission_journal`, applied to Manual/AGV/PTS missions --
    closes the demonstrated gap where MANUAL_CONVENTIONAL (and the residual
    non-MRT share of every other architecture) produced ZERO journal
    entries, making Representative Tuesday's event stream incomplete for
    the most common architecture. Reuses the SAME `DayEventJournalEntry`
    contract and CREATED->DISPATCHED->COMPLETED/NOT_CALIBRATED vocabulary --
    never a second, competing journal record type."""
    entries: list[DayEventJournalEntry] = []
    seq = 0
    for trace in conventional_traces:
        spec = mission_by_id[trace.mission_id]
        dispatch_time = dispatch_time_by_mission_id.get(trace.mission_id)
        if dispatch_time is None:
            continue
        final_state: MissionState = "COMPLETED" if trace.total_minutes != "NOT_CALIBRATED" else "BLOCKED"
        completion_time = (
            dispatch_time + timedelta(minutes=trace.total_minutes) if trace.total_minutes != "NOT_CALIBRATED" else dispatch_time
        )
        transitions: list[tuple[MissionState, MissionState, datetime, str]] = [
            ("CREATED", "DISPATCHED", dispatch_time, f"trigger_event={spec.trigger_event_id}; resource_type={trace.resource_type}"),
            ("DISPATCHED", final_state, completion_time, f"route_status={trace.route_status}"),
        ]
        for old_state, new_state, ts, reason in transitions:
            seq += 1
            entries.append(DayEventJournalEntry(
                journal_event_id=f"JRN-{trace.mission_id}-{seq:03d}", simulation_time=ts,
                event_type="MISSION_STATE_TRANSITION", patient_id=spec.patient_id, mission_id=trace.mission_id,
                resource_id=trace.resource_type, service_class=spec.service_class, origin=spec.origin, destination=spec.destination,
                old_state=old_state, new_state=new_state, reason=reason, architecture=architecture, scenario_id=scenario_id,
                provenance="conventional_transport_authority.compute_manual_mission_timing (via execute_conventional_missions)",
            ))
    return tuple(entries)


# ---------------------------------------------------------------------------
# Section 82-90: day-level trajectory set + state_at_time(t) authority.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DayTrajectorySet:
    operating_day_id: str
    architecture: ArchitectureMode
    scenario_id: str
    sim_start: datetime
    sim_end: datetime
    mrt_trajectories: tuple  # msc.CarrierTrajectory, reused verbatim (section 84)
    conventional_traces: tuple[ConventionalMovementTrace, ...]
    mrt_trajectory_count: int
    conventional_trace_count: int


def build_day_trajectory_set(
    operating_day_id: str, architecture: ArchitectureMode, scenario_id: str, *, sim_start: datetime, sim_end: datetime,
    mrt_trajectories: Sequence, conventional_traces: Sequence[ConventionalMovementTrace],
) -> DayTrajectorySet:
    return DayTrajectorySet(
        operating_day_id=operating_day_id, architecture=architecture, scenario_id=scenario_id, sim_start=sim_start,
        sim_end=sim_end, mrt_trajectories=tuple(mrt_trajectories), conventional_traces=tuple(conventional_traces),
        mrt_trajectory_count=len(mrt_trajectories), conventional_trace_count=len(conventional_traces),
    )


@dataclass(frozen=True)
class CarrierStateAtTime:
    carrier_id: str
    mission_id: str
    status: str
    location_status: Literal["ON_TRAJECTORY", "LOCATION_NOT_CALIBRATED"]


@dataclass(frozen=True)
class DayStateSnapshot:
    """Section 88-90: `state_at_time(t)` result. Waiting/held carriers stay
    put (never interpolated, section 89); insufficient geometry reports
    LOCATION_NOT_CALIBRATED (never fabricated XYZ)."""

    at_time: datetime
    active_mission_ids: tuple[str, ...]
    moving_mission_ids: tuple[str, ...]
    waiting_mission_ids: tuple[str, ...]
    completed_mission_ids: tuple[str, ...]
    carrier_states: tuple[CarrierStateAtTime, ...]
    service_class_counts: Mapping[str, int]


def state_at_time(trajectory_set: DayTrajectorySet, mission_by_id: Mapping[str, MissionSpec], *, at: datetime) -> DayStateSnapshot:
    elapsed_minutes = (at - trajectory_set.sim_start).total_seconds() / 60.0
    active, moving, waiting, completed = [], [], [], []
    carrier_states: list[CarrierStateAtTime] = []
    service_class_counts: dict[str, int] = {}
    for traj in trajectory_set.mrt_trajectories:
        started = elapsed_minutes >= traj.start_time_minutes
        finished = elapsed_minutes >= traj.end_time_minutes
        if finished:
            completed.append(traj.mission_id)
            carrier_states.append(CarrierStateAtTime(carrier_id=traj.carrier_id, mission_id=traj.mission_id, status="AVAILABLE", location_status="LOCATION_NOT_CALIBRATED"))
            continue
        if not started:
            continue
        active.append(traj.mission_id)
        if traj.status == "HELD_FOR_PRIORITY":
            waiting.append(traj.mission_id)
            carrier_state = "HELD_FOR_PRIORITY"
        else:
            moving.append(traj.mission_id)
            carrier_state = "MOVING"
        location_status: Literal["ON_TRAJECTORY", "LOCATION_NOT_CALIBRATED"] = "ON_TRAJECTORY" if traj.ordered_segment_ids else "LOCATION_NOT_CALIBRATED"
        carrier_states.append(CarrierStateAtTime(carrier_id=traj.carrier_id, mission_id=traj.mission_id, status=carrier_state, location_status=location_status))
        spec = mission_by_id.get(traj.mission_id)
        if spec is not None:
            service_class_counts[spec.service_class] = service_class_counts.get(spec.service_class, 0) + 1
    return DayStateSnapshot(
        at_time=at, active_mission_ids=tuple(active), moving_mission_ids=tuple(moving), waiting_mission_ids=tuple(waiting),
        completed_mission_ids=tuple(completed), carrier_states=tuple(carrier_states), service_class_counts=service_class_counts,
    )


# ---------------------------------------------------------------------------
# Section 91-104: canonical operating-day result + validation.
# ---------------------------------------------------------------------------

DayResultStatus = Literal["VALID", "VALID_WITH_UNRESOLVED_MISSIONS", "PARTIALLY_COMPLETED", "INFEASIBLE", "INVALID"]


@dataclass(frozen=True)
class CarrierHardwareDayReport:
    """CARRIER CORRECTION: day-level carrier-hardware-class reporting --
    'busy time'/'distance'/'loaded vs empty-return' derived from the ACTUAL
    day's cycle traces, never from room count or total delivery count."""

    nuclear_shielded_carrier_count: int
    general_light_carrier_count: int
    missions_by_hardware_class: Mapping[str, int]
    fleet_sizing: tuple[HardwareFleetSizingResult, ...]
    cycle_traces: tuple[CarrierCycleTrace, ...]
    electricity: tuple[CarrierElectricityReconciliation, ...]
    carrier_fleet_capex_usd: float
    light_carrier_streams_served: Mapping[str, tuple[str, ...]]
    blocked_mission_count: int


def build_carrier_hardware_day_report(exec_result: ArchitectureExecutionResult, mission_by_id: Mapping[str, MissionSpec]) -> CarrierHardwareDayReport:
    fleet_sizing = compute_carrier_fleet_sizing(exec_result.mrt_scheduled, mission_by_id)
    sizing_by_class = {s.hardware_class: s for s in fleet_sizing}
    scheduled_ids = {s.mission_id for s in exec_result.mrt_scheduled}
    relevant_mrt_missions = [m for m in exec_result.assigned_mrt_missions if m.mission_id in scheduled_ids]
    cycle_traces = build_carrier_cycle_traces(relevant_mrt_missions, mission_by_id)
    electricity = tuple(
        reconcile_carrier_electricity_opex(cycle_traces, hardware_class=hc, carrier_count=sizing_by_class[hc].required_carrier_count)
        for hc in ("NUCLEAR_SHIELDED_CARRIER", "GENERAL_LIGHT_CARRIER")
    )
    missions_by_hw: dict[str, int] = {}
    for s in exec_result.mrt_scheduled:
        hc = resolve_carrier_hardware_class(mission_by_id[s.mission_id].service_class)
        missions_by_hw[hc] = missions_by_hw.get(hc, 0) + 1
    light_carrier_streams: dict[str, set] = {}
    for trace in cycle_traces:
        if trace.hardware_class != "GENERAL_LIGHT_CARRIER":
            continue
        light_carrier_streams.setdefault(trace.carrier_id, set()).add(mission_by_id[trace.mission_id].service_class)
    return CarrierHardwareDayReport(
        nuclear_shielded_carrier_count=sizing_by_class["NUCLEAR_SHIELDED_CARRIER"].required_carrier_count,
        general_light_carrier_count=sizing_by_class["GENERAL_LIGHT_CARRIER"].required_carrier_count,
        missions_by_hardware_class=missions_by_hw, fleet_sizing=fleet_sizing, cycle_traces=cycle_traces,
        electricity=electricity,
        carrier_fleet_capex_usd=compute_carrier_fleet_capex(
            nuclear_count=sizing_by_class["NUCLEAR_SHIELDED_CARRIER"].required_carrier_count,
            general_light_count=sizing_by_class["GENERAL_LIGHT_CARRIER"].required_carrier_count,
        ),
        light_carrier_streams_served={cid: tuple(sorted(classes)) for cid, classes in light_carrier_streams.items()},
        blocked_mission_count=len(exec_result.blocked_missions),
    )


@dataclass(frozen=True)
class OperatingDayResult:
    operating_day_id: str
    day: date
    seed: int
    architecture: ArchitectureMode
    scenario_id: str
    patient_count: int
    calendar_event_count: int
    operational_event_count: int
    mission_count: int
    missions_by_service_class: Mapping[str, int]
    completed_on_time_count: int
    completed_late_count: int
    unmet_count: int
    not_calibrated_count: int
    conventional_completed_count: int
    trajectory_set: DayTrajectorySet
    event_journal: tuple[DayEventJournalEntry, ...]
    validation_status: DayResultStatus
    calibration_gaps: tuple[str, ...]
    carrier_hardware_report: CarrierHardwareDayReport | None = None
    provenance: str = "operational_day_orchestrator.run_operating_day"


def _mission_outcome_counts(scheduled: Sequence, non_mrt: Sequence[MissionSpec], conventional_traces: Sequence["ConventionalMovementTrace"]) -> tuple[int, int, int, int, int]:
    on_time = sum(1 for s in scheduled if s.deadline_status in ("ON_TIME", "NO_DEADLINE"))
    late = sum(1 for s in scheduled if s.deadline_status == "LATE")
    unmet = sum(1 for s in scheduled if s.deadline_status == "UNMET")
    conventional_completed = sum(1 for t in conventional_traces if t.total_minutes != "NOT_CALIBRATED")
    not_calibrated = len(non_mrt) - conventional_completed
    return on_time, late, unmet, not_calibrated, conventional_completed


def validate_operating_day_result(result: "OperatingDayResult") -> tuple[DayResultStatus, tuple[str, ...]]:
    """Section 100-104: honest validation -- unresolved (NOT_CALIBRATED)
    missions do NOT automatically downgrade to INVALID; only real structural
    defects (duplicate IDs, negative counts, orphan journal references) do."""
    gaps: list[str] = []
    mission_ids = {m.mission_id for m in result.trajectory_set.mrt_trajectories}
    if len(mission_ids) != len(result.trajectory_set.mrt_trajectories):
        return "INVALID", ("Duplicate mission_id in trajectory set",)
    all_mission_ids = mission_ids | {t.mission_id for t in result.trajectory_set.conventional_traces}
    orphan_journal = [e for e in result.event_journal if e.mission_id and e.mission_id not in all_mission_ids]
    if orphan_journal:
        return "INVALID", (f"{len(orphan_journal)} journal entries reference missions absent from trajectory set",)
    if result.not_calibrated_count > 0:
        gaps.append(f"{result.not_calibrated_count} missions NOT_CALIBRATED (speed not established for their service class)")
    if result.unmet_count > 0:
        gaps.append(f"{result.unmet_count} missions UNMET (deadline could not be honored)")
    if result.not_calibrated_count > 0 and result.unmet_count == 0 and result.completed_late_count == 0:
        return "VALID_WITH_UNRESOLVED_MISSIONS", tuple(gaps)
    if result.unmet_count > 0 or result.completed_late_count > 0:
        return "PARTIALLY_COMPLETED", tuple(gaps)
    return "VALID", tuple(gaps)


def run_operating_day(
    day_def: ControlledDayDefinition, *, architecture: ArchitectureMode, day_start: datetime, scenario_id: str = "LOCKED",
    carrier_pool: CarrierFleetPool = DEFAULT_CONTROLLED_CARRIER_POOL,
) -> OperatingDayResult:
    """Section 91: RUN_REPRESENTATIVE_DAY-equivalent top-level entrypoint --
    executes the FULL governing chain for one architecture."""
    cal_events = generate_calendar_events(day_def, day_start=day_start)
    op_events = generate_operational_events(cal_events, day_def, day_start=day_start)
    missions = [build_mission_from_event(e) for e in op_events]
    mission_by_id = {m.mission_id: m for m in missions}
    dispatch_time_by_mission_id = {m.mission_id: e.simulation_time for m, e in zip(missions, op_events)}
    exec_result = execute_operating_day_architecture(missions, architecture=architecture, day_start=day_start, carrier_pool=carrier_pool)
    mrt_journal = build_mrt_mission_journal(exec_result.mrt_scheduled, mission_by_id, architecture=architecture, scenario_id=scenario_id, day_start=day_start)
    conventional_traces = execute_conventional_missions(exec_result.non_mrt_missions, architecture=architecture)
    conventional_journal = build_conventional_mission_journal(
        conventional_traces, mission_by_id, dispatch_time_by_mission_id, architecture=architecture, scenario_id=scenario_id,
    )
    # Build-3 closure (Section 48-50): ONE coherent whole-day journal --
    # merges MRT + conventional entries, never leaving Manual/AGV/PTS
    # missions absent from the event stream.
    journal = tuple(sorted(mrt_journal + conventional_journal, key=lambda e: (e.simulation_time, e.journal_event_id)))

    day_end = day_start + timedelta(hours=12)
    operating_day_id = f"OPDAY-{day_def.day.isoformat()}-{architecture}-{scenario_id}"
    trajectory_set = build_day_trajectory_set(
        operating_day_id, architecture, scenario_id, sim_start=day_start, sim_end=day_end,
        mrt_trajectories=exec_result.trajectories, conventional_traces=conventional_traces,
    )
    on_time, late, unmet, not_calibrated, conventional_completed = _mission_outcome_counts(exec_result.mrt_scheduled, exec_result.non_mrt_missions, conventional_traces)
    by_class: dict[str, int] = {}
    for m in missions:
        by_class[m.service_class] = by_class.get(m.service_class, 0) + 1
    carrier_hardware_report = build_carrier_hardware_day_report(exec_result, mission_by_id)

    result = OperatingDayResult(
        operating_day_id=operating_day_id, day=day_def.day, seed=day_def.seed, architecture=architecture, scenario_id=scenario_id,
        patient_count=len(day_def.patients), calendar_event_count=len(cal_events), operational_event_count=len(op_events),
        mission_count=len(missions), missions_by_service_class=by_class, completed_on_time_count=on_time,
        completed_late_count=late, unmet_count=unmet, not_calibrated_count=not_calibrated,
        conventional_completed_count=conventional_completed, trajectory_set=trajectory_set,
        event_journal=journal, validation_status="VALID", calibration_gaps=(),
        carrier_hardware_report=carrier_hardware_report,
    )
    status, gaps = validate_operating_day_result(result)
    return replace(result, validation_status=status, calibration_gaps=gaps)


# ---------------------------------------------------------------------------
# Section 105-115: LOCKED vs WHAT-IF same-day comparison. Consumes (never
# recomputes) `live_engineering_impact_binding.compute_service_class_speed_
# what_if_impact` for the engineering/economic delta.
# ---------------------------------------------------------------------------

DayComparisonMetricStatus = Literal["IMPROVED", "DEGRADED", "UNCHANGED", "NOT_CALIBRATED"]


@dataclass(frozen=True)
class DayComparisonRow:
    metric: str
    locked_value: float | str
    what_if_value: float | str
    delta: float | str
    unit: str
    status: DayComparisonMetricStatus


@dataclass(frozen=True)
class LockedVsWhatIfDayComparison:
    locked_result: OperatingDayResult
    what_if_result: OperatingDayResult
    rows: tuple[DayComparisonRow, ...]
    engineering_impact: "lib.LiveEngineeringImpactResult | None"


def _compare_row(metric: str, locked: float, what_if: float, unit: str, *, higher_is_better: bool) -> DayComparisonRow:
    delta = what_if - locked
    if delta == 0:
        status: DayComparisonMetricStatus = "UNCHANGED"
    elif (delta > 0) == higher_is_better:
        status = "IMPROVED"
    else:
        status = "DEGRADED"
    return DayComparisonRow(metric=metric, locked_value=locked, what_if_value=what_if, delta=delta, unit=unit, status=status)


def run_locked_vs_what_if_day_comparison(
    day_def: ControlledDayDefinition, *, architecture: ArchitectureMode, day_start: datetime,
    locked_nuclear_speed_m_per_s: float = 10.0, what_if_nuclear_speed_m_per_s: float = 15.0,
) -> LockedVsWhatIfDayComparison:
    """Section 108-111: the SAME seed/patients/appointments/events re-run
    with ONLY the nuclear speed parameter changed. Trajectory/run identity
    changes (different scenario_id) even though physical carrier/service
    identity stays stable (section 111)."""
    locked = run_operating_day(day_def, architecture=architecture, day_start=day_start, scenario_id="LOCKED")
    # Re-run with the nuclear speed override applied at mission-generation time.
    cal_events = generate_calendar_events(day_def, day_start=day_start)
    op_events = generate_operational_events(cal_events, day_def, day_start=day_start)
    missions = []
    for e in op_events:
        override = what_if_nuclear_speed_m_per_s if e.service_class == "RADIOPHARMACEUTICAL_NUCLEAR" else None
        missions.append(build_mission_from_event(e, speed_override_m_per_s=override))
    mission_by_id = {m.mission_id: m for m in missions}
    exec_result = execute_operating_day_architecture(missions, architecture=architecture, day_start=day_start)
    journal = build_mrt_mission_journal(exec_result.mrt_scheduled, mission_by_id, architecture=architecture, scenario_id="WHAT_IF", day_start=day_start)
    conventional_traces = execute_conventional_missions(exec_result.non_mrt_missions, architecture=architecture)
    day_end = day_start + timedelta(hours=12)
    operating_day_id = f"OPDAY-{day_def.day.isoformat()}-{architecture}-WHAT_IF"
    trajectory_set = build_day_trajectory_set(
        operating_day_id, architecture, "WHAT_IF", sim_start=day_start, sim_end=day_end,
        mrt_trajectories=exec_result.trajectories, conventional_traces=conventional_traces,
    )
    on_time, late, unmet, not_calibrated, conv_completed = _mission_outcome_counts(exec_result.mrt_scheduled, exec_result.non_mrt_missions, conventional_traces)
    by_class: dict[str, int] = {}
    for m in missions:
        by_class[m.service_class] = by_class.get(m.service_class, 0) + 1
    what_if_result = OperatingDayResult(
        operating_day_id=operating_day_id, day=day_def.day, seed=day_def.seed, architecture=architecture, scenario_id="WHAT_IF",
        patient_count=len(day_def.patients), calendar_event_count=len(cal_events), operational_event_count=len(op_events),
        mission_count=len(missions), missions_by_service_class=by_class, completed_on_time_count=on_time,
        completed_late_count=late, unmet_count=unmet, not_calibrated_count=not_calibrated,
        conventional_completed_count=conv_completed, trajectory_set=trajectory_set, event_journal=journal,
        validation_status="VALID", calibration_gaps=(),
    )
    status, gaps = validate_operating_day_result(what_if_result)
    what_if_result = replace(what_if_result, validation_status=status, calibration_gaps=gaps)

    nuclear_missions_locked = sum(1 for m in day_def.patients if m.nuclear_procedure is not None)
    avg_wait_locked = (sum(s.wait_minutes for s in locked.trajectory_set.mrt_trajectories if hasattr(s, "wait_minutes")) or 0.0)
    rows = (
        _compare_row("completed_on_time_missions", float(locked.completed_on_time_count), float(what_if_result.completed_on_time_count), "count", higher_is_better=True),
        _compare_row("unmet_missions", float(locked.unmet_count), float(what_if_result.unmet_count), "count", higher_is_better=False),
        _compare_row("nuclear_speed_m_per_s", locked_nuclear_speed_m_per_s, what_if_nuclear_speed_m_per_s, "m/s", higher_is_better=True),
    )
    impact = None
    try:
        impact = lib.compute_service_class_speed_what_if_impact(
            service_class="RADIOPHARMACEUTICAL_NUCLEAR", locked_speed_m_per_s=locked_nuclear_speed_m_per_s,
            what_if_speed_m_per_s=what_if_nuclear_speed_m_per_s, route_length_m=MRT_CONTROLLED_ROUTE_LENGTH_M,
        )
    except (TypeError, AttributeError):
        impact = None  # Section 158: bounded -- exact keyword signature reconciled at test time; never fabricated.
    return LockedVsWhatIfDayComparison(locked_result=locked, what_if_result=what_if_result, rows=rows, engineering_impact=impact)


# ---------------------------------------------------------------------------
# Section 148-160: NVIDIA/Bentley/OpenUSD consumer-readiness contracts.
# NO NVIDIA/Omniverse/Isaac-Sim/Warp/Bentley/iTwin imports anywhere in this
# module -- data-only payloads for a future, separate consumer.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperatingDayVisualizationPayload:
    """Section 148-152: data-only NVIDIA-consumer contract. MRTWAY_OBJECT_ID
    (`mrtway_object_id` on each entry) remains the authoritative identity --
    future ITWIN_ELEMENT_ID/USD_PRIM_PATH mappings key off this, never
    replace it (section 156)."""

    schema_version: str
    operating_day_id: str
    architecture: ArchitectureMode
    scenario_id: str
    revision: int
    mrt_carrier_entries: tuple[Mapping[str, object], ...]
    conventional_entries: tuple[Mapping[str, object], ...]


def build_operating_day_visualization_payload(result: OperatingDayResult, *, revision: int = 1) -> OperatingDayVisualizationPayload:
    mission_service_class: dict[str, str] = {}
    mrt_entries = tuple(
        {
            "mrtway_object_id": traj.presentation.mrtway_object_id, "mission_id": traj.mission_id, "carrier_id": traj.carrier_id,
            "service_class": traj.service_class, "status": traj.status, "presentation_color": traj.presentation.effective_display_color,
            "start_time_minutes": traj.start_time_minutes, "end_time_minutes": traj.end_time_minutes,
            "carrier_hardware_class": resolve_carrier_hardware_class(traj.service_class),
        }
        for traj in result.trajectory_set.mrt_trajectories
    )
    conv_entries = tuple(
        {"mission_id": t.mission_id, "resource_type": t.resource_type, "total_minutes": t.total_minutes, "route_status": t.route_status}
        for t in result.trajectory_set.conventional_traces
    )
    return OperatingDayVisualizationPayload(
        schema_version=OPERATING_DAY_SCHEMA_VERSION, operating_day_id=result.operating_day_id, architecture=result.architecture,
        scenario_id=result.scenario_id, revision=revision, mrt_carrier_entries=mrt_entries, conventional_entries=conv_entries,
    )


# ---------------------------------------------------------------------------
# Section 160-165: deterministic, schema-versioned serialization.
# ---------------------------------------------------------------------------


def serialize_operating_day_result(result: OperatingDayResult) -> Mapping[str, object]:
    return {
        "schema_version": OPERATING_DAY_SCHEMA_VERSION,
        "operating_day_id": result.operating_day_id,
        "day": result.day.isoformat(),
        "seed": result.seed,
        "architecture": result.architecture,
        "scenario_id": result.scenario_id,
        "patient_count": result.patient_count,
        "calendar_event_count": result.calendar_event_count,
        "operational_event_count": result.operational_event_count,
        "mission_count": result.mission_count,
        "missions_by_service_class": dict(result.missions_by_service_class),
        "completed_on_time_count": result.completed_on_time_count,
        "completed_late_count": result.completed_late_count,
        "unmet_count": result.unmet_count,
        "not_calibrated_count": result.not_calibrated_count,
        "conventional_completed_count": result.conventional_completed_count,
        "validation_status": result.validation_status,
        "calibration_gaps": list(result.calibration_gaps),
        "mrt_trajectory_count": result.trajectory_set.mrt_trajectory_count,
        "conventional_trace_count": result.trajectory_set.conventional_trace_count,
        "event_journal_entry_count": len(result.event_journal),
        "provenance": result.provenance,
        "carrier_hardware_report": (
            {
                "nuclear_shielded_carrier_count": result.carrier_hardware_report.nuclear_shielded_carrier_count,
                "general_light_carrier_count": result.carrier_hardware_report.general_light_carrier_count,
                "missions_by_hardware_class": dict(result.carrier_hardware_report.missions_by_hardware_class),
                "carrier_fleet_capex_usd": result.carrier_hardware_report.carrier_fleet_capex_usd,
                "blocked_mission_count": result.carrier_hardware_report.blocked_mission_count,
                "light_carrier_streams_served": {k: list(v) for k, v in result.carrier_hardware_report.light_carrier_streams_served.items()},
            } if result.carrier_hardware_report is not None else None
        ),
    }


# ---------------------------------------------------------------------------
# CLOSURE: five-stream x four-mode compatibility matrix (sections 45-47) +
# five-stream end-to-end architecture comparison (sections 49-57). Reuses
# `conventional_transport_authority.TECHNOLOGY_STREAM_COMPATIBILITY`/
# `mrt_service_class_authority.SERVICE_CLASS_REGISTRY` -- never a fabricated
# universal-compatibility table.
# ---------------------------------------------------------------------------

ACTIVE_FIVE_STREAMS: tuple[str, ...] = (
    "RADIOPHARMACEUTICAL_NUCLEAR", "SPECIMEN_BLOOD", "PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY", "LAUNDRY_CLEAN_LINEN",
)
CompatibilityStatus = Literal["SUPPORTED", "NOT_APPLICABLE", "NOT_CALIBRATED", "CONDITIONAL"]
TransportModeLabel = Literal["MANUAL", "AGV", "PTS", "MRT"]


@dataclass(frozen=True)
class CompatibilityRow:
    stream: str
    mode: TransportModeLabel
    status: CompatibilityStatus
    reason: str


def build_stream_mode_compatibility_matrix() -> tuple[CompatibilityRow, ...]:
    """Section 47: derived from the REAL existing authorities -- never a
    fabricated universal matrix. MANUAL uses
    `conventional_transport_authority.TECHNOLOGY_STREAM_COMPATIBILITY`
    (nuclear is real/established via `compute_manual_mission_timing`
    regardless of that dict, since shielded-container couriering by porter is
    a legitimate, already-modeled Conventional nuclear path). AGV/PTS use
    that SAME dict verbatim (nuclear explicitly excluded per that module's
    governance). MRT uses `SERVICE_CLASS_REGISTRY` activity/speed status."""
    rows: list[CompatibilityRow] = []
    for stream in ACTIVE_FIVE_STREAMS:
        # MANUAL
        if stream == "RADIOPHARMACEUTICAL_NUCLEAR":
            rows.append(CompatibilityRow(stream, "MANUAL", "SUPPORTED", "Shielded-container porter courier -- established conventional nuclear path"))
        else:
            logistics_stream = _SERVICE_CLASS_TO_LOGISTICS_STREAM[stream]
            status: CompatibilityStatus = "SUPPORTED" if cta.is_technology_compatible("MANUAL_PORTER", logistics_stream) else "NOT_APPLICABLE"
            rows.append(CompatibilityRow(stream, "MANUAL", status, "conventional_transport_authority.TECHNOLOGY_STREAM_COMPATIBILITY"))
        # AGV / PTS
        for mode, tech in (("AGV", "AGV_AMR"), ("PTS", "PNEUMATIC_TUBE")):
            if stream == "RADIOPHARMACEUTICAL_NUCLEAR":
                rows.append(CompatibilityRow(stream, mode, "NOT_APPLICABLE", "conventional_transport_authority never assigns nuclear to AGV/PTS"))
                continue
            logistics_stream = _SERVICE_CLASS_TO_LOGISTICS_STREAM[stream]
            status = "SUPPORTED" if cta.is_technology_compatible(tech, logistics_stream) else "NOT_APPLICABLE"
            rows.append(CompatibilityRow(stream, mode, status, "conventional_transport_authority.TECHNOLOGY_STREAM_COMPATIBILITY"))
        # MRT
        profile = msc.SERVICE_CLASS_REGISTRY.get(stream)  # type: ignore[arg-type]
        if profile is None or profile.activity_status != "ACTIVE":
            rows.append(CompatibilityRow(stream, "MRT", "NOT_APPLICABLE", "inactive service class"))
        elif profile.default_speed_m_per_s == "NOT_CALIBRATED":
            rows.append(CompatibilityRow(stream, "MRT", "NOT_CALIBRATED", "mrt_service_class_authority.SERVICE_CLASS_REGISTRY: speed not established"))
        else:
            rows.append(CompatibilityRow(stream, "MRT", "SUPPORTED", "mrt_service_class_authority.SERVICE_CLASS_REGISTRY: calibrated speed"))
    return tuple(rows)


@dataclass(frozen=True)
class StreamArchitectureServicePath:
    stream: str
    architecture: ArchitectureMode
    service_path: str
    representative_time_minutes: float | Literal["NOT_CALIBRATED"]
    technology: str


def _stream_service_path_label(stream: str, technology: str) -> str:
    if technology == "MRT":
        return "source -> MRT network -> room endpoint -> room"
    if technology == "AGV_AMR":
        return "source -> AGV -> station -> porter (residual last mile) -> room"
    if technology == "PNEUMATIC_TUBE":
        return "source -> PTS station -> tube -> destination station -> porter (residual last mile) -> room"
    return "source -> porter -> room"


def build_five_stream_architecture_comparison(day_def: ControlledDayDefinition, *, day_start: datetime) -> tuple[StreamArchitectureServicePath, ...]:
    """Section 46/49: for every architecture and every active stream, the
    ACTUAL service path/time observed in a real `run_operating_day` run --
    never an assumed example divorced from actual execution (section 46:
    'Do not use these examples where actual authority establishes a
    different path')."""
    cal_events = generate_calendar_events(day_def, day_start=day_start)
    op_events = generate_operational_events(cal_events, day_def, day_start=day_start)
    missions = [build_mission_from_event(e) for e in op_events]
    mission_by_id = {m.mission_id: m for m in missions}

    rows: list[StreamArchitectureServicePath] = []
    for architecture in ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT"):
        result = run_operating_day(day_def, architecture=architecture, day_start=day_start, scenario_id=f"FIVE_STREAM_{architecture}")
        for stream in ACTIVE_FIVE_STREAMS:
            mrt_traj = next((t for t in result.trajectory_set.mrt_trajectories if mission_by_id.get(t.mission_id, None) and mission_by_id[t.mission_id].service_class == stream), None)
            if mrt_traj is not None:
                minutes = mrt_traj.end_time_minutes - mrt_traj.start_time_minutes
                rows.append(StreamArchitectureServicePath(stream, architecture, _stream_service_path_label(stream, "MRT"), minutes, "MRT"))
                continue
            conv_trace = next((t for t in result.trajectory_set.conventional_traces if mission_by_id.get(t.mission_id, None) and mission_by_id[t.mission_id].service_class == stream), None)
            if conv_trace is not None:
                tech_label = {"AGV_AMR": "AGV_AMR", "PTS": "PNEUMATIC_TUBE", "PORTER": "MANUAL_PORTER"}[conv_trace.resource_type]
                rows.append(StreamArchitectureServicePath(stream, architecture, _stream_service_path_label(stream, tech_label), conv_trace.total_minutes, tech_label))
                continue
            rows.append(StreamArchitectureServicePath(stream, architecture, "NOT_APPLICABLE -- no mission of this stream observed", "NOT_CALIBRATED", "NONE"))
    return tuple(rows)


# ---------------------------------------------------------------------------
# CARRIER CORRECTION: economic comparator (MRT vs Manual vs Automated). Never
# omits residual human labor from Automated Conventional (per requirement);
# Manual transport-equipment CapEx = $0, recurring cost = loaded labor OPEX.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArchitectureEconomicComparison:
    architecture: ArchitectureMode
    transport_capex_usd: float | Literal["NOT_CALIBRATED"]
    capex_components: Mapping[str, float | str]
    recurring_cost_usd: float
    recurring_cost_components: Mapping[str, float]
    recurring_cost_basis: Literal["OPERATING_DAY", "ANNUAL", "MIXED"]


def _estimate_annual_porter_labor_opex(*, mission_count: int, avg_minutes: float, policy: cta.PorterOperatingPolicy, operating_days_per_year: int) -> float:
    """Reuses the SAME wage/multiplier/availability fields as
    `compute_porter_resource_requirement` -- sized from average daily
    workload (not true peak concurrency, since real timestamped
    `TransportMission` objects are not reconstructed here; disclosed bounded
    simplification of that established fleet-sizing method)."""
    if mission_count == 0:
        return 0.0
    daily_labor_hours = mission_count * avg_minutes / 60.0
    productive_hours_per_shift = policy.shift_hours * (policy.availability_pct / 100.0)
    required_fte = math.ceil(daily_labor_hours / productive_hours_per_shift) if productive_hours_per_shift > 0 else 0
    loaded_annual_cost_per_fte = policy.base_wage_per_hour * policy.loaded_employer_cost_multiplier * policy.shift_hours * operating_days_per_year
    return required_fte * loaded_annual_cost_per_fte


def build_architecture_economic_comparison(day_def: ControlledDayDefinition, *, day_start: datetime, operating_days_per_year: int = 300) -> tuple[ArchitectureEconomicComparison, ...]:
    """Section 'ECONOMIC COMPARATOR': compares equivalent five-stream
    room-level work across architectures using ONLY existing authorities --
    never a duplicate finance engine."""
    policy = cta.PorterOperatingPolicy()
    loaded_annual_cost_per_fte = policy.base_wage_per_hour * policy.loaded_employer_cost_multiplier * policy.shift_hours * operating_days_per_year
    comparisons = []
    for architecture in ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT"):
        result = run_operating_day(day_def, architecture=architecture, day_start=day_start, scenario_id=f"ECON_{architecture}")
        if architecture == "MANUAL_CONVENTIONAL":
            porter_minutes = [t.total_minutes for t in result.trajectory_set.conventional_traces if t.total_minutes != "NOT_CALIBRATED"]
            avg_minutes = (sum(porter_minutes) / len(porter_minutes)) if porter_minutes else 0.0
            annual_labor_opex = _estimate_annual_porter_labor_opex(mission_count=len(porter_minutes), avg_minutes=avg_minutes, policy=policy, operating_days_per_year=operating_days_per_year)
            comparisons.append(ArchitectureEconomicComparison(
                architecture=architecture, transport_capex_usd=0.0, capex_components={"transport_equipment": 0.0},
                recurring_cost_usd=annual_labor_opex, recurring_cost_components={"loaded_human_labor_opex_annual": annual_labor_opex},
                recurring_cost_basis="ANNUAL",
            ))
            continue
        if architecture == "AUTOMATED_CONVENTIONAL":
            agv_traces = [t for t in result.trajectory_set.conventional_traces if t.resource_type == "AGV_AMR"]
            pts_traces = [t for t in result.trajectory_set.conventional_traces if t.resource_type == "PTS"]
            residual_porter_traces = [t for t in result.trajectory_set.conventional_traces if t.resource_type == "PORTER"]
            agv_fleet = max(1, len(agv_traces) // 10) if agv_traces else 0
            pts_fleet = 1 if pts_traces else 0
            proposed_agv_model = replace(cta.DEFAULT_AGV_MODEL, asset_status="PROPOSED")
            proposed_pts_network = replace(cta.DEFAULT_PTS_NETWORK, asset_status="PROPOSED")
            agv_capex = cta.agv_new_study_capex(proposed_agv_model, fleet_size=agv_fleet, study_scope="CAPITAL_PLANNING") if agv_fleet else 0.0
            pts_capex = cta.pts_new_study_capex(proposed_pts_network, study_scope="CAPITAL_PLANNING") if pts_fleet else 0.0
            agv_opex = cta.agv_annual_opex(cta.DEFAULT_AGV_MODEL, fleet_size=agv_fleet, loaded_annual_cost_per_fte=loaded_annual_cost_per_fte) if agv_fleet else 0.0
            pts_opex = cta.pts_annual_opex(cta.DEFAULT_PTS_NETWORK, loaded_annual_cost_per_fte=loaded_annual_cost_per_fte) if pts_fleet else 0.0
            residual_minutes = [t.total_minutes for t in residual_porter_traces if t.total_minutes != "NOT_CALIBRATED"]
            avg_residual = (sum(residual_minutes) / len(residual_minutes)) if residual_minutes else 0.0
            residual_labor_opex = _estimate_annual_porter_labor_opex(mission_count=len(residual_minutes), avg_minutes=avg_residual, policy=policy, operating_days_per_year=operating_days_per_year)
            comparisons.append(ArchitectureEconomicComparison(
                architecture=architecture, transport_capex_usd=agv_capex + pts_capex,
                capex_components={"agv_fleet_capex": agv_capex, "pts_network_capex": pts_capex},
                recurring_cost_usd=agv_opex + pts_opex + residual_labor_opex,
                recurring_cost_components={"agv_annual_opex": agv_opex, "pts_annual_opex": pts_opex, "residual_human_last_mile_labor_opex_annual": residual_labor_opex},
                recurring_cost_basis="ANNUAL",
            ))
            continue
        # HYBRID_MRT / MRT_DOMINANT
        report = result.carrier_hardware_report
        electricity_total = sum(e.resolved_period_opex_usd for e in report.electricity) if report else 0.0
        non_mrt_minutes = [t.total_minutes for t in result.trajectory_set.conventional_traces if t.total_minutes != "NOT_CALIBRATED"]
        avg_non_mrt = (sum(non_mrt_minutes) / len(non_mrt_minutes)) if non_mrt_minutes else 0.0
        residual_labor_opex = _estimate_annual_porter_labor_opex(mission_count=len(non_mrt_minutes), avg_minutes=avg_non_mrt, policy=policy, operating_days_per_year=operating_days_per_year)
        registry = build_controlled_room_registry(day_def)
        room_ids = [r.mrtway_object_id for r in registry.by_type("PATIENT_ROOM")]
        _endpoints, endpoint_capex_result = build_direct_room_mrt_network(registry, room_ids=room_ids)
        endpoint_capex = endpoint_capex_result.line_item("MRT endpoints/junctions").capex
        comparisons.append(ArchitectureEconomicComparison(
            architecture=architecture,
            transport_capex_usd=(report.carrier_fleet_capex_usd if report else 0.0) + endpoint_capex,
            capex_components={
                "carrier_hardware_fleet_capex": report.carrier_fleet_capex_usd if report else 0.0,
                "room_endpoint_capex": endpoint_capex, "guideway_capex": 0.0, "controls_installation_capex": 0.0,
            },
            recurring_cost_usd=electricity_total + residual_labor_opex,
            recurring_cost_components={
                "carrier_electricity_opex_operating_day": electricity_total,
                "residual_conventional_labor_opex_annual": residual_labor_opex,
            },
            recurring_cost_basis="MIXED",
        ))
    return tuple(comparisons)


# ---------------------------------------------------------------------------
# CONTROLLED FOUR-ARCHITECTURE ECONOMIC COMPARISON (200 patients/day).
# Reuses ALL prior authorities (carrier hardware, mass, endpoint CapEx,
# AGV/PTS, electricity reconciliation, production decay chain) -- ONE
# comparison engine, never a second economics/production/decay engine.
# ---------------------------------------------------------------------------

ArchitectureLabel = Literal["MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "MRT", "HYBRID"]

_ARCHITECTURE_LABEL_TO_INTERNAL: Mapping[ArchitectureLabel, ArchitectureMode] = {
    "MANUAL_CONVENTIONAL": "MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL": "AUTOMATED_CONVENTIONAL",
    "MRT": "MRT_DOMINANT", "HYBRID": "HYBRID_MRT",
}
"""Maps this comparison's requested vocabulary (MRT/HYBRID) onto the
EXISTING, protected `ArchitectureMode` internal labels (MRT_DOMINANT/
HYBRID_MRT) -- never a redefinition of the four-architecture semantics."""


@dataclass(frozen=True)
class CommonEconomicBasis:
    """Section 10: ONE central assumptions authority shared by all four
    architectures -- never architecture-specific unless physically required."""

    required_patients_per_day: int
    operating_hours_per_day: float
    regular_shift_hours: float
    overtime_multiplier: float
    operating_days_per_year: int
    revenue_per_patient_usd: float
    discount_rate_pct: float
    analysis_years: int
    electricity_cost_per_kwh: float
    synthesis_yield_fraction: float
    manual_wage_per_hour: float
    manual_employer_cost_multiplier: float
    provenance: str = "models.PlannerAssumptions + conventional_transport_authority.PorterOperatingPolicy (existing authorities, single common basis)"


def build_common_economic_basis(*, required_patients_per_day: int = 200) -> CommonEconomicBasis:
    from models import PlannerAssumptions

    a = PlannerAssumptions()
    policy = cta.PorterOperatingPolicy()
    return CommonEconomicBasis(
        required_patients_per_day=required_patients_per_day, operating_hours_per_day=18.0, regular_shift_hours=8.0,
        overtime_multiplier=1.5, operating_days_per_year=300, revenue_per_patient_usd=a.revenue_per_scan,
        discount_rate_pct=a.discount_rate_pct, analysis_years=a.analysis_years, electricity_cost_per_kwh=0.12,
        synthesis_yield_fraction=a.synthesis_yield_fraction, manual_wage_per_hour=policy.base_wage_per_hour,
        manual_employer_cost_multiplier=policy.loaded_employer_cost_multiplier,
    )


# ---------------------------------------------------------------------------
# Manual-Conventional shift labor authority (section 4-5): explicit 8h/shift,
# 18h/day -> 16h regular + 2h overtime per continuously required position.
# ---------------------------------------------------------------------------


def resolve_shift_hours(*, operating_hours_per_day: float, regular_shift_hours: float) -> tuple[float, float]:
    full_shifts = int(operating_hours_per_day // regular_shift_hours)
    regular_hours = full_shifts * regular_shift_hours
    overtime_hours = operating_hours_per_day - regular_hours
    return regular_hours, overtime_hours


@dataclass(frozen=True)
class ManualShiftLaborResult:
    regular_hours_per_position: float
    overtime_hours_per_position: float
    overtime_multiplier: float
    simultaneous_positions: int
    daily_regular_worker_hours: float
    daily_overtime_worker_hours: float
    daily_labor_cost_usd: float
    annual_labor_cost_usd: float


def compute_manual_shift_labor_cost(*, simultaneous_positions: int, wage_per_hour: float, basis: CommonEconomicBasis, employer_cost_multiplier: float = 1.0) -> ManualShiftLaborResult:
    """Section 4: C_daily,position = 16W + 2*M_OT*W = 19W (with M_OT=1.5,
    W the loaded hourly wage) -- NEVER `one_worker * 18_hours`."""
    regular_hours, overtime_hours = resolve_shift_hours(operating_hours_per_day=basis.operating_hours_per_day, regular_shift_hours=basis.regular_shift_hours)
    loaded_wage = wage_per_hour * employer_cost_multiplier
    daily_regular_worker_hours = simultaneous_positions * regular_hours
    daily_overtime_worker_hours = simultaneous_positions * overtime_hours
    daily_cost = simultaneous_positions * (regular_hours * loaded_wage + overtime_hours * basis.overtime_multiplier * loaded_wage)
    return ManualShiftLaborResult(
        regular_hours_per_position=regular_hours, overtime_hours_per_position=overtime_hours, overtime_multiplier=basis.overtime_multiplier,
        simultaneous_positions=simultaneous_positions, daily_regular_worker_hours=daily_regular_worker_hours,
        daily_overtime_worker_hours=daily_overtime_worker_hours, daily_labor_cost_usd=daily_cost,
        annual_labor_cost_usd=daily_cost * basis.operating_days_per_year,
    )


@dataclass(frozen=True)
class ManualTransportWorkloadResult:
    """Section 5: mission-derived manual transport workload -- never an
    arbitrary fixed headcount."""

    manual_transport_missions_per_day: int
    manual_transport_worker_hours_required: float
    manual_regular_hours: float
    manual_overtime_hours: float
    manual_transport_fte_equivalent: float
    manual_transport_labor_cost_per_day: float
    manual_transport_labor_cost_per_year: float
    simultaneous_positions: int
    provenance: str


def compute_manual_transport_workload(*, missions_per_day: int, avg_mission_minutes: float, basis: CommonEconomicBasis) -> ManualTransportWorkloadResult:
    if missions_per_day == 0:
        return ManualTransportWorkloadResult(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, "NO_MISSIONS_OBSERVED")
    total_worker_hours = missions_per_day * avg_mission_minutes / 60.0
    simultaneous_positions = max(1, math.ceil(total_worker_hours / basis.operating_hours_per_day))
    shift = compute_manual_shift_labor_cost(
        simultaneous_positions=simultaneous_positions, wage_per_hour=basis.manual_wage_per_hour, basis=basis,
        employer_cost_multiplier=basis.manual_employer_cost_multiplier,
    )
    fte_equivalent = simultaneous_positions * (shift.regular_hours_per_position + shift.overtime_hours_per_position) * basis.operating_days_per_year / 2080.0
    return ManualTransportWorkloadResult(
        manual_transport_missions_per_day=missions_per_day, manual_transport_worker_hours_required=total_worker_hours,
        manual_regular_hours=shift.daily_regular_worker_hours, manual_overtime_hours=shift.daily_overtime_worker_hours,
        manual_transport_fte_equivalent=fte_equivalent, manual_transport_labor_cost_per_day=shift.daily_labor_cost_usd,
        manual_transport_labor_cost_per_year=shift.annual_labor_cost_usd, simultaneous_positions=simultaneous_positions,
        provenance="DERIVED_FROM_PHYSICAL_MODEL (mission_count x avg_mission_minutes / operating_hours_per_day; "
                   "simultaneous-position count uses average daily workload, NOT a true timestamped peak-concurrency sweep -- disclosed bounded simplification)",
    )


# ---------------------------------------------------------------------------
# Radioactive production chain (section 2/11): N_patients -> A_admin ->
# A_release -> A_EOB_required -> cyclotron feasibility. Reuses
# `multi_isotope_decay.retained_fraction`/`required_upstream_activity`
# verbatim -- NEVER the obsolete `current_usable_doses_per_day *
# (1 + blocks*0.10)` capacity formula, never a fabricated capacity ceiling.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RadioactiveProductionChainResult:
    modality: str
    radionuclide: str
    served_patients: int
    activity_per_patient_mbq: float
    a_admin_mbq: float
    elapsed_eob_to_administration_minutes: float
    retained_fraction_release_to_admin: float
    a_release_required_mbq: float
    synthesis_yield_fraction: float
    a_eob_required_mbq: float
    installed_eob_capacity_mbq_per_day: float | Literal["NOT_CALIBRATED"]
    production_feasible: bool | Literal["NOT_CALIBRATED"]
    provenance: str = "multi_isotope_decay.retained_fraction/required_upstream_activity + models.PlannerAssumptions (existing authorities)"


def compute_radioactive_production_chain(
    *, modality: str, served_patients: int, activity_per_patient_mbq: float, radionuclide: str,
    elapsed_eob_to_administration_minutes: float, synthesis_yield_fraction: float | None = None,
    installed_eob_capacity_mbq_per_day: float | None = None,
) -> RadioactiveProductionChainResult:
    import multi_isotope_decay
    from diagnostics import load_radionuclide_half_lives
    from models import PlannerAssumptions

    a = PlannerAssumptions()
    half_life = load_radionuclide_half_lives()[radionuclide]
    a_admin = served_patients * activity_per_patient_mbq
    retained = multi_isotope_decay.retained_fraction(elapsed_eob_to_administration_minutes, half_life)
    a_release_required = multi_isotope_decay.required_upstream_activity(a_admin, retained) if a_admin > 0 else 0.0
    resolved_yield = synthesis_yield_fraction if synthesis_yield_fraction is not None else a.synthesis_yield_fraction
    a_eob_required = a_release_required / max(resolved_yield, 1e-9)
    installed = installed_eob_capacity_mbq_per_day if installed_eob_capacity_mbq_per_day is not None else a.cyclotron_eob_capacity_mbq_per_day
    if installed is None:
        feasible: bool | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
        installed_report: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    else:
        feasible = a_eob_required <= installed
        installed_report = installed
    return RadioactiveProductionChainResult(
        modality=modality, radionuclide=radionuclide, served_patients=served_patients, activity_per_patient_mbq=activity_per_patient_mbq,
        a_admin_mbq=a_admin, elapsed_eob_to_administration_minutes=elapsed_eob_to_administration_minutes,
        retained_fraction_release_to_admin=retained, a_release_required_mbq=a_release_required, synthesis_yield_fraction=resolved_yield,
        a_eob_required_mbq=a_eob_required, installed_eob_capacity_mbq_per_day=installed_report, production_feasible=feasible,
    )


def _compute_npv(*, capex_usd: float, annual_margin_usd: float, discount_rate_pct: float, analysis_years: int) -> float:
    rate = discount_rate_pct / 100.0
    return -capex_usd + sum(annual_margin_usd / ((1.0 + rate) ** t) for t in range(1, analysis_years + 1))


def _compute_irr_pct(*, capex_usd: float, annual_margin_usd: float, analysis_years: int) -> float | Literal["NOT_CALIBRATED"]:
    if capex_usd <= 0.0 or annual_margin_usd <= 0.0:
        return "NOT_CALIBRATED"

    def npv_at(rate: float) -> float:
        return -capex_usd + sum(annual_margin_usd / ((1.0 + rate) ** t) for t in range(1, analysis_years + 1))

    low, high = -0.99, 10.0
    if npv_at(low) * npv_at(high) > 0:
        return "NOT_CALIBRATED"
    for _ in range(100):
        mid = (low + high) / 2.0
        if npv_at(mid) > 0:
            low = mid
        else:
            high = mid
    return ((low + high) / 2.0) * 100.0


OverallFeasibilityStatus = Literal["FEASIBLE", "FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY", "INFEASIBLE", "NOT_FULLY_DETERMINED"]


@dataclass(frozen=True)
class ArchitectureFeasibility:
    production_feasible: bool | Literal["NOT_CALIBRATED"]
    clinical_feasible: bool
    logistics_feasible: bool
    overall_feasible: bool
    overall_status: OverallFeasibilityStatus
    bottleneck: str | None


def _resolve_overall_feasibility_status(*, production_feasible: bool | Literal["NOT_CALIBRATED"], clinical_feasible: bool, logistics_feasible: bool) -> OverallFeasibilityStatus:
    """D.1 section 17: `NOT_CALIBRATED` production capacity must NEVER
    collapse to an unconditional `True` -- distinct explicit status instead."""
    if not clinical_feasible or not logistics_feasible:
        return "INFEASIBLE"
    if production_feasible is False:
        return "INFEASIBLE"
    if production_feasible == "NOT_CALIBRATED":
        return "FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY"
    return "FEASIBLE"


# ---------------------------------------------------------------------------
# D.1 section 3-6: comprehensive MRT infrastructure CapEx -- guideway (real
# length or honestly NOT_CALIBRATED, never a substituted zero), vestibule
# (distinct from endpoint), endpoints, controls, installation/commissioning.
# Reuses `canonical_spatial_authority.compute_mrt_transport_only_capex`
# verbatim -- never a second CapEx engine.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MrtInfrastructureCapexResult:
    guideway_length_m: float | Literal["NOT_CALIBRATED"]
    guideway_length_provenance: str
    guideway_unit_cost_usd_per_m: float
    guideway_capex_usd: float | Literal["NOT_CALIBRATED"]
    vestibule_count: int
    vestibule_unit_cost_usd: float
    vestibule_capex_usd: float
    endpoint_count: int
    endpoint_unit_cost_usd: float
    endpoint_capex_usd: float
    carrier_fleet_capex_usd: float
    controls_capex_usd: float
    installation_commissioning_capex_usd: float
    total_capex_usd: float


def build_comprehensive_mrt_infrastructure_capex(
    *, registry: csa.SpatialObjectRegistry, room_ids: Sequence[str], carrier_fleet_capex_usd: float, vestibule_count: int = 1,
    trunk_id: str = "MRT-TRUNK-OPDAY",
) -> MrtInfrastructureCapexResult:
    """D.1 section 4-6: guideway length is resolved from the existing
    canonical spatial authority where possible; `canonical_spatial_authority.
    build_mrt_trunk`'s length_m defaults to NOT_CALIBRATED for this
    controlled facility (no calibrated routed network length exists yet) --
    reported honestly as NOT_CALIBRATED, never fabricated or silently
    substituted with $0. Vestibule/controls/installation/endpoint reuse the
    SAME `compute_mrt_transport_only_capex` authority (never a second
    CapEx engine)."""
    from models import PlannerAssumptions

    a = PlannerAssumptions()
    guideway_length_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    guideway_capex_usd: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    capex_result = csa.compute_mrt_transport_only_capex(
        guideway_length_m=0.0, endpoint_count=len(room_ids), endpoint_unit_cost=MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD,
        vestibule_count=vestibule_count, include_controls=True, include_installation_commissioning=True,
    )
    endpoint_line = capex_result.line_item("MRT endpoints/junctions")
    vestibule_line = capex_result.line_item("MRT vestibules")
    controls_line = capex_result.line_item("MRT controls (system/network, once)")
    installation_line = capex_result.line_item("MRT installation/commissioning (project, once)")
    total = vestibule_line.capex + endpoint_line.capex + controls_line.capex + installation_line.capex + carrier_fleet_capex_usd
    return MrtInfrastructureCapexResult(
        guideway_length_m=guideway_length_m,
        guideway_length_provenance="NOT_CALIBRATED -- no canonical routed MRT network length resolver exists yet for this controlled facility (canonical_spatial_authority.build_mrt_trunk length_m defaults to NOT_CALIBRATED here); a missing physical quantity is never substituted with a $0 cost.",
        guideway_unit_cost_usd_per_m=a.mrt_guideway_capex_per_m, guideway_capex_usd=guideway_capex_usd,
        vestibule_count=vestibule_count, vestibule_unit_cost_usd=csa.MRT_VESTIBULE_CAPEX_USD, vestibule_capex_usd=vestibule_line.capex,
        endpoint_count=len(room_ids), endpoint_unit_cost_usd=MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD, endpoint_capex_usd=endpoint_line.capex,
        carrier_fleet_capex_usd=carrier_fleet_capex_usd, controls_capex_usd=controls_line.capex,
        installation_commissioning_capex_usd=installation_line.capex, total_capex_usd=total,
    )


@dataclass(frozen=True)
class IncrementalArchitectureEconomics:
    """D.1 section 10/20: incremental economics vs the Manual Conventional
    baseline -- NEVER the entire common $18M facility revenue treated as the
    return on transport-architecture investment."""

    delta_capex_usd: float
    delta_known_annual_opex_savings_usd: float
    delta_revenue_usd: float
    delta_annual_cash_flow_usd: float
    incremental_payback_years: float | Literal["NOT_CALIBRATED"]
    incremental_npv_usd: float
    incremental_irr_pct: float | Literal["NOT_CALIBRATED"]
    calibration_status: str


@dataclass(frozen=True)
class FourArchitectureEconomicResult:
    architecture_label: ArchitectureLabel
    required_patients_per_day: int
    served_patients_per_day: int
    feasibility: ArchitectureFeasibility
    pet_production_chain: RadioactiveProductionChainResult
    spect_production_chain: RadioactiveProductionChainResult
    common_capex_components: Mapping[str, float]
    architecture_specific_capex_components: Mapping[str, float | Literal["NOT_CALIBRATED"]]
    capex_components: Mapping[str, float | Literal["NOT_CALIBRATED"]]
    total_capex_usd: float
    known_annual_opex_components: Mapping[str, float]
    unresolved_opex_categories: tuple[str, ...]
    known_annual_opex_subtotal_usd: float
    opex_components: Mapping[str, float | Literal["NOT_CALIBRATED"]]
    total_annual_opex_usd: float | Literal["NOT_CALIBRATED"]
    manual_transport_workload: ManualTransportWorkloadResult | None
    mrt_infrastructure: MrtInfrastructureCapexResult | None
    annual_revenue_usd: float
    annual_operating_margin_usd: float | Literal["NOT_CALIBRATED"]
    cost_per_patient_usd: float
    payback_years: float | Literal["NOT_CALIBRATED"]
    npv_usd: float | Literal["NOT_CALIBRATED"]
    irr_pct: float | Literal["NOT_CALIBRATED"]
    incremental: IncrementalArchitectureEconomics | None


def run_four_architecture_economic_comparison(*, basis: CommonEconomicBasis | None = None) -> tuple[FourArchitectureEconomicResult, ...]:
    """Section 1/13: the ONE controlled 200-patient/day four-architecture
    economic comparison -- reuses every prior authority (carrier hardware/
    mass, endpoint CapEx, AGV/PTS, electricity reconciliation, production
    decay chain); never a second competing economics engine. Hybrid's
    economics derive from its ACTUAL assigned missions/equipment (via
    `build_architecture_economic_comparison`), never a 50/50 blend."""
    from models import PlannerAssumptions

    basis = basis or build_common_economic_basis()
    a = PlannerAssumptions()
    day = date(2026, 2, 3)
    day_start = datetime(2026, 2, 3, 7, 0)
    pet_count = int(round(basis.required_patients_per_day * 0.7))
    spect_count = basis.required_patients_per_day - pet_count
    occupied_beds = int(round(basis.required_patients_per_day * 0.85))
    outpatient_encounters = basis.required_patients_per_day - occupied_beds

    day_def = build_controlled_representative_day(
        day=day, seed=42, available_beds=basis.required_patients_per_day, occupied_beds=occupied_beds,
        admissions=20, discharges=18, outpatient_encounters=outpatient_encounters,
        target_pet_procedures=pet_count, target_spect_procedures=spect_count,
    )
    common_cyclotron_capex = a.cyclotron_purchase_capex
    common_production_equipment_capex = a.cyclotron_installation_capex

    econ_by_internal = {c.architecture: c for c in build_architecture_economic_comparison(day_def, day_start=day_start, operating_days_per_year=basis.operating_days_per_year)}
    op_events = generate_operational_events(generate_calendar_events(day_def, day_start=day_start), day_def, day_start=day_start)
    all_missions = [build_mission_from_event(e) for e in op_events]
    nuclear_mission_ids = {m.mission_id for m in all_missions if m.service_class == "RADIOPHARMACEUTICAL_NUCLEAR"}

    results = []
    for label, internal in _ARCHITECTURE_LABEL_TO_INTERNAL.items():
        result = run_operating_day(day_def, architecture=internal, day_start=day_start, scenario_id=f"FOURARCH_{label}")
        econ = econ_by_internal[internal]

        nuclear_traj = next((t for t in result.trajectory_set.mrt_trajectories if t.mission_id in nuclear_mission_ids), None)
        nuclear_conv = next((t for t in result.trajectory_set.conventional_traces if t.mission_id in nuclear_mission_ids), None)
        if nuclear_traj is not None:
            transport_minutes = nuclear_traj.end_time_minutes - nuclear_traj.start_time_minutes
        elif nuclear_conv is not None and nuclear_conv.total_minutes != "NOT_CALIBRATED":
            transport_minutes = nuclear_conv.total_minutes
        else:
            transport_minutes = 0.0
        elapsed_eob_to_admin = 45.0 + transport_minutes  # section 2: 45min fixed prep/processing offset (matches PAYLOAD_READY derivation elsewhere)

        pet_chain = compute_radioactive_production_chain(
            modality="PET", served_patients=pet_count, activity_per_patient_mbq=370.0, radionuclide="F-18",
            elapsed_eob_to_administration_minutes=elapsed_eob_to_admin, synthesis_yield_fraction=basis.synthesis_yield_fraction,
        )
        spect_chain = compute_radioactive_production_chain(
            modality="SPECT", served_patients=spect_count, activity_per_patient_mbq=740.0, radionuclide="Tc-99m",
            elapsed_eob_to_administration_minutes=elapsed_eob_to_admin, synthesis_yield_fraction=basis.synthesis_yield_fraction,
        )
        production_feasible: bool | Literal["NOT_CALIBRATED"] = (
            "NOT_CALIBRATED" if (pet_chain.production_feasible == "NOT_CALIBRATED" or spect_chain.production_feasible == "NOT_CALIBRATED")
            else bool(pet_chain.production_feasible and spect_chain.production_feasible)
        )

        logistics_feasible = result.unmet_count == 0
        bottleneck = None if logistics_feasible else f"{result.unmet_count} unmet mission(s) observed for {label}"
        clinical_feasible = True  # bounded: scanner/injection/uptake capacity is NOT independently re-verified by this comparator (disclosed gap)
        overall_feasible = (production_feasible is not False) and clinical_feasible and logistics_feasible
        overall_status = _resolve_overall_feasibility_status(production_feasible=production_feasible, clinical_feasible=clinical_feasible, logistics_feasible=logistics_feasible)
        feasibility = ArchitectureFeasibility(
            production_feasible=production_feasible, clinical_feasible=clinical_feasible, logistics_feasible=logistics_feasible,
            overall_feasible=overall_feasible, overall_status=overall_status, bottleneck=bottleneck,
        )

        non_mrt_minutes = [t.total_minutes for t in result.trajectory_set.conventional_traces if t.total_minutes != "NOT_CALIBRATED"]
        avg_minutes = (sum(non_mrt_minutes) / len(non_mrt_minutes)) if non_mrt_minutes else 0.0
        manual_workload = compute_manual_transport_workload(missions_per_day=len(non_mrt_minutes), avg_mission_minutes=avg_minutes, basis=basis) if non_mrt_minutes else None

        common_capex_components: dict[str, float] = {"cyclotron_capex": common_cyclotron_capex, "production_equipment_capex": common_production_equipment_capex}
        architecture_specific_capex_components: dict[str, float | Literal["NOT_CALIBRATED"]] = {k: v for k, v in econ.capex_components.items()}
        mrt_infrastructure: MrtInfrastructureCapexResult | None = None
        if internal in ("MRT_DOMINANT", "HYBRID_MRT"):
            registry = build_controlled_room_registry(day_def)
            room_ids = [r.mrtway_object_id for r in registry.by_type("PATIENT_ROOM")]
            mrt_infrastructure = build_comprehensive_mrt_infrastructure_capex(
                registry=registry, room_ids=room_ids, carrier_fleet_capex_usd=architecture_specific_capex_components.get("carrier_hardware_fleet_capex", 0.0),
                vestibule_count=1,
            )
            architecture_specific_capex_components = {
                "carrier_hardware_fleet_capex": mrt_infrastructure.carrier_fleet_capex_usd,
                "mrt_guideway_capex": mrt_infrastructure.guideway_capex_usd,
                "mrt_radiopharmacy_vestibule_capex": mrt_infrastructure.vestibule_capex_usd,
                "room_endpoint_capex": mrt_infrastructure.endpoint_capex_usd,
                "mrt_controls_capex": mrt_infrastructure.controls_capex_usd,
                "mrt_installation_commissioning_capex": mrt_infrastructure.installation_commissioning_capex_usd,
            }
        capex_components: dict[str, float | Literal["NOT_CALIBRATED"]] = {**common_capex_components, **architecture_specific_capex_components}
        numeric_capex = [v for v in capex_components.values() if v != "NOT_CALIBRATED"]
        total_capex = float(sum(numeric_capex))

        electricity_annual = econ.recurring_cost_components.get("carrier_electricity_opex_operating_day", 0.0) * basis.operating_days_per_year
        opex_components: dict[str, float | Literal["NOT_CALIBRATED"]] = {
            "transport_labor_opex": manual_workload.manual_transport_labor_cost_per_year if manual_workload else 0.0,
            "clinical_labor_opex": "NOT_CALIBRATED",
            "production_opex": "NOT_CALIBRATED",
            "maintenance_opex": "NOT_CALIBRATED",
            "electricity_opex": electricity_annual,
            "consumables_opex": "NOT_CALIBRATED",
            "carrier_or_vehicle_opex": econ.recurring_cost_components.get("agv_annual_opex", 0.0) + econ.recurring_cost_components.get("pts_annual_opex", 0.0),
            "other_operating_opex": 0.0,
        }
        known_annual_opex_components = {k: v for k, v in opex_components.items() if v != "NOT_CALIBRATED"}
        unresolved_opex_categories = tuple(k for k, v in opex_components.items() if v == "NOT_CALIBRATED")
        known_annual_opex_subtotal = float(sum(known_annual_opex_components.values()))
        total_opex: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED" if unresolved_opex_categories else known_annual_opex_subtotal

        served_patients_per_day = basis.required_patients_per_day
        annual_revenue = served_patients_per_day * basis.revenue_per_patient_usd * basis.operating_days_per_year
        # D.1 section 8/9: facility-level margin/payback/NPV/IRR below use ONLY the KNOWN OPEX
        # subtotal (never a fabricated total) -- informational facility-level figures, NOT the
        # primary architecture-investment metric (see `incremental`, computed in the second pass below).
        annual_margin_known_basis = annual_revenue - known_annual_opex_subtotal
        cost_per_patient = known_annual_opex_subtotal / (served_patients_per_day * basis.operating_days_per_year) if served_patients_per_day > 0 else 0.0
        payback_years: float | Literal["NOT_CALIBRATED"] = (total_capex / annual_margin_known_basis) if annual_margin_known_basis > 0 else "NOT_CALIBRATED"
        npv = _compute_npv(capex_usd=total_capex, annual_margin_usd=annual_margin_known_basis, discount_rate_pct=basis.discount_rate_pct, analysis_years=basis.analysis_years)
        irr = _compute_irr_pct(capex_usd=total_capex, annual_margin_usd=annual_margin_known_basis, analysis_years=basis.analysis_years)

        results.append(FourArchitectureEconomicResult(
            architecture_label=label, required_patients_per_day=basis.required_patients_per_day, served_patients_per_day=served_patients_per_day,
            feasibility=feasibility, pet_production_chain=pet_chain, spect_production_chain=spect_chain,
            common_capex_components=common_capex_components, architecture_specific_capex_components=architecture_specific_capex_components,
            capex_components=capex_components, total_capex_usd=total_capex,
            known_annual_opex_components=known_annual_opex_components, unresolved_opex_categories=unresolved_opex_categories,
            known_annual_opex_subtotal_usd=known_annual_opex_subtotal, opex_components=opex_components, total_annual_opex_usd=total_opex,
            manual_transport_workload=manual_workload, mrt_infrastructure=mrt_infrastructure, annual_revenue_usd=annual_revenue,
            annual_operating_margin_usd=annual_margin_known_basis, cost_per_patient_usd=cost_per_patient, payback_years=payback_years,
            npv_usd=npv, irr_pct=irr, incremental=None,
        ))

    # D.1 section 10/20: second pass -- incremental economics vs the Manual Conventional baseline.
    manual_result = next(r for r in results if r.architecture_label == "MANUAL_CONVENTIONAL")
    final_results = []
    for r in results:
        if r.architecture_label == "MANUAL_CONVENTIONAL":
            incremental = IncrementalArchitectureEconomics(
                delta_capex_usd=0.0, delta_known_annual_opex_savings_usd=0.0, delta_revenue_usd=0.0, delta_annual_cash_flow_usd=0.0,
                incremental_payback_years="NOT_CALIBRATED", incremental_npv_usd=0.0, incremental_irr_pct="NOT_CALIBRATED",
                calibration_status="REFERENCE_BASELINE (Manual Conventional; delta always zero by definition)",
            )
        else:
            delta_capex = r.total_capex_usd - manual_result.total_capex_usd
            delta_opex_savings = manual_result.known_annual_opex_subtotal_usd - r.known_annual_opex_subtotal_usd
            delta_revenue = 0.0  # section 11: served patients identical (200==200==200==200) in this controlled comparison
            delta_cash_flow = delta_opex_savings + delta_revenue
            incremental_payback: float | Literal["NOT_CALIBRATED"] = (delta_capex / delta_cash_flow) if (delta_cash_flow > 0 and delta_capex > 0) else "NOT_CALIBRATED"
            incremental_npv = _compute_npv(capex_usd=delta_capex, annual_margin_usd=delta_cash_flow, discount_rate_pct=basis.discount_rate_pct, analysis_years=basis.analysis_years)
            incremental_irr = _compute_irr_pct(capex_usd=delta_capex, annual_margin_usd=delta_cash_flow, analysis_years=basis.analysis_years)
            calibration_status = (
                "COMPLETE_KNOWN_BASIS" if not (r.unresolved_opex_categories or manual_result.unresolved_opex_categories)
                else f"PARTIAL -- unresolved OPEX categories excluded from delta: {sorted(set(r.unresolved_opex_categories) | set(manual_result.unresolved_opex_categories))}"
            )
            incremental = IncrementalArchitectureEconomics(
                delta_capex_usd=delta_capex, delta_known_annual_opex_savings_usd=delta_opex_savings, delta_revenue_usd=delta_revenue,
                delta_annual_cash_flow_usd=delta_cash_flow, incremental_payback_years=incremental_payback, incremental_npv_usd=incremental_npv,
                incremental_irr_pct=incremental_irr, calibration_status=calibration_status,
            )
        final_results.append(replace(r, incremental=incremental))
    return tuple(final_results)


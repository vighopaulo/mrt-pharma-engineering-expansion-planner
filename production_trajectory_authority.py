"""Production Trajectory Build 1: Unified Moving-Entity Trajectory Authority.

GOVERNANCE: this module owns ONLY the derivation of authoritative,
vendor-neutral moving-entity trajectory DATA (position/time/route-segment
resolution) from EXISTING engineering/operational authorities. It:

  - does NOT select transport technology (ENGINE_SELECTS_TRANSPORT_SOLUTION
    remains the architecture optimizer's job, never this module's);
  - does NOT invent routes, speeds, mission timing, demand, or geometry --
    every number here is either read from an existing authority or resolved
    via `canonical_spatial_authority.resolve_route`/`resolve_global_position`
    (the SAME common route solver/position resolver already used
    throughout the repository, never a second one);
  - does NOT animate anything -- it produces authoritative motion DATA that
    a FUTURE concurrent-playback build, OpenUSD time-sampling, Bentley
    visualization, or NVIDIA/Omniverse consumer may later read;
  - does NOT call Bentley, OpenUSD (`pxr`), or NVIDIA/Omniverse (`omni`) --
    verified by tests scanning this module's own import lines.

AUDIT (performed before writing this module; see repo memory / session
notes for the full file-by-file findings): the repository already had TWO
distinct, non-duplicated trajectory-adjacent concepts --
`mrt_service_class_authority.CarrierTrajectory` (per-MISSION, scheduler-
derived start/end/status timing for MRT ONLY, no waypoints) and
`dynamic_scene_state_authority.DynamicObjectTrajectory` (a presentation-only,
OpenUSD-neutral time-sampled position contract, caller-supplied samples
only, no route/speed knowledge of its own). Neither one resolves piecewise
position from a REAL ordered route the way this module now does; neither is
replaced or duplicated here -- `CarrierTrajectory` is REUSED verbatim for
MRT start/end/status, and `to_dynamic_object_trajectory()` below is a
one-way BRIDGE from this module's own contract into
`DynamicObjectTrajectory`, never a redefinition of it.
`operational_day_orchestrator.ConventionalMovementTrace` is explicitly NOT a
trajectory (its own docstring says so) and is left untouched.

SIMULATION TIME (section 3): reuses `dynamic_scene_state_authority.
MRT_SIMULATION_TIME_UNIT` ("MINUTES") verbatim -- never a second clock.
OpenUSD TimeCode conversion remains exclusively an `openusd_spatial_adapter`
concern; this module is never imported by, and never imports, that adapter.

MOTION-STATE VOCABULARY (section 16): reuses `dynamic_scene_state_authority.
MovementState` verbatim (never a second vocabulary) -- "STATIONARY" stands
in for a generic pre-start/idle state, "LOADING"/"UNLOADING" stand in for
station-handling states, matching the existing convention already
established by `generate_openusd_hospital_dynamic_foundation_demo.py`'s
carrier-status-to-movement-state mapping (`_map_movement_state` below
reuses that EXACT same mapping pattern).

NOT_APPLICABLE / NOT_CALIBRATED (section 4/10): `TrajectorySample.
time_minutes` and `MovingEntityTrajectory.start_time_minutes/
end_time_minutes/duration_minutes` are `float | Literal["NOT_APPLICABLE",
"NOT_CALIBRATED"]` -- a spatial-only PTS path (geometry ready, no
authoritative timing) reports `"NOT_APPLICABLE"` in samples and
`"NOT_CALIBRATED"` at the trajectory level; a route that itself could not
be resolved reports `route_status="ROUTE_NOT_CALIBRATED"` and empty
samples. Nothing is ever silently defaulted to zero or fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import canonical_spatial_authority as csa
import conventional_transport_authority as cta
import dynamic_scene_state_authority as dss
import human_circulation_authority as hca
import mrt_service_class_authority as msc
import pts_spatial_network_authority as ptsna
import rght_spatial_network_authority as rghtna

PRODUCTION_TRAJECTORY_TIME_UNIT = dss.MRT_SIMULATION_TIME_UNIT
"""Section 3: reused verbatim -- "MINUTES". Never a second simulation clock."""

PRODUCTION_TRAJECTORY_REQUIRES_OPENUSD = False
PRODUCTION_TRAJECTORY_REQUIRES_BENTLEY = False
PRODUCTION_TRAJECTORY_REQUIRES_NVIDIA = False

NOT_APPLICABLE: Literal["NOT_APPLICABLE"] = "NOT_APPLICABLE"
NOT_CALIBRATED: Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"

EntityType = Literal["MRT_CARRIER", "RGHT_VEHICLE", "PTS_CAPSULE", "MANUAL_PORTER", "PATIENT"]
RouteStatus = Literal["CALIBRATED", "ROUTE_NOT_CALIBRATED"]
PtsTrajectoryKind = Literal["PTS_SPATIAL_TRAJECTORY_PATH", "PTS_TIME_POSITION_TRAJECTORY"]
MotionState = dss.MovementState

MRT_TRAJECTORY_SUPPORTED = True
RGHT_TRAJECTORY_SUPPORTED = True
PTS_TRAJECTORY_SUPPORTED = "GEOMETRY_READY_TIMING_SUBJECT_TO_EXISTING_CALIBRATION"
PORTER_TRAJECTORY_SUPPORTED = True
PATIENT_TRAJECTORY_SUPPORTED = True
FLOOR_AGV_AMR_IMPLEMENTED = False


# ---------------------------------------------------------------------------
# Section 4/17: the ONE unified moving-entity trajectory contract.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrajectorySample:
    """One discrete, exact sample along a trajectory -- never an
    invented/interpolated interior point (interpolation happens only at
    query time, in `resolve_entity_state_at_time`)."""

    time_minutes: float | Literal["NOT_APPLICABLE"]
    x_m: float
    y_m: float
    z_m: float
    motion_state: MotionState
    route_edge_id: str | None
    progress_fraction: float | None


@dataclass(frozen=True)
class MovingEntityTrajectory:
    """Section 4: the ONE vendor-neutral trajectory contract for every
    entity type in scope (section 6). Fields irrelevant to a given entity
    type are explicitly `None`/`"NOT_APPLICABLE"`, never omitted or
    fabricated (section 4: "do not require all entity types to populate
    irrelevant fields")."""

    trajectory_id: str
    entity_id: str
    entity_type: EntityType
    transport_mode: str
    mission_id: str | None
    source_event_id: str | None
    patient_id: str | None
    payload_service_class: str | None

    origin_object_id: str
    destination_object_id: str

    route_status: RouteStatus
    route_node_ids: tuple[str, ...]
    route_edge_ids: tuple[str, ...]
    route_distance_m: float | Literal["NOT_CALIBRATED"]

    start_time_minutes: float | Literal["NOT_APPLICABLE", "NOT_CALIBRATED"]
    end_time_minutes: float | Literal["NOT_APPLICABLE", "NOT_CALIBRATED"]
    duration_minutes: float | Literal["NOT_APPLICABLE", "NOT_CALIBRATED"]

    trajectory_provenance: str
    timing_provenance: str
    spatial_provenance: str

    samples: tuple[TrajectorySample, ...]
    pts_trajectory_kind: PtsTrajectoryKind | None = None


@dataclass(frozen=True)
class EntityStateAtTime:
    """Section 17: the deterministic result of
    `resolve_entity_state_at_time`."""

    entity_id: str
    time_minutes: float
    position_x_m: float
    position_y_m: float
    position_z_m: float
    motion_state: MotionState
    current_route_edge_id: str | None
    progress_fraction: float | None


# ---------------------------------------------------------------------------
# Section 17/18: the ONE mode-neutral position/time query, with explicit,
# tested boundary semantics.
# ---------------------------------------------------------------------------


def resolve_entity_state_at_time(trajectory: MovingEntityTrajectory, time_minutes: float) -> EntityStateAtTime:
    """Section 17-18: deterministic, mode-neutral. Boundary convention
    (documented, section 18):
      - before start: entity remains at the FIRST sample's position with
        motion_state "STATIONARY" (unless queried exactly at the start
        time, which returns the first sample's own state);
      - exactly at start / during movement / exactly at a route-node
        transition: linear interpolation between the bracketing samples,
        using the LATER sample's motion_state/edge exactly at a boundary;
      - at or after end: entity remains at the LAST sample's position with
        motion_state "COMPLETE"."""
    if not isinstance(trajectory.start_time_minutes, float):
        raise ValueError(
            f"trajectory {trajectory.trajectory_id!r} has no calibrated time basis "
            f"(start_time_minutes={trajectory.start_time_minutes!r}) -- use "
            "resolve_entity_position_at_progress for a spatial-only trajectory"
        )
    samples = trajectory.samples
    if not samples:
        raise ValueError(f"trajectory {trajectory.trajectory_id!r} has no samples")

    first, last = samples[0], samples[-1]
    if time_minutes <= first.time_minutes:
        motion_state: MotionState = first.motion_state if time_minutes == first.time_minutes else "STATIONARY"
        return EntityStateAtTime(
            entity_id=trajectory.entity_id, time_minutes=time_minutes, position_x_m=first.x_m, position_y_m=first.y_m,
            position_z_m=first.z_m, motion_state=motion_state, current_route_edge_id=None, progress_fraction=first.progress_fraction,
        )
    if time_minutes >= last.time_minutes:
        return EntityStateAtTime(
            entity_id=trajectory.entity_id, time_minutes=time_minutes, position_x_m=last.x_m, position_y_m=last.y_m,
            position_z_m=last.z_m, motion_state="COMPLETE", current_route_edge_id=last.route_edge_id, progress_fraction=1.0,
        )
    for a, b in zip(samples, samples[1:]):
        if a.time_minutes <= time_minutes <= b.time_minutes:
            span = b.time_minutes - a.time_minutes
            frac = 0.0 if span <= 0 else (time_minutes - a.time_minutes) / span
            progress = None
            if a.progress_fraction is not None and b.progress_fraction is not None:
                progress = a.progress_fraction + (b.progress_fraction - a.progress_fraction) * frac
            at_boundary = time_minutes == b.time_minutes
            return EntityStateAtTime(
                entity_id=trajectory.entity_id, time_minutes=time_minutes,
                position_x_m=a.x_m + (b.x_m - a.x_m) * frac, position_y_m=a.y_m + (b.y_m - a.y_m) * frac,
                position_z_m=a.z_m + (b.z_m - a.z_m) * frac, motion_state=(b.motion_state if at_boundary else a.motion_state),
                current_route_edge_id=(b.route_edge_id if at_boundary else a.route_edge_id), progress_fraction=progress,
            )
    raise AssertionError("unreachable -- samples must be time-ordered and bracket every interior time_minutes")


def resolve_entity_position_at_progress(trajectory: MovingEntityTrajectory, progress_fraction: float) -> tuple[float, float, float]:
    """Progress-based query for a trajectory with NO authoritative time
    basis (e.g. `PTS_SPATIAL_TRAJECTORY_PATH`) -- never fabricates a time
    value merely to reuse `resolve_entity_state_at_time`."""
    samples = trajectory.samples
    if not samples:
        raise ValueError(f"trajectory {trajectory.trajectory_id!r} has no samples")
    progress_fraction = max(0.0, min(1.0, progress_fraction))
    for a, b in zip(samples, samples[1:]):
        if a.progress_fraction is None or b.progress_fraction is None:
            continue
        if a.progress_fraction <= progress_fraction <= b.progress_fraction:
            span = b.progress_fraction - a.progress_fraction
            frac = 0.0 if span <= 0 else (progress_fraction - a.progress_fraction) / span
            return (a.x_m + (b.x_m - a.x_m) * frac, a.y_m + (b.y_m - a.y_m) * frac, a.z_m + (b.z_m - a.z_m) * frac)
    last = samples[-1]
    return (last.x_m, last.y_m, last.z_m)


# ---------------------------------------------------------------------------
# Internal helpers -- ordered edges/nodes and deterministic piecewise
# constant-speed sampling (sections 14-15). Reused by every entity builder
# below; never a per-entity-type reimplementation.
# ---------------------------------------------------------------------------


def _ordered_edges(graph: csa.ConnectivityGraph, *, origin_object_id: str, path_edge_ids: tuple[str, ...]) -> tuple[csa.SpatialEdge, ...]:
    edges_by_id = {e.edge_id: e for e in graph.edges}
    ordered: list[csa.SpatialEdge] = []
    current = origin_object_id
    for edge_id in path_edge_ids:
        edge = edges_by_id[edge_id]
        ordered.append(edge)
        current = edge.to_object_id if edge.from_object_id == current else edge.from_object_id
    return tuple(ordered)


def _route_node_ids(*, origin_object_id: str, ordered_edges: tuple[csa.SpatialEdge, ...]) -> tuple[str, ...]:
    node_ids = [origin_object_id]
    current = origin_object_id
    for edge in ordered_edges:
        current = edge.to_object_id if edge.from_object_id == current else edge.from_object_id
        node_ids.append(current)
    return tuple(node_ids)


def _map_movement_state(status: str) -> MotionState:
    """Reuses the EXACT mapping pattern already established by
    `generate_openusd_hospital_dynamic_foundation_demo.
    build_carrier_trajectory_bridge` -- never a second vocabulary."""
    return status if status in dss.MovementState.__args__ else "UNKNOWN"  # type: ignore[attr-defined]


def _build_piecewise_samples(
    registry: csa.SpatialObjectRegistry, *, ordered_edges: tuple[csa.SpatialEdge, ...], origin_object_id: str,
    start_time_minutes: float, speed_for_edge, end_motion_state: MotionState,
) -> tuple[TrajectorySample, ...]:
    """Section 14-15: constant-speed-per-edge piecewise samples, preserving
    route order/turns/vertical movement. Caller MUST have already confirmed
    every edge has a real (float) `length_m` (i.e. `route.calibration_status
    == "CALIBRATED"`) -- never invoked on an uncalibrated route."""
    total = sum(e.length_m for e in ordered_edges)  # type: ignore[misc]
    samples: list[TrajectorySample] = []
    current = origin_object_id
    t = start_time_minutes
    cumulative = 0.0
    x0, y0, z0 = csa.resolve_global_position(registry, current)
    samples.append(TrajectorySample(
        time_minutes=t, x_m=x0, y_m=y0, z_m=z0, motion_state=("MOVING" if ordered_edges else end_motion_state),
        route_edge_id=None, progress_fraction=(0.0 if total > 0 else 1.0),
    ))
    for edge in ordered_edges:
        next_node = edge.to_object_id if edge.from_object_id == current else edge.from_object_id
        speed = speed_for_edge(edge)
        duration = (edge.length_m / speed) / 60.0 if speed and speed > 0 else 0.0  # type: ignore[operator]
        t += duration
        cumulative += edge.length_m  # type: ignore[operator]
        x, y, z = csa.resolve_global_position(registry, next_node)
        progress = (cumulative / total) if total > 0 else 1.0
        samples.append(TrajectorySample(
            time_minutes=t, x_m=x, y_m=y, z_m=z, motion_state="MOVING", route_edge_id=edge.edge_id, progress_fraction=progress,
        ))
        current = next_node
    if samples:
        samples[-1] = replace(samples[-1], motion_state=end_motion_state)
    return tuple(samples)


def _build_spatial_only_samples(
    registry: csa.SpatialObjectRegistry, *, ordered_edges: tuple[csa.SpatialEdge, ...], origin_object_id: str,
) -> tuple[TrajectorySample, ...]:
    """Section 10: geometry-only samples with an explicit
    `"NOT_APPLICABLE"` time -- never a fabricated uniform-motion time
    basis (`PTS_FAKE_UNIFORM_MOTION_CREATED = NO`)."""
    total = sum(e.length_m for e in ordered_edges)  # type: ignore[misc]
    samples: list[TrajectorySample] = []
    current = origin_object_id
    cumulative = 0.0
    x0, y0, z0 = csa.resolve_global_position(registry, current)
    samples.append(TrajectorySample(time_minutes=NOT_APPLICABLE, x_m=x0, y_m=y0, z_m=z0, motion_state="UNKNOWN", route_edge_id=None, progress_fraction=(0.0 if total > 0 else 1.0)))
    for edge in ordered_edges:
        next_node = edge.to_object_id if edge.from_object_id == current else edge.from_object_id
        cumulative += edge.length_m  # type: ignore[operator]
        x, y, z = csa.resolve_global_position(registry, next_node)
        progress = (cumulative / total) if total > 0 else 1.0
        samples.append(TrajectorySample(time_minutes=NOT_APPLICABLE, x_m=x, y_m=y, z_m=z, motion_state="UNKNOWN", route_edge_id=edge.edge_id, progress_fraction=progress))
        current = next_node
    return tuple(samples)


# ---------------------------------------------------------------------------
# Section 7: MRT trajectory -- reuses the ACTUAL ordered MRT route (never
# the flat 300m placeholder) and the EXISTING MRT speed/timing authority
# (`mrt_service_class_authority.mission_effective_speed`) and the EXISTING
# scheduler-derived `CarrierTrajectory` for start/end/status.
# ---------------------------------------------------------------------------


def resolve_mrt_route_and_build_mission(
    graph: csa.ConnectivityGraph, *, mission_id: str, carrier_id: str, service_class: str, origin_object_id: str,
    destination_object_id: str, start_minutes: float, speed_override_m_per_s: float | None = None,
    priority_override=None, deadline_minutes: float | None = None,
) -> tuple[csa.RouteResult, "msc.MrtServiceMission"]:
    """Section 7: the ONE place `route_length_m` is derived for an MRT
    mission -- ALWAYS from `resolve_route`, NEVER a hard-coded constant."""
    route = csa.resolve_route(graph, origin_object_id=origin_object_id, destination_object_id=destination_object_id, mode="MRT")
    mission = msc.MrtServiceMission(
        mission_id=mission_id, carrier_id=carrier_id, service_class=service_class, route_length_m=route.distance_m,  # type: ignore[arg-type]
        start_minutes=start_minutes, speed_override_m_per_s=speed_override_m_per_s, priority_override=priority_override,
        deadline_minutes=deadline_minutes,
    )
    return route, mission


def build_mrt_trajectory(
    registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph, *, mission: "msc.MrtServiceMission", mrtway_object_id: str,
    origin_object_id: str, destination_object_id: str, route_id: str | None = None, patient_id: str | None = None,
    source_event_id: str | None = None,
) -> MovingEntityTrajectory:
    route = csa.resolve_route(graph, origin_object_id=origin_object_id, destination_object_id=destination_object_id, mode="MRT")
    scheduled_all, unresolved = msc.schedule_service_missions([mission])
    if unresolved or not scheduled_all:
        raise ValueError(f"MRT mission {mission.mission_id!r} could not be scheduled -- trajectory requires a resolved mission")
    scheduled = scheduled_all[0]
    carrier_trajectory = msc.build_carrier_trajectory(mission, scheduled, mrtway_object_id=mrtway_object_id, route_id=route_id, ordered_segment_ids=route.path_edge_ids)
    speed = msc.mission_effective_speed(mission)

    if route.calibration_status == "CALIBRATED" and isinstance(speed, float) and speed > 0:
        ordered_edges = _ordered_edges(graph, origin_object_id=origin_object_id, path_edge_ids=route.path_edge_ids)
        node_ids = _route_node_ids(origin_object_id=origin_object_id, ordered_edges=ordered_edges)
        samples = _build_piecewise_samples(
            registry, ordered_edges=ordered_edges, origin_object_id=origin_object_id, start_time_minutes=carrier_trajectory.start_time_minutes,
            speed_for_edge=lambda _e: speed, end_motion_state=_map_movement_state(carrier_trajectory.status),
        )
    else:
        node_ids, samples = (), ()

    return MovingEntityTrajectory(
        trajectory_id=f"TRAJ-MRT-{mission.mission_id}", entity_id=mrtway_object_id, entity_type="MRT_CARRIER", transport_mode="MRT",
        mission_id=mission.mission_id, source_event_id=source_event_id, patient_id=patient_id, payload_service_class=mission.service_class,
        origin_object_id=origin_object_id, destination_object_id=destination_object_id, route_status=route.calibration_status,
        route_node_ids=node_ids, route_edge_ids=route.path_edge_ids, route_distance_m=route.distance_m,
        start_time_minutes=carrier_trajectory.start_time_minutes, end_time_minutes=carrier_trajectory.end_time_minutes,
        duration_minutes=carrier_trajectory.end_time_minutes - carrier_trajectory.start_time_minutes,
        trajectory_provenance="canonical_spatial_authority.resolve_route(mode='MRT') + mrt_service_class_authority.build_carrier_trajectory",
        timing_provenance="mrt_service_class_authority.mission_effective_speed (existing MRT speed authority) + schedule_service_missions",
        spatial_provenance="canonical_spatial_authority.resolve_global_position along the resolved MRT route edges",
        samples=samples,
    )


# ---------------------------------------------------------------------------
# Section 8: RGHT trajectory -- its OWN network/mode/speed, never shared
# with MRT (RGHT_AND_MRT_SHARE_SPEED = NO, ..._SHARE_INSTALLED_NETWORK = NO,
# ..._SHARE_MOVING_ENTITY = NO).
# ---------------------------------------------------------------------------


def build_rght_trajectory(
    registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph, *, vehicle_id: str, mission_id: str,
    origin_object_id: str, destination_object_id: str, start_time_minutes: float,
    speed_m_per_s: float = cta.DEFAULT_AGV_MODEL.speed_m_per_s, source_event_id: str | None = None,
    patient_id: str | None = None, payload_service_class: str | None = None,
) -> MovingEntityTrajectory:
    route = csa.resolve_route(graph, origin_object_id=origin_object_id, destination_object_id=destination_object_id, mode=rghtna.RGHT_TRANSPORT_MODE)
    if route.calibration_status == "CALIBRATED" and speed_m_per_s > 0:
        ordered_edges = _ordered_edges(graph, origin_object_id=origin_object_id, path_edge_ids=route.path_edge_ids)
        node_ids = _route_node_ids(origin_object_id=origin_object_id, ordered_edges=ordered_edges)
        samples = _build_piecewise_samples(
            registry, ordered_edges=ordered_edges, origin_object_id=origin_object_id, start_time_minutes=start_time_minutes,
            speed_for_edge=lambda _e: speed_m_per_s, end_motion_state="COMPLETE",
        )
        end_time: float | Literal["NOT_CALIBRATED"] = samples[-1].time_minutes  # type: ignore[assignment]
    else:
        node_ids, samples = (), ()
        end_time = NOT_CALIBRATED

    duration: float | Literal["NOT_CALIBRATED"] = (end_time - start_time_minutes) if isinstance(end_time, float) else NOT_CALIBRATED
    return MovingEntityTrajectory(
        trajectory_id=f"TRAJ-RGHT-{mission_id}", entity_id=vehicle_id, entity_type="RGHT_VEHICLE", transport_mode=rghtna.RGHT_TRANSPORT_MODE,
        mission_id=mission_id, source_event_id=source_event_id, patient_id=patient_id, payload_service_class=payload_service_class,
        origin_object_id=origin_object_id, destination_object_id=destination_object_id, route_status=route.calibration_status,
        route_node_ids=node_ids, route_edge_ids=route.path_edge_ids, route_distance_m=route.distance_m,
        start_time_minutes=start_time_minutes, end_time_minutes=end_time, duration_minutes=duration,
        trajectory_provenance="canonical_spatial_authority.resolve_route(mode=RGHT's own AGV_AMR identifier) -- RGHT's own network, never shared with MRT",
        timing_provenance="conventional_transport_authority.DEFAULT_AGV_MODEL.speed_m_per_s (existing RGHT speed authority) unless caller overrides",
        spatial_provenance="canonical_spatial_authority.resolve_global_position along the resolved RGHT route edges",
        samples=samples,
    )


# ---------------------------------------------------------------------------
# Section 10: PTS trajectory -- distinguishes PTS_SPATIAL_TRAJECTORY_PATH
# (always geometry-ready when the route is calibrated) from
# PTS_TIME_POSITION_TRAJECTORY (produced ONLY when the caller explicitly
# asserts a calibrated timing authority for THIS mission, e.g. dedicated
# RP-PTS -- never assumed for ordinary PTS's
# dispatch_minutes+station_handling_minutes doctrine).
# ---------------------------------------------------------------------------


def build_pts_trajectory(
    registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph, *, capsule_id: str, mission_id: str,
    origin_object_id: str, destination_object_id: str, network: cta.PneumaticTubeNetwork = cta.DEFAULT_PTS_NETWORK,
    calibrated_start_time_minutes: float | None = None, source_event_id: str | None = None,
    patient_id: str | None = None, payload_service_class: str | None = None,
) -> MovingEntityTrajectory:
    route = csa.resolve_route(graph, origin_object_id=origin_object_id, destination_object_id=destination_object_id, mode=ptsna.PTS_TRANSPORT_MODE)
    if route.calibration_status == "CALIBRATED":
        ordered_edges = _ordered_edges(graph, origin_object_id=origin_object_id, path_edge_ids=route.path_edge_ids)
        node_ids = _route_node_ids(origin_object_id=origin_object_id, ordered_edges=ordered_edges)
    else:
        ordered_edges, node_ids = (), ()

    if route.calibration_status == "CALIBRATED" and calibrated_start_time_minutes is not None and network.speed_m_per_s > 0:
        samples = _build_piecewise_samples(
            registry, ordered_edges=ordered_edges, origin_object_id=origin_object_id, start_time_minutes=calibrated_start_time_minutes,
            speed_for_edge=lambda _e: network.speed_m_per_s, end_motion_state="COMPLETE",
        )
        start_time: float | Literal["NOT_CALIBRATED"] = calibrated_start_time_minutes
        end_time: float | Literal["NOT_CALIBRATED"] = samples[-1].time_minutes  # type: ignore[assignment]
        duration: float | Literal["NOT_CALIBRATED"] = end_time - start_time  # type: ignore[operator]
        kind: PtsTrajectoryKind = "PTS_TIME_POSITION_TRAJECTORY"
        timing_provenance = (
            f"caller-asserted calibrated timing authority for network {network.network_id!r} "
            f"(speed_m_per_s={network.speed_m_per_s}) -- never assumed true for ordinary PTS by default"
        )
    elif route.calibration_status == "CALIBRATED":
        samples = _build_spatial_only_samples(registry, ordered_edges=ordered_edges, origin_object_id=origin_object_id)
        start_time = end_time = duration = NOT_CALIBRATED
        kind = "PTS_SPATIAL_TRAJECTORY_PATH"
        timing_provenance = (
            "NOT_CALIBRATED -- ordinary PTS mission timing is "
            "conventional_transport_authority.DEFAULT_PTS_NETWORK.dispatch_minutes+station_handling_minutes "
            "(fixed ~2.5 min, never route-distance-based) unless the caller explicitly asserts a calibrated "
            "timing authority via calibrated_start_time_minutes (e.g. dedicated RP-PTS)"
        )
    else:
        samples = ()
        start_time = end_time = duration = NOT_CALIBRATED
        kind = "PTS_SPATIAL_TRAJECTORY_PATH"
        timing_provenance = "NOT_CALIBRATED -- route itself is not calibrated (no PTS network geometry between these two objects)"

    return MovingEntityTrajectory(
        trajectory_id=f"TRAJ-PTS-{mission_id}", entity_id=capsule_id, entity_type="PTS_CAPSULE", transport_mode=ptsna.PTS_TRANSPORT_MODE,
        mission_id=mission_id, source_event_id=source_event_id, patient_id=patient_id, payload_service_class=payload_service_class,
        origin_object_id=origin_object_id, destination_object_id=destination_object_id, route_status=route.calibration_status,
        route_node_ids=node_ids, route_edge_ids=route.path_edge_ids, route_distance_m=route.distance_m,
        start_time_minutes=start_time, end_time_minutes=end_time, duration_minutes=duration,
        trajectory_provenance="canonical_spatial_authority.resolve_route(mode=PNEUMATIC_TUBE) -- geometry available whenever the PTS network is calibrated",
        timing_provenance=timing_provenance,
        spatial_provenance="canonical_spatial_authority.resolve_global_position along the resolved PTS route edges",
        samples=samples, pts_trajectory_kind=kind,
    )


# ---------------------------------------------------------------------------
# Sections 11-13: manual porter + patient trajectories -- SAME pedestrian
# network/route solver/speed doctrine (`human_circulation_authority`), but
# semantically DISTINCT entity types (PATIENT_TRAJECTORY_ENTITY_TYPE_EQUALS_
# PORTER = NO) and never straight-line-through-walls.
# ---------------------------------------------------------------------------


def _build_human_trajectory(
    registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph, *, subject: "hca.HumanSubject", entity_type: EntityType,
    entity_id: str, mission_id: str, origin_object_id: str, destination_object_id: str, start_time_minutes: float,
    dispatch_minutes: float, source_event_id: str | None, patient_id: str | None, payload_service_class: str | None,
) -> MovingEntityTrajectory:
    pedestrian_route = hca.resolve_pedestrian_route(registry, graph, subject=subject, origin_object_id=origin_object_id, destination_object_id=destination_object_id)
    csa_mode = "PATIENT_MOVEMENT" if subject == "PATIENT" else "WALKING_PORTER"

    if pedestrian_route.route_status == "ROUTE_CALIBRATED":
        route_result = csa.resolve_route(graph, origin_object_id=origin_object_id, destination_object_id=destination_object_id, mode=csa_mode)
        ordered_edges = _ordered_edges(graph, origin_object_id=origin_object_id, path_edge_ids=route_result.path_edge_ids)
        movement_start = start_time_minutes + dispatch_minutes
        samples = _build_piecewise_samples(
            registry, ordered_edges=ordered_edges, origin_object_id=origin_object_id, start_time_minutes=movement_start,
            speed_for_edge=lambda e: (hca.HUMAN_ELEVATOR_SPEED_M_PER_S if e.vertical else hca.HUMAN_WALKING_SPEED_M_PER_S),
            end_motion_state="COMPLETE",
        )
        if dispatch_minutes > 0 and samples:
            samples = (replace(samples[0], time_minutes=start_time_minutes, motion_state="WAITING"),) + samples
        end_time: float | Literal["NOT_CALIBRATED"] = samples[-1].time_minutes  # type: ignore[assignment]
        route_status: RouteStatus = "CALIBRATED"
        node_ids = pedestrian_route.route_node_ids
        route_edge_ids = route_result.path_edge_ids
        route_distance: float | Literal["NOT_CALIBRATED"] = pedestrian_route.total_distance_m if pedestrian_route.total_distance_m is not None else NOT_CALIBRATED
    else:
        samples, node_ids, route_edge_ids = (), (), ()
        end_time = NOT_CALIBRATED
        route_status = "ROUTE_NOT_CALIBRATED"
        route_distance = NOT_CALIBRATED

    duration: float | Literal["NOT_CALIBRATED"] = (end_time - start_time_minutes) if isinstance(end_time, float) else NOT_CALIBRATED
    kind_label = "PATIENT" if subject == "PATIENT" else "PORTER"
    return MovingEntityTrajectory(
        trajectory_id=f"TRAJ-{kind_label}-{mission_id}", entity_id=entity_id, entity_type=entity_type, transport_mode=csa_mode,
        mission_id=mission_id, source_event_id=source_event_id, patient_id=patient_id, payload_service_class=payload_service_class,
        origin_object_id=origin_object_id, destination_object_id=destination_object_id, route_status=route_status,
        route_node_ids=node_ids, route_edge_ids=route_edge_ids, route_distance_m=route_distance,
        start_time_minutes=start_time_minutes, end_time_minutes=end_time, duration_minutes=duration,
        trajectory_provenance=(
            "human_circulation_authority.resolve_pedestrian_route (shared PATIENT_MOVEMENT/WALKING_PORTER "
            "pedestrian network via corridors/elevators) -- never straight-line-through-walls"
        ),
        timing_provenance="human_circulation_authority.HUMAN_WALKING_SPEED_M_PER_S/HUMAN_ELEVATOR_SPEED_M_PER_S (existing shared human speed authority)",
        spatial_provenance="canonical_spatial_authority.resolve_global_position along the resolved pedestrian route edges",
        samples=samples,
    )


def build_porter_trajectory(
    registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph, *, porter_id: str, mission_id: str,
    origin_object_id: str, destination_object_id: str, start_time_minutes: float, dispatch_minutes: float = 0.0,
    source_event_id: str | None = None, patient_id: str | None = None, payload_service_class: str | None = None,
) -> MovingEntityTrajectory:
    return _build_human_trajectory(
        registry, graph, subject="PORTER", entity_type="MANUAL_PORTER", entity_id=porter_id, mission_id=mission_id,
        origin_object_id=origin_object_id, destination_object_id=destination_object_id, start_time_minutes=start_time_minutes,
        dispatch_minutes=dispatch_minutes, source_event_id=source_event_id, patient_id=patient_id, payload_service_class=payload_service_class,
    )


def build_patient_trajectory(
    registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph, *, patient_entity_id: str, mission_id: str,
    patient_id: str, origin_object_id: str, destination_object_id: str, start_time_minutes: float,
    source_event_id: str | None = None,
) -> MovingEntityTrajectory:
    """Section 12-13: `entity_type="PATIENT"` -- NEVER `"MANUAL_PORTER"`
    (PATIENT_TRAVEL_COUNTED_AS_PORTER_LABOR = NO). Never invents a
    PATIENT_ROOM -> injection-room leg (PATIENT_ROOM_TO_INJECTION_ROOM_
    TRAJECTORY_CREATED = NO)."""
    return _build_human_trajectory(
        registry, graph, subject="PATIENT", entity_type="PATIENT", entity_id=patient_entity_id, mission_id=mission_id,
        origin_object_id=origin_object_id, destination_object_id=destination_object_id, start_time_minutes=start_time_minutes,
        dispatch_minutes=0.0, source_event_id=source_event_id, patient_id=patient_id, payload_service_class=None,
    )


# ---------------------------------------------------------------------------
# Sections 19-20: distance/time conservation validators.
# ---------------------------------------------------------------------------


def validate_distance_conservation(trajectory: MovingEntityTrajectory, graph: csa.ConnectivityGraph, *, tolerance_m: float = 1e-6) -> bool:
    """Section 19: sum of traversed edge distances (independently
    recomputed from the graph) must equal the authoritative route distance
    within tolerance."""
    if not isinstance(trajectory.route_distance_m, float):
        return trajectory.route_distance_m == NOT_CALIBRATED
    edges_by_id = {e.edge_id: e for e in graph.edges}
    traversed = sum(edges_by_id[eid].length_m for eid in trajectory.route_edge_ids)  # type: ignore[misc]
    return abs(traversed - trajectory.route_distance_m) <= tolerance_m


def validate_time_conservation(trajectory: MovingEntityTrajectory, *, tolerance_minutes: float = 1e-6) -> bool:
    """Section 20: `end_time - start_time` must reconcile with the actual
    sampled span (which includes any dwell/dispatch samples this module
    prepended) -- never silently dropped."""
    if not isinstance(trajectory.start_time_minutes, float) or not isinstance(trajectory.end_time_minutes, float):
        return trajectory.duration_minutes in (NOT_CALIBRATED, NOT_APPLICABLE)
    if not trajectory.samples:
        return False
    span = trajectory.samples[-1].time_minutes - trajectory.samples[0].time_minutes  # type: ignore[operator]
    return abs(span - trajectory.duration_minutes) <= tolerance_minutes  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Section 26: one-way bridge into the EXISTING presentation-only
# `DynamicObjectTrajectory` contract -- proves the mapping; never authors
# production USD time samples itself.
# ---------------------------------------------------------------------------


def to_dynamic_object_trajectory(trajectory: MovingEntityTrajectory) -> dss.DynamicObjectTrajectory:
    if not isinstance(trajectory.start_time_minutes, float):
        raise ValueError(f"trajectory {trajectory.trajectory_id!r} has no calibrated time basis -- cannot map to DynamicObjectTrajectory")
    if not trajectory.samples:
        raise ValueError(f"trajectory {trajectory.trajectory_id!r} has no samples")
    return dss.build_linear_trajectory(
        canonical_object_id=trajectory.entity_id, waypoints_m=[(s.x_m, s.y_m, s.z_m) for s in trajectory.samples],
        times_minutes=[s.time_minutes for s in trajectory.samples],  # type: ignore[misc]
        movement_states=[s.motion_state for s in trajectory.samples], provenance=trajectory.trajectory_provenance,
    )


# ---------------------------------------------------------------------------
# Section 30: controlled MRT proof network -- an L-shaped route
# (trunk -> junction -> branch) on top of an already-existing facility.
# Distances are ALWAYS computed via `compute_global_distance` -- never a
# flat placeholder.
# ---------------------------------------------------------------------------


def build_controlled_mrt_proof_network(
    registry: csa.SpatialObjectRegistry, *, facility_id: str,
) -> tuple[csa.ConnectivityGraph, tuple[csa.CanonicalSpatialObject, ...]]:
    created: list[csa.CanonicalSpatialObject] = []
    trunk = csa.build_mrt_trunk(registry, trunk_id="MRT-TRUNK-1", facility_id=facility_id, length_m=20.0, transform=csa.Transform(position_x=0.0, position_y=0.0, position_z=0.0))
    junction = csa.build_mrt_junction(registry, junction_id="MRT-JCT-1", facility_id=facility_id, transform=csa.Transform(position_x=20.0, position_y=0.0, position_z=0.0))
    branch = csa.build_mrt_branch(registry, branch_id="MRT-BRANCH-1", facility_id=facility_id, connects_to_object_id=junction.mrtway_object_id, length_m=15.0, transform=csa.Transform(position_x=0.0, position_y=15.0, position_z=0.0))
    endpoint_origin = csa.build_mrt_endpoint(registry, endpoint_id="MRT-ENDPOINT-RP", facility_id=facility_id, connected_network_object_id=trunk.mrtway_object_id, transform=csa.Transform(position_x=-5.0, position_y=0.0, position_z=0.0))
    endpoint_destination = csa.build_mrt_endpoint(registry, endpoint_id="MRT-ENDPOINT-SCN", facility_id=facility_id, connected_network_object_id=branch.mrtway_object_id, transform=csa.Transform(position_x=0.0, position_y=10.0, position_z=0.0))
    created.extend((trunk, junction, branch, endpoint_origin, endpoint_destination))

    def _len(a: str, b: str) -> float:
        return csa.compute_global_distance(registry, a, b)

    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="MRT-E1", from_object_id=endpoint_origin.mrtway_object_id, to_object_id=trunk.mrtway_object_id, length_m=_len(endpoint_origin.mrtway_object_id, trunk.mrtway_object_id), compatible_modes=frozenset({"MRT"})))
    graph.add_edge(csa.SpatialEdge(edge_id="MRT-E2", from_object_id=trunk.mrtway_object_id, to_object_id=junction.mrtway_object_id, length_m=_len(trunk.mrtway_object_id, junction.mrtway_object_id), compatible_modes=frozenset({"MRT"})))
    graph.add_edge(csa.SpatialEdge(edge_id="MRT-E3", from_object_id=junction.mrtway_object_id, to_object_id=branch.mrtway_object_id, length_m=_len(junction.mrtway_object_id, branch.mrtway_object_id), compatible_modes=frozenset({"MRT"})))
    graph.add_edge(csa.SpatialEdge(edge_id="MRT-E4", from_object_id=branch.mrtway_object_id, to_object_id=endpoint_destination.mrtway_object_id, length_m=_len(branch.mrtway_object_id, endpoint_destination.mrtway_object_id), compatible_modes=frozenset({"MRT"})))
    return graph, tuple(created)

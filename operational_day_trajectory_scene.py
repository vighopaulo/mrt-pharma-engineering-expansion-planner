"""Production Trajectory Build 2: Operational-Day Trajectory Composition.

GOVERNANCE: this module owns ONLY the composition of already-built
`production_trajectory_authority.MovingEntityTrajectory` objects into ONE
synchronized, time-indexed operational-day scene, plus deterministic
read-only queries/sampling over that scene. It:

  - does NOT build trajectories itself (every trajectory is produced by
    Build 1's existing entity builders -- `build_mrt_trajectory`,
    `build_rght_trajectory`, `build_pts_trajectory`, `build_porter_
    trajectory`, `build_patient_trajectory`);
  - does NOT select transport technology (`ENGINE_SELECTS_TRANSPORT_
    SOLUTION`/`TRAJECTORY_COMPOSER_SELECTS_TRANSPORT_SOLUTION = NO` --
    whatever mode/mission the engine already decided is represented as-is);
  - does NOT invent a second interpolation engine -- `resolve_scene_state_
    at_time` delegates every per-trajectory position/time resolution to
    Build 1's own `production_trajectory_authority.resolve_entity_state_
    at_time`;
  - does NOT call Bentley, OpenUSD (`pxr`), or NVIDIA/Omniverse (`omni`) --
    verified by tests scanning this module's own import lines.

AUDIT (before writing this module): the repository already had
`mrt_service_class_authority.CarrierTrajectory` (per-mission MRT timing,
no waypoints), `dynamic_scene_state_authority.DynamicObjectTrajectory`
(presentation-only, caller-supplied samples), and `operational_day_
orchestrator.ConventionalMovementTrace` (explicitly NOT a trajectory, its
own docstring says so) -- none of these compose MULTIPLE entities into one
synchronized, queryable scene; that capability was genuinely missing and
is added here, reusing Build 1's `MovingEntityTrajectory`/
`resolve_entity_state_at_time` exclusively (never a duplicate geometry/
time-position engine, never a second `MovementState` vocabulary).

TIME AUTHORITY (section 3): reuses `production_trajectory_authority.
PRODUCTION_TRAJECTORY_TIME_UNIT` ("MINUTES") verbatim -- no second
simulation clock is introduced anywhere in this module.

STABLE ENTITY IDENTITY (section 5/12): a scene may contain MULTIPLE
`MovingEntityTrajectory` objects that share the SAME `entity_id` (one
physical entity performing several missions across the day, separated by
dwell/idle gaps) -- this module NEVER creates a new entity identity per
mission, per timestep, or per sample.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

import production_trajectory_authority as pta

SCENE_TIME_UNIT = pta.PRODUCTION_TRAJECTORY_TIME_UNIT
"""Section 3: reused verbatim ("MINUTES"). Never a second simulation clock."""

ENGINE_SELECTS_TRANSPORT_SOLUTION = True
TRAJECTORY_COMPOSER_SELECTS_TRANSPORT_SOLUTION = False
OPENUSD_SELECTS_TRANSPORT_SOLUTION = False
NVIDIA_SELECTS_TRANSPORT_SOLUTION = False

FRAME_SAMPLING_IS_DERIVED = True
FRAME_DATABASE_BECOMES_ENGINEERING_AUTHORITY = False

OPENUSD_PRODUCTION_TRAJECTORY_BINDING_STARTED = False
OPENUSD_HANDOFF_READY = True
BENTLEY_CALLED_BY_TRAJECTORY_BUILD = False
NVIDIA_STARTED = False


class OverlappingActiveTrajectoryError(ValueError):
    """Section 26: raised when two trajectories for the SAME physical
    entity have overlapping calibrated [start, end] windows -- never
    silently repaired."""


class InvertedMissionTimeError(ValueError):
    """Section 26: raised when a trajectory's calibrated end_time_minutes
    precedes its start_time_minutes."""


class UnknownSceneEntityError(ValueError):
    """Section 26: raised when a caller queries an entity_id that is not
    present in the scene."""


# ---------------------------------------------------------------------------
# Section 4: the ONE new composition authority. Never duplicates trajectory
# geometry -- `trajectories` holds the ACTUAL Build 1 objects, verbatim.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationalDayTrajectoryScene:
    scene_id: str
    start_time_minutes: float | Literal["NOT_CALIBRATED"]
    end_time_minutes: float | Literal["NOT_CALIBRATED"]
    trajectories: tuple[pta.MovingEntityTrajectory, ...]
    entity_ids: tuple[str, ...]
    mission_ids: tuple[str, ...]
    metadata: Mapping[str, object]


def _validate_no_overlapping_active_trajectories(trajectories: Sequence[pta.MovingEntityTrajectory]) -> None:
    by_entity: dict[str, list[pta.MovingEntityTrajectory]] = {}
    for trajectory in trajectories:
        by_entity.setdefault(trajectory.entity_id, []).append(trajectory)
    for entity_id, group in by_entity.items():
        calibrated = [t for t in group if isinstance(t.start_time_minutes, float) and isinstance(t.end_time_minutes, float)]
        for t in calibrated:
            if t.end_time_minutes < t.start_time_minutes:  # type: ignore[operator]
                raise InvertedMissionTimeError(f"trajectory {t.trajectory_id!r} (entity {entity_id!r}) has end_time_minutes < start_time_minutes")
        calibrated.sort(key=lambda t: t.start_time_minutes)  # type: ignore[arg-type,return-value]
        for a, b in zip(calibrated, calibrated[1:]):
            if b.start_time_minutes < a.end_time_minutes:  # type: ignore[operator]
                raise OverlappingActiveTrajectoryError(
                    f"entity {entity_id!r} has overlapping active trajectories {a.trajectory_id!r} "
                    f"[{a.start_time_minutes}, {a.end_time_minutes}] and {b.trajectory_id!r} [{b.start_time_minutes}, {b.end_time_minutes}]"
                )


def build_operational_day_trajectory_scene(
    trajectories: Sequence[pta.MovingEntityTrajectory], *, scene_id: str, metadata: Mapping[str, object] | None = None,
) -> OperationalDayTrajectoryScene:
    """Sections 4/18/26: validates (no overlapping active trajectories per
    entity, no inverted mission time), then composes ONE deterministic
    scene -- `trajectories` is stored/ordered but never copied/mutated
    into a second geometry representation."""
    _validate_no_overlapping_active_trajectories(trajectories)
    calibrated_starts = [t.start_time_minutes for t in trajectories if isinstance(t.start_time_minutes, float)]
    calibrated_ends = [t.end_time_minutes for t in trajectories if isinstance(t.end_time_minutes, float)]
    start_time_minutes: float | Literal["NOT_CALIBRATED"] = min(calibrated_starts) if calibrated_starts else pta.NOT_CALIBRATED
    end_time_minutes: float | Literal["NOT_CALIBRATED"] = max(calibrated_ends) if calibrated_ends else pta.NOT_CALIBRATED
    entity_ids = tuple(sorted({t.entity_id for t in trajectories}))
    mission_ids = tuple(sorted({t.mission_id for t in trajectories if t.mission_id is not None}))
    ordered_trajectories = tuple(sorted(
        trajectories,
        key=lambda t: (t.entity_id, t.start_time_minutes if isinstance(t.start_time_minutes, float) else float("inf"), t.trajectory_id),
    ))
    return OperationalDayTrajectoryScene(
        scene_id=scene_id, start_time_minutes=start_time_minutes, end_time_minutes=end_time_minutes,
        trajectories=ordered_trajectories, entity_ids=entity_ids, mission_ids=mission_ids, metadata=dict(metadata or {}),
    )


def trajectories_for_entity(scene: OperationalDayTrajectoryScene, entity_id: str) -> tuple[pta.MovingEntityTrajectory, ...]:
    """Section 21 (OpenUSD handoff prep): ordered missions for ONE stable
    entity -- a future OpenUSD adapter merges these into one prim's time
    samples; this module never performs that merge itself (section 21:
    `OPENUSD_PRODUCTION_TRAJECTORY_BINDING_STARTED = NO`)."""
    if entity_id not in scene.entity_ids:
        raise UnknownSceneEntityError(f"entity_id {entity_id!r} is not present in scene {scene.scene_id!r}")
    return tuple(t for t in scene.trajectories if t.entity_id == entity_id)


# ---------------------------------------------------------------------------
# Section 14-15: unified scene/entity query -- delegates ALL position/time
# resolution to Build 1's `resolve_entity_state_at_time` (never a second
# interpolation engine).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SceneEntityState:
    entity_id: str
    entity_type: str
    mission_id: str | None
    transport_mode: str
    position_x_m: float
    position_y_m: float
    position_z_m: float
    motion_state: str
    route_edge_id: str | None
    progress_fraction: float | None
    service_class: str | None
    patient_id: str | None


def _select_active_trajectory(calibrated: Sequence[pta.MovingEntityTrajectory], time_minutes: float) -> pta.MovingEntityTrajectory:
    """Section 12-13: within a mission window -> that mission; before the
    first / after the last -> the boundary mission (Build 1's own
    STATIONARY/COMPLETE semantics apply); strictly between two missions
    (a dwell/idle gap) -> the PREVIOUS mission, so the entity remains at
    its last known location (`INTERMISSION_TELEPORTATION = NO`)."""
    for t in calibrated:
        if t.start_time_minutes <= time_minutes <= t.end_time_minutes:  # type: ignore[operator]
            return t
    if time_minutes < calibrated[0].start_time_minutes:  # type: ignore[operator]
        return calibrated[0]
    if time_minutes > calibrated[-1].end_time_minutes:  # type: ignore[operator]
        return calibrated[-1]
    previous = calibrated[0]
    for t in calibrated:
        if t.end_time_minutes <= time_minutes:  # type: ignore[operator]
            previous = t
        else:
            break
    return previous


def _scene_entity_state_from_trajectory(trajectory: pta.MovingEntityTrajectory, time_minutes: float) -> SceneEntityState:
    base = pta.resolve_entity_state_at_time(trajectory, time_minutes)
    active_mission_id = trajectory.mission_id if (isinstance(trajectory.start_time_minutes, float) and trajectory.start_time_minutes <= time_minutes <= trajectory.end_time_minutes) else None  # type: ignore[operator]
    return SceneEntityState(
        entity_id=trajectory.entity_id, entity_type=trajectory.entity_type, mission_id=active_mission_id,
        transport_mode=trajectory.transport_mode, position_x_m=base.position_x_m, position_y_m=base.position_y_m,
        position_z_m=base.position_z_m, motion_state=base.motion_state, route_edge_id=base.current_route_edge_id,
        progress_fraction=base.progress_fraction, service_class=trajectory.payload_service_class, patient_id=trajectory.patient_id,
    )


def resolve_scene_state_at_time(scene: OperationalDayTrajectoryScene, time_minutes: float) -> tuple[SceneEntityState, ...]:
    """Section 14/17/18: returns the state of every entity that has AT
    LEAST one time-calibrated trajectory, in deterministic `entity_id`
    order -- entities with only spatial-only trajectories (e.g. ordinary
    PTS) are honestly omitted (never a fabricated position)."""
    states = []
    for entity_id in scene.entity_ids:
        calibrated = [t for t in scene.trajectories if t.entity_id == entity_id and isinstance(t.start_time_minutes, float) and isinstance(t.end_time_minutes, float)]
        if not calibrated:
            continue
        calibrated.sort(key=lambda t: t.start_time_minutes)  # type: ignore[arg-type,return-value]
        active = _select_active_trajectory(calibrated, time_minutes)
        states.append(_scene_entity_state_from_trajectory(active, time_minutes))
    return tuple(states)


def resolve_entity_state_in_scene_at_time(scene: OperationalDayTrajectoryScene, *, entity_id: str, time_minutes: float) -> SceneEntityState:
    """Section 15: optional single-entity query -- fails clearly for an
    unknown entity_id (section 26), reuses `resolve_scene_state_at_time`
    internally (never a second resolution path)."""
    if entity_id not in scene.entity_ids:
        raise UnknownSceneEntityError(f"entity_id {entity_id!r} is not present in scene {scene.scene_id!r}")
    for state in resolve_scene_state_at_time(scene, time_minutes):
        if state.entity_id == entity_id:
            return state
    raise UnknownSceneEntityError(f"entity_id {entity_id!r} has no time-calibrated trajectory in scene {scene.scene_id!r}")


# ---------------------------------------------------------------------------
# Section 16: derived sampling helper for visualization/export -- NEVER a
# second authoritative frame database (section 16: `FRAME_SAMPLING_IS_
# DERIVED = YES`, `FRAME_DATABASE_BECOMES_ENGINEERING_AUTHORITY = NO`).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SceneSample:
    time_minutes: float
    entity_states: tuple[SceneEntityState, ...]


def sample_scene(
    scene: OperationalDayTrajectoryScene, *, start_time_minutes: float, end_time_minutes: float, step_minutes: float,
) -> tuple[SceneSample, ...]:
    if step_minutes <= 0:
        raise ValueError("step_minutes must be positive")
    if end_time_minutes < start_time_minutes:
        raise InvertedMissionTimeError("end_time_minutes must be >= start_time_minutes")
    samples = []
    t = start_time_minutes
    epsilon = step_minutes * 1e-9
    while t <= end_time_minutes + epsilon:
        samples.append(SceneSample(time_minutes=t, entity_states=resolve_scene_state_at_time(scene, t)))
        t += step_minutes
    return tuple(samples)

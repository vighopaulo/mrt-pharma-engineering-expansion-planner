"""OpenUSD Phase 2A: Vendor-Neutral Dynamic Scene-State Authority.

GOVERNANCE (section 1/4): MRT Pharma -- NOT OpenUSD, NOT NVIDIA -- owns
simulation time and dynamic scene state. This module is the vendor-neutral
contract between MRT Pharma's own simulation-derived data and any
visualization adapter (OpenUSD today; NVIDIA/Omniverse or any other
consumer later). It imports NOTHING platform-specific: no `pxr`, no
`omni`/NVIDIA/Omniverse, no Bentley/iTwin module. `openusd_spatial_adapter.py`
is the ONLY module in this repository that translates this contract into
real `Usd.TimeCode`-sampled attributes (section 6).

STATIC VS DYNAMIC (section 5): this module NEVER represents canonical
engineering identity/transform/dimensions/provenance -- that remains
exclusively `canonical_spatial_authority.CanonicalSpatialObject`. A
`DynamicObjectTrajectory` only ever describes ADDITIONAL time-varying
presentation state for an ALREADY-EXISTING canonical object
(`canonical_object_id` references it by id only, never redefines it).
Nothing in this module mutates `LockedSpatialState`/`WhatIfSpatialState`.

TIME AUTHORITY (section 2-3): the dominant time convention already used
across this repository's simulation/scheduling code
(`operating_day_scheduler.py`, `long_horizon_operational_planning.py`,
`mrt_service_class_authority.CarrierTrajectory.start_time_minutes/
end_time_minutes`) is float MINUTES -- this module reuses that convention
verbatim (`MRT_SIMULATION_TIME_UNIT = "MINUTES"`) rather than inventing a
second clock. `operational_day_orchestrator.SimulationClock` is a separate,
higher-level wall-clock/datetime concept for the whole operating day; this
module does not duplicate it, it only defines the MINUTES<->USD TimeCode
conversion needed to author time samples.

INTERPOLATION (section 12): this module authors only DISCRETE, exact,
caller-supplied samples -- it never computes an interior/interpolated
position itself. Linear interpolation BETWEEN authored samples, when it
occurs, is performed by the consuming USD runtime's own well-known default
numeric time-sample interpolation, not by this module. `interpolation_method`
on `DynamicObjectTrajectory` is a documentation/labeling field only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

MRT_SIMULATION_TIME_UNIT = "MINUTES"
"""Section 2: reused verbatim from CarrierTrajectory/operating_day_scheduler
-- never a second clock unit invented for this module."""

USD_TIME_CODES_PER_SECOND = 1.0
"""Section 3: 1 USD TimeCode == 1 simulation SECOND -- a deliberate,
documented choice (never frame-rate-derived, never implicit). A consumer
that plays the stage back at exactly 1 timeCode/real-second sees the
simulation at true 1:1 speed."""

MovementState = Literal[
    "STATIONARY", "MOVING", "WAITING", "QUEUED", "HELD_FOR_PRIORITY", "AT_JUNCTION",
    "LOADING", "UNLOADING", "COMPLETE", "UNKNOWN",
]
"""Deliberately aligned with (but NOT imported from)
`mrt_service_class_authority.CarrierAnimationStatus` -- this module has zero
import dependency on that authority; the vocabulary overlap is documented
convention, not a hard coupling."""

InterpolationMethod = Literal["LINEAR", "HELD"]


def simulation_minutes_to_usd_timecode(simulation_time_minutes: float) -> float:
    """Section 3: the ONLY conversion function -- minutes -> seconds -> USD
    TimeCode units, using the documented `USD_TIME_CODES_PER_SECOND`."""
    return simulation_time_minutes * 60.0 * USD_TIME_CODES_PER_SECOND


def usd_timecode_to_simulation_minutes(usd_timecode: float) -> float:
    """Section 3: the exact inverse of `simulation_minutes_to_usd_timecode`."""
    return usd_timecode / (60.0 * USD_TIME_CODES_PER_SECOND)


def timecode_round_trip_error_minutes(simulation_time_minutes: float) -> float:
    """Section 3: reversibility proof helper -- returns the absolute error
    (in minutes) after converting to USD TimeCode and back."""
    round_tripped = usd_timecode_to_simulation_minutes(simulation_minutes_to_usd_timecode(simulation_time_minutes))
    return abs(round_tripped - simulation_time_minutes)


@dataclass(frozen=True)
class DynamicObjectState:
    """Section 4: one discrete presentation-state sample for an existing
    canonical object at a given simulation time -- never canonical
    engineering truth (section 5)."""

    canonical_object_id: str
    simulation_time_minutes: float
    position_x_m: float
    position_y_m: float
    position_z_m: float
    movement_state: MovementState
    rotation_z_deg: float | None = None
    provenance: str = "SYNTHETIC_CONTROLLED_FOUNDATION_PROOF"


@dataclass(frozen=True)
class DynamicObjectTrajectory:
    """Section 7/9: ONE canonical_object_id, MANY time samples -- never a
    new engineering identity per sample."""

    canonical_object_id: str
    samples: tuple[DynamicObjectState, ...]
    interpolation_method: InterpolationMethod
    provenance: str

    def __post_init__(self) -> None:
        if not self.samples:
            raise ValueError("DynamicObjectTrajectory requires at least one sample")
        if any(s.canonical_object_id != self.canonical_object_id for s in self.samples):
            raise ValueError("all samples must share the trajectory's canonical_object_id")
        times = [s.simulation_time_minutes for s in self.samples]
        if times != sorted(times):
            raise ValueError("samples must be strictly time-ordered (non-decreasing simulation_time_minutes)")

    @property
    def start_time_minutes(self) -> float:
        return self.samples[0].simulation_time_minutes

    @property
    def end_time_minutes(self) -> float:
        return self.samples[-1].simulation_time_minutes


def build_linear_trajectory(
    *, canonical_object_id: str, waypoints_m: Sequence[tuple[float, float, float]], times_minutes: Sequence[float],
    movement_states: Sequence[MovementState] | None = None, provenance: str,
) -> DynamicObjectTrajectory:
    """Section 9/12: builds a `DynamicObjectTrajectory` from EXACT,
    caller-supplied waypoints/times -- never fabricates an interior point.
    `interpolation_method="LINEAR"` documents that a consuming USD runtime's
    default numeric time-sample interpolation will be used between these
    exact samples; this function itself performs no interpolation."""
    if len(waypoints_m) != len(times_minutes):
        raise ValueError("waypoints_m and times_minutes must have the same length")
    states = movement_states or tuple("MOVING" for _ in waypoints_m)
    if len(states) != len(waypoints_m):
        raise ValueError("movement_states must match waypoints_m length")
    samples = tuple(
        DynamicObjectState(
            canonical_object_id=canonical_object_id, simulation_time_minutes=t, position_x_m=x, position_y_m=y,
            position_z_m=z, movement_state=state, provenance=provenance,
        )
        for (x, y, z), t, state in zip(waypoints_m, times_minutes, states)
    )
    return DynamicObjectTrajectory(
        canonical_object_id=canonical_object_id, samples=samples, interpolation_method="LINEAR", provenance=provenance,
    )

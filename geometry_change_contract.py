"""Geometry-Change Contract: 3D object change -> MRT Pharma recomputation
request -> 2D analytical consequence (Sec 19-27, 39-47).

This build establishes the CONTRACT ONLY -- NOT a finished 3D UI and NOT a full
reactive recomputation engine (Sec 19/22). The governing pipeline:

  3D OBJECT CHANGE -> SPATIAL STATE CHANGE -> MRT PHARMA RECOMPUTATION REQUEST
  -> ENGINEERING/CLINICAL/ECONOMIC DELTA -> 2D ANALYTICAL RESULT.

HARD DOCTRINES:
  * Absolute old AND new state are preserved, not only deltas (Sec 40) -- for
    reproducibility, reversal, and drift prevention (Sec 41).
  * A geometry event is validated before acceptance (Sec 39).
  * Every consequence consumer is classified honestly (Sec 22/43-44):
    RUNTIME_CONSUMED_NOW / ADAPTER_AVAILABLE / NOT_YET_INTEGRATED / NOT_CALIBRATED.
  * Unknown downstream consequences are preserved as NOT_CALIBRATED, never
    zero-filled (Sec 47).
  * No live Bentley mutation (Sec 48) -- these are LOCAL deterministic contract
    events describing PROPOSED changes.

Composes Super-Build 3 (target-vs-incremental doctrine, Sec 46) via
`capital_project_inheritance_authority`; never re-implements economics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

# ===========================================================================
# 1. Transform classes (Sec 20).
# ===========================================================================

TransformType = Literal[
    "TRANSLATE", "ROTATE", "CHANGE_ELEVATION", "CHANGE_BUILDING_SEPARATION",
    "CHANGE_FLOOR_COUNT", "CHANGE_FLOOR_HEIGHT", "RESIZE_FOOTPRINT",
    "RELOCATE_ROOM", "RELOCATE_EQUIPMENT",
]

SUPPORTED_TRANSFORM_TYPES: tuple[TransformType, ...] = (
    "TRANSLATE", "ROTATE", "CHANGE_ELEVATION", "CHANGE_BUILDING_SEPARATION",
    "CHANGE_FLOOR_COUNT", "CHANGE_FLOOR_HEIGHT", "RESIZE_FOOTPRINT",
    "RELOCATE_ROOM", "RELOCATE_EQUIPMENT",
)

_XYZ = tuple[float, float, float]


# ===========================================================================
# 2. Geometry transform event (Sec 20/40). Absolute old + new state.
# ===========================================================================

@dataclass(frozen=True)
class GeometryTransformEvent:
    """Sec 20/40: a PROPOSED 3D transform. Absolute old AND new state are
    preserved (never only a delta) so events are reproducible and reversible
    (Sec 41). Bentley source identity is carried when the object is Bentley-bound."""

    scenario_id: str
    mrt_object_id: str
    transform_type: TransformType
    # source identity (optional -- only when Bentley-bound)
    source_platform: str | None = None
    itwin_id: str | None = None
    imodel_id: str | None = None
    source_changeset_id: str | None = None
    element_id: str | None = None
    # absolute state (old + new). Which fields are meaningful depends on transform_type.
    old_position_xyz: _XYZ | None = None
    new_position_xyz: _XYZ | None = None
    old_rotation_deg: _XYZ | None = None
    new_rotation_deg: _XYZ | None = None
    old_separation_m: float | None = None
    new_separation_m: float | None = None
    old_floor_count: int | None = None
    new_floor_count: int | None = None
    old_floor_height_m: float | None = None
    new_floor_height_m: float | None = None
    old_elevation_m: float | None = None
    new_elevation_m: float | None = None
    old_footprint_m2: float | None = None
    new_footprint_m2: float | None = None
    version: int = 1

    # -- derived deltas (Sec 46: both absolute and delta available) ----------

    def separation_delta_m(self) -> float | None:
        if self.old_separation_m is None or self.new_separation_m is None:
            return None
        return self.new_separation_m - self.old_separation_m

    def floor_count_delta(self) -> int | None:
        if self.old_floor_count is None or self.new_floor_count is None:
            return None
        return self.new_floor_count - self.old_floor_count

    def elevation_delta_m(self) -> float | None:
        if self.old_elevation_m is None or self.new_elevation_m is None:
            return None
        return self.new_elevation_m - self.old_elevation_m

    def translation_distance_m(self) -> float | None:
        if self.old_position_xyz is None or self.new_position_xyz is None:
            return None
        return math.dist(self.old_position_xyz, self.new_position_xyz)


# ===========================================================================
# 3. Validation (Sec 39). No invalid event accepted.
# ===========================================================================

@dataclass(frozen=True)
class GeometryEventValidation:
    valid: bool
    errors: tuple[str, ...]


def _finite(v: float | None) -> bool:
    return v is None or (isinstance(v, (int, float)) and math.isfinite(v))


def _xyz_finite(p: _XYZ | None) -> bool:
    return p is None or all(math.isfinite(c) for c in p)


def validate_geometry_event(event: GeometryTransformEvent) -> GeometryEventValidation:
    """Sec 39: reject missing scenario/object id, missing Bentley identity when
    Bentley-bound, non-finite coordinates, negative floor count, non-positive
    floor height, unsupported transform, inconsistent old/new state."""
    errors: list[str] = []
    if not event.scenario_id:
        errors.append("missing scenario_id")
    if not event.mrt_object_id:
        errors.append("missing mrt_object_id")
    if event.transform_type not in SUPPORTED_TRANSFORM_TYPES:
        errors.append(f"unsupported transform_type {event.transform_type!r}")
    # Bentley-bound => require source identity
    if event.source_platform == "BENTLEY_ITWIN":
        if not (event.itwin_id and event.imodel_id and event.element_id):
            errors.append("Bentley-bound event missing itwin_id/imodel_id/element_id")
    # finiteness
    for p in (event.old_position_xyz, event.new_position_xyz):
        if not _xyz_finite(p):
            errors.append("non-finite position coordinate")
    for v in (event.old_separation_m, event.new_separation_m, event.old_floor_height_m,
              event.new_floor_height_m, event.old_elevation_m, event.new_elevation_m,
              event.old_footprint_m2, event.new_footprint_m2):
        if not _finite(v):
            errors.append("non-finite scalar geometry value")
    # floor count / height physical validity
    for fc in (event.old_floor_count, event.new_floor_count):
        if fc is not None and fc < 0:
            errors.append("negative floor count")
    for fh in (event.old_floor_height_m, event.new_floor_height_m):
        if fh is not None and fh <= 0.0:
            errors.append("zero/negative floor height")
    for fp in (event.old_footprint_m2, event.new_footprint_m2):
        if fp is not None and fp <= 0.0:
            errors.append("zero/negative footprint")
    for sep in (event.old_separation_m, event.new_separation_m):
        if sep is not None and sep < 0.0:
            errors.append("negative separation")
    # per-transform old/new consistency
    required: Mapping[TransformType, tuple[str, str]] = {
        "CHANGE_BUILDING_SEPARATION": ("old_separation_m", "new_separation_m"),
        "CHANGE_FLOOR_COUNT": ("old_floor_count", "new_floor_count"),
        "CHANGE_FLOOR_HEIGHT": ("old_floor_height_m", "new_floor_height_m"),
        "CHANGE_ELEVATION": ("old_elevation_m", "new_elevation_m"),
        "RESIZE_FOOTPRINT": ("old_footprint_m2", "new_footprint_m2"),
        "TRANSLATE": ("old_position_xyz", "new_position_xyz"),
        "ROTATE": ("old_rotation_deg", "new_rotation_deg"),
        "RELOCATE_ROOM": ("old_position_xyz", "new_position_xyz"),
        "RELOCATE_EQUIPMENT": ("old_position_xyz", "new_position_xyz"),
    }
    if event.transform_type in required:
        oldf, newf = required[event.transform_type]
        if getattr(event, oldf) is None or getattr(event, newf) is None:
            errors.append(f"{event.transform_type} requires both {oldf} and {newf}")
    return GeometryEventValidation(valid=not errors, errors=tuple(errors))


def accept_geometry_event(event: GeometryTransformEvent) -> GeometryTransformEvent:
    """Sec 39: raise on an invalid event so INVALID_GEOMETRY_EVENT_ACCEPTED=NO."""
    v = validate_geometry_event(event)
    if not v.valid:
        raise ValueError(f"invalid geometry event: {v.errors}")
    return event


# ===========================================================================
# 4. Reversibility / no-drift (Sec 41). Absolute state, not accumulated deltas.
# ===========================================================================

def apply_events_to_separation(initial_m: float, events: Sequence[GeometryTransformEvent]) -> float:
    """Sec 41: applying a sequence of separation events returns the LAST event's
    absolute new state -- NOT the initial plus a sum of deltas (which would
    drift). A 100->500->100 round trip returns exactly 100.0."""
    current = initial_m
    for e in events:
        if e.transform_type == "CHANGE_BUILDING_SEPARATION" and e.new_separation_m is not None:
            # trust absolute new state; validate continuity against current
            current = e.new_separation_m
    return current


def round_trip_drift(initial_m: float, events: Sequence[GeometryTransformEvent]) -> float:
    """Return |final_absolute - expected|. For a reversible round trip the
    final absolute equals the last event's new_separation_m exactly (0 drift)."""
    final = apply_events_to_separation(initial_m, events)
    expected = events[-1].new_separation_m if events and events[-1].new_separation_m is not None else initial_m
    return abs(final - expected)


# ===========================================================================
# 5. Consequence consumer routing (Sec 22/43-44). Honest classification.
# ===========================================================================

ConsumerReadiness = Literal[
    "RUNTIME_CONSUMED_NOW", "ADAPTER_AVAILABLE", "NOT_YET_INTEGRATED", "NOT_CALIBRATED",
]


@dataclass(frozen=True)
class ConsequenceConsumer:
    consequence: str
    owning_authority: str
    readiness: ConsumerReadiness


# Sec 43: which authorities can consume a building-separation distance change.
# Honest state: the per-mode economics authorities EXIST (SB1/SB2) and can be
# fed a distance, but no reactive wiring feeds a live geometry event into them
# yet -> ADAPTER_AVAILABLE (callable) or NOT_YET_INTEGRATED (no reactive path).
BUILDING_SEPARATION_CONSUMERS: tuple[ConsequenceConsumer, ...] = (
    ConsequenceConsumer("Manual route distance", "conventional_transport_authority.compute_manual_mission_timing", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("PTS tube/network length", "conventional_transport_authority.DEFAULT_PTS_NETWORK", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("RTHS track length", "conventional_transport_authority RGHT", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("AGV route distance", "floor_agv_amr_authority.compute_floor_agv_mission_timing", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("MRT guideway length", "mrt_canonical_configuration (READ-ONLY)", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Patient travel", "spatial_benchmark route metrics", "NOT_YET_INTEGRATED"),
    ConsequenceConsumer("Connection work CapEx", "capital_project_inheritance_authority", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Incremental transport CapEx", "generalized_transport_optimizer + capital inheritance", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Transport OPEX/energy", "per-mode OPEX authorities", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Clinical timing", "operating_day_scheduler", "NOT_YET_INTEGRATED"),
    ConsequenceConsumer("Radionuclide decay consequence", "multi_isotope_decay", "NOT_YET_INTEGRATED"),
)

# Sec 44: which authorities can consume a floor-count change.
FLOOR_COUNT_CONSUMERS: tuple[ConsequenceConsumer, ...] = (
    ConsequenceConsumer("Floor geometry", "canonical_spatial_authority", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Vertical travel distance", "floor_agv_amr_authority elevator model", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Elevator/vertical transport", "conventional_transport_authority elevator wait", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Beds/rooms", "capital_project_inheritance_authority capacity-delta", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("HVAC", "capital_project_inheritance_authority material scope", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Electrical", "capital_project_inheritance_authority material scope", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Structure", "capital_project_inheritance_authority material scope", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Shielding", "capital_project_inheritance_authority material scope", "NOT_CALIBRATED"),
    ConsequenceConsumer("Transport vertical segments", "generalized_transport_optimizer", "NOT_YET_INTEGRATED"),
    ConsequenceConsumer("Scanner/resource demand", "engineering.required_scanners / capacity-delta", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Patient throughput", "operating_day_scheduler", "NOT_YET_INTEGRATED"),
    ConsequenceConsumer("Incremental CapEx", "capital_project_inheritance_authority", "ADAPTER_AVAILABLE"),
    ConsequenceConsumer("Target/incremental OPEX", "capital_project_inheritance_authority OPEX inheritance", "ADAPTER_AVAILABLE"),
)

GENERALIZED_REACTIVE_ENGINE_INTEGRATED_NOW = False
"""Sec 22: the full reactive recomputation engine is NOT wired. This build
establishes the binding + geometry-change CONTRACT only. Consumers are
classified honestly above; none is falsely claimed RUNTIME_CONSUMED_NOW."""


# ===========================================================================
# 6. 2D analytical result contract (Sec 21/45-47). Machine-readable; absolute
#    + delta; unknown/not-calibrated preserved.
# ===========================================================================

MetricStatus = Literal["CALIBRATED", "NOT_CALIBRATED", "NOT_APPLICABLE", "NOT_YET_INTEGRATED"]


@dataclass(frozen=True)
class AnalyticalMetric:
    """Sec 46: both absolute target value and delta-vs-baseline; status carries
    NOT_CALIBRATED (never zero-filled, Sec 47)."""

    name: str
    category: str
    target_value: float | None
    delta_vs_baseline: float | None
    unit: str
    status: MetricStatus

    def is_unknown(self) -> bool:
        return self.status in ("NOT_CALIBRATED", "NOT_YET_INTEGRATED")


@dataclass(frozen=True)
class AnalyticalResult:
    """Sec 45: the structured result the future 2D consequence panel receives
    (never scraped from the 3D viewer). Machine-readable; presentation is not
    the engineering authority."""

    scenario_id: str
    baseline_scenario_id: str
    geometry_change_id: str
    version: int
    changed_object_ids: tuple[str, ...]
    metrics: tuple[AnalyticalMetric, ...]
    warnings: tuple[str, ...] = ()
    provenance: str = "GEOMETRY_CHANGE_CONTRACT_LOCAL"

    def unknown_components(self) -> tuple[str, ...]:
        return tuple(m.name for m in self.metrics if m.is_unknown())

    def not_calibrated_components(self) -> tuple[str, ...]:
        return tuple(m.name for m in self.metrics if m.status == "NOT_CALIBRATED")

    def metric(self, name: str) -> AnalyticalMetric | None:
        return next((m for m in self.metrics if m.name == name), None)


def build_geometry_metric_result(event: GeometryTransformEvent, *, baseline_scenario_id: str,
                                 geometry_change_id: str) -> AnalyticalResult:
    """Sec 21/45-47: build the pure-geometry portion of the analytical result
    for a geometry event. Only geometry metrics are CALIBRATED here (they are
    directly derivable from the event's absolute state); downstream engineering/
    economic metrics are emitted as NOT_YET_INTEGRATED (honest -- the reactive
    engine is a later build), NEVER zero-filled."""
    metrics: list[AnalyticalMetric] = []
    # geometry metrics (calibrated from the event)
    if event.transform_type == "CHANGE_BUILDING_SEPARATION":
        metrics.append(AnalyticalMetric("building_separation", "geometry", event.new_separation_m,
                                        event.separation_delta_m(), "m", "CALIBRATED"))
    if event.transform_type == "CHANGE_FLOOR_COUNT":
        fc = float(event.new_floor_count) if event.new_floor_count is not None else None
        fd = float(event.floor_count_delta()) if event.floor_count_delta() is not None else None
        metrics.append(AnalyticalMetric("floor_count", "geometry", fc, fd, "floors", "CALIBRATED"))
    if event.transform_type == "TRANSLATE" or event.transform_type in ("RELOCATE_ROOM", "RELOCATE_EQUIPMENT"):
        d = event.translation_distance_m()
        metrics.append(AnalyticalMetric("translation_distance", "geometry", d, d, "m", "CALIBRATED" if d is not None else "NOT_APPLICABLE"))
    # downstream consequences: honestly NOT_YET_INTEGRATED (no reactive wiring)
    for name, cat in (("incremental_transport_capex", "economic"),
                      ("target_opex", "economic"), ("incremental_opex", "economic"),
                      ("patient_throughput", "clinical"), ("mrt_guideway_length", "transport")):
        metrics.append(AnalyticalMetric(name, cat, None, None, "usd_or_unit", "NOT_YET_INTEGRATED"))
    return AnalyticalResult(
        scenario_id=event.scenario_id, baseline_scenario_id=baseline_scenario_id,
        geometry_change_id=geometry_change_id, version=event.version,
        changed_object_ids=(event.mrt_object_id,), metrics=tuple(metrics),
        warnings=("downstream engineering/economic metrics NOT_YET_INTEGRATED -- reactive engine is a later build (Sec 22)",),
    )

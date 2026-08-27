"""OpenUSD Production Binding Build 1: Operational-Day Trajectory Scene ->
Animated USD (ASCII .usda).

GOVERNANCE: this module owns ONLY the translation of an already-built
`operational_day_trajectory_scene.OperationalDayTrajectoryScene` into a
real, standards-compliant ASCII USD (`.usda`) artifact. It:

  - does NOT select transport technology, compute speed/route/timing, or
    recompute anything the engine already decided (`OPENUSD_SELECTS_
    TRANSPORT_SOLUTION = NO`, `OPENUSD_BECOMES_ENGINEERING_AUTHORITY = NO`,
    `ENGINEERING_RECOMPUTED_INSIDE_OPENUSD_ADAPTER = NO`);
  - does NOT implement a second interpolation engine -- every authored
    position/time sample is copied VERBATIM from Build 1's own
    `MovingEntityTrajectory.samples` (via Build 2's `trajectories_for_
    entity`), never recalculated;
  - does NOT call Bentley, or require an NVIDIA/Omniverse runtime to
    generate the artifact (verified by tests scanning this module's own
    import lines).

RUNTIME AVAILABILITY (section 2 -- corrects an earlier, incomplete check
in this build): a bare `import pxr` fails in this environment, but
`openusd_spatial_adapter.py` vendors a real `usd-core` install into a
workspace-local `.usd_runtime/` directory and inserts it onto `sys.path`
at import time -- so once that adapter module is imported (as it is here),
`pxr`/`Usd`/`UsdGeom`/`Gf`/`Sdf` ARE genuinely importable
(`OPENUSD_PYTHON_RUNTIME_AVAILABLE = True`, confirmed via `openusd_spatial_
adapter.OPENUSD_RUNTIME_AVAILABLE`). Per section 1's audit mandate, this
module therefore REUSES that adapter's real `pxr`-backed authoring
functions directly (`configure_stage_time_basis`, `author_dynamic_object_
trajectory`, `save_stage_to_usda`, `load_stage_from_usda`, `read_dynamic_
object_state_at_time`, `sanitize_prim_path_segment`, `METERS_PER_UNIT`,
`UP_AXIS`) rather than duplicating them -- this is NOT a second adapter,
it is a narrow, additive composition on top of the existing one, scoped to
one `OperationalDayTrajectoryScene` rather than a full facility
`SpatialObjectRegistry` (a different input shape, which is why a new
top-level stage-building function was still required). A dependency-free
ASCII-text fallback path (`build_yc_demo_usda_text_fallback`) is ALSO
provided and used automatically if `pxr` ever becomes unavailable in a
future environment -- per the build's own governor, this is never allowed
to become a multi-day installation blocker.

Every authored position/time sample is copied VERBATIM from Build 1's own
`MovingEntityTrajectory.samples` (via Build 2's `trajectories_for_entity`),
never recalculated -- this module never reimplements route interpolation.
`dynamic_scene_state_authority.simulation_minutes_to_usd_timecode`/
`USD_TIME_CODES_PER_SECOND` (the EXISTING, already-tested minutes<->USD
TimeCode mapping, 1 TimeCode = 1 real second) is reused verbatim -- never a
second time-mapping formula. This module does NOT select transport
technology, does NOT call Bentley, and does NOT require or invoke any
NVIDIA/Omniverse runtime (verified by tests scanning this module's own
import lines).
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from typing import Mapping, Sequence

import dynamic_scene_state_authority as dss
import openusd_spatial_adapter as usda
import operational_day_trajectory_scene as odts
import production_trajectory_authority as pta

OPENUSD_PYTHON_RUNTIME_AVAILABLE = usda.OPENUSD_RUNTIME_AVAILABLE
OPENUSD_RUNTIME_INSTALLATION_BECOMES_BLOCKER = False

USD_STAGE_ROOT_NAME = "MRTPharma"
USD_STAGE_ROOT_PATH = f"/{USD_STAGE_ROOT_NAME}"
USD_STAGE_METERS_PER_UNIT = usda.METERS_PER_UNIT
"""Reused verbatim from `openusd_spatial_adapter.py` (never a second unit
constant) -- 1.0 (meters), matching every canonical coordinate in this
repository."""
USD_STAGE_UP_AXIS = usda.UP_AXIS
"""Reused verbatim -- "Z", matching `canonical_spatial_authority.Transform.
position_z` (vertical) directly; no rotation is ever applied for visual
convenience (section 4)."""

USD_TIME_CODES_PER_SECOND = dss.USD_TIME_CODES_PER_SECOND
"""Reused verbatim from `dynamic_scene_state_authority.py` (1.0: one USD
TimeCode == one real playback second) -- never a second time-mapping
formula. `simulation_minutes_to_usd_timecode`/its inverse are reused
directly below, never reimplemented."""
USD_FRAMES_PER_SECOND = 24.0
"""Section 11: an explicit, documented DCC/viewer playback-rate HINT --
independent of `timeCodesPerSecond` (which governs the actual TimeCode<->
second relationship). Presentation choice only; never alters engineering
trajectory duration."""

ENGINEERING_TIME_UNIT = pta.PRODUCTION_TRAJECTORY_TIME_UNIT

OPENUSD_SELECTS_TRANSPORT_SOLUTION = False
OPENUSD_BECOMES_ENGINEERING_AUTHORITY = False
ENGINEERING_RECOMPUTED_INSIDE_OPENUSD_ADAPTER = False
BENTLEY_CALLED_DURING_USD_EXPORT = False
NVIDIA_REQUIRED_TO_GENERATE_USD = False
NVIDIA_STARTED = False
OPENUSD_BUILD_CHANGES_ENGINEERING = False
OPENUSD_BUILD_CHANGES_ECONOMICS = False
OPENUSD_BUILD_CHANGES_DEMAND = False

_ENTITY_GEOM_TYPE: Mapping[str, str] = {
    "MRT_CARRIER": "Cube", "RGHT_VEHICLE": "Cube", "MANUAL_PORTER": "Capsule", "PATIENT": "Capsule",
}
_ENTITY_DISPLAY_COLOR: Mapping[str, tuple[float, float, float]] = {
    "MRT_CARRIER": (0.85, 0.15, 0.15), "RGHT_VEHICLE": (0.15, 0.45, 0.85),
    "MANUAL_PORTER": (0.95, 0.65, 0.10), "PATIENT": (0.15, 0.75, 0.30),
}
"""Section 10: presentation-only display colors distinguishing the four
entity types -- NEVER engineering truth (matches the discipline already
established by `mrt_service_class_authority`'s presentation-color
separation)."""

_NETWORK_PRIM_NAME: Mapping[str, str] = {
    "MRT_CARRIER": "MRT", "RGHT_VEHICLE": "RGHT", "MANUAL_PORTER": "Pedestrian", "PATIENT": "Pedestrian",
}


def _prim_name(entity_id: str) -> str:
    return usda.sanitize_prim_path_segment(entity_id.replace("-", "_"))


def _fmt(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError(f"non-finite numeric value cannot be authored to USD: {value!r}")
    return f"{value:.6f}"


def _vec(x: float, y: float, z: float) -> str:
    return f"({_fmt(x)}, {_fmt(y)}, {_fmt(z)})"


# ---------------------------------------------------------------------------
# Section 12/15: merge ALL of one entity's Build 1 trajectories (in time
# order) into ONE continuous sample track -- holds position across
# inter-mission gaps (never linearly interpolating a fake motion across a
# dwell), reusing Build 1 samples verbatim (never recomputed).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MergedEntitySamples:
    entity_id: str
    entity_type: str
    mission_ids: tuple[str, ...]
    samples: tuple[tuple[float, float, float, float, str], ...]  # (time_minutes, x, y, z, motion_state)


def merge_entity_samples(scene: odts.OperationalDayTrajectoryScene, entity_id: str) -> MergedEntitySamples:
    trajectories = odts.trajectories_for_entity(scene, entity_id)
    calibrated = sorted(
        (t for t in trajectories if isinstance(t.start_time_minutes, float) and isinstance(t.end_time_minutes, float)),
        key=lambda t: t.start_time_minutes,  # type: ignore[arg-type,return-value]
    )
    if not calibrated:
        fallback_type = trajectories[0].entity_type if trajectories else "UNKNOWN"
        return MergedEntitySamples(entity_id=entity_id, entity_type=fallback_type, mission_ids=(), samples=())
    merged: list[tuple[float, float, float, float, str]] = []
    for index, trajectory in enumerate(calibrated):
        for sample in trajectory.samples:
            merged.append((sample.time_minutes, sample.x_m, sample.y_m, sample.z_m, sample.motion_state))  # type: ignore[arg-type]
        if index + 1 < len(calibrated):
            next_trajectory = calibrated[index + 1]
            gap = next_trajectory.start_time_minutes - trajectory.end_time_minutes  # type: ignore[operator]
            if gap > 1e-9:
                last_sample = trajectory.samples[-1]
                hold_time = trajectory.end_time_minutes + gap / 2.0  # type: ignore[operator]
                merged.append((hold_time, last_sample.x_m, last_sample.y_m, last_sample.z_m, last_sample.motion_state))
    mission_ids = tuple(t.mission_id for t in calibrated if t.mission_id is not None)
    return MergedEntitySamples(entity_id=entity_id, entity_type=calibrated[0].entity_type, mission_ids=mission_ids, samples=tuple(merged))


def _collect_room_markers(scene: odts.OperationalDayTrajectoryScene) -> dict[str, tuple[float, float, float]]:
    """Section 6: simple room/anchor markers derived directly from each
    trajectory's own origin/destination endpoint positions -- never a
    second coordinate source."""
    markers: dict[str, tuple[float, float, float]] = {}
    for trajectory in scene.trajectories:
        if not trajectory.samples:
            continue
        first, last = trajectory.samples[0], trajectory.samples[-1]
        if isinstance(first.x_m, float):
            markers.setdefault(trajectory.origin_object_id, (first.x_m, first.y_m, first.z_m))
        if isinstance(last.x_m, float):
            markers.setdefault(trajectory.destination_object_id, (last.x_m, last.y_m, last.z_m))
    return dict(sorted(markers.items()))


def _collect_static_networks(scene: odts.OperationalDayTrajectoryScene) -> dict[str, tuple[tuple[float, float, float], ...]]:
    """Sections 7-8: static guideway/path geometry derived DIRECTLY from
    each entity's own trajectory samples (the exact canonical route
    already resolved by Build 1) -- never a second route/geometry source,
    never a straight line between endpoints."""
    networks: dict[str, tuple[tuple[float, float, float], ...]] = {}
    for trajectory in scene.trajectories:
        network_name = _NETWORK_PRIM_NAME.get(trajectory.entity_type)
        if network_name is None or network_name in networks or not trajectory.samples:
            continue
        networks[network_name] = tuple((s.x_m, s.y_m, s.z_m) for s in trajectory.samples)
    return dict(sorted(networks.items()))


def _compute_scene_bounds(scene: odts.OperationalDayTrajectoryScene) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    xs, ys, zs = [], [], []
    for trajectory in scene.trajectories:
        for sample in trajectory.samples:
            if isinstance(sample.x_m, float):
                xs.append(sample.x_m); ys.append(sample.y_m); zs.append(sample.z_m)
    if not xs:
        return (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


# ---------------------------------------------------------------------------
# Section 21: the actual ASCII USDA stage text builder.
# ---------------------------------------------------------------------------


def build_yc_demo_usda_text_fallback(scene: odts.OperationalDayTrajectoryScene) -> str:
    """Section 2 fallback path: hand-authored ASCII USDA text, no `pxr`
    import at all. Used automatically by `export_yc_demo_stage` only when
    `OPENUSD_PYTHON_RUNTIME_AVAILABLE` is False; kept and tested even in
    this environment (where the real runtime IS available) so the artifact
    remains generatable on a machine without a vendored USD runtime."""
    if not isinstance(scene.start_time_minutes, float) or not isinstance(scene.end_time_minutes, float):
        raise ValueError(f"scene {scene.scene_id!r} has no calibrated time window -- cannot author a time-sampled USD stage")

    start_tc = dss.simulation_minutes_to_usd_timecode(scene.start_time_minutes)
    end_tc = dss.simulation_minutes_to_usd_timecode(scene.end_time_minutes)
    (min_x, min_y, min_z), (max_x, max_y, max_z) = _compute_scene_bounds(scene)
    center = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, (min_z + max_z) / 2.0)
    span = max(max_x - min_x, max_y - min_y, 5.0)
    camera_pos = (center[0] - span, center[1] - span, center[2] + span)

    lines: list[str] = []
    lines.append("#usda 1.0")
    lines.append("(")
    lines.append(f'    defaultPrim = "{USD_STAGE_ROOT_NAME}"')
    lines.append(f"    metersPerUnit = {_fmt(USD_STAGE_METERS_PER_UNIT)}")
    lines.append(f'    upAxis = "{USD_STAGE_UP_AXIS}"')
    lines.append(f"    startTimeCode = {_fmt(start_tc)}")
    lines.append(f"    endTimeCode = {_fmt(end_tc)}")
    lines.append(f"    timeCodesPerSecond = {_fmt(USD_TIME_CODES_PER_SECOND)}")
    lines.append(f"    framesPerSecond = {_fmt(USD_FRAMES_PER_SECOND)}")
    lines.append("    customLayerData = {")
    lines.append(f'        string engineering_time_unit = "{ENGINEERING_TIME_UNIT}"')
    lines.append(f'        string scene_id = "{scene.scene_id}"')
    lines.append("    }")
    lines.append(")")
    lines.append("")
    lines.append(f'def Xform "{USD_STAGE_ROOT_NAME}"')
    lines.append("{")

    # --- Facility: simple room/anchor markers ---
    lines.append('    def Xform "Facility"')
    lines.append("    {")
    for room_id, (x, y, z) in _collect_room_markers(scene).items():
        prim_name = usda.sanitize_prim_path_segment(room_id.replace("-", "_"))
        lines.append(f'        def Cube "{prim_name}"')
        lines.append("        (")
        lines.append(f'            customData = {{ string room_id = "{room_id}" }}')
        lines.append("        )")
        lines.append("        {")
        lines.append("            double size = 2")
        lines.append(f"            double3 xformOp:translate = {_vec(x, y, z)}")
        lines.append('            uniform token[] xformOpOrder = ["xformOp:translate"]')
        lines.append("        }")
    lines.append("    }")

    # --- Infrastructure: static network guideways derived from engine geometry ---
    lines.append('    def Xform "Infrastructure"')
    lines.append("    {")
    for network_name, points in _collect_static_networks(scene).items():
        lines.append(f'        def Xform "{network_name}"')
        lines.append("        {")
        lines.append('            def BasisCurves "Guideway"')
        lines.append("            {")
        lines.append('                uniform token type = "linear"')
        lines.append(f"                int[] curveVertexCounts = [{len(points)}]")
        points_str = ", ".join(_vec(x, y, z) for x, y, z in points)
        lines.append(f"                point3f[] points = [{points_str}]")
        widths_str = ", ".join("0.1" for _ in points)
        lines.append(f"                float[] widths = [{widths_str}]")
        lines.append("            }")
        lines.append("        }")
    lines.append("    }")

    # --- DynamicEntities: one stable prim per entity, time-sampled translate ---
    lines.append('    def Xform "DynamicEntities"')
    lines.append("    {")
    for entity_id in scene.entity_ids:
        merged = merge_entity_samples(scene, entity_id)
        if not merged.samples:
            continue
        entity_trajectories = odts.trajectories_for_entity(scene, entity_id)
        first_trajectory = entity_trajectories[0]
        geom_type = _ENTITY_GEOM_TYPE.get(merged.entity_type, "Cube")
        color = _ENTITY_DISPLAY_COLOR.get(merged.entity_type, (0.8, 0.8, 0.8))
        prim_name = _prim_name(entity_id)
        lines.append(f'        def {geom_type} "{prim_name}"')
        lines.append("        (")
        lines.append("            customData = {")
        lines.append(f'                string entity_id = "{entity_id}"')
        lines.append(f'                string entity_type = "{merged.entity_type}"')
        lines.append(f'                string transport_mode = "{first_trajectory.transport_mode}"')
        lines.append(f'                string mission_ids = "{",".join(merged.mission_ids)}"')
        if first_trajectory.payload_service_class:
            lines.append(f'                string service_class = "{first_trajectory.payload_service_class}"')
        if first_trajectory.patient_id:
            lines.append(f'                string patient_id = "{first_trajectory.patient_id}"')
        lines.append("            }")
        lines.append("        )")
        lines.append("        {")
        lines.append(f"            color3f[] primvars:displayColor = [{_vec(*color)}]")
        if geom_type == "Cube":
            lines.append("            double size = 1")
        else:
            lines.append("            double height = 1")
            lines.append("            double radius = 0.3")
        lines.append("            double3 xformOp:translate.timeSamples = {")
        for time_minutes, x, y, z, _motion_state in merged.samples:
            timecode = dss.simulation_minutes_to_usd_timecode(time_minutes)
            lines.append(f"                {_fmt(timecode)}: {_vec(x, y, z)},")
        lines.append("            }")
        lines.append('            uniform token[] xformOpOrder = ["xformOp:translate"]')
        lines.append("            custom string motion_state.timeSamples = {")
        for time_minutes, _x, _y, _z, motion_state in merged.samples:
            timecode = dss.simulation_minutes_to_usd_timecode(time_minutes)
            lines.append(f'                {_fmt(timecode)}: "{motion_state}",')
        lines.append("            }")
        lines.append("        }")
    lines.append("    }")

    # --- One simple overview camera (section 19) ---
    lines.append('    def Camera "DemoCam"')
    lines.append("    (")
    lines.append('        customData = { string purpose = "YC demo overview camera -- simple elevated view, not cinematic" }')
    lines.append("    )")
    lines.append("    {")
    lines.append(f"        double3 xformOp:translate = {_vec(*camera_pos)}")
    lines.append("        float3 xformOp:rotateXYZ = (-35, 0, 45)")
    lines.append('        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]')
    lines.append("        float focalLength = 35")
    lines.append("    }")

    lines.append("}")
    return "\n".join(lines) + "\n"


USD_DEMO_CAMERA = "CREATED"
"""Section 19: a single, simple elevated/diagonal overview camera is
authored above -- not cinematic, but genuinely present (never deferred
merely for expedience, since ASCII authoring of one static camera prim is
trivial)."""

USD_LIGHTING = "DEFERRED"
"""Section 20: no `UsdLux` prim is authored -- every dynamic/static prim
carries an explicit `primvars:displayColor`, which standard USD viewers
render correctly under their own default lighting; adding physically-based
lighting was judged unnecessary for a technically-credible first artifact
and is deferred per the YC governor (section 0)."""


# ---------------------------------------------------------------------------
# Section 3/21: real-`pxr`-backed stage builder -- the PRIMARY path in this
# environment (the vendored runtime IS available). Reuses the existing
# adapter's authoring functions directly; never reimplements interpolation
# or the minutes<->TimeCode mapping.
# ---------------------------------------------------------------------------


def build_yc_demo_stage(scene: odts.OperationalDayTrajectoryScene) -> "usda.Usd.Stage":
    usda._require_runtime()
    if not isinstance(scene.start_time_minutes, float) or not isinstance(scene.end_time_minutes, float):
        raise ValueError(f"scene {scene.scene_id!r} has no calibrated time window -- cannot author a time-sampled USD stage")

    Usd, UsdGeom, Gf = usda.Usd, usda.UsdGeom, usda.Gf

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(stage, USD_STAGE_METERS_PER_UNIT)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root = UsdGeom.Xform.Define(stage, USD_STAGE_ROOT_PATH)
    stage.SetDefaultPrim(root.GetPrim())
    root.GetPrim().SetCustomDataByKey("scene_id", scene.scene_id)
    root.GetPrim().SetCustomDataByKey("engineering_time_unit", ENGINEERING_TIME_UNIT)

    # Reused verbatim: authors the existing, already-tested 1-TimeCode==
    # 1-second stage time basis (section 3). `framesPerSecond` is then
    # overridden to our own explicit, documented viewer-hint constant
    # WITHOUT touching `timeCodesPerSecond` (which stays the reused 1.0).
    usda.configure_stage_time_basis(stage, start_time_minutes=scene.start_time_minutes, end_time_minutes=scene.end_time_minutes)
    stage.SetFramesPerSecond(USD_FRAMES_PER_SECOND)

    # --- Facility: simple room/anchor markers ---
    UsdGeom.Xform.Define(stage, f"{USD_STAGE_ROOT_PATH}/Facility")
    for room_id, (x, y, z) in _collect_room_markers(scene).items():
        prim_name = usda.sanitize_prim_path_segment(room_id.replace("-", "_"))
        cube = UsdGeom.Cube.Define(stage, f"{USD_STAGE_ROOT_PATH}/Facility/{prim_name}")
        cube.CreateSizeAttr(2.0)
        UsdGeom.XformCommonAPI(cube.GetPrim()).SetTranslate(Gf.Vec3d(x, y, z))
        cube.GetPrim().SetCustomDataByKey("room_id", room_id)

    # --- Infrastructure: static network guideways derived from engine geometry ---
    UsdGeom.Xform.Define(stage, f"{USD_STAGE_ROOT_PATH}/Infrastructure")
    for network_name, points in _collect_static_networks(scene).items():
        network_path = f"{USD_STAGE_ROOT_PATH}/Infrastructure/{network_name}"
        UsdGeom.Xform.Define(stage, network_path)
        curve = UsdGeom.BasisCurves.Define(stage, f"{network_path}/Guideway")
        curve.CreateTypeAttr(UsdGeom.Tokens.linear)
        curve.CreateCurveVertexCountsAttr([len(points)])
        curve.CreatePointsAttr([Gf.Vec3f(*p) for p in points])
        curve.CreateWidthsAttr([0.1 for _ in points])

    # --- DynamicEntities: one stable prim per entity, real time-sampled xforms ---
    UsdGeom.Xform.Define(stage, f"{USD_STAGE_ROOT_PATH}/DynamicEntities")
    for entity_id in scene.entity_ids:
        merged = merge_entity_samples(scene, entity_id)
        if not merged.samples:
            continue
        entity_trajectories = odts.trajectories_for_entity(scene, entity_id)
        first_trajectory = entity_trajectories[0]
        geom_type = _ENTITY_GEOM_TYPE.get(merged.entity_type, "Cube")
        color = _ENTITY_DISPLAY_COLOR.get(merged.entity_type, (0.8, 0.8, 0.8))
        prim_name = _prim_name(entity_id)
        prim_path = f"{USD_STAGE_ROOT_PATH}/DynamicEntities/{prim_name}"

        if geom_type == "Cube":
            geom = UsdGeom.Cube.Define(stage, prim_path)
            geom.CreateSizeAttr(1.0)
        else:
            geom = UsdGeom.Capsule.Define(stage, prim_path)
            geom.CreateHeightAttr(1.0)
            geom.CreateRadiusAttr(0.3)
        geom.CreateDisplayColorAttr([Gf.Vec3f(*color)])

        prim = geom.GetPrim()
        prim.SetCustomDataByKey("mrtway_object_id", entity_id)
        prim.SetCustomDataByKey("entity_id", entity_id)
        prim.SetCustomDataByKey("entity_type", merged.entity_type)
        prim.SetCustomDataByKey("transport_mode", first_trajectory.transport_mode)
        prim.SetCustomDataByKey("mission_ids", ",".join(merged.mission_ids))
        if first_trajectory.payload_service_class:
            prim.SetCustomDataByKey("service_class", first_trajectory.payload_service_class)
        if first_trajectory.patient_id:
            prim.SetCustomDataByKey("patient_id", first_trajectory.patient_id)

        # Reused verbatim: builds the EXISTING presentation-only contract
        # object from our merged (never reinterpolated) samples, then
        # authors it via the EXISTING adapter function -- never a second
        # time-sample-authoring routine.
        waypoints = [(x, y, z) for (_t, x, y, z, _m) in merged.samples]
        times = [t for (t, _x, _y, _z, _m) in merged.samples]
        states = [m for (_t, _x, _y, _z, m) in merged.samples]
        dyn_trajectory = dss.build_linear_trajectory(
            canonical_object_id=entity_id, waypoints_m=waypoints, times_minutes=times,
            movement_states=states, provenance=first_trajectory.trajectory_provenance,
        )
        usda.author_dynamic_object_trajectory(stage, prim_path=prim_path, trajectory=dyn_trajectory)

    # --- One simple overview camera (section 19) -- defined directly under
    # our OWN root (never `openusd_spatial_adapter.add_presentation_camera`,
    # which hard-codes the unrelated `/MRTwayCampus` root from the earlier,
    # full-facility-export build). ---
    (min_x, min_y, min_z), (max_x, max_y, max_z) = _compute_scene_bounds(scene)
    center = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, (min_z + max_z) / 2.0)
    span = max(max_x - min_x, max_y - min_y, 5.0)
    camera_pos = (center[0] - span, center[1] - span, center[2] + span)
    camera = UsdGeom.Camera.Define(stage, f"{USD_STAGE_ROOT_PATH}/DemoCam")
    camera.GetPrim().SetCustomDataByKey("purpose", "YC demo overview camera -- simple elevated view, not cinematic")
    UsdGeom.XformCommonAPI(camera.GetPrim()).SetTranslate(Gf.Vec3d(*camera_pos))
    UsdGeom.XformCommonAPI(camera.GetPrim()).SetRotate(Gf.Vec3f(-35.0, 0.0, 45.0))
    camera.CreateFocalLengthAttr(35.0)

    return stage


USD_DEMO_CAMERA = "CREATED"
"""Section 19: a single, simple elevated/diagonal overview camera is
authored above -- not cinematic, but genuinely present (never deferred
merely for expedience, since authoring one static camera prim is
trivial)."""

USD_LIGHTING = "DEFERRED"
"""Section 20: no `UsdLux` prim is authored -- every dynamic/static prim
carries an explicit `displayColor`, which standard USD viewers render
correctly under their own default lighting; adding physically-based
lighting was judged unnecessary for a technically-credible first artifact
and is deferred per the YC governor (section 0)."""


# ---------------------------------------------------------------------------
# Section 21-22: artifact + manifest export. Uses the real `pxr` runtime
# when available (this environment), else the dependency-free ASCII
# fallback -- decided ONCE, explicitly, never silently.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsdArtifact:
    path: str
    format: str
    size_bytes: int


@dataclass(frozen=True)
class UsdManifest:
    path: str
    content: Mapping[str, object]


def export_yc_demo_stage(scene: odts.OperationalDayTrajectoryScene, *, output_dir: str = "artifacts/yc_demo") -> tuple[UsdArtifact, UsdManifest]:
    os.makedirs(output_dir, exist_ok=True)
    artifact_path = os.path.join(output_dir, "mrt_pharma_yc_demo.usda")
    if OPENUSD_PYTHON_RUNTIME_AVAILABLE:
        stage = build_yc_demo_stage(scene)
        usda.save_stage_to_usda(stage, artifact_path)
    else:
        usda_text = build_yc_demo_usda_text_fallback(scene)
        with open(artifact_path, "w") as handle:
            handle.write(usda_text)
    artifact = UsdArtifact(path=artifact_path, format="usda", size_bytes=os.path.getsize(artifact_path))

    manifest_content = {
        "scene_id": scene.scene_id,
        "stage_units": {"metersPerUnit": USD_STAGE_METERS_PER_UNIT, "upAxis": USD_STAGE_UP_AXIS},
        "engineering_time_unit": ENGINEERING_TIME_UNIT,
        "usd_time_codes_per_second": USD_TIME_CODES_PER_SECOND,
        "usd_frames_per_second": USD_FRAMES_PER_SECOND,
        "scene_start_time_minutes": scene.start_time_minutes,
        "scene_end_time_minutes": scene.end_time_minutes,
        "entity_count": len(scene.entity_ids),
        "entity_ids": list(scene.entity_ids),
        "mission_ids": list(scene.mission_ids),
        "artifact_filename": os.path.basename(artifact_path),
    }
    manifest_path = os.path.join(output_dir, "mrt_pharma_yc_demo_manifest.json")
    with open(manifest_path, "w") as handle:
        json.dump(manifest_content, handle, indent=2, sort_keys=True)
    manifest = UsdManifest(path=manifest_path, content=manifest_content)
    return artifact, manifest


# ---------------------------------------------------------------------------
# Section 23: validation -- OPENUSD_RUNTIME if `pxr` is importable, else a
# deterministic STRUCTURAL check. Never claims full-parser validation
# without a real parser.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsdStructuralValidationResult:
    valid: bool
    checks: Mapping[str, bool]
    detail: str


def determine_validation_level() -> str:
    return "OPENUSD_RUNTIME" if OPENUSD_PYTHON_RUNTIME_AVAILABLE else "STRUCTURAL"


def validate_usda_with_runtime(path: str, scene: odts.OperationalDayTrajectoryScene) -> UsdStructuralValidationResult:
    """Section 23 primary path (runtime available): re-opens the authored
    `.usda` file with the REAL `pxr` parser and checks stage metadata,
    prim existence, and round-tripped entity start positions against the
    scene's own (never recomputed) samples -- genuine parser validation,
    not a text scan."""
    usda._require_runtime()
    stage = usda.load_stage_from_usda(path)
    checks: dict[str, bool] = {"stage_opens": stage is not None}
    default_prim = stage.GetDefaultPrim()
    checks["has_default_prim"] = bool(default_prim) and default_prim.IsValid()
    checks["meters_per_unit_correct"] = math.isclose(usda.UsdGeom.GetStageMetersPerUnit(stage), USD_STAGE_METERS_PER_UNIT, rel_tol=1e-9)
    checks["up_axis_correct"] = usda.UsdGeom.GetStageUpAxis(stage) == usda.UsdGeom.Tokens.z
    expected_start = dss.simulation_minutes_to_usd_timecode(scene.start_time_minutes)  # type: ignore[arg-type]
    expected_end = dss.simulation_minutes_to_usd_timecode(scene.end_time_minutes)  # type: ignore[arg-type]
    checks["start_time_code_correct"] = math.isclose(stage.GetStartTimeCode(), expected_start, rel_tol=1e-9)
    checks["end_time_code_correct"] = math.isclose(stage.GetEndTimeCode(), expected_end, rel_tol=1e-9)
    checks["infrastructure_prim_exists"] = stage.GetPrimAtPath(f"{USD_STAGE_ROOT_PATH}/Infrastructure").IsValid()
    for entity_id in scene.entity_ids:
        prim_name = _prim_name(entity_id)
        prim_path = f"{USD_STAGE_ROOT_PATH}/DynamicEntities/{prim_name}"
        prim = stage.GetPrimAtPath(prim_path)
        checks[f"entity_prim_exists_{prim_name}"] = prim.IsValid()
        merged = merge_entity_samples(scene, entity_id)
        if prim.IsValid() and merged.samples:
            time0, x0, y0, z0, _motion0 = merged.samples[0]
            state = usda.read_dynamic_object_state_at_time(stage, prim_path=prim_path, simulation_time_minutes=time0)
            checks[f"entity_start_position_correct_{prim_name}"] = (
                math.isclose(state.position_x_m, x0, abs_tol=1e-6)
                and math.isclose(state.position_y_m, y0, abs_tol=1e-6)
                and math.isclose(state.position_z_m, z0, abs_tol=1e-6)
            )
    valid = all(checks.values())
    detail = "ALL_CHECKS_PASSED" if valid else f"FAILED: {sorted(k for k, v in checks.items() if not v)}"
    return UsdStructuralValidationResult(valid=valid, checks=checks, detail=detail)


_NAN_TOKEN = re.compile(r"\bnan\b", re.IGNORECASE)
_INF_TOKEN = re.compile(r"\binf\b", re.IGNORECASE)


def validate_usda_structure(usda_text: str, *, expected_entity_ids: Sequence[str]) -> UsdStructuralValidationResult:
    checks: dict[str, bool] = {
        "has_usda_header": usda_text.startswith("#usda 1.0"),
        "has_meters_per_unit": "metersPerUnit" in usda_text,
        "has_up_axis": "upAxis" in usda_text,
        "has_start_time_code": "startTimeCode" in usda_text,
        "has_end_time_code": "endTimeCode" in usda_text,
        "has_dynamic_entities_prim": 'def Xform "DynamicEntities"' in usda_text,
        "has_infrastructure_prim": 'def Xform "Infrastructure"' in usda_text,
        "has_time_samples": "xformOp:translate.timeSamples" in usda_text,
        "balanced_braces": usda_text.count("{") == usda_text.count("}"),
        "balanced_parens": usda_text.count("(") == usda_text.count(")"),
        "no_nan": _NAN_TOKEN.search(usda_text) is None,
        "no_inf": _INF_TOKEN.search(usda_text) is None,
    }
    for entity_id in expected_entity_ids:
        checks[f"has_entity_prim_{_prim_name(entity_id)}"] = f'"{_prim_name(entity_id)}"' in usda_text
    valid = all(checks.values())
    detail = "ALL_CHECKS_PASSED" if valid else f"FAILED: {sorted(k for k, v in checks.items() if not v)}"
    return UsdStructuralValidationResult(valid=valid, checks=checks, detail=detail)

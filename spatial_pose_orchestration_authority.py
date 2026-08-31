"""6-DOF Anchor/Movable Pose Orchestration (ADDITIVE clarification to the
current Bentley 3D digital-twin integration + spatial-network-response build).

This module introduces NO new spatial transform engine. It COMPOSES the
existing 6-DOF primitives in `canonical_spatial_authority`:
  * `Transform` (position x/y/z + rotation x/y/z -- full 6-DOF rigid pose)
  * `apply_rigid_transform` (x_global = R x_local + t; Rz.Ry.Rx Euler)
  * `resolve_global_position` (accumulates up the parent chain -- children
    follow parent translation AND rotation)
  * `SpatialObjectRegistry.replace_transform` (non-mutating; rigid-body child
    propagation)
  * `compute_global_distance`

It establishes the Bentley/spatial ORCHESTRATION around those primitives:
ANCHOR / MOVABLE semantics, permitted-DOF policy, relative vector + true 3D
geometric separation, orientation-aware connection-candidate invalidation, and
the hard doctrine

    GEOMETRIC_SEPARATION != TRANSPORT_ROUTE_LENGTH

(each mode recomputes through its own legal movement domain -- see
`transport_movement_domain_authority`).

Nothing here is put into the capital-inheritance economics authority. Nothing
mutates a live Bentley iModel, MRT canonical physics, Part 3E, or equal_budget.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Mapping

import canonical_spatial_authority as csa

# ===========================================================================
# 1. Anchor / Movable role + permitted-DOF policy.
# ===========================================================================

PoseRole = Literal["ANCHOR", "MOVABLE"]

DegreeOfFreedom = Literal["TX", "TY", "TZ", "ROLL", "PITCH", "YAW"]

ALL_DOF: tuple[DegreeOfFreedom, ...] = ("TX", "TY", "TZ", "ROLL", "PITCH", "YAW")


@dataclass(frozen=True)
class PermittedDofPolicy:
    """Explicit permitted-DOF set. Default = all 6 (full rigid pose).
    BUILDING_TRANSLATION_RESTRICTED_TO_SINGLE_AXIS is NO unless a caller
    deliberately supplies a single-axis policy."""

    permitted: frozenset[DegreeOfFreedom] = field(default_factory=lambda: frozenset(ALL_DOF))

    def allows(self, dof: DegreeOfFreedom) -> bool:
        return dof in self.permitted

    def is_full_6dof(self) -> bool:
        return set(self.permitted) == set(ALL_DOF)


def full_6dof_policy() -> PermittedDofPolicy:
    return PermittedDofPolicy(frozenset(ALL_DOF))


def ground_plane_policy() -> PermittedDofPolicy:
    """An explicit constrained policy: planar translation + yaw only (no Z,
    roll, pitch). Used ONLY when a caller opts in."""
    return PermittedDofPolicy(frozenset({"TX", "TY", "YAW"}))


def whole_building_placement_policy() -> PermittedDofPolicy:
    """Sec M-Q: the NORMAL whole-building planning UX policy -- FREE PLANAR
    PLACEMENT (X, Y) + YAW ROTATION + SUPPORT-AWARE ELEVATION (Z), with ROLL
    and PITCH LOCKED (upright equilibrium). This is NOT unrestricted 6-DOF: a
    building must never be left banked/tilted/pitched. The underlying
    canonical Transform remains 6-DOF capable for other object classes; this
    policy is the product placement contract for a whole building.

    Z is permitted here at the DOF level, but committed placement must resolve
    it support-aware (see resolve_support_aware_elevation) -- never left
    floating."""
    return PermittedDofPolicy(frozenset({"TX", "TY", "TZ", "YAW"}))


# Hard-gate flags (Sec M-Q, AB).
SPATIAL_TRANSFORM_SUPPORTS_6DOF = True
"""Hard flag: the underlying canonical Transform carries all 6 DOF."""
WHOLE_BUILDING_UNRESTRICTED_6DOF_UX = False
WHOLE_BUILDING_ROLL_LOCKED = True
WHOLE_BUILDING_PITCH_LOCKED = True
WHOLE_BUILDING_YAW_FREE = True
WHOLE_BUILDING_XY_FREE = True
WHOLE_BUILDING_Z_SUPPORT_AWARE = True


# ===========================================================================
# 1b. Whole-building placement resolution: PREVIEW -> RESOLVE -> COMMITTED
#     (Sec S). Locks roll/pitch to upright; resolves support-aware Z; free
#     X/Y/yaw. Vertical building movement is CHANGE_SUPPORT_ELEVATION, NEVER
#     floor-count (Sec R).
# ===========================================================================

SupportResolution = Literal["RESOLVED_TO_SUPPORT", "SUPPORT_ELEVATION_NOT_CALIBRATED"]


@dataclass(frozen=True)
class WholeBuildingPlacementResult:
    preview_transform: csa.Transform
    committed_transform: csa.Transform
    roll_pitch_forced_upright: bool
    support_resolution: SupportResolution
    z_source: str


def resolve_whole_building_placement(
    *, preview_transform: csa.Transform, support_elevation_m: float | None,
) -> WholeBuildingPlacementResult:
    """Sec M-S: from a raw/preview drag pose, produce the COMMITTED engineering
    pose the authoritative engine consumes: roll (rotation_x) and pitch
    (rotation_y) forced to 0 (upright equilibrium); free X/Y/yaw preserved; Z
    resolved to a known support plane when available, else left at the preview
    Z but flagged SUPPORT_ELEVATION_NOT_CALIBRATED (never inventing grade)."""
    roll_pitch_changed = (abs(preview_transform.rotation_x) > 1e-9 or abs(preview_transform.rotation_y) > 1e-9)
    if support_elevation_m is not None:
        z = support_elevation_m
        support_res: SupportResolution = "RESOLVED_TO_SUPPORT"
        z_source = "support_plane"
    else:
        z = preview_transform.position_z
        support_res = "SUPPORT_ELEVATION_NOT_CALIBRATED"
        z_source = "NOT_CALIBRATED (preview Z retained; grade never fabricated)"
    committed = csa.Transform(
        position_x=preview_transform.position_x, position_y=preview_transform.position_y, position_z=z,
        rotation_x=0.0, rotation_y=0.0, rotation_z=preview_transform.rotation_z,  # roll/pitch locked; yaw free
    )
    return WholeBuildingPlacementResult(
        preview_transform=preview_transform, committed_transform=committed,
        roll_pitch_forced_upright=roll_pitch_changed, support_resolution=support_res, z_source=z_source,
    )


# ===========================================================================
# 2. Anchor/Movable relationship over the canonical registry.
# ===========================================================================

@dataclass(frozen=True)
class PoseState:
    object_id: str
    position_xyz: tuple[float, float, float]
    rotation_deg_xyz: tuple[float, float, float]


@dataclass(frozen=True)
class AnchorMovableSeparation:
    anchor_id: str
    movable_id: str
    anchor_pose: PoseState
    movable_pose: PoseState
    relative_vector_xyz: tuple[float, float, float]
    delta_x: float
    delta_y: float
    delta_z: float
    geometric_separation_m: float
    movable_orientation_deg_xyz: tuple[float, float, float]
    anchor_drifted: bool


def _pose(registry: csa.SpatialObjectRegistry, object_id: str) -> PoseState:
    obj = registry.get(object_id)
    gp = csa.resolve_global_position(registry, object_id)
    t = obj.transform
    return PoseState(object_id=object_id, position_xyz=gp, rotation_deg_xyz=(t.rotation_x, t.rotation_y, t.rotation_z))


def _xyz_close(a: tuple[float, float, float], b: tuple[float, float, float], tol: float = 1e-9) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def compute_anchor_movable_separation(
    registry: csa.SpatialObjectRegistry, *, anchor_id: str, movable_id: str,
    anchor_reference_position: tuple[float, float, float] | None = None,
) -> AnchorMovableSeparation:
    """Expose anchor pose, movable pose, relative vector, per-axis deltas, true
    3D geometric separation, and movable orientation. `anchor_reference_position`
    (optional) lets a caller assert the anchor did not drift after a movable
    transform (ANCHOR / LOCKED doctrine)."""
    a = _pose(registry, anchor_id)
    b = _pose(registry, movable_id)
    rel = (b.position_xyz[0] - a.position_xyz[0],
           b.position_xyz[1] - a.position_xyz[1],
           b.position_xyz[2] - a.position_xyz[2])
    sep = math.dist(a.position_xyz, b.position_xyz)
    drifted = (anchor_reference_position is not None
               and not _xyz_close(a.position_xyz, anchor_reference_position))
    return AnchorMovableSeparation(
        anchor_id=anchor_id, movable_id=movable_id, anchor_pose=a, movable_pose=b,
        relative_vector_xyz=rel, delta_x=rel[0], delta_y=rel[1], delta_z=rel[2],
        geometric_separation_m=sep, movable_orientation_deg_xyz=b.rotation_deg_xyz,
        anchor_drifted=drifted,
    )


def move_movable(
    registry: csa.SpatialObjectRegistry, *, movable_id: str, new_transform: csa.Transform,
    policy: PermittedDofPolicy | None = None, current_transform: csa.Transform | None = None,
) -> csa.SpatialObjectRegistry:
    """Apply a new pose to the MOVABLE object via the existing non-mutating
    `replace_transform` (children follow rigidly). If a permitted-DOF policy is
    supplied, a change on a forbidden DOF raises (never silently ignored)."""
    if policy is not None and current_transform is not None:
        _enforce_policy(current_transform, new_transform, policy)
    return registry.replace_transform(movable_id, new_transform)


def _enforce_policy(old: csa.Transform, new: csa.Transform, policy: PermittedDofPolicy) -> None:
    changes: Mapping[DegreeOfFreedom, tuple[float, float]] = {
        "TX": (old.position_x, new.position_x), "TY": (old.position_y, new.position_y),
        "TZ": (old.position_z, new.position_z), "ROLL": (old.rotation_x, new.rotation_x),
        "PITCH": (old.rotation_y, new.rotation_y), "YAW": (old.rotation_z, new.rotation_z),
    }
    for dof, (o, n) in changes.items():
        if abs(o - n) > 1e-9 and not policy.allows(dof):
            raise ValueError(f"DOF {dof} change not permitted by policy (permitted={sorted(policy.permitted)})")


# ===========================================================================
# 3. Orientation-aware connection-candidate invalidation.
#    SAME_CENTER_DISTANCE does NOT imply SAME_ENGINEERING_RESULT.
# ===========================================================================

@dataclass(frozen=True)
class ConnectionCandidateGeometry:
    """A child interface (door / MRT endpoint / PTS station / RTHS station /
    AGV/Manual entrance) whose WORLD coordinates follow its parent's pose."""

    interface_id: str
    parent_object_id: str
    world_position_xyz: tuple[float, float, float]


def resolve_child_interface_world_positions(
    registry: csa.SpatialObjectRegistry, interface_ids: tuple[str, ...],
) -> tuple[ConnectionCandidateGeometry, ...]:
    """CHILD_CONNECTION_POINT_TRANSFORM_FOLLOWS_PARENT = YES: each interface's
    world position is resolved through the parent chain (so parent translation
    AND rotation move it correctly)."""
    out: list[ConnectionCandidateGeometry] = []
    for iid in interface_ids:
        obj = registry.get(iid)
        out.append(ConnectionCandidateGeometry(
            interface_id=iid, parent_object_id=obj.parent_object_id or "",
            world_position_xyz=csa.resolve_global_position(registry, iid),
        ))
    return tuple(out)


@dataclass(frozen=True)
class RotationImpactResult:
    center_separation_unchanged: bool
    any_interface_world_position_changed: bool
    connection_candidates_must_recompute: bool
    moved_interface_ids: tuple[str, ...]


def evaluate_rotation_impact(
    registry_before: csa.SpatialObjectRegistry, registry_after: csa.SpatialObjectRegistry,
    *, anchor_id: str, movable_id: str, interface_ids: tuple[str, ...],
) -> RotationImpactResult:
    """A yaw about the movable's own origin leaves center separation unchanged
    but moves child interface world coordinates -> connection candidates MUST
    recompute. BUILDING_ROTATION_IGNORED_BY_CONNECTION_ENGINE = NO."""
    sep_before = csa.compute_global_distance(registry_before, anchor_id, movable_id)
    sep_after = csa.compute_global_distance(registry_after, anchor_id, movable_id)
    center_unchanged = abs(sep_before - sep_after) <= 1e-9
    moved: list[str] = []
    for iid in interface_ids:
        before = csa.resolve_global_position(registry_before, iid)
        after = csa.resolve_global_position(registry_after, iid)
        if not _xyz_close(before, after):
            moved.append(iid)
    return RotationImpactResult(
        center_separation_unchanged=center_unchanged,
        any_interface_world_position_changed=bool(moved),
        connection_candidates_must_recompute=bool(moved),
        moved_interface_ids=tuple(moved),
    )


# ===========================================================================
# 4. Geometric separation != transport route length.
# ===========================================================================

@dataclass(frozen=True)
class GeometricVsTransportComparison:
    geometric_separation_m: float
    transport_route_lengths_m: Mapping[str, float | None]
    geometric_equals_all_routes: bool


def compare_geometric_vs_transport(
    *, geometric_separation_m: float, transport_route_lengths_m: Mapping[str, float | None],
) -> GeometricVsTransportComparison:
    """GEOMETRIC_SEPARATION_EQUALS_ALL_TRANSPORT_ROUTE_LENGTHS = NO: geometric
    separation is a straight-line 3D distance; each mode's route length comes
    from its own legal topology and generally differs. Returns True for
    `geometric_equals_all_routes` ONLY in the degenerate case where every
    supplied route length happens to equal the geometric separation."""
    known = [v for v in transport_route_lengths_m.values() if v is not None]
    equals_all = bool(known) and all(abs(v - geometric_separation_m) <= 1e-9 for v in known)
    return GeometricVsTransportComparison(
        geometric_separation_m=geometric_separation_m,
        transport_route_lengths_m=dict(transport_route_lengths_m),
        geometric_equals_all_routes=equals_all,
    )


# ===========================================================================
# 5. 6-DOF round-trip drift. Pose A -> arbitrary permitted Pose B -> A.
# ===========================================================================

@dataclass(frozen=True)
class SixDofRoundTripResult:
    anchor_unchanged: bool
    movable_pose_restored: bool
    child_world_positions_restored: bool
    max_drift_m: float
    drift_present: bool


def evaluate_six_dof_round_trip(
    registry_initial: csa.SpatialObjectRegistry, *, anchor_id: str, movable_id: str,
    intermediate_transform: csa.Transform, restore_transform: csa.Transform,
    interface_ids: tuple[str, ...] = (), tolerance_m: float = 1e-6,
) -> SixDofRoundTripResult:
    """Apply an arbitrary permitted intermediate pose then restore the original
    pose; verify the anchor never moved, the movable's absolute pose is
    restored, and every child interface world coordinate returns within
    tolerance. SIX_DOF_ROUND_TRIP_DRIFT_PRESENT = NO."""
    anchor_before = csa.resolve_global_position(registry_initial, anchor_id)
    child_before = {iid: csa.resolve_global_position(registry_initial, iid) for iid in interface_ids}
    movable_before = _pose(registry_initial, movable_id)

    r1 = registry_initial.replace_transform(movable_id, intermediate_transform)
    r2 = r1.replace_transform(movable_id, restore_transform)

    anchor_after = csa.resolve_global_position(r2, anchor_id)
    movable_after = _pose(r2, movable_id)
    child_after = {iid: csa.resolve_global_position(r2, iid) for iid in interface_ids}

    anchor_unchanged = _xyz_close(anchor_before, anchor_after, tolerance_m)
    movable_restored = (_xyz_close(movable_before.position_xyz, movable_after.position_xyz, tolerance_m)
                        and _xyz_close(movable_before.rotation_deg_xyz, movable_after.rotation_deg_xyz, tolerance_m))
    drifts = [max(abs(a - b) for a, b in zip(child_before[iid], child_after[iid])) for iid in interface_ids]
    child_restored = all(d <= tolerance_m for d in drifts)
    max_drift = max([*drifts, 0.0])
    return SixDofRoundTripResult(
        anchor_unchanged=anchor_unchanged, movable_pose_restored=movable_restored,
        child_world_positions_restored=child_restored, max_drift_m=max_drift,
        drift_present=not (anchor_unchanged and movable_restored and child_restored),
    )

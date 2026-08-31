"""Whole-Building Upright / Equilibrium Placement Policy Authority (ADDITIVE
clarification to the current Bentley 3D spatial build).

DOCTRINE: the geometry engine MAY support 6-DOF (the canonical_spatial_authority
`Transform` already carries rotation_x/y/z + position_x/y/z), BUT whole-building
USER manipulation is constrained by a building placement policy:

  DEFAULT WHOLE-BUILDING PERMITTED DOF (Sec A):
    TRANSLATION_X = FREE
    TRANSLATION_Y = FREE
    TRANSLATION_Z = PERMITTED SUBJECT TO SUPPORT / ELEVATION CONSTRAINTS
    YAW           = FREE (0..360)
    ROLL          = LOCKED (target 0)
    PITCH         = LOCKED (target 0)

  * A released/committed building resolves to an UPRIGHT equilibrium pose
    (roll=0, pitch=0) unless an explicit advanced scenario allows otherwise
    (Sec B/G).
  * Yaw rotation triggers connection/network recomputation (Sec C).
  * Z settles to a valid support surface where support data exist; otherwise
    SUPPORT_ELEVATION_NOT_CALIBRATED (never invent a ground level) (Sec D).
  * INTERACTIVE_PREVIEW_POSE (raw drag, may be tilted) is distinct from the
    COMMITTED_ENGINEERING_POSE; authoritative engineering state is NEVER
    computed from an invalid tilted preview (Sec E).
  * The underlying engine keeps roll/pitch capability for OTHER object classes
    (equipment/pipes/track/sloped structures) -- only the whole-building USER
    policy locks them (Sec G).

This module COMPOSES `canonical_spatial_authority.Transform`; it does not
introduce a second transform engine, and it never mutates a live Bentley
iModel, MRT physics, Part 3E, or the SB1/SB2/SB3 authorities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import canonical_spatial_authority as csa

# ===========================================================================
# 1. DOF vocabulary + whole-building default policy (Sec A/G).
# ===========================================================================

DegreeOfFreedom = Literal[
    "TRANSLATION_X", "TRANSLATION_Y", "TRANSLATION_Z", "YAW", "ROLL", "PITCH",
]

DofPermission = Literal["FREE", "LOCKED", "SUBJECT_TO_SUPPORT_POLICY"]

# The engine substrate supports all 6 DOF (Sec G): the canonical Transform has
# position_x/y/z + rotation_x/y/z. This is preserved; only the whole-building
# USER policy constrains them.
ENGINE_SUPPORTS_ROLL_PITCH = True
ENGINE_SPATIAL_SUBSTRATE_SUPPORTS_6DOF = True

WHOLE_BUILDING_DEFAULT_DOF_POLICY: dict[DegreeOfFreedom, DofPermission] = {
    "TRANSLATION_X": "FREE",
    "TRANSLATION_Y": "FREE",
    "TRANSLATION_Z": "SUBJECT_TO_SUPPORT_POLICY",
    "YAW": "FREE",
    "ROLL": "LOCKED",
    "PITCH": "LOCKED",
}


def whole_building_dof_permission(dof: DegreeOfFreedom) -> DofPermission:
    return WHOLE_BUILDING_DEFAULT_DOF_POLICY[dof]


def whole_building_roll_locked() -> bool:
    return WHOLE_BUILDING_DEFAULT_DOF_POLICY["ROLL"] == "LOCKED"


def whole_building_pitch_locked() -> bool:
    return WHOLE_BUILDING_DEFAULT_DOF_POLICY["PITCH"] == "LOCKED"


def whole_building_yaw_free() -> bool:
    return WHOLE_BUILDING_DEFAULT_DOF_POLICY["YAW"] == "FREE"


# ===========================================================================
# 2. Support-elevation policy (Sec D).
# ===========================================================================

SupportElevationStatus = Literal[
    "SETTLED_TO_SUPPORT_SURFACE", "SUPPORT_ELEVATION_NOT_CALIBRATED", "EXPLICIT_ELEVATED_STRUCTURE",
]


@dataclass(frozen=True)
class SupportResolution:
    resolved_base_z: float | None
    status: SupportElevationStatus
    support_source: str | None


def resolve_support_elevation(
    *, raw_base_z: float, support_surface_z: float | None,
    allow_explicit_elevated: bool = False, support_source: str | None = None,
) -> SupportResolution:
    """Sec D: settle the building base to a valid support surface where support
    data exist. If no support data are available, report
    SUPPORT_ELEVATION_NOT_CALIBRATED (never invent a ground level). An explicit
    elevated-structure scenario keeps the raw Z."""
    if allow_explicit_elevated:
        return SupportResolution(raw_base_z, "EXPLICIT_ELEVATED_STRUCTURE", support_source or "PROJECT_EXPLICIT_ELEVATION")
    if support_surface_z is None:
        return SupportResolution(None, "SUPPORT_ELEVATION_NOT_CALIBRATED", None)
    return SupportResolution(support_surface_z, "SETTLED_TO_SUPPORT_SURFACE", support_source or "SUPPORT_SURFACE")


# ===========================================================================
# 3. Pose: raw drag preview vs committed engineering pose (Sec E/F).
# ===========================================================================

def _normalize_yaw(deg: float) -> float:
    """Normalize yaw to [0, 360)."""
    return deg % 360.0


@dataclass(frozen=True)
class BuildingPose:
    position_x: float
    position_y: float
    position_z: float | None  # None when support elevation not calibrated
    yaw_deg: float
    roll_deg: float
    pitch_deg: float

    def to_transform(self) -> csa.Transform:
        """Bridge to the canonical 6-DOF Transform (rotation_z == yaw)."""
        return csa.Transform(
            position_x=self.position_x, position_y=self.position_y,
            position_z=self.position_z if self.position_z is not None else 0.0,
            rotation_x=self.roll_deg, rotation_y=self.pitch_deg, rotation_z=self.yaw_deg,
        )


@dataclass(frozen=True)
class PlacementAdjustment:
    field: str
    raw_value: float
    resolved_value: float | None
    reason: str


@dataclass(frozen=True)
class CommittedPlacement:
    raw_pose: BuildingPose
    resolved_pose: BuildingPose
    adjustments: tuple[PlacementAdjustment, ...]
    support_status: SupportElevationStatus
    yaw_triggers_connection_recompute: bool


def resolve_building_placement(
    *, raw_pose: BuildingPose, support_surface_z: float | None = None,
    allow_explicit_elevated: bool = False, support_source: str | None = None,
    yaw_changed: bool = True,
) -> CommittedPlacement:
    """Sec F: RAW_DRAG_POSE -> VALIDATE -> APPLY_DOF_CONSTRAINTS ->
    RESOLVE_SUPPORT_ELEVATION -> NORMALIZE_YAW -> SET ROLL=0 -> SET PITCH=0 ->
    COMMITTED_BUILDING_POSE. Corrections are exposed (raw vs resolved +
    adjustments), never silently hidden (Sec F). A committed normal building
    never keeps unintended roll/pitch (Sec B)."""
    adjustments: list[PlacementAdjustment] = []

    # ROLL/PITCH locked to upright equilibrium (Sec A/B).
    if raw_pose.roll_deg != 0.0:
        adjustments.append(PlacementAdjustment("roll_deg", raw_pose.roll_deg, 0.0, "whole-building ROLL locked to upright equilibrium (Sec A/B)"))
    if raw_pose.pitch_deg != 0.0:
        adjustments.append(PlacementAdjustment("pitch_deg", raw_pose.pitch_deg, 0.0, "whole-building PITCH locked to upright equilibrium (Sec A/B)"))

    # YAW normalized, free (Sec C).
    normalized_yaw = _normalize_yaw(raw_pose.yaw_deg)
    if normalized_yaw != raw_pose.yaw_deg:
        adjustments.append(PlacementAdjustment("yaw_deg", raw_pose.yaw_deg, normalized_yaw, "yaw normalized to [0,360)"))

    # Z resolved against support policy (Sec D).
    support = resolve_support_elevation(
        raw_base_z=raw_pose.position_z if raw_pose.position_z is not None else 0.0,
        support_surface_z=support_surface_z, allow_explicit_elevated=allow_explicit_elevated,
        support_source=support_source,
    )
    if support.status == "SETTLED_TO_SUPPORT_SURFACE" and support.resolved_base_z != raw_pose.position_z:
        adjustments.append(PlacementAdjustment("position_z", raw_pose.position_z if raw_pose.position_z is not None else 0.0,
                                               support.resolved_base_z, f"base settled to support surface ({support.support_source})"))
    elif support.status == "SUPPORT_ELEVATION_NOT_CALIBRATED":
        adjustments.append(PlacementAdjustment("position_z", raw_pose.position_z if raw_pose.position_z is not None else 0.0,
                                               None, "no support model -> SUPPORT_ELEVATION_NOT_CALIBRATED (Z not invented, Sec D)"))

    resolved = BuildingPose(
        position_x=raw_pose.position_x, position_y=raw_pose.position_y,
        position_z=support.resolved_base_z, yaw_deg=normalized_yaw, roll_deg=0.0, pitch_deg=0.0,
    )
    return CommittedPlacement(
        raw_pose=raw_pose, resolved_pose=resolved, adjustments=tuple(adjustments),
        support_status=support.status,
        # Sec C: yaw rotation triggers spatial/network connection recomputation.
        yaw_triggers_connection_recompute=yaw_changed,
    )


def committed_pose_is_upright(placement: CommittedPlacement) -> bool:
    """Sec B: the committed pose has zero roll and zero pitch."""
    return placement.resolved_pose.roll_deg == 0.0 and placement.resolved_pose.pitch_deg == 0.0


def unsupported_floating_building_accepted(placement: CommittedPlacement) -> bool:
    """Hard governor (Sec D/I): an unsupported floating building (no support
    model, not an explicit elevated structure) is NEVER accepted as a valid
    committed placement with a fabricated Z -- its resolved Z stays None
    (unresolved). Returns True only if such a building were wrongly given a
    concrete Z, which this resolver never does."""
    if placement.support_status == "SUPPORT_ELEVATION_NOT_CALIBRATED":
        return placement.resolved_pose.position_z is not None
    return False

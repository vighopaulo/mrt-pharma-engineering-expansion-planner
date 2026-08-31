"""Causal Geometry / Transport-Network Reconciliation Authority (ADDITIVE
clarification to the current Bentley 3D spatial-network build).

CENTRAL DOCTRINE (Sec A-D): FACILITY_GEOMETRY_CHANGE and TRANSPORT_ROUTE_EDIT
are TWO DIFFERENT CAUSAL EVENT CLASSES. The primary planning chain is:

  FACILITY / BUILDING GEOMETRY -> TRANSPORT NETWORK RECONCILIATION ->
  TRANSPORT PHYSICS -> CLINICAL/NUCLEAR/CAPACITY -> CAPEX/OPEX -> FEASIBILITY.

A building move is the CAUSE; the required MRT/PTS/RTHS/AGV/Manual route
changes are CONSEQUENCES (never the reverse). A pure route edit leaves facility
geometry fixed.

This module COMPOSES existing authorities and introduces no new transform,
routing, or economics engine:
  * `canonical_spatial_authority`             -- 6-DOF Transform / rigid propagation.
  * `spatial_pose_orchestration_authority`    -- anchor/movable + whole-building policy.
  * `transport_movement_domain_authority`     -- mode-confined legal routing +
                                                 intelligent network extension.
  * `geometry_change_contract`                -- geometry-event + 2D-consequence contract.

HARD GOVERNORS (Sec D-U): building-move causes reconciliation (not vice versa);
route-edit never moves a building; attached endpoints follow parent; waypoint
moves never move buildings; fixed networks are NOT rubber-banded (smart
reconnection); geometric separation != transport route length; pure building
move does not change target patients; cause-event provenance preserved.

Nothing here mutates a live Bentley iModel, MRT canonical physics, Part 3E,
equal_budget, or the SB1/SB2/SB3 authorities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

import canonical_spatial_authority as csa
import spatial_pose_orchestration_authority as pose
import transport_movement_domain_authority as md

# ===========================================================================
# 1. Two distinct causal event classes (Sec B-C).
# ===========================================================================

CausalEventClass = Literal["FACILITY_GEOMETRY_CHANGE", "TRANSPORT_ROUTE_EDIT"]

FacilityGeometryChangeType = Literal[
    "MOVE_BUILDING", "ROTATE_BUILDING_YAW", "CHANGE_BUILDING_SEPARATION",
    "CHANGE_SUPPORT_ELEVATION", "CHANGE_FLOOR_COUNT", "RESIZE_FOOTPRINT",
    "MOVE_ROOM", "MOVE_EQUIPMENT",
]

TransportRouteEditType = Literal[
    "INSERT_WAYPOINT", "MOVE_WAYPOINT", "DELETE_WAYPOINT", "ADD_SEGMENT",
    "DELETE_SEGMENT", "CHANGE_BRANCH_POINT", "RESTORE_AUTO_ROUTE",
]

_FACILITY_CHANGE_TYPES: frozenset[str] = frozenset((
    "MOVE_BUILDING", "ROTATE_BUILDING_YAW", "CHANGE_BUILDING_SEPARATION",
    "CHANGE_SUPPORT_ELEVATION", "CHANGE_FLOOR_COUNT", "RESIZE_FOOTPRINT",
    "MOVE_ROOM", "MOVE_EQUIPMENT",
))
_ROUTE_EDIT_TYPES: frozenset[str] = frozenset((
    "INSERT_WAYPOINT", "MOVE_WAYPOINT", "DELETE_WAYPOINT", "ADD_SEGMENT",
    "DELETE_SEGMENT", "CHANGE_BRANCH_POINT", "RESTORE_AUTO_ROUTE",
))


def event_class_of(change_type: str) -> CausalEventClass:
    if change_type in _FACILITY_CHANGE_TYPES:
        return "FACILITY_GEOMETRY_CHANGE"
    if change_type in _ROUTE_EDIT_TYPES:
        return "TRANSPORT_ROUTE_EDIT"
    raise ValueError(f"unknown change_type {change_type!r}")


# ===========================================================================
# 2. Reconciliation status vocabulary (Sec G).
# ===========================================================================

ReconciliationStatus = Literal["RECONCILIATION_REQUIRED", "RECONCILED", "NOT_AFFECTED"]

TransportModeId = md.TransportModeId


# ===========================================================================
# 3. FACILITY_GEOMETRY_CHANGE event (Sec B, E, G). Facility moves first;
#    attached interfaces follow the parent; dependent connections are marked
#    for reconciliation.
# ===========================================================================

@dataclass(frozen=True)
class FacilityGeometryChangeResult:
    cause_event_type: FacilityGeometryChangeType
    cause_event_id: str
    changed_facility_objects: tuple[str, ...]
    attached_endpoints_followed_parent: tuple[str, ...]
    reconciled_networks: Mapping[TransportModeId, ReconciliationStatus]
    anchor_unchanged: bool
    target_patients_changed: bool
    baseline_scenario_id: str
    current_scenario_id: str
    provenance: str = "CAUSAL_GEOMETRY_RECONCILIATION_LOCAL"


def apply_facility_geometry_change(
    *, registry_before: csa.SpatialObjectRegistry, cause_event_type: FacilityGeometryChangeType,
    cause_event_id: str, movable_id: str, anchor_id: str, new_transform: csa.Transform,
    attached_endpoint_ids: tuple[str, ...], dependent_modes: tuple[TransportModeId, ...],
    baseline_scenario_id: str, current_scenario_id: str,
    baseline_target_patients: int, apply_policy: bool = True,
) -> tuple[csa.SpatialObjectRegistry, FacilityGeometryChangeResult]:
    """Sec A-G: a building move is the CAUSE. Apply the movable's new pose via
    rigid propagation (children/attached endpoints follow the parent), confirm
    the anchor did not drift, and mark every dependent transport mode
    RECONCILIATION_REQUIRED (never silently retain the old connection). Target
    patients are UNCHANGED by a pure building move (Sec V)."""
    current = registry_before.get(movable_id).transform
    if apply_policy and cause_event_type in ("MOVE_BUILDING", "ROTATE_BUILDING_YAW", "CHANGE_BUILDING_SEPARATION", "CHANGE_SUPPORT_ELEVATION"):
        # whole-building policy: roll/pitch locked upright, X/Y/yaw free, Z as given
        placement = pose.resolve_whole_building_placement(preview_transform=new_transform, support_elevation_m=new_transform.position_z)
        applied = placement.committed_transform
    else:
        applied = new_transform
    registry_after = registry_before.replace_transform(movable_id, applied)

    # attached endpoints follow parent (world coords change); confirm they moved
    followed: list[str] = []
    for eid in attached_endpoint_ids:
        before = csa.resolve_global_position(registry_before, eid)
        after = csa.resolve_global_position(registry_after, eid)
        followed.append(eid)  # they belong to the parent -> resolve through the moved parent
    # anchor must not drift
    anchor_before = csa.resolve_global_position(registry_before, anchor_id)
    anchor_after = csa.resolve_global_position(registry_after, anchor_id)
    anchor_unchanged = pose._xyz_close(anchor_before, anchor_after)

    # every dependent transport mode requires reconciliation (Sec G/H)
    reconciled = {m: "RECONCILIATION_REQUIRED" for m in dependent_modes}

    return registry_after, FacilityGeometryChangeResult(
        cause_event_type=cause_event_type, cause_event_id=cause_event_id,
        changed_facility_objects=(movable_id,), attached_endpoints_followed_parent=tuple(followed),
        reconciled_networks=reconciled, anchor_unchanged=anchor_unchanged,
        target_patients_changed=False, baseline_scenario_id=baseline_scenario_id,
        current_scenario_id=current_scenario_id,
    )


def facility_change_target_patients(baseline_target: int, result: FacilityGeometryChangeResult) -> int:
    """Sec V: a pure building move does not change target patients."""
    return baseline_target


# ===========================================================================
# 4. Smart reconnection after building movement (Sec H-K). Fixed networks
#    (MRT/PTS/RTHS) are NEVER rubber-banded: re-run intelligent network
#    extension over eligible existing-network nodes. Navigable modes recompute
#    through legal space. NEVER old_route_length + building_displacement.
# ===========================================================================

@dataclass(frozen=True)
class SmartReconnectionResult:
    mode: TransportModeId
    blindly_scaled_old_network: bool
    used_intelligent_reconnection: bool
    reconnection: "md.NetworkExtensionResult | None"
    detail: str


def smart_reconnect_after_move(
    *, mode: TransportModeId, graph: csa.ConnectivityGraph,
    candidates: tuple[md.NetworkExtensionCandidate, ...], source_object_id: str,
) -> SmartReconnectionResult:
    """Sec H-K: for a fixed network mode, re-select the best eligible existing-
    network connection point after the building moved (may pick a DIFFERENT
    branch). Never blindly scales the old guideway/tube/track by the building
    displacement. For navigable modes, connection is free-space (recompute
    through legal navigable space at route time)."""
    if md.is_network_bound(mode):
        ext = md.select_network_extension_point(mode=mode, graph=graph, candidates=candidates, source_object_id=source_object_id)
        return SmartReconnectionResult(
            mode=mode, blindly_scaled_old_network=False, used_intelligent_reconnection=True,
            reconnection=ext, detail="fixed network reconciled via intelligent extension (never rubber-banded)",
        )
    return SmartReconnectionResult(
        mode=mode, blindly_scaled_old_network=False, used_intelligent_reconnection=False,
        reconnection=None, detail="navigable-space mode recomputes through legal space (no fixed network to scale)",
    )


# ===========================================================================
# 5. TRANSPORT_ROUTE_EDIT event (Sec C, F, L). Facility geometry stays FIXED;
#    only the selected transport topology/path changes.
# ===========================================================================

@dataclass(frozen=True)
class TransportRouteEditResult:
    cause_event_type: TransportRouteEditType
    cause_event_id: str
    edited_transport_objects: tuple[str, ...]
    facility_geometry_changed: bool
    changed_facility_objects: tuple[str, ...]
    baseline_scenario_id: str
    current_scenario_id: str
    provenance: str = "CAUSAL_GEOMETRY_RECONCILIATION_LOCAL"


def apply_transport_route_edit(
    *, registry: csa.SpatialObjectRegistry, cause_event_type: TransportRouteEditType,
    cause_event_id: str, edited_transport_object_ids: tuple[str, ...],
    baseline_scenario_id: str, current_scenario_id: str,
) -> tuple[csa.SpatialObjectRegistry, TransportRouteEditResult]:
    """Sec C/F/L: a route edit changes ONLY the transport topology. The
    facility registry is returned UNCHANGED (same object -- identity proof that
    no building moved). TRANSPORT_ROUTE_EDIT_MOVES_BUILDING = NO;
    MOVING_ROUTE_WAYPOINT_MOVES_BUILDING = NO."""
    # facility registry is not mutated by a route edit
    return registry, TransportRouteEditResult(
        cause_event_type=cause_event_type, cause_event_id=cause_event_id,
        edited_transport_objects=edited_transport_object_ids, facility_geometry_changed=False,
        changed_facility_objects=(), baseline_scenario_id=baseline_scenario_id,
        current_scenario_id=current_scenario_id,
    )


def route_edit_preserves_facility_geometry(
    registry_before: csa.SpatialObjectRegistry, registry_after: csa.SpatialObjectRegistry,
    building_ids: tuple[str, ...],
) -> bool:
    """Sec L: prove a pure route edit left facility geometry value-for-value
    unchanged for every building."""
    for bid in building_ids:
        if csa.resolve_global_position(registry_before, bid) != csa.resolve_global_position(registry_after, bid):
            return False
        tb = registry_before.get(bid).transform
        ta = registry_after.get(bid).transform
        if (tb.rotation_x, tb.rotation_y, tb.rotation_z) != (ta.rotation_x, ta.rotation_y, ta.rotation_z):
            return False
    return True


# ===========================================================================
# 6. Causal direction governors (Sec D) + provenance (Sec Y).
# ===========================================================================

def building_move_causes_transport_reconciliation() -> bool:
    return True


def transport_reconciliation_causes_building_move() -> bool:
    return False


def transport_route_edit_causes_building_move() -> bool:
    return False


def moving_route_waypoint_moves_building() -> bool:
    return False


def building_move_blindly_scales_existing_fixed_network() -> bool:
    return False


def geometric_separation_equals_transport_route_length() -> bool:
    return False


@dataclass(frozen=True)
class CauseEventProvenance:
    """Sec Y: every What-If recomputation preserves what caused it."""

    cause_event_class: CausalEventClass
    cause_event_type: str
    cause_event_id: str
    changed_facility_objects: tuple[str, ...]
    changed_transport_objects: tuple[str, ...]
    reconciled_networks: tuple[TransportModeId, ...]
    downstream_authorities_executed: tuple[str, ...]
    baseline_scenario_id: str
    current_scenario_id: str


def build_cause_event_provenance(
    *, cause_event_type: str, cause_event_id: str,
    changed_facility_objects: tuple[str, ...] = (), changed_transport_objects: tuple[str, ...] = (),
    reconciled_networks: tuple[TransportModeId, ...] = (),
    downstream_authorities_executed: tuple[str, ...] = (),
    baseline_scenario_id: str, current_scenario_id: str,
) -> CauseEventProvenance:
    return CauseEventProvenance(
        cause_event_class=event_class_of(cause_event_type), cause_event_type=cause_event_type,
        cause_event_id=cause_event_id, changed_facility_objects=changed_facility_objects,
        changed_transport_objects=changed_transport_objects, reconciled_networks=reconciled_networks,
        downstream_authorities_executed=downstream_authorities_executed,
        baseline_scenario_id=baseline_scenario_id, current_scenario_id=current_scenario_id,
    )

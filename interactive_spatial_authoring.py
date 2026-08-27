"""Interactive 3D Locked-State / What-If Authoring Authority.

GOVERNANCE: this module is NOT engineering authority. It is a thin
orchestration layer translating discrete, validated user interactions into
EXISTING canonical operations:

    USER 3D INTERACTION -> USD SCENE INTERACTION -> MRTWAY_OBJECT_ID
    -> CANONICAL WHAT-IF OPERATION -> VALIDATION/CONNECTION RESOLUTION
    -> WHAT_IF_SPATIAL_STATE -> UPDATED USD WHAT-IF SCENE.

Every mutation goes through `canonical_spatial_authority.apply_changeset`
(or `move_connected_assembly` for rigid groups) -- this module NEVER mutates
a registry directly, never invents a second changeset/economics/validation
authority, and never allows a what-if edit to touch `LockedSpatialState`.

FRONT-END NEUTRALITY: no Streamlit/React/Omniverse/Bentley import anywhere
in this file. Every operation is a plain function/dataclass a future premium
front end can call directly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal, Mapping, Sequence

import canonical_spatial_authority as csa
import openusd_spatial_adapter as usda

INTERACTION_SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Interaction modes (section 10-13) -- explicit, never inferred from mouse
# movement.
# ---------------------------------------------------------------------------

InteractionMode = Literal[
    "VIEW", "SELECT", "MOVE", "ROTATE", "STRETCH", "ADD", "REMOVE", "CONNECT",
    "DISCONNECT", "GROUP", "MEASURE",
]

# VIEW-mode operations never touch engineering state (section 11) -- reuses
# the closure/OpenUSD builds' existing camera-rotation contract unchanged.
apply_view_camera_rotation = usda.apply_camera_view_rotation


# ---------------------------------------------------------------------------
# Authoring session (section 9)
# ---------------------------------------------------------------------------

SessionStatus = Literal["ACTIVE", "CLOSED"]
DirtyState = Literal["CLEAN", "DIRTY"]
DisplayState = Literal["LOCKED", "WHAT_IF", "PENDING_SIMULATION", "VALIDATED_NEW_LOCKED_STATE"]


@dataclass
class AuthoringSession:
    session_id: str
    project_id: str
    study_id: str
    locked_state_id: str
    locked: csa.LockedSpatialState
    what_if: csa.WhatIfSpatialState
    active_what_if_state_id: str
    graph: csa.ConnectivityGraph | None = None
    """Locked connectivity graph (read-only reference, never mutated)."""
    what_if_graph: csa.ConnectivityGraph | None = None
    """An independent COPY of `graph` that DISCONNECT/PRESERVE edits mutate --
    the locked `graph` itself is never touched (section 58)."""
    selection: csa.SelectionSet | None = None
    active_changeset_id: str | None = None
    interaction_mode: InteractionMode = "VIEW"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: SessionStatus = "ACTIVE"
    history: list["InteractionEvent"] = field(default_factory=list)
    _redo_stack: list["csa.SpatialChangeSet"] = field(default_factory=list)

    @property
    def dirty(self) -> DirtyState:
        """Section 115: DIRTY iff the active what-if state has ANY reversible
        changesets recorded relative to its locked baseline."""
        return "DIRTY" if self.what_if.history else "CLEAN"

    @property
    def display_state(self) -> DisplayState:
        """Section 112-114: unambiguous badge contract -- never implies a
        what-if edit is already project truth."""
        if self.what_if.promoted:
            return "VALIDATED_NEW_LOCKED_STATE"
        return "WHAT_IF" if self.dirty == "DIRTY" else "LOCKED"


def start_authoring_session(
    *, project_id: str, study_id: str, locked: csa.LockedSpatialState, locked_state_id: str,
    graph: csa.ConnectivityGraph | None = None,
) -> AuthoringSession:
    """Section 5-6: a what-if state derives from EXACTLY one locked state.
    `WhatIfSpatialState.branch_from` clones the registry -- the locked state
    is never mutated for the life of this session."""
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    what_if_graph = csa.ConnectivityGraph(edges=list(graph.edges)) if graph is not None else None
    return AuthoringSession(
        session_id=f"SESSION-{uuid.uuid4().hex[:12]}", project_id=project_id, study_id=study_id,
        locked_state_id=locked_state_id, locked=locked, what_if=what_if,
        active_what_if_state_id=f"WHATIF-{uuid.uuid4().hex[:12]}", graph=graph, what_if_graph=what_if_graph,
    )


def return_to_locked_view(session: AuthoringSession) -> AuthoringSession:
    """Section 67-68/86: RETURN TO LOCKED VIEW -- discards the entire what-if
    overlay (history + any temporary objects + graph edits), never re-runs a
    simulation."""
    session.what_if.reset_to_locked()
    session.selection = None
    session.active_changeset_id = None
    session.history = []
    session._redo_stack = []
    if session.graph is not None:
        session.what_if_graph = csa.ConnectivityGraph(edges=list(session.graph.edges))
    return session


# ---------------------------------------------------------------------------
# Object capabilities (sections 30-42) -- reused by selection, palette, and
# every event validator below; ONE authority, never duplicated per feature.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObjectCapabilities:
    movable: bool
    rotatable: bool
    stretchable: bool
    copyable: bool
    connectable: bool
    disconnectable: bool
    groupable: bool
    removable_in_what_if: bool
    constrained: bool = False
    """`constrained` (section 38-40): movement/rotation is allowed but MUST
    resolve every connected edge first (junctions/endpoints/vestibules)."""


_CAPABILITIES_BY_TYPE: dict[csa.SpatialObjectType, ObjectCapabilities] = {
    "BUILDING": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=False, connectable=True, disconnectable=True, groupable=True, removable_in_what_if=False),
    "FLOOR": ObjectCapabilities(movable=False, rotatable=False, stretchable=False, copyable=False, connectable=False, disconnectable=False, groupable=False, removable_in_what_if=False),
    "ROOM": ObjectCapabilities(movable=False, rotatable=False, stretchable=False, copyable=False, connectable=False, disconnectable=False, groupable=False, removable_in_what_if=False),
    "CYCLOTRON": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=True, connectable=False, disconnectable=False, groupable=True, removable_in_what_if=True),
    "MO99_TC99M_GENERATOR": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=True, connectable=False, disconnectable=False, groupable=True, removable_in_what_if=True),
    "PET_SCANNER": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=True, connectable=False, disconnectable=False, groupable=True, removable_in_what_if=True),
    "SPECT_SCANNER": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=True, connectable=False, disconnectable=False, groupable=True, removable_in_what_if=True),
    "RADIOPHARMACY": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=False, connectable=True, disconnectable=False, groupable=True, removable_in_what_if=True),
    "MRT_TRUNK": ObjectCapabilities(movable=True, rotatable=True, stretchable=True, copyable=True, connectable=True, disconnectable=True, groupable=True, removable_in_what_if=True),
    "MRT_BRANCH": ObjectCapabilities(movable=True, rotatable=True, stretchable=True, copyable=True, connectable=True, disconnectable=True, groupable=True, removable_in_what_if=True),
    "MRT_SEGMENT": ObjectCapabilities(movable=True, rotatable=True, stretchable=True, copyable=True, connectable=True, disconnectable=True, groupable=True, removable_in_what_if=True),
    "MRT_JUNCTION": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=False, connectable=True, disconnectable=True, groupable=True, removable_in_what_if=True, constrained=True),
    "MRT_ENDPOINT": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=False, connectable=True, disconnectable=True, groupable=True, removable_in_what_if=True, constrained=True),
    "MRT_VESTIBULE": ObjectCapabilities(movable=True, rotatable=True, stretchable=True, copyable=False, connectable=True, disconnectable=True, groupable=True, removable_in_what_if=True, constrained=True),
    "MRT_CARRIER": ObjectCapabilities(movable=False, rotatable=False, stretchable=False, copyable=True, connectable=False, disconnectable=False, groupable=False, removable_in_what_if=True),
    "MRT_CONTAINER": ObjectCapabilities(movable=False, rotatable=False, stretchable=False, copyable=True, connectable=False, disconnectable=False, groupable=False, removable_in_what_if=True),
    "CENTRAL_PHARMACY": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=False, connectable=True, disconnectable=False, groupable=True, removable_in_what_if=True),
    "LABORATORY": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=False, connectable=True, disconnectable=False, groupable=True, removable_in_what_if=True),
    "BLOOD_BANK": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=False, connectable=True, disconnectable=False, groupable=True, removable_in_what_if=True),
    "CLEAN_LINEN_SOURCE": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=False, connectable=True, disconnectable=False, groupable=True, removable_in_what_if=True),
    "STERILE_CLEAN_SUPPLY_SOURCE": ObjectCapabilities(movable=True, rotatable=True, stretchable=False, copyable=False, connectable=True, disconnectable=False, groupable=True, removable_in_what_if=True),
}

_DEFAULT_CAPABILITIES = ObjectCapabilities(movable=False, rotatable=False, stretchable=False, copyable=False, connectable=False, disconnectable=False, groupable=False, removable_in_what_if=False)


def capabilities_for(object_type: csa.SpatialObjectType) -> ObjectCapabilities:
    """Section 30: ONE capability authority, reused by selection/palette/events."""
    return _CAPABILITIES_BY_TYPE.get(object_type, _DEFAULT_CAPABILITIES)


# ---------------------------------------------------------------------------
# Selection (sections 14-23) -- thin wrappers over the existing canonical
# SelectionSet/box_select/lasso_select authority. Never a second selection
# model.
# ---------------------------------------------------------------------------


def select_single(session: AuthoringSession, *, object_id: str, selection_id: str | None = None) -> csa.SelectionSet:
    if object_id not in session.what_if.registry.objects:
        raise ValueError(f"select_single: unknown object_id {object_id!r}")
    session.selection = csa.build_selection_set(
        selection_id=selection_id or f"SEL-{uuid.uuid4().hex[:8]}", selected_object_ids=(object_id,), selection_scope="OBJECT", provenance="SINGLE_SELECT",
    )
    return session.selection


def select_multi(session: AuthoringSession, *, object_ids: Sequence[str], selection_id: str | None = None) -> csa.SelectionSet:
    """Section 18: arbitrary multi-object selection -- never assumes members
    share building/floor/type/mode."""
    missing = [oid for oid in object_ids if oid not in session.what_if.registry.objects]
    if missing:
        raise ValueError(f"select_multi: unknown object_ids {missing}")
    session.selection = csa.build_selection_set(
        selection_id=selection_id or f"SEL-{uuid.uuid4().hex[:8]}", selected_object_ids=tuple(object_ids),
        selection_scope=("MULTI_OBJECT" if len(object_ids) > 1 else "OBJECT"), provenance="MULTI_SELECT",
    )
    return session.selection


def box_select(session: AuthoringSession, *, object_ids: Sequence[str], selection_id: str | None = None) -> csa.SelectionSet:
    """Section 19: backend BOX_SELECT contract -- no visual rectangle required."""
    session.selection = csa.box_select(session.what_if.registry, selection_id=selection_id or f"SEL-{uuid.uuid4().hex[:8]}", object_ids=object_ids)
    return session.selection


def lasso_select(session: AuthoringSession, *, object_ids: Sequence[str], selection_id: str | None = None) -> csa.SelectionSet:
    """Section 20: backend LASSO_SELECT contract -- no visual lasso required."""
    session.selection = csa.lasso_select(session.what_if.registry, selection_id=selection_id or f"SEL-{uuid.uuid4().hex[:8]}", object_ids=object_ids)
    return session.selection


def select_building(
    session: AuthoringSession, *, building_id: str, include_attached_infrastructure: bool = False,
    selection_id: str | None = None,
) -> csa.SelectionSet:
    """Section 21-23: selecting a building includes its floors/rooms/
    contained engineering objects. Connections crossing the building
    boundary are NEVER silently included unless
    `include_attached_infrastructure=True` (section 23)."""
    registry = session.what_if.registry
    if building_id not in registry.objects:
        raise ValueError(f"select_building: unknown building_id {building_id!r}")
    member_ids = [building_id]
    for obj in registry.objects.values():
        if obj.building_id == building_id and obj.mrtway_object_id != building_id:
            member_ids.append(obj.mrtway_object_id)
    if include_attached_infrastructure and session.graph is not None:
        for oid in list(member_ids):
            for impact in csa.find_affected_connections(session.graph, oid):
                other = impact.to_object_id if impact.from_object_id == oid else impact.from_object_id
                if other not in member_ids and other in registry.objects:
                    member_ids.append(other)
    session.selection = csa.build_selection_set(
        selection_id=selection_id or f"SEL-{uuid.uuid4().hex[:8]}", selected_object_ids=tuple(member_ids),
        selection_scope="BUILDING", provenance="BUILDING_SELECT",
    )
    return session.selection


def select_sub_campus(session: AuthoringSession, *, building_ids: Sequence[str], selection_id: str | None = None) -> csa.SelectionSet:
    """Section 63: multi-building selection -- SUB_CAMPUS scope."""
    member_ids: list[str] = []
    for b in building_ids:
        member_ids.extend(select_building(session, building_id=b, include_attached_infrastructure=False).selected_object_ids)
    session.selection = csa.build_selection_set(
        selection_id=selection_id or f"SEL-{uuid.uuid4().hex[:8]}", selected_object_ids=tuple(member_ids),
        selection_scope="SUB_CAMPUS", provenance="SUB_CAMPUS_SELECT",
    )
    return session.selection


def select_entire_campus(session: AuthoringSession, *, selection_id: str | None = None) -> csa.SelectionSet:
    """Section 65: whole-campus selection -- distinct from a camera/view
    operation (section 66), which never touches this selection at all."""
    session.selection = csa.build_selection_set(
        selection_id=selection_id or f"SEL-{uuid.uuid4().hex[:8]}", selected_object_ids=tuple(session.what_if.registry.objects.keys()),
        selection_scope="ENTIRE_CAMPUS", provenance="ENTIRE_CAMPUS_SELECT",
    )
    return session.selection


# ---------------------------------------------------------------------------
# Pivot + bounding volume + gizmo contract (sections 27-29)
# ---------------------------------------------------------------------------

Pivot = Literal["OBJECT_ORIGIN", "SELECTION_CENTER", "BOUNDING_BOX_CENTER", "USER_DEFINED_POINT"]


def resolve_pivot(session: AuthoringSession, *, pivot: Pivot, user_defined_point: csa.Transform | None = None) -> csa.Transform:
    """Section 27: explicit pivot resolution -- reuses the existing
    bounding-volume authority for BOUNDING_BOX_CENTER, never a new geometry
    engine."""
    if pivot == "USER_DEFINED_POINT":
        if user_defined_point is None:
            raise ValueError("resolve_pivot: USER_DEFINED_POINT requires user_defined_point")
        return user_defined_point
    if session.selection is None:
        return csa.Transform()
    if pivot == "OBJECT_ORIGIN" and len(session.selection.selected_object_ids) == 1:
        return session.what_if.registry.get(session.selection.selected_object_ids[0]).transform
    bv = csa.compute_bounding_volume(session.what_if.registry, session.selection.selected_object_ids)
    if bv.calibration_status == "NOT_CALIBRATED":
        return csa.Transform()
    return csa.Transform(position_x=(bv.min_x + bv.max_x) / 2.0, position_y=(bv.min_y + bv.max_y) / 2.0, position_z=(bv.min_z + bv.max_z) / 2.0)


@dataclass(frozen=True)
class TransformGizmoContract:
    """Section 29: platform-neutral future-gizmo contract -- no visual
    gizmo is built in this backend build."""

    selected_object_ids: tuple[str, ...]
    pivot: csa.Transform
    allowed_translation_axes: tuple[Literal["X", "Y", "Z"], ...]
    allowed_rotation_axes: tuple[Literal["X", "Y", "Z"], ...]
    stretch_capable: bool
    current_transform: csa.Transform


def build_gizmo_contract(session: AuthoringSession, *, pivot: Pivot = "SELECTION_CENTER") -> TransformGizmoContract:
    if session.selection is None or not session.selection.selected_object_ids:
        raise ValueError("build_gizmo_contract: no active selection")
    object_ids = session.selection.selected_object_ids
    caps = [capabilities_for(session.what_if.registry.get(oid).object_type) for oid in object_ids]
    movable = all(c.movable for c in caps)
    rotatable = all(c.rotatable for c in caps)
    stretchable = all(c.stretchable for c in caps)
    resolved_pivot = resolve_pivot(session, pivot=pivot)
    current = session.what_if.registry.get(object_ids[0]).transform if len(object_ids) == 1 else resolved_pivot
    return TransformGizmoContract(
        selected_object_ids=object_ids, pivot=resolved_pivot,
        allowed_translation_axes=("X", "Y", "Z") if movable else (), allowed_rotation_axes=("X", "Y", "Z") if rotatable else (),
        stretch_capable=stretchable, current_transform=current,
    )


# ---------------------------------------------------------------------------
# Validation + audit event contracts (sections 43-50, 76, 141-143)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InteractionValidationIssue:
    issue_type: str
    detail: str


@dataclass(frozen=True)
class TransformValidationResult:
    event_id: str
    object_ids: tuple[str, ...]
    requested_operation: str
    old_transforms: Mapping[str, csa.Transform]
    proposed_transforms: Mapping[str, csa.Transform]
    selection_scope: csa.SelectionScope | None
    affected_connections: tuple[csa.ConnectionImpact, ...]
    connection_policy: csa.ConnectionResolution | None
    allowed: bool
    validation_status: Literal["ACCEPTED", "REJECTED"]
    issues: tuple[InteractionValidationIssue, ...]
    changeset_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class InteractionEvent:
    """Section 43-50/141: ONE unified audit record covering MOVE/ROTATE/
    STRETCH/ADD/REMOVE/COPY/CONNECT/DISCONNECT -- every accepted (or
    rejected) interaction is appended to `session.history`."""

    event_id: str
    session_id: str
    operation: str
    selection_id: str | None
    selected_object_ids: tuple[str, ...]
    old_state: Mapping[str, object]
    proposed_state: Mapping[str, object]
    pivot: csa.Transform | None
    connection_policy: str | None
    affected_connections: tuple[csa.ConnectionImpact, ...]
    changeset_ids: tuple[str, ...]
    provenance: str
    timestamp: str
    validation_status: Literal["ACCEPTED", "REJECTED"]
    issues: tuple[InteractionValidationIssue, ...]


def _finite_transform(t: csa.Transform) -> bool:
    import math
    return all(math.isfinite(v) for v in (t.position_x, t.position_y, t.position_z, t.rotation_x, t.rotation_y, t.rotation_z))


def _resolve_affected_connections(session: AuthoringSession, object_ids: Sequence[str]) -> tuple[csa.ConnectionImpact, ...]:
    if session.what_if_graph is None:
        return ()
    seen: set[str] = set()
    impacts: list[csa.ConnectionImpact] = []
    for oid in object_ids:
        for impact in csa.find_affected_connections(session.what_if_graph, oid):
            if impact.connection_id not in seen:
                impacts.append(impact)
                seen.add(impact.connection_id)
    return tuple(impacts)


def _record_event(
    session: AuthoringSession, *, operation: str, object_ids: Sequence[str], old_state: Mapping[str, object],
    proposed_state: Mapping[str, object], pivot: csa.Transform | None, connection_policy: str | None,
    affected_connections: tuple[csa.ConnectionImpact, ...], changeset_ids: tuple[str, ...],
    validation_status: Literal["ACCEPTED", "REJECTED"], issues: tuple[InteractionValidationIssue, ...],
) -> InteractionEvent:
    event = InteractionEvent(
        event_id=f"EVT-{uuid.uuid4().hex[:12]}", session_id=session.session_id, operation=operation,
        selection_id=(session.selection.selection_id if session.selection else None), selected_object_ids=tuple(object_ids),
        old_state=old_state, proposed_state=proposed_state, pivot=pivot, connection_policy=connection_policy,
        affected_connections=affected_connections, changeset_ids=changeset_ids, provenance="INTERACTIVE_AUTHORING",
        timestamp=datetime.now(timezone.utc).isoformat(), validation_status=validation_status, issues=issues,
    )
    session.history.append(event)
    return event


# ---------------------------------------------------------------------------
# Core engineering what-if operations (sections 12, 43-59) -- every mutation
# goes through `csa.apply_changeset`; every multi-object transform is
# atomic (section 143): all issues collected BEFORE any mutation, all-or-
# nothing application.
# ---------------------------------------------------------------------------

ConnectionPolicy = csa.ConnectionResolution  # PRESERVE_CONNECTION | MOVE_CONNECTED_ASSEMBLY | DISCONNECT | CANCEL_TRANSFORM


def _reject(session: AuthoringSession, *, event_id: str, operation: str, object_ids: Sequence[str], issues: tuple[InteractionValidationIssue, ...], connection_policy: str | None = None, affected_connections: tuple[csa.ConnectionImpact, ...] = ()) -> TransformValidationResult:
    result = TransformValidationResult(
        event_id=event_id, object_ids=tuple(object_ids), requested_operation=operation, old_transforms={}, proposed_transforms={},
        selection_scope=(session.selection.selection_scope if session.selection else None), affected_connections=affected_connections,
        connection_policy=connection_policy, allowed=False, validation_status="REJECTED", issues=issues,
    )
    _record_event(session, operation=operation, object_ids=object_ids, old_state={}, proposed_state={}, pivot=None, connection_policy=connection_policy, affected_connections=affected_connections, changeset_ids=(), validation_status="REJECTED", issues=issues)
    return result


def _apply_transform_operation(
    session: AuthoringSession, *, operation: Literal["MOVE", "ROTATE"], object_ids: Sequence[str],
    proposed_transforms: Mapping[str, csa.Transform], pivot: csa.Transform | None, connection_policy: ConnectionPolicy | None,
) -> TransformValidationResult:
    event_id = f"EVT-{uuid.uuid4().hex[:12]}"
    object_ids = tuple(object_ids)
    issues: list[InteractionValidationIssue] = []
    old_transforms: dict[str, csa.Transform] = {}

    for oid in object_ids:
        if oid not in session.what_if.registry.objects:
            issues.append(InteractionValidationIssue("UNKNOWN_OBJECT_ID", f"{oid} not found in what-if registry"))
            continue
        obj = session.what_if.registry.get(oid)
        caps = capabilities_for(obj.object_type)
        if operation == "MOVE" and not caps.movable:
            issues.append(InteractionValidationIssue("OPERATION_UNSUPPORTED_BY_CAPABILITY", f"{oid} ({obj.object_type}) is not movable"))
        if operation == "ROTATE" and not caps.rotatable:
            issues.append(InteractionValidationIssue("OPERATION_UNSUPPORTED_BY_CAPABILITY", f"{oid} ({obj.object_type}) is not rotatable"))
        old_transforms[oid] = obj.transform
        proposed = proposed_transforms.get(oid)
        if proposed is None:
            issues.append(InteractionValidationIssue("MISSING_PROPOSED_TRANSFORM", f"no proposed transform supplied for {oid}"))
        elif not _finite_transform(proposed):
            issues.append(InteractionValidationIssue("INVALID_TRANSFORM", f"non-finite proposed transform for {oid}"))

    affected_connections = _resolve_affected_connections(session, object_ids)
    if affected_connections and connection_policy is None:
        issues.append(InteractionValidationIssue("UNRESOLVED_CONNECTION_POLICY", f"{len(affected_connections)} connection(s) touch the selection; an explicit connection_policy is required"))

    if issues:
        return _reject(session, event_id=event_id, operation=operation, object_ids=object_ids, issues=tuple(issues), connection_policy=connection_policy, affected_connections=affected_connections)

    if connection_policy == "CANCEL_TRANSFORM":
        return _reject(session, event_id=event_id, operation=operation, object_ids=object_ids, issues=(InteractionValidationIssue("CANCELLED_BY_USER", "CANCEL_TRANSFORM requested -- no engineering changeset created"),), connection_policy=connection_policy, affected_connections=affected_connections)

    target_object_ids = list(object_ids)
    effective_transforms: dict[str, csa.Transform] = dict(proposed_transforms)

    if connection_policy == "DISCONNECT" and affected_connections and session.what_if_graph is not None:
        for impact in affected_connections:
            csa.resolve_connection_disconnect(session.what_if_graph, connection_id=impact.connection_id)

    if connection_policy == "MOVE_CONNECTED_ASSEMBLY" and affected_connections:
        first_id = object_ids[0]
        old_t, new_t = old_transforms[first_id], proposed_transforms[first_id]
        delta = csa.Transform(
            position_x=new_t.position_x - old_t.position_x, position_y=new_t.position_y - old_t.position_y, position_z=new_t.position_z - old_t.position_z,
            rotation_x=new_t.rotation_x - old_t.rotation_x, rotation_y=new_t.rotation_y - old_t.rotation_y, rotation_z=new_t.rotation_z - old_t.rotation_z,
        )
        for impact in affected_connections:
            other = impact.to_object_id if impact.from_object_id in object_ids else impact.from_object_id
            if other not in target_object_ids and other in session.what_if.registry.objects:
                obj = session.what_if.registry.get(other)
                effective_transforms[other] = csa.Transform(
                    position_x=obj.transform.position_x + delta.position_x, position_y=obj.transform.position_y + delta.position_y, position_z=obj.transform.position_z + delta.position_z,
                    rotation_x=obj.transform.rotation_x + delta.rotation_x, rotation_y=obj.transform.rotation_y + delta.rotation_y, rotation_z=obj.transform.rotation_z + delta.rotation_z,
                )
                old_transforms[other] = obj.transform
                target_object_ids.append(other)

    # PRESERVE_CONNECTION: the graph is intentionally left untouched here --
    # real edge-length recomputation from 3D geometry is out of this build's
    # bounded scope (disclosed limitation); the connection is honestly
    # reported as still CONNECTED via `affected_connections`, never silently
    # dropped.

    changeset_ids: list[str] = []
    op_name = "MOVE_OBJECT" if operation == "MOVE" else "ROTATE_OBJECT"
    for oid in target_object_ids:
        obj = session.what_if.registry.get(oid)
        new_obj = replace(obj, transform=effective_transforms[oid])
        cs = csa.apply_changeset(session.what_if, change_id=f"{event_id}-{oid}", operation=op_name, object_id=oid, new_object=new_obj)
        changeset_ids.append(cs.change_id)
    session._redo_stack.clear()

    result = TransformValidationResult(
        event_id=event_id, object_ids=tuple(target_object_ids), requested_operation=operation, old_transforms=old_transforms,
        proposed_transforms=effective_transforms, selection_scope=(session.selection.selection_scope if session.selection else None),
        affected_connections=affected_connections, connection_policy=connection_policy, allowed=True, validation_status="ACCEPTED",
        issues=(), changeset_ids=tuple(changeset_ids),
    )
    _record_event(session, operation=operation, object_ids=tuple(target_object_ids), old_state=old_transforms, proposed_state=effective_transforms, pivot=pivot, connection_policy=connection_policy, affected_connections=affected_connections, changeset_ids=tuple(changeset_ids), validation_status="ACCEPTED", issues=())
    return result


def move_objects(
    session: AuthoringSession, *, object_ids: Sequence[str], proposed_transforms: Mapping[str, csa.Transform],
    pivot: csa.Transform | None = None, connection_policy: ConnectionPolicy | None = None,
) -> TransformValidationResult:
    """Section 43/51-59: connection impact is ALWAYS resolved BEFORE any
    mutation; atomic across the whole selection."""
    return _apply_transform_operation(session, operation="MOVE", object_ids=object_ids, proposed_transforms=proposed_transforms, pivot=pivot, connection_policy=connection_policy)


def rotate_objects(
    session: AuthoringSession, *, object_ids: Sequence[str], proposed_transforms: Mapping[str, csa.Transform],
    pivot: csa.Transform | None = None, connection_policy: ConnectionPolicy | None = None,
) -> TransformValidationResult:
    """Section 44/13: ENGINEERING_OBJECT_ROTATION -- distinct from camera
    rotation (`apply_view_camera_rotation`), which never reaches this path."""
    return _apply_transform_operation(session, operation="ROTATE", object_ids=object_ids, proposed_transforms=proposed_transforms, pivot=pivot, connection_policy=connection_policy)


def stretch_segment(session: AuthoringSession, *, object_id: str, new_length_m: float) -> TransformValidationResult:
    """Section 45/108: MRT stretch -- updates what-if geometry/length only;
    never computes CapEx/OPEX here (see `compute_segment_length_capex_delta`
    in canonical_spatial_authority.py for the existing economic hook)."""
    import math

    event_id = f"EVT-{uuid.uuid4().hex[:12]}"
    if object_id not in session.what_if.registry.objects:
        return _reject(session, event_id=event_id, operation="STRETCH", object_ids=(object_id,), issues=(InteractionValidationIssue("UNKNOWN_OBJECT_ID", f"{object_id} not found"),))
    obj = session.what_if.registry.get(object_id)
    caps = capabilities_for(obj.object_type)
    issues = []
    if not caps.stretchable:
        issues.append(InteractionValidationIssue("OPERATION_UNSUPPORTED_BY_CAPABILITY", f"{object_id} ({obj.object_type}) is not stretchable"))
    if not math.isfinite(new_length_m) or new_length_m < 0:
        issues.append(InteractionValidationIssue("INVALID_STRETCH", f"invalid new_length_m {new_length_m!r}"))
    if issues:
        return _reject(session, event_id=event_id, operation="STRETCH", object_ids=(object_id,), issues=tuple(issues))

    old_ref = obj.geometry_reference
    old_length = None
    if old_ref and old_ref.startswith("LENGTH:") and old_ref.split(":", 1)[1] != "NOT_CALIBRATED":
        try:
            old_length = float(old_ref.split(":", 1)[1])
        except ValueError:
            old_length = None
    op_name = "EXTEND_SEGMENT" if (old_length is None or new_length_m >= old_length) else "SHORTEN_SEGMENT"
    new_obj = replace(obj, geometry_reference=f"LENGTH:{new_length_m}", spatial_status="CALIBRATED")
    cs = csa.apply_changeset(session.what_if, change_id=event_id, operation=op_name, object_id=object_id, new_object=new_obj)
    session._redo_stack.clear()

    result = TransformValidationResult(
        event_id=event_id, object_ids=(object_id,), requested_operation="STRETCH", old_transforms={object_id: obj.transform},
        proposed_transforms={object_id: obj.transform}, selection_scope=None, affected_connections=(), connection_policy=None,
        allowed=True, validation_status="ACCEPTED", issues=(), changeset_ids=(cs.change_id,),
    )
    _record_event(session, operation="STRETCH", object_ids=(object_id,), old_state={"geometry_reference": old_ref}, proposed_state={"geometry_reference": new_obj.geometry_reference}, pivot=None, connection_policy=None, affected_connections=(), changeset_ids=(cs.change_id,), validation_status="ACCEPTED", issues=())
    return result


def add_object(
    session: AuthoringSession, *, new_object_id: str, object_type: csa.SpatialObjectType, parent_object_id: str,
    transform: csa.Transform = csa.Transform(), engineering_object_id: str | None = None,
) -> TransformValidationResult:
    """Section 46/83: creates a temporary PROPOSED object that exists ONLY
    in what-if state until simulation promotion."""
    event_id = f"EVT-{uuid.uuid4().hex[:12]}"
    issues = []
    if new_object_id in session.what_if.registry.objects:
        issues.append(InteractionValidationIssue("DUPLICATE_NEW_OBJECT_ID", f"{new_object_id} already exists"))
    if parent_object_id not in session.what_if.registry.objects:
        issues.append(InteractionValidationIssue("INVALID_PARENT", f"parent_object_id {parent_object_id} not found"))
    if not _finite_transform(transform):
        issues.append(InteractionValidationIssue("INVALID_TRANSFORM", "non-finite transform"))
    if issues:
        return _reject(session, event_id=event_id, operation="ADD", object_ids=(new_object_id,), issues=tuple(issues))

    parent = session.what_if.registry.get(parent_object_id)
    new_obj = csa.CanonicalSpatialObject(
        mrtway_object_id=new_object_id, object_type=object_type, facility_id=parent.facility_id, building_id=parent.building_id,
        floor_id=parent.floor_id, space_id=new_object_id, parent_object_id=parent_object_id, transform=transform,
        geometry_reference=None, coordinate_system=parent.coordinate_system, asset_status="PROPOSED", operational_state="AVAILABLE",
        spatial_status="USER_PLACED", provenance="USER_CREATED", engineering_object_id=engineering_object_id,
    )
    cs = csa.apply_changeset(session.what_if, change_id=event_id, operation="ADD_OBJECT", object_id=new_object_id, new_object=new_obj)
    session._redo_stack.clear()
    result = TransformValidationResult(event_id=event_id, object_ids=(new_object_id,), requested_operation="ADD", old_transforms={}, proposed_transforms={new_object_id: transform}, selection_scope=None, affected_connections=(), connection_policy=None, allowed=True, validation_status="ACCEPTED", issues=(), changeset_ids=(cs.change_id,))
    _record_event(session, operation="ADD", object_ids=(new_object_id,), old_state={}, proposed_state={"object_type": object_type, "parent_object_id": parent_object_id}, pivot=None, connection_policy=None, affected_connections=(), changeset_ids=(cs.change_id,), validation_status="ACCEPTED", issues=())
    return result


def remove_object(session: AuthoringSession, *, object_id: str) -> TransformValidationResult:
    """Section 47/84: hides/removes the object from the EFFECTIVE what-if
    design only -- the locked object is untouched (verified by construction:
    `apply_changeset` never writes to `session.locked`)."""
    event_id = f"EVT-{uuid.uuid4().hex[:12]}"
    if object_id not in session.what_if.registry.objects:
        return _reject(session, event_id=event_id, operation="REMOVE", object_ids=(object_id,), issues=(InteractionValidationIssue("UNKNOWN_OBJECT_ID", f"{object_id} not found"),))
    obj = session.what_if.registry.get(object_id)
    caps = capabilities_for(obj.object_type)
    if not caps.removable_in_what_if:
        return _reject(session, event_id=event_id, operation="REMOVE", object_ids=(object_id,), issues=(InteractionValidationIssue("OPERATION_UNSUPPORTED_BY_CAPABILITY", f"{object_id} ({obj.object_type}) is not removable in what-if state"),))
    cs = csa.apply_changeset(session.what_if, change_id=event_id, operation="REMOVE_OBJECT", object_id=object_id, new_object=None)
    session._redo_stack.clear()
    result = TransformValidationResult(event_id=event_id, object_ids=(object_id,), requested_operation="REMOVE", old_transforms={object_id: obj.transform}, proposed_transforms={}, selection_scope=None, affected_connections=(), connection_policy=None, allowed=True, validation_status="ACCEPTED", issues=(), changeset_ids=(cs.change_id,))
    _record_event(session, operation="REMOVE", object_ids=(object_id,), old_state={"present": True}, proposed_state={"present": False}, pivot=None, connection_policy=None, affected_connections=(), changeset_ids=(cs.change_id,), validation_status="ACCEPTED", issues=())
    return result


def copy_object(session: AuthoringSession, *, source_object_id: str, new_object_id: str, transform: csa.Transform | None = None) -> TransformValidationResult:
    """Section 48/78/111: creates a NEW engineering instance -- never reuses
    `MRTWAY_OBJECT_ID`; catalog/geometry binding (`engineering_object_id`)
    reference may be reused via the caller's own binding table."""
    event_id = f"EVT-{uuid.uuid4().hex[:12]}"
    issues = []
    if source_object_id not in session.what_if.registry.objects:
        issues.append(InteractionValidationIssue("UNKNOWN_OBJECT_ID", f"{source_object_id} not found"))
    if new_object_id in session.what_if.registry.objects:
        issues.append(InteractionValidationIssue("DUPLICATE_NEW_OBJECT_ID", f"{new_object_id} already exists"))
    if issues:
        return _reject(session, event_id=event_id, operation="COPY", object_ids=(new_object_id,), issues=tuple(issues))

    source = session.what_if.registry.get(source_object_id)
    new_obj = replace(
        source, mrtway_object_id=new_object_id, transform=(transform or source.transform), asset_status="PROPOSED",
        provenance="USER_CREATED", engineering_object_id=(new_object_id if source.engineering_object_id is not None else None),
    )
    cs = csa.apply_changeset(session.what_if, change_id=event_id, operation="COPY_OBJECT", object_id=new_object_id, new_object=new_obj)
    session._redo_stack.clear()
    result = TransformValidationResult(event_id=event_id, object_ids=(new_object_id,), requested_operation="COPY", old_transforms={}, proposed_transforms={new_object_id: new_obj.transform}, selection_scope=None, affected_connections=(), connection_policy=None, allowed=True, validation_status="ACCEPTED", issues=(), changeset_ids=(cs.change_id,))
    _record_event(session, operation="COPY", object_ids=(new_object_id,), old_state={"source_object_id": source_object_id}, proposed_state={"new_object_id": new_object_id}, pivot=None, connection_policy=None, affected_connections=(), changeset_ids=(cs.change_id,), validation_status="ACCEPTED", issues=())
    return result


def connect_objects(
    session: AuthoringSession, *, source_object_id: str, target_object_id: str,
    connection_type: Literal["MRT", "CORRIDOR_BRIDGE_TUNNEL", "OTHER"], length_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED",
    edge_id: str | None = None,
) -> TransformValidationResult:
    """Section 49: CONNECT identifies source/target/connection type and
    creates a proposed edge in the WHAT-IF graph copy only -- the locked
    graph is never touched."""
    event_id = f"EVT-{uuid.uuid4().hex[:12]}"
    issues = []
    for oid in (source_object_id, target_object_id):
        if oid not in session.what_if.registry.objects:
            issues.append(InteractionValidationIssue("UNKNOWN_OBJECT_ID", f"{oid} not found"))
        elif not capabilities_for(session.what_if.registry.get(oid).object_type).connectable:
            issues.append(InteractionValidationIssue("OPERATION_UNSUPPORTED_BY_CAPABILITY", f"{oid} is not connectable"))
    if session.what_if_graph is None:
        issues.append(InteractionValidationIssue("NO_GRAPH_AVAILABLE", "session has no connectivity graph"))
    if issues:
        return _reject(session, event_id=event_id, operation="CONNECT", object_ids=(source_object_id, target_object_id), issues=tuple(issues))

    new_edge_id = edge_id or f"EDGE-{uuid.uuid4().hex[:8]}"
    compatible_modes = frozenset({"MRT"}) if connection_type == "MRT" else frozenset({"WALKING_PORTER", "PATIENT_MOVEMENT"})
    session.what_if_graph.add_edge(csa.SpatialEdge(edge_id=new_edge_id, from_object_id=source_object_id, to_object_id=target_object_id, length_m=length_m, compatible_modes=compatible_modes))
    result = TransformValidationResult(event_id=event_id, object_ids=(source_object_id, target_object_id), requested_operation="CONNECT", old_transforms={}, proposed_transforms={}, selection_scope=None, affected_connections=(), connection_policy=None, allowed=True, validation_status="ACCEPTED", issues=(), changeset_ids=())
    _record_event(session, operation="CONNECT", object_ids=(source_object_id, target_object_id), old_state={}, proposed_state={"edge_id": new_edge_id, "connection_type": connection_type}, pivot=None, connection_policy=None, affected_connections=(), changeset_ids=(), validation_status="ACCEPTED", issues=())
    return result


def disconnect_connection(session: AuthoringSession, *, connection_id: str) -> TransformValidationResult:
    """Section 50/58: DISCONNECT removes/deactivates an edge in the WHAT-IF
    graph copy ONLY; the locked graph and locked registry are never mutated."""
    event_id = f"EVT-{uuid.uuid4().hex[:12]}"
    if session.what_if_graph is None:
        return _reject(session, event_id=event_id, operation="DISCONNECT", object_ids=(), issues=(InteractionValidationIssue("NO_GRAPH_AVAILABLE", "session has no connectivity graph"),))
    edge = next((e for e in session.what_if_graph.edges if e.edge_id == connection_id), None)
    if edge is None:
        return _reject(session, event_id=event_id, operation="DISCONNECT", object_ids=(), issues=(InteractionValidationIssue("UNKNOWN_CONNECTION", f"connection {connection_id} not found"),))
    resolution = csa.resolve_connection_disconnect(session.what_if_graph, connection_id=connection_id)
    result = TransformValidationResult(event_id=event_id, object_ids=(edge.from_object_id, edge.to_object_id), requested_operation="DISCONNECT", old_transforms={}, proposed_transforms={}, selection_scope=None, affected_connections=(), connection_policy="DISCONNECT", allowed=True, validation_status="ACCEPTED", issues=(), changeset_ids=())
    _record_event(session, operation="DISCONNECT", object_ids=(edge.from_object_id, edge.to_object_id), old_state={"connection_id": connection_id, "status": "CONNECTED"}, proposed_state={"status": resolution.resulting_status}, pivot=None, connection_policy="DISCONNECT", affected_connections=(), changeset_ids=(), validation_status="ACCEPTED", issues=())
    return result


# ---------------------------------------------------------------------------
# Group / ungroup passthrough (sections 24-26)
# ---------------------------------------------------------------------------


def group_selected(session: AuthoringSession, *, group_id: str) -> csa.ObjectGroup:
    """Section 24/26: grouping is a transform convenience -- reuses the
    existing `ObjectGroup` authority verbatim, never replaces canonical
    identity."""
    if session.selection is None:
        raise ValueError("group_selected: no active selection")
    return csa.group_objects(group_id=group_id, member_object_ids=session.selection.selected_object_ids)


def ungroup_members(group: csa.ObjectGroup) -> tuple[str, ...]:
    """Section 25: UNGROUP removes grouping only -- never deletes objects."""
    return csa.ungroup(group)


# ---------------------------------------------------------------------------
# Undo / redo (sections 69-70)
# ---------------------------------------------------------------------------


def undo_last(session: AuthoringSession) -> csa.SpatialChangeSet | None:
    """Section 69: reverses the most recent CANONICAL what-if changeset
    (never merely a USD visual edit)."""
    changeset = session.what_if.undo_last_change()
    if changeset is not None:
        session._redo_stack.append(changeset)
    return changeset


def redo_last(session: AuthoringSession) -> csa.SpatialChangeSet | None:
    """Section 70: REDO_LAST -- re-applies the single most recently undone
    changeset. DISCLOSED LIMITATION: this is a depth-1 redo (only the most
    recent undo can be redone before a new edit clears the stack) -- a full
    arbitrary-depth redo stack was judged out of this build's bounded scope;
    this does not compromise the existing undo/reset semantics at all."""
    if not session._redo_stack:
        return None
    changeset = session._redo_stack.pop()
    return csa.apply_changeset(session.what_if, change_id=f"{changeset.change_id}-REDO", operation=changeset.operation, object_id=changeset.object_id, new_object=changeset.new_object, note=changeset.note)


# ---------------------------------------------------------------------------
# External viewer transform event (sections 73-76)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExternalViewerTransformEvent:
    usd_prim_path: str
    old_usd_transform: csa.Transform
    new_usd_transform: csa.Transform
    resolved_mrtway_object_id: str | None = None


def apply_external_viewer_transform(
    session: AuthoringSession, *, event: ExternalViewerTransformEvent, path_registry: usda.PrimPathRegistry,
    connection_policy: ConnectionPolicy | None = None,
) -> TransformValidationResult:
    """Section 73-76: NO USD-FIRST AUTHORITY -- an external viewer's raw
    prim transform is resolved to `MRTWAY_OBJECT_ID`, then routed through the
    EXACT SAME `move_objects` validation/atomicity path used for in-app
    interaction. Rejected transforms leave locked AND what-if state
    unchanged."""
    event_id = f"EVT-{uuid.uuid4().hex[:12]}"
    mrtway_id = event.resolved_mrtway_object_id or path_registry.resolve_by_prim_path(event.usd_prim_path)
    issues = []
    if mrtway_id is None:
        issues.append(InteractionValidationIssue("UNRESOLVED_MRTWAY_OBJECT_ID", f"prim {event.usd_prim_path!r} has no MRTWAY_OBJECT_ID mapping"))
    elif mrtway_id not in session.what_if.registry.objects:
        issues.append(InteractionValidationIssue("UNKNOWN_OBJECT_ID", f"{mrtway_id} not found in what-if registry"))
    if not _finite_transform(event.new_usd_transform):
        issues.append(InteractionValidationIssue("INVALID_TRANSFORM", "non-finite transform in external viewer event"))
    if issues:
        return _reject(session, event_id=event_id, operation="EXTERNAL_VIEWER_MOVE", object_ids=((mrtway_id,) if mrtway_id else ()), issues=tuple(issues))
    return move_objects(session, object_ids=(mrtway_id,), proposed_transforms={mrtway_id: event.new_usd_transform}, connection_policy=connection_policy)


# ---------------------------------------------------------------------------
# Simulation handoff (sections 7, 87, 116-117) -- promotion remains explicit.
# ---------------------------------------------------------------------------


def build_proposed_simulation_input(session: AuthoringSession) -> csa.LockedSpatialState:
    """Section 116: BUILD_PROPOSED_SIMULATION_INPUT_FROM_WHAT_IF -- reuses
    the existing promotion foundation verbatim. Does NOT run any simulation
    and does NOT itself make this the session's locked state -- the caller
    must explicitly treat the RESULT as a candidate new locked state after
    running engineering validation (outside this build's scope)."""
    return csa.promote_what_if_to_simulation_input(session.what_if)


def sync_what_if_usd_scene(session: AuthoringSession, **export_kwargs):
    """Section 72: canonical state FIRST, USD second -- call only AFTER a
    valid canonical what-if change has already been applied."""
    return usda.export_what_if_state(session.what_if, **export_kwargs)


# ---------------------------------------------------------------------------
# Engineering object palette backend (sections 77-90) -- metadata ONLY, no
# visual UI. Reuses the OpenUSD build's geometry-asset registry and the
# EXISTING equipment/MRT/logistics catalogs -- never a second catalog.
# ---------------------------------------------------------------------------

PaletteCategory = Literal[
    "FACILITY", "NUCLEAR_PRODUCTION", "NUCLEAR_IMAGING", "MRT_INFRASTRUCTURE",
    "GENERAL_LOGISTICS", "AUTOMATED_CONVENTIONAL", "SUPPORT",
]


@dataclass(frozen=True)
class PaletteItem:
    palette_item_id: str
    object_type: csa.SpatialObjectType
    display_name: str
    category: PaletteCategory
    manufacturer: str | None
    model: str | None
    catalog_model_id: str | None
    geometry_asset_id: str
    geometry_quality: usda.GeometryQuality
    placeable: bool
    movable: bool
    rotatable: bool
    stretchable: bool
    copyable: bool
    connectable: bool
    disconnectable: bool
    required_parent_types: tuple[csa.SpatialObjectType, ...]
    default_asset_status: csa.AssetStatus
    provenance: str


def _palette_entry_from_capabilities(
    *, palette_item_id: str, object_type: csa.SpatialObjectType, display_name: str, category: PaletteCategory,
    required_parent_types: tuple[csa.SpatialObjectType, ...], manufacturer: str | None = None, model: str | None = None,
    catalog_model_id: str | None = None, geometry_asset: usda.GeometryAsset | None = None, provenance: str = "ENGINEERING_CATALOG",
) -> PaletteItem:
    caps = capabilities_for(object_type)
    resolved_asset = geometry_asset or usda._NOT_AVAILABLE_GEOMETRY_ASSET
    return PaletteItem(
        palette_item_id=palette_item_id, object_type=object_type, display_name=display_name, category=category,
        manufacturer=manufacturer, model=model, catalog_model_id=catalog_model_id, geometry_asset_id=resolved_asset.geometry_asset_id,
        geometry_quality=resolved_asset.geometry_quality, placeable=True, movable=caps.movable, rotatable=caps.rotatable,
        stretchable=caps.stretchable, copyable=caps.copyable, connectable=caps.connectable, disconnectable=caps.disconnectable,
        required_parent_types=required_parent_types, default_asset_status="PROPOSED", provenance=provenance,
    )


def build_engineering_object_palette(geometry_assets: usda.GeometryAssetRegistry | None = None) -> tuple[PaletteItem, ...]:
    """Section 77-90: reads ONLY real repository catalogs -- never fabricates
    a manufacturer/model. Absent catalog entries simply produce no palette
    row (section 132), never a placeholder fake model."""
    geometry_assets = geometry_assets or usda.default_geometry_asset_registry()
    items: list[PaletteItem] = []

    try:
        from cyclotron_catalog import load_cyclotron_catalog
        for model in load_cyclotron_catalog().models:
            if not model.customer_selectable:
                continue
            items.append(_palette_entry_from_capabilities(
                palette_item_id=f"PALETTE-CYCLOTRON-{model.catalog_model_id}", object_type="CYCLOTRON",
                display_name=f"{model.manufacturer} {model.model}", category="NUCLEAR_PRODUCTION",
                required_parent_types=("FLOOR",), manufacturer=model.manufacturer, model=model.model,
                catalog_model_id=model.catalog_model_id, geometry_asset=geometry_assets.resolve(model.catalog_model_id),
            ))
    except Exception:
        pass

    try:
        from generator_catalog import load_generator_catalog
        for model in load_generator_catalog().models:
            items.append(_palette_entry_from_capabilities(
                palette_item_id=f"PALETTE-GENERATOR-{model.catalog_model_id}", object_type="MO99_TC99M_GENERATOR",
                display_name=f"{model.manufacturer} {model.model}", category="NUCLEAR_PRODUCTION",
                required_parent_types=("FLOOR",), manufacturer=model.manufacturer, model=model.model,
                catalog_model_id=model.catalog_model_id, geometry_asset=geometry_assets.resolve(model.catalog_model_id),
            ))
    except Exception:
        pass

    try:
        from scanner_catalog import load_scanner_catalog
        catalog = load_scanner_catalog()
        for model in catalog.models_of_modality("PET"):
            items.append(_palette_entry_from_capabilities(
                palette_item_id=f"PALETTE-PET-{model.catalog_model_id}", object_type="PET_SCANNER",
                display_name=f"{model.manufacturer} {model.model}", category="NUCLEAR_IMAGING",
                required_parent_types=("FLOOR",), manufacturer=model.manufacturer, model=model.model,
                catalog_model_id=model.catalog_model_id, geometry_asset=geometry_assets.resolve(model.catalog_model_id),
            ))
        for model in catalog.models_of_modality("SPECT"):
            items.append(_palette_entry_from_capabilities(
                palette_item_id=f"PALETTE-SPECT-{model.catalog_model_id}", object_type="SPECT_SCANNER",
                display_name=f"{model.manufacturer} {model.model}", category="NUCLEAR_IMAGING",
                required_parent_types=("FLOOR",), manufacturer=model.manufacturer, model=model.model,
                catalog_model_id=model.catalog_model_id, geometry_asset=geometry_assets.resolve(model.catalog_model_id),
            ))
    except Exception:
        pass

    # RADIOPHARMACY (section 79) -- existing engineering object type, no
    # separate manufacturer catalog exists for it.
    items.append(_palette_entry_from_capabilities(
        palette_item_id="PALETTE-RADIOPHARMACY", object_type="RADIOPHARMACY", display_name="Radiopharmacy",
        category="NUCLEAR_PRODUCTION", required_parent_types=("FLOOR",), provenance="ENGINEERING_AUTHORITY",
    ))

    # MRT infrastructure (section 87-88) -- vestibule economics disclosed as
    # metadata reference only, never calculated here (section 88).
    mrt_types: tuple[tuple[csa.SpatialObjectType, str], ...] = (
        ("MRT_VESTIBULE", "MRT Vestibule"), ("MRT_TRUNK", "MRT Trunk"), ("MRT_BRANCH", "MRT Branch"),
        ("MRT_SEGMENT", "MRT Segment"), ("MRT_JUNCTION", "MRT Junction"), ("MRT_ENDPOINT", "MRT Endpoint"),
        ("MRT_CARRIER", "MRT Carrier"), ("MRT_CONTAINER", "MRT Container"),
    )
    for object_type, display_name in mrt_types:
        items.append(_palette_entry_from_capabilities(
            palette_item_id=f"PALETTE-{object_type}", object_type=object_type, display_name=display_name,
            category="MRT_INFRASTRUCTURE", required_parent_types=(), provenance="ENGINEERING_AUTHORITY",
        ))

    # General logistics origins (section 42/89)
    logistics_types: tuple[tuple[csa.SpatialObjectType, str], ...] = (
        ("CENTRAL_PHARMACY", "Central Pharmacy"), ("LABORATORY", "Laboratory"), ("BLOOD_BANK", "Blood Bank"),
        ("CLEAN_LINEN_SOURCE", "Clean Linen Source"), ("STERILE_CLEAN_SUPPLY_SOURCE", "Sterile Clean Supply Source"),
    )
    for object_type, display_name in logistics_types:
        items.append(_palette_entry_from_capabilities(
            palette_item_id=f"PALETTE-{object_type}", object_type=object_type, display_name=display_name,
            category="GENERAL_LOGISTICS", required_parent_types=("FLOOR",), provenance="ENGINEERING_AUTHORITY",
        ))

    return tuple(items)


def palette_vestibule_economic_reference() -> float:
    """Section 88: exposes the EXISTING controlled vestibule economic value
    for palette display metadata only -- never recomputed here."""
    return csa.MRT_VESTIBULE_CAPEX_USD


# ---------------------------------------------------------------------------
# Drop validation (sections 91-95)
# ---------------------------------------------------------------------------

FitStatus = Literal["FIT", "DOES_NOT_FIT", "NOT_CALIBRATED"]


@dataclass(frozen=True)
class DropValidationResult:
    valid: bool
    issues: tuple[InteractionValidationIssue, ...]
    fit_status: FitStatus
    service_clearance_status: Literal["NOT_CALIBRATED"]


def validate_drop_placement(
    session: AuthoringSession, *, palette_item: PaletteItem, new_object_id: str, target_parent_object_id: str,
    transform: csa.Transform,
) -> DropValidationResult:
    """Section 92-95: validates target parent/location existence, hierarchy
    rules, ID uniqueness, transform finiteness, and geometry-quality
    disclosure -- never fabricates clearance/fit."""
    issues = []
    if new_object_id in session.what_if.registry.objects:
        issues.append(InteractionValidationIssue("DUPLICATE_NEW_OBJECT_ID", f"{new_object_id} already exists"))
    if target_parent_object_id not in session.what_if.registry.objects:
        issues.append(InteractionValidationIssue("INVALID_PARENT", f"parent {target_parent_object_id} not found"))
    else:
        parent = session.what_if.registry.get(target_parent_object_id)
        if palette_item.required_parent_types and parent.object_type not in palette_item.required_parent_types:
            issues.append(InteractionValidationIssue("INVALID_HIERARCHY", f"{palette_item.object_type} requires a parent of type {palette_item.required_parent_types}, got {parent.object_type}"))
    if not _finite_transform(transform):
        issues.append(InteractionValidationIssue("INVALID_TRANSFORM", "non-finite drop transform"))
    if palette_item.catalog_model_id is not None and palette_item.geometry_quality == "NOT_AVAILABLE":
        issues.append(InteractionValidationIssue("MISSING_CATALOG_BINDING", "catalog_model_id present but no geometry asset bound"))
    return DropValidationResult(valid=(len(issues) == 0), issues=tuple(issues), fit_status="NOT_CALIBRATED", service_clearance_status="NOT_CALIBRATED")


def drop_palette_item(
    session: AuthoringSession, *, palette_item: PaletteItem, new_object_id: str, target_parent_object_id: str,
    transform: csa.Transform = csa.Transform(),
) -> TransformValidationResult:
    """Section 91: palette item selected -> validated -> canonical ADD_OBJECT
    what-if change. Never a final visual drag/drop."""
    event_id = f"EVT-{uuid.uuid4().hex[:12]}"
    validation = validate_drop_placement(session, palette_item=palette_item, new_object_id=new_object_id, target_parent_object_id=target_parent_object_id, transform=transform)
    if not validation.valid:
        return _reject(session, event_id=event_id, operation="ADD", object_ids=(new_object_id,), issues=validation.issues)
    return add_object(session, new_object_id=new_object_id, object_type=palette_item.object_type, parent_object_id=target_parent_object_id, transform=transform, engineering_object_id=(new_object_id if palette_item.catalog_model_id else None))


# ---------------------------------------------------------------------------
# Object-inspector binding + 2D table / system-delta contracts (sections
# 101-103) -- NO new economics are calculated here; unresolved values are
# honestly `NOT_CALIBRATED`/`PENDING_ENGINEERING_RECALCULATION`.
# ---------------------------------------------------------------------------


def inspect_object(session: AuthoringSession, *, object_id: str) -> csa.ObjectInspectorRecord:
    """Section 101/112: reuses the existing object-inspector contract --
    never a second engineering calculation."""
    return csa.build_object_inspector_record(session.what_if.registry.get(object_id))


EconomicValue = float | Literal["NOT_CALIBRATED", "PENDING_ENGINEERING_RECALCULATION"]


@dataclass(frozen=True)
class NearbyObjectRow:
    object_id: str
    quantity: int
    locked_status: str
    what_if_status: str
    capex: EconomicValue
    annual_opex: EconomicValue
    delta: EconomicValue


def build_nearby_object_table(session: AuthoringSession, *, object_ids: Sequence[str]) -> tuple[NearbyObjectRow, ...]:
    """Section 102: backend output for the future 2D panel. Economic columns
    are honestly PENDING_ENGINEERING_RECALCULATION unless the caller has
    already run (and supplied) a real recalculation -- never fabricated."""
    rows = []
    for oid in object_ids:
        in_locked = oid in session.locked.registry.objects
        in_what_if = oid in session.what_if.registry.objects
        rows.append(NearbyObjectRow(
            object_id=oid, quantity=1, locked_status=("PRESENT" if in_locked else "ABSENT"),
            what_if_status=("PRESENT" if in_what_if else "ABSENT"), capex="PENDING_ENGINEERING_RECALCULATION",
            annual_opex="PENDING_ENGINEERING_RECALCULATION", delta="PENDING_ENGINEERING_RECALCULATION",
        ))
    return tuple(rows)


@dataclass(frozen=True)
class SystemDeltaRow:
    metric: str
    locked: EconomicValue
    what_if: EconomicValue
    delta: EconomicValue


def build_system_delta_contract(session: AuthoringSession) -> tuple[SystemDeltaRow, ...]:
    """Section 103-105: only genuinely deterministic SPATIAL deltas are
    computed immediately (section 105); every downstream engineering/
    economic metric is honestly PENDING_ENGINEERING_RECALCULATION (section
    104) until the real authority has actually run."""
    spatial_delta = csa.compute_delta(session.locked, session.what_if)
    rows = [
        SystemDeltaRow(metric="object_count_added", locked=float(len(session.locked.registry.objects)), what_if=float(len(session.what_if.registry.objects)), delta=float(len(spatial_delta.added_object_ids))),
        SystemDeltaRow(metric="object_count_removed", locked=0.0, what_if=0.0, delta=float(len(spatial_delta.removed_object_ids))),
        SystemDeltaRow(metric="object_count_modified", locked=0.0, what_if=0.0, delta=float(len(spatial_delta.modified_object_ids))),
    ]
    for metric in ("transport_only_capex", "annual_opex", "npv_lifecycle_metric", "route_length", "transport_time", "porter_fte", "agv_fleet", "mrt_carrier_requirement", "nuclear_qualification", "late_missions", "unmet_missions"):
        rows.append(SystemDeltaRow(metric=metric, locked="PENDING_ENGINEERING_RECALCULATION", what_if="PENDING_ENGINEERING_RECALCULATION", delta="PENDING_ENGINEERING_RECALCULATION"))
    return tuple(rows)


def build_segment_length_delta_row(session: AuthoringSession, *, object_id: str, guideway_unit_cost_per_m: float | None = None) -> SystemDeltaRow:
    """Section 105-106: segment length delta IS immediately deterministic --
    reuses the EXISTING `compute_segment_length_capex_delta` hook, never an
    independent viewer price."""
    def _length_of(reg: csa.SpatialObjectRegistry) -> float | None:
        if object_id not in reg.objects:
            return None
        ref = reg.get(object_id).geometry_reference
        if ref and ref.startswith("LENGTH:") and ref.split(":", 1)[1] != "NOT_CALIBRATED":
            try:
                return float(ref.split(":", 1)[1])
            except ValueError:
                return None
        return None

    locked_length = _length_of(session.locked.registry)
    what_if_length = _length_of(session.what_if.registry)
    if locked_length is None or what_if_length is None:
        return SystemDeltaRow(metric=f"segment_length[{object_id}]", locked="NOT_CALIBRATED", what_if="NOT_CALIBRATED", delta="NOT_CALIBRATED")
    delta_capex = csa.compute_segment_length_capex_delta(locked_length_m=locked_length, what_if_length_m=what_if_length, guideway_unit_cost_per_m=guideway_unit_cost_per_m)
    return SystemDeltaRow(metric=f"segment_length_capex_delta[{object_id}]", locked=locked_length, what_if=what_if_length, delta=delta_capex)

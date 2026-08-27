"""Unified Lockdown / What-If Lineage and Result-Binding Authority (Phase 1A).

GOVERNANCE: this module does NOT reimplement spatial branching, parameter
what-if changesets, plan versioning, engineering-impact revision protection,
or ANY physics/decay/transport/CapEx/OPEX/NPV/IRR mathematics. It BINDS the
existing identities -- `canonical_spatial_authority.LockedSpatialState` /
`WhatIfSpatialState`, `mrt_auxiliary_systems_authority.UnifiedWhatIfScenario`
/ `ActiveChange`, `live_operational_state.PlanVersion`, and whichever
simulation/engineering/economic result objects the caller already computed
-- under ONE `lockdown_id` / `what_if_id` lineage, per the governance audit.

Every spatial mutation still goes through `canonical_spatial_authority`
(`apply_changeset`, `promote_what_if_to_simulation_input`,
`WhatIfSpatialState.branch_from`/`reset_to_locked`) -- this module only ever
calls those functions, never re-derives their behavior. Simulation/
engineering/economic results are held by REFERENCE (`object | None`); this
module never recomputes or reproduces their fields, only stores/retrieves
them and reads a small set of well-known attribute names for comparison
rows (see `_ECONOMIC_FIELD_ALIASES`).

A Lockdown is immutable once created (status supersession replaces the
registry entry; nothing mutates a `CanonicalLockdownRecord` in place). A
What-If is mutable while ACTIVE/SAVED_VIEW (recomputed results attach in
place) and effectively frozen once DISCARDED or PROMOTED_TO_LOCKDOWN.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from datetime import datetime, timezone
from typing import Literal, Mapping

import canonical_spatial_authority as csa
import mrt_auxiliary_systems_authority as maux

LOCKDOWN_LINEAGE_SCHEMA_VERSION = "1.0.0"

LockdownStatus = Literal["CURRENT", "SUPERSEDED"]
WhatIfStatus = Literal["ACTIVE", "SAVED_VIEW", "DISCARDED", "PROMOTED_TO_LOCKDOWN"]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Canonical records (sections 3-4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalLockdownRecord:
    """Section 1/3: LOCKDOWN = CONFIGURATION + GEOMETRY + ACTIVE PARAMETERS
    + result references + LINEAGE, fixed at creation time. Superseding a
    Lockdown (section 6) replaces the registry entry via `dataclasses.
    replace` -- this record itself is never mutated in place."""

    lockdown_id: str
    parent_lockdown_id: str | None
    source_what_if_id: str | None
    created_at: str
    spatial_state: csa.LockedSpatialState
    active_parameters: Mapping[str, object]
    simulation_result: object | None
    engineering_result: object | None
    economic_result: object | None
    reason: str
    status: LockdownStatus = "CURRENT"
    entity_bindings: object | None = None
    """Phase 1B: an optional `canonical_entity_binding_authority.
    EntityBindingRegistry` snapshot for this Lockdown -- held generically
    (`object | None`) to keep this module decoupled from Phase 1B, exactly
    like `simulation_result`/`engineering_result`/`economic_result`."""


@dataclass
class CanonicalWhatIfRecord:
    """Section 4-5: a non-authoritative branch. Mutable while ACTIVE/
    SAVED_VIEW (`update_what_if_results` attaches recomputed outputs in
    place); no function mutates it further once DISCARDED or
    PROMOTED_TO_LOCKDOWN."""

    what_if_id: str
    parent_lockdown_id: str
    created_at: str
    what_if_scenario: maux.UnifiedWhatIfScenario
    simulation_result: object | None = None
    engineering_result: object | None = None
    economic_result: object | None = None
    status: WhatIfStatus = "ACTIVE"
    entity_bindings: object | None = None
    """Phase 1B: this branch's own `EntityBindingRegistry` snapshot -- the
    caller is responsible for cloning it from the parent Lockdown's (e.g.
    via `canonical_entity_binding_authority.branch_entity_bindings`) so a
    What-If binding edit never mutates the parent (section 30)."""

    @property
    def change_set(self) -> tuple[maux.ActiveChange, ...]:
        return self.what_if_scenario.active_change_list()

    @property
    def active_parameters(self) -> dict[str, object]:
        return {
            change.parameter_id: change.what_if_value
            for change in self.what_if_scenario.active_changes
            if change.kind == "PARAMETER" and change.parameter_id is not None
        }


@dataclass(frozen=True)
class PlanVersionScenarioBinding:
    """Section 9-10: resolves one `PlanVersion.version_id` to the Lockdown
    or What-If it was generated against -- exactly one of
    `lockdown_id`/`what_if_id` is set."""

    version_id: str
    lockdown_id: str | None
    what_if_id: str | None


# ---------------------------------------------------------------------------
# Registry (section 11: current-Lockdown authority)
# ---------------------------------------------------------------------------


@dataclass
class LockdownLineageRegistry:
    """Section 11: the unified identity/lineage store. `current_lockdown_id`
    is changed by EXACTLY ONE function in this module --
    `promote_what_if_to_lockdown` (section 14: no silent promotion)."""

    lockdowns: dict[str, CanonicalLockdownRecord] = field(default_factory=dict)
    what_ifs: dict[str, CanonicalWhatIfRecord] = field(default_factory=dict)
    current_lockdown_id: str | None = None
    plan_version_scenario: dict[str, PlanVersionScenarioBinding] = field(default_factory=dict)

    def lockdown(self, lockdown_id: str) -> CanonicalLockdownRecord:
        return self.lockdowns[lockdown_id]

    def what_if(self, what_if_id: str) -> CanonicalWhatIfRecord:
        return self.what_ifs[what_if_id]

    def current_lockdown(self) -> CanonicalLockdownRecord | None:
        return self.lockdowns[self.current_lockdown_id] if self.current_lockdown_id else None


# ---------------------------------------------------------------------------
# Transitions (sections 6-7, 16)
# ---------------------------------------------------------------------------


def create_first_lockdown(
    registry: LockdownLineageRegistry,
    *,
    locked: csa.LockedSpatialState,
    active_parameters: Mapping[str, object] | None = None,
    simulation_result: object | None = None,
    engineering_result: object | None = None,
    economic_result: object | None = None,
    reason: str = "initial simulation",
    lockdown_id: str | None = None,
    entity_bindings: object | None = None,
) -> CanonicalLockdownRecord:
    """Section 7: PRE_LOCKDOWN_PROJECT_STATE -> SIMULATION -> L0. Only valid
    for a registry with no prior Lockdown -- branch a What-If and promote it
    to add a subsequent Lockdown (section 6)."""
    if registry.lockdowns:
        raise ValueError("create_first_lockdown: registry already has a Lockdown; branch a What-If and promote it instead")
    record = CanonicalLockdownRecord(
        lockdown_id=lockdown_id or f"LOCKDOWN-{uuid.uuid4().hex[:12]}",
        parent_lockdown_id=None,
        source_what_if_id=None,
        created_at=_timestamp(),
        spatial_state=locked,
        active_parameters=dict(active_parameters or {}),
        simulation_result=simulation_result,
        engineering_result=engineering_result,
        economic_result=economic_result,
        reason=reason,
        status="CURRENT",
        entity_bindings=entity_bindings,
    )
    registry.lockdowns[record.lockdown_id] = record
    registry.current_lockdown_id = record.lockdown_id
    return record


def branch_what_if(
    registry: LockdownLineageRegistry, *, parent_lockdown_id: str, what_if_id: str | None = None,
) -> CanonicalWhatIfRecord:
    """Section 2/16: a What-If never mutates its parent Lockdown -- reuses
    `branch_what_if_scenario`/`WhatIfSpatialState.branch_from` verbatim.
    Never changes `registry.current_lockdown_id` (section 14). Section 30:
    if the parent Lockdown carries an `entity_bindings` snapshot, the
    branch starts from an independent clone of it (never the same object)
    -- callers needing this must pass their own clone via
    `canonical_entity_binding_authority.branch_entity_bindings`; this
    module stays decoupled from Phase 1B and only copies whatever object
    reference the caller already cloned, via `update_what_if_results`-style
    attachment after `branch_what_if` returns."""
    parent = registry.lockdowns[parent_lockdown_id]
    scenario = maux.branch_what_if_scenario(locked=parent.spatial_state, base_locked_state_id=parent_lockdown_id, scenario_id=what_if_id)
    record = CanonicalWhatIfRecord(
        what_if_id=scenario.scenario_id, parent_lockdown_id=parent_lockdown_id, created_at=_timestamp(), what_if_scenario=scenario,
    )
    registry.what_ifs[record.what_if_id] = record
    return record


def update_what_if_results(
    registry: LockdownLineageRegistry,
    what_if_id: str,
    *,
    simulation_result: object | None = None,
    engineering_result: object | None = None,
    economic_result: object | None = None,
    entity_bindings: object | None = None,
) -> CanonicalWhatIfRecord:
    """Section 5/9-10/30: recomputed outputs (including a Phase 1B
    `entity_bindings` snapshot) attach to the ACTIVE/SAVED_VIEW branch in
    place -- never touches the parent Lockdown."""
    record = registry.what_ifs[what_if_id]
    if record.status not in ("ACTIVE", "SAVED_VIEW"):
        raise ValueError(f"cannot update results for a What-If with status {record.status!r}")
    if simulation_result is not None:
        record.simulation_result = simulation_result
    if engineering_result is not None:
        record.engineering_result = engineering_result
    if economic_result is not None:
        record.economic_result = economic_result
    if entity_bindings is not None:
        record.entity_bindings = entity_bindings
    return record


def discard_what_if(registry: LockdownLineageRegistry, what_if_id: str) -> CanonicalWhatIfRecord:
    """Section 3/16: What-If -> discard -> Lockdown remains current. The
    record is PRESERVED with status DISCARDED for audit, never deleted."""
    record = registry.what_ifs[what_if_id]
    if record.status not in ("ACTIVE", "SAVED_VIEW"):
        raise ValueError(f"cannot discard a What-If with status {record.status!r}")
    record.what_if_scenario.what_if.reset_to_locked()
    record.status = "DISCARDED"
    return record


def save_what_if_view(registry: LockdownLineageRegistry, what_if_id: str) -> CanonicalWhatIfRecord:
    """Section 5: SAVE THIS VIEW without promotion -- remains
    non-authoritative, reopenable, and later promotable; never changes
    `current_lockdown_id`."""
    record = registry.what_ifs[what_if_id]
    if record.status != "ACTIVE":
        raise ValueError(f"cannot save a What-If with status {record.status!r}")
    record.status = "SAVED_VIEW"
    return record


def reopen_saved_what_if(registry: LockdownLineageRegistry, what_if_id: str) -> CanonicalWhatIfRecord:
    """Section 5: a saved What-If can later be reopened for further edits."""
    record = registry.what_ifs[what_if_id]
    if record.status != "SAVED_VIEW":
        raise ValueError(f"cannot reopen a What-If with status {record.status!r}")
    record.status = "ACTIVE"
    return record


def promote_what_if_to_lockdown(
    registry: LockdownLineageRegistry, what_if_id: str, *, reason: str = "", lockdown_id: str | None = None,
) -> CanonicalLockdownRecord:
    """Section 6/16: W1 -> LOCK DOWN THIS VIEW -> L1. L1 records
    parent_lockdown_id=L0 and source_what_if_id=W1; L0 is preserved
    (status SUPERSEDED, never deleted/overwritten); W1 becomes
    PROMOTED_TO_LOCKDOWN. This is the ONLY function in this module that may
    change `registry.current_lockdown_id` (section 11/14)."""
    record = registry.what_ifs[what_if_id]
    if record.status not in ("ACTIVE", "SAVED_VIEW"):
        raise ValueError(f"cannot promote a What-If with status {record.status!r}")
    parent = registry.lockdowns[record.parent_lockdown_id]
    new_locked = csa.promote_what_if_to_simulation_input(record.what_if_scenario.what_if)
    new_record = CanonicalLockdownRecord(
        lockdown_id=lockdown_id or f"LOCKDOWN-{uuid.uuid4().hex[:12]}",
        parent_lockdown_id=parent.lockdown_id,
        source_what_if_id=what_if_id,
        created_at=_timestamp(),
        spatial_state=new_locked,
        active_parameters=dict(record.active_parameters),
        simulation_result=record.simulation_result,
        engineering_result=record.engineering_result,
        economic_result=record.economic_result,
        reason=reason,
        status="CURRENT",
        entity_bindings=record.entity_bindings,
    )
    registry.lockdowns[parent.lockdown_id] = replace(parent, status="SUPERSEDED")
    registry.lockdowns[new_record.lockdown_id] = new_record
    record.status = "PROMOTED_TO_LOCKDOWN"
    registry.current_lockdown_id = new_record.lockdown_id
    return new_record


# ---------------------------------------------------------------------------
# PlanVersion / live-simulation-state binding (sections 9-10)
# ---------------------------------------------------------------------------


def bind_plan_version(
    registry: LockdownLineageRegistry, *, version_id: str, lockdown_id: str | None = None, what_if_id: str | None = None,
) -> PlanVersionScenarioBinding:
    """Section 9-10: a `PlanVersion`/live-simulation run must know exactly
    which Lockdown or What-If it ran against -- reuses `PlanVersion`
    unchanged, only binds its `version_id` to a scenario identity."""
    if (lockdown_id is None) == (what_if_id is None):
        raise ValueError("bind_plan_version: exactly one of lockdown_id/what_if_id must be provided")
    if lockdown_id is not None and lockdown_id not in registry.lockdowns:
        raise ValueError(f"bind_plan_version: unknown lockdown_id {lockdown_id!r}")
    if what_if_id is not None and what_if_id not in registry.what_ifs:
        raise ValueError(f"bind_plan_version: unknown what_if_id {what_if_id!r}")
    binding = PlanVersionScenarioBinding(version_id=version_id, lockdown_id=lockdown_id, what_if_id=what_if_id)
    registry.plan_version_scenario[version_id] = binding
    return binding


def resolve_plan_version_scenario(registry: LockdownLineageRegistry, version_id: str) -> PlanVersionScenarioBinding | None:
    return registry.plan_version_scenario.get(version_id)


# ---------------------------------------------------------------------------
# Comparison (sections 12-13) -- reuses `SpatialDelta`/`compute_delta`;
# reads well-known economic-result attribute names generically rather than
# hard-coding to one result dataclass (never a new financial calculation).
# ---------------------------------------------------------------------------

LineageMetricStatus = Literal["IMPROVED", "DEGRADED", "UNCHANGED", "NOT_AVAILABLE"]


@dataclass(frozen=True)
class LineageComparisonRow:
    metric: str
    before_value: float | str | None
    after_value: float | str | None
    delta: float | str | None
    unit: str
    status: LineageMetricStatus


@dataclass(frozen=True)
class LineageComparisonResult:
    before_id: str
    after_id: str
    comparison_kind: Literal["LOCKDOWN_VS_LOCKDOWN", "LOCKDOWN_VS_WHAT_IF"]
    spatial_delta: csa.SpatialDelta
    rows: tuple[LineageComparisonRow, ...]


# (metric label, candidate attribute names in priority order, unit, higher_is_better)
_ECONOMIC_FIELD_ALIASES: tuple[tuple[str, tuple[str, ...], str, bool], ...] = (
    ("capex", ("total_capex_usd", "initial_capex", "capex"), "usd", False),
    ("annual_opex", ("total_annual_opex_usd", "annual_opex", "annual_incremental_opex"), "usd/yr", False),
    ("annual_revenue", ("annual_revenue_usd", "annual_revenue"), "usd/yr", True),
    ("npv", ("npv_usd", "final_npv"), "usd", True),
    ("payback_years", ("payback_years", "payback_year"), "years", False),
    ("irr_pct", ("irr_pct",), "%", True),
)


def _first_attr(result: object | None, names: tuple[str, ...]) -> float | str | None:
    if result is None:
        return None
    for name in names:
        if hasattr(result, name):
            value = getattr(result, name)
            return value if isinstance(value, (int, float, str)) else None
    return None


def _economic_rows(before: object | None, after: object | None) -> tuple[LineageComparisonRow, ...]:
    rows: list[LineageComparisonRow] = []
    for metric, names, unit, higher_is_better in _ECONOMIC_FIELD_ALIASES:
        before_value = _first_attr(before, names)
        after_value = _first_attr(after, names)
        if not isinstance(before_value, (int, float)) or not isinstance(after_value, (int, float)):
            rows.append(LineageComparisonRow(metric=metric, before_value=before_value, after_value=after_value, delta=None, unit=unit, status="NOT_AVAILABLE"))
            continue
        delta = after_value - before_value
        if delta == 0:
            status: LineageMetricStatus = "UNCHANGED"
        elif (delta > 0) == higher_is_better:
            status = "IMPROVED"
        else:
            status = "DEGRADED"
        rows.append(LineageComparisonRow(metric=metric, before_value=before_value, after_value=after_value, delta=delta, unit=unit, status=status))
    return tuple(rows)


def _registry_delta(before_registry: csa.SpatialObjectRegistry, after_registry: csa.SpatialObjectRegistry) -> csa.SpatialDelta:
    """Section 12: generalizes `csa.compute_delta`'s object-id set-diff to
    ANY two registries (Lockdown-vs-Lockdown) -- reuses the `SpatialDelta`
    type verbatim, never a second delta shape."""
    before_ids = set(before_registry.objects.keys())
    after_ids = set(after_registry.objects.keys())
    added = tuple(sorted(after_ids - before_ids))
    removed = tuple(sorted(before_ids - after_ids))
    modified = tuple(sorted(
        oid for oid in (before_ids & after_ids)
        if before_registry.objects[oid] != after_registry.objects[oid]
    ))
    return csa.SpatialDelta(added_object_ids=added, removed_object_ids=removed, modified_object_ids=modified)


def compare_lockdowns(registry: LockdownLineageRegistry, before_id: str, after_id: str) -> LineageComparisonResult:
    """Section 12: L0 vs L1 -- computes no new engineering/economic math,
    only diffs the already-bound spatial registries and result references."""
    before = registry.lockdowns[before_id]
    after = registry.lockdowns[after_id]
    delta = _registry_delta(before.spatial_state.registry, after.spatial_state.registry)
    rows = _economic_rows(before.economic_result, after.economic_result)
    return LineageComparisonResult(before_id=before_id, after_id=after_id, comparison_kind="LOCKDOWN_VS_LOCKDOWN", spatial_delta=delta, rows=rows)


def compare_lockdown_to_what_if(registry: LockdownLineageRegistry, what_if_id: str) -> LineageComparisonResult:
    """Section 13: generalizes `LockedVsWhatIfDayComparison` beyond its one
    hard-coded nuclear-speed path -- any What-If's recomputed results are
    comparable against its parent Lockdown's bound results."""
    what_if = registry.what_ifs[what_if_id]
    parent = registry.lockdowns[what_if.parent_lockdown_id]
    delta = csa.compute_delta(parent.spatial_state, what_if.what_if_scenario.what_if)
    rows = _economic_rows(parent.economic_result, what_if.economic_result)
    return LineageComparisonResult(before_id=parent.lockdown_id, after_id=what_if_id, comparison_kind="LOCKDOWN_VS_WHAT_IF", spatial_delta=delta, rows=rows)


# ---------------------------------------------------------------------------
# Serialization (section 15) -- reuses `csa.registry_to_json`/
# `registry_from_json` verbatim for spatial state; result references are
# preserved as plain dicts (via `dataclasses.asdict`) since their concrete
# types are not owned by this module and are never reconstructed here.
# ---------------------------------------------------------------------------


def _json_safe(value: object) -> object:
    """Phase 1B note: `asdict()` leaves `set`/`frozenset` values untouched
    (e.g. inside `canonical_entity_binding_authority.EntityBindingRegistry`'s
    reverse indexes); this recursively normalizes those (and any nested
    dict/list/tuple) into plain JSON-safe structures, sorted for determinism.
    Behavior for existing dataclasses without sets (economic/simulation/
    engineering results) is unchanged."""
    if isinstance(value, Mapping):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(_json_safe(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _serialize_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, Mapping):
        return _json_safe(dict(value))
    return repr(value)


def _result_to_serializable(result: object | None) -> dict | None:
    if result is None:
        return None
    if is_dataclass(result) and not isinstance(result, type):
        payload = _json_safe(asdict(result))
        payload["_result_type"] = f"{type(result).__module__}.{type(result).__qualname__}"
        return payload
    if isinstance(result, Mapping):
        return _json_safe(dict(result))
    raise TypeError(f"cannot serialize result of type {type(result)!r}")


def _serialize_active_change(change: maux.ActiveChange) -> dict:
    return {
        "change_id": change.change_id, "category": change.category, "kind": change.kind,
        "description": change.description, "locked_value": _serialize_value(change.locked_value),
        "what_if_value": _serialize_value(change.what_if_value), "timestamp": change.timestamp,
        "status": change.status, "parameter_id": change.parameter_id,
    }


def _deserialize_active_change(data: dict) -> maux.ActiveChange:
    return maux.ActiveChange(
        change_id=data["change_id"], category=data["category"], kind=data["kind"], description=data["description"],
        locked_value=data["locked_value"], what_if_value=data["what_if_value"], timestamp=data["timestamp"],
        status=data["status"], spatial_changeset=None, parameter_id=data["parameter_id"],
    )


def serialize_lockdown(record: CanonicalLockdownRecord) -> dict:
    return {
        "schema_version": LOCKDOWN_LINEAGE_SCHEMA_VERSION,
        "lockdown_id": record.lockdown_id, "parent_lockdown_id": record.parent_lockdown_id,
        "source_what_if_id": record.source_what_if_id, "created_at": record.created_at,
        "spatial_state_registry": csa.registry_to_json(record.spatial_state.registry),
        "active_parameters": dict(record.active_parameters),
        "simulation_result": _result_to_serializable(record.simulation_result),
        "engineering_result": _result_to_serializable(record.engineering_result),
        "economic_result": _result_to_serializable(record.economic_result),
        "entity_bindings": _result_to_serializable(record.entity_bindings),
        "reason": record.reason, "status": record.status,
    }


def deserialize_lockdown(data: dict) -> CanonicalLockdownRecord:
    registry = csa.registry_from_json(data["spatial_state_registry"])
    return CanonicalLockdownRecord(
        lockdown_id=data["lockdown_id"], parent_lockdown_id=data["parent_lockdown_id"],
        source_what_if_id=data["source_what_if_id"], created_at=data["created_at"],
        spatial_state=csa.LockedSpatialState(registry=registry), active_parameters=dict(data["active_parameters"]),
        simulation_result=data["simulation_result"], engineering_result=data["engineering_result"],
        economic_result=data["economic_result"], reason=data["reason"], status=data["status"],
        entity_bindings=data.get("entity_bindings"),
    )


def serialize_what_if(record: CanonicalWhatIfRecord) -> dict:
    scenario = record.what_if_scenario
    return {
        "schema_version": LOCKDOWN_LINEAGE_SCHEMA_VERSION,
        "what_if_id": record.what_if_id, "parent_lockdown_id": record.parent_lockdown_id, "created_at": record.created_at,
        "base_locked_state_id": scenario.base_locked_state_id,
        "what_if_registry": csa.registry_to_json(scenario.what_if.registry),
        "promoted": scenario.what_if.promoted,
        "active_changes": [_serialize_active_change(c) for c in scenario.active_changes],
        "simulation_result": _result_to_serializable(record.simulation_result),
        "engineering_result": _result_to_serializable(record.engineering_result),
        "economic_result": _result_to_serializable(record.economic_result),
        "entity_bindings": _result_to_serializable(record.entity_bindings),
        "status": record.status,
    }


def deserialize_what_if(data: dict, *, parent_locked: csa.LockedSpatialState) -> CanonicalWhatIfRecord:
    what_if_state = csa.WhatIfSpatialState(base=parent_locked, registry=csa.registry_from_json(data["what_if_registry"]), promoted=data["promoted"])
    active_changes = [_deserialize_active_change(c) for c in data["active_changes"]]
    scenario = maux.UnifiedWhatIfScenario(
        scenario_id=data["what_if_id"], base_locked_state_id=data["base_locked_state_id"], locked=parent_locked,
        what_if=what_if_state, active_changes=active_changes,
    )
    return CanonicalWhatIfRecord(
        what_if_id=data["what_if_id"], parent_lockdown_id=data["parent_lockdown_id"], created_at=data["created_at"],
        what_if_scenario=scenario, simulation_result=data["simulation_result"], engineering_result=data["engineering_result"],
        economic_result=data["economic_result"], status=data["status"], entity_bindings=data.get("entity_bindings"),
    )


def serialize_lineage_registry(registry: LockdownLineageRegistry) -> dict:
    return {
        "schema_version": LOCKDOWN_LINEAGE_SCHEMA_VERSION,
        "current_lockdown_id": registry.current_lockdown_id,
        "lockdowns": [serialize_lockdown(r) for r in registry.lockdowns.values()],
        "what_ifs": [serialize_what_if(r) for r in registry.what_ifs.values()],
        "plan_version_scenario": [
            {"version_id": b.version_id, "lockdown_id": b.lockdown_id, "what_if_id": b.what_if_id}
            for b in registry.plan_version_scenario.values()
        ],
    }


def deserialize_lineage_registry(data: dict) -> LockdownLineageRegistry:
    registry = LockdownLineageRegistry()
    for raw in data["lockdowns"]:
        record = deserialize_lockdown(raw)
        registry.lockdowns[record.lockdown_id] = record
    for raw in data["what_ifs"]:
        parent = registry.lockdowns[raw["parent_lockdown_id"]]
        record = deserialize_what_if(raw, parent_locked=parent.spatial_state)
        registry.what_ifs[record.what_if_id] = record
    for raw in data["plan_version_scenario"]:
        registry.plan_version_scenario[raw["version_id"]] = PlanVersionScenarioBinding(
            version_id=raw["version_id"], lockdown_id=raw["lockdown_id"], what_if_id=raw["what_if_id"],
        )
    registry.current_lockdown_id = data["current_lockdown_id"]
    return registry


def lineage_registry_to_json(registry: LockdownLineageRegistry) -> str:
    return json.dumps(serialize_lineage_registry(registry), sort_keys=True)


def lineage_registry_from_json(payload: str) -> LockdownLineageRegistry:
    return deserialize_lineage_registry(json.loads(payload))

"""Focused tests for lockdown_what_if_lineage_authority.py -- Phase 1A
unified Lockdown/What-If identity and result-lineage binding.

Covers: immutable parent Lockdown, branch identity, saved What-If, discard,
promotion, parent/source lineage, current-Lockdown authority, no silent
promotion, result binding, PlanVersion scenario binding, serialization/
reload, and Lockdown-vs-Lockdown / Lockdown-vs-What-If comparison.
"""

from __future__ import annotations

import dataclasses

import pytest

import canonical_spatial_authority as csa
import lockdown_what_if_lineage_authority as lla


def _build_registry() -> csa.SpatialObjectRegistry:
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    csa.add_building(reg, facility_id="FAC-001", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="BLDG-A-F1-R01")
    return reg


@dataclasses.dataclass(frozen=True)
class _FakeEconomicResult:
    total_capex_usd: float
    total_annual_opex_usd: float
    annual_revenue_usd: float
    npv_usd: float
    payback_years: float
    irr_pct: float


def _registry_with_first_lockdown() -> tuple[lla.LockdownLineageRegistry, lla.CanonicalLockdownRecord]:
    registry = lla.LockdownLineageRegistry()
    locked = csa.LockedSpatialState(registry=_build_registry())
    econ = _FakeEconomicResult(total_capex_usd=1_000_000.0, total_annual_opex_usd=200_000.0, annual_revenue_usd=500_000.0, npv_usd=100_000.0, payback_years=4.0, irr_pct=12.0)
    l0 = lla.create_first_lockdown(registry, locked=locked, active_parameters={"carrier_speed": 10.0}, economic_result=econ, reason="initial simulation")
    return registry, l0


# ---------------------------------------------------------------------------
# First Lockdown (section 7)
# ---------------------------------------------------------------------------


def test_first_lockdown_has_no_parent_or_source():
    registry, l0 = _registry_with_first_lockdown()
    assert l0.parent_lockdown_id is None
    assert l0.source_what_if_id is None
    assert l0.status == "CURRENT"
    assert registry.current_lockdown_id == l0.lockdown_id


def test_cannot_create_a_second_first_lockdown():
    registry, _ = _registry_with_first_lockdown()
    with pytest.raises(ValueError):
        lla.create_first_lockdown(registry, locked=csa.LockedSpatialState(registry=_build_registry()))


# ---------------------------------------------------------------------------
# Branch identity (sections 2, 4)
# ---------------------------------------------------------------------------


def test_branch_what_if_never_mutates_parent_lockdown():
    registry, l0 = _registry_with_first_lockdown()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    assert w1.parent_lockdown_id == l0.lockdown_id
    assert w1.status == "ACTIVE"

    moved = dataclasses.replace(w1.what_if_scenario.what_if.registry.get("BLDG-A-F1-R01"), transform=csa.Transform(position_x=99.0))
    csa.apply_changeset(w1.what_if_scenario.what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-A-F1-R01", new_object=moved)

    assert l0.spatial_state.registry.get("BLDG-A-F1-R01").transform.position_x == 0.0
    assert w1.what_if_scenario.what_if.registry.get("BLDG-A-F1-R01").transform.position_x == 99.0
    assert registry.current_lockdown_id == l0.lockdown_id


# ---------------------------------------------------------------------------
# Saved What-If (section 5)
# ---------------------------------------------------------------------------


def test_save_what_if_view_then_reopen():
    registry, l0 = _registry_with_first_lockdown()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    saved = lla.save_what_if_view(registry, w1.what_if_id)
    assert saved.status == "SAVED_VIEW"
    assert registry.current_lockdown_id == l0.lockdown_id

    reopened = lla.reopen_saved_what_if(registry, w1.what_if_id)
    assert reopened.status == "ACTIVE"


def test_cannot_save_a_discarded_what_if():
    registry, l0 = _registry_with_first_lockdown()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    lla.discard_what_if(registry, w1.what_if_id)
    with pytest.raises(ValueError):
        lla.save_what_if_view(registry, w1.what_if_id)


# ---------------------------------------------------------------------------
# Discard (section 3/16)
# ---------------------------------------------------------------------------


def test_discard_what_if_preserves_current_lockdown():
    registry, l0 = _registry_with_first_lockdown()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    discarded = lla.discard_what_if(registry, w1.what_if_id)
    assert discarded.status == "DISCARDED"
    assert registry.current_lockdown_id == l0.lockdown_id
    assert w1.what_if_id in registry.what_ifs  # preserved for audit, not deleted


# ---------------------------------------------------------------------------
# Promotion (sections 6, 16)
# ---------------------------------------------------------------------------


def test_promotion_creates_new_lockdown_and_preserves_parent():
    registry, l0 = _registry_with_first_lockdown()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    moved = dataclasses.replace(w1.what_if_scenario.what_if.registry.get("BLDG-A-F1-R01"), transform=csa.Transform(position_x=42.0))
    csa.apply_changeset(w1.what_if_scenario.what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-A-F1-R01", new_object=moved)

    l1 = lla.promote_what_if_to_lockdown(registry, w1.what_if_id, reason="accepted PET-02 relocation")

    assert l1.parent_lockdown_id == l0.lockdown_id
    assert l1.source_what_if_id == w1.what_if_id
    assert l1.status == "CURRENT"
    assert l1.spatial_state.registry.get("BLDG-A-F1-R01").transform.position_x == 42.0

    # L0 remains preserved, untouched, just superseded.
    stored_l0 = registry.lockdown(l0.lockdown_id)
    assert stored_l0.status == "SUPERSEDED"
    assert stored_l0.spatial_state.registry.get("BLDG-A-F1-R01").transform.position_x == 0.0
    assert registry.what_if(w1.what_if_id).status == "PROMOTED_TO_LOCKDOWN"
    assert registry.current_lockdown_id == l1.lockdown_id


def test_cannot_promote_a_discarded_what_if():
    registry, l0 = _registry_with_first_lockdown()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    lla.discard_what_if(registry, w1.what_if_id)
    with pytest.raises(ValueError):
        lla.promote_what_if_to_lockdown(registry, w1.what_if_id)


# ---------------------------------------------------------------------------
# Required transition model (section 16)
# ---------------------------------------------------------------------------


def test_required_transition_model_end_to_end():
    registry, l0 = _registry_with_first_lockdown()

    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    lla.discard_what_if(registry, w1.what_if_id)
    assert registry.current_lockdown_id == l0.lockdown_id

    w2 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    lla.save_what_if_view(registry, w2.what_if_id)
    assert registry.what_if(w2.what_if_id).status == "SAVED_VIEW"
    assert registry.current_lockdown_id == l0.lockdown_id

    l1 = lla.promote_what_if_to_lockdown(registry, w2.what_if_id)
    assert l1.parent_lockdown_id == l0.lockdown_id
    assert l1.source_what_if_id == w2.what_if_id
    assert registry.lockdown(l0.lockdown_id).status == "SUPERSEDED"
    assert registry.current_lockdown_id == l1.lockdown_id


# ---------------------------------------------------------------------------
# No silent promotion (section 14)
# ---------------------------------------------------------------------------


def test_no_action_other_than_promotion_changes_current_lockdown():
    registry, l0 = _registry_with_first_lockdown()
    baseline_current = registry.current_lockdown_id

    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    assert registry.current_lockdown_id == baseline_current  # drag/drop-equivalent branch

    lla.update_what_if_results(registry, w1.what_if_id, economic_result=_FakeEconomicResult(1.0, 1.0, 1.0, 1.0, 1.0, 1.0))
    assert registry.current_lockdown_id == baseline_current  # parameter edit / recompute

    lla.save_what_if_view(registry, w1.what_if_id)
    assert registry.current_lockdown_id == baseline_current  # saving a What-If

    lla.reopen_saved_what_if(registry, w1.what_if_id)
    assert registry.current_lockdown_id == baseline_current

    lla.discard_what_if(registry, w1.what_if_id)
    assert registry.current_lockdown_id == baseline_current  # closing/discarding a What-If

    w2 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    assert registry.current_lockdown_id == baseline_current
    lla.promote_what_if_to_lockdown(registry, w2.what_if_id)
    assert registry.current_lockdown_id != baseline_current  # ONLY promotion changes it


# ---------------------------------------------------------------------------
# Result binding (section 8)
# ---------------------------------------------------------------------------


def test_result_binding_round_trips_by_reference():
    registry, l0 = _registry_with_first_lockdown()
    assert l0.economic_result.total_capex_usd == 1_000_000.0
    assert l0.economic_result.npv_usd == 100_000.0

    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    econ = _FakeEconomicResult(total_capex_usd=1_200_000.0, total_annual_opex_usd=180_000.0, annual_revenue_usd=520_000.0, npv_usd=140_000.0, payback_years=3.6, irr_pct=15.0)
    lla.update_what_if_results(registry, w1.what_if_id, economic_result=econ)
    assert registry.what_if(w1.what_if_id).economic_result is econ


def test_cannot_update_results_on_a_promoted_what_if():
    registry, l0 = _registry_with_first_lockdown()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    lla.promote_what_if_to_lockdown(registry, w1.what_if_id)
    with pytest.raises(ValueError):
        lla.update_what_if_results(registry, w1.what_if_id, economic_result=None if False else _FakeEconomicResult(1, 1, 1, 1, 1, 1))


# ---------------------------------------------------------------------------
# PlanVersion scenario binding (section 9-10)
# ---------------------------------------------------------------------------


def test_plan_version_binds_to_lockdown_or_what_if():
    registry, l0 = _registry_with_first_lockdown()
    binding = lla.bind_plan_version(registry, version_id="PLAN-0000", lockdown_id=l0.lockdown_id)
    assert lla.resolve_plan_version_scenario(registry, "PLAN-0000") == binding
    assert binding.what_if_id is None

    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    binding2 = lla.bind_plan_version(registry, version_id="PLAN-0001", what_if_id=w1.what_if_id)
    assert binding2.lockdown_id is None
    assert lla.resolve_plan_version_scenario(registry, "PLAN-0001").what_if_id == w1.what_if_id


def test_plan_version_binding_requires_exactly_one_scenario_reference():
    registry, l0 = _registry_with_first_lockdown()
    with pytest.raises(ValueError):
        lla.bind_plan_version(registry, version_id="PLAN-X")
    with pytest.raises(ValueError):
        w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
        lla.bind_plan_version(registry, version_id="PLAN-Y", lockdown_id=l0.lockdown_id, what_if_id=w1.what_if_id)


# ---------------------------------------------------------------------------
# Comparison (sections 12-13)
# ---------------------------------------------------------------------------


def test_compare_lockdowns_reports_geometry_and_economic_delta():
    registry, l0 = _registry_with_first_lockdown()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    moved = dataclasses.replace(w1.what_if_scenario.what_if.registry.get("BLDG-A-F1-R01"), transform=csa.Transform(position_x=42.0))
    csa.apply_changeset(w1.what_if_scenario.what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-A-F1-R01", new_object=moved)
    econ = _FakeEconomicResult(total_capex_usd=1_100_000.0, total_annual_opex_usd=190_000.0, annual_revenue_usd=510_000.0, npv_usd=130_000.0, payback_years=3.8, irr_pct=14.0)
    lla.update_what_if_results(registry, w1.what_if_id, economic_result=econ)
    l1 = lla.promote_what_if_to_lockdown(registry, w1.what_if_id)

    comparison = lla.compare_lockdowns(registry, l0.lockdown_id, l1.lockdown_id)
    assert comparison.comparison_kind == "LOCKDOWN_VS_LOCKDOWN"
    assert "BLDG-A-F1-R01" in comparison.spatial_delta.modified_object_ids
    capex_row = next(r for r in comparison.rows if r.metric == "capex")
    assert capex_row.delta == pytest.approx(100_000.0)
    assert capex_row.status == "DEGRADED"  # higher capex is not better
    npv_row = next(r for r in comparison.rows if r.metric == "npv")
    assert npv_row.status == "IMPROVED"


def test_compare_lockdown_to_what_if_generalizes_beyond_one_parameter():
    registry, l0 = _registry_with_first_lockdown()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    econ = _FakeEconomicResult(total_capex_usd=900_000.0, total_annual_opex_usd=210_000.0, annual_revenue_usd=480_000.0, npv_usd=80_000.0, payback_years=4.5, irr_pct=10.0)
    lla.update_what_if_results(registry, w1.what_if_id, economic_result=econ)

    comparison = lla.compare_lockdown_to_what_if(registry, w1.what_if_id)
    assert comparison.comparison_kind == "LOCKDOWN_VS_WHAT_IF"
    capex_row = next(r for r in comparison.rows if r.metric == "capex")
    assert capex_row.status == "IMPROVED"  # lower capex is better


def test_comparison_marks_missing_result_as_not_available():
    registry, l0 = _registry_with_first_lockdown()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    comparison = lla.compare_lockdown_to_what_if(registry, w1.what_if_id)
    assert all(row.status == "NOT_AVAILABLE" for row in comparison.rows)


# ---------------------------------------------------------------------------
# Serialization / reload (section 15)
# ---------------------------------------------------------------------------


def test_lineage_registry_survives_save_and_reload():
    registry, l0 = _registry_with_first_lockdown()
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    moved = dataclasses.replace(w1.what_if_scenario.what_if.registry.get("BLDG-A-F1-R01"), transform=csa.Transform(position_x=17.0))
    csa.apply_changeset(w1.what_if_scenario.what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-A-F1-R01", new_object=moved)
    maux_scenario = w1.what_if_scenario
    import mrt_auxiliary_systems_authority as maux
    maux.record_parameter_change(maux_scenario, category="TRANSPORT_MRT", parameter_id="carrier_speed", locked_value=10.0, what_if_value=15.0, description="speed what-if")
    econ = _FakeEconomicResult(total_capex_usd=1_050_000.0, total_annual_opex_usd=205_000.0, annual_revenue_usd=505_000.0, npv_usd=95_000.0, payback_years=4.1, irr_pct=11.0)
    lla.update_what_if_results(registry, w1.what_if_id, economic_result=econ)
    lla.save_what_if_view(registry, w1.what_if_id)
    lla.bind_plan_version(registry, version_id="PLAN-0000", lockdown_id=l0.lockdown_id)

    payload = lla.lineage_registry_to_json(registry)
    reloaded = lla.lineage_registry_from_json(payload)

    assert reloaded.current_lockdown_id == registry.current_lockdown_id
    reloaded_l0 = reloaded.lockdown(l0.lockdown_id)
    assert reloaded_l0.parent_lockdown_id is None
    assert reloaded_l0.economic_result["total_capex_usd"] == 1_000_000.0
    assert reloaded_l0.active_parameters == {"carrier_speed": 10.0}

    reloaded_w1 = reloaded.what_if(w1.what_if_id)
    assert reloaded_w1.parent_lockdown_id == l0.lockdown_id
    assert reloaded_w1.status == "SAVED_VIEW"
    assert reloaded_w1.what_if_scenario.what_if.registry.get("BLDG-A-F1-R01").transform.position_x == 17.0
    assert reloaded_w1.active_parameters == {"carrier_speed": 15.0}
    assert reloaded_w1.economic_result["total_capex_usd"] == 1_050_000.0

    assert lla.resolve_plan_version_scenario(reloaded, "PLAN-0000").lockdown_id == l0.lockdown_id

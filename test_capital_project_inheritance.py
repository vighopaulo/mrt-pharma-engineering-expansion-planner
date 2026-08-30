"""KIRO Super-Build 3 tests -- capital-project inheritance & economic scope.

Covers: 3 project classes, 7 asset economic states, physical != economic
inheritance, BIM economic governor, capacity-delta, material/equipment/
transport economic scope, incremental CapEx, OPEX inheritance (baseline vs
incremental, savings preserved, no-silent-zero, NOT_CALIBRATED preserved),
and all Sec 22-30 deterministic scenario controls.
"""
from __future__ import annotations

import pytest

import capital_project_inheritance_authority as cap
import capital_project_inheritance_scenarios as scn


# --- Sec 1-2: three project classes ---------------------------------------

def test_exactly_three_project_classes():
    assert cap.CANONICAL_PROJECT_CLASSES == (
        "EXISTING_FACILITY_RETROFIT", "EXISTING_FACILITY_EXPANSION", "GREENFIELD_NEW_FACILITY",
    )


def test_retrofit_and_expansion_inherit_existing():
    assert cap.PROJECT_CLASS_INHERITS_EXISTING["EXISTING_FACILITY_RETROFIT"]
    assert cap.PROJECT_CLASS_INHERITS_EXISTING["EXISTING_FACILITY_EXPANSION"]


def test_greenfield_does_not_inherit_existing():
    assert not cap.PROJECT_CLASS_INHERITS_EXISTING["GREENFIELD_NEW_FACILITY"]


def test_scope_object_requires_baseline_for_inheriting_classes():
    with pytest.raises(ValueError):
        cap.CapitalProjectScope(project_id="P", project_class="EXISTING_FACILITY_RETROFIT", baseline_facility_id=None)
    with pytest.raises(ValueError):
        cap.CapitalProjectScope(project_id="P", project_class="EXISTING_FACILITY_EXPANSION", baseline_facility_id=None)


def test_scope_object_greenfield_needs_no_baseline():
    s = cap.CapitalProjectScope(project_id="P", project_class="GREENFIELD_NEW_FACILITY", baseline_facility_id=None)
    assert not s.inherits_existing_facility()


def test_scope_object_rejects_unknown_class():
    with pytest.raises(ValueError):
        cap.CapitalProjectScope(project_id="P", project_class="BOGUS", baseline_facility_id="F")  # type: ignore[arg-type]


# --- Sec 8-16: seven asset economic states --------------------------------

def test_exactly_seven_asset_economic_states():
    assert cap.CANONICAL_ASSET_ECONOMIC_STATES == (
        "INHERITED_EXISTING", "RETAINED_NO_CHANGE", "MODIFY", "REPLACE", "NEW", "REMOVE", "OUT_OF_SCOPE",
    )


@pytest.mark.parametrize("state,charges", [
    ("INHERITED_EXISTING", False), ("RETAINED_NO_CHANGE", False), ("MODIFY", False),
    ("REPLACE", True), ("NEW", True), ("REMOVE", False), ("OUT_OF_SCOPE", False),
])
def test_full_acquisition_charge_by_state(state, charges):
    assert cap.state_charges_full_acquisition_capex(state) == charges


def test_removed_asset_leaves_target_capacity():
    assert not cap.state_contributes_target_capacity("REMOVE")


def test_out_of_scope_still_physically_present_for_capacity():
    # Sec 15/16: physical presence vs economic scope are distinct
    assert cap.state_contributes_target_capacity("OUT_OF_SCOPE")
    assert not cap.state_contributes_target_opex("OUT_OF_SCOPE")


def test_inherited_contributes_target_capacity_and_opex():
    assert cap.state_contributes_target_capacity("INHERITED_EXISTING")
    assert cap.state_contributes_target_opex("INHERITED_EXISTING")


# --- Sec 9-15: charged_capex per state ------------------------------------

def test_inherited_existing_charges_zero_capex():
    r = cap.AssetEconomicRecord("A", "SCANNER", "INHERITED_EXISTING", full_acquisition_capex_usd=2_000_000.0)
    charged, status, unknown = r.charged_capex()
    assert charged == 0.0 and status == "INHERITED_NO_NEW_CAPEX" and not unknown


def test_retained_no_change_charges_zero_capex():
    r = cap.AssetEconomicRecord("A", "HVAC", "RETAINED_NO_CHANGE", full_acquisition_capex_usd=1_000_000.0)
    assert r.charged_capex()[0] == 0.0


def test_new_charges_full_acquisition():
    r = cap.AssetEconomicRecord("A", "SCANNER", "NEW", full_acquisition_capex_usd=2_000_000.0)
    assert r.charged_capex()[0] == 2_000_000.0


def test_modify_charges_only_modification():
    r = cap.AssetEconomicRecord("A", "SHIELDING", "MODIFY", full_acquisition_capex_usd=999_999.0, modification_capex_usd=250_000.0)
    charged, status, _ = r.charged_capex()
    assert charged == 250_000.0 and status == "MODIFICATION_ONLY"


def test_replace_charges_replacement_plus_removal_not_original():
    r = cap.AssetEconomicRecord("A", "SCANNER", "REPLACE", full_acquisition_capex_usd=2_000_000.0,
                                replacement_capex_usd=1_800_000.0, removal_capex_usd=50_000.0)
    charged, status, _ = r.charged_capex()
    assert charged == 1_850_000.0 and status == "REPLACEMENT"


def test_out_of_scope_charges_zero():
    r = cap.AssetEconomicRecord("A", "STRUCTURE", "OUT_OF_SCOPE", full_acquisition_capex_usd=5_000_000.0)
    assert r.charged_capex()[0] == 0.0


def test_new_unknown_capex_not_zero_filled():
    r = cap.AssetEconomicRecord("A", "SCANNER", "NEW", full_acquisition_capex_usd=None)
    charged, status, unknown = r.charged_capex()
    assert status == "NOT_CALIBRATED" and unknown  # surfaced, not silently 0
    assert charged == 0.0  # not added to a real subtotal (see aggregation test)


# --- Sec 16-18: physical != economic + BIM governor -----------------------

def test_bim_present_retrofit_defaults_inherited_not_new():
    assert cap.bim_object_default_economic_state(project_class="EXISTING_FACILITY_RETROFIT") == "INHERITED_EXISTING"


def test_bim_present_expansion_untouched_defaults_inherited():
    assert cap.bim_object_default_economic_state(project_class="EXISTING_FACILITY_EXPANSION") == "INHERITED_EXISTING"


def test_bim_intervention_becomes_new():
    assert cap.bim_object_default_economic_state(project_class="EXISTING_FACILITY_RETROFIT", is_project_intervention=True) == "NEW"


def test_bim_greenfield_all_new():
    assert cap.bim_object_default_economic_state(project_class="GREENFIELD_NEW_FACILITY") == "NEW"


def test_bim_object_present_does_not_charge_new_capex():
    assert not cap.bim_object_charges_new_capex("INHERITED_EXISTING")
    assert not cap.bim_object_charges_new_capex("RETAINED_NO_CHANGE")
    assert cap.bim_object_charges_new_capex("NEW")
    assert cap.bim_object_charges_new_capex("REPLACE")


# --- Sec 21-26: capacity delta --------------------------------------------

def test_capacity_delta_incremental_formula():
    r = cap.compute_capacity_delta(cap.CapacityDeltaInputs("scanner", existing_usable_units=2, target_required_units=3, unit_capex_usd=2_000_000.0))
    assert r.new_units_required == 1 and r.acquisition_quantity == 1 and r.new_capex_usd == 2_000_000.0


def test_capacity_delta_no_shortfall_zero_new():
    r = cap.compute_capacity_delta(cap.CapacityDeltaInputs("cyclotron", existing_usable_units=1, target_required_units=1, unit_capex_usd=3_000_000.0))
    assert r.new_units_required == 0 and r.new_capex_usd == 0.0


def test_capacity_delta_unknown_unit_cost_not_calibrated():
    r = cap.compute_capacity_delta(cap.CapacityDeltaInputs("scanner", existing_usable_units=2, target_required_units=3))
    assert r.new_capex_usd is None and r.capex_status == "NOT_CALIBRATED"


def test_capacity_delta_replacement_acquisition_includes_replaced():
    r = cap.compute_capacity_delta(cap.CapacityDeltaInputs("scanner", existing_usable_units=2, target_required_units=3, replaced_units=1, unit_capex_usd=2_000_000.0))
    assert r.retained_units == 1 and r.new_units_required == 1 and r.acquisition_quantity == 2


def test_capacity_delta_rejects_replaced_exceeding_existing():
    with pytest.raises(ValueError):
        cap.CapacityDeltaInputs("scanner", existing_usable_units=1, target_required_units=3, replaced_units=2)


def test_capacity_delta_removed_reduces_retained():
    r = cap.compute_capacity_delta(cap.CapacityDeltaInputs("bed", existing_usable_units=30, target_required_units=40, removed_units=5, unit_capex_usd=100.0))
    # retained 25, target 40 -> new 15
    assert r.retained_units == 25 and r.new_units_required == 15


# --- Sec 28: incremental capex aggregation --------------------------------

def test_incremental_capex_inherited_excluded_disclosed():
    recs = [
        cap.AssetEconomicRecord("S1", "SCANNER", "INHERITED_EXISTING", full_acquisition_capex_usd=2_000_000.0),
        cap.AssetEconomicRecord("S2", "SCANNER", "NEW", full_acquisition_capex_usd=2_000_000.0),
    ]
    ic = cap.aggregate_incremental_capex(project_class="EXISTING_FACILITY_EXPANSION", records=recs)
    assert ic.total_incremental_capex_usd == 2_000_000.0
    assert ic.inherited_asset_value_excluded_usd == 2_000_000.0


def test_incremental_capex_unknown_surfaced_not_summed():
    recs = [cap.AssetEconomicRecord("S", "SCANNER", "NEW", full_acquisition_capex_usd=None)]
    ic = cap.aggregate_incremental_capex(project_class="GREENFIELD_NEW_FACILITY", records=recs)
    assert ic.total_incremental_capex_usd == 0.0
    assert ic.unknown_capex_components  # not silently zeroed away


# --- Sec 39: OPEX inheritance ---------------------------------------------

def test_opex_retained_scanner_keeps_baseline_zero_incremental():
    op = cap.compute_opex_inheritance([
        cap.OpexInheritanceRecord("S", "RETAINED_NO_CHANGE", baseline_annual_opex_usd=200_000.0),
    ])
    assert op.existing_baseline_opex_usd == 200_000.0
    assert op.retained_existing_opex_usd == 200_000.0
    assert op.target_total_opex_usd == 200_000.0
    assert op.incremental_project_opex_usd in (None, 0.0)


def test_opex_new_scanner_incremental_equals_new():
    op = cap.compute_opex_inheritance([
        cap.OpexInheritanceRecord("S1", "RETAINED_NO_CHANGE", baseline_annual_opex_usd=200_000.0),
        cap.OpexInheritanceRecord("S2", "RETAINED_NO_CHANGE", baseline_annual_opex_usd=200_000.0),
        cap.OpexInheritanceRecord("SN", "NEW", target_annual_opex_usd=180_000.0),
    ])
    assert op.existing_baseline_opex_usd == 400_000.0
    assert op.new_asset_opex_usd == 180_000.0
    assert op.target_total_opex_usd == 580_000.0
    assert op.incremental_project_opex_usd == 180_000.0


def test_opex_replacement_displaces_baseline_producing_saving():
    op = cap.compute_opex_inheritance([
        cap.OpexInheritanceRecord("S", "REPLACE", baseline_annual_opex_usd=200_000.0, target_annual_opex_usd=150_000.0),
    ])
    assert op.incremental_project_opex_usd == -50_000.0
    assert op.opex_savings_present


def test_opex_modification_saving_visible():
    op = cap.compute_opex_inheritance([
        cap.OpexInheritanceRecord("HVAC", "MODIFY", baseline_annual_opex_usd=100_000.0, target_annual_opex_usd=80_000.0),
    ])
    assert op.incremental_project_opex_usd == -20_000.0
    assert op.target_total_opex_usd == 80_000.0


def test_opex_removed_asset_not_in_target():
    op = cap.compute_opex_inheritance([
        cap.OpexInheritanceRecord("OLD", "REMOVE", baseline_annual_opex_usd=90_000.0),
    ])
    assert op.removed_existing_opex_usd == 90_000.0
    # removed opex is a saving; not retained in target
    assert op.incremental_project_opex_usd == -90_000.0


def test_opex_inherited_not_zeroed_by_inherited_capex():
    # an inherited scanner has $0 new capex but nonzero OPEX
    op = cap.compute_opex_inheritance([
        cap.OpexInheritanceRecord("S", "INHERITED_EXISTING", baseline_annual_opex_usd=200_000.0),
    ])
    assert op.target_total_opex_usd == 200_000.0  # NOT zero


def test_opex_unknown_baseline_not_zero_filled():
    op = cap.compute_opex_inheritance([
        cap.OpexInheritanceRecord("X", "RETAINED_NO_CHANGE", baseline_annual_opex_usd=None),
    ])
    assert not op.reconciled
    assert op.unknown_baseline_components


def test_opex_out_of_scope_excluded():
    op = cap.compute_opex_inheritance([
        cap.OpexInheritanceRecord("OOS", "OUT_OF_SCOPE", baseline_annual_opex_usd=500_000.0),
    ])
    assert op.target_total_opex_usd in (None, 0.0)


# --- Sec 31-33: material / equipment economic scope -----------------------

def test_material_scope_default_all_on():
    s = cap.EconomicScopeSettings()
    for c in cap.CANONICAL_MATERIAL_SYSTEM_CATEGORIES:
        assert s.material_in_economic_scope(c)


def test_material_scope_off_does_not_delete_physical():
    s = cap.EconomicScopeSettings().with_material_off("HVAC")
    assert not s.material_in_economic_scope("HVAC")
    # doctrine: economic OFF != physically absent -- other categories unaffected
    assert s.material_in_economic_scope("STRUCTURE")


def test_equipment_scope_off():
    s = cap.EconomicScopeSettings().with_equipment_off("SCANNER")
    assert not s.equipment_in_economic_scope("SCANNER")
    assert s.equipment_in_economic_scope("CYCLOTRON")


def test_out_of_scope_record_zero_capex_when_scope_off():
    r = cap.AssetEconomicRecord("A", "HVAC", "MODIFY", modification_capex_usd=100_000.0, in_economic_scope=False)
    assert r.charged_capex()[0] == 0.0


# --- Sec 22-30 scenario controls ------------------------------------------

def test_sec22_scanner_delta_control():
    r = scn.scanner_delta_control()
    assert r.new_units_required == 1 and r.acquisition_quantity == 1


def test_sec23_scanner_replacement_control_buys_two_not_three():
    assert scn.scanner_replacement_control().acquisition_quantity == 2


def test_sec24_cyclotron_within_capacity_zero_new():
    assert scn.cyclotron_within_capacity_control().new_units_required == 0


def test_sec24_cyclotron_shortfall_one_new():
    assert scn.cyclotron_shortfall_control().new_units_required == 1


def test_sec25_generator_within_capacity_zero_new():
    assert scn.generator_within_capacity_control().new_units_required == 0


def test_sec26_bed_room_delta():
    b = scn.bed_room_delta_control()
    assert b.existing_beds == 30 and b.new_beds == 20 and b.target_beds == 50
    assert not b.existing_beds_charged_as_new


def test_sec27_new_wing_existing_not_recharged():
    w = scn.new_wing_control()
    assert not w.existing_hospital_recharged
    assert w.incremental_capex.total_incremental_capex_usd == 15_500_000.0


def test_sec28_vertical_expansion_only_new_floors_priced():
    v = scn.vertical_expansion_control()
    assert v.inherited_floor_count == 4 and v.new_floor_count == 4
    assert not v.all_floors_priced_as_new
    assert v.incremental_capex.total_incremental_capex_usd == 12_000_000.0


def test_sec29_retrofit_charges_only_modeled_work():
    rt = scn.retrofit_control()
    assert not rt.full_room_recosted
    assert rt.incremental_capex.total_incremental_capex_usd == 370_000.0


def test_sec30_greenfield_no_zero_cost_inheritance():
    gf = scn.greenfield_control()
    assert not gf.any_zero_cost_inheritance
    assert gf.incremental_capex.total_incremental_capex_usd == 37_000_000.0


# --- Sec 34-38: transport inheritance -------------------------------------

def test_sec37_pts_backbone_reused_only_new_stations_charged():
    pts = scn.pts_transport_inheritance_control()
    assert pts.new_quantity == 2
    assert pts.shared_backbone_reused
    assert pts.incremental_capex_usd == 90_000.0  # 2 * 45k, backbone NOT re-charged


def test_sec35_mrt_new_full_guideway_charged():
    mrt = scn.mrt_transport_new_control()
    assert mrt.new_quantity == 300
    assert mrt.incremental_capex_usd == 750_000.0


def test_transport_inheritance_unknown_unit_cost_not_calibrated():
    r = cap.compute_transport_inheritance(cap.TransportResourceInheritance(
        resource="AGV vehicles", existing_quantity=2, retained_quantity=2, removed_quantity=0,
        target_required_quantity=5))
    assert r.incremental_capex_usd is None and r.incremental_capex_status == "NOT_CALIBRATED"
    assert r.new_quantity == 3


# ===========================================================================
# CLARIFICATION A: asset origin vs project action are separate axes.
# ===========================================================================

def test_existing_retained_distinguishable():
    c = cap.AssetClassification("EXISTING_BASELINE", "RETAINED_NO_CHANGE")
    assert c.origin == "EXISTING_BASELINE" and c.action == "RETAINED_NO_CHANGE"
    assert c.economic_state == "RETAINED_NO_CHANGE"


def test_existing_modified_distinguishable():
    c = cap.AssetClassification("EXISTING_BASELINE", "MODIFY")
    assert c.origin == "EXISTING_BASELINE" and c.action == "MODIFY"
    assert c.economic_state == "MODIFY"


def test_existing_replaced_distinguishable():
    c = cap.AssetClassification("EXISTING_BASELINE", "REPLACE")
    assert c.origin == "EXISTING_BASELINE" and c.economic_state == "REPLACE"


def test_new_asset_origin_and_action_consistent():
    c = cap.AssetClassification("NEW_TO_PROJECT", "NEW")
    assert c.origin == "NEW_TO_PROJECT" and c.action == "NEW" and c.economic_state == "NEW"


def test_new_origin_incompatible_with_retain_modify_replace():
    for action in ("RETAINED_NO_CHANGE", "MODIFY", "REPLACE", "REMOVE"):
        with pytest.raises(ValueError):
            cap.AssetClassification("NEW_TO_PROJECT", action)  # type: ignore[arg-type]


def test_economic_state_decomposition_roundtrip():
    for st in cap.CANONICAL_ASSET_ECONOMIC_STATES:
        origin, action = cap.decompose_economic_state(st)
        # normalized state is stable (INHERITED_EXISTING normalizes to RETAINED_NO_CHANGE)
        norm = cap.economic_state_of(origin, action)
        assert norm in cap.CANONICAL_ASSET_ECONOMIC_STATES


def test_inherited_existing_and_retained_share_cost_treatment_but_are_axis_distinct():
    # same cost treatment ($0 new capex) ...
    for st in ("INHERITED_EXISTING", "RETAINED_NO_CHANGE"):
        r = cap.AssetEconomicRecord("A", "SCANNER", st, full_acquisition_capex_usd=2_000_000.0)
        assert r.charged_capex()[0] == 0.0
    # ... yet both decompose to the same explicit (origin, action), proving they
    # are representable without losing the axis distinction
    assert cap.decompose_economic_state("INHERITED_EXISTING") == ("EXISTING_BASELINE", "RETAINED_NO_CHANGE")


# ===========================================================================
# CLARIFICATION B: unknown OPEX identity (no triple counting).
# ===========================================================================

def test_one_unknown_source_appears_in_multiple_views():
    op = cap.compute_opex_inheritance([cap.OpexInheritanceRecord("X", "RETAINED_NO_CHANGE", baseline_annual_opex_usd=None)])
    # multiple reporting-view labels for traceability
    assert len(op.unknown_baseline_components) >= 2


def test_one_unknown_source_counted_once_economically():
    op = cap.compute_opex_inheritance([cap.OpexInheritanceRecord("X", "RETAINED_NO_CHANGE", baseline_annual_opex_usd=None)])
    assert op.distinct_unknown_count() == 1
    assert op.distinct_unknown_source_ids() == ("X:BASELINE",)


def test_unknown_opex_double_counting_absent_multi_asset():
    op = cap.compute_opex_inheritance([
        cap.OpexInheritanceRecord("A", "RETAINED_NO_CHANGE", baseline_annual_opex_usd=None),
        cap.OpexInheritanceRecord("B", "RETAINED_NO_CHANGE", baseline_annual_opex_usd=None),
    ])
    # two distinct sources, each once -- not 6 (3 views x 2 assets)
    assert op.distinct_unknown_count() == 2


# ===========================================================================
# CLARIFICATION C: transport package reconciliation.
# ===========================================================================

def test_guideway_line_alone_is_partial_not_total():
    r = cap.reconcile_transport_package(family="MRT", lines=[
        cap.TransportLineItem("MRT guideway (m)", "LINEAR", 0, 0, 300, unit_capex_usd=2500.0),
    ])
    assert r.known_incremental_capex_usd == 750_000.0
    assert r.completeness == "PARTIAL_PACKAGE"
    assert not r.is_total_project_capex


def test_complete_mrt_package_is_total():
    r = cap.reconcile_transport_package(family="MRT", lines=[
        cap.TransportLineItem("MRT guideway (m)", "LINEAR", 0, 0, 300, unit_capex_usd=2500.0),
        cap.TransportLineItem("MRT carriers", "DISCRETE_UNIT", 0, 0, 10, unit_capex_usd=2000.0),
        cap.TransportLineItem("MRT endpoints", "DISCRETE_UNIT", 0, 0, 4, unit_capex_usd=25000.0),
        cap.TransportLineItem("MRT controls", "SHARED_BACKBONE", 0, 0, 1, unit_capex_usd=80000.0),
        cap.TransportLineItem("MRT installation/integration", "INTEGRATION", 0, 0, 1, unit_capex_usd=40000.0),
    ])
    assert r.completeness == "COMPLETE_PACKAGE" and r.is_total_project_capex


def test_pts_shared_backbone_not_double_purchased():
    r = cap.reconcile_transport_package(family="PTS", lines=[
        cap.TransportLineItem("PTS backbone", "SHARED_BACKBONE", 1, 1, 1, shared_exists_in_baseline=True),
        cap.TransportLineItem("PTS blower capacity", "SHARED_CAPACITY", 1, 1, 1, shared_exists_in_baseline=True),
        cap.TransportLineItem("PTS controls", "SHARED_BACKBONE", 1, 1, 1, shared_exists_in_baseline=True),
        cap.TransportLineItem("PTS switches/diverters", "DISCRETE_UNIT", 2, 2, 2, unit_capex_usd=15000.0),
        cap.TransportLineItem("PTS stations", "DISCRETE_UNIT", 4, 4, 6, unit_capex_usd=45000.0),
        cap.TransportLineItem("PTS carriers", "DISCRETE_UNIT", 6, 6, 8, unit_capex_usd=1200.0),
    ])
    assert "PTS backbone" in r.shared_lines_reused
    # only new stations (2*45k) + new carriers (2*1200); backbone/controls/blower reused
    assert r.known_incremental_capex_usd == 90_000.0 + 2_400.0


def test_pts_blower_upgrade_charged_when_required():
    r = cap.reconcile_transport_package(family="PTS", lines=[
        cap.TransportLineItem("PTS backbone", "SHARED_BACKBONE", 1, 1, 1, shared_exists_in_baseline=True),
        cap.TransportLineItem("PTS blower capacity", "SHARED_CAPACITY", 1, 1, 1, shared_exists_in_baseline=True, upgrade_required=True, upgrade_capex_usd=60000.0),
        cap.TransportLineItem("PTS controls", "SHARED_BACKBONE", 1, 1, 1, shared_exists_in_baseline=True),
        cap.TransportLineItem("PTS switches/diverters", "DISCRETE_UNIT", 2, 2, 2, unit_capex_usd=15000.0),
        cap.TransportLineItem("PTS stations", "DISCRETE_UNIT", 4, 4, 4, unit_capex_usd=45000.0),
        cap.TransportLineItem("PTS carriers", "DISCRETE_UNIT", 6, 6, 6, unit_capex_usd=1200.0),
    ])
    assert r.known_incremental_capex_usd == 60_000.0  # only the blower upgrade


def test_rths_existing_track_not_double_purchased():
    r = cap.reconcile_transport_package(family="RTHS", lines=[
        cap.TransportLineItem("RTHS track", "LINEAR", 200, 200, 200, unit_capex_usd=3000.0),  # fully retained
        cap.TransportLineItem("RTHS stations", "DISCRETE_UNIT", 3, 3, 3, unit_capex_usd=40000.0),
        cap.TransportLineItem("RTHS switches", "DISCRETE_UNIT", 2, 2, 2, unit_capex_usd=20000.0),
        cap.TransportLineItem("RTHS vehicles", "DISCRETE_UNIT", 2, 2, 3, unit_capex_usd=100000.0),
        cap.TransportLineItem("RTHS controls", "SHARED_BACKBONE", 1, 1, 1, shared_exists_in_baseline=True),
        cap.TransportLineItem("RTHS vertical sections", "DISCRETE_UNIT", 1, 1, 1, unit_capex_usd=50000.0),
    ])
    # only 1 new vehicle (3-2)*100k; track fully retained -> $0
    assert r.known_incremental_capex_usd == 100_000.0


def test_agv_shared_platform_not_double_purchased():
    r = cap.reconcile_transport_package(family="AGV_AMR", lines=[
        cap.TransportLineItem("AGV vehicles (light)", "DISCRETE_UNIT", 3, 3, 4, unit_capex_usd=90000.0),
        cap.TransportLineItem("AGV vehicles (heavy)", "DISCRETE_UNIT", 0, 0, 1, unit_capex_usd=130000.0),
        cap.TransportLineItem("AGV chargers", "DISCRETE_UNIT", 2, 2, 2, unit_capex_usd=12000.0),
        cap.TransportLineItem("AGV fleet-management platform", "SHARED_BACKBONE", 1, 1, 1, shared_exists_in_baseline=True),
        cap.TransportLineItem("AGV door integration", "INTEGRATION", 4, 4, 4, unit_capex_usd=3000.0),
        cap.TransportLineItem("AGV elevator integration", "INTEGRATION", 2, 2, 2, unit_capex_usd=25000.0),
        cap.TransportLineItem("AGV network/controls", "SHARED_BACKBONE", 1, 1, 1, shared_exists_in_baseline=True),
    ])
    assert "AGV fleet-management platform" in r.shared_lines_reused
    # 1 new light (90k) + 1 new heavy (130k); platform reused
    assert r.known_incremental_capex_usd == 220_000.0


def test_partial_package_unknown_surfaced():
    r = cap.reconcile_transport_package(family="MRT", lines=[
        cap.TransportLineItem("MRT guideway (m)", "LINEAR", 0, 0, 300, unit_capex_usd=None),
    ])
    assert r.unknown_capex_components and r.completeness == "PARTIAL_PACKAGE"


# ===========================================================================
# CLARIFICATION D: material economic-scope runtime consumer.
# ===========================================================================

def _hvac_struct_records():
    return [
        cap.ScopedAssetRecord(cap.AssetEconomicRecord("HVAC-1", "HVAC", "NEW", full_acquisition_capex_usd=2_000_000.0), "HVAC"),
        cap.ScopedAssetRecord(cap.AssetEconomicRecord("STRUCT-1", "STRUCTURE", "NEW", full_acquisition_capex_usd=10_000_000.0), "STRUCTURE"),
    ]


def test_economic_scope_setting_has_real_runtime_consumer():
    on = cap.apply_material_economic_scope(scoped_records=_hvac_struct_records(), economic_scope=cap.EconomicScopeSettings())
    assert on.total_project_capex_usd == 12_000_000.0


def test_economic_scope_off_removes_project_cost():
    off = cap.apply_material_economic_scope(
        scoped_records=_hvac_struct_records(), economic_scope=cap.EconomicScopeSettings().with_material_off("HVAC"))
    assert off.total_project_capex_usd == 10_000_000.0
    assert off.excluded_by_economic_scope_usd == 2_000_000.0


def test_economic_scope_off_does_not_delete_physical_object():
    off = cap.apply_material_economic_scope(
        scoped_records=_hvac_struct_records(), economic_scope=cap.EconomicScopeSettings().with_material_off("HVAC"))
    assert "HVAC-1" in off.physically_present_but_excluded  # object still present


def test_economic_scope_on_new_item_appears_in_cost():
    recs = [cap.ScopedAssetRecord(cap.AssetEconomicRecord("HVAC-NEW", "HVAC", "MODIFY", modification_capex_usd=150_000.0), "HVAC")]
    on = cap.apply_material_economic_scope(scoped_records=recs, economic_scope=cap.EconomicScopeSettings())
    assert on.total_project_capex_usd == 150_000.0


@pytest.mark.parametrize("category", ["STRUCTURE", "HVAC", "EQUIPMENT", "TRANSPORT_INFRASTRUCTURE"])
def test_material_scope_off_excludes_only_that_category(category):
    recs = [
        cap.ScopedAssetRecord(cap.AssetEconomicRecord(f"{c}-1", c, "NEW", full_acquisition_capex_usd=1_000_000.0), c)
        for c in ("STRUCTURE", "HVAC", "EQUIPMENT", "TRANSPORT_INFRASTRUCTURE")
    ]
    off = cap.apply_material_economic_scope(scoped_records=recs, economic_scope=cap.EconomicScopeSettings().with_material_off(category))
    assert off.total_project_capex_usd == 3_000_000.0  # 4 categories - 1 off
    assert category in off.excluded_categories


# ===========================================================================
# CLARIFICATION E: expansion connection work.
# ===========================================================================

def _expansion():
    return cap.reconcile_expansion(
        existing_building=[cap.AssetEconomicRecord("HOSP", "STRUCTURE", "INHERITED_EXISTING", full_acquisition_capex_usd=40_000_000.0)],
        new_wing=[cap.AssetEconomicRecord("WING", "STRUCTURE", "NEW", full_acquisition_capex_usd=12_000_000.0)],
        connection_work=[
            cap.ConnectionWorkItem("GUIDEWAY_EXTENSION", 1_250_000.0),
            cap.ConnectionWorkItem("UTILITY_CONNECTION", 400_000.0),
            cap.ConnectionWorkItem("EXISTING_BUILDING_CONNECTION_MODIFICATION", 300_000.0, economic_state="MODIFY"),
        ],
    )


def test_expansion_existing_building_not_recharged():
    assert not _expansion().existing_building_recharged
    assert _expansion().existing_building_charged_usd == 0.0


def test_expansion_new_wing_costed():
    assert _expansion().new_wing_charged_usd == 12_000_000.0


def test_expansion_connection_work_identifiable_and_included():
    e = _expansion()
    assert e.connection_work_identifiable
    assert e.connection_work_charged_usd == 1_950_000.0
    kinds = [k for k, _ in e.connection_work_items]
    assert "EXISTING_BUILDING_CONNECTION_MODIFICATION" in kinds


def test_expansion_connection_modification_is_modify_not_whole_building():
    # the existing-building connection change is a MODIFY line, not a re-cost of
    # the whole $40M building
    e = _expansion()
    assert e.total_incremental_capex_usd == 12_000_000.0 + 1_950_000.0
    assert e.total_incremental_capex_usd < 40_000_000.0


# ===========================================================================
# CLARIFICATION F: greenfield over-inheritance sentinel.
# ===========================================================================

def test_greenfield_silent_inheritance_flagged():
    audit = cap.audit_greenfield_inheritance(records=[
        cap.AssetEconomicRecord("GF-NEW", "STRUCTURE", "NEW", full_acquisition_capex_usd=30_000_000.0),
        cap.AssetEconomicRecord("SNUCK", "HVAC", "INHERITED_EXISTING", full_acquisition_capex_usd=5_000_000.0),
    ])
    assert audit.over_inheritance_detected
    assert "SNUCK" in audit.zero_cost_inherited_assets


def test_greenfield_clean_no_over_inheritance():
    audit = cap.audit_greenfield_inheritance(records=[
        cap.AssetEconomicRecord("GF-STRUCT", "STRUCTURE", "NEW", full_acquisition_capex_usd=30_000_000.0),
        cap.AssetEconomicRecord("GF-HVAC", "HVAC", "NEW", full_acquisition_capex_usd=5_000_000.0),
    ])
    assert not audit.over_inheritance_detected
    assert audit.required_new_scope_costed


def test_greenfield_explicit_external_reuse_allowed():
    audit = cap.audit_greenfield_inheritance(
        records=[
            cap.AssetEconomicRecord("GF-NEW", "STRUCTURE", "NEW", full_acquisition_capex_usd=30_000_000.0),
            cap.AssetEconomicRecord("EXT-REUSE", "EQUIPMENT", "INHERITED_EXISTING", full_acquisition_capex_usd=1_000_000.0),
        ],
        explicitly_reused_external_ids=frozenset({"EXT-REUSE"}),
    )
    assert not audit.over_inheritance_detected  # explicitly reused, not silent
    assert "EXT-REUSE" in audit.explicitly_reused_external

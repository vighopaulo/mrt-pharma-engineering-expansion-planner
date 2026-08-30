"""KIRO Super-Build 3 -- deterministic capital-inheritance scenario controls
(Sec 22-30). Each builds a concrete named scenario from the
`capital_project_inheritance_authority` primitives and exposes the exact
quantities the spec requires. These are illustrative controlled scenarios
(CONTROLLED_ENGINEERING_ASSUMPTION unit costs), not calibrated facility facts.

No new economics engine: every scenario composes the authority. Nothing here
changes MRT/Part 3E/equal_budget/SB1/SB2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import capital_project_inheritance_authority as cap

# Controlled illustrative unit costs (Sec disclosure: not calibrated).
SCANNER_UNIT_CAPEX_USD = 2_000_000.0
CYCLOTRON_UNIT_CAPEX_USD = 3_000_000.0
GENERATOR_UNIT_CAPEX_USD = 250_000.0
ROOM_UNIT_CAPEX_USD = 120_000.0
SCANNER_ANNUAL_OPEX_USD = 200_000.0
SCANNER_REPLACEMENT_ANNUAL_OPEX_USD = 150_000.0


# --- Sec 22: scanner delta (2 existing usable, 3 required -> 1 new) ---------

def scanner_delta_control() -> cap.CapacityDeltaResult:
    return cap.compute_capacity_delta(cap.CapacityDeltaInputs(
        resource="scanner", existing_usable_units=2, target_required_units=3,
        unit_capex_usd=SCANNER_UNIT_CAPEX_USD,
    ))


# --- Sec 23: scanner replacement (2 existing, 1 replaced, target 3 -> buy 2) -

def scanner_replacement_control() -> cap.CapacityDeltaResult:
    return cap.compute_capacity_delta(cap.CapacityDeltaInputs(
        resource="scanner", existing_usable_units=2, target_required_units=3,
        replaced_units=1, unit_capex_usd=SCANNER_UNIT_CAPEX_USD,
    ))


# --- Sec 24: cyclotron delta (within existing usable capacity -> 0 new) ------

def cyclotron_within_capacity_control() -> cap.CapacityDeltaResult:
    return cap.compute_capacity_delta(cap.CapacityDeltaInputs(
        resource="cyclotron", existing_usable_units=1, target_required_units=1,
        unit_capex_usd=CYCLOTRON_UNIT_CAPEX_USD,
    ))


def cyclotron_shortfall_control() -> cap.CapacityDeltaResult:
    return cap.compute_capacity_delta(cap.CapacityDeltaInputs(
        resource="cyclotron", existing_usable_units=1, target_required_units=2,
        unit_capex_usd=CYCLOTRON_UNIT_CAPEX_USD,
    ))


# --- Sec 25: generator delta ------------------------------------------------

def generator_within_capacity_control() -> cap.CapacityDeltaResult:
    return cap.compute_capacity_delta(cap.CapacityDeltaInputs(
        resource="generator", existing_usable_units=1, target_required_units=1,
        unit_capex_usd=GENERATOR_UNIT_CAPEX_USD,
    ))


# --- Sec 26: bed/room delta (30 existing + 20 new = 50 target) --------------

@dataclass(frozen=True)
class BedRoomDeltaResult:
    existing_beds: int
    new_beds: int
    target_beds: int
    existing_beds_charged_as_new: bool


def bed_room_delta_control() -> BedRoomDeltaResult:
    delta = cap.compute_capacity_delta(cap.CapacityDeltaInputs(
        resource="bed", existing_usable_units=30, target_required_units=50,
        unit_capex_usd=ROOM_UNIT_CAPEX_USD,
    ))
    # existing 30 are INHERITED_EXISTING -> not charged as new construction.
    return BedRoomDeltaResult(
        existing_beds=30, new_beds=delta.new_units_required, target_beds=50,
        existing_beds_charged_as_new=False,
    )


# --- Sec 27: new wing 500 m away (existing hospital inherited, wing NEW) -----

@dataclass(frozen=True)
class NewWingControlResult:
    incremental_capex: cap.IncrementalCapexResult
    existing_hospital_recharged: bool


def new_wing_control() -> NewWingControlResult:
    records = [
        # existing hospital building fabric -> inherited, $0 new capex
        cap.AssetEconomicRecord("HOSP-STRUCTURE", "STRUCTURE", "INHERITED_EXISTING", full_acquisition_capex_usd=40_000_000.0),
        cap.AssetEconomicRecord("HOSP-HVAC", "HVAC", "INHERITED_EXISTING", full_acquisition_capex_usd=6_000_000.0),
        # new wing -> NEW scope
        cap.AssetEconomicRecord("WING-STRUCTURE", "STRUCTURE", "NEW", full_acquisition_capex_usd=12_000_000.0),
        cap.AssetEconomicRecord("WING-HVAC", "HVAC", "NEW", full_acquisition_capex_usd=2_000_000.0),
        cap.AssetEconomicRecord("WING-CONNECTION", "TRANSPORT_INFRASTRUCTURE", "NEW", full_acquisition_capex_usd=1_500_000.0),
    ]
    ic = cap.aggregate_incremental_capex(project_class="EXISTING_FACILITY_EXPANSION", records=records)
    # existing hospital fabric never charged (all inherited)
    recharged = ic.charged_by_state["INHERITED_EXISTING"] > 0.0
    return NewWingControlResult(incremental_capex=ic, existing_hospital_recharged=recharged)


# --- Sec 28: vertical expansion 4 -> 8 floors (1-4 inherited, 5-8 new) -------

@dataclass(frozen=True)
class VerticalExpansionResult:
    incremental_capex: cap.IncrementalCapexResult
    inherited_floor_count: int
    new_floor_count: int
    all_floors_priced_as_new: bool


def vertical_expansion_control() -> VerticalExpansionResult:
    records = []
    for f in range(1, 5):  # floors 1-4 inherited
        records.append(cap.AssetEconomicRecord(f"FLOOR-{f}", "STRUCTURE", "INHERITED_EXISTING", full_acquisition_capex_usd=3_000_000.0))
    for f in range(5, 9):  # floors 5-8 new
        records.append(cap.AssetEconomicRecord(f"FLOOR-{f}", "STRUCTURE", "NEW", full_acquisition_capex_usd=3_000_000.0))
    ic = cap.aggregate_incremental_capex(project_class="EXISTING_FACILITY_EXPANSION", records=records)
    inherited = sum(1 for r in records if r.economic_state == "INHERITED_EXISTING")
    new = sum(1 for r in records if r.economic_state == "NEW")
    # all-floors-priced-as-new would be 8*3M = 24M; correct is 4*3M = 12M
    all_new = abs(ic.total_incremental_capex_usd - 8 * 3_000_000.0) < 1e-6
    return VerticalExpansionResult(incremental_capex=ic, inherited_floor_count=inherited, new_floor_count=new, all_floors_priced_as_new=all_new)


# --- Sec 29: retrofit (room present; only modeled retrofit work charged) -----

@dataclass(frozen=True)
class RetrofitControlResult:
    incremental_capex: cap.IncrementalCapexResult
    full_room_recosted: bool


def retrofit_control() -> RetrofitControlResult:
    records = [
        # room structure inherited; only shielding + HVAC retrofit charged
        cap.AssetEconomicRecord("ROOM-STRUCTURE", "STRUCTURE", "INHERITED_EXISTING", full_acquisition_capex_usd=800_000.0),
        cap.AssetEconomicRecord("ROOM-SHIELDING", "SHIELDING", "MODIFY", modification_capex_usd=250_000.0),
        cap.AssetEconomicRecord("ROOM-HVAC", "HVAC", "MODIFY", modification_capex_usd=120_000.0),
    ]
    ic = cap.aggregate_incremental_capex(project_class="EXISTING_FACILITY_RETROFIT", records=records)
    # full room re-cost would include the $800k structure; correct total = 370k
    full_recost = ic.total_incremental_capex_usd >= 800_000.0
    return RetrofitControlResult(incremental_capex=ic, full_room_recosted=full_recost)


# --- Sec 30: greenfield (no zero-cost inheritance; everything NEW) ----------

@dataclass(frozen=True)
class GreenfieldControlResult:
    incremental_capex: cap.IncrementalCapexResult
    any_zero_cost_inheritance: bool


def greenfield_control() -> GreenfieldControlResult:
    records = [
        cap.AssetEconomicRecord("GF-STRUCTURE", "STRUCTURE", "NEW", full_acquisition_capex_usd=30_000_000.0),
        cap.AssetEconomicRecord("GF-HVAC", "HVAC", "NEW", full_acquisition_capex_usd=5_000_000.0),
        cap.AssetEconomicRecord("GF-SCANNER", "SCANNER", "NEW", full_acquisition_capex_usd=2_000_000.0),
    ]
    ic = cap.aggregate_incremental_capex(project_class="GREENFIELD_NEW_FACILITY", records=records)
    # greenfield must not have any INHERITED_EXISTING/RETAINED zero-cost objects
    any_inherited = ic.charged_by_state["INHERITED_EXISTING"] != 0.0 or ic.inherited_asset_value_excluded_usd != 0.0
    return GreenfieldControlResult(incremental_capex=ic, any_zero_cost_inheritance=any_inherited)


# --- Sec 34-37: transport inheritance (existing PTS reused, only new added) --

def pts_transport_inheritance_control() -> cap.TransportInheritanceResult:
    # existing 4 PTS stations retained, target 6 -> 2 new; backbone inherited (not re-charged)
    return cap.compute_transport_inheritance(
        cap.TransportResourceInheritance(
            resource="PTS stations", existing_quantity=4, retained_quantity=4, removed_quantity=0,
            target_required_quantity=6, unit_capex_usd=45_000.0, shared_backbone_exists=True,
        ),
        shared_backbone_capex_usd=cap.__dict__.get("PTS_SHARED_BACKBONE_CAPEX_USD", 120_000.0),
    )


def mrt_transport_new_control() -> cap.TransportInheritanceResult:
    # no existing MRT -> full guideway is NEW (Sec 35)
    return cap.compute_transport_inheritance(
        cap.TransportResourceInheritance(
            resource="MRT guideway (m)", existing_quantity=0, retained_quantity=0, removed_quantity=0,
            target_required_quantity=300, unit_capex_usd=2_500.0, shared_backbone_exists=False,
        ),
    )

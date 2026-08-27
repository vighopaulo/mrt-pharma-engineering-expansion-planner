"""Reactive Engineering and Economic Consequence Authority (Phase 3).

GOVERNANCE: this module does NOT reimplement CapEx/OPEX/revenue/lifecycle
formulas. It feeds Phase 1B/2A/2B-derived engineering quantities (route
distance, installed-network length, resource counts) into the EXISTING
authorities (`finance.incremental_financials`,
`canonical_spatial_authority.mrt_segment_length_capex`,
`operational_day_orchestrator._compute_irr_pct`) and binds the result to
Phase 1A Lockdown/What-If lineage via one canonical `ChangeConsequenceRecord`
-- never a second lineage/result model.

AUDIT (section 3), performed before adding anything:

  MOVE_SCANNER                -- route/time: EXISTING_AND_CONNECTED (Phase
                                  2A/2B `derive_shadow_route`). Relocation
                                  CapEx: MISSING -- no repository authority
                                  prices in-place PET/SPECT relocation. A new
                                  `CONTROLLED_PLANNING_ASSUMPTION` editable
                                  parameter is added below (never hidden,
                                  never hard-coded).
  CHANGE_PATIENT_ROOM_ASSIGNMENT -- route/time: EXISTING_AND_CONNECTED.
                                  CapEx: correctly $0 by design -- no
                                  authority needed, none added.
  MOVE_BUILDING                -- inter-building route: EXISTING_AND_CONNECTED
                                  (Phase 2A `straight_line_distance_m`/
                                  `derive_shadow_route`). Installed-network
                                  CapEx: EXISTING_BUT_NOT_CONNECTED
                                  (`canonical_spatial_authority.
                                  mrt_segment_length_capex` already exists but
                                  was never applied to a translation-induced
                                  connection-length delta before this module).
  MOVE_ENDPOINT                -- same classification as MOVE_BUILDING.
  ADD_SCANNER / ADD_CYCLOTRON / ADD_GENERATOR / CHANGE_MRT_SPEED /
  CHANGE_STAFFING              -- AUDITED, NOT IMPLEMENTED this phase: the
                                  existing `ADD_OBJECT` changeset
                                  (`canonical_spatial_authority`) and
                                  `record_parameter_change`
                                  (`mrt_auxiliary_systems_authority`) already
                                  cover these structurally; no new gap found
                                  that this phase's scope requires closing.

TRANSPORT SPATIAL AUTHORITY BUILD 4 (sections 19-23) AUDIT ADDENDUM:

  MRT distance-reactive CapEx/OPEX -- ALREADY VALIDATED above
                                  (`evaluate_move_building_consequence`/
                                  `evaluate_move_endpoint_consequence`); no
                                  change required.
  RGHT distance-reactive CapEx     -- `conventional_transport_authority.
                                  AgvModelClass` CapEx (`vehicle_capex` +
                                  `system_integration_capex`) is a PER-FLEET
                                  cost, never a $/m installed-track
                                  coefficient (confirmed by repository-wide
                                  search: no `rght_capex_per_m`/`agv_capex_
                                  per_m` authority exists anywhere).
                                  RGHT_DISTANCE_REACTIVE_CAPEX =
                                  NOT_CALIBRATED (section 20 mandatory
                                  fallback) -- no new coefficient invented.
  RGHT distance-reactive OPEX      -- `AgvModelClass.annual_maintenance_
                                  opex`/`.annual_energy_opex` are flat
                                  annual allowances, not distance/time
                                  functions. RGHT_DISTANCE_REACTIVE_OPEX =
                                  NOT_CALIBRATED.
  PTS distance-reactive CapEx      -- `conventional_transport_authority.
                                  PneumaticTubeNetwork.network_capex_per_m`
                                  IS an existing $/m coefficient, consumed by
                                  `pts_new_study_capex` via `network.
                                  network_length_m`. `compute_pts_capex_
                                  with_installed_length` below feeds the
                                  REAL calibrated installed PTS tube length
                                  (`pts_spatial_network_authority.
                                  PtsInfrastructureQuantities.
                                  total_tube_length_m`) into that EXISTING
                                  field via `dataclasses.replace` -- never a
                                  new coefficient, never a mission-route
                                  distance substituted for network length.
                                  PTS_DISTANCE_REACTIVE_CAPEX = VALIDATED.
  PTS distance-reactive OPEX       -- `pts_annual_opex` = maintenance +
                                  energy + residual-labor terms, none of
                                  which depend on `network_length_m`
                                  (fixed/lumped controlled allowance).
                                  PTS_DISTANCE_REACTIVE_OPEX = NOT_CALIBRATED.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal

import finance
from editable_default_authority import EditableParameter
from mrt_transport_energy_maintenance_authority import (
    MRT_GUIDEWAY_MAINTENANCE_FRACTION_PER_YEAR,
    MrtMissionEnergyInputs,
    compute_mrt_mission_energy_annual_opex_delta_usd,
)

if TYPE_CHECKING:
    from conventional_transport_authority import PneumaticTubeNetwork
    from pts_spatial_network_authority import PtsInfrastructureQuantities

# Section 20-21 (Build 4): honest, non-fabricated findings -- no existing
# distance-based RGHT infrastructure coefficient exists.
RGHT_DISTANCE_REACTIVE_CAPEX: Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
RGHT_DISTANCE_REACTIVE_OPEX: Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
# Section 23 (Build 4): PTS OPEX is a fixed/lumped controlled allowance.
PTS_DISTANCE_REACTIVE_OPEX: Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"

ChangeType = Literal[
    "MOVE_SCANNER", "CHANGE_PATIENT_ROOM_ASSIGNMENT", "MOVE_BUILDING", "MOVE_ENDPOINT",
    "ADD_SCANNER", "REMOVE_SCANNER", "ADD_CYCLOTRON", "ADD_GENERATOR", "CHANGE_MRT_SPEED", "CHANGE_STAFFING",
]

AuthorityStatus = Literal["EXISTING_AND_CONNECTED", "EXISTING_BUT_NOT_CONNECTED", "PARTIAL", "MISSING"]

ReactivityClassification = Literal[
    "FULLY_REACTIVE", "PARTIALLY_REACTIVE", "PHYSICAL_ONLY_NO_ECONOMIC_DEPENDENCY", "MISSING_ECONOMIC_AUTHORITY",
]

# ---------------------------------------------------------------------------
# Section 7/21: scanner relocation is a genuinely MISSING cost authority.
# DEFAULT -> ACTIVE -> OPTIONAL OVERRIDE, reusing the existing
# `EditableParameter` structure verbatim -- never a hard-coded literal inside
# a calculation function. Kept explicitly separate from
# `assumptions.scanner_capex` (a NEW-purchase price this parameter NEVER
# substitutes for).
# ---------------------------------------------------------------------------

SCANNER_RELOCATION_CAPEX_USD = EditableParameter(
    parameter_id="SCANNER_RELOCATION_CAPEX_USD",
    default_value=75_000.0,
    units="USD per relocation",
    source=(
        "No repository authority prices in-place PET/SPECT relocation (disconnection, rigging/transport within "
        "the facility, reinstallation, electrical/service reconnection, and post-move requalification/QA) -- "
        "distinct from `assumptions.scanner_capex` (a new-unit purchase price, unaffected by this parameter)."
    ),
    source_type="CONTROLLED_ENGINEERING_ASSUMPTION",
    confidence="LOW",
    notes="Relocation-only cost; never charges a new scanner purchase merely because an existing unit moved (section 7).",
)


def scanner_relocation_editable_registry() -> tuple[EditableParameter, ...]:
    return (SCANNER_RELOCATION_CAPEX_USD,)


# ---------------------------------------------------------------------------
# Canonical change-consequence record (section 4) -- binds to, never
# duplicates, Phase 1A lineage (`lockdown_id`/`what_if_id` are foreign keys
# only).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChangeConsequenceRecord:
    change_id: str
    change_type: ChangeType
    what_if_id: str | None
    source_lockdown_id: str | None
    entity_id: str
    before_geometry_summary: str
    after_geometry_summary: str
    route_distance_before_m: float | None
    route_distance_after_m: float | None
    installed_network_before_m: float | None
    installed_network_after_m: float | None
    travel_time_before_minutes: float | None
    travel_time_after_minutes: float | None
    resource_count_before: int | None
    resource_count_after: int | None
    capex_delta_usd: float
    annual_opex_delta_usd: float
    annual_revenue_delta_usd: float
    npv_before_usd: float | None
    npv_after_usd: float | None
    npv_delta_usd: float | None
    payback_before_years: float | None
    payback_after_years: float | None
    payback_delta_years: float | None
    irr_before_pct: float | Literal["NOT_CALIBRATED"] | None
    irr_after_pct: float | Literal["NOT_CALIBRATED"] | None
    irr_delta_pct: float | Literal["NOT_CALIBRATED"] | None
    reactivity: ReactivityClassification
    provenance: tuple[str, ...]
    calculation_status: Literal["COMPLETE", "PARTIAL", "NOT_APPLICABLE"]
    annual_energy_opex_delta_usd: float = 0.0
    annual_maintenance_opex_delta_usd: float = 0.0


def _irr_delta(
    *, capex_before: float, capex_after: float, annual_margin_before_usd: float, annual_margin_after_usd: float, analysis_years: int,
) -> tuple[float | Literal["NOT_CALIBRATED"], float | Literal["NOT_CALIBRATED"], float | Literal["NOT_CALIBRATED"] | None]:
    """Reuses the EXISTING, already-verified
    `operational_day_orchestrator._compute_irr_pct` -- never a re-derived IRR
    formula (section 20: verify the actual IRR authority before reporting
    it). Returns "NOT_CALIBRATED" (never a fabricated number) when capex or
    margin is non-positive, matching that authority's own guard."""
    from operational_day_orchestrator import _compute_irr_pct

    irr_before = _compute_irr_pct(capex_usd=capex_before, annual_margin_usd=annual_margin_before_usd, analysis_years=analysis_years)
    irr_after = _compute_irr_pct(capex_usd=capex_after, annual_margin_usd=annual_margin_after_usd, analysis_years=analysis_years)
    if irr_before == "NOT_CALIBRATED" or irr_after == "NOT_CALIBRATED":
        return irr_before, irr_after, None
    return irr_before, irr_after, irr_after - irr_before


def _mrt_energy_opex_delta(inputs: MrtMissionEnergyInputs | None) -> float:
    """Section 14/16-17: zero unless a caller proves a genuine MRT
    mission-distance change -- never fabricated for changes that do not
    genuinely touch an MRT mission."""
    if inputs is None:
        return 0.0
    return compute_mrt_mission_energy_annual_opex_delta_usd(inputs)


def _lifecycle_delta(
    *, capex_before: float, capex_after: float, opex_before: float, opex_after: float,
    throughput_patients_per_day: float, revenue_per_scan: float, operating_days_per_year: int,
    discount_rate_pct: float, analysis_years: int,
) -> dict:
    """Reuses `finance.incremental_financials` verbatim for BOTH the before
    and after configurations -- revenue driver (throughput) is held constant
    unless the caller proves a genuine throughput change (section 19: no
    revenue delta from distance alone)."""
    before = finance.incremental_financials(
        capex_before, opex_before, throughput_patients_per_day, revenue_per_scan, operating_days_per_year, discount_rate_pct, analysis_years,
    )
    after = finance.incremental_financials(
        capex_after, opex_after, throughput_patients_per_day, revenue_per_scan, operating_days_per_year, discount_rate_pct, analysis_years,
    )
    (rev_before, opex_b, cash_before, npv_before, roi_before, payback_before) = before
    (rev_after, opex_a, cash_after, npv_after, roi_after, payback_after) = after
    return {
        "revenue_delta": rev_after - rev_before, "npv_before": npv_before, "npv_after": npv_after,
        "npv_delta": npv_after - npv_before, "payback_before": payback_before, "payback_after": payback_after,
        "payback_delta": (payback_after - payback_before) if (payback_before not in (float("inf"),) and payback_after not in (float("inf"),)) else None,
        "annual_margin_before": cash_before, "annual_margin_after": cash_after,
    }


# ---------------------------------------------------------------------------
# Section 25: MOVE_SCANNER consequence
# ---------------------------------------------------------------------------


def evaluate_move_scanner_consequence(
    *, change_id: str, scanner_id: str, what_if_id: str | None, source_lockdown_id: str | None,
    route_distance_before_m: float | None, route_distance_after_m: float | None,
    travel_time_before_minutes: float | None, travel_time_after_minutes: float | None,
    throughput_patients_per_day: float, revenue_per_scan: float, operating_days_per_year: int,
    discount_rate_pct: float, analysis_years: int, baseline_capex: float, baseline_annual_opex: float,
    relocation_occurs: bool = True, mrt_mission_energy_inputs: "MrtMissionEnergyInputs | None" = None,
) -> ChangeConsequenceRecord:
    """Section 6-7/16: scanner relocation genuinely changes patient route/
    travel time (reactive) and incurs the disclosed `SCANNER_RELOCATION_CAPEX_USD`
    (never a new-purchase price). No MRT infrastructure/energy effect is
    created unless the caller proves the move genuinely changes an MRT
    mission (`mrt_mission_energy_inputs`, default None -- section 16)."""
    relocation_capex = float(SCANNER_RELOCATION_CAPEX_USD.active_value) if relocation_occurs else 0.0
    energy_opex_delta = _mrt_energy_opex_delta(mrt_mission_energy_inputs)
    capex_after = baseline_capex + relocation_capex
    opex_after = baseline_annual_opex + energy_opex_delta
    lifecycle = _lifecycle_delta(
        capex_before=baseline_capex, capex_after=capex_after, opex_before=baseline_annual_opex, opex_after=opex_after,
        throughput_patients_per_day=throughput_patients_per_day, revenue_per_scan=revenue_per_scan,
        operating_days_per_year=operating_days_per_year, discount_rate_pct=discount_rate_pct, analysis_years=analysis_years,
    )
    irr_before, irr_after, irr_delta = _irr_delta(
        capex_before=baseline_capex, capex_after=capex_after,
        annual_margin_before_usd=lifecycle["annual_margin_before"], annual_margin_after_usd=lifecycle["annual_margin_after"],
        analysis_years=analysis_years,
    )
    reactivity: ReactivityClassification = "FULLY_REACTIVE" if (relocation_capex > 0 or energy_opex_delta != 0.0) else "PHYSICAL_ONLY_NO_ECONOMIC_DEPENDENCY"
    return ChangeConsequenceRecord(
        change_id=change_id, change_type="MOVE_SCANNER", what_if_id=what_if_id, source_lockdown_id=source_lockdown_id,
        entity_id=scanner_id, before_geometry_summary=f"scanner {scanner_id} at prior room",
        after_geometry_summary=f"scanner {scanner_id} relocated", route_distance_before_m=route_distance_before_m,
        route_distance_after_m=route_distance_after_m, installed_network_before_m=None, installed_network_after_m=None,
        travel_time_before_minutes=travel_time_before_minutes, travel_time_after_minutes=travel_time_after_minutes,
        resource_count_before=None, resource_count_after=None, capex_delta_usd=relocation_capex, annual_opex_delta_usd=energy_opex_delta,
        annual_energy_opex_delta_usd=energy_opex_delta, annual_maintenance_opex_delta_usd=0.0,
        annual_revenue_delta_usd=lifecycle["revenue_delta"], npv_before_usd=lifecycle["npv_before"], npv_after_usd=lifecycle["npv_after"],
        npv_delta_usd=lifecycle["npv_delta"], payback_before_years=lifecycle["payback_before"], payback_after_years=lifecycle["payback_after"],
        payback_delta_years=lifecycle["payback_delta"], irr_before_pct=irr_before, irr_after_pct=irr_after, irr_delta_pct=irr_delta,
        reactivity=reactivity,
        provenance=("Phase 2A/2B route/time (canonical_geometry_shadow_routing_authority)", "SCANNER_RELOCATION_CAPEX_USD (CONTROLLED_ENGINEERING_ASSUMPTION)", "finance.incremental_financials", "operational_day_orchestrator._compute_irr_pct", "mrt_transport_energy_maintenance_authority (only if mrt_mission_energy_inputs supplied)"),
        calculation_status="COMPLETE",
    )


# ---------------------------------------------------------------------------
# Section 26: CHANGE_PATIENT_ROOM_ASSIGNMENT consequence
# ---------------------------------------------------------------------------


def evaluate_change_patient_room_consequence(
    *, change_id: str, patient_id: str, what_if_id: str | None, source_lockdown_id: str | None,
    route_distance_before_m: float | None, route_distance_after_m: float | None,
    travel_time_before_minutes: float | None, travel_time_after_minutes: float | None,
    mrt_mission_energy_inputs: MrtMissionEnergyInputs | None = None,
) -> ChangeConsequenceRecord:
    """Section 8/17: patient-room reassignment has NO direct CapEx by design --
    genuinely $0, never fabricated. Route/travel-time recompute (Phase
    2A/2B) is the only physical consequence unless a genuine workload/energy
    dependency is separately proven by the caller via `mrt_mission_energy_inputs`
    (default None -- never invented)."""
    route_changed = route_distance_before_m != route_distance_after_m
    energy_opex_delta = _mrt_energy_opex_delta(mrt_mission_energy_inputs)
    reactivity: ReactivityClassification = "FULLY_REACTIVE" if energy_opex_delta != 0.0 else "PHYSICAL_ONLY_NO_ECONOMIC_DEPENDENCY"
    return ChangeConsequenceRecord(
        change_id=change_id, change_type="CHANGE_PATIENT_ROOM_ASSIGNMENT", what_if_id=what_if_id, source_lockdown_id=source_lockdown_id,
        entity_id=patient_id, before_geometry_summary=f"patient {patient_id} prior room",
        after_geometry_summary=f"patient {patient_id} reassigned room", route_distance_before_m=route_distance_before_m,
        route_distance_after_m=route_distance_after_m, installed_network_before_m=None, installed_network_after_m=None,
        travel_time_before_minutes=travel_time_before_minutes, travel_time_after_minutes=travel_time_after_minutes,
        resource_count_before=None, resource_count_after=None, capex_delta_usd=0.0, annual_opex_delta_usd=energy_opex_delta,
        annual_energy_opex_delta_usd=energy_opex_delta, annual_maintenance_opex_delta_usd=0.0,
        annual_revenue_delta_usd=0.0, npv_before_usd=None, npv_after_usd=None, npv_delta_usd=0.0 if route_changed else 0.0,
        payback_before_years=None, payback_after_years=None, payback_delta_years=None, irr_before_pct=None, irr_after_pct=None,
        irr_delta_pct=None,
        reactivity=reactivity,
        provenance=("Phase 2A/2B route/time (canonical_geometry_shadow_routing_authority)", "CapEx intentionally $0 by design (section 8)", "mrt_transport_energy_maintenance_authority (only if mrt_mission_energy_inputs supplied)"),
        calculation_status="COMPLETE",
    )


# ---------------------------------------------------------------------------
# Sections 27/10-11: MOVE_BUILDING consequence
# ---------------------------------------------------------------------------


def evaluate_move_building_consequence(
    *, change_id: str, building_id: str, what_if_id: str | None, source_lockdown_id: str | None,
    inter_building_distance_before_m: float, inter_building_distance_after_m: float, guideway_capex_per_m: float,
    baseline_capex: float, baseline_annual_opex: float, throughput_patients_per_day: float, revenue_per_scan: float,
    operating_days_per_year: int, discount_rate_pct: float, analysis_years: int,
    mrt_mission_energy_inputs: MrtMissionEnergyInputs | None = None,
) -> ChangeConsequenceRecord:
    """Sections 10-11/18: reuses the EXISTING `mrt_segment_length_capex`
    formula (length x unit_cost) applied to the CONNECTION-LENGTH DELTA
    caused by the translation -- never re-prices the building itself.
    Guideway maintenance ALWAYS reacts to this same installed-network CapEx
    delta (section 8/18, never mission-route length); mission energy only
    reacts if the caller proves a genuine MRT mission-distance change
    (`mrt_mission_energy_inputs`, default None)."""
    import canonical_spatial_authority as csa

    installed_network_delta_m = inter_building_distance_after_m - inter_building_distance_before_m
    connection_capex_delta = csa.mrt_segment_length_capex(length_m=abs(installed_network_delta_m), unit_cost_per_length=guideway_capex_per_m)
    if installed_network_delta_m < 0:
        connection_capex_delta = -connection_capex_delta  # shortened connection -- reduced CapEx, never invented savings beyond the formula's own symmetry
    guideway_maintenance_delta = connection_capex_delta * MRT_GUIDEWAY_MAINTENANCE_FRACTION_PER_YEAR.active_value
    energy_opex_delta = _mrt_energy_opex_delta(mrt_mission_energy_inputs)
    opex_delta = guideway_maintenance_delta + energy_opex_delta
    capex_after = baseline_capex + connection_capex_delta
    opex_after = baseline_annual_opex + opex_delta
    lifecycle = _lifecycle_delta(
        capex_before=baseline_capex, capex_after=capex_after, opex_before=baseline_annual_opex, opex_after=opex_after,
        throughput_patients_per_day=throughput_patients_per_day, revenue_per_scan=revenue_per_scan,
        operating_days_per_year=operating_days_per_year, discount_rate_pct=discount_rate_pct, analysis_years=analysis_years,
    )
    irr_before, irr_after, irr_delta = _irr_delta(
        capex_before=baseline_capex, capex_after=capex_after,
        annual_margin_before_usd=lifecycle["annual_margin_before"], annual_margin_after_usd=lifecycle["annual_margin_after"],
        analysis_years=analysis_years,
    )
    return ChangeConsequenceRecord(
        change_id=change_id, change_type="MOVE_BUILDING", what_if_id=what_if_id, source_lockdown_id=source_lockdown_id,
        entity_id=building_id, before_geometry_summary=f"building {building_id} at prior position",
        after_geometry_summary=f"building {building_id} translated", route_distance_before_m=inter_building_distance_before_m,
        route_distance_after_m=inter_building_distance_after_m, installed_network_before_m=inter_building_distance_before_m,
        installed_network_after_m=inter_building_distance_after_m, travel_time_before_minutes=None, travel_time_after_minutes=None,
        resource_count_before=None, resource_count_after=None, capex_delta_usd=connection_capex_delta, annual_opex_delta_usd=opex_delta,
        annual_energy_opex_delta_usd=energy_opex_delta, annual_maintenance_opex_delta_usd=guideway_maintenance_delta,
        annual_revenue_delta_usd=lifecycle["revenue_delta"], npv_before_usd=lifecycle["npv_before"], npv_after_usd=lifecycle["npv_after"],
        npv_delta_usd=lifecycle["npv_delta"], payback_before_years=lifecycle["payback_before"], payback_after_years=lifecycle["payback_after"],
        payback_delta_years=lifecycle["payback_delta"], irr_before_pct=irr_before, irr_after_pct=irr_after, irr_delta_pct=irr_delta,
        reactivity="FULLY_REACTIVE" if connection_capex_delta != 0 else "PHYSICAL_ONLY_NO_ECONOMIC_DEPENDENCY",
        provenance=(
            "Phase 2A straight_line_distance_m/derive_shadow_route", "canonical_spatial_authority.mrt_segment_length_capex (existing formula, newly connected)",
            "mrt_transport_energy_maintenance_authority.compute_mrt_guideway_annual_maintenance_usd (10%/yr of installed CapEx delta)",
            "finance.incremental_financials",
        ),
        calculation_status="COMPLETE",
    )


# ---------------------------------------------------------------------------
# Section 28/12-13: MOVE_ENDPOINT consequence
# ---------------------------------------------------------------------------


def evaluate_move_endpoint_consequence(
    *, change_id: str, endpoint_id: str, what_if_id: str | None, source_lockdown_id: str | None,
    installed_network_before_m: float, installed_network_after_m: float, mission_route_before_m: float, mission_route_after_m: float,
    guideway_capex_per_m: float, baseline_capex: float, baseline_annual_opex: float, throughput_patients_per_day: float,
    revenue_per_scan: float, operating_days_per_year: int, discount_rate_pct: float, analysis_years: int,
    mrt_mission_energy_inputs: MrtMissionEnergyInputs | None = None,
) -> ChangeConsequenceRecord:
    """Sections 12-15/19: installed-network delta drives guideway CapEx (never
    the mission-route delta); mission-route delta is reported separately and
    never substituted as the CapEx basis. Guideway maintenance ALWAYS reacts
    to the installed-network CapEx delta; mission energy only reacts if the
    caller proves a genuine MRT mission-distance change."""
    import canonical_spatial_authority as csa

    network_delta_m = installed_network_after_m - installed_network_before_m
    capex_delta = csa.mrt_segment_length_capex(length_m=abs(network_delta_m), unit_cost_per_length=guideway_capex_per_m)
    if network_delta_m < 0:
        capex_delta = -capex_delta
    guideway_maintenance_delta = capex_delta * MRT_GUIDEWAY_MAINTENANCE_FRACTION_PER_YEAR.active_value
    energy_opex_delta = _mrt_energy_opex_delta(mrt_mission_energy_inputs)
    opex_delta = guideway_maintenance_delta + energy_opex_delta
    capex_after = baseline_capex + capex_delta
    opex_after = baseline_annual_opex + opex_delta
    lifecycle = _lifecycle_delta(
        capex_before=baseline_capex, capex_after=capex_after, opex_before=baseline_annual_opex, opex_after=opex_after,
        throughput_patients_per_day=throughput_patients_per_day, revenue_per_scan=revenue_per_scan,
        operating_days_per_year=operating_days_per_year, discount_rate_pct=discount_rate_pct, analysis_years=analysis_years,
    )
    irr_before, irr_after, irr_delta = _irr_delta(
        capex_before=baseline_capex, capex_after=capex_after,
        annual_margin_before_usd=lifecycle["annual_margin_before"], annual_margin_after_usd=lifecycle["annual_margin_after"],
        analysis_years=analysis_years,
    )
    return ChangeConsequenceRecord(
        change_id=change_id, change_type="MOVE_ENDPOINT", what_if_id=what_if_id, source_lockdown_id=source_lockdown_id,
        entity_id=endpoint_id, before_geometry_summary=f"endpoint {endpoint_id} at prior position",
        after_geometry_summary=f"endpoint {endpoint_id} relocated", route_distance_before_m=mission_route_before_m,
        route_distance_after_m=mission_route_after_m, installed_network_before_m=installed_network_before_m,
        installed_network_after_m=installed_network_after_m, travel_time_before_minutes=None, travel_time_after_minutes=None,
        resource_count_before=None, resource_count_after=None, capex_delta_usd=capex_delta, annual_opex_delta_usd=opex_delta,
        annual_energy_opex_delta_usd=energy_opex_delta, annual_maintenance_opex_delta_usd=guideway_maintenance_delta,
        annual_revenue_delta_usd=lifecycle["revenue_delta"], npv_before_usd=lifecycle["npv_before"], npv_after_usd=lifecycle["npv_after"],
        npv_delta_usd=lifecycle["npv_delta"], payback_before_years=lifecycle["payback_before"], payback_after_years=lifecycle["payback_after"],
        payback_delta_years=lifecycle["payback_delta"], irr_before_pct=irr_before, irr_after_pct=irr_after, irr_delta_pct=irr_delta,
        reactivity="FULLY_REACTIVE" if capex_delta != 0 else "PHYSICAL_ONLY_NO_ECONOMIC_DEPENDENCY",
        provenance=(
            "Phase 2A/2B mission-route + installed-network union (canonical_geometry_shadow_routing_authority, authoritative_geometry_routing_activation)",
            "canonical_spatial_authority.mrt_segment_length_capex",
            "mrt_transport_energy_maintenance_authority.compute_mrt_guideway_annual_maintenance_usd (10%/yr of installed CapEx delta)",
            "finance.incremental_financials",
        ),
        calculation_status="COMPLETE",
    )


# ---------------------------------------------------------------------------
# Transport Spatial Authority Build 4, section 22: PTS installed-network
# CapEx reacts to REAL calibrated geometry via the EXISTING
# `network_capex_per_m` coefficient -- never a new coefficient, never a
# single mission's route distance substituted for total installed length.
# ---------------------------------------------------------------------------


def compute_pts_capex_with_installed_length(
    network: "PneumaticTubeNetwork", quantities: "PtsInfrastructureQuantities", *,
    study_scope: Literal["OPERATIONAL_ONLY", "CAPITAL_PLANNING"],
) -> float:
    """Feeds `quantities.total_tube_length_m` (the REAL calibrated installed
    PTS tube length from `pts_spatial_network_authority.
    compute_pts_infrastructure_quantities`) into `network.network_length_m`
    via `dataclasses.replace`, then calls the EXISTING, UNCHANGED
    `conventional_transport_authority.pts_new_study_capex` -- the only
    change is which length that existing formula receives."""
    from conventional_transport_authority import pts_new_study_capex

    calibrated_network = replace(network, network_length_m=quantities.total_tube_length_m)
    return pts_new_study_capex(calibrated_network, study_scope=study_scope)

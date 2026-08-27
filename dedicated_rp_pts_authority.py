"""Dedicated Radiopharmaceutical PTS (Build 2R): a DISTINCT technology
concept from ordinary PTS / AGV_AMR / MANUAL_SHIELDED / MRT (Section 5) --
serves ONLY `RADIOPHARMACEUTICAL_NUCLEAR` (Section 6), never general
logistics streams.

TOPOLOGY (Section 15/16, confirmed via source inspection, never invented):
this repo's clinical-resource authority (`hybrid_optimization.HybridZoneCandidate`
/`clinical_resource_identity.py`) already models injection/uptake/scanner
rooms as a CENTRALIZED nuclear-medicine suite (fixed counts: 6 scanners, 6
injection resources, 12 uptake resources), NOT distributed one-per-floor like
CLEAN_LINEN/PHARMACY_INFUSION/etc. Dedicated RP-PTS therefore connects ONE
source station (radiopharmacy/hot-lab release point) to ONE destination
station (the centralized injection suite) -- `installed_stations=2`,
`served_floors=1` -- rather than an invented 8-floor distribution that would
contradict the existing, already-tested clinical-resource geometry.

NETWORK LENGTH (Section 16): reuses the SAME facility-geometry authority
already established for Light MRT's guideway (the `mrt_guideway_horizontal_m`
+ `mrt_guideway_vertical_m` trunk route computed by
`_nuclear_result(baseline, mrt_floors=all_floors)`, currently 198.0+24.0=222.0m
for this benchmark) -- never a new invented building geometry.

Do NOT build pneumatic CFD/blower/valve physics here (Section 6/22)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from editable_default_authority import (
    RP_PTS_OPERATING_SPEED_M_PER_S,
    RP_PTS_STATION_HANDLING_MINUTES,
    RP_PTS_DISPATCH_MINUTES,
    RP_PTS_SHIELDED_CARRIER_MASS_LIMIT_KG,
    RP_PTS_PUBLISHED_SYSTEM_CAPEX_REFERENCE_USD,
    RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD,
    RP_PTS_ANNUAL_ENERGY_OPEX_USD,
)

RP_PTS_COMPATIBLE_STREAMS = frozenset({"RADIOPHARMACEUTICAL_NUCLEAR"})
RP_PTS_INSTALLED_STATIONS = 2  # 1 source (radiopharmacy) + 1 destination (centralized injection suite).
RP_PTS_SERVED_FLOORS = 1  # nuclear-medicine suite is centralized, not floor-distributed (see module docstring).
RP_PTS_SHIELDING_STATUS = "CLINICALLY_DEMONSTRATED_BUT_PROJECT_SHIELDING_NOT_CALIBRATED"  # Section 14.


@dataclass(frozen=True)
class RpPtsMissionCycle:
    dispatch_minutes: float
    source_handling_minutes: float
    tube_transport_minutes: float
    destination_handling_minutes: float
    total_minutes: float
    route_status: str


def compute_rp_pts_mission_cycle(*, network_length_m: float) -> RpPtsMissionCycle:
    """T_RPPTS = dispatch + source_handling + tube_transport(L/v) +
    destination_handling (Section 17). `T_queue`/`T_last_mile`/
    `T_carrier_reavailability` are NOT separately added here: the
    destination station IS the centralized injection suite (Section 15
    topology), so no further last-mile hand-off distance exists; queueing
    beyond dispatch and carrier-reavailability delay have no defensible
    authority and are disclosed separately (never silently fabricated as
    zero-cost, never silently added as an invented duration)."""
    speed = RP_PTS_OPERATING_SPEED_M_PER_S.active_value
    dispatch = RP_PTS_DISPATCH_MINUTES.active_value
    handling = RP_PTS_STATION_HANDLING_MINUTES.active_value
    tube_transport = (network_length_m / speed) / 60.0
    total = dispatch + handling + tube_transport + handling
    return RpPtsMissionCycle(
        dispatch_minutes=dispatch, source_handling_minutes=handling, tube_transport_minutes=tube_transport,
        destination_handling_minutes=handling, total_minutes=total,
        route_status="FACILITY_GEOMETRY_REUSED_FROM_MRT_GUIDEWAY_TRUNK",
    )


@dataclass(frozen=True)
class RpPtsCapexLedger:
    network_station_carrier_controls_installation_capex: float
    shielding_certification_delta_capex: float | None
    total_capex: float
    notes: tuple[str, ...]


def compute_rp_pts_capex() -> RpPtsCapexLedger:
    """C_RPPTS = C_network + C_stations + C_carriers + C_controls +
    C_installation + C_other_nuclear_specific (Section 21). The first five
    terms have no dedicated-RP-PTS-specific breakdown available anywhere
    (manufacturer/literature/repo) -- per Section 12, the published $350,000
    illustrative ordinary-PTS-system reference is used as an
    EVIDENCE_BASED_PLANNING_DEFAULT bundle for them (NOT a calibrated
    radioactive-system cost). `C_other_nuclear_specific` (shielding/
    certification delta) has no defensible value at all and is NOT charged
    as $0 -- it is reported as `None`/NOT_CALIBRATED with a break-even bound
    computed by the caller, never silently folded into the bundle above."""
    bundle = RP_PTS_PUBLISHED_SYSTEM_CAPEX_REFERENCE_USD.active_value
    return RpPtsCapexLedger(
        network_station_carrier_controls_installation_capex=bundle,
        shielding_certification_delta_capex=None,
        total_capex=bundle,
        notes=(
            f"C_network+C_stations+C_carriers+C_controls+C_installation = ${bundle:,.0f} "
            f"({RP_PTS_PUBLISHED_SYSTEM_CAPEX_REFERENCE_USD.status}, {RP_PTS_PUBLISHED_SYSTEM_CAPEX_REFERENCE_USD.source}) "
            "-- an ordinary-PTS-scale reference, NOT a validated dedicated-radioactive-transport installed cost.",
            "C_other_nuclear_specific (shielding/certification delta) = NOT_CALIBRATED -- no defensible value exists; "
            "NOT charged as $0 -- see break-even analysis for the maximum tolerable value.",
        ),
    )


@dataclass(frozen=True)
class RpPtsOpexLedger:
    human_labor_annual_opex: float
    human_labor_fte: float
    energy_annual_opex: float
    maintenance_annual_opex: float
    total_calibrated_annual_opex: float
    notes: tuple[str, ...]


def compute_rp_pts_opex(*, human_labor_annual_opex: float, human_labor_fte: float) -> RpPtsOpexLedger:
    """Section 22: human handling labor (caller-supplied, WORKLOAD-derived --
    Section 20's audit corrected this away from peak-concurrency-as-FTE,
    see `compute_rp_pts_labor` below), energy, and maintenance -- reusing
    the ordinary-PTS controlled rates as evidence-based planning defaults
    (no dedicated RP-PTS rate exists). Carrier replacement/maintenance is
    NOT separately itemized (no defensible per-carrier rate exists) --
    bundled/disclosed within the maintenance allowance above, never
    fabricated as a separate line."""
    energy = RP_PTS_ANNUAL_ENERGY_OPEX_USD.active_value
    maintenance = RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD.active_value
    total = human_labor_annual_opex + energy + maintenance
    return RpPtsOpexLedger(
        human_labor_annual_opex=human_labor_annual_opex, human_labor_fte=human_labor_fte,
        energy_annual_opex=energy, maintenance_annual_opex=maintenance, total_calibrated_annual_opex=total,
        notes=(
            f"Energy=${energy:,.0f}/yr, maintenance=${maintenance:,.0f}/yr ({RP_PTS_ANNUAL_ENERGY_OPEX_USD.status}/"
            f"{RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD.status}) -- reused ordinary-PTS controlled rates, no dedicated "
            "RP-PTS-specific rate exists; carrier replacement/maintenance is not separately itemized (no defensible rate).",
        ),
    )


@dataclass(frozen=True)
class RpPtsLaborDerivation:
    """Build 2R FTE-semantics closure (Sections 9-20): distinguishes THREE
    genuinely different quantities that must never be conflated:
    `peak_concurrent_carriers`/`peak_concurrent_human_handlers` (max
    simultaneous physical/human requirement at any instant -- a scheduling/
    coverage fact, NOT an annual headcount), `total_human_minutes_per_day`/
    `total_annual_labor_hours` (actual workload), and `workload_derived_fte`
    (annual_hours / productive_hours_per_fte_year -- the ONLY quantity that
    should drive annual labor COST unless an explicit minimum-staffing
    policy authority exists, which this repo does not have for a new,
    narrow, low-volume dedicated technology)."""

    missions_per_day: int
    peak_concurrent_carriers: int
    peak_concurrent_human_handlers: int
    total_human_minutes_per_day: float
    total_human_hours_per_day: float
    total_annual_labor_hours: float
    productive_hours_per_fte_year: float
    workload_derived_fte: float
    final_required_fte: float
    notes: tuple[str, ...]


def compute_rp_pts_labor(
    *, missions_per_day: int, human_touch_minutes_per_mission: float, peak_concurrent_carriers: int,
    peak_concurrent_human_handlers: int, operating_days_per_year: int, productive_hours_per_fte_year: float,
) -> RpPtsLaborDerivation:
    """Section 20 audit conclusion: CONFIRMED_FTE_SEMANTICS_DEFECT in the
    prior round -- `required_fte = max(peak_concurrency, workload_derived)`
    is the CORRECT pattern for PHYSICAL ASSETS that must be INSTALLED to
    cover simultaneous physical need (AGV fleet size, PTS station count --
    a vehicle/tube cannot be time-shared across two simultaneous missions),
    but it is NOT automatically correct for a NEW, narrow, low-volume
    DEDICATED human labor pool with no established minimum-simultaneous-
    staffing policy authority in this repo. `final_required_fte` is
    therefore the WORKLOAD-derived value only; `peak_concurrent_human_
    handlers` is disclosed SEPARATELY as a scheduling/rostering fact (the
    batch-release pattern genuinely requires this many people to be
    PRESENT at that instant -- plausibly met by existing/shared/flex staff,
    not by hiring that many new full-time positions)."""
    total_human_minutes_per_day = missions_per_day * human_touch_minutes_per_mission
    total_human_hours_per_day = total_human_minutes_per_day / 60.0
    total_annual_labor_hours = total_human_hours_per_day * operating_days_per_year
    workload_derived_fte = (
        math.ceil(total_annual_labor_hours / productive_hours_per_fte_year) if productive_hours_per_fte_year > 0 else 0.0
    )
    return RpPtsLaborDerivation(
        missions_per_day=missions_per_day, peak_concurrent_carriers=peak_concurrent_carriers,
        peak_concurrent_human_handlers=peak_concurrent_human_handlers,
        total_human_minutes_per_day=total_human_minutes_per_day, total_human_hours_per_day=total_human_hours_per_day,
        total_annual_labor_hours=total_annual_labor_hours, productive_hours_per_fte_year=productive_hours_per_fte_year,
        workload_derived_fte=workload_derived_fte, final_required_fte=workload_derived_fte,
        notes=(
            f"CONFIRMED_FTE_SEMANTICS_DEFECT (corrected): peak_concurrent_carriers={peak_concurrent_carriers} and "
            f"peak_concurrent_human_handlers={peak_concurrent_human_handlers} (batch-release clustering -- both source "
            "and destination handling windows overlap almost entirely within each ~5-dose batch) are scheduling/"
            "coverage facts, NOT annual headcount -- no explicit minimum-simultaneous-staffing policy authority exists "
            "in this repo for a new, narrow, low-volume dedicated technology (total workload is only "
            f"{total_annual_labor_hours:.0f} hours/year). final_required_fte=workload_derived_fte="
            f"{workload_derived_fte:.0f} (annual_hours/productive_hours_per_fte_year), NOT max(peak, workload).",
        ),
    )


@dataclass(frozen=True)
class DedicatedRpPtsNuclearEvaluation:
    """Section 32/33: the complete Dedicated RP-PTS nuclear-transport-leg
    physical + economic model for the current benchmark. NEVER a fifth
    whole-architecture engine -- only replaces the nuclear transport
    component (Section 29)."""

    missions_per_day: int
    speed_m_per_s: float
    network_length_m: float
    installed_stations: int
    served_floors: int
    cycle: RpPtsMissionCycle
    labor: RpPtsLaborDerivation
    capex: RpPtsCapexLedger
    opex: RpPtsOpexLedger
    shielding_status: str
    shielded_carrier_mass_limit_kg: float | None
    notes: tuple[str, ...]

"""Phase 3.1 Part A -- Transport Energy/Maintenance Closure (Light-MRT + AGV/PTS/RP-PTS).

AUDIT PERFORMED FIRST (validation sequence step A), reading the actual repo
constants -- never assumed:

  MRT mass/guideway   -- `shared_mrt_multistream_authority.LIGHT_MRT_LOADED_MASS_CEILING_KG`
                          (=5.0 kg) and `.LIGHT_MRT_GUIDEWAY_CAPEX_PER_M` (=$2,000/m)
                          ALREADY EXIST for this exact Light-MRT scope -- reused
                          here verbatim, never re-defined with a second value.
  MRT carrier CapEx   -- MISSING for Light-MRT specifically (the existing
                          `models.PlannerAssumptions.mrt_carrier_capex_per_installed_unit
                          = $10,000` belongs to the separate, preserved HEAVY MRT
                          scope). A new `MRT_CARRIER_CAPEX_USD` ($5,000) is added
                          below, scoped to Light-MRT only.
  MRT moving power/energy -- `mrt_auxiliary_systems_authority.compute_acceleration_energy_j`
                          computes KINETIC energy (0.5*m*v^2) only -- explicitly NOT
                          an electrical-draw model (section 3: "do not derive
                          electrical input from kinetic energy alone"). No
                          P*t-based MRT electrical-mission-energy authority exists
                          yet -- added below as a genuinely new, disclosed
                          CONTROLLED_PLANNING_ASSUMPTION.
  MRT carrier/guideway maintenance -- `models.PlannerAssumptions
                          .mrt_carrier_maintenance_opex_per_installed_unit_year`
                          (flat $500/unit) and `.mrt_guideway_maintenance_fraction_of_capex_per_year`
                          (3%/year) ALREADY EXIST for the HEAVY MRT scope --
                          untouched. A distinct 10%/year Light-MRT authority is
                          added below (section 7-8), never overwriting the heavy
                          scope's 3%.
  Electricity tariff  -- `electricity_cost_per_kwh` is an EXISTING, widely reused
                          concept (`infrastructure_opex.py`, `decision_pipeline.py`,
                          `architecture_report.py`, $0.12-$0.18/kWh across
                          scenarios). This module does NOT create a competing
                          tariff authority -- `MRT_ELECTRICITY_TARIFF_USD_PER_KWH`
                          below is only a standalone default for callers with no
                          caller-supplied tariff (section 5), reusing the SAME
                          concept/units.
  AGV energy/maintenance -- `conventional_transport_authority.DEFAULT_AGV_MODEL
                          .annual_energy_opex` ($1,500/vehicle/yr, flat) and
                          `.annual_maintenance_opex` ($4,000/vehicle/yr, flat)
                          ALREADY EXIST and are ALREADY included in current OPEX
                          (confirmed by `test_agv_pts_maintenance_energy_authorities_already_in_current_opex`).
                          No distance-sensitive AGV energy coefficient exists --
                          `AGV_ENERGY_KWH_PER_KM` is added below as a genuinely new,
                          OPTIONAL, additive coefficient (never silently
                          substituted for the existing flat figure, to avoid
                          double counting).
  PTS energy/maintenance -- `DEFAULT_PTS_NETWORK.annual_energy_opex`
                          ($1,000/network/yr) and `.annual_maintenance_opex`
                          ($8,000/network/yr) ALREADY EXIST, flat, already
                          included in current OPEX. `PTS_VARIABLE_ENERGY_KWH_PER_CAPSULE_KM`
                          is added below as an optional additive coefficient for
                          the same reason.
  RP-PTS energy/maintenance -- `editable_default_authority.RP_PTS_ANNUAL_ENERGY_OPEX_USD`/
                          `RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD` ALREADY EXIST as
                          SEPARATELY IDENTIFIABLE editable parameters, already
                          explicitly documented as reusing ordinary-PTS rates
                          (`source=` field states this verbatim) -- section 12's
                          requirement is therefore ALREADY satisfied; nothing new
                          is created here for RP-PTS.
  $12,000/m guideway CapEx -- used pervasively across dozens of PRE-EXISTING test
                          files (test_infrastructure_capex.py, test_decision_pipeline.py,
                          test_mrt_carrier_fleet.py, etc.) representing the
                          separate, preserved HEAVY MRT test scope's guideway
                          unit cost -- NOT a defect, NOT the Light-MRT value.
                          Classified `LEGITIMATE_OTHER_SCOPE` (section 20) via
                          `classify_12000_per_m_provenance()` below. Only THIS
                          repository's own Phase 3 What-If test fixture (written
                          in the prior Phase 3 session, representing the CURRENT
                          Light-MRT planning scope) is updated to $2,000/m --
                          all historical/unrelated $12,000/m test usages are left
                          untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from editable_default_authority import EditableParameter
from shared_mrt_multistream_authority import LIGHT_MRT_GUIDEWAY_CAPEX_PER_M, LIGHT_MRT_LOADED_MASS_CEILING_KG
from mrt_canonical_configuration import (
    CARRIER_CAPEX_USD as _CANONICAL_CARRIER_CAPEX_USD,
    EMPTY_CARRIER_MASS_TARGET_LOW_KG as _CANONICAL_EMPTY_CARRIER_MASS_KG,
    MAX_GROSS_MOVING_MASS_KG as _CANONICAL_MAX_GROSS_MOVING_MASS_KG,
)

# ---------------------------------------------------------------------------
# Section 1: Final MRT canonical controlled design basis (bound to
# mrt_canonical_configuration -- the single canonical owner).
# ---------------------------------------------------------------------------

FULLY_LOADED_MRT_CARRIER_MASS_KG = LIGHT_MRT_LOADED_MASS_CEILING_KG
"""Reuses the EXISTING canonical ceiling verbatim (=5.0 kg, now sourced from
mrt_canonical_configuration.MAX_GROSS_MOVING_MASS_KG via
shared_mrt_multistream_authority) -- never a second, independently-drifting
mass authority."""

EMPTY_MRT_CARRIER_MASS_KG = _CANONICAL_EMPTY_CARRIER_MASS_KG
"""Canonical empty-carrier target low bound (=2.0 kg). Bound to
mrt_canonical_configuration -- never a second literal."""
MAX_MRT_PAYLOAD_KG = _CANONICAL_MAX_GROSS_MOVING_MASS_KG - _CANONICAL_EMPTY_CARRIER_MASS_KG
"""Derived from the canonical ceiling minus canonical empty target (=3.0 kg),
so empty + payload can never exceed the 5.0 kg gross ceiling by construction."""
assert EMPTY_MRT_CARRIER_MASS_KG + MAX_MRT_PAYLOAD_KG == FULLY_LOADED_MRT_CARRIER_MASS_KG

MRT_CARRIER_CAPEX_USD = EditableParameter(
    parameter_id="MRT_CARRIER_CAPEX_USD",
    default_value=_CANONICAL_CARRIER_CAPEX_USD,
    units="USD per carrier",
    source=(
        "MRT CANONICAL CONFIGURATION CORRECTION (Section 0.7/12): bound to the single canonical owner "
        "mrt_canonical_configuration.CARRIER_CAPEX_USD (=$2,000/carrier). CORRECTS the prior divergent "
        "$5,000 Light-MRT value. Distinct from models.PlannerAssumptions.mrt_carrier_capex_per_installed_unit "
        "($10,000, unchanged, preserved for the separate heavy-MRT scope, Section 29)."
    ),
    source_type="CONTROLLED_ENGINEERING_ASSUMPTION",
    confidence="LOW",
    notes="Never confused with MRT_GUIDEWAY_CAPEX_PER_M_USD ($/m, a distinct authority).",
)

MRT_GUIDEWAY_CAPEX_PER_M_USD = LIGHT_MRT_GUIDEWAY_CAPEX_PER_M
"""Alias, not a duplicate -- reuses `shared_mrt_multistream_authority.LIGHT_MRT_GUIDEWAY_CAPEX_PER_M`
(now =$2,500/m, canonical two-way) verbatim so the two names can never
numerically drift apart."""

# ---------------------------------------------------------------------------
# Section 3: MRT moving power (electrical draw, NOT kinetic energy)
# ---------------------------------------------------------------------------

MRT_MOVING_POWER_KW = EditableParameter(
    parameter_id="MRT_MOVING_POWER_KW",
    default_value=0.75,
    units="kW",
    source=(
        "Section 3: controlled planning placeholder for TOTAL electrical draw while moving (coil resistive "
        "losses, resonant losses, power electronics, levitation/support, centering, controls, other "
        "inefficiencies combined) -- NOT derived from kinetic energy (0.5*m*v^2) alone, and NOT measured "
        "prototype performance. Distinct from `mrt_auxiliary_systems_authority.compute_acceleration_energy_j` "
        "(kinetic energy only)."
    ),
    source_type="CONTROLLED_PLANNING_ASSUMPTION",
    confidence="LOW",
    notes="Preserves future ability to calibrate horizontal/vertical moving power separately (see moving_power_horizontal_kw/moving_power_vertical_kw params below).",
)

MRT_ELECTRICITY_TARIFF_USD_PER_KWH = EditableParameter(
    parameter_id="MRT_ELECTRICITY_TARIFF_USD_PER_KWH",
    default_value=0.15,
    units="USD/kWh",
    source=(
        "Section 5: reuses the EXISTING `electricity_cost_per_kwh` concept already used across "
        "infrastructure_opex.py/decision_pipeline.py/architecture_report.py ($0.12-$0.18/kWh in various "
        "scenarios) -- this is only a standalone default for callers that do not supply their own tariff; "
        "it is not a competing/second tariff authority."
    ),
    source_type="CONTROLLED_PLANNING_ASSUMPTION",
    confidence="LOW",
)

# ---------------------------------------------------------------------------
# Section 7-8: MRT carrier/guideway maintenance (Light-MRT scope, distinct
# from the preserved heavy-MRT 3%/year `PlannerAssumptions` authority)
# ---------------------------------------------------------------------------

MRT_CARRIER_MAINTENANCE_FRACTION_PER_YEAR = EditableParameter(
    parameter_id="MRT_CARRIER_MAINTENANCE_FRACTION_PER_YEAR",
    default_value=0.10,
    units="fraction of carrier CapEx per year",
    source="Section 7: MRT controlled planning value. At the canonical MRT_CARRIER_CAPEX_USD=$2,000, this is $200/carrier-year.",
    source_type="CONTROLLED_PLANNING_ASSUMPTION",
    confidence="LOW",
)

MRT_GUIDEWAY_MAINTENANCE_FRACTION_PER_YEAR = EditableParameter(
    parameter_id="MRT_GUIDEWAY_MAINTENANCE_FRACTION_PER_YEAR",
    default_value=0.10,
    units="fraction of installed guideway CapEx per year",
    source=(
        "Section 8: Light-MRT controlled planning value. MUST be applied to INSTALLED_NETWORK_GEOMETRY CapEx "
        "(never mission-route length). At $2,000/m x 222m = $444,000 installed CapEx, this is $44,400/year."
    ),
    source_type="CONTROLLED_PLANNING_ASSUMPTION",
    confidence="LOW",
)


def compute_mrt_carrier_annual_maintenance_usd(
    *, carrier_count: int, carrier_capex_usd: float | None = None, fraction_per_year: float | None = None,
) -> float:
    """Section 7. `carrier_capex_usd`/`fraction_per_year` default to the
    controlled Light-MRT authorities above -- never hard-coded."""
    capex = MRT_CARRIER_CAPEX_USD.active_value if carrier_capex_usd is None else carrier_capex_usd
    fraction = MRT_CARRIER_MAINTENANCE_FRACTION_PER_YEAR.active_value if fraction_per_year is None else fraction_per_year
    return carrier_count * capex * fraction


def compute_mrt_guideway_annual_maintenance_usd(
    *, installed_guideway_capex_usd: float, fraction_per_year: float | None = None,
) -> float:
    """Section 8. `installed_guideway_capex_usd` MUST be derived from
    INSTALLED_NETWORK_GEOMETRY (never mission-route length) -- the caller's
    responsibility, enforced by naming/documentation only (no second
    geometry authority is created here)."""
    fraction = MRT_GUIDEWAY_MAINTENANCE_FRACTION_PER_YEAR.active_value if fraction_per_year is None else fraction_per_year
    return installed_guideway_capex_usd * fraction


# ---------------------------------------------------------------------------
# Section 4/6: MRT mission energy -- actual route decomposition (E=P*t),
# never a hardcoded per-mission energy figure.
# ---------------------------------------------------------------------------

MRT_HORIZONTAL_SPEED_M_PER_S = 3.0
"""Reuses the EXISTING `models.PlannerAssumptions.mrt_horizontal_speed_m_per_s`
default value (=3.0) -- duplicated as a float literal only to avoid importing
`models.py` here; both must be kept numerically identical (verified by test)."""
MRT_VERTICAL_SPEED_M_PER_S = 1.5
"""Reuses the EXISTING `models.PlannerAssumptions.mrt_vertical_speed_m_per_s`
default value (=1.5), same rationale as above."""


@dataclass(frozen=True)
class MrtMissionEnergyResult:
    horizontal_m: float
    vertical_m: float
    horizontal_time_s: float
    vertical_time_s: float
    one_way_time_s: float
    horizontal_energy_kwh: float
    vertical_energy_kwh: float
    one_way_energy_kwh: float
    round_trip_energy_kwh: float
    provenance: str = "PHYSICS_DERIVED (E=P*t from route horizontal/vertical decomposition, section 4/6)"


def compute_mrt_mission_energy(
    *, horizontal_m: float, vertical_m: float, horizontal_speed_m_per_s: float = MRT_HORIZONTAL_SPEED_M_PER_S,
    vertical_speed_m_per_s: float = MRT_VERTICAL_SPEED_M_PER_S, moving_power_horizontal_kw: float | None = None,
    moving_power_vertical_kw: float | None = None,
) -> MrtMissionEnergyResult:
    """Section 4/6: E_h = P_h*(L_h/v_h)/3600 ; E_v = P_v*(L_v/v_v)/3600 ;
    E_mission = E_h + E_v. If only one moving-power value exists,
    P_h = P_v = MRT_MOVING_POWER_KW (section 4)."""
    power_h = MRT_MOVING_POWER_KW.active_value if moving_power_horizontal_kw is None else moving_power_horizontal_kw
    power_v = MRT_MOVING_POWER_KW.active_value if moving_power_vertical_kw is None else moving_power_vertical_kw
    h_time_s = horizontal_m / horizontal_speed_m_per_s if horizontal_speed_m_per_s > 0 else 0.0
    v_time_s = vertical_m / vertical_speed_m_per_s if vertical_speed_m_per_s > 0 else 0.0
    e_h_kwh = power_h * (h_time_s / 3600.0)
    e_v_kwh = power_v * (v_time_s / 3600.0)
    one_way_kwh = e_h_kwh + e_v_kwh
    return MrtMissionEnergyResult(
        horizontal_m=horizontal_m, vertical_m=vertical_m, horizontal_time_s=h_time_s, vertical_time_s=v_time_s,
        one_way_time_s=h_time_s + v_time_s, horizontal_energy_kwh=e_h_kwh, vertical_energy_kwh=e_v_kwh,
        one_way_energy_kwh=one_way_kwh, round_trip_energy_kwh=one_way_kwh * 2.0,
    )


def compute_mrt_mission_electricity_opex_usd(*, energy_kwh: float, tariff_usd_per_kwh: float | None = None) -> float:
    tariff = MRT_ELECTRICITY_TARIFF_USD_PER_KWH.active_value if tariff_usd_per_kwh is None else tariff_usd_per_kwh
    return energy_kwh * tariff


@dataclass(frozen=True)
class MrtMissionEnergyInputs:
    """Section 14/18/19: caller-supplied MISSION_ROUTE_GEOMETRY decomposition
    (horizontal/vertical) before/after a change, plus the annual mission
    count -- never invented by this module. Used only where a caller proves
    a genuine MRT mission-distance change (sections 16-17: never fabricated
    for MOVE_SCANNER/CHANGE_PATIENT_ROOM unless genuinely present)."""

    horizontal_m_before: float
    horizontal_m_after: float
    vertical_m_before: float
    vertical_m_after: float
    missions_per_year: float
    moving_power_horizontal_kw: float | None = None
    moving_power_vertical_kw: float | None = None
    tariff_usd_per_kwh: float | None = None


def compute_mrt_mission_energy_annual_opex_delta_usd(inputs: MrtMissionEnergyInputs) -> float:
    """Section 4/14: distance-sensitive mission electricity OPEX delta,
    derived from actual route decomposition -- never hardcoded per mission."""
    before = compute_mrt_mission_energy(
        horizontal_m=inputs.horizontal_m_before, vertical_m=inputs.vertical_m_before,
        moving_power_horizontal_kw=inputs.moving_power_horizontal_kw, moving_power_vertical_kw=inputs.moving_power_vertical_kw,
    )
    after = compute_mrt_mission_energy(
        horizontal_m=inputs.horizontal_m_after, vertical_m=inputs.vertical_m_after,
        moving_power_horizontal_kw=inputs.moving_power_horizontal_kw, moving_power_vertical_kw=inputs.moving_power_vertical_kw,
    )
    annual_before = compute_mrt_mission_electricity_opex_usd(
        energy_kwh=before.round_trip_energy_kwh * inputs.missions_per_year, tariff_usd_per_kwh=inputs.tariff_usd_per_kwh,
    )
    annual_after = compute_mrt_mission_electricity_opex_usd(
        energy_kwh=after.round_trip_energy_kwh * inputs.missions_per_year, tariff_usd_per_kwh=inputs.tariff_usd_per_kwh,
    )
    return annual_after - annual_before


# ---------------------------------------------------------------------------
# Section 10-12: AGV / ordinary PTS / RP-PTS -- additive, optional
# distance-sensitive coefficients ONLY (existing flat authorities are
# reused, never replaced, to avoid double counting).
# ---------------------------------------------------------------------------

AGV_ENERGY_KWH_PER_KM = EditableParameter(
    parameter_id="AGV_ENERGY_KWH_PER_KM",
    default_value=0.5,
    units="kWh/km",
    source=(
        "Section 10: no distance-sensitive AGV energy coefficient exists in the repository -- "
        "`conventional_transport_authority.DEFAULT_AGV_MODEL.annual_energy_opex` ($1,500/vehicle/yr) is a "
        "FLAT lumped figure, already included in current OPEX. This is a NEW, OPTIONAL, additive controlled "
        "default for callers that need a distance-sensitive component; it must never be added on top of the "
        "flat figure for the SAME vehicle without disclosure (double-counting risk)."
    ),
    source_type="CONTROLLED_ENGINEERING_ASSUMPTION",
    confidence="LOW",
)


def compute_agv_distance_energy_kwh(*, distance_km: float, energy_kwh_per_km: float | None = None) -> float:
    """Section 10: mission energy MUST use the actual route distance already
    activated in Phase 2B -- never a hardcoded per-mission figure."""
    rate = AGV_ENERGY_KWH_PER_KM.active_value if energy_kwh_per_km is None else energy_kwh_per_km
    return distance_km * rate


PTS_VARIABLE_ENERGY_KWH_PER_CAPSULE_KM = EditableParameter(
    parameter_id="PTS_VARIABLE_ENERGY_KWH_PER_CAPSULE_KM",
    default_value=0.1,
    units="kWh per capsule-km",
    source=(
        "Section 11: no distance-sensitive PTS energy coefficient exists -- `DEFAULT_PTS_NETWORK.annual_energy_opex` "
        "($1,000/network/yr) is a FLAT lumped figure, already included in current OPEX. NEW, OPTIONAL, additive "
        "controlled default; route distance follows project-specific PTS geometry if supplied, otherwise "
        "SHARED_MRT_REFERENCE_CORRIDOR_ASSUMPTION (Phase 2B, `authoritative_geometry_routing_activation.py`)."
    ),
    source_type="CONTROLLED_ENGINEERING_ASSUMPTION",
    confidence="LOW",
)


def compute_pts_distance_energy_kwh(*, distance_km: float, kwh_per_capsule_km: float | None = None) -> float:
    rate = PTS_VARIABLE_ENERGY_KWH_PER_CAPSULE_KM.active_value if kwh_per_capsule_km is None else kwh_per_capsule_km
    return distance_km * rate


MANUAL_PROPULSION_ELECTRICITY_OPEX_USD = 0.0
"""Section 13: Manual propulsion-electricity OPEX is genuinely zero (human
porters) -- a hard invariant, not an editable planning assumption. Existing
Manual OPEX (porter labor, shift/overtime, cart/equipment economics) is
untouched and unaffected by this module."""


# ---------------------------------------------------------------------------
# Section 20: $12,000/m provenance
# ---------------------------------------------------------------------------

Provenance12000Status = Literal["TEST_ONLY", "LEGITIMATE_OTHER_SCOPE", "DEFECT_CORRECTED"]


def classify_12000_per_m_provenance() -> Provenance12000Status:
    """Section 20: $12,000/m is used pervasively across dozens of PRE-EXISTING
    test files (test_infrastructure_capex.py, test_decision_pipeline.py,
    test_mrt_carrier_fleet.py, test_cyclotron_fleet_integration.py, etc.) as
    the guideway unit cost for the SEPARATE, PRESERVED heavy-MRT test scope --
    not the Light-MRT scope this phase controls. This is not a defect: it is
    a legitimate, different, unrelated scope, left untouched (section 20:
    'do not silently rewrite unrelated historical tests/scopes')."""
    return "LEGITIMATE_OTHER_SCOPE"


# ---------------------------------------------------------------------------
# Section 58/191-style audit table (existing-authority audit, section 1/10-12)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransportEnergyMaintenanceAuditEntry:
    technology: str
    energy_authority: str
    distance_sensitive: bool
    maintenance_authority: str
    editable: bool
    status: Literal["VALIDATED", "CONTROLLED_DEFAULT", "BLOCKED"]


def audit_transport_energy_maintenance_authorities() -> tuple[TransportEnergyMaintenanceAuditEntry, ...]:
    from conventional_transport_authority import DEFAULT_AGV_MODEL, DEFAULT_PTS_NETWORK
    from editable_default_authority import RP_PTS_ANNUAL_ENERGY_OPEX_USD, RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD

    return (
        TransportEnergyMaintenanceAuditEntry(
            technology="MRT", energy_authority="compute_mrt_mission_energy (E=P*t, route-derived, NEW)",
            distance_sensitive=True, maintenance_authority="compute_mrt_guideway_annual_maintenance_usd / compute_mrt_carrier_annual_maintenance_usd (NEW, 10%/yr)",
            editable=True, status="VALIDATED",
        ),
        TransportEnergyMaintenanceAuditEntry(
            technology="AGV", energy_authority=f"DEFAULT_AGV_MODEL.annual_energy_opex (existing, flat, ${DEFAULT_AGV_MODEL.annual_energy_opex:,.0f}/vehicle/yr) + optional AGV_ENERGY_KWH_PER_KM (NEW, additive)",
            distance_sensitive=False, maintenance_authority=f"DEFAULT_AGV_MODEL.annual_maintenance_opex (existing, flat, ${DEFAULT_AGV_MODEL.annual_maintenance_opex:,.0f}/vehicle/yr)",
            editable=True, status="CONTROLLED_DEFAULT",
        ),
        TransportEnergyMaintenanceAuditEntry(
            technology="ORDINARY_PTS", energy_authority=f"DEFAULT_PTS_NETWORK.annual_energy_opex (existing, flat, ${DEFAULT_PTS_NETWORK.annual_energy_opex:,.0f}/network/yr) + optional PTS_VARIABLE_ENERGY_KWH_PER_CAPSULE_KM (NEW, additive)",
            distance_sensitive=False, maintenance_authority=f"DEFAULT_PTS_NETWORK.annual_maintenance_opex (existing, flat, ${DEFAULT_PTS_NETWORK.annual_maintenance_opex:,.0f}/network/yr)",
            editable=True, status="CONTROLLED_DEFAULT",
        ),
        TransportEnergyMaintenanceAuditEntry(
            technology="DEDICATED_RP_PTS", energy_authority=f"RP_PTS_ANNUAL_ENERGY_OPEX_USD (existing, ${RP_PTS_ANNUAL_ENERGY_OPEX_USD.active_value:,.0f}/yr, explicitly documented reuse of ordinary-PTS rate)",
            distance_sensitive=False, maintenance_authority=f"RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD (existing, ${RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD.active_value:,.0f}/yr, same documented reuse)",
            editable=True, status="CONTROLLED_DEFAULT",
        ),
        TransportEnergyMaintenanceAuditEntry(
            technology="MANUAL", energy_authority=f"MANUAL_PROPULSION_ELECTRICITY_OPEX_USD (hard invariant, ${MANUAL_PROPULSION_ELECTRICITY_OPEX_USD:.2f})",
            distance_sensitive=False, maintenance_authority="Existing porter labor/shift/cart economics (untouched, out of this module's scope)",
            editable=False, status="VALIDATED",
        ),
    )

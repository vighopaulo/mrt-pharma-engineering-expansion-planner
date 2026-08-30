"""Super-Build 1: Free-roaming Floor AGV/AMR Transport Authority.

GOVERNANCE / AUTHORITY-FIRST: this module OWNS the genuinely NEW free-roaming
floor AGV/AMR transport technology class that
`transport_technology_authority.FLOOR_AGV_AMR` declared NOT_IMPLEMENTED. It is
a DISTINCT authority from the existing rail-guided `conventional_transport_
authority.AgvModelClass` (technology_class="RGHT"): RGHT != FLOOR_AGV_AMR is a
required repository invariant (transport_technology_authority.py). This module
never reuses RGHT's economics/physics, and never touches MRT, PTS, Manual, or
the Part 3E experiment path.

Two physically DISTINCT free-roaming configurations are modeled (Super-Build
Sec 13/36-50):

    AGV_AMR_LIGHT_CLINICAL  -- small secure clinical courier (specimens,
                               pharmacy, small clinical supplies).
    AGV_AMR_HEAVY_LOGISTICS -- tug/cart logistics vehicle (linen, bulk sterile,
                               meals, waste, carts).

They may share abstractions but retain SEPARATE dimensions / payload / speed /
battery / charging / eligibility / fleet economics. A payload rejected by the
light class NEVER silently enlarges it or acquires the heavy class's capacity
(Sec 39): selecting the heavy vehicle is an explicit decision made by the
caller / future optimizer, never a hidden fallback here.

PROVENANCE: every uncertain physical/economic parameter is an
`editable_default_authority.EditableParameter` carrying units + source +
source_type + calibration status. Unknown battery-replacement cost/lifetime is
CONTROLLED_ENGINEERING_ASSUMPTION or NOT_CALIBRATED -- NEVER $0-filled
(Sec 44/63). Radiopharmaceutical transport defaults to QUALIFICATION_REQUIRED
for BOTH classes (Sec 40) -- economics never manufacture regulatory/shielding
qualification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

from editable_default_authority import EditableParameter

# ===========================================================================
# 1. Technology-class identity (bound to the canonical NOT_IMPLEMENTED gap).
# ===========================================================================

FloorAgvClass = Literal["AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS"]

FLOOR_AGV_AMR_LIGHT_CLINICAL = "AGV_AMR_LIGHT_CLINICAL"
FLOOR_AGV_AMR_HEAVY_LOGISTICS = "AGV_AMR_HEAVY_LOGISTICS"

FLOOR_AGV_TECHNOLOGY_CLASS = "FLOOR_AGV_AMR"
"""The canonical free-roaming technology class from
`transport_technology_authority.FLOOR_AGV_AMR`. This module is its
implementation; RGHT (rail-guided) remains a separate, preserved class."""

RadiopharmEligibilityStatus = Literal[
    "ELIGIBLE", "INELIGIBLE", "QUALIFICATION_REQUIRED", "FACILITY_VALIDATION_REQUIRED", "NOT_MODELED",
]

# ===========================================================================
# 2. Controlled-benchmark parameters (editable, provenance-tagged). None of
#    these is a calibrated vendor quote; all are transparent planning defaults
#    a facility/vendor can override. Never labeled CALIBRATED.
# ===========================================================================

def _bench(pid: str, value: float | None, units: str, source: str, conf: str = "LOW") -> EditableParameter:
    return EditableParameter(
        parameter_id=pid, default_value=value, units=units, source=source,
        source_type="CONTROLLED_ENGINEERING_ASSUMPTION" if value is not None else "NOT_CALIBRATED",
        confidence=conf,
    )


# --- Light-clinical controlled benchmarks -------------------------------------------------
LIGHT_VEHICLE_LENGTH_M = _bench("FLOOR_AGV_LIGHT_LENGTH_M", 0.70, "m", "Compact clinical courier AMR planning envelope")
LIGHT_VEHICLE_WIDTH_M = _bench("FLOOR_AGV_LIGHT_WIDTH_M", 0.55, "m", "Compact clinical courier AMR planning envelope")
LIGHT_VEHICLE_HEIGHT_M = _bench("FLOOR_AGV_LIGHT_HEIGHT_M", 1.20, "m", "Compact clinical courier AMR planning envelope")
LIGHT_PAYLOAD_MASS_LIMIT_KG = _bench("FLOOR_AGV_LIGHT_PAYLOAD_KG", 40.0, "kg", "Secure-compartment clinical courier payload planning limit")
LIGHT_PAYLOAD_VOLUME_LIMIT_L = _bench("FLOOR_AGV_LIGHT_VOLUME_L", 60.0, "L", "Secure-compartment clinical courier volume planning limit")
LIGHT_SPEED_M_PER_S = _bench("FLOOR_AGV_LIGHT_SPEED_M_PER_S", 1.2, "m/s", "Indoor clinical AMR nominal travel-speed planning default", conf="MEDIUM")
LIGHT_LOAD_MINUTES = _bench("FLOOR_AGV_LIGHT_LOAD_MIN", 1.5, "min", "Automated secure-compartment load planning default")
LIGHT_UNLOAD_MINUTES = _bench("FLOOR_AGV_LIGHT_UNLOAD_MIN", 1.5, "min", "Automated secure-compartment unload planning default")
LIGHT_BATTERY_CAPACITY_KWH = _bench("FLOOR_AGV_LIGHT_BATTERY_KWH", 1.0, "kWh", "Compact clinical AMR battery planning default")
LIGHT_USABLE_BATTERY_FRACTION = _bench("FLOOR_AGV_LIGHT_USABLE_SOC_FRACTION", 0.80, "fraction", "SoC operating window (20-100%) planning default", conf="MEDIUM")
LIGHT_ENERGY_KWH_PER_KM = _bench("FLOOR_AGV_LIGHT_ENERGY_KWH_PER_KM", 0.10, "kWh/km", "Compact indoor AMR traction-energy planning default")
LIGHT_IDLE_POWER_KW = _bench("FLOOR_AGV_LIGHT_IDLE_KW", 0.05, "kW", "Onboard-controls/idle draw planning default")
LIGHT_CHARGING_POWER_KW = _bench("FLOOR_AGV_LIGHT_CHARGE_KW", 0.6, "kW", "Contact/inductive clinical AMR charging planning default")
LIGHT_CHARGING_EFFICIENCY = _bench("FLOOR_AGV_LIGHT_CHARGE_EFF", 0.90, "fraction", "Charging efficiency planning default", conf="MEDIUM")
LIGHT_VEHICLE_CAPEX_USD = _bench("FLOOR_AGV_LIGHT_VEHICLE_CAPEX", 90_000.0, "USD/vehicle", "Clinical courier AMR unit planning benchmark")
LIGHT_VEHICLE_MAINT_USD_PER_YEAR = _bench("FLOOR_AGV_LIGHT_MAINT_USD_YR", 3_500.0, "USD/vehicle-yr", "Clinical AMR preventive+corrective maintenance planning default")
LIGHT_BATTERY_REPLACEMENT_USD = _bench("FLOOR_AGV_LIGHT_BATTERY_REPLACEMENT_USD", 2_000.0, "USD/battery", "Li-ion pack replacement planning benchmark")
LIGHT_BATTERY_LIFE_YEARS = _bench("FLOOR_AGV_LIGHT_BATTERY_LIFE_YR", 4.0, "years", "Duty-cycle battery lifetime planning default")

# --- Heavy-logistics controlled benchmarks ------------------------------------------------
HEAVY_VEHICLE_LENGTH_M = _bench("FLOOR_AGV_HEAVY_LENGTH_M", 1.30, "m", "Tug/cart logistics AMR planning envelope")
HEAVY_VEHICLE_WIDTH_M = _bench("FLOOR_AGV_HEAVY_WIDTH_M", 0.80, "m", "Tug/cart logistics AMR planning envelope")
HEAVY_VEHICLE_HEIGHT_M = _bench("FLOOR_AGV_HEAVY_HEIGHT_M", 1.60, "m", "Tug/cart logistics AMR planning envelope")
HEAVY_PAYLOAD_MASS_LIMIT_KG = _bench("FLOOR_AGV_HEAVY_PAYLOAD_KG", 300.0, "kg", "Towed/onboard hospital-cart logistics payload planning limit")
HEAVY_PAYLOAD_VOLUME_LIMIT_L = _bench("FLOOR_AGV_HEAVY_VOLUME_L", 900.0, "L", "Hospital-cart logistics volume planning limit")
HEAVY_SPEED_M_PER_S = _bench("FLOOR_AGV_HEAVY_SPEED_M_PER_S", 1.0, "m/s", "Loaded logistics AMR nominal travel-speed planning default", conf="MEDIUM")
HEAVY_LOAD_MINUTES = _bench("FLOOR_AGV_HEAVY_LOAD_MIN", 4.0, "min", "Cart hitch/load planning default")
HEAVY_UNLOAD_MINUTES = _bench("FLOOR_AGV_HEAVY_UNLOAD_MIN", 4.0, "min", "Cart unhitch/unload planning default")
HEAVY_BATTERY_CAPACITY_KWH = _bench("FLOOR_AGV_HEAVY_BATTERY_KWH", 4.0, "kWh", "Logistics tug battery planning default")
HEAVY_USABLE_BATTERY_FRACTION = _bench("FLOOR_AGV_HEAVY_USABLE_SOC_FRACTION", 0.80, "fraction", "SoC operating window planning default", conf="MEDIUM")
HEAVY_ENERGY_KWH_PER_KM = _bench("FLOOR_AGV_HEAVY_ENERGY_KWH_PER_KM", 0.40, "kWh/km", "Loaded logistics AMR traction-energy planning default")
HEAVY_IDLE_POWER_KW = _bench("FLOOR_AGV_HEAVY_IDLE_KW", 0.08, "kW", "Onboard-controls/idle draw planning default")
HEAVY_CHARGING_POWER_KW = _bench("FLOOR_AGV_HEAVY_CHARGE_KW", 2.0, "kW", "Logistics AMR charging planning default")
HEAVY_CHARGING_EFFICIENCY = _bench("FLOOR_AGV_HEAVY_CHARGE_EFF", 0.90, "fraction", "Charging efficiency planning default", conf="MEDIUM")
HEAVY_VEHICLE_CAPEX_USD = _bench("FLOOR_AGV_HEAVY_VEHICLE_CAPEX", 130_000.0, "USD/vehicle", "Logistics tug/cart AMR unit planning benchmark")
HEAVY_VEHICLE_MAINT_USD_PER_YEAR = _bench("FLOOR_AGV_HEAVY_MAINT_USD_YR", 6_000.0, "USD/vehicle-yr", "Logistics AMR preventive+corrective maintenance planning default")
HEAVY_BATTERY_REPLACEMENT_USD = _bench("FLOOR_AGV_HEAVY_BATTERY_REPLACEMENT_USD", 5_000.0, "USD/battery", "Logistics-tug Li-ion pack replacement planning benchmark")
HEAVY_BATTERY_LIFE_YEARS = _bench("FLOOR_AGV_HEAVY_BATTERY_LIFE_YR", 4.0, "years", "Duty-cycle battery lifetime planning default")

# --- Shared / infrastructure controlled benchmarks ----------------------------------------
FLOOR_AGV_ELECTRICITY_TARIFF_USD_PER_KWH = _bench("FLOOR_AGV_ELECTRICITY_TARIFF", 0.15, "USD/kWh", "Controlled electricity tariff (matches repo $0.12-0.18 range)", conf="MEDIUM")
FLOOR_AGV_CHARGING_STATION_CAPEX_USD = _bench("FLOOR_AGV_CHARGING_STATION_CAPEX", 12_000.0, "USD/station", "Charging dock planning benchmark")
FLOOR_AGV_CHARGING_STATION_MAINT_USD_PER_YEAR = _bench("FLOOR_AGV_CHARGING_STATION_MAINT", 800.0, "USD/station-yr", "Charging dock maintenance planning default")
FLOOR_AGV_FLEET_MANAGER_CAPEX_USD = _bench("FLOOR_AGV_FLEET_MANAGER_CAPEX", 120_000.0, "USD (once)", "Fleet-management hardware/software integration planning benchmark (charged once, NOT per vehicle)")
FLOOR_AGV_FLEET_SOFTWARE_USD_PER_YEAR = _bench("FLOOR_AGV_FLEET_SOFTWARE_USD_YR", 30_000.0, "USD/yr (once)", "Fleet-management software/support subscription planning default (once, NOT per vehicle)")
FLOOR_AGV_ELEVATOR_INTEGRATION_CAPEX_USD = _bench("FLOOR_AGV_ELEVATOR_INTEGRATION_CAPEX", 25_000.0, "USD/elevator", "Elevator-call integration planning benchmark")
FLOOR_AGV_DOOR_INTEGRATION_CAPEX_USD = _bench("FLOOR_AGV_DOOR_INTEGRATION_CAPEX", 3_000.0, "USD/door", "Automatic-door/access-control integration planning benchmark")
FLOOR_AGV_INSTALL_COMMISSIONING_USD = _bench("FLOOR_AGV_INSTALL_COMMISSION", 40_000.0, "USD (once)", "Install/commissioning/training planning benchmark (once)")
FLOOR_AGV_SUPERVISION_FTE = _bench("FLOOR_AGV_SUPERVISION_FTE", 0.2, "FTE", "Residual human fleet-supervision planning default")

FLOOR_AGV_ELEVATOR_WAIT_MINUTES = _bench("FLOOR_AGV_ELEVATOR_WAIT_MIN", 2.5, "min", "Automated elevator-call wait planning default")
FLOOR_AGV_ELEVATOR_RIDE_MINUTES = _bench("FLOOR_AGV_ELEVATOR_RIDE_MIN", 1.0, "min", "Per-transition elevator ride+enter/exit planning default")
FLOOR_AGV_DOOR_DELAY_MINUTES = _bench("FLOOR_AGV_DOOR_DELAY_MIN", 0.25, "min", "Per automatic-door negotiation planning default")
FLOOR_AGV_AVAILABILITY_PCT = _bench("FLOOR_AGV_AVAILABILITY_PCT", 90.0, "percent", "Fleet mechanical/charging availability planning default", conf="MEDIUM")

# Standby/controls network electricity beyond per-vehicle idle: genuinely uncalibrated.
FLOOR_AGV_NETWORK_STANDBY_KWH_PER_DAY_STATUS = "NOT_CALIBRATED"
"""Facility-level charging-infrastructure standby / fleet-server electricity is
NOT modeled here (no defensible planning value) -- reported as NOT_CALIBRATED,
never $0-filled (Sec 45/63)."""


# ===========================================================================
# 3. Vehicle configuration profile (frozen; distinct per class).
# ===========================================================================

@dataclass(frozen=True)
class FloorAgvProfile:
    """One free-roaming floor AGV/AMR configuration. Light and heavy profiles
    are physically distinct; a payload rejected by one profile NEVER enlarges
    it to the other (Sec 39)."""

    vehicle_class: FloorAgvClass
    length_m: float
    width_m: float
    height_m: float
    payload_mass_limit_kg: float
    payload_volume_limit_l: float
    speed_m_per_s: float
    load_minutes: float
    unload_minutes: float
    battery_capacity_kwh: float
    usable_battery_fraction: float
    energy_kwh_per_km: float
    idle_power_kw: float
    charging_power_kw: float
    charging_efficiency: float
    availability_pct: float
    vehicle_capex_usd: float
    vehicle_maint_usd_per_year: float
    battery_replacement_usd: float
    battery_life_years: float
    # Payload streams the configured vehicle physically supports (mass/volume
    # eligible). Radiopharmaceutical is deliberately ABSENT -- it is
    # QUALIFICATION_REQUIRED for both classes regardless of mass.
    supported_streams: frozenset[str]
    radiopharmaceutical_status: RadiopharmEligibilityStatus = "QUALIFICATION_REQUIRED"
    provenance: str = "CONTROLLED_ENGINEERING_ASSUMPTION (free-roaming floor AGV/AMR planning benchmark; not vendor-calibrated)"


def _p(param: EditableParameter) -> float:
    v = param.active_value
    if v is None:
        raise ValueError(f"{param.parameter_id} is NOT_CALIBRATED and cannot be used as a physical value")
    return float(v)


def default_light_clinical_profile() -> FloorAgvProfile:
    """AGV_AMR_LIGHT_CLINICAL: small secure clinical courier. Supports compact
    clinical streams; NOT bulk linen / bulk sterile (mass/volume envelope)."""
    return FloorAgvProfile(
        vehicle_class="AGV_AMR_LIGHT_CLINICAL",
        length_m=_p(LIGHT_VEHICLE_LENGTH_M), width_m=_p(LIGHT_VEHICLE_WIDTH_M), height_m=_p(LIGHT_VEHICLE_HEIGHT_M),
        payload_mass_limit_kg=_p(LIGHT_PAYLOAD_MASS_LIMIT_KG), payload_volume_limit_l=_p(LIGHT_PAYLOAD_VOLUME_LIMIT_L),
        speed_m_per_s=_p(LIGHT_SPEED_M_PER_S), load_minutes=_p(LIGHT_LOAD_MINUTES), unload_minutes=_p(LIGHT_UNLOAD_MINUTES),
        battery_capacity_kwh=_p(LIGHT_BATTERY_CAPACITY_KWH), usable_battery_fraction=_p(LIGHT_USABLE_BATTERY_FRACTION),
        energy_kwh_per_km=_p(LIGHT_ENERGY_KWH_PER_KM), idle_power_kw=_p(LIGHT_IDLE_POWER_KW),
        charging_power_kw=_p(LIGHT_CHARGING_POWER_KW), charging_efficiency=_p(LIGHT_CHARGING_EFFICIENCY),
        availability_pct=_p(FLOOR_AGV_AVAILABILITY_PCT),
        vehicle_capex_usd=_p(LIGHT_VEHICLE_CAPEX_USD), vehicle_maint_usd_per_year=_p(LIGHT_VEHICLE_MAINT_USD_PER_YEAR),
        battery_replacement_usd=_p(LIGHT_BATTERY_REPLACEMENT_USD), battery_life_years=_p(LIGHT_BATTERY_LIFE_YEARS),
        supported_streams=frozenset({"SPECIMEN_BLOOD", "PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY"}),
    )


def default_heavy_logistics_profile() -> FloorAgvProfile:
    """AGV_AMR_HEAVY_LOGISTICS: tug/cart logistics vehicle. Supports bulk
    logistics streams; a compact-only workload does NOT force selecting it."""
    return FloorAgvProfile(
        vehicle_class="AGV_AMR_HEAVY_LOGISTICS",
        length_m=_p(HEAVY_VEHICLE_LENGTH_M), width_m=_p(HEAVY_VEHICLE_WIDTH_M), height_m=_p(HEAVY_VEHICLE_HEIGHT_M),
        payload_mass_limit_kg=_p(HEAVY_PAYLOAD_MASS_LIMIT_KG), payload_volume_limit_l=_p(HEAVY_PAYLOAD_VOLUME_LIMIT_L),
        speed_m_per_s=_p(HEAVY_SPEED_M_PER_S), load_minutes=_p(HEAVY_LOAD_MINUTES), unload_minutes=_p(HEAVY_UNLOAD_MINUTES),
        battery_capacity_kwh=_p(HEAVY_BATTERY_CAPACITY_KWH), usable_battery_fraction=_p(HEAVY_USABLE_BATTERY_FRACTION),
        energy_kwh_per_km=_p(HEAVY_ENERGY_KWH_PER_KM), idle_power_kw=_p(HEAVY_IDLE_POWER_KW),
        charging_power_kw=_p(HEAVY_CHARGING_POWER_KW), charging_efficiency=_p(HEAVY_CHARGING_EFFICIENCY),
        availability_pct=_p(FLOOR_AGV_AVAILABILITY_PCT),
        vehicle_capex_usd=_p(HEAVY_VEHICLE_CAPEX_USD), vehicle_maint_usd_per_year=_p(HEAVY_VEHICLE_MAINT_USD_PER_YEAR),
        battery_replacement_usd=_p(HEAVY_BATTERY_REPLACEMENT_USD), battery_life_years=_p(HEAVY_BATTERY_LIFE_YEARS),
        supported_streams=frozenset({"CLEAN_LINEN", "STERILE_CLEAN_SUPPLY"}),
    )


DEFAULT_LIGHT_CLINICAL_PROFILE = default_light_clinical_profile()
DEFAULT_HEAVY_LOGISTICS_PROFILE = default_heavy_logistics_profile()


# ===========================================================================
# 4. Payload eligibility against the CONFIGURED class (Sec 39/40).
# ===========================================================================

@dataclass(frozen=True)
class FloorAgvPayloadEligibility:
    vehicle_class: FloorAgvClass
    stream: str
    payload_mass_kg: float | None
    payload_volume_l: float | None
    eligible: bool
    status: Literal["ELIGIBLE", "INELIGIBLE_MASS", "INELIGIBLE_VOLUME", "INELIGIBLE_STREAM", "QUALIFICATION_REQUIRED"]
    reason: str


def evaluate_floor_agv_payload(
    *, profile: FloorAgvProfile, stream: str, payload_mass_kg: float | None = None, payload_volume_l: float | None = None,
) -> FloorAgvPayloadEligibility:
    """Eligibility is judged against the SUPPLIED profile only. A payload the
    profile cannot carry is INELIGIBLE -- it NEVER causes the vehicle to enlarge
    or borrow the other class's capacity (Sec 39). Radiopharmaceutical is always
    QUALIFICATION_REQUIRED regardless of mass (Sec 40)."""
    if stream == "RADIOPHARMACEUTICAL_NUCLEAR":
        return FloorAgvPayloadEligibility(
            profile.vehicle_class, stream, payload_mass_kg, payload_volume_l, False, "QUALIFICATION_REQUIRED",
            "Radiopharmaceutical transport requires facility/technology qualification (shielding/contamination/"
            "dose-rate/regulatory) -- never granted by mass capacity or economics.",
        )
    if stream not in profile.supported_streams:
        return FloorAgvPayloadEligibility(
            profile.vehicle_class, stream, payload_mass_kg, payload_volume_l, False, "INELIGIBLE_STREAM",
            f"{stream} is outside {profile.vehicle_class} supported streams {sorted(profile.supported_streams)}.",
        )
    if payload_mass_kg is not None and payload_mass_kg > profile.payload_mass_limit_kg:
        return FloorAgvPayloadEligibility(
            profile.vehicle_class, stream, payload_mass_kg, payload_volume_l, False, "INELIGIBLE_MASS",
            f"payload {payload_mass_kg} kg exceeds {profile.vehicle_class} limit {profile.payload_mass_limit_kg} kg "
            "(NEVER silently enlarged to the heavy class).",
        )
    if payload_volume_l is not None and payload_volume_l > profile.payload_volume_limit_l:
        return FloorAgvPayloadEligibility(
            profile.vehicle_class, stream, payload_mass_kg, payload_volume_l, False, "INELIGIBLE_VOLUME",
            f"payload {payload_volume_l} L exceeds {profile.vehicle_class} limit {profile.payload_volume_limit_l} L.",
        )
    return FloorAgvPayloadEligibility(
        profile.vehicle_class, stream, payload_mass_kg, payload_volume_l, True, "ELIGIBLE",
        f"{stream} within {profile.vehicle_class} mass/volume envelope.",
    )


# ===========================================================================
# 5. Route / mission-cycle physics (Sec 41-42).
# ===========================================================================

@dataclass(frozen=True)
class FloorAgvMissionTiming:
    horizontal_minutes: float
    vertical_elevator_minutes: float
    door_delay_minutes: float
    load_minutes: float
    unload_minutes: float
    return_minutes: float
    total_minutes: float
    one_way_distance_m: float
    round_trip_distance_km: float
    route_status: Literal["ROUTE_CALIBRATED", "ROUTE_NOT_CALIBRATED"]


def compute_floor_agv_mission_timing(
    *, profile: FloorAgvProfile, horizontal_distance_m: float | None = None,
    vertical_transitions: int = 0, doors_per_mission: int = 0,
    controlled_scenario_horizontal_minutes: float = 5.0,
) -> FloorAgvMissionTiming:
    """T = load + horizontal + vertical(elevator) + door + unload + return.
    Uses real distance when supplied (ROUTE_CALIBRATED); else an explicit
    controlled duration (ROUTE_NOT_CALIBRATED) -- never fabricated geometry.
    Robots never teleport between floors: each vertical transition incurs
    elevator wait + ride (Sec 41-42)."""
    if horizontal_distance_m is not None:
        horizontal_minutes = horizontal_distance_m / profile.speed_m_per_s / 60.0
        one_way_m = horizontal_distance_m
        route_status: Literal["ROUTE_CALIBRATED", "ROUTE_NOT_CALIBRATED"] = "ROUTE_CALIBRATED"
    else:
        horizontal_minutes = controlled_scenario_horizontal_minutes
        one_way_m = profile.speed_m_per_s * controlled_scenario_horizontal_minutes * 60.0
        route_status = "ROUTE_NOT_CALIBRATED"
    elevator = vertical_transitions * (_p(FLOOR_AGV_ELEVATOR_WAIT_MINUTES) + _p(FLOOR_AGV_ELEVATOR_RIDE_MINUTES))
    door = doors_per_mission * _p(FLOOR_AGV_DOOR_DELAY_MINUTES)
    return_minutes = horizontal_minutes + elevator + door  # symmetric reposition (empty return over same route)
    total = profile.load_minutes + horizontal_minutes + elevator + door + profile.unload_minutes + return_minutes
    round_trip_km = 2.0 * one_way_m / 1000.0
    return FloorAgvMissionTiming(
        horizontal_minutes=horizontal_minutes, vertical_elevator_minutes=elevator, door_delay_minutes=door,
        load_minutes=profile.load_minutes, unload_minutes=profile.unload_minutes, return_minutes=return_minutes,
        total_minutes=total, one_way_distance_m=one_way_m, round_trip_distance_km=round_trip_km, route_status=route_status,
    )


# ===========================================================================
# 6. Battery / charging + energy (Sec 44-45). Charging electricity and traction
#    electricity are NOT double-counted: annual electricity = mission traction
#    energy / charging_efficiency (charging losses folded in once).
# ===========================================================================

@dataclass(frozen=True)
class FloorAgvEnergyResult:
    energy_per_mission_kwh: float
    missions_per_day: int
    daily_traction_kwh: float
    annual_traction_kwh: float
    annual_idle_kwh: float
    charging_loss_kwh_per_year: float
    total_known_annual_kwh: float
    annual_electricity_usd: float
    network_standby_status: str
    energy_boundary: str


def compute_floor_agv_energy(
    *, profile: FloorAgvProfile, round_trip_distance_km: float, missions_per_day: int,
    operating_days_per_year: int, idle_hours_per_day: float = 0.0,
) -> FloorAgvEnergyResult:
    """Traction energy from actual round-trip distance × energy/km (never a flat
    lump). Charging losses folded in ONCE via charging_efficiency (charging kWh
    and traction kWh are the SAME energy at different points -- never summed
    twice, Sec 45). Facility-network standby stays NOT_CALIBRATED (never $0)."""
    energy_per_mission = round_trip_distance_km * profile.energy_kwh_per_km
    daily_traction = energy_per_mission * missions_per_day
    annual_traction = daily_traction * operating_days_per_year
    annual_idle = profile.idle_power_kw * idle_hours_per_day * operating_days_per_year
    # Wall-plug charging energy exceeds delivered traction energy by 1/efficiency;
    # the incremental charging loss is counted once, on top of delivered energy.
    charging_loss = (annual_traction + annual_idle) * (1.0 / profile.charging_efficiency - 1.0)
    total_known = annual_traction + annual_idle + charging_loss
    tariff = _p(FLOOR_AGV_ELECTRICITY_TARIFF_USD_PER_KWH)
    return FloorAgvEnergyResult(
        energy_per_mission_kwh=energy_per_mission, missions_per_day=missions_per_day,
        daily_traction_kwh=daily_traction, annual_traction_kwh=annual_traction, annual_idle_kwh=annual_idle,
        charging_loss_kwh_per_year=charging_loss, total_known_annual_kwh=total_known,
        annual_electricity_usd=total_known * tariff,
        network_standby_status=FLOOR_AGV_NETWORK_STANDBY_KWH_PER_DAY_STATUS,
        energy_boundary="motion(traction) + onboard idle + charging losses; facility charging-network standby NOT_CALIBRATED",
    )


# ===========================================================================
# 7. Fleet sizing (Sec 43): workload-derived, charging + elevator + availability
#    included; NEVER a published-hospital fleet count.
# ===========================================================================

@dataclass(frozen=True)
class FloorAgvFleetResult:
    missions_per_day: int
    mission_cycle_minutes: float
    charging_minutes_per_mission: float
    effective_cycle_minutes: float
    available_minutes_per_vehicle_per_day: float
    required_fleet: int
    fleet_basis: str


def compute_floor_agv_fleet(
    *, profile: FloorAgvProfile, missions_per_day: int, mission_cycle_minutes: float,
    energy_per_mission_kwh: float, operating_hours_per_day: float = 20.0, reserve_fraction: float = 0.0,
) -> FloorAgvFleetResult:
    """REQUIRED_FLEET = ceil( missions/day × (cycle + per-mission charging) /
    (available minutes/vehicle/day) ) × (1 + reserve). Charging time per mission
    = (energy/mission / usable-battery-throughput) recharge minutes, so a
    fleet is never sized ignoring charging duty (Sec 43-44). Availability scales
    the usable minutes. Never a published fleet count."""
    if missions_per_day <= 0:
        return FloorAgvFleetResult(0, mission_cycle_minutes, 0.0, mission_cycle_minutes, 0.0, 0, "NO_WORKLOAD")
    # Recharge time to replenish this mission's energy at charging power.
    charging_minutes_per_mission = (energy_per_mission_kwh / profile.charging_power_kw) * 60.0
    effective_cycle = mission_cycle_minutes + charging_minutes_per_mission
    available_minutes = operating_hours_per_day * 60.0 * (profile.availability_pct / 100.0)
    import math
    base_fleet = math.ceil(missions_per_day * effective_cycle / available_minutes) if available_minutes > 0 else 0
    required = max(1, math.ceil(base_fleet * (1.0 + reserve_fraction)))
    return FloorAgvFleetResult(
        missions_per_day=missions_per_day, mission_cycle_minutes=mission_cycle_minutes,
        charging_minutes_per_mission=charging_minutes_per_mission, effective_cycle_minutes=effective_cycle,
        available_minutes_per_vehicle_per_day=available_minutes, required_fleet=required,
        fleet_basis="workload×(cycle+charging)/available-minutes × (1+reserve); availability-scaled; NOT a published count",
    )


# ===========================================================================
# 8. CapEx (Sec 47): per-vehicle costs × fleet; one-time integration NOT
#    multiplied by vehicle count. Unknown lines listed separately, never $0 in
#    the known subtotal.
# ===========================================================================

@dataclass(frozen=True)
class FloorAgvCapexResult:
    vehicle_class: FloorAgvClass
    fleet_size: int
    vehicles_capex: float
    charging_stations_capex: float
    fleet_manager_capex: float
    elevator_integration_capex: float
    door_integration_capex: float
    install_commissioning_capex: float
    known_capex_subtotal: float
    unknown_capex_components: tuple[str, ...]
    ledger: tuple[tuple[str, float, float, str], ...]  # (component, quantity, unit_cost, provenance)


def compute_floor_agv_capex(
    *, profile: FloorAgvProfile, fleet_size: int, charging_station_count: int,
    elevators_integrated: int = 0, doors_integrated: int = 0,
) -> FloorAgvCapexResult:
    """One-time fleet-manager / install-commissioning are charged ONCE (never ×
    vehicle count, Sec 47). Charging stations, elevator, door integration are
    quantity-driven. Battery replacement is OPEX (Sec 48), not initial CapEx."""
    veh_unit = profile.vehicle_capex_usd
    vehicles = fleet_size * veh_unit
    stn_unit = _p(FLOOR_AGV_CHARGING_STATION_CAPEX_USD)
    stations = charging_station_count * stn_unit
    fm = _p(FLOOR_AGV_FLEET_MANAGER_CAPEX_USD)  # once
    elev_unit = _p(FLOOR_AGV_ELEVATOR_INTEGRATION_CAPEX_USD)
    elev = elevators_integrated * elev_unit
    door_unit = _p(FLOOR_AGV_DOOR_INTEGRATION_CAPEX_USD)
    doors = doors_integrated * door_unit
    install = _p(FLOOR_AGV_INSTALL_COMMISSIONING_USD)  # once
    subtotal = vehicles + stations + fm + elev + doors + install
    ledger = (
        ("Vehicles", float(fleet_size), veh_unit, "CONTROLLED_ENGINEERING_ASSUMPTION"),
        ("Charging stations", float(charging_station_count), stn_unit, "CONTROLLED_ENGINEERING_ASSUMPTION"),
        ("Fleet-management hardware/software (once)", 1.0, fm, "CONTROLLED_ENGINEERING_ASSUMPTION"),
        ("Elevator integration", float(elevators_integrated), elev_unit, "CONTROLLED_ENGINEERING_ASSUMPTION"),
        ("Door/access integration", float(doors_integrated), door_unit, "CONTROLLED_ENGINEERING_ASSUMPTION"),
        ("Install/commissioning/training (once)", 1.0, install, "CONTROLLED_ENGINEERING_ASSUMPTION"),
    )
    return FloorAgvCapexResult(
        vehicle_class=profile.vehicle_class, fleet_size=fleet_size, vehicles_capex=vehicles,
        charging_stations_capex=stations, fleet_manager_capex=fm, elevator_integration_capex=elev,
        door_integration_capex=doors, install_commissioning_capex=install, known_capex_subtotal=subtotal,
        unknown_capex_components=("Facility network/server upgrades allocation (NOT_CALIBRATED)",),
        ledger=ledger,
    )


# ===========================================================================
# 9. OPEX (Sec 48): electricity + vehicle maintenance + amortized battery
#    replacement + charging-station maintenance + fleet software + supervision.
#    Battery replacement amortized over life; NEVER $0 when unknown.
# ===========================================================================

@dataclass(frozen=True)
class FloorAgvOpexResult:
    vehicle_class: FloorAgvClass
    fleet_size: int
    electricity_usd: float
    vehicle_maintenance_usd: float
    battery_replacement_amortized_usd: float
    charging_station_maintenance_usd: float
    fleet_software_usd: float
    supervision_usd: float
    known_annual_opex_subtotal: float
    unknown_opex_components: tuple[str, ...]
    total_opex_status: str
    ledger: tuple[tuple[str, float, str], ...]  # (component, annual_usd, provenance)


def compute_floor_agv_opex(
    *, profile: FloorAgvProfile, fleet_size: int, charging_station_count: int,
    annual_electricity_usd: float, loaded_annual_cost_per_fte: float,
) -> FloorAgvOpexResult:
    """KNOWN subtotal = electricity + fleet×maint + amortized battery replacement
    + stations×station-maint + fleet software (once) + supervision FTE×loaded
    cost. Unknown service-contract/network standby stay OUT of the subtotal,
    listed separately (never $0-filled, Sec 48/63)."""
    veh_maint = fleet_size * profile.vehicle_maint_usd_per_year
    battery_amortized = fleet_size * (profile.battery_replacement_usd / profile.battery_life_years)
    stn_maint = charging_station_count * _p(FLOOR_AGV_CHARGING_STATION_MAINT_USD_PER_YEAR)
    software = _p(FLOOR_AGV_FLEET_SOFTWARE_USD_PER_YEAR)  # once, not per vehicle
    supervision = _p(FLOOR_AGV_SUPERVISION_FTE) * loaded_annual_cost_per_fte
    subtotal = annual_electricity_usd + veh_maint + battery_amortized + stn_maint + software + supervision
    ledger = (
        ("Electricity (motion+idle+charging losses)", annual_electricity_usd, "CONTROLLED_ENGINEERING_ASSUMPTION"),
        ("Vehicle maintenance", veh_maint, "CONTROLLED_ENGINEERING_ASSUMPTION"),
        ("Battery replacement (amortized)", battery_amortized, "CONTROLLED_ENGINEERING_ASSUMPTION"),
        ("Charging-station maintenance", stn_maint, "CONTROLLED_ENGINEERING_ASSUMPTION"),
        ("Fleet-management software/support (once)", software, "CONTROLLED_ENGINEERING_ASSUMPTION"),
        ("Residual human supervision", supervision, "CONTROLLED_ENGINEERING_ASSUMPTION"),
    )
    return FloorAgvOpexResult(
        vehicle_class=profile.vehicle_class, fleet_size=fleet_size, electricity_usd=annual_electricity_usd,
        vehicle_maintenance_usd=veh_maint, battery_replacement_amortized_usd=battery_amortized,
        charging_station_maintenance_usd=stn_maint, fleet_software_usd=software, supervision_usd=supervision,
        known_annual_opex_subtotal=subtotal,
        unknown_opex_components=(
            "Vendor service contract (NOT_CALIBRATED)",
            "Facility charging-network standby electricity (NOT_CALIBRATED)",
        ),
        total_opex_status="KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED",
        ledger=ledger,
    )


# ===========================================================================
# 10. Controlled-benchmark register export (Sec 66).
# ===========================================================================

_ALL_BENCHMARKS: tuple[EditableParameter, ...] = (
    LIGHT_VEHICLE_LENGTH_M, LIGHT_VEHICLE_WIDTH_M, LIGHT_VEHICLE_HEIGHT_M, LIGHT_PAYLOAD_MASS_LIMIT_KG,
    LIGHT_PAYLOAD_VOLUME_LIMIT_L, LIGHT_SPEED_M_PER_S, LIGHT_LOAD_MINUTES, LIGHT_UNLOAD_MINUTES,
    LIGHT_BATTERY_CAPACITY_KWH, LIGHT_USABLE_BATTERY_FRACTION, LIGHT_ENERGY_KWH_PER_KM, LIGHT_IDLE_POWER_KW,
    LIGHT_CHARGING_POWER_KW, LIGHT_CHARGING_EFFICIENCY, LIGHT_VEHICLE_CAPEX_USD, LIGHT_VEHICLE_MAINT_USD_PER_YEAR,
    LIGHT_BATTERY_REPLACEMENT_USD, LIGHT_BATTERY_LIFE_YEARS,
    HEAVY_VEHICLE_LENGTH_M, HEAVY_VEHICLE_WIDTH_M, HEAVY_VEHICLE_HEIGHT_M, HEAVY_PAYLOAD_MASS_LIMIT_KG,
    HEAVY_PAYLOAD_VOLUME_LIMIT_L, HEAVY_SPEED_M_PER_S, HEAVY_LOAD_MINUTES, HEAVY_UNLOAD_MINUTES,
    HEAVY_BATTERY_CAPACITY_KWH, HEAVY_USABLE_BATTERY_FRACTION, HEAVY_ENERGY_KWH_PER_KM, HEAVY_IDLE_POWER_KW,
    HEAVY_CHARGING_POWER_KW, HEAVY_CHARGING_EFFICIENCY, HEAVY_VEHICLE_CAPEX_USD, HEAVY_VEHICLE_MAINT_USD_PER_YEAR,
    HEAVY_BATTERY_REPLACEMENT_USD, HEAVY_BATTERY_LIFE_YEARS,
    FLOOR_AGV_ELECTRICITY_TARIFF_USD_PER_KWH, FLOOR_AGV_CHARGING_STATION_CAPEX_USD,
    FLOOR_AGV_CHARGING_STATION_MAINT_USD_PER_YEAR, FLOOR_AGV_FLEET_MANAGER_CAPEX_USD,
    FLOOR_AGV_FLEET_SOFTWARE_USD_PER_YEAR, FLOOR_AGV_ELEVATOR_INTEGRATION_CAPEX_USD,
    FLOOR_AGV_DOOR_INTEGRATION_CAPEX_USD, FLOOR_AGV_INSTALL_COMMISSIONING_USD, FLOOR_AGV_SUPERVISION_FTE,
    FLOOR_AGV_ELEVATOR_WAIT_MINUTES, FLOOR_AGV_ELEVATOR_RIDE_MINUTES, FLOOR_AGV_DOOR_DELAY_MINUTES,
    FLOOR_AGV_AVAILABILITY_PCT,
)


def floor_agv_controlled_benchmark_register() -> tuple[Mapping[str, object], ...]:
    """Every controlled benchmark this module owns, normalized for the
    Controlled Benchmark Register (Sec 66)."""
    rows: list[Mapping[str, object]] = []
    for p in _ALL_BENCHMARKS:
        rows.append({
            "parameter": p.parameter_id, "transport_mode": FLOOR_AGV_TECHNOLOGY_CLASS,
            "value": p.active_value, "unit": p.units, "provenance": p.source_type,
            "rationale": p.source, "editable": p.user_editable, "calibration_status": p.status,
            "replacement_data_needed": "vendor/facility-confirmed value",
        })
    return tuple(rows)

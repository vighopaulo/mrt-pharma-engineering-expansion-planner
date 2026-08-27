"""Manual / Automated Conventional Transport Technology Authority.

GOVERNANCE (sections 2-4, 27-28): implements REAL operational/economic
authority for MANUAL_CONVENTIONAL and AUTOMATED_CONVENTIONAL general
logistics. HYBRID_MRT/MRT_DOMINANT semantics (established in
`general_oncology_logistics.py`) are UNCHANGED. Nuclear transport remains the
protected existing Conventional nuclear authority -- this module never
assigns a radiopharmaceutical mission to AGV/PTS (section 28).

Reuses -- never duplicates -- the `ProvenancedField`-style evidence pattern
already established in `cyclotron_catalog.py`/`generator_catalog.py`/
`scanner_catalog.py`, and `general_oncology_logistics.py`'s
`LogisticsStream`/`TransportLoad`/`TransportMission`/`FacilityRoleLocation`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Literal, Mapping

from cyclotron_catalog import CalibrationStatus, EvidenceType
from general_oncology_logistics import LogisticsStream, TransportLoad, TransportMission

TechnologyType = Literal["MANUAL_PORTER", "PORTER_CART", "AGV_AMR", "PNEUMATIC_TUBE"]
AssetStatus = Literal["EXISTING", "PROPOSED"]
OperationalState = Literal["AVAILABLE", "UNAVAILABLE", "MAINTENANCE"]
TechnologyReadiness = Literal["IMPLEMENTATION_PENDING", "PERFORMANCE_NOT_CALIBRATED", "ECONOMICS_NOT_CALIBRATED", "CALIBRATED"]


@dataclass(frozen=True)
class EvidenceValue:
    """Mirrors `cyclotron_catalog.ProvenancedField`/`generator_catalog.GeneratorEconomicRecord`
    -- every technology parameter carries explicit provenance (section 29)."""

    value: float | Literal["NOT_CALIBRATED"]
    unit: str
    cost_year: str | None
    source: str
    evidence_type: EvidenceType
    calibration_status: CalibrationStatus
    confidence: Literal["high", "medium", "low", "unknown"]


# ---------------------------------------------------------------------------
# Technology compatibility (sections 6, 19, 25, 28) -- explicit, never assumed
# ---------------------------------------------------------------------------

TECHNOLOGY_STREAM_COMPATIBILITY: Mapping[TechnologyType, frozenset[LogisticsStream]] = {
    "MANUAL_PORTER": frozenset({"PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY"}),
    "PORTER_CART": frozenset({"PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY"}),
    "AGV_AMR": frozenset({"CLEAN_LINEN", "STERILE_CLEAN_SUPPLY", "PHARMACY_INFUSION"}),
    "PNEUMATIC_TUBE": frozenset({"SPECIMEN_BLOOD", "PHARMACY_INFUSION"}),
    # Section 25/8: pneumatic tube is NOT a bulk-material system -- CLEAN_LINEN and
    # large sterile-supply totes are explicitly excluded, never silently permitted.
}


def is_technology_compatible(technology: TechnologyType, stream: LogisticsStream) -> bool:
    return stream in TECHNOLOGY_STREAM_COMPATIBILITY[technology]


# ---------------------------------------------------------------------------
# Manual porter authority (sections 7-13)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PorterOperatingPolicy:
    """Section 7/9-10: derives mission time from labor/resource requirements
    -- never a single arbitrary 'manual trip cost'."""

    unloaded_walk_speed_m_per_s: float = 1.4
    loaded_hand_carry_speed_m_per_s: float = 1.1
    loaded_cart_speed_m_per_s: float = 0.9
    dispatch_minutes: float = 2.0
    load_minutes: float = 3.0
    unload_minutes: float = 3.0
    wait_minutes: float = 1.0
    elevator_wait_minutes: float = 2.0
    shift_hours: float = 8.0
    availability_pct: float = 85.0
    base_wage_per_hour: float = 17.0
    """CONTROLLED_ENGINEERING_ASSUMPTION (section 9) -- general hospital
    porter/transporter occupational wage, not independently re-verified via
    live fetch this session (consistent with this session's prior oncology
    logistics research phase disclosure)."""
    loaded_employer_cost_multiplier: float = 1.3
    """Explicit, labeled payroll-burden multiplier (section 13) -- never an
    unlabeled invented figure."""
    provenance: str = "CONTROLLED_ENGINEERING_ASSUMPTION"


@dataclass(frozen=True)
class ManualMissionTiming:
    """Section 10: T_mission = dispatch + load + horizontal + vertical + wait
    + unload + return/reposition. `route_calibrated=False` -> horizontal/
    vertical times use a controlled scenario duration only, explicitly
    flagged `ROUTE_NOT_CALIBRATED` -- never a fabricated precise distance."""

    dispatch_minutes: float
    load_minutes: float
    horizontal_minutes: float
    vertical_minutes: float
    wait_minutes: float
    unload_minutes: float
    return_minutes: float
    total_minutes: float
    route_status: Literal["ROUTE_CALIBRATED", "ROUTE_NOT_CALIBRATED"]


def compute_manual_mission_timing(
    *, policy: PorterOperatingPolicy, technology: Literal["MANUAL_PORTER", "PORTER_CART"],
    horizontal_distance_m: float | None = None, vertical_transitions: int = 0,
    controlled_scenario_horizontal_minutes: float = 4.0,
) -> ManualMissionTiming:
    """Section 10: uses real distance when calibrated; otherwise an explicit
    controlled scenario duration (never an invented precise geometry)."""
    speed = policy.loaded_cart_speed_m_per_s if technology == "PORTER_CART" else policy.loaded_hand_carry_speed_m_per_s
    if horizontal_distance_m is not None:
        horizontal_minutes = horizontal_distance_m / speed / 60.0
        route_status: Literal["ROUTE_CALIBRATED", "ROUTE_NOT_CALIBRATED"] = "ROUTE_CALIBRATED"
    else:
        horizontal_minutes = controlled_scenario_horizontal_minutes
        route_status = "ROUTE_NOT_CALIBRATED"
    vertical_minutes = vertical_transitions * policy.elevator_wait_minutes
    return_minutes = horizontal_minutes  # section 10: symmetric reposition, same route
    total = (
        policy.dispatch_minutes + policy.load_minutes + horizontal_minutes + vertical_minutes
        + policy.wait_minutes + policy.unload_minutes + return_minutes
    )
    return ManualMissionTiming(
        dispatch_minutes=policy.dispatch_minutes, load_minutes=policy.load_minutes, horizontal_minutes=horizontal_minutes,
        vertical_minutes=vertical_minutes, wait_minutes=policy.wait_minutes, unload_minutes=policy.unload_minutes,
        return_minutes=return_minutes, total_minutes=total, route_status=route_status,
    )


@dataclass(frozen=True)
class PorterResourceRequirement:
    """Section 11-12: FTE derived from workload, never `missions/day = porters`."""

    total_missions: int
    total_labor_hours: float
    peak_concurrent_porters: int
    required_fte: float
    annual_labor_opex: float


def compute_porter_resource_requirement(
    *, missions: tuple[TransportMission, ...], mission_minutes: float, policy: PorterOperatingPolicy,
    operating_days_per_year: int,
) -> PorterResourceRequirement:
    """Section 11-13: peak-concurrency-derived FTE, base + loaded labor cost
    computed separately (never merged with cart/equipment cost, section 8)."""
    if not missions:
        return PorterResourceRequirement(total_missions=0, total_labor_hours=0.0, peak_concurrent_porters=0, required_fte=0.0, annual_labor_opex=0.0)
    total_labor_hours = len(missions) * mission_minutes / 60.0

    # Peak concurrency: sort mission windows, sweep-line count of overlaps (never a fixed constant).
    events: list[tuple[float, int]] = []
    for m in missions:
        start = (m.departure_datetime - missions[0].departure_datetime).total_seconds() / 60.0
        end = start + mission_minutes
        events.append((start, 1))
        events.append((end, -1))
    events.sort(key=lambda e: (e[0], -e[1]))
    current = 0
    peak = 0
    for _t, delta in events:
        current += delta
        peak = max(peak, current)

    productive_hours_per_shift = policy.shift_hours * (policy.availability_pct / 100.0)
    required_fte = max(peak, math.ceil(total_labor_hours / (productive_hours_per_shift * operating_days_per_year))) if productive_hours_per_shift > 0 else 0.0
    loaded_annual_cost_per_fte = policy.base_wage_per_hour * policy.loaded_employer_cost_multiplier * policy.shift_hours * operating_days_per_year
    annual_labor_opex = required_fte * loaded_annual_cost_per_fte
    return PorterResourceRequirement(
        total_missions=len(missions), total_labor_hours=total_labor_hours, peak_concurrent_porters=peak,
        required_fte=required_fte, annual_labor_opex=annual_labor_opex,
    )


# ---------------------------------------------------------------------------
# Cart authority (sections 8, 14-17) -- equipment asset, distinct from porter labor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CartClass:
    """Section 14-15: a controlled generic cart class -- capacity
    INDEPENDENTLY configurable, never reusing the MRT 20kg container size."""

    cart_class_id: str
    compatible_streams: frozenset[LogisticsStream]
    payload_capacity: float
    unit: str
    purchase_capex: float
    useful_life_years: float
    annual_maintenance_opex: float
    asset_status: AssetStatus = "EXISTING"
    operational_state: OperationalState = "AVAILABLE"
    provenance: str = "CONTROLLED_ENGINEERING_ASSUMPTION"


DEFAULT_LINEN_CART = CartClass(
    cart_class_id="LINEN_CART_STANDARD", compatible_streams=frozenset({"CLEAN_LINEN"}), payload_capacity=80.0,
    unit="kg", purchase_capex=800.0, useful_life_years=7.0, annual_maintenance_opex=60.0,
)
DEFAULT_GENERAL_CART = CartClass(
    cart_class_id="GENERAL_TOTE_CART", compatible_streams=frozenset({"PHARMACY_INFUSION", "SPECIMEN_BLOOD", "STERILE_CLEAN_SUPPLY"}),
    payload_capacity=20.0, unit="tote_equivalent", purchase_capex=500.0, useful_life_years=7.0, annual_maintenance_opex=40.0,
)


def cart_new_study_capex(cart: CartClass, *, study_scope: Literal["OPERATIONAL_ONLY", "CAPITAL_PLANNING"]) -> float:
    """Section 16/49: existing carts contribute zero new study CapEx in
    OPERATIONAL_ONLY; only PROPOSED carts contribute in CAPITAL_PLANNING."""
    if study_scope == "OPERATIONAL_ONLY":
        return 0.0
    return cart.purchase_capex if cart.asset_status == "PROPOSED" else 0.0


# ---------------------------------------------------------------------------
# AGV/AMR authority (sections 18-23)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgvModelClass:
    model_class_id: str
    compatible_streams: frozenset[LogisticsStream]
    payload_capacity_kg: float
    speed_m_per_s: float
    availability_pct: float
    vehicle_capex: float
    system_integration_capex: float
    """Section 22: vehicle cost vs system/integration cost kept separate."""
    annual_maintenance_opex: float
    annual_energy_opex: float
    residual_supervision_fte: float
    useful_life_years: float
    asset_status: AssetStatus = "EXISTING"
    operational_state: OperationalState = "AVAILABLE"
    provenance: str = "CONTROLLED_ENGINEERING_ASSUMPTION"
    technology_class: str = "RGHT"
    """Transport Spatial Authority Build 1 (section 4/22): canonical
    semantic technology class -- Rail-Guided Hospital Transport. This
    legacy `AgvModelClass`/`"AGV_AMR"` identifier's economics are, by
    evidence, materially closer to RGHT than to a true free-roaming floor
    AGV/AMR (see `transport_technology_authority.py`)."""
    commercial_calibration_status: str = "NOT_CALIBRATED_TO_CURRENT_VENDOR_QUOTE"
    vendor_comparator_basis: str = "TELELIFT_CLASS_REFERENCE"
    """Documentation/provenance ONLY -- no Telelift-specific engineering
    assumption (dimensions/motors/controls/switch logic) is encoded here or
    anywhere else in this repository."""


DEFAULT_AGV_MODEL = AgvModelClass(
    model_class_id="GENERIC_HOSPITAL_AGV", compatible_streams=frozenset({"CLEAN_LINEN", "STERILE_CLEAN_SUPPLY", "PHARMACY_INFUSION"}),
    payload_capacity_kg=150.0, speed_m_per_s=0.8, availability_pct=90.0, vehicle_capex=100_000.0,
    system_integration_capex=50_000.0, annual_maintenance_opex=4_000.0, annual_energy_opex=1_500.0,
    residual_supervision_fte=0.1, useful_life_years=10.0,
)
"""Section 30: vehicle_capex reuses this session's prior oncology-logistics-research
~$100k historical US hospital AGV vehicle evidence point; system_integration_capex,
maintenance, and energy are CONTROLLED_ENGINEERING_ASSUMPTION (no per-vendor
system-cost evidence located)."""


def _compute_mission_peak_concurrency(missions: tuple[TransportMission, ...], mission_minutes: float) -> int:
    """Build 2R permanent operational-feasibility authority (Section 17):
    sweep-line peak overlap over [departure, departure+mission_minutes]
    windows -- the SAME technique already used by
    `compute_porter_resource_requirement`'s `peak_concurrent_porters` and
    `shared_mrt_multistream_authority.compute_physical_carrier_peak_concurrency`.
    Reused here for AGV/PTS so fleet/station sizing is never average-workload-
    only (which can understate the TRUE simultaneous-vehicle requirement when
    missions cluster in time, even if their total daily minutes are modest)."""
    if not missions:
        return 0
    events: list[tuple[float, int]] = []
    base = missions[0].departure_datetime
    for m in missions:
        start = (m.departure_datetime - base).total_seconds() / 60.0
        events.append((start, 1))
        events.append((start + mission_minutes, -1))
    events.sort(key=lambda e: (e[0], -e[1]))
    current = peak = 0
    for _t, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


def agv_required_fleet_size(
    *, missions: tuple[TransportMission, ...], mission_minutes: float, model: AgvModelClass,
    operating_hours_per_day: float, operating_days_per_year: int,
) -> int:
    """Section 17/21 (Build 2R permanent operational-feasibility authority):
    requirement = max(peak physical concurrency, average-workload-derived
    count) -- never average-workload-only (previously this function computed
    only the average-daily-minutes/vehicle-capacity ratio, despite its
    docstring claiming peak concurrency; genuinely fixed here to
    ALSO sweep-line the actual mission windows, mirroring
    `compute_porter_resource_requirement`'s `peak_concurrent_porters`)."""
    if not missions:
        return 0
    total_minutes = len(missions) * mission_minutes
    daily_capacity_minutes_per_vehicle = operating_hours_per_day * 60.0 * (model.availability_pct / 100.0)
    minutes_per_day = total_minutes / operating_days_per_year if operating_days_per_year > 0 else total_minutes
    average_derived = math.ceil(minutes_per_day / daily_capacity_minutes_per_vehicle) if daily_capacity_minutes_per_vehicle > 0 else 0
    peak_concurrency = _compute_mission_peak_concurrency(missions, mission_minutes)
    return max(1, average_derived, peak_concurrency)


def pts_required_station_count(
    *, missions: tuple[TransportMission, ...], mission_minutes: float, network: PneumaticTubeNetwork,
    operating_hours_per_day: float, operating_days_per_year: int,
) -> int:
    """Repository-first closure (audit finding, item 'PTS infrastructure
    sizing'): station count derived from missions/duration/availability --
    mirrors `agv_required_fleet_size` -- never a hard-coded default station
    count (`DEFAULT_PTS_NETWORK.station_count=6`) regardless of workload.

    Build 2R permanent operational-feasibility authority (Section 17): now
    ALSO takes the peak physical concurrency into account (same sweep-line
    technique), never average-workload-only."""
    if not missions:
        return 0
    total_minutes = len(missions) * mission_minutes
    # PneumaticTubeNetwork has no per-station availability_pct field (single
    # fixed network asset) -- use full operating-hours capacity per station.
    daily_capacity_minutes_per_station = operating_hours_per_day * 60.0
    minutes_per_day = total_minutes / operating_days_per_year if operating_days_per_year > 0 else total_minutes
    average_derived = math.ceil(minutes_per_day / daily_capacity_minutes_per_station) if daily_capacity_minutes_per_station > 0 else 0
    peak_concurrency = _compute_mission_peak_concurrency(missions, mission_minutes)
    return max(1, average_derived, peak_concurrency)


def agv_new_study_capex(model: AgvModelClass, *, fleet_size: int, study_scope: Literal["OPERATIONAL_ONLY", "CAPITAL_PLANNING"]) -> float:
    """Section 16/22/49: existing AGVs contribute zero; only proposed fleet
    additions contribute CapEx in CAPITAL_PLANNING."""
    if study_scope == "OPERATIONAL_ONLY" or model.asset_status != "PROPOSED":
        return 0.0
    return fleet_size * (model.vehicle_capex + model.system_integration_capex)


def agv_annual_opex(model: AgvModelClass, *, fleet_size: int, loaded_annual_cost_per_fte: float) -> float:
    return fleet_size * (model.annual_maintenance_opex + model.annual_energy_opex) + model.residual_supervision_fte * loaded_annual_cost_per_fte


def convert_load_to_agv_missions(*, load: TransportLoad, model: AgvModelClass, travel_minutes: float = 4.0) -> tuple[TransportMission, ...]:
    """Section 20: converts using AGV payload capacity, never Manual cart or
    MRT container capacity unless they genuinely happen to match."""
    if not is_technology_compatible("AGV_AMR", load.stream):
        raise ValueError(f"AGV_AMR is not compatible with stream {load.stream} (section 6)")
    trips = max(1, math.ceil(load.quantity / model.payload_capacity_kg))
    missions = []
    for i in range(trips):
        departure = load.release_datetime
        arrival = departure + timedelta(minutes=travel_minutes)
        missions.append(TransportMission(
            mission_id=f"MISSION-AGV-{load.load_id}-{i+1:02d}", load_id=load.load_id, transport_mode="AGV_AMR",
            origin=load.origin, destination=load.destination, departure_datetime=departure, arrival_datetime=arrival,
            patient_ids=load.patient_ids, duration_minutes=travel_minutes, resource_id=model.model_class_id,
        ))
    return tuple(missions)


# ---------------------------------------------------------------------------
# Pneumatic-tube authority (sections 24-26, 53)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PneumaticTubeNetwork:
    """Section 24/26: a distinct fixed-network technology -- CapEx depends on
    station count/network length, never one universal flat price."""

    network_id: str
    compatible_streams: frozenset[LogisticsStream]
    station_count: int
    network_length_m: float | None
    capsule_payload_kg: float
    speed_m_per_s: float
    station_capex_per_unit: float
    network_capex_per_m: float | None
    annual_maintenance_opex: float
    annual_energy_opex: float
    residual_labor_fte: float
    dispatch_minutes: float = 1.0
    station_handling_minutes: float = 1.5
    asset_status: AssetStatus = "EXISTING"
    operational_state: OperationalState = "AVAILABLE"
    provenance: str = "CONTROLLED_ENGINEERING_ASSUMPTION"


DEFAULT_PTS_NETWORK = PneumaticTubeNetwork(
    network_id="GENERIC_HOSPITAL_PTS", compatible_streams=frozenset({"SPECIMEN_BLOOD", "PHARMACY_INFUSION"}),
    station_count=6, network_length_m=300.0, capsule_payload_kg=2.0, speed_m_per_s=6.0,
    station_capex_per_unit=45_000.0, network_capex_per_m=250.0, annual_maintenance_opex=8_000.0,
    annual_energy_opex=1_000.0, residual_labor_fte=0.2,
)


def pts_new_study_capex(network: PneumaticTubeNetwork, *, study_scope: Literal["OPERATIONAL_ONLY", "CAPITAL_PLANNING"]) -> float:
    if study_scope == "OPERATIONAL_ONLY" or network.asset_status != "PROPOSED":
        return 0.0
    station_cost = network.station_count * network.station_capex_per_unit
    network_cost = (network.network_length_m * network.network_capex_per_m) if (network.network_length_m and network.network_capex_per_m) else 0.0
    return station_cost + network_cost


def pts_annual_opex(network: PneumaticTubeNetwork, *, loaded_annual_cost_per_fte: float) -> float:
    """Section 22 parity for pneumatic tube: maintenance + energy + residual
    station-handling labor (never assumed fully unattended)."""
    return network.annual_maintenance_opex + network.annual_energy_opex + network.residual_labor_fte * loaded_annual_cost_per_fte


def convert_load_to_pts_missions(*, load: TransportLoad, network: PneumaticTubeNetwork) -> tuple[TransportMission, ...]:
    """Section 25: rejects bulk streams explicitly -- CLEAN_LINEN/large
    sterile totes must never be routed through pneumatic tube."""
    if not is_technology_compatible("PNEUMATIC_TUBE", load.stream):
        raise ValueError(f"PNEUMATIC_TUBE is not compatible with stream {load.stream} (bulk-material exclusion, section 25)")
    trips = max(1, math.ceil(load.quantity / network.capsule_payload_kg))
    travel_minutes = network.dispatch_minutes + network.station_handling_minutes
    missions = []
    for i in range(trips):
        departure = load.release_datetime
        arrival = departure + timedelta(minutes=travel_minutes)
        missions.append(TransportMission(
            mission_id=f"MISSION-PTS-{load.load_id}-{i+1:02d}", load_id=load.load_id, transport_mode="PNEUMATIC_TUBE",
            origin=load.origin, destination=load.destination, departure_datetime=departure, arrival_datetime=arrival,
            patient_ids=load.patient_ids, duration_minutes=travel_minutes, resource_id=network.network_id,
        ))
    return tuple(missions)


# ---------------------------------------------------------------------------
# Automated Conventional CLUSTER + DISTRIBUTION landing-point authority
# (repository-first closure build). This is a genuinely NEW concept that the
# audit confirmed was ABSENT from this module ("landing", "hub", "zone",
# "floor_station" -- zero matches). It composes ONLY the existing timing
# primitives above (`compute_manual_mission_timing`, the AGV/PTS mission
# converters) into the timing chain:
#   T_origin_handling + T_automated_main_leg + T_landing_handoff +
#   T_manual_last_mile + T_destination_handoff
# It never introduces a new physics model, and it never claims a real,
# calibrated main-leg route distance -- the automated main leg reuses the
# SAME `controlled_scenario_horizontal_minutes`-style placeholder already
# used everywhere else in this authority for whole-hospital timing, honestly
# flagged NOT_CALIBRATED. Only the manual last-mile leg gets an explicit,
# short, disclosed distance (mirrors the corrected AGV/PTS last-mile fix
# already established in `operational_day_orchestrator.py`: never reuse a
# full door-to-door mission timing model as a short hand-off).
# ---------------------------------------------------------------------------

AUTOMATED_CONVENTIONAL_CLUSTER_MAX_VERTICAL_TRANSITIONS: int = 1
"""Floors reachable within this many vertical transitions from the general
logistics origin are served by the CLUSTER tier (pure Manual Conventional,
unchanged) -- manual porter round trips there are already short/efficient,
so automated distribution provides no measurable benefit. Floors requiring
MORE vertical transitions are served by the DISTRIBUTION tier (automated
main leg to a floor landing point + manual last mile). This is a disclosed,
named policy threshold grounded in vertical-transit efficiency -- not an
arbitrary hard-coded room/floor list -- and can be recalibrated once real
building geometry/distance data is available for this general-logistics
demand model (which currently carries ward/floor identity but not literal
room coordinates, unlike `spatial_benchmark.BenchmarkGeometry`)."""

LANDING_POINT_LAST_MILE_DISTANCE_M: float = 15.0
"""Distance from a floor's automated landing point to an individual
destination room -- a short local hand-off, explicitly distinct from the
automated main-leg distance. Never reused as a stand-in for the full
main-leg or a full round-trip mission."""


FloorServiceTier = Literal["CLUSTER", "DISTRIBUTION"]


def classify_floor_service_tier(
    *, vertical_transitions_from_origin: int,
    cluster_max_vertical_transitions: int = AUTOMATED_CONVENTIONAL_CLUSTER_MAX_VERTICAL_TRANSITIONS,
) -> FloorServiceTier:
    """Section 8-9 closure: clustering emerges from a disclosed
    vertical-transit-efficiency threshold applied to the ACTUAL per-floor
    vertical transition count, never an arbitrary floor list."""
    return "CLUSTER" if vertical_transitions_from_origin <= cluster_max_vertical_transitions else "DISTRIBUTION"


@dataclass(frozen=True)
class AutomatedConventionalMissionTiming:
    """Section 11 timing chain for ONE DISTRIBUTION-tier mission (T_queue_wait
    is applied downstream by `compute_porter_resource_requirement`'s
    sweep-line peak-concurrency logic, not duplicated here)."""

    technology: Literal["AGV_AMR", "PNEUMATIC_TUBE"]
    origin_handling_minutes: float
    automated_main_leg_minutes: float
    automated_main_leg_route_status: Literal["ROUTE_CALIBRATED", "ROUTE_NOT_CALIBRATED"]
    landing_handoff_minutes: float
    manual_last_mile_minutes: float
    destination_handoff_minutes: float
    total_minutes: float


def compute_automated_conventional_distribution_timing(
    *, policy: PorterOperatingPolicy, main_leg_technology: Literal["AGV_AMR", "PNEUMATIC_TUBE"],
    agv_model: AgvModelClass | None = None, pts_network: PneumaticTubeNetwork | None = None,
    automated_main_leg_minutes: float = 4.0,
    last_mile_technology: Literal["MANUAL_PORTER", "PORTER_CART"] = "MANUAL_PORTER",
) -> AutomatedConventionalMissionTiming:
    """Composes the DISTRIBUTION-tier mission timing (section 10-11) from
    EXISTING dispatch/load/unload/last-mile primitives -- never a new
    physics model. `automated_main_leg_minutes` defaults to the SAME
    `controlled_scenario_horizontal_minutes=4.0` convention used by
    `compute_manual_mission_timing`/`convert_load_to_agv_missions` elsewhere
    in this authority (explicitly ROUTE_NOT_CALIBRATED)."""
    if main_leg_technology == "AGV_AMR":
        if agv_model is None:
            raise ValueError("agv_model is required for AGV_AMR main leg")
        landing_handoff_minutes = policy.load_minutes
    elif main_leg_technology == "PNEUMATIC_TUBE":
        if pts_network is None:
            raise ValueError("pts_network is required for PNEUMATIC_TUBE main leg")
        landing_handoff_minutes = pts_network.station_handling_minutes
    else:
        raise ValueError(f"Unsupported main-leg technology: {main_leg_technology}")

    last_mile = compute_manual_mission_timing(
        policy=policy, technology=last_mile_technology,
        horizontal_distance_m=LANDING_POINT_LAST_MILE_DISTANCE_M, vertical_transitions=0,
    )
    destination_handoff_minutes = policy.unload_minutes
    total_minutes = (
        policy.dispatch_minutes + automated_main_leg_minutes + landing_handoff_minutes
        + last_mile.total_minutes + destination_handoff_minutes
    )
    return AutomatedConventionalMissionTiming(
        technology=main_leg_technology, origin_handling_minutes=policy.dispatch_minutes,
        automated_main_leg_minutes=automated_main_leg_minutes, automated_main_leg_route_status="ROUTE_NOT_CALIBRATED",
        landing_handoff_minutes=landing_handoff_minutes, manual_last_mile_minutes=last_mile.total_minutes,
        destination_handoff_minutes=destination_handoff_minutes, total_minutes=total_minutes,
    )


# ---------------------------------------------------------------------------
# Automated Conventional portfolio enumeration/selection (sections 5, 46,
# 54-63) -- MINIMUM feasible portfolio, never auto-purchase everything.
# ---------------------------------------------------------------------------

PortfolioId = Literal["MANUAL_ONLY", "MANUAL_PLUS_AGV", "MANUAL_PLUS_PTS", "MANUAL_PLUS_AGV_PLUS_PTS"]

_PORTFOLIO_TECHNOLOGIES: Mapping[PortfolioId, frozenset[TechnologyType]] = {
    "MANUAL_ONLY": frozenset({"MANUAL_PORTER", "PORTER_CART"}),
    "MANUAL_PLUS_AGV": frozenset({"MANUAL_PORTER", "PORTER_CART", "AGV_AMR"}),
    "MANUAL_PLUS_PTS": frozenset({"MANUAL_PORTER", "PORTER_CART", "PNEUMATIC_TUBE"}),
    "MANUAL_PLUS_AGV_PLUS_PTS": frozenset({"MANUAL_PORTER", "PORTER_CART", "AGV_AMR", "PNEUMATIC_TUBE"}),
}


@dataclass(frozen=True)
class StreamTechnologyAssignment:
    stream: LogisticsStream
    assigned_technology: TechnologyType


@dataclass(frozen=True)
class PortfolioEvaluation:
    """Section 54/62: one row per evaluated portfolio -- feasibility and
    economics are OUTPUTS, never assumed winners (section 55)."""

    portfolio_id: PortfolioId
    stream_assignments: tuple[StreamTechnologyAssignment, ...]
    residual_manual_streams: tuple[LogisticsStream, ...]
    new_study_capex: float
    annual_opex: float
    feasible: bool
    reason: str


def assign_technology_per_stream(*, portfolio_id: PortfolioId, streams: tuple[LogisticsStream, ...]) -> tuple[StreamTechnologyAssignment, ...]:
    """Section 55: prefers the highest-throughput compatible AUTOMATED
    technology in the portfolio for each stream; falls back to MANUAL_PORTER
    when no automated technology in the portfolio is compatible (section 61) --
    never hard-coded per-stream winners."""
    available = _PORTFOLIO_TECHNOLOGIES[portfolio_id]
    preference_order: tuple[TechnologyType, ...] = ("AGV_AMR", "PNEUMATIC_TUBE", "PORTER_CART", "MANUAL_PORTER")
    assignments = []
    for stream in streams:
        chosen: TechnologyType = "MANUAL_PORTER"
        for tech in preference_order:
            if tech in available and is_technology_compatible(tech, stream):
                chosen = tech
                break
        assignments.append(StreamTechnologyAssignment(stream=stream, assigned_technology=chosen))
    return tuple(assignments)


def is_portfolio_feasible_for_streams(*, technologies: frozenset[TechnologyType], streams: tuple[LogisticsStream, ...]) -> bool:
    """Correction section 33: a portfolio is feasible only if EVERY stream
    has at least one compatible technology within it -- computed from the
    real compatibility matrix, never assumed True."""
    return all(any(is_technology_compatible(t, s) for t in technologies) for s in streams)


def evaluate_portfolio(
    *, portfolio_id: PortfolioId, streams: tuple[LogisticsStream, ...],
    agv_new_capex: float, agv_annual_opex_value: float,
    pts_new_capex: float, pts_annual_opex_value: float,
    manual_annual_opex: float | None = None,
    manual_annual_opex_by_stream: Mapping[LogisticsStream, float] | None = None,
) -> PortfolioEvaluation:
    """Section 57-58/60: CapEx/OPEX limited to the SELECTED portfolio's
    technologies only -- never charges an unused technology.

    Correction section 38: `manual_annual_opex_by_stream` charges manual
    labor OPEX only for the RESIDUAL (still-manual) streams -- a stream
    assigned to AGV/PTS no longer contributes porter labor cost, so
    automation can genuinely reduce total OPEX rather than being added on
    top of an unchanged flat manual total. `manual_annual_opex` (a single
    flat figure) remains supported for backward compatibility -- callers
    using it accept the LEGACY approximation that manual labor cost does not
    shrink when streams are automated."""
    technologies = _PORTFOLIO_TECHNOLOGIES[portfolio_id]
    feasible = is_portfolio_feasible_for_streams(technologies=technologies, streams=streams)
    assignments = assign_technology_per_stream(portfolio_id=portfolio_id, streams=streams)
    residual_manual = tuple(a.stream for a in assignments if a.assigned_technology in ("MANUAL_PORTER", "PORTER_CART"))
    uses_agv = any(a.assigned_technology == "AGV_AMR" for a in assignments)
    uses_pts = any(a.assigned_technology == "PNEUMATIC_TUBE" for a in assignments)
    new_study_capex = (agv_new_capex if uses_agv else 0.0) + (pts_new_capex if uses_pts else 0.0)
    if manual_annual_opex_by_stream is not None:
        manual_cost = sum(manual_annual_opex_by_stream.get(s, 0.0) for s in residual_manual)
    elif manual_annual_opex is not None:
        manual_cost = manual_annual_opex
    else:
        raise ValueError("evaluate_portfolio requires manual_annual_opex or manual_annual_opex_by_stream")
    annual_opex = manual_cost + (agv_annual_opex_value if uses_agv else 0.0) + (pts_annual_opex_value if uses_pts else 0.0)
    return PortfolioEvaluation(
        portfolio_id=portfolio_id, stream_assignments=assignments, residual_manual_streams=residual_manual,
        new_study_capex=new_study_capex, annual_opex=annual_opex, feasible=feasible,
        reason=(
            "All streams assigned a compatible technology (fallback to MANUAL_PORTER where no automated option in this portfolio is compatible)"
            if feasible else "At least one stream has no compatible technology within this portfolio (correction section 33)"
        ),
    )


def select_minimum_feasible_portfolio(evaluations: tuple[PortfolioEvaluation, ...]) -> PortfolioEvaluation:
    """LEGACY selection rule (CapEx-first among feasible) -- retained for
    backward compatibility. Superseded as the PRIMARY investment decision
    rule by `select_best_portfolio_by_lifecycle_economics` (correction
    sections 32-38): CapEx-first structurally favors zero-CapEx Manual and
    can never let automation win even when justified by lifecycle economics."""
    feasible = tuple(e for e in evaluations if e.feasible)
    if not feasible:
        raise ValueError("No feasible Automated Conventional portfolio found")
    return min(feasible, key=lambda e: (e.new_study_capex, e.annual_opex))


# ---------------------------------------------------------------------------
# Lifecycle/TCO portfolio ranking (correction sections 32-39) -- feasibility
# first, then rank by the EXISTING `study_scope.apply_study_scope` discounted
# present-value authority -- no parallel finance engine.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PortfolioLifecycleResult:
    portfolio_id: PortfolioId
    feasible: bool
    new_study_capex: float
    annual_opex: float
    replacement_present_value: float
    lifecycle_cost: float
    """Correction section 34: new_study_capex + replacement_present_value +
    PV(annual_opex over the study horizon) -- revenue-free, lower is better."""
    npv_or_metric: float
    """Correction section 35-36: `-lifecycle_cost` for COST_ONLY; the full
    discounted NPV (including architecture-invariant patient revenue) for
    REVENUE_AWARE -- higher is better in both cases."""
    rank: int = 0
    selected: bool = False


def agv_fleet_replacement_present_value(
    model: AgvModelClass, *, fleet_size: int, analysis_years: int, discount_rate_pct: float,
) -> float:
    """Correction section 34: PV of AGV fleet replacement purchases at each
    multiple of `model.useful_life_years` within the study horizon (excludes
    the initial year-0 purchase, already counted in `new_study_capex`).
    Reuses the model's own EXISTING `useful_life_years` field -- not a new
    fabricated figure."""
    if fleet_size <= 0 or model.useful_life_years <= 0:
        return 0.0
    unit_cost = model.vehicle_capex + model.system_integration_capex
    discount_rate = discount_rate_pct / 100.0
    pv = 0.0
    year = model.useful_life_years
    while year < analysis_years:
        pv += (fleet_size * unit_cost) / ((1.0 + discount_rate) ** year)
        year += model.useful_life_years
    return pv


def evaluate_portfolio_lifecycle(
    evaluation: PortfolioEvaluation, *, mode: Literal["COST_ONLY", "REVENUE_AWARE"],
    study_scope: Literal["OPERATIONAL_ONLY", "CAPITAL_PLANNING"],
    replacement_present_value: float = 0.0, operating_days_per_year: int = 300,
    discount_rate_pct: float = 8.0, analysis_years: int = 10,
    architecture_invariant_annual_revenue: float = 0.0,
) -> PortfolioLifecycleResult:
    """Correction section 34/36: reuses `study_scope.apply_study_scope` --
    THE existing discounted lifecycle/NPV authority -- twice: once with
    revenue=0 to obtain a pure `lifecycle_cost`, and once with the (mode-
    gated) architecture-invariant patient revenue to obtain `npv_or_metric`.
    Never a parallel finance engine."""
    from study_scope import apply_study_scope

    reference_capex = evaluation.new_study_capex + replacement_present_value
    cost_only_result = apply_study_scope(
        study_scope=study_scope, transport_architecture="CONVENTIONAL", qualified_throughput=1,
        reference_capex=reference_capex, annual_opex=evaluation.annual_opex, revenue_per_scan=0.0,
        operating_days_per_year=operating_days_per_year, discount_rate_pct=discount_rate_pct, analysis_years=analysis_years,
    )
    lifecycle_cost = -cost_only_result.operating_horizon_present_value

    revenue = architecture_invariant_annual_revenue if mode == "REVENUE_AWARE" else 0.0
    revenue_per_scan = (revenue / operating_days_per_year) if operating_days_per_year > 0 else 0.0
    metric_result = apply_study_scope(
        study_scope=study_scope, transport_architecture="CONVENTIONAL", qualified_throughput=1,
        reference_capex=reference_capex, annual_opex=evaluation.annual_opex, revenue_per_scan=revenue_per_scan,
        operating_days_per_year=operating_days_per_year, discount_rate_pct=discount_rate_pct, analysis_years=analysis_years,
    )
    npv_or_metric = metric_result.operating_horizon_present_value

    return PortfolioLifecycleResult(
        portfolio_id=evaluation.portfolio_id, feasible=evaluation.feasible, new_study_capex=evaluation.new_study_capex,
        annual_opex=evaluation.annual_opex, replacement_present_value=replacement_present_value,
        lifecycle_cost=lifecycle_cost, npv_or_metric=npv_or_metric,
    )


def rank_portfolios_by_lifecycle_economics(results: tuple[PortfolioLifecycleResult, ...]) -> tuple[PortfolioLifecycleResult, ...]:
    """Correction section 33/35-36: FEASIBILITY FIRST (infeasible portfolios
    are never ranked/selectable), THEN highest `npv_or_metric` wins -- never
    CapEx-first (section 32). Manual is still allowed to win (section 37) if
    its lifecycle economics are best; automation is allowed to win (section
    38) when its lower recurring cost outweighs its CapEx over the horizon."""
    feasible = [r for r in results if r.feasible]
    infeasible = [r for r in results if not r.feasible]
    ranked_feasible = sorted(feasible, key=lambda r: r.npv_or_metric, reverse=True)
    output = []
    for i, r in enumerate(ranked_feasible):
        output.append(replace(r, rank=i + 1, selected=(i == 0)))
    for r in infeasible:
        output.append(replace(r, rank=0, selected=False))
    return tuple(output)


def select_best_portfolio_by_lifecycle_economics(results: tuple[PortfolioLifecycleResult, ...]) -> PortfolioLifecycleResult:
    """Correction sections 32-38: PRIMARY portfolio-selection authority --
    feasibility first, then maximum discounted lifecycle NPV (equivalently,
    minimum lifecycle cost under COST_ONLY, since `npv_or_metric ==
    -lifecycle_cost` there)."""
    ranked = rank_portfolios_by_lifecycle_economics(results)
    selected = next((r for r in ranked if r.selected), None)
    if selected is None:
        raise ValueError("No feasible Automated Conventional portfolio found")
    return selected


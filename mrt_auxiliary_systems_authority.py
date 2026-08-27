"""MRT + Automated-Conventional Auxiliary Systems Authority + Unified What-If
Parameter/Impact Contract.

GOVERNANCE: this module NEVER creates a second finance/decay/spatial engine.
It composes NEW physical auxiliary-system calculations (resistive/thermal/
cooling/vacuum/site-power) and feeds RESOLVED values into the EXISTING
economic composition authority (`equipment_energy_opex.build_ledger_energy_component`,
`infrastructure_opex.py`) -- it never bypasses them.

MANDATORY AUDIT FINDING (section 58/191, read BEFORE writing any new
physics): the repository ALREADY explicitly discloses MRT carrier/guideway
energy as uncalibrated PHYSICS:

    equipment_energy_opex.MRT_ENERGY_STATUS == "ENERGY_SPECIFICATION_NOT_CALIBRATED"

while `models.PlannerAssumptions` carries a SEPARATE, already-existing
PROJECT_PLANNING_ASSUMPTION-tier annual OPEX figure:

    mrt_carrier_allocated_electricity_opex_per_operated_unit_year = $250/unit/year
    mrt_carrier_maintenance_opex_per_installed_unit_year = $500/unit/year
    mrt_guideway_maintenance_fraction_of_capex_per_year = 3%/year

These are NOT a physical calculation -- they are a controlled planning
allowance. This module's new resistive/thermal physics NEVER silently adds
on top of them; reconciliation is delegated to the EXISTING
`equipment_energy_opex.build_ledger_energy_component()` fallback policy
(CALIBRATED_FOR_ENERGY -> physical value REPLACES the allowance; otherwise
the allowance is preserved unchanged, tagged GENERIC_ENERGY_FALLBACK_USED).

Similarly for Automated Conventional: `conventional_transport_authority.py`'s
`DEFAULT_AGV_MODEL.annual_energy_opex = $1,500` and
`DEFAULT_PTS_NETWORK.annual_energy_opex = $1,000` are lumped
CONTROLLED_ENGINEERING_ASSUMPTION figures -- no charger-count/power/schedule
or blower/compressor physical detail exists in the repository. This module
represents that gap honestly as `NOT_CALIBRATED`, never fabricating charger
counts or blower wattage.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal, Mapping, Sequence

import canonical_spatial_authority as csa

AUXILIARY_SCHEMA_VERSION = "1.0.0"

CalibrationStatus = Literal[
    "CALIBRATED", "PARTIALLY_CALIBRATED", "NOT_CALIBRATED", "PENDING_CALIBRATION",
]

Provenance = Literal[
    "EXISTING_PROJECT_ASSUMPTION", "USER_SUPPLIED", "CONTROLLED_ENGINEERING_ASSUMPTION",
    "CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE", "MANUFACTURER_DATA", "PROTOTYPE_MEASURED",
    "LAB_MEASURED", "SIMULATION_DERIVED", "NOT_CALIBRATED",
]


@dataclass(frozen=True)
class EngineeringCalibrationRecord:
    """Section 84: reusable calibration provenance record -- never buried in
    a comment."""

    parameter: str
    value: float | str | None
    unit: str
    source: str
    status: CalibrationStatus
    confidence: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"] = "UNKNOWN"
    effective_version: str = AUXILIARY_SCHEMA_VERSION
    notes: str = ""


# ---------------------------------------------------------------------------
# Section 58/191: existing MRT/AGV/PTS energy-OPEX authority audit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExistingAuthorityAuditEntry:
    component: str
    file: str
    authority: str
    value: str
    semantic_meaning: str
    classification: Literal[
        "PHYSICAL_CALIBRATION", "PROJECT_PLANNING_ASSUMPTION", "CONTROLLED_SCENARIO_ASSUMPTION",
        "NOT_CALIBRATED", "EMBEDDED_COMPONENT", "SUPERSEDED",
    ]
    overlap_risk: str


def audit_existing_energy_opex_authority() -> tuple[ExistingAuthorityAuditEntry, ...]:
    """Section 58-59/191: reads live from the actual repo constants -- can
    never silently drift from the real authority."""
    from models import PlannerAssumptions
    from conventional_transport_authority import DEFAULT_AGV_MODEL, DEFAULT_PTS_NETWORK
    from equipment_energy_opex import MRT_ENERGY_STATUS

    a = PlannerAssumptions()
    return (
        ExistingAuthorityAuditEntry(
            "MRT carrier physics-level energy status", "equipment_energy_opex.py", "MRT_ENERGY_STATUS", MRT_ENERGY_STATUS,
            "Explicit disclosure that NO physically-calibrated MRT carrier/guideway energy specification exists yet.",
            "NOT_CALIBRATED", "This new module's resistive physics is the FIRST attempt at that physical calculation -- must reconcile, never stack, with the planning allowance below.",
        ),
        ExistingAuthorityAuditEntry(
            "MRT carrier electricity (planning allowance)", "models.py", "PlannerAssumptions.mrt_carrier_allocated_electricity_opex_per_operated_unit_year",
            f"${a.mrt_carrier_allocated_electricity_opex_per_operated_unit_year:,.0f}/operated-unit/year",
            "A flat per-carrier annual electricity allowance -- NOT derived from resistance/current/speed physics.",
            "PROJECT_PLANNING_ASSUMPTION", "HIGH -- represents the SAME physical carrier electricity a resistive model would compute; must be replaced (not added to) once CALIBRATED_FOR_ENERGY.",
        ),
        ExistingAuthorityAuditEntry(
            "MRT carrier maintenance", "models.py", "PlannerAssumptions.mrt_carrier_maintenance_opex_per_installed_unit_year",
            f"${a.mrt_carrier_maintenance_opex_per_installed_unit_year:,.0f}/installed-unit/year",
            "Flat per-carrier maintenance allowance -- mechanical/electrical upkeep, not an energy figure.",
            "PROJECT_PLANNING_ASSUMPTION", "LOW -- maintenance is a distinct cost category from electricity; no overlap with new resistive/thermal energy physics.",
        ),
        ExistingAuthorityAuditEntry(
            "MRT guideway maintenance fraction", "models.py", "PlannerAssumptions.mrt_guideway_maintenance_fraction_of_capex_per_year",
            f"{a.mrt_guideway_maintenance_fraction_of_capex_per_year:.0%}/year of guideway CapEx",
            "A capex-indexed maintenance allowance, not an energy figure.",
            "PROJECT_PLANNING_ASSUMPTION", "LOW -- no overlap with new resistive/thermal energy physics.",
        ),
        ExistingAuthorityAuditEntry(
            "AGV annual energy OPEX (lumped)", "conventional_transport_authority.py", "DEFAULT_AGV_MODEL.annual_energy_opex",
            f"${DEFAULT_AGV_MODEL.annual_energy_opex:,.0f}/vehicle/year", "A single lumped annual electricity figure per vehicle -- no charger count/power/schedule detail exists.",
            "CONTROLLED_SCENARIO_ASSUMPTION", "HIGH -- represents the SAME physical AGV charging electricity a charger-count/power model would compute; must be replaced (not added to) if ever calibrated.",
        ),
        ExistingAuthorityAuditEntry(
            "PTS annual energy OPEX (lumped)", "conventional_transport_authority.py", "DEFAULT_PTS_NETWORK.annual_energy_opex",
            f"${DEFAULT_PTS_NETWORK.annual_energy_opex:,.0f}/network/year", "A single lumped annual electricity figure -- no blower/compressor power/duty-cycle detail exists.",
            "CONTROLLED_SCENARIO_ASSUMPTION", "HIGH -- represents the SAME physical PTS blower/compressor electricity a physical model would compute; must be replaced (not added to) if ever calibrated.",
        ),
        ExistingAuthorityAuditEntry(
            "MRT support staff (controls-adjacent labor)", "infrastructure_opex.py", "InfrastructureOpexInputs.mrt_support_staff_fte/loaded_cost_per_fte",
            "Caller-supplied FTE x loaded cost", "Labor cost for MRT operational support -- not an electrical controls-system power figure.",
            "EMBEDDED_COMPONENT", "LOW -- labor cost, not electricity; no overlap with new MRT_CONTROL_SYSTEM electrical load.",
        ),
        ExistingAuthorityAuditEntry(
            "MRT controls CapEx (flat, once)", "canonical_spatial_authority.py", "MRT_CONTROLS_CAPEX_USD", "$100,000 once per MRT system/network",
            "A CapEx figure for the controls SYSTEM purchase -- not its ongoing electrical consumption.",
            "CONTROLLED_SCENARIO_ASSUMPTION", "LOW -- CapEx, not OPEX; this build's MRT_CONTROL_SYSTEM electrical load is a genuinely NEW (currently NOT_CALIBRATED) OPEX component, not a duplicate of the $100k CapEx.",
        ),
    )


# ---------------------------------------------------------------------------
# Section 6-9: Resistive MRT electrical authority
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConductorSpec:
    material: str | None
    resistivity_ohm_m: float | Literal["NOT_CALIBRATED"]
    length_m: float | Literal["NOT_CALIBRATED"]
    cross_sectional_area_m2: float | Literal["NOT_CALIBRATED"]
    provenance: Provenance = "NOT_CALIBRATED"


def compute_conductor_resistance_ohm(conductor: ConductorSpec) -> float | Literal["NOT_CALIBRATED"]:
    """Section 7: R = rho * L / A -- only when every input is calibrated."""
    if "NOT_CALIBRATED" in (conductor.resistivity_ohm_m, conductor.length_m, conductor.cross_sectional_area_m2):
        return "NOT_CALIBRATED"
    if conductor.cross_sectional_area_m2 <= 0:
        return "NOT_CALIBRATED"
    return conductor.resistivity_ohm_m * conductor.length_m / conductor.cross_sectional_area_m2  # type: ignore[operator]


@dataclass(frozen=True)
class ElectricalOperatingPoint:
    rms_current_a: float | Literal["NOT_CALIBRATED"]
    voltage_v: float | Literal["NOT_CALIBRATED"]
    frequency_hz: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    energized_segment_count: int | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    energized_duration_s: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    duty_cycle_fraction: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"


def compute_joule_loss_w(*, rms_current_a: float | Literal["NOT_CALIBRATED"], resistance_ohm: float | Literal["NOT_CALIBRATED"]) -> float | Literal["NOT_CALIBRATED"]:
    """Section 8: P_joule = I_rms^2 * R -- per energized segment/coil."""
    if rms_current_a == "NOT_CALIBRATED" or resistance_ohm == "NOT_CALIBRATED":
        return "NOT_CALIBRATED"
    return float(rms_current_a) ** 2 * float(resistance_ohm)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ElectromagneticLossBreakdown:
    """Section 9: explicit, individually NOT_CALIBRATED-capable loss
    categories -- never hidden inside one arbitrary multiplier."""

    joule_loss_w: float | Literal["NOT_CALIBRATED"]
    eddy_current_loss_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    core_loss_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    proximity_skin_effect_loss_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    switching_loss_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    converter_inverter_loss_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    bus_conductor_loss_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"

    def total_w(self) -> float | Literal["NOT_CALIBRATED"]:
        values = (self.joule_loss_w, self.eddy_current_loss_w, self.core_loss_w, self.proximity_skin_effect_loss_w, self.switching_loss_w, self.converter_inverter_loss_w, self.bus_conductor_loss_w)
        calibrated = [v for v in values if v != "NOT_CALIBRATED"]
        if not calibrated:
            return "NOT_CALIBRATED"
        return float(sum(calibrated))  # type: ignore[arg-type]


@dataclass(frozen=True)
class PowerElectronicsSpec:
    """Section 27: converter/inverter efficiency authority -- never assumes
    100% efficiency."""

    efficiency_fraction: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    standby_loss_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    provenance: Provenance = "NOT_CALIBRATED"


def compute_power_electronics_loss_w(*, input_power_w: float | Literal["NOT_CALIBRATED"], spec: PowerElectronicsSpec) -> float | Literal["NOT_CALIBRATED"]:
    if input_power_w == "NOT_CALIBRATED" or spec.efficiency_fraction == "NOT_CALIBRATED":
        return "NOT_CALIBRATED"
    conduction_loss = float(input_power_w) * (1.0 - float(spec.efficiency_fraction))
    standby = spec.standby_loss_w if spec.standby_loss_w != "NOT_CALIBRATED" else 0.0
    return conduction_loss + float(standby)


# ---------------------------------------------------------------------------
# Section 10-11: Thermal load (heat generation + reconciliation)
# ---------------------------------------------------------------------------

HeatSource = Literal["RESISTIVE_CONDUCTOR", "POWER_ELECTRONICS", "BUS_CONNECTIONS", "NEARBY_STRUCTURE"]


@dataclass(frozen=True)
class ThermalLoad:
    """Section 11: heat load reconciles with modeled electrical losses --
    never independently invented (never models surrounding transport air as
    the primary heat source, section 10)."""

    heat_generated_w: float | Literal["NOT_CALIBRATED"]
    by_source_w: Mapping[HeatSource, float | Literal["NOT_CALIBRATED"]]

    def heat_generated_kw(self) -> float | Literal["NOT_CALIBRATED"]:
        return self.heat_generated_w / 1000.0 if self.heat_generated_w != "NOT_CALIBRATED" else "NOT_CALIBRATED"


def compute_thermal_load(*, electromagnetic_losses: ElectromagneticLossBreakdown, power_electronics_loss_w: float | Literal["NOT_CALIBRATED"]) -> ThermalLoad:
    """Section 11: heat = sum of ALL modeled electrical losses -- reconciles
    exactly, never a separate independently-guessed heat number."""
    em_total = electromagnetic_losses.total_w()
    by_source: dict[HeatSource, float | Literal["NOT_CALIBRATED"]] = {
        "RESISTIVE_CONDUCTOR": em_total, "POWER_ELECTRONICS": power_electronics_loss_w,
    }
    calibrated = [v for v in (em_total, power_electronics_loss_w) if v != "NOT_CALIBRATED"]
    total = float(sum(calibrated)) if calibrated else "NOT_CALIBRATED"
    return ThermalLoad(heat_generated_w=total, by_source_w=by_source)


# ---------------------------------------------------------------------------
# Section 12-16: Cooling architecture
# ---------------------------------------------------------------------------

CoolingArchitecture = Literal["FORCED_AIR", "LIQUID_COOLING", "HYBRID_COOLING", "PASSIVE", "NOT_SELECTED", "NOT_CALIBRATED"]


@dataclass(frozen=True)
class ForcedAirCoolingSpec:
    """Section 13-14: cooling airflow passage is explicitly distinct from the
    carrier transport chamber -- never forces cooling air into the transport
    volume."""

    heat_rejection_w: float | Literal["NOT_CALIBRATED"]
    inlet_temp_c: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    outlet_temp_c: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    air_density_kg_m3: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    specific_heat_j_per_kg_k: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    pressure_drop_pa: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    fan_efficiency_fraction: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    isolated_from_transport_chamber: bool = True


@dataclass(frozen=True)
class ForcedAirCoolingResult:
    required_airflow_m3_s: float | Literal["NOT_CALIBRATED"]
    fan_electrical_power_w: float | Literal["NOT_CALIBRATED"]
    missing_inputs: tuple[str, ...]


def compute_forced_air_cooling(spec: ForcedAirCoolingSpec) -> ForcedAirCoolingResult:
    """Section 13/83: required airflow = Q / (rho * cp * dT); fan power =
    airflow * pressure_drop / fan_efficiency. Every missing input is
    individually reported (section 83), never silently assumed."""
    missing = []
    if spec.heat_rejection_w == "NOT_CALIBRATED":
        missing.append("heat_rejection_w")
    if spec.inlet_temp_c == "NOT_CALIBRATED" or spec.outlet_temp_c == "NOT_CALIBRATED":
        missing.append("inlet_temp_c/outlet_temp_c (allowable temperature rise)")
    if spec.air_density_kg_m3 == "NOT_CALIBRATED":
        missing.append("air_density_kg_m3")
    if spec.specific_heat_j_per_kg_k == "NOT_CALIBRATED":
        missing.append("specific_heat_j_per_kg_k")
    if spec.pressure_drop_pa == "NOT_CALIBRATED":
        missing.append("pressure_drop_pa")
    if spec.fan_efficiency_fraction == "NOT_CALIBRATED":
        missing.append("fan_efficiency_fraction")
    if missing:
        return ForcedAirCoolingResult(required_airflow_m3_s="NOT_CALIBRATED", fan_electrical_power_w="NOT_CALIBRATED", missing_inputs=tuple(missing))

    delta_t = float(spec.outlet_temp_c) - float(spec.inlet_temp_c)  # type: ignore[arg-type]
    if delta_t <= 0:
        return ForcedAirCoolingResult(required_airflow_m3_s="NOT_CALIBRATED", fan_electrical_power_w="NOT_CALIBRATED", missing_inputs=("outlet_temp_c must exceed inlet_temp_c",))
    mass_flow_kg_s = float(spec.heat_rejection_w) / (float(spec.specific_heat_j_per_kg_k) * delta_t)  # type: ignore[arg-type]
    airflow_m3_s = mass_flow_kg_s / float(spec.air_density_kg_m3)  # type: ignore[arg-type]
    fan_power_w = airflow_m3_s * float(spec.pressure_drop_pa) / float(spec.fan_efficiency_fraction)  # type: ignore[arg-type]
    return ForcedAirCoolingResult(required_airflow_m3_s=airflow_m3_s, fan_electrical_power_w=fan_power_w, missing_inputs=())


@dataclass(frozen=True)
class LiquidCoolingSpec:
    coolant: str | None
    mass_flow_kg_s: float | Literal["NOT_CALIBRATED"]
    specific_heat_j_per_kg_k: float | Literal["NOT_CALIBRATED"]
    temperature_rise_k: float | Literal["NOT_CALIBRATED"]
    pump_head_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    pump_efficiency_fraction: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    fluid_density_kg_m3: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"


@dataclass(frozen=True)
class LiquidCoolingResult:
    heat_rejection_capacity_w: float | Literal["NOT_CALIBRATED"]
    pump_electrical_power_w: float | Literal["NOT_CALIBRATED"]
    missing_inputs: tuple[str, ...]


def compute_liquid_cooling(spec: LiquidCoolingSpec) -> LiquidCoolingResult:
    """Section 15: Q = m_dot * cp * dT; pump power = m_dot * g * head / (rho * eta)."""
    missing = []
    for field_name in ("mass_flow_kg_s", "specific_heat_j_per_kg_k", "temperature_rise_k"):
        if getattr(spec, field_name) == "NOT_CALIBRATED":
            missing.append(field_name)
    if missing:
        return LiquidCoolingResult(heat_rejection_capacity_w="NOT_CALIBRATED", pump_electrical_power_w="NOT_CALIBRATED", missing_inputs=tuple(missing))
    heat_capacity_w = float(spec.mass_flow_kg_s) * float(spec.specific_heat_j_per_kg_k) * float(spec.temperature_rise_k)  # type: ignore[arg-type]

    pump_missing = [f for f in ("pump_head_m", "pump_efficiency_fraction", "fluid_density_kg_m3") if getattr(spec, f) == "NOT_CALIBRATED"]
    if pump_missing:
        return LiquidCoolingResult(heat_rejection_capacity_w=heat_capacity_w, pump_electrical_power_w="NOT_CALIBRATED", missing_inputs=tuple(pump_missing))
    g = 9.80665
    pump_power_w = float(spec.mass_flow_kg_s) * g * float(spec.pump_head_m) / float(spec.pump_efficiency_fraction)  # type: ignore[arg-type]
    return LiquidCoolingResult(heat_rejection_capacity_w=heat_capacity_w, pump_electrical_power_w=pump_power_w, missing_inputs=())


@dataclass(frozen=True)
class CoolingResult:
    """Section 16: cooling electrical power kept SEPARATE from propulsion
    power -- one of the four required electrical categories (section 16/37)."""

    architecture: CoolingArchitecture
    cooling_electrical_power_w: float | Literal["NOT_CALIBRATED"]
    missing_inputs: tuple[str, ...]


def resolve_cooling_power(*, architecture: CoolingArchitecture, forced_air: ForcedAirCoolingResult | None = None, liquid: LiquidCoolingResult | None = None) -> CoolingResult:
    if architecture == "FORCED_AIR" and forced_air is not None:
        return CoolingResult(architecture=architecture, cooling_electrical_power_w=forced_air.fan_electrical_power_w, missing_inputs=forced_air.missing_inputs)
    if architecture == "LIQUID_COOLING" and liquid is not None:
        return CoolingResult(architecture=architecture, cooling_electrical_power_w=liquid.pump_electrical_power_w, missing_inputs=liquid.missing_inputs)
    if architecture == "HYBRID_COOLING" and forced_air is not None and liquid is not None:
        values = [v for v in (forced_air.fan_electrical_power_w, liquid.pump_electrical_power_w) if v != "NOT_CALIBRATED"]
        combined_missing = forced_air.missing_inputs + liquid.missing_inputs
        return CoolingResult(architecture=architecture, cooling_electrical_power_w=(float(sum(values)) if values and not combined_missing else "NOT_CALIBRATED"), missing_inputs=combined_missing)
    if architecture == "PASSIVE":
        return CoolingResult(architecture=architecture, cooling_electrical_power_w=0.0, missing_inputs=())
    return CoolingResult(architecture=architecture, cooling_electrical_power_w="NOT_CALIBRATED", missing_inputs=("cooling architecture not selected/calibrated",))


# ---------------------------------------------------------------------------
# Section 17-23: Transport environment (pressure/vacuum) + aerodynamic drag
# ---------------------------------------------------------------------------

TransportEnvironment = Literal["ATMOSPHERIC", "REDUCED_PRESSURE", "VACUUM"]

_STANDARD_ATMOSPHERIC_DENSITY_KG_M3 = 1.225
"""Sea-level standard air density -- CONTROLLED_ENGINEERING_ASSUMPTION, used
ONLY for ATMOSPHERIC. Never applied to REDUCED_PRESSURE/VACUUM (section 19)."""


@dataclass(frozen=True)
class TransportEnvironmentSpec:
    environment: TransportEnvironment
    chamber_pressure_pa: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    """Section 18: required for REDUCED_PRESSURE/VACUUM -- never fabricated."""


def resolve_gas_density_kg_m3(spec: TransportEnvironmentSpec, *, gas_constant_j_per_kg_k: float = 287.05, temperature_k: float = 293.15) -> float | Literal["NOT_CALIBRATED"]:
    """Section 19: ideal-gas density from calibrated chamber pressure for
    REDUCED_PRESSURE/VACUUM -- ATMOSPHERIC uses the standard sea-level value;
    never reuses atmospheric density for vacuum operation."""
    if spec.environment == "ATMOSPHERIC":
        return _STANDARD_ATMOSPHERIC_DENSITY_KG_M3
    if spec.chamber_pressure_pa == "NOT_CALIBRATED":
        return "NOT_CALIBRATED"
    return float(spec.chamber_pressure_pa) / (gas_constant_j_per_kg_k * temperature_k)  # type: ignore[arg-type]


@dataclass(frozen=True)
class DragSpec:
    frontal_area_m2: float | Literal["NOT_CALIBRATED"]
    drag_coefficient: float | Literal["NOT_CALIBRATED"]


def compute_drag_force_n(*, spec: DragSpec, gas_density_kg_m3: float | Literal["NOT_CALIBRATED"], speed_m_per_s: float) -> float | Literal["NOT_CALIBRATED"]:
    """Section 19: F_drag = 0.5 * rho * Cd * A * v^2 -- speed-dependent,
    never a fixed assumption."""
    if spec.frontal_area_m2 == "NOT_CALIBRATED" or spec.drag_coefficient == "NOT_CALIBRATED" or gas_density_kg_m3 == "NOT_CALIBRATED":
        return "NOT_CALIBRATED"
    return 0.5 * float(gas_density_kg_m3) * float(spec.drag_coefficient) * float(spec.frontal_area_m2) * speed_m_per_s ** 2  # type: ignore[arg-type]


def compute_drag_power_w(*, drag_force_n: float | Literal["NOT_CALIBRATED"], speed_m_per_s: float) -> float | Literal["NOT_CALIBRATED"]:
    """Section 20: P_drag = F_drag * v -- one genuine source of NONLINEAR
    (cubic in speed) power growth, never a linear speed assumption."""
    if drag_force_n == "NOT_CALIBRATED":
        return "NOT_CALIBRATED"
    return float(drag_force_n) * speed_m_per_s


@dataclass(frozen=True)
class VacuumSystemSpec:
    """Section 21: vacuum pump authority -- never fabricates pump size."""

    conduit_volume_m3: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    target_pressure_pa: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    leakage_rate_pa_m3_per_s: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    pump_down_time_s: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    pump_efficiency_fraction: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    holding_power_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"


@dataclass(frozen=True)
class VacuumEnergyResult:
    pump_down_energy_j: float | Literal["NOT_CALIBRATED"]
    steady_holding_power_w: float | Literal["NOT_CALIBRATED"]
    missing_inputs: tuple[str, ...]


def compute_vacuum_energy(spec: VacuumSystemSpec) -> VacuumEnergyResult:
    """Section 22: pump-down energy and steady holding power kept DISTINCT."""
    missing = []
    if spec.conduit_volume_m3 == "NOT_CALIBRATED":
        missing.append("conduit_volume_m3")
    if spec.target_pressure_pa == "NOT_CALIBRATED":
        missing.append("target_pressure_pa")
    if spec.pump_down_time_s == "NOT_CALIBRATED":
        missing.append("pump_down_time_s")
    if spec.pump_efficiency_fraction == "NOT_CALIBRATED":
        missing.append("pump_efficiency_fraction")
    pump_down_energy: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    if not missing:
        # W = P*V*ln(P_atm/P_target)/eta -- isothermal pump-down work approximation
        p_atm = 101_325.0
        work_j = float(spec.target_pressure_pa) * float(spec.conduit_volume_m3) * math.log(p_atm / float(spec.target_pressure_pa)) / float(spec.pump_efficiency_fraction)  # type: ignore[arg-type]
        pump_down_energy = abs(work_j)
    holding = spec.holding_power_w
    if holding == "NOT_CALIBRATED":
        missing.append("holding_power_w")
    return VacuumEnergyResult(pump_down_energy_j=pump_down_energy, steady_holding_power_w=holding, missing_inputs=tuple(missing))


# ---------------------------------------------------------------------------
# Section 24-26: Superconducting MRT + Hybrid resistive/superconducting
# ---------------------------------------------------------------------------

MrtGuidewayTechnology = Literal["RESISTIVE", "SUPERCONDUCTING", "HYBRID"]


@dataclass(frozen=True)
class SuperconductingAuxiliarySpec:
    """Section 24-25: a DISTINCT contract -- never inherits the resistive
    thermal model blindly."""

    cryogenic_refrigeration_demand_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    cryocooler_electrical_demand_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    thermal_leak_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    vacuum_insulation_pump_power_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    controls_power_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"

    def total_w(self) -> float | Literal["NOT_CALIBRATED"]:
        values = (self.cryogenic_refrigeration_demand_w, self.cryocooler_electrical_demand_w, self.thermal_leak_w, self.vacuum_insulation_pump_power_w, self.controls_power_w)
        calibrated = [v for v in values if v != "NOT_CALIBRATED"]
        return float(sum(calibrated)) if calibrated else "NOT_CALIBRATED"


def compose_hybrid_guideway_load(
    *, resistive_electrical_w: float | Literal["NOT_CALIBRATED"], superconducting_electrical_w: float | Literal["NOT_CALIBRATED"],
    shared_controls_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED",
) -> float | Literal["NOT_CALIBRATED"]:
    """Section 26: combines applicable subsystems WITHOUT double-counting
    shared controls/communications -- `shared_controls_w` is added exactly
    ONCE, never once per subsystem."""
    values = [v for v in (resistive_electrical_w, superconducting_electrical_w, shared_controls_w) if v != "NOT_CALIBRATED"]
    return float(sum(values)) if values else "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# Section 28-30: Segmented energization, duty cycle, concurrency
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SegmentedEnergizationSpec:
    """Section 28-30: distinguishes localized/segmented energization from
    naive full-guideway continuous peak power; scales with actual
    concurrency, never `one_carrier_power * total_daily_carriers`."""

    per_segment_power_w: float | Literal["NOT_CALIBRATED"]
    simultaneous_active_segments: int | Literal["NOT_CALIBRATED"]
    duty_cycle_fraction: float | Literal["NOT_CALIBRATED"] = 1.0


@dataclass(frozen=True)
class NetworkElectricalLoadResult:
    instantaneous_peak_w: float | Literal["NOT_CALIBRATED"]
    average_w: float | Literal["NOT_CALIBRATED"]


def compute_network_electrical_load(spec: SegmentedEnergizationSpec) -> NetworkElectricalLoadResult:
    if spec.per_segment_power_w == "NOT_CALIBRATED" or spec.simultaneous_active_segments == "NOT_CALIBRATED":
        return NetworkElectricalLoadResult(instantaneous_peak_w="NOT_CALIBRATED", average_w="NOT_CALIBRATED")
    peak = float(spec.per_segment_power_w) * int(spec.simultaneous_active_segments)  # type: ignore[arg-type]
    duty = spec.duty_cycle_fraction if spec.duty_cycle_fraction != "NOT_CALIBRATED" else 1.0
    return NetworkElectricalLoadResult(instantaneous_peak_w=peak, average_w=peak * float(duty))


# ---------------------------------------------------------------------------
# Section 31-33: Carrier kinematics (mass, acceleration, regeneration)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CarrierKinematicsSpec:
    carrier_mass_kg: float | Literal["NOT_CALIBRATED"]
    payload_mass_kg: float | Literal["NOT_CALIBRATED"]
    target_speed_m_per_s: float
    acceleration_m_per_s2: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    route_length_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    regenerative_braking_status: Literal["NOT_MODELED", "NOT_CALIBRATED", "MODELED"] = "NOT_MODELED"
    regenerative_recovery_fraction: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    """Section 33: only used when `regenerative_braking_status == "MODELED"`
    AND this fraction is itself calibrated -- never a fabricated default
    recovery efficiency."""


@dataclass(frozen=True)
class TransportTimeResult:
    accelerate_time_s: float | Literal["NOT_CALIBRATED"]
    steady_time_s: float | Literal["NOT_CALIBRATED"]
    total_time_s: float | Literal["NOT_CALIBRATED"]


def compute_transport_time(spec: CarrierKinematicsSpec) -> TransportTimeResult:
    """Section 32: transport time explicitly distinguishes acceleration from
    steady-speed travel (section 3/89)."""
    if spec.route_length_m == "NOT_CALIBRATED" or spec.target_speed_m_per_s <= 0:
        return TransportTimeResult(accelerate_time_s="NOT_CALIBRATED", steady_time_s="NOT_CALIBRATED", total_time_s="NOT_CALIBRATED")
    if spec.acceleration_m_per_s2 == "NOT_CALIBRATED" or spec.acceleration_m_per_s2 <= 0:
        steady_time = float(spec.route_length_m) / spec.target_speed_m_per_s  # type: ignore[arg-type]
        return TransportTimeResult(accelerate_time_s="NOT_CALIBRATED", steady_time_s=steady_time, total_time_s=steady_time)
    accel_time = spec.target_speed_m_per_s / float(spec.acceleration_m_per_s2)  # type: ignore[arg-type]
    accel_distance = 0.5 * float(spec.acceleration_m_per_s2) * accel_time ** 2  # type: ignore[arg-type]
    remaining_distance = float(spec.route_length_m) - 2 * accel_distance  # type: ignore[arg-type]
    if remaining_distance < 0:
        return TransportTimeResult(accelerate_time_s=accel_time, steady_time_s="NOT_CALIBRATED", total_time_s="NOT_CALIBRATED")
    steady_time = remaining_distance / spec.target_speed_m_per_s
    return TransportTimeResult(accelerate_time_s=accel_time, steady_time_s=steady_time, total_time_s=2 * accel_time + steady_time)


def compute_acceleration_energy_j(spec: CarrierKinematicsSpec) -> float | Literal["NOT_CALIBRATED"]:
    """Section 32: kinetic energy imparted during acceleration -- distinct
    from steady-speed drag/resistive energy."""
    if spec.carrier_mass_kg == "NOT_CALIBRATED" or spec.payload_mass_kg == "NOT_CALIBRATED":
        return "NOT_CALIBRATED"
    total_mass = float(spec.carrier_mass_kg) + float(spec.payload_mass_kg)  # type: ignore[arg-type]
    kinetic_energy = 0.5 * total_mass * spec.target_speed_m_per_s ** 2
    if spec.regenerative_braking_status == "MODELED" and spec.regenerative_recovery_fraction != "NOT_CALIBRATED":
        return kinetic_energy * (1.0 - float(spec.regenerative_recovery_fraction))
    return kinetic_energy


# ---------------------------------------------------------------------------
# Section 34-37: Controls / sensors / communications + total electrical load
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MrtAuxiliaryElectricalComponents:
    """Section 37: the four+ required electrical categories, kept
    individually inspectable -- never pre-summed into one opaque figure."""

    electromagnetic_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    power_electronics_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    cooling_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    vacuum_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    controls_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    sensors_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    communications_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    other_auxiliaries_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"


@dataclass(frozen=True)
class MrtTotalElectricalLoadResult:
    total_w: float | Literal["NOT_CALIBRATED"]
    resolved_components: Mapping[str, float]
    unresolved_components: tuple[str, ...]


def compute_mrt_total_electrical_load(components: MrtAuxiliaryElectricalComponents) -> MrtTotalElectricalLoadResult:
    """Section 37: sums only calibrated categories -- never silently treats
    an unresolved subsystem as zero without disclosure."""
    field_names = ("electromagnetic_w", "power_electronics_w", "cooling_w", "vacuum_w", "controls_w", "sensors_w", "communications_w", "other_auxiliaries_w")
    resolved = {}
    unresolved = []
    for f in field_names:
        v = getattr(components, f)
        if v == "NOT_CALIBRATED":
            unresolved.append(f)
        else:
            resolved[f] = float(v)
    total = float(sum(resolved.values())) if resolved else "NOT_CALIBRATED"
    return MrtTotalElectricalLoadResult(total_w=total, resolved_components=resolved, unresolved_components=tuple(unresolved))


# ---------------------------------------------------------------------------
# Section 38-41: Peak vs average power, annual energy, electricity OPEX
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnnualEnergyResult:
    peak_kw: float | Literal["NOT_CALIBRATED"]
    average_operating_kw: float | Literal["NOT_CALIBRATED"]
    annual_kwh: float | Literal["NOT_CALIBRATED"]


def compute_annual_energy(*, average_operating_w: float | Literal["NOT_CALIBRATED"], peak_w: float | Literal["NOT_CALIBRATED"], operating_hours_per_year: float | Literal["NOT_CALIBRATED"]) -> AnnualEnergyResult:
    """Section 38-39: annual kWh derives from average operating power over
    the ACTUAL operating schedule -- never `peak_kW * 8760` unless
    `operating_hours_per_year == 8760` is explicitly supplied (continuous
    operation)."""
    if average_operating_w == "NOT_CALIBRATED" or operating_hours_per_year == "NOT_CALIBRATED":
        return AnnualEnergyResult(peak_kw=(peak_w / 1000.0 if peak_w != "NOT_CALIBRATED" else "NOT_CALIBRATED"), average_operating_kw="NOT_CALIBRATED", annual_kwh="NOT_CALIBRATED")
    average_kw = float(average_operating_w) / 1000.0  # type: ignore[arg-type]
    return AnnualEnergyResult(peak_kw=(peak_w / 1000.0 if peak_w != "NOT_CALIBRATED" else "NOT_CALIBRATED"), average_operating_kw=average_kw, annual_kwh=average_kw * float(operating_hours_per_year))  # type: ignore[arg-type]


def compute_electricity_opex(*, annual_kwh: float | Literal["NOT_CALIBRATED"], electricity_cost_per_kwh: float | Literal["NOT_CALIBRATED"]) -> float | Literal["NOT_CALIBRATED"]:
    """Section 40-41: reuses the SAME `electricity_cost_per_kwh` tariff
    concept already used throughout `infrastructure_opex.py`/
    `equipment_energy_opex.py` -- never a second finance engine."""
    if annual_kwh == "NOT_CALIBRATED" or electricity_cost_per_kwh == "NOT_CALIBRATED":
        return "NOT_CALIBRATED"
    return float(annual_kwh) * float(electricity_cost_per_kwh)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Section 42-47: Site power profile + adequacy
# ---------------------------------------------------------------------------

SitePowerAdequacyStatus = Literal["ADEQUATE", "INADEQUATE", "NOT_CALIBRATED"]
PowerReliabilityClassification = Literal["NORMAL_UTILITY", "RESILIENT_HOSPITAL_GRADE", "WEAK_GRID", "NOT_CALIBRATED"]
BackupPowerClassification = Literal["SITE_SPECIFIC_RESILIENCE", "INTRINSIC_MRT_COMPONENT"]


@dataclass(frozen=True)
class SitePowerProfile:
    """Section 42: site-level electrical-service profile -- entirely
    SEPARATE from any single architecture's intrinsic auxiliary load."""

    available_normal_power_kw: float | Literal["NOT_CALIBRATED"]
    available_emergency_power_kw: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    ups_capacity_kw: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    reliability_classification: PowerReliabilityClassification = "NOT_CALIBRATED"
    outage_characteristics: str | None = None
    power_quality_status: Literal["NORMAL", "DEGRADED", "NOT_CALIBRATED"] = "NOT_CALIBRATED"
    provenance: Provenance = "NOT_CALIBRATED"


@dataclass(frozen=True)
class SitePowerAdequacyResult:
    status: SitePowerAdequacyStatus
    headroom_kw: float | Literal["NOT_CALIBRATED"]
    incremental_backup_capex_usd: float | Literal["NOT_CALIBRATED"]
    backup_classification: BackupPowerClassification | None


def evaluate_site_power_adequacy(
    *, profile: SitePowerProfile, incremental_demand_kw: float | Literal["NOT_CALIBRATED"],
    incremental_backup_generation_capex_usd: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED",
) -> SitePowerAdequacyResult:
    """Section 43-46: normal adequate-hospital case legitimately produces
    $0 incremental backup CapEx (section 43); only a weak-grid/inadequate
    site should even consider incremental resilience infrastructure, and
    even then it is classified SITE_SPECIFIC_RESILIENCE, never
    INTRINSIC_MRT_COMPONENT (section 46)."""
    if profile.available_normal_power_kw == "NOT_CALIBRATED" or incremental_demand_kw == "NOT_CALIBRATED":
        return SitePowerAdequacyResult(status="NOT_CALIBRATED", headroom_kw="NOT_CALIBRATED", incremental_backup_capex_usd="NOT_CALIBRATED", backup_classification=None)
    headroom = float(profile.available_normal_power_kw) - float(incremental_demand_kw)  # type: ignore[arg-type]
    if headroom >= 0:
        return SitePowerAdequacyResult(status="ADEQUATE", headroom_kw=headroom, incremental_backup_capex_usd=0.0, backup_classification=None)
    return SitePowerAdequacyResult(
        status="INADEQUATE", headroom_kw=headroom, incremental_backup_capex_usd=incremental_backup_generation_capex_usd,
        backup_classification="SITE_SPECIFIC_RESILIENCE",
    )


ADEQUATE_HOSPITAL_SITE_POWER_PROFILE = SitePowerProfile(
    available_normal_power_kw=5_000.0, available_emergency_power_kw=2_000.0, ups_capacity_kw=500.0,
    reliability_classification="RESILIENT_HOSPITAL_GRADE", power_quality_status="NORMAL",
    provenance="CONTROLLED_ENGINEERING_ASSUMPTION",
)
"""Section 103: controlled site-power example -- a normal, already-resilient
hospital with ample headroom. NOT a claim about any real facility."""

WEAK_GRID_CONTROLLED_SITE_POWER_PROFILE = SitePowerProfile(
    available_normal_power_kw=50.0, available_emergency_power_kw="NOT_CALIBRATED", ups_capacity_kw="NOT_CALIBRATED",
    reliability_classification="WEAK_GRID", power_quality_status="DEGRADED",
    provenance="CONTROLLED_ENGINEERING_ASSUMPTION",
)
"""Section 104: WEAK_GRID_CONTROLLED_SCENARIO -- deliberately inadequate for
a meaningful MRT load, to prove the model can identify inadequacy without
fabricating a generator price (incremental_backup_generation_capex_usd stays
NOT_CALIBRATED unless the caller explicitly supplies a real cost)."""


# ---------------------------------------------------------------------------
# Section 48-53: Automated-Conventional auxiliary parity + Manual Conventional
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgvChargingAuthorityResult:
    """Section 51: explicit charger-level authority -- NOT_CALIBRATED unless
    real charger count/power/schedule data exists (it does not, per audit)."""

    charger_count: int | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    charger_power_kw: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    peak_charging_demand_kw: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    annual_charging_energy_kwh: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    existing_lumped_annual_opex_usd: float = 0.0
    provenance: str = "NOT_CALIBRATED -- no charger count/power/schedule data exists in this repository; existing lumped annual_energy_opex assumption is preserved unchanged (section 50)."


def resolve_agv_charging_authority(*, existing_annual_energy_opex_usd: float) -> AgvChargingAuthorityResult:
    """Section 50-51: preserves the EXISTING `DEFAULT_AGV_MODEL.annual_energy_opex`
    value unchanged; never replaces it with a fabricated charger-derived figure."""
    return AgvChargingAuthorityResult(existing_lumped_annual_opex_usd=existing_annual_energy_opex_usd)


@dataclass(frozen=True)
class PtsAuxiliaryAuthorityResult:
    """Section 52: PTS blower/compressor authority -- NOT_CALIBRATED unless
    real physical data exists (it does not, per audit); never assumes zero
    energy (section 52)."""

    blower_compressor_power_kw: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    station_controls_power_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    network_standby_load_w: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    existing_lumped_annual_opex_usd: float = 0.0
    provenance: str = "NOT_CALIBRATED -- no blower/compressor power data exists in this repository; existing lumped annual_energy_opex assumption is preserved unchanged (section 50)."


def resolve_pts_auxiliary_authority(*, existing_annual_energy_opex_usd: float) -> PtsAuxiliaryAuthorityResult:
    return PtsAuxiliaryAuthorityResult(existing_lumped_annual_opex_usd=existing_annual_energy_opex_usd)


def manual_conventional_propulsion_electricity_w() -> Literal[0.0]:
    """Section 53/107: Manual porter transport has NO propulsion electrical
    demand -- always exactly 0.0, never fabricated."""
    return 0.0


UtilityCostCategory = Literal["COMMON_BASELINE", "ARCHITECTURE_SPECIFIC", "SITE_SPECIFIC_RESILIENCE"]


@dataclass(frozen=True)
class UtilityClassification:
    load: str
    category: UtilityCostCategory
    note: str


def classify_common_vs_architecture_specific_utilities() -> tuple[UtilityClassification, ...]:
    """Section 54/107: common hospital utilities (HVAC/lighting) never
    become one architecture's cost."""
    return (
        UtilityClassification("Facility-wide HVAC/lighting", "COMMON_BASELINE", "Present regardless of transport architecture choice."),
        UtilityClassification("Manual porter propulsion electricity", "ARCHITECTURE_SPECIFIC", "Always exactly $0/0W -- Manual has no propulsion electrical demand."),
        UtilityClassification("MRT electromagnetic/cooling/vacuum/controls", "ARCHITECTURE_SPECIFIC", "Exists only because MRT/Hybrid-MRT was selected."),
        UtilityClassification("AGV charging electricity", "ARCHITECTURE_SPECIFIC", "Exists only because Automated Conventional/AGV was selected."),
        UtilityClassification("PTS blower/compressor electricity", "ARCHITECTURE_SPECIFIC", "Exists only because PTS was selected."),
        UtilityClassification("Dedicated backup generation/UPS/ATS", "SITE_SPECIFIC_RESILIENCE", "Depends on site grid adequacy, not on transport architecture choice (section 46)."),
    )


# ---------------------------------------------------------------------------
# Section 57/159-162: Legacy-vs-physical reconciliation -- reuses the
# EXISTING `equipment_energy_opex.build_ledger_energy_component` fallback
# policy verbatim. Never a second reconciliation mechanism.
# ---------------------------------------------------------------------------


def reconcile_mrt_energy_with_legacy_assumption(
    *, physical_annual_kwh: float | Literal["NOT_CALIBRATED"], physical_calibration_status: Literal["CALIBRATED_FOR_ENERGY", "PARTIALLY_CALIBRATED", "NOT_CALIBRATED", "NOT_APPLICABLE"],
    legacy_annual_opex_per_unit_usd: float, electricity_cost_per_kwh: float,
) -> "object":
    """Section 160-162: delegates to the EXISTING reconciliation authority
    (never a second one). CALIBRATED_FOR_ENERGY REPLACES the legacy $/unit
    allowance; otherwise the legacy allowance is preserved unchanged."""
    from equipment_energy_opex import build_ledger_energy_component

    legacy_equivalent_kwh = legacy_annual_opex_per_unit_usd / electricity_cost_per_kwh if electricity_cost_per_kwh > 0 else 0.0
    calculated_kwh = physical_annual_kwh if physical_annual_kwh != "NOT_CALIBRATED" else 0.0
    return build_ledger_energy_component(
        component_name="MRT carrier electricity", calculated_energy_kwh=calculated_kwh, calibration_status=physical_calibration_status,
        generic_fallback_annual_kwh=legacy_equivalent_kwh,
    )


# ---------------------------------------------------------------------------
# Section 76-77/139-142: Speed dependency graph
# ---------------------------------------------------------------------------

DependencyResolutionStatus = Literal["RESOLVED", "PENDING_ENGINEERING_RECALCULATION", "NOT_CALIBRATED", "NOT_APPLICABLE", "INFEASIBLE"]


@dataclass(frozen=True)
class DependencyNode:
    node_id: str
    display_name: str
    depends_on: tuple[str, ...]
    resolution_status: DependencyResolutionStatus
    value: float | str | None = None


SPEED_DEPENDENCY_CHAIN: tuple[str, ...] = (
    "carrier_speed", "transport_time", "acceleration_deceleration_requirement", "drag", "electromagnetic_demand",
    "energization_duty_timing", "electrical_losses", "thermal_load", "cooling_requirement", "vacuum_pressure_demand",
    "annual_energy", "annual_opex", "carrier_network_capacity", "nuclear_retained_activity_qualification", "lifecycle_economics",
)
"""Section 77: the mandatory speed dependency chain -- every node must be
representable even when its resolution_status is NOT_CALIBRATED (section
141)."""


def build_speed_dependency_trace(resolution_by_node: Mapping[str, DependencyResolutionStatus | tuple[DependencyResolutionStatus, float | str | None]]) -> tuple[DependencyNode, ...]:
    """Section 76-77/177: builds the explicit dependency trace for
    `carrier_speed` -- unresolved dependencies remain visible as
    NOT_CALIBRATED/PENDING nodes, never silently dropped."""
    nodes = []
    prior = None
    for node_id in SPEED_DEPENDENCY_CHAIN:
        entry = resolution_by_node.get(node_id, "NOT_CALIBRATED")
        if isinstance(entry, tuple):
            status, value = entry
        else:
            status, value = entry, None
        nodes.append(DependencyNode(
            node_id=node_id, display_name=node_id.replace("_", " ").title(), depends_on=((prior,) if prior else ()),
            resolution_status=status, value=value,
        ))
        prior = node_id
    return tuple(nodes)


# ============================================================================
# UNIFIED WHAT-IF PARAMETER / IMPACT CONTRACT (sections 60-154)
#
# GOVERNANCE: organizes existing + new what-if capability into ONE combined
# scenario authority. Spatial changes reuse `canonical_spatial_authority`/
# `interactive_spatial_authoring` verbatim (never re-implemented); this layer
# adds non-spatial PARAMETER changes (speed, tariff, demand, staffing, ...)
# and merges BOTH into one ordered active-change list/category-count view.
# ============================================================================

WhatIfCategory = Literal[
    "GEOMETRY_ORIENTATION", "FACILITY_EQUIPMENT", "TRANSPORT_MRT", "OPERATIONS_CAPACITY",
    "PATIENTS_DEMAND", "STAFFING_RESOURCES", "ELECTRICAL_THERMAL", "FAILURE_RESILIENCE", "ECONOMICS_ASSUMPTIONS",
]

WHAT_IF_CATEGORIES: tuple[WhatIfCategory, ...] = (
    "GEOMETRY_ORIENTATION", "FACILITY_EQUIPMENT", "TRANSPORT_MRT", "OPERATIONS_CAPACITY",
    "PATIENTS_DEMAND", "STAFFING_RESOURCES", "ELECTRICAL_THERMAL", "FAILURE_RESILIENCE", "ECONOMICS_ASSUMPTIONS",
)

ParameterType = Literal[
    "NUMERIC", "INTEGER", "BOOLEAN", "ENUM", "EQUIPMENT_SELECTION", "SPATIAL_TRANSFORM", "SPATIAL_SELECTION",
    "FAILURE_EVENT", "ARCHITECTURE_SELECTION", "DEVELOPMENT_CONTEXT", "SCHEDULE",
]


@dataclass(frozen=True)
class WhatIfParameterDefinition:
    """Section 73-75: platform-neutral parameter-registry entry -- a future
    UI control existing does NOT imply physical certainty (section 75)."""

    parameter_id: str
    display_name: str
    category: WhatIfCategory
    parameter_type: ParameterType
    unit: str | None
    valid_range: tuple[float, float] | None
    calibration_status: CalibrationStatus
    provenance: Provenance
    affected_authorities: tuple[str, ...]
    subcategory: str | None = None


@dataclass
class WhatIfParameterRegistry:
    definitions: dict[str, WhatIfParameterDefinition] = field(default_factory=dict)

    def register(self, definition: WhatIfParameterDefinition) -> None:
        self.definitions[definition.parameter_id] = definition

    def resolve(self, parameter_id: str) -> WhatIfParameterDefinition | None:
        return self.definitions.get(parameter_id)

    def by_category(self, category: WhatIfCategory) -> tuple[WhatIfParameterDefinition, ...]:
        return tuple(d for d in self.definitions.values() if d.category == category)


def build_default_parameter_registry() -> WhatIfParameterRegistry:
    """Section 60-70: representative parameters spanning ALL nine
    categories -- proves they coexist in ONE registry, never separate
    disconnected what-if applications (section 61)."""
    registry = WhatIfParameterRegistry()
    registry.register(WhatIfParameterDefinition("carrier_speed", "MRT carrier speed", "ELECTRICAL_THERMAL", "NUMERIC", "m/s", None, "CONTROLLED_ENGINEERING_ASSUMPTION" if False else "PARTIALLY_CALIBRATED", "CONTROLLED_ENGINEERING_ASSUMPTION", ("mrt_auxiliary_systems_authority", "shared_mrt_multistream_authority", "canonical_spatial_authority")))
    registry.register(WhatIfParameterDefinition("cooling_architecture", "MRT cooling architecture", "ELECTRICAL_THERMAL", "ENUM", None, None, "NOT_CALIBRATED", "NOT_CALIBRATED", ("mrt_auxiliary_systems_authority",)))
    registry.register(WhatIfParameterDefinition("transport_environment", "MRT transport environment", "ELECTRICAL_THERMAL", "ENUM", None, None, "NOT_CALIBRATED", "NOT_CALIBRATED", ("mrt_auxiliary_systems_authority",)))
    registry.register(WhatIfParameterDefinition("electricity_tariff", "Electricity tariff", "ECONOMICS_ASSUMPTIONS", "NUMERIC", "$/kWh", (0.0, 1.0), "CONTROLLED_ENGINEERING_ASSUMPTION" if False else "PARTIALLY_CALIBRATED", "EXISTING_PROJECT_ASSUMPTION", ("infrastructure_opex", "mrt_auxiliary_systems_authority")))
    registry.register(WhatIfParameterDefinition("building_transform", "Building move/rotation", "GEOMETRY_ORIENTATION", "SPATIAL_TRANSFORM", None, None, "CALIBRATED", "USER_SUPPLIED", ("canonical_spatial_authority", "interactive_spatial_authoring")))
    registry.register(WhatIfParameterDefinition("equipment_add_remove_copy", "Equipment add/remove/copy", "FACILITY_EQUIPMENT", "EQUIPMENT_SELECTION", None, None, "CALIBRATED", "USER_SUPPLIED", ("canonical_spatial_authority", "interactive_spatial_authoring")))
    registry.register(WhatIfParameterDefinition("mrt_segment_length", "MRT segment length", "TRANSPORT_MRT", "NUMERIC", "m", None, "CALIBRATED", "USER_SUPPLIED", ("canonical_spatial_authority",)))
    registry.register(WhatIfParameterDefinition("operating_hours_per_day", "Operating hours/day", "OPERATIONS_CAPACITY", "NUMERIC", "hours", (0.0, 24.0), "PARTIALLY_CALIBRATED", "EXISTING_PROJECT_ASSUMPTION", ("models",)))
    registry.register(WhatIfParameterDefinition("pet_demand_multiplier", "PET demand multiplier", "PATIENTS_DEMAND", "NUMERIC", "x", (0.0, 5.0), "PARTIALLY_CALIBRATED", "EXISTING_PROJECT_ASSUMPTION", ("oncology_pet_spect_scenario",)))
    registry.register(WhatIfParameterDefinition("porter_fte", "Porter FTE", "STAFFING_RESOURCES", "NUMERIC", "FTE", (0.0, 200.0), "PARTIALLY_CALIBRATED", "EXISTING_PROJECT_ASSUMPTION", ("conventional_transport_authority",)))
    registry.register(WhatIfParameterDefinition("cyclotron_outage", "Cyclotron outage event", "FAILURE_RESILIENCE", "FAILURE_EVENT", None, None, "CALIBRATED", "USER_SUPPLIED", ("live_operational_state",)))
    return registry


# ---------------------------------------------------------------------------
# Combined multi-category what-if scenario (sections 61-72, 122-154)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActiveChange:
    """Section 122/147: ONE unified active-change record -- spatial AND
    parameter changes coexist in the same ordered list."""

    change_id: str
    category: WhatIfCategory
    kind: Literal["SPATIAL", "PARAMETER"]
    description: str
    locked_value: object
    what_if_value: object
    timestamp: str
    status: Literal["ACTIVE"] = "ACTIVE"
    spatial_changeset: csa.SpatialChangeSet | None = None
    parameter_id: str | None = None


@dataclass
class UnifiedWhatIfScenario:
    """Section 71/145: ONE combined ordered scenario -- categories are
    organizational only, never separate simulations (section 71)."""

    scenario_id: str
    base_locked_state_id: str
    locked: csa.LockedSpatialState
    what_if: csa.WhatIfSpatialState
    active_changes: list[ActiveChange] = field(default_factory=list)

    def category_counts(self) -> dict[WhatIfCategory, int]:
        """Section 123/146: category-count summary for the future workspace."""
        counts = {c: 0 for c in WHAT_IF_CATEGORIES}
        for change in self.active_changes:
            counts[change.category] += 1
        return counts

    def active_change_list(self) -> tuple[ActiveChange, ...]:
        """Section 147: ordered active-change list."""
        return tuple(self.active_changes)


def branch_what_if_scenario(*, locked: csa.LockedSpatialState, base_locked_state_id: str, scenario_id: str | None = None) -> UnifiedWhatIfScenario:
    """Section 151: independent scenario branch from the SAME locked state --
    reuses `WhatIfSpatialState.branch_from` verbatim; two scenario branches
    never share mutable state (each clones its own registry dict)."""
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    return UnifiedWhatIfScenario(scenario_id=scenario_id or f"SCENARIO-{uuid.uuid4().hex[:12]}", base_locked_state_id=base_locked_state_id, locked=locked, what_if=what_if)


def record_spatial_change(scenario: UnifiedWhatIfScenario, *, category: WhatIfCategory, changeset: csa.SpatialChangeSet, description: str) -> ActiveChange:
    change = ActiveChange(
        change_id=changeset.change_id, category=category, kind="SPATIAL", description=description,
        locked_value=changeset.previous_object, what_if_value=changeset.new_object,
        timestamp=datetime.now(timezone.utc).isoformat(), spatial_changeset=changeset,
    )
    scenario.active_changes.append(change)
    return change


def record_parameter_change(
    scenario: UnifiedWhatIfScenario, *, category: WhatIfCategory, parameter_id: str, locked_value: object, what_if_value: object, description: str,
) -> ActiveChange:
    change = ActiveChange(
        change_id=f"PARAM-{uuid.uuid4().hex[:12]}", category=category, kind="PARAMETER", description=description,
        locked_value=locked_value, what_if_value=what_if_value, timestamp=datetime.now(timezone.utc).isoformat(), parameter_id=parameter_id,
    )
    scenario.active_changes.append(change)
    return change


def _rebuild_from_changes(scenario: UnifiedWhatIfScenario, changes: Sequence[ActiveChange]) -> None:
    """Replay-based reset (sections 124-126, 148-150): the cleanest way to
    selectively remove ONE category/change while preserving others is to
    fully reset to locked, then REPLAY the remaining spatial changesets in
    original order via the existing `apply_changeset` authority -- never a
    bespoke selective-undo stack."""
    scenario.what_if.reset_to_locked()
    for change in changes:
        if change.kind == "SPATIAL" and change.spatial_changeset is not None:
            cs = change.spatial_changeset
            csa.apply_changeset(scenario.what_if, change_id=cs.change_id, operation=cs.operation, object_id=cs.object_id, new_object=cs.new_object, note=cs.note)
    scenario.active_changes = list(changes)


def reset_what_if_category(scenario: UnifiedWhatIfScenario, category: WhatIfCategory) -> None:
    """Section 124/149: removes ONE category's changes, preserves all
    others, never mutates locked state."""
    remaining = [c for c in scenario.active_changes if c.category != category]
    _rebuild_from_changes(scenario, remaining)


def remove_one_change(scenario: UnifiedWhatIfScenario, change_id: str) -> None:
    """Section 126/148: removes exactly one change, preserves all others."""
    remaining = [c for c in scenario.active_changes if c.change_id != change_id]
    _rebuild_from_changes(scenario, remaining)


def return_scenario_to_locked(scenario: UnifiedWhatIfScenario) -> None:
    """Section 125/150/181: removes ALL active changes across ALL
    categories -- locked state was never mutated."""
    scenario.what_if.reset_to_locked()
    scenario.active_changes = []


# ---------------------------------------------------------------------------
# Scenario validation (sections 127-130)
# ---------------------------------------------------------------------------

ScenarioStatus = Literal["VALID", "VALID_WITH_UNCALIBRATED_DEPENDENCIES", "PENDING_ENGINEERING_RECALCULATION", "INFEASIBLE", "INVALID"]


@dataclass(frozen=True)
class ScenarioValidationResult:
    status: ScenarioStatus
    issues: tuple[str, ...]
    uncalibrated_dependencies: tuple[str, ...]


def validate_what_if_scenario(scenario: UnifiedWhatIfScenario, *, parameter_registry: WhatIfParameterRegistry | None = None) -> ScenarioValidationResult:
    """Section 127-129: validates the COMBINED scenario as a whole -- never
    partially evaluates an invalid scenario as though valid."""
    spatial_issues = csa.validate_spatial_registry(scenario.what_if.registry)
    if spatial_issues:
        return ScenarioValidationResult(status="INVALID", issues=tuple(f"{i.issue_type}: {i.detail}" for i in spatial_issues), uncalibrated_dependencies=())

    registry = parameter_registry or build_default_parameter_registry()
    uncalibrated = []
    for change in scenario.active_changes:
        if change.kind == "PARAMETER" and change.parameter_id:
            definition = registry.resolve(change.parameter_id)
            if definition is None:
                return ScenarioValidationResult(status="INVALID", issues=(f"unknown parameter_id {change.parameter_id!r}",), uncalibrated_dependencies=())
            if definition.calibration_status == "NOT_CALIBRATED":
                uncalibrated.append(change.parameter_id)

    if uncalibrated:
        return ScenarioValidationResult(status="VALID_WITH_UNCALIBRATED_DEPENDENCIES", issues=(), uncalibrated_dependencies=tuple(uncalibrated))
    return ScenarioValidationResult(status="VALID", issues=(), uncalibrated_dependencies=())


# ---------------------------------------------------------------------------
# Financial / physical impact contracts (sections 79-81, 130, 152-153)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImpactMetricRow:
    metric: str
    locked_value: object
    what_if_value: object
    delta: object
    status: DependencyResolutionStatus


def build_financial_impact_contract(scenario: UnifiedWhatIfScenario) -> tuple[ImpactMetricRow, ...]:
    """Section 79: reuses the EXISTING economic authority -- never a second
    finance engine. Only genuinely resolved deterministic spatial counts are
    RESOLVED; CapEx/OPEX/NPV are honestly PENDING unless the caller supplies
    an already-computed engineering result."""
    delta = csa.compute_delta(scenario.locked, scenario.what_if)
    return (
        ImpactMetricRow("locked_capex", "PENDING_ENGINEERING_RECALCULATION", None, None, "PENDING_ENGINEERING_RECALCULATION"),
        ImpactMetricRow("what_if_capex", None, "PENDING_ENGINEERING_RECALCULATION", None, "PENDING_ENGINEERING_RECALCULATION"),
        ImpactMetricRow("delta_capex", None, None, "PENDING_ENGINEERING_RECALCULATION", "PENDING_ENGINEERING_RECALCULATION"),
        ImpactMetricRow("locked_annual_opex", "PENDING_ENGINEERING_RECALCULATION", None, None, "PENDING_ENGINEERING_RECALCULATION"),
        ImpactMetricRow("what_if_annual_opex", None, "PENDING_ENGINEERING_RECALCULATION", None, "PENDING_ENGINEERING_RECALCULATION"),
        ImpactMetricRow("delta_annual_opex", None, None, "PENDING_ENGINEERING_RECALCULATION", "PENDING_ENGINEERING_RECALCULATION"),
        ImpactMetricRow("npv_lifecycle_metric_delta", None, None, "PENDING_ENGINEERING_RECALCULATION", "PENDING_ENGINEERING_RECALCULATION"),
        ImpactMetricRow("object_count_delta", len(scenario.locked.registry.objects), len(scenario.what_if.registry.objects), len(delta.added_object_ids) - len(delta.removed_object_ids), "RESOLVED"),
    )


def compare_what_if_scenarios(locked: csa.LockedSpatialState, scenarios: Mapping[str, UnifiedWhatIfScenario]) -> tuple[str, ...]:
    """Section 152-153: comparison FOUNDATION only (table structure), never
    the final comparison UI."""
    header = ("metric",) + tuple(scenarios.keys())
    return header


# ---------------------------------------------------------------------------
# Speed feasibility + sweep + locked-vs-what-if comparison (sections 88-96,
# 139-144)
# ---------------------------------------------------------------------------

SpeedFeasibilityStatus = Literal["FEASIBLE", "INFEASIBLE", "NOT_CALIBRATED"]


def evaluate_speed_feasibility(*, kinematics: CarrierKinematicsSpec) -> SpeedFeasibilityStatus:
    """Section 95-96: NEVER fabricates a maximum speed. A speed is only
    FEASIBLE if the transport-time chain resolves (i.e. the route is long
    enough to reach the target speed given the calibrated acceleration);
    otherwise INFEASIBLE (a real physical contradiction, e.g. the route is
    too short) or NOT_CALIBRATED (inputs missing)."""
    if kinematics.route_length_m == "NOT_CALIBRATED" or kinematics.acceleration_m_per_s2 == "NOT_CALIBRATED":
        return "NOT_CALIBRATED"
    time_result = compute_transport_time(kinematics)
    if time_result.total_time_s == "NOT_CALIBRATED":
        return "INFEASIBLE"
    return "FEASIBLE"


@dataclass(frozen=True)
class SpeedSweepRow:
    speed_m_per_s: float
    feasibility: SpeedFeasibilityStatus
    transport_time_s: float | Literal["NOT_CALIBRATED"]
    drag_power_w: float | Literal["NOT_CALIBRATED"]
    acceleration_energy_j: float | Literal["NOT_CALIBRATED"]


def sweep_speeds(
    *, speeds: Sequence[float], kinematics_template: CarrierKinematicsSpec, drag_spec: DragSpec, gas_density_kg_m3: float | Literal["NOT_CALIBRATED"],
) -> tuple[SpeedSweepRow, ...]:
    """Section 4/89: evaluates the SAME dependency chain at each requested
    speed -- never a linear extrapolation from one calibrated point."""
    rows = []
    for speed in speeds:
        kinematics = replace(kinematics_template, target_speed_m_per_s=speed)
        feasibility = evaluate_speed_feasibility(kinematics=kinematics)
        time_result = compute_transport_time(kinematics)
        force = compute_drag_force_n(spec=drag_spec, gas_density_kg_m3=gas_density_kg_m3, speed_m_per_s=speed)
        power = compute_drag_power_w(drag_force_n=force, speed_m_per_s=speed)
        accel_energy = compute_acceleration_energy_j(kinematics)
        rows.append(SpeedSweepRow(speed_m_per_s=speed, feasibility=feasibility, transport_time_s=time_result.total_time_s, drag_power_w=power, acceleration_energy_j=accel_energy))
    return tuple(rows)


@dataclass(frozen=True)
class SpeedWhatIfComparisonRow:
    metric: str
    locked_value: float | Literal["NOT_CALIBRATED"]
    what_if_value: float | Literal["NOT_CALIBRATED"]
    status: DependencyResolutionStatus


def compare_speed_what_if(
    *, locked_speed_m_per_s: float, what_if_speed_m_per_s: float, kinematics_template: CarrierKinematicsSpec, drag_spec: DragSpec, gas_density_kg_m3: float | Literal["NOT_CALIBRATED"],
) -> tuple[SpeedWhatIfComparisonRow, ...]:
    """Section 5/143-144: the mandatory 10 m/s (locked) -> 15 m/s (what-if)
    structured, nonlinear comparison. Never assumes energy scales linearly
    with speed."""
    rows_by_speed = {r.speed_m_per_s: r for r in sweep_speeds(speeds=(locked_speed_m_per_s, what_if_speed_m_per_s), kinematics_template=kinematics_template, drag_spec=drag_spec, gas_density_kg_m3=gas_density_kg_m3)}
    locked_row = rows_by_speed[locked_speed_m_per_s]
    what_if_row = rows_by_speed[what_if_speed_m_per_s]

    def _status(a: object, b: object) -> DependencyResolutionStatus:
        if what_if_row.feasibility == "INFEASIBLE":
            return "INFEASIBLE"
        if a == "NOT_CALIBRATED" or b == "NOT_CALIBRATED":
            return "NOT_CALIBRATED"
        return "RESOLVED"

    return (
        SpeedWhatIfComparisonRow("transport_time_s", locked_row.transport_time_s, what_if_row.transport_time_s, _status(locked_row.transport_time_s, what_if_row.transport_time_s)),
        SpeedWhatIfComparisonRow("drag_power_w", locked_row.drag_power_w, what_if_row.drag_power_w, _status(locked_row.drag_power_w, what_if_row.drag_power_w)),
        SpeedWhatIfComparisonRow("acceleration_energy_j", locked_row.acceleration_energy_j, what_if_row.acceleration_energy_j, _status(locked_row.acceleration_energy_j, what_if_row.acceleration_energy_j)),
    )


# ---------------------------------------------------------------------------
# Auxiliary canonical object types for future spatial binding (sections
# 97-100) -- lightweight identifiers only, NEVER full 3D geometry here.
# ---------------------------------------------------------------------------

AuxiliaryObjectType = Literal[
    "MRT_POWER_ELECTRONICS", "MRT_COOLING_SYSTEM", "MRT_VACUUM_SYSTEM", "MRT_CONTROL_SYSTEM",
    "MRT_SENSOR_SYSTEM", "MRT_COMMUNICATION_SYSTEM", "AGV_CHARGING_SYSTEM", "PTS_BLOWER_OR_COMPRESSOR",
    "SITE_POWER_INTERFACE",
]


# ---------------------------------------------------------------------------
# Auxiliary zones -- shared-subsystem grouping (sections 112-115)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuxiliaryZone:
    """Section 112-115: ONE shared cooling/power/vacuum/sensor plant may
    serve MULTIPLE segments/branches -- never multiplied per-segment."""

    zone_id: str
    zone_type: Literal["COOLING_ZONE", "POWER_ZONE", "VACUUM_ZONE", "SENSOR_ZONE"]
    served_segment_ids: tuple[str, ...]
    shared_electrical_load_w: float | Literal["NOT_CALIBRATED"]


# ---------------------------------------------------------------------------
# Retrofit/greenfield semantics (sections 101-102)
# ---------------------------------------------------------------------------

DevelopmentContext = Literal["RETROFIT", "GREENFIELD"]


@dataclass(frozen=True)
class AuxiliaryInfrastructureProvisioning:
    """Section 101-102: retrofit may reuse existing site capacity; greenfield
    may require new provisioning -- never double-counted."""

    development_context: DevelopmentContext
    existing_capacity_sufficient: bool | Literal["NOT_CALIBRATED"]
    new_capex_required_usd: float | Literal["NOT_CALIBRATED"]


def evaluate_auxiliary_provisioning(*, context: DevelopmentContext, adequacy: SitePowerAdequacyResult) -> AuxiliaryInfrastructureProvisioning:
    if context == "RETROFIT" and adequacy.status == "ADEQUATE":
        return AuxiliaryInfrastructureProvisioning(development_context=context, existing_capacity_sufficient=True, new_capex_required_usd=0.0)
    if adequacy.status == "NOT_CALIBRATED":
        return AuxiliaryInfrastructureProvisioning(development_context=context, existing_capacity_sufficient="NOT_CALIBRATED", new_capex_required_usd="NOT_CALIBRATED")
    return AuxiliaryInfrastructureProvisioning(development_context=context, existing_capacity_sufficient=False, new_capex_required_usd=adequacy.incremental_backup_capex_usd)


# ============================================================================
# CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE (sections 163-170)
#
# TEST-ONLY FIXTURE. These values are illustrative CONTROLLED_ENGINEERING_
# ASSUMPTIONS / CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE constants chosen to
# exercise the full resistive-electrical -> thermal -> cooling -> vacuum ->
# concurrency chain end-to-end at 5/10/15 m/s. They are NEVER production
# defaults and must NEVER be imported by production code paths.
# ============================================================================

CONTROLLED_TEST_CONDUCTOR = ConductorSpec(material="copper", resistivity_ohm_m=1.68e-8, length_m=500.0, cross_sectional_area_m2=0.0002, provenance="CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE")
CONTROLLED_TEST_DRAG_SPEC = DragSpec(frontal_area_m2=1.0, drag_coefficient=0.8)
CONTROLLED_TEST_KINEMATICS = CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=10.0, acceleration_m_per_s2=1.0, route_length_m=500.0)
CONTROLLED_TEST_ATMOSPHERIC_ENV = TransportEnvironmentSpec(environment="ATMOSPHERIC")
CONTROLLED_TEST_VACUUM_ENV = TransportEnvironmentSpec(environment="VACUUM", chamber_pressure_pa=100.0)
CONTROLLED_TEST_POWER_ELECTRONICS = PowerElectronicsSpec(efficiency_fraction=0.95, standby_loss_w=50.0, provenance="CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE")
CONTROLLED_TEST_FORCED_AIR = ForcedAirCoolingSpec(heat_rejection_w="NOT_CALIBRATED", inlet_temp_c=22.0, outlet_temp_c=35.0, air_density_kg_m3=1.2, specific_heat_j_per_kg_k=1005.0, pressure_drop_pa=150.0, fan_efficiency_fraction=0.6)
CONTROLLED_TEST_VACUUM_SYSTEM = VacuumSystemSpec(conduit_volume_m3=50.0, target_pressure_pa=100.0, leakage_rate_pa_m3_per_s=0.01, pump_down_time_s=600.0, pump_efficiency_fraction=0.6, holding_power_w=200.0)


@dataclass(frozen=True)
class ControlledAuxiliaryPhysicsTestCaseRow:
    speed_m_per_s: float
    resistance_ohm: float | Literal["NOT_CALIBRATED"]
    joule_loss_w: float | Literal["NOT_CALIBRATED"]
    power_electronics_loss_w: float | Literal["NOT_CALIBRATED"]
    thermal_load_w: float | Literal["NOT_CALIBRATED"]
    drag_power_atmospheric_w: float | Literal["NOT_CALIBRATED"]
    drag_power_vacuum_w: float | Literal["NOT_CALIBRATED"]
    vacuum_pump_down_energy_j: float | Literal["NOT_CALIBRATED"]
    transport_time_s: float | Literal["NOT_CALIBRATED"]


def build_controlled_auxiliary_physics_test_case(*, rms_current_a: float = 200.0, speeds: Sequence[float] = (5.0, 10.0, 15.0)) -> tuple[ControlledAuxiliaryPhysicsTestCaseRow, ...]:
    """Section 163-170: exercises the COMPLETE chain end-to-end at 5/10/15
    m/s -- clearly a TEST fixture, never a production default. Speed feeds
    BOTH the drag calculation AND the kinematics -- the required nonlinear
    dependency is demonstrated by `drag_power` scaling with v^3
    (per section 20's F=0.5*rho*Cd*A*v^2, P=F*v)."""
    resistance = compute_conductor_resistance_ohm(CONTROLLED_TEST_CONDUCTOR)
    joule = compute_joule_loss_w(rms_current_a=rms_current_a, resistance_ohm=resistance)
    pe_loss = compute_power_electronics_loss_w(input_power_w=10_000.0, spec=CONTROLLED_TEST_POWER_ELECTRONICS)
    em_losses = ElectromagneticLossBreakdown(joule_loss_w=joule)
    thermal = compute_thermal_load(electromagnetic_losses=em_losses, power_electronics_loss_w=pe_loss)
    atm_density = resolve_gas_density_kg_m3(CONTROLLED_TEST_ATMOSPHERIC_ENV)
    vac_density = resolve_gas_density_kg_m3(CONTROLLED_TEST_VACUUM_ENV)
    vacuum_energy = compute_vacuum_energy(CONTROLLED_TEST_VACUUM_SYSTEM)

    rows = []
    for speed in speeds:
        kinematics = replace(CONTROLLED_TEST_KINEMATICS, target_speed_m_per_s=speed)
        time_result = compute_transport_time(kinematics)
        atm_force = compute_drag_force_n(spec=CONTROLLED_TEST_DRAG_SPEC, gas_density_kg_m3=atm_density, speed_m_per_s=speed)
        atm_power = compute_drag_power_w(drag_force_n=atm_force, speed_m_per_s=speed)
        vac_force = compute_drag_force_n(spec=CONTROLLED_TEST_DRAG_SPEC, gas_density_kg_m3=vac_density, speed_m_per_s=speed)
        vac_power = compute_drag_power_w(drag_force_n=vac_force, speed_m_per_s=speed)
        rows.append(ControlledAuxiliaryPhysicsTestCaseRow(
            speed_m_per_s=speed, resistance_ohm=resistance, joule_loss_w=joule, power_electronics_loss_w=pe_loss,
            thermal_load_w=thermal.heat_generated_w, drag_power_atmospheric_w=atm_power, drag_power_vacuum_w=vac_power,
            vacuum_pump_down_energy_j=vacuum_energy.pump_down_energy_j, transport_time_s=time_result.total_time_s,
        ))
    return tuple(rows)


# ---------------------------------------------------------------------------
# Serialization / versioning (sections 155-156)
# ---------------------------------------------------------------------------


def serialize_engineering_calibration_record(record: EngineeringCalibrationRecord) -> dict:
    return {
        "schema_version": AUXILIARY_SCHEMA_VERSION, "parameter": record.parameter, "value": record.value, "unit": record.unit,
        "source": record.source, "status": record.status, "confidence": record.confidence,
        "effective_version": record.effective_version, "notes": record.notes,
    }


# ============================================================================
# CLOSURE BUILD: mission-specific service-class speed-mix energy integration
# (sections 37-41, 70-75 of the "MRT Multi-Stream Service Classes" closure).
#
# GOVERNANCE: this is an ADDITION to the existing auxiliary authority --
# never a second electrical/thermal model. `mrt_service_class_authority.py`
# builds `ServiceClassMissionGroup` inputs from its own mission objects and
# calls the function below; this module never imports
# `mrt_service_class_authority` (avoids a circular dependency, keeps this
# module the single physics owner).
# ============================================================================


@dataclass(frozen=True)
class ServiceClassMissionGroup:
    """Section 38/70: one (service_class, effective_speed) bucket -- missions
    are grouped by their ACTUAL effective speed, never collapsed to a single
    mean speed before physics (section 70)."""

    service_class: str
    mission_count: int
    effective_speed_m_per_s: float | Literal["NOT_CALIBRATED"]
    route_length_m: float | Literal["NOT_CALIBRATED"]


@dataclass(frozen=True)
class ServiceClassSpeedMixEntry:
    service_class: str
    mission_count: int
    effective_speed_m_per_s: float | Literal["NOT_CALIBRATED"]
    route_length_m: float | Literal["NOT_CALIBRATED"]
    transport_time_s: float | Literal["NOT_CALIBRATED"]
    drag_power_w: float | Literal["NOT_CALIBRATED"]
    energy_resolution_status: DependencyResolutionStatus
    thermal_resolution_status: DependencyResolutionStatus
    cooling_resolution_status: DependencyResolutionStatus
    annual_opex_resolution_status: DependencyResolutionStatus


@dataclass(frozen=True)
class SpeedMixAggregateResult:
    entries: tuple[ServiceClassSpeedMixEntry, ...]
    missions_by_service_class: Mapping[str, int]
    missions_by_effective_speed: Mapping[float, int]
    energy_resolution_status: DependencyResolutionStatus
    thermal_resolution_status: DependencyResolutionStatus
    cooling_resolution_status: DependencyResolutionStatus
    annual_opex_resolution_status: DependencyResolutionStatus


def aggregate_service_class_speed_mix(
    groups: Sequence[ServiceClassMissionGroup], *, drag_spec: DragSpec, gas_density_kg_m3: float | Literal["NOT_CALIBRATED"] = 1.225,
) -> SpeedMixAggregateResult:
    """Section 38-41/70-75: evaluates `n_i` missions at their OWN effective
    speed per service class -- never `total_missions * one_universal_speed`
    (section 38/71). Thermal/cooling/OPEX remain NOT_CALIBRATED until the
    caller supplies genuinely calibrated electrical-loss/cooling-architecture
    inputs (never fabricated here, section 40/72). Shared infrastructure
    (controls/cooling plant/vacuum/power conversion/comms) is NOT multiplied
    per service class -- this function only reports PER-CLASS drag/transport
    physics, which is legitimately mission-specific; shared subsystems are
    composed exactly once elsewhere (section 74)."""
    entries = []
    missions_by_class: dict[str, int] = {}
    missions_by_speed: dict[float, int] = {}
    any_energy_calibrated = False
    for g in groups:
        missions_by_class[g.service_class] = missions_by_class.get(g.service_class, 0) + g.mission_count
        if g.effective_speed_m_per_s != "NOT_CALIBRATED":
            missions_by_speed[g.effective_speed_m_per_s] = missions_by_speed.get(g.effective_speed_m_per_s, 0) + g.mission_count

        if g.effective_speed_m_per_s == "NOT_CALIBRATED" or g.route_length_m == "NOT_CALIBRATED":
            entries.append(ServiceClassSpeedMixEntry(
                service_class=g.service_class, mission_count=g.mission_count, effective_speed_m_per_s=g.effective_speed_m_per_s,
                route_length_m=g.route_length_m, transport_time_s="NOT_CALIBRATED", drag_power_w="NOT_CALIBRATED",
                energy_resolution_status="NOT_CALIBRATED", thermal_resolution_status="NOT_CALIBRATED",
                cooling_resolution_status="NOT_CALIBRATED", annual_opex_resolution_status="NOT_CALIBRATED",
            ))
            continue

        transport_time_s = float(g.route_length_m) / float(g.effective_speed_m_per_s)  # type: ignore[arg-type]
        force = compute_drag_force_n(spec=drag_spec, gas_density_kg_m3=gas_density_kg_m3, speed_m_per_s=g.effective_speed_m_per_s)
        power = compute_drag_power_w(drag_force_n=force, speed_m_per_s=g.effective_speed_m_per_s)
        energy_status: DependencyResolutionStatus = "RESOLVED" if power != "NOT_CALIBRATED" else "NOT_CALIBRATED"
        any_energy_calibrated = any_energy_calibrated or energy_status == "RESOLVED"
        entries.append(ServiceClassSpeedMixEntry(
            service_class=g.service_class, mission_count=g.mission_count, effective_speed_m_per_s=g.effective_speed_m_per_s,
            route_length_m=g.route_length_m, transport_time_s=transport_time_s, drag_power_w=power,
            energy_resolution_status=energy_status, thermal_resolution_status="PENDING_ENGINEERING_RECALCULATION",
            cooling_resolution_status="PENDING_ENGINEERING_RECALCULATION", annual_opex_resolution_status="PENDING_ENGINEERING_RECALCULATION",
        ))

    overall_energy: DependencyResolutionStatus = "RESOLVED" if any_energy_calibrated else "NOT_CALIBRATED"
    return SpeedMixAggregateResult(
        entries=tuple(entries), missions_by_service_class=missions_by_class, missions_by_effective_speed=missions_by_speed,
        energy_resolution_status=overall_energy, thermal_resolution_status="PENDING_ENGINEERING_RECALCULATION",
        cooling_resolution_status="PENDING_ENGINEERING_RECALCULATION", annual_opex_resolution_status="PENDING_ENGINEERING_RECALCULATION",
    )

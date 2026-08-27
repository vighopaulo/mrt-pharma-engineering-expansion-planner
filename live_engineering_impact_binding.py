"""Live Engineering Impact Binding + Unified What-If Recalculation Graph.

GOVERNANCE: this module is an ORCHESTRATION layer only. It creates NO second
physics engine, NO second scheduler, NO second spatial engine, NO second
what-if engine, and NO second finance/NPV engine. Every calculation is
delegated to an EXISTING authority:

    spatial changes          -> canonical_spatial_authority
    equipment/economic deltas-> canonical_spatial_authority
                                (compute_mrt_transport_only_capex,
                                 compute_segment_length_capex_delta,
                                 compute_vestibule_count_capex_delta)
    what-if scenario/registry-> mrt_auxiliary_systems_authority
                                (UnifiedWhatIfScenario, WhatIfParameterRegistry,
                                 validate_what_if_scenario, reset_what_if_category,
                                 remove_one_change, return_scenario_to_locked,
                                 branch_what_if_scenario)
    resistive/thermal/cooling/
    vacuum/site-power/energy -> mrt_auxiliary_systems_authority
    service-class/priority/
    scheduling/decay/carrier -> mrt_service_class_authority
                                (which itself reuses
                                 shared_mrt_multistream_authority and
                                 multi_isotope_decay)
    cyclotron catalog        -> cyclotron_catalog
    lifecycle economics/NPV  -> lifecycle_economics (referenced, NEVER
                                reimplemented; this module reports
                                PENDING_ENGINEERING_RECALCULATION for NPV/NPC
                                whenever the required upstream demand/capacity/
                                revenue inputs are not supplied by the caller)

The governing chain (section 0):

    WHAT-IF INPUT -> VALIDATION -> CANONICAL WHAT-IF STATE ->
    DEPENDENCY RESOLUTION -> AUTHORITATIVE ENGINEERING RECALCULATION ->
    SCHEDULING/OPERATIONS RECALCULATION -> AUXILIARY/ENERGY/THERMAL
    RECALCULATION -> ECONOMIC RECALCULATION -> UNIFIED IMPACT RESULT ->
    FUTURE DASHBOARD/3D PRESENTATION.

NO FALSE REAL-TIME CLAIM (section 24): "live" means synchronous recalculation
immediately after a submitted what-if change -- NOT live hospital telemetry,
NOT a live vendor API, NOT real-time PLC control.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal, Mapping, Sequence

import canonical_spatial_authority as csa
import mrt_auxiliary_systems_authority as maux
import mrt_service_class_authority as msc

LIVE_BINDING_SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Section 9: explicit result status vocabulary
# ---------------------------------------------------------------------------

ImpactStatus = Literal[
    "RESOLVED", "NOT_CALIBRATED", "PENDING_ENGINEERING_RECALCULATION", "NOT_APPLICABLE",
    "INFEASIBLE", "BLOCKED", "INVALID", "UNCHANGED",
]

ImpactScope = Literal[
    "SPATIAL", "FACILITY_EQUIPMENT", "TRANSPORT_MRT", "TRANSPORT_CONVENTIONAL", "SERVICE_CLASS",
    "PRODUCTION", "CLINICAL_OPERATIONS", "AUXILIARY_SYSTEMS", "ECONOMICS", "FULL_SCENARIO",
]

MetricGroup = Literal[
    "SPATIAL", "PHYSICAL", "THERMAL", "ELECTRICAL", "PRODUCTION", "CLINICAL", "TRANSPORT",
    "STAFFING", "SITE_POWER", "CAPEX", "OPEX", "LIFECYCLE_ECONOMICS",
]


# ---------------------------------------------------------------------------
# Section 150: structured error contract
# ---------------------------------------------------------------------------


class LiveImpactError(Exception):
    """Base class for all live-impact-binding errors."""


class InvalidParameterError(LiveImpactError):
    pass


class InvalidObjectError(LiveImpactError):
    pass


class InvalidServiceClassError(LiveImpactError):
    pass


class InvalidMissionError(LiveImpactError):
    pass


class InvalidUnitError(LiveImpactError):
    pass


class InvalidScenarioError(LiveImpactError):
    pass


class UnresolvedConnectionPolicyError(LiveImpactError):
    pass


class CalibrationRequiredError(LiveImpactError):
    pass


class InfeasibleScenarioError(LiveImpactError):
    pass


class StaleRevisionError(LiveImpactError):
    pass


def _reject_non_finite(value: object, *, name: str) -> None:
    """Section 107: NaN/+-Infinity must never enter a published snapshot."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(value) or math.isinf(value):
            raise InvalidParameterError(f"{name} must be finite, got {value!r}")


# ---------------------------------------------------------------------------
# Section 121: ONE common impact-metric representation (never a different
# incompatible structure per subsystem).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImpactMetric:
    metric_id: str
    display_name: str
    locked_value: object
    what_if_value: object
    absolute_delta: object
    percent_delta: object
    unit: str | None
    status: ImpactStatus
    source_authority: str
    provenance: str
    calibration_status: str
    group: MetricGroup
    note: str = ""


def build_impact_metric(
    *, metric_id: str, display_name: str, locked_value: object, what_if_value: object, unit: str | None,
    source_authority: str, provenance: str, calibration_status: str, group: MetricGroup, note: str = "",
) -> ImpactMetric:
    """Section 81/121: computes absolute/percent delta safely -- handles a
    locked value of zero without fabricating a percentage, and never
    computes a delta across an unresolved (NOT_CALIBRATED/etc.) value."""
    for v, n in ((locked_value, "locked_value"), (what_if_value, "what_if_value")):
        _reject_non_finite(v, name=f"{metric_id}.{n}")

    unresolved_markers = ("NOT_CALIBRATED", "PENDING_ENGINEERING_RECALCULATION", "NOT_APPLICABLE", "INFEASIBLE", "BLOCKED")
    if locked_value in unresolved_markers or what_if_value in unresolved_markers:
        status: ImpactStatus = what_if_value if what_if_value in unresolved_markers else locked_value  # type: ignore[assignment]
        return ImpactMetric(
            metric_id=metric_id, display_name=display_name, locked_value=locked_value, what_if_value=what_if_value,
            absolute_delta=status, percent_delta=status, unit=unit, status=status, source_authority=source_authority,
            provenance=provenance, calibration_status=calibration_status, group=group, note=note,
        )

    if isinstance(locked_value, (int, float)) and isinstance(what_if_value, (int, float)) and not isinstance(locked_value, bool):
        absolute_delta = float(what_if_value) - float(locked_value)
        percent_delta = (absolute_delta / float(locked_value) * 100.0) if locked_value != 0 else None
        status = "UNCHANGED" if absolute_delta == 0.0 else "RESOLVED"
        return ImpactMetric(
            metric_id=metric_id, display_name=display_name, locked_value=locked_value, what_if_value=what_if_value,
            absolute_delta=absolute_delta, percent_delta=percent_delta, unit=unit, status=status,
            source_authority=source_authority, provenance=provenance, calibration_status=calibration_status, group=group, note=note,
        )

    # non-numeric (identity) comparison -- e.g. service_class_id, color, container_class
    status = "UNCHANGED" if locked_value == what_if_value else "RESOLVED"
    return ImpactMetric(
        metric_id=metric_id, display_name=display_name, locked_value=locked_value, what_if_value=what_if_value,
        absolute_delta=None, percent_delta=None, unit=unit, status=status, source_authority=source_authority,
        provenance=provenance, calibration_status=calibration_status, group=group, note=note,
    )


# ---------------------------------------------------------------------------
# Section 7-8: request/result contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LiveImpactRequest:
    scenario_id: str
    base_locked_state_id: str
    requested_scope: tuple[ImpactScope, ...]
    project_id: str | None = None
    study_id: str | None = None
    change_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class ImpactTraceNode:
    """Section 12-13/95/118: one dependency-graph node -- the ORDERED
    engineering causality chain, never a flat list of unrelated callbacks."""

    dependency_node: str
    input_summary: str
    output_summary: str
    status: ImpactStatus
    owning_authority: str


@dataclass(frozen=True)
class ObjectLevelImpact:
    object_id: str
    object_type: str
    locked_value: object
    what_if_value: object
    delta: object
    status: ImpactStatus
    owning_authority: str


@dataclass(frozen=True)
class ServiceClassImpact:
    service_class: str
    mission_count: int
    effective_speed_m_per_s: object
    priority: object
    average_transport_time_s: object
    energy_contribution_w: object
    opex_contribution: object
    status: ImpactStatus


@dataclass(frozen=True)
class MissionLevelImpact:
    mission_id: str
    carrier_id: str
    service_class: str
    locked_speed_m_per_s: object
    what_if_speed_m_per_s: object
    wait_delta_minutes: object
    transport_time_delta_minutes: object
    trajectory_revision: int
    status: ImpactStatus


@dataclass(frozen=True)
class LiveEngineeringImpactTiming:
    """Section 91: measured recalculation duration -- never claimed as
    enterprise real-time performance from tiny controlled fixtures."""

    validation_seconds: float
    engineering_recalculation_seconds: float
    economic_reconciliation_seconds: float
    total_seconds: float


@dataclass(frozen=True)
class LiveEngineeringImpactResult:
    scenario_id: str
    locked_state_id: str
    revision: int
    validation_status: Literal["VALID", "INVALID", "VALID_WITH_UNCALIBRATED_DEPENDENCIES"]
    metrics: tuple[ImpactMetric, ...]
    trace: tuple[ImpactTraceNode, ...]
    object_impacts: tuple[ObjectLevelImpact, ...] = ()
    service_class_impacts: tuple[ServiceClassImpact, ...] = ()
    mission_impacts: tuple[MissionLevelImpact, ...] = ()
    warnings: tuple[str, ...] = ()
    timing: LiveEngineeringImpactTiming | None = None

    def metric(self, metric_id: str) -> ImpactMetric | None:
        return next((m for m in self.metrics if m.metric_id == metric_id), None)


# ---------------------------------------------------------------------------
# Section 89-90: revision/stale-result protection (contract-level, even
# though recalculation is currently synchronous).
# ---------------------------------------------------------------------------


@dataclass
class LiveImpactPublisher:
    _last_revision: dict[str, int] = field(default_factory=dict)
    _last_result: dict[str, LiveEngineeringImpactResult] = field(default_factory=dict)

    def publish(self, result: LiveEngineeringImpactResult) -> LiveEngineeringImpactResult:
        """Section 89-90: a delayed/older revision N must never overwrite an
        already-accepted N+1."""
        last = self._last_revision.get(result.scenario_id, -1)
        if result.revision <= last:
            raise StaleRevisionError(f"revision {result.revision} is stale for scenario {result.scenario_id!r} (last accepted: {last})")
        self._last_revision[result.scenario_id] = result.revision
        self._last_result[result.scenario_id] = result
        return result

    def latest(self, scenario_id: str) -> LiveEngineeringImpactResult | None:
        return self._last_result.get(scenario_id)


# ---------------------------------------------------------------------------
# Section 25-38: the flagship service-class speed what-if binding --
# reused verbatim for nuclear/blood/linen (sections 25, 39, 40).
# ---------------------------------------------------------------------------


def compute_service_class_speed_what_if_impact(
    *, service_class: msc.MrtServiceClass, locked_speed_m_per_s: float, what_if_speed_m_per_s: float,
    route_length_m: float, environment: maux.TransportEnvironment = "ATMOSPHERIC",
    chamber_pressure_pa: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED",
    drag_spec: maux.DragSpec | None = None, half_life_minutes: float | None = None,
    operating_hours_per_year: float | None = None, electricity_cost_per_kwh: float | None = None,
    revision: int = 1,
) -> LiveEngineeringImpactResult:
    """Section 22-38: the governing chain for a mission-speed what-if --
    speed -> transport time -> scheduling -> drag -> (nuclear) decay ->
    electrical -> thermal -> cooling -> energy -> OPEX reconciliation ->
    economics (PENDING, never computed here). Every step calls an EXISTING
    authority; nothing here is a second physics/scheduler/finance engine."""
    for name, value in (("locked_speed_m_per_s", locked_speed_m_per_s), ("what_if_speed_m_per_s", what_if_speed_m_per_s), ("route_length_m", route_length_m)):
        _reject_non_finite(value, name=name)
        if value <= 0:
            raise InvalidParameterError(f"{name} must be positive, got {value!r}")
    if service_class not in msc.SERVICE_CLASS_REGISTRY:
        raise InvalidServiceClassError(f"Unknown service class: {service_class!r}")
    profile = msc.SERVICE_CLASS_REGISTRY[service_class]
    if profile.activity_status != "ACTIVE":
        raise InvalidServiceClassError(f"{service_class!r} is {profile.activity_status} -- cannot run a live speed what-if on an inactive service class")

    metrics: list[ImpactMetric] = []
    trace: list[ImpactTraceNode] = []
    warnings: list[str] = []

    locked_mission = msc.MrtServiceMission(mission_id="LOCKED", carrier_id="LIVE-IMPACT-CARRIER", service_class=service_class, route_length_m=route_length_m, start_minutes=0.0, speed_override_m_per_s=locked_speed_m_per_s)
    what_if_mission = msc.MrtServiceMission(mission_id="WHATIF", carrier_id="LIVE-IMPACT-CARRIER", service_class=service_class, route_length_m=route_length_m, start_minutes=0.0, speed_override_m_per_s=what_if_speed_m_per_s)

    # --- Section 26: identity invariants (service class/color/priority/container) ---
    locked_dispatch = msc.build_carrier_dispatch_state(locked_mission)
    what_if_dispatch = msc.build_carrier_dispatch_state(what_if_mission)
    metrics.append(build_impact_metric(
        metric_id="service_class_identity", display_name="Service class identity", locked_value=locked_dispatch.service_class,
        what_if_value=what_if_dispatch.service_class, unit=None, source_authority="mrt_service_class_authority.build_carrier_dispatch_state",
        provenance="EXISTING_PROJECT_ASSUMPTION", calibration_status="CALIBRATED", group="TRANSPORT",
    ))
    metrics.append(build_impact_metric(
        metric_id="presentation_color", display_name="Presentation color", locked_value=locked_dispatch.effective_display_color,
        what_if_value=what_if_dispatch.effective_display_color, unit=None, source_authority="mrt_service_class_authority.build_carrier_dispatch_state",
        provenance="EXISTING_PROJECT_ASSUMPTION", calibration_status="CALIBRATED", group="TRANSPORT",
    ))
    metrics.append(build_impact_metric(
        metric_id="effective_priority", display_name="Effective priority", locked_value=locked_dispatch.effective_priority,
        what_if_value=what_if_dispatch.effective_priority, unit=None, source_authority="mrt_service_class_authority.build_carrier_dispatch_state",
        provenance="EXISTING_PROJECT_ASSUMPTION", calibration_status="CALIBRATED", group="TRANSPORT",
    ))
    metrics.append(build_impact_metric(
        metric_id="container_class", display_name="Container class", locked_value=locked_dispatch.container_class_id,
        what_if_value=what_if_dispatch.container_class_id, unit=None, source_authority="mrt_service_class_authority.build_carrier_dispatch_state",
        provenance="EXISTING_PROJECT_ASSUMPTION", calibration_status="CALIBRATED", group="TRANSPORT",
    ))
    trace.append(ImpactTraceNode("carrier_speed", f"{locked_speed_m_per_s}->{what_if_speed_m_per_s} m/s", "speed override resolved", "RESOLVED", "mrt_service_class_authority.resolve_effective_speed"))

    # --- Section 27: transport time via the existing mission-duration authority ---
    locked_duration_min = msc.compute_mission_duration_minutes(locked_mission)
    what_if_duration_min = msc.compute_mission_duration_minutes(what_if_mission)
    metrics.append(build_impact_metric(
        metric_id="transport_time_minutes", display_name="Transport time", locked_value=locked_duration_min, what_if_value=what_if_duration_min,
        unit="min", source_authority="mrt_service_class_authority.compute_mission_duration_minutes",
        provenance="USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION", calibration_status="PARTIALLY_CALIBRATED", group="TRANSPORT",
    ))
    trace.append(ImpactTraceNode("transport_time", f"route_length_m={route_length_m}", f"{locked_duration_min} -> {what_if_duration_min} min", "RESOLVED", "mrt_service_class_authority.compute_mission_duration_minutes"))

    # --- Section 28: scheduling via the EXISTING single-shared-segment scheduler ---
    locked_scheduled, locked_unresolved = msc.schedule_service_missions([locked_mission])
    what_if_scheduled, what_if_unresolved = msc.schedule_service_missions([what_if_mission])
    locked_wait = locked_scheduled[0].wait_minutes if locked_scheduled else "NOT_CALIBRATED"
    what_if_wait = what_if_scheduled[0].wait_minutes if what_if_scheduled else "NOT_CALIBRATED"
    metrics.append(build_impact_metric(
        metric_id="scheduled_wait_minutes", display_name="Scheduled wait", locked_value=locked_wait, what_if_value=what_if_wait,
        unit="min", source_authority="shared_mrt_multistream_authority.schedule_missions_on_shared_segment",
        provenance="EXISTING_PROJECT_ASSUMPTION", calibration_status="CALIBRATED", group="TRANSPORT",
    ))
    trace.append(ImpactTraceNode("scheduling", "single-mission dispatch", f"wait={what_if_wait}", "RESOLVED", "shared_mrt_multistream_authority.schedule_missions_on_shared_segment"))

    # --- Section 30-31: drag via the EXISTING pressure/vacuum-aware physics (nonlinear in v) ---
    env_spec = maux.TransportEnvironmentSpec(environment=environment, chamber_pressure_pa=chamber_pressure_pa)
    gas_density = maux.resolve_gas_density_kg_m3(env_spec)
    spec = drag_spec or maux.DragSpec(frontal_area_m2=1.0, drag_coefficient=0.8)
    locked_force = maux.compute_drag_force_n(spec=spec, gas_density_kg_m3=gas_density, speed_m_per_s=locked_speed_m_per_s)
    what_if_force = maux.compute_drag_force_n(spec=spec, gas_density_kg_m3=gas_density, speed_m_per_s=what_if_speed_m_per_s)
    locked_drag_power = maux.compute_drag_power_w(drag_force_n=locked_force, speed_m_per_s=locked_speed_m_per_s)
    what_if_drag_power = maux.compute_drag_power_w(drag_force_n=what_if_force, speed_m_per_s=what_if_speed_m_per_s)
    metrics.append(build_impact_metric(
        metric_id="drag_power_w", display_name="Aerodynamic drag power", locked_value=locked_drag_power, what_if_value=what_if_drag_power,
        unit="W", source_authority="mrt_auxiliary_systems_authority.compute_drag_power_w",
        provenance="CONTROLLED_ENGINEERING_ASSUMPTION" if gas_density != "NOT_CALIBRATED" else "NOT_CALIBRATED",
        calibration_status="PARTIALLY_CALIBRATED" if gas_density != "NOT_CALIBRATED" else "NOT_CALIBRATED", group="ELECTRICAL",
    ))
    trace.append(ImpactTraceNode("drag", f"environment={environment}", f"{locked_drag_power} -> {what_if_drag_power} W", "RESOLVED" if what_if_drag_power != "NOT_CALIBRATED" else "NOT_CALIBRATED", "mrt_auxiliary_systems_authority.compute_drag_power_w"))

    # --- Section 31: acceleration energy via the EXISTING kinematics authority ---
    locked_kinematics = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=locked_speed_m_per_s)
    what_if_kinematics = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=what_if_speed_m_per_s)
    locked_accel_energy = maux.compute_acceleration_energy_j(locked_kinematics)
    what_if_accel_energy = maux.compute_acceleration_energy_j(what_if_kinematics)
    metrics.append(build_impact_metric(
        metric_id="acceleration_energy_j", display_name="Acceleration kinetic energy", locked_value=locked_accel_energy, what_if_value=what_if_accel_energy,
        unit="J", source_authority="mrt_auxiliary_systems_authority.compute_acceleration_energy_j",
        provenance="CONTROLLED_ENGINEERING_ASSUMPTION", calibration_status="PARTIALLY_CALIBRATED", group="PHYSICAL",
    ))
    trace.append(ImpactTraceNode("acceleration_energy", "carrier_mass_kg=200.0 (controlled)", f"{locked_accel_energy} -> {what_if_accel_energy} J", "RESOLVED", "mrt_auxiliary_systems_authority.compute_acceleration_energy_j"))

    # --- Section 29/35: decay via the EXISTING decay authority -- nuclear only ---
    if service_class == "RADIOPHARMACEUTICAL_NUCLEAR" and half_life_minutes is not None:
        locked_retained = msc.compute_nuclear_retained_fraction_for_mission(locked_mission, half_life_minutes=half_life_minutes)
        what_if_retained = msc.compute_nuclear_retained_fraction_for_mission(what_if_mission, half_life_minutes=half_life_minutes)
        metrics.append(build_impact_metric(
            metric_id="retained_activity_fraction", display_name="Retained activity fraction", locked_value=locked_retained, what_if_value=what_if_retained,
            unit="fraction", source_authority="multi_isotope_decay.retained_fraction (via mrt_service_class_authority)",
            provenance="EXISTING_PROJECT_ASSUMPTION", calibration_status="CALIBRATED", group="PRODUCTION",
        ))
        trace.append(ImpactTraceNode("decay_retention", f"half_life_minutes={half_life_minutes}", f"{locked_retained} -> {what_if_retained}", "RESOLVED", "multi_isotope_decay.retained_fraction"))
    elif service_class == "RADIOPHARMACEUTICAL_NUCLEAR":
        metrics.append(build_impact_metric(
            metric_id="retained_activity_fraction", display_name="Retained activity fraction", locked_value="NOT_CALIBRATED", what_if_value="NOT_CALIBRATED",
            unit="fraction", source_authority="multi_isotope_decay.retained_fraction", provenance="NOT_CALIBRATED",
            calibration_status="NOT_CALIBRATED", group="PRODUCTION", note="half_life_minutes not supplied by caller",
        ))
        trace.append(ImpactTraceNode("decay_retention", "half_life_minutes not supplied", "NOT_CALIBRATED", "NOT_CALIBRATED", "multi_isotope_decay.retained_fraction"))
        warnings.append("Nuclear decay retention NOT_CALIBRATED: half_life_minutes was not supplied to this scenario.")
    else:
        metrics.append(build_impact_metric(
            metric_id="retained_activity_fraction", display_name="Retained activity fraction", locked_value="NOT_APPLICABLE", what_if_value="NOT_APPLICABLE",
            unit=None, source_authority="mrt_service_class_authority.general_logistics_has_no_decay_field", provenance="NOT_APPLICABLE",
            calibration_status="NOT_APPLICABLE", group="PRODUCTION", note="general logistics never acquires a fake decay field",
        ))
        trace.append(ImpactTraceNode("decay_retention", service_class, "NOT_APPLICABLE (non-nuclear service class)", "NOT_APPLICABLE", "mrt_service_class_authority.general_logistics_has_no_decay_field"))

    # --- Section 32-33: electrical/thermal load. Joule/PE losses depend on
    # resistance/current in the existing model, NOT on carrier speed, so
    # they are honestly UNCHANGED (never fabricated as speed-coupled)
    # unless the caller supplies a conductor+operating-point relationship
    # (out of scope for a pure speed what-if; not invented here). ---
    metrics.append(build_impact_metric(
        metric_id="resistive_electrical_load_w", display_name="Resistive (Joule/PE) electrical load", locked_value="NOT_CALIBRATED",
        what_if_value="NOT_CALIBRATED", unit="W", source_authority="mrt_auxiliary_systems_authority.compute_joule_loss_w",
        provenance="NOT_CALIBRATED", calibration_status="NOT_CALIBRATED", group="ELECTRICAL",
        note="Joule/power-electronics losses are not coupled to carrier speed in the existing resistive model; no conductor/operating-point spec was supplied.",
    ))
    trace.append(ImpactTraceNode("electrical_demand", "no conductor/operating-point spec supplied", "NOT_CALIBRATED", "NOT_CALIBRATED", "mrt_auxiliary_systems_authority.compute_joule_loss_w"))

    # --- Section 33-34: thermal/cooling reconcile from resolved losses only;
    # since electrical load above is NOT_CALIBRATED, thermal/cooling remain
    # PENDING (never independently invented). ---
    metrics.append(build_impact_metric(
        metric_id="thermal_load_w", display_name="Thermal load", locked_value="PENDING_ENGINEERING_RECALCULATION",
        what_if_value="PENDING_ENGINEERING_RECALCULATION", unit="W", source_authority="mrt_auxiliary_systems_authority.compute_thermal_load",
        provenance="NOT_CALIBRATED", calibration_status="NOT_CALIBRATED", group="THERMAL",
        note="Depends on the unresolved resistive electrical load above.",
    ))
    trace.append(ImpactTraceNode("thermal_load", "depends on electrical_demand", "PENDING_ENGINEERING_RECALCULATION", "PENDING_ENGINEERING_RECALCULATION", "mrt_auxiliary_systems_authority.compute_thermal_load"))
    metrics.append(build_impact_metric(
        metric_id="cooling_power_w", display_name="Cooling auxiliary power", locked_value="NOT_CALIBRATED", what_if_value="NOT_CALIBRATED",
        unit="W", source_authority="mrt_auxiliary_systems_authority.resolve_cooling_power", provenance="NOT_CALIBRATED",
        calibration_status="NOT_CALIBRATED", group="THERMAL", note="No cooling architecture/spec was supplied for this scenario.",
    ))
    trace.append(ImpactTraceNode("cooling_requirement", "no cooling architecture selected", "NOT_CALIBRATED", "NOT_CALIBRATED", "mrt_auxiliary_systems_authority.resolve_cooling_power"))

    # --- Section 36-37: annual energy/OPEX from the RESOLVED drag power (the
    # only resolved speed-dependent electrical component here), reconciled
    # against the existing legacy $/carrier/year allowance -- never stacked. ---
    if operating_hours_per_year is not None and electricity_cost_per_kwh is not None and what_if_drag_power != "NOT_CALIBRATED":
        locked_annual = maux.compute_annual_energy(average_operating_w=locked_drag_power, peak_w=locked_drag_power, operating_hours_per_year=operating_hours_per_year)
        what_if_annual = maux.compute_annual_energy(average_operating_w=what_if_drag_power, peak_w=what_if_drag_power, operating_hours_per_year=operating_hours_per_year)
        locked_opex = maux.compute_electricity_opex(annual_kwh=locked_annual.annual_kwh, electricity_cost_per_kwh=electricity_cost_per_kwh)
        what_if_opex = maux.compute_electricity_opex(annual_kwh=what_if_annual.annual_kwh, electricity_cost_per_kwh=electricity_cost_per_kwh)
        metrics.append(build_impact_metric(
            metric_id="annual_energy_kwh", display_name="Annual propulsion energy", locked_value=locked_annual.annual_kwh, what_if_value=what_if_annual.annual_kwh,
            unit="kWh", source_authority="mrt_auxiliary_systems_authority.compute_annual_energy", provenance="CONTROLLED_ENGINEERING_ASSUMPTION",
            calibration_status="PARTIALLY_CALIBRATED", group="OPEX",
        ))
        trace.append(ImpactTraceNode("annual_energy", f"operating_hours_per_year={operating_hours_per_year}", f"{locked_annual.annual_kwh} -> {what_if_annual.annual_kwh} kWh", "RESOLVED", "mrt_auxiliary_systems_authority.compute_annual_energy"))

        reconciliation = maux.reconcile_mrt_energy_with_legacy_assumption(
            physical_annual_kwh=what_if_annual.annual_kwh, physical_calibration_status="CALIBRATED_FOR_ENERGY",
            legacy_annual_opex_per_unit_usd=250.0, electricity_cost_per_kwh=electricity_cost_per_kwh,
        )
        metrics.append(build_impact_metric(
            metric_id="electricity_opex_usd", display_name="Annual electricity OPEX", locked_value=locked_opex, what_if_value=what_if_opex,
            unit="USD/year", source_authority="mrt_auxiliary_systems_authority.compute_electricity_opex", provenance="CONTROLLED_ENGINEERING_ASSUMPTION",
            calibration_status="PARTIALLY_CALIBRATED", group="OPEX",
            note=f"legacy_reconciliation={reconciliation.value_source} (REPLACES legacy $250/carrier/yr allowance, never stacked)",
        ))
        trace.append(ImpactTraceNode("electricity_opex", "reconcile_mrt_energy_with_legacy_assumption", reconciliation.value_source, "RESOLVED", "equipment_energy_opex.build_ledger_energy_component (via mrt_auxiliary_systems_authority)"))
    else:
        metrics.append(build_impact_metric(
            metric_id="annual_energy_kwh", display_name="Annual propulsion energy", locked_value="PENDING_ENGINEERING_RECALCULATION",
            what_if_value="PENDING_ENGINEERING_RECALCULATION", unit="kWh", source_authority="mrt_auxiliary_systems_authority.compute_annual_energy",
            provenance="NOT_CALIBRATED", calibration_status="NOT_CALIBRATED", group="OPEX",
            note="operating_hours_per_year/electricity_cost_per_kwh not supplied",
        ))
        trace.append(ImpactTraceNode("annual_energy", "operating_hours_per_year/electricity_cost_per_kwh not supplied", "PENDING_ENGINEERING_RECALCULATION", "PENDING_ENGINEERING_RECALCULATION", "mrt_auxiliary_systems_authority.compute_annual_energy"))
        metrics.append(build_impact_metric(
            metric_id="electricity_opex_usd", display_name="Annual electricity OPEX", locked_value="PENDING_ENGINEERING_RECALCULATION",
            what_if_value="PENDING_ENGINEERING_RECALCULATION", unit="USD/year", source_authority="mrt_auxiliary_systems_authority.compute_electricity_opex",
            provenance="NOT_CALIBRATED", calibration_status="NOT_CALIBRATED", group="OPEX",
        ))
        trace.append(ImpactTraceNode("electricity_opex", "depends on unresolved annual_energy", "PENDING_ENGINEERING_RECALCULATION", "PENDING_ENGINEERING_RECALCULATION", "mrt_auxiliary_systems_authority.compute_electricity_opex"))

    # --- Section 38: NPV/NPC -- NEVER computed here (no second finance engine) ---
    metrics.append(build_impact_metric(
        metric_id="npv_usd", display_name="Lifecycle NPV", locked_value="PENDING_ENGINEERING_RECALCULATION",
        what_if_value="PENDING_ENGINEERING_RECALCULATION", unit="USD", source_authority="lifecycle_economics.evaluate_lifecycle_economics",
        provenance="NOT_CALIBRATED", calibration_status="NOT_CALIBRATED", group="LIFECYCLE_ECONOMICS",
        note="Requires patient-demand/capacity/revenue inputs not supplied by a pure speed what-if; never computed inside the binding layer.",
    ))
    trace.append(ImpactTraceNode("lifecycle_economics", "requires demand/capacity/revenue inputs", "PENDING_ENGINEERING_RECALCULATION", "PENDING_ENGINEERING_RECALCULATION", "lifecycle_economics.evaluate_lifecycle_economics"))

    unresolved_count = sum(1 for m in metrics if m.status in ("NOT_CALIBRATED", "PENDING_ENGINEERING_RECALCULATION"))
    validation_status: Literal["VALID", "INVALID", "VALID_WITH_UNCALIBRATED_DEPENDENCIES"] = "VALID_WITH_UNCALIBRATED_DEPENDENCIES" if unresolved_count else "VALID"

    mission_impacts = (
        MissionLevelImpact(
            mission_id="LOCKED/WHATIF", carrier_id="LIVE-IMPACT-CARRIER", service_class=service_class,
            locked_speed_m_per_s=locked_speed_m_per_s, what_if_speed_m_per_s=what_if_speed_m_per_s,
            wait_delta_minutes=(what_if_wait - locked_wait) if isinstance(locked_wait, (int, float)) and isinstance(what_if_wait, (int, float)) else "NOT_CALIBRATED",
            transport_time_delta_minutes=what_if_duration_min - locked_duration_min if isinstance(locked_duration_min, (int, float)) and isinstance(what_if_duration_min, (int, float)) else "NOT_CALIBRATED",
            trajectory_revision=revision, status="RESOLVED",
        ),
    )
    service_class_impacts = (
        ServiceClassImpact(
            service_class=service_class, mission_count=1, effective_speed_m_per_s=what_if_speed_m_per_s, priority=what_if_dispatch.effective_priority,
            average_transport_time_s=(what_if_duration_min * 60.0) if isinstance(what_if_duration_min, (int, float)) else "NOT_CALIBRATED",
            energy_contribution_w=what_if_drag_power, opex_contribution=metrics[-2].what_if_value if len(metrics) >= 2 else "NOT_CALIBRATED",
            status="RESOLVED",
        ),
    )

    return LiveEngineeringImpactResult(
        scenario_id=f"SPEED-WHATIF-{service_class}", locked_state_id="LOCKED", revision=revision, validation_status=validation_status,
        metrics=tuple(metrics), trace=tuple(trace), mission_impacts=mission_impacts, service_class_impacts=service_class_impacts,
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Section 58-65: MRT segment-length what-if -- reuses the EXISTING guideway
# unit-cost/delta authority verbatim (never a second economic model).
# ---------------------------------------------------------------------------


def compute_segment_length_what_if_impact(
    *, locked_length_m: float, what_if_length_m: float, guideway_unit_cost_per_m: float | None = None,
    speed_m_per_s: float | None = None, revision: int = 1,
) -> LiveEngineeringImpactResult:
    """Section 58-65: segment length -> route length -> travel time (where a
    speed is supplied) -> guideway CapEx delta ONLY (controls/vestibule/
    installation are never recharged merely because length changed --
    sections 59-62)."""
    for name, value in (("locked_length_m", locked_length_m), ("what_if_length_m", what_if_length_m)):
        _reject_non_finite(value, name=name)
        if value < 0:
            raise InvalidParameterError(f"{name} must be non-negative, got {value!r}")

    metrics: list[ImpactMetric] = []
    trace: list[ImpactTraceNode] = []

    capex_delta = csa.compute_segment_length_capex_delta(locked_length_m=locked_length_m, what_if_length_m=what_if_length_m, guideway_unit_cost_per_m=guideway_unit_cost_per_m)
    from models import PlannerAssumptions
    resolved_unit_cost = guideway_unit_cost_per_m if guideway_unit_cost_per_m is not None else PlannerAssumptions().mrt_guideway_capex_per_m
    metrics.append(build_impact_metric(
        metric_id="segment_length_m", display_name="MRT segment length", locked_value=locked_length_m, what_if_value=what_if_length_m,
        unit="m", source_authority="canonical_spatial_authority (spatial state)", provenance="USER_SUPPLIED",
        calibration_status="CALIBRATED", group="SPATIAL",
    ))
    trace.append(ImpactTraceNode("segment_length", f"{locked_length_m} -> {what_if_length_m} m", "route length delta resolved", "RESOLVED", "canonical_spatial_authority"))
    metrics.append(build_impact_metric(
        metric_id="guideway_capex_delta_usd", display_name="Guideway CapEx delta", locked_value=0.0, what_if_value=capex_delta,
        unit="USD", source_authority="canonical_spatial_authority.compute_segment_length_capex_delta",
        provenance=f"EXISTING_PROJECT_ASSUMPTION (unit_cost=${resolved_unit_cost:,.0f}/m)", calibration_status="CALIBRATED", group="CAPEX",
    ))
    trace.append(ImpactTraceNode("guideway_capex", f"unit_cost=${resolved_unit_cost:,.0f}/m", f"delta=${capex_delta:,.2f}", "RESOLVED", "canonical_spatial_authority.compute_segment_length_capex_delta"))

    # Section 61-62/65: explicit non-regression -- controls/vestibule/installation NEVER recharge from a length-only change.
    for once_component, once_value in (("controls_capex_usd", csa.MRT_CONTROLS_CAPEX_USD), ("vestibule_capex_usd", csa.MRT_VESTIBULE_CAPEX_USD), ("installation_commissioning_capex_usd", csa.MRT_INSTALLATION_COMMISSIONING_CAPEX_USD)):
        metrics.append(build_impact_metric(
            metric_id=f"{once_component}_delta", display_name=f"{once_component} (non-regression)", locked_value=0.0, what_if_value=0.0,
            unit="USD", source_authority="canonical_spatial_authority (once-per-network constants)", provenance="USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION",
            calibration_status="CALIBRATED", group="CAPEX", note=f"Reference constant={once_value:,.0f}; never recharged for a length-only change.",
        ))

    if speed_m_per_s is not None:
        locked_time_s = locked_length_m / speed_m_per_s if speed_m_per_s > 0 else "NOT_CALIBRATED"
        what_if_time_s = what_if_length_m / speed_m_per_s if speed_m_per_s > 0 else "NOT_CALIBRATED"
        metrics.append(build_impact_metric(
            metric_id="transport_time_s", display_name="Transport time (at fixed speed)", locked_value=locked_time_s, what_if_value=what_if_time_s,
            unit="s", source_authority="mrt_service_class_authority.compute_mission_duration_minutes (analogous formula)", provenance="USER_SUPPLIED",
            calibration_status="CALIBRATED", group="TRANSPORT",
        ))
        trace.append(ImpactTraceNode("travel_time", f"speed_m_per_s={speed_m_per_s}", f"{locked_time_s} -> {what_if_time_s} s", "RESOLVED", "mrt_service_class_authority"))
    else:
        metrics.append(build_impact_metric(
            metric_id="transport_time_s", display_name="Transport time (at fixed speed)", locked_value="NOT_CALIBRATED", what_if_value="NOT_CALIBRATED",
            unit="s", source_authority="mrt_service_class_authority.compute_mission_duration_minutes", provenance="NOT_CALIBRATED",
            calibration_status="NOT_CALIBRATED", group="TRANSPORT", note="No speed supplied for this scenario.",
        ))

    metrics.append(build_impact_metric(
        metric_id="annual_opex_delta_usd", display_name="Annual OPEX delta", locked_value="PENDING_ENGINEERING_RECALCULATION",
        what_if_value="PENDING_ENGINEERING_RECALCULATION", unit="USD/year", source_authority="mrt_auxiliary_systems_authority / infrastructure_opex",
        provenance="NOT_CALIBRATED", calibration_status="NOT_CALIBRATED", group="OPEX", note="Guideway maintenance is CapEx-indexed (existing PlannerAssumptions fraction) but not recomputed here without a full OPEX ledger call.",
    ))

    object_impacts = (
        ObjectLevelImpact(object_id="MRT-SEGMENT-1", object_type="MRT_SEGMENT", locked_value=locked_length_m, what_if_value=what_if_length_m, delta=what_if_length_m - locked_length_m, status="RESOLVED", owning_authority="canonical_spatial_authority"),
    )
    unresolved_count = sum(1 for m in metrics if m.status in ("NOT_CALIBRATED", "PENDING_ENGINEERING_RECALCULATION"))
    validation_status: Literal["VALID", "INVALID", "VALID_WITH_UNCALIBRATED_DEPENDENCIES"] = "VALID_WITH_UNCALIBRATED_DEPENDENCIES" if unresolved_count else "VALID"
    return LiveEngineeringImpactResult(
        scenario_id="SEGMENT-LENGTH-WHATIF", locked_state_id="LOCKED", revision=revision, validation_status=validation_status,
        metrics=tuple(metrics), trace=tuple(trace), object_impacts=object_impacts,
    )


# ---------------------------------------------------------------------------
# Section 68/114: electricity-tariff what-if -- cost consequence only, NEVER
# a physical kWh consequence.
# ---------------------------------------------------------------------------


def compute_electricity_tariff_what_if_impact(
    *, annual_kwh: float, locked_tariff_usd_per_kwh: float, what_if_tariff_usd_per_kwh: float, revision: int = 1,
) -> LiveEngineeringImpactResult:
    for name, value in (("annual_kwh", annual_kwh), ("locked_tariff_usd_per_kwh", locked_tariff_usd_per_kwh), ("what_if_tariff_usd_per_kwh", what_if_tariff_usd_per_kwh)):
        _reject_non_finite(value, name=name)
        if value < 0:
            raise InvalidParameterError(f"{name} must be non-negative, got {value!r}")

    locked_opex = maux.compute_electricity_opex(annual_kwh=annual_kwh, electricity_cost_per_kwh=locked_tariff_usd_per_kwh)
    what_if_opex = maux.compute_electricity_opex(annual_kwh=annual_kwh, electricity_cost_per_kwh=what_if_tariff_usd_per_kwh)

    metrics = (
        build_impact_metric(
            metric_id="physical_annual_kwh", display_name="Physical annual energy (kWh)", locked_value=annual_kwh, what_if_value=annual_kwh,
            unit="kWh", source_authority="mrt_auxiliary_systems_authority (upstream physical result)", provenance="EXISTING_PROJECT_ASSUMPTION",
            calibration_status="CALIBRATED", group="ELECTRICAL", note="Section 68: tariff changes cost, never physical consumption.",
        ),
        build_impact_metric(
            metric_id="electricity_tariff_usd_per_kwh", display_name="Electricity tariff", locked_value=locked_tariff_usd_per_kwh, what_if_value=what_if_tariff_usd_per_kwh,
            unit="USD/kWh", source_authority="USER_SUPPLIED (what-if parameter registry: electricity_tariff)", provenance="EXISTING_PROJECT_ASSUMPTION",
            calibration_status="PARTIALLY_CALIBRATED", group="OPEX",
        ),
        build_impact_metric(
            metric_id="electricity_opex_usd", display_name="Annual electricity OPEX", locked_value=locked_opex, what_if_value=what_if_opex,
            unit="USD/year", source_authority="mrt_auxiliary_systems_authority.compute_electricity_opex", provenance="EXISTING_PROJECT_ASSUMPTION",
            calibration_status="CALIBRATED", group="OPEX",
        ),
        build_impact_metric(
            metric_id="capex_delta_usd", display_name="CapEx delta", locked_value=0.0, what_if_value=0.0, unit="USD",
            source_authority="N/A (tariff has no CapEx consequence)", provenance="EXISTING_PROJECT_ASSUMPTION", calibration_status="CALIBRATED", group="CAPEX",
        ),
    )
    trace = (
        ImpactTraceNode("electricity_tariff", f"{locked_tariff_usd_per_kwh} -> {what_if_tariff_usd_per_kwh} USD/kWh", "tariff resolved", "RESOLVED", "USER_SUPPLIED"),
        ImpactTraceNode("electricity_opex", f"annual_kwh={annual_kwh} (unchanged)", f"{locked_opex} -> {what_if_opex} USD/year", "RESOLVED", "mrt_auxiliary_systems_authority.compute_electricity_opex"),
    )
    return LiveEngineeringImpactResult(scenario_id="ELECTRICITY-TARIFF-WHATIF", locked_state_id="LOCKED", revision=revision, validation_status="VALID", metrics=metrics, trace=trace)


# ---------------------------------------------------------------------------
# Section 74-75/128: site-power impact binding -- reuses
# `evaluate_site_power_adequacy` verbatim; never fabricates backup CapEx.
# ---------------------------------------------------------------------------


def compute_site_power_what_if_impact(
    *, profile: maux.SitePowerProfile, locked_incremental_demand_kw: float, what_if_incremental_demand_kw: float, revision: int = 1,
) -> LiveEngineeringImpactResult:
    for name, value in (("locked_incremental_demand_kw", locked_incremental_demand_kw), ("what_if_incremental_demand_kw", what_if_incremental_demand_kw)):
        _reject_non_finite(value, name=name)

    locked_result = maux.evaluate_site_power_adequacy(profile=profile, incremental_demand_kw=locked_incremental_demand_kw)
    what_if_result = maux.evaluate_site_power_adequacy(profile=profile, incremental_demand_kw=what_if_incremental_demand_kw)

    metrics = (
        build_impact_metric(
            metric_id="incremental_demand_kw", display_name="Incremental electrical demand", locked_value=locked_incremental_demand_kw,
            what_if_value=what_if_incremental_demand_kw, unit="kW", source_authority="mrt_auxiliary_systems_authority (upstream electrical/cooling result)",
            provenance="EXISTING_PROJECT_ASSUMPTION", calibration_status="PARTIALLY_CALIBRATED", group="SITE_POWER",
        ),
        build_impact_metric(
            metric_id="site_power_adequacy_status", display_name="Site power adequacy", locked_value=locked_result.status, what_if_value=what_if_result.status,
            unit=None, source_authority="mrt_auxiliary_systems_authority.evaluate_site_power_adequacy", provenance="EXISTING_PROJECT_ASSUMPTION",
            calibration_status="CALIBRATED", group="SITE_POWER",
        ),
        build_impact_metric(
            metric_id="headroom_kw", display_name="Available headroom", locked_value=locked_result.headroom_kw, what_if_value=what_if_result.headroom_kw,
            unit="kW", source_authority="mrt_auxiliary_systems_authority.evaluate_site_power_adequacy", provenance="EXISTING_PROJECT_ASSUMPTION",
            calibration_status="CALIBRATED", group="SITE_POWER",
        ),
        build_impact_metric(
            metric_id="incremental_backup_capex_usd", display_name="Incremental backup-generation CapEx", locked_value=locked_result.incremental_backup_capex_usd,
            what_if_value=what_if_result.incremental_backup_capex_usd, unit="USD", source_authority="mrt_auxiliary_systems_authority.evaluate_site_power_adequacy",
            provenance="EXISTING_PROJECT_ASSUMPTION", calibration_status="CALIBRATED", group="CAPEX",
            note="Section 74: adequate sites never fabricate standby-generation CapEx; inadequate sites report NOT_CALIBRATED unless a real generator cost is supplied.",
        ),
    )
    trace = (
        ImpactTraceNode("cooling_and_electrical_demand", f"{locked_incremental_demand_kw} -> {what_if_incremental_demand_kw} kW", "incremental site demand resolved", "RESOLVED", "mrt_auxiliary_systems_authority"),
        ImpactTraceNode("site_power_adequacy", f"available_normal_power_kw={profile.available_normal_power_kw}", f"{locked_result.status} -> {what_if_result.status}", "RESOLVED", "mrt_auxiliary_systems_authority.evaluate_site_power_adequacy"),
    )
    return LiveEngineeringImpactResult(scenario_id="SITE-POWER-WHATIF", locked_state_id="LOCKED", revision=revision, validation_status="VALID", metrics=metrics, trace=trace)


# ---------------------------------------------------------------------------
# Section 48-50/126: cyclotron equipment what-if -- reuses the EXISTING
# catalog verbatim; never fabricates manufacturer/model metadata or a
# per-model price differentiation the catalog does not carry.
# ---------------------------------------------------------------------------


def compute_cyclotron_model_what_if_impact(*, locked_model_id: str, what_if_model_id: str, revision: int = 1) -> LiveEngineeringImpactResult:
    from cyclotron_catalog import load_cyclotron_catalog
    from models import PlannerAssumptions

    catalog = load_cyclotron_catalog()
    by_id = {m.catalog_model_id: m for m in catalog.models}
    if locked_model_id not in by_id:
        raise InvalidObjectError(f"Unknown catalog_model_id: {locked_model_id!r}")
    if what_if_model_id not in by_id:
        raise InvalidObjectError(f"Unknown catalog_model_id: {what_if_model_id!r}")
    locked_model = by_id[locked_model_id]
    what_if_model = by_id[what_if_model_id]
    a = PlannerAssumptions()

    metrics = (
        build_impact_metric(
            metric_id="catalog_model_id", display_name="Cyclotron catalog model", locked_value=locked_model.catalog_model_id, what_if_value=what_if_model.catalog_model_id,
            unit=None, source_authority="cyclotron_catalog.load_cyclotron_catalog", provenance="MANUFACTURER_SPECIFICATION", calibration_status="CALIBRATED", group="PRODUCTION",
        ),
        build_impact_metric(
            metric_id="manufacturer_model", display_name="Manufacturer / model", locked_value=f"{locked_model.manufacturer} {locked_model.model}",
            what_if_value=f"{what_if_model.manufacturer} {what_if_model.model}", unit=None, source_authority="cyclotron_catalog.load_cyclotron_catalog",
            provenance="MANUFACTURER_SPECIFICATION", calibration_status="CALIBRATED", group="PRODUCTION",
        ),
        build_impact_metric(
            metric_id="supported_radionuclides", display_name="Supported radionuclides", locked_value=tuple(sorted(locked_model.supported_radionuclides)),
            what_if_value=tuple(sorted(what_if_model.supported_radionuclides)), unit=None, source_authority="cyclotron_catalog.load_cyclotron_catalog",
            provenance="MANUFACTURER_SPECIFICATION", calibration_status="CALIBRATED", group="PRODUCTION",
        ),
        build_impact_metric(
            metric_id="max_simultaneous_production_streams", display_name="Max simultaneous production streams", locked_value=locked_model.max_simultaneous_production_streams,
            what_if_value=what_if_model.max_simultaneous_production_streams, unit="streams", source_authority="cyclotron_catalog.load_cyclotron_catalog",
            provenance="MANUFACTURER_SPECIFICATION", calibration_status="CALIBRATED", group="PRODUCTION",
        ),
        build_impact_metric(
            metric_id="cyclotron_capex_usd", display_name="Cyclotron purchase+installation CapEx", locked_value=a.cyclotron_purchase_capex + a.cyclotron_installation_capex,
            what_if_value=a.cyclotron_purchase_capex + a.cyclotron_installation_capex, unit="USD", source_authority="models.PlannerAssumptions (flat, no per-model differentiation)",
            provenance="PROJECT_PLANNING_ASSUMPTION", calibration_status="PARTIALLY_CALIBRATED", group="CAPEX",
            note="The existing economic authority prices cyclotron purchase/installation as a FLAT constant regardless of catalog model -- a genuine, disclosed limitation, not fabricated here.",
        ),
    )
    trace = (
        ImpactTraceNode("catalog_model", f"{locked_model_id} -> {what_if_model_id}", "catalog identity resolved", "RESOLVED", "cyclotron_catalog.load_cyclotron_catalog"),
        ImpactTraceNode("production_capability", "supported_radionuclides/cycle_minutes/streams", "diffed from catalog", "RESOLVED", "cyclotron_catalog.load_cyclotron_catalog"),
        ImpactTraceNode("equipment_capex", "PlannerAssumptions.cyclotron_purchase_capex/installation_capex", "UNCHANGED (flat, no per-model price)", "UNCHANGED", "models.PlannerAssumptions"),
    )
    object_impacts = (
        ObjectLevelImpact(object_id="CY-001", object_type="CYCLOTRON", locked_value=locked_model_id, what_if_value=what_if_model_id, delta=None, status="RESOLVED", owning_authority="cyclotron_catalog"),
    )
    return LiveEngineeringImpactResult(scenario_id="CYCLOTRON-MODEL-WHATIF", locked_state_id="LOCKED", revision=revision, validation_status="VALID", metrics=metrics, trace=trace, object_impacts=object_impacts)


# ---------------------------------------------------------------------------
# Section 41/111: mixed-service scenario -- nuclear + blood + linen missions
# scheduled/aggregated TOGETHER via the EXISTING shared scheduler/aux
# authority. Never collapsed to one fleet-wide speed.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MixedServiceScenarioResult:
    scheduled: tuple
    unresolved: tuple
    speed_mix: "maux.SpeedMixAggregateResult"
    priority_performance: tuple
    trajectories: tuple


def compute_mixed_service_scenario(
    *, nuclear_speed_m_per_s: float = 10.0, blood_speed_m_per_s: float = 7.0, linen_speed_m_per_s: float = 1.0,
    route_length_m: float = 100.0, revision: int = 1,
) -> MixedServiceScenarioResult:
    nuclear = msc.MrtServiceMission(mission_id="NUC-1", carrier_id="CARRIER-N", service_class="RADIOPHARMACEUTICAL_NUCLEAR", route_length_m=route_length_m, start_minutes=1.0, speed_override_m_per_s=nuclear_speed_m_per_s)
    blood = msc.MrtServiceMission(mission_id="BLD-1", carrier_id="CARRIER-B", service_class="SPECIMEN_BLOOD", route_length_m=route_length_m, start_minutes=0.5, speed_override_m_per_s=blood_speed_m_per_s)
    linen = msc.MrtServiceMission(mission_id="LIN-1", carrier_id="CARRIER-L", service_class="LAUNDRY_CLEAN_LINEN", route_length_m=route_length_m, start_minutes=0.0, speed_override_m_per_s=linen_speed_m_per_s)

    scheduled, unresolved = msc.schedule_service_missions([nuclear, blood, linen])
    speed_mix = msc.aggregate_mission_speed_mix_energy([nuclear, blood, linen])
    priority_performance = msc.build_priority_performance_table(scheduled)

    missions_by_id = {"NUC-1": nuclear, "BLD-1": blood, "LIN-1": linen}
    trajectories = tuple(
        msc.build_carrier_trajectory(missions_by_id[s.mission_id], s, mrtway_object_id=f"{s.mission_id}-OBJ", route_id="ROUTE-MIXED")
        for s in scheduled
    )
    return MixedServiceScenarioResult(scheduled=scheduled, unresolved=unresolved, speed_mix=speed_mix, priority_performance=priority_performance, trajectories=trajectories)


# ---------------------------------------------------------------------------
# Section 6/16-22: scenario integration -- reuses `UnifiedWhatIfScenario`
# verbatim (locked-state immutability, scenario isolation, reset-category,
# remove-one-change, return-to-locked all come from the EXISTING authority).
# ---------------------------------------------------------------------------


def run_nuclear_speed_what_if_within_scenario(
    scenario: maux.UnifiedWhatIfScenario, *, locked_speed_m_per_s: float = 10.0, what_if_speed_m_per_s: float = 15.0,
    route_length_m: float = 500.0, revision: int = 1,
) -> tuple[maux.ActiveChange, LiveEngineeringImpactResult]:
    """Section 6/25: records the speed change on the EXISTING
    `UnifiedWhatIfScenario` (never a competing scenario model) and returns
    the corresponding live impact result."""
    change = maux.record_parameter_change(
        scenario, category="TRANSPORT_MRT", parameter_id="mission_speed_override", locked_value=locked_speed_m_per_s,
        what_if_value=what_if_speed_m_per_s, description=f"RADIOPHARMACEUTICAL_NUCLEAR speed {locked_speed_m_per_s}->{what_if_speed_m_per_s} m/s",
    )
    result = compute_service_class_speed_what_if_impact(
        service_class="RADIOPHARMACEUTICAL_NUCLEAR", locked_speed_m_per_s=locked_speed_m_per_s, what_if_speed_m_per_s=what_if_speed_m_per_s,
        route_length_m=route_length_m, revision=revision,
    )
    return change, replace(result, scenario_id=scenario.scenario_id)


# ---------------------------------------------------------------------------
# Section 106/148: deterministic serialization + round-trip.
# ---------------------------------------------------------------------------


def serialize_impact_metric(metric: ImpactMetric) -> dict:
    return {
        "metric_id": metric.metric_id, "display_name": metric.display_name, "locked_value": metric.locked_value,
        "what_if_value": metric.what_if_value, "absolute_delta": metric.absolute_delta, "percent_delta": metric.percent_delta,
        "unit": metric.unit, "status": metric.status, "source_authority": metric.source_authority,
        "provenance": metric.provenance, "calibration_status": metric.calibration_status, "group": metric.group, "note": metric.note,
    }


def serialize_impact_result(result: LiveEngineeringImpactResult) -> dict:
    """Section 106/148: deterministic (sorted-key-independent field order via
    explicit dict construction) serialization sufficient for round-trip
    verification of the required fields (section 148)."""
    return {
        "schema_version": LIVE_BINDING_SCHEMA_VERSION, "scenario_id": result.scenario_id, "locked_state_id": result.locked_state_id,
        "revision": result.revision, "validation_status": result.validation_status,
        "metrics": [serialize_impact_metric(m) for m in result.metrics],
        "trace": [
            {"dependency_node": t.dependency_node, "input_summary": t.input_summary, "output_summary": t.output_summary, "status": t.status, "owning_authority": t.owning_authority}
            for t in result.trace
        ],
        "warnings": list(result.warnings),
    }


def deserialize_impact_result(data: dict) -> LiveEngineeringImpactResult:
    metrics = tuple(ImpactMetric(**m) for m in data["metrics"])
    trace = tuple(ImpactTraceNode(**t) for t in data["trace"])
    return LiveEngineeringImpactResult(
        scenario_id=data["scenario_id"], locked_state_id=data["locked_state_id"], revision=data["revision"],
        validation_status=data["validation_status"], metrics=metrics, trace=trace, warnings=tuple(data.get("warnings", ())),
    )


# ---------------------------------------------------------------------------
# Section 98-99, 145-146: OpenUSD/NVIDIA consumer contract -- PRESENTATION
# ONLY. Neither OpenUSD nor a future NVIDIA viewer calculates engineering
# state; they consume the already-resolved payload below.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NvidiaConsumerPayload:
    """Section 145: platform-neutral consumer payload for a future NVIDIA
    Realtime Viewer prototype -- no NVIDIA/Omniverse library is imported or
    implemented here (section 102/146)."""

    scenario_revision: int
    scene_state_id: str
    carrier_trajectories: tuple
    presentation_metadata: tuple
    impact_summary_reference: str


def build_nvidia_consumer_payload(*, scenario_revision: int, scene_state_id: str, trajectories: Sequence, impact_summary_reference: str) -> NvidiaConsumerPayload:
    presentation = tuple(t.presentation for t in trajectories)
    return NvidiaConsumerPayload(
        scenario_revision=scenario_revision, scene_state_id=scene_state_id, carrier_trajectories=tuple(trajectories),
        presentation_metadata=presentation, impact_summary_reference=impact_summary_reference,
    )

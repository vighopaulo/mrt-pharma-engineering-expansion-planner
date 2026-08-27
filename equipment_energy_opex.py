"""Equipment Specification Catalog + Schedule-Derived Energy OPEX.

Governing equation (section: PURPOSE):
    E_{i,d} = sum_s P_{i,s} * t_{i,d,s}          (kWh)
    Electricity OPEX = E_kWh * electricity_cost_per_kWh

Reuses -- never duplicates -- the existing:
  - `healthcare_integration.EquipmentIdentityRecord` / `EquipmentPowerStateSpecification`
    (equipment identity/specification hooks, already governs kW/kVA/kWh separation
    and NOT_CALIBRATED semantics);
  - `long_horizon_operational_planning.production_plan_for_cyclotron` (actual
    cyclotron irradiation schedule) and `assignments_for_resource` (actual
    scanner scan intervals) for state-TIME derivation -- never re-derives
    intraday physics;
  - `cyclotron_catalog.py` production calibration, untouched (production
    calibration and energy calibration are independent dimensions, section 18).

MRT carrier/guideway energy remains `ENERGY_SPECIFICATION_NOT_CALIBRATED`
unless authoritative repository evidence proves otherwise (none currently
exists) -- never fabricated to make a Conventional/MRT comparison look
complete (sections 48-51, 82-85).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Mapping, Sequence

from clinical_resource_identity import ResourceAvailabilityCalendar
from healthcare_integration import (
    ENERGY_SPECIFICATION_NOT_CALIBRATED,
    EconomicComparabilityStatus,
    EquipmentClass,
    EquipmentEnergyCalibrationStatus,
    EquipmentIdentityRecord,
    is_energy_usable_measurement,
)
from long_horizon_operational_planning import (
    CyclotronCalendar,
    LongHorizonMasterPlan,
    assignments_for_resource,
    production_plan_for_cyclotron,
)

DEFAULT_ACCOUNTING_HORIZON_MINUTES_PER_DAY = 1440.0
CYCLOTRON_ACTIVE_STATE = "IRRADIATING"
SCANNER_ACTIVE_STATE = "SCANNING"


@dataclass(frozen=True)
class EquipmentOperatingStatePolicy:
    """Section 29-30: a deterministic, explicitly-labeled PROJECT_ASSUMPTION
    policy for filling non-scheduled time -- never real hospital policy
    calibration. Equipment remaining available (ON/AVAILABLE) that date
    spends its non-active time in `standby_state`; equipment OFF/UNAVAILABLE
    for the whole date spends the entire accounting horizon in `off_state`."""

    accounting_horizon_minutes_per_day: float = DEFAULT_ACCOUNTING_HORIZON_MINUTES_PER_DAY
    standby_state: str = "STANDBY"
    off_state: str = "OFF"
    provenance: str = "PROJECT_ASSUMPTION"


DEFAULT_OPERATING_STATE_POLICY = EquipmentOperatingStatePolicy()


def derive_cyclotron_state_minutes(
    *, plan: LongHorizonMasterPlan, cyclotron_calendar: CyclotronCalendar, cyclotron_id: str, day: date,
    policy: EquipmentOperatingStatePolicy = DEFAULT_OPERATING_STATE_POLICY,
) -> dict[str, float]:
    """Section 25-26: irradiation time comes from the ACTUAL production
    schedule; OFF-day cyclotrons get zero irradiation and the whole
    accounting horizon in `off_state` -- no fabricated production energy."""
    cycles = production_plan_for_cyclotron(plan, cyclotron_id=cyclotron_id, day=day)
    irradiating_minutes = sum(c.end_time_minutes - c.start_time_minutes for c in cycles)
    is_on = cyclotron_calendar.scenario_state_on(day=day, cyclotron_id=cyclotron_id) == "ON"
    horizon = policy.accounting_horizon_minutes_per_day
    if not is_on:
        return {CYCLOTRON_ACTIVE_STATE: 0.0, policy.off_state: horizon}
    remainder = max(0.0, horizon - irradiating_minutes)
    return {CYCLOTRON_ACTIVE_STATE: irradiating_minutes, policy.standby_state: remainder}


def derive_scanner_state_minutes(
    *, plan: LongHorizonMasterPlan, resource_calendar: ResourceAvailabilityCalendar, scanner_id: str, day: date,
    policy: EquipmentOperatingStatePolicy = DEFAULT_OPERATING_STATE_POLICY,
) -> dict[str, float]:
    """Section 27-28: scan-active time comes from ACTUAL persistent scanner
    assignments (`assignments_for_resource`), never from
    patient_count * assumed duration."""
    assignments = assignments_for_resource(plan, resource_id=scanner_id, day=day)
    scanning_minutes = sum(
        end - start for entry in assignments if entry.scanner_resource_id == scanner_id
        for start, end in (entry.scan_window_minutes,)
    )
    is_available = resource_calendar.state_on(resource_id=scanner_id, day=day) == "AVAILABLE"
    horizon = policy.accounting_horizon_minutes_per_day
    if not is_available:
        return {SCANNER_ACTIVE_STATE: 0.0, policy.off_state: horizon}
    remainder = max(0.0, horizon - scanning_minutes)
    return {SCANNER_ACTIVE_STATE: scanning_minutes, policy.standby_state: remainder}


@dataclass(frozen=True)
class EquipmentDailyEnergyResult:
    """Section 34: one row per equipment/date; `state_durations_minutes` may
    contain calibrated AND uncalibrated states side by side (section 32-33)."""

    day: date
    equipment_id: str
    equipment_class: EquipmentClass
    manufacturer: str
    model: str
    state_durations_minutes: Mapping[str, float]
    state_power_kw_used: Mapping[str, float]
    calculated_energy_kwh: float
    uncalibrated_state_minutes: float
    calibration_status: EquipmentEnergyCalibrationStatus
    electricity_opex: float
    """Reflects only the CALCULATED (calibrated) portion -- section 47: never
    interpret this as total facility electricity when calibration_status !=
    CALIBRATED_FOR_ENERGY; consult `uncalibrated_state_minutes`."""
    provenance: str


def compute_equipment_daily_energy(
    *, equipment_record: EquipmentIdentityRecord, state_durations_minutes: Mapping[str, float], day: date,
    electricity_cost_per_kwh: float,
) -> EquipmentDailyEnergyResult:
    """Section 15/32-33/47: only measurement-legitimate kW states contribute
    to kWh; everything else is tracked as uncalibrated MINUTES (duration
    preserved, section 32) -- never silently treated as zero energy."""
    state_power_kw_used: dict[str, float] = {}
    calculated_kwh = 0.0
    uncalibrated_minutes = 0.0
    for state, minutes in state_durations_minutes.items():
        spec = equipment_record.power_state_spec(state)
        if spec is not None and is_energy_usable_measurement(spec.measurement_type, spec.power_unit):
            calculated_kwh += spec.power_value * (minutes / 60.0)
            state_power_kw_used[state] = spec.power_value
        else:
            uncalibrated_minutes += minutes

    if not equipment_record.power_state_specifications:
        calibration_status: EquipmentEnergyCalibrationStatus = "NOT_CALIBRATED"
    elif uncalibrated_minutes > 0.0:
        calibration_status = "PARTIALLY_CALIBRATED"
    else:
        calibration_status = "CALIBRATED_FOR_ENERGY"

    return EquipmentDailyEnergyResult(
        day=day, equipment_id=equipment_record.canonical_equipment_id, equipment_class=equipment_record.equipment_class,
        manufacturer=equipment_record.manufacturer, model=equipment_record.model,
        state_durations_minutes=dict(state_durations_minutes), state_power_kw_used=state_power_kw_used,
        calculated_energy_kwh=calculated_kwh, uncalibrated_state_minutes=uncalibrated_minutes,
        calibration_status=calibration_status, electricity_opex=calculated_kwh * electricity_cost_per_kwh,
        provenance=equipment_record.specification_provenance,
    )


# ---------------------------------------------------------------------------
# Horizon aggregation (sections 39-41, 88-93)
# ---------------------------------------------------------------------------


MRT_ENERGY_STATUS = ENERGY_SPECIFICATION_NOT_CALIBRATED
"""Section 48-51/101: MRT carrier/guideway energy remains uncalibrated in
this repository -- no authoritative electrical parameters exist. Never
fabricated to $0 or any other value."""


@dataclass(frozen=True)
class HorizonEquipmentEnergyResult:
    """Section 39/93: daily traceability preserved via `daily_results`; the
    remaining fields are horizon-level aggregates."""

    daily_results: tuple[EquipmentDailyEnergyResult, ...]
    cyclotron_calculated_kwh: float
    scanner_calculated_kwh: float
    mrt_energy_status: str
    uncalibrated_component_count: int
    calculated_electricity_opex: float
    economic_comparability_status: EconomicComparabilityStatus


def compute_cyclotron_energy_for_plan(
    *, plan: LongHorizonMasterPlan, cyclotron_calendar: CyclotronCalendar,
    equipment_records_by_id: Mapping[str, EquipmentIdentityRecord], electricity_cost_per_kwh: float,
    policy: EquipmentOperatingStatePolicy = DEFAULT_OPERATING_STATE_POLICY,
) -> tuple[EquipmentDailyEnergyResult, ...]:
    days = sorted({summary.day for summary in plan.daily_summaries})
    results: list[EquipmentDailyEnergyResult] = []
    for cyclotron_id, equipment_record in equipment_records_by_id.items():
        if equipment_record.canonical_equipment_id != cyclotron_id:
            raise ValueError(f"equipment_records_by_id key {cyclotron_id} does not match record identity {equipment_record.canonical_equipment_id}")
        for day in days:
            state_minutes = derive_cyclotron_state_minutes(
                plan=plan, cyclotron_calendar=cyclotron_calendar, cyclotron_id=cyclotron_id, day=day, policy=policy,
            )
            results.append(compute_equipment_daily_energy(
                equipment_record=equipment_record, state_durations_minutes=state_minutes, day=day,
                electricity_cost_per_kwh=electricity_cost_per_kwh,
            ))
    return tuple(results)


def compute_scanner_energy_for_plan(
    *, plan: LongHorizonMasterPlan, resource_calendar: ResourceAvailabilityCalendar,
    equipment_records_by_id: Mapping[str, EquipmentIdentityRecord], electricity_cost_per_kwh: float,
    policy: EquipmentOperatingStatePolicy = DEFAULT_OPERATING_STATE_POLICY,
) -> tuple[EquipmentDailyEnergyResult, ...]:
    days = sorted({summary.day for summary in plan.daily_summaries})
    results: list[EquipmentDailyEnergyResult] = []
    for scanner_id, equipment_record in equipment_records_by_id.items():
        if equipment_record.canonical_equipment_id != scanner_id:
            raise ValueError(f"equipment_records_by_id key {scanner_id} does not match record identity {equipment_record.canonical_equipment_id}")
        for day in days:
            state_minutes = derive_scanner_state_minutes(
                plan=plan, resource_calendar=resource_calendar, scanner_id=scanner_id, day=day, policy=policy,
            )
            results.append(compute_equipment_daily_energy(
                equipment_record=equipment_record, state_durations_minutes=state_minutes, day=day,
                electricity_cost_per_kwh=electricity_cost_per_kwh,
            ))
    return tuple(results)


def _economic_comparability_status(uncalibrated_component_count: int, total_component_count: int) -> EconomicComparabilityStatus:
    """Section 83-85: an uncalibrated MRT (or any) energy component must
    never silently read as a $0 advantage -- it downgrades comparability."""
    if uncalibrated_component_count == 0:
        return "FULLY_CALIBRATED"
    if uncalibrated_component_count < total_component_count:
        return "PARTIALLY_CALIBRATED"
    return "NOT_COMPARABLE_DUE_TO_UNCALIBRATED_ENERGY"


def summarize_horizon_equipment_energy(
    *, cyclotron_results: Sequence[EquipmentDailyEnergyResult], scanner_results: Sequence[EquipmentDailyEnergyResult],
    mrt_component_count: int = 0,
) -> HorizonEquipmentEnergyResult:
    """Section 93: horizon-level energy summary, MRT reported explicitly as
    uncalibrated (never omitted, section 82-83)."""
    all_results = list(cyclotron_results) + list(scanner_results)
    cyclotron_kwh = sum(r.calculated_energy_kwh for r in cyclotron_results)
    scanner_kwh = sum(r.calculated_energy_kwh for r in scanner_results)
    uncalibrated_count = sum(1 for r in all_results if r.calibration_status != "CALIBRATED_FOR_ENERGY") + mrt_component_count
    total_count = len(all_results) + mrt_component_count
    return HorizonEquipmentEnergyResult(
        daily_results=tuple(all_results),
        cyclotron_calculated_kwh=cyclotron_kwh,
        scanner_calculated_kwh=scanner_kwh,
        mrt_energy_status=MRT_ENERGY_STATUS,
        uncalibrated_component_count=uncalibrated_count,
        calculated_electricity_opex=sum(r.electricity_opex for r in all_results),
        economic_comparability_status=_economic_comparability_status(uncalibrated_count, total_count),
    )


def energy_for_equipment(
    horizon_result: HorizonEquipmentEnergyResult, *, equipment_id: str, day: date | None = None,
) -> tuple[EquipmentDailyEnergyResult, ...]:
    """Section 89."""
    return tuple(r for r in horizon_result.daily_results if r.equipment_id == equipment_id and (day is None or r.day == day))


def energy_for_date(horizon_result: HorizonEquipmentEnergyResult, *, day: date) -> tuple[EquipmentDailyEnergyResult, ...]:
    """Section 90: calibrated and uncalibrated components remain distinct
    per-row -- never pre-collapsed."""
    return tuple(r for r in horizon_result.daily_results if r.day == day)


# ---------------------------------------------------------------------------
# OPEX reconciliation / no double-counting (sections 4, 44, 57, 103)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpexReconciliationRow:
    component: str
    before: float
    after: float
    classification: str
    replaced: bool
    residual: float


def reconcile_generic_energy_line_with_schedule_derived(
    *, component_name: str, generic_annual_kwh: float, electricity_cost_per_kwh: float, schedule_derived_annual_opex: float,
) -> OpexReconciliationRow:
    """Section 44/103: for CALIBRATED equipment, the schedule-derived value
    REPLACES the generic annual-allowance line for the SAME physical
    consumption -- never both added together."""
    before = generic_annual_kwh * electricity_cost_per_kwh
    return OpexReconciliationRow(
        component=component_name, before=before, after=schedule_derived_annual_opex,
        classification="ELECTRICITY_INCLUDED", replaced=True, residual=0.0,
    )


# ---------------------------------------------------------------------------
# Authoritative-ledger input bridge (this build): the smallest structured
# handoff `infrastructure_opex.py` needs to compose calibration-aware
# electricity lines without re-deriving any kW/kWh physics itself (section
# 7/17/20). `infrastructure_opex.py` remains the sole authoritative OPEX
# ledger/composition owner -- this module only supplies VALUES + PROVENANCE.
# ---------------------------------------------------------------------------

EnergyValueSource = Literal["SCHEDULE_DERIVED_CALIBRATION", "GENERIC_ENERGY_FALLBACK"]
GENERIC_ENERGY_FALLBACK_USED = "GENERIC_ENERGY_FALLBACK_USED"
ENERGY_PHYSICS_NOT_CALIBRATED = "ENERGY_PHYSICS_NOT_CALIBRATED"


@dataclass(frozen=True)
class LedgerEnergyComponentInput:
    """One physical electricity component's value + provenance for one
    authoritative ledger line (e.g. "Cyclotron energy"). `annual_kwh` is the
    VALUE the ledger should actually bill -- already resolved by
    `build_ledger_energy_component()`'s fallback policy (section 11-12);
    `calculated_energy_kwh` is always the raw schedule-derived figure (0.0 if
    no calibrated state existed) so it is never lost even when the ledger
    bills the generic fallback instead."""

    component_name: str
    annual_kwh: float
    calibration_status: EquipmentEnergyCalibrationStatus
    value_source: EnergyValueSource
    calculated_energy_kwh: float
    uncalibrated_state_minutes: float = 0.0
    generic_fallback_used: bool = False


@dataclass(frozen=True)
class PathwayEnergyLedgerInput:
    """Bundled calibration-aware electricity inputs for one pathway run
    (section 7). Any component left as None means "no schedule-derived
    figure supplied for this line" -- `infrastructure_opex.py` then uses its
    own pre-existing generic assumption unchanged (full backward
    compatibility, section 34/62)."""

    scanner: LedgerEnergyComponentInput | None = None
    cyclotron: LedgerEnergyComponentInput | None = None
    mrt: LedgerEnergyComponentInput | None = None
    other: LedgerEnergyComponentInput | None = None

    def economic_comparability_status(self) -> EconomicComparabilityStatus:
        components = [c for c in (self.scanner, self.cyclotron, self.mrt, self.other) if c is not None]
        uncalibrated = sum(1 for c in components if c.calibration_status != "CALIBRATED_FOR_ENERGY")
        return _economic_comparability_status(uncalibrated, len(components)) if components else "FULLY_CALIBRATED"


def build_ledger_energy_component(
    *, component_name: str, calculated_energy_kwh: float, calibration_status: EquipmentEnergyCalibrationStatus,
    generic_fallback_annual_kwh: float, uncalibrated_state_minutes: float = 0.0,
) -> LedgerEnergyComponentInput:
    """Sections 8-12: the ONE explicit fallback policy for this build.

    CALIBRATED_FOR_ENERGY -> the generic line is REPLACED by the
    schedule-derived kWh (section 5/8).

    PARTIALLY_CALIBRATED / NOT_CALIBRATED -> the known/calculated portion
    alone is never presented as the total physical electricity cost (section
    9); the pre-existing generic annual-kWh assumption is retained for
    economic continuity (section 11), tagged GENERIC_ENERGY_FALLBACK_USED /
    ENERGY_PHYSICS_NOT_CALIBRATED rather than SCHEDULE_DERIVED_CALIBRATION
    (section 12) -- this is NEVER collapsed to 0 kWh/$0 (section 10)."""
    if calibration_status == "CALIBRATED_FOR_ENERGY":
        return LedgerEnergyComponentInput(
            component_name=component_name, annual_kwh=calculated_energy_kwh, calibration_status=calibration_status,
            value_source="SCHEDULE_DERIVED_CALIBRATION", calculated_energy_kwh=calculated_energy_kwh,
            uncalibrated_state_minutes=uncalibrated_state_minutes, generic_fallback_used=False,
        )
    return LedgerEnergyComponentInput(
        component_name=component_name, annual_kwh=generic_fallback_annual_kwh, calibration_status=calibration_status,
        value_source="GENERIC_ENERGY_FALLBACK", calculated_energy_kwh=calculated_energy_kwh,
        uncalibrated_state_minutes=uncalibrated_state_minutes, generic_fallback_used=True,
    )


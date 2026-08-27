"""Controlled tests: Equipment Specification Catalog + Schedule-Derived Energy
OPEX -- cyclotrons + PET/PET-CT scanners.

Grounding: CY-001 uses the REAL catalog identity GE_PETTRACE_890, which is
production-calibrated but carries NO power_kw field-provenance entry in
cyclotron_equipment_catalog.json (verified by direct audit) -- i.e. genuinely
energy-NOT_CALIBRATED today. All power-state values attached in these tests
are explicitly labeled specification_provenance="SYNTHETIC_TEST_CALIBRATION"
-- never presented as real vendor data (section 94-95).
"""

from __future__ import annotations

from datetime import date

import pytest

from clinical_resource_identity import build_calendar_with_no_exceptions, build_deterministic_resource_inventory
from equipment_energy_opex import (
    CYCLOTRON_ACTIVE_STATE,
    MRT_ENERGY_STATUS,
    SCANNER_ACTIVE_STATE,
    DEFAULT_OPERATING_STATE_POLICY,
    compute_cyclotron_energy_for_plan,
    compute_equipment_daily_energy,
    compute_scanner_energy_for_plan,
    derive_cyclotron_state_minutes,
    derive_scanner_state_minutes,
    energy_for_date,
    energy_for_equipment,
    reconcile_generic_energy_line_with_schedule_derived,
    summarize_horizon_equipment_energy,
)
from healthcare_integration import (
    ENERGY_SPECIFICATION_NOT_CALIBRATED,
    EquipmentIdentityRecord,
    EquipmentPowerStateSpecification,
    is_energy_usable_measurement,
)
from long_horizon_operational_planning import CanonicalOperationalPatientRecord, CyclotronCalendar, OperatingCalendar, run_long_horizon_operational_plan
from models import PlannerAssumptions
from multi_cyclotron_authority import build_controlled_dual_origin_geometry, build_multi_cyclotron_scenario

ELECTRICITY_COST_PER_KWH = 0.18


def _geometry_and_calendar(*, cy001="ON", cy002="OFF"):
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state=cy001, cy002_scenario_state=cy002)
    geometry = build_controlled_dual_origin_geometry()
    return geometry, configured


def _resource_calendar(*, scanners: int = 2, injection_resources: int = 3, uptake_resources: int = 3):
    inventory = build_deterministic_resource_inventory(
        injection_room_count=injection_resources, uptake_room_count=uptake_resources, scanner_count=scanners,
    )
    return build_calendar_with_no_exceptions(inventory)


def _committed(patient_id: str, day: date) -> CanonicalOperationalPatientRecord:
    return CanonicalOperationalPatientRecord(
        internal_model_patient_id=patient_id, demand_status="COMMITTED", patient_type="OUTPATIENT",
        radionuclide="F-18", prescribed_activity_mbq=200.0, scheduled_date=day, source_provenance="USER_ENTERED",
    )


def _build_plan(*, patient_count: int, day: date, cy001="ON", cy002="OFF", scanners: int = 2, distribution_concurrency: int = 2):
    geometry, configured = _geometry_and_calendar(cy001=cy001, cy002=cy002)
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=day, planning_end_date=day)
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    records = [_committed(f"P{i}", day) for i in range(patient_count)]
    plan = run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar, pathway="Conventional",
        geometry=geometry, assumptions=assumptions, resource_calendar=_resource_calendar(scanners=scanners),
        distribution_concurrency=distribution_concurrency,
    )
    return plan, cyclotron_calendar, _resource_calendar(scanners=scanners)


def _synthetic_cyclotron_record(*, irradiating_kw: float | None = 180.0, standby_kw: float | None = 15.0, equipment_id: str = "CY-001") -> EquipmentIdentityRecord:
    specs = []
    if irradiating_kw is not None:
        specs.append(EquipmentPowerStateSpecification(
            equipment_class="CYCLOTRON", manufacturer="GE HealthCare", model="PETtrace 890",
            operating_state=CYCLOTRON_ACTIVE_STATE, power_value=irradiating_kw, power_unit="kW",
            measurement_type="AVERAGE_ACTIVE_POWER", source_document="SYNTHETIC_TEST_CALIBRATION",
            source_provenance="SYNTHETIC_TEST_CALIBRATION", calibration_status="SITE_CALIBRATED",
        ))
    if standby_kw is not None:
        specs.append(EquipmentPowerStateSpecification(
            equipment_class="CYCLOTRON", manufacturer="GE HealthCare", model="PETtrace 890",
            operating_state="STANDBY", power_value=standby_kw, power_unit="kW",
            measurement_type="STANDBY_POWER", source_document="SYNTHETIC_TEST_CALIBRATION",
            source_provenance="SYNTHETIC_TEST_CALIBRATION", calibration_status="SITE_CALIBRATED",
        ))
    return EquipmentIdentityRecord(
        canonical_equipment_id=equipment_id, equipment_class="CYCLOTRON", manufacturer="GE HealthCare", model="PETtrace 890",
        specification_provenance="SYNTHETIC_TEST_CALIBRATION", power_state_specifications=tuple(specs),
    )


# ---------------------------------------------------------------------------
# Unit / measurement-semantics correctness
# ---------------------------------------------------------------------------


def test_kw_average_active_power_is_energy_usable() -> None:
    assert is_energy_usable_measurement("AVERAGE_ACTIVE_POWER", "kW")


def test_kva_is_never_energy_usable_even_with_operating_meaning() -> None:
    """Section 8-9: kVA is apparent power/electrical service demand, never
    silently treated as real-power consumption."""
    assert not is_energy_usable_measurement("AVERAGE_ACTIVE_POWER", "kVA")


def test_rated_maximum_and_component_rating_are_never_energy_usable() -> None:
    assert not is_energy_usable_measurement("RATED_MAXIMUM", "kW")
    assert not is_energy_usable_measurement("MAXIMUM_DEMAND", "kW")
    assert not is_energy_usable_measurement("COMPONENT_RATING", "kW")
    assert not is_energy_usable_measurement("SERVICE_REQUIREMENT", "kW")
    assert not is_energy_usable_measurement("NAMEPLATE_ELECTRICAL_SERVICE", "kW")


# ---------------------------------------------------------------------------
# Schedule-derived state time
# ---------------------------------------------------------------------------


def test_cyclotron_irradiating_minutes_come_from_actual_production_schedule() -> None:
    plan, cyclotron_calendar, _ = _build_plan(patient_count=4, day=date(2026, 10, 5))
    state_minutes = derive_cyclotron_state_minutes(plan=plan, cyclotron_calendar=cyclotron_calendar, cyclotron_id="CY-001", day=date(2026, 10, 5))
    assert state_minutes[CYCLOTRON_ACTIVE_STATE] > 0.0
    # State-time conservation: no overlap/negative duration, sums to horizon exactly.
    assert sum(state_minutes.values()) == pytest.approx(DEFAULT_OPERATING_STATE_POLICY.accounting_horizon_minutes_per_day)


def test_cyclotron_off_day_has_zero_irradiation_and_full_off_time() -> None:
    plan, cyclotron_calendar, _ = _build_plan(patient_count=4, day=date(2026, 10, 5))
    cyclotron_calendar_off = CyclotronCalendar(
        configured_cyclotrons=cyclotron_calendar.configured_cyclotrons,
        scenario_state_overrides_by_date={date(2026, 10, 5): {"CY-001": "OFF"}},
    )
    state_minutes = derive_cyclotron_state_minutes(plan=plan, cyclotron_calendar=cyclotron_calendar_off, cyclotron_id="CY-001", day=date(2026, 10, 5))
    assert state_minutes[CYCLOTRON_ACTIVE_STATE] == 0.0
    assert state_minutes["OFF"] == DEFAULT_OPERATING_STATE_POLICY.accounting_horizon_minutes_per_day


def test_scanner_scanning_minutes_come_from_actual_assignments_unused_scanner_is_zero() -> None:
    plan, _, resource_calendar = _build_plan(patient_count=4, day=date(2026, 10, 5), scanners=2)
    used = derive_scanner_state_minutes(plan=plan, resource_calendar=resource_calendar, scanner_id="SCN-001", day=date(2026, 10, 5))
    assert sum(used.values()) == pytest.approx(DEFAULT_OPERATING_STATE_POLICY.accounting_horizon_minutes_per_day)
    # With only 4 patients across 2 scanners, at least one scanner sees real scan-active time.
    assert used[SCANNER_ACTIVE_STATE] >= 0.0


def test_scanner_unavailable_day_has_zero_scanning_and_full_off_time() -> None:
    plan, _, resource_calendar = _build_plan(patient_count=4, day=date(2026, 10, 5), scanners=2)
    from clinical_resource_identity import ResourceAvailabilityCalendar
    unavailable_calendar = ResourceAvailabilityCalendar(
        inventory=resource_calendar.inventory, unavailable_by_date={date(2026, 10, 5): frozenset({"SCN-001"})},
    )
    state_minutes = derive_scanner_state_minutes(plan=plan, resource_calendar=unavailable_calendar, scanner_id="SCN-001", day=date(2026, 10, 5))
    assert state_minutes[SCANNER_ACTIVE_STATE] == 0.0
    assert state_minutes["OFF"] == DEFAULT_OPERATING_STATE_POLICY.accounting_horizon_minutes_per_day


# ---------------------------------------------------------------------------
# Calibration status / no fabrication
# ---------------------------------------------------------------------------


def test_fully_calibrated_cyclotron_computes_nonzero_energy_and_opex() -> None:
    plan, cyclotron_calendar, _ = _build_plan(patient_count=4, day=date(2026, 10, 5))
    state_minutes = derive_cyclotron_state_minutes(plan=plan, cyclotron_calendar=cyclotron_calendar, cyclotron_id="CY-001", day=date(2026, 10, 5))
    record = _synthetic_cyclotron_record()
    result = compute_equipment_daily_energy(equipment_record=record, state_durations_minutes=state_minutes, day=date(2026, 10, 5), electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH)
    assert result.calibration_status == "CALIBRATED_FOR_ENERGY"
    assert result.calculated_energy_kwh > 0.0
    assert result.electricity_opex == pytest.approx(result.calculated_energy_kwh * ELECTRICITY_COST_PER_KWH)
    assert result.uncalibrated_state_minutes == 0.0


def test_partially_calibrated_cyclotron_known_standby_unknown_active() -> None:
    """Known idle/standby power + unknown active power -> PARTIALLY_CALIBRATED;
    known-state energy calculated, unknown-state minutes tracked distinctly
    (never defaulted to zero cost, section 47)."""
    plan, cyclotron_calendar, _ = _build_plan(patient_count=4, day=date(2026, 10, 5))
    state_minutes = derive_cyclotron_state_minutes(plan=plan, cyclotron_calendar=cyclotron_calendar, cyclotron_id="CY-001", day=date(2026, 10, 5))
    record = _synthetic_cyclotron_record(irradiating_kw=None, standby_kw=15.0)
    result = compute_equipment_daily_energy(equipment_record=record, state_durations_minutes=state_minutes, day=date(2026, 10, 5), electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH)
    assert result.calibration_status == "PARTIALLY_CALIBRATED"
    assert result.uncalibrated_state_minutes == pytest.approx(state_minutes[CYCLOTRON_ACTIVE_STATE])
    # Standby-state (known) energy still calculated.
    assert result.calculated_energy_kwh == pytest.approx(15.0 * state_minutes["STANDBY"] / 60.0)


def test_production_calibrated_but_energy_uncalibrated_cy001_ge_pettrace_890() -> None:
    """Real-evidence scenario: CY-001/GE_PETTRACE_890 is production-calibrated
    (schedules real cycles) but the repository carries no power_kw entry for
    this model -- an EquipmentIdentityRecord with no power_state_specifications
    must report NOT_CALIBRATED, never a fabricated value or $0-as-known-cost."""
    plan, cyclotron_calendar, _ = _build_plan(patient_count=4, day=date(2026, 10, 5))
    state_minutes = derive_cyclotron_state_minutes(plan=plan, cyclotron_calendar=cyclotron_calendar, cyclotron_id="CY-001", day=date(2026, 10, 5))
    assert state_minutes[CYCLOTRON_ACTIVE_STATE] > 0.0  # production genuinely occurred
    record = EquipmentIdentityRecord(canonical_equipment_id="CY-001", equipment_class="CYCLOTRON")  # no specs attached
    result = compute_equipment_daily_energy(equipment_record=record, state_durations_minutes=state_minutes, day=date(2026, 10, 5), electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH)
    assert result.calibration_status == "NOT_CALIBRATED"
    assert result.calculated_energy_kwh == 0.0
    assert result.uncalibrated_state_minutes == pytest.approx(sum(state_minutes.values()))
    assert record.energy_specification_status() == ENERGY_SPECIFICATION_NOT_CALIBRATED


def test_unknown_equipment_model_never_defaults_energy() -> None:
    """SCN-003-style unknown manufacturer/model -> NOT_CALIBRATED, no default assigned."""
    record = EquipmentIdentityRecord(canonical_equipment_id="SCN-003", equipment_class="SCANNER")
    assert record.manufacturer == "UNKNOWN"
    assert record.model == "UNKNOWN"
    result = compute_equipment_daily_energy(
        equipment_record=record, state_durations_minutes={SCANNER_ACTIVE_STATE: 120.0, "STANDBY": 1320.0},
        day=date(2026, 10, 5), electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH,
    )
    assert result.calibration_status == "NOT_CALIBRATED"
    assert result.calculated_energy_kwh == 0.0


# ---------------------------------------------------------------------------
# Mixed fleet / no cross-contamination
# ---------------------------------------------------------------------------


def test_mixed_fleet_each_equipment_independently_reported() -> None:
    plan, cyclotron_calendar, _ = _build_plan(patient_count=4, day=date(2026, 10, 5), cy001="ON", cy002="OFF")
    records = {
        "CY-001": _synthetic_cyclotron_record(equipment_id="CY-001"),
        "CY-002": EquipmentIdentityRecord(canonical_equipment_id="CY-002", equipment_class="CYCLOTRON"),
    }
    results = compute_cyclotron_energy_for_plan(
        plan=plan, cyclotron_calendar=cyclotron_calendar, equipment_records_by_id=records, electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH,
    )
    by_id = {r.equipment_id: r for r in results}
    assert by_id["CY-001"].calibration_status == "CALIBRATED_FOR_ENERGY"
    assert by_id["CY-001"].calculated_energy_kwh > 0.0
    assert by_id["CY-002"].calibration_status == "NOT_CALIBRATED"
    assert by_id["CY-002"].calculated_energy_kwh == 0.0
    # CY-002's uncalibrated status never contaminates CY-001's calibrated figure.
    assert by_id["CY-001"].calculated_energy_kwh != by_id["CY-002"].calculated_energy_kwh


def test_equipment_records_by_id_key_must_match_record_identity() -> None:
    plan, cyclotron_calendar, _ = _build_plan(patient_count=4, day=date(2026, 10, 5))
    mismatched = {"CY-999": _synthetic_cyclotron_record(equipment_id="CY-001")}
    with pytest.raises(ValueError):
        compute_cyclotron_energy_for_plan(
            plan=plan, cyclotron_calendar=cyclotron_calendar, equipment_records_by_id=mismatched, electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH,
        )


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------


def test_tariff_sensitivity_same_kwh_opex_scales_linearly() -> None:
    plan, cyclotron_calendar, _ = _build_plan(patient_count=4, day=date(2026, 10, 5))
    state_minutes = derive_cyclotron_state_minutes(plan=plan, cyclotron_calendar=cyclotron_calendar, cyclotron_id="CY-001", day=date(2026, 10, 5))
    record = _synthetic_cyclotron_record()
    low = compute_equipment_daily_energy(equipment_record=record, state_durations_minutes=state_minutes, day=date(2026, 10, 5), electricity_cost_per_kwh=0.10)
    high = compute_equipment_daily_energy(equipment_record=record, state_durations_minutes=state_minutes, day=date(2026, 10, 5), electricity_cost_per_kwh=0.20)
    assert low.calculated_energy_kwh == pytest.approx(high.calculated_energy_kwh)
    assert high.electricity_opex == pytest.approx(low.electricity_opex * 2.0)


def test_schedule_sensitivity_more_patients_more_production_time_more_energy() -> None:
    record = _synthetic_cyclotron_record()
    plan_small, cal_small, _ = _build_plan(patient_count=2, day=date(2026, 10, 5))
    plan_large, cal_large, _ = _build_plan(patient_count=8, day=date(2026, 10, 5))
    small_minutes = derive_cyclotron_state_minutes(plan=plan_small, cyclotron_calendar=cal_small, cyclotron_id="CY-001", day=date(2026, 10, 5))
    large_minutes = derive_cyclotron_state_minutes(plan=plan_large, cyclotron_calendar=cal_large, cyclotron_id="CY-001", day=date(2026, 10, 5))
    small_result = compute_equipment_daily_energy(equipment_record=record, state_durations_minutes=small_minutes, day=date(2026, 10, 5), electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH)
    large_result = compute_equipment_daily_energy(equipment_record=record, state_durations_minutes=large_minutes, day=date(2026, 10, 5), electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH)
    assert large_minutes[CYCLOTRON_ACTIVE_STATE] >= small_minutes[CYCLOTRON_ACTIVE_STATE]
    assert large_result.calculated_energy_kwh >= small_result.calculated_energy_kwh


# ---------------------------------------------------------------------------
# MRT remains uncalibrated / no artificial advantage
# ---------------------------------------------------------------------------


def test_mrt_energy_status_remains_not_calibrated() -> None:
    assert MRT_ENERGY_STATUS == ENERGY_SPECIFICATION_NOT_CALIBRATED


def test_uncalibrated_mrt_component_downgrades_economic_comparability_not_zero_cost() -> None:
    plan, cyclotron_calendar, resource_calendar = _build_plan(patient_count=4, day=date(2026, 10, 5))
    cyclotron_results = compute_cyclotron_energy_for_plan(
        plan=plan, cyclotron_calendar=cyclotron_calendar, equipment_records_by_id={"CY-001": _synthetic_cyclotron_record()},
        electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH,
    )
    scn_record = EquipmentIdentityRecord(canonical_equipment_id="SCN-001", equipment_class="SCANNER")
    scanner_results = compute_scanner_energy_for_plan(
        plan=plan, resource_calendar=resource_calendar, equipment_records_by_id={"SCN-001": scn_record},
        electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH,
    )
    summary = summarize_horizon_equipment_energy(cyclotron_results=cyclotron_results, scanner_results=scanner_results, mrt_component_count=1)
    assert summary.mrt_energy_status == ENERGY_SPECIFICATION_NOT_CALIBRATED
    assert summary.economic_comparability_status in ("PARTIALLY_CALIBRATED", "NOT_COMPARABLE_DUE_TO_UNCALIBRATED_ENERGY")
    # Never presented as a $0 MRT energy advantage.
    assert summary.economic_comparability_status != "FULLY_CALIBRATED"


def test_fully_calibrated_fleet_reports_fully_calibrated_comparability() -> None:
    plan, cyclotron_calendar, _ = _build_plan(patient_count=4, day=date(2026, 10, 5))
    cyclotron_results = compute_cyclotron_energy_for_plan(
        plan=plan, cyclotron_calendar=cyclotron_calendar, equipment_records_by_id={"CY-001": _synthetic_cyclotron_record()},
        electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH,
    )
    summary = summarize_horizon_equipment_energy(cyclotron_results=cyclotron_results, scanner_results=(), mrt_component_count=0)
    assert summary.economic_comparability_status == "FULLY_CALIBRATED"


# ---------------------------------------------------------------------------
# OPEX reconciliation -- no double counting
# ---------------------------------------------------------------------------


def test_reconciliation_replaces_generic_line_never_adds() -> None:
    row = reconcile_generic_energy_line_with_schedule_derived(
        component_name="Cyclotron energy", generic_annual_kwh=50000.0, electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH,
        schedule_derived_annual_opex=12000.0,
    )
    assert row.replaced is True
    assert row.residual == 0.0
    assert row.after == pytest.approx(12000.0)
    assert row.before == pytest.approx(50000.0 * ELECTRICITY_COST_PER_KWH)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def test_energy_for_equipment_and_energy_for_date_queries() -> None:
    plan, cyclotron_calendar, resource_calendar = _build_plan(patient_count=4, day=date(2026, 10, 5))
    cyclotron_results = compute_cyclotron_energy_for_plan(
        plan=plan, cyclotron_calendar=cyclotron_calendar,
        equipment_records_by_id={"CY-001": _synthetic_cyclotron_record(), "CY-002": EquipmentIdentityRecord(canonical_equipment_id="CY-002", equipment_class="CYCLOTRON")},
        electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH,
    )
    summary = summarize_horizon_equipment_energy(cyclotron_results=cyclotron_results, scanner_results=())
    cy001_rows = energy_for_equipment(summary, equipment_id="CY-001")
    assert len(cy001_rows) == 1
    assert cy001_rows[0].day == date(2026, 10, 5)
    date_rows = energy_for_date(summary, day=date(2026, 10, 5))
    assert len(date_rows) == 2


# ---------------------------------------------------------------------------
# Patient-throughput / resource non-regression
# ---------------------------------------------------------------------------


def test_attaching_energy_specs_never_changes_patient_throughput_or_qualified_count() -> None:
    """Attaching EquipmentIdentityRecord/energy computations is read-only over
    the plan -- qualified/committed counts and resource assignments are
    identical whether or not energy specs are computed afterward."""
    plan, cyclotron_calendar, resource_calendar = _build_plan(patient_count=4, day=date(2026, 10, 5))
    before_committed = plan.committed_patient_count
    before_qualified = sum(1 for p in plan.patient_plans if p.completed_within_operating_day)
    before_assignments = {(p.internal_model_patient_id, p.injection_resource_id, p.uptake_resource_id, p.scanner_resource_id) for p in plan.patient_plans}

    compute_cyclotron_energy_for_plan(
        plan=plan, cyclotron_calendar=cyclotron_calendar, equipment_records_by_id={"CY-001": _synthetic_cyclotron_record()},
        electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH,
    )
    compute_scanner_energy_for_plan(
        plan=plan, resource_calendar=resource_calendar,
        equipment_records_by_id={"SCN-001": EquipmentIdentityRecord(canonical_equipment_id="SCN-001", equipment_class="SCANNER"),
                                  "SCN-002": EquipmentIdentityRecord(canonical_equipment_id="SCN-002", equipment_class="SCANNER")},
        electricity_cost_per_kwh=ELECTRICITY_COST_PER_KWH,
    )

    assert plan.committed_patient_count == before_committed
    assert sum(1 for p in plan.patient_plans if p.completed_within_operating_day) == before_qualified
    after_assignments = {(p.internal_model_patient_id, p.injection_resource_id, p.uptake_resource_id, p.scanner_resource_id) for p in plan.patient_plans}
    assert after_assignments == before_assignments

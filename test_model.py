import io
import math
from pathlib import Path

import pandas as pd

from diagnostics import load_radionuclide_half_lives, resolve_half_life_min, validate
from engineering import retention, room_capacity, scanner_capacity
from models import PlannerAssumptions, PlannerInputs, PlannerReport
from optimization import conventional, mrt
from presentation import cumulative_roi_label, format_count, format_currency, format_minutes, format_patients_per_day, format_percent
from reporting_engine import REPORT_SECTIONS, assumptions_dataframe, capex_ledger_dataframe, comparison_dataframe, excel_bytes, ledger_dataframe
from ui_logic import (
    MRT_DEFAULT_DELIVERY_SECONDS,
    assumptions_from_values,
    changed_assumption_labels,
    default_assumption_values,
    seconds_to_minutes,
    validate_assumptions,
)


def sample_inputs(**overrides):
    payload = {
        "project_name": "Test Expansion",
        "current_patients_per_day": 100.0,
        "target_patients_per_day": 180.0,
        "maximum_expected_demand_per_day": 180.0,
        "current_scanners": 3,
        "current_injection_rooms": 6,
        "current_uptake_rooms": 6,
        "has_existing_cyclotron": True,
        "current_usable_doses_per_day": 120.0,
        "current_average_transport_min": 20.0,
        "mrt_transport_min": 0.5,
        "existing_mrt_connectable_rooms": 2,
        "representative_radionuclide": "F-18",
        "representative_half_life_min": None,
    }
    payload.update(overrides)
    return PlannerInputs(**payload)


def test_mrt_default_is_30_seconds_and_internal_half_minute():
    defaults = PlannerAssumptions()
    assert MRT_DEFAULT_DELIVERY_SECONDS == 30.0
    assert math.isclose(defaults.mrt_transport_default_min, 0.5)
    assert math.isclose(seconds_to_minutes(MRT_DEFAULT_DELIVERY_SECONDS), 0.5)


def test_edited_mrt_delivery_time_persists_through_analysis_and_decay():
    assumptions = PlannerAssumptions()
    half_life = 109.8
    edited_minutes = seconds_to_minutes(90.0)
    inputs = sample_inputs(mrt_transport_min=edited_minutes)
    plan = mrt(inputs, assumptions, half_life)

    expected_retained = retention(edited_minutes, half_life) * 100.0
    assert math.isclose(plan.retained_activity_pct, expected_retained)
    assert math.isclose(plan.ledger["mrt_transport_time"], edited_minutes)


def test_assumption_defaults_edit_restore_and_validation():
    defaults = default_assumption_values()
    edited = dict(defaults)
    edited["discount_rate_pct"] = 12.5
    edited["scanner_cycle_min"] = 40.0

    changed = changed_assumption_labels(edited)
    assert "Discount rate" in changed
    assert "Scanner cycle time" in changed

    assumptions = assumptions_from_values(edited)
    assert assumptions.discount_rate_pct == 12.5
    assert assumptions.scanner_cycle_min == 40.0

    restored = default_assumption_values()
    assert restored["discount_rate_pct"] == defaults["discount_rate_pct"]

    invalid = dict(defaults)
    invalid["scanner_availability_pct"] = 0.0
    invalid["discount_rate_pct"] = 150.0
    invalid["additional_room_capex"] = -1.0
    issues = validate_assumptions(invalid)
    assert issues


def test_edited_assumptions_affect_calculation_results():
    base = PlannerAssumptions()
    half_life = 109.8
    inputs = sample_inputs()

    base_conv = conventional(inputs, base, half_life)
    base_mrt = mrt(inputs, base, half_life)

    edited = assumptions_from_values({
        **default_assumption_values(),
        "additional_room_capex": 100_000.0,
        "mrt_infrastructure_capex": 8_000_000.0,
    })
    edited_conv = conventional(inputs, edited, half_life)
    edited_mrt = mrt(inputs, edited, half_life)

    assert edited_conv.capex > base_conv.capex
    assert edited_mrt.capex > base_mrt.capex


def test_conventional_is_linear_and_non_search():
    assumptions = PlannerAssumptions()
    half_life = 109.8
    inputs_a = sample_inputs(target_patients_per_day=150.0)
    inputs_b = sample_inputs(target_patients_per_day=200.0)

    plan_a = conventional(inputs_a, assumptions, half_life)
    plan_b = conventional(inputs_b, assumptions, half_life)
    plan_a_repeat = conventional(inputs_a, assumptions, half_life)

    # Capacity growth remains target/current.
    assert math.isclose(plan_a.capacity_increase_pct, 50.0)
    assert math.isclose(plan_b.capacity_increase_pct, 100.0)

    # Deterministic behavior: same inputs produce the same outputs.
    assert math.isclose(plan_a.required_production_increase_pct, plan_a_repeat.required_production_increase_pct)
    assert plan_a.additional_scanners == plan_a_repeat.additional_scanners
    assert plan_a.additional_injection_rooms == plan_a_repeat.additional_injection_rooms
    assert plan_a.additional_uptake_rooms == plan_a_repeat.additional_uptake_rooms

    # Physical feasibility is enforced.
    assert plan_a.achieved_capacity_per_day >= 150.0
    assert plan_b.achieved_capacity_per_day >= 200.0
    assert plan_b.additional_scanners >= plan_a.additional_scanners

    # Production increase is decay-aware: derived from gross requirement, not raw patient growth.
    retained = retention(inputs_a.current_average_transport_min, half_life)
    expected_a = max(0.0, ((inputs_a.target_patients_per_day / retained) / inputs_a.current_usable_doses_per_day - 1.0) * 100.0)
    expected_b = max(0.0, ((inputs_b.target_patients_per_day / retained) / inputs_b.current_usable_doses_per_day - 1.0) * 100.0)
    assert math.isclose(plan_a.required_production_increase_pct, expected_a)
    assert math.isclose(plan_b.required_production_increase_pct, expected_b)

    # Slower transport (more decay) should require more gross production and expansion.
    fast = conventional(sample_inputs(target_patients_per_day=150.0, current_average_transport_min=5.0), assumptions, half_life)
    slow = conventional(sample_inputs(target_patients_per_day=150.0, current_average_transport_min=20.0), assumptions, half_life)
    assert slow.retained_activity_pct < fast.retained_activity_pct
    assert slow.ledger["required_gross_doses_per_day"] > fast.ledger["required_gross_doses_per_day"]
    assert slow.required_production_increase_pct > fast.required_production_increase_pct


def test_conventional_scanner_and_room_feasibility_is_enforced_deterministically():
    assumptions = PlannerAssumptions()
    inputs = sample_inputs(target_patients_per_day=180.0)
    plan = conventional(inputs, assumptions, 109.8)

    proportional_scanners = int(plan.ledger["proportional_scanner_estimate"])
    required_scanners = int(plan.ledger["required_total_scanners"])
    assert proportional_scanners == math.ceil(3 * 1.8)
    assert required_scanners >= proportional_scanners

    scanner_cap = scanner_capacity(
        required_scanners,
        assumptions.operating_hours_per_day,
        assumptions.scanner_cycle_min,
        assumptions.scanner_availability_pct,
    )
    injection_cap = room_capacity(
        int(plan.ledger["required_total_injection_rooms"]),
        assumptions.operating_hours_per_day,
        assumptions.injection_cycle_min,
    )
    uptake_cap = room_capacity(
        int(plan.ledger["required_total_uptake_rooms"]),
        assumptions.operating_hours_per_day,
        assumptions.uptake_cycle_min,
    )

    assert scanner_cap >= 180.0
    assert injection_cap >= 180.0
    assert uptake_cap >= 180.0
    assert plan.achieved_capacity_per_day >= 180.0


def test_conventional_retention_affects_production_requirement():
    assumptions = PlannerAssumptions()
    half_life = 109.8
    fast = conventional(sample_inputs(current_average_transport_min=5.0), assumptions, half_life)
    slow = conventional(sample_inputs(current_average_transport_min=20.0), assumptions, half_life)

    assert slow.ledger["required_gross_doses_per_day"] > fast.ledger["required_gross_doses_per_day"]
    assert slow.required_production_increase_pct > fast.required_production_increase_pct


def test_conventional_revenue_uses_requested_target_capacity():
    assumptions = PlannerAssumptions()
    inputs = sample_inputs(target_patients_per_day=180.0, maximum_expected_demand_per_day=150.0)
    plan = conventional(inputs, assumptions, 109.8)

    expected_revenue = 180.0 * assumptions.revenue_per_scan * assumptions.operating_days_per_year
    assert math.isclose(plan.revenue_generating_throughput_per_day, 180.0)
    assert math.isclose(plan.financials.annual_revenue, expected_revenue)


def test_mrt_optimization_returns_feasible_minimal_candidate_shape():
    assumptions = PlannerAssumptions()
    plan = mrt(sample_inputs(), assumptions, 109.8)

    assert plan.achieved_capacity_per_day >= 180.0
    assert plan.endpoints >= 2
    assert plan.infrastructure_units >= 1


def test_mrt_revenue_is_capped_by_maximum_expected_demand():
    assumptions = PlannerAssumptions()
    inputs = sample_inputs(maximum_expected_demand_per_day=150.0)
    plan = mrt(inputs, assumptions, 109.8)

    expected_throughput = min(plan.achieved_capacity_per_day, 150.0)
    expected_revenue = expected_throughput * assumptions.revenue_per_scan * assumptions.operating_days_per_year
    assert math.isclose(plan.revenue_generating_throughput_per_day, expected_throughput)
    assert math.isclose(plan.financials.annual_revenue, expected_revenue)


def test_mrt_backbone_is_charged_once_and_capex_ledger_reconciles():
    assumptions = PlannerAssumptions()
    plan = mrt(sample_inputs(), assumptions, 109.8)

    backbone_rows = [row for row in plan.capex_ledger if row["component"] == "MRT base infrastructure"]
    assert len(backbone_rows) == 1
    assert math.isclose(float(backbone_rows[0]["subtotal"]), assumptions.mrt_infrastructure_capex)
    assert math.isclose(sum(float(item["subtotal"]) for item in plan.capex_ledger), plan.capex)


def test_report_generation_assumptions_and_ledger_are_traceable():
    assumptions = assumptions_from_values({
        **default_assumption_values(),
        "discount_rate_pct": 11.0,
    })
    inputs = sample_inputs()
    half_life = 109.8
    conv = conventional(inputs, assumptions, half_life)
    mrt_plan = mrt(inputs, assumptions, half_life)
    report = PlannerReport(
        project_name=inputs.project_name,
        inputs=inputs,
        assumptions=assumptions,
        conventional=conv,
        mrt=mrt_plan,
    )

    comparison = comparison_dataframe(report)
    ledger = ledger_dataframe(report)
    assumptions_table = assumptions_dataframe(report.assumptions)
    capex_table = capex_ledger_dataframe(report)
    book = excel_bytes(report)
    comparison_sheet = pd.read_excel(io.BytesIO(book), sheet_name="Comparison")

    assert list(comparison["Option"]) == ["Conventional Expansion", "MRT-enabled Expansion"]
    assert "Current Patients/day" in comparison.columns
    assert "Requested Patients/day" in comparison.columns
    assert "Maximum Expected Demand/day" in comparison.columns
    assert "Revenue Throughput/day" in comparison.columns
    assert "Annual Revenue" in comparison.columns
    assert "Additional MRT Annual Revenue" in comparison.columns
    assert "Conventional Production Expansion %" in comparison.columns
    assert "MRT Production Expansion %" in comparison.columns
    assert cumulative_roi_label(assumptions.analysis_years) in comparison.columns
    assert all(
        math.isclose(value, conv.required_production_increase_pct)
        for value in comparison["Conventional Production Expansion %"]
    )
    assert all(
        math.isclose(value, mrt_plan.production_increase_pct)
        for value in comparison["MRT Production Expansion %"]
    )
    assert all(
        math.isclose(value, conv.required_production_increase_pct)
        for value in comparison_sheet["Conventional Production Expansion %"]
    )
    assert all(
        math.isclose(value, mrt_plan.production_increase_pct)
        for value in comparison_sheet["MRT Production Expansion %"]
    )
    assert "retention_formula" in set(ledger["Metric"])
    assert "mrt_transport_time" in set(ledger["Metric"])
    assert "conventional_transport_time" in set(ledger["Metric"])
    assert "Status" in assumptions_table.columns
    assert "User-adjusted assumption" in set(assumptions_table["Status"])
    assert "18 hours/day" in set(assumptions_table["Standard Value"])
    assert "Total" in set(capex_table["Component"])
    assert "$6,000,000" in set(assumptions_table["Standard Value"]) 
    assert isinstance(book, bytes)
    assert len(REPORT_SECTIONS) == 12


def test_conventional_transport_time_flows_to_ledger_and_decay_inputs():
    assumptions = PlannerAssumptions()
    inputs = sample_inputs(current_average_transport_min=20.0)
    plan = conventional(inputs, assumptions, 109.8)

    assert math.isclose(plan.ledger["conventional_transport_time"], 20.0)
    assert math.isclose(plan.retained_activity_pct, retention(20.0, 109.8) * 100.0)


def test_professional_number_and_currency_formatting_helpers():
    assert format_currency(6_000_000) == "$6,000,000"
    assert format_currency(25_000) == "$25,000"
    assert format_percent(20.0) == "20%"
    assert format_percent(35.4) == "35.4%"
    assert format_patients_per_day(100) == "100 patients/day"
    assert format_minutes(2.5) == "2.5 minutes"
    assert format_count(4, "scanners") == "4 scanners"


def test_validation_and_half_life_resolution():
    lookup = load_radionuclide_half_lives()
    valid = sample_inputs(representative_radionuclide="Ga-68", representative_half_life_min=None)
    assert validate(valid, lookup) == []
    resolved = resolve_half_life_min(valid, lookup)
    assert math.isclose(resolved, lookup["Ga-68"])

    invalid = sample_inputs(
        project_name="",
        current_patients_per_day=0.0,
        target_patients_per_day=0.0,
        representative_radionuclide="Unknown",
        representative_half_life_min=None,
    )
    issues = validate(invalid, lookup)
    assert issues


def test_build1_shell_labels_and_primary_navigation_text():
    app_text = Path("app.py").read_text(encoding="utf-8")
    foundation_text = Path("ui_foundation.py").read_text(encoding="utf-8")
    text = app_text + "\n" + foundation_text

    expected_labels = [
        "Home / Landing",
        "Projects",
        "Project Overview",
        "Project Definition / Project Mode",
        "Review & Run",
        "Master Engineering Data / Reports / Evidence / Exports",
    ]
    for label in expected_labels:
        assert label in text

    assert "Back" in app_text
    assert "Forward" in app_text
    assert "Create Project" in app_text
    assert "Open Project" in app_text

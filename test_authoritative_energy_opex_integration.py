"""Authoritative Schedule-Derived Energy OPEX Ledger Integration.

Closes the prior build's disclosed gap: schedule-derived/reconciled
electricity (equipment_energy_opex.py) now flows through the SAME
authoritative ledger (infrastructure_opex.py) that decision_pipeline.py
already uses for Conventional/MRT OPEX -> lifecycle economics -> NPV. No
second economics/OPEX authority is created; NPV is never manually
reconstructed in a test -- every NPV assertion below reads
`NativePathwayResult.lifecycle_result.final_npv` produced by the REAL chain:
schedule -> equipment energy -> infrastructure_opex ledger -> total OPEX ->
lifecycle_economics -> NPV.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from decision_pipeline import (
    NativeDecisionPipelineScenario,
    NativePathwayScenario,
    run_native_pathway_pipeline,
)
from equipment_energy_opex import (
    LedgerEnergyComponentInput,
    PathwayEnergyLedgerInput,
    build_ledger_energy_component,
)
from hybrid_optimization import HybridZoneCandidate, evaluate_hybrid_zone_candidate
from cyclotron_production_windows import CyclotronProductionCapability
from engineering_authority import validate_energy_ledger_integration
from models import PlannerAssumptions, SharedNetworkAssumptions
from spatial_benchmark import build_benchmark_geometry, build_production_basis, _base_assumptions
from stochastic_design_day import ActivityDemandModel
from study_scope import apply_study_scope

GENERIC_CYCLOTRON_KWH = 120_000.0
GENERIC_SCANNER_KWH = 12_000.0
GENERIC_MRT_KWH = 25_000.0
TARIFF = 0.18


def _activity_models() -> dict[str, ActivityDemandModel]:
    return {
        "F-18": ActivityDemandModel(
            "bounded_normal", mean_activity_mbq=200.0, stddev_activity_mbq=20.0,
            lower_bound_mbq=160.0, upper_bound_mbq=240.0,
        ),
    }


def _conventional_pathway(*, energy_ledger_input: PathwayEnergyLedgerInput | None = None) -> NativePathwayScenario:
    return NativePathwayScenario(
        pathway="Conventional",
        scanners=3, injection_resources=2, uptake_resources=7,
        distribution_concurrency=1, transport_minutes=7.0,
        installed_cyclotron_units=1, installed_radiopharmacy_units=1,
        radiopharmacy_unit_capex=750_000.0,
        conventional_infrastructure_allowance_units=1,
        conventional_infrastructure_allowance_unit_capex=125_000.0,
        annual_conventional_transport_opex=750_000.0,
        annual_production_variable_cost=300_000.0,
        cyclotron_annual_opex_per_unit=180_000.0,
        annual_scanner_energy_kwh=GENERIC_SCANNER_KWH,
        annual_cyclotron_energy_kwh=GENERIC_CYCLOTRON_KWH,
        annual_other_energy_kwh=4_000.0,
        electricity_cost_per_kwh=TARIFF,
        clinical_staff_fte=4.0, clinical_staff_loaded_cost_per_fte=95_000.0,
        production_staff_fte=2.0, production_staff_loaded_cost_per_fte=110_000.0,
        annual_consumable_units=6000.0, consumable_cost_per_unit=22.0,
        energy_ledger_input=energy_ledger_input,
    )


def _mrt_pathway(*, energy_ledger_input: PathwayEnergyLedgerInput | None = None) -> NativePathwayScenario:
    return NativePathwayScenario(
        pathway="MRT",
        scanners=5, injection_resources=3, uptake_resources=10,
        distribution_concurrency=2, transport_minutes=5.0,
        installed_cyclotron_units=1, installed_radiopharmacy_units=1,
        radiopharmacy_unit_capex=750_000.0,
        installed_mrt_base_infrastructure_units=1, installed_mrt_endpoints=2,
        installed_guideway_length_m=250.0, guideway_capex_per_m=12_000.0,
        operated_mrt_base_units=1, operated_mrt_endpoints=2, operated_guideway_length_m=250.0,
        guideway_maintenance_per_m_year=1_200.0,
        annual_mrt_energy_kwh=GENERIC_MRT_KWH,
        mrt_support_staff_fte=3.0, mrt_support_staff_loaded_cost_per_fte=105_000.0,
        annual_production_variable_cost=300_000.0,
        cyclotron_annual_opex_per_unit=180_000.0,
        annual_scanner_energy_kwh=GENERIC_SCANNER_KWH,
        annual_cyclotron_energy_kwh=GENERIC_CYCLOTRON_KWH,
        annual_other_energy_kwh=4_000.0,
        electricity_cost_per_kwh=TARIFF,
        clinical_staff_fte=4.0, clinical_staff_loaded_cost_per_fte=95_000.0,
        production_staff_fte=2.0, production_staff_loaded_cost_per_fte=110_000.0,
        annual_consumable_units=6000.0, consumable_cost_per_unit=22.0,
        energy_ledger_input=energy_ledger_input,
    )


def _request(conventional: NativePathwayScenario, mrt: NativePathwayScenario) -> NativeDecisionPipelineScenario:
    return NativeDecisionPipelineScenario(
        project_name="Authoritative Energy Ledger Integration",
        target_patients_per_day=150,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide=_activity_models(),
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="PIPELINE-SINGLE",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
        ),
        conventional=conventional,
        mrt=mrt,
        planner_assumptions=PlannerAssumptions(
            analysis_years=10, discount_rate_pct=8.0, operating_days_per_year=300,
            revenue_per_scan=2000.0, scanner_cycle_min=20.0, injection_cycle_min=10.0,
            uptake_cycle_min=45.0, operating_hours_per_day=18.0,
        ),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260818,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )


def _calibrated_cyclotron_component(annual_kwh: float) -> LedgerEnergyComponentInput:
    return build_ledger_energy_component(
        component_name="Cyclotron energy", calculated_energy_kwh=annual_kwh,
        calibration_status="CALIBRATED_FOR_ENERGY", generic_fallback_annual_kwh=GENERIC_CYCLOTRON_KWH,
    )


def _pettrace_890_uncalibrated_cyclotron_component() -> LedgerEnergyComponentInput:
    """Grounding: CY-001/GE_PETTRACE_890 is production-calibrated but has no
    power_kw field-provenance entry -- energy NOT_CALIBRATED (section 37)."""
    return build_ledger_energy_component(
        component_name="Cyclotron energy", calculated_energy_kwh=0.0,
        calibration_status="NOT_CALIBRATED", generic_fallback_annual_kwh=GENERIC_CYCLOTRON_KWH,
        uncalibrated_state_minutes=1440.0,
    )


def _uncalibrated_mrt_component() -> LedgerEnergyComponentInput:
    return build_ledger_energy_component(
        component_name="MRT energy", calculated_energy_kwh=0.0,
        calibration_status="NOT_CALIBRATED", generic_fallback_annual_kwh=GENERIC_MRT_KWH,
        uncalibrated_state_minutes=1440.0,
    )


def _ledger_row(result, component: str):
    return next(row for row in result.opex_result.ledger if row.component == component)


# ---------------------------------------------------------------------------
# Positive control (sections 61/63): real chain, no manual NPV reconstruction.
# ---------------------------------------------------------------------------


def test_calibrated_replacement_flows_through_authoritative_ledger_to_npv():
    baseline_request = _request(_conventional_pathway(), _mrt_pathway())
    baseline = run_native_pathway_pipeline(baseline_request, pathway="Conventional")

    calibrated_kwh = 90_000.0  # deliberately different from the generic 120,000 kWh assumption
    ledger_input = PathwayEnergyLedgerInput(cyclotron=_calibrated_cyclotron_component(calibrated_kwh))
    calibrated_request = _request(_conventional_pathway(energy_ledger_input=ledger_input), _mrt_pathway())
    calibrated = run_native_pathway_pipeline(calibrated_request, pathway="Conventional")

    cyclotron_row = _ledger_row(calibrated, "Cyclotron energy")
    assert cyclotron_row.quantity == pytest.approx(calibrated_kwh)
    assert cyclotron_row.energy_provenance == "SCHEDULE_DERIVED_CALIBRATION"
    assert calibrated.opex_result.total_annual_opex != baseline.opex_result.total_annual_opex
    # Real propagation through the EXISTING lifecycle economics engine -- no
    # manual NPV reconstruction here.
    assert calibrated.lifecycle_result.final_npv != baseline.lifecycle_result.final_npv


def test_schedule_sensitivity_changes_kwh_ledger_and_npv():
    low_ledger = PathwayEnergyLedgerInput(cyclotron=_calibrated_cyclotron_component(50_000.0))
    high_ledger = PathwayEnergyLedgerInput(cyclotron=_calibrated_cyclotron_component(200_000.0))
    low = run_native_pathway_pipeline(_request(_conventional_pathway(energy_ledger_input=low_ledger), _mrt_pathway()), pathway="Conventional")
    high = run_native_pathway_pipeline(_request(_conventional_pathway(energy_ledger_input=high_ledger), _mrt_pathway()), pathway="Conventional")

    assert _ledger_row(high, "Cyclotron energy").quantity > _ledger_row(low, "Cyclotron energy").quantity
    assert high.opex_result.total_annual_opex > low.opex_result.total_annual_opex
    assert high.lifecycle_result.final_npv < low.lifecycle_result.final_npv


def test_tariff_sensitivity_kwh_unchanged_opex_and_npv_change():
    ledger_input = PathwayEnergyLedgerInput(cyclotron=_calibrated_cyclotron_component(90_000.0))
    low_tariff = run_native_pathway_pipeline(
        _request(_conventional_pathway(energy_ledger_input=ledger_input), _mrt_pathway()), pathway="Conventional",
    )
    conv_high = _conventional_pathway(energy_ledger_input=ledger_input)
    conv_high = replace(conv_high, electricity_cost_per_kwh=TARIFF * 2.0)
    high_tariff = run_native_pathway_pipeline(_request(conv_high, _mrt_pathway()), pathway="Conventional")

    assert _ledger_row(low_tariff, "Cyclotron energy").quantity == pytest.approx(_ledger_row(high_tariff, "Cyclotron energy").quantity)
    assert high_tariff.opex_result.total_annual_opex > low_tariff.opex_result.total_annual_opex
    assert high_tariff.lifecycle_result.final_npv < low_tariff.lifecycle_result.final_npv


# ---------------------------------------------------------------------------
# Negative control (section 62): backward compatibility.
# ---------------------------------------------------------------------------


def test_uncalibrated_negative_control_reproduces_prior_generic_economics():
    baseline = run_native_pathway_pipeline(_request(_conventional_pathway(), _mrt_pathway()), pathway="Conventional")
    ledger_input = PathwayEnergyLedgerInput(cyclotron=_pettrace_890_uncalibrated_cyclotron_component())
    uncalibrated = run_native_pathway_pipeline(
        _request(_conventional_pathway(energy_ledger_input=ledger_input), _mrt_pathway()), pathway="Conventional",
    )
    assert uncalibrated.opex_result.total_annual_opex == pytest.approx(baseline.opex_result.total_annual_opex)
    assert uncalibrated.lifecycle_result.final_npv == pytest.approx(baseline.lifecycle_result.final_npv)
    row = _ledger_row(uncalibrated, "Cyclotron energy")
    assert row.quantity == pytest.approx(GENERIC_CYCLOTRON_KWH)
    assert row.energy_provenance == "GENERIC_ENERGY_FALLBACK"


def test_pettrace_890_does_not_receive_fabricated_calibrated_energy():
    ledger_input = PathwayEnergyLedgerInput(cyclotron=_pettrace_890_uncalibrated_cyclotron_component())
    result = run_native_pathway_pipeline(_request(_conventional_pathway(energy_ledger_input=ledger_input), _mrt_pathway()), pathway="Conventional")
    row = _ledger_row(result, "Cyclotron energy")
    assert row.energy_provenance == "GENERIC_ENERGY_FALLBACK"
    assert row.quantity > 0.0  # never silently zeroed
    assert result.opex_result.economic_comparability_status != "FULLY_CALIBRATED"


# ---------------------------------------------------------------------------
# Partial calibration
# ---------------------------------------------------------------------------


def test_partially_calibrated_component_retains_fallback_and_status():
    ledger_component = build_ledger_energy_component(
        component_name="Cyclotron energy", calculated_energy_kwh=30_000.0,
        calibration_status="PARTIALLY_CALIBRATED", generic_fallback_annual_kwh=GENERIC_CYCLOTRON_KWH,
        uncalibrated_state_minutes=600.0,
    )
    ledger_input = PathwayEnergyLedgerInput(cyclotron=ledger_component)
    result = run_native_pathway_pipeline(_request(_conventional_pathway(energy_ledger_input=ledger_input), _mrt_pathway()), pathway="Conventional")
    row = _ledger_row(result, "Cyclotron energy")
    assert row.quantity == pytest.approx(GENERIC_CYCLOTRON_KWH)  # known portion never presented as the total
    assert row.energy_provenance == "GENERIC_ENERGY_FALLBACK"
    # Not fully calibrated -- must never read as FULLY_CALIBRATED (the row-level
    # calibration_status itself is PARTIALLY_CALIBRATED; see build_ledger_energy_component).
    assert result.opex_result.economic_comparability_status != "FULLY_CALIBRATED"


# ---------------------------------------------------------------------------
# MRT fallback (section 38)
# ---------------------------------------------------------------------------


def test_mrt_uncalibrated_energy_never_becomes_zero_cost():
    baseline = run_native_pathway_pipeline(_request(_conventional_pathway(), _mrt_pathway()), pathway="MRT")
    ledger_input = PathwayEnergyLedgerInput(mrt=_uncalibrated_mrt_component())
    result = run_native_pathway_pipeline(_request(_conventional_pathway(), _mrt_pathway(energy_ledger_input=ledger_input)), pathway="MRT")
    row = _ledger_row(result, "MRT energy")
    assert row.quantity == pytest.approx(GENERIC_MRT_KWH)
    assert row.quantity > 0.0
    assert row.energy_provenance == "GENERIC_ENERGY_FALLBACK"
    # Backward-compatible: economics unchanged from the pre-existing generic assumption.
    assert result.opex_result.total_annual_opex == pytest.approx(baseline.opex_result.total_annual_opex)


# ---------------------------------------------------------------------------
# Fixed O&M preservation / no double counting
# ---------------------------------------------------------------------------


def test_fixed_om_preserved_when_energy_is_replaced():
    ledger_input = PathwayEnergyLedgerInput(cyclotron=_calibrated_cyclotron_component(90_000.0))
    result = run_native_pathway_pipeline(_request(_conventional_pathway(energy_ledger_input=ledger_input), _mrt_pathway()), pathway="Conventional")
    fixed_om = _ledger_row(result, "Cyclotron annual fixed O&M")
    assert fixed_om.cost_type == "FIXED"
    assert fixed_om.annual_cost > 0.0
    assert fixed_om.energy_provenance is None


def test_no_duplicate_energy_ledger_line_for_same_component():
    ledger_input = PathwayEnergyLedgerInput(cyclotron=_calibrated_cyclotron_component(90_000.0))
    result = run_native_pathway_pipeline(_request(_conventional_pathway(energy_ledger_input=ledger_input), _mrt_pathway()), pathway="Conventional")
    cyclotron_energy_rows = [row for row in result.opex_result.ledger if row.component == "Cyclotron energy"]
    assert len(cyclotron_energy_rows) == 1
    findings = validate_energy_ledger_integration(ledger=result.opex_result.ledger)
    assert findings == []


# ---------------------------------------------------------------------------
# Study-scope invariance (sections 30-31)
# ---------------------------------------------------------------------------


def test_energy_kwh_invariant_to_study_scope_only_capex_differs():
    ledger_input = PathwayEnergyLedgerInput(cyclotron=_calibrated_cyclotron_component(90_000.0))
    result = run_native_pathway_pipeline(_request(_conventional_pathway(energy_ledger_input=ledger_input), _mrt_pathway()), pathway="Conventional")
    annual_opex = result.opex_result.total_annual_opex
    qualified = int(result.actual_lifecycle_throughput_per_day)

    operational_only = apply_study_scope(
        study_scope="OPERATIONAL_ONLY", transport_architecture="CONVENTIONAL", qualified_throughput=qualified,
        reference_capex=result.capex_result.total_capex, annual_opex=annual_opex, revenue_per_scan=2000.0,
        operating_days_per_year=300, discount_rate_pct=8.0, analysis_years=10,
    )
    capital_planning = apply_study_scope(
        study_scope="CAPITAL_PLANNING", transport_architecture="CONVENTIONAL", qualified_throughput=qualified,
        reference_capex=result.capex_result.total_capex, annual_opex=annual_opex, revenue_per_scan=2000.0,
        operating_days_per_year=300, discount_rate_pct=8.0, analysis_years=10,
    )
    assert operational_only.annual_opex == pytest.approx(capital_planning.annual_opex)
    assert operational_only.study_capex == 0.0
    assert capital_planning.study_capex == result.capex_result.total_capex


# ---------------------------------------------------------------------------
# Non-regression (sections 42-44)
# ---------------------------------------------------------------------------


def test_throughput_and_capex_unchanged_by_energy_ledger_integration():
    baseline = run_native_pathway_pipeline(_request(_conventional_pathway(), _mrt_pathway()), pathway="Conventional")
    ledger_input = PathwayEnergyLedgerInput(cyclotron=_calibrated_cyclotron_component(90_000.0))
    energy_integrated = run_native_pathway_pipeline(_request(_conventional_pathway(energy_ledger_input=ledger_input), _mrt_pathway()), pathway="Conventional")
    assert energy_integrated.actual_lifecycle_throughput_per_day == baseline.actual_lifecycle_throughput_per_day
    assert energy_integrated.capex_result.total_capex == pytest.approx(baseline.capex_result.total_capex)


def test_staffing_opex_unchanged_by_energy_ledger_integration():
    baseline = run_native_pathway_pipeline(_request(_conventional_pathway(), _mrt_pathway()), pathway="Conventional")
    ledger_input = PathwayEnergyLedgerInput(cyclotron=_calibrated_cyclotron_component(90_000.0))
    energy_integrated = run_native_pathway_pipeline(_request(_conventional_pathway(energy_ledger_input=ledger_input), _mrt_pathway()), pathway="Conventional")
    assert _ledger_row(energy_integrated, "Clinical labor").annual_cost == pytest.approx(_ledger_row(baseline, "Clinical labor").annual_cost)
    assert _ledger_row(energy_integrated, "Production labor").annual_cost == pytest.approx(_ledger_row(baseline, "Production labor").annual_cost)


# ---------------------------------------------------------------------------
# OPEX conservation (section 45-46)
# ---------------------------------------------------------------------------


def test_total_opex_reconciles_exactly_to_ledger_sum():
    ledger_input = PathwayEnergyLedgerInput(cyclotron=_calibrated_cyclotron_component(90_000.0))
    result = run_native_pathway_pipeline(_request(_conventional_pathway(energy_ledger_input=ledger_input), _mrt_pathway()), pathway="Conventional")
    ledger_sum = sum(row.annual_cost for row in result.opex_result.ledger)
    assert ledger_sum == pytest.approx(result.opex_result.total_annual_opex)


# ---------------------------------------------------------------------------
# Hybrid shared-electricity no-double-count (sections 21-24, 39, 64)
# ---------------------------------------------------------------------------


def test_hybrid_shared_scanner_and_production_charged_once_regardless_of_mode_split():
    """OBSOLETE_EXPECTATION_FROM_SUPERSEDED_HYBRID_OPEX_AUTHORITY (superseded by
    the Hybrid Authoritative OPEX Ledger Unification build): Hybrid now routes
    through the SAME infrastructure_opex.py ledger pure pathways use (no
    longer a disclosed limitation). This test now proves shared-row equality
    directly from the authoritative ledger rather than a hand-built residual
    subtraction (which grew stale once genuinely MRT-specific rows -- MRT
    support labor, MRT endpoint O&M, guideway maintenance -- were added for
    the MIXED candidate only)."""
    geometry = build_benchmark_geometry()
    basis = build_production_basis()
    assumptions = _base_assumptions()
    network_assumptions = SharedNetworkAssumptions()

    all_conventional = HybridZoneCandidate(
        candidate_id="ALL-CONV", mrt_floors=frozenset(), conventional_floors=frozenset({1, 2, 3}),
        scanners=6, injection_resources=6, uptake_resources=12,
    )
    mixed = HybridZoneCandidate(
        candidate_id="MIXED", mrt_floors=frozenset({1}), conventional_floors=frozenset({2, 3}),
        scanners=6, injection_resources=6, uptake_resources=12,
    )
    conv_result = evaluate_hybrid_zone_candidate(
        geometry=geometry, candidate=all_conventional, demand=200, production_basis=basis,
        assumptions=assumptions, network_assumptions=network_assumptions,
    )
    mixed_result = evaluate_hybrid_zone_candidate(
        geometry=geometry, candidate=mixed, demand=200, production_basis=basis,
        assumptions=assumptions, network_assumptions=network_assumptions,
    )
    # ONE production-labor charge regardless of how many transport modes serve
    # patients -- never duplicated per mode.
    assert conv_result.production_labor_annual_opex == pytest.approx(mixed_result.production_labor_annual_opex)
    # Shared physical-resource ledger rows (scanner=6 in both candidates) are
    # identical in dollar terms regardless of transport-mode split -- never
    # CONV-SCN + MRT-SCN duplicated.
    for component in ("Scanner annual O&M", "Injection resource annual O&M", "Uptake resource annual O&M", "Scanner energy", "Cyclotron energy", "Production labor"):
        conv_row = next(row for row in conv_result.opex_result.ledger if row.component == component)
        mixed_row = next(row for row in mixed_result.opex_result.ledger if row.component == component)
        assert conv_row.annual_cost == pytest.approx(mixed_row.annual_cost), component
    # MRT-specific rows exist ONLY for the mixed candidate, never for ALL_CONVENTIONAL.
    assert not any(row.component == "MRT support labor" for row in conv_result.opex_result.ledger)
    assert any(row.component == "MRT support labor" for row in mixed_result.opex_result.ledger)


from __future__ import annotations

import math

import pytest

from cyclotron_catalog import (
    FacilityCyclotronInstance,
    build_fleet_from_instances,
    find_production_records,
    load_cyclotron_catalog,
)
from decision_pipeline import NativeDecisionPipelineScenario, NativePathwayScenario, run_native_decision_pipeline
from models import PlannerAssumptions, SharedNetworkAssumptions
from multi_isotope_decay import retained_fraction
from stochastic_design_day import ActivityDemandModel


def _planner_assumptions() -> PlannerAssumptions:
    return PlannerAssumptions(
        analysis_years=5,
        discount_rate_pct=8.0,
        operating_days_per_year=300,
        revenue_per_scan=2000.0,
        scanner_cycle_min=20.0,
        injection_cycle_min=10.0,
        uptake_cycle_min=45.0,
        operating_hours_per_day=18.0,
    )


def _pathway(
    *,
    scanners: int,
    injection: int,
    uptake: int,
    transport_minutes: float = 7.0,
    distribution_concurrency: int = 1,
) -> NativePathwayScenario:
    return NativePathwayScenario(
        pathway="Conventional",
        scanners=scanners,
        injection_resources=injection,
        uptake_resources=uptake,
        distribution_concurrency=distribution_concurrency,
        transport_minutes=transport_minutes,
        installed_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        radiopharmacy_unit_capex=750_000.0,
        conventional_infrastructure_allowance_units=1,
        conventional_infrastructure_allowance_unit_capex=125_000.0,
        annual_conventional_transport_opex=750_000.0,
        annual_production_variable_cost=300_000.0,
        annual_scanner_energy_kwh=12_000.0,
        annual_cyclotron_energy_kwh=120_000.0,
        annual_other_energy_kwh=4_000.0,
        electricity_cost_per_kwh=0.18,
        clinical_staff_fte=4.0,
        clinical_staff_loaded_cost_per_fte=95_000.0,
        production_staff_fte=2.0,
        production_staff_loaded_cost_per_fte=110_000.0,
        annual_consumable_units=6000.0,
        consumable_cost_per_unit=22.0,
    )


def _mrt_pathway(
    *,
    scanners: int,
    injection: int,
    uptake: int,
    transport_minutes: float = 5.0,
    distribution_concurrency: int = 2,
) -> NativePathwayScenario:
    return NativePathwayScenario(
        pathway="MRT",
        scanners=scanners,
        injection_resources=injection,
        uptake_resources=uptake,
        distribution_concurrency=distribution_concurrency,
        transport_minutes=transport_minutes,
        installed_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        radiopharmacy_unit_capex=750_000.0,
        installed_mrt_base_infrastructure_units=1,
        installed_mrt_endpoints=2,
        installed_guideway_length_m=250.0,
        guideway_capex_per_m=12_000.0,
        operated_mrt_base_units=1,
        operated_mrt_endpoints=2,
        operated_guideway_length_m=250.0,
        guideway_maintenance_per_m_year=1_200.0,
        annual_mrt_energy_kwh=25_000.0,
        mrt_support_staff_fte=3.0,
        mrt_support_staff_loaded_cost_per_fte=105_000.0,
        annual_production_variable_cost=300_000.0,
        annual_scanner_energy_kwh=12_000.0,
        annual_cyclotron_energy_kwh=120_000.0,
        annual_other_energy_kwh=4_000.0,
        electricity_cost_per_kwh=0.18,
        clinical_staff_fte=4.0,
        clinical_staff_loaded_cost_per_fte=95_000.0,
        production_staff_fte=2.0,
        production_staff_loaded_cost_per_fte=110_000.0,
        annual_consumable_units=6000.0,
        consumable_cost_per_unit=22.0,
    )


def _scenario(
    *,
    fleet,
    target_patients_per_day: int,
    activity_per_patient_mbq: float,
    scanners: int,
    injection_resources: int,
    uptake_resources: int,
    conventional_distribution_concurrency: int = 1,
    mrt_distribution_concurrency: int = 2,
    seed: int = 20260816,
) -> NativeDecisionPipelineScenario:
    return NativeDecisionPipelineScenario(
        project_name="Catalog E2E",
        target_patients_per_day=target_patients_per_day,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=activity_per_patient_mbq),
        },
        cyclotron_capability=fleet.assets[0].capability,
        cyclotron_fleet=fleet,
        conventional=_pathway(
            scanners=scanners,
            injection=injection_resources,
            uptake=uptake_resources,
            distribution_concurrency=conventional_distribution_concurrency,
        ),
        mrt=_mrt_pathway(
            scanners=scanners,
            injection=injection_resources,
            uptake=uptake_resources,
            distribution_concurrency=mrt_distribution_concurrency,
        ),
        planner_assumptions=_planner_assumptions(),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=seed,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )


def _fleet_for_models(*catalog_model_ids: str, site_daily_capacity_mbq: float | None = None):
    catalog = load_cyclotron_catalog()
    instances = []
    for index, model_id in enumerate(catalog_model_ids, start=1):
        instances.append(
            FacilityCyclotronInstance(
                instance_id=f"CY-{index:03d}",
                catalog_model_id=model_id,
                site_max_eob_capacity_mbq_per_day=site_daily_capacity_mbq,
            )
        )
    fleet, warnings = build_fleet_from_instances(catalog=catalog, instances=tuple(instances))
    assert warnings == ()
    assert fleet is not None
    return fleet


def test_catalog_model_selection_changes_end_to_end_when_production_is_bottleneck() -> None:
    catalog = load_cyclotron_catalog()
    rec_840 = find_production_records(catalog=catalog, catalog_model_id="GE_PETTRACE_840", radionuclide="F-18")[0]
    rec_890 = find_production_records(catalog=catalog, catalog_model_id="GE_PETTRACE_890", radionuclide="F-18")[0]
    assert rec_840.normalized_eob_activity_mbq == 240000.0
    assert rec_890.normalized_eob_activity_mbq == 648000.0

    fleet_840 = _fleet_for_models("GE_PETTRACE_840")
    fleet_890 = _fleet_for_models("GE_PETTRACE_890")
    assert fleet_840.assets[0].capability.calibrated_eob_activity_mbq_by_radionuclide["F-18"] == 240000.0
    assert fleet_890.assets[0].capability.calibrated_eob_activity_mbq_by_radionuclide["F-18"] == 648000.0

    request_840 = _scenario(
        fleet=fleet_840,
        target_patients_per_day=160,
        activity_per_patient_mbq=15000.0,
        scanners=20,
        injection_resources=20,
        uptake_resources=20,
    )
    request_890 = _scenario(
        fleet=fleet_890,
        target_patients_per_day=160,
        activity_per_patient_mbq=15000.0,
        scanners=20,
        injection_resources=20,
        uptake_resources=20,
    )

    result_840 = run_native_decision_pipeline(request_840)
    result_890 = run_native_decision_pipeline(request_890)

    assert result_890.conventional.operational_result.patients_completed > result_840.conventional.operational_result.patients_completed
    assert result_890.conventional.annual_revenue > result_840.conventional.annual_revenue

    first_trace = result_890.conventional.decay_summary.patient_traces[0]
    assert first_trace.activity_at_injection_mbq < first_trace.activity_at_eob_mbq
    expected_retained = retained_fraction(first_trace.elapsed_eob_to_injection_minutes, first_trace.half_life_minutes)
    assert math.isclose(
        first_trace.activity_at_injection_mbq / first_trace.activity_at_eob_mbq,
        expected_retained,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_scanner_bottleneck_converges_revenue_for_different_models() -> None:
    fleet_840 = _fleet_for_models("GE_PETTRACE_840")
    fleet_890 = _fleet_for_models("GE_PETTRACE_890")
    req_840 = _scenario(
        fleet=fleet_840,
        target_patients_per_day=300,
        activity_per_patient_mbq=370.0,
        scanners=2,
        injection_resources=20,
        uptake_resources=20,
        conventional_distribution_concurrency=20,
        mrt_distribution_concurrency=20,
    )
    req_890 = _scenario(
        fleet=fleet_890,
        target_patients_per_day=300,
        activity_per_patient_mbq=370.0,
        scanners=2,
        injection_resources=20,
        uptake_resources=20,
        conventional_distribution_concurrency=20,
        mrt_distribution_concurrency=20,
    )

    res_840 = run_native_decision_pipeline(req_840)
    res_890 = run_native_decision_pipeline(req_890)

    assert res_840.conventional.operational_result.bottleneck.resource == res_890.conventional.operational_result.bottleneck.resource
    assert res_840.conventional.operational_result.patients_completed == res_890.conventional.operational_result.patients_completed
    assert res_840.conventional.annual_revenue == pytest.approx(res_890.conventional.annual_revenue)


def test_multiple_identical_cyclotrons_contribute_independently() -> None:
    one = _fleet_for_models("GE_PETTRACE_880")
    two = _fleet_for_models("GE_PETTRACE_880", "GE_PETTRACE_880")

    req_one = _scenario(
        fleet=one,
        target_patients_per_day=260,
        activity_per_patient_mbq=370.0,
        scanners=20,
        injection_resources=20,
        uptake_resources=20,
        conventional_distribution_concurrency=20,
        mrt_distribution_concurrency=20,
    )
    req_two = _scenario(
        fleet=two,
        target_patients_per_day=260,
        activity_per_patient_mbq=370.0,
        scanners=20,
        injection_resources=20,
        uptake_resources=20,
        conventional_distribution_concurrency=20,
        mrt_distribution_concurrency=20,
    )

    res_one = run_native_decision_pipeline(req_one)
    res_two = run_native_decision_pipeline(req_two)

    assert len(one.assets) == 1
    assert len(two.assets) == 2
    assert res_two.conventional.operational_result.patients_completed >= res_one.conventional.operational_result.patients_completed
    if res_two.conventional.operational_result.patients_completed == res_one.conventional.operational_result.patients_completed:
        assert res_two.conventional.annual_revenue == pytest.approx(res_one.conventional.annual_revenue)
    else:
        assert res_two.conventional.annual_revenue > res_one.conventional.annual_revenue


def test_heterogeneous_fleet_preserves_model_specific_capability_records() -> None:
    fleet = _fleet_for_models("GE_PETTRACE_890", "IBA_CYCLONE_KEY")
    eob_by_machine = {
        asset.cyclotron_id: asset.capability.calibrated_eob_activity_mbq_by_radionuclide["F-18"]
        for asset in fleet.assets
    }
    assert sorted(eob_by_machine.values()) == [111000.0, 648000.0]

    result = run_native_decision_pipeline(
        _scenario(
            fleet=fleet,
            target_patients_per_day=160,
            activity_per_patient_mbq=12000.0,
            scanners=20,
            injection_resources=20,
            uptake_resources=20,
        )
    )
    assignments = {
        mapping.assigned_cyclotron_id
        for mapping in result.conventional.operational_result.production_clinical_result.batch_release_mappings
    }
    assert assignments == {"CY-001", "CY-002"}


def test_catalog_not_calibrated_model_stays_non_fabricated() -> None:
    fleet = _fleet_for_models("GE_PETTRACE_800")
    result = run_native_decision_pipeline(
        _scenario(
            fleet=fleet,
            target_patients_per_day=80,
            activity_per_patient_mbq=370.0,
            scanners=20,
            injection_resources=20,
            uptake_resources=20,
        )
    )
    assert result.conventional.operational_result.patients_completed == 0
    assert result.conventional.operational_result.production_activity_infeasible_patients > 0
    assert any("not_calibrated" in warning for warning in result.conventional.warnings)


def test_site_specific_eob_capacity_precedence_over_catalog_batch_point() -> None:
    fleet = _fleet_for_models("GE_PETTRACE_890", site_daily_capacity_mbq=120000.0)
    result = run_native_decision_pipeline(
        _scenario(
            fleet=fleet,
            target_patients_per_day=120,
            activity_per_patient_mbq=5000.0,
            scanners=20,
            injection_resources=20,
            uptake_resources=20,
        )
    )
    assert result.conventional.operational_result.patients_completed < result.conventional.operational_result.decay_feasible_completed_patients


def test_model_change_without_energy_or_utility_overrides_does_not_fabricate_opex_delta() -> None:
    fleet_840 = _fleet_for_models("GE_PETTRACE_840")
    fleet_890 = _fleet_for_models("GE_PETTRACE_890")

    res_840 = run_native_decision_pipeline(
        _scenario(
            fleet=fleet_840,
            target_patients_per_day=200,
            activity_per_patient_mbq=370.0,
            scanners=6,
            injection_resources=8,
            uptake_resources=8,
        )
    )
    res_890 = run_native_decision_pipeline(
        _scenario(
            fleet=fleet_890,
            target_patients_per_day=200,
            activity_per_patient_mbq=370.0,
            scanners=6,
            injection_resources=8,
            uptake_resources=8,
        )
    )

    assert res_840.conventional.annual_opex == pytest.approx(res_890.conventional.annual_opex)

from __future__ import annotations

from dataclasses import replace

import pytest

from architecture_recommendation import (
    ArchitectureRecommendationRequest,
    ConventionalArchitectureBounds,
    MrtArchitectureBounds,
    run_native_architecture_recommendation,
)
from architecture_report import build_native_architecture_report_data
from cyclotron_production_windows import CyclotronProductionCapability
from decision_pipeline import NativeDecisionPipelineScenario, NativePathwayScenario, run_native_decision_pipeline
from models import PlannerAssumptions, SharedNetworkAssumptions
from mrt_carrier_fleet import MrtCarrierFleetInputs, audit_native_mrt_carrier_integration
from reliability_engine import run_native_reliability_engine
from stochastic_design_day import ActivityDemandModel


def _planner() -> PlannerAssumptions:
    return PlannerAssumptions(
        analysis_years=10,
        discount_rate_pct=8.0,
        operating_days_per_year=300,
        revenue_per_scan=2000.0,
        scanner_cycle_min=20.0,
        injection_cycle_min=10.0,
        uptake_cycle_min=45.0,
        operating_hours_per_day=18.0,
    )


def _activity_models() -> dict[str, ActivityDemandModel]:
    return {
        "F-18": ActivityDemandModel(
            "bounded_normal",
            mean_activity_mbq=200.0,
            stddev_activity_mbq=20.0,
            lower_bound_mbq=160.0,
            upper_bound_mbq=240.0,
        ),
    }


def _conventional() -> NativePathwayScenario:
    return NativePathwayScenario(
        pathway="Conventional",
        scanners=3,
        injection_resources=2,
        uptake_resources=7,
        distribution_concurrency=1,
        transport_minutes=7.0,
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


def _mrt(
    *,
    distribution_concurrency: int = 2,
    installed_mrt_carriers: int | None = None,
    operated_mrt_carriers: int | None = None,
    transport_minutes: float = 5.0,
    scanners: int = 5,
    injection_resources: int = 3,
    uptake_resources: int = 10,
) -> NativePathwayScenario:
    return NativePathwayScenario(
        pathway="MRT",
        scanners=scanners,
        injection_resources=injection_resources,
        uptake_resources=uptake_resources,
        distribution_concurrency=distribution_concurrency,
        transport_minutes=transport_minutes,
        installed_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        radiopharmacy_unit_capex=750_000.0,
        installed_mrt_base_infrastructure_units=1,
        installed_mrt_endpoints=2,
        installed_guideway_length_m=250.0,
        guideway_capex_per_m=12_000.0,
        installed_mrt_carriers=installed_mrt_carriers,
        operated_mrt_carriers=operated_mrt_carriers,
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


def _request(
    *,
    target_patients_per_day: int = 220,
    mrt_pathway: NativePathwayScenario | None = None,
    seed: int = 20260813,
) -> NativeDecisionPipelineScenario:
    return NativeDecisionPipelineScenario(
        project_name="Native MRT Carrier Fleet",
        target_patients_per_day=target_patients_per_day,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide=_activity_models(),
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="PIPELINE-F18",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
        ),
        conventional=_conventional(),
        mrt=_mrt() if mrt_pathway is None else mrt_pathway,
        planner_assumptions=_planner(),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=seed,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )


def _architecture_request(
    *,
    target_patients_per_day: int = 220,
    minimum_reliability: float = 0.5,
    mrt_base: NativePathwayScenario | None = None,
    mrt_distribution_bounds: tuple[int, ...] = (1, 2, 4),
) -> ArchitectureRecommendationRequest:
    mrt_base = _mrt(installed_mrt_carriers=4, operated_mrt_carriers=2) if mrt_base is None else mrt_base
    pipeline = _request(target_patients_per_day=target_patients_per_day, mrt_pathway=mrt_base)
    return ArchitectureRecommendationRequest(
        target_patients_per_day=target_patients_per_day,
        minimum_reliability=minimum_reliability,
        seeds=(101, 102, 103),
        pipeline_template=pipeline,
        conventional_bounds=ConventionalArchitectureBounds(
            scanners=(3,),
            injection_resources=(2,),
            uptake_resources=(7,),
            distribution_concurrency=(1,),
            transport_minutes=(7.0,),
        ),
        mrt_bounds=MrtArchitectureBounds(
            scanners=(mrt_base.scanners,),
            injection_resources=(mrt_base.injection_resources,),
            uptake_resources=(mrt_base.uptake_resources,),
            distribution_concurrency=mrt_distribution_bounds,
            installed_mrt_endpoints=(mrt_base.installed_mrt_endpoints,),
            transport_minutes=(mrt_base.transport_minutes,),
        ),
        max_candidate_count=16,
        throughput_thresholds_per_day=(float(target_patients_per_day),),
    )


def test_native_mrt_carrier_audit_identifies_distribution_concurrency_as_authoritative_equivalent():
    audit = audit_native_mrt_carrier_integration()

    assert audit.distribution_concurrency_is_native_equivalent is True
    assert audit.carrier_count_changes_throughput_natively is True
    assert audit.carrier_capex_line_item_exists is False
    assert audit.carrier_opex_line_item_exists is False
    assert audit.carrier_energy_line_item_exists is False
    assert audit.reporting_exposes_carrier_quantity is False
    assert audit.integration_audit["carrier fleet -> distribution concurrency"] == "DIRECT NATIVE CONNECTION"
    assert audit.integration_audit["carrier fleet -> architecture recommendation"] == "NATIVE BOUNDED ORCHESTRATION"


def test_mrt_carrier_inputs_validate_installed_ge_operated_and_reconcile_spares():
    resolved = MrtCarrierFleetInputs(distribution_concurrency=2, installed_carriers=3, operated_carriers=2)

    assert resolved.spare_carriers == 1

    with pytest.raises(ValueError, match="installed_carriers must be greater than or equal to operated_carriers"):
        MrtCarrierFleetInputs(distribution_concurrency=2, installed_carriers=1, operated_carriers=2)


def test_backward_compatibility_defaults_carriers_to_distribution_concurrency():
    mrt = _mrt(distribution_concurrency=3)

    assert mrt.installed_mrt_carriers == 3
    assert mrt.operated_mrt_carriers == 3


def test_operated_carriers_must_match_distribution_concurrency():
    with pytest.raises(ValueError, match="operated_carriers must equal distribution_concurrency"):
        _mrt(distribution_concurrency=2, operated_mrt_carriers=3)


def test_too_few_carriers_constrain_throughput_when_distribution_binds():
    low = run_native_decision_pipeline(
        _request(
            target_patients_per_day=80,
            mrt_pathway=_mrt(
                distribution_concurrency=1,
                transport_minutes=60.0,
                scanners=6,
                injection_resources=6,
                uptake_resources=6,
            ),
        )
    )
    high = run_native_decision_pipeline(
        _request(
            target_patients_per_day=80,
            mrt_pathway=_mrt(
                distribution_concurrency=4,
                transport_minutes=60.0,
                scanners=6,
                injection_resources=6,
                uptake_resources=6,
            ),
        )
    )

    assert low.mrt.operational_result.mrt_carrier_fleet is not None
    assert low.mrt.operational_result.mrt_carrier_fleet.carrier_constrained_throughput is True
    assert high.mrt.operational_result.decay_feasible_completed_patients > low.mrt.operational_result.decay_feasible_completed_patients


def test_additional_carriers_do_not_improve_throughput_after_scanners_bind():
    low = run_native_decision_pipeline(
        _request(
            target_patients_per_day=40,
            mrt_pathway=_mrt(
                distribution_concurrency=1,
                transport_minutes=2.0,
                scanners=1,
                injection_resources=5,
                uptake_resources=5,
            ),
        )
    )
    high = run_native_decision_pipeline(
        _request(
            target_patients_per_day=40,
            mrt_pathway=_mrt(
                distribution_concurrency=4,
                transport_minutes=2.0,
                scanners=1,
                injection_resources=5,
                uptake_resources=5,
            ),
        )
    )

    assert low.mrt.operational_result.decay_feasible_completed_patients == high.mrt.operational_result.decay_feasible_completed_patients


def test_carrier_quantity_appears_in_pathway_and_reliability_outputs():
    request = _request(target_patients_per_day=60, mrt_pathway=_mrt(distribution_concurrency=2, installed_mrt_carriers=3, operated_mrt_carriers=2))
    direct = run_native_decision_pipeline(request)
    reliability = run_native_reliability_engine(request, seeds=(101, 102), throughput_thresholds_per_day=(60.0,))

    carrier = direct.mrt.operational_result.mrt_carrier_fleet
    assert carrier is not None
    assert carrier.installed_carriers == 3
    assert carrier.operated_carriers == 2
    assert carrier.spare_carriers == 1
    assert direct.mrt.operational_result.pathway_config.operated_mrt_carriers == 2

    assert reliability.mrt.mrt_carrier_fleet is not None
    assert reliability.mrt.mrt_carrier_fleet.operated_carriers == 2
    ref = reliability.provenance.run_references_by_seed[101]
    assert ref.distribution_concurrency_by_pathway["MRT"] == 2
    assert ref.installed_carriers_by_pathway["MRT"] == 3
    assert ref.operated_carriers_by_pathway["MRT"] == 2
    assert ref.spare_carriers_by_pathway["MRT"] == 1


def test_carrier_quantity_appears_in_architecture_recommendation_and_reporting():
    recommendation = run_native_architecture_recommendation(_architecture_request(target_patients_per_day=60))
    report = build_native_architecture_report_data(recommendation)

    assert recommendation.mrt_candidates
    assert all(candidate.architecture.operated_mrt_carriers == candidate.architecture.distribution_concurrency for candidate in recommendation.mrt_candidates)
    assert all(candidate.provenance.architecture_quantities["operated_mrt_carriers"] == candidate.architecture.distribution_concurrency for candidate in recommendation.mrt_candidates)
    assert all(candidate.provenance.architecture_quantities["spare_mrt_carriers"] == 2 for candidate in recommendation.mrt_candidates)

    assert report.best_qualifying_mrt_report is not None
    detail = report.best_qualifying_mrt_report.engineering_detail
    assert detail.operated_mrt_carriers == detail.distribution_concurrency
    assert detail.installed_mrt_carriers >= detail.operated_mrt_carriers
    assert detail.spare_mrt_carriers == detail.installed_mrt_carriers - detail.operated_mrt_carriers
    assert detail.carrier_proxy_relationship == "distribution_concurrency == operated_carriers"


def test_no_fabricated_carrier_capex_opex_or_energy_multiplier():
    low = run_native_decision_pipeline(_request(target_patients_per_day=80, mrt_pathway=_mrt(distribution_concurrency=1)))
    high = run_native_decision_pipeline(_request(target_patients_per_day=80, mrt_pathway=_mrt(distribution_concurrency=4)))

    low_carrier = low.mrt.operational_result.mrt_carrier_fleet
    high_carrier = high.mrt.operational_result.mrt_carrier_fleet
    assert low_carrier is not None and high_carrier is not None
    assert low_carrier.carrier_capex_modeled is False
    assert low_carrier.carrier_opex_modeled is False
    assert low_carrier.carrier_energy_modeled is False

    assert low.mrt.capex_result.total_capex == pytest.approx(high.mrt.capex_result.total_capex)
    assert low.mrt.opex_result.total_annual_opex == pytest.approx(high.mrt.opex_result.total_annual_opex)

    low_mrt_energy = next(item for item in low.mrt.opex_result.ledger if item.component == "MRT energy")
    high_mrt_energy = next(item for item in high.mrt.opex_result.ledger if item.component == "MRT energy")
    assert low_mrt_energy.annual_cost == pytest.approx(high_mrt_energy.annual_cost)
    assert all("carrier" not in item.component.lower() for item in low.mrt.capex_result.ledger)
    assert all("carrier" not in item.component.lower() for item in low.mrt.opex_result.ledger)


def test_bounded_carrier_sizing_is_deterministic_and_smaller_qualifying_candidate_can_win():
    request = _architecture_request(
        target_patients_per_day=40,
        minimum_reliability=0.01,
        mrt_base=_mrt(
            distribution_concurrency=2,
            installed_mrt_carriers=4,
            operated_mrt_carriers=2,
            transport_minutes=2.0,
            scanners=1,
            injection_resources=5,
            uptake_resources=5,
        ),
        mrt_distribution_bounds=(1, 2, 4),
    )
    first = run_native_architecture_recommendation(request)
    second = run_native_architecture_recommendation(request)

    assert [candidate.architecture.operated_mrt_carriers for candidate in first.mrt_candidates] == [1, 2, 4]
    assert [candidate.architecture.installed_mrt_carriers for candidate in first.mrt_candidates] == [3, 4, 6]
    assert [candidate.candidate_id for candidate in first.mrt_candidates] == [candidate.candidate_id for candidate in second.mrt_candidates]
    assert first.best_qualifying_mrt is not None
    assert first.best_qualifying_mrt.architecture.operated_mrt_carriers == 1
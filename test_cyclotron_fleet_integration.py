from __future__ import annotations

from dataclasses import replace

import pytest

from architecture_recommendation import (
    ArchitectureRecommendationRequest,
    ConventionalArchitectureBounds,
    MrtArchitectureBounds,
    run_native_architecture_recommendation,
)
from cyclotron_production_windows import (
    CyclotronAsset,
    CyclotronFleet,
    CyclotronProductionCapability,
    assign_batches_to_cyclotron_fleet,
    build_single_cyclotron_fleet,
    schedule_cyclotron_fleet_production_windows,
)
from decision_pipeline import NativeDecisionPipelineScenario, NativePathwayScenario, run_native_decision_pipeline
from models import PlannerAssumptions, SharedNetworkAssumptions
from patient_radionuclide_demand import FacilityDayPatientDemand, PatientRadionuclideDemand
from production_clinical_schedule import ProductionClinicalScenario, build_production_clinical_schedule
from reliability_engine import run_native_reliability_engine
from stochastic_design_day import ActivityDemandModel, DesignDayDemandScenario, generate_design_day_demand


def _planner_assumptions() -> PlannerAssumptions:
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
        "F-18": ActivityDemandModel("bounded_normal", mean_activity_mbq=200.0, stddev_activity_mbq=20.0, lower_bound_mbq=160.0, upper_bound_mbq=240.0),
        "Ga-68": ActivityDemandModel("bounded_normal", mean_activity_mbq=150.0, stddev_activity_mbq=15.0, lower_bound_mbq=120.0, upper_bound_mbq=180.0),
        "N-13": ActivityDemandModel("bounded_normal", mean_activity_mbq=180.0, stddev_activity_mbq=10.0, lower_bound_mbq=150.0, upper_bound_mbq=210.0),
        "C-11": ActivityDemandModel("bounded_normal", mean_activity_mbq=220.0, stddev_activity_mbq=12.0, lower_bound_mbq=190.0, upper_bound_mbq=250.0),
        "O-15": ActivityDemandModel("bounded_normal", mean_activity_mbq=160.0, stddev_activity_mbq=8.0, lower_bound_mbq=140.0, upper_bound_mbq=180.0),
    }


def _conventional_pathway() -> NativePathwayScenario:
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


def _mrt_pathway() -> NativePathwayScenario:
    return NativePathwayScenario(
        pathway="MRT",
        scanners=5,
        injection_resources=3,
        uptake_resources=10,
        distribution_concurrency=2,
        transport_minutes=5.0,
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


def _asset(cyclotron_id: str, supported: tuple[str, ...], cycles: dict[str, float]) -> CyclotronAsset:
    capability = CyclotronProductionCapability(
        cyclotron_id=cyclotron_id,
        supported_radionuclides=supported,
        max_simultaneous_production_streams=2,
        production_cycle_minutes_by_radionuclide=cycles,
        simultaneously_compatible_radionuclide_sets=(frozenset(("F-18", "Ga-68")),) if {"F-18", "Ga-68"}.issubset(set(supported)) else (),
    )
    return CyclotronAsset(cyclotron_id=cyclotron_id, capability=capability, manufacturer="Demo", model_identifier="Demo-Model", capability_provenance="test")


def _fleet_disjoint() -> CyclotronFleet:
    return CyclotronFleet(
        fleet_id="FLEET-DISJOINT",
        assets=(
            _asset("CY-A", ("F-18", "Ga-68"), {"F-18": 30.0, "Ga-68": 20.0}),
            _asset("CY-B", ("N-13", "C-11", "O-15"), {"N-13": 15.0, "C-11": 18.0, "O-15": 12.0}),
        ),
    )


def _fleet_overlap() -> CyclotronFleet:
    return CyclotronFleet(
        fleet_id="FLEET-OVERLAP",
        assets=(
            _asset("CY-A", ("F-18",), {"F-18": 30.0}),
            _asset("CY-B", ("F-18", "Ga-68"), {"F-18": 28.0, "Ga-68": 20.0}),
        ),
    )


def _request(fleet: CyclotronFleet, *, seed: int = 20260813, mix: dict[str, float] | None = None) -> NativeDecisionPipelineScenario:
    mix = mix or {"F-18": 0.35, "Ga-68": 0.20, "N-13": 0.15, "C-11": 0.15, "O-15": 0.15}
    all_models = _activity_models()
    selected_models = {
        radionuclide: all_models.get(radionuclide, ActivityDemandModel("fixed", fixed_activity_mbq=200.0))
        for radionuclide in mix
    }
    return NativeDecisionPipelineScenario(
        project_name="Native Multi Cyclotron Fleet",
        target_patients_per_day=200,
        radionuclide_mix=mix,
        activity_distribution_by_radionuclide=selected_models,
        cyclotron_capability=fleet.assets[0].capability,
        cyclotron_fleet=fleet,
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=_planner_assumptions(),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=seed,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )


def test_single_cyclotron_backward_compatibility_fleet_wrapper():
    capability = CyclotronProductionCapability(
        cyclotron_id="SINGLE",
        supported_radionuclides=("F-18", "Ga-68", "Tc-99m"),
        max_simultaneous_production_streams=2,
        production_cycle_minutes_by_radionuclide={"F-18": 30.0, "Ga-68": 20.0, "Tc-99m": 25.0},
        simultaneously_compatible_radionuclide_sets=(frozenset(("F-18", "Ga-68")),),
    )
    scenario = ProductionClinicalScenario(
        facility_day_demand=FacilityDayPatientDemand(
            patients=(
                PatientRadionuclideDemand("P1", "F-18", 200.0),
                PatientRadionuclideDemand("P2", "Ga-68", 150.0),
            )
        ),
        requested_batch_count_by_radionuclide={"F-18": 1, "Ga-68": 1},
        cyclotron_capability=capability,
        transport_minutes=5.0,
        injection_service_minutes=5.0,
        uptake_minutes=5.0,
        scanner_service_minutes=5.0,
        injection_resources=1,
        uptake_resources=1,
        scanners=1,
        distribution_concurrency=1,
    )
    result = build_production_clinical_schedule(scenario)
    assert result.production_schedule.total_batches == 2


def test_empty_and_duplicate_fleet_validation():
    with pytest.raises(ValueError, match="at least one asset"):
        CyclotronFleet(assets=())
    with pytest.raises(ValueError, match="Duplicate cyclotron ID"):
        asset = _asset("CY-X", ("F-18",), {"F-18": 30.0})
        CyclotronFleet(assets=(asset, asset))


def test_disjoint_fleet_union_is_correct():
    fleet = _fleet_disjoint()
    assert set(fleet.fleet_supported_radionuclides) == {"F-18", "Ga-68", "N-13", "C-11", "O-15"}


def test_stochastic_generator_rejects_unsupported_radionuclide_when_fleet_constrained():
    with pytest.raises(ValueError, match="unavailable in the installed cyclotron fleet"):
        generate_design_day_demand(
            DesignDayDemandScenario(
                target_patients_per_day=20,
                radionuclide_mix={"F-18": 0.8, "Tc-99m": 0.2},
                activity_distribution_by_radionuclide={"F-18": _activity_models()["F-18"], "Tc-99m": ActivityDemandModel("fixed", fixed_activity_mbq=600.0)},
                available_radionuclides=("F-18", "Ga-68"),
                unsupported_radionuclide_policy="reject",
                seed=1,
            )
        )


def test_batch_assignment_respects_isotope_capability_and_is_deterministic():
    fleet = _fleet_disjoint()
    patients = FacilityDayPatientDemand(
        patients=(
            PatientRadionuclideDemand("P1", "F-18", 200.0),
            PatientRadionuclideDemand("P2", "Ga-68", 150.0),
            PatientRadionuclideDemand("P3", "N-13", 180.0),
            PatientRadionuclideDemand("P4", "C-11", 220.0),
        )
    )
    scenario = ProductionClinicalScenario(
        facility_day_demand=patients,
        requested_batch_count_by_radionuclide={"F-18": 1, "Ga-68": 1, "N-13": 1, "C-11": 1},
        cyclotron_fleet=fleet,
        transport_minutes=5.0,
        injection_service_minutes=5.0,
        uptake_minutes=5.0,
        scanner_service_minutes=5.0,
        injection_resources=1,
        uptake_resources=1,
        scanners=1,
        distribution_concurrency=1,
    )
    result_a = build_production_clinical_schedule(scenario)
    result_b = build_production_clinical_schedule(scenario)
    assert result_a.batch_release_mappings == result_b.batch_release_mappings
    for mapping in result_a.batch_release_mappings:
        capability = next(asset.capability for asset in fleet.assets if asset.cyclotron_id == mapping.assigned_cyclotron_id)
        assert mapping.radionuclide in capability.supported_radionuclides


def test_multi_cyclotron_parallelism_allows_overlapping_production_windows():
    fleet = _fleet_disjoint()
    patients = FacilityDayPatientDemand(
        patients=(
            PatientRadionuclideDemand("P1", "F-18", 200.0),
            PatientRadionuclideDemand("P2", "N-13", 180.0),
        )
    )
    scenario = ProductionClinicalScenario(
        facility_day_demand=patients,
        requested_batch_count_by_radionuclide={"F-18": 1, "N-13": 1},
        cyclotron_fleet=fleet,
        transport_minutes=5.0,
        injection_service_minutes=5.0,
        uptake_minutes=5.0,
        scanner_service_minutes=5.0,
        injection_resources=1,
        uptake_resources=1,
        scanners=1,
        distribution_concurrency=1,
    )
    result = build_production_clinical_schedule(scenario)
    windows = result.production_schedule.windows
    assert len(windows) == 2
    assert windows[0].start_time_minutes == pytest.approx(windows[1].start_time_minutes)


def test_same_seed_population_shared_between_conventional_and_mrt_with_same_fleet():
    result = run_native_decision_pipeline(_request(_fleet_disjoint()))
    assert result.conventional.operational_result.demand_result is result.mrt.operational_result.demand_result
    assert result.conventional.operational_result.demand_result.trace_id == result.mrt.operational_result.demand_result.trace_id


def test_unsupported_mix_fails_in_decision_pipeline_with_fleet():
    request = _request(_fleet_disjoint(), mix={"F-18": 0.8, "Tc-99m": 0.2})
    with pytest.raises(ValueError, match="unavailable in the installed cyclotron fleet"):
        run_native_decision_pipeline(request)


def test_fleet_size_propagates_into_capex_and_opex_cyclotron_quantities():
    result = run_native_decision_pipeline(_request(_fleet_disjoint()))
    for pathway in (result.conventional, result.mrt):
        assert pathway.capex_result.charged_quantities["charged_cyclotron_units"] == pytest.approx(2.0)
        assert pathway.opex_result.operated_quantities["operated_cyclotron_units"] == pytest.approx(2.0)


def test_additional_cyclotron_does_not_automatically_create_revenue_when_throughput_unchanged():
    single = CyclotronFleet(assets=(_asset("CY-A", ("F-18", "Ga-68"), {"F-18": 30.0, "Ga-68": 20.0}),), fleet_id="SINGLE")
    dual = CyclotronFleet(
        assets=(
            _asset("CY-A", ("F-18", "Ga-68"), {"F-18": 30.0, "Ga-68": 20.0}),
            _asset("CY-B", ("F-18", "Ga-68"), {"F-18": 30.0, "Ga-68": 20.0}),
        ),
        fleet_id="DUAL",
    )
    mix = {"F-18": 0.7, "Ga-68": 0.3}
    single_result = run_native_decision_pipeline(_request(single, mix=mix))
    dual_result = run_native_decision_pipeline(_request(dual, mix=mix))
    if dual_result.conventional.operational_result.decay_feasible_completed_patients == single_result.conventional.operational_result.decay_feasible_completed_patients:
        assert dual_result.conventional.annual_revenue == pytest.approx(single_result.conventional.annual_revenue)


def test_reliability_preserves_fleet_identity_across_seeds():
    request = _request(_fleet_disjoint())
    result = run_native_reliability_engine(request, seeds=(101, 102, 103))
    for seed, reference in result.provenance.run_references_by_seed.items():
        assert seed in (101, 102, 103)
        assert reference.fleet_id == "FLEET-DISJOINT"
        assert set(reference.fleet_supported_radionuclides) == {"F-18", "Ga-68", "N-13", "C-11", "O-15"}


def test_recommendation_candidate_preserves_fleet_provenance():
    template = _request(_fleet_disjoint())
    recommendation = run_native_architecture_recommendation(
        ArchitectureRecommendationRequest(
            target_patients_per_day=template.target_patients_per_day,
            minimum_reliability=0.9,
            seeds=(101, 102),
            pipeline_template=template,
            conventional_bounds=ConventionalArchitectureBounds(
                scanners=(3,),
                injection_resources=(2,),
                uptake_resources=(7,),
                distribution_concurrency=(1,),
                transport_minutes=(7.0,),
            ),
            mrt_bounds=MrtArchitectureBounds(
                scanners=(5,),
                injection_resources=(3,),
                uptake_resources=(10,),
                distribution_concurrency=(2,),
                installed_mrt_endpoints=(2,),
                transport_minutes=(5.0,),
            ),
            max_candidate_count=4,
            throughput_thresholds_per_day=(template.target_patients_per_day,),
        )
    )
    candidate = (recommendation.conventional_candidates + recommendation.mrt_candidates)[0]
    assert candidate.provenance.fleet_id == "FLEET-DISJOINT"
    assert set(candidate.provenance.fleet_supported_radionuclides) == {"F-18", "Ga-68", "N-13", "C-11", "O-15"}


def test_redundancy_and_removal_behavior():
    overlap = _fleet_overlap()
    assert "F-18" in overlap.fleet_supported_radionuclides
    assert "Ga-68" in overlap.fleet_supported_radionuclides

    removed_a = CyclotronFleet(fleet_id="REMOVED-A", assets=(overlap.assets[1],))
    assert "F-18" in removed_a.fleet_supported_radionuclides
    assert "Ga-68" in removed_a.fleet_supported_radionuclides

    removed_b = CyclotronFleet(fleet_id="REMOVED-B", assets=(overlap.assets[0],))
    assert "F-18" in removed_b.fleet_supported_radionuclides
    assert "Ga-68" not in removed_b.fleet_supported_radionuclides

    req = _request(removed_b, mix={"F-18": 0.6, "Ga-68": 0.4})
    with pytest.raises(ValueError, match="unavailable in the installed cyclotron fleet"):
        run_native_decision_pipeline(req)


def test_production_trace_includes_patient_to_batch_to_cyclotron_lineage():
    result = run_native_decision_pipeline(_request(_fleet_disjoint()))
    trace = result.conventional.operational_result.production_clinical_result.patient_traces[0]
    assert trace.patient_id.startswith("P")
    assert trace.batch_id > 0
    assert trace.assigned_cyclotron_id in {"CY-A", "CY-B"}
    assert trace.production_window_id > 0

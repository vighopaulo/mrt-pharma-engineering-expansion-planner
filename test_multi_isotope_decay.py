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
from multi_isotope_decay import activity_after_decay, evaluate_pathway_decay, retained_fraction
from patient_radionuclide_demand import PatientRadionuclideDemand
from pettrace_800_capability import PETTRACE_800_REFERENCE_RECORDS, pettrace_800_supported_radionuclides
from production_clinical_schedule import ProductionClinicalPatientTrace
from reliability_engine import run_native_reliability_engine
from stochastic_design_day import ActivityDemandModel


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


def _activity_models(include_extended: bool = False) -> dict[str, ActivityDemandModel]:
    models = {
        "F-18": ActivityDemandModel("bounded_normal", mean_activity_mbq=200.0, stddev_activity_mbq=20.0, lower_bound_mbq=160.0, upper_bound_mbq=240.0),
        "Ga-68": ActivityDemandModel("bounded_normal", mean_activity_mbq=150.0, stddev_activity_mbq=15.0, lower_bound_mbq=120.0, upper_bound_mbq=180.0),
    }
    if include_extended:
        models.update(
            {
                "N-13": ActivityDemandModel("bounded_normal", mean_activity_mbq=180.0, stddev_activity_mbq=10.0, lower_bound_mbq=150.0, upper_bound_mbq=210.0),
                "C-11": ActivityDemandModel("bounded_normal", mean_activity_mbq=220.0, stddev_activity_mbq=12.0, lower_bound_mbq=190.0, upper_bound_mbq=250.0),
                "O-15": ActivityDemandModel("bounded_normal", mean_activity_mbq=160.0, stddev_activity_mbq=8.0, lower_bound_mbq=140.0, upper_bound_mbq=180.0),
            }
        )
    else:
        models["Tc-99m"] = ActivityDemandModel("bounded_normal", mean_activity_mbq=600.0, stddev_activity_mbq=40.0, lower_bound_mbq=500.0, upper_bound_mbq=700.0)
    return models


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


def _request(*, seed: int = 20260813, include_extended: bool = False) -> NativeDecisionPipelineScenario:
    if include_extended:
        mix = {
            "F-18": 0.35,
            "Ga-68": 0.20,
            "N-13": 0.15,
            "C-11": 0.15,
            "O-15": 0.15,
        }
        capability_supported = ("F-18", "Ga-68", "N-13", "C-11", "O-15")
        cycle = {"F-18": 30.0, "Ga-68": 20.0, "N-13": 15.0, "C-11": 18.0, "O-15": 12.0}
    else:
        mix = {"F-18": 0.60, "Ga-68": 0.25, "Tc-99m": 0.15}
        capability_supported = ("F-18", "Ga-68", "Tc-99m")
        cycle = {"F-18": 30.0, "Ga-68": 20.0, "Tc-99m": 25.0}

    return NativeDecisionPipelineScenario(
        project_name="Native Multi Isotope Decay",
        target_patients_per_day=120,
        radionuclide_mix=mix,
        activity_distribution_by_radionuclide=_activity_models(include_extended=include_extended),
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="PIPELINE-DUAL",
            supported_radionuclides=capability_supported,
            max_simultaneous_production_streams=2,
            production_cycle_minutes_by_radionuclide=cycle,
            simultaneously_compatible_radionuclide_sets=(frozenset({"F-18", "Ga-68"}),),
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=_planner_assumptions(),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=seed,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )


def test_decay_closed_form_values():
    assert retained_fraction(0.0, 109.8) == pytest.approx(1.0)
    assert retained_fraction(109.8, 109.8) == pytest.approx(0.5)
    assert retained_fraction(2 * 109.8, 109.8) == pytest.approx(0.25)
    assert activity_after_decay(100.0, 109.8, 109.8) == pytest.approx(50.0)


def test_isotope_specific_half_life_behavior_differs():
    # For the same elapsed time, shorter half-life should retain less activity.
    f18_retained = retained_fraction(30.0, 109.8)
    o15_retained = retained_fraction(30.0, 2.04)
    assert o15_retained < f18_retained


def test_patient_identity_preserved_and_aggregation_reconciles():
    patients = [
        PatientRadionuclideDemand("P1", "F-18", 200.0),
        PatientRadionuclideDemand("P2", "Ga-68", 150.0),
    ]
    traces = [
        ProductionClinicalPatientTrace("P1", "F-18", 1, 1, 0.0, 30.0, 35.0, 1, 35.0, 40.0, 40.0, 50.0, 50.0, 95.0, 95.0, 115.0, True),
        ProductionClinicalPatientTrace("P2", "Ga-68", 1, 1, 0.0, 30.0, 35.0, 2, 35.0, 42.0, 42.0, 52.0, 52.0, 97.0, 97.0, 117.0, True),
    ]
    summary = evaluate_pathway_decay(pathway="Conventional", generated_patients=patients, patient_traces=traces)

    assert [trace.patient_id for trace in summary.patient_traces] == ["P1", "P2"]
    assert summary.total_patients == 2
    assert sum(batch.patient_count for batch in summary.batch_summaries) == summary.total_patients
    assert sum(item.patient_count for item in summary.isotope_summaries) == summary.total_patients
    assert summary.overall_decay_loss_mbq >= 0.0
    assert summary.overall_decay_loss_mbq == pytest.approx(
        summary.overall_physical_decay_loss_mbq + summary.overall_unmet_prescribed_activity_mbq
    )
    assert all(0.0 <= trace.retained_fraction_at_administration <= 1.0 for trace in summary.patient_traces)
    assert all(trace.activity_at_injection_mbq == pytest.approx(trace.prescribed_activity_mbq) for trace in summary.patient_traces)
    assert all(trace.activity_at_eob_mbq >= trace.activity_at_injection_mbq for trace in summary.patient_traces)
    assert all(trace.activity_at_release_mbq >= trace.activity_at_injection_mbq for trace in summary.patient_traces)
    assert all(trace.decay_feasible for trace in summary.patient_traces)
    assert all(trace.decay_infeasibility_reason is None for trace in summary.patient_traces)


def test_shorter_timing_has_higher_retention_with_all_else_equal():
    patient = [PatientRadionuclideDemand("P1", "F-18", 200.0)]
    slower = [
        ProductionClinicalPatientTrace("P1", "F-18", 1, 1, 0.0, 30.0, 35.0, 1, 35.0, 40.0, 40.0, 80.0, 80.0, 125.0, 125.0, 145.0, True)
    ]
    faster = [
        ProductionClinicalPatientTrace("P1", "F-18", 1, 1, 0.0, 30.0, 33.0, 1, 33.0, 36.0, 36.0, 45.0, 45.0, 75.0, 75.0, 95.0, True)
    ]
    slow_summary = evaluate_pathway_decay(pathway="Conventional", generated_patients=patient, patient_traces=slower)
    fast_summary = evaluate_pathway_decay(pathway="MRT", generated_patients=patient, patient_traces=faster)

    assert fast_summary.mean_retained_fraction > slow_summary.mean_retained_fraction
    assert fast_summary.overall_decay_loss_mbq < slow_summary.overall_decay_loss_mbq


def test_pathways_deliver_same_prescribed_dose_but_different_upstream_requirement():
    patient = [PatientRadionuclideDemand("P1", "F-18", 200.0)]
    slower = [
        ProductionClinicalPatientTrace("P1", "F-18", 1, 1, 0.0, 30.0, 35.0, 1, 35.0, 40.0, 40.0, 80.0, 80.0, 125.0, 125.0, 145.0, True)
    ]
    faster = [
        ProductionClinicalPatientTrace("P1", "F-18", 1, 1, 0.0, 30.0, 33.0, 1, 33.0, 36.0, 36.0, 45.0, 45.0, 75.0, 75.0, 95.0, True)
    ]

    slow_summary = evaluate_pathway_decay(pathway="Conventional", generated_patients=patient, patient_traces=slower)
    fast_summary = evaluate_pathway_decay(pathway="MRT", generated_patients=patient, patient_traces=faster)
    slow_trace = slow_summary.patient_traces[0]
    fast_trace = fast_summary.patient_traces[0]

    assert slow_trace.activity_at_injection_mbq == pytest.approx(200.0)
    assert fast_trace.activity_at_injection_mbq == pytest.approx(200.0)
    assert slow_trace.activity_at_eob_mbq > fast_trace.activity_at_eob_mbq
    assert slow_trace.physical_decay_loss_before_administration_mbq > fast_trace.physical_decay_loss_before_administration_mbq


def test_supported_radionuclides_include_pettrace_minimum_scope():
    isotopes = pettrace_800_supported_radionuclides()
    assert {"F-18", "Ga-68", "N-13", "C-11", "O-15"}.issubset(set(isotopes))
    assert len(PETTRACE_800_REFERENCE_RECORDS) >= 5


def test_missing_radionuclide_physics_fails_explicitly(monkeypatch):
    patient = [PatientRadionuclideDemand("P1", "F-18", 200.0)]
    traces = [
        ProductionClinicalPatientTrace("P1", "F-18", 1, 1, 0.0, 30.0, 35.0, 1, 35.0, 40.0, 40.0, 45.0, 45.0, 90.0, 90.0, 110.0, True)
    ]

    monkeypatch.setattr("multi_isotope_decay._half_life_lookup", lambda: {"Ga-68": 67.7})
    with pytest.raises(ValueError, match="Missing radionuclide half-life physics"):
        evaluate_pathway_decay(pathway="Conventional", generated_patients=patient, patient_traces=traces)


def test_decay_feasibility_guard_marks_infeasible_patient_without_astronomical_back_calculation():
    patient = [PatientRadionuclideDemand("P1", "O-15", 160.0)]
    traces = [
        ProductionClinicalPatientTrace("P1", "O-15", 1, 1, 0.0, 10.0, 10.0, 1, 10.0, 12.0, 40.0, 90.0, 90.0, 120.0, 120.0, 140.0, True)
    ]

    summary = evaluate_pathway_decay(
        pathway="Conventional",
        generated_patients=patient,
        patient_traces=traces,
        min_retained_fraction_for_feasibility=0.10,
    )
    trace = summary.patient_traces[0]

    assert not trace.decay_feasible
    assert trace.decay_infeasibility_reason is not None
    assert trace.activity_at_injection_mbq < trace.prescribed_activity_mbq
    assert trace.activity_at_eob_mbq == 0.0
    assert trace.required_upstream_activity_for_prescribed_mbq == 0.0
    assert trace.physical_decay_loss_before_administration_mbq == 0.0
    assert trace.unmet_prescribed_activity_mbq > 0.0
    assert summary.decay_infeasible_patient_count == 1
    assert summary.decay_infeasible_by_isotope["O-15"] == 1


def test_decision_pipeline_uses_same_patient_realization_for_both_pathways_and_is_decay_aware():
    result = run_native_decision_pipeline(_request(seed=20260813))
    demand_patients = result.demand_result.simulation.generated_demand.patients

    conventional_ids = [trace.patient_id for trace in result.conventional.decay_summary.patient_traces]
    mrt_ids = [trace.patient_id for trace in result.mrt.decay_summary.patient_traces]

    assert conventional_ids == [patient.patient_id for patient in demand_patients]
    assert mrt_ids == [patient.patient_id for patient in demand_patients]
    assert result.conventional.decay_summary.total_patients == result.mrt.decay_summary.total_patients


def test_reliability_engine_preserves_decay_metrics_across_seeds():
    request = _request(seed=20260813)
    result = run_native_reliability_engine(request, seeds=(101, 102, 103))

    assert result.conventional.decay_loss_distribution_mbq.run_count == 3
    assert result.mrt.decay_loss_distribution_mbq.run_count == 3
    assert result.conventional.retained_fraction_distribution.run_count == 3
    assert result.mrt.retained_fraction_distribution.run_count == 3


def test_recommendation_exposes_decay_metrics_without_ranking_contract_change():
    template = _request(seed=20260813)
    request = ArchitectureRecommendationRequest(
        target_patients_per_day=template.target_patients_per_day,
        minimum_reliability=0.90,
        seeds=(101, 102),
        pipeline_template=template,
        conventional_bounds=ConventionalArchitectureBounds(
            scanners=(3, 4), injection_resources=(2,), uptake_resources=(7,), distribution_concurrency=(1,), transport_minutes=(6.5, 7.0)
        ),
        mrt_bounds=MrtArchitectureBounds(
            scanners=(5, 6), injection_resources=(3,), uptake_resources=(10,), distribution_concurrency=(2,), installed_mrt_endpoints=(2,), transport_minutes=(4.5, 5.0)
        ),
        max_candidate_count=16,
        throughput_thresholds_per_day=(template.target_patients_per_day,),
    )
    result = run_native_architecture_recommendation(request)
    candidates = result.conventional_candidates + result.mrt_candidates
    assert all(hasattr(candidate, "decay_total_loss_mbq") for candidate in candidates)
    assert all(hasattr(candidate, "decay_mean_retained_fraction") for candidate in candidates)


def test_report_contract_contains_decay_fields_and_tables():
    template = _request(seed=20260813)
    request = ArchitectureRecommendationRequest(
        target_patients_per_day=template.target_patients_per_day,
        minimum_reliability=0.90,
        seeds=(101, 102),
        pipeline_template=template,
        conventional_bounds=ConventionalArchitectureBounds(
            scanners=(3, 4), injection_resources=(2,), uptake_resources=(7,), distribution_concurrency=(1,), transport_minutes=(6.5, 7.0)
        ),
        mrt_bounds=MrtArchitectureBounds(
            scanners=(5, 6), injection_resources=(3,), uptake_resources=(10,), distribution_concurrency=(2,), installed_mrt_endpoints=(2,), transport_minutes=(4.5, 5.0)
        ),
        max_candidate_count=16,
        throughput_thresholds_per_day=(template.target_patients_per_day,),
    )
    recommendation = run_native_architecture_recommendation(request)
    report = build_native_architecture_report_data(recommendation)

    for pathway_report in report.reportable_pathway_reports:
        assert pathway_report.isotope_decay_summary_rows
        assert pathway_report.batch_decay_summary_rows
        assert pathway_report.chart_data.retained_activity_by_patient
        assert pathway_report.chart_data.decay_loss_by_isotope
        assert pathway_report.chart_data.decay_loss_by_batch
        assert pathway_report.chart_data.elapsed_time_vs_retained_fraction
        sample = pathway_report.patient_records[0]
        assert sample.elapsed_decay_time_minutes >= 0.0
        assert 0.0 <= sample.retained_fraction_at_administration <= 1.0
        assert sample.activity_at_injection_mbq >= 0.0


def test_extended_isotope_pipeline_support_includes_n13_c11_o15():
    result = run_native_decision_pipeline(_request(seed=20260813, include_extended=True))
    observed_isotopes = set(result.demand_result.patient_ids_by_radionuclide)
    assert {"F-18", "Ga-68", "N-13", "C-11", "O-15"}.issubset(observed_isotopes)
    assert set(result.conventional.decay_summary.total_prescribed_activity_mbq_by_isotope).issuperset({"F-18", "Ga-68", "N-13", "C-11", "O-15"})

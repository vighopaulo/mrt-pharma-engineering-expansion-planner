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
from decision_pipeline import NativeDecisionPipelineScenario, NativePathwayScenario
from models import PlannerAssumptions, SharedNetworkAssumptions
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


def _activity_models() -> dict[str, ActivityDemandModel]:
    return {
        "F-18": ActivityDemandModel(
            "bounded_normal",
            mean_activity_mbq=200.0,
            stddev_activity_mbq=20.0,
            lower_bound_mbq=160.0,
            upper_bound_mbq=240.0,
        ),
        "Ga-68": ActivityDemandModel(
            "bounded_normal",
            mean_activity_mbq=150.0,
            stddev_activity_mbq=15.0,
            lower_bound_mbq=120.0,
            upper_bound_mbq=180.0,
        ),
        "Tc-99m": ActivityDemandModel(
            "bounded_normal",
            mean_activity_mbq=600.0,
            stddev_activity_mbq=40.0,
            lower_bound_mbq=500.0,
            upper_bound_mbq=700.0,
        ),
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


def _pipeline_template(*, seed: int = 20260813) -> NativeDecisionPipelineScenario:
    return NativeDecisionPipelineScenario(
        project_name="Native Architecture Report",
        target_patients_per_day=200,
        radionuclide_mix={"F-18": 0.60, "Ga-68": 0.25, "Tc-99m": 0.15},
        activity_distribution_by_radionuclide=_activity_models(),
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="PIPELINE-DUAL",
            supported_radionuclides=("F-18", "Ga-68", "Tc-99m"),
            max_simultaneous_production_streams=2,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0, "Ga-68": 20.0, "Tc-99m": 25.0},
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


def _request() -> ArchitectureRecommendationRequest:
    return ArchitectureRecommendationRequest(
        target_patients_per_day=200,
        minimum_reliability=0.95,
        seeds=(101, 102),
        pipeline_template=replace(_pipeline_template(), target_patients_per_day=200),
        conventional_bounds=ConventionalArchitectureBounds(
            scanners=(3, 4),
            injection_resources=(2,),
            uptake_resources=(7,),
            distribution_concurrency=(1,),
            transport_minutes=(6.5, 7.0),
        ),
        mrt_bounds=MrtArchitectureBounds(
            scanners=(5, 6),
            injection_resources=(3,),
            uptake_resources=(10,),
            distribution_concurrency=(2,),
            installed_mrt_endpoints=(2,),
            transport_minutes=(4.5, 5.0),
        ),
        max_candidate_count=16,
        throughput_thresholds_per_day=(200.0,),
    )


def test_report_contract_reconciles_native_economics_and_patient_traces():
    recommendation = run_native_architecture_recommendation(_request())
    report = build_native_architecture_report_data(recommendation)

    assert report.provenance.recommendation_trace_id == recommendation.provenance.aggregate_trace_id
    assert len(report.recommendation_chart_data.npv_vs_reliability) == recommendation.candidate_count_evaluated
    assert len(report.recommendation_chart_data.capex_vs_reliable_throughput) == recommendation.candidate_count_evaluated
    assert len(report.reportable_pathway_reports) == sum(
        1
        for candidate in (
            recommendation.best_qualifying_conventional,
            recommendation.best_qualifying_mrt,
        )
        if candidate is not None
    )

    if report.selected_pathway_report is not None and recommendation.recommended_architecture is not None:
        assert report.selected_pathway_report.candidate_id == recommendation.recommended_architecture.candidate_id

    for pathway_report in report.reportable_pathway_reports:
        candidate = pathway_report.candidate_result
        assert pathway_report.economic_summary.initial_capex == pytest.approx(candidate.capex_result.total_capex)
        assert pathway_report.economic_summary.annual_opex == pytest.approx(candidate.opex_result.total_annual_opex)
        assert pathway_report.economic_summary.annual_revenue == pytest.approx(candidate.lifecycle_result.annual_rows[0].annual_revenue)
        assert pathway_report.economic_summary.annual_net_cash_flow == pytest.approx(candidate.lifecycle_result.annual_rows[0].annual_net_cash_flow)
        assert pathway_report.economic_summary.final_npv == pytest.approx(candidate.lifecycle_result.final_npv)
        assert pathway_report.economic_summary.payback_year == candidate.lifecycle_result.payback_year
        assert len(pathway_report.run_reports) == len(candidate.reliability_result.run_results)
        assert len(pathway_report.patient_records) == sum(len(run.patient_records) for run in pathway_report.run_reports)
        assert len(pathway_report.annual_cash_flow_rows) == candidate.lifecycle_result.analysis_years
        assert pathway_report.annual_cash_flow_rows[-1].cumulative_npv == pytest.approx(candidate.lifecycle_result.final_npv)

        for run_report in pathway_report.run_reports:
            native_run = next(run for run in candidate.reliability_result.run_results if run.seed == run_report.seed)
            expected_patients = native_run.native_result.demand_result.simulation.generated_demand.patients
            expected_traces = (
                native_run.native_result.conventional.operational_result.production_clinical_result.patient_traces
                if candidate.pathway == "Conventional"
                else native_run.native_result.mrt.operational_result.production_clinical_result.patient_traces
            )
            assert [record.patient_id for record in run_report.patient_records] == [patient.patient_id for patient in expected_patients]
            assert [record.radionuclide for record in run_report.patient_records] == [patient.radionuclide for patient in expected_patients]
            assert [record.completed_within_operating_day for record in run_report.patient_records] == [trace.completed_within_operating_day for trace in expected_traces]
            assert all(hasattr(record, "required_activity_at_eob_mbq") for record in run_report.patient_records)
            assert all(hasattr(record, "required_activity_at_release_mbq") for record in run_report.patient_records)
            assert all(hasattr(record, "decay_feasible") for record in run_report.patient_records)
            assert all(hasattr(record, "physical_decay_loss_before_administration_mbq") for record in run_report.patient_records)
            assert all(hasattr(record, "unmet_prescribed_activity_mbq") for record in run_report.patient_records)
            assert run_report.schedule_completed_patients >= run_report.effective_completed_patients
            assert run_report.completed_patients == run_report.effective_completed_patients
            assert run_report.incomplete_patients == run_report.scheduled_patients - run_report.effective_completed_patients

        assert all(row.feasible_patient_count + row.infeasible_patient_count == row.patient_count for row in pathway_report.isotope_decay_summary_rows)
        assert all(row.feasible_patient_count + row.infeasible_patient_count == row.patient_count for row in pathway_report.batch_decay_summary_rows)


def test_report_chart_series_are_derived_from_reported_data():
    recommendation = run_native_architecture_recommendation(_request())
    report = build_native_architecture_report_data(recommendation)

    for pathway_report in report.reportable_pathway_reports:
        assert sum(item.share for item in pathway_report.chart_data.capex_composition) == pytest.approx(1.0)
        assert sum(item.share for item in pathway_report.chart_data.opex_composition) == pytest.approx(1.0)
        assert sum(item.share for item in pathway_report.chart_data.isotope_mix) == pytest.approx(1.0)
        assert len(pathway_report.chart_data.stochastic_daily_completions) == len(pathway_report.run_reports)
        assert len(pathway_report.chart_data.annual_financials) == pathway_report.candidate_result.lifecycle_result.analysis_years
        assert pathway_report.chart_data.cumulative_discounted_cash_flow[-1].y == pytest.approx(pathway_report.candidate_result.lifecycle_result.final_npv)

    if report.best_qualifying_conventional_report is not None and report.best_qualifying_mrt_report is not None:
        conventional = report.best_qualifying_conventional_report
        mrt = report.best_qualifying_mrt_report
        assert conventional.incremental_economic_summary == mrt.incremental_economic_summary
        assert conventional.incremental_economic_summary is not None
        assert conventional.incremental_economic_summary.capex_delta == pytest.approx(
            mrt.economic_summary.initial_capex - conventional.economic_summary.initial_capex
        )

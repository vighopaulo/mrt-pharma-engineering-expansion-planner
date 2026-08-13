from __future__ import annotations

from dataclasses import replace
import math

import pytest

from cyclotron_production_windows import CyclotronProductionCapability
import decision_pipeline as pipeline_module
from decision_pipeline import (
    NativeDecisionPipelineScenario,
    NativePathwayScenario,
    run_native_decision_pipeline,
)
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


def _request(*, seed: int = 20260813) -> NativeDecisionPipelineScenario:
    return NativeDecisionPipelineScenario(
        project_name="Native Decision Pipeline",
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


def test_native_decision_pipeline_is_deterministic_for_same_seed():
    result_a = run_native_decision_pipeline(_request())
    result_b = run_native_decision_pipeline(_request())

    assert result_a == result_b
    assert result_a.provenance.comparison_trace_id == result_b.provenance.comparison_trace_id


def test_run_native_decision_pipeline_generates_demand_once_and_reuses_it(monkeypatch):
    original = pipeline_module.generate_design_day_demand
    call_count = {"count": 0}

    def counted_generate_design_day_demand(scenario):
        call_count["count"] += 1
        return original(scenario)

    monkeypatch.setattr(pipeline_module, "generate_design_day_demand", counted_generate_design_day_demand)

    result = run_native_decision_pipeline(_request())

    assert call_count["count"] == 1
    assert result.conventional.operational_result.demand_result is result.mrt.operational_result.demand_result
    assert result.conventional.operational_result.demand_result.simulation is result.mrt.operational_result.demand_result.simulation
    assert result.batch_policy_description.startswith("PIPELINE BATCH POLICY:")


def test_generated_patients_propagate_into_batching():
    result = run_native_decision_pipeline(_request())
    demand = result.demand_result.simulation

    assert demand.patient_count == len(demand.generated_demand.patients)
    assert sum(result.demand_result.requested_batch_count_by_radionuclide.values()) == len(result.demand_result.batch_demands)
    assert sum(batch.patient_count for batch in result.demand_result.batch_demands) == demand.patient_count


def test_pipeline_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="target_patients_per_day must be greater than zero"):
        NativeDecisionPipelineScenario(
            project_name="Native Decision Pipeline",
            target_patients_per_day=0,
            radionuclide_mix={"F-18": 0.60, "Ga-68": 0.25, "Tc-99m": 0.15},
            activity_distribution_by_radionuclide=_activity_models(),
            cyclotron_capability=_request().cyclotron_capability,
            conventional=_conventional_pathway(),
            mrt=_mrt_pathway(),
            planner_assumptions=_planner_assumptions(),
            shared_network_assumptions=SharedNetworkAssumptions(),
            day_type="typical",
            seed=20260813,
            operating_day_minutes=1080.0,
            batch_target_patients_per_batch=20,
        )

    with pytest.raises(ValueError, match="batch_target_patients_per_batch must be at least 1"):
        NativeDecisionPipelineScenario(
            project_name="Native Decision Pipeline",
            target_patients_per_day=200,
            radionuclide_mix={"F-18": 0.60, "Ga-68": 0.25, "Tc-99m": 0.15},
            activity_distribution_by_radionuclide=_activity_models(),
            cyclotron_capability=_request().cyclotron_capability,
            conventional=_conventional_pathway(),
            mrt=_mrt_pathway(),
            planner_assumptions=_planner_assumptions(),
            shared_network_assumptions=SharedNetworkAssumptions(),
            day_type="typical",
            seed=20260813,
            operating_day_minutes=1080.0,
            batch_target_patients_per_batch=0,
        )

    with pytest.raises(ValueError, match="pathway must be Conventional or MRT"):
        NativePathwayScenario(
            pathway="Invalid",  # type: ignore[arg-type]
            scanners=1,
            injection_resources=1,
            uptake_resources=1,
        )

    with pytest.raises(ValueError, match="radionuclide_mix must not be empty"):
        NativeDecisionPipelineScenario(
            project_name="Native Decision Pipeline",
            target_patients_per_day=200,
            radionuclide_mix={},
            activity_distribution_by_radionuclide={},
            cyclotron_capability=_request().cyclotron_capability,
            conventional=_conventional_pathway(),
            mrt=_mrt_pathway(),
            planner_assumptions=_planner_assumptions(),
            shared_network_assumptions=SharedNetworkAssumptions(),
            day_type="typical",
            seed=20260813,
            operating_day_minutes=1080.0,
            batch_target_patients_per_batch=20,
        )

    with pytest.raises(ValueError, match="Missing activity distribution"):
        run_native_decision_pipeline(
            NativeDecisionPipelineScenario(
                project_name="Native Decision Pipeline",
                target_patients_per_day=200,
                radionuclide_mix={"F-18": 0.5, "Ga-68": 0.5},
                activity_distribution_by_radionuclide={"F-18": _activity_models()["F-18"]},
                cyclotron_capability=_request().cyclotron_capability,
                conventional=_conventional_pathway(),
                mrt=_mrt_pathway(),
                planner_assumptions=_planner_assumptions(),
                shared_network_assumptions=SharedNetworkAssumptions(),
                day_type="typical",
                seed=20260813,
                operating_day_minutes=1080.0,
                batch_target_patients_per_batch=20,
            )
        )


def test_every_patient_has_one_auditable_isotope_batch_trace():
    result = run_native_decision_pipeline(_request())
    traces = result.conventional.operational_result.production_clinical_result.patient_traces
    batch_ids = {batch.batch_id for batch in result.conventional.operational_result.production_clinical_result.batch_demands}
    window_ids = {mapping.production_window_id for mapping in result.conventional.operational_result.production_clinical_result.batch_release_mappings}

    assert len(traces) == result.conventional.operational_result.patients_considered
    assert len({trace.patient_id for trace in traces}) == len(traces)
    for trace in traces:
        assert trace.radionuclide in result.demand_result.patient_ids_by_radionuclide
        assert trace.batch_id in batch_ids
        assert trace.production_window_id in window_ids
        assert trace.batch_release_time_minutes >= trace.production_window_end_time_minutes
        assert trace.scan_start >= trace.uptake_end


def test_every_batch_propagates_into_production_and_clinical_schedule():
    result = run_native_decision_pipeline(_request())
    operational = result.conventional.operational_result
    clinical = operational.production_clinical_result.clinical_schedule

    assert operational.patients_completed + operational.patients_incomplete == operational.patients_considered
    assert len(operational.production_clinical_result.batch_demands) == len(operational.production_clinical_result.batch_release_mappings)
    assert len(operational.production_clinical_result.batch_releases) == len(operational.production_clinical_result.batch_demands)
    assert clinical.completed_patients + clinical.uncompleted_patients == clinical.total_patients_considered


def test_actual_scheduler_completion_feeds_lifecycle_and_reconciles_ledger_values():
    result = run_native_decision_pipeline(_request())

    for pathway_result in (result.conventional, result.mrt):
        operational = pathway_result.operational_result
        lifecycle = pathway_result.lifecycle_result

        assert operational.schedule_completed_patients >= operational.decay_feasible_completed_patients
        assert operational.patients_completed == operational.decay_feasible_completed_patients
        assert math.isclose(pathway_result.actual_lifecycle_throughput_per_day, float(operational.patients_completed), rel_tol=0.0, abs_tol=1e-9)
        assert math.isclose(lifecycle.annual_rows[0].installed_capacity_per_day, float(operational.patients_completed), rel_tol=0.0, abs_tol=1e-9)
        assert math.isclose(pathway_result.annual_completed_scans, float(operational.patients_completed) * result.request.planner_assumptions.operating_days_per_year, rel_tol=0.0, abs_tol=1e-9)
        assert math.isclose(pathway_result.annual_revenue, pathway_result.annual_completed_scans * result.request.planner_assumptions.revenue_per_scan, rel_tol=0.0, abs_tol=1e-9)
        assert math.isclose(pathway_result.capex_result.total_capex, lifecycle.initial_capex, rel_tol=0.0, abs_tol=1e-9)
        assert math.isclose(pathway_result.opex_result.total_annual_opex, lifecycle.annual_rows[0].annual_opex, rel_tol=0.0, abs_tol=1e-9)


def test_decay_infeasible_patients_are_excluded_from_effective_revenue_throughput():
    request = _request(seed=20260813)
    guarded_request = replace(
        request,
        planner_assumptions=replace(request.planner_assumptions, decay_feasibility_min_retained_fraction=0.95),
    )
    result = run_native_decision_pipeline(guarded_request)

    any_infeasible = False
    for pathway_result in (result.conventional, result.mrt):
        operational = pathway_result.operational_result
        lifecycle = pathway_result.lifecycle_result

        any_infeasible = any_infeasible or operational.decay_infeasible_patients > 0
        assert operational.patients_completed == operational.decay_feasible_completed_patients
        assert operational.patients_incomplete == operational.scheduled_patients - operational.decay_feasible_completed_patients
        assert operational.decay_infeasible_patients == operational.scheduled_patients - operational.decay_feasible_scheduled_patients
        assert math.isclose(lifecycle.annual_rows[0].installed_capacity_per_day, float(operational.decay_feasible_completed_patients), rel_tol=0.0, abs_tol=1e-9)
        assert math.isclose(
            lifecycle.annual_rows[0].annual_revenue,
            float(operational.decay_feasible_completed_patients)
            * guarded_request.planner_assumptions.operating_days_per_year
            * guarded_request.planner_assumptions.revenue_per_scan,
            rel_tol=0.0,
            abs_tol=1e-9,
        )

    assert any_infeasible


def test_decay_outputs_do_not_apply_unsupported_blanket_opex_multipliers():
    result = run_native_decision_pipeline(_request())

    for pathway_result, pathway_config in (
        (result.conventional, result.request.conventional),
        (result.mrt, result.request.mrt),
    ):
        production_variable = next(item for item in pathway_result.opex_result.ledger if item.component == "Production variable cost")
        consumables = next(item for item in pathway_result.opex_result.ledger if item.component == "Consumables")
        cyclotron_energy = next(item for item in pathway_result.opex_result.ledger if item.component == "Cyclotron energy")

        assert production_variable.unit_cost == pytest.approx(pathway_config.annual_production_variable_cost)
        assert consumables.quantity == pytest.approx(pathway_config.annual_consumable_units)
        assert cyclotron_energy.quantity == pytest.approx(pathway_config.annual_cyclotron_energy_kwh)


def test_pathway_isolation_and_incremental_values_reconcile():
    result = run_native_decision_pipeline(_request())

    assert result.conventional.capex_result.mrt_specific_capex == 0.0
    assert result.conventional.opex_result.mrt_specific_opex == 0.0
    assert result.mrt.capex_result.conventional_specific_capex == 0.0
    assert result.mrt.opex_result.conventional_specific_opex == 0.0

    assert math.isclose(result.incremental_mrt_capex, result.mrt_capex - result.conventional_capex, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(result.incremental_mrt_opex, result.mrt_annual_opex - result.conventional_annual_opex, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(result.incremental_npv, result.mrt_lifecycle_result.final_npv - result.conventional_lifecycle_result.final_npv, rel_tol=0.0, abs_tol=1e-9)


def test_comparison_uses_identical_stochastic_patient_population():
    result = run_native_decision_pipeline(_request())

    assert result.conventional.operational_result.demand_result is result.mrt.operational_result.demand_result
    assert result.conventional.operational_result.demand_result.trace_id == result.mrt.operational_result.demand_result.trace_id
    assert result.request.seed == 20260813
    assert result.throughput_difference == result.mrt.operational_result.patients_completed - result.conventional.operational_result.patients_completed


def test_known_missing_capabilities_and_audit_are_reported():
    result = run_native_decision_pipeline(_request())

    audit = result.integration_audit
    assert audit.demand_to_patients == "DIRECT NATIVE CONNECTION"
    assert audit.patients_to_isotope_batching == "DIRECT NATIVE CONNECTION"
    assert audit.batches_to_production == "DIRECT NATIVE CONNECTION"
    assert audit.production_to_clinical_schedule == "DIRECT NATIVE CONNECTION (WITH PER-PATIENT DECAY TRACE)"
    assert audit.resource_quantities_to_capex == "DIRECT NATIVE CONNECTION"
    assert audit.resource_quantities_to_opex == "DIRECT NATIVE CONNECTION"
    assert audit.actual_clinical_completion_to_lifecycle_throughput == "DIRECT NATIVE CONNECTION"
    assert audit.capex_to_lifecycle == "DIRECT NATIVE CONNECTION"
    assert audit.opex_to_lifecycle == "DIRECT NATIVE CONNECTION"
    assert audit.lifecycle_to_conventional_mrt_comparison == "DIRECT NATIVE CONNECTION"

    assert "No spatially derived guideway length." in audit.missing_capabilities
    assert "No floor-area/floor-count resource placement." in audit.missing_capabilities
    assert "Decay physics is natively integrated, but direct monetization of activity loss requires an authoritative isotope-production cost model." in audit.missing_capabilities
    assert "No detailed MRT energy physics." in audit.missing_capabilities
    assert "No demand-driven staffing inference." in audit.missing_capabilities
    assert any("explicit batch_target_patients_per_batch" in warning for warning in result.warnings)


def test_end_to_end_200_patient_scenario_matches_native_comparison_expectations():
    result = run_native_decision_pipeline(_request())

    assert result.demand_result.simulation.patient_count == 200
    assert result.demand_result.simulation.patient_count_by_radionuclide == {"F-18": 106, "Ga-68": 50, "Tc-99m": 44}
    assert result.conventional.operational_result.patients_completed == 140
    assert result.mrt.operational_result.patients_completed == 200
    assert result.conventional.operational_result.bottleneck.resource == "distribution"
    assert result.mrt.operational_result.bottleneck.resource == "uptake"
    assert result.throughput_difference == 60
    assert result.economic_winner == "MRT"
    assert result.lifecycle_comparison_result is not None
    assert math.isclose(result.lifecycle_comparison_result.incremental_final_npv_mrt_minus_conventional, result.incremental_npv, rel_tol=0.0, abs_tol=1e-9)
    assert result.mrt_lifecycle_result.final_npv > result.conventional_lifecycle_result.final_npv

    conventional_decay = result.conventional.decay_summary
    mrt_decay = result.mrt.decay_summary
    for isotope, prescribed in conventional_decay.total_prescribed_activity_mbq_by_isotope.items():
        assert conventional_decay.total_activity_at_injection_mbq_by_isotope[isotope] <= prescribed
        assert mrt_decay.total_activity_at_injection_mbq_by_isotope[isotope] <= mrt_decay.total_prescribed_activity_mbq_by_isotope[isotope]
    assert conventional_decay.decay_infeasible_patient_count >= 0
    assert mrt_decay.decay_infeasible_patient_count >= 0

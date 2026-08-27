from __future__ import annotations

from dataclasses import replace
import math

import pytest

from cyclotron_production_windows import CyclotronProductionCapability
import decision_pipeline as pipeline_module
from decision_pipeline import (
    NativeDecisionPipelineScenario,
    NativePathwayScenario,
    run_native_conventional_only_pipeline,
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


def test_conventional_result_matches_between_dual_and_conventional_only_profiles():
    dual_request = _request()
    dual_result = run_native_decision_pipeline(dual_request)

    conventional_only_request = replace(dual_request, mrt=None, product_profile="CONVENTIONAL_ONLY")
    conventional_only_result = run_native_conventional_only_pipeline(conventional_only_request)

    dual_conv = dual_result.conventional
    solo_conv = conventional_only_result.conventional

    assert dual_conv.operational_result.pathway_config.transport_minutes == pytest.approx(
        solo_conv.operational_result.pathway_config.transport_minutes
    )
    assert dual_conv.operational_result.pathway_config.transport_minutes_source == (
        solo_conv.operational_result.pathway_config.transport_minutes_source
    )
    assert dual_conv.operational_result.patients_completed == solo_conv.operational_result.patients_completed
    assert dual_conv.decay_summary.mean_retained_fraction == pytest.approx(solo_conv.decay_summary.mean_retained_fraction)
    assert dual_conv.capex_result.total_capex == pytest.approx(solo_conv.capex_result.total_capex)
    assert dual_conv.opex_result.total_annual_opex == pytest.approx(solo_conv.opex_result.total_annual_opex)
    assert dual_conv.lifecycle_result.final_npv == pytest.approx(solo_conv.lifecycle_result.final_npv)


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
    assert len(operational.production_clinical_result.batch_releases) == len(operational.production_clinical_result.transport_payloads)
    assert len(operational.production_clinical_result.batch_releases) >= len(operational.production_clinical_result.batch_demands)
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
    assert result.conventional.operational_result.patients_completed == 147
    assert result.mrt.operational_result.patients_completed == 196
    assert result.conventional.operational_result.bottleneck.resource == "uptake"
    assert result.mrt.operational_result.bottleneck.resource == "carrier_transport"
    assert result.throughput_difference == 49
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


def test_requirement_derived_scheduler_allows_one_cycle_to_serve_more_than_20_patients() -> None:
    request = NativeDecisionPipelineScenario(
        project_name="Requirement Derived >20 One Cycle",
        target_patients_per_day=40,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=200.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-CAL",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 20_000.0},
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(_planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260901,
        operating_day_minutes=1080.0,
        production_start_time_minutes=500.0,
        batch_target_patients_per_batch=20,
    )
    result = run_native_decision_pipeline(request)
    assert result.demand_result.requested_batch_count_by_radionuclide["F-18"] == 1
    assert result.demand_result.activity_derived_cycle_count_by_radionuclide["F-18"] == 1
    assert result.demand_result.temporal_derived_cycle_count_by_radionuclide["F-18"] == 1


def test_requirement_derived_scheduler_can_require_multiple_cycles_for_fewer_than_20_patients() -> None:
    request = NativeDecisionPipelineScenario(
        project_name="Requirement Derived <20 Multi Cycle",
        target_patients_per_day=10,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=1000.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-CAL",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 4_000.0},
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(_planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260902,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )
    result = run_native_decision_pipeline(request)
    assert result.demand_result.requested_batch_count_by_radionuclide["F-18"] >= 3


def test_requirement_derived_temporal_separation_can_increase_required_cycles() -> None:
    base_request = NativeDecisionPipelineScenario(
        project_name="Requirement Derived Temporal",
        target_patients_per_day=12,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=200.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-CAL",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 20_000.0},
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(
            _planner_assumptions(),
            default_clinical_administration_cohorts_per_day=1,
            decay_feasibility_min_retained_fraction=0.10,
        ),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260903,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )
    single = run_native_decision_pipeline(base_request)
    multi = run_native_decision_pipeline(
        replace(
            base_request,
            planner_assumptions=replace(
                base_request.planner_assumptions,
                default_clinical_administration_cohorts_per_day=2,
            ),
        )
    )
    assert single.demand_result.requested_batch_count_by_radionuclide["F-18"] <= multi.demand_result.requested_batch_count_by_radionuclide["F-18"]


def test_required_activity_cycle_count_uses_required_eob_formula_for_blocker_case() -> None:
    assert pipeline_module._required_activity_cycle_count(2_380_785.0, 648_000.0) == 4


def test_required_activity_cycle_count_exact_boundary_two_cycles() -> None:
    assert pipeline_module._required_activity_cycle_count(2.0 * 648_000.0, 648_000.0) == 2


def test_requirement_derived_activity_can_dominate_temporal_cycle_count() -> None:
    # NOTE: calibrated capacity is set to 2_000.0 (not the original 12_000.0). Under
    # the corrected cycle-relative requirement (patient EOB computed relative to the
    # supplying cycle, not a common early EOB reference), 12_000.0 MBq comfortably
    # covers all 4 patients from a single freshest cycle. 2_000.0 MBq forces genuine
    # activity-capacity-driven splitting across multiple physically distinct cycles.
    request = NativeDecisionPipelineScenario(
        project_name="Activity Dominates",
        target_patients_per_day=4,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=600.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-ACT",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 120.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 2_000.0},
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(_planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260907,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )
    result = run_native_decision_pipeline(request)
    assert result.demand_result.activity_derived_cycle_count_by_radionuclide["F-18"] == 3
    assert result.demand_result.temporal_derived_cycle_count_by_radionuclide["F-18"] == 1
    assert result.demand_result.required_cycle_count_by_radionuclide["F-18"] == 3


def test_requirement_derived_temporal_cycles_can_dominate_activity_cycles() -> None:
    request = NativeDecisionPipelineScenario(
        project_name="Temporal Dominates",
        target_patients_per_day=12,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=100.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-TEMP",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 1_000_000.0},
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(
            _planner_assumptions(),
            default_clinical_administration_cohorts_per_day=2,
            decay_feasibility_min_retained_fraction=0.2,
        ),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260908,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )
    result = run_native_decision_pipeline(request)
    assert result.demand_result.activity_derived_cycle_count_by_radionuclide["F-18"] == 1
    assert result.demand_result.temporal_derived_cycle_count_by_radionuclide["F-18"] == 2
    assert result.demand_result.required_cycle_count_by_radionuclide["F-18"] == 2


def test_required_cycles_are_capped_by_the_configured_production_horizon() -> None:
    # NOTE: this test previously asserted a required_cycle_count of 4 derived from the
    # (now removed) common-early-EOB heuristic, which inflated aggregate demand well
    # beyond what these 8 patients actually need, forcing an artificial
    # PRODUCTION_SCHEDULE_CAPACITY shortfall against horizon [0, 360] at 120
    # minutes/cycle. Under the corrected cycle-relative requirement, patient EOB is
    # computed relative to the freshest cycle that can actually supply it, so this
    # demand comfortably fits in a single physically required cycle -- and that cycle
    # is never placed beyond the configured production horizon (section 18).
    request = NativeDecisionPipelineScenario(
        project_name="Required Capped By Horizon",
        target_patients_per_day=8,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=200.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-HZN",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 120.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 6_000.0},
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(_planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260909,
        operating_day_minutes=1080.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=360.0,
        batch_target_patients_per_batch=20,
    )
    result = run_native_decision_pipeline(request)

    assert result.demand_result.required_cycle_count_by_radionuclide["F-18"] == 1
    assert result.demand_result.unassigned_patient_ids_by_radionuclide["F-18"] == ()
    for pathway in (result.conventional, result.mrt):
        diag = pathway.operational_result.production_schedule_diagnostic
        assert diag.required_batch_count == 1
        assert diag.scheduled_batch_count == 1
        assert diag.unscheduled_batch_count == 0
        assert pathway.operational_result.primary_unmet_demand_cause == "NONE"


def test_cycle_relative_requirement_never_generates_candidate_cycles_beyond_configured_horizon() -> None:
    # Directly proves section 18: candidate production cycles must never be invented
    # beyond the configured production horizon, even when demand would benefit from more.
    request = NativeDecisionPipelineScenario(
        project_name="Horizon Is Authoritative",
        target_patients_per_day=8,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=200.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-HZN",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 120.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 2_000.0},
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(_planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260909,
        operating_day_minutes=1080.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=360.0,
        batch_target_patients_per_batch=20,
    )
    result = run_native_decision_pipeline(request)
    crr = result.demand_result.cycle_relative_requirement_by_radionuclide["F-18"]
    for usage in crr.cycle_usages:
        assert usage.eob_minutes <= 360.0 + 1e-9


def test_requirement_derived_multi_radionuclide_activity_authority_is_independent() -> None:
    request = NativeDecisionPipelineScenario(
        project_name="Independent Activity Authority",
        target_patients_per_day=12,
        radionuclide_mix={"F-18": 0.5, "C-11": 0.5},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=300.0),
            "C-11": ActivityDemandModel("fixed", fixed_activity_mbq=60.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="DUAL-INDEPENDENT",
            supported_radionuclides=("F-18", "C-11"),
            max_simultaneous_production_streams=2,
            production_cycle_minutes_by_radionuclide={"F-18": 120.0, "C-11": 30.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 8_000.0, "C-11": 2_000.0},
            simultaneously_compatible_radionuclide_sets=(frozenset({"F-18", "C-11"}),),
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(_planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260910,
        operating_day_minutes=1080.0,
        production_start_time_minutes=500.0,
        batch_target_patients_per_batch=20,
    )
    result = run_native_decision_pipeline(request)
    assert result.demand_result.activity_derived_cycle_count_by_radionuclide["F-18"] >= 1
    assert result.demand_result.activity_derived_cycle_count_by_radionuclide["C-11"] >= 1
    assert result.demand_result.required_eob_activity_mbq_by_radionuclide["F-18"] != result.demand_result.required_eob_activity_mbq_by_radionuclide["C-11"]


def test_legacy_fallback_remains_explicit_when_calibration_is_missing() -> None:
    request = NativeDecisionPipelineScenario(
        project_name="Legacy Fallback Explicit",
        target_patients_per_day=25,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=200.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-NO-CAL",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
            calibrated_eob_activity_mbq_by_radionuclide=None,
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(_planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260911,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )
    result = run_native_decision_pipeline(request)
    assert result.demand_result.required_cycle_count_by_radionuclide["F-18"] == 2
    assert result.demand_result.production_requirement_mode == "REQUIREMENT_DERIVED_WITH_LEGACY_COMPATIBILITY_BYPASS"
    assert any("LEGACY_COMPATIBILITY_BATCH_HEURISTIC_ACTIVE" in token for token in result.demand_result.production_requirement_bypasses)


def test_required_eob_reconciles_from_cycles_within_tolerance() -> None:
    request = NativeDecisionPipelineScenario(
        project_name="Cycle EOB Reconciliation",
        target_patients_per_day=8,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=200.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-RECON",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 120.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 6_000.0},
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(_planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260912,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )
    result = run_native_decision_pipeline(request)

    for pathway_result in (result.conventional, result.mrt):
        decay = pathway_result.decay_summary
        production = pathway_result.operational_result.production_clinical_result
        expected_total = float(decay.total_required_activity_at_eob_mbq_by_isotope["F-18"])
        by_cycle: dict[int, float] = {}
        for trace in decay.patient_traces:
            by_cycle[trace.batch_id] = by_cycle.get(trace.batch_id, 0.0) + float(trace.required_upstream_activity_for_prescribed_mbq)
        assert math.isclose(sum(by_cycle.values()), expected_total, rel_tol=0.0, abs_tol=1e-6)

        batch_map = {mapping.batch_id: mapping for mapping in production.batch_release_mappings}
        per_cycle_cap = request.cyclotron_capability.calibrated_eob_activity_mbq_by_radionuclide["F-18"]
        for batch_id, required_cycle_eob in by_cycle.items():
            if batch_id in batch_map:
                assert required_cycle_eob <= per_cycle_cap + 1e-6


def test_requirement_derived_unsupported_radionuclide_raises_explicit_failure() -> None:
    request = NativeDecisionPipelineScenario(
        project_name="Unsupported Isotope",
        target_patients_per_day=10,
        radionuclide_mix={"C-11": 1.0},
        activity_distribution_by_radionuclide={
            "C-11": ActivityDemandModel("fixed", fixed_activity_mbq=200.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-ONLY",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=_planner_assumptions(),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260904,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )
    with pytest.raises(ValueError, match="RADIONUCLIDE_NOT_SUPPORTED_BY_INSTALLED_FLEET"):
        run_native_decision_pipeline(request)


def test_requirement_derived_multi_radionuclide_production_is_separate_by_isotope() -> None:
    request = NativeDecisionPipelineScenario(
        project_name="Multi Isotope Requirement",
        target_patients_per_day=40,
        radionuclide_mix={"F-18": 0.5, "C-11": 0.5},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=200.0),
            "C-11": ActivityDemandModel("fixed", fixed_activity_mbq=220.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="DUAL",
            supported_radionuclides=("F-18", "C-11"),
            max_simultaneous_production_streams=2,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0, "C-11": 20.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 10_000.0, "C-11": 6_000.0},
            simultaneously_compatible_radionuclide_sets=(frozenset({"F-18", "C-11"}),),
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(_planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260905,
        operating_day_minutes=1080.0,
        production_start_time_minutes=500.0,
        batch_target_patients_per_batch=20,
    )
    result = run_native_decision_pipeline(request)
    isotopes = {batch.radionuclide for batch in result.demand_result.batch_demands}
    assert isotopes == {"F-18", "C-11"}
    assert result.demand_result.requested_batch_count_by_radionuclide["F-18"] > 0
    assert result.demand_result.requested_batch_count_by_radionuclide["C-11"] > 0


def test_requirement_derived_explicit_daily_capacity_limits_feasible_throughput() -> None:
    base = NativeDecisionPipelineScenario(
        project_name="Explicit Capacity",
        target_patients_per_day=30,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={
            "F-18": ActivityDemandModel("fixed", fixed_activity_mbq=300.0),
        },
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-CAP",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 20_000.0},
            site_eob_capacity_mbq_per_day=3_000.0,
        ),
        conventional=_conventional_pathway(),
        mrt=_mrt_pathway(),
        planner_assumptions=replace(_planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260906,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )
    constrained = run_native_decision_pipeline(base)
    unconstrained = run_native_decision_pipeline(
        replace(
            base,
            cyclotron_capability=replace(base.cyclotron_capability, site_eob_capacity_mbq_per_day=300_000.0),
        )
    )
    assert constrained.conventional.operational_result.primary_unmet_demand_cause == "PRODUCTION_ACTIVITY_CAPACITY"
    assert unconstrained.conventional.operational_result.patients_completed >= constrained.conventional.operational_result.patients_completed


def test_pathway_fairness_uses_same_patient_demand_and_can_differ_in_upstream_activity_due_to_timing() -> None:
    result = run_native_decision_pipeline(_request())
    assert result.conventional.operational_result.demand_result is result.mrt.operational_result.demand_result
    assert result.conventional.decay_summary.total_prescribed_activity_mbq_by_isotope == result.mrt.decay_summary.total_prescribed_activity_mbq_by_isotope
    any_difference = any(
        not math.isclose(
            result.conventional.decay_summary.total_required_activity_at_eob_mbq_by_isotope[iso],
            result.mrt.decay_summary.total_required_activity_at_eob_mbq_by_isotope[iso],
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        for iso in result.conventional.decay_summary.total_required_activity_at_eob_mbq_by_isotope
    )
    assert any_difference

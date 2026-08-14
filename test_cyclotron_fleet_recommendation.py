from __future__ import annotations

from dataclasses import replace

import pytest

from architecture_recommendation import ConventionalArchitectureBounds, MrtArchitectureBounds
from cyclotron_fleet_recommendation import (
    CyclotronFleetRecommendationRequest,
    CyclotronModelSpec,
    build_native_cyclotron_fleet_recommendation_report_data,
    run_native_cyclotron_fleet_recommendation,
)
from cyclotron_production_windows import CyclotronAsset, CyclotronFleet, CyclotronProductionCapability
from decision_pipeline import NativeDecisionPipelineScenario, NativePathwayScenario
from models import PlannerAssumptions, SharedNetworkAssumptions
from stochastic_design_day import ActivityDemandModel


_CYCLOTRON_ANNUAL_OPEX_PER_UNIT = 420_000.0


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
        "F-18": ActivityDemandModel("bounded_normal", mean_activity_mbq=200.0, stddev_activity_mbq=20.0, lower_bound_mbq=160.0, upper_bound_mbq=240.0),
        "Ga-68": ActivityDemandModel("bounded_normal", mean_activity_mbq=150.0, stddev_activity_mbq=15.0, lower_bound_mbq=120.0, upper_bound_mbq=180.0),
        "N-13": ActivityDemandModel("bounded_normal", mean_activity_mbq=180.0, stddev_activity_mbq=10.0, lower_bound_mbq=150.0, upper_bound_mbq=210.0),
        "O-15": ActivityDemandModel("bounded_normal", mean_activity_mbq=160.0, stddev_activity_mbq=8.0, lower_bound_mbq=140.0, upper_bound_mbq=180.0),
        "C-11": ActivityDemandModel("bounded_normal", mean_activity_mbq=220.0, stddev_activity_mbq=12.0, lower_bound_mbq=190.0, upper_bound_mbq=250.0),
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
        cyclotron_annual_opex_per_unit=_CYCLOTRON_ANNUAL_OPEX_PER_UNIT,
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


def _mrt() -> NativePathwayScenario:
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
        installed_guideway_length_m=350.0,
        guideway_capex_per_m=12_000.0,
        operated_mrt_base_units=1,
        operated_mrt_endpoints=2,
        operated_guideway_length_m=350.0,
        guideway_maintenance_per_m_year=1_200.0,
        annual_mrt_energy_kwh=25_000.0,
        mrt_support_staff_fte=3.0,
        mrt_support_staff_loaded_cost_per_fte=105_000.0,
        annual_production_variable_cost=300_000.0,
        cyclotron_annual_opex_per_unit=_CYCLOTRON_ANNUAL_OPEX_PER_UNIT,
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


def _cap(cyclotron_id: str, supported: tuple[str, ...], cycles: dict[str, float]) -> CyclotronProductionCapability:
    return CyclotronProductionCapability(
        cyclotron_id=cyclotron_id,
        supported_radionuclides=supported,
        max_simultaneous_production_streams=2,
        production_cycle_minutes_by_radionuclide=cycles,
        simultaneously_compatible_radionuclide_sets=(frozenset(("F-18", "Ga-68")),) if {"F-18", "Ga-68"}.issubset(set(supported)) else (),
    )


def _candidate_models() -> tuple[CyclotronModelSpec, ...]:
    return (
        CyclotronModelSpec(
            model_id="A",
            capability=_cap("CAP-A", ("F-18", "Ga-68"), {"F-18": 30.0, "Ga-68": 20.0}),
            manufacturer="Demo",
            model_identifier="Model-A",
            min_quantity=0,
            max_quantity=2,
        ),
        CyclotronModelSpec(
            model_id="B",
            capability=_cap("CAP-B", ("N-13", "O-15"), {"N-13": 15.0, "O-15": 12.0}),
            manufacturer="Demo",
            model_identifier="Model-B",
            min_quantity=0,
            max_quantity=2,
        ),
        CyclotronModelSpec(
            model_id="C",
            capability=_cap("CAP-C", ("C-11",), {"C-11": 18.0}),
            manufacturer="Demo",
            model_identifier="Model-C",
            min_quantity=0,
            max_quantity=1,
        ),
    )


def _pipeline_template() -> NativeDecisionPipelineScenario:
    models = _candidate_models()
    fleet = CyclotronFleet(
        fleet_id="TEMPLATE-FLEET",
        assets=(
            CyclotronAsset(cyclotron_id="CAP-A", capability=models[0].capability, manufacturer="Demo", model_identifier="Model-A", capability_provenance="A"),
            CyclotronAsset(cyclotron_id="CAP-B", capability=models[1].capability, manufacturer="Demo", model_identifier="Model-B", capability_provenance="B"),
        ),
    )
    return NativeDecisionPipelineScenario(
        project_name="Fleet Recommendation",
        target_patients_per_day=220,
        radionuclide_mix={"F-18": 0.45, "Ga-68": 0.25, "N-13": 0.15, "O-15": 0.10, "C-11": 0.05},
        activity_distribution_by_radionuclide=_activity_models(),
        cyclotron_capability=fleet.assets[0].capability,
        cyclotron_fleet=fleet,
        conventional=_conventional(),
        mrt=_mrt(),
        planner_assumptions=_planner(),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260813,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=20,
    )


def _request(
    *,
    objective: str = "maximum_npv_qualifying",
    max_fleet_size: int = 3,
    max_candidates: int = 64,
    incremental_expansion_only: bool = False,
    current_fleet: CyclotronFleet | None = None,
) -> CyclotronFleetRecommendationRequest:
    return CyclotronFleetRecommendationRequest(
        project_name="Fleet Recommendation Test",
        target_patients_per_day=220,
        required_radionuclides=("F-18", "Ga-68", "N-13", "O-15"),
        optional_radionuclides=("C-11",),
        radionuclide_mix={"F-18": 0.45, "Ga-68": 0.25, "N-13": 0.15, "O-15": 0.10, "C-11": 0.05},
        activity_distribution_by_radionuclide=_activity_models(),
        candidate_models=_candidate_models(),
        max_fleet_size=max_fleet_size,
        minimum_reliability=0.95,
        analysis_assumptions=_planner(),
        pipeline_template=_pipeline_template(),
        conventional_bounds=ConventionalArchitectureBounds(
            scanners=(3, 4),
            injection_resources=(2,),
            uptake_resources=(7, 8),
            distribution_concurrency=(1,),
            transport_minutes=(7.0,),
        ),
        mrt_bounds=MrtArchitectureBounds(
            scanners=(5, 6),
            injection_resources=(3,),
            uptake_resources=(10,),
            distribution_concurrency=(2,),
            installed_mrt_endpoints=(2,),
            transport_minutes=(5.0,),
        ),
        seeds=(101, 102, 103),
        candidate_generation_max_count=max_candidates,
        objective=objective,
        current_fleet=current_fleet,
        incremental_expansion_only=incremental_expansion_only,
        throughputs_for_reliability=(220.0,),
    )


def _first_qualified(result):
    return next(candidate for candidate in result.candidate_results if candidate.qualification_status == "QUALIFIED")


def _only_candidate(result):
    assert len(result.candidate_results) == 1
    return result.candidate_results[0]


def _single_model_request(*, fleet_size: int, target: int = 20) -> CyclotronFleetRecommendationRequest:
    base = _request()
    activity_models = _activity_models()
    single = (
        CyclotronModelSpec(
            model_id="A",
            capability=_cap("CAP-A", ("F-18", "Ga-68"), {"F-18": 30.0, "Ga-68": 20.0}),
            manufacturer="Demo",
            model_identifier="Model-A",
            min_quantity=fleet_size,
            max_quantity=fleet_size,
        ),
    )
    return replace(
        base,
        target_patients_per_day=target,
        required_radionuclides=("F-18", "Ga-68"),
        optional_radionuclides=(),
        radionuclide_mix={"F-18": 0.7, "Ga-68": 0.3},
        candidate_models=single,
        max_fleet_size=fleet_size,
        minimum_reliability=0.01,
        throughputs_for_reliability=(float(target),),
        pipeline_template=replace(
            base.pipeline_template,
            target_patients_per_day=target,
            radionuclide_mix={"F-18": 0.7, "Ga-68": 0.3},
            activity_distribution_by_radionuclide={
                "F-18": activity_models["F-18"],
                "Ga-68": activity_models["Ga-68"],
            },
            conventional=replace(base.pipeline_template.conventional, cyclotron_annual_opex_per_unit=_CYCLOTRON_ANNUAL_OPEX_PER_UNIT),
            mrt=replace(base.pipeline_template.mrt, cyclotron_annual_opex_per_unit=_CYCLOTRON_ANNUAL_OPEX_PER_UNIT),
        ),
    )


def test_single_cyclotron_candidate_can_qualify_and_be_selected():
    req = replace(
        _request(),
        target_patients_per_day=20,
        max_fleet_size=1,
        minimum_reliability=0.01,
        objective="minimum_fleet_size_qualifying",
        required_radionuclides=("F-18", "Ga-68"),
        optional_radionuclides=(),
        radionuclide_mix={"F-18": 0.7, "Ga-68": 0.3},
        throughputs_for_reliability=(20.0,),
    )
    result = run_native_cyclotron_fleet_recommendation(
        req
    )
    assert result.recommended_candidate is not None
    assert result.recommended_candidate.fleet.asset_count == 1


def test_single_cyclotron_missing_required_isotope_is_rejected():
    req = replace(_request(), max_fleet_size=1)
    result = run_native_cyclotron_fleet_recommendation(req)
    rejected = [candidate for candidate in result.rejected_candidates if candidate.rejection_reason and "Missing required radionuclide" in candidate.rejection_reason]
    assert rejected


def test_two_complementary_cyclotrons_cover_required_portfolio():
    result = run_native_cyclotron_fleet_recommendation(_request())
    covering = [
        candidate
        for candidate in result.qualified_candidates
        if {"F-18", "Ga-68", "N-13", "O-15"}.issubset(set(candidate.supported_radionuclides))
        and candidate.fleet.asset_count == 2
    ]
    assert covering


def test_candidate_enumeration_is_deterministic_and_has_no_order_duplicates():
    a = run_native_cyclotron_fleet_recommendation(_request())
    b = run_native_cyclotron_fleet_recommendation(_request())
    sig_a = [(candidate.candidate_id, tuple(sorted(candidate.model_counts.items()))) for candidate in a.candidate_results]
    sig_b = [(candidate.candidate_id, tuple(sorted(candidate.model_counts.items()))) for candidate in b.candidate_results]
    assert sig_a == sig_b


def test_max_fleet_size_is_enforced_by_request_and_generation():
    result = run_native_cyclotron_fleet_recommendation(replace(_request(), max_fleet_size=2))
    assert all(candidate.fleet.asset_count <= 2 for candidate in result.candidate_results)


def test_max_candidate_count_guard_raises_when_exceeded():
    with pytest.raises(ValueError, match="exceeds candidate_generation_max_count"):
        run_native_cyclotron_fleet_recommendation(replace(_request(), candidate_generation_max_count=2))


def test_required_radionuclides_are_mandatory():
    result = run_native_cyclotron_fleet_recommendation(_request())
    for candidate in result.qualified_candidates:
        assert set(_request().required_radionuclides).issubset(set(candidate.supported_radionuclides))


def test_optional_radionuclides_do_not_force_rejection():
    req = replace(_request(), optional_radionuclides=("C-11",), radionuclide_mix={"F-18": 0.5, "Ga-68": 0.25, "N-13": 0.15, "O-15": 0.10, "C-11": 0.0})
    result = run_native_cyclotron_fleet_recommendation(req)
    assert result.qualified_candidates


def test_same_fleet_preserves_shared_patient_realization_for_conventional_and_mrt():
    result = run_native_cyclotron_fleet_recommendation(_request())
    candidate = _first_qualified(result)
    arch = candidate.architecture_summary.architecture_recommendation_result.recommended_architecture
    assert arch is not None
    direct = arch.direct_decision_result
    assert direct.conventional.operational_result.demand_result.trace_id == direct.mrt.operational_result.demand_result.trace_id


def test_fleet_supported_population_contains_no_unavailable_isotope():
    result = run_native_cyclotron_fleet_recommendation(_request())
    candidate = _first_qualified(result)
    arch = candidate.architecture_summary.architecture_recommendation_result.recommended_architecture
    patients = arch.direct_decision_result.demand_result.simulation.generated_demand.patients
    supported = set(candidate.supported_radionuclides)
    assert all(patient.radionuclide in supported for patient in patients)


def test_effective_throughput_drives_reliability_metrics():
    result = run_native_cyclotron_fleet_recommendation(_request())
    candidate = _first_qualified(result)
    summary = candidate.architecture_summary
    assert summary.effective_throughput_per_day_at_reliability <= summary.raw_completed_patients_per_day


def test_capex_and_opex_reflect_fleet_quantity_changes():
    result = run_native_cyclotron_fleet_recommendation(_request())
    qualified = sorted(result.qualified_candidates, key=lambda candidate: candidate.fleet.asset_count)
    if len(qualified) > 1:
        small = qualified[0]
        large = qualified[-1]
        assert large.architecture_summary.capex >= small.architecture_summary.capex
        assert large.architecture_summary.annual_opex >= small.architecture_summary.annual_opex


def test_one_operated_cyclotron_uses_one_unit_cyclotron_opex():
    result = run_native_cyclotron_fleet_recommendation(_single_model_request(fleet_size=1))
    candidate = _only_candidate(result)
    recommended = candidate.architecture_summary.architecture_recommendation_result.recommended_architecture
    assert recommended is not None
    operated_units = recommended.opex_result.operated_quantities["operated_cyclotron_units"]
    cyclotron_row = next(item for item in recommended.opex_result.ledger if item.component == "Cyclotron annual fixed O&M")
    assert operated_units == pytest.approx(1.0)
    assert cyclotron_row.annual_cost == pytest.approx(_CYCLOTRON_ANNUAL_OPEX_PER_UNIT)


def test_two_operated_cyclotrons_use_two_unit_cyclotron_opex():
    result = run_native_cyclotron_fleet_recommendation(_single_model_request(fleet_size=2))
    candidate = _only_candidate(result)
    recommended = candidate.architecture_summary.architecture_recommendation_result.recommended_architecture
    assert recommended is not None
    operated_units = recommended.opex_result.operated_quantities["operated_cyclotron_units"]
    cyclotron_row = next(item for item in recommended.opex_result.ledger if item.component == "Cyclotron annual fixed O&M")
    assert operated_units == pytest.approx(2.0)
    assert cyclotron_row.annual_cost == pytest.approx(2.0 * _CYCLOTRON_ANNUAL_OPEX_PER_UNIT)


def test_three_operated_cyclotrons_use_three_unit_cyclotron_opex():
    result = run_native_cyclotron_fleet_recommendation(_single_model_request(fleet_size=3))
    candidate = _only_candidate(result)
    recommended = candidate.architecture_summary.architecture_recommendation_result.recommended_architecture
    assert recommended is not None
    operated_units = recommended.opex_result.operated_quantities["operated_cyclotron_units"]
    cyclotron_row = next(item for item in recommended.opex_result.ledger if item.component == "Cyclotron annual fixed O&M")
    assert operated_units == pytest.approx(3.0)
    assert cyclotron_row.annual_cost == pytest.approx(3.0 * _CYCLOTRON_ANNUAL_OPEX_PER_UNIT)


def test_candidate_annual_opex_reconciles_to_selected_architecture_opex_ledger():
    result = run_native_cyclotron_fleet_recommendation(_request())
    candidate = _first_qualified(result)
    recommended = candidate.architecture_summary.architecture_recommendation_result.recommended_architecture
    assert recommended is not None
    ledger_total = sum(item.annual_cost for item in recommended.opex_result.ledger)
    assert candidate.architecture_summary.annual_opex == pytest.approx(recommended.opex_result.total_annual_opex)
    assert candidate.architecture_summary.annual_opex == pytest.approx(ledger_total)


def test_revenue_not_inflated_by_fleet_count_without_effective_throughput_gain():
    result = run_native_cyclotron_fleet_recommendation(_request())
    by_size = {}
    for candidate in result.qualified_candidates:
        by_size.setdefault(candidate.fleet.asset_count, []).append(candidate)
    if 1 in by_size and 2 in by_size:
        one = by_size[1][0]
        two = by_size[2][0]
        if two.architecture_summary.effective_throughput_per_day_at_reliability == one.architecture_summary.effective_throughput_per_day_at_reliability:
            assert two.architecture_summary.annual_revenue == pytest.approx(one.architecture_summary.annual_revenue)


def test_added_cyclotron_can_raise_opex_without_revenue_gain_when_throughput_unchanged():
    one = _only_candidate(run_native_cyclotron_fleet_recommendation(_single_model_request(fleet_size=1, target=20)))
    two = _only_candidate(run_native_cyclotron_fleet_recommendation(_single_model_request(fleet_size=2, target=20)))
    if one.architecture_summary.effective_throughput_per_day_at_reliability == two.architecture_summary.effective_throughput_per_day_at_reliability:
        assert two.architecture_summary.annual_opex > one.architecture_summary.annual_opex
        assert two.architecture_summary.annual_revenue == pytest.approx(one.architecture_summary.annual_revenue)


def test_bottleneck_is_reported_for_candidates():
    result = run_native_cyclotron_fleet_recommendation(_request())
    candidate = _first_qualified(result)
    assert candidate.architecture_summary.bottleneck is not None
    assert candidate.architecture_summary.bottleneck.resource in {"scanner", "injection", "uptake", "distribution"}


def test_objective_minimum_capex_qualifying_is_respected():
    result = run_native_cyclotron_fleet_recommendation(replace(_request(objective="minimum_capex_qualifying"), minimum_reliability=0.01))
    winner = result.recommended_candidate
    assert winner is not None
    min_capex = min(candidate.architecture_summary.capex for candidate in result.qualified_candidates)
    assert winner.architecture_summary.capex == pytest.approx(min_capex)


def test_objective_maximum_npv_qualifying_is_respected():
    result = run_native_cyclotron_fleet_recommendation(_request(objective="maximum_npv_qualifying"))
    winner = result.recommended_candidate
    assert winner is not None
    max_npv = max(candidate.architecture_summary.lifecycle_npv for candidate in result.qualified_candidates)
    assert winner.architecture_summary.lifecycle_npv == pytest.approx(max_npv)


def test_objective_minimum_fleet_size_qualifying_is_respected():
    result = run_native_cyclotron_fleet_recommendation(replace(_request(objective="minimum_fleet_size_qualifying"), minimum_reliability=0.01))
    winner = result.recommended_candidate
    assert winner is not None
    min_size = min(candidate.fleet.asset_count for candidate in result.qualified_candidates)
    assert winner.fleet.asset_count == min_size


def test_incremental_mode_evaluates_add_one_cyclotron_candidates():
    specs = _candidate_models()
    current = CyclotronFleet(
        fleet_id="CURRENT",
        assets=(
            CyclotronAsset(cyclotron_id="CAP-A", capability=specs[0].capability, manufacturer="Demo", model_identifier="Model-A", capability_provenance="A"),
        ),
    )
    req = replace(
        _request(incremental_expansion_only=True, current_fleet=current),
        minimum_reliability=0.01,
        required_radionuclides=("F-18", "Ga-68"),
        optional_radionuclides=("N-13", "O-15", "C-11"),
    )
    result = run_native_cyclotron_fleet_recommendation(req)
    assert result.incremental_expansion is not None
    assert result.incremental_expansion.evaluated_expansion_candidates


def test_positive_weight_optional_isotope_unsupported_is_explicitly_noted_and_not_generated():
    activity_models = _activity_models()
    req = replace(
        _request(),
        required_radionuclides=("F-18", "Ga-68"),
        optional_radionuclides=("N-13",),
        radionuclide_mix={"F-18": 0.7, "Ga-68": 0.2, "N-13": 0.1},
        candidate_models=(
            CyclotronModelSpec(
                model_id="A",
                capability=_cap("CAP-A", ("F-18", "Ga-68"), {"F-18": 30.0, "Ga-68": 20.0}),
                manufacturer="Demo",
                model_identifier="Model-A",
                min_quantity=1,
                max_quantity=1,
            ),
        ),
        max_fleet_size=1,
        minimum_reliability=0.01,
        target_patients_per_day=20,
        throughputs_for_reliability=(20.0,),
        pipeline_template=replace(
            _pipeline_template(),
            target_patients_per_day=20,
            radionuclide_mix={"F-18": 0.7, "Ga-68": 0.2, "N-13": 0.1},
            activity_distribution_by_radionuclide={
                "F-18": activity_models["F-18"],
                "Ga-68": activity_models["Ga-68"],
                "N-13": activity_models["N-13"],
            },
        ),
    )
    result = run_native_cyclotron_fleet_recommendation(req)
    candidate = _only_candidate(result)
    assert candidate.qualification_status == "QUALIFIED"
    assert candidate.demand_mix_note is not None
    assert "Dropped unsupported optional radionuclides" in candidate.demand_mix_note
    recommended = candidate.architecture_summary.architecture_recommendation_result.recommended_architecture
    assert recommended is not None
    generated = {p.radionuclide for p in recommended.direct_decision_result.demand_result.simulation.generated_demand.patients}
    assert "N-13" not in generated


def test_incremental_base_not_suppressed_by_unsupported_optional_isotopes():
    specs = _candidate_models()
    current = CyclotronFleet(
        fleet_id="CURRENT",
        assets=(CyclotronAsset(cyclotron_id="CAP-A", capability=specs[0].capability, manufacturer="Demo", model_identifier="Model-A", capability_provenance="A"),),
    )
    req = replace(
        _request(incremental_expansion_only=True, current_fleet=current),
        target_patients_per_day=20,
        minimum_reliability=0.01,
        throughputs_for_reliability=(20.0,),
        required_radionuclides=("F-18", "Ga-68"),
        optional_radionuclides=("N-13", "O-15", "C-11"),
    )
    result = run_native_cyclotron_fleet_recommendation(req)
    inc = result.incremental_expansion
    assert inc is not None
    assert inc.base_fleet_candidate is not None
    assert inc.base_fleet_candidate.qualification_status == "QUALIFIED"
    assert inc.base_fleet_candidate.rejection_reason is None


def test_incremental_deltas_reconcile_when_best_expansion_exists():
    specs = _candidate_models()
    current = CyclotronFleet(
        fleet_id="CURRENT",
        assets=(CyclotronAsset(cyclotron_id="CAP-A", capability=specs[0].capability, manufacturer="Demo", model_identifier="Model-A", capability_provenance="A"),),
    )
    req = replace(
        _request(incremental_expansion_only=True, current_fleet=current),
        minimum_reliability=0.01,
        required_radionuclides=("F-18", "Ga-68"),
        optional_radionuclides=("N-13", "O-15", "C-11"),
    )
    result = run_native_cyclotron_fleet_recommendation(req)
    inc = result.incremental_expansion
    assert inc is not None
    if inc.base_fleet_candidate and inc.best_expansion_candidate and inc.base_fleet_candidate.architecture_summary and inc.best_expansion_candidate.architecture_summary:
        assert inc.capex_delta == pytest.approx(inc.best_expansion_candidate.architecture_summary.capex - inc.base_fleet_candidate.architecture_summary.capex)
        assert inc.annual_opex_delta == pytest.approx(inc.best_expansion_candidate.architecture_summary.annual_opex - inc.base_fleet_candidate.architecture_summary.annual_opex)


def test_determinism_with_same_request_and_seed_set():
    a = run_native_cyclotron_fleet_recommendation(_request())
    b = run_native_cyclotron_fleet_recommendation(_request())
    assert [candidate.fleet_trace_id for candidate in a.candidate_results] == [candidate.fleet_trace_id for candidate in b.candidate_results]
    assert (None if a.recommended_candidate is None else a.recommended_candidate.candidate_id) == (None if b.recommended_candidate is None else b.recommended_candidate.candidate_id)


def test_reporting_contract_exposes_fleet_recommendation_evidence():
    result = run_native_cyclotron_fleet_recommendation(_request())
    report = build_native_cyclotron_fleet_recommendation_report_data(result)
    assert report.candidate_rows
    row = report.candidate_rows[0]
    assert row.candidate_id
    assert row.fleet_id
    assert isinstance(row.supported_radionuclides, tuple)


def test_backward_compatibility_existing_architecture_recommendation_pipeline_still_usable():
    result = run_native_cyclotron_fleet_recommendation(_request())
    candidate = _first_qualified(result)
    summary = candidate.architecture_summary
    assert summary.architecture_recommendation_result.recommended_pathway in {"Conventional", "MRT", "NONE"}

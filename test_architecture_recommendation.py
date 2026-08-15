from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import architecture_recommendation as recommendation_module
from architecture_recommendation import (
    ArchitectureRecommendationRequest,
    ConventionalArchitectureBounds,
    MrtArchitectureBounds,
    run_native_architecture_recommendation,
)
from cyclotron_production_windows import CyclotronProductionCapability
from decision_pipeline import NativeBottleneckSummary, NativeDecisionPipelineScenario, NativePathwayScenario, run_native_decision_pipeline
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
        project_name="Native Architecture Recommendation",
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


def _request(*, target_patients_per_day: int = 200, minimum_reliability: float = 0.95, seeds: tuple[int, ...] = (101, 102)) -> ArchitectureRecommendationRequest:
    return ArchitectureRecommendationRequest(
        target_patients_per_day=target_patients_per_day,
        minimum_reliability=minimum_reliability,
        seeds=seeds,
        pipeline_template=replace(_pipeline_template(), target_patients_per_day=target_patients_per_day),
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
        throughput_thresholds_per_day=(target_patients_per_day,),
    )


def _candidate_signature(request: NativeDecisionPipelineScenario) -> tuple[str, tuple[int, int, int, int, float, int]]:
    conventional_base = _pipeline_template().conventional
    mrt_base = _pipeline_template().mrt
    conventional_changed = (
        request.conventional.scanners != conventional_base.scanners
        or request.conventional.injection_resources != conventional_base.injection_resources
        or request.conventional.uptake_resources != conventional_base.uptake_resources
        or request.conventional.distribution_concurrency != conventional_base.distribution_concurrency
        or request.conventional.transport_minutes != conventional_base.transport_minutes
    )
    mrt_changed = (
        request.mrt.scanners != mrt_base.scanners
        or request.mrt.injection_resources != mrt_base.injection_resources
        or request.mrt.uptake_resources != mrt_base.uptake_resources
        or request.mrt.distribution_concurrency != mrt_base.distribution_concurrency
        or request.mrt.installed_mrt_endpoints != mrt_base.installed_mrt_endpoints
        or request.mrt.transport_minutes != mrt_base.transport_minutes
    )
    if conventional_changed and not mrt_changed:
        arch = request.conventional
        return (
            "Conventional",
            (
                arch.scanners,
                arch.injection_resources,
                arch.uptake_resources,
                arch.distribution_concurrency,
                float(arch.transport_minutes),
                arch.installed_mrt_endpoints,
            ),
        )
    arch = request.mrt
    return (
        "MRT",
        (
            arch.scanners,
            arch.injection_resources,
            arch.uptake_resources,
            arch.distribution_concurrency,
            float(arch.transport_minutes),
            arch.installed_mrt_endpoints,
        ),
    )


def _fake_direct_decision_result(request: NativeDecisionPipelineScenario):
    pathway, signature = _candidate_signature(request)
    trace_suffix = "-".join(str(value) for value in signature)
    return SimpleNamespace(
        provenance=SimpleNamespace(
            scenario_trace_id=f"scenario-{pathway}-{trace_suffix}",
            demand_trace_id=f"demand-{pathway}-{trace_suffix}",
            conventional_trace_id=f"conventional-{pathway}-{trace_suffix}",
            mrt_trace_id=f"mrt-{pathway}-{trace_suffix}",
            comparison_trace_id=f"comparison-{pathway}-{trace_suffix}",
            batch_policy_description="PIPELINE BATCH POLICY: ceil(patient_count / 20) per radionuclide",
        ),
        conventional=SimpleNamespace(trace_id=f"conventional-result-{trace_suffix}"),
        mrt=SimpleNamespace(trace_id=f"mrt-result-{trace_suffix}"),
    )


def _make_bottleneck(resource: str, scanner: float, injection: float, uptake: float, distribution: float) -> NativeBottleneckSummary:
    return NativeBottleneckSummary(
        resource=resource,
        utilization_pct=max(scanner, injection, uptake, distribution),
        near_binding_resources=(resource,),
        utilization_by_resource={
            "scanner": scanner,
            "injection": injection,
            "uptake": uptake,
            "distribution": distribution,
        },
    )


def _fake_reliability_engine_factory(outcomes: dict[tuple[str, tuple[int, int, int, int, float, int]], dict[str, float | str]]):
    def fake_run_native_reliability_engine(request, seeds, *, throughput_thresholds_per_day=(), worst_run_count=3):
        pathway, signature = _candidate_signature(request)
        outcome = outcomes.get(
            (pathway, signature),
            {
                "throughput": 100.0,
                "reliability": 0.0,
                "capex": 10_000.0,
                "opex": 1_000.0,
                "conventional_npv": 0.0,
                "mrt_npv": 0.0,
                "bottleneck": "scanner",
            },
        )
        throughput = float(outcome["throughput"])
        reliability = float(outcome["reliability"])
        capex = float(outcome["capex"])
        opex = float(outcome["opex"])
        bottleneck = str(outcome["bottleneck"])
        run_refs = {
            seed: recommendation_module.NativeReliabilityRunReference(
                seed=seed,
                comparison_trace_id=f"comparison-{pathway}-{seed}-{signature}",
                demand_trace_id=f"demand-{pathway}-{seed}-{signature}",
                pathway_trace_ids={"Conventional": f"conv-{seed}", "MRT": f"mrt-{seed}"},
                completed_patients_per_day_by_pathway={"Conventional": int(throughput), "MRT": int(throughput)},
                completion_percentage_by_pathway={"Conventional": reliability * 100.0, "MRT": reliability * 100.0},
                bottleneck_by_pathway={
                    "Conventional": _make_bottleneck(bottleneck, 70.0, 50.0, 40.0, 30.0),
                    "MRT": _make_bottleneck(bottleneck, 70.0, 50.0, 40.0, 30.0),
                },
            )
            for seed in seeds
        }
        distribution = recommendation_module.NativeReliabilityDistributionSummary(
            observations=tuple([throughput] * len(seeds)),
            run_count=len(seeds),
            mean=throughput,
            minimum=throughput,
            maximum=throughput,
            p5=throughput,
            p50=throughput,
            p90=throughput,
            p95=throughput,
            p99=throughput,
        )
        pathway_summary = SimpleNamespace(
            pathway=pathway,
            throughput_distribution=distribution,
            completion_percentage_distribution=distribution,
            probability_meeting_target_demand=reliability,
            probability_below_thresholds={float(threshold): 1.0 - reliability for threshold in throughput_thresholds_per_day},
            bottleneck_counts={bottleneck: len(seeds)},
            bottleneck_frequencies={bottleneck: 1.0},
            worst_runs=tuple(run_refs.values())[:worst_run_count],
            throughput_supportable_at_90pct_reliability=throughput,
            throughput_supportable_at_95pct_reliability=throughput,
            throughput_supportable_at_99pct_reliability=throughput,
            capex_result=SimpleNamespace(total_capex=capex),
            opex_result=SimpleNamespace(total_annual_opex=opex),
            source_run_reference=next(iter(run_refs.values())),
        )
        mean_case = recommendation_module.NativeReliabilityLifecycleCase(
            label="mean",
            conventional_throughput_per_day=throughput,
            mrt_throughput_per_day=throughput,
            conventional_lifecycle_result=SimpleNamespace(final_npv=float(outcome["conventional_npv"])),
            mrt_lifecycle_result=SimpleNamespace(final_npv=float(outcome["mrt_npv"])),
            lifecycle_comparison_result=SimpleNamespace(
                incremental_final_npv_mrt_minus_conventional=float(outcome["mrt_npv"]) - float(outcome["conventional_npv"])
            ),
            economic_winner="MRT" if float(outcome["mrt_npv"]) > float(outcome["conventional_npv"]) else "Conventional",
        )
        p50_case = recommendation_module.NativeReliabilityLifecycleCase(
            label="p50",
            conventional_throughput_per_day=throughput,
            mrt_throughput_per_day=throughput,
            conventional_lifecycle_result=SimpleNamespace(final_npv=float(outcome["conventional_npv"]) - 10.0),
            mrt_lifecycle_result=SimpleNamespace(final_npv=float(outcome["mrt_npv"]) - 10.0),
            lifecycle_comparison_result=SimpleNamespace(
                incremental_final_npv_mrt_minus_conventional=float(outcome["mrt_npv"]) - float(outcome["conventional_npv"])
            ),
            economic_winner="MRT" if float(outcome["mrt_npv"]) > float(outcome["conventional_npv"]) else "Conventional",
        )
        p5_case = recommendation_module.NativeReliabilityLifecycleCase(
            label="p5",
            conventional_throughput_per_day=throughput,
            mrt_throughput_per_day=throughput,
            conventional_lifecycle_result=SimpleNamespace(final_npv=float(outcome["conventional_npv"]) - 20.0),
            mrt_lifecycle_result=SimpleNamespace(final_npv=float(outcome["mrt_npv"]) - 20.0),
            lifecycle_comparison_result=SimpleNamespace(
                incremental_final_npv_mrt_minus_conventional=float(outcome["mrt_npv"]) - float(outcome["conventional_npv"])
            ),
            economic_winner="MRT" if float(outcome["mrt_npv"]) > float(outcome["conventional_npv"]) else "Conventional",
        )
        return SimpleNamespace(
            request=request,
            seeds=tuple(seeds),
            run_count=len(seeds),
            run_results=tuple(SimpleNamespace(seed=seed, reference=run_refs[seed], native_result=_fake_direct_decision_result(request)) for seed in seeds),
            conventional=pathway_summary,
            mrt=pathway_summary,
            lifecycle_cases=(mean_case, p50_case, p5_case),
            economic_winner_by_case={"mean": mean_case.economic_winner, "p50": p50_case.economic_winner, "p5": p5_case.economic_winner},
            stable_economic_preference=True,
            provenance=SimpleNamespace(request=request, seeds=tuple(seeds), run_references_by_seed=run_refs, aggregate_trace_id=f"agg-{pathway}-{signature}"),
            trace_id=f"reliability-{pathway}-{signature}",
            warnings=(),
            limitations=(),
        )

    return fake_run_native_reliability_engine


def test_recommendation_is_deterministic_for_same_request_and_seeds(monkeypatch):
    outcomes = {
        ("Conventional", (3, 2, 7, 1, 6.5, 0)): {"throughput": 180.0, "reliability": 1.0, "capex": 100.0, "opex": 10.0, "conventional_npv": 900.0, "mrt_npv": 800.0, "bottleneck": "scanner"},
        ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 200.0, "reliability": 1.0, "capex": 120.0, "opex": 12.0, "conventional_npv": 800.0, "mrt_npv": 1100.0, "bottleneck": "uptake"},
    }
    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", _fake_reliability_engine_factory(outcomes))

    result_a = run_native_architecture_recommendation(_request())
    result_b = run_native_architecture_recommendation(_request())

    assert result_a == result_b
    assert result_a.candidate_count_evaluated == 8


def test_same_seed_set_is_used_for_all_candidates(monkeypatch):
    seen_seeds: list[tuple[int, ...]] = []

    def fake_reliability(request, seeds, *, throughput_thresholds_per_day=(), worst_run_count=3):
        seen_seeds.append(tuple(seeds))
        return _fake_reliability_engine_factory({
            ("Conventional", (3, 2, 7, 1, 6.5, 0)): {"throughput": 180.0, "reliability": 1.0, "capex": 100.0, "opex": 10.0, "conventional_npv": 900.0, "mrt_npv": 800.0, "bottleneck": "scanner"},
            ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 200.0, "reliability": 1.0, "capex": 120.0, "opex": 12.0, "conventional_npv": 800.0, "mrt_npv": 1100.0, "bottleneck": "uptake"},
        })(request, seeds, throughput_thresholds_per_day=throughput_thresholds_per_day, worst_run_count=worst_run_count)

    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", fake_reliability)

    run_native_architecture_recommendation(_request(seeds=(7, 8, 9)))

    assert seen_seeds and all(seed_set == (7, 8, 9) for seed_set in seen_seeds)
    assert len(seen_seeds) == 8


def test_conventional_and_mrt_are_evaluated_fairly(monkeypatch):
    observed_requests: list[tuple[str, tuple[int, ...], int]] = []

    def fake_reliability(request, seeds, *, throughput_thresholds_per_day=(), worst_run_count=3):
        pathway, _ = _candidate_signature(request)
        observed_requests.append((pathway, tuple(seeds), request.target_patients_per_day))
        return _fake_reliability_engine_factory({
            ("Conventional", (3, 2, 7, 1, 6.5, 0)): {"throughput": 180.0, "reliability": 1.0, "capex": 100.0, "opex": 10.0, "conventional_npv": 900.0, "mrt_npv": 800.0, "bottleneck": "scanner"},
            ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 200.0, "reliability": 1.0, "capex": 120.0, "opex": 12.0, "conventional_npv": 800.0, "mrt_npv": 1100.0, "bottleneck": "uptake"},
        })(request, seeds, throughput_thresholds_per_day=throughput_thresholds_per_day, worst_run_count=worst_run_count)

    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", fake_reliability)

    result = run_native_architecture_recommendation(_request())

    assert {entry[0] for entry in observed_requests} == {"Conventional", "MRT"}
    assert all(entry[1] == (101, 102) for entry in observed_requests)
    assert all(entry[2] == 200 for entry in observed_requests)
    assert result.candidate_count_by_pathway == {"Conventional": 4, "MRT": 4}


def test_reliability_rejected_candidate_cannot_win(monkeypatch):
    outcomes = {
        ("Conventional", (3, 2, 7, 1, 6.5, 0)): {"throughput": 180.0, "reliability": 0.90, "capex": 100.0, "opex": 10.0, "conventional_npv": 900.0, "mrt_npv": 800.0, "bottleneck": "scanner"},
        ("Conventional", (4, 2, 7, 1, 6.5, 0)): {"throughput": 200.0, "reliability": 1.0, "capex": 120.0, "opex": 12.0, "conventional_npv": 1100.0, "mrt_npv": 800.0, "bottleneck": "scanner"},
        ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 200.0, "reliability": 1.0, "capex": 130.0, "opex": 13.0, "conventional_npv": 800.0, "mrt_npv": 1000.0, "bottleneck": "uptake"},
    }
    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", _fake_reliability_engine_factory(outcomes))

    result = run_native_architecture_recommendation(_request())

    rejected = [candidate for candidate in result.conventional_candidates if candidate.status == "REJECTED_RELIABILITY"]
    assert rejected
    assert result.recommended_pathway in {"Conventional", "MRT"}
    assert all(candidate.candidate_id != result.recommended_architecture.candidate_id for candidate in rejected if result.recommended_architecture)


def test_qualifying_candidate_can_win(monkeypatch):
    outcomes = {
        ("Conventional", (4, 2, 7, 1, 6.5, 0)): {"throughput": 200.0, "reliability": 1.0, "capex": 100.0, "opex": 10.0, "conventional_npv": 1400.0, "mrt_npv": 800.0, "bottleneck": "scanner"},
        ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 200.0, "reliability": 1.0, "capex": 120.0, "opex": 12.0, "conventional_npv": 800.0, "mrt_npv": 1000.0, "bottleneck": "uptake"},
    }
    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", _fake_reliability_engine_factory(outcomes))

    result = run_native_architecture_recommendation(_request())

    assert result.recommended_pathway == "Conventional"
    assert result.best_qualifying_conventional is not None
    assert result.recommended_architecture.candidate_id == result.best_qualifying_conventional.candidate_id


def test_lowest_resource_candidate_is_not_automatically_selected(monkeypatch):
    outcomes = {
        ("Conventional", (3, 2, 7, 1, 6.5, 0)): {"throughput": 200.0, "reliability": 1.0, "capex": 90.0, "opex": 9.0, "conventional_npv": 500.0, "mrt_npv": 400.0, "bottleneck": "scanner"},
        ("Conventional", (4, 2, 7, 1, 6.5, 0)): {"throughput": 200.0, "reliability": 1.0, "capex": 150.0, "opex": 15.0, "conventional_npv": 900.0, "mrt_npv": 400.0, "bottleneck": "scanner"},
        ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 200.0, "reliability": 1.0, "capex": 130.0, "opex": 13.0, "conventional_npv": 600.0, "mrt_npv": 700.0, "bottleneck": "uptake"},
    }
    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", _fake_reliability_engine_factory(outcomes))

    result = run_native_architecture_recommendation(_request())

    assert result.best_qualifying_conventional is not None
    assert result.best_qualifying_conventional.architecture.scanners == 4
    assert result.best_qualifying_conventional.lifecycle_npv > 500.0


def test_higher_resource_candidate_is_not_automatically_selected(monkeypatch):
    outcomes = {
        ("Conventional", (3, 2, 7, 1, 6.5, 0)): {"throughput": 200.0, "reliability": 1.0, "capex": 90.0, "opex": 9.0, "conventional_npv": 1000.0, "mrt_npv": 400.0, "bottleneck": "scanner"},
        ("Conventional", (4, 2, 7, 1, 6.5, 0)): {"throughput": 205.0, "reliability": 1.0, "capex": 200.0, "opex": 20.0, "conventional_npv": 800.0, "mrt_npv": 400.0, "bottleneck": "scanner"},
        ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 200.0, "reliability": 1.0, "capex": 130.0, "opex": 13.0, "conventional_npv": 600.0, "mrt_npv": 700.0, "bottleneck": "uptake"},
    }
    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", _fake_reliability_engine_factory(outcomes))

    result = run_native_architecture_recommendation(_request())

    assert result.best_qualifying_conventional is not None
    assert result.best_qualifying_conventional.architecture.scanners == 3
    assert result.best_qualifying_conventional.lifecycle_npv == 1000.0


def test_pathway_with_no_qualifying_candidates_is_handled_correctly(monkeypatch):
    outcomes = {
        ("Conventional", (3, 2, 7, 1, 6.5, 0)): {"throughput": 180.0, "reliability": 1.0, "capex": 100.0, "opex": 10.0, "conventional_npv": 900.0, "mrt_npv": 800.0, "bottleneck": "scanner"},
        ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 180.0, "reliability": 0.90, "capex": 120.0, "opex": 12.0, "conventional_npv": 800.0, "mrt_npv": 1000.0, "bottleneck": "uptake"},
    }
    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", _fake_reliability_engine_factory(outcomes))

    result = run_native_architecture_recommendation(_request())

    assert result.best_qualifying_mrt is None
    assert result.best_qualifying_conventional is not None
    assert result.recommended_pathway == "Conventional"


def test_neither_pathway_qualifying_returns_none(monkeypatch):
    outcomes = {
        ("Conventional", (3, 2, 7, 1, 6.5, 0)): {"throughput": 180.0, "reliability": 0.80, "capex": 100.0, "opex": 10.0, "conventional_npv": 900.0, "mrt_npv": 800.0, "bottleneck": "scanner"},
        ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 180.0, "reliability": 0.85, "capex": 120.0, "opex": 12.0, "conventional_npv": 800.0, "mrt_npv": 1000.0, "bottleneck": "uptake"},
    }
    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", _fake_reliability_engine_factory(outcomes))

    result = run_native_architecture_recommendation(_request())

    assert result.best_qualifying_conventional is None
    assert result.best_qualifying_mrt is None
    assert result.recommended_pathway == "NONE"
    assert result.recommended_architecture is None


def test_lifecycle_results_come_from_native_engines(monkeypatch):
    outcomes = {
        ("Conventional", (4, 2, 7, 1, 6.5, 0)): {"throughput": 200.0, "reliability": 1.0, "capex": 100.0, "opex": 10.0, "conventional_npv": 1400.0, "mrt_npv": 800.0, "bottleneck": "scanner"},
        ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 200.0, "reliability": 1.0, "capex": 120.0, "opex": 12.0, "conventional_npv": 800.0, "mrt_npv": 1000.0, "bottleneck": "uptake"},
    }
    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", _fake_reliability_engine_factory(outcomes))

    result = run_native_architecture_recommendation(_request())

    assert result.best_qualifying_conventional.lifecycle_case.label == "mean"
    assert result.best_qualifying_conventional.lifecycle_result.final_npv == 1400.0
    assert result.best_qualifying_mrt.lifecycle_result.final_npv == 1000.0


def test_recommendation_provenance_points_to_an_actual_evaluated_candidate(monkeypatch):
    outcomes = {
        ("Conventional", (4, 2, 7, 1, 6.5, 0)): {"throughput": 200.0, "reliability": 1.0, "capex": 100.0, "opex": 10.0, "conventional_npv": 1400.0, "mrt_npv": 800.0, "bottleneck": "scanner"},
        ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 200.0, "reliability": 1.0, "capex": 120.0, "opex": 12.0, "conventional_npv": 800.0, "mrt_npv": 1000.0, "bottleneck": "uptake"},
    }
    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", _fake_reliability_engine_factory(outcomes))

    result = run_native_architecture_recommendation(_request())

    winning_id = result.provenance.winning_candidate_id
    assert winning_id in result.provenance.candidate_provenance_by_id
    assert result.provenance.candidate_provenance_by_id[winning_id].candidate_id == winning_id


@pytest.mark.parametrize(
    "minimum_reliability,target_patients_per_day",
    [
        (0.0, 200),
        (1.5, 200),
        (0.95, 0),
    ],
)
def test_invalid_reliability_requirements_are_rejected(minimum_reliability, target_patients_per_day):
    with pytest.raises(ValueError):
        _request(target_patients_per_day=target_patients_per_day, minimum_reliability=minimum_reliability)


def test_invalid_candidate_bounds_are_rejected():
    with pytest.raises(ValueError, match="must not be empty"):
        ConventionalArchitectureBounds(scanners=(), injection_resources=(2,), uptake_resources=(7,), distribution_concurrency=(1,), transport_minutes=(7.0,))
    with pytest.raises(ValueError, match="must not be empty"):
        MrtArchitectureBounds(scanners=(5,), injection_resources=(3,), uptake_resources=(10,), distribution_concurrency=(2,), installed_mrt_endpoints=(), transport_minutes=(5.0,))
    with pytest.raises(ValueError, match="values must be at least 0"):
        MrtArchitectureBounds(scanners=(5,), injection_resources=(3,), uptake_resources=(10,), distribution_concurrency=(2,), installed_mrt_endpoints=(-1,), transport_minutes=(5.0,))


def test_candidate_count_guard_works(monkeypatch):
    monkeypatch.setattr(recommendation_module, "run_native_decision_pipeline", _fake_direct_decision_result)
    monkeypatch.setattr(recommendation_module, "run_native_reliability_engine", _fake_reliability_engine_factory({
        ("Conventional", (3, 2, 7, 1, 6.5, 0)): {"throughput": 200.0, "reliability": 1.0, "capex": 100.0, "opex": 10.0, "conventional_npv": 1400.0, "mrt_npv": 800.0, "bottleneck": "scanner"},
        ("MRT", (5, 3, 10, 2, 4.5, 2)): {"throughput": 200.0, "reliability": 1.0, "capex": 120.0, "opex": 12.0, "conventional_npv": 800.0, "mrt_npv": 1000.0, "bottleneck": "uptake"},
    }))

    request = _request()
    request = replace(request, max_candidate_count=2)

    with pytest.raises(ValueError, match="exceeds max_candidate_count"):
        run_native_architecture_recommendation(request)


def test_real_native_smoke_test_uses_the_established_200_patient_scenario():
    result_before = run_native_decision_pipeline(_pipeline_template())

    request = ArchitectureRecommendationRequest(
        target_patients_per_day=200,
        minimum_reliability=0.95,
        seeds=(20260813, 20260814),
        pipeline_template=_pipeline_template(),
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

    result = run_native_architecture_recommendation(request)
    result_after = run_native_decision_pipeline(_pipeline_template())

    assert result_before == result_after
    assert result.candidate_count_evaluated == 8
    assert result.candidate_count_by_pathway == {"Conventional": 4, "MRT": 4}
    assert result.best_qualifying_conventional is not None or result.best_qualifying_mrt is not None
    assert result.recommended_pathway in {"Conventional", "MRT", "NONE"}
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import reliability_engine as reliability_module
from cyclotron_production_windows import CyclotronProductionCapability
from decision_pipeline import NativeBottleneckSummary, NativeDecisionPipelineScenario, NativePathwayScenario, run_native_decision_pipeline
from models import PlannerAssumptions, SharedNetworkAssumptions
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
        project_name="Native Reliability Pipeline",
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


def _fake_native_result(
    *,
    seed: int,
    conventional_completed: int,
    mrt_completed: int,
    conventional_resource: str,
    mrt_resource: str,
    conventional_utilization: float = 55.0,
    mrt_utilization: float = 75.0,
    conventional_total: int = 100,
    mrt_total: int = 100,
    conventional_capex: float = 1_000_000.0,
    mrt_capex: float = 1_200_000.0,
    conventional_opex: float = 100_000.0,
    mrt_opex: float = 125_000.0,
):
    return SimpleNamespace(
        provenance=SimpleNamespace(
            comparison_trace_id=f"comparison-{seed}",
            demand_trace_id=f"demand-{seed}",
            conventional_trace_id=f"conventional-{seed}",
            mrt_trace_id=f"mrt-{seed}",
        ),
        conventional=SimpleNamespace(
            trace_id=f"conventional-path-{seed}",
            operational_result=SimpleNamespace(
                patients_completed=conventional_completed,
                completion_percentage=100.0 * conventional_completed / conventional_total,
            ),
            capex_result=SimpleNamespace(total_capex=conventional_capex),
            opex_result=SimpleNamespace(total_annual_opex=conventional_opex),
        ),
        mrt=SimpleNamespace(
            trace_id=f"mrt-path-{seed}",
            operational_result=SimpleNamespace(
                patients_completed=mrt_completed,
                completion_percentage=100.0 * mrt_completed / mrt_total,
            ),
            capex_result=SimpleNamespace(total_capex=mrt_capex),
            opex_result=SimpleNamespace(total_annual_opex=mrt_opex),
        ),
        bottleneck_information={
            "Conventional": NativeBottleneckSummary(
                resource=conventional_resource,
                utilization_pct=conventional_utilization,
                near_binding_resources=(conventional_resource,),
                utilization_by_resource={
                    "scanner": conventional_utilization,
                    "injection": 10.0,
                    "uptake": 8.0,
                    "distribution": 5.0,
                },
            ),
            "MRT": NativeBottleneckSummary(
                resource=mrt_resource,
                utilization_pct=mrt_utilization,
                near_binding_resources=(mrt_resource,),
                utilization_by_resource={
                    "scanner": 15.0,
                    "injection": mrt_utilization,
                    "uptake": 9.0,
                    "distribution": 7.0,
                },
            ),
        },
        warnings=(f"seed-{seed}-warning",),
    )


def _fake_pipeline_factory(conventional_values: list[int], mrt_values: list[int], *, conventional_resources: list[str] | None = None, mrt_resources: list[str] | None = None):
    conventional_resources = conventional_resources or ["scanner"] * len(conventional_values)
    mrt_resources = mrt_resources or ["injection"] * len(mrt_values)

    def fake_run_native_decision_pipeline(request):
        position = max(0, int(request.seed) - 1) % len(conventional_values)
        return _fake_native_result(
            seed=request.seed,
            conventional_completed=conventional_values[position],
            mrt_completed=mrt_values[position],
            conventional_resource=conventional_resources[position],
            mrt_resource=mrt_resources[position],
        )

    return fake_run_native_decision_pipeline


def test_reliability_engine_is_deterministic_for_identical_seed_sets(monkeypatch):
    fake = _fake_pipeline_factory([10, 20, 30], [12, 22, 32])
    monkeypatch.setattr(reliability_module, "run_native_decision_pipeline", fake)

    seeds = (1, 2, 3)
    result_a = run_native_reliability_engine(_request(), seeds, throughput_thresholds_per_day=(15.0, 25.0))
    result_b = run_native_reliability_engine(_request(), seeds, throughput_thresholds_per_day=(15.0, 25.0))

    assert result_a == result_b
    assert result_a.seeds == seeds
    assert result_a.run_count == len(seeds)


def test_different_seed_sets_are_honored(monkeypatch):
    def fake_run_native_decision_pipeline(request):
        return _fake_native_result(
            seed=request.seed,
            conventional_completed=request.seed,
            mrt_completed=request.seed + 10,
            conventional_resource="scanner",
            mrt_resource="injection",
        )

    monkeypatch.setattr(reliability_module, "run_native_decision_pipeline", fake_run_native_decision_pipeline)

    result_a = run_native_reliability_engine(_request(), (1, 2, 3))
    result_b = run_native_reliability_engine(_request(), (4, 5, 6))

    assert tuple(run.seed for run in result_a.run_results) == (1, 2, 3)
    assert tuple(run.seed for run in result_b.run_results) == (4, 5, 6)
    assert result_a != result_b


def test_run_native_decision_pipeline_called_once_per_seed(monkeypatch):
    call_log: list[int] = []

    def fake_run_native_decision_pipeline(request):
        call_log.append(request.seed)
        return _fake_native_result(
            seed=request.seed,
            conventional_completed=20 + request.seed,
            mrt_completed=30 + request.seed,
            conventional_resource="scanner",
            mrt_resource="injection",
        )

    monkeypatch.setattr(reliability_module, "run_native_decision_pipeline", fake_run_native_decision_pipeline)

    seeds = (11, 12, 13, 14)
    run_native_reliability_engine(_request(), seeds)

    assert call_log == list(seeds)


def test_no_stochastic_day_is_silently_dropped(monkeypatch):
    monkeypatch.setattr(
        reliability_module,
        "run_native_decision_pipeline",
        _fake_pipeline_factory([10, 20, 30, 40], [11, 21, 31, 41]),
    )

    seeds = (100, 101, 102, 103)
    result = run_native_reliability_engine(_request(), seeds)

    assert result.run_count == len(seeds)
    assert len(result.run_results) == len(seeds)
    assert tuple(run.seed for run in result.run_results) == seeds
    assert result.provenance.seeds == seeds


def test_aggregate_percentiles_come_from_native_completed_throughput(monkeypatch):
    throughput_values = [10, 20, 30, 40]

    def fake_run_native_decision_pipeline(request):
        value = throughput_values[request.seed]
        return _fake_native_result(
            seed=request.seed,
            conventional_completed=value,
            mrt_completed=value,
            conventional_resource="scanner",
            mrt_resource="scanner",
            conventional_total=100,
            mrt_total=100,
        )

    monkeypatch.setattr(reliability_module, "run_native_decision_pipeline", fake_run_native_decision_pipeline)

    result = run_native_reliability_engine(_request(), (0, 1, 2, 3))

    summary = result.conventional.throughput_distribution
    assert summary.observations == (10.0, 20.0, 30.0, 40.0)
    assert summary.mean == pytest.approx(25.0)
    assert summary.minimum == 10.0
    assert summary.maximum == 40.0
    assert summary.p5 == pytest.approx(11.5)
    assert summary.p50 == pytest.approx(25.0)
    assert summary.p90 == pytest.approx(37.0)
    assert summary.p95 == pytest.approx(38.5)
    assert summary.p99 == pytest.approx(39.7)


def test_target_demand_reliability_is_calculated_correctly(monkeypatch):
    throughput_values = [10, 20, 30, 40]

    def fake_run_native_decision_pipeline(request):
        value = throughput_values[request.seed]
        return _fake_native_result(
            seed=request.seed,
            conventional_completed=value,
            mrt_completed=value,
            conventional_resource="scanner",
            mrt_resource="scanner",
        )

    monkeypatch.setattr(reliability_module, "run_native_decision_pipeline", fake_run_native_decision_pipeline)

    request = replace(_request(), target_patients_per_day=25)
    result = run_native_reliability_engine(request, (0, 1, 2, 3))

    assert result.conventional.probability_meeting_target_demand == pytest.approx(0.5)
    assert result.mrt.probability_meeting_target_demand == pytest.approx(0.5)
    assert result.conventional.probability_below_thresholds == {}


def test_ninetieth_and_conservative_reliability_throughput_are_calculated_correctly(monkeypatch):
    throughput_values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    def fake_run_native_decision_pipeline(request):
        value = throughput_values[request.seed]
        return _fake_native_result(
            seed=request.seed,
            conventional_completed=value,
            mrt_completed=value,
            conventional_resource="scanner",
            mrt_resource="scanner",
        )

    monkeypatch.setattr(reliability_module, "run_native_decision_pipeline", fake_run_native_decision_pipeline)

    result = run_native_reliability_engine(_request(), range(10))

    assert result.conventional.throughput_supportable_at_90pct_reliability == pytest.approx(19.0)
    assert result.conventional.throughput_supportable_at_95pct_reliability == pytest.approx(14.5)
    assert result.conventional.throughput_supportable_at_99pct_reliability == pytest.approx(10.9)
    assert result.mrt.throughput_supportable_at_90pct_reliability == pytest.approx(19.0)
    assert result.mrt.throughput_supportable_at_95pct_reliability == pytest.approx(14.5)
    assert result.mrt.throughput_supportable_at_99pct_reliability == pytest.approx(10.9)


def test_bottleneck_frequencies_reconcile_to_run_count(monkeypatch):
    conventional_resources = ["scanner", "scanner", "uptake", "distribution"]
    mrt_resources = ["injection", "injection", "scanner", "scanner"]

    monkeypatch.setattr(
        reliability_module,
        "run_native_decision_pipeline",
        _fake_pipeline_factory([10, 20, 30, 40], [11, 21, 31, 41], conventional_resources=conventional_resources, mrt_resources=mrt_resources),
    )

    result = run_native_reliability_engine(_request(), (0, 1, 2, 3))

    assert sum(result.conventional.bottleneck_counts.values()) == result.run_count
    assert sum(result.mrt.bottleneck_counts.values()) == result.run_count
    assert sum(result.conventional.bottleneck_frequencies.values()) == pytest.approx(1.0)
    assert sum(result.mrt.bottleneck_frequencies.values()) == pytest.approx(1.0)


def test_worst_run_provenance_resolves_to_an_actual_run(monkeypatch):
    monkeypatch.setattr(
        reliability_module,
        "run_native_decision_pipeline",
        _fake_pipeline_factory([40, 30, 20, 10], [41, 31, 21, 11]),
    )

    result = run_native_reliability_engine(_request(), (1, 2, 3, 4), worst_run_count=2)

    worst = result.conventional.worst_runs[0]
    actual = result.provenance.run_references_by_seed[worst.seed]

    assert worst.seed == 4
    assert actual.comparison_trace_id == worst.comparison_trace_id
    assert actual.demand_trace_id == worst.demand_trace_id


def test_mean_p50_and_p5_lifecycle_throughput_comes_from_reliability_statistics(monkeypatch):
    monkeypatch.setattr(
        reliability_module,
        "run_native_decision_pipeline",
        _fake_pipeline_factory([10, 20, 30, 40], [12, 22, 32, 42]),
    )

    result = run_native_reliability_engine(_request(), (0, 1, 2, 3))

    mean_case, p50_case, p5_case = result.lifecycle_cases

    assert mean_case.conventional_throughput_per_day == pytest.approx(result.conventional.throughput_distribution.mean)
    assert p50_case.conventional_throughput_per_day == pytest.approx(result.conventional.throughput_distribution.p50)
    assert p5_case.conventional_throughput_per_day == pytest.approx(result.conventional.throughput_distribution.p5)
    assert mean_case.mrt_throughput_per_day == pytest.approx(result.mrt.throughput_distribution.mean)
    assert p50_case.mrt_throughput_per_day == pytest.approx(result.mrt.throughput_distribution.p50)
    assert p5_case.mrt_throughput_per_day == pytest.approx(result.mrt.throughput_distribution.p5)
    assert set(result.economic_winner_by_case) == {"mean", "p50", "p5"}


def test_invalid_or_empty_seed_inputs_fail_clearly(monkeypatch):
    monkeypatch.setattr(
        reliability_module,
        "run_native_decision_pipeline",
        _fake_pipeline_factory([10], [10]),
    )

    with pytest.raises(ValueError, match="seeds must not be empty"):
        run_native_reliability_engine(_request(), [])

    with pytest.raises(TypeError, match="seeds must contain integers"):
        run_native_reliability_engine(_request(), [1, "2"])  # type: ignore[list-item]


def test_existing_native_decision_pipeline_behavior_remains_unchanged():
    request = _request()
    baseline = run_native_decision_pipeline(request)

    result = run_native_reliability_engine(request, (20260813, 20260814))
    after = run_native_decision_pipeline(request)

    assert baseline == after
    assert result.run_count == 2
    assert result.seeds == (20260813, 20260814)
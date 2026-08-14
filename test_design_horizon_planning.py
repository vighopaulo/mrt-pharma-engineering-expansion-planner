from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import design_horizon_planning as horizon_module
from cyclotron_production_windows import CyclotronProductionCapability
from decision_pipeline import NativeDecisionPipelineScenario, NativePathwayScenario
from design_horizon_planning import DesignHorizonPlanningRequest, run_native_design_horizon_planning
from models import PlannerAssumptions, SharedNetworkAssumptions
from stochastic_design_day import ActivityDemandModel


def _activity_models() -> dict[str, ActivityDemandModel]:
    return {
        "F-18": ActivityDemandModel(
            "bounded_normal",
            mean_activity_mbq=200.0,
            stddev_activity_mbq=20.0,
            lower_bound_mbq=160.0,
            upper_bound_mbq=240.0,
        )
    }


def _planner_assumptions() -> PlannerAssumptions:
    return PlannerAssumptions(
        analysis_years=5,
        discount_rate_pct=8.0,
        operating_days_per_year=300,
        revenue_per_scan=1200.0,
        scanner_cycle_min=20.0,
        injection_cycle_min=10.0,
        uptake_cycle_min=45.0,
        operating_hours_per_day=18.0,
    )


def _pipeline_template() -> NativeDecisionPipelineScenario:
    conventional = NativePathwayScenario(
        pathway="Conventional",
        scanners=2,
        injection_resources=2,
        uptake_resources=2,
        distribution_concurrency=1,
        transport_minutes=8.0,
        installed_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        annual_production_variable_cost=200_000.0,
    )
    mrt = NativePathwayScenario(
        pathway="MRT",
        scanners=2,
        injection_resources=2,
        uptake_resources=2,
        distribution_concurrency=1,
        transport_minutes=4.0,
        installed_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        installed_mrt_base_infrastructure_units=1,
        operated_mrt_base_units=1,
        installed_mrt_endpoints=1,
        operated_mrt_endpoints=1,
        annual_production_variable_cost=220_000.0,
    )
    return NativeDecisionPipelineScenario(
        project_name="Horizon Test",
        target_patients_per_day=100,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide=_activity_models(),
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="H1",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
        ),
        conventional=conventional,
        mrt=mrt,
        planner_assumptions=_planner_assumptions(),
        shared_network_assumptions=SharedNetworkAssumptions(),
        seed=7,
        batch_target_patients_per_batch=20,
    )


def _capacity_by_pathway(scenario: NativeDecisionPipelineScenario) -> tuple[float, float]:
    conventional = scenario.conventional
    mrt = scenario.mrt
    conventional_capacity = (
        conventional.scanners * 22.0
        + conventional.injection_resources * 14.0
        + conventional.uptake_resources * 10.0
        + conventional.distribution_concurrency * 8.0
    )
    mrt_capacity = (
        mrt.scanners * 24.0
        + mrt.injection_resources * 14.0
        + mrt.uptake_resources * 10.0
        + mrt.distribution_concurrency * 10.0
        + mrt.installed_mrt_endpoints * 6.0
    )
    return conventional_capacity, mrt_capacity


def _bottleneck_for(pathway: str, scenario: NativeDecisionPipelineScenario, demand: float) -> str:
    architecture = scenario.conventional if pathway == "Conventional" else scenario.mrt
    capacity_terms = {
        "scanner": architecture.scanners * (22.0 if pathway == "Conventional" else 24.0),
        "injection": architecture.injection_resources * 14.0,
        "uptake": architecture.uptake_resources * 10.0,
        "distribution": architecture.distribution_concurrency * (8.0 if pathway == "Conventional" else 10.0),
    }
    if pathway == "MRT":
        capacity_terms["endpoint"] = architecture.installed_mrt_endpoints * 6.0
    return min(capacity_terms, key=capacity_terms.get)


def _fake_reliability_engine(request, seeds, *, throughput_thresholds_per_day=(), worst_run_count=3):
    del seeds, throughput_thresholds_per_day, worst_run_count
    conv_capacity, mrt_capacity = _capacity_by_pathway(request)
    demand = float(request.target_patients_per_day)

    conv_bottleneck = _bottleneck_for("Conventional", request, demand)
    mrt_bottleneck = _bottleneck_for("MRT", request, demand)

    conv_probability = 1.0 if conv_capacity >= demand else max(0.0, conv_capacity / demand)
    mrt_probability = 1.0 if mrt_capacity >= demand else max(0.0, mrt_capacity / demand)

    return SimpleNamespace(
        conventional=SimpleNamespace(
            throughput_distribution=SimpleNamespace(mean=min(conv_capacity, demand)),
            probability_meeting_target_demand=conv_probability,
            source_run_reference=SimpleNamespace(
                bottleneck_by_pathway={
                    "Conventional": SimpleNamespace(resource=conv_bottleneck),
                    "MRT": SimpleNamespace(resource=mrt_bottleneck),
                }
            ),
            opex_result=SimpleNamespace(total_annual_opex=600_000.0 + 30_000.0 * request.conventional.scanners),
            capex_result=SimpleNamespace(total_capex=4_000_000.0 + 1_000_000.0 * request.conventional.scanners),
        ),
        mrt=SimpleNamespace(
            throughput_distribution=SimpleNamespace(mean=min(mrt_capacity, demand)),
            probability_meeting_target_demand=mrt_probability,
            source_run_reference=SimpleNamespace(
                bottleneck_by_pathway={
                    "Conventional": SimpleNamespace(resource=conv_bottleneck),
                    "MRT": SimpleNamespace(resource=mrt_bottleneck),
                }
            ),
            opex_result=SimpleNamespace(total_annual_opex=700_000.0 + 35_000.0 * request.mrt.scanners),
            capex_result=SimpleNamespace(total_capex=5_000_000.0 + 1_200_000.0 * request.mrt.scanners + 80_000.0 * request.mrt.installed_mrt_endpoints),
        ),
    )


def _fake_decision_pipeline(request):
    conv_cap, mrt_cap = _capacity_by_pathway(request)
    return SimpleNamespace(
        conventional=SimpleNamespace(
            capex_result=SimpleNamespace(total_capex=4_000_000.0 + 1_000_000.0 * request.conventional.scanners),
            opex_result=SimpleNamespace(total_annual_opex=600_000.0 + 30_000.0 * request.conventional.scanners),
            lifecycle_result=SimpleNamespace(final_npv=conv_cap * 1000.0),
        ),
        mrt=SimpleNamespace(
            capex_result=SimpleNamespace(total_capex=5_000_000.0 + 1_200_000.0 * request.mrt.scanners + 80_000.0 * request.mrt.installed_mrt_endpoints),
            opex_result=SimpleNamespace(total_annual_opex=700_000.0 + 35_000.0 * request.mrt.scanners),
            lifecycle_result=SimpleNamespace(final_npv=mrt_cap * 1000.0),
        ),
    )


def test_milestone_trajectory_and_determinism(monkeypatch):
    monkeypatch.setattr(horizon_module, "run_native_reliability_engine", _fake_reliability_engine)
    monkeypatch.setattr(horizon_module, "run_native_decision_pipeline", _fake_decision_pipeline)

    request = DesignHorizonPlanningRequest(
        pipeline_template=_pipeline_template(),
        seeds=(1, 2, 3),
        demand_mode="milestone",
        milestone_daily_demand_by_year={1: 100.0, 3: 160.0, 5: 220.0},
        max_expansion_actions_per_year=1,
        max_total_build_ahead_actions=3,
    )

    result_a = run_native_design_horizon_planning(request)
    result_b = run_native_design_horizon_planning(request)

    assert result_a == result_b
    assert result_a.demand_trajectory.daily_demand_by_year == [100.0, 130.0, 160.0, 190.0, 220.0]


def test_year_level_results_include_headroom_exhaustion_and_bottleneck_migration(monkeypatch):
    monkeypatch.setattr(horizon_module, "run_native_reliability_engine", _fake_reliability_engine)
    monkeypatch.setattr(horizon_module, "run_native_decision_pipeline", _fake_decision_pipeline)

    request = DesignHorizonPlanningRequest(
        pipeline_template=_pipeline_template(),
        seeds=(1, 2),
        demand_mode="explicit",
        explicit_daily_demand_by_year=[110.0, 170.0, 240.0, 300.0, 360.0],
        max_expansion_actions_per_year=1,
        max_total_build_ahead_actions=2,
        allowed_expansion_resources={
            "Conventional": ("scanner", "injection"),
            "MRT": ("scanner", "endpoint"),
        },
    )

    result = run_native_design_horizon_planning(request)

    assert len(result.year_results) == 5
    assert result.conventional_summary.exhaustion_year is not None
    assert result.mrt_summary.exhaustion_year is not None
    assert result.conventional_summary.bottleneck_migration_timeline
    assert result.mrt_summary.bottleneck_migration_timeline


def test_phased_capex_discounting_and_strategy_comparison(monkeypatch):
    monkeypatch.setattr(horizon_module, "run_native_reliability_engine", _fake_reliability_engine)
    monkeypatch.setattr(horizon_module, "run_native_decision_pipeline", _fake_decision_pipeline)

    template = _pipeline_template()
    template = replace(
        template,
        planner_assumptions=replace(template.planner_assumptions, discount_rate_pct=10.0, analysis_years=5),
    )

    request = DesignHorizonPlanningRequest(
        pipeline_template=template,
        seeds=(9, 10),
        demand_mode="compound",
        constant_daily_demand=100.0,
        annual_growth_rate=0.15,
        max_expansion_actions_per_year=1,
        max_total_build_ahead_actions=3,
    )

    result = run_native_design_horizon_planning(request)

    phased_rows = result.phased_strategy.conventional_lifecycle.annual_rows
    assert phased_rows[1].annual_capex >= 0.0
    assert phased_rows[1].discounted_capex <= phased_rows[1].annual_capex + 1e-9

    assert "Conventional" in result.strategy_comparison_by_pathway
    assert "MRT" in result.strategy_comparison_by_pathway
    assert result.strategy_comparison_by_pathway["Conventional"].preferred_strategy in {"phased", "build_ahead", "tie"}
    assert result.strategy_comparison_by_pathway["MRT"].preferred_strategy in {"phased", "build_ahead", "tie"}


def test_build_ahead_marks_infeasible_when_bounded_sizing_cannot_reach_peak(monkeypatch):
    monkeypatch.setattr(horizon_module, "run_native_reliability_engine", _fake_reliability_engine)
    monkeypatch.setattr(horizon_module, "run_native_decision_pipeline", _fake_decision_pipeline)

    request = DesignHorizonPlanningRequest(
        pipeline_template=_pipeline_template(),
        seeds=(1, 2),
        demand_mode="explicit",
        explicit_daily_demand_by_year=[500.0, 500.0, 500.0, 500.0, 500.0],
        max_expansion_actions_per_year=1,
        max_total_build_ahead_actions=1,
        allowed_expansion_resources={
            "Conventional": ("uptake",),
            "MRT": ("uptake",),
        },
    )

    result = run_native_design_horizon_planning(request)

    conventional_strategy = result.strategy_comparison_by_pathway["Conventional"]
    mrt_strategy = result.strategy_comparison_by_pathway["MRT"]

    assert conventional_strategy.build_ahead_feasible is False
    assert mrt_strategy.build_ahead_feasible is False
    assert conventional_strategy.build_ahead_infeasibility_reason is not None
    assert mrt_strategy.build_ahead_infeasibility_reason is not None
    assert conventional_strategy.preferred_strategy == "phased"
    assert mrt_strategy.preferred_strategy == "phased"


def test_phased_uses_single_combo_decision_when_no_single_resource_qualifies(monkeypatch):
    monkeypatch.setattr(horizon_module, "run_native_reliability_engine", _fake_reliability_engine)
    monkeypatch.setattr(horizon_module, "run_native_decision_pipeline", _fake_decision_pipeline)

    request = DesignHorizonPlanningRequest(
        pipeline_template=_pipeline_template(),
        seeds=(1, 2),
        demand_mode="explicit",
        explicit_daily_demand_by_year=[135.0, 135.0, 135.0, 135.0, 135.0],
        max_expansion_actions_per_year=1,
        max_total_build_ahead_actions=1,
        allowed_expansion_resources={
            "Conventional": ("scanner", "injection"),
            "MRT": ("scanner",),
        },
    )

    result = run_native_design_horizon_planning(request)
    year_one_conventional_actions = result.year_results[0].conventional.expansion_actions

    assert len(year_one_conventional_actions) == 1
    assert year_one_conventional_actions[0].resource.startswith("combo(")
    assert "scanner=1" in year_one_conventional_actions[0].resource
    assert "injection=1" in year_one_conventional_actions[0].resource
    assert "multi-resource combination" in year_one_conventional_actions[0].reason

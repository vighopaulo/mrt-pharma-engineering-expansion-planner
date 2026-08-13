from __future__ import annotations

import math

import pytest

from cyclotron_production_windows import CyclotronProductionCapability
from patient_radionuclide_demand import FacilityDayPatientDemand
from production_clinical_schedule import ProductionClinicalScenario, build_production_clinical_schedule
from stochastic_design_day import (
    ActivityDemandModel,
    DesignDayDemandScenario,
    generate_design_day_demand,
    simulate_design_days,
    summarize_design_day_simulations,
)


def _fixed_model(activity: float) -> ActivityDemandModel:
    return ActivityDemandModel(model_type="fixed", fixed_activity_mbq=activity)


def _bounded_model(mean: float = 200.0, stddev: float = 25.0, lower: float = 150.0, upper: float = 250.0) -> ActivityDemandModel:
    return ActivityDemandModel(
        model_type="bounded_normal",
        mean_activity_mbq=mean,
        stddev_activity_mbq=stddev,
        lower_bound_mbq=lower,
        upper_bound_mbq=upper,
    )


def _scenario(**overrides) -> DesignDayDemandScenario:
    payload = {
        "target_patients_per_day": 12,
        "radionuclide_mix": {"F-18": 0.5, "Ga-68": 0.3, "Tc-99m": 0.2},
        "activity_distribution_by_radionuclide": {
            "F-18": _bounded_model(200.0, 20.0, 160.0, 240.0),
            "Ga-68": _bounded_model(150.0, 15.0, 120.0, 180.0),
            "Tc-99m": _bounded_model(600.0, 40.0, 500.0, 700.0),
        },
        "day_type": "typical",
        "seed": 123,
    }
    payload.update(overrides)
    return DesignDayDemandScenario(**payload)


def _capability() -> CyclotronProductionCapability:
    return CyclotronProductionCapability(
        cyclotron_id="DEMO",
        supported_radionuclides=("F-18", "Ga-68", "Tc-99m"),
        max_simultaneous_production_streams=2,
        production_cycle_minutes_by_radionuclide={"F-18": 30.0, "Ga-68": 20.0, "Tc-99m": 25.0},
        simultaneously_compatible_radionuclide_sets=(frozenset(("F-18", "Ga-68")),),
    )


def test_fixed_seed_reproducibility():
    scenario = _scenario(seed=7)
    assert generate_design_day_demand(scenario) == generate_design_day_demand(scenario)


def test_different_seed_variation():
    day_a = generate_design_day_demand(_scenario(seed=7))
    day_b = generate_design_day_demand(_scenario(seed=8))
    assert day_a != day_b


def test_exact_target_patient_count():
    result = generate_design_day_demand(_scenario(target_patients_per_day=25, seed=1))
    assert result.patient_count == 25


def test_unique_patient_ids():
    result = generate_design_day_demand(_scenario(seed=1))
    patient_ids = [patient.patient_id for patient in result.generated_demand.patients]
    assert len(patient_ids) == len(set(patient_ids))


def test_valid_radionuclide_assignment():
    result = generate_design_day_demand(_scenario(seed=1))
    assert {patient.radionuclide for patient in result.generated_demand.patients}.issubset({"F-18", "Ga-68", "Tc-99m"})


def test_normalized_radionuclide_weights_are_respected_from_scaled_inputs():
    result_a = generate_design_day_demand(_scenario(radionuclide_mix={"F-18": 5.0, "Ga-68": 3.0, "Tc-99m": 2.0}, seed=11))
    result_b = generate_design_day_demand(_scenario(radionuclide_mix={"F-18": 0.5, "Ga-68": 0.3, "Tc-99m": 0.2}, seed=11))
    assert result_a.generated_demand == result_b.generated_demand
    assert result_a.patient_count_by_radionuclide == result_b.patient_count_by_radionuclide
    assert result_a.total_activity_by_radionuclide == result_b.total_activity_by_radionuclide


def test_invalid_mix_rejection():
    with pytest.raises(ValueError, match="must have positive total weight"):
        _scenario(radionuclide_mix={"F-18": 0.0, "Ga-68": 0.0, "Tc-99m": 0.0})


def test_fixed_activity_generation():
    scenario = _scenario(
        activity_distribution_by_radionuclide={"F-18": _fixed_model(200.0), "Ga-68": _fixed_model(150.0), "Tc-99m": _fixed_model(600.0)},
        seed=3,
    )
    result = generate_design_day_demand(scenario)
    expected = {"F-18": 200.0, "Ga-68": 150.0, "Tc-99m": 600.0}
    assert all(patient.prescribed_activity_mbq == expected[patient.radionuclide] for patient in result.generated_demand.patients)


def test_bounded_stochastic_activity_generation():
    result = generate_design_day_demand(_scenario(seed=5))
    activities = [patient.prescribed_activity_mbq for patient in result.generated_demand.patients]
    assert len(set(activities)) > 1


def test_activity_lower_bound_enforcement():
    scenario = _scenario(
        activity_distribution_by_radionuclide={"F-18": _bounded_model(1.0, 1000.0, 160.0, 240.0), "Ga-68": _fixed_model(150.0), "Tc-99m": _fixed_model(600.0)},
        radionuclide_mix={"F-18": 1.0, "Ga-68": 0.0, "Tc-99m": 0.0},
        seed=4,
    )
    result = generate_design_day_demand(scenario)
    assert all(patient.prescribed_activity_mbq >= 160.0 for patient in result.generated_demand.patients)


def test_activity_upper_bound_enforcement():
    scenario = _scenario(
        activity_distribution_by_radionuclide={"F-18": _bounded_model(1000.0, 1000.0, 160.0, 240.0), "Ga-68": _fixed_model(150.0), "Tc-99m": _fixed_model(600.0)},
        radionuclide_mix={"F-18": 1.0, "Ga-68": 0.0, "Tc-99m": 0.0},
        seed=4,
    )
    result = generate_design_day_demand(scenario)
    assert all(patient.prescribed_activity_mbq <= 240.0 for patient in result.generated_demand.patients)


def test_typical_day_generation():
    result = generate_design_day_demand(_scenario(day_type="typical", seed=9))
    assert result.scenario.day_type == "typical"


def test_peak_day_generation():
    result = generate_design_day_demand(_scenario(day_type="peak", peak_activity_multiplier=1.2, seed=9))
    assert result.scenario.day_type == "peak"


def test_peak_demand_greater_than_or_equal_to_comparable_typical_day():
    typical = generate_design_day_demand(_scenario(day_type="typical", seed=9))
    peak = generate_design_day_demand(_scenario(day_type="peak", peak_activity_multiplier=1.2, seed=9))
    assert sum(peak.total_activity_by_radionuclide.values()) >= sum(typical.total_activity_by_radionuclide.values())


def test_monte_carlo_simulation_count():
    result = simulate_design_days(_scenario(seed=17), 25)
    assert len(result.simulated_days) == 25


def test_monte_carlo_seed_reproducibility():
    scenario = _scenario(seed=17)
    assert simulate_design_days(scenario, 10) == simulate_design_days(scenario, 10)


def test_independent_simulated_days():
    result = simulate_design_days(_scenario(seed=17), 5)
    assert len({tuple((patient.radionuclide, patient.prescribed_activity_mbq) for patient in day.generated_demand.patients) for day in result.simulated_days}) > 1


def test_total_activity_aggregation_by_radionuclide():
    result = generate_design_day_demand(_scenario(seed=1, radionuclide_mix={"F-18": 1.0, "Ga-68": 0.0, "Tc-99m": 0.0}, activity_distribution_by_radionuclide={"F-18": _fixed_model(200.0), "Ga-68": _fixed_model(150.0), "Tc-99m": _fixed_model(600.0)}))
    assert math.isclose(result.total_activity_by_radionuclide["F-18"], 12 * 200.0, rel_tol=0.0, abs_tol=1e-9)


def test_mean_summary_statistics():
    summary = summarize_design_day_simulations(simulate_design_days(_scenario(seed=17), 8))
    assert summary.simulated_day_count == 8
    assert summary.mean_patients_per_day == 12.0


def test_maximum_summary_statistics():
    summary = summarize_design_day_simulations(
        simulate_design_days(_scenario(seed=17, patient_count_bounds=(10, 14)), 8)
    )
    assert summary.max_patients_per_day >= summary.min_patients_per_day


def test_percentile_statistics():
    summary = summarize_design_day_simulations(simulate_design_days(_scenario(seed=17), 8), percentiles=(50.0, 95.0))
    assert 50.0 in summary.percentile_activity_by_radionuclide
    assert 95.0 in summary.percentile_activity_by_radionuclide


def test_compatibility_with_facilitydaypatientdemand():
    result = generate_design_day_demand(_scenario(seed=1))
    assert isinstance(result.generated_demand, FacilityDayPatientDemand)


def test_compatibility_with_productionclinicalscenario():
    generated = generate_design_day_demand(_scenario(seed=1))
    scenario = ProductionClinicalScenario(
        facility_day_demand=generated.generated_demand,
        requested_batch_count_by_radionuclide={radionuclide: 1 for radionuclide in generated.patient_count_by_radionuclide},
        cyclotron_capability=_capability(),
        transport_minutes=5.0,
        injection_service_minutes=5.0,
        uptake_minutes=5.0,
        scanner_service_minutes=5.0,
        injection_resources=1,
        uptake_resources=1,
        scanners=1,
        distribution_concurrency=1,
    )
    assert isinstance(scenario, ProductionClinicalScenario)


def test_generated_design_day_runs_through_production_clinical_schedule():
    generated = generate_design_day_demand(_scenario(seed=1))
    scenario = ProductionClinicalScenario(
        facility_day_demand=generated.generated_demand,
        requested_batch_count_by_radionuclide={radionuclide: 1 for radionuclide in generated.patient_count_by_radionuclide},
        cyclotron_capability=_capability(),
        transport_minutes=5.0,
        injection_service_minutes=5.0,
        uptake_minutes=5.0,
        scanner_service_minutes=5.0,
        injection_resources=1,
        uptake_resources=1,
        scanners=1,
        distribution_concurrency=1,
        production_horizon_minutes=1080.0,
    )
    result = build_production_clinical_schedule(scenario)
    assert result.clinical_schedule.total_patients_considered == generated.patient_count


def test_invalid_patient_count():
    with pytest.raises(ValueError, match="target_patients_per_day must be greater than zero"):
        _scenario(target_patients_per_day=0)


def test_invalid_activity_model():
    with pytest.raises(ValueError, match="Unsupported activity model"):
        ActivityDemandModel(model_type="unknown")  # type: ignore[arg-type]


def test_invalid_day_type():
    with pytest.raises(ValueError, match="day_type must be 'typical' or 'peak'"):
        _scenario(day_type="holiday")  # type: ignore[arg-type]


def test_invalid_monte_carlo_count():
    with pytest.raises(ValueError, match="simulation_count must be greater than zero"):
        simulate_design_days(_scenario(), 0)
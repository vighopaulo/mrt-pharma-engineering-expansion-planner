from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable, Mapping, Literal

from diagnostics import load_radionuclide_half_lives
from patient_radionuclide_demand import FacilityDayPatientDemand, PatientRadionuclideDemand


DayType = Literal["typical", "peak"]
ActivityModelType = Literal["fixed", "bounded_normal"]


def _canonical_radionuclide_lookup() -> dict[str, float]:
    return load_radionuclide_half_lives()


def _normalize_radionuclide(radionuclide: str) -> str:
    if not isinstance(radionuclide, str):
        raise ValueError("radionuclide must be a non-empty string")
    name = radionuclide.strip()
    if not name:
        raise ValueError("radionuclide must be a non-empty string")
    if name not in _canonical_radionuclide_lookup():
        raise ValueError(f"Unknown radionuclide: {name}")
    return name


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (len(sorted_values) - 1) * percentile / 100.0
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = rank - lower
    return float(sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction)


@dataclass(frozen=True)
class ActivityDemandModel:
    model_type: ActivityModelType
    fixed_activity_mbq: float | None = None
    mean_activity_mbq: float | None = None
    stddev_activity_mbq: float | None = None
    lower_bound_mbq: float | None = None
    upper_bound_mbq: float | None = None

    def __post_init__(self) -> None:
        if self.model_type == "fixed":
            if self.fixed_activity_mbq is None:
                raise ValueError("fixed activity model requires fixed_activity_mbq")
            if float(self.fixed_activity_mbq) <= 0.0:
                raise ValueError("fixed_activity_mbq must be greater than zero")
        elif self.model_type == "bounded_normal":
            required = {
                "mean_activity_mbq": self.mean_activity_mbq,
                "stddev_activity_mbq": self.stddev_activity_mbq,
                "lower_bound_mbq": self.lower_bound_mbq,
                "upper_bound_mbq": self.upper_bound_mbq,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                raise ValueError(f"bounded_normal activity model requires {', '.join(missing)}")
            if float(self.stddev_activity_mbq) < 0.0:
                raise ValueError("stddev_activity_mbq must be non-negative")
            if float(self.lower_bound_mbq) <= 0.0:
                raise ValueError("lower_bound_mbq must be greater than zero")
            if float(self.upper_bound_mbq) < float(self.lower_bound_mbq):
                raise ValueError("upper_bound_mbq must be greater than or equal to lower_bound_mbq")
        else:
            raise ValueError(f"Unsupported activity model: {self.model_type}")


@dataclass(frozen=True)
class DesignDayDemandScenario:
    target_patients_per_day: int
    radionuclide_mix: Mapping[str, float]
    activity_distribution_by_radionuclide: Mapping[str, ActivityDemandModel]
    day_type: DayType = "typical"
    peak_patient_multiplier: float = 1.0
    peak_activity_multiplier: float = 1.0
    seed: int = 0
    patient_count_bounds: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        if int(self.target_patients_per_day) <= 0:
            raise ValueError("target_patients_per_day must be greater than zero")
        if self.day_type not in {"typical", "peak"}:
            raise ValueError("day_type must be 'typical' or 'peak'")
        if not self.radionuclide_mix:
            raise ValueError("radionuclide_mix must not be empty")
        if float(self.peak_patient_multiplier) <= 0.0:
            raise ValueError("peak_patient_multiplier must be greater than zero")
        if float(self.peak_activity_multiplier) <= 0.0:
            raise ValueError("peak_activity_multiplier must be greater than zero")
        if self.day_type == "peak" and self.peak_patient_multiplier == 1.0 and self.peak_activity_multiplier == 1.0:
            raise ValueError("peak day requires an explicit peak multiplier greater than 1.0")

        normalized_mix: dict[str, float] = {}
        total_weight = 0.0
        positive_radionuclides: list[str] = []
        for radionuclide, weight in self.radionuclide_mix.items():
            normalized = _normalize_radionuclide(radionuclide)
            numeric_weight = float(weight)
            if numeric_weight < 0.0:
                raise ValueError("radionuclide mix weights must be non-negative")
            normalized_mix[normalized] = numeric_weight
            total_weight += numeric_weight
            if numeric_weight > 0.0:
                positive_radionuclides.append(normalized)

        if total_weight <= 0.0:
            raise ValueError("radionuclide mix must have positive total weight")
        if len(set(positive_radionuclides)) > 3:
            raise ValueError("Design day cannot contain more than three positive-weight radionuclides")

        normalized_activity_models: dict[str, ActivityDemandModel] = {}
        for radionuclide, model in self.activity_distribution_by_radionuclide.items():
            normalized_activity_models[_normalize_radionuclide(radionuclide)] = model

        missing_models = sorted(set(normalized_mix).difference(normalized_activity_models))
        if missing_models:
            raise ValueError(f"Missing activity distribution for radionuclides: {missing_models}")

        extra_models = sorted(set(normalized_activity_models).difference(normalized_mix))
        if extra_models:
            raise ValueError(f"Activity distributions provided for radionuclides not in mix: {extra_models}")

        if self.patient_count_bounds is not None:
            lower, upper = self.patient_count_bounds
            if int(lower) <= 0 or int(upper) <= 0:
                raise ValueError("patient_count_bounds must contain positive integers")
            if int(lower) > int(upper):
                raise ValueError("patient_count_bounds lower bound must not exceed upper bound")
            object.__setattr__(self, "patient_count_bounds", (int(lower), int(upper)))

        object.__setattr__(self, "target_patients_per_day", int(self.target_patients_per_day))
        object.__setattr__(self, "radionuclide_mix", normalized_mix)
        object.__setattr__(self, "activity_distribution_by_radionuclide", normalized_activity_models)
        object.__setattr__(self, "seed", int(self.seed))


@dataclass(frozen=True)
class DesignDaySimulationResult:
    scenario: DesignDayDemandScenario
    generated_demand: FacilityDayPatientDemand
    patient_count: int
    patient_count_by_radionuclide: Mapping[str, int]
    total_activity_by_radionuclide: Mapping[str, float]


@dataclass(frozen=True)
class DesignDayMonteCarloResult:
    scenario: DesignDayDemandScenario
    simulated_days: tuple[DesignDaySimulationResult, ...]


@dataclass(frozen=True)
class DesignDaySummaryStatistics:
    simulated_day_count: int
    mean_patients_per_day: float
    min_patients_per_day: int
    max_patients_per_day: int
    mean_activity_by_radionuclide: Mapping[str, float]
    max_activity_by_radionuclide: Mapping[str, float]
    percentile_activity_by_radionuclide: Mapping[float, Mapping[str, float]]


def _effective_patient_count(scenario: DesignDayDemandScenario, rng: random.Random) -> int:
    multiplier = scenario.peak_patient_multiplier if scenario.day_type == "peak" else 1.0
    if scenario.patient_count_bounds is None:
        return max(1, int(round(scenario.target_patients_per_day * multiplier)))

    lower, upper = scenario.patient_count_bounds
    scaled_lower = max(1, int(round(lower * multiplier)))
    scaled_upper = max(1, int(round(upper * multiplier)))
    if scaled_lower > scaled_upper:
        scaled_lower, scaled_upper = scaled_upper, scaled_lower
    return rng.randint(scaled_lower, scaled_upper)


def _normalized_positive_mix(scenario: DesignDayDemandScenario) -> tuple[tuple[str, float], ...]:
    positives = [(radionuclide, weight) for radionuclide, weight in scenario.radionuclide_mix.items() if weight > 0.0]
    total = sum(weight for _, weight in positives)
    return tuple((radionuclide, weight / total) for radionuclide, weight in positives)


def _sample_radionuclide(rng: random.Random, normalized_mix: tuple[tuple[str, float], ...]) -> str:
    threshold = rng.random()
    cumulative = 0.0
    for radionuclide, probability in normalized_mix:
        cumulative += probability
        if threshold <= cumulative + 1e-12:
            return radionuclide
    return normalized_mix[-1][0]


def _sample_activity(
    rng: random.Random,
    model: ActivityDemandModel,
    peak_activity_multiplier: float,
    day_type: DayType,
) -> float:
    if model.model_type == "fixed":
        base = float(model.fixed_activity_mbq)
    elif model.model_type == "bounded_normal":
        sampled = rng.gauss(float(model.mean_activity_mbq), float(model.stddev_activity_mbq))
        base = min(max(sampled, float(model.lower_bound_mbq)), float(model.upper_bound_mbq))
    else:
        raise ValueError(f"Unsupported activity model: {model.model_type}")

    multiplier = peak_activity_multiplier if day_type == "peak" else 1.0
    activity = base * multiplier
    if activity <= 0.0:
        raise ValueError("Generated activity must be greater than zero")
    return activity


def _count_by_radionuclide(patients: Iterable[PatientRadionuclideDemand]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for patient in patients:
        counts[patient.radionuclide] = counts.get(patient.radionuclide, 0) + 1
    return counts


def _activity_by_radionuclide(patients: Iterable[PatientRadionuclideDemand]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for patient in patients:
        totals[patient.radionuclide] = totals.get(patient.radionuclide, 0.0) + patient.prescribed_activity_mbq
    return totals


def generate_design_day_demand(scenario: DesignDayDemandScenario) -> DesignDaySimulationResult:
    rng = random.Random(scenario.seed)
    patient_count = _effective_patient_count(scenario, rng)
    normalized_mix = _normalized_positive_mix(scenario)

    patients: list[PatientRadionuclideDemand] = []
    for patient_index in range(patient_count):
        radionuclide = _sample_radionuclide(rng, normalized_mix)
        activity = _sample_activity(
            rng,
            scenario.activity_distribution_by_radionuclide[radionuclide],
            scenario.peak_activity_multiplier,
            scenario.day_type,
        )
        patients.append(
            PatientRadionuclideDemand(
                patient_id=f"P{patient_index + 1}",
                radionuclide=radionuclide,
                prescribed_activity_mbq=activity,
            )
        )

    generated_demand = FacilityDayPatientDemand(patients=tuple(patients))
    counts = _count_by_radionuclide(generated_demand.patients)
    totals = _activity_by_radionuclide(generated_demand.patients)

    return DesignDaySimulationResult(
        scenario=scenario,
        generated_demand=generated_demand,
        patient_count=patient_count,
        patient_count_by_radionuclide=counts,
        total_activity_by_radionuclide=totals,
    )


def simulate_design_days(
    scenario: DesignDayDemandScenario,
    simulation_count: int,
) -> DesignDayMonteCarloResult:
    if int(simulation_count) <= 0:
        raise ValueError("simulation_count must be greater than zero")
    master_rng = random.Random(scenario.seed)
    days: list[DesignDaySimulationResult] = []
    for _ in range(int(simulation_count)):
        sub_seed = master_rng.randrange(0, 2**63)
        day_scenario = DesignDayDemandScenario(
            target_patients_per_day=scenario.target_patients_per_day,
            radionuclide_mix=scenario.radionuclide_mix,
            activity_distribution_by_radionuclide=scenario.activity_distribution_by_radionuclide,
            day_type=scenario.day_type,
            peak_patient_multiplier=scenario.peak_patient_multiplier,
            peak_activity_multiplier=scenario.peak_activity_multiplier,
            seed=sub_seed,
            patient_count_bounds=scenario.patient_count_bounds,
        )
        days.append(generate_design_day_demand(day_scenario))
    return DesignDayMonteCarloResult(scenario=scenario, simulated_days=tuple(days))


def summarize_design_day_simulations(
    simulation_results: DesignDayMonteCarloResult | Iterable[DesignDaySimulationResult],
    *,
    percentiles: tuple[float, ...] = (95.0,),
) -> DesignDaySummaryStatistics:
    if isinstance(simulation_results, DesignDayMonteCarloResult):
        days = list(simulation_results.simulated_days)
    else:
        days = list(simulation_results)

    if not days:
        raise ValueError("simulation_results must not be empty")

    for percentile in percentiles:
        if percentile < 0.0 or percentile > 100.0:
            raise ValueError("percentiles must be between 0 and 100")

    patient_counts = [day.patient_count for day in days]
    radionuclides = sorted({rad for day in days for rad in day.scenario.radionuclide_mix if day.scenario.radionuclide_mix[rad] > 0.0})

    mean_activity_by_radionuclide: dict[str, float] = {}
    max_activity_by_radionuclide: dict[str, float] = {}
    percentile_activity_by_radionuclide: dict[float, dict[str, float]] = {}

    for radionuclide in radionuclides:
        totals = [float(day.total_activity_by_radionuclide.get(radionuclide, 0.0)) for day in days]
        mean_activity_by_radionuclide[radionuclide] = sum(totals) / len(totals)
        max_activity_by_radionuclide[radionuclide] = max(totals)

    for percentile in percentiles:
        percentile_activity_by_radionuclide[float(percentile)] = {
            radionuclide: _percentile(
                [float(day.total_activity_by_radionuclide.get(radionuclide, 0.0)) for day in days],
                float(percentile),
            )
            for radionuclide in radionuclides
        }

    return DesignDaySummaryStatistics(
        simulated_day_count=len(days),
        mean_patients_per_day=sum(patient_counts) / len(patient_counts),
        min_patients_per_day=min(patient_counts),
        max_patients_per_day=max(patient_counts),
        mean_activity_by_radionuclide=mean_activity_by_radionuclide,
        max_activity_by_radionuclide=max_activity_by_radionuclide,
        percentile_activity_by_radionuclide=percentile_activity_by_radionuclide,
    )
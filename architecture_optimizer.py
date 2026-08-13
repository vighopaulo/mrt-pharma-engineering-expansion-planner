from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from engineering import room_capacity, scanner_capacity
from lifecycle_economics import (
    LifecycleEconomicResult,
    compare_lifecycle_results,
    evaluate_lifecycle_economics,
)
from models import PlannerAssumptions


Pathway = Literal["Conventional", "MRT"]


@dataclass(frozen=True)
class FacilityEnvelope:
    max_scanners: int
    max_injection_resources: int
    max_uptake_resources: int
    max_mrt_endpoints: int
    min_scanners: int = 0
    min_injection_resources: int = 0
    min_uptake_resources: int = 0
    min_mrt_endpoints: int = 1


@dataclass(frozen=True)
class ArchitectureCandidate:
    pathway: Pathway
    scanners: int
    injection_resources: int
    uptake_resources: int
    endpoints: int
    installed_capacity_per_day: float
    capex: float
    annual_opex: float
    lifecycle: LifecycleEconomicResult
    final_npv: float
    payback_year: float | None


@dataclass(frozen=True)
class PathwayOptimizationResult:
    pathway: Pathway
    optimal_candidate: ArchitectureCandidate
    feasible_candidate_count: int
    feasible_candidates: list[ArchitectureCandidate]


@dataclass(frozen=True)
class ArchitectureComparisonResult:
    conventional: PathwayOptimizationResult
    mrt: PathwayOptimizationResult
    incremental_capex_mrt_minus_conventional: float
    incremental_annual_opex_mrt_minus_conventional: float
    incremental_installed_capacity_mrt_minus_conventional: float
    incremental_final_npv_mrt_minus_conventional: float
    economic_crossover_year: float | None


@dataclass(frozen=True)
class OptimizationDemand:
    starting_demand_per_day: float
    annual_growth_rate: float = 0.0
    explicit_daily_demand_by_year: list[float] | None = None


def _clinical_capacity_per_day(
    scanners: int,
    injection_resources: int,
    uptake_resources: int,
    assumptions: PlannerAssumptions,
) -> float:
    scan_cap = scanner_capacity(
        scanners,
        assumptions.operating_hours_per_day,
        assumptions.scanner_cycle_min,
        assumptions.scanner_availability_pct,
    )
    injection_cap = room_capacity(
        injection_resources,
        assumptions.operating_hours_per_day,
        assumptions.injection_cycle_min,
    )
    uptake_cap = room_capacity(
        uptake_resources,
        assumptions.operating_hours_per_day,
        assumptions.uptake_cycle_min,
    )
    return min(scan_cap, injection_cap, uptake_cap)


def _conventional_capex(
    scanners: int,
    injection_resources: int,
    uptake_resources: int,
    assumptions: PlannerAssumptions,
) -> float:
    return (
        scanners * assumptions.scanner_capex
        + (injection_resources + uptake_resources) * assumptions.additional_room_capex
    )


def _conventional_annual_opex(
    scanners: int,
    injection_resources: int,
    uptake_resources: int,
    assumptions: PlannerAssumptions,
) -> float:
    return (
        scanners * assumptions.scanner_incremental_opex
        + (injection_resources + uptake_resources) * assumptions.room_incremental_opex
    )


def _mrt_capex(
    scanners: int,
    injection_resources: int,
    uptake_resources: int,
    endpoints: int,
    assumptions: PlannerAssumptions,
) -> float:
    return (
        assumptions.mrt_infrastructure_capex
        + scanners * assumptions.scanner_capex
        + (injection_resources + uptake_resources) * assumptions.additional_room_capex
        + endpoints * assumptions.endpoint_capex
    )


def _mrt_annual_opex(
    scanners: int,
    injection_resources: int,
    uptake_resources: int,
    endpoints: int,
    assumptions: PlannerAssumptions,
) -> float:
    return (
        scanners * assumptions.scanner_incremental_opex
        + (injection_resources + uptake_resources) * assumptions.room_incremental_opex
        + endpoints * assumptions.endpoint_incremental_opex
    )


def evaluate_architecture_candidate(
    *,
    pathway: Pathway,
    scanners: int,
    injection_resources: int,
    uptake_resources: int,
    endpoints: int,
    assumptions: PlannerAssumptions,
    demand: OptimizationDemand,
) -> ArchitectureCandidate | None:
    if pathway not in ("Conventional", "MRT"):
        raise ValueError("pathway must be Conventional or MRT")
    if scanners < 0 or injection_resources < 0 or uptake_resources < 0 or endpoints < 0:
        raise ValueError("resource counts must be non-negative")

    installed_capacity = _clinical_capacity_per_day(
        scanners,
        injection_resources,
        uptake_resources,
        assumptions,
    )
    if installed_capacity <= 0.0:
        return None

    if pathway == "Conventional":
        capex = _conventional_capex(scanners, injection_resources, uptake_resources, assumptions)
        annual_opex = _conventional_annual_opex(scanners, injection_resources, uptake_resources, assumptions)
        endpoint_count = 0
    else:
        capex = _mrt_capex(scanners, injection_resources, uptake_resources, endpoints, assumptions)
        annual_opex = _mrt_annual_opex(scanners, injection_resources, uptake_resources, endpoints, assumptions)
        endpoint_count = endpoints

    lifecycle = evaluate_lifecycle_economics(
        initial_capex=capex,
        installed_capacity_per_day=installed_capacity,
        annual_opex=annual_opex,
        revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=assumptions.operating_days_per_year,
        discount_rate_pct=assumptions.discount_rate_pct,
        analysis_years=assumptions.analysis_years,
        starting_demand_per_day=demand.starting_demand_per_day,
        annual_demand_growth_rate=demand.annual_growth_rate,
        explicit_daily_demand_by_year=demand.explicit_daily_demand_by_year,
    )

    return ArchitectureCandidate(
        pathway=pathway,
        scanners=scanners,
        injection_resources=injection_resources,
        uptake_resources=uptake_resources,
        endpoints=endpoint_count,
        installed_capacity_per_day=installed_capacity,
        capex=capex,
        annual_opex=annual_opex,
        lifecycle=lifecycle,
        final_npv=lifecycle.final_npv,
        payback_year=lifecycle.payback_year,
    )


def optimize_pathway(
    *,
    pathway: Pathway,
    envelope: FacilityEnvelope,
    assumptions: PlannerAssumptions,
    demand: OptimizationDemand,
) -> PathwayOptimizationResult:
    candidates: list[ArchitectureCandidate] = []

    endpoint_range: range
    if pathway == "MRT":
        endpoint_range = range(envelope.min_mrt_endpoints, envelope.max_mrt_endpoints + 1)
    else:
        endpoint_range = range(0, 1)

    for scanners in range(envelope.min_scanners, envelope.max_scanners + 1):
        for injection_resources in range(envelope.min_injection_resources, envelope.max_injection_resources + 1):
            for uptake_resources in range(envelope.min_uptake_resources, envelope.max_uptake_resources + 1):
                for endpoints in endpoint_range:
                    candidate = evaluate_architecture_candidate(
                        pathway=pathway,
                        scanners=scanners,
                        injection_resources=injection_resources,
                        uptake_resources=uptake_resources,
                        endpoints=endpoints,
                        assumptions=assumptions,
                        demand=demand,
                    )
                    if candidate is not None:
                        candidates.append(candidate)

    if not candidates:
        raise ValueError(f"No feasible candidates found for {pathway}")

    optimal = max(
        candidates,
        key=lambda c: (
            c.final_npv,
            c.installed_capacity_per_day,
            -c.capex,
            -c.annual_opex,
            -c.endpoints,
        ),
    )

    return PathwayOptimizationResult(
        pathway=pathway,
        optimal_candidate=optimal,
        feasible_candidate_count=len(candidates),
        feasible_candidates=candidates,
    )


def optimize_fixed_envelope_architecture(
    *,
    envelope: FacilityEnvelope,
    assumptions: PlannerAssumptions,
    demand: OptimizationDemand,
) -> ArchitectureComparisonResult:
    conventional_result = optimize_pathway(
        pathway="Conventional",
        envelope=envelope,
        assumptions=assumptions,
        demand=demand,
    )
    mrt_result = optimize_pathway(
        pathway="MRT",
        envelope=envelope,
        assumptions=assumptions,
        demand=demand,
    )

    lifecycle_comparison = compare_lifecycle_results(
        conventional=conventional_result.optimal_candidate.lifecycle,
        mrt=mrt_result.optimal_candidate.lifecycle,
    )

    return ArchitectureComparisonResult(
        conventional=conventional_result,
        mrt=mrt_result,
        incremental_capex_mrt_minus_conventional=(
            mrt_result.optimal_candidate.capex - conventional_result.optimal_candidate.capex
        ),
        incremental_annual_opex_mrt_minus_conventional=(
            mrt_result.optimal_candidate.annual_opex - conventional_result.optimal_candidate.annual_opex
        ),
        incremental_installed_capacity_mrt_minus_conventional=(
            mrt_result.optimal_candidate.installed_capacity_per_day
            - conventional_result.optimal_candidate.installed_capacity_per_day
        ),
        incremental_final_npv_mrt_minus_conventional=(
            mrt_result.optimal_candidate.final_npv - conventional_result.optimal_candidate.final_npv
        ),
        economic_crossover_year=lifecycle_comparison.economic_crossover_year,
    )

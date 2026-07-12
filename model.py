from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ModelInputs:
    # Current hospital and demand
    current_patients_day: float
    target_patients_day: float
    current_scanners: int
    max_additional_scanners: int
    operating_hours_day: float
    scanner_cycle_minutes: float
    scanner_availability_pct: float

    # Rooms
    current_injection_rooms: int
    current_uptake_rooms: int
    max_additional_injection_rooms: int
    max_additional_uptake_rooms: int
    patients_per_injection_room_day: float
    patients_per_uptake_room_day: float

    # Production
    current_dose_capacity_day: float
    max_production_upgrade_pct: int

    # MRT deployment
    max_mrt_enabled_inpatient_rooms: int
    patients_per_enabled_inpatient_room_day: float
    other_mrt_destinations: int

    # Capital costs
    scanner_capex: float
    injection_room_capex: float
    uptake_room_capex: float
    conventional_upgrade_capex_per_10pct: float
    hybrid_upgrade_capex_per_10pct: float
    mrt_core_capex: float
    mrt_endpoint_capex: float

    # Operating costs
    annual_base_opex_conventional: float
    annual_base_opex_hybrid: float
    annual_opex_per_scanner: float
    annual_opex_per_injection_room: float
    annual_opex_per_uptake_room: float
    annual_mrt_maintenance: float
    annual_opex_per_mrt_endpoint: float

    # Financial assumptions
    net_contribution_per_incremental_patient: float
    operating_days_year: int
    analysis_years: int
    discount_rate_pct: float
    maximum_capex_budget: float


@dataclass
class Candidate:
    architecture: str
    installed_capacity_day: float
    patients_served_day: float
    reserve_capacity_day: float
    incremental_patients_day: float
    capex: float
    annual_opex: float
    annual_incremental_revenue: float
    annual_net_cash_flow: float
    production_upgrade_pct: int
    additional_scanners: int
    additional_injection_rooms: int
    additional_uptake_rooms: int
    mrt_enabled_inpatient_rooms: int
    mrt_endpoints: int
    dedicated_rooms_avoided: int
    payback_years: float = math.inf
    roi_pct: float = 0.0
    npv: float = 0.0


@dataclass
class ModelResults:
    current_physical_capacity_day: float
    conventional_candidates_evaluated: int
    hybrid_candidates_evaluated: int
    feasible_candidates: int
    positive_npv_candidates: int
    best_conventional: Optional[Candidate]
    best_hybrid: Optional[Candidate]
    decision: Optional[Candidate]
    ranked_candidates: List[Candidate]


def scanner_capacity(
    scanners: int,
    operating_hours_day: float,
    scanner_cycle_minutes: float,
    availability_pct: float,
) -> float:
    if scanner_cycle_minutes <= 0:
        return 0.0
    return (
        scanners
        * operating_hours_day
        * 60.0
        / scanner_cycle_minutes
        * availability_pct
        / 100.0
    )


def financialize(candidate: Candidate, inputs: ModelInputs) -> Candidate:
    candidate.patients_served_day = min(
        candidate.installed_capacity_day,
        inputs.target_patients_day,
    )
    candidate.reserve_capacity_day = max(
        0.0,
        candidate.installed_capacity_day - inputs.target_patients_day,
    )
    candidate.incremental_patients_day = max(
        0.0,
        candidate.patients_served_day - inputs.current_patients_day,
    )
    candidate.annual_incremental_revenue = (
        candidate.incremental_patients_day
        * inputs.operating_days_year
        * inputs.net_contribution_per_incremental_patient
    )
    candidate.annual_net_cash_flow = (
        candidate.annual_incremental_revenue - candidate.annual_opex
    )

    rate = inputs.discount_rate_pct / 100.0
    candidate.payback_years = (
        candidate.capex / candidate.annual_net_cash_flow
        if candidate.annual_net_cash_flow > 0
        else math.inf
    )
    candidate.roi_pct = (
        (
            candidate.annual_net_cash_flow * inputs.analysis_years
            - candidate.capex
        )
        / candidate.capex
        * 100.0
        if candidate.capex > 0
        else 0.0
    )
    candidate.npv = -candidate.capex + sum(
        candidate.annual_net_cash_flow / ((1.0 + rate) ** year)
        for year in range(1, inputs.analysis_years + 1)
    )
    return candidate


def optimize(inputs: ModelInputs) -> ModelResults:
    current_scanner_capacity = scanner_capacity(
        inputs.current_scanners,
        inputs.operating_hours_day,
        inputs.scanner_cycle_minutes,
        inputs.scanner_availability_pct,
    )
    current_injection_capacity = (
        inputs.current_injection_rooms
        * inputs.patients_per_injection_room_day
    )
    current_uptake_capacity = (
        inputs.current_uptake_rooms
        * inputs.patients_per_uptake_room_day
    )
    current_physical_capacity = min(
        current_scanner_capacity,
        current_injection_capacity,
        current_uptake_capacity,
        inputs.current_dose_capacity_day,
    )

    candidates: List[Candidate] = []
    conventional_evaluated = 0
    hybrid_evaluated = 0

    upgrade_values = range(
        0,
        inputs.max_production_upgrade_pct + 1,
        5,
    )

    # --------------------------------------------------------
    # OPTION 1: CONVENTIONAL EXPANSION
    # --------------------------------------------------------
    for upgrade_pct in upgrade_values:
        production_capacity = (
            inputs.current_dose_capacity_day
            * (1.0 + upgrade_pct / 100.0)
        )

        for add_scanners in range(inputs.max_additional_scanners + 1):
            scanners = inputs.current_scanners + add_scanners
            scan_capacity = scanner_capacity(
                scanners,
                inputs.operating_hours_day,
                inputs.scanner_cycle_minutes,
                inputs.scanner_availability_pct,
            )

            for add_injection in range(
                inputs.max_additional_injection_rooms + 1
            ):
                injection_capacity = (
                    inputs.current_injection_rooms + add_injection
                ) * inputs.patients_per_injection_room_day

                for add_uptake in range(
                    inputs.max_additional_uptake_rooms + 1
                ):
                    conventional_evaluated += 1

                    uptake_capacity = (
                        inputs.current_uptake_rooms + add_uptake
                    ) * inputs.patients_per_uptake_room_day

                    installed_capacity = min(
                        scan_capacity,
                        injection_capacity,
                        uptake_capacity,
                        production_capacity,
                    )

                    if installed_capacity < inputs.target_patients_day:
                        continue

                    capex = (
                        add_scanners * inputs.scanner_capex
                        + add_injection * inputs.injection_room_capex
                        + add_uptake * inputs.uptake_room_capex
                        + upgrade_pct
                        / 10.0
                        * inputs.conventional_upgrade_capex_per_10pct
                    )

                    if capex > inputs.maximum_capex_budget:
                        continue

                    annual_opex = (
                        inputs.annual_base_opex_conventional
                        + add_scanners * inputs.annual_opex_per_scanner
                        + add_injection
                        * inputs.annual_opex_per_injection_room
                        + add_uptake
                        * inputs.annual_opex_per_uptake_room
                    )

                    candidate = Candidate(
                        architecture="Conventional Expansion",
                        installed_capacity_day=installed_capacity,
                        patients_served_day=0.0,
                        reserve_capacity_day=0.0,
                        incremental_patients_day=0.0,
                        capex=capex,
                        annual_opex=annual_opex,
                        annual_incremental_revenue=0.0,
                        annual_net_cash_flow=0.0,
                        production_upgrade_pct=upgrade_pct,
                        additional_scanners=add_scanners,
                        additional_injection_rooms=add_injection,
                        additional_uptake_rooms=add_uptake,
                        mrt_enabled_inpatient_rooms=0,
                        mrt_endpoints=0,
                        dedicated_rooms_avoided=0,
                    )
                    candidates.append(financialize(candidate, inputs))

    # --------------------------------------------------------
    # OPTION 2: MRT PHARMA HYBRID
    # Existing dedicated rooms remain available.
    # MRT-enabled inpatient rooms add one distributed
    # administration-and-uptake place each.
    # --------------------------------------------------------
    for upgrade_pct in upgrade_values:
        production_capacity = (
            inputs.current_dose_capacity_day
            * (1.0 + upgrade_pct / 100.0)
        )

        for add_scanners in range(inputs.max_additional_scanners + 1):
            scanners = inputs.current_scanners + add_scanners
            scan_capacity = scanner_capacity(
                scanners,
                inputs.operating_hours_day,
                inputs.scanner_cycle_minutes,
                inputs.scanner_availability_pct,
            )

            for enabled_rooms in range(
                inputs.max_mrt_enabled_inpatient_rooms + 1
            ):
                hybrid_evaluated += 1

                distributed_capacity = (
                    enabled_rooms
                    * inputs.patients_per_enabled_inpatient_room_day
                )
                injection_capacity = (
                    current_injection_capacity + distributed_capacity
                )
                uptake_capacity = (
                    current_uptake_capacity + distributed_capacity
                )

                installed_capacity = min(
                    scan_capacity,
                    injection_capacity,
                    uptake_capacity,
                    production_capacity,
                )

                if installed_capacity < inputs.target_patients_day:
                    continue

                # Current dedicated injection rooms, current uptake rooms,
                # all scanners, enabled inpatient rooms, and user-specified
                # supporting destinations such as radiopharmacy and waste.
                mrt_endpoints = (
                    inputs.current_injection_rooms
                    + inputs.current_uptake_rooms
                    + scanners
                    + enabled_rooms
                    + inputs.other_mrt_destinations
                )

                capex = (
                    add_scanners * inputs.scanner_capex
                    + upgrade_pct
                    / 10.0
                    * inputs.hybrid_upgrade_capex_per_10pct
                    + inputs.mrt_core_capex
                    + mrt_endpoints * inputs.mrt_endpoint_capex
                )

                if capex > inputs.maximum_capex_budget:
                    continue

                annual_opex = (
                    inputs.annual_base_opex_hybrid
                    + inputs.annual_mrt_maintenance
                    + add_scanners * inputs.annual_opex_per_scanner
                    + mrt_endpoints
                    * inputs.annual_opex_per_mrt_endpoint
                )

                # Estimate how many dedicated rooms conventional expansion
                # would need to provide the same distributed room capacity.
                avoided_injection = math.ceil(
                    distributed_capacity
                    / inputs.patients_per_injection_room_day
                )
                avoided_uptake = math.ceil(
                    distributed_capacity
                    / inputs.patients_per_uptake_room_day
                )

                candidate = Candidate(
                    architecture="MRT Pharma Hybrid",
                    installed_capacity_day=installed_capacity,
                    patients_served_day=0.0,
                    reserve_capacity_day=0.0,
                    incremental_patients_day=0.0,
                    capex=capex,
                    annual_opex=annual_opex,
                    annual_incremental_revenue=0.0,
                    annual_net_cash_flow=0.0,
                    production_upgrade_pct=upgrade_pct,
                    additional_scanners=add_scanners,
                    additional_injection_rooms=0,
                    additional_uptake_rooms=0,
                    mrt_enabled_inpatient_rooms=enabled_rooms,
                    mrt_endpoints=mrt_endpoints,
                    dedicated_rooms_avoided=(
                        avoided_injection + avoided_uptake
                    ),
                )
                candidates.append(financialize(candidate, inputs))

    positive_candidates = [
        candidate
        for candidate in candidates
        if (
            candidate.annual_net_cash_flow > 0
            and candidate.npv > 0
            and math.isfinite(candidate.payback_years)
        )
    ]

    conventional_rows = [
        c
        for c in positive_candidates
        if c.architecture == "Conventional Expansion"
    ]
    hybrid_rows = [
        c
        for c in positive_candidates
        if c.architecture == "MRT Pharma Hybrid"
    ]

    best_conventional = (
        max(conventional_rows, key=lambda c: (c.npv, -c.capex))
        if conventional_rows
        else None
    )
    best_hybrid = (
        max(hybrid_rows, key=lambda c: (c.npv, -c.capex))
        if hybrid_rows
        else None
    )
    decision = (
        max(positive_candidates, key=lambda c: (c.npv, -c.capex))
        if positive_candidates
        else None
    )
    ranked = sorted(
        positive_candidates,
        key=lambda c: (-c.npv, c.capex),
    )[:100]

    return ModelResults(
        current_physical_capacity_day=current_physical_capacity,
        conventional_candidates_evaluated=conventional_evaluated,
        hybrid_candidates_evaluated=hybrid_evaluated,
        feasible_candidates=len(candidates),
        positive_npv_candidates=len(positive_candidates),
        best_conventional=best_conventional,
        best_hybrid=best_hybrid,
        decision=decision,
        ranked_candidates=ranked,
    )


def candidate_to_dict(candidate: Candidate) -> Dict[str, float]:
    return asdict(candidate)

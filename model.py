from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Inputs:
    current_scanners: int = 2
    target_patients: int = 200
    operating_hours: float = 18.0
    scan_minutes: float = 20.0
    turnover_minutes: float = 15.0
    scanner_availability_pct: float = 85.0
    max_additional_scanners: int = 10

    current_injection_rooms: int = 6
    patients_per_injection_room: float = 30.0
    current_uptake_rooms: int = 6
    patients_per_uptake_room: float = 15.0
    max_additional_injection_rooms: int = 12
    max_additional_uptake_rooms: int = 30
    manual_deliveries_day: float = 250.0

    total_oncology_rooms: int = 500
    shared_injection_uptake_rooms: int = 0
    available_inpatient_rooms: int = 170
    max_enabled_inpatient_rooms: int = 170
    patients_per_enabled_room: float = 1.0
    max_mrt_delivery_points: int = 50
    mrt_deliveries_per_point_day: float = 12.0

    eob_gbq_batch: float = 30.0
    current_batches: int = 2
    synthesis_yield_pct: float = 75.0
    qc_yield_pct: float = 95.0
    eob_release_min: float = 45.0
    patient_dose_mbq: float = 300.0
    manual_transport_min: float = 10.0
    mrt_distance_m: float = 750.0
    mrt_load_dock_sec: float = 50.0
    max_additional_batches: int = 2
    max_upgrade_pct: int = 40
    half_life_min: float = 109.8
    centralized_efficiency_pct: float = 90.0
    uplift_per_point_pct: float = 0.5
    max_uplift_pct: float = 10.0

    new_cyclotron_capex: float = 15_000_000.0
    new_cyclotron_added_gbq_day: float = 45.0
    scanner_capex: float = 250_000.0
    injection_room_capex: float = 25_000.0
    uptake_room_capex: float = 20_000.0
    mrt_point_capex: float = 25_000.0
    room_enablement_capex: float = 0.0
    conventional_upgrade_capex_per_10pct: float = 1_500_000.0
    hybrid_upgrade_capex_per_10pct: float = 600_000.0
    mrt_core_capex: float = 6_000_000.0

    contribution_per_incremental_patient: float = 300.0
    base_opex_new: float = 2_000_000.0
    base_opex_conventional: float = 2_000_000.0
    base_opex_hybrid: float = 200_000.0
    annual_mrt_maintenance: float = 500_000.0
    opex_per_added_batch: float = 8_000.0
    annual_opex_per_scanner: float = 100_000.0
    annual_opex_per_injection_room: float = 90_000.0
    annual_opex_per_uptake_room: float = 70_000.0
    annual_opex_per_mrt_point: float = 10_000.0
    annual_opex_per_enabled_room: float = 0.0
    operating_days: int = 300
    analysis_years: int = 10
    discount_rate_pct: float = 10.0
    maximum_budget: float = 100_000_000.0


@dataclass
class Candidate:
    architecture: str
    installed_capacity: float
    patients_served: float
    reserve_capacity: float
    incremental_patients_day: float
    capex: float
    annual_opex: float
    annual_revenue: float
    annual_net_cash_flow: float
    upgrade_pct: int
    added_batches: int
    added_scanners: int
    added_injection_rooms: int
    added_uptake_rooms: int
    centralized_intake_points: int
    mrt_delivery_points: int
    enabled_inpatient_rooms: int
    fdg_survival_pct: float
    payback_years: float = math.inf
    roi_pct: float = 0.0
    npv: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ModelResult:
    current_throughput: float
    candidates_evaluated: int
    feasible_candidates: List[Candidate]
    best_by_architecture: Dict[str, Optional[Candidate]]
    decision: Optional[Candidate]
    assumptions: Dict[str, float | str]


def npv(capex: float, annual_net: float, years: int, rate: float) -> float:
    return -capex + sum(annual_net / ((1 + rate) ** year) for year in range(1, years + 1))


def roi(capex: float, annual_net: float, years: int) -> float:
    return (((annual_net * years) - capex) / capex * 100.0) if capex > 0 else 0.0


def payback(capex: float, annual_net: float) -> float:
    return capex / annual_net if annual_net > 0 else math.inf


def discounted_cash_flow(candidate: Candidate, years: int, rate: float) -> List[float]:
    values = [-candidate.capex]
    total = -candidate.capex
    for year in range(1, years + 1):
        total += candidate.annual_net_cash_flow / ((1 + rate) ** year)
        values.append(total)
    return values


def _centralized_points(scanner_count: int) -> int:
    return max(1, math.ceil(scanner_count / 2))


def run_model(x: Inputs) -> ModelResult:
    if x.scan_minutes + x.turnover_minutes <= 0:
        raise ValueError("Scanner cycle time must be greater than zero.")
    if x.patient_dose_mbq <= 0 or x.half_life_min <= 0:
        raise ValueError("Patient dose and isotope half-life must be greater than zero.")

    patients_per_scanner = (
        x.operating_hours * 60.0 / (x.scan_minutes + x.turnover_minutes)
    ) * (x.scanner_availability_pct / 100.0)

    decay_to_release = 2 ** (-x.eob_release_min / x.half_life_min)
    released_gbq_per_batch = (
        x.eob_gbq_batch
        * x.synthesis_yield_pct / 100.0
        * x.qc_yield_pct / 100.0
        * decay_to_release
    )
    current_release_day = released_gbq_per_batch * x.current_batches
    manual_survival = 2 ** (-x.manual_transport_min / x.half_life_min)
    mrt_transport_min = ((x.mrt_distance_m / 50.0) + x.mrt_load_dock_sec) / 60.0
    mrt_survival = 2 ** (-mrt_transport_min / x.half_life_min)

    current_throughput = min(
        x.current_scanners * patients_per_scanner,
        x.current_injection_rooms * x.patients_per_injection_room,
        x.current_uptake_rooms * x.patients_per_uptake_room,
        x.manual_deliveries_day,
        current_release_day * 1000.0 * manual_survival / x.patient_dose_mbq,
    )

    valid_shared = min(
        x.shared_injection_uptake_rooms,
        x.current_injection_rooms,
        x.current_uptake_rooms,
    )
    unique_centralized_rooms = x.current_injection_rooms + x.current_uptake_rooms - valid_shared
    remaining_room_inventory = max(0, x.total_oncology_rooms - unique_centralized_rooms)
    max_enabled = min(
        x.available_inpatient_rooms,
        x.max_enabled_inpatient_rooms,
        remaining_room_inventory,
        max(0, x.max_mrt_delivery_points - x.current_injection_rooms),
    )

    rate = x.discount_rate_pct / 100.0
    evaluated = 0
    feasible: List[Candidate] = []

    def add_candidate(
        architecture: str,
        installed_capacity: float,
        capex: float,
        annual_opex: float,
        upgrade_pct: int,
        added_batches: int,
        added_scanners: int,
        added_injection_rooms: int,
        added_uptake_rooms: int,
        centralized_intake_points: int,
        mrt_delivery_points: int,
        enabled_inpatient_rooms: int,
        fdg_survival_pct: float,
    ) -> None:
        patients_served = min(installed_capacity, float(x.target_patients))
        incremental = max(0.0, patients_served - current_throughput)
        annual_revenue = incremental * x.operating_days * x.contribution_per_incremental_patient
        annual_net = annual_revenue - annual_opex
        c = Candidate(
            architecture=architecture,
            installed_capacity=installed_capacity,
            patients_served=patients_served,
            reserve_capacity=max(0.0, installed_capacity - x.target_patients),
            incremental_patients_day=incremental,
            capex=capex,
            annual_opex=annual_opex,
            annual_revenue=annual_revenue,
            annual_net_cash_flow=annual_net,
            upgrade_pct=upgrade_pct,
            added_batches=added_batches,
            added_scanners=added_scanners,
            added_injection_rooms=added_injection_rooms,
            added_uptake_rooms=added_uptake_rooms,
            centralized_intake_points=centralized_intake_points,
            mrt_delivery_points=mrt_delivery_points,
            enabled_inpatient_rooms=enabled_inpatient_rooms,
            fdg_survival_pct=fdg_survival_pct,
        )
        c.payback_years = payback(c.capex, c.annual_net_cash_flow)
        c.roi_pct = roi(c.capex, c.annual_net_cash_flow, x.analysis_years)
        c.npv = npv(c.capex, c.annual_net_cash_flow, x.analysis_years, rate)
        if c.annual_net_cash_flow > 0 and c.npv > 0 and math.isfinite(c.payback_years):
            feasible.append(c)

    # New cyclotron
    for s in range(x.max_additional_scanners + 1):
        for inj in range(x.max_additional_injection_rooms + 1):
            for upt in range(x.max_additional_uptake_rooms + 1):
                evaluated += 1
                scanners = x.current_scanners + s
                capacity = min(
                    scanners * patients_per_scanner,
                    (x.current_injection_rooms + inj) * x.patients_per_injection_room,
                    (x.current_uptake_rooms + upt) * x.patients_per_uptake_room,
                    x.manual_deliveries_day,
                    (current_release_day + x.new_cyclotron_added_gbq_day) * 1000.0 * manual_survival / x.patient_dose_mbq,
                )
                if capacity < x.target_patients:
                    continue
                capex = x.new_cyclotron_capex + s*x.scanner_capex + inj*x.injection_room_capex + upt*x.uptake_room_capex
                if capex > x.maximum_budget:
                    continue
                annual_opex = x.base_opex_new + s*x.annual_opex_per_scanner + inj*x.annual_opex_per_injection_room + upt*x.annual_opex_per_uptake_room
                add_candidate("New Cyclotron", capacity, capex, annual_opex, 0, 0, s, inj, upt, _centralized_points(scanners), 0, 0, manual_survival*100.0)

    # Conventional upgrade
    for up in range(0, x.max_upgrade_pct + 1, 5):
        for batches in range(x.max_additional_batches + 1):
            fdg_capacity = (
                current_release_day * (1 + up/100.0) + batches*released_gbq_per_batch
            ) * 1000.0 * manual_survival / x.patient_dose_mbq
            for s in range(x.max_additional_scanners + 1):
                for inj in range(x.max_additional_injection_rooms + 1):
                    for upt in range(x.max_additional_uptake_rooms + 1):
                        evaluated += 1
                        scanners = x.current_scanners + s
                        capacity = min(
                            scanners * patients_per_scanner,
                            (x.current_injection_rooms + inj) * x.patients_per_injection_room,
                            (x.current_uptake_rooms + upt) * x.patients_per_uptake_room,
                            x.manual_deliveries_day,
                            fdg_capacity,
                        )
                        if capacity < x.target_patients:
                            continue
                        capex = (up/10.0)*x.conventional_upgrade_capex_per_10pct + s*x.scanner_capex + inj*x.injection_room_capex + upt*x.uptake_room_capex
                        if capex > x.maximum_budget:
                            continue
                        annual_opex = x.base_opex_conventional + batches*x.opex_per_added_batch*x.operating_days + s*x.annual_opex_per_scanner + inj*x.annual_opex_per_injection_room + upt*x.annual_opex_per_uptake_room
                        add_candidate("Conventional Upgrade", capacity, capex, annual_opex, up, batches, s, inj, upt, _centralized_points(scanners), 0, 0, manual_survival*100.0)

    # MRT Pharma hybrid
    for up in range(0, x.max_upgrade_pct + 1, 5):
        for batches in range(x.max_additional_batches + 1):
            fdg_capacity = (
                current_release_day * (1 + up/100.0) + batches*released_gbq_per_batch
            ) * 1000.0 * mrt_survival / x.patient_dose_mbq
            for enabled in range(max_enabled + 1):
                points = x.current_injection_rooms + enabled
                if points > x.max_mrt_delivery_points:
                    continue
                distributed_capacity = enabled * x.patients_per_enabled_room
                injection_capacity = x.current_injection_rooms*x.patients_per_injection_room + distributed_capacity
                uptake_capacity = x.current_uptake_rooms*x.patients_per_uptake_room + distributed_capacity
                transport_capacity = points * x.mrt_deliveries_per_point_day
                uplift = min(x.max_uplift_pct, x.uplift_per_point_pct*points)
                distribution_factor = min(1.0, x.centralized_efficiency_pct/100.0 + uplift/100.0)
                for s in range(x.max_additional_scanners + 1):
                    evaluated += 1
                    scanners = x.current_scanners + s
                    capacity = min(
                        scanners*patients_per_scanner*distribution_factor,
                        injection_capacity,
                        uptake_capacity,
                        transport_capacity,
                        fdg_capacity,
                    )
                    if capacity < x.target_patients:
                        continue
                    capex = (up/10.0)*x.hybrid_upgrade_capex_per_10pct + x.mrt_core_capex + points*x.mrt_point_capex + enabled*x.room_enablement_capex + s*x.scanner_capex
                    if capex > x.maximum_budget:
                        continue
                    annual_opex = x.base_opex_hybrid + x.annual_mrt_maintenance + batches*x.opex_per_added_batch*x.operating_days + s*x.annual_opex_per_scanner + points*x.annual_opex_per_mrt_point + enabled*x.annual_opex_per_enabled_room
                    add_candidate("MRT Pharma Hybrid", capacity, capex, annual_opex, up, batches, s, 0, 0, 0, points, enabled, mrt_survival*100.0)

    names = ["New Cyclotron", "Conventional Upgrade", "MRT Pharma Hybrid"]
    best: Dict[str, Optional[Candidate]] = {}
    for name in names:
        rows = [c for c in feasible if c.architecture == name]
        best[name] = max(rows, key=lambda c: (c.npv, -c.capex)) if rows else None
    decision = max(feasible, key=lambda c: (c.npv, -c.capex)) if feasible else None

    assumptions = {
        "Current modeled throughput/day": current_throughput,
        "Target patients/day": x.target_patients,
        "Manual FDG survival (%)": manual_survival*100.0,
        "MRT FDG survival (%)": mrt_survival*100.0,
        "Unique centralized physical rooms": unique_centralized_rooms,
        "Maximum usable MRT-enabled inpatient rooms": max_enabled,
        "Decision criterion": "Highest positive NPV",
    }
    return ModelResult(current_throughput, evaluated, feasible, best, decision, assumptions)

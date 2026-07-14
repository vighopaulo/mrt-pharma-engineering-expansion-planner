from __future__ import annotations
import math
from typing import Dict, List, Tuple

BASE_WEIGHTS: Dict[str, float] = {
    "NPV": 0.24,
    "CapEx": 0.16,
    "ROI": 0.11,
    "Payback": 0.08,
    "Annual OpEx": 0.07,
    "Annual net cash flow": 0.07,
    "Isotope preservation": 0.05,
    "Operational flexibility": 0.05,
    "Batch flexibility": 0.04,
    "Production upgrade burden": 0.04,
    "Dedicated-room burden": 0.03,
    "Logistics burden": 0.03,
    "Resilience": 0.03,
}

PRIORITY_OPTIONS = list(BASE_WEIGHTS.keys())
PRIORITY_RANK_WEIGHTS = (0.30, 0.20, 0.15)


def build_priority_weights(priority_1: str, priority_2: str, priority_3: str) -> Dict[str, float]:
    priorities = [priority_1, priority_2, priority_3]
    if len(set(priorities)) != 3:
        raise ValueError("The three hospital priorities must be different.")
    unknown = [p for p in priorities if p not in BASE_WEIGHTS]
    if unknown:
        raise ValueError(f"Unknown decision priority: {unknown[0]}")

    weights = {metric: 0.0 for metric in BASE_WEIGHTS}
    for metric, rank_weight in zip(priorities, PRIORITY_RANK_WEIGHTS):
        weights[metric] = rank_weight

    remainder = 1.0 - sum(PRIORITY_RANK_WEIGHTS)
    unselected = [metric for metric in BASE_WEIGHTS if metric not in priorities]
    baseline_total = sum(BASE_WEIGHTS[metric] for metric in unselected)
    for metric in unselected:
        weights[metric] = remainder * BASE_WEIGHTS[metric] / baseline_total

    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise ValueError("Generated decision weights do not sum to 1.0.")
    return weights


def _higher(a: float, b: float) -> Tuple[float, float]:
    if a <= 0 and b <= 0:
        return 0.0, 0.0
    maximum = max(a, b)
    return max(0.0, a) / maximum, max(0.0, b) / maximum


def _lower(a: float, b: float) -> Tuple[float, float]:
    if math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12):
        return 1.0, 1.0
    if a == 0 and b > 0:
        return 1.0, 0.0
    if b == 0 and a > 0:
        return 0.0, 1.0
    if not math.isfinite(a) and not math.isfinite(b):
        return 0.0, 0.0
    if not math.isfinite(a):
        return 0.0, 1.0
    if not math.isfinite(b):
        return 1.0, 0.0
    low = min(a, b)
    return low / a, low / b


def compute_scores(conventional, mrt, weights=None):
    weights = weights or BASE_WEIGHTS
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise ValueError("Weights must sum to 1.0.")

    if conventional.feasible and not mrt.feasible:
        return 100.0, 0.0, [{"Metric": "Feasibility gate", "Weight": 1.0, "Conventional Points": 100.0, "MRT Points": 0.0}]
    if mrt.feasible and not conventional.feasible:
        return 0.0, 100.0, [{"Metric": "Feasibility gate", "Weight": 1.0, "Conventional Points": 0.0, "MRT Points": 100.0}]
    if not conventional.feasible and not mrt.feasible:
        return 0.0, 0.0, [{"Metric": "Feasibility gate", "Weight": 1.0, "Conventional Points": 0.0, "MRT Points": 0.0}]

    conv_flex = min(1.0, 0.45 * conventional.feasible_batch_count / max(1, conventional.feasible_batch_count, mrt.feasible_batch_count) + 0.55 * conventional.reserve_capacity_day / max(1.0, conventional.patients_served_day))
    mrt_flex = min(1.0, 0.45 * mrt.feasible_batch_count / max(1, conventional.feasible_batch_count, mrt.feasible_batch_count) + 0.55 * mrt.reserve_capacity_day / max(1.0, mrt.patients_served_day))

    conventional_resilience = min(1.0, 0.5 + conventional.reserve_capacity_day / max(1.0, conventional.patients_served_day))
    mrt_resilience = min(1.0, 0.5 + mrt.reserve_capacity_day / max(1.0, mrt.patients_served_day))

    values = {
        "NPV": (conventional.npv, mrt.npv, "higher"),
        "CapEx": (conventional.capex, mrt.capex, "lower"),
        "ROI": (conventional.roi_pct, mrt.roi_pct, "higher"),
        "Payback": (conventional.payback_years, mrt.payback_years, "lower"),
        "Annual OpEx": (conventional.annual_opex, mrt.annual_opex, "lower"),
        "Annual net cash flow": (conventional.annual_net_cash_flow, mrt.annual_net_cash_flow, "higher"),
        "Isotope preservation": (conventional.retained_activity_pct, mrt.retained_activity_pct, "higher"),
        "Operational flexibility": (conv_flex, mrt_flex, "higher"),
        "Batch flexibility": (conventional.feasible_batch_count, mrt.feasible_batch_count, "higher"),
        "Production upgrade burden": (conventional.production_increase_pct, mrt.production_increase_pct, "lower"),
        "Dedicated-room burden": (
            conventional.additional_injection_rooms + conventional.additional_uptake_rooms,
            mrt.additional_injection_rooms + mrt.additional_uptake_rooms,
            "lower",
        ),
        "Logistics burden": (conventional.annual_logistics_hours, mrt.annual_logistics_hours, "lower"),
        "Resilience": (conventional_resilience, mrt_resilience, "higher"),
    }

    conventional_total = 0.0
    mrt_total = 0.0
    rows: List[dict] = []
    for metric, weight in weights.items():
        conventional_raw, mrt_raw, direction = values[metric]
        conventional_norm, mrt_norm = _higher(conventional_raw, mrt_raw) if direction == "higher" else _lower(conventional_raw, mrt_raw)
        conventional_points = 100.0 * weight * conventional_norm
        mrt_points = 100.0 * weight * mrt_norm
        conventional_total += conventional_points
        mrt_total += mrt_points
        rows.append({
            "Metric": metric,
            "Weight": weight,
            "Direction": "Higher is better" if direction == "higher" else "Lower is better",
            "Conventional Raw": conventional_raw,
            "MRT Raw": mrt_raw,
            "Conventional Normalized": conventional_norm,
            "MRT Normalized": mrt_norm,
            "Conventional Points": conventional_points,
            "MRT Points": mrt_points,
        })
    return conventional_total, mrt_total, rows


def recommendation_strength(a: float, b: float) -> str:
    difference = abs(a - b)
    if difference < 3:
        return "Essentially tied"
    if difference < 8:
        return "Moderate preference"
    return "Strong preference"

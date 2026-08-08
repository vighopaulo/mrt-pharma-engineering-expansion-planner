from __future__ import annotations

from models import PlannerAssumptions


MRT_DEFAULT_DELIVERY_SECONDS = 30.0


ASSUMPTION_FIELDS = [
    "mrt_infrastructure_capex",
    "cyclotron_purchase_capex",
    "cyclotron_installation_capex",
    "additional_room_capex",
    "production_expansion_capex_per_10pct",
    "revenue_per_scan",
    "discount_rate_pct",
    "analysis_years",
    "operating_days_per_year",
    "scanner_availability_pct",
    "scanner_cycle_min",
    "injection_cycle_min",
    "uptake_cycle_min",
]


def seconds_to_minutes(seconds: float) -> float:
    return seconds / 60.0


def default_assumption_values() -> dict[str, float]:
    defaults = PlannerAssumptions()
    return {
        "mrt_infrastructure_capex": defaults.mrt_infrastructure_capex,
        "cyclotron_purchase_capex": defaults.cyclotron_purchase_capex,
        "cyclotron_installation_capex": defaults.cyclotron_installation_capex,
        "additional_room_capex": defaults.additional_room_capex,
        "production_expansion_capex_per_10pct": defaults.production_expansion_capex_per_10pct,
        "revenue_per_scan": defaults.revenue_per_scan,
        "discount_rate_pct": defaults.discount_rate_pct,
        "analysis_years": float(defaults.analysis_years),
        "operating_days_per_year": float(defaults.operating_days_per_year),
        "scanner_availability_pct": defaults.scanner_availability_pct,
        "scanner_cycle_min": defaults.scanner_cycle_min,
        "injection_cycle_min": defaults.injection_cycle_min,
        "uptake_cycle_min": defaults.uptake_cycle_min,
    }


def assumptions_from_values(values: dict[str, float]) -> PlannerAssumptions:
    return PlannerAssumptions(
        mrt_infrastructure_capex=values["mrt_infrastructure_capex"],
        cyclotron_purchase_capex=values["cyclotron_purchase_capex"],
        cyclotron_installation_capex=values["cyclotron_installation_capex"],
        additional_room_capex=values["additional_room_capex"],
        production_expansion_capex_per_10pct=values["production_expansion_capex_per_10pct"],
        revenue_per_scan=values["revenue_per_scan"],
        discount_rate_pct=values["discount_rate_pct"],
        analysis_years=int(values["analysis_years"]),
        operating_days_per_year=int(values["operating_days_per_year"]),
        scanner_availability_pct=values["scanner_availability_pct"],
        scanner_cycle_min=values["scanner_cycle_min"],
        injection_cycle_min=values["injection_cycle_min"],
        uptake_cycle_min=values["uptake_cycle_min"],
        mrt_transport_default_min=seconds_to_minutes(MRT_DEFAULT_DELIVERY_SECONDS),
    )


def changed_assumption_labels(values: dict[str, float]) -> list[str]:
    defaults = default_assumption_values()
    labels = {
        "mrt_infrastructure_capex": "MRT infrastructure cost",
        "cyclotron_purchase_capex": "Cyclotron purchase cost",
        "cyclotron_installation_capex": "Cyclotron installation cost",
        "additional_room_capex": "Additional room cost",
        "production_expansion_capex_per_10pct": "Conventional production expansion cost",
        "revenue_per_scan": "Revenue per scan",
        "discount_rate_pct": "Discount rate",
        "analysis_years": "Analysis period",
        "operating_days_per_year": "Operating days per year",
        "scanner_availability_pct": "Scanner availability",
        "scanner_cycle_min": "Scanner cycle time",
        "injection_cycle_min": "Injection-room cycle time",
        "uptake_cycle_min": "Uptake-room cycle time",
    }
    changed: list[str] = []
    for key in ASSUMPTION_FIELDS:
        if abs(float(values[key]) - float(defaults[key])) > 1e-9:
            changed.append(labels[key])
    return changed


def validate_assumptions(values: dict[str, float]) -> list[str]:
    issues: list[str] = []
    labels = {
        "mrt_infrastructure_capex": "MRT infrastructure cost",
        "cyclotron_purchase_capex": "Cyclotron purchase cost",
        "cyclotron_installation_capex": "Cyclotron installation cost",
        "additional_room_capex": "Additional room cost",
        "production_expansion_capex_per_10pct": "Conventional production expansion cost",
        "revenue_per_scan": "Revenue per scan",
        "scanner_cycle_min": "Scanner cycle time",
        "injection_cycle_min": "Injection-room cycle time",
        "uptake_cycle_min": "Uptake-room cycle time",
    }
    non_negative = [
        "mrt_infrastructure_capex",
        "cyclotron_purchase_capex",
        "cyclotron_installation_capex",
        "additional_room_capex",
        "production_expansion_capex_per_10pct",
        "revenue_per_scan",
    ]
    for key in non_negative:
        if values[key] < 0:
            issues.append(f"{labels[key]} cannot be negative.")

    if values["discount_rate_pct"] < 0 or values["discount_rate_pct"] > 100:
        issues.append("Discount rate must be between 0% and 100%.")
    if values["analysis_years"] <= 0:
        issues.append("Analysis period must be at least 1 year.")
    if values["operating_days_per_year"] <= 0 or values["operating_days_per_year"] > 366:
        issues.append("Operating days per year must be between 1 and 366.")
    if values["scanner_availability_pct"] <= 0 or values["scanner_availability_pct"] > 100:
        issues.append("Scanner availability must be greater than 0% and at most 100%.")

    positive_cycles = ["scanner_cycle_min", "injection_cycle_min", "uptake_cycle_min"]
    for key in positive_cycles:
        if values[key] <= 0:
            issues.append(f"{labels[key]} must be greater than zero.")

    return issues

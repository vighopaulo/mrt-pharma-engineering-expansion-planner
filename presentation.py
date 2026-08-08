from __future__ import annotations


def format_currency(value: float) -> str:
    return f"${value:,.0f}"


def format_percent(value: float, decimals: int = 1) -> str:
    rounded = round(value, decimals)
    if rounded.is_integer():
        return f"{int(rounded)}%"
    return f"{rounded:.{decimals}f}%"


def format_patients_per_day(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,} patients/day"
    return f"{value:,.1f} patients/day"


def format_count(value: int | float, label: str) -> str:
    amount = int(value)
    if amount == 1:
        singular = label[:-1] if label.endswith("s") else label
        return f"{amount} {singular}"
    return f"{amount} {label}"


def format_minutes(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value)} minutes"
    return f"{value:.1f} minutes"


def format_seconds(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value)} seconds"
    return f"{value:.1f} seconds"


def format_years(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value)} years"
    return f"{value:.1f} years"


def format_hours_per_day(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value)} hours/day"
    return f"{value:.1f} hours/day"


def cumulative_roi_label(analysis_years: int) -> str:
    return f"{analysis_years}-Year Cumulative ROI"

from __future__ import annotations

import json
from pathlib import Path

from models import PlannerInputs


def load_radionuclide_half_lives() -> dict[str, float]:
    path = Path(__file__).with_name("radionuclides.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {name: float(values["half_life_min"]) for name, values in payload.items()}


def resolve_half_life_min(inputs: PlannerInputs, half_life_lookup: dict[str, float]) -> float:
    if inputs.representative_half_life_min is not None and inputs.representative_half_life_min > 0:
        return float(inputs.representative_half_life_min)
    if inputs.representative_radionuclide:
        name = inputs.representative_radionuclide.strip()
        if name in half_life_lookup:
            return half_life_lookup[name]
    raise ValueError("Provide either a valid representative radionuclide or a positive half-life.")


def validate(inputs: PlannerInputs, half_life_lookup: dict[str, float]) -> list[str]:
    issues: list[str] = []
    if not inputs.project_name.strip():
        issues.append("Project name is required.")
    if inputs.current_patients_per_day <= 0:
        issues.append("Current patients/day must be positive.")
    if inputs.target_patients_per_day <= 0:
        issues.append("Target patients/day must be positive.")
    if inputs.target_patients_per_day < inputs.current_patients_per_day:
        issues.append("Target patients/day must be greater than or equal to current patients/day.")
    if inputs.maximum_expected_demand_per_day <= 0:
        issues.append("Maximum expected demand/day must be positive.")
    if inputs.current_scanners < 0 or inputs.current_injection_rooms < 0 or inputs.current_uptake_rooms < 0:
        issues.append("Current scanner and room counts cannot be negative.")
    if inputs.current_usable_doses_per_day <= 0:
        issues.append("Current usable doses/day must be positive.")
    if inputs.current_average_transport_min < 0:
        issues.append("Current average transport time cannot be negative.")
    if inputs.conventional_transport_min is not None and inputs.conventional_transport_min < 0:
        issues.append("Conventional transport time cannot be negative.")
    if inputs.mrt_transport_min is not None and inputs.mrt_transport_min < 0:
        issues.append("MRT transport time cannot be negative.")
    if inputs.existing_mrt_connectable_rooms < 0:
        issues.append("Existing MRT-connectable rooms cannot be negative.")
    if inputs.current_cyclotron_eob_capacity_mbq_per_day is not None and inputs.current_cyclotron_eob_capacity_mbq_per_day <= 0:
        issues.append("Cyclotron EOB activity capacity must be positive when provided.")

    try:
        resolve_half_life_min(inputs, half_life_lookup)
    except ValueError as exc:
        issues.append(str(exc))

    return issues

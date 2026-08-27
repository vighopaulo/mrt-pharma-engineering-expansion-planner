"""Nuclear Source Abstraction Boundary (CYCLOTRON | GENERATOR).

Section 2-3 closure: this is ONLY an integration boundary, never a
replacement physics model. Existing cyclotron objects
(`cyclotron_catalog.py`/`cyclotron_production_windows.py`) remain
authoritative for cyclotron physics; `generator.py`/`generator_catalog.py`
remain authoritative for generator physics. `NuclearSourceInstance` lets a
single evaluator (see `oncology_pet_spect_scenario.evaluate_native_mixed_candidate`)
consume EITHER source type through one interface without pretending the two
production mechanisms are physically identical (section 4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from cyclotron_production_windows import CyclotronAsset
from generator_catalog import FacilityGeneratorInstance, GeneratorCatalogModel, resolve_effective_elution_efficiency, resolve_effective_reference_activity_mbq
from generator import GeneratorAsset

NuclearSourceType = Literal["CYCLOTRON", "GENERATOR"]


@dataclass(frozen=True)
class NuclearSourceInstance:
    """The integration-boundary wrapper. Exactly one of `cyclotron_asset` /
    (`generator_instance`, `generator_model`) is populated, matching
    `source_type` -- never both, never neither (section 3)."""

    source_id: str
    source_type: NuclearSourceType
    radionuclide: str
    cyclotron_asset: CyclotronAsset | None = None
    generator_instance: FacilityGeneratorInstance | None = None
    generator_model: GeneratorCatalogModel | None = None
    generator_physics: GeneratorAsset | None = None
    """The live, stateful Bateman-physics object for GENERATOR sources
    (`generator.py`'s authoritative model) -- None for CYCLOTRON sources."""

    def __post_init__(self) -> None:
        if self.source_type == "CYCLOTRON":
            if self.cyclotron_asset is None:
                raise ValueError(f"{self.source_id}: CYCLOTRON source requires cyclotron_asset")
            if self.generator_instance is not None or self.generator_model is not None or self.generator_physics is not None:
                raise ValueError(f"{self.source_id}: CYCLOTRON source must not carry generator fields")
        elif self.source_type == "GENERATOR":
            if self.generator_instance is None or self.generator_model is None or self.generator_physics is None:
                raise ValueError(f"{self.source_id}: GENERATOR source requires generator_instance/generator_model/generator_physics")
            if self.cyclotron_asset is not None:
                raise ValueError(f"{self.source_id}: GENERATOR source must not carry a cyclotron_asset")
        else:
            raise ValueError(f"Unknown source_type: {self.source_type}")


def build_cyclotron_source(*, source_id: str, radionuclide: str, cyclotron_asset: CyclotronAsset) -> NuclearSourceInstance:
    """Section 4: reuses the EXISTING cyclotron authority unchanged -- no new
    cyclotron physics introduced here."""
    return NuclearSourceInstance(source_id=source_id, source_type="CYCLOTRON", radionuclide=radionuclide, cyclotron_asset=cyclotron_asset)


def build_generator_source(
    *, source_id: str, generator_instance: FacilityGeneratorInstance, generator_model: GeneratorCatalogModel,
    calibration_datetime: datetime,
) -> NuclearSourceInstance:
    """Section 4: reuses the EXISTING generator authority (`generator.py`)
    unchanged -- the Bateman parent-daughter physics object is constructed
    from the catalog-resolved reference activity/elution efficiency."""
    reference_activity = resolve_effective_reference_activity_mbq(generator_instance, generator_model)
    if reference_activity is None:
        raise ValueError(f"{source_id}: no reference activity available (catalog and site override both missing)")
    efficiency = resolve_effective_elution_efficiency(generator_instance, generator_model)
    physics = GeneratorAsset(
        generator_id=generator_instance.instance_id, calibration_datetime=calibration_datetime,
        calibration_mo99_activity_mbq=reference_activity,
        elution_efficiency=efficiency if efficiency is not None else 0.85,
    )
    return NuclearSourceInstance(
        source_id=source_id, source_type="GENERATOR", radionuclide=generator_model.daughter_radionuclide,
        generator_instance=generator_instance, generator_model=generator_model, generator_physics=physics,
    )


@dataclass(frozen=True)
class SourceFeasibilityResult:
    """Section 5, 49: requirement-derived feasibility -- never a fixed
    'doses/day' capacity for either source type."""

    source_id: str
    source_type: NuclearSourceType
    radionuclide: str
    required_activity_mbq: float
    available_activity_mbq: float
    utilization: float | None
    patients_served: int
    patients_requested: int
    unmet: int
    status: Literal["FEASIBLE", "INSUFFICIENT_ACTIVITY", "SOURCE_UNAVAILABLE"]


def evaluate_cyclotron_source_feasibility(
    *, source: NuclearSourceInstance, required_activity_mbq: float, available_eob_capacity_mbq_per_day: float,
    patients_requested: int,
) -> SourceFeasibilityResult:
    if source.source_type != "CYCLOTRON":
        raise ValueError("evaluate_cyclotron_source_feasibility requires a CYCLOTRON source")
    utilization = required_activity_mbq / available_eob_capacity_mbq_per_day if available_eob_capacity_mbq_per_day > 0 else None
    feasible = available_eob_capacity_mbq_per_day >= required_activity_mbq
    served = patients_requested if feasible else (
        int(patients_requested * (available_eob_capacity_mbq_per_day / required_activity_mbq)) if required_activity_mbq > 0 else 0
    )
    return SourceFeasibilityResult(
        source_id=source.source_id, source_type="CYCLOTRON", radionuclide=source.radionuclide,
        required_activity_mbq=required_activity_mbq, available_activity_mbq=available_eob_capacity_mbq_per_day,
        utilization=utilization, patients_served=served, patients_requested=patients_requested,
        unmet=patients_requested - served,
        status="FEASIBLE" if feasible else "INSUFFICIENT_ACTIVITY",
    )


def evaluate_generator_source_feasibility(
    *, source: NuclearSourceInstance, required_eluted_activity_mbq: float, elution_datetime: datetime,
    patients_requested: int,
) -> SourceFeasibilityResult:
    """Section 5, 34: patient-derived generator sizing -- available activity
    is the ACTUAL physically available daughter activity at the requested
    elution time (Bateman physics), never a fixed dose count."""
    if source.source_type != "GENERATOR" or source.generator_physics is None:
        raise ValueError("evaluate_generator_source_feasibility requires a GENERATOR source")
    available_before_elution = source.generator_physics.available_tc99m_activity_mbq(at_datetime=elution_datetime)
    efficiency = source.generator_physics.elution_efficiency
    available_eluted = available_before_elution * efficiency
    utilization = required_eluted_activity_mbq / available_eluted if available_eluted > 0 else None
    feasible = available_eluted >= required_eluted_activity_mbq
    served = patients_requested if feasible else (
        int(patients_requested * (available_eluted / required_eluted_activity_mbq)) if required_eluted_activity_mbq > 0 else 0
    )
    return SourceFeasibilityResult(
        source_id=source.source_id, source_type="GENERATOR", radionuclide=source.radionuclide,
        required_activity_mbq=required_eluted_activity_mbq, available_activity_mbq=available_eluted,
        utilization=utilization, patients_served=served, patients_requested=patients_requested,
        unmet=patients_requested - served,
        status="FEASIBLE" if feasible else "INSUFFICIENT_ACTIVITY",
    )

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from cyclotron_production_windows import CyclotronProductionCapability


@dataclass(frozen=True)
class PettraceProductionRecord:
    cyclotron_series: str
    radionuclide: str
    target_system: str
    process_system: str | None
    irradiation_time_minutes: float | None
    source_reference: str
    yield_basis: str
    notes: str


# Manufacturer-grounded reference records derived from the uploaded GE HealthCare
# PETtrace 800 reference set named by the user. Numeric yield values are not
# fabricated when not explicitly available in the provided sheets.
PETTRACE_800_REFERENCE_RECORDS: tuple[PettraceProductionRecord, ...] = (
    PettraceProductionRecord(
        cyclotron_series="GE HealthCare PETtrace 800",
        radionuclide="F-18",
        target_system="F-18 target systems",
        process_system=None,
        irradiation_time_minutes=None,
        source_reference="Uploaded GE HealthCare PETtrace 800 manufacturer sheets",
        yield_basis="not provided as normalized numeric yield in repository",
        notes="Irradiation-specific yield should be populated only from explicit manufacturer table values.",
    ),
    PettraceProductionRecord(
        cyclotron_series="GE HealthCare PETtrace 800",
        radionuclide="Ga-68",
        target_system="Ga-68 liquid target system",
        process_system=None,
        irradiation_time_minutes=None,
        source_reference="Uploaded GE HealthCare PETtrace 800 manufacturer sheets",
        yield_basis="not provided as normalized numeric yield in repository",
        notes="Liquid target production details should remain source-constrained.",
    ),
    PettraceProductionRecord(
        cyclotron_series="GE HealthCare PETtrace 800",
        radionuclide="N-13",
        target_system="N-13 ammonia target system",
        process_system=None,
        irradiation_time_minutes=None,
        source_reference="Uploaded GE HealthCare PETtrace 800 manufacturer sheets",
        yield_basis="not provided as normalized numeric yield in repository",
        notes="No yield interpolation is introduced in this build.",
    ),
    PettraceProductionRecord(
        cyclotron_series="GE HealthCare PETtrace 800",
        radionuclide="C-11",
        target_system="C-11 target/process systems",
        process_system="C-11 process systems",
        irradiation_time_minutes=None,
        source_reference="Uploaded GE HealthCare PETtrace 800 manufacturer sheets",
        yield_basis="not provided as normalized numeric yield in repository",
        notes="Model/target/process variant must be explicitly configured from source sheets before quantitative use.",
    ),
    PettraceProductionRecord(
        cyclotron_series="GE HealthCare PETtrace 800",
        radionuclide="O-15",
        target_system="O-15 target/process system",
        process_system="O-15 process system",
        irradiation_time_minutes=None,
        source_reference="Uploaded GE HealthCare PETtrace 800 manufacturer sheets",
        yield_basis="not provided as normalized numeric yield in repository",
        notes="O-15 half-life is short; schedule-to-injection timing is especially sensitive.",
    ),
)


def pettrace_800_supported_radionuclides() -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for record in PETTRACE_800_REFERENCE_RECORDS:
        seen[record.radionuclide] = None
    return tuple(seen.keys())


def build_pettrace_800_capability(
    *,
    cyclotron_id: str,
    production_cycle_minutes_by_radionuclide: Mapping[str, float],
    max_simultaneous_production_streams: int = 1,
    release_processing_minutes_by_radionuclide: Mapping[str, float] | None = None,
) -> CyclotronProductionCapability:
    supported = pettrace_800_supported_radionuclides()
    return CyclotronProductionCapability(
        cyclotron_id=cyclotron_id,
        supported_radionuclides=supported,
        max_simultaneous_production_streams=max_simultaneous_production_streams,
        production_cycle_minutes_by_radionuclide=production_cycle_minutes_by_radionuclide,
        release_processing_minutes_by_radionuclide=release_processing_minutes_by_radionuclide,
    )
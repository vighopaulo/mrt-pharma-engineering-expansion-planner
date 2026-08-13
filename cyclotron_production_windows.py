from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping

from diagnostics import load_radionuclide_half_lives
from patient_radionuclide_demand import RadionuclideBatchDemand


@lru_cache(maxsize=1)
def _canonical_radionuclide_lookup() -> dict[str, float]:
    return load_radionuclide_half_lives()


def _normalize_radionuclide_name(radionuclide: str) -> str:
    if not isinstance(radionuclide, str):
        raise ValueError("radionuclide names must be strings")
    name = radionuclide.strip()
    if not name:
        raise ValueError("radionuclide names must be non-empty strings")
    if name not in _canonical_radionuclide_lookup():
        raise ValueError(f"Unknown radionuclide: {name}")
    return name


@dataclass(frozen=True)
class CyclotronProductionCapability:
    cyclotron_id: str
    supported_radionuclides: tuple[str, ...]
    max_simultaneous_production_streams: int
    production_cycle_minutes_by_radionuclide: Mapping[str, float]
    simultaneously_compatible_radionuclide_sets: tuple[frozenset[str], ...] = ()
    release_processing_minutes_by_radionuclide: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        cyclotron_id = self.cyclotron_id.strip() if isinstance(self.cyclotron_id, str) else ""
        if not cyclotron_id:
            raise ValueError("cyclotron_id must be a non-empty string")

        if self.max_simultaneous_production_streams < 1:
            raise ValueError("max_simultaneous_production_streams must be at least 1")

        if not self.supported_radionuclides:
            raise ValueError("supported_radionuclides must contain at least one radionuclide")

        normalized_supported = tuple(_normalize_radionuclide_name(name) for name in self.supported_radionuclides)
        if len(set(normalized_supported)) != len(normalized_supported):
            raise ValueError("supported_radionuclides must be unique")

        cycle_lookup: dict[str, float] = {}
        for radionuclide, cycle_minutes in self.production_cycle_minutes_by_radionuclide.items():
            normalized = _normalize_radionuclide_name(radionuclide)
            cycle_value = float(cycle_minutes)
            if cycle_value <= 0.0:
                raise ValueError("production cycle minutes must be greater than zero")
            cycle_lookup[normalized] = cycle_value

        for radionuclide in normalized_supported:
            if radionuclide not in cycle_lookup:
                raise ValueError(f"Missing production cycle minutes for radionuclide {radionuclide}")

        unknown_cycle_keys = set(cycle_lookup).difference(normalized_supported)
        if unknown_cycle_keys:
            raise ValueError(f"Unsupported radionuclides in production cycle mapping: {sorted(unknown_cycle_keys)}")

        normalized_compatibility: list[frozenset[str]] = []
        for compatibility_group in self.simultaneously_compatible_radionuclide_sets:
            normalized_group = frozenset(_normalize_radionuclide_name(item) for item in compatibility_group)
            if len(normalized_group) < 2:
                raise ValueError("Compatibility groups must contain at least two distinct radionuclides")
            if len(normalized_group) > self.max_simultaneous_production_streams:
                raise ValueError("Compatibility groups cannot exceed max simultaneous production streams")
            unsupported = set(normalized_group).difference(normalized_supported)
            if unsupported:
                raise ValueError(f"Compatibility group includes unsupported radionuclides: {sorted(unsupported)}")
            normalized_compatibility.append(normalized_group)

        unique_compatibility = tuple(dict.fromkeys(normalized_compatibility))

        normalized_release_processing: dict[str, float] | None = None
        if self.release_processing_minutes_by_radionuclide is not None:
            normalized_release_processing = {}
            for radionuclide, processing_minutes in self.release_processing_minutes_by_radionuclide.items():
                normalized = _normalize_radionuclide_name(radionuclide)
                if normalized not in normalized_supported:
                    raise ValueError(f"release processing entry references unsupported radionuclide {normalized}")
                value = float(processing_minutes)
                if value < 0.0:
                    raise ValueError("release processing minutes must be non-negative")
                normalized_release_processing[normalized] = value

        object.__setattr__(self, "cyclotron_id", cyclotron_id)
        object.__setattr__(self, "supported_radionuclides", normalized_supported)
        object.__setattr__(self, "production_cycle_minutes_by_radionuclide", cycle_lookup)
        object.__setattr__(self, "simultaneously_compatible_radionuclide_sets", unique_compatibility)
        object.__setattr__(self, "release_processing_minutes_by_radionuclide", normalized_release_processing)


@dataclass(frozen=True)
class ProductionWindow:
    window_id: int
    batch_ids: tuple[int, ...]
    radionuclides: tuple[str, ...]
    start_time_minutes: float
    end_time_minutes: float
    duration_minutes: float
    simultaneous_stream_count: int


@dataclass(frozen=True)
class CyclotronProductionSchedule:
    cyclotron_id: str
    windows: tuple[ProductionWindow, ...]
    total_batches: int
    total_windows: int
    production_start_time_minutes: float
    production_end_time_minutes: float
    total_elapsed_production_minutes: float
    max_simultaneous_streams_used: int
    all_batches_scheduled: bool
    fits_within_production_horizon: bool


def _can_share_window(
    capability: CyclotronProductionCapability,
    existing_radionuclides: tuple[str, ...],
    candidate_radionuclide: str,
) -> bool:
    if candidate_radionuclide in existing_radionuclides:
        return False

    new_group = frozenset(existing_radionuclides + (candidate_radionuclide,))
    if len(new_group) == 1:
        return True

    for compatible_set in capability.simultaneously_compatible_radionuclide_sets:
        if new_group.issubset(compatible_set):
            return True
    return False


def schedule_cyclotron_production_windows(
    batch_demands: tuple[RadionuclideBatchDemand, ...] | list[RadionuclideBatchDemand],
    capability: CyclotronProductionCapability,
    production_start_time_minutes: float = 0.0,
    production_horizon_minutes: float | None = None,
) -> CyclotronProductionSchedule:
    if production_start_time_minutes < 0.0:
        raise ValueError("production_start_time_minutes must be non-negative")
    if production_horizon_minutes is not None and production_horizon_minutes < 0.0:
        raise ValueError("production_horizon_minutes must be non-negative when provided")

    ordered_batches = tuple(batch_demands)
    for batch in ordered_batches:
        if batch.radionuclide not in capability.supported_radionuclides:
            raise ValueError(
                f"Batch {batch.batch_id} requires unsupported radionuclide {batch.radionuclide} "
                f"for cyclotron {capability.cyclotron_id}"
            )

    windows: list[ProductionWindow] = []
    pending = list(ordered_batches)
    current_time = float(production_start_time_minutes)
    window_id = 1

    while pending:
        first_batch = pending[0]
        selected_indices = [0]
        selected_radionuclides = [first_batch.radionuclide]

        if capability.max_simultaneous_production_streams > 1:
            candidate_index = 1
            while (
                candidate_index < len(pending)
                and len(selected_indices) < capability.max_simultaneous_production_streams
            ):
                candidate = pending[candidate_index]
                if _can_share_window(capability, tuple(selected_radionuclides), candidate.radionuclide):
                    selected_indices.append(candidate_index)
                    selected_radionuclides.append(candidate.radionuclide)
                candidate_index += 1

        selected_batches = [pending[index] for index in selected_indices]

        window_duration = max(
            capability.production_cycle_minutes_by_radionuclide[batch.radionuclide]
            for batch in selected_batches
        )
        start_time = current_time
        end_time = start_time + window_duration

        windows.append(
            ProductionWindow(
                window_id=window_id,
                batch_ids=tuple(batch.batch_id for batch in selected_batches),
                radionuclides=tuple(batch.radionuclide for batch in selected_batches),
                start_time_minutes=start_time,
                end_time_minutes=end_time,
                duration_minutes=window_duration,
                simultaneous_stream_count=len(selected_batches),
            )
        )

        for index in sorted(selected_indices, reverse=True):
            del pending[index]

        current_time = end_time
        window_id += 1

    production_end = current_time
    elapsed = production_end - production_start_time_minutes
    max_streams_used = max((window.simultaneous_stream_count for window in windows), default=0)

    if production_horizon_minutes is None:
        fits_within_horizon = True
    else:
        fits_within_horizon = production_end <= production_horizon_minutes

    return CyclotronProductionSchedule(
        cyclotron_id=capability.cyclotron_id,
        windows=tuple(windows),
        total_batches=len(ordered_batches),
        total_windows=len(windows),
        production_start_time_minutes=float(production_start_time_minutes),
        production_end_time_minutes=production_end,
        total_elapsed_production_minutes=elapsed,
        max_simultaneous_streams_used=max_streams_used,
        all_batches_scheduled=(len(ordered_batches) == sum(len(window.batch_ids) for window in windows)),
        fits_within_production_horizon=fits_within_horizon,
    )
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping, Sequence

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
    calibrated_eob_activity_mbq_by_radionuclide: Mapping[str, float] | None = None
    site_eob_capacity_mbq_per_day: float | None = None

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

        normalized_calibrated_eob: dict[str, float] | None = None
        if self.calibrated_eob_activity_mbq_by_radionuclide is not None:
            normalized_calibrated_eob = {}
            for radionuclide, eob_activity_mbq in self.calibrated_eob_activity_mbq_by_radionuclide.items():
                normalized = _normalize_radionuclide_name(radionuclide)
                if normalized not in normalized_supported:
                    raise ValueError(f"calibrated EOB activity entry references unsupported radionuclide {normalized}")
                value = float(eob_activity_mbq)
                if value <= 0.0:
                    raise ValueError("calibrated EOB activity must be positive when provided")
                normalized_calibrated_eob[normalized] = value

        site_eob_capacity = None
        if self.site_eob_capacity_mbq_per_day is not None:
            site_eob_capacity = float(self.site_eob_capacity_mbq_per_day)
            if site_eob_capacity <= 0.0:
                raise ValueError("site_eob_capacity_mbq_per_day must be positive when provided")

        object.__setattr__(self, "cyclotron_id", cyclotron_id)
        object.__setattr__(self, "supported_radionuclides", normalized_supported)
        object.__setattr__(self, "production_cycle_minutes_by_radionuclide", cycle_lookup)
        object.__setattr__(self, "simultaneously_compatible_radionuclide_sets", unique_compatibility)
        object.__setattr__(self, "release_processing_minutes_by_radionuclide", normalized_release_processing)
        object.__setattr__(self, "calibrated_eob_activity_mbq_by_radionuclide", normalized_calibrated_eob)
        object.__setattr__(self, "site_eob_capacity_mbq_per_day", site_eob_capacity)


@dataclass(frozen=True)
class ProductionWindow:
    window_id: int
    assigned_cyclotron_id: str
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


@dataclass(frozen=True)
class CyclotronAsset:
    cyclotron_id: str
    capability: CyclotronProductionCapability
    model_identifier: str | None = None
    manufacturer: str | None = None
    installed_quantity: int = 1
    capability_provenance: str | None = None

    def __post_init__(self) -> None:
        cyclotron_id = self.cyclotron_id.strip() if isinstance(self.cyclotron_id, str) else ""
        if not cyclotron_id:
            raise ValueError("cyclotron_id must be a non-empty string")
        if int(self.installed_quantity) < 1:
            raise ValueError("installed_quantity must be at least 1")
        if self.capability.cyclotron_id != cyclotron_id:
            raise ValueError("CyclotronAsset cyclotron_id must match capability.cyclotron_id")
        object.__setattr__(self, "cyclotron_id", cyclotron_id)
        object.__setattr__(self, "installed_quantity", int(self.installed_quantity))


@dataclass(frozen=True)
class CyclotronFleet:
    assets: tuple[CyclotronAsset, ...]
    fleet_id: str = "PRIMARY_FLEET"
    maximum_supported_assets: int = 16

    def __post_init__(self) -> None:
        assets = tuple(self.assets)
        if not assets:
            raise ValueError("Cyclotron fleet must contain at least one asset")
        if int(self.maximum_supported_assets) < 1:
            raise ValueError("maximum_supported_assets must be at least 1")
        if len(assets) > int(self.maximum_supported_assets):
            raise ValueError(
                f"Cyclotron fleet asset count {len(assets)} exceeds configured maximum_supported_assets {int(self.maximum_supported_assets)}"
            )
        seen_ids: set[str] = set()
        for asset in assets:
            if asset.cyclotron_id in seen_ids:
                raise ValueError(f"Duplicate cyclotron ID in fleet: {asset.cyclotron_id}")
            seen_ids.add(asset.cyclotron_id)
        object.__setattr__(self, "assets", assets)
        object.__setattr__(self, "maximum_supported_assets", int(self.maximum_supported_assets))

    @property
    def fleet_supported_radionuclides(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for asset in self.assets:
            for radionuclide in asset.capability.supported_radionuclides:
                seen[radionuclide] = None
        return tuple(seen.keys())

    @property
    def asset_count(self) -> int:
        return len(self.assets)


@dataclass(frozen=True)
class BatchCyclotronAssignment:
    batch_id: int
    radionuclide: str
    assigned_cyclotron_id: str
    assignment_reason: str


@dataclass(frozen=True)
class CyclotronFleetProductionSchedule:
    fleet_id: str
    batch_assignments: tuple[BatchCyclotronAssignment, ...]
    per_cyclotron_schedules: Mapping[str, CyclotronProductionSchedule]
    windows: tuple[ProductionWindow, ...]
    total_batches: int
    total_windows: int
    production_start_time_minutes: float
    production_end_time_minutes: float
    total_elapsed_production_minutes: float
    max_simultaneous_streams_used: int
    all_batches_scheduled: bool
    fits_within_production_horizon: bool


def build_single_cyclotron_fleet(
    capability: CyclotronProductionCapability,
    *,
    model_identifier: str | None = None,
    manufacturer: str | None = None,
    capability_provenance: str | None = None,
) -> CyclotronFleet:
    return CyclotronFleet(
        assets=(
            CyclotronAsset(
                cyclotron_id=capability.cyclotron_id,
                capability=capability,
                model_identifier=model_identifier,
                manufacturer=manufacturer,
                capability_provenance=capability_provenance,
            ),
        )
    )


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
                assigned_cyclotron_id=capability.cyclotron_id,
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


def _predicted_end_time_for_assignment(
    asset: CyclotronAsset,
    assigned_batches: Sequence[RadionuclideBatchDemand],
    candidate_batch: RadionuclideBatchDemand,
    *,
    production_start_time_minutes: float,
    production_horizon_minutes: float | None,
) -> float:
    schedule = schedule_cyclotron_production_windows(
        tuple(list(assigned_batches) + [candidate_batch]),
        asset.capability,
        production_start_time_minutes=production_start_time_minutes,
        production_horizon_minutes=production_horizon_minutes,
    )
    return schedule.production_end_time_minutes


def assign_batches_to_cyclotron_fleet(
    batch_demands: tuple[RadionuclideBatchDemand, ...] | list[RadionuclideBatchDemand],
    fleet: CyclotronFleet,
    *,
    production_start_time_minutes: float = 0.0,
    production_horizon_minutes: float | None = None,
) -> tuple[BatchCyclotronAssignment, ...]:
    ordered_batches = tuple(batch_demands)
    assigned_by_cyclotron: dict[str, list[RadionuclideBatchDemand]] = {asset.cyclotron_id: [] for asset in fleet.assets}
    assignments: list[BatchCyclotronAssignment] = []

    for batch in ordered_batches:
        eligible_assets = [asset for asset in fleet.assets if batch.radionuclide in asset.capability.supported_radionuclides]
        if not eligible_assets:
            raise ValueError(
                f"Batch {batch.batch_id} requires unsupported radionuclide {batch.radionuclide} for fleet {fleet.fleet_id}"
            )

        ranked_assets = sorted(
            (
                (
                    _predicted_end_time_for_assignment(
                        asset,
                        assigned_by_cyclotron[asset.cyclotron_id],
                        batch,
                        production_start_time_minutes=production_start_time_minutes,
                        production_horizon_minutes=production_horizon_minutes,
                    ),
                    asset.cyclotron_id,
                    asset,
                )
                for asset in eligible_assets
            ),
            key=lambda item: (item[0], item[1]),
        )
        selected_asset = ranked_assets[0][2]
        assigned_by_cyclotron[selected_asset.cyclotron_id].append(batch)
        assignments.append(
            BatchCyclotronAssignment(
                batch_id=batch.batch_id,
                radionuclide=batch.radionuclide,
                assigned_cyclotron_id=selected_asset.cyclotron_id,
                assignment_reason="deterministic earliest-finish eligible cyclotron",
            )
        )

    return tuple(assignments)


def schedule_cyclotron_fleet_production_windows(
    batch_demands: tuple[RadionuclideBatchDemand, ...] | list[RadionuclideBatchDemand],
    fleet: CyclotronFleet,
    production_start_time_minutes: float = 0.0,
    production_horizon_minutes: float | None = None,
) -> CyclotronFleetProductionSchedule:
    assignments = assign_batches_to_cyclotron_fleet(
        batch_demands,
        fleet,
        production_start_time_minutes=production_start_time_minutes,
        production_horizon_minutes=production_horizon_minutes,
    )

    batches_by_id = {batch.batch_id: batch for batch in tuple(batch_demands)}
    by_cyclotron: dict[str, list[RadionuclideBatchDemand]] = {asset.cyclotron_id: [] for asset in fleet.assets}
    for assignment in assignments:
        by_cyclotron[assignment.assigned_cyclotron_id].append(batches_by_id[assignment.batch_id])

    per_cyclotron: dict[str, CyclotronProductionSchedule] = {}
    for asset in fleet.assets:
        per_cyclotron[asset.cyclotron_id] = schedule_cyclotron_production_windows(
            by_cyclotron[asset.cyclotron_id],
            asset.capability,
            production_start_time_minutes=production_start_time_minutes,
            production_horizon_minutes=production_horizon_minutes,
        )

    flattened: list[ProductionWindow] = []
    global_window_id = 1
    for cyclotron_id, schedule in sorted(per_cyclotron.items()):
        for window in schedule.windows:
            flattened.append(
                ProductionWindow(
                    window_id=global_window_id,
                    assigned_cyclotron_id=cyclotron_id,
                    batch_ids=window.batch_ids,
                    radionuclides=window.radionuclides,
                    start_time_minutes=window.start_time_minutes,
                    end_time_minutes=window.end_time_minutes,
                    duration_minutes=window.duration_minutes,
                    simultaneous_stream_count=window.simultaneous_stream_count,
                )
            )
            global_window_id += 1

    ordered_windows = tuple(sorted(flattened, key=lambda window: (window.start_time_minutes, window.end_time_minutes, window.assigned_cyclotron_id, window.window_id)))
    max_end = max((schedule.production_end_time_minutes for schedule in per_cyclotron.values()), default=production_start_time_minutes)
    min_start = min((schedule.production_start_time_minutes for schedule in per_cyclotron.values()), default=production_start_time_minutes)

    return CyclotronFleetProductionSchedule(
        fleet_id=fleet.fleet_id,
        batch_assignments=assignments,
        per_cyclotron_schedules=per_cyclotron,
        windows=ordered_windows,
        total_batches=len(tuple(batch_demands)),
        total_windows=len(ordered_windows),
        production_start_time_minutes=float(min_start),
        production_end_time_minutes=float(max_end),
        total_elapsed_production_minutes=float(max_end - min_start),
        max_simultaneous_streams_used=max((schedule.max_simultaneous_streams_used for schedule in per_cyclotron.values()), default=0),
        all_batches_scheduled=all(schedule.all_batches_scheduled for schedule in per_cyclotron.values()),
        fits_within_production_horizon=all(schedule.fits_within_production_horizon for schedule in per_cyclotron.values()),
    )


def resolve_fleet_eob_capacity_mbq_per_day(
    *,
    fleet: CyclotronFleet,
    radionuclide: str,
    production_batches_per_day: int,
) -> tuple[float | None, str]:
    if production_batches_per_day < 1:
        raise ValueError("production_batches_per_day must be at least 1")

    isotope = _normalize_radionuclide_name(radionuclide)
    total_capacity_mbq = 0.0
    capacity_found = False
    unknown_assets = 0

    for asset in fleet.assets:
        capability = asset.capability
        if isotope not in capability.supported_radionuclides:
            continue

        if capability.site_eob_capacity_mbq_per_day is not None:
            total_capacity_mbq += float(capability.site_eob_capacity_mbq_per_day)
            capacity_found = True
            continue

        calibrated_map = capability.calibrated_eob_activity_mbq_by_radionuclide or {}
        calibrated_per_batch = calibrated_map.get(isotope)
        if calibrated_per_batch is not None:
            total_capacity_mbq += float(calibrated_per_batch) * float(production_batches_per_day)
            capacity_found = True
            continue

        unknown_assets += 1

    if not capacity_found:
        return None, "not_calibrated"
    if unknown_assets > 0:
        return total_capacity_mbq, "partial_fleet_calibrated"
    return total_capacity_mbq, "fleet_calibrated"
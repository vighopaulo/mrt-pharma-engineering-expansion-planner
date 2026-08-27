"""Persistent Clinical Resource Identity + Assignment Authority.

Establishes ONE physical resource model for INJECTION_ROOM/UPTAKE_ROOM/SCANNER
identities that persist across operating days, weeks, months, and the full
six-month planning horizon (sections 3-5, 17-18).

GOVERNING PRINCIPLE (unchanged capacity/physics): identity is assigned by
deterministically mapping the array index the day-engine ALREADY computes
internally (operating_day_scheduler.py::_allocate_earliest, previously
discarded) onto a stable ID -- no new allocation/selection algorithm, no
capacity change, no queueing change (sections 6-8).

Resource availability-by-date (sections 19-22) affects only which resource
COUNT is passed to the existing day-engine for that date; unavailable
resources are never deleted from the persistent inventory, they simply
receive zero assignments and are excluded from that date's active count.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Mapping

ClinicalResourceType = Literal["INJECTION_ROOM", "UPTAKE_ROOM", "SCANNER", "INBOUND_ROOM"]
ResourceAvailabilityState = Literal["AVAILABLE", "UNAVAILABLE"]
ResourceAssetState = Literal["EXISTING", "PROPOSED"]
ScannerModality = Literal["PET", "SPECT"]

_ID_PREFIX_BY_TYPE: Mapping[ClinicalResourceType, str] = {
    "INJECTION_ROOM": "INJ",
    "UPTAKE_ROOM": "UP",
    "SCANNER": "SCN",
    "INBOUND_ROOM": "IR",
}


def resource_id_for_index(resource_type: ClinicalResourceType, index: int) -> str:
    """Deterministic index->ID mapping (section 5/8): 0-based scheduler array
    index -> stable 1-based, zero-padded resource identity. Never a random
    UUID; the same index always yields the same ID."""
    if index < 0:
        raise ValueError("index must be non-negative")
    prefix = _ID_PREFIX_BY_TYPE[resource_type]
    return f"{prefix}-{index + 1:03d}"


@dataclass(frozen=True)
class ClinicalResource:
    """Section 3: the smallest coherent identifiable-clinical-resource model."""

    resource_id: str
    resource_type: ClinicalResourceType
    asset_state: ResourceAssetState = "EXISTING"
    building_id: str | None = None
    floor_id: str | None = None
    room_id: str | None = None
    source_provenance: str = "PROJECT_ASSUMPTION"
    capabilities: tuple[str, ...] = ()
    modality: ScannerModality | None = None
    """Section 52 (PET/SPECT scanner resource conservation): None preserves
    all pre-existing (undifferentiated) resource behavior unchanged -- only
    SCANNER resources may legitimately carry a modality tag."""

    def __post_init__(self) -> None:
        expected_prefix = _ID_PREFIX_BY_TYPE[self.resource_type]
        if not self.resource_id.startswith(f"{expected_prefix}-"):
            raise ValueError(f"resource_id {self.resource_id} does not match resource_type {self.resource_type}")
        if self.modality is not None and self.resource_type != "SCANNER":
            raise ValueError(f"modality may only be set on SCANNER resources, not {self.resource_type}")


@dataclass(frozen=True)
class ClinicalResourceInventory:
    """Section 18: one persistent facility resource inventory the long-horizon
    planner references; daily schedules consume it, never recreate it."""

    injection_rooms: tuple[ClinicalResource, ...]
    uptake_rooms: tuple[ClinicalResource, ...]
    scanners: tuple[ClinicalResource, ...]
    inbound_rooms: tuple[ClinicalResource, ...] = ()

    def __post_init__(self) -> None:
        for resource_type, resources in (
            ("INJECTION_ROOM", self.injection_rooms), ("UPTAKE_ROOM", self.uptake_rooms), ("SCANNER", self.scanners),
            ("INBOUND_ROOM", self.inbound_rooms),
        ):
            ids = [r.resource_id for r in resources]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {resource_type} resource_id in inventory")
            for r in resources:
                if r.resource_type != resource_type:
                    raise ValueError(f"{r.resource_id} has resource_type {r.resource_type}, expected {resource_type}")

    def resources_of_type(self, resource_type: ClinicalResourceType) -> tuple[ClinicalResource, ...]:
        return {
            "INJECTION_ROOM": self.injection_rooms, "UPTAKE_ROOM": self.uptake_rooms,
            "SCANNER": self.scanners, "INBOUND_ROOM": self.inbound_rooms,
        }[resource_type]

    def scanners_of_modality(self, modality: ScannerModality) -> tuple[ClinicalResource, ...]:
        """Section 52: PET procedures may only consume PET-tagged scanners and
        SPECT procedures may only consume SPECT-tagged scanners. Scanners with
        `modality=None` (all pre-existing single-modality benchmarks) are
        untagged legacy resources and are excluded from both modality pools --
        callers of a mixed-modality scenario must build a modality-tagged
        inventory explicitly (no silent capacity sharing)."""
        return tuple(s for s in self.scanners if s.modality == modality)


    def by_id(self, resource_id: str) -> ClinicalResource:
        for resources in (self.injection_rooms, self.uptake_rooms, self.scanners, self.inbound_rooms):
            for r in resources:
                if r.resource_id == resource_id:
                    return r
        raise ValueError(f"Unknown resource_id: {resource_id}")


def build_deterministic_resource_inventory(
    *,
    injection_room_count: int,
    uptake_room_count: int,
    scanner_count: int,
    inbound_room_count: int = 0,
    asset_state: ResourceAssetState = "EXISTING",
    source_provenance: str = "PROJECT_ASSUMPTION",
) -> ClinicalResourceInventory:
    """Section 5-6: exactly `injection_room_count` INJ-xxx / `uptake_room_count`
    UP-xxx / `scanner_count` SCN-xxx / `inbound_room_count` IR-xxx identities --
    no hidden extra resources, no fewer than requested."""
    if injection_room_count < 1 or uptake_room_count < 1 or scanner_count < 1:
        raise ValueError("injection/uptake/scanner counts must each be at least 1")
    if inbound_room_count < 0:
        raise ValueError("inbound_room_count must be non-negative")
    return ClinicalResourceInventory(
        injection_rooms=tuple(
            ClinicalResource(resource_id=resource_id_for_index("INJECTION_ROOM", i), resource_type="INJECTION_ROOM",
                              asset_state=asset_state, source_provenance=source_provenance)
            for i in range(injection_room_count)
        ),
        uptake_rooms=tuple(
            ClinicalResource(resource_id=resource_id_for_index("UPTAKE_ROOM", i), resource_type="UPTAKE_ROOM",
                              asset_state=asset_state, source_provenance=source_provenance)
            for i in range(uptake_room_count)
        ),
        scanners=tuple(
            ClinicalResource(resource_id=resource_id_for_index("SCANNER", i), resource_type="SCANNER",
                              asset_state=asset_state, source_provenance=source_provenance)
            for i in range(scanner_count)
        ),
        inbound_rooms=tuple(
            ClinicalResource(resource_id=resource_id_for_index("INBOUND_ROOM", i), resource_type="INBOUND_ROOM",
                              asset_state=asset_state, source_provenance=source_provenance)
            for i in range(inbound_room_count)
        ),
    )


def build_modality_tagged_scanner_pool(
    *,
    pet_scanner_count: int,
    spect_scanner_count: int,
    asset_state: ResourceAssetState = "EXISTING",
    source_provenance: str = "PROJECT_ASSUMPTION",
) -> tuple[ClinicalResource, ...]:
    """Section 52: build a scanner pool where every scanner is tagged PET or
    SPECT (never shared/untagged) -- exactly `pet_scanner_count` PET-tagged and
    `spect_scanner_count` SPECT-tagged SCN-xxx identities, contiguous indices
    so resource_id remains a stable, deterministic, zero-padded identity
    (section 5/8) across the combined pool."""
    if pet_scanner_count < 0 or spect_scanner_count < 0:
        raise ValueError("scanner counts must be non-negative")
    if pet_scanner_count + spect_scanner_count < 1:
        raise ValueError("at least one PET or SPECT scanner is required")
    pet_scanners = tuple(
        ClinicalResource(resource_id=resource_id_for_index("SCANNER", i), resource_type="SCANNER",
                          asset_state=asset_state, source_provenance=source_provenance, modality="PET")
        for i in range(pet_scanner_count)
    )
    spect_scanners = tuple(
        ClinicalResource(resource_id=resource_id_for_index("SCANNER", pet_scanner_count + i), resource_type="SCANNER",
                          asset_state=asset_state, source_provenance=source_provenance, modality="SPECT")
        for i in range(spect_scanner_count)
    )
    return pet_scanners + spect_scanners


def add_proposed_resources(
    inventory: ClinicalResourceInventory, *, resource_type: ClinicalResourceType, additional_count: int,
) -> ClinicalResourceInventory:
    """Section 45: CAPITAL_PLANNING may add PROPOSED resources beyond the
    existing inventory; existing identities/order are preserved unchanged."""
    if additional_count <= 0:
        raise ValueError("additional_count must be positive")
    existing = inventory.resources_of_type(resource_type)
    new_resources = tuple(
        ClinicalResource(resource_id=resource_id_for_index(resource_type, len(existing) + i), resource_type=resource_type,
                          asset_state="PROPOSED", source_provenance="PROJECT_ASSUMPTION")
        for i in range(additional_count)
    )
    combined = {
        "INJECTION_ROOM": inventory.injection_rooms, "UPTAKE_ROOM": inventory.uptake_rooms,
        "SCANNER": inventory.scanners, "INBOUND_ROOM": inventory.inbound_rooms,
    }
    combined[resource_type] = existing + new_resources
    return ClinicalResourceInventory(
        injection_rooms=combined["INJECTION_ROOM"], uptake_rooms=combined["UPTAKE_ROOM"],
        scanners=combined["SCANNER"], inbound_rooms=combined["INBOUND_ROOM"],
    )


# ---------------------------------------------------------------------------
# Availability-by-date (sections 19-22, 44)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceAvailabilityCalendar:
    """Section 19-22: deterministic calendar availability only (no stochastic
    breakdowns). An UNAVAILABLE resource is never deleted (section 22) --
    it is simply excluded from that date's active count/index mapping."""

    inventory: ClinicalResourceInventory
    unavailable_by_date: Mapping[date, frozenset[str]]

    def state_on(self, *, resource_id: str, day: date) -> ResourceAvailabilityState:
        self.inventory.by_id(resource_id)  # raises if unknown
        if resource_id in self.unavailable_by_date.get(day, frozenset()):
            return "UNAVAILABLE"
        return "AVAILABLE"

    def active_resource_ids_for_date(self, *, resource_type: ClinicalResourceType, day: date) -> tuple[str, ...]:
        """Section 21: the day-engine's resource COUNT for `resource_type` on
        `day` must equal len(this). Only EXISTING (or PROPOSED-but-installed,
        per caller's inventory construction) resources in AVAILABLE state are
        active; PROPOSED resources not yet built are excluded by the caller
        selecting which inventory/asset_state subset to pass in."""
        return tuple(
            r.resource_id for r in self.inventory.resources_of_type(resource_type)
            if self.state_on(resource_id=r.resource_id, day=day) == "AVAILABLE"
        )

    def compacted_index_to_resource_id(self, *, resource_type: ClinicalResourceType, day: date) -> dict[int, str]:
        """Maps the day-engine's 0-based COMPACTED array index (built from
        only that day's active resources) back to the persistent resource_id
        (section 20: the scheduler must not see/assign an UNAVAILABLE
        resource's slot)."""
        active_ids = self.active_resource_ids_for_date(resource_type=resource_type, day=day)
        return {index: resource_id for index, resource_id in enumerate(active_ids)}


def build_calendar_with_no_exceptions(inventory: ClinicalResourceInventory) -> ResourceAvailabilityCalendar:
    """Every resource AVAILABLE on every date (the common case)."""
    return ResourceAvailabilityCalendar(inventory=inventory, unavailable_by_date={})

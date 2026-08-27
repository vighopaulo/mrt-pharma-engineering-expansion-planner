"""Canonical Entity Identity, Spatial Binding, and End-to-End Traceability
Authority (Phase 1B).

GOVERNANCE: this module does NOT recompute or duplicate ANY existing
physics/decay/transport/production/CapEx/OPEX/NPV/IRR mathematics, and does
NOT introduce a second spatial registry. It is a pure IDENTITY/BINDING/
TRACEABILITY layer: given IDs already produced by existing authorities
(`production_clinical_schedule.ProductionClinicalPatientTrace`,
`clinical_resource_identity.ClinicalResource`,
`cyclotron_production_windows.BatchCyclotronAssignment`,
`oncology_pet_spect_scenario.SpectDoseLineage`,
`canonical_spatial_authority.CanonicalSpatialObject`, ...), it registers and
resolves cross-entity relationships that are today implicit, index-based, or
reconstructable-only.

Room/location resolution reuses `canonical_spatial_authority` verbatim
(`SpatialObjectRegistry`, `CanonicalSpatialObject.parent_object_id`/
`engineering_object_id`) -- never a parallel geometry model.

Every relationship is stored as an explicit, queryable index built on TWO
generic, independently-tested primitives (`_OneToManyIndex`/
`_ManyToManyIndex`) rather than N bespoke dict pairs. Registration functions
("bind_*") only ever copy IDs already present on existing records; adapter
functions ("bind_production_clinical_trace", ...) extract those IDs from
real existing objects without altering them.

Generator-sourced supply is tracked through its own index
(`generator_batches_or_supplies`), never forced through cyclotron batch
semantics -- per the audit, `PreparationBatch`/`SpectDoseLineage` use a
different identifier scheme (string batch IDs) than PET/cyclotron batches
(integer `RadionuclideBatchDemand.batch_id`). All batch-like keys are
normalized to `str(...)` for cross-domain lookup only; the ORIGINAL typed ID
on the source record is never altered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import canonical_spatial_authority as csa
from clinical_resource_identity import ClinicalResourceType, resource_id_for_index

UNRESOLVED = "UNRESOLVED"
UNRESOLVED_LEGACY_LOCATION_REFERENCE = "UNRESOLVED_LEGACY_LOCATION_REFERENCE"

TransportResourceIdentityModel = Literal["INSTANCE_IDENTITY_AVAILABLE", "AGGREGATE_RESOURCE_ONLY"]

# Section 19: which transport technologies carry a genuine persistent
# per-unit identifier today vs. only an aggregate fleet count. Evidence:
# `production_clinical_schedule.MRTCarrier.carrier_id` is a real per-unit
# int; `conventional_transport_authority.py`/`dedicated_rp_pts_authority.py`
# only expose aggregate counts (`installed_stations`, `peak_concurrent_carriers`).
TRANSPORT_RESOURCE_IDENTITY_MODEL: dict[str, TransportResourceIdentityModel] = {
    "MRT_CARRIER": "INSTANCE_IDENTITY_AVAILABLE",
    "AGV": "AGGREGATE_RESOURCE_ONLY",
    "PTS_CARRIER": "AGGREGATE_RESOURCE_ONLY",
    "RP_PTS_CARRIER": "AGGREGATE_RESOURCE_ONLY",
    "MANUAL_PORTER": "AGGREGATE_RESOURCE_ONLY",
}


# ---------------------------------------------------------------------------
# Generic index primitives (section 29: ONE tested implementation per
# relationship shape, never N bespoke dict pairs)
# ---------------------------------------------------------------------------


@dataclass
class _OneToManyIndex:
    """`child` resolves to exactly one `parent`; `parent` resolves to the
    set of its children. Re-binding a child to a new parent removes it from
    the old parent's child set (never leaves a stale reverse entry)."""

    forward: dict[str, str] = field(default_factory=dict)
    reverse: dict[str, set[str]] = field(default_factory=dict)

    def bind(self, child: str, parent: str) -> None:
        previous = self.forward.get(child)
        if previous is not None and previous in self.reverse:
            self.reverse[previous].discard(child)
        self.forward[child] = parent
        self.reverse.setdefault(parent, set()).add(child)

    def parent_of(self, child: str) -> str | None:
        return self.forward.get(child)

    def children_of(self, parent: str) -> tuple[str, ...]:
        return tuple(sorted(self.reverse.get(parent, ())))

    def clone(self) -> "_OneToManyIndex":
        return _OneToManyIndex(forward=dict(self.forward), reverse={k: set(v) for k, v in self.reverse.items()})


@dataclass
class _ManyToManyIndex:
    """Arbitrary `a` <-> `b` associations (e.g. one payload may carry
    several patients; in principle a patient could appear on more than one
    payload across service legs)."""

    forward: dict[str, set[str]] = field(default_factory=dict)
    reverse: dict[str, set[str]] = field(default_factory=dict)

    def bind(self, a: str, b: str) -> None:
        self.forward.setdefault(a, set()).add(b)
        self.reverse.setdefault(b, set()).add(a)

    def related_to_a(self, a: str) -> tuple[str, ...]:
        return tuple(sorted(self.forward.get(a, ())))

    def related_to_b(self, b: str) -> tuple[str, ...]:
        return tuple(sorted(self.reverse.get(b, ())))

    def clone(self) -> "_ManyToManyIndex":
        return _ManyToManyIndex(forward={k: set(v) for k, v in self.forward.items()}, reverse={k: set(v) for k, v in self.reverse.items()})


@dataclass(frozen=True)
class BatchSourceBinding:
    """Section 8-10: a batch/supply is EITHER cyclotron-sourced OR
    generator-sourced -- never both -- so the binding honestly names which."""

    batch_id: str
    source_type: Literal["CYCLOTRON", "GENERATOR"]
    cyclotron_id: str | None = None
    generator_id: str | None = None


# ---------------------------------------------------------------------------
# Registry (section 29)
# ---------------------------------------------------------------------------


@dataclass
class EntityBindingRegistry:
    """The unified cross-entity binding/index layer. `CanonicalSpatialObject`
    remains the spatial authority (section 29) -- this registry only stores
    the ID-to-ID relationships, never geometry."""

    patient_room: _OneToManyIndex = field(default_factory=_OneToManyIndex)
    patient_radionuclide: dict[str, str] = field(default_factory=dict)
    patient_batch: _OneToManyIndex = field(default_factory=_OneToManyIndex)
    batch_source: dict[str, BatchSourceBinding] = field(default_factory=dict)
    batch_cyclotron: _OneToManyIndex = field(default_factory=_OneToManyIndex)
    batch_or_supply_generator: _OneToManyIndex = field(default_factory=_OneToManyIndex)
    batch_payload: _OneToManyIndex = field(default_factory=_OneToManyIndex)
    payload_patient: _ManyToManyIndex = field(default_factory=_ManyToManyIndex)
    mission_payload: _OneToManyIndex = field(default_factory=_OneToManyIndex)
    mission_transport_resource: _OneToManyIndex = field(default_factory=_OneToManyIndex)
    equipment_room: _OneToManyIndex = field(default_factory=_OneToManyIndex)
    equipment_kind: dict[str, str] = field(default_factory=dict)  # equipment_id -> "CYCLOTRON"/"GENERATOR"/"SCANNER"
    clinical_resource_room: _OneToManyIndex = field(default_factory=_OneToManyIndex)
    patient_scanner: _OneToManyIndex = field(default_factory=_OneToManyIndex)
    transport_interface_room: _OneToManyIndex = field(default_factory=_OneToManyIndex)
    interface_kind: dict[str, str] = field(default_factory=dict)  # interface_id -> "MRT"/"PTS"/"RP_PTS"/"AGV"/"MANUAL_DELIVERY_POINT"

    def clone(self) -> "EntityBindingRegistry":
        """Section 30: deep-clones every index -- used to branch a What-If's
        bindings without ever mutating the parent Lockdown's snapshot."""
        return EntityBindingRegistry(
            patient_room=self.patient_room.clone(), patient_radionuclide=dict(self.patient_radionuclide),
            patient_batch=self.patient_batch.clone(), batch_source=dict(self.batch_source),
            batch_cyclotron=self.batch_cyclotron.clone(), batch_or_supply_generator=self.batch_or_supply_generator.clone(),
            batch_payload=self.batch_payload.clone(), payload_patient=self.payload_patient.clone(),
            mission_payload=self.mission_payload.clone(), mission_transport_resource=self.mission_transport_resource.clone(),
            equipment_room=self.equipment_room.clone(), equipment_kind=dict(self.equipment_kind),
            clinical_resource_room=self.clinical_resource_room.clone(), patient_scanner=self.patient_scanner.clone(),
            transport_interface_room=self.transport_interface_room.clone(), interface_kind=dict(self.interface_kind),
        )


def branch_entity_bindings(parent: EntityBindingRegistry) -> EntityBindingRegistry:
    """Section 30: a What-If's bindings start as a clone of its parent
    Lockdown's -- mirrors `WhatIfSpatialState.branch_from` exactly."""
    return parent.clone()


# ---------------------------------------------------------------------------
# Registration ("bind_*") -- sections 5-24
# ---------------------------------------------------------------------------


def bind_patient_room(registry: EntityBindingRegistry, *, patient_id: str, room_id: str) -> None:
    registry.patient_room.bind(patient_id, room_id)


def bind_patient_radionuclide(registry: EntityBindingRegistry, *, patient_id: str, radionuclide_id: str) -> None:
    registry.patient_radionuclide[patient_id] = radionuclide_id


def bind_patient_batch(registry: EntityBindingRegistry, *, patient_id: str, batch_id: str) -> None:
    registry.patient_batch.bind(patient_id, batch_id)


def bind_batch_cyclotron(registry: EntityBindingRegistry, *, batch_id: str, cyclotron_id: str) -> None:
    registry.batch_cyclotron.bind(batch_id, cyclotron_id)
    registry.batch_source[batch_id] = BatchSourceBinding(batch_id=batch_id, source_type="CYCLOTRON", cyclotron_id=cyclotron_id)


def bind_batch_or_supply_generator(registry: EntityBindingRegistry, *, batch_or_supply_id: str, generator_id: str) -> None:
    """Section 10: generator-sourced supply is bound through its OWN index --
    never through `batch_cyclotron` -- so PET and SPECT source semantics are
    never conflated."""
    registry.batch_or_supply_generator.bind(batch_or_supply_id, generator_id)
    registry.batch_source[batch_or_supply_id] = BatchSourceBinding(batch_id=batch_or_supply_id, source_type="GENERATOR", generator_id=generator_id)


def bind_batch_payload(registry: EntityBindingRegistry, *, batch_id: str, payload_id: str) -> None:
    registry.batch_payload.bind(payload_id, batch_id)


def bind_payload_patient(registry: EntityBindingRegistry, *, payload_id: str, patient_id: str) -> None:
    registry.payload_patient.bind(payload_id, patient_id)


def bind_mission_payload(registry: EntityBindingRegistry, *, mission_id: str, payload_id: str) -> None:
    registry.mission_payload.bind(mission_id, payload_id)


def bind_mission_transport_resource(registry: EntityBindingRegistry, *, mission_id: str, transport_resource_id: str) -> None:
    registry.mission_transport_resource.bind(mission_id, transport_resource_id)


def bind_equipment_room(registry: EntityBindingRegistry, *, equipment_id: str, room_id: str, equipment_kind: str) -> None:
    """`equipment_kind` in {"CYCLOTRON", "GENERATOR", "SCANNER", ...} --
    generic so `equipment_in_room` can aggregate across kinds (section 24)
    while `cyclotrons_in_room`/`generators_in_room`/`scanners_in_room` filter
    by kind (sections 11-12)."""
    registry.equipment_room.bind(equipment_id, room_id)
    registry.equipment_kind[equipment_id] = equipment_kind


def bind_clinical_resource_room(registry: EntityBindingRegistry, *, resource_id: str, room_id: str) -> None:
    registry.clinical_resource_room.bind(resource_id, room_id)


def bind_patient_scanner(registry: EntityBindingRegistry, *, patient_id: str, scanner_id: str) -> None:
    registry.patient_scanner.bind(patient_id, scanner_id)


def bind_transport_interface_room(registry: EntityBindingRegistry, *, interface_id: str, room_id: str, interface_kind: str) -> None:
    """`interface_kind` in {"MRT", "PTS", "RP_PTS", "AGV", "MANUAL_DELIVERY_POINT"}."""
    registry.transport_interface_room.bind(interface_id, room_id)
    registry.interface_kind[interface_id] = interface_kind


# ---------------------------------------------------------------------------
# Queries -- exact names required by sections 4-24
# ---------------------------------------------------------------------------


def room_for_patient(registry: EntityBindingRegistry, patient_id: str) -> str | None:
    return registry.patient_room.parent_of(patient_id)


def patients_in_room(registry: EntityBindingRegistry, room_id: str) -> tuple[str, ...]:
    return registry.patient_room.children_of(room_id)


def radionuclide_for_patient(registry: EntityBindingRegistry, patient_id: str) -> str | None:
    return registry.patient_radionuclide.get(patient_id)


def batch_for_patient(registry: EntityBindingRegistry, patient_id: str) -> str | None:
    return registry.patient_batch.parent_of(patient_id)


def patients_for_batch(registry: EntityBindingRegistry, batch_id: str) -> tuple[str, ...]:
    return registry.patient_batch.children_of(batch_id)


def cyclotron_for_batch(registry: EntityBindingRegistry, batch_id: str) -> str | None:
    return registry.batch_cyclotron.parent_of(batch_id)


def batches_for_cyclotron(registry: EntityBindingRegistry, cyclotron_id: str) -> tuple[str, ...]:
    return registry.batch_cyclotron.children_of(cyclotron_id)


def generator_for_batch_or_supply(registry: EntityBindingRegistry, batch_or_supply_id: str) -> str | None:
    return registry.batch_or_supply_generator.parent_of(batch_or_supply_id)


def batches_or_supplies_for_generator(registry: EntityBindingRegistry, generator_id: str) -> tuple[str, ...]:
    return registry.batch_or_supply_generator.children_of(generator_id)


def _equipment_in_room_of_kind(registry: EntityBindingRegistry, room_id: str, kind: str) -> tuple[str, ...]:
    return tuple(sorted(eid for eid in registry.equipment_room.children_of(room_id) if registry.equipment_kind.get(eid) == kind))


def room_for_cyclotron(registry: EntityBindingRegistry, cyclotron_id: str) -> str | None:
    return registry.equipment_room.parent_of(cyclotron_id)


def cyclotrons_in_room(registry: EntityBindingRegistry, room_id: str) -> tuple[str, ...]:
    return _equipment_in_room_of_kind(registry, room_id, "CYCLOTRON")


def room_for_generator(registry: EntityBindingRegistry, generator_id: str) -> str | None:
    return registry.equipment_room.parent_of(generator_id)


def generators_in_room(registry: EntityBindingRegistry, room_id: str) -> tuple[str, ...]:
    return _equipment_in_room_of_kind(registry, room_id, "GENERATOR")


def room_for_scanner(registry: EntityBindingRegistry, scanner_id: str) -> str | None:
    return registry.equipment_room.parent_of(scanner_id) or registry.clinical_resource_room.parent_of(scanner_id)


def scanners_in_room(registry: EntityBindingRegistry, room_id: str) -> tuple[str, ...]:
    from_equipment = _equipment_in_room_of_kind(registry, room_id, "SCANNER")
    from_clinical = tuple(rid for rid in registry.clinical_resource_room.children_of(room_id) if rid.startswith("SCN-"))
    return tuple(sorted(set(from_equipment) | set(from_clinical)))


def scanner_for_patient(registry: EntityBindingRegistry, patient_id: str) -> str | None:
    return registry.patient_scanner.parent_of(patient_id)


def patients_for_scanner(registry: EntityBindingRegistry, scanner_id: str) -> tuple[str, ...]:
    return registry.patient_scanner.children_of(scanner_id)


def room_for_clinical_resource(registry: EntityBindingRegistry, resource_id: str) -> str | None:
    return registry.clinical_resource_room.parent_of(resource_id)


def resources_in_room(registry: EntityBindingRegistry, room_id: str) -> tuple[str, ...]:
    return registry.clinical_resource_room.children_of(room_id)


def payloads_for_batch(registry: EntityBindingRegistry, batch_id: str) -> tuple[str, ...]:
    return registry.batch_payload.children_of(batch_id)


def batch_for_payload(registry: EntityBindingRegistry, payload_id: str) -> str | None:
    return registry.batch_payload.parent_of(payload_id)


def payloads_for_patient(registry: EntityBindingRegistry, patient_id: str) -> tuple[str, ...]:
    return registry.payload_patient.related_to_b(patient_id)


def patients_for_payload(registry: EntityBindingRegistry, payload_id: str) -> tuple[str, ...]:
    return registry.payload_patient.related_to_a(payload_id)


def patient_for_payload(registry: EntityBindingRegistry, payload_id: str) -> str | None:
    """Section 18: convenience singular accessor. A `TransportPayload` MAY
    legitimately carry more than one patient (batched delivery); this
    returns the single patient only when exactly one is bound, else None --
    callers needing the full set must use `patients_for_payload`."""
    patients = patients_for_payload(registry, payload_id)
    return patients[0] if len(patients) == 1 else None


def payload_for_mission(registry: EntityBindingRegistry, mission_id: str) -> str | None:
    return registry.mission_payload.parent_of(mission_id)


def missions_for_payload(registry: EntityBindingRegistry, payload_id: str) -> tuple[str, ...]:
    return registry.mission_payload.children_of(payload_id)


def mission_for_payload(registry: EntityBindingRegistry, payload_id: str) -> str | None:
    """Section 20: singular accessor -- returns the single mission only
    when exactly one is bound (see `patient_for_payload` rationale)."""
    missions = missions_for_payload(registry, payload_id)
    return missions[0] if len(missions) == 1 else None


def transport_resource_for_mission(registry: EntityBindingRegistry, mission_id: str) -> str | None:
    return registry.mission_transport_resource.parent_of(mission_id)


def missions_for_transport_resource(registry: EntityBindingRegistry, transport_resource_id: str) -> tuple[str, ...]:
    return registry.mission_transport_resource.children_of(transport_resource_id)


def transport_interfaces_for_room(registry: EntityBindingRegistry, room_id: str) -> tuple[str, ...]:
    return registry.transport_interface_room.children_of(room_id)


def room_for_transport_interface(registry: EntityBindingRegistry, interface_id: str) -> str | None:
    return registry.transport_interface_room.parent_of(interface_id)


def equipment_in_room(registry: EntityBindingRegistry, room_id: str) -> tuple[str, ...]:
    """Section 24: generic reverse query across ALL equipment kinds bound
    via `bind_equipment_room` (cyclotron/generator/scanner/...)."""
    return registry.equipment_room.children_of(room_id)


# ---------------------------------------------------------------------------
# Room-as-spatial-anchor helpers (sections 2, 4, 11-12, 21, 23) -- reuse
# `canonical_spatial_authority` verbatim, never a second spatial graph.
# ---------------------------------------------------------------------------


def nearest_room_id_for_spatial_object(spatial_registry: csa.SpatialObjectRegistry, object_id: str) -> str | None:
    """Walks the EXISTING `parent_object_id` hierarchy until a ROOM-typed
    object is found. Reuses `SpatialObjectRegistry.objects`/
    `CanonicalSpatialObject.parent_object_id` verbatim -- never a second
    spatial graph."""
    seen: set[str] = set()
    current = spatial_registry.objects.get(object_id)
    while current is not None and current.mrtway_object_id not in seen:
        if current.object_type == "ROOM":
            return current.mrtway_object_id
        seen.add(current.mrtway_object_id)
        current = spatial_registry.objects.get(current.parent_object_id) if current.parent_object_id else None
    return None


def room_for_engineering_object(spatial_registry: csa.SpatialObjectRegistry, engineering_object_id: str) -> str | None:
    """Section 11-12: resolves a room for any equipment ID ALREADY bridged
    into the canonical spatial registry via
    `CanonicalSpatialObject.engineering_object_id` (e.g. "CY-001",
    "GEN-001", "SCN-001") -- returns None (not a fabricated room) if no such
    spatial object exists yet."""
    obj = next((o for o in spatial_registry.objects.values() if o.engineering_object_id == engineering_object_id), None)
    if obj is None:
        return None
    if obj.object_type == "ROOM":
        return obj.mrtway_object_id
    return nearest_room_id_for_spatial_object(spatial_registry, obj.parent_object_id) if obj.parent_object_id else None


def bind_equipment_room_from_spatial_registry(
    registry: EntityBindingRegistry, spatial_registry: csa.SpatialObjectRegistry, *, equipment_id: str, equipment_kind: str,
) -> str | None:
    """Populates `equipment_room` FROM the canonical spatial registry when
    possible (section 2: canonical spatial identity is the location
    foundation); returns the resolved room_id, or None if the equipment has
    no spatial representation yet (caller may then fall back to an explicit
    `bind_equipment_room` registration)."""
    room_id = room_for_engineering_object(spatial_registry, equipment_id)
    if room_id is not None:
        bind_equipment_room(registry, equipment_id=equipment_id, room_id=room_id, equipment_kind=equipment_kind)
    return room_id


def resolve_manual_delivery_point(known_room_ids: set[str], location: str) -> str:
    """Section 22: Manual transport's plain origin/destination strings are
    resolved ONLY if they already name a known canonical room -- never
    fabricated. Preserves the string; classifies unresolvable ones
    honestly."""
    return location if location in known_room_ids else UNRESOLVED_LEGACY_LOCATION_REFERENCE


# ---------------------------------------------------------------------------
# Clinical event location binding (section 15) -- resolves scheduler
# resource INDICES (not room IDs) to canonical rooms without rewriting
# scheduling.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClinicalEventLocationResolution:
    injection_resource_id: str | None
    injection_room_id: str | None
    uptake_resource_id: str | None
    uptake_room_id: str | None
    scanner_resource_id: str | None
    scanner_room_id: str | None


def resolve_clinical_event_location(
    registry: EntityBindingRegistry, *, injection_resource_index: int | None = None,
    uptake_resource_index: int | None = None, scanner_resource_index: int | None = None,
) -> ClinicalEventLocationResolution:
    """Section 15: event -> clinical resource -> canonical room. Numerical
    timestamps are never touched; this only resolves location for an
    already-scheduled event's resource indices."""
    resource_type_by_field: dict[str, ClinicalResourceType] = {
        "injection": "INJECTION_ROOM", "uptake": "UPTAKE_ROOM", "scanner": "SCANNER",
    }
    resolved: dict[str, str | None] = {}
    for field_name, index in (("injection", injection_resource_index), ("uptake", uptake_resource_index), ("scanner", scanner_resource_index)):
        if index is None:
            resolved[f"{field_name}_resource_id"] = None
            resolved[f"{field_name}_room_id"] = None
            continue
        resource_id = resource_id_for_index(resource_type_by_field[field_name], index)
        resolved[f"{field_name}_resource_id"] = resource_id
        resolved[f"{field_name}_room_id"] = room_for_clinical_resource(registry, resource_id)
    return ClinicalEventLocationResolution(**resolved)


# ---------------------------------------------------------------------------
# Adapters -- populate the registry FROM existing real records, never
# recomputing anything (sections 2, 8, 16, 33, 34).
# ---------------------------------------------------------------------------


def bind_production_clinical_trace(registry: EntityBindingRegistry, trace: object) -> ClinicalEventLocationResolution:
    """Extracts already-computed IDs from an EXISTING
    `production_clinical_schedule.ProductionClinicalPatientTrace` (duck-typed
    to avoid a hard import) -- never recalculates timing/activity/batch
    composition."""
    batch_id = str(trace.batch_id)
    bind_patient_batch(registry, patient_id=trace.patient_id, batch_id=batch_id)
    bind_patient_radionuclide(registry, patient_id=trace.patient_id, radionuclide_id=trace.radionuclide)
    bind_batch_cyclotron(registry, batch_id=batch_id, cyclotron_id=trace.assigned_cyclotron_id)
    bind_batch_payload(registry, batch_id=batch_id, payload_id=trace.payload_id)
    bind_payload_patient(registry, payload_id=trace.payload_id, patient_id=trace.patient_id)
    if getattr(trace, "inbound_room_id", None) is not None:
        bind_patient_room(registry, patient_id=trace.patient_id, room_id=trace.inbound_room_id)
    resolution = resolve_clinical_event_location(
        registry, injection_resource_index=trace.injection_resource_index, uptake_resource_index=trace.uptake_resource_index,
        scanner_resource_index=trace.scanner_resource_index,
    )
    if resolution.scanner_resource_id is not None:
        bind_patient_scanner(registry, patient_id=trace.patient_id, scanner_id=resolution.scanner_resource_id)
    return resolution


def bind_clinical_resource(registry: EntityBindingRegistry, resource: object) -> None:
    """Extracts room binding from an EXISTING `clinical_resource_identity.
    ClinicalResource` (duck-typed) -- never mutates it."""
    if getattr(resource, "room_id", None) is not None:
        bind_clinical_resource_room(registry, resource_id=resource.resource_id, room_id=resource.room_id)


def bind_spect_dose_lineage(registry: EntityBindingRegistry, lineage: object) -> None:
    """Extracts already-computed IDs from an EXISTING
    `oncology_pet_spect_scenario.SpectDoseLineage` (duck-typed) -- generator
    linkage is honestly bound through `bind_batch_or_supply_generator`, NEVER
    through `bind_batch_cyclotron` (section 10)."""
    preparation_batch = lineage.preparation_batch
    batch_or_supply_id = str(preparation_batch.batch_id)
    bind_patient_batch(registry, patient_id=lineage.patient_id, batch_id=batch_or_supply_id)
    bind_batch_or_supply_generator(registry, batch_or_supply_id=batch_or_supply_id, generator_id=lineage.generator_id)
    bind_patient_radionuclide(registry, patient_id=lineage.patient_id, radionuclide_id="Tc-99m")
    if getattr(lineage, "scanner_id", None) is not None:
        bind_patient_scanner(registry, patient_id=lineage.patient_id, scanner_id=lineage.scanner_id)


# ---------------------------------------------------------------------------
# Room / patient / batch queryability (sections 26-28, 38-40)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoomQueryResult:
    room_id: str
    assigned_patient_ids: tuple[str, ...]
    equipment_ids: tuple[str, ...]
    clinical_resource_ids: tuple[str, ...]
    transport_interface_ids: tuple[str, ...]


def describe_room(registry: EntityBindingRegistry, room_id: str) -> RoomQueryResult:
    """Section 26/39: room-centered queryability over EXISTING bindings
    only -- no live-state/occupancy-over-time claim."""
    return RoomQueryResult(
        room_id=room_id, assigned_patient_ids=patients_in_room(registry, room_id),
        equipment_ids=equipment_in_room(registry, room_id), clinical_resource_ids=resources_in_room(registry, room_id),
        transport_interface_ids=transport_interfaces_for_room(registry, room_id),
    )


@dataclass(frozen=True)
class BatchQueryResult:
    batch_id: str
    radionuclide_id: str | None
    source: BatchSourceBinding | None
    patient_ids: tuple[str, ...]
    payload_ids: tuple[str, ...]


def describe_batch(registry: EntityBindingRegistry, batch_id: str) -> BatchQueryResult:
    """Section 28/40: batch-centered queryability -- no new production
    calculation, only resolution of already-bound facts."""
    patient_ids = patients_for_batch(registry, batch_id)
    radionuclide_id = registry.patient_radionuclide.get(patient_ids[0]) if patient_ids else None
    return BatchQueryResult(
        batch_id=batch_id, radionuclide_id=radionuclide_id, source=registry.batch_source.get(batch_id),
        patient_ids=patient_ids, payload_ids=payloads_for_batch(registry, batch_id),
    )


@dataclass(frozen=True)
class PatientTraceabilityChain:
    """Section 25/27/38: PATIENT -> RADIONUCLIDE -> BATCH/SOURCE -> CYCLOTRON
    OR GENERATOR -> PAYLOAD -> MISSION -> TRANSPORT RESOURCE -> DESTINATION
    CLINICAL RESOURCE -> SCANNER. Any unresolved hop reports `UNRESOLVED`
    with a reason -- never fabricated."""

    patient_id: str
    radionuclide_id: str | None
    radionuclide_status: str
    batch_id: str | None
    batch_status: str
    source_type: str | None
    source_equipment_id: str | None
    source_room_id: str | None
    payload_id: str | None
    payload_status: str
    mission_id: str | None
    mission_status: str
    transport_resource_id: str | None
    transport_resource_status: str
    scanner_id: str | None
    scanner_room_id: str | None
    scanner_status: str


def resolve_patient_radionuclide_chain(registry: EntityBindingRegistry, patient_id: str) -> PatientTraceabilityChain:
    """Section 25/38: traceability OVER existing records only -- computes no
    new values."""
    radionuclide_id = radionuclide_for_patient(registry, patient_id)
    batch_id = batch_for_patient(registry, patient_id)
    source = registry.batch_source.get(batch_id) if batch_id is not None else None
    source_equipment_id = (source.cyclotron_id or source.generator_id) if source is not None else None
    source_room_id = None
    if source is not None and source.cyclotron_id is not None:
        source_room_id = room_for_cyclotron(registry, source.cyclotron_id)
    elif source is not None and source.generator_id is not None:
        source_room_id = room_for_generator(registry, source.generator_id)

    payload_candidates = payloads_for_batch(registry, batch_id) if batch_id is not None else ()
    payload_id = next((p for p in payload_candidates if patient_id in patients_for_payload(registry, p)), None)
    mission_id = mission_for_payload(registry, payload_id) if payload_id is not None else None
    transport_resource_id = transport_resource_for_mission(registry, mission_id) if mission_id is not None else None
    scanner_id = scanner_for_patient(registry, patient_id)
    scanner_room_id = room_for_scanner(registry, scanner_id) if scanner_id is not None else None

    return PatientTraceabilityChain(
        patient_id=patient_id,
        radionuclide_id=radionuclide_id, radionuclide_status="RESOLVED" if radionuclide_id is not None else UNRESOLVED,
        batch_id=batch_id, batch_status="RESOLVED" if batch_id is not None else UNRESOLVED,
        source_type=(source.source_type if source is not None else None),
        source_equipment_id=source_equipment_id, source_room_id=source_room_id,
        payload_id=payload_id, payload_status="RESOLVED" if payload_id is not None else UNRESOLVED,
        mission_id=mission_id,
        mission_status="RESOLVED" if mission_id is not None else (
            "UNRESOLVED: no TransportMission bound to this payload -- ProductionClinicalPatientTrace tracks "
            "delivery_job_id (a distinct scheduler-internal identifier), and no cross-reference exists in the "
            "repository today between that identifier and general_oncology_logistics.TransportMission.mission_id"
            if payload_id is not None else UNRESOLVED
        ),
        transport_resource_id=transport_resource_id,
        transport_resource_status="RESOLVED" if transport_resource_id is not None else UNRESOLVED,
        scanner_id=scanner_id, scanner_room_id=scanner_room_id,
        scanner_status="RESOLVED" if scanner_id is not None else UNRESOLVED,
    )


# ---------------------------------------------------------------------------
# Serialization (section 31) -- reuses plain dict/list JSON shapes, never
# relies on Python object identity.
# ---------------------------------------------------------------------------


def _serialize_one_to_many(index: _OneToManyIndex) -> dict:
    return {"forward": dict(index.forward)}


def _deserialize_one_to_many(data: dict) -> _OneToManyIndex:
    index = _OneToManyIndex()
    for child, parent in data["forward"].items():
        index.bind(child, parent)
    return index


def _serialize_many_to_many(index: _ManyToManyIndex) -> dict:
    return {"forward": {a: sorted(bs) for a, bs in index.forward.items()}}


def _deserialize_many_to_many(data: dict) -> _ManyToManyIndex:
    index = _ManyToManyIndex()
    for a, bs in data["forward"].items():
        for b in bs:
            index.bind(a, b)
    return index


def _serialize_batch_source(binding: BatchSourceBinding) -> dict:
    return {"batch_id": binding.batch_id, "source_type": binding.source_type, "cyclotron_id": binding.cyclotron_id, "generator_id": binding.generator_id}


def serialize_entity_bindings(registry: EntityBindingRegistry) -> dict:
    return {
        "patient_room": _serialize_one_to_many(registry.patient_room),
        "patient_radionuclide": dict(registry.patient_radionuclide),
        "patient_batch": _serialize_one_to_many(registry.patient_batch),
        "batch_source": {k: _serialize_batch_source(v) for k, v in registry.batch_source.items()},
        "batch_cyclotron": _serialize_one_to_many(registry.batch_cyclotron),
        "batch_or_supply_generator": _serialize_one_to_many(registry.batch_or_supply_generator),
        "batch_payload": _serialize_one_to_many(registry.batch_payload),
        "payload_patient": _serialize_many_to_many(registry.payload_patient),
        "mission_payload": _serialize_one_to_many(registry.mission_payload),
        "mission_transport_resource": _serialize_one_to_many(registry.mission_transport_resource),
        "equipment_room": _serialize_one_to_many(registry.equipment_room),
        "equipment_kind": dict(registry.equipment_kind),
        "clinical_resource_room": _serialize_one_to_many(registry.clinical_resource_room),
        "patient_scanner": _serialize_one_to_many(registry.patient_scanner),
        "transport_interface_room": _serialize_one_to_many(registry.transport_interface_room),
        "interface_kind": dict(registry.interface_kind),
    }


def deserialize_entity_bindings(data: dict) -> EntityBindingRegistry:
    return EntityBindingRegistry(
        patient_room=_deserialize_one_to_many(data["patient_room"]), patient_radionuclide=dict(data["patient_radionuclide"]),
        patient_batch=_deserialize_one_to_many(data["patient_batch"]),
        batch_source={k: BatchSourceBinding(**v) for k, v in data["batch_source"].items()},
        batch_cyclotron=_deserialize_one_to_many(data["batch_cyclotron"]),
        batch_or_supply_generator=_deserialize_one_to_many(data["batch_or_supply_generator"]),
        batch_payload=_deserialize_one_to_many(data["batch_payload"]), payload_patient=_deserialize_many_to_many(data["payload_patient"]),
        mission_payload=_deserialize_one_to_many(data["mission_payload"]),
        mission_transport_resource=_deserialize_one_to_many(data["mission_transport_resource"]),
        equipment_room=_deserialize_one_to_many(data["equipment_room"]), equipment_kind=dict(data["equipment_kind"]),
        clinical_resource_room=_deserialize_one_to_many(data["clinical_resource_room"]),
        patient_scanner=_deserialize_one_to_many(data["patient_scanner"]),
        transport_interface_room=_deserialize_one_to_many(data["transport_interface_room"]), interface_kind=dict(data["interface_kind"]),
    )

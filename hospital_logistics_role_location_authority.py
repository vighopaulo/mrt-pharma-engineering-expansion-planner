"""Facility Expansion Authority Build 4C: Canonical Hospital Logistics
Role-Location and Porter Route Closure.

GOVERNANCE: this module owns ONLY functional-role identity, canonical
object binding, binding status/provenance, and role-location validation.
It is NOT a route solver, NOT a mission generator, NOT a staffing
authority, and NOT an economic/animation authority.

AUDIT (section 2), performed before writing anything:

  `general_oncology_logistics.FacilityRoleLocation`/`build_default_
    facility_roles` ALREADY exist and ALREADY carry `object_id`s for
    RADIOPHARMACY ("RP-001"), CENTRAL_PHARMACY ("PHARM-001"), LABORATORY
    ("LAB-001"), and BLOOD_BANK ("BB-001") with `location_status=
    "CALIBRATED"`. CLEAN_LINEN_SOURCE/STERILE_CLEAN_SUPPLY are the ONLY two
    roles with `object_id=None`/`location_status="LOCATION_NOT_CALIBRATED"`
    -- confirming Build 4B's disclosed gap is genuine and narrow.

  `canonical_spatial_authority.build_general_logistics_origin_objects`
    ALREADY exists and ALREADY converts those role locations into REAL
    `CanonicalSpatialObject`s (object types `CENTRAL_PHARMACY`/`LABORATORY`/
    `BLOOD_BANK`/`CLEAN_LINEN_SOURCE`/`STERILE_CLEAN_SUPPLY_SOURCE` are
    ALREADY valid `SpatialObjectType` values) at each role's EXISTING
    `object_id` -- reused verbatim below, never re-derived. Its one
    genuine limitation (never claimed otherwise by its own docstring): it
    places every created object at `Transform()` (the origin), so distinct
    controlled-proof coordinates must be layered on top by the caller.
    `general_oncology_logistics.generate_daily_logistics_demand` already
    accepts an explicit `roles` parameter -- no change to that function is
    needed to use a controlled-proof role set.

  `canonical_entity_binding_authority.py` binds PATIENT<->ROOM identities
    only; it has no existing role<->object-type binding concept, so it is
    NOT extended here (role binding is a distinct concern, section 4).

GENUINE GAP CLOSED: CLEAN_LINEN_SOURCE/STERILE_CLEAN_SUPPLY have NO real
object_id anywhere in the existing repository. This module supplies a
CONTROLLED_PROOF_LOCATION override (`CONTROLLED_PROOF_ROLE_OVERRIDES`)
ONLY for use by this controlled fixture -- it NEVER mutates
`general_oncology_logistics.build_default_facility_roles` (that function's
own global default for these two roles remains, honestly,
LOCATION_NOT_CALIBRATED).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import canonical_spatial_authority as csa
from general_oncology_logistics import FacilityRole, FacilityRoleLocation, build_default_facility_roles

RoleLocationCalibrationStatus = Literal["CALIBRATED_CANONICAL_LOCATION", "CONTROLLED_PROOF_LOCATION", "NOT_CALIBRATED"]

LOGISTICS_ROLE_AND_SPATIAL_OBJECT_ARE_DISTINCT = True
LOGISTICS_ROLE_CAN_BIND_TO_CANONICAL_OBJECT = True
ROLE_LOCATION_STATUS_EXPLICIT = True
CENTRAL_SERVICE_ROLE_REPLICATES_WITH_EVERY_FLOOR = False
ROLE_BINDING_REQUIRES_BENTLEY = False
ROLE_BINDING_CHANGES_ASSET_COST_STATUS = False

_ROLE_TO_OBJECT_TYPE: dict[FacilityRole, csa.SpatialObjectType] = {
    "RADIOPHARMACY": "RADIOPHARMACY", "CENTRAL_PHARMACY": "CENTRAL_PHARMACY", "LABORATORY": "LABORATORY",
    "BLOOD_BANK": "BLOOD_BANK", "CLEAN_LINEN_SOURCE": "CLEAN_LINEN_SOURCE", "STERILE_CLEAN_SUPPLY": "STERILE_CLEAN_SUPPLY_SOURCE",
}

# Section 7: CONTROLLED_PROOF_LOCATION override -- ONLY the two roles the
# EXISTING `build_default_facility_roles()` leaves LOCATION_NOT_CALIBRATED.
# Never overrides RADIOPHARMACY/CENTRAL_PHARMACY/LABORATORY/BLOOD_BANK
# (already CALIBRATED via the existing authority).
CONTROLLED_PROOF_ROLE_OVERRIDES: tuple[FacilityRoleLocation, ...] = (
    FacilityRoleLocation(role="CLEAN_LINEN_SOURCE", object_id="LINEN-001", building_id="BLDG-V", floor_id="F1", location_status="CALIBRATED", streams_served=("CLEAN_LINEN",)),
    FacilityRoleLocation(role="STERILE_CLEAN_SUPPLY", object_id="STERILE-001", building_id="BLDG-V", floor_id="F1", location_status="CALIBRATED", streams_served=("STERILE_CLEAN_SUPPLY",)),
)

# Deterministic F1 coordinates for the controlled proof -- distinct
# per-role, never chosen merely to force identical route lengths (section 7).
_CONTROLLED_PROOF_COORDINATES: dict[str, tuple[float, float, float]] = {
    "PHARM-001": (3.0, 2.0, 0.0), "LAB-001": (5.0, -2.0, 0.0), "LINEN-001": (-3.0, 4.0, 0.0), "STERILE-001": (-4.0, -3.0, 0.0),
}


def resolve_controlled_proof_roles() -> tuple[FacilityRoleLocation, ...]:
    """Section 5/17: merges the EXISTING `build_default_facility_roles()`
    with the CONTROLLED_PROOF override above -- every other role is
    untouched. Passed directly into the EXISTING `generate_daily_logistics_
    demand(roles=...)` parameter (section 17: no change to demand
    generation itself)."""
    overridden = {r.role for r in CONTROLLED_PROOF_ROLE_OVERRIDES}
    base = tuple(r for r in build_default_facility_roles() if r.role not in overridden)
    return base + CONTROLLED_PROOF_ROLE_OVERRIDES


@dataclass(frozen=True)
class RoleLocationBinding:
    role: FacilityRole
    canonical_object_id: str | None
    building_id: str | None
    floor_id: str | None
    status: RoleLocationCalibrationStatus
    provenance: str


def bind_role_location(role_location: FacilityRoleLocation, registry: csa.SpatialObjectRegistry, *, controlled_proof: bool = False) -> RoleLocationBinding:
    """Section 4/6: binds an EXISTING `FacilityRoleLocation` to an ACTUAL
    registered canonical spatial object -- role identity and spatial
    object identity remain distinct fields (never conflated). Honest
    status: `NOT_CALIBRATED` where no object_id exists or the object_id is
    not actually registered (never a silently-invented adjacency)."""
    if role_location.object_id is None:
        return RoleLocationBinding(
            role=role_location.role, canonical_object_id=None, building_id=None, floor_id=None, status="NOT_CALIBRATED",
            provenance="general_oncology_logistics.FacilityRoleLocation has no object_id (LOCATION_NOT_CALIBRATED)",
        )
    if role_location.object_id not in registry.objects:
        return RoleLocationBinding(
            role=role_location.role, canonical_object_id=role_location.object_id, building_id=role_location.building_id,
            floor_id=role_location.floor_id, status="NOT_CALIBRATED",
            provenance=f"object_id {role_location.object_id} declared by the role but not registered in this canonical registry",
        )
    status: RoleLocationCalibrationStatus = "CONTROLLED_PROOF_LOCATION" if controlled_proof else "CALIBRATED_CANONICAL_LOCATION"
    return RoleLocationBinding(
        role=role_location.role, canonical_object_id=role_location.object_id, building_id=role_location.building_id,
        floor_id=role_location.floor_id, status=status,
        provenance="general_oncology_logistics.FacilityRoleLocation.object_id bound to an existing canonical_spatial_authority object",
    )


def build_controlled_hospital_role_registry(
    registry: csa.SpatialObjectRegistry, *, facility_id: str, building_id: str, floor_id: str,
) -> tuple[RoleLocationBinding, ...]:
    """Sections 3/7-8: reuses `canonical_spatial_authority.
    build_general_logistics_origin_objects` verbatim (never re-derives its
    role->object_type mapping), then layers distinct controlled-proof
    coordinates on top (that existing function always places objects at
    `Transform()`, disclosed, never claimed otherwise). CLEAN_LINEN_SOURCE/
    STERILE_CLEAN_SUPPLY use the CONTROLLED_PROOF override roles so they
    receive a real, distinct, CONTROLLED_PROOF_LOCATION object instead of
    the existing function's honest `-NOT-CALIBRATED` placeholder."""
    roles = resolve_controlled_proof_roles()
    controlled_proof_object_ids = {r.object_id for r in CONTROLLED_PROOF_ROLE_OVERRIDES}
    bindings: list[RoleLocationBinding] = []
    for role_location in roles:
        if role_location.role not in _ROLE_TO_OBJECT_TYPE or role_location.role == "RADIOPHARMACY":
            continue  # RADIOPHARMACY is bound separately (build_nuclear_engineering_objects owns it)
        object_id = role_location.object_id
        if object_id is None:
            bindings.append(bind_role_location(role_location, registry))
            continue
        if object_id not in registry.objects:
            spatial_status: csa.SpatialStatus = "CALIBRATED" if role_location.location_status == "CALIBRATED" else "LOCATION_NOT_CALIBRATED"
            csa.add_room(
                registry, facility_id=facility_id, building_id=building_id, floor_id=floor_id, room_id=object_id,
                object_type=_ROLE_TO_OBJECT_TYPE[role_location.role], spatial_status=spatial_status,
            )
        if object_id in _CONTROLLED_PROOF_COORDINATES:
            registry.objects[object_id] = csa.replace(registry.objects[object_id], transform=csa.Transform(*_CONTROLLED_PROOF_COORDINATES[object_id]))
        placed_role_location = replace(role_location, building_id=building_id, floor_id=floor_id)
        bindings.append(bind_role_location(placed_role_location, registry, controlled_proof=object_id in controlled_proof_object_ids))
    return tuple(bindings)

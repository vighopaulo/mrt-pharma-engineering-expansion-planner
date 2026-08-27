"""BIM/iTwin Phase 2B: narrow Bentley-live-element -> existing canonical
object binding helper.

GOVERNANCE: this module reuses (never duplicates) `canonical_spatial_authority`'s
`SpatialObjectRegistry`/`CanonicalSpatialObject`/`ExternalReference`. It
contains NO Bentley HTTP calls, NO route/economic/clinical logic -- pure
normalization+binding, exactly like `canonical_spatial_authority`'s existing
`normalize_itwin_import` (Phase 1), but for a SINGLE already-retrieved live
element rather than a bulk import.

IDENTITY GOVERNANCE (sections 8-10): a Bentley external element identity is
NEVER canonical identity. Binding always resolves through
`element.canonical_reference_value` (the synchronized IFC `ObjectType`) to an
ALREADY-EXISTING `mrtway_object_id` in the supplied registry -- if that
canonical object does not already exist, this module fails explicitly
(never fabricates a new canonical room/equipment identity merely because
Bentley supplied one).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import canonical_spatial_authority as csa
from bentley_itwin_client import BentleyLiveElementRecord

BentleyBindingResult = Literal[
    "BOUND_EXISTING", "MISSING_CANONICAL_REFERENCE", "UNKNOWN_CANONICAL_ROOM", "UNKNOWN_ENGINEERING_OBJECT",
]


@dataclass(frozen=True)
class BentleyLiveBindingOutcome:
    """One deterministic outcome per live element -- never a silent guess
    (mirrors `canonical_spatial_authority.BentleyBindingOutcome`'s Phase 1
    governance, applied here to a single live-retrieved element)."""

    element: BentleyLiveElementRecord
    result: BentleyBindingResult
    mrtway_object_id: str | None
    detail: str = ""


def _resolve_existing_canonical_object(
    registry: csa.SpatialObjectRegistry, canonical_reference_value: str,
) -> csa.CanonicalSpatialObject | None:
    """Section 8: direct `mrtway_object_id` match first (the repository's own
    convention for rooms and for equipment built via
    `build_nuclear_engineering_objects`/Phase 1 `normalize_itwin_import`,
    where `mrtway_object_id == engineering_object_id`); falls back to a scan
    by `engineering_object_id` for a registry built under a different
    convention. Never resolves by name/label/geometry proximity."""
    direct = registry.objects.get(canonical_reference_value)
    if direct is not None:
        return direct
    for obj in registry.objects.values():
        if obj.engineering_object_id == canonical_reference_value:
            return obj
    return None


def bind_live_bentley_element(
    registry: csa.SpatialObjectRegistry, element: BentleyLiveElementRecord,
) -> BentleyLiveBindingOutcome:
    """Sections 8-10: resolves an ALREADY-EXISTING canonical object via
    `element.canonical_reference_value` and attaches/updates the Bentley
    `ExternalReference` on that SAME object -- idempotent by construction
    (repeated calls for the same `canonical_reference_value` update the SAME
    object; a changed `external_element_id`/`external_global_id` across a
    future synchronization updates the binding without creating a second
    canonical object, section 9). `registry` MUST be a `WhatIfSpatialState`'s
    registry, never a `LockedSpatialState`'s (section 14) -- the exact same
    caller responsibility already established for `normalize_itwin_import`
    and `apply_changeset`."""
    if element.canonical_reference_value is None:
        return BentleyLiveBindingOutcome(
            element=element, result="MISSING_CANONICAL_REFERENCE", mrtway_object_id=None,
            detail="Bentley element carries no canonical_reference_value (ObjectType) -- refusing to fabricate an identity",
        )
    canonical_reference_value = element.canonical_reference_value
    existing = _resolve_existing_canonical_object(registry, canonical_reference_value)
    if existing is None:
        kind: BentleyBindingResult = "UNKNOWN_CANONICAL_ROOM" if element.element_class.lower() == "ifcspace" else "UNKNOWN_ENGINEERING_OBJECT"
        return BentleyLiveBindingOutcome(
            element=element, result=kind, mrtway_object_id=None,
            detail=f"no existing canonical object {canonical_reference_value!r} found in the supplied registry -- Bentley may not fabricate one",
        )
    updated_external_reference = replace(
        existing.external_reference, itwin_element_id=element.external_element_id,
        external_project_id=element.external_project_id, external_model_id=element.external_model_id,
        change_reference=element.change_reference if element.change_reference is not None else existing.external_reference.change_reference,
    )
    registry.objects[existing.mrtway_object_id] = replace(existing, external_reference=updated_external_reference)
    return BentleyLiveBindingOutcome(
        element=element, result="BOUND_EXISTING", mrtway_object_id=existing.mrtway_object_id, detail="",
    )

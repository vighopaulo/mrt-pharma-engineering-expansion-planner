"""Transport Spatial Authority Build 1: Canonical Transport Technology Identity.

GOVERNANCE: this module owns ONLY semantic technology identity, naming, and
legacy-identifier normalization. It is NOT a routing authority, NOT a cost
authority, NOT a mission authority, NOT a simulation authority, and NOT a
visualization authority -- it imports nothing from any of those, and
implements none of their logic.

Existing `conventional_transport_authority.TechnologyType`/
`TECHNOLOGY_STREAM_COMPATIBILITY` and `canonical_spatial_authority.
TransportMode` are UNCHANGED by this module -- it sits ALONGSIDE them as a
semantic-normalization/reporting layer, never replacing their literal
values. The legacy identifier `"AGV_AMR"` remains fully accepted at
internal/serialization boundaries (section 5); only its CANONICAL SEMANTIC
MEANING is redirected to RGHT via `normalize_transport_technology`.

TAXONOMY (per the preceding read-only audit): the repository's existing
`AGV_AMR` economics/infrastructure (vehicle + per-floor docking CapEx,
"Telelift-class" cost basis) are materially closer to a dedicated
rail-guided hospital carrier technology class than to a true free-roaming
floor AGV/AMR (no floor graph/path-planning/collision/charging model exists
anywhere). This module formalizes that distinction:

    RGHT             = Rail-Guided Hospital Transport (the legacy AGV_AMR
                        economics/infrastructure's actual semantic meaning)
    FLOOR_AGV_AMR    = the TRUE free-roaming technology class -- distinct,
                        remains NOT_IMPLEMENTED.

Never use a commercial vendor brand (Telelift/Swisslog/UniCar) as the
canonical technology name (section 2/19) -- vendor names may appear only in
provenance/comparator documentation.
"""

from __future__ import annotations

from typing import Literal

RAIL_GUIDED_HOSPITAL_TRANSPORT = "RGHT"
"""Section 2: canonical technology-class identifier for the conventional
dedicated rail/track-guided hospital carrier technology class."""

RGHT_LABEL = "RAIL_GUIDED_HOSPITAL_TRANSPORT"
"""Section 2: canonical human-readable label for RGHT."""

FLOOR_AGV_AMR = "FLOOR_AGV_AMR"
"""Section 6: the TRUE free-roaming floor AGV/AMR technology class --
deliberately DISTINCT from RGHT. `RGHT != FLOOR_AGV_AMR` is a required
invariant."""

FloorAgvImplementationStatus = Literal["NOT_IMPLEMENTED", "IMPLEMENTED"]

FLOOR_AGV_AMR_IMPLEMENTATION_STATUS: FloorAgvImplementationStatus = "NOT_IMPLEMENTED"
"""Section 6: remains NOT_IMPLEMENTED unless the repository gains a
truthful, separately-calibrated free-roaming floor-navigation model of its
own -- never silently upgraded to reuse RGHT's/PTS's/MRT's assumptions."""

RGHT_ECONOMIC_STATUS = "CONTROLLED_ENGINEERING_ASSUMPTION"
RGHT_VENDOR_QUOTE_CALIBRATION = "NOT_CALIBRATED_TO_CURRENT_VENDOR_QUOTE"
RGHT_VENDOR_COMPARATOR_BASIS = "TELELIFT_CLASS_REFERENCE"
"""Section 4/22: preserved economic-provenance status. The EXISTING legacy
`AGV_AMR` planning CapEx (`conventional_transport_authority.
DEFAULT_AGV_MODEL`) was partially justified using a Telelift-class
commercial comparator -- documentation/provenance ONLY, never a
vendor-specific engineering assumption. No proprietary dimensions, motor
values, controls, or switch logic are encoded anywhere in this repository
for RGHT (section 3)."""

ACTIVE_TRANSPORT_TECHNOLOGY_CLASSES = ("MRT", RAIL_GUIDED_HOSPITAL_TRANSPORT, "PNEUMATIC_TUBE", "MANUAL_PORTER")
"""Section 7: the active study-scope technology classes for the current
four-architecture comparative study. `FLOOR_AGV_AMR` is intentionally
absent -- outside current active study scope."""

_LEGACY_TO_CANONICAL: dict[str, str] = {
    "AGV_AMR": RAIL_GUIDED_HOSPITAL_TRANSPORT,
    "PORTER_CART": "PORTER_CART",
    "MANUAL_PORTER": "MANUAL_PORTER",
    "WALKING_PORTER": "MANUAL_PORTER",
    "PNEUMATIC_TUBE": "PNEUMATIC_TUBE",
    "MRT": "MRT",
    "PATIENT_MOVEMENT": "PATIENT_MOVEMENT",
    RAIL_GUIDED_HOSPITAL_TRANSPORT: RAIL_GUIDED_HOSPITAL_TRANSPORT,
    FLOOR_AGV_AMR: FLOOR_AGV_AMR,
}
"""Section 5: the ONE authoritative compatibility mapping -- never scatter
ad-hoc string replacements across the repository. Only the legacy `AGV_AMR`
identifier actually changes canonical meaning (-> RGHT); every other
existing identifier passes through unchanged, never silently
reinterpreted."""


def normalize_transport_technology(identifier: str) -> str:
    """Section 5: `normalize_transport_technology("AGV_AMR") == "RGHT"`.
    Unknown identifiers pass through UNCHANGED (never fabricates a mapping)
    -- callers remain responsible for validating identifiers against their
    own existing enums (e.g. `conventional_transport_authority.
    TechnologyType`, `canonical_spatial_authority.TransportMode`)."""
    return _LEGACY_TO_CANONICAL.get(identifier, identifier)


def is_vendor_brand_name(identifier: str) -> bool:
    """Section 2/19/23: explicit negative check -- commercial vendor brands
    must never be used as the canonical technology name."""
    return identifier.strip().upper() in {"TELELIFT", "SWISSLOG", "UNICAR"}

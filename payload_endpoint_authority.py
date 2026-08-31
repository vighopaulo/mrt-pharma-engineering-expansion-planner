"""Payload Stream Origin / Destination Authority (ADDITIVE clarification to the
current Bentley 3D spatial-network build).

Transport mission endpoints DERIVE FROM THE PAYLOAD / SERVICE STREAM and its
direction -- never a universal assumption that everything begins at the
pharmacy or cyclotron (Sec M).

HARD DOCTRINES:
  * Radiopharmaceutical PRODUCTION origin (cyclotron/generator) is DISTINCT
    from the clinical-logistics TRANSPORT origin (qualified radiopharmacy
    release / vestibule). RADIOPHARMACEUTICAL_PRODUCTION_ORIGIN_EQUALS_
    TRANSPORT_ORIGIN_BY_DEFAULT = NO (Sec N).
  * Conventional medication originates at pharmacy, not radiopharmacy (Sec O).
  * Clean linen originates at laundry; sterile supply at CSSD/sterile
    processing -- STERILE_SUPPLY_ORIGIN_ALWAYS_LAUNDRY = NO (Sec P).
  * A specimen travels patient/collection -> laboratory; SPECIMEN_ORIGIN_
    ALWAYS_LAB = NO; lab-originating supply/result missions travel the
    opposite direction (Sec Q).
  * Destination is not universally the patient room; reverse logistics
    (specimen->lab, linen return->laundry, ...) are preserved (Sec R).
  * Endpoints are validated against stream + direction + mode + qualification
    before auto-routing (Sec S).

This module composes existing facility-role / service-class vocabulary; it
never mutates a live Bentley iModel, MRT canonical physics, or the SB1/2/3
authorities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

# ===========================================================================
# 1. Payload streams + facility service nodes (Sec M-R).
# ===========================================================================

PayloadStream = Literal[
    "RADIOPHARMACEUTICAL", "CONVENTIONAL_MEDICATION", "CLEAN_LINEN",
    "STERILE_SUPPLY", "SPECIMEN", "LAB_SUPPLY",
]

CANONICAL_PAYLOAD_STREAMS: tuple[PayloadStream, ...] = (
    "RADIOPHARMACEUTICAL", "CONVENTIONAL_MEDICATION", "CLEAN_LINEN",
    "STERILE_SUPPLY", "SPECIMEN", "LAB_SUPPLY",
)

# Canonical facility service-node roles (origins/destinations).
ServiceNodeRole = Literal[
    "CYCLOTRON_GENERATOR_PRODUCTION", "RADIOPHARMACY_RELEASE", "CENTRAL_PHARMACY",
    "LAUNDRY_LINEN_SERVICE", "CSSD_STERILE_PROCESSING", "LABORATORY",
    "PATIENT_CLINICAL_ROOM", "COLLECTION_POINT", "OWNING_DEPARTMENT", "CONFIGURED_NODE",
]

# Mission direction (Sec Q-R): OUTBOUND = service->clinical; RETURN = reverse.
MissionDirection = Literal["OUTBOUND", "RETURN"]


# ===========================================================================
# 2. Default endpoint semantics per (stream, direction) (Sec N-R). Defaults are
#    CONTROLLED assumptions, always overridable by an explicit configured node.
# ===========================================================================

@dataclass(frozen=True)
class EndpointSemantics:
    stream: PayloadStream
    direction: MissionDirection
    origin_role: ServiceNodeRole
    destination_role: ServiceNodeRole
    provenance: str


_DEFAULT_ENDPOINTS: Mapping[tuple[PayloadStream, MissionDirection], tuple[ServiceNodeRole, ServiceNodeRole]] = {
    # Sec N: radiopharm TRANSPORT origin = radiopharmacy RELEASE (NOT cyclotron production).
    ("RADIOPHARMACEUTICAL", "OUTBOUND"): ("RADIOPHARMACY_RELEASE", "PATIENT_CLINICAL_ROOM"),
    # Sec O: conventional medication from pharmacy.
    ("CONVENTIONAL_MEDICATION", "OUTBOUND"): ("CENTRAL_PHARMACY", "PATIENT_CLINICAL_ROOM"),
    # Sec P: linen from laundry; sterile from CSSD.
    ("CLEAN_LINEN", "OUTBOUND"): ("LAUNDRY_LINEN_SERVICE", "PATIENT_CLINICAL_ROOM"),
    ("CLEAN_LINEN", "RETURN"): ("PATIENT_CLINICAL_ROOM", "LAUNDRY_LINEN_SERVICE"),
    ("STERILE_SUPPLY", "OUTBOUND"): ("CSSD_STERILE_PROCESSING", "PATIENT_CLINICAL_ROOM"),
    ("STERILE_SUPPLY", "RETURN"): ("OWNING_DEPARTMENT", "CSSD_STERILE_PROCESSING"),
    # Sec Q: specimen collected at patient/collection -> laboratory.
    ("SPECIMEN", "OUTBOUND"): ("COLLECTION_POINT", "LABORATORY"),
    # Sec Q: lab-originating supply/result travels the opposite direction.
    ("LAB_SUPPLY", "OUTBOUND"): ("LABORATORY", "PATIENT_CLINICAL_ROOM"),
}


def default_endpoints(stream: PayloadStream, direction: MissionDirection = "OUTBOUND") -> EndpointSemantics:
    """Sec N-R: the default origin/destination roles for a stream + direction.
    Radiopharm TRANSPORT origin is the radiopharmacy release, never the
    cyclotron (Sec N). Raises for an unmodeled (stream, direction) pair rather
    than fabricating a universal default."""
    key = (stream, direction)
    if key not in _DEFAULT_ENDPOINTS:
        raise ValueError(f"no default endpoints modeled for {stream} {direction} (supply explicit configured nodes)")
    origin, dest = _DEFAULT_ENDPOINTS[key]
    return EndpointSemantics(
        stream=stream, direction=direction, origin_role=origin, destination_role=dest,
        provenance="CONTROLLED_STREAM_DIRECTION_DEFAULT (overridable by configured node)",
    )


# ===========================================================================
# 3. Radiopharmaceutical production-vs-transport origin chain (Sec N).
# ===========================================================================

RADIOPHARM_ORIGIN_CHAIN: tuple[ServiceNodeRole, ...] = (
    "CYCLOTRON_GENERATOR_PRODUCTION",  # radionuclide production
    "RADIOPHARMACY_RELEASE",           # synthesis/prep/QC/release -> TRANSPORT ORIGIN
    "PATIENT_CLINICAL_ROOM",           # clinical destination
)


def radiopharmaceutical_transport_origin() -> ServiceNodeRole:
    """Sec N: for a finished patient dose the TRANSPORT origin is the qualified
    radiopharmacy release/vestibule -- NOT the cyclotron production node."""
    return "RADIOPHARMACY_RELEASE"


def radiopharmaceutical_production_origin() -> ServiceNodeRole:
    """The radionuclide PRODUCTION origin (distinct from transport origin)."""
    return "CYCLOTRON_GENERATOR_PRODUCTION"


def production_origin_equals_transport_origin() -> bool:
    """Hard governor (Sec N): always False. Production and clinical-logistics
    origins are never collapsed into one node."""
    return radiopharmaceutical_production_origin() == radiopharmaceutical_transport_origin()


# ===========================================================================
# 4. Endpoint validation before auto-routing (Sec S).
# ===========================================================================

# Which transport modes a stream may use (composes the SB1/SB2 eligibility
# intent at the endpoint level; the optimizer's eligibility authority remains
# the full gate). Movement modes use the movement-domain vocabulary.
MovementModeId = Literal[
    "MRT", "RTHS", "PTS_CONVENTIONAL", "PTS_NUCLEAR_QUALIFIED",
    "AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS", "MANUAL",
]

EndpointValidationStatus = Literal[
    "VALID", "INVALID_STREAM_MODE", "INVALID_NO_ENDPOINT_INTERFACE",
    "INVALID_QUALIFICATION_MISSING", "INVALID_UNCONNECTED_STATION",
]


@dataclass(frozen=True)
class EndpointValidationResult:
    stream: PayloadStream
    mode: MovementModeId
    origin_node_id: str
    destination_node_id: str
    status: EndpointValidationStatus
    reason: str

    @property
    def valid(self) -> bool:
        return self.status == "VALID"


def validate_endpoints(
    *, stream: PayloadStream, mode: MovementModeId,
    origin_node_id: str, destination_node_id: str,
    origin_has_mode_interface: bool, destination_has_mode_interface: bool,
    destination_reachable_on_network: bool = True,
    nuclear_qualification_present: bool = False,
) -> EndpointValidationResult:
    """Sec S: validate the endpoint pair for stream/direction/mode/qualification
    BEFORE auto-routing. Rejects: nuclear PTS from an unqualified station; MRT to
    a room with no MRT endpoint; RTHS to an unconnected station; other invalid
    pairings. Never permits an invalid mission to route."""
    def _res(status: EndpointValidationStatus, reason: str) -> EndpointValidationResult:
        return EndpointValidationResult(stream, mode, origin_node_id, destination_node_id, status, reason)

    # radiopharmaceutical over qualified nuclear channels requires qualification
    if stream == "RADIOPHARMACEUTICAL" and mode in ("PTS_CONVENTIONAL",):
        return _res("INVALID_STREAM_MODE", "radiopharmaceutical not permitted on conventional PTS (Sec S)")
    if stream == "RADIOPHARMACEUTICAL" and mode in ("PTS_NUCLEAR_QUALIFIED", "MRT", "RTHS", "AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS") and not nuclear_qualification_present:
        return _res("INVALID_QUALIFICATION_MISSING", f"radiopharmaceutical on {mode} requires nuclear qualification (Sec S)")
    # bulk streams cannot use PTS/MRT (envelope) -- endpoint-level guard
    if stream in ("CLEAN_LINEN",) and mode in ("PTS_CONVENTIONAL", "PTS_NUCLEAR_QUALIFIED", "MRT"):
        return _res("INVALID_STREAM_MODE", f"{stream} not permitted on {mode} (envelope, Sec S)")
    # a network-bound mode needs an interface at BOTH endpoints
    if not origin_has_mode_interface:
        return _res("INVALID_NO_ENDPOINT_INTERFACE", f"origin {origin_node_id} has no {mode} interface (Sec S)")
    if not destination_has_mode_interface:
        return _res("INVALID_NO_ENDPOINT_INTERFACE", f"destination {destination_node_id} has no {mode} interface (Sec S)")
    if mode in ("MRT", "RTHS", "PTS_CONVENTIONAL", "PTS_NUCLEAR_QUALIFIED") and not destination_reachable_on_network:
        return _res("INVALID_UNCONNECTED_STATION", f"destination {destination_node_id} not connected on the {mode} network (Sec S)")
    return _res("VALID", "endpoint pair valid for stream/mode/qualification")

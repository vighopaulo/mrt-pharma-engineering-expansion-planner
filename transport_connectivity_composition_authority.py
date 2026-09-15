"""MRT Pharma Build 2A: Canonical Transport Automatic-Connectivity Composition
Authority.

GOVERNANCE / ONE-AUTHORITY-PER-CONCEPT: this module introduces NO new physics,
NO new economics, NO new routing engine, NO new eligibility engine, and NO new
per-mode transport-unit equipment. It is a THIN, ADDITIVE COMPOSITION seam that
answers exactly the mission-first question Build 2A requires:

    LOGISTICS MISSION
      -> WHICH MODES ARE ELIGIBLE?        (transport_mode_eligibility_authority)
      -> WHERE ARE THE ENDPOINTS?         (payload_endpoint_authority roles ->
                                           caller-supplied canonical object ids)
      -> IS THERE A REAL CALIBRATED ROUTE? (transport_mission_route_bridge ->
                                           canonical_spatial_authority.resolve_route)
      -> ARE THE ENDPOINT INTERFACES VALID? (payload_endpoint_authority.validate_endpoints)
      => ONE deterministic CONNECTIVITY VERDICT per (mission, mode).

    plus the two genuinely-missing requirement-derivation seams:
      * ONE ROOM -> ONE SHARED CLINICAL LOGISTICS ENDPOINT (idempotent, keyed by
        room canonical object id; reuse-before-create; $1,000 crosswalk to the
        existing LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT). A shared endpoint is a room
        interface, NOT an MRT vestibule (MRT_VESTIBULE_EQUALS_ROOM_ENDPOINT = NO).
      * MRT VESTIBULE requirement derivation ($30,000 crosswalk to the existing
        canonical_spatial_authority.MRT_VESTIBULE_CAPEX_USD).

    plus the cross-mode infrastructure BILL-OF-MATERIALS composer that reuses the
    existing per-network quantity computers and separates ALREADY-EXISTING
    (AssetStatus == "EXISTING") from NEW_REQUIRED (AssetStatus == "PROPOSED"),
    mirroring the repository's established installed-vs-existing CapEx mechanism
    (study_scope existing_* fields).

HARD DOCTRINES ENFORCED HERE (never violated):
  * CONNECTIVITY_SEPARATE_FROM_CAPACITY = YES. A FEASIBLE connectivity verdict
    NEVER asserts throughput/capacity feasibility (capacity remains owned by the
    per-mode capacity authorities; PTS contention is NOT_IMPLEMENTED upstream).
  * MRT_FORCED_AS_DEFAULT_WINNER = NO. This module ranks nothing and picks no
    winner; it only reports per-mode connectivity + the composed BoM. Mode
    SELECTION remains owned by generalized_transport_optimizer.
  * SYNTHETIC_TRANSPORT_CAPEX = NO. Every dollar figure is a crosswalk to an
    existing published canonical constant/computer; unknown components are
    reported honestly as "NOT_CALIBRATED", never a fabricated percentage block.
  * SHARED_RIGHT_OF_WAY_EQUALS_SHARED_PHYSICAL_NETWORK = NO. MRT / RGHT / PTS
    remain DISTINCT installed networks (their own authorities' governance);
    this module never merges their installed-network objects.
  * AUTOMATIC_CONNECTIVITY_IDEMPOTENT = YES. Re-deriving requirements for the
    same rooms/missions yields the identical shared-endpoint set and BoM.
  * OUT_OF_SCOPE production units (hot cell, dispensing/QC hot cells, dose
    calibrator bench, fume hood, isolator, shielded storage, waste-decay store)
    are NOT transport-unit equipment and are NOT created, costed, or endpointed
    by this module. They are explicitly enumerated for protection only.

This module imports nothing from OpenUSD/pxr, NVIDIA/Omniverse, or Bentley, and
NEVER mutates a supplied registry/graph or any locked/what-if spatial state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

import canonical_spatial_authority as csa
import payload_endpoint_authority as pea
import shared_mrt_multistream_authority as smx
import transport_mode_eligibility_authority as elig
import transport_mission_route_bridge as bridge
import pts_spatial_network_authority as pts
import rght_spatial_network_authority as rght

# ===========================================================================
# 0. OUT-OF-SCOPE production units (Build 2A section 3). Enumerated for
#    PROTECTION only -- these are radiopharmacy PRODUCTION/handling units, not
#    transport-unit equipment. This module never creates/costs/endpoints them.
# ===========================================================================

OUT_OF_SCOPE_PRODUCTION_UNITS: tuple[str, ...] = (
    "HOT_CELL",
    "DISPENSING_QC_HOT_CELL",
    "DOSE_CALIBRATOR_BENCH",
    "FUME_HOOD",
    "ISOLATOR",
    "SHIELDED_STORAGE",
    "WASTE_DECAY_STORE",
)
"""The 7 production units that are OUT_OF_SCOPE for Build 2A transport. They are
radiopharmacy production/handling equipment, NOT canonical transport-unit
equipment; they receive no transport catalog entry, no CapEx, and no shared
endpoint here."""

TRANSPORT_UNIT_EQUIPMENT_IS_OUT_OF_SCOPE_PRODUCTION_UNIT = False
"""Governor: a transport-unit-equipment builder must never be one of the 7
production units above."""


def is_out_of_scope_production_unit(unit: str) -> bool:
    """True iff `unit` is one of the 7 Build 2A OUT_OF_SCOPE production units."""
    return unit.upper() in OUT_OF_SCOPE_PRODUCTION_UNITS


# ===========================================================================
# 1. Logistics mission (Build 2A section: richer mission authority). The
#    OPTIMIZER's OptimizerMission is intentionally THIN (stream + payload only);
#    this enriches it with the mission-first attributes Build 2A requires
#    (radioactive/nuclear flag, origin/destination role + canonical object id,
#    priority, demand frequency, SLA). It COMPOSES the eligibility authority --
#    it does NOT re-implement eligibility.
# ===========================================================================

MissionPriority = Literal["ROUTINE", "URGENT", "STAT"]

# The canonical eligibility-stream vocabulary (transport_mode_eligibility_authority
# .CanonicalStream) mapped from the payload-endpoint stream vocabulary
# (payload_endpoint_authority.PayloadStream). Both are existing canonical
# vocabularies; this is a crosswalk, never a new stream taxonomy.
_PAYLOAD_STREAM_TO_ELIGIBILITY_STREAM: Mapping[pea.PayloadStream, str] = {
    "RADIOPHARMACEUTICAL": "RADIOPHARMACEUTICAL_NUCLEAR",
    "CONVENTIONAL_MEDICATION": "PHARMACY_INFUSION",
    "CLEAN_LINEN": "CLEAN_LINEN",
    "STERILE_SUPPLY": "STERILE_CLEAN_SUPPLY",
    "SPECIMEN": "SPECIMEN_BLOOD",
    "LAB_SUPPLY": "STERILE_CLEAN_SUPPLY",
}

# The eligibility-family -> the mission-mode string the route bridge understands
# -> the payload-endpoint MovementModeId used for endpoint-interface validation.
# All three vocabularies already exist; this is a crosswalk only.
_ELIGIBILITY_FAMILY_TO_BRIDGE_MODE: Mapping[elig.TransportModeFamily, str] = {
    "MANUAL": "MANUAL_PORTER",
    "PTS": "PNEUMATIC_TUBE",
    "DEDICATED_RP_PTS": "PNEUMATIC_TUBE",
    "AGV_AMR_LIGHT_CLINICAL": "RGHT",
    "AGV_AMR_HEAVY_LOGISTICS": "RGHT",
    "MRT": "MRT",
}

_ELIGIBILITY_FAMILY_TO_ENDPOINT_MODE: Mapping[elig.TransportModeFamily, pea.MovementModeId] = {
    "MANUAL": "MANUAL",
    "PTS": "PTS_CONVENTIONAL",
    "DEDICATED_RP_PTS": "PTS_NUCLEAR_QUALIFIED",
    "AGV_AMR_LIGHT_CLINICAL": "AGV_AMR_LIGHT_CLINICAL",
    "AGV_AMR_HEAVY_LOGISTICS": "AGV_AMR_HEAVY_LOGISTICS",
    "MRT": "MRT",
}


@dataclass(frozen=True)
class LogisticsMission:
    """Build 2A mission-first contract. Enriches the thin OptimizerMission with
    radioactive/nuclear semantics, resolved endpoint object ids, priority,
    demand frequency, and an SLA -- all optional/honest (None => NOT_CALIBRATED
    for that attribute), never fabricated."""

    mission_id: str
    payload_stream: pea.PayloadStream
    direction: pea.MissionDirection = "OUTBOUND"
    origin_object_id: str | None = None
    destination_object_id: str | None = None
    payload_mass_kg: float | None = None
    payload_volume_l: float | None = None
    specimen_sensitivity: "elig.SpecimenSensitivity | None" = None
    is_radioactive: bool = False
    nuclear_qualification_present: bool = False
    priority: MissionPriority = "ROUTINE"
    demand_missions_per_day: float | None = None
    sla_max_transit_minutes: float | None = None
    patient_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # A radiopharmaceutical stream is radioactive by definition; never allow
        # a radiopharmaceutical mission to silently claim non-radioactive.
        if self.payload_stream == "RADIOPHARMACEUTICAL" and not self.is_radioactive:
            object.__setattr__(self, "is_radioactive", True)

    @property
    def eligibility_stream(self) -> str:
        """The canonical transport_mode_eligibility_authority stream identifier
        for this mission's payload stream (crosswalk, not a new taxonomy)."""
        return _PAYLOAD_STREAM_TO_ELIGIBILITY_STREAM[self.payload_stream]


@dataclass(frozen=True)
class ResolvedMissionEndpoints:
    """payload_endpoint_authority roles resolved to canonical object ids. Roles
    ALWAYS come from the endpoint authority; object ids come from the mission
    (explicit) -- never fabricated when absent."""

    mission_id: str
    stream: pea.PayloadStream
    direction: pea.MissionDirection
    origin_role: pea.ServiceNodeRole
    destination_role: pea.ServiceNodeRole
    origin_object_id: str | None
    destination_object_id: str | None
    endpoints_resolved: bool
    provenance: str


def resolve_mission_endpoint_objects(mission: LogisticsMission) -> ResolvedMissionEndpoints:
    """Compose payload_endpoint_authority.default_endpoints (roles) with the
    mission's supplied canonical object ids. Never invents an object id: if the
    mission did not supply one, endpoints_resolved is False and the connectivity
    verdict downstream is NOT_CALIBRATED (honest), never FEASIBLE."""
    semantics = pea.default_endpoints(mission.payload_stream, mission.direction)
    resolved = mission.origin_object_id is not None and mission.destination_object_id is not None
    return ResolvedMissionEndpoints(
        mission_id=mission.mission_id, stream=mission.payload_stream, direction=mission.direction,
        origin_role=semantics.origin_role, destination_role=semantics.destination_role,
        origin_object_id=mission.origin_object_id, destination_object_id=mission.destination_object_id,
        endpoints_resolved=resolved,
        provenance="payload_endpoint_authority.default_endpoints roles + mission-supplied canonical object ids",
    )


# ===========================================================================
# 2. Shared clinical logistics endpoint (Build 2A: ONE ROOM -> ONE SHARED
#    ENDPOINT). Idempotent registry keyed by ROOM canonical object id. A shared
#    endpoint is a room-side interface reused across missions/modes -- it is NOT
#    an MRT vestibule (MRT_VESTIBULE_EQUALS_ROOM_ENDPOINT = NO). Its unit cost is
#    a crosswalk to the existing ordinary-endpoint constant ($1,000), never a
#    new invented cost.
# ===========================================================================

SHARED_CLINICAL_LOGISTICS_ENDPOINT_CAPEX_USD = smx.LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT
"""$1,000/endpoint crosswalk to the EXISTING shared_mrt_multistream_authority.
LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT -- never a new invented endpoint cost."""

MRT_VESTIBULE_EQUALS_ROOM_ENDPOINT = False
"""Hard governor (Build 2A): a shared room endpoint interface is NOT an MRT
vestibule. They are distinct objects with distinct costs ($1,000 vs $30,000)."""

# Room-like canonical object types that may host a shared clinical logistics
# endpoint. Uses the EXISTING canonical SpatialObjectType vocabulary.
_ROOM_LIKE_OBJECT_TYPES: frozenset[csa.SpatialObjectType] = frozenset({
    "ROOM", "PATIENT_ROOM", "INJECTION_ROOM", "UPTAKE_ROOM", "NUCLEAR_MEDICINE_ROOM",
    "CONTROL_ROOM", "STORAGE", "UTILITY_SPACE", "RADIOPHARMACY", "CENTRAL_PHARMACY",
    "LABORATORY", "BLOOD_BANK", "CLEAN_LINEN_SOURCE", "STERILE_CLEAN_SUPPLY_SOURCE",
    "LOGISTICS_ORIGIN", "LOGISTICS_DESTINATION",
})


@dataclass(frozen=True)
class SharedClinicalLogisticsEndpoint:
    """ONE shared endpoint interface per room. `serving_modes` accumulates every
    transport mode that reuses this SAME physical interface -- reuse never
    creates a second endpoint (Build 2A idempotence). `is_existing` mirrors the
    room's AssetStatus (EXISTING => not charged as NEW)."""

    endpoint_id: str
    room_object_id: str
    room_object_type: csa.SpatialObjectType
    serving_modes: tuple[str, ...]
    is_existing: bool
    unit_capex_usd: float
    provenance: str


@dataclass
class SharedClinicalLogisticsEndpointRegistry:
    """Idempotent registry: keyed by ROOM canonical object id. Requesting an
    endpoint for a room that already has one REUSES it (adds the mode to
    serving_modes) -- it never creates a duplicate. This is the concrete
    'one room = one shared endpoint' authority."""

    _by_room: dict[str, SharedClinicalLogisticsEndpoint] = field(default_factory=dict)

    def require_endpoint(
        self, registry: csa.SpatialObjectRegistry, *, room_object_id: str, serving_mode: str,
    ) -> SharedClinicalLogisticsEndpoint:
        """Idempotently require a shared endpoint at `room_object_id` for
        `serving_mode`. Reuses an existing endpoint (adding the mode) or creates
        exactly one. Raises if the room object is unknown or not room-like (never
        endpoints a production unit or a network object)."""
        if room_object_id not in registry.objects:
            raise ValueError(f"unknown room object {room_object_id!r} (not in canonical registry)")
        obj = registry.objects[room_object_id]
        if obj.object_type not in _ROOM_LIKE_OBJECT_TYPES:
            raise ValueError(
                f"{room_object_id!r} is a {obj.object_type}, not a room-like host for a shared clinical "
                "logistics endpoint (production/network objects never receive a shared endpoint)"
            )
        existing = self._by_room.get(room_object_id)
        if existing is not None:
            if serving_mode in existing.serving_modes:
                return existing
            merged = SharedClinicalLogisticsEndpoint(
                endpoint_id=existing.endpoint_id, room_object_id=existing.room_object_id,
                room_object_type=existing.room_object_type,
                serving_modes=tuple(sorted(set(existing.serving_modes) | {serving_mode})),
                is_existing=existing.is_existing, unit_capex_usd=existing.unit_capex_usd,
                provenance=existing.provenance,
            )
            self._by_room[room_object_id] = merged
            return merged
        created = SharedClinicalLogisticsEndpoint(
            endpoint_id=f"SHARED-ENDPOINT::{room_object_id}",
            room_object_id=room_object_id, room_object_type=obj.object_type,
            serving_modes=(serving_mode,),
            is_existing=(obj.asset_status == "EXISTING"),
            unit_capex_usd=SHARED_CLINICAL_LOGISTICS_ENDPOINT_CAPEX_USD,
            provenance="Build 2A shared clinical logistics endpoint (crosswalk $1,000 LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT)",
        )
        self._by_room[room_object_id] = created
        return created

    def endpoints(self) -> tuple[SharedClinicalLogisticsEndpoint, ...]:
        return tuple(self._by_room[k] for k in sorted(self._by_room))

    def endpoint_count(self) -> int:
        return len(self._by_room)

    def new_required_endpoint_count(self) -> int:
        """Count of endpoints that are NEW_REQUIRED (room AssetStatus PROPOSED)."""
        return sum(1 for e in self._by_room.values() if not e.is_existing)

    def new_required_endpoint_capex_usd(self) -> float:
        """$1,000 * NEW_REQUIRED endpoints -- existing rooms' endpoints are $0
        NEW (mirrors installed-vs-existing mechanism)."""
        return self.new_required_endpoint_count() * SHARED_CLINICAL_LOGISTICS_ENDPOINT_CAPEX_USD


# ===========================================================================
# 3. MRT vestibule requirement derivation (Build 2A). Distinct from a shared
#    room endpoint. Crosswalk to the EXISTING canonical
#    canonical_spatial_authority.MRT_VESTIBULE_CAPEX_USD ($30,000).
# ===========================================================================

MRT_VESTIBULE_REQUIREMENT_CAPEX_USD = csa.MRT_VESTIBULE_CAPEX_USD
"""$30,000/vestibule crosswalk to the EXISTING canonical
canonical_spatial_authority.MRT_VESTIBULE_CAPEX_USD -- never re-derived."""


@dataclass(frozen=True)
class MrtVestibuleRequirement:
    """An MRT mission requires a qualified MRT vestibule at its radiopharmacy /
    release origin (the transport origin, per payload_endpoint_authority Sec N).
    This records the requirement + its crosswalk cost; it never builds geometry
    (build_mrt_vestibule remains the geometry owner)."""

    mission_id: str
    origin_object_id: str | None
    vestibule_required: bool
    is_existing: bool
    unit_capex_usd: float
    reason: str


def derive_mrt_vestibule_requirement(
    mission: LogisticsMission, *, registry: csa.SpatialObjectRegistry | None = None,
) -> MrtVestibuleRequirement:
    """MRT requires a vestibule at the transport origin. If the origin object is
    known and already an EXISTING MRT_VESTIBULE, no NEW vestibule is charged;
    otherwise a NEW vestibule is required at $30,000 (crosswalk)."""
    origin = mission.origin_object_id
    is_existing = False
    if registry is not None and origin is not None and origin in registry.objects:
        obj = registry.objects[origin]
        is_existing = obj.object_type == "MRT_VESTIBULE" and obj.asset_status == "EXISTING"
    return MrtVestibuleRequirement(
        mission_id=mission.mission_id, origin_object_id=origin,
        vestibule_required=True, is_existing=is_existing,
        unit_capex_usd=MRT_VESTIBULE_REQUIREMENT_CAPEX_USD,
        reason="MRT mission requires a qualified MRT vestibule at the transport origin "
               "(payload_endpoint_authority Sec N: radiopharmacy release, distinct from a room endpoint)",
    )


# ===========================================================================
# 4. Automatic connectivity verdict (Build 2A). ONE deterministic verdict per
#    (mission, mode): eligibility gate -> endpoint resolution -> route bridge ->
#    endpoint-interface validation -> vertical-connectivity check. CONNECTIVITY
#    IS SEPARATE FROM CAPACITY (never asserts throughput).
# ===========================================================================

ConnectivityStatus = Literal[
    "FEASIBLE",
    "INFEASIBLE",
    "NOT_CALIBRATED",
    "NO_NETWORK_PATH",
    "MISSING_ORIGIN_INTERFACE",
    "MISSING_DESTINATION_INTERFACE",
    "MISSING_VERTICAL_CONNECTIVITY",
    "PAYLOAD_INCOMPATIBLE",
    "MODE_INELIGIBLE",
]


@dataclass(frozen=True)
class TransportConnectivityCandidate:
    """ONE mission + ONE mode connectivity verdict. FEASIBLE means: mode
    eligible + endpoints resolved + real calibrated route + valid endpoint
    interfaces + vertical connectivity satisfied. It NEVER implies capacity."""

    mission_id: str
    eligibility_family: elig.TransportModeFamily
    bridge_mode: str
    endpoint_mode: pea.MovementModeId
    status: ConnectivityStatus
    eligibility_status: str
    route_status: str
    route_distance_m: float | None
    endpoint_validation_status: str
    requires_vertical_connectivity: bool
    vertical_connectivity_satisfied: bool | None
    connectivity_separate_from_capacity: bool
    reason: str
    provenance: str


def _requires_vertical(
    registry: csa.SpatialObjectRegistry | None, origin_object_id: str | None, destination_object_id: str | None,
) -> bool | None:
    """True iff origin/destination are on DIFFERENT floors (need vertical
    connectivity). None (NOT_CALIBRATED) when the objects/floors are unknown."""
    if registry is None or origin_object_id is None or destination_object_id is None:
        return None
    if origin_object_id not in registry.objects or destination_object_id not in registry.objects:
        return None
    o_floor = registry.objects[origin_object_id].floor_id
    d_floor = registry.objects[destination_object_id].floor_id
    if o_floor is None or d_floor is None:
        return None
    return o_floor != d_floor


def evaluate_transport_connectivity(
    mission: LogisticsMission, family: elig.TransportModeFamily, *,
    registry: csa.SpatialObjectRegistry | None = None, graph: csa.ConnectivityGraph | None = None,
    origin_has_mode_interface: bool = True, destination_has_mode_interface: bool = True,
) -> TransportConnectivityCandidate:
    """Compose the full automatic-connectivity chain for ONE mission + ONE mode.
    Deterministic; honest NOT_CALIBRATED when endpoints/route are not supplied;
    never fabricates a route or asserts capacity."""
    bridge_mode = _ELIGIBILITY_FAMILY_TO_BRIDGE_MODE[family]
    endpoint_mode = _ELIGIBILITY_FAMILY_TO_ENDPOINT_MODE[family]

    def _verdict(
        status: ConnectivityStatus, *, elig_status: str, route_status: str, route_distance: float | None,
        ep_status: str, requires_vertical: bool | None, vertical_ok: bool | None, reason: str,
    ) -> TransportConnectivityCandidate:
        return TransportConnectivityCandidate(
            mission_id=mission.mission_id, eligibility_family=family, bridge_mode=bridge_mode,
            endpoint_mode=endpoint_mode, status=status, eligibility_status=elig_status,
            route_status=route_status, route_distance_m=route_distance, endpoint_validation_status=ep_status,
            requires_vertical_connectivity=bool(requires_vertical) if requires_vertical is not None else False,
            vertical_connectivity_satisfied=vertical_ok,
            connectivity_separate_from_capacity=True,
            reason=reason,
            provenance="composition of transport_mode_eligibility_authority + transport_mission_route_bridge "
                       "+ payload_endpoint_authority (no capacity, no synthetic CapEx)",
        )

    # (a) Eligibility gate FIRST (Sec: PAYLOAD -> ELIGIBILITY -> ...).
    elig_result = elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(
        mode=family, stream=mission.eligibility_stream, payload_mass_kg=mission.payload_mass_kg,
        payload_volume_l=mission.payload_volume_l, specimen_sensitivity=mission.specimen_sensitivity,
        radiopharm_qualified=mission.nuclear_qualification_present,
        manual_shielding_configured=mission.nuclear_qualification_present or family != "MANUAL" or not mission.is_radioactive,
    ))
    if not elig.is_allowed(elig_result):
        status: ConnectivityStatus = "PAYLOAD_INCOMPATIBLE" if elig_result.eligibility in ("INELIGIBLE", "NOT_MODELED") else "MODE_INELIGIBLE"
        return _verdict(
            status, elig_status=elig_result.eligibility, route_status="NOT_EVALUATED", route_distance=None,
            ep_status="NOT_EVALUATED", requires_vertical=None, vertical_ok=None,
            reason=f"mode {family} not allowed for {mission.eligibility_stream}: {elig_result.reason}",
        )

    # (b) Endpoints must be resolved to real object ids or the verdict is honest
    #     NOT_CALIBRATED (never FEASIBLE on assumed endpoints).
    endpoints = resolve_mission_endpoint_objects(mission)
    if not endpoints.endpoints_resolved:
        return _verdict(
            "NOT_CALIBRATED", elig_status=elig_result.eligibility, route_status="NOT_EVALUATED", route_distance=None,
            ep_status="NOT_EVALUATED", requires_vertical=None, vertical_ok=None,
            reason="mission endpoints not resolved to canonical object ids (origin/destination object id absent)",
        )

    # (c) Route bridge -- reuse the canonical route authority verbatim.
    route = bridge.resolve_mission_route(
        mission_id=mission.mission_id, transport_mode=bridge_mode,
        origin_object_id=endpoints.origin_object_id, destination_object_id=endpoints.destination_object_id,
        registry=registry, graph=graph,
    )
    requires_vertical = _requires_vertical(registry, endpoints.origin_object_id, endpoints.destination_object_id)

    if route.route_status != "ROUTE_CALIBRATED":
        # Distinguish "no network at all / not calibrated" (honest NOT_CALIBRATED)
        # from "network exists but this pair is unconnected" (NO_NETWORK_PATH).
        if route.route_status == "ROUTE_NOT_CALIBRATED":
            return _verdict(
                "NO_NETWORK_PATH", elig_status=elig_result.eligibility, route_status=route.route_status,
                route_distance=None, ep_status="NOT_EVALUATED", requires_vertical=requires_vertical, vertical_ok=None,
                reason="a network exists for this mode but no calibrated path connects the endpoints",
            )
        return _verdict(
            "NOT_CALIBRATED", elig_status=elig_result.eligibility, route_status=route.route_status,
            route_distance=None, ep_status="NOT_EVALUATED", requires_vertical=requires_vertical, vertical_ok=None,
            reason=f"route not calibrated ({route.route_status}): {route.provenance}",
        )

    # (d) Endpoint-interface validation -- reuse payload_endpoint_authority.
    ep = pea.validate_endpoints(
        stream=mission.payload_stream, mode=endpoint_mode,
        origin_node_id=endpoints.origin_object_id, destination_node_id=endpoints.destination_object_id,
        origin_has_mode_interface=origin_has_mode_interface, destination_has_mode_interface=destination_has_mode_interface,
        destination_reachable_on_network=True,
        nuclear_qualification_present=mission.nuclear_qualification_present,
    )
    if not ep.valid:
        if ep.status == "INVALID_NO_ENDPOINT_INTERFACE" and not origin_has_mode_interface:
            return _verdict(
                "MISSING_ORIGIN_INTERFACE", elig_status=elig_result.eligibility, route_status=route.route_status,
                route_distance=route.route_distance_m, ep_status=ep.status, requires_vertical=requires_vertical,
                vertical_ok=None, reason=ep.reason,
            )
        if ep.status == "INVALID_NO_ENDPOINT_INTERFACE" and not destination_has_mode_interface:
            return _verdict(
                "MISSING_DESTINATION_INTERFACE", elig_status=elig_result.eligibility, route_status=route.route_status,
                route_distance=route.route_distance_m, ep_status=ep.status, requires_vertical=requires_vertical,
                vertical_ok=None, reason=ep.reason,
            )
        return _verdict(
            "INFEASIBLE", elig_status=elig_result.eligibility, route_status=route.route_status,
            route_distance=route.route_distance_m, ep_status=ep.status, requires_vertical=requires_vertical,
            vertical_ok=None, reason=f"endpoint validation failed: {ep.reason}",
        )

    # (e) Vertical connectivity: a calibrated route that traverses floors already
    #     proves vertical connectivity (the route bridge would not have returned
    #     ROUTE_CALIBRATED otherwise). Only flag MISSING when we KNOW floors
    #     differ AND the route did not resolve -- which cannot reach here.
    vertical_ok: bool | None
    if requires_vertical is None:
        vertical_ok = None
    else:
        vertical_ok = True  # calibrated route across the graph satisfies it

    return _verdict(
        "FEASIBLE", elig_status=elig_result.eligibility, route_status=route.route_status,
        route_distance=route.route_distance_m, ep_status=ep.status,
        requires_vertical=requires_vertical, vertical_ok=vertical_ok,
        reason="eligible + endpoints resolved + calibrated route + valid interfaces "
               "(CONNECTIVITY only -- capacity NOT asserted)",
    )


def evaluate_mission_connectivity(
    mission: LogisticsMission, *, families: Sequence[elig.TransportModeFamily] | None = None,
    registry: csa.SpatialObjectRegistry | None = None, graph: csa.ConnectivityGraph | None = None,
    origin_has_mode_interface: bool = True, destination_has_mode_interface: bool = True,
) -> tuple[TransportConnectivityCandidate, ...]:
    """Automatic connectivity across every candidate mode for ONE mission.
    Deterministic ordering (ALL_TRANSPORT_MODE_FAMILIES). Ranks nothing and
    picks no winner (MRT_FORCED_AS_DEFAULT_WINNER = NO)."""
    fams = tuple(families) if families is not None else elig.ALL_TRANSPORT_MODE_FAMILIES
    return tuple(
        evaluate_transport_connectivity(
            mission, fam, registry=registry, graph=graph,
            origin_has_mode_interface=origin_has_mode_interface,
            destination_has_mode_interface=destination_has_mode_interface,
        )
        for fam in elig.ALL_TRANSPORT_MODE_FAMILIES if fam in fams
    )


# ===========================================================================
# 5. Cross-mode infrastructure bill-of-materials composer (Build 2A). Reuses the
#    EXISTING per-network quantity computers and the shared-endpoint registry.
#    Separates ALREADY-EXISTING (AssetStatus EXISTING) from NEW_REQUIRED
#    (PROPOSED). NO synthetic CapEx: every figure is a crosswalk or NOT_CALIBRATED.
# ===========================================================================

@dataclass(frozen=True)
class NetworkInfrastructureLine:
    """One transport network's composed quantities + its NEW_REQUIRED-vs-EXISTING
    object split. Quantities come straight from the existing per-network
    computers (never re-derived here)."""

    network: Literal["MRT", "PTS", "RGHT"]
    total_length_m: float
    unit_counts: Mapping[str, int]
    existing_object_count: int
    new_required_object_count: int
    capex_authority: str
    capex_status: Literal["CROSSWALK", "NOT_CALIBRATED"]


@dataclass(frozen=True)
class TransportInfrastructureBillOfMaterials:
    """The composed cross-mode BoM: per-network quantities + shared-endpoint
    accounting + MRT vestibule accounting. EXISTING vs NEW_REQUIRED separated."""

    network_lines: tuple[NetworkInfrastructureLine, ...]
    shared_endpoint_count: int
    shared_endpoint_new_required_count: int
    shared_endpoint_new_required_capex_usd: float
    mrt_vestibule_required_count: int
    mrt_vestibule_new_required_count: int
    mrt_vestibule_new_required_capex_usd: float
    connectivity_separate_from_capacity: bool
    synthetic_transport_capex: bool
    provenance: str


def _network_object_split(
    registry: csa.SpatialObjectRegistry, object_types: Sequence[csa.SpatialObjectType],
) -> tuple[int, int]:
    """(existing, new_required) counts for the given network object types,
    reusing the canonical AssetStatus (EXISTING vs PROPOSED)."""
    existing = new_required = 0
    for obj in registry.objects.values():
        if obj.object_type in object_types:
            if obj.asset_status == "EXISTING":
                existing += 1
            else:
                new_required += 1
    return existing, new_required


_PTS_OBJECT_TYPES: tuple[csa.SpatialObjectType, ...] = (
    "PTS_STATION", "PTS_JUNCTION", "PTS_TUBE_SEGMENT", "PTS_VERTICAL_SEGMENT", "PTS_CAPSULE",
)
_RGHT_OBJECT_TYPES: tuple[csa.SpatialObjectType, ...] = (
    "RGHT_STATION", "RGHT_SWITCH", "RGHT_TRACK_SEGMENT", "RGHT_VERTICAL_SEGMENT", "RGHT_VEHICLE",
)
_MRT_OBJECT_TYPES: tuple[csa.SpatialObjectType, ...] = (
    "MRT_TRUNK", "MRT_BRANCH", "MRT_SEGMENT", "MRT_JUNCTION", "MRT_ENDPOINT", "MRT_CARRIER",
    "MRT_CONTAINER", "MRT_VESTIBULE",
)


def compose_transport_infrastructure_bom(
    registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph, *,
    shared_endpoints: SharedClinicalLogisticsEndpointRegistry | None = None,
    mrt_vestibule_requirements: Sequence[MrtVestibuleRequirement] = (),
) -> TransportInfrastructureBillOfMaterials:
    """Compose the cross-mode infrastructure BoM from what was ACTUALLY built in
    the supplied registry/graph. Quantities reuse the existing computers; the
    EXISTING vs NEW_REQUIRED split reuses the canonical AssetStatus. NO synthetic
    CapEx -- MRT vestibule + shared endpoints are the only crosswalk dollar
    figures; network CapEx is deferred to the owning CapEx computers (reported
    as CROSSWALK/NOT_CALIBRATED, never fabricated here)."""
    lines: list[NetworkInfrastructureLine] = []

    pts_q = pts.compute_pts_infrastructure_quantities(registry, graph)
    pts_existing, pts_new = _network_object_split(registry, _PTS_OBJECT_TYPES)
    lines.append(NetworkInfrastructureLine(
        network="PTS", total_length_m=pts_q.total_tube_length_m,
        unit_counts={
            "station": pts_q.station_count, "junction": pts_q.junction_count,
            "vertical_segment": pts_q.vertical_segment_count, "capsule": pts_q.capsule_count,
        },
        existing_object_count=pts_existing, new_required_object_count=pts_new,
        capex_authority="conventional_transport_authority.DEFAULT_PTS_NETWORK (owning CapEx computer)",
        capex_status="NOT_CALIBRATED",
    ))

    rght_q = rght.compute_rght_infrastructure_quantities(registry, graph)
    rght_existing, rght_new = _network_object_split(registry, _RGHT_OBJECT_TYPES)
    lines.append(NetworkInfrastructureLine(
        network="RGHT", total_length_m=rght_q.total_track_length_m,
        unit_counts={
            "station": rght_q.station_count, "switch": rght_q.switch_count,
            "vertical_segment": rght_q.vertical_segment_count, "vehicle": rght_q.vehicle_count,
        },
        existing_object_count=rght_existing, new_required_object_count=rght_new,
        capex_authority="conventional_transport_authority RGHT (owning CapEx computer)",
        capex_status="NOT_CALIBRATED",
    ))

    mrt_existing, mrt_new = _network_object_split(registry, _MRT_OBJECT_TYPES)
    mrt_segment_len = sum(
        e.length_m for e in graph.edges_for_mode("MRT")
        if e.length_m != "NOT_CALIBRATED"
    )
    lines.append(NetworkInfrastructureLine(
        network="MRT", total_length_m=float(mrt_segment_len),
        unit_counts={
            t.split("MRT_")[1].lower(): sum(1 for o in registry.objects.values() if o.object_type == t)
            for t in _MRT_OBJECT_TYPES
        },
        existing_object_count=mrt_existing, new_required_object_count=mrt_new,
        capex_authority="canonical_spatial_authority.compute_mrt_transport_only_capex (owning CapEx computer)",
        capex_status="CROSSWALK",  # MRT vestibule $30k + endpoints crosswalk exist; guideway unit cost caller-supplied
    ))

    se = shared_endpoints if shared_endpoints is not None else SharedClinicalLogisticsEndpointRegistry()
    ves_required = sum(1 for r in mrt_vestibule_requirements if r.vestibule_required)
    ves_new = sum(1 for r in mrt_vestibule_requirements if r.vestibule_required and not r.is_existing)

    return TransportInfrastructureBillOfMaterials(
        network_lines=tuple(lines),
        shared_endpoint_count=se.endpoint_count(),
        shared_endpoint_new_required_count=se.new_required_endpoint_count(),
        shared_endpoint_new_required_capex_usd=se.new_required_endpoint_capex_usd(),
        mrt_vestibule_required_count=ves_required,
        mrt_vestibule_new_required_count=ves_new,
        mrt_vestibule_new_required_capex_usd=ves_new * MRT_VESTIBULE_REQUIREMENT_CAPEX_USD,
        connectivity_separate_from_capacity=True,
        synthetic_transport_capex=False,
        provenance="reuses compute_pts/rght_infrastructure_quantities + canonical AssetStatus split + "
                   "$1,000/$30,000 crosswalks; no synthetic percentage CapEx",
    )

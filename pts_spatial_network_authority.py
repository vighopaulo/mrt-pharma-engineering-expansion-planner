"""Transport Spatial Authority Build 3: PTS Canonical Spatial Network Authority.

GOVERNANCE: this module owns ONLY Pneumatic Tube System (PTS) infrastructure
identity, connectivity, route geometry, and spatial validation. It is NOT
an economic authority, NOT an architecture optimizer, NOT a clinical
authority, NOT an animation authority, and NOT an OpenUSD/Bentley/NVIDIA
authority -- it imports none of those.

PTS_AND_MRT_SHARE_INSTALLED_NETWORK = NO / PTS_AND_RGHT_SHARE_INSTALLED_
NETWORK = NO: this module NEVER reuses `MRT_*` or `RGHT_*` object types or
their builder functions -- PTS has its own distinct canonical object types
(`PTS_STATION`/`PTS_TUBE_SEGMENT`/`PTS_JUNCTION`/`PTS_VERTICAL_SEGMENT`/
`PTS_CAPSULE`, added to `canonical_spatial_authority.SpatialObjectType`).
MRT/RGHT/PTS may share corridor/building/floor OPPORTUNITY (the same
building geometry) but never the same installed transport-network object.

GENERAL PTS VS DEDICATED RP-PTS (section 14): this module models the
GENERAL/ordinary PTS technology (`conventional_transport_authority.
PneumaticTubeNetwork`/`DEFAULT_PTS_NETWORK`) only. It NEVER merges with or
imports `dedicated_rp_pts_authority.py` -- that module's dedicated
radiopharmaceutical PTS (distinct speed 6.1 m/s vs ordinary 6.0 m/s,
distinct 2-station centralized topology, distinct regulatory/economic
provenance) remains completely separate and untouched.

ROUTE SOLVER REUSE (section 7): PTS edges are tagged with the EXISTING
`canonical_spatial_authority.TransportMode` value `"PNEUMATIC_TUBE"` --
`canonical_spatial_authority.resolve_route`/`ConnectivityGraph` are reused
verbatim (`PTS_USES_COMMON_ROUTE_SOLVER = YES`); no second PTS pathfinder is
introduced.

TIMING AUDIT FINDING (sections 16-17, see `test_transport_spatial_authority_
build3.py` for the full evidence trail): the existing `conventional_
transport_authority.convert_load_to_pts_missions`/`operational_day_
orchestrator.execute_conventional_missions` PNEUMATIC_TUBE branch compute
mission duration as `dispatch_minutes + station_handling_minutes` (a flat
~2.5 minutes) -- `network_length_m`/`speed_m_per_s` are declared on
`PneumaticTubeNetwork` but are NEVER referenced by that timing formula
anywhere in this repository (confirmed by search). The sibling `dedicated_
rp_pts_authority.compute_rp_pts_mission_cycle` DOES separately add a
`tube_transport_minutes = network_length_m / speed` term alongside
dispatch/handling -- suggestive evidence that dispatch/handling are
OVERHEAD-ONLY by convention -- but the ORDINARY PTS module itself never
explicitly states this. Per this build's conservative mandate, this is
treated as `SEMANTICS_NOT_SUFFICIENTLY_CALIBRATED` for ordinary PTS:
`PTS_ROUTE_BASED_TIMING = NOT_CALIBRATED`. NO existing PTS timing numerics
are changed by this module or by this build -- only route METADATA
(status/distance/node path/provenance) is attached where a real network is
supplied.

VENDOR NEUTRALITY (section 2): no blower design, tube diameter, pressure,
capsule design, or diverter mechanics are encoded anywhere in this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import canonical_spatial_authority as csa

PTS_TRANSPORT_MODE: csa.TransportMode = "PNEUMATIC_TUBE"
"""Section 7: the EXISTING `canonical_spatial_authority.TransportMode`
value used to tag every PTS-eligible `SpatialEdge` -- never a second mode
value."""


# ---------------------------------------------------------------------------
# Section 5: canonical PTS object-type builders.
# ---------------------------------------------------------------------------


def build_pts_station(
    registry: csa.SpatialObjectRegistry, *, station_id: str, facility_id: str, building_id: str, floor_id: str,
    transform: csa.Transform = csa.Transform(), asset_status: csa.AssetStatus = "PROPOSED",
) -> csa.CanonicalSpatialObject:
    """Section 9: a PTS station where a capsule loads/unloads. Reuses the
    existing `add_room`-style construction with `object_type=
    "PTS_STATION"`. Whether this station serves a room directly
    (`DIRECT_ROOM_PTS_STATION`) or requires manual last-mile
    (`CENTRAL_PTS_STATION_WITH_LAST_MILE`) is determined by
    `classify_pts_endpoint_model`, never hard-coded here."""
    return csa.add_room(
        registry, facility_id=facility_id, building_id=building_id, floor_id=floor_id, room_id=station_id,
        object_type="PTS_STATION", transform=transform,
    )


def build_pts_junction(
    registry: csa.SpatialObjectRegistry, *, junction_id: str, facility_id: str, building_id: str, floor_id: str,
    transform: csa.Transform = csa.Transform(), asset_status: csa.AssetStatus = "PROPOSED",
) -> csa.CanonicalSpatialObject:
    """Section 5/11: a generic tube branching/diverter point -- represented
    topologically (incoming tube + multiple eligible outgoing tubes via
    `SpatialEdge`s), never a proprietary diverter mechanism."""
    obj = csa.CanonicalSpatialObject(
        mrtway_object_id=junction_id, object_type="PTS_JUNCTION", facility_id=facility_id, building_id=building_id,
        floor_id=floor_id, space_id=None, parent_object_id=csa.default_floor_object_id(building_id, floor_id),
        transform=transform, geometry_reference=None, coordinate_system="LOCAL_BUILDING", asset_status=asset_status,
        operational_state="AVAILABLE", spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def build_pts_tube_segment(
    registry: csa.SpatialObjectRegistry, *, segment_id: str, facility_id: str, building_id: str | None = None,
    floor_id: str | None = None, length_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED",
    asset_status: csa.AssetStatus = "PROPOSED",
) -> csa.CanonicalSpatialObject:
    """Section 5/11: the infrastructure-identity object for ONE physical PTS
    tube segment -- carries floor/building context. The routing GRAPH edge
    is a SEPARATE `SpatialEdge` (section 7); this object exists for
    CapEx/inventory identity only. Technology is implicit via
    `object_type="PTS_TUBE_SEGMENT"` (section 11)."""
    status: csa.SpatialStatus = "CALIBRATED" if length_m != "NOT_CALIBRATED" else "GEOMETRY_NOT_CALIBRATED"
    obj = csa.CanonicalSpatialObject(
        mrtway_object_id=segment_id, object_type="PTS_TUBE_SEGMENT", facility_id=facility_id, building_id=building_id,
        floor_id=floor_id, space_id=None, parent_object_id=None, transform=csa.Transform(), geometry_reference=f"LENGTH:{length_m}",
        coordinate_system="PROJECT_GLOBAL", asset_status=asset_status, operational_state="AVAILABLE",
        spatial_status=status, provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def build_pts_vertical_segment(
    registry: csa.SpatialObjectRegistry, *, segment_id: str, facility_id: str, building_id: str,
    start_floor_id: str, end_floor_id: str, start_elevation_m: float, end_elevation_m: float,
    length_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED", asset_status: csa.AssetStatus = "PROPOSED",
) -> csa.CanonicalSpatialObject:
    """Section 12: a generic vertical PTS transport segment -- preserves
    start/end elevation (never flattened into 2D), NOT a proprietary
    pneumatic riser mechanism."""
    if length_m == "NOT_CALIBRATED":
        length_m = abs(end_elevation_m - start_elevation_m)
    status: csa.SpatialStatus = "CALIBRATED" if length_m != "NOT_CALIBRATED" else "GEOMETRY_NOT_CALIBRATED"
    obj = csa.CanonicalSpatialObject(
        mrtway_object_id=segment_id, object_type="PTS_VERTICAL_SEGMENT", facility_id=facility_id, building_id=building_id,
        floor_id=start_floor_id, space_id=None, parent_object_id=None,
        transform=csa.Transform(position_z=start_elevation_m), geometry_reference=f"LENGTH:{length_m}",
        coordinate_system="PROJECT_GLOBAL", asset_status=asset_status, operational_state="AVAILABLE",
        spatial_status=status, provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


@dataclass(frozen=True)
class PtsCapsuleSpec:
    """Section 13: engineering companion record for ONE `PTS_CAPSULE`
    canonical object -- kept SEPARATE from `CanonicalSpatialObject`, mirroring
    `rght_spatial_network_authority.RghtVehicleSpec`. NEVER fabricates
    tare mass/dimensions/payload capacity/pressure rating -- `NOT_CALIBRATED`
    where no evidence exists; `payload_capacity_kg` may honestly reuse the
    EXISTING `conventional_transport_authority.DEFAULT_PTS_NETWORK.
    capsule_payload_kg` controlled planning assumption."""

    capsule_id: str
    technology: str = "PNEUMATIC_TUBE"
    tare_mass_kg: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    dimensions_note: str = "NOT_CALIBRATED"
    payload_capacity_kg: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    pressure_rating: str = "NOT_CALIBRATED"
    operational_state: csa.OperationalState = "AVAILABLE"
    provenance: str = "NOT_CALIBRATED -- no PTS-specific capsule engineering evidence located"


def build_pts_capsule(
    registry: csa.SpatialObjectRegistry, *, capsule_id: str, facility_id: str, network_object_id: str,
    transform: csa.Transform = csa.Transform(), asset_status: csa.AssetStatus = "PROPOSED",
    payload_capacity_kg: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED",
    payload_capacity_provenance: str = "NOT_CALIBRATED -- no PTS-specific capsule engineering evidence located",
) -> tuple[csa.CanonicalSpatialObject, PtsCapsuleSpec]:
    """Section 13: `network_object_id` must already exist and MUST NOT be an
    MRT or RGHT object (section 3/26-27)."""
    if network_object_id not in registry.objects:
        raise ValueError(f"PTS capsule {capsule_id} requires an existing network_object_id: {network_object_id} not found")
    parent = registry.get(network_object_id)
    if parent.object_type.startswith("MRT_") or parent.object_type.startswith("RGHT_"):
        raise ValueError(f"PTS capsule {capsule_id} must not be parented to an MRT/RGHT object ({network_object_id}, section 3)")
    obj = csa.CanonicalSpatialObject(
        mrtway_object_id=capsule_id, object_type="PTS_CAPSULE", facility_id=facility_id, building_id=None,
        floor_id=None, space_id=None, parent_object_id=network_object_id, transform=transform, geometry_reference=None,
        coordinate_system="PROJECT_GLOBAL", asset_status=asset_status, operational_state="AVAILABLE",
        spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    registry.add(obj)
    spec = PtsCapsuleSpec(capsule_id=capsule_id, payload_capacity_kg=payload_capacity_kg, provenance=payload_capacity_provenance)
    return obj, spec


# ---------------------------------------------------------------------------
# Section 9: central-station vs direct-room classification.
# ---------------------------------------------------------------------------

PtsEndpointModel = Literal["DIRECT_ROOM_PTS_STATION", "CENTRAL_PTS_STATION_WITH_LAST_MILE"]


def classify_pts_endpoint_model(*, station_object_id: str, destination_room_object_id: str) -> PtsEndpointModel:
    """Section 9: honest, minimal classification -- if the PTS station IS
    the destination room object itself, the network delivers directly; any
    other station requires a distinct manual last-mile handoff (section
    10, reusing the existing conventional last-mile timing authority, never
    a second porter model)."""
    if station_object_id == destination_room_object_id:
        return "DIRECT_ROOM_PTS_STATION"
    return "CENTRAL_PTS_STATION_WITH_LAST_MILE"


# ---------------------------------------------------------------------------
# Section 19: infrastructure quantity reporting.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PtsInfrastructureQuantities:
    total_horizontal_tube_length_m: float
    total_vertical_tube_length_m: float
    total_tube_length_m: float
    station_count: int
    junction_count: int
    vertical_segment_count: int
    capsule_count: int


def compute_pts_infrastructure_quantities(registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph) -> PtsInfrastructureQuantities:
    """Section 18-19: derived purely from what was actually built --
    `TOTAL_INSTALLED_PTS_NETWORK_LENGTH` is NOT the same concept as any one
    mission's route distance (section 18); this reports the former only."""
    pts_edges = graph.edges_for_mode(PTS_TRANSPORT_MODE)
    horizontal_length = sum(e.length_m for e in pts_edges if not e.vertical and e.length_m != "NOT_CALIBRATED")
    vertical_length = sum(e.length_m for e in pts_edges if e.vertical and e.length_m != "NOT_CALIBRATED")
    return PtsInfrastructureQuantities(
        total_horizontal_tube_length_m=float(horizontal_length), total_vertical_tube_length_m=float(vertical_length),
        total_tube_length_m=float(horizontal_length + vertical_length),
        station_count=sum(1 for o in registry.objects.values() if o.object_type == "PTS_STATION"),
        junction_count=sum(1 for o in registry.objects.values() if o.object_type == "PTS_JUNCTION"),
        vertical_segment_count=sum(1 for o in registry.objects.values() if o.object_type == "PTS_VERTICAL_SEGMENT"),
        capsule_count=sum(1 for o in registry.objects.values() if o.object_type == "PTS_CAPSULE"),
    )


# ---------------------------------------------------------------------------
# Section 24: contention/directionality disclosure -- NOT implemented.
# ---------------------------------------------------------------------------

PTS_NETWORK_CONTENTION_STATUS = "NOT_IMPLEMENTED"
"""Section 24: no multiple-simultaneous-capsule/tube-occupancy/junction-
contention/station-queue/priority model exists anywhere in this repository
-- never invented here. Tube directionality in the controlled proof below
is a CONTROLLED_PROOF_ASSUMPTION (bidirectional edges), never presented as
an established engineering fact."""


# ---------------------------------------------------------------------------
# Section 8: controlled PTS proof network -- reuses the SAME controlled
# hospital coordinates already used by MRT/Bentley/OpenUSD/RGHT proofs.
# ---------------------------------------------------------------------------


def build_controlled_pts_proof_network(
    registry: csa.SpatialObjectRegistry, *, facility_id: str, building_id: str,
) -> tuple[csa.ConnectivityGraph, tuple[csa.CanonicalSpatialObject, ...]]:
    """Section 8/36: builds one deterministic controlled PTS network on top
    of an ALREADY-EXISTING registry (caller must have already created
    `facility_id`/`building_id`/floor F1/F2). Proves: (A) a horizontal
    route, (B) a junction with two eligible outgoing branches, (C) a
    cross-floor route via one controlled vertical segment. Coordinates
    reuse the exact Radiopharmacy/Injection-Room/Scanner-Room positions
    from `ifc_hospital_proof_model_generator.build_hospital_proof_model()`
    (5,15,0 / 22,5,0 / 15,10,0 / 24,6,4 / 15,10,4) -- never invented, and
    distinct object IDs from `rght_spatial_network_authority.py`'s proof so
    both networks may coexist in the same registry without collision."""
    created: list[csa.CanonicalSpatialObject] = []

    station_rp = build_pts_station(
        registry, station_id="PTS-STN-RP", facility_id=facility_id, building_id=building_id, floor_id="F1",
        transform=csa.Transform(position_x=5.0, position_y=15.0, position_z=0.0),
    )
    junction_f1 = build_pts_junction(
        registry, junction_id="PTS-JCT-F1", facility_id=facility_id, building_id=building_id, floor_id="F1",
        transform=csa.Transform(position_x=15.0, position_y=10.0, position_z=0.0),
    )
    station_inj = build_pts_station(
        registry, station_id="PTS-STN-INJ", facility_id=facility_id, building_id=building_id, floor_id="F1",
        transform=csa.Transform(position_x=22.0, position_y=5.0, position_z=0.0),
    )
    junction_f2 = build_pts_junction(
        registry, junction_id="PTS-JCT-F2", facility_id=facility_id, building_id=building_id, floor_id="F2",
        transform=csa.Transform(position_x=15.0, position_y=10.0, position_z=4.0),
    )
    station_scn = build_pts_station(
        registry, station_id="PTS-STN-SCN", facility_id=facility_id, building_id=building_id, floor_id="F2",
        transform=csa.Transform(position_x=24.0, position_y=6.0, position_z=4.0),
    )
    created.extend((station_rp, junction_f1, station_inj, junction_f2, station_scn))

    def _dist(a: csa.CanonicalSpatialObject, b: csa.CanonicalSpatialObject) -> float:
        return math.sqrt((a.transform.position_x - b.transform.position_x) ** 2 + (a.transform.position_y - b.transform.position_y) ** 2)

    length_rp_to_jct1 = _dist(station_rp, junction_f1)
    length_jct1_to_inj = _dist(junction_f1, station_inj)
    length_jct2_to_scn = _dist(junction_f2, station_scn)
    vertical_length = abs(junction_f2.transform.position_z - junction_f1.transform.position_z)

    seg_rp_jct1 = build_pts_tube_segment(registry, segment_id="PTS-SEG-RP-JCT1", facility_id=facility_id, building_id=building_id, floor_id="F1", length_m=length_rp_to_jct1)
    seg_jct1_inj = build_pts_tube_segment(registry, segment_id="PTS-SEG-JCT1-INJ", facility_id=facility_id, building_id=building_id, floor_id="F1", length_m=length_jct1_to_inj)
    seg_vertical = build_pts_vertical_segment(
        registry, segment_id="PTS-SEG-VERTICAL", facility_id=facility_id, building_id=building_id,
        start_floor_id="F1", end_floor_id="F2", start_elevation_m=junction_f1.transform.position_z,
        end_elevation_m=junction_f2.transform.position_z, length_m=vertical_length,
    )
    seg_jct2_scn = build_pts_tube_segment(registry, segment_id="PTS-SEG-JCT2-SCN", facility_id=facility_id, building_id=building_id, floor_id="F2", length_m=length_jct2_to_scn)
    created.extend((seg_rp_jct1, seg_jct1_inj, seg_vertical, seg_jct2_scn))

    capsule_obj, _capsule_spec = build_pts_capsule(
        registry, capsule_id="PTS-CAPSULE-001", facility_id=facility_id, network_object_id=junction_f1.mrtway_object_id,
        payload_capacity_kg=2.0,  # section 13: honestly reuses the EXISTING legacy PTS controlled planning assumption
        payload_capacity_provenance="CONTROLLED_ENGINEERING_ASSUMPTION reused verbatim from conventional_transport_authority.DEFAULT_PTS_NETWORK.capsule_payload_kg (2.0 kg) -- never a fabricated PTS-specific value",
    )
    created.append(capsule_obj)

    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="PTS-EDGE-RP-JCT1", from_object_id=station_rp.mrtway_object_id, to_object_id=junction_f1.mrtway_object_id, length_m=length_rp_to_jct1, compatible_modes=frozenset({PTS_TRANSPORT_MODE})))
    graph.add_edge(csa.SpatialEdge(edge_id="PTS-EDGE-JCT1-INJ", from_object_id=junction_f1.mrtway_object_id, to_object_id=station_inj.mrtway_object_id, length_m=length_jct1_to_inj, compatible_modes=frozenset({PTS_TRANSPORT_MODE})))
    graph.add_edge(csa.SpatialEdge(edge_id="PTS-EDGE-VERTICAL", from_object_id=junction_f1.mrtway_object_id, to_object_id=junction_f2.mrtway_object_id, length_m=vertical_length, compatible_modes=frozenset({PTS_TRANSPORT_MODE}), vertical=True))
    graph.add_edge(csa.SpatialEdge(edge_id="PTS-EDGE-JCT2-SCN", from_object_id=junction_f2.mrtway_object_id, to_object_id=station_scn.mrtway_object_id, length_m=length_jct2_to_scn, compatible_modes=frozenset({PTS_TRANSPORT_MODE})))

    return graph, tuple(created)

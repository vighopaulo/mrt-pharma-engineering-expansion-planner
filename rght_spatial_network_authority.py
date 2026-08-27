"""Transport Spatial Authority Build 2: RGHT Canonical Spatial Network Authority.

GOVERNANCE: this module owns ONLY RGHT (Rail-Guided Hospital Transport)
infrastructure identity, connectivity, route geometry, and spatial
validation. It is NOT an architecture optimizer, NOT an economic authority,
NOT an animation authority, and NOT an OpenUSD/Bentley/NVIDIA authority --
it imports none of those.

MRT_AND_RGHT_SHARE_ENGINEERING_INFRASTRUCTURE_OBJECTS = NO: this module
NEVER reuses `MRT_TRUNK`/`MRT_BRANCH`/`MRT_SEGMENT`/`MRT_JUNCTION`/
`MRT_ENDPOINT`/`MRT_CARRIER`/`MRT_CONTAINER`/`MRT_VESTIBULE` object types or
their builder functions -- RGHT has its own distinct canonical object types
(`RGHT_TRACK_SEGMENT`/`RGHT_STATION`/`RGHT_SWITCH`/`RGHT_VERTICAL_SEGMENT`/
`RGHT_VEHICLE`, added to `canonical_spatial_authority.SpatialObjectType`).
MRT and RGHT may share corridor/building/floor OPPORTUNITY (the same
building geometry) but never the same installed transport-network object.

RGHT_AND_PTS_SHARE_INFRASTRUCTURE_OBJECTS = NO: PTS remains conceptually
tube/station/junction/capsule and is NOT modeled here or anywhere as a
first-class canonical spatial network in this repository (unchanged from
Build 1's `PNEUMATIC_SPATIAL_NETWORK = NOT_CALIBRATED`).

ROUTE SOLVER REUSE (section 10): RGHT edges are tagged with the EXISTING
`canonical_spatial_authority.TransportMode` value `"AGV_AMR"` -- the SAME
value Build 1 established as the legacy/serialization identifier whose
canonical semantic meaning is RGHT (`transport_technology_authority.
normalize_transport_technology("AGV_AMR") == "RGHT"`). No second
`TransportMode` value or route-solving algorithm is introduced;
`canonical_spatial_authority.resolve_route`/`ConnectivityGraph` are reused
verbatim (`RGHT_USES_COMMON_ROUTE_SOLVER = YES`).

VENDOR NEUTRALITY (section 2): RGHT is modeled as a generic technology
class only -- no Telelift/Swisslog/UniCar-specific rail profile, motor
specification, switch mechanism, or communication architecture is encoded
anywhere in this module (`RGHT_VENDOR_NEUTRAL = YES`).

RGHT VEHICLE MASS (section 15): `RghtVehicleSpec` NEVER reuses MRT carrier
mass assumptions. `tare_mass_kg` defaults to `"NOT_CALIBRATED"` (no RGHT
vehicle mechanical-design evidence exists anywhere in this repository);
`payload_capacity_kg` may honestly reuse the EXISTING legacy
`conventional_transport_authority.DEFAULT_AGV_MODEL.payload_capacity_kg`
controlled planning assumption (with its provenance preserved, never
silently upgraded to a calibrated engineering value).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import canonical_spatial_authority as csa

RGHT_TRANSPORT_MODE: csa.TransportMode = "AGV_AMR"
"""Section 2/10: the EXISTING `canonical_spatial_authority.TransportMode`
value used to tag every RGHT-eligible `SpatialEdge` -- never a second mode
value. Canonical semantic reporting of this technology is `"RGHT"` via
`transport_technology_authority.normalize_transport_technology`."""


# ---------------------------------------------------------------------------
# Section 5: canonical RGHT object-type builders. Station and dock are
# treated as ONE canonical type (`RGHT_STATION`) at this phase -- the
# controlled proof network has no scenario requiring a distinct docking
# sub-object, so a second type is not introduced (section 5: "do not
# proliferate types unnecessarily"). `RGHT_HANDOFF_POINT` is likewise
# omitted -- the existing conventional last-mile authority (section 9)
# already represents the handoff as a timing leg, not a spatial object.
# ---------------------------------------------------------------------------


def build_rght_station(
    registry: csa.SpatialObjectRegistry, *, station_id: str, facility_id: str, building_id: str, floor_id: str,
    transform: csa.Transform = csa.Transform(), asset_status: csa.AssetStatus = "PROPOSED",
) -> csa.CanonicalSpatialObject:
    """A station/dock/landing where an RGHT vehicle loads/unloads. Reuses
    the existing `add_room`-style construction (never a bespoke room-like
    dataclass) with `object_type="RGHT_STATION"`."""
    return csa.add_room(
        registry, facility_id=facility_id, building_id=building_id, floor_id=floor_id, room_id=station_id,
        object_type="RGHT_STATION", transform=transform,
    )


def build_rght_switch(
    registry: csa.SpatialObjectRegistry, *, switch_id: str, facility_id: str, building_id: str, floor_id: str,
    transform: csa.Transform = csa.Transform(), asset_status: csa.AssetStatus = "PROPOSED",
) -> csa.CanonicalSpatialObject:
    """A track branching point -- represented topologically (incoming track
    + multiple eligible outgoing tracks via `SpatialEdge`s sharing this
    object's ID as an endpoint), never a proprietary switch mechanism
    (section 12)."""
    obj = csa.CanonicalSpatialObject(
        mrtway_object_id=switch_id, object_type="RGHT_SWITCH", facility_id=facility_id, building_id=building_id,
        floor_id=floor_id, space_id=None, parent_object_id=csa.default_floor_object_id(building_id, floor_id),
        transform=transform, geometry_reference=None, coordinate_system="LOCAL_BUILDING", asset_status=asset_status,
        operational_state="AVAILABLE", spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def build_rght_track_segment(
    registry: csa.SpatialObjectRegistry, *, segment_id: str, facility_id: str, building_id: str | None = None,
    floor_id: str | None = None, length_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED",
    asset_status: csa.AssetStatus = "PROPOSED",
) -> csa.CanonicalSpatialObject:
    """Section 5/11: the infrastructure-identity object for ONE physical
    RGHT track segment (mirrors `build_mrt_segment`'s pattern) -- carries
    floor/building context (section 11), unlike `MRT_SEGMENT` which does
    not. The routing GRAPH edge is a SEPARATE `SpatialEdge` (section 10);
    this object exists for CapEx/inventory identity only."""
    status: csa.SpatialStatus = "CALIBRATED" if length_m != "NOT_CALIBRATED" else "GEOMETRY_NOT_CALIBRATED"
    obj = csa.CanonicalSpatialObject(
        mrtway_object_id=segment_id, object_type="RGHT_TRACK_SEGMENT", facility_id=facility_id, building_id=building_id,
        floor_id=floor_id, space_id=None, parent_object_id=None, transform=csa.Transform(), geometry_reference=f"LENGTH:{length_m}",
        coordinate_system="PROJECT_GLOBAL", asset_status=asset_status, operational_state="AVAILABLE",
        spatial_status=status, provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


def build_rght_vertical_segment(
    registry: csa.SpatialObjectRegistry, *, segment_id: str, facility_id: str, building_id: str,
    start_floor_id: str, end_floor_id: str, start_elevation_m: float, end_elevation_m: float,
    length_m: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED", asset_status: csa.AssetStatus = "PROPOSED",
) -> csa.CanonicalSpatialObject:
    """Section 13: a generic vertical RGHT transport segment -- preserves
    start/end elevation (never flattened, section 13), NOT a proprietary
    vertical mechanism. `floor_id` is left as `start_floor_id` (the
    segment's origin context); the connectivity graph edge (section 10)
    carries `vertical=True` and the real length."""
    if length_m == "NOT_CALIBRATED":
        length_m = abs(end_elevation_m - start_elevation_m)
    status: csa.SpatialStatus = "CALIBRATED" if length_m != "NOT_CALIBRATED" else "GEOMETRY_NOT_CALIBRATED"
    obj = csa.CanonicalSpatialObject(
        mrtway_object_id=segment_id, object_type="RGHT_VERTICAL_SEGMENT", facility_id=facility_id, building_id=building_id,
        floor_id=start_floor_id, space_id=None, parent_object_id=None,
        transform=csa.Transform(position_z=start_elevation_m), geometry_reference=f"LENGTH:{length_m}",
        coordinate_system="PROJECT_GLOBAL", asset_status=asset_status, operational_state="AVAILABLE",
        spatial_status=status, provenance="USER_CREATED",
    )
    registry.add(obj)
    return obj


@dataclass(frozen=True)
class RghtVehicleSpec:
    """Section 14-15: engineering-mass/capacity companion record for ONE
    `RGHT_VEHICLE` canonical object -- kept SEPARATE from
    `CanonicalSpatialObject` (which carries spatial identity only), mirroring
    how MRT carrier mass lives in `mrt_auxiliary_systems_authority.
    CarrierKinematicsSpec`, never on the spatial object itself. NEVER
    reuses MRT carrier mass assumptions (section 15)."""

    vehicle_id: str
    technology: str = "RGHT"
    tare_mass_kg: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    payload_capacity_kg: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    operational_state: csa.OperationalState = "AVAILABLE"
    provenance: str = "NOT_CALIBRATED -- no RGHT-specific vehicle engineering evidence located"


def build_rght_vehicle(
    registry: csa.SpatialObjectRegistry, *, vehicle_id: str, facility_id: str, network_object_id: str,
    transform: csa.Transform = csa.Transform(), asset_status: csa.AssetStatus = "PROPOSED",
    payload_capacity_kg: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED",
    payload_capacity_provenance: str = "NOT_CALIBRATED -- no RGHT-specific vehicle engineering evidence located",
) -> tuple[csa.CanonicalSpatialObject, RghtVehicleSpec]:
    """Section 14: `network_object_id` must already exist (no teleporting
    vehicle, mirroring `build_mrt_carrier`'s discipline) -- but the parent
    MUST be an RGHT object, never an `MRT_*` object (section 3)."""
    if network_object_id not in registry.objects:
        raise ValueError(f"RGHT vehicle {vehicle_id} requires an existing network_object_id: {network_object_id} not found")
    parent = registry.get(network_object_id)
    if parent.object_type.startswith("MRT_"):
        raise ValueError(f"RGHT vehicle {vehicle_id} must not be parented to an MRT object ({network_object_id}, section 3/24)")
    obj = csa.CanonicalSpatialObject(
        mrtway_object_id=vehicle_id, object_type="RGHT_VEHICLE", facility_id=facility_id, building_id=None,
        floor_id=None, space_id=None, parent_object_id=network_object_id, transform=transform, geometry_reference=None,
        coordinate_system="PROJECT_GLOBAL", asset_status=asset_status, operational_state="AVAILABLE",
        spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    registry.add(obj)
    spec = RghtVehicleSpec(
        vehicle_id=vehicle_id, tare_mass_kg="NOT_CALIBRATED", payload_capacity_kg=payload_capacity_kg,
        provenance=payload_capacity_provenance,
    )
    return obj, spec


# ---------------------------------------------------------------------------
# Section 8: central-floor-station vs direct-endpoint classification.
# ---------------------------------------------------------------------------

RghtEndpointModel = Literal["DIRECT_RGHT_ENDPOINT", "CENTRAL_FLOOR_STATION_WITH_LAST_MILE"]


def classify_rght_endpoint_model(*, station_object_id: str, destination_room_object_id: str) -> RghtEndpointModel:
    """Section 8: honest, minimal classification -- if the RGHT station IS
    the destination room object itself, the network delivers directly; any
    other station requires a distinct last-mile handoff. Never assumed
    universally one way (section 8)."""
    if station_object_id == destination_room_object_id:
        return "DIRECT_RGHT_ENDPOINT"
    return "CENTRAL_FLOOR_STATION_WITH_LAST_MILE"


# ---------------------------------------------------------------------------
# Section 22: infrastructure quantity reporting (engineering quantities
# only -- never converted into new CapEx in this build).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RghtInfrastructureQuantities:
    total_horizontal_track_length_m: float
    total_vertical_track_length_m: float
    total_track_length_m: float
    station_count: int
    switch_count: int
    vertical_segment_count: int
    vehicle_count: int


def compute_rght_infrastructure_quantities(registry: csa.SpatialObjectRegistry, graph: csa.ConnectivityGraph) -> RghtInfrastructureQuantities:
    """Section 22: derived purely from what was actually built -- never a
    hard-coded/assumed quantity."""
    rght_edges = graph.edges_for_mode(RGHT_TRANSPORT_MODE)
    horizontal_length = sum(e.length_m for e in rght_edges if not e.vertical and e.length_m != "NOT_CALIBRATED")
    vertical_length = sum(e.length_m for e in rght_edges if e.vertical and e.length_m != "NOT_CALIBRATED")
    return RghtInfrastructureQuantities(
        total_horizontal_track_length_m=float(horizontal_length), total_vertical_track_length_m=float(vertical_length),
        total_track_length_m=float(horizontal_length + vertical_length),
        station_count=sum(1 for o in registry.objects.values() if o.object_type == "RGHT_STATION"),
        switch_count=sum(1 for o in registry.objects.values() if o.object_type == "RGHT_SWITCH"),
        vertical_segment_count=sum(1 for o in registry.objects.values() if o.object_type == "RGHT_VERTICAL_SEGMENT"),
        vehicle_count=sum(1 for o in registry.objects.values() if o.object_type == "RGHT_VEHICLE"),
    )


# ---------------------------------------------------------------------------
# Section 7/27: controlled RGHT proof network -- reuses the SAME controlled
# hospital coordinates already used by MRT/Bentley/OpenUSD proofs
# (`ifc_hospital_proof_model_generator.build_hospital_proof_model`), never a
# second hospital coordinate source.
# ---------------------------------------------------------------------------


def build_controlled_rght_proof_network(
    registry: csa.SpatialObjectRegistry, *, facility_id: str, building_id: str,
) -> tuple[csa.ConnectivityGraph, tuple[csa.CanonicalSpatialObject, ...]]:
    """Section 7/27: builds one deterministic controlled RGHT network on
    top of an ALREADY-EXISTING registry (caller must have already created
    `facility_id`/`building_id`/floor F1/F2). Proves: (A) a horizontal
    route, (B) a switch with two eligible outgoing branches, (C) a
    cross-floor route via one controlled vertical segment. Coordinates
    reuse the exact Radiopharmacy/Injection-Room/Scanner-Room positions
    from `ifc_hospital_proof_model_generator.build_hospital_proof_model()`
    (5,15,0 / 22,5,0 / 15,10,0 / 24,6,4 / 15,10,4) -- never invented."""
    created: list[csa.CanonicalSpatialObject] = []

    station_rp = build_rght_station(
        registry, station_id="RGHT-STN-RP", facility_id=facility_id, building_id=building_id, floor_id="F1",
        transform=csa.Transform(position_x=5.0, position_y=15.0, position_z=0.0),
    )
    switch_f1 = build_rght_switch(
        registry, switch_id="RGHT-SWITCH-F1", facility_id=facility_id, building_id=building_id, floor_id="F1",
        transform=csa.Transform(position_x=15.0, position_y=10.0, position_z=0.0),
    )
    station_inj = build_rght_station(
        registry, station_id="RGHT-STN-INJ", facility_id=facility_id, building_id=building_id, floor_id="F1",
        transform=csa.Transform(position_x=22.0, position_y=5.0, position_z=0.0),
    )
    switch_f2 = build_rght_switch(
        registry, switch_id="RGHT-SWITCH-F2", facility_id=facility_id, building_id=building_id, floor_id="F2",
        transform=csa.Transform(position_x=15.0, position_y=10.0, position_z=4.0),
    )
    station_scn = build_rght_station(
        registry, station_id="RGHT-STN-SCN", facility_id=facility_id, building_id=building_id, floor_id="F2",
        transform=csa.Transform(position_x=24.0, position_y=6.0, position_z=4.0),
    )
    created.extend((station_rp, switch_f1, station_inj, switch_f2, station_scn))

    def _dist(a: csa.CanonicalSpatialObject, b: csa.CanonicalSpatialObject) -> float:
        return math.sqrt((a.transform.position_x - b.transform.position_x) ** 2 + (a.transform.position_y - b.transform.position_y) ** 2)

    length_rp_to_switch1 = _dist(station_rp, switch_f1)
    length_switch1_to_inj = _dist(switch_f1, station_inj)
    length_switch2_to_scn = _dist(switch_f2, station_scn)
    vertical_length = abs(switch_f2.transform.position_z - switch_f1.transform.position_z)

    seg_rp_switch1 = build_rght_track_segment(registry, segment_id="RGHT-SEG-RP-SW1", facility_id=facility_id, building_id=building_id, floor_id="F1", length_m=length_rp_to_switch1)
    seg_switch1_inj = build_rght_track_segment(registry, segment_id="RGHT-SEG-SW1-INJ", facility_id=facility_id, building_id=building_id, floor_id="F1", length_m=length_switch1_to_inj)
    seg_vertical = build_rght_vertical_segment(
        registry, segment_id="RGHT-SEG-VERTICAL", facility_id=facility_id, building_id=building_id,
        start_floor_id="F1", end_floor_id="F2", start_elevation_m=switch_f1.transform.position_z,
        end_elevation_m=switch_f2.transform.position_z, length_m=vertical_length,
    )
    seg_switch2_scn = build_rght_track_segment(registry, segment_id="RGHT-SEG-SW2-SCN", facility_id=facility_id, building_id=building_id, floor_id="F2", length_m=length_switch2_to_scn)
    created.extend((seg_rp_switch1, seg_switch1_inj, seg_vertical, seg_switch2_scn))

    vehicle_obj, _vehicle_spec = build_rght_vehicle(
        registry, vehicle_id="RGHT-VEH-001", facility_id=facility_id, network_object_id=switch_f1.mrtway_object_id,
        payload_capacity_kg=150.0,  # section 14: honestly reuses the EXISTING legacy AGV controlled planning assumption
        payload_capacity_provenance="CONTROLLED_ENGINEERING_ASSUMPTION reused verbatim from conventional_transport_authority.DEFAULT_AGV_MODEL.payload_capacity_kg (150.0 kg) -- never a fabricated RGHT-specific value",
    )
    created.append(vehicle_obj)

    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="RGHT-EDGE-RP-SW1", from_object_id=station_rp.mrtway_object_id, to_object_id=switch_f1.mrtway_object_id, length_m=length_rp_to_switch1, compatible_modes=frozenset({RGHT_TRANSPORT_MODE})))
    graph.add_edge(csa.SpatialEdge(edge_id="RGHT-EDGE-SW1-INJ", from_object_id=switch_f1.mrtway_object_id, to_object_id=station_inj.mrtway_object_id, length_m=length_switch1_to_inj, compatible_modes=frozenset({RGHT_TRANSPORT_MODE})))
    graph.add_edge(csa.SpatialEdge(edge_id="RGHT-EDGE-VERTICAL", from_object_id=switch_f1.mrtway_object_id, to_object_id=switch_f2.mrtway_object_id, length_m=vertical_length, compatible_modes=frozenset({RGHT_TRANSPORT_MODE}), vertical=True))
    graph.add_edge(csa.SpatialEdge(edge_id="RGHT-EDGE-SW2-SCN", from_object_id=switch_f2.mrtway_object_id, to_object_id=station_scn.mrtway_object_id, length_m=length_switch2_to_scn, compatible_modes=frozenset({RGHT_TRANSPORT_MODE})))

    return graph, tuple(created)

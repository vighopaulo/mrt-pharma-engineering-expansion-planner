from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import math
from statistics import mean
from typing import TYPE_CHECKING, Literal, Mapping

from cyclotron_production_windows import (
    BatchCyclotronAssignment,
    CyclotronFleet,
    CyclotronFleetProductionSchedule,
    CyclotronProductionCapability,
    CyclotronProductionSchedule,
    ProductionWindow,
    build_single_cyclotron_fleet,
    schedule_cyclotron_fleet_production_windows,
)
from facility_engineering_model import FacilityEngineeringObjectModel, SpatialEdge
from models import PlannerAssumptions
from operating_day_scheduler import (
    DEDICATED_ROOM_RESOURCE_INDEX,
    BatchRelease,
    ClinicalResourceMode,
    OperatingDayInputs,
    OperatingDayScheduleResult,
    schedule_operating_day,
)
from patient_radionuclide_demand import (
    FacilityDayPatientDemand,
    RadionuclideBatchDemand,
    partition_facility_day_patient_demand,
)

if TYPE_CHECKING:
    # Deferred to break a circular import: multi_isotope_decay.py imports
    # ProductionClinicalPatientTrace from this module.
    from cycle_relative_production_requirement import CycleRelativeRequirementResult


Pathway = Literal["Conventional", "MRT"]
MrtCarrierState = Literal[
    "AVAILABLE",
    "ASSIGNED",
    "IN_TRANSIT",
    "RETURNING",
    "MAINTENANCE",
    "UNAVAILABLE",
]
MrtRouteSegmentType = Literal[
    "HORIZONTAL_GUIDEWAY",
    "VERTICAL_GUIDEWAY",
    "H_TO_V_TRANSITION",
    "V_TO_H_TRANSITION",
    "INTER_BUILDING_GUIDEWAY",
    "STATION_ENDPOINT",
]
MrtCarrierRepositionPolicy = Literal["RETURN_TO_ORIGIN", "REMAIN_AT_DESTINATION"]
DestinationAssignmentPolicy = Literal["BALANCED_ROUND_ROBIN"]


@dataclass(frozen=True)
class TransportDeliveryResult:
    delivery_job_id: int
    payload_id: str
    batch_id: int
    patient_ids: tuple[str, ...]
    dispatch_time_minutes: float
    arrival_time_minutes: float
    destination: str
    queue_wait_minutes: float


@dataclass(frozen=True)
class ProductionClinicalScenario:
    facility_day_demand: FacilityDayPatientDemand
    requested_batch_count_by_radionuclide: Mapping[str, int]
    transport_minutes: float
    injection_service_minutes: float
    uptake_minutes: float
    scanner_service_minutes: float
    injection_resources: int
    uptake_resources: int
    scanners: int
    distribution_concurrency: int
    transport_return_minutes: float = 0.0
    cyclotron_capability: CyclotronProductionCapability | None = None
    cyclotron_fleet: CyclotronFleet | None = None
    clinical_day_start_minute: float = 0.0
    operating_day_minutes: float = 1080.0
    production_start_time_minutes: float = 0.0
    production_horizon_minutes: float | None = None
    pathway: Pathway = "Conventional"
    facility_engineering_model: FacilityEngineeringObjectModel | None = None
    planner_assumptions: PlannerAssumptions | None = None
    mrt_operated_carriers: int | None = None
    mrt_reposition_policy: MrtCarrierRepositionPolicy = "RETURN_TO_ORIGIN"
    transport_minutes_source: str = "USER_SUPPLIED_TRANSPORT_TIME"
    destination_assignment_policy: DestinationAssignmentPolicy = "BALANCED_ROUND_ROBIN"
    conventional_payload_capacity_doses: int = 5
    mrt_payload_capacity_doses: int = 1
    # AUTHORITATIVE final patient-to-cycle assignment from the cycle-relative production
    # planner (see cycle_relative_production_requirement.py). When present for a
    # radionuclide, the scheduler consumes this assignment directly (subject to physical
    # veto) instead of repartitioning/dense-packing. Absent radionuclides fall back to
    # the LEGACY_COMPATIBILITY patient-count batching + dense-packing path.
    finalized_cycle_assignment_by_radionuclide: Mapping[str, CycleRelativeRequirementResult] | None = None
    # Multi-origin cyclotron/radiopharmacy spatial authority (see
    # multi_cyclotron_authority.py). Maps assigned_cyclotron_id -> radiopharmacy
    # release origin object_id. When None (default), every payload's transport
    # origin resolves to the single model.primary_route_origin_object_id exactly
    # as before (byte-for-byte backward compatible, single-cyclotron benchmarks
    # are unaffected). When provided, each payload's transport origin is resolved
    # from the cyclotron that actually produced it (see _build_batch_release_mappings
    # / ProductionBatchReleaseMapping.assigned_cyclotron_id), not a single global node.
    cyclotron_radiopharmacy_origin_object_id_by_cyclotron_id: Mapping[str, str] | None = None
    blocked_injection_indices: frozenset[int] = frozenset()
    blocked_uptake_indices: frozenset[int] = frozenset()
    blocked_scanner_indices: frozenset[int] = frozenset()
    injection_reserved_until: Mapping[int, float] = field(default_factory=dict)
    uptake_reserved_until: Mapping[int, float] = field(default_factory=dict)
    scanner_reserved_until: Mapping[int, float] = field(default_factory=dict)
    """Rolling-reoptimization identity-sticky reservation (additive, threaded
    through to OperatingDayInputs unchanged) -- see operating_day_scheduler.py
    ::OperatingDayInputs docstring. Empty (default) is byte-for-byte identical
    to prior behavior for every existing caller."""
    # RUNTIME MIGRATION (SPEED): canonical STRAIGHT/HORIZONTAL route-time cruise
    # speed override (m/s). When None (default) route resolution preserves the
    # heavy planner_assumptions.mrt_horizontal_speed_m_per_s (3.0 m/s). When set
    # (canonical current-runtime = 10.0 m/s) only the horizontal segment time is
    # affected in _resolve_mrt_route_profile; vertical (1.5 m/s) / curve /
    # transition / station times are NOT touched.
    mrt_straight_speed_m_per_s_override: float | None = None

    def __post_init__(self) -> None:
        if self.pathway not in {"Conventional", "MRT"}:
            raise ValueError("pathway must be Conventional or MRT")
        if self.operating_day_minutes <= 0.0:
            raise ValueError("operating_day_minutes must be positive")
        if self.production_horizon_minutes is not None and self.production_horizon_minutes < self.production_start_time_minutes:
            raise ValueError("production_horizon_minutes must be at least production_start_time_minutes when provided")
        if self.transport_minutes < 0.0:
            raise ValueError("transport_minutes must be non-negative")
        if self.transport_return_minutes < 0.0:
            raise ValueError("transport_return_minutes must be non-negative")
        if self.injection_service_minutes < 0.0:
            raise ValueError("injection_service_minutes must be non-negative")
        if self.uptake_minutes < 0.0:
            raise ValueError("uptake_minutes must be non-negative")
        if self.scanner_service_minutes < 0.0:
            raise ValueError("scanner_service_minutes must be non-negative")
        if self.injection_resources <= 0:
            raise ValueError("injection_resources must be at least 1")
        if self.uptake_resources <= 0:
            raise ValueError("uptake_resources must be at least 1")
        if self.scanners <= 0:
            raise ValueError("scanners must be at least 1")
        if self.distribution_concurrency <= 0:
            raise ValueError("distribution_concurrency must be at least 1")
        if self.mrt_operated_carriers is not None and self.mrt_operated_carriers <= 0:
            raise ValueError("mrt_operated_carriers must be at least 1 when provided")
        if self.mrt_reposition_policy not in {"RETURN_TO_ORIGIN", "REMAIN_AT_DESTINATION"}:
            raise ValueError("mrt_reposition_policy must be RETURN_TO_ORIGIN or REMAIN_AT_DESTINATION")
        if self.destination_assignment_policy != "BALANCED_ROUND_ROBIN":
            raise ValueError("destination_assignment_policy must be BALANCED_ROUND_ROBIN")
        if self.conventional_payload_capacity_doses <= 0:
            raise ValueError("conventional_payload_capacity_doses must be at least 1")
        if self.mrt_payload_capacity_doses <= 0:
            raise ValueError("mrt_payload_capacity_doses must be at least 1")

        if self.cyclotron_capability is None and self.cyclotron_fleet is None:
            raise ValueError("Either cyclotron_capability or cyclotron_fleet must be provided")
        if self.cyclotron_capability is not None and self.cyclotron_fleet is not None:
            raise ValueError("Provide either cyclotron_capability or cyclotron_fleet, not both")

        object.__setattr__(self, "requested_batch_count_by_radionuclide", dict(self.requested_batch_count_by_radionuclide))


@dataclass(frozen=True)
class ProductionBatchReleaseMapping:
    batch_id: int
    radionuclide: str
    patient_ids: tuple[str, ...]
    patient_count: int
    total_prescribed_activity_mbq: float
    assigned_cyclotron_id: str
    production_window_id: int
    production_window_start_time_minutes: float
    production_window_end_time_minutes: float
    release_time_minutes: float


@dataclass(frozen=True)
class ReleasedDoseInventory:
    batch_id: int
    radionuclide: str
    release_time_minutes: float
    released_activity_mbq: float
    patient_ids: tuple[str, ...]
    patient_prescribed_activity_mbq_by_id: Mapping[str, float]
    available_destinations: tuple[str, ...]


@dataclass(frozen=True)
class TransportPayload:
    payload_id: str
    source_batch_id: int
    radionuclide: str
    patient_ids: tuple[str, ...]
    patient_count: int
    destination_object_id: str
    destination_floor: int | None
    payload_activity_mbq: float
    ready_time_minutes: float
    transport_mode: Pathway
    payload_capacity_basis: str


@dataclass(frozen=True)
class ConventionalTransportJob:
    job_id: int
    payload_id: str
    batch_id: int
    radionuclide: str
    patient_count: int
    destination_object_id: str
    destination_floor: int | None
    queue_ready_time_minutes: float
    transporter_id: int
    dispatch_time_minutes: float
    pickup_completion_time_minutes: float
    arrival_time_minutes: float
    handoff_completion_time_minutes: float
    transporter_release_time_minutes: float
    outbound_transport_minutes: float
    return_reposition_minutes: float
    resource_occupancy_minutes: float
    patients_represented: tuple[str, ...]
    activity_represented_mbq: float


@dataclass(frozen=True)
class ConventionalTransportScheduleResult:
    jobs: tuple[ConventionalTransportJob, ...]
    transporter_count: int
    transport_jobs_per_day: int
    transport_resource_minutes_per_day: float
    transporter_utilization_pct: float
    average_wait_minutes: float
    max_wait_minutes: float
    deliveries: tuple[TransportDeliveryResult, ...] = ()


@dataclass(frozen=True)
class MrtRouteSegment:
    segment_id: str
    segment_type: MrtRouteSegmentType
    length_m: float
    vertical_change_m: float


@dataclass(frozen=True)
class MrtRouteProfile:
    origin_object_id: str
    destination_object_id: str
    route_distance_m: float
    horizontal_distance_m: float
    vertical_distance_m: float
    hv_transition_count: int
    segment_sequence: tuple[MrtRouteSegment, ...]
    transport_minutes: float
    transport_minutes_source: str


@dataclass(frozen=True)
class MRTCarrier:
    carrier_id: int
    status: MrtCarrierState
    current_position: str
    available_time_minutes: float
    assigned_job_id: int | None
    payload_capacity: int


@dataclass(frozen=True)
class MRTCarrierTransportJob:
    job_id: int
    payload_id: str
    batch_id: int
    radionuclide: str
    origin: str
    destination: str
    destination_floor: int | None
    carrier_id: int
    route: tuple[MrtRouteSegment, ...]
    queue_start_time_minutes: float
    dispatch_time_minutes: float
    arrival_time_minutes: float
    handoff_completion_time_minutes: float
    carrier_release_time_minutes: float
    transport_time_minutes: float
    queue_wait_time_minutes: float
    reposition_time_minutes: float
    carrier_resource_cycle_minutes: float
    patient_count: int
    patients_represented: tuple[str, ...]
    activity_represented_mbq: float


@dataclass(frozen=True)
class MRTCarrierTransportScheduleResult:
    jobs: tuple[MRTCarrierTransportJob, ...]
    carriers: tuple[MRTCarrier, ...]
    carrier_count: int
    transport_jobs_per_day: int
    carrier_resource_minutes_per_day: float
    carrier_utilization_pct: float
    average_carrier_queue_wait_minutes: float
    maximum_carrier_queue_wait_minutes: float
    route_profile: MrtRouteProfile
    deliveries: tuple[TransportDeliveryResult, ...]


@dataclass(frozen=True)
class ProductionClinicalPatientTrace:
    patient_id: str
    radionuclide: str
    batch_id: int
    assigned_cyclotron_id: str
    production_window_id: int
    production_window_start_time_minutes: float
    production_window_end_time_minutes: float
    batch_release_time_minutes: float
    assigned_destination_object_id: str
    payload_id: str
    delivery_job_id: int
    transport_arrival_time_minutes: float
    scheduler_patient_id: int
    distribution_start: float
    distribution_end: float
    injection_start: float
    injection_end: float
    uptake_start: float
    uptake_end: float
    scan_start: float
    scan_end: float
    completed_within_operating_day: bool
    injection_resource_index: int = 0
    uptake_resource_index: int = 0
    scanner_resource_index: int = 0
    clinical_resource_mode: ClinicalResourceMode = "OUTPATIENT_SHARED"
    inbound_room_id: str | None = None


TransportScheduleResult = ConventionalTransportScheduleResult | MRTCarrierTransportScheduleResult


@dataclass(frozen=True)
class ProductionClinicalScheduleResult:
    scenario: ProductionClinicalScenario
    batch_demands: tuple[RadionuclideBatchDemand, ...]
    scheduled_batch_demands: tuple[RadionuclideBatchDemand, ...]
    unscheduled_batch_demands: tuple[RadionuclideBatchDemand, ...]
    production_schedule: CyclotronFleetProductionSchedule
    batch_release_mappings: tuple[ProductionBatchReleaseMapping, ...]
    released_inventory: tuple[ReleasedDoseInventory, ...]
    transport_payloads: tuple[TransportPayload, ...]
    batch_releases: tuple[BatchRelease, ...]
    transport_schedule: TransportScheduleResult
    operating_day_inputs: OperatingDayInputs
    clinical_schedule: OperatingDayScheduleResult
    patient_traces: tuple[ProductionClinicalPatientTrace, ...]
    transport_deliveries: tuple[TransportDeliveryResult, ...]


def _release_processing_minutes(
    fleet: CyclotronFleet,
    assigned_cyclotron_id: str,
    radionuclide: str,
) -> float:
    asset = next((entry for entry in fleet.assets if entry.cyclotron_id == assigned_cyclotron_id), None)
    if asset is None:
        raise ValueError(f"Assigned cyclotron {assigned_cyclotron_id} not found in fleet")
    capability = asset.capability
    if capability.release_processing_minutes_by_radionuclide is None:
        return 0.0
    return float(capability.release_processing_minutes_by_radionuclide.get(radionuclide, 0.0))


def _build_batch_release_mappings(
    batch_demands: tuple[RadionuclideBatchDemand, ...],
    production_schedule: CyclotronFleetProductionSchedule,
    fleet: CyclotronFleet,
) -> tuple[ProductionBatchReleaseMapping, ...]:
    window_by_batch_id: dict[int, object] = {}
    for window in production_schedule.windows:
        for batch_id in window.batch_ids:
            window_by_batch_id[batch_id] = window

    mappings: list[ProductionBatchReleaseMapping] = []
    for batch in batch_demands:
        window = window_by_batch_id[batch.batch_id]
        release_time = window.end_time_minutes + _release_processing_minutes(fleet, window.assigned_cyclotron_id, batch.radionuclide)
        mappings.append(
            ProductionBatchReleaseMapping(
                batch_id=batch.batch_id,
                radionuclide=batch.radionuclide,
                patient_ids=batch.patient_ids,
                patient_count=batch.patient_count,
                total_prescribed_activity_mbq=batch.total_prescribed_activity_mbq,
                assigned_cyclotron_id=window.assigned_cyclotron_id,
                production_window_id=window.window_id,
                production_window_start_time_minutes=window.start_time_minutes,
                production_window_end_time_minutes=window.end_time_minutes,
                release_time_minutes=release_time,
            )
        )
    return tuple(mappings)


def _node_ids_by_object_id(model: FacilityEngineeringObjectModel) -> dict[str, str]:
    node_ids: dict[str, str] = {}
    for node in model.nodes:
        node_ids[node.node_id] = node.node_id
        if node.object_id:
            node_ids[node.object_id] = node.node_id
    return node_ids


def _network_route_path_edges(
    model: FacilityEngineeringObjectModel,
    start_node_id: str,
    end_node_id: str,
) -> tuple[SpatialEdge, ...]:
    adjacency: dict[str, list[tuple[str, SpatialEdge, float]]] = {}
    for edge in model.edges:
        adjacency.setdefault(edge.source_node_id, []).append((edge.destination_node_id, edge, float(edge.length_m)))
        if edge.directionality in {"BIDIRECTIONAL", "ONE_WAY_REVERSE", "UNKNOWN"}:
            adjacency.setdefault(edge.destination_node_id, []).append((edge.source_node_id, edge, float(edge.length_m)))

    frontier: list[tuple[float, str]] = [(0.0, start_node_id)]
    best_cost: dict[str, float] = {start_node_id: 0.0}
    previous_edge: dict[str, SpatialEdge] = {}
    previous_node: dict[str, str] = {}

    while frontier:
        frontier.sort(reverse=True)
        current_cost, current_node = frontier.pop()
        if current_node == end_node_id:
            break
        for neighbor_node, edge, edge_cost in adjacency.get(current_node, []):
            candidate_cost = current_cost + edge_cost
            if neighbor_node not in best_cost or candidate_cost < best_cost[neighbor_node]:
                best_cost[neighbor_node] = candidate_cost
                previous_edge[neighbor_node] = edge
                previous_node[neighbor_node] = current_node
                frontier.append((candidate_cost, neighbor_node))

    if end_node_id not in best_cost:
        raise ValueError(f"No route exists between {start_node_id} and {end_node_id}")

    path_edges: list[SpatialEdge] = []
    cursor = end_node_id
    while cursor != start_node_id:
        edge = previous_edge.get(cursor)
        prior = previous_node.get(cursor)
        if edge is None or prior is None:
            raise ValueError(f"No route exists between {start_node_id} and {end_node_id}")
        path_edges.append(edge)
        cursor = prior
    path_edges.reverse()
    return tuple(path_edges)


def _resolve_active_destinations(scenario: ProductionClinicalScenario) -> tuple[str, ...]:
    model = scenario.facility_engineering_model
    if model is None or not model.primary_route_destination_object_ids:
        return ("CLINICAL_ENDPOINT",)
    ordered_unique = tuple(dict.fromkeys(model.primary_route_destination_object_ids))
    return ordered_unique if ordered_unique else ("CLINICAL_ENDPOINT",)


def _destination_floor_lookup(model: FacilityEngineeringObjectModel | None) -> dict[str, int | None]:
    if model is None:
        return {}
    floor_lookup: dict[str, int | None] = {}
    for node in model.nodes:
        if not node.object_id:
            continue
        if node.coordinate is None:
            floor_lookup[node.object_id] = None
            continue
        storey = (node.coordinate.storey or "").upper()
        floor: int | None = None
        if storey.startswith("LEVEL "):
            suffix = storey.removeprefix("LEVEL ").strip()
            if suffix.lstrip("-").isdigit():
                floor = int(suffix)
        floor_lookup[node.object_id] = floor
    return floor_lookup


def _patient_activity_lookup(scenario: ProductionClinicalScenario) -> dict[str, float]:
    return {
        patient.patient_id: float(patient.prescribed_activity_mbq)
        for patient in scenario.facility_day_demand.patients
    }


def _build_released_inventory(
    batch_release_mappings: tuple[ProductionBatchReleaseMapping, ...],
    patient_activity_mbq_by_id: Mapping[str, float],
    active_destinations: tuple[str, ...],
) -> tuple[ReleasedDoseInventory, ...]:
    inventory: list[ReleasedDoseInventory] = []
    for mapping in batch_release_mappings:
        patient_activity = {
            patient_id: float(patient_activity_mbq_by_id.get(patient_id, 0.0))
            for patient_id in mapping.patient_ids
        }
        inventory.append(
            ReleasedDoseInventory(
                batch_id=mapping.batch_id,
                radionuclide=mapping.radionuclide,
                release_time_minutes=mapping.release_time_minutes,
                released_activity_mbq=sum(patient_activity.values()),
                patient_ids=mapping.patient_ids,
                patient_prescribed_activity_mbq_by_id=patient_activity,
                available_destinations=active_destinations,
            )
        )
    return tuple(inventory)


def _assign_patients_to_destinations(
    patient_ids: tuple[str, ...],
    destinations: tuple[str, ...],
    policy: DestinationAssignmentPolicy,
) -> dict[str, list[str]]:
    if not destinations:
        raise ValueError("at least one destination is required for assignment")
    if policy != "BALANCED_ROUND_ROBIN":
        raise ValueError("Unsupported destination assignment policy")

    assignment: dict[str, list[str]] = {destination: [] for destination in destinations}
    for index, patient_id in enumerate(patient_ids):
        destination = destinations[index % len(destinations)]
        assignment[destination].append(patient_id)
    return assignment


def _build_transport_payloads(
    released_inventory: tuple[ReleasedDoseInventory, ...],
    payload_capacity_doses: int,
    transport_mode: Pathway,
    destination_assignment_policy: DestinationAssignmentPolicy,
    destination_floor_by_id: Mapping[str, int | None],
) -> tuple[TransportPayload, ...]:
    payloads: list[TransportPayload] = []
    next_payload_number = 1

    for inventory in sorted(released_inventory, key=lambda item: (item.release_time_minutes, item.batch_id)):
        assignments = _assign_patients_to_destinations(
            inventory.patient_ids,
            inventory.available_destinations,
            destination_assignment_policy,
        )
        for destination in inventory.available_destinations:
            patient_ids = assignments.get(destination, [])
            if not patient_ids:
                continue
            for offset in range(0, len(patient_ids), payload_capacity_doses):
                chunk = tuple(patient_ids[offset:offset + payload_capacity_doses])
                payload_activity = sum(float(inventory.patient_prescribed_activity_mbq_by_id[patient_id]) for patient_id in chunk)
                payloads.append(
                    TransportPayload(
                        payload_id=f"PAY-{next_payload_number:05d}",
                        source_batch_id=inventory.batch_id,
                        radionuclide=inventory.radionuclide,
                        patient_ids=chunk,
                        patient_count=len(chunk),
                        destination_object_id=destination,
                        destination_floor=destination_floor_by_id.get(destination),
                        payload_activity_mbq=payload_activity,
                        ready_time_minutes=inventory.release_time_minutes,
                        transport_mode=transport_mode,
                        payload_capacity_basis=f"{transport_mode.upper()}_PAYLOAD_CAPACITY_DOSES={payload_capacity_doses}",
                    )
                )
                next_payload_number += 1

    return tuple(payloads)


def _manual_movement_minutes(horizontal_distance_m: float, vertical_distance_m: float, assumptions: PlannerAssumptions) -> float:
    horizontal_minutes = horizontal_distance_m / max(assumptions.manual_transport_speed_m_per_s * 60.0, 1e-12)
    elevator_minutes = 0.0
    if vertical_distance_m > 0.0:
        elevator_minutes = (
            assumptions.manual_transport_elevator_wait_minutes
            + assumptions.manual_transport_elevator_loading_minutes
            + vertical_distance_m / max(assumptions.manual_transport_elevator_speed_m_per_s * 60.0, 1e-12)
        )
    return horizontal_minutes + elevator_minutes


def _resolve_conventional_route_components(
    scenario: ProductionClinicalScenario,
    destination_object_id: str,
    origin_object_id_override: str | None = None,
) -> tuple[float, float, float, float]:
    assumptions = scenario.planner_assumptions or PlannerAssumptions()
    pickup = float(assumptions.manual_transport_pickup_minutes)
    handoff = float(assumptions.manual_transport_handoff_minutes)

    model = scenario.facility_engineering_model
    if model is None or not model.nodes or not model.edges:
        outbound_total = float(scenario.transport_minutes)
        movement = max(0.0, outbound_total - pickup - handoff)
        return_minutes = float(scenario.transport_return_minutes) if scenario.transport_return_minutes > 0.0 else movement
        return pickup, movement, handoff, return_minutes

    node_ids = _node_ids_by_object_id(model)
    origin_object_id = origin_object_id_override or model.primary_route_origin_object_id or "RADIOPHARMACY_RELEASE"
    origin_node_id = node_ids.get(origin_object_id, model.edges[0].source_node_id)
    destination_node_id = node_ids.get(destination_object_id)
    if destination_node_id is None:
        outbound_total = float(scenario.transport_minutes)
        movement = max(0.0, outbound_total - pickup - handoff)
        return_minutes = float(scenario.transport_return_minutes) if scenario.transport_return_minutes > 0.0 else movement
        return pickup, movement, handoff, return_minutes

    outbound_edges = _network_route_path_edges(model, origin_node_id, destination_node_id)
    outbound_vertical = sum(abs(float(edge.vertical_change_m)) for edge in outbound_edges)
    outbound_horizontal = sum(max(0.0, float(edge.length_m) - abs(float(edge.vertical_change_m))) for edge in outbound_edges)
    outbound_movement = _manual_movement_minutes(outbound_horizontal, outbound_vertical, assumptions)

    try:
        return_edges = _network_route_path_edges(model, destination_node_id, origin_node_id)
        return_vertical = sum(abs(float(edge.vertical_change_m)) for edge in return_edges)
        return_horizontal = sum(max(0.0, float(edge.length_m) - abs(float(edge.vertical_change_m))) for edge in return_edges)
        return_movement = _manual_movement_minutes(return_horizontal, return_vertical, assumptions)
    except ValueError:
        return_movement = float(scenario.transport_return_minutes) if scenario.transport_return_minutes > 0.0 else outbound_movement

    return pickup, outbound_movement, handoff, return_movement


def _resolve_mrt_route_profile(
    scenario: ProductionClinicalScenario,
    destination_object_id: str,
    origin_object_id_override: str | None = None,
) -> MrtRouteProfile:
    assumptions = scenario.planner_assumptions or PlannerAssumptions()
    source = scenario.transport_minutes_source

    model = scenario.facility_engineering_model
    if model is None or not model.nodes or not model.edges:
        return MrtRouteProfile(
            origin_object_id="RADIOPHARMACY_RELEASE",
            destination_object_id=destination_object_id,
            route_distance_m=0.0,
            horizontal_distance_m=0.0,
            vertical_distance_m=0.0,
            hv_transition_count=0,
            segment_sequence=(
                MrtRouteSegment(
                    segment_id="LEGACY-SCALAR",
                    segment_type="HORIZONTAL_GUIDEWAY",
                    length_m=0.0,
                    vertical_change_m=0.0,
                ),
            ),
            transport_minutes=float(scenario.transport_minutes),
            transport_minutes_source=source,
        )

    node_ids = _node_ids_by_object_id(model)
    destination_node_id = node_ids.get(destination_object_id)
    if destination_node_id is None:
        destination_node_id = model.edges[0].destination_node_id

    origin_object_id = origin_object_id_override or model.primary_route_origin_object_id or "RADIOPHARMACY_RELEASE"
    origin_node_id = node_ids.get(origin_object_id)
    if origin_node_id is None:
        origin_node_id = model.edges[0].source_node_id

    path_edges = _network_route_path_edges(model, origin_node_id, destination_node_id)

    route_segments: list[MrtRouteSegment] = []
    horizontal_distance_m = 0.0
    vertical_distance_m = 0.0
    hv_transition_count = 0

    for edge in path_edges:
        vertical = abs(float(edge.vertical_change_m))
        total_length = float(edge.length_m)
        horizontal = max(0.0, total_length - vertical)

        if edge.route_corridor_class == "INTER_BUILDING_LINK":
            route_segments.append(
                MrtRouteSegment(
                    segment_id=f"{edge.edge_id}:IB",
                    segment_type="INTER_BUILDING_GUIDEWAY",
                    length_m=total_length,
                    vertical_change_m=vertical,
                )
            )
            horizontal_distance_m += total_length
            continue

        if horizontal > 0.0:
            route_segments.append(
                MrtRouteSegment(
                    segment_id=f"{edge.edge_id}:H",
                    segment_type="HORIZONTAL_GUIDEWAY",
                    length_m=horizontal,
                    vertical_change_m=0.0,
                )
            )
            horizontal_distance_m += horizontal

        if vertical > 0.0:
            hv_transition_count += 2
            route_segments.append(
                MrtRouteSegment(
                    segment_id=f"{edge.edge_id}:HTOV",
                    segment_type="H_TO_V_TRANSITION",
                    length_m=0.0,
                    vertical_change_m=0.0,
                )
            )
            route_segments.append(
                MrtRouteSegment(
                    segment_id=f"{edge.edge_id}:V",
                    segment_type="VERTICAL_GUIDEWAY",
                    length_m=vertical,
                    vertical_change_m=vertical,
                )
            )
            route_segments.append(
                MrtRouteSegment(
                    segment_id=f"{edge.edge_id}:VTOH",
                    segment_type="V_TO_H_TRANSITION",
                    length_m=0.0,
                    vertical_change_m=0.0,
                )
            )
            vertical_distance_m += vertical

    route_segments.append(
        MrtRouteSegment(
            segment_id="STATION-LOADING-UNLOADING",
            segment_type="STATION_ENDPOINT",
            length_m=0.0,
            vertical_change_m=0.0,
        )
    )

    # RUNTIME MIGRATION (SPEED): the STRAIGHT/HORIZONTAL cruise speed is sourced
    # from the canonical override when supplied (current MRT/Hybrid/Part3E
    # runtime = 10.0 m/s), else the heavy legacy assumptions.mrt_horizontal_speed
    # _m_per_s (3.0 m/s). Vertical / transition / station physics are UNCHANGED.
    horizontal_speed = (
        scenario.mrt_straight_speed_m_per_s_override
        if scenario.mrt_straight_speed_m_per_s_override is not None
        else assumptions.mrt_horizontal_speed_m_per_s
    )
    horizontal_seconds = horizontal_distance_m / max(horizontal_speed, 1e-12)
    vertical_seconds = vertical_distance_m / max(assumptions.mrt_vertical_speed_m_per_s, 1e-12)
    transition_seconds = hv_transition_count * assumptions.mrt_transition_time_seconds
    station_seconds = assumptions.mrt_station_loading_time_seconds + assumptions.mrt_station_unloading_time_seconds

    transport_minutes = (horizontal_seconds + vertical_seconds + transition_seconds + station_seconds) / 60.0

    if source == "SITE_CALIBRATED":
        resolved_source = source
    elif model.route_geometry_status == "RECONSTRUCTED":
        resolved_source = "VERIFIED_GEOMETRY_DERIVED"
    elif model.route_distance_source == "USER_SUPPLIED":
        resolved_source = "USER_SUPPLIED_DISTANCE_DERIVED"
    elif model.source_type == "BENCHMARK":
        resolved_source = "BENCHMARK_ASSUMPTION"
    else:
        resolved_source = "USER_SUPPLIED_DISTANCE_DERIVED"

    return MrtRouteProfile(
        origin_object_id=origin_object_id,
        destination_object_id=destination_object_id,
        route_distance_m=horizontal_distance_m + vertical_distance_m,
        horizontal_distance_m=horizontal_distance_m,
        vertical_distance_m=vertical_distance_m,
        hv_transition_count=hv_transition_count,
        segment_sequence=tuple(route_segments),
        transport_minutes=transport_minutes,
        transport_minutes_source=resolved_source,
    )


def _origin_object_id_for_batch(
    scenario: ProductionClinicalScenario,
    mapping_by_batch_id: Mapping[int, ProductionBatchReleaseMapping],
    batch_id: int,
) -> str | None:
    """Resolves the actual producing cyclotron's radiopharmacy origin for a batch,
    when the scenario's cyclotron_radiopharmacy_origin_object_id_by_cyclotron_id map
    is provided. Returns None when no override applies, so callers fall back to the
    existing single global model.primary_route_origin_object_id (unchanged behavior).
    """
    origin_by_cyclotron = scenario.cyclotron_radiopharmacy_origin_object_id_by_cyclotron_id
    if not origin_by_cyclotron:
        return None
    mapping = mapping_by_batch_id.get(batch_id)
    if mapping is None:
        return None
    return origin_by_cyclotron.get(mapping.assigned_cyclotron_id)


def _schedule_conventional_transport_jobs(
    payloads: tuple[TransportPayload, ...],
    transporter_count: int,
    scenario: ProductionClinicalScenario,
    batch_release_mappings: tuple[ProductionBatchReleaseMapping, ...] = (),
) -> ConventionalTransportScheduleResult:
    if transporter_count <= 0:
        raise ValueError("transporter_count must be at least 1")

    earliest_ready = min((payload.ready_time_minutes for payload in payloads), default=0.0)
    transporter_available_at = [min(0.0, earliest_ready)] * transporter_count
    jobs: list[ConventionalTransportJob] = []
    waits: list[float] = []
    mapping_by_batch_id = {mapping.batch_id: mapping for mapping in batch_release_mappings}

    for job_id, payload in enumerate(sorted(payloads, key=lambda item: (item.ready_time_minutes, item.payload_id)), start=1):
        origin_override = _origin_object_id_for_batch(scenario, mapping_by_batch_id, payload.source_batch_id)
        pickup_minutes, movement_minutes, handoff_minutes, return_minutes = _resolve_conventional_route_components(
            scenario,
            payload.destination_object_id,
            origin_override,
        )
        transporter_id = min(range(transporter_count), key=lambda index: transporter_available_at[index])
        queue_ready = payload.ready_time_minutes
        dispatch_time = max(queue_ready, transporter_available_at[transporter_id])
        pickup_complete = dispatch_time + pickup_minutes
        arrival_time = pickup_complete + movement_minutes
        handoff_complete = arrival_time + handoff_minutes
        transporter_release_time = handoff_complete + return_minutes
        resource_cycle = pickup_minutes + movement_minutes + handoff_minutes + return_minutes

        transporter_available_at[transporter_id] = transporter_release_time
        waits.append(max(0.0, dispatch_time - queue_ready))

        jobs.append(
            ConventionalTransportJob(
                job_id=job_id,
                payload_id=payload.payload_id,
                batch_id=payload.source_batch_id,
                radionuclide=payload.radionuclide,
                patient_count=payload.patient_count,
                destination_object_id=payload.destination_object_id,
                destination_floor=payload.destination_floor,
                queue_ready_time_minutes=queue_ready,
                transporter_id=transporter_id + 1,
                dispatch_time_minutes=dispatch_time,
                pickup_completion_time_minutes=pickup_complete,
                arrival_time_minutes=arrival_time,
                handoff_completion_time_minutes=handoff_complete,
                transporter_release_time_minutes=transporter_release_time,
                outbound_transport_minutes=pickup_minutes + movement_minutes + handoff_minutes,
                return_reposition_minutes=return_minutes,
                resource_occupancy_minutes=resource_cycle,
                patients_represented=payload.patient_ids,
                activity_represented_mbq=payload.payload_activity_mbq,
            )
        )

    if jobs:
        total_occupancy = sum(job.resource_occupancy_minutes for job in jobs)
        denominator = transporter_count * max(job.transporter_release_time_minutes for job in jobs)
        utilization = 100.0 * total_occupancy / max(denominator, 1e-12)
    else:
        total_occupancy = 0.0
        utilization = 0.0

    deliveries = tuple(
        TransportDeliveryResult(
            delivery_job_id=job.job_id,
            payload_id=job.payload_id,
            batch_id=job.batch_id,
            patient_ids=job.patients_represented,
            dispatch_time_minutes=job.dispatch_time_minutes,
            arrival_time_minutes=job.handoff_completion_time_minutes,
            destination=job.destination_object_id,
            queue_wait_minutes=max(0.0, job.dispatch_time_minutes - job.queue_ready_time_minutes),
        )
        for job in jobs
    )

    return ConventionalTransportScheduleResult(
        jobs=tuple(jobs),
        transporter_count=transporter_count,
        transport_jobs_per_day=len(jobs),
        transport_resource_minutes_per_day=total_occupancy,
        transporter_utilization_pct=min(100.0, utilization),
        average_wait_minutes=mean(waits) if waits else 0.0,
        max_wait_minutes=max(waits) if waits else 0.0,
        deliveries=deliveries,
    )


def _schedule_mrt_carrier_transport_jobs(
    payloads: tuple[TransportPayload, ...],
    carrier_count: int,
    route_profiles_by_destination: Mapping[str, MrtRouteProfile],
    reposition_policy: MrtCarrierRepositionPolicy,
    payload_capacity_doses: int,
    route_profiles_by_origin_and_destination: Mapping[tuple[str, str], MrtRouteProfile] | None = None,
    origin_object_id_by_batch_id: Mapping[int, str] | None = None,
) -> MRTCarrierTransportScheduleResult:
    if carrier_count <= 0:
        raise ValueError("carrier_count must be at least 1")

    if route_profiles_by_destination:
        origin_object_id = next(iter(route_profiles_by_destination.values())).origin_object_id
    else:
        origin_object_id = "RADIOPHARMACY_RELEASE"

    earliest_release = min((payload.ready_time_minutes for payload in payloads), default=0.0)
    carrier_available_at = [min(0.0, earliest_release)] * carrier_count
    carrier_positions = [origin_object_id] * carrier_count
    carrier_status = ["AVAILABLE"] * carrier_count

    jobs: list[MRTCarrierTransportJob] = []
    waits: list[float] = []

    for job_id, payload in enumerate(sorted(payloads, key=lambda item: (item.ready_time_minutes, item.payload_id)), start=1):
        route_profile = None
        if route_profiles_by_origin_and_destination and origin_object_id_by_batch_id:
            payload_origin = origin_object_id_by_batch_id.get(payload.source_batch_id)
            if payload_origin is not None:
                route_profile = route_profiles_by_origin_and_destination.get((payload_origin, payload.destination_object_id))
        if route_profile is None:
            route_profile = route_profiles_by_destination.get(payload.destination_object_id)
        if route_profile is None:
            raise ValueError(f"Missing MRT route profile for destination {payload.destination_object_id}")

        transport_minutes = float(route_profile.transport_minutes)
        reposition_minutes = transport_minutes if reposition_policy == "RETURN_TO_ORIGIN" else 0.0

        carrier_id = min(range(carrier_count), key=lambda index: carrier_available_at[index])
        queue_start = payload.ready_time_minutes
        dispatch_time = max(queue_start, carrier_available_at[carrier_id])
        queue_wait = max(0.0, dispatch_time - queue_start)
        arrival_time = dispatch_time + transport_minutes
        handoff_completion = arrival_time
        carrier_release_time = handoff_completion + reposition_minutes

        carrier_available_at[carrier_id] = carrier_release_time
        carrier_positions[carrier_id] = (
            route_profile.origin_object_id if reposition_policy == "RETURN_TO_ORIGIN" else route_profile.destination_object_id
        )
        carrier_status[carrier_id] = "AVAILABLE"
        waits.append(queue_wait)

        jobs.append(
            MRTCarrierTransportJob(
                job_id=job_id,
                payload_id=payload.payload_id,
                batch_id=payload.source_batch_id,
                radionuclide=payload.radionuclide,
                origin=route_profile.origin_object_id,
                destination=route_profile.destination_object_id,
                destination_floor=payload.destination_floor,
                carrier_id=carrier_id + 1,
                route=route_profile.segment_sequence,
                queue_start_time_minutes=queue_start,
                dispatch_time_minutes=dispatch_time,
                arrival_time_minutes=arrival_time,
                handoff_completion_time_minutes=handoff_completion,
                carrier_release_time_minutes=carrier_release_time,
                transport_time_minutes=transport_minutes,
                queue_wait_time_minutes=queue_wait,
                reposition_time_minutes=reposition_minutes,
                carrier_resource_cycle_minutes=transport_minutes + reposition_minutes,
                patient_count=payload.patient_count,
                patients_represented=payload.patient_ids,
                activity_represented_mbq=payload.payload_activity_mbq,
            )
        )

    if jobs:
        total_resource_minutes = sum(job.carrier_resource_cycle_minutes for job in jobs)
        denominator = carrier_count * max(job.carrier_release_time_minutes for job in jobs)
        utilization = 100.0 * total_resource_minutes / max(denominator, 1e-12)
    else:
        total_resource_minutes = 0.0
        utilization = 0.0

    carriers = tuple(
        MRTCarrier(
            carrier_id=index + 1,
            status=carrier_status[index],
            current_position=carrier_positions[index],
            available_time_minutes=carrier_available_at[index],
            assigned_job_id=None,
            payload_capacity=payload_capacity_doses,
        )
        for index in range(carrier_count)
    )

    deliveries = tuple(
        TransportDeliveryResult(
            delivery_job_id=job.job_id,
            payload_id=job.payload_id,
            batch_id=job.batch_id,
            patient_ids=job.patients_represented,
            dispatch_time_minutes=job.dispatch_time_minutes,
            arrival_time_minutes=job.arrival_time_minutes,
            destination=job.destination,
            queue_wait_minutes=job.queue_wait_time_minutes,
        )
        for job in jobs
    )

    representative_route = (
        next(iter(route_profiles_by_destination.values()))
        if route_profiles_by_destination
        else MrtRouteProfile(
            origin_object_id="RADIOPHARMACY_RELEASE",
            destination_object_id="CLINICAL_ENDPOINT",
            route_distance_m=0.0,
            horizontal_distance_m=0.0,
            vertical_distance_m=0.0,
            hv_transition_count=0,
            segment_sequence=(),
            transport_minutes=0.0,
            transport_minutes_source="BENCHMARK_ASSUMPTION",
        )
    )

    return MRTCarrierTransportScheduleResult(
        jobs=tuple(jobs),
        carriers=carriers,
        carrier_count=carrier_count,
        transport_jobs_per_day=len(jobs),
        carrier_resource_minutes_per_day=total_resource_minutes,
        carrier_utilization_pct=min(100.0, utilization),
        average_carrier_queue_wait_minutes=mean(waits) if waits else 0.0,
        maximum_carrier_queue_wait_minutes=max(waits) if waits else 0.0,
        route_profile=representative_route,
        deliveries=deliveries,
    )


def _build_batch_releases_from_transport(
    payloads: tuple[TransportPayload, ...],
    deliveries: tuple[TransportDeliveryResult, ...],
    clinical_mode_by_patient_id: Mapping[str, ClinicalResourceMode] | None = None,
    inbound_room_id_by_patient_id: Mapping[str, str] | None = None,
) -> tuple[BatchRelease, ...]:
    arrival_by_payload_id = {delivery.payload_id: delivery.arrival_time_minutes for delivery in deliveries}
    release_rows: list[BatchRelease] = []
    for payload in sorted(payloads, key=lambda item: (arrival_by_payload_id.get(item.payload_id, item.ready_time_minutes), item.payload_id)):
        arrival = arrival_by_payload_id.get(payload.payload_id)
        if arrival is None:
            raise ValueError(f"Missing delivery arrival for payload {payload.payload_id}")
        patient_clinical_modes: tuple[ClinicalResourceMode, ...] = ()
        patient_inbound_room_ids: tuple[str | None, ...] = ()
        if clinical_mode_by_patient_id:
            patient_clinical_modes = tuple(
                clinical_mode_by_patient_id.get(patient_id, "OUTPATIENT_SHARED") for patient_id in payload.patient_ids
            )
            patient_inbound_room_ids = tuple(
                (inbound_room_id_by_patient_id or {}).get(patient_id) for patient_id in payload.patient_ids
            )
        release_rows.append(
            BatchRelease(
                batch_id=payload.source_batch_id,
                release_time_minutes=arrival,
                patients_in_batch=payload.patient_count,
                release_unit_id=payload.payload_id,
                patient_clinical_modes=patient_clinical_modes,
                patient_inbound_room_ids=patient_inbound_room_ids,
            )
        )
    return tuple(release_rows)


def _build_patient_traces(
    batch_release_mappings: tuple[ProductionBatchReleaseMapping, ...],
    payloads: tuple[TransportPayload, ...],
    deliveries: tuple[TransportDeliveryResult, ...],
    clinical_schedule: OperatingDayScheduleResult,
) -> tuple[ProductionClinicalPatientTrace, ...]:
    mapping_by_batch_id = {mapping.batch_id: mapping for mapping in batch_release_mappings}
    payload_by_id = {payload.payload_id: payload for payload in payloads}
    delivery_by_payload_id = {delivery.payload_id: delivery for delivery in deliveries}

    schedules_by_release_unit_id: dict[str, list[object]] = defaultdict(list)
    for patient_schedule in clinical_schedule.patient_schedules:
        release_unit_id = patient_schedule.release_unit_id
        if release_unit_id is None:
            raise ValueError("Clinical schedule row missing release_unit_id")
        schedules_by_release_unit_id[release_unit_id].append(patient_schedule)

    traces: list[ProductionClinicalPatientTrace] = []
    for payload in payloads:
        mapping = mapping_by_batch_id[payload.source_batch_id]
        delivery = delivery_by_payload_id.get(payload.payload_id)
        if delivery is None:
            raise ValueError(f"Missing delivery for payload {payload.payload_id}")
        payload_schedules = sorted(
            schedules_by_release_unit_id.get(payload.payload_id, []),
            key=lambda schedule: schedule.patient_id,
        )
        if len(payload_schedules) != payload.patient_count:
            raise ValueError(
                f"Clinical schedule patient count for payload {payload.payload_id} does not match payload demand"
            )

        for patient_id, patient_schedule in zip(payload.patient_ids, payload_schedules):
            traces.append(
                ProductionClinicalPatientTrace(
                    patient_id=patient_id,
                    radionuclide=mapping.radionuclide,
                    batch_id=mapping.batch_id,
                    assigned_cyclotron_id=mapping.assigned_cyclotron_id,
                    production_window_id=mapping.production_window_id,
                    production_window_start_time_minutes=mapping.production_window_start_time_minutes,
                    production_window_end_time_minutes=mapping.production_window_end_time_minutes,
                    batch_release_time_minutes=mapping.release_time_minutes,
                    assigned_destination_object_id=payload.destination_object_id,
                    payload_id=payload.payload_id,
                    delivery_job_id=delivery.delivery_job_id,
                    transport_arrival_time_minutes=delivery.arrival_time_minutes,
                    scheduler_patient_id=patient_schedule.patient_id,
                    distribution_start=patient_schedule.distribution_start,
                    distribution_end=patient_schedule.distribution_end,
                    injection_start=patient_schedule.injection_start,
                    injection_end=patient_schedule.injection_end,
                    uptake_start=patient_schedule.uptake_start,
                    uptake_end=patient_schedule.uptake_end,
                    scan_start=patient_schedule.scan_start,
                    scan_end=patient_schedule.scan_end,
                    completed_within_operating_day=patient_schedule.completed_within_operating_day,
                    injection_resource_index=patient_schedule.injection_resource_index,
                    uptake_resource_index=patient_schedule.uptake_resource_index,
                    scanner_resource_index=patient_schedule.scanner_resource_index,
                    clinical_resource_mode=patient_schedule.clinical_resource_mode,
                    inbound_room_id=patient_schedule.inbound_room_id,
                )
            )
    return tuple(sorted(traces, key=lambda trace: (trace.batch_id, trace.patient_id)))


def _batches_and_schedule_from_finalized_assignment(
    *,
    facility_day_demand: FacilityDayPatientDemand,
    finalized_by_radionuclide: Mapping[str, CycleRelativeRequirementResult],
    fleet: CyclotronFleet,
    production_horizon_minutes: float | None,
) -> tuple[tuple[RadionuclideBatchDemand, ...], CyclotronFleetProductionSchedule]:
    """Consume the planner's finalized patient-to-cycle assignment directly rather than
    repartitioning patients or dense-packing production windows. Cycles the planner
    marked SCHEDULED_ACTIVITY_INFEASIBLE (exceed calibrated capacity), that fall outside
    the configured production horizon, or that overlap another finalized cycle on the
    same cyclotron are rejected here (no window is created, so they surface as
    unscheduled) rather than silently reshaped into a different grouping or timing.
    """
    patients_by_id = {patient.patient_id: patient for patient in facility_day_demand.patients}

    batch_demands: list[RadionuclideBatchDemand] = []
    windows: list[ProductionWindow] = []
    batch_assignments: list[BatchCyclotronAssignment] = []
    rejected_batch_ids: list[int] = []
    accepted_intervals_by_cyclotron: dict[str, list[tuple[float, float]]] = defaultdict(list)
    next_batch_id = 1
    next_window_id = 1

    for radionuclide in sorted(finalized_by_radionuclide):
        result = finalized_by_radionuclide[radionuclide]
        for usage in sorted(result.cycle_usages, key=lambda item: (item.eob_minutes, item.cycle_id)):
            if not usage.patient_ids:
                continue
            batch_id = next_batch_id
            next_batch_id += 1
            total_activity = sum(
                float(patients_by_id[patient_id].prescribed_activity_mbq) for patient_id in usage.patient_ids
            )
            batch_demands.append(
                RadionuclideBatchDemand(
                    batch_id=batch_id,
                    radionuclide=radionuclide,
                    patient_ids=usage.patient_ids,
                    patient_count=len(usage.patient_ids),
                    total_prescribed_activity_mbq=total_activity,
                )
            )
            batch_assignments.append(
                BatchCyclotronAssignment(
                    batch_id=batch_id,
                    radionuclide=radionuclide,
                    assigned_cyclotron_id=usage.cyclotron_id,
                    assignment_reason="FINALIZED_CYCLE_RELATIVE_ASSIGNMENT",
                )
            )

            within_horizon = production_horizon_minutes is None or usage.eob_minutes <= production_horizon_minutes + 1e-6
            overlaps = any(
                usage.start_minutes < existing_end and usage.eob_minutes > existing_start
                for existing_start, existing_end in accepted_intervals_by_cyclotron[usage.cyclotron_id]
            )
            physically_valid = usage.status == "SCHEDULED_FEASIBLE" and within_horizon and not overlaps

            if physically_valid:
                windows.append(
                    ProductionWindow(
                        window_id=next_window_id,
                        assigned_cyclotron_id=usage.cyclotron_id,
                        batch_ids=(batch_id,),
                        radionuclides=(radionuclide,),
                        start_time_minutes=usage.start_minutes,
                        end_time_minutes=usage.eob_minutes,
                        duration_minutes=usage.eob_minutes - usage.start_minutes,
                        simultaneous_stream_count=1,
                    )
                )
                accepted_intervals_by_cyclotron[usage.cyclotron_id].append((usage.start_minutes, usage.eob_minutes))
                next_window_id += 1
            else:
                rejected_batch_ids.append(batch_id)

    ordered_windows = tuple(
        sorted(windows, key=lambda window: (window.start_time_minutes, window.end_time_minutes, window.assigned_cyclotron_id, window.window_id))
    )

    per_cyclotron: dict[str, CyclotronProductionSchedule] = {}
    for asset in fleet.assets:
        asset_windows = tuple(window for window in ordered_windows if window.assigned_cyclotron_id == asset.cyclotron_id)
        asset_scheduled_batch_ids = {batch_id for window in asset_windows for batch_id in window.batch_ids}
        asset_total_batches = sum(1 for assignment in batch_assignments if assignment.assigned_cyclotron_id == asset.cyclotron_id)
        asset_unscheduled_ids = tuple(
            sorted(
                assignment.batch_id
                for assignment in batch_assignments
                if assignment.assigned_cyclotron_id == asset.cyclotron_id and assignment.batch_id not in asset_scheduled_batch_ids
            )
        )
        asset_start = min((window.start_time_minutes for window in asset_windows), default=0.0)
        asset_end = max((window.end_time_minutes for window in asset_windows), default=asset_start)
        per_cyclotron[asset.cyclotron_id] = CyclotronProductionSchedule(
            cyclotron_id=asset.cyclotron_id,
            windows=asset_windows,
            total_batches=asset_total_batches,
            scheduled_batches=len(asset_scheduled_batch_ids),
            unscheduled_batches=len(asset_unscheduled_ids),
            unscheduled_batch_ids=asset_unscheduled_ids,
            total_windows=len(asset_windows),
            production_start_time_minutes=asset_start,
            production_end_time_minutes=asset_end,
            total_elapsed_production_minutes=max(0.0, asset_end - asset_start),
            max_simultaneous_streams_used=max((window.simultaneous_stream_count for window in asset_windows), default=0),
            all_batches_scheduled=(len(asset_unscheduled_ids) == 0),
            fits_within_production_horizon=(len(asset_unscheduled_ids) == 0),
        )

    scheduled_batch_ids_all = {batch_id for window in ordered_windows for batch_id in window.batch_ids}
    all_unscheduled_ids = tuple(sorted(rejected_batch_ids))
    min_start = min((window.start_time_minutes for window in ordered_windows), default=0.0)
    max_end = max((window.end_time_minutes for window in ordered_windows), default=min_start)

    production_schedule = CyclotronFleetProductionSchedule(
        fleet_id=fleet.fleet_id,
        batch_assignments=tuple(batch_assignments),
        per_cyclotron_schedules=per_cyclotron,
        windows=ordered_windows,
        total_batches=len(batch_demands),
        scheduled_batches=len(scheduled_batch_ids_all),
        unscheduled_batches=len(all_unscheduled_ids),
        unscheduled_batch_ids=all_unscheduled_ids,
        total_windows=len(ordered_windows),
        production_start_time_minutes=min_start,
        production_end_time_minutes=max_end,
        total_elapsed_production_minutes=max(0.0, max_end - min_start),
        max_simultaneous_streams_used=max((window.simultaneous_stream_count for window in ordered_windows), default=0),
        all_batches_scheduled=(len(all_unscheduled_ids) == 0),
        fits_within_production_horizon=(len(all_unscheduled_ids) == 0),
    )

    return tuple(batch_demands), production_schedule


def build_production_clinical_schedule(
    scenario: ProductionClinicalScenario,
) -> ProductionClinicalScheduleResult:
    fleet = scenario.cyclotron_fleet if scenario.cyclotron_fleet is not None else build_single_cyclotron_fleet(scenario.cyclotron_capability)

    finalized = scenario.finalized_cycle_assignment_by_radionuclide
    positive_radionuclides = {
        radionuclide
        for radionuclide, count in scenario.requested_batch_count_by_radionuclide.items()
        if int(count) > 0
    }
    use_finalized_assignment = bool(finalized) and positive_radionuclides.issubset(set(finalized))

    if use_finalized_assignment:
        batch_demands, production_schedule = _batches_and_schedule_from_finalized_assignment(
            facility_day_demand=scenario.facility_day_demand,
            finalized_by_radionuclide=finalized,
            fleet=fleet,
            production_horizon_minutes=scenario.production_horizon_minutes,
        )
    else:
        # LEGACY_COMPATIBILITY: no (or only partial) authoritative cycle-relative
        # assignment is available; fall back to patient-count batching + dense packing.
        batch_demands = tuple(
            partition_facility_day_patient_demand(
                scenario.facility_day_demand,
                scenario.requested_batch_count_by_radionuclide,
            )
        )
        production_schedule = schedule_cyclotron_fleet_production_windows(
            batch_demands,
            fleet,
            production_start_time_minutes=scenario.production_start_time_minutes,
            production_horizon_minutes=scenario.production_horizon_minutes,
        )
    scheduled_batch_ids = {
        batch_id
        for window in production_schedule.windows
        for batch_id in window.batch_ids
    }
    scheduled_batch_demands = tuple(batch for batch in batch_demands if batch.batch_id in scheduled_batch_ids)
    unscheduled_batch_demands = tuple(batch for batch in batch_demands if batch.batch_id not in scheduled_batch_ids)
    batch_release_mappings = _build_batch_release_mappings(
        scheduled_batch_demands,
        production_schedule,
        fleet,
    )

    active_destinations = _resolve_active_destinations(scenario)
    destination_floor_by_id = _destination_floor_lookup(scenario.facility_engineering_model)
    patient_activity_mbq_by_id = _patient_activity_lookup(scenario)
    released_inventory = _build_released_inventory(
        batch_release_mappings,
        patient_activity_mbq_by_id,
        active_destinations,
    )

    payload_capacity = (
        scenario.mrt_payload_capacity_doses
        if scenario.pathway == "MRT"
        else scenario.conventional_payload_capacity_doses
    )
    transport_payloads = _build_transport_payloads(
        released_inventory,
        payload_capacity_doses=payload_capacity,
        transport_mode=scenario.pathway,
        destination_assignment_policy=scenario.destination_assignment_policy,
        destination_floor_by_id=destination_floor_by_id,
    )

    if scenario.pathway == "MRT":
        origin_override_map = scenario.cyclotron_radiopharmacy_origin_object_id_by_cyclotron_id
        mapping_by_batch_id_for_mrt = {mapping.batch_id: mapping for mapping in batch_release_mappings}
        route_profiles_by_destination = {
            destination: _resolve_mrt_route_profile(scenario, destination)
            for destination in active_destinations
        }
        route_profiles_by_origin_and_destination: dict[tuple[str, str], MrtRouteProfile] | None = None
        origin_object_id_by_batch_id: dict[int, str] | None = None
        if origin_override_map:
            origin_object_id_by_batch_id = {
                batch_id: origin
                for batch_id, mapping in mapping_by_batch_id_for_mrt.items()
                if (origin := _origin_object_id_for_batch(scenario, mapping_by_batch_id_for_mrt, batch_id)) is not None
            }
            distinct_origins = set(origin_object_id_by_batch_id.values())
            route_profiles_by_origin_and_destination = {
                (origin, destination): _resolve_mrt_route_profile(scenario, destination, origin)
                for origin in distinct_origins
                for destination in active_destinations
            }
        carrier_count = scenario.mrt_operated_carriers if scenario.mrt_operated_carriers is not None else scenario.distribution_concurrency
        transport_schedule: TransportScheduleResult = _schedule_mrt_carrier_transport_jobs(
            transport_payloads,
            carrier_count=carrier_count,
            route_profiles_by_destination=route_profiles_by_destination,
            reposition_policy=scenario.mrt_reposition_policy,
            payload_capacity_doses=scenario.mrt_payload_capacity_doses,
            route_profiles_by_origin_and_destination=route_profiles_by_origin_and_destination,
            origin_object_id_by_batch_id=origin_object_id_by_batch_id,
        )
        deliveries = transport_schedule.deliveries
    else:
        transport_schedule = _schedule_conventional_transport_jobs(
            transport_payloads,
            transporter_count=scenario.distribution_concurrency,
            scenario=scenario,
            batch_release_mappings=batch_release_mappings,
        )
        deliveries = transport_schedule.deliveries

    clinical_mode_by_patient_id = {
        patient.patient_id: patient.clinical_resource_mode for patient in scenario.facility_day_demand.patients
    }
    inbound_room_id_by_patient_id = {
        patient.patient_id: patient.inbound_room_id
        for patient in scenario.facility_day_demand.patients
        if patient.inbound_room_id is not None
    }
    batch_releases = _build_batch_releases_from_transport(
        transport_payloads, deliveries, clinical_mode_by_patient_id, inbound_room_id_by_patient_id,
    )

    operating_day_inputs = OperatingDayInputs(
        clinical_day_start_minute=scenario.clinical_day_start_minute,
        operating_day_minutes=scenario.operating_day_minutes,
        batch_releases=list(batch_releases),
        transport_minutes=0.0,
        injection_service_minutes=scenario.injection_service_minutes,
        uptake_minutes=scenario.uptake_minutes,
        scanner_service_minutes=scenario.scanner_service_minutes,
        injection_resources=scenario.injection_resources,
        uptake_resources=scenario.uptake_resources,
        scanners=scenario.scanners,
        distribution_concurrency=scenario.distribution_concurrency,
        blocked_injection_indices=scenario.blocked_injection_indices,
        blocked_uptake_indices=scenario.blocked_uptake_indices,
        blocked_scanner_indices=scenario.blocked_scanner_indices,
        injection_reserved_until=scenario.injection_reserved_until,
        uptake_reserved_until=scenario.uptake_reserved_until,
        scanner_reserved_until=scenario.scanner_reserved_until,
    )
    clinical_schedule = schedule_operating_day(operating_day_inputs)
    patient_traces = _build_patient_traces(
        batch_release_mappings,
        transport_payloads,
        deliveries,
        clinical_schedule,
    )

    return ProductionClinicalScheduleResult(
        scenario=scenario,
        batch_demands=batch_demands,
        scheduled_batch_demands=scheduled_batch_demands,
        unscheduled_batch_demands=unscheduled_batch_demands,
        production_schedule=production_schedule,
        batch_release_mappings=batch_release_mappings,
        released_inventory=released_inventory,
        transport_payloads=transport_payloads,
        batch_releases=batch_releases,
        transport_schedule=transport_schedule,
        operating_day_inputs=operating_day_inputs,
        clinical_schedule=clinical_schedule,
        patient_traces=patient_traces,
        transport_deliveries=deliveries,
    )

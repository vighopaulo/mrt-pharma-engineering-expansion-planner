from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from statistics import mean
from typing import Literal, Mapping, Sequence

from cyclotron_catalog import FacilityCyclotronInstance, build_fleet_from_instances, find_production_records, load_cyclotron_catalog
from cyclotron_production_windows import (
    CyclotronAsset,
    CyclotronFleet,
    CyclotronProductionCapability,
    resolve_fleet_schedule_derived_eob_capacity_mbq,
)
from decision_pipeline import (
    NativeDecisionPipelineScenario,
    NativePathwayResult,
    NativePathwayScenario,
    run_native_pathway_pipeline,
)
from diagnostics import load_radionuclide_half_lives
from facility_engineering_model import (
    CoordinateSystem,
    FacilityEngineeringObjectModel,
    SpatialCoordinate,
    SpatialEdge,
    SpatialNode,
    Space,
    network_route_distance_m,
)
from lifecycle_economics import evaluate_lifecycle_economics
from models import PlannerAssumptions, SharedNetworkAssumptions
from multi_isotope_decay import retained_fraction
from production_clinical_schedule import ConventionalTransportScheduleResult, MRTCarrierTransportScheduleResult
from stochastic_design_day import ActivityDemandModel


RoomFunction = Literal[
    "NEUTRAL_CANDIDATE_SPACE",
    "INJECTION_ADMINISTRATION",
    "UPTAKE",
    "SCANNER",
    "SUPPORT_UNUSED",
]
Pathway = Literal["Conventional", "MRT"]

FLOOR_COUNT = 8
ROOMS_PER_FLOOR = 10
PRIMARY_DEMAND = 200
DEMAND_SWEEP = (50, 100, 150, 200, 250, 300)
DEFAULT_SEED = 20260816
BENCHMARK_PRODUCTION_START_MINUTE = -240.0
BENCHMARK_PRODUCTION_END_MINUTE = 960.0
BENCHMARK_CLINICAL_START_MINUTE = 0.0
CONVENTIONAL_PAYLOAD_CAPACITY_DOSES = 5
MRT_PAYLOAD_CAPACITY_DOSES = 1
CONVENTIONAL_MAX_SCANNERS = 12
CONVENTIONAL_MAX_INJECTION_ROOMS = 16
CONVENTIONAL_MAX_UPTAKE_RESOURCES = 16


@dataclass(frozen=True)
class BenchmarkClockAssumptions:
    production_start_minute: float
    production_end_minute: float
    clinical_start_minute: float
    clinical_end_minute: float


@dataclass(frozen=True)
class BenchmarkGeometry:
    floor_count: int
    rooms_per_floor: int
    floor_to_floor_height_m: float
    corridor_room_spacing_m: float
    elevator_x_m: float
    room_ids: tuple[str, ...]
    room_floor_by_id: Mapping[str, int]
    room_coordinates_by_id: Mapping[str, SpatialCoordinate]
    production_origin_object_id: str
    release_origin_object_id: str
    base_model: FacilityEngineeringObjectModel
    building_length_m: float = 0.0
    building_width_m: float = 0.0
    gross_floor_plate_m2: float = 0.0
    total_gross_area_m2: float = 0.0
    dimension_provenance: str = "NOT_CALIBRATED"
    """Build 2R correction round (eight-storey building dimensions): explicit
    building envelope dimensions, populated by `build_benchmark_geometry` as
    SYNTHETIC_BENCHMARK_ASSUMPTION. Defaults preserve the pre-existing
    `campus_retrofit_benchmark.py` construction site (which does not model
    an explicit building envelope) as NOT_CALIBRATED/0.0, never a fabricated
    value."""


@dataclass(frozen=True)
class ProductionBasis:
    cyclotron_instance_id: str
    radiopharmacy_release_id: str
    catalog_model_id: str
    manufacturer: str
    model: str
    radionuclide: str
    release_processing_minutes: float
    calibrated_record_source: str
    calibrated_record_cycle_minutes: float
    calibrated_record_eob_mbq: float
    fleet_capacity_status: str
    fleet_capacity_mbq_per_day: float | None
    explicit_site_eob_capacity_mbq_per_day: float | None
    cyclotron_fleet: CyclotronFleet


@dataclass(frozen=True)
class CandidateLayout:
    candidate_id: str
    pattern_id: str
    active_floors: tuple[int, ...]
    scanners: int
    injection_resources: int
    uptake_resources: int
    distribution_concurrency: int
    room_assignments: Mapping[str, RoomFunction]
    floor_assignments: Mapping[int, tuple[tuple[str, RoomFunction], ...]]
    injection_rooms: tuple[str, ...]
    avg_route_distance_m: float
    max_route_distance_m: float
    avg_vertical_distance_m: float
    max_vertical_distance_m: float
    avg_vertical_transitions: float
    max_vertical_transitions: int
    guideway_horizontal_length_m: float
    guideway_vertical_length_m: float
    guideway_total_length_m: float
    guideway_transition_count: int
    anchor_injection_room_id: str
    destination_object_ids: tuple[str, ...]
    model_with_anchor: FacilityEngineeringObjectModel


@dataclass(frozen=True)
class CandidateOutcome:
    pathway: Pathway
    layout: CandidateLayout
    physically_feasible: bool
    feasibility_reason: str | None
    meets_required_demand: bool
    patients_served_per_day: int
    service_shortfall_per_day: int
    bottleneck: str
    production_batches_per_day: int
    released_payloads_per_day: int
    delivery_jobs_per_day: int
    transport_jobs_per_day: int
    active_destinations: int
    peak_simultaneous_jobs: int
    average_simultaneous_jobs: float
    transport_utilization_pct: float
    avg_transport_queue_minutes: float
    max_transport_queue_minutes: float
    transport_resource_minutes_per_day: float
    manual_transporters: int
    mrt_installed_carriers: int
    mrt_operated_carriers: int
    total_capex: float
    transport_capex: float
    annual_total_opex: float
    annual_transport_opex: float
    annual_revenue: float
    lifecycle_npv: float
    avg_release_to_injection_minutes: float
    max_release_to_injection_minutes: float
    avg_eob_to_release_minutes: float
    avg_eob_to_injection_minutes: float
    # Operational retention (section 8): computed from the ACTUAL simulated
    # release->administration timing for this candidate's executed schedule, not
    # from the best-case/no-queue geometric envelope used to pre-filter candidate rooms.
    # NOTE (retention-qualified-throughput authority build): this field is now
    # correctly gated by clinical completion (a patient who never finished the
    # clinical workflow cannot count as retention-feasible); see
    # patients_retention_qualified_completed for the explicit, disambiguated name.
    retention_feasible_patients_per_day: int
    retention_threshold: float
    avg_injection_queue_minutes: float
    # Retention-qualified-throughput authority (see RETENTION_QUALIFIED_COMPLETION_p
    # in the design-success rule): clinical completion and the 90% design criterion
    # are tracked separately and never collapsed into one generic "patients_served".
    patients_demanded: int
    patients_production_feasible: int
    patients_geometrically_retention_feasible: int
    patients_clinically_completed: int
    patients_retention_pass: int
    patients_retention_qualified_completed: int
    meets_retention_qualified_demand: bool
    # LEGACY_COMPATIBILITY / CLINICAL_CAPACITY_DIAGNOSTIC: revenue/NPV computed from
    # ALL clinically completed patients, independent of the retention design
    # criterion. Preserved for callers that need clinical-capacity economics, but is
    # NOT the primary authority for the retention-constrained design comparison.
    clinical_completion_revenue_potential: float
    # PRIMARY authority for the retention-constrained economic comparison: revenue
    # and NPV computed from patients_retention_qualified_completed only, reusing the
    # same authoritative evaluate_lifecycle_economics formula/assumptions (CapEx,
    # OPEX, revenue_per_scan, discount rate, horizon) -- no new economic model invented.
    qualified_annual_revenue: float
    qualified_lifecycle_npv: float
    pathway_result: NativePathwayResult


@dataclass(frozen=True)
class PathwayOptimizationResult:
    pathway: Pathway
    demand: int
    evaluated_candidates: int
    rejected_candidates: int
    demand_failing_candidates: int
    demand_meeting_candidates: int
    winner: CandidateOutcome
    runner_up: CandidateOutcome | None
    winner_reason: str
    outcomes: tuple[CandidateOutcome, ...]


@dataclass(frozen=True)
class DemandSweepRow:
    demand: int
    conventional_served: int
    conventional_floors_used: int
    conventional_scanners: int
    conventional_transport_burden: float
    mrt_served: int
    mrt_floors_used: int
    mrt_scanners: int
    mrt_transport_burden: float
    conventional_avg_release_to_injection_minutes: float
    conventional_max_release_to_injection_minutes: float
    conventional_avg_transport_queue_minutes: float
    conventional_transport_utilization_pct: float
    mrt_avg_release_to_injection_minutes: float
    mrt_max_release_to_injection_minutes: float
    mrt_avg_transport_queue_minutes: float
    mrt_transport_utilization_pct: float


@dataclass(frozen=True)
class ProductionCapacityGateRow:
    demand: int
    pathway: Pathway
    required_batches: int
    feasible_scheduled_batches: int
    unscheduled_batches: int
    required_administered_activity_mbq: float
    required_release_activity_mbq: float
    required_eob_activity_mbq: float
    schedule_derived_feasible_eob_capacity_mbq: float | None
    explicit_site_capacity_mbq_per_day: float | None
    available_eob_capacity_mbq_per_day: float | None
    capacity_status: str
    # Narrower flag: does the required EOB activity for scheduled/feasible patients fit
    # within the schedule-derived capacity? This can be True even when whole-demand
    # production is not feasible (e.g. some batches remain unscheduled).
    scheduled_activity_fits_capacity: bool
    # Demand-layer authoritative required EOB activity (cycle-relative; see
    # cycle_relative_production_requirement.py), summed across all patients assigned to
    # a physically required, feasible production cycle -- independent of whether every
    # such cycle could actually be scheduled within the production horizon.
    demand_layer_required_eob_activity_mbq: float
    # Patients for whom no candidate production cycle could supply activity in time.
    unassigned_patient_production_demand_count: int
    # NON-AUTHORITATIVE DIAGNOSTIC ONLY: previous common-early-EOB heuristic, retained
    # only for regression comparison. Must never drive scheduling/feasibility/economics.
    non_authoritative_common_early_eob_activity_mbq: float
    non_authoritative_common_early_eob_implied_cycle_count: int
    # Whole-demand production feasibility: True only when every production-required
    # patient is both assigned to a feasible cycle AND that cycle's batch was actually
    # scheduled within the production horizon (no unscheduled batches, no unassigned
    # patient production demand, and scheduled activity fits capacity).
    production_feasible: bool
    # PLANNED_EOB_REQUIREMENT: demand-layer cycle-relative requirement using provisional
    # admin timing and idealized freshest-candidate-cycle assignment (same value as
    # demand_layer_required_eob_activity_mbq, named explicitly per the reconciliation
    # semantic model).
    planned_required_eob_activity_mbq: float
    # REALIZED_EOB_REQUIREMENT: requirement recomputed from the actual scheduled
    # production/transport/clinical timing (same value as required_eob_activity_mbq).
    realized_required_eob_activity_mbq: float
    # FINAL_RECONCILED_EOB_REQUIREMENT: the physically authoritative requirement after
    # the bounded schedule-refinement loop converged. Never forced to equal planned.
    final_reconciled_required_eob_activity_mbq: float
    unused_production_headroom_mbq: float | None
    production_requirement_convergence_status: str
    production_requirement_reconciliation_iterations: int
    production_requirement_max_relative_difference: float


RetentionStatus = Literal["RETENTION_FEASIBLE", "RETENTION_INFEASIBLE"]


@dataclass(frozen=True)
class RoomRetentionRecord:
    """Traceability record for one candidate room's RELEASE -> ADMINISTRATION retention.

    This is a PROJECT DESIGN CRITERION baseline: transport_minutes is the pathway's
    physically-modeled (not distance-alone) route time to this room at minimum queueing
    (a transporter/carrier immediately available). It reuses the same
    _manual_transport_minutes/_mrt_transport_minutes physics used for real scheduling.
    The actually-realized per-patient release-to-injection time (which includes real
    queueing) is tracked separately via patient decay traces once a layout is executed.
    """

    room_id: str
    floor: int
    pathway: Pathway
    radionuclide: str
    half_life_minutes: float
    route_distance_m: float
    vertical_transitions: int
    transport_minutes: float
    release_to_administration_minutes: float
    retained_fraction: float
    threshold: float
    status: RetentionStatus


@dataclass(frozen=True)
class RetentionEnvelope:
    pathway: Pathway
    radionuclide: str
    half_life_minutes: float
    threshold: float
    records_by_room_id: Mapping[str, RoomRetentionRecord]
    feasible_room_ids: frozenset[str]
    feasible_floors: frozenset[int]


def _retention_time_budget_minutes(*, half_life_minutes: float, threshold: float) -> float:
    """Maximum release->administration elapsed minutes consistent with `threshold`."""
    if not (0.0 < threshold <= 1.0):
        raise ValueError("threshold must be within (0, 1]")
    return half_life_minutes * math.log2(1.0 / threshold)


def compute_retention_envelope(
    *,
    geometry: BenchmarkGeometry,
    assumptions: PlannerAssumptions,
    radionuclide: str,
    pathway: Pathway,
    threshold: float | None = None,
) -> RetentionEnvelope:
    """Determine which candidate rooms satisfy the common RELEASE->ADMINISTRATION
    retention rule (project design criterion, default 90%) for this pathway, reusing
    the repository's authoritative decay engine (retained_fraction) and the same
    transport-time physics used for real scheduling.
    """
    effective_threshold = (
        float(assumptions.minimum_release_to_administration_retention_fraction) if threshold is None else float(threshold)
    )
    if not (0.0 < effective_threshold <= 1.0):
        raise ValueError("threshold must be within (0, 1]")

    half_life_minutes = float(load_radionuclide_half_lives()[radionuclide])

    (
        distance_by_room,
        _vertical_by_room,
        transitions_by_room,
        manual_minutes_by_room,
        mrt_minutes_by_room,
        _path_edges_by_room,
    ) = _route_metrics_for_rooms(geometry, geometry.room_ids, assumptions)

    records: dict[str, RoomRetentionRecord] = {}
    feasible_room_ids: set[str] = set()
    for room_id in geometry.room_ids:
        transport_minutes = (
            manual_minutes_by_room[room_id] if pathway == "Conventional" else mrt_minutes_by_room[room_id]
        )
        retained = retained_fraction(max(0.0, transport_minutes), half_life_minutes)
        status: RetentionStatus = "RETENTION_FEASIBLE" if retained >= effective_threshold else "RETENTION_INFEASIBLE"
        if status == "RETENTION_FEASIBLE":
            feasible_room_ids.add(room_id)
        records[room_id] = RoomRetentionRecord(
            room_id=room_id,
            floor=geometry.room_floor_by_id[room_id],
            pathway=pathway,
            radionuclide=radionuclide,
            half_life_minutes=half_life_minutes,
            route_distance_m=distance_by_room[room_id],
            vertical_transitions=transitions_by_room[room_id],
            transport_minutes=transport_minutes,
            release_to_administration_minutes=transport_minutes,
            retained_fraction=retained,
            threshold=effective_threshold,
            status=status,
        )

    feasible_floors = frozenset(records[room_id].floor for room_id in feasible_room_ids)
    return RetentionEnvelope(
        pathway=pathway,
        radionuclide=radionuclide,
        half_life_minutes=half_life_minutes,
        threshold=effective_threshold,
        records_by_room_id=records,
        feasible_room_ids=frozenset(feasible_room_ids),
        feasible_floors=feasible_floors,
    )


@dataclass(frozen=True)
class RepresentativeTimeline:
    pathway: Pathway
    patient_id: str
    batch_id: int
    production_window_end_minutes: float
    release_minutes: float
    transport_queue_start_minutes: float
    transport_dispatch_minutes: float
    transport_arrival_minutes: float
    injection_resource_wait_minutes: float
    injection_start_minutes: float
    injection_end_minutes: float
    uptake_end_minutes: float
    scan_start_minutes: float
    scan_end_minutes: float
    elapsed_eob_to_release_minutes: float
    elapsed_release_to_injection_minutes: float
    elapsed_eob_to_injection_minutes: float
    elapsed_eob_to_scan_completion_minutes: float


@dataclass(frozen=True)
class SpatialBenchmarkResult:
    geometry: BenchmarkGeometry
    production_basis: ProductionBasis
    clock_assumptions: BenchmarkClockAssumptions
    assumptions: PlannerAssumptions
    primary_demand: int
    conventional_primary: PathwayOptimizationResult
    mrt_primary: PathwayOptimizationResult
    demand_sweep: tuple[DemandSweepRow, ...]
    production_capacity_gate_rows: tuple[ProductionCapacityGateRow, ...]
    representative_timelines: tuple[RepresentativeTimeline, ...]
    equal_budget_secondary_status: str
    reproducibility_fingerprint: str
    conventional_retention_envelope: RetentionEnvelope
    mrt_retention_envelope: RetentionEnvelope


def _room_id(floor: int, slot: int) -> str:
    return f"F{floor}-R{slot:02d}"


def build_benchmark_geometry(
    *,
    floor_count: int = FLOOR_COUNT,
    rooms_per_floor: int = ROOMS_PER_FLOOR,
    floor_to_floor_height_m: float = 4.0,
    corridor_room_spacing_m: float = 6.0,
    building_length_m: float | None = None,
    building_width_m: float | None = None,
    distribute_both_sides: bool = False,
) -> BenchmarkGeometry:
    """Build the synthetic benchmark geometry. Defaults reproduce BASELINE_CONTROL
    (8 floors, 10 rooms/floor, 4m floor height, 6m room spacing) exactly; callers
    may override any dimension to generate deterministic scale-sensitivity variants
    (see build_scaled_benchmark_geometry).

    `distribute_both_sides=False` (default) preserves the ORIGINAL single-row
    corridor layout bit-for-bit (every existing caller/test unaffected).
    `distribute_both_sides=True` (Build 2R eight-storey building dimensions,
    SYNTHETIC_BENCHMARK_ASSUMPTION) distributes `rooms_per_floor` on BOTH
    SIDES of a central longitudinal corridor spanning `building_length_m`,
    with each room offset laterally by `building_width_m / 4.0` (a
    disclosed "room centered within its half of the building width"
    assumption) -- this lateral offset is added into the room's routed
    horizontal distance (Manhattan: along-corridor + lateral), so the width
    dimension genuinely affects routed distance/retention/CapEx, never only
    presentation. `building_width_m` is required when `distribute_both_sides`
    is True (no silent default -- the caller must state the width being modeled).
    """
    if distribute_both_sides and building_width_m is None:
        raise ValueError("distribute_both_sides=True requires an explicit building_width_m")
    floor_height_m = floor_to_floor_height_m
    room_spacing_m = corridor_room_spacing_m
    elevator_x_m = 0.0

    room_ids: list[str] = []
    room_floor_by_id: dict[str, int] = {}
    room_coordinates_by_id: dict[str, SpatialCoordinate] = {}
    nodes: list[SpatialNode] = []
    edges: list[SpatialEdge] = []
    spaces: list[Space] = []

    coordinate_system = CoordinateSystem(
        coordinate_system_id="BENCHMARK-CS-001",
        name="Synthetic 8-floor benchmark",
        building="Benchmark Clinical Tower",
        local_coordinate_system="BENCHMARK_LOCAL",
        source_coordinate_reference="synthetic",
        scale_m_per_unit=1.0,
    )

    production_node_id = "NODE-RP-001"
    production_object_id = "RP-001"
    nodes.append(
        SpatialNode(
            node_id=production_node_id,
            object_id=production_object_id,
            kind="equipment",
            coordinate=SpatialCoordinate(
                x_m=0.0,
                y_m=0.0,
                z_m=0.0,
                building="Production Building",
                storey="LEVEL 0",
                local_coordinate_system="BENCHMARK_LOCAL",
                source_coordinate_reference="synthetic",
            ),
            evidence_class="BENCHMARK_ASSUMED",
            confidence="HIGH",
        )
    )

    lobby_node_ids: dict[int, str] = {}
    for floor in range(0, floor_count + 1):
        node_id = f"NODE-LOBBY-L{floor}"
        lobby_node_ids[floor] = node_id
        nodes.append(
            SpatialNode(
                node_id=node_id,
                object_id=f"LOBBY-L{floor}",
                kind="junction",
                coordinate=SpatialCoordinate(
                    x_m=elevator_x_m,
                    y_m=0.0,
                    z_m=floor * floor_height_m,
                    building="Benchmark Clinical Tower",
                    storey=f"LEVEL {floor}",
                    local_coordinate_system="BENCHMARK_LOCAL",
                    source_coordinate_reference="synthetic",
                ),
                evidence_class="BENCHMARK_ASSUMED",
                confidence="HIGH",
            )
        )

    edges.append(
        SpatialEdge(
            edge_id="EDGE-RP-TO-LOBBY-L0",
            source_node_id=production_node_id,
            destination_node_id=lobby_node_ids[0],
            length_m=3.0,
            vertical_change_m=0.0,
            edge_type="HORIZONTAL",
            route_corridor_class="INTERIOR_CLINICAL_PATH",
            evidence_class="BENCHMARK_ASSUMED",
            confidence="HIGH",
        )
    )

    for floor in range(1, floor_count + 1):
        edges.append(
            SpatialEdge(
                edge_id=f"EDGE-ELEV-L{floor-1}-L{floor}",
                source_node_id=lobby_node_ids[floor - 1],
                destination_node_id=lobby_node_ids[floor],
                length_m=floor_height_m,
                vertical_change_m=floor_height_m,
                edge_type="ELEVATOR",
                route_corridor_class="VERTICAL_GUIDEWAY",
                evidence_class="BENCHMARK_ASSUMED",
                confidence="HIGH",
            )
        )

    rooms_per_side = math.ceil(rooms_per_floor / 2) if distribute_both_sides else rooms_per_floor
    corridor_length_m = building_length_m if building_length_m is not None else rooms_per_floor * room_spacing_m
    along_spacing_m = (corridor_length_m / (rooms_per_side + 1)) if distribute_both_sides else room_spacing_m
    lateral_offset_m = (building_width_m / 4.0) if distribute_both_sides else 0.0

    for floor in range(1, floor_count + 1):
        for slot in range(1, rooms_per_floor + 1):
            rid = _room_id(floor, slot)
            room_ids.append(rid)
            room_floor_by_id[rid] = floor
            z = floor * floor_height_m
            if distribute_both_sides:
                side_a = slot <= rooms_per_side
                position_within_side = slot if side_a else slot - rooms_per_side
                along_corridor_m = position_within_side * along_spacing_m
                y = lateral_offset_m if side_a else -lateral_offset_m
                # Manhattan routed distance: along the corridor to this position, then laterally into the room --
                # this is what genuinely makes the width dimension affect routed distance, never presentation-only.
                route_length_m = along_corridor_m + lateral_offset_m
            else:
                along_corridor_m = slot * room_spacing_m
                y = 0.0
                route_length_m = along_corridor_m
            x = along_corridor_m
            room_coordinates_by_id[rid] = SpatialCoordinate(
                x_m=x,
                y_m=y,
                z_m=z,
                building="Benchmark Clinical Tower",
                storey=f"LEVEL {floor}",
                local_coordinate_system="BENCHMARK_LOCAL",
                source_coordinate_reference="synthetic",
            )

            spaces.append(
                Space(
                    object_id=rid,
                    name=f"Room {rid}",
                    source_identifier=None,
                    evidence_class="BENCHMARK_ASSUMED",
                    confidence="HIGH",
                    status="NEW_CANDIDATE",
                    building_id="B-CLINICAL",
                    storey_id=f"LEVEL-{floor}",
                    notes=("NEUTRAL_CANDIDATE_SPACE",),
                )
            )

            room_node_id = f"NODE-{rid}"
            nodes.append(
                SpatialNode(
                    node_id=room_node_id,
                    object_id=rid,
                    kind="space",
                    coordinate=room_coordinates_by_id[rid],
                    evidence_class="BENCHMARK_ASSUMED",
                    confidence="HIGH",
                    building_id="B-CLINICAL",
                    storey_id=f"LEVEL-{floor}",
                    room_id=rid,
                    notes=("NEUTRAL_CANDIDATE_SPACE",),
                )
            )
            edges.append(
                SpatialEdge(
                    edge_id=f"EDGE-LOBBY-L{floor}-TO-{rid}",
                    source_node_id=lobby_node_ids[floor],
                    destination_node_id=room_node_id,
                    length_m=route_length_m,
                    vertical_change_m=0.0,
                    edge_type="HORIZONTAL",
                    route_corridor_class="INTERIOR_CLINICAL_PATH",
                    evidence_class="BENCHMARK_ASSUMED",
                    confidence="HIGH",
                )
            )

    base_model = FacilityEngineeringObjectModel(
        facility_id="FAC-BENCHMARK-8F80R",
        facility_name="8-floor / 80-room synthetic benchmark",
        project_spatial_mode="RETROFIT",
        source_type="BENCHMARK",
        evidence_class="BENCHMARK_ASSUMED",
        maturity="CONCEPTUAL",
        subscription_tier="BASIC",
        coordinate_system=coordinate_system,
        spaces=tuple(spaces),
        nodes=tuple(nodes),
        edges=tuple(edges),
        primary_route_origin_object_id=production_object_id,
        primary_route_destination_object_ids=(_room_id(1, 1),),
        route_geometry_status="RECONSTRUCTED",
        route_distance_source="DERIVED_GEOMETRY",
        clinical_floors_in_scope=floor_count,
        scanner_floors=tuple(f"LEVEL {floor}" for floor in range(1, floor_count + 1)),
        injection_floors=tuple(f"LEVEL {floor}" for floor in range(1, floor_count + 1)),
        uptake_floors=tuple(f"LEVEL {floor}" for floor in range(1, floor_count + 1)),
        include_ground_floor=True,
        notes=(
            "Deterministic synthetic facility for pathway benchmark comparison.",
            "CY-001 and RP-001 treated as existing fixed assets at production Level 0.",
            "All clinical rooms begin as NEUTRAL_CANDIDATE_SPACE.",
        ),
    )

    resolved_width_m = building_width_m if distribute_both_sides else 0.0
    resolved_width_m = resolved_width_m if resolved_width_m is not None else 0.0
    gross_floor_plate_m2 = corridor_length_m * resolved_width_m
    return BenchmarkGeometry(
        floor_count=floor_count,
        rooms_per_floor=rooms_per_floor,
        floor_to_floor_height_m=floor_height_m,
        corridor_room_spacing_m=room_spacing_m,
        elevator_x_m=elevator_x_m,
        room_ids=tuple(sorted(room_ids)),
        room_floor_by_id=room_floor_by_id,
        room_coordinates_by_id=room_coordinates_by_id,
        production_origin_object_id="CY-001",
        release_origin_object_id=production_object_id,
        base_model=base_model,
        building_length_m=corridor_length_m,
        building_width_m=resolved_width_m,
        gross_floor_plate_m2=gross_floor_plate_m2,
        total_gross_area_m2=gross_floor_plate_m2 * floor_count,
        dimension_provenance="SYNTHETIC_BENCHMARK_ASSUMPTION" if distribute_both_sides else "NOT_CALIBRATED",
    )


def build_scaled_benchmark_geometry(
    *,
    horizontal_scale: float = 1.0,
    floor_count: int = FLOOR_COUNT,
) -> BenchmarkGeometry:
    """Deterministic synthetic geometry variant for scale-sensitivity study
    (section 31): scales BASELINE_CONTROL's room/corridor spacing by
    `horizontal_scale` and/or the floor count, holding rooms_per_floor and
    floor_to_floor_height_m fixed at baseline values. horizontal_scale=1.0 and
    floor_count=FLOOR_COUNT reproduces BASELINE_CONTROL exactly.
    """
    return build_benchmark_geometry(
        floor_count=floor_count,
        rooms_per_floor=ROOMS_PER_FLOOR,
        floor_to_floor_height_m=4.0,
        corridor_room_spacing_m=6.0 * horizontal_scale,
    )


def _shortest_path_edges(model: FacilityEngineeringObjectModel, start_node_id: str, end_node_id: str) -> tuple[SpatialEdge, ...]:
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


def _node_ids_by_object_id(model: FacilityEngineeringObjectModel) -> dict[str, str]:
    node_ids: dict[str, str] = {}
    for node in model.nodes:
        node_ids[node.node_id] = node.node_id
        if node.object_id:
            node_ids[node.object_id] = node.node_id
    return node_ids


def _manual_transport_minutes(distance_m: float, vertical_m: float, assumptions: PlannerAssumptions) -> float:
    horizontal_m = max(0.0, distance_m - vertical_m)
    horizontal_minutes = horizontal_m / max(assumptions.manual_transport_speed_m_per_s * 60.0, 1e-12)
    elevator_minutes = 0.0
    if vertical_m > 0.0:
        elevator_minutes = (
            assumptions.manual_transport_elevator_wait_minutes
            + assumptions.manual_transport_elevator_loading_minutes
            + vertical_m / max(assumptions.manual_transport_elevator_speed_m_per_s * 60.0, 1e-12)
        )
    return (
        assumptions.manual_transport_pickup_minutes
        + horizontal_minutes
        + elevator_minutes
        + assumptions.manual_transport_handoff_minutes
    )


def _mrt_transport_minutes(distance_m: float, vertical_m: float, transitions: int, assumptions: PlannerAssumptions) -> float:
    horizontal_m = max(0.0, distance_m - vertical_m)
    horizontal_seconds = horizontal_m / max(assumptions.mrt_horizontal_speed_m_per_s, 1e-12)
    vertical_seconds = vertical_m / max(assumptions.mrt_vertical_speed_m_per_s, 1e-12)
    transition_seconds = transitions * assumptions.mrt_transition_time_seconds
    station_seconds = assumptions.mrt_station_loading_time_seconds + assumptions.mrt_station_unloading_time_seconds
    return (horizontal_seconds + vertical_seconds + transition_seconds + station_seconds) / 60.0


def _physical_motion_mode_sequence(path_edges: Sequence[SpatialEdge]) -> tuple[str, ...]:
    """Compress a raw graph-edge path into physical MRT motion modes: "H" for
    horizontal guideway travel, "V" for vertical guideway/elevator travel, merging
    consecutive edges of the same mode. Graph edges are a routing/topology artifact
    (this benchmark represents each floor-to-floor elevator hop as its own edge so
    partial-height routes can be composed); this compression reflects the actual
    number of times the carrier physically changes between horizontal and vertical
    motion, not how many edges the graph happens to segment the route into.
    """
    modes: list[str] = []
    for edge in path_edges:
        mode = "V" if abs(float(edge.vertical_change_m)) > 0.0 else "H"
        if not modes or modes[-1] != mode:
            modes.append(mode)
    return tuple(modes)


def _physical_transition_count(path_edges: Sequence[SpatialEdge]) -> int:
    """Number of genuine H<->V directional transitions along the physically
    compressed motion-mode sequence (see _physical_motion_mode_sequence), not the
    number of vertical graph edges traversed.
    """
    modes = _physical_motion_mode_sequence(path_edges)
    return max(0, len(modes) - 1)


def _route_metrics_for_rooms(
    geometry: BenchmarkGeometry,
    room_ids: Sequence[str],
    assumptions: PlannerAssumptions,
) -> tuple[
    Mapping[str, float],
    Mapping[str, float],
    Mapping[str, int],
    Mapping[str, float],
    Mapping[str, float],
    Mapping[str, tuple[SpatialEdge, ...]],
]:
    node_ids = _node_ids_by_object_id(geometry.base_model)
    start_node_id = node_ids[geometry.release_origin_object_id]
    node_map = {node.node_id: node for node in geometry.base_model.nodes}

    distance_by_room: dict[str, float] = {}
    vertical_by_room: dict[str, float] = {}
    transitions_by_room: dict[str, int] = {}
    manual_minutes_by_room: dict[str, float] = {}
    mrt_minutes_by_room: dict[str, float] = {}
    path_edges_by_room: dict[str, tuple[SpatialEdge, ...]] = {}

    for room_id in room_ids:
        end_node_id = node_ids[room_id]
        distance = network_route_distance_m(node_map, geometry.base_model.edges, start_node_id, end_node_id)
        path_edges = _shortest_path_edges(geometry.base_model, start_node_id, end_node_id)
        vertical = sum(abs(float(edge.vertical_change_m)) for edge in path_edges)
        # Physical H<->V transitions follow motion-mode changes, not graph-edge count
        # (audit: MRT H<->V transition semantics, section 16) -- see _physical_transition_count.
        transitions = _physical_transition_count(path_edges)
        distance_by_room[room_id] = float(distance)
        vertical_by_room[room_id] = float(vertical)
        transitions_by_room[room_id] = int(transitions)
        manual_minutes_by_room[room_id] = _manual_transport_minutes(distance, vertical, assumptions)
        mrt_minutes_by_room[room_id] = _mrt_transport_minutes(distance, vertical, transitions, assumptions)
        path_edges_by_room[room_id] = path_edges

    return (
        distance_by_room,
        vertical_by_room,
        transitions_by_room,
        manual_minutes_by_room,
        mrt_minutes_by_room,
        path_edges_by_room,
    )


def build_production_basis(
    *,
    radionuclide: str = "F-18",
    catalog_model_id: str = "GE_PETTRACE_890",
    release_processing_minutes: float = 71.0,
    cyclotron_instance_id: str = "CY-001",
    radiopharmacy_release_id: str = "RP-001",
) -> ProductionBasis:
    catalog = load_cyclotron_catalog()
    model = catalog.by_id(catalog_model_id)

    instance = FacilityCyclotronInstance(
        instance_id=cyclotron_instance_id,
        catalog_model_id=catalog_model_id,
    )
    fleet, warnings = build_fleet_from_instances(catalog=catalog, instances=(instance,))
    if warnings:
        raise ValueError(f"Failed to build benchmark fleet: {warnings}")
    if fleet is None or len(fleet.assets) != 1:
        raise ValueError(f"Benchmark requires exactly one cyclotron asset ({cyclotron_instance_id})")

    base_asset = fleet.assets[0]
    capability = base_asset.capability
    release_map = {radionuclide: float(release_processing_minutes)}

    enriched_capability = CyclotronProductionCapability(
        cyclotron_id=capability.cyclotron_id,
        supported_radionuclides=capability.supported_radionuclides,
        max_simultaneous_production_streams=capability.max_simultaneous_production_streams,
        production_cycle_minutes_by_radionuclide=capability.production_cycle_minutes_by_radionuclide,
        simultaneously_compatible_radionuclide_sets=capability.simultaneously_compatible_radionuclide_sets,
        release_processing_minutes_by_radionuclide=release_map,
        calibrated_eob_activity_mbq_by_radionuclide=capability.calibrated_eob_activity_mbq_by_radionuclide,
        site_eob_capacity_mbq_per_day=capability.site_eob_capacity_mbq_per_day,
    )

    enriched_asset = CyclotronAsset(
        cyclotron_id=base_asset.cyclotron_id,
        capability=enriched_capability,
        model_identifier=base_asset.model_identifier,
        manufacturer=base_asset.manufacturer,
        installed_quantity=base_asset.installed_quantity,
        capability_provenance=base_asset.capability_provenance,
    )
    enriched_fleet = CyclotronFleet(assets=(enriched_asset,), fleet_id=f"BENCHMARK_{cyclotron_instance_id}")

    records = find_production_records(catalog=catalog, catalog_model_id=catalog_model_id, radionuclide=radionuclide)
    calibrated_record = next((record for record in records if record.normalized_eob_activity_mbq is not None), None)
    if calibrated_record is None:
        raise ValueError(f"No calibrated {radionuclide} production record for model {catalog_model_id}")

    explicit_site_capacity = enriched_capability.site_eob_capacity_mbq_per_day
    capacity_status = "EXPLICIT_SITE_DAILY_CAPACITY" if explicit_site_capacity is not None else "CALIBRATED_PER_CYCLE_ONLY"

    return ProductionBasis(
        cyclotron_instance_id=cyclotron_instance_id,
        radiopharmacy_release_id=radiopharmacy_release_id,
        catalog_model_id=catalog_model_id,
        manufacturer=model.manufacturer,
        model=model.model,
        radionuclide=radionuclide,
        release_processing_minutes=float(release_processing_minutes),
        calibrated_record_source=calibrated_record.source,
        calibrated_record_cycle_minutes=float(calibrated_record.irradiation_time_minutes or 0.0),
        calibrated_record_eob_mbq=float(calibrated_record.normalized_eob_activity_mbq),
        fleet_capacity_status=capacity_status,
        fleet_capacity_mbq_per_day=explicit_site_capacity,
        explicit_site_eob_capacity_mbq_per_day=explicit_site_capacity,
        cyclotron_fleet=enriched_fleet,
    )


def _capacity_per_scanner(assumptions: PlannerAssumptions) -> float:
    return (
        assumptions.operating_hours_per_day
        * 60.0
        / assumptions.scanner_cycle_min
        * assumptions.scanner_availability_pct
        / 100.0
    )


def _capacity_per_injection_room(assumptions: PlannerAssumptions) -> float:
    return assumptions.operating_hours_per_day * 60.0 / assumptions.injection_cycle_min


def _capacity_per_uptake_room(assumptions: PlannerAssumptions) -> float:
    return assumptions.operating_hours_per_day * 60.0 / assumptions.uptake_cycle_min


def _resource_requirements_for_demand(demand: int, assumptions: PlannerAssumptions) -> tuple[int, int, int]:
    scanners = max(1, math.ceil(demand / max(_capacity_per_scanner(assumptions), 1e-12)))
    injection = max(1, math.ceil(demand / max(_capacity_per_injection_room(assumptions), 1e-12)))
    uptake = max(1, math.ceil(demand / max(_capacity_per_uptake_room(assumptions), 1e-12)))
    return scanners, injection, uptake


def _active_floor_patterns(floor_count: int = FLOOR_COUNT) -> tuple[tuple[int, ...], ...]:
    raw_patterns = [
        (1,),
        (1, 2),
        (1, 2, 3),
        (1, 2, 3, 4),
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6, 7, 8),
        (2, 3, 4, 5),
        (5, 6, 7, 8),
        (1, 3, 5, 7),
        (2, 4, 6, 8),
        (1, 4, 8),
        tuple(range(1, floor_count + 1)),
    ]
    seen: set[tuple[int, ...]] = set()
    patterns: list[tuple[int, ...]] = []
    for pattern in raw_patterns:
        normalized = tuple(sorted(set(int(floor) for floor in pattern if 1 <= int(floor) <= floor_count)))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        patterns.append(normalized)
    return tuple(patterns)


def _floors_are_contiguous(floors: tuple[int, ...]) -> bool:
    if not floors:
        return False
    return floors == tuple(range(min(floors), max(floors) + 1))


def _distribute_count(total: int, floors: tuple[int, ...], mode: Literal["clustered", "balanced"]) -> dict[int, int]:
    allocation = {floor: 0 for floor in floors}
    if total <= 0:
        return allocation
    if mode == "clustered":
        remaining = total
        for floor in floors:
            if remaining <= 0:
                break
            take = remaining
            allocation[floor] += take
            remaining -= take
        return allocation

    index = 0
    ordered = list(floors)
    while index < total:
        floor = ordered[index % len(ordered)]
        allocation[floor] += 1
        index += 1
    return allocation


def _assign_rooms_for_candidate(
    *,
    geometry: BenchmarkGeometry,
    active_floors: tuple[int, ...],
    scanners: int,
    injections: int,
    uptake: int,
    distribution_mode: Literal["clustered", "balanced"],
    assumptions: PlannerAssumptions,
    candidate_id: str,
    pattern_id: str,
    distribution_concurrency: int,
    feasible_room_ids: frozenset[str] | None = None,
) -> CandidateLayout | None:
    if scanners <= 0 or injections <= 0 or uptake <= 0:
        return None

    if feasible_room_ids is not None:
        # A floor with zero retention-feasible rooms cannot host any clinical resource:
        # nothing there could ever receive released material with adequate retention.
        feasible_floors = {geometry.room_floor_by_id[rid] for rid in feasible_room_ids}
        if any(floor not in feasible_floors for floor in active_floors):
            return None

    rooms_by_floor: dict[int, list[str]] = {
        floor: sorted(rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] == floor)
        for floor in active_floors
    }

    scanner_alloc = _distribute_count(scanners, active_floors, distribution_mode)
    injection_alloc = _distribute_count(injections, active_floors, distribution_mode)
    uptake_alloc = _distribute_count(uptake, active_floors, distribution_mode)

    room_assignments: dict[str, RoomFunction] = {rid: "NEUTRAL_CANDIDATE_SPACE" for rid in geometry.room_ids}
    floor_assignments: dict[int, list[tuple[str, RoomFunction]]] = {floor: [] for floor in range(1, geometry.floor_count + 1)}
    injection_rooms: list[str] = []

    for floor in active_floors:
        scanner_n = scanner_alloc.get(floor, 0)
        injection_n = injection_alloc.get(floor, 0)
        uptake_n = uptake_alloc.get(floor, 0)
        if scanner_n + injection_n + uptake_n > geometry.rooms_per_floor:
            return None

        cursor = 0
        floor_rooms = rooms_by_floor[floor]

        for _ in range(scanner_n):
            rid = floor_rooms[cursor]
            cursor += 1
            room_assignments[rid] = "SCANNER"
            floor_assignments[floor].append((rid, "SCANNER"))

        # The injection/administration room is the critical retention delivery endpoint
        # (section 16): when a retention envelope is supplied, only retention-feasible
        # rooms may be selected here, skipping infeasible ones deterministically in slot
        # order rather than silently including them.
        floor_injection_count = 0
        while floor_injection_count < injection_n:
            if cursor >= len(floor_rooms):
                return None
            rid = floor_rooms[cursor]
            cursor += 1
            if feasible_room_ids is not None and rid not in feasible_room_ids:
                room_assignments[rid] = "SUPPORT_UNUSED"
                floor_assignments[floor].append((rid, "SUPPORT_UNUSED"))
                continue
            room_assignments[rid] = "INJECTION_ADMINISTRATION"
            floor_assignments[floor].append((rid, "INJECTION_ADMINISTRATION"))
            injection_rooms.append(rid)
            floor_injection_count += 1

        for _ in range(uptake_n):
            if cursor >= len(floor_rooms):
                return None
            rid = floor_rooms[cursor]
            cursor += 1
            room_assignments[rid] = "UPTAKE"
            floor_assignments[floor].append((rid, "UPTAKE"))

        for rid in floor_rooms[cursor:]:
            room_assignments[rid] = "SUPPORT_UNUSED"
            floor_assignments[floor].append((rid, "SUPPORT_UNUSED"))

    if len(injection_rooms) != injections:
        return None

    (
        distance_by_room,
        vertical_by_room,
        transitions_by_room,
        _manual_minutes_by_room,
        _mrt_minutes_by_room,
        path_edges_by_room,
    ) = _route_metrics_for_rooms(geometry, injection_rooms, assumptions)

    distances = [distance_by_room[rid] for rid in injection_rooms]
    verticals = [vertical_by_room[rid] for rid in injection_rooms]
    transition_values = [transitions_by_room[rid] for rid in injection_rooms]

    avg_distance = mean(distances)
    anchor_room = sorted(injection_rooms, key=lambda rid: (abs(distance_by_room[rid] - avg_distance), rid))[0]

    guideway_edge_ids: set[str] = set()
    guideway_horizontal = 0.0
    guideway_vertical = 0.0
    for rid in injection_rooms:
        for edge in path_edges_by_room[rid]:
            if edge.edge_id in guideway_edge_ids:
                continue
            guideway_edge_ids.add(edge.edge_id)
            vertical = abs(float(edge.vertical_change_m))
            guideway_vertical += vertical
            guideway_horizontal += max(0.0, float(edge.length_m) - vertical)

    injection_floors = tuple(sorted({geometry.room_floor_by_id[rid] for rid in injection_rooms}))
    scanner_floors = tuple(sorted({floor for floor, entries in floor_assignments.items() if any(fn == "SCANNER" for _, fn in entries)}))
    uptake_floors = tuple(sorted({floor for floor, entries in floor_assignments.items() if any(fn == "UPTAKE" for _, fn in entries)}))

    destination_object_ids = tuple(sorted(injection_rooms))
    model_with_anchor = replace(
        geometry.base_model,
        primary_route_destination_object_ids=destination_object_ids,
        scanner_floors=tuple(f"LEVEL {floor}" for floor in scanner_floors),
        injection_floors=tuple(f"LEVEL {floor}" for floor in injection_floors),
        uptake_floors=tuple(f"LEVEL {floor}" for floor in uptake_floors),
    )

    return CandidateLayout(
        candidate_id=candidate_id,
        pattern_id=pattern_id,
        active_floors=active_floors,
        scanners=scanners,
        injection_resources=injections,
        uptake_resources=uptake,
        distribution_concurrency=max(1, distribution_concurrency),
        room_assignments=room_assignments,
        floor_assignments={floor: tuple(entries) for floor, entries in floor_assignments.items()},
        injection_rooms=tuple(sorted(injection_rooms)),
        avg_route_distance_m=avg_distance,
        max_route_distance_m=max(distances),
        avg_vertical_distance_m=mean(verticals),
        max_vertical_distance_m=max(verticals),
        avg_vertical_transitions=mean(float(value) for value in transition_values),
        max_vertical_transitions=max(transition_values),
        guideway_horizontal_length_m=guideway_horizontal,
        guideway_vertical_length_m=guideway_vertical,
        guideway_total_length_m=guideway_horizontal + guideway_vertical,
        guideway_transition_count=sum(transition_values),
        anchor_injection_room_id=anchor_room,
        destination_object_ids=destination_object_ids,
        model_with_anchor=model_with_anchor,
    )


def generate_candidate_layouts(
    *,
    pathway: Pathway,
    demand: int,
    geometry: BenchmarkGeometry,
    assumptions: PlannerAssumptions,
    retention_envelope: RetentionEnvelope | None = None,
) -> tuple[CandidateLayout, ...]:
    required_scanners, required_injection, required_uptake = _resource_requirements_for_demand(demand, assumptions)

    # Resource-sizing search bounds (section 20 audit): injection-room multipliers are
    # swept beyond the naive patients*injection_minutes/operating_day baseline because
    # operational retention (queue-driven, not distance-driven) is sensitive to injection
    # throughput. Scanner/uptake stay close to the demand-derived baseline since the
    # audit found retention loss is dominated by injection queueing, not scanner/uptake
    # capacity, in this benchmark; CONVENTIONAL_MAX_* caps remain the outer legacy bound
    # (justified by available floor rooms: 10 rooms/floor x up to 8 floors = 80).
    profiles = (
        ("tight", 1.00, 1.00, 1.00, 0),
        ("buffered", 1.15, 1.20, 1.15, 1),
        ("injection_expanded", 1.00, 2.00, 1.15, 1),
        ("injection_expanded_buffered", 1.15, 3.00, 1.30, 1),
    )
    distributions = ("clustered", "balanced")

    candidates: list[CandidateLayout] = []
    counter = 1

    for floors in _active_floor_patterns(geometry.floor_count):
        if pathway == "Conventional" and not _floors_are_contiguous(floors):
            continue
        floor_capacity = len(floors) * geometry.rooms_per_floor
        for profile_name, s_factor, i_factor, u_factor, concurrency_extra in profiles:
            scanners = max(1, math.ceil(required_scanners * s_factor))
            injections = max(1, math.ceil(required_injection * i_factor))
            uptake = max(1, math.ceil(required_uptake * u_factor))

            if pathway == "Conventional":
                if scanners > CONVENTIONAL_MAX_SCANNERS:
                    continue
                if injections > CONVENTIONAL_MAX_INJECTION_ROOMS:
                    continue
                if uptake > CONVENTIONAL_MAX_UPTAKE_RESOURCES:
                    continue

            if scanners + injections + uptake > floor_capacity:
                continue

            for distribution in distributions:
                distribution_concurrency = max(1, min(8, len(floors) + concurrency_extra))
                if pathway == "Conventional":
                    # Conventional transporters are serialized human resources: do not
                    # size the human transporter pool independently of how many
                    # injection rooms actually exist to receive deliveries.
                    distribution_concurrency = min(distribution_concurrency, injections)
                candidate_id = f"CAND-{counter:03d}"
                counter += 1
                pattern_id = f"{pathway}:{profile_name}:{distribution}:{'-'.join(str(floor) for floor in floors)}"
                layout = _assign_rooms_for_candidate(
                    geometry=geometry,
                    active_floors=floors,
                    scanners=scanners,
                    injections=injections,
                    uptake=uptake,
                    distribution_mode=distribution,
                    assumptions=assumptions,
                    candidate_id=candidate_id,
                    pattern_id=pattern_id,
                    distribution_concurrency=distribution_concurrency,
                    feasible_room_ids=(retention_envelope.feasible_room_ids if retention_envelope is not None else None),
                )
                if layout is None:
                    continue
                candidates.append(layout)

    return tuple(candidates)


def _base_assumptions() -> PlannerAssumptions:
    return PlannerAssumptions(
        analysis_years=10,
        discount_rate_pct=8.0,
        operating_days_per_year=300,
        revenue_per_scan=2000.0,
        scanner_cycle_min=20.0,
        injection_cycle_min=10.0,
        uptake_cycle_min=45.0,
        operating_hours_per_day=18.0,
        prescribed_activity_mbq_per_patient=370.0,
    )


def _activity_models(assumptions: PlannerAssumptions) -> dict[str, ActivityDemandModel]:
    prescribed = assumptions.prescribed_activity_mbq_per_patient
    return {
        "F-18": ActivityDemandModel(
            "bounded_normal",
            mean_activity_mbq=prescribed,
            stddev_activity_mbq=prescribed * 0.05,
            lower_bound_mbq=prescribed * 0.85,
            upper_bound_mbq=prescribed * 1.15,
        )
    }


def _build_pathway_scenarios(layout: CandidateLayout) -> tuple[NativePathwayScenario, NativePathwayScenario]:
    conventional = NativePathwayScenario(
        pathway="Conventional",
        scanners=layout.scanners,
        injection_resources=layout.injection_resources,
        uptake_resources=layout.uptake_resources,
        distribution_concurrency=layout.distribution_concurrency,
        transport_minutes=0.0,
        conventional_payload_capacity_doses=CONVENTIONAL_PAYLOAD_CAPACITY_DOSES,
        mrt_payload_capacity_doses=MRT_PAYLOAD_CAPACITY_DOSES,
        transport_minutes_source="BENCHMARK_ASSUMPTION",
        installed_cyclotron_units=1,
        operated_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        operated_radiopharmacy_units=1,
        radiopharmacy_unit_capex=750_000.0,
        conventional_infrastructure_allowance_units=1,
        conventional_infrastructure_allowance_unit_capex=125_000.0,
        annual_conventional_transport_opex=750_000.0,
        annual_production_variable_cost=300_000.0,
        cyclotron_annual_opex_per_unit=0.0,
        # PROJECT_ASSUMPTION (asset cost ledger audit): each serialized human
        # transporter is one loaded FTE; rate matches the existing repository
        # test constant (test_conventional_only_negative_integration.py).
        # Fixes the prior gap where +1 transporter had zero OPEX consequence.
        conventional_transport_staff_fte=float(layout.distribution_concurrency),
        conventional_transport_staff_loaded_cost_per_fte=85_000.0,
        annual_scanner_energy_kwh=12_000.0,
        annual_cyclotron_energy_kwh=120_000.0,
        annual_other_energy_kwh=4_000.0,
        electricity_cost_per_kwh=0.18,
        clinical_staff_fte=4.0,
        clinical_staff_loaded_cost_per_fte=95_000.0,
        production_staff_fte=2.0,
        production_staff_loaded_cost_per_fte=110_000.0,
        annual_consumable_units=6000.0,
        consumable_cost_per_unit=22.0,
    )

    mrt = NativePathwayScenario(
        pathway="MRT",
        scanners=layout.scanners,
        injection_resources=layout.injection_resources,
        uptake_resources=layout.uptake_resources,
        distribution_concurrency=layout.distribution_concurrency,
        transport_minutes=0.0,
        conventional_payload_capacity_doses=CONVENTIONAL_PAYLOAD_CAPACITY_DOSES,
        mrt_payload_capacity_doses=MRT_PAYLOAD_CAPACITY_DOSES,
        transport_minutes_source="BENCHMARK_ASSUMPTION",
        installed_cyclotron_units=1,
        operated_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        operated_radiopharmacy_units=1,
        radiopharmacy_unit_capex=750_000.0,
        installed_mrt_base_infrastructure_units=1,
        operated_mrt_base_units=1,
        installed_mrt_endpoints=max(1, layout.injection_resources),
        operated_mrt_endpoints=max(1, layout.injection_resources),
        installed_guideway_length_m=max(0.0, layout.guideway_total_length_m),
        operated_guideway_length_m=max(0.0, layout.guideway_total_length_m),
        guideway_capex_per_m=0.0,
        installed_vertical_transitions=max(0, layout.guideway_transition_count),
        operated_vertical_transitions=max(0, layout.guideway_transition_count),
        installed_building_connections=0,
        operated_building_connections=0,
        installed_mrt_carriers=max(1, layout.distribution_concurrency),
        operated_mrt_carriers=max(1, layout.distribution_concurrency),
        guideway_maintenance_per_m_year=0.0,
        annual_mrt_energy_kwh=25_000.0,
        mrt_support_staff_fte=3.0,
        mrt_support_staff_loaded_cost_per_fte=105_000.0,
        annual_production_variable_cost=300_000.0,
        annual_scanner_energy_kwh=12_000.0,
        annual_cyclotron_energy_kwh=120_000.0,
        annual_other_energy_kwh=4_000.0,
        electricity_cost_per_kwh=0.18,
        clinical_staff_fte=4.0,
        clinical_staff_loaded_cost_per_fte=95_000.0,
        production_staff_fte=2.0,
        production_staff_loaded_cost_per_fte=110_000.0,
        annual_consumable_units=6000.0,
        consumable_cost_per_unit=22.0,
    )

    return conventional, mrt


def _build_request(
    *,
    demand: int,
    pathway_layout: CandidateLayout,
    production_basis: ProductionBasis,
    assumptions: PlannerAssumptions,
    seed: int,
    mrt_straight_speed_m_per_s_override: float | None = None,
) -> NativeDecisionPipelineScenario:
    conventional, mrt = _build_pathway_scenarios(pathway_layout)
    return NativeDecisionPipelineScenario(
        project_name=f"Spatial Benchmark Demand {demand}",
        target_patients_per_day=int(demand),
        radionuclide_mix={production_basis.radionuclide: 1.0},
        activity_distribution_by_radionuclide=_activity_models(assumptions),
        cyclotron_capability=production_basis.cyclotron_fleet.assets[0].capability,
        cyclotron_fleet=production_basis.cyclotron_fleet,
        conventional=conventional,
        mrt=mrt,
        product_profile="MRT_ENABLED",
        planner_assumptions=assumptions,
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=int(seed),
        clinical_day_start_time_minutes=BENCHMARK_CLINICAL_START_MINUTE,
        operating_day_minutes=1080.0,
        production_start_time_minutes=BENCHMARK_PRODUCTION_START_MINUTE,
        production_horizon_minutes=BENCHMARK_PRODUCTION_END_MINUTE,
        batch_target_patients_per_batch=20,
        facility_engineering_model=pathway_layout.model_with_anchor,
        mrt_straight_speed_m_per_s_override=mrt_straight_speed_m_per_s_override,
    )


def _simultaneous_job_metrics(intervals: Sequence[tuple[float, float]]) -> tuple[int, float]:
    if not intervals:
        return 0, 0.0
    points: list[tuple[float, int]] = []
    for start, end in intervals:
        if end < start:
            continue
        points.append((start, 1))
        points.append((end, -1))
    points.sort(key=lambda item: (item[0], item[1]))
    if not points:
        return 0, 0.0

    active = 0
    peak = 0
    weighted_time = 0.0
    total_time = max(0.0, points[-1][0] - points[0][0])
    last_time = points[0][0]
    for time, delta in points:
        dt = max(0.0, time - last_time)
        weighted_time += active * dt
        active += delta
        peak = max(peak, active)
        last_time = time
    average = (weighted_time / total_time) if total_time > 0.0 else float(peak)
    return int(peak), float(average)


def _transport_metrics(pathway_result: NativePathwayResult) -> tuple[int, float, float, float, float, int, int, int, float]:
    schedule = pathway_result.operational_result.production_clinical_result.transport_schedule
    if isinstance(schedule, ConventionalTransportScheduleResult):
        peak_simultaneous, avg_simultaneous = _simultaneous_job_metrics(
            tuple((job.dispatch_time_minutes, job.transporter_release_time_minutes) for job in schedule.jobs)
        )
        return (
            schedule.transport_jobs_per_day,
            float(schedule.transporter_utilization_pct),
            float(schedule.average_wait_minutes),
            float(schedule.max_wait_minutes),
            float(schedule.transport_resource_minutes_per_day),
            int(schedule.transporter_count),
            0,
            peak_simultaneous,
            avg_simultaneous,
        )
    if isinstance(schedule, MRTCarrierTransportScheduleResult):
        peak_simultaneous, avg_simultaneous = _simultaneous_job_metrics(
            tuple((job.dispatch_time_minutes, job.carrier_release_time_minutes) for job in schedule.jobs)
        )
        return (
            schedule.transport_jobs_per_day,
            float(schedule.carrier_utilization_pct),
            float(schedule.average_carrier_queue_wait_minutes),
            float(schedule.maximum_carrier_queue_wait_minutes),
            float(schedule.carrier_resource_minutes_per_day),
            0,
            int(schedule.carrier_count),
            peak_simultaneous,
            avg_simultaneous,
        )
    raise TypeError("Unsupported transport schedule result type")


def _transport_capex(pathway_result: NativePathwayResult) -> float:
    if pathway_result.pathway == "Conventional":
        components = {
            "Conventional infrastructure allowance",
        }
    else:
        components = {
            "MRT base infrastructure",
            "MRT endpoints",
            "MRT guideway",
            "Vertical transitions",
            "Building connections",
            "MRT carriers",
        }
    return sum(item.subtotal for item in pathway_result.capex_result.ledger if item.component in components)


def _transport_opex(pathway_result: NativePathwayResult) -> float:
    if pathway_result.pathway == "Conventional":
        components = {
            "Conventional transport and handling allowance",
            "Conventional transport labor",
        }
    else:
        components = {
            "MRT base annual O&M",
            "Guideway annual maintenance",
            "Vertical transition annual maintenance",
            "Building connection annual maintenance",
            "MRT support labor",
            "MRT carrier allocated electricity",
            "MRT carrier maintenance",
        }
    return sum(item.annual_cost for item in pathway_result.opex_result.ledger if item.component in components)


def _route_timing_metrics(pathway_result: NativePathwayResult) -> tuple[float, float, float, float]:
    traces = pathway_result.decay_summary.patient_traces
    if not traces:
        return (0.0, 0.0, 0.0, 0.0)
    release_to_injection = [float(trace.elapsed_release_to_injection_minutes) for trace in traces]
    eob_to_release = [float(trace.elapsed_eob_to_release_minutes) for trace in traces]
    eob_to_injection = [float(trace.elapsed_eob_to_injection_minutes) for trace in traces]
    return (
        mean(release_to_injection),
        max(release_to_injection),
        mean(eob_to_release),
        mean(eob_to_injection),
    )


def _operational_retention_metrics(pathway_result: NativePathwayResult, *, threshold: float) -> tuple[int, int, float]:
    """Operational (queue-aware, REALIZED) retention metrics -- distinct from the
    best-case geometric envelope used to pre-filter candidate rooms (section 8).

    Returns (retention_pass_count, retention_qualified_completed_count, avg_injection_queue_minutes).
    retention_pass_count: RELEASE->ADMINISTRATION retained_fraction >= threshold,
        regardless of whether the patient's clinical workflow actually completed
        within the operating day (a project DESIGN CRITERION, not a clinical-
        validity judgment -- see RETENTION-qualified throughput audit).
    retention_qualified_completed_count: retention_pass AND
        completed_within_operating_day -- the authoritative successful,
        design-criterion-compliant throughput (T_qualified).
    """
    decay_traces = pathway_result.decay_summary.patient_traces
    retention_pass = 0
    retention_qualified_completed = 0
    for trace in decay_traces:
        passed = retained_fraction(max(0.0, trace.elapsed_release_to_injection_minutes), trace.half_life_minutes) >= threshold
        if passed:
            retention_pass += 1
            if trace.completed_within_operating_day:
                retention_qualified_completed += 1
    clinical_traces = pathway_result.operational_result.production_clinical_result.patient_traces
    injection_waits = [max(0.0, trace.injection_start - trace.distribution_end) for trace in clinical_traces]
    avg_injection_queue = mean(injection_waits) if injection_waits else 0.0
    return retention_pass, retention_qualified_completed, avg_injection_queue


def _evaluate_layout(
    *,
    pathway: Pathway,
    layout: CandidateLayout,
    demand: int,
    production_basis: ProductionBasis,
    assumptions: PlannerAssumptions,
    seed: int,
    retention_threshold: float | None = None,
) -> CandidateOutcome:
    used_rooms = sum(1 for function in layout.room_assignments.values() if function in {"SCANNER", "INJECTION_ADMINISTRATION", "UPTAKE"})
    if used_rooms > len(layout.room_assignments):
        raise ValueError("Candidate consumes more rooms than available")

    effective_retention_threshold = (
        float(assumptions.minimum_release_to_administration_retention_fraction)
        if retention_threshold is None
        else float(retention_threshold)
    )

    request = _build_request(
        demand=demand,
        pathway_layout=layout,
        production_basis=production_basis,
        assumptions=assumptions,
        seed=seed,
    )

    pathway_result = run_native_pathway_pipeline(request, pathway=pathway)

    patients_served = int(pathway_result.operational_result.patients_completed)
    shortfall = max(0, int(demand) - patients_served)
    meets_required = patients_served >= int(demand)

    (
        transport_jobs,
        transport_utilization,
        avg_queue,
        max_queue,
        transport_minutes,
        manual_transporters,
        mrt_operated_carriers,
        peak_simultaneous_jobs,
        avg_simultaneous_jobs,
    ) = _transport_metrics(pathway_result)

    production_result = pathway_result.operational_result.production_clinical_result
    production_batches_per_day = len(production_result.scheduled_batch_demands)
    released_payloads_per_day = len(production_result.transport_payloads)
    active_destinations = len({payload.destination_object_id for payload in production_result.transport_payloads})

    avg_release_to_injection, max_release_to_injection, avg_eob_to_release, avg_eob_to_injection = _route_timing_metrics(pathway_result)
    retention_pass, retention_qualified_completed, avg_injection_queue_minutes = _operational_retention_metrics(
        pathway_result, threshold=effective_retention_threshold
    )

    operational_result = pathway_result.operational_result
    patients_production_feasible = int(operational_result.production_activity_feasible_scheduled_patients)
    # Geometric retention feasibility is enforced at candidate-generation time via
    # feasible_room_ids room gating (see _assign_rooms_for_candidate); every
    # production-feasible patient assigned to a gated candidate is therefore, by
    # construction, delivered to a geometrically-retention-feasible destination.
    patients_geometrically_retention_feasible = patients_production_feasible
    meets_retention_qualified = retention_qualified_completed >= int(demand)

    qualified_lifecycle_result = evaluate_lifecycle_economics(
        initial_capex=pathway_result.capex_result.total_capex,
        installed_capacity_per_day=float(retention_qualified_completed),
        annual_opex=pathway_result.opex_result.total_annual_opex,
        revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=assumptions.operating_days_per_year,
        discount_rate_pct=assumptions.discount_rate_pct,
        analysis_years=assumptions.analysis_years,
        starting_demand_per_day=float(retention_qualified_completed),
        annual_demand_growth_rate=0.0,
    )
    qualified_annual_revenue = float(qualified_lifecycle_result.annual_rows[0].annual_revenue) if qualified_lifecycle_result.annual_rows else 0.0
    qualified_lifecycle_npv = float(qualified_lifecycle_result.final_npv)

    return CandidateOutcome(
        pathway=pathway,
        layout=layout,
        physically_feasible=True,
        feasibility_reason=None,
        meets_required_demand=meets_required,
        patients_served_per_day=patients_served,
        service_shortfall_per_day=shortfall,
        bottleneck=pathway_result.operational_result.bottleneck.resource,
        production_batches_per_day=production_batches_per_day,
        released_payloads_per_day=released_payloads_per_day,
        delivery_jobs_per_day=transport_jobs,
        transport_jobs_per_day=transport_jobs,
        active_destinations=active_destinations,
        peak_simultaneous_jobs=peak_simultaneous_jobs,
        average_simultaneous_jobs=avg_simultaneous_jobs,
        transport_utilization_pct=transport_utilization,
        avg_transport_queue_minutes=avg_queue,
        max_transport_queue_minutes=max_queue,
        transport_resource_minutes_per_day=transport_minutes,
        manual_transporters=manual_transporters,
        mrt_installed_carriers=int(pathway_result.operational_result.pathway_config.installed_mrt_carriers),
        mrt_operated_carriers=mrt_operated_carriers,
        total_capex=float(pathway_result.capex_result.total_capex),
        transport_capex=float(_transport_capex(pathway_result)),
        annual_total_opex=float(pathway_result.opex_result.total_annual_opex),
        annual_transport_opex=float(_transport_opex(pathway_result)),
        annual_revenue=float(pathway_result.annual_revenue),
        lifecycle_npv=float(pathway_result.lifecycle_result.final_npv),
        avg_release_to_injection_minutes=avg_release_to_injection,
        max_release_to_injection_minutes=max_release_to_injection,
        avg_eob_to_release_minutes=avg_eob_to_release,
        avg_eob_to_injection_minutes=avg_eob_to_injection,
        retention_feasible_patients_per_day=retention_qualified_completed,
        retention_threshold=effective_retention_threshold,
        avg_injection_queue_minutes=avg_injection_queue_minutes,
        patients_demanded=int(demand),
        patients_production_feasible=patients_production_feasible,
        patients_geometrically_retention_feasible=patients_geometrically_retention_feasible,
        patients_clinically_completed=patients_served,
        patients_retention_pass=retention_pass,
        patients_retention_qualified_completed=retention_qualified_completed,
        meets_retention_qualified_demand=meets_retention_qualified,
        clinical_completion_revenue_potential=float(pathway_result.annual_revenue),
        qualified_annual_revenue=qualified_annual_revenue,
        qualified_lifecycle_npv=qualified_lifecycle_npv,
        pathway_result=pathway_result,
    )


SpatialForm = Literal["COMPACT_CLUSTERED", "MODERATELY_DISTRIBUTED", "HIGHLY_DISTRIBUTED"]


def classify_spatial_form(layout: CandidateLayout) -> SpatialForm:
    """Deterministic spatial-form classification (independent optimization build,
    section 24) from explicit floor-span/floor-count metrics -- never subjective.
    COMPACT_CLUSTERED: <=3 active floors spanning <=3 levels.
    MODERATELY_DISTRIBUTED: floor span of 4-6 levels.
    HIGHLY_DISTRIBUTED: floor span of 7+ levels.
    """
    if not layout.active_floors:
        return "COMPACT_CLUSTERED"
    floor_span = max(layout.active_floors) - min(layout.active_floors) + 1
    if floor_span <= 3 and len(layout.active_floors) <= 3:
        return "COMPACT_CLUSTERED"
    if floor_span <= 6:
        return "MODERATELY_DISTRIBUTED"
    return "HIGHLY_DISTRIBUTED"


def _dominates(a: CandidateOutcome, b: CandidateOutcome) -> bool:
    """True if `a` dominates `b`: at least as good on every axis (higher
    RETENTION-QUALIFIED throughput, lower CapEx, higher qualified NPV) with a
    strict improvement on at least one axis (section 21/37). Uses qualified
    (design-criterion-compliant) clinical value, not raw clinical completions --
    a candidate with more unqualified completions must not dominate one with
    fewer clinical completions but more qualified completions.
    """
    at_least_as_good = (
        a.patients_retention_qualified_completed >= b.patients_retention_qualified_completed
        and a.total_capex <= b.total_capex
        and a.qualified_lifecycle_npv >= b.qualified_lifecycle_npv
    )
    strictly_better = (
        a.patients_retention_qualified_completed > b.patients_retention_qualified_completed
        or a.total_capex < b.total_capex
        or a.qualified_lifecycle_npv > b.qualified_lifecycle_npv
    )
    return at_least_as_good and strictly_better


def pareto_frontier(outcomes: Sequence[CandidateOutcome]) -> tuple[CandidateOutcome, ...]:
    """Non-dominated candidates across (retention-qualified completed patients,
    CapEx, qualified lifecycle NPV) among PHYSICALLY FEASIBLE candidates only
    (section 21/6/37: physical feasibility precedes economics; clinical
    performance dimension is retention-qualified, not raw clinical completion).
    Deterministically ordered by qualified throughput desc, CapEx asc, qualified
    NPV desc, candidate_id.
    """
    feasible = [outcome for outcome in outcomes if outcome.physically_feasible]
    frontier = [
        candidate
        for candidate in feasible
        if not any(_dominates(other, candidate) for other in feasible if other is not candidate)
    ]
    return tuple(
        sorted(
            frontier,
            key=lambda outcome: (
                -outcome.patients_retention_qualified_completed,
                outcome.total_capex,
                -outcome.qualified_lifecycle_npv,
                outcome.layout.candidate_id,
            ),
        )
    )


def _ranking_key(outcome: CandidateOutcome) -> tuple[int, int, int, float, float]:
    """Retention-qualified-throughput authority (see design-success rule):
    primary ranking uses patients_retention_qualified_completed and
    qualified_lifecycle_npv, NOT raw clinical completion / clinical-completion
    NPV. Ordinary clinical throughput remains available as secondary diagnostic
    information on CandidateOutcome, never discarded, never the ranking authority.
    """
    return (
        1 if outcome.physically_feasible else 0,
        1 if outcome.meets_retention_qualified_demand else 0,
        int(outcome.patients_retention_qualified_completed),
        float(outcome.qualified_lifecycle_npv),
        -float(outcome.total_capex),
    )


def _winner_reason(winner: CandidateOutcome, runner_up: CandidateOutcome | None, demand: int) -> str:
    if runner_up is None:
        return "Only one feasible candidate was available."
    if winner.meets_retention_qualified_demand and not runner_up.meets_retention_qualified_demand:
        return (
            f"{winner.layout.candidate_id} was selected because it meets {demand}/day retention-qualified while "
            f"runner-up {runner_up.layout.candidate_id} does not."
        )
    if winner.patients_retention_qualified_completed != runner_up.patients_retention_qualified_completed:
        return (
            f"{winner.layout.candidate_id} was selected for higher retention-qualified throughput "
            f"({winner.patients_retention_qualified_completed} vs {runner_up.patients_retention_qualified_completed})."
        )
    if not math.isclose(winner.qualified_lifecycle_npv, runner_up.qualified_lifecycle_npv, rel_tol=1e-9, abs_tol=1e-6):
        return (
            f"{winner.layout.candidate_id} was selected for stronger qualified lifecycle NPV "
            f"({winner.qualified_lifecycle_npv:.2f} vs {runner_up.qualified_lifecycle_npv:.2f})."
        )
    if not math.isclose(winner.total_capex, runner_up.total_capex, rel_tol=1e-9, abs_tol=1e-6):
        return (
            f"{winner.layout.candidate_id} was selected as tie-break by lower CapEx "
            f"({winner.total_capex:.2f} vs {runner_up.total_capex:.2f})."
        )
    return (
        f"{winner.layout.candidate_id} was selected by deterministic candidate ordering "
        f"after equivalent feasibility, retention-qualified throughput, qualified NPV, and CapEx against {runner_up.layout.candidate_id}."
    )


def optimize_pathway_layouts(
    *,
    pathway: Pathway,
    demand: int,
    geometry: BenchmarkGeometry,
    production_basis: ProductionBasis,
    assumptions: PlannerAssumptions,
    seed: int = DEFAULT_SEED,
    retention_envelope: RetentionEnvelope | None = None,
) -> PathwayOptimizationResult:
    candidates = generate_candidate_layouts(
        pathway=pathway,
        demand=demand,
        geometry=geometry,
        assumptions=assumptions,
        retention_envelope=retention_envelope,
    )
    outcomes: list[CandidateOutcome] = []

    for index, layout in enumerate(candidates):
        outcome = _evaluate_layout(
            pathway=pathway,
            layout=layout,
            demand=demand,
            production_basis=production_basis,
            assumptions=assumptions,
            seed=seed + index,
            retention_threshold=(retention_envelope.threshold if retention_envelope is not None else None),
        )
        outcomes.append(outcome)

    if not outcomes:
        raise ValueError("No candidate outcomes were produced")

    ordered = sorted(outcomes, key=_ranking_key, reverse=True)
    winner = ordered[0]
    runner_up = ordered[1] if len(ordered) > 1 else None

    rejected = sum(1 for outcome in outcomes if not outcome.physically_feasible)
    failing = sum(1 for outcome in outcomes if not outcome.meets_required_demand)
    meeting = sum(1 for outcome in outcomes if outcome.meets_required_demand)

    return PathwayOptimizationResult(
        pathway=pathway,
        demand=int(demand),
        evaluated_candidates=len(outcomes),
        rejected_candidates=rejected,
        demand_failing_candidates=failing,
        demand_meeting_candidates=meeting,
        winner=winner,
        runner_up=runner_up,
        winner_reason=_winner_reason(winner, runner_up, demand),
        outcomes=tuple(ordered),
    )


@dataclass(frozen=True)
class PatientRetentionRecord:
    """Per-patient RELEASE->ADMINISTRATION retention using the REALIZED (actually
    scheduled/simulated) release and injection timing -- reuses the authoritative
    retained_fraction and the elapsed_release_to_injection_minutes already tracked on
    the decay trace. This is the realized counterpart to the pre-filter, best-case
    RoomRetentionRecord envelope used to constrain candidate room activation.
    """

    patient_id: str
    radionuclide: str
    destination_room_id: str | None
    release_time_minutes: float
    administration_time_minutes: float
    elapsed_release_to_administration_minutes: float
    retained_fraction: float
    threshold: float
    status: RetentionStatus


def compute_patient_retention_records(
    outcome: CandidateOutcome,
    *,
    threshold: float,
) -> tuple[PatientRetentionRecord, ...]:
    destination_by_patient_id = {
        trace.patient_id: trace.assigned_destination_object_id
        for trace in outcome.pathway_result.operational_result.production_clinical_result.patient_traces
    }
    records: list[PatientRetentionRecord] = []
    for trace in outcome.pathway_result.decay_summary.patient_traces:
        retained = retained_fraction(max(0.0, trace.elapsed_release_to_injection_minutes), trace.half_life_minutes)
        status: RetentionStatus = "RETENTION_FEASIBLE" if retained >= threshold else "RETENTION_INFEASIBLE"
        records.append(
            PatientRetentionRecord(
                patient_id=trace.patient_id,
                radionuclide=trace.radionuclide,
                destination_room_id=destination_by_patient_id.get(trace.patient_id),
                release_time_minutes=float(trace.release_time_minutes),
                administration_time_minutes=float(trace.injection_start_minutes),
                elapsed_release_to_administration_minutes=float(trace.elapsed_release_to_injection_minutes),
                retained_fraction=retained,
                threshold=threshold,
                status=status,
            )
        )
    return tuple(sorted(records, key=lambda record: record.patient_id))


def _representative_timeline(pathway: Pathway, outcome: CandidateOutcome) -> RepresentativeTimeline:
    traces = sorted(
        outcome.pathway_result.operational_result.production_clinical_result.patient_traces,
        key=lambda trace: trace.patient_id,
    )
    if not traces:
        raise ValueError("No decay traces available for representative timeline")
    trace = traces[0]

    schedule = outcome.pathway_result.operational_result.production_clinical_result.transport_schedule
    if isinstance(schedule, ConventionalTransportScheduleResult):
        job = next(job for job in schedule.jobs if job.job_id == trace.delivery_job_id)
        queue_start = job.queue_ready_time_minutes
        dispatch = job.dispatch_time_minutes
        arrival = job.handoff_completion_time_minutes
    elif isinstance(schedule, MRTCarrierTransportScheduleResult):
        job = next(job for job in schedule.jobs if job.job_id == trace.delivery_job_id)
        queue_start = job.queue_start_time_minutes
        dispatch = job.dispatch_time_minutes
        arrival = job.handoff_completion_time_minutes
    else:
        raise TypeError("Unsupported transport schedule type")

    injection_wait = max(0.0, trace.injection_start - arrival)

    return RepresentativeTimeline(
        pathway=pathway,
        patient_id=trace.patient_id,
        batch_id=int(trace.batch_id),
        production_window_end_minutes=float(trace.production_window_end_time_minutes),
        release_minutes=float(trace.batch_release_time_minutes),
        transport_queue_start_minutes=float(queue_start),
        transport_dispatch_minutes=float(dispatch),
        transport_arrival_minutes=float(arrival),
        injection_resource_wait_minutes=float(injection_wait),
        injection_start_minutes=float(trace.injection_start),
        injection_end_minutes=float(trace.injection_end),
        uptake_end_minutes=float(trace.scan_start),
        scan_start_minutes=float(trace.scan_start),
        scan_end_minutes=float(trace.scan_end),
        elapsed_eob_to_release_minutes=float(trace.batch_release_time_minutes - trace.production_window_end_time_minutes),
        elapsed_release_to_injection_minutes=float(trace.injection_start - trace.batch_release_time_minutes),
        elapsed_eob_to_injection_minutes=float(trace.injection_start - trace.production_window_end_time_minutes),
        elapsed_eob_to_scan_completion_minutes=float(trace.scan_end - trace.production_window_end_time_minutes),
    )


def _production_gate_row(demand: int, pathway: Pathway, outcome: CandidateOutcome, production_basis: ProductionBasis) -> ProductionCapacityGateRow:
    traces = outcome.pathway_result.decay_summary.patient_traces
    required_administered = demand * outcome.pathway_result.operational_result.demand_result.simulation.generated_demand.patients[0].prescribed_activity_mbq
    required_release = sum(float(trace.required_activity_at_release_mbq) for trace in traces)
    required_eob = sum(float(trace.required_upstream_activity_for_prescribed_mbq) for trace in traces)

    demand_result = outcome.pathway_result.operational_result.demand_result
    radionuclide = production_basis.radionuclide
    demand_layer_required_eob = float(demand_result.required_eob_activity_mbq_by_radionuclide.get(radionuclide, 0.0))
    unassigned_patient_count = len(demand_result.unassigned_patient_ids_by_radionuclide.get(radionuclide, ()))
    diagnostic_common_eob = float(
        demand_result.non_authoritative_common_early_eob_activity_mbq_by_radionuclide.get(radionuclide, 0.0)
    )
    diagnostic_common_eob_cycles = int(
        demand_result.non_authoritative_common_early_eob_implied_cycle_count_by_radionuclide.get(radionuclide, 0)
    )

    production_result = outcome.pathway_result.operational_result.production_clinical_result
    required_batches = len(production_result.batch_demands)
    feasible_scheduled_batches = len(production_result.scheduled_batch_demands)
    unscheduled_batches = len(production_result.unscheduled_batch_demands)
    available_eob, status = resolve_fleet_schedule_derived_eob_capacity_mbq(
        fleet=production_basis.cyclotron_fleet,
        radionuclide=production_basis.radionuclide,
        feasible_scheduled_windows=max(0, production_result.production_schedule.scheduled_batches),
    )

    scheduled_activity_fits_capacity = available_eob is not None and available_eob + 1e-9 >= required_eob
    whole_demand_production_feasible = (
        scheduled_activity_fits_capacity
        and unscheduled_batches == 0
        and unassigned_patient_count == 0
    )

    reconciliation = outcome.pathway_result.operational_result.production_requirement_reconciliation
    final_reconciled_required_eob = (
        reconciliation.final_reconciled_eob_activity_mbq if reconciliation is not None else required_eob
    )
    unused_headroom = (
        max(0.0, available_eob - final_reconciled_required_eob) if available_eob is not None else None
    )

    return ProductionCapacityGateRow(
        demand=int(demand),
        pathway=pathway,
        required_batches=required_batches,
        feasible_scheduled_batches=feasible_scheduled_batches,
        unscheduled_batches=unscheduled_batches,
        required_administered_activity_mbq=float(required_administered),
        required_release_activity_mbq=float(required_release),
        required_eob_activity_mbq=float(required_eob),
        schedule_derived_feasible_eob_capacity_mbq=available_eob,
        explicit_site_capacity_mbq_per_day=production_basis.explicit_site_eob_capacity_mbq_per_day,
        available_eob_capacity_mbq_per_day=available_eob,
        capacity_status=status,
        scheduled_activity_fits_capacity=scheduled_activity_fits_capacity,
        demand_layer_required_eob_activity_mbq=demand_layer_required_eob,
        unassigned_patient_production_demand_count=unassigned_patient_count,
        non_authoritative_common_early_eob_activity_mbq=diagnostic_common_eob,
        non_authoritative_common_early_eob_implied_cycle_count=diagnostic_common_eob_cycles,
        production_feasible=whole_demand_production_feasible,
        planned_required_eob_activity_mbq=demand_layer_required_eob,
        realized_required_eob_activity_mbq=float(required_eob),
        final_reconciled_required_eob_activity_mbq=float(final_reconciled_required_eob),
        unused_production_headroom_mbq=unused_headroom,
        production_requirement_convergence_status=(
            reconciliation.convergence_status if reconciliation is not None else "CONVERGED"
        ),
        production_requirement_reconciliation_iterations=(
            reconciliation.iterations_used if reconciliation is not None else 0
        ),
        production_requirement_max_relative_difference=(
            reconciliation.max_relative_difference if reconciliation is not None else 0.0
        ),
    )


def run_spatial_benchmark(
    *,
    primary_demand: int = PRIMARY_DEMAND,
    demand_sweep: Sequence[int] = DEMAND_SWEEP,
    seed: int = DEFAULT_SEED,
    assumptions: PlannerAssumptions | None = None,
    release_processing_minutes: float = 71.0,
    geometry: BenchmarkGeometry | None = None,
) -> SpatialBenchmarkResult:
    common_assumptions = _base_assumptions() if assumptions is None else assumptions
    geometry = build_benchmark_geometry() if geometry is None else geometry
    production_basis = build_production_basis(release_processing_minutes=release_processing_minutes)
    clock_assumptions = BenchmarkClockAssumptions(
        production_start_minute=BENCHMARK_PRODUCTION_START_MINUTE,
        production_end_minute=BENCHMARK_PRODUCTION_END_MINUTE,
        clinical_start_minute=BENCHMARK_CLINICAL_START_MINUTE,
        clinical_end_minute=BENCHMARK_CLINICAL_START_MINUTE + 1080.0,
    )

    conventional_retention_envelope = compute_retention_envelope(
        geometry=geometry,
        assumptions=common_assumptions,
        radionuclide=production_basis.radionuclide,
        pathway="Conventional",
    )
    mrt_retention_envelope = compute_retention_envelope(
        geometry=geometry,
        assumptions=common_assumptions,
        radionuclide=production_basis.radionuclide,
        pathway="MRT",
    )

    conventional_primary = optimize_pathway_layouts(
        pathway="Conventional",
        demand=primary_demand,
        geometry=geometry,
        production_basis=production_basis,
        assumptions=common_assumptions,
        seed=seed,
        retention_envelope=conventional_retention_envelope,
    )
    mrt_primary = optimize_pathway_layouts(
        pathway="MRT",
        demand=primary_demand,
        geometry=geometry,
        production_basis=production_basis,
        assumptions=common_assumptions,
        seed=seed,
        retention_envelope=mrt_retention_envelope,
    )

    sweep_rows: list[DemandSweepRow] = []
    gate_rows: list[ProductionCapacityGateRow] = []

    for index, demand in enumerate(demand_sweep):
        conv = optimize_pathway_layouts(
            pathway="Conventional",
            demand=int(demand),
            geometry=geometry,
            production_basis=production_basis,
            assumptions=common_assumptions,
            seed=seed + 1000 + index,
            retention_envelope=conventional_retention_envelope,
        )
        mrt = optimize_pathway_layouts(
            pathway="MRT",
            demand=int(demand),
            geometry=geometry,
            production_basis=production_basis,
            assumptions=common_assumptions,
            seed=seed + 2000 + index,
            retention_envelope=mrt_retention_envelope,
        )

        sweep_rows.append(
            DemandSweepRow(
                demand=int(demand),
                conventional_served=conv.winner.patients_served_per_day,
                conventional_floors_used=len(conv.winner.layout.active_floors),
                conventional_scanners=conv.winner.layout.scanners,
                conventional_transport_burden=conv.winner.transport_resource_minutes_per_day,
                mrt_served=mrt.winner.patients_served_per_day,
                mrt_floors_used=len(mrt.winner.layout.active_floors),
                mrt_scanners=mrt.winner.layout.scanners,
                mrt_transport_burden=mrt.winner.transport_resource_minutes_per_day,
                conventional_avg_release_to_injection_minutes=conv.winner.avg_release_to_injection_minutes,
                conventional_max_release_to_injection_minutes=conv.winner.max_release_to_injection_minutes,
                conventional_avg_transport_queue_minutes=conv.winner.avg_transport_queue_minutes,
                conventional_transport_utilization_pct=conv.winner.transport_utilization_pct,
                mrt_avg_release_to_injection_minutes=mrt.winner.avg_release_to_injection_minutes,
                mrt_max_release_to_injection_minutes=mrt.winner.max_release_to_injection_minutes,
                mrt_avg_transport_queue_minutes=mrt.winner.avg_transport_queue_minutes,
                mrt_transport_utilization_pct=mrt.winner.transport_utilization_pct,
            )
        )

        gate_rows.append(_production_gate_row(int(demand), "Conventional", conv.winner, production_basis))
        gate_rows.append(_production_gate_row(int(demand), "MRT", mrt.winner, production_basis))

    timelines = (
        _representative_timeline("Conventional", conventional_primary.winner),
        _representative_timeline("MRT", mrt_primary.winner),
    )

    fingerprint_payload = {
        "primary_demand": primary_demand,
        "seed": seed,
        "conventional_winner": conventional_primary.winner.layout.candidate_id,
        "mrt_winner": mrt_primary.winner.layout.candidate_id,
        "conventional_served": conventional_primary.winner.patients_served_per_day,
        "mrt_served": mrt_primary.winner.patients_served_per_day,
    }
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    return SpatialBenchmarkResult(
        geometry=geometry,
        production_basis=production_basis,
        clock_assumptions=clock_assumptions,
        assumptions=common_assumptions,
        primary_demand=int(primary_demand),
        conventional_primary=conventional_primary,
        mrt_primary=mrt_primary,
        demand_sweep=tuple(sweep_rows),
        production_capacity_gate_rows=tuple(gate_rows),
        representative_timelines=timelines,
        equal_budget_secondary_status="DEFERRED - REQUIRES SPATIAL CANDIDATE TO EQUAL-BUDGET INTEGRATION",
        reproducibility_fingerprint=fingerprint,
        conventional_retention_envelope=conventional_retention_envelope,
        mrt_retention_envelope=mrt_retention_envelope,
    )


def floor_assignment_rows(layout: CandidateLayout) -> tuple[tuple[int, tuple[tuple[str, RoomFunction], ...]], ...]:
    rows: list[tuple[int, tuple[tuple[str, RoomFunction], ...]]] = []
    for floor in range(1, FLOOR_COUNT + 1):
        rows.append((floor, tuple(sorted(layout.floor_assignments.get(floor, ()), key=lambda item: item[0]))))
    return tuple(rows)


def to_serializable_summary(result: SpatialBenchmarkResult) -> dict[str, object]:
    def _outcome_dict(outcome: CandidateOutcome) -> dict[str, object]:
        return {
            "candidate_id": outcome.layout.candidate_id,
            "pattern_id": outcome.layout.pattern_id,
            "active_floors": list(outcome.layout.active_floors),
            "patients_served_per_day": outcome.patients_served_per_day,
            "service_shortfall_per_day": outcome.service_shortfall_per_day,
            "production_batches_per_day": outcome.production_batches_per_day,
            "released_payloads_per_day": outcome.released_payloads_per_day,
            "delivery_jobs_per_day": outcome.delivery_jobs_per_day,
            "scanners": outcome.layout.scanners,
            "injection_resources": outcome.layout.injection_resources,
            "uptake_resources": outcome.layout.uptake_resources,
            "active_destinations": outcome.active_destinations,
            "peak_simultaneous_jobs": outcome.peak_simultaneous_jobs,
            "average_simultaneous_jobs": outcome.average_simultaneous_jobs,
            "avg_route_distance_m": outcome.layout.avg_route_distance_m,
            "max_route_distance_m": outcome.layout.max_route_distance_m,
            "avg_transport_queue_minutes": outcome.avg_transport_queue_minutes,
            "max_transport_queue_minutes": outcome.max_transport_queue_minutes,
            "transport_utilization_pct": outcome.transport_utilization_pct,
            "transport_jobs_per_day": outcome.transport_jobs_per_day,
            "manual_transporters": outcome.manual_transporters,
            "mrt_installed_carriers": outcome.mrt_installed_carriers,
            "mrt_operated_carriers": outcome.mrt_operated_carriers,
            "guideway_total_length_m": outcome.layout.guideway_total_length_m,
            "transport_capex": outcome.transport_capex,
            "total_capex": outcome.total_capex,
            "annual_transport_opex": outcome.annual_transport_opex,
            "annual_total_opex": outcome.annual_total_opex,
            "annual_revenue": outcome.annual_revenue,
            "lifecycle_npv": outcome.lifecycle_npv,
            "bottleneck": outcome.bottleneck,
            "avg_eob_to_release_minutes": outcome.avg_eob_to_release_minutes,
            "avg_release_to_injection_minutes": outcome.avg_release_to_injection_minutes,
            "avg_eob_to_injection_minutes": outcome.avg_eob_to_injection_minutes,
        }

    return {
        "primary_demand": result.primary_demand,
        "reproducibility_fingerprint": result.reproducibility_fingerprint,
        "equal_budget_secondary_status": result.equal_budget_secondary_status,
        "conventional_primary": {
            "evaluated_candidates": result.conventional_primary.evaluated_candidates,
            "rejected_candidates": result.conventional_primary.rejected_candidates,
            "demand_failing_candidates": result.conventional_primary.demand_failing_candidates,
            "demand_meeting_candidates": result.conventional_primary.demand_meeting_candidates,
            "winner_reason": result.conventional_primary.winner_reason,
            "winner": _outcome_dict(result.conventional_primary.winner),
            "runner_up": None if result.conventional_primary.runner_up is None else _outcome_dict(result.conventional_primary.runner_up),
        },
        "mrt_primary": {
            "evaluated_candidates": result.mrt_primary.evaluated_candidates,
            "rejected_candidates": result.mrt_primary.rejected_candidates,
            "demand_failing_candidates": result.mrt_primary.demand_failing_candidates,
            "demand_meeting_candidates": result.mrt_primary.demand_meeting_candidates,
            "winner_reason": result.mrt_primary.winner_reason,
            "winner": _outcome_dict(result.mrt_primary.winner),
            "runner_up": None if result.mrt_primary.runner_up is None else _outcome_dict(result.mrt_primary.runner_up),
        },
        "demand_sweep": [row.__dict__ for row in result.demand_sweep],
        "production_capacity_gate_rows": [row.__dict__ for row in result.production_capacity_gate_rows],
        "representative_timelines": [timeline.__dict__ for timeline in result.representative_timelines],
    }

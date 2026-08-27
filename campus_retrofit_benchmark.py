"""F-18 Two-Building Campus Retrofit Benchmark.

CONTROLLED STATIC F-18 BENCHMARK -- reuses 100% existing physics/economics
authorities (spatial_benchmark.py's candidate search/evaluation,
hybrid_optimization.py's joint-schedule Hybrid evaluator, the authoritative
decay engine, infrastructure CapEx/OPEX ledgers, lifecycle economics). No new
physics/economics engine is created here -- only a custom two-building
SYNTHETIC_TEST_GEOMETRY and a thin driver that classifies campus-level vs
building-level architecture.

GOVERNING CAMPUS MODEL:
    BUILDING A (existing): houses CY-001 + RADIOPHARMACY-A (the ONE
    production/release origin), remains Conventional-operated in BOTH cases,
    contributes ZERO new clinical rooms (existing shell, $0 NEW CAPEX per
    section 56/59 -- diagnosed explicitly in the CapEx table, not modeled by
    a new "existing asset" flag inside infrastructure_capex.py).

    BUILDING B (planned retrofit): 4 floors x 10 rooms = 40 candidate
    clinical rooms, offset 500 m (the campus route) from Building A. This is
    the ONLY building whose transport architecture changes between cases.

    CASE 1 (CAMPUS_CONVENTIONAL): Building B served by Conventional
    transport. Modeled directly via `spatial_benchmark.optimize_pathway_layouts
    (pathway="Conventional", ...)` on the campus geometry -- Building B IS the
    geometry's entire clinical room set, so scanner/injection/uptake counts
    and clustering-vs-distribution emerge exactly as they would for a
    standalone pure-Conventional benchmark, just with the 500 m campus route
    baked into every room's route distance.

    CASE 2 (CAMPUS_HYBRID_A_CONVENTIONAL_B_MRT): Building B served by MRT.
    Building A's production/Conventional operation is unchanged (shared,
    always-Conventional production basis) -- this is exactly
    `hybrid_optimization.evaluate_hybrid_zone_candidate`'s existing "100% MRT
    floors" boundary case (already validated:
    `test_hundred_pct_mrt_boundary_all_mrt_mode`), reused verbatim with
    `conventional_floors=()`, `mrt_floors=`Building B's 4 floors. This is
    NEVER called "PURE_MRT" -- the campus remains HYBRID because Building A's
    production is a real, permanent Conventional-operated component of the
    campus (section 2-3).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Literal, Sequence

from facility_engineering_model import (
    CoordinateSystem,
    FacilityEngineeringObjectModel,
    SpatialCoordinate,
    SpatialEdge,
    SpatialNode,
    Space,
)
from hybrid_optimization import HybridEvaluationResult, HybridZoneCandidate, evaluate_hybrid_zone_candidate
from lifecycle_economics import evaluate_lifecycle_economics
from models import PlannerAssumptions, SharedNetworkAssumptions
from spatial_benchmark import (
    BenchmarkGeometry,
    PathwayOptimizationResult,
    ProductionBasis,
    _base_assumptions,
    _production_gate_row,
    _resource_requirements_for_demand,
    build_benchmark_geometry,
    build_production_basis,
    classify_spatial_form,
    compute_retention_envelope,
    optimize_pathway_layouts,
)

CampusArchitecture = Literal[
    "CAMPUS_CONVENTIONAL", "CAMPUS_HYBRID_A_CONVENTIONAL_B_MRT", "DECENTRALIZED_CONVENTIONAL_PRODUCTION",
]

BUILDING_B_FLOOR_COUNT = 4
BUILDING_B_ROOMS_PER_FLOOR = 10
CAMPUS_SEPARATION_M = 500.0
BUILDING_B_DEMAND = 200
BUILDING_A_EXISTING_DEMAND = 100
# Section 9: SYNTHETIC_TEST_EXISTING_BUILDING_A_DEMAND, a controlled benchmark
# assumption -- never presented as measured hospital data.
CAMPUS_TOTAL_DEMAND = BUILDING_A_EXISTING_DEMAND + BUILDING_B_DEMAND
BUILDING_A_INTERNAL_ROUTE_MINUTES = 4.0
# Section 50: Building-A patients get an explicit non-zero internal route
# (SYNTHETIC_TEST_ASSUMPTION) -- Building A's own floor layout is not
# spatially re-optimized here (it is EXISTING/FIXED, section 16).
RADIONUCLIDE = "F-18"


def _building_b_room_id(floor: int, slot: int) -> str:
    return f"B-F{floor}-R{slot:02d}"


def build_two_building_campus_geometry(
    *,
    campus_separation_m: float = CAMPUS_SEPARATION_M,
    floor_count: int = BUILDING_B_FLOOR_COUNT,
    rooms_per_floor: int = BUILDING_B_ROOMS_PER_FLOOR,
    floor_to_floor_height_m: float = 4.0,
    corridor_room_spacing_m: float = 6.0,
) -> BenchmarkGeometry:
    """Section 9-14: deterministic SYNTHETIC_TEST_GEOMETRY -- Building A's
    production origin at (0,0,0), Building B's 4x10 rooms reached via a
    500 m campus route (`EDGE-RP-TO-LOBBY-L0`) plus a deterministic internal
    corridor/vertical-core layout identical in structure to
    `spatial_benchmark.build_benchmark_geometry` (reused pattern, not a new
    route-distance model)."""
    room_ids: list[str] = []
    room_floor_by_id: dict[str, int] = {}
    room_coordinates_by_id: dict[str, SpatialCoordinate] = {}
    nodes: list[SpatialNode] = []
    edges: list[SpatialEdge] = []
    spaces: list[Space] = []

    coordinate_system = CoordinateSystem(
        coordinate_system_id="CAMPUS-CS-001",
        name="Two-building F-18 campus retrofit benchmark",
        building="Campus",
        local_coordinate_system="CAMPUS_LOCAL",
        source_coordinate_reference="synthetic",
        scale_m_per_unit=1.0,
    )

    production_node_id = "NODE-RP-001"
    production_object_id = "RP-001"
    nodes.append(SpatialNode(
        node_id=production_node_id, object_id=production_object_id, kind="equipment",
        coordinate=SpatialCoordinate(
            x_m=0.0, y_m=0.0, z_m=0.0, building="Building A", storey="LEVEL 0",
            local_coordinate_system="CAMPUS_LOCAL", source_coordinate_reference="synthetic",
        ),
        evidence_class="BENCHMARK_ASSUMED", confidence="HIGH",
    ))

    lobby_node_ids: dict[int, str] = {}
    for floor in range(0, floor_count + 1):
        node_id = f"NODE-B-LOBBY-L{floor}"
        lobby_node_ids[floor] = node_id
        nodes.append(SpatialNode(
            node_id=node_id, object_id=f"B-LOBBY-L{floor}", kind="junction",
            coordinate=SpatialCoordinate(
                x_m=campus_separation_m, y_m=0.0, z_m=floor * floor_to_floor_height_m,
                building="Building B", storey=f"LEVEL {floor}",
                local_coordinate_system="CAMPUS_LOCAL", source_coordinate_reference="synthetic",
            ),
            evidence_class="BENCHMARK_ASSUMED", confidence="HIGH",
        ))

    # Section 9/27/36-37: the 500 m campus route -- the ONE edge shared by
    # both Conventional and MRT route calculations (baked into geometry, not
    # a separate hard-coded distance term in either pathway's economics).
    edges.append(SpatialEdge(
        edge_id="EDGE-RP-TO-BUILDING-B-ENTRY", source_node_id=production_node_id,
        destination_node_id=lobby_node_ids[0], length_m=campus_separation_m, vertical_change_m=0.0,
        edge_type="HORIZONTAL", route_corridor_class="CAMPUS_CONNECTION",
        evidence_class="BENCHMARK_ASSUMED", confidence="HIGH",
    ))

    for floor in range(1, floor_count + 1):
        edges.append(SpatialEdge(
            edge_id=f"EDGE-B-ELEV-L{floor-1}-L{floor}", source_node_id=lobby_node_ids[floor - 1],
            destination_node_id=lobby_node_ids[floor], length_m=floor_to_floor_height_m,
            vertical_change_m=floor_to_floor_height_m, edge_type="ELEVATOR",
            route_corridor_class="VERTICAL_GUIDEWAY", evidence_class="BENCHMARK_ASSUMED", confidence="HIGH",
        ))

    for floor in range(1, floor_count + 1):
        for slot in range(1, rooms_per_floor + 1):
            rid = _building_b_room_id(floor, slot)
            room_ids.append(rid)
            room_floor_by_id[rid] = floor
            x = campus_separation_m + slot * corridor_room_spacing_m
            z = floor * floor_to_floor_height_m
            room_coordinates_by_id[rid] = SpatialCoordinate(
                x_m=x, y_m=0.0, z_m=z, building="Building B", storey=f"LEVEL {floor}",
                local_coordinate_system="CAMPUS_LOCAL", source_coordinate_reference="synthetic",
            )
            spaces.append(Space(
                object_id=rid, name=f"Room {rid}", source_identifier=None,
                evidence_class="BENCHMARK_ASSUMED", confidence="HIGH", status="NEW_CANDIDATE",
                building_id="BUILDING-B", storey_id=f"LEVEL-{floor}", notes=("NEUTRAL_CANDIDATE_SPACE",),
            ))
            room_node_id = f"NODE-{rid}"
            nodes.append(SpatialNode(
                node_id=room_node_id, object_id=rid, kind="space", coordinate=room_coordinates_by_id[rid],
                evidence_class="BENCHMARK_ASSUMED", confidence="HIGH", building_id="BUILDING-B",
                storey_id=f"LEVEL-{floor}", room_id=rid, notes=("NEUTRAL_CANDIDATE_SPACE",),
            ))
            edges.append(SpatialEdge(
                edge_id=f"EDGE-B-LOBBY-L{floor}-TO-{rid}", source_node_id=lobby_node_ids[floor],
                destination_node_id=room_node_id, length_m=slot * corridor_room_spacing_m, vertical_change_m=0.0,
                edge_type="HORIZONTAL", route_corridor_class="INTERIOR_CLINICAL_PATH",
                evidence_class="BENCHMARK_ASSUMED", confidence="HIGH",
            ))

    base_model = FacilityEngineeringObjectModel(
        facility_id="FAC-CAMPUS-RETROFIT-A-B", facility_name="Two-building F-18 campus retrofit benchmark",
        project_spatial_mode="RETROFIT", source_type="BENCHMARK", evidence_class="BENCHMARK_ASSUMED",
        maturity="CONCEPTUAL", subscription_tier="BASIC", coordinate_system=coordinate_system,
        spaces=tuple(spaces), nodes=tuple(nodes), edges=tuple(edges),
        primary_route_origin_object_id=production_object_id,
        primary_route_destination_object_ids=(_building_b_room_id(1, 1),),
        route_geometry_status="RECONSTRUCTED", route_distance_source="DERIVED_GEOMETRY",
        clinical_floors_in_scope=floor_count,
        scanner_floors=tuple(f"LEVEL {floor}" for floor in range(1, floor_count + 1)),
        injection_floors=tuple(f"LEVEL {floor}" for floor in range(1, floor_count + 1)),
        uptake_floors=tuple(f"LEVEL {floor}" for floor in range(1, floor_count + 1)),
        include_ground_floor=True,
        notes=(
            "SYNTHETIC_TEST_GEOMETRY: two-building F-18 campus retrofit benchmark.",
            "Building A (existing): CY-001/RADIOPHARMACY-A at (0,0,0), zero clinical rooms, existing shell.",
            "Building B (planned retrofit): 4 floors x 10 rooms, offset 500 m (campus route) from Building A.",
            "BUILDING_B_EXISTING_SHELL_RETROFIT: Building B structural shell assumed existing (SYNTHETIC_TEST_ASSUMPTION).",
        ),
    )

    return BenchmarkGeometry(
        floor_count=floor_count, rooms_per_floor=rooms_per_floor, floor_to_floor_height_m=floor_to_floor_height_m,
        corridor_room_spacing_m=corridor_room_spacing_m, elevator_x_m=campus_separation_m,
        room_ids=tuple(sorted(room_ids)), room_floor_by_id=room_floor_by_id,
        room_coordinates_by_id=room_coordinates_by_id, production_origin_object_id="CY-001",
        release_origin_object_id=production_object_id, base_model=base_model,
    )


@dataclass(frozen=True)
class CampusRetrofitResult:
    campus_architecture: CampusArchitecture
    building_a_new_capex: float
    """Section 56: always 0.0 -- Building A is existing, no upgrade selected."""
    conventional_case: PathwayOptimizationResult
    hybrid_case: HybridEvaluationResult | None
    hybrid_candidate: HybridZoneCandidate | None
    hybrid_spatial_form: str | None


def run_campus_case_1_conventional(
    *, geometry: BenchmarkGeometry, demand: int = BUILDING_B_DEMAND,
) -> PathwayOptimizationResult:
    """CASE 1 = CAMPUS_CONVENTIONAL: Building B served by Conventional
    transport, via the EXISTING pure-pathway candidate search/evaluation
    authority (`optimize_pathway_layouts`) -- scanner/injection/uptake counts
    and clustering-vs-distribution all emerge as outputs (sections 28/44-46),
    never hard-coded."""
    assumptions = _base_assumptions()
    basis = build_production_basis()
    if basis.radionuclide != RADIONUCLIDE:
        raise ValueError(f"F18_PATIENT_ACTIVITY_NOT_CALIBRATED: benchmark production basis is {basis.radionuclide}, not F-18")
    envelope = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=RADIONUCLIDE, pathway="Conventional")
    return optimize_pathway_layouts(pathway="Conventional", demand=demand, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=envelope)


def run_campus_case_2_hybrid(
    *, geometry: BenchmarkGeometry, conventional_winner: PathwayOptimizationResult, demand: int = BUILDING_B_DEMAND,
    mrt_floors: tuple[int, ...] | None = None,
) -> tuple[HybridEvaluationResult, HybridZoneCandidate]:
    """CASE 2 = CAMPUS_HYBRID_A_CONVENTIONAL_B_MRT: Building B served (fully
    or partially, section 55) by MRT, Building A's production remains
    Conventional-operated (shared, section 32-34). `mrt_floors=None` (default)
    evaluates the full 4-floor MRT boundary; any proper subset leaves the
    remaining Building-B floors Conventional (mixed Building-B case, section
    55) -- the campus label stays HYBRID either way (section 2-3), never
    'PURE_MRT'. Building B's resource counts are taken from the SAME
    clinical-bottleneck-derived winner Case 1 already searched (sections
    44-46: never independently hard-coded for Case 2)."""
    assumptions = _base_assumptions()
    basis = build_production_basis()
    network_assumptions = SharedNetworkAssumptions()
    winner_layout = conventional_winner.winner.layout
    all_floors = frozenset(range(1, geometry.floor_count + 1))
    mrt_set = frozenset(mrt_floors) if mrt_floors is not None else all_floors
    conv_set = all_floors - mrt_set
    candidate = HybridZoneCandidate(
        candidate_id=f"CASE2-B-MRT-{'-'.join(str(f) for f in sorted(mrt_set)) or 'NONE'}",
        mrt_floors=mrt_set, conventional_floors=conv_set,
        scanners=winner_layout.scanners, injection_resources=winner_layout.injection_resources,
        uptake_resources=winner_layout.uptake_resources,
    )
    result = evaluate_hybrid_zone_candidate(
        geometry=geometry, candidate=candidate, demand=demand, production_basis=basis,
        assumptions=assumptions, network_assumptions=network_assumptions,
    )
    return result, candidate


# ---------------------------------------------------------------------------
# Section 53-55: full Hybrid Building-B floor-subset optimization -- evaluate
# every physically meaningful non-empty subset of Building B's 4 floors as
# the MRT-served set (remainder Conventional, mixed-Hybrid, section 55),
# never asserting the all-4-floor case is optimal by assumption.
# ---------------------------------------------------------------------------

_ALL_BUILDING_B_FLOOR_SUBSETS: tuple[tuple[int, ...], ...] = tuple(
    tuple(sorted(combo))
    for size in range(1, BUILDING_B_FLOOR_COUNT + 1)
    for combo in itertools.combinations(range(1, BUILDING_B_FLOOR_COUNT + 1), size)
)


@dataclass(frozen=True)
class HybridFloorSubsetOutcome:
    mrt_floors: tuple[int, ...]
    conventional_floors: tuple[int, ...]
    result: HybridEvaluationResult
    candidate: HybridZoneCandidate


def search_hybrid_building_b_floor_subsets(
    *, geometry: BenchmarkGeometry, conventional_winner: PathwayOptimizationResult, demand: int = BUILDING_B_DEMAND,
) -> tuple[HybridFloorSubsetOutcome, ...]:
    """Section 53-54: evaluate all 15 non-empty Building-B floor subsets as
    the MRT-served set (single-floor through all-4-floor), reusing
    `run_campus_case_2_hybrid` for each -- never a second Hybrid engine."""
    outcomes: list[HybridFloorSubsetOutcome] = []
    for subset in _ALL_BUILDING_B_FLOOR_SUBSETS:
        result, candidate = run_campus_case_2_hybrid(geometry=geometry, conventional_winner=conventional_winner, demand=demand, mrt_floors=subset)
        outcomes.append(HybridFloorSubsetOutcome(
            mrt_floors=subset, conventional_floors=tuple(sorted(candidate.conventional_floors)), result=result, candidate=candidate,
        ))
    return tuple(outcomes)


def best_hybrid_floor_subset(outcomes: Sequence[HybridFloorSubsetOutcome]) -> HybridFloorSubsetOutcome:
    """Deterministic winner: highest retention-qualified completed patients,
    then higher qualified lifecycle NPV, then lower total CapEx, then the
    canonical (sorted) floor-subset tuple as a final tie-break."""
    return sorted(
        outcomes,
        key=lambda o: (-o.result.retention_qualified_completed, -o.result.qualified_lifecycle_npv, o.result.total_capex, o.mrt_floors),
    )[0]


# ---------------------------------------------------------------------------
# Sections 9-24: Building-A existing baseline + Study B (full A+B campus)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildingABaseline:
    """Section 14-18: EXISTING_FIXED_BASELINE -- Building A's clinical
    resource inventory, derived ONCE via the SAME clinical-bottleneck
    authority Building B uses (`_resource_requirements_for_demand`), for the
    controlled 100/day Building-A demand, then frozen and reused IDENTICALLY
    across both campus architectures (section 15) -- never re-optimized
    merely because Building B's transport architecture changes."""

    demand: int
    scanners: int
    injection_resources: int
    uptake_resources: int
    inbound_resources: int
    scanner_ids: tuple[str, ...]
    injection_ids: tuple[str, ...]
    uptake_ids: tuple[str, ...]
    internal_route_minutes: float
    new_capex: float
    """Section 17: always 0.0 -- Building A is existing."""


def build_building_a_baseline(*, demand: int = BUILDING_A_EXISTING_DEMAND) -> BuildingABaseline:
    assumptions = _base_assumptions()
    scanners, injection, uptake = _resource_requirements_for_demand(demand, assumptions)
    return BuildingABaseline(
        demand=demand, scanners=scanners, injection_resources=injection, uptake_resources=uptake, inbound_resources=0,
        scanner_ids=tuple(f"A-SCN-{i + 1:03d}" for i in range(scanners)),
        injection_ids=tuple(f"A-INJ-{i + 1:03d}" for i in range(injection)),
        uptake_ids=tuple(f"A-UP-{i + 1:03d}" for i in range(uptake)),
        internal_route_minutes=BUILDING_A_INTERNAL_ROUTE_MINUTES, new_capex=0.0,
    )


def _building_b_resource_ids(prefix: str, count: int) -> tuple[str, ...]:
    """Section 22: building-aware persistent identity for reporting -- never
    transport-mode-prefixed (the underlying shared scheduler/hybrid engines
    keep their plain SCN-xxx/INJ-xxx/UP-xxx convention, section 6 of the
    prior Hybrid Live-State phase; this campus benchmark's OWN accounting
    layer relabels them with the "B-" building prefix since every such
    resource in this study is exclusively a Building-B asset)."""
    return tuple(f"B-{prefix}-{i + 1:03d}" for i in range(count))


@dataclass(frozen=True)
class CampusResourceRow:
    architecture: CampusArchitecture
    building: Literal["A", "B"]
    demand_per_day: int
    scanners: int
    injection_resources: int
    uptake_resources: int
    inbound_resources: int
    transport_mode: str


@dataclass(frozen=True)
class ProductionCapacityRow:
    architecture: CampusArchitecture
    campus_patients_per_day: int
    production_feasible: bool
    unmet_patients: int
    bottleneck: str


@dataclass(frozen=True)
class StudyBFullCampusResult:
    building_a: BuildingABaseline
    conventional_campus_rows: tuple[CampusResourceRow, ...]
    hybrid_campus_rows: tuple[CampusResourceRow, ...]
    conventional_production: ProductionCapacityRow
    hybrid_production: ProductionCapacityRow
    campus_total_demand: int


def _campus_rows_for_building_b(
    *, architecture: CampusArchitecture, building_a: BuildingABaseline,
    b_scanners: int, b_injection: int, b_uptake: int, transport_mode: str,
) -> tuple[CampusResourceRow, ...]:
    return (
        CampusResourceRow(architecture, "A", building_a.demand, building_a.scanners, building_a.injection_resources, building_a.uptake_resources, building_a.inbound_resources, "Conventional"),
        CampusResourceRow(architecture, "B", BUILDING_B_DEMAND, b_scanners, b_injection, b_uptake, 0, transport_mode),
    )


def _campus_production_feasibility(
    *, geometry: BenchmarkGeometry, architecture: CampusArchitecture, campus_demand: int = CAMPUS_TOTAL_DEMAND,
) -> ProductionCapacityRow:
    """Section 39-42: production feasibility is a CY-001 (single shared
    cyclotron) property, evaluated at the CAMPUS total (Building A + Building
    B combined draw) -- never tested against Building-B demand alone.
    Reuses the SAME candidate evaluation authority `optimize_pathway_layouts`
    already uses internally (`patients_production_feasible`), never a
    separate production-capacity model."""
    assumptions = _base_assumptions()
    basis = build_production_basis()
    envelope = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=RADIONUCLIDE, pathway="Conventional")
    result = optimize_pathway_layouts(pathway="Conventional", demand=campus_demand, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=envelope)
    winner = result.winner
    feasible = winner.patients_production_feasible >= campus_demand
    unmet = max(0, campus_demand - winner.patients_production_feasible)
    return ProductionCapacityRow(
        architecture=architecture, campus_patients_per_day=campus_demand, production_feasible=feasible,
        unmet_patients=unmet, bottleneck="CY-001 production capacity" if not feasible else "none (production-feasible)",
    )


def run_study_b_full_campus(
    *, geometry: BenchmarkGeometry, conventional_winner: PathwayOptimizationResult, hybrid_winner: HybridEvaluationResult, hybrid_candidate: HybridZoneCandidate,
) -> StudyBFullCampusResult:
    """Section 9-24: full A+B campus accounting. Building A's baseline is
    computed ONCE (section 15) and reused IDENTICALLY for both architectures.
    Campus totals = Building A + Building B (section 20-21, no double
    counting -- each physical resource belongs to exactly one building)."""
    building_a = build_building_a_baseline()
    b_layout = conventional_winner.winner.layout
    conventional_rows = _campus_rows_for_building_b(
        architecture="CAMPUS_CONVENTIONAL", building_a=building_a,
        b_scanners=b_layout.scanners, b_injection=b_layout.injection_resources, b_uptake=b_layout.uptake_resources,
        transport_mode="Conventional",
    )
    hybrid_rows = _campus_rows_for_building_b(
        architecture="CAMPUS_HYBRID_A_CONVENTIONAL_B_MRT", building_a=building_a,
        b_scanners=hybrid_candidate.scanners, b_injection=hybrid_candidate.injection_resources, b_uptake=hybrid_candidate.uptake_resources,
        transport_mode="MRT" if hybrid_candidate.conventional_floors == frozenset() else "MIXED_MRT_CONVENTIONAL",
    )
    conventional_production = _campus_production_feasibility(geometry=geometry, architecture="CAMPUS_CONVENTIONAL")
    hybrid_production = _campus_production_feasibility(geometry=geometry, architecture="CAMPUS_HYBRID_A_CONVENTIONAL_B_MRT")
    return StudyBFullCampusResult(
        building_a=building_a, conventional_campus_rows=conventional_rows, hybrid_campus_rows=hybrid_rows,
        conventional_production=conventional_production, hybrid_production=hybrid_production, campus_total_demand=CAMPUS_TOTAL_DEMAND,
    )


# ---------------------------------------------------------------------------
# MRT distribution vs second-cyclotron decentralization (CASE A / B / C)
#
# CASE A (CENTRALIZED_CONVENTIONAL): `run_campus_case_1_conventional` (reused
# above, unchanged) -- CY-001/RP-001 in Building A, Conventional 500 m
# delivery to Building B.
#
# CASE B (DECENTRALIZED_CONVENTIONAL_PRODUCTION): a REAL second physical
# production system -- CY-002/RP-B installed IN Building B, reusing the
# EXACT SAME `spatial_benchmark.build_benchmark_geometry()` single-building
# construction (never a new geometry engine) to represent Building B's own
# floors/production origin, with `build_production_basis(cyclotron_instance_id=
# "CY-002", radiopharmacy_release_id="RP-B")` giving CY-002 a genuine catalog
# identity, EOB capacity, and CapEx/OPEX -- never abstract extra MBq.
# Building-B patients therefore receive ONLY internal Building-B transport
# (section 12) -- no 500 m inter-building payload.
#
# CASE C (HYBRID_A_CONVENTIONAL_B_MRT): `run_campus_case_2_hybrid` (reused
# above, unchanged) -- CY-001/RP-001 only, Building B served via MRT.
# ---------------------------------------------------------------------------

CY002_CATALOG_MODEL_ID = "GE_PETTRACE_890"
"""Section 7: same calibrated model as CY-001 (a legitimate, common real-world
choice -- standardizing spares/training/parts). Multiple OTHER calibrated F-18
models exist in the catalog (GE PETtrace 840/860/880, IBA Cyclone KEY/KIUBE);
a full model-selection search via a separate recommendation authority was NOT
exercised this phase (disclosed limitation, not fabricated capability)."""


def run_building_a_standalone(*, demand: int = BUILDING_A_EXISTING_DEMAND) -> PathwayOptimizationResult:
    """Section 16/50: Building A's OWN internal geometry/production/economics
    (never 0 m/0 min internal routes) -- reuses the SAME default single-
    building benchmark geometry construction used everywhere else in this
    repository, with CY-001/RP-001 (defaults) as the production origin.
    Identical across all three cases (Building A is fixed, section 16)."""
    assumptions = _base_assumptions()
    basis = build_production_basis()
    geometry = build_benchmark_geometry(floor_count=BUILDING_B_FLOOR_COUNT, rooms_per_floor=BUILDING_B_ROOMS_PER_FLOOR)
    envelope = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=RADIONUCLIDE, pathway="Conventional")
    return optimize_pathway_layouts(pathway="Conventional", demand=demand, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=envelope)


def run_case_b_decentralized_building_b(
    *, demand: int = BUILDING_B_DEMAND, catalog_model_id: str = CY002_CATALOG_MODEL_ID,
) -> PathwayOptimizationResult:
    """CASE B's Building-B production+clinical evaluation: CY-002/RP-B
    physically located IN Building B (its own standalone geometry, zero
    inter-building distance -- section 12), reusing the identical
    `optimize_pathway_layouts` search authority Building A and Case A/C use."""
    assumptions = _base_assumptions()
    basis = build_production_basis(catalog_model_id=catalog_model_id, cyclotron_instance_id="CY-002", radiopharmacy_release_id="RP-B")
    geometry = build_benchmark_geometry(floor_count=BUILDING_B_FLOOR_COUNT, rooms_per_floor=BUILDING_B_ROOMS_PER_FLOOR)
    envelope = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=RADIONUCLIDE, pathway="Conventional")
    return optimize_pathway_layouts(pathway="Conventional", demand=demand, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=envelope)


@dataclass(frozen=True)
class CapacityVsSpatialValue:
    """Section 8/37/54: CY-002's benefit decomposed into two INDEPENDENT
    questions -- was it needed for aggregate production capacity (it was
    not: CY-001 alone is production-feasible for the full 300/day campus,
    established in the prior phase), versus was it economically useful
    because of reduced Building-B transport distance/decay (measured
    directly as the qualified-throughput/NPV delta versus Case A)."""

    cy001_alone_feasible_for_campus_total: bool
    capacity_value_qualified_patients_per_day: int
    """Always 0 in this benchmark: CY-001 alone already met 300/day (section 8)."""
    spatial_decay_value_qualified_patients_per_day: int
    """Case B's Building-B qualified/day minus Case A's Building-B qualified/day."""
    spatial_decay_value_npv: float


# ---------------------------------------------------------------------------
# Section 15-17/56: existing-Building-A-CY-001 CapEx correction. Both the
# pure-pathway ledger (`_evaluate_layout`) and `evaluate_hybrid_zone_candidate`
# generically price ONE new cyclotron/radiopharmacy per evaluation (they have
# no "this asset already exists elsewhere" concept) -- correct at THIS
# benchmark's reporting layer for Case A/C (Building A's CY-001/RP-001 are
# EXISTING, section 15/17), while Case B's CY-002/RP-B genuinely deserves
# that charge (a real new asset, section 25). NPV is recomputed with the
# corrected CapEx via the SAME `evaluate_lifecycle_economics` authority, never
# a new economics engine.
# ---------------------------------------------------------------------------

_EXISTING_CYCLOTRON_LEDGER_COMPONENTS = frozenset({"Cyclotron purchase", "Cyclotron installation", "Radiopharmacy infrastructure"})


def new_study_capex_pathway(outcome, *, cyclotron_is_existing: bool) -> float:
    """Excludes Building A's existing CY-001/RP-001 CapEx line items from a
    pure-pathway outcome's ledger when `cyclotron_is_existing=True`."""
    if not cyclotron_is_existing:
        return outcome.total_capex
    return sum(row.subtotal for row in outcome.pathway_result.capex_result.ledger if row.component not in _EXISTING_CYCLOTRON_LEDGER_COMPONENTS)


def new_study_capex_hybrid(result: HybridEvaluationResult, assumptions: PlannerAssumptions, *, cyclotron_is_existing: bool = True) -> float:
    """Excludes the phantom existing-CY-001 cyclotron CapEx
    `evaluate_hybrid_zone_candidate`'s formula always includes generically
    (Case C always uses the existing CY-001, section 14)."""
    if not cyclotron_is_existing:
        return result.total_capex
    cyclotron_capex = assumptions.cyclotron_purchase_capex + assumptions.cyclotron_installation_capex
    return result.total_capex - cyclotron_capex


def recompute_corrected_npv(
    *, corrected_capex: float, qualified_patients_per_day: int, annual_opex: float, assumptions: PlannerAssumptions,
) -> float:
    """Recomputes lifecycle NPV with the corrected (existing-asset-excluded)
    CapEx, reusing the SAME `evaluate_lifecycle_economics` call pattern and
    inputs `evaluate_hybrid_zone_candidate`/`_evaluate_layout` already use
    (installed/starting demand = qualified patients/day, zero growth) --
    never a new NPV formula."""
    result = evaluate_lifecycle_economics(
        initial_capex=corrected_capex,
        installed_capacity_per_day=float(qualified_patients_per_day),
        annual_opex=annual_opex,
        revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=assumptions.operating_days_per_year,
        discount_rate_pct=assumptions.discount_rate_pct,
        analysis_years=assumptions.analysis_years,
        starting_demand_per_day=float(qualified_patients_per_day),
        annual_demand_growth_rate=0.0,
    )
    return result.final_npv


@dataclass(frozen=True)
class CorrectedCaseEconomics:
    """Section 15-17/38-41: New-study CapEx and NPV with Building A's
    existing CY-001/RP-001 correctly excluded (Case A/C) or genuinely
    included (Case B's real CY-002/RP-B)."""

    architecture: str
    qualified_patients_per_day: int
    annual_opex: float
    new_capex: float
    npv: float


def compute_corrected_economics(comparison: "ThreeWayCampusComparison") -> tuple[CorrectedCaseEconomics, CorrectedCaseEconomics, CorrectedCaseEconomics]:
    assumptions = _base_assumptions()
    a = comparison.case_a_building_b.winner
    b = comparison.case_b_building_b.winner
    c = comparison.case_c_building_b

    a_capex = new_study_capex_pathway(a, cyclotron_is_existing=True)
    a_npv = recompute_corrected_npv(corrected_capex=a_capex, qualified_patients_per_day=a.patients_retention_qualified_completed, annual_opex=a.annual_total_opex, assumptions=assumptions)
    b_capex = new_study_capex_pathway(b, cyclotron_is_existing=False)
    b_npv = recompute_corrected_npv(corrected_capex=b_capex, qualified_patients_per_day=b.patients_retention_qualified_completed, annual_opex=b.annual_total_opex, assumptions=assumptions)
    c_capex = new_study_capex_hybrid(c, assumptions, cyclotron_is_existing=True)
    c_npv = recompute_corrected_npv(corrected_capex=c_capex, qualified_patients_per_day=c.retention_qualified_completed, annual_opex=c.total_annual_opex, assumptions=assumptions)

    return (
        CorrectedCaseEconomics("CENTRALIZED_CONVENTIONAL", a.patients_retention_qualified_completed, a.annual_total_opex, a_capex, a_npv),
        CorrectedCaseEconomics("DECENTRALIZED_CONVENTIONAL_PRODUCTION", b.patients_retention_qualified_completed, b.annual_total_opex, b_capex, b_npv),
        CorrectedCaseEconomics("HYBRID_A_CONVENTIONAL_B_MRT", c.retention_qualified_completed, c.total_annual_opex, c_capex, c_npv),
    )


def compute_capacity_vs_spatial_value(
    *, case_a_building_b: PathwayOptimizationResult, case_b_building_b: PathwayOptimizationResult, campus_production_feasible_with_cy001_alone: bool,
) -> CapacityVsSpatialValue:
    """NPV delta uses the CORRECTED (existing-CY-001-excluded for A, genuinely-
    new-CY-002 for B) figures -- the correction is NOT symmetric (only Case A's
    phantom existing-cyclotron charge is removed), so it does not cancel out
    of a naive uncorrected delta."""
    assumptions = _base_assumptions()
    a = case_a_building_b.winner
    b = case_b_building_b.winner
    a_capex = new_study_capex_pathway(a, cyclotron_is_existing=True)
    a_npv = recompute_corrected_npv(corrected_capex=a_capex, qualified_patients_per_day=a.patients_retention_qualified_completed, annual_opex=a.annual_total_opex, assumptions=assumptions)
    b_capex = new_study_capex_pathway(b, cyclotron_is_existing=False)
    b_npv = recompute_corrected_npv(corrected_capex=b_capex, qualified_patients_per_day=b.patients_retention_qualified_completed, annual_opex=b.annual_total_opex, assumptions=assumptions)
    return CapacityVsSpatialValue(
        cy001_alone_feasible_for_campus_total=campus_production_feasible_with_cy001_alone,
        capacity_value_qualified_patients_per_day=0 if campus_production_feasible_with_cy001_alone else (b.patients_retention_qualified_completed - a.patients_retention_qualified_completed),
        spatial_decay_value_qualified_patients_per_day=b.patients_retention_qualified_completed - a.patients_retention_qualified_completed,
        spatial_decay_value_npv=b_npv - a_npv,
    )


@dataclass(frozen=True)
class ThreeWayCampusComparison:
    case_a_building_b: PathwayOptimizationResult
    case_b_building_b: PathwayOptimizationResult
    case_c_building_b: HybridEvaluationResult
    case_c_candidate: HybridZoneCandidate
    building_a: BuildingABaseline
    capacity_vs_spatial: CapacityVsSpatialValue


def run_three_way_campus_comparison(*, geometry: BenchmarkGeometry) -> ThreeWayCampusComparison:
    """Sections 2-3/39-42: builds all three primary alternatives against the
    IDENTICAL 300/day campus demand (100 A + 200 B), reusing every existing
    evaluation function above -- no forced winner, no new economics engine."""
    case_a = run_campus_case_1_conventional(geometry=geometry)
    case_b = run_case_b_decentralized_building_b()
    case_c, case_c_candidate = run_campus_case_2_hybrid(geometry=geometry, conventional_winner=case_a)
    building_a = build_building_a_baseline()
    campus_feasible = _campus_production_feasibility(geometry=geometry, architecture="CAMPUS_CONVENTIONAL").production_feasible
    capacity_vs_spatial = compute_capacity_vs_spatial_value(
        case_a_building_b=case_a, case_b_building_b=case_b, campus_production_feasible_with_cy001_alone=campus_feasible,
    )
    return ThreeWayCampusComparison(
        case_a_building_b=case_a, case_b_building_b=case_b, case_c_building_b=case_c, case_c_candidate=case_c_candidate,
        building_a=building_a, capacity_vs_spatial=capacity_vs_spatial,
    )


# ---------------------------------------------------------------------------
# Extended distance sensitivity (100/250/500/750/1000 m): re-optimizes all
# THREE architectures at each distance -- Case C's Hybrid floor subset is
# genuinely re-searched every time (section 9/10), never scaled from the
# 500 m result. Case B is distance-independent by physical construction
# (Building B's own standalone geometry, section 15) -- computed once and
# reused, never re-derived with a fabricated distance penalty.
# ---------------------------------------------------------------------------

DISTANCE_GRID_M: tuple[float, ...] = (100.0, 250.0, 500.0, 750.0, 1000.0)


@dataclass(frozen=True)
class DistanceSensitivityRow:
    distance_m: float
    architecture: str
    physically_feasible: bool
    infeasibility_reason: str | None
    qualified_per_day: int
    mean_retention: float
    minimum_retention: float
    clinical_completions: int
    required_eob_activity_mbq: float | None
    new_capex: float
    annual_opex: float
    npv: float
    mrt_floors: tuple[int, ...]
    conventional_floors: tuple[int, ...]
    scanners: int
    injection_resources: int
    uptake_resources: int


def _pathway_retention_stats(outcome) -> tuple[float, float]:
    fractions = [t.retained_fraction_at_administration for t in outcome.pathway_result.decay_summary.patient_traces]
    if not fractions:
        return 0.0, 0.0
    return sum(fractions) / len(fractions), min(fractions)


def _hybrid_retention_stats(result: HybridEvaluationResult) -> tuple[float, float]:
    fractions = [t.retained_fraction for t in result.patient_traces]
    if not fractions:
        return 0.0, 0.0
    return sum(fractions) / len(fractions), min(fractions)


def run_distance_sensitivity_study(
    *, distances_m: Sequence[float] = DISTANCE_GRID_M,
) -> tuple[DistanceSensitivityRow, ...]:
    """Sections 2-10/45: 5 distances x 3 architectures = 15 rows, EVERY
    architecture genuinely re-optimized at every distance (Case A/C rerun
    the real candidate search; Case B is recomputed identically each time
    since it is physically distance-independent by construction, never
    scaled)."""
    assumptions = _base_assumptions()
    cy002_basis = build_production_basis(catalog_model_id=CY002_CATALOG_MODEL_ID, cyclotron_instance_id="CY-002", radiopharmacy_release_id="RP-B")
    case_b = run_case_b_decentralized_building_b()  # distance-independent (section 15)
    b_mean_retention, b_min_retention = _pathway_retention_stats(case_b.winner)
    b_capex = new_study_capex_pathway(case_b.winner, cyclotron_is_existing=False)
    b_npv = recompute_corrected_npv(
        corrected_capex=b_capex, qualified_patients_per_day=case_b.winner.patients_retention_qualified_completed,
        annual_opex=case_b.winner.annual_total_opex, assumptions=assumptions,
    )
    b_gate = _production_gate_row(BUILDING_B_DEMAND, "Conventional", case_b.winner, cy002_basis)

    rows: list[DistanceSensitivityRow] = []
    for distance_m in distances_m:
        geometry = build_two_building_campus_geometry(campus_separation_m=distance_m)

        try:
            case_a = run_campus_case_1_conventional(geometry=geometry)
        except ValueError as exc:
            # Section 39: at long enough distance, the geometric retention
            # envelope can leave zero physically feasible candidates for
            # Centralized Conventional -- a genuine, reportable regime
            # boundary, never silently hidden. Case B's independently-searched
            # layout (same clinical-bottleneck authority) stands in for the
            # unavailable Case-A layout when sizing Case C's fallback.
            fallback_scanners = case_b.winner.layout.scanners
            fallback_injection = case_b.winner.layout.injection_resources
            fallback_uptake = case_b.winner.layout.uptake_resources
            rows.append(DistanceSensitivityRow(
                distance_m=distance_m, architecture="CENTRALIZED_CONVENTIONAL",
                physically_feasible=False, infeasibility_reason=str(exc),
                qualified_per_day=0, mean_retention=0.0, minimum_retention=0.0, clinical_completions=0,
                required_eob_activity_mbq=None, new_capex=float("nan"), annual_opex=float("nan"), npv=float("-inf"),
                mrt_floors=(), conventional_floors=(), scanners=fallback_scanners, injection_resources=fallback_injection,
                uptake_resources=fallback_uptake,
            ))

            rows.append(DistanceSensitivityRow(
                distance_m=distance_m, architecture="DECENTRALIZED_CONVENTIONAL_PRODUCTION",
                physically_feasible=True, infeasibility_reason=None,
                qualified_per_day=case_b.winner.patients_retention_qualified_completed,
                mean_retention=b_mean_retention, minimum_retention=b_min_retention,
                clinical_completions=case_b.winner.patients_clinically_completed,
                required_eob_activity_mbq=b_gate.required_eob_activity_mbq, new_capex=b_capex, annual_opex=case_b.winner.annual_total_opex, npv=b_npv,
                mrt_floors=(), conventional_floors=tuple(sorted(case_b.winner.layout.active_floors)),
                scanners=case_b.winner.layout.scanners, injection_resources=case_b.winner.layout.injection_resources,
                uptake_resources=case_b.winner.layout.uptake_resources,
            ))

            floor_outcomes = search_hybrid_building_b_floor_subsets(geometry=geometry, conventional_winner=case_b, demand=BUILDING_B_DEMAND)
            best = best_hybrid_floor_subset(floor_outcomes)
            c_mean_retention, c_min_retention = _hybrid_retention_stats(best.result)
            c_capex = new_study_capex_hybrid(best.result, assumptions, cyclotron_is_existing=True)
            c_npv = recompute_corrected_npv(
                corrected_capex=c_capex, qualified_patients_per_day=best.result.retention_qualified_completed,
                annual_opex=best.result.total_annual_opex, assumptions=assumptions,
            )
            rows.append(DistanceSensitivityRow(
                distance_m=distance_m, architecture="HYBRID_A_CONVENTIONAL_B_MRT",
                physically_feasible=True, infeasibility_reason=None,
                qualified_per_day=best.result.retention_qualified_completed,
                mean_retention=c_mean_retention, minimum_retention=c_min_retention,
                clinical_completions=sum(1 for t in best.result.patient_traces if t.clinically_completed),
                required_eob_activity_mbq=None, new_capex=c_capex, annual_opex=best.result.total_annual_opex, npv=c_npv,
                mrt_floors=best.mrt_floors, conventional_floors=best.conventional_floors,
                scanners=best.candidate.scanners, injection_resources=best.candidate.injection_resources, uptake_resources=best.candidate.uptake_resources,
            ))
            continue

        a_mean_retention, a_min_retention = _pathway_retention_stats(case_a.winner)
        a_capex = new_study_capex_pathway(case_a.winner, cyclotron_is_existing=True)
        a_npv = recompute_corrected_npv(
            corrected_capex=a_capex, qualified_patients_per_day=case_a.winner.patients_retention_qualified_completed,
            annual_opex=case_a.winner.annual_total_opex, assumptions=assumptions,
        )
        a_gate = _production_gate_row(BUILDING_B_DEMAND, "Conventional", case_a.winner, build_production_basis())
        rows.append(DistanceSensitivityRow(
            distance_m=distance_m, architecture="CENTRALIZED_CONVENTIONAL",
            physically_feasible=True, infeasibility_reason=None,
            qualified_per_day=case_a.winner.patients_retention_qualified_completed,
            mean_retention=a_mean_retention, minimum_retention=a_min_retention,
            clinical_completions=case_a.winner.patients_clinically_completed,
            required_eob_activity_mbq=a_gate.required_eob_activity_mbq, new_capex=a_capex, annual_opex=case_a.winner.annual_total_opex, npv=a_npv,
            mrt_floors=(), conventional_floors=tuple(sorted(case_a.winner.layout.active_floors)),
            scanners=case_a.winner.layout.scanners, injection_resources=case_a.winner.layout.injection_resources,
            uptake_resources=case_a.winner.layout.uptake_resources,
        ))

        rows.append(DistanceSensitivityRow(
            distance_m=distance_m, architecture="DECENTRALIZED_CONVENTIONAL_PRODUCTION",
            physically_feasible=True, infeasibility_reason=None,
            qualified_per_day=case_b.winner.patients_retention_qualified_completed,
            mean_retention=b_mean_retention, minimum_retention=b_min_retention,
            clinical_completions=case_b.winner.patients_clinically_completed,
            required_eob_activity_mbq=b_gate.required_eob_activity_mbq, new_capex=b_capex, annual_opex=case_b.winner.annual_total_opex, npv=b_npv,
            mrt_floors=(), conventional_floors=tuple(sorted(case_b.winner.layout.active_floors)),
            scanners=case_b.winner.layout.scanners, injection_resources=case_b.winner.layout.injection_resources,
            uptake_resources=case_b.winner.layout.uptake_resources,
        ))

        floor_outcomes = search_hybrid_building_b_floor_subsets(geometry=geometry, conventional_winner=case_a)
        best = best_hybrid_floor_subset(floor_outcomes)
        c_mean_retention, c_min_retention = _hybrid_retention_stats(best.result)
        c_capex = new_study_capex_hybrid(best.result, assumptions, cyclotron_is_existing=True)
        c_npv = recompute_corrected_npv(
            corrected_capex=c_capex, qualified_patients_per_day=best.result.retention_qualified_completed,
            annual_opex=best.result.total_annual_opex, assumptions=assumptions,
        )
        rows.append(DistanceSensitivityRow(
            distance_m=distance_m, architecture="HYBRID_A_CONVENTIONAL_B_MRT",
            physically_feasible=True, infeasibility_reason=None,
            qualified_per_day=best.result.retention_qualified_completed,
            mean_retention=c_mean_retention, minimum_retention=c_min_retention,
            clinical_completions=sum(1 for t in best.result.patient_traces if t.clinically_completed),
            required_eob_activity_mbq=None, new_capex=c_capex, annual_opex=best.result.total_annual_opex, npv=c_npv,
            mrt_floors=best.mrt_floors, conventional_floors=best.conventional_floors,
            scanners=best.candidate.scanners, injection_resources=best.candidate.injection_resources,
            uptake_resources=best.candidate.uptake_resources,
        ))

    return tuple(rows)


def winner_by_distance(rows: Sequence[DistanceSensitivityRow]) -> dict[float, str]:
    """Section 27/45: preferred architecture per distance, read from actual
    NPV among PHYSICALLY FEASIBLE architectures only -- never assumed/forced."""
    winners: dict[float, str] = {}
    by_distance: dict[float, list[DistanceSensitivityRow]] = {}
    for row in rows:
        by_distance.setdefault(row.distance_m, []).append(row)
    for distance_m, group in by_distance.items():
        feasible = [r for r in group if r.physically_feasible]
        winners[distance_m] = max(feasible, key=lambda r: r.npv).architecture
    return winners

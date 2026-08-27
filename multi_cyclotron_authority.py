"""Multi-Radionuclide + Multi-Cyclotron Authority (spatial origin, ON/OFF).

GOVERNANCE-FIRST BUILD: reuses 100% of the existing native production/decay
pipeline's ALREADY-GENERIC multi-asset fleet support
(cyclotron_catalog.build_fleet_from_instances accepts a SEQUENCE of
FacilityCyclotronInstance; decision_pipeline._cycle_relative_requirement_by_radionuclide
already loops `for asset in fleet.assets`, generating per-asset candidate
production cycles keyed by cyclotron_id) -- no second production/decay engine
is created here.

DECAY_MODEL_SUPPORTED vs CYCLOTRON_PRODUCTION_SUPPORTED (sections 6/7/47):
multi_isotope_decay's half-life database supports 6 radionuclides
(F-18, C-11, N-13, O-15, Ga-68, Tc-99m). CY-001 (GE PETtrace 890) is
calibrated for F-18 ONLY. The catalog's multi-isotope-capable model
(GE_PETTRACE_800, supporting F-18/C-11/N-13/O-15/Ga-68) has production
records but NONE calibrated (normalized_eob_activity_mbq is None for every
radionuclide) -- per section 6 ("do not fabricate cyclotron production
capability"), this model is therefore NOT used to claim calibrated multi-
isotope production capacity. Tc-99m is decay-model-supported but has no
calibrated production path on ANY catalog model audited -- the clean
DECAY_MODEL_SUPPORTED-but-NOT-CYCLOTRON_PRODUCTION_SUPPORTED example.

MULTI-CYCLOTRON DEMONSTRATION (sections 12/18/20-25): CY-002 is built as a
SECOND, independently calibrated instance of the SAME already-calibrated
model as CY-001 (GE_PETTRACE_890, F-18-only) at a DISTINCT spatial
coordinate -- this genuinely exercises multi-cyclotron capacity/parallelism/
ON-OFF/spatial-origin authority using only already-calibrated data, with zero
fabrication.

ON/OFF (section 13): implemented as the simplest coherent representation --
inclusion/exclusion of a FacilityCyclotronInstance from the fleet's
`instances` sequence passed to build_fleet_from_instances. ON = included;
OFF = excluded (contributes zero production capacity for that scenario run,
but the instance/asset-state record itself is preserved separately, never
deleted -- section 15/16).

CYCLOTRON_RADIOPHARMACY_COLOCATION (section 19): PROJECT_ASSUMPTION,
coordinate(CY_k) == coordinate(RP_k) for every modeled cyclotron.

MULTI-ORIGIN SPATIAL INTEGRATION (this build): the point where cyclotron-
specific transport origin was previously lost was identified in
production_clinical_schedule.py's `_resolve_conventional_route_components` /
`_resolve_mrt_route_profile`: both always resolved transport origin from a
SINGLE global `model.primary_route_origin_object_id`, regardless of which
cyclotron actually produced a given payload's activity (each payload only
carried `source_batch_id`, and `ProductionBatchReleaseMapping.assigned_cyclotron_id`
was already tracked but never consulted for routing). This is now fixed with a
fully additive, backward-compatible change: `ProductionClinicalScenario` gained
an optional `cyclotron_radiopharmacy_origin_object_id_by_cyclotron_id` map
(default None => existing single-origin behavior is byte-for-byte unchanged);
when provided, `build_production_clinical_schedule` resolves each payload's
actual producing cyclotron (via the batch release mapping) and looks up ITS
radiopharmacy origin for both Conventional (`_schedule_conventional_transport_jobs`)
and MRT (`_schedule_mrt_carrier_transport_jobs`) routing -- no parallel/diagnostic-
only computation, this is the same authoritative code path used everywhere else.

`build_controlled_dual_origin_geometry` builds a small deterministic route-
network (not Euclidean) with RP-001/RP-002 at different graph distances from a
shared set of destinations, used to prove Conventional/MRT route and retention
genuinely respond to which cyclotron produced a patient's dose (sections 17,
25-26, 46-48), and to test MRT-network-disconnected-origin classification
(section 10).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cyclotron_catalog import (
    FacilityCyclotronInstance,
    build_fleet_from_instances,
    find_production_records,
    load_cyclotron_catalog,
)
from cyclotron_production_windows import (
    CyclotronAsset,
    CyclotronFleet,
    CyclotronProductionCapability,
)
from diagnostics import load_radionuclide_half_lives
from facility_engineering_model import (
    CoordinateSystem,
    FacilityEngineeringObjectModel,
    SpatialCoordinate,
    SpatialEdge,
    SpatialNode,
    network_route_distance_m,
)
from models import PlannerAssumptions
from multi_isotope_decay import retained_fraction
from patient_radionuclide_demand import FacilityDayPatientDemand, PatientRadionuclideDemand
from production_clinical_schedule import (
    ProductionClinicalScenario,
    ProductionClinicalScheduleResult,
    build_production_clinical_schedule,
)
from spatial_benchmark import (
    _manual_transport_minutes,
    _mrt_transport_minutes,
    _physical_transition_count,
    _shortest_path_edges,
)

CyclotronScenarioState = Literal["ON", "OFF"]
CyclotronAssetState = Literal["EXISTING", "PROPOSED"]


@dataclass(frozen=True)
class CyclotronSpatialOrigin:
    """PROJECT_ASSUMPTION (section 19): coordinate(CY_k) == coordinate(RP_k).
    `origin_object_id` is the single production/release origin node shared by
    the cyclotron and its co-located radiopharmacy."""

    cyclotron_id: str
    radiopharmacy_id: str
    origin_object_id: str


@dataclass(frozen=True)
class ConfiguredCyclotron:
    cyclotron_id: str
    radiopharmacy_id: str
    origin_object_id: str
    asset_state: CyclotronAssetState
    scenario_state: CyclotronScenarioState
    instance: FacilityCyclotronInstance


def radionuclide_support_report(catalog_model_id: str) -> dict[str, str]:
    """Sections 6/7: DECAY_MODEL_SUPPORTED vs CYCLOTRON_PRODUCTION_SUPPORTED,
    never conflated. Returns {radionuclide: status} for every decay-model-
    known radionuclide, where status is one of:
      DECAY_AND_CALIBRATED_PRODUCTION_SUPPORTED
      DECAY_SUPPORTED_PRODUCTION_LISTED_NOT_CALIBRATED
      DECAY_SUPPORTED_PRODUCTION_NOT_SUPPORTED
    """
    catalog = load_cyclotron_catalog()
    model = catalog.by_id(catalog_model_id)
    half_lives = load_radionuclide_half_lives()
    report: dict[str, str] = {}
    for radionuclide in sorted(half_lives):
        if radionuclide not in model.supported_radionuclides:
            report[radionuclide] = "DECAY_SUPPORTED_PRODUCTION_NOT_SUPPORTED"
            continue
        records = find_production_records(catalog=catalog, catalog_model_id=catalog_model_id, radionuclide=radionuclide)
        calibrated = any(record.normalized_eob_activity_mbq is not None for record in records)
        report[radionuclide] = (
            "DECAY_AND_CALIBRATED_PRODUCTION_SUPPORTED" if calibrated else "DECAY_SUPPORTED_PRODUCTION_LISTED_NOT_CALIBRATED"
        )
    return report


def build_calibrated_cyclotron_asset(
    *,
    instance_id: str,
    catalog_model_id: str,
    radionuclide: str,
    release_processing_minutes: float,
) -> CyclotronAsset:
    """Reuses spatial_benchmark.build_production_basis's exact enrichment
    pattern (same calibrated-record lookup, no new physics) to build one
    calibrated CyclotronAsset for an arbitrary instance_id/model, so multiple
    independently-identified cyclotrons of the same (or different) calibrated
    model can be assembled into one multi-asset fleet."""
    catalog = load_cyclotron_catalog()
    instance = FacilityCyclotronInstance(instance_id=instance_id, catalog_model_id=catalog_model_id)
    fleet, warnings = build_fleet_from_instances(catalog=catalog, instances=(instance,))
    if warnings or fleet is None or len(fleet.assets) != 1:
        raise ValueError(f"Cannot build a calibrated single-asset fleet for {instance_id}/{catalog_model_id}: {warnings}")
    base_asset = fleet.assets[0]
    capability = base_asset.capability
    calibrated_eob = capability.calibrated_eob_activity_mbq_by_radionuclide or {}
    if calibrated_eob.get(radionuclide) is None:
        raise ValueError(
            f"{catalog_model_id} has no calibrated EOB activity record for {radionuclide}; "
            "refusing to fabricate cyclotron production capability (see engineering_authority "
            "CYCLOTRON_RADIONUCLIDE_COMPATIBILITY)."
        )
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
    return CyclotronAsset(
        cyclotron_id=instance_id,
        capability=enriched_capability,
        model_identifier=base_asset.model_identifier,
        manufacturer=base_asset.manufacturer,
        installed_quantity=base_asset.installed_quantity,
        capability_provenance=base_asset.capability_provenance,
    )


def build_multi_cyclotron_scenario(
    *,
    cy001_scenario_state: CyclotronScenarioState = "ON",
    cy002_scenario_state: CyclotronScenarioState = "OFF",
) -> tuple[CyclotronFleet, tuple[ConfiguredCyclotron, ...]]:
    """Sections 12-25: assembles a 2-cyclotron fleet -- CY-001 (EXISTING,
    F-18-only, at the established benchmark origin) and CY-002 (PROPOSED,
    same calibrated F-18-only model, at a DISTINCT co-located
    cyclotron/radiopharmacy origin) -- honoring each cyclotron's ON/OFF
    scenario state (OFF = excluded from the fleet entirely for this run,
    contributing zero production capacity, section 13-16)."""
    configured: list[ConfiguredCyclotron] = []
    assets: list[CyclotronAsset] = []

    cy001_instance = FacilityCyclotronInstance(instance_id="CY-001", catalog_model_id="GE_PETTRACE_890")
    configured.append(ConfiguredCyclotron(
        cyclotron_id="CY-001", radiopharmacy_id="RP-001", origin_object_id="RP-001",
        asset_state="EXISTING", scenario_state=cy001_scenario_state, instance=cy001_instance,
    ))
    if cy001_scenario_state == "ON":
        assets.append(build_calibrated_cyclotron_asset(
            instance_id="CY-001", catalog_model_id="GE_PETTRACE_890", radionuclide="F-18", release_processing_minutes=71.0,
        ))

    cy002_instance = FacilityCyclotronInstance(instance_id="CY-002", catalog_model_id="GE_PETTRACE_890")
    configured.append(ConfiguredCyclotron(
        cyclotron_id="CY-002", radiopharmacy_id="RP-002", origin_object_id="RP-002",
        asset_state="PROPOSED", scenario_state=cy002_scenario_state, instance=cy002_instance,
    ))
    if cy002_scenario_state == "ON":
        assets.append(build_calibrated_cyclotron_asset(
            instance_id="CY-002", catalog_model_id="GE_PETTRACE_890", radionuclide="F-18", release_processing_minutes=71.0,
        ))

    if not assets:
        raise ValueError("At least one cyclotron must be ON")
    fleet = CyclotronFleet(assets=tuple(assets), fleet_id="MULTI_CYCLOTRON_BENCHMARK")
    return fleet, tuple(configured)


# ---------------------------------------------------------------------------
# Multi-origin spatial integration (sections 3-11, 17, 25-26, 44-52)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PatientOriginTrace:
    """Patient->cyclotron->cycle->origin traceability record (section 5)."""

    patient_id: str
    radionuclide: str
    cyclotron_id: str
    production_cycle_id: int
    radiopharmacy_origin_id: str
    release_time_minutes: float


def origin_object_id_by_cyclotron_id(configured: tuple[ConfiguredCyclotron, ...]) -> dict[str, str]:
    """Cyclotron -> radiopharmacy release origin object_id registry (section 4/6)."""
    return {entry.cyclotron_id: entry.origin_object_id for entry in configured}


def validate_payload_origin(
    *,
    cyclotron_id: str,
    claimed_origin_object_id: str,
    configured: tuple[ConfiguredCyclotron, ...],
) -> tuple[bool, str]:
    """Section 34/45: authority check -- a payload's claimed transport origin
    must match the origin actually registered for the cyclotron that produced
    it. Returns (is_valid, message)."""
    registry = origin_object_id_by_cyclotron_id(configured)
    registered_origin = registry.get(cyclotron_id)
    if registered_origin is None:
        return False, f"Unknown radiopharmacy origin for cyclotron {cyclotron_id}"
    if claimed_origin_object_id != registered_origin:
        return False, (
            f"Payload produced by {cyclotron_id} (origin={registered_origin}) claims transport "
            f"origin {claimed_origin_object_id} -- cyclotron/radiopharmacy origin mismatch."
        )
    return True, "OK"


def build_controlled_dual_origin_geometry(*, include_rp002_in_network: bool = True) -> FacilityEngineeringObjectModel:
    """Deterministic controlled route-network geometry (section 17): RP-001 and
    RP-002 at different graph positions, with destinations D-NEAR-A (closer to
    RP-001) and D-NEAR-B (closer to RP-002), connected by a single corridor
    chain so route distance reflects actual graph-edge-path length, not a
    Euclidean shortcut. D-NEAR-A sits on a different level than RP-001/RP-002
    so the route includes a genuine vertical (elevator) transition.

    When `include_rp002_in_network` is False, RP-002 is present as a node but
    has NO edges connecting it to the route network at all -- used to prove
    MRT-network-disconnected-origin classification (section 10).
    """
    coordinate_system = CoordinateSystem(
        coordinate_system_id="DUAL-ORIGIN-CS-001",
        name="Controlled dual-origin geometry",
        local_coordinate_system="DUAL_ORIGIN_LOCAL",
        source_coordinate_reference="synthetic",
        scale_m_per_unit=1.0,
    )

    def _node(node_id: str, object_id: str, x_m: float, z_m: float) -> SpatialNode:
        return SpatialNode(
            node_id=node_id,
            object_id=object_id,
            kind="space" if object_id.startswith("D-") else "equipment",
            coordinate=SpatialCoordinate(
                x_m=x_m, y_m=0.0, z_m=z_m,
                building="Controlled Benchmark", storey=f"LEVEL {int(z_m // 4)}",
                local_coordinate_system="DUAL_ORIGIN_LOCAL", source_coordinate_reference="synthetic",
            ),
            evidence_class="BENCHMARK_ASSUMED",
            confidence="HIGH",
        )

    nodes = [
        _node("NODE-RP-001", "RP-001", x_m=0.0, z_m=0.0),
        _node("NODE-D-NEAR-A", "D-NEAR-A", x_m=20.0, z_m=4.0),
        _node("NODE-D-NEAR-B", "D-NEAR-B", x_m=80.0, z_m=0.0),
        _node("NODE-RP-002", "RP-002", x_m=100.0, z_m=0.0),
    ]

    def _edge(edge_id: str, source: str, destination: str, length_m: float, vertical_m: float = 0.0) -> SpatialEdge:
        return SpatialEdge(
            edge_id=edge_id, source_node_id=source, destination_node_id=destination,
            length_m=length_m, vertical_change_m=vertical_m,
            edge_type="ELEVATOR" if vertical_m else "HORIZONTAL",
            route_corridor_class="INTERIOR_CLINICAL_PATH",
            evidence_class="BENCHMARK_ASSUMED", confidence="HIGH",
        )

    edges = [
        _edge("EDGE-RP1-TO-DA", "NODE-RP-001", "NODE-D-NEAR-A", length_m=20.0, vertical_m=4.0),
        _edge("EDGE-DA-TO-DB", "NODE-D-NEAR-A", "NODE-D-NEAR-B", length_m=60.0, vertical_m=4.0),
    ]
    if include_rp002_in_network:
        edges.append(_edge("EDGE-DB-TO-RP2", "NODE-D-NEAR-B", "NODE-RP-002", length_m=20.0))

    return FacilityEngineeringObjectModel(
        facility_id="FAC-DUAL-ORIGIN-CONTROL",
        facility_name="Controlled dual-origin spatial benchmark",
        project_spatial_mode="RETROFIT",
        source_type="BENCHMARK",
        evidence_class="BENCHMARK_ASSUMED",
        maturity="CONCEPTUAL",
        subscription_tier="BASIC",
        coordinate_system=coordinate_system,
        nodes=tuple(nodes),
        edges=tuple(edges),
        primary_route_origin_object_id="RP-001",
        primary_route_destination_object_ids=("D-NEAR-A", "D-NEAR-B"),
        route_geometry_status="RECONSTRUCTED",
        route_distance_source="DERIVED_GEOMETRY",
    )


@dataclass(frozen=True)
class OriginRouteMetrics:
    origin_object_id: str
    destination_object_id: str
    distance_m: float
    vertical_m: float
    transitions: int
    manual_minutes: float
    mrt_minutes: float


def route_metrics_from_origin(
    *,
    model: FacilityEngineeringObjectModel,
    origin_object_id: str,
    destination_object_id: str,
    assumptions: PlannerAssumptions,
) -> OriginRouteMetrics:
    """Sections 7/9/25-26: computes real route-network (not Euclidean) distance,
    vertical transitions, Conventional and MRT transport minutes from an
    ARBITRARY origin node to a destination, reusing spatial_benchmark's exact
    physics functions. Raises ValueError (network-disconnected) if no route
    exists between the origin and destination -- callers use this to classify
    MRT_ORIGIN_NOT_NETWORK_CONNECTED (section 10)."""
    node_ids = {node.object_id: node.node_id for node in model.nodes if node.object_id}
    origin_node_id = node_ids[origin_object_id]
    destination_node_id = node_ids[destination_object_id]
    path_edges = _shortest_path_edges(model, origin_node_id, destination_node_id)
    distance_m = sum(float(edge.length_m) for edge in path_edges)
    vertical_m = sum(abs(float(edge.vertical_change_m)) for edge in path_edges)
    transitions = _physical_transition_count(path_edges)
    return OriginRouteMetrics(
        origin_object_id=origin_object_id,
        destination_object_id=destination_object_id,
        distance_m=distance_m,
        vertical_m=vertical_m,
        transitions=transitions,
        manual_minutes=_manual_transport_minutes(distance_m, vertical_m, assumptions),
        mrt_minutes=_mrt_transport_minutes(distance_m, vertical_m, transitions, assumptions),
    )


def build_single_origin_production_clinical_scenario(
    *,
    cyclotron_id: str,
    radiopharmacy_origin_object_id: str,
    pathway: Literal["Conventional", "MRT"],
    geometry: FacilityEngineeringObjectModel,
    patient_count: int,
    assumptions: PlannerAssumptions | None = None,
) -> ProductionClinicalScenario:
    """Section 46/47 controlled test scaffold: an F-18 patient population produced
    entirely by ONE named cyclotron/origin, routed to the SAME destinations via
    the REAL authoritative scheduling pipeline (build_production_clinical_schedule),
    so producing from RP-001 vs RP-002 can be directly compared for the identical
    destination set."""
    asset = build_calibrated_cyclotron_asset(
        instance_id=cyclotron_id, catalog_model_id="GE_PETTRACE_890", radionuclide="F-18", release_processing_minutes=71.0,
    )
    fleet = CyclotronFleet(assets=(asset,), fleet_id=f"SINGLE_ORIGIN_{cyclotron_id}")
    demand = FacilityDayPatientDemand(
        patients=tuple(
            PatientRadionuclideDemand(patient_id=f"P{i+1}", radionuclide="F-18", prescribed_activity_mbq=200.0)
            for i in range(patient_count)
        )
    )
    return ProductionClinicalScenario(
        facility_day_demand=demand,
        requested_batch_count_by_radionuclide={"F-18": 1},
        cyclotron_fleet=fleet,
        transport_minutes=5.0,
        injection_service_minutes=10.0,
        uptake_minutes=45.0,
        scanner_service_minutes=20.0,
        injection_resources=2,
        uptake_resources=2,
        scanners=2,
        distribution_concurrency=2,
        operating_day_minutes=1080.0,
        production_horizon_minutes=1080.0,
        pathway=pathway,
        facility_engineering_model=geometry,
        planner_assumptions=assumptions or PlannerAssumptions(),
        cyclotron_radiopharmacy_origin_object_id_by_cyclotron_id={cyclotron_id: radiopharmacy_origin_object_id},
    )

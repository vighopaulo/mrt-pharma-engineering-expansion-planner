"""OpenUSD Phase 2A: Recognizable Hospital + Dynamic Foundation Demonstration.

GOVERNANCE: reuses the Phase 1B static scene (recognizable scanner/
cyclotron/radiopharmacy/room context) verbatim via
`generate_openusd_hospital_visual_demo.py` -- never a second hospital
definition. Adds exactly ONE controlled moving MRT carrier proof on top,
using the existing `canonical_spatial_authority.build_mrt_trunk`/
`build_mrt_carrier` object builders (never a parallel carrier class) and the
Phase 2A vendor-neutral `dynamic_scene_state_authority` contract + the
`openusd_spatial_adapter` time-sample adapter functions.

SCANNER/CYCLOTRON/RADIOPHARMACY REMAIN STATIC in this build (section 8) --
only the ONE synthetic carrier receives time samples.

CARRIERTRAJECTORY BRIDGE (section 10): `mrt_service_class_authority.
CarrierTrajectory` provides real, scheduler-derived `start_time_minutes`/
`end_time_minutes`/`status` for ONE mission -- it carries NO spatial
coordinates and NO intermediate waypoint (confirmed by audit). The bridge
below reuses those three real fields verbatim for the trajectory's start and
end samples; the single intermediate waypoint/time is explicitly synthetic
(never claimed to be scheduler-derived) and is clearly labeled as such.
"""

from __future__ import annotations

import os

import canonical_spatial_authority as csa
import dynamic_scene_state_authority as dss
import mrt_service_class_authority as msc
import openusd_spatial_adapter as usda
from generate_openusd_hospital_visual_demo import DEFAULT_ASSET_DIR, build_demo_registry, configure_geometry_assets

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SCENE_PATH = os.path.join(DEFAULT_ASSET_DIR, "mrt_pharma_hospital_dynamic_foundation_demo.usda")
DEFAULT_MANIFEST_PATH = os.path.join(_MODULE_DIR, "OPENUSD_DYNAMIC_FOUNDATION_DEMO_MANIFEST.md")

CARRIER_ID = "MRT-CARRIER-001"
CARRIER_TRUNK_ID = "MRT-TRUNK-DEMO"


def build_carrier_trajectory_bridge(registry: csa.SpatialObjectRegistry) -> tuple[msc.CarrierTrajectory, dss.DynamicObjectTrajectory]:
    """Section 10: real `CarrierTrajectory` (scheduler-derived timing/status)
    + an explicit, honestly-synthetic spatial bridge -- ROOM-RP-101 and
    ROOM-SCN-202 positions are read from the SAME canonical registry
    (never a second copy of coordinates)."""
    origin = registry.get("ROOM-RP-101").transform
    destination = registry.get("ROOM-SCN-202").transform
    route_length_m = csa.compute_global_distance(registry, "ROOM-RP-101", "ROOM-SCN-202")

    mission = msc.MrtServiceMission(
        mission_id="M-CARRIER-DEMO", carrier_id=CARRIER_ID, service_class="RADIOPHARMACEUTICAL_NUCLEAR",
        route_length_m=route_length_m, start_minutes=0.0,
    )
    scheduled, unresolved = msc.schedule_service_missions([mission])
    if unresolved or not scheduled:
        raise RuntimeError("controlled carrier mission could not be scheduled -- foundation proof requires a resolved mission")
    carrier_trajectory = msc.build_carrier_trajectory(
        mission, scheduled[0], mrtway_object_id=CARRIER_ID, route_id="ROUTE-RP-TO-SCN",
    )

    start_time = carrier_trajectory.start_time_minutes
    end_time = carrier_trajectory.end_time_minutes
    intermediate_time = start_time + (end_time - start_time) / 2.0  # synthetic midpoint -- NOT scheduler-derived
    intermediate_position = (
        (origin.position_x + destination.position_x) / 2.0,
        (origin.position_y + destination.position_y) / 2.0,
        (origin.position_z + destination.position_z) / 2.0,
    )
    end_movement_state = carrier_trajectory.status if carrier_trajectory.status in dss.MovementState.__args__ else "UNKNOWN"

    dynamic_trajectory = dss.build_linear_trajectory(
        canonical_object_id=CARRIER_ID,
        waypoints_m=[
            (origin.position_x, origin.position_y, origin.position_z),
            intermediate_position,
            (destination.position_x, destination.position_y, destination.position_z),
        ],
        times_minutes=[start_time, intermediate_time, end_time],
        movement_states=["MOVING", "MOVING", end_movement_state],
        provenance=(
            "start/end time+status reused verbatim from mrt_service_class_authority.CarrierTrajectory "
            "(scheduler-derived); intermediate waypoint/time is SYNTHETIC_CONTROLLED_FOUNDATION_PROOF, "
            "not scheduler-derived"
        ),
    )
    return carrier_trajectory, dynamic_trajectory


def build_dynamic_registry() -> tuple[csa.SpatialObjectRegistry, object]:
    registry, model = build_demo_registry()
    csa.build_mrt_trunk(registry, trunk_id=CARRIER_TRUNK_ID, facility_id=registry.get("BLDG-HOSP-A").facility_id)
    csa.build_mrt_carrier(registry, carrier_id=CARRIER_ID, facility_id=registry.get("BLDG-HOSP-A").facility_id, network_object_id=CARRIER_TRUNK_ID)
    return registry, model


def _write_manifest(
    manifest_path: str, *, carrier_trajectory: msc.CarrierTrajectory, dynamic_trajectory: dss.DynamicObjectTrajectory, prim_path: str,
) -> None:
    lines = [
        "# OpenUSD Dynamic Foundation Demo Manifest",
        "",
        "Non-authoritative presentation summary only.",
        "",
        f"- simulation time basis: `{dss.MRT_SIMULATION_TIME_UNIT}` (MRT Pharma authoritative unit)",
        "- USD time-code mapping: 1 USD TimeCode = 1 simulation second (`timeCodesPerSecond=1.0`)",
        f"- moving canonical object ID: `{dynamic_trajectory.canonical_object_id}`",
        f"- number of time samples: {len(dynamic_trajectory.samples)}",
        f"- start position (m): ({dynamic_trajectory.samples[0].position_x_m}, {dynamic_trajectory.samples[0].position_y_m}, {dynamic_trajectory.samples[0].position_z_m})",
        f"- end position (m): ({dynamic_trajectory.samples[-1].position_x_m}, {dynamic_trajectory.samples[-1].position_y_m}, {dynamic_trajectory.samples[-1].position_z_m})",
        f"- movement state sequence: {[s.movement_state for s in dynamic_trajectory.samples]}",
        f"- OpenUSD prim path: `{prim_path}`",
        f"- underlying CarrierTrajectory status (real, scheduler-derived): `{carrier_trajectory.status}`",
        "- engineering-authority statement: canonical identity/transform/dimensions/room-floor assignment remain exclusively owned by `canonical_spatial_authority.py`; nothing above changes them.",
        "- visualization-authority statement: OpenUSD/`dynamic_scene_state_authority` represent presentation-only dynamic state; they are not engineering, routing, or economic authorities.",
    ]
    with open(manifest_path, "w") as handle:
        handle.write("\n".join(lines) + "\n")


def generate_dynamic_demo(
    *, asset_dir: str = DEFAULT_ASSET_DIR, scene_path: str = DEFAULT_SCENE_PATH, manifest_path: str | None = DEFAULT_MANIFEST_PATH,
):
    if not usda.OPENUSD_RUNTIME_AVAILABLE:
        raise usda.OpenUsdRuntimeNotAvailable("OpenUSD runtime not available -- cannot generate the dynamic foundation demo.")
    registry, _model = build_dynamic_registry()
    geometry_assets, catalog_bindings = configure_geometry_assets(asset_dir)
    stage, path_registry, export_result = usda.export_registry_to_stage(registry, catalog_bindings=catalog_bindings, geometry_assets=geometry_assets)

    carrier_trajectory, dynamic_trajectory = build_carrier_trajectory_bridge(registry)
    prim_path = path_registry.resolve_by_mrtway_id(CARRIER_ID)
    usda.configure_stage_time_basis(stage, start_time_minutes=dynamic_trajectory.start_time_minutes, end_time_minutes=dynamic_trajectory.end_time_minutes)
    usda.author_dynamic_object_trajectory(stage, prim_path=prim_path, trajectory=dynamic_trajectory)

    os.makedirs(os.path.dirname(scene_path), exist_ok=True)
    usda.save_stage_to_usda(stage, scene_path)
    if manifest_path is not None:
        _write_manifest(manifest_path, carrier_trajectory=carrier_trajectory, dynamic_trajectory=dynamic_trajectory, prim_path=prim_path)
    return {
        "scene_path": scene_path, "manifest_path": manifest_path, "registry": registry, "path_registry": path_registry,
        "export_result": export_result, "carrier_trajectory": carrier_trajectory, "dynamic_trajectory": dynamic_trajectory,
        "carrier_prim_path": prim_path,
    }


def main() -> None:
    result = generate_dynamic_demo()
    print("OPENUSD_DYNAMIC_DEMO_SCENE =", result["scene_path"])
    print("OPENUSD_DYNAMIC_DEMO_MANIFEST =", result["manifest_path"])
    print("DYNAMIC_OBJECT_COUNT =", 1)
    print("TIME_SAMPLE_COUNT =", len(result["dynamic_trajectory"].samples))
    print("USD_OUTPUT_SIZE_BYTES =", os.path.getsize(result["scene_path"]))


if __name__ == "__main__":
    main()

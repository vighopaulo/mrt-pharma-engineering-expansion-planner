"""Super-Build 1: Four-Technology Parity View + PTS Profiles.

GOVERNANCE: a DERIVED_VIEW authority (Sec 93). It NEVER re-implements per-mode
physics/economics -- it composes the existing owners into the normalized
`TransportParityResult` contract so Manual / PTS / AGV-light / AGV-heavy / MRT
can be compared on the SAME schema (physics + capacity + CapEx + OPEX +
provenance), WITHOUT ranking them (Sec 73-74). Ranking is the future
optimizer's job.

It also adds configurable PTS PROFILES (Sec 25) as a thin view over the
existing `conventional_transport_authority.PneumaticTubeNetwork` -- vendor/
facility size profiles, never a second PTS engine.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

import conventional_transport_authority as cta
import floor_agv_amr_authority as agv
from transport_mode_scope_authority import TransportParityResult

# ===========================================================================
# 1. PTS profiles (Sec 25) -- thin views over the existing PneumaticTubeNetwork.
#    Each carries provenance; the ACTIVE benchmark (DEFAULT_PTS_NETWORK) is
#    preserved as one profile so existing behaviour is unchanged.
# ===========================================================================

@dataclass(frozen=True)
class PtsProfile:
    profile_id: str
    network: cta.PneumaticTubeNetwork
    carrier_internal_diameter_mm: float
    carrier_length_mm: float
    provenance: str


PTS_PROFILE_STANDARD_110MM = PtsProfile(
    profile_id="PTS_STANDARD_110MM",
    network=cta.DEFAULT_PTS_NETWORK,  # preserved active benchmark (6.0 m/s, 2 kg capsule)
    carrier_internal_diameter_mm=110.0, carrier_length_mm=300.0,
    provenance="CONTROLLED_ENGINEERING_ASSUMPTION (common 110 mm hospital PTS carrier planning profile; active repo benchmark preserved)",
)

PTS_PROFILE_LARGE_160MM = PtsProfile(
    profile_id="PTS_LARGE_160MM",
    network=replace(cta.DEFAULT_PTS_NETWORK, network_id="LARGE_BORE_PTS", capsule_payload_kg=3.0),
    carrier_internal_diameter_mm=160.0, carrier_length_mm=400.0,
    provenance="CONTROLLED_ENGINEERING_ASSUMPTION (larger-bore hospital PTS carrier planning profile; NOT vendor-calibrated)",
)

PTS_PROFILES: Mapping[str, PtsProfile] = {
    PTS_PROFILE_STANDARD_110MM.profile_id: PTS_PROFILE_STANDARD_110MM,
    PTS_PROFILE_LARGE_160MM.profile_id: PTS_PROFILE_LARGE_160MM,
}


# ===========================================================================
# 2. Parity views -- one TransportParityResult per mode. Economics use the
#    EXISTING per-mode functions; loaded_annual_cost_per_fte is caller-supplied
#    (the shared labor basis), never invented here.
# ===========================================================================

def manual_parity_view(
    *, policy: cta.PorterOperatingPolicy, stream: str, mission_minutes: float,
    required_fte: float, annual_labor_opex: float, cart: cta.CartClass | None = None,
    study_scope: str = "CAPITAL_PLANNING",
) -> TransportParityResult:
    cart_capex = cta.cart_new_study_capex(cart, study_scope=study_scope) if cart is not None else 0.0
    cart_maint = cart.annual_maintenance_opex if cart is not None else 0.0
    return TransportParityResult(
        transport_mode="MANUAL", configuration_id="PORTER" + ("+CART" if cart else ""), payload_stream=stream,
        eligibility="see transport_mode_eligibility_authority", route_time_minutes=mission_minutes,
        route_time_status="MODELED", capacity_basis="porter peak-concurrency FTE (compute_porter_resource_requirement)",
        required_resources=f"{required_fte} FTE",
        known_capex_usd=cart_capex, unknown_capex_components=(),
        known_annual_opex_usd=annual_labor_opex + cart_maint,
        unknown_opex_components=("Radiation exposure monitoring (NOT_MODELED)",),
        total_opex_status="KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED",
        provenance="conventional_transport_authority (PorterOperatingPolicy)", calibration_status="CONTROLLED_ENGINEERING_ASSUMPTION",
        known_limitations=("Human energy N/A", "Labor-dominated OPEX"),
    )


def pts_parity_view(
    *, profile: PtsProfile, stream: str, station_count: int, loaded_annual_cost_per_fte: float,
    study_scope: str = "CAPITAL_PLANNING",
) -> TransportParityResult:
    net = replace(profile.network, station_count=station_count, asset_status="PROPOSED")
    capex = cta.pts_new_study_capex(net, study_scope=study_scope)
    opex = cta.pts_annual_opex(net, loaded_annual_cost_per_fte=loaded_annual_cost_per_fte)
    route_min = net.dispatch_minutes + (net.network_length_m or 0.0) / net.speed_m_per_s / 60.0 + net.station_handling_minutes
    return TransportParityResult(
        transport_mode="PTS", configuration_id=profile.profile_id, payload_stream=stream,
        eligibility="see transport_mode_eligibility_authority", route_time_minutes=route_min, route_time_status="MODELED",
        capacity_basis="carrier/station peak-concurrency (pts_required_station_count)",
        required_resources=f"{station_count} stations",
        known_capex_usd=capex, unknown_capex_components=("Building penetrations/retrofit complexity (NOT_CALIBRATED)",),
        known_annual_opex_usd=opex,
        unknown_opex_components=("Blower calibrated power (CONTROLLED_BENCHMARK)", "Diverter/controls service (NOT_CALIBRATED)"),
        total_opex_status="KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED",
        provenance="conventional_transport_authority.PneumaticTubeNetwork", calibration_status="CONTROLLED_ENGINEERING_ASSUMPTION",
        known_limitations=(f"Capsule {profile.network.capsule_payload_kg} kg limit", "Bulk linen/large sterile excluded"),
    )


def floor_agv_parity_view(
    *, profile: agv.FloorAgvProfile, stream: str, fleet: int, charging_stations: int,
    mission_minutes: float, capex: agv.FloorAgvCapexResult, opex: agv.FloorAgvOpexResult,
) -> TransportParityResult:
    return TransportParityResult(
        transport_mode=profile.vehicle_class, configuration_id=profile.vehicle_class, payload_stream=stream,
        eligibility="see transport_mode_eligibility_authority", route_time_minutes=mission_minutes, route_time_status="MODELED",
        capacity_basis="workload×(cycle+charging)/available-minutes fleet (compute_floor_agv_fleet)",
        required_resources=f"{fleet} vehicles, {charging_stations} charging stations",
        known_capex_usd=capex.known_capex_subtotal, unknown_capex_components=capex.unknown_capex_components,
        known_annual_opex_usd=opex.known_annual_opex_subtotal, unknown_opex_components=opex.unknown_opex_components,
        total_opex_status=opex.total_opex_status,
        provenance="floor_agv_amr_authority (free-roaming FLOOR_AGV_AMR)", calibration_status="CONTROLLED_ENGINEERING_ASSUMPTION",
        known_limitations=(f"payload {profile.payload_mass_limit_kg} kg limit", "Radiopharm QUALIFICATION_REQUIRED", "Battery/charging duty"),
    )


def mrt_parity_view_reference(*, stream: str, route_time_minutes: float | None) -> TransportParityResult:
    """MRT is REFERENCE-ONLY in this build (Sec 14): the view reads the
    canonical MRT authorities and never modifies them. CapEx/OPEX are marked
    as owned by the canonical MRT authority (not recomputed here)."""
    return TransportParityResult(
        transport_mode="MRT", configuration_id="CANONICAL_COMPACT_MRT", payload_stream=stream,
        eligibility="shared_mrt_multistream_authority.evaluate_light_mrt_stream_compatibility (preserved)",
        route_time_minutes=route_time_minutes, route_time_status="MODELED" if route_time_minutes is not None else "NOT_CALIBRATED",
        capacity_basis="canonical heterogeneous carrier fleet (preserved)",
        required_resources="canonical carriers (mrt_carrier_fleet, preserved)",
        known_capex_usd=None, unknown_capex_components=("Owned by canonical MRT authority (not recomputed in parity build)",),
        known_annual_opex_usd=None,
        unknown_opex_components=("Standby/controls/cooling electricity NOT_CALIBRATED (canonical authority)",),
        total_opex_status="OWNED_BY_CANONICAL_MRT_AUTHORITY_REFERENCE_ONLY",
        provenance="mrt_canonical_configuration + shared_mrt_multistream_authority (REFERENCE, unchanged)",
        calibration_status="CONTROLLED_ENGINEERING_ASSUMPTION",
        known_limitations=("5 kg gross moving mass ceiling", "Bulk linen excluded", "Reference-only in this build"),
    )

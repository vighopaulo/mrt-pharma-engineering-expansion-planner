"""Super-Build 1: Common Transport-Mode Eligibility Authority.

GOVERNANCE / ONE-AUTHORITY-PER-CONCEPT: this is the SINGLE authority that
answers "CAN THIS PAYLOAD/MISSION USE THIS TRANSPORT MODE UNDER THIS
CONFIGURATION?" across ALL transport families (Sec 51). It COMPOSES the
existing per-mode owners -- it never re-implements or duplicates their
eligibility logic:

    MANUAL / PTS / RGHT  -> conventional_transport_authority.TECHNOLOGY_STREAM_COMPATIBILITY
    DEDICATED RP-PTS     -> dedicated_rp_pts_authority.RP_PTS_COMPATIBLE_STREAMS
    MRT                  -> shared_mrt_multistream_authority.evaluate_light_mrt_stream_compatibility
    FLOOR AGV/AMR        -> floor_agv_amr_authority.evaluate_floor_agv_payload

INVARIANT (Sec 52): PAYLOAD -> ELIGIBILITY -> ALLOWED MODES -> (future)
OPTIMIZATION. This module establishes the eligibility gate that MUST precede
any optimization; economic attractiveness NEVER makes an ineligible mode
valid (Sec 63/91). This build does NOT integrate the optimizer.

Radiopharmaceutical transport is NOT universally granted: PTS and both
AGV/AMR classes default to QUALIFICATION_REQUIRED (Sec 40/53); Manual is
ELIGIBLE only with shielded-container procedure; MRT is governed by its own
canonical mass/eligibility authority (Sec 14, preserved untouched).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import conventional_transport_authority as cta
import dedicated_rp_pts_authority as rp
import shared_mrt_multistream_authority as smx
import floor_agv_amr_authority as agv

# ===========================================================================
# 1. Canonical transport-mode family identifiers (Sec 10/57).
# ===========================================================================

TransportModeFamily = Literal[
    "MANUAL", "PTS", "DEDICATED_RP_PTS", "AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS", "MRT",
]

ALL_TRANSPORT_MODE_FAMILIES: tuple[TransportModeFamily, ...] = (
    "MANUAL", "PTS", "DEDICATED_RP_PTS", "AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS", "MRT",
)

# Canonical payload/mission streams (Sec 17). Uses the general-logistics
# identifiers (CLEAN_LINEN, not LAUNDRY_CLEAN_LINEN) that the conventional +
# light-MRT authorities consume; the MRT service-class alias bridge lives in
# mrt_service_class_authority (never renamed here).
CanonicalStream = Literal[
    "RADIOPHARMACEUTICAL_NUCLEAR", "SPECIMEN_BLOOD", "PHARMACY_INFUSION",
    "STERILE_CLEAN_SUPPLY", "CLEAN_LINEN",
]

EligibilityStatus = Literal[
    "ELIGIBLE", "INELIGIBLE", "QUALIFICATION_REQUIRED", "FACILITY_VALIDATION_REQUIRED", "NOT_MODELED",
]

# ===========================================================================
# 2. Specimen sub-identity (Sec 26-27/55): a general compatible specimen may
#    be PTS-eligible; a PTS-sensitive specimen must NOT silently inherit that.
# ===========================================================================

SpecimenSensitivity = Literal["GENERAL_COMPATIBLE", "PTS_SENSITIVE"]


@dataclass(frozen=True)
class TransportEligibilityQuery:
    """Sec 51 inputs -- what/where/how, never assumed."""
    mode: TransportModeFamily
    stream: str
    payload_mass_kg: float | None = None
    payload_volume_l: float | None = None
    specimen_sensitivity: SpecimenSensitivity | None = None
    # Facility/technology qualification states (default: not qualified).
    radiopharm_qualified: bool = False
    pts_sensitive_specimen_validated: bool = False
    manual_shielding_configured: bool = True  # shielded-container courier procedure available
    agv_profile: "agv.FloorAgvProfile | None" = None


@dataclass(frozen=True)
class TransportEligibilityResult:
    mode: TransportModeFamily
    stream: str
    eligibility: EligibilityStatus
    fallback_required: bool
    reason: str
    provenance: str
    calibration_status: str


def _manual(query: TransportEligibilityQuery) -> TransportEligibilityResult:
    stream = query.stream
    if stream == "RADIOPHARMACEUTICAL_NUCLEAR":
        if query.manual_shielding_configured:
            return TransportEligibilityResult(
                "MANUAL", stream, "ELIGIBLE", False,
                "Shielded-container porter courier -- established conventional nuclear path.",
                "conventional_transport_authority + stream_mode_compatibility.csv", "CONTROLLED_ENGINEERING_ASSUMPTION",
            )
        return TransportEligibilityResult(
            "MANUAL", stream, "QUALIFICATION_REQUIRED", True,
            "Manual radiopharmaceutical courier requires configured shielded-container procedure.",
            "conventional_transport_authority", "CONTROLLED_ENGINEERING_ASSUMPTION",
        )
    eligible = cta.is_technology_compatible("MANUAL_PORTER", stream)
    return TransportEligibilityResult(
        "MANUAL", stream, "ELIGIBLE" if eligible else "INELIGIBLE", not eligible,
        f"{stream} {'in' if eligible else 'not in'} MANUAL_PORTER compatibility set.",
        "conventional_transport_authority.TECHNOLOGY_STREAM_COMPATIBILITY", "CONTROLLED_ENGINEERING_ASSUMPTION",
    )


def _pts(query: TransportEligibilityQuery) -> TransportEligibilityResult:
    stream = query.stream
    if stream == "RADIOPHARMACEUTICAL_NUCLEAR":
        return TransportEligibilityResult(
            "PTS", stream, "QUALIFICATION_REQUIRED", True,
            "Ordinary PTS radiopharmaceutical transport requires facility/vendor qualification "
            "(shielding/contamination/regulatory) -- never granted because a blood tube fits (Sec 28).",
            "Super-Build transport doctrine Sec 12/28", "CONTROLLED_ENGINEERING_ASSUMPTION",
        )
    if not cta.is_technology_compatible("PNEUMATIC_TUBE", stream):
        return TransportEligibilityResult(
            "PTS", stream, "INELIGIBLE", True,
            f"{stream} outside PTS compatibility (bulk/large payloads excluded, Sec 26).",
            "conventional_transport_authority.TECHNOLOGY_STREAM_COMPATIBILITY", "CONTROLLED_ENGINEERING_ASSUMPTION",
        )
    # Compatible stream; a PTS-sensitive specimen still needs facility validation (Sec 27).
    if stream == "SPECIMEN_BLOOD" and query.specimen_sensitivity == "PTS_SENSITIVE" and not query.pts_sensitive_specimen_validated:
        return TransportEligibilityResult(
            "PTS", stream, "FACILITY_VALIDATION_REQUIRED", True,
            "PTS-sensitive specimen must not silently inherit general-specimen PTS eligibility "
            "-- facility validation required (Sec 27).",
            "Super-Build transport doctrine Sec 27", "CONTROLLED_ENGINEERING_ASSUMPTION",
        )
    return TransportEligibilityResult(
        "PTS", stream, "ELIGIBLE", False, f"{stream} within PTS compatibility set.",
        "conventional_transport_authority.TECHNOLOGY_STREAM_COMPATIBILITY", "CONTROLLED_ENGINEERING_ASSUMPTION",
    )


def _rp_pts(query: TransportEligibilityQuery) -> TransportEligibilityResult:
    stream = query.stream
    if stream in rp.RP_PTS_COMPATIBLE_STREAMS:
        return TransportEligibilityResult(
            "DEDICATED_RP_PTS", stream, "ELIGIBLE", False,
            "Dedicated radiopharmaceutical PTS (nuclear-only, dedicated shielded infrastructure).",
            "dedicated_rp_pts_authority.RP_PTS_COMPATIBLE_STREAMS", rp.RP_PTS_SHIELDING_STATUS,
        )
    return TransportEligibilityResult(
        "DEDICATED_RP_PTS", stream, "INELIGIBLE", True,
        f"{stream} not served by dedicated RP-PTS (nuclear-only; NOT interchangeable with ordinary PTS).",
        "dedicated_rp_pts_authority.RP_PTS_COMPATIBLE_STREAMS", "CONTROLLED_ENGINEERING_ASSUMPTION",
    )


def _floor_agv(query: TransportEligibilityQuery, vehicle_class: agv.FloorAgvClass) -> TransportEligibilityResult:
    profile = query.agv_profile
    if profile is None:
        profile = (
            agv.DEFAULT_LIGHT_CLINICAL_PROFILE if vehicle_class == "AGV_AMR_LIGHT_CLINICAL"
            else agv.DEFAULT_HEAVY_LOGISTICS_PROFILE
        )
    if profile.vehicle_class != vehicle_class:
        raise ValueError(f"agv_profile class {profile.vehicle_class} != requested {vehicle_class}")
    r = agv.evaluate_floor_agv_payload(
        profile=profile, stream=query.stream, payload_mass_kg=query.payload_mass_kg, payload_volume_l=query.payload_volume_l,
    )
    if r.status == "QUALIFICATION_REQUIRED":
        elig: EligibilityStatus = "QUALIFICATION_REQUIRED"
    elif r.eligible:
        elig = "ELIGIBLE"
    else:
        elig = "INELIGIBLE"
    return TransportEligibilityResult(
        vehicle_class, query.stream, elig, not r.eligible, r.reason,
        "floor_agv_amr_authority.evaluate_floor_agv_payload", "CONTROLLED_ENGINEERING_ASSUMPTION",
    )


def _mrt(query: TransportEligibilityQuery) -> TransportEligibilityResult:
    """MRT eligibility is governed by the PRESERVED canonical mass/eligibility
    authority (never re-implemented here). CLEAN_LINEN (13.5 kg > 5 kg) is
    UNSUPPORTED_BY_LIGHT_MRT by that authority."""
    stream = query.stream
    try:
        compat = smx.evaluate_light_mrt_stream_compatibility(stream)
    except ValueError:
        return TransportEligibilityResult(
            "MRT", stream, "NOT_MODELED", True, f"{stream} not in canonical MRT mass authority.",
            "shared_mrt_multistream_authority.evaluate_light_mrt_stream_compatibility", "NOT_CALIBRATED",
        )
    if compat.compatible:
        return TransportEligibilityResult(
            "MRT", stream, "ELIGIBLE", False,
            f"fully-loaded {compat.fully_loaded_mass_kg} kg <= canonical {compat.ceiling_kg} kg ceiling.",
            "shared_mrt_multistream_authority.evaluate_light_mrt_stream_compatibility", compat.provenance,
        )
    return TransportEligibilityResult(
        "MRT", stream, "INELIGIBLE", True,
        f"fully-loaded {compat.fully_loaded_mass_kg} kg exceeds canonical {compat.ceiling_kg} kg ceiling "
        "(bulk linen excluded; Manual fallback).",
        "shared_mrt_multistream_authority.evaluate_light_mrt_stream_compatibility", compat.provenance,
    )


def evaluate_transport_eligibility(query: TransportEligibilityQuery) -> TransportEligibilityResult:
    """THE single cross-mode eligibility gate (Sec 51). Dispatches to the
    existing per-mode owner; never re-implements their logic."""
    mode = query.mode
    if mode == "MANUAL":
        return _manual(query)
    if mode == "PTS":
        return _pts(query)
    if mode == "DEDICATED_RP_PTS":
        return _rp_pts(query)
    if mode == "AGV_AMR_LIGHT_CLINICAL":
        return _floor_agv(query, "AGV_AMR_LIGHT_CLINICAL")
    if mode == "AGV_AMR_HEAVY_LOGISTICS":
        return _floor_agv(query, "AGV_AMR_HEAVY_LOGISTICS")
    if mode == "MRT":
        return _mrt(query)
    raise ValueError(f"Unknown transport mode family: {mode!r}")


def allowed_modes_for_payload(
    *, stream: str, payload_mass_kg: float | None = None, payload_volume_l: float | None = None,
    specimen_sensitivity: SpecimenSensitivity | None = None, radiopharm_qualified: bool = False,
    pts_sensitive_specimen_validated: bool = False,
    candidate_modes: tuple[TransportModeFamily, ...] = ALL_TRANSPORT_MODE_FAMILIES,
) -> dict[TransportModeFamily, TransportEligibilityResult]:
    """Sec 52: PAYLOAD -> {mode -> eligibility}. The eligibility gate the future
    optimizer will consume; an INELIGIBLE / QUALIFICATION_REQUIRED /
    FACILITY_VALIDATION_REQUIRED mode is NOT an allowed candidate."""
    out: dict[TransportModeFamily, TransportEligibilityResult] = {}
    for mode in candidate_modes:
        out[mode] = evaluate_transport_eligibility(TransportEligibilityQuery(
            mode=mode, stream=stream, payload_mass_kg=payload_mass_kg, payload_volume_l=payload_volume_l,
            specimen_sensitivity=specimen_sensitivity, radiopharm_qualified=radiopharm_qualified,
            pts_sensitive_specimen_validated=pts_sensitive_specimen_validated,
        ))
    return out


def is_allowed(result: TransportEligibilityResult) -> bool:
    """An allowed candidate is strictly ELIGIBLE. QUALIFICATION_REQUIRED /
    FACILITY_VALIDATION_REQUIRED / INELIGIBLE / NOT_MODELED are NOT allowed
    until the required qualification/validation is supplied."""
    return result.eligibility == "ELIGIBLE"

"""Shared MRT Multi-Stream Authority.

GOVERNANCE (sections 1-4): ONE physical MRT network serves BOTH the
protected nuclear MRT authority (`hybrid_optimization.py`,
`infrastructure_capex.py`/`infrastructure_opex.py`, `mrt_carrier_fleet.py` --
all UNCHANGED) and general-oncology-logistics MRT missions (built from the
already-established `LogisticsDemand`/`TransportLoad`/`TransportMission`
objects in `general_oncology_logistics.py`, also UNCHANGED). This module
NEVER creates a second network, a second carrier-fleet sizing formula, a
second CapEx/OPEX ledger authority, or a second event framework -- it
composes the existing authorities and adds ONLY the genuinely new concepts
the spec requires: payload compatibility, payload containers (distinct from
the shared carrier), priority scheduling across the combined workload, and
container/segment capacity semantics.

NUCLEAR CONTAINER (section 8): nuclear radiopharmaceutical shielding/handling
economics are ALREADY counted inside the existing nuclear MRT CapEx/OPEX
authority (carrier + endpoint + base infrastructure lines in
`infrastructure_capex.py`/`infrastructure_opex.py`). This module's
`NUCLEAR_SHIELDED_CONTAINER` is therefore a STRUCTURAL identity only -- its
`unit_capex` is `"ALREADY_INCLUDED_IN_EXISTING_MRT_CARRIER_AUTHORITY"`, never
a second, double-counted cost line.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Literal, Mapping, Sequence

from general_oncology_logistics import (
    LogisticsPriority,
    LogisticsStream,
    SpecimenBloodSubtype,
    TransportLoad,
    TransportMission,
    convert_load_to_mrt_missions,
)
from hybrid_optimization import HybridEvaluationResult, HybridPatientTrace
from infrastructure_capex import CapexLedgerItem
from infrastructure_opex import OpexLedgerItem, merge_shared_and_mode_specific_ledgers, recompute_ledger_totals
from mrt_carrier_fleet import MrtCarrierFleetResult, resolve_mrt_carrier_fleet
from mrt_canonical_configuration import (
    TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M as _CANONICAL_TWO_WAY_GUIDEWAY_CAPEX_PER_M,
    MrtRuntimeConfig,
)

# NOTE: `CarrierHardwareClass`/`CARRIER_HARDWARE_REGISTRY`/`compute_carrier_fleet_capex`
# are the ESTABLISHED nuclear-shielded/general-light hardware-class authority,
# defined in operational_day_orchestrator.py. That module imports
# mrt_service_class_authority, which imports THIS module (as `smx`) at load
# time -- a module-level import here would be circular. Imported lazily
# (inside the functions that need it) instead; this still reuses the SAME
# authority, never a duplicate mapping/pricing scheme.

StudyScope = Literal["OPERATIONAL_ONLY", "CAPITAL_PLANNING"]
AssetStatus = Literal["EXISTING", "PROPOSED"]

# ---------------------------------------------------------------------------
# MRT payload compatibility (section 5) -- explicit, never all-compatible
# ---------------------------------------------------------------------------

MrtPayloadClass = Literal[
    "NUCLEAR_RADIOPHARMACEUTICAL", "PHARMACY_INFUSION", "SPECIMEN", "BLOOD_PRODUCT",
    "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY",
]
CompatibilityStatus = Literal["COMPATIBLE", "COMPATIBLE_WITH_CONTAINER", "INCOMPATIBLE", "NOT_CALIBRATED"]

MRT_PAYLOAD_COMPATIBILITY: Mapping[MrtPayloadClass, CompatibilityStatus] = {
    "NUCLEAR_RADIOPHARMACEUTICAL": "COMPATIBLE_WITH_CONTAINER",
    "PHARMACY_INFUSION": "COMPATIBLE_WITH_CONTAINER",
    "SPECIMEN": "COMPATIBLE_WITH_CONTAINER",
    "BLOOD_PRODUCT": "COMPATIBLE_WITH_CONTAINER",
    "CLEAN_LINEN": "COMPATIBLE_WITH_CONTAINER",
    "STERILE_CLEAN_SUPPLY": "COMPATIBLE_WITH_CONTAINER",
}


def is_mrt_payload_compatible(payload_class: MrtPayloadClass) -> bool:
    status = MRT_PAYLOAD_COMPATIBILITY.get(payload_class, "NOT_CALIBRATED")
    return status in ("COMPATIBLE", "COMPATIBLE_WITH_CONTAINER")


def stream_to_payload_class(stream: LogisticsStream, *, subtype: SpecimenBloodSubtype | None = None) -> MrtPayloadClass:
    """Section 5/11: SPECIMEN_BLOOD's subtype resolves to the two distinct
    payload classes -- never a single merged 'specimen_blood' class."""
    if stream == "SPECIMEN_BLOOD":
        if subtype is None:
            raise ValueError("SPECIMEN_BLOOD stream requires a subtype to resolve MrtPayloadClass")
        return "SPECIMEN" if subtype == "SPECIMEN" else "BLOOD_PRODUCT"
    if stream == "PHARMACY_INFUSION":
        return "PHARMACY_INFUSION"
    if stream == "CLEAN_LINEN":
        return "CLEAN_LINEN"
    if stream == "STERILE_CLEAN_SUPPLY":
        return "STERILE_CLEAN_SUPPLY"
    raise ValueError(f"Unknown LogisticsStream: {stream}")


# ---------------------------------------------------------------------------
# Carrier vs container (sections 6-11) -- ONE standard carrier platform,
# application-specific payload containers exchanged on it.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MrtContainerClass:
    container_class_id: str
    compatible_payload_classes: frozenset[MrtPayloadClass]
    capacity: float
    unit: str
    load_minutes: float
    unload_minutes: float
    exchange_minutes: float
    """Section 33: container-exchange/cleaning time between incompatible
    payloads on the SAME shared carrier -- never assumed instantaneous."""
    unit_capex: float | Literal["NOT_CALIBRATED", "ALREADY_INCLUDED_IN_EXISTING_MRT_CARRIER_AUTHORITY"]
    calibration_status: Literal["CONTROLLED_ENGINEERING_ASSUMPTION", "NOT_CALIBRATED", "ALREADY_INCLUDED_ELSEWHERE"]
    asset_status: AssetStatus = "EXISTING"
    provenance: str = "CONTROLLED_ENGINEERING_ASSUMPTION"


DEFAULT_NUCLEAR_SHIELDED_CONTAINER = MrtContainerClass(
    container_class_id="NUCLEAR_SHIELDED_CONTAINER", compatible_payload_classes=frozenset({"NUCLEAR_RADIOPHARMACEUTICAL"}),
    capacity=1.0, unit="dose_payload", load_minutes=1.5, unload_minutes=1.5, exchange_minutes=5.0,
    unit_capex="ALREADY_INCLUDED_IN_EXISTING_MRT_CARRIER_AUTHORITY", calibration_status="ALREADY_INCLUDED_ELSEWHERE",
    provenance="Section 8: nuclear shielding/handling economics remain inside the existing carrier/endpoint/base-infrastructure CapEx (infrastructure_capex.py) -- never a second, duplicated cost line.",
)
DEFAULT_CLINICAL_CLEAN_CONTAINER = MrtContainerClass(
    container_class_id="CLINICAL_CLEAN_CONTAINER", compatible_payload_classes=frozenset({"PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY"}),
    capacity=20.0, unit="tote_equivalent", load_minutes=1.0, unload_minutes=1.0, exchange_minutes=2.0,
    unit_capex=350.0, calibration_status="CONTROLLED_ENGINEERING_ASSUMPTION",
    provenance="Section 9: general clean clinical container -- explicitly NOT validated clinical certification, controlled engineering assumption only.",
)
DEFAULT_LINEN_CONTAINER = MrtContainerClass(
    container_class_id="LINEN_CONTAINER", compatible_payload_classes=frozenset({"CLEAN_LINEN"}),
    capacity=20.0, unit="kg", load_minutes=1.5, unload_minutes=1.5, exchange_minutes=3.0,
    unit_capex=300.0, calibration_status="CONTROLLED_ENGINEERING_ASSUMPTION",
    provenance="Section 10: preserves the CONTROLLED_ENGINEERING_ASSUMPTION 20 kg/container capacity exactly -- never silently increased, never reused as the Conventional cart capacity.",
)
DEFAULT_SPECIMEN_BLOOD_CONTAINER = MrtContainerClass(
    container_class_id="SPECIMEN_BLOOD_CONTAINER", compatible_payload_classes=frozenset({"SPECIMEN", "BLOOD_PRODUCT"}),
    capacity=2.0, unit="specimen_or_blood_container", load_minutes=0.5, unload_minutes=0.5, exchange_minutes=1.5,
    unit_capex=400.0, calibration_status="CONTROLLED_ENGINEERING_ASSUMPTION",
    provenance="Section 11: small controlled container abstraction -- no radioactive decay modeled for this stream.",
)
DEFAULT_STERILE_SUPPLY_CONTAINER = DEFAULT_CLINICAL_CLEAN_CONTAINER
"""Section 9: sterile supply shares the general clean container class
(same clean-handling requirements) -- not a fabricated separate container
merely to inflate the inventory."""

# ---------------------------------------------------------------------------
# Build 2R Light MRT design-point correction (Sections 1-7): a SEPARATE,
# lighter MRT configuration -- does not replace or delete the heavy MRT
# authority (infrastructure_capex.py's mrt_infrastructure_capex/
# vertical_transition_capex/guideway_segment_capex remain fully intact for
# that preserved configuration).
# ---------------------------------------------------------------------------

LIGHT_MRT_LOADED_MASS_CEILING_KG = 5.0
"""Section 1: maximum FULLY LOADED moving mass (payload + carrier structure +
integral shielding where required + all moving hardware), not payload alone.
USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION."""

LIGHT_MRT_GUIDEWAY_CAPEX_PER_M = _CANONICAL_TWO_WAY_GUIDEWAY_CAPEX_PER_M
"""Section 3/13: CONTROLLED_ENGINEERING_ASSUMPTION, NOT vendor-calibrated.
MRT CANONICAL CONFIGURATION CORRECTION: now bound to the single canonical
owner `mrt_canonical_configuration.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M` (=$2,500/m
for a COMPLETE TWO-WAY guideway, NOT per lane, never doubled). This CORRECTS
the prior divergent $2,000/m Light-MRT value. It replaces (never adds to) the
heavy MRT's flat $6,000,000 base infrastructure allowance and $350,000/
transition charge for the current configuration only -- those remain
exclusively charged to the preserved heavy configuration (Section 29)."""

LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT = 1_000.0
"""Section 4: preserves the existing controlled ordinary-endpoint assumption
(same $1,000/endpoint used elsewhere in this benchmark); endpoint quantity
remains geometry/service-derived, never assumed."""

LIGHT_MRT_CARRIER_STRUCTURE_MASS_KG = 1.5
"""Section 1 (non-nuclear streams): disclosed CONTROLLED_LIGHT_MRT_ENGINEERING_ASSUMPTION
for a minimal light integral-carrier shell mass, added to the stream's
established payload mass to derive fully-loaded moving mass."""

LIGHT_MRT_NUCLEAR_INTEGRAL_CARRIER_LOADED_MASS_KG = 5.0
"""Section 1: for radiopharmaceutical service the carrier itself IS the
shielded transport pig (vial -> integrated shielded MRT carrier; no separate
pig plus separate carrier in this design). This assumes the fully-loaded
integral shielded nuclear carrier attains EXACTLY the 5.0 kg ceiling -- a
disclosed, UNVALIDATED, best-case CONTROLLED_LIGHT_MRT_ENGINEERING_ASSUMPTION
pending shielding/dose-rate validation, DELIBERATELY DIFFERENT FROM (lighter
than) the independently-established heavy-carrier-model payload-only figure
`operational_day_orchestrator.SERVICE_CLASS_CONTROLLED_PAYLOAD_MASS_KG
['RADIOPHARMACEUTICAL_NUCLEAR'] = 6.5 kg` (which alone already exceeds this
5.0 kg ceiling). Both figures are disclosed rather than silently reconciled:
if real shielding cannot achieve <=5.0 kg fully loaded, RADIOPHARMACEUTICAL_
NUCLEAR is NOT genuinely Light-MRT-compatible and must use the preserved
heavier MRT configuration instead."""

LIGHT_MRT_STREAM_PAYLOAD_MASS_KG: Mapping[str, float] = {
    "SPECIMEN_BLOOD": 2.0, "PHARMACY_INFUSION": 2.0, "STERILE_CLEAN_SUPPLY": 2.0, "CLEAN_LINEN": 12.0,
}
"""Reuses the independently-established per-stream payload mass figures
(`operational_day_orchestrator.SERVICE_CLASS_CONTROLLED_PAYLOAD_MASS_KG`,
duplicated as float literals here to avoid a circular import -- that module
imports mrt_service_class_authority, which imports this module as `smx`)."""


@dataclass(frozen=True)
class LightMrtCompatibilityResult:
    stream: str
    fully_loaded_mass_kg: float
    ceiling_kg: float
    compatible: bool
    status: Literal["COMPATIBLE", "UNSUPPORTED_BY_LIGHT_MRT"]
    provenance: str


def evaluate_light_mrt_stream_compatibility(stream: str) -> LightMrtCompatibilityResult:
    """Section 6: the physically compatible technology set is derived from
    the ACTUAL fully-loaded moving mass -- LIGHT_MRT is never restricted to
    radiopharmaceuticals, and never force-fitted to bulky/heavy missions."""
    if stream == "RADIOPHARMACEUTICAL_NUCLEAR":
        loaded = LIGHT_MRT_NUCLEAR_INTEGRAL_CARRIER_LOADED_MASS_KG
        provenance = "CONTROLLED_LIGHT_MRT_ENGINEERING_ASSUMPTION (integral shielded carrier, pending shielding/dose-rate validation)"
    else:
        if stream not in LIGHT_MRT_STREAM_PAYLOAD_MASS_KG:
            raise ValueError(f"Unknown stream for Light MRT compatibility: {stream}")
        loaded = LIGHT_MRT_STREAM_PAYLOAD_MASS_KG[stream] + LIGHT_MRT_CARRIER_STRUCTURE_MASS_KG
        provenance = "CONTROLLED_LIGHT_MRT_ENGINEERING_ASSUMPTION (payload + light integral carrier structure)"
    compatible = loaded <= LIGHT_MRT_LOADED_MASS_CEILING_KG
    return LightMrtCompatibilityResult(
        stream=stream, fully_loaded_mass_kg=loaded, ceiling_kg=LIGHT_MRT_LOADED_MASS_CEILING_KG,
        compatible=compatible, status="COMPATIBLE" if compatible else "UNSUPPORTED_BY_LIGHT_MRT", provenance=provenance,
    )


@dataclass(frozen=True)
class LightMrtCapexResult:
    guideway_length_m: float
    guideway_capex: float
    endpoint_count: int
    endpoint_capex: float
    carrier_capex: float
    total_capex: float
    provenance: str = "USER_SUPPLIED_CONTROLLED_LIGHT_MRT_COST_ASSUMPTION"


def compute_light_mrt_capex(*, guideway_length_m: float, endpoint_count: int, carrier_capex: float) -> LightMrtCapexResult:
    """Section 3: C_guideway = L_routed x $2,000/m. Does NOT add the heavy
    $6,000,000 flat base-infrastructure allowance or $350,000/transition
    charge -- those remain exclusive to the preserved heavy MRT configuration.
    `carrier_capex` is supplied by the caller (workload/concurrency-derived,
    reusing the EXISTING heterogeneous carrier fleet authority -- never
    recomputed here, avoiding double counting per Section 5)."""
    guideway_capex = guideway_length_m * LIGHT_MRT_GUIDEWAY_CAPEX_PER_M
    endpoint_capex = endpoint_count * LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT
    total = guideway_capex + endpoint_capex + carrier_capex
    return LightMrtCapexResult(
        guideway_length_m=guideway_length_m, guideway_capex=guideway_capex, endpoint_count=endpoint_count,
        endpoint_capex=endpoint_capex, carrier_capex=carrier_capex, total_capex=total,
    )

_CONTAINER_BY_PAYLOAD_CLASS: Mapping[MrtPayloadClass, MrtContainerClass] = {
    "NUCLEAR_RADIOPHARMACEUTICAL": DEFAULT_NUCLEAR_SHIELDED_CONTAINER,
    "PHARMACY_INFUSION": DEFAULT_CLINICAL_CLEAN_CONTAINER,
    "STERILE_CLEAN_SUPPLY": DEFAULT_STERILE_SUPPLY_CONTAINER,
    "CLEAN_LINEN": DEFAULT_LINEN_CONTAINER,
    "SPECIMEN": DEFAULT_SPECIMEN_BLOOD_CONTAINER,
    "BLOOD_PRODUCT": DEFAULT_SPECIMEN_BLOOD_CONTAINER,
}


def resolve_container_for_payload(payload_class: MrtPayloadClass) -> MrtContainerClass:
    if not is_mrt_payload_compatible(payload_class):
        raise ValueError(f"{payload_class} is not MRT-compatible (compatibility={MRT_PAYLOAD_COMPATIBILITY.get(payload_class, 'NOT_CALIBRATED')})")
    return _CONTAINER_BY_PAYLOAD_CLASS[payload_class]


# ---------------------------------------------------------------------------
# Priority classes (sections 21-24)
# ---------------------------------------------------------------------------

MrtPriorityClass = Literal[
    "PRIORITY_1_NUCLEAR_CRITICAL", "PRIORITY_2_CLINICAL_URGENT",
    "PRIORITY_3_SCHEDULED_CLINICAL", "PRIORITY_4_ROUTINE_GENERAL",
]
NUCLEAR_PRIORITY: MrtPriorityClass = "PRIORITY_1_NUCLEAR_CRITICAL"
_PRIORITY_RANK: Mapping[MrtPriorityClass, int] = {
    "PRIORITY_1_NUCLEAR_CRITICAL": 1, "PRIORITY_2_CLINICAL_URGENT": 2,
    "PRIORITY_3_SCHEDULED_CLINICAL": 3, "PRIORITY_4_ROUTINE_GENERAL": 4,
}


def resolve_general_logistics_priority(priority: LogisticsPriority) -> MrtPriorityClass:
    """Section 21 suggested mapping -- urgent/critical clinical general
    logistics outrank scheduled clinical, which outranks routine (linen)."""
    if priority in ("URGENT", "CRITICAL"):
        return "PRIORITY_2_CLINICAL_URGENT"
    if priority == "SCHEDULED":
        return "PRIORITY_3_SCHEDULED_CLINICAL"
    return "PRIORITY_4_ROUTINE_GENERAL"


# ---------------------------------------------------------------------------
# Combined mission-window abstraction (sections 3-4, 16-19) -- ONE timeline
# nuclear and general-logistics missions both project onto.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MrtMissionWindow:
    mission_id: str
    patient_ids: tuple[str, ...]
    stream_or_nuclear: Literal["NUCLEAR", "PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY"]
    priority_class: MrtPriorityClass
    start_minutes: float
    duration_minutes: float
    deadline_minutes: float | None = None


def nuclear_trace_to_window(trace: HybridPatientTrace) -> MrtMissionWindow | None:
    """Section 25: nuclear decay/retention timing remains authoritative --
    this only PROJECTS the already-computed MRT transport window onto the
    shared timeline; it never recomputes activity/retention."""
    if trace.transport_mode != "MRT":
        return None
    duration = max(0.0, trace.transport_arrival_time_minutes - trace.release_time_minutes)
    return MrtMissionWindow(
        mission_id=f"NUCLEAR-{trace.patient_id}-{trace.payload_id}", patient_ids=(trace.patient_id,),
        stream_or_nuclear="NUCLEAR", priority_class=NUCLEAR_PRIORITY,
        start_minutes=trace.release_time_minutes, duration_minutes=duration, deadline_minutes=None,
    )


def general_mission_to_window(mission: TransportMission, *, day_start: datetime, priority: LogisticsPriority) -> MrtMissionWindow:
    start = (mission.departure_datetime - day_start).total_seconds() / 60.0
    duration = (mission.arrival_datetime - mission.departure_datetime).total_seconds() / 60.0
    stream = mission.mission_id.split("-")[1] if mission.mission_id.startswith("MISSION-MRT-") else "PHARMACY_INFUSION"
    return MrtMissionWindow(
        mission_id=mission.mission_id, patient_ids=mission.patient_ids,
        stream_or_nuclear="PHARMACY_INFUSION", priority_class=resolve_general_logistics_priority(priority),
        start_minutes=start, duration_minutes=duration, deadline_minutes=None,
    )


def build_general_mission_window(
    mission: TransportMission, *, stream: LogisticsStream, day_start: datetime, priority: LogisticsPriority,
    required_by_datetime: datetime | None = None,
) -> MrtMissionWindow:
    """Preferred constructor (explicit stream, avoids parsing mission_id)."""
    start = (mission.departure_datetime - day_start).total_seconds() / 60.0
    duration = (mission.arrival_datetime - mission.departure_datetime).total_seconds() / 60.0
    deadline = (required_by_datetime - day_start).total_seconds() / 60.0 if required_by_datetime is not None else None
    return MrtMissionWindow(
        mission_id=mission.mission_id, patient_ids=mission.patient_ids, stream_or_nuclear=stream,
        priority_class=resolve_general_logistics_priority(priority), start_minutes=start, duration_minutes=duration,
        deadline_minutes=deadline,
    )


def compute_peak_concurrency(windows: tuple[MrtMissionWindow, ...]) -> int:
    """Section 16-19: sweep-line peak overlap across the COMBINED (nuclear +
    general) mission timeline -- never two independently-sized fleets summed.

    NOTE (Build 2R correction round, item 40): `w.duration_minutes` is the
    ONE-WAY LOADED-OUTBOUND leg only (`mission.arrival_datetime -
    mission.departure_datetime`, per `build_general_mission_window`/
    `nuclear_trace_to_window`) -- it does NOT include the empty-return/
    repositioning leg a physical carrier must complete before it is next
    available. This function is kept for callers that intentionally want the
    raw outbound-only overlap (e.g. as a disclosed audit figure). Fleet
    SIZING must use `compute_physical_carrier_peak_concurrency` below, which
    is the one that accounts for the full physical occupation cycle."""
    if not windows:
        return 0
    events: list[tuple[float, int]] = []
    for w in windows:
        events.append((w.start_minutes, 1))
        events.append((w.start_minutes + w.duration_minutes, -1))
    events.sort(key=lambda e: (e[0], -e[1]))
    current = peak = 0
    for _t, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


def compute_physical_carrier_peak_concurrency(windows: tuple[MrtMissionWindow, ...], *, return_leg_multiplier: float = 1.0) -> int:
    """Section 40 (Build 2R correction round): the CORRECTED, physically
    honest fleet-sizing concurrency. `compute_peak_concurrency` sweeps only
    the one-way loaded-outbound window (dispatch -> delivery); it silently
    assumes a carrier is instantly available again the moment it delivers,
    which is not physical -- a carrier must travel back (empty) before it
    can be assigned to its next mission.

    Each window is extended to
    `[start_minutes, start_minutes + duration_minutes * (1 + return_leg_multiplier)]`
    before sweeping for peak overlap. `return_leg_multiplier=1.0` is a
    disclosed SYMMETRIC-TRANSIT-TIME assumption (no separate empty-carrier
    speed/route model exists anywhere in this repository) -- it is not a
    measured physical value, but it is the only defensible default absent a
    dedicated empty-return routing authority. This can only ever INCREASE
    (never decrease) the reported concurrency relative to
    `compute_peak_concurrency`, since it strictly extends each occupied
    interval."""
    if not windows:
        return 0
    events: list[tuple[float, int]] = []
    for w in windows:
        occupied_until = w.start_minutes + w.duration_minutes * (1.0 + return_leg_multiplier)
        events.append((w.start_minutes, 1))
        events.append((occupied_until, -1))
    events.sort(key=lambda e: (e[0], -e[1]))
    current = peak = 0
    for _t, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


def compute_shared_carrier_fleet(
    windows: tuple[MrtMissionWindow, ...], *, installed_carriers: int | None = None, operated_carriers: int | None = None,
) -> MrtCarrierFleetResult:
    """Section 16-18/37: reuses `resolve_mrt_carrier_fleet` -- the ONE
    existing carrier-sizing authority -- fed by the combined peak
    concurrency; never a second sizing formula.

    NOTE (Build 2R correction round, item 7): this function is kept for
    direct callers/tests that want a single homogeneous pool sized off an
    arbitrary window set. `compute_shared_mrt_economic_result` no longer
    calls this with a caller-supplied `installed_carriers`/`operated_carriers`
    override -- see `compute_heterogeneous_shared_carrier_fleet` below, which
    is the corrected authority for the real NUCLEAR_SHIELDED_CARRIER /
    GENERAL_LIGHT_CARRIER dual-pool sizing used by the economic result."""
    peak = max(1, compute_peak_concurrency(windows))
    return resolve_mrt_carrier_fleet(distribution_concurrency=peak, installed_carriers=installed_carriers, operated_carriers=operated_carriers)


def resolve_shared_hardware_class(stream_or_nuclear: str) -> "CarrierHardwareClass":
    """Binds THIS module's own `MrtMissionWindow.stream_or_nuclear` vocabulary
    ("NUCLEAR", "PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN",
    "STERILE_CLEAN_SUPPLY") to the ALREADY-ESTABLISHED
    NUCLEAR_SHIELDED_CARRIER / GENERAL_LIGHT_CARRIER hardware-class authority
    in `operational_day_orchestrator.py` (`CARRIER_HARDWARE_REGISTRY`,
    `SERVICE_CLASS_TO_HARDWARE_CLASS`). This is NOT a new hardware-class
    mapping/pricing scheme -- it is the same classification rule (nuclear
    always shielded-only, every general-logistics stream always light-only)
    re-applied to this module's own stream labels, which differ in spelling
    only (e.g. "CLEAN_LINEN" here vs "LAUNDRY_CLEAN_LINEN" there)."""
    return "NUCLEAR_SHIELDED_CARRIER" if stream_or_nuclear == "NUCLEAR" else "GENERAL_LIGHT_CARRIER"


@dataclass(frozen=True)
class HeterogeneousSharedFleetResult:
    """Section 16-18/37 CORRECTED (Build 2R correction round, item 7): the
    shared MRT carrier fleet is genuinely TWO separate hardware-class pools,
    each sized from its OWN peak concurrency -- never a single homogeneous
    fleet, never a hardcoded pass-through of the nuclear-only count.

    Section 40 CORRECTED: sizing uses `nuclear_peak_concurrency`/
    `general_light_peak_concurrency`, which are PHYSICAL CYCLE concurrency
    (loaded-outbound + empty-return, via `compute_physical_carrier_peak_concurrency`)
    -- NOT the raw one-way outbound-only overlap. The raw figures are
    preserved separately as `nuclear_outbound_only_peak_concurrency`/
    `general_light_outbound_only_peak_concurrency` for audit disclosure."""

    nuclear_fleet: MrtCarrierFleetResult
    general_light_fleet: MrtCarrierFleetResult
    nuclear_peak_concurrency: int
    general_light_peak_concurrency: int
    nuclear_outbound_only_peak_concurrency: int
    general_light_outbound_only_peak_concurrency: int
    return_leg_multiplier: float
    nuclear_installed_carriers: int
    general_light_installed_carriers: int
    baseline_nuclear_installed_carriers: int
    fleet_capex_total: float
    baseline_nuclear_only_capex: float
    incremental_carrier_capex: float
    provenance: str


def compute_heterogeneous_shared_carrier_fleet(
    nuclear_windows: tuple[MrtMissionWindow, ...], general_windows: tuple[MrtMissionWindow, ...], *,
    baseline_nuclear_installed_carriers: int,
    carrier_unit_capex_usd_override: float | None = None,
) -> HeterogeneousSharedFleetResult:
    """Section 16-18/37 CORRECTED: replaces the defective call pattern where
    `compute_shared_carrier_fleet(combined_windows, installed_carriers=hybrid_result.mrt_carriers,
    operated_carriers=hybrid_result.mrt_carriers)` explicitly locked the
    shared fleet to the nuclear-only count regardless of the combined peak
    concurrency (a confirmed defect: `resolve_mrt_carrier_fleet` computes the
    combined peak correctly but then discards it whenever installed/operated
    are explicitly supplied, per `MrtCarrierFleetInputs.__post_init__`).

    Reuses the SAME sizing authority (`compute_peak_concurrency` +
    `resolve_mrt_carrier_fleet`) applied ONCE PER HARDWARE CLASS, since
    NUCLEAR_SHIELDED_CARRIER and GENERAL_LIGHT_CARRIER are physically
    distinct, non-interchangeable assets (different unit CapEx, shielding
    required only for nuclear, per `SERVICE_CLASS_TO_HARDWARE_CLASS`).

    The nuclear pool is never sized BELOW `baseline_nuclear_installed_carriers`
    (the count already validated by `evaluate_hybrid_zone_candidate`'s
    workload-driven adaptive search) -- only ever sized UP if the combined
    nuclear timeline's peak concurrency genuinely exceeds it. The
    general-light pool is sized directly from the general-logistics peak
    concurrency (previously ignored entirely).

    Section 40 CORRECTED: both peaks are computed via
    `compute_physical_carrier_peak_concurrency` (loaded-outbound + disclosed
    symmetric empty-return leg), never the raw one-way
    `compute_peak_concurrency` -- a carrier is not physically available again
    the instant it delivers."""
    from operational_day_orchestrator import compute_carrier_fleet_capex  # lazy: avoids circular import (see module header note)

    return_leg_multiplier = 1.0
    nuclear_outbound_only_peak = compute_peak_concurrency(nuclear_windows)
    general_outbound_only_peak = compute_peak_concurrency(general_windows)
    nuclear_peak = compute_physical_carrier_peak_concurrency(nuclear_windows, return_leg_multiplier=return_leg_multiplier)
    general_peak = compute_physical_carrier_peak_concurrency(general_windows, return_leg_multiplier=return_leg_multiplier)

    if nuclear_peak > 0:
        nuclear_operated = max(nuclear_peak, baseline_nuclear_installed_carriers)
        nuclear_fleet = resolve_mrt_carrier_fleet(
            distribution_concurrency=nuclear_peak, installed_carriers=nuclear_operated, operated_carriers=nuclear_operated,
        )
    else:
        nuclear_fleet = MrtCarrierFleetResult(
            installed_carriers=baseline_nuclear_installed_carriers, operated_carriers=baseline_nuclear_installed_carriers,
            spare_carriers=0, distribution_concurrency=0, carrier_constrained_throughput=False, bottleneck_resource=None,
            proxy_relationship="No nuclear MRT missions in the combined timeline; nuclear pool held at the caller-supplied baseline.",
            carrier_capex_modeled=True, carrier_opex_modeled=True, carrier_energy_modeled=True,
            carrier_capex_status="PROJECT_PLANNING_ASSUMPTION", carrier_opex_status="PROJECT_PLANNING_ASSUMPTION",
            carrier_energy_status="PROJECT_PLANNING_ASSUMPTION",
        )

    if general_peak > 0:
        general_light_fleet = resolve_mrt_carrier_fleet(
            distribution_concurrency=general_peak, installed_carriers=general_peak, operated_carriers=general_peak,
        )
    else:
        general_light_fleet = MrtCarrierFleetResult(
            installed_carriers=0, operated_carriers=0, spare_carriers=0, distribution_concurrency=0,
            carrier_constrained_throughput=False, bottleneck_resource=None,
            proxy_relationship="No general-logistics MRT missions in the combined timeline.",
            carrier_capex_modeled=True, carrier_opex_modeled=True, carrier_energy_modeled=True,
            carrier_capex_status="PROJECT_PLANNING_ASSUMPTION", carrier_opex_status="PROJECT_PLANNING_ASSUMPTION",
            carrier_energy_status="PROJECT_PLANNING_ASSUMPTION",
        )

    # RUNTIME MIGRATION: price the incremental fleet at the canonical compact
    # carrier CapEx ($2,000) when the current runtime supplies an override;
    # otherwise the preserved heavy $10,000/$1,000 pricing is used. The SAME
    # unit price is applied to both fleet_capex_total and the baseline so the
    # incremental delta stays internally consistent.
    fleet_capex_total = compute_carrier_fleet_capex(
        nuclear_count=nuclear_fleet.installed_carriers, general_light_count=general_light_fleet.installed_carriers,
        nuclear_unit_capex_usd=carrier_unit_capex_usd_override,
        general_light_unit_capex_usd=carrier_unit_capex_usd_override,
    )
    baseline_nuclear_only_capex = compute_carrier_fleet_capex(
        nuclear_count=baseline_nuclear_installed_carriers, general_light_count=0,
        nuclear_unit_capex_usd=carrier_unit_capex_usd_override,
        general_light_unit_capex_usd=carrier_unit_capex_usd_override,
    )

    return HeterogeneousSharedFleetResult(
        nuclear_fleet=nuclear_fleet, general_light_fleet=general_light_fleet,
        nuclear_peak_concurrency=nuclear_peak, general_light_peak_concurrency=general_peak,
        nuclear_outbound_only_peak_concurrency=nuclear_outbound_only_peak,
        general_light_outbound_only_peak_concurrency=general_outbound_only_peak,
        return_leg_multiplier=return_leg_multiplier,
        nuclear_installed_carriers=nuclear_fleet.installed_carriers, general_light_installed_carriers=general_light_fleet.installed_carriers,
        baseline_nuclear_installed_carriers=baseline_nuclear_installed_carriers, fleet_capex_total=fleet_capex_total,
        baseline_nuclear_only_capex=baseline_nuclear_only_capex,
        incremental_carrier_capex=fleet_capex_total - baseline_nuclear_only_capex,
        provenance=(
            "CARRIER_HARDWARE_REGISTRY/compute_carrier_fleet_capex (operational_day_orchestrator.py) for pricing; "
            "resolve_mrt_carrier_fleet/compute_physical_carrier_peak_concurrency (this module, return_leg_multiplier=1.0 "
            "disclosed symmetric-transit assumption) for sizing, applied once per hardware class."
        ),
    )


# ---------------------------------------------------------------------------
# Network segment / capacity / conflict authority (sections 13, 19-20)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MrtNetworkSegment:
    """Section 13: persistent segment identity. This build models the shared
    trunk as ONE constrained segment (the physical guideway already
    established by `hybrid_optimization`/`infrastructure_capex`) -- never a
    duplicate per-stream segment."""

    segment_id: str
    start_node: str
    end_node: str
    length_m: float
    orientation: Literal["HORIZONTAL", "VERTICAL", "MIXED"]
    minimum_headway_minutes: float
    asset_status: AssetStatus = "EXISTING"
    operational_state: Literal["AVAILABLE", "UNAVAILABLE", "MAINTENANCE"] = "AVAILABLE"
    provenance: str = "CONTROLLED_ENGINEERING_ASSUMPTION"


DEFAULT_SHARED_TRUNK_SEGMENT = MrtNetworkSegment(
    segment_id="MRT-TRUNK-001", start_node="BLDG-A-BASE", end_node="BLDG-A-B-JUNCTION", length_m=0.0,
    orientation="MIXED", minimum_headway_minutes=1.0,
)


@dataclass(frozen=True)
class ScheduledMrtMission:
    mission_id: str
    priority_class: MrtPriorityClass
    original_start_minutes: float
    scheduled_start_minutes: float
    scheduled_end_minutes: float
    wait_minutes: float
    deadline_minutes: float | None
    deadline_status: Literal["ON_TIME", "LATE", "UNMET", "NO_DEADLINE"]


def schedule_missions_on_shared_segment(
    windows: tuple[MrtMissionWindow, ...], *, segment: MrtNetworkSegment = DEFAULT_SHARED_TRUNK_SEGMENT,
) -> tuple[ScheduledMrtMission, ...]:
    """Section 20-24/61: non-preemptive, priority-ordered single-resource
    scheduling -- once a mission starts it runs to completion (no
    interruption is modeled); a higher-priority mission queued behind a
    lower-priority one that has ALREADY STARTED must still wait (this is the
    real, disclosed non-preemptive behavior, never a fabricated preemption).
    Missions are dispatched in (priority, original arrival) order onto the
    ONE shared segment honoring `minimum_headway_minutes`."""
    ordered = sorted(windows, key=lambda w: (_PRIORITY_RANK[w.priority_class], w.start_minutes))
    scheduled: list[ScheduledMrtMission] = []
    segment_free_at = float("-inf")
    for w in ordered:
        start = max(w.start_minutes, segment_free_at)
        end = start + w.duration_minutes
        segment_free_at = end + segment.minimum_headway_minutes
        wait = start - w.start_minutes
        if w.deadline_minutes is None:
            status: Literal["ON_TIME", "LATE", "UNMET", "NO_DEADLINE"] = "NO_DEADLINE"
        elif end <= w.deadline_minutes:
            status = "ON_TIME"
        elif start <= w.deadline_minutes:
            status = "LATE"
        else:
            status = "UNMET"
        scheduled.append(ScheduledMrtMission(
            mission_id=w.mission_id, priority_class=w.priority_class, original_start_minutes=w.start_minutes,
            scheduled_start_minutes=start, scheduled_end_minutes=end, wait_minutes=wait,
            deadline_minutes=w.deadline_minutes, deadline_status=status,
        ))
    return tuple(scheduled)


def detect_segment_conflicts(windows: tuple[MrtMissionWindow, ...]) -> tuple[tuple[str, str], ...]:
    """Section 19-20: pairs of missions whose ORIGINAL (unscheduled) windows
    overlap on the single shared segment -- the conflicts
    `schedule_missions_on_shared_segment` resolves via priority ordering."""
    conflicts = []
    ordered = sorted(windows, key=lambda w: w.start_minutes)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            if b.start_minutes >= a.start_minutes + a.duration_minutes:
                break
            conflicts.append((a.mission_id, b.mission_id))
    return tuple(conflicts)


# ---------------------------------------------------------------------------
# Container inventory sizing (sections 34-36)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContainerRequirement:
    container_class_id: str
    total_missions: int
    peak_concurrent_use: int
    required_count: int


def compute_container_requirement(
    missions: tuple[TransportMission, ...], *, container: MrtContainerClass, day_start: datetime,
) -> ContainerRequirement:
    """Section 35: required_count is PEAK-CONCURRENCY-derived (occupancy
    window = load + transit + unload + exchange/cleaning) -- never simply
    `container_count = mission_count`."""
    if not missions:
        return ContainerRequirement(container_class_id=container.container_class_id, total_missions=0, peak_concurrent_use=0, required_count=0)
    occupancy_minutes = container.load_minutes + container.unload_minutes + container.exchange_minutes
    windows = tuple(
        MrtMissionWindow(
            mission_id=m.mission_id, patient_ids=m.patient_ids, stream_or_nuclear="PHARMACY_INFUSION",
            priority_class="PRIORITY_4_ROUTINE_GENERAL",
            start_minutes=(m.departure_datetime - day_start).total_seconds() / 60.0,
            duration_minutes=max(m.duration_minutes or 0.0, occupancy_minutes),
        )
        for m in missions
    )
    peak = compute_peak_concurrency(windows)
    return ContainerRequirement(
        container_class_id=container.container_class_id, total_missions=len(missions),
        peak_concurrent_use=peak, required_count=max(1, peak),
    )


def compute_container_requirements_by_class(
    missions_by_stream: Mapping[LogisticsStream, tuple[TransportMission, ...]], *,
    containers_by_stream: Mapping[LogisticsStream, MrtContainerClass], day_start: datetime,
) -> tuple[ContainerRequirement, ...]:
    """Section 9/34: streams sharing the SAME container class (e.g.
    PHARMACY_INFUSION and STERILE_CLEAN_SUPPLY both use
    CLINICAL_CLEAN_CONTAINER) must be pooled into ONE combined inventory
    requirement -- never sized/charged as separate per-stream silos for the
    same physical container class (the container-equivalent of the shared
    carrier fleet principle, sections 16-18)."""
    missions_by_class: dict[str, list[TransportMission]] = {}
    container_by_class: dict[str, MrtContainerClass] = {}
    for stream, missions in missions_by_stream.items():
        container = containers_by_stream[stream]
        missions_by_class.setdefault(container.container_class_id, []).extend(missions)
        container_by_class[container.container_class_id] = container
    return tuple(
        compute_container_requirement(tuple(missions), container=container_by_class[class_id], day_start=day_start)
        for class_id, missions in missions_by_class.items()
    )


def container_inventory_new_study_capex(
    container: MrtContainerClass, *, required_count: int, study_scope: StudyScope,
) -> float:
    """Section 16-18/36/44-45: NUCLEAR container economics are already
    counted elsewhere (never a second cost line); non-nuclear containers
    contribute new-study CapEx only for PROPOSED units under CAPITAL_PLANNING."""
    if container.unit_capex in ("ALREADY_INCLUDED_IN_EXISTING_MRT_CARRIER_AUTHORITY", "NOT_CALIBRATED"):
        return 0.0
    if study_scope == "OPERATIONAL_ONLY" or container.asset_status != "PROPOSED":
        return 0.0
    return required_count * float(container.unit_capex)


# ---------------------------------------------------------------------------
# General-logistics MRT mission conversion (sections 3-4, 27-32) -- reuses
# `convert_load_to_mrt_missions` EXACTLY (protected default signature).
# ---------------------------------------------------------------------------


def convert_load_to_shared_mrt_missions(*, load: TransportLoad, subtype: SpecimenBloodSubtype | None = None) -> tuple[TransportMission, ...]:
    """Section 3-4/31-33: resolves the load's payload class/container, then
    delegates mission conversion to the UNCHANGED, protected
    `general_oncology_logistics.convert_load_to_mrt_missions` -- never a
    reimplementation. Raises for an incompatible stream (never silently
    fabricates compatibility)."""
    payload_class = stream_to_payload_class(load.stream, subtype=subtype)
    container = resolve_container_for_payload(payload_class)
    return convert_load_to_mrt_missions(load=load, container_capacity_kg=container.capacity)


# ---------------------------------------------------------------------------
# Shared CapEx/OPEX ledger composition (sections 14-15, 36, 42-43) -- reuses
# `merge_shared_and_mode_specific_ledgers`/`recompute_ledger_totals`
# (infrastructure_opex.py); no parallel ledger authority for OPEX. CapEx has
# no existing merge helper, so ONE narrowly-scoped merge (identical
# non-duplication guard) is added here.
# ---------------------------------------------------------------------------


def build_container_capex_ledger(
    requirements: tuple[ContainerRequirement, ...], containers: Mapping[str, MrtContainerClass], *, study_scope: StudyScope,
) -> tuple[CapexLedgerItem, ...]:
    items = []
    for req in requirements:
        container = containers[req.container_class_id]
        capex = container_inventory_new_study_capex(container, required_count=req.required_count, study_scope=study_scope)
        if container.unit_capex in ("ALREADY_INCLUDED_IN_EXISTING_MRT_CARRIER_AUTHORITY", "NOT_CALIBRATED"):
            continue  # section 36: never a fabricated cost line
        items.append(CapexLedgerItem(
            component=f"MRT container inventory - {req.container_class_id}", category="MRT_CONTAINER",
            quantity=req.required_count, unit="containers", unit_cost=float(container.unit_capex), subtotal=capex,
            cost_basis=container.provenance,
        ))
    return tuple(items)


def merge_shared_and_container_capex_ledgers(
    *, shared_ledger: tuple[CapexLedgerItem, ...], container_ledger: tuple[CapexLedgerItem, ...],
) -> tuple[CapexLedgerItem, ...]:
    """Section 14-15/43: identical non-duplication guard to
    `infrastructure_opex.merge_shared_and_mode_specific_ledgers` -- raises if
    a container component name collides with an existing shared-ledger
    component (would indicate double counting)."""
    shared_components = {row.component for row in shared_ledger}
    overlap = shared_components & {row.component for row in container_ledger}
    if overlap:
        raise ValueError(f"Component(s) {sorted(overlap)} present in both ledgers -- would double-count")
    return tuple(shared_ledger) + tuple(container_ledger)


def build_container_opex_ledger(
    requirements: tuple[ContainerRequirement, ...], containers: Mapping[str, MrtContainerClass], *,
    cleaning_cost_per_unit_year: float = 150.0,
) -> tuple[OpexLedgerItem, ...]:
    """Section 39: container maintenance/cleaning charged separately from
    carrier maintenance and from shared guideway/network maintenance."""
    items = []
    for req in requirements:
        container = containers[req.container_class_id]
        if container.unit_capex == "ALREADY_INCLUDED_IN_EXISTING_MRT_CARRIER_AUTHORITY":
            continue  # nuclear container cleaning/handling already inside existing nuclear labor/OPEX
        annual_cost = req.required_count * cleaning_cost_per_unit_year
        items.append(OpexLedgerItem(
            component=f"MRT container maintenance/cleaning - {req.container_class_id}", category="MRT",
            cost_type="FIXED", quantity=req.required_count, unit="containers", unit_cost=cleaning_cost_per_unit_year,
            annual_cost=annual_cost, cost_basis="CONTROLLED_ENGINEERING_ASSUMPTION (container cleaning/turnaround)",
        ))
    return tuple(items)


# ---------------------------------------------------------------------------
# Patient traceability (sections 54-56)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiStreamPatientTraceabilityRecord:
    patient_id: str
    nuclear_mission_ids: tuple[str, ...]
    general_mission_ids_by_stream: Mapping[LogisticsStream, tuple[str, ...]]


def build_patient_traceability(
    patient_id: str, *, nuclear_traces: tuple[HybridPatientTrace, ...],
    general_missions_by_stream: Mapping[LogisticsStream, tuple[TransportMission, ...]],
) -> MultiStreamPatientTraceabilityRecord:
    nuclear_ids = tuple(f"NUCLEAR-{t.patient_id}-{t.payload_id}" for t in nuclear_traces if t.patient_id == patient_id and t.transport_mode == "MRT")
    general_by_stream = {
        stream: tuple(m.mission_id for m in missions if patient_id in m.patient_ids)
        for stream, missions in general_missions_by_stream.items()
    }
    return MultiStreamPatientTraceabilityRecord(patient_id=patient_id, nuclear_mission_ids=nuclear_ids, general_mission_ids_by_stream=general_by_stream)


# ---------------------------------------------------------------------------
# Deadline compliance (section 26)
# ---------------------------------------------------------------------------

DeadlineStatus = Literal["ON_TIME", "LATE", "UNMET", "NO_DEADLINE"]


def general_deadline_status(*, arrival_datetime: datetime, required_by_datetime: datetime | None) -> DeadlineStatus:
    if required_by_datetime is None:
        return "NO_DEADLINE"
    return "ON_TIME" if arrival_datetime <= required_by_datetime else "LATE"


# ---------------------------------------------------------------------------
# Combined economic result (sections 69-71) -- nuclear side via the
# UNCHANGED `evaluate_hybrid_zone_candidate`; general side via this module.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SharedMrtEconomicResult:
    architecture: Literal["HYBRID_MRT", "MRT_DOMINANT"]
    nuclear_capex: float
    nuclear_annual_opex: float
    container_new_study_capex: float
    container_annual_opex: float
    combined_new_study_capex: float
    combined_annual_opex: float
    heterogeneous_carrier_fleet: HeterogeneousSharedFleetResult
    combined_capex_ledger: tuple[CapexLedgerItem, ...]
    combined_opex_ledger: tuple[OpexLedgerItem, ...]
    cost_per_inpatient_day: float | None
    cost_per_episode: float | None
    cyclotron_linked_vestibule_count: int = 0
    cyclotron_linked_vestibule_capex: float = 0.0
    """Build 2R correction round (item 54): $30,000/vestibule
    (canonical_spatial_authority.MRT_VESTIBULE_CAPEX_USD), one vestibule per
    cyclotron interface requiring MRT transfer -- NEVER tied to radiopharmacy
    count, floor count, room count, or endpoint count. Defaults to 0/0.0 for
    callers that do not pass cyclotron_count (backward-compatible)."""


def compute_shared_mrt_economic_result(
    *, architecture: Literal["HYBRID_MRT", "MRT_DOMINANT"], hybrid_result: HybridEvaluationResult,
    general_windows: tuple[MrtMissionWindow, ...], container_requirements: tuple[ContainerRequirement, ...],
    containers: Mapping[str, MrtContainerClass], study_scope: StudyScope,
    inpatient_count: int | None = None, average_los_days: float | None = None, cyclotron_count: int = 0,
    mrt_runtime_config: "MrtRuntimeConfig | None" = None,
) -> SharedMrtEconomicResult:
    """Section 69-71: combines the PROTECTED nuclear Hybrid/MRT-Dominant
    result with the general-logistics MRT layer -- nuclear CapEx/OPEX values
    are read from `hybrid_result` UNCHANGED; only the shared carrier fleet
    sizing and the (new) container ledger are added on top.

    `cyclotron_count` (Build 2R correction round, item 54): adds the
    cyclotron-linked MRT vestibule CapEx ($30,000/vestibule, one per
    cyclotron interface) ON TOP of `hybrid_result.total_capex` -- this
    authority chain (`evaluate_hybrid_zone_candidate`) does not price
    vestibules at all, so this is a genuine, additive, disclosed correction,
    never a double-count of anything already in `hybrid_result.total_capex`.
    Defaults to 0 (no vestibule charge) for existing callers that do not
    pass it, preserving prior behavior exactly."""
    from canonical_spatial_authority import MRT_VESTIBULE_CAPEX_USD

    # RUNTIME MIGRATION: when the current runtime supplies a config, price the
    # incremental carrier fleet at the canonical compact carrier CapEx; else
    # (None) preserve the heavy $10,000/$1,000 pricing exactly.
    _carrier_override = None if mrt_runtime_config is None else mrt_runtime_config.carrier_capex_per_installed_unit_usd
    nuclear_windows = tuple(w for w in (nuclear_trace_to_window(t) for t in hybrid_result.patient_traces) if w is not None)
    heterogeneous_fleet = compute_heterogeneous_shared_carrier_fleet(
        nuclear_windows, general_windows, baseline_nuclear_installed_carriers=hybrid_result.mrt_carriers,
        carrier_unit_capex_usd_override=_carrier_override,
    )
    vestibule_capex = cyclotron_count * MRT_VESTIBULE_CAPEX_USD

    container_capex_ledger = build_container_capex_ledger(container_requirements, containers, study_scope=study_scope)
    container_opex_ledger = build_container_opex_ledger(container_requirements, containers)
    container_capex_total = sum(item.subtotal for item in container_capex_ledger)
    container_opex_total = sum(item.annual_cost for item in container_opex_ledger)

    container_components = frozenset(item.component for item in container_opex_ledger)
    combined_opex_ledger = merge_shared_and_mode_specific_ledgers(
        shared_and_conventional_ledger=hybrid_result.opex_result.ledger, mrt_specific_ledger=container_opex_ledger,
        mrt_specific_components=container_components,
    )
    combined_totals = recompute_ledger_totals(combined_opex_ledger)

    cost_per_inpatient_day = None
    cost_per_episode = None
    if inpatient_count and inpatient_count > 0:
        cost_per_inpatient_day = combined_totals["total_annual_opex"] / (inpatient_count * 365.0)
        if average_los_days:
            cost_per_episode = cost_per_inpatient_day * average_los_days

    return SharedMrtEconomicResult(
        architecture=architecture, nuclear_capex=hybrid_result.total_capex, nuclear_annual_opex=hybrid_result.total_annual_opex,
        container_new_study_capex=container_capex_total, container_annual_opex=container_opex_total,
        # CORRECTED (Build 2R correction round, item 7): adds the INCREMENTAL
        # carrier CapEx delta between the properly-sized heterogeneous fleet
        # (nuclear pool sized up if genuinely warranted + general-light pool
        # sized from its own peak concurrency, priced at $10,000/$1,000
        # respectively) and the baseline nuclear-only carrier CapEx already
        # embedded inside hybrid_result.total_capex -- never double-counts the
        # baseline, never silently drops the general-light fleet's CapEx.
        combined_new_study_capex=hybrid_result.total_capex + container_capex_total + heterogeneous_fleet.incremental_carrier_capex + vestibule_capex,
        combined_annual_opex=combined_totals["total_annual_opex"], heterogeneous_carrier_fleet=heterogeneous_fleet,
        combined_capex_ledger=(),  # no existing CapEx ledger surfaced by HybridEvaluationResult (only total_capex); see report disclosure
        combined_opex_ledger=combined_opex_ledger,
        cost_per_inpatient_day=cost_per_inpatient_day, cost_per_episode=cost_per_episode,
        cyclotron_linked_vestibule_count=cyclotron_count, cyclotron_linked_vestibule_capex=vestibule_capex,
    )


# ---------------------------------------------------------------------------
# Live-State foundation (sections 78-79) -- reuse existing event framework,
# never a parallel one.
# ---------------------------------------------------------------------------


def mrt_segment_event_reuses_existing_framework() -> bool:
    """Section 78-79: `live_operational_state.py` already defines
    `MRT_CARRIER_STATE_CHANGE` in its `OperationalEventType` Literal and an
    `mrt_carrier_state` dict on `OperationalStateStore` -- this module
    intentionally does NOT define `MRT_SEGMENT_UNAVAILABLE`/
    `MRT_ENDPOINT_UNAVAILABLE` as a new parallel framework; segment/endpoint
    unavailability is representable via the SAME `ObjectStateRecord`/
    `OperationalEvent` primitives keyed by `segment_id`/endpoint object_id,
    reusing `mrt_carrier_state`-style dicts rather than inventing new ones."""
    from live_operational_state import OperationalEventType
    import typing
    return "MRT_CARRIER_STATE_CHANGE" in typing.get_args(OperationalEventType)

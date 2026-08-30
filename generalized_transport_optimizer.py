"""KIRO Super-Build 2 -- Generalized Multi-Transport Optimizer + Transport
ON/OFF Runtime Integration.

This module makes the Super-Build 1 parity authorities OPERATIONAL. It is the
generalized candidate generator + selector the SB1 seam
(`transport_mode_scope_authority.FUTURE_OPTIMIZER_CONTRACT`) documented. It
does NOT introduce a second physics/economics engine: it COMPOSES

  * transport_settings_authority         -- family/subtype ON/OFF (Sec 6-8)
  * transport_mode_scope_authority       -- scope + fallback conservation
  * transport_mode_eligibility_authority -- payload eligibility (Sec 9-11)
  * floor_agv_amr_authority              -- free-roaming AGV economics/physics
  * conventional_transport_authority     -- Manual / PTS / RGHT(RTHS)
  * dedicated_rp_pts_authority           -- nuclear-qualified PTS
  * mrt_canonical_configuration          -- MRT (READ-ONLY reference, Sec 15/59)

GOVERNING CHAIN (Sec 9): PAYLOAD -> SCOPE -> ELIGIBILITY -> QUALIFICATION ->
FEASIBLE MODE SET -> CANDIDATE GENERATION -> CAPACITY -> ECONOMICS ->
OPTIMIZATION. Never ECONOMICS -> FORCE ELIGIBILITY.

USER EXCLUSION IS ABSOLUTE (Sec 8): a disabled family/subtype never enters
candidate generation, receives missions, appears in a Hybrid, is inserted as
fallback, or appears in the selected economics. Scope dominates economics.

HYBRID (Sec 21) is NOT hardware: it is >=2 enabled technologies assigned to
different missions under one architecture. Multiple distinct Hybrids may be
generated. NO FORCED WINNER (Sec 52): selection emerges from allowed
technologies + eligibility + capacity + economics + the existing objective.

This build does NOT stage/commit/push, does NOT change MRT canonical physics,
Part 3E, or equal_budget.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

import transport_mode_eligibility_authority as elig
import transport_mode_scope_authority as scope_auth
import floor_agv_amr_authority as agv
import conventional_transport_authority as cta
import dedicated_rp_pts_authority as rp
import mrt_canonical_configuration as mrt

from transport_settings_authority import (
    TransportSettings, TransportFamily, TransportSubtype, ResolvedMode,
    CANONICAL_TRANSPORT_FAMILIES, FAMILY_SUBTYPES, SUBTYPE_PARENT, SUBTYPE_RESOLVED_MODE,
    default_transport_settings,
)

# ===========================================================================
# 1. Mission model (Sec 10/18). One payload/mission carries what/where/how-much.
# ===========================================================================

@dataclass(frozen=True)
class OptimizerMission:
    """Sec 10/18: a transport mission with the inputs eligibility needs."""
    mission_id: str
    stream: str
    payload_mass_kg: float | None = None
    payload_volume_l: float | None = None
    specimen_sensitivity: "elig.SpecimenSensitivity | None" = None
    patient_ids: tuple[str, ...] = ()


# ===========================================================================
# 2. Settings -> in-scope resolved modes (Sec 8, reconciliation).
#    A resolved-mode (eligibility vocabulary) is available iff its owning
#    family/subtype is EFFECTIVELY enabled in the settings.
# ===========================================================================

# resolved-mode -> the settings predicate that gates it
def _available_resolved_modes(settings: TransportSettings) -> frozenset[ResolvedMode]:
    """Sec 7-8: the set of resolved transport modes the settings permit,
    honoring parent->child inheritance. RTHS is represented by the resolved
    sentinel 'RTHS'."""
    available: set[ResolvedMode] = set()
    # MANUAL family (no subtype): the family IS the mode.
    if settings.family_enabled("MANUAL"):
        available.add("MANUAL")
    # subtype-backed families resolve through effectively-enabled subtypes.
    for subtype in SUBTYPE_PARENT:
        if settings.subtype_effectively_enabled(subtype):
            available.add(SUBTYPE_RESOLVED_MODE[subtype])
    return frozenset(available)


# resolved-mode -> canonical family (for reporting ACTUALLY_USED families)
_RESOLVED_TO_FAMILY: Mapping[ResolvedMode, TransportFamily] = {
    "MANUAL": "MANUAL",
    "PTS": "PTS",
    "DEDICATED_RP_PTS": "PTS",
    "AGV_AMR_LIGHT_CLINICAL": "AGV_AMR",
    "AGV_AMR_HEAVY_LOGISTICS": "AGV_AMR",
    "RTHS": "RTHS",
    "MRT": "MRT",
}


# ===========================================================================
# 3. Eligibility of a resolved-mode for a mission (Sec 9-11). RTHS is resolved
#    through its legacy authority (conventional_transport_authority RGHT
#    stream compatibility); every other resolved mode uses the SB1 eligibility
#    authority so qualification-required is never silently upgraded (Sec 11).
# ===========================================================================

# RTHS (rail-guided) stream compatibility. RGHT is the legacy AGV_AMR class in
# conventional_transport_authority; its compatible streams define RTHS
# eligibility. Radiopharmaceutical is QUALIFICATION_REQUIRED (never auto).
def _rths_eligibility(mission: OptimizerMission, *, rths_radiopharm_qualified: bool) -> str:
    stream = mission.stream
    if stream == "RADIOPHARMACEUTICAL_NUCLEAR":
        return "ELIGIBLE" if rths_radiopharm_qualified else "QUALIFICATION_REQUIRED"
    # RGHT compatible streams (rail-guided hospital carrier).
    if cta.is_technology_compatible("AGV_AMR", stream):
        # rail-guided cannot exceed its carrier payload envelope; use the RGHT
        # (DEFAULT_AGV_MODEL) payload capacity as the mass gate.
        if mission.payload_mass_kg is not None and mission.payload_mass_kg > cta.DEFAULT_AGV_MODEL.payload_capacity_kg:
            return "INELIGIBLE"
        return "ELIGIBLE"
    return "INELIGIBLE"


def resolved_mode_eligibility(
    mission: OptimizerMission, resolved: ResolvedMode, settings: TransportSettings,
) -> str:
    """Sec 9-11: eligibility of one resolved mode for one mission. Uses the SB1
    eligibility authority (never re-implemented); RTHS via its legacy owner."""
    if resolved == "RTHS":
        return _rths_eligibility(mission, rths_radiopharm_qualified=settings.radiopharm_qualification_supplied)
    # Map resolved -> eligibility TransportModeFamily.
    fam: elig.TransportModeFamily = resolved  # type: ignore[assignment]
    r = elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(
        mode=fam, stream=mission.stream, payload_mass_kg=mission.payload_mass_kg,
        payload_volume_l=mission.payload_volume_l, specimen_sensitivity=mission.specimen_sensitivity,
        radiopharm_qualified=settings.radiopharm_qualification_supplied,
        pts_sensitive_specimen_validated=settings.pts_sensitive_specimen_validated,
        manual_shielding_configured=settings.radiopharm_qualification_supplied,
    ))
    return r.eligibility


def allowed_modes_for_mission(
    mission: OptimizerMission, settings: TransportSettings,
) -> tuple[ResolvedMode, ...]:
    """Sec 8-11: resolved modes that are BOTH available (in-scope per settings)
    AND strictly ELIGIBLE for this mission. Ordering is canonical/deterministic."""
    available = _available_resolved_modes(settings)
    order: tuple[ResolvedMode, ...] = (
        "MANUAL", "PTS", "DEDICATED_RP_PTS", "RTHS",
        "AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS", "MRT",
    )
    allowed: list[ResolvedMode] = []
    for m in order:
        if m in available and resolved_mode_eligibility(mission, m, settings) == "ELIGIBLE":
            allowed.append(m)
    return tuple(allowed)


# ===========================================================================
# 4. Mission assignment for a candidate (Sec 18/24). A candidate is a set of
#    resolved modes it is permitted to use. Assignment respects scope +
#    eligibility + a deterministic preference; unmet missions are conserved.
# ===========================================================================

@dataclass(frozen=True)
class MissionAssignment:
    mission_id: str
    stream: str
    assigned_mode: ResolvedMode | None
    status: Literal["ASSIGNED", "UNMET"]
    reason: str


@dataclass(frozen=True)
class AssignmentResult:
    input_missions: int
    assigned_missions: int
    unmet_missions: int
    assignments: tuple[MissionAssignment, ...]
    conserved: bool
    missions_by_mode: Mapping[ResolvedMode, int]
    streams_by_mode: Mapping[ResolvedMode, tuple[str, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "conserved", self.input_missions == self.assigned_missions + self.unmet_missions)


def _assign_missions(
    *, missions: Sequence[OptimizerMission], candidate_modes: frozenset[ResolvedMode],
    settings: TransportSettings, preference: Sequence[ResolvedMode],
) -> AssignmentResult:
    """Sec 24: assign each mission to the FIRST allowed mode in `preference`
    that is (a) in the candidate's mode set, (b) available per settings, and
    (c) strictly eligible. No silent fallback to an out-of-candidate/off mode
    (Sec 17). INPUT == ASSIGNED + UNMET (Sec 18)."""
    assignments: list[MissionAssignment] = []
    assigned = unmet = 0
    by_mode: dict[ResolvedMode, int] = {}
    streams_by_mode: dict[ResolvedMode, list[str]] = {}
    for mission in missions:
        allowed = set(allowed_modes_for_mission(mission, settings)) & candidate_modes
        chosen: ResolvedMode | None = next((m for m in preference if m in allowed), None)
        if chosen is not None:
            assigned += 1
            by_mode[chosen] = by_mode.get(chosen, 0) + 1
            streams_by_mode.setdefault(chosen, []).append(mission.stream)
            assignments.append(MissionAssignment(mission.mission_id, mission.stream, chosen, "ASSIGNED", f"assigned to {chosen}"))
        else:
            unmet += 1
            assignments.append(MissionAssignment(
                mission.mission_id, mission.stream, None, "UNMET",
                "no allowed mode within candidate scope (excluded/ineligible modes never inserted, Sec 8/17)",
            ))
    return AssignmentResult(
        input_missions=len(missions), assigned_missions=assigned, unmet_missions=unmet,
        assignments=tuple(assignments), conserved=True,
        missions_by_mode={m: by_mode[m] for m in sorted(by_mode)},
        streams_by_mode={m: tuple(sorted(set(streams_by_mode[m]))) for m in sorted(streams_by_mode)},
    )


# ===========================================================================
# 5. Per-mode economics (Sec 12-13, 28-29). Each resolved mode's CapEx/OPEX is
#    computed by its OWNING authority. Shared vs mode-specific separation
#    (Sec 12-13/26) avoids double-buying. MRT is READ-ONLY (Sec 15/59): its
#    canonical unit costs are read, never recomputed or altered here.
# ===========================================================================

# Controlled shared-infrastructure allowances (Sec 12-13/27). These are the
# ONLY cross-subtype shared components, and they are counted ONCE per family.
PTS_SHARED_BACKBONE_CAPEX_USD = 120_000.0   # tube backbone/blowers/controls shared by both PTS subtypes
AGV_SHARED_FLEET_MANAGER_CAPEX_USD = 120_000.0  # fleet-management HW/SW shared by light+heavy (matches floor_agv once-charge)
AGV_SHARED_FLEET_SOFTWARE_OPEX_USD = 30_000.0   # fleet software/support shared by light+heavy


@dataclass(frozen=True)
class ModeEconomics:
    mode: ResolvedMode
    missions_assigned: int
    mode_specific_capex_usd: float
    mode_specific_annual_opex_usd: float
    unknown_capex_components: tuple[str, ...]
    unknown_opex_components: tuple[str, ...]
    capacity_basis: str
    provenance: str


def _manual_economics(missions: int) -> ModeEconomics:
    # Manual: proposed general cart CapEx (existing carts = $0); OPEX = porter
    # labor is workload-derived elsewhere; here we expose the cart CapEx and a
    # per-mission-derived residual. Labor OPEX is computed via porter authority
    # only when route timing is supplied; absent that we mark it unknown.
    capex = cta.DEFAULT_GENERAL_CART.purchase_capex if missions else 0.0
    return ModeEconomics(
        "MANUAL", missions, capex, 0.0,
        (), ("Porter labor OPEX (workload/route-timing-derived; NOT_CALIBRATED without route geometry)",),
        "porter peak-concurrency FTE", "conventional_transport_authority.PorterOperatingPolicy",
    )


def _pts_economics(missions: int) -> ModeEconomics:
    # Ordinary PTS mode-specific increment (shared backbone counted separately).
    proposed = cta.DEFAULT_PTS_NETWORK
    # station-only incremental CapEx (backbone shared): stations * unit cost
    incremental = proposed.station_count * proposed.station_capex_per_unit
    return ModeEconomics(
        "PTS", missions, float(incremental), float(proposed.annual_maintenance_opex + proposed.annual_energy_opex),
        (), ("Diverter/controls service (NOT_CALIBRATED)", "Building penetrations (NOT_CALIBRATED)"),
        "carrier/station peak-concurrency", "conventional_transport_authority.DEFAULT_PTS_NETWORK",
    )


def _rp_pts_economics(missions: int) -> ModeEconomics:
    cap = rp.compute_rp_pts_capex()
    op = rp.compute_rp_pts_opex(human_labor_annual_opex=0.0, human_labor_fte=0.0)
    return ModeEconomics(
        "DEDICATED_RP_PTS", missions, cap.total_capex, op.total_calibrated_annual_opex,
        (("Shielding/certification delta (NOT_CALIBRATED)",) if cap.shielding_certification_delta_capex is None else ()),
        ("Human handling labor (workload-derived; supplied separately)",),
        "dedicated nuclear carrier/station", "dedicated_rp_pts_authority",
    )


def _agv_economics(mode: ResolvedMode, missions: int, *, fleet_size: int, stations: int) -> ModeEconomics:
    profile = agv.DEFAULT_LIGHT_CLINICAL_PROFILE if mode == "AGV_AMR_LIGHT_CLINICAL" else agv.DEFAULT_HEAVY_LOGISTICS_PROFILE
    cap = agv.compute_floor_agv_capex(profile=profile, fleet_size=fleet_size, charging_station_count=stations)
    en = agv.compute_floor_agv_energy(profile=profile, round_trip_distance_km=0.3, missions_per_day=max(missions, 1), operating_days_per_year=300)
    op = agv.compute_floor_agv_opex(profile=profile, fleet_size=fleet_size, charging_station_count=stations,
                                    annual_electricity_usd=en.annual_electricity_usd, loaded_annual_cost_per_fte=70000.0)
    # Subtract the shared fleet-manager CapEx + software OPEX so they can be
    # counted ONCE at the family level (Sec 13 no double-count).
    mode_capex = cap.known_capex_subtotal - AGV_SHARED_FLEET_MANAGER_CAPEX_USD
    mode_opex = op.known_annual_opex_subtotal - AGV_SHARED_FLEET_SOFTWARE_OPEX_USD
    return ModeEconomics(
        mode, missions, mode_capex, mode_opex,
        tuple(cap.unknown_capex_components), tuple(op.unknown_opex_components),
        "fleet workload+charging", "floor_agv_amr_authority",
    )


def _rths_economics(missions: int, *, fleet_size: int) -> ModeEconomics:
    model = cta.DEFAULT_AGV_MODEL  # RGHT = rail-guided hospital transport (legacy)
    capex = cta.agv_new_study_capex(model, fleet_size=fleet_size, study_scope="CAPITAL_PLANNING") if missions else 0.0
    opex = cta.agv_annual_opex(model, fleet_size=fleet_size, loaded_annual_cost_per_fte=70000.0) if missions else 0.0
    return ModeEconomics(
        "RTHS", missions, float(capex), float(opex),
        ("Track/guideway civil works (NOT_CALIBRATED)",), ("Vendor service contract (NOT_CALIBRATED)",),
        "vehicles/track occupancy", "conventional_transport_authority RGHT (rail-guided)",
    )


def _mrt_economics(missions: int, *, guideway_m: float, carriers: int) -> ModeEconomics:
    # READ-ONLY canonical unit costs (Sec 15/59): never recomputed/altered.
    cfg = mrt.CANONICAL_MRT
    capex = guideway_m * cfg.two_way_guideway_capex_usd_per_m + carriers * cfg.carrier_capex_usd if missions else 0.0
    return ModeEconomics(
        "MRT", missions, float(capex), 0.0,
        (), ("Standby/controls/cooling electricity (NOT_CALIBRATED, canonical)", "MRT support labor (canonical authority)"),
        "canonical guideway/carrier fleet", "mrt_canonical_configuration (READ-ONLY)",
    )


# ===========================================================================
# 6. Generalized candidate (Sec 22/50). One architecture = one permitted mode
#    set + its resulting mission assignment + aggregated economics + feasibility.
# ===========================================================================

@dataclass(frozen=True)
class GeneralizedCandidate:
    candidate_id: str
    candidate_name: str
    enabled_families: tuple[TransportFamily, ...]
    enabled_subtypes: tuple[TransportSubtype, ...]
    candidate_modes: frozenset[ResolvedMode]
    actually_used_modes: tuple[ResolvedMode, ...]
    actually_used_families: tuple[TransportFamily, ...]
    assignment: AssignmentResult
    mode_economics: tuple[ModeEconomics, ...]
    shared_capex_usd: float
    shared_capex_components: tuple[str, ...]
    known_capex_usd: float
    unknown_capex_components: tuple[str, ...]
    known_annual_opex_usd: float
    unknown_opex_components: tuple[str, ...]
    lifecycle_cost_usd: float
    physically_feasible: bool
    transport_scope_feasible: bool
    mission_eligibility_feasible: bool
    capacity_feasible: bool
    qualification_feasible: bool
    economic_status: str
    unmet_missions: int
    blockers: tuple[str, ...]
    is_hybrid: bool

    def actually_used_subtypes(self) -> tuple[str, ...]:
        return tuple(m for m in self.actually_used_modes)


_ANALYSIS_YEARS = 10
_DISCOUNT_RATE_PCT = 8.0


def _annuity_factor(years: int = _ANALYSIS_YEARS, rate_pct: float = _DISCOUNT_RATE_PCT) -> float:
    r = rate_pct / 100.0
    return (1 - (1 + r) ** (-years)) / r


def _mode_economics_for(mode: ResolvedMode, missions: int) -> ModeEconomics:
    """Dispatch to the owning authority. Fleet/station sizes derived simply
    from mission count (workload-derived; never fleet=1 arbitrarily, never
    infinite)."""
    if mode == "MANUAL":
        return _manual_economics(missions)
    if mode == "PTS":
        return _pts_economics(missions)
    if mode == "DEDICATED_RP_PTS":
        return _rp_pts_economics(missions)
    if mode == "AGV_AMR_LIGHT_CLINICAL" or mode == "AGV_AMR_HEAVY_LOGISTICS":
        fleet = max(1, (missions + 19) // 20)
        return _agv_economics(mode, missions, fleet_size=fleet, stations=max(1, fleet // 2 + 1))
    if mode == "RTHS":
        fleet = max(1, (missions + 24) // 25)
        return _rths_economics(missions, fleet_size=fleet)
    if mode == "MRT":
        carriers = max(1, (missions + 9) // 10)
        return _mrt_economics(missions, guideway_m=300.0, carriers=carriers)
    raise ValueError(f"unknown resolved mode {mode}")


def _aggregate_candidate_economics(
    used_modes: tuple[ResolvedMode, ...], assignment: AssignmentResult,
) -> tuple[tuple[ModeEconomics, ...], float, tuple[str, ...], float, tuple[str, ...], float, tuple[str, ...]]:
    """Sec 28-29: aggregate mode-specific economics + count shared
    infrastructure ONCE per family. Returns (mode_econ, shared_capex,
    shared_components, known_capex, unknown_capex, known_opex, unknown_opex)."""
    mode_econ = tuple(_mode_economics_for(m, assignment.missions_by_mode.get(m, 0)) for m in used_modes)
    mode_specific_capex = sum(e.mode_specific_capex_usd for e in mode_econ)
    mode_specific_opex = sum(e.mode_specific_annual_opex_usd for e in mode_econ)

    shared_capex = 0.0
    shared_components: list[str] = []
    shared_opex = 0.0
    families = {_RESOLVED_TO_FAMILY[m] for m in used_modes}
    # PTS shared backbone counted once if any PTS-family mode is used.
    if "PTS" in families and any(m in ("PTS", "DEDICATED_RP_PTS") for m in used_modes):
        shared_capex += PTS_SHARED_BACKBONE_CAPEX_USD
        shared_components.append("PTS shared tube backbone/blowers/controls (once)")
    # AGV shared fleet-manager counted once if any AGV-family mode is used.
    if "AGV_AMR" in families:
        shared_capex += AGV_SHARED_FLEET_MANAGER_CAPEX_USD
        shared_components.append("AGV shared fleet-management HW/SW (once)")
        shared_opex += AGV_SHARED_FLEET_SOFTWARE_OPEX_USD

    known_capex = mode_specific_capex + shared_capex
    known_opex = mode_specific_opex + shared_opex
    unknown_capex = tuple(sorted({c for e in mode_econ for c in e.unknown_capex_components}))
    unknown_opex = tuple(sorted({c for e in mode_econ for c in e.unknown_opex_components}))
    return mode_econ, shared_capex, tuple(shared_components), known_capex, unknown_capex, known_opex, unknown_opex


def build_candidate(
    *, candidate_id: str, candidate_modes: frozenset[ResolvedMode],
    missions: Sequence[OptimizerMission], settings: TransportSettings,
    preference: Sequence[ResolvedMode] | None = None,
) -> GeneralizedCandidate:
    """Sec 19-22/50: build one generalized candidate from a permitted mode set.
    Assignment is eligibility-first; economics aggregate per owning authority;
    feasibility distinguishes the Sec 32 dimensions."""
    default_pref: tuple[ResolvedMode, ...] = (
        "MANUAL", "PTS", "DEDICATED_RP_PTS", "RTHS",
        "AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS", "MRT",
    )
    pref = tuple(preference) if preference is not None else default_pref
    assignment = _assign_missions(missions=missions, candidate_modes=candidate_modes, settings=settings, preference=pref)

    used_modes = tuple(m for m in default_pref if assignment.missions_by_mode.get(m, 0) > 0)
    mode_econ, shared_capex, shared_components, known_capex, unknown_capex, known_opex, unknown_opex = (
        _aggregate_candidate_economics(used_modes, assignment)
    )
    lifecycle = known_capex + known_opex * _annuity_factor()

    used_families = tuple(sorted({_RESOLVED_TO_FAMILY[m] for m in used_modes}, key=CANONICAL_TRANSPORT_FAMILIES.index))
    is_hybrid = len(used_families) >= 2

    # Feasibility dimensions (Sec 32).
    mission_eligibility_feasible = assignment.unmet_missions == 0
    transport_scope_feasible = candidate_modes.issubset(_available_resolved_modes(settings))
    capacity_feasible = True  # workload-derived sizing always yields a finite feasible fleet here
    qualification_feasible = True  # qualification-required missions are UNMET, never silently qualified
    physically_feasible = mission_eligibility_feasible
    blockers: list[str] = []
    if assignment.unmet_missions:
        unmet_streams = sorted({a.stream for a in assignment.assignments if a.status == "UNMET"})
        blockers.append(f"UNMET missions for streams {unmet_streams} (no allowed+eligible mode in scope)")

    economic_status = "COMPARABLE" if not unknown_capex and not unknown_opex else "COMPARABLE_WITH_QUALIFICATIONS"

    name_modes = "+".join(used_families) if used_families else "NONE"
    candidate_name = ("HYBRID_" + "_".join(used_families)) if is_hybrid else (used_families[0] + "_ONLY" if used_families else "INFEASIBLE_NO_MODE")

    return GeneralizedCandidate(
        candidate_id=candidate_id, candidate_name=candidate_name,
        enabled_families=settings.effectively_enabled_families(),
        enabled_subtypes=settings.effectively_enabled_subtypes(),
        candidate_modes=candidate_modes, actually_used_modes=used_modes, actually_used_families=used_families,
        assignment=assignment, mode_economics=mode_econ,
        shared_capex_usd=shared_capex, shared_capex_components=shared_components,
        known_capex_usd=known_capex, unknown_capex_components=unknown_capex,
        known_annual_opex_usd=known_opex, unknown_opex_components=unknown_opex,
        lifecycle_cost_usd=lifecycle,
        physically_feasible=physically_feasible, transport_scope_feasible=transport_scope_feasible,
        mission_eligibility_feasible=mission_eligibility_feasible, capacity_feasible=capacity_feasible,
        qualification_feasible=qualification_feasible, economic_status=economic_status,
        unmet_missions=assignment.unmet_missions, blockers=tuple(blockers), is_hybrid=is_hybrid,
    )


# ===========================================================================
# 7. Candidate generation (Sec 19-23). Enumerate single-mode + multi-mode
#    permitted mode sets over the AVAILABLE (in-scope) resolved modes, dedup
#    equivalent candidates (Sec 23), and build each.
# ===========================================================================

def generate_candidates(
    *, missions: Sequence[OptimizerMission], settings: TransportSettings = None,  # type: ignore[assignment]
    max_modes_per_candidate: int | None = None,
) -> tuple[GeneralizedCandidate, ...]:
    """Sec 19-23: generate all single-mode and multi-mode candidates over the
    available modes. An excluded family/subtype NEVER appears in any candidate
    mode set (Sec 8). Candidates that USE an identical set of modes with an
    identical mission allocation are deduplicated (Sec 23)."""
    if settings is None:
        settings = default_transport_settings()
    available = sorted(_available_resolved_modes(settings))
    if not available:
        # Sec 81: all modes off -> a single INFEASIBLE candidate (never an empty
        # apparently-successful result).
        empty = build_candidate(candidate_id="CAND-EMPTY", candidate_modes=frozenset(), missions=missions, settings=settings)
        return (empty,)

    n = len(available)
    upper = n if max_modes_per_candidate is None else min(max_modes_per_candidate, n)
    raw: list[GeneralizedCandidate] = []
    idx = 0
    for size in range(1, upper + 1):
        for combo in itertools.combinations(available, size):
            idx += 1
            cand = build_candidate(
                candidate_id=f"CAND-{idx:03d}", candidate_modes=frozenset(combo), missions=missions, settings=settings,
            )
            raw.append(cand)

    # Dedup (Sec 23): keep the FIRST candidate for each (actually_used_modes,
    # mission-allocation) signature. Two candidates whose extra permitted modes
    # go unused collapse to the same physical architecture.
    seen: dict[tuple, GeneralizedCandidate] = {}
    for cand in raw:
        signature = (
            cand.actually_used_modes,
            tuple(sorted(cand.assignment.missions_by_mode.items())),
            cand.unmet_missions,
        )
        if signature not in seen:
            seen[signature] = cand
    return tuple(seen.values())


# ===========================================================================
# 8. Selection + explainability (Sec 24/30/50-54). Objective = minimize known
#    lifecycle cost among FEASIBLE candidates (existing repository objective,
#    Sec 53), with unmet-missions as a hard feasibility gate first. NO forced
#    winner (Sec 52): technology preference plays no role.
# ===========================================================================

OPTIMIZER_OBJECTIVE = "MINIMIZE_KNOWN_LIFECYCLE_COST_AMONG_MISSION_FEASIBLE_CANDIDATES"


@dataclass(frozen=True)
class RejectionReason:
    candidate_id: str
    candidate_name: str
    reason: str


@dataclass(frozen=True)
class SelectionResult:
    objective: str
    selected: GeneralizedCandidate | None
    why_selected: str
    ranked_feasible: tuple[GeneralizedCandidate, ...]
    rejections: tuple[RejectionReason, ...]
    all_candidates: tuple[GeneralizedCandidate, ...]


def select_candidate(candidates: Sequence[GeneralizedCandidate]) -> SelectionResult:
    """Sec 51-52: select the feasible candidate with the lowest known lifecycle
    cost. Feasibility (zero unmet missions) gates comparison; economics decide
    among feasible candidates; no technology is preferred a priori."""
    feasible = [c for c in candidates if c.mission_eligibility_feasible and c.actually_used_modes]
    rejections: list[RejectionReason] = []
    for c in candidates:
        if not c.actually_used_modes:
            rejections.append(RejectionReason(c.candidate_id, c.candidate_name, "no mission assigned (empty/degenerate candidate)"))
        elif not c.mission_eligibility_feasible:
            rejections.append(RejectionReason(c.candidate_id, c.candidate_name, f"{c.unmet_missions} unmet mission(s): {c.blockers}"))

    if not feasible:
        return SelectionResult(OPTIMIZER_OBJECTIVE, None, "no feasible candidate (all have unmet missions or no assignable mode)",
                               (), tuple(rejections), tuple(candidates))

    ranked = tuple(sorted(feasible, key=lambda c: (c.lifecycle_cost_usd, c.known_capex_usd, len(c.actually_used_modes))))
    winner = ranked[0]
    for c in ranked[1:]:
        rejections.append(RejectionReason(
            c.candidate_id, c.candidate_name,
            f"higher lifecycle cost ${c.lifecycle_cost_usd:,.0f} vs selected ${winner.lifecycle_cost_usd:,.0f}"
            + (" (also has unresolved unknown costs -- comparison qualified)" if c.economic_status != "COMPARABLE" else ""),
        ))
    why = (
        f"lowest known lifecycle cost ${winner.lifecycle_cost_usd:,.0f} "
        f"(CapEx ${winner.known_capex_usd:,.0f} + OPEX-annuity) among {len(feasible)} mission-feasible candidates; "
        f"uses {winner.actually_used_families}; economic_status={winner.economic_status}"
    )
    return SelectionResult(OPTIMIZER_OBJECTIVE, winner, why, ranked, tuple(rejections), tuple(candidates))


def optimize(
    *, missions: Sequence[OptimizerMission], settings: TransportSettings = None,  # type: ignore[assignment]
    max_modes_per_candidate: int | None = None,
) -> SelectionResult:
    """Sec 9 end-to-end: settings -> candidates -> selection. The ONE runtime
    entry point that makes transport scope operational."""
    if settings is None:
        settings = default_transport_settings()
    candidates = generate_candidates(missions=missions, settings=settings, max_modes_per_candidate=max_modes_per_candidate)
    return select_candidate(candidates)

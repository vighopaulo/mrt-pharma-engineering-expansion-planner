"""Super-Build 1: Transport-Modes-In-Scope + Fallback-Conservation + Parity
Result Contract Authority.

GOVERNANCE: backend authority only (Sec 57 -- NO UI). It owns three concepts
the future generalized multi-transport optimizer will consume, established
here WITHOUT integrating that optimizer (Sec 52/94):

  1. TRANSPORT_MODES_IN_SCOPE -- the authoritative set of transport families a
     study permits. USER EXCLUSION IS AUTHORITATIVE (Sec 58): an excluded mode
     must NEVER become a candidate, a fallback, a Hybrid re-entry, or silently
     make an assignment feasible. Exclusion DOMINATES economics (Sec 89).

  2. FALLBACK CONSERVATION (Sec 59) -- a rejected mission cannot vanish. It
     moves to an explicitly allowed fallback, or the candidate is INFEASIBLE.
     Hard invariant: INPUT_MISSIONS == ASSIGNED_MISSIONS + UNMET_MISSIONS.

  3. TRANSPORT PARITY RESULT CONTRACT (Sec 93) + FUTURE OPTIMIZER SEAM
     (Sec 94) -- a normalized comparable per-mode result carrying eligibility /
     physics / economics / provenance, and a documented seam the next
     Super-Build consumes. HYBRID is NOT a hardware mode (Sec 60); it is a
     future composition of >=2 allowed modes.

This module composes `transport_mode_eligibility_authority`; it never
re-implements per-mode physics/economics and never touches MRT/Part 3E.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

import transport_mode_eligibility_authority as elig
from transport_mode_eligibility_authority import TransportModeFamily, ALL_TRANSPORT_MODE_FAMILIES

# ===========================================================================
# 1. Transport-modes-in-scope (Sec 57-58).
# ===========================================================================

@dataclass(frozen=True)
class TransportModesInScope:
    """The authoritative permitted-mode set for a study. `HYBRID` is NOT a
    member -- it is a future composition, not a hardware mode (Sec 60)."""
    modes: frozenset[TransportModeFamily]

    def __post_init__(self) -> None:
        unknown = self.modes - set(ALL_TRANSPORT_MODE_FAMILIES)
        if unknown:
            raise ValueError(f"Unknown transport mode(s) in scope: {sorted(unknown)}")
        if not self.modes:
            raise ValueError("TRANSPORT_MODES_IN_SCOPE must contain at least one mode")

    def includes(self, mode: TransportModeFamily) -> bool:
        return mode in self.modes

    def excludes(self, mode: TransportModeFamily) -> bool:
        return mode not in self.modes


def all_modes_in_scope() -> TransportModesInScope:
    return TransportModesInScope(frozenset(ALL_TRANSPORT_MODE_FAMILIES))


def modes_in_scope(*modes: TransportModeFamily) -> TransportModesInScope:
    return TransportModesInScope(frozenset(modes))


def all_except(*excluded: TransportModeFamily) -> TransportModesInScope:
    return TransportModesInScope(frozenset(m for m in ALL_TRANSPORT_MODE_FAMILIES if m not in excluded))


# ===========================================================================
# 2. Scope-aware allowed-mode resolution: eligibility AND scope must BOTH pass
#    (Sec 58/89). Exclusion dominates: an out-of-scope mode is never allowed
#    even if eligible and even if it were free.
# ===========================================================================

@dataclass(frozen=True)
class ScopedModeDecision:
    mode: TransportModeFamily
    in_scope: bool
    eligibility: str
    allowed: bool
    reason: str


def resolve_scoped_allowed_modes(
    *, scope: TransportModesInScope, stream: str, payload_mass_kg: float | None = None,
    payload_volume_l: float | None = None,
    specimen_sensitivity: "elig.SpecimenSensitivity | None" = None,
    radiopharm_qualified: bool = False, pts_sensitive_specimen_validated: bool = False,
) -> tuple[ScopedModeDecision, ...]:
    """For every canonical mode, report (in_scope, eligibility, allowed). A mode
    is ALLOWED iff it is BOTH in scope AND strictly ELIGIBLE. Out-of-scope modes
    are never allowed regardless of eligibility/economics."""
    elig_map = elig.allowed_modes_for_payload(
        stream=stream, payload_mass_kg=payload_mass_kg, payload_volume_l=payload_volume_l,
        specimen_sensitivity=specimen_sensitivity, radiopharm_qualified=radiopharm_qualified,
        pts_sensitive_specimen_validated=pts_sensitive_specimen_validated,
    )
    decisions: list[ScopedModeDecision] = []
    for mode in ALL_TRANSPORT_MODE_FAMILIES:
        in_scope = scope.includes(mode)
        e = elig_map[mode]
        allowed = in_scope and elig.is_allowed(e)
        if not in_scope:
            reason = f"EXCLUDED_BY_SCOPE (user technology exclusion is authoritative; eligibility {e.eligibility} ignored)"
        elif not elig.is_allowed(e):
            reason = f"IN_SCOPE_BUT_{e.eligibility}: {e.reason}"
        else:
            reason = "ALLOWED (in scope and eligible)"
        decisions.append(ScopedModeDecision(mode, in_scope, e.eligibility, allowed, reason))
    return tuple(decisions)


def allowed_mode_set(
    *, scope: TransportModesInScope, stream: str, payload_mass_kg: float | None = None,
    payload_volume_l: float | None = None,
    specimen_sensitivity: "elig.SpecimenSensitivity | None" = None,
    radiopharm_qualified: bool = False, pts_sensitive_specimen_validated: bool = False,
) -> frozenset[TransportModeFamily]:
    decisions = resolve_scoped_allowed_modes(
        scope=scope, stream=stream, payload_mass_kg=payload_mass_kg, payload_volume_l=payload_volume_l,
        specimen_sensitivity=specimen_sensitivity, radiopharm_qualified=radiopharm_qualified,
        pts_sensitive_specimen_validated=pts_sensitive_specimen_validated,
    )
    return frozenset(d.mode for d in decisions if d.allowed)


# ===========================================================================
# 3. Fallback conservation (Sec 59). INPUT == ASSIGNED + UNMET, always.
# ===========================================================================

@dataclass(frozen=True)
class MissionAssignmentRequest:
    mission_id: str
    stream: str
    payload_mass_kg: float | None = None
    payload_volume_l: float | None = None
    specimen_sensitivity: "elig.SpecimenSensitivity | None" = None


@dataclass(frozen=True)
class MissionAssignment:
    mission_id: str
    stream: str
    assigned_mode: TransportModeFamily | None
    status: Literal["ASSIGNED", "UNMET"]
    reason: str


@dataclass(frozen=True)
class ConservationResult:
    input_missions: int
    assigned_missions: int
    unmet_missions: int
    assignments: tuple[MissionAssignment, ...]
    conserved: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "conserved", self.input_missions == self.assigned_missions + self.unmet_missions)


def assign_missions_within_scope(
    *, scope: TransportModesInScope, missions: Sequence[MissionAssignmentRequest],
    mode_preference: Sequence[TransportModeFamily] | None = None,
    radiopharm_qualified: bool = False, pts_sensitive_specimen_validated: bool = False,
) -> ConservationResult:
    """Assign each mission to the FIRST allowed mode in `mode_preference`
    (default: canonical order) that is BOTH in scope AND eligible. A mission
    with no allowed mode becomes UNMET -- it is NEVER dropped and NEVER assigned
    to an out-of-scope mode (Sec 58-59). Conservation: INPUT == ASSIGNED + UNMET.
    NO silent fallback insertion: fallback modes must themselves be in scope."""
    preference = tuple(mode_preference) if mode_preference is not None else ALL_TRANSPORT_MODE_FAMILIES
    assignments: list[MissionAssignment] = []
    assigned = unmet = 0
    for m in missions:
        allowed = allowed_mode_set(
            scope=scope, stream=m.stream, payload_mass_kg=m.payload_mass_kg, payload_volume_l=m.payload_volume_l,
            specimen_sensitivity=m.specimen_sensitivity, radiopharm_qualified=radiopharm_qualified,
            pts_sensitive_specimen_validated=pts_sensitive_specimen_validated,
        )
        chosen: TransportModeFamily | None = next((mode for mode in preference if mode in allowed), None)
        if chosen is not None:
            assigned += 1
            assignments.append(MissionAssignment(m.mission_id, m.stream, chosen, "ASSIGNED", f"assigned to {chosen} (in scope + eligible)"))
        else:
            unmet += 1
            assignments.append(MissionAssignment(
                m.mission_id, m.stream, None, "UNMET",
                "no in-scope + eligible mode (excluded modes are never inserted as silent fallback, Sec 58-59)",
            ))
    return ConservationResult(
        input_missions=len(missions), assigned_missions=assigned, unmet_missions=unmet,
        assignments=tuple(assignments), conserved=True,
    )


# ===========================================================================
# 4. Transport parity result contract (Sec 61-62/93) -- normalized comparable
#    per-mode outputs. Not all modes have every physical/economic component;
#    NOT_APPLICABLE / NOT_CALIBRATED are first-class (never $0).
# ===========================================================================

ParityFieldStatus = Literal["MODELED", "CONTROLLED_BENCHMARK", "NOT_CALIBRATED", "NOT_APPLICABLE"]


@dataclass(frozen=True)
class TransportParityResult:
    """Sec 93: one comparable row per (mode, configuration, payload stream).
    Physical representation is NOT forced identical across technologies; the
    STATUS fields carry provenance/calibration."""
    transport_mode: TransportModeFamily
    configuration_id: str
    payload_stream: str
    eligibility: str
    route_time_minutes: float | None
    route_time_status: ParityFieldStatus
    capacity_basis: str
    required_resources: str
    known_capex_usd: float | None
    unknown_capex_components: tuple[str, ...]
    known_annual_opex_usd: float | None
    unknown_opex_components: tuple[str, ...]
    total_opex_status: str
    provenance: str
    calibration_status: str
    known_limitations: tuple[str, ...] = ()


# ===========================================================================
# 5. Economic + physics parity CONTRACT category definitions (Sec 61-62). These
#    are the comparable schema categories every mode must classify against.
# ===========================================================================

ECONOMIC_PARITY_CATEGORIES: tuple[str, ...] = (
    "KNOWN_CAPEX", "UNKNOWN_CAPEX", "KNOWN_ANNUAL_LABOR_OPEX", "KNOWN_ANNUAL_ENERGY_OPEX",
    "KNOWN_ANNUAL_MAINTENANCE_OPEX", "KNOWN_ANNUAL_SOFTWARE_SUPPORT_OPEX", "KNOWN_ANNUAL_OTHER_OPEX",
    "UNKNOWN_OPEX_CATEGORIES", "KNOWN_ANNUAL_OPEX_SUBTOTAL", "TOTAL_OPEX_STATUS",
)

PHYSICS_PARITY_CATEGORIES: tuple[str, ...] = (
    "PAYLOAD_LIMIT", "VOLUME_LIMIT", "SPEED", "ROUTE_TIME", "LOAD_TIME", "UNLOAD_TIME", "VERTICAL_TRAVEL",
    "CONGESTION", "QUEUEING", "CAPACITY", "AVAILABILITY", "DOWNTIME", "ENERGY", "MAINTENANCE",
    "FLEET_REQUIREMENT", "MISSION_ELIGIBILITY",
)


# ===========================================================================
# 6. FUTURE OPTIMIZER CONTRACT (Sec 94) -- documented seam only; NOT implemented.
# ===========================================================================

FUTURE_OPTIMIZER_CONTRACT = (
    "GENERALIZED_TRANSPORT_CANDIDATE_GENERATION = "
    "TRANSPORT_MODES_IN_SCOPE (transport_mode_scope_authority.TransportModesInScope) + "
    "TRANSPORT_ELIGIBILITY_AUTHORITY (transport_mode_eligibility_authority.allowed_modes_for_payload) + "
    "MODE_SPECIFIC_PHYSICS (conventional_transport_authority / floor_agv_amr_authority / dedicated_rp_pts_authority / "
    "shared_mrt_multistream_authority) + "
    "MODE_SPECIFIC_ECONOMICS (per-mode CapEx/OPEX authorities). "
    "The NEXT Super-Build consumes exactly these seams to generate multi-technology candidates + true Hybrid "
    "compositions; it is NOT implemented in this build (isolated authorities READY_FOR_NEXT_INTEGRATION)."
)

GENERALIZED_OPTIMIZER_INTEGRATED_NOW = False
"""Hard flag: this Super-Build establishes the parity authorities but does NOT
wire them into a generalized multi-transport optimizer (Sec 52/94)."""

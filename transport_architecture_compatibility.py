"""KIRO Super-Build 2 -- Legacy Four-Architecture Compatibility Adapter
(Sec 47-49).

The existing named four-architecture evaluators in
`whole_oncology_four_architecture_optimization.py`
(MANUAL_CONVENTIONAL / AUTOMATED_CONVENTIONAL / HYBRID_MRT / MRT_DOMINANT)
are mature, heavily tested, and remain the authoritative economic engines for
those specific named studies.

CHOSEN COMPATIBILITY STRATEGY (Sec 47, reported honestly):
  PRESERVE_AS_LEGACY_ADAPTERS -- the legacy evaluators are PRESERVED UNCHANGED.
  This module is a THIN, ADDITIVE adapter that expresses each legacy named
  architecture as the equivalent generalized `TransportSettings` scope, so a
  caller can reason about both vocabularies. It does NOT rewrite the legacy
  evaluators as wrappers over the generalized optimizer (that would risk
  changing byte-for-byte tested economics), and it does NOT claim the legacy
  code disappeared (Sec 48: NO FALSE CURRENT-RUNTIME CLAIM).

AUTOMATED_CONVENTIONAL SEMANTICS (Sec 49): AUTOMATED_CONVENTIONAL is NOT a
single transport family. Its existing physical meaning is a COMPOSITE:
manual-cluster + AGV/PTS-distribution + manual last-mile (nuclear side
unchanged/manual). Its historical semantics are preserved: the generalized
scope equivalent enables MANUAL + PTS + AGV_AMR, but the legacy composite
architecture's specific CLUSTER/DISTRIBUTION tiering remains owned by
`evaluate_automated_conventional`, not reproduced here.

Nothing here changes MRT canonical physics, Part 3E, or equal_budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from transport_settings_authority import TransportSettings, only_families

LegacyArchitectureMode = Literal[
    "MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT",
]

COMPATIBILITY_STRATEGY = "PRESERVE_AS_LEGACY_ADAPTERS"
"""Sec 47: the legacy evaluators are preserved unchanged; this module only maps
names -> generalized scope. NEVER claims the legacy code became a wrapper."""

LEGACY_EVALUATORS_PRESERVED = True
"""Sec 48: the four legacy evaluate_* functions physically still exist in
whole_oncology_four_architecture_optimization.py and are unchanged by this build."""


@dataclass(frozen=True)
class LegacyArchitectureMapping:
    legacy_architecture: LegacyArchitectureMode
    generalized_settings: TransportSettings
    semantics: str
    is_composite: bool
    preserved_owner: str


def _mapping(mode: LegacyArchitectureMode) -> LegacyArchitectureMapping:
    if mode == "MANUAL_CONVENTIONAL":
        return LegacyArchitectureMapping(
            mode, only_families("MANUAL"),
            "Porter/hand-carry/cart for nuclear + all general logistics; no MRT/AGV/PTS.",
            False, "whole_oncology_four_architecture_optimization.evaluate_manual_conventional",
        )
    if mode == "AUTOMATED_CONVENTIONAL":
        return LegacyArchitectureMapping(
            mode, only_families("MANUAL", "PTS", "AGV_AMR"),
            "COMPOSITE (Sec 49): manual-cluster + AGV/PTS-distribution main leg + manual last-mile; "
            "nuclear side unchanged/manual. NOT a single family; legacy CLUSTER/DISTRIBUTION tiering "
            "owned by evaluate_automated_conventional, not reproduced.",
            True, "whole_oncology_four_architecture_optimization.evaluate_automated_conventional",
        )
    if mode == "HYBRID_MRT":
        return LegacyArchitectureMapping(
            mode, only_families("MANUAL", "MRT"),
            "MRT covers selected zones only; Conventional (manual) serves the rest. Legacy floor-partition "
            "Hybrid owned by hybrid_optimization.evaluate_hybrid_zone_candidate (zone coverage).",
            True, "whole_oncology_four_architecture_optimization.evaluate_hybrid_mrt",
        )
    if mode == "MRT_DOMINANT":
        return LegacyArchitectureMapping(
            mode, only_families("MANUAL", "MRT"),
            "MRT is the principal network for all compatible loads; manual fallback for exceptions "
            "(bulk linen). Legacy owner evaluate_mrt_dominant.",
            False, "whole_oncology_four_architecture_optimization.evaluate_mrt_dominant",
        )
    raise ValueError(f"Unknown legacy architecture: {mode}")


LEGACY_ARCHITECTURE_MAPPINGS: Mapping[LegacyArchitectureMode, LegacyArchitectureMapping] = {
    m: _mapping(m) for m in ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT")
}


def legacy_architecture_to_settings(mode: LegacyArchitectureMode) -> TransportSettings:
    """Sec 47: the generalized `TransportSettings` scope equivalent of a legacy
    named architecture. The legacy evaluator remains the authoritative economic
    engine for that named architecture; this is a scope-vocabulary bridge only."""
    return LEGACY_ARCHITECTURE_MAPPINGS[mode].generalized_settings


def automated_conventional_is_composite() -> bool:
    """Sec 49: AUTOMATED_CONVENTIONAL is a composite portfolio, not one family."""
    return LEGACY_ARCHITECTURE_MAPPINGS["AUTOMATED_CONVENTIONAL"].is_composite

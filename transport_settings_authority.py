"""KIRO Super-Build 2 -- Transport Settings Authority (family/subtype ON/OFF).

THE CENTRAL PRODUCT CAPABILITY (Sec 6-8): the user decides which transport
technologies the digital twin is allowed to consider, and the runtime obeys
that choice ABSOLUTELY. This module owns the ONE backend settings structure
representing that permission, at both the family and subtype level, with
parent->child inheritance (Sec 7) and deterministic serialization (Sec 45).

It is a BACKEND SETTINGS CONTRACT (no UI, Sec 6). It composes -- never
re-implements -- the Super-Build 1 authorities:

  * five canonical TOP-LEVEL families (Sec 5): MANUAL, PTS, RTHS, AGV_AMR, MRT
  * subtypes (Sec 5): PTS_CONVENTIONAL / PTS_NUCLEAR_QUALIFIED,
    AGV_AMR_LIGHT_CLINICAL / AGV_AMR_HEAVY_LOGISTICS
  * RTHS = the legacy rail-guided hospital transport family
    (transport_technology_authority.RGHT), distinct from free-roaming AGV_AMR
  * MRT = MRT_CANONICAL_COMPACT (preserved, never re-costed here)

The settings resolve down to `transport_mode_eligibility_authority`'s
`TransportModeFamily` vocabulary (the 6 eligibility families) so the
generalized optimizer consumes ONE reconciled mode set. RTHS maps to the
DEDICATED_RP_PTS-style legacy handling is NOT done here: RTHS is its own
family. DEDICATED_RP_PTS is treated as the nuclear-qualified PTS subtype's
dedicated-infrastructure eligibility owner (Sec 12).

NOTHING here changes MRT canonical physics, Part 3E, or equal_budget.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Literal, Mapping

from transport_mode_eligibility_authority import TransportModeFamily

# ===========================================================================
# 1. Canonical five top-level families + subtype vocabulary (Sec 5).
# ===========================================================================

TransportFamily = Literal["MANUAL", "PTS", "RTHS", "AGV_AMR", "MRT"]

CANONICAL_TRANSPORT_FAMILIES: tuple[TransportFamily, ...] = (
    "MANUAL", "PTS", "RTHS", "AGV_AMR", "MRT",
)

TransportSubtype = Literal[
    "PTS_CONVENTIONAL", "PTS_NUCLEAR_QUALIFIED",
    "AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS",
    "RTHS_STANDARD_CARRIER", "MRT_CANONICAL_COMPACT",
]

# Sec 5: subtype -> parent family. RTHS and MRT each currently have one
# canonical configuration; MANUAL has none (the family IS the configuration).
SUBTYPE_PARENT: Mapping[TransportSubtype, TransportFamily] = {
    "PTS_CONVENTIONAL": "PTS",
    "PTS_NUCLEAR_QUALIFIED": "PTS",
    "AGV_AMR_LIGHT_CLINICAL": "AGV_AMR",
    "AGV_AMR_HEAVY_LOGISTICS": "AGV_AMR",
    "RTHS_STANDARD_CARRIER": "RTHS",
    "MRT_CANONICAL_COMPACT": "MRT",
}

FAMILY_SUBTYPES: Mapping[TransportFamily, tuple[TransportSubtype, ...]] = {
    "MANUAL": (),
    "PTS": ("PTS_CONVENTIONAL", "PTS_NUCLEAR_QUALIFIED"),
    "RTHS": ("RTHS_STANDARD_CARRIER",),
    "AGV_AMR": ("AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS"),
    "MRT": ("MRT_CANONICAL_COMPACT",),
}

# ===========================================================================
# 2. Reconciliation to the eligibility TransportModeFamily vocabulary.
#    The generalized optimizer works in the eligibility vocabulary; the user
#    controls scope in the CANONICAL family/subtype vocabulary. This is the
#    ONE mapping that reconciles the two (Sec 4 gotcha).
#
#    MANUAL                    -> MANUAL
#    PTS_CONVENTIONAL          -> PTS
#    PTS_NUCLEAR_QUALIFIED     -> DEDICATED_RP_PTS  (nuclear-qualified dedicated)
#    RTHS_STANDARD_CARRIER     -> RTHS  (own eligibility family; see below)
#    AGV_AMR_LIGHT_CLINICAL    -> AGV_AMR_LIGHT_CLINICAL
#    AGV_AMR_HEAVY_LOGISTICS   -> AGV_AMR_HEAVY_LOGISTICS
#    MRT_CANONICAL_COMPACT     -> MRT
# ===========================================================================

# The eligibility authority does not model a distinct RTHS family (RTHS is the
# legacy rail-guided class owned by conventional_transport_authority /
# transport_technology_authority.RGHT). For scope resolution the optimizer
# handles RTHS through its own legacy authority, so RTHS subtypes map to the
# sentinel "RTHS" (not an eligibility TransportModeFamily). See
# generalized_transport_optimizer for how RTHS eligibility is resolved.
ResolvedMode = Literal[
    "MANUAL", "PTS", "DEDICATED_RP_PTS",
    "AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS", "MRT", "RTHS",
]

SUBTYPE_RESOLVED_MODE: Mapping[TransportSubtype, ResolvedMode] = {
    "PTS_CONVENTIONAL": "PTS",
    "PTS_NUCLEAR_QUALIFIED": "DEDICATED_RP_PTS",
    "AGV_AMR_LIGHT_CLINICAL": "AGV_AMR_LIGHT_CLINICAL",
    "AGV_AMR_HEAVY_LOGISTICS": "AGV_AMR_HEAVY_LOGISTICS",
    "RTHS_STANDARD_CARRIER": "RTHS",
    "MRT_CANONICAL_COMPACT": "MRT",
}

FAMILY_RESOLVED_MODE: Mapping[TransportFamily, ResolvedMode] = {
    "MANUAL": "MANUAL",  # MANUAL family resolves directly (no subtype)
    # families below only resolve through their subtypes; entry documents intent
}


# ===========================================================================
# 3. The settings structure (Sec 6).
# ===========================================================================

@dataclass(frozen=True)
class TransportSettings:
    """What the user permits the simulation to consider (Sec 6). Family-level
    switches + subtype-level switches. Parent OFF forces every child OFF
    EFFECTIVELY (Sec 7); a child cannot override a disabled parent.

    Defaults (Sec 46): all families and subtypes ON, preserving the existing
    all-technologies-available behaviour so legacy architecture scope remains
    available. The user must still be able to exclude any technology, which
    the `*_enabled` flags provide."""

    manual_enabled: bool = True
    pts_enabled: bool = True
    rths_enabled: bool = True
    agv_amr_enabled: bool = True
    mrt_enabled: bool = True

    pts_conventional_enabled: bool = True
    pts_nuclear_qualified_enabled: bool = True
    agv_amr_light_clinical_enabled: bool = True
    agv_amr_heavy_logistics_enabled: bool = True
    rths_standard_carrier_enabled: bool = True
    mrt_canonical_compact_enabled: bool = True

    # Project-supplied qualification flags (Sec 11): a radiopharmaceutical
    # QUALIFICATION_REQUIRED mode does NOT become eligible unless the study
    # explicitly supplies the qualification. Default: absent.
    radiopharm_qualification_supplied: bool = False
    pts_sensitive_specimen_validated: bool = False

    def family_enabled(self, family: TransportFamily) -> bool:
        return {
            "MANUAL": self.manual_enabled, "PTS": self.pts_enabled,
            "RTHS": self.rths_enabled, "AGV_AMR": self.agv_amr_enabled,
            "MRT": self.mrt_enabled,
        }[family]

    def _subtype_own_flag(self, subtype: TransportSubtype) -> bool:
        return {
            "PTS_CONVENTIONAL": self.pts_conventional_enabled,
            "PTS_NUCLEAR_QUALIFIED": self.pts_nuclear_qualified_enabled,
            "AGV_AMR_LIGHT_CLINICAL": self.agv_amr_light_clinical_enabled,
            "AGV_AMR_HEAVY_LOGISTICS": self.agv_amr_heavy_logistics_enabled,
            "RTHS_STANDARD_CARRIER": self.rths_standard_carrier_enabled,
            "MRT_CANONICAL_COMPACT": self.mrt_canonical_compact_enabled,
        }[subtype]

    def subtype_effectively_enabled(self, subtype: TransportSubtype) -> bool:
        """Sec 7: a subtype is EFFECTIVELY enabled iff its own flag is ON AND
        its parent family is ON. Parent OFF forces the child OFF regardless of
        the child's own flag (a child cannot override a disabled parent)."""
        parent = SUBTYPE_PARENT[subtype]
        return self.family_enabled(parent) and self._subtype_own_flag(subtype)

    def effectively_enabled_subtypes(self) -> tuple[TransportSubtype, ...]:
        return tuple(s for s in SUBTYPE_PARENT if self.subtype_effectively_enabled(s))

    def effectively_enabled_families(self) -> tuple[TransportFamily, ...]:
        """A family is effectively active iff it is ON and (has no subtypes OR
        at least one subtype is effectively enabled)."""
        active: list[TransportFamily] = []
        for fam in CANONICAL_TRANSPORT_FAMILIES:
            if not self.family_enabled(fam):
                continue
            subs = FAMILY_SUBTYPES[fam]
            if not subs or any(self.subtype_effectively_enabled(s) for s in subs):
                active.append(fam)
        return tuple(active)

    # -- serialization (Sec 45) --------------------------------------------

    def to_dict(self) -> dict[str, bool]:
        return {
            "manual_enabled": self.manual_enabled,
            "pts_enabled": self.pts_enabled,
            "rths_enabled": self.rths_enabled,
            "agv_amr_enabled": self.agv_amr_enabled,
            "mrt_enabled": self.mrt_enabled,
            "pts_conventional_enabled": self.pts_conventional_enabled,
            "pts_nuclear_qualified_enabled": self.pts_nuclear_qualified_enabled,
            "agv_amr_light_clinical_enabled": self.agv_amr_light_clinical_enabled,
            "agv_amr_heavy_logistics_enabled": self.agv_amr_heavy_logistics_enabled,
            "rths_standard_carrier_enabled": self.rths_standard_carrier_enabled,
            "mrt_canonical_compact_enabled": self.mrt_canonical_compact_enabled,
            "radiopharm_qualification_supplied": self.radiopharm_qualification_supplied,
            "pts_sensitive_specimen_validated": self.pts_sensitive_specimen_validated,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, bool]) -> "TransportSettings":
        known = set(cls().to_dict().keys())
        unknown = set(data.keys()) - known
        if unknown:
            raise ValueError(f"Unknown transport settings keys: {sorted(unknown)}")
        return cls(**{k: bool(v) for k, v in data.items()})

    @classmethod
    def from_json(cls, text: str) -> "TransportSettings":
        return cls.from_dict(json.loads(text))


def default_transport_settings() -> TransportSettings:
    """Sec 46: the documented safe product default -- all technologies ON,
    preserving existing all-architectures-available behaviour. Backward
    compatible: no existing caller that omits settings changes behaviour."""
    return TransportSettings()


def only_families(*families: TransportFamily) -> TransportSettings:
    """Enable exactly the named families (subtypes ON within them); disable
    all others. Convenience for scope matrices (Sec 43)."""
    on = set(families)
    return TransportSettings(
        manual_enabled="MANUAL" in on, pts_enabled="PTS" in on, rths_enabled="RTHS" in on,
        agv_amr_enabled="AGV_AMR" in on, mrt_enabled="MRT" in on,
    )


def all_except_families(*excluded: TransportFamily) -> TransportSettings:
    return only_families(*(f for f in CANONICAL_TRANSPORT_FAMILIES if f not in excluded))


def with_overrides(base: TransportSettings, **overrides: object) -> TransportSettings:
    return replace(base, **overrides)

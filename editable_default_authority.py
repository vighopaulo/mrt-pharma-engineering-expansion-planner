"""Editable Default -> Active Value -> Override authority (Build 2R,
Dedicated RP-PTS round, Sections 1-4/23-27/31 + "Governing Calibration
Policy"/"No False Calibration"/"Defaults Must Be Editable" appendices).

GOVERNANCE: every externally-sourced or project-assumption parameter used by
the capital-planning engines should be representable as an `EditableParameter`
carrying BOTH a published/controlled `default_value` and an optional
`override_value` -- the calculation engine always reads `.active_value`
(never `default_value` directly), so a user override can never silently lose
the original default/provenance (Section 2: "Do not overwrite the published
value when a user changes the project value.").

This module does NOT change any existing active benchmark value on its own
(Section 23: "migrate them toward the same default/override structure
WITHOUT changing active benchmark values unless explicitly required").
`ORDINARY_PTS_SPEED_M_PER_S` below is a worked example of this: its
`default_value` is the newly-registered PUBLISHED_ENGINEERING_DEFAULT
(6.1 m/s), but its `override_value` is set to the EXISTING, unchanged
`conventional_transport_authority.DEFAULT_PTS_NETWORK.speed_m_per_s=6.0`
authority -- so `.active_value` still resolves to 6.0, preserving the
Automated Conventional benchmark exactly, while disclosing the published
reference alongside it.

SOURCE-TYPE HIERARCHY (Section 3, preference order 1=strongest):
    MANUFACTURER_DEFAULT
    PUBLISHED_CLINICAL_DEFAULT / PUBLISHED_CLINICAL_PRECEDENT
    PUBLISHED_ENGINEERING_DEFAULT
    PUBLISHED_REFERENCE_BENCHMARK
    PUBLISHED_COST_REFERENCE
    PROJECT_CONTROLLED_ASSUMPTION
    CONTROLLED_ENGINEERING_ASSUMPTION
    NOT_CALIBRATED (only when no defensible default exists at all)

A published/controlled default is explicitly NEVER labeled
`CALIBRATED_PROJECT_VALUE` (Section 4) -- that status is reserved for an
actual facility/vendor-confirmed value, which no parameter here has yet.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

EvidenceClass = str  # see hierarchy above -- kept as str (no closed enum yet).


@dataclass(frozen=True)
class EditableParameter:
    parameter_id: str
    default_value: float | None
    units: str
    source: str
    source_type: EvidenceClass
    confidence: str  # "HIGH" | "MEDIUM-HIGH" | "MEDIUM" | "LOW"
    user_editable: bool = True
    override_value: float | None = None
    notes: str = ""

    @property
    def active_value(self) -> float | None:
        """The ONE value every calculation must read -- never `default_value`
        directly (Section 2). None means genuinely NOT_CALIBRATED (no
        defensible default AND no override exist -- never fabricated)."""
        return self.override_value if self.override_value is not None else self.default_value

    @property
    def override_status(self) -> str:
        return "USER_OVERRIDE" if self.override_value is not None else "NO_OVERRIDE"

    @property
    def status(self) -> str:
        if self.active_value is None:
            return "NOT_CALIBRATED"
        return "USER_OVERRIDE" if self.override_value is not None else self.source_type

    def with_override(self, value: float) -> "EditableParameter":
        """Applies a project-specific override -- the original `default_value`
        and `source`/`source_type` are PRESERVED unchanged (Section 2: never
        destroy the original default or provenance)."""
        return replace(self, override_value=value)

    def clear_override(self) -> "EditableParameter":
        return replace(self, override_value=None)


# ---------------------------------------------------------------------------
# Section 8/23: ordinary + Dedicated RP-PTS operating-speed defaults.
# ---------------------------------------------------------------------------

ORDINARY_PTS_SPEED_M_PER_S = EditableParameter(
    parameter_id="PTS_OPERATING_SPEED_M_PER_S",
    default_value=6.1,
    units="m/s",
    source="~20 ft/s published hospital pneumatic-tube operating-speed planning reference",
    source_type="PUBLISHED_ENGINEERING_DEFAULT",
    confidence="MEDIUM-HIGH",
    # Preserves the EXISTING, already-tested ordinary-PTS active benchmark
    # value (conventional_transport_authority.DEFAULT_PTS_NETWORK.speed_m_per_s
    # = 6.0) as a project-controlled override -- Section 23 forbids changing
    # the active Automated Conventional result in this build.
    override_value=6.0,
    notes=(
        "Published default is NOT a guaranteed vendor performance, maximum speed, or calibrated project speed. "
        "Active value (6.0 m/s) is the pre-existing repo CONTROLLED_ENGINEERING_ASSUMPTION for ordinary PTS, "
        "preserved unchanged; represented here as a PROJECT_CONTROLLED_ASSUMPTION override of the new published default."
    ),
)

RP_PTS_OPERATING_SPEED_M_PER_S = EditableParameter(
    parameter_id="RP_PTS_OPERATING_SPEED_M_PER_S",
    default_value=6.1,
    units="m/s",
    source="Ordinary PTS published planning reference (~20 ft/s), applied to RP-PTS via disclosed cross-technology transferability assumption",
    source_type="PUBLISHED_ENGINEERING_DEFAULT",
    confidence="LOW",
    notes=(
        "No RP-PTS-specific (shielded-carrier) speed authority exists in manufacturer/clinical literature or this "
        "repo. Section 8: the ordinary-PTS published value MAY be used as an editable planning default for RP-PTS "
        "with explicit transferability disclosure -- it is NOT vendor-validated for a shielded radiopharmaceutical carrier."
    ),
)

PTS_REFERENCE_TRANSACTIONS_PER_DAY = EditableParameter(
    parameter_id="PTS_REFERENCE_TRANSACTIONS_PER_DAY",
    default_value=1500.0,
    units="transactions/day",
    source="Documented industry PTS throughput planning reference",
    source_type="PUBLISHED_REFERENCE_BENCHMARK",
    confidence="MEDIUM",
    notes=(
        "Section 9: this is a SANITY/REFERENCE benchmark ONLY, NEVER the mathematical network-capacity ceiling. "
        "Actual capacity must be determined from missions/cycle-time/stations/concurrency, never from "
        "'1,500/day > demand therefore feasible.'"
    ),
)

RP_PTS_PET_DOSE_PRECEDENT_DISTANCE_M = EditableParameter(
    parameter_id="RP_PTS_PET_DOSE_PRECEDENT_DISTANCE_M",
    default_value=76.2,  # 250 ft
    units="m",
    source="Published PET unit-dose pneumatic transport precedent (radiochemistry facility to PET imaging)",
    source_type="PUBLISHED_CLINICAL_PRECEDENT",
    confidence="MEDIUM-HIGH",
    user_editable=False,  # a historical precedent fact, not a project planning knob.
    notes=(
        "Section 10: proves RADIOPHARMACEUTICAL_PTS_IS_REAL_CLINICAL_PRACTICE. Does NOT prove 76.2m is a maximum "
        "or recommended range, this benchmark's carrier mass, shielding design, or installed cost. Disclosure-only "
        "-- never used as this benchmark's network_length_m (the actual facility geometry is reused instead)."
    ),
)

RP_PTS_PUBLISHED_SYSTEM_CAPEX_REFERENCE_USD = EditableParameter(
    parameter_id="RP_PTS_PUBLISHED_SYSTEM_CAPEX_REFERENCE_USD",
    default_value=350_000.0,
    units="USD",
    source="Illustrative medium-hospital ordinary PTS system cost reference",
    source_type="PUBLISHED_COST_REFERENCE",
    confidence="LOW",
    notes=(
        "Section 11/12: this is an ORDINARY-PTS-scale reference, NOT a calibrated dedicated-radioactive-transport "
        "installed cost. Used ONLY as an evidence-based planning default / sensitivity basis for Dedicated RP-PTS "
        "bundled network+station+carrier+controls+installation CapEx -- never stacked with the separate, unrelated "
        "$100,000/floor ordinary-PTS controlled model."
    ),
)

RP_PTS_STATION_HANDLING_MINUTES = EditableParameter(
    parameter_id="RP_PTS_STATION_HANDLING_MINUTES",
    default_value=1.5,
    units="minutes",
    source="Reused conventional_transport_authority.DEFAULT_PTS_NETWORK.station_handling_minutes (ordinary PTS authority)",
    source_type="PROJECT_CONTROLLED_ASSUMPTION",
    confidence="LOW",
    notes="No stronger dedicated RP-PTS station-handling-time source found (Section 18) -- retains the existing controlled handling assumption.",
)

RP_PTS_DISPATCH_MINUTES = EditableParameter(
    parameter_id="RP_PTS_DISPATCH_MINUTES",
    default_value=1.0,
    units="minutes",
    source="Reused conventional_transport_authority.DEFAULT_PTS_NETWORK.dispatch_minutes (ordinary PTS authority)",
    source_type="PROJECT_CONTROLLED_ASSUMPTION",
    confidence="LOW",
    notes="No stronger dedicated RP-PTS dispatch-time source found -- retains the existing controlled dispatch assumption.",
)

RP_PTS_SHIELDED_CARRIER_MASS_LIMIT_KG = EditableParameter(
    parameter_id="RP_PTS_SHIELDED_CARRIER_MASS_LIMIT_KG",
    default_value=None,
    units="kg",
    source="",
    source_type="NOT_CALIBRATED",
    confidence="LOW",
    notes="Section 13: no defensible public/internal maximum shielded-carrier mass exists -- NEVER invented as 2kg/5kg.",
)

RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD = EditableParameter(
    parameter_id="RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD",
    default_value=8_000.0,
    units="USD/year",
    source="Reused conventional_transport_authority.DEFAULT_PTS_NETWORK.annual_maintenance_opex (ordinary PTS authority)",
    source_type="PROJECT_CONTROLLED_ASSUMPTION",
    confidence="LOW",
    notes="No dedicated RP-PTS maintenance-rate source found -- reuses the ordinary-PTS controlled rate as an evidence-based planning default.",
)

RP_PTS_ANNUAL_ENERGY_OPEX_USD = EditableParameter(
    parameter_id="RP_PTS_ANNUAL_ENERGY_OPEX_USD",
    default_value=1_000.0,
    units="USD/year",
    source="Reused conventional_transport_authority.DEFAULT_PTS_NETWORK.annual_energy_opex (ordinary PTS authority)",
    source_type="PROJECT_CONTROLLED_ASSUMPTION",
    confidence="LOW",
    notes="No dedicated RP-PTS energy-rate source found -- reuses the ordinary-PTS controlled rate as an evidence-based planning default.",
)


def editable_default_registry_table() -> tuple[EditableParameter, ...]:
    """Every PTS/RP-PTS editable default introduced or touched in this build
    (Section 31, Table 1)."""
    return (
        ORDINARY_PTS_SPEED_M_PER_S,
        RP_PTS_OPERATING_SPEED_M_PER_S,
        PTS_REFERENCE_TRANSACTIONS_PER_DAY,
        RP_PTS_PET_DOSE_PRECEDENT_DISTANCE_M,
        RP_PTS_PUBLISHED_SYSTEM_CAPEX_REFERENCE_USD,
        RP_PTS_STATION_HANDLING_MINUTES,
        RP_PTS_DISPATCH_MINUTES,
        RP_PTS_SHIELDED_CARRIER_MASS_LIMIT_KG,
        RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD,
        RP_PTS_ANNUAL_ENERGY_OPEX_USD,
    )

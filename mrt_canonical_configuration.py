"""MRT CANONICAL CURRENT CONFIGURATION AUTHORITY.

ONE canonical current MRT (compact reduced design) configuration authority.

CORRECTION BUILD PURPOSE
------------------------
The repository accumulated multiple generations of MRT physical/economic
assumptions across three modules with two live divergences and three gaps
(see `MRT_CANONICAL_CONFIGURATION_AUTHORITY.md`, sections 2-4):

  * `shared_mrt_multistream_authority.py`      (Light-MRT: 5.0 kg ceiling, $2,000/m guideway)
  * `mrt_transport_energy_maintenance_authority.py` (Light-MRT: 2.0+3.0 kg, $5,000 carrier, E=P*t energy)
  * `operational_day_orchestrator.py` / `models.PlannerAssumptions` (HEAVY MRT: 12/6.5/12 kg,
                                                 $10,000 carrier, $5,000/m guideway, 3.0/1.5 m/s)

This module establishes the ONE current-configuration authority. It does NOT
delete the preserved HEAVY-MRT scope (a separate, documented configuration
locked by dozens of pre-existing tests -- Section 29): that scope remains for
historical/comparative reference and is classified ACTIVE_OBSOLETE_PRESERVED
in the trace, never silently rewritten here.

PROVENANCE DISCIPLINE
---------------------
Every value below is a CONTROLLED_ENGINEERING_ASSUMPTION or
CONTROLLED_ENGINEERING_ENVELOPE (Section 5). None is manufacturer-calibrated.
The `status` field on each entry preserves that provenance and must never be
relabeled CALIBRATED/MANUFACTURER_CALIBRATED without real vendor evidence.

NO FORCED MRT WIN (Section 35)
------------------------------
This module fixes the machine being tested; it does not decide the winner.
It never reduces MRT cost below the stated canonical assumptions, never
inflates competing architectures, and never fabricates an MRT advantage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping


# ===========================================================================
# 0. PROVENANCE VOCABULARY (Section 5)
# ===========================================================================

ConfigStatus = Literal[
    "CONTROLLED_ENGINEERING_ASSUMPTION",
    "CONTROLLED_ENGINEERING_ENVELOPE",
    "CONTROLLED_PLANNING_ASSUMPTION",
    "PHYSICS_DERIVED",
    "NOT_CALIBRATED",
]

CANONICAL_CONFIG_NAME = "MRT"
"""Product/configuration name (Section 0). 'MRT Light' / 'Light-MRT' /
'MRT-Dominant hardware' / the old large-carrier configuration are NOT separate
current hardware products -- MRT_DOMINANT is a deployment POLICY, not hardware
(Section 9/36)."""


# ===========================================================================
# 1. MASS (Section 0.1, 6)
# ===========================================================================

MAX_GROSS_MOVING_MASS_KG = 5.0
"""CONTROLLED_ENGINEERING_ASSUMPTION. Section 0.1: the TOTAL moving mass --
carrier + shielding + coils + electronics + mission insert + payload. This is
NOT empty-carrier mass. Authoritative hard ceiling for current MRT planning.
Numerically identical to the pre-existing
`shared_mrt_multistream_authority.LIGHT_MRT_LOADED_MASS_CEILING_KG` (=5.0),
now promoted to the single canonical owner."""

EMPTY_CARRIER_MASS_TARGET_LOW_KG = 2.0
EMPTY_CARRIER_MASS_TARGET_HIGH_KG = 3.0
"""CONTROLLED_ENGINEERING_ASSUMPTION. Section 0.1 empty-carrier engineering
target range 2.0-3.0 kg."""

PAYLOAD_TARGET_LOW_KG = 2.0
PAYLOAD_TARGET_HIGH_KG = 3.0
"""CONTROLLED_ENGINEERING_ASSUMPTION. Section 0.1 usable payload target range
~2.0-3.0 kg, subject always to TOTAL MOVING MASS <= 5.0 kg."""


# ===========================================================================
# 2. CARRIER GEOMETRY (Section 0.2, 7)
# ===========================================================================

CARRIER_LENGTH_M = 0.200
CARRIER_WIDTH_M = 0.120
CARRIER_HEIGHT_M = 0.100
"""CONTROLLED_ENGINEERING_ENVELOPE (200 mm x 120 mm x 100 mm), Section 0.2.
NOT manufacturer-calibrated. This is the EXTERNAL envelope; internal usable
volume is NOT_CALIBRATED (wall/shield/coil thickness not calibrated -- see
`qualify_payload_volume`)."""


# ===========================================================================
# 3. SPEED (Section 0.3, 11)
# ===========================================================================

MAX_STRAIGHT_SPEED_M_PER_S = 10.0
"""CONTROLLED_ENGINEERING_ASSUMPTION. Section 0.3: maximum STRAIGHT-SEGMENT
design speed (= 36 km/h). This is NOT the speed through curves, vertical
transitions, junctions, station approaches, or braking -- those segment
dynamics are NOT_CALIBRATED (see `SEGMENT_SPEED_MODEL_STATUS`)."""

SEGMENT_SPEED_MODEL_STATUS: ConfigStatus = "NOT_CALIBRATED"
"""Section 11: no curve/transition/vertical segment-specific dynamics model
exists. Route time computed as distance/straight-speed is a LIMITATION, not
calibrated curve dynamics (Section 32). Never fabricate curve speeds."""


# ===========================================================================
# 4. CARRIER STRUCTURE / SHIELDING / THERMAL (Sections 0.4-0.6, 15-16)
# ===========================================================================

COMMON_CARRIER_PLATFORM = True
"""Section 0.4: ONE common compact MRT carrier platform. The carrier itself is
the transport container/pig -- NO second transport pig around it."""

LOCALIZED_SHIELDING = True
"""Section 0.5/16: localized tungsten-composite shielding around the
radioactive payload region ONLY, mission-dependent. The whole carrier is NOT
modeled as solid tungsten; shielding mass is NOT applied to non-radioactive
missions (blood/lab/pharmacy/specimens)."""

POWERED_ONBOARD_REFRIGERATION = False
"""Section 0.6/15: NO powered onboard refrigeration system on the canonical
carrier. Guideway/environmental cooling, passive payload conditioning, and
mission-specific thermal inserts remain separate legitimate authorities and
are not removed."""


# ===========================================================================
# 5. CARRIER CapEx (Section 0.7, 12)
# ===========================================================================

CARRIER_CAPEX_USD = 2_000.0
"""CONTROLLED_ENGINEERING_ASSUMPTION. Section 0.7: current controlled planning
CapEx/ceiling per MRT carrier. CORRECTS the divergent Light-MRT
`MRT_CARRIER_CAPEX_USD` default of $5,000 and the obsolete heavy
`$10,000/carrier` for the CURRENT configuration. The heavy $10,000 value
remains ONLY inside the preserved heavy-MRT scope (Section 29)."""


# ===========================================================================
# 6. GUIDEWAY GEOMETRY & CapEx (Sections 0.8-0.9, 13-14, 30)
# ===========================================================================

GUIDEWAY_EXTERNAL_WIDTH_M = 0.400
GUIDEWAY_EXTERNAL_HEIGHT_M = 0.180
"""CONTROLLED_ENGINEERING_ENVELOPE (~400 mm x 180 mm), Section 0.8. This is
the COMPLETE TWO-WAY guideway envelope. NOT manufacturer-calibrated."""

TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M = 2_500.0
"""CONTROLLED_ENGINEERING_ASSUMPTION. Section 0.9: $2,500 per linear metre of
COMPLETE TWO-WAY MRT guideway -- NOT per lane, NEVER doubled to $5,000/m for
two directions (Section 13/30). CORRECTS the divergent Light-MRT $2,000/m and
the obsolete heavy $5,000/m for the CURRENT configuration."""

GUIDEWAY_LENGTH_SEMANTICS = (
    "CAPEX_LENGTH = physical guideway centreline length. The guideway is a "
    "COMPLETE TWO-WAY assembly, so length is NOT doubled for outbound + return "
    "traffic (Section 30). $2,500/m already prices both directions."
)


# ===========================================================================
# 7. MISSION ENVELOPE / ELIGIBILITY (Sections 0.10-0.11, 8, 39)
# ===========================================================================

BULK_LINEN_ELIGIBLE = False
"""Section 0.10/39: current MRT is compact micro-logistics; bulk linen is NOT
eligible (bulky/volume mission, not merely a mass question). Never enlarge MRT
to accommodate linen."""

DEFAULT_BULKY_LOGISTICS_MODE = "MANUAL"
"""Section 0.11/8: default complementary mode for bulky/excluded logistics is
MANUAL, unless another automated mode independently wins the physical/economic
comparison. No robot/AGV/AMR is auto-inserted merely because MRT excludes a
mission (Section 0.11)."""

MRT_ELIGIBLE_MICRO_LOGISTICS = frozenset({
    "RADIOPHARMACEUTICAL_NUCLEAR", "SPECIMEN_BLOOD", "SPECIMEN", "BLOOD_PRODUCT",
    "PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY",
})
"""Section 8: compact/time-sensitive candidate streams. Final eligibility is
still gated by the mass governor AND the volume governor per mission -- mass
below 5 kg does NOT by itself imply eligibility (Section 7)."""

MRT_EXCLUDED_BULKY_LOGISTICS = frozenset({
    "CLEAN_LINEN", "LAUNDRY_CLEAN_LINEN",
})
"""Section 8/39: bulky streams excluded from current canonical MRT eligibility
(default -> MANUAL). Consistent with the pre-existing
`whole_oncology_four_architecture_optimization.LIGHT_MRT_INCOMPATIBLE_STREAMS`."""


# ===========================================================================
# 8. THE CANONICAL CONFIGURATION OBJECT (Section 5)
# ===========================================================================

@dataclass(frozen=True)
class MrtCanonicalConfiguration:
    """ONE current MRT configuration authority (Section 5). Frozen; every
    field carries a value already provenance-documented above. Consumers read
    THIS, never a scattered second literal."""

    config_name: str = CANONICAL_CONFIG_NAME

    # Mass
    max_gross_moving_mass_kg: float = MAX_GROSS_MOVING_MASS_KG
    empty_carrier_mass_target_low_kg: float = EMPTY_CARRIER_MASS_TARGET_LOW_KG
    empty_carrier_mass_target_high_kg: float = EMPTY_CARRIER_MASS_TARGET_HIGH_KG
    payload_target_low_kg: float = PAYLOAD_TARGET_LOW_KG
    payload_target_high_kg: float = PAYLOAD_TARGET_HIGH_KG

    # Geometry
    carrier_length_m: float = CARRIER_LENGTH_M
    carrier_width_m: float = CARRIER_WIDTH_M
    carrier_height_m: float = CARRIER_HEIGHT_M

    # Speed
    max_straight_speed_m_per_s: float = MAX_STRAIGHT_SPEED_M_PER_S

    # CapEx
    carrier_capex_usd: float = CARRIER_CAPEX_USD
    guideway_external_width_m: float = GUIDEWAY_EXTERNAL_WIDTH_M
    guideway_external_height_m: float = GUIDEWAY_EXTERNAL_HEIGHT_M
    two_way_guideway_capex_usd_per_m: float = TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M

    # Structure / thermal / shielding
    powered_onboard_refrigeration: bool = POWERED_ONBOARD_REFRIGERATION
    localized_shielding: bool = LOCALIZED_SHIELDING
    common_carrier_platform: bool = COMMON_CARRIER_PLATFORM

    # Mission envelope
    bulk_linen_eligible: bool = BULK_LINEN_ELIGIBLE
    default_bulky_logistics_mode: str = DEFAULT_BULKY_LOGISTICS_MODE

    # Provenance (every physical value is controlled, never calibrated)
    mass_status: ConfigStatus = "CONTROLLED_ENGINEERING_ASSUMPTION"
    geometry_status: ConfigStatus = "CONTROLLED_ENGINEERING_ENVELOPE"
    speed_status: ConfigStatus = "CONTROLLED_ENGINEERING_ASSUMPTION"
    carrier_capex_status: ConfigStatus = "CONTROLLED_ENGINEERING_ASSUMPTION"
    guideway_capex_status: ConfigStatus = "CONTROLLED_ENGINEERING_ASSUMPTION"
    guideway_geometry_status: ConfigStatus = "CONTROLLED_ENGINEERING_ENVELOPE"

    def __post_init__(self) -> None:
        # Internal consistency: empty + payload target must not exceed the
        # gross ceiling (2.0 + 3.0 == 5.0), Section 0.1/6.
        assert self.empty_carrier_mass_target_low_kg + self.payload_target_high_kg <= self.max_gross_moving_mass_kg + 1e-9
        assert self.empty_carrier_mass_target_high_kg <= self.max_gross_moving_mass_kg


CANONICAL_MRT = MrtCanonicalConfiguration()
"""The single shared canonical instance every consumer should read."""


# ===========================================================================
# 9. MASS GOVERNOR (Section 6, 38)
# ===========================================================================

MassEligibility = Literal["MRT_ELIGIBLE_BY_MASS", "MRT_INELIGIBLE_BY_MASS"]


@dataclass(frozen=True)
class MassGovernorResult:
    total_moving_mass_kg: float
    ceiling_kg: float
    eligibility: MassEligibility
    over_ceiling_kg: float
    reason: str


def enforce_mass_governor(
    *, empty_carrier_mass_kg: float, payload_mass_kg: float, shielding_insert_mass_kg: float = 0.0,
    config: MrtCanonicalConfiguration = CANONICAL_MRT,
) -> MassGovernorResult:
    """Section 6: enforce TOTAL MOVING MASS <= 5.0 kg. If
    carrier + insert/shielding + payload > 5 kg the mission is
    MRT_INELIGIBLE_BY_MASS. The carrier is NEVER auto-enlarged and the
    obsolete heavy carrier is NEVER substituted (Section 6/38) -- the mission
    simply remains eligible for another transport mode."""
    for label, value in (
        ("empty_carrier_mass_kg", empty_carrier_mass_kg),
        ("payload_mass_kg", payload_mass_kg),
        ("shielding_insert_mass_kg", shielding_insert_mass_kg),
    ):
        if value < 0 or value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{label} must be a finite, non-negative mass, got {value!r}")

    total = empty_carrier_mass_kg + payload_mass_kg + shielding_insert_mass_kg
    ceiling = config.max_gross_moving_mass_kg
    if total <= ceiling + 1e-9:
        return MassGovernorResult(
            total_moving_mass_kg=total, ceiling_kg=ceiling, eligibility="MRT_ELIGIBLE_BY_MASS",
            over_ceiling_kg=0.0, reason=f"total moving mass {total:.3f} kg <= {ceiling:.1f} kg ceiling",
        )
    return MassGovernorResult(
        total_moving_mass_kg=total, ceiling_kg=ceiling, eligibility="MRT_INELIGIBLE_BY_MASS",
        over_ceiling_kg=total - ceiling,
        reason=(
            f"total moving mass {total:.3f} kg exceeds {ceiling:.1f} kg ceiling by "
            f"{total - ceiling:.3f} kg -- carrier NOT enlarged, heavy legacy carrier NOT substituted"
        ),
    )


# ===========================================================================
# 10. PAYLOAD VOLUME / ENVELOPE GOVERNOR (Section 7)
# ===========================================================================

VolumeQualification = Literal[
    "VERIFIED", "PROJECT_SUPPLIED", "NOT_CALIBRATED", "DOES_NOT_FIT",
]


@dataclass(frozen=True)
class PayloadVolumeQualification:
    qualification: VolumeQualification
    external_length_m: float
    external_width_m: float
    external_height_m: float
    reason: str


def qualify_payload_volume(
    *, payload_length_m: float | None = None, payload_width_m: float | None = None,
    payload_height_m: float | None = None, config: MrtCanonicalConfiguration = CANONICAL_MRT,
) -> PayloadVolumeQualification:
    """Section 7: mass eligibility does NOT imply volume eligibility. The
    carrier EXTERNAL envelope is 200 x 120 x 100 mm; internal usable volume is
    NOT_CALIBRATED because wall/shield/coil thickness is not calibrated. If no
    payload dimensions are supplied -> NOT_CALIBRATED. If supplied dimensions
    exceed the EXTERNAL envelope -> DOES_NOT_FIT (they cannot possibly fit
    inside). Otherwise -> PROJECT_SUPPLIED (fits the external envelope, but the
    internal-fit cannot be VERIFIED without calibrated wall thickness). Bulk
    linen must not become eligible merely because its mass is below 5 kg."""
    ext = (config.carrier_length_m, config.carrier_width_m, config.carrier_height_m)
    if payload_length_m is None or payload_width_m is None or payload_height_m is None:
        return PayloadVolumeQualification(
            qualification="NOT_CALIBRATED", external_length_m=ext[0], external_width_m=ext[1], external_height_m=ext[2],
            reason="no payload dimensions supplied; internal usable volume NOT_CALIBRATED (wall/shield/coil thickness uncalibrated)",
        )
    for label, value in (("length", payload_length_m), ("width", payload_width_m), ("height", payload_height_m)):
        if value < 0 or value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"payload {label} must be a finite, non-negative dimension, got {value!r}")
    fits_external = (payload_length_m <= ext[0] + 1e-9 and payload_width_m <= ext[1] + 1e-9 and payload_height_m <= ext[2] + 1e-9)
    if not fits_external:
        return PayloadVolumeQualification(
            qualification="DOES_NOT_FIT", external_length_m=ext[0], external_width_m=ext[1], external_height_m=ext[2],
            reason=(
                f"payload {payload_length_m:.3f}x{payload_width_m:.3f}x{payload_height_m:.3f} m exceeds the external "
                f"envelope {ext[0]:.3f}x{ext[1]:.3f}x{ext[2]:.3f} m -- cannot fit"
            ),
        )
    return PayloadVolumeQualification(
        qualification="PROJECT_SUPPLIED", external_length_m=ext[0], external_width_m=ext[1], external_height_m=ext[2],
        reason=(
            "payload fits within the EXTERNAL envelope; internal usable fit cannot be VERIFIED without calibrated "
            "wall/shield/coil thickness (PROJECT_SUPPLIED, not VERIFIED)"
        ),
    )


# ===========================================================================
# 11. MISSION ELIGIBILITY (Sections 8, 39-41)
# ===========================================================================

@dataclass(frozen=True)
class MissionEligibilityResult:
    stream: str
    mass_result: MassGovernorResult | None
    volume_qualification: PayloadVolumeQualification | None
    mrt_eligible: bool
    fallback_mode: str
    reason: str


def resolve_mission_eligibility(
    *, stream: str, empty_carrier_mass_kg: float, payload_mass_kg: float,
    shielding_insert_mass_kg: float = 0.0,
    payload_length_m: float | None = None, payload_width_m: float | None = None,
    payload_height_m: float | None = None, config: MrtCanonicalConfiguration = CANONICAL_MRT,
) -> MissionEligibilityResult:
    """Sections 8/39-41: combine the excluded-bulky classification, the mass
    governor and the volume governor into one eligibility verdict. Bulk linen
    is excluded regardless of a contrived below-ceiling mass (Section 39).
    When ineligible, the default fallback is MANUAL (Section 0.11/8) -- no
    automated mode is auto-inserted."""
    if stream in MRT_EXCLUDED_BULKY_LOGISTICS:
        return MissionEligibilityResult(
            stream=stream, mass_result=None, volume_qualification=None, mrt_eligible=False,
            fallback_mode=config.default_bulky_logistics_mode,
            reason=f"{stream} is a bulky/excluded logistics stream (Section 8/39) -> default MANUAL fallback",
        )
    mass = enforce_mass_governor(
        empty_carrier_mass_kg=empty_carrier_mass_kg, payload_mass_kg=payload_mass_kg,
        shielding_insert_mass_kg=shielding_insert_mass_kg, config=config,
    )
    volume = qualify_payload_volume(
        payload_length_m=payload_length_m, payload_width_m=payload_width_m,
        payload_height_m=payload_height_m, config=config,
    )
    if mass.eligibility == "MRT_INELIGIBLE_BY_MASS":
        return MissionEligibilityResult(
            stream=stream, mass_result=mass, volume_qualification=volume, mrt_eligible=False,
            fallback_mode=config.default_bulky_logistics_mode, reason=mass.reason,
        )
    if volume.qualification == "DOES_NOT_FIT":
        return MissionEligibilityResult(
            stream=stream, mass_result=mass, volume_qualification=volume, mrt_eligible=False,
            fallback_mode=config.default_bulky_logistics_mode, reason=volume.reason,
        )
    return MissionEligibilityResult(
        stream=stream, mass_result=mass, volume_qualification=volume, mrt_eligible=True,
        fallback_mode="N/A", reason="mass within ceiling and volume within external envelope (mass+volume governors passed)",
    )


# ===========================================================================
# 12. ENERGY MODEL STATUS (Section 17)
# ===========================================================================

MRT_ENERGY_MODEL_STATUS = (
    "CONTROLLED_ENGINEERING_SENSITIVITY. The current MRT mission electricity is "
    "computed by mrt_transport_energy_maintenance_authority.compute_mrt_mission_energy "
    "as E = P*t (route horizontal/vertical decomposition, PHYSICS_DERIVED form) "
    "using a single lumped controlled active-power draw (MRT_MOVING_POWER_KW, LOW "
    "confidence -- NOT prototype-measured, NOT kinetic-energy-derived). No "
    "calibrated electromagnetic power model exists; the motion-power sensitivity "
    "below is transparent and explicitly NOT calibrated."
)
"""Section 17: the honest status of the MRT electricity model. Motion energy is
NOT kinetic (0.5*m*v^2) -- kinetic acceleration energy
(mrt_auxiliary_systems_authority.compute_acceleration_energy_j) is a separate,
disclosure-only lower bound and is NEVER added to the active-power electricity
below (Section 18: no double-count)."""


# ===========================================================================
# 13. CONTROLLED MRT MOTION-POWER SENSITIVITY (Section 18, 44)
# ===========================================================================

LOW_ACTIVE_POWER_KW = 0.75
BASE_ACTIVE_POWER_KW = 1.50
HIGH_ACTIVE_POWER_KW = 3.00
STRESS_ACTIVE_POWER_KW = 5.00
"""Section 18: CONTROLLED ENGINEERING SENSITIVITY cases for the TOTAL electrical
draw while moving (coil/resonant/power-electronics/levitation/controls/other
inefficiencies combined). NOT calibrated, NOT prototype-measured. The existing
mrt_transport_energy_maintenance_authority.MRT_MOVING_POWER_KW default (=0.75)
coincides with LOW."""

MOTION_POWER_SENSITIVITY_KW: Mapping[str, float] = {
    "LOW": LOW_ACTIVE_POWER_KW, "BASE": BASE_ACTIVE_POWER_KW,
    "HIGH": HIGH_ACTIVE_POWER_KW, "STRESS": STRESS_ACTIVE_POWER_KW,
}

CANONICAL_SPEED_KM_PER_H = MAX_STRAIGHT_SPEED_M_PER_S * 3.6
"""10 m/s = 36 km/h (Section 18)."""


def motion_kwh_per_carrier_km(active_power_kw: float, *, speed_km_per_h: float = CANONICAL_SPEED_KM_PER_H) -> float:
    """Section 18/44: KWH_PER_CARRIER_KM = ACTIVE_POWER_KW / speed_km_per_h.
    At 36 km/h: LOW=0.020833, BASE=0.041667, HIGH=0.083333, STRESS=0.138889
    kWh/carrier-km. Uses actual carrier-km workload where physically available.
    Kinetic acceleration energy is NOT counted again here (Section 18)."""
    if speed_km_per_h <= 0:
        raise ValueError(f"speed_km_per_h must be positive, got {speed_km_per_h!r}")
    return active_power_kw / speed_km_per_h


def motion_electricity_kwh_per_day(
    *, carrier_km_per_day: float, active_power_case: str = "BASE",
    speed_km_per_h: float = CANONICAL_SPEED_KM_PER_H,
) -> float:
    """Section 21/44: MOTION electricity only (never standby/controls/cooling).
    carrier_km_per_day is the ACTUAL workload the caller supplies -- never
    fabricated here."""
    if active_power_case not in MOTION_POWER_SENSITIVITY_KW:
        raise ValueError(f"unknown active_power_case {active_power_case!r}; expected one of {sorted(MOTION_POWER_SENSITIVITY_KW)}")
    if carrier_km_per_day < 0:
        raise ValueError(f"carrier_km_per_day must be non-negative, got {carrier_km_per_day!r}")
    rate = motion_kwh_per_carrier_km(MOTION_POWER_SENSITIVITY_KW[active_power_case], speed_km_per_h=speed_km_per_h)
    return carrier_km_per_day * rate


# ===========================================================================
# 14. NETWORK STANDBY / CONTROLS / COOLING (Section 19) -- SEPARATE from motion
# ===========================================================================

NETWORK_STANDBY_POWER_KW_STATUS: ConfigStatus = "NOT_CALIBRATED"
CONTROLS_POWER_KW_STATUS: ConfigStatus = "NOT_CALIBRATED"
GUIDEWAY_COOLING_POWER_KW_STATUS: ConfigStatus = "NOT_CALIBRATED"
"""Section 19: no calibrated standby/controls/cooling power authority exists in
the repository. These are declared SEPARATE from motion electricity and remain
NOT_CALIBRATED -- transparent controlled sensitivity values may be supplied by
a caller for a controlled comparison, but are never fabricated as canonical
constants. Motion electricity, standby, controls and cooling are added AT MOST
ONCE each (Section 19: no double-counting)."""

# Explicit double-counting-avoidance flags (Section 19 report fields).
MRT_MOTION_ELECTRICITY_SEPARATE = True
MRT_STANDBY_ELECTRICITY_SEPARATE = True
MRT_CONTROLS_ELECTRICITY_SEPARATE = True
MRT_COOLING_ELECTRICITY_SEPARATE = True
MRT_ELECTRICITY_DOUBLE_COUNTING_PRESENT = False
"""Section 19: motion / standby / controls / cooling electricity streams are
each modeled separately and summed at most once; kinetic acceleration energy is
never added on top of the active-power motion electricity. No double counting."""


# ===========================================================================
# 15. ELECTRICITY PRICE (Section 20) -- physical energy kept separate from tariff
# ===========================================================================

CONTROLLED_ELECTRICITY_TARIFF_USD_PER_KWH = 0.15
"""Section 20: a standalone CONTROLLED tariff default for controlled
comparisons only, matching the existing
mrt_transport_energy_maintenance_authority.MRT_ELECTRICITY_TARIFF_USD_PER_KWH
(=0.15) and the $0.12-$0.18/kWh range used across infrastructure_opex /
decision_pipeline / architecture_report. A PROJECT_SUPPLIED tariff must be
preserved as PROJECT_SUPPLIED. Physical energy (kWh) is produced INDEPENDENTLY
of $/kWh; annual cost = kWh * tariff."""


# ===========================================================================
# 16. ANNUAL MRT ELECTRICITY / OPEX RECONCILIATION (Sections 21-24, 45)
# ===========================================================================

@dataclass(frozen=True)
class MrtAnnualElectricityResult:
    motion_kwh_per_year: float
    standby_kwh_per_year: float | Literal["NOT_CALIBRATED"]
    controls_kwh_per_year: float | Literal["NOT_CALIBRATED"]
    cooling_kwh_per_year: float | Literal["NOT_CALIBRATED"]
    total_known_kwh_per_year: float
    total_electricity_cost_usd_per_year: float
    tariff_usd_per_kwh: float
    tariff_source: str
    unknown_components: tuple[str, ...]
    inputs: Mapping[str, object]


def compute_mrt_annual_electricity(
    *, carrier_km_per_day: float, operating_days_per_year: int, active_power_case: str = "BASE",
    standby_kwh_per_day: float | None = None, controls_kwh_per_day: float | None = None,
    cooling_kwh_per_day: float | None = None,
    tariff_usd_per_kwh: float | None = None, tariff_source: str = "CONTROLLED_SENSITIVITY_DEFAULT",
    speed_km_per_h: float = CANONICAL_SPEED_KM_PER_H,
) -> MrtAnnualElectricityResult:
    """Sections 21-24/45: transparent annual electricity reconciliation that
    EXPOSES its inputs. MOTION electricity is always computed from the
    controlled motion-power sensitivity + actual carrier-km workload. STANDBY /
    CONTROLS / COOLING are NOT_CALIBRATED and contribute to the total ONLY when
    the caller explicitly supplies a controlled-sensitivity value (never
    fabricated, never silently zero-filled). Physical kWh is kept separate from
    the tariff; cost = total_known_kWh * tariff."""
    motion_per_day = motion_electricity_kwh_per_day(
        carrier_km_per_day=carrier_km_per_day, active_power_case=active_power_case, speed_km_per_h=speed_km_per_h,
    )
    motion_year = motion_per_day * operating_days_per_year

    def _annual(component_per_day: float | None) -> float | Literal["NOT_CALIBRATED"]:
        return "NOT_CALIBRATED" if component_per_day is None else component_per_day * operating_days_per_year

    standby_year = _annual(standby_kwh_per_day)
    controls_year = _annual(controls_kwh_per_day)
    cooling_year = _annual(cooling_kwh_per_day)

    unknown: list[str] = []
    total_known = motion_year
    for name, value in (("standby", standby_year), ("controls", controls_year), ("cooling", cooling_year)):
        if value == "NOT_CALIBRATED":
            unknown.append(name)
        else:
            total_known += value  # each added AT MOST ONCE (Section 19)

    tariff = CONTROLLED_ELECTRICITY_TARIFF_USD_PER_KWH if tariff_usd_per_kwh is None else tariff_usd_per_kwh
    resolved_tariff_source = "PROJECT_SUPPLIED" if tariff_usd_per_kwh is not None and tariff_source == "PROJECT_SUPPLIED" else tariff_source

    return MrtAnnualElectricityResult(
        motion_kwh_per_year=motion_year, standby_kwh_per_year=standby_year,
        controls_kwh_per_year=controls_year, cooling_kwh_per_year=cooling_year,
        total_known_kwh_per_year=total_known, total_electricity_cost_usd_per_year=total_known * tariff,
        tariff_usd_per_kwh=tariff, tariff_source=resolved_tariff_source, unknown_components=tuple(unknown),
        inputs={
            "carrier_km_per_day": carrier_km_per_day, "operating_days_per_year": operating_days_per_year,
            "active_power_case": active_power_case, "active_power_kw": MOTION_POWER_SENSITIVITY_KW[active_power_case],
            "speed_km_per_h": speed_km_per_h, "standby_kwh_per_day": standby_kwh_per_day,
            "controls_kwh_per_day": controls_kwh_per_day, "cooling_kwh_per_day": cooling_kwh_per_day,
        },
    )


# ===========================================================================
# 17. MRT MAINTENANCE OPEX STATUS (Section 22)
# ===========================================================================

MRT_MAINTENANCE_MODEL_STATUS = (
    "CONTROLLED_PLANNING_ASSUMPTION. Carrier maintenance = 10%/year of the "
    "canonical $2,000 carrier CapEx (=$200/carrier-year); guideway maintenance = "
    "10%/year of INSTALLED guideway CapEx -- both owned by "
    "mrt_transport_energy_maintenance_authority (compute_mrt_carrier_annual_maintenance_usd "
    "/ compute_mrt_guideway_annual_maintenance_usd). Kept SEPARATE from "
    "electricity (Section 22). Not vendor-calibrated."
)
"""Section 22: maintenance provenance. Reuses the existing controlled 10%/year
Light-MRT maintenance authority (now on the canonical $2,000 carrier CapEx);
never fabricated as a calibrated number; never merged with electricity."""

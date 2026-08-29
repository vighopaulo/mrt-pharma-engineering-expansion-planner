"""Equipment OPEX Authority — canonical annual-OPEX driver/monetary authority.

PURPOSE (Sections 0-2 of the Equipment OPEX Authority brief):

    PATIENT / OPERATIONAL DEMAND
      -> EQUIPMENT WORKLOAD
      -> EQUIPMENT UTILIZATION / DUTY
      -> PHYSICAL OPEX DRIVERS
      -> EVIDENCE-BASED UNIT COSTS
      -> ANNUAL OPEX COMPONENTS.

This module is the single canonical authority that COMPOSES existing physical
duty/energy authorities into componentized annual OPEX for three equipment
classes — SCANNER, CYCLOTRON, GENERATOR — while preserving the governing
distinctions (Section 2):

    EQUIPMENT SPECIFICATION  != ANNUAL OPEX
    PHYSICAL OPEX DRIVER     != MONETARY UNIT COST
    CONNECTED LOAD           != OPERATING POWER != ANNUAL ENERGY
    PURCHASE CAPEX           != MAINTENANCE OPEX
    PATIENT DEMAND -> WORKLOAD -> UTILIZATION -> OPEX (never reversed)
    EXCESS CAPACITY          == HEADROOM (never additional revenue)

It DOES NOT:
  - replace `equipment_energy_opex.py` (it composes it — Section 3/34);
  - re-derive any kW / kWh / duty-cycle physics (Section 3/47);
  - fabricate power, cycle duration, EOB activity, consumable rates, service
    prices, or generator prices (Section 28 — NO ZERO-FILLING);
  - back-derive facility kW from beam current or EOB activity (Section 15/38);
  - mutate patient demand, decay physics, production physics, or the calendar
    (Sections 34/47);
  - integrate the Part 3E optimizer (Section 30/42).

MONETARY DOCTRINE (Sections 5-7, OG-OPEX-1):

    OPEX_annual = OPEX_spec_derived + OPEX_commercial + OPEX_site_specific

The PHYSICAL DRIVER and the MONETARY UNIT COST carry SEPARATE evidence
classes; the weakest of the two governs a component's calculation status
(Section 7). A component's `annual_cost_usd` is `None` (not 0.0) whenever
either the physical quantity or the unit cost is unavailable (Section 28).
`known_annual_opex_subtotal_usd` sums ONLY components with a genuine calculated
dollar value; `total_annual_opex_status` remains `NOT_CALIBRATED` while any
component is uncalibrated (Sections 12/26 — known subtotal may be numeric while
total is NOT_CALIBRATED).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from cyclotron_catalog import CyclotronCatalogModel
from equipment_energy_opex import EquipmentDailyEnergyResult
from generator_catalog import (
    GeneratorCatalogModel,
    FacilityGeneratorInstance,
)
from healthcare_integration import (
    ENERGY_SPECIFICATION_NOT_CALIBRATED,
    EconomicComparabilityStatus,
)

# Section 4: the OPEX authority reports THREE equipment classes independently.
# `healthcare_integration.EquipmentClass` is an energy-oriented enum
# (CYCLOTRON/SCANNER/MRT_CARRIER/MRT_GUIDEWAY) that intentionally has no
# GENERATOR member — a passive Mo-99/Tc-99m generator is not an electrically
# metered facility asset. This authority therefore owns its own broader class
# literal rather than forcing generators into the energy enum (no class
# collapsing).
EquipmentOpexClass = Literal["SCANNER", "CYCLOTRON", "GENERATOR"]

# ---------------------------------------------------------------------------
# Section 7 — Evidence hierarchy (REUSED, not reinvented).
# The repository already carries two conceptually-equivalent calibration
# vocabularies (equipment catalogs use lowercase `calibration_status`;
# economic authorities use UPPERCASE tokens). This module maps both onto the
# single reference ladder below WITHOUT introducing competing vocabulary; the
# tokens are ordered strongest -> weakest so that "weakest component governs"
# (Section 7) is a simple max-index comparison.
# ---------------------------------------------------------------------------

EvidenceStatus = Literal[
    "SITE_CALIBRATED",
    "MANUFACTURER_SPECIFIED",
    "COMMERCIAL_QUOTE",
    "LITERATURE_DERIVED",
    "MODELED_ESTIMATE",
    "CONTROLLED_ASSUMPTION",
    "NOT_CALIBRATED",
    "NOT_AVAILABLE",
]

_EVIDENCE_RANK: dict[str, int] = {
    "SITE_CALIBRATED": 0,
    "MANUFACTURER_SPECIFIED": 1,
    "COMMERCIAL_QUOTE": 2,
    "LITERATURE_DERIVED": 3,
    "MODELED_ESTIMATE": 4,
    "CONTROLLED_ASSUMPTION": 5,
    "NOT_CALIBRATED": 6,
    "NOT_AVAILABLE": 7,
}

# Mapping of the repo's existing lowercase catalog `calibration_status` tokens
# onto the reference ladder (Section 7 — "reuse existing terminology").
_CATALOG_STATUS_TO_EVIDENCE: dict[str, EvidenceStatus] = {
    "site_calibrated": "SITE_CALIBRATED",
    "manufacturer_calibrated": "MANUFACTURER_SPECIFIED",
    "commercial_quote": "COMMERCIAL_QUOTE",
    "contract": "COMMERCIAL_QUOTE",
    "literature_calibrated": "LITERATURE_DERIVED",
    "modeled": "MODELED_ESTIMATE",
    "controlled_assumption": "CONTROLLED_ASSUMPTION",
    "not_calibrated": "NOT_CALIBRATED",
    "not_available": "NOT_AVAILABLE",
}


def map_catalog_status_to_evidence(catalog_status: str) -> EvidenceStatus:
    """Section 7: normalize a catalog `calibration_status` token onto the
    reference evidence ladder — never inventing a stronger class than the
    catalog actually asserts."""
    return _CATALOG_STATUS_TO_EVIDENCE.get(catalog_status.strip().lower(), "NOT_CALIBRATED")


def weakest_evidence(*statuses: str) -> EvidenceStatus:
    """Section 7: the strongest input must not falsely promote the whole
    result — the WEAKEST evidence class governs."""
    normalized = [s if s in _EVIDENCE_RANK else map_catalog_status_to_evidence(s) for s in statuses if s]
    if not normalized:
        return "NOT_AVAILABLE"
    return max(normalized, key=lambda s: _EVIDENCE_RANK[s])  # type: ignore[return-value]


def _is_calculable_evidence(status: EvidenceStatus) -> bool:
    """A component yields a genuine dollar value only if evidence is at least
    a CONTROLLED_ASSUMPTION (Section 7/28) — NOT_CALIBRATED / NOT_AVAILABLE
    never produce a fabricated number."""
    return _EVIDENCE_RANK[status] <= _EVIDENCE_RANK["CONTROLLED_ASSUMPTION"]


# ---------------------------------------------------------------------------
# Section 5/35 — Result layering.
# ---------------------------------------------------------------------------

ComponentCalculationStatus = Literal[
    "CALCULATED",
    "PHYSICAL_QUANTITY_NOT_CALIBRATED",
    "UNIT_COST_NOT_CALIBRATED",
    "NOT_CALIBRATED",
    "NOT_APPLICABLE",
]

TotalOpexStatus = Literal["CALIBRATED", "PARTIALLY_CALIBRATED", "NOT_CALIBRATED"]


@dataclass(frozen=True)
class EquipmentOpexComponent:
    """Section 6/35: one physically-applicable recurring OPEX component.

    The PHYSICAL DRIVER (`physical_quantity` + `physical_evidence_status`) and
    the MONETARY UNIT COST (`unit_cost_usd` + `unit_cost_basis`) are tracked
    SEPARATELY (Section 7). `annual_cost_usd` is `None` — never 0.0 — whenever
    either side is uncalibrated (Section 28)."""

    component_type: str
    physical_quantity: float | None
    physical_unit: str | None
    physical_evidence_status: EvidenceStatus
    unit_cost_usd: float | None
    unit_cost_basis: EvidenceStatus
    annual_cost_usd: float | None
    calculation_status: ComponentCalculationStatus
    provenance: str
    limitations: tuple[str, ...] = ()

    @property
    def is_calculated(self) -> bool:
        return self.calculation_status == "CALCULATED" and self.annual_cost_usd is not None


@dataclass(frozen=True)
class EquipmentOpexResult:
    """Section 5/26/35: a layered, honest annual-OPEX result for one piece of
    equipment. `known_annual_opex_subtotal_usd` sums ONLY calculated
    components; `total_annual_opex_status` stays `NOT_CALIBRATED` while any
    applicable component is uncalibrated — the known subtotal may be numeric
    while the total is not (Section 12/26)."""

    equipment_type: EquipmentOpexClass
    equipment_id: str
    catalog_model_id: str | None
    planning_horizon_days: int | None
    components: tuple[EquipmentOpexComponent, ...]
    known_annual_opex_subtotal_usd: float
    total_annual_opex_usd: float | None
    total_annual_opex_status: TotalOpexStatus
    comparability_status: EconomicComparabilityStatus
    limitations: tuple[str, ...] = ()

    @property
    def uncalibrated_component_count(self) -> int:
        return sum(1 for c in self.components if not c.is_calculated and c.calculation_status != "NOT_APPLICABLE")

    @property
    def applicable_component_count(self) -> int:
        return sum(1 for c in self.components if c.calculation_status != "NOT_APPLICABLE")


# ---------------------------------------------------------------------------
# Section 6 — Component factory (single no-zero-fill choke point).
# ---------------------------------------------------------------------------


def build_opex_component(
    *,
    component_type: str,
    physical_quantity: float | None,
    physical_unit: str | None,
    physical_evidence_status: EvidenceStatus,
    unit_cost_usd: float | None,
    unit_cost_basis: EvidenceStatus,
    provenance: str,
    limitations: Sequence[str] = (),
) -> EquipmentOpexComponent:
    """Section 6-7/28: the ONE place that decides whether a component yields a
    dollar value. A dollar value is produced ONLY when BOTH the physical
    quantity and the unit cost are present AND each carries at least
    CONTROLLED_ASSUMPTION evidence. Otherwise the annual cost is `None` (never
    0.0) and the calculation status names exactly which side is missing."""
    phys_ok = physical_quantity is not None and _is_calculable_evidence(physical_evidence_status)
    cost_ok = unit_cost_usd is not None and _is_calculable_evidence(unit_cost_basis)

    if phys_ok and cost_ok:
        annual = physical_quantity * unit_cost_usd  # type: ignore[operator]
        status: ComponentCalculationStatus = "CALCULATED"
    elif not phys_ok and not cost_ok:
        annual = None
        status = "NOT_CALIBRATED"
    elif not phys_ok:
        annual = None
        status = "PHYSICAL_QUANTITY_NOT_CALIBRATED"
    else:
        annual = None
        status = "UNIT_COST_NOT_CALIBRATED"

    return EquipmentOpexComponent(
        component_type=component_type,
        physical_quantity=physical_quantity,
        physical_unit=physical_unit,
        physical_evidence_status=physical_evidence_status,
        unit_cost_usd=unit_cost_usd,
        unit_cost_basis=unit_cost_basis,
        annual_cost_usd=annual,
        calculation_status=status,
        provenance=provenance,
        limitations=tuple(limitations),
    )


def _assemble_result(
    *,
    equipment_type: EquipmentOpexClass,
    equipment_id: str,
    catalog_model_id: str | None,
    planning_horizon_days: int | None,
    components: Sequence[EquipmentOpexComponent],
    limitations: Sequence[str] = (),
) -> EquipmentOpexResult:
    """Section 12/26/27: fold components into a layered result. Known subtotal
    sums calculated components only; total status/comparability degrade to the
    weakest applicable component (Section 7/27)."""
    comps = tuple(components)
    known_subtotal = float(sum(c.annual_cost_usd for c in comps if c.is_calculated))  # type: ignore[misc]

    applicable = [c for c in comps if c.calculation_status != "NOT_APPLICABLE"]
    uncalibrated = [c for c in applicable if not c.is_calculated]

    if not applicable:
        total_status: TotalOpexStatus = "NOT_CALIBRATED"
        comparability: EconomicComparabilityStatus = "NOT_COMPARABLE_DUE_TO_UNCALIBRATED_ENERGY"
    elif not uncalibrated:
        total_status = "CALIBRATED"
        comparability = "FULLY_CALIBRATED"
    elif len(uncalibrated) < len(applicable):
        total_status = "NOT_CALIBRATED"  # any unknown component -> total not calibrated (Section 12/26)
        comparability = "PARTIALLY_CALIBRATED"
    else:
        total_status = "NOT_CALIBRATED"
        comparability = "NOT_COMPARABLE_DUE_TO_UNCALIBRATED_ENERGY"

    # Total dollars are only ever reported when EVERY applicable component is
    # calculated (Section 26 — never present an incomplete total as complete).
    total_usd = known_subtotal if total_status == "CALIBRATED" else None

    return EquipmentOpexResult(
        equipment_type=equipment_type,
        equipment_id=equipment_id,
        catalog_model_id=catalog_model_id,
        planning_horizon_days=planning_horizon_days,
        components=comps,
        known_annual_opex_subtotal_usd=known_subtotal,
        total_annual_opex_usd=total_usd,
        total_annual_opex_status=total_status,
        comparability_status=comparability,
        limitations=tuple(limitations),
    )


# ---------------------------------------------------------------------------
# Section 25 — Annualization (explicit, never blind).
# ---------------------------------------------------------------------------

DEFAULT_ANNUALIZATION_DAYS = 365.0


def annualize_horizon_quantity(
    *, observed_quantity: float, horizon_days: int, representative: bool,
) -> tuple[float | None, str]:
    """Section 25: annualize a horizon-period physical quantity ONLY when the
    modeled horizon is representative. An unrepresentative/short/commissioning
    horizon returns `None` + a status so the caller reports horizon-period
    OPEX instead of a misleading annual figure — never a blind x365/N."""
    if horizon_days <= 0:
        return None, "HORIZON_INVALID"
    if not representative:
        return None, "HORIZON_NOT_REPRESENTATIVE_REPORT_PERIOD_ONLY"
    return observed_quantity * (DEFAULT_ANNUALIZATION_DAYS / float(horizon_days)), "ANNUALIZED_REPRESENTATIVE"


# ---------------------------------------------------------------------------
# Section 10-12 — SCANNER OPEX.
# ---------------------------------------------------------------------------


def build_scanner_energy_component(
    *,
    daily_energy_results: Sequence[EquipmentDailyEnergyResult],
    horizon_days: int,
    electricity_tariff_usd_per_kwh: float,
    tariff_basis: EvidenceStatus = "CONTROLLED_ASSUMPTION",
    representative_horizon: bool = True,
    generic_fallback_annual_kwh: float = 0.0,
) -> EquipmentOpexComponent:
    """Section 11/28: scanner energy composes the schedule-derived state-time
    authority. If catalog power is `NOT_CALIBRATED`, the energy authority
    yields `calculated_energy_kwh = 0.0` with a NON-`CALIBRATED_FOR_ENERGY`
    status — this module preserves that as a `PHYSICAL_QUANTITY_NOT_CALIBRATED`
    energy component (energy quantity NOT_CALIBRATED, never a fabricated 0 kWh
    billed as $0). The tariff itself is a valid site unit cost awaiting a
    physical consumption it can multiply (Section 9)."""
    calc_kwh = sum(r.calculated_energy_kwh for r in daily_energy_results)
    uncalibrated_minutes = sum(r.uncalibrated_state_minutes for r in daily_energy_results)
    all_calibrated = bool(daily_energy_results) and all(
        r.calibration_status == "CALIBRATED_FOR_ENERGY" for r in daily_energy_results
    )

    if not all_calibrated:
        # Power is NOT_CALIBRATED -> the physical energy quantity is unknown.
        # Never 0 kWh, never $0 (Section 10/11/28). The uncalibrated duty
        # minutes are preserved on the component's limitations for traceability.
        return build_opex_component(
            component_type="ELECTRICITY",
            physical_quantity=None,
            physical_unit="kWh/yr",
            physical_evidence_status="NOT_CALIBRATED",
            unit_cost_usd=electricity_tariff_usd_per_kwh,
            unit_cost_basis=tariff_basis,
            provenance="equipment_energy_opex schedule-derived duty; catalog active_power_kw NOT_CALIBRATED",
            limitations=(
                f"{ENERGY_SPECIFICATION_NOT_CALIBRATED}: scanner active/standby power kW absent from catalog",
                f"uncalibrated_state_minutes={uncalibrated_minutes:.1f} over horizon (duty exists; power does not)",
                "energy dollars NOT_CALIBRATED — never billed as 0 kWh/$0",
            ),
        )

    horizon_annual_kwh, annualization_status = annualize_horizon_quantity(
        observed_quantity=calc_kwh, horizon_days=horizon_days, representative=representative_horizon,
    )
    return build_opex_component(
        component_type="ELECTRICITY",
        physical_quantity=horizon_annual_kwh,
        physical_unit="kWh/yr",
        physical_evidence_status="SITE_CALIBRATED",
        unit_cost_usd=electricity_tariff_usd_per_kwh,
        unit_cost_basis=tariff_basis,
        provenance=f"equipment_energy_opex schedule-derived, {annualization_status}",
        limitations=() if horizon_annual_kwh is not None else ("energy annualization suppressed (horizon not representative)",),
    )


def build_scanner_service_component() -> EquipmentOpexComponent:
    """Section 12/G/28: no defensible per-model scanner service/maintenance
    price exists (catalog economics all NOT_CALIBRATED). Reported as an
    unknown component — never $0."""
    return build_opex_component(
        component_type="SERVICE_CONTRACT",
        physical_quantity=1.0,
        physical_unit="service-year",
        physical_evidence_status="MODELED_ESTIMATE",
        unit_cost_usd=None,
        unit_cost_basis="NOT_CALIBRATED",
        provenance="scanner_equipment_catalog economics: annual_service_opex NOT_CALIBRATED (all models)",
        limitations=("no defensible per-model scanner service price located",),
    )


def compute_scanner_opex(
    *,
    scanner_id: str,
    catalog_model_id: str,
    daily_energy_results: Sequence[EquipmentDailyEnergyResult],
    horizon_days: int,
    electricity_tariff_usd_per_kwh: float,
    tariff_basis: EvidenceStatus = "CONTROLLED_ASSUMPTION",
    representative_horizon: bool = True,
    extra_components: Sequence[EquipmentOpexComponent] = (),
) -> EquipmentOpexResult:
    """Section 10-12/H: layered scanner OPEX. Energy composes the existing
    schedule-derived authority; service remains NOT_CALIBRATED. No patient
    identity is required (Section 19)."""
    energy = build_scanner_energy_component(
        daily_energy_results=daily_energy_results,
        horizon_days=horizon_days,
        electricity_tariff_usd_per_kwh=electricity_tariff_usd_per_kwh,
        tariff_basis=tariff_basis,
        representative_horizon=representative_horizon,
    )
    service = build_scanner_service_component()
    components = [energy, service, *extra_components]
    return _assemble_result(
        equipment_type="SCANNER",
        equipment_id=scanner_id,
        catalog_model_id=catalog_model_id,
        planning_horizon_days=horizon_days,
        components=components,
        limitations=(
            "scanner model power NOT_CALIBRATED -> energy dollars NOT_CALIBRATED",
            "scanner service/maintenance price NOT_CALIBRATED",
            "staffing owned by labor authority — NOT included here (Section 22)",
        ),
    )


# ---------------------------------------------------------------------------
# Section 13-17 — CYCLOTRON OPEX.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CyclotronUtilization:
    """Section 14: physical utilization drivers derived from the ACTUAL
    production schedule — never from revenue, budget, or installed capacity.
    Beam current is NOT a facility electrical load (Section 15)."""

    cyclotron_id: str
    production_cycles: int
    beam_on_minutes: float
    beam_on_hours: float
    scheduled_production_days: int
    driver_evidence_status: EvidenceStatus = "SITE_CALIBRATED"  # schedule-derived


def derive_cyclotron_utilization_from_cycles(
    *,
    cyclotron_id: str,
    cycle_intervals_minutes: Sequence[tuple[float, float]],
    scheduled_production_days: int,
) -> CyclotronUtilization:
    """Section 14/24: fold `ProductionCycleRecord` (start/end minutes) intervals
    into beam-on utilization. The DEMAND -> CYCLES direction is preserved; this
    consumes the already-scheduled cycles, it does not create demand."""
    beam_on_minutes = sum(max(0.0, end - start) for start, end in cycle_intervals_minutes)
    return CyclotronUtilization(
        cyclotron_id=cyclotron_id,
        production_cycles=len(cycle_intervals_minutes),
        beam_on_minutes=beam_on_minutes,
        beam_on_hours=beam_on_minutes / 60.0,
        scheduled_production_days=scheduled_production_days,
    )


def build_cyclotron_energy_component(
    utilization: CyclotronUtilization,
    *,
    electricity_tariff_usd_per_kwh: float,
    facility_power_kw: float | None = None,
    facility_power_basis: EvidenceStatus = "NOT_CALIBRATED",
    tariff_basis: EvidenceStatus = "CONTROLLED_ASSUMPTION",
) -> EquipmentOpexComponent:
    """Section 15/38: cyclotron energy needs a DEFENSIBLE facility kW. Beam-on
    HOURS are known (utilization driver), but the catalog carries NO facility
    electrical load, so `facility_power_kw` defaults to `None` and energy stays
    NOT_CALIBRATED. Energy is NEVER manufactured from beam current or EOB
    activity."""
    if facility_power_kw is None or not _is_calculable_evidence(facility_power_basis):
        return build_opex_component(
            component_type="ELECTRICITY",
            physical_quantity=None,
            physical_unit="kWh/yr",
            physical_evidence_status="NOT_CALIBRATED",
            unit_cost_usd=electricity_tariff_usd_per_kwh,
            unit_cost_basis=tariff_basis,
            provenance="beam-on hours known (schedule-derived); facility kW absent from cyclotron catalog",
            limitations=(
                f"{ENERGY_SPECIFICATION_NOT_CALIBRATED}: magnet/RF/vacuum/cooling facility kW not in catalog",
                "beam current is NOT facility electrical load (Section 15) — kW not back-derived",
                f"beam_on_hours={utilization.beam_on_hours:.2f} preserved as driver, energy $ NOT_CALIBRATED",
            ),
        )
    annual_kwh = utilization.beam_on_hours * facility_power_kw
    return build_opex_component(
        component_type="ELECTRICITY",
        physical_quantity=annual_kwh,
        physical_unit="kWh/yr",
        physical_evidence_status=facility_power_basis,
        unit_cost_usd=electricity_tariff_usd_per_kwh,
        unit_cost_basis=tariff_basis,
        provenance="beam-on hours (schedule-derived) x supplied facility kW",
    )


def build_cyclotron_consumable_component(
    utilization: CyclotronUtilization,
    *,
    consumable_type: str = "TARGETS",
    unit_cost_usd: float | None = None,
    unit_cost_basis: EvidenceStatus = "NOT_CALIBRATED",
    uses_per_cycle: float = 1.0,
) -> EquipmentOpexComponent:
    """Section 16: production-cycle count is a valid consumable-use DRIVER, but
    the consumable unit cost is absent -> monetary OPEX NOT_CALIBRATED. One
    cycle is never converted to an arbitrary dollar value."""
    return build_opex_component(
        component_type=consumable_type,
        physical_quantity=utilization.production_cycles * uses_per_cycle,
        physical_unit="uses/horizon",
        physical_evidence_status="SITE_CALIBRATED",  # cycle count is schedule-derived
        unit_cost_usd=unit_cost_usd,
        unit_cost_basis=unit_cost_basis,
        provenance="production cycles (schedule-derived) x uses/cycle",
        limitations=() if unit_cost_usd is not None else ("consumable unit cost NOT_CALIBRATED — driver preserved, $ withheld",),
    )


def build_cyclotron_service_component(
    *,
    unit_cost_usd: float | None = None,
    unit_cost_basis: EvidenceStatus = "NOT_CALIBRATED",
) -> EquipmentOpexComponent:
    """Section 17: no real service contract price exists. A %-of-CapEx rule (if
    ever used) is a CONTROLLED_ASSUMPTION, never MANUFACTURER_SPECIFIED — and
    none is applied here by default."""
    return build_opex_component(
        component_type="SERVICE_CONTRACT",
        physical_quantity=1.0,
        physical_unit="service-year",
        physical_evidence_status="MODELED_ESTIMATE",
        unit_cost_usd=unit_cost_usd,
        unit_cost_basis=unit_cost_basis,
        provenance="no defensible cyclotron service price; %-of-CapEx would be CONTROLLED_ASSUMPTION only",
        limitations=("cyclotron service/maintenance price NOT_CALIBRATED",),
    )


def compute_cyclotron_opex(
    *,
    utilization: CyclotronUtilization,
    catalog_model: CyclotronCatalogModel | None,
    horizon_days: int,
    electricity_tariff_usd_per_kwh: float,
    facility_power_kw: float | None = None,
    facility_power_basis: EvidenceStatus = "NOT_CALIBRATED",
    tariff_basis: EvidenceStatus = "CONTROLLED_ASSUMPTION",
    extra_components: Sequence[EquipmentOpexComponent] = (),
) -> EquipmentOpexResult:
    """Section 13-17: layered cyclotron OPEX. Utilization is real; energy,
    consumables, and service remain NOT_CALIBRATED absent monetary evidence.
    Production CALIBRATION status (a workload dimension) is independent of OPEX
    calibration (Section 13/38) and is only surfaced as a limitation note."""
    energy = build_cyclotron_energy_component(
        utilization,
        electricity_tariff_usd_per_kwh=electricity_tariff_usd_per_kwh,
        facility_power_kw=facility_power_kw,
        facility_power_basis=facility_power_basis,
        tariff_basis=tariff_basis,
    )
    consumable = build_cyclotron_consumable_component(utilization)
    service = build_cyclotron_service_component()
    components = [energy, consumable, service, *extra_components]

    prod_note = (
        f"production_calibration_status={catalog_model.production_calibration_status}"
        if catalog_model is not None else "catalog model not supplied"
    )
    return _assemble_result(
        equipment_type="CYCLOTRON",
        equipment_id=utilization.cyclotron_id,
        catalog_model_id=(catalog_model.catalog_model_id if catalog_model is not None else None),
        planning_horizon_days=horizon_days,
        components=components,
        limitations=(
            "cyclotron facility power kW NOT_CALIBRATED -> energy $ NOT_CALIBRATED",
            "cyclotron consumable/service unit costs NOT_CALIBRATED",
            "production activity calibration is a WORKLOAD dimension, independent of OPEX $ (Section 13/38)",
            f"{prod_note}",
            "staffing (operator/radiochemist/QC) owned by labor authority — NOT included (Section 22)",
        ),
    )


# ---------------------------------------------------------------------------
# Section 18-21 — GENERATOR OPEX.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeneratorReplacementSchedule:
    """Section 19: physical replacement schedule derived from useful life +
    horizon. Units (generators/horizon) are derivable even when procurement
    dollars are NOT_CALIBRATED (Section 20)."""

    catalog_model_id: str
    useful_life_days: float | None
    horizon_days: int
    generators_required: int | None
    schedule_status: Literal["CALCULABLE", "NOT_CALIBRATED"]
    driver_evidence_status: EvidenceStatus
    limitations: tuple[str, ...] = ()


def derive_generator_replacement_schedule(
    *,
    model: GeneratorCatalogModel,
    horizon_days: int,
    concurrent_generators_required: int = 1,
) -> GeneratorReplacementSchedule:
    """Section 19: Tc-99m demand -> required activity -> elution requirement ->
    generator utilization -> replacement schedule. Here we derive the
    horizon-level replacement COUNT from useful life (the replacement interval
    driver); the concurrent-generator multiplier lets callers scale by the
    demand-derived elution requirement without re-deriving decay physics."""
    life = model.useful_life_days
    if life is None or life <= 0.0:
        return GeneratorReplacementSchedule(
            catalog_model_id=model.catalog_model_id,
            useful_life_days=life,
            horizon_days=horizon_days,
            generators_required=None,
            schedule_status="NOT_CALIBRATED",
            driver_evidence_status="NOT_CALIBRATED",
            limitations=("useful_life_days NOT_CALIBRATED for this model",),
        )
    # Ceiling of horizon/life, scaled by the number of concurrently-required
    # generators. A longer horizon can never reduce the replacement count
    # (Section 41 monotonicity).
    replacements_per_line = -(-horizon_days // int(life)) if horizon_days > 0 else 0
    generators_required = max(0, replacements_per_line) * max(1, concurrent_generators_required)
    life_status = model.field_provenance.get("useful_life_days")
    driver_evidence = (
        map_catalog_status_to_evidence(life_status.calibration_status)
        if life_status is not None else "LITERATURE_DERIVED"
    )
    return GeneratorReplacementSchedule(
        catalog_model_id=model.catalog_model_id,
        useful_life_days=life,
        horizon_days=horizon_days,
        generators_required=generators_required,
        schedule_status="CALCULABLE",
        driver_evidence_status=driver_evidence,
    )


def build_generator_procurement_component(
    schedule: GeneratorReplacementSchedule,
    *,
    unit_purchase_price_usd: float | None = None,
    price_basis: EvidenceStatus = "NOT_CALIBRATED",
) -> EquipmentOpexComponent:
    """Section 20: separate GENERATORS/HORIZON from $/HORIZON. Replacement
    schedule may be CALCULABLE while procurement dollars stay NOT_CALIBRATED —
    no speculative market price is inserted."""
    qty = float(schedule.generators_required) if schedule.generators_required is not None else None
    phys_status: EvidenceStatus = schedule.driver_evidence_status if schedule.schedule_status == "CALCULABLE" else "NOT_CALIBRATED"
    return build_opex_component(
        component_type="GENERATOR_PROCUREMENT",
        physical_quantity=qty,
        physical_unit="generators/horizon",
        physical_evidence_status=phys_status,
        unit_cost_usd=unit_purchase_price_usd,
        unit_cost_basis=price_basis,
        provenance="useful-life-derived replacement count x purchase price",
        limitations=() if unit_purchase_price_usd is not None else ("generator purchase price NOT_CALIBRATED — schedule in units only",),
    )


def compute_generator_opex(
    *,
    instance: FacilityGeneratorInstance,
    model: GeneratorCatalogModel,
    horizon_days: int,
    concurrent_generators_required: int = 1,
    unit_purchase_price_usd: float | None = None,
    price_basis: EvidenceStatus = "NOT_CALIBRATED",
    extra_components: Sequence[EquipmentOpexComponent] = (),
) -> tuple[EquipmentOpexResult, GeneratorReplacementSchedule]:
    """Section 18-21: layered generator OPEX. A generator behaves as recurring
    PROCUREMENT, not permanent capital. Replacement schedule derivable in
    units; procurement dollars NOT_CALIBRATED absent a price. Generator decay
    physics is untouched (Section 19/47)."""
    schedule = derive_generator_replacement_schedule(
        model=model, horizon_days=horizon_days, concurrent_generators_required=concurrent_generators_required,
    )
    procurement = build_generator_procurement_component(
        schedule, unit_purchase_price_usd=unit_purchase_price_usd, price_basis=price_basis,
    )
    # Section 21: passive lead-shielded column generators require no meaningful
    # electrical input -> energy is explicitly NOT_APPLICABLE (never a
    # fabricated $0 that would inflate the known subtotal or falsely improve
    # comparability). If a model ever declares it needs power, energy is
    # NOT_CALIBRATED (unknown), never zero.
    if not model.requires_electrical_power:
        energy = EquipmentOpexComponent(
            component_type="ELECTRICITY",
            physical_quantity=0.0,
            physical_unit="kWh/yr",
            physical_evidence_status="MANUFACTURER_SPECIFIED",
            unit_cost_usd=None,
            unit_cost_basis="NOT_APPLICABLE",
            annual_cost_usd=None,
            calculation_status="NOT_APPLICABLE",
            provenance="passive lead-shielded column generator requires no meaningful electrical input",
            limitations=("requires_electrical_power=false — energy NOT_APPLICABLE (Section 21)",),
        )
    else:
        energy = build_opex_component(
            component_type="ELECTRICITY",
            physical_quantity=None,
            physical_unit="kWh/yr",
            physical_evidence_status="NOT_CALIBRATED",
            unit_cost_usd=None,
            unit_cost_basis="NOT_CALIBRATED",
            provenance="generator declares electrical power requirement; kW NOT_CALIBRATED",
            limitations=("generator electrical power NOT_CALIBRATED — never $0",),
        )

    components = [procurement, energy, *extra_components]
    result = _assemble_result(
        equipment_type="GENERATOR",
        equipment_id=instance.instance_id,
        catalog_model_id=model.catalog_model_id,
        planning_horizon_days=horizon_days,
        components=components,
        limitations=(
            "generator behaves as recurring PROCUREMENT, not permanent CapEx (Section 18)",
            f"replacement schedule status={schedule.schedule_status}",
            "generator procurement/QC/disposal/logistics dollars NOT_CALIBRATED absent evidence",
            "elution/decay physics untouched — consumed, not rewritten (Section 19/47)",
        ),
    )
    return result, schedule

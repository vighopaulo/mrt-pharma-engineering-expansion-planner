"""Mo-99/Tc-99m Generator Economic Calibration.

GOVERNANCE (correction sections 11-18): `generator_catalog.py`/
`generator_equipment_catalog.json` are UNCHANGED -- their honest
`NOT_CALIBRATED` `replacement_cost_per_cycle`/`purchase_capex` disclosures
(no defensible procurement evidence located, both live-fetch attempts
returned HTTP 404) are preserved exactly. This module adds a SEPARATE,
transparent controlled economic layer on top, mirroring how
`patient_economics.CONTROLLED_SCAN_REVENUE_ASSUMPTION` composes with the
audited nuclear scan-revenue value without altering `models.py`.

CLASSIFICATION (section 12): the recurring generator delivery/replacement
cost is a SUPPLY/OPERATING item (consumable, decays away, replaced on a
clinical cadence) -- NEVER durable cyclotron-like purchase CapEx. No function
in this module returns a non-zero CapEx for this recurring line; durable
local infrastructure/shielding/installation remain modeled separately (see
`oncology_pet_spect_scenario.evaluate_spect_economics`'s
`generator_purchase_capex`/`generator_installation_capex`, untouched here).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from generator_catalog import GeneratorCatalogModel

CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_USD = 3500.0
"""Section 11: CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_2026 -- a project
benchmark assumption, applied uniformly to the initial catalog models unless
a model-specific calibrated value already exists in `generator_catalog.json`
(none currently does -- all three are honestly NOT_CALIBRATED)."""
CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_PROVENANCE = "CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_2026"

SUPPLY_CADENCE_DAYS_PER_YEAR_CONVENTION = 364.0
"""Section 14: a disclosed 52-week (364-day) supply-cadence convention --
distinct from the 365-day calendar year used elsewhere in the repository --
chosen because it reconciles the weekly (364/7=52) and 14-day (364/14=26)
controlled examples EXACTLY. Never silently conflated with a 365-day year."""

DeliveryCostBasis = Literal["MODEL_SPECIFIC_CALIBRATED", "USER_OVERRIDE", "CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_2026"]
CadenceBasis = Literal["USER_SUPPLIED", "MODEL_USEFUL_LIFE_DAYS", "CONTROLLED_ASSUMPTION"]


@dataclass(frozen=True)
class GeneratorDeliveryCostResolution:
    catalog_model_id: str
    delivery_cost_usd: float
    basis: DeliveryCostBasis
    provenance: str


def resolve_generator_delivery_cost(
    model: GeneratorCatalogModel, *, override_usd: float | None = None,
) -> GeneratorDeliveryCostResolution:
    """Section 11/15: user override first, then a genuinely model-specific
    calibrated `replacement_cost_per_cycle` if one exists, else the
    controlled $3,500 benchmark -- never silently overwrites a real
    calibrated value with the controlled assumption."""
    if override_usd is not None:
        return GeneratorDeliveryCostResolution(
            catalog_model_id=model.catalog_model_id, delivery_cost_usd=override_usd,
            basis="USER_OVERRIDE", provenance="user_supplied_override",
        )
    for record in model.economics:
        if record.component == "replacement_cost_per_cycle" and record.value != "NOT_CALIBRATED":
            return GeneratorDeliveryCostResolution(
                catalog_model_id=model.catalog_model_id, delivery_cost_usd=float(record.value),
                basis="MODEL_SPECIFIC_CALIBRATED", provenance=record.source,
            )
    return GeneratorDeliveryCostResolution(
        catalog_model_id=model.catalog_model_id, delivery_cost_usd=CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_USD,
        basis="CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_2026", provenance=CONTROLLED_TC99M_GENERATOR_DELIVERY_COST_PROVENANCE,
    )


@dataclass(frozen=True)
class GeneratorReplacementCadence:
    interval_days: float
    deliveries_per_year: float
    basis: CadenceBasis


def deliveries_per_year_from_interval_days(interval_days: float) -> float:
    """Section 13-14: annual_generator_supply_cost = deliveries_per_year x
    delivery_cost -- deliveries_per_year is DERIVED from cadence, never
    hard-coded (e.g. never a hard-coded 182000 USD/year)."""
    if interval_days <= 0:
        raise ValueError("interval_days must be positive")
    return SUPPLY_CADENCE_DAYS_PER_YEAR_CONVENTION / interval_days


def build_replacement_cadence(
    model: GeneratorCatalogModel, *, override_interval_days: float | None = None,
) -> GeneratorReplacementCadence:
    """Section 13/15: user override first, else the model's own
    `useful_life_days` (already a real catalog field -- e.g. 14 days for all
    three initial models), else a disclosed controlled fallback."""
    if override_interval_days is not None:
        interval_days, basis = override_interval_days, "USER_SUPPLIED"
    elif model.useful_life_days is not None:
        interval_days, basis = model.useful_life_days, "MODEL_USEFUL_LIFE_DAYS"
    else:
        interval_days, basis = 14.0, "CONTROLLED_ASSUMPTION"
    return GeneratorReplacementCadence(
        interval_days=interval_days, deliveries_per_year=deliveries_per_year_from_interval_days(interval_days), basis=basis,
    )


def annual_generator_supply_opex(*, delivery_cost_usd: float, deliveries_per_year: float) -> float:
    """Section 13: the ONLY formula -- deliveries_per_year x delivery_cost.
    Never a hard-coded annual figure."""
    return delivery_cost_usd * deliveries_per_year


def generator_supply_ledger_rows(*, delivery_cost_usd: float, deliveries_per_year: float) -> tuple[float, ...]:
    """Section 42: one ledger row per delivery (plus a fractional final row
    for a non-integer cadence) -- `sum(rows) == annual_generator_supply_opex`
    exactly, proving reconciliation rather than asserting it separately."""
    full_deliveries = int(deliveries_per_year)
    remainder = deliveries_per_year - full_deliveries
    rows = [delivery_cost_usd] * full_deliveries
    if remainder > 1e-9:
        rows.append(delivery_cost_usd * remainder)
    return tuple(rows)


def generator_delivery_new_study_capex(
    model: GeneratorCatalogModel, *, study_scope: Literal["OPERATIONAL_ONLY", "CAPITAL_PLANNING"],
) -> float:
    """Section 12/16-17: the recurring consumable delivery/replacement cost
    is NEVER durable-equipment CapEx, in EITHER study scope -- always 0.0.
    Durable local infrastructure/shielding/installation, if legitimately
    calibrated, is modeled elsewhere (never multiplied from this $3,500
    recurring figure)."""
    return 0.0


@dataclass(frozen=True)
class GeneratorEconomicReportRow:
    generator_model: str
    delivery_cost_usd: float
    replacement_interval_days: float
    deliveries_per_year: float
    annual_supply_opex_usd: float
    capex_treatment: str
    provenance: str


def generator_economic_report_row(
    model: GeneratorCatalogModel, *, override_delivery_cost_usd: float | None = None,
    override_interval_days: float | None = None,
) -> GeneratorEconomicReportRow:
    cost = resolve_generator_delivery_cost(model, override_usd=override_delivery_cost_usd)
    cadence = build_replacement_cadence(model, override_interval_days=override_interval_days)
    annual_opex = annual_generator_supply_opex(delivery_cost_usd=cost.delivery_cost_usd, deliveries_per_year=cadence.deliveries_per_year)
    return GeneratorEconomicReportRow(
        generator_model=f"{model.manufacturer} {model.model}", delivery_cost_usd=cost.delivery_cost_usd,
        replacement_interval_days=cadence.interval_days, deliveries_per_year=cadence.deliveries_per_year,
        annual_supply_opex_usd=annual_opex, capex_treatment="OPEX_ONLY (recurring supply, never durable CapEx)",
        provenance=f"delivery_cost={cost.basis}; cadence={cadence.basis}",
    )

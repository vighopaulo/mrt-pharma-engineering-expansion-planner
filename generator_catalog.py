"""Commercial Mo-99/Tc-99m Generator Equipment Catalog.

GOVERNANCE-FIRST BUILD (Section 9 closure): mirrors the EXISTING
`cyclotron_catalog.py` schema/pattern exactly -- reuses its
`ProvenancedField`/`CalibrationStatus`/`EvidenceType` types directly rather
than duplicating them. A generator catalog model -> facility instance ->
fleet chain follows the identical shape as
`CyclotronCatalogModel -> FacilityCyclotronInstance -> CyclotronFleet`.

RESEARCH DISCLOSURE (section 10-11, honesty requirement): no live web
citation could be independently fetched in this session (both attempted
manufacturer URLs returned HTTP 404). The three models below are real,
long-standing, publicly documented commercial Mo-99/Tc-99m generator products
(Curium TechneLite, Curium Ultra-TechneKow FM, GE Healthcare Drytec) recalled
from general nuclear-pharmacy professional knowledge -- NOT independently
re-verified via a live fetch this session. Every field is therefore marked
`evidence_type="technical_literature"`, `confidence="medium"`, and
`calibration_status="literature_calibrated"` at best -- never
`"manufacturer_calibrated"` (that status is reserved for the cyclotron
catalog's actually-fetched-in-a-live-session entries). Purchase/replacement
pricing could not be defensibly sourced this session and is explicitly
`NOT_CALIBRATED` (never $0) per section 11.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from cyclotron_catalog import CalibrationStatus, EvidenceType, ProvenancedField

GeneratorAssetStatus = Literal["EXISTING", "PROPOSED", "UPGRADE", "REPLACEMENT"]
GeneratorOperatingState = Literal["AVAILABLE", "ELUTING", "MAINTENANCE", "UNAVAILABLE", "EXPIRED"]


@dataclass(frozen=True)
class GeneratorEconomicRecord:
    """Section 11-12: every economic value carries explicit provenance; a
    missing value is `NOT_CALIBRATED`, never a fabricated $0 or a guessed
    figure. Mirrors `ProvenancedField` but scoped to one cost line."""

    component: str
    value: float | Literal["NOT_CALIBRATED"]
    currency: str | None
    cost_year: str | None
    price_basis: str | None
    source: str
    evidence_type: EvidenceType
    confidence: Literal["high", "medium", "low", "unknown"]
    calibration_status: CalibrationStatus


@dataclass(frozen=True)
class GeneratorCatalogModel:
    catalog_model_id: str
    manufacturer: str
    model: str
    parent_radionuclide: str
    daughter_radionuclide: str
    commercial_status: Literal["current", "legacy", "discontinued"]
    new_purchase_candidate: bool
    installed_equipment_selectable: bool
    customer_selectable: bool
    nominal_reference_activity_options_mbq: tuple[float, ...]
    """Section 10: activity configuration options at reference/calibration
    time (the manufacturer's stated calibration point, typically the
    shipment/reference date-time -- NOT the elution time)."""
    reference_calibration_semantics: str
    useful_life_days: float | None
    """Typical clinical generator shelf life before replacement (driven by
    Mo-99 decay economics, not a hard physical failure) -- None if
    NOT_CALIBRATED for this specific model."""
    elution_efficiency_fraction: float | None
    max_elutions_per_day: int | None
    dimensions_cm: tuple[float, float, float] | None
    mass_kg: float | None
    shielding_handling_notes: str | None
    technical_operating_requirements: str | None
    requires_electrical_power: bool
    """Section 13: passive lead-shielded column generators (the norm for
    Mo-99/Tc-99m clinical generators) require NO meaningful electrical input
    for parent-daughter production/elution -- explicit, not fabricated."""
    field_provenance: Mapping[str, ProvenancedField]
    economics: tuple[GeneratorEconomicRecord, ...]
    source_url_or_document: str
    source_confidence: Literal["high", "medium", "low", "unknown"]


@dataclass(frozen=True)
class GeneratorCatalog:
    schema_version: str
    models: tuple[GeneratorCatalogModel, ...]

    def by_id(self, catalog_model_id: str) -> GeneratorCatalogModel:
        for model in self.models:
            if model.catalog_model_id == catalog_model_id:
                return model
        raise ValueError(f"Unknown generator catalog_model_id: {catalog_model_id}")


@dataclass(frozen=True)
class FacilityGeneratorInstance:
    """Mirrors `FacilityCyclotronInstance` exactly (section 17)."""

    instance_id: str
    catalog_model_id: str
    asset_status: GeneratorAssetStatus = "EXISTING"
    operating_state: GeneratorOperatingState = "AVAILABLE"
    site_reference_activity_mbq_override: float | None = None
    site_elution_efficiency_override: float | None = None
    location_object_id: str | None = None
    """Section 18: spatial placement anchor -- moving this changes route
    distance/transport time/Tc-99m decay downstream, never generator identity
    or economics by itself (no CapEx from a coordinate change alone)."""


def _catalog_path() -> Path:
    return Path(__file__).with_name("generator_equipment_catalog.json")


def _parse_provenanced_field(payload: Mapping[str, Any]) -> ProvenancedField:
    return ProvenancedField(
        value=payload.get("value"),
        unit=(None if payload.get("unit") is None else str(payload.get("unit"))),
        source=str(payload.get("source", "UNKNOWN")),
        evidence_type=str(payload.get("evidence_type", "unknown_not_calibrated")),
        confidence=str(payload.get("confidence", "unknown")),
        calibration_status=str(payload.get("calibration_status", "not_calibrated")),
        source_revision_or_date=(None if payload.get("source_revision_or_date") is None else str(payload.get("source_revision_or_date"))),
        notes=(None if payload.get("notes") is None else str(payload.get("notes"))),
    )


def _parse_economic_record(payload: Mapping[str, Any]) -> GeneratorEconomicRecord:
    raw_value = payload.get("value")
    value: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED" if raw_value in (None, "NOT_CALIBRATED") else float(raw_value)
    return GeneratorEconomicRecord(
        component=str(payload["component"]),
        value=value,
        currency=(None if payload.get("currency") is None else str(payload.get("currency"))),
        cost_year=(None if payload.get("cost_year") is None else str(payload.get("cost_year"))),
        price_basis=(None if payload.get("price_basis") is None else str(payload.get("price_basis"))),
        source=str(payload.get("source", "UNKNOWN")),
        evidence_type=str(payload.get("evidence_type", "unknown_not_calibrated")),
        confidence=str(payload.get("confidence", "unknown")),
        calibration_status=str(payload.get("calibration_status", "not_calibrated")),
    )


def _parse_model(payload: Mapping[str, Any]) -> GeneratorCatalogModel:
    dims = payload.get("dimensions_cm")
    return GeneratorCatalogModel(
        catalog_model_id=str(payload["catalog_model_id"]),
        manufacturer=str(payload["manufacturer"]),
        model=str(payload["model"]),
        parent_radionuclide=str(payload.get("parent_radionuclide", "Mo-99")),
        daughter_radionuclide=str(payload.get("daughter_radionuclide", "Tc-99m")),
        commercial_status=str(payload.get("commercial_status", "legacy")),
        new_purchase_candidate=bool(payload.get("new_purchase_candidate", False)),
        installed_equipment_selectable=bool(payload.get("installed_equipment_selectable", True)),
        customer_selectable=bool(payload.get("customer_selectable", True)),
        nominal_reference_activity_options_mbq=tuple(float(v) for v in payload.get("nominal_reference_activity_options_mbq", [])),
        reference_calibration_semantics=str(payload.get("reference_calibration_semantics", "UNKNOWN")),
        useful_life_days=(None if payload.get("useful_life_days") is None else float(payload.get("useful_life_days"))),
        elution_efficiency_fraction=(None if payload.get("elution_efficiency_fraction") is None else float(payload.get("elution_efficiency_fraction"))),
        max_elutions_per_day=(None if payload.get("max_elutions_per_day") is None else int(payload.get("max_elutions_per_day"))),
        dimensions_cm=(None if dims is None else tuple(float(v) for v in dims)),
        mass_kg=(None if payload.get("mass_kg") is None else float(payload.get("mass_kg"))),
        shielding_handling_notes=(None if payload.get("shielding_handling_notes") is None else str(payload.get("shielding_handling_notes"))),
        technical_operating_requirements=(None if payload.get("technical_operating_requirements") is None else str(payload.get("technical_operating_requirements"))),
        requires_electrical_power=bool(payload.get("requires_electrical_power", False)),
        field_provenance={
            str(name): _parse_provenanced_field(fp) for name, fp in dict(payload.get("field_provenance", {})).items()
        },
        economics=tuple(_parse_economic_record(rec) for rec in payload.get("economics", [])),
        source_url_or_document=str(payload.get("source_url_or_document", "UNKNOWN")),
        source_confidence=str(payload.get("source_confidence", "unknown")),
    )


@lru_cache(maxsize=1)
def load_generator_catalog() -> GeneratorCatalog:
    payload = json.loads(_catalog_path().read_text(encoding="utf-8"))
    return GeneratorCatalog(
        schema_version=str(payload.get("schema_version", "unknown")),
        models=tuple(_parse_model(item) for item in payload.get("models", [])),
    )


def create_facility_generator_instance(
    *, instance_id: str, catalog_model_id: str, asset_status: GeneratorAssetStatus = "EXISTING",
    location_object_id: str | None = None,
) -> FacilityGeneratorInstance:
    """Section 16-17: selecting a catalog model creates a persistent facility
    instance (GEN-001, GEN-002, ...) -- mirrors
    `create_facility_cyclotron_instance` exactly."""
    return FacilityGeneratorInstance(
        instance_id=instance_id, catalog_model_id=catalog_model_id, asset_status=asset_status,
        location_object_id=location_object_id,
    )


def resolve_effective_reference_activity_mbq(instance: FacilityGeneratorInstance, model: GeneratorCatalogModel) -> float | None:
    if instance.site_reference_activity_mbq_override is not None:
        return instance.site_reference_activity_mbq_override
    if model.nominal_reference_activity_options_mbq:
        return model.nominal_reference_activity_options_mbq[0]
    return None


def resolve_effective_elution_efficiency(instance: FacilityGeneratorInstance, model: GeneratorCatalogModel) -> float | None:
    if instance.site_elution_efficiency_override is not None:
        return instance.site_elution_efficiency_override
    return model.elution_efficiency_fraction

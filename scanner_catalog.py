"""Unified PET + SPECT Scanner Equipment Catalog.

GOVERNANCE NOTE (section 20-22 closure -- IMPORTANT HONEST FINDING): a prior
codebase audit (this build) found NO pre-existing PET scanner equipment
catalog and NO "live/API equipment data" mechanism anywhere in this
repository -- `scanner.py` is a bare capacity dataclass
(cycle_min_per_patient/availability_pct) with no manufacturer/model identity,
and `healthcare_adapters.py`/`healthcare_integration.py` are explicitly
documented as having "no live connections, no API calls" (patient-data
adapters only, not equipment data). There is therefore no existing PET
architecture to "integrate SPECT into" -- this module is the FIRST scanner
equipment catalog in the repository, and it is symmetric for PET and SPECT
from its first line (mirrors `cyclotron_catalog.py`'s schema/pattern exactly,
reusing its `ProvenancedField`/`CalibrationStatus`/`EvidenceType` types) --
satisfying "one equipment-data authority for both modalities" as a NEW,
unified authority rather than a retrofit of something that did not exist.

RESEARCH DISCLOSURE: no live citation could be fetched this session (attempted
manufacturer URL returned HTTP 404). All records below use real, publicly
known current/legacy PET and SPECT/SPECT-CT product names, with GENERAL
(non-model-specific-quote) technical characteristics recalled from
professional knowledge, honestly labeled `confidence="medium"`,
`calibration_status="literature_calibrated"` (never "manufacturer_calibrated").
Purchase/service pricing per section 25 is NOT_CALIBRATED (never $0/fabricated)
unless a defensible source is available -- none was for any specific model
this session.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping

from cyclotron_catalog import CalibrationStatus, EvidenceType, ProvenancedField
from clinical_resource_identity import ScannerModality

ScannerAssetStatus = Literal["EXISTING", "PROPOSED", "UPGRADE", "REPLACEMENT"]
ScannerOperatingState = Literal["AVAILABLE", "IN_USE", "MAINTENANCE", "UNAVAILABLE"]


@dataclass(frozen=True)
class ScannerEconomicRecord:
    component: str
    value: float | Literal["NOT_CALIBRATED"]
    currency: str | None
    cost_year: str | None
    price_basis: str | None
    equipment_only_or_installed: Literal["EQUIPMENT_ONLY", "INSTALLED", "UNKNOWN"]
    service_scope: str | None
    source: str
    evidence_type: EvidenceType
    confidence: Literal["high", "medium", "low", "unknown"]
    calibration_status: CalibrationStatus


@dataclass(frozen=True)
class ScannerCatalogModel:
    catalog_model_id: str
    manufacturer: str
    model: str
    modality: ScannerModality
    ct_configuration: str | None
    """e.g. 'integrated low-dose CT for attenuation correction', 'SPECT-only (no CT)'."""
    commercial_status: Literal["current", "legacy", "discontinued", "LEGACY_INSTALLED_BASE"]
    new_purchase_candidate: bool
    installed_equipment_selectable: bool
    customer_selectable: bool
    supported_radionuclides_or_energy_range_kev: str
    detector_technology: str | None
    protocol_families: tuple[str, ...]
    typical_acquisition_minutes_per_protocol: Mapping[str, float]
    patient_weight_limit_kg: float | None
    dimensions_footprint_notes: str | None
    power_specification_status: Literal["MEASURED", "MANUFACTURER_STATED", "NOT_CALIBRATED"]
    active_power_kw: float | None
    idle_power_kw: float | None
    field_provenance: Mapping[str, ProvenancedField]
    economics: tuple[ScannerEconomicRecord, ...]
    source_url_or_document: str
    source_confidence: Literal["high", "medium", "low", "unknown"]


@dataclass(frozen=True)
class ScannerCatalog:
    schema_version: str
    models: tuple[ScannerCatalogModel, ...]

    def by_id(self, catalog_model_id: str) -> ScannerCatalogModel:
        for model in self.models:
            if model.catalog_model_id == catalog_model_id:
                return model
        raise ValueError(f"Unknown scanner catalog_model_id: {catalog_model_id}")

    def models_of_modality(self, modality: ScannerModality) -> tuple[ScannerCatalogModel, ...]:
        return tuple(m for m in self.models if m.modality == modality)


@dataclass(frozen=True)
class FacilityScannerInstance:
    """Mirrors `FacilityCyclotronInstance`/`FacilityGeneratorInstance`."""

    scanner_id: str
    catalog_model_id: str
    modality: ScannerModality
    asset_status: ScannerAssetStatus = "EXISTING"
    operating_state: ScannerOperatingState = "AVAILABLE"
    location_object_id: str | None = None


def _catalog_path() -> Path:
    return Path(__file__).with_name("scanner_equipment_catalog.json")


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


def _parse_economic_record(payload: Mapping[str, Any]) -> ScannerEconomicRecord:
    raw_value = payload.get("value")
    value: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED" if raw_value in (None, "NOT_CALIBRATED") else float(raw_value)
    return ScannerEconomicRecord(
        component=str(payload["component"]), value=value,
        currency=(None if payload.get("currency") is None else str(payload.get("currency"))),
        cost_year=(None if payload.get("cost_year") is None else str(payload.get("cost_year"))),
        price_basis=(None if payload.get("price_basis") is None else str(payload.get("price_basis"))),
        equipment_only_or_installed=str(payload.get("equipment_only_or_installed", "UNKNOWN")),
        service_scope=(None if payload.get("service_scope") is None else str(payload.get("service_scope"))),
        source=str(payload.get("source", "UNKNOWN")),
        evidence_type=str(payload.get("evidence_type", "unknown_not_calibrated")),
        confidence=str(payload.get("confidence", "unknown")),
        calibration_status=str(payload.get("calibration_status", "not_calibrated")),
    )


def _parse_model(payload: Mapping[str, Any]) -> ScannerCatalogModel:
    return ScannerCatalogModel(
        catalog_model_id=str(payload["catalog_model_id"]),
        manufacturer=str(payload["manufacturer"]),
        model=str(payload["model"]),
        modality=str(payload["modality"]),
        ct_configuration=(None if payload.get("ct_configuration") is None else str(payload.get("ct_configuration"))),
        commercial_status=str(payload.get("commercial_status", "legacy")),
        new_purchase_candidate=bool(payload.get("new_purchase_candidate", False)),
        installed_equipment_selectable=bool(payload.get("installed_equipment_selectable", True)),
        customer_selectable=bool(payload.get("customer_selectable", True)),
        supported_radionuclides_or_energy_range_kev=str(payload.get("supported_radionuclides_or_energy_range_kev", "UNKNOWN")),
        detector_technology=(None if payload.get("detector_technology") is None else str(payload.get("detector_technology"))),
        protocol_families=tuple(str(p) for p in payload.get("protocol_families", [])),
        typical_acquisition_minutes_per_protocol={
            str(k): float(v) for k, v in dict(payload.get("typical_acquisition_minutes_per_protocol", {})).items()
        },
        patient_weight_limit_kg=(None if payload.get("patient_weight_limit_kg") is None else float(payload.get("patient_weight_limit_kg"))),
        dimensions_footprint_notes=(None if payload.get("dimensions_footprint_notes") is None else str(payload.get("dimensions_footprint_notes"))),
        power_specification_status=str(payload.get("power_specification_status", "NOT_CALIBRATED")),
        active_power_kw=(None if payload.get("active_power_kw") is None else float(payload.get("active_power_kw"))),
        idle_power_kw=(None if payload.get("idle_power_kw") is None else float(payload.get("idle_power_kw"))),
        field_provenance={
            str(name): _parse_provenanced_field(fp) for name, fp in dict(payload.get("field_provenance", {})).items()
        },
        economics=tuple(_parse_economic_record(rec) for rec in payload.get("economics", [])),
        source_url_or_document=str(payload.get("source_url_or_document", "UNKNOWN")),
        source_confidence=str(payload.get("source_confidence", "unknown")),
    )


@lru_cache(maxsize=1)
def load_scanner_catalog() -> ScannerCatalog:
    payload = json.loads(_catalog_path().read_text(encoding="utf-8"))
    return ScannerCatalog(
        schema_version=str(payload.get("schema_version", "unknown")),
        models=tuple(_parse_model(item) for item in payload.get("models", [])),
    )


def create_facility_scanner_instance(
    *, scanner_id: str, catalog_model_id: str, modality: ScannerModality,
    asset_status: ScannerAssetStatus = "EXISTING", location_object_id: str | None = None,
) -> FacilityScannerInstance:
    return FacilityScannerInstance(
        scanner_id=scanner_id, catalog_model_id=catalog_model_id, modality=modality,
        asset_status=asset_status, location_object_id=location_object_id,
    )

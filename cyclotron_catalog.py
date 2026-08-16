from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from cyclotron_production_windows import CyclotronAsset, CyclotronFleet, CyclotronProductionCapability


CalibrationStatus = Literal[
    "manufacturer_calibrated",
    "site_calibrated",
    "literature_calibrated",
    "modeled",
    "not_calibrated",
]

EvidenceType = Literal[
    "manufacturer_specification",
    "manufacturer_performance_data",
    "technical_literature",
    "operational_installation",
    "site_specific",
    "derived_unit_conversion",
    "modeled",
    "not_calibrated",
    "derived_calculated_value",
    "manufacturer_brochure",
    "peer_reviewed_literature",
    "operational_installation_data",
    "site_specific_measured_data",
    "engineering_assumption",
    "unknown_not_calibrated",
]

CommercialStatus = Literal["current", "legacy", "discontinued"]
CyclotronOperatingState = Literal[
    "AVAILABLE",
    "SETUP",
    "IRRADIATING",
    "TARGET_CHANGE",
    "TRANSFER",
    "MAINTENANCE",
    "FAULT",
    "STANDBY",
]


@dataclass(frozen=True)
class ProvenancedField:
    value: Any
    unit: str | None
    source: str
    evidence_type: EvidenceType
    confidence: Literal["high", "medium", "low", "unknown"]
    calibration_status: CalibrationStatus
    source_revision_or_date: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ProductionPerformanceRecord:
    manufacturer: str
    model: str
    radionuclide: str
    particle: str | None
    target_system: str | None
    beam_energy_mev: float | None
    beam_current_ua: float | None
    irradiation_time_minutes: float | None
    single_or_dual_irradiation: str | None
    number_of_targets: int | None
    reported_eob_activity: float | None
    reported_eob_activity_unit: str | None
    normalized_eob_activity_mbq: float | None
    production_conditions: str | None
    source: str
    source_revision: str | None
    evidence_type: EvidenceType
    confidence: Literal["high", "medium", "low", "unknown"]
    calibration_status: CalibrationStatus
    notes: str | None = None


@dataclass(frozen=True)
class CyclotronCatalogModel:
    catalog_model_id: str
    manufacturer: str
    model: str
    family: str | None
    commercial_status: CommercialStatus
    new_purchase_candidate: bool
    installed_equipment_selectable: bool
    customer_selectable: bool
    classification: str
    supported_radionuclides: tuple[str, ...]
    production_cycle_minutes_by_radionuclide: Mapping[str, float]
    max_simultaneous_production_streams: int
    field_provenance: Mapping[str, ProvenancedField]
    production_performance_records: tuple[ProductionPerformanceRecord, ...]

    @property
    def has_calibrated_radionuclide_capability(self) -> bool:
        return bool(self.supported_radionuclides)

    @property
    def has_production_cycles_for_supported_radionuclides(self) -> bool:
        if not self.supported_radionuclides:
            return False
        return all(isotope in self.production_cycle_minutes_by_radionuclide for isotope in self.supported_radionuclides)

    @property
    def schedulable_radionuclides(self) -> tuple[str, ...]:
        return tuple(
            isotope
            for isotope in self.supported_radionuclides
            if isotope in self.production_cycle_minutes_by_radionuclide
        )

    @property
    def production_calibration_status(self) -> CalibrationStatus:
        has_calibrated_point = any(
            record.normalized_eob_activity_mbq is not None and record.calibration_status == "manufacturer_calibrated"
            for record in self.production_performance_records
        )
        if has_calibrated_point:
            return "manufacturer_calibrated"
        if self.schedulable_radionuclides:
            return "modeled"
        return "not_calibrated"


@dataclass(frozen=True)
class FacilityCyclotronInstance:
    instance_id: str
    catalog_model_id: str
    installed: bool = True
    operating_state: CyclotronOperatingState = "AVAILABLE"
    site_supported_radionuclide_override: tuple[str, ...] | None = None
    site_production_cycle_minutes_override: Mapping[str, float] | None = None
    site_operating_current_ua: float | None = None
    site_max_eob_capacity_mbq_per_day: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "catalog_model_id": self.catalog_model_id,
            "installed": bool(self.installed),
            "operating_state": self.operating_state,
            "site_supported_radionuclide_override": list(self.site_supported_radionuclide_override) if self.site_supported_radionuclide_override is not None else None,
            "site_production_cycle_minutes_override": None if self.site_production_cycle_minutes_override is None else dict(self.site_production_cycle_minutes_override),
            "site_operating_current_ua": self.site_operating_current_ua,
            "site_max_eob_capacity_mbq_per_day": self.site_max_eob_capacity_mbq_per_day,
        }

    @staticmethod
    def from_dict(payload: Mapping[str, Any]) -> "FacilityCyclotronInstance":
        return FacilityCyclotronInstance(
            instance_id=str(payload["instance_id"]),
            catalog_model_id=str(payload["catalog_model_id"]),
            installed=bool(payload.get("installed", True)),
            operating_state=str(payload.get("operating_state", "AVAILABLE")),
            site_supported_radionuclide_override=(
                None
                if payload.get("site_supported_radionuclide_override") is None
                else tuple(str(item) for item in payload.get("site_supported_radionuclide_override", []))
            ),
            site_production_cycle_minutes_override=(
                None
                if payload.get("site_production_cycle_minutes_override") is None
                else {str(k): float(v) for k, v in dict(payload.get("site_production_cycle_minutes_override", {})).items()}
            ),
            site_operating_current_ua=(
                None
                if payload.get("site_operating_current_ua") is None
                else float(payload.get("site_operating_current_ua"))
            ),
            site_max_eob_capacity_mbq_per_day=(
                None
                if payload.get("site_max_eob_capacity_mbq_per_day") is None
                else float(payload.get("site_max_eob_capacity_mbq_per_day"))
            ),
        )


@dataclass(frozen=True)
class CyclotronCatalog:
    schema_version: str
    models: tuple[CyclotronCatalogModel, ...]

    def manufacturers(self, *, customer_selectable_only: bool = True) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for model in self.models:
            if customer_selectable_only and not model.customer_selectable:
                continue
            seen[model.manufacturer] = None
        return tuple(seen.keys())

    def models_for_manufacturer(self, manufacturer: str, *, customer_selectable_only: bool = True) -> tuple[CyclotronCatalogModel, ...]:
        return tuple(
            model
            for model in self.models
            if model.manufacturer == manufacturer and (model.customer_selectable or not customer_selectable_only)
        )

    def by_id(self, catalog_model_id: str) -> CyclotronCatalogModel:
        for model in self.models:
            if model.catalog_model_id == catalog_model_id:
                return model
        raise KeyError(f"Unknown catalog model id: {catalog_model_id}")

    def to_customer_model_options(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (model.catalog_model_id, f"{model.model} ({model.commercial_status})")
            for model in self.models
            if model.customer_selectable
        )


def _catalog_path() -> Path:
    return Path(__file__).with_name("cyclotron_equipment_catalog.json")


def _parse_provenanced_field(payload: Mapping[str, Any]) -> ProvenancedField:
    return ProvenancedField(
        value=payload.get("value"),
        unit=payload.get("unit"),
        source=str(payload.get("source", "UNKNOWN")),
        evidence_type=str(payload.get("evidence_type", "unknown_not_calibrated")),
        confidence=str(payload.get("confidence", "unknown")),
        calibration_status=str(payload.get("calibration_status", "not_calibrated")),
        source_revision_or_date=payload.get("source_revision_or_date"),
        notes=payload.get("notes"),
    )


def _normalize_activity_to_mbq(value: float | None, unit: str | None) -> float | None:
    if value is None or unit is None:
        return None
    normalized_unit = unit.strip().lower()
    if normalized_unit == "mbq":
        return float(value)
    if normalized_unit == "gbq":
        return float(value) * 1000.0
    if normalized_unit == "ci":
        return float(value) * 37_000.0
    if normalized_unit == "mci":
        return float(value) * 37.0
    raise ValueError(f"Unsupported activity unit for normalization: {unit}")


def _parse_performance_record(payload: Mapping[str, Any]) -> ProductionPerformanceRecord:
    reported_value = payload.get("reported_eob_activity")
    reported_unit = payload.get("reported_eob_activity_unit")
    normalized_payload_value = payload.get("normalized_eob_activity_mbq")
    normalized_computed = _normalize_activity_to_mbq(
        None if reported_value is None else float(reported_value),
        None if reported_unit is None else str(reported_unit),
    )
    normalized_value = normalized_computed if normalized_computed is not None else (
        None if normalized_payload_value is None else float(normalized_payload_value)
    )
    return ProductionPerformanceRecord(
        manufacturer=str(payload.get("manufacturer", "")),
        model=str(payload.get("model", "")),
        radionuclide=str(payload.get("radionuclide", "")),
        particle=(None if payload.get("particle") is None else str(payload.get("particle"))),
        target_system=(None if payload.get("target_system") is None else str(payload.get("target_system"))),
        beam_energy_mev=(None if payload.get("beam_energy_mev") is None else float(payload.get("beam_energy_mev"))),
        beam_current_ua=(None if payload.get("beam_current_ua") is None else float(payload.get("beam_current_ua"))),
        irradiation_time_minutes=(None if payload.get("irradiation_time_minutes") is None else float(payload.get("irradiation_time_minutes"))),
        single_or_dual_irradiation=(
            None if payload.get("single_or_dual_irradiation") is None else str(payload.get("single_or_dual_irradiation"))
        ),
        number_of_targets=(None if payload.get("number_of_targets") is None else int(payload.get("number_of_targets"))),
        reported_eob_activity=(None if reported_value is None else float(reported_value)),
        reported_eob_activity_unit=(None if reported_unit is None else str(reported_unit)),
        normalized_eob_activity_mbq=normalized_value,
        production_conditions=(None if payload.get("production_conditions") is None else str(payload.get("production_conditions"))),
        source=str(payload.get("source", "UNKNOWN")),
        source_revision=(None if payload.get("source_revision") is None else str(payload.get("source_revision"))),
        evidence_type=str(payload.get("evidence_type", "unknown_not_calibrated")),
        confidence=str(payload.get("confidence", "unknown")),
        calibration_status=str(payload.get("calibration_status", "not_calibrated")),
        notes=(None if payload.get("notes") is None else str(payload.get("notes"))),
    )


def _parse_model(payload: Mapping[str, Any]) -> CyclotronCatalogModel:
    radionuclides = tuple(str(item) for item in payload.get("supported_radionuclides", []))
    cycles = {str(k): float(v) for k, v in dict(payload.get("production_cycle_minutes_by_radionuclide", {})).items()}
    return CyclotronCatalogModel(
        catalog_model_id=str(payload["catalog_model_id"]),
        manufacturer=str(payload["manufacturer"]),
        model=str(payload["model"]),
        family=(None if payload.get("family") is None else str(payload.get("family"))),
        commercial_status=str(payload.get("commercial_status", "legacy")),
        new_purchase_candidate=bool(payload.get("new_purchase_candidate", False)),
        installed_equipment_selectable=bool(payload.get("installed_equipment_selectable", True)),
        customer_selectable=bool(payload.get("customer_selectable", True)),
        classification=str(payload.get("classification", "unclassified")),
        supported_radionuclides=radionuclides,
        production_cycle_minutes_by_radionuclide=cycles,
        max_simultaneous_production_streams=int(payload.get("max_simultaneous_production_streams", 1)),
        field_provenance={
            str(name): _parse_provenanced_field(field_payload)
            for name, field_payload in dict(payload.get("field_provenance", {})).items()
        },
        production_performance_records=tuple(
            _parse_performance_record(record)
            for record in payload.get("production_performance_records", [])
        ),
    )


@lru_cache(maxsize=1)
def load_cyclotron_catalog() -> CyclotronCatalog:
    payload = json.loads(_catalog_path().read_text(encoding="utf-8"))
    return CyclotronCatalog(
        schema_version=str(payload.get("schema_version", "unknown")),
        models=tuple(_parse_model(item) for item in payload.get("models", [])),
    )


def create_facility_cyclotron_instance(
    *,
    catalog_model_id: str,
    existing_instances: Sequence[FacilityCyclotronInstance],
    preferred_instance_id: str | None = None,
) -> FacilityCyclotronInstance:
    if preferred_instance_id:
        new_id = preferred_instance_id.strip()
        if not new_id:
            raise ValueError("preferred_instance_id cannot be blank")
    else:
        seen = {item.instance_id for item in existing_instances}
        index = 1
        while True:
            candidate = f"CY-{index:03d}"
            if candidate not in seen:
                new_id = candidate
                break
            index += 1
    return FacilityCyclotronInstance(instance_id=new_id, catalog_model_id=catalog_model_id)


def resolve_effective_supported_radionuclides(
    instance: FacilityCyclotronInstance,
    model: CyclotronCatalogModel,
) -> tuple[str, ...]:
    if instance.site_supported_radionuclide_override is not None:
        return tuple(instance.site_supported_radionuclide_override)
    return model.supported_radionuclides


def resolve_effective_cycle_map(
    instance: FacilityCyclotronInstance,
    model: CyclotronCatalogModel,
) -> dict[str, float]:
    if instance.site_production_cycle_minutes_override is not None:
        return dict(instance.site_production_cycle_minutes_override)
    return dict(model.production_cycle_minutes_by_radionuclide)


def _resolve_calibrated_eob_by_radionuclide(
    *,
    model: CyclotronCatalogModel,
    schedulable_supported: Sequence[str],
    cycles: Mapping[str, float],
    site_operating_current_ua: float | None,
) -> dict[str, float]:
    resolved: dict[str, float] = {}
    for isotope in schedulable_supported:
        target_cycle = float(cycles[isotope])
        candidates = [
            record
            for record in model.production_performance_records
            if record.radionuclide == isotope
            and record.calibration_status == "manufacturer_calibrated"
            and record.normalized_eob_activity_mbq is not None
            and record.irradiation_time_minutes is not None
            and abs(float(record.irradiation_time_minutes) - target_cycle) <= 1e-9
        ]
        if site_operating_current_ua is not None:
            narrowed = [
                record
                for record in candidates
                if record.beam_current_ua is not None
                and abs(float(record.beam_current_ua) - float(site_operating_current_ua)) <= 1e-9
            ]
            if narrowed:
                candidates = narrowed
        if not candidates:
            continue
        selected = candidates[0]
        resolved[isotope] = float(selected.normalized_eob_activity_mbq)
    return resolved


def build_cyclotron_asset_from_instance(
    *,
    instance: FacilityCyclotronInstance,
    model: CyclotronCatalogModel,
) -> CyclotronAsset | None:
    supported = resolve_effective_supported_radionuclides(instance, model)
    cycles = resolve_effective_cycle_map(instance, model)
    if not supported:
        return None

    schedulable_supported = tuple(isotope for isotope in supported if isotope in cycles)
    if not schedulable_supported:
        return None

    calibrated_eob = _resolve_calibrated_eob_by_radionuclide(
        model=model,
        schedulable_supported=schedulable_supported,
        cycles=cycles,
        site_operating_current_ua=instance.site_operating_current_ua,
    )

    capability = CyclotronProductionCapability(
        cyclotron_id=instance.instance_id,
        supported_radionuclides=schedulable_supported,
        max_simultaneous_production_streams=model.max_simultaneous_production_streams,
        production_cycle_minutes_by_radionuclide={
            isotope: float(cycles[isotope])
            for isotope in schedulable_supported
        },
        calibrated_eob_activity_mbq_by_radionuclide=(calibrated_eob or None),
        site_eob_capacity_mbq_per_day=instance.site_max_eob_capacity_mbq_per_day,
    )
    return CyclotronAsset(
        cyclotron_id=instance.instance_id,
        capability=capability,
        model_identifier=model.model,
        manufacturer=model.manufacturer,
        capability_provenance=model.catalog_model_id,
    )


def build_fleet_from_instances(
    *,
    catalog: CyclotronCatalog,
    instances: Sequence[FacilityCyclotronInstance],
) -> tuple[CyclotronFleet | None, tuple[str, ...]]:
    assets: list[CyclotronAsset] = []
    warnings: list[str] = []
    for instance in instances:
        model = catalog.by_id(instance.catalog_model_id)
        asset = build_cyclotron_asset_from_instance(instance=instance, model=model)
        if asset is None:
            warnings.append(
                f"{instance.instance_id} ({model.manufacturer} {model.model}) does not have calibrated radionuclide and cycle data for scheduling."
            )
            continue
        assets.append(asset)
    if not assets:
        return None, tuple(warnings)
    return CyclotronFleet(assets=tuple(assets)), tuple(warnings)


def list_models_grouped_by_manufacturer(catalog: CyclotronCatalog) -> dict[str, tuple[CyclotronCatalogModel, ...]]:
    grouped: dict[str, list[CyclotronCatalogModel]] = {}
    for model in catalog.models:
        if not model.customer_selectable:
            continue
        grouped.setdefault(model.manufacturer, []).append(model)
    return {manufacturer: tuple(models) for manufacturer, models in grouped.items()}


def find_production_records(
    *,
    catalog: CyclotronCatalog,
    catalog_model_id: str,
    radionuclide: str | None = None,
) -> tuple[ProductionPerformanceRecord, ...]:
    model = catalog.by_id(catalog_model_id)
    if radionuclide is None:
        return model.production_performance_records
    return tuple(record for record in model.production_performance_records if record.radionuclide == radionuclide)


def calculate_eob_activity_from_calibrated_record(
    *,
    record: ProductionPerformanceRecord,
    beam_current_ua: float,
    irradiation_time_minutes: float,
    calibration_constant_k: float | None,
) -> tuple[float | None, str]:
    if calibration_constant_k is None:
        if (
            record.normalized_eob_activity_mbq is not None
            and record.beam_current_ua is not None
            and record.irradiation_time_minutes is not None
            and abs(float(beam_current_ua) - float(record.beam_current_ua)) <= 1e-9
            and abs(float(irradiation_time_minutes) - float(record.irradiation_time_minutes)) <= 1e-9
        ):
            return record.normalized_eob_activity_mbq, "manufacturer_reported_calibration_point"
        if record.normalized_eob_activity_mbq is not None:
            return None, "not_calibrated"
        return None, "not_calibrated"

    if beam_current_ua <= 0.0 or irradiation_time_minutes <= 0.0:
        raise ValueError("beam_current_ua and irradiation_time_minutes must be positive")

    # Saturation-like modeled relationship is allowed only when an explicit calibration constant is provided.
    half_life_minutes_by_radionuclide = {
        "F-18": 109.8,
        "Ga-68": 67.7,
        "C-11": 20.3,
        "N-13": 9.97,
        "O-15": 2.04,
        "Tc-99m": 360.0,
    }
    half_life_minutes = half_life_minutes_by_radionuclide.get(record.radionuclide)
    if half_life_minutes is None:
        return None, "not_calibrated"
    decay_lambda = math.log(2.0) / half_life_minutes
    modeled = float(calibration_constant_k) * beam_current_ua * (1.0 - math.exp(-decay_lambda * irradiation_time_minutes))
    return modeled, "modeled"


def migration_from_legacy_model_counts(saved_or_draft_state: Mapping[str, Any]) -> tuple[FacilityCyclotronInstance, ...]:
    mapping = {
        "PETTRACE_800": "GE_PETTRACE_800",
        "COMPACT_F18_GA68": "GE_PETTRACE_840",
        "RESEARCH_MULTI_ISOTOPE": "IBA_CYCLONE_30XP",
    }
    instances: list[FacilityCyclotronInstance] = []
    for legacy_id, catalog_id in mapping.items():
        raw_count = saved_or_draft_state.get(f"build3::production::model_count::{legacy_id}", 0)
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            count = 0
        for _ in range(max(0, count)):
            instances.append(create_facility_cyclotron_instance(catalog_model_id=catalog_id, existing_instances=instances))
    return tuple(instances)

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
import hashlib
import json
import re
from typing import Any, Iterable, Literal, Mapping, Sequence

from cyclotron_fleet_recommendation import CyclotronModelSpec
from cyclotron_production_windows import CyclotronProductionCapability


EngineeringSourceType = Literal[
    "manufacturer_document",
    "regulatory_document",
    "government_source",
    "academic_publication",
    "hospital_document",
    "project_document",
    "vendor_quote",
    "industry_report",
    "user_supplied_document",
    "internal_engineering_record",
    "web_page",
    "database_record",
    "unknown",
]

EvidenceSourceTier = Literal["TIER_1", "TIER_2", "TIER_3", "TIER_4", "UNKNOWN"]
SourceQuality = Literal["high", "medium", "low", "unknown"]
SourceStatus = Literal["active", "superseded", "withdrawn", "unknown"]
DocumentFormat = Literal["pdf", "docx", "txt", "csv", "json", "html", "url_reference", "unknown"]
ClaimType = Literal["quantitative", "qualitative", "capability", "cost", "compatibility", "unknown"]
VerificationStatus = Literal["unverified", "verified", "rejected"]
ConflictStatus = Literal["none", "conflict", "not_comparable", "unknown"]
ConflictResolutionStatus = Literal[
    "unresolved",
    "resolved_by_user",
    "resolved_by_authoritative_source",
    "resolved_by_policy",
    "not_comparable",
]
ValueType = Literal["scalar", "range", "boolean", "text", "currency", "unknown"]
ProposalPromotionStatus = Literal["evidence_only", "candidate", "accepted", "rejected", "superseded"]
CatalogStatus = Literal["draft", "incomplete", "conflicted", "ready"]
RelationshipAuditStatus = Literal[
    "DIRECT NATIVE CONNECTION",
    "NATIVE BOUNDED ORCHESTRATION",
    "PARTIAL CONNECTION",
    "NOT CONNECTED",
]


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def classify_source_tier(source_type: EngineeringSourceType) -> EvidenceSourceTier:
    if source_type in {
        "manufacturer_document",
        "regulatory_document",
        "government_source",
        "hospital_document",
        "project_document",
        "internal_engineering_record",
    }:
        return "TIER_1"
    if source_type in {"academic_publication"}:
        return "TIER_2"
    if source_type in {"vendor_quote", "industry_report", "database_record"}:
        return "TIER_3"
    if source_type in {"web_page"}:
        return "TIER_4"
    return "UNKNOWN"


def _tokenize(text: str) -> tuple[str, ...]:
    tokens = tuple(token for token in re.split(r"[^a-z0-9]+", text.lower()) if token)
    return tokens


def _tier_rank(tier: EvidenceSourceTier) -> int:
    ranks = {"TIER_1": 1, "TIER_2": 2, "TIER_3": 3, "TIER_4": 4, "UNKNOWN": 5}
    return ranks[tier]


@dataclass(frozen=True)
class EngineeringEvidenceSource:
    source_id: str
    source_type: EngineeringSourceType
    title: str
    publisher_or_organization: str | None = None
    author: str | None = None
    publication_date: date | None = None
    retrieved_at: datetime | None = None
    url_or_locator: str | None = None
    document_identifier: str | None = None
    version: str | None = None
    jurisdiction: str | None = None
    language: str | None = None
    source_tier: EvidenceSourceTier = "UNKNOWN"
    source_quality: SourceQuality = "unknown"
    source_status: SourceStatus = "unknown"
    notes: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class EngineeringEvidenceDocument:
    document_id: str
    source_id: str
    title: str
    format: DocumentFormat
    document_identifier: str | None = None
    url_or_locator: str | None = None
    version: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    content_fingerprint: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class EngineeringEvidenceChunk:
    chunk_id: str
    document_id: str
    source_id: str
    content: str
    page_reference: str | None = None
    section_reference: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    trace_id: str | None = None


@dataclass(frozen=True)
class EngineeringEvidenceClaim:
    claim_id: str
    source_id: str
    document_id: str | None
    chunk_id: str | None
    claim_type: ClaimType
    subject: str
    predicate: str
    raw_value: Any
    normalized_value: Any
    unit: str | None
    quoted_or_extracted_text_reference: str | None = None
    confidence: float | None = None
    source_tier: EvidenceSourceTier = "UNKNOWN"
    verification_status: VerificationStatus = "unverified"
    conflict_status: ConflictStatus = "unknown"
    parameter_type: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class EngineeringEvidenceValue:
    value_id: str
    parameter_name: str
    value: float | str | bool | None = None
    unit: str | None = None
    value_type: ValueType = "unknown"
    minimum: float | None = None
    maximum: float | None = None
    central_estimate: float | None = None
    currency: str | None = None
    currency_year: int | None = None
    geographic_basis: str | None = None
    effective_date: date | None = None
    confidence: float | None = None
    source_claim_ids: tuple[str, ...] = ()
    trace_id: str | None = None


@dataclass(frozen=True)
class EngineeringEvidenceConflict:
    conflict_id: str
    subject: str
    field: str
    candidate_values: tuple[Any, ...]
    source_claim_ids: tuple[str, ...]
    source_tiers: tuple[EvidenceSourceTier, ...]
    dates: tuple[date | None, ...]
    units: tuple[str | None, ...]
    conflict_status: ConflictStatus
    resolution_status: ConflictResolutionStatus
    trace_id: str | None = None


@dataclass(frozen=True)
class EngineeringAssumptionProposal:
    proposal_id: str
    parameter_name: str
    proposed_value: Any
    unit: str | None
    supporting_claim_ids: tuple[str, ...]
    source_tiers: tuple[EvidenceSourceTier, ...]
    confidence: float | None
    conflict_status: ConflictStatus
    promotion_status: ProposalPromotionStatus
    reason: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class EngineeringParameterRegistryEntry:
    native_parameter: str
    expected_type: str
    expected_unit: str | None
    allowed_range: tuple[float | None, float | None] | None
    destination_contract: str
    evidence_supported: bool = True
    automatic_promotion_allowed: bool = False


@dataclass(frozen=True)
class EvidenceRetrievalFilter:
    source_type: EngineeringSourceType | None = None
    source_tier: EvidenceSourceTier | None = None
    manufacturer: str | None = None
    model: str | None = None
    facility: str | None = None
    radionuclide: str | None = None
    date_start: date | None = None
    date_end: date | None = None
    jurisdiction: str | None = None
    parameter_type: str | None = None


@dataclass(frozen=True)
class EvidenceRetrievalResult:
    query: str
    rank: int
    score: float
    document_id: str
    chunk_id: str
    source_id: str
    source_tier: EvidenceSourceTier
    content_reference: str
    trace_id: str | None


@dataclass(frozen=True)
class EngineeringEvidenceQueryResult:
    query: str
    parameter_name: str
    matching_claims: tuple[EngineeringEvidenceClaim, ...]
    source_metadata: tuple[EngineeringEvidenceSource, ...]
    conflicts: tuple[EngineeringEvidenceConflict, ...]
    missing_evidence: bool
    availability_status: Literal["FOUND", "NOT FOUND / NOT NATIVELY AVAILABLE"]


@dataclass(frozen=True)
class ComparableProjectEvidence:
    project_id: str
    facility_name: str | None = None
    location: str | None = None
    project_type: str | None = None
    cyclotron_models: tuple[str, ...] = ()
    cyclotron_count: int | None = None
    scanner_count: int | None = None
    radionuclides: tuple[str, ...] = ()
    facility_area: float | None = None
    guideway_or_transport_system: str | None = None
    capital_cost: EngineeringEvidenceValue | None = None
    operating_cost: EngineeringEvidenceValue | None = None
    completion_year: int | None = None
    source_claim_ids: tuple[str, ...] = ()
    confidence: float | None = None
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceBackedCyclotronModel:
    manufacturer: str
    model: str
    supported_radionuclides: tuple[str, ...]
    beam_energy: EngineeringEvidenceValue | None = None
    production_capabilities: Mapping[str, Any] = field(default_factory=dict)
    footprint: EngineeringEvidenceValue | None = None
    electrical_demand: EngineeringEvidenceValue | None = None
    purchase_cost: EngineeringEvidenceValue | None = None
    annual_opex: EngineeringEvidenceValue | None = None
    source_claim_ids_by_field: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    conflicts_by_field: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    missing_fields: tuple[str, ...] = ()
    catalog_status: CatalogStatus = "draft"

    def to_cyclotron_model_spec(
        self,
        *,
        accepted_fields: Mapping[str, bool] | None = None,
        require_cost_fields: bool = True,
        max_quantity: int = 1,
    ) -> CyclotronModelSpec:
        required_fields = ["manufacturer", "model", "supported_radionuclides", "production_capabilities"]
        if require_cost_fields:
            required_fields.extend(["purchase_cost", "annual_opex"])

        accepted_lookup = dict(accepted_fields or {})
        for field_name in required_fields:
            if field_name in self.missing_fields:
                raise ValueError(f"Cannot convert evidence-backed cyclotron model: missing required field {field_name}")
            if self.conflicts_by_field.get(field_name):
                raise ValueError(f"Cannot convert evidence-backed cyclotron model: unresolved conflict on {field_name}")
            if accepted_lookup.get(field_name) is not True:
                raise ValueError(f"Cannot convert evidence-backed cyclotron model: field {field_name} is not accepted")

        max_streams = int(self.production_capabilities.get("max_simultaneous_production_streams", 1))
        cycle_map = dict(self.production_capabilities.get("production_cycle_minutes_by_radionuclide", {}))
        compatible_sets = tuple(
            frozenset(group) for group in self.production_capabilities.get("simultaneously_compatible_radionuclide_sets", ())
        )
        cyclotron_id = str(self.production_capabilities.get("cyclotron_id", f"{self.manufacturer}-{self.model}"))

        capability = CyclotronProductionCapability(
            cyclotron_id=cyclotron_id,
            supported_radionuclides=tuple(self.supported_radionuclides),
            max_simultaneous_production_streams=max_streams,
            production_cycle_minutes_by_radionuclide=cycle_map,
            simultaneously_compatible_radionuclide_sets=compatible_sets,
        )
        return CyclotronModelSpec(
            model_id=f"{self.manufacturer}-{self.model}",
            capability=capability,
            manufacturer=self.manufacturer,
            model_identifier=self.model,
            min_quantity=0,
            max_quantity=max_quantity,
        )


@dataclass(frozen=True)
class RagToNativeBoundaryAudit:
    trace_id: str
    edge_classification: Mapping[str, RelationshipAuditStatus]


@dataclass(frozen=True)
class ProvenanceChainRecord:
    document_id: str
    chunk_id: str
    claim_id: str
    value_id: str
    proposal_id: str
    accepted_parameter_name: str
    native_mapping: EngineeringParameterRegistryEntry
    trace_id: str


def default_engineering_parameter_registry() -> dict[str, EngineeringParameterRegistryEntry]:
    return {
        "cyclotron_annual_opex_per_unit": EngineeringParameterRegistryEntry(
            native_parameter="cyclotron_annual_opex_per_unit",
            expected_type="float",
            expected_unit="currency/year",
            allowed_range=(0.0, None),
            destination_contract="NativePathwayScenario",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
        "guideway_capex_per_m": EngineeringParameterRegistryEntry(
            native_parameter="guideway_capex_per_m",
            expected_type="float",
            expected_unit="currency/m",
            allowed_range=(0.0, None),
            destination_contract="InfrastructureCapexInputs",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
        "guideway_maintenance_per_m_year": EngineeringParameterRegistryEntry(
            native_parameter="guideway_maintenance_per_m_year",
            expected_type="float",
            expected_unit="currency/m/year",
            allowed_range=(0.0, None),
            destination_contract="InfrastructureOpexInputs",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
        "electricity_cost_per_kwh": EngineeringParameterRegistryEntry(
            native_parameter="electricity_cost_per_kwh",
            expected_type="float",
            expected_unit="currency/kWh",
            allowed_range=(0.0, None),
            destination_contract="NativePathwayScenario",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
        "annual_mrt_energy_kwh": EngineeringParameterRegistryEntry(
            native_parameter="annual_mrt_energy_kwh",
            expected_type="float",
            expected_unit="kWh/year",
            allowed_range=(0.0, None),
            destination_contract="NativePathwayScenario",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
        "installed_guideway_length_m": EngineeringParameterRegistryEntry(
            native_parameter="installed_guideway_length_m",
            expected_type="float",
            expected_unit="m",
            allowed_range=(0.0, None),
            destination_contract="NativePathwayScenario",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
        "installed_mrt_endpoints": EngineeringParameterRegistryEntry(
            native_parameter="installed_mrt_endpoints",
            expected_type="int",
            expected_unit="count",
            allowed_range=(0.0, None),
            destination_contract="NativePathwayScenario",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
        "installed_mrt_carriers": EngineeringParameterRegistryEntry(
            native_parameter="installed_mrt_carriers",
            expected_type="int",
            expected_unit="count",
            allowed_range=(0.0, None),
            destination_contract="NativePathwayScenario",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
        "scanners": EngineeringParameterRegistryEntry(
            native_parameter="scanners",
            expected_type="int",
            expected_unit="count",
            allowed_range=(1.0, None),
            destination_contract="NativePathwayScenario",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
        "uptake_resources": EngineeringParameterRegistryEntry(
            native_parameter="uptake_resources",
            expected_type="int",
            expected_unit="count",
            allowed_range=(1.0, None),
            destination_contract="NativePathwayScenario",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
        "injection_resources": EngineeringParameterRegistryEntry(
            native_parameter="injection_resources",
            expected_type="int",
            expected_unit="count",
            allowed_range=(1.0, None),
            destination_contract="NativePathwayScenario",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
        "installed_cyclotron_units": EngineeringParameterRegistryEntry(
            native_parameter="installed_cyclotron_units",
            expected_type="int",
            expected_unit="count",
            allowed_range=(0.0, None),
            destination_contract="NativePathwayScenario",
            evidence_supported=True,
            automatic_promotion_allowed=False,
        ),
    }


class EngineeringEvidenceRepository:
    def __init__(self, *, parameter_registry: Mapping[str, EngineeringParameterRegistryEntry] | None = None) -> None:
        self.sources: dict[str, EngineeringEvidenceSource] = {}
        self.documents: dict[str, EngineeringEvidenceDocument] = {}
        self.chunks: dict[str, EngineeringEvidenceChunk] = {}
        self.claims: dict[str, EngineeringEvidenceClaim] = {}
        self.values: dict[str, EngineeringEvidenceValue] = {}
        self.conflicts: dict[str, EngineeringEvidenceConflict] = {}
        self.proposals: dict[str, EngineeringAssumptionProposal] = {}
        self.parameter_registry = dict(parameter_registry or default_engineering_parameter_registry())

    def register_source(
        self,
        *,
        source_type: EngineeringSourceType,
        title: str,
        source_id: str | None = None,
        publisher_or_organization: str | None = None,
        author: str | None = None,
        publication_date: date | None = None,
        retrieved_at: datetime | None = None,
        url_or_locator: str | None = None,
        document_identifier: str | None = None,
        version: str | None = None,
        jurisdiction: str | None = None,
        language: str | None = None,
        source_tier: EvidenceSourceTier | None = None,
        source_quality: SourceQuality = "unknown",
        source_status: SourceStatus = "unknown",
        notes: str | None = None,
        trace_id: str | None = None,
    ) -> EngineeringEvidenceSource:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("source title must be non-empty")
        resolved_tier = classify_source_tier(source_type) if source_tier is None else source_tier
        computed_id = source_id or _stable_id(
            "src",
            {
                "source_type": source_type,
                "title": normalized_title,
                "publisher_or_organization": publisher_or_organization,
                "document_identifier": document_identifier,
                "url_or_locator": url_or_locator,
                "version": version,
            },
        )
        source = EngineeringEvidenceSource(
            source_id=computed_id,
            source_type=source_type,
            title=normalized_title,
            publisher_or_organization=publisher_or_organization,
            author=author,
            publication_date=publication_date,
            retrieved_at=retrieved_at,
            url_or_locator=url_or_locator,
            document_identifier=document_identifier,
            version=version,
            jurisdiction=jurisdiction,
            language=language,
            source_tier=resolved_tier,
            source_quality=source_quality,
            source_status=source_status,
            notes=notes,
            trace_id=trace_id,
        )
        self.sources[source.source_id] = source
        return source

    def register_document(
        self,
        *,
        source_id: str,
        title: str,
        format: DocumentFormat,
        content: str | None = None,
        document_id: str | None = None,
        document_identifier: str | None = None,
        url_or_locator: str | None = None,
        version: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> EngineeringEvidenceDocument:
        if source_id not in self.sources:
            raise ValueError(f"unknown source_id: {source_id}")
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("document title must be non-empty")
        fingerprint = hashlib.sha256((content or "").encode("utf-8")).hexdigest() if content is not None else None
        payload = {
            "source_id": source_id,
            "title": normalized_title,
            "format": format,
            "document_identifier": document_identifier,
            "url_or_locator": url_or_locator,
            "version": version,
            "content_fingerprint": fingerprint,
        }
        computed_id = document_id or _stable_id("doc", payload)

        # Deterministic duplicate control: same computed identity returns the existing object.
        if computed_id in self.documents:
            return self.documents[computed_id]

        document = EngineeringEvidenceDocument(
            document_id=computed_id,
            source_id=source_id,
            title=normalized_title,
            format=format,
            document_identifier=document_identifier,
            url_or_locator=url_or_locator,
            version=version,
            metadata=dict(metadata or {}),
            content_fingerprint=fingerprint,
            trace_id=trace_id,
        )
        self.documents[document.document_id] = document
        return document

    def register_chunk(
        self,
        *,
        document_id: str,
        content: str,
        chunk_id: str | None = None,
        page_reference: str | None = None,
        section_reference: str | None = None,
        char_start: int | None = None,
        char_end: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> EngineeringEvidenceChunk:
        if document_id not in self.documents:
            raise ValueError(f"unknown document_id: {document_id}")
        if not content:
            raise ValueError("chunk content must be non-empty")
        document = self.documents[document_id]
        computed_id = chunk_id or _stable_id(
            "chk",
            {
                "document_id": document_id,
                "content": content,
                "page_reference": page_reference,
                "section_reference": section_reference,
                "char_start": char_start,
                "char_end": char_end,
            },
        )
        if computed_id in self.chunks:
            return self.chunks[computed_id]
        chunk = EngineeringEvidenceChunk(
            chunk_id=computed_id,
            document_id=document_id,
            source_id=document.source_id,
            content=content,
            page_reference=page_reference,
            section_reference=section_reference,
            char_start=char_start,
            char_end=char_end,
            metadata=dict(metadata or {}),
            trace_id=trace_id,
        )
        self.chunks[chunk.chunk_id] = chunk
        return chunk

    def register_plain_text_chunks(
        self,
        *,
        document_id: str,
        content: str,
        chunk_size: int = 500,
        overlap: int = 100,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[EngineeringEvidenceChunk, ...]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size")
        if not content:
            return ()

        chunks: list[EngineeringEvidenceChunk] = []
        start = 0
        while start < len(content):
            end = min(len(content), start + chunk_size)
            block = content[start:end]
            chunk = self.register_chunk(
                document_id=document_id,
                content=block,
                char_start=start,
                char_end=end,
                metadata=metadata,
            )
            chunks.append(chunk)
            if end == len(content):
                break
            start = end - overlap
        return tuple(chunks)

    def register_claim(
        self,
        *,
        source_id: str,
        claim_type: ClaimType,
        subject: str,
        predicate: str,
        raw_value: Any,
        normalized_value: Any,
        unit: str | None,
        claim_id: str | None = None,
        document_id: str | None = None,
        chunk_id: str | None = None,
        quoted_or_extracted_text_reference: str | None = None,
        confidence: float | None = None,
        source_tier: EvidenceSourceTier | None = None,
        verification_status: VerificationStatus = "unverified",
        conflict_status: ConflictStatus = "unknown",
        parameter_type: str | None = None,
        trace_id: str | None = None,
    ) -> EngineeringEvidenceClaim:
        if source_id not in self.sources:
            raise ValueError(f"unknown source_id: {source_id}")
        if document_id is not None and document_id not in self.documents:
            raise ValueError(f"unknown document_id: {document_id}")
        if chunk_id is not None and chunk_id not in self.chunks:
            raise ValueError(f"unknown chunk_id: {chunk_id}")
        if not subject.strip() or not predicate.strip():
            raise ValueError("subject and predicate must be non-empty")

        resolved_tier = source_tier or self.sources[source_id].source_tier
        computed_id = claim_id or _stable_id(
            "clm",
            {
                "source_id": source_id,
                "document_id": document_id,
                "chunk_id": chunk_id,
                "subject": subject,
                "predicate": predicate,
                "normalized_value": normalized_value,
                "unit": unit,
            },
        )
        claim = EngineeringEvidenceClaim(
            claim_id=computed_id,
            source_id=source_id,
            document_id=document_id,
            chunk_id=chunk_id,
            claim_type=claim_type,
            subject=subject,
            predicate=predicate,
            raw_value=raw_value,
            normalized_value=normalized_value,
            unit=unit,
            quoted_or_extracted_text_reference=quoted_or_extracted_text_reference,
            confidence=confidence,
            source_tier=resolved_tier,
            verification_status=verification_status,
            conflict_status=conflict_status,
            parameter_type=parameter_type,
            trace_id=trace_id,
        )
        self.claims[claim.claim_id] = claim
        return claim

    def register_value(
        self,
        *,
        parameter_name: str,
        source_claim_ids: Sequence[str],
        value: float | str | bool | None = None,
        unit: str | None = None,
        value_type: ValueType = "unknown",
        minimum: float | None = None,
        maximum: float | None = None,
        central_estimate: float | None = None,
        currency: str | None = None,
        currency_year: int | None = None,
        geographic_basis: str | None = None,
        effective_date: date | None = None,
        confidence: float | None = None,
        value_id: str | None = None,
        trace_id: str | None = None,
    ) -> EngineeringEvidenceValue:
        if not parameter_name.strip():
            raise ValueError("parameter_name must be non-empty")
        claim_ids = tuple(source_claim_ids)
        if not claim_ids:
            raise ValueError("source_claim_ids must not be empty")
        for claim_id in claim_ids:
            if claim_id not in self.claims:
                raise ValueError(f"unknown claim_id in source_claim_ids: {claim_id}")

        if currency is not None and currency_year is None:
            # Missing currency year stays explicit and should be flagged by callers/tests.
            pass

        computed_id = value_id or _stable_id(
            "val",
            {
                "parameter_name": parameter_name,
                "source_claim_ids": claim_ids,
                "value": value,
                "unit": unit,
                "minimum": minimum,
                "maximum": maximum,
                "central_estimate": central_estimate,
                "currency": currency,
                "currency_year": currency_year,
            },
        )
        evidence_value = EngineeringEvidenceValue(
            value_id=computed_id,
            parameter_name=parameter_name,
            value=value,
            unit=unit,
            value_type=value_type,
            minimum=minimum,
            maximum=maximum,
            central_estimate=central_estimate,
            currency=currency,
            currency_year=currency_year,
            geographic_basis=geographic_basis,
            effective_date=effective_date,
            confidence=confidence,
            source_claim_ids=claim_ids,
            trace_id=trace_id,
        )
        self.values[evidence_value.value_id] = evidence_value
        return evidence_value

    def detect_conflicts(self, *, subject: str, field: str) -> tuple[EngineeringEvidenceConflict, ...]:
        candidates = [claim for claim in self.claims.values() if claim.subject == subject and claim.predicate == field]
        if len(candidates) < 2:
            return ()

        units = {claim.unit for claim in candidates}
        values = tuple(claim.normalized_value for claim in candidates)
        claim_ids = tuple(claim.claim_id for claim in candidates)
        tiers = tuple(claim.source_tier for claim in candidates)
        dates = tuple(self.sources[claim.source_id].publication_date for claim in candidates)

        if len(units) > 1:
            conflict = EngineeringEvidenceConflict(
                conflict_id=_stable_id("cnf", {"subject": subject, "field": field, "claims": claim_ids, "reason": "unit-mismatch"}),
                subject=subject,
                field=field,
                candidate_values=values,
                source_claim_ids=claim_ids,
                source_tiers=tiers,
                dates=dates,
                units=tuple(units),
                conflict_status="not_comparable",
                resolution_status="not_comparable",
            )
            self.conflicts[conflict.conflict_id] = conflict
            for claim in candidates:
                self.claims[claim.claim_id] = replace(claim, conflict_status="not_comparable")
            return (conflict,)

        distinct_values = {json.dumps(value, sort_keys=True, default=str) for value in values}
        if len(distinct_values) <= 1:
            for claim in candidates:
                self.claims[claim.claim_id] = replace(claim, conflict_status="none")
            return ()

        conflict = EngineeringEvidenceConflict(
            conflict_id=_stable_id("cnf", {"subject": subject, "field": field, "claims": claim_ids, "reason": "value-mismatch"}),
            subject=subject,
            field=field,
            candidate_values=values,
            source_claim_ids=claim_ids,
            source_tiers=tiers,
            dates=dates,
            units=tuple(units),
            conflict_status="conflict",
            resolution_status="unresolved",
        )
        self.conflicts[conflict.conflict_id] = conflict
        for claim in candidates:
            self.claims[claim.claim_id] = replace(claim, conflict_status="conflict")
        return (conflict,)

    def register_assumption_proposal(
        self,
        *,
        parameter_name: str,
        proposed_value: Any,
        unit: str | None,
        supporting_claim_ids: Sequence[str],
        confidence: float | None,
        promotion_status: ProposalPromotionStatus = "candidate",
        reason: str | None = None,
        proposal_id: str | None = None,
        trace_id: str | None = None,
    ) -> EngineeringAssumptionProposal:
        claim_ids = tuple(supporting_claim_ids)
        if not claim_ids:
            raise ValueError("supporting_claim_ids must not be empty")
        source_tiers: list[EvidenceSourceTier] = []
        aggregate_conflict_status: ConflictStatus = "none"
        for claim_id in claim_ids:
            claim = self.claims.get(claim_id)
            if claim is None:
                raise ValueError(f"unknown supporting claim_id: {claim_id}")
            if claim.source_id not in self.sources:
                raise ValueError("claim without source lineage cannot be promoted")
            source_tiers.append(claim.source_tier)
            if claim.conflict_status == "conflict":
                aggregate_conflict_status = "conflict"
            elif claim.conflict_status == "not_comparable" and aggregate_conflict_status != "conflict":
                aggregate_conflict_status = "not_comparable"

        computed_id = proposal_id or _stable_id(
            "prp",
            {
                "parameter_name": parameter_name,
                "proposed_value": proposed_value,
                "unit": unit,
                "supporting_claim_ids": claim_ids,
            },
        )
        proposal = EngineeringAssumptionProposal(
            proposal_id=computed_id,
            parameter_name=parameter_name,
            proposed_value=proposed_value,
            unit=unit,
            supporting_claim_ids=claim_ids,
            source_tiers=tuple(source_tiers),
            confidence=confidence,
            conflict_status=aggregate_conflict_status,
            promotion_status=promotion_status,
            reason=reason,
            trace_id=trace_id,
        )
        self.proposals[proposal.proposal_id] = proposal
        return proposal

    def update_proposal_status(
        self,
        *,
        proposal_id: str,
        promotion_status: ProposalPromotionStatus,
        reason: str | None = None,
    ) -> EngineeringAssumptionProposal:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"unknown proposal_id: {proposal_id}")

        if promotion_status == "accepted" and proposal.conflict_status in {"conflict", "not_comparable"}:
            raise ValueError("unresolved conflict cannot be promoted automatically")

        updated = replace(proposal, promotion_status=promotion_status, reason=reason or proposal.reason)
        self.proposals[proposal_id] = updated
        return updated

    def build_native_parameter_overrides(self) -> dict[str, Any]:
        overrides: dict[str, Any] = {}
        for proposal in self.proposals.values():
            if proposal.promotion_status != "accepted":
                continue
            if proposal.conflict_status in {"conflict", "not_comparable"}:
                raise ValueError("unresolved conflict cannot be converted to native parameter overrides")
            entry = self.parameter_registry.get(proposal.parameter_name)
            if entry is None:
                raise ValueError(f"proposal parameter is not in engineering parameter registry: {proposal.parameter_name}")
            if proposal.unit is not None and entry.expected_unit is not None and proposal.unit != entry.expected_unit:
                raise ValueError(
                    f"unsupported unit conversion for {proposal.parameter_name}: expected {entry.expected_unit}, got {proposal.unit}"
                )
            if entry.allowed_range is not None and isinstance(proposal.proposed_value, (int, float)):
                lower, upper = entry.allowed_range
                numeric = float(proposal.proposed_value)
                if lower is not None and numeric < float(lower):
                    raise ValueError(f"proposal value for {proposal.parameter_name} is below native minimum")
                if upper is not None and numeric > float(upper):
                    raise ValueError(f"proposal value for {proposal.parameter_name} is above native maximum")
            overrides[proposal.parameter_name] = proposal.proposed_value
        return overrides

    def retrieve(
        self,
        *,
        query: str,
        filters: EvidenceRetrievalFilter | None = None,
    ) -> tuple[EvidenceRetrievalResult, ...]:
        query_tokens = set(_tokenize(query))
        applied_filters = filters or EvidenceRetrievalFilter()
        results: list[EvidenceRetrievalResult] = []

        for chunk in self.chunks.values():
            source = self.sources[chunk.source_id]
            document = self.documents[chunk.document_id]

            if applied_filters.source_type is not None and source.source_type != applied_filters.source_type:
                continue
            if applied_filters.source_tier is not None and source.source_tier != applied_filters.source_tier:
                continue
            if applied_filters.jurisdiction is not None and source.jurisdiction != applied_filters.jurisdiction:
                continue
            if applied_filters.date_start is not None:
                if source.publication_date is None or source.publication_date < applied_filters.date_start:
                    continue
            if applied_filters.date_end is not None:
                if source.publication_date is None or source.publication_date > applied_filters.date_end:
                    continue
            if applied_filters.manufacturer is not None and chunk.metadata.get("manufacturer") != applied_filters.manufacturer:
                continue
            if applied_filters.model is not None and chunk.metadata.get("model") != applied_filters.model:
                continue
            if applied_filters.facility is not None and chunk.metadata.get("facility") != applied_filters.facility:
                continue
            if applied_filters.radionuclide is not None and chunk.metadata.get("radionuclide") != applied_filters.radionuclide:
                continue
            if applied_filters.parameter_type is not None and chunk.metadata.get("parameter_type") != applied_filters.parameter_type:
                continue

            chunk_tokens = set(_tokenize(chunk.content))
            overlap = query_tokens.intersection(chunk_tokens)
            score = float(len(overlap))
            if query.lower() in chunk.content.lower():
                score += 2.0

            domain_hints = {
                "cyclotron": "cyclotron",
                "carrier": "carrier",
                "guideway": "guideway",
            }
            for token, parameter_domain in domain_hints.items():
                if token in query_tokens and chunk.metadata.get("domain") == parameter_domain:
                    score += 1.5

            if score <= 0.0:
                continue

            section = chunk.section_reference or document.title
            results.append(
                EvidenceRetrievalResult(
                    query=query,
                    rank=0,
                    score=score,
                    document_id=document.document_id,
                    chunk_id=chunk.chunk_id,
                    source_id=source.source_id,
                    source_tier=source.source_tier,
                    content_reference=section,
                    trace_id=chunk.trace_id,
                )
            )

        ordered = sorted(
            results,
            key=lambda item: (
                -item.score,
                _tier_rank(item.source_tier),
                item.document_id,
                item.chunk_id,
                item.source_id,
            ),
        )
        ranked: list[EvidenceRetrievalResult] = []
        for index, item in enumerate(ordered, start=1):
            ranked.append(replace(item, rank=index))
        return tuple(ranked)

    def query_evidence(
        self,
        *,
        parameter_name: str,
        subject: str | None = None,
        filters: EvidenceRetrievalFilter | None = None,
    ) -> EngineeringEvidenceQueryResult:
        matches = [
            claim
            for claim in self.claims.values()
            if (
                claim.predicate == parameter_name
                or claim.parameter_type == parameter_name
                or claim.claim_type == parameter_name
            )
            and (subject is None or claim.subject == subject)
        ]

        if filters is not None:
            filtered: list[EngineeringEvidenceClaim] = []
            for claim in matches:
                source = self.sources[claim.source_id]
                if filters.source_type is not None and source.source_type != filters.source_type:
                    continue
                if filters.source_tier is not None and source.source_tier != filters.source_tier:
                    continue
                if filters.jurisdiction is not None and source.jurisdiction != filters.jurisdiction:
                    continue
                filtered.append(claim)
            matches = filtered

        conflict_hits = tuple(
            conflict
            for conflict in self.conflicts.values()
            if conflict.field == parameter_name and (subject is None or conflict.subject == subject)
        )
        sources = tuple(self.sources[claim.source_id] for claim in matches)

        return EngineeringEvidenceQueryResult(
            query=f"parameter={parameter_name};subject={subject or '*'}",
            parameter_name=parameter_name,
            matching_claims=tuple(matches),
            source_metadata=sources,
            conflicts=conflict_hits,
            missing_evidence=(len(matches) == 0),
            availability_status="FOUND" if matches else "NOT FOUND / NOT NATIVELY AVAILABLE",
        )

    def audit_rag_to_native_boundary(self) -> RagToNativeBoundaryAudit:
        documents_to_source: RelationshipAuditStatus = "DIRECT NATIVE CONNECTION"
        if not self.documents:
            documents_to_source = "NOT CONNECTED"
        elif any(document.source_id not in self.sources for document in self.documents.values()):
            documents_to_source = "PARTIAL CONNECTION"

        source_to_claim: RelationshipAuditStatus = "DIRECT NATIVE CONNECTION"
        if not self.claims:
            source_to_claim = "NOT CONNECTED"
        elif any(claim.source_id not in self.sources for claim in self.claims.values()):
            source_to_claim = "PARTIAL CONNECTION"

        claim_to_value: RelationshipAuditStatus = "DIRECT NATIVE CONNECTION"
        if not self.values:
            claim_to_value = "NOT CONNECTED"
        elif any(any(claim_id not in self.claims for claim_id in value.source_claim_ids) for value in self.values.values()):
            claim_to_value = "PARTIAL CONNECTION"

        value_to_proposal: RelationshipAuditStatus = "DIRECT NATIVE CONNECTION" if self.proposals else "NOT CONNECTED"

        accepted = [proposal for proposal in self.proposals.values() if proposal.promotion_status == "accepted"]
        proposal_to_accepted: RelationshipAuditStatus = "DIRECT NATIVE CONNECTION" if accepted else ("PARTIAL CONNECTION" if self.proposals else "NOT CONNECTED")

        accepted_to_native_field: RelationshipAuditStatus = "NOT CONNECTED"
        if accepted:
            mapped_count = sum(1 for proposal in accepted if proposal.parameter_name in self.parameter_registry)
            if mapped_count == len(accepted):
                accepted_to_native_field = "DIRECT NATIVE CONNECTION"
            elif mapped_count > 0:
                accepted_to_native_field = "PARTIAL CONNECTION"

        native_to_calculation: RelationshipAuditStatus = (
            "NATIVE BOUNDED ORCHESTRATION" if accepted_to_native_field in {"DIRECT NATIVE CONNECTION", "PARTIAL CONNECTION"} else "NOT CONNECTED"
        )
        calculation_to_report: RelationshipAuditStatus = (
            "NATIVE BOUNDED ORCHESTRATION" if native_to_calculation != "NOT CONNECTED" else "NOT CONNECTED"
        )

        edges: dict[str, RelationshipAuditStatus] = {
            "retrieved document -> evidence source": documents_to_source,
            "evidence source -> claim": source_to_claim,
            "claim -> normalized value": claim_to_value,
            "normalized value -> assumption proposal": value_to_proposal,
            "assumption proposal -> accepted assumption": proposal_to_accepted,
            "accepted assumption -> native model field": accepted_to_native_field,
            "native field -> native calculation": native_to_calculation,
            "native calculation -> report": calculation_to_report,
        }
        return RagToNativeBoundaryAudit(trace_id=_stable_id("aud", {"edges": edges}), edge_classification=edges)

    def build_provenance_chain(
        self,
        *,
        proposal_id: str,
        parameter_name: str,
    ) -> ProvenanceChainRecord:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"unknown proposal_id: {proposal_id}")
        if proposal.promotion_status != "accepted":
            raise ValueError("proposal must be accepted to build provenance chain")
        if proposal.parameter_name != parameter_name:
            raise ValueError("parameter_name does not match proposal")

        first_claim = self.claims[proposal.supporting_claim_ids[0]]
        if first_claim.document_id is None or first_claim.chunk_id is None:
            raise ValueError("cannot build provenance chain without claim document/chunk lineage")

        value_match = next(
            (value for value in self.values.values() if proposal.supporting_claim_ids[0] in value.source_claim_ids and value.parameter_name == parameter_name),
            None,
        )
        if value_match is None:
            raise ValueError("no normalized evidence value links the supporting claim to the proposal")

        mapping = self.parameter_registry.get(parameter_name)
        if mapping is None:
            raise ValueError(f"parameter {parameter_name} is not mapped in engineering parameter registry")

        trace_payload = {
            "document_id": first_claim.document_id,
            "chunk_id": first_claim.chunk_id,
            "claim_id": first_claim.claim_id,
            "value_id": value_match.value_id,
            "proposal_id": proposal_id,
            "parameter_name": parameter_name,
        }
        return ProvenanceChainRecord(
            document_id=first_claim.document_id,
            chunk_id=first_claim.chunk_id,
            claim_id=first_claim.claim_id,
            value_id=value_match.value_id,
            proposal_id=proposal_id,
            accepted_parameter_name=parameter_name,
            native_mapping=mapping,
            trace_id=_stable_id("chn", trace_payload),
        )

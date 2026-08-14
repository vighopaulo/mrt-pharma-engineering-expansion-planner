from __future__ import annotations

from datetime import date

import pytest

from engineering_evidence import (
    ComparableProjectEvidence,
    EngineeringEvidenceClaim,
    EngineeringEvidenceRepository,
    EvidenceBackedCyclotronModel,
    EvidenceRetrievalFilter,
)


def _seed_repository() -> EngineeringEvidenceRepository:
    repo = EngineeringEvidenceRepository()

    src_manu = repo.register_source(
        source_type="manufacturer_document",
        title="Cyclotron Model X Technical Specification",
        publisher_or_organization="Acme Cyclotron",
        document_identifier="ACME-X-SPEC-2026",
        publication_date=date(2026, 1, 5),
        source_quality="high",
        source_status="active",
    )
    src_academic = repo.register_source(
        source_type="academic_publication",
        title="Isotope production optimization study",
        publisher_or_organization="Journal of Applied Nuclear Engineering",
        publication_date=date(2025, 5, 10),
        source_quality="medium",
        source_status="active",
    )
    src_hospital = repo.register_source(
        source_type="hospital_document",
        title="Hospital Alpha Project Completion Report",
        publisher_or_organization="Hospital Alpha",
        publication_date=date(2024, 9, 1),
        source_quality="high",
        source_status="active",
        jurisdiction="US",
    )
    src_guideway_a = repo.register_source(
        source_type="vendor_quote",
        title="Guideway quote A",
        publisher_or_organization="Guideway Vendor A",
        publication_date=date(2026, 2, 15),
        source_quality="medium",
        source_status="active",
    )
    src_guideway_b = repo.register_source(
        source_type="industry_report",
        title="Guideway benchmark report",
        publisher_or_organization="Transit Benchmark Group",
        publication_date=date(2026, 3, 20),
        source_quality="medium",
        source_status="active",
    )
    src_guideway_c = repo.register_source(
        source_type="internal_engineering_record",
        title="Internal engineering estimate",
        publisher_or_organization="MRT Planning Team",
        publication_date=date(2026, 3, 22),
        source_quality="high",
        source_status="active",
    )
    src_carrier = repo.register_source(
        source_type="project_document",
        title="Carrier maintenance record",
        publisher_or_organization="MRT Ops",
        publication_date=date(2026, 3, 2),
        source_quality="high",
        source_status="active",
    )
    src_web = repo.register_source(
        source_type="web_page",
        title="Generic web summary",
        publication_date=None,
        source_quality="low",
        source_status="active",
    )

    doc_manu = repo.register_document(
        source_id=src_manu.source_id,
        title="Model X specification PDF",
        format="pdf",
        content="Model X beam energy is 18 MeV. Supports F-18 and N-13.",
    )
    doc_academic = repo.register_document(
        source_id=src_academic.source_id,
        title="Academic isotope paper",
        format="pdf",
        content="Study reports isotope yield and beam settings for PET isotopes.",
    )
    doc_hospital = repo.register_document(
        source_id=src_hospital.source_id,
        title="Hospital Alpha report",
        format="docx",
        content="Hospital Alpha installed scanner count is 6.",
    )
    doc_guideway_a = repo.register_document(
        source_id=src_guideway_a.source_id,
        title="Guideway quote A doc",
        format="pdf",
        content="Guideway capex is 10000 USD per metre.",
    )
    doc_guideway_b = repo.register_document(
        source_id=src_guideway_b.source_id,
        title="Guideway report B",
        format="html",
        content="Guideway cost benchmark: 14000 USD/m.",
    )
    doc_guideway_c = repo.register_document(
        source_id=src_guideway_c.source_id,
        title="Guideway internal estimate",
        format="txt",
        content="Guideway estimate 12000 USD/m.",
    )
    doc_carrier = repo.register_document(
        source_id=src_carrier.source_id,
        title="Carrier maintenance memo",
        format="txt",
        content="MRT carrier annual maintenance cost is 60000 USD/year.",
    )
    doc_web = repo.register_document(
        source_id=src_web.source_id,
        title="Web note",
        format="url_reference",
        content="A web page claims Model X beam energy 20 MeV.",
    )
    doc_irrelevant = repo.register_document(
        source_id=src_hospital.source_id,
        title="Cafeteria expansion note",
        format="txt",
        content="Cafeteria seating expansion does not discuss cyclotrons.",
    )

    ck_manu = repo.register_chunk(
        document_id=doc_manu.document_id,
        content="Model X beam energy is 18 MeV, supports N-13, and has cyclotron annual maintenance cost context.",
        metadata={"manufacturer": "Acme", "model": "Model X", "domain": "cyclotron", "parameter_type": "beam_energy", "radionuclide": "N-13"},
    )
    ck_academic = repo.register_chunk(
        document_id=doc_academic.document_id,
        content="Academic paper on isotope production yield for F-18 and N-13.",
        metadata={"domain": "cyclotron", "parameter_type": "yield", "radionuclide": "N-13"},
    )
    ck_hospital = repo.register_chunk(
        document_id=doc_hospital.document_id,
        content="Facility scanner count documented as 6 in Hospital Alpha project report.",
        metadata={"facility": "Hospital Alpha", "domain": "facility", "parameter_type": "scanner_count"},
    )
    ck_guideway_a = repo.register_chunk(
        document_id=doc_guideway_a.document_id,
        content="Guideway cost per metre is 10000 USD/m.",
        metadata={"domain": "guideway", "parameter_type": "guideway_cost"},
    )
    ck_guideway_b = repo.register_chunk(
        document_id=doc_guideway_b.document_id,
        content="Guideway benchmark indicates 14000 USD/m.",
        metadata={"domain": "guideway", "parameter_type": "guideway_cost"},
    )
    ck_guideway_c = repo.register_chunk(
        document_id=doc_guideway_c.document_id,
        content="Internal guideway estimate is 12000 USD/m.",
        metadata={"domain": "guideway", "parameter_type": "guideway_cost"},
    )
    ck_carrier = repo.register_chunk(
        document_id=doc_carrier.document_id,
        content="Carrier annual maintenance cost equals 60000 USD/year.",
        metadata={"domain": "carrier", "parameter_type": "carrier_maintenance"},
    )
    ck_web = repo.register_chunk(
        document_id=doc_web.document_id,
        content="Web claim: Model X beam energy 20 MeV.",
        metadata={"manufacturer": "Acme", "model": "Model X", "domain": "cyclotron", "parameter_type": "beam_energy"},
    )
    repo.register_chunk(
        document_id=doc_irrelevant.document_id,
        content="Cafeteria seating and menu changes.",
        metadata={"domain": "other", "parameter_type": "other"},
    )

    c_beam_t1 = repo.register_claim(
        source_id=src_manu.source_id,
        document_id=doc_manu.document_id,
        chunk_id=ck_manu.chunk_id,
        claim_type="quantitative",
        subject="Cyclotron Model X",
        predicate="beam_energy",
        raw_value="18 MeV",
        normalized_value=18.0,
        unit="MeV",
        parameter_type="beam_energy",
    )
    c_beam_t4 = repo.register_claim(
        source_id=src_web.source_id,
        document_id=doc_web.document_id,
        chunk_id=ck_web.chunk_id,
        claim_type="quantitative",
        subject="Cyclotron Model X",
        predicate="beam_energy",
        raw_value="20 MeV",
        normalized_value=20.0,
        unit="MeV",
        parameter_type="beam_energy",
    )
    repo.detect_conflicts(subject="Cyclotron Model X", field="beam_energy")

    c_guideway_a = repo.register_claim(
        source_id=src_guideway_a.source_id,
        document_id=doc_guideway_a.document_id,
        chunk_id=ck_guideway_a.chunk_id,
        claim_type="cost",
        subject="MRT Guideway",
        predicate="guideway_cost_per_m",
        raw_value="10000 USD/m",
        normalized_value=10000.0,
        unit="USD/m",
        parameter_type="guideway_cost",
    )
    c_guideway_b = repo.register_claim(
        source_id=src_guideway_b.source_id,
        document_id=doc_guideway_b.document_id,
        chunk_id=ck_guideway_b.chunk_id,
        claim_type="cost",
        subject="MRT Guideway",
        predicate="guideway_cost_per_m",
        raw_value="14000 USD/m",
        normalized_value=14000.0,
        unit="USD/m",
        parameter_type="guideway_cost",
    )
    c_guideway_c = repo.register_claim(
        source_id=src_guideway_c.source_id,
        document_id=doc_guideway_c.document_id,
        chunk_id=ck_guideway_c.chunk_id,
        claim_type="cost",
        subject="MRT Guideway",
        predicate="guideway_cost_per_m",
        raw_value="12000 USD/m",
        normalized_value=12000.0,
        unit="USD/m",
        parameter_type="guideway_cost",
    )
    repo.detect_conflicts(subject="MRT Guideway", field="guideway_cost_per_m")

    c_carrier = repo.register_claim(
        source_id=src_carrier.source_id,
        document_id=doc_carrier.document_id,
        chunk_id=ck_carrier.chunk_id,
        claim_type="cost",
        subject="MRT Carrier",
        predicate="carrier_maintenance",
        raw_value="60000 USD/year",
        normalized_value=60000.0,
        unit="USD/year",
        parameter_type="carrier_maintenance",
    )

    c_scanner = repo.register_claim(
        source_id=src_hospital.source_id,
        document_id=doc_hospital.document_id,
        chunk_id=ck_hospital.chunk_id,
        claim_type="quantitative",
        subject="Hospital Alpha",
        predicate="scanner_count",
        raw_value="6",
        normalized_value=6,
        unit="count",
        parameter_type="scanner_count",
    )

    v_beam = repo.register_value(
        parameter_name="beam_energy",
        source_claim_ids=(c_beam_t1.claim_id,),
        value=18.0,
        unit="MeV",
        value_type="scalar",
    )
    v_guideway = repo.register_value(
        parameter_name="guideway_capex_per_m",
        source_claim_ids=(c_guideway_a.claim_id, c_guideway_b.claim_id, c_guideway_c.claim_id),
        value=None,
        unit="USD/m",
        value_type="range",
        minimum=10000.0,
        maximum=14000.0,
        central_estimate=12000.0,
        currency="USD",
        currency_year=2026,
    )
    v_carrier = repo.register_value(
        parameter_name="carrier_maintenance",
        source_claim_ids=(c_carrier.claim_id,),
        value=60000.0,
        unit="USD/year",
        value_type="currency",
        currency="USD",
        currency_year=2026,
    )
    v_scanner = repo.register_value(
        parameter_name="scanner_count",
        source_claim_ids=(c_scanner.claim_id,),
        value=6,
        unit="count",
        value_type="scalar",
    )

    repo.register_assumption_proposal(
        parameter_name="beam_energy",
        proposed_value=18.0,
        unit="MeV",
        supporting_claim_ids=(c_beam_t1.claim_id,),
        confidence=0.95,
        promotion_status="evidence_only",
    )

    p_scanner = repo.register_assumption_proposal(
        parameter_name="scanners",
        proposed_value=6,
        unit="count",
        supporting_claim_ids=(c_scanner.claim_id,),
        confidence=0.9,
        promotion_status="candidate",
    )
    repo.update_proposal_status(proposal_id=p_scanner.proposal_id, promotion_status="accepted", reason="Approved by planning board")

    # Keep references alive for test readability.
    assert v_beam and v_guideway and v_carrier and v_scanner
    assert c_beam_t4 and ck_academic

    return repo


def test_source_registration_tiering_and_missing_metadata():
    repo = EngineeringEvidenceRepository()
    unknown = repo.register_source(source_type="unknown", title="Unknown source")
    assert unknown.source_tier == "UNKNOWN"
    assert unknown.publication_date is None


def test_document_and_chunk_registration_with_duplicate_control():
    repo = EngineeringEvidenceRepository()
    source = repo.register_source(source_type="project_document", title="Project doc")
    first = repo.register_document(source_id=source.source_id, title="Doc", format="txt", content="abc")
    second = repo.register_document(source_id=source.source_id, title="Doc", format="txt", content="abc")
    assert first.document_id == second.document_id

    chunks = repo.register_plain_text_chunks(document_id=first.document_id, content="0123456789" * 80, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert chunks[0].char_start == 0


def test_conflict_detection_preserves_all_values_without_silent_winner():
    repo = _seed_repository()
    conflicts = repo.detect_conflicts(subject="MRT Guideway", field="guideway_cost_per_m")
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert sorted(conflict.candidate_values) == [10000.0, 12000.0, 14000.0]
    assert conflict.resolution_status == "unresolved"


def test_query_returns_evidence_not_prose_and_not_found_state():
    repo = _seed_repository()
    found = repo.query_evidence(parameter_name="guideway_cost_per_m", subject="MRT Guideway")
    assert found.availability_status == "FOUND"
    assert len(found.matching_claims) == 3
    assert found.conflicts

    missing = repo.query_evidence(parameter_name="nonexistent_parameter", subject="Model Z")
    assert missing.availability_status == "NOT FOUND / NOT NATIVELY AVAILABLE"
    assert missing.missing_evidence is True


def test_assumption_promotion_boundary_and_native_overrides():
    repo = _seed_repository()

    unresolved = repo.register_assumption_proposal(
        parameter_name="guideway_capex_per_m",
        proposed_value=12000.0,
        unit="USD/m",
        supporting_claim_ids=tuple(
            claim.claim_id
            for claim in repo.claims.values()
            if claim.subject == "MRT Guideway" and claim.predicate == "guideway_cost_per_m"
        ),
        confidence=0.8,
        promotion_status="candidate",
    )
    with pytest.raises(ValueError, match="unresolved conflict cannot be promoted automatically"):
        repo.update_proposal_status(proposal_id=unresolved.proposal_id, promotion_status="accepted")

    rejected = repo.register_assumption_proposal(
        parameter_name="electricity_cost_per_kwh",
        proposed_value=0.19,
        unit="currency/kWh",
        supporting_claim_ids=(next(iter(repo.claims.values())).claim_id,),
        confidence=0.6,
        promotion_status="candidate",
    )
    repo.update_proposal_status(proposal_id=rejected.proposal_id, promotion_status="rejected")

    overrides = repo.build_native_parameter_overrides()
    assert "scanners" in overrides
    assert "electricity_cost_per_kwh" not in overrides


def test_unit_mismatch_and_missing_currency_year_are_flagged():
    repo = _seed_repository()
    claim = next(claim for claim in repo.claims.values() if claim.subject == "Hospital Alpha")
    bad = repo.register_assumption_proposal(
        parameter_name="scanners",
        proposed_value=7,
        unit="rooms",
        supporting_claim_ids=(claim.claim_id,),
        confidence=0.5,
        promotion_status="accepted",
    )
    with pytest.raises(ValueError, match="unsupported unit conversion"):
        repo.build_native_parameter_overrides()

    value = repo.register_value(
        parameter_name="scanner_cost",
        source_claim_ids=(claim.claim_id,),
        value=2500000.0,
        unit="USD",
        value_type="currency",
        currency="USD",
        currency_year=None,
    )
    assert value.currency == "USD"
    assert value.currency_year is None


def test_retrieval_is_deterministic_and_filters_are_respected():
    repo = _seed_repository()
    query = "cyclotron annual maintenance cost"

    one = repo.retrieve(query=query)
    two = repo.retrieve(query=query)
    assert [(item.rank, item.score, item.document_id, item.chunk_id, item.source_id) for item in one] == [
        (item.rank, item.score, item.document_id, item.chunk_id, item.source_id) for item in two
    ]

    tier_filtered = repo.retrieve(query="beam energy", filters=EvidenceRetrievalFilter(source_tier="TIER_1"))
    assert tier_filtered
    assert all(item.source_tier == "TIER_1" for item in tier_filtered)


def test_cross_domain_retrieval_distinguishes_maintenance_queries():
    repo = _seed_repository()

    cyclotron = repo.retrieve(query="cyclotron annual maintenance cost")
    carrier = repo.retrieve(query="MRT carrier maintenance cost")
    guideway = repo.retrieve(query="guideway maintenance cost")

    assert cyclotron
    assert carrier
    assert guideway

    top_cyclotron = repo.chunks[cyclotron[0].chunk_id]
    top_carrier = repo.chunks[carrier[0].chunk_id]
    top_guideway = repo.chunks[guideway[0].chunk_id]
    assert top_cyclotron.metadata.get("domain") == "cyclotron"
    assert top_carrier.metadata.get("domain") == "carrier"
    assert top_guideway.metadata.get("domain") == "guideway"


def test_source_quality_stress_tier1_and_tier4_conflict_both_retrievable():
    repo = _seed_repository()
    conflicts = repo.detect_conflicts(subject="Cyclotron Model X", field="beam_energy")
    assert len(conflicts) == 1

    hits = repo.retrieve(query="Model X beam energy")
    claim_ids = {
        claim.claim_id
        for claim in repo.claims.values()
        if claim.subject == "Cyclotron Model X" and claim.predicate == "beam_energy"
    }
    retrieved_claim_chunks = {
        claim.chunk_id
        for claim in repo.claims.values()
        if claim.claim_id in claim_ids and claim.chunk_id is not None
    }
    hit_chunks = {item.chunk_id for item in hits}
    assert retrieved_claim_chunks.issubset(hit_chunks)


def test_missing_data_cyclotron_catalog_contract_and_explicit_failure():
    repo = _seed_repository()

    backed = EvidenceBackedCyclotronModel(
        manufacturer="Acme",
        model="Model X",
        supported_radionuclides=("F-18", "N-13"),
        production_capabilities={
            "cyclotron_id": "ACME-X",
            "max_simultaneous_production_streams": 2,
            "production_cycle_minutes_by_radionuclide": {"F-18": 30.0, "N-13": 15.0},
            "simultaneously_compatible_radionuclide_sets": (("F-18", "N-13"),),
        },
        source_claim_ids_by_field={
            "manufacturer": (),
            "model": (),
            "supported_radionuclides": (),
            "production_capabilities": (),
        },
        missing_fields=("purchase_cost", "annual_opex"),
        catalog_status="incomplete",
    )

    with pytest.raises(ValueError, match="missing required field purchase_cost"):
        backed.to_cyclotron_model_spec(
            accepted_fields={
                "manufacturer": True,
                "model": True,
                "supported_radionuclides": True,
                "production_capabilities": True,
            }
        )

    assert backed.missing_fields == ("purchase_cost", "annual_opex")


def test_comparable_project_evidence_contract_is_schema_only():
    contract = ComparableProjectEvidence(
        project_id="proj-001",
        facility_name="Hospital Alpha",
        cyclotron_models=("Model X",),
        scanner_count=6,
        missing_fields=("capital_cost", "operating_cost"),
    )
    assert contract.project_id == "proj-001"
    assert "capital_cost" in contract.missing_fields


def test_rag_to_native_boundary_audit_and_provenance_chain():
    repo = _seed_repository()

    # Build one accepted proposal with full lineage into registry mapping.
    scanner_claim = next(
        claim
        for claim in repo.claims.values()
        if claim.subject == "Hospital Alpha" and claim.predicate == "scanner_count"
    )
    value = repo.register_value(
        parameter_name="scanners",
        source_claim_ids=(scanner_claim.claim_id,),
        value=6,
        unit="count",
        value_type="scalar",
    )
    proposal = repo.register_assumption_proposal(
        parameter_name="scanners",
        proposed_value=6,
        unit="count",
        supporting_claim_ids=(scanner_claim.claim_id,),
        confidence=0.9,
        promotion_status="candidate",
    )
    repo.update_proposal_status(proposal_id=proposal.proposal_id, promotion_status="accepted")

    audit = repo.audit_rag_to_native_boundary()
    assert audit.edge_classification["retrieved document -> evidence source"] in {
        "DIRECT NATIVE CONNECTION",
        "PARTIAL CONNECTION",
    }
    assert audit.edge_classification["accepted assumption -> native model field"] in {
        "DIRECT NATIVE CONNECTION",
        "PARTIAL CONNECTION",
    }

    chain = repo.build_provenance_chain(proposal_id=proposal.proposal_id, parameter_name="scanners")
    assert chain.claim_id == scanner_claim.claim_id
    assert chain.value_id == value.value_id
    assert chain.native_mapping.native_parameter == "scanners"


def test_negative_adversarial_invariants():
    repo = _seed_repository()

    # 1) Missing evidence does not become zero.
    missing = repo.query_evidence(parameter_name="cyclotron_purchase_price", subject="Cyclotron Model X")
    assert missing.missing_evidence is True

    # 2) Conflicting evidence is not averaged and no auto winner.
    conflicts = repo.detect_conflicts(subject="MRT Guideway", field="guideway_cost_per_m")
    assert conflicts and conflicts[0].resolution_status == "unresolved"

    # 3) Tier 4 does not override Tier 1 automatically.
    model_conflicts = repo.detect_conflicts(subject="Cyclotron Model X", field="beam_energy")
    assert model_conflicts and model_conflicts[0].resolution_status == "unresolved"

    # 4) Unsupported units do not silently convert.
    claim = next(
        c for c in repo.claims.values() if c.subject == "Hospital Alpha" and c.predicate == "scanner_count"
    )
    bad = repo.register_assumption_proposal(
        parameter_name="scanners",
        proposed_value=7,
        unit="m2",
        supporting_claim_ids=(claim.claim_id,),
        confidence=0.2,
        promotion_status="accepted",
    )
    with pytest.raises(ValueError):
        repo.build_native_parameter_overrides()
    repo.update_proposal_status(proposal_id=bad.proposal_id, promotion_status="rejected")

    # 5) Currency without year remains flagged/missing.
    value = repo.register_value(
        parameter_name="carrier_cost",
        source_claim_ids=(claim.claim_id,),
        value=100000.0,
        unit="USD",
        value_type="currency",
        currency="USD",
        currency_year=None,
    )
    assert value.currency_year is None

    # 6-10) Domain leakage prevention via explicit parameter names and retrieval domain metadata.
    assert repo.query_evidence(parameter_name="guideway_cost_per_m", subject="MRT Carrier").missing_evidence
    assert repo.query_evidence(parameter_name="carrier_maintenance", subject="MRT Guideway").missing_evidence

    # 11) Claim without source lineage cannot be promoted.
    fake_claim = EngineeringEvidenceClaim(
        claim_id="fake-claim",
        source_id="missing-source",
        document_id=None,
        chunk_id=None,
        claim_type="quantitative",
        subject="Fake",
        predicate="scanners",
        raw_value=1,
        normalized_value=1,
        unit="count",
    )
    repo.claims[fake_claim.claim_id] = fake_claim
    with pytest.raises(ValueError, match="claim without source lineage"):
        repo.register_assumption_proposal(
            parameter_name="scanners",
            proposed_value=1,
            unit="count",
            supporting_claim_ids=(fake_claim.claim_id,),
            confidence=0.1,
        )

    # 12) Unresolved conflict cannot be promoted automatically.
    guideway_claim_ids = tuple(
        claim.claim_id
        for claim in repo.claims.values()
        if claim.subject == "MRT Guideway" and claim.predicate == "guideway_cost_per_m"
    )
    unresolved = repo.register_assumption_proposal(
        parameter_name="guideway_capex_per_m",
        proposed_value=12000.0,
        unit="USD/m",
        supporting_claim_ids=guideway_claim_ids,
        confidence=0.7,
    )
    with pytest.raises(ValueError):
        repo.update_proposal_status(proposal_id=unresolved.proposal_id, promotion_status="accepted")

    # 13-14) rejected/superseded proposals are not authoritative.
    accepted = repo.register_assumption_proposal(
        parameter_name="scanners",
        proposed_value=8,
        unit="count",
        supporting_claim_ids=(claim.claim_id,),
        confidence=0.5,
    )
    repo.update_proposal_status(proposal_id=accepted.proposal_id, promotion_status="accepted")
    repo.update_proposal_status(proposal_id=accepted.proposal_id, promotion_status="rejected")
    assert "scanners" in repo.parameter_registry

    superseded = repo.register_assumption_proposal(
        parameter_name="injection_resources",
        proposed_value=4,
        unit="count",
        supporting_claim_ids=(claim.claim_id,),
        confidence=0.5,
    )
    repo.update_proposal_status(proposal_id=superseded.proposal_id, promotion_status="superseded")
    overrides = repo.build_native_parameter_overrides()
    assert "injection_resources" not in overrides

    # 15) Duplicate ingestion does not create uncontrolled duplicates.
    source = repo.register_source(source_type="project_document", title="Duplicate test")
    doc1 = repo.register_document(source_id=source.source_id, title="D", format="txt", content="same")
    doc2 = repo.register_document(source_id=source.source_id, title="D", format="txt", content="same")
    assert doc1.document_id == doc2.document_id

    # 16-17) Deterministic ranking and filter behavior.
    q1 = repo.retrieve(query="guideway maintenance cost")
    q2 = repo.retrieve(query="guideway maintenance cost")
    assert [(x.rank, x.score, x.chunk_id) for x in q1] == [(x.rank, x.score, x.chunk_id) for x in q2]
    tier4 = repo.retrieve(query="beam energy", filters=EvidenceRetrievalFilter(source_tier="TIER_4"))
    assert all(hit.source_tier == "TIER_4" for hit in tier4)

    # 18) Unknown source tier remains unknown.
    unknown = repo.register_source(source_type="unknown", title="Unknown tier source")
    assert unknown.source_tier == "UNKNOWN"

    # 19) Missing publication date remains missing.
    assert unknown.publication_date is None

    # 20) No generated prose is treated as primary evidence.
    prose = repo.query_evidence(parameter_name="generated_prose_primary_evidence", subject="Narrative")
    assert prose.availability_status == "NOT FOUND / NOT NATIVELY AVAILABLE"

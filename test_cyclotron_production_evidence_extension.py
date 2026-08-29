"""Focused tests for the Cyclotron Production Evidence & Calibration Extension.

Covers the 34 invariants of the build's Section 38 against the REAL repository
authorities: the new evidence registry (`cyclotron_production_evidence.json`),
the estimator seam in `cyclotron_production_estimation_authority.py`, the Build
3B catalog, the Part 3D per-radionuclide gate, and the generator boundary.

Governing facts used (physical repository):
  - GE PETtrace 890 + F-18 : 160 uA / 120 min -> 648000 MBq (manufacturer_calibrated).
  - IBA Cyclone KEY  + F-18 : 100 uA / 120 min -> 111000 MBq (manufacturer_calibrated).
  - SUMITOMO CYPRIS MP-30 + F-18 : SUPPORTED, no records / no OWN beam current -> NOT_AVAILABLE.
  - SIEMENS Eclipse HP + F-18 : SUPPORTED, own literature beam current 60 uA @ 11 MeV,
        no calibrated EOB record -> becomes MODELED_ESTIMATE via the reaction
        saturation-yield registry record (8.3 GBq/uA, 18O(p,n)18F). NEW modeled pair.
  - Tc-99m : generator daughter (Mo-99 -> Tc-99m), OUT_OF_CYCLOTRON_SCOPE.

The registry evidence is REACTION-LEVEL physics (18O(p,n)18F saturation yield),
applied ONLY with a machine's OWN published beam current. It is MODELED_ESTIMATE
only and never becomes manufacturer/site calibrated.
"""

from __future__ import annotations

import math

import pytest

import cyclotron_production_estimation_authority as cpea
import cyclotron_catalog as cc


GE890 = "GE_PETTRACE_890"
IBA_KEY = "IBA_CYCLONE_KEY"
CYPRIS_MP30 = "SUMITOMO_CYPRIS_MP_30"
GE800 = "GE_PETTRACE_800"
BEST_14P = "BEST_14P"
ECLIPSE_HP = "SIEMENS_CTI_ECLIPSE_HP"

# Locked expected reaction-yield modeled value: Ysat = 8300 MBq/uA (8.3 GBq/uA),
# Eclipse HP OWN beam current I = 60 uA, half-life F-18 = 109.8 min, t = 120 min.
_YSAT_MBQ_PER_UA = 8300.0
_ECLIPSE_I_UA = 60.0
_F18_HL = 109.8
_LAMBDA_F18 = math.log(2.0) / _F18_HL


def _expected_eclipse_eob(t_min: float) -> float:
    return _YSAT_MBQ_PER_UA * _ECLIPSE_I_UA * (1.0 - math.exp(-_LAMBDA_F18 * t_min))


@pytest.fixture(autouse=True)
def _fresh_registry():
    # Ensure each test reads the on-disk registry (defensive against cache).
    cpea.load_production_evidence_registry(force_reload=True)
    yield


# ---------------------------------------------------------------------------
# 1. evidence registry loads
# ---------------------------------------------------------------------------
def test_01_evidence_registry_loads():
    records = cpea.load_production_evidence_registry()
    assert len(records) >= 1
    assert all(isinstance(r, cpea.ProductionEvidenceRecord) for r in records)


# ---------------------------------------------------------------------------
# 2. evidence records have stable IDs
# ---------------------------------------------------------------------------
def test_02_records_have_stable_ids():
    records = cpea.load_production_evidence_registry()
    ids = [r.evidence_record_id for r in records]
    assert all(isinstance(i, str) and i for i in ids)
    assert len(ids) == len(set(ids))  # unique
    assert "EV-F18-18OPN-SAT-001" in ids


# ---------------------------------------------------------------------------
# 3. source / provenance is present
# ---------------------------------------------------------------------------
def test_03_source_provenance_present():
    for r in cpea.load_production_evidence_registry():
        assert r.source_title, r.evidence_record_id
        # A citation reference is always constructible.
        assert isinstance(r.source_reference, str) and r.source_reference


# ---------------------------------------------------------------------------
# 4. model identity is preserved
# ---------------------------------------------------------------------------
def test_04_model_identity_preserved():
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18")
    assert r.catalog_model_id == ECLIPSE_HP
    assert r.model == "Eclipse HP"
    assert r.manufacturer == "Siemens/CTI"


# ---------------------------------------------------------------------------
# 5. radionuclide identity is preserved
# ---------------------------------------------------------------------------
def test_05_radionuclide_identity_preserved():
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18")
    assert r.radionuclide == "F-18"
    for rec in cpea.resolve_evidence_registry_records(ECLIPSE_HP, "F-18"):
        assert rec.radionuclide == "F-18"


# ---------------------------------------------------------------------------
# 6. raw values remain traceable
# ---------------------------------------------------------------------------
def test_06_raw_values_traceable():
    primary = next(r for r in cpea.load_production_evidence_registry()
                   if r.evidence_record_id == "EV-F18-18OPN-SAT-001")
    assert primary.raw_value == 8.3
    assert primary.raw_unit == "GBq/uA"
    # The modeled estimate exposes the raw evidence in its reference string.
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18")
    assert r.raw_evidence_reference is not None
    assert "8.3" in r.raw_evidence_reference and "GBq/uA" in r.raw_evidence_reference


# ---------------------------------------------------------------------------
# 7. normalization is unit-correct (GBq/uA -> MBq/uA)
# ---------------------------------------------------------------------------
def test_07_normalization_unit_correct():
    primary = next(r for r in cpea.load_production_evidence_registry()
                   if r.evidence_record_id == "EV-F18-18OPN-SAT-001")
    assert primary.saturation_yield_mbq_per_ua == 8300.0  # 8.3 GBq/uA * 1000


# ---------------------------------------------------------------------------
# 8. literature evidence does not become manufacturer-calibrated
# ---------------------------------------------------------------------------
def test_08_literature_not_manufacturer_calibrated():
    for r in cpea.load_production_evidence_registry():
        assert r.evidence_class == "MODELED_ESTIMATE"
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18")
    assert r.production_basis == "MODELED_ESTIMATE"
    assert r.calibration_status != "manufacturer_calibrated"
    assert r.calibration_status != "site_calibrated"


# ---------------------------------------------------------------------------
# 9. literature evidence does not become site-calibrated
# ---------------------------------------------------------------------------
def test_09_literature_not_site_calibrated():
    for r in cpea.load_production_evidence_registry():
        assert r.evidence_class != "SITE_CALIBRATED"
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18")
    assert r.production_basis != "SITE_CALIBRATED"


# ---------------------------------------------------------------------------
# 10. manufacturer-calibrated record outranks modeled evidence
# ---------------------------------------------------------------------------
def test_10_manufacturer_outranks_modeled():
    # GE890 has a manufacturer anchor; the registry branch is never reached.
    r = cpea.estimate_cyclotron_production(GE890, "F-18")
    assert r.production_basis == "MANUFACTURER_CALIBRATED"
    assert r.estimated_or_calibrated_eob_mbq == 648000.0
    assert r.evidence_record_id is None  # no registry record used
    assert cpea.stronger_basis("MANUFACTURER_CALIBRATED", "MODELED_ESTIMATE") == "MANUFACTURER_CALIBRATED"


# ---------------------------------------------------------------------------
# 11. site-calibrated record outranks manufacturer evidence (precedence order)
# ---------------------------------------------------------------------------
def test_11_site_outranks_manufacturer_precedence():
    # No site-calibrated cyclotron record is physically present, so lock the
    # precedence ordering the resolver relies on.
    assert cpea.stronger_basis("SITE_CALIBRATED", "MANUFACTURER_CALIBRATED") == "SITE_CALIBRATED"
    assert cpea.stronger_basis("SITE_CALIBRATED", "MODELED_ESTIMATE") == "SITE_CALIBRATED"


# ---------------------------------------------------------------------------
# 12. modeled evidence outranks NOT_AVAILABLE
# ---------------------------------------------------------------------------
def test_12_modeled_outranks_not_available():
    assert cpea.stronger_basis("MODELED_ESTIMATE", "NOT_AVAILABLE") == "MODELED_ESTIMATE"
    # Concretely: Eclipse HP + F-18 was NOT_AVAILABLE before evidence; now MODELED.
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18")
    assert r.production_basis == "MODELED_ESTIMATE"
    assert r.estimation_status == "AVAILABLE"


# ---------------------------------------------------------------------------
# 13. no cross-model borrowing
# ---------------------------------------------------------------------------
def test_13_no_cross_model_borrowing():
    # Eclipse HP's modeled EOB uses its OWN 60 uA, never GE890's 648000 / 160 uA.
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18")
    assert r.estimated_or_calibrated_eob_mbq != 648000.0
    assert r.estimated_or_calibrated_eob_mbq < 648000.0
    assert "OWN" in " ".join(r.limitations) or "own" in r.provenance.lower()
    # CYPRIS MP-30 (no own current) cannot borrow another machine's current.
    c = cpea.estimate_cyclotron_production(CYPRIS_MP30, "F-18")
    assert c.estimated_or_calibrated_eob_mbq is None


# ---------------------------------------------------------------------------
# 14. no cross-radionuclide borrowing
# ---------------------------------------------------------------------------
def test_14_no_cross_radionuclide_borrowing():
    # The F-18 reaction record only qualifies F-18. Eclipse HP supports C-11 but
    # has no C-11 evidence record -> NOT_AVAILABLE (never inherits F-18's number).
    c11 = cpea.estimate_cyclotron_production(ECLIPSE_HP, "C-11")
    assert c11.estimation_status == "NOT_AVAILABLE"
    assert c11.estimated_or_calibrated_eob_mbq is None
    for rec in cpea.resolve_evidence_registry_records(ECLIPSE_HP, "C-11"):
        assert False, "no F-18 record should match a C-11 query"


# ---------------------------------------------------------------------------
# 15. competing records are not silently averaged
# ---------------------------------------------------------------------------
def test_15_competing_records_not_averaged():
    res = cpea.resolve_evidence_record(ECLIPSE_HP, "F-18")
    assert len(res.competing_record_ids) >= 2  # 8.3 and 7.8 GBq/uA both apply
    # The chosen value equals ONE record's basis (8300), never the mean of 8300 & 7800.
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18", irradiation_minutes=120.0)
    mean_yield = (8300.0 + 7800.0) / 2.0
    averaged = mean_yield * _ECLIPSE_I_UA * (1.0 - math.exp(-_LAMBDA_F18 * 120.0))
    assert abs(r.estimated_or_calibrated_eob_mbq - averaged) > 1.0
    assert abs(r.estimated_or_calibrated_eob_mbq - _expected_eclipse_eob(120.0)) < 1.0


# ---------------------------------------------------------------------------
# 16. chosen evidence is explainable
# ---------------------------------------------------------------------------
def test_16_chosen_evidence_explainable():
    res = cpea.resolve_evidence_record(ECLIPSE_HP, "F-18")
    assert res.chosen is not None
    assert isinstance(res.selection_reason, str) and res.selection_reason
    assert res.chosen.evidence_record_id == "EV-F18-18OPN-SAT-001"  # measured > calculated
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18")
    assert r.evidence_record_id == "EV-F18-18OPN-SAT-001"
    assert r.source_reference is not None and "ijrr.com" in r.source_reference


# ---------------------------------------------------------------------------
# 17. confidence preserved / honest
# ---------------------------------------------------------------------------
def test_17_confidence_preserved():
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18")
    # Reaction-yield applied to a literature beam current is honestly LOW.
    assert r.confidence == "LOW"
    assert r.confidence in {"HIGH", "MEDIUM", "LOW", "NOT_ASSESSED"}


# ---------------------------------------------------------------------------
# 18. CYPRIS MP-30 + F-18 real identity preserved
# ---------------------------------------------------------------------------
def test_18_cypris_identity_preserved():
    r = cpea.estimate_cyclotron_production(CYPRIS_MP30, "F-18")
    assert r.catalog_model_id == CYPRIS_MP30
    assert r.model == "CYPRIS MP-30"
    assert r.supported is True


# ---------------------------------------------------------------------------
# 19. CYPRIS MP-30 + F-18 no GE capacity borrowing
# ---------------------------------------------------------------------------
def test_19_cypris_no_ge_borrowing():
    r = cpea.estimate_cyclotron_production(CYPRIS_MP30, "F-18")
    assert r.estimated_or_calibrated_eob_mbq is None
    assert r.production_basis == "NOT_AVAILABLE"
    assert r.evidence_record_id is None


# ---------------------------------------------------------------------------
# 20. CYPRIS MP-30 + F-18 evidence outcome honest (NOT_AVAILABLE retained)
# ---------------------------------------------------------------------------
def test_20_cypris_outcome_honest():
    r = cpea.estimate_cyclotron_production(CYPRIS_MP30, "F-18")
    assert r.calibration_status == "not_calibrated"
    assert r.estimation_status == "NOT_AVAILABLE"
    # No own beam current is published, so the reaction-yield record cannot apply.
    model = cc.load_cyclotron_catalog().by_id(CYPRIS_MP30)
    assert cpea._model_own_beam_current_ua(model) is None


# ---------------------------------------------------------------------------
# 21. at least two additional CYPRIS radionuclide controls
# ---------------------------------------------------------------------------
def test_21_additional_cypris_radionuclide_controls():
    # Cu-64: supported by CYPRIS but no half-life physics + no evidence -> NOT_AVAILABLE.
    cu = cpea.estimate_cyclotron_production(CYPRIS_MP30, "Cu-64")
    assert cu.supported is True
    assert cu.estimation_status == "NOT_AVAILABLE"
    assert cu.estimated_or_calibrated_eob_mbq is None
    # Ga-68: supported, has half-life, but no CYPRIS own current / no Ga-68 record.
    ga = cpea.estimate_cyclotron_production(CYPRIS_MP30, "Ga-68")
    assert ga.supported is True
    assert ga.estimation_status == "NOT_AVAILABLE"
    assert ga.estimated_or_calibrated_eob_mbq is None


# ---------------------------------------------------------------------------
# 22. calibrated GE890 + F-18 remains calibrated
# ---------------------------------------------------------------------------
def test_22_ge890_remains_calibrated():
    model = cc.load_cyclotron_catalog().by_id(GE890)
    assert model.production_calibration_status == "manufacturer_calibrated"
    r = cpea.estimate_cyclotron_production(GE890, "F-18")
    assert r.production_basis == "MANUFACTURER_CALIBRATED"
    assert r.estimated_or_calibrated_eob_mbq == 648000.0
    assert r.confidence == "HIGH"


# ---------------------------------------------------------------------------
# 23. unsupported pair remains unsupported
# ---------------------------------------------------------------------------
def test_23_unsupported_pair_remains_unsupported():
    # Cu-64 is cyclotron-only (no generator) and unsupported by BEST_14P ->
    # NO_COMPATIBLE_SOURCE, no fabricated EOB. (Ga-68 now has a Ge-68/Ga-68
    # generator after the Clinical Radionuclide Completeness closure, so it is
    # OUT_OF_CYCLOTRON_SCOPE on an unsupported cyclotron rather than
    # NO_COMPATIBLE_SOURCE.)
    r = cpea.estimate_cyclotron_production(BEST_14P, "Cu-64")
    assert r.supported is False
    assert r.estimation_status == "NO_COMPATIBLE_SOURCE"
    assert r.estimated_or_calibrated_eob_mbq is None


# ---------------------------------------------------------------------------
# 24. Tc-99m remains outside cyclotron estimator
# ---------------------------------------------------------------------------
def test_24_tc99m_outside_cyclotron():
    r = cpea.estimate_cyclotron_production(GE890, "Tc-99m")
    assert r.estimation_status == "OUT_OF_CYCLOTRON_SCOPE"
    assert r.estimated_or_calibrated_eob_mbq is None
    # No Tc-99m evidence record exists in the cyclotron registry.
    for rec in cpea.load_production_evidence_registry():
        assert rec.radionuclide != "Tc-99m"


# ---------------------------------------------------------------------------
# 25. new modeled pair produces numerical EOB (evidence exists)
# ---------------------------------------------------------------------------
def test_25_new_modeled_pair_produces_numerical_eob():
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18")
    assert r.production_basis == "MODELED_ESTIMATE"
    assert r.estimation_status == "AVAILABLE"
    assert r.has_numerical_value()
    assert abs(r.estimated_or_calibrated_eob_mbq - _expected_eclipse_eob(120.0)) < 1.0
    # Irradiation-time response is monotone increasing.
    e30 = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18", irradiation_minutes=30.0)
    e60 = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18", irradiation_minutes=60.0)
    e240 = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18", irradiation_minutes=240.0)
    vals = [e30.estimated_or_calibrated_eob_mbq, e60.estimated_or_calibrated_eob_mbq,
            r.estimated_or_calibrated_eob_mbq, e240.estimated_or_calibrated_eob_mbq]
    assert all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))


# ---------------------------------------------------------------------------
# 26. larger required EOB cannot reduce cycle count
# ---------------------------------------------------------------------------
def test_26_larger_required_eob_cannot_reduce_cycles():
    reqs = [100000.0, 264528.0, 264529.0, 1_000_000.0, 5_000_000.0]
    cycles = [cpea.estimate_required_physical_cycles(ECLIPSE_HP, "F-18", q).required_cycles for q in reqs]
    assert all(cycles[i] <= cycles[i + 1] for i in range(len(cycles) - 1))
    assert cycles[0] == 1 and cycles[2] == 2


# ---------------------------------------------------------------------------
# 27. patient identity is not required
# ---------------------------------------------------------------------------
def test_27_patient_identity_not_required():
    import inspect
    for fn in (cpea.estimate_cyclotron_production, cpea.estimate_required_physical_cycles,
               cpea.resolve_simulation_production_basis, cpea.resolve_evidence_record,
               cpea.resolve_evidence_registry_records, cpea.load_production_evidence_registry):
        params = set(inspect.signature(fn).parameters)
        assert not (params & {"patient", "patient_id", "patient_name", "room", "scanner"})
    b = cpea.estimate_required_physical_cycles(ECLIPSE_HP, "F-18", 500000.0)
    assert not hasattr(b, "patient_id")


# ---------------------------------------------------------------------------
# 28. no legacy 10% production blocks
# ---------------------------------------------------------------------------
def test_28_no_legacy_10_percent_blocks():
    src = open("cyclotron_production_estimation_authority.py", encoding="utf-8").read()
    assert "production_block" not in src
    assert "0.10" not in src and "* 0.1" not in src


# ---------------------------------------------------------------------------
# 29. no current_usable_doses fallback
# ---------------------------------------------------------------------------
def test_29_no_usable_doses_fallback():
    src = open("cyclotron_production_estimation_authority.py", encoding="utf-8").read()
    assert "usable_doses" not in src
    assert "doses_per_day" not in src


# ---------------------------------------------------------------------------
# 30. excess production does not create patients
# ---------------------------------------------------------------------------
def test_30_excess_production_does_not_create_patients():
    src = open("cyclotron_production_estimation_authority.py", encoding="utf-8").read()
    for forbidden in ("oncology_pet_spect_scenario", "inbound_patient_program",
                      "build_representative_day_population", "PatientRadionuclideDemand"):
        assert forbidden not in src
    # A huge modeled per-cycle vs a tiny requirement yields 1 cycle, no patients.
    b = cpea.estimate_required_physical_cycles(ECLIPSE_HP, "F-18", 1000.0)
    assert b.required_cycles == 1


# ---------------------------------------------------------------------------
# 31. excess production does not create revenue
# ---------------------------------------------------------------------------
def test_31_excess_production_does_not_create_revenue():
    for obj in (
        cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18"),
        cpea.estimate_required_physical_cycles(ECLIPSE_HP, "F-18", 1000.0),
        cpea.load_production_evidence_registry()[0],
    ):
        assert not any("revenue" in f.lower() for f in vars(obj).keys())
    src = open("cyclotron_production_estimation_authority.py", encoding="utf-8").read()
    for forbidden in ("import economics", "patient_economics", "whole_oncology_revenue",
                      "AUDITED_NUCLEAR_SCAN_REVENUE"):
        assert forbidden not in src


# ---------------------------------------------------------------------------
# 32. OG-SYNTH-1 remains open (this build does not touch the randomizer)
# ---------------------------------------------------------------------------
def test_32_og_synth_1_remains_open():
    corpus = open("MRT_PHARMA_OPEN_GAPS.md", encoding="utf-8").read()
    assert "OG-SYNTH-1" in corpus
    # The estimator/registry never imports the synthetic patient generator.
    src = open("cyclotron_production_estimation_authority.py", encoding="utf-8").read()
    assert "oncology_pet_spect_scenario" not in src
    assert "generate_synthetic_patient_population" not in src


# ---------------------------------------------------------------------------
# 33. old estimator tests remain green (structural: the estimator API is intact)
# ---------------------------------------------------------------------------
def test_33_old_estimator_api_intact():
    # The pre-existing public API still resolves the same controls.
    assert cpea.estimate_cyclotron_production(GE890, "F-18").estimated_or_calibrated_eob_mbq == 648000.0
    assert cpea.estimate_cyclotron_production(IBA_KEY, "F-18").estimated_or_calibrated_eob_mbq == 111000.0
    assert cpea.estimate_cyclotron_production(GE890, "F-18", irradiation_minutes=60.0).production_basis == "MODELED_ESTIMATE"
    assert cpea.estimate_cyclotron_production(GE800, "C-11").estimation_status == "NOT_AVAILABLE"
    assert cpea.resolve_simulation_production_basis(CYPRIS_MP30, "F-18") == "NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# 34. Part 3D calibrated controls remain green (per-radionuclide gate seam)
# ---------------------------------------------------------------------------
def test_34_part3d_controls_remain_green():
    import whole_oncology_four_architecture_optimization as wo
    from cyclotron_production_windows import CyclotronProductionCapability, build_single_cyclotron_fleet

    cap = CyclotronProductionCapability(
        cyclotron_id="CY-1", supported_radionuclides=("F-18",),
        max_simultaneous_production_streams=1,
        production_cycle_minutes_by_radionuclide={"F-18": 120.0},
        calibrated_eob_activity_mbq_by_radionuclide={"F-18": 648000.0},
    )
    fleet = build_single_cyclotron_fleet(
        cap, model_identifier="PETtrace 890", manufacturer="GE HealthCare",
        capability_provenance="GE_PETTRACE_890",
    )
    # CYPRIS installed selection: NOT_CALIBRATED, real identity, no borrow, no estimate.
    gate = wo._resolve_radionuclide_production_gate(
        "F-18", fleet, 500000.0, installed_cyclotron_model_ids=(CYPRIS_MP30,),
    )
    assert gate.status == "PRODUCTION_NOT_CALIBRATED"
    assert "CYPRIS MP-30" in gate.source_identity
    assert gate.simulation_production_basis == "NOT_AVAILABLE"
    assert gate.installed_eob_capacity_mbq_per_day is None


# ---------------------------------------------------------------------------
# Additional: unknown model id still raises (honest, not fabricated)
# ---------------------------------------------------------------------------
def test_unknown_model_id_raises():
    with pytest.raises(KeyError):
        cpea.estimate_cyclotron_production("NO_SUCH_MODEL", "F-18")


# ---------------------------------------------------------------------------
# Additional: missing registry file degrades to pre-seam behavior (never raises)
# ---------------------------------------------------------------------------
def test_missing_registry_degrades_gracefully(monkeypatch):
    monkeypatch.setattr(cpea, "_EVIDENCE_REGISTRY_FILENAME", "does_not_exist_registry.json")
    records = cpea.load_production_evidence_registry(force_reload=True)
    assert records == ()
    # With no registry, Eclipse HP + F-18 reverts to honest NOT_AVAILABLE.
    r = cpea.estimate_cyclotron_production(ECLIPSE_HP, "F-18")
    assert r.estimation_status == "NOT_AVAILABLE"
    assert r.estimated_or_calibrated_eob_mbq is None
    # restore for other tests via the autouse fixture on next call
    monkeypatch.setattr(cpea, "_EVIDENCE_REGISTRY_FILENAME", "cyclotron_production_evidence.json")
    cpea.load_production_evidence_registry(force_reload=True)

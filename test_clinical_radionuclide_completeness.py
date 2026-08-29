"""Focused tests for the Clinical Radionuclide Completeness & Evidence Closure
build (Pre-Part-3E).

Protects the Section 35 invariants (1-50) and the Section 36 control proofs
(A-I). This build is a COMPLETENESS build: it determines whether radionuclides
excluded from the NORMAL clinical portfolio were excluded for lack of evidence
or merely because the repository had not incorporated available authoritative
evidence, then propagates the found evidence into the CANONICAL authorities
(never into the report/registry only).

Doctrine locked here:
    CLINICAL INCLUSION      != MRT PREFERENCE
    PHYSICAL SUPPORT        != CLINICAL USE
    CLINICAL USE            != PRODUCTION CALIBRATION
    SUPPORTED               != CALIBRATED != MODELED ESTIMATE
    PORTFOLIO               != DEMAND MIX != OPTIMIZATION RESULT

Every promoted canonical fact is backed by a traceable evidence record in
`clinical_radionuclide_evidence.json` and locked by a test below (Section M.1).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clinical_radionuclide_portfolio import (
    discover_physically_recognized_radionuclides,
    resolve_clinical_radionuclide_portfolio,
    _clinical_modality_for,
)
from diagnostics import load_radionuclide_half_lives
from cyclotron_catalog import load_cyclotron_catalog
from generator_catalog import load_generator_catalog
from synthetic_radionuclide_source_capability import (
    _CLINICALLY_RECOGNIZED_RADIONUCLIDES_BY_MODALITY as MODALITY,
    resolve_admissible_radionuclides,
)

_EVIDENCE_PATH = Path(__file__).with_name("clinical_radionuclide_evidence.json")

# A scenario that selects a rich multi-isotope cyclotron + both generators +
# both scanner modalities, so admissibility is exercised across the expanded
# universe. IBA KIUBE declares F-18,Ga-68,Zr-89,Cu-64,N-13,C-11,O-15,I-123,I-124.
_KIUBE = "IBA_CYCLONE_KIUBE"
_IKON = "IBA_CYCLONE_IKON"          # declares Cu-64,Ge-68,I-123,Tl-201,Zr-89,F-18,Ga-68,I-124
_30XP = "IBA_CYCLONE_30XP"          # declares F-18,Cu-64,Zr-89,Ge-68,I-123,In-111,Tl-201,At-211
_GE890 = "GE_PETTRACE_890"          # F-18 manufacturer-calibrated
_PETTRACE_800 = "GE_PETTRACE_800"   # F-18,C-11,N-13,O-15,Ga-68
_TECHNELITE = "CURIUM_TECHNELITE"   # Mo-99 -> Tc-99m
_BOTH = ("PET", "SPECT")

# The 15 physically-recognized radionuclides (discovered, asserted below).
_PHYSICAL_15 = {
    "At-211", "C-11", "Cu-64", "F-18", "Ga-68", "Ge-68", "I-123", "I-124",
    "In-111", "Mo-99", "N-13", "O-15", "Tc-99m", "Tl-201", "Zr-89",
}


@pytest.fixture(scope="module")
def evidence():
    return json.loads(_EVIDENCE_PATH.read_text(encoding="utf-8"))


def _records(evidence, radionuclide=None, dimension=None):
    out = evidence["records"]
    if radionuclide is not None:
        out = [r for r in out if r["radionuclide"] == radionuclide]
    if dimension is not None:
        out = [r for r in out if r["evidence_dimension"] == dimension]
    return out


def _full_universe_portfolio():
    cyc = tuple(m.catalog_model_id for m in load_cyclotron_catalog().models)
    gen = tuple(m.catalog_model_id for m in load_generator_catalog().models)
    return resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=cyc, selected_generator_ids=gen,
        selected_scanner_modalities=_BOTH, mode="NORMAL",
    )


# ---------------------------------------------------------------------------
# 1-6: registry + physical universe
# ---------------------------------------------------------------------------

def test_01_completeness_authorities_import_cleanly():
    assert callable(resolve_clinical_radionuclide_portfolio)
    assert callable(resolve_admissible_radionuclides)
    assert callable(load_radionuclide_half_lives)


def test_02_evidence_registry_loads(evidence):
    assert evidence["schema_version"]
    assert isinstance(evidence["records"], list)
    assert len(evidence["records"]) >= 15


def test_03_every_physical_radionuclide_audited(evidence):
    universe = set(discover_physically_recognized_radionuclides())
    assert universe == _PHYSICAL_15
    covered = {r["radionuclide"] for r in evidence["records"]}
    # Every physically-recognized radionuclide has at least one evidence record.
    assert _PHYSICAL_15 <= covered


def test_04_evidence_ids_unique(evidence):
    ids = [r["evidence_record_id"] for r in evidence["records"]]
    assert len(ids) == len(set(ids))


def test_05_raw_evidence_preserved(evidence):
    for r in evidence["records"]:
        assert "raw_value" in r and "raw_unit" in r
        assert r["raw_value"] is not None


def test_06_normalized_evidence_preserved(evidence):
    for r in evidence["records"]:
        assert "normalized_value" in r and "normalized_unit" in r
        assert "evidence_class" in r and r["evidence_class"] in set(evidence["evidence_class_vocabulary"])
        assert r["source_reference"]


# ---------------------------------------------------------------------------
# 7-11: half-life canonical propagation (single decay authority, no 2nd table)
# ---------------------------------------------------------------------------

def test_07_half_life_canonical_propagation_works():
    hl = load_radionuclide_half_lives()
    # All 15 physically-recognized radionuclides now have canonical decay authority.
    assert _PHYSICAL_15 <= set(hl)
    assert len(hl) == 15


def test_08_no_second_decay_table():
    # multi_isotope_decay must consume the SAME radionuclides.json table, never
    # a second hardcoded copy.
    from multi_isotope_decay import _half_life_lookup
    assert _half_life_lookup() == load_radionuclide_half_lives()
    # The portfolio must NOT hardcode half-lives (it reads the loader).
    import inspect
    import clinical_radionuclide_portfolio as mod
    src = inspect.getsource(mod)
    assert "load_radionuclide_half_lives" in src
    for forbidden in ("762.0", "4705.2", "390441.6"):  # newly-added values, must not be literals here
        assert forbidden not in src


def test_09_new_half_lives_match_normalized_evidence(evidence):
    hl = load_radionuclide_half_lives()
    for rn in ("Cu-64", "Zr-89", "Ge-68", "I-123", "I-124", "In-111", "Tl-201", "At-211"):
        recs = _records(evidence, rn, "half_life")
        assert recs, f"missing half-life evidence for {rn}"
        assert hl[rn] == pytest.approx(recs[0]["normalized_value"])


def test_10_formerly_missing_isotopes_decay_through_single_engine():
    from multi_isotope_decay import retained_fraction
    hl = load_radionuclide_half_lives()
    for rn in ("Cu-64", "Zr-89", "I-123", "At-211"):
        # elapsed = exactly one half-life -> retained fraction 0.5.
        assert retained_fraction(hl[rn], hl[rn]) == pytest.approx(0.5)


def test_11_half_life_values_are_positive_and_ordered():
    hl = load_radionuclide_half_lives()
    assert all(v > 0 for v in hl.values())
    # O-15 shortest, Ge-68 (generator parent) longest -- physical ordering sanity.
    assert hl["O-15"] < hl["C-11"] < hl["F-18"]
    assert hl["Ge-68"] == max(hl.values())


# ---------------------------------------------------------------------------
# 12-16: clinical modality canonical authority consumed, no duplicate dicts
# ---------------------------------------------------------------------------

def test_12_clinical_modality_canonical_authority_consumed():
    # The portfolio's modality resolver reads the SAME canonical dict as the
    # synthetic capability authority (no competing table).
    for rn in ("F-18", "C-11", "Ga-68", "Cu-64", "I-124"):
        assert _clinical_modality_for(rn) == "PET"
    for rn in ("Tc-99m", "I-123", "In-111", "Tl-201"):
        assert _clinical_modality_for(rn) == "SPECT"


def test_13_procedure_authority_still_not_fabricated():
    # PROCEDURE authority remains NOT_MODELED: no radionuclide-specific procedure
    # class is invented. (Completeness closed modality + decay, not procedure.)
    pf = _full_universe_portfolio()
    for e in pf.entries:
        assert e.procedure_status == "PROCEDURE_NOT_MODELED"


def test_14_no_duplicate_modality_dictionaries():
    # There is exactly ONE canonical modality mapping; the portfolio imports the
    # synthetic-capability recognition set rather than declaring its own.
    import inspect
    import clinical_radionuclide_portfolio as mod
    src = inspect.getsource(mod)
    assert "_CLINICALLY_RECOGNIZED_RADIONUCLIDES_BY_MODALITY" in src
    # The portfolio must not define its own PET/SPECT membership frozensets.
    assert 'frozenset({"F-18"' not in src and "frozenset({'F-18'" not in src


def test_15_modality_classification_is_evidence_gated(evidence):
    # Every PET/SPECT binding in the canonical dict has a modality evidence record.
    classified = set(MODALITY["PET"]) | set(MODALITY["SPECT"])
    for rn in classified:
        if rn in ("F-18", "Tc-99m"):
            continue  # controls (pre-existing)
        recs = _records(evidence, rn, "clinical_modality")
        assert recs, f"{rn} classified without a modality evidence record"


def test_16_modality_matches_evidence_normalized_value(evidence):
    for r in _records(evidence, dimension="clinical_modality"):
        rn = r["radionuclide"]
        assert _clinical_modality_for(rn) == r["normalized_value"]


# ---------------------------------------------------------------------------
# 17-20: controls preserved (F-18, Tc-99m, Mo-99)
# ---------------------------------------------------------------------------

def test_17_f18_preserved():
    hl = load_radionuclide_half_lives()
    assert hl["F-18"] == 109.8
    assert _clinical_modality_for("F-18") == "PET"
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_GE890,), selected_generator_ids=(_TECHNELITE,),
        selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    e = pf.entry_for("F-18")
    assert e.normal_admissible == "NORMAL_ADMISSIBLE"
    assert e.production_calibration_status == "MANUFACTURER_CALIBRATED"


def test_18_tc99m_preserved():
    hl = load_radionuclide_half_lives()
    assert hl["Tc-99m"] == 360.0
    assert _clinical_modality_for("Tc-99m") == "SPECT"


def test_19_mo99_parent_boundary_preserved():
    pf = _full_universe_portfolio()
    e = pf.entry_for("Mo-99")
    assert e.is_generator_parent is True
    assert e.clinical_modality is None            # generator parent: not patient demand
    assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_20_mo99_tc99m_generators_intact():
    cat = load_generator_catalog()
    mo99 = [m for m in cat.models if m.parent_radionuclide == "Mo-99"]
    assert {m.catalog_model_id for m in mo99} >= {
        "CURIUM_TECHNELITE", "CURIUM_ULTRA_TECHNEKOW_FM", "GE_HEALTHCARE_DRYTEC"
    }
    assert all(m.daughter_radionuclide == "Tc-99m" for m in mo99)


# ---------------------------------------------------------------------------
# 21-33: per-radionuclide completeness audit
# ---------------------------------------------------------------------------

def test_21_c11_audited(evidence):
    assert _clinical_modality_for("C-11") == "PET"
    assert _records(evidence, "C-11", "clinical_modality")


def test_22_n13_audited(evidence):
    assert _clinical_modality_for("N-13") == "PET"
    assert _records(evidence, "N-13", "clinical_modality")


def test_23_o15_audited(evidence):
    assert _clinical_modality_for("O-15") == "PET"
    assert _records(evidence, "O-15", "clinical_modality")


def test_24_ga68_audited_both_pathways(evidence):
    # Ga-68 has BOTH a cyclotron and a generator production pathway, kept distinct.
    assert _clinical_modality_for("Ga-68") == "PET"
    cyc_support = any("Ga-68" in m.supported_radionuclides for m in load_cyclotron_catalog().models)
    gen_daughter = any(m.daughter_radionuclide == "Ga-68" for m in load_generator_catalog().models)
    assert cyc_support and gen_daughter
    assert _records(evidence, "Ga-68", "generator_pathway")


def test_25_cu64_audited(evidence):
    hl = load_radionuclide_half_lives()
    assert hl["Cu-64"] == 762.0
    assert _clinical_modality_for("Cu-64") == "PET"
    assert _records(evidence, "Cu-64", "half_life")


def test_26_zr89_audited(evidence):
    hl = load_radionuclide_half_lives()
    assert hl["Zr-89"] == 4705.2
    assert _clinical_modality_for("Zr-89") == "PET"


def test_27_i123_audited(evidence):
    assert _clinical_modality_for("I-123") == "SPECT"  # gamma, NOT PET
    assert _records(evidence, "I-123", "half_life")


def test_28_i124_audited(evidence):
    assert _clinical_modality_for("I-124") == "PET"  # positron, NOT SPECT
    assert _records(evidence, "I-124", "half_life")


def test_29_i123_i124_classified_independently():
    # Same element, different emission -> different modality. Never inferred from
    # element identity.
    assert _clinical_modality_for("I-123") == "SPECT"
    assert _clinical_modality_for("I-124") == "PET"


def test_30_at211_audited_therapy_not_scanner(evidence):
    # At-211 is THERAPY (alpha): recognized in the registry, decay-authorized,
    # but carries NO diagnostic scanner modality and must never be forced into
    # PET/SPECT demand.
    hl = load_radionuclide_half_lives()
    assert hl["At-211"] == 432.96
    assert _clinical_modality_for("At-211") is None
    assert "At-211" not in MODALITY["PET"] and "At-211" not in MODALITY["SPECT"]
    recs = _records(evidence, "At-211")
    assert any(r["clinical_modality"] == "THERAPY" for r in recs)


def test_31_ge68_audited_generator_parent(evidence):
    hl = load_radionuclide_half_lives()
    assert hl["Ge-68"] == 390441.6
    assert _clinical_modality_for("Ge-68") is None  # generator parent, not administered
    pf = _full_universe_portfolio()
    assert pf.entry_for("Ge-68").is_generator_parent is True


def test_32_in111_audited(evidence):
    hl = load_radionuclide_half_lives()
    assert hl["In-111"] == pytest.approx(4038.912)
    assert _clinical_modality_for("In-111") == "SPECT"


def test_33_tl201_audited(evidence):
    hl = load_radionuclide_half_lives()
    assert hl["Tl-201"] == pytest.approx(4380.624)
    assert _clinical_modality_for("Tl-201") == "SPECT"


# ---------------------------------------------------------------------------
# 34-38: generator / cyclotron boundaries
# ---------------------------------------------------------------------------

def test_34_generator_parent_daughter_identity_preserved():
    cat = load_generator_catalog()
    pairs = {(m.parent_radionuclide, m.daughter_radionuclide) for m in cat.models}
    assert ("Mo-99", "Tc-99m") in pairs
    assert ("Ge-68", "Ga-68") in pairs
    # Parents and daughters never collapse together.
    parents = {p for p, _ in pairs}
    daughters = {d for _, d in pairs}
    assert not (parents & daughters)


def test_35_ge68_ga68_generator_now_canonical():
    ge_ga = [m for m in load_generator_catalog().models if m.parent_radionuclide == "Ge-68"]
    assert ge_ga
    # Generator-produced Ga-68 is admissible PET when the generator is selected.
    pf = resolve_clinical_radionuclide_portfolio(
        selected_generator_ids=(ge_ga[0].catalog_model_id,),
        selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    e = pf.entry_for("Ga-68")
    assert ge_ga[0].catalog_model_id in e.compatible_generator_ids
    assert e.normal_admissible == "NORMAL_ADMISSIBLE"


def test_36_model_specific_cyclotron_support_preserved():
    # Model identity is exact: GE890 supports F-18 only; the completeness build
    # never widened a specific model's supported_radionuclides.
    cat = load_cyclotron_catalog()
    assert cat.by_id(_GE890).supported_radionuclides == ("F-18",)


def test_37_no_cross_model_borrowing():
    # Selecting only GE890 (F-18) must not make Cu-64/Zr-89 admissible via GE890.
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_GE890,), selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    for rn in ("Cu-64", "Zr-89", "I-124"):
        e = pf.entry_for(rn)
        assert e.compatible_cyclotron_ids == ()  # GE890 does not support them
        assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_38_production_evidence_never_changes_clinical_identity():
    # A radionuclide's clinical modality is independent of production calibration
    # tier: CYPRIS (NOT_CALIBRATED) F-18 is still PET-classified & admissible.
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=("SUMITOMO_CYPRIS_MP_30",),
        selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    e = pf.entry_for("F-18")
    assert e.clinical_modality == "PET"
    assert e.production_calibration_status == "NOT_CALIBRATED"
    assert e.normal_admissible == "NORMAL_ADMISSIBLE"


# ---------------------------------------------------------------------------
# 39-43: scanner / therapy / prevalence separation
# ---------------------------------------------------------------------------

def test_39_clinical_evidence_never_fabricates_quantitative_production():
    # Modality evidence for Cu-64 (Detectnet) does NOT create a production number:
    # the portfolio production status stays NOT_CALIBRATED where uncalibrated.
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_KIUBE,), selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    e = pf.entry_for("Cu-64")
    assert e.clinical_modality == "PET"
    assert e.production_calibration_status in ("NOT_CALIBRATED", "MODELED")


def test_40_scanner_modality_respected():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_KIUBE,), selected_generator_ids=(_TECHNELITE,),
        selected_scanner_modalities=("PET",), mode="NORMAL",  # no SPECT scanner
    )
    # A SPECT radionuclide (I-123) becomes NO_COMPATIBLE_SCANNER without a SPECT scanner.
    e = pf.entry_for("I-123")
    assert e.scanner_modality_required == "SPECT"
    assert e.scanner_compatibility_status == "NO_COMPATIBLE_SCANNER"
    assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_41_therapy_only_radionuclide_not_forced_into_scanner_demand():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_30XP,),  # 30XP declares At-211
        selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    e = pf.entry_for("At-211")
    assert e.clinical_modality is None
    assert e.scanner_modality_required is None
    assert e.normal_admissible == "NORMAL_EXCLUDED"  # therapy, never scanner demand


def test_42_multi_radionuclide_weighting_not_fabricated():
    pf = _full_universe_portfolio()
    assert pf.multi_radionuclide_weighting_authority == "NOT_MODELED"


def test_43_portfolio_expanded_without_fabricated_prevalence():
    # The portfolio may now list MANY admissible radionuclides, but still assigns
    # NO prevalence mix (PORTFOLIO != DEMAND MIX).
    pf = _full_universe_portfolio()
    assert pf.normal_admissible_count >= 12
    assert pf.multi_radionuclide_weighting_authority == "NOT_MODELED"


# ---------------------------------------------------------------------------
# 44-50: modes, neutrality, seams
# ---------------------------------------------------------------------------

def test_44_normal_recomputed_from_canonical_authority():
    pf = _full_universe_portfolio()
    # Emergent from canonical authorities, not manually set. All 12 diagnostic,
    # decay-authorized, source-supported radionuclides are admissible.
    assert set(pf.normal_admissible_radionuclides) == {
        "F-18", "C-11", "N-13", "O-15", "Ga-68", "Cu-64", "Zr-89", "I-124",
        "Tc-99m", "I-123", "In-111", "Tl-201",
    }


def test_45_stress_preserves_all_identities():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_GE890,), selected_scanner_modalities=_BOTH, mode="STRESS_TEST",
    )
    assert set(pf.stress_visible_radionuclides) == _PHYSICAL_15


def test_46_explicit_demand_preserves_identities_and_no_fallback():
    from patient_radionuclide_demand import PatientRadionuclideDemand
    # Every physically-recognized radionuclide is now representable as explicit
    # demand (all decay-authorized); identity preserved verbatim, no substitution.
    for rn in ("Cu-64", "Zr-89", "At-211", "Ge-68", "I-124"):
        d = PatientRadionuclideDemand(patient_id="P", radionuclide=rn, prescribed_activity_mbq=185.0)
        assert d.radionuclide == rn  # no F-18/Tc-99m fallback


def test_47_no_f18_or_tc99m_fallback_on_no_source():
    r_pet = resolve_admissible_radionuclides(modality="PET")     # no source
    r_spect = resolve_admissible_radionuclides(modality="SPECT")  # no source
    assert r_pet.admissible_radionuclides == ()
    assert r_spect.admissible_radionuclides == ()


def test_48_portfolio_does_not_rank_architectures_or_award_mrt_bonus():
    # Architecture neutrality is a STRUCTURAL invariant: the portfolio module
    # imports no economics/transport authority and exposes no architecture/cost
    # ranking field. (The docstring may mention MRT/transport only to DECLARE the
    # absence of any such bias, so we assert on imports + fields, not prose.)
    import inspect
    import dataclasses
    import clinical_radionuclide_portfolio as mod
    src = inspect.getsource(mod)
    for forbidden_import in (
        "import equal_budget", "equipment_opex_authority", "apply_study_scope",
        "transport_technology_authority", "hybrid_optimization", "whole_oncology",
    ):
        assert forbidden_import not in src
    result_fields = {f.name.lower() for f in dataclasses.fields(mod.ClinicalRadionuclidePortfolioResult)}
    for forbidden in ("mrt", "npv", "capex", "opex", "lifecycle", "ranking", "advantage"):
        assert not any(forbidden in name for name in result_fields)


def test_49_short_half_life_not_preferentially_admitted():
    # Short-lived C-11/N-13/O-15 are admitted on EXACTLY the same footing as the
    # long-lived F-18 when a schedulable source is selected -- no short-half-life
    # multiplier, no MRT bonus.
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_PETTRACE_800,), selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    for rn in ("F-18", "C-11", "N-13", "O-15", "Ga-68"):
        assert pf.entry_for(rn).normal_admissible == "NORMAL_ADMISSIBLE"


def test_50_part3e_interface_remains_portfolio_only():
    pf = _full_universe_portfolio()
    import dataclasses
    result_fields = {f.name for f in dataclasses.fields(type(pf))}
    for forbidden in ("npv", "capex", "opex", "architecture", "ranking", "best", "demand_mix", "prevalence"):
        assert not any(forbidden in name for name in result_fields)
    # Part 3E eligibility is per-entry, expanded to the evidence-complete set.
    assert pf.entry_for("Cu-64").part3e_eligible == "PART3E_ELIGIBLE"


# ---------------------------------------------------------------------------
# Section 36 control proofs A-I
# ---------------------------------------------------------------------------

def test_proof_a_f18_control_no_regression():
    hl = load_radionuclide_half_lives()
    assert hl["F-18"] == 109.8
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_GE890,), selected_generator_ids=(_TECHNELITE,),
        selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    e = pf.entry_for("F-18")
    assert e.clinical_modality == "PET"
    assert e.production_calibration_status == "MANUFACTURER_CALIBRATED"
    assert e.normal_admissible == "NORMAL_ADMISSIBLE"


def test_proof_b_tc99m_mo99_boundary():
    cat = load_generator_catalog()
    assert any(m.parent_radionuclide == "Mo-99" and m.daughter_radionuclide == "Tc-99m" for m in cat.models)
    assert _clinical_modality_for("Tc-99m") == "SPECT"
    assert _clinical_modality_for("Mo-99") is None  # parent, never administered


def test_proof_c_c11_before_after():
    # BEFORE: C-11 had half-life but no modality -> excluded on modality.
    # AFTER : C-11 is PET-classified; excluded only for lack of a selected source
    #         in a bare scenario, admissible when its source is selected.
    assert _clinical_modality_for("C-11") == "PET"
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_PETTRACE_800,), selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    assert pf.entry_for("C-11").normal_admissible == "NORMAL_ADMISSIBLE"


def test_proof_d_n13_before_after():
    assert _clinical_modality_for("N-13") == "PET"
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_PETTRACE_800,), selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    assert pf.entry_for("N-13").normal_admissible == "NORMAL_ADMISSIBLE"


def test_proof_e_o15_before_after():
    assert _clinical_modality_for("O-15") == "PET"
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_PETTRACE_800,), selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    assert pf.entry_for("O-15").normal_admissible == "NORMAL_ADMISSIBLE"


def test_proof_f_ga68_cyclotron_and_generator_pathways():
    # Cyclotron pathway (PETtrace 800 supports Ga-68) and generator pathway
    # (Ge-68/Ga-68) are DISTINCT and independently admissible.
    ge_ga = next(m.catalog_model_id for m in load_generator_catalog().models if m.parent_radionuclide == "Ge-68")
    cyc_pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_PETTRACE_800,), selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    gen_pf = resolve_clinical_radionuclide_portfolio(
        selected_generator_ids=(ge_ga,), selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    cyc_e = cyc_pf.entry_for("Ga-68")
    gen_e = gen_pf.entry_for("Ga-68")
    assert cyc_e.compatible_cyclotron_ids and not cyc_e.compatible_generator_ids
    assert gen_e.compatible_generator_ids and not gen_e.compatible_cyclotron_ids
    assert cyc_e.normal_admissible == gen_e.normal_admissible == "NORMAL_ADMISSIBLE"


def test_proof_g_missing_half_life_control_now_propagated():
    # A formerly-missing isotope (Zr-89) now has canonical decay-data propagation
    # through the SINGLE decay authority.
    from multi_isotope_decay import retained_fraction
    hl = load_radionuclide_half_lives()
    assert "Zr-89" in hl and hl["Zr-89"] == 4705.2
    assert retained_fraction(hl["Zr-89"], hl["Zr-89"]) == pytest.approx(0.5)


def test_proof_h_no_cross_model_borrowing_stays_honest():
    # A model that SUPPORTS but is not quantitatively calibrated for a
    # radionuclide stays honest (NOT_CALIBRATED), never borrowing another model.
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=("SUMITOMO_CYPRIS_MP_30",),
        selected_scanner_modalities=_BOTH, mode="NORMAL",
    )
    e = pf.entry_for("Cu-64")  # CYPRIS supports Cu-64 but is not calibrated for it
    assert e.compatible_cyclotron_ids == ("SUMITOMO_CYPRIS_MP_30",)
    assert e.production_calibration_status == "NOT_CALIBRATED"


def test_proof_i_no_prevalence_fabrication_after_expansion():
    pf = _full_universe_portfolio()
    # Portfolio expanded (>=12 admissible) yet the demand mix stays NOT_MODELED.
    assert pf.normal_admissible_count >= 12
    assert pf.multi_radionuclide_weighting_authority == "NOT_MODELED"


# ---------------------------------------------------------------------------
# Canonical-change traceability (Section M.1): every promoted fact -> evidence
# ---------------------------------------------------------------------------

def test_every_new_half_life_has_evidence_record(evidence):
    for rn in ("Cu-64", "Zr-89", "Ge-68", "I-123", "I-124", "In-111", "Tl-201", "At-211"):
        assert _records(evidence, rn, "half_life"), f"{rn} half-life promoted without evidence"


def test_every_new_modality_has_evidence_record(evidence):
    newly_classified = (set(MODALITY["PET"]) | set(MODALITY["SPECT"])) - {"F-18", "Tc-99m"}
    for rn in newly_classified:
        assert _records(evidence, rn, "clinical_modality"), f"{rn} modality promoted without evidence"


def test_ge68_ga68_generator_has_evidence_record(evidence):
    assert _records(evidence, "Ga-68", "generator_pathway")

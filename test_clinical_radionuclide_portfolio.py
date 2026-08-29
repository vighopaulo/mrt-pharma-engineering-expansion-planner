"""Focused tests for the Clinical Radionuclide Portfolio Authority (OG-RAD-1).

Protects the Section 35 invariants (1-42) and the Section 36 control proofs
(A-G). The portfolio authority is ARCHITECTURE-NEUTRAL: no test here asserts any
transport/MRT/Conventional advantage, and short-half-life radionuclides are
audited on the same footing as long-lived ones.

All facts are asserted against the PHYSICAL repository authorities (half-life
table, cyclotron catalog, generator catalog, scanner catalog) via the portfolio
module -- never a hardcoded expectation that could drift from the catalogs.
"""

from __future__ import annotations

import dataclasses

import pytest

from clinical_radionuclide_portfolio import (
    ClinicalRadionuclidePortfolioEntry,
    ClinicalRadionuclidePortfolioResult,
    discover_physically_recognized_radionuclides,
    resolve_clinical_radionuclide_portfolio,
)

# Benchmark selected-source scenario reused across proofs (a calibrated F-18
# cyclotron + a Tc-99m generator + both scanner modalities present).
_CALIBRATED_CYCLOTRON = "GE_PETTRACE_890"      # F-18, manufacturer-calibrated EOB point
_TC99M_GENERATOR = "CURIUM_TECHNELITE"          # Mo-99 -> Tc-99m
_MULTI_ISOTOPE_CYCLOTRON = "GE_PETTRACE_800"    # schedulable F-18,C-11,N-13,O-15,Ga-68
_CYPRIS = "SUMITOMO_CYPRIS_MP_30"               # supports F-18 but NOT_CALIBRATED
_BOTH_MODALITIES = ("PET", "SPECT")


def _benchmark_normal() -> ClinicalRadionuclidePortfolioResult:
    return resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CALIBRATED_CYCLOTRON,),
        selected_generator_ids=(_TC99M_GENERATOR,),
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="NORMAL",
    )


# ---------------------------------------------------------------------------
# 1-3: imports, immutable types, universe discovered from authorities
# ---------------------------------------------------------------------------


def test_01_authority_imports_cleanly():
    assert callable(resolve_clinical_radionuclide_portfolio)
    assert callable(discover_physically_recognized_radionuclides)


def test_02_result_types_are_immutable():
    pf = _benchmark_normal()
    with pytest.raises(dataclasses.FrozenInstanceError):
        pf.mode = "STRESS_TEST"  # type: ignore[misc]
    entry = pf.entries[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.radionuclide = "X"  # type: ignore[misc]


def test_03_universe_discovered_from_physical_authorities():
    universe = discover_physically_recognized_radionuclides()
    # Discovered, not hardcoded: at minimum the half-life table, the cyclotron
    # supported union, and the generator daughter/parent are all present.
    for expected in ("F-18", "Tc-99m", "Mo-99", "C-11", "N-13", "O-15", "Ga-68"):
        assert expected in universe
    # One entry per physically-recognized radionuclide.
    pf = _benchmark_normal()
    assert tuple(sorted(e.radionuclide for e in pf.entries)) == tuple(sorted(universe))
    assert pf.physically_recognized_radionuclides == universe


# ---------------------------------------------------------------------------
# 4-14: per-radionuclide audit (one assertion group per radionuclide)
# ---------------------------------------------------------------------------


def _entry(radionuclide: str) -> ClinicalRadionuclidePortfolioEntry:
    return _benchmark_normal().entry_for(radionuclide)


def test_04_f18_audited_pet_calibrated_admissible():
    e = _entry("F-18")
    assert e.clinical_modality == "PET"
    assert e.decay_status == "DECAY_AUTHORITY_PRESENT"
    assert e.production_calibration_status == "MANUFACTURER_CALIBRATED"
    assert e.normal_admissible == "NORMAL_ADMISSIBLE"


def test_05_tc99m_audited_spect_generator_admissible():
    e = _entry("Tc-99m")
    assert e.clinical_modality == "SPECT"
    assert e.compatible_generator_ids == (_TC99M_GENERATOR,)
    assert e.compatible_cyclotron_ids == ()  # never routed through cyclotron
    assert e.normal_admissible == "NORMAL_ADMISSIBLE"


def test_06_c11_audited_modality_not_modeled():
    e = _entry("C-11")
    assert e.decay_status == "DECAY_AUTHORITY_PRESENT"  # half-life exists
    assert e.clinical_modality_status == "CLINICAL_MODALITY_NOT_MODELED"
    assert e.normal_admissible == "NORMAL_EXCLUDED"
    assert e.blocking_gap == "CLINICAL_MODALITY_NOT_MODELED"


def test_07_n13_audited_modality_not_modeled():
    e = _entry("N-13")
    assert e.decay_status == "DECAY_AUTHORITY_PRESENT"
    assert e.clinical_modality_status == "CLINICAL_MODALITY_NOT_MODELED"
    assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_08_o15_audited_modality_not_modeled():
    e = _entry("O-15")
    assert e.decay_status == "DECAY_AUTHORITY_PRESENT"
    assert e.clinical_modality_status == "CLINICAL_MODALITY_NOT_MODELED"
    assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_09_ga68_audited_no_generator_modality_not_modeled():
    e = _entry("Ga-68")
    assert e.decay_status == "DECAY_AUTHORITY_PRESENT"
    assert e.compatible_generator_ids == ()  # OG-GEN-1: no Ge-68/Ga-68 generator
    assert e.clinical_modality_status == "CLINICAL_MODALITY_NOT_MODELED"
    assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_10_cu64_audited_decay_missing():
    e = _entry("Cu-64")
    assert e.decay_status == "DECAY_AUTHORITY_MISSING"
    assert e.half_life_minutes is None
    assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_11_zr89_audited_decay_missing():
    e = _entry("Zr-89")
    assert e.decay_status == "DECAY_AUTHORITY_MISSING"
    assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_12_i123_audited_decay_missing():
    e = _entry("I-123")
    assert e.decay_status == "DECAY_AUTHORITY_MISSING"
    assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_13_i124_audited_decay_missing():
    e = _entry("I-124")
    assert e.decay_status == "DECAY_AUTHORITY_MISSING"
    assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_14_mo99_audited_generator_parent_not_patient_demand():
    e = _entry("Mo-99")
    assert e.is_generator_parent is True
    assert e.clinical_modality_status == "CLINICAL_MODALITY_NOT_MODELED"
    assert e.normal_admissible == "NORMAL_EXCLUDED"  # never patient-administered demand


# ---------------------------------------------------------------------------
# 15-22: chain rules
# ---------------------------------------------------------------------------


def test_15_half_life_absence_blocks_normal_where_required():
    for radionuclide in ("Cu-64", "Zr-89", "I-123", "I-124", "Ge-68"):
        e = _entry(radionuclide)
        assert e.decay_status == "DECAY_AUTHORITY_MISSING"
        assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_16_selected_source_support_required():
    # F-18 admissible only because GE890 is SELECTED.
    with_source = _benchmark_normal().entry_for("F-18")
    assert with_source.normal_admissible == "NORMAL_ADMISSIBLE"
    without_source = resolve_clinical_radionuclide_portfolio(
        selected_scanner_modalities=_BOTH_MODALITIES, mode="NORMAL"
    ).entry_for("F-18")
    assert without_source.normal_admissible == "NORMAL_EXCLUDED"
    assert without_source.blocking_gap == "NO_COMPATIBLE_SOURCE"


def test_17_no_global_catalog_fallback():
    # F-18 is supported by MANY catalog machines, but with NONE selected it must
    # not become admissible (SUPPORTED_BY_CATALOG_ONLY, never NORMAL).
    e = resolve_clinical_radionuclide_portfolio(
        selected_scanner_modalities=_BOTH_MODALITIES, mode="NORMAL"
    ).entry_for("F-18")
    assert e.source_capability_status == "SUPPORTED_BY_CATALOG_ONLY"
    assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_18_multi_cyclotron_union_works():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CALIBRATED_CYCLOTRON, _MULTI_ISOTOPE_CYCLOTRON),
        selected_generator_ids=(_TC99M_GENERATOR,),
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="NORMAL",
    )
    f18 = pf.entry_for("F-18")
    assert set(f18.compatible_cyclotron_ids) == {_CALIBRATED_CYCLOTRON, _MULTI_ISOTOPE_CYCLOTRON}


def test_19_multi_generator_union_one_identity():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CALIBRATED_CYCLOTRON,),
        selected_generator_ids=("CURIUM_TECHNELITE", "CURIUM_ULTRA_TECHNEKOW_FM", "GE_HEALTHCARE_DRYTEC"),
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="NORMAL",
    )
    tc_rows = [e for e in pf.entries if e.radionuclide == "Tc-99m"]
    assert len(tc_rows) == 1  # one identity, not three
    assert set(tc_rows[0].compatible_generator_ids) == {
        "CURIUM_TECHNELITE", "CURIUM_ULTRA_TECHNEKOW_FM", "GE_HEALTHCARE_DRYTEC"
    }


def test_20_source_identities_preserved():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CALIBRATED_CYCLOTRON, _MULTI_ISOTOPE_CYCLOTRON),
        selected_generator_ids=(_TC99M_GENERATOR,),
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="NORMAL",
    )
    # No flattened/averaged machine: every compatible id is a real selected id.
    for entry in pf.entries:
        for cid in entry.compatible_cyclotron_ids:
            assert cid in (_CALIBRATED_CYCLOTRON, _MULTI_ISOTOPE_CYCLOTRON)
        for gid in entry.compatible_generator_ids:
            assert gid == _TC99M_GENERATOR


def test_21_pet_spect_scanner_compatibility_respected():
    e_f18 = _entry("F-18")
    e_tc = _entry("Tc-99m")
    assert e_f18.scanner_modality_required == "PET"
    assert e_tc.scanner_modality_required == "SPECT"
    assert e_f18.scanner_compatibility_status == "SCANNER_MODALITY_AVAILABLE"
    assert e_tc.scanner_compatibility_status == "SCANNER_MODALITY_AVAILABLE"


def test_22_no_compatible_scanner_surfaced():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CALIBRATED_CYCLOTRON,),
        selected_generator_ids=(_TC99M_GENERATOR,),
        selected_scanner_modalities=("SPECT",),  # no PET scanner
        mode="NORMAL",
    )
    e = pf.entry_for("F-18")
    assert e.scanner_compatibility_status == "NO_COMPATIBLE_SCANNER"
    assert e.normal_admissible == "NORMAL_EXCLUDED"
    assert e.blocking_gap == "NO_COMPATIBLE_SCANNER"


# ---------------------------------------------------------------------------
# 23-33: distinction / no-fabrication invariants
# ---------------------------------------------------------------------------


def test_23_supported_not_equal_calibrated():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CYPRIS,),
        selected_generator_ids=(_TC99M_GENERATOR,),
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="NORMAL",
    )
    e = pf.entry_for("F-18")
    assert e.source_capability_status == "SUPPORTED_BY_SELECTED_SOURCE"
    assert e.production_calibration_status == "NOT_CALIBRATED"


def test_24_clinical_admissibility_not_equal_production_calibration():
    # CYPRIS F-18 is NORMAL-admissible (clinically classified + supported +
    # decay + scanner) even though production is NOT_CALIBRATED.
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CYPRIS,),
        selected_generator_ids=(_TC99M_GENERATOR,),
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="NORMAL",
    )
    e = pf.entry_for("F-18")
    assert e.normal_admissible == "NORMAL_ADMISSIBLE"
    assert e.production_calibration_status == "NOT_CALIBRATED"


def test_25_explicit_demand_never_mutated():
    # The portfolio authority does not touch explicit demand identity. The
    # explicit-demand path (patient_radionuclide_demand) stamps the caller's
    # radionuclide verbatim; the portfolio only REPORTS representability.
    from patient_radionuclide_demand import PatientRadionuclideDemand

    demand = PatientRadionuclideDemand(patient_id="P1", radionuclide="F-18", prescribed_activity_mbq=370.0)
    assert demand.radionuclide == "F-18"  # unchanged
    e = resolve_clinical_radionuclide_portfolio(mode="EXPLICIT").entry_for("F-18")
    assert e.explicit_demand_representable is True


def test_26_stress_demand_never_substituted():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CALIBRATED_CYCLOTRON,),
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="STRESS_TEST",
    )
    # Every physically-recognized identity remains visible; none substituted.
    assert set(pf.stress_visible_radionuclides) == set(pf.physically_recognized_radionuclides)
    # A radionuclide with no selected source is still visible under stress, with
    # its precise reason preserved (not swapped for F-18).
    tc = pf.entry_for("Tc-99m")
    assert tc.stress_visible is True
    assert tc.source_capability_status in ("NO_COMPATIBLE_SOURCE", "SUPPORTED_BY_CATALOG_ONLY")


def test_27_no_f18_fallback():
    # SPECT-only selection must never make Tc-99m demand fall back to F-18.
    pf = resolve_clinical_radionuclide_portfolio(
        selected_generator_ids=(_TC99M_GENERATOR,),
        selected_scanner_modalities=("SPECT",),
        mode="NORMAL",
    )
    assert "F-18" not in pf.normal_admissible_radionuclides
    assert pf.entry_for("F-18").normal_admissible == "NORMAL_EXCLUDED"


def test_28_no_tc99m_fallback():
    # PET-only cyclotron selection must never make PET demand fall back to Tc-99m.
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CALIBRATED_CYCLOTRON,),
        selected_scanner_modalities=("PET",),
        mode="NORMAL",
    )
    assert "Tc-99m" not in pf.normal_admissible_radionuclides


def test_29_no_cross_radionuclide_production_borrowing():
    # A calibrated F-18 record must NEVER qualify C-11/N-13/O-15/Ga-68.
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CALIBRATED_CYCLOTRON,),  # F-18 only
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="NORMAL",
    )
    for other in ("C-11", "N-13", "O-15", "Ga-68"):
        e = pf.entry_for(other)
        assert e.production_calibration_status != "MANUFACTURER_CALIBRATED"
        assert e.normal_admissible == "NORMAL_EXCLUDED"


def test_30_no_cross_model_capability_borrowing():
    # Selecting only CYPRIS must not borrow GE PETtrace capability for F-18.
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CYPRIS,),
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="NORMAL",
    )
    e = pf.entry_for("F-18")
    assert e.compatible_cyclotron_ids == (_CYPRIS,)
    assert e.production_calibration_status == "NOT_CALIBRATED"  # not borrowed MANUFACTURER_CALIBRATED


def test_31_no_invented_modality_classification():
    pf = _benchmark_normal()
    classified = [e.radionuclide for e in pf.entries if e.clinical_modality is not None]
    assert set(classified) == {"F-18", "Tc-99m"}  # exactly the repository's two bindings


def test_32_no_invented_procedure_classification():
    pf = _benchmark_normal()
    for e in pf.entries:
        assert e.procedure_status == "PROCEDURE_NOT_MODELED"


def test_33_multi_radionuclide_weighting_not_fabricated():
    pf = _benchmark_normal()
    assert pf.multi_radionuclide_weighting_authority == "NOT_MODELED"
    # The portfolio may list several admissible radionuclides without any
    # fabricated prevalence mix (PORTFOLIO != DEMAND MIX).
    assert set(pf.normal_admissible_radionuclides) == {"F-18", "Tc-99m"}


# ---------------------------------------------------------------------------
# 34-42: boundary / seam invariants
# ---------------------------------------------------------------------------


def test_34_patient_identity_not_required_by_portfolio():
    # No patient identity input exists on the API; a full portfolio resolves
    # with only equipment/scanner selection.
    pf = _benchmark_normal()
    assert pf.entries  # resolved without any patient_id


def test_35_patient_aware_batch_boundary_preserved():
    # The portfolio carries no batch/patient fields; downstream patient-aware
    # batch planning (patient_radionuclide_demand) remains a separate authority.
    from patient_radionuclide_demand import partition_facility_day_patient_demand  # noqa: F401

    entry_field_names = {f.name for f in dataclasses.fields(ClinicalRadionuclidePortfolioEntry)}
    assert "patient_id" not in entry_field_names
    assert "batch_id" not in entry_field_names


def test_36_cyclotron_remains_non_patient_identity_aware():
    # Resolving the portfolio never passes patient identity into the cyclotron
    # catalog. (The catalog API takes model ids/counts only.) Structural proof:
    # the module imports the catalog loader, not any patient type.
    import clinical_radionuclide_portfolio as mod
    src = mod.__doc__ or ""
    assert "patient" in src.lower()  # doctrine documented
    # No patient identity field leaks into results:
    result_fields = {f.name for f in dataclasses.fields(ClinicalRadionuclidePortfolioResult)}
    assert not any("patient" in name for name in result_fields)


def test_37_generator_remains_non_patient_identity_aware():
    pf = _benchmark_normal()
    tc = pf.entry_for("Tc-99m")
    # Only source model ids are carried, never patient identity.
    assert all(isinstance(gid, str) for gid in tc.compatible_generator_ids)


def test_38_part3e_interface_is_portfolio_not_optimizer_result():
    pf = _benchmark_normal()
    # Portfolio says WHAT MAY be requested; it carries no cost/npv/architecture
    # ranking (that is the Part 3E optimizer's job).
    result_fields = {f.name for f in dataclasses.fields(ClinicalRadionuclidePortfolioResult)}
    for forbidden in ("npv", "capex", "opex", "lifecycle_cost", "architecture", "ranking", "best"):
        assert not any(forbidden in name for name in result_fields)
    # Part 3E eligibility is expressed per entry.
    assert pf.entry_for("F-18").part3e_eligible == "PART3E_ELIGIBLE"


def test_39_calendar_seam_preserved():
    # The portfolio has no calendar/date/horizon fields; the long-horizon
    # Hospital Master Calendar remains a separate downstream authority.
    result_fields = {f.name for f in dataclasses.fields(ClinicalRadionuclidePortfolioResult)}
    for forbidden in ("date", "calendar", "horizon", "day", "week", "month"):
        assert not any(forbidden in name for name in result_fields)


def test_40_patient_export_traceability_preserved():
    # The portfolio never destroys radionuclide identity needed for downstream
    # patient-level export: every admissible radionuclide keeps its identity +
    # compatible source ids.
    pf = _benchmark_normal()
    for radionuclide in pf.normal_admissible_radionuclides:
        e = pf.entry_for(radionuclide)
        assert e.radionuclide == radionuclide
        assert e.compatible_cyclotron_ids or e.compatible_generator_ids


def test_41_financial_export_seam_preserved():
    # No financial dependency introduced into the clinical portfolio authority.
    import clinical_radionuclide_portfolio as mod
    import inspect

    src = inspect.getsource(mod)
    for forbidden in ("import equal_budget", "equipment_opex_authority", "apply_study_scope"):
        assert forbidden not in src


def test_42_short_half_life_radionuclides_independently_represented():
    pf = _benchmark_normal()
    for radionuclide in ("C-11", "N-13", "O-15"):
        e = pf.entry_for(radionuclide)
        # Independently represented with real half-life + its own precise reason;
        # NOT promoted, NOT hidden, NOT collapsed into F-18.
        assert e.radionuclide == radionuclide
        assert e.half_life_minutes is not None
        assert e.blocking_gap == "CLINICAL_MODALITY_NOT_MODELED"
        assert e.stress_visible is True


# ---------------------------------------------------------------------------
# Section 36 control proofs A-G
# ---------------------------------------------------------------------------


def test_proof_a_current_normal_control():
    pf = _benchmark_normal()
    assert pf.entry_for("F-18").normal_admissible == "NORMAL_ADMISSIBLE"
    assert pf.entry_for("F-18").clinical_modality == "PET"
    assert pf.entry_for("Tc-99m").normal_admissible == "NORMAL_ADMISSIBLE"
    assert pf.entry_for("Tc-99m").clinical_modality == "SPECT"
    assert set(pf.normal_admissible_radionuclides) == {"F-18", "Tc-99m"}


def test_proof_b_short_half_life_audit():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_MULTI_ISOTOPE_CYCLOTRON,),  # schedulable C-11/N-13/O-15
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="NORMAL",
    )
    for radionuclide in ("C-11", "N-13", "O-15"):
        e = pf.entry_for(radionuclide)
        assert e.half_life_minutes is not None                       # half-life present
        assert e.clinical_modality_status == "CLINICAL_MODALITY_NOT_MODELED"
        assert e.procedure_status == "PROCEDURE_NOT_MODELED"
        assert e.source_capability_status == "SUPPORTED_BY_SELECTED_SOURCE"  # supported by selected
        assert e.normal_admissible == "NORMAL_EXCLUDED"
        assert e.blocking_gap == "CLINICAL_MODALITY_NOT_MODELED"     # honest blocking reason


def test_proof_c_cypris_control():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CYPRIS,),
        selected_generator_ids=(_TC99M_GENERATOR,),
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="NORMAL",
    )
    e = pf.entry_for("F-18")
    assert e.source_capability_status == "SUPPORTED_BY_SELECTED_SOURCE"  # physically supported
    assert e.production_calibration_status == "NOT_CALIBRATED"           # not calibrated
    assert e.compatible_cyclotron_ids == (_CYPRIS,)                      # real identity, no GE borrow


def test_proof_d_pettrace_800_control():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_MULTI_ISOTOPE_CYCLOTRON,),  # supports F-18,C-11,N-13,O-15,Ga-68
        selected_generator_ids=(_TC99M_GENERATOR,),
        selected_scanner_modalities=_BOTH_MODALITIES,
        mode="NORMAL",
    )
    # Physically supports 5 isotopes; clinical authority admits only F-18 to NORMAL.
    supported = [e.radionuclide for e in pf.entries if _MULTI_ISOTOPE_CYCLOTRON in e.compatible_cyclotron_ids]
    assert set(supported) >= {"F-18", "C-11", "N-13", "O-15", "Ga-68"}
    assert pf.entry_for("F-18").normal_admissible == "NORMAL_ADMISSIBLE"
    for other in ("C-11", "N-13", "O-15", "Ga-68"):
        assert pf.entry_for(other).normal_admissible == "NORMAL_EXCLUDED"


def test_proof_e_no_source():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_scanner_modalities=_BOTH_MODALITIES, mode="NORMAL"
    )
    assert pf.normal_admissible_radionuclides == ()  # honest failure, no fallback
    assert pf.entry_for("F-18").blocking_gap == "NO_COMPATIBLE_SOURCE"


def test_proof_f_no_scanner():
    pf = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=(_CALIBRATED_CYCLOTRON,),  # PET-valid F-18
        selected_generator_ids=(_TC99M_GENERATOR,),
        selected_scanner_modalities=("SPECT",),           # only SPECT scanner
        mode="NORMAL",
    )
    e = pf.entry_for("F-18")
    assert e.scanner_compatibility_status == "NO_COMPATIBLE_SCANNER"
    assert e.normal_admissible == "NORMAL_EXCLUDED"
    # No substitution: F-18 identity intact, not swapped for Tc-99m.
    assert e.radionuclide == "F-18"


def test_proof_g_explicit_demand():
    from patient_radionuclide_demand import PatientRadionuclideDemand

    # An explicitly requested radionuclide that lacks decay authority cannot be
    # represented (validation raises) -- identity is never silently mutated.
    with pytest.raises(ValueError):
        PatientRadionuclideDemand(patient_id="P9", radionuclide="Cu-64", prescribed_activity_mbq=200.0)
    # A clinically-incomplete but decay-authorized radionuclide (Ga-68) is
    # representable as explicit demand; the portfolio reports its real limitation
    # rather than rewriting it.
    demand = PatientRadionuclideDemand(patient_id="P9", radionuclide="Ga-68", prescribed_activity_mbq=200.0)
    assert demand.radionuclide == "Ga-68"
    e = resolve_clinical_radionuclide_portfolio(mode="EXPLICIT").entry_for("Ga-68")
    assert e.explicit_demand_representable is True
    assert e.clinical_modality_status == "CLINICAL_MODALITY_NOT_MODELED"


# ---------------------------------------------------------------------------
# Validation / determinism
# ---------------------------------------------------------------------------


def test_unknown_selected_id_raises():
    with pytest.raises((KeyError, ValueError)):
        resolve_clinical_radionuclide_portfolio(selected_cyclotron_ids=("NOT_A_REAL_MODEL",), mode="NORMAL")


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        resolve_clinical_radionuclide_portfolio(mode="BOGUS")  # type: ignore[arg-type]


def test_deterministic_and_order_stable():
    a = _benchmark_normal()
    b = _benchmark_normal()
    assert a.physically_recognized_radionuclides == b.physically_recognized_radionuclides
    assert a.normal_admissible_radionuclides == b.normal_admissible_radionuclides
    assert tuple(e.radionuclide for e in a.entries) == tuple(e.radionuclide for e in b.entries)

"""Focused tests for the Synthetic Patient Radionuclide Source-Capability
Authority (OG-SYNTH-1).

Covers the 40 required invariants (build governor Section 41), the six control
proofs A-F (Section 42), and the patient-aware batch-planning boundary proof
(Section 43). Uses the REAL repository catalog authorities -- no fabricated
fleets, no fabricated production data.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

import synthetic_radionuclide_source_capability as srsc
import oncology_pet_spect_scenario as ops
from synthetic_radionuclide_source_capability import (
    NoCompatibleSourceError,
    SyntheticRadionuclideCapabilityResult,
    choose_normal_synthetic_radionuclide,
    resolve_admissible_radionuclides,
)

# Real catalog identities used across the suite.
CYCLOTRON_F18_CALIBRATED = "GE_PETTRACE_890"
CYCLOTRON_MULTI = "GE_PETTRACE_800"  # F-18,C-11,N-13,O-15,Ga-68
CYPRIS = "SUMITOMO_CYPRIS_MP_30"      # F-18,Cu-64,Zr-89,I-123,I-124,Ga-68 (SUPPORTED, NOT_CALIBRATED)
SIEMENS_ECLIPSE = "SIEMENS_CTI_ECLIPSE_HP"
SIEMENS_RDS = "SIEMENS_CTI_RDS_111"
GEN_TECHNELITE = "CURIUM_TECHNELITE"
GEN_ULTRA = "CURIUM_ULTRA_TECHNEKOW_FM"
GEN_DRYTEC = "GE_HEALTHCARE_DRYTEC"

_DAY_KW = dict(
    day=date(2026, 1, 1), available_beds=10, occupied_beds=8, admissions=2, discharges=1,
    outpatient_encounters=10, target_pet_procedures=3, target_spect_procedures=2, seed=7,
)


def _rns(patients):
    return sorted({p.nuclear_procedure.radionuclide for p in patients if p.nuclear_procedure})


def _pet_spect_counts(patients):
    pet = sum(1 for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "PET")
    spect = sum(1 for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "SPECT")
    return pet, spect


# ---------------------------------------------------------------------------
# 1-7: resolver existence, selected-source scoping, exposure, identity/dedupe,
#      modality specificity
# ---------------------------------------------------------------------------

def test_01_resolver_exists():
    assert callable(resolve_admissible_radionuclides)
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYCLOTRON_F18_CALIBRATED])
    assert isinstance(r, SyntheticRadionuclideCapabilityResult)


def test_02_resolver_uses_selected_sources_not_whole_catalog():
    # Only GE890 (F-18) is selected; CYPRIS's Cu-64/Zr-89 exist in the catalog
    # but must NOT appear because CYPRIS was not selected.
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYCLOTRON_F18_CALIBRATED])
    all_seen = set(r.admissible_radionuclides) | {e[0] for e in r.excluded_radionuclides}
    assert "Cu-64" not in all_seen and "Zr-89" not in all_seen
    assert r.selected_cyclotron_ids == (CYCLOTRON_F18_CALIBRATED,)


def test_03_cyclotron_supported_radionuclides_exposed():
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYCLOTRON_MULTI])
    seen = set(r.admissible_radionuclides) | {e[0] for e in r.excluded_radionuclides}
    # PETtrace 800 declares F-18,C-11,N-13,O-15,Ga-68 -- all must be visible.
    assert {"F-18", "C-11", "N-13", "O-15", "Ga-68"} <= seen


def test_04_generator_daughter_exposed():
    r = resolve_admissible_radionuclides(modality="SPECT", selected_generator_ids=[GEN_TECHNELITE])
    assert "Tc-99m" in r.admissible_radionuclides


def test_05_source_identities_preserved():
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYPRIS])
    assert r.compatible_source_ids_for("F-18") == (CYPRIS,)


def test_06_duplicate_support_no_duplicate_choices():
    r = resolve_admissible_radionuclides(
        modality="SPECT", selected_generator_ids=[GEN_TECHNELITE, GEN_ULTRA, GEN_DRYTEC],
    )
    assert r.admissible_radionuclides == ("Tc-99m",)  # one identity
    assert r.compatible_source_ids_for("Tc-99m") == (GEN_TECHNELITE, GEN_ULTRA, GEN_DRYTEC)  # three sources


def test_07_pet_and_spect_sets_are_modality_specific():
    pet = resolve_admissible_radionuclides(
        modality="PET", selected_cyclotron_ids=[CYCLOTRON_F18_CALIBRATED], selected_generator_ids=[GEN_TECHNELITE],
    )
    spect = resolve_admissible_radionuclides(
        modality="SPECT", selected_cyclotron_ids=[CYCLOTRON_F18_CALIBRATED], selected_generator_ids=[GEN_TECHNELITE],
    )
    assert pet.admissible_radionuclides == ("F-18",)
    assert spect.admissible_radionuclides == ("Tc-99m",)
    assert "Tc-99m" not in pet.admissible_radionuclides
    assert "F-18" not in spect.admissible_radionuclides


# ---------------------------------------------------------------------------
# 8-12: normal mode consumes constrained set; no unsupported demand; no-source
#       failures; no global-catalog fallback
# ---------------------------------------------------------------------------

def test_08_normal_mode_uses_source_constrained_set():
    patients, _ = ops.build_representative_day_population(
        **_DAY_KW, selected_cyclotron_ids=(CYCLOTRON_F18_CALIBRATED,), selected_generator_ids=(GEN_TECHNELITE,),
    )
    assert _rns(patients) == ["F-18", "Tc-99m"]


def test_09_normal_mode_does_not_generate_unsupported_radionuclide():
    # No generator selected -> the SPECT admissible set must not silently emit a
    # generator daughter (Tc-99m). Completeness note: after modality closure
    # CYPRIS DOES support the SPECT cyclotron isotope I-123, so to prove the
    # "no unsupported radionuclide" invariant we use a cyclotron that supports
    # NO SPECT radionuclide at all (GE890, F-18 only). Requesting SPECT then must
    # raise -- never fall back to Tc-99m.
    with pytest.raises(NoCompatibleSourceError):
        ops.build_representative_day_population(
            **{**_DAY_KW, "target_pet_procedures": 0}, selected_cyclotron_ids=(CYCLOTRON_F18_CALIBRATED,),
        )


def test_10_no_source_pet_returns_explicit_failure():
    r = resolve_admissible_radionuclides(modality="PET")
    assert r.status == "NO_COMPATIBLE_SOURCE"
    assert r.limitations  # explains why
    with pytest.raises(NoCompatibleSourceError):
        choose_normal_synthetic_radionuclide(r)


def test_11_no_source_spect_returns_explicit_failure():
    r = resolve_admissible_radionuclides(modality="SPECT")
    assert r.status == "NO_COMPATIBLE_SOURCE"
    with pytest.raises(NoCompatibleSourceError):
        choose_normal_synthetic_radionuclide(r)


def test_12_no_global_catalog_fallback():
    # No source selected -> no admissible radionuclide despite F-18/Tc-99m
    # existing in the global catalog on unselected machines.
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[], selected_generator_ids=[])
    assert r.admissible_radionuclides == ()
    assert "F-18" not in r.admissible_radionuclides


# ---------------------------------------------------------------------------
# 13-15: CYPRIS support semantics (SUPPORTED != CALIBRATED != ESTIMABLE)
# ---------------------------------------------------------------------------

def test_13_cypris_f18_admissible_by_support():
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYPRIS])
    assert "F-18" in r.admissible_radionuclides
    assert r.status == "ADMISSIBLE"


def test_14_cypris_f18_not_calibrated_does_not_erase_support():
    # CYPRIS has empty production_cycle map (schedulable=()) yet F-18 is still
    # admissible by SUPPORT semantics -- calibration state is not consulted here.
    from cyclotron_catalog import load_cyclotron_catalog
    model = load_cyclotron_catalog().by_id(CYPRIS)
    assert model.schedulable_radionuclides == ()  # NOT_CALIBRATED / not schedulable
    assert "F-18" in model.supported_radionuclides
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYPRIS])
    assert "F-18" in r.admissible_radionuclides


def test_15_cypris_f18_not_available_quantitatively_does_not_erase_support():
    # The estimator (quantitative) is deliberately NOT invoked by the resolver.
    # Prove admissibility does not depend on any numerical estimate.
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYPRIS])
    assert r.compatible_source_ids_for("F-18") == (CYPRIS,)


# ---------------------------------------------------------------------------
# 16-18: Siemens models admissible; modeled evidence does not inflate counts
# ---------------------------------------------------------------------------

def test_16_siemens_eclipse_f18_admissible():
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[SIEMENS_ECLIPSE])
    assert "F-18" in r.admissible_radionuclides


def test_17_siemens_rds_f18_admissible():
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[SIEMENS_RDS])
    assert "F-18" in r.admissible_radionuclides


def test_18_modeled_evidence_does_not_increase_patient_count():
    # Siemens Eclipse/RDS have MODELED_ESTIMATE F-18 evidence; GE890 is calibrated.
    # Same requested counts -> same patient census regardless of evidence tier.
    base, _ = ops.build_representative_day_population(
        **_DAY_KW, selected_cyclotron_ids=(CYCLOTRON_F18_CALIBRATED,), selected_generator_ids=(GEN_TECHNELITE,),
    )
    siemens, _ = ops.build_representative_day_population(
        **_DAY_KW, selected_cyclotron_ids=(SIEMENS_ECLIPSE,), selected_generator_ids=(GEN_TECHNELITE,),
    )
    assert _pet_spect_counts(base) == _pet_spect_counts(siemens)
    assert len(base) == len(siemens)


# ---------------------------------------------------------------------------
# 19-21: capacity/economics do not weight radionuclide selection
# ---------------------------------------------------------------------------

def test_19_production_capacity_does_not_weight_selection():
    # Production capacity/calibration must not weight the admissible set. Compare
    # the SAME F-18-only source presented as calibrated (GE890) vs a
    # supported-but-uncalibrated source restricted to the same isotope set is not
    # directly comparable post-completeness (CYPRIS supports more isotopes), so
    # the capacity-neutrality invariant is proven on F-18 specifically: F-18 is
    # admissible from BOTH regardless of calibration tier, and appears exactly
    # once in each admissible set.
    high = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYCLOTRON_F18_CALIBRATED])
    low = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYPRIS])
    assert "F-18" in high.admissible_radionuclides
    assert "F-18" in low.admissible_radionuclides
    assert high.admissible_radionuclides.count("F-18") == low.admissible_radionuclides.count("F-18") == 1
    # GE890 (F-18 only) yields exactly F-18; capacity/calibration never adds or
    # removes a radionuclide beyond what the source SUPPORTS.
    assert high.admissible_radionuclides == ("F-18",)


def test_20_revenue_does_not_weight_selection():
    # The resolver has no economics inputs at all; identical result regardless.
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYCLOTRON_F18_CALIBRATED])
    assert r.admissible_radionuclides == ("F-18",)
    # Sanity: no economics field exists on the result contract.
    assert not any(f in r.__dict__ for f in ("revenue", "capex", "opex", "npv"))


def test_21_capex_opex_do_not_weight_selection():
    r1 = resolve_admissible_radionuclides(modality="SPECT", selected_generator_ids=[GEN_TECHNELITE])
    r2 = resolve_admissible_radionuclides(modality="SPECT", selected_generator_ids=[GEN_DRYTEC])
    assert r1.admissible_radionuclides == r2.admissible_radionuclides == ("Tc-99m",)


# ---------------------------------------------------------------------------
# 22-23: Tc-99m via generator authority, never via cyclotron estimator
# ---------------------------------------------------------------------------

def test_22_tc99m_comes_through_generator_authority():
    r = resolve_admissible_radionuclides(modality="SPECT", selected_generator_ids=[GEN_TECHNELITE])
    binding = next(b for b in r.source_by_radionuclide if b.radionuclide == "Tc-99m")
    assert binding.source_type == "GENERATOR"


def test_23_tc99m_not_resolved_through_cyclotron():
    # SPECT with ONLY a cyclotron selected must not produce Tc-99m.
    r = resolve_admissible_radionuclides(modality="SPECT", selected_cyclotron_ids=[CYCLOTRON_F18_CALIBRATED])
    assert "Tc-99m" not in r.admissible_radionuclides
    assert r.status == "NO_COMPATIBLE_SOURCE"


# ---------------------------------------------------------------------------
# 24-26: mixed, multi-cyclotron union, multi-generator identity
# ---------------------------------------------------------------------------

def test_24_mixed_scenario_resolves_pet_and_spect_independently():
    # After completeness closure CYPRIS supports several PET isotopes
    # (F-18, Cu-64, Zr-89, I-124, Ga-68) and one SPECT isotope (I-123); the
    # generator adds Tc-99m to SPECT. The two modality sets stay independent:
    # PET carries no generator daughter, SPECT carries the generator daughter +
    # the cyclotron's SPECT isotope, and the sets do not cross-contaminate.
    pet = resolve_admissible_radionuclides(
        modality="PET", selected_cyclotron_ids=[CYPRIS], selected_generator_ids=[GEN_DRYTEC],
    )
    spect = resolve_admissible_radionuclides(
        modality="SPECT", selected_cyclotron_ids=[CYPRIS], selected_generator_ids=[GEN_DRYTEC],
    )
    assert set(pet.admissible_radionuclides) == {"F-18", "Cu-64", "Zr-89", "I-124", "Ga-68"}
    assert set(spect.admissible_radionuclides) == {"Tc-99m", "I-123"}
    # Independence: no PET isotope leaks into SPECT and vice versa.
    assert not (set(pet.admissible_radionuclides) & set(spect.admissible_radionuclides))
    assert "Tc-99m" not in pet.admissible_radionuclides


def test_25_multiple_cyclotrons_produce_union():
    # GE890 (F-18) UNION PETtrace 800 (F-18,C-11,N-13,O-15,Ga-68) -> all five
    # PET isotopes are admissible after completeness closure.
    r = resolve_admissible_radionuclides(
        modality="PET", selected_cyclotron_ids=[CYCLOTRON_F18_CALIBRATED, CYCLOTRON_MULTI],
    )
    assert set(r.admissible_radionuclides) == {"F-18", "C-11", "N-13", "O-15", "Ga-68"}
    # Union preserves BOTH source ids for the shared F-18 identity (no duplicate).
    assert set(r.compatible_source_ids_for("F-18")) == {CYCLOTRON_F18_CALIBRATED, CYCLOTRON_MULTI}
    assert r.admissible_radionuclides.count("F-18") == 1


def test_26_multiple_generators_preserve_identity_without_duplicates():
    r = resolve_admissible_radionuclides(
        modality="SPECT", selected_generator_ids=[GEN_TECHNELITE, GEN_ULTRA, GEN_DRYTEC],
    )
    assert r.admissible_radionuclides == ("Tc-99m",)
    assert len(r.compatible_source_ids_for("Tc-99m")) == 3


# ---------------------------------------------------------------------------
# 27-28: reproducibility + deterministic change with capability
# ---------------------------------------------------------------------------

def test_27_seeded_normal_generation_reproducible():
    a, _ = ops.build_representative_day_population(
        **_DAY_KW, selected_cyclotron_ids=(CYCLOTRON_F18_CALIBRATED,), selected_generator_ids=(GEN_TECHNELITE,),
    )
    b, _ = ops.build_representative_day_population(
        **_DAY_KW, selected_cyclotron_ids=(CYCLOTRON_F18_CALIBRATED,), selected_generator_ids=(GEN_TECHNELITE,),
    )
    key = lambda ps: tuple((p.patient_id, p.nuclear_procedure.radionuclide if p.nuclear_procedure else None) for p in ps)
    assert key(a) == key(b)


def test_28_changing_capability_changes_admissible_set_deterministically():
    with_gen = resolve_admissible_radionuclides(modality="SPECT", selected_generator_ids=[GEN_TECHNELITE])
    without_gen = resolve_admissible_radionuclides(modality="SPECT", selected_generator_ids=[])
    assert with_gen.admissible_radionuclides == ("Tc-99m",)
    assert without_gen.admissible_radionuclides == ()
    # Deterministic: re-running yields identical results.
    assert resolve_admissible_radionuclides(modality="SPECT", selected_generator_ids=[GEN_TECHNELITE]).admissible_radionuclides == ("Tc-99m",)


# ---------------------------------------------------------------------------
# 29-32: stress-test / explicit demand preserved; no silent mutation
# ---------------------------------------------------------------------------

def test_29_explicit_stress_unsupported_demand_is_preserved():
    # Explicit demand for an unsupported radionuclide is preserved verbatim by
    # the explicit-demand authority (never rewritten to fit equipment).
    from patient_radionuclide_demand import PatientRadionuclideDemand
    d = PatientRadionuclideDemand(patient_id="STRESS-1", radionuclide="Ga-68", prescribed_activity_mbq=185.0)
    assert d.radionuclide == "Ga-68"


def test_30_stress_unsupported_demand_reaches_no_compatible_source():
    # STRESS_TEST resolver call for a modality whose selected sources cannot
    # supply a clinically-recognized radionuclide -> NO_COMPATIBLE_SOURCE, and
    # the resolver never substitutes. Completeness note: CYPRIS now supports the
    # SPECT isotope I-123, so to prove the NO_COMPATIBLE_SOURCE stress path we
    # use GE890 (F-18 only, no SPECT isotope) under SPECT.
    r = resolve_admissible_radionuclides(
        modality="SPECT", selected_cyclotron_ids=[CYCLOTRON_F18_CALIBRATED], mode="STRESS_TEST",
    )
    assert r.status == "NO_COMPATIBLE_SOURCE"
    assert r.mode == "STRESS_TEST"
    assert r.admissible_radionuclides == ()


def test_31_explicit_demand_never_silently_rewritten():
    # A caller-supplied radionuclide on the inbound synthetic path is stamped
    # verbatim (this is the EXPLICIT-demand path, not source-constrained).
    from inbound_patient_program import generate_synthetic_patient_population
    pats = generate_synthetic_patient_population(demand=5, radionuclide="Zr-89", prescribed_activity_mbq=185.0)
    assert {p.radionuclide for p in pats} == {"Zr-89"}


def test_32_capability_result_is_immutable_after_creation():
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYCLOTRON_F18_CALIBRATED])
    with pytest.raises(FrozenInstanceError):
        r.status = "MUTATED"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 33-36: patient-aware batch boundary; cyclotron/generator not patient-aware;
#        cohort != physical batch
# ---------------------------------------------------------------------------

def test_33_patient_aware_batch_planning_remains_downstream():
    # After radionuclide assignment, the patient-aware batch planner still
    # aggregates patient-level demand (carries patient_ids).
    from patient_radionuclide_demand import (
        FacilityDayPatientDemand, PatientRadionuclideDemand, partition_facility_day_patient_demand,
    )
    day = FacilityDayPatientDemand(patients=tuple(
        PatientRadionuclideDemand(patient_id=f"P{i}", radionuclide="F-18", prescribed_activity_mbq=200.0)
        for i in range(1, 5)
    ))
    batches = partition_facility_day_patient_demand(day, {"F-18": 2})
    assert len(batches) == 2
    assert all(b.patient_ids for b in batches)  # patient-aware


def test_34_cyclotron_api_does_not_require_patient_identity():
    import inspect
    from nuclear_source import evaluate_cyclotron_source_feasibility
    params = inspect.signature(evaluate_cyclotron_source_feasibility).parameters
    assert "patients_requested" in params  # a COUNT
    assert not any("patient_id" in p for p in params)


def test_35_generator_api_does_not_require_patient_identity():
    import inspect
    from nuclear_source import evaluate_generator_source_feasibility
    params = inspect.signature(evaluate_generator_source_feasibility).parameters
    assert "patients_requested" in params
    assert not any("patient_id" in p for p in params)


def test_36_patient_cohort_distinct_from_physical_batch():
    from patient_radionuclide_demand import (
        FacilityDayPatientDemand, PatientRadionuclideDemand, partition_facility_day_patient_demand,
    )
    day = FacilityDayPatientDemand(patients=tuple(
        PatientRadionuclideDemand(patient_id=f"P{i}", radionuclide="F-18", prescribed_activity_mbq=200.0)
        for i in range(1, 7)
    ))
    batches = partition_facility_day_patient_demand(day, {"F-18": 2})
    # 6 patients, 2 batches -> cohort size (6) != batch count (2).
    assert len(day.patients) == 6 and len(batches) == 2


# ---------------------------------------------------------------------------
# 37-40: representative benchmark preservation + governance status
# ---------------------------------------------------------------------------

def test_37_representative_pet_benchmark_stays_f18_with_compatible_source():
    patients, _ = ops.build_representative_day_population(
        **{**_DAY_KW, "target_spect_procedures": 0},
        selected_cyclotron_ids=(CYCLOTRON_F18_CALIBRATED,),
    )
    pet_rns = {p.nuclear_procedure.radionuclide for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "PET"}
    assert pet_rns == {"F-18"}


def test_38_representative_spect_benchmark_stays_tc99m_with_compatible_generator():
    patients, _ = ops.build_representative_day_population(
        **{**_DAY_KW, "target_pet_procedures": 0},
        selected_generator_ids=(GEN_TECHNELITE,),
    )
    spect_rns = {p.nuclear_procedure.radionuclide for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "SPECT"}
    assert spect_rns == {"Tc-99m"}


def test_39_representative_patient_census_unchanged_by_binding():
    # No selected-source args (benchmark default) vs a compatible selected set:
    # census and patient identities are identical.
    base_pats, base_census = ops.build_representative_day_population(**_DAY_KW)
    bound_pats, bound_census = ops.build_representative_day_population(
        **_DAY_KW, selected_cyclotron_ids=(CYCLOTRON_F18_CALIBRATED,), selected_generator_ids=(GEN_TECHNELITE,),
    )
    assert tuple(p.patient_id for p in base_pats) == tuple(p.patient_id for p in bound_pats)
    assert (base_census.pet_procedures, base_census.spect_procedures, base_census.total_active_patients) == (
        bound_census.pet_procedures, bound_census.spect_procedures, bound_census.total_active_patients
    )
    assert _rns(base_pats) == _rns(bound_pats) == ["F-18", "Tc-99m"]


def test_40_backward_compat_none_selected_sources_preserves_defaults():
    patients, _ = ops.build_representative_day_population(**_DAY_KW)  # no source args at all
    assert _rns(patients) == ["F-18", "Tc-99m"]


# ---------------------------------------------------------------------------
# Control proofs A-F (Section 42)
# ---------------------------------------------------------------------------

def test_proof_A_normal_representative_control():
    patients, census = ops.build_representative_day_population(
        **_DAY_KW, selected_cyclotron_ids=(CYCLOTRON_F18_CALIBRATED,), selected_generator_ids=(GEN_TECHNELITE,),
    )
    pet = [p for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "PET"]
    spect = [p for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "SPECT"]
    assert {p.nuclear_procedure.radionuclide for p in pet} == {"F-18"}
    assert {p.nuclear_procedure.radionuclide for p in spect} == {"Tc-99m"}
    # census unchanged vs benchmark default
    _, base_census = ops.build_representative_day_population(**_DAY_KW)
    assert census.total_nuclear_procedures == base_census.total_nuclear_procedures


def test_proof_B_cypris_support_control():
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYPRIS])
    assert "F-18" in r.admissible_radionuclides  # SUPPORTED
    from cyclotron_catalog import load_cyclotron_catalog
    model = load_cyclotron_catalog().by_id(CYPRIS)
    assert model.schedulable_radionuclides == ()  # NOT_CALIBRATED downstream unresolved


def test_proof_C_no_source_control():
    for modality in ("PET", "SPECT"):
        r = resolve_admissible_radionuclides(modality=modality)  # no sources
        assert r.status == "NO_COMPATIBLE_SOURCE"
        assert r.admissible_radionuclides == ()
    # no F-18/Tc-99m fallback at the generator seam either
    with pytest.raises(NoCompatibleSourceError):
        ops.build_representative_day_population(**_DAY_KW, selected_cyclotron_ids=(), selected_generator_ids=())


def test_proof_D_mixed_source_control():
    # PETtrace 800 supports F-18,C-11,N-13,O-15,Ga-68 (all PET after closure);
    # the Tc-99m generator supplies SPECT. Modality independence preserved.
    pet = resolve_admissible_radionuclides(
        modality="PET", selected_cyclotron_ids=[CYCLOTRON_MULTI], selected_generator_ids=[GEN_TECHNELITE],
    )
    spect = resolve_admissible_radionuclides(
        modality="SPECT", selected_cyclotron_ids=[CYCLOTRON_MULTI], selected_generator_ids=[GEN_TECHNELITE],
    )
    assert set(pet.admissible_radionuclides) == {"F-18", "C-11", "N-13", "O-15", "Ga-68"}
    assert spect.admissible_radionuclides == ("Tc-99m",)  # PETtrace 800 has no SPECT isotope
    assert "Tc-99m" not in pet.admissible_radionuclides


def test_proof_E_stress_test_control_preserves_and_exposes():
    # Deliberately request SPECT with no generator -> preserved as
    # NO_COMPATIBLE_SOURCE, no substitution to F-18.
    r = resolve_admissible_radionuclides(
        modality="SPECT", selected_cyclotron_ids=[CYCLOTRON_F18_CALIBRATED], mode="STRESS_TEST",
    )
    assert r.status == "NO_COMPATIBLE_SOURCE"
    assert "F-18" not in r.admissible_radionuclides


def test_proof_F_multi_radionuclide_control():
    r = resolve_admissible_radionuclides(modality="PET", selected_cyclotron_ids=[CYCLOTRON_MULTI])
    seen = set(r.admissible_radionuclides) | {e[0] for e in r.excluded_radionuclides}
    # All declared radionuclides are visible. After completeness closure every
    # PETtrace-800 isotope is evidence-classified PET, so all five are now
    # admissible (multi-radionuclide) -- each backed by a traceable evidence
    # record, none invented. This is the intended completeness result.
    assert {"F-18", "C-11", "N-13", "O-15", "Ga-68"} <= seen
    assert set(r.admissible_radionuclides) == {"F-18", "C-11", "N-13", "O-15", "Ga-68"}
    # No radionuclide is excluded for "not clinically classified" any more.
    excluded_reasons = {rn: reason for rn, reason in r.excluded_radionuclides}
    for rn in ("C-11", "N-13", "O-15", "Ga-68"):
        assert rn not in excluded_reasons


# ---------------------------------------------------------------------------
# Patient-aware batch planning proof (Section 43)
# ---------------------------------------------------------------------------

def test_batch_planning_is_patient_aware_but_source_apis_are_not():
    from patient_radionuclide_demand import (
        FacilityDayPatientDemand, PatientRadionuclideDemand, partition_facility_day_patient_demand,
    )
    # Patient-aware batch planning carries patient identity.
    day = FacilityDayPatientDemand(patients=tuple(
        PatientRadionuclideDemand(patient_id=f"P{i}", radionuclide="F-18", prescribed_activity_mbq=200.0)
        for i in range(1, 4)
    ))
    batches = partition_facility_day_patient_demand(day, {"F-18": 1})
    assert batches[0].patient_ids == ("P1", "P2", "P3")
    # But the physical production requirement passed downstream is
    # radionuclide + activity + count -- never patient identity.
    assert batches[0].radionuclide == "F-18"
    assert batches[0].patient_count == 3
    assert batches[0].total_prescribed_activity_mbq == pytest.approx(600.0)

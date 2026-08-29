"""Focused tests for the Cyclotron Production Estimation Authority (OG-CYC-1).

Covers the 30 invariants of the build's Section 28 plus the physical control
proofs A-F of Section 47, all against the REAL repository catalog authorities
(no fabricated fixtures for the numerical controls).

Calibrated ground-truth facts used (from `cyclotron_equipment_catalog.json`):
  - GE PETtrace 890 + F-18 : 160 uA / 120 min -> 648000 MBq (manufacturer_calibrated)
  - IBA Cyclone KEY  + F-18 : 100 uA / 120 min -> 111000 MBq (manufacturer_calibrated)
  - SUMITOMO CYPRIS MP-30 + F-18 : SUPPORTED, no records/cycles -> not_calibrated
  - Tc-99m : generator daughter (Mo-99 -> Tc-99m), outside cyclotron estimation
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


# ---------------------------------------------------------------------------
# 1. calibrated record takes precedence over estimate
# ---------------------------------------------------------------------------
def test_01_calibrated_record_takes_precedence_over_estimate():
    r = cpea.estimate_cyclotron_production(GE890, "F-18")
    assert r.production_basis == "MANUFACTURER_CALIBRATED"
    assert r.estimated_or_calibrated_eob_mbq == 648000.0
    # Even queried at the calibrated irradiation time, calibrated wins (not modeled).
    r_at = cpea.estimate_cyclotron_production(GE890, "F-18", irradiation_minutes=120.0)
    assert r_at.production_basis == "MANUFACTURER_CALIBRATED"
    assert r_at.estimated_or_calibrated_eob_mbq == 648000.0


# ---------------------------------------------------------------------------
# 2. SITE_CALIBRATED precedence if physically represented (precedence ordering)
# ---------------------------------------------------------------------------
def test_02_site_calibrated_precedence_ordering():
    # No cyclotron production performance record is currently tagged
    # site_calibrated in the repo, so we lock the PRECEDENCE ORDER instead
    # (SITE_CALIBRATED outranks MANUFACTURER_CALIBRATED and MODELED_ESTIMATE).
    assert cpea.stronger_basis("SITE_CALIBRATED", "MANUFACTURER_CALIBRATED") == "SITE_CALIBRATED"
    assert cpea.stronger_basis("SITE_CALIBRATED", "MODELED_ESTIMATE") == "SITE_CALIBRATED"


# ---------------------------------------------------------------------------
# 3. manufacturer-calibrated F-18 returns calibrated basis
# ---------------------------------------------------------------------------
def test_03_manufacturer_calibrated_f18_returns_calibrated_basis():
    r = cpea.estimate_cyclotron_production(IBA_KEY, "F-18")
    assert r.production_basis == "MANUFACTURER_CALIBRATED"
    assert r.calibration_status == "manufacturer_calibrated"
    assert r.estimated_or_calibrated_eob_mbq == 111000.0


# ---------------------------------------------------------------------------
# 4. CYPRIS MP-30 + F-18 remains manufacturer/site NOT_CALIBRATED
# ---------------------------------------------------------------------------
def test_04_cypris_mp30_f18_remains_not_calibrated():
    r = cpea.estimate_cyclotron_production(CYPRIS_MP30, "F-18")
    assert r.supported is True
    assert r.calibration_status == "not_calibrated"


# ---------------------------------------------------------------------------
# 5. CYPRIS MP-30 never borrows PETtrace 890 capacity
# ---------------------------------------------------------------------------
def test_05_cypris_mp30_never_borrows_pettrace_capacity():
    r = cpea.estimate_cyclotron_production(CYPRIS_MP30, "F-18")
    # No numerical value at all -> cannot have borrowed 648000 or any GE figure.
    assert r.estimated_or_calibrated_eob_mbq is None
    assert r.estimation_status == "NOT_AVAILABLE"
    assert r.production_basis == "NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# 6. modeled estimate is explicitly labeled MODELED_ESTIMATE
# ---------------------------------------------------------------------------
def test_06_modeled_estimate_is_labeled():
    r = cpea.estimate_cyclotron_production(GE890, "F-18", irradiation_minutes=60.0)
    assert r.production_basis == "MODELED_ESTIMATE"
    assert r.evidence_class == "MODELED_ESTIMATE"
    assert r.estimation_status == "AVAILABLE"
    assert r.estimated_or_calibrated_eob_mbq is not None
    assert r.estimated_or_calibrated_eob_mbq < 648000.0  # shorter irradiation -> less activity


# ---------------------------------------------------------------------------
# 7. modeled estimate does not change calibration status
# ---------------------------------------------------------------------------
def test_07_modeled_estimate_does_not_change_calibration_status():
    r = cpea.estimate_cyclotron_production(GE890, "F-18", irradiation_minutes=60.0)
    assert r.production_basis == "MODELED_ESTIMATE"
    # The manufacturer calibration evidence status is unchanged.
    assert r.calibration_status == "manufacturer_calibrated"


# ---------------------------------------------------------------------------
# 8. no-evidence pair returns NOT_AVAILABLE rather than a fabricated number
# ---------------------------------------------------------------------------
def test_08_no_evidence_pair_returns_not_available():
    r = cpea.estimate_cyclotron_production(GE800, "C-11")
    assert r.supported is True
    assert r.estimation_status == "NOT_AVAILABLE"
    assert r.estimated_or_calibrated_eob_mbq is None


# ---------------------------------------------------------------------------
# 9. estimate is radionuclide-specific
# ---------------------------------------------------------------------------
def test_09_estimate_is_radionuclide_specific():
    f18 = cpea.estimate_cyclotron_production(GE890, "F-18")
    assert f18.radionuclide == "F-18"
    # A different radionuclide on the same model resolves independently.
    c11 = cpea.estimate_cyclotron_production(GE890, "C-11")
    assert c11.radionuclide == "C-11"
    assert c11.production_basis != "MANUFACTURER_CALIBRATED"


# ---------------------------------------------------------------------------
# 10-12. F-18 estimate cannot qualify C-11 / N-13 / Ga-68
# ---------------------------------------------------------------------------
def test_10_f18_estimate_cannot_qualify_c11():
    # GE890 supports only F-18; C-11 has no compatible source on this model.
    assert cpea.estimate_cyclotron_production(GE890, "C-11").estimation_status == "NO_COMPATIBLE_SOURCE"


def test_11_f18_estimate_cannot_qualify_n13():
    assert cpea.estimate_cyclotron_production(GE890, "N-13").estimation_status == "NO_COMPATIBLE_SOURCE"


def test_12_f18_estimate_cannot_qualify_ga68():
    # Even on a model that DOES support both F-18 and Ga-68 (GE800), an F-18
    # anchor never produces a Ga-68 number.
    ga = cpea.estimate_cyclotron_production(GE800, "Ga-68")
    assert ga.estimated_or_calibrated_eob_mbq is None
    assert ga.estimation_status == "NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# 13. required EOB accepted as an engineering requirement without patient ID
# ---------------------------------------------------------------------------
def test_13_required_eob_accepted_without_patient_id():
    batch = cpea.estimate_required_physical_cycles(GE890, "F-18", 1_000_000.0)
    assert batch is not None
    assert batch.required_eob_activity_mbq == 1_000_000.0


# ---------------------------------------------------------------------------
# 14. estimator result contains provenance
# ---------------------------------------------------------------------------
def test_14_result_contains_provenance():
    r = cpea.estimate_cyclotron_production(GE890, "F-18")
    assert isinstance(r.provenance, str) and r.provenance
    assert r.raw_evidence_reference is not None


# ---------------------------------------------------------------------------
# 15. estimator result contains evidence class
# ---------------------------------------------------------------------------
def test_15_result_contains_evidence_class():
    r = cpea.estimate_cyclotron_production(GE890, "F-18")
    assert r.evidence_class in {
        "SITE_CALIBRATED", "MANUFACTURER_CALIBRATED", "MODELED_ESTIMATE",
        "CONTROLLED_ASSUMPTION", "NOT_AVAILABLE",
    }
    assert r.evidence_class == r.production_basis


# ---------------------------------------------------------------------------
# 16. normalized activity uses canonical units (MBq)
# ---------------------------------------------------------------------------
def test_16_normalized_activity_uses_mbq():
    r = cpea.estimate_cyclotron_production(GE890, "F-18")
    # 648 GBq normalized to 648000 MBq by the Build 3B normalization authority.
    assert r.estimated_or_calibrated_eob_mbq == 648000.0


# ---------------------------------------------------------------------------
# 17. raw evidence remains traceable where present
# ---------------------------------------------------------------------------
def test_17_raw_evidence_traceable():
    r = cpea.estimate_cyclotron_production(GE890, "F-18")
    assert r.raw_evidence_reference is not None
    assert "648000" in r.raw_evidence_reference or "648" in r.raw_evidence_reference


# ---------------------------------------------------------------------------
# 18. physical batch/cycle count is distinct from patient cohort count
# ---------------------------------------------------------------------------
def test_18_physical_cycle_distinct_from_patient_cohort():
    # One 648000 MBq cycle can cover a required EOB far larger than "1 patient".
    batch = cpea.estimate_required_physical_cycles(GE890, "F-18", 500000.0)
    assert batch is not None
    assert batch.required_cycles == 1  # not derived from any patient count
    # The estimator API has no patient concept at all.
    assert not hasattr(batch, "patient_id")


# ---------------------------------------------------------------------------
# 19. increasing required EOB cannot reduce required physical cycles
# ---------------------------------------------------------------------------
def test_19_increasing_required_eob_cannot_reduce_cycles():
    reqs = [100000.0, 648000.0, 648001.0, 1_296_000.0, 5_000_000.0]
    cycles = [cpea.estimate_required_physical_cycles(GE890, "F-18", q).required_cycles for q in reqs]
    assert all(cycles[i] <= cycles[i + 1] for i in range(len(cycles) - 1))
    assert cycles[0] == 1 and cycles[2] == 2


# ---------------------------------------------------------------------------
# 20. zero/invalid required EOB is handled honestly
# ---------------------------------------------------------------------------
def test_20_zero_or_invalid_required_eob_handled():
    with pytest.raises(ValueError):
        cpea.estimate_required_physical_cycles(GE890, "F-18", 0.0)
    with pytest.raises(ValueError):
        cpea.estimate_required_physical_cycles(GE890, "F-18", -5.0)


# ---------------------------------------------------------------------------
# 21. irradiation duration handling follows the chosen physical model
# ---------------------------------------------------------------------------
def test_21_irradiation_duration_follows_saturation_model():
    # A_EOB = K*I*(1 - exp(-lambda*t)); increasing t increases activity monotonically.
    e60 = cpea.estimate_cyclotron_production(GE890, "F-18", irradiation_minutes=60.0)
    e120 = cpea.estimate_cyclotron_production(GE890, "F-18", irradiation_minutes=120.0)
    e240 = cpea.estimate_cyclotron_production(GE890, "F-18", irradiation_minutes=240.0)
    assert e60.estimated_or_calibrated_eob_mbq < e120.estimated_or_calibrated_eob_mbq
    assert e120.estimated_or_calibrated_eob_mbq < e240.estimated_or_calibrated_eob_mbq
    # The t==t_cal point equals the calibrated anchor exactly.
    assert e120.estimated_or_calibrated_eob_mbq == 648000.0
    with pytest.raises(ValueError):
        cpea.estimate_cyclotron_production(GE890, "F-18", irradiation_minutes=-10.0)


# ---------------------------------------------------------------------------
# 22. unsupported radionuclide returns no compatible production authority
# ---------------------------------------------------------------------------
def test_22_unsupported_radionuclide_no_compatible_source():
    # Cu-64 is a cyclotron-only radionuclide (no generator pathway) that BEST_14P
    # (F-18 only) does not support -> NO_COMPATIBLE_SOURCE. (Ga-68 is no longer a
    # valid example here: after the Clinical Radionuclide Completeness closure it
    # has a Ge-68/Ga-68 GENERATOR pathway, so an unsupported cyclotron classifies
    # it OUT_OF_CYCLOTRON_SCOPE instead -- see test_22b.)
    r = cpea.estimate_cyclotron_production(BEST_14P, "Cu-64")
    assert r.supported is False
    assert r.estimation_status == "NO_COMPATIBLE_SOURCE"


def test_22b_ga68_generator_daughter_out_of_cyclotron_scope():
    # OG-GEN-1 closure ripple: Ga-68 now has a Ge-68/Ga-68 generator, so a
    # cyclotron that does not support it treats it as OUT_OF_CYCLOTRON_SCOPE
    # (like Tc-99m), never applying the cyclotron saturation equation.
    r = cpea.estimate_cyclotron_production(BEST_14P, "Ga-68")
    assert r.supported is False
    assert r.estimation_status == "OUT_OF_CYCLOTRON_SCOPE"
    import generator_catalog as gc
    daughters = {m.daughter_radionuclide for m in gc.load_generator_catalog().models}
    assert "Ga-68" in daughters


# ---------------------------------------------------------------------------
# 23. Tc-99m remains outside cyclotron estimation
# ---------------------------------------------------------------------------
def test_23_tc99m_outside_cyclotron_estimation():
    r = cpea.estimate_cyclotron_production(GE890, "Tc-99m")
    assert r.estimation_status == "OUT_OF_CYCLOTRON_SCOPE"
    assert r.estimated_or_calibrated_eob_mbq is None
    # And the batch/cycle path yields no cyclotron cycles for Tc-99m.
    assert cpea.estimate_required_physical_cycles(GE890, "Tc-99m", 500000.0) is None


# ---------------------------------------------------------------------------
# 24. Build 3B calibrated capacity behavior preserved
# ---------------------------------------------------------------------------
def test_24_build3b_calibrated_capacity_behavior_preserved():
    # The estimator reads the SAME calibrated record Build 3B exposes; the
    # catalog production_calibration_status is unchanged.
    model = cc.load_cyclotron_catalog().by_id(GE890)
    assert model.production_calibration_status == "manufacturer_calibrated"
    r = cpea.estimate_cyclotron_production(GE890, "F-18")
    assert r.estimated_or_calibrated_eob_mbq == 648000.0


# ---------------------------------------------------------------------------
# 25. Part 3D CYPRIS control preserved (through the wo4a seam)
# ---------------------------------------------------------------------------
def test_25_part3d_cypris_control_preserved():
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
    gate = wo._resolve_radionuclide_production_gate(
        "F-18", fleet, 500000.0, installed_cyclotron_model_ids=(CYPRIS_MP30,),
    )
    assert gate.status == "PRODUCTION_NOT_CALIBRATED"
    assert "CYPRIS MP-30" in gate.source_identity
    assert gate.simulation_production_basis == "NOT_AVAILABLE"  # no borrow, no estimate
    assert gate.installed_eob_capacity_mbq_per_day is None


# ---------------------------------------------------------------------------
# 26. patient identity is not required by estimator API
# ---------------------------------------------------------------------------
def test_26_patient_identity_not_required():
    import inspect
    for fn in (cpea.estimate_cyclotron_production, cpea.estimate_required_physical_cycles,
               cpea.resolve_simulation_production_basis):
        params = set(inspect.signature(fn).parameters)
        assert not (params & {"patient", "patient_id", "patient_name", "room", "scanner"})


# ---------------------------------------------------------------------------
# 27. no legacy 10% production blocks are used
# ---------------------------------------------------------------------------
def test_27_no_legacy_10_percent_production_blocks():
    src = open("cyclotron_production_estimation_authority.py", encoding="utf-8").read()
    assert "production_block" not in src
    assert "0.10" not in src and "* 0.1" not in src


# ---------------------------------------------------------------------------
# 28. no current_usable_doses_per_day fallback is used
# ---------------------------------------------------------------------------
def test_28_no_usable_doses_fallback():
    src = open("cyclotron_production_estimation_authority.py", encoding="utf-8").read()
    assert "usable_doses" not in src
    assert "doses_per_day" not in src


# ---------------------------------------------------------------------------
# 29. modeled estimate does not create patient demand
# ---------------------------------------------------------------------------
def test_29_modeled_estimate_does_not_create_patient_demand():
    src = open("cyclotron_production_estimation_authority.py", encoding="utf-8").read()
    # The module never imports a patient/demand generator or scenario builder.
    for forbidden in ("oncology_pet_spect_scenario", "inbound_patient_program",
                      "build_representative_day_population", "PatientRadionuclideDemand"):
        assert forbidden not in src


# ---------------------------------------------------------------------------
# 30. excess modeled production does not create revenue
# ---------------------------------------------------------------------------
def test_30_excess_modeled_production_does_not_create_revenue():
    # The estimator exposes no revenue field on any result type, and never
    # imports an economics/revenue authority (production is not monetized here).
    # (The module docstring mentions "revenue" only to forbid deriving
    # production FROM revenue, so we assert on the code contract, not prose.)
    for obj in (
        cpea.estimate_cyclotron_production(GE890, "F-18"),
        cpea.estimate_required_physical_cycles(GE890, "F-18", 1000.0),
    ):
        assert not any("revenue" in f.lower() for f in vars(obj).keys())
    src = open("cyclotron_production_estimation_authority.py", encoding="utf-8").read()
    for forbidden in ("import economics", "patient_economics", "whole_oncology_revenue",
                      "AUDITED_NUCLEAR_SCAN_REVENUE"):
        assert forbidden not in src
    # Headroom (large estimate vs small requirement) yields 1 cycle, no revenue object.
    batch = cpea.estimate_required_physical_cycles(GE890, "F-18", 1000.0)
    assert batch.required_cycles == 1
    assert not hasattr(batch, "revenue")


# ===========================================================================
# CONTROL PROOFS (Section 47)
# ===========================================================================

def test_proof_a_calibrated_control():
    r = cpea.estimate_cyclotron_production(GE890, "F-18")
    assert r.production_basis == "MANUFACTURER_CALIBRATED"
    assert r.estimated_or_calibrated_eob_mbq == 648000.0
    assert r.is_calibrated() and not r.is_modeled()


def test_proof_b_supported_but_uncalibrated_control():
    r = cpea.estimate_cyclotron_production(CYPRIS_MP30, "F-18")
    assert r.supported is True
    assert r.calibration_status == "not_calibrated"
    assert r.estimation_status == "NOT_AVAILABLE"
    assert r.estimated_or_calibrated_eob_mbq is None  # no GE PETtrace borrowing


def test_proof_c_radionuclide_specificity():
    f18 = cpea.estimate_cyclotron_production(GE890, "F-18")
    assert f18.is_calibrated()
    # The calibrated F-18 result qualifies NO other radionuclide: none inherits
    # an EOB value. Cyclotron-only unsupported isotopes (C-11, N-13) resolve
    # NO_COMPATIBLE_SOURCE; Ga-68 (now a generator daughter) resolves
    # OUT_OF_CYCLOTRON_SCOPE. In every case no F-18 capacity is borrowed.
    for other in ("C-11", "N-13"):
        r = cpea.estimate_cyclotron_production(GE890, other)
        assert r.estimation_status == "NO_COMPATIBLE_SOURCE"
        assert r.estimated_or_calibrated_eob_mbq is None
    ga = cpea.estimate_cyclotron_production(GE890, "Ga-68")
    assert ga.estimation_status == "OUT_OF_CYCLOTRON_SCOPE"
    assert ga.estimated_or_calibrated_eob_mbq is None  # still no F-18 borrowing


def test_proof_d_no_compatible_source():
    # A cyclotron-only radionuclide (Cu-64, no generator pathway) unsupported by
    # the model resolves NO_COMPATIBLE_SOURCE.
    r = cpea.estimate_cyclotron_production(BEST_14P, "Cu-64")
    assert r.estimation_status == "NO_COMPATIBLE_SOURCE"


def test_proof_e_generator_boundary():
    r = cpea.estimate_cyclotron_production(GE890, "Tc-99m")
    assert r.estimation_status == "OUT_OF_CYCLOTRON_SCOPE"
    # Tc-99m resolves through the generator authority, not the cyclotron estimator.
    import generator_catalog as gc
    daughters = {m.daughter_radionuclide for m in gc.load_generator_catalog().models}
    assert "Tc-99m" in daughters


def test_proof_f_batch_requirement_monotonic():
    # Larger required EOB must never produce fewer physical cycles.
    small = cpea.estimate_required_physical_cycles(GE890, "F-18", 648000.0)
    large = cpea.estimate_required_physical_cycles(GE890, "F-18", 2_000_000.0)
    assert small.required_cycles <= large.required_cycles
    assert small.required_cycles == 1
    assert large.required_cycles == math.ceil(2_000_000.0 / 648000.0)


# ---------------------------------------------------------------------------
# Additional: unknown model id raises (honest, not fabricated)
# ---------------------------------------------------------------------------
def test_unknown_model_id_raises():
    with pytest.raises(KeyError):
        cpea.estimate_cyclotron_production("NO_SUCH_MODEL", "F-18")

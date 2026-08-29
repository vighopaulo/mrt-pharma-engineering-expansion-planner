"""Focused tests for Part 3E Phase 1 -- Radionuclide-Aware Architecture
Optimization (`part3e_radionuclide_aware_architecture.py`).

Coverage (50+ tests):
  - Frozen read-model invariants + validation.
  - Per-radionuclide resolution (source/activity/decay/scanner) -- each
    radionuclide against its OWN compatible source (no cross-qualification).
  - The seven controls (baseline / short-half-life / Ga-68 dual pathway /
    mixed PET / mixed PET+SPECT / unsupported equipment).
  - Multi-radionuclide scheduling honesty disclosure (TRUE_JOINT=NO,
    PHASE1_AGGREGATION=YES, JOINT_OPERATIONAL_FEASIBILITY_STATUS,
    SHARED_RESOURCE_CONFLICT_VALIDATION).
  - Phase-1 aggregation: PET vs SPECT scanner pools kept distinct; activity
    never summed across radionuclides.
  - Four-architecture bouquet consumes the canonical Part 3D-derived feasibility;
    ranking uses the existing wo4a helpers (NO MRT/Conventional bonus).
  - Export seams (patient/appointment/financial).
  - No invented prevalence (demand mix always explicit).

These tests neither modify nor rely on modifying wo4a / Part 3D.
"""

from __future__ import annotations

import warnings

import pytest

warnings.filterwarnings("ignore")

import part3e_radionuclide_aware_architecture as p3e
import whole_oncology_four_architecture_optimization as wo4a
from patient_radionuclide_demand import PatientRadionuclideDemand


# ---------------------------------------------------------------------------
# Session-scoped scenario evaluations (each bouquet run is expensive).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def baseline_result():
    return p3e.evaluate_radionuclide_aware_architectures(p3e.build_baseline_f18_tc99m_control())


@pytest.fixture(scope="module")
def short_half_life_result():
    return p3e.evaluate_radionuclide_aware_architectures(p3e.build_short_half_life_control())


@pytest.fixture(scope="module")
def ga68_cyclotron_result():
    return p3e.evaluate_radionuclide_aware_architectures(p3e.build_ga68_cyclotron_control())


@pytest.fixture(scope="module")
def ga68_generator_result():
    return p3e.evaluate_radionuclide_aware_architectures(
        p3e.build_ga68_generator_control("ECKERT_ZIEGLER_GALLIAPHARM")
    )


@pytest.fixture(scope="module")
def mixed_pet_result():
    return p3e.evaluate_radionuclide_aware_architectures(p3e.build_mixed_pet_control())


@pytest.fixture(scope="module")
def mixed_pet_spect_result():
    return p3e.evaluate_radionuclide_aware_architectures(p3e.build_mixed_pet_spect_control())


@pytest.fixture(scope="module")
def unsupported_result():
    return p3e.evaluate_radionuclide_aware_architectures(p3e.build_unsupported_equipment_control())


# ===========================================================================
# 1. FROZEN read-model invariants
# ===========================================================================


def test_01_stream_demand_is_frozen():
    s = p3e.RadionuclideStreamDemand(radionuclide="F-18", patient_count=10, activity_per_patient_mbq=370.0)
    with pytest.raises(Exception):
        s.patient_count = 5  # type: ignore[misc]


def test_02_stream_demand_rejects_negative_count():
    with pytest.raises(ValueError):
        p3e.RadionuclideStreamDemand(radionuclide="F-18", patient_count=-1, activity_per_patient_mbq=370.0)


def test_03_stream_demand_rejects_negative_activity():
    with pytest.raises(ValueError):
        p3e.RadionuclideStreamDemand(radionuclide="F-18", patient_count=1, activity_per_patient_mbq=-5.0)


def test_04_scenario_requires_at_least_one_stream():
    with pytest.raises(ValueError):
        p3e.RadionuclideDemandScenario(scenario_id="EMPTY", demand_source="PROJECT_SUPPLIED_COUNTS", streams=())


def test_05_scenario_rejects_duplicate_radionuclide_stream():
    with pytest.raises(ValueError):
        p3e.RadionuclideDemandScenario(
            scenario_id="DUP", demand_source="PROJECT_SUPPLIED_COUNTS",
            streams=(
                p3e.RadionuclideStreamDemand(radionuclide="F-18", patient_count=1, activity_per_patient_mbq=1.0),
                p3e.RadionuclideStreamDemand(radionuclide="F-18", patient_count=1, activity_per_patient_mbq=1.0),
            ),
        )


def test_06_scenario_is_frozen():
    sc = p3e.build_ga68_cyclotron_control()
    with pytest.raises(Exception):
        sc.scenario_id = "X"  # type: ignore[misc]


def test_07_scenario_radionuclides_and_totals():
    sc = p3e.build_baseline_f18_tc99m_control()
    assert set(sc.radionuclides) == {"F-18", "Tc-99m"}
    assert sc.total_patient_count == 50


def test_08_scenario_is_mixed_flag():
    assert p3e.build_baseline_f18_tc99m_control().is_mixed is True
    assert p3e.build_ga68_cyclotron_control().is_mixed is False


def test_09_single_radionuclide_scenario_not_mixed():
    sc = p3e.scenario_from_counts(scenario_id="ONE", counts_and_activity=(("F-18", 10, 370.0),))
    assert sc.is_mixed is False


def test_10_scheduling_disclosure_is_frozen(baseline_result):
    d = baseline_result.scheduling_disclosure
    with pytest.raises(Exception):
        d.true_joint_multi_radionuclide_scheduling = "YES"  # type: ignore[misc]


# ===========================================================================
# 2. Scenario construction (EXPLICIT demand only -- no invented prevalence)
# ===========================================================================


def test_11_scenario_from_counts_source_label():
    sc = p3e.scenario_from_counts(scenario_id="C", counts_and_activity=(("F-18", 5, 370.0),))
    assert sc.demand_source == "PROJECT_SUPPLIED_COUNTS"


def test_12_scenario_from_patients_preserves_streams():
    patients = [
        PatientRadionuclideDemand(patient_id="P1", radionuclide="F-18", prescribed_activity_mbq=370.0),
        PatientRadionuclideDemand(patient_id="P2", radionuclide="F-18", prescribed_activity_mbq=390.0),
        PatientRadionuclideDemand(patient_id="P3", radionuclide="Tc-99m", prescribed_activity_mbq=740.0),
    ]
    sc = p3e.scenario_from_patients(scenario_id="FROM_PT", patients=patients)
    assert sc.demand_source == "PROJECT_SUPPLIED_PATIENTS"
    assert set(sc.radionuclides) == {"F-18", "Tc-99m"}
    f18 = next(s for s in sc.streams if s.radionuclide == "F-18")
    assert f18.patient_count == 2
    assert f18.activity_per_patient_mbq == pytest.approx((370.0 + 390.0) / 2)


def test_13_scenario_from_patients_requires_patients():
    with pytest.raises(ValueError):
        p3e.scenario_from_patients(scenario_id="X", patients=[])


def test_14_no_stochastic_or_prevalence_demand_source():
    # Only explicit sources exist; there is no invented-prevalence source.
    sc = p3e.build_mixed_pet_control()
    assert sc.demand_source in ("PROJECT_SUPPLIED_PATIENTS", "PROJECT_SUPPLIED_COUNTS")


def test_15_portfolio_weighting_authority_not_modeled(baseline_result):
    # The consumed portfolio never fabricates a demand mix.
    assert baseline_result.portfolio.multi_radionuclide_weighting_authority == "NOT_MODELED"


# ===========================================================================
# 3. Per-radionuclide resolution -- each against its OWN source
# ===========================================================================


def test_16_baseline_f18_resolves_cyclotron_sufficient(baseline_result):
    f18 = baseline_result.resolution_for("F-18")
    assert f18.clinical_modality == "PET"
    assert f18.production_source_type == "CYCLOTRON"
    assert f18.production_gate_status == "PRODUCTION_SUFFICIENT"
    assert f18.status == "RESOLVED_ADMISSIBLE"


def test_17_baseline_tc99m_resolves_generator_not_calibrated(baseline_result):
    tc = baseline_result.resolution_for("Tc-99m")
    assert tc.clinical_modality == "SPECT"
    assert tc.production_source_type == "GENERATOR"
    assert tc.production_gate_status == "PRODUCTION_NOT_CALIBRATED"
    assert tc.status == "RESOLVED_WITH_UNCALIBRATED_PRODUCTION"


def test_18_f18_record_does_not_qualify_c11(short_half_life_result):
    c11 = short_half_life_result.resolution_for("C-11")
    assert c11.production_gate_status == "NO_COMPATIBLE_SOURCE"
    assert c11.status == "EXCLUDED_NO_COMPATIBLE_SOURCE"


def test_19_f18_record_does_not_qualify_n13_o15(short_half_life_result):
    for r in ("N-13", "O-15"):
        res = short_half_life_result.resolution_for(r)
        assert res.production_gate_status == "NO_COMPATIBLE_SOURCE"


def test_20_short_half_life_all_pet_modality(short_half_life_result):
    for r in ("C-11", "N-13", "O-15"):
        assert short_half_life_result.resolution_for(r).clinical_modality == "PET"


def test_21_resolution_carries_half_life(baseline_result):
    assert baseline_result.resolution_for("F-18").half_life_minutes is not None
    assert baseline_result.resolution_for("F-18").decay_status == "DECAY_AUTHORITY_PRESENT"


def test_22_total_prescribed_activity_is_per_stream(baseline_result):
    f18 = baseline_result.resolution_for("F-18")
    assert f18.total_prescribed_activity_mbq == pytest.approx(f18.patient_count * f18.activity_per_patient_mbq)


def test_23_required_scanner_count_positive_for_demand(baseline_result):
    assert baseline_result.resolution_for("F-18").required_scanner_count >= 1


def test_24_resolution_is_admissible_property(baseline_result):
    assert baseline_result.resolution_for("F-18").is_admissible is True
    assert baseline_result.resolution_for("Tc-99m").is_admissible is True


def test_25_decay_authority_missing_excludes_stream():
    # An unknown radionuclide cannot even be constructed as a validated patient,
    # but a raw stream with no half-life resolves EXCLUDED_DECAY_AUTHORITY_MISSING.
    sc = p3e.RadionuclideDemandScenario(
        scenario_id="NO_DECAY", demand_source="PROJECT_SUPPLIED_COUNTS",
        streams=(p3e.RadionuclideStreamDemand(radionuclide="ZZ-999", patient_count=1, activity_per_patient_mbq=1.0),),
    )
    res = p3e.evaluate_radionuclide_aware_architectures(sc)
    assert res.resolution_for("ZZ-999").status == "EXCLUDED_DECAY_AUTHORITY_MISSING"


# ===========================================================================
# 4. Ga-68 dual pathway (cyclotron vs generator, DISTINCT)
# ===========================================================================


def test_26_ga68_cyclotron_arm_source_type(ga68_cyclotron_result):
    ga = ga68_cyclotron_result.resolution_for("Ga-68")
    assert ga.production_source_type == "CYCLOTRON"
    assert "CYPRIS" in ga.production_source_identity


def test_27_ga68_generator_arm_source_type(ga68_generator_result):
    ga = ga68_generator_result.resolution_for("Ga-68")
    assert ga.production_source_type == "GENERATOR"
    assert ga.production_source_identity == "ECKERT_ZIEGLER_GALLIAPHARM"


def test_28_ga68_dual_pathway_distinct_source_types(ga68_cyclotron_result, ga68_generator_result):
    cyc = ga68_cyclotron_result.resolution_for("Ga-68")
    gen = ga68_generator_result.resolution_for("Ga-68")
    assert cyc.production_source_type != gen.production_source_type


def test_29_ga68_both_arms_not_calibrated_not_fabricated(ga68_cyclotron_result, ga68_generator_result):
    assert ga68_cyclotron_result.resolution_for("Ga-68").production_gate_status == "PRODUCTION_NOT_CALIBRATED"
    assert ga68_generator_result.resolution_for("Ga-68").production_gate_status == "PRODUCTION_NOT_CALIBRATED"


def test_30_ga68_arms_admissible_with_limitations(ga68_cyclotron_result, ga68_generator_result):
    assert ga68_cyclotron_result.resolution_for("Ga-68").status == "RESOLVED_WITH_UNCALIBRATED_PRODUCTION"
    assert ga68_generator_result.resolution_for("Ga-68").status == "RESOLVED_WITH_UNCALIBRATED_PRODUCTION"


def test_31_ga68_no_installed_cyclotron_falls_to_generator():
    # With no cyclotron selected, benchmark GE fleet does not support Ga-68, so
    # it resolves via the generator daughter path (never fabricated).
    sc = p3e.scenario_from_counts(scenario_id="GA_NO_CYC", counts_and_activity=(("Ga-68", 5, 185.0),))
    res = p3e.evaluate_radionuclide_aware_architectures(sc)
    assert res.resolution_for("Ga-68").production_source_type == "GENERATOR"


# ===========================================================================
# 5. Unsupported-equipment control (real identity, NOT_CALIBRATED, not fabricated)
# ===========================================================================


def test_32_unsupported_cypris_real_identity(unsupported_result):
    f18 = unsupported_result.resolution_for("F-18")
    assert f18.production_source_type == "CYCLOTRON"
    assert "CYPRIS" in f18.production_source_identity


def test_33_unsupported_cypris_not_calibrated_not_no_source(unsupported_result):
    f18 = unsupported_result.resolution_for("F-18")
    assert f18.production_gate_status == "PRODUCTION_NOT_CALIBRATED"
    assert f18.production_gate_status != "NO_COMPATIBLE_SOURCE"


def test_34_unsupported_installed_eob_never_fabricated(unsupported_result):
    # NOT_CALIBRATED means no installed EOB capacity is invented.
    f18 = unsupported_result.resolution_for("F-18")
    assert f18.status == "RESOLVED_WITH_UNCALIBRATED_PRODUCTION"


# ===========================================================================
# 6. Multi-radionuclide scheduling honesty disclosure (supplemental governor)
# ===========================================================================


def test_35_true_joint_is_always_no(baseline_result, mixed_pet_spect_result, ga68_cyclotron_result):
    for res in (baseline_result, mixed_pet_spect_result, ga68_cyclotron_result):
        assert res.scheduling_disclosure.true_joint_multi_radionuclide_scheduling == "NO"


def test_36_phase1_aggregation_is_always_yes(baseline_result, mixed_pet_spect_result):
    assert baseline_result.scheduling_disclosure.multi_radionuclide_phase1_aggregation == "YES"
    assert mixed_pet_spect_result.scheduling_disclosure.multi_radionuclide_phase1_aggregation == "YES"


def test_37_scheduling_basis_single_radionuclide(baseline_result):
    assert baseline_result.scheduling_disclosure.scheduling_basis == "SINGLE_RADIONUCLIDE_PER_STREAM_INDEPENDENT"


def test_38_single_radionuclide_scenario_validated(ga68_cyclotron_result):
    d = ga68_cyclotron_result.scheduling_disclosure
    assert d.joint_operational_feasibility_status == "SINGLE_RADIONUCLIDE_VALIDATED"
    assert d.shared_resource_conflict_validation == "NOT_APPLICABLE_SINGLE_RADIONUCLIDE"


def test_39_mixed_feasible_scenario_not_fully_validated(mixed_pet_spect_result):
    d = mixed_pet_spect_result.scheduling_disclosure
    assert d.joint_operational_feasibility_status == "NOT_FULLY_VALIDATED"
    assert d.shared_resource_conflict_validation == "NOT_VALIDATED"


def test_40_mixed_with_infeasible_stream_flagged(mixed_pet_result, short_half_life_result):
    # Both carry a NO_COMPATIBLE_SOURCE stream -> INFEASIBLE_STREAM_PRESENT.
    assert mixed_pet_result.scheduling_disclosure.joint_operational_feasibility_status == "INFEASIBLE_STREAM_PRESENT"
    assert short_half_life_result.scheduling_disclosure.joint_operational_feasibility_status == "INFEASIBLE_STREAM_PRESENT"


def test_41_disclosure_stream_count_matches(mixed_pet_spect_result):
    assert mixed_pet_spect_result.scheduling_disclosure.radionuclide_stream_count == 3


# ===========================================================================
# 7. Phase-1 aggregation (PET vs SPECT pools distinct; activity per-radionuclide)
# ===========================================================================


def test_42_pet_spect_scanner_pools_distinct(mixed_pet_spect_result):
    agg = mixed_pet_spect_result.aggregation
    assert agg.required_pet_scanner_count >= 1
    assert agg.required_spect_scanner_count >= 1
    assert agg.required_total_scanner_count == agg.required_pet_scanner_count + agg.required_spect_scanner_count


def test_43_spect_only_from_spect_streams(mixed_pet_spect_result):
    # Tc-99m is the only SPECT stream; PET streams never add to the SPECT pool.
    agg = mixed_pet_spect_result.aggregation
    tc = mixed_pet_spect_result.resolution_for("Tc-99m")
    assert agg.required_spect_scanner_count == tc.required_scanner_count


def test_44_pet_pool_sums_only_pet_streams(mixed_pet_spect_result):
    agg = mixed_pet_spect_result.aggregation
    pet_streams = [r for r in mixed_pet_spect_result.stream_resolutions if r.clinical_modality == "PET"]
    assert agg.required_pet_scanner_count == sum(r.required_scanner_count for r in pet_streams)


def test_45_activity_kept_per_radionuclide(baseline_result):
    agg = baseline_result.aggregation
    assert set(agg.prescribed_activity_by_radionuclide_mbq.keys()) == {"F-18", "Tc-99m"}
    # Never a single collapsed 'total activity' key.
    assert "TOTAL" not in agg.prescribed_activity_by_radionuclide_mbq


def test_46_admissible_and_excluded_partition(mixed_pet_result):
    agg = mixed_pet_result.aggregation
    assert "F-18" in agg.admissible_radionuclides
    assert "Ga-68" in agg.admissible_radionuclides
    excluded_ids = {r for (r, _reason) in agg.excluded_radionuclides}
    assert "C-11" in excluded_ids


def test_47_total_patient_count_aggregated(baseline_result):
    assert baseline_result.aggregation.total_patient_count == 50


def test_48_pet_spect_patient_counts_split(mixed_pet_spect_result):
    agg = mixed_pet_spect_result.aggregation
    assert agg.pet_patient_count == 24 + 6  # F-18 + Ga-68
    assert agg.spect_patient_count == 16     # Tc-99m


# ===========================================================================
# 8. Four-architecture bouquet -- Part 3D consumption + NO bonus
# ===========================================================================


def test_49_bouquet_has_all_four_architectures(baseline_result):
    archs = {r.architecture for r in baseline_result.architecture_results}
    assert archs == {"MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "MRT_DOMINANT", "HYBRID_MRT"}


def test_50_feasibility_is_derived_not_hardcoded(baseline_result):
    # Every architecture carries a DERIVED Part 3D status (never NOT_EVALUATED).
    for r in baseline_result.architecture_results:
        assert r.physical_feasibility_status != "NOT_EVALUATED"
        assert r.qualification_status != "NOT_EVALUATED"


def test_51_architecture_result_feasible_matches_status(baseline_result):
    for r in baseline_result.architecture_results:
        assert r.feasible == (r.physical_feasibility_status != "INFEASIBLE")


def test_52_mrt_dominant_uses_canonical_derived_path(baseline_result):
    # Canonical MRT_DOMINANT derives feasibility (not the hardcoded Light-MRT variant).
    mrt = baseline_result.result_for("MRT_DOMINANT")
    assert mrt.physical_feasibility_status != "NOT_EVALUATED"


def test_53_ranking_is_cost_only_no_bonus(baseline_result):
    # Ranking must equal wo4a.rank_cost_only over the same results -- no family bonus.
    wo4a_results = tuple(r.architecture_result for r in baseline_result.architecture_results)
    expected = tuple(r.architecture for r in wo4a.rank_cost_only(wo4a_results))  # type: ignore[misc]
    assert baseline_result.ranked_feasible_architectures == expected


def test_54_ranking_orders_by_lifecycle_cost(baseline_result):
    ranked = baseline_result.ranked_feasible_architectures
    costs = [baseline_result.result_for(a).lifecycle_cost for a in ranked]
    assert costs == sorted(costs)


def test_55_pareto_front_subset_of_bouquet(baseline_result):
    archs = {r.architecture for r in baseline_result.architecture_results}
    assert set(baseline_result.pareto_front_architectures).issubset(archs)


def test_56_per_radionuclide_gates_propagated(baseline_result):
    # The Part 3D per-radionuclide gates flow onto each architecture result.
    for r in baseline_result.architecture_results:
        assert isinstance(r.per_radionuclide_production_gates, tuple)


def test_57_manual_cheaper_than_mrt_dominant(baseline_result):
    manual = baseline_result.result_for("MANUAL_CONVENTIONAL").lifecycle_cost
    mrt = baseline_result.result_for("MRT_DOMINANT").lifecycle_cost
    assert manual < mrt  # no MRT bonus inflating MRT's rank


# ===========================================================================
# 9. Export seams
# ===========================================================================


def test_58_patient_export_row_per_stream(mixed_pet_spect_result):
    rows = p3e.export_patient_appointment_rows(mixed_pet_spect_result)
    assert len(rows) == len(mixed_pet_spect_result.stream_resolutions)
    assert {r.radionuclide for r in rows} == {"F-18", "Tc-99m", "Ga-68"}


def test_59_patient_export_carries_source_and_scanner(mixed_pet_spect_result):
    rows = {r.radionuclide: r for r in p3e.export_patient_appointment_rows(mixed_pet_spect_result)}
    assert rows["Tc-99m"].production_source_type == "GENERATOR"
    assert rows["F-18"].clinical_modality == "PET"
    assert rows["F-18"].required_scanner_count >= 1


def test_60_financial_export_row_per_architecture(baseline_result):
    rows = p3e.export_financial_rows(baseline_result)
    assert {r.architecture for r in rows} == {
        "MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "MRT_DOMINANT", "HYBRID_MRT",
    }


def test_61_financial_export_matches_architecture_result(baseline_result):
    rows = {r.architecture: r for r in p3e.export_financial_rows(baseline_result)}
    for pr in baseline_result.architecture_results:
        assert rows[pr.architecture].lifecycle_cost == pr.architecture_result.lifecycle_cost
        assert rows[pr.architecture].feasible == pr.feasible


def test_62_financial_export_scenario_id(baseline_result):
    for row in p3e.export_financial_rows(baseline_result):
        assert row.scenario_id == baseline_result.scenario.scenario_id


# ===========================================================================
# 10. Part 3D / framework preservation (Part 3E does not mutate wo4a)
# ===========================================================================


def test_63_wo4a_manual_still_directly_callable():
    # The framework evaluator is unchanged and still works standalone.
    baseline = wo4a.build_common_project_baseline()
    r = wo4a.evaluate_manual_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    assert r.architecture == "MANUAL_CONVENTIONAL"
    assert r.physical_feasibility_status != "NOT_EVALUATED"


def test_64_scenario_result_limitations_disclosed(baseline_result):
    joined = " ".join(baseline_result.limitations)
    assert "TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING=NO" in joined
    assert "CLASS_AND_MODALITY" in joined
    assert "no radionuclide prevalence is invented" in joined


def test_65_result_for_unknown_architecture_raises(baseline_result):
    with pytest.raises(KeyError):
        baseline_result.result_for("MANUAL_CONVENTIONAL_XYZ")  # type: ignore[arg-type]


def test_66_resolution_for_unknown_radionuclide_raises(baseline_result):
    with pytest.raises(KeyError):
        baseline_result.resolution_for("Xe-133")


def test_67_same_nuclear_patient_ids_across_architectures(baseline_result):
    # Only transport architecture differs; the nuclear patient subset is identical.
    wo4a_results = tuple(r.architecture_result for r in baseline_result.architecture_results)
    assert wo4a.same_nuclear_patient_ids_across_architectures(wo4a_results)

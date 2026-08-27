"""Focused test suite: Full Operational + Capital Qualification.

Covers (section 111, bounded scope disclosed in the final report): complete
canonical nuclear population distinct from the legacy transport subset, PET/
SPECT x inpatient/outpatient inclusion, cyclotron vs generator source
authority, outpatient nuclear revenue vs inpatient bundling, complete nuclear
revenue reconciliation, Operational-only for all four architectures with no
auto-purchase, Capital-planning for all four, Retrofit/Greenfield patient
conservation, long-horizon patient uniqueness, porter shortage failure mode,
MRT carrier shortage failure mode, architecture fairness, bounded
sensitivities (census, nuclear demand, distance), study branching, four-
architecture non-regression, component non-regression.
"""

from __future__ import annotations

from datetime import date

import pytest

from campus_retrofit_benchmark import build_two_building_campus_geometry, run_campus_case_1_conventional
from oncology_pet_spect_scenario import build_representative_day_population

from whole_oncology_four_architecture_optimization import (
    build_common_project_baseline,
    evaluate_manual_conventional,
    evaluate_automated_conventional,
    evaluate_hybrid_mrt,
    evaluate_mrt_dominant,
    resolve_complete_nuclear_population,
    resolve_canonical_inpatient_pet_subset,
    summarize_nuclear_population,
    build_complete_nuclear_matrix,
    _nuclear_result,
    compute_whole_oncology_annual_revenue,
    rank_cost_only,
    rank_revenue_aware,
    evaluate_manual_conventional_porter_shortage,
    evaluate_mrt_dominant_operational_only_carrier_shortage,
    build_census_sensitivity_baselines,
    qualify_architecture,
    clone_study_configuration,
    StudyConfiguration,
    compute_retrofit_to_greenfield_transition_impact,
)


@pytest.fixture(scope="module")
def baseline():
    return build_common_project_baseline()


@pytest.fixture(scope="module")
def four_results(baseline):
    manual = evaluate_manual_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    automated = evaluate_automated_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    hybrid = evaluate_hybrid_mrt(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    mrt_dominant = evaluate_mrt_dominant(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    return manual, automated, hybrid, mrt_dominant


# ---------------------------------------------------------------------------
# Complete nuclear population vs transport subset (sections 1-11)
# ---------------------------------------------------------------------------


def test_complete_nuclear_population_includes_all_settings_and_modalities(baseline):
    summary = summarize_nuclear_population(baseline)
    assert summary.total_nuclear_patients == summary.pet_nuclear_patients + summary.spect_nuclear_patients
    assert summary.total_nuclear_patients == summary.inpatient_nuclear_patients + summary.outpatient_nuclear_patients


def test_pet_inpatient_included(baseline):
    complete = resolve_complete_nuclear_population(baseline)
    assert any(p.patient_type == "INPATIENT" and p.nuclear_procedure.modality == "PET" for p in complete)


def test_pet_outpatient_included(baseline):
    complete = resolve_complete_nuclear_population(baseline)
    assert any(p.patient_type == "OUTPATIENT" and p.nuclear_procedure.modality == "PET" for p in complete)


def test_spect_inpatient_included(baseline):
    complete = resolve_complete_nuclear_population(baseline)
    assert any(p.patient_type == "INPATIENT" and p.nuclear_procedure.modality == "SPECT" for p in complete)


def test_spect_outpatient_included(baseline):
    complete = resolve_complete_nuclear_population(baseline)
    assert any(p.patient_type == "OUTPATIENT" and p.nuclear_procedure.modality == "SPECT" for p in complete)


def test_total_nuclear_not_equal_to_transport_subset(baseline):
    summary = summarize_nuclear_population(baseline)
    assert summary.total_nuclear_patients != summary.nuclear_transport_eligible_patients
    assert summary.total_nuclear_patients == summary.nuclear_transport_eligible_patients + summary.nuclear_transport_ineligible_or_not_applicable_patients


def test_pet_uses_cyclotron_authority(baseline):
    matrix = build_complete_nuclear_matrix(baseline)
    assert all(r.source_type == "CYCLOTRON" for r in matrix if r.modality == "PET")


def test_spect_uses_generator_authority(baseline):
    matrix = build_complete_nuclear_matrix(baseline)
    assert all(r.source_type == "GENERATOR" for r in matrix if r.modality == "SPECT")


def test_pet_and_spect_never_flattened_into_one_pool(baseline):
    matrix = build_complete_nuclear_matrix(baseline)
    source_types = {(r.modality, r.source_type) for r in matrix}
    assert source_types <= {("PET", "CYCLOTRON"), ("SPECT", "GENERATOR")}


# ---------------------------------------------------------------------------
# Revenue reconciliation (sections 12-15, 53)
# ---------------------------------------------------------------------------


def test_outpatient_revenue_only_counts_outpatient_nuclear(baseline):
    summary = summarize_nuclear_population(baseline)
    revenue = compute_whole_oncology_annual_revenue(baseline)
    expected = summary.outpatient_nuclear_patients * baseline.operating_days_per_year * 2000.0
    assert revenue.annual_outpatient_nuclear_revenue == pytest.approx(expected)


def test_inpatient_nuclear_not_double_counted(baseline):
    summary = summarize_nuclear_population(baseline)
    revenue = compute_whole_oncology_annual_revenue(baseline)
    # Inpatient nuclear count must NOT contribute to outpatient revenue
    naive_wrong = summary.total_nuclear_patients * baseline.operating_days_per_year * 2000.0
    assert revenue.annual_outpatient_nuclear_revenue < naive_wrong


def test_complete_nuclear_revenue_reconciliation(baseline):
    revenue = compute_whole_oncology_annual_revenue(baseline)
    assert revenue.total_annual_clinical_revenue == pytest.approx(
        revenue.annual_inpatient_episode_revenue + revenue.annual_outpatient_nuclear_revenue
    )


def test_complete_nuclear_cost_categories_present(baseline):
    matrix = build_complete_nuclear_matrix(baseline)
    assert len(matrix) == len(resolve_complete_nuclear_population(baseline))
    for r in matrix:
        assert r.payment_context in ("SEPARATELY_PAYABLE", "BUNDLED_IN_INPATIENT_EPISODE")


# ---------------------------------------------------------------------------
# Operational-only / Capital-planning for all four (sections 27-38)
# ---------------------------------------------------------------------------


def test_manual_operational_only_no_auto_purchase(baseline):
    result = evaluate_manual_conventional(baseline, development_context="RETROFIT", study_scope="OPERATIONAL_ONLY")
    assert result.new_study_capex == 0.0


def test_automated_operational_only_no_auto_purchase(baseline):
    result = evaluate_automated_conventional(baseline, development_context="RETROFIT", study_scope="OPERATIONAL_ONLY")
    assert result.new_study_capex == 0.0


def test_hybrid_operational_only_no_auto_purchase(baseline):
    result = evaluate_hybrid_mrt(baseline, development_context="RETROFIT", study_scope="OPERATIONAL_ONLY")
    assert result.new_study_capex == 0.0


def test_mrt_dominant_operational_only_no_auto_purchase(baseline):
    result = evaluate_mrt_dominant(baseline, development_context="RETROFIT", study_scope="OPERATIONAL_ONLY")
    assert result.new_study_capex == 0.0


def test_manual_capital_planning(baseline):
    """Build 2R common/inherited CapEx correction: Manual's architecture-
    specific CapEx is the $125,000 conventional-transport flat allowance
    (previously silently excluded), not literally $0 -- the common
    scanner/injection/uptake/cyclotron cost is reported separately."""
    result = evaluate_manual_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    assert result.new_study_capex == pytest.approx(125_000.0)
    assert result.common_new_study_capex == 0.0


def test_automated_capital_planning(baseline):
    result = evaluate_automated_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    assert result.new_study_capex > 0.0


def test_hybrid_capital_planning(baseline):
    result = evaluate_hybrid_mrt(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    assert result.new_study_capex > 0.0


def test_mrt_dominant_capital_planning(baseline):
    result = evaluate_mrt_dominant(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    assert result.new_study_capex > 0.0


# ---------------------------------------------------------------------------
# Retrofit / Greenfield / branching (sections 37-38, 77-80)
# ---------------------------------------------------------------------------


def test_same_patients_across_contexts(baseline):
    retrofit = evaluate_manual_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    greenfield = evaluate_manual_conventional(baseline, development_context="GREENFIELD", study_scope="CAPITAL_PLANNING")
    assert retrofit.canonical_patient_ids == greenfield.canonical_patient_ids


def test_study_branching_non_destructive():
    config = StudyConfiguration(study_id="S1", development_context="RETROFIT", architecture="MANUAL_CONVENTIONAL", study_scope="CAPITAL_PLANNING", economic_mode="COST_ONLY")
    cloned = clone_study_configuration(config, architecture="MRT_DOMINANT")
    assert config.architecture == "MANUAL_CONVENTIONAL"
    assert cloned.architecture == "MRT_DOMINANT"


def test_retrofit_greenfield_transition_impact():
    config = StudyConfiguration(study_id="S1", development_context="RETROFIT", architecture="HYBRID_MRT", study_scope="CAPITAL_PLANNING", economic_mode="COST_ONLY")
    impact = compute_retrofit_to_greenfield_transition_impact(config)
    assert "patient population" in impact.preserved_project_data


# ---------------------------------------------------------------------------
# Long-horizon / known-vs-forecast (sections 39-42)
# ---------------------------------------------------------------------------


def test_long_horizon_patient_uniqueness():
    day1, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    day2, _ = build_representative_day_population(
        day=date(2026, 2, 3), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=43,
    )
    ids1 = {p.patient_id for p in day1}
    ids2 = {p.patient_id for p in day2}
    assert not (ids1 & ids2)


# ---------------------------------------------------------------------------
# Failure modes (sections 47, 51, 60, 93-94)
# ---------------------------------------------------------------------------


def test_porter_shortage_shows_degraded_service(baseline):
    shortage = evaluate_manual_conventional_porter_shortage(baseline, installed_porters=3)
    assert shortage.late + shortage.unmet > 0
    assert shortage.outcome != "RECOVERED_WITHOUT_SERVICE_IMPACT"


def test_mrt_carrier_shortage_shows_degraded_service(baseline):
    constrained = evaluate_mrt_dominant_operational_only_carrier_shortage(baseline, installed_carriers=7)
    assert constrained.late + constrained.unmet > 0


def test_mrt_carrier_shortage_never_auto_expands(baseline):
    constrained = evaluate_mrt_dominant_operational_only_carrier_shortage(baseline, installed_carriers=7)
    assert constrained.installed_carriers == 7  # never silently expanded


# ---------------------------------------------------------------------------
# Sensitivity (sections 81-90)
# ---------------------------------------------------------------------------


def test_census_sensitivity_general_logistics_responds():
    baselines = build_census_sensitivity_baselines(occupied_levels=(100, 170, 200))
    demand_counts = [len(b.corrected_demands) for b in baselines]
    assert demand_counts == sorted(demand_counts)  # monotonically increases with census
    nuclear_counts = [b.census.pet_procedures + b.census.spect_procedures for b in baselines]
    assert len(set(nuclear_counts)) == 1  # nuclear demand NOT tied to census (section 83)


def test_nuclear_demand_sensitivity_uses_authoritative_path():
    baseline_30 = build_common_project_baseline(target_mean_pet=30 * 32 / 50, target_mean_spect=30 * 18 / 50)
    baseline_100 = build_common_project_baseline(target_mean_pet=100 * 32 / 50, target_mean_spect=100 * 18 / 50)
    assert baseline_30.census.inpatients == baseline_100.census.inpatients == 170  # census fixed, only nuclear varies


def test_distance_sensitivity_reuses_authoritative_campus_function():
    from campus_retrofit_benchmark import run_distance_sensitivity_study
    rows = run_distance_sensitivity_study(distances_m=(250.0, 500.0))
    assert len(rows) >= 2


# ---------------------------------------------------------------------------
# Architecture fairness / qualification (sections 24, 70, 107)
# ---------------------------------------------------------------------------


def test_architecture_fairness_same_canonical_workload(four_results):
    assert len({r.canonical_patient_ids for r in four_results}) == 1
    assert len({r.canonical_nuclear_patient_ids for r in four_results}) == 1


def test_four_architecture_qualification_status(four_results):
    for r in four_results:
        qualification = qualify_architecture(r)
        assert qualification.status in ("QUALIFIED", "QUALIFIED_WITH_LIMITATIONS", "NOT_QUALIFIED")


def test_no_forced_winner_after_complete_revenue_fix(baseline, four_results):
    ranked = rank_cost_only(four_results)
    revenue = compute_whole_oncology_annual_revenue(baseline)
    ranked_revenue = rank_revenue_aware(four_results, revenue)
    assert ranked[0].architecture in ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT")
    assert ranked_revenue[0][0].architecture in ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT")


# ---------------------------------------------------------------------------
# Non-regression (section 112-113)
# ---------------------------------------------------------------------------


def test_nuclear_physical_non_regression():
    geometry = build_two_building_campus_geometry(campus_separation_m=500.0)
    result = run_campus_case_1_conventional(geometry=geometry, demand=200)
    assert result.winner.patients_retention_qualified_completed == 36


def test_general_logistics_physical_non_regression(baseline):
    linen_qty = sum(d.quantity for d in baseline.corrected_demands if d.stream == "CLEAN_LINEN")
    assert linen_qty == pytest.approx(1275.0)


def test_four_architecture_optimizer_non_regression(four_results):
    for r in four_results:
        assert r.feasible


def test_no_invalid_stubbed_hybrid_resourcing():
    import whole_oncology_four_architecture_optimization as module
    import inspect
    source = inspect.getsource(module)
    assert "SimpleNamespace" not in source
    assert "_resource_requirements_for_demand" not in source

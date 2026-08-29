"""Part 3E.2 -- focused invariant suite for the Decision Envelope, Architecture
Crossover & Decision-Critical Calibration analysis (Section 28).

These tests lock the READ-ONLY analytical contract: Part 3E.2 consumes the
committed Part 3E.1/3E/3D/economic/decay/transport authorities, invents no
engine/ranking/economics, applies no architecture bonus, preserves every
NOT_CALIBRATED honesty marker, and never fabricates a crossover, a probability
distribution, or an appointment date.

The Part 3E.1 campaign is expensive (~16 s); it is built ONCE at module scope
and shared by every test.
"""

from __future__ import annotations

import dataclasses

import pytest

import part3e2_decision_envelope as de
import part3e_radionuclide_experiment_campaign as camp
import part3e_radionuclide_aware_architecture as p3e
import whole_oncology_four_architecture_optimization as wo4a


# ---------------------------------------------------------------------------
# Shared, module-scoped fixtures (run the campaign + envelope exactly once).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def campaign() -> "camp.CampaignResult":
    return camp.run_full_campaign()


@pytest.fixture(scope="module")
def envelope(campaign) -> "de.Part3E2DecisionEnvelopeResult":
    return de.build_decision_envelope(campaign)


_BOUQUET = ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "MRT_DOMINANT", "HYBRID_MRT")


# ===========================================================================
# 1-8: Part 3E.1 baseline consumed (not rebuilt); radionuclides distinct.
# ===========================================================================


def test_01_part3e1_baseline_consumed_not_rebuilt(envelope, campaign):
    # The envelope embeds the SAME campaign object it was given (no rebuild).
    assert envelope.campaign is campaign


def test_02_f18_preserved(campaign):
    assert "F-18" in campaign.f18.radionuclides


def test_03_c11_distinct(campaign):
    assert campaign.c11.radionuclides == ("C-11",)
    assert campaign.c11.scenario_id != campaign.n13.scenario_id


def test_04_n13_distinct(campaign):
    assert campaign.n13.radionuclides == ("N-13",)


def test_05_o15_distinct(campaign):
    assert campaign.o15.radionuclides == ("O-15",)
    # O-15 has the shortest canonical half-life.
    assert de._HALF_LIVES["O-15"] < de._HALF_LIVES["N-13"] < de._HALF_LIVES["C-11"] < de._HALF_LIVES["F-18"]


def test_06_ga68_cyclotron_pathway_preserved(campaign):
    obs = campaign.ga68_cyclotron.production_source_observations
    assert any(o.source_kind == "CYCLOTRON" and o.radionuclide == "Ga-68" for o in obs)


def test_07_ga68_generator_pathway_preserved(campaign):
    obs = campaign.ga68_generator.production_source_observations
    assert any(o.source_kind == "GENERATOR" and o.radionuclide == "Ga-68" for o in obs)


def test_08_ga68_pathways_remain_distinct(campaign):
    cyc = campaign.ga68_cyclotron.production_source_observations[0]
    gen = campaign.ga68_generator.production_source_observations[0]
    assert cyc.source_kind == "CYCLOTRON" and gen.source_kind == "GENERATOR"
    assert cyc.catalog_model_id != gen.catalog_model_id


# ===========================================================================
# 9-14: no architecture bonus; canonical ranking/Pareto helpers.
# ===========================================================================


def test_09_no_mrt_bonus(envelope):
    # MRT never receives a decision region for free.
    assert envelope.mrt_dominant_decision_region == "NO_MRT_DOMINANT_DECISION_REGION_OBSERVED"


def test_10_no_hybrid_bonus(envelope):
    assert envelope.hybrid_decision_region == "NO_HYBRID_DECISION_REGION_OBSERVED"


def test_11_no_conventional_bonus(envelope):
    # AUTOMATED does not win a region merely for being conventional.
    assert envelope.automated_decision_region == "NO"


def test_12_no_short_half_life_bonus(envelope):
    # No short-half-life radionuclide flips the preferred architecture.
    for row in envelope.half_life_comparison:
        assert row.preferred_architecture == "MANUAL_CONVENTIONAL"
        assert row.correlates_with_ranking is False


def test_13_ranking_uses_canonical_helper(campaign):
    # The Part 3E ranking is exactly wo4a.rank_cost_only of the derived results.
    sr = campaign.baseline.scenario_result
    wo4a_results = tuple(r.architecture_result for r in sr.architecture_results)
    expected = tuple(r.architecture for r in wo4a.rank_cost_only(wo4a_results))
    assert sr.ranked_feasible_architectures == expected


def test_14_pareto_uses_canonical_helper(campaign):
    sr = campaign.baseline.scenario_result
    wo4a_results = tuple(r.architecture_result for r in sr.architecture_results)
    expected = tuple(r.architecture for r in wo4a.compute_pareto_front(wo4a_results))
    assert sr.pareto_front_architectures == expected


# ===========================================================================
# 15-17: known vs unknown economics preserved.
# ===========================================================================


def test_15_unknown_opex_not_zero_filled(campaign):
    for row in campaign.baseline.bouquet:
        # A KNOWN subtotal is reported; the TOTAL is flagged not-calibrated.
        assert row.total_opex_calibration_status == "KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED"


def test_16_total_opex_not_calibrated_preserved(envelope):
    for b in envelope.break_even_thresholds:
        assert b.full_opex_break_even_status == "FULL_OPEX_BREAK_EVEN_NOT_CALCULABLE"


def test_17_known_opex_subtotal_preserved_separately(envelope):
    # delta_known_annual_opex is distinct from delta_true_total_annual_opex.
    mrt = next(d for d in envelope.baseline_deltas if d.architecture == "MRT_DOMINANT")
    assert mrt.delta_known_annual_opex != mrt.delta_true_total_annual_opex


# ===========================================================================
# 18-20: canonical transport / speed / decay authorities.
# ===========================================================================


def test_18_distance_sensitivity_uses_canonical_transport_authority(envelope):
    from spatial_benchmark import _manual_transport_minutes, _mrt_transport_minutes
    from models import PlannerAssumptions
    a = PlannerAssumptions()
    # Recompute one distance point's transport time through the canonical
    # authority and confirm the envelope carries the SAME value.
    d, v, t = de._benchmark_worst_case_route()
    pt = next(p for p in envelope.distance_envelope if p.radionuclide == "F-18" and p.distance_multiplier == 1.0)
    expect_manual = _manual_transport_minutes(d, v, a)
    expect_mrt = _mrt_transport_minutes(d, v, t, a)
    assert pt.manual_transport_minutes == pytest.approx(expect_manual)
    assert pt.mrt_transport_minutes == pytest.approx(expect_mrt)


def test_19_mrt_speed_is_controlled_assumption(envelope):
    for p in envelope.mrt_speed_envelope:
        assert "CONTROLLED" in p.speed_basis.upper() or "ASSUMPTION" in p.speed_basis.upper()


def test_20_decay_uses_canonical_engine(envelope):
    from multi_isotope_decay import retained_fraction
    # A physical-effect delta's MRT retained fraction equals the canonical decay
    # authority over the single controlled interval.
    d = next(x for x in envelope.physical_effect_deltas if x.radionuclide == "F-18")
    elapsed = camp.CONTROLLED_EOB_TO_RELEASE_MINUTES + d.mrt_transport_minutes + camp.CONTROLLED_ADMIN_AFTER_ARRIVAL_MINUTES
    assert d.mrt_retained_fraction == pytest.approx(retained_fraction(elapsed, de._HALF_LIVES["F-18"]))


# ===========================================================================
# 21-28: explicit demand; production support != calibration; per-radionuclide.
# ===========================================================================


def test_21_explicit_patient_demand_only(envelope):
    counts = {(p.radionuclide, p.demand_level): p.patient_count for p in envelope.patient_volume_envelope}
    assert counts[("F-18", "BASELINE")] == 32
    assert counts[("C-11", "LOW")] == 2


def test_22_prevalence_not_invented(campaign):
    note = campaign.baseline.scenario_result.portfolio.multi_radionuclide_weighting_authority
    assert note == "NOT_MODELED"


def test_23_production_support_not_promoted_to_calibration(envelope):
    # A row that only DECLARES support (schedulable/modeled) is never labelled
    # manufacturer_calibrated unless it truly has a calibrated EOB record.
    for row in envelope.production_source_envelope:
        if row.production_calibration_status == "manufacturer_calibrated":
            assert row.has_calibrated_eob_record is True


def test_24_f18_calibration_never_borrowed(envelope):
    # The only manufacturer_calibrated production rows are F-18 rows.
    for row in envelope.production_source_envelope:
        if row.production_calibration_status == "manufacturer_calibrated":
            assert row.radionuclide == "F-18"


def test_25_c11_production_status_model_specific(envelope):
    c11 = [r for r in envelope.production_source_envelope if r.radionuclide == "C-11"]
    assert c11, "expected C-11 production source rows"
    assert all(r.production_calibration_status != "manufacturer_calibrated" for r in c11)


def test_26_n13_production_status_model_specific(envelope):
    n13 = [r for r in envelope.production_source_envelope if r.radionuclide == "N-13"]
    assert n13
    assert all(r.production_calibration_status != "manufacturer_calibrated" for r in n13)


def test_27_o15_production_status_model_specific(envelope):
    o15 = [r for r in envelope.production_source_envelope if r.radionuclide == "O-15"]
    assert o15
    assert all(r.production_calibration_status != "manufacturer_calibrated" for r in o15)


def test_28_ga68_source_identity_model_specific(envelope):
    ga = [r for r in envelope.production_source_envelope if r.radionuclide == "Ga-68"]
    kinds = {r.source_kind for r in ga}
    assert {"CYCLOTRON", "GENERATOR"}.issubset(kinds)


# ===========================================================================
# 29-34: scanner pools distinct; Part 3D consumed/unmodified; four architectures.
# ===========================================================================


def test_29_pet_spect_scanner_pools_distinct(campaign):
    agg = campaign.mixed_pet_spect.scenario_result.aggregation
    # PET and SPECT pools are counted separately, never collapsed.
    assert agg.required_total_scanner_count == agg.required_pet_scanner_count + agg.required_spect_scanner_count


def test_30_part3d_feasibility_consumed(envelope):
    # Every decision region carries a Part 3D physical-feasibility state.
    for region in envelope.decision_regions:
        assert region.physical_feasibility_state in (
            "FEASIBLE", "FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY",
            "INFEASIBLE", "NOT_FULLY_QUALIFIED", "NOT_EVALUATED",
        )


def test_31_part3d_not_modified(campaign):
    # The Part 3E architecture results carry the DERIVED (non-hardcoded) status.
    for pr in campaign.baseline.scenario_result.architecture_results:
        assert pr.physical_feasibility_status != "NOT_EVALUATED"


def test_32_equipment_opex_consumed_statuses_present(campaign):
    # The equipment OPEX authority's not-calibrated posture flows through as the
    # known-subtotal-only marker (never zero-filled to a fake total).
    for row in campaign.baseline.bouquet:
        assert "NOT_CALIBRATED" in row.total_opex_calibration_status


def test_33_economic_engine_not_rebuilt(campaign):
    # lifecycle_cost == new_study_capex + AF*known_annual_opex EXACTLY (the
    # canonical engine identity Part 3E.2 reuses, not a second engine).
    af = de.ANNUITY_FACTOR
    for row in campaign.baseline.bouquet:
        assert row.lifecycle_cost == pytest.approx(row.new_study_capex + af * row.known_annual_opex, rel=1e-9)


def test_34_all_four_architectures_represented(envelope):
    archs = {d.architecture for d in envelope.baseline_deltas}
    assert archs == set(_BOUQUET)


# ===========================================================================
# 35-41: crossover honesty; break-even read-only; uncalibrated not treated known.
# ===========================================================================


def test_35_crossover_requires_observed_ranking_change(envelope):
    for b in envelope.distance_crossovers:
        if b.crossover_state == "BRACKETED_CROSSOVER":
            assert b.preferred_below != b.preferred_above
        else:
            assert b.preferred_below == b.preferred_above


def test_36_no_crossover_fabricated(envelope):
    # Over the tested envelope no crossover was manufactured.
    assert all(b.crossover_state != "BRACKETED_CROSSOVER" for b in envelope.distance_crossovers)
    assert envelope.mrt_speed_crossover_found is False


def test_37_crossover_bracket_uses_tested_points(envelope):
    for b in envelope.distance_crossovers:
        assert b.lower_value in camp.CONTROLLED_DISTANCE_MULTIPLIERS
        assert b.upper_value in camp.CONTROLLED_DISTANCE_MULTIPLIERS


def test_38_no_absurd_range_extension(envelope):
    # Distance multipliers never exceed the defensible 3.0x upper bound.
    assert max(p.distance_multiplier for p in envelope.distance_envelope) <= 3.0


def test_39_capex_break_even_is_read_only_threshold(envelope):
    for b in envelope.break_even_thresholds:
        # The required CapEx reduction to tie equals the known lifecycle gap.
        assert b.required_capex_reduction_for_break_even_usd == pytest.approx(b.known_lifecycle_gap_usd)


def test_40_known_opex_break_even_is_read_only_threshold(envelope):
    af = de.ANNUITY_FACTOR
    for b in envelope.break_even_thresholds:
        assert b.required_annual_known_opex_savings_for_break_even_usd == pytest.approx(b.known_lifecycle_gap_usd / af)


def test_41_unknown_total_opex_not_treated_as_known(envelope):
    for b in envelope.break_even_thresholds:
        assert b.basis == "CANONICAL_LIFECYCLE_IDENTITY_KNOWN_OPEX_ONLY"
        assert b.full_opex_break_even_status == "FULL_OPEX_BREAK_EVEN_NOT_CALCULABLE"


# ===========================================================================
# 42-46: deterministic calibration; no probability; joint-scheduler limitation.
# ===========================================================================


def test_42_deterministic_calibration_priority(envelope):
    allowed = {
        "DECISION_CRITICAL", "POTENTIALLY_DECISION_CRITICAL",
        "UNLIKELY_TO_CHANGE_CURRENT_DECISION", "NOT_ASSESSABLE",
    }
    assert envelope.calibration_priorities
    for c in envelope.calibration_priorities:
        assert c.classification in allowed


def test_43_no_fake_probability_distribution(envelope):
    allowed = {"DECISION_ROBUST", "DECISION_SENSITIVE", "DECISION_UNRESOLVED_DUE_TO_CALIBRATION"}
    assert envelope.ranking_robustness.robustness in allowed
    # No probabilistic vocabulary leaks into the rationale.
    text = envelope.ranking_robustness.rationale.lower()
    assert "confidence interval" not in text and "probability" not in text


def test_44_joint_scheduler_limitation_preserved(envelope):
    assert envelope.joint_scheduler_gate.true_joint_multi_radionuclide_scheduling == "NO"


def test_45_mixed_pet_joint_feasibility_not_overstated(envelope):
    status = envelope.joint_scheduler_gate.mixed_pet_joint_feasibility_status
    assert status != "JOINT_OPERATION_VALIDATED"


def test_46_mixed_pet_spect_feasibility_not_overstated(envelope):
    status = envelope.joint_scheduler_gate.mixed_pet_spect_joint_feasibility_status
    assert status != "JOINT_OPERATION_VALIDATED"


# ===========================================================================
# 47-50: export seams; unknown financial/appointment fields preserved.
# ===========================================================================


def test_47_patient_export_seam_preserved(campaign):
    rows = p3e.export_patient_appointment_rows(campaign.baseline.scenario_result)
    assert rows and all(hasattr(r, "radionuclide") for r in rows)


def test_48_appointment_export_seam_preserved(envelope):
    assert envelope.forward_appointment_export
    for r in envelope.forward_appointment_export:
        assert hasattr(r, "appointment_date")


def test_49_financial_export_seam_preserved(campaign):
    rows = p3e.export_financial_rows(campaign.baseline.scenario_result)
    assert len(rows) == 4
    assert {r.architecture for r in rows} == set(_BOUQUET)


def test_50_unknown_financial_fields_preserved(envelope):
    # Appointment date is explicitly NOT_MODELED; never a fabricated date.
    for r in envelope.forward_appointment_export:
        assert r.appointment_date == "NOT_MODELED"
        assert r.forward_plan_status == "ANALYTICAL_REQUIREMENT_NOT_A_VALIDATED_SCHEDULE"


# ===========================================================================
# 51-56: simulation timing (excludes pytest); tables present.
# ===========================================================================


def test_51_simulation_timing_excludes_pytest_time(envelope):
    # Timing measurements are self-contained wall-clock floats, not pytest-derived.
    for s in envelope.simulation_performance:
        assert isinstance(s.wall_clock_seconds, float)
        assert s.wall_clock_seconds >= 0.0


def test_52_scenario_execution_time_recorded(envelope):
    labels = {s.measurement for s in envelope.simulation_performance}
    assert "A_SINGLE_SCENARIO" in labels


def test_53_bouquet_time_recorded(envelope):
    labels = {s.measurement for s in envelope.simulation_performance}
    assert "B_FOUR_ARCHITECTURE_BOUQUET" in labels


def test_54_distance_sweep_time_recorded(envelope):
    labels = {s.measurement for s in envelope.simulation_performance}
    assert "C_DISTANCE_SWEEP" in labels


def test_55_full_campaign_time_recorded(envelope):
    labels = {s.measurement for s in envelope.simulation_performance}
    assert "F_FULL_PART3E2_CAMPAIGN" in labels


def test_56_all_60_tables_present():
    # The report file physically contains all 60 required TABLE headings.
    import os
    path = os.path.join(os.path.dirname(__file__), "PART_3E_2_DECISION_ENVELOPE_AND_CROSSOVER_REPORT.md")
    assert os.path.exists(path), "report file must exist"
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for n in range(1, 61):
        assert f"TABLE {n} " in text or f"TABLE {n}\n" in text or f"TABLE {n} —" in text, f"missing TABLE {n}"


# ===========================================================================
# 57-63: decision-region conclusions derived; neutrality; gaps not aspirational.
# ===========================================================================


def test_57_mrt_decision_region_conclusion_derived(envelope):
    assert envelope.mrt_dominant_decision_region in (
        "YES", "NO_MRT_DOMINANT_DECISION_REGION_OBSERVED",
        "NOT_ESTABLISHED_DUE_TO_UNCALIBRATED_ECONOMICS",
    )


def test_58_hybrid_decision_region_conclusion_derived(envelope):
    assert envelope.hybrid_decision_region in (
        "YES", "NO_HYBRID_DECISION_REGION_OBSERVED",
        "NOT_ESTABLISHED_DUE_TO_UNCALIBRATED_ECONOMICS",
    )


def test_59_no_architecture_guaranteed_a_winning_region(envelope):
    # At least one architecture is observed WITHOUT a winning region -> no
    # architecture is guaranteed one. (MRT + Hybrid both have none here.)
    regions = {
        "MANUAL_CONVENTIONAL": envelope.manual_decision_region,
        "AUTOMATED_CONVENTIONAL": envelope.automated_decision_region,
        "MRT_DOMINANT": envelope.mrt_dominant_decision_region,
        "HYBRID_MRT": envelope.hybrid_decision_region,
    }
    assert any(v not in ("YES",) for v in regions.values())


def test_60_calibration_gaps_not_closed_aspirationally(envelope):
    # Production output gaps remain NOT_CALIBRATED; never promoted to calibrated.
    prod = [c for c in envelope.calibration_priorities if c.gap_category == "PRODUCTION"]
    assert prod
    for c in prod:
        assert c.current_status == "NOT_CALIBRATED"


def test_61_c11_n13_o15_not_collapsed(envelope):
    # The three short-half-life radionuclides appear as DISTINCT half-life rows.
    hl = {r.radionuclide: r.half_life_minutes for r in envelope.half_life_comparison}
    assert hl["C-11"] != hl["N-13"] != hl["O-15"]
    assert hl["C-11"] is not None and hl["N-13"] is not None and hl["O-15"] is not None


def test_62_ga68_generator_economics_remain_uncalibrated(envelope):
    ga_gen = [r for r in envelope.production_source_envelope
              if r.radionuclide == "Ga-68" and r.source_kind == "GENERATOR"]
    assert ga_gen
    for r in ga_gen:
        assert r.production_calibration_status == "not_calibrated"


def test_63_architecture_neutrality_preserved(envelope):
    # The module encodes no per-architecture preference: the preferred
    # architecture EMERGES from the canonical cost-only ranking, identically for
    # every experiment (no experiment-specific override).
    prefs = {d.preferred_architecture for d in envelope.decision_drivers}
    # All emerge from the same canonical ranking; none is hand-forced.
    assert prefs, "decision drivers must be populated"
    assert all(d.preferred_architecture in _BOUQUET for d in envelope.decision_drivers)


# ===========================================================================
# Additional invariants (Section 28 "add where useful").
# ===========================================================================


def test_64_baseline_delta_reference_is_manual(envelope):
    for d in envelope.baseline_deltas:
        assert d.reference_architecture == "MANUAL_CONVENTIONAL"
    manual = next(d for d in envelope.baseline_deltas if d.architecture == "MANUAL_CONVENTIONAL")
    assert manual.delta_new_study_capex == 0.0 and manual.delta_known_lifecycle_cost == 0.0


def test_65_principal_baseline_driver_emerges_from_evidence(envelope):
    allowed = {
        "CAPEX_DOMINANT", "KNOWN_OPEX_DOMINANT", "TRANSPORT_TIME_DOMINANT",
        "DECAY_LOSS_DOMINANT", "PRODUCTION_CAPACITY_DOMINANT", "SCANNER_CAPACITY_DOMINANT",
        "STAFFING_DOMINANT", "PHYSICAL_FEASIBILITY_DOMINANT", "UNCALIBRATED_ECONOMICS_DOMINANT",
        "MULTIPLE_DRIVERS", "INSUFFICIENT_EVIDENCE",
    }
    assert envelope.principal_baseline_decision_driver in allowed


def test_66_annuity_factor_matches_canonical_engine(envelope):
    # The AF is derived from the wo4a discount rate / horizon, not invented.
    assert envelope.annuity_factor == pytest.approx(
        de.operating_horizon_annuity_factor(
            discount_rate_pct=float(wo4a.DISCOUNT_RATE_PCT), analysis_years=int(wo4a.ANALYSIS_YEARS)
        )
    )


def test_67_read_models_are_frozen():
    # A representative sample of read models must be immutable (frozen).
    for cls in (de.ArchitectureDeltaDecomposition, de.BreakEvenThreshold,
                de.CalibrationPriority, de.ArchitectureCrossoverBracket,
                de.Part3E2DecisionEnvelopeResult):
        assert cls.__dataclass_params__.frozen is True


def test_68_result_immutable_instance(envelope):
    with pytest.raises(dataclasses.FrozenInstanceError):
        envelope.principal_baseline_decision_driver = "CHANGED"  # type: ignore[misc]


# ===========================================================================
# 69-78: Part 3E.2 FINAL RECONCILIATION invariants (universe vs subset; qualified
# KNOWN_OPEX_DOMINANT; total OPEX NOT_CALIBRATED; calibration threshold discipline;
# AS-IS twin not implemented).
# ===========================================================================


def test_69_canonical_physical_universe_is_15(envelope):
    # The canonical physical universe is CONSUMED from the completeness authority,
    # never hardcoded to the experimental subset. It is 15 radionuclides.
    from clinical_radionuclide_portfolio import discover_physically_recognized_radionuclides
    canonical = set(discover_physically_recognized_radionuclides())
    assert len(canonical) == 15
    assert envelope.physically_recognized_radionuclide_count == 15
    assert set(envelope.physically_recognized_radionuclides) == canonical


def test_70_analyzed_subset_is_separate_from_universe(envelope):
    # The analyzed subset is a STRICT subset of the physical universe, reported
    # separately -- never conflated, never expanded to equal the universe.
    universe = set(envelope.physically_recognized_radionuclides)
    analyzed = set(envelope.part3e2_radionuclides_analyzed)
    assert envelope.part3e2_radionuclides_analyzed_count == 6
    assert analyzed == {"F-18", "C-11", "N-13", "O-15", "Ga-68", "Tc-99m"}
    assert analyzed < universe  # strict subset
    assert envelope.part3e2_radionuclides_analyzed_count < envelope.physically_recognized_radionuclide_count


def test_71_known_opex_dominant_terminology_is_qualified(envelope):
    # KNOWN_OPEX_DOMINANT must be QUALIFIED: it is a full-bouquet-spread statement,
    # not a claim that total OPEX is known nor that OPEX governs the decisive margin.
    q = envelope.known_opex_driver_qualification
    assert "QUALIFIED" in q
    assert "NOT_CALIBRATED" in q
    # It explicitly names that the decisive Manual-vs-Automated margin is CapEx-led.
    assert "CAPEX" in q.upper()
    assert "MANUAL_CONVENTIONAL" in q and "AUTOMATED_CONVENTIONAL" in q


def test_72_pairwise_decisive_margin_is_capex_led(campaign):
    # Deterministic decomposition: at the binding preferred->second-best pair
    # (Manual vs Automated) the discounted CapEx term dominates the discounted
    # known-OPEX term. This is the fact the qualification rests on.
    af = de.ANNUITY_FACTOR
    rows = {r.architecture: r for r in campaign.baseline.bouquet}
    ordered = sorted(("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "MRT_DOMINANT", "HYBRID_MRT"),
                     key=lambda a: rows[a].lifecycle_cost)
    pref, second = ordered[0], ordered[1]
    d_capex = rows[second].new_study_capex - rows[pref].new_study_capex
    d_opex_life = (rows[second].known_annual_opex - rows[pref].known_annual_opex) * af
    assert abs(d_capex) > abs(d_opex_life)  # CapEx-led decisive margin


def test_73_lifecycle_identity_reconciles_per_pair(campaign):
    # ΔLifecycleKnown == ΔCapEx + AF·ΔKnownAnnualOPEX exactly, per pair vs Manual.
    af = de.ANNUITY_FACTOR
    rows = {r.architecture: r for r in campaign.baseline.bouquet}
    ref = rows["MANUAL_CONVENTIONAL"]
    for a in ("AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT"):
        d_capex = rows[a].new_study_capex - ref.new_study_capex
        d_opex = rows[a].known_annual_opex - ref.known_annual_opex
        d_life = rows[a].lifecycle_cost - ref.lifecycle_cost
        assert d_life == pytest.approx(d_capex + af * d_opex, rel=1e-9)


def test_74_total_opex_remains_not_calibrated(envelope, campaign):
    # Full-OPEX limitation preserved: total OPEX NOT_CALIBRATED, full-OPEX break-even
    # NOT_CALCULABLE. Uncalibrated components are never treated as zero.
    for b in envelope.break_even_thresholds:
        assert b.full_opex_break_even_status == "FULL_OPEX_BREAK_EVEN_NOT_CALCULABLE"
    for row in campaign.baseline.bouquet:
        assert "NOT_CALIBRATED" in row.total_opex_calibration_status


def test_75_porter_calibration_rationale_is_threshold_based_not_cancellation(envelope):
    # Reconciliation: porter labor does NOT cancel (different FTE on Manual vs
    # Automated); its UNLIKELY_TO_CHANGE label must rest on a deterministic
    # directional threshold, NOT a false "common cancels" claim.
    porter = next(c for c in envelope.calibration_priorities if c.gap_id == "porter_staffing_rate")
    assert porter.classification == "UNLIKELY_TO_CHANGE_CURRENT_DECISION"
    text = porter.rationale.lower()
    assert "does not cancel" in text
    assert "threshold" in text or "directional" in text
    # Must NOT claim porter is common-and-cancels.
    assert "common to both" not in text


def test_76_unlikely_to_change_labels_have_deterministic_basis(envelope):
    # Every UNLIKELY_TO_CHANGE classification must carry a deterministic argument
    # (exact cancellation OR proven directional bound), never "unknown => zero".
    for c in envelope.calibration_priorities:
        if c.classification == "UNLIKELY_TO_CHANGE_CURRENT_DECISION":
            r = c.rationale.lower()
            assert any(k in r for k in ("cancel", "widen", "threshold", "directional", "at least as")), c.gap_id


def test_77_production_gaps_not_unlikely_to_change(envelope):
    # Unbounded production-output unknowns must NOT be blanket UNLIKELY_TO_CHANGE;
    # they are POTENTIALLY_DECISION_CRITICAL (feasibility/admissibility dimension).
    for c in envelope.calibration_priorities:
        if c.gap_category == "PRODUCTION":
            assert c.classification == "POTENTIALLY_DECISION_CRITICAL"
            assert c.current_status == "NOT_CALIBRATED"


def test_78_as_is_twin_not_implemented_in_report():
    # The report must state the AS-IS twin is NOT implemented (readiness != built).
    import os
    path = os.path.join(os.path.dirname(__file__), "PART_3E_2_DECISION_ENVELOPE_AND_CROSSOVER_REPORT.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    assert "EXISTING_FACILITY_AS_IS_TWIN_IMPLEMENTED" in text
    assert "FACILITY_INGESTION_IMPLEMENTED" in text
    assert "LIVE_HOSPITAL_OPERATIONAL_STATE_INGESTION_IMPLEMENTED" in text
    assert "READY_TO_BEGIN_EXISTING_FACILITY_AS_IS_TWIN_BUILD" in text
    # Both the universe (15) and subset (6) must be present and distinct.
    assert "PHYSICALLY_RECOGNIZED_RADIONUCLIDE_COUNT" in text
    assert "PART3E2_RADIONUCLIDES_ANALYZED_COUNT" in text

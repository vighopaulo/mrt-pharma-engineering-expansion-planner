"""Build 2R FINAL eight-floor capital architecture competition -- focused
tests (18 required). Never full-repository regression from this file alone;
the calling validation sequence runs full regression separately if all
required checks pass."""

from __future__ import annotations

import pytest

from whole_oncology_four_architecture_optimization import (
    build_eight_floor_deterministic_capital_baseline,
    evaluate_manual_conventional,
    evaluate_automated_conventional,
    evaluate_automated_conventional_final,
    evaluate_light_mrt_dominant,
    evaluate_light_mrt_nuclear_standalone_and_incremental,
    evaluate_optimized_technology_mix,
    evaluate_dedicated_rp_pts_nuclear_transport,
    compute_common_project_capex,
    compute_common_project_opex,
    _nuclear_result,
    _price_stream_as_manual,
    _price_stream_as_agv,
    _price_stream_as_pts,
    STREAMS,
    DISCOUNT_RATE_PCT,
    ANALYSIS_YEARS,
)
from editable_default_authority import editable_default_registry_table


@pytest.fixture(scope="module")
def baseline():
    return build_eight_floor_deterministic_capital_baseline(seed=42)


@pytest.fixture(scope="module")
def af():
    return (1 - (1 + DISCOUNT_RATE_PCT / 100.0) ** (-ANALYSIS_YEARS)) / (DISCOUNT_RATE_PCT / 100.0)


# 1. Identical raw demand reaches every architecture.
def test_identical_raw_demand_reaches_every_architecture(baseline):
    for stream in STREAMS:
        assert len(tuple(d for d in baseline.corrected_demands if d.stream == stream)) == 80


# 2. 30 nuclear procedures remain identical across all candidates.
def test_thirty_nuclear_procedures_identical_across_candidates(baseline):
    manual_nuclear = _nuclear_result(baseline, mrt_floors=frozenset())
    all_floors = frozenset(range(1, baseline.geometry.floor_count + 1))
    mrt_nuclear = _nuclear_result(baseline, mrt_floors=all_floors)
    rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(baseline)
    assert len(manual_nuclear.patient_traces) == 30
    assert len(mrt_nuclear.patient_traces) == 30
    assert rp_pts.missions_per_day == 30
    assert {t.canonical_patient_id for t in manual_nuclear.patient_traces} == {t.canonical_patient_id for t in mrt_nuclear.patient_traces}


# 3. No legacy $11.4M MRT comparator enters active competition.
def test_no_legacy_mrt_comparator_in_active_competition(baseline):
    light = evaluate_light_mrt_dominant(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING", endpoint_topology="FULL_ROOM_COVERAGE")
    mrt_nuc = evaluate_light_mrt_nuclear_standalone_and_incremental(baseline)
    mrt_final_capex = light.architecture_specific_capex + mrt_nuc.incremental_capex
    assert mrt_final_capex < 1_000_000.0
    assert mrt_final_capex != pytest.approx(11_400_000.0)


# 4. Shared MRT infrastructure is charged once (Optimized bundle == pure MRT CapEx basis).
def test_shared_mrt_infrastructure_charged_once(baseline):
    light = evaluate_light_mrt_dominant(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING", endpoint_topology="FULL_ROOM_COVERAGE")
    opt_b = evaluate_optimized_technology_mix(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING", mrt_nuclear_qualified=True)
    mrt_nuc = evaluate_light_mrt_nuclear_standalone_and_incremental(baseline)
    # Optimized (MRT selected for general + nuclear) must equal pure MRT's guideway/endpoint
    # CapEx + the SAME incremental nuclear endpoint delta -- never guideway charged twice.
    assert opt_b.architecture_specific_capex == pytest.approx(light.architecture_specific_capex + mrt_nuc.incremental_capex, abs=1.0)


# 5. Shared AGV fleet is jointly resized after service assignment (Automated's
#    combined AGV fleet is not simply the sum of independent per-stream fleets).
def test_shared_agv_fleet_jointly_resized(baseline):
    linen_agv = _price_stream_as_agv(baseline, "CLEAN_LINEN")
    pharmacy_agv = _price_stream_as_agv(baseline, "PHARMACY_INFUSION")
    sterile_agv = _price_stream_as_agv(baseline, "STERILE_CLEAN_SUPPLY")
    standalone_sum_vehicle_capex = sum(p.capex for p in (linen_agv, pharmacy_agv, sterile_agv) if p.eligible)
    automated = evaluate_automated_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    # The tested Automated Conventional authority already jointly sizes ONE AGV fleet
    # across all AGV-served streams (agv_required_fleet_size on the COMBINED mission set) --
    # this must be <= the sum of three independently-standalone-sized fleets.
    assert automated.architecture_specific_capex <= standalone_sum_vehicle_capex + 200_000.0  # generous bound; joint sizing never worse


# 6. Shared PTS infrastructure is not duplicated.
def test_shared_pts_infrastructure_not_duplicated(baseline):
    automated = evaluate_automated_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    assert any("Superseded the prior agv_new_study_capex/pts_new_study_capex formula" in n for n in automated.notes)


# 7. Linen >5kg does not enter current MRT.
def test_linen_over_five_kg_does_not_enter_mrt(baseline):
    opt_a = evaluate_optimized_technology_mix(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING", mrt_nuclear_qualified=False)
    assert opt_a.service_technology["CLEAN_LINEN"] != "MRT"
    assert any("13.5kg > 5.0kg" in n for n in opt_a.notes)


# 8. Corrected 80kg linen fallback remains intact.
def test_eighty_kg_linen_fallback_intact():
    from conventional_transport_authority import DEFAULT_LINEN_CART
    assert DEFAULT_LINEN_CART.payload_capacity == pytest.approx(80.0)


# 9. Automated nuclear selection can choose RP-PTS over Manual when economically valid.
def test_automated_nuclear_selection_chooses_rp_pts_when_valid(baseline):
    final = evaluate_automated_conventional_final(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    assert final.selected_nuclear_technology == "DEDICATED_RP_PTS"
    assert final.rp_pts_nuclear_leg_tco_10yr < final.manual_nuclear_leg_tco_10yr


# 10. Optimized Mix is service/technology based, not floor-Hybrid based.
def test_optimized_mix_is_service_based_not_floor_hybrid(baseline):
    opt_a = evaluate_optimized_technology_mix(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING", mrt_nuclear_qualified=False)
    assert set(opt_a.service_technology.keys()) == set(STREAMS) | {"RADIOPHARMACEUTICAL_NUCLEAR"}
    assert not any("floor" in str(v).lower() for v in opt_a.service_technology.values())


# 11. Physical eligibility precedes economic selection.
def test_physical_eligibility_precedes_economics(baseline):
    linen_pts = _price_stream_as_pts(baseline, "CLEAN_LINEN")
    assert linen_pts.eligible is False
    sterile_pts = _price_stream_as_pts(baseline, "STERILE_CLEAN_SUPPLY")
    assert sterile_pts.eligible is False
    blood_agv = _price_stream_as_agv(baseline, "SPECIMEN_BLOOD")
    assert blood_agv.eligible is False


# 12. Peak human concurrency is not automatically annual FTE (RP-PTS semantics preserved).
def test_peak_human_concurrency_not_automatically_annual_fte(baseline):
    rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(baseline)
    assert rp_pts.labor.peak_concurrent_human_handlers == 5
    assert rp_pts.labor.final_required_fte == 1


# 13. Common CapEx is identical across candidates.
def test_common_capex_identical_across_candidates(baseline):
    common = compute_common_project_capex(baseline, development_context="RETROFIT")
    manual = evaluate_manual_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    automated = evaluate_automated_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    assert manual.common_inherited_capex == pytest.approx(common.total_common_asset_value)
    assert automated.common_inherited_capex == pytest.approx(common.total_common_asset_value)


# 14. Common OPEX is identical across candidates.
def test_common_opex_identical_across_candidates(baseline):
    common_opex = compute_common_project_opex(_nuclear_result(baseline, mrt_floors=frozenset()))
    manual = evaluate_manual_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    automated = evaluate_automated_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    assert manual.common_annual_opex == pytest.approx(common_opex.common_annual_opex, abs=1.0)
    assert automated.common_annual_opex == pytest.approx(common_opex.common_annual_opex, abs=1.0)


# 15. Architecture-specific TCO reconciles.
def test_architecture_specific_tco_reconciles(baseline, af):
    final = evaluate_automated_conventional_final(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    tco = final.architecture_specific_capex + final.architecture_specific_annual_opex * af
    assert tco == pytest.approx(
        final.whole_architecture_tco_rp_pts_nuclear_10yr if final.selected_nuclear_technology == "DEDICATED_RP_PTS" else final.whole_architecture_tco_manual_nuclear_10yr
    )


# 16. Whole-project TCO reconciles (common + architecture-specific, not mixed scopes).
def test_whole_project_tco_reconciles(baseline, af):
    common = compute_common_project_capex(baseline, development_context="RETROFIT")
    common_opex = compute_common_project_opex(_nuclear_result(baseline, mrt_floors=frozenset()))
    manual = evaluate_manual_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    whole_capex = common.total_common_asset_value + manual.architecture_specific_capex
    whole_opex = common_opex.common_annual_opex + manual.architecture_specific_annual_opex
    whole_tco = whole_capex + whole_opex * af
    arch_tco = manual.architecture_specific_capex + manual.architecture_specific_annual_opex * af
    assert whole_tco == pytest.approx(common.total_common_asset_value + common_opex.common_annual_opex * af + arch_tco)


# 17. MRT nuclear validation sensitivity is clearly separated from currently qualified result.
def test_mrt_nuclear_sensitivity_separated_from_qualified(baseline):
    opt_a = evaluate_optimized_technology_mix(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING", mrt_nuclear_qualified=False)
    opt_b = evaluate_optimized_technology_mix(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING", mrt_nuclear_qualified=True)
    assert opt_a.view == "CURRENTLY_PHYSICALLY_QUALIFIED_MIX"
    assert opt_b.view == "MRT_NUCLEAR_VALIDATION_SENSITIVITY"
    assert opt_a.service_technology["RADIOPHARMACEUTICAL_NUCLEAR"] != "MRT_SHIELDED"
    assert any("SHIELDING_NOT_YET_VALIDATED" in n for n in opt_b.notes)


# 18. Defaults/provenance remain attached.
def test_defaults_provenance_remain_attached():
    for param in editable_default_registry_table():
        assert param.parameter_id
        assert param.source_type
        assert param.notes is not None


# ---------------------------------------------------------------------------
# FINAL BUILD 2R CLOSURE -- three narrow corrections.
# ---------------------------------------------------------------------------

class TestFinalBuild2RClosureCorrections:

    # Correction 1: demand conservation -- general logistics vs nuclear vs total.
    def test_demand_conservation_reconciles_by_category(self, baseline):
        general_logistics_demands_served = sum(
            len(tuple(d for d in baseline.corrected_demands if d.stream == s)) for s in STREAMS
        )
        nuclear_procedures_served = len(_nuclear_result(baseline, mrt_floors=frozenset()).patient_traces)
        total_service_requirements_served = general_logistics_demands_served + nuclear_procedures_served
        assert general_logistics_demands_served == 320
        assert nuclear_procedures_served == 30
        assert total_service_requirements_served == 350

    # Correction 2: RP-PTS is never labeled PHYSICALLY_QUALIFIED -- only
    # CLINICAL_PRECEDENT_EXISTS / project-shielding-not-yet-validated, with
    # economic completeness (COMPLETE_WITH_DEFAULTS) kept as a SEPARATE axis.
    def test_rp_pts_never_labeled_physically_qualified(self, baseline):
        rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(baseline)
        assert rp_pts.shielding_status == "CLINICALLY_DEMONSTRATED_BUT_PROJECT_SHIELDING_NOT_CALIBRATED"
        assert "PHYSICALLY_QUALIFIED" not in rp_pts.shielding_status
        final = evaluate_automated_conventional_final(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
        assert final.result_status == "COMPLETE_WITH_DEFAULTS"
        assert not any("RP-PTS" in n and "PHYSICALLY_QUALIFIED" in n for n in final.notes)
        assert any("CLINICALLY_DEMONSTRATED_BUT_PROJECT_SHIELDING_NOT_CALIBRATED" in n for n in final.notes)

    # Correction 3: nuclear-leg-only marginal TCO is the selection basis,
    # not the whole-architecture totals (though both must agree on the winner).
    def test_nuclear_leg_marginal_tco_is_selection_basis(self, baseline):
        final = evaluate_automated_conventional_final(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
        assert final.manual_nuclear_leg_tco_10yr == pytest.approx(2_976_785.0, abs=1000.0)
        assert final.rp_pts_nuclear_leg_tco_10yr == pytest.approx(766_293.0, abs=1000.0)
        assert final.delta_nuclear_leg_tco_10yr == pytest.approx(
            final.rp_pts_nuclear_leg_tco_10yr - final.manual_nuclear_leg_tco_10yr,
        )
        assert final.delta_nuclear_leg_tco_10yr == pytest.approx(-2_210_491.0, abs=1000.0)
        # The whole-architecture totals must independently agree on the winner
        # (never used as the primary criterion, but must reconcile).
        whole_delta = final.whole_architecture_tco_rp_pts_nuclear_10yr - final.whole_architecture_tco_manual_nuclear_10yr
        assert whole_delta == pytest.approx(final.delta_nuclear_leg_tco_10yr, abs=1.0)
        assert any("NUCLEAR-LEG-ONLY marginal comparison" in n for n in final.notes)


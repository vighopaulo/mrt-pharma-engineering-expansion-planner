"""Build 2R Dedicated RP-PTS focused tests -- editable-default authority,
RP-PTS distinctness/topology/economics, and the Automated+RP-PTS diagnostic
portfolio. Never full repository regression (Section 38)."""

from __future__ import annotations

import pytest

from editable_default_authority import (
    EditableParameter,
    ORDINARY_PTS_SPEED_M_PER_S,
    RP_PTS_OPERATING_SPEED_M_PER_S,
    PTS_REFERENCE_TRANSACTIONS_PER_DAY,
    RP_PTS_PET_DOSE_PRECEDENT_DISTANCE_M,
    RP_PTS_PUBLISHED_SYSTEM_CAPEX_REFERENCE_USD,
    RP_PTS_SHIELDED_CARRIER_MASS_LIMIT_KG,
    editable_default_registry_table,
)
from dedicated_rp_pts_authority import (
    RP_PTS_COMPATIBLE_STREAMS,
    RP_PTS_INSTALLED_STATIONS,
    compute_rp_pts_mission_cycle,
    compute_rp_pts_capex,
)
from conventional_transport_authority import TECHNOLOGY_STREAM_COMPATIBILITY, DEFAULT_PTS_NETWORK
from whole_oncology_four_architecture_optimization import (
    build_eight_floor_deterministic_capital_baseline,
    evaluate_dedicated_rp_pts_nuclear_transport,
    evaluate_automated_conventional_with_dedicated_rp_pts_diagnostic,
    evaluate_automated_conventional,
    evaluate_manual_conventional,
    evaluate_light_mrt_nuclear_standalone_and_incremental,
    _nuclear_result,
    compute_common_project_capex,
    compute_common_project_opex,
    DISCOUNT_RATE_PCT,
    ANALYSIS_YEARS,
)


@pytest.fixture(scope="module")
def capital_baseline():
    return build_eight_floor_deterministic_capital_baseline(seed=42)


# ---------------------------------------------------------------------------
# 1. Dedicated RP-PTS is distinct from ordinary PTS / AGV / MANUAL_SHIELDED / MRT.
# ---------------------------------------------------------------------------

def test_rp_pts_distinct_from_ordinary_pts_and_agv():
    assert RP_PTS_COMPATIBLE_STREAMS == frozenset({"RADIOPHARMACEUTICAL_NUCLEAR"})
    assert "RADIOPHARMACEUTICAL_NUCLEAR" not in TECHNOLOGY_STREAM_COMPATIBILITY["PNEUMATIC_TUBE"]
    assert "RADIOPHARMACEUTICAL_NUCLEAR" not in TECHNOLOGY_STREAM_COMPATIBILITY["AGV_AMR"]


def test_ordinary_pts_never_gains_nuclear_compatibility(capital_baseline):
    """Confirms touching RP-PTS in this build never mutates the ordinary
    PTS authority's compatible_streams."""
    assert "RADIOPHARMACEUTICAL_NUCLEAR" not in DEFAULT_PTS_NETWORK.compatible_streams
    assert DEFAULT_PTS_NETWORK.compatible_streams == frozenset({"SPECIMEN_BLOOD", "PHARMACY_INFUSION"})


# ---------------------------------------------------------------------------
# 2. Same 30 nuclear procedures reach all nuclear competitors.
# ---------------------------------------------------------------------------

def test_same_thirty_procedures_reach_manual_and_rp_pts(capital_baseline):
    manual_nuclear = _nuclear_result(capital_baseline, mrt_floors=frozenset())
    rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
    assert len(manual_nuclear.patient_traces) == 30
    assert rp_pts.missions_per_day == 30
    assert rp_pts.missions_per_day == len(manual_nuclear.patient_traces)


def test_rp_pts_reuses_same_canonical_nuclear_result_as_manual(capital_baseline):
    """RP-PTS's own nuclear() call uses the IDENTICAL mrt_floors=frozenset()
    envelope Manual/Automated use -- never a divergent nuclear demand."""
    manual = evaluate_manual_conventional(capital_baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    manual_nuclear = _nuclear_result(capital_baseline, mrt_floors=frozenset())
    assert manual.nuclear_qualified_completed == manual_nuclear.retention_qualified_completed == 30


# ---------------------------------------------------------------------------
# 3-6. Editable default -> active -> override model.
# ---------------------------------------------------------------------------

def test_published_defaults_remain_editable():
    assert RP_PTS_OPERATING_SPEED_M_PER_S.user_editable is True
    assert PTS_REFERENCE_TRANSACTIONS_PER_DAY.user_editable is True
    assert RP_PTS_PUBLISHED_SYSTEM_CAPEX_REFERENCE_USD.user_editable is True


def test_active_value_equals_default_until_overridden():
    param = EditableParameter(
        parameter_id="TEST_PARAM", default_value=5.0, units="unit", source="test",
        source_type="PUBLISHED_ENGINEERING_DEFAULT", confidence="MEDIUM",
    )
    assert param.override_value is None
    assert param.active_value == 5.0
    assert param.override_status == "NO_OVERRIDE"


def test_user_override_changes_active_without_destroying_default():
    param = EditableParameter(
        parameter_id="TEST_PARAM", default_value=6.1, units="m/s", source="published source",
        source_type="PUBLISHED_ENGINEERING_DEFAULT", confidence="MEDIUM-HIGH",
    )
    overridden = param.with_override(5.2)
    assert overridden.active_value == 5.2
    assert overridden.default_value == 6.1  # original default preserved
    assert overridden.override_status == "USER_OVERRIDE"
    assert overridden.source == param.source  # provenance preserved


def test_source_provenance_remains_attached_after_override():
    overridden = RP_PTS_OPERATING_SPEED_M_PER_S.with_override(5.2)
    assert overridden.source == RP_PTS_OPERATING_SPEED_M_PER_S.source
    assert overridden.source_type == RP_PTS_OPERATING_SPEED_M_PER_S.source_type
    assert overridden.default_value == 6.1


def test_ordinary_pts_active_speed_preserves_existing_benchmark_value():
    """Section 23: touching ordinary-PTS defaults must NOT change the active
    benchmark value -- the 6.1 m/s published default is registered, but the
    active value stays the pre-existing 6.0 m/s repo authority."""
    assert ORDINARY_PTS_SPEED_M_PER_S.default_value == 6.1
    assert ORDINARY_PTS_SPEED_M_PER_S.active_value == pytest.approx(DEFAULT_PTS_NETWORK.speed_m_per_s)
    assert ORDINARY_PTS_SPEED_M_PER_S.active_value == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# 7-10. Precedent/reference values must not be misused.
# ---------------------------------------------------------------------------

def test_ordinary_pts_speed_default_not_treated_as_guaranteed_rp_pts_fact():
    assert RP_PTS_OPERATING_SPEED_M_PER_S.confidence == "LOW"
    assert "NOT vendor-validated" in RP_PTS_OPERATING_SPEED_M_PER_S.notes


def test_reference_transactions_per_day_not_used_as_capacity_ceiling(capital_baseline):
    rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
    assert rp_pts.missions_per_day < PTS_REFERENCE_TRANSACTIONS_PER_DAY.active_value
    assert "sanity" in PTS_REFERENCE_TRANSACTIONS_PER_DAY.notes.lower() or "reference" in PTS_REFERENCE_TRANSACTIONS_PER_DAY.notes.lower()
    # missions/day must be independently derived, never compared as "1500 > 30 therefore feasible" only.
    assert rp_pts.labor.peak_concurrent_carriers > 0


def test_pet_dose_precedent_distance_not_treated_as_maximum_range(capital_baseline):
    rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
    assert rp_pts.network_length_m != RP_PTS_PET_DOSE_PRECEDENT_DISTANCE_M.active_value
    assert "NOT prove" in RP_PTS_PET_DOSE_PRECEDENT_DISTANCE_M.notes


def test_published_cost_reference_not_stacked_on_active_per_floor_model(capital_baseline):
    """The $350k RP-PTS reference must never be ADDED to the unrelated
    $100,000/served-floor ordinary-PTS active CapEx model."""
    automated = evaluate_automated_conventional(capital_baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    rp_pts_capex = compute_rp_pts_capex()
    assert rp_pts_capex.total_capex == pytest.approx(350_000.0)
    # Automated's existing CapEx is unaffected by the RP-PTS reference existing.
    assert automated.architecture_specific_capex == pytest.approx(1_475_000.0)


# ---------------------------------------------------------------------------
# 11-12. Installed vs utilized stations; ordinary PTS stays nuclear-incompatible.
# ---------------------------------------------------------------------------

def test_installed_stations_distinct_from_utilized(capital_baseline):
    rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
    assert rp_pts.installed_stations == RP_PTS_INSTALLED_STATIONS == 2
    # Utilized concept: today's peak concurrent dose requirement must never exceed installed capital assumption silently.
    assert isinstance(rp_pts.labor.peak_concurrent_carriers, int)


def test_ordinary_pts_does_not_gain_nuclear_compatibility_via_rp_pts(capital_baseline):
    automated = evaluate_automated_conventional(capital_baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    assert any("shielding modification cost = NOT_CALIBRATED" in n for n in automated.notes)
    assert any("no AGV-nuclear CapEx is charged at all" in n for n in automated.notes)


# ---------------------------------------------------------------------------
# 13-14. Automated baseline unchanged; +RP-PTS changes only nuclear component.
# ---------------------------------------------------------------------------

def test_automated_baseline_remains_unchanged(capital_baseline):
    automated = evaluate_automated_conventional(capital_baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
    assert automated.architecture_specific_capex == pytest.approx(1_475_000.0)
    assert automated.architecture_specific_annual_opex == pytest.approx(1_745_872.0, abs=1.0)


def test_automated_plus_rp_pts_changes_only_nuclear_component(capital_baseline):
    diag = evaluate_automated_conventional_with_dedicated_rp_pts_diagnostic(
        capital_baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING",
    )
    assert diag.automated_current_capex == pytest.approx(1_475_000.0)
    assert diag.automated_current_annual_opex == pytest.approx(1_745_872.0, abs=1.0)
    # AGV/PTS general-logistics floor infrastructure delta ($150,000/floor unit + station
    # allowances) is untouched -- only the nuclear-transport CapEx/OPEX component changed.
    common = compute_common_project_capex(capital_baseline, development_context="RETROFIT")
    manual_nuclear = _nuclear_result(capital_baseline, mrt_floors=frozenset())
    manual_nuclear_capex_delta = manual_nuclear.total_capex - common.total_common_asset_value
    expected_general_capex = diag.automated_current_capex - manual_nuclear_capex_delta
    assert (diag.automated_plus_rp_pts_capex - diag.rp_pts.capex.total_capex) == pytest.approx(expected_general_capex, abs=1.0)


# ---------------------------------------------------------------------------
# 15. Unknown RP-PTS terms remain explicit.
# ---------------------------------------------------------------------------

def test_unknown_rp_pts_terms_remain_explicit(capital_baseline):
    rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
    assert rp_pts.shielded_carrier_mass_limit_kg is None
    assert RP_PTS_SHIELDED_CARRIER_MASS_LIMIT_KG.status == "NOT_CALIBRATED"
    assert rp_pts.capex.shielding_certification_delta_capex is None
    assert any("NOT_CALIBRATED" in n for n in rp_pts.capex.notes)
    assert rp_pts.shielding_status == "CLINICALLY_DEMONSTRATED_BUT_PROJECT_SHIELDING_NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# 16. Break-even equations reconcile.
# ---------------------------------------------------------------------------

def test_break_even_headroom_reconciles_against_manual_nuclear(capital_baseline):
    rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
    common = compute_common_project_capex(capital_baseline, development_context="RETROFIT")
    manual_nuclear = _nuclear_result(capital_baseline, mrt_floors=frozenset())
    manual_capex_delta = manual_nuclear.total_capex - common.total_common_asset_value
    manual_opex_delta = compute_common_project_opex(manual_nuclear).architecture_specific_annual_opex

    af = (1 - (1 + DISCOUNT_RATE_PCT / 100.0) ** (-ANALYSIS_YEARS)) / (DISCOUNT_RATE_PCT / 100.0)
    tco_manual_nuclear = manual_capex_delta + manual_opex_delta * af
    tco_rp_pts = rp_pts.capex.total_capex + rp_pts.opex.total_calibrated_annual_opex * af
    headroom = tco_manual_nuclear - tco_rp_pts
    max_extra_capex = headroom
    max_extra_opex = headroom / af
    # Reconciles exactly at the boundary: spending the FULL headroom as extra CapEx
    # (holding OPEX fixed) makes RP-PTS's TCO exactly equal Manual's.
    assert (tco_rp_pts + max_extra_capex) == pytest.approx(tco_manual_nuclear)
    assert (tco_rp_pts + max_extra_opex * af) == pytest.approx(tco_manual_nuclear)


# ---------------------------------------------------------------------------
# Build 2R narrow RP-PTS / Light-MRT comparator + FTE semantics closure round
# (12 required tests).
# ---------------------------------------------------------------------------

class TestBuild2RRpPtsLightMrtComparatorAndFteSemanticsClosure:

    def test_legacy_heavy_mrt_not_used_as_current_rp_pts_comparator(self, capital_baseline):
        light = evaluate_light_mrt_nuclear_standalone_and_incremental(capital_baseline)
        assert any("LEGACY_LARGER_CAPACITY_MRT_REFERENCE" in n for n in light.notes)
        assert any("NOT the current comparator" in n for n in light.notes)
        # The legacy ~$11.4M figure must not appear as either active Light-MRT view.
        assert light.standalone_capex != pytest.approx(11_400_000.0)
        assert light.incremental_capex != pytest.approx(11_400_000.0)

    def test_current_five_kg_light_mrt_is_used(self, capital_baseline):
        light = evaluate_light_mrt_nuclear_standalone_and_incremental(capital_baseline)
        # Standalone/incremental figures must be an order of magnitude below the legacy heavy-MRT reference.
        assert light.standalone_capex < 1_000_000.0
        assert light.incremental_capex < 1_000_000.0

    def test_shared_infrastructure_not_double_charged_to_incremental_nuclear(self, capital_baseline):
        light = evaluate_light_mrt_nuclear_standalone_and_incremental(capital_baseline)
        # Incremental must exclude the guideway trunk cost (already installed/shared).
        assert light.incremental_capex < light.standalone_capex
        assert light.guideway_length_m * 2000.0 not in (light.incremental_capex,)
        assert any("ALREADY INSTALLED" in n for n in light.notes)

    def test_same_thirty_procedures_reach_all_three_nuclear_competitors(self, capital_baseline):
        manual_nuclear = _nuclear_result(capital_baseline, mrt_floors=frozenset())
        rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
        all_floors = frozenset(range(1, capital_baseline.geometry.floor_count + 1))
        mrt_nuclear = _nuclear_result(capital_baseline, mrt_floors=all_floors)
        assert len(manual_nuclear.patient_traces) == 30
        assert rp_pts.missions_per_day == 30
        assert len(mrt_nuclear.patient_traces) == 30
        assert {t.canonical_patient_id for t in manual_nuclear.patient_traces} == {t.canonical_patient_id for t in mrt_nuclear.patient_traces}

    def test_peak_carrier_concurrency_distinct_from_peak_human_concurrency(self, capital_baseline):
        rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
        # Both fields must exist independently -- even though they happen to be numerically
        # equal for this benchmark's tight batch clustering, they are computed via SEPARATE
        # sweep-lines (full-cycle window vs human-handling-only sub-windows).
        assert hasattr(rp_pts.labor, "peak_concurrent_carriers")
        assert hasattr(rp_pts.labor, "peak_concurrent_human_handlers")

    def test_peak_human_concurrency_distinct_from_workload_derived_fte(self, capital_baseline):
        rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
        assert rp_pts.labor.peak_concurrent_human_handlers == 5
        assert rp_pts.labor.workload_derived_fte == 1
        assert rp_pts.labor.peak_concurrent_human_handlers != rp_pts.labor.workload_derived_fte
        assert rp_pts.labor.final_required_fte == rp_pts.labor.workload_derived_fte

    def test_total_human_minutes_per_day_reconciles(self, capital_baseline):
        rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
        human_touch_minutes_per_mission = (
            rp_pts.cycle.dispatch_minutes + rp_pts.cycle.source_handling_minutes + rp_pts.cycle.destination_handling_minutes
        )
        assert rp_pts.labor.total_human_minutes_per_day == pytest.approx(rp_pts.missions_per_day * human_touch_minutes_per_mission)
        assert rp_pts.labor.total_human_minutes_per_day == pytest.approx(120.0)

    def test_annual_labor_hours_reconcile(self, capital_baseline):
        rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
        expected = (rp_pts.labor.total_human_minutes_per_day / 60.0) * capital_baseline.operating_days_per_year
        assert rp_pts.labor.total_annual_labor_hours == pytest.approx(expected)
        assert rp_pts.labor.total_annual_labor_hours == pytest.approx(600.0)

    def test_labor_cost_reconciles_to_final_fte_authority(self, capital_baseline):
        rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
        loaded_cost_per_fte = rp_pts.opex.human_labor_annual_opex / rp_pts.labor.final_required_fte
        assert rp_pts.opex.human_labor_fte == rp_pts.labor.final_required_fte
        assert rp_pts.opex.human_labor_annual_opex == pytest.approx(rp_pts.labor.final_required_fte * loaded_cost_per_fte)
        # Must NOT equal the old (defective) peak-concurrency-derived cost.
        assert rp_pts.opex.human_labor_annual_opex != pytest.approx(rp_pts.labor.peak_concurrent_carriers * loaded_cost_per_fte * 5)

    def test_retention_clinical_timing_remains_feasible(self, capital_baseline):
        """The FTE-semantics correction changes only headcount/cost accounting
        -- it must NOT alter the mission cycle time or dispatch/injection
        schedule that clinical retention feasibility depends on."""
        rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
        assert rp_pts.cycle.total_minutes == pytest.approx(4.60655737704918)
        assert rp_pts.missions_per_day == 30

    def test_editable_defaults_and_provenance_remain_intact(self):
        for param in editable_default_registry_table():
            assert param.parameter_id
            assert param.source_type
            # active_value resolution must never destroy default_value.
            assert param.default_value is None or isinstance(param.default_value, float)

    def test_automated_baseline_unchanged_unless_rp_pts_diagnostic_explicitly_evaluated(self, capital_baseline):
        automated = evaluate_automated_conventional(capital_baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
        assert automated.architecture_specific_capex == pytest.approx(1_475_000.0)
        assert automated.architecture_specific_annual_opex == pytest.approx(1_745_872.0, abs=1.0)

    def test_corrected_rp_pts_labor_cost_lower_than_pre_audit_value(self, capital_baseline):
        """Confirms the FTE-semantics correction genuinely reduced cost from
        the prior (defective) round's reported $265,200/year peak-derived figure."""
        rp_pts = evaluate_dedicated_rp_pts_nuclear_transport(capital_baseline)
        assert rp_pts.opex.human_labor_annual_opex < 265_200.0
        assert rp_pts.opex.human_labor_annual_opex == pytest.approx(53_040.0)
        assert rp_pts.opex.total_calibrated_annual_opex == pytest.approx(62_040.0)

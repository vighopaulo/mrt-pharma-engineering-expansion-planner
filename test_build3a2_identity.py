"""Build 3A.2 — legacy candidate identity and transport-basis closure.

Engine-level focused proofs (no API/FastAPI dependency) for two confirmed
legacy-result semantic defects:

  D-I1  A zero-backbone winner from the legacy MRT investment search was reported
        as "MRT" even though no MRT system was selected. It must carry the explicit
        candidate identity NO_BUILD_BASELINE (distinct from the search pathway).

  D-T1  That zero-backbone winner was calculated on the Conventional 8.0-min
        transport basis, but the multibatch wrapper reported the MRT 3.0-min basis
        purely because the candidate originated from the MRT search. The reported
        transport basis must equal the basis actually used for retention/capacity.

Semantic principle: SEARCH PATHWAY (`pathway`) and SELECTED PHYSICAL CANDIDATE
IDENTITY (`candidate_identity`) are different concepts. An MRT investment search
may legitimately conclude that no MRT investment is needed.

These legacy identities (NO_BUILD_BASELINE / GENERIC_LEGACY_MRT /
GENERIC_LEGACY_CONVENTIONAL) are deliberately NOT the four-architecture doctrine
(MANUAL_CONVENTIONAL / AUTOMATED_CONVENTIONAL / HYBRID_MRT / MRT_DOMINANT).
"""

import math

import cyclotron_catalog as cc
from equal_budget import (
    maximize_conventional_capacity,
    maximize_mrt_capacity,
    run_equal_budget_multibatch_optimization,
)
from models import PlannerAssumptions, PlannerInputs

_HALF_LIFE_F18_MIN = 109.8


def _exact_case_inputs() -> PlannerInputs:
    """RETROFIT, current=30, target=45, budget=$35M, SUMITOMO_CYPRIS_MP_30 (uncalibrated)."""
    catalog = cc.load_cyclotron_catalog()
    instance = cc.create_facility_cyclotron_instance(
        catalog_model_id="SUMITOMO_CYPRIS_MP_30", existing_instances=()
    )
    fleet, _warnings = cc.build_fleet_from_instances(catalog=catalog, instances=(instance,))
    assert fleet is None  # CYPRIS MP-30 has no calibrated cycle/performance data
    return PlannerInputs(
        project_name="Capital Project — oncology-expansion-demo",
        current_patients_per_day=30.0,
        target_patients_per_day=45.0,
        maximum_expected_demand_per_day=45.0,
        current_scanners=2,
        current_injection_rooms=2,
        current_uptake_rooms=2,
        has_existing_cyclotron=fleet is not None,
        current_usable_doses_per_day=30.0,
        current_average_transport_min=8.0,
        mrt_transport_min=3.0,
        conventional_transport_min=8.0,
        existing_mrt_connectable_rooms=2,
        representative_radionuclide="F-18",
        representative_half_life_min=_HALF_LIFE_F18_MIN,
        selected_cyclotron_radionuclide="F-18",
        cyclotron_fleet=fleet,
    )


def _real_mrt_inputs() -> PlannerInputs:
    """A scenario that naturally selects a backbone-charged (GENERIC_LEGACY_MRT) winner.

    High demand + calibrated EOB capacity so MRT infrastructure is genuinely chosen.
    """
    return PlannerInputs(
        project_name="real-mrt",
        current_patients_per_day=60.0,
        target_patients_per_day=300.0,
        maximum_expected_demand_per_day=300.0,
        current_scanners=6,
        current_injection_rooms=6,
        current_uptake_rooms=6,
        has_existing_cyclotron=True,
        current_usable_doses_per_day=60.0,
        current_average_transport_min=20.0,
        mrt_transport_min=0.5,
        conventional_transport_min=20.0,
        existing_mrt_connectable_rooms=4,
        representative_radionuclide="F-18",
        representative_half_life_min=_HALF_LIFE_F18_MIN,
        selected_cyclotron_radionuclide="F-18",
        current_cyclotron_eob_capacity_mbq_per_day=500_000.0,
    )


# ---------------------------------------------------------------------------
# D-I1: candidate identity for the zero-backbone MRT-search winner
# ---------------------------------------------------------------------------


def test_1_zero_backbone_mrt_winner_is_no_build_baseline():
    base = maximize_mrt_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    assert base.backbone_charged is False
    assert base.candidate_identity == "NO_BUILD_BASELINE"


def test_2_zero_backbone_mrt_winner_is_not_generic_legacy_mrt():
    base = maximize_mrt_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    assert base.candidate_identity != "GENERIC_LEGACY_MRT"
    # search provenance is preserved separately
    assert base.pathway == "MRT"


# ---------------------------------------------------------------------------
# D-T1: transport basis of the zero-backbone winner
# ---------------------------------------------------------------------------


def test_3_zero_backbone_reported_transport_is_conventional_basis():
    result = run_equal_budget_multibatch_optimization(
        _exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, explicit_budget=35_000_000.0
    )
    mrt = result.mrt
    assert mrt.candidate_identity == "NO_BUILD_BASELINE"
    # conventional_transport_min for this case is 8.0 (not the MRT 3.0)
    assert mrt.transport_minutes == 8.0


def test_4_reported_transport_agrees_with_retained_activity():
    result = run_equal_budget_multibatch_optimization(
        _exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, explicit_budget=35_000_000.0
    )
    mrt = result.mrt
    expected_retained_pct = 2 ** (-mrt.transport_minutes / _HALF_LIFE_F18_MIN) * 100.0
    assert math.isclose(mrt.retained_activity_pct, expected_retained_pct, rel_tol=0.0, abs_tol=1e-6)


# ---------------------------------------------------------------------------
# Real MRT control: backbone-charged winner
# ---------------------------------------------------------------------------


def test_5_backbone_charged_winner_is_generic_legacy_mrt():
    base = maximize_mrt_capacity(_real_mrt_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 30_000_000.0)
    assert base.backbone_charged is True
    assert base.candidate_identity == "GENERIC_LEGACY_MRT"
    # genuine MRT infrastructure CapEx is charged
    assert base.capex_used > 0.0
    assert base.guideway_segments > 0
    assert base.endpoints > 0


def test_6_backbone_charged_reported_transport_is_mrt_basis():
    base = maximize_mrt_capacity(_real_mrt_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 30_000_000.0)
    # inputs.mrt_transport_min = 0.5 for the real MRT scenario
    assert base.transport_minutes_basis == 0.5


# ---------------------------------------------------------------------------
# Conventional identity
# ---------------------------------------------------------------------------


def test_7_conventional_identity_is_generic_legacy_conventional():
    base = maximize_conventional_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    assert base.candidate_identity == "GENERIC_LEGACY_CONVENTIONAL"
    # legacy conventional must NOT be mislabeled as the four-architecture Manual identity
    assert base.candidate_identity != "MANUAL_CONVENTIONAL"


# ---------------------------------------------------------------------------
# Build 3A production correction must remain intact
# ---------------------------------------------------------------------------


def test_8_build3a_uncalibrated_production_correction_intact():
    result = run_equal_budget_multibatch_optimization(
        _exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, explicit_budget=35_000_000.0
    )
    mrt = result.mrt
    assert mrt.production_expansion_pct == 0.0
    assert mrt.production_capacity_status == "not_calibrated"
    assert mrt.production_feasibility_qualified is False
    assert "production_after_decay" not in mrt.binding_constraint


def test_9_target_bounded_ranking_intact():
    base = maximize_mrt_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    # served demand satisfied without overbuilding
    assert base.revenue_generating_throughput_per_day == 45.0
    assert base.achieved_capacity_per_day > 45.0
    assert base.capex_used < 6_000_000.0


def test_10_no_build_result_fabricates_no_mrt_carrier_capex():
    base = maximize_mrt_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    # NO_BUILD_BASELINE: zero MRT-specific CapEx of any kind, including any carrier line.
    assert base.capex_used == 0.0
    assert base.guideway_segments == 0
    assert base.endpoints == 0
    for item in base.capex_ledger:
        component = str(item.get("component", "")).lower()
        if "carrier" in component:
            assert float(item["subtotal"]) == 0.0


def test_11_conventional_exact_case_unchanged_except_identity():
    base = maximize_conventional_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    # corrected conventional exact-case result: ~52.46/day, $25k (one uptake room), 8-min basis
    assert math.isclose(base.achieved_capacity_per_day, 52.45714285714286, rel_tol=0.0, abs_tol=1e-6)
    assert base.revenue_generating_throughput_per_day == 45.0
    assert base.transport_minutes_basis == 8.0
    assert base.binding_constraint == "scanner"
    assert base.production_capacity_status == "not_calibrated"
    assert base.production_feasibility_qualified is False

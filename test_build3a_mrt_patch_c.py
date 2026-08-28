"""Build 3A — Patch C focused proof for maximize_mrt_capacity.

Verifies (engine-level, no API/FastAPI dependency) that when physical cyclotron
EOB capacity is NOT_CALIBRATED for the exact live case (RETROFIT, current=30,
target=45, budget=$35M, SUMITOMO_CYPRIS_MP_30):

  - legacy 10% production blocks do not become physical capacity;
  - production_expansion_pct == 0;
  - no synthetic production-block CapEx is charged;
  - no cyclotron purchase/install is triggered solely by legacy prod_blocks;
  - production_after_decay is not a calibrated physical binding constraint;
  - production_capacity_status == "not_calibrated";
  - production_feasibility_qualified is False;
  - target-bounded ranking does not overbuild beyond served demand;
  - actual achieved capacity is preserved (uncapped) for reporting;
  - internal float("inf") is never returned/stored on the result object.
"""

import math

import cyclotron_catalog as cc
from equal_budget import maximize_mrt_capacity, run_equal_budget_multibatch_optimization
from models import PlannerAssumptions, PlannerInputs

_HALF_LIFE_F18_MIN = 109.8


def _exact_case_inputs() -> PlannerInputs:
    catalog = cc.load_cyclotron_catalog()
    instance = cc.create_facility_cyclotron_instance(
        catalog_model_id="SUMITOMO_CYPRIS_MP_30", existing_instances=()
    )
    fleet, _warnings = cc.build_fleet_from_instances(catalog=catalog, instances=(instance,))
    # CYPRIS MP-30 has no calibrated cycle/performance data -> fleet is None.
    assert fleet is None
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


def test_mrt_uncalibrated_no_legacy_production_blocks():
    base = maximize_mrt_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    assert base.production_expansion_pct == 0.0


def test_mrt_uncalibrated_no_production_block_capex():
    base = maximize_mrt_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    prod_block_capex = 0.0
    cyclotron_capex = 0.0
    for item in base.capex_ledger:
        component = str(item.get("component", ""))
        if "Production expansion" in component:
            prod_block_capex = float(item["subtotal"])
        if "Cyclotron" in component:
            cyclotron_capex += float(item["subtotal"])
    assert prod_block_capex == 0.0
    assert cyclotron_capex == 0.0


def test_mrt_uncalibrated_production_status_and_qualification():
    base = maximize_mrt_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    assert base.production_capacity_status == "not_calibrated"
    assert base.production_feasibility_qualified is False


def test_mrt_uncalibrated_production_after_decay_not_binding():
    base = maximize_mrt_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    assert "production_after_decay" not in base.binding_constraint


def test_mrt_target_bounded_ranking_does_not_overbuild():
    base = maximize_mrt_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    # Once served demand (45) is satisfied, the optimizer must not spend budget to
    # maximize unused capacity. The pre-correction defect selected 13 scanners / $33M.
    assert base.additional_scanners <= 1
    assert base.capex_used < 6_000_000.0  # nowhere near the old ~$33M overbuild


def test_mrt_achieved_capacity_preserved_uncapped():
    base = maximize_mrt_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    # Two existing scanners already yield ~52.46/day; achieved must NOT be capped at 45.
    assert base.achieved_capacity_per_day > 45.0
    assert base.revenue_generating_throughput_per_day == 45.0
    headroom = base.achieved_capacity_per_day - 45.0
    assert headroom > 0.0


def test_mrt_no_infinity_stored_on_result():
    base = maximize_mrt_capacity(_exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, 35_000_000.0)
    # achieved / capacity / reserve must be finite (inf is internal-only).
    assert math.isfinite(base.achieved_capacity_per_day)
    assert math.isfinite(base.reserve_capacity_above_expected_demand_per_day)
    assert math.isfinite(base.gross_required_doses_per_day)
    assert math.isfinite(base.capex_used)


def test_mrt_multibatch_propagates_production_status():
    result = run_equal_budget_multibatch_optimization(
        _exact_case_inputs(), PlannerAssumptions(), _HALF_LIFE_F18_MIN, explicit_budget=35_000_000.0
    )
    assert result.mrt.production_capacity_status == "not_calibrated"
    assert result.mrt.production_feasibility_qualified is False
    assert result.mrt.production_expansion_pct == 0.0

"""
Validation scenarios required by Section 33 of the spec:
  Scenario A: Conventional should win
  Scenario B: MRT should win
  Scenario C: Neither should be feasible

Run with:  python3 test_model.py
"""

from model import Inputs, run_comparison

BASE = dict(
    current_patients=50,
    current_scanners=2,
    operating_hours=18,
    scanner_cycle_min=35,
    scanner_availability=0.85,
    current_injection_rooms=6,
    current_uptake_rooms=6,
    patients_per_dedicated_room=10,
    current_doses_per_batch=60,
    max_additional_mrt_dedicated_rooms=6,
    supporting_mrt_destinations=4,
    capex_per_scanner=1_800_000,
    capex_per_dedicated_room=150_000,
    capex_mrt_core=2_000_000,
    capex_per_endpoint=15_000,
    max_capex_budget=50_000_000,
    net_contribution_per_patient=650,
    opex_base_conventional=250_000,
    opex_base_mrt=250_000,
    opex_per_additional_scanner=250_000,
    opex_per_additional_dedicated_room=120_000,
    opex_mrt_maintenance=400_000,
    opex_per_endpoint=3_000,
    annual_cost_per_extra_daily_batch=180_000,
    operating_days_per_year=250,
    analysis_period_years=10,
    discount_rate=0.08,
    production_search_increment=5,
)


def scenario_a():
    """Conventional should win: small target growth, short conventional
    transport (little decay penalty), cheap conventional upgrade, expensive
    MRT core, very few MRT inpatient rooms available."""
    inp = Inputs(
        target_patients=65,                 # small growth from 50
        conventional_delivery_time=3,       # short -> little decay benefit for MRT
        mrt_delivery_time=1,
        isotope_half_life=110,
        max_mrt_batches_per_day=3,
        max_mrt_inpatient_rooms=2,           # very limited
        patients_per_mrt_inpatient_room=1,
        capex_mrt_upgrade_per_10pct=400_000,
        capex_conv_upgrade_per_10pct=150_000,  # cheap conventional upgrade
        **BASE_OVERRIDE(capex_mrt_core=9_000_000),  # expensive MRT core
    )
    return run_comparison(inp)


def BASE_OVERRIDE(**kwargs):
    d = dict(BASE)
    d.update(kwargs)
    return d


def scenario_b():
    """MRT should win: large target growth, expensive conventional
    production expansion, long conventional transport (big decay penalty),
    fast MRT delivery, many batches / inpatient rooms available, expensive
    new centralized room construction."""
    inp = Inputs(
        target_patients=220,                  # large growth from 50
        conventional_delivery_time=45,        # long -> heavy decay loss
        mrt_delivery_time=4,                  # fast
        isotope_half_life=110,                # ~2h half life (e.g. F-18-like)
        max_mrt_batches_per_day=4,
        max_mrt_inpatient_rooms=200,
        patients_per_mrt_inpatient_room=1,
        capex_mrt_upgrade_per_10pct=400_000,
        capex_conv_upgrade_per_10pct=900_000,  # expensive conventional upgrade
        **BASE_OVERRIDE(
            capex_per_dedicated_room=400_000,   # expensive new centralized rooms
            capex_mrt_core=2_500_000,
            opex_mrt_maintenance=350_000,
            opex_per_endpoint=2_000,
            max_capex_budget=90_000_000,
        ),
    )
    return run_comparison(inp)


def scenario_c():
    """Neither feasible: target far too high for available doses/scanners/
    rooms/budget."""
    inp = Inputs(
        target_patients=5000,
        conventional_delivery_time=10,
        mrt_delivery_time=3,
        isotope_half_life=110,
        max_mrt_batches_per_day=2,
        max_mrt_inpatient_rooms=3,
        patients_per_mrt_inpatient_room=1,
        capex_mrt_upgrade_per_10pct=400_000,
        capex_conv_upgrade_per_10pct=400_000,
        **BASE_OVERRIDE(
            max_additional_mrt_dedicated_rooms=1,
            max_capex_budget=2_000_000,   # far too small
            current_scanners=1,
        ),
    )
    return run_comparison(inp)


if __name__ == "__main__":
    a = scenario_a()
    print("=== Scenario A (expect: conventional wins) ===")
    print("winner:", a.winner,
          "| conv feasible:", a.conventional.feasible, "npv:", round(a.conventional.npv, 0),
          "| mrt feasible:", a.mrt.feasible,
          "npv:" if a.mrt.feasible else "reasons:",
          round(a.mrt.npv, 0) if a.mrt.feasible else a.mrt.infeasible_reasons)
    assert a.winner == "conventional", f"Scenario A FAILED: winner was {a.winner}"
    print("PASSED\n")

    b = scenario_b()
    print("=== Scenario B (expect: MRT wins) ===")
    print("winner:", b.winner,
          "| conv feasible:", b.conventional.feasible, "npv:", round(b.conventional.npv, 0),
          "| mrt feasible:", b.mrt.feasible,
          "npv:" if b.mrt.feasible else "reasons:",
          round(b.mrt.npv, 0) if b.mrt.feasible else b.mrt.infeasible_reasons)
    if b.mrt.feasible:
        print("  MRT U_m:", b.mrt.U_m, "B_m:", b.mrt.B_m, "R_a:", b.mrt.R_a, "R_m:", b.mrt.R_m)
    assert b.winner == "mrt", f"Scenario B FAILED: winner was {b.winner}"
    print("PASSED\n")

    c = scenario_c()
    print("=== Scenario C (expect: neither feasible) ===")
    print("winner:", c.winner,
          "| conv feasible:", c.conventional.feasible, "reasons:", c.conventional.infeasible_reasons,
          "| mrt feasible:", c.mrt.feasible, "reasons:", c.mrt.infeasible_reasons,
          "| mrt diagnostic best served:", c.mrt.diagnostic_best_served,
          "binding:", c.mrt.diagnostic_binding_constraint)
    assert c.winner == "neither", f"Scenario C FAILED: winner was {c.winner}"
    print("PASSED\n")

    print("ALL SCENARIOS PASSED")

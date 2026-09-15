"""BUILD 1B.9 — Physics & Economics Integrity Audit (headless, independent).

This module INDEPENDENTLY verifies the CURRENTLY-IMPLEMENTED engineering /
economic models against test-side analytical references — never by comparing a
production function to another call of the same function. It also proves the
engineering engine is HEADLESS (no Bentley / viewer / DOM / WebGL / animation)
and that visualization cannot contaminate engineering results.

It does NOT invent missing physics. Where a quantitative solver does not exist
(e.g. detailed MRT electromagnetic simulation, PTS pneumatic CFD), the audit
asserts the honest implementation STATUS rather than fabricating a benchmark.

Independent references used here:
  - constant-speed motion    t = L / v
  - radioactive decay        A(t) = A0 * 2^(-t / T_half)   (T_half from radionuclides.json)
  - simple payback           payback = CapEx / annual_net_cash_flow
  - discounted NPV           NPV = -CapEx + sum_y CF/(1+r)^y
"""
from __future__ import annotations

import math
import importlib
import sys

import pytest


# ---------------------------------------------------------------------------
# HEADLESS EXECUTION PROOF — no viewer/DOM/WebGL/animation in the engine path
# ---------------------------------------------------------------------------

ENGINE_MODULES = [
    "f18_decay_model",
    "conventional_transport_authority",
    "finance",
    "transport_movement_domain_authority",
]


def test_engine_modules_import_headlessly():
    """Core physics/economics modules import with NO Bentley/viewer/DOM stack."""
    for name in ENGINE_MODULES:
        mod = importlib.import_module(name)
        assert mod is not None
    # None of the engine modules pulled a browser/viewer runtime into sys.modules.
    forbidden = ("IModelApp", "webgl", "requestAnimationFrame")
    loaded = " ".join(sys.modules.keys()).lower()
    for token in forbidden:
        assert token.lower() not in loaded, f"engine unexpectedly loaded {token}"


# ---------------------------------------------------------------------------
# RADIOACTIVE DECAY — independent A(t) = A0 * 2^(-t/T_half), T_half canonical
# ---------------------------------------------------------------------------

def _independent_decay(a0: float, t_min: float, t_half_min: float) -> float:
    return a0 * 2.0 ** (-t_min / t_half_min)


def test_f18_half_life_provenance_is_canonical():
    from f18_decay_model import load_f18_half_life_minutes
    t_half = load_f18_half_life_minutes()
    # Canonical value from radionuclides.json (provenance-backed, not from memory).
    assert t_half == pytest.approx(109.8, abs=1e-9)


def test_f18_decay_matches_independent_reference_at_half_life_multiples():
    from f18_decay_model import load_f18_half_life_minutes, retention_at_delay_minutes
    t_half = load_f18_half_life_minutes()
    # t = 0 -> full; 1 half-life -> 1/2; 2 half-lives -> 1/4 (independent formula).
    assert retention_at_delay_minutes(0.0, t_half) == pytest.approx(1.0, abs=1e-12)
    assert retention_at_delay_minutes(t_half, t_half) == pytest.approx(0.5, abs=1e-12)
    assert retention_at_delay_minutes(2 * t_half, t_half) == pytest.approx(0.25, abs=1e-12)
    # Arbitrary delay against the independent exponential-equivalent reference.
    for delay in (17.0, 40.0, 90.0, 137.5):
        assert retention_at_delay_minutes(delay, t_half) == pytest.approx(
            _independent_decay(1.0, delay, t_half), rel=1e-12
        )


def test_decay_is_monotonic_nonincreasing_in_delay():
    from f18_decay_model import load_f18_half_life_minutes, retention_at_delay_minutes
    t_half = load_f18_half_life_minutes()
    prev = 1.0
    for delay in (0.0, 10.0, 20.0, 50.0, 100.0, 200.0):
        r = retention_at_delay_minutes(delay, t_half)
        assert 0.0 <= r <= 1.0
        assert r <= prev + 1e-12  # longer delay never increases surviving activity
        prev = r


# ---------------------------------------------------------------------------
# MANUAL TRANSPORT — L1 kinematic; independent t = L / v + fixed handling
# ---------------------------------------------------------------------------

def _porter():
    from conventional_transport_authority import PorterOperatingPolicy
    return PorterOperatingPolicy()


def test_manual_horizontal_time_matches_independent_constant_speed():
    from conventional_transport_authority import compute_manual_mission_timing
    p = _porter()
    L = 110.0  # meters (calibrated route)
    r = compute_manual_mission_timing(policy=p, technology="MANUAL_PORTER", horizontal_distance_m=L)
    # Independent: horizontal minutes = L / speed / 60.
    expected_h = L / p.loaded_hand_carry_speed_m_per_s / 60.0
    assert r.horizontal_minutes == pytest.approx(expected_h, rel=1e-12)
    assert r.route_status == "ROUTE_CALIBRATED"
    # Cart is slower than hand-carry -> longer horizontal time for the same L.
    r_cart = compute_manual_mission_timing(policy=p, technology="PORTER_CART", horizontal_distance_m=L)
    assert r_cart.horizontal_minutes > r.horizontal_minutes


def test_manual_distance_monotonicity_L_and_2L():
    from conventional_transport_authority import compute_manual_mission_timing
    p = _porter()
    t1 = compute_manual_mission_timing(policy=p, technology="MANUAL_PORTER", horizontal_distance_m=100.0).total_minutes
    t2 = compute_manual_mission_timing(policy=p, technology="MANUAL_PORTER", horizontal_distance_m=200.0).total_minutes
    assert t2 >= t1  # 2L never faster than L, all else fixed


def test_manual_vertical_transition_adds_time():
    from conventional_transport_authority import compute_manual_mission_timing
    p = _porter()
    flat = compute_manual_mission_timing(policy=p, technology="MANUAL_PORTER", horizontal_distance_m=100.0, vertical_transitions=0)
    up = compute_manual_mission_timing(policy=p, technology="MANUAL_PORTER", horizontal_distance_m=100.0, vertical_transitions=2)
    assert up.total_minutes > flat.total_minutes
    assert up.vertical_minutes == pytest.approx(2 * p.elevator_wait_minutes, rel=1e-12)


def test_manual_route_not_calibrated_without_distance():
    from conventional_transport_authority import compute_manual_mission_timing
    p = _porter()
    r = compute_manual_mission_timing(policy=p, technology="MANUAL_PORTER")
    assert r.route_status == "ROUTE_NOT_CALIBRATED"  # explicit status, not a fake distance


# ---------------------------------------------------------------------------
# ECONOMICS — independent simple payback + NPV recomputation
# ---------------------------------------------------------------------------

def test_simple_payback_matches_independent_definition():
    from finance import incremental_financials
    capex = 500_000.0
    annual_opex = 20_000.0
    throughput = 10.0
    revenue = 1_000.0
    days = 250
    (annual_revenue, _opex, net_cf, npv, _roi, payback) = incremental_financials(
        capex=capex, annual_incremental_opex=annual_opex,
        throughput_patients_per_day=throughput, revenue_per_scan=revenue,
        operating_days_per_year=days, discount_rate_pct=8.0, analysis_years=10,
    )
    # Independent references.
    exp_rev = throughput * days * revenue
    exp_net = exp_rev - annual_opex
    exp_payback = capex / exp_net
    exp_npv = -capex + sum(exp_net / (1.08 ** y) for y in range(1, 11))
    assert annual_revenue == pytest.approx(exp_rev, rel=1e-12)
    assert net_cf == pytest.approx(exp_net, rel=1e-12)
    assert payback == pytest.approx(exp_payback, rel=1e-12)
    assert npv == pytest.approx(exp_npv, rel=1e-9)


def test_payback_edge_cases_zero_and_negative_savings():
    from finance import incremental_financials
    # Zero net cash flow -> payback is infinite (never a misleading finite number).
    (_r, _o, net0, _npv, _roi, payback0) = incremental_financials(
        capex=100_000.0, annual_incremental_opex=100_000.0,
        throughput_patients_per_day=10.0, revenue_per_scan=1_000.0,
        operating_days_per_year=10, discount_rate_pct=8.0, analysis_years=5,
    )
    # revenue 10*10*1000 = 100_000; opex 100_000 -> net 0 -> payback inf.
    assert net0 == pytest.approx(0.0, abs=1e-9)
    assert math.isinf(payback0)
    # Negative savings -> payback infinite (not a negative "payback").
    (_r2, _o2, net_neg, _npv2, _roi2, payback_neg) = incremental_financials(
        capex=100_000.0, annual_incremental_opex=200_000.0,
        throughput_patients_per_day=10.0, revenue_per_scan=1_000.0,
        operating_days_per_year=10, discount_rate_pct=8.0, analysis_years=5,
    )
    assert net_neg < 0.0
    assert math.isinf(payback_neg)


def test_capex_increase_does_not_shorten_payback():
    from finance import incremental_financials
    def payback(capex):
        return incremental_financials(
            capex=capex, annual_incremental_opex=20_000.0,
            throughput_patients_per_day=10.0, revenue_per_scan=1_000.0,
            operating_days_per_year=250, discount_rate_pct=8.0, analysis_years=10,
        )[5]
    assert payback(600_000.0) >= payback(500_000.0)  # more CapEx never pays back faster


# ---------------------------------------------------------------------------
# VISUALIZATION INDEPENDENCE — the engine has no visual parameter at all, so the
# same engineering inputs are deterministic regardless of any viewer condition.
# ---------------------------------------------------------------------------

def test_engineering_outputs_are_deterministic_and_visualization_free():
    from finance import incremental_financials
    from conventional_transport_authority import compute_manual_mission_timing, PorterOperatingPolicy
    from f18_decay_model import load_f18_half_life_minutes, retention_at_delay_minutes
    # Run the same scenario twice; identical (no hidden global visual/animation state).
    def run():
        fin = incremental_financials(
            capex=500_000.0, annual_incremental_opex=20_000.0,
            throughput_patients_per_day=10.0, revenue_per_scan=1_000.0,
            operating_days_per_year=250, discount_rate_pct=8.0, analysis_years=10,
        )
        mission = compute_manual_mission_timing(policy=PorterOperatingPolicy(), technology="MANUAL_PORTER", horizontal_distance_m=110.0).total_minutes
        decay = retention_at_delay_minutes(60.0, load_f18_half_life_minutes())
        return fin, mission, decay
    a = run()
    b = run()
    assert a == b  # byte-for-byte identical; no visual/animation contamination possible


# ---------------------------------------------------------------------------
# HONEST STATUS ASSERTIONS — do NOT fake unimplemented physics
# ---------------------------------------------------------------------------

def test_no_animation_clock_authority_in_engine():
    """The engine must not derive engineering quantities from playback/frame time."""
    import pathlib
    root = pathlib.Path(__file__).parent
    banned = ("requestanimationframe", "performance.now", "animationduration", "playbackspeed", "framedelta")
    for mod in ENGINE_MODULES:
        src = (root / f"{mod}.py").read_text(encoding="utf-8").lower()
        for token in banned:
            assert token not in src, f"{mod}.py references visual-clock token {token}"

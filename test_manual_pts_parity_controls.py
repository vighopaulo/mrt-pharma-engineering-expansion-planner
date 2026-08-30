"""KIRO Super-Build 1: deterministic Manual + PTS parity controls.

These lock the Manual and PTS physics/staffing/CapEx/OPEX arithmetic through
the EXISTING conventional_transport_authority owner (Sec 69-70 control sets),
plus the Super-Build parity views. No new physics is introduced; these are
deterministic invariants over the established authority."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

import conventional_transport_authority as cta
import transport_parity_view as view

DAY0 = datetime(2026, 2, 2, 8, 0, 0)


def _missions(n: int, spacing_minutes: float, stream: str = "SPECIMEN_BLOOD"):
    out = []
    for i in range(n):
        dep = DAY0 + timedelta(minutes=i * spacing_minutes)
        out.append(cta.TransportMission(
            mission_id=f"M-{i:03d}", load_id=f"L-{i:03d}", transport_mode="MANUAL_PORTER",
            origin="RADIOPHARMACY", destination="WARD", departure_datetime=dep,
            arrival_datetime=dep + timedelta(minutes=10), patient_ids=(f"P-{i:03d}",),
            duration_minutes=10.0, resource_id="PORTER",
        ))
    return tuple(out)


# ===========================================================================
# Manual physics (Sec 18/69)
# ===========================================================================
class TestManualPhysics:
    def test_calibrated_route_uses_distance(self):
        p = cta.PorterOperatingPolicy()
        t = cta.compute_manual_mission_timing(policy=p, technology="MANUAL_PORTER", horizontal_distance_m=110.0)
        assert t.route_status == "ROUTE_CALIBRATED"
        assert t.horizontal_minutes == pytest.approx(110.0 / p.loaded_hand_carry_speed_m_per_s / 60.0)

    def test_cart_slower_than_hand(self):
        p = cta.PorterOperatingPolicy()
        hand = cta.compute_manual_mission_timing(policy=p, technology="MANUAL_PORTER", horizontal_distance_m=110.0)
        cart = cta.compute_manual_mission_timing(policy=p, technology="PORTER_CART", horizontal_distance_m=110.0)
        assert cart.horizontal_minutes > hand.horizontal_minutes  # 0.9 < 1.1 m/s

    def test_uncalibrated_route_flagged(self):
        t = cta.compute_manual_mission_timing(policy=cta.PorterOperatingPolicy(), technology="MANUAL_PORTER")
        assert t.route_status == "ROUTE_NOT_CALIBRATED"

    def test_symmetric_return_included(self):
        t = cta.compute_manual_mission_timing(policy=cta.PorterOperatingPolicy(), technology="MANUAL_PORTER", horizontal_distance_m=110.0)
        assert t.return_minutes == pytest.approx(t.horizontal_minutes)

    def test_elevator_adds_vertical(self):
        p = cta.PorterOperatingPolicy()
        t0 = cta.compute_manual_mission_timing(policy=p, technology="MANUAL_PORTER", horizontal_distance_m=110.0, vertical_transitions=0)
        t1 = cta.compute_manual_mission_timing(policy=p, technology="MANUAL_PORTER", horizontal_distance_m=110.0, vertical_transitions=1)
        assert t1.vertical_minutes == pytest.approx(p.elevator_wait_minutes)
        assert t1.total_minutes > t0.total_minutes


# ===========================================================================
# Manual staffing / FTE / overtime (Sec 19/69)
# ===========================================================================
class TestManualStaffing:
    def test_empty_zero(self):
        r = cta.compute_porter_resource_requirement(missions=(), mission_minutes=10.0, policy=cta.PorterOperatingPolicy(), operating_days_per_year=300)
        assert r.required_fte == 0.0 and r.annual_labor_opex == 0.0

    def test_fte_never_missions_equals_porters(self):
        # 20 well-spaced missions do NOT require 20 porters (peak concurrency low).
        r = cta.compute_porter_resource_requirement(missions=_missions(20, 30.0), mission_minutes=10.0, policy=cta.PorterOperatingPolicy(), operating_days_per_year=300)
        assert r.required_fte < 20

    def test_peak_concurrency_drives_fte(self):
        # 5 simultaneous missions (spacing 0) => peak concurrency 5.
        r = cta.compute_porter_resource_requirement(missions=_missions(5, 0.0), mission_minutes=10.0, policy=cta.PorterOperatingPolicy(), operating_days_per_year=300)
        assert r.peak_concurrent_porters == 5
        assert r.required_fte >= 5

    def test_annual_labor_opex_arithmetic(self):
        p = cta.PorterOperatingPolicy()
        r = cta.compute_porter_resource_requirement(missions=_missions(5, 0.0), mission_minutes=10.0, policy=p, operating_days_per_year=300)
        loaded_per_fte = p.base_wage_per_hour * p.loaded_employer_cost_multiplier * p.shift_hours * 300
        assert r.annual_labor_opex == pytest.approx(r.required_fte * loaded_per_fte)

    def test_labor_hours_scale_with_missions(self):
        p = cta.PorterOperatingPolicy()
        r = cta.compute_porter_resource_requirement(missions=_missions(10, 30.0), mission_minutes=12.0, policy=p, operating_days_per_year=300)
        assert r.total_labor_hours == pytest.approx(10 * 12.0 / 60.0)


# ===========================================================================
# Manual CapEx (Sec 20)
# ===========================================================================
class TestManualCapex:
    def test_existing_cart_zero_capex(self):
        assert cta.cart_new_study_capex(cta.DEFAULT_LINEN_CART, study_scope="CAPITAL_PLANNING") == 0.0  # EXISTING

    def test_proposed_cart_capex(self):
        import dataclasses
        proposed = dataclasses.replace(cta.DEFAULT_LINEN_CART, asset_status="PROPOSED")
        assert cta.cart_new_study_capex(proposed, study_scope="CAPITAL_PLANNING") == cta.DEFAULT_LINEN_CART.purchase_capex

    def test_operational_only_zero(self):
        import dataclasses
        proposed = dataclasses.replace(cta.DEFAULT_LINEN_CART, asset_status="PROPOSED")
        assert cta.cart_new_study_capex(proposed, study_scope="OPERATIONAL_ONLY") == 0.0


# ===========================================================================
# Manual parity view (Sec 22)
# ===========================================================================
class TestManualParityView:
    def test_view_exposes_required_outputs(self):
        v = view.manual_parity_view(policy=cta.PorterOperatingPolicy(), stream="SPECIMEN_BLOOD", mission_minutes=15.0, required_fte=2.0, annual_labor_opex=200_000.0)
        assert v.route_time_minutes == 15.0
        assert v.known_annual_opex_usd >= 200_000.0
        assert v.total_opex_status == "KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED"

    def test_view_with_cart_adds_maintenance(self):
        base = view.manual_parity_view(policy=cta.PorterOperatingPolicy(), stream="CLEAN_LINEN", mission_minutes=15.0, required_fte=1.0, annual_labor_opex=100_000.0)
        with_cart = view.manual_parity_view(policy=cta.PorterOperatingPolicy(), stream="CLEAN_LINEN", mission_minutes=15.0, required_fte=1.0, annual_labor_opex=100_000.0, cart=cta.DEFAULT_LINEN_CART)
        assert with_cart.known_annual_opex_usd > base.known_annual_opex_usd

    def test_radiation_exposure_unknown_flagged(self):
        v = view.manual_parity_view(policy=cta.PorterOperatingPolicy(), stream="SPECIMEN_BLOOD", mission_minutes=15.0, required_fte=1.0, annual_labor_opex=100_000.0)
        assert any("exposure" in u.lower() for u in v.unknown_opex_components)


# ===========================================================================
# PTS capacity / route / CapEx / OPEX (Sec 24-35/70)
# ===========================================================================
class TestPts:
    def test_station_count_zero_workload(self):
        n = cta.pts_required_station_count(missions=(), mission_minutes=2.5, network=cta.DEFAULT_PTS_NETWORK, operating_hours_per_day=20.0, operating_days_per_year=300)
        assert n == 0

    def test_station_count_scales_with_concurrency(self):
        low = cta.pts_required_station_count(missions=_missions(4, 30.0), mission_minutes=2.5, network=cta.DEFAULT_PTS_NETWORK, operating_hours_per_day=20.0, operating_days_per_year=300)
        high = cta.pts_required_station_count(missions=_missions(6, 0.0), mission_minutes=2.5, network=cta.DEFAULT_PTS_NETWORK, operating_hours_per_day=20.0, operating_days_per_year=300)
        assert high >= low

    def test_capacity_not_infinite(self):
        n = cta.pts_required_station_count(missions=_missions(10, 0.0), mission_minutes=2.5, network=cta.DEFAULT_PTS_NETWORK, operating_hours_per_day=20.0, operating_days_per_year=300)
        assert n >= 1  # finite, workload-derived

    def test_pts_capex_proposed(self):
        import dataclasses
        net = dataclasses.replace(cta.DEFAULT_PTS_NETWORK, asset_status="PROPOSED")
        capex = cta.pts_new_study_capex(net, study_scope="CAPITAL_PLANNING")
        expected = net.station_count * net.station_capex_per_unit + (net.network_length_m * net.network_capex_per_m)
        assert capex == pytest.approx(expected)

    def test_pts_capex_existing_zero(self):
        assert cta.pts_new_study_capex(cta.DEFAULT_PTS_NETWORK, study_scope="CAPITAL_PLANNING") == 0.0

    def test_pts_opex_includes_residual_labor(self):
        opex = cta.pts_annual_opex(cta.DEFAULT_PTS_NETWORK, loaded_annual_cost_per_fte=70_000.0)
        expected = cta.DEFAULT_PTS_NETWORK.annual_maintenance_opex + cta.DEFAULT_PTS_NETWORK.annual_energy_opex + cta.DEFAULT_PTS_NETWORK.residual_labor_fte * 70_000.0
        assert opex == pytest.approx(expected)

    def test_pts_profile_standard_preserves_active_network(self):
        assert view.PTS_PROFILE_STANDARD_110MM.network is cta.DEFAULT_PTS_NETWORK

    def test_pts_profile_large_bigger_capsule(self):
        assert view.PTS_PROFILE_LARGE_160MM.network.capsule_payload_kg > cta.DEFAULT_PTS_NETWORK.capsule_payload_kg

    def test_pts_parity_route_time_from_network(self):
        v = view.pts_parity_view(profile=view.PTS_PROFILE_STANDARD_110MM, stream="SPECIMEN_BLOOD", station_count=6, loaded_annual_cost_per_fte=70_000.0)
        net = cta.DEFAULT_PTS_NETWORK
        expected = net.dispatch_minutes + net.network_length_m / net.speed_m_per_s / 60.0 + net.station_handling_minutes
        assert v.route_time_minutes == pytest.approx(expected)

    def test_pts_bulk_linen_rejected_by_converter(self):
        load = cta.TransportLoad(load_id="L1", stream="CLEAN_LINEN", patient_ids=("P-1",), origin="A", destination="B",
                                 quantity=1.0, unit="kg", payload_class="CLEAN_LINEN", release_datetime=DAY0, priority="ROUTINE")
        with pytest.raises(ValueError):
            cta.convert_load_to_pts_missions(load=load, network=cta.DEFAULT_PTS_NETWORK)


# ===========================================================================
# No-double-count governor (Sec 64): each economic term appears once per view
# ===========================================================================
class TestNoDoubleCount:
    def test_pts_capex_counts_stations_and_network_once(self):
        import dataclasses
        net = dataclasses.replace(cta.DEFAULT_PTS_NETWORK, asset_status="PROPOSED")
        capex = cta.pts_new_study_capex(net, study_scope="CAPITAL_PLANNING")
        # Exactly stations + network, no third term.
        assert capex == pytest.approx(net.station_count * net.station_capex_per_unit + net.network_length_m * net.network_capex_per_m)

    def test_manual_labor_and_cart_are_separate_terms(self):
        # cart maintenance is distinct from porter labor -- adding a cart only adds the cart term.
        base = view.manual_parity_view(policy=cta.PorterOperatingPolicy(), stream="CLEAN_LINEN", mission_minutes=15.0, required_fte=1.0, annual_labor_opex=100_000.0)
        with_cart = view.manual_parity_view(policy=cta.PorterOperatingPolicy(), stream="CLEAN_LINEN", mission_minutes=15.0, required_fte=1.0, annual_labor_opex=100_000.0, cart=cta.DEFAULT_LINEN_CART)
        assert with_cart.known_annual_opex_usd - base.known_annual_opex_usd == pytest.approx(cta.DEFAULT_LINEN_CART.annual_maintenance_opex)

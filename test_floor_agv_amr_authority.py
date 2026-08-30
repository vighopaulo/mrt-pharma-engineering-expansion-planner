"""KIRO Super-Build 1: deterministic tests for the free-roaming floor AGV/AMR
authority (AGV_AMR_LIGHT_CLINICAL + AGV_AMR_HEAVY_LOGISTICS)."""

from __future__ import annotations

import math

import pytest

import floor_agv_amr_authority as agv
import transport_technology_authority as tta


# --- Class identity / distinctness -------------------------------------------------------
class TestClassIdentity:
    def test_two_distinct_classes(self):
        assert agv.FLOOR_AGV_AMR_LIGHT_CLINICAL != agv.FLOOR_AGV_AMR_HEAVY_LOGISTICS

    def test_floor_agv_is_the_now_implemented_class(self):
        assert tta.FLOOR_AGV_AMR_IMPLEMENTATION_STATUS == "IMPLEMENTED"

    def test_rght_not_floor_agv_invariant_preserved(self):
        assert tta.RAIL_GUIDED_HOSPITAL_TRANSPORT != tta.FLOOR_AGV_AMR

    def test_light_and_heavy_have_distinct_payload_limits(self):
        assert agv.DEFAULT_LIGHT_CLINICAL_PROFILE.payload_mass_limit_kg < agv.DEFAULT_HEAVY_LOGISTICS_PROFILE.payload_mass_limit_kg

    def test_light_and_heavy_have_distinct_batteries(self):
        assert agv.DEFAULT_LIGHT_CLINICAL_PROFILE.battery_capacity_kwh != agv.DEFAULT_HEAVY_LOGISTICS_PROFILE.battery_capacity_kwh

    def test_light_and_heavy_have_distinct_supported_streams(self):
        assert agv.DEFAULT_LIGHT_CLINICAL_PROFILE.supported_streams != agv.DEFAULT_HEAVY_LOGISTICS_PROFILE.supported_streams

    def test_radiopharm_default_qualification_required_both(self):
        assert agv.DEFAULT_LIGHT_CLINICAL_PROFILE.radiopharmaceutical_status == "QUALIFICATION_REQUIRED"
        assert agv.DEFAULT_HEAVY_LOGISTICS_PROFILE.radiopharmaceutical_status == "QUALIFICATION_REQUIRED"


# --- Payload eligibility / no silent enlarge ---------------------------------------------
class TestPayloadEligibility:
    def test_light_accepts_specimen(self):
        r = agv.evaluate_floor_agv_payload(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, stream="SPECIMEN_BLOOD", payload_mass_kg=2.0)
        assert r.eligible and r.status == "ELIGIBLE"

    def test_light_rejects_linen_stream(self):
        r = agv.evaluate_floor_agv_payload(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, stream="CLEAN_LINEN", payload_mass_kg=60.0)
        assert not r.eligible and r.status == "INELIGIBLE_STREAM"

    def test_light_rejects_overmass_supported_stream(self):
        r = agv.evaluate_floor_agv_payload(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, stream="STERILE_CLEAN_SUPPLY", payload_mass_kg=100.0)
        assert not r.eligible and r.status == "INELIGIBLE_MASS"

    def test_light_rejects_overvolume(self):
        r = agv.evaluate_floor_agv_payload(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, stream="STERILE_CLEAN_SUPPLY", payload_mass_kg=5.0, payload_volume_l=500.0)
        assert not r.eligible and r.status == "INELIGIBLE_VOLUME"

    def test_heavy_accepts_linen(self):
        r = agv.evaluate_floor_agv_payload(profile=agv.DEFAULT_HEAVY_LOGISTICS_PROFILE, stream="CLEAN_LINEN", payload_mass_kg=60.0)
        assert r.eligible and r.status == "ELIGIBLE"

    def test_light_never_silently_enlarged(self):
        # A payload the light class cannot carry stays INELIGIBLE on the light profile.
        r = agv.evaluate_floor_agv_payload(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, stream="CLEAN_LINEN", payload_mass_kg=60.0)
        assert r.vehicle_class == "AGV_AMR_LIGHT_CLINICAL"  # never becomes heavy
        assert not r.eligible

    def test_radiopharm_qualification_required_light(self):
        r = agv.evaluate_floor_agv_payload(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, stream="RADIOPHARMACEUTICAL_NUCLEAR", payload_mass_kg=3.0)
        assert r.status == "QUALIFICATION_REQUIRED" and not r.eligible

    def test_radiopharm_qualification_required_heavy(self):
        r = agv.evaluate_floor_agv_payload(profile=agv.DEFAULT_HEAVY_LOGISTICS_PROFILE, stream="RADIOPHARMACEUTICAL_NUCLEAR", payload_mass_kg=3.0)
        assert r.status == "QUALIFICATION_REQUIRED" and not r.eligible


# --- Route physics -----------------------------------------------------------------------
class TestRoutePhysics:
    def test_calibrated_horizontal(self):
        p = agv.DEFAULT_LIGHT_CLINICAL_PROFILE
        t = agv.compute_floor_agv_mission_timing(profile=p, horizontal_distance_m=120.0)
        assert t.route_status == "ROUTE_CALIBRATED"
        assert t.horizontal_minutes == pytest.approx(120.0 / p.speed_m_per_s / 60.0)

    def test_not_calibrated_fallback(self):
        t = agv.compute_floor_agv_mission_timing(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE)
        assert t.route_status == "ROUTE_NOT_CALIBRATED"

    def test_elevator_adds_time_no_teleport(self):
        p = agv.DEFAULT_LIGHT_CLINICAL_PROFILE
        t0 = agv.compute_floor_agv_mission_timing(profile=p, horizontal_distance_m=100.0, vertical_transitions=0)
        t1 = agv.compute_floor_agv_mission_timing(profile=p, horizontal_distance_m=100.0, vertical_transitions=1)
        assert t1.total_minutes > t0.total_minutes  # vertical transition costs elevator time (no teleport)

    def test_door_delay_adds_time(self):
        p = agv.DEFAULT_LIGHT_CLINICAL_PROFILE
        t0 = agv.compute_floor_agv_mission_timing(profile=p, horizontal_distance_m=100.0, doors_per_mission=0)
        t2 = agv.compute_floor_agv_mission_timing(profile=p, horizontal_distance_m=100.0, doors_per_mission=3)
        assert t2.total_minutes > t0.total_minutes

    def test_round_trip_distance_double_one_way(self):
        t = agv.compute_floor_agv_mission_timing(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, horizontal_distance_m=100.0)
        assert t.round_trip_distance_km == pytest.approx(2.0 * 100.0 / 1000.0)


# --- Energy / no double count ------------------------------------------------------------
class TestEnergy:
    def test_traction_energy_distance_scaled(self):
        p = agv.DEFAULT_HEAVY_LOGISTICS_PROFILE
        e = agv.compute_floor_agv_energy(profile=p, round_trip_distance_km=0.5, missions_per_day=10, operating_days_per_year=300)
        assert e.annual_traction_kwh == pytest.approx(0.5 * p.energy_kwh_per_km * 10 * 300)

    def test_charging_loss_folded_once_not_double(self):
        p = agv.DEFAULT_LIGHT_CLINICAL_PROFILE
        e = agv.compute_floor_agv_energy(profile=p, round_trip_distance_km=0.24, missions_per_day=20, operating_days_per_year=300)
        # total_known = (traction+idle) + charging_loss, where charging_loss=(traction+idle)*(1/eff - 1)
        base = e.annual_traction_kwh + e.annual_idle_kwh
        assert e.total_known_annual_kwh == pytest.approx(base / p.charging_efficiency)

    def test_network_standby_not_calibrated_not_zero(self):
        e = agv.compute_floor_agv_energy(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, round_trip_distance_km=0.24, missions_per_day=20, operating_days_per_year=300)
        assert e.network_standby_status == "NOT_CALIBRATED"

    def test_electricity_cost_uses_tariff(self):
        e = agv.compute_floor_agv_energy(profile=agv.DEFAULT_HEAVY_LOGISTICS_PROFILE, round_trip_distance_km=0.5, missions_per_day=10, operating_days_per_year=300)
        assert e.annual_electricity_usd == pytest.approx(e.total_known_annual_kwh * agv.FLOOR_AGV_ELECTRICITY_TARIFF_USD_PER_KWH.active_value)


# --- Fleet sizing ------------------------------------------------------------------------
class TestFleet:
    def test_zero_workload_zero_fleet(self):
        f = agv.compute_floor_agv_fleet(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, missions_per_day=0, mission_cycle_minutes=10.0, energy_per_mission_kwh=0.1)
        assert f.required_fleet == 0

    def test_fleet_includes_charging_in_cycle(self):
        f = agv.compute_floor_agv_fleet(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, missions_per_day=50, mission_cycle_minutes=15.0, energy_per_mission_kwh=0.2)
        assert f.charging_minutes_per_mission > 0
        assert f.effective_cycle_minutes > f.mission_cycle_minutes

    def test_fleet_workload_scales(self):
        p = agv.DEFAULT_LIGHT_CLINICAL_PROFILE
        low = agv.compute_floor_agv_fleet(profile=p, missions_per_day=20, mission_cycle_minutes=15.0, energy_per_mission_kwh=0.2)
        high = agv.compute_floor_agv_fleet(profile=p, missions_per_day=200, mission_cycle_minutes=15.0, energy_per_mission_kwh=0.2)
        assert high.required_fleet > low.required_fleet

    def test_reserve_increases_fleet(self):
        p = agv.DEFAULT_HEAVY_LOGISTICS_PROFILE
        base = agv.compute_floor_agv_fleet(profile=p, missions_per_day=100, mission_cycle_minutes=20.0, energy_per_mission_kwh=0.3)
        res = agv.compute_floor_agv_fleet(profile=p, missions_per_day=100, mission_cycle_minutes=20.0, energy_per_mission_kwh=0.3, reserve_fraction=0.5)
        assert res.required_fleet >= base.required_fleet


# --- CapEx -------------------------------------------------------------------------------
class TestCapex:
    def test_vehicles_scale_but_fleet_manager_once(self):
        p = agv.DEFAULT_LIGHT_CLINICAL_PROFILE
        c1 = agv.compute_floor_agv_capex(profile=p, fleet_size=1, charging_station_count=1)
        c5 = agv.compute_floor_agv_capex(profile=p, fleet_size=5, charging_station_count=1)
        # fleet-manager + install are once (identical); vehicle line scales
        assert c1.fleet_manager_capex == c5.fleet_manager_capex
        assert c1.install_commissioning_capex == c5.install_commissioning_capex
        assert c5.vehicles_capex == 5 * p.vehicle_capex_usd

    def test_capex_subtotal_is_sum_of_known_lines(self):
        c = agv.compute_floor_agv_capex(profile=agv.DEFAULT_HEAVY_LOGISTICS_PROFILE, fleet_size=3, charging_station_count=2, elevators_integrated=2, doors_integrated=4)
        line_sum = c.vehicles_capex + c.charging_stations_capex + c.fleet_manager_capex + c.elevator_integration_capex + c.door_integration_capex + c.install_commissioning_capex
        assert c.known_capex_subtotal == pytest.approx(line_sum)

    def test_capex_has_unknown_components_listed(self):
        c = agv.compute_floor_agv_capex(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, fleet_size=2, charging_station_count=1)
        assert len(c.unknown_capex_components) >= 1


# --- OPEX --------------------------------------------------------------------------------
class TestOpex:
    def test_opex_subtotal_is_sum_of_known_lines(self):
        o = agv.compute_floor_agv_opex(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, fleet_size=3, charging_station_count=2, annual_electricity_usd=1000.0, loaded_annual_cost_per_fte=70_000.0)
        line_sum = o.electricity_usd + o.vehicle_maintenance_usd + o.battery_replacement_amortized_usd + o.charging_station_maintenance_usd + o.fleet_software_usd + o.supervision_usd
        assert o.known_annual_opex_subtotal == pytest.approx(line_sum)

    def test_battery_replacement_amortized_never_zero(self):
        o = agv.compute_floor_agv_opex(profile=agv.DEFAULT_HEAVY_LOGISTICS_PROFILE, fleet_size=2, charging_station_count=1, annual_electricity_usd=500.0, loaded_annual_cost_per_fte=70_000.0)
        assert o.battery_replacement_amortized_usd > 0.0

    def test_software_once_not_per_vehicle(self):
        p = agv.DEFAULT_LIGHT_CLINICAL_PROFILE
        o1 = agv.compute_floor_agv_opex(profile=p, fleet_size=1, charging_station_count=1, annual_electricity_usd=100.0, loaded_annual_cost_per_fte=70_000.0)
        o9 = agv.compute_floor_agv_opex(profile=p, fleet_size=9, charging_station_count=1, annual_electricity_usd=100.0, loaded_annual_cost_per_fte=70_000.0)
        assert o1.fleet_software_usd == o9.fleet_software_usd

    def test_total_opex_status_not_fully_calibrated(self):
        o = agv.compute_floor_agv_opex(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, fleet_size=2, charging_station_count=1, annual_electricity_usd=100.0, loaded_annual_cost_per_fte=70_000.0)
        assert o.total_opex_status == "KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED"
        assert len(o.unknown_opex_components) >= 1


# --- Provenance / benchmark register -----------------------------------------------------
class TestProvenance:
    def test_benchmark_register_nonempty_and_labeled(self):
        rows = agv.floor_agv_controlled_benchmark_register()
        assert len(rows) >= 40
        for row in rows:
            assert row["parameter"] and row["unit"] and row["provenance"]
            assert row["calibration_status"] in {"CONTROLLED_ENGINEERING_ASSUMPTION", "PROJECT_CONTROLLED_ASSUMPTION", "NOT_CALIBRATED", "USER_OVERRIDE", "PUBLISHED_ENGINEERING_DEFAULT", "MEDIUM"}

    def test_no_benchmark_is_calibrated_project_value(self):
        rows = agv.floor_agv_controlled_benchmark_register()
        assert all(row["calibration_status"] != "CALIBRATED_PROJECT_VALUE" for row in rows)

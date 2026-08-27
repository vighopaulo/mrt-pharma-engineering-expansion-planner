"""Focused tests for `mrt_auxiliary_systems_authority.py`: the MRT/Automated-
Conventional auxiliary electrical/thermal/cooling/vacuum/site-power physics
authority AND the unified what-if parameter/scenario authority.

Covers: mandatory existing-authority audit, resistive electrical authority,
thermal load reconciliation, cooling architecture, pressure/vacuum/drag
physics, superconducting/hybrid guideway composition, segmented energization/
concurrency, carrier kinematics/speed dependency, total electrical load
composition, annual energy/electricity OPEX, site power adequacy, Automated-
Conventional auxiliary parity, Manual Conventional zero-propulsion assertion,
utility classification, legacy-vs-physical reconciliation, speed dependency
trace/sweep/feasibility/what-if comparison, the unified what-if parameter
registry, the combined multi-category scenario authority (branching, add/
remove/reset-category/return-to-locked), scenario validation, impact
contracts, auxiliary zones/provisioning, and the CONTROLLED_AUXILIARY_PHYSICS_
TEST_CASE fixture.
"""

import math

import pytest

import canonical_spatial_authority as csa
import mrt_auxiliary_systems_authority as maux


# ---------------------------------------------------------------------------
# Mandatory existing-authority audit
# ---------------------------------------------------------------------------


def test_audit_existing_energy_opex_authority_returns_eight_entries_with_live_values():
    entries = maux.audit_existing_energy_opex_authority()
    assert len(entries) == 8
    by_component = {e.component: e for e in entries}
    assert "$250" in by_component["MRT carrier electricity (planning allowance)"].value
    assert "$500" in by_component["MRT carrier maintenance"].value
    assert "3%" in by_component["MRT guideway maintenance fraction"].value
    assert "$1,500" in by_component["AGV annual energy OPEX (lumped)"].value
    assert "$1,000" in by_component["PTS annual energy OPEX (lumped)"].value


def test_audit_classifications_never_claim_physical_calibration_for_planning_assumptions():
    entries = maux.audit_existing_energy_opex_authority()
    for e in entries:
        if "OPEX" in e.component or "maintenance" in e.component.lower():
            assert e.classification in ("PROJECT_PLANNING_ASSUMPTION", "CONTROLLED_SCENARIO_ASSUMPTION", "NOT_CALIBRATED", "EMBEDDED_COMPONENT")


# ---------------------------------------------------------------------------
# Resistive MRT electrical authority
# ---------------------------------------------------------------------------


def test_conductor_resistance_matches_hand_calculation():
    conductor = maux.ConductorSpec(material="copper", resistivity_ohm_m=1.68e-8, length_m=500.0, cross_sectional_area_m2=0.0002, provenance="CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE")
    resistance = maux.compute_conductor_resistance_ohm(conductor)
    assert resistance == pytest.approx(0.042, rel=1e-6)


def test_conductor_resistance_not_calibrated_when_area_missing():
    conductor = maux.ConductorSpec(material="copper", resistivity_ohm_m=1.68e-8, length_m=500.0, cross_sectional_area_m2="NOT_CALIBRATED", provenance="NOT_CALIBRATED")
    assert maux.compute_conductor_resistance_ohm(conductor) == "NOT_CALIBRATED"


def test_conductor_resistance_not_calibrated_when_area_zero_or_negative():
    conductor = maux.ConductorSpec(material="copper", resistivity_ohm_m=1.68e-8, length_m=500.0, cross_sectional_area_m2=0.0, provenance="NOT_CALIBRATED")
    assert maux.compute_conductor_resistance_ohm(conductor) == "NOT_CALIBRATED"


def test_joule_loss_matches_hand_calculation():
    joule = maux.compute_joule_loss_w(rms_current_a=200.0, resistance_ohm=0.042)
    assert joule == pytest.approx(1680.0, rel=1e-9)


def test_joule_loss_not_calibrated_propagates():
    assert maux.compute_joule_loss_w(rms_current_a="NOT_CALIBRATED", resistance_ohm=0.042) == "NOT_CALIBRATED"
    assert maux.compute_joule_loss_w(rms_current_a=200.0, resistance_ohm="NOT_CALIBRATED") == "NOT_CALIBRATED"


def test_electromagnetic_loss_breakdown_sums_only_calibrated_components():
    breakdown = maux.ElectromagneticLossBreakdown(joule_loss_w=1680.0, eddy_current_loss_w=50.0)
    assert breakdown.total_w() == pytest.approx(1730.0)


def test_electromagnetic_loss_breakdown_not_calibrated_only_if_all_missing():
    breakdown = maux.ElectromagneticLossBreakdown(joule_loss_w="NOT_CALIBRATED")
    assert breakdown.total_w() == "NOT_CALIBRATED"


def test_power_electronics_loss_matches_hand_calculation():
    spec = maux.PowerElectronicsSpec(efficiency_fraction=0.95, standby_loss_w=50.0, provenance="CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE")
    loss = maux.compute_power_electronics_loss_w(input_power_w=10_000.0, spec=spec)
    assert loss == pytest.approx(550.0)


def test_power_electronics_loss_never_assumes_full_efficiency():
    spec = maux.PowerElectronicsSpec(efficiency_fraction="NOT_CALIBRATED", standby_loss_w=50.0, provenance="NOT_CALIBRATED")
    assert maux.compute_power_electronics_loss_w(input_power_w=10_000.0, spec=spec) == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# Thermal load
# ---------------------------------------------------------------------------


def test_thermal_load_reconciles_exactly_with_modeled_losses():
    em = maux.ElectromagneticLossBreakdown(joule_loss_w=1680.0)
    thermal = maux.compute_thermal_load(electromagnetic_losses=em, power_electronics_loss_w=550.0)
    assert thermal.heat_generated_w == pytest.approx(2230.0)
    assert thermal.heat_generated_kw() == pytest.approx(2.23)


def test_thermal_load_not_calibrated_when_all_sources_missing():
    em = maux.ElectromagneticLossBreakdown(joule_loss_w="NOT_CALIBRATED")
    thermal = maux.compute_thermal_load(electromagnetic_losses=em, power_electronics_loss_w="NOT_CALIBRATED")
    assert thermal.heat_generated_w == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# Cooling architecture
# ---------------------------------------------------------------------------


def test_forced_air_cooling_computes_airflow_and_fan_power():
    spec = maux.ForcedAirCoolingSpec(heat_rejection_w=2230.0, inlet_temp_c=22.0, outlet_temp_c=35.0, air_density_kg_m3=1.2, specific_heat_j_per_kg_k=1005.0, pressure_drop_pa=150.0, fan_efficiency_fraction=0.6)
    result = maux.compute_forced_air_cooling(spec)
    assert result.missing_inputs == ()
    assert result.required_airflow_m3_s > 0
    assert result.fan_electrical_power_w > 0


def test_forced_air_cooling_reports_every_missing_input_individually():
    spec = maux.ForcedAirCoolingSpec(heat_rejection_w="NOT_CALIBRATED")
    result = maux.compute_forced_air_cooling(spec)
    assert "heat_rejection_w" in result.missing_inputs
    assert len(result.missing_inputs) > 1


def test_forced_air_cooling_rejects_nonpositive_temperature_rise():
    spec = maux.ForcedAirCoolingSpec(heat_rejection_w=1000.0, inlet_temp_c=30.0, outlet_temp_c=22.0, air_density_kg_m3=1.2, specific_heat_j_per_kg_k=1005.0, pressure_drop_pa=150.0, fan_efficiency_fraction=0.6)
    result = maux.compute_forced_air_cooling(spec)
    assert result.required_airflow_m3_s == "NOT_CALIBRATED"


def test_liquid_cooling_heat_capacity_resolves_even_if_pump_inputs_missing():
    spec = maux.LiquidCoolingSpec(coolant="water", mass_flow_kg_s=0.5, specific_heat_j_per_kg_k=4186.0, temperature_rise_k=5.0, pump_head_m="NOT_CALIBRATED", pump_efficiency_fraction="NOT_CALIBRATED", fluid_density_kg_m3="NOT_CALIBRATED")
    result = maux.compute_liquid_cooling(spec)
    assert result.heat_rejection_capacity_w == pytest.approx(0.5 * 4186.0 * 5.0)
    assert result.pump_electrical_power_w == "NOT_CALIBRATED"
    assert "pump_head_m" in result.missing_inputs


def test_resolve_cooling_power_passive_is_zero_electrical():
    result = maux.resolve_cooling_power(architecture="PASSIVE")
    assert result.cooling_electrical_power_w == 0.0


def test_resolve_cooling_power_hybrid_sums_both_when_resolved():
    fa = maux.ForcedAirCoolingResult(required_airflow_m3_s=1.0, fan_electrical_power_w=100.0, missing_inputs=())
    liq = maux.LiquidCoolingResult(heat_rejection_capacity_w=2000.0, pump_electrical_power_w=50.0, missing_inputs=())
    result = maux.resolve_cooling_power(architecture="HYBRID_COOLING", forced_air=fa, liquid=liq)
    assert result.cooling_electrical_power_w == pytest.approx(150.0)


def test_resolve_cooling_power_unselected_is_not_calibrated():
    result = maux.resolve_cooling_power(architecture="NOT_SELECTED")
    assert result.cooling_electrical_power_w == "NOT_CALIBRATED"
    assert result.missing_inputs


# ---------------------------------------------------------------------------
# Pressure/vacuum + aerodynamic drag
# ---------------------------------------------------------------------------


def test_atmospheric_density_is_standard_sea_level_value():
    spec = maux.TransportEnvironmentSpec(environment="ATMOSPHERIC")
    assert maux.resolve_gas_density_kg_m3(spec) == pytest.approx(1.225)


def test_vacuum_density_requires_calibrated_pressure_never_fabricated():
    spec = maux.TransportEnvironmentSpec(environment="VACUUM")
    assert maux.resolve_gas_density_kg_m3(spec) == "NOT_CALIBRATED"


def test_vacuum_density_is_far_lower_than_atmospheric_when_calibrated():
    vac_spec = maux.TransportEnvironmentSpec(environment="VACUUM", chamber_pressure_pa=100.0)
    atm_spec = maux.TransportEnvironmentSpec(environment="ATMOSPHERIC")
    vac_density = maux.resolve_gas_density_kg_m3(vac_spec)
    atm_density = maux.resolve_gas_density_kg_m3(atm_spec)
    assert vac_density < atm_density / 1000.0


def test_drag_power_scales_cubically_with_speed_never_linearly():
    drag_spec = maux.DragSpec(frontal_area_m2=1.0, drag_coefficient=0.8)
    density = 1.225
    force_10 = maux.compute_drag_force_n(spec=drag_spec, gas_density_kg_m3=density, speed_m_per_s=10.0)
    power_10 = maux.compute_drag_power_w(drag_force_n=force_10, speed_m_per_s=10.0)
    force_15 = maux.compute_drag_force_n(spec=drag_spec, gas_density_kg_m3=density, speed_m_per_s=15.0)
    power_15 = maux.compute_drag_power_w(drag_force_n=force_15, speed_m_per_s=15.0)
    ratio = power_15 / power_10
    assert ratio == pytest.approx(1.5 ** 3, rel=1e-6)
    assert ratio != pytest.approx(1.5, rel=0.05)


def test_drag_power_in_vacuum_is_dramatically_lower_than_atmospheric_at_same_speed():
    drag_spec = maux.DragSpec(frontal_area_m2=1.0, drag_coefficient=0.8)
    atm_force = maux.compute_drag_force_n(spec=drag_spec, gas_density_kg_m3=1.225, speed_m_per_s=10.0)
    atm_power = maux.compute_drag_power_w(drag_force_n=atm_force, speed_m_per_s=10.0)
    vac_force = maux.compute_drag_force_n(spec=drag_spec, gas_density_kg_m3=0.001188, speed_m_per_s=10.0)
    vac_power = maux.compute_drag_power_w(drag_force_n=vac_force, speed_m_per_s=10.0)
    assert vac_power < atm_power / 100.0


def test_vacuum_energy_distinguishes_pump_down_from_holding():
    spec = maux.VacuumSystemSpec(conduit_volume_m3=50.0, target_pressure_pa=100.0, pump_down_time_s=600.0, pump_efficiency_fraction=0.6, holding_power_w=200.0)
    result = maux.compute_vacuum_energy(spec)
    assert result.pump_down_energy_j != "NOT_CALIBRATED"
    assert result.steady_holding_power_w == 200.0
    assert result.missing_inputs == ()


def test_vacuum_energy_never_fabricates_pump_size_when_inputs_missing():
    spec = maux.VacuumSystemSpec()
    result = maux.compute_vacuum_energy(spec)
    assert result.pump_down_energy_j == "NOT_CALIBRATED"
    assert result.steady_holding_power_w == "NOT_CALIBRATED"
    assert len(result.missing_inputs) >= 4


# ---------------------------------------------------------------------------
# Superconducting + hybrid composition
# ---------------------------------------------------------------------------


def test_superconducting_auxiliary_total_sums_calibrated_components():
    spec = maux.SuperconductingAuxiliarySpec(cryogenic_refrigeration_demand_w=500.0, cryocooler_electrical_demand_w=1500.0, thermal_leak_w=50.0)
    assert spec.total_w() == pytest.approx(2050.0)


def test_hybrid_guideway_composition_adds_shared_controls_exactly_once():
    total = maux.compose_hybrid_guideway_load(resistive_electrical_w=2000.0, superconducting_electrical_w=2050.0, shared_controls_w=100.0)
    assert total == pytest.approx(4150.0)


def test_hybrid_guideway_composition_not_calibrated_when_all_missing():
    total = maux.compose_hybrid_guideway_load(resistive_electrical_w="NOT_CALIBRATED", superconducting_electrical_w="NOT_CALIBRATED")
    assert total == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# Segmented energization / concurrency
# ---------------------------------------------------------------------------


def test_network_electrical_load_scales_with_simultaneous_segments_not_daily_total():
    one = maux.SegmentedEnergizationSpec(per_segment_power_w=5000.0, simultaneous_active_segments=1, duty_cycle_fraction=0.5)
    five = maux.SegmentedEnergizationSpec(per_segment_power_w=5000.0, simultaneous_active_segments=5, duty_cycle_fraction=0.5)
    result_one = maux.compute_network_electrical_load(one)
    result_five = maux.compute_network_electrical_load(five)
    assert result_one.instantaneous_peak_w == pytest.approx(5000.0)
    assert result_five.instantaneous_peak_w == pytest.approx(25000.0)
    assert result_five.average_w == pytest.approx(12500.0)


def test_network_electrical_load_not_calibrated_when_concurrency_unknown():
    spec = maux.SegmentedEnergizationSpec(per_segment_power_w=5000.0, simultaneous_active_segments="NOT_CALIBRATED")
    result = maux.compute_network_electrical_load(spec)
    assert result.instantaneous_peak_w == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# Carrier kinematics + transport time + acceleration energy
# ---------------------------------------------------------------------------


def test_transport_time_distinguishes_acceleration_from_steady_travel():
    spec = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=10.0, acceleration_m_per_s2=1.0, route_length_m=500.0)
    result = maux.compute_transport_time(spec)
    assert result.accelerate_time_s == pytest.approx(10.0)
    assert result.steady_time_s is not None
    assert result.total_time_s == pytest.approx(result.accelerate_time_s + result.steady_time_s + result.accelerate_time_s)


def test_transport_time_infeasible_when_route_too_short_for_target_speed():
    spec = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=15.0, acceleration_m_per_s2=1.0, route_length_m=100.0)
    result = maux.compute_transport_time(spec)
    assert result.total_time_s == "NOT_CALIBRATED"


def test_acceleration_energy_scales_quadratically_with_speed():
    spec_10 = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=10.0)
    spec_15 = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=15.0)
    e10 = maux.compute_acceleration_energy_j(spec_10)
    e15 = maux.compute_acceleration_energy_j(spec_15)
    assert e15 / e10 == pytest.approx(1.5 ** 2, rel=1e-6)


def test_regenerative_braking_never_assumed_without_calibrated_recovery_fraction():
    spec = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=10.0, regenerative_braking_status="MODELED", regenerative_recovery_fraction="NOT_CALIBRATED")
    modeled_without_fraction = maux.compute_acceleration_energy_j(spec)
    baseline = maux.compute_acceleration_energy_j(maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=10.0))
    assert modeled_without_fraction == baseline


def test_regenerative_braking_reduces_energy_only_when_fraction_calibrated():
    spec = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=10.0, regenerative_braking_status="MODELED", regenerative_recovery_fraction=0.3)
    energy = maux.compute_acceleration_energy_j(spec)
    baseline = maux.compute_acceleration_energy_j(maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=10.0))
    assert energy == pytest.approx(baseline * 0.7)


# ---------------------------------------------------------------------------
# Total electrical load, annual energy, electricity OPEX
# ---------------------------------------------------------------------------


def test_total_electrical_load_sums_only_calibrated_categories():
    components = maux.MrtAuxiliaryElectricalComponents(electromagnetic_w=2000.0, power_electronics_w=550.0, cooling_w=300.0)
    result = maux.compute_mrt_total_electrical_load(components)
    assert result.total_w == pytest.approx(2850.0)
    assert "vacuum_w" in result.unresolved_components


def test_total_electrical_load_not_calibrated_when_everything_missing():
    result = maux.compute_mrt_total_electrical_load(maux.MrtAuxiliaryElectricalComponents())
    assert result.total_w == "NOT_CALIBRATED"
    assert len(result.unresolved_components) == 8


def test_annual_energy_uses_average_operating_power_and_actual_schedule():
    result = maux.compute_annual_energy(average_operating_w=2850.0, peak_w=3000.0, operating_hours_per_year=6000.0)
    assert result.annual_kwh == pytest.approx(2.85 * 6000.0)
    assert result.annual_kwh != pytest.approx((3000.0 / 1000.0) * 8760.0)


def test_annual_energy_not_calibrated_when_schedule_missing():
    result = maux.compute_annual_energy(average_operating_w=2850.0, peak_w=3000.0, operating_hours_per_year="NOT_CALIBRATED")
    assert result.annual_kwh == "NOT_CALIBRATED"


def test_electricity_opex_reuses_tariff_concept():
    opex = maux.compute_electricity_opex(annual_kwh=17100.0, electricity_cost_per_kwh=0.15)
    assert opex == pytest.approx(2565.0)


def test_electricity_opex_not_calibrated_when_tariff_missing():
    assert maux.compute_electricity_opex(annual_kwh=17100.0, electricity_cost_per_kwh="NOT_CALIBRATED") == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# Site power adequacy
# ---------------------------------------------------------------------------


def test_adequate_hospital_site_power_yields_zero_incremental_backup_capex():
    result = maux.evaluate_site_power_adequacy(profile=maux.ADEQUATE_HOSPITAL_SITE_POWER_PROFILE, incremental_demand_kw=10.0)
    assert result.status == "ADEQUATE"
    assert result.incremental_backup_capex_usd == 0.0
    assert result.backup_classification is None


def test_weak_grid_controlled_scenario_is_inadequate_and_never_fabricates_backup_cost():
    result = maux.evaluate_site_power_adequacy(profile=maux.WEAK_GRID_CONTROLLED_SITE_POWER_PROFILE, incremental_demand_kw=100.0)
    assert result.status == "INADEQUATE"
    assert result.incremental_backup_capex_usd == "NOT_CALIBRATED"
    assert result.backup_classification == "SITE_SPECIFIC_RESILIENCE"


def test_weak_grid_scenario_is_a_separately_labeled_controlled_case_not_default():
    assert maux.WEAK_GRID_CONTROLLED_SITE_POWER_PROFILE.reliability_classification == "WEAK_GRID"
    assert maux.ADEQUATE_HOSPITAL_SITE_POWER_PROFILE.reliability_classification == "RESILIENT_HOSPITAL_GRADE"


def test_site_power_adequacy_not_calibrated_when_profile_incomplete():
    incomplete = maux.SitePowerProfile(available_normal_power_kw="NOT_CALIBRATED")
    result = maux.evaluate_site_power_adequacy(profile=incomplete, incremental_demand_kw=10.0)
    assert result.status == "NOT_CALIBRATED"
    assert result.backup_classification is None


# ---------------------------------------------------------------------------
# Automated-Conventional auxiliary parity + Manual Conventional
# ---------------------------------------------------------------------------


def test_agv_charging_authority_preserves_existing_lumped_opex_unchanged():
    result = maux.resolve_agv_charging_authority(existing_annual_energy_opex_usd=1_500.0)
    assert result.existing_lumped_annual_opex_usd == 1_500.0
    assert result.charger_count == "NOT_CALIBRATED"
    assert result.peak_charging_demand_kw == "NOT_CALIBRATED"


def test_pts_auxiliary_authority_preserves_existing_lumped_opex_unchanged():
    result = maux.resolve_pts_auxiliary_authority(existing_annual_energy_opex_usd=1_000.0)
    assert result.existing_lumped_annual_opex_usd == 1_000.0
    assert result.blower_compressor_power_kw == "NOT_CALIBRATED"


def test_manual_conventional_propulsion_electricity_is_always_exactly_zero():
    assert maux.manual_conventional_propulsion_electricity_w() == 0.0


def test_utility_classification_never_charges_common_hvac_to_one_architecture():
    classifications = maux.classify_common_vs_architecture_specific_utilities()
    by_load = {c.load: c for c in classifications}
    assert by_load["Facility-wide HVAC/lighting"].category == "COMMON_BASELINE"
    assert by_load["Manual porter propulsion electricity"].category == "ARCHITECTURE_SPECIFIC"
    assert by_load["Dedicated backup generation/UPS/ATS"].category == "SITE_SPECIFIC_RESILIENCE"


# ---------------------------------------------------------------------------
# Legacy-vs-physical reconciliation (reuses equipment_energy_opex verbatim)
# ---------------------------------------------------------------------------


def test_reconciliation_replaces_legacy_allowance_when_physically_calibrated():
    row = maux.reconcile_mrt_energy_with_legacy_assumption(
        physical_annual_kwh=17100.0, physical_calibration_status="CALIBRATED_FOR_ENERGY",
        legacy_annual_opex_per_unit_usd=250.0, electricity_cost_per_kwh=0.15,
    )
    assert row.annual_kwh == pytest.approx(17100.0)
    assert row.value_source == "SCHEDULE_DERIVED_CALIBRATION"
    assert row.generic_fallback_used is False


def test_reconciliation_preserves_legacy_allowance_when_not_calibrated():
    row = maux.reconcile_mrt_energy_with_legacy_assumption(
        physical_annual_kwh="NOT_CALIBRATED", physical_calibration_status="NOT_CALIBRATED",
        legacy_annual_opex_per_unit_usd=250.0, electricity_cost_per_kwh=0.15,
    )
    assert row.value_source == "GENERIC_ENERGY_FALLBACK"
    assert row.generic_fallback_used is True
    assert row.annual_kwh == pytest.approx(250.0 / 0.15)


def test_reconciliation_never_double_counts_calibrated_and_legacy_together():
    row = maux.reconcile_mrt_energy_with_legacy_assumption(
        physical_annual_kwh=17100.0, physical_calibration_status="CALIBRATED_FOR_ENERGY",
        legacy_annual_opex_per_unit_usd=250.0, electricity_cost_per_kwh=0.15,
    )
    assert row.annual_kwh != pytest.approx(17100.0 + (250.0 / 0.15))


# ---------------------------------------------------------------------------
# Speed dependency trace
# ---------------------------------------------------------------------------


def test_speed_dependency_chain_starts_with_carrier_speed():
    assert maux.SPEED_DEPENDENCY_CHAIN[0] == "carrier_speed"


def test_build_speed_dependency_trace_preserves_unresolved_nodes_visibly():
    trace = maux.build_speed_dependency_trace({"drag": ("RESOLVED", 490.0)})
    by_id = {n.node_id: n for n in trace}
    assert by_id["drag"].resolution_status == "RESOLVED"
    assert by_id["carrier_speed"].resolution_status == "NOT_CALIBRATED"
    assert len(trace) == len(maux.SPEED_DEPENDENCY_CHAIN)


def test_dependency_trace_nodes_chain_sequentially():
    trace = maux.build_speed_dependency_trace({})
    assert trace[0].depends_on == ()
    assert trace[1].depends_on == (trace[0].node_id,)


# ---------------------------------------------------------------------------
# Speed feasibility, sweep, and the mandatory 10->15 m/s comparison
# ---------------------------------------------------------------------------


def test_speed_feasibility_infeasible_for_physically_impossible_short_route():
    spec = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=15.0, acceleration_m_per_s2=1.0, route_length_m=100.0)
    assert maux.evaluate_speed_feasibility(kinematics=spec) == "INFEASIBLE"


def test_speed_feasibility_feasible_for_adequate_route():
    spec = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=15.0, acceleration_m_per_s2=1.0, route_length_m=500.0)
    assert maux.evaluate_speed_feasibility(kinematics=spec) == "FEASIBLE"


def test_speed_feasibility_never_fabricates_a_maximum_speed():
    for speed in (5.0, 10.0, 15.0, 20.0):
        spec = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=speed, acceleration_m_per_s2=1.0, route_length_m=1000.0)
        assert maux.evaluate_speed_feasibility(kinematics=spec) == "FEASIBLE"


def test_speed_feasibility_not_calibrated_when_inputs_missing():
    spec = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=10.0)
    assert maux.evaluate_speed_feasibility(kinematics=spec) == "NOT_CALIBRATED"


def test_sweep_speeds_evaluates_the_same_chain_at_each_speed():
    template = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=10.0, acceleration_m_per_s2=1.0, route_length_m=500.0)
    drag_spec = maux.DragSpec(frontal_area_m2=1.0, drag_coefficient=0.8)
    rows = maux.sweep_speeds(speeds=(5.0, 10.0, 15.0), kinematics_template=template, drag_spec=drag_spec, gas_density_kg_m3=1.225)
    assert [r.speed_m_per_s for r in rows] == [5.0, 10.0, 15.0]
    assert rows[2].drag_power_w > rows[1].drag_power_w > rows[0].drag_power_w


def test_compare_speed_what_if_10_to_15_shows_nonlinear_resolved_deltas():
    template = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=10.0, acceleration_m_per_s2=1.0, route_length_m=500.0)
    drag_spec = maux.DragSpec(frontal_area_m2=1.0, drag_coefficient=0.8)
    rows = maux.compare_speed_what_if(locked_speed_m_per_s=10.0, what_if_speed_m_per_s=15.0, kinematics_template=template, drag_spec=drag_spec, gas_density_kg_m3=1.225)
    by_metric = {r.metric: r for r in rows}
    assert by_metric["drag_power_w"].status == "RESOLVED"
    assert by_metric["drag_power_w"].what_if_value > by_metric["drag_power_w"].locked_value
    assert by_metric["transport_time_s"].what_if_value < by_metric["transport_time_s"].locked_value


def test_compare_speed_what_if_marks_infeasible_what_if_speed():
    template = maux.CarrierKinematicsSpec(carrier_mass_kg=200.0, payload_mass_kg=50.0, target_speed_m_per_s=10.0, acceleration_m_per_s2=1.0, route_length_m=100.0)
    drag_spec = maux.DragSpec(frontal_area_m2=1.0, drag_coefficient=0.8)
    rows = maux.compare_speed_what_if(locked_speed_m_per_s=5.0, what_if_speed_m_per_s=15.0, kinematics_template=template, drag_spec=drag_spec, gas_density_kg_m3=1.225)
    by_metric = {r.metric: r for r in rows}
    assert by_metric["transport_time_s"].status == "INFEASIBLE"


# ---------------------------------------------------------------------------
# Unified what-if parameter registry
# ---------------------------------------------------------------------------


def test_default_parameter_registry_spans_all_nine_categories():
    registry = maux.build_default_parameter_registry()
    categories_present = {d.category for d in registry.definitions.values()}
    assert categories_present == set(maux.WHAT_IF_CATEGORIES)


def test_parameter_registry_resolve_and_by_category():
    registry = maux.build_default_parameter_registry()
    definition = registry.resolve("carrier_speed")
    assert definition is not None
    assert definition.category == "ELECTRICAL_THERMAL"
    electrical_params = registry.by_category("ELECTRICAL_THERMAL")
    assert any(d.parameter_id == "carrier_speed" for d in electrical_params)


def test_parameter_registry_unknown_id_resolves_to_none():
    registry = maux.build_default_parameter_registry()
    assert registry.resolve("does_not_exist") is None


# ---------------------------------------------------------------------------
# Combined multi-category what-if scenario authority
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_locked_state():
    return csa.LockedSpatialState(registry=csa.SpatialObjectRegistry(objects={}))


@pytest.fixture
def locked_state_with_equipment():
    obj = csa.CanonicalSpatialObject(
        mrtway_object_id="EQ-1", object_type="EQUIPMENT", facility_id="FAC-1", building_id="B1", floor_id="F1",
        space_id=None, parent_object_id=None, transform=csa.Transform(), geometry_reference=None,
        coordinate_system="LOCAL_FACILITY", asset_status="EXISTING", operational_state="AVAILABLE",
        spatial_status="CALIBRATED", provenance="USER_CREATED",
    )
    return csa.LockedSpatialState(registry=csa.SpatialObjectRegistry(objects={"EQ-1": obj}))


def test_branch_what_if_scenario_creates_independent_clone(empty_locked_state):
    scenario = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1")
    assert scenario.what_if.registry.objects == empty_locked_state.registry.objects
    assert scenario.what_if.registry is not empty_locked_state.registry


def test_two_branches_from_same_locked_state_are_mutually_independent(locked_state_with_equipment):
    locked = locked_state_with_equipment
    scenario_a = maux.branch_what_if_scenario(locked=locked, base_locked_state_id="LOCKED-1", scenario_id="A")
    scenario_b = maux.branch_what_if_scenario(locked=locked, base_locked_state_id="LOCKED-1", scenario_id="B")
    obj = locked.registry.objects["EQ-1"]
    moved = csa.replace(obj, transform=csa.Transform(position_x=99.0))
    cs = csa.apply_changeset(scenario_a.what_if, change_id="CS-A", operation="MOVE_OBJECT", object_id="EQ-1", new_object=moved)
    maux.record_spatial_change(scenario_a, category="GEOMETRY_ORIENTATION", changeset=cs, description="move in A only")
    assert scenario_a.what_if.registry.objects["EQ-1"].transform.position_x == 99.0
    assert scenario_b.what_if.registry.objects["EQ-1"].transform.position_x == 0.0
    assert locked.registry.objects["EQ-1"].transform.position_x == 0.0


def test_record_parameter_change_and_category_counts(empty_locked_state):
    scenario = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1")
    maux.record_parameter_change(scenario, category="ELECTRICAL_THERMAL", parameter_id="carrier_speed", locked_value=10.0, what_if_value=15.0, description="speed change")
    maux.record_parameter_change(scenario, category="ECONOMICS_ASSUMPTIONS", parameter_id="electricity_tariff", locked_value=0.15, what_if_value=0.20, description="tariff change")
    counts = scenario.category_counts()
    assert counts["ELECTRICAL_THERMAL"] == 1
    assert counts["ECONOMICS_ASSUMPTIONS"] == 1
    assert counts["GEOMETRY_ORIENTATION"] == 0
    assert len(scenario.active_change_list()) == 2


def test_active_changes_are_ordered(empty_locked_state):
    scenario = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1")
    c1 = maux.record_parameter_change(scenario, category="ELECTRICAL_THERMAL", parameter_id="carrier_speed", locked_value=10.0, what_if_value=15.0, description="first")
    c2 = maux.record_parameter_change(scenario, category="ECONOMICS_ASSUMPTIONS", parameter_id="electricity_tariff", locked_value=0.15, what_if_value=0.20, description="second")
    changes = scenario.active_change_list()
    assert changes[0].change_id == c1.change_id
    assert changes[1].change_id == c2.change_id


def test_remove_one_change_preserves_others(empty_locked_state):
    scenario = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1")
    c1 = maux.record_parameter_change(scenario, category="ELECTRICAL_THERMAL", parameter_id="carrier_speed", locked_value=10.0, what_if_value=15.0, description="speed")
    c2 = maux.record_parameter_change(scenario, category="ECONOMICS_ASSUMPTIONS", parameter_id="electricity_tariff", locked_value=0.15, what_if_value=0.20, description="tariff")
    maux.remove_one_change(scenario, c1.change_id)
    remaining_ids = [c.change_id for c in scenario.active_change_list()]
    assert c1.change_id not in remaining_ids
    assert c2.change_id in remaining_ids


def test_reset_category_removes_only_that_category(locked_state_with_equipment):
    locked = locked_state_with_equipment
    scenario = maux.branch_what_if_scenario(locked=locked, base_locked_state_id="LOCKED-1")
    obj = locked.registry.objects["EQ-1"]
    moved = csa.replace(obj, transform=csa.Transform(position_x=5.0))
    cs = csa.apply_changeset(scenario.what_if, change_id="CS-1", operation="MOVE_OBJECT", object_id="EQ-1", new_object=moved)
    maux.record_spatial_change(scenario, category="GEOMETRY_ORIENTATION", changeset=cs, description="move equipment")
    maux.record_parameter_change(scenario, category="ELECTRICAL_THERMAL", parameter_id="carrier_speed", locked_value=10.0, what_if_value=15.0, description="speed change")

    maux.reset_what_if_category(scenario, "GEOMETRY_ORIENTATION")

    assert scenario.what_if.registry.objects["EQ-1"].transform.position_x == 0.0
    counts = scenario.category_counts()
    assert counts["GEOMETRY_ORIENTATION"] == 0
    assert counts["ELECTRICAL_THERMAL"] == 1


def test_return_to_locked_clears_everything_and_never_mutates_locked(locked_state_with_equipment):
    locked = locked_state_with_equipment
    scenario = maux.branch_what_if_scenario(locked=locked, base_locked_state_id="LOCKED-1")
    obj = locked.registry.objects["EQ-1"]
    moved = csa.replace(obj, transform=csa.Transform(position_x=5.0))
    cs = csa.apply_changeset(scenario.what_if, change_id="CS-1", operation="MOVE_OBJECT", object_id="EQ-1", new_object=moved)
    maux.record_spatial_change(scenario, category="GEOMETRY_ORIENTATION", changeset=cs, description="move equipment")
    maux.record_parameter_change(scenario, category="ELECTRICAL_THERMAL", parameter_id="carrier_speed", locked_value=10.0, what_if_value=15.0, description="speed change")

    maux.return_scenario_to_locked(scenario)

    assert scenario.active_change_list() == ()
    assert all(v == 0 for v in scenario.category_counts().values())
    assert scenario.what_if.registry.objects == locked.registry.objects
    assert locked.registry.objects["EQ-1"].transform.position_x == 0.0


# ---------------------------------------------------------------------------
# Scenario validation
# ---------------------------------------------------------------------------


def test_scenario_validation_valid_when_all_parameters_calibrated(empty_locked_state):
    scenario = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1")
    maux.record_parameter_change(scenario, category="GEOMETRY_ORIENTATION", parameter_id="building_transform", locked_value=None, what_if_value=None, description="move building")
    registry = maux.build_default_parameter_registry()
    result = maux.validate_what_if_scenario(scenario, parameter_registry=registry)
    assert result.status == "VALID"


def test_scenario_validation_flags_uncalibrated_dependencies(empty_locked_state):
    scenario = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1")
    maux.record_parameter_change(scenario, category="ELECTRICAL_THERMAL", parameter_id="cooling_architecture", locked_value=None, what_if_value="LIQUID_COOLING", description="cooling change")
    registry = maux.build_default_parameter_registry()
    result = maux.validate_what_if_scenario(scenario, parameter_registry=registry)
    assert result.status == "VALID_WITH_UNCALIBRATED_DEPENDENCIES"
    assert "cooling_architecture" in result.uncalibrated_dependencies


def test_scenario_validation_invalid_for_unknown_parameter_id(empty_locked_state):
    scenario = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1")
    maux.record_parameter_change(scenario, category="ELECTRICAL_THERMAL", parameter_id="does_not_exist", locked_value=None, what_if_value=None, description="bogus")
    result = maux.validate_what_if_scenario(scenario)
    assert result.status == "INVALID"


# ---------------------------------------------------------------------------
# Impact contracts + scenario comparison foundation
# ---------------------------------------------------------------------------


def test_financial_impact_contract_resolves_object_count_delta(locked_state_with_equipment):
    locked = locked_state_with_equipment
    scenario = maux.branch_what_if_scenario(locked=locked, base_locked_state_id="LOCKED-1")
    rows = maux.build_financial_impact_contract(scenario)
    by_metric = {r.metric: r for r in rows}
    assert by_metric["object_count_delta"].status == "RESOLVED"
    assert by_metric["locked_capex"].status == "PENDING_ENGINEERING_RECALCULATION"


def test_financial_impact_contract_never_computes_npv_internally(locked_state_with_equipment):
    scenario = maux.branch_what_if_scenario(locked=locked_state_with_equipment, base_locked_state_id="LOCKED-1")
    rows = maux.build_financial_impact_contract(scenario)
    npv_rows = [r for r in rows if "npv" in r.metric]
    assert npv_rows
    for row in npv_rows:
        assert row.status == "PENDING_ENGINEERING_RECALCULATION"


def test_compare_what_if_scenarios_builds_header_row(empty_locked_state):
    scenario_a = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1", scenario_id="A")
    scenario_b = maux.branch_what_if_scenario(locked=empty_locked_state, base_locked_state_id="LOCKED-1", scenario_id="B")
    header = maux.compare_what_if_scenarios(empty_locked_state, {"A": scenario_a, "B": scenario_b})
    assert header == ("metric", "A", "B")


# ---------------------------------------------------------------------------
# Auxiliary zones + retrofit/greenfield provisioning
# ---------------------------------------------------------------------------


def test_auxiliary_zone_serves_multiple_segments_without_multiplying_load():
    zone = maux.AuxiliaryZone(zone_id="COOL-1", zone_type="COOLING_ZONE", served_segment_ids=("SEG-1", "SEG-2", "SEG-3"), shared_electrical_load_w=500.0)
    assert len(zone.served_segment_ids) == 3
    assert zone.shared_electrical_load_w == 500.0


def test_retrofit_with_adequate_site_power_needs_no_new_capex():
    adequacy = maux.SitePowerAdequacyResult(status="ADEQUATE", headroom_kw=100.0, incremental_backup_capex_usd=0.0, backup_classification=None)
    result = maux.evaluate_auxiliary_provisioning(context="RETROFIT", adequacy=adequacy)
    assert result.existing_capacity_sufficient is True
    assert result.new_capex_required_usd == 0.0


def test_greenfield_with_inadequate_power_reports_new_capex_honestly():
    adequacy = maux.SitePowerAdequacyResult(status="INADEQUATE", headroom_kw=-50.0, incremental_backup_capex_usd="NOT_CALIBRATED", backup_classification="SITE_SPECIFIC_RESILIENCE")
    result = maux.evaluate_auxiliary_provisioning(context="GREENFIELD", adequacy=adequacy)
    assert result.existing_capacity_sufficient is False
    assert result.new_capex_required_usd == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE fixture
# ---------------------------------------------------------------------------


def test_controlled_auxiliary_physics_test_case_produces_5_10_15_rows():
    rows = maux.build_controlled_auxiliary_physics_test_case()
    assert [r.speed_m_per_s for r in rows] == [5.0, 10.0, 15.0]


def test_controlled_auxiliary_physics_test_case_shows_nonlinear_drag_growth():
    rows = maux.build_controlled_auxiliary_physics_test_case()
    by_speed = {r.speed_m_per_s: r for r in rows}
    ratio = by_speed[15.0].drag_power_atmospheric_w / by_speed[10.0].drag_power_atmospheric_w
    assert ratio == pytest.approx(1.5 ** 3, rel=1e-6)


def test_controlled_auxiliary_physics_test_case_vacuum_drag_dramatically_lower():
    rows = maux.build_controlled_auxiliary_physics_test_case()
    for row in rows:
        assert row.drag_power_vacuum_w < row.drag_power_atmospheric_w / 100.0


def test_controlled_auxiliary_physics_test_case_electrical_losses_are_speed_independent_in_this_fixture():
    """The fixture's Joule/PE loss inputs (current, PE spec) are held fixed
    across speeds -- only drag/transport-time/kinematics vary with speed in
    this bounded fixture; this test documents that scope honestly."""
    rows = maux.build_controlled_auxiliary_physics_test_case()
    joule_losses = {r.joule_loss_w for r in rows}
    assert len(joule_losses) == 1


def test_controlled_constants_are_never_accidentally_used_as_production_defaults():
    assert maux.CONTROLLED_TEST_CONDUCTOR.provenance == "CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE"
    assert maux.CONTROLLED_TEST_POWER_ELECTRONICS.provenance == "CONTROLLED_AUXILIARY_PHYSICS_TEST_CASE"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_serialize_engineering_calibration_record_includes_schema_version():
    record = maux.EngineeringCalibrationRecord(parameter="carrier_speed", value=10.0, unit="m/s", source="controlled test", status="CALIBRATED")
    serialized = maux.serialize_engineering_calibration_record(record)
    assert serialized["schema_version"] == maux.AUXILIARY_SCHEMA_VERSION
    assert serialized["parameter"] == "carrier_speed"
    assert serialized["value"] == 10.0

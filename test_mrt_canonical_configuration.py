"""Focused deterministic invariants for the MRT CANONICAL CONFIGURATION
CORRECTION build (Sections 37-48, 50).

Targets >= 50 deterministic invariants covering: canonical mass, empty-vs-gross
semantics, payload envelope, carrier dimensions, straight speed, carrier price,
guideway dimensions, guideway price, two-way semantics, refrigeration False,
localized shielding, common carrier, linen exclusion, Manual fallback, mass
negative control, blood/specimen positive control, radiopharmaceutical control,
guideway/carrier/motion-electricity/annual-electricity arithmetic, MRT OPEX
reconciliation, Automated Conventional fairness, Manual preservation, Hybrid
mission assignment, legacy-name compatibility, active old-mass guard, no forced
MRT win, and the experiment-rerun inventory.

Every value is CONTROLLED_ENGINEERING_ASSUMPTION/ENVELOPE, never calibrated.
"""

from __future__ import annotations

import math

import pytest

import mrt_canonical_configuration as mcc


# ===========================================================================
# Section 37 -- CURRENT MRT CONFIGURATION PROOF
# ===========================================================================

class TestCanonicalConfigurationProof:
    def test_config_name_is_mrt(self):
        assert mcc.CANONICAL_MRT.config_name == "MRT"
        assert mcc.CANONICAL_CONFIG_NAME == "MRT"

    def test_max_gross_moving_mass_is_5kg(self):
        assert mcc.MAX_GROSS_MOVING_MASS_KG == 5.0
        assert mcc.CANONICAL_MRT.max_gross_moving_mass_kg == 5.0

    def test_5kg_is_gross_not_empty(self):
        # Empty target is 2-3 kg, strictly below the 5 kg GROSS ceiling.
        assert mcc.EMPTY_CARRIER_MASS_TARGET_HIGH_KG < mcc.MAX_GROSS_MOVING_MASS_KG
        assert mcc.EMPTY_CARRIER_MASS_TARGET_LOW_KG == 2.0
        assert mcc.EMPTY_CARRIER_MASS_TARGET_HIGH_KG == 3.0

    def test_payload_target_range(self):
        assert mcc.PAYLOAD_TARGET_LOW_KG == 2.0
        assert mcc.PAYLOAD_TARGET_HIGH_KG == 3.0

    def test_empty_plus_payload_within_gross_ceiling(self):
        assert mcc.EMPTY_CARRIER_MASS_TARGET_LOW_KG + mcc.PAYLOAD_TARGET_HIGH_KG <= mcc.MAX_GROSS_MOVING_MASS_KG

    def test_carrier_dimensions(self):
        assert mcc.CARRIER_LENGTH_M == 0.200
        assert mcc.CARRIER_WIDTH_M == 0.120
        assert mcc.CARRIER_HEIGHT_M == 0.100

    def test_max_straight_speed_is_10(self):
        assert mcc.MAX_STRAIGHT_SPEED_M_PER_S == 10.0
        assert mcc.CANONICAL_MRT.max_straight_speed_m_per_s == 10.0

    def test_segment_speed_model_not_calibrated(self):
        assert mcc.SEGMENT_SPEED_MODEL_STATUS == "NOT_CALIBRATED"

    def test_carrier_capex_is_2000(self):
        assert mcc.CARRIER_CAPEX_USD == 2_000.0
        assert mcc.CANONICAL_MRT.carrier_capex_usd == 2_000.0

    def test_guideway_two_way_envelope(self):
        assert mcc.GUIDEWAY_EXTERNAL_WIDTH_M == 0.400
        assert mcc.GUIDEWAY_EXTERNAL_HEIGHT_M == 0.180

    def test_two_way_guideway_capex_is_2500_per_m(self):
        assert mcc.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M == 2_500.0
        assert mcc.CANONICAL_MRT.two_way_guideway_capex_usd_per_m == 2_500.0

    def test_powered_onboard_refrigeration_false(self):
        assert mcc.POWERED_ONBOARD_REFRIGERATION is False
        assert mcc.CANONICAL_MRT.powered_onboard_refrigeration is False

    def test_localized_shielding_true(self):
        assert mcc.LOCALIZED_SHIELDING is True

    def test_common_carrier_platform_true(self):
        assert mcc.COMMON_CARRIER_PLATFORM is True

    def test_bulk_linen_eligible_false(self):
        assert mcc.BULK_LINEN_ELIGIBLE is False

    def test_default_bulky_logistics_mode_manual(self):
        assert mcc.DEFAULT_BULKY_LOGISTICS_MODE == "MANUAL"

    def test_no_config_asserts_obsolete_carrier_mass(self):
        obsolete = {12.0, 17.0, 18.0, 18.5, 19.0, 20.0}
        for value in (
            mcc.MAX_GROSS_MOVING_MASS_KG, mcc.EMPTY_CARRIER_MASS_TARGET_LOW_KG,
            mcc.EMPTY_CARRIER_MASS_TARGET_HIGH_KG, mcc.PAYLOAD_TARGET_LOW_KG, mcc.PAYLOAD_TARGET_HIGH_KG,
        ):
            assert value not in obsolete

    def test_provenance_never_calibrated(self):
        c = mcc.CANONICAL_MRT
        for status in (c.mass_status, c.geometry_status, c.speed_status, c.carrier_capex_status, c.guideway_capex_status, c.guideway_geometry_status):
            assert "CONTROLLED" in status
            assert "CALIBRATED" not in status or status == "NOT_CALIBRATED"


# ===========================================================================
# Section 6/38 -- MASS GOVERNOR + MASS NEGATIVE CONTROL
# ===========================================================================

class TestMassGovernor:
    def test_within_ceiling_eligible(self):
        r = mcc.enforce_mass_governor(empty_carrier_mass_kg=2.5, payload_mass_kg=2.0)
        assert r.eligibility == "MRT_ELIGIBLE_BY_MASS"
        assert r.total_moving_mass_kg == pytest.approx(4.5)
        assert r.over_ceiling_kg == 0.0

    def test_exactly_at_ceiling_eligible(self):
        r = mcc.enforce_mass_governor(empty_carrier_mass_kg=2.0, payload_mass_kg=3.0)
        assert r.eligibility == "MRT_ELIGIBLE_BY_MASS"
        assert r.total_moving_mass_kg == pytest.approx(5.0)

    def test_over_ceiling_ineligible(self):
        r = mcc.enforce_mass_governor(empty_carrier_mass_kg=2.5, payload_mass_kg=3.0, shielding_insert_mass_kg=1.0)
        assert r.eligibility == "MRT_INELIGIBLE_BY_MASS"
        assert r.over_ceiling_kg == pytest.approx(1.5)

    def test_ineligible_reason_no_enlarge_no_heavy_substitute(self):
        r = mcc.enforce_mass_governor(empty_carrier_mass_kg=3.0, payload_mass_kg=6.5)
        assert r.eligibility == "MRT_INELIGIBLE_BY_MASS"
        assert "not enlarged" in r.reason.lower()
        assert "not substituted" in r.reason.lower()

    def test_shielding_insert_counts_toward_gross(self):
        r = mcc.enforce_mass_governor(empty_carrier_mass_kg=2.0, payload_mass_kg=2.0, shielding_insert_mass_kg=1.5)
        assert r.total_moving_mass_kg == pytest.approx(5.5)
        assert r.eligibility == "MRT_INELIGIBLE_BY_MASS"

    def test_negative_mass_rejected(self):
        with pytest.raises(ValueError):
            mcc.enforce_mass_governor(empty_carrier_mass_kg=-1.0, payload_mass_kg=2.0)

    def test_nan_mass_rejected(self):
        with pytest.raises(ValueError):
            mcc.enforce_mass_governor(empty_carrier_mass_kg=math.nan, payload_mass_kg=2.0)

    def test_inf_mass_rejected(self):
        with pytest.raises(ValueError):
            mcc.enforce_mass_governor(empty_carrier_mass_kg=math.inf, payload_mass_kg=2.0)

    def test_obsolete_heavy_nuclear_loaded_mass_ineligible(self):
        # The obsolete heavy nuclear loaded mass 18.5 kg must be MRT_INELIGIBLE.
        r = mcc.enforce_mass_governor(empty_carrier_mass_kg=12.0, payload_mass_kg=6.5)
        assert r.total_moving_mass_kg == pytest.approx(18.5)
        assert r.eligibility == "MRT_INELIGIBLE_BY_MASS"

    def test_obsolete_heavy_linen_loaded_mass_ineligible(self):
        r = mcc.enforce_mass_governor(empty_carrier_mass_kg=5.0, payload_mass_kg=12.0)
        assert r.total_moving_mass_kg == pytest.approx(17.0)
        assert r.eligibility == "MRT_INELIGIBLE_BY_MASS"


# ===========================================================================
# Section 7 -- PAYLOAD VOLUME GOVERNOR
# ===========================================================================

class TestVolumeGovernor:
    def test_no_dimensions_not_calibrated(self):
        v = mcc.qualify_payload_volume()
        assert v.qualification == "NOT_CALIBRATED"

    def test_fits_external_project_supplied(self):
        v = mcc.qualify_payload_volume(payload_length_m=0.15, payload_width_m=0.10, payload_height_m=0.08)
        assert v.qualification == "PROJECT_SUPPLIED"

    def test_exceeds_external_does_not_fit(self):
        v = mcc.qualify_payload_volume(payload_length_m=0.30, payload_width_m=0.10, payload_height_m=0.08)
        assert v.qualification == "DOES_NOT_FIT"

    def test_mass_eligibility_does_not_imply_volume(self):
        # A payload light enough by mass can still DOES_NOT_FIT by volume.
        mass = mcc.enforce_mass_governor(empty_carrier_mass_kg=2.0, payload_mass_kg=1.0)
        vol = mcc.qualify_payload_volume(payload_length_m=1.0, payload_width_m=0.5, payload_height_m=0.5)
        assert mass.eligibility == "MRT_ELIGIBLE_BY_MASS"
        assert vol.qualification == "DOES_NOT_FIT"

    def test_negative_dimension_rejected(self):
        with pytest.raises(ValueError):
            mcc.qualify_payload_volume(payload_length_m=-0.1, payload_width_m=0.1, payload_height_m=0.1)

    def test_external_envelope_reported(self):
        v = mcc.qualify_payload_volume()
        assert (v.external_length_m, v.external_width_m, v.external_height_m) == (0.200, 0.120, 0.100)


# ===========================================================================
# Section 8/39-41 -- MISSION ELIGIBILITY + NEGATIVE/POSITIVE CONTROLS
# ===========================================================================

class TestMissionEligibility:
    def test_linen_negative_control_excluded_even_below_mass(self):
        # Section 39: bulk linen excluded even if a contrived mass alone would fit.
        r = mcc.resolve_mission_eligibility(stream="CLEAN_LINEN", empty_carrier_mass_kg=2.5, payload_mass_kg=1.0)
        assert r.mrt_eligible is False
        assert r.fallback_mode == "MANUAL"

    def test_laundry_clean_linen_alias_excluded(self):
        r = mcc.resolve_mission_eligibility(stream="LAUNDRY_CLEAN_LINEN", empty_carrier_mass_kg=2.5, payload_mass_kg=1.0)
        assert r.mrt_eligible is False
        assert r.fallback_mode == "MANUAL"

    def test_no_robot_auto_inserted_for_excluded(self):
        r = mcc.resolve_mission_eligibility(stream="CLEAN_LINEN", empty_carrier_mass_kg=2.5, payload_mass_kg=1.0)
        assert r.fallback_mode == "MANUAL"  # never AGV/AMR/robot

    def test_blood_specimen_positive_control(self):
        # Section 40: compact blood/specimen within the gross-mass envelope.
        r = mcc.resolve_mission_eligibility(stream="SPECIMEN_BLOOD", empty_carrier_mass_kg=2.5, payload_mass_kg=2.0)
        assert r.mrt_eligible is True

    def test_blood_no_shielding_forced(self):
        # Non-radioactive mission: no shielding insert forced (default 0).
        r = mcc.resolve_mission_eligibility(stream="SPECIMEN_BLOOD", empty_carrier_mass_kg=2.5, payload_mass_kg=2.0)
        assert r.mass_result.total_moving_mass_kg == pytest.approx(4.5)  # 2.5 + 2.0, no shielding added

    def test_radiopharmaceutical_positive_control_with_shielding(self):
        # Section 41: compact radiopharmaceutical with localized shielding, within 5 kg.
        r = mcc.resolve_mission_eligibility(
            stream="RADIOPHARMACEUTICAL_NUCLEAR", empty_carrier_mass_kg=2.0, payload_mass_kg=1.0, shielding_insert_mass_kg=1.5,
        )
        assert r.mrt_eligible is True
        assert r.mass_result.total_moving_mass_kg == pytest.approx(4.5)

    def test_heavy_mission_ineligible_falls_back_manual(self):
        r = mcc.resolve_mission_eligibility(stream="PHARMACY_INFUSION", empty_carrier_mass_kg=3.0, payload_mass_kg=4.0)
        assert r.mrt_eligible is False
        assert r.fallback_mode == "MANUAL"

    def test_localized_shielding_only_on_radioactive(self):
        assert mcc.LOCALIZED_SHIELDING is True
        # eligible sets reflect radiopharmaceutical present, linen absent
        assert "RADIOPHARMACEUTICAL_NUCLEAR" in mcc.MRT_ELIGIBLE_MICRO_LOGISTICS
        assert "CLEAN_LINEN" not in mcc.MRT_ELIGIBLE_MICRO_LOGISTICS

    def test_excluded_set_contains_linen(self):
        assert "CLEAN_LINEN" in mcc.MRT_EXCLUDED_BULKY_LOGISTICS
        assert "LAUNDRY_CLEAN_LINEN" in mcc.MRT_EXCLUDED_BULKY_LOGISTICS


# ===========================================================================
# Section 42 -- GUIDEWAY COST CONTROL (two-way, never doubled)
# ===========================================================================

class TestGuidewayCostControl:
    def test_100m_two_way_is_250000(self):
        import canonical_spatial_authority as csa
        r = csa.compute_mrt_transport_only_capex(
            guideway_length_m=100.0, guideway_unit_cost_per_m=mcc.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M, carrier_count=0,
        )
        assert r.line_item("MRT guideway/trunk/branch/segment").capex == pytest.approx(250_000.0)

    def test_100m_not_500000_no_lane_doubling(self):
        assert 100.0 * mcc.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M == 250_000.0
        assert 100.0 * mcc.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M != 500_000.0

    def test_500m_two_way_is_1_250_000(self):
        assert 500.0 * mcc.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M == 1_250_000.0

    def test_guideway_length_semantics_documented(self):
        assert "not doubled" in mcc.GUIDEWAY_LENGTH_SEMANTICS.lower() or "not\ndoubled" in mcc.GUIDEWAY_LENGTH_SEMANTICS.lower()


# ===========================================================================
# Section 43 -- CARRIER CapEx CONTROL
# ===========================================================================

class TestCarrierCostControl:
    def test_20_carriers_is_40000(self):
        assert 20 * mcc.CARRIER_CAPEX_USD == 40_000.0

    def test_carrier_only_excludes_guideway(self):
        import canonical_spatial_authority as csa
        r = csa.compute_mrt_transport_only_capex(guideway_length_m=0.0, carrier_count=20, carrier_unit_cost=mcc.CARRIER_CAPEX_USD)
        assert r.line_item("MRT carriers").capex == pytest.approx(40_000.0)
        assert r.line_item("MRT guideway/trunk/branch/segment").capex == pytest.approx(0.0)


# ===========================================================================
# Section 44 -- MOTION ELECTRICITY CONTROL
# ===========================================================================

class TestMotionElectricityControl:
    def test_base_rate_per_carrier_km(self):
        assert mcc.motion_kwh_per_carrier_km(mcc.BASE_ACTIVE_POWER_KW) == pytest.approx(0.0416667, abs=1e-6)

    def test_low_high_stress_rates(self):
        assert mcc.motion_kwh_per_carrier_km(mcc.LOW_ACTIVE_POWER_KW) == pytest.approx(0.0208333, abs=1e-6)
        assert mcc.motion_kwh_per_carrier_km(mcc.HIGH_ACTIVE_POWER_KW) == pytest.approx(0.0833333, abs=1e-6)
        assert mcc.motion_kwh_per_carrier_km(mcc.STRESS_ACTIVE_POWER_KW) == pytest.approx(0.1388889, abs=1e-6)

    def test_base_300_carrier_km_is_12_5(self):
        assert mcc.motion_electricity_kwh_per_day(carrier_km_per_day=300.0, active_power_case="BASE") == pytest.approx(12.5)

    def test_canonical_speed_is_36_kmh(self):
        assert mcc.CANONICAL_SPEED_KM_PER_H == pytest.approx(36.0)

    def test_power_sensitivity_cases(self):
        assert mcc.MOTION_POWER_SENSITIVITY_KW == {"LOW": 0.75, "BASE": 1.5, "HIGH": 3.0, "STRESS": 5.0}

    def test_unknown_case_rejected(self):
        with pytest.raises(ValueError):
            mcc.motion_electricity_kwh_per_day(carrier_km_per_day=100.0, active_power_case="TURBO")


# ===========================================================================
# Section 45 -- ANNUAL ELECTRICITY CONTROL
# ===========================================================================

class TestAnnualElectricityControl:
    def test_annual_controlled_example(self):
        res = mcc.compute_mrt_annual_electricity(
            carrier_km_per_day=300.0, operating_days_per_year=365, active_power_case="BASE",
            standby_kwh_per_day=24.0, cooling_kwh_per_day=48.0, tariff_usd_per_kwh=0.15,
        )
        # motion 12.5 + standby 24 + cooling 48 = 84.5 kWh/day * 365 = 30842.5 kWh/yr
        assert res.total_known_kwh_per_year == pytest.approx(30_842.5)
        assert res.total_electricity_cost_usd_per_year == pytest.approx(4_626.375)

    def test_controls_left_uncalibrated_not_zero_filled(self):
        res = mcc.compute_mrt_annual_electricity(
            carrier_km_per_day=300.0, operating_days_per_year=365, active_power_case="BASE",
            standby_kwh_per_day=24.0, cooling_kwh_per_day=48.0,
        )
        assert res.controls_kwh_per_year == "NOT_CALIBRATED"
        assert "controls" in res.unknown_components

    def test_motion_only_never_zero_fills_others(self):
        res = mcc.compute_mrt_annual_electricity(carrier_km_per_day=300.0, operating_days_per_year=365)
        assert set(res.unknown_components) == {"standby", "controls", "cooling"}
        assert res.motion_kwh_per_year == pytest.approx(12.5 * 365)

    def test_physical_energy_separate_from_tariff(self):
        res = mcc.compute_mrt_annual_electricity(carrier_km_per_day=300.0, operating_days_per_year=365, tariff_usd_per_kwh=0.20)
        assert res.total_electricity_cost_usd_per_year == pytest.approx(res.total_known_kwh_per_year * 0.20)

    def test_project_supplied_tariff_preserved(self):
        res = mcc.compute_mrt_annual_electricity(
            carrier_km_per_day=300.0, operating_days_per_year=365, tariff_usd_per_kwh=0.11, tariff_source="PROJECT_SUPPLIED",
        )
        assert res.tariff_source == "PROJECT_SUPPLIED"
        assert res.tariff_usd_per_kwh == 0.11


# ===========================================================================
# Section 19 -- ELECTRICITY DOUBLE-COUNTING GUARD
# ===========================================================================

class TestNoDoubleCounting:
    def test_streams_separate(self):
        assert mcc.MRT_MOTION_ELECTRICITY_SEPARATE is True
        assert mcc.MRT_STANDBY_ELECTRICITY_SEPARATE is True
        assert mcc.MRT_CONTROLS_ELECTRICITY_SEPARATE is True
        assert mcc.MRT_COOLING_ELECTRICITY_SEPARATE is True

    def test_no_double_counting(self):
        assert mcc.MRT_ELECTRICITY_DOUBLE_COUNTING_PRESENT is False

    def test_standby_controls_cooling_not_calibrated(self):
        assert mcc.NETWORK_STANDBY_POWER_KW_STATUS == "NOT_CALIBRATED"
        assert mcc.CONTROLS_POWER_KW_STATUS == "NOT_CALIBRATED"
        assert mcc.GUIDEWAY_COOLING_POWER_KW_STATUS == "NOT_CALIBRATED"

    def test_energy_model_status_not_kinetic(self):
        assert "NOT kinetic" in mcc.MRT_ENERGY_MODEL_STATUS or "not kinetic" in mcc.MRT_ENERGY_MODEL_STATUS.lower()


# ===========================================================================
# Section 46 -- AUTOMATED-CONVENTIONAL OPEX FAIRNESS
# ===========================================================================

class TestAutomatedConventionalFairness:
    def test_agv_opex_components_not_zero(self):
        import conventional_transport_authority as cta
        agv = cta.DEFAULT_AGV_MODEL
        assert agv.annual_maintenance_opex > 0
        assert agv.annual_energy_opex > 0
        assert agv.residual_supervision_fte >= 0

    def test_pts_opex_components_not_zero(self):
        import conventional_transport_authority as cta
        pts = cta.DEFAULT_PTS_NETWORK
        assert pts.annual_maintenance_opex > 0
        assert pts.annual_energy_opex > 0

    def test_agv_annual_opex_includes_labor(self):
        import conventional_transport_authority as cta
        agv = cta.DEFAULT_AGV_MODEL
        opex = cta.agv_annual_opex(agv, fleet_size=2, loaded_annual_cost_per_fte=80_000.0)
        # 2*(4000+1500) + 0.1*80000 = 11000 + 8000 = 19000
        assert opex == pytest.approx(19_000.0)


# ===========================================================================
# Section 26 -- MANUAL OPEX PRESERVATION
# ===========================================================================

class TestManualPreservation:
    def test_manual_default_bulky_fallback(self):
        assert mcc.DEFAULT_BULKY_LOGISTICS_MODE == "MANUAL"

    def test_manual_opex_not_changed_by_mrt_correction(self):
        # The MRT correction touched only MRT authorities; manual/porter economics
        # remain governed by their own authority and are unaffected.
        import conventional_transport_authority as cta
        assert cta.DEFAULT_GENERAL_CART.annual_maintenance_opex == 40.0
        assert cta.DEFAULT_LINEN_CART.annual_maintenance_opex == 60.0


# ===========================================================================
# Section 47 -- MANUAL + MRT HYBRID CONTROL
# ===========================================================================

class TestManualMrtHybridControl:
    def test_specimen_mrt_linen_manual(self):
        specimen = mcc.resolve_mission_eligibility(stream="SPECIMEN_BLOOD", empty_carrier_mass_kg=2.5, payload_mass_kg=2.0)
        linen = mcc.resolve_mission_eligibility(stream="CLEAN_LINEN", empty_carrier_mass_kg=2.5, payload_mass_kg=1.0)
        assert specimen.mrt_eligible is True
        assert linen.mrt_eligible is False
        assert linen.fallback_mode == "MANUAL"

    def test_no_robot_inserted_in_mix(self):
        linen = mcc.resolve_mission_eligibility(stream="CLEAN_LINEN", empty_carrier_mass_kg=2.5, payload_mass_kg=1.0)
        assert linen.fallback_mode == "MANUAL"


# ===========================================================================
# Section 9/36 -- LEGACY-NAME COMPATIBILITY
# ===========================================================================

class TestLegacyNameCompatibility:
    def test_light_mrt_guideway_bound_to_canonical(self):
        import shared_mrt_multistream_authority as smx
        assert smx.LIGHT_MRT_GUIDEWAY_CAPEX_PER_M == mcc.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M == 2_500.0

    def test_energy_authority_carrier_capex_bound_to_canonical(self):
        import mrt_transport_energy_maintenance_authority as mtem
        assert mtem.MRT_CARRIER_CAPEX_USD.active_value == mcc.CARRIER_CAPEX_USD == 2_000.0

    def test_energy_authority_masses_bound_to_canonical(self):
        import mrt_transport_energy_maintenance_authority as mtem
        assert mtem.EMPTY_MRT_CARRIER_MASS_KG == mcc.EMPTY_CARRIER_MASS_TARGET_LOW_KG == 2.0
        assert mtem.MAX_MRT_PAYLOAD_KG == pytest.approx(3.0)
        assert mtem.FULLY_LOADED_MRT_CARRIER_MASS_KG == mcc.MAX_GROSS_MOVING_MASS_KG == 5.0

    def test_guideway_alias_tracks_canonical(self):
        import mrt_transport_energy_maintenance_authority as mtem
        assert mtem.MRT_GUIDEWAY_CAPEX_PER_M_USD == 2_500.0


# ===========================================================================
# Section 48 -- ACTIVE OLD-MASS GUARD
# ===========================================================================

class TestActiveOldMassGuard:
    def test_canonical_config_active_no_12kg(self):
        # ACTIVE_CURRENT_MRT_12KG_PRESENT = NO in the canonical authority surface.
        c = mcc.CANONICAL_MRT
        actives = (c.max_gross_moving_mass_kg, c.empty_carrier_mass_target_low_kg, c.empty_carrier_mass_target_high_kg, c.payload_target_low_kg, c.payload_target_high_kg)
        assert 12.0 not in actives

    def test_canonical_config_active_no_17kg(self):
        c = mcc.CANONICAL_MRT
        actives = (c.max_gross_moving_mass_kg, c.empty_carrier_mass_target_low_kg, c.empty_carrier_mass_target_high_kg, c.payload_target_low_kg, c.payload_target_high_kg)
        assert 17.0 not in actives

    def test_canonical_config_active_no_20kg(self):
        c = mcc.CANONICAL_MRT
        actives = (c.max_gross_moving_mass_kg, c.empty_carrier_mass_target_low_kg, c.empty_carrier_mass_target_high_kg, c.payload_target_low_kg, c.payload_target_high_kg)
        assert 20.0 not in actives

    def test_energy_authority_no_obsolete_carrier_capex_5000(self):
        import mrt_transport_energy_maintenance_authority as mtem
        assert mtem.MRT_CARRIER_CAPEX_USD.active_value != 5_000.0

    def test_shared_authority_no_obsolete_guideway_2000(self):
        import shared_mrt_multistream_authority as smx
        assert smx.LIGHT_MRT_GUIDEWAY_CAPEX_PER_M != 2_000.0


# ===========================================================================
# Section 35 -- NO FORCED MRT WIN
# ===========================================================================

class TestNoForcedMrtWin:
    def test_carrier_capex_not_below_canonical(self):
        # The correction sets carrier CapEx to exactly the canonical $2,000 --
        # never lower to make MRT cheaper.
        assert mcc.CARRIER_CAPEX_USD == 2_000.0

    def test_guideway_capex_not_below_canonical(self):
        # Corrected UP to $2,500/m (from $2,000), not reduced to favor MRT.
        assert mcc.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M == 2_500.0

    def test_guideway_correction_raised_not_lowered_cost(self):
        # $2,500 > the prior $2,000 -- the correction did NOT reduce MRT cost.
        assert mcc.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M > 2_000.0

    def test_no_negative_or_zero_canonical_costs(self):
        assert mcc.CARRIER_CAPEX_USD > 0
        assert mcc.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M > 0


# ===========================================================================
# Section 33-34 -- EXPERIMENT RERUN INVENTORY (documented flags)
# ===========================================================================

class TestExperimentRerunInventory:
    """These invariants lock the contamination-inventory conclusions so a
    future reader/CI cannot silently forget that the Part 3E-family MRT
    economics were superseded by this correction."""

    def test_part3e_reports_exist(self):
        import os
        for name in (
            "RADIONUCLIDE_AWARE_ARCHITECTURE_AUTHORITY_PART_3E.md",
            "PART_3E_1_RADIONUCLIDE_EXPERIMENT_CAMPAIGN_REPORT.md",
            "PART_3E_2_DECISION_ENVELOPE_AND_CROSSOVER_REPORT.md",
        ):
            assert os.path.exists(name), f"missing {name}"

    def test_authority_doc_records_rerun_flags(self):
        import os
        doc = "MRT_CANONICAL_CONFIGURATION_AUTHORITY.md"
        assert os.path.exists(doc)
        text = open(doc, encoding="utf-8").read()
        assert "PART3E_RERUN_REQUIRED" in text
        assert "PART3E_1_RERUN_REQUIRED" in text
        assert "PART3E_2_RERUN_REQUIRED" in text
        assert "SHORT_HALF_LIFE_EXPERIMENT_RERUN_REQUIRED" in text

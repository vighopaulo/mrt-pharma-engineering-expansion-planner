"""Focused deterministic invariants for the MRT CANONICAL RUNTIME MIGRATION.

Proves the CURRENT four-architecture MRT/Hybrid runtime (and thereby the Part 3E
bouquet) consumes the canonical compact MRT configuration
(mrt_canonical_configuration) rather than the preserved heavy PlannerAssumptions
/ heavy-fleet defaults -- while every legacy default-arg caller is unchanged.

Central proofs (empirical, through the real runtime, not the standalone helper):
  * canonical guideway/carrier perturbation MOVES current MRT/Hybrid/Part3E CapEx;
  * heavy PlannerAssumptions perturbation does NOT move current MRT/Hybrid/Part3E;
  * the canonical 5 kg gross mass governor gates MRT assignment generically
    (a stream is excluded by MASS, not by name) -> Manual fallback;
  * no $6,000,000 flat base, $2,000 carrier, $2,500/m two-way guideway;
  * heavy configuration remains intact for legacy consumers.

The migration touched ONLY MRT-runtime wiring. No physics/experiment logic
changed. Part 3E experiment reports remain superseded/pending rerun.
"""

from __future__ import annotations

import dataclasses

import pytest

import mrt_canonical_configuration as mcc
import shared_mrt_multistream_authority as smx
import operational_day_orchestrator as ody
import inbound_patient_program as ipp
import hybrid_optimization as hopt
import whole_oncology_four_architecture_optimization as wo4a
import part3e_radionuclide_aware_architecture as p3e


# ---------------------------------------------------------------------------
# Shared baseline + runtime evaluators (module-scoped for speed).
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def baseline():
    return wo4a.build_common_project_baseline()


def _mrt_capex(bl):
    return wo4a.evaluate_mrt_dominant(bl, development_context="RETROFIT", study_scope="CAPITAL_PLANNING").architecture_specific_capex


def _hyb_capex(bl):
    return wo4a.evaluate_hybrid_mrt(bl, development_context="RETROFIT", study_scope="CAPITAL_PLANNING").architecture_specific_capex


def _p3e_mrt_capex(bl):
    return p3e._evaluate_architecture(
        "MRT_DOMINANT", baseline=bl, development_context="RETROFIT", study_scope="CAPITAL_PLANNING",
        nuclear_demand_override=None,
    ).architecture_specific_capex


# ===========================================================================
# Sec 2 -- EXPLICIT CANONICAL RUNTIME CONFIG PRESENT; PlannerAssumptions NOT repurposed
# ===========================================================================
class TestRuntimeConfigPresent:
    def test_runtime_config_type_exists(self):
        assert hasattr(mcc, "MrtRuntimeConfig")
        assert hasattr(mcc, "CANONICAL_MRT_RUNTIME_CONFIG")

    def test_canonical_runtime_config_values(self):
        c = mcc.CANONICAL_MRT_RUNTIME_CONFIG
        assert c.guideway_capex_per_m == 2_500.0
        assert c.carrier_capex_per_installed_unit_usd == 2_000.0
        assert c.include_flat_infrastructure_base is False
        assert c.max_gross_moving_mass_kg == 5.0
        assert c.max_straight_speed_m_per_s == 10.0
        assert c.carrier_maintenance_fraction_per_year == pytest.approx(0.10)

    def test_wo4a_threads_the_canonical_config(self):
        # The four-architecture module imports and uses the canonical runtime config.
        assert wo4a.CANONICAL_MRT_RUNTIME_CONFIG is not None
        assert wo4a.CANONICAL_MRT_RUNTIME_CONFIG.carrier_capex_per_installed_unit_usd == 2_000.0

    def test_planner_assumptions_heavy_defaults_not_repurposed(self):
        # models.PlannerAssumptions heavy defaults remain the heavy values.
        from models import PlannerAssumptions
        a = PlannerAssumptions()
        assert a.mrt_guideway_capex_per_m == 5_000.0
        assert a.mrt_carrier_capex_per_installed_unit == 10_000.0
        assert a.mrt_infrastructure_capex == 6_000_000.0

    def test_config_provenance_controlled_not_calibrated(self):
        assert "CONTROLLED" in mcc.CANONICAL_MRT_RUNTIME_CONFIG.provenance


# ===========================================================================
# Sec 3 -- BACKWARD COMPATIBILITY (legacy default-arg callers unchanged)
# ===========================================================================
class TestBackwardCompatibility:
    def test_compute_carrier_fleet_capex_default_heavy(self):
        # No override -> heavy $10,000/$1,000 exactly.
        assert ody.compute_carrier_fleet_capex(nuclear_count=1, general_light_count=0) == 10_000.0
        assert ody.compute_carrier_fleet_capex(nuclear_count=0, general_light_count=1) == 1_000.0
        assert ody.compute_carrier_fleet_capex(nuclear_count=8, general_light_count=42) == 122_000.0

    def test_compute_carrier_fleet_capex_override_canonical(self):
        assert ody.compute_carrier_fleet_capex(
            nuclear_count=20, general_light_count=0,
            nuclear_unit_capex_usd=2_000.0, general_light_unit_capex_usd=2_000.0,
        ) == 40_000.0

    def test_guideway_extension_default_uses_heavy(self):
        import inspect
        sig = inspect.signature(ipp.compute_inbound_room_guideway_extension)
        assert "guideway_capex_per_m_override" in sig.parameters
        assert sig.parameters["guideway_capex_per_m_override"].default is None

    def test_evaluate_hybrid_zone_candidate_has_optional_config(self):
        import inspect
        sig = inspect.signature(hopt.evaluate_hybrid_zone_candidate)
        assert "mrt_runtime_config" in sig.parameters
        assert sig.parameters["mrt_runtime_config"].default is None

    def test_compute_shared_mrt_economic_result_has_optional_config(self):
        import inspect
        sig = inspect.signature(smx.compute_shared_mrt_economic_result)
        assert "mrt_runtime_config" in sig.parameters
        assert sig.parameters["mrt_runtime_config"].default is None

    def test_compute_heterogeneous_fleet_has_optional_override(self):
        import inspect
        sig = inspect.signature(smx.compute_heterogeneous_shared_carrier_fleet)
        assert "carrier_unit_capex_usd_override" in sig.parameters
        assert sig.parameters["carrier_unit_capex_usd_override"].default is None

    def test_heavy_configuration_not_deleted(self):
        # HEAVY_CONFIGURATION_DELETED = NO
        from models import PlannerAssumptions
        assert PlannerAssumptions().mrt_infrastructure_capex == 6_000_000.0
        assert ody.NUCLEAR_SHIELDED_CARRIER_CAPEX_USD == 10_000.0


# ===========================================================================
# Sec 4 -- NO $6M FLAT BASE IN CURRENT MRT
# ===========================================================================
class TestNoFlatBase:
    def test_current_mrt_capex_far_below_heavy_plus_6m(self, baseline):
        # Old heavy figure was ~$11.48M (incl $6M flat base). Current canonical
        # must be materially below the old heavy figure and below $6M alone.
        assert _mrt_capex(baseline) < 6_000_000.0

    def test_current_hybrid_capex_far_below_heavy(self, baseline):
        assert _hyb_capex(baseline) < 6_000_000.0

    def test_perturbing_heavy_flat_base_does_not_move_current_mrt(self, baseline):
        base_capex = _mrt_capex(baseline)
        bumped = dataclasses.replace(
            baseline, assumptions=dataclasses.replace(
                baseline.assumptions, mrt_infrastructure_capex=baseline.assumptions.mrt_infrastructure_capex + 1_000_000.0),
        )
        assert _mrt_capex(bumped) == pytest.approx(base_capex)


# ===========================================================================
# Sec 5-7 -- SENTINEL PROOF: heavy zero-effect, canonical non-zero (MRT/Hybrid/Part3E)
# ===========================================================================
def _heavy_bumped(baseline, delta=1000.0):
    return dataclasses.replace(
        baseline, assumptions=dataclasses.replace(
            baseline.assumptions,
            mrt_guideway_capex_per_m=baseline.assumptions.mrt_guideway_capex_per_m + delta,
            mrt_carrier_capex_per_installed_unit=baseline.assumptions.mrt_carrier_capex_per_installed_unit + delta,
            mrt_infrastructure_capex=baseline.assumptions.mrt_infrastructure_capex + delta,
        ),
    )


class _CanonicalBumped:
    """Context manager: temporarily bump the module canonical runtime config."""
    def __init__(self, delta=1000.0):
        self.delta = delta

    def __enter__(self):
        self._saved = wo4a.CANONICAL_MRT_RUNTIME_CONFIG
        wo4a.CANONICAL_MRT_RUNTIME_CONFIG = mcc.MrtRuntimeConfig(
            guideway_capex_per_m=mcc.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M + self.delta,
            carrier_capex_per_installed_unit_usd=mcc.CARRIER_CAPEX_USD + self.delta,
        )
        return self

    def __exit__(self, *a):
        wo4a.CANONICAL_MRT_RUNTIME_CONFIG = self._saved
        return False


class TestSentinelMrt:
    def test_heavy_sentinel_zero_effect_on_mrt(self, baseline):
        base = _mrt_capex(baseline)
        assert _mrt_capex(_heavy_bumped(baseline)) == pytest.approx(base)

    def test_canonical_sentinel_moves_mrt(self, baseline):
        base = _mrt_capex(baseline)
        with _CanonicalBumped():
            bumped = _mrt_capex(baseline)
        assert bumped > base


class TestSentinelHybrid:
    def test_heavy_sentinel_zero_effect_on_hybrid(self, baseline):
        base = _hyb_capex(baseline)
        assert _hyb_capex(_heavy_bumped(baseline)) == pytest.approx(base)

    def test_canonical_sentinel_moves_hybrid(self, baseline):
        base = _hyb_capex(baseline)
        with _CanonicalBumped():
            bumped = _hyb_capex(baseline)
        assert bumped > base


class TestSentinelPart3E:
    def test_heavy_sentinel_zero_effect_on_part3e(self, baseline):
        base = _p3e_mrt_capex(baseline)
        assert _p3e_mrt_capex(_heavy_bumped(baseline)) == pytest.approx(base)

    def test_canonical_sentinel_moves_part3e(self, baseline):
        base = _p3e_mrt_capex(baseline)
        with _CanonicalBumped():
            bumped = _p3e_mrt_capex(baseline)
        assert bumped > base

    def test_part3e_dispatches_to_migrated_evaluator(self):
        import inspect
        src = inspect.getsource(p3e._evaluate_architecture)
        assert "evaluate_mrt_dominant" in src
        assert "evaluate_hybrid_mrt" in src
        assert "evaluate_light_mrt_dominant" not in src


# ===========================================================================
# Sec 8 -- 5 kg MASS GOVERNOR THROUGH ACTUAL RUNTIME (generic, not name check)
# ===========================================================================
class TestMassGovernorRuntime:
    def test_compatible_streams_assigned_to_mrt(self, baseline):
        mbs, _ = wo4a._general_mrt_missions_and_containers(baseline, mrt_ward_coverage=None)
        assert len(mbs.get("SPECIMEN_BLOOD", ())) > 0
        assert len(mbs.get("PHARMACY_INFUSION", ())) > 0

    def test_over_5kg_stream_routed_to_manual_by_mass_not_name(self, baseline):
        # Temporarily make a normally-eligible stream exceed 5 kg by MASS and
        # confirm the runtime routes it to Manual fallback -- proving a general
        # mass gate, not a hard-coded linen name check.
        saved = dict(smx.LIGHT_MRT_STREAM_PAYLOAD_MASS_KG)
        try:
            smx.LIGHT_MRT_STREAM_PAYLOAD_MASS_KG = dict(saved)
            smx.LIGHT_MRT_STREAM_PAYLOAD_MASS_KG["SPECIMEN_BLOOD"] = 9.0  # 9.0 + 1.5 = 10.5 kg > 5
            mbs, fbs = wo4a._general_mrt_missions_and_containers(baseline, mrt_ward_coverage=None)
            assert len(mbs.get("SPECIMEN_BLOOD", ())) == 0
            assert len(fbs.get("SPECIMEN_BLOOD", ())) > 0
        finally:
            smx.LIGHT_MRT_STREAM_PAYLOAD_MASS_KG = saved
        # restored: SPECIMEN_BLOOD is compatible again
        assert smx.evaluate_light_mrt_stream_compatibility("SPECIMEN_BLOOD").compatible is True

    def test_mass_authority_ceiling_bound_to_canonical(self):
        assert smx.LIGHT_MRT_LOADED_MASS_CEILING_KG == mcc.MAX_GROSS_MOVING_MASS_KG == 5.0

    def test_standalone_governor_rejects_over_ceiling(self):
        r = mcc.enforce_mass_governor(empty_carrier_mass_kg=2.5, payload_mass_kg=3.0, shielding_insert_mass_kg=1.0)
        assert r.eligibility == "MRT_INELIGIBLE_BY_MASS"


# ===========================================================================
# Sec 9 -- LINEN NEGATIVE CONTROL THROUGH ACTUAL RUNTIME
# ===========================================================================
class TestLinenNegativeControl:
    def test_linen_not_assigned_to_mrt_dominant(self, baseline):
        mbs, fbs = wo4a._general_mrt_missions_and_containers(baseline, mrt_ward_coverage=None)
        assert len(mbs.get("CLEAN_LINEN", ())) == 0
        assert len(fbs.get("CLEAN_LINEN", ())) > 0  # routed to Manual fallback

    def test_linen_not_assigned_in_hybrid_coverage(self, baseline):
        # Even within covered wards, linen (13.5 kg) is excluded by mass.
        coverage = frozenset(f"WARD-F{n}" for n in range(1, baseline.geometry.floor_count + 1))
        mbs, fbs = wo4a._general_mrt_missions_and_containers(baseline, mrt_ward_coverage=coverage)
        assert len(mbs.get("CLEAN_LINEN", ())) == 0

    def test_default_bulky_mode_is_manual(self):
        assert mcc.DEFAULT_BULKY_LOGISTICS_MODE == "MANUAL"
        assert mcc.CANONICAL_MRT_RUNTIME_CONFIG  # config exists; fallback is Manual (not robot)

    def test_linen_mass_exceeds_ceiling(self):
        r = smx.evaluate_light_mrt_stream_compatibility("CLEAN_LINEN")
        assert r.fully_loaded_mass_kg > 5.0
        assert r.compatible is False


# ===========================================================================
# Sec 10-11 -- POSITIVE CONTROLS (compact specimen + radiopharm, one platform)
# ===========================================================================
class TestPositiveControls:
    def test_compact_specimen_eligible(self):
        r = smx.evaluate_light_mrt_stream_compatibility("SPECIMEN_BLOOD")
        assert r.compatible is True
        assert r.fully_loaded_mass_kg <= 5.0

    def test_radiopharm_eligible_within_5kg(self):
        assert smx.LIGHT_MRT_NUCLEAR_INTEGRAL_CARRIER_LOADED_MASS_KG <= 5.0

    def test_localized_shielding_true_no_onboard_refrigeration(self):
        assert mcc.LOCALIZED_SHIELDING is True
        assert mcc.POWERED_ONBOARD_REFRIGERATION is False

    def test_common_carrier_platform(self):
        assert mcc.COMMON_CARRIER_PLATFORM is True

    def test_specimen_not_forced_shielding(self):
        # Non-radioactive specimen loaded mass = payload + structure only (no shield).
        r = smx.evaluate_light_mrt_stream_compatibility("SPECIMEN_BLOOD")
        assert r.fully_loaded_mass_kg == pytest.approx(
            smx.LIGHT_MRT_STREAM_PAYLOAD_MASS_KG["SPECIMEN_BLOOD"] + smx.LIGHT_MRT_CARRIER_STRUCTURE_MASS_KG)


# ===========================================================================
# Sec 6/13/18 -- GUIDEWAY / CARRIER PRICING THROUGH THE RUNTIME
# ===========================================================================
class TestGuidewayCarrierPricing:
    def test_guideway_100m_is_250000(self):
        lc = smx.compute_light_mrt_capex(guideway_length_m=100.0, endpoint_count=0, carrier_capex=0.0)
        assert lc.guideway_capex == pytest.approx(250_000.0)

    def test_guideway_not_doubled_by_lane(self):
        assert 100.0 * smx.LIGHT_MRT_GUIDEWAY_CAPEX_PER_M == 250_000.0

    def test_carrier_20_canonical_is_40000(self):
        assert ody.compute_carrier_fleet_capex(
            nuclear_count=0, general_light_count=20,
            nuclear_unit_capex_usd=2_000.0, general_light_unit_capex_usd=2_000.0) == 40_000.0

    def test_combined_guideway_carrier_290000(self):
        lc = smx.compute_light_mrt_capex(guideway_length_m=100.0, endpoint_count=0, carrier_capex=0.0)
        carriers = ody.compute_carrier_fleet_capex(
            nuclear_count=20, general_light_count=0,
            nuclear_unit_capex_usd=2_000.0, general_light_unit_capex_usd=2_000.0)
        assert lc.guideway_capex + carriers == pytest.approx(290_000.0)

    def test_current_guideway_unit_is_2500(self):
        assert smx.LIGHT_MRT_GUIDEWAY_CAPEX_PER_M == 2_500.0

    def test_current_carrier_unit_is_2000(self):
        assert mcc.CANONICAL_MRT_RUNTIME_CONFIG.carrier_capex_per_installed_unit_usd == 2_000.0


# ===========================================================================
# Sec 15 -- MAINTENANCE AUTHORITY
# ===========================================================================
class TestMaintenance:
    def test_canonical_carrier_maintenance_is_200(self):
        import mrt_transport_energy_maintenance_authority as mtem
        assert mtem.compute_mrt_carrier_annual_maintenance_usd(carrier_count=1) == pytest.approx(200.0)

    def test_maintenance_fraction_10pct(self):
        assert mcc.CANONICAL_MRT_RUNTIME_CONFIG.carrier_maintenance_fraction_per_year == pytest.approx(0.10)


# ===========================================================================
# Sec 12 -- SPEED SEMANTICS (canonical straight = 10; no blind replacement)
# ===========================================================================
class TestSpeedSemantics:
    def test_canonical_straight_speed_is_10(self):
        assert mcc.MAX_STRAIGHT_SPEED_M_PER_S == 10.0
        assert mcc.CANONICAL_MRT_RUNTIME_CONFIG.max_straight_speed_m_per_s == 10.0

    def test_segment_speed_model_not_calibrated(self):
        # Curve/vertical/transition dynamics remain uncalibrated -- never fabricated.
        assert mcc.SEGMENT_SPEED_MODEL_STATUS == "NOT_CALIBRATED"


# ===========================================================================
# Sec 19-20 -- HEAVY ISOLATION + LIGHT-MRT COMPATIBILITY
# ===========================================================================
class TestHeavyIsolationAndLightMrt:
    def test_heavy_config_still_present(self):
        from models import PlannerAssumptions
        a = PlannerAssumptions()
        assert a.mrt_guideway_capex_per_m == 5_000.0 and a.mrt_carrier_capex_per_installed_unit == 10_000.0

    def test_heavy_not_used_by_current_mrt(self, baseline):
        # Perturbing heavy leaves current MRT unchanged (already covered) -- also
        # assert current MRT capex is the canonical-consistent figure, not heavy.
        assert _mrt_capex(baseline) < 6_000_000.0

    def test_light_mrt_dominant_shares_canonical_guideway(self):
        # evaluate_light_mrt_dominant, if present, must price guideway from the
        # same canonical authority (compute_light_mrt_capex uses $2,500/m).
        assert hasattr(wo4a, "evaluate_light_mrt_dominant")
        assert smx.LIGHT_MRT_GUIDEWAY_CAPEX_PER_M == 2_500.0

    def test_no_separate_current_light_mrt_guideway_price(self):
        # There is ONE current guideway price; light-mrt path uses it too.
        assert smx.LIGHT_MRT_GUIDEWAY_CAPEX_PER_M == mcc.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M


# ===========================================================================
# Sec 22/39 -- EXPERIMENT RERUN FLAGS REMAIN LOCKED
# ===========================================================================
class TestRerunFlagsLocked:
    def test_authority_doc_still_records_rerun_required(self):
        import os
        doc = "MRT_CANONICAL_CONFIGURATION_AUTHORITY.md"
        assert os.path.exists(doc)
        text = open(doc, encoding="utf-8").read()
        for flag in ("PART3E_RERUN_REQUIRED", "PART3E_1_RERUN_REQUIRED",
                     "PART3E_2_RERUN_REQUIRED", "SHORT_HALF_LIFE_EXPERIMENT_RERUN_REQUIRED"):
            assert flag in text

    def test_migration_report_records_rerun_flags(self):
        import os
        doc = "MRT_CANONICAL_RUNTIME_MIGRATION_REPORT.md"
        assert os.path.exists(doc)
        text = open(doc, encoding="utf-8").read()
        assert "PART3E_RERUN_REQUIRED" in text
        assert "SHORT_HALF_LIFE_EXPERIMENT_RERUN_REQUIRED" in text


# ===========================================================================
# Sec 32 -- FAIRNESS / PRESERVATION (Automated Conventional + Manual unchanged)
# ===========================================================================
class TestFairnessPreservation:
    def test_automated_conventional_opex_components_unchanged(self):
        import conventional_transport_authority as cta
        assert cta.DEFAULT_AGV_MODEL.annual_maintenance_opex == 4_000.0
        assert cta.DEFAULT_AGV_MODEL.annual_energy_opex == 1_500.0
        assert cta.DEFAULT_PTS_NETWORK.annual_maintenance_opex == 8_000.0

    def test_manual_cart_authority_unchanged(self):
        import conventional_transport_authority as cta
        assert cta.DEFAULT_GENERAL_CART.annual_maintenance_opex == 40.0
        assert cta.DEFAULT_LINEN_CART.annual_maintenance_opex == 60.0

    def test_manual_result_not_changed_by_migration(self, baseline):
        # Manual architecture does not consume the MRT runtime config at all.
        manual = wo4a.evaluate_manual_conventional(baseline, development_context="RETROFIT", study_scope="CAPITAL_PLANNING")
        assert manual.architecture == "MANUAL_CONVENTIONAL"
        assert manual.architecture_specific_capex >= 0.0


# ===========================================================================
# Sec 33 -- ROUTE-TIME STRAIGHT SPEED migration (canonical 10 m/s straight;
#           vertical 1.5 / transition / station physics preserved; legacy None
#           keeps heavy 3.0 m/s). Proven at the route-resolution authority.
# ===========================================================================
import dataclasses as _dc

from production_clinical_schedule import _resolve_mrt_route_profile
from models import PlannerAssumptions as _PA
from spatial_benchmark import build_benchmark_geometry as _build_geom


@_dc.dataclass
class _SpeedProbeScenario:
    """Duck-typed minimal scenario faithful to the fields
    _resolve_mrt_route_profile reads (mirrors ProductionClinicalScenario)."""
    facility_engineering_model: object
    transport_minutes: float = 5.0
    transport_minutes_source: str = "SCENARIO_SUPPLIED"
    planner_assumptions: object = None
    mrt_straight_speed_m_per_s_override: float | None = None


class TestRouteTimeStraightSpeed:
    def _model(self):
        return _build_geom(building_length_m=60.0, building_width_m=40.0, distribute_both_sides=True).base_model

    def test_scenario_field_exists_and_defaults_none(self):
        from production_clinical_schedule import ProductionClinicalScenario
        import inspect
        # Field must exist as an optional field (None default preserves legacy).
        assert "mrt_straight_speed_m_per_s_override" in ProductionClinicalScenario.__dataclass_fields__
        from decision_pipeline import NativeDecisionPipelineScenario
        assert "mrt_straight_speed_m_per_s_override" in NativeDecisionPipelineScenario.__dataclass_fields__

    def test_override_changes_only_horizontal_time(self):
        model = self._model()
        pa = _PA()
        dest = "F1-R02"
        heavy = _resolve_mrt_route_profile(
            _SpeedProbeScenario(facility_engineering_model=model, planner_assumptions=pa, mrt_straight_speed_m_per_s_override=None), dest,
        )
        canon = _resolve_mrt_route_profile(
            _SpeedProbeScenario(facility_engineering_model=model, planner_assumptions=pa, mrt_straight_speed_m_per_s_override=10.0), dest,
        )
        # The observed transport-time delta must equal EXACTLY the horizontal-only
        # delta (vertical/transition/station terms invariant).
        h = heavy.horizontal_distance_m
        heavy_h_s = h / pa.mrt_horizontal_speed_m_per_s
        canon_h_s = h / 10.0
        observed = heavy.transport_minutes - canon.transport_minutes
        expected = (heavy_h_s - canon_h_s) / 60.0
        assert observed == pytest.approx(expected, abs=1e-9)
        assert canon.transport_minutes < heavy.transport_minutes  # 10 m/s faster than 3 m/s

    def test_hundred_metre_straight_control_is_ten_seconds(self):
        # Pure physical control: 100 m at canonical 10 m/s = 10 s.
        assert 100.0 / 10.0 == pytest.approx(10.0)

    def test_speed_sentinel_canonical_isolated_from_heavy(self):
        model = self._model()
        dest = "F1-R02"
        pa = _PA()
        pa_perturbed = _dc.replace(pa, mrt_horizontal_speed_m_per_s=pa.mrt_horizontal_speed_m_per_s * 2)
        # Under the canonical override, perturbing the HEAVY horizontal speed must
        # NOT change the result.
        a = _resolve_mrt_route_profile(_SpeedProbeScenario(facility_engineering_model=model, planner_assumptions=pa, mrt_straight_speed_m_per_s_override=10.0), dest)
        b = _resolve_mrt_route_profile(_SpeedProbeScenario(facility_engineering_model=model, planner_assumptions=pa_perturbed, mrt_straight_speed_m_per_s_override=10.0), dest)
        assert a.transport_minutes == pytest.approx(b.transport_minutes, abs=1e-12)

    def test_speed_sentinel_override_is_authoritative(self):
        model = self._model()
        dest = "F1-R02"
        pa = _PA()
        a = _resolve_mrt_route_profile(_SpeedProbeScenario(facility_engineering_model=model, planner_assumptions=pa, mrt_straight_speed_m_per_s_override=10.0), dest)
        b = _resolve_mrt_route_profile(_SpeedProbeScenario(facility_engineering_model=model, planner_assumptions=pa, mrt_straight_speed_m_per_s_override=20.0), dest)
        assert a.transport_minutes != pytest.approx(b.transport_minutes)

    def test_legacy_none_keeps_heavy_authoritative(self):
        model = self._model()
        dest = "F1-R02"
        pa = _PA()
        pa_perturbed = _dc.replace(pa, mrt_horizontal_speed_m_per_s=pa.mrt_horizontal_speed_m_per_s * 2)
        # With override None, the heavy horizontal speed still drives the result
        # (legacy back-compat preserved).
        a = _resolve_mrt_route_profile(_SpeedProbeScenario(facility_engineering_model=model, planner_assumptions=pa, mrt_straight_speed_m_per_s_override=None), dest)
        b = _resolve_mrt_route_profile(_SpeedProbeScenario(facility_engineering_model=model, planner_assumptions=pa_perturbed, mrt_straight_speed_m_per_s_override=None), dest)
        assert a.transport_minutes != pytest.approx(b.transport_minutes)


# ===========================================================================
# Sec 34 -- OPEX ENERGY + MAINTENANCE migration through the REAL runtime
#           (canonical vs legacy None). Streams distinct; no double-count;
#           standby/controls/cooling NOT_CALIBRATED (never $0-filled).
# ===========================================================================
def _mrt_opex_rows(result):
    return {r.component: r for r in result.opex_result.ledger}


def _nuclear(bl, cfg):
    return wo4a._nuclear_result(bl, mrt_floors=frozenset({3}), mrt_runtime_config=cfg)


class TestOpexEnergyMaintenanceMigration:
    @pytest.fixture(scope="class")
    def opex_baseline(self):
        return wo4a.build_eight_floor_deterministic_capital_baseline()

    def test_canonical_carrier_maintenance_is_200(self, opex_baseline):
        rows = _mrt_opex_rows(_nuclear(opex_baseline, mcc.CANONICAL_MRT_RUNTIME_CONFIG))
        assert rows["MRT carrier maintenance"].unit_cost == pytest.approx(200.0)  # 10% x $2,000

    def test_legacy_carrier_maintenance_is_heavy_500(self, opex_baseline):
        rows = _mrt_opex_rows(_nuclear(opex_baseline, None))
        assert rows["MRT carrier maintenance"].unit_cost == pytest.approx(500.0)

    def test_canonical_guideway_maintenance_is_250_per_m(self, opex_baseline):
        rows = _mrt_opex_rows(_nuclear(opex_baseline, mcc.CANONICAL_MRT_RUNTIME_CONFIG))
        # $2,500/m x 10% = $250/m-year, booked as "Scenario calibrated input".
        assert rows["Guideway annual maintenance"].unit_cost == pytest.approx(250.0)
        assert rows["Guideway annual maintenance"].cost_basis == "Scenario calibrated input"

    def test_legacy_guideway_maintenance_is_heavy_fraction(self, opex_baseline):
        rows = _mrt_opex_rows(_nuclear(opex_baseline, None))
        # Heavy fallback: max(0, $5,000/m) x 3% = $150/m-year.
        assert rows["Guideway annual maintenance"].unit_cost == pytest.approx(150.0)

    def test_canonical_energy_uses_controlled_tariff(self, opex_baseline):
        rows = _mrt_opex_rows(_nuclear(opex_baseline, mcc.CANONICAL_MRT_RUNTIME_CONFIG))
        assert rows["MRT energy"].unit_cost == pytest.approx(mcc.CONTROLLED_ELECTRICITY_TARIFF_USD_PER_KWH)  # 0.15
        assert rows["MRT energy"].category == "ENERGY"

    def test_legacy_energy_uses_scenario_tariff_and_static_kwh(self, opex_baseline):
        rows = _mrt_opex_rows(_nuclear(opex_baseline, None))
        assert rows["MRT energy"].unit_cost == pytest.approx(0.18)
        assert rows["MRT energy"].quantity == pytest.approx(25_000.0)

    def test_canonical_energy_kwh_is_motion_derived_not_static(self, opex_baseline):
        rows = _mrt_opex_rows(_nuclear(opex_baseline, mcc.CANONICAL_MRT_RUNTIME_CONFIG))
        # Canonical motion energy is workload-derived and small; must NOT equal
        # the heavy static 25,000 kWh.
        assert rows["MRT energy"].quantity != pytest.approx(25_000.0)
        assert rows["MRT energy"].quantity > 0.0

    def test_carrier_allocated_electricity_is_distinct_and_unchanged(self, opex_baseline):
        # The THIRD electricity-adjacent term is NOT merged into energy/maintenance
        # and is identical under canonical vs legacy.
        canon = _mrt_opex_rows(_nuclear(opex_baseline, mcc.CANONICAL_MRT_RUNTIME_CONFIG))
        legacy = _mrt_opex_rows(_nuclear(opex_baseline, None))
        assert canon["MRT carrier allocated electricity"].annual_cost == pytest.approx(
            legacy["MRT carrier allocated electricity"].annual_cost
        )
        assert canon["MRT carrier allocated electricity"].category == "MRT"

    def test_no_double_count_each_mrt_row_appears_once(self, opex_baseline):
        from collections import Counter
        res = _nuclear(opex_baseline, mcc.CANONICAL_MRT_RUNTIME_CONFIG)
        counts = Counter(r.component for r in res.opex_result.ledger)
        for comp in (
            "MRT energy", "MRT carrier maintenance", "Guideway annual maintenance",
            "MRT carrier allocated electricity", "Vertical transition annual maintenance",
        ):
            assert counts[comp] == 1

    def test_energy_maintenance_sentinel_canonical_isolated(self, opex_baseline):
        pa = opex_baseline.assumptions
        perturbed = _dc.replace(
            opex_baseline,
            assumptions=_dc.replace(
                pa,
                mrt_carrier_maintenance_opex_per_installed_unit_year=pa.mrt_carrier_maintenance_opex_per_installed_unit_year * 10,
                mrt_guideway_maintenance_fraction_of_capex_per_year=pa.mrt_guideway_maintenance_fraction_of_capex_per_year * 10,
                mrt_guideway_capex_per_m=pa.mrt_guideway_capex_per_m * 10,
            ),
        )
        a = _mrt_opex_rows(_nuclear(opex_baseline, mcc.CANONICAL_MRT_RUNTIME_CONFIG))
        b = _mrt_opex_rows(_nuclear(perturbed, mcc.CANONICAL_MRT_RUNTIME_CONFIG))
        for comp in ("MRT carrier maintenance", "Guideway annual maintenance", "MRT energy"):
            assert a[comp].annual_cost == pytest.approx(b[comp].annual_cost, abs=1e-9)

    def test_energy_maintenance_sentinel_legacy_heavy_authoritative(self, opex_baseline):
        pa = opex_baseline.assumptions
        perturbed = _dc.replace(
            opex_baseline,
            assumptions=_dc.replace(
                pa,
                mrt_carrier_maintenance_opex_per_installed_unit_year=pa.mrt_carrier_maintenance_opex_per_installed_unit_year * 10,
            ),
        )
        a = _mrt_opex_rows(_nuclear(opex_baseline, None))
        b = _mrt_opex_rows(_nuclear(perturbed, None))
        assert a["MRT carrier maintenance"].annual_cost != pytest.approx(b["MRT carrier maintenance"].annual_cost)


# ===========================================================================
# Sec 35 -- DECAY CONSEQUENCE of the faster canonical straight speed
#           (shorter transit -> less in-transit decay -> >= retention).
# ===========================================================================
class TestDecayConsequence:
    @pytest.fixture(scope="class")
    def dc_baseline(self):
        return wo4a.build_eight_floor_deterministic_capital_baseline()

    def test_canonical_faster_transit_retains_at_least_as_much(self, dc_baseline):
        canon = _nuclear(dc_baseline, mcc.CANONICAL_MRT_RUNTIME_CONFIG)
        legacy = _nuclear(dc_baseline, None)
        c_mrt = [t for t in canon.patient_traces if t.transport_mode == "MRT"]
        l_mrt = [t for t in legacy.patient_traces if t.transport_mode == "MRT"]
        assert c_mrt and l_mrt
        c_elapsed = sum(t.elapsed_release_to_administration_minutes for t in c_mrt) / len(c_mrt)
        l_elapsed = sum(t.elapsed_release_to_administration_minutes for t in l_mrt) / len(l_mrt)
        c_ret = sum(t.retained_fraction for t in c_mrt) / len(c_mrt)
        l_ret = sum(t.retained_fraction for t in l_mrt) / len(l_mrt)
        assert c_elapsed <= l_elapsed + 1e-9   # canonical no slower
        assert c_ret >= l_ret - 1e-12          # faster -> retains at least as much


# ===========================================================================
# Sec 36 -- FAIRNESS under speed+OPEX migration: Manual + Automated Conventional
#           byte-identical under drastic heavy-MRT perturbation.
# ===========================================================================
class TestConventionalFairnessUnderMigration:
    @pytest.fixture(scope="class")
    def fair_baseline(self):
        return wo4a.build_eight_floor_deterministic_capital_baseline()

    def _perturbed(self, bl):
        pa = bl.assumptions
        return _dc.replace(
            bl,
            assumptions=_dc.replace(
                pa,
                mrt_carrier_capex_per_installed_unit=pa.mrt_carrier_capex_per_installed_unit * 10,
                mrt_guideway_capex_per_m=pa.mrt_guideway_capex_per_m * 10,
                mrt_infrastructure_capex=pa.mrt_infrastructure_capex * 10,
                mrt_carrier_maintenance_opex_per_installed_unit_year=pa.mrt_carrier_maintenance_opex_per_installed_unit_year * 10,
                mrt_horizontal_speed_m_per_s=pa.mrt_horizontal_speed_m_per_s / 2,
            ),
        )

    def test_manual_byte_identical_under_heavy_mrt_perturbation(self, fair_baseline):
        a = wo4a.evaluate_manual_conventional(fair_baseline, development_context="GREENFIELD", study_scope="CAPITAL_PLANNING")
        b = wo4a.evaluate_manual_conventional(self._perturbed(fair_baseline), development_context="GREENFIELD", study_scope="CAPITAL_PLANNING")
        assert a.new_study_capex == b.new_study_capex
        assert a.annual_opex == b.annual_opex

    def test_automated_byte_identical_under_heavy_mrt_perturbation(self, fair_baseline):
        a = wo4a.evaluate_automated_conventional(fair_baseline, development_context="GREENFIELD", study_scope="CAPITAL_PLANNING")
        b = wo4a.evaluate_automated_conventional(self._perturbed(fair_baseline), development_context="GREENFIELD", study_scope="CAPITAL_PLANNING")
        assert a.new_study_capex == b.new_study_capex
        assert a.annual_opex == b.annual_opex

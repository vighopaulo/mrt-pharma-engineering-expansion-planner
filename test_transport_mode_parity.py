"""KIRO Super-Build 1: deterministic tests for the common transport-mode
eligibility authority, transport-modes-in-scope + fallback conservation, the
parity contract, and the cross-mode sentinels (exclusion / fallback /
eligibility / radiation qualification / economic + physics parity)."""

from __future__ import annotations

import pytest

import transport_mode_eligibility_authority as elig
import transport_mode_scope_authority as scope
import transport_parity_view as view
import conventional_transport_authority as cta
import floor_agv_amr_authority as agv
import engineering_authority as ea

ALL = elig.ALL_TRANSPORT_MODE_FAMILIES


# ===========================================================================
# Governance
# ===========================================================================
class TestGovernance:
    def test_super_build_governance_registered(self):
        assert ea.super_build_governance_present()
        assert len(ea.SUPER_BUILD_GOVERNANCE_REGISTRY) >= 20

    def test_key_principles_present(self):
        principles = {r.principle for r in ea.SUPER_BUILD_GOVERNANCE_REGISTRY}
        for p in ("PAYLOAD_ELIGIBILITY_BEFORE_OPTIMIZATION", "FALLBACK_CONSERVATION", "NO_ZERO_FILLING_UNKNOWN_COSTS",
                  "ONE_AUTHORITY_PER_CONCEPT", "EXPERIMENT_FREEZE", "TECHNOLOGY_FAIRNESS"):
            assert p in principles


# ===========================================================================
# Radiopharmaceutical eligibility matrix (Sec 53)
# ===========================================================================
class TestRadiopharmMatrix:
    def _elig(self, mode):
        return elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode=mode, stream="RADIOPHARMACEUTICAL_NUCLEAR", payload_mass_kg=3.0)).eligibility

    def test_manual_eligible_with_shielding(self):
        assert self._elig("MANUAL") == "ELIGIBLE"

    def test_manual_qualification_without_shielding(self):
        r = elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode="MANUAL", stream="RADIOPHARMACEUTICAL_NUCLEAR", manual_shielding_configured=False))
        assert r.eligibility == "QUALIFICATION_REQUIRED"

    def test_pts_qualification_required(self):
        assert self._elig("PTS") == "QUALIFICATION_REQUIRED"

    def test_rp_pts_eligible(self):
        assert self._elig("DEDICATED_RP_PTS") == "ELIGIBLE"

    def test_agv_light_qualification_required(self):
        assert self._elig("AGV_AMR_LIGHT_CLINICAL") == "QUALIFICATION_REQUIRED"

    def test_agv_heavy_qualification_required(self):
        assert self._elig("AGV_AMR_HEAVY_LOGISTICS") == "QUALIFICATION_REQUIRED"

    def test_mrt_eligible_by_canonical_authority(self):
        assert self._elig("MRT") == "ELIGIBLE"


# ===========================================================================
# Linen / bulk-logistics eligibility matrix (Sec 54)
# ===========================================================================
class TestLinenMatrix:
    def _elig(self, mode):
        return elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode=mode, stream="CLEAN_LINEN", payload_mass_kg=60.0)).eligibility

    def test_manual_eligible(self):
        assert self._elig("MANUAL") == "ELIGIBLE"

    def test_pts_ineligible(self):
        assert self._elig("PTS") == "INELIGIBLE"

    def test_agv_light_ineligible(self):
        assert self._elig("AGV_AMR_LIGHT_CLINICAL") == "INELIGIBLE"

    def test_agv_heavy_eligible(self):
        assert self._elig("AGV_AMR_HEAVY_LOGISTICS") == "ELIGIBLE"

    def test_mrt_ineligible_bulk_linen(self):
        assert self._elig("MRT") == "INELIGIBLE"


# ===========================================================================
# Specimen eligibility matrix (Sec 55)
# ===========================================================================
class TestSpecimenMatrix:
    def test_manual_specimen_eligible(self):
        assert elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode="MANUAL", stream="SPECIMEN_BLOOD")).eligibility == "ELIGIBLE"

    def test_pts_general_specimen_eligible(self):
        r = elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode="PTS", stream="SPECIMEN_BLOOD", specimen_sensitivity="GENERAL_COMPATIBLE"))
        assert r.eligibility == "ELIGIBLE"

    def test_pts_sensitive_specimen_needs_validation(self):
        r = elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode="PTS", stream="SPECIMEN_BLOOD", specimen_sensitivity="PTS_SENSITIVE"))
        assert r.eligibility == "FACILITY_VALIDATION_REQUIRED"

    def test_pts_sensitive_specimen_validated_eligible(self):
        r = elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode="PTS", stream="SPECIMEN_BLOOD", specimen_sensitivity="PTS_SENSITIVE", pts_sensitive_specimen_validated=True))
        assert r.eligibility == "ELIGIBLE"

    def test_light_agv_specimen_eligible(self):
        assert elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode="AGV_AMR_LIGHT_CLINICAL", stream="SPECIMEN_BLOOD", payload_mass_kg=2.0)).eligibility == "ELIGIBLE"

    def test_heavy_agv_not_specimen_preferred_by_capacity(self):
        # Heavy AGV does not support specimen stream at all (not merely by capacity).
        assert elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode="AGV_AMR_HEAVY_LOGISTICS", stream="SPECIMEN_BLOOD", payload_mass_kg=2.0)).eligibility == "INELIGIBLE"


# ===========================================================================
# Pharmacy / sterile eligibility (Sec 56)
# ===========================================================================
class TestPharmacySterile:
    def test_pharmacy_multiple_modes(self):
        m = elig.allowed_modes_for_payload(stream="PHARMACY_INFUSION", payload_mass_kg=2.0)
        allowed = {k for k, v in m.items() if elig.is_allowed(v)}
        assert "MANUAL" in allowed and "PTS" in allowed and "AGV_AMR_LIGHT_CLINICAL" in allowed

    def test_bulk_sterile_rejected_by_light(self):
        r = elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode="AGV_AMR_LIGHT_CLINICAL", stream="STERILE_CLEAN_SUPPLY", payload_mass_kg=100.0))
        assert not elig.is_allowed(r)


# ===========================================================================
# Transport-modes-in-scope + exclusion sentinel (Sec 58/72/89)
# ===========================================================================
class TestScopeExclusion:
    def test_scope_manual_pts_excludes_others(self):
        sc = scope.modes_in_scope("MANUAL", "PTS")
        allowed = scope.allowed_mode_set(scope=sc, stream="SPECIMEN_BLOOD", payload_mass_kg=2.0)
        assert allowed == frozenset({"MANUAL", "PTS"})

    def test_exclusion_dominates_economics(self):
        # Eligibility gate takes NO economics -> an excluded mode is never allowed,
        # regardless of any hypothetical cost. Verified structurally: out-of-scope
        # decisions are labeled EXCLUDED_BY_SCOPE.
        sc = scope.modes_in_scope("MANUAL", "PTS")
        dec = {d.mode: d for d in scope.resolve_scoped_allowed_modes(scope=sc, stream="SPECIMEN_BLOOD", payload_mass_kg=2.0)}
        assert not dec["MRT"].allowed and dec["MRT"].reason.startswith("EXCLUDED_BY_SCOPE")
        assert not dec["AGV_AMR_LIGHT_CLINICAL"].allowed

    def test_scope_mrt_only(self):
        sc = scope.modes_in_scope("MRT")
        allowed = scope.allowed_mode_set(scope=sc, stream="SPECIMEN_BLOOD", payload_mass_kg=2.0)
        assert allowed == frozenset({"MRT"})

    def test_all_except_robots(self):
        sc = scope.all_except("AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS")
        assert sc.excludes("AGV_AMR_LIGHT_CLINICAL") and sc.excludes("AGV_AMR_HEAVY_LOGISTICS")
        assert sc.includes("MRT") and sc.includes("MANUAL")

    def test_all_except_mrt(self):
        sc = scope.all_except("MRT")
        assert sc.excludes("MRT") and sc.includes("MANUAL")

    def test_empty_scope_rejected(self):
        with pytest.raises(ValueError):
            scope.TransportModesInScope(frozenset())

    def test_unknown_mode_rejected(self):
        with pytest.raises(ValueError):
            scope.TransportModesInScope(frozenset({"TELEPORTER"}))  # type: ignore[arg-type]


# ===========================================================================
# Fallback conservation sentinel (Sec 59/90)
# ===========================================================================
class TestFallbackConservation:
    def test_conservation_holds_all_modes(self):
        sc = scope.all_modes_in_scope()
        res = scope.assign_missions_within_scope(scope=sc, missions=[
            scope.MissionAssignmentRequest("L", "CLEAN_LINEN", payload_mass_kg=60.0),
            scope.MissionAssignmentRequest("S", "SPECIMEN_BLOOD", payload_mass_kg=2.0),
            scope.MissionAssignmentRequest("P", "PHARMACY_INFUSION", payload_mass_kg=2.0),
        ])
        assert res.conserved and res.input_missions == res.assigned_missions + res.unmet_missions
        assert res.unmet_missions == 0

    def test_scope_mrt_bulk_linen_unmet_no_manual_insertion(self):
        sc = scope.modes_in_scope("MRT")
        res = scope.assign_missions_within_scope(scope=sc, missions=[
            scope.MissionAssignmentRequest("L", "CLEAN_LINEN", payload_mass_kg=60.0),
        ])
        linen = res.assignments[0]
        assert linen.status == "UNMET" and linen.assigned_mode is None
        assert res.conserved

    def test_no_mission_lost(self):
        sc = scope.modes_in_scope("PTS")
        res = scope.assign_missions_within_scope(scope=sc, missions=[
            scope.MissionAssignmentRequest("A", "SPECIMEN_BLOOD", payload_mass_kg=2.0),
            scope.MissionAssignmentRequest("B", "CLEAN_LINEN", payload_mass_kg=60.0),  # PTS ineligible -> UNMET
        ])
        assert res.input_missions == 2 == res.assigned_missions + res.unmet_missions
        assert res.assigned_missions == 1 and res.unmet_missions == 1


# ===========================================================================
# Eligibility sentinel (Sec 91): physical envelope beats economics
# ===========================================================================
class TestEligibilitySentinel:
    def test_overmass_stays_ineligible_regardless_of_scope(self):
        # A payload exceeding the light class envelope is INELIGIBLE even if the
        # light class is the only in-scope mode (economics cannot rescue it).
        sc = scope.modes_in_scope("AGV_AMR_LIGHT_CLINICAL")
        allowed = scope.allowed_mode_set(scope=sc, stream="STERILE_CLEAN_SUPPLY", payload_mass_kg=100.0)
        assert allowed == frozenset()

    def test_radiation_qualification_sentinel(self):
        # radiopharm attractive-but-unqualified stays QUALIFICATION_REQUIRED for PTS/AGV
        for mode in ("PTS", "AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS"):
            r = elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode=mode, stream="RADIOPHARMACEUTICAL_NUCLEAR", payload_mass_kg=3.0))
            assert r.eligibility == "QUALIFICATION_REQUIRED"
            assert not elig.is_allowed(r)


# ===========================================================================
# Parity contract + views (Sec 61-62/93) -- schema parity, NOT ranking
# ===========================================================================
class TestParityContract:
    def test_economic_parity_categories_present(self):
        for c in ("KNOWN_CAPEX", "UNKNOWN_CAPEX", "KNOWN_ANNUAL_OPEX_SUBTOTAL", "TOTAL_OPEX_STATUS"):
            assert c in scope.ECONOMIC_PARITY_CATEGORIES

    def test_physics_parity_categories_present(self):
        for c in ("PAYLOAD_LIMIT", "SPEED", "ROUTE_TIME", "CAPACITY", "FLEET_REQUIREMENT", "MISSION_ELIGIBILITY"):
            assert c in scope.PHYSICS_PARITY_CATEGORIES

    def test_manual_parity_view(self):
        v = view.manual_parity_view(policy=cta.PorterOperatingPolicy(), stream="SPECIMEN_BLOOD", mission_minutes=15.0, required_fte=2.0, annual_labor_opex=200_000.0)
        assert v.transport_mode == "MANUAL" and v.known_annual_opex_usd >= 200_000.0

    def test_pts_parity_view(self):
        v = view.pts_parity_view(profile=view.PTS_PROFILE_STANDARD_110MM, stream="SPECIMEN_BLOOD", station_count=6, loaded_annual_cost_per_fte=70_000.0)
        assert v.transport_mode == "PTS" and v.known_capex_usd is not None and v.known_capex_usd > 0

    def test_floor_agv_parity_view(self):
        p = agv.DEFAULT_LIGHT_CLINICAL_PROFILE
        cap = agv.compute_floor_agv_capex(profile=p, fleet_size=2, charging_station_count=1)
        op = agv.compute_floor_agv_opex(profile=p, fleet_size=2, charging_station_count=1, annual_electricity_usd=500.0, loaded_annual_cost_per_fte=70_000.0)
        v = view.floor_agv_parity_view(profile=p, stream="SPECIMEN_BLOOD", fleet=2, charging_stations=1, mission_minutes=14.0, capex=cap, opex=op)
        assert v.transport_mode == "AGV_AMR_LIGHT_CLINICAL" and v.known_annual_opex_usd == op.known_annual_opex_subtotal

    def test_mrt_parity_view_reference_only(self):
        v = view.mrt_parity_view_reference(stream="SPECIMEN_BLOOD", route_time_minutes=2.0)
        assert v.transport_mode == "MRT" and v.total_opex_status.startswith("OWNED_BY_CANONICAL")
        # reference-only: no recomputed CapEx/OPEX
        assert v.known_capex_usd is None and v.known_annual_opex_usd is None

    def test_pts_profiles_preserve_active_benchmark(self):
        assert view.PTS_PROFILE_STANDARD_110MM.network is cta.DEFAULT_PTS_NETWORK


# ===========================================================================
# Physics parity control (Sec 74): report times where eligible, no "fastest=best"
# ===========================================================================
class TestPhysicsParityControl:
    def test_route_times_reported_per_mode(self):
        # For a compatible specimen at a controlled distance, each eligible mode
        # exposes a route time; the test asserts they EXIST and are positive,
        # never that the fastest is preferred.
        manual = view.manual_parity_view(policy=cta.PorterOperatingPolicy(), stream="SPECIMEN_BLOOD", mission_minutes=15.0, required_fte=1.0, annual_labor_opex=100_000.0)
        pts = view.pts_parity_view(profile=view.PTS_PROFILE_STANDARD_110MM, stream="SPECIMEN_BLOOD", station_count=6, loaded_annual_cost_per_fte=70_000.0)
        light = agv.compute_floor_agv_mission_timing(profile=agv.DEFAULT_LIGHT_CLINICAL_PROFILE, horizontal_distance_m=100.0)
        assert manual.route_time_minutes > 0 and pts.route_time_minutes > 0 and light.total_minutes > 0

    def test_no_ranking_in_parity_build(self):
        # The scope authority explicitly does NOT integrate an optimizer/ranker.
        assert scope.GENERALIZED_OPTIMIZER_INTEGRATED_NOW is False


# ===========================================================================
# No-silent-zero governor (Sec 63)
# ===========================================================================
class TestNoSilentZero:
    def test_unknown_agv_opex_not_in_known_subtotal(self):
        o = agv.compute_floor_agv_opex(profile=agv.DEFAULT_HEAVY_LOGISTICS_PROFILE, fleet_size=2, charging_station_count=1, annual_electricity_usd=500.0, loaded_annual_cost_per_fte=70_000.0)
        assert len(o.unknown_opex_components) >= 1
        assert o.total_opex_status == "KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED"

    def test_ineligible_never_eligible(self):
        r = elig.evaluate_transport_eligibility(elig.TransportEligibilityQuery(mode="PTS", stream="CLEAN_LINEN", payload_mass_kg=60.0))
        assert not elig.is_allowed(r)


# ===========================================================================
# Future optimizer contract documented but NOT implemented (Sec 94)
# ===========================================================================
class TestFutureContract:
    def test_contract_documented(self):
        assert "GENERALIZED_TRANSPORT_CANDIDATE_GENERATION" in scope.FUTURE_OPTIMIZER_CONTRACT
        assert scope.GENERALIZED_OPTIMIZER_INTEGRATED_NOW is False

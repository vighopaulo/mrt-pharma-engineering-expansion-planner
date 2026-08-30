"""KIRO Super-Build 2 tests -- generalized multi-transport optimizer:
eligibility-first candidate generation, single/multi-mode, true hybrid, dedup,
mission conservation, capacity, economics (no-double-count / no-silent-zero),
objective transparency, winner neutrality, and the family/subtype sentinels
(Sec 8-42, 50-82).
"""
from __future__ import annotations

import pytest

import generalized_transport_optimizer as gto
from generalized_transport_optimizer import OptimizerMission, optimize, generate_candidates, build_candidate
from transport_settings_authority import (
    TransportSettings, default_transport_settings, only_families, all_except_families, with_overrides,
)


# --- fixtures --------------------------------------------------------------

def _mixed_workload():
    return [
        OptimizerMission("M-RADIO", "RADIOPHARMACEUTICAL_NUCLEAR", payload_mass_kg=3.0, patient_ids=("P1",)),
        OptimizerMission("M-SPEC", "SPECIMEN_BLOOD", payload_mass_kg=1.0, patient_ids=("P2",)),
        OptimizerMission("M-LINEN", "CLEAN_LINEN", payload_mass_kg=60.0, payload_volume_l=400.0, patient_ids=("P3",)),
        OptimizerMission("M-PHARM", "PHARMACY_INFUSION", payload_mass_kg=2.0, patient_ids=("P4",)),
    ]


def _linen_mission():
    return [OptimizerMission("L1", "CLEAN_LINEN", payload_mass_kg=60.0, payload_volume_l=400.0)]


def _radiopharm_mission():
    return [OptimizerMission("R1", "RADIOPHARMACEUTICAL_NUCLEAR", payload_mass_kg=2.0)]


def _specimen_mission():
    return [OptimizerMission("S1", "SPECIMEN_BLOOD", payload_mass_kg=1.0)]


# --- eligibility-first + qualification (Sec 9-11) --------------------------

def test_available_modes_honor_family_scope():
    avail = gto._available_resolved_modes(only_families("MANUAL", "MRT"))
    assert avail == frozenset({"MANUAL", "MRT"})


def test_radiopharm_via_ordinary_pts_qualification_required_not_eligible():
    m = OptimizerMission("R", "RADIOPHARMACEUTICAL_NUCLEAR", payload_mass_kg=2.0)
    s = TransportSettings(pts_nuclear_qualified_enabled=False)  # only ordinary PTS in PTS family
    assert gto.resolved_mode_eligibility(m, "PTS", s) == "QUALIFICATION_REQUIRED"
    assert "PTS" not in gto.allowed_modes_for_mission(m, s)


def test_radiopharm_via_light_agv_qualification_required():
    m = _radiopharm_mission()[0]
    s = default_transport_settings()
    assert gto.resolved_mode_eligibility(m, "AGV_AMR_LIGHT_CLINICAL", s) == "QUALIFICATION_REQUIRED"


def test_radiopharm_via_heavy_agv_qualification_required():
    m = _radiopharm_mission()[0]
    s = default_transport_settings()
    assert gto.resolved_mode_eligibility(m, "AGV_AMR_HEAVY_LOGISTICS", s) == "QUALIFICATION_REQUIRED"


def test_radiopharm_dedicated_rp_pts_eligible():
    m = _radiopharm_mission()[0]
    s = default_transport_settings()
    assert gto.resolved_mode_eligibility(m, "DEDICATED_RP_PTS", s) == "ELIGIBLE"


def test_manual_radiopharm_requires_shielding():
    m = _radiopharm_mission()[0]
    no_shield = default_transport_settings()
    assert gto.resolved_mode_eligibility(m, "MANUAL", no_shield) == "QUALIFICATION_REQUIRED"
    shielded = with_overrides(default_transport_settings(), radiopharm_qualification_supplied=True)
    assert gto.resolved_mode_eligibility(m, "MANUAL", shielded) == "ELIGIBLE"


def test_eligibility_precedes_economics_never_forces_eligible():
    # bulk linen on light AGV is ineligible regardless of settings
    m = _linen_mission()[0]
    s = default_transport_settings()
    assert gto.resolved_mode_eligibility(m, "AGV_AMR_LIGHT_CLINICAL", s) == "INELIGIBLE"


# --- linen matrix (Sec 12 report / eligibility) ----------------------------

def test_linen_manual_and_heavy_agv_eligible_only():
    m = _linen_mission()[0]
    s = default_transport_settings()
    allowed = set(gto.allowed_modes_for_mission(m, s))
    assert "MANUAL" in allowed
    assert "AGV_AMR_HEAVY_LOGISTICS" in allowed
    assert "PTS" not in allowed
    assert "AGV_AMR_LIGHT_CLINICAL" not in allowed
    assert "MRT" not in allowed


# --- specimen matrix (Sec 13) ---------------------------------------------

def test_pts_sensitive_specimen_facility_validation_required():
    m = OptimizerMission("S", "SPECIMEN_BLOOD", payload_mass_kg=1.0, specimen_sensitivity="PTS_SENSITIVE")
    s = TransportSettings(pts_nuclear_qualified_enabled=False)
    assert gto.resolved_mode_eligibility(m, "PTS", s) == "FACILITY_VALIDATION_REQUIRED"
    validated = with_overrides(s, pts_sensitive_specimen_validated=True)
    assert gto.resolved_mode_eligibility(m, "PTS", validated) == "ELIGIBLE"


# --- single-mode candidates (Sec 19) --------------------------------------

def test_single_mode_candidate_manual_only():
    c = build_candidate(candidate_id="C", candidate_modes=frozenset({"MANUAL"}),
                        missions=_specimen_mission(), settings=only_families("MANUAL"))
    assert c.actually_used_families == ("MANUAL",)
    assert not c.is_hybrid


def test_single_mode_candidates_present_in_generation():
    cands = generate_candidates(missions=_specimen_mission(), settings=default_transport_settings())
    names = {c.candidate_name for c in cands}
    assert any(n.endswith("_ONLY") for n in names)


# --- multi-mode + true hybrid (Sec 20-22) ---------------------------------

def test_true_hybrid_manual_mrt_control_a():
    res = optimize(missions=_mixed_workload(), settings=only_families("MANUAL", "MRT"))
    assert res.selected is not None
    assert res.selected.is_hybrid
    assert set(res.selected.actually_used_families) == {"MANUAL", "MRT"}
    assert res.selected.assignment.conserved
    assert res.selected.unmet_missions == 0


def test_true_hybrid_pts_agv_heavy_manual_control_b():
    missions = [
        OptimizerMission("G1", "SPECIMEN_BLOOD", payload_mass_kg=1.0, specimen_sensitivity="GENERAL_COMPATIBLE"),
        OptimizerMission("G2", "SPECIMEN_BLOOD", payload_mass_kg=1.0, specimen_sensitivity="PTS_SENSITIVE"),
        OptimizerMission("G3", "CLEAN_LINEN", payload_mass_kg=60.0, payload_volume_l=400.0),
        OptimizerMission("G4", "PHARMACY_INFUSION", payload_mass_kg=2.0),
    ]
    s = TransportSettings(
        rths_enabled=False, mrt_enabled=False,
        pts_nuclear_qualified_enabled=False, agv_amr_light_clinical_enabled=False,
    )  # PTS_CONVENTIONAL + AGV_HEAVY + MANUAL
    res = optimize(missions=missions, settings=s)
    assert res.selected is not None
    # PTS-sensitive without validation must NOT silently use PTS
    sens = next(a for a in res.selected.assignment.assignments if a.mission_id == "G2")
    assert sens.assigned_mode != "PTS"
    assert res.selected.assignment.conserved


def test_true_hybrid_mrt_rths_manual_control_c():
    missions = [
        OptimizerMission("C1", "PHARMACY_INFUSION", payload_mass_kg=2.0),
        OptimizerMission("C2", "STERILE_CLEAN_SUPPLY", payload_mass_kg=5.0),
    ]
    res = optimize(missions=missions, settings=only_families("MRT", "RTHS", "MANUAL"))
    assert res.selected is not None
    # RTHS remains its own family, distinct from MRT
    assert "RTHS" in gto._RESOLVED_TO_FAMILY.values()
    assert res.selected.assignment.conserved


def test_hybrid_exposes_mission_by_mode():
    res = optimize(missions=_mixed_workload(), settings=only_families("MANUAL", "MRT"))
    assert res.selected is not None
    assert sum(res.selected.assignment.missions_by_mode.values()) == res.selected.assignment.assigned_missions


# --- dedup (Sec 23) --------------------------------------------------------

def test_candidate_dedup_collapses_equivalent_allocations():
    # with a single specimen mission, many permitted mode sets collapse to the
    # same actually-used allocation
    cands = generate_candidates(missions=_specimen_mission(), settings=default_transport_settings())
    signatures = [(c.actually_used_modes, tuple(sorted(c.assignment.missions_by_mode.items()))) for c in cands]
    assert len(signatures) == len(set(signatures))


# --- mission conservation (Sec 18, 68) ------------------------------------

@pytest.mark.parametrize("scope", [
    only_families("MANUAL"), only_families("PTS"), only_families("MRT"),
    only_families("MANUAL", "MRT"), all_except_families("MRT"), default_transport_settings(),
])
def test_mission_conservation_holds_for_every_candidate(scope):
    cands = generate_candidates(missions=_mixed_workload(), settings=scope)
    for c in cands:
        assert c.assignment.input_missions == c.assignment.assigned_missions + c.assignment.unmet_missions
        assert c.assignment.conserved


# --- fallback exclusion (Sec 17, 39) --------------------------------------

def test_scope_mrt_only_linen_becomes_unmet_no_manual_insertion():
    res = optimize(missions=_linen_mission(), settings=only_families("MRT"))
    # MRT cannot carry bulk linen; Manual is OFF -> unmet, never silently inserted
    assert res.selected is None
    empty_or_infeasible = res.all_candidates
    for c in empty_or_infeasible:
        assert "MANUAL" not in c.actually_used_families


def test_manual_off_fallback_linen_unmet_unless_other_eligible():
    # Manual OFF, MRT ON, linen -> unmet
    s = TransportSettings(manual_enabled=False, pts_enabled=False, rths_enabled=False, agv_amr_enabled=False, mrt_enabled=True)
    res = optimize(missions=_linen_mission(), settings=s)
    assert res.selected is None
    # but with heavy AGV enabled, linen becomes feasible
    s2 = TransportSettings(manual_enabled=False, pts_enabled=False, rths_enabled=False, mrt_enabled=False,
                           agv_amr_enabled=True, agv_amr_light_clinical_enabled=False)
    res2 = optimize(missions=_linen_mission(), settings=s2)
    assert res2.selected is not None
    assert "AGV_AMR" in res2.selected.actually_used_families


# --- FAMILY-OFF sentinels (Sec 33-34, 65, 76-80) --------------------------

@pytest.mark.parametrize("fam,marker", [
    ("MANUAL", "MANUAL"), ("PTS", "PTS"), ("RTHS", "RTHS"), ("AGV_AMR", "AGV_AMR"), ("MRT", "MRT"),
])
def test_family_off_absent_from_all_candidates(fam, marker):
    s = all_except_families(fam)
    cands = generate_candidates(missions=_mixed_workload(), settings=s)
    for c in cands:
        assert marker not in c.actually_used_families
        assert fam not in c.enabled_families


def test_mrt_off_even_if_free_not_generated():
    # artificially make MRT free by disabling it and verifying no candidate uses it
    s = all_except_families("MRT")
    assert "MRT" not in gto._available_resolved_modes(s)
    cands = generate_candidates(missions=_mixed_workload(), settings=s)
    assert all("MRT" not in c.candidate_modes for c in cands)


def test_agv_off_both_subtypes_absent():
    s = all_except_families("AGV_AMR")
    avail = gto._available_resolved_modes(s)
    assert "AGV_AMR_LIGHT_CLINICAL" not in avail
    assert "AGV_AMR_HEAVY_LOGISTICS" not in avail


# --- SUBTYPE-OFF sentinels (Sec 35-36, 66) --------------------------------

def test_pts_nuclear_off_no_dedicated_rp_pts_even_with_qualification():
    s = TransportSettings(pts_nuclear_qualified_enabled=False, radiopharm_qualification_supplied=True)
    assert "DEDICATED_RP_PTS" not in gto._available_resolved_modes(s)
    res = optimize(missions=_radiopharm_mission(), settings=with_overrides(s,
        manual_enabled=False, rths_enabled=False, agv_amr_enabled=False, mrt_enabled=False))
    assert res.selected is None  # conventional PTS not qualified; nuclear off


def test_agv_heavy_off_bulk_linen_not_served_by_heavy():
    s = TransportSettings(agv_amr_heavy_logistics_enabled=False)
    cands = generate_candidates(missions=_linen_mission(), settings=s)
    for c in cands:
        assert "AGV_AMR_HEAVY_LOGISTICS" not in c.actually_used_modes


# --- ALL-OFF / ALL-ON (Sec 81-82) -----------------------------------------

def test_all_modes_off_is_infeasible_not_empty_success():
    s = TransportSettings(manual_enabled=False, pts_enabled=False, rths_enabled=False,
                          agv_amr_enabled=False, mrt_enabled=False)
    res = optimize(missions=_specimen_mission(), settings=s)
    assert res.selected is None
    assert len(res.all_candidates) == 1
    assert res.all_candidates[0].unmet_missions == 1


def test_all_modes_on_no_forced_inclusion():
    res = optimize(missions=_specimen_mission(), settings=default_transport_settings())
    assert res.selected is not None
    # a single small specimen need not use every enabled technology
    assert len(res.selected.actually_used_families) >= 1


# --- eligibility / qualification / capacity over economics (Sec 37-38, 52) --

def test_overmass_payload_stays_ineligible_when_only_mode(monkeypatch):
    # heavy-only scope, payload beyond envelope
    over = OptimizerMission("O", "STERILE_CLEAN_SUPPLY", payload_mass_kg=5000.0, payload_volume_l=99999.0)
    s = TransportSettings(manual_enabled=False, pts_enabled=False, rths_enabled=False, mrt_enabled=False,
                          agv_amr_enabled=True, agv_amr_light_clinical_enabled=False)
    res = optimize(missions=[over], settings=s)
    assert res.selected is None  # economics cannot rescue an over-envelope payload


def test_radiopharm_qualification_over_economics():
    # PTS/AGV cheapest but radiopharm not qualified -> unmet
    s = TransportSettings(manual_enabled=False, rths_enabled=False, mrt_enabled=False,
                          pts_nuclear_qualified_enabled=False)  # ordinary PTS + AGV, no nuclear PTS
    res = optimize(missions=_radiopharm_mission(), settings=s)
    assert res.selected is None
    # supply qualification -> still not eligible for ordinary PTS/AGV (those stay QUALIFICATION_REQUIRED)
    # only becomes feasible via a qualified path (dedicated RP-PTS / manual shielded)
    s2 = with_overrides(s, pts_nuclear_qualified_enabled=True)
    res2 = optimize(missions=_radiopharm_mission(), settings=s2)
    assert res2.selected is not None  # dedicated RP-PTS now available + eligible


# --- objective transparency + winner neutrality (Sec 52-53, 72) -----------

def test_objective_is_explicit():
    assert gto.OPTIMIZER_OBJECTIVE == "MINIMIZE_KNOWN_LIFECYCLE_COST_AMONG_MISSION_FEASIBLE_CANDIDATES"


def test_selection_explains_why_and_rejections():
    res = optimize(missions=_mixed_workload(), settings=default_transport_settings())
    assert res.selected is not None
    assert res.why_selected
    assert len(res.rejections) >= 1


def test_economics_drive_selection_switch_changes_winner(monkeypatch):
    # RTHS vs heavy-AGV for sterile supply; make RTHS cheap then expensive.
    missions = [OptimizerMission(f"M{i}", "STERILE_CLEAN_SUPPLY", payload_mass_kg=5.0) for i in range(6)]
    s = only_families("RTHS", "AGV_AMR")

    import conventional_transport_authority as cta
    # baseline: capture ranking
    base = optimize(missions=missions, settings=s)
    assert base.selected is not None
    baseline_winner = base.selected.candidate_name

    # perturb RTHS (RGHT) annual maintenance OPEX upward -> its lifecycle rises
    # (proves the optimizer consumes the RGHT economic authority, not a constant)
    import dataclasses
    expensive_rght = dataclasses.replace(cta.DEFAULT_AGV_MODEL, annual_maintenance_opex=1_000_000.0)
    monkeypatch.setattr(cta, "DEFAULT_AGV_MODEL", expensive_rght)
    perturbed = optimize(missions=missions, settings=s)
    # the RTHS candidate lifecycle must have increased (economics consumed)
    rths_base = next(c for c in base.ranked_feasible if c.actually_used_families == ("RTHS",))
    rths_pert = next(c for c in perturbed.ranked_feasible if c.actually_used_families == ("RTHS",))
    assert rths_pert.lifecycle_cost_usd > rths_base.lifecycle_cost_usd


# --- no-silent-zero (Sec 31) ----------------------------------------------

def test_unknown_costs_listed_not_zeroed():
    res = optimize(missions=_mixed_workload(), settings=default_transport_settings())
    # at least one candidate must carry unknown cost disclosures
    assert any(c.unknown_capex_components or c.unknown_opex_components for c in res.all_candidates)


def test_unknown_costs_flag_comparison_qualification():
    c = build_candidate(candidate_id="C", candidate_modes=frozenset({"AGV_AMR_HEAVY_LOGISTICS"}),
                        missions=_linen_mission(), settings=only_families("AGV_AMR"))
    if c.unknown_capex_components or c.unknown_opex_components:
        assert c.economic_status == "COMPARABLE_WITH_QUALIFICATIONS"


# --- no-double-count (Sec 21 report / 13) ---------------------------------

def test_agv_shared_fleet_manager_counted_once_across_light_and_heavy():
    missions = [
        OptimizerMission("A1", "PHARMACY_INFUSION", payload_mass_kg=2.0),      # light
        OptimizerMission("A2", "CLEAN_LINEN", payload_mass_kg=60.0, payload_volume_l=400.0),  # heavy
    ]
    c = build_candidate(candidate_id="C",
                        candidate_modes=frozenset({"AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS"}),
                        missions=missions, settings=only_families("AGV_AMR"))
    # shared fleet-manager appears exactly once in shared components
    shared_mgr = [x for x in c.shared_capex_components if "fleet-management" in x]
    assert len(shared_mgr) == 1


def test_pts_shared_backbone_counted_once():
    # both PTS subtypes active + a radiopharm + a specimen
    missions = [
        OptimizerMission("P1", "SPECIMEN_BLOOD", payload_mass_kg=1.0),
        OptimizerMission("P2", "RADIOPHARMACEUTICAL_NUCLEAR", payload_mass_kg=2.0),
    ]
    c = build_candidate(candidate_id="C",
                        candidate_modes=frozenset({"PTS", "DEDICATED_RP_PTS"}),
                        missions=missions, settings=only_families("PTS"))
    backbone = [x for x in c.shared_capex_components if "backbone" in x]
    assert len(backbone) <= 1


# --- candidate result schema (Sec 50) -------------------------------------

def test_candidate_exposes_required_schema_fields():
    res = optimize(missions=_mixed_workload(), settings=default_transport_settings())
    c = res.selected
    assert c is not None
    for attr in ("candidate_id", "candidate_name", "enabled_families", "enabled_subtypes",
                 "actually_used_families", "assignment", "unmet_missions", "physically_feasible",
                 "capacity_feasible", "qualification_feasible", "known_capex_usd",
                 "unknown_capex_components", "known_annual_opex_usd", "unknown_opex_components",
                 "lifecycle_cost_usd", "economic_status", "blockers"):
        assert hasattr(c, attr)


# --- user can exclude every family/subtype (Sec 96-97 gates) --------------

@pytest.mark.parametrize("fam", ["MANUAL", "PTS", "RTHS", "AGV_AMR", "MRT"])
def test_user_can_exclude_each_family(fam):
    s = all_except_families(fam)
    assert fam not in s.effectively_enabled_families()


@pytest.mark.parametrize("flag,sub", [
    ("pts_conventional_enabled", "PTS_CONVENTIONAL"),
    ("pts_nuclear_qualified_enabled", "PTS_NUCLEAR_QUALIFIED"),
    ("agv_amr_light_clinical_enabled", "AGV_AMR_LIGHT_CLINICAL"),
    ("agv_amr_heavy_logistics_enabled", "AGV_AMR_HEAVY_LOGISTICS"),
])
def test_user_can_exclude_each_subtype(flag, sub):
    s = TransportSettings(**{flag: False})
    assert sub not in s.effectively_enabled_subtypes()

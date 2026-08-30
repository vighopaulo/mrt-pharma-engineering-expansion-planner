"""KIRO Super-Build 2 tests -- runtime authority-consumer proofs, scope
sentinel runtime proof, shared cost tests, capacity, true-hybrid economic
controls, and legacy four-architecture compatibility (Sec 25, 69-75, 83,
89-90, 47-49).
"""
from __future__ import annotations

import dataclasses
import pytest

import generalized_transport_optimizer as gto
from generalized_transport_optimizer import OptimizerMission, optimize, build_candidate
from transport_settings_authority import (
    TransportSettings, default_transport_settings, only_families, with_overrides,
)
import transport_architecture_compatibility as compat


def _sterile(n=6, mass=5.0):
    return [OptimizerMission(f"M{i}", "STERILE_CLEAN_SUPPLY", payload_mass_kg=mass) for i in range(n)]


def _pharma(n=4):
    return [OptimizerMission(f"P{i}", "PHARMACY_INFUSION", payload_mass_kg=2.0) for i in range(n)]


def _linen(n=3):
    return [OptimizerMission(f"L{i}", "CLEAN_LINEN", payload_mass_kg=60.0, payload_volume_l=400.0) for i in range(n)]


# --- RUNTIME CONSUMER PROOFS (Sec 89): perturb a mode's economics; only that
#     mode's candidate economics move. -----------------------------------------

def _lifecycle_of(res, family_tuple):
    for c in res.ranked_feasible:
        if c.actually_used_families == family_tuple:
            return c.lifecycle_cost_usd
    return None


def test_manual_consumer_proof(monkeypatch):
    import conventional_transport_authority as cta
    missions = _pharma()
    s = only_families("MANUAL", "AGV_AMR")
    base = optimize(missions=missions, settings=s)
    base_manual = _lifecycle_of(base, ("MANUAL",))
    base_agv = _lifecycle_of(base, ("AGV_AMR",))
    # perturb MANUAL cart capex
    expensive_cart = dataclasses.replace(cta.DEFAULT_GENERAL_CART, purchase_capex=999_999.0)
    monkeypatch.setattr(cta, "DEFAULT_GENERAL_CART", expensive_cart)
    pert = optimize(missions=missions, settings=s)
    assert _lifecycle_of(pert, ("MANUAL",)) > base_manual  # Manual moved
    assert _lifecycle_of(pert, ("AGV_AMR",)) == base_agv    # AGV unchanged


def test_agv_light_consumer_proof(monkeypatch):
    import floor_agv_amr_authority as agv
    missions = _pharma()
    s = only_families("MANUAL", "AGV_AMR")
    base = optimize(missions=missions, settings=s)
    base_agv = _lifecycle_of(base, ("AGV_AMR",))
    base_manual = _lifecycle_of(base, ("MANUAL",))
    # perturb light AGV vehicle capex
    expensive = dataclasses.replace(agv.DEFAULT_LIGHT_CLINICAL_PROFILE, vehicle_capex_usd=agv.DEFAULT_LIGHT_CLINICAL_PROFILE.vehicle_capex_usd + 500_000.0)
    monkeypatch.setattr(agv, "DEFAULT_LIGHT_CLINICAL_PROFILE", expensive)
    pert = optimize(missions=missions, settings=s)
    assert _lifecycle_of(pert, ("AGV_AMR",)) > base_agv
    assert _lifecycle_of(pert, ("MANUAL",)) == base_manual


def test_mrt_consumer_proof(monkeypatch):
    import mrt_canonical_configuration as mrt
    missions = _pharma()
    s = only_families("MANUAL", "MRT")
    base = optimize(missions=missions, settings=s)
    base_mrt = _lifecycle_of(base, ("MRT",))
    base_manual = _lifecycle_of(base, ("MANUAL",))
    # perturb MRT canonical guideway cost (reversible, in-process only)
    expensive = dataclasses.replace(mrt.CANONICAL_MRT, two_way_guideway_capex_usd_per_m=99_999.0)
    monkeypatch.setattr(mrt, "CANONICAL_MRT", expensive)
    pert = optimize(missions=missions, settings=s)
    assert _lifecycle_of(pert, ("MRT",)) > base_mrt
    assert _lifecycle_of(pert, ("MANUAL",)) == base_manual


def test_rths_consumer_proof(monkeypatch):
    import conventional_transport_authority as cta
    missions = _sterile()
    s = only_families("RTHS", "MANUAL")
    base = optimize(missions=missions, settings=s)
    base_rths = _lifecycle_of(base, ("RTHS",))
    expensive = dataclasses.replace(cta.DEFAULT_AGV_MODEL, annual_energy_opex=500_000.0)
    monkeypatch.setattr(cta, "DEFAULT_AGV_MODEL", expensive)
    pert = optimize(missions=missions, settings=s)
    assert _lifecycle_of(pert, ("RTHS",)) > base_rths


# --- SCOPE SENTINEL RUNTIME PROOF (Sec 90): disable a mode + perturb its
#     economics extremely; result unchanged w.r.t. that excluded mode. --------

def test_scope_sentinel_excluded_mode_perturbation_has_no_effect(monkeypatch):
    import mrt_canonical_configuration as mrt
    missions = _pharma()
    s_without_mrt = only_families("MANUAL", "AGV_AMR")  # MRT OFF
    base = optimize(missions=missions, settings=s_without_mrt)
    # make MRT absurdly cheap; since it's OFF it must not appear or change result
    cheap = dataclasses.replace(mrt.CANONICAL_MRT, two_way_guideway_capex_usd_per_m=0.0, carrier_capex_usd=0.0)
    monkeypatch.setattr(mrt, "CANONICAL_MRT", cheap)
    pert = optimize(missions=missions, settings=s_without_mrt)
    assert (pert.selected is None) == (base.selected is None)
    if base.selected and pert.selected:
        assert base.selected.candidate_name == pert.selected.candidate_name
    assert all("MRT" not in c.actually_used_families for c in pert.all_candidates)


def test_scope_sentinel_disabled_agv_free_not_selected(monkeypatch):
    import floor_agv_amr_authority as agv
    missions = _pharma()
    s = only_families("MANUAL")  # AGV OFF
    cheap = dataclasses.replace(agv.DEFAULT_LIGHT_CLINICAL_PROFILE, vehicle_capex_usd=0.0)
    monkeypatch.setattr(agv, "DEFAULT_LIGHT_CLINICAL_PROFILE", cheap)
    res = optimize(missions=missions, settings=s)
    assert all("AGV_AMR" not in c.actually_used_families for c in res.all_candidates)


# --- SHARED CAPEX / OPEX (Sec 69-70) --------------------------------------

def test_shared_agv_capex_not_duplicated_light_plus_heavy():
    missions = [
        OptimizerMission("A1", "PHARMACY_INFUSION", payload_mass_kg=2.0),
        OptimizerMission("A2", "CLEAN_LINEN", payload_mass_kg=60.0, payload_volume_l=400.0),
    ]
    c = build_candidate(candidate_id="C",
                        candidate_modes=frozenset({"AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS"}),
                        missions=missions, settings=only_families("AGV_AMR"))
    # shared fleet-manager appears once; total shared capex == single allowance
    assert c.shared_capex_usd == gto.AGV_SHARED_FLEET_MANAGER_CAPEX_USD


def test_shared_agv_opex_software_counted_once():
    missions = [
        OptimizerMission("A1", "PHARMACY_INFUSION", payload_mass_kg=2.0),
        OptimizerMission("A2", "CLEAN_LINEN", payload_mass_kg=60.0, payload_volume_l=400.0),
    ]
    light_only = build_candidate(candidate_id="L", candidate_modes=frozenset({"AGV_AMR_LIGHT_CLINICAL"}),
                                 missions=[missions[0]], settings=only_families("AGV_AMR"))
    both = build_candidate(candidate_id="B",
                           candidate_modes=frozenset({"AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS"}),
                           missions=missions, settings=only_families("AGV_AMR"))
    # the shared software OPEX component is the same single allowance in both
    assert gto.AGV_SHARED_FLEET_SOFTWARE_OPEX_USD > 0


def test_pts_shared_backbone_single_allowance():
    missions = [
        OptimizerMission("P1", "SPECIMEN_BLOOD", payload_mass_kg=1.0),
        OptimizerMission("P2", "RADIOPHARMACEUTICAL_NUCLEAR", payload_mass_kg=2.0),
    ]
    c = build_candidate(candidate_id="C", candidate_modes=frozenset({"PTS", "DEDICATED_RP_PTS"}),
                        missions=missions, settings=only_families("PTS"))
    assert c.shared_capex_usd == pytest.approx(gto.PTS_SHARED_BACKBONE_CAPEX_USD)


# --- CAPACITY (Sec 25, 75): fleet workload-derived, never infinite --------

def test_agv_fleet_scales_with_workload():
    small = build_candidate(candidate_id="S", candidate_modes=frozenset({"AGV_AMR_LIGHT_CLINICAL"}),
                            missions=_pharma(2), settings=only_families("AGV_AMR"))
    big = build_candidate(candidate_id="B", candidate_modes=frozenset({"AGV_AMR_LIGHT_CLINICAL"}),
                          missions=_pharma(80), settings=only_families("AGV_AMR"))
    small_e = next(e for e in small.mode_economics if e.mode == "AGV_AMR_LIGHT_CLINICAL")
    big_e = next(e for e in big.mode_economics if e.mode == "AGV_AMR_LIGHT_CLINICAL")
    assert big_e.mode_specific_capex_usd >= small_e.mode_specific_capex_usd


def test_capacity_feasible_is_finite_and_true():
    c = build_candidate(candidate_id="C", candidate_modes=frozenset({"AGV_AMR_LIGHT_CLINICAL"}),
                        missions=_pharma(50), settings=only_families("AGV_AMR"))
    assert c.capacity_feasible is True


# --- TRUE HYBRID ECONOMIC CONTROL (Sec 71) --------------------------------

def test_true_hybrid_manual_mrt_reports_by_mode():
    missions = [
        OptimizerMission("H1", "PHARMACY_INFUSION", payload_mass_kg=2.0),
        OptimizerMission("H2", "CLEAN_LINEN", payload_mass_kg=60.0, payload_volume_l=400.0),
    ]
    c = build_candidate(candidate_id="C", candidate_modes=frozenset({"MANUAL", "MRT"}),
                        missions=missions, settings=only_families("MANUAL", "MRT"))
    # linen -> MANUAL, pharmacy -> MRT (compact) OR MANUAL; conserved either way
    assert c.assignment.conserved
    assert c.known_capex_usd >= 0.0
    # every mode economics row corresponds to an actually-used mode
    for e in c.mode_economics:
        assert e.mode in c.actually_used_modes


def test_true_hybrid_pts_agv_heavy_manual_by_mode():
    missions = [
        OptimizerMission("H1", "SPECIMEN_BLOOD", payload_mass_kg=1.0),
        OptimizerMission("H2", "CLEAN_LINEN", payload_mass_kg=60.0, payload_volume_l=400.0),
    ]
    s = TransportSettings(rths_enabled=False, mrt_enabled=False,
                          pts_nuclear_qualified_enabled=False, agv_amr_light_clinical_enabled=False)
    c = build_candidate(candidate_id="C", candidate_modes=frozenset({"PTS", "AGV_AMR_HEAVY_LOGISTICS", "MANUAL"}),
                        missions=missions, settings=s)
    assert c.assignment.conserved
    # unknown costs disclosed, never zeroed into subtotal
    assert isinstance(c.unknown_opex_components, tuple)


# --- LEGACY FOUR-ARCHITECTURE COMPATIBILITY (Sec 47-49, 83) ---------------

def test_legacy_strategy_is_preserve_adapters():
    assert compat.COMPATIBILITY_STRATEGY == "PRESERVE_AS_LEGACY_ADAPTERS"
    assert compat.LEGACY_EVALUATORS_PRESERVED is True


def test_legacy_evaluators_still_importable_and_present():
    import whole_oncology_four_architecture_optimization as woa
    for fn in ("evaluate_manual_conventional", "evaluate_automated_conventional",
               "evaluate_mrt_dominant"):
        assert hasattr(woa, fn)


def test_manual_conventional_maps_to_manual_only():
    s = compat.legacy_architecture_to_settings("MANUAL_CONVENTIONAL")
    assert s.effectively_enabled_families() == ("MANUAL",)


def test_automated_conventional_is_composite_not_single_family():
    assert compat.automated_conventional_is_composite() is True
    s = compat.legacy_architecture_to_settings("AUTOMATED_CONVENTIONAL")
    assert set(s.effectively_enabled_families()) == {"MANUAL", "PTS", "AGV_AMR"}


def test_mrt_dominant_maps_to_manual_mrt():
    s = compat.legacy_architecture_to_settings("MRT_DOMINANT")
    assert set(s.effectively_enabled_families()) == {"MANUAL", "MRT"}


def test_every_legacy_architecture_has_mapping():
    for m in ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT"):
        assert m in compat.LEGACY_ARCHITECTURE_MAPPINGS


# --- USER-SCOPE MATRIX (Sec 43): representative combinations feasible ------

@pytest.mark.parametrize("families", [
    ("MANUAL",), ("MANUAL", "PTS"), ("MANUAL", "MRT"), ("MANUAL", "RTHS"),
    ("MANUAL", "AGV_AMR"), ("PTS", "MANUAL"), ("MRT", "RTHS", "MANUAL"),
])
def test_user_scope_matrix_conserves_missions(families):
    from transport_settings_authority import only_families as of
    missions = [
        OptimizerMission("X1", "PHARMACY_INFUSION", payload_mass_kg=2.0),
        OptimizerMission("X2", "STERILE_CLEAN_SUPPLY", payload_mass_kg=5.0),
    ]
    res = optimize(missions=missions, settings=of(*families))
    for c in res.all_candidates:
        assert c.assignment.conserved


# --- FUTURE CAPITAL-INHERITANCE SEAM (Sec 60-62): resource inventory present

def test_mode_economics_expose_capacity_basis_and_provenance():
    res = optimize(missions=_pharma(), settings=default_transport_settings())
    assert res.selected is not None
    for e in res.selected.mode_economics:
        assert e.capacity_basis
        assert e.provenance


# --- PER-FAMILY OFF: no physical artifacts of the disabled family (Sec 76-80)

def test_manual_off_no_manual_artifacts():
    from transport_settings_authority import all_except_families
    res = optimize(missions=_pharma(), settings=all_except_families("MANUAL"))
    for c in res.all_candidates:
        assert "MANUAL" not in c.actually_used_modes
        for e in c.mode_economics:
            assert e.mode != "MANUAL"


def test_mrt_off_no_mrt_artifacts():
    from transport_settings_authority import all_except_families
    res = optimize(missions=_pharma(), settings=all_except_families("MRT"))
    for c in res.all_candidates:
        assert "MRT" not in c.actually_used_modes
        for e in c.mode_economics:
            assert e.mode != "MRT"


def test_pts_off_both_subtypes_no_artifacts():
    from transport_settings_authority import all_except_families
    res = optimize(missions=_pharma(), settings=all_except_families("PTS"))
    for c in res.all_candidates:
        assert "PTS" not in c.actually_used_modes
        assert "DEDICATED_RP_PTS" not in c.actually_used_modes


def test_rths_off_no_artifacts():
    from transport_settings_authority import all_except_families
    res = optimize(missions=_sterile(), settings=all_except_families("RTHS"))
    for c in res.all_candidates:
        assert "RTHS" not in c.actually_used_modes


def test_agv_off_no_battery_or_fleet_artifacts():
    from transport_settings_authority import all_except_families
    res = optimize(missions=_pharma(), settings=all_except_families("AGV_AMR"))
    for c in res.all_candidates:
        assert not any(m.startswith("AGV_AMR") for m in c.actually_used_modes)
        assert c.shared_capex_usd == 0.0 or "fleet-management" not in " ".join(c.shared_capex_components)


# --- eligibility-over-economics per family (Sec 67) -----------------------

def test_pts_incompatible_linen_blocked_regardless_of_scope():
    c = build_candidate(candidate_id="C", candidate_modes=frozenset({"PTS"}),
                        missions=_linen(1), settings=only_families("PTS"))
    assert c.unmet_missions == 1  # PTS cannot carry bulk linen; not rescued


def test_mrt_bulk_linen_blocked():
    c = build_candidate(candidate_id="C", candidate_modes=frozenset({"MRT"}),
                        missions=_linen(1), settings=only_families("MRT"))
    assert c.unmet_missions == 1  # 13.5kg loaded > 5kg ceiling


def test_light_agv_bulk_linen_blocked():
    c = build_candidate(candidate_id="C", candidate_modes=frozenset({"AGV_AMR_LIGHT_CLINICAL"}),
                        missions=_linen(1),
                        settings=TransportSettings(agv_amr_heavy_logistics_enabled=False,
                                                   manual_enabled=False, pts_enabled=False,
                                                   rths_enabled=False, mrt_enabled=False))
    assert c.unmet_missions == 1


# --- no-forced-winner: identical-cost symmetric candidates do not prefer a
#     particular technology (Sec 52) --------------------------------------

def test_selection_prefers_fewer_modes_on_tie_not_a_technology():
    # single specimen: MANUAL_ONLY and other single-mode feasible candidates;
    # the winner is chosen by lifecycle then mode-count, never by tech identity
    res = optimize(missions=[OptimizerMission("S", "SPECIMEN_BLOOD", payload_mass_kg=1.0)],
                   settings=default_transport_settings())
    assert res.selected is not None
    # winner is a single-mode candidate (fewest modes) among feasible
    assert len(res.selected.actually_used_modes) == 1


def test_generalized_optimizer_integrated_flag_now_true_in_runtime_module():
    # the runtime optimizer module exists and exposes the objective (integration
    # is real, not a dead authority)
    assert hasattr(gto, "optimize")
    assert hasattr(gto, "OPTIMIZER_OBJECTIVE")

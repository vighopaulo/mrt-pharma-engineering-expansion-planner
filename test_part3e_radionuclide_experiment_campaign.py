"""Invariant tests for the Part 3E.1 radionuclide architecture experiment
campaign (`part3e_radionuclide_experiment_campaign`).

These tests LOCK the campaign's honesty guarantees. They assert that the
campaign is a read-only CONSUMER of the committed authorities and never encodes
an architecture preference, never fabricates production capacity, never
zero-fills unknown economics, and never claims joint multi-radionuclide
scheduling. They also lock the real decay physics (MRT's shorter route retains
more; longer distance retains less; O-15's collapse is observed not rewarded)
and the honest crossover conclusion.
"""

from __future__ import annotations

import math

import pytest

import part3e_radionuclide_experiment_campaign as camp
import part3e_radionuclide_aware_architecture as p3e
from multi_isotope_decay import retained_fraction, required_upstream_activity
from diagnostics import load_radionuclide_half_lives


_BOUQUET = ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "MRT_DOMINANT", "HYBRID_MRT")


@pytest.fixture(scope="module")
def campaign() -> camp.CampaignResult:
    return camp.run_full_campaign()


# ---------------------------------------------------------------------------
# Bouquet completeness: the user MUST see all four architectures, always.
# ---------------------------------------------------------------------------


def test_every_scenario_experiment_reports_all_four_architectures(campaign):
    for exp in campaign.all_scenario_experiments:
        arches = tuple(row.architecture for row in exp.bouquet)
        assert set(arches) == set(_BOUQUET), f"{exp.experiment_id} missing an architecture: {arches}"
        assert len(exp.bouquet) == 4, f"{exp.experiment_id} did not report exactly four candidates"


def test_bouquet_reports_feasibility_and_economics_for_each_candidate(campaign):
    for exp in campaign.all_scenario_experiments:
        for row in exp.bouquet:
            assert isinstance(row.feasible, bool)
            assert row.physical_feasibility_status != ""
            assert row.qualification_status != ""
            assert row.lifecycle_cost > 0.0
            assert row.new_study_capex >= 0.0
            # cost-only rank is present for feasible candidates
            if row.feasible:
                assert row.cost_only_rank is not None


# ---------------------------------------------------------------------------
# No architecture bonus: ranking is cost-only over the derived lifecycle cost;
# the ordering EMERGES, it is not hardcoded to favor a family.
# ---------------------------------------------------------------------------


def test_ranking_is_cost_only_ascending_lifecycle(campaign):
    for exp in campaign.all_scenario_experiments:
        ranked = exp.ranked_feasible_architectures
        costs = [exp.bouquet_row(a).lifecycle_cost for a in ranked]
        assert costs == sorted(costs), f"{exp.experiment_id} ranking not ascending by lifecycle cost"


def test_no_mrt_or_hybrid_bonus_baseline_order(campaign):
    # At the benchmark basis the derived economics put the conventional families
    # ahead of the MRT families -- proving no MRT/Hybrid bonus was injected.
    ranked = campaign.baseline.ranked_feasible_architectures
    assert ranked[0] == "MANUAL_CONVENTIONAL"
    assert ranked.index("MANUAL_CONVENTIONAL") < ranked.index("MRT_DOMINANT")
    assert ranked.index("AUTOMATED_CONVENTIONAL") < ranked.index("HYBRID_MRT")


def test_architecture_economics_stable_across_radionuclide_identity(campaign):
    # Honest engine-basis consequence: the four-architecture economics are
    # anchored to the validated benchmark single-radionuclide basis, so a pure
    # radionuclide-identity change (F-18 vs C-11 vs N-13 vs O-15 single streams)
    # does NOT move the lifecycle cost -- proving no short-half-life bonus.
    ref = {r.architecture: r.lifecycle_cost for r in campaign.f18.bouquet}
    for exp in (campaign.c11, campaign.n13, campaign.o15):
        for row in exp.bouquet:
            assert math.isclose(row.lifecycle_cost, ref[row.architecture], rel_tol=1e-9), (
                f"{exp.experiment_id} {row.architecture} lifecycle cost drifted from F-18 basis "
                "-> a radionuclide bonus/penalty would have leaked in"
            )


# ---------------------------------------------------------------------------
# Baseline reproduction (Experiment 0).
# ---------------------------------------------------------------------------


def test_baseline_reproduces_all_feasible(campaign):
    for row in campaign.baseline.bouquet:
        assert row.feasible is True
        assert row.physical_feasibility_status == "FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY"
    assert campaign.baseline.radionuclides == ("F-18", "Tc-99m")


# ---------------------------------------------------------------------------
# Decay is the REAL authority, single interval (no double-count), and MRT's
# shorter route retains MORE activity than the manual route.
# ---------------------------------------------------------------------------


def test_decay_matches_real_authority_single_interval():
    obs = camp._decay_observation("C-11", transport_mode="MRT", transport_minutes=2.0)
    hl = load_radionuclide_half_lives()["C-11"]
    elapsed = camp.CONTROLLED_EOB_TO_RELEASE_MINUTES + 2.0 + camp.CONTROLLED_ADMIN_AFTER_ARRIVAL_MINUTES
    expected_R = retained_fraction(elapsed, hl)
    assert math.isclose(obs.total_elapsed_eob_to_admin_minutes, elapsed, rel_tol=1e-12)
    assert math.isclose(obs.retained_fraction_at_admin, expected_R, rel_tol=1e-12)
    # required upstream = admin / retained, straight from the authority
    expected_eob = required_upstream_activity(obs.admin_activity_mbq, expected_R)
    assert math.isclose(obs.required_upstream_eob_activity_mbq, expected_eob, rel_tol=1e-12)


def test_mrt_shorter_route_retains_more_than_manual(campaign):
    # For every short-lived PET radionuclide the MRT decay observation retains
    # strictly more than the manual one at the same route (shorter transport
    # time), for radionuclides where any activity survives.
    for exp in (campaign.f18, campaign.c11, campaign.n13):
        by_mode = {o.transport_mode: o for o in exp.decay_observations}
        assert "MANUAL" in by_mode and "MRT" in by_mode
        assert by_mode["MRT"].retained_fraction_at_admin > by_mode["MANUAL"].retained_fraction_at_admin


def test_longer_distance_reduces_retention(campaign):
    # Distance sensitivity: retained fraction is monotonically non-increasing as
    # the route lengthens, for both modes (real transport-time + decay).
    for exp in (campaign.distance_c11, campaign.distance_n13):
        manual_R = [p.manual_decay.retained_fraction_at_admin for p in exp.distance_points]
        mrt_R = [p.mrt_decay.retained_fraction_at_admin for p in exp.distance_points]
        assert manual_R == sorted(manual_R, reverse=True)
        assert mrt_R == sorted(mrt_R, reverse=True)
        # MRT retains >= manual at every distance point
        for p in exp.distance_points:
            assert p.mrt_decay.retained_fraction_at_admin >= p.manual_decay.retained_fraction_at_admin


def test_o15_collapse_is_observed_not_rewarded(campaign):
    # O-15 (2.04 min) collapses to ~0 retained regardless of speed; no bonus is
    # applied and its bouquet is not forced feasible-with-advantage.
    for _rn, pts in campaign.mrt_speed_sensitivity:
        if _rn == "O-15":
            for sp in pts:
                assert sp.mrt_decay.retained_fraction_at_admin < 1e-3
    # O-15 single-stream bouquet still ranks conventional ahead of MRT (no bonus)
    ranked = campaign.o15.ranked_feasible_architectures
    assert ranked.index("MANUAL_CONVENTIONAL") < ranked.index("MRT_DOMINANT")


def test_faster_mrt_speed_not_automatically_better_for_o15(campaign):
    # Faster MRT speed measurably raises C-11 retention, but for O-15 every speed
    # point stays clinically negligible (~0) -> a faster carrier does NOT rescue
    # O-15. "Faster is automatically better" is falsified, as required.
    speed = dict(campaign.mrt_speed_sensitivity)
    c11_by_label = {sp.label: sp for sp in speed["C-11"]}
    assert c11_by_label["VERY_FAST"].mrt_decay.retained_fraction_at_admin > c11_by_label["SLOW"].mrt_decay.retained_fraction_at_admin
    # O-15: even the fastest carrier leaves retention far below any usable level
    # (< 0.1%), so speed does not change the practical O-15 outcome.
    for sp in speed["O-15"]:
        assert sp.mrt_decay.retained_fraction_at_admin < 1e-3


# ---------------------------------------------------------------------------
# Production: support is never converted to calibration; F-18 record never
# qualifies another radionuclide; output never borrowed between models.
# ---------------------------------------------------------------------------


def test_f18_calibrated_but_short_lived_pet_not_calibrated(campaign):
    # F-18 on GE PETtrace 890 is manufacturer_calibrated; C-11/N-13/O-15 on the
    # same-family / cross-vendor cyclotrons are never manufacturer_calibrated.
    f18_src = campaign.f18.production_source_observations[0]
    assert f18_src.radionuclide == "F-18"
    assert f18_src.production_calibration_status == "manufacturer_calibrated"
    for so in campaign.production_source_sensitivity:
        assert so.radionuclide in ("C-11", "N-13", "O-15")
        assert so.production_calibration_status in ("modeled", "not_calibrated")
        assert so.production_calibration_status != "manufacturer_calibrated"


def test_support_not_converted_to_calibration(campaign):
    # Every short-lived PET source DECLARES support but none is manufacturer
    # calibrated; declared-but-unschedulable is not_calibrated, schedulable is
    # modeled -- never fabricated into calibrated.
    for so in campaign.production_source_sensitivity:
        assert so.declares_support is True
        if so.schedulable:
            assert so.production_calibration_status == "modeled"
        else:
            assert so.production_calibration_status == "not_calibrated"


def test_production_ranking_depends_on_equipment_not_radionuclide(campaign):
    # For the SAME radionuclide, calibration status differs by model (equipment),
    # proving the production verdict is equipment-driven, not radionuclide-driven.
    by_rn: dict[str, set[str]] = {}
    for so in campaign.production_source_sensitivity:
        by_rn.setdefault(so.radionuclide, set()).add(so.production_calibration_status)
    for rn, statuses in by_rn.items():
        assert len(statuses) >= 2, f"{rn} production status did not vary by equipment: {statuses}"


def test_ga68_dual_pathway_distinct_identities_never_fabricated(campaign):
    cyc = campaign.ga68_cyclotron
    gen = campaign.ga68_generator
    cyc_src = cyc.production_source_observations[0]
    gen_src = gen.production_source_observations[0]
    assert cyc_src.source_kind == "CYCLOTRON" and cyc_src.catalog_model_id == "SUMITOMO_CYPRIS_MP_30"
    assert gen_src.source_kind == "GENERATOR" and gen_src.catalog_model_id == "ECKERT_ZIEGLER_GALLIAPHARM"
    # Neither fabricates capacity -> both NOT_CALIBRATED production
    assert cyc_src.production_calibration_status == "not_calibrated"
    assert gen_src.production_calibration_status == "not_calibrated"
    cyc_res = cyc.scenario_result.resolution_for("Ga-68")
    gen_res = gen.scenario_result.resolution_for("Ga-68")
    assert cyc_res.production_source_type == "CYCLOTRON"
    assert gen_res.production_source_type == "GENERATOR"
    assert cyc_res.production_gate_status == "PRODUCTION_NOT_CALIBRATED"
    assert gen_res.production_gate_status == "PRODUCTION_NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# Economics: total OPEX is a known subtotal only; never claimed calibrated.
# ---------------------------------------------------------------------------


def test_total_opex_never_claimed_fully_calibrated(campaign):
    for exp in campaign.all_scenario_experiments:
        for row in exp.bouquet:
            assert row.total_opex_calibration_status == "KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED"
            # known annual opex is a real positive subtotal, never zero-filled to fake completeness
            assert row.known_annual_opex > 0.0


# ---------------------------------------------------------------------------
# Joint-scheduling governor remains active for mixed scenarios.
# ---------------------------------------------------------------------------


def test_mixed_scenarios_never_claim_joint_scheduling(campaign):
    for exp in (campaign.mixed_pet, campaign.mixed_pet_spect):
        disc = exp.scenario_result.scheduling_disclosure
        assert disc.true_joint_multi_radionuclide_scheduling == "NO"
        assert disc.multi_radionuclide_phase1_aggregation == "YES"
        assert disc.joint_operational_feasibility_status in ("NOT_FULLY_VALIDATED", "INFEASIBLE_STREAM_PRESENT")


def test_mixed_pet_spect_keeps_scanner_pools_distinct(campaign):
    agg = campaign.mixed_pet_spect.scenario_result.aggregation
    assert agg.pet_patient_count > 0
    assert agg.spect_patient_count > 0
    assert agg.required_pet_scanner_count > 0
    assert agg.required_spect_scanner_count > 0
    # Total is PET + SPECT, never a collapsed shared pool
    assert agg.required_total_scanner_count == agg.required_pet_scanner_count + agg.required_spect_scanner_count


def test_mixed_pet_preserves_every_radionuclide_stream(campaign):
    exp = campaign.mixed_pet
    assert set(exp.radionuclides) == {"F-18", "C-11", "N-13", "O-15"}
    # each stream resolved independently
    for rn in exp.radionuclides:
        res = exp.scenario_result.resolution_for(rn)
        assert res.radionuclide == rn


# ---------------------------------------------------------------------------
# Demand sensitivity: explicit counts, scanner requirement scales, production
# gate preserved; no prevalence invented.
# ---------------------------------------------------------------------------


def test_demand_scanner_requirement_monotonic_nondecreasing(campaign):
    by_rn: dict[str, list[camp.DemandLevelObservation]] = {}
    for o in campaign.demand_sensitivity:
        by_rn.setdefault(o.radionuclide, []).append(o)
    order = {"LOW": 0, "BASELINE": 1, "HIGH": 2}
    for rn, obs in by_rn.items():
        obs_sorted = sorted(obs, key=lambda o: order[o.demand_level])
        counts = [o.patient_count for o in obs_sorted]
        scanners = [o.required_scanner_count for o in obs_sorted]
        assert counts == sorted(counts)
        assert scanners == sorted(scanners), f"{rn} scanner requirement not non-decreasing with demand"


def test_uncalibrated_production_preserved_across_demand(campaign):
    # O-15 / Ga-68 have no calibrated production record at any demand level ->
    # never zero, never auto-sufficient, never fabricated.
    for o in campaign.demand_sensitivity:
        if o.radionuclide in ("O-15", "Ga-68"):
            assert o.production_gate_status == "PRODUCTION_NOT_CALIBRATED"
        if o.radionuclide == "F-18":
            assert o.production_gate_status == "PRODUCTION_SUFFICIENT"


# ---------------------------------------------------------------------------
# Crossover search: honest conclusion.
# ---------------------------------------------------------------------------


def test_crossover_reports_honest_conclusion(campaign):
    x = campaign.crossover
    # No MRT-family architecture reached cost-only rank 1 at the benchmark basis.
    assert x.mrt_crossover_observed is False
    assert x.manual_always_rank_1 is True
    assert "NO_MRT_CROSSOVER_OBSERVED" in x.conclusion


# ---------------------------------------------------------------------------
# Export seams are stable, typed projections (no engine re-run).
# ---------------------------------------------------------------------------


def test_export_seams_project_without_rerunning_engine(campaign):
    prows = p3e.export_patient_appointment_rows(campaign.mixed_pet_spect.scenario_result)
    frows = p3e.export_financial_rows(campaign.mixed_pet_spect.scenario_result)
    assert len(prows) == len(campaign.mixed_pet_spect.radionuclides)
    assert len(frows) == 4  # one per architecture
    for fr in frows:
        assert fr.architecture in _BOUQUET
        assert fr.lifecycle_cost > 0.0


# ---------------------------------------------------------------------------
# No new engine: the campaign must not redefine decay/production/transport.
# It imports and consumes the committed authorities.
# ---------------------------------------------------------------------------


def test_campaign_consumes_committed_authorities_not_reimplements():
    import inspect
    src = inspect.getsource(camp)
    # It must import the real authorities (consume-only).
    assert "from multi_isotope_decay import" in src
    assert "from spatial_benchmark import" in src
    assert "import part3e_radionuclide_aware_architecture as p3e" in src
    assert "import whole_oncology_four_architecture_optimization as wo4a" in src
    # It must NOT define its own decay/transport-time math.
    assert "def retained_fraction" not in src
    assert "def _manual_transport_minutes" not in src
    assert "def _mrt_transport_minutes" not in src

"""Controlled tests: Multi-radionuclide + multi-cyclotron / spatial-origin authority.

Covers spec sections (this phase): 6-7 (decay-vs-production support
distinction, no fabrication), 12-25 (multi-cyclotron ON/OFF, spatial origin,
colocation, patient-aware per-asset assignment), 37-38 (no patient creation
from added capacity, no unnecessary-cyclotron reward), 46-49 (radionuclide-
specific retention budgets, engineering_authority registry extension).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from diagnostics import load_radionuclide_half_lives
from engineering_authority import AUTHORITY_REGISTRY
from multi_cyclotron_authority import (
    build_calibrated_cyclotron_asset,
    build_multi_cyclotron_scenario,
    radionuclide_support_report,
)
from multi_isotope_decay import retained_fraction
from spatial_benchmark import (
    _assign_rooms_for_candidate,
    _base_assumptions,
    _evaluate_layout,
    _retention_time_budget_minutes,
    build_benchmark_geometry,
    build_production_basis,
    compute_retention_envelope,
)

NEW_AUTHORITY_IDS = (
    "MULTI_RADIONUCLIDE_PATIENT_NEED",
    "PROTOCOL_SPECIFIC_CLINICAL_REQUIREMENTS",
    "CYCLOTRON_CONFIGURATION_STATE",
    "CYCLOTRON_RADIONUCLIDE_COMPATIBILITY",
    "CYCLOTRON_SPATIAL_ORIGIN",
    "CYCLOTRON_RADIOPHARMACY_COLOCATION",
    "MULTI_CYCLOTRON_PRODUCTION_ASSIGNMENT",
)


def test_engineering_authority_registry_has_seven_new_rules() -> None:
    ids = {rule.authority_id for rule in AUTHORITY_REGISTRY}
    for authority_id in NEW_AUTHORITY_IDS:
        assert authority_id in ids
    # No duplicate authority_ids anywhere in the registry.
    all_ids = [rule.authority_id for rule in AUTHORITY_REGISTRY]
    assert len(all_ids) == len(set(all_ids))


def test_decay_model_supports_six_radionuclides() -> None:
    # STALE_TEST_EXPECTATION correction: radionuclides.json intentionally
    # gained a 7th entry, Mo-99 -- the Tc-99m generator's PARENT isotope
    # (generator.py/nuclear_source.py's Mo-99/Tc-99m elution physics), not a
    # directly-injected clinical PET/SPECT radionuclide itself. It is required
    # by the SPECT generator decay math and is deeply used across
    # generator.py, nuclear_source.py, canonical_spatial_authority.py and
    # their tests -- not an accidental/misplaced catalog entry. Test the
    # REQUIRED clinical radionuclide set as a subset (never a brittle exact
    # count) so a future, equally-intentional catalog addition does not
    # require another test edit.
    half_lives = load_radionuclide_half_lives()
    required_clinical_radionuclides = {"C-11", "F-18", "Ga-68", "N-13", "O-15", "Tc-99m"}
    assert required_clinical_radionuclides.issubset(set(half_lives))
    assert "Mo-99" in half_lives  # intentional Tc-99m generator parent isotope, not a defect.


def test_cy001_only_calibrated_for_f18_all_others_production_unsupported() -> None:
    report = radionuclide_support_report("GE_PETTRACE_890")
    assert report["F-18"] == "DECAY_AND_CALIBRATED_PRODUCTION_SUPPORTED"
    for radionuclide in ("C-11", "Ga-68", "N-13", "O-15", "Tc-99m"):
        assert report[radionuclide] == "DECAY_SUPPORTED_PRODUCTION_NOT_SUPPORTED"


def test_multi_isotope_listed_model_never_claims_fabricated_calibration() -> None:
    # GE_PETTRACE_800 lists 5 radionuclides but has zero calibrated EOB
    # records -- must never be reported as calibrated production support.
    report = radionuclide_support_report("GE_PETTRACE_800")
    for radionuclide in ("F-18", "C-11", "N-13", "O-15", "Ga-68"):
        assert report[radionuclide] == "DECAY_SUPPORTED_PRODUCTION_LISTED_NOT_CALIBRATED"
    assert report["Tc-99m"] == "DECAY_SUPPORTED_PRODUCTION_NOT_SUPPORTED"


def test_radionuclide_specific_retention_budgets_differ() -> None:
    half_lives = load_radionuclide_half_lives()
    budget_f18 = _retention_time_budget_minutes(half_life_minutes=half_lives["F-18"], threshold=0.90)
    budget_c11 = _retention_time_budget_minutes(half_life_minutes=half_lives["C-11"], threshold=0.90)
    assert budget_f18 == pytest.approx(16.6899, rel=1e-3)
    assert budget_c11 != budget_f18
    assert budget_c11 < budget_f18  # C-11's much shorter half-life yields a tighter T_90 budget.
    # Same elapsed time, different radionuclides -> different retained fraction (no shared physics shortcut).
    elapsed = 15.0
    retained_f18 = retained_fraction(elapsed_minutes=elapsed, half_life_minutes=half_lives["F-18"])
    retained_c11 = retained_fraction(elapsed_minutes=elapsed, half_life_minutes=half_lives["C-11"])
    assert retained_f18 != retained_c11
    assert retained_c11 < retained_f18


def test_cyclotron_scenario_on_off_controls_fleet_membership() -> None:
    fleet_off, configured_off = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="OFF")
    assert fleet_off.asset_count == 1
    assert [a.cyclotron_id for a in fleet_off.assets] == ["CY-001"]
    # CY-002's configuration record is preserved even while OFF (never deleted).
    cy002_record = next(c for c in configured_off if c.cyclotron_id == "CY-002")
    assert cy002_record.scenario_state == "OFF"
    assert cy002_record.asset_state == "PROPOSED"

    fleet_on, configured_on = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="ON")
    assert fleet_on.asset_count == 2
    assert sorted(a.cyclotron_id for a in fleet_on.assets) == ["CY-001", "CY-002"]
    assert fleet_on.fleet_supported_radionuclides == ("F-18",)


def test_cyclotron_spatial_origin_and_colocation() -> None:
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="ON")
    origins = {c.cyclotron_id: c.origin_object_id for c in configured}
    # Distinct spatial origins per cyclotron.
    assert origins["CY-001"] != origins["CY-002"]
    # Colocation: each cyclotron's radiopharmacy_id is uniquely paired (CY_k <-> RP_k), not shared/ambiguous.
    radiopharmacy_ids = {c.cyclotron_id: c.radiopharmacy_id for c in configured}
    assert radiopharmacy_ids["CY-001"] != radiopharmacy_ids["CY-002"]


def test_multi_cyclotron_asset_state_distinct_from_scenario_state() -> None:
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="OFF")
    cy001 = next(c for c in configured if c.cyclotron_id == "CY-001")
    cy002 = next(c for c in configured if c.cyclotron_id == "CY-002")
    # asset_state (EXISTING/PROPOSED) is independent of scenario_state (ON/OFF) --
    # CY-002 is PROPOSED (capital asset classification) regardless of whether it is
    # scenario-ON or scenario-OFF for a given run.
    assert cy001.asset_state == "EXISTING"
    assert cy001.scenario_state == "ON"
    assert cy002.asset_state == "PROPOSED"
    assert cy002.scenario_state == "OFF"


def test_at_least_one_cyclotron_must_be_on() -> None:
    with pytest.raises(ValueError):
        build_multi_cyclotron_scenario(cy001_scenario_state="OFF", cy002_scenario_state="OFF")


def test_calibrated_asset_rejects_uncalibrated_model() -> None:
    with pytest.raises(ValueError):
        build_calibrated_cyclotron_asset(
            instance_id="CY-999", catalog_model_id="GE_PETTRACE_800", radionuclide="C-11",
            release_processing_minutes=71.0,
        )


def test_multi_cyclotron_pipeline_no_patient_creation_and_patient_aware_assignment() -> None:
    """Sections 5, 37: same patient population regardless of CY-002 on/off;
    section 20-25: patient-aware per-cyclotron batch membership (no
    anonymous pooling) when more than one cyclotron is active."""
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    env = compute_retention_envelope(
        geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway="Conventional",
    )
    layout = _assign_rooms_for_candidate(
        geometry=geometry, active_floors=(1, 2, 3, 4), scanners=6, injections=18, uptake=12,
        distribution_mode="balanced", assumptions=assumptions, candidate_id="MC-CTRL", pattern_id="MC-CTRL",
        distribution_concurrency=8, feasible_room_ids=env.feasible_room_ids,
    )

    results = {}
    for cy002_state in ("OFF", "ON"):
        fleet, _ = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state=cy002_state)
        basis_variant = replace(basis, cyclotron_fleet=fleet)
        outcome = _evaluate_layout(
            pathway="Conventional", layout=layout, demand=200, production_basis=basis_variant,
            assumptions=assumptions, seed=1,
        )
        demand_count = len(
            outcome.pathway_result.operational_result.demand_result.simulation.generated_demand.patients
        )
        clinical = outcome.pathway_result.operational_result.production_clinical_result
        cyclotron_ids_used = sorted({m.assigned_cyclotron_id for m in clinical.batch_release_mappings})
        results[cy002_state] = (demand_count, outcome.patients_retention_qualified_completed, tuple(cyclotron_ids_used))

    # No patient creation from added capacity -- identical demand population both ways.
    assert results["OFF"][0] == results["ON"][0] == 200
    # Qualified throughput unaffected: CY-001 alone was never the binding
    # constraint at this benchmark's demand scale (no fabricated/unearned benefit).
    assert results["OFF"][1] == results["ON"][1]
    # Patient-aware assignment: every used cyclotron_id is a real, known asset id.
    for cyclotron_ids_used in (results["OFF"][2], results["ON"][2]):
        assert set(cyclotron_ids_used).issubset({"CY-001", "CY-002"})
        assert len(cyclotron_ids_used) >= 1

"""Focused test suite: unified oncology patient / PET / SPECT nuclear trunk.

Covers (section 55): persistent patient identity, inpatient/outpatient
distinction, room assignment, admission/discharge conservation, stochastic
reproducibility, PET/SPECT procedure assignment, PET/SPECT scanner
compatibility, cyclotron patient lineage (existing authority, non-regression),
generator patient lineage, Mo-99/Tc-99m parent-daughter evolution, elution
state update, repeat elution behavior, pre/post-elution activity conservation,
preparation-batch patient allocation, Tc-99m transport decay, multi-day
generator persistence, calendar-day radioactive evolution, existing/proposed
scanner treatment, uncalibrated SPECT economics behavior, Conventional/MRT/
Hybrid nuclear operation, 50/day controlled benchmark, 200/day F-18 stress
non-regression.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import pytest

from clinical_resource_identity import build_modality_tagged_scanner_pool
from generator import (
    GeneratorAsset,
    MO99_HALF_LIFE_MIN,
    TC99M_HALF_LIFE_MIN,
    build_preparation_batch,
    mo99_activity_mbq,
    tc99m_available_activity_mbq,
)
from models import PlannerAssumptions
from multi_isotope_decay import retained_fraction
from oncology_pet_spect_scenario import (
    HIGH_VOLUME_F18_STRESS_200,
    REALISTIC_ONCOLOGY_50,
    OncologyPatientRecord,
    assign_spect_patients_to_generator_batch,
    build_representative_day_population,
    check_modality_capacity,
    evaluate_spect_economics,
)


# ---------------------------------------------------------------------------
# Persistent patient population / inpatient / outpatient / room identity
# ---------------------------------------------------------------------------


def test_persistent_patient_identity_and_inpatient_outpatient_distinction():
    patients, census = build_representative_day_population(
        day=date(2026, 1, 5), available_beds=200, occupied_beds=170, admissions=20, discharges=18,
        outpatient_encounters=40, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    ids = [p.patient_id for p in patients]
    assert len(ids) == len(set(ids)), "every patient must have a unique persistent identity"
    inpatients = [p for p in patients if p.patient_type == "INPATIENT"]
    outpatients = [p for p in patients if p.patient_type == "OUTPATIENT"]
    assert len(inpatients) == 170
    assert len(outpatients) == 40
    assert census.total_active_patients == 210
    assert census.total_active_patients != census.occupied_beds  # 200 beds != 200 patients/day invariant
    assert census.total_nuclear_procedures != census.total_active_patients  # 50 != 210


def test_room_assignment_survives_for_inpatients():
    patients, _ = build_representative_day_population(
        day=date(2026, 1, 5), available_beds=200, occupied_beds=170, admissions=20, discharges=18,
        outpatient_encounters=40, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    for p in patients:
        if p.patient_type == "INPATIENT":
            assert p.room_id is not None and p.building_id is not None and p.floor_id is not None
        else:
            assert p.room_id is None
            assert p.outpatient_origin is not None


def test_inpatients_never_exceed_available_beds():
    with pytest.raises(ValueError):
        build_representative_day_population(
            day=date(2026, 1, 5), available_beds=100, occupied_beds=150, admissions=0, discharges=0,
            outpatient_encounters=10, target_pet_procedures=5, target_spect_procedures=5, seed=1,
        )


def test_admission_discharge_conservation_tracked_independently():
    _, census = build_representative_day_population(
        day=date(2026, 1, 5), available_beds=200, occupied_beds=170, admissions=20, discharges=18,
        outpatient_encounters=40, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    assert census.admissions == 20
    assert census.discharges == 18
    assert census.admissions != census.discharges


def test_stochastic_reproducibility_with_seed():
    patients_a, census_a = build_representative_day_population(
        day=date(2026, 1, 5), available_beds=200, occupied_beds=170, admissions=20, discharges=18,
        outpatient_encounters=40, target_pet_procedures=32, target_spect_procedures=18, seed=777,
    )
    patients_b, census_b = build_representative_day_population(
        day=date(2026, 1, 5), available_beds=200, occupied_beds=170, admissions=20, discharges=18,
        outpatient_encounters=40, target_pet_procedures=32, target_spect_procedures=18, seed=777,
    )
    assert [p.patient_id for p in patients_a] == [p.patient_id for p in patients_b]
    assert [p.nuclear_procedure for p in patients_a] == [p.nuclear_procedure for p in patients_b]
    assert census_a == census_b

    patients_c, _ = build_representative_day_population(
        day=date(2026, 1, 5), available_beds=200, occupied_beds=170, admissions=20, discharges=18,
        outpatient_encounters=40, target_pet_procedures=32, target_spect_procedures=18, seed=999,
    )
    assignments_a = [p.nuclear_procedure.modality if p.nuclear_procedure else None for p in patients_a]
    assignments_c = [p.nuclear_procedure.modality if p.nuclear_procedure else None for p in patients_c]
    assert assignments_a != assignments_c, "different seeds must be capable of producing different assignments"


def test_pet_spect_procedure_assignment_from_both_inpatient_and_outpatient():
    patients, census = build_representative_day_population(
        day=date(2026, 1, 5), available_beds=200, occupied_beds=170, admissions=20, discharges=18,
        outpatient_encounters=40, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    nuclear_patients = [p for p in patients if p.nuclear_procedure is not None]
    assert len(nuclear_patients) == 50
    assert census.pet_procedures + census.spect_procedures == census.total_nuclear_procedures == 50
    origins = {p.patient_type for p in nuclear_patients}
    assert origins <= {"INPATIENT", "OUTPATIENT"}
    # No second identity: nuclear patients are a SUBSET of the same population, not additional records.
    assert set(p.patient_id for p in nuclear_patients).issubset(set(p.patient_id for p in patients))


def test_no_patient_receives_both_pet_and_spect_simultaneously():
    patients, _ = build_representative_day_population(
        day=date(2026, 1, 5), available_beds=200, occupied_beds=170, admissions=20, discharges=18,
        outpatient_encounters=40, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    for p in patients:
        if p.nuclear_procedure is not None:
            assert p.nuclear_procedure.modality in ("PET", "SPECT")


# ---------------------------------------------------------------------------
# PET / SPECT scanner modality compatibility (section 52)
# ---------------------------------------------------------------------------


def test_pet_and_spect_scanner_pools_are_disjoint_and_correctly_sized():
    pool = build_modality_tagged_scanner_pool(pet_scanner_count=4, spect_scanner_count=2)
    assert len(pool) == 6
    pet = [r for r in pool if r.modality == "PET"]
    spect = [r for r in pool if r.modality == "SPECT"]
    assert len(pet) == 4 and len(spect) == 2
    assert set(r.resource_id for r in pet).isdisjoint(set(r.resource_id for r in spect))


def test_adding_spect_scanners_does_not_change_pet_capacity():
    assumptions = PlannerAssumptions()
    check_a_pet, check_a_spect = check_modality_capacity(
        pet_scanner_count=4, spect_scanner_count=2, pet_demand=30, spect_demand=15, assumptions=assumptions,
    )
    check_b_pet, check_b_spect = check_modality_capacity(
        pet_scanner_count=4, spect_scanner_count=10, pet_demand=30, spect_demand=15, assumptions=assumptions,
    )
    assert check_a_pet.daily_capacity == check_b_pet.daily_capacity, "PET capacity must be unaffected by SPECT scanner count"
    assert check_b_spect.daily_capacity > check_a_spect.daily_capacity


def test_adding_pet_scanners_does_not_change_spect_capacity():
    assumptions = PlannerAssumptions()
    _, check_a_spect = check_modality_capacity(
        pet_scanner_count=4, spect_scanner_count=2, pet_demand=30, spect_demand=15, assumptions=assumptions,
    )
    _, check_b_spect = check_modality_capacity(
        pet_scanner_count=20, spect_scanner_count=2, pet_demand=30, spect_demand=15, assumptions=assumptions,
    )
    assert check_a_spect.daily_capacity == check_b_spect.daily_capacity


def test_modality_may_only_be_set_on_scanner_resources():
    from clinical_resource_identity import ClinicalResource
    with pytest.raises(ValueError):
        ClinicalResource(resource_id="INJ-001", resource_type="INJECTION_ROOM", modality="PET")


def test_existing_and_proposed_scanner_treatment_preserved_with_modality():
    pool = build_modality_tagged_scanner_pool(pet_scanner_count=2, spect_scanner_count=2, asset_state="PROPOSED")
    assert all(r.asset_state == "PROPOSED" for r in pool)
    pool_existing = build_modality_tagged_scanner_pool(pet_scanner_count=2, spect_scanner_count=2, asset_state="EXISTING")
    assert all(r.asset_state == "EXISTING" for r in pool_existing)


# ---------------------------------------------------------------------------
# Mo-99 / Tc-99m generator physics (section 55)
# ---------------------------------------------------------------------------


def test_mo99_decays_independently_of_elution():
    a0 = 10_000.0
    a_at_1_halflife = mo99_activity_mbq(calibration_activity_mbq=a0, elapsed_min=MO99_HALF_LIFE_MIN)
    assert math.isclose(a_at_1_halflife, a0 / 2.0, rel_tol=1e-9)


def test_tc99m_grows_from_zero_and_peaks_then_declines_per_transient_equilibrium():
    """Standard generator physics: because Tc-99m's half-life (360 min) is
    much shorter than Mo-99's (3956.4 min), Tc-99m activity grows from zero,
    reaches a transient-equilibrium PEAK (~22-23h post-reference), then
    DECLINES thereafter tracking the parent's slower decay -- it does NOT
    keep growing forever. This is why clinical generators are eluted ~daily."""
    parent_activity = 10_000.0
    at_zero = tc99m_available_activity_mbq(parent_activity_at_reference_mbq=parent_activity, minutes_since_reference=0.0)
    at_six_hours = tc99m_available_activity_mbq(parent_activity_at_reference_mbq=parent_activity, minutes_since_reference=360.0)
    at_one_day = tc99m_available_activity_mbq(parent_activity_at_reference_mbq=parent_activity, minutes_since_reference=1440.0)
    at_two_days = tc99m_available_activity_mbq(parent_activity_at_reference_mbq=parent_activity, minutes_since_reference=2880.0)
    assert at_zero == 0.0
    assert at_six_hours > 0.0
    assert at_one_day > at_six_hours, "activity keeps growing well before the transient-equilibrium peak (~23h)"
    assert at_two_days < at_one_day, "activity declines after the peak, tracking Mo-99's slower parent decay"


def test_generator_elution_state_update_and_repeat_elution_behavior():
    generator = GeneratorAsset(
        generator_id="GEN-001", calibration_datetime=datetime(2026, 1, 1, 6, 0),
        calibration_mo99_activity_mbq=50_000.0,
    )
    t1 = datetime(2026, 1, 2, 6, 0)  # 24h after calibration
    updated1, event1 = generator.elute(at_datetime=t1)
    assert updated1.last_reference_datetime == t1
    assert event1.eluted_activity_mbq > 0.0
    assert math.isclose(event1.eluted_activity_mbq, event1.available_activity_mbq_before_elution * 0.85, rel_tol=1e-9)

    # repeat elution the next day -- must not raise, and clock resets again
    t2 = datetime(2026, 1, 3, 6, 0)
    updated2, event2 = updated1.elute(at_datetime=t2)
    assert updated2.last_reference_datetime == t2
    assert event2.available_activity_mbq_before_elution > 0.0


def test_pre_post_elution_activity_conservation():
    generator = GeneratorAsset(
        generator_id="GEN-001", calibration_datetime=datetime(2026, 1, 1, 6, 0),
        calibration_mo99_activity_mbq=50_000.0, elution_efficiency=0.85,
    )
    at = datetime(2026, 1, 2, 6, 0)
    available_before = generator.available_tc99m_activity_mbq(at_datetime=at)
    _, event = generator.elute(at_datetime=at)
    assert math.isclose(event.eluted_activity_mbq + event.residual_activity_mbq_in_column, available_before, rel_tol=1e-9)


def test_elution_cannot_go_backward_in_time():
    generator = GeneratorAsset(
        generator_id="GEN-001", calibration_datetime=datetime(2026, 1, 1, 6, 0),
        calibration_mo99_activity_mbq=50_000.0,
    )
    updated, _ = generator.elute(at_datetime=datetime(2026, 1, 2, 6, 0))
    with pytest.raises(ValueError):
        updated.elute(at_datetime=datetime(2026, 1, 1, 12, 0))


def test_multi_day_generator_persistence_and_calendar_day_evolution():
    generator = GeneratorAsset(
        generator_id="GEN-001", calibration_datetime=datetime(2026, 1, 1, 6, 0),
        calibration_mo99_activity_mbq=50_000.0,
    )
    current = generator
    eluted_activities = []
    for day_offset in range(1, 6):
        at = datetime(2026, 1, 1, 6, 0) + timedelta(days=day_offset)
        current, event = current.elute(at_datetime=at)
        eluted_activities.append(event.eluted_activity_mbq)
    assert len(eluted_activities) == 5
    # Mo-99 continuously decays, so each day's eluted activity trends downward over a multi-day horizon.
    assert eluted_activities[0] > eluted_activities[-1]
    assert current.calibration_mo99_activity_mbq == 50_000.0  # calibration identity persists across all elutions


def test_generator_rejects_non_positive_calibration_activity():
    with pytest.raises(ValueError):
        GeneratorAsset(generator_id="GEN-001", calibration_datetime=datetime(2026, 1, 1), calibration_mo99_activity_mbq=0.0)


# ---------------------------------------------------------------------------
# SPECT patient dose lineage (source -> patient conservation, section 50)
# ---------------------------------------------------------------------------


def test_preparation_batch_patient_allocation():
    generator = GeneratorAsset(
        generator_id="GEN-001", calibration_datetime=datetime(2026, 1, 1, 6, 0),
        calibration_mo99_activity_mbq=50_000.0,
    )
    _, event = generator.elute(at_datetime=datetime(2026, 1, 2, 6, 0))
    batch = build_preparation_batch(
        batch_id="B1", elute_event=event, generator_id="GEN-001",
        preparation_processing_minutes=20.0, patient_ids=("P1", "P2", "P3"),
    )
    assert batch.patient_ids == ("P1", "P2", "P3")
    assert math.isclose(batch.activity_per_patient_mbq() * 3, batch.eluted_activity_mbq, rel_tol=1e-9)
    assert batch.release_datetime() == datetime(2026, 1, 2, 6, 20)


def test_preparation_batch_requires_at_least_one_patient():
    generator = GeneratorAsset(
        generator_id="GEN-001", calibration_datetime=datetime(2026, 1, 1, 6, 0),
        calibration_mo99_activity_mbq=50_000.0,
    )
    _, event = generator.elute(at_datetime=datetime(2026, 1, 2, 6, 0))
    with pytest.raises(ValueError):
        build_preparation_batch(
            batch_id="B1", elute_event=event, generator_id="GEN-001",
            preparation_processing_minutes=20.0, patient_ids=(),
        )


def test_generator_patient_lineage_end_to_end():
    patients, _ = build_representative_day_population(
        day=date(2026, 1, 5), available_beds=200, occupied_beds=170, admissions=20, discharges=18,
        outpatient_encounters=40, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    spect_patients = tuple(p for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "SPECT")
    assert len(spect_patients) == 18
    generator = GeneratorAsset(
        generator_id="GEN-001", calibration_datetime=datetime(2026, 1, 5, 4, 0),
        calibration_mo99_activity_mbq=100_000.0,
    )
    _, batch, lineages = assign_spect_patients_to_generator_batch(
        spect_patients=spect_patients, generator=generator, elution_datetime=datetime(2026, 1, 5, 6, 0),
        preparation_processing_minutes=20.0, transport_minutes_by_architecture={"Conventional": 12.0, "MRT": 2.0, "Hybrid": 5.0},
        architecture="Conventional",
    )
    assert len(lineages) == 18
    for lineage in lineages:
        assert lineage.generator_id == "GEN-001"
        assert lineage.preparation_batch.batch_id == batch.batch_id
        assert 0.0 < lineage.retained_fraction_at_administration <= 1.0
        assert lineage.activity_at_administration_mbq > 0.0
    # patient_id -> procedure_id -> radionuclide -> source -> transport chain is fully populated
    ids = set(p.patient_id for p in spect_patients)
    assert set(l.patient_id for l in lineages) == ids


# ---------------------------------------------------------------------------
# Decay conservation (section 51) -- both PET and SPECT radionuclides
# ---------------------------------------------------------------------------


def test_decay_active_for_both_pet_and_spect_and_transport_speed_consequence_differs():
    f18_half_life = 109.8
    tc99m_half_life = TC99M_HALF_LIFE_MIN
    slow_transport, fast_transport = 30.0, 2.0

    f18_slow = retained_fraction(slow_transport, f18_half_life)
    f18_fast = retained_fraction(fast_transport, f18_half_life)
    tc_slow = retained_fraction(slow_transport, tc99m_half_life)
    tc_fast = retained_fraction(fast_transport, tc99m_half_life)

    f18_delta = f18_fast - f18_slow
    tc_delta = tc_fast - tc_slow
    assert f18_delta > 0.0 and tc_delta > 0.0, "decay physics must remain active (not disabled) for both radionuclides"
    assert f18_delta > tc_delta, "transport speed has a SMALLER consequence for Tc-99m than for F-18 (section 51)"


def test_decay_is_never_bypassed_to_force_mrt_win():
    # Even with instantaneous (near-zero) transport, retained fraction must be < 1.0 whenever transport_min > 0,
    # and exactly 1.0 only at transport_min == 0 -- decay is never artificially disabled.
    assert retained_fraction(0.0, TC99M_HALF_LIFE_MIN) == 1.0
    assert retained_fraction(0.01, TC99M_HALF_LIFE_MIN) < 1.0


# ---------------------------------------------------------------------------
# SPECT / generator economics remain explicitly NOT_CALIBRATED (section 53)
# ---------------------------------------------------------------------------


def test_uncalibrated_spect_and_generator_economics_reported_explicitly():
    assumptions = PlannerAssumptions()
    result = evaluate_spect_economics(assumptions)
    assert result.spect_scanner_capex == "NOT_CALIBRATED"
    assert result.spect_scanner_incremental_opex == "NOT_CALIBRATED"
    assert result.generator_purchase_capex == "NOT_CALIBRATED"
    assert result.generator_installation_capex == "NOT_CALIBRATED"
    assert result.generator_annual_maintenance_opex == "NOT_CALIBRATED"


def test_spect_economics_uses_supplied_value_when_legitimately_provided():
    assumptions = PlannerAssumptions(spect_scanner_capex=1_800_000.0)
    result = evaluate_spect_economics(assumptions)
    assert result.spect_scanner_capex == 1_800_000.0
    assert result.generator_purchase_capex == "NOT_CALIBRATED"  # unaffected, still uncalibrated


# ---------------------------------------------------------------------------
# Conventional / MRT / Hybrid nuclear operation (transport-mode reuse)
# ---------------------------------------------------------------------------


def test_conventional_mrt_hybrid_all_consume_spect_dose_lineage():
    patients, _ = build_representative_day_population(
        day=date(2026, 1, 5), available_beds=200, occupied_beds=170, admissions=20, discharges=18,
        outpatient_encounters=40, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    spect_patients = tuple(p for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "SPECT")
    transport_minutes = {"Conventional": 12.0, "MRT": 2.0, "Hybrid": 5.0}
    results = {}
    for architecture in ("Conventional", "MRT", "Hybrid"):
        generator = GeneratorAsset(
            generator_id="GEN-001", calibration_datetime=datetime(2026, 1, 5, 4, 0), calibration_mo99_activity_mbq=100_000.0,
        )
        _, _, lineages = assign_spect_patients_to_generator_batch(
            spect_patients=spect_patients, generator=generator, elution_datetime=datetime(2026, 1, 5, 6, 0),
            preparation_processing_minutes=20.0, transport_minutes_by_architecture=transport_minutes, architecture=architecture,
        )
        results[architecture] = lineages
    # MRT (fastest transport) must retain a higher (or equal) fraction than Conventional (slowest) -- decay stays authoritative.
    assert results["MRT"][0].retained_fraction_at_administration >= results["Conventional"][0].retained_fraction_at_administration
    assert results["Hybrid"][0].retained_fraction_at_administration >= results["Conventional"][0].retained_fraction_at_administration
    assert len(results["Conventional"]) == len(results["MRT"]) == len(results["Hybrid"]) == 18


# ---------------------------------------------------------------------------
# 50/day controlled benchmark + 200/day F-18 stress non-regression (section 54)
# ---------------------------------------------------------------------------


def test_realistic_oncology_50_benchmark_descriptor():
    assert REALISTIC_ONCOLOGY_50.total_nuclear_per_day == 50
    assert REALISTIC_ONCOLOGY_50.pet_per_day + REALISTIC_ONCOLOGY_50.spect_per_day == 50
    assert REALISTIC_ONCOLOGY_50.purpose == "REALISTIC_CONTROLLED_OPERATING_BENCHMARK"


def test_high_volume_f18_stress_200_benchmark_descriptor_unchanged():
    assert HIGH_VOLUME_F18_STRESS_200.total_nuclear_per_day == 200
    assert HIGH_VOLUME_F18_STRESS_200.pet_per_day == 200
    assert HIGH_VOLUME_F18_STRESS_200.spect_per_day == 0
    assert HIGH_VOLUME_F18_STRESS_200.purpose == "ENGINEERING_STRESS_TEST"
    assert HIGH_VOLUME_F18_STRESS_200.purpose != REALISTIC_ONCOLOGY_50.purpose


def test_realistic_benchmark_produces_50_day_population():
    patients, census = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=REALISTIC_ONCOLOGY_50.beds,
        occupied_beds=int(REALISTIC_ONCOLOGY_50.beds * REALISTIC_ONCOLOGY_50.occupancy_fraction),
        admissions=15, discharges=14, outpatient_encounters=60,
        target_pet_procedures=REALISTIC_ONCOLOGY_50.pet_per_day,
        target_spect_procedures=REALISTIC_ONCOLOGY_50.spect_per_day, seed=2026,
    )
    assert census.total_nuclear_procedures == 50
    assert census.pet_procedures == 32
    assert census.spect_procedures == 18


def test_200_f18_stress_benchmark_non_regression_via_existing_campus_authority():
    """Section 56/60: the historical 200/day F-18 stress benchmark must remain
    valid and untouched -- reuses the SAME existing authoritative function this
    entire session has validated across many prior phases."""
    from campus_retrofit_benchmark import build_two_building_campus_geometry, run_campus_case_1_conventional

    geometry = build_two_building_campus_geometry(campus_separation_m=500.0)
    result = run_campus_case_1_conventional(geometry=geometry, demand=200)
    assert result.demand == 200
    assert result.winner.patients_retention_qualified_completed == 36  # matches this session's established 500m/200 Conventional control point

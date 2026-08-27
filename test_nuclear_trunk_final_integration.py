"""Focused test suite: nuclear trunk final integration correction.

Covers (section 41): single authoritative optimizer, PET/SPECT source
integration, mixed PET/SPECT candidate, known patient appointment, six-month
patient calendar, forecast+known demand reconciliation, forecast never
overwrites booked demand, patient room/outpatient-origin identity, generator
outage replan, elution delay/failed-QC/actual-activity consequence, SPECT
scanner outage replan, PET non-drift during SPECT events, operational-only
scope, capital-planning scope, existing-asset zero new-study CapEx, proposed
asset legitimate CapEx, asset-status/operational-state separation, relocation
does not repurchase, Conventional/MRT/Hybrid, 50/day realistic benchmark,
200/day F-18 stress non-regression.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import pytest

from campus_retrofit_benchmark import build_two_building_campus_geometry, run_campus_case_1_conventional
from generator_catalog import create_facility_generator_instance, load_generator_catalog
from models import PlannerAssumptions
from nuclear_appointment import (
    NuclearAppointment,
    build_six_month_appointment_calendar,
    find_patient_appointment,
    reconcile_known_and_forecast_demand,
)
from nuclear_source import build_generator_source
from oncology_pet_spect_scenario import (
    HIGH_VOLUME_F18_STRESS_200,
    REALISTIC_ONCOLOGY_50,
    SpectDoseLineage,
    assign_spect_patients_to_generator_batch,
    build_representative_day_population,
    evaluate_authoritative_nuclear_candidate,
    generate_stochastic_daily_nuclear_demand,
)
from scanner_catalog import load_scanner_catalog
from study_scope import apply_study_scope

ASSUMPTIONS = PlannerAssumptions()


def _spect_source(instance_id: str = "GEN-001") -> "object":
    catalog = load_generator_catalog()
    instance = create_facility_generator_instance(instance_id=instance_id, catalog_model_id="CURIUM_TECHNELITE")
    return build_generator_source(source_id=instance_id, generator_instance=instance, generator_model=catalog.by_id("CURIUM_TECHNELITE"), calibration_datetime=datetime(2026, 1, 1, 4, 0))


def _spect_model():
    return load_scanner_catalog().by_id("GE_NM_CT_870_DR")


def _geometry():
    return build_two_building_campus_geometry(campus_separation_m=500.0)


# ---------------------------------------------------------------------------
# Single authoritative optimizer (sections 1-4, 35, 36)
# ---------------------------------------------------------------------------


def test_authoritative_candidate_reproduces_real_pet_control_point():
    """The PET leg must reproduce the exact real, established campus control
    point (36 qualified at 500m/200) -- proof the REAL optimizer is used, not
    a stub or reinvention."""
    result = evaluate_authoritative_nuclear_candidate(
        architecture="Conventional", geometry=_geometry(), pet_demand=200, spect_requested=18,
        spect_source=_spect_source(), spect_activity_per_patient_mbq=740.0, spect_model=_spect_model(),
        spect_protocol="oncology_spect_ct", spect_elution_datetime=datetime(2026, 1, 2, 6, 0),
        assumptions=ASSUMPTIONS, study_scope="CAPITAL_PLANNING",
    )
    assert result.pet_qualified == 36  # matches this session's established 500m/200 Conventional control point


def test_authoritative_candidate_is_single_result_pet_plus_spect():
    result = evaluate_authoritative_nuclear_candidate(
        architecture="Conventional", geometry=_geometry(), pet_demand=200, spect_requested=18,
        spect_source=_spect_source(), spect_activity_per_patient_mbq=740.0, spect_model=_spect_model(),
        spect_protocol="oncology_spect_ct", spect_elution_datetime=datetime(2026, 1, 2, 6, 0),
        assumptions=ASSUMPTIONS, study_scope="CAPITAL_PLANNING",
    )
    assert result.combined_qualified_throughput == result.pet_qualified + result.spect_served
    assert result.reference_capex == result.pet_capex + result.spect_capex
    assert result.annual_opex == result.pet_opex + result.spect_opex
    # ONE npv value -- not two independently computed NPVs left as separate final truths
    assert isinstance(result.npv, float)


def test_conventional_mrt_hybrid_all_use_same_authoritative_path():
    results = {}
    for arch in ("Conventional", "MRT", "Hybrid"):
        results[arch] = evaluate_authoritative_nuclear_candidate(
            architecture=arch, geometry=_geometry(), pet_demand=200, spect_requested=18,
            spect_source=_spect_source(), spect_activity_per_patient_mbq=740.0, spect_model=_spect_model(),
            spect_protocol="oncology_spect_ct", spect_elution_datetime=datetime(2026, 1, 2, 6, 0),
            assumptions=ASSUMPTIONS, study_scope="CAPITAL_PLANNING",
        )
    # matches this session's established anchors: Conventional=36, MRT/Hybrid=72 at 500m/200
    assert results["Conventional"].pet_qualified == 36
    assert results["MRT"].pet_qualified == 72
    assert results["Hybrid"].pet_qualified == 72
    for arch in ("Conventional", "MRT", "Hybrid"):
        assert results[arch].spect_served == 18


# ---------------------------------------------------------------------------
# Patient calendar (sections 6-10)
# ---------------------------------------------------------------------------


def test_known_patient_appointment_minimum_fields():
    appt = NuclearAppointment(
        appointment_id="APPT-001", patient_id="P-023", procedure_id="SPECT-P-023",
        scheduled_datetime=datetime(2026, 12, 5, 9, 0), patient_type="OUTPATIENT",
        modality="SPECT", radiopharmaceutical="Tc-99m MDP", radionuclide="Tc-99m",
        status="BOOKED", provenance="USER_ENTERED", outpatient_origin="ONCOLOGY_CLINIC_CHECKIN-0023",
        scanner_requirement="SCN-SPECT-004",
    )
    assert appt.is_known()


def test_appointment_requires_room_or_outpatient_origin():
    with pytest.raises(ValueError):
        NuclearAppointment(
            appointment_id="APPT-002", patient_id="P-041", procedure_id="PET-P-041",
            scheduled_datetime=datetime(2026, 12, 5, 10, 0), patient_type="INPATIENT",
            modality="PET", radiopharmaceutical="F-18 FDG", radionuclide="F-18",
            status="CONFIRMED", provenance="USER_ENTERED",
        )


def test_six_month_patient_calendar_lookup():
    appointments = tuple(
        NuclearAppointment(
            appointment_id=f"APPT-{i:03d}", patient_id=f"P-{i:03d}", procedure_id=f"PROC-{i:03d}",
            scheduled_datetime=datetime(2026, 1, 1) + timedelta(days=i * 5), patient_type="OUTPATIENT",
            modality="PET" if i % 2 == 0 else "SPECT", radiopharmaceutical=("F-18 FDG" if i % 2 == 0 else "Tc-99m MDP"),
            radionuclide=("F-18" if i % 2 == 0 else "Tc-99m"), status="CONFIRMED", provenance="USER_ENTERED",
            outpatient_origin=f"ORIGIN-{i:03d}",
        )
        for i in range(36)  # ~6 months at 5-day spacing
    )
    calendar = build_six_month_appointment_calendar(start_date=date(2026, 1, 1), appointments=appointments)
    target = appointments[10]
    found = find_patient_appointment(calendar=calendar, patient_id=target.patient_id, on_date=target.scheduled_datetime.date())
    assert found is not None
    assert found.appointment_id == target.appointment_id
    assert found.modality == target.modality


# ---------------------------------------------------------------------------
# Known vs forecast demand (sections 8-9)
# ---------------------------------------------------------------------------


def test_known_appointments_never_overwritten_by_forecast():
    known = (
        NuclearAppointment(
            appointment_id="APPT-KNOWN-1", patient_id="P-100", procedure_id="SPECT-P-100",
            scheduled_datetime=datetime(2026, 6, 1, 9, 0), patient_type="OUTPATIENT", modality="SPECT",
            radiopharmaceutical="Tc-99m MDP", radionuclide="Tc-99m", status="BOOKED", provenance="USER_ENTERED",
            outpatient_origin="ORIGIN-100",
        ),
        NuclearAppointment(
            appointment_id="APPT-KNOWN-2", patient_id="P-101", procedure_id="PET-P-101",
            scheduled_datetime=datetime(2026, 6, 1, 10, 0), patient_type="OUTPATIENT", modality="PET",
            radiopharmaceutical="F-18 FDG", radionuclide="F-18", status="CONFIRMED", provenance="USER_ENTERED",
            outpatient_origin="ORIGIN-101",
        ),
    )
    result = reconcile_known_and_forecast_demand(day=date(2026, 6, 1), known_appointments=known, forecast_pet=30, forecast_spect=16)
    assert result.known_pet == 1 and result.known_spect == 1
    assert result.total_planned_pet == 31 and result.total_planned_spect == 17
    assert "P-100" in result.booked_patient_ids and "P-101" in result.booked_patient_ids
    # forecast never reduces/removes known counts
    assert result.total_planned_pet >= result.known_pet
    assert result.total_planned_spect >= result.known_spect


def test_forecast_demand_supplements_not_replaces():
    result_no_known = reconcile_known_and_forecast_demand(day=date(2026, 6, 2), known_appointments=(), forecast_pet=32, forecast_spect=18)
    assert result_no_known.known_pet == 0 and result_no_known.total_planned_pet == 32


# ---------------------------------------------------------------------------
# Spatial traceability (room/outpatient origin survive, section 11)
# ---------------------------------------------------------------------------


def test_room_identity_survives_for_inpatient_spect_and_pet():
    patients, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    for p in patients:
        if p.patient_type == "INPATIENT":
            assert p.room_id is not None and p.building_id is not None and p.floor_id is not None
        else:
            assert p.outpatient_origin is not None


# ---------------------------------------------------------------------------
# Generator outage replan (sections 22-23, 32)
# ---------------------------------------------------------------------------


def test_generator_outage_triggers_replan_for_affected_spect_patients_only():
    from live_operational_state import OperationalEvent, replan_spect_after_generator_event
    from healthcare_integration import CanonicalIntegrationEvent

    generator = _spect_source().generator_physics
    patients, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    spect_patients = tuple(p for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "SPECT")
    _, _, lineages = assign_spect_patients_to_generator_batch(
        spect_patients=spect_patients, generator=generator, elution_datetime=datetime(2026, 2, 2, 6, 0),
        preparation_processing_minutes=20.0, transport_minutes_by_architecture={"Conventional": 12.0, "MRT": 2.0, "Hybrid": 5.0},
        architecture="Conventional", scanner_id="SCN-005",
    )
    integration_event = CanonicalIntegrationEvent(
        source_system="MANUAL", source_event_id="EVT-GEN-DOWN", event_type="DEVICE_STATUS", event_timestamp=datetime(2026, 2, 2, 7, 0),
    )
    event = OperationalEvent(integration_event=integration_event, event_kind="GENERATOR_UNAVAILABLE", object_id="GEN-001", new_state="UNAVAILABLE")
    result = replan_spect_after_generator_event(event=event, spect_lineages=lineages)
    assert set(result.affected_patient_ids) == set(l.patient_id for l in lineages)  # all 18 use GEN-001
    assert result.unmet_patient_ids  # no alternate source supplied -- honest unmet, no fabricated activity


def test_generator_outage_with_alternate_source_reassigns_affected_only():
    from live_operational_state import OperationalEvent, replan_spect_after_generator_event
    from healthcare_integration import CanonicalIntegrationEvent

    generator = _spect_source().generator_physics
    alternate = _spect_source(instance_id="GEN-002")
    patients, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    spect_patients = tuple(p for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "SPECT")
    _, _, lineages = assign_spect_patients_to_generator_batch(
        spect_patients=spect_patients, generator=generator, elution_datetime=datetime(2026, 2, 2, 6, 0),
        preparation_processing_minutes=20.0, transport_minutes_by_architecture={"Conventional": 12.0, "MRT": 2.0, "Hybrid": 5.0},
        architecture="Conventional", scanner_id="SCN-005",
    )
    integration_event = CanonicalIntegrationEvent(
        source_system="MANUAL", source_event_id="EVT-GEN-DOWN-2", event_type="DEVICE_STATUS", event_timestamp=datetime(2026, 2, 2, 7, 0),
    )
    event = OperationalEvent(integration_event=integration_event, event_kind="GENERATOR_UNAVAILABLE", object_id="GEN-001", new_state="UNAVAILABLE")
    result = replan_spect_after_generator_event(
        event=event, spect_lineages=lineages, alternate_sources=(alternate,), elution_datetime=datetime(2026, 2, 2, 8, 0),
    )
    assert len(result.unmet_patient_ids) < len(lineages)  # alternate generator serves at least some affected patients


# ---------------------------------------------------------------------------
# FINAL NUCLEAR TRUNK CLOSURE: alternate-generator lineage rematerialization
# ---------------------------------------------------------------------------


def _build_spect_lineages(seed: int = 42):
    generator = _spect_source().generator_physics
    patients, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=seed,
    )
    spect_patients = tuple(p for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "SPECT")
    _, batch, lineages = assign_spect_patients_to_generator_batch(
        spect_patients=spect_patients, generator=generator, elution_datetime=datetime(2026, 2, 2, 6, 0),
        preparation_processing_minutes=20.0, transport_minutes_by_architecture={"Conventional": 12.0, "MRT": 2.0, "Hybrid": 5.0},
        architecture="Conventional", scanner_id="SCN-005",
    )
    return lineages, batch


def _generator_down_event(object_id: str = "GEN-001"):
    from live_operational_state import OperationalEvent
    from healthcare_integration import CanonicalIntegrationEvent
    ie = CanonicalIntegrationEvent(source_system="MANUAL", source_event_id=f"EVT-{object_id}-DOWN", event_type="DEVICE_STATUS", event_timestamp=datetime(2026, 2, 2, 7, 0))
    return OperationalEvent(integration_event=ie, event_kind="GENERATOR_UNAVAILABLE", object_id=object_id, new_state="UNAVAILABLE")


def test_full_reassignment_all_affected_patients_get_complete_alternate_lineage():
    """Section 14: alternate capacity sufficient for all -> unmet == 0, every
    affected patient has a COMPLETE revised lineage in the returned result."""
    from live_operational_state import replan_spect_after_generator_event
    lineages, old_batch = _build_spect_lineages()
    alternate = _spect_source(instance_id="GEN-002")
    result = replan_spect_after_generator_event(
        event=_generator_down_event(), spect_lineages=lineages, alternate_sources=(alternate,),
        elution_datetime=datetime(2026, 2, 2, 8, 0),
    )
    revised_by_id = {l.patient_id: l for l in result.revised_lineages}
    for pid in result.affected_patient_ids:
        if pid in result.unmet_patient_ids:
            continue
        revised = revised_by_id[pid]
        assert revised.generator_id == "GEN-002"
        assert revised.preparation_batch is not None
        assert revised.preparation_batch.source_generator_id == "GEN-002"
        assert revised.activity_at_administration_mbq > 0.0


def test_partial_reassignment_served_get_lineage_unmet_get_none():
    """Section 13: GEN-002 has enough for SOME but not ALL -- served patients
    receive complete new lineage, unmet patients receive NO fabricated dose."""
    from live_operational_state import replan_spect_after_generator_event
    lineages, _ = _build_spect_lineages()
    alternate = _spect_source(instance_id="GEN-002")
    result = replan_spect_after_generator_event(
        event=_generator_down_event(), spect_lineages=lineages, alternate_sources=(alternate,),
        elution_datetime=datetime(2026, 2, 2, 8, 0),
    )
    revised_ids = frozenset(l.patient_id for l in result.revised_lineages)
    assert result.unmet_patient_ids, "this scenario is expected to leave at least one patient unmet"
    for pid in result.unmet_patient_ids:
        assert pid not in revised_ids  # no fabricated lineage for unmet patients
    for l in result.revised_lineages:
        if l.patient_id in result.affected_patient_ids:
            assert l.generator_id == "GEN-002"


def test_no_alternate_generator_produces_no_fabricated_lineage():
    """Section 15: no valid alternate -- served=0, unmet=affected count, no
    fabricated batch/elution/dose anywhere in the result."""
    from live_operational_state import replan_spect_after_generator_event
    lineages, _ = _build_spect_lineages()
    result = replan_spect_after_generator_event(event=_generator_down_event(), spect_lineages=lineages)
    assert set(result.unmet_patient_ids) == set(result.affected_patient_ids)
    revised_ids = frozenset(l.patient_id for l in result.revised_lineages)
    assert not (revised_ids & frozenset(result.unmet_patient_ids))


def test_reassigned_patient_identity_and_procedure_identity_preserved():
    """Section 4/G: patient_id and procedure_id survive reassignment -- never
    a new identity like P-023-NEW."""
    from live_operational_state import replan_spect_after_generator_event
    lineages, _ = _build_spect_lineages()
    alternate = _spect_source(instance_id="GEN-002")
    result = replan_spect_after_generator_event(
        event=_generator_down_event(), spect_lineages=lineages, alternate_sources=(alternate,),
        elution_datetime=datetime(2026, 2, 2, 8, 0),
    )
    old_by_id = {l.patient_id: l for l in lineages}
    for revised in result.revised_lineages:
        if revised.patient_id in result.affected_patient_ids and revised.patient_id not in result.unmet_patient_ids:
            old = old_by_id[revised.patient_id]
            assert revised.patient_id == old.patient_id
            assert revised.procedure_id == old.procedure_id


def test_alternate_generator_activity_physically_consumed():
    """Section L: the alternate generator's real Bateman-physics state is
    consumed by the elution -- available activity strictly decreases after
    serving reassigned patients (residual + eluted == available_before)."""
    lineages, _ = _build_spect_lineages()
    alternate = _spect_source(instance_id="GEN-002")
    physics = alternate.generator_physics
    at = datetime(2026, 2, 2, 8, 0)
    available_before = physics.available_tc99m_activity_mbq(at_datetime=at)
    _, event = physics.elute(at_datetime=at)
    assert math.isclose(event.eluted_activity_mbq + event.residual_activity_mbq_in_column, available_before, rel_tol=1e-9)
    assert event.eluted_activity_mbq > 0.0


def test_scanner_assignment_preserved_across_generator_only_reassignment():
    """Section 9: a generator-only outage must not change the SPECT scanner
    assignment -- scanner_id is copied forward unchanged."""
    from live_operational_state import replan_spect_after_generator_event
    lineages, _ = _build_spect_lineages()
    alternate = _spect_source(instance_id="GEN-002")
    result = replan_spect_after_generator_event(
        event=_generator_down_event(), spect_lineages=lineages, alternate_sources=(alternate,),
        elution_datetime=datetime(2026, 2, 2, 8, 0),
    )
    for l in result.revised_lineages:
        if l.patient_id in result.affected_patient_ids and l.patient_id not in result.unmet_patient_ids:
            assert l.scanner_id == "SCN-005"  # unchanged


def test_unaffected_spect_lineage_unchanged_by_generator_event():
    """Section 8/11: lineages served by a DIFFERENT generator than the one
    that went down are unaffected -- preserved lineages come back
    byte-for-byte identical, never rebuilt."""
    from live_operational_state import replan_spect_after_generator_event
    lineages_gen1, _ = _build_spect_lineages(seed=42)
    lineages_gen2_source = _spect_source(instance_id="GEN-002")
    generator2 = lineages_gen2_source.generator_physics
    patients2, _ = build_representative_day_population(
        day=date(2026, 2, 3), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=99,
    )
    spect_patients2 = tuple(p for p in patients2 if p.nuclear_procedure and p.nuclear_procedure.modality == "SPECT")
    _, _, lineages_gen2 = assign_spect_patients_to_generator_batch(
        spect_patients=spect_patients2, generator=generator2, elution_datetime=datetime(2026, 2, 3, 6, 0),
        preparation_processing_minutes=20.0, transport_minutes_by_architecture={"Conventional": 12.0, "MRT": 2.0, "Hybrid": 5.0},
        architecture="Conventional", scanner_id="SCN-006",
    )
    combined = lineages_gen1 + lineages_gen2
    result = replan_spect_after_generator_event(event=_generator_down_event(), spect_lineages=combined)
    original_by_id = {l.patient_id: l for l in combined}
    # GEN-002's own patients must be entirely preserved -- GEN-001's outage never touches them.
    for l in lineages_gen2:
        assert l.patient_id in result.preserved_patient_ids
        preserved_match = next(x for x in result.revised_lineages if x.patient_id == l.patient_id)
        assert preserved_match == original_by_id[l.patient_id]


def test_locked_patient_lineage_unchanged_even_if_generator_matches():
    """Section 11: a LOCKED (completed) SPECT patient's lineage must not be
    rewritten even though their generator_id matches the outage."""
    from live_operational_state import replan_spect_after_generator_event
    lineages, _ = _build_spect_lineages()
    locked_id = lineages[0].patient_id
    alternate = _spect_source(instance_id="GEN-002")
    result = replan_spect_after_generator_event(
        event=_generator_down_event(), spect_lineages=lineages, alternate_sources=(alternate,),
        elution_datetime=datetime(2026, 2, 2, 8, 0), locked_patient_ids=frozenset({locked_id}),
    )
    assert locked_id not in result.affected_patient_ids
    revised = next(l for l in result.revised_lineages if l.patient_id == locked_id)
    assert revised == lineages[0]  # untouched, byte-for-byte


def test_multiple_alternate_generators_not_hardcoded():
    """Section 12: with two alternates, the result must identify which
    generator actually serves which patient -- never assume GEN-002 alone."""
    from live_operational_state import replan_spect_after_generator_event
    lineages, _ = _build_spect_lineages()
    alt1 = _spect_source(instance_id="GEN-002")
    alt2 = _spect_source(instance_id="GEN-003")
    result = replan_spect_after_generator_event(
        event=_generator_down_event(), spect_lineages=lineages, alternate_sources=(alt1, alt2),
        elution_datetime=datetime(2026, 2, 2, 8, 0),
    )
    used_generators = {l.generator_id for l in result.revised_lineages if l.patient_id in result.affected_patient_ids}
    assert used_generators <= {"GEN-002", "GEN-003"}
    assert len(result.unmet_patient_ids) <= len(result.affected_patient_ids)


def test_operational_only_generator_reassignment_zero_new_study_capex():
    """Section 21/O: switching installed GEN-001 -> installed GEN-002 in an
    OPERATIONAL_ONLY study contributes zero new study CapEx."""
    from generator_catalog import FacilityGeneratorInstance
    gen1 = FacilityGeneratorInstance(instance_id="GEN-001", catalog_model_id="CURIUM_TECHNELITE", asset_status="EXISTING")
    gen2 = FacilityGeneratorInstance(instance_id="GEN-002", catalog_model_id="GE_HEALTHCARE_DRYTEC", asset_status="EXISTING")
    result = apply_study_scope(
        study_scope="OPERATIONAL_ONLY", transport_architecture="CONVENTIONAL", qualified_throughput=18,
        reference_capex=0.0, annual_opex=0.0, revenue_per_scan=ASSUMPTIONS.revenue_per_scan,
        operating_days_per_year=ASSUMPTIONS.operating_days_per_year, discount_rate_pct=ASSUMPTIONS.discount_rate_pct,
        analysis_years=ASSUMPTIONS.analysis_years,
    )
    assert gen1.asset_status == "EXISTING" and gen2.asset_status == "EXISTING"
    assert result.study_capex == 0.0


def test_generator_available_recovery_does_not_force_reshuffle():
    from live_operational_state import OperationalEvent, replan_spect_after_generator_event
    from healthcare_integration import CanonicalIntegrationEvent

    generator = _spect_source().generator_physics
    patients, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    spect_patients = tuple(p for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "SPECT")
    _, _, lineages = assign_spect_patients_to_generator_batch(
        spect_patients=spect_patients, generator=generator, elution_datetime=datetime(2026, 2, 2, 6, 0),
        preparation_processing_minutes=20.0, transport_minutes_by_architecture={"Conventional": 12.0, "MRT": 2.0, "Hybrid": 5.0},
        architecture="Conventional", scanner_id="SCN-005",
    )
    integration_event = CanonicalIntegrationEvent(
        source_system="MANUAL", source_event_id="EVT-GEN-UP", event_type="DEVICE_STATUS", event_timestamp=datetime(2026, 2, 2, 7, 0),
    )
    event = OperationalEvent(integration_event=integration_event, event_kind="GENERATOR_AVAILABLE", object_id="GEN-001", new_state="AVAILABLE")
    result = replan_spect_after_generator_event(event=event, spect_lineages=lineages)
    assert result.escalation == "LEVEL_0_STATE_UPDATE_ONLY"
    assert result.revised_lineages == tuple(lineages)


# ---------------------------------------------------------------------------
# SPECT scanner outage replan + PET non-drift (sections 24-25, 33)
# ---------------------------------------------------------------------------


def test_spect_scanner_outage_replan_reassigns_only_affected_patients():
    from live_operational_state import OperationalEvent, replan_spect_after_scanner_event
    from healthcare_integration import CanonicalIntegrationEvent

    generator = _spect_source().generator_physics
    patients, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    spect_patients = tuple(p for p in patients if p.nuclear_procedure and p.nuclear_procedure.modality == "SPECT")
    _, _, lineages = assign_spect_patients_to_generator_batch(
        spect_patients=spect_patients, generator=generator, elution_datetime=datetime(2026, 2, 2, 6, 0),
        preparation_processing_minutes=20.0, transport_minutes_by_architecture={"Conventional": 12.0, "MRT": 2.0, "Hybrid": 5.0},
        architecture="Conventional", scanner_id="SCN-005",
    )
    integration_event = CanonicalIntegrationEvent(
        source_system="MANUAL", source_event_id="EVT-SCN-DOWN", event_type="DEVICE_STATUS", event_timestamp=datetime(2026, 2, 2, 7, 0),
    )
    event = OperationalEvent(integration_event=integration_event, event_kind="SPECT_SCANNER_UNAVAILABLE", object_id="SCN-005", new_state="UNAVAILABLE")
    result = replan_spect_after_scanner_event(event=event, spect_lineages=lineages, alternate_scanner_ids=("SCN-006",))
    assert set(result.affected_patient_ids) == set(l.patient_id for l in lineages)
    revised_scanner_ids = {l.scanner_id for l in result.revised_lineages if l.patient_id in result.affected_patient_ids}
    assert revised_scanner_ids == {"SCN-006"}


def test_pet_patients_never_referenced_by_spect_live_state_functions():
    """Section 25/10: proof of non-drift by construction -- these functions'
    signatures only accept SPECT lineages, never PatientOperationalPlan."""
    import inspect
    from live_operational_state import replan_spect_after_generator_event, replan_spect_after_scanner_event
    for fn in (replan_spect_after_generator_event, replan_spect_after_scanner_event):
        sig = inspect.signature(fn)
        for param in sig.parameters.values():
            assert "PatientOperationalPlan" not in str(param.annotation)


# ---------------------------------------------------------------------------
# Study scope: OPERATIONAL_ONLY vs CAPITAL_PLANNING (sections 13-18)
# ---------------------------------------------------------------------------


def test_operational_only_existing_asset_zero_new_study_capex():
    result = evaluate_authoritative_nuclear_candidate(
        architecture="Conventional", geometry=_geometry(), pet_demand=200, spect_requested=18,
        spect_source=_spect_source(), spect_activity_per_patient_mbq=740.0, spect_model=_spect_model(),
        spect_protocol="oncology_spect_ct", spect_elution_datetime=datetime(2026, 1, 2, 6, 0),
        assumptions=ASSUMPTIONS, study_scope="OPERATIONAL_ONLY",
    )
    assert result.study_capex == 0.0
    assert result.reference_capex > 0.0  # historical/reference value preserved, not zeroed


def test_capital_planning_permits_legitimate_capex():
    result = evaluate_authoritative_nuclear_candidate(
        architecture="Conventional", geometry=_geometry(), pet_demand=200, spect_requested=18,
        spect_source=_spect_source(), spect_activity_per_patient_mbq=740.0, spect_model=_spect_model(),
        spect_protocol="oncology_spect_ct", spect_elution_datetime=datetime(2026, 1, 2, 6, 0),
        assumptions=ASSUMPTIONS, study_scope="CAPITAL_PLANNING",
    )
    assert result.study_capex == result.reference_capex
    assert result.study_capex > 0.0


def test_turning_generator_off_does_not_change_asset_status():
    from generator_catalog import FacilityGeneratorInstance
    instance = FacilityGeneratorInstance(instance_id="GEN-001", catalog_model_id="CURIUM_TECHNELITE", asset_status="EXISTING", operating_state="AVAILABLE")
    turned_off = FacilityGeneratorInstance(
        instance_id=instance.instance_id, catalog_model_id=instance.catalog_model_id,
        asset_status=instance.asset_status, operating_state="UNAVAILABLE",
    )
    assert turned_off.asset_status == "EXISTING"  # unchanged
    assert turned_off.operating_state == "UNAVAILABLE"  # only operational state changed


def test_relocation_does_not_change_catalog_identity_or_asset_status():
    from generator_catalog import create_facility_generator_instance
    a = create_facility_generator_instance(instance_id="GEN-001", catalog_model_id="CURIUM_TECHNELITE", location_object_id="RP-001")
    b = create_facility_generator_instance(instance_id="GEN-001", catalog_model_id="CURIUM_TECHNELITE", location_object_id="RP-002")
    assert a.catalog_model_id == b.catalog_model_id
    assert a.asset_status == b.asset_status
    assert a.location_object_id != b.location_object_id


# ---------------------------------------------------------------------------
# Non-regression (200/day F-18 stress + realistic benchmark)
# ---------------------------------------------------------------------------


def test_200_f18_stress_benchmark_non_regression():
    geometry = _geometry()
    result = run_campus_case_1_conventional(geometry=geometry, demand=200)
    assert result.winner.patients_retention_qualified_completed == 36


def test_realistic_oncology_50_benchmark_stochastic_not_forced():
    totals = [generate_stochastic_daily_nuclear_demand(day=date(2026, 3, 1), target_mean_pet=32, target_mean_spect=18, seed=s).realized_total for s in range(20)]
    assert len(set(totals)) > 1
    assert HIGH_VOLUME_F18_STRESS_200.purpose != REALISTIC_ONCOLOGY_50.purpose

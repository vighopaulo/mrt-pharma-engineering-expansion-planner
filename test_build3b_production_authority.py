"""Build 3B focused regression: cyclotron radionuclide / batch-production /
patient-demand authority invariants.

These tests LOCK the audit findings recorded in
CYCLOTRON_PRODUCTION_DATA_AUTHORITY_BUILD_3B.md so they cannot silently
regress. They assert authority BEHAVIOR against the physical repository
(catalog JSON + resolver + demand/batch/activity chain), never fabricated
values. No production code is modified by this build; these are additive,
read-only-style assertions.

Scope guard: this file does NOT connect four-architecture feasibility, does
NOT begin Part 3D, and does NOT modify the 6/6/12 benchmark -- it only verifies
the current physical state.
"""

from __future__ import annotations

import math

import cyclotron_catalog as cc
from cyclotron_production_windows import resolve_fleet_eob_capacity_mbq_per_day
from cycle_relative_production_requirement import (
    derive_cycle_relative_requirement,
    generate_candidate_production_cycles,
)
from multi_isotope_decay import required_upstream_activity, retained_fraction
from patient_radionuclide_demand import (
    FacilityDayPatientDemand,
    PatientRadionuclideDemand,
    RadionuclideBatchDemand,
    group_patients_by_radionuclide,
    partition_facility_day_patient_demand,
)


# ---------------------------------------------------------------------------
# 1. CYPRIS MP-30 CONTROL -- supported != calibrated != capacity
# ---------------------------------------------------------------------------


def test_cypris_mp30_f18_supported_but_production_not_calibrated():
    """Section 8 control: F-18 is declared supported, yet no cycle data and no
    performance records exist, so production is NOT_CALIBRATED and no schedulable
    radionuclide is derived."""
    model = cc.load_cyclotron_catalog().by_id("SUMITOMO_CYPRIS_MP_30")
    assert "F-18" in model.supported_radionuclides
    assert model.has_calibrated_radionuclide_capability is True  # SUPPORT flag only
    assert dict(model.production_cycle_minutes_by_radionuclide) == {}
    assert model.production_performance_records == ()
    assert model.schedulable_radionuclides == ()
    assert model.production_calibration_status == "not_calibrated"


def test_cypris_mp30_builds_no_fleet_and_emits_warning():
    """A CYPRIS MP-30 facility instance cannot form a schedulable asset:
    the fleet is None and a calibration warning is emitted."""
    catalog = cc.load_cyclotron_catalog()
    instance = cc.create_facility_cyclotron_instance(
        catalog_model_id="SUMITOMO_CYPRIS_MP_30", existing_instances=()
    )
    fleet, warnings = cc.build_fleet_from_instances(catalog=catalog, instances=(instance,))
    assert fleet is None
    assert any("does not have calibrated radionuclide and cycle data" in w for w in warnings)


def test_cypris_mp30_never_infers_capacity_from_energy_or_current():
    """No numeric F-18 capacity may be synthesized from MeV/beam-current class."""
    model = cc.load_cyclotron_catalog().by_id("SUMITOMO_CYPRIS_MP_30")
    for record in model.production_performance_records:
        assert record.normalized_eob_activity_mbq is None


# ---------------------------------------------------------------------------
# 2. POSITIVE PRODUCTION CONTROL -- calibrated F-18 resolves real capacity
# ---------------------------------------------------------------------------


def test_pettrace_840_positive_control_calibrated_and_resolves():
    """Section 9 positive control: PETtrace 840 has a manufacturer-calibrated
    F-18 EOB reference point (240 GBq @ 120 min, 60 uA) and resolves a
    schedule-derived daily capacity that scales linearly with windows/day."""
    catalog = cc.load_cyclotron_catalog()
    model = catalog.by_id("GE_PETTRACE_840")
    assert model.production_calibration_status == "manufacturer_calibrated"
    assert model.schedulable_radionuclides == ("F-18",)
    (record,) = model.production_performance_records
    assert record.radionuclide == "F-18"
    assert record.normalized_eob_activity_mbq == 240000.0
    assert record.irradiation_time_minutes == 120.0
    assert record.calibration_status == "manufacturer_calibrated"

    instance = cc.create_facility_cyclotron_instance(
        catalog_model_id="GE_PETTRACE_840", existing_instances=()
    )
    fleet, warnings = cc.build_fleet_from_instances(catalog=catalog, instances=(instance,))
    assert fleet is not None
    assert warnings == ()

    cap1, status1 = resolve_fleet_eob_capacity_mbq_per_day(
        fleet=fleet, radionuclide="F-18", production_batches_per_day=1
    )
    cap2, status2 = resolve_fleet_eob_capacity_mbq_per_day(
        fleet=fleet, radionuclide="F-18", production_batches_per_day=2
    )
    assert cap1 == 240000.0
    assert cap2 == 480000.0
    assert status1 == "schedule_derived_capacity"
    assert status2 == "schedule_derived_capacity"


def test_gbq_to_mbq_normalization_is_1000x():
    """Unit normalization must convert GBq->MBq by x1000 (not silently pass through)."""
    catalog = cc.load_cyclotron_catalog()
    model = catalog.by_id("GE_PETTRACE_890")
    (record,) = model.production_performance_records
    assert record.reported_eob_activity == 648.0
    assert record.reported_eob_activity_unit == "GBq"
    assert record.normalized_eob_activity_mbq == 648000.0


# ---------------------------------------------------------------------------
# 3. CATALOG-WIDE INVARIANTS -- no non-F-18 calibrated production anywhere
# ---------------------------------------------------------------------------


def test_no_non_f18_radionuclide_has_calibrated_eob_anywhere():
    """Audit invariant: F-18 is the ONLY radionuclide with any calibrated EOB
    record in the entire catalog. If a future edit adds a non-F-18 calibrated
    point, this test should be updated deliberately -- never silently."""
    catalog = cc.load_cyclotron_catalog()
    for model in catalog.models:
        for record in model.production_performance_records:
            if record.normalized_eob_activity_mbq is not None:
                assert record.radionuclide == "F-18", (
                    f"Unexpected calibrated non-F-18 EOB on {model.catalog_model_id}: "
                    f"{record.radionuclide}"
                )


def test_calibrated_f18_model_set_is_exactly_the_six_known_models():
    """Exactly six models expose a manufacturer-calibrated F-18 EOB point."""
    catalog = cc.load_cyclotron_catalog()
    calibrated = {
        model.catalog_model_id
        for model in catalog.models
        if any(
            r.radionuclide == "F-18"
            and r.calibration_status == "manufacturer_calibrated"
            and r.normalized_eob_activity_mbq is not None
            for r in model.production_performance_records
        )
    }
    assert calibrated == {
        "GE_PETTRACE_840",
        "GE_PETTRACE_860",
        "GE_PETTRACE_880",
        "GE_PETTRACE_890",
        "IBA_CYCLONE_KEY",
        "IBA_CYCLONE_KIUBE",
    }


def test_pettrace_800_schedulable_but_uncalibrated_yields():
    """PETtrace 800 has cycle times (schedulable) but every performance record
    has a null yield (not_calibrated) -- it must never resolve a numeric EOB."""
    model = cc.load_cyclotron_catalog().by_id("GE_PETTRACE_800")
    assert model.schedulable_radionuclides  # non-empty (has cycles)
    assert all(r.normalized_eob_activity_mbq is None for r in model.production_performance_records)
    assert model.production_calibration_status in ("modeled", "not_calibrated")


# ---------------------------------------------------------------------------
# 4. RADIONUCLIDE-SPECIFIC RESOLUTION -- never cross-radionuclide reuse
# ---------------------------------------------------------------------------


def test_calibrated_eob_resolution_is_radionuclide_and_cycle_specific():
    """A calibrated EOB is only bound to an isotope whose cycle time matches
    the record's irradiation time; a mismatched cycle yields no capacity."""
    catalog = cc.load_cyclotron_catalog()
    model = catalog.by_id("GE_PETTRACE_840")
    # Correct cycle (120 min) -> resolves.
    resolved_match = cc._resolve_calibrated_eob_by_radionuclide(
        model=model,
        schedulable_supported=("F-18",),
        cycles={"F-18": 120.0},
        site_operating_current_ua=None,
    )
    assert resolved_match == {"F-18": 240000.0}
    # Mismatched cycle (90 min) -> no record matches -> empty.
    resolved_mismatch = cc._resolve_calibrated_eob_by_radionuclide(
        model=model,
        schedulable_supported=("F-18",),
        cycles={"F-18": 90.0},
        site_operating_current_ua=None,
    )
    assert resolved_mismatch == {}


# ---------------------------------------------------------------------------
# 5. PATIENT -> RADIONUCLIDE -> ACTIVITY (demand-derived, heterogeneous)
# ---------------------------------------------------------------------------


def test_patient_demand_groups_preserve_heterogeneous_activity_sum():
    """total_prescribed_activity_mbq is the SUM of per-patient activity, never
    patient_count x generic dose."""
    day = FacilityDayPatientDemand(
        patients=(
            PatientRadionuclideDemand(patient_id="P1", radionuclide="F-18", prescribed_activity_mbq=370.0),
            PatientRadionuclideDemand(patient_id="P2", radionuclide="F-18", prescribed_activity_mbq=250.0),
            PatientRadionuclideDemand(patient_id="P3", radionuclide="F-18", prescribed_activity_mbq=410.0),
        )
    )
    (group,) = group_patients_by_radionuclide(day)
    assert group.radionuclide == "F-18"
    assert group.patient_count == 3
    assert group.total_prescribed_activity_mbq == 370.0 + 250.0 + 410.0
    # NOT patient_count * a single dose
    assert group.total_prescribed_activity_mbq != 3 * 370.0


def test_activity_chain_admin_to_eob_is_decay_compensated_per_patient():
    """A_EOB = A_admin / R(elapsed) using the canonical decay primitives."""
    half_life = 109.8  # F-18
    a_admin = 370.0
    elapsed = 60.0
    retained = retained_fraction(elapsed, half_life)
    a_eob = required_upstream_activity(a_admin, retained)
    # Decay compensation strictly increases the required upstream activity.
    assert a_eob > a_admin
    assert math.isclose(a_eob, a_admin / retained, rel_tol=0.0, abs_tol=1e-9)


def test_cycle_relative_requirement_sums_per_patient_eob():
    """derive_cycle_relative_requirement assigns patients to a calibrated cycle
    and reports a total EOB requirement equal to the sum of per-patient EOB."""
    half_life = 109.8
    cycles = generate_candidate_production_cycles(
        cyclotron_id="CY-TEST",
        radionuclide="F-18",
        cycle_minutes=120.0,
        calibrated_eob_capacity_mbq=240000.0,
        release_processing_minutes=30.0,
        production_start_time_minutes=0.0,
        production_horizon_minutes=600.0,
    )
    assert cycles  # at least one schedulable cycle
    patient_ids = ["P1", "P2"]
    prescribed = {"P1": 370.0, "P2": 250.0}
    admin_times = {"P1": 300.0, "P2": 330.0}
    result = derive_cycle_relative_requirement(
        radionuclide="F-18",
        half_life_minutes=half_life,
        patient_ids=patient_ids,
        prescribed_activity_mbq_by_patient_id=prescribed,
        administration_time_minutes_by_patient_id=admin_times,
        candidate_cycles=cycles,
    )
    assigned = [a for a in result.assignments if a.feasible]
    assert len(assigned) == 2
    summed = sum(a.required_eob_activity_mbq for a in assigned)
    assert math.isclose(result.total_required_eob_activity_mbq, summed, rel_tol=0.0, abs_tol=1e-6)
    # Each per-patient EOB is decay-compensated above its prescribed activity.
    for a in assigned:
        assert a.required_eob_activity_mbq >= prescribed[a.patient_id]


# ---------------------------------------------------------------------------
# 6. PATIENT -> BATCH -> SOURCE (radionuclide compatibility enforced)
# ---------------------------------------------------------------------------


def test_batch_partition_is_per_radionuclide_and_preserves_patient_ids():
    day = FacilityDayPatientDemand(
        patients=(
            PatientRadionuclideDemand(patient_id="P1", radionuclide="F-18", prescribed_activity_mbq=370.0),
            PatientRadionuclideDemand(patient_id="P2", radionuclide="F-18", prescribed_activity_mbq=370.0),
            PatientRadionuclideDemand(patient_id="P3", radionuclide="Ga-68", prescribed_activity_mbq=185.0),
        )
    )
    batches = partition_facility_day_patient_demand(day, {"F-18": 1, "Ga-68": 1})
    by_iso = {b.radionuclide: b for b in batches}
    assert set(by_iso) == {"F-18", "Ga-68"}
    assert isinstance(by_iso["F-18"], RadionuclideBatchDemand)
    assert by_iso["F-18"].patient_count == 2
    assert set(by_iso["F-18"].patient_ids) == {"P1", "P2"}
    assert by_iso["Ga-68"].patient_ids == ("P3",)
    # A batch never mixes radionuclides.
    for batch in batches:
        assert isinstance(batch.batch_id, int)


def test_batch_assignment_requires_radionuclide_support():
    """assign_batches_to_cyclotron_fleet raises when the batch radionuclide is
    not supported by any fleet cyclotron (never silently reassigns)."""
    from cyclotron_production_windows import (
        CyclotronProductionCapability,
        assign_batches_to_cyclotron_fleet,
        build_single_cyclotron_fleet,
    )

    capability = CyclotronProductionCapability(
        cyclotron_id="CY-F18",
        supported_radionuclides=("F-18",),
        max_simultaneous_production_streams=1,
        production_cycle_minutes_by_radionuclide={"F-18": 120.0},
    )
    fleet = build_single_cyclotron_fleet(capability)
    incompatible_batch = RadionuclideBatchDemand(
        batch_id=1, radionuclide="Ga-68", patient_ids=("P1",), patient_count=1,
        total_prescribed_activity_mbq=185.0,
    )
    try:
        assign_batches_to_cyclotron_fleet((incompatible_batch,), fleet)
    except ValueError as exc:
        assert "unsupported radionuclide" in str(exc)
    else:  # pragma: no cover - assignment must not succeed
        raise AssertionError("Expected ValueError for unsupported radionuclide batch")


# ---------------------------------------------------------------------------
# 7. RESOLVER CORRECTNESS -- no legacy fallback, honest not_calibrated
# ---------------------------------------------------------------------------


def test_resolver_returns_not_calibrated_for_uncalibrated_fleet_isotope():
    """A calibrated F-18 fleet queried for a non-calibrated isotope returns
    not_calibrated -- never a cross-radionuclide or legacy fallback number."""
    catalog = cc.load_cyclotron_catalog()
    instance = cc.create_facility_cyclotron_instance(
        catalog_model_id="GE_PETTRACE_840", existing_instances=()
    )
    fleet, _ = cc.build_fleet_from_instances(catalog=catalog, instances=(instance,))
    assert fleet is not None
    # PETtrace 840 supports only F-18; Ga-68 must resolve to not_calibrated.
    cap, status = resolve_fleet_eob_capacity_mbq_per_day(
        fleet=fleet, radionuclide="Ga-68", production_batches_per_day=1
    )
    assert cap is None
    assert status == "not_calibrated"


# ---------------------------------------------------------------------------
# 8. GENERATOR PARITY -- Mo-99/Tc-99m only, economics not calibrated
# ---------------------------------------------------------------------------


def test_generator_catalog_is_mo99_tc99m_and_economics_not_calibrated():
    import generator_catalog as gc

    catalog = gc.load_generator_catalog()
    assert catalog.models, "generator catalog must contain at least one model"

    # RECONCILED (Clinical Radionuclide Completeness & Evidence Closure, OG-GEN-1):
    # Build 3B originally protected the repository GAP "the only generator pathway
    # is Mo-99 -> Tc-99m; no gallium generator exists". That gap was later CLOSED
    # by canonical evidence: the Ge-68 -> Ga-68 generator (ECKERT_ZIEGLER_GALLIAPHARM,
    # evidence EV-GA68-GEN-001 / EV-GE68-HL-001) is now a real catalog model. This
    # test is narrowed to protect the NEW canonical truth without weakening Build 3B's
    # actual guarantees: (a) the Mo-99 -> Tc-99m pathway is still present, and (b) all
    # generator economics remain NOT_CALIBRATED (never fabricated $0).
    mo99_tc99m = [m for m in catalog.models if m.parent_radionuclide == "Mo-99"]
    assert mo99_tc99m, "Mo-99 -> Tc-99m generator pathway must remain present"
    for model in mo99_tc99m:
        assert model.daughter_radionuclide == "Tc-99m"

    # The Ge-68 -> Ga-68 pathway is now canonical and DISTINCT from Mo-99/Tc-99m.
    ge68_ga68 = [m for m in catalog.models if m.parent_radionuclide == "Ge-68"]
    for model in ge68_ga68:
        assert model.daughter_radionuclide == "Ga-68"
    # Every generator parent/daughter pairing is one of the two canonical pathways;
    # no fabricated third pathway was introduced.
    for model in catalog.models:
        assert (model.parent_radionuclide, model.daughter_radionuclide) in {
            ("Mo-99", "Tc-99m"),
            ("Ge-68", "Ga-68"),
        }

    # Generator economics remain NOT_CALIBRATED for every model (the guarantee the
    # test name asserts) -- never a fabricated price.
    for model in catalog.models:
        for record in model.economics:
            assert record.value == "NOT_CALIBRATED"
            assert record.calibration_status == "not_calibrated"

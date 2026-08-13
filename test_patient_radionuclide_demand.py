from __future__ import annotations

import math

import pytest

from diagnostics import load_radionuclide_half_lives
from patient_radionuclide_demand import (
    FacilityDayPatientDemand,
    PatientRadionuclideDemand,
    group_patients_by_radionuclide,
    partition_facility_day_patient_demand,
    resolve_facility_day_patient_demand,
)


def _patient(patient_id: str, radionuclide: str, activity: float) -> PatientRadionuclideDemand:
    return PatientRadionuclideDemand(
        patient_id=patient_id,
        radionuclide=radionuclide,
        prescribed_activity_mbq=activity,
    )


def _day(*patients: PatientRadionuclideDemand) -> FacilityDayPatientDemand:
    return FacilityDayPatientDemand(patients=tuple(patients))


def _demo_day() -> FacilityDayPatientDemand:
    return _day(
        _patient("P1", "F-18", 200.0),
        _patient("P2", "Ga-68", 150.0),
        _patient("P3", "F-18", 200.0),
        _patient("P4", "Tc-99m", 600.0),
        _patient("P5", "Ga-68", 150.0),
        _patient("P6", "F-18", 200.0),
    )


def test_valid_f18_patient_record():
    patient = _patient("P1", "F-18", 200.0)
    assert patient.patient_id == "P1"
    assert patient.radionuclide == "F-18"
    assert patient.prescribed_activity_mbq == 200.0


def test_valid_ga68_patient_record():
    patient = _patient("P2", "Ga-68", 150.0)
    assert patient.patient_id == "P2"
    assert patient.radionuclide == "Ga-68"
    assert patient.prescribed_activity_mbq == 150.0


def test_unknown_radionuclide_is_rejected():
    with pytest.raises(ValueError, match="Unknown radionuclide"):
        _patient("P1", "Xe-123", 100.0)


def test_zero_prescribed_activity_is_rejected():
    with pytest.raises(ValueError, match="greater than zero"):
        _patient("P1", "F-18", 0.0)


def test_negative_prescribed_activity_is_rejected():
    with pytest.raises(ValueError, match="greater than zero"):
        _patient("P1", "F-18", -1.0)


def test_empty_patient_id_is_rejected():
    with pytest.raises(ValueError, match="patient_id must be a non-empty string"):
        _patient("   ", "F-18", 100.0)


def test_duplicate_patient_ids_in_same_facility_day_are_rejected():
    with pytest.raises(ValueError, match="Duplicate patient_id"):
        _day(_patient("P1", "F-18", 100.0), _patient("P1", "Ga-68", 100.0))


def test_one_radionuclide_day_is_accepted():
    day = _day(_patient("P1", "F-18", 100.0), _patient("P2", "F-18", 100.0))
    assert len(day.patients) == 2


def test_two_radionuclide_day_is_accepted():
    day = _day(_patient("P1", "F-18", 100.0), _patient("P2", "Ga-68", 100.0))
    assert len({patient.radionuclide for patient in day.patients}) == 2


def test_three_radionuclide_day_is_accepted():
    day = _day(
        _patient("P1", "F-18", 100.0),
        _patient("P2", "Ga-68", 100.0),
        _patient("P3", "Tc-99m", 100.0),
    )
    assert len({patient.radionuclide for patient in day.patients}) == 3


def test_four_radionuclide_day_is_rejected():
    with pytest.raises(ValueError, match="more than three distinct radionuclides"):
        _day(
            _patient("P1", "F-18", 100.0),
            _patient("P2", "Ga-68", 100.0),
            _patient("P3", "Tc-99m", 100.0),
            _patient("P4", "C-11", 100.0),
        )


def test_half_life_is_resolved_from_canonical_library_not_stored_on_patient():
    patient = _patient("P1", "F-18", 200.0)
    resolved = resolve_facility_day_patient_demand(_day(patient))[0]
    assert not hasattr(patient, "half_life_minutes")
    assert resolved.half_life_minutes == load_radionuclide_half_lives()["F-18"]


def test_f18_half_life_resolves_to_current_canonical_value():
    assert load_radionuclide_half_lives()["F-18"] == 109.8


def test_ga68_half_life_resolves_to_current_canonical_value():
    assert load_radionuclide_half_lives()["Ga-68"] == 67.7


def test_grouping_produces_correct_patient_counts_by_isotope():
    groups = group_patients_by_radionuclide(
        _day(
            _patient("P1", "F-18", 200.0),
            _patient("P2", "Ga-68", 150.0),
            _patient("P3", "F-18", 200.0),
            _patient("P4", "Tc-99m", 600.0),
            _patient("P5", "Ga-68", 150.0),
        )
    )
    counts = {group.radionuclide: group.patient_count for group in groups}
    assert counts == {"F-18": 2, "Ga-68": 2, "Tc-99m": 1}


def test_grouping_produces_correct_total_prescribed_activity_by_isotope():
    groups = group_patients_by_radionuclide(_demo_day())
    totals = {group.radionuclide: group.total_prescribed_activity_mbq for group in groups}
    assert totals == {"F-18": 600.0, "Ga-68": 300.0, "Tc-99m": 600.0}


def test_patient_ordering_is_deterministic_within_group():
    groups = group_patients_by_radionuclide(
        _day(
            _patient("P3", "F-18", 200.0),
            _patient("P1", "F-18", 200.0),
            _patient("P2", "F-18", 200.0),
        )
    )
    assert groups[0].patient_ids == ("P3", "P1", "P2")


def test_batch_partition_never_mixes_radionuclides():
    day = _demo_day()
    batches = partition_facility_day_patient_demand(day, {"F-18": 2, "Ga-68": 1, "Tc-99m": 1})
    patient_to_radionuclide = {patient.patient_id: patient.radionuclide for patient in day.patients}
    for batch in batches:
        assert all(patient_to_radionuclide[patient_id] == batch.radionuclide for patient_id in batch.patient_ids)


def test_ten_patients_into_three_batches_produces_four_three_three():
    day = _day(*(_patient(f"F{i}", "F-18", 100.0) for i in range(10)))
    batches = partition_facility_day_patient_demand(day, {"F-18": 3})
    assert [batch.patient_count for batch in batches] == [4, 3, 3]


def test_multiple_radionuclides_partition_independently():
    batches = partition_facility_day_patient_demand(
        _demo_day(),
        {"F-18": 2, "Ga-68": 1, "Tc-99m": 1},
    )
    counts = {"F-18": 0, "Ga-68": 0, "Tc-99m": 0}
    for batch in batches:
        counts[batch.radionuclide] += 1
    assert counts == {"F-18": 2, "Ga-68": 1, "Tc-99m": 1}


def test_every_patient_appears_in_exactly_one_generated_batch():
    batches = partition_facility_day_patient_demand(
        _demo_day(),
        {"F-18": 2, "Ga-68": 1, "Tc-99m": 1},
    )
    seen = [patient_id for batch in batches for patient_id in batch.patient_ids]
    assert sorted(seen) == ["P1", "P2", "P3", "P4", "P5", "P6"]
    assert len(seen) == len(set(seen))


def test_batch_activity_reconciles_with_facility_day_total():
    day = _demo_day()
    batches = partition_facility_day_patient_demand(day, {"F-18": 2, "Ga-68": 1, "Tc-99m": 1})
    total_batch_activity = sum(batch.total_prescribed_activity_mbq for batch in batches)
    total_day_activity = sum(patient.prescribed_activity_mbq for patient in day.patients)
    assert math.isclose(total_batch_activity, total_day_activity, rel_tol=0.0, abs_tol=1e-9)
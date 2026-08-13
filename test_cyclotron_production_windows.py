from __future__ import annotations

import math

import pytest

from cyclotron_production_windows import (
    CyclotronProductionCapability,
    schedule_cyclotron_production_windows,
)
from patient_radionuclide_demand import (
    FacilityDayPatientDemand,
    PatientRadionuclideDemand,
    partition_facility_day_patient_demand,
)


def _patient(patient_id: str, radionuclide: str, activity: float) -> PatientRadionuclideDemand:
    return PatientRadionuclideDemand(
        patient_id=patient_id,
        radionuclide=radionuclide,
        prescribed_activity_mbq=activity,
    )


def _demo_day() -> FacilityDayPatientDemand:
    return FacilityDayPatientDemand(
        patients=(
            _patient("P1", "F-18", 200.0),
            _patient("P2", "Ga-68", 150.0),
            _patient("P3", "F-18", 200.0),
            _patient("P4", "Tc-99m", 600.0),
            _patient("P5", "Ga-68", 150.0),
            _patient("P6", "F-18", 200.0),
        )
    )


def _demo_batches():
    return partition_facility_day_patient_demand(
        _demo_day(),
        {"F-18": 2, "Ga-68": 1, "Tc-99m": 1},
    )


def _serial_capability() -> CyclotronProductionCapability:
    return CyclotronProductionCapability(
        cyclotron_id="CY-serial",
        supported_radionuclides=("F-18", "Ga-68", "Tc-99m"),
        max_simultaneous_production_streams=1,
        production_cycle_minutes_by_radionuclide={
            "F-18": 30.0,
            "Ga-68": 20.0,
            "Tc-99m": 25.0,
        },
    )


def _dual_capability_with_f18_ga68_pair() -> CyclotronProductionCapability:
    return CyclotronProductionCapability(
        cyclotron_id="CY-dual",
        supported_radionuclides=("F-18", "Ga-68", "Tc-99m"),
        max_simultaneous_production_streams=2,
        production_cycle_minutes_by_radionuclide={
            "F-18": 30.0,
            "Ga-68": 20.0,
            "Tc-99m": 25.0,
        },
        simultaneously_compatible_radionuclide_sets=(frozenset(("F-18", "Ga-68")),),
    )


def test_valid_single_stream_capability():
    capability = _serial_capability()
    assert capability.max_simultaneous_production_streams == 1


def test_valid_dual_stream_capability():
    capability = _dual_capability_with_f18_ga68_pair()
    assert capability.max_simultaneous_production_streams == 2


def test_empty_cyclotron_id_rejected():
    with pytest.raises(ValueError, match="cyclotron_id must be a non-empty string"):
        CyclotronProductionCapability(
            cyclotron_id=" ",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
        )


def test_unknown_supported_radionuclide_rejected():
    with pytest.raises(ValueError, match="Unknown radionuclide"):
        CyclotronProductionCapability(
            cyclotron_id="CY1",
            supported_radionuclides=("F-18", "Xx-1"),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0, "Xx-1": 10.0},
        )


def test_zero_simultaneous_streams_rejected():
    with pytest.raises(ValueError, match="at least 1"):
        CyclotronProductionCapability(
            cyclotron_id="CY1",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=0,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
        )


def test_negative_production_cycle_rejected():
    with pytest.raises(ValueError, match="greater than zero"):
        CyclotronProductionCapability(
            cyclotron_id="CY1",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": -1.0},
        )


def test_missing_production_cycle_value_rejected():
    with pytest.raises(ValueError, match="Missing production cycle minutes"):
        CyclotronProductionCapability(
            cyclotron_id="CY1",
            supported_radionuclides=("F-18", "Ga-68"),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
        )


def test_unsupported_batch_isotope_rejected():
    capability = CyclotronProductionCapability(
        cyclotron_id="CY1",
        supported_radionuclides=("F-18",),
        max_simultaneous_production_streams=1,
        production_cycle_minutes_by_radionuclide={"F-18": 30.0},
    )
    batches = _demo_batches()
    with pytest.raises(ValueError, match="unsupported radionuclide"):
        schedule_cyclotron_production_windows(batches, capability)


def test_single_stream_schedules_all_batches_serially():
    schedule = schedule_cyclotron_production_windows(_demo_batches(), _serial_capability())
    assert schedule.total_windows == schedule.total_batches


def test_serial_schedule_timing_reconciles_exactly():
    schedule = schedule_cyclotron_production_windows(_demo_batches(), _serial_capability())
    expected = 30.0 + 30.0 + 20.0 + 25.0
    assert math.isclose(schedule.total_elapsed_production_minutes, expected, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(schedule.production_end_time_minutes, expected, rel_tol=0.0, abs_tol=1e-9)


def test_dual_stream_compatible_f18_and_ga68_can_share_window():
    schedule = schedule_cyclotron_production_windows(_demo_batches(), _dual_capability_with_f18_ga68_pair())
    assert any(set(window.radionuclides) == {"F-18", "Ga-68"} for window in schedule.windows)


def test_simultaneous_batches_remain_separate_batch_ids():
    schedule = schedule_cyclotron_production_windows(_demo_batches(), _dual_capability_with_f18_ga68_pair())
    pair_window = next(window for window in schedule.windows if len(window.batch_ids) == 2)
    assert len(pair_window.batch_ids) == 2
    assert pair_window.batch_ids[0] != pair_window.batch_ids[1]


def test_same_isotope_batches_never_share_window():
    schedule = schedule_cyclotron_production_windows(_demo_batches(), _dual_capability_with_f18_ga68_pair())
    for window in schedule.windows:
        assert len(window.radionuclides) == len(set(window.radionuclides))


def test_incompatible_isotope_pair_remains_serial():
    batches = _demo_batches()
    tc_batch = next(batch for batch in batches if batch.radionuclide == "Tc-99m")
    schedule = schedule_cyclotron_production_windows(batches, _dual_capability_with_f18_ga68_pair())
    tc_window = next(window for window in schedule.windows if tc_batch.batch_id in window.batch_ids)
    assert tc_window.simultaneous_stream_count == 1


def test_dual_stream_without_explicit_compatibility_remains_serial():
    capability = CyclotronProductionCapability(
        cyclotron_id="CY-dual-no-compat",
        supported_radionuclides=("F-18", "Ga-68", "Tc-99m"),
        max_simultaneous_production_streams=2,
        production_cycle_minutes_by_radionuclide={"F-18": 30.0, "Ga-68": 20.0, "Tc-99m": 25.0},
    )
    schedule = schedule_cyclotron_production_windows(_demo_batches(), capability)
    assert all(window.simultaneous_stream_count == 1 for window in schedule.windows)


def test_simultaneous_window_duration_equals_longest_cycle():
    schedule = schedule_cyclotron_production_windows(_demo_batches(), _dual_capability_with_f18_ga68_pair())
    pair_window = next(window for window in schedule.windows if set(window.radionuclides) == {"F-18", "Ga-68"})
    assert math.isclose(pair_window.duration_minutes, 30.0, rel_tol=0.0, abs_tol=1e-9)


def test_next_window_starts_at_prior_window_end():
    schedule = schedule_cyclotron_production_windows(_demo_batches(), _dual_capability_with_f18_ga68_pair())
    for prior, later in zip(schedule.windows, schedule.windows[1:]):
        assert math.isclose(later.start_time_minutes, prior.end_time_minutes, rel_tol=0.0, abs_tol=1e-9)


def test_every_input_batch_appears_exactly_once():
    batches = _demo_batches()
    schedule = schedule_cyclotron_production_windows(batches, _dual_capability_with_f18_ga68_pair())
    listed = [batch_id for window in schedule.windows for batch_id in window.batch_ids]
    expected = [batch.batch_id for batch in batches]
    assert sorted(listed) == sorted(expected)
    assert len(listed) == len(set(listed))


def test_no_batch_appears_in_two_windows():
    schedule = schedule_cyclotron_production_windows(_demo_batches(), _dual_capability_with_f18_ga68_pair())
    listed = [batch_id for window in schedule.windows for batch_id in window.batch_ids]
    assert len(listed) == len(set(listed))


def test_max_stream_limit_never_exceeded():
    capability = _dual_capability_with_f18_ga68_pair()
    schedule = schedule_cyclotron_production_windows(_demo_batches(), capability)
    assert all(window.simultaneous_stream_count <= capability.max_simultaneous_production_streams for window in schedule.windows)


def test_1080_minute_feasible_schedule_returns_true():
    schedule = schedule_cyclotron_production_windows(
        _demo_batches(),
        _serial_capability(),
        production_horizon_minutes=1080.0,
    )
    assert schedule.fits_within_production_horizon is True


def test_over_horizon_schedule_returns_false():
    schedule = schedule_cyclotron_production_windows(
        _demo_batches(),
        _serial_capability(),
        production_horizon_minutes=90.0,
    )
    assert schedule.fits_within_production_horizon is False


def test_deterministic_ordering_is_preserved():
    schedule_a = schedule_cyclotron_production_windows(_demo_batches(), _dual_capability_with_f18_ga68_pair())
    schedule_b = schedule_cyclotron_production_windows(_demo_batches(), _dual_capability_with_f18_ga68_pair())
    signature_a = tuple((window.batch_ids, window.radionuclides) for window in schedule_a.windows)
    signature_b = tuple((window.batch_ids, window.radionuclides) for window in schedule_b.windows)
    assert signature_a == signature_b


def test_three_isotope_patient_day_batches_can_be_scheduled():
    schedule = schedule_cyclotron_production_windows(_demo_batches(), _dual_capability_with_f18_ga68_pair())
    assert schedule.all_batches_scheduled is True
    assert schedule.total_batches == 4


def test_max_streams_two_does_not_imply_arbitrary_three_isotope_pairing():
    schedule = schedule_cyclotron_production_windows(_demo_batches(), _dual_capability_with_f18_ga68_pair())
    assert all(set(window.radionuclides) != {"F-18", "Tc-99m"} for window in schedule.windows)

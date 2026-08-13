from __future__ import annotations

import math

import pytest

from cyclotron_production_windows import CyclotronProductionCapability
from patient_radionuclide_demand import (
    FacilityDayPatientDemand,
    PatientRadionuclideDemand,
)
from production_clinical_schedule import (
    ProductionClinicalScenario,
    build_production_clinical_schedule,
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


def _serial_capability() -> CyclotronProductionCapability:
    return CyclotronProductionCapability(
        cyclotron_id="DEMO-SERIAL",
        supported_radionuclides=("F-18", "Ga-68", "Tc-99m"),
        max_simultaneous_production_streams=1,
        production_cycle_minutes_by_radionuclide={"F-18": 30.0, "Ga-68": 20.0, "Tc-99m": 25.0},
    )


def _dual_capability() -> CyclotronProductionCapability:
    return CyclotronProductionCapability(
        cyclotron_id="DEMO-DUAL",
        supported_radionuclides=("F-18", "Ga-68", "Tc-99m"),
        max_simultaneous_production_streams=2,
        production_cycle_minutes_by_radionuclide={"F-18": 30.0, "Ga-68": 20.0, "Tc-99m": 25.0},
        simultaneously_compatible_radionuclide_sets=(frozenset(("F-18", "Ga-68")),),
    )


def _dual_no_compat_capability() -> CyclotronProductionCapability:
    return CyclotronProductionCapability(
        cyclotron_id="DEMO-DUAL-NO-COMPAT",
        supported_radionuclides=("F-18", "Ga-68", "Tc-99m"),
        max_simultaneous_production_streams=2,
        production_cycle_minutes_by_radionuclide={"F-18": 30.0, "Ga-68": 20.0, "Tc-99m": 25.0},
    )


def _scenario(
    capability: CyclotronProductionCapability,
    *,
    transport: float = 5.0,
    injection: float = 5.0,
    uptake: float = 5.0,
    scan: float = 5.0,
    scanners: int = 1,
    injection_resources: int = 1,
    uptake_resources: int = 1,
    distribution_concurrency: int = 1,
    operating_day_minutes: float = 1080.0,
) -> ProductionClinicalScenario:
    return ProductionClinicalScenario(
        facility_day_demand=_demo_day(),
        requested_batch_count_by_radionuclide={"F-18": 2, "Ga-68": 1, "Tc-99m": 1},
        cyclotron_capability=capability,
        transport_minutes=transport,
        injection_service_minutes=injection,
        uptake_minutes=uptake,
        scanner_service_minutes=scan,
        injection_resources=injection_resources,
        uptake_resources=uptake_resources,
        scanners=scanners,
        distribution_concurrency=distribution_concurrency,
        operating_day_minutes=operating_day_minutes,
        production_horizon_minutes=1080.0,
    )


def _trace_by_patient(result):
    return {trace.patient_id: trace for trace in result.patient_traces}


def _release_by_batch(result):
    return {mapping.batch_id: mapping for mapping in result.batch_release_mappings}


def test_batch_release_time_equals_production_window_end_time():
    result = build_production_clinical_schedule(_scenario(_serial_capability()))
    mapping = _release_by_batch(result)[1]
    assert math.isclose(mapping.release_time_minutes, mapping.production_window_end_time_minutes, rel_tol=0.0, abs_tol=1e-9)


def test_two_isotope_batches_in_same_production_window_receive_same_release_time():
    result = build_production_clinical_schedule(_scenario(_dual_capability()))
    releases = _release_by_batch(result)
    assert releases[1].production_window_id == releases[3].production_window_id
    assert math.isclose(releases[1].release_time_minutes, releases[3].release_time_minutes, rel_tol=0.0, abs_tol=1e-9)


def test_batches_remain_isotope_specific_after_shared_production_window():
    result = build_production_clinical_schedule(_scenario(_dual_capability()))
    releases = _release_by_batch(result)
    assert releases[1].radionuclide == "F-18"
    assert releases[3].radionuclide == "Ga-68"


def test_patient_inherits_its_batch_release_time():
    result = build_production_clinical_schedule(_scenario(_dual_capability()))
    traces = _trace_by_patient(result)
    releases = _release_by_batch(result)
    assert math.isclose(traces["P2"].batch_release_time_minutes, releases[3].release_time_minutes, rel_tol=0.0, abs_tol=1e-9)


def test_every_patient_maps_to_exactly_one_production_batch():
    result = build_production_clinical_schedule(_scenario(_serial_capability()))
    patient_ids = [patient_id for batch in result.batch_demands for patient_id in batch.patient_ids]
    assert sorted(patient_ids) == ["P1", "P2", "P3", "P4", "P5", "P6"]
    assert len(patient_ids) == len(set(patient_ids))


def test_every_production_batch_maps_to_exactly_one_production_window():
    result = build_production_clinical_schedule(_scenario(_dual_capability()))
    batch_ids = [mapping.batch_id for mapping in result.batch_release_mappings]
    assert sorted(batch_ids) == [1, 2, 3, 4]
    assert len(batch_ids) == len(set(batch_ids))


def test_generated_batchrelease_patient_counts_reconcile_with_batch_demand():
    result = build_production_clinical_schedule(_scenario(_serial_capability()))
    counts = {batch.batch_id: batch.patient_count for batch in result.batch_demands}
    release_counts = {release.batch_id: release.patients_in_batch for release in result.batch_releases}
    assert release_counts == counts


def test_serial_production_release_times_are_chronological():
    result = build_production_clinical_schedule(_scenario(_serial_capability()))
    assert [release.release_time_minutes for release in result.batch_releases] == [30.0, 60.0, 80.0, 105.0]


def test_dual_compatible_production_can_create_earlier_release_for_batches():
    serial = build_production_clinical_schedule(_scenario(_serial_capability()))
    dual = build_production_clinical_schedule(_scenario(_dual_capability()))
    assert _release_by_batch(dual)[3].release_time_minutes < _release_by_batch(serial)[3].release_time_minutes


def test_earlier_production_release_propagates_to_earlier_distribution():
    serial = build_production_clinical_schedule(_scenario(_serial_capability()))
    dual = build_production_clinical_schedule(_scenario(_dual_capability()))
    assert _trace_by_patient(dual)["P2"].distribution_start < _trace_by_patient(serial)["P2"].distribution_start


def test_earlier_release_propagates_to_earlier_injection_when_resources_permit():
    serial = build_production_clinical_schedule(_scenario(_serial_capability()))
    dual = build_production_clinical_schedule(_scenario(_dual_capability()))
    assert _trace_by_patient(dual)["P2"].injection_start < _trace_by_patient(serial)["P2"].injection_start


def test_earlier_release_does_not_guarantee_earlier_scan_if_scanner_binds():
    serial = build_production_clinical_schedule(_scenario(_serial_capability(), scan=120.0))
    dual = build_production_clinical_schedule(_scenario(_dual_capability(), scan=120.0))
    assert _trace_by_patient(dual)["P4"].batch_release_time_minutes < _trace_by_patient(serial)["P4"].batch_release_time_minutes
    assert math.isclose(_trace_by_patient(dual)["P4"].scan_start, _trace_by_patient(serial)["P4"].scan_start, rel_tol=0.0, abs_tol=1e-9)


def test_production_batches_share_same_clinical_resource_pools():
    result = build_production_clinical_schedule(_scenario(_dual_capability()))
    traces = _trace_by_patient(result)
    assert traces["P2"].distribution_start >= traces["P3"].distribution_end


def test_later_isotope_batch_does_not_reset_scanner_capacity():
    result = build_production_clinical_schedule(_scenario(_dual_capability(), scan=120.0))
    traces = _trace_by_patient(result)
    assert traces["P4"].scan_start >= traces["P6"].scan_end


def test_clinical_completion_still_obeys_1080_minute_cutoff():
    result = build_production_clinical_schedule(
        _scenario(_serial_capability(), scan=300.0, operating_day_minutes=400.0)
    )
    assert any(not trace.completed_within_operating_day for trace in result.patient_traces)
    assert result.clinical_schedule.completed_patients < result.clinical_schedule.total_patients_considered


def test_no_patient_is_counted_twice():
    result = build_production_clinical_schedule(_scenario(_serial_capability()))
    patient_ids = [trace.patient_id for trace in result.patient_traces]
    assert len(patient_ids) == len(set(patient_ids))


def test_patient_count_reconciles_across_demand_batches_and_scheduler():
    result = build_production_clinical_schedule(_scenario(_serial_capability()))
    demand_patients = len(result.scenario.facility_day_demand.patients)
    batch_patients = sum(batch.patient_count for batch in result.batch_demands)
    scheduled_patients = result.clinical_schedule.total_patients_considered
    traced_patients = len(result.patient_traces)
    assert demand_patients == batch_patients == scheduled_patients == traced_patients


def test_unsupported_cyclotron_isotope_fails_upstream():
    capability = CyclotronProductionCapability(
        cyclotron_id="F18-ONLY",
        supported_radionuclides=("F-18",),
        max_simultaneous_production_streams=1,
        production_cycle_minutes_by_radionuclide={"F-18": 30.0},
    )
    with pytest.raises(ValueError, match="unsupported radionuclide"):
        build_production_clinical_schedule(_scenario(capability))


def test_incompatible_isotope_pair_remains_serial_and_retains_serial_release_timing():
    serial = build_production_clinical_schedule(_scenario(_serial_capability()))
    dual_no_compat = build_production_clinical_schedule(_scenario(_dual_no_compat_capability()))
    assert [release.release_time_minutes for release in dual_no_compat.batch_releases] == [release.release_time_minutes for release in serial.batch_releases]


def test_identical_production_schedules_produce_identical_clinical_schedules():
    scenario = _scenario(_dual_capability())
    result_a = build_production_clinical_schedule(scenario)
    result_b = build_production_clinical_schedule(scenario)
    assert result_a == result_b


def test_dual_stream_production_does_not_multiply_clinical_resource_counts():
    serial = build_production_clinical_schedule(_scenario(_serial_capability()))
    dual = build_production_clinical_schedule(_scenario(_dual_capability()))
    assert serial.operating_day_inputs.scanners == dual.operating_day_inputs.scanners == 1
    assert serial.operating_day_inputs.injection_resources == dual.operating_day_inputs.injection_resources == 1
    assert serial.operating_day_inputs.uptake_resources == dual.operating_day_inputs.uptake_resources == 1
    assert serial.operating_day_inputs.distribution_concurrency == dual.operating_day_inputs.distribution_concurrency == 1


def test_traceability_chain_is_complete_for_every_patient():
    result = build_production_clinical_schedule(_scenario(_dual_capability()))
    for trace in result.patient_traces:
        assert trace.patient_id
        assert trace.radionuclide
        assert trace.batch_id > 0
        assert trace.production_window_id > 0
        assert trace.production_window_end_time_minutes >= trace.production_window_start_time_minutes
        assert trace.batch_release_time_minutes >= trace.production_window_end_time_minutes
        assert trace.scheduler_patient_id > 0
        assert trace.distribution_start >= trace.batch_release_time_minutes
        assert trace.injection_start >= trace.distribution_end
        assert trace.uptake_start >= trace.injection_end
        assert trace.scan_start >= trace.uptake_end

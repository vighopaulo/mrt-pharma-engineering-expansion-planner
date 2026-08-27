from __future__ import annotations

from dataclasses import replace

import pytest

from cyclotron_production_windows import CyclotronProductionCapability
from decision_pipeline import NativeDecisionPipelineScenario, NativePathwayScenario, run_native_decision_pipeline
from facility_engineering_model import CoordinateSystem, build_default_facility_engineering_object_model
from models import PlannerAssumptions, SharedNetworkAssumptions
from production_clinical_schedule import MRTCarrierTransportScheduleResult
from stochastic_design_day import ActivityDemandModel


def _planner() -> PlannerAssumptions:
    return PlannerAssumptions(
        analysis_years=10,
        discount_rate_pct=8.0,
        operating_days_per_year=300,
        revenue_per_scan=2000.0,
        scanner_cycle_min=20.0,
        injection_cycle_min=10.0,
        uptake_cycle_min=45.0,
        operating_hours_per_day=18.0,
    )


def _activity_models() -> dict[str, ActivityDemandModel]:
    return {
        "F-18": ActivityDemandModel(
            "bounded_normal",
            mean_activity_mbq=200.0,
            stddev_activity_mbq=20.0,
            lower_bound_mbq=160.0,
            upper_bound_mbq=240.0,
        ),
    }


def _conventional_pathway(*, distribution_concurrency: int = 1) -> NativePathwayScenario:
    return NativePathwayScenario(
        pathway="Conventional",
        scanners=3,
        injection_resources=2,
        uptake_resources=7,
        distribution_concurrency=distribution_concurrency,
        transport_minutes=7.0,
        installed_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        radiopharmacy_unit_capex=750_000.0,
        conventional_infrastructure_allowance_units=1,
        conventional_infrastructure_allowance_unit_capex=125_000.0,
        annual_conventional_transport_opex=750_000.0,
        annual_production_variable_cost=300_000.0,
        annual_scanner_energy_kwh=12_000.0,
        annual_cyclotron_energy_kwh=120_000.0,
        annual_other_energy_kwh=4_000.0,
        electricity_cost_per_kwh=0.18,
        clinical_staff_fte=4.0,
        clinical_staff_loaded_cost_per_fte=95_000.0,
        production_staff_fte=2.0,
        production_staff_loaded_cost_per_fte=110_000.0,
        annual_consumable_units=6000.0,
        consumable_cost_per_unit=22.0,
    )


def _mrt_pathway(
    *,
    distribution_concurrency: int = 2,
    installed_mrt_carriers: int = 2,
    operated_mrt_carriers: int = 2,
    transport_minutes: float = 5.0,
    installed_guideway_length_m: float = 250.0,
    guideway_capex_per_m: float = 12_000.0,
) -> NativePathwayScenario:
    return NativePathwayScenario(
        pathway="MRT",
        scanners=5,
        injection_resources=3,
        uptake_resources=10,
        distribution_concurrency=distribution_concurrency,
        transport_minutes=transport_minutes,
        installed_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        radiopharmacy_unit_capex=750_000.0,
        installed_mrt_base_infrastructure_units=1,
        installed_mrt_endpoints=2,
        installed_guideway_length_m=installed_guideway_length_m,
        guideway_capex_per_m=guideway_capex_per_m,
        installed_mrt_carriers=installed_mrt_carriers,
        operated_mrt_carriers=operated_mrt_carriers,
        operated_mrt_base_units=1,
        operated_mrt_endpoints=2,
        operated_guideway_length_m=installed_guideway_length_m,
        guideway_maintenance_per_m_year=0.0,
        annual_mrt_energy_kwh=25_000.0,
        mrt_support_staff_fte=3.0,
        mrt_support_staff_loaded_cost_per_fte=105_000.0,
        annual_production_variable_cost=300_000.0,
        annual_scanner_energy_kwh=12_000.0,
        annual_cyclotron_energy_kwh=120_000.0,
        annual_other_energy_kwh=4_000.0,
        electricity_cost_per_kwh=0.18,
        clinical_staff_fte=4.0,
        clinical_staff_loaded_cost_per_fte=95_000.0,
        production_staff_fte=2.0,
        production_staff_loaded_cost_per_fte=110_000.0,
        annual_consumable_units=6000.0,
        consumable_cost_per_unit=22.0,
    )


def _request(
    *,
    target_patients_per_day: int = 180,
    conventional: NativePathwayScenario | None = None,
    mrt: NativePathwayScenario | None = None,
    facility_model=None,
    planner: PlannerAssumptions | None = None,
) -> NativeDecisionPipelineScenario:
    return NativeDecisionPipelineScenario(
        project_name="MRT Transport Separation",
        target_patients_per_day=target_patients_per_day,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide=_activity_models(),
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="PIPELINE-F18",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
        ),
        conventional=_conventional_pathway() if conventional is None else conventional,
        mrt=_mrt_pathway() if mrt is None else mrt,
        planner_assumptions=_planner() if planner is None else planner,
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260816,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=5,
        facility_engineering_model=facility_model,
    )


def _coord() -> CoordinateSystem:
    return CoordinateSystem(
        coordinate_system_id="LOCAL",
        name="Local",
        building="Building A",
        storey="Level 1",
        local_coordinate_system="LOCAL",
        source_coordinate_reference="manual",
        scale_m_per_unit=1.0,
    )


def _facility(route_distance_m: float, vertical_change_m: float) -> object:
    return build_default_facility_engineering_object_model(
        facility_id="FAC-MRT",
        facility_name="MRT Facility",
        project_spatial_mode="RETROFIT",
        source_type="DWG",
        subscription_tier="PROFESSIONAL",
        coordinate_system=_coord(),
        building_name="Production Building",
        clinical_building_name="Clinical Building",
        route_distance_m=route_distance_m,
        vertical_change_m=vertical_change_m,
        route_geometry_status="RECONSTRUCTED",
        equipment_class="Cyclotron",
        scanner_floors=("Level 1",),
        injection_floors=("Level 1",),
        uptake_floors=("Level 1",),
    )


def _mrt_schedule(result) -> MRTCarrierTransportScheduleResult:
    schedule = result.mrt.operational_result.production_clinical_result.transport_schedule
    assert isinstance(schedule, MRTCarrierTransportScheduleResult)
    return schedule


def test_mrt_ignores_conventional_manual_transport_assumptions():
    base_request = _request()
    fast_manual = replace(
        base_request.planner_assumptions,
        manual_transport_speed_m_per_s=10.0,
        manual_transport_pickup_minutes=0.0,
        manual_transport_handoff_minutes=0.0,
        manual_transport_elevator_wait_minutes=0.0,
        manual_transport_elevator_loading_minutes=0.0,
    )
    slow_manual = replace(
        base_request.planner_assumptions,
        manual_transport_speed_m_per_s=0.1,
        manual_transport_pickup_minutes=6.0,
        manual_transport_handoff_minutes=6.0,
        manual_transport_elevator_wait_minutes=12.0,
        manual_transport_elevator_loading_minutes=4.0,
    )

    base = run_native_decision_pipeline(base_request)
    fast = run_native_decision_pipeline(replace(base_request, planner_assumptions=fast_manual))
    slow = run_native_decision_pipeline(replace(base_request, planner_assumptions=slow_manual))

    base_schedule = _mrt_schedule(base)
    fast_schedule = _mrt_schedule(fast)
    slow_schedule = _mrt_schedule(slow)

    assert base.mrt.operational_result.pathway_config.transport_minutes == pytest.approx(fast.mrt.operational_result.pathway_config.transport_minutes)
    assert base.mrt.operational_result.pathway_config.transport_minutes == pytest.approx(slow.mrt.operational_result.pathway_config.transport_minutes)
    assert base_schedule.average_carrier_queue_wait_minutes == pytest.approx(fast_schedule.average_carrier_queue_wait_minutes)
    assert base_schedule.average_carrier_queue_wait_minutes == pytest.approx(slow_schedule.average_carrier_queue_wait_minutes)
    assert base.mrt.operational_result.patients_completed == fast.mrt.operational_result.patients_completed == slow.mrt.operational_result.patients_completed


def test_mrt_carrier_count_controls_queueing_and_throughput_under_transport_limit():
    one = run_native_decision_pipeline(_request(mrt=_mrt_pathway(distribution_concurrency=1, installed_mrt_carriers=1, operated_mrt_carriers=1, transport_minutes=120.0)))
    two = run_native_decision_pipeline(_request(mrt=_mrt_pathway(distribution_concurrency=2, installed_mrt_carriers=2, operated_mrt_carriers=2, transport_minutes=120.0)))
    four = run_native_decision_pipeline(_request(mrt=_mrt_pathway(distribution_concurrency=4, installed_mrt_carriers=4, operated_mrt_carriers=4, transport_minutes=120.0)))

    s1 = _mrt_schedule(one)
    s2 = _mrt_schedule(two)
    s4 = _mrt_schedule(four)

    assert s1.transport_jobs_per_day == s2.transport_jobs_per_day == s4.transport_jobs_per_day
    assert s1.average_carrier_queue_wait_minutes >= s2.average_carrier_queue_wait_minutes >= s4.average_carrier_queue_wait_minutes
    assert s1.maximum_carrier_queue_wait_minutes >= s2.maximum_carrier_queue_wait_minutes >= s4.maximum_carrier_queue_wait_minutes
    assert one.mrt.operational_result.patients_completed <= two.mrt.operational_result.patients_completed <= four.mrt.operational_result.patients_completed


def test_mrt_geometry_route_length_changes_transport_time():
    short_route = run_native_decision_pipeline(_request(facility_model=_facility(route_distance_m=120.0, vertical_change_m=0.0)))
    long_route = run_native_decision_pipeline(_request(facility_model=_facility(route_distance_m=1500.0, vertical_change_m=0.0)))

    short_schedule = _mrt_schedule(short_route)
    long_schedule = _mrt_schedule(long_route)

    assert short_route.mrt.operational_result.pathway_config.transport_minutes_source == "VERIFIED_GEOMETRY_DERIVED"
    assert long_route.mrt.operational_result.pathway_config.transport_minutes_source == "VERIFIED_GEOMETRY_DERIVED"
    assert long_schedule.route_profile.route_distance_m > short_schedule.route_profile.route_distance_m
    assert long_schedule.route_profile.transport_minutes > short_schedule.route_profile.transport_minutes


def test_mrt_vertical_route_uses_transition_and_vertical_segments_not_manual_elevator():
    same_floor = run_native_decision_pipeline(_request(facility_model=_facility(route_distance_m=200.0, vertical_change_m=0.0)))
    upper_floor = run_native_decision_pipeline(_request(facility_model=_facility(route_distance_m=200.0, vertical_change_m=8.0)))

    same_schedule = _mrt_schedule(same_floor)
    upper_schedule = _mrt_schedule(upper_floor)

    assert same_schedule.route_profile.vertical_distance_m == pytest.approx(0.0)
    assert upper_schedule.route_profile.vertical_distance_m > 0.0
    assert upper_schedule.route_profile.hv_transition_count > 0
    assert upper_schedule.route_profile.transport_minutes > same_schedule.route_profile.transport_minutes


def test_mrt_economics_carrier_capex_and_opex_scale_with_carriers():
    one = run_native_decision_pipeline(_request(mrt=_mrt_pathway(installed_mrt_carriers=1, operated_mrt_carriers=1)))
    four = run_native_decision_pipeline(_request(mrt=_mrt_pathway(installed_mrt_carriers=4, operated_mrt_carriers=4, distribution_concurrency=4)))

    one_capex = next(item for item in one.mrt.capex_result.ledger if item.component == "MRT carriers")
    four_capex = next(item for item in four.mrt.capex_result.ledger if item.component == "MRT carriers")
    assert one_capex.subtotal == pytest.approx(10_000.0)
    assert four_capex.subtotal == pytest.approx(40_000.0)

    one_electric = next(item for item in one.mrt.opex_result.ledger if item.component == "MRT carrier allocated electricity")
    four_electric = next(item for item in four.mrt.opex_result.ledger if item.component == "MRT carrier allocated electricity")
    one_maintenance = next(item for item in one.mrt.opex_result.ledger if item.component == "MRT carrier maintenance")
    four_maintenance = next(item for item in four.mrt.opex_result.ledger if item.component == "MRT carrier maintenance")

    assert one_electric.annual_cost == pytest.approx(250.0)
    assert four_electric.annual_cost == pytest.approx(1_000.0)
    assert one_maintenance.annual_cost == pytest.approx(500.0)
    assert four_maintenance.annual_cost == pytest.approx(2_000.0)


def test_mrt_guideway_capex_scales_with_length_under_default_assumption():
    short = run_native_decision_pipeline(_request(mrt=_mrt_pathway(installed_guideway_length_m=100.0, guideway_capex_per_m=0.0)))
    long = run_native_decision_pipeline(_request(mrt=_mrt_pathway(installed_guideway_length_m=400.0, guideway_capex_per_m=0.0)))

    short_item = next(item for item in short.mrt.capex_result.ledger if item.component == "MRT guideway")
    long_item = next(item for item in long.mrt.capex_result.ledger if item.component == "MRT guideway")

    assert short_item.subtotal == pytest.approx(100.0 * 5_000.0)
    assert long_item.subtotal == pytest.approx(400.0 * 5_000.0)
    assert long_item.subtotal == pytest.approx(4.0 * short_item.subtotal)


def test_no_transport_economic_cross_charging_between_pathways():
    result = run_native_decision_pipeline(_request())

    mrt_components = [row.component for row in result.mrt.opex_result.ledger]
    conventional_components = [row.component for row in result.conventional.opex_result.ledger]

    assert "Conventional transport and handling allowance" not in mrt_components
    assert "Conventional transport labor" not in mrt_components
    assert "MRT carrier allocated electricity" not in conventional_components
    assert "MRT carrier maintenance" not in conventional_components


def test_legacy_mrt_fallback_without_geometry_remains_scalar_transport_basis():
    result = run_native_decision_pipeline(_request(facility_model=None))
    schedule = _mrt_schedule(result)

    assert result.mrt.operational_result.pathway_config.transport_minutes_source == "USER_SUPPLIED_TRANSPORT_TIME"
    assert schedule.route_profile.transport_minutes_source == "USER_SUPPLIED_TRANSPORT_TIME"
    assert schedule.route_profile.transport_minutes == pytest.approx(result.mrt.operational_result.pathway_config.transport_minutes)


def test_mrt_decay_clock_counts_queue_and_transport_once_and_timeline_is_ordered():
    request = _request(
        target_patients_per_day=20,
        mrt=_mrt_pathway(distribution_concurrency=1, installed_mrt_carriers=1, operated_mrt_carriers=1, transport_minutes=120.0),
    )
    result = run_native_decision_pipeline(request)
    schedule = _mrt_schedule(result)

    first_job = schedule.jobs[0]
    first_trace = result.mrt.decay_summary.patient_traces[0]

    assert first_trace.production_window_end_time_minutes <= first_trace.release_time_minutes
    assert first_trace.release_time_minutes <= first_job.queue_start_time_minutes
    assert first_job.queue_start_time_minutes <= first_job.dispatch_time_minutes
    assert first_job.dispatch_time_minutes <= first_job.arrival_time_minutes
    assert first_job.arrival_time_minutes <= first_trace.injection_start_minutes
    assert first_trace.injection_start_minutes <= first_trace.injection_end_minutes
    assert first_trace.injection_end_minutes <= first_trace.scan_start_minutes

    elapsed = first_trace.elapsed_release_to_injection_minutes
    assert elapsed >= first_job.queue_wait_time_minutes + first_job.transport_time_minutes

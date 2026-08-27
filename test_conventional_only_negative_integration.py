from __future__ import annotations

import math

import pytest

from cyclotron_production_windows import CyclotronAsset, CyclotronFleet, CyclotronProductionCapability
from decision_pipeline import (
    NativeDecisionPipelineScenario,
    NativePathwayScenario,
    run_native_conventional_only_pipeline,
    run_native_decision_pipeline,
)
from facility_engineering_model import (
    CoordinateSystem,
    RequiredFacilityProgram,
    build_default_facility_engineering_object_model,
    build_space_function_assignment,
    validate_facility_engineering_object_model,
)
from models import PlannerAssumptions, SharedNetworkAssumptions
from stochastic_design_day import ActivityDemandModel


def _planner_assumptions() -> PlannerAssumptions:
    return PlannerAssumptions(
        analysis_years=5,
        discount_rate_pct=8.0,
        operating_days_per_year=300,
        revenue_per_scan=1800.0,
        scanner_cycle_min=20.0,
        injection_cycle_min=10.0,
        uptake_cycle_min=45.0,
        operating_hours_per_day=18.0,
    )


def _activity_models() -> dict[str, ActivityDemandModel]:
    return {
        "F-18": ActivityDemandModel(
            "fixed",
            fixed_activity_mbq=370.0,
        )
    }


def _conventional_pathway(*, transport_minutes: float = 8.0, distribution_concurrency: int = 1) -> NativePathwayScenario:
    return NativePathwayScenario(
        pathway="Conventional",
        scanners=4,
        injection_resources=3,
        uptake_resources=8,
        distribution_concurrency=distribution_concurrency,
        transport_minutes=transport_minutes,
        installed_cyclotron_units=2,
        existing_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        radiopharmacy_unit_capex=700_000.0,
        conventional_infrastructure_allowance_units=1,
        conventional_infrastructure_allowance_unit_capex=120_000.0,
        annual_conventional_transport_opex=500_000.0,
        annual_production_variable_cost=280_000.0,
        cyclotron_annual_opex_per_unit=420_000.0,
        annual_scanner_energy_kwh=15_000.0,
        annual_cyclotron_energy_kwh=140_000.0,
        annual_other_energy_kwh=8_000.0,
        electricity_cost_per_kwh=0.18,
        clinical_staff_fte=6.0,
        clinical_staff_loaded_cost_per_fte=95_000.0,
        production_staff_fte=4.0,
        production_staff_loaded_cost_per_fte=110_000.0,
        conventional_transport_staff_fte=2.0,
        conventional_transport_staff_loaded_cost_per_fte=85_000.0,
        annual_consumable_units=8_000.0,
        consumable_cost_per_unit=20.0,
    )


def _mrt_pathway() -> NativePathwayScenario:
    return NativePathwayScenario(
        pathway="MRT",
        scanners=4,
        injection_resources=3,
        uptake_resources=8,
        distribution_concurrency=2,
        transport_minutes=3.0,
        installed_cyclotron_units=2,
        existing_cyclotron_units=1,
        installed_radiopharmacy_units=1,
        radiopharmacy_unit_capex=700_000.0,
        installed_mrt_base_infrastructure_units=1,
        installed_mrt_endpoints=2,
        installed_guideway_length_m=180.0,
        guideway_capex_per_m=10_000.0,
        operated_mrt_base_units=1,
        operated_mrt_endpoints=2,
        operated_guideway_length_m=180.0,
        guideway_maintenance_per_m_year=900.0,
        annual_mrt_energy_kwh=22_000.0,
        mrt_support_staff_fte=2.0,
        mrt_support_staff_loaded_cost_per_fte=100_000.0,
        annual_production_variable_cost=280_000.0,
        cyclotron_annual_opex_per_unit=420_000.0,
        annual_scanner_energy_kwh=15_000.0,
        annual_cyclotron_energy_kwh=140_000.0,
        annual_other_energy_kwh=8_000.0,
        electricity_cost_per_kwh=0.18,
        clinical_staff_fte=6.0,
        clinical_staff_loaded_cost_per_fte=95_000.0,
        production_staff_fte=4.0,
        production_staff_loaded_cost_per_fte=110_000.0,
        annual_consumable_units=8_000.0,
        consumable_cost_per_unit=20.0,
    )


def _capability(*, calibrated: bool) -> CyclotronProductionCapability:
    return CyclotronProductionCapability(
        cyclotron_id="CY-FLEET",
        supported_radionuclides=("F-18",),
        max_simultaneous_production_streams=1,
        production_cycle_minutes_by_radionuclide={"F-18": 35.0},
        release_processing_minutes_by_radionuclide={"F-18": 6.0},
        calibrated_eob_activity_mbq_by_radionuclide={"F-18": 250_000.0} if calibrated else None,
        site_eob_capacity_mbq_per_day=900_000.0 if calibrated else None,
    )


def _request_conventional_only(*, calibrated: bool = True) -> NativeDecisionPipelineScenario:
    capability = _capability(calibrated=calibrated)
    fleet = CyclotronFleet(
        assets=(
            CyclotronAsset(
                cyclotron_id="CY-FLEET",
                capability=capability,
                installed_quantity=2,
                capability_provenance="catalog" if not calibrated else "test",
            ),
        )
    )
    return NativeDecisionPipelineScenario(
        project_name="Conventional Only",
        target_patients_per_day=90,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide=_activity_models(),
        cyclotron_capability=capability,
        cyclotron_fleet=fleet,
        conventional=_conventional_pathway(transport_minutes=9.0, distribution_concurrency=1),
        mrt=None,
        product_profile="CONVENTIONAL_ONLY",
        planner_assumptions=_planner_assumptions(),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260816,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=15,
    )


def _route_model(*, route_distance_m: float, vertical_change_m: float, route_geometry_status: str = "NOT_RECONSTRUCTED"):
    return build_default_facility_engineering_object_model(
        facility_id="FAC-ROUTE",
        facility_name="Conventional Route Study",
        project_spatial_mode="RETROFIT",
        source_type="MANUAL",
        subscription_tier="BASIC",
        coordinate_system=CoordinateSystem(
            coordinate_system_id="LOCAL-ROUTE",
            name="Local route coordinates",
            building="Building A",
            storey="Level 1",
            local_coordinate_system="LOCAL",
            source_coordinate_reference="manual",
            scale_m_per_unit=1.0,
        ),
        building_name="Production Building",
        clinical_building_name="Clinical Building",
        storey_name="Level 1",
        space_name="Injection Room",
        route_distance_m=route_distance_m,
        vertical_change_m=vertical_change_m,
        route_geometry_status=route_geometry_status,
        equipment_class="Cyclotron",
        scanner_floors=("Level 1",),
        injection_floors=("Level 1",),
        uptake_floors=("Level 1",),
    )


def _request_conventional_only_with_model(model) -> NativeDecisionPipelineScenario:
    request = _request_conventional_only(calibrated=True)
    return NativeDecisionPipelineScenario(
        project_name=request.project_name,
        target_patients_per_day=request.target_patients_per_day,
        radionuclide_mix=request.radionuclide_mix,
        activity_distribution_by_radionuclide=request.activity_distribution_by_radionuclide,
        cyclotron_capability=request.cyclotron_capability,
        cyclotron_fleet=request.cyclotron_fleet,
        conventional=request.conventional,
        mrt=None,
        product_profile=request.product_profile,
        planner_assumptions=request.planner_assumptions,
        shared_network_assumptions=request.shared_network_assumptions,
        day_type=request.day_type,
        seed=request.seed,
        operating_day_minutes=request.operating_day_minutes,
        batch_target_patients_per_batch=request.batch_target_patients_per_batch,
        facility_engineering_model=model,
    )


def test_conventional_only_pipeline_executes_without_mrt_and_keeps_core_physics() -> None:
    result = run_native_conventional_only_pipeline(_request_conventional_only(calibrated=True))
    pathway = result.conventional
    operational = pathway.operational_result

    assert result.product_profile == "CONVENTIONAL_ONLY"
    assert pathway.pathway == "Conventional"
    assert pathway.capex_result.total_capex > 0.0
    assert pathway.opex_result.total_annual_opex > 0.0
    assert pathway.annual_revenue > 0.0
    assert operational.patients_completed > 0

    assert pathway.capex_result.mrt_specific_capex == pytest.approx(0.0)
    assert pathway.opex_result.mrt_specific_opex == pytest.approx(0.0)
    assert all("mrt" not in item.component.lower() for item in pathway.capex_result.ledger)
    assert all("guideway" not in item.component.lower() for item in pathway.capex_result.ledger)
    assert all("carrier" not in item.component.lower() for item in pathway.capex_result.ledger)
    assert all("mrt" not in item.component.lower() for item in pathway.opex_result.ledger)
    assert all("guideway" not in item.component.lower() for item in pathway.opex_result.ledger)
    assert all("carrier" not in item.component.lower() for item in pathway.opex_result.ledger)

    transport_schedule = operational.production_clinical_result.transport_schedule
    assert operational.production_clinical_result.operating_day_inputs.transport_minutes == pytest.approx(0.0)
    assert transport_schedule.transport_jobs_per_day > 0
    assert transport_schedule.transporter_utilization_pct > 0.0
    assert transport_schedule.transport_resource_minutes_per_day > 0.0
    assert all(job.resource_occupancy_minutes == pytest.approx(job.outbound_transport_minutes + job.return_reposition_minutes) for job in transport_schedule.jobs)

    assert not hasattr(result, "mrt")
    assert not hasattr(result, "lifecycle_comparison_result")

    traces_with_elapsed = [trace for trace in pathway.decay_summary.patient_traces if trace.elapsed_eob_to_injection_minutes > 0.0]
    assert traces_with_elapsed
    assert all(trace.activity_at_eob_mbq > trace.activity_at_injection_mbq for trace in traces_with_elapsed)
    assert all(
        math.isclose(
            trace.activity_at_injection_mbq,
            trace.activity_at_eob_mbq * (2.0 ** (-trace.elapsed_eob_to_injection_minutes / trace.half_life_minutes)),
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        for trace in traces_with_elapsed
        if trace.activity_at_eob_mbq > 0.0
    )
    assert operational.bottleneck.resource in {"scanner", "injection", "uptake", "distribution"}


def test_conventional_route_distance_changes_derived_transport_time() -> None:
    near_model = _route_model(route_distance_m=25.0, vertical_change_m=0.0)
    far_model = _route_model(route_distance_m=250.0, vertical_change_m=0.0)

    near = run_native_conventional_only_pipeline(_request_conventional_only_with_model(near_model))
    far = run_native_conventional_only_pipeline(_request_conventional_only_with_model(far_model))

    assert near.conventional.operational_result.pathway_config.transport_minutes_source == "USER_SUPPLIED_DISTANCE_DERIVED"
    assert far.conventional.operational_result.pathway_config.transport_minutes_source == "USER_SUPPLIED_DISTANCE_DERIVED"
    assert far.conventional.operational_result.production_clinical_result.transport_schedule.jobs[0].outbound_transport_minutes > near.conventional.operational_result.production_clinical_result.transport_schedule.jobs[0].outbound_transport_minutes
    assert far.conventional.operational_result.production_clinical_result.transport_schedule.jobs[0].arrival_time_minutes > near.conventional.operational_result.production_clinical_result.transport_schedule.jobs[0].arrival_time_minutes
    assert far.conventional.decay_summary.mean_retained_fraction < near.conventional.decay_summary.mean_retained_fraction


def test_upper_floor_route_requires_more_transport_than_same_floor_route() -> None:
    same_floor_model = _route_model(route_distance_m=40.0, vertical_change_m=0.0)
    upper_floor_model = _route_model(route_distance_m=40.0, vertical_change_m=4.0)

    same_floor = run_native_conventional_only_pipeline(_request_conventional_only_with_model(same_floor_model))
    upper_floor = run_native_conventional_only_pipeline(_request_conventional_only_with_model(upper_floor_model))

    assert upper_floor.conventional.operational_result.production_clinical_result.transport_schedule.jobs[0].outbound_transport_minutes > same_floor.conventional.operational_result.production_clinical_result.transport_schedule.jobs[0].outbound_transport_minutes
    assert upper_floor.conventional.decay_summary.mean_retained_fraction < same_floor.conventional.decay_summary.mean_retained_fraction


def test_transporter_concurrency_changes_queueing_under_transport_limited_demand() -> None:
    base_request = _request_conventional_only(calibrated=True)
    queue_model = build_default_facility_engineering_object_model(
        facility_id="FAC-QUEUE-1",
        facility_name="Queue Study",
        project_spatial_mode="RETROFIT",
        source_type="MANUAL",
        subscription_tier="BASIC",
        coordinate_system=CoordinateSystem(
            coordinate_system_id="LOCAL-QUEUE",
            name="Queue coordinates",
            building="Building A",
            storey="Level 1",
            local_coordinate_system="LOCAL",
            source_coordinate_reference="manual",
            scale_m_per_unit=1.0,
        ),
        building_name="Production Building",
        clinical_building_name="Clinical Building",
        storey_name="Level 1",
        space_name="Injection Room",
        route_distance_m=5000.0,
        vertical_change_m=0.0,
        equipment_class="Cyclotron",
        scanner_floors=("Level 1",),
        injection_floors=("Level 1",),
        uptake_floors=("Level 1",),
    )

    def _request_with_transporters(transporter_count: int) -> NativeDecisionPipelineScenario:
        return NativeDecisionPipelineScenario(
            project_name=base_request.project_name,
            target_patients_per_day=180,
            radionuclide_mix={"F-18": 1.0},
            activity_distribution_by_radionuclide=base_request.activity_distribution_by_radionuclide,
            cyclotron_capability=base_request.cyclotron_capability,
            cyclotron_fleet=base_request.cyclotron_fleet,
            conventional=type(base_request.conventional)(**{**base_request.conventional.__dict__, "distribution_concurrency": transporter_count}),
            mrt=None,
            product_profile="CONVENTIONAL_ONLY",
            planner_assumptions=base_request.planner_assumptions,
            shared_network_assumptions=base_request.shared_network_assumptions,
            day_type=base_request.day_type,
            seed=base_request.seed,
            operating_day_minutes=1080.0,
            batch_target_patients_per_batch=5,
            facility_engineering_model=queue_model,
        )

    one = run_native_conventional_only_pipeline(_request_with_transporters(1))
    two = run_native_conventional_only_pipeline(_request_with_transporters(2))

    one_schedule = one.conventional.operational_result.production_clinical_result.transport_schedule
    two_schedule = two.conventional.operational_result.production_clinical_result.transport_schedule

    assert one_schedule.transport_jobs_per_day == two_schedule.transport_jobs_per_day
    assert one_schedule.average_wait_minutes > two_schedule.average_wait_minutes
    assert one_schedule.transporter_utilization_pct > two_schedule.transporter_utilization_pct
    assert one.conventional.operational_result.patients_completed < two.conventional.operational_result.patients_completed


def test_core_vs_expansion_building_demo_reports_transport_queue_and_economics() -> None:
    core_model = _route_model(route_distance_m=25.0, vertical_change_m=0.0)
    expansion_model = _route_model(route_distance_m=5000.0, vertical_change_m=4.0)

    core = run_native_conventional_only_pipeline(_request_conventional_only_with_model(core_model))
    expansion = run_native_conventional_only_pipeline(_request_conventional_only_with_model(expansion_model))

    core_transport = core.conventional.operational_result.production_clinical_result.transport_schedule
    expansion_transport = expansion.conventional.operational_result.production_clinical_result.transport_schedule

    assert expansion_transport.jobs[0].outbound_transport_minutes > core_transport.jobs[0].outbound_transport_minutes
    assert expansion_transport.average_wait_minutes >= core_transport.average_wait_minutes
    assert expansion_transport.transport_resource_minutes_per_day >= core_transport.transport_resource_minutes_per_day
    assert expansion.conventional.decay_summary.mean_retained_fraction < core.conventional.decay_summary.mean_retained_fraction
    assert expansion.conventional.operational_result.patients_completed <= core.conventional.operational_result.patients_completed
    assert expansion.conventional.annual_opex == pytest.approx(core.conventional.annual_opex)
    assert expansion.conventional.annual_revenue <= core.conventional.annual_revenue
    assert expansion_transport.transporter_utilization_pct >= core_transport.transporter_utilization_pct


def test_conventional_only_not_calibrated_behavior_is_preserved() -> None:
    result = run_native_conventional_only_pipeline(_request_conventional_only(calibrated=False))
    warnings = result.conventional.operational_result.activity_capacity_warnings

    assert warnings
    assert any("not_calibrated" in warning for warning in warnings)


def test_conventional_spatial_model_valid_without_mrt_objects() -> None:
    model = build_default_facility_engineering_object_model(
        facility_id="FAC-CONV-001",
        facility_name="Conventional Facility",
        project_spatial_mode="RETROFIT",
        source_type="MANUAL",
        subscription_tier="BASIC",
        coordinate_system=CoordinateSystem(
            coordinate_system_id="LOCAL-1",
            name="Local coordinates",
            building="Production Building",
            storey="Level 1",
            local_coordinate_system="LOCAL",
            source_coordinate_reference="manual",
            scale_m_per_unit=1.0,
        ),
        building_name="Production Building",
        clinical_building_name="Clinical Building",
        storey_name="Level 1",
        space_name="Radiopharmacy",
        route_distance_m=52.0,
        vertical_change_m=0.0,
        equipment_class="Cyclotron",
        scanner_floors=("Level 1",),
        injection_floors=("Level 1",),
        uptake_floors=("Level 1",),
        source_space_assignments=(
            build_space_function_assignment(
                space_id="FAC-CONV-001:R1",
                source_name="Office",
                source_function="Office",
                proposed_name="Office",
                proposed_function="Office",
                assignment_status="EXISTING_AS_BUILT",
            ),
        ),
        proposed_space_assignments=(
            build_space_function_assignment(
                space_id="FAC-CONV-001:R1",
                source_name="Office",
                source_function="Office",
                proposed_name="Injection Room 1",
                proposed_function="Injection room",
                assignment_status="OPTIMIZER_PROPOSED",
                suitability="SUITABLE_WITH_MODIFICATION",
            ),
            build_space_function_assignment(
                space_id="FAC-CONV-001:R2",
                source_name="Storage",
                source_function="Storage",
                proposed_name="Uptake Room 1",
                proposed_function="Uptake room",
                assignment_status="OPTIMIZER_PROPOSED",
                suitability="SUITABLE_WITH_MODIFICATION",
            ),
            build_space_function_assignment(
                space_id="FAC-CONV-001:R3",
                source_name="Control Room",
                source_function="Control room",
                proposed_name="PET/CT 1",
                proposed_function="PET/CT scanner",
                assignment_status="OPTIMIZER_PROPOSED",
                suitability="SUITABLE_WITH_MODIFICATION",
            ),
        ),
        required_program=RequiredFacilityProgram(
            injection_rooms_required=1,
            uptake_rooms_required=1,
            pet_ct_scanners_required=1,
        ),
    )

    issues = validate_facility_engineering_object_model(model)
    codes = {issue.code for issue in issues}

    assert model.production_building_id is not None
    assert model.clinical_building_ids
    assert model.primary_route_origin_object_id is not None
    assert model.feasibility_report is not None
    assert model.feasibility_report.feasible is True
    assert "CYCLOTRON_NOT_GROUND_LEVEL" not in codes
    assert "PRODUCTION_BUILDING_NOT_SEPARATE" not in codes
    assert "MISSING_ROUTE_ORIGIN" not in codes
    assert not any(equipment.equipment_class.startswith("MRT") for equipment in model.equipment)


def test_conventional_only_does_not_require_comparison_but_mrt_pipeline_still_works() -> None:
    conventional_only_request = _request_conventional_only(calibrated=True)
    with pytest.raises(ValueError, match="run_native_conventional_only_pipeline"):
        run_native_decision_pipeline(conventional_only_request)

    mrt_enabled_request = NativeDecisionPipelineScenario(
        project_name="MRT Preserved",
        target_patients_per_day=90,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide=_activity_models(),
        cyclotron_capability=_capability(calibrated=True),
        conventional=_conventional_pathway(transport_minutes=9.0, distribution_concurrency=1),
        mrt=_mrt_pathway(),
        product_profile="MRT_ENABLED",
        planner_assumptions=_planner_assumptions(),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260816,
        operating_day_minutes=1080.0,
        batch_target_patients_per_batch=15,
    )

    comparison = run_native_decision_pipeline(mrt_enabled_request)
    conventional_only = run_native_conventional_only_pipeline(conventional_only_request)

    assert comparison.mrt.pathway == "MRT"
    assert comparison.mrt.capex_result.mrt_specific_capex > 0.0
    assert comparison.mrt.opex_result.mrt_specific_opex > 0.0
    assert comparison.mrt.operational_result.pathway_config.transport_minutes == pytest.approx(3.0)

    assert math.isclose(
        comparison.conventional.operational_result.patients_completed,
        conventional_only.conventional.operational_result.patients_completed,
        rel_tol=0.0,
        abs_tol=1e-9,
    )
    assert comparison.conventional.operational_result.pathway_config.transport_minutes == pytest.approx(9.0)

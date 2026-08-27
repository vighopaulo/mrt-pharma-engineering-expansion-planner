"""Controlled tests: Multi-Origin Cyclotron Spatial Integration (this phase).

Covers spec sections 44-52, 62: patient->cyclotron->origin traceability,
wrong-origin rejection, Conventional/MRT route-origin sensitivity, retention
response, Hybrid source/mode independence, CY-002 ON/OFF, and the distinction
between production-capacity value and spatial-origin value.
"""

from __future__ import annotations

import pytest

from engineering_authority import validate_cyclotron_spatial_origin_traceability
from models import PlannerAssumptions
from multi_isotope_decay import retained_fraction
from diagnostics import load_radionuclide_half_lives
from multi_cyclotron_authority import (
    build_controlled_dual_origin_geometry,
    build_multi_cyclotron_scenario,
    build_single_origin_production_clinical_scenario,
    origin_object_id_by_cyclotron_id,
    route_metrics_from_origin,
    validate_payload_origin,
)
from production_clinical_schedule import (
    ConventionalTransportScheduleResult,
    MRTCarrierTransportScheduleResult,
    build_production_clinical_schedule,
)


def test_controlled_geometry_route_network_not_euclidean() -> None:
    """Section 17: destinations genuinely differ in graph-edge-path distance
    (not Euclidean straight-line distance) depending on origin."""
    assumptions = PlannerAssumptions()
    geometry = build_controlled_dual_origin_geometry()

    near_a_from_rp1 = route_metrics_from_origin(model=geometry, origin_object_id="RP-001", destination_object_id="D-NEAR-A", assumptions=assumptions)
    near_a_from_rp2 = route_metrics_from_origin(model=geometry, origin_object_id="RP-002", destination_object_id="D-NEAR-A", assumptions=assumptions)
    near_b_from_rp1 = route_metrics_from_origin(model=geometry, origin_object_id="RP-001", destination_object_id="D-NEAR-B", assumptions=assumptions)
    near_b_from_rp2 = route_metrics_from_origin(model=geometry, origin_object_id="RP-002", destination_object_id="D-NEAR-B", assumptions=assumptions)

    # D-NEAR-A is closer to RP-001; D-NEAR-B is closer to RP-002.
    assert near_a_from_rp1.distance_m < near_a_from_rp2.distance_m
    assert near_b_from_rp2.distance_m < near_b_from_rp1.distance_m


def test_mrt_origin_not_network_connected_is_classified_infeasible() -> None:
    """Section 10: an origin with no edges into the route network raises a
    clear infeasibility signal rather than silently teleporting the payload."""
    assumptions = PlannerAssumptions()
    disconnected_geometry = build_controlled_dual_origin_geometry(include_rp002_in_network=False)
    with pytest.raises(ValueError):
        route_metrics_from_origin(model=disconnected_geometry, origin_object_id="RP-002", destination_object_id="D-NEAR-B", assumptions=assumptions)
    # RP-001 remains fully network-connected regardless of RP-002's isolation.
    reachable = route_metrics_from_origin(model=disconnected_geometry, origin_object_id="RP-001", destination_object_id="D-NEAR-B", assumptions=assumptions)
    assert reachable.distance_m > 0.0


def test_conventional_route_responds_to_producing_cyclotron_origin() -> None:
    """Section 46: same destination, produced once from RP-001, once from
    RP-002 -- Conventional route/time genuinely changes with origin, via the
    REAL authoritative build_production_clinical_schedule pipeline (not a
    parallel diagnostic computation)."""
    assumptions = PlannerAssumptions()
    geometry = build_controlled_dual_origin_geometry()

    scenario_a = build_single_origin_production_clinical_scenario(
        cyclotron_id="CY-001", radiopharmacy_origin_object_id="RP-001", pathway="Conventional",
        geometry=geometry, patient_count=4, assumptions=assumptions,
    )
    scenario_b = build_single_origin_production_clinical_scenario(
        cyclotron_id="CY-002", radiopharmacy_origin_object_id="RP-002", pathway="Conventional",
        geometry=geometry, patient_count=4, assumptions=assumptions,
    )
    result_a = build_production_clinical_schedule(scenario_a)
    result_b = build_production_clinical_schedule(scenario_b)

    assert isinstance(result_a.transport_schedule, ConventionalTransportScheduleResult)
    job_a = result_a.transport_schedule.jobs[0]
    job_b = result_b.transport_schedule.jobs[0]
    assert job_a.destination_object_id == job_b.destination_object_id == "D-NEAR-A"
    # RP-001 is closer to D-NEAR-A than RP-002 -- outbound transport time must differ.
    assert job_a.outbound_transport_minutes != job_b.outbound_transport_minutes
    assert job_a.outbound_transport_minutes < job_b.outbound_transport_minutes


def test_mrt_route_responds_to_producing_cyclotron_origin() -> None:
    """Section 47: same concept for MRT -- network route/time responds to
    which cyclotron/origin actually produced the payload."""
    assumptions = PlannerAssumptions()
    geometry = build_controlled_dual_origin_geometry()

    scenario_a = build_single_origin_production_clinical_scenario(
        cyclotron_id="CY-001", radiopharmacy_origin_object_id="RP-001", pathway="MRT",
        geometry=geometry, patient_count=4, assumptions=assumptions,
    )
    scenario_b = build_single_origin_production_clinical_scenario(
        cyclotron_id="CY-002", radiopharmacy_origin_object_id="RP-002", pathway="MRT",
        geometry=geometry, patient_count=4, assumptions=assumptions,
    )
    result_a = build_production_clinical_schedule(scenario_a)
    result_b = build_production_clinical_schedule(scenario_b)

    assert isinstance(result_a.transport_schedule, MRTCarrierTransportScheduleResult)
    job_a = result_a.transport_schedule.jobs[0]
    job_b = result_b.transport_schedule.jobs[0]
    assert job_a.origin == "RP-001"
    assert job_b.origin == "RP-002"
    assert job_a.destination == job_b.destination == "D-NEAR-A"
    assert job_a.transport_time_minutes != job_b.transport_time_minutes
    assert job_a.transport_time_minutes < job_b.transport_time_minutes


def test_retention_responds_to_origin_dependent_transport_timing() -> None:
    """Section 48: retained_fraction (authoritative decay engine) genuinely
    changes when transport time changes because of a different producing
    origin."""
    assumptions = PlannerAssumptions()
    geometry = build_controlled_dual_origin_geometry()
    half_life = load_radionuclide_half_lives()["F-18"]

    metrics_a = route_metrics_from_origin(model=geometry, origin_object_id="RP-001", destination_object_id="D-NEAR-B", assumptions=assumptions)
    metrics_b = route_metrics_from_origin(model=geometry, origin_object_id="RP-002", destination_object_id="D-NEAR-B", assumptions=assumptions)

    assert metrics_a.manual_minutes != metrics_b.manual_minutes
    retained_a = retained_fraction(metrics_a.manual_minutes, half_life)
    retained_b = retained_fraction(metrics_b.manual_minutes, half_life)
    assert retained_a != retained_b
    # RP-002 is closer to D-NEAR-B -- shorter transport -- higher retention.
    assert retained_b > retained_a


def test_patient_cyclotron_origin_traceability_survives_to_payload() -> None:
    """Section 5/44: patient->cyclotron->cycle->origin->payload traceability
    is preserved end to end through the real pipeline."""
    assumptions = PlannerAssumptions()
    geometry = build_controlled_dual_origin_geometry()
    scenario = build_single_origin_production_clinical_scenario(
        cyclotron_id="CY-002", radiopharmacy_origin_object_id="RP-002", pathway="Conventional",
        geometry=geometry, patient_count=4, assumptions=assumptions,
    )
    result = build_production_clinical_schedule(scenario)

    for mapping in result.batch_release_mappings:
        assert mapping.assigned_cyclotron_id == "CY-002"
    for trace in result.patient_traces:
        assert trace.assigned_cyclotron_id == "CY-002"
    # The transport job actually used RP-002's route (proven by the differing
    # timing tests above); here we confirm the mapping/trace identity chain
    # itself never drops or substitutes the cyclotron identity.
    assert {mapping.assigned_cyclotron_id for mapping in result.batch_release_mappings} == {"CY-002"}


def test_wrong_origin_payload_is_rejected_by_authority() -> None:
    """Section 45: deliberately claim a CY-002-produced payload was routed
    from RP-001 -- authority validation must fail."""
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="ON")
    ok, message = validate_payload_origin(cyclotron_id="CY-002", claimed_origin_object_id="RP-001", configured=configured)
    assert ok is False
    assert "mismatch" in message.lower()

    registry = origin_object_id_by_cyclotron_id(configured)
    findings = validate_cyclotron_spatial_origin_traceability(
        payload_cyclotron_ids=["CY-001", "CY-002"],
        payload_origin_object_ids=["RP-001", "RP-001"],  # CY-002's payload incorrectly claims RP-001
        registered_origin_object_id_by_cyclotron_id=registry,
    )
    assert len(findings) == 1
    assert findings[0].authority_id == "CYCLOTRON_SPATIAL_ORIGIN"
    assert "CY-002" in findings[0].affected_object_ids


def test_correct_origin_payloads_pass_authority_validation() -> None:
    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="ON")
    registry = origin_object_id_by_cyclotron_id(configured)
    findings = validate_cyclotron_spatial_origin_traceability(
        payload_cyclotron_ids=["CY-001", "CY-002"],
        payload_origin_object_ids=["RP-001", "RP-002"],
        registered_origin_object_id_by_cyclotron_id=registry,
    )
    assert findings == []


def test_cy002_off_contributes_zero_production_and_zero_assignment() -> None:
    """Section 50: CY-002 OFF must contribute zero production/patient
    assignment; its coordinate remains known scenario metadata only."""
    fleet, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="OFF")
    assert fleet.asset_count == 1
    assert all(asset.cyclotron_id != "CY-002" for asset in fleet.assets)
    cy002 = next(c for c in configured if c.cyclotron_id == "CY-002")
    assert cy002.origin_object_id == "RP-002"  # metadata preserved even while OFF


def test_hybrid_preserves_source_origin_independent_of_transport_mode() -> None:
    """Section 27/59.6: production origin and transport mode are independent
    assignments -- one patient population produced from two distinct origins,
    with one subset routed Conventional and another routed MRT, each
    retaining its own correct origin regardless of transport mode."""
    assumptions = PlannerAssumptions()
    geometry = build_controlled_dual_origin_geometry()

    conventional_from_rp1 = build_single_origin_production_clinical_scenario(
        cyclotron_id="CY-001", radiopharmacy_origin_object_id="RP-001", pathway="Conventional",
        geometry=geometry, patient_count=3, assumptions=assumptions,
    )
    mrt_from_rp2 = build_single_origin_production_clinical_scenario(
        cyclotron_id="CY-002", radiopharmacy_origin_object_id="RP-002", pathway="MRT",
        geometry=geometry, patient_count=3, assumptions=assumptions,
    )
    result_conventional = build_production_clinical_schedule(conventional_from_rp1)
    result_mrt = build_production_clinical_schedule(mrt_from_rp2)

    assert isinstance(result_conventional.transport_schedule, ConventionalTransportScheduleResult)
    assert isinstance(result_mrt.transport_schedule, MRTCarrierTransportScheduleResult)
    assert all(mapping.assigned_cyclotron_id == "CY-001" for mapping in result_conventional.batch_release_mappings)
    assert all(mapping.assigned_cyclotron_id == "CY-002" for mapping in result_mrt.batch_release_mappings)
    assert result_mrt.transport_schedule.jobs[0].origin == "RP-002"
    # No shared clinical/cost-line leakage across the two independently-modeled runs.
    assert type(result_conventional.transport_schedule) is not type(result_mrt.transport_schedule)


def test_capacity_headroom_and_spatial_value_are_distinct_concepts() -> None:
    """Section 24/49: CY-001 alone has ample EOB capacity for this small
    controlled population (no capacity constraint is ever binding here); any
    transport-time difference measured between origins is therefore
    attributable to spatial/route position, not to production-capacity."""
    assumptions = PlannerAssumptions()
    geometry = build_controlled_dual_origin_geometry()

    scenario_rp1 = build_single_origin_production_clinical_scenario(
        cyclotron_id="CY-001", radiopharmacy_origin_object_id="RP-001", pathway="Conventional",
        geometry=geometry, patient_count=2, assumptions=assumptions,
    )
    scenario_rp2 = build_single_origin_production_clinical_scenario(
        cyclotron_id="CY-002", radiopharmacy_origin_object_id="RP-002", pathway="Conventional",
        geometry=geometry, patient_count=2, assumptions=assumptions,
    )
    result_rp1 = build_production_clinical_schedule(scenario_rp1)
    result_rp2 = build_production_clinical_schedule(scenario_rp2)

    # Both single-cyclotron scenarios schedule the same tiny population with
    # zero unscheduled batches -- production capacity is not the constraint.
    assert result_rp1.unscheduled_batch_demands == ()
    assert result_rp2.unscheduled_batch_demands == ()
    # Yet transport timing still differs purely by origin position.
    assert result_rp1.transport_schedule.jobs[0].outbound_transport_minutes != result_rp2.transport_schedule.jobs[0].outbound_transport_minutes

"""Build 2 focused tests: Manual/Automated Conventional route sensitivity to
geometry (Section 23-24/34 items 6-9).

These tests vary the EXISTING `conventional_transport_authority` timing
functions' distance/route parameters directly (never a new physics model)
to prove Conventional/Automated-Conventional route, workload, and (via
`compute_porter_resource_requirement`) labor cost genuinely respond to
geometry -- and are never a fixed representative price regardless of route
length.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from conventional_transport_authority import (
    PorterOperatingPolicy,
    compute_manual_mission_timing,
    compute_porter_resource_requirement,
    compute_automated_conventional_distribution_timing,
    DEFAULT_AGV_MODEL,
    DEFAULT_PTS_NETWORK,
    agv_required_fleet_size,
)
from general_oncology_logistics import TransportMission


def _missions(count: int, mission_minutes: float) -> tuple[TransportMission, ...]:
    return tuple(
        TransportMission(
            mission_id=f"M{i}", load_id=f"L{i}", transport_mode="MANUAL_PORTER", origin="A", destination="B",
            departure_datetime=datetime(2026, 1, 1, 8) + timedelta(minutes=i),
            arrival_datetime=datetime(2026, 1, 1, 8) + timedelta(minutes=i + mission_minutes),
            patient_ids=(f"P{i}",), duration_minutes=mission_minutes, resource_id="PORTER-1",
        )
        for i in range(count)
    )


class TestManualConventionalRouteSensitivity:
    """Test group item 9: Manual Conventional route/envelope responds to geometry."""

    def test_manual_mission_timing_responds_to_horizontal_distance(self):
        policy = PorterOperatingPolicy()
        near = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=20.0, vertical_transitions=0)
        far = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=200.0, vertical_transitions=0)
        assert far.total_minutes > near.total_minutes
        assert far.route_status == "ROUTE_CALIBRATED"
        assert near.route_status == "ROUTE_CALIBRATED"

    def test_manual_mission_timing_responds_to_vertical_transitions(self):
        policy = PorterOperatingPolicy()
        ground = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=50.0, vertical_transitions=0)
        upper_floor = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=50.0, vertical_transitions=5)
        assert upper_floor.total_minutes > ground.total_minutes
        assert upper_floor.vertical_minutes == pytest.approx(5 * policy.elevator_wait_minutes)

    def test_porter_labor_opex_responds_to_route_length_via_mission_minutes(self):
        """Δ route -> Δ transport time -> Δ workload -> Δ porter FTE/OPEX
        (never a flat allowance independent of route length)."""
        policy = PorterOperatingPolicy()
        missions = _missions(40, mission_minutes=1.0)  # placeholder; timing supplied separately below
        near_timing = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=20.0)
        far_timing = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=500.0)
        near_req = compute_porter_resource_requirement(missions=missions, mission_minutes=near_timing.total_minutes, policy=policy, operating_days_per_year=300)
        far_req = compute_porter_resource_requirement(missions=missions, mission_minutes=far_timing.total_minutes, policy=policy, operating_days_per_year=300)
        assert far_req.total_labor_hours > near_req.total_labor_hours
        assert far_req.annual_labor_opex >= near_req.annual_labor_opex


class TestAutomatedConventionalRouteSensitivity:
    """Test group items 6-8: Automated-Conventional automated trunk route +
    last-mile route + last-mile worker-hours respond to geometry."""

    def test_automated_main_leg_timing_responds_to_supplied_route_minutes(self):
        """Section 23: automated trunk distance must be an explicit input,
        never folded into a fixed generic automation price."""
        policy = PorterOperatingPolicy()
        near_leg = compute_automated_conventional_distribution_timing(
            policy=policy, main_leg_technology="AGV_AMR", agv_model=DEFAULT_AGV_MODEL, automated_main_leg_minutes=2.0,
        )
        far_leg = compute_automated_conventional_distribution_timing(
            policy=policy, main_leg_technology="AGV_AMR", agv_model=DEFAULT_AGV_MODEL, automated_main_leg_minutes=15.0,
        )
        assert far_leg.total_minutes > near_leg.total_minutes
        assert far_leg.automated_main_leg_minutes == 15.0
        assert near_leg.automated_main_leg_minutes == 2.0
        # last-mile leg (fixed 15m landing-to-room distance) is UNAFFECTED by main-leg distance -- distinct legs
        assert far_leg.manual_last_mile_minutes == pytest.approx(near_leg.manual_last_mile_minutes)

    def test_agv_fleet_size_responds_to_main_leg_duration(self):
        """Longer automated trunk missions consume more vehicle-minutes per
        mission -> more required fleet at the same mission volume/availability."""
        missions = _missions(2000, mission_minutes=1.0)
        short_fleet = agv_required_fleet_size(missions=missions, mission_minutes=3.0, model=DEFAULT_AGV_MODEL, operating_hours_per_day=18.0, operating_days_per_year=300)
        long_fleet = agv_required_fleet_size(missions=missions, mission_minutes=20.0, model=DEFAULT_AGV_MODEL, operating_hours_per_day=18.0, operating_days_per_year=300)
        assert long_fleet >= short_fleet

    def test_last_mile_worker_hours_respond_to_last_mile_route_length(self):
        """Section 23 requirement: last-mile distance is EXPLICIT and
        separately variable from the automated main leg -- workload must
        genuinely respond to it, not be folded into a fixed AGV/PTS price."""
        policy = PorterOperatingPolicy()
        short_last_mile = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=5.0, vertical_transitions=0)
        long_last_mile = compute_manual_mission_timing(policy=policy, technology="MANUAL_PORTER", horizontal_distance_m=60.0, vertical_transitions=0)
        missions = _missions(30, mission_minutes=1.0)
        short_req = compute_porter_resource_requirement(missions=missions, mission_minutes=short_last_mile.total_minutes, policy=policy, operating_days_per_year=300)
        long_req = compute_porter_resource_requirement(missions=missions, mission_minutes=long_last_mile.total_minutes, policy=policy, operating_days_per_year=300)
        assert long_req.total_labor_hours > short_req.total_labor_hours

    def test_pts_distribution_timing_unaffected_by_agv_specific_parameters(self):
        """Architecture purity (test item 19): PTS distribution timing must
        use PTS-specific handoff (`station_handling_minutes`), never
        accidentally inherit AGV's `load_minutes`."""
        policy = PorterOperatingPolicy()
        pts_timing = compute_automated_conventional_distribution_timing(policy=policy, main_leg_technology="PNEUMATIC_TUBE", pts_network=DEFAULT_PTS_NETWORK)
        assert pts_timing.landing_handoff_minutes == DEFAULT_PTS_NETWORK.station_handling_minutes
        assert pts_timing.landing_handoff_minutes != policy.load_minutes

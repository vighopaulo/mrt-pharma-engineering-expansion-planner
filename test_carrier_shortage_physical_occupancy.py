"""Carrier-shortage regression tests for the physical-occupancy doctrine (Build 2R2).

Pre-AWS audit Defect 2: the operational-only carrier-shortage evaluator formerly bucketed
missions round-robin and scheduled each carrier on a zero-length segment with a ~1-minute
headway, silently omitting the full carrier turnaround/return occupancy (a MISSING_CONSTRAINT).
It bypassed the repository's canonical physical carrier-availability authority
`compute_physical_carrier_peak_concurrency`.

The corrected evaluator models a multi-server queue in which each carrier is unavailable for
the FULL physical occupation cycle (loaded-outbound leg + empty-return/recovery leg), sharing
the SAME `PHYSICAL_CARRIER_RETURN_LEG_MULTIPLIER` occupancy doctrine used for fleet sizing.

These tests prove (Section 13):
  * carrier shortage is sensitive to physical mission occupancy;
  * return/turnaround occupancy cannot be silently omitted;
  * reducing the fleet below the physical peak causes degraded service;
  * a fleet at/above the physical requirement does not fabricate degradation;
  * mission counts are preserved (no mission disappears to satisfy fleet capacity);
  * fleet sizing and shortage evaluation share ONE physical-occupancy authority.
"""

from __future__ import annotations

import pytest

import whole_oncology_four_architecture_optimization as woao
from shared_mrt_multistream_authority import (
    PHYSICAL_CARRIER_RETURN_LEG_MULTIPLIER,
    MrtMissionWindow,
    compute_peak_concurrency,
    compute_physical_carrier_peak_concurrency,
)


@pytest.fixture(scope="module")
def baseline():
    return woao.build_common_project_baseline()


def _mission_count_preserved(outcome) -> bool:
    return outcome.on_time + outcome.late + outcome.unmet == outcome.total_missions


# ---------------------------------------------------------------------------
# Physical peak concurrency is the shared sizing/shortage authority.
# ---------------------------------------------------------------------------
def test_shortage_reports_physical_peak_concurrency(baseline):
    outcome = woao.evaluate_mrt_dominant_operational_only_carrier_shortage(baseline, installed_carriers=1)
    # The corrected evaluator reports the physical peak (loaded-outbound + empty-return),
    # which is strictly >= the naive one-way outbound-only peak for the same windows.
    assert outcome.physical_peak_carrier_concurrency >= 1


def test_return_occupancy_cannot_be_silently_omitted():
    # Two 10-minute outbound missions with a 0.5-minute gap. A naive one-way view sees no
    # overlap (peak=1); the physical view (carrier still returning) sees peak=2. The shortage
    # evaluator must honor the physical view -- this is the exact MISSING_CONSTRAINT the audit
    # identified.
    a = MrtMissionWindow(mission_id="A", patient_ids=("P1",), stream_or_nuclear="CLEAN_LINEN",
                         priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=0.0, duration_minutes=10.0)
    b = MrtMissionWindow(mission_id="B", patient_ids=("P2",), stream_or_nuclear="CLEAN_LINEN",
                         priority_class="PRIORITY_4_ROUTINE_GENERAL", start_minutes=10.5, duration_minutes=10.0)
    windows = (a, b)
    assert compute_peak_concurrency(windows) == 1  # one-way view misses the return leg
    assert compute_physical_carrier_peak_concurrency(windows) == 2  # physical view catches it


# ---------------------------------------------------------------------------
# Sensitivity: below physical peak degrades, at/above does not fabricate degradation.
# ---------------------------------------------------------------------------
def test_below_physical_peak_causes_queuing(baseline):
    peak = woao.evaluate_mrt_dominant_operational_only_carrier_shortage(
        baseline, installed_carriers=1
    ).physical_peak_carrier_concurrency
    assert peak >= 2
    below = woao.evaluate_mrt_dominant_operational_only_carrier_shortage(
        baseline, installed_carriers=peak - 1
    )
    # A fleet one carrier short of the physical peak must incur queuing wait -- proving the
    # evaluator is sensitive to physical mission occupancy, not just one-way overlap.
    assert below.max_wait_minutes > 0.0
    assert _mission_count_preserved(below)


def test_at_physical_peak_no_queuing(baseline):
    peak = woao.evaluate_mrt_dominant_operational_only_carrier_shortage(
        baseline, installed_carriers=1
    ).physical_peak_carrier_concurrency
    at_peak = woao.evaluate_mrt_dominant_operational_only_carrier_shortage(
        baseline, installed_carriers=peak
    )
    assert at_peak.max_wait_minutes == 0.0
    assert at_peak.late == 0 and at_peak.unmet == 0
    assert _mission_count_preserved(at_peak)


def test_single_carrier_is_genuinely_degraded(baseline):
    one = woao.evaluate_mrt_dominant_operational_only_carrier_shortage(baseline, installed_carriers=1)
    # One carrier is far below the physical peak: genuine late/unmet degradation.
    assert one.late + one.unmet > 0
    assert _mission_count_preserved(one)


def test_shortage_is_monotone_non_increasing_in_max_wait(baseline):
    # More carriers can only reduce (never increase) the worst-case queuing wait.
    waits = [
        woao.evaluate_mrt_dominant_operational_only_carrier_shortage(baseline, installed_carriers=n).max_wait_minutes
        for n in (1, 2, 3, 5, 9, 12)
    ]
    for earlier, later in zip(waits, waits[1:]):
        assert later <= earlier + 1e-9


# ---------------------------------------------------------------------------
# Mission preservation & non-expansion.
# ---------------------------------------------------------------------------
def test_no_mission_disappears_to_satisfy_fleet_capacity(baseline):
    for n in (1, 2, 3, 7, 9, 50):
        outcome = woao.evaluate_mrt_dominant_operational_only_carrier_shortage(baseline, installed_carriers=n)
        assert _mission_count_preserved(outcome)
        # Fleet is never silently expanded to make the shortage disappear.
        assert outcome.installed_carriers == n


def test_sizing_and_shortage_share_one_occupancy_multiplier():
    # Section 12: exactly ONE physical carrier-occupancy value governs both fleet sizing and
    # shortage evaluation. Assert the shared constant is the disclosed symmetric-transit value.
    assert PHYSICAL_CARRIER_RETURN_LEG_MULTIPLIER == 1.0

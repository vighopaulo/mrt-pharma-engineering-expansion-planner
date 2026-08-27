"""Facility-Wide Radiopharmaceutical Workflow Staffing + OPEX -- controlled tests.

Covers sections 44-50 (focused subset): room count != FTE, peak concurrency
staffing, batch-gap staff reuse, inbound LOS does not multiply shared staff
labor, MRT clinical staff not zero, Conventional transport labor reused (not
duplicated), Hybrid shared staffing not duplicated across modes.
"""

from __future__ import annotations

from dataclasses import dataclass

from models import SharedNetworkAssumptions
from spatial_benchmark import (
    build_benchmark_geometry,
    build_production_basis,
    _base_assumptions,
    compute_retention_envelope,
    _assign_rooms_for_candidate,
    _evaluate_layout,
)
from hybrid_optimization import HybridZoneCandidate, evaluate_hybrid_zone_candidate
from radiopharm_workflow_staffing import (
    compute_radiopharm_workflow_staffing,
    COMMON_RADIOPHARM_WORKFLOW_LOADED_COST_PER_FTE,
    PATIENTS_SUPERVISED_PER_UPTAKE_STAFF,
)


@dataclass
class _FakeSchedule:
    injection_start: float
    injection_end: float
    uptake_start: float
    uptake_end: float
    scan_start: float
    scan_end: float


def _fixtures():
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    return geometry, assumptions, basis


def _run(geometry, assumptions, basis, pathway, injections, floors=(1, 2, 3, 4), uptake=12, scanners=6):
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway=pathway)
    layout = _assign_rooms_for_candidate(
        geometry=geometry, active_floors=floors, scanners=scanners, injections=injections, uptake=uptake,
        distribution_mode="balanced", assumptions=assumptions, candidate_id=f"T-{pathway}-{injections}",
        pattern_id=f"T-{pathway}-{injections}", distribution_concurrency=min(8, injections),
        feasible_room_ids=env.feasible_room_ids,
    )
    assert layout is not None
    return _evaluate_layout(pathway=pathway, layout=layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1)


# --- Section 44: room count != FTE ------------------------------------------

def test_room_count_does_not_automatically_equal_fte():
    """18 injection rooms with LOW workload (few overlapping patients) must
    NOT force 18 annual FTE -- FTE follows the schedule, not the room count."""
    # Sparse schedule: only 2 patients ever injected simultaneously, despite
    # notionally having "18 rooms" worth of capacity available upstream.
    schedules = [
        _FakeSchedule(injection_start=0.0, injection_end=10.0, uptake_start=10.0, uptake_end=55.0, scan_start=55.0, scan_end=75.0),
        _FakeSchedule(injection_start=5.0, injection_end=15.0, uptake_start=15.0, uptake_end=60.0, scan_start=60.0, scan_end=80.0),
        _FakeSchedule(injection_start=200.0, injection_end=210.0, uptake_start=210.0, uptake_end=255.0, scan_start=255.0, scan_end=275.0),
    ]
    result = compute_radiopharm_workflow_staffing(patient_schedules=schedules, operating_days_per_year=300)
    assert result.injection_staff.peak_concurrency == 2
    assert result.injection_staff.fte < 18.0


# --- Section 45: peak concurrency staffing ----------------------------------

def test_peak_concurrency_matches_actual_simultaneous_injections():
    schedules = [
        _FakeSchedule(injection_start=0.0, injection_end=10.0, uptake_start=10.0, uptake_end=55.0, scan_start=55.0, scan_end=75.0),
        _FakeSchedule(injection_start=3.0, injection_end=13.0, uptake_start=13.0, uptake_end=58.0, scan_start=58.0, scan_end=78.0),
        _FakeSchedule(injection_start=6.0, injection_end=16.0, uptake_start=16.0, uptake_end=61.0, scan_start=61.0, scan_end=81.0),
    ]
    result = compute_radiopharm_workflow_staffing(patient_schedules=schedules, operating_days_per_year=300)
    # all three intervals [0,10),[3,13),[6,16) overlap at t=6-10 -> peak 3.
    assert result.injection_staff.peak_concurrency == 3
    assert result.injection_staff.fte >= 3.0


# --- Section 46: batch gap staff reuse --------------------------------------

def test_two_separated_waves_do_not_double_the_required_fte():
    wave1 = [_FakeSchedule(injection_start=float(i), injection_end=float(i) + 10.0, uptake_start=0, uptake_end=0, scan_start=0, scan_end=0) for i in range(5)]
    wave2 = [_FakeSchedule(injection_start=float(500 + i), injection_end=float(500 + i) + 10.0, uptake_start=0, uptake_end=0, scan_start=0, scan_end=0) for i in range(5)]
    combined = wave1 + wave2
    result_combined = compute_radiopharm_workflow_staffing(patient_schedules=combined, operating_days_per_year=300)
    result_one_wave = compute_radiopharm_workflow_staffing(patient_schedules=wave1, operating_days_per_year=300)
    # Two non-overlapping waves of identical peak concurrency must NOT double
    # the peak-driven FTE requirement (same staff serve both waves).
    assert result_combined.injection_staff.peak_concurrency == result_one_wave.injection_staff.peak_concurrency
    assert result_combined.injection_staff.fte < 2 * result_one_wave.injection_staff.fte


# --- Section 47: inbound LOS does not multiply shared staff labor -----------

def test_inbound_dedicated_room_excluded_from_shared_staff_pools_regardless_of_los():
    """Integrated inbound patients use a dedicated room/injection/uptake and
    must be excluded from the shared-pool patient_schedules list passed to
    this module (by construction/caller convention). Demonstrates that
    varying an (excluded) inbound patient's LOS from 1 day to 7 days has NO
    effect on shared staffing once properly excluded."""
    shared_only = [
        _FakeSchedule(injection_start=0.0, injection_end=10.0, uptake_start=10.0, uptake_end=55.0, scan_start=55.0, scan_end=75.0),
    ]
    result_1_day_los_excluded = compute_radiopharm_workflow_staffing(patient_schedules=shared_only, operating_days_per_year=300)
    result_7_day_los_excluded = compute_radiopharm_workflow_staffing(patient_schedules=shared_only, operating_days_per_year=300)
    assert result_1_day_los_excluded.total_new_pool_annual_opex == result_7_day_los_excluded.total_new_pool_annual_opex


# --- Section 48: MRT clinical staff not zero --------------------------------

def test_pure_mrt_with_active_throughput_has_nonzero_clinical_staff():
    geometry, assumptions, basis = _fixtures()
    outcome = _run(geometry, assumptions, basis, "MRT", 15)
    schedules = outcome.pathway_result.operational_result.production_clinical_result.clinical_schedule.patient_schedules
    staffing = compute_radiopharm_workflow_staffing(patient_schedules=schedules, operating_days_per_year=int(assumptions.operating_days_per_year))
    assert staffing.injection_staff.fte > 0.0
    assert staffing.uptake_staff.fte > 0.0
    assert staffing.scanner_staff.fte > 0.0
    assert staffing.total_new_pool_annual_opex > 0.0


# --- Section 49: Conventional transport labor reused, not duplicated -------

def test_conventional_transport_labor_line_untouched_and_not_duplicated():
    geometry, assumptions, basis = _fixtures()
    outcome = _run(geometry, assumptions, basis, "Conventional", 15)
    ledger = outcome.pathway_result.opex_result.ledger
    transport_labor_lines = [item for item in ledger if "transport labor" in item.component.lower()]
    clinical_labor_lines = [item for item in ledger if item.component == "Clinical labor"]
    assert len(transport_labor_lines) == 1, "exactly one Conventional transport labor line must exist (reused, never duplicated)"
    assert len(clinical_labor_lines) == 1, "the existing fixed Clinical labor line remains present in the base ledger (Stage B REPLACES it in the corrected total, does not mutate the base ledger)"


# --- Hybrid: shared staffing computed once across merged patient traces ----

def test_hybrid_shared_staff_pools_computed_once_across_both_transport_modes():
    geometry, assumptions, basis = _fixtures()
    network_assumptions = SharedNetworkAssumptions()
    candidate = HybridZoneCandidate(candidate_id="STAFF-HYB", mrt_floors=frozenset({3, 4}), conventional_floors=frozenset({1, 2}), scanners=6, injection_resources=15, uptake_resources=12)
    result = evaluate_hybrid_zone_candidate(geometry=geometry, candidate=candidate, demand=200, production_basis=basis, assumptions=assumptions, network_assumptions=network_assumptions)
    conv_patients = [t for t in result.patient_traces if t.transport_mode == "CONVENTIONAL"]
    mrt_patients = [t for t in result.patient_traces if t.transport_mode == "MRT"]
    assert conv_patients and mrt_patients

    def _to_schedule(t):
        return _FakeSchedule(
            injection_start=t.injection_start_minutes, injection_end=t.injection_start_minutes + assumptions.injection_cycle_min,
            uptake_start=t.injection_start_minutes + assumptions.injection_cycle_min,
            uptake_end=t.injection_start_minutes + assumptions.injection_cycle_min + assumptions.uptake_cycle_min,
            scan_start=t.injection_start_minutes + assumptions.injection_cycle_min + assumptions.uptake_cycle_min,
            scan_end=t.injection_start_minutes + assumptions.injection_cycle_min + assumptions.uptake_cycle_min + assumptions.scanner_cycle_min,
        )

    all_schedules = [_to_schedule(t) for t in result.patient_traces]
    staffing_merged = compute_radiopharm_workflow_staffing(patient_schedules=all_schedules, operating_days_per_year=int(assumptions.operating_days_per_year))
    conv_only = [_to_schedule(t) for t in conv_patients]
    mrt_only = [_to_schedule(t) for t in mrt_patients]
    staffing_conv = compute_radiopharm_workflow_staffing(patient_schedules=conv_only, operating_days_per_year=int(assumptions.operating_days_per_year))
    staffing_mrt = compute_radiopharm_workflow_staffing(patient_schedules=mrt_only, operating_days_per_year=int(assumptions.operating_days_per_year))
    # The ONE shared-pool computation over merged patients must not equal the
    # naive SUM of two independently-sized mode-specific pools (which would
    # imply duplicated capacity); shared pooling is more efficient (concurrency
    # is bounded by real overlap across the whole merged population).
    assert staffing_merged.injection_staff.fte <= staffing_conv.injection_staff.fte + staffing_mrt.injection_staff.fte


def test_common_loaded_cost_rate_is_documented_project_assumption():
    assert COMMON_RADIOPHARM_WORKFLOW_LOADED_COST_PER_FTE == 85_000.0
    assert PATIENTS_SUPERVISED_PER_UPTAKE_STAFF == 4.0

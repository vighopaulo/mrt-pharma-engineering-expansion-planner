"""Facility-wide radiopharmaceutical workflow staffing + OPEX (Stage B).

GOVERNING PRINCIPLE: ROOM COUNT != PEAK STAFF COUNT != ANNUAL FTE. Staffing is
derived from actual scheduled task workload (peak concurrency + total active
task-minutes), never from a naive room-count proxy.

AUDIT (section 2-3, evidence from executable configuration): the existing
ledger already carries THREE labor lines, none of which are duplicated here:
  - "Conventional transport labor" (production_clinical_schedule /
    decision_pipeline): conventional_transport_staff_fte =
    layout.distribution_concurrency (already workload/resource-dependent),
    $85,000/FTE/year -- REUSED UNCHANGED as the Conventional transport pool.
  - "MRT support staff" (mrt_support_staff_fte=3.0 fixed, $105,000/FTE) --
    MRT-specific transport/network supervision, distinct function from
    injection/uptake/scanner clinical staffing -- REUSED UNCHANGED, not
    duplicated by the new pools below.
  - "Production labor" (production_staff_fte=2.0 fixed, $110,000/FTE) --
    already a repository production-labor assumption tied to CY-001
    operations (section 15: "if current code already contains production
    labor assumptions: reuse them") -- REUSED UNCHANGED.
  - "Clinical labor" (clinical_staff_fte=4.0 FIXED, $95,000/FTE) -- this is
    the ONE existing line classified INJECTION_STAFF_OPEX_PRESENT_BUT_NOT_
    RESOURCE_DEPENDENT / AMBIGUOUS in the prior audit. This module REPLACES
    it (never adds alongside it, avoiding double-counting per section 30)
    with three workload-derived pools: injection, uptake supervision, and
    scanner staff.

RATE (section 3): no existing common radiopharmaceutical-workflow clinical
labor rate exists that is both workload-derived and common across pools, so
this module introduces COMMON_RADIOPHARM_WORKFLOW_LOADED_COST_PER_FTE =
$85,000/FTE/year as a PROJECT_ASSUMPTION -- deliberately reusing the SAME
rate already used for Conventional transport labor (an equal-pay
simplification per section 3, NOT a claim that nurses/technologists/
transporters are paid identically in reality).

UPTAKE SUPERVISION MODEL (section 12): uptake occupancy (45 min) is NOT
1:1 continuous staff attendance. This module introduces
PATIENTS_SUPERVISED_PER_UPTAKE_STAFF = 4 as an explicit PROJECT_ASSUMPTION,
REQUIRES_LABOR_CALIBRATION (no existing repository supervision ratio found).

PRODUCTIVE HOURS PER FTE (section 25): no existing repository assumption
found; PRODUCTIVE_HOURS_PER_FTE_YEAR = 2000.0 is introduced as a
PROJECT_ASSUMPTION, REQUIRES_LABOR_CALIBRATION.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# PROJECT_ASSUMPTION (section 3): deliberate equal-pay simplification, reuses
# the existing Conventional transport labor rate.
COMMON_RADIOPHARM_WORKFLOW_LOADED_COST_PER_FTE = 85_000.0

# PROJECT_ASSUMPTION, REQUIRES_LABOR_CALIBRATION (section 25): no existing
# repository productive-hours/FTE assumption found.
PRODUCTIVE_HOURS_PER_FTE_YEAR = 2_000.0

# PROJECT_ASSUMPTION, REQUIRES_LABOR_CALIBRATION (section 12): no existing
# repository uptake-supervision ratio found.
PATIENTS_SUPERVISED_PER_UPTAKE_STAFF = 4.0


@dataclass(frozen=True)
class StaffPoolResult:
    pool_name: str
    peak_concurrency: int
    daily_labor_hours: float
    annual_labor_hours: float
    fte: float
    annual_opex: float


@dataclass(frozen=True)
class RadiopharmWorkflowStaffingResult:
    injection_staff: StaffPoolResult
    uptake_staff: StaffPoolResult
    scanner_staff: StaffPoolResult
    total_new_pool_annual_opex: float


def _peak_concurrency(intervals: Sequence[tuple[float, float]]) -> int:
    events: list[tuple[float, int]] = []
    for start, end in intervals:
        if end <= start:
            continue
        events.append((start, 1))
        events.append((end, -1))
    # End events must be processed before start events at an identical
    # timestamp: a resource freed at time t is immediately available for a
    # new occupant starting at t (matches operating_day_scheduler's
    # back-to-back _allocate_earliest semantics) -- otherwise touching,
    # non-overlapping intervals are miscounted as simultaneous.
    events.sort(key=lambda item: (item[0], item[1]))
    active = 0
    peak = 0
    for _, delta in events:
        active += delta
        peak = max(peak, active)
    return peak


def _one_to_one_pool(
    *,
    pool_name: str,
    intervals: Sequence[tuple[float, float]],
    productive_hours_per_fte_year: float,
    operating_days_per_year: int,
    loaded_cost_per_fte: float,
) -> StaffPoolResult:
    """1:1 active-procedure staffing (injection, scanner): one staff member
    per concurrently active procedure; daily labor hours = sum of actual
    task durations (NOT peak concurrency x full operating day), reflecting
    wave-based task reuse across the day (section 17)."""
    peak = _peak_concurrency(intervals)
    daily_labor_hours = sum(max(0.0, end - start) for start, end in intervals) / 60.0
    annual_labor_hours = daily_labor_hours * operating_days_per_year
    # Section 26: FTE must also satisfy peak concurrency/coverage, never a
    # phantom low annual-hours-only value (section 27).
    fte = max(float(peak), annual_labor_hours / productive_hours_per_fte_year)
    return StaffPoolResult(
        pool_name=pool_name,
        peak_concurrency=peak,
        daily_labor_hours=daily_labor_hours,
        annual_labor_hours=annual_labor_hours,
        fte=fte,
        annual_opex=fte * loaded_cost_per_fte,
    )


def _supervision_pool(
    *,
    pool_name: str,
    intervals: Sequence[tuple[float, float]],
    patients_supervised_per_staff: float,
    productive_hours_per_fte_year: float,
    operating_days_per_year: int,
    loaded_cost_per_fte: float,
) -> StaffPoolResult:
    """Non-1:1 supervision staffing (uptake): peak concurrency is the peak
    simultaneous occupied rooms divided by the supervision ratio (rounded up);
    daily labor hours reflect total supervised-patient-minutes divided by the
    same ratio, NOT one dedicated attendant per patient for the full
    occupancy interval (section 12)."""
    import math

    peak_patients = _peak_concurrency(intervals)
    peak_staff = math.ceil(peak_patients / patients_supervised_per_staff) if peak_patients > 0 else 0
    total_patient_minutes = sum(max(0.0, end - start) for start, end in intervals)
    daily_labor_hours = (total_patient_minutes / patients_supervised_per_staff) / 60.0
    annual_labor_hours = daily_labor_hours * operating_days_per_year
    fte = max(float(peak_staff), annual_labor_hours / productive_hours_per_fte_year)
    return StaffPoolResult(
        pool_name=pool_name,
        peak_concurrency=peak_staff,
        daily_labor_hours=daily_labor_hours,
        annual_labor_hours=annual_labor_hours,
        fte=fte,
        annual_opex=fte * loaded_cost_per_fte,
    )


def compute_radiopharm_workflow_staffing(
    *,
    patient_schedules: Sequence[object],
    productive_hours_per_fte_year: float = PRODUCTIVE_HOURS_PER_FTE_YEAR,
    operating_days_per_year: int = 300,
    loaded_cost_per_fte: float = COMMON_RADIOPHARM_WORKFLOW_LOADED_COST_PER_FTE,
    patients_supervised_per_uptake_staff: float = PATIENTS_SUPERVISED_PER_UPTAKE_STAFF,
) -> RadiopharmWorkflowStaffingResult:
    """Derives injection/uptake-supervision/scanner staffing from the ACTUAL
    scheduled patient tasks (production_clinical_schedule.PatientSchedule-like
    objects exposing injection_start/injection_end, uptake_start/uptake_end,
    scan_start/scan_end). Replaces the fixed, non-resource-dependent
    'Clinical labor' ledger line -- never added alongside it."""
    injection_intervals = [(ps.injection_start, ps.injection_end) for ps in patient_schedules]
    uptake_intervals = [(ps.uptake_start, ps.uptake_end) for ps in patient_schedules]
    scanner_intervals = [(ps.scan_start, ps.scan_end) for ps in patient_schedules]

    injection_staff = _one_to_one_pool(
        pool_name="Injection staff", intervals=injection_intervals,
        productive_hours_per_fte_year=productive_hours_per_fte_year,
        operating_days_per_year=operating_days_per_year, loaded_cost_per_fte=loaded_cost_per_fte,
    )
    uptake_staff = _supervision_pool(
        pool_name="Uptake supervision staff", intervals=uptake_intervals,
        patients_supervised_per_staff=patients_supervised_per_uptake_staff,
        productive_hours_per_fte_year=productive_hours_per_fte_year,
        operating_days_per_year=operating_days_per_year, loaded_cost_per_fte=loaded_cost_per_fte,
    )
    scanner_staff = _one_to_one_pool(
        pool_name="Scanner staff", intervals=scanner_intervals,
        productive_hours_per_fte_year=productive_hours_per_fte_year,
        operating_days_per_year=operating_days_per_year, loaded_cost_per_fte=loaded_cost_per_fte,
    )

    return RadiopharmWorkflowStaffingResult(
        injection_staff=injection_staff,
        uptake_staff=uptake_staff,
        scanner_staff=scanner_staff,
        total_new_pool_annual_opex=injection_staff.annual_opex + uptake_staff.annual_opex + scanner_staff.annual_opex,
    )


@dataclass(frozen=True)
class StaffingAwareCandidateResult:
    """Authoritative staffing-integrated result for a PURE pathway
    CandidateOutcome (Conventional/MRT). Section 20: staffing enters OPEX/NPV
    automatically -- no separate manual Stage-B script required. Replaces the
    fixed, non-resource-dependent 'Clinical labor' ledger line (never adds
    alongside it); all other existing ledger lines (Production labor,
    Conventional transport labor, MRT support staff) are reused unchanged."""

    staffing: RadiopharmWorkflowStaffingResult
    removed_fixed_clinical_labor_opex: float
    corrected_annual_opex: float
    corrected_qualified_lifecycle_npv: float


def apply_staffing_authority_to_pure_pathway_outcome(outcome: object, assumptions: object) -> StaffingAwareCandidateResult:
    """`outcome` is a spatial_benchmark.CandidateOutcome; `assumptions` is the
    PlannerAssumptions used to produce it. Computes workload-derived
    injection/uptake/scanner staffing from the REAL clinical schedule already
    produced for this candidate, replaces the existing fixed 'Clinical labor'
    ledger line with it, and recomputes qualified NPV using the same
    discount-rate/analysis-years/operating-days basis already used for
    `outcome` (section 20: integrated automatically, no manual Stage-B script)."""
    pathway_result = outcome.pathway_result
    clinical_schedule = pathway_result.operational_result.production_clinical_result.clinical_schedule

    ledger = pathway_result.opex_result.ledger
    fixed_clinical_labor = sum(item.annual_cost for item in ledger if item.component == "Clinical labor")

    operating_days_per_year = int(assumptions.operating_days_per_year)
    staffing = compute_radiopharm_workflow_staffing(
        patient_schedules=clinical_schedule.patient_schedules,
        operating_days_per_year=operating_days_per_year,
    )

    corrected_annual_opex = outcome.annual_total_opex - fixed_clinical_labor + staffing.total_new_pool_annual_opex

    qualified = outcome.patients_retention_qualified_completed
    qualified_annual_revenue = qualified * assumptions.revenue_per_scan * operating_days_per_year
    discount_rate = assumptions.discount_rate_pct / 100.0
    net_cash_flow = qualified_annual_revenue - corrected_annual_opex
    npv = -outcome.total_capex
    for year in range(1, int(assumptions.analysis_years) + 1):
        npv += net_cash_flow / ((1.0 + discount_rate) ** year)

    return StaffingAwareCandidateResult(
        staffing=staffing,
        removed_fixed_clinical_labor_opex=fixed_clinical_labor,
        corrected_annual_opex=corrected_annual_opex,
        corrected_qualified_lifecycle_npv=npv,
    )

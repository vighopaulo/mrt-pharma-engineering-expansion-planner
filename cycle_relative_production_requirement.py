"""Cycle-relative patient EOB requirement derivation.

AUTHORITATIVE production sizing must know which physical production cycle
supplies each patient before computing that patient's required EOB activity.
This module replaces the previous "common-early-EOB" heuristic (which summed
every patient's decay compensation against a single provisional EOB reference
time before any cycle assignment existed) with a deterministic, bounded
patient-to-cycle assignment/convergence process.

Governing formula for patient p supplied by candidate cycle c:

    A_EOB,p,c = A_admin,p / R(EOB_c -> administration_p)

This module reuses the repository's authoritative decay functions
(`retained_fraction`, `required_upstream_activity`) and does not implement an
independent half-life model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from multi_isotope_decay import required_upstream_activity, retained_fraction

_EPS = 1e-6

ConvergenceStatus = Literal["CONVERGED", "PRODUCTION_REQUIREMENT_DID_NOT_CONVERGE"]
CycleStatus = Literal["SCHEDULED_FEASIBLE", "SCHEDULED_ACTIVITY_INFEASIBLE"]


@dataclass(frozen=True)
class CandidateProductionCycle:
    cycle_id: str
    cyclotron_id: str
    radionuclide: str
    start_minutes: float
    eob_minutes: float
    release_minutes: float
    calibrated_eob_capacity_mbq: float


@dataclass(frozen=True)
class PatientCycleAssignment:
    patient_id: str
    cycle_id: str | None
    administration_time_minutes: float
    prescribed_activity_mbq: float
    elapsed_eob_to_administration_minutes: float | None
    retained_fraction_at_administration: float | None
    required_eob_activity_mbq: float | None
    feasible: bool
    infeasibility_reason: str | None


@dataclass(frozen=True)
class CandidateCycleUsageSummary:
    cycle_id: str
    cyclotron_id: str
    radionuclide: str
    start_minutes: float
    eob_minutes: float
    release_minutes: float
    patient_ids: tuple[str, ...]
    required_eob_activity_mbq: float
    available_eob_capacity_mbq: float
    unused_eob_capacity_mbq: float
    earliest_administration_minutes: float | None
    latest_administration_minutes: float | None
    status: CycleStatus


@dataclass(frozen=True)
class CycleRelativeRequirementResult:
    radionuclide: str
    half_life_minutes: float
    assignments: tuple[PatientCycleAssignment, ...]
    cycle_usages: tuple[CandidateCycleUsageSummary, ...]
    required_cycle_count: int
    unassigned_patient_ids: tuple[str, ...]
    total_required_eob_activity_mbq: float
    convergence_status: ConvergenceStatus
    iterations_used: int


def generate_candidate_production_cycles(
    *,
    cyclotron_id: str,
    radionuclide: str,
    cycle_minutes: float,
    calibrated_eob_capacity_mbq: float,
    release_processing_minutes: float,
    production_start_time_minutes: float,
    production_horizon_minutes: float,
) -> tuple[CandidateProductionCycle, ...]:
    """Generate the physically schedulable candidate cycles for one cyclotron/radionuclide.

    Cycles are stepped back-to-back (single stream) from production_start_time_minutes
    and truncated at production_horizon_minutes. This mirrors the horizon math already
    used by `schedule_cyclotron_production_windows`, but generation here is independent
    of any particular patient/batch count.
    """
    if cycle_minutes <= 0.0:
        raise ValueError("cycle_minutes must be greater than zero")
    if calibrated_eob_capacity_mbq <= 0.0:
        raise ValueError("calibrated_eob_capacity_mbq must be greater than zero")

    cycles: list[CandidateProductionCycle] = []
    start = float(production_start_time_minutes)
    index = 1
    while True:
        eob = start + float(cycle_minutes)
        if eob > float(production_horizon_minutes) + _EPS:
            break
        release = eob + float(release_processing_minutes)
        cycles.append(
            CandidateProductionCycle(
                cycle_id=f"{cyclotron_id}:{radionuclide}:{index}",
                cyclotron_id=cyclotron_id,
                radionuclide=radionuclide,
                start_minutes=start,
                eob_minutes=eob,
                release_minutes=release,
                calibrated_eob_capacity_mbq=float(calibrated_eob_capacity_mbq),
            )
        )
        start = eob
        index += 1
    return tuple(cycles)


def _required_eob_for_cycle(
    prescribed_activity_mbq: float,
    administration_time_minutes: float,
    cycle: CandidateProductionCycle,
    half_life_minutes: float,
) -> tuple[float, float, float]:
    elapsed = max(0.0, administration_time_minutes - cycle.eob_minutes)
    retained = retained_fraction(elapsed, half_life_minutes)
    retained = max(retained, 1e-12)
    required = required_upstream_activity(prescribed_activity_mbq, retained)
    return elapsed, retained, required


def derive_cycle_relative_requirement(
    *,
    radionuclide: str,
    half_life_minutes: float,
    patient_ids: Sequence[str],
    prescribed_activity_mbq_by_patient_id: Mapping[str, float],
    administration_time_minutes_by_patient_id: Mapping[str, float],
    candidate_cycles: Sequence[CandidateProductionCycle],
    max_iterations: int = 64,
) -> CycleRelativeRequirementResult:
    """Assign patients to the freshest feasible candidate cycle and enforce per-cycle capacity.

    Deterministic ordering: patients are processed by (administration_time, patient_id).
    A patient may only use a cycle whose release occurs at or before that patient's
    required administration time (early patients cannot use a future release). Among
    eligible cycles, the freshest (latest EOB) is preferred to minimize decay
    compensation. When a cycle's assigned aggregate required EOB activity exceeds its
    calibrated capacity, the earliest-administered patient in that cycle (the patient
    with the most timing slack) is reassigned to its next-freshest eligible cycle with
    spare capacity. The refinement loop is bounded by max_iterations.
    """
    ordered_cycles = sorted(candidate_cycles, key=lambda cycle: cycle.eob_minutes)
    ordered_patient_ids = sorted(
        patient_ids,
        key=lambda patient_id: (administration_time_minutes_by_patient_id[patient_id], patient_id),
    )

    assigned_cycle_by_patient: dict[str, str | None] = {}
    required_by_patient: dict[str, float] = {}
    elapsed_by_patient: dict[str, float] = {}
    retained_by_patient: dict[str, float] = {}
    reason_by_patient: dict[str, str | None] = {}

    cycles_by_id = {cycle.cycle_id: cycle for cycle in ordered_cycles}

    for patient_id in ordered_patient_ids:
        admin_time = administration_time_minutes_by_patient_id[patient_id]
        prescribed = prescribed_activity_mbq_by_patient_id[patient_id]
        eligible = [cycle for cycle in ordered_cycles if cycle.release_minutes <= admin_time + _EPS]
        if not eligible:
            assigned_cycle_by_patient[patient_id] = None
            reason_by_patient[patient_id] = (
                "UNASSIGNED_PATIENT_PRODUCTION_DEMAND: no candidate production cycle releases "
                "early enough to meet this patient's required administration time"
            )
            continue
        chosen = max(eligible, key=lambda cycle: cycle.eob_minutes)
        elapsed, retained, required = _required_eob_for_cycle(prescribed, admin_time, chosen, half_life_minutes)
        assigned_cycle_by_patient[patient_id] = chosen.cycle_id
        required_by_patient[patient_id] = required
        elapsed_by_patient[patient_id] = elapsed
        retained_by_patient[patient_id] = retained
        reason_by_patient[patient_id] = None

    iterations_used = 0
    converged = False
    while iterations_used < max_iterations:
        iterations_used += 1
        totals: dict[str, float] = {}
        for patient_id, cycle_id in assigned_cycle_by_patient.items():
            if cycle_id is None:
                continue
            totals[cycle_id] = totals.get(cycle_id, 0.0) + required_by_patient[patient_id]

        overloaded = [
            cycle_id
            for cycle_id, total in totals.items()
            if total > cycles_by_id[cycle_id].calibrated_eob_capacity_mbq + _EPS
        ]
        if not overloaded:
            converged = True
            break

        overloaded.sort(
            key=lambda cycle_id: (
                -(totals[cycle_id] - cycles_by_id[cycle_id].calibrated_eob_capacity_mbq),
                cycle_id,
            )
        )
        target_cycle_id = overloaded[0]

        members = sorted(
            (patient_id for patient_id, cycle_id in assigned_cycle_by_patient.items() if cycle_id == target_cycle_id),
            key=lambda patient_id: (administration_time_minutes_by_patient_id[patient_id], patient_id),
        )

        moved = False
        for patient_id in members:
            admin_time = administration_time_minutes_by_patient_id[patient_id]
            prescribed = prescribed_activity_mbq_by_patient_id[patient_id]
            alternatives = [
                cycle
                for cycle in ordered_cycles
                if cycle.cycle_id != target_cycle_id and cycle.release_minutes <= admin_time + _EPS
            ]
            best_alt: tuple[CandidateProductionCycle, float, float, float] | None = None
            for alt in alternatives:
                elapsed, retained, required = _required_eob_for_cycle(prescribed, admin_time, alt, half_life_minutes)
                existing_total = totals.get(alt.cycle_id, 0.0)
                if existing_total + required <= alt.calibrated_eob_capacity_mbq + _EPS:
                    if best_alt is None or alt.eob_minutes > best_alt[0].eob_minutes:
                        best_alt = (alt, elapsed, retained, required)
            if best_alt is None:
                continue
            alt, elapsed, retained, required = best_alt
            assigned_cycle_by_patient[patient_id] = alt.cycle_id
            required_by_patient[patient_id] = required
            elapsed_by_patient[patient_id] = elapsed
            retained_by_patient[patient_id] = retained
            moved = True
            break

        if not moved:
            break

    if not converged:
        totals = {}
        for patient_id, cycle_id in assigned_cycle_by_patient.items():
            if cycle_id is None:
                continue
            totals[cycle_id] = totals.get(cycle_id, 0.0) + required_by_patient[patient_id]
        convergence_status: ConvergenceStatus = "PRODUCTION_REQUIREMENT_DID_NOT_CONVERGE"
    else:
        convergence_status = "CONVERGED"

    used_cycle_ids = sorted(
        {cycle_id for cycle_id in assigned_cycle_by_patient.values() if cycle_id is not None},
        key=lambda cycle_id: cycles_by_id[cycle_id].eob_minutes,
    )

    cycle_usages: list[CandidateCycleUsageSummary] = []
    for cycle_id in used_cycle_ids:
        cycle = cycles_by_id[cycle_id]
        members = [patient_id for patient_id, assigned in assigned_cycle_by_patient.items() if assigned == cycle_id]
        member_admin_times = [administration_time_minutes_by_patient_id[patient_id] for patient_id in members]
        required_total = sum(required_by_patient[patient_id] for patient_id in members)
        status: CycleStatus = (
            "SCHEDULED_FEASIBLE"
            if required_total <= cycle.calibrated_eob_capacity_mbq + _EPS
            else "SCHEDULED_ACTIVITY_INFEASIBLE"
        )
        cycle_usages.append(
            CandidateCycleUsageSummary(
                cycle_id=cycle.cycle_id,
                cyclotron_id=cycle.cyclotron_id,
                radionuclide=cycle.radionuclide,
                start_minutes=cycle.start_minutes,
                eob_minutes=cycle.eob_minutes,
                release_minutes=cycle.release_minutes,
                patient_ids=tuple(sorted(members)),
                required_eob_activity_mbq=required_total,
                available_eob_capacity_mbq=cycle.calibrated_eob_capacity_mbq,
                unused_eob_capacity_mbq=max(0.0, cycle.calibrated_eob_capacity_mbq - required_total),
                earliest_administration_minutes=min(member_admin_times) if member_admin_times else None,
                latest_administration_minutes=max(member_admin_times) if member_admin_times else None,
                status=status,
            )
        )

    assignments: list[PatientCycleAssignment] = []
    for patient_id in ordered_patient_ids:
        cycle_id = assigned_cycle_by_patient.get(patient_id)
        assignments.append(
            PatientCycleAssignment(
                patient_id=patient_id,
                cycle_id=cycle_id,
                administration_time_minutes=administration_time_minutes_by_patient_id[patient_id],
                prescribed_activity_mbq=prescribed_activity_mbq_by_patient_id[patient_id],
                elapsed_eob_to_administration_minutes=elapsed_by_patient.get(patient_id),
                retained_fraction_at_administration=retained_by_patient.get(patient_id),
                required_eob_activity_mbq=required_by_patient.get(patient_id),
                feasible=cycle_id is not None,
                infeasibility_reason=reason_by_patient.get(patient_id),
            )
        )

    unassigned_patient_ids = tuple(
        patient_id for patient_id, cycle_id in assigned_cycle_by_patient.items() if cycle_id is None
    )
    total_required_eob_activity_mbq = sum(usage.required_eob_activity_mbq for usage in cycle_usages)

    return CycleRelativeRequirementResult(
        radionuclide=radionuclide,
        half_life_minutes=half_life_minutes,
        assignments=tuple(sorted(assignments, key=lambda assignment: (assignment.administration_time_minutes, assignment.patient_id))),
        cycle_usages=tuple(cycle_usages),
        required_cycle_count=len(cycle_usages),
        unassigned_patient_ids=unassigned_patient_ids,
        total_required_eob_activity_mbq=float(total_required_eob_activity_mbq),
        convergence_status=convergence_status,
        iterations_used=iterations_used,
    )

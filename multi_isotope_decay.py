from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean
from typing import Literal, Mapping, Sequence

from diagnostics import load_radionuclide_half_lives
from patient_radionuclide_demand import PatientRadionuclideDemand
from production_clinical_schedule import ProductionClinicalPatientTrace


Pathway = Literal["Conventional", "MRT"]


def retained_fraction(elapsed_minutes: float, half_life_minutes: float) -> float:
    if half_life_minutes <= 0.0:
        raise ValueError("half_life_minutes must be positive")
    if elapsed_minutes < 0.0:
        raise ValueError("elapsed_minutes must be non-negative")
    return 2.0 ** (-float(elapsed_minutes) / float(half_life_minutes))


def activity_after_decay(initial_activity_mbq: float, elapsed_minutes: float, half_life_minutes: float) -> float:
    activity = float(initial_activity_mbq)
    if activity < 0.0:
        raise ValueError("initial_activity_mbq must be non-negative")
    return activity * retained_fraction(elapsed_minutes, half_life_minutes)


def required_upstream_activity(required_administration_activity_mbq: float, retained_fraction_at_administration: float) -> float:
    required = float(required_administration_activity_mbq)
    if required < 0.0:
        raise ValueError("required_administration_activity_mbq must be non-negative")
    if retained_fraction_at_administration <= 0.0:
        raise ValueError("retained_fraction_at_administration must be positive")
    return required / retained_fraction_at_administration


@dataclass(frozen=True)
class PatientDecayTrace:
    patient_id: str
    pathway: Pathway
    radionuclide: str
    half_life_minutes: float
    prescribed_activity_mbq: float
    batch_id: int
    production_window_id: int
    production_window_start_time_minutes: float
    production_window_end_time_minutes: float
    release_time_minutes: float
    distribution_start_minutes: float
    distribution_end_minutes: float
    injection_start_minutes: float
    injection_end_minutes: float
    scan_start_minutes: float
    scan_end_minutes: float
    elapsed_eob_to_release_minutes: float
    elapsed_release_to_injection_minutes: float
    elapsed_eob_to_injection_minutes: float
    activity_at_eob_mbq: float
    activity_at_release_mbq: float
    activity_at_injection_mbq: float
    physical_decay_loss_before_administration_mbq: float
    unmet_prescribed_activity_mbq: float
    retained_fraction_at_administration: float
    activity_lost_percentage_before_administration: float
    required_upstream_activity_for_prescribed_mbq: float
    required_activity_at_release_mbq: float
    theoretical_required_activity_at_eob_mbq: float
    theoretical_required_activity_at_release_mbq: float
    theoretical_compensation_factor: float
    decay_feasible: bool
    decay_infeasibility_reason: str | None
    potential_shortfall_mbq_if_no_upstream_adjustment: float
    dose_sufficient_if_no_upstream_adjustment: bool
    completed_within_operating_day: bool


@dataclass(frozen=True)
class BatchDecaySummary:
    pathway: Pathway
    radionuclide: str
    batch_id: int
    production_window_id: int
    patient_count: int
    patient_ids: tuple[str, ...]
    production_window_start_time_minutes: float
    production_window_end_time_minutes: float
    release_time_minutes: float
    total_prescribed_activity_mbq: float
    total_prescribed_activity_mbq_successfully_served: float
    total_activity_at_eob_mbq: float
    total_activity_at_release_mbq: float
    total_activity_at_injection_mbq: float
    total_physical_decay_loss_before_administration_mbq: float
    total_unmet_prescribed_activity_mbq: float
    average_retained_fraction: float
    minimum_retained_fraction: float
    maximum_retained_fraction: float
    feasible_patient_count: int
    infeasible_patient_count: int
    total_potential_shortfall_mbq_if_no_upstream_adjustment: float


@dataclass(frozen=True)
class IsotopeDecaySummary:
    pathway: Pathway
    radionuclide: str
    half_life_minutes: float
    patient_count: int
    completed_patient_count: int
    feasible_completed_patient_count: int
    total_prescribed_activity_mbq: float
    total_prescribed_activity_mbq_successfully_served: float
    total_activity_at_eob_mbq: float
    total_activity_at_release_mbq: float
    total_activity_at_injection_mbq: float
    total_physical_decay_loss_before_administration_mbq: float
    total_unmet_prescribed_activity_mbq: float
    mean_retained_fraction: float
    min_retained_fraction: float
    max_retained_fraction: float
    feasible_patient_count: int
    infeasible_patient_count: int
    total_potential_shortfall_mbq_if_no_upstream_adjustment: float


@dataclass(frozen=True)
class PathwayDecaySummary:
    pathway: Pathway
    total_patients: int
    completed_patients: int
    feasible_scheduled_patients: int
    feasible_completed_patients: int
    effective_completion_percentage: float
    total_prescribed_activity_mbq_by_isotope: Mapping[str, float]
    total_prescribed_activity_mbq_successfully_served_by_isotope: Mapping[str, float]
    total_required_activity_at_eob_mbq_by_isotope: Mapping[str, float]
    total_required_activity_at_release_mbq_by_isotope: Mapping[str, float]
    total_activity_at_injection_mbq_by_isotope: Mapping[str, float]
    total_physical_decay_loss_mbq_by_isotope: Mapping[str, float]
    total_unmet_prescribed_activity_mbq_by_isotope: Mapping[str, float]
    total_decay_loss_mbq_by_isotope: Mapping[str, float]
    overall_physical_decay_loss_mbq: float
    overall_unmet_prescribed_activity_mbq: float
    overall_decay_loss_mbq: float
    mean_retained_fraction: float
    decay_loss_mbq_per_completed_patient: float
    physical_decay_loss_mbq_per_feasible_completed_patient: float
    required_eob_mbq_per_feasible_completed_patient: float
    total_potential_shortfall_mbq_if_no_upstream_adjustment: float
    dose_sufficient_patient_count_if_no_upstream_adjustment: int
    dose_insufficient_patient_count_if_no_upstream_adjustment: int
    decay_feasible_patient_count: int
    decay_infeasible_patient_count: int
    decay_infeasible_by_isotope: Mapping[str, int]
    isotope_summaries: tuple[IsotopeDecaySummary, ...]
    batch_summaries: tuple[BatchDecaySummary, ...]
    patient_traces: tuple[PatientDecayTrace, ...]


def _half_life_lookup() -> dict[str, float]:
    return load_radionuclide_half_lives()


def evaluate_pathway_decay(
    *,
    pathway: Pathway,
    generated_patients: Sequence[PatientRadionuclideDemand],
    patient_traces: Sequence[ProductionClinicalPatientTrace],
    min_retained_fraction_for_feasibility: float = 0.0,
    max_decay_compensation_factor: float | None = None,
) -> PathwayDecaySummary:
    minimum_retained = float(min_retained_fraction_for_feasibility)
    if minimum_retained < 0.0 or minimum_retained > 1.0:
        raise ValueError("min_retained_fraction_for_feasibility must be within [0.0, 1.0]")

    max_compensation = None if max_decay_compensation_factor is None else float(max_decay_compensation_factor)
    if max_compensation is not None and max_compensation < 1.0:
        raise ValueError("max_decay_compensation_factor must be at least 1.0 when provided")

    if max_compensation is not None:
        minimum_retained = max(minimum_retained, 1.0 / max_compensation)

    half_life_lookup = _half_life_lookup()
    trace_by_patient_id = {trace.patient_id: trace for trace in patient_traces}

    patient_decay_traces: list[PatientDecayTrace] = []
    for patient in generated_patients:
        trace = trace_by_patient_id.get(patient.patient_id)
        if trace is None:
            raise ValueError(f"Missing clinical trace for patient {patient.patient_id}")

        radionuclide = patient.radionuclide
        if radionuclide not in half_life_lookup:
            raise ValueError(f"Missing radionuclide half-life physics for {radionuclide}")

        half_life = float(half_life_lookup[radionuclide])
        elapsed_eob_to_release = max(0.0, trace.batch_release_time_minutes - trace.production_window_end_time_minutes)
        elapsed_release_to_injection = max(0.0, trace.injection_start - trace.batch_release_time_minutes)
        elapsed_total = elapsed_eob_to_release + elapsed_release_to_injection

        prescribed = float(patient.prescribed_activity_mbq)
        retained = retained_fraction(elapsed_total, half_life)
        retained = min(1.0, max(0.0, retained))
        no_adjustment_admin_activity = activity_after_decay(prescribed, elapsed_total, half_life)
        shortfall = max(0.0, prescribed - no_adjustment_admin_activity)
        theoretical_compensation_factor = float("inf") if retained <= 0.0 else 1.0 / retained
        theoretical_required_eob = required_upstream_activity(prescribed, retained) if retained > 0.0 else float("inf")
        theoretical_required_release = activity_after_decay(theoretical_required_eob, elapsed_eob_to_release, half_life) if math.isfinite(theoretical_required_eob) else float("inf")

        feasible = retained >= minimum_retained
        infeasibility_reason = None
        if not feasible:
            infeasibility_reason = (
                f"Retained fraction {retained:.6f} below feasibility minimum {minimum_retained:.6f}; "
                f"required compensation factor {theoretical_compensation_factor:.2f} exceeds configured guard"
            )

        if feasible:
            required_upstream = theoretical_required_eob
            activity_at_eob = required_upstream
            activity_at_release = activity_after_decay(activity_at_eob, elapsed_eob_to_release, half_life)
            activity_at_injection = prescribed
            physical_decay_loss = max(0.0, activity_at_eob - activity_at_injection)
            unmet_prescribed_activity = 0.0
        else:
            required_upstream = 0.0
            activity_at_eob = 0.0
            activity_at_release = 0.0
            activity_at_injection = no_adjustment_admin_activity
            physical_decay_loss = 0.0
            unmet_prescribed_activity = max(0.0, prescribed - activity_at_injection)

        loss_pct = 100.0 * physical_decay_loss / activity_at_eob if math.isfinite(activity_at_eob) and activity_at_eob > 0.0 else 0.0

        patient_decay_traces.append(
            PatientDecayTrace(
                patient_id=patient.patient_id,
                pathway=pathway,
                radionuclide=radionuclide,
                half_life_minutes=half_life,
                prescribed_activity_mbq=prescribed,
                batch_id=trace.batch_id,
                production_window_id=trace.production_window_id,
                production_window_start_time_minutes=trace.production_window_start_time_minutes,
                production_window_end_time_minutes=trace.production_window_end_time_minutes,
                release_time_minutes=trace.batch_release_time_minutes,
                distribution_start_minutes=trace.distribution_start,
                distribution_end_minutes=trace.distribution_end,
                injection_start_minutes=trace.injection_start,
                injection_end_minutes=trace.injection_end,
                scan_start_minutes=trace.scan_start,
                scan_end_minutes=trace.scan_end,
                elapsed_eob_to_release_minutes=elapsed_eob_to_release,
                elapsed_release_to_injection_minutes=elapsed_release_to_injection,
                elapsed_eob_to_injection_minutes=elapsed_total,
                activity_at_eob_mbq=activity_at_eob,
                activity_at_release_mbq=activity_at_release,
                activity_at_injection_mbq=activity_at_injection,
                physical_decay_loss_before_administration_mbq=physical_decay_loss,
                unmet_prescribed_activity_mbq=unmet_prescribed_activity,
                retained_fraction_at_administration=retained,
                activity_lost_percentage_before_administration=loss_pct,
                required_upstream_activity_for_prescribed_mbq=required_upstream,
                required_activity_at_release_mbq=activity_at_release,
                theoretical_required_activity_at_eob_mbq=theoretical_required_eob,
                theoretical_required_activity_at_release_mbq=theoretical_required_release,
                theoretical_compensation_factor=theoretical_compensation_factor,
                decay_feasible=feasible,
                decay_infeasibility_reason=infeasibility_reason,
                potential_shortfall_mbq_if_no_upstream_adjustment=shortfall,
                dose_sufficient_if_no_upstream_adjustment=shortfall <= 1e-9,
                completed_within_operating_day=trace.completed_within_operating_day,
            )
        )

    by_batch: dict[tuple[int, str], list[PatientDecayTrace]] = {}
    by_isotope: dict[str, list[PatientDecayTrace]] = {}
    for trace in patient_decay_traces:
        by_batch.setdefault((trace.batch_id, trace.radionuclide), []).append(trace)
        by_isotope.setdefault(trace.radionuclide, []).append(trace)

    batch_summaries: list[BatchDecaySummary] = []
    for (batch_id, radionuclide), traces in sorted(by_batch.items(), key=lambda item: (item[0][0], item[0][1])):
        retained_values = [trace.retained_fraction_at_administration for trace in traces]
        batch_summaries.append(
            BatchDecaySummary(
                pathway=pathway,
                radionuclide=radionuclide,
                batch_id=batch_id,
                production_window_id=traces[0].production_window_id,
                patient_count=len(traces),
                patient_ids=tuple(trace.patient_id for trace in traces),
                production_window_start_time_minutes=traces[0].production_window_start_time_minutes,
                production_window_end_time_minutes=traces[0].production_window_end_time_minutes,
                release_time_minutes=traces[0].release_time_minutes,
                total_prescribed_activity_mbq=sum(trace.prescribed_activity_mbq for trace in traces),
                total_prescribed_activity_mbq_successfully_served=sum(trace.prescribed_activity_mbq for trace in traces if trace.decay_feasible),
                total_activity_at_eob_mbq=sum(trace.activity_at_eob_mbq for trace in traces if math.isfinite(trace.activity_at_eob_mbq)),
                total_activity_at_release_mbq=sum(trace.activity_at_release_mbq for trace in traces if math.isfinite(trace.activity_at_release_mbq)),
                total_activity_at_injection_mbq=sum(trace.activity_at_injection_mbq for trace in traces),
                total_physical_decay_loss_before_administration_mbq=sum(trace.physical_decay_loss_before_administration_mbq for trace in traces),
                total_unmet_prescribed_activity_mbq=sum(trace.unmet_prescribed_activity_mbq for trace in traces),
                average_retained_fraction=mean(retained_values) if retained_values else 0.0,
                minimum_retained_fraction=min(retained_values) if retained_values else 0.0,
                maximum_retained_fraction=max(retained_values) if retained_values else 0.0,
                feasible_patient_count=sum(1 for trace in traces if trace.decay_feasible),
                infeasible_patient_count=sum(1 for trace in traces if not trace.decay_feasible),
                total_potential_shortfall_mbq_if_no_upstream_adjustment=sum(trace.potential_shortfall_mbq_if_no_upstream_adjustment for trace in traces),
            )
        )

    isotope_summaries: list[IsotopeDecaySummary] = []
    for radionuclide, traces in sorted(by_isotope.items()):
        retained_values = [trace.retained_fraction_at_administration for trace in traces]
        isotope_summaries.append(
            IsotopeDecaySummary(
                pathway=pathway,
                radionuclide=radionuclide,
                half_life_minutes=traces[0].half_life_minutes,
                patient_count=len(traces),
                completed_patient_count=sum(1 for trace in traces if trace.completed_within_operating_day),
                feasible_completed_patient_count=sum(1 for trace in traces if trace.completed_within_operating_day and trace.decay_feasible),
                total_prescribed_activity_mbq=sum(trace.prescribed_activity_mbq for trace in traces),
                total_prescribed_activity_mbq_successfully_served=sum(trace.prescribed_activity_mbq for trace in traces if trace.decay_feasible),
                total_activity_at_eob_mbq=sum(trace.activity_at_eob_mbq for trace in traces if math.isfinite(trace.activity_at_eob_mbq)),
                total_activity_at_release_mbq=sum(trace.activity_at_release_mbq for trace in traces if math.isfinite(trace.activity_at_release_mbq)),
                total_activity_at_injection_mbq=sum(trace.activity_at_injection_mbq for trace in traces),
                total_physical_decay_loss_before_administration_mbq=sum(trace.physical_decay_loss_before_administration_mbq for trace in traces),
                total_unmet_prescribed_activity_mbq=sum(trace.unmet_prescribed_activity_mbq for trace in traces),
                mean_retained_fraction=mean(retained_values) if retained_values else 0.0,
                min_retained_fraction=min(retained_values) if retained_values else 0.0,
                max_retained_fraction=max(retained_values) if retained_values else 0.0,
                feasible_patient_count=sum(1 for trace in traces if trace.decay_feasible),
                infeasible_patient_count=sum(1 for trace in traces if not trace.decay_feasible),
                total_potential_shortfall_mbq_if_no_upstream_adjustment=sum(trace.potential_shortfall_mbq_if_no_upstream_adjustment for trace in traces),
            )
        )

    totals_prescribed = {summary.radionuclide: summary.total_prescribed_activity_mbq for summary in isotope_summaries}
    totals_prescribed_served = {summary.radionuclide: summary.total_prescribed_activity_mbq_successfully_served for summary in isotope_summaries}
    totals_required_eob = {summary.radionuclide: summary.total_activity_at_eob_mbq for summary in isotope_summaries}
    totals_required_release = {summary.radionuclide: summary.total_activity_at_release_mbq for summary in isotope_summaries}
    totals_at_injection = {summary.radionuclide: summary.total_activity_at_injection_mbq for summary in isotope_summaries}
    totals_physical_loss = {summary.radionuclide: summary.total_physical_decay_loss_before_administration_mbq for summary in isotope_summaries}
    totals_unmet = {summary.radionuclide: summary.total_unmet_prescribed_activity_mbq for summary in isotope_summaries}
    retained_values = [trace.retained_fraction_at_administration for trace in patient_decay_traces]
    completed_count = sum(1 for trace in patient_decay_traces if trace.completed_within_operating_day)
    feasible_scheduled_count = sum(1 for trace in patient_decay_traces if trace.decay_feasible)
    feasible_completed_count = sum(1 for trace in patient_decay_traces if trace.decay_feasible and trace.completed_within_operating_day)
    overall_physical_loss = sum(totals_physical_loss.values())
    overall_unmet = sum(totals_unmet.values())
    overall_loss = overall_physical_loss + overall_unmet
    infeasible_by_isotope: dict[str, int] = {}
    for trace in patient_decay_traces:
        if not trace.decay_feasible:
            infeasible_by_isotope[trace.radionuclide] = infeasible_by_isotope.get(trace.radionuclide, 0) + 1

    return PathwayDecaySummary(
        pathway=pathway,
        total_patients=len(patient_decay_traces),
        completed_patients=completed_count,
        feasible_scheduled_patients=feasible_scheduled_count,
        feasible_completed_patients=feasible_completed_count,
        effective_completion_percentage=(100.0 * feasible_completed_count / len(patient_decay_traces)) if patient_decay_traces else 0.0,
        total_prescribed_activity_mbq_by_isotope=totals_prescribed,
        total_prescribed_activity_mbq_successfully_served_by_isotope=totals_prescribed_served,
        total_required_activity_at_eob_mbq_by_isotope=totals_required_eob,
        total_required_activity_at_release_mbq_by_isotope=totals_required_release,
        total_activity_at_injection_mbq_by_isotope=totals_at_injection,
        total_physical_decay_loss_mbq_by_isotope=totals_physical_loss,
        total_unmet_prescribed_activity_mbq_by_isotope=totals_unmet,
        total_decay_loss_mbq_by_isotope={k: totals_physical_loss[k] + totals_unmet[k] for k in totals_prescribed},
        overall_physical_decay_loss_mbq=overall_physical_loss,
        overall_unmet_prescribed_activity_mbq=overall_unmet,
        overall_decay_loss_mbq=overall_loss,
        mean_retained_fraction=mean(retained_values) if retained_values else 0.0,
        decay_loss_mbq_per_completed_patient=(overall_loss / completed_count) if completed_count > 0 else 0.0,
        physical_decay_loss_mbq_per_feasible_completed_patient=(overall_physical_loss / feasible_completed_count) if feasible_completed_count > 0 else 0.0,
        required_eob_mbq_per_feasible_completed_patient=(sum(totals_required_eob.values()) / feasible_completed_count) if feasible_completed_count > 0 else 0.0,
        total_potential_shortfall_mbq_if_no_upstream_adjustment=sum(trace.potential_shortfall_mbq_if_no_upstream_adjustment for trace in patient_decay_traces),
        dose_sufficient_patient_count_if_no_upstream_adjustment=sum(1 for trace in patient_decay_traces if trace.dose_sufficient_if_no_upstream_adjustment),
        dose_insufficient_patient_count_if_no_upstream_adjustment=sum(1 for trace in patient_decay_traces if not trace.dose_sufficient_if_no_upstream_adjustment),
        decay_feasible_patient_count=sum(1 for trace in patient_decay_traces if trace.decay_feasible),
        decay_infeasible_patient_count=sum(1 for trace in patient_decay_traces if not trace.decay_feasible),
        decay_infeasible_by_isotope=infeasible_by_isotope,
        isotope_summaries=tuple(isotope_summaries),
        batch_summaries=tuple(batch_summaries),
        patient_traces=tuple(patient_decay_traces),
    )
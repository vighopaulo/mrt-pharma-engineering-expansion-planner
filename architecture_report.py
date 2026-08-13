from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from architecture_recommendation import ArchitectureCandidateResult, ArchitectureRecommendationResult
from decision_pipeline import NativeBottleneckSummary, NativePathwayScenario, Pathway
from infrastructure_capex import CapexLedgerItem
from infrastructure_opex import OpexLedgerItem
from lifecycle_economics import LifecycleComparisonResult, LifecycleEconomicResult
from production_clinical_schedule import ProductionClinicalPatientTrace
from stochastic_design_day import PatientRadionuclideDemand


def _trace_id(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class NativeChartPoint:
    x: float
    y: float
    label: str | None = None


@dataclass(frozen=True)
class NativeCategoricalChartItem:
    label: str
    value: float
    share: float


@dataclass(frozen=True)
class NativeAnnualCashFlowPoint:
    year: int
    forecast_demand_per_day: float
    patients_served_per_day: float
    annual_revenue: float
    annual_opex: float
    annual_net_cash_flow: float
    discounted_cash_flow: float
    cumulative_npv: float


@dataclass(frozen=True)
class NativePatientReportRecord:
    seed: int
    pathway: Pathway
    candidate_id: str
    patient_id: str
    radionuclide: str
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
    uptake_start_minutes: float
    uptake_end_minutes: float
    scan_start_minutes: float
    scan_end_minutes: float
    completed_within_operating_day: bool


@dataclass(frozen=True)
class NativeRunReport:
    seed: int
    pathway: Pathway
    candidate_id: str
    comparison_trace_id: str
    demand_trace_id: str
    pathway_trace_id: str
    bottleneck: NativeBottleneckSummary
    completed_patients: int
    incomplete_patients: int
    completion_percentage: float
    patient_records: tuple[NativePatientReportRecord, ...]


@dataclass(frozen=True)
class NativeEconomicSummary:
    initial_capex: float
    annual_revenue: float
    annual_opex: float
    annual_net_cash_flow: float
    final_npv: float
    payback_year: float | None


@dataclass(frozen=True)
class NativeIncrementalEconomicSummary:
    capex_delta: float
    annual_opex_delta: float
    annual_revenue_delta: float
    annual_net_cash_flow_delta: float
    final_npv_delta: float
    payback_year_delta: float | None


@dataclass(frozen=True)
class NativeEngineeringDetail:
    scanners: int
    injection_resources: int
    uptake_resources: int
    distribution_concurrency: int
    transport_minutes: float
    installed_cyclotron_units: int
    installed_radiopharmacy_units: int
    installed_mrt_base_infrastructure_units: int
    installed_mrt_endpoints: int
    installed_guideway_length_m: float
    guideway_capex_per_m: float
    guideway_capex_total: float
    guideway_maintenance_per_m_year: float
    guideway_maintenance_annual_cost: float
    operated_cyclotron_units: int
    operated_radiopharmacy_units: int
    operated_mrt_base_units: int
    operated_mrt_endpoints: int
    operated_guideway_length_m: float
    operated_vertical_transitions: int
    operated_building_connections: int
    clinical_staff_fte: float
    clinical_staff_loaded_cost_per_fte: float
    production_staff_fte: float
    production_staff_loaded_cost_per_fte: float
    conventional_transport_staff_fte: float
    conventional_transport_staff_loaded_cost_per_fte: float
    mrt_support_staff_fte: float
    mrt_support_staff_loaded_cost_per_fte: float
    annual_scanner_energy_kwh: float
    annual_cyclotron_energy_kwh: float
    annual_mrt_energy_kwh: float
    annual_other_energy_kwh: float
    electricity_cost_per_kwh: float
    annual_consumable_units: float
    consumable_cost_per_unit: float


@dataclass(frozen=True)
class NativePathwayChartData:
    throughput_distribution: tuple[NativeChartPoint, ...]
    reliability_curve: tuple[NativeChartPoint, ...]
    stochastic_daily_completions: tuple[NativeChartPoint, ...]
    isotope_mix: tuple[NativeCategoricalChartItem, ...]
    bottleneck_frequencies: tuple[NativeCategoricalChartItem, ...]
    capex_composition: tuple[NativeCategoricalChartItem, ...]
    opex_composition: tuple[NativeCategoricalChartItem, ...]
    annual_financials: tuple[NativeAnnualCashFlowPoint, ...]
    cumulative_discounted_cash_flow: tuple[NativeChartPoint, ...]


@dataclass(frozen=True)
class NativeRecommendationChartData:
    npv_vs_reliability: tuple[NativeChartPoint, ...]
    capex_vs_reliable_throughput: tuple[NativeChartPoint, ...]


@dataclass(frozen=True)
class NativePathwayReport:
    candidate_id: str
    pathway: Pathway
    status: Literal["QUALIFIED", "REJECTED_RELIABILITY"]
    measured_reliability: float
    reliability_margin: float
    architecture: NativePathwayScenario
    engineering_detail: NativeEngineeringDetail
    economic_summary: NativeEconomicSummary
    incremental_economic_summary: NativeIncrementalEconomicSummary | None
    candidate_result: ArchitectureCandidateResult
    capex_ledger: tuple[CapexLedgerItem, ...]
    opex_ledger: tuple[OpexLedgerItem, ...]
    lifecycle_result: LifecycleEconomicResult
    lifecycle_comparison_result: LifecycleComparisonResult | None
    annual_cash_flow_rows: tuple[NativeAnnualCashFlowPoint, ...]
    run_reports: tuple[NativeRunReport, ...]
    patient_records: tuple[NativePatientReportRecord, ...]
    chart_data: NativePathwayChartData
    selection_reason: str
    rejection_reason: str | None
    bottleneck_summary: NativeBottleneckSummary
    provenance_trace_id: str


@dataclass(frozen=True)
class NativeArchitectureReportProvenance:
    recommendation_trace_id: str
    candidate_provenance_trace_ids: Mapping[str, str]
    run_trace_ids_by_candidate_id: Mapping[str, tuple[str, ...]]
    report_trace_id: str


@dataclass(frozen=True)
class NativeArchitectureReportData:
    recommendation_result: ArchitectureRecommendationResult
    selected_pathway_report: NativePathwayReport | None
    best_qualifying_conventional_report: NativePathwayReport | None
    best_qualifying_mrt_report: NativePathwayReport | None
    reportable_pathway_reports: tuple[NativePathwayReport, ...]
    recommendation_chart_data: NativeRecommendationChartData
    provenance: NativeArchitectureReportProvenance
    limitations: tuple[str, ...]


def _economic_summary(
    lifecycle_result: LifecycleEconomicResult,
    capex_total: float,
    opex_total: float,
) -> NativeEconomicSummary:
    first_row = lifecycle_result.annual_rows[0]
    return NativeEconomicSummary(
        initial_capex=float(capex_total),
        annual_revenue=float(first_row.annual_revenue),
        annual_opex=float(opex_total),
        annual_net_cash_flow=float(first_row.annual_net_cash_flow),
        final_npv=float(lifecycle_result.final_npv),
        payback_year=lifecycle_result.payback_year,
    )


def _incremental_economic_summary(
    conventional: NativePathwayReport,
    mrt: NativePathwayReport,
) -> NativeIncrementalEconomicSummary:
    conventional_payback = conventional.economic_summary.payback_year
    mrt_payback = mrt.economic_summary.payback_year
    return NativeIncrementalEconomicSummary(
        capex_delta=mrt.economic_summary.initial_capex - conventional.economic_summary.initial_capex,
        annual_opex_delta=mrt.economic_summary.annual_opex - conventional.economic_summary.annual_opex,
        annual_revenue_delta=mrt.economic_summary.annual_revenue - conventional.economic_summary.annual_revenue,
        annual_net_cash_flow_delta=mrt.economic_summary.annual_net_cash_flow - conventional.economic_summary.annual_net_cash_flow,
        final_npv_delta=mrt.economic_summary.final_npv - conventional.economic_summary.final_npv,
        payback_year_delta=(mrt_payback - conventional_payback) if mrt_payback is not None and conventional_payback is not None else None,
    )


def _engineering_detail(candidate_result: ArchitectureCandidateResult) -> NativeEngineeringDetail:
    architecture = candidate_result.architecture
    guideway_maintenance_annual_cost = 0.0
    for item in candidate_result.opex_result.ledger:
        if item.component == "Guideway maintenance":
            guideway_maintenance_annual_cost = float(item.annual_cost)
            break
    return NativeEngineeringDetail(
        scanners=architecture.scanners,
        injection_resources=architecture.injection_resources,
        uptake_resources=architecture.uptake_resources,
        distribution_concurrency=architecture.distribution_concurrency,
        transport_minutes=architecture.transport_minutes,
        installed_cyclotron_units=architecture.installed_cyclotron_units,
        installed_radiopharmacy_units=architecture.installed_radiopharmacy_units,
        installed_mrt_base_infrastructure_units=architecture.installed_mrt_base_infrastructure_units,
        installed_mrt_endpoints=architecture.installed_mrt_endpoints,
        installed_guideway_length_m=architecture.installed_guideway_length_m,
        guideway_capex_per_m=architecture.guideway_capex_per_m,
        guideway_capex_total=float(candidate_result.capex_result.mrt_specific_capex),
        guideway_maintenance_per_m_year=architecture.guideway_maintenance_per_m_year,
        guideway_maintenance_annual_cost=guideway_maintenance_annual_cost,
        operated_cyclotron_units=architecture.operated_cyclotron_units,
        operated_radiopharmacy_units=architecture.operated_radiopharmacy_units,
        operated_mrt_base_units=architecture.operated_mrt_base_units,
        operated_mrt_endpoints=architecture.operated_mrt_endpoints,
        operated_guideway_length_m=architecture.operated_guideway_length_m,
        operated_vertical_transitions=architecture.operated_vertical_transitions,
        operated_building_connections=architecture.operated_building_connections,
        clinical_staff_fte=architecture.clinical_staff_fte,
        clinical_staff_loaded_cost_per_fte=architecture.clinical_staff_loaded_cost_per_fte,
        production_staff_fte=architecture.production_staff_fte,
        production_staff_loaded_cost_per_fte=architecture.production_staff_loaded_cost_per_fte,
        conventional_transport_staff_fte=architecture.conventional_transport_staff_fte,
        conventional_transport_staff_loaded_cost_per_fte=architecture.conventional_transport_staff_loaded_cost_per_fte,
        mrt_support_staff_fte=architecture.mrt_support_staff_fte,
        mrt_support_staff_loaded_cost_per_fte=architecture.mrt_support_staff_loaded_cost_per_fte,
        annual_scanner_energy_kwh=architecture.annual_scanner_energy_kwh,
        annual_cyclotron_energy_kwh=architecture.annual_cyclotron_energy_kwh,
        annual_mrt_energy_kwh=architecture.annual_mrt_energy_kwh,
        annual_other_energy_kwh=architecture.annual_other_energy_kwh,
        electricity_cost_per_kwh=architecture.electricity_cost_per_kwh,
        annual_consumable_units=architecture.annual_consumable_units,
        consumable_cost_per_unit=architecture.consumable_cost_per_unit,
    )


def _annual_cash_flow_rows(lifecycle_result: LifecycleEconomicResult) -> tuple[NativeAnnualCashFlowPoint, ...]:
    return tuple(
        NativeAnnualCashFlowPoint(
            year=row.year,
            forecast_demand_per_day=row.forecast_demand_per_day,
            patients_served_per_day=row.patients_served_per_day,
            annual_revenue=row.annual_revenue,
            annual_opex=row.annual_opex,
            annual_net_cash_flow=row.annual_net_cash_flow,
            discounted_cash_flow=row.discounted_cash_flow,
            cumulative_npv=row.cumulative_npv,
        )
        for row in lifecycle_result.annual_rows
    )


def _patient_records_for_run(
    *,
    seed: int,
    pathway: Pathway,
    candidate_id: str,
    generated_patients: Sequence[PatientRadionuclideDemand],
    patient_traces: Sequence[ProductionClinicalPatientTrace],
) -> tuple[NativePatientReportRecord, ...]:
    trace_by_patient_id = {trace.patient_id: trace for trace in patient_traces}
    records: list[NativePatientReportRecord] = []
    for patient in generated_patients:
        trace = trace_by_patient_id[patient.patient_id]
        records.append(
            NativePatientReportRecord(
                seed=seed,
                pathway=pathway,
                candidate_id=candidate_id,
                patient_id=patient.patient_id,
                radionuclide=patient.radionuclide,
                prescribed_activity_mbq=patient.prescribed_activity_mbq,
                batch_id=trace.batch_id,
                production_window_id=trace.production_window_id,
                production_window_start_time_minutes=trace.production_window_start_time_minutes,
                production_window_end_time_minutes=trace.production_window_end_time_minutes,
                release_time_minutes=trace.batch_release_time_minutes,
                distribution_start_minutes=trace.distribution_start,
                distribution_end_minutes=trace.distribution_end,
                injection_start_minutes=trace.injection_start,
                injection_end_minutes=trace.injection_end,
                uptake_start_minutes=trace.uptake_start,
                uptake_end_minutes=trace.uptake_end,
                scan_start_minutes=trace.scan_start,
                scan_end_minutes=trace.scan_end,
                completed_within_operating_day=trace.completed_within_operating_day,
            )
        )
    return tuple(records)


def _categorical_items(items: Mapping[str, float]) -> tuple[NativeCategoricalChartItem, ...]:
    total = sum(float(value) for value in items.values())
    if total <= 0.0:
        total = 1.0
    return tuple(NativeCategoricalChartItem(label=label, value=float(value), share=float(value) / total) for label, value in sorted(items.items()))


def _throughput_distribution_series(values: Sequence[float]) -> tuple[NativeChartPoint, ...]:
    sorted_values = sorted(float(value) for value in values)
    if not sorted_values:
        return ()
    total = len(sorted_values)
    return tuple(NativeChartPoint(x=value, y=1.0 / total) for value in sorted_values)


def _reliability_curve_series(values: Sequence[float]) -> tuple[NativeChartPoint, ...]:
    sorted_values = sorted(float(value) for value in values)
    if not sorted_values:
        return ()
    total = len(sorted_values)
    return tuple(NativeChartPoint(x=value, y=(total - index) / total) for index, value in enumerate(sorted_values))


def _stochastic_completion_series(run_reports: Sequence[NativeRunReport]) -> tuple[NativeChartPoint, ...]:
    return tuple(NativeChartPoint(x=float(report.seed), y=float(report.completed_patients), label=str(report.seed)) for report in run_reports)


def _capex_ledger_chart_items(items: Sequence[CapexLedgerItem]) -> tuple[NativeCategoricalChartItem, ...]:
    total = sum(float(item.subtotal) for item in items)
    if total <= 0.0:
        total = 1.0
    chart_items: list[NativeCategoricalChartItem] = []
    for item in items:
        value = float(item.subtotal)
        chart_items.append(NativeCategoricalChartItem(label=str(item.component), value=value, share=value / total))
    return tuple(chart_items)


def _opex_ledger_chart_items(items: Sequence[OpexLedgerItem]) -> tuple[NativeCategoricalChartItem, ...]:
    total = sum(float(item.annual_cost) for item in items)
    if total <= 0.0:
        total = 1.0
    chart_items: list[NativeCategoricalChartItem] = []
    for item in items:
        value = float(item.annual_cost)
        chart_items.append(NativeCategoricalChartItem(label=str(item.component), value=value, share=value / total))
    return tuple(chart_items)


def _isotope_counts_from_runs(run_reports: Sequence[NativeRunReport]) -> Mapping[str, float]:
    counts: Counter[str] = Counter()
    for report in run_reports:
        for patient in report.patient_records:
            counts[patient.radionuclide] += 1
    return dict(counts)


def _pathway_chart_data(candidate: ArchitectureCandidateResult, run_reports: Sequence[NativeRunReport]) -> NativePathwayChartData:
    throughput_values = candidate.throughput_distribution.observations
    annual_financials = _annual_cash_flow_rows(candidate.lifecycle_result)
    bottleneck_counts = (
        candidate.reliability_result.conventional.bottleneck_counts
        if candidate.pathway == "Conventional"
        else candidate.reliability_result.mrt.bottleneck_counts
    )
    return NativePathwayChartData(
        throughput_distribution=_throughput_distribution_series(throughput_values),
        reliability_curve=_reliability_curve_series(throughput_values),
        stochastic_daily_completions=_stochastic_completion_series(run_reports),
        isotope_mix=_categorical_items(_isotope_counts_from_runs(run_reports)),
        bottleneck_frequencies=_categorical_items(bottleneck_counts),
        capex_composition=_capex_ledger_chart_items(candidate.capex_result.ledger),
        opex_composition=_opex_ledger_chart_items(candidate.opex_result.ledger),
        annual_financials=annual_financials,
        cumulative_discounted_cash_flow=tuple(NativeChartPoint(x=float(row.year), y=float(row.cumulative_npv)) for row in annual_financials),
    )


def _run_report(candidate: ArchitectureCandidateResult, run_result) -> NativeRunReport:
    pathway_result = run_result.native_result.conventional if candidate.pathway == "Conventional" else run_result.native_result.mrt
    patient_records = _patient_records_for_run(
        seed=run_result.seed,
        pathway=candidate.pathway,
        candidate_id=candidate.candidate_id,
        generated_patients=run_result.native_result.demand_result.simulation.generated_demand.patients,
        patient_traces=pathway_result.operational_result.production_clinical_result.patient_traces,
    )
    return NativeRunReport(
        seed=run_result.seed,
        pathway=candidate.pathway,
        candidate_id=candidate.candidate_id,
        comparison_trace_id=run_result.reference.comparison_trace_id,
        demand_trace_id=run_result.reference.demand_trace_id,
        pathway_trace_id=run_result.reference.pathway_trace_ids[candidate.pathway],
        bottleneck=run_result.reference.bottleneck_by_pathway[candidate.pathway],
        completed_patients=int(pathway_result.operational_result.patients_completed),
        incomplete_patients=int(pathway_result.operational_result.patients_incomplete),
        completion_percentage=float(pathway_result.operational_result.completion_percentage),
        patient_records=patient_records,
    )


def _pathway_report(candidate: ArchitectureCandidateResult) -> NativePathwayReport:
    run_reports = tuple(_run_report(candidate, run_result) for run_result in candidate.reliability_result.run_results)
    chart_data = _pathway_chart_data(candidate, run_reports)
    lifecycle_comparison_result = candidate.lifecycle_case.lifecycle_comparison_result
    economic_summary = _economic_summary(
        lifecycle_result=candidate.lifecycle_result,
        capex_total=candidate.capex_result.total_capex,
        opex_total=candidate.opex_result.total_annual_opex,
    )
    return NativePathwayReport(
        candidate_id=candidate.candidate_id,
        pathway=candidate.pathway,
        status=candidate.status,
        measured_reliability=candidate.measured_reliability,
        reliability_margin=candidate.reliability_margin,
        architecture=candidate.architecture,
        engineering_detail=_engineering_detail(candidate),
        economic_summary=economic_summary,
        incremental_economic_summary=None,
        candidate_result=candidate,
        capex_ledger=candidate.capex_result.ledger,
        opex_ledger=candidate.opex_result.ledger,
        lifecycle_result=candidate.lifecycle_result,
        lifecycle_comparison_result=lifecycle_comparison_result,
        annual_cash_flow_rows=chart_data.annual_financials,
        run_reports=run_reports,
        patient_records=tuple(record for run in run_reports for record in run.patient_records),
        chart_data=chart_data,
        selection_reason=candidate.selection_reason,
        rejection_reason=candidate.rejection_reason,
        bottleneck_summary=candidate.bottleneck_summary,
        provenance_trace_id=candidate.provenance.reliability_trace_id,
    )


def _limitations() -> tuple[str, ...]:
    return (
        "Empirical report data depends on the supplied seed set.",
        "No spatially derived guideway geometry.",
        "No demand-driven staffing inference.",
        "No multi-isotope decay economics.",
        "No PDF/DOCX/XLSX rendering in this build.",
    )


def build_native_architecture_report_data(recommendation_result: ArchitectureRecommendationResult) -> NativeArchitectureReportData:
    conventional_report = _pathway_report(recommendation_result.best_qualifying_conventional) if recommendation_result.best_qualifying_conventional is not None else None
    mrt_report = _pathway_report(recommendation_result.best_qualifying_mrt) if recommendation_result.best_qualifying_mrt is not None else None
    reportable_pathway_reports = tuple(report for report in (conventional_report, mrt_report) if report is not None)

    if conventional_report is not None and mrt_report is not None:
        incremental_summary = _incremental_economic_summary(conventional_report, mrt_report)
        conventional_report = NativePathwayReport(
            **{**conventional_report.__dict__, "incremental_economic_summary": incremental_summary}
        )
        mrt_report = NativePathwayReport(
            **{**mrt_report.__dict__, "incremental_economic_summary": incremental_summary}
        )

    selected_pathway_report: NativePathwayReport | None = None
    if recommendation_result.recommended_pathway == "Conventional":
        selected_pathway_report = conventional_report
    elif recommendation_result.recommended_pathway == "MRT":
        selected_pathway_report = mrt_report

    recommendation_chart_data = NativeRecommendationChartData(
        npv_vs_reliability=tuple(
            NativeChartPoint(x=candidate.measured_reliability, y=candidate.lifecycle_npv, label=candidate.candidate_id)
            for candidate in recommendation_result.conventional_candidates + recommendation_result.mrt_candidates
        ),
        capex_vs_reliable_throughput=tuple(
            NativeChartPoint(x=candidate.throughput_distribution.p95, y=candidate.capex_result.total_capex, label=candidate.candidate_id)
            for candidate in recommendation_result.conventional_candidates + recommendation_result.mrt_candidates
        ),
    )

    provenance = NativeArchitectureReportProvenance(
        recommendation_trace_id=recommendation_result.provenance.aggregate_trace_id,
        candidate_provenance_trace_ids={
            candidate.candidate_id: candidate.provenance.reliability_trace_id
            for candidate in recommendation_result.conventional_candidates + recommendation_result.mrt_candidates
        },
        run_trace_ids_by_candidate_id={
            candidate.candidate_id: tuple(run.reference.comparison_trace_id for run in candidate.reliability_result.run_results)
            for candidate in recommendation_result.conventional_candidates + recommendation_result.mrt_candidates
        },
        report_trace_id=_trace_id(
            {
                "recommendation_trace_id": recommendation_result.provenance.aggregate_trace_id,
                "selected_candidate_id": None if selected_pathway_report is None else selected_pathway_report.candidate_id,
                "reportable_candidate_ids": [report.candidate_id for report in reportable_pathway_reports],
            }
        ),
    )

    limitations = recommendation_result.limitations + _limitations() + (
        "Report contract preserves native generated patients for each run and does not synthesize a persistent patient library.",
    )

    return NativeArchitectureReportData(
        recommendation_result=recommendation_result,
        selected_pathway_report=selected_pathway_report,
        best_qualifying_conventional_report=conventional_report,
        best_qualifying_mrt_report=mrt_report,
        reportable_pathway_reports=reportable_pathway_reports,
        recommendation_chart_data=recommendation_chart_data,
        provenance=provenance,
        limitations=limitations,
    )
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from architecture_recommendation import ArchitectureCandidateResult, ArchitectureRecommendationResult
from design_horizon_planning import (
    DesignHorizonPlanningResult,
    DesignHorizonYearResult,
    HorizonExpansionAction,
    _apply_resource_step,
)
from decision_pipeline import NativeBottleneckSummary, NativePathwayScenario, Pathway
from infrastructure_capex import CapexLedgerItem
from infrastructure_opex import OpexLedgerItem
from lifecycle_economics import LifecycleComparisonResult, LifecycleEconomicResult
from multi_isotope_decay import PathwayDecaySummary
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
    assigned_cyclotron_id: str
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
    elapsed_decay_time_minutes: float
    retained_fraction_at_administration: float
    required_activity_at_eob_mbq: float
    required_activity_at_release_mbq: float
    activity_at_injection_mbq: float
    physical_decay_loss_before_administration_mbq: float
    unmet_prescribed_activity_mbq: float
    required_upstream_activity_for_prescribed_mbq: float
    theoretical_required_activity_at_eob_mbq: float
    theoretical_required_activity_at_release_mbq: float
    theoretical_compensation_factor: float
    decay_feasible: bool
    decay_infeasibility_reason: str | None
    potential_shortfall_mbq_if_no_upstream_adjustment: float
    dose_sufficient_if_no_upstream_adjustment: bool
    completed_within_operating_day: bool


@dataclass(frozen=True)
class NativeRunReport:
    seed: int
    pathway: Pathway
    candidate_id: str
    comparison_trace_id: str
    demand_trace_id: str
    fleet_id: str
    fleet_asset_ids: tuple[str, ...]
    fleet_supported_radionuclides: tuple[str, ...]
    pathway_trace_id: str
    bottleneck: NativeBottleneckSummary
    scheduled_patients: int
    schedule_completed_patients: int
    effective_completed_patients: int
    decay_infeasible_patients: int
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
    installed_mrt_carriers: int
    operated_mrt_carriers: int
    spare_mrt_carriers: int
    carrier_quantity_constrained_throughput: bool
    carrier_proxy_relationship: str | None
    carrier_capex_modeled: bool
    carrier_opex_modeled: bool
    carrier_energy_modeled: bool
    carrier_capex_status: str
    carrier_opex_status: str
    carrier_energy_status: str
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
    retained_activity_by_patient: tuple[NativeChartPoint, ...]
    decay_loss_by_isotope: tuple[NativeCategoricalChartItem, ...]
    decay_loss_by_batch: tuple[NativeCategoricalChartItem, ...]
    elapsed_time_vs_retained_fraction: tuple[NativeChartPoint, ...]


@dataclass(frozen=True)
class NativeRecommendationChartData:
    npv_vs_reliability: tuple[NativeChartPoint, ...]
    capex_vs_reliable_throughput: tuple[NativeChartPoint, ...]
    conventional_vs_mrt_retained_activity: tuple[NativeChartPoint, ...]


@dataclass(frozen=True)
class NativeDecayIsotopeSummaryRow:
    isotope: str
    half_life_minutes: float
    patient_count: int
    total_prescribed_activity_mbq: float
    total_prescribed_activity_mbq_successfully_served: float
    total_required_activity_at_eob_mbq: float
    total_required_activity_at_release_mbq: float
    total_activity_at_injection_mbq: float
    total_physical_decay_loss_mbq: float
    total_unmet_prescribed_activity_mbq: float
    total_decay_related_loss_mbq: float
    feasible_patient_count: int
    infeasible_patient_count: int
    retained_percentage: float


@dataclass(frozen=True)
class NativeDecayBatchSummaryRow:
    batch_id: int
    isotope: str
    patient_count: int
    assigned_cyclotron_id: str
    production_window_id: int
    production_window_start_time_minutes: float
    production_window_end_time_minutes: float
    release_time_minutes: float
    total_prescribed_activity_mbq: float
    total_prescribed_activity_mbq_successfully_served: float
    total_required_activity_at_eob_mbq: float
    total_required_activity_at_release_mbq: float
    total_activity_at_injection_mbq: float
    total_physical_decay_loss_mbq: float
    total_unmet_prescribed_activity_mbq: float
    total_decay_related_loss_mbq: float
    feasible_patient_count: int
    infeasible_patient_count: int
    average_retained_fraction: float


@dataclass(frozen=True)
class NativePathwayDecayComparison:
    conventional_physical_decay_loss_mbq: float
    mrt_physical_decay_loss_mbq: float
    conventional_unmet_prescribed_activity_mbq: float
    mrt_unmet_prescribed_activity_mbq: float
    conventional_total_decay_related_loss_mbq: float
    mrt_total_decay_related_loss_mbq: float
    incremental_activity_retained_mrt_minus_conventional_mbq: float
    retained_activity_percentage_difference_mrt_minus_conventional: float


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
    fleet_id: str
    fleet_asset_ids: tuple[str, ...]
    fleet_supported_radionuclides: tuple[str, ...]
    capex_ledger: tuple[CapexLedgerItem, ...]
    opex_ledger: tuple[OpexLedgerItem, ...]
    lifecycle_result: LifecycleEconomicResult
    lifecycle_comparison_result: LifecycleComparisonResult | None
    decay_summary: PathwayDecaySummary
    isotope_decay_summary_rows: tuple[NativeDecayIsotopeSummaryRow, ...]
    batch_decay_summary_rows: tuple[NativeDecayBatchSummaryRow, ...]
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
    pathway_decay_comparison: NativePathwayDecayComparison | None
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
    carrier_fleet = (
        candidate_result.direct_decision_result.mrt.operational_result.mrt_carrier_fleet
        if candidate_result.pathway == "MRT"
        else None
    )
    carrier_capex_status = (
        "NOT APPLICABLE: Conventional pathway does not use MRT carriers."
        if carrier_fleet is None
        else carrier_fleet.carrier_capex_status
    )
    carrier_opex_status = (
        "NOT APPLICABLE: Conventional pathway does not use MRT carriers."
        if carrier_fleet is None
        else carrier_fleet.carrier_opex_status
    )
    carrier_energy_status = (
        "NOT APPLICABLE: Conventional pathway does not use MRT carriers."
        if carrier_fleet is None
        else carrier_fleet.carrier_energy_status
    )
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
        installed_mrt_carriers=0 if carrier_fleet is None else carrier_fleet.installed_carriers,
        operated_mrt_carriers=0 if carrier_fleet is None else carrier_fleet.operated_carriers,
        spare_mrt_carriers=0 if carrier_fleet is None else carrier_fleet.spare_carriers,
        carrier_quantity_constrained_throughput=False if carrier_fleet is None else carrier_fleet.carrier_constrained_throughput,
        carrier_proxy_relationship=None if carrier_fleet is None else carrier_fleet.proxy_relationship,
        carrier_capex_modeled=False if carrier_fleet is None else carrier_fleet.carrier_capex_modeled,
        carrier_opex_modeled=False if carrier_fleet is None else carrier_fleet.carrier_opex_modeled,
        carrier_energy_modeled=False if carrier_fleet is None else carrier_fleet.carrier_energy_modeled,
        carrier_capex_status=carrier_capex_status,
        carrier_opex_status=carrier_opex_status,
        carrier_energy_status=carrier_energy_status,
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
    patient_decay_traces,
) -> tuple[NativePatientReportRecord, ...]:
    trace_by_patient_id = {trace.patient_id: trace for trace in patient_traces}
    decay_by_patient_id = {trace.patient_id: trace for trace in patient_decay_traces}
    records: list[NativePatientReportRecord] = []
    for patient in generated_patients:
        trace = trace_by_patient_id[patient.patient_id]
        decay_trace = decay_by_patient_id[patient.patient_id]
        records.append(
            NativePatientReportRecord(
                seed=seed,
                pathway=pathway,
                candidate_id=candidate_id,
                patient_id=patient.patient_id,
                radionuclide=patient.radionuclide,
                prescribed_activity_mbq=patient.prescribed_activity_mbq,
                batch_id=trace.batch_id,
                assigned_cyclotron_id=trace.assigned_cyclotron_id,
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
                elapsed_decay_time_minutes=decay_trace.elapsed_eob_to_injection_minutes,
                retained_fraction_at_administration=decay_trace.retained_fraction_at_administration,
                required_activity_at_eob_mbq=decay_trace.activity_at_eob_mbq,
                required_activity_at_release_mbq=decay_trace.activity_at_release_mbq,
                activity_at_injection_mbq=decay_trace.activity_at_injection_mbq,
                physical_decay_loss_before_administration_mbq=decay_trace.physical_decay_loss_before_administration_mbq,
                unmet_prescribed_activity_mbq=decay_trace.unmet_prescribed_activity_mbq,
                required_upstream_activity_for_prescribed_mbq=decay_trace.required_upstream_activity_for_prescribed_mbq,
                theoretical_required_activity_at_eob_mbq=decay_trace.theoretical_required_activity_at_eob_mbq,
                theoretical_required_activity_at_release_mbq=decay_trace.theoretical_required_activity_at_release_mbq,
                theoretical_compensation_factor=decay_trace.theoretical_compensation_factor,
                decay_feasible=decay_trace.decay_feasible,
                decay_infeasibility_reason=decay_trace.decay_infeasibility_reason,
                potential_shortfall_mbq_if_no_upstream_adjustment=decay_trace.potential_shortfall_mbq_if_no_upstream_adjustment,
                dose_sufficient_if_no_upstream_adjustment=decay_trace.dose_sufficient_if_no_upstream_adjustment,
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


def _retained_activity_by_patient(run_reports: Sequence[NativeRunReport]) -> tuple[NativeChartPoint, ...]:
    points: list[NativeChartPoint] = []
    for run_report in run_reports:
        for patient in run_report.patient_records:
            points.append(
                NativeChartPoint(
                    x=float(len(points) + 1),
                    y=float(patient.activity_at_injection_mbq),
                    label=patient.patient_id,
                )
            )
    return tuple(points)


def _elapsed_vs_retained(run_reports: Sequence[NativeRunReport]) -> tuple[NativeChartPoint, ...]:
    points: list[NativeChartPoint] = []
    for run_report in run_reports:
        for patient in run_report.patient_records:
            points.append(
                NativeChartPoint(
                    x=float(patient.elapsed_decay_time_minutes),
                    y=float(patient.retained_fraction_at_administration),
                    label=patient.patient_id,
                )
            )
    return tuple(points)


def _decay_loss_by_batch(run_reports: Sequence[NativeRunReport]) -> tuple[NativeCategoricalChartItem, ...]:
    by_batch: dict[str, float] = {}
    for run_report in run_reports:
        for patient in run_report.patient_records:
            key = f"{patient.batch_id}:{patient.radionuclide}"
            by_batch[key] = by_batch.get(key, 0.0) + float(patient.physical_decay_loss_before_administration_mbq)
    return _categorical_items(by_batch)


def _decay_loss_by_isotope(run_reports: Sequence[NativeRunReport]) -> tuple[NativeCategoricalChartItem, ...]:
    by_isotope: dict[str, float] = {}
    for run_report in run_reports:
        for patient in run_report.patient_records:
            key = patient.radionuclide
            by_isotope[key] = by_isotope.get(key, 0.0) + float(patient.physical_decay_loss_before_administration_mbq)
    return _categorical_items(by_isotope)


def _isotope_decay_rows(pathway_decay_summary: PathwayDecaySummary) -> tuple[NativeDecayIsotopeSummaryRow, ...]:
    rows: list[NativeDecayIsotopeSummaryRow] = []
    for summary in pathway_decay_summary.isotope_summaries:
        required_eob = float(summary.total_activity_at_eob_mbq)
        delivered = float(summary.total_activity_at_injection_mbq)
        retained_pct = 100.0 * delivered / required_eob if required_eob > 0.0 else 0.0
        rows.append(
            NativeDecayIsotopeSummaryRow(
                isotope=summary.radionuclide,
                half_life_minutes=summary.half_life_minutes,
                patient_count=summary.patient_count,
                total_prescribed_activity_mbq=float(summary.total_prescribed_activity_mbq),
                total_prescribed_activity_mbq_successfully_served=float(summary.total_prescribed_activity_mbq_successfully_served),
                total_required_activity_at_eob_mbq=required_eob,
                total_required_activity_at_release_mbq=float(summary.total_activity_at_release_mbq),
                total_activity_at_injection_mbq=delivered,
                total_physical_decay_loss_mbq=float(summary.total_physical_decay_loss_before_administration_mbq),
                total_unmet_prescribed_activity_mbq=float(summary.total_unmet_prescribed_activity_mbq),
                total_decay_related_loss_mbq=float(summary.total_physical_decay_loss_before_administration_mbq + summary.total_unmet_prescribed_activity_mbq),
                feasible_patient_count=summary.feasible_patient_count,
                infeasible_patient_count=summary.infeasible_patient_count,
                retained_percentage=retained_pct,
            )
        )
    return tuple(rows)


def _batch_decay_rows(pathway_decay_summary: PathwayDecaySummary) -> tuple[NativeDecayBatchSummaryRow, ...]:
    rows: list[NativeDecayBatchSummaryRow] = []
    for summary in pathway_decay_summary.batch_summaries:
        rows.append(
            NativeDecayBatchSummaryRow(
                batch_id=summary.batch_id,
                isotope=summary.radionuclide,
                patient_count=summary.patient_count,
                assigned_cyclotron_id=summary.assigned_cyclotron_id,
                production_window_id=summary.production_window_id,
                production_window_start_time_minutes=summary.production_window_start_time_minutes,
                production_window_end_time_minutes=summary.production_window_end_time_minutes,
                release_time_minutes=summary.release_time_minutes,
                total_prescribed_activity_mbq=summary.total_prescribed_activity_mbq,
                total_prescribed_activity_mbq_successfully_served=summary.total_prescribed_activity_mbq_successfully_served,
                total_required_activity_at_eob_mbq=summary.total_activity_at_eob_mbq,
                total_required_activity_at_release_mbq=summary.total_activity_at_release_mbq,
                total_activity_at_injection_mbq=summary.total_activity_at_injection_mbq,
                total_physical_decay_loss_mbq=summary.total_physical_decay_loss_before_administration_mbq,
                total_unmet_prescribed_activity_mbq=summary.total_unmet_prescribed_activity_mbq,
                total_decay_related_loss_mbq=summary.total_physical_decay_loss_before_administration_mbq + summary.total_unmet_prescribed_activity_mbq,
                feasible_patient_count=summary.feasible_patient_count,
                infeasible_patient_count=summary.infeasible_patient_count,
                average_retained_fraction=summary.average_retained_fraction,
            )
        )
    return tuple(rows)


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
        retained_activity_by_patient=_retained_activity_by_patient(run_reports),
        decay_loss_by_isotope=_decay_loss_by_isotope(run_reports),
        decay_loss_by_batch=_decay_loss_by_batch(run_reports),
        elapsed_time_vs_retained_fraction=_elapsed_vs_retained(run_reports),
    )


def _run_report(candidate: ArchitectureCandidateResult, run_result) -> NativeRunReport:
    pathway_result = run_result.native_result.conventional if candidate.pathway == "Conventional" else run_result.native_result.mrt
    pathway_decay_summary = pathway_result.decay_summary
    patient_records = _patient_records_for_run(
        seed=run_result.seed,
        pathway=candidate.pathway,
        candidate_id=candidate.candidate_id,
        generated_patients=run_result.native_result.demand_result.simulation.generated_demand.patients,
        patient_traces=pathway_result.operational_result.production_clinical_result.patient_traces,
        patient_decay_traces=pathway_decay_summary.patient_traces,
    )
    return NativeRunReport(
        seed=run_result.seed,
        pathway=candidate.pathway,
        candidate_id=candidate.candidate_id,
        comparison_trace_id=run_result.reference.comparison_trace_id,
        demand_trace_id=run_result.reference.demand_trace_id,
        fleet_id=getattr(run_result.reference, "fleet_id", "PRIMARY_FLEET"),
        fleet_asset_ids=tuple(getattr(run_result.reference, "fleet_asset_ids", ())),
        fleet_supported_radionuclides=tuple(getattr(run_result.reference, "fleet_supported_radionuclides", ())),
        pathway_trace_id=run_result.reference.pathway_trace_ids[candidate.pathway],
        bottleneck=run_result.reference.bottleneck_by_pathway[candidate.pathway],
        scheduled_patients=int(pathway_result.operational_result.scheduled_patients),
        schedule_completed_patients=int(pathway_result.operational_result.schedule_completed_patients),
        effective_completed_patients=int(pathway_result.operational_result.decay_feasible_completed_patients),
        decay_infeasible_patients=int(pathway_result.operational_result.decay_infeasible_patients),
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
        fleet_id=candidate.provenance.fleet_id,
        fleet_asset_ids=candidate.provenance.fleet_asset_ids,
        fleet_supported_radionuclides=candidate.provenance.fleet_supported_radionuclides,
        capex_ledger=candidate.capex_result.ledger,
        opex_ledger=candidate.opex_result.ledger,
        lifecycle_result=candidate.lifecycle_result,
        lifecycle_comparison_result=lifecycle_comparison_result,
        decay_summary=(
            candidate.direct_decision_result.conventional.decay_summary
            if candidate.pathway == "Conventional"
            else candidate.direct_decision_result.mrt.decay_summary
        ),
        isotope_decay_summary_rows=_isotope_decay_rows(
            candidate.direct_decision_result.conventional.decay_summary
            if candidate.pathway == "Conventional"
            else candidate.direct_decision_result.mrt.decay_summary
        ),
        batch_decay_summary_rows=_batch_decay_rows(
            candidate.direct_decision_result.conventional.decay_summary
            if candidate.pathway == "Conventional"
            else candidate.direct_decision_result.mrt.decay_summary
        ),
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
        "Decay physics is integrated, but direct monetization of activity loss requires an authoritative isotope-production cost model.",
        "No PDF/DOCX/XLSX rendering in this build.",
    )


def build_native_architecture_report_data(recommendation_result: ArchitectureRecommendationResult) -> NativeArchitectureReportData:
    conventional_report = _pathway_report(recommendation_result.best_qualifying_conventional) if recommendation_result.best_qualifying_conventional is not None else None
    mrt_report = _pathway_report(recommendation_result.best_qualifying_mrt) if recommendation_result.best_qualifying_mrt is not None else None

    if conventional_report is not None and mrt_report is not None:
        incremental_summary = _incremental_economic_summary(conventional_report, mrt_report)
        conventional_report = NativePathwayReport(
            **{**conventional_report.__dict__, "incremental_economic_summary": incremental_summary}
        )
        mrt_report = NativePathwayReport(
            **{**mrt_report.__dict__, "incremental_economic_summary": incremental_summary}
        )

    reportable_pathway_reports = tuple(report for report in (conventional_report, mrt_report) if report is not None)

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
        conventional_vs_mrt_retained_activity=(
            tuple(
                NativeChartPoint(x=0.0, y=conventional_report.decay_summary.mean_retained_fraction, label="Conventional")
                for _ in [0]
            )
            + tuple(
                NativeChartPoint(x=1.0, y=mrt_report.decay_summary.mean_retained_fraction, label="MRT")
                for _ in [0]
            )
            if conventional_report is not None and mrt_report is not None
            else ()
        ),
    )

    pathway_decay_comparison: NativePathwayDecayComparison | None = None
    if conventional_report is not None and mrt_report is not None:
        conventional_required_eob = sum(summary.total_activity_at_eob_mbq for summary in conventional_report.decay_summary.isotope_summaries)
        mrt_required_eob = sum(summary.total_activity_at_eob_mbq for summary in mrt_report.decay_summary.isotope_summaries)
        conventional_delivered = sum(conventional_report.decay_summary.total_activity_at_injection_mbq_by_isotope.values())
        mrt_delivered = sum(mrt_report.decay_summary.total_activity_at_injection_mbq_by_isotope.values())
        retained_pct_conventional = 100.0 * conventional_delivered / conventional_required_eob if conventional_required_eob > 0.0 else 0.0
        retained_pct_mrt = 100.0 * mrt_delivered / mrt_required_eob if mrt_required_eob > 0.0 else 0.0
        pathway_decay_comparison = NativePathwayDecayComparison(
            conventional_physical_decay_loss_mbq=conventional_report.decay_summary.overall_physical_decay_loss_mbq,
            mrt_physical_decay_loss_mbq=mrt_report.decay_summary.overall_physical_decay_loss_mbq,
            conventional_unmet_prescribed_activity_mbq=conventional_report.decay_summary.overall_unmet_prescribed_activity_mbq,
            mrt_unmet_prescribed_activity_mbq=mrt_report.decay_summary.overall_unmet_prescribed_activity_mbq,
            conventional_total_decay_related_loss_mbq=conventional_report.decay_summary.overall_decay_loss_mbq,
            mrt_total_decay_related_loss_mbq=mrt_report.decay_summary.overall_decay_loss_mbq,
            incremental_activity_retained_mrt_minus_conventional_mbq=mrt_delivered - conventional_delivered,
            retained_activity_percentage_difference_mrt_minus_conventional=retained_pct_mrt - retained_pct_conventional,
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
        pathway_decay_comparison=pathway_decay_comparison,
        recommendation_chart_data=recommendation_chart_data,
        provenance=provenance,
        limitations=limitations,
    )


@dataclass(frozen=True)
class NativeHorizonMetadata:
    project_name: str
    analysis_years: int
    demand_mode: str
    demand_trajectory_source: str
    demand_trajectory_interpolation_method: str
    seeds: tuple[int, ...]
    operating_days_per_year: int
    revenue_per_scan: float
    discount_rate_pct: float
    horizon_trace_id: str


@dataclass(frozen=True)
class NativeHorizonDemandYearRecord:
    year: int
    demand_patients_per_day: float


@dataclass(frozen=True)
class NativeHorizonResourceState:
    scanners: int
    injection_resources: int
    uptake_resources: int
    distribution_concurrency: int
    installed_mrt_carriers: int
    operated_mrt_carriers: int
    spare_mrt_carriers: int
    installed_mrt_endpoints: int
    installed_guideway_length_m: float
    cyclotron_units: int


@dataclass(frozen=True)
class NativeHorizonPathwayYearRecord:
    pathway: Pathway
    year: int
    demand_patients_per_day: float
    installed_reliable_effective_capacity_patients_per_day: float
    patients_served_per_day: float
    unmet_demand_per_day: float
    headroom_per_day: float
    capacity_utilization_pct: float
    probability_meeting_target_demand: float
    binding_bottleneck_resource: str
    annual_opex: float
    annual_revenue: float
    annual_expansion_capex: float
    resources: NativeHorizonResourceState
    fleet_id: str
    fleet_asset_ids: tuple[str, ...]
    fleet_supported_radionuclides: tuple[str, ...]


@dataclass(frozen=True)
class NativeHorizonExpansionResourceDelta:
    resource: str
    step: int


@dataclass(frozen=True)
class NativeHorizonExpansionDecisionRecord:
    year: int
    pathway: Pathway
    decision_id: str
    action_identifier: str
    action_type: Literal["single_resource", "multi_resource_combo"]
    resources_changed: tuple[NativeHorizonExpansionResourceDelta, ...]
    pre_expansion_capacity: float | None
    post_expansion_capacity: float | None
    capacity_delta: float | None
    pre_expansion_reliability: float | None
    post_expansion_reliability: float | None
    reliability_delta: float | None
    bottleneck_before: str | None
    bottleneck_after: str | None
    incremental_capex: float
    incremental_annual_opex: float
    reason: str
    trace_id: str


@dataclass(frozen=True)
class NativeHorizonCapacityExhaustionRecord:
    pathway: Pathway
    exhaustion_within_horizon: bool
    first_exhaustion_year: int | None
    demand_at_exhaustion: float | None
    capacity_at_exhaustion: float | None
    headroom_at_exhaustion: float | None
    reliability_at_exhaustion: float | None
    bottleneck_at_exhaustion: str | None


@dataclass(frozen=True)
class NativeHorizonBottleneckYearState:
    pathway: Pathway
    year: int
    bottleneck: str


@dataclass(frozen=True)
class NativeHorizonBottleneckMigrationEvent:
    pathway: Pathway
    year: int
    previous_bottleneck: str
    new_bottleneck: str


@dataclass(frozen=True)
class NativeHorizonStrategyPathwaySummary:
    pathway: Pathway
    strategy: Literal["build_ahead", "phased"]
    feasible: bool
    infeasibility_reason: str | None
    horizon_peak_demand: float
    year_zero_installed_capacity: float
    final_modeled_capacity: float
    year_zero_capex: float
    nominal_future_expansion_capex: float
    discounted_pv_future_expansion_capex: float
    total_horizon_opex: float
    total_horizon_revenue: float
    lifecycle_npv: float
    payback_year: float | None
    expansion_intervention_count: int
    expansion_intervention_years: tuple[int, ...]
    final_headroom: float
    final_bottleneck: str


@dataclass(frozen=True)
class NativeHorizonPathwayStrategyComparison:
    pathway: Pathway
    build_ahead_feasible: bool
    phased_feasible: bool
    build_ahead_npv: float
    phased_npv: float
    npv_delta_build_ahead_minus_phased: float
    capex_delta_build_ahead_minus_phased: float
    opex_delta_build_ahead_minus_phased: float
    intervention_count_delta_build_ahead_minus_phased: int
    preferred_strategy: str
    recommendation_reason: str | None


@dataclass(frozen=True)
class NativeHorizonYearComparisonRecord:
    year: int
    demand_patients_per_day: float
    conventional_capacity: float
    mrt_capacity: float
    capacity_delta_mrt_minus_conventional: float
    conventional_headroom: float
    mrt_headroom: float
    headroom_delta_mrt_minus_conventional: float
    conventional_reliability: float
    mrt_reliability: float
    reliability_delta_mrt_minus_conventional: float
    conventional_annual_opex: float
    mrt_annual_opex: float
    opex_delta_mrt_minus_conventional: float
    conventional_annual_revenue: float
    mrt_annual_revenue: float
    revenue_delta_mrt_minus_conventional: float
    conventional_expansion_capex: float
    mrt_expansion_capex: float
    conventional_bottleneck: str
    mrt_bottleneck: str


@dataclass(frozen=True)
class NativeHorizonFinalComparison:
    final_year: int
    final_demand: float
    conventional_final_capacity: float
    mrt_final_capacity: float
    conventional_final_headroom: float
    mrt_final_headroom: float
    conventional_cumulative_expansion_capex: float
    mrt_cumulative_expansion_capex: float
    conventional_lifecycle_npv: float
    mrt_lifecycle_npv: float
    lifecycle_npv_delta_mrt_minus_conventional: float
    conventional_intervention_count: int
    mrt_intervention_count: int
    pathway_strategy_preference: Mapping[Pathway, str]


@dataclass(frozen=True)
class NativeHorizonChartSeries:
    demand: tuple[NativeChartPoint, ...]
    conventional_capacity: tuple[NativeChartPoint, ...]
    mrt_capacity: tuple[NativeChartPoint, ...]
    conventional_headroom: tuple[NativeChartPoint, ...]
    mrt_headroom: tuple[NativeChartPoint, ...]
    conventional_reliability: tuple[NativeChartPoint, ...]
    mrt_reliability: tuple[NativeChartPoint, ...]
    conventional_annual_opex: tuple[NativeChartPoint, ...]
    mrt_annual_opex: tuple[NativeChartPoint, ...]
    conventional_annual_revenue: tuple[NativeChartPoint, ...]
    mrt_annual_revenue: tuple[NativeChartPoint, ...]
    conventional_expansion_capex: tuple[NativeChartPoint, ...]
    mrt_expansion_capex: tuple[NativeChartPoint, ...]
    conventional_cumulative_expansion_capex: tuple[NativeChartPoint, ...]
    mrt_cumulative_expansion_capex: tuple[NativeChartPoint, ...]
    conventional_bottleneck_by_year: tuple[NativeCategoricalChartItem, ...]
    mrt_bottleneck_by_year: tuple[NativeCategoricalChartItem, ...]
    conventional_scanners: tuple[NativeChartPoint, ...]
    mrt_scanners: tuple[NativeChartPoint, ...]
    conventional_injection_resources: tuple[NativeChartPoint, ...]
    mrt_injection_resources: tuple[NativeChartPoint, ...]
    conventional_uptake_resources: tuple[NativeChartPoint, ...]
    mrt_uptake_resources: tuple[NativeChartPoint, ...]
    conventional_distribution_concurrency: tuple[NativeChartPoint, ...]
    mrt_distribution_concurrency: tuple[NativeChartPoint, ...]
    mrt_operated_carriers: tuple[NativeChartPoint, ...]
    strategy_lifecycle_npv_comparison: tuple[NativeChartPoint, ...]
    strategy_capex_comparison: tuple[NativeChartPoint, ...]
    strategy_opex_comparison: tuple[NativeChartPoint, ...]


@dataclass(frozen=True)
class NativeDesignHorizonReportData:
    metadata: NativeHorizonMetadata
    demand_trajectory_rows: tuple[NativeHorizonDemandYearRecord, ...]
    conventional_year_rows: tuple[NativeHorizonPathwayYearRecord, ...]
    mrt_year_rows: tuple[NativeHorizonPathwayYearRecord, ...]
    year_comparison_rows: tuple[NativeHorizonYearComparisonRecord, ...]
    conventional_expansion_decisions: tuple[NativeHorizonExpansionDecisionRecord, ...]
    mrt_expansion_decisions: tuple[NativeHorizonExpansionDecisionRecord, ...]
    conventional_exhaustion: NativeHorizonCapacityExhaustionRecord
    mrt_exhaustion: NativeHorizonCapacityExhaustionRecord
    bottleneck_year_states: tuple[NativeHorizonBottleneckYearState, ...]
    bottleneck_migration_events: tuple[NativeHorizonBottleneckMigrationEvent, ...]
    build_ahead_conventional: NativeHorizonStrategyPathwaySummary
    build_ahead_mrt: NativeHorizonStrategyPathwaySummary
    phased_conventional: NativeHorizonStrategyPathwaySummary
    phased_mrt: NativeHorizonStrategyPathwaySummary
    strategy_comparison_by_pathway: Mapping[Pathway, NativeHorizonPathwayStrategyComparison]
    final_comparison: NativeHorizonFinalComparison
    chart_series: NativeHorizonChartSeries
    provenance: Mapping[str, Any]
    derived_value_notes: tuple[str, ...]


def _split_combo_action(resource: str, step: int) -> tuple[NativeHorizonExpansionResourceDelta, ...]:
    if resource.startswith("combo(") and resource.endswith(")"):
        payload = resource[6:-1].strip()
        if not payload:
            return ()
        changes: list[NativeHorizonExpansionResourceDelta] = []
        for token in payload.split(","):
            part = token.strip()
            if "=" not in part:
                continue
            name, amount = part.split("=", 1)
            changes.append(NativeHorizonExpansionResourceDelta(resource=name.strip(), step=int(amount.strip())))
        return tuple(changes)
    return (NativeHorizonExpansionResourceDelta(resource=resource, step=step),)


def _year_rows_by_pathway(result: DesignHorizonPlanningResult, pathway: Pathway) -> tuple[Any, ...]:
    rows: list[Any] = []
    for year in result.year_results:
        rows.append(year.conventional if pathway == "Conventional" else year.mrt)
    return tuple(rows)


def _resource_state_timeline(result: DesignHorizonPlanningResult, pathway: Pathway) -> tuple[NativeHorizonResourceState, ...]:
    scenario = result.request.pipeline_template
    architecture = scenario.conventional if pathway == "Conventional" else scenario.mrt
    states: list[NativeHorizonResourceState] = []
    for year in result.year_results:
        pathway_row = year.conventional if pathway == "Conventional" else year.mrt
        for action in pathway_row.expansion_actions:
            architecture = _apply_resource_step(pathway, architecture, action.resource, action.step)
        installed_carriers = int(architecture.installed_mrt_carriers or 0)
        operated_carriers = int(architecture.operated_mrt_carriers or 0)
        states.append(
            NativeHorizonResourceState(
                scanners=int(architecture.scanners),
                injection_resources=int(architecture.injection_resources),
                uptake_resources=int(architecture.uptake_resources),
                distribution_concurrency=int(architecture.distribution_concurrency),
                installed_mrt_carriers=installed_carriers,
                operated_mrt_carriers=operated_carriers,
                spare_mrt_carriers=installed_carriers - operated_carriers,
                installed_mrt_endpoints=int(architecture.installed_mrt_endpoints),
                installed_guideway_length_m=float(architecture.installed_guideway_length_m),
                cyclotron_units=int(architecture.operated_cyclotron_units),
            )
        )
    return tuple(states)


def _annual_revenue_from_row(result: DesignHorizonPlanningResult, served_per_day: float) -> float:
    assumptions = result.request.pipeline_template.planner_assumptions
    return float(served_per_day) * float(assumptions.revenue_per_scan) * float(assumptions.operating_days_per_year)


def _horizon_pathway_rows(
    result: DesignHorizonPlanningResult,
    pathway: Pathway,
    *,
    fleet_id: str,
    fleet_asset_ids: tuple[str, ...],
    fleet_supported_radionuclides: tuple[str, ...],
) -> tuple[NativeHorizonPathwayYearRecord, ...]:
    native_rows = _year_rows_by_pathway(result, pathway)
    states = _resource_state_timeline(result, pathway)
    output: list[NativeHorizonPathwayYearRecord] = []
    for index, native_row in enumerate(native_rows):
        state = states[index]
        output.append(
            NativeHorizonPathwayYearRecord(
                pathway=pathway,
                year=index + 1,
                demand_patients_per_day=float(native_row.demand_per_day),
                installed_reliable_effective_capacity_patients_per_day=float(native_row.installed_capacity_per_day),
                patients_served_per_day=float(native_row.patients_served_per_day),
                unmet_demand_per_day=float(native_row.unmet_demand_per_day),
                headroom_per_day=float(native_row.headroom_per_day),
                capacity_utilization_pct=float(native_row.capacity_utilization_pct),
                probability_meeting_target_demand=float(native_row.reliability_probability_meeting_target),
                binding_bottleneck_resource=str(native_row.binding_bottleneck_resource),
                annual_opex=float(native_row.annual_opex),
                annual_revenue=_annual_revenue_from_row(result, float(native_row.patients_served_per_day)),
                annual_expansion_capex=float(native_row.annual_capex),
                resources=state,
                fleet_id=fleet_id,
                fleet_asset_ids=fleet_asset_ids,
                fleet_supported_radionuclides=fleet_supported_radionuclides,
            )
        )
    return tuple(output)


def _expansion_decisions(result: DesignHorizonPlanningResult, pathway: Pathway) -> tuple[NativeHorizonExpansionDecisionRecord, ...]:
    native_rows = _year_rows_by_pathway(result, pathway)
    decisions: list[NativeHorizonExpansionDecisionRecord] = []
    prior_capacity: float | None = None
    prior_reliability: float | None = None
    prior_bottleneck: str | None = None
    for year_index, native_row in enumerate(native_rows, start=1):
        gains = [float(action.throughput_gain_per_day) for action in native_row.expansion_actions]
        running_capacity = float(native_row.installed_capacity_per_day) - sum(gains)
        for action_index, action in enumerate(native_row.expansion_actions, start=1):
            action_type: Literal["single_resource", "multi_resource_combo"] = (
                "multi_resource_combo" if action.resource.startswith("combo(") else "single_resource"
            )
            resources_changed = _split_combo_action(action.resource, action.step)
            pre_capacity = running_capacity
            post_capacity = pre_capacity + float(action.throughput_gain_per_day)
            running_capacity = post_capacity
            is_last_action = action_index == len(native_row.expansion_actions)
            post_reliability = float(native_row.reliability_probability_meeting_target) if is_last_action else None
            pre_reliability = prior_reliability if action_index == 1 else None
            reliability_delta = (
                None
                if pre_reliability is None or post_reliability is None
                else float(post_reliability - pre_reliability)
            )
            bottleneck_before = prior_bottleneck if action_index == 1 else None
            bottleneck_after = str(native_row.binding_bottleneck_resource) if is_last_action else None

            decisions.append(
                NativeHorizonExpansionDecisionRecord(
                    year=year_index,
                    pathway=pathway,
                    decision_id=f"{pathway}-Y{year_index}-A{action_index}",
                    action_identifier=action.resource,
                    action_type=action_type,
                    resources_changed=resources_changed,
                    pre_expansion_capacity=pre_capacity,
                    post_expansion_capacity=post_capacity,
                    capacity_delta=float(action.throughput_gain_per_day),
                    pre_expansion_reliability=pre_reliability,
                    post_expansion_reliability=post_reliability,
                    reliability_delta=reliability_delta,
                    bottleneck_before=bottleneck_before,
                    bottleneck_after=bottleneck_after,
                    incremental_capex=float(action.annual_capex_delta),
                    incremental_annual_opex=float(action.annual_opex_delta),
                    reason=action.reason,
                    trace_id=action.trace_id,
                )
            )

        prior_capacity = float(native_row.installed_capacity_per_day)
        prior_reliability = float(native_row.reliability_probability_meeting_target)
        prior_bottleneck = str(native_row.binding_bottleneck_resource)
    return tuple(decisions)


def _exhaustion_record(pathway: Pathway, rows: Sequence[NativeHorizonPathwayYearRecord]) -> NativeHorizonCapacityExhaustionRecord:
    for row in rows:
        if row.unmet_demand_per_day > 0.0:
            return NativeHorizonCapacityExhaustionRecord(
                pathway=pathway,
                exhaustion_within_horizon=True,
                first_exhaustion_year=row.year,
                demand_at_exhaustion=row.demand_patients_per_day,
                capacity_at_exhaustion=row.installed_reliable_effective_capacity_patients_per_day,
                headroom_at_exhaustion=row.headroom_per_day,
                reliability_at_exhaustion=row.probability_meeting_target_demand,
                bottleneck_at_exhaustion=row.binding_bottleneck_resource,
            )
    return NativeHorizonCapacityExhaustionRecord(
        pathway=pathway,
        exhaustion_within_horizon=False,
        first_exhaustion_year=None,
        demand_at_exhaustion=None,
        capacity_at_exhaustion=None,
        headroom_at_exhaustion=None,
        reliability_at_exhaustion=None,
        bottleneck_at_exhaustion=None,
    )


def _bottleneck_contract(
    conventional_rows: Sequence[NativeHorizonPathwayYearRecord],
    mrt_rows: Sequence[NativeHorizonPathwayYearRecord],
) -> tuple[tuple[NativeHorizonBottleneckYearState, ...], tuple[NativeHorizonBottleneckMigrationEvent, ...]]:
    year_states: list[NativeHorizonBottleneckYearState] = []
    events: list[NativeHorizonBottleneckMigrationEvent] = []
    for pathway, rows in (("Conventional", conventional_rows), ("MRT", mrt_rows)):
        previous: str | None = None
        for row in rows:
            year_states.append(
                NativeHorizonBottleneckYearState(pathway=pathway, year=row.year, bottleneck=row.binding_bottleneck_resource)
            )
            if previous is not None and previous != row.binding_bottleneck_resource:
                events.append(
                    NativeHorizonBottleneckMigrationEvent(
                        pathway=pathway,
                        year=row.year,
                        previous_bottleneck=previous,
                        new_bottleneck=row.binding_bottleneck_resource,
                    )
                )
            previous = row.binding_bottleneck_resource
    return tuple(year_states), tuple(events)


def _strategy_summary(
    *,
    result: DesignHorizonPlanningResult,
    pathway: Pathway,
    strategy: Literal["build_ahead", "phased"],
    rows: Sequence[NativeHorizonPathwayYearRecord],
) -> NativeHorizonStrategyPathwaySummary:
    lifecycle = (
        result.build_ahead_strategy.conventional_lifecycle
        if strategy == "build_ahead" and pathway == "Conventional"
        else result.build_ahead_strategy.mrt_lifecycle
        if strategy == "build_ahead"
        else result.phased_strategy.conventional_lifecycle
        if pathway == "Conventional"
        else result.phased_strategy.mrt_lifecycle
    )
    comparison = result.strategy_comparison_by_pathway[pathway]
    feasible = bool(comparison.phased_feasible) if strategy == "phased" else bool(comparison.build_ahead_feasible)
    infeasibility_reason = comparison.phased_infeasibility_reason if strategy == "phased" else comparison.build_ahead_infeasibility_reason
    if strategy == "build_ahead":
        # Native build-ahead encodes Year-0 sizing into the first modeled year CAPEX row.
        # Reporting normalizes this to Year-0 so future interventions remain zero.
        staged_year_zero_incremental_capex = sum(float(row.annual_capex) for row in lifecycle.annual_rows)
        year_zero_capex = float(lifecycle.initial_capex) + staged_year_zero_incremental_capex
        intervention_years = tuple(row.year for row in lifecycle.annual_rows[1:] if float(row.annual_capex) > 0.0)
        future_nominal = sum(float(row.annual_capex) for row in lifecycle.annual_rows[1:])
        future_pv = sum(float(row.discounted_capex) for row in lifecycle.annual_rows[1:])
    else:
        year_zero_capex = float(lifecycle.initial_capex)
        intervention_years = tuple(row.year for row in lifecycle.annual_rows if float(row.annual_capex) > 0.0)
        future_nominal = sum(float(row.annual_capex) for row in lifecycle.annual_rows)
        future_pv = sum(float(row.discounted_capex) for row in lifecycle.annual_rows)
    final_row = rows[-1]
    return NativeHorizonStrategyPathwaySummary(
        pathway=pathway,
        strategy=strategy,
        feasible=feasible,
        infeasibility_reason=infeasibility_reason,
        horizon_peak_demand=max(float(value) for value in result.demand_trajectory.daily_demand_by_year),
        year_zero_installed_capacity=float(lifecycle.annual_rows[0].installed_capacity_per_day),
        final_modeled_capacity=float(lifecycle.annual_rows[-1].installed_capacity_per_day),
        year_zero_capex=year_zero_capex,
        nominal_future_expansion_capex=float(future_nominal),
        discounted_pv_future_expansion_capex=float(future_pv),
        total_horizon_opex=float(sum(float(row.annual_opex) for row in lifecycle.annual_rows)),
        total_horizon_revenue=float(sum(float(row.annual_revenue) for row in lifecycle.annual_rows)),
        lifecycle_npv=float(lifecycle.final_npv),
        payback_year=lifecycle.payback_year,
        expansion_intervention_count=len(intervention_years),
        expansion_intervention_years=intervention_years,
        final_headroom=float(final_row.headroom_per_day),
        final_bottleneck=final_row.binding_bottleneck_resource,
    )


def _strategy_reason(summary: NativeHorizonPathwayStrategyComparison) -> str | None:
    if summary.preferred_strategy == "no_feasible_strategy":
        return "Neither native horizon strategy met the required capacity/reliability contract within bounded expansion limits."
    if not summary.build_ahead_feasible:
        return "Build-ahead infeasible in native horizon engine; phased retained only if it remained feasible."
    if summary.preferred_strategy == "build_ahead":
        return "Native horizon engine selected build_ahead based on pathway lifecycle comparison."
    if summary.preferred_strategy == "phased":
        return "Native horizon engine selected phased based on pathway lifecycle comparison."
    return "Native horizon engine reported strategy tie."


def _year_comparisons(
    conventional_rows: Sequence[NativeHorizonPathwayYearRecord],
    mrt_rows: Sequence[NativeHorizonPathwayYearRecord],
) -> tuple[NativeHorizonYearComparisonRecord, ...]:
    rows: list[NativeHorizonYearComparisonRecord] = []
    for conventional, mrt in zip(conventional_rows, mrt_rows):
        rows.append(
            NativeHorizonYearComparisonRecord(
                year=conventional.year,
                demand_patients_per_day=conventional.demand_patients_per_day,
                conventional_capacity=conventional.installed_reliable_effective_capacity_patients_per_day,
                mrt_capacity=mrt.installed_reliable_effective_capacity_patients_per_day,
                capacity_delta_mrt_minus_conventional=(
                    mrt.installed_reliable_effective_capacity_patients_per_day
                    - conventional.installed_reliable_effective_capacity_patients_per_day
                ),
                conventional_headroom=conventional.headroom_per_day,
                mrt_headroom=mrt.headroom_per_day,
                headroom_delta_mrt_minus_conventional=mrt.headroom_per_day - conventional.headroom_per_day,
                conventional_reliability=conventional.probability_meeting_target_demand,
                mrt_reliability=mrt.probability_meeting_target_demand,
                reliability_delta_mrt_minus_conventional=(
                    mrt.probability_meeting_target_demand - conventional.probability_meeting_target_demand
                ),
                conventional_annual_opex=conventional.annual_opex,
                mrt_annual_opex=mrt.annual_opex,
                opex_delta_mrt_minus_conventional=mrt.annual_opex - conventional.annual_opex,
                conventional_annual_revenue=conventional.annual_revenue,
                mrt_annual_revenue=mrt.annual_revenue,
                revenue_delta_mrt_minus_conventional=mrt.annual_revenue - conventional.annual_revenue,
                conventional_expansion_capex=conventional.annual_expansion_capex,
                mrt_expansion_capex=mrt.annual_expansion_capex,
                conventional_bottleneck=conventional.binding_bottleneck_resource,
                mrt_bottleneck=mrt.binding_bottleneck_resource,
            )
        )
    return tuple(rows)


def _categorical_bottleneck_series(rows: Sequence[NativeHorizonPathwayYearRecord]) -> tuple[NativeCategoricalChartItem, ...]:
    counts: dict[str, float] = {}
    for row in rows:
        counts[row.binding_bottleneck_resource] = counts.get(row.binding_bottleneck_resource, 0.0) + 1.0
    return _categorical_items(counts)


def _chart_series(
    demand_rows: Sequence[NativeHorizonDemandYearRecord],
    conventional_rows: Sequence[NativeHorizonPathwayYearRecord],
    mrt_rows: Sequence[NativeHorizonPathwayYearRecord],
    build_ahead_conventional: NativeHorizonStrategyPathwaySummary,
    build_ahead_mrt: NativeHorizonStrategyPathwaySummary,
    phased_conventional: NativeHorizonStrategyPathwaySummary,
    phased_mrt: NativeHorizonStrategyPathwaySummary,
) -> NativeHorizonChartSeries:
    conventional_cum = 0.0
    mrt_cum = 0.0
    conventional_cum_points: list[NativeChartPoint] = []
    mrt_cum_points: list[NativeChartPoint] = []
    for conv, mrt in zip(conventional_rows, mrt_rows):
        conventional_cum += conv.annual_expansion_capex
        mrt_cum += mrt.annual_expansion_capex
        conventional_cum_points.append(NativeChartPoint(x=float(conv.year), y=conventional_cum))
        mrt_cum_points.append(NativeChartPoint(x=float(mrt.year), y=mrt_cum))

    return NativeHorizonChartSeries(
        demand=tuple(NativeChartPoint(x=float(row.year), y=float(row.demand_patients_per_day)) for row in demand_rows),
        conventional_capacity=tuple(
            NativeChartPoint(x=float(row.year), y=row.installed_reliable_effective_capacity_patients_per_day)
            for row in conventional_rows
        ),
        mrt_capacity=tuple(
            NativeChartPoint(x=float(row.year), y=row.installed_reliable_effective_capacity_patients_per_day)
            for row in mrt_rows
        ),
        conventional_headroom=tuple(NativeChartPoint(x=float(row.year), y=row.headroom_per_day) for row in conventional_rows),
        mrt_headroom=tuple(NativeChartPoint(x=float(row.year), y=row.headroom_per_day) for row in mrt_rows),
        conventional_reliability=tuple(
            NativeChartPoint(x=float(row.year), y=row.probability_meeting_target_demand) for row in conventional_rows
        ),
        mrt_reliability=tuple(NativeChartPoint(x=float(row.year), y=row.probability_meeting_target_demand) for row in mrt_rows),
        conventional_annual_opex=tuple(NativeChartPoint(x=float(row.year), y=row.annual_opex) for row in conventional_rows),
        mrt_annual_opex=tuple(NativeChartPoint(x=float(row.year), y=row.annual_opex) for row in mrt_rows),
        conventional_annual_revenue=tuple(NativeChartPoint(x=float(row.year), y=row.annual_revenue) for row in conventional_rows),
        mrt_annual_revenue=tuple(NativeChartPoint(x=float(row.year), y=row.annual_revenue) for row in mrt_rows),
        conventional_expansion_capex=tuple(
            NativeChartPoint(x=float(row.year), y=row.annual_expansion_capex) for row in conventional_rows
        ),
        mrt_expansion_capex=tuple(NativeChartPoint(x=float(row.year), y=row.annual_expansion_capex) for row in mrt_rows),
        conventional_cumulative_expansion_capex=tuple(conventional_cum_points),
        mrt_cumulative_expansion_capex=tuple(mrt_cum_points),
        conventional_bottleneck_by_year=_categorical_bottleneck_series(conventional_rows),
        mrt_bottleneck_by_year=_categorical_bottleneck_series(mrt_rows),
        conventional_scanners=tuple(NativeChartPoint(x=float(row.year), y=float(row.resources.scanners)) for row in conventional_rows),
        mrt_scanners=tuple(NativeChartPoint(x=float(row.year), y=float(row.resources.scanners)) for row in mrt_rows),
        conventional_injection_resources=tuple(
            NativeChartPoint(x=float(row.year), y=float(row.resources.injection_resources)) for row in conventional_rows
        ),
        mrt_injection_resources=tuple(
            NativeChartPoint(x=float(row.year), y=float(row.resources.injection_resources)) for row in mrt_rows
        ),
        conventional_uptake_resources=tuple(
            NativeChartPoint(x=float(row.year), y=float(row.resources.uptake_resources)) for row in conventional_rows
        ),
        mrt_uptake_resources=tuple(
            NativeChartPoint(x=float(row.year), y=float(row.resources.uptake_resources)) for row in mrt_rows
        ),
        conventional_distribution_concurrency=tuple(
            NativeChartPoint(x=float(row.year), y=float(row.resources.distribution_concurrency)) for row in conventional_rows
        ),
        mrt_distribution_concurrency=tuple(
            NativeChartPoint(x=float(row.year), y=float(row.resources.distribution_concurrency)) for row in mrt_rows
        ),
        mrt_operated_carriers=tuple(
            NativeChartPoint(x=float(row.year), y=float(row.resources.operated_mrt_carriers)) for row in mrt_rows
        ),
        strategy_lifecycle_npv_comparison=(
            NativeChartPoint(x=0.0, y=build_ahead_conventional.lifecycle_npv, label="Conventional build_ahead"),
            NativeChartPoint(x=1.0, y=phased_conventional.lifecycle_npv, label="Conventional phased"),
            NativeChartPoint(x=2.0, y=build_ahead_mrt.lifecycle_npv, label="MRT build_ahead"),
            NativeChartPoint(x=3.0, y=phased_mrt.lifecycle_npv, label="MRT phased"),
        ),
        strategy_capex_comparison=(
            NativeChartPoint(
                x=0.0,
                y=build_ahead_conventional.year_zero_capex + build_ahead_conventional.nominal_future_expansion_capex,
                label="Conventional build_ahead",
            ),
            NativeChartPoint(
                x=1.0,
                y=phased_conventional.year_zero_capex + phased_conventional.nominal_future_expansion_capex,
                label="Conventional phased",
            ),
            NativeChartPoint(
                x=2.0,
                y=build_ahead_mrt.year_zero_capex + build_ahead_mrt.nominal_future_expansion_capex,
                label="MRT build_ahead",
            ),
            NativeChartPoint(
                x=3.0,
                y=phased_mrt.year_zero_capex + phased_mrt.nominal_future_expansion_capex,
                label="MRT phased",
            ),
        ),
        strategy_opex_comparison=(
            NativeChartPoint(x=0.0, y=build_ahead_conventional.total_horizon_opex, label="Conventional build_ahead"),
            NativeChartPoint(x=1.0, y=phased_conventional.total_horizon_opex, label="Conventional phased"),
            NativeChartPoint(x=2.0, y=build_ahead_mrt.total_horizon_opex, label="MRT build_ahead"),
            NativeChartPoint(x=3.0, y=phased_mrt.total_horizon_opex, label="MRT phased"),
        ),
    )


def build_native_design_horizon_report_data(result: DesignHorizonPlanningResult) -> NativeDesignHorizonReportData:
    scenario = result.request.pipeline_template
    assumptions = scenario.planner_assumptions
    fleet = scenario.cyclotron_fleet
    fleet_id = "PRIMARY_FLEET" if fleet is None else fleet.fleet_id
    fleet_asset_ids = () if fleet is None else tuple(asset.cyclotron_id for asset in fleet.assets)
    fleet_supported = (
        tuple(scenario.cyclotron_capability.supported_radionuclides)
        if fleet is None
        else tuple(fleet.fleet_supported_radionuclides)
    )

    metadata = NativeHorizonMetadata(
        project_name=scenario.project_name,
        analysis_years=int(result.demand_trajectory.analysis_years),
        demand_mode=str(result.request.demand_mode),
        demand_trajectory_source=str(result.demand_trajectory.source),
        demand_trajectory_interpolation_method=str(result.demand_trajectory.interpolation_method),
        seeds=tuple(int(seed) for seed in result.request.seeds),
        operating_days_per_year=int(assumptions.operating_days_per_year),
        revenue_per_scan=float(assumptions.revenue_per_scan),
        discount_rate_pct=float(assumptions.discount_rate_pct),
        horizon_trace_id=result.trace_id,
    )

    demand_rows = tuple(
        NativeHorizonDemandYearRecord(year=index + 1, demand_patients_per_day=float(value))
        for index, value in enumerate(result.demand_trajectory.daily_demand_by_year)
    )

    conventional_rows = _horizon_pathway_rows(
        result,
        "Conventional",
        fleet_id=fleet_id,
        fleet_asset_ids=fleet_asset_ids,
        fleet_supported_radionuclides=fleet_supported,
    )
    mrt_rows = _horizon_pathway_rows(
        result,
        "MRT",
        fleet_id=fleet_id,
        fleet_asset_ids=fleet_asset_ids,
        fleet_supported_radionuclides=fleet_supported,
    )

    conventional_expansions = _expansion_decisions(result, "Conventional")
    mrt_expansions = _expansion_decisions(result, "MRT")

    conventional_exhaustion = _exhaustion_record("Conventional", conventional_rows)
    mrt_exhaustion = _exhaustion_record("MRT", mrt_rows)

    bottleneck_year_states, bottleneck_events = _bottleneck_contract(conventional_rows, mrt_rows)

    build_ahead_conventional = _strategy_summary(
        result=result,
        pathway="Conventional",
        strategy="build_ahead",
        rows=conventional_rows,
    )
    build_ahead_mrt = _strategy_summary(
        result=result,
        pathway="MRT",
        strategy="build_ahead",
        rows=mrt_rows,
    )
    phased_conventional = _strategy_summary(
        result=result,
        pathway="Conventional",
        strategy="phased",
        rows=conventional_rows,
    )
    phased_mrt = _strategy_summary(
        result=result,
        pathway="MRT",
        strategy="phased",
        rows=mrt_rows,
    )

    strategy_comparison: dict[Pathway, NativeHorizonPathwayStrategyComparison] = {}
    for pathway in ("Conventional", "MRT"):
        native = result.strategy_comparison_by_pathway[pathway]
        build_summary = build_ahead_conventional if pathway == "Conventional" else build_ahead_mrt
        phased_summary = phased_conventional if pathway == "Conventional" else phased_mrt
        strategy_row = NativeHorizonPathwayStrategyComparison(
            pathway=pathway,
            build_ahead_feasible=bool(native.build_ahead_feasible),
            phased_feasible=bool(native.phased_feasible),
            build_ahead_npv=float(native.build_ahead_final_npv),
            phased_npv=float(native.phased_final_npv),
            npv_delta_build_ahead_minus_phased=float(native.incremental_npv_build_ahead_minus_phased),
            capex_delta_build_ahead_minus_phased=float(
                (build_summary.year_zero_capex + build_summary.nominal_future_expansion_capex)
                - (phased_summary.year_zero_capex + phased_summary.nominal_future_expansion_capex)
            ),
            opex_delta_build_ahead_minus_phased=float(build_summary.total_horizon_opex - phased_summary.total_horizon_opex),
            intervention_count_delta_build_ahead_minus_phased=(
                build_summary.expansion_intervention_count - phased_summary.expansion_intervention_count
            ),
            preferred_strategy=str(native.preferred_strategy),
            recommendation_reason=None,
        )
        strategy_comparison[pathway] = NativeHorizonPathwayStrategyComparison(
            **{**strategy_row.__dict__, "recommendation_reason": _strategy_reason(strategy_row)}
        )

    year_comparison_rows = _year_comparisons(conventional_rows, mrt_rows)

    final_comparison = NativeHorizonFinalComparison(
        final_year=conventional_rows[-1].year,
        final_demand=conventional_rows[-1].demand_patients_per_day,
        conventional_final_capacity=conventional_rows[-1].installed_reliable_effective_capacity_patients_per_day,
        mrt_final_capacity=mrt_rows[-1].installed_reliable_effective_capacity_patients_per_day,
        conventional_final_headroom=conventional_rows[-1].headroom_per_day,
        mrt_final_headroom=mrt_rows[-1].headroom_per_day,
        conventional_cumulative_expansion_capex=sum(row.annual_expansion_capex for row in conventional_rows),
        mrt_cumulative_expansion_capex=sum(row.annual_expansion_capex for row in mrt_rows),
        conventional_lifecycle_npv=float(result.phased_strategy.conventional_lifecycle.final_npv),
        mrt_lifecycle_npv=float(result.phased_strategy.mrt_lifecycle.final_npv),
        lifecycle_npv_delta_mrt_minus_conventional=float(
            result.phased_strategy.pathway_comparison.incremental_final_npv_mrt_minus_conventional
        ),
        conventional_intervention_count=len(conventional_expansions),
        mrt_intervention_count=len(mrt_expansions),
        pathway_strategy_preference={
            "Conventional": strategy_comparison["Conventional"].preferred_strategy,
            "MRT": strategy_comparison["MRT"].preferred_strategy,
        },
    )

    chart_series = _chart_series(
        demand_rows,
        conventional_rows,
        mrt_rows,
        build_ahead_conventional,
        build_ahead_mrt,
        phased_conventional,
        phased_mrt,
    )

    provenance: dict[str, Any] = {
        "horizon_trace_id": result.trace_id,
        "request_project_name": scenario.project_name,
        "seed_set": tuple(int(seed) for seed in result.request.seeds),
        "pipeline_cyclotron_id": scenario.cyclotron_capability.cyclotron_id,
        "fleet_id": fleet_id,
        "fleet_asset_ids": fleet_asset_ids,
        "fleet_supported_radionuclides": fleet_supported,
        "build_ahead_strategy": {
            "conventional_feasible": result.strategy_comparison_by_pathway["Conventional"].build_ahead_feasible,
            "mrt_feasible": result.strategy_comparison_by_pathway["MRT"].build_ahead_feasible,
        },
        "expansion_trace_ids": {
            "conventional": tuple(decision.trace_id for decision in conventional_expansions),
            "mrt": tuple(decision.trace_id for decision in mrt_expansions),
        },
    }

    return NativeDesignHorizonReportData(
        metadata=metadata,
        demand_trajectory_rows=demand_rows,
        conventional_year_rows=conventional_rows,
        mrt_year_rows=mrt_rows,
        year_comparison_rows=year_comparison_rows,
        conventional_expansion_decisions=conventional_expansions,
        mrt_expansion_decisions=mrt_expansions,
        conventional_exhaustion=conventional_exhaustion,
        mrt_exhaustion=mrt_exhaustion,
        bottleneck_year_states=bottleneck_year_states,
        bottleneck_migration_events=bottleneck_events,
        build_ahead_conventional=build_ahead_conventional,
        build_ahead_mrt=build_ahead_mrt,
        phased_conventional=phased_conventional,
        phased_mrt=phased_mrt,
        strategy_comparison_by_pathway=strategy_comparison,
        final_comparison=final_comparison,
        chart_series=chart_series,
        provenance=provenance,
        derived_value_notes=(
            "Reporting-only arithmetic includes deltas, annual revenue (served * revenue_per_scan * operating_days_per_year), and cumulative sums.",
            "Expansion pre/post reliability per action is only directly native for the year-level post value; non-native intermediate reliability values remain null.",
            "Expansion pre/post bottleneck per action uses adjacent year-level native bottlenecks when available.",
        ),
    )
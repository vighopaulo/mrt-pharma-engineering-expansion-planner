from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

from diagnostics import load_radionuclide_half_lives
from multi_isotope_decay import retained_fraction


ProjectMode = Literal["GREENFIELD", "EXISTING_FACILITY_EXPANSION"]
ProjectSupplyMode = Literal["ON_SITE_PRODUCTION", "EXTERNAL_SUPPLY"]
SupplySourceType = Literal["CYCLOTRON", "GENERATOR", "OTHER_EXTERNAL_SOURCE"]
ProductionMode = Literal["ON_SITE", "EXTERNAL", "HYBRID"]
ReleaseActivityBasis = Literal["MBQ_AT_SOURCE_RELEASE"]
ReleaseTimeBasis = Literal["SOURCE_RELEASE_TIMESTAMP"]
DataStatus = Literal["KNOWN", "USER_ASSUMED", "EVIDENCE_BACKED", "UNKNOWN", "NOT_CALIBRATED"]
ValueStatus = Literal["DEFAULT_MODEL_VALUE", "USER_OVERRIDE", "NOT_CALIBRATED"]

TransportSegmentType = Literal[
    "ORIGIN_HANDLING",
    "AIR_TRANSPORT",
    "DESTINATION_HANDLING",
    "LAST_MILE_TRANSFER",
]
TransportMode = Literal["GROUND", "AIR", "MRT"]
SegmentDesignation = Literal["COMMON_PREFIX", "CONVENTIONAL_LAST_MILE", "MRT_LAST_MILE"]

ExternalSupplyFeasibilityStatus = Literal[
    "FEASIBLE",
    "INSUFFICIENT_UPSTREAM_ACTIVITY",
    "UNSUPPORTED_RADIONUCLIDE",
    "TRANSPORT_TIME_NOT_CALIBRATED",
    "SUPPLY_CAPACITY_NOT_CALIBRATED",
    "INFEASIBLE_DECAY_COMPENSATION",
]

PathwayOperationalState = Literal[
    "PHYSICALLY_FEASIBLE",
    "CAPACITY_NOT_CALIBRATED",
    "CAPACITY_SHORTFALL",
    "TRANSPORT_NOT_CALIBRATED",
    "UNSUPPORTED_RADIONUCLIDE",
    "INFEASIBLE_DECAY_COMPENSATION",
]


@dataclass(frozen=True)
class EconomicValueProvenance:
    parameter_name: str
    value: float | None
    value_status: ValueStatus
    default_reference_value: float | None


@dataclass(frozen=True)
class ResourceDeltaRow:
    resource: str
    existing_quantity: float | None
    existing_quantity_status: DataStatus
    retained_usable_existing_quantity: float | None
    final_required_quantity: float | None
    additional_required_quantity: float | None


@dataclass(frozen=True)
class ExternalSupplySource:
    source_id: str
    source_name: str
    source_type: SupplySourceType
    location_label: str
    supported_radionuclides: tuple[str, ...]
    production_mode: ProductionMode
    release_activity_basis: ReleaseActivityBasis = "MBQ_AT_SOURCE_RELEASE"
    release_time_basis: ReleaseTimeBasis = "SOURCE_RELEASE_TIMESTAMP"
    provenance_status: DataStatus = "USER_ASSUMED"
    provenance_reference_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id must be non-empty")
        if not self.source_name.strip():
            raise ValueError("source_name must be non-empty")
        if not self.location_label.strip():
            raise ValueError("location_label must be non-empty")
        if not self.supported_radionuclides:
            raise ValueError("supported_radionuclides must not be empty")


@dataclass(frozen=True)
class ExternalSupplyTransportSegment:
    segment_id: str
    segment_type: TransportSegmentType
    designation: SegmentDesignation
    origin_label: str
    destination_label: str
    distance_km: float | None
    duration_minutes: float | None
    handling_minutes: float = 0.0
    transport_mode: TransportMode = "GROUND"
    active: bool = True
    provenance_status: DataStatus = "USER_ASSUMED"
    provenance_reference_ids: tuple[str, ...] = ()
    assumption_label: str | None = None

    def __post_init__(self) -> None:
        if not self.segment_id.strip():
            raise ValueError("segment_id must be non-empty")
        if not self.origin_label.strip():
            raise ValueError("origin_label must be non-empty")
        if not self.destination_label.strip():
            raise ValueError("destination_label must be non-empty")
        if self.distance_km is not None and self.distance_km < 0.0:
            raise ValueError("distance_km must be non-negative when provided")
        if self.duration_minutes is not None and self.duration_minutes < 0.0:
            raise ValueError("duration_minutes must be non-negative when provided")
        if self.handling_minutes < 0.0:
            raise ValueError("handling_minutes must be non-negative")


@dataclass(frozen=True)
class ReceivingHospitalWorkflow:
    receiving_radiopharmacy_units: int
    injection_resources: int
    uptake_resources: int
    scanners: int
    conventional_internal_distribution_minutes: float
    mrt_internal_distribution_minutes: float
    administration_minutes: float
    on_site_cyclotron_units: int = 0
    on_site_cyclotron_inventory_status: DataStatus = "KNOWN"
    provenance_status: DataStatus = "USER_ASSUMED"
    provenance_reference_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.receiving_radiopharmacy_units < 0:
            raise ValueError("receiving_radiopharmacy_units must be non-negative")
        if self.injection_resources < 0:
            raise ValueError("injection_resources must be non-negative")
        if self.uptake_resources < 0:
            raise ValueError("uptake_resources must be non-negative")
        if self.scanners < 0:
            raise ValueError("scanners must be non-negative")
        if self.conventional_internal_distribution_minutes < 0.0:
            raise ValueError("conventional_internal_distribution_minutes must be non-negative")
        if self.mrt_internal_distribution_minutes < 0.0:
            raise ValueError("mrt_internal_distribution_minutes must be non-negative")
        if self.administration_minutes < 0.0:
            raise ValueError("administration_minutes must be non-negative")
        if self.on_site_cyclotron_units < 0:
            raise ValueError("on_site_cyclotron_units must be non-negative")
        if self.on_site_cyclotron_inventory_status in {"UNKNOWN", "NOT_CALIBRATED"} and self.on_site_cyclotron_units != 0:
            raise ValueError("unknown cyclotron inventory cannot specify a non-zero quantity")


@dataclass(frozen=True)
class ExternalSupplyEconomicInputs:
    external_product_supply_cost_per_year: float | None = None
    air_transport_cost_per_year: float | None = None
    airport_handling_cost_per_year: float | None = None
    conventional_last_mile_cost_per_year: float | None = None
    mrt_last_mile_incremental_capex: float | None = None
    mrt_last_mile_opex_per_year: float | None = None
    receiving_infrastructure_incremental_capex: float | None = None
    discount_rate_pct: float | None = None
    analysis_years: int | None = None

    def __post_init__(self) -> None:
        fields = (
            self.external_product_supply_cost_per_year,
            self.air_transport_cost_per_year,
            self.airport_handling_cost_per_year,
            self.conventional_last_mile_cost_per_year,
            self.mrt_last_mile_incremental_capex,
            self.mrt_last_mile_opex_per_year,
            self.receiving_infrastructure_incremental_capex,
        )
        if any(value is not None and value < 0.0 for value in fields):
            raise ValueError("economic input costs must be non-negative when provided")
        if self.discount_rate_pct is not None and self.discount_rate_pct < 0.0:
            raise ValueError("discount_rate_pct must be non-negative when provided")
        if self.analysis_years is not None and self.analysis_years <= 0:
            raise ValueError("analysis_years must be positive when provided")


@dataclass(frozen=True)
class ExternalSupplyScenario:
    scenario_id: str
    project_mode: ProjectMode
    project_supply_mode: ProjectSupplyMode
    radionuclide: str
    patients_per_day: float
    prescribed_activity_mbq_per_patient: float
    source: ExternalSupplySource
    common_prefix_segments: tuple[ExternalSupplyTransportSegment, ...]
    conventional_last_mile_segment: ExternalSupplyTransportSegment
    mrt_last_mile_segment: ExternalSupplyTransportSegment
    receiving_workflow: ReceivingHospitalWorkflow
    explicit_upstream_release_capacity_mbq_per_day: float | None = None
    planned_upstream_release_activity_mbq_per_day: float | None = None
    fixed_upstream_release_activity_mbq_per_day: float | None = None
    max_decay_compensation_factor: float | None = None
    revenue_per_scan: float | None = None
    operating_days_per_year: int | None = None
    resource_existing_quantities: Mapping[str, float | None] = field(default_factory=dict)
    resource_existing_statuses: Mapping[str, DataStatus] = field(default_factory=dict)
    resource_final_required_quantities: Mapping[str, float | None] = field(default_factory=dict)
    economics: ExternalSupplyEconomicInputs = field(default_factory=ExternalSupplyEconomicInputs)
    assumptions: tuple[str, ...] = ()
    provenance_reference_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise ValueError("scenario_id must be non-empty")
        if not self.radionuclide.strip():
            raise ValueError("radionuclide must be non-empty")
        if self.patients_per_day <= 0.0:
            raise ValueError("patients_per_day must be positive")
        if self.prescribed_activity_mbq_per_patient <= 0.0:
            raise ValueError("prescribed_activity_mbq_per_patient must be positive")
        if self.explicit_upstream_release_capacity_mbq_per_day is not None and self.explicit_upstream_release_capacity_mbq_per_day <= 0.0:
            raise ValueError("explicit_upstream_release_capacity_mbq_per_day must be positive when provided")
        if self.planned_upstream_release_activity_mbq_per_day is not None and self.planned_upstream_release_activity_mbq_per_day <= 0.0:
            raise ValueError("planned_upstream_release_activity_mbq_per_day must be positive when provided")
        if self.fixed_upstream_release_activity_mbq_per_day is not None and self.fixed_upstream_release_activity_mbq_per_day <= 0.0:
            raise ValueError("fixed_upstream_release_activity_mbq_per_day must be positive when provided")
        if self.max_decay_compensation_factor is not None and self.max_decay_compensation_factor < 1.0:
            raise ValueError("max_decay_compensation_factor must be at least 1.0 when provided")
        if self.revenue_per_scan is not None and self.revenue_per_scan < 0.0:
            raise ValueError("revenue_per_scan must be non-negative when provided")
        if self.operating_days_per_year is not None and self.operating_days_per_year <= 0:
            raise ValueError("operating_days_per_year must be positive when provided")

        if self.project_mode not in {"GREENFIELD", "EXISTING_FACILITY_EXPANSION"}:
            raise ValueError("project_mode must be GREENFIELD or EXISTING_FACILITY_EXPANSION")

        if any(segment.designation != "COMMON_PREFIX" for segment in self.common_prefix_segments):
            raise ValueError("all common_prefix_segments must have designation COMMON_PREFIX")
        if self.conventional_last_mile_segment.designation != "CONVENTIONAL_LAST_MILE":
            raise ValueError("conventional_last_mile_segment designation must be CONVENTIONAL_LAST_MILE")
        if self.mrt_last_mile_segment.designation != "MRT_LAST_MILE":
            raise ValueError("mrt_last_mile_segment designation must be MRT_LAST_MILE")

        if self.project_mode == "GREENFIELD" and any(
            value is not None and value > 0.0 for value in self.resource_existing_quantities.values()
        ):
            raise ValueError("GREENFIELD project_mode requires zero existing resource quantities in this contract")


@dataclass(frozen=True)
class SegmentDecayRow:
    segment_id: str
    segment_type: TransportSegmentType
    designation: SegmentDesignation
    transport_mode: TransportMode
    origin_label: str
    destination_label: str
    distance_km: float | None
    duration_minutes: float | None
    handling_minutes: float
    elapsed_segment_minutes: float | None
    retained_fraction: float | None
    activity_entering_segment_mbq: float | None
    activity_leaving_segment_mbq: float | None
    physical_decay_loss_mbq: float | None
    active: bool
    assumption_label: str | None
    provenance_status: DataStatus


@dataclass(frozen=True)
class PathwayEconomicsResult:
    incremental_capex: float | None
    incremental_annual_opex: float | None
    annual_revenue: float | None
    annual_net_cash_flow: float | None
    npv: float | None
    payback_years: float | None
    not_calibrated_fields: tuple[str, ...]


@dataclass(frozen=True)
class ExternalSupplyPathwayResult:
    pathway: Literal["CONVENTIONAL", "MRT"]
    project_supply_mode: ProjectSupplyMode
    radionuclide: str
    patients_per_day: float
    prescribed_activity_mbq_per_patient: float
    total_prescribed_activity_mbq_per_day: float
    source: ExternalSupplySource
    external_supply_feasibility_status: ExternalSupplyFeasibilityStatus
    operational_state: PathwayOperationalState
    feasibility_reason: str
    transport_rows: tuple[SegmentDecayRow, ...]
    total_external_elapsed_minutes: float | None
    total_external_retained_fraction: float | None
    total_external_decay_loss_mbq: float | None
    activity_at_source_release_mbq_per_day: float | None
    activity_at_hospital_receipt_mbq_per_day: float | None
    activity_at_patient_administration_mbq_per_day: float | None
    required_activity_at_hospital_receipt_mbq_per_day: float | None
    required_upstream_activity_mbq_per_day: float | None
    confirmed_upstream_capacity_mbq_per_day: float | None
    upstream_capacity_status: Literal["CONFIRMED", "NOT_CALIBRATED", "SHORTFALL", "NOT_APPLICABLE"]
    retained_fraction_internal_workflow: float | None
    internal_distribution_mode: Literal["CONVENTIONAL_MANUAL", "MRT_INTERNAL"]
    internal_distribution_minutes: float
    total_internal_workflow_minutes: float
    internal_decay_loss_mbq: float | None
    effective_patients_per_day: float | None
    unmet_patients_per_day: float | None
    required_upstream_mbq_per_effective_patient: float | None
    economics: PathwayEconomicsResult
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    trace_id: str


@dataclass(frozen=True)
class ExternalSupplyComparisonReport:
    scenario_id: str
    project_mode: ProjectMode
    project_supply_mode: ProjectSupplyMode
    radionuclide: str
    patients_per_day: float
    prescribed_activity_mbq_per_patient: float
    total_prescribed_activity_mbq_per_day: float
    source: ExternalSupplySource
    receiving_workflow: ReceivingHospitalWorkflow
    resource_delta_rows: tuple[ResourceDeltaRow, ...]
    revenue_per_scan_provenance: EconomicValueProvenance
    common_prefix_segment_ids: tuple[str, ...]
    conventional: ExternalSupplyPathwayResult
    mrt: ExternalSupplyPathwayResult
    difference_minutes_saved_mrt_vs_conventional: float | None
    difference_mbq_preserved_at_hospital_receipt_mrt_vs_conventional: float | None
    difference_required_upstream_mbq_avoided_mrt_vs_conventional: float | None
    percentage_activity_improvement_at_hospital_receipt_mrt_vs_conventional: float | None
    fixed_source_upstream_release_mbq_per_day: float | None
    fixed_source_receipt_mbq_conventional: float | None
    fixed_source_receipt_mbq_mrt: float | None
    fixed_source_administration_mbq_conventional: float | None
    fixed_source_administration_mbq_mrt: float | None
    fixed_source_supported_patient_capacity_conventional: float | None
    fixed_source_supported_patient_capacity_mrt: float | None
    fixed_source_actual_effective_patients_served_conventional: float | None
    fixed_source_actual_effective_patients_served_mrt: float | None
    fixed_source_effective_patients_conventional: float | None
    fixed_source_effective_patients_mrt: float | None
    fixed_source_unused_mbq_conventional: float | None
    fixed_source_unused_mbq_mrt: float | None
    fixed_source_external_decay_loss_conventional: float | None
    fixed_source_external_decay_loss_mrt: float | None
    fixed_source_mbq_preserved_at_hospital_receipt_mrt_vs_conventional: float | None
    limitations: tuple[str, ...]
    assumptions: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    trace_id: str


def _trace_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _normalize_near_zero(value: float | None, *, tolerance: float = 1e-9) -> float | None:
    if value is None:
        return None
    if abs(value) <= tolerance:
        return 0.0
    return float(value)


def _resolve_revenue_per_scan(scenario: ExternalSupplyScenario) -> EconomicValueProvenance:
    default_value = 2000.0
    if scenario.revenue_per_scan is None:
        return EconomicValueProvenance(
            parameter_name="revenue_per_scan",
            value=default_value,
            value_status="DEFAULT_MODEL_VALUE",
            default_reference_value=default_value,
        )
    return EconomicValueProvenance(
        parameter_name="revenue_per_scan",
        value=float(scenario.revenue_per_scan),
        value_status="USER_OVERRIDE",
        default_reference_value=default_value,
    )


def _build_resource_delta_rows(scenario: ExternalSupplyScenario) -> tuple[ResourceDeltaRow, ...]:
    names = sorted(
        set(scenario.resource_existing_quantities)
        | set(scenario.resource_existing_statuses)
        | set(scenario.resource_final_required_quantities)
    )
    rows: list[ResourceDeltaRow] = []
    for resource in names:
        existing = scenario.resource_existing_quantities.get(resource)
        status = scenario.resource_existing_statuses.get(resource, "UNKNOWN")
        final_required = scenario.resource_final_required_quantities.get(resource)

        retained_usable: float | None
        if status in {"UNKNOWN", "NOT_CALIBRATED"}:
            retained_usable = None
        else:
            retained_usable = 0.0 if existing is None else float(existing)

        additional: float | None = None
        if final_required is not None and retained_usable is not None:
            additional = max(0.0, float(final_required) - retained_usable)

        rows.append(
            ResourceDeltaRow(
                resource=resource,
                existing_quantity=None if existing is None else float(existing),
                existing_quantity_status=status,
                retained_usable_existing_quantity=retained_usable,
                final_required_quantity=None if final_required is None else float(final_required),
                additional_required_quantity=additional,
            )
        )
    return tuple(rows)


def _segment_elapsed_minutes(segment: ExternalSupplyTransportSegment) -> float | None:
    if not segment.active:
        return 0.0
    if segment.duration_minutes is None:
        return None
    return float(segment.duration_minutes) + float(segment.handling_minutes)


def _validate_common_structure(segments: Sequence[ExternalSupplyTransportSegment]) -> None:
    if not segments:
        raise ValueError("common_prefix_segments must not be empty")
    expected = "ORIGIN_HANDLING"
    if segments[0].segment_type != expected:
        raise ValueError("first common segment must be ORIGIN_HANDLING")
    if len({segment.segment_id for segment in segments}) != len(segments):
        raise ValueError("segment_id values must be unique")


def _build_segment_rows(
    *,
    segments: Sequence[ExternalSupplyTransportSegment],
    initial_activity_mbq: float,
    half_life_minutes: float,
) -> tuple[tuple[SegmentDecayRow, ...], float | None, float | None, float | None, float | None]:
    rows: list[SegmentDecayRow] = []
    running_activity: float | None = float(initial_activity_mbq)
    total_elapsed = 0.0
    total_retained = 1.0
    transport_not_calibrated = False

    for segment in segments:
        elapsed = _segment_elapsed_minutes(segment)
        retained: float | None = None
        entering = running_activity
        leaving: float | None = None
        loss: float | None = None

        if elapsed is None:
            transport_not_calibrated = True
        elif running_activity is not None:
            retained = retained_fraction(elapsed, half_life_minutes)
            leaving = running_activity * retained
            loss = running_activity - leaving
            running_activity = leaving
            total_elapsed += elapsed
            total_retained *= retained
        else:
            transport_not_calibrated = True

        if elapsed is None:
            running_activity = None

        rows.append(
            SegmentDecayRow(
                segment_id=segment.segment_id,
                segment_type=segment.segment_type,
                designation=segment.designation,
                transport_mode=segment.transport_mode,
                origin_label=segment.origin_label,
                destination_label=segment.destination_label,
                distance_km=segment.distance_km,
                duration_minutes=segment.duration_minutes,
                handling_minutes=segment.handling_minutes,
                elapsed_segment_minutes=elapsed,
                retained_fraction=retained,
                activity_entering_segment_mbq=entering,
                activity_leaving_segment_mbq=leaving,
                physical_decay_loss_mbq=loss,
                active=segment.active,
                assumption_label=segment.assumption_label,
                provenance_status=segment.provenance_status,
            )
        )

    if transport_not_calibrated:
        return tuple(rows), None, None, None, None

    return tuple(rows), total_elapsed, total_retained, initial_activity_mbq - (running_activity or 0.0), running_activity


def _internal_retained_fraction(
    workflow: ReceivingHospitalWorkflow,
    half_life_minutes: float,
    *,
    pathway: Literal["CONVENTIONAL", "MRT"],
) -> float:
    internal_distribution = (
        workflow.conventional_internal_distribution_minutes
        if pathway == "CONVENTIONAL"
        else workflow.mrt_internal_distribution_minutes
    )
    elapsed = internal_distribution + workflow.administration_minutes
    return retained_fraction(elapsed, half_life_minutes)


def _classify_operational_state(status: ExternalSupplyFeasibilityStatus) -> PathwayOperationalState:
    if status == "FEASIBLE":
        return "PHYSICALLY_FEASIBLE"
    if status == "SUPPLY_CAPACITY_NOT_CALIBRATED":
        return "CAPACITY_NOT_CALIBRATED"
    if status == "INSUFFICIENT_UPSTREAM_ACTIVITY":
        return "CAPACITY_SHORTFALL"
    if status == "TRANSPORT_TIME_NOT_CALIBRATED":
        return "TRANSPORT_NOT_CALIBRATED"
    if status == "UNSUPPORTED_RADIONUCLIDE":
        return "UNSUPPORTED_RADIONUCLIDE"
    return "INFEASIBLE_DECAY_COMPENSATION"


def _evaluate_economics(
    *,
    scenario: ExternalSupplyScenario,
    pathway: Literal["CONVENTIONAL", "MRT"],
    effective_patients_per_day: float | None,
) -> PathwayEconomicsResult:
    economics = scenario.economics
    not_calibrated: list[str] = []
    revenue_assumption = _resolve_revenue_per_scan(scenario)

    shared_opex_parts = {
        "external_product_supply_cost_per_year": economics.external_product_supply_cost_per_year,
        "air_transport_cost_per_year": economics.air_transport_cost_per_year,
        "airport_handling_cost_per_year": economics.airport_handling_cost_per_year,
    }

    pathway_opex_parts: dict[str, float | None]
    if pathway == "CONVENTIONAL":
        pathway_opex_parts = {
            "conventional_last_mile_cost_per_year": economics.conventional_last_mile_cost_per_year,
        }
        pathway_capex_parts = {
            "receiving_infrastructure_incremental_capex": economics.receiving_infrastructure_incremental_capex,
        }
    else:
        pathway_opex_parts = {
            "mrt_last_mile_opex_per_year": economics.mrt_last_mile_opex_per_year,
        }
        pathway_capex_parts = {
            "mrt_last_mile_incremental_capex": economics.mrt_last_mile_incremental_capex,
            "receiving_infrastructure_incremental_capex": economics.receiving_infrastructure_incremental_capex,
        }

    capex_values = list(pathway_capex_parts.values())
    opex_values = list(shared_opex_parts.values()) + list(pathway_opex_parts.values())

    incremental_capex = None if any(value is None for value in capex_values) else float(sum(value for value in capex_values if value is not None))
    incremental_annual_opex = None if any(value is None for value in opex_values) else float(sum(value for value in opex_values if value is not None))

    for name, value in {**pathway_capex_parts, **shared_opex_parts, **pathway_opex_parts}.items():
        if value is None:
            not_calibrated.append(name)

    annual_revenue: float | None = None
    if effective_patients_per_day is not None and revenue_assumption.value is not None and scenario.operating_days_per_year is not None:
        annual_revenue = (
            float(effective_patients_per_day)
            * float(revenue_assumption.value)
            * float(scenario.operating_days_per_year)
        )
    else:
        not_calibrated.extend(
            name
            for name, value in {
                "revenue_per_scan": revenue_assumption.value,
                "operating_days_per_year": scenario.operating_days_per_year,
            }.items()
            if value is None
        )

    annual_net_cash_flow: float | None = None
    if annual_revenue is not None and incremental_annual_opex is not None:
        annual_net_cash_flow = annual_revenue - incremental_annual_opex

    npv: float | None = None
    payback_years: float | None = None
    if (
        annual_net_cash_flow is not None
        and incremental_capex is not None
        and economics.discount_rate_pct is not None
        and economics.analysis_years is not None
    ):
        rate = float(economics.discount_rate_pct) / 100.0
        years = int(economics.analysis_years)
        cumulative = -incremental_capex
        npv_value = -incremental_capex
        for year in range(1, years + 1):
            discounted = annual_net_cash_flow / ((1.0 + rate) ** year)
            npv_value += discounted
            cumulative += discounted
            if payback_years is None and cumulative >= 0.0 and annual_net_cash_flow > 0.0:
                payback_years = float(year)
        npv = npv_value
    else:
        for name, value in {
            "discount_rate_pct": economics.discount_rate_pct,
            "analysis_years": economics.analysis_years,
            "annual_net_cash_flow": annual_net_cash_flow,
            "incremental_capex": incremental_capex,
        }.items():
            if value is None:
                not_calibrated.append(name)

    return PathwayEconomicsResult(
        incremental_capex=incremental_capex,
        incremental_annual_opex=incremental_annual_opex,
        annual_revenue=annual_revenue,
        annual_net_cash_flow=annual_net_cash_flow,
        npv=npv,
        payback_years=payback_years,
        not_calibrated_fields=tuple(sorted(set(not_calibrated))),
    )


def _evaluate_pathway(
    *,
    scenario: ExternalSupplyScenario,
    pathway: Literal["CONVENTIONAL", "MRT"],
    half_life_minutes: float | None,
    last_mile_segment: ExternalSupplyTransportSegment,
) -> ExternalSupplyPathwayResult:
    total_prescribed = float(scenario.patients_per_day) * float(scenario.prescribed_activity_mbq_per_patient)
    internal_distribution_minutes = (
        scenario.receiving_workflow.conventional_internal_distribution_minutes
        if pathway == "CONVENTIONAL"
        else scenario.receiving_workflow.mrt_internal_distribution_minutes
    )
    if half_life_minutes is None:
        status: ExternalSupplyFeasibilityStatus = "UNSUPPORTED_RADIONUCLIDE"
        reason = f"No authoritative half-life physics is configured for radionuclide {scenario.radionuclide}."
        economics = _evaluate_economics(scenario=scenario, pathway=pathway, effective_patients_per_day=0.0)
        return ExternalSupplyPathwayResult(
            pathway=pathway,
            project_supply_mode=scenario.project_supply_mode,
            radionuclide=scenario.radionuclide,
            patients_per_day=float(scenario.patients_per_day),
            prescribed_activity_mbq_per_patient=float(scenario.prescribed_activity_mbq_per_patient),
            total_prescribed_activity_mbq_per_day=total_prescribed,
            source=scenario.source,
            external_supply_feasibility_status=status,
            operational_state=_classify_operational_state(status),
            feasibility_reason=reason,
            transport_rows=tuple(),
            total_external_elapsed_minutes=None,
            total_external_retained_fraction=None,
            total_external_decay_loss_mbq=None,
            activity_at_source_release_mbq_per_day=None,
            activity_at_hospital_receipt_mbq_per_day=None,
            activity_at_patient_administration_mbq_per_day=None,
            required_activity_at_hospital_receipt_mbq_per_day=None,
            required_upstream_activity_mbq_per_day=None,
            confirmed_upstream_capacity_mbq_per_day=scenario.explicit_upstream_release_capacity_mbq_per_day,
            upstream_capacity_status="NOT_APPLICABLE",
            retained_fraction_internal_workflow=None,
            internal_distribution_mode=internal_mode,
            internal_distribution_minutes=internal_distribution_minutes,
            total_internal_workflow_minutes=internal_distribution_minutes + scenario.receiving_workflow.administration_minutes,
            internal_decay_loss_mbq=None,
            effective_patients_per_day=0.0,
            unmet_patients_per_day=float(scenario.patients_per_day),
            required_upstream_mbq_per_effective_patient=None,
            economics=economics,
            assumptions=scenario.assumptions,
            limitations=("Radionuclide physics must be loaded from authoritative repository half-life data.",),
            provenance_reference_ids=scenario.provenance_reference_ids,
            trace_id=_trace_id({"pathway": pathway, "status": status, "scenario": scenario.scenario_id}),
        )
    internal_mode: Literal["CONVENTIONAL_MANUAL", "MRT_INTERNAL"] = (
        "CONVENTIONAL_MANUAL" if pathway == "CONVENTIONAL" else "MRT_INTERNAL"
    )
    supported = set(scenario.source.supported_radionuclides)
    if scenario.radionuclide not in supported:
        status: ExternalSupplyFeasibilityStatus = "UNSUPPORTED_RADIONUCLIDE"
        reason = f"Source {scenario.source.source_id} does not support radionuclide {scenario.radionuclide}."
        economics = _evaluate_economics(scenario=scenario, pathway=pathway, effective_patients_per_day=0.0)
        return ExternalSupplyPathwayResult(
            pathway=pathway,
            project_supply_mode=scenario.project_supply_mode,
            radionuclide=scenario.radionuclide,
            patients_per_day=float(scenario.patients_per_day),
            prescribed_activity_mbq_per_patient=float(scenario.prescribed_activity_mbq_per_patient),
            total_prescribed_activity_mbq_per_day=total_prescribed,
            source=scenario.source,
            external_supply_feasibility_status=status,
            operational_state=_classify_operational_state(status),
            feasibility_reason=reason,
            transport_rows=tuple(),
            total_external_elapsed_minutes=None,
            total_external_retained_fraction=None,
            total_external_decay_loss_mbq=None,
            activity_at_source_release_mbq_per_day=None,
            activity_at_hospital_receipt_mbq_per_day=None,
            activity_at_patient_administration_mbq_per_day=None,
            required_activity_at_hospital_receipt_mbq_per_day=None,
            required_upstream_activity_mbq_per_day=None,
            confirmed_upstream_capacity_mbq_per_day=scenario.explicit_upstream_release_capacity_mbq_per_day,
            upstream_capacity_status="NOT_APPLICABLE",
            retained_fraction_internal_workflow=None,
            internal_distribution_mode=internal_mode,
            internal_distribution_minutes=internal_distribution_minutes,
            total_internal_workflow_minutes=internal_distribution_minutes + scenario.receiving_workflow.administration_minutes,
            internal_decay_loss_mbq=None,
            effective_patients_per_day=0.0,
            unmet_patients_per_day=float(scenario.patients_per_day),
            required_upstream_mbq_per_effective_patient=None,
            economics=economics,
            assumptions=scenario.assumptions,
            limitations=("Radionuclide support must be explicitly provided by supply source.",),
            provenance_reference_ids=scenario.provenance_reference_ids,
            trace_id=_trace_id({"pathway": pathway, "status": status, "scenario": scenario.scenario_id}),
        )

    internal_retained = _internal_retained_fraction(
        scenario.receiving_workflow,
        half_life_minutes,
        pathway=pathway,
    )
    if internal_retained <= 0.0:
        status = "INFEASIBLE_DECAY_COMPENSATION"
        reason = "Internal workflow retention is non-positive; cannot compensate decay."
        economics = _evaluate_economics(scenario=scenario, pathway=pathway, effective_patients_per_day=0.0)
        return ExternalSupplyPathwayResult(
            pathway=pathway,
            project_supply_mode=scenario.project_supply_mode,
            radionuclide=scenario.radionuclide,
            patients_per_day=float(scenario.patients_per_day),
            prescribed_activity_mbq_per_patient=float(scenario.prescribed_activity_mbq_per_patient),
            total_prescribed_activity_mbq_per_day=total_prescribed,
            source=scenario.source,
            external_supply_feasibility_status=status,
            operational_state=_classify_operational_state(status),
            feasibility_reason=reason,
            transport_rows=tuple(),
            total_external_elapsed_minutes=None,
            total_external_retained_fraction=None,
            total_external_decay_loss_mbq=None,
            activity_at_source_release_mbq_per_day=None,
            activity_at_hospital_receipt_mbq_per_day=None,
            activity_at_patient_administration_mbq_per_day=None,
            required_activity_at_hospital_receipt_mbq_per_day=None,
            required_upstream_activity_mbq_per_day=None,
            confirmed_upstream_capacity_mbq_per_day=scenario.explicit_upstream_release_capacity_mbq_per_day,
            upstream_capacity_status="NOT_APPLICABLE",
            retained_fraction_internal_workflow=internal_retained,
            internal_distribution_mode=internal_mode,
            internal_distribution_minutes=internal_distribution_minutes,
            total_internal_workflow_minutes=internal_distribution_minutes + scenario.receiving_workflow.administration_minutes,
            internal_decay_loss_mbq=None,
            effective_patients_per_day=0.0,
            unmet_patients_per_day=float(scenario.patients_per_day),
            required_upstream_mbq_per_effective_patient=None,
            economics=economics,
            assumptions=scenario.assumptions,
            limitations=("Internal workflow timing must retain positive activity.",),
            provenance_reference_ids=scenario.provenance_reference_ids,
            trace_id=_trace_id({"pathway": pathway, "status": status, "scenario": scenario.scenario_id}),
        )

    required_hospital_receipt = total_prescribed / internal_retained
    segments = tuple(scenario.common_prefix_segments) + (last_mile_segment,)
    rows_required, elapsed_required, retained_required, _, _ = _build_segment_rows(
        segments=segments,
        initial_activity_mbq=required_hospital_receipt,
        half_life_minutes=half_life_minutes,
    )
    if retained_required is None or elapsed_required is None or retained_required <= 0.0:
        status = "TRANSPORT_TIME_NOT_CALIBRATED"
        reason = "At least one active transport segment is missing explicit duration_minutes."
        economics = _evaluate_economics(scenario=scenario, pathway=pathway, effective_patients_per_day=None)
        return ExternalSupplyPathwayResult(
            pathway=pathway,
            project_supply_mode=scenario.project_supply_mode,
            radionuclide=scenario.radionuclide,
            patients_per_day=float(scenario.patients_per_day),
            prescribed_activity_mbq_per_patient=float(scenario.prescribed_activity_mbq_per_patient),
            total_prescribed_activity_mbq_per_day=total_prescribed,
            source=scenario.source,
            external_supply_feasibility_status=status,
            operational_state=_classify_operational_state(status),
            feasibility_reason=reason,
            transport_rows=rows_required,
            total_external_elapsed_minutes=None,
            total_external_retained_fraction=None,
            total_external_decay_loss_mbq=None,
            activity_at_source_release_mbq_per_day=None,
            activity_at_hospital_receipt_mbq_per_day=None,
            activity_at_patient_administration_mbq_per_day=None,
            required_activity_at_hospital_receipt_mbq_per_day=required_hospital_receipt,
            required_upstream_activity_mbq_per_day=None,
            confirmed_upstream_capacity_mbq_per_day=scenario.explicit_upstream_release_capacity_mbq_per_day,
            upstream_capacity_status="NOT_CALIBRATED",
            retained_fraction_internal_workflow=internal_retained,
            internal_distribution_mode=internal_mode,
            internal_distribution_minutes=internal_distribution_minutes,
            total_internal_workflow_minutes=internal_distribution_minutes + scenario.receiving_workflow.administration_minutes,
            internal_decay_loss_mbq=None,
            effective_patients_per_day=None,
            unmet_patients_per_day=None,
            required_upstream_mbq_per_effective_patient=None,
            economics=economics,
            assumptions=scenario.assumptions,
            limitations=("Unknown transport duration remains uncalibrated in this deterministic foundation.",),
            provenance_reference_ids=scenario.provenance_reference_ids,
            trace_id=_trace_id({"pathway": pathway, "status": status, "scenario": scenario.scenario_id}),
        )

    required_upstream = required_hospital_receipt / retained_required
    if scenario.max_decay_compensation_factor is not None and required_upstream / total_prescribed > scenario.max_decay_compensation_factor:
        status = "INFEASIBLE_DECAY_COMPENSATION"
        reason = (
            f"Required upstream compensation factor {required_upstream / total_prescribed:.4f} exceeds configured "
            f"max_decay_compensation_factor {scenario.max_decay_compensation_factor:.4f}."
        )
        economics = _evaluate_economics(scenario=scenario, pathway=pathway, effective_patients_per_day=0.0)
        return ExternalSupplyPathwayResult(
            pathway=pathway,
            project_supply_mode=scenario.project_supply_mode,
            radionuclide=scenario.radionuclide,
            patients_per_day=float(scenario.patients_per_day),
            prescribed_activity_mbq_per_patient=float(scenario.prescribed_activity_mbq_per_patient),
            total_prescribed_activity_mbq_per_day=total_prescribed,
            source=scenario.source,
            external_supply_feasibility_status=status,
            operational_state=_classify_operational_state(status),
            feasibility_reason=reason,
            transport_rows=rows_required,
            total_external_elapsed_minutes=elapsed_required,
            total_external_retained_fraction=retained_required,
            total_external_decay_loss_mbq=required_upstream - required_hospital_receipt,
            activity_at_source_release_mbq_per_day=None,
            activity_at_hospital_receipt_mbq_per_day=None,
            activity_at_patient_administration_mbq_per_day=None,
            required_activity_at_hospital_receipt_mbq_per_day=required_hospital_receipt,
            required_upstream_activity_mbq_per_day=required_upstream,
            confirmed_upstream_capacity_mbq_per_day=scenario.explicit_upstream_release_capacity_mbq_per_day,
            upstream_capacity_status="NOT_APPLICABLE",
            retained_fraction_internal_workflow=internal_retained,
            internal_distribution_mode=internal_mode,
            internal_distribution_minutes=internal_distribution_minutes,
            total_internal_workflow_minutes=internal_distribution_minutes + scenario.receiving_workflow.administration_minutes,
            internal_decay_loss_mbq=None,
            effective_patients_per_day=0.0,
            unmet_patients_per_day=float(scenario.patients_per_day),
            required_upstream_mbq_per_effective_patient=None,
            economics=economics,
            assumptions=scenario.assumptions,
            limitations=("Configured decay compensation guard rejected pathway.",),
            provenance_reference_ids=scenario.provenance_reference_ids,
            trace_id=_trace_id({"pathway": pathway, "status": status, "scenario": scenario.scenario_id}),
        )

    target_upstream_release = required_upstream
    if scenario.planned_upstream_release_activity_mbq_per_day is not None:
        target_upstream_release = scenario.planned_upstream_release_activity_mbq_per_day

    capacity_status: Literal["CONFIRMED", "NOT_CALIBRATED", "SHORTFALL", "NOT_APPLICABLE"]
    if scenario.explicit_upstream_release_capacity_mbq_per_day is None:
        capacity_status = "NOT_CALIBRATED"
        actual_upstream_release = target_upstream_release
        status = "SUPPLY_CAPACITY_NOT_CALIBRATED"
        reason = "Required upstream activity is computed, but upstream release capacity is not calibrated."
    else:
        capacity = float(scenario.explicit_upstream_release_capacity_mbq_per_day)
        actual_upstream_release = min(target_upstream_release, capacity)
        if required_upstream <= capacity + 1e-9:
            status = "FEASIBLE"
            reason = "External chain is physically feasible and required upstream activity is within explicit capacity."
            capacity_status = "CONFIRMED"
        else:
            status = "INSUFFICIENT_UPSTREAM_ACTIVITY"
            reason = (
                f"Required upstream activity {required_upstream:.3f} MBq/day exceeds explicit upstream capacity "
                f"{capacity:.3f} MBq/day."
            )
            capacity_status = "SHORTFALL"

    rows_actual, elapsed_actual, retained_actual, decay_loss_actual, activity_receipt_actual = _build_segment_rows(
        segments=segments,
        initial_activity_mbq=actual_upstream_release,
        half_life_minutes=half_life_minutes,
    )
    if retained_actual is None or elapsed_actual is None or activity_receipt_actual is None:
        status = "TRANSPORT_TIME_NOT_CALIBRATED"
        reason = "At least one active transport segment is missing explicit duration_minutes."

    activity_administration_actual = None if activity_receipt_actual is None else activity_receipt_actual * internal_retained
    internal_decay_loss = None
    if activity_receipt_actual is not None and activity_administration_actual is not None:
        internal_decay_loss = activity_receipt_actual - activity_administration_actual
    effective_patients = None
    unmet_patients = None
    if activity_administration_actual is not None:
        effective_patients = min(float(scenario.patients_per_day), activity_administration_actual / float(scenario.prescribed_activity_mbq_per_patient))
        unmet_patients = max(0.0, float(scenario.patients_per_day) - effective_patients)

    required_upstream_per_effective_patient = None
    if effective_patients is not None and effective_patients > 0.0:
        required_upstream_per_effective_patient = required_upstream / effective_patients

    economics = _evaluate_economics(scenario=scenario, pathway=pathway, effective_patients_per_day=effective_patients)

    trace_id = _trace_id(
        {
            "scenario_id": scenario.scenario_id,
            "pathway": pathway,
            "status": status,
            "required_upstream": required_upstream,
            "actual_upstream": actual_upstream_release,
            "activity_receipt": activity_receipt_actual,
            "activity_administration": activity_administration_actual,
        }
    )

    return ExternalSupplyPathwayResult(
        pathway=pathway,
        project_supply_mode=scenario.project_supply_mode,
        radionuclide=scenario.radionuclide,
        patients_per_day=float(scenario.patients_per_day),
        prescribed_activity_mbq_per_patient=float(scenario.prescribed_activity_mbq_per_patient),
        total_prescribed_activity_mbq_per_day=total_prescribed,
        source=scenario.source,
        external_supply_feasibility_status=status,
        operational_state=_classify_operational_state(status),
        feasibility_reason=reason,
        transport_rows=rows_actual,
        total_external_elapsed_minutes=elapsed_actual,
        total_external_retained_fraction=retained_actual,
        total_external_decay_loss_mbq=decay_loss_actual,
        activity_at_source_release_mbq_per_day=actual_upstream_release,
        activity_at_hospital_receipt_mbq_per_day=activity_receipt_actual,
        activity_at_patient_administration_mbq_per_day=activity_administration_actual,
        required_activity_at_hospital_receipt_mbq_per_day=required_hospital_receipt,
        required_upstream_activity_mbq_per_day=required_upstream,
        confirmed_upstream_capacity_mbq_per_day=scenario.explicit_upstream_release_capacity_mbq_per_day,
        upstream_capacity_status=capacity_status,
        retained_fraction_internal_workflow=internal_retained,
        internal_distribution_mode=internal_mode,
        internal_distribution_minutes=internal_distribution_minutes,
        total_internal_workflow_minutes=internal_distribution_minutes + scenario.receiving_workflow.administration_minutes,
        internal_decay_loss_mbq=internal_decay_loss,
        effective_patients_per_day=effective_patients,
        unmet_patients_per_day=unmet_patients,
        required_upstream_mbq_per_effective_patient=required_upstream_per_effective_patient,
        economics=economics,
        assumptions=scenario.assumptions,
        limitations=(
            "Deterministic single-hub/single-spoke foundation; no route optimization.",
            "Unknown durations remain not calibrated and are not fabricated from distance.",
        ),
        provenance_reference_ids=scenario.provenance_reference_ids,
        trace_id=trace_id,
    )


def run_external_supply_hub_spoke(scenario: ExternalSupplyScenario) -> ExternalSupplyComparisonReport:
    _validate_common_structure(scenario.common_prefix_segments)

    half_life_lookup = load_radionuclide_half_lives()
    half_life = None if scenario.radionuclide not in half_life_lookup else float(half_life_lookup[scenario.radionuclide])
    revenue_provenance = _resolve_revenue_per_scan(scenario)
    resource_delta_rows = _build_resource_delta_rows(scenario)
    conventional = _evaluate_pathway(
        scenario=scenario,
        pathway="CONVENTIONAL",
        half_life_minutes=half_life,
        last_mile_segment=scenario.conventional_last_mile_segment,
    )
    mrt = _evaluate_pathway(
        scenario=scenario,
        pathway="MRT",
        half_life_minutes=half_life,
        last_mile_segment=scenario.mrt_last_mile_segment,
    )

    minutes_saved = None
    if conventional.total_external_elapsed_minutes is not None and mrt.total_external_elapsed_minutes is not None:
        minutes_saved = _normalize_near_zero(conventional.total_external_elapsed_minutes - mrt.total_external_elapsed_minutes)

    mbq_preserved = None
    if conventional.activity_at_hospital_receipt_mbq_per_day is not None and mrt.activity_at_hospital_receipt_mbq_per_day is not None:
        mbq_preserved = _normalize_near_zero(mrt.activity_at_hospital_receipt_mbq_per_day - conventional.activity_at_hospital_receipt_mbq_per_day)

    upstream_avoided = None
    if conventional.required_upstream_activity_mbq_per_day is not None and mrt.required_upstream_activity_mbq_per_day is not None:
        upstream_avoided = _normalize_near_zero(conventional.required_upstream_activity_mbq_per_day - mrt.required_upstream_activity_mbq_per_day)

    pct_improvement = None
    if (
        conventional.activity_at_hospital_receipt_mbq_per_day is not None
        and mrt.activity_at_hospital_receipt_mbq_per_day is not None
        and conventional.activity_at_hospital_receipt_mbq_per_day > 0.0
    ):
        pct_improvement = _normalize_near_zero(
            100.0
            * (mrt.activity_at_hospital_receipt_mbq_per_day - conventional.activity_at_hospital_receipt_mbq_per_day)
            / conventional.activity_at_hospital_receipt_mbq_per_day
        )

    fixed_source_receipt_conventional = None
    fixed_source_receipt_mrt = None
    fixed_source_admin_conventional = None
    fixed_source_admin_mrt = None
    fixed_source_capacity_conventional = None
    fixed_source_capacity_mrt = None
    fixed_source_served_conventional = None
    fixed_source_served_mrt = None
    fixed_source_unused_conventional = None
    fixed_source_unused_mrt = None
    fixed_source_external_decay_conventional = None
    fixed_source_external_decay_mrt = None
    fixed_source_preserved_receipt = None
    if scenario.fixed_upstream_release_activity_mbq_per_day is not None and half_life is not None:
        segments_conventional = tuple(scenario.common_prefix_segments) + (scenario.conventional_last_mile_segment,)
        segments_mrt = tuple(scenario.common_prefix_segments) + (scenario.mrt_last_mile_segment,)
        _, _, _, fixed_source_external_decay_conventional, fixed_source_receipt_conventional = _build_segment_rows(
            segments=segments_conventional,
            initial_activity_mbq=scenario.fixed_upstream_release_activity_mbq_per_day,
            half_life_minutes=half_life,
        )
        _, _, _, fixed_source_external_decay_mrt, fixed_source_receipt_mrt = _build_segment_rows(
            segments=segments_mrt,
            initial_activity_mbq=scenario.fixed_upstream_release_activity_mbq_per_day,
            half_life_minutes=half_life,
        )
        if fixed_source_receipt_conventional is not None:
            retained_conv = _internal_retained_fraction(
                scenario.receiving_workflow,
                half_life,
                pathway="CONVENTIONAL",
            )
            fixed_source_admin_conventional = fixed_source_receipt_conventional * retained_conv
            fixed_source_capacity_conventional = fixed_source_admin_conventional / float(scenario.prescribed_activity_mbq_per_patient)
            clinical_capacity_conventional = (
                float(scenario.patients_per_day)
                if conventional.effective_patients_per_day is None
                else float(conventional.effective_patients_per_day)
            )
            fixed_source_served_conventional = min(
                float(scenario.patients_per_day),
                fixed_source_capacity_conventional,
                clinical_capacity_conventional,
            )
            fixed_source_unused_conventional = max(
                0.0,
                fixed_source_admin_conventional - (fixed_source_served_conventional * float(scenario.prescribed_activity_mbq_per_patient)),
            )
        if fixed_source_receipt_mrt is not None:
            retained_mrt = _internal_retained_fraction(
                scenario.receiving_workflow,
                half_life,
                pathway="MRT",
            )
            fixed_source_admin_mrt = fixed_source_receipt_mrt * retained_mrt
            fixed_source_capacity_mrt = fixed_source_admin_mrt / float(scenario.prescribed_activity_mbq_per_patient)
            clinical_capacity_mrt = (
                float(scenario.patients_per_day)
                if mrt.effective_patients_per_day is None
                else float(mrt.effective_patients_per_day)
            )
            fixed_source_served_mrt = min(
                float(scenario.patients_per_day),
                fixed_source_capacity_mrt,
                clinical_capacity_mrt,
            )
            fixed_source_unused_mrt = max(
                0.0,
                fixed_source_admin_mrt - (fixed_source_served_mrt * float(scenario.prescribed_activity_mbq_per_patient)),
            )
        if fixed_source_receipt_conventional is not None and fixed_source_receipt_mrt is not None:
            fixed_source_preserved_receipt = _normalize_near_zero(
                fixed_source_receipt_mrt - fixed_source_receipt_conventional
            )

    trace_id = _trace_id(
        {
            "scenario_id": scenario.scenario_id,
            "conventional_trace_id": conventional.trace_id,
            "mrt_trace_id": mrt.trace_id,
            "minutes_saved": minutes_saved,
            "mbq_preserved": mbq_preserved,
            "upstream_avoided": upstream_avoided,
        }
    )

    return ExternalSupplyComparisonReport(
        scenario_id=scenario.scenario_id,
        project_mode=scenario.project_mode,
        project_supply_mode=scenario.project_supply_mode,
        radionuclide=scenario.radionuclide,
        patients_per_day=float(scenario.patients_per_day),
        prescribed_activity_mbq_per_patient=float(scenario.prescribed_activity_mbq_per_patient),
        total_prescribed_activity_mbq_per_day=float(scenario.patients_per_day) * float(scenario.prescribed_activity_mbq_per_patient),
        source=scenario.source,
        receiving_workflow=scenario.receiving_workflow,
        resource_delta_rows=resource_delta_rows,
        revenue_per_scan_provenance=revenue_provenance,
        common_prefix_segment_ids=tuple(segment.segment_id for segment in scenario.common_prefix_segments),
        conventional=conventional,
        mrt=mrt,
        difference_minutes_saved_mrt_vs_conventional=minutes_saved,
        difference_mbq_preserved_at_hospital_receipt_mrt_vs_conventional=None,
        difference_required_upstream_mbq_avoided_mrt_vs_conventional=upstream_avoided,
        percentage_activity_improvement_at_hospital_receipt_mrt_vs_conventional=pct_improvement,
        fixed_source_upstream_release_mbq_per_day=scenario.fixed_upstream_release_activity_mbq_per_day,
        fixed_source_receipt_mbq_conventional=fixed_source_receipt_conventional,
        fixed_source_receipt_mbq_mrt=fixed_source_receipt_mrt,
        fixed_source_administration_mbq_conventional=fixed_source_admin_conventional,
        fixed_source_administration_mbq_mrt=fixed_source_admin_mrt,
        fixed_source_supported_patient_capacity_conventional=fixed_source_capacity_conventional,
        fixed_source_supported_patient_capacity_mrt=fixed_source_capacity_mrt,
        fixed_source_actual_effective_patients_served_conventional=fixed_source_served_conventional,
        fixed_source_actual_effective_patients_served_mrt=fixed_source_served_mrt,
        fixed_source_effective_patients_conventional=fixed_source_capacity_conventional,
        fixed_source_effective_patients_mrt=fixed_source_capacity_mrt,
        fixed_source_unused_mbq_conventional=fixed_source_unused_conventional,
        fixed_source_unused_mbq_mrt=fixed_source_unused_mrt,
        fixed_source_external_decay_loss_conventional=fixed_source_external_decay_conventional,
        fixed_source_external_decay_loss_mrt=fixed_source_external_decay_mrt,
        fixed_source_mbq_preserved_at_hospital_receipt_mrt_vs_conventional=fixed_source_preserved_receipt,
        limitations=(
            "Single-hub/single-spoke deterministic foundation.",
            "No schedule, routing, or inventory optimization is modeled in this build.",
        ),
        assumptions=scenario.assumptions,
        provenance_reference_ids=scenario.provenance_reference_ids,
        trace_id=trace_id,
    )


def build_receiving_workflow_from_retrofit_resource_facts(
    resource_facts: Mapping[str, Any],
    *,
    conventional_internal_distribution_minutes: float,
    mrt_internal_distribution_minutes: float,
    administration_minutes: float,
    provenance_status: DataStatus = "USER_ASSUMED",
    provenance_reference_ids: tuple[str, ...] = (),
) -> ReceivingHospitalWorkflow:
    def _as_quantity(resource_name: str) -> int:
        value = resource_facts.get(resource_name)
        if value is None:
            return 0

        operational = getattr(value, "operational_quantity", None)
        existing = getattr(value, "existing_quantity", None)

        if operational is not None:
            return int(round(float(operational)))
        if existing is not None:
            return int(round(float(existing)))
        if isinstance(value, (int, float)):
            return int(round(float(value)))
        return 0

    return ReceivingHospitalWorkflow(
        receiving_radiopharmacy_units=_as_quantity("radiopharmacy_units"),
        injection_resources=_as_quantity("injection_resources"),
        uptake_resources=_as_quantity("uptake_resources"),
        scanners=_as_quantity("scanners"),
        on_site_cyclotron_units=_as_quantity("cyclotron_units"),
        on_site_cyclotron_inventory_status=(
            "KNOWN"
            if resource_facts.get("cyclotron_units") is not None
            else "UNKNOWN"
        ),
        conventional_internal_distribution_minutes=float(conventional_internal_distribution_minutes),
        mrt_internal_distribution_minutes=float(mrt_internal_distribution_minutes),
        administration_minutes=float(administration_minutes),
        provenance_status=provenance_status,
        provenance_reference_ids=provenance_reference_ids,
    )

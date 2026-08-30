"""Hybrid Conventional+MRT zone-based transport-mode optimization.

FINAL HYBRID AUTHORITY CORRECTION (this build) fixes two gaps left open by the
Phase 15 foundation (preserved: floor/zone candidate representation, 0%/100%
MRT boundaries, shared CY-001 production basis, shared-trunk guideway
deduplication, patient-level traceability):

GAP 1 -- JOINT CLINICAL SCHEDULE (the central correction, spec sections 8-14):
Conventional- and MRT-delivered patients now enter ONE shared deterministic
injection->uptake->scanner schedule, competing for the SAME resource pools,
rather than being evaluated through two fully separate pipeline runs and
picked from whichever run matches their zone. Mechanism (reuses 100% existing
authoritative scheduling primitives from production_clinical_schedule.py,
adds no new physics):
  1. ONE production authority: the Conventional pathway's native pipeline run
     supplies the authoritative batch/cycle assignment, released dose
     inventory, and patient population (section 5/6). Conventional is used as
     the sizing/production reference because its slower transport time is the
     conservative basis for production/decay-feasibility sizing.
  2. Deterministic per-patient destination assignment is derived ONCE (via
     production_clinical_schedule._build_transport_payloads with the FULL
     shared destination set, matching existing BALANCED_ROUND_ROBIN
     semantics) so a patient's assigned room is identical regardless of which
     payload-capacity/transport-mode grouping is later applied to it.
  3. Payloads are split by the destination's assigned zone (Conventional vs
     MRT, per the HybridZoneCandidate's floor assignment) and scheduled
     through mode-specific, physically distinct transport resource pools
     (serialized human transporters vs MRT carriers) -- section 8.
  4. All resulting mode-specific delivery arrivals are merged into ONE
     deterministic batch-release stream and fed through ONE call of the
     existing operating_day_scheduler.schedule_operating_day with a SINGLE
     shared injection/uptake/scanner resource pool -- section 9/10/12/13.
  5. Retention is recalculated strictly AFTER the joint schedule using the
     authoritative decay engine (retained_fraction), from each patient's
     ACTUAL joint-schedule injection_start minus their production release
     time -- section 15. No patient reconstruction after the merge (14).

GAP 2 -- ADAPTIVE RESOURCE SIZING (spec sections 21-31, 42-44):
Conventional transporter and MRT carrier counts are no longer derived from a
floor-count heuristic (Phase 15's approximation, root cause of the 3-vs-4 /
6-vs-7 transporter/carrier discrepancies described in the audit below).
Instead a deterministic, bounded, workload-driven minimum-feasible search is
used: start at 1 unit, increase while additional units still measurably
reduce queueing, adaptively expand the search bound if the winner sits at the
current maximum with wait still improving, and stop only for a documented
reason (never bare SEARCH_BOUND_REACHED unless a hard computational safeguard
is hit).

AUDIT FINDING (sections 21-22): classification A. DIFFERENT_RESOURCE_SEARCH_STATE
for both the 3-vs-4 transporter and 6-vs-7 carrier discrepancies. The pure-
pathway reference's `distribution_concurrency` came from
spatial_benchmark.generate_candidate_layouts's profile sweep
(`min(8, len(floors) + concurrency_extra)`, concurrency_extra in {0, 1}
depending on the winning profile) -- a different resource-search mechanism
than Phase 15 Hybrid's naive `min(8, len(floors))` (always concurrency_extra=0).
This is NOT a boundary-reproduction defect in the scheduling/merge mechanism
itself; it is fixed here by replacing the floor-count heuristic with the
workload-driven adaptive search described above, evaluated against the SAME
joint schedule used everywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Literal, Mapping

from diagnostics import load_radionuclide_half_lives
from decision_pipeline import NativePathwayScenario
from equipment_energy_opex import PathwayEnergyLedgerInput, build_ledger_energy_component
from infrastructure_opex import (
    InfrastructureOpexInputs,
    InfrastructureOpexResult,
    OpexLedgerItem,
    calculate_infrastructure_opex,
    merge_shared_and_mode_specific_ledgers,
    recompute_ledger_totals,
    replace_ledger_component,
)
from lifecycle_economics import evaluate_lifecycle_economics
from models import PlannerAssumptions, SharedNetworkAssumptions
from multi_isotope_decay import retained_fraction
from operating_day_scheduler import BatchRelease, OperatingDayInputs, schedule_operating_day
from production_clinical_schedule import (
    ConventionalTransportScheduleResult,
    ProductionClinicalPatientTrace,
    _build_batch_releases_from_transport,
    _build_patient_traces,
    _build_transport_payloads,
    _destination_floor_lookup,
    _resolve_active_destinations,
    _resolve_mrt_route_profile,
    _schedule_conventional_transport_jobs,
    _schedule_mrt_carrier_transport_jobs,
)
from spatial_benchmark import (
    BenchmarkGeometry,
    ProductionBasis,
    _assign_rooms_for_candidate,
    _build_request,
    run_native_pathway_pipeline,
)
from clinical_resource_identity import resource_id_for_index
from mrt_canonical_configuration import (
    MrtRuntimeConfig,
    CONTROLLED_ELECTRICITY_TARIFF_USD_PER_KWH,
    compute_mrt_annual_electricity,
)
# NOTE: `mrt_transport_energy_maintenance_authority` is imported lazily inside
# `_build_hybrid_opex_result` (not at module top) to avoid a circular import:
# that module imports `shared_mrt_multistream_authority`, which in turn imports
# `HybridEvaluationResult`/`HybridPatientTrace` from THIS module.
from inbound_patient_program import compute_inbound_room_guideway_extension
from operating_day_scheduler import DEDICATED_ROOM_RESOURCE_INDEX
from radiopharm_workflow_staffing import RadiopharmWorkflowStaffingResult, compute_radiopharm_workflow_staffing

TransportMode = Literal["CONVENTIONAL", "MRT"]

# Hard computational safeguards (section 26): documented bounds beyond which
# adaptive resource-count expansion stops regardless of remaining improvement.
# Far above any candidate value ever found useful in this benchmark's demand
# range; exists only to guarantee termination.
TRANSPORT_RESOURCE_HARD_CAP = 32
TRANSPORT_RESOURCE_INITIAL_MAX = 8
TRANSPORT_RESOURCE_EXPANSION_STEP = 4
TRANSPORT_RESOURCE_WAIT_IMPROVEMENT_THRESHOLD_MINUTES = 1.0

# LEGACY_FIXED_PRODUCTION_STAFF_ASSUMPTION: reused verbatim from
# spatial_benchmark._build_pathway_scenarios (identical for both pure
# pathways). Hybrid uses ONE shared CY-001/production authority, so exactly
# ONE production-labor charge applies regardless of transport-mode split.
PRODUCTION_STAFF_FTE = 2.0
PRODUCTION_STAFF_LOADED_COST_PER_FTE = 110_000.0


@dataclass(frozen=True)
class HybridZoneCandidate:
    """Smallest coherent Hybrid representation (Phase 15, preserved unchanged)."""

    candidate_id: str
    mrt_floors: frozenset[int]
    conventional_floors: frozenset[int]
    scanners: int
    injection_resources: int
    uptake_resources: int


@dataclass(frozen=True)
class ResourceSearchDiagnostic:
    """Section 23 required reporting: selected value, maximum tested, stop reason."""

    dimension: str
    selected_value: int
    maximum_value_tested: int
    stop_reason: str


@dataclass(frozen=True)
class HybridPatientTrace:
    patient_id: str
    destination_room_id: str
    destination_floor: int
    transport_mode: TransportMode
    production_cycle_batch_id: int
    payload_id: str
    release_time_minutes: float
    injection_start_minutes: float
    clinically_completed: bool
    elapsed_release_to_administration_minutes: float
    retained_fraction: float
    retention_pass: bool
    retention_qualified_completion: bool
    # Live-State adapter fields (additive, default-safe): the SAME persistent
    # shared INJ-xxx/UP-xxx/SCN-xxx clinical-resource identity convention
    # `clinical_resource_identity.py` uses for Conventional/MRT (section 6 --
    # ONE shared resource system, never CONV-SCN-001/MRT-SCN-001 duplicates),
    # plus full timing windows/production traceability so an existing Hybrid
    # result can be represented as `PatientOperationalPlan` entries without a
    # second patient-plan type (see hybrid_live_state_adapter below).
    assigned_cyclotron_id: str = ""
    radiopharmacy_origin_id: str | None = None
    production_window_id: int = 0
    transport_arrival_time_minutes: float = 0.0
    clinical_resource_mode: str = "OUTPATIENT_SHARED"
    inbound_room_id: str | None = None
    injection_resource_id: str = ""
    uptake_resource_id: str = ""
    scanner_resource_id: str = ""
    injection_end_minutes: float = 0.0
    uptake_start_minutes: float = 0.0
    uptake_end_minutes: float = 0.0
    scan_start_minutes: float = 0.0
    scan_end_minutes: float = 0.0
    canonical_patient_id: str | None = None
    """Section 34 (whole-oncology patient identity unification): additive,
    None-safe bridge to a canonical `OncologyPatientRecord.patient_id` --
    populated by an external adapter (never by this module) via a
    deterministic, validated mapping. None means no canonical population was
    supplied (legacy/component-benchmark call, section 35/83) -- never
    fabricated."""


@dataclass(frozen=True)
class HybridEvaluationResult:
    candidate: HybridZoneCandidate
    mrt_penetration_pct: float  # % of injection rooms assigned to MRT.
    patient_traces: tuple[HybridPatientTrace, ...]
    retention_qualified_completed: int
    conventional_transporters: int
    mrt_carriers: int
    conventional_transporter_search: ResourceSearchDiagnostic
    mrt_carrier_search: ResourceSearchDiagnostic
    mrt_guideway_horizontal_m: float
    mrt_guideway_vertical_m: float
    mrt_transitions: int
    staffing: RadiopharmWorkflowStaffingResult
    production_labor_annual_opex: float
    total_capex: float
    total_annual_opex: float
    qualified_annual_revenue: float
    qualified_lifecycle_npv: float
    opex_result: InfrastructureOpexResult
    # Live-State adapter fields (additive): the joint schedule's physical
    # basis, needed to rerun the SAME shared schedule (never a second
    # scheduler) for an affected subset only.
    radionuclide: str = ""
    injection_service_minutes: float = 0.0
    uptake_minutes: float = 0.0
    scanner_service_minutes: float = 0.0
    clinical_day_start_minute: float = 0.0
    operating_day_minutes: float = 0.0
    half_life_minutes: float = 0.0
    retention_threshold_used: float = 0.0
    """Section 5/41: the ONE authoritative ledger (infrastructure_opex.py) --
    `total_annual_opex` above is always `opex_result.total_annual_opex`
    (section 35); the old bespoke formula is REMOVED_FROM_AUTHORITATIVE_PATH,
    never a second competing total (section 84-85)."""


def _room_floor(geometry: BenchmarkGeometry, room_id: str) -> int:
    return geometry.room_floor_by_id[room_id]


def _search_transport_resource_count(
    *,
    max_count: int,
    schedule_fn: Callable[[int], object],
    wait_extractor: Callable[[object], float],
) -> tuple[int, int, str]:
    """Deterministic bounded minimum-feasible-then-useful search (sections 25/43/44).

    Returns (selected_count, maximum_value_tested, stop_reason).
    """
    best_count = 1
    best_wait: float | None = None
    tested_max = 0
    stop_reason = "SEARCH_BOUND_REACHED"
    for count in range(1, max_count + 1):
        tested_max = count
        result = schedule_fn(count)
        wait = wait_extractor(result)
        if wait <= 1e-6:
            best_count = count
            stop_reason = "DEMAND_SATURATED"
            break
        if best_wait is not None and (best_wait - wait) < TRANSPORT_RESOURCE_WAIT_IMPROVEMENT_THRESHOLD_MINUTES:
            stop_reason = "NO_QUALIFIED_THROUGHPUT_GAIN"
            break
        best_count = count
        best_wait = wait
    return best_count, tested_max, stop_reason


def _adaptive_transport_resource_search(
    *,
    dimension: str,
    schedule_fn: Callable[[int], object],
    wait_extractor: Callable[[object], float],
) -> ResourceSearchDiagnostic:
    """Section 25/26: expand the search bound while the winner sits at the
    current maximum and queueing is still improving; stop only for a
    documented reason, with TRANSPORT_RESOURCE_HARD_CAP as the final
    documented computational safeguard (never a bare, unjustified stop)."""
    max_count = TRANSPORT_RESOURCE_INITIAL_MAX
    while True:
        selected, tested_max, stop_reason = _search_transport_resource_count(
            max_count=max_count, schedule_fn=schedule_fn, wait_extractor=wait_extractor,
        )
        at_bound = tested_max == max_count and stop_reason == "SEARCH_BOUND_REACHED"
        if not at_bound or max_count >= TRANSPORT_RESOURCE_HARD_CAP:
            final_reason = stop_reason
            if at_bound and max_count >= TRANSPORT_RESOURCE_HARD_CAP:
                final_reason = "PHYSICAL_LIMIT"  # documented computational safeguard, section 26
            return ResourceSearchDiagnostic(dimension, selected, max_count, final_reason)
        max_count = min(TRANSPORT_RESOURCE_HARD_CAP, max_count + TRANSPORT_RESOURCE_EXPANSION_STEP)


# ---------------------------------------------------------------------------
# Hybrid -> InfrastructureOpexInputs adapter (this build, sections 5-6/41):
# the ONE authoritative OPEX ledger semantic for Conventional/MRT/Hybrid.
# Never a second, competing "HybridOpexLedgerV2" authority -- this function
# only maps Hybrid's real physical/shared/mode-specific quantities onto TWO
# `calculate_infrastructure_opex` calls (Conventional-flavored carries shared
# + Conventional-specific quantities; MRT-flavored carries ONLY MRT-exclusive
# quantities, all shared quantities zeroed) and merges them via
# `merge_shared_and_mode_specific_ledgers` (which itself raises if any
# component would be double-counted, section 32).
# ---------------------------------------------------------------------------

MRT_SPECIFIC_LEDGER_COMPONENTS = frozenset({
    "MRT energy", "MRT base annual O&M", "MRT endpoint annual O&M",
    "Guideway annual maintenance", "Vertical transition annual maintenance",
    "Building connection annual maintenance", "MRT support labor",
    "MRT carrier allocated electricity", "MRT carrier maintenance",
})


def _build_hybrid_opex_result(
    *,
    candidate: HybridZoneCandidate,
    conv_config: NativePathwayScenario,
    mrt_config: NativePathwayScenario,
    conv_active: bool,
    mrt_active: bool,
    conv_transporters: int,
    mrt_carriers: int,
    mrt_endpoint_count: int,
    mrt_guideway_length_m: float,
    mrt_transitions: int,
    staffing: RadiopharmWorkflowStaffingResult,
    assumptions: PlannerAssumptions,
    mrt_runtime_config: "MrtRuntimeConfig | None" = None,
    mrt_carrier_km_per_day: float = 0.0,
) -> InfrastructureOpexResult:
    """Section 3-20: decomposition/classification of every Hybrid OPEX term,
    reused verbatim from `conv_config`/`mrt_config` (the SAME
    `NativePathwayScenario` objects already built by `_build_request` for
    Hybrid's own production/transport pipeline runs -- section 82, no new
    pricing assumptions):

    SHARED (charged once, from `conv_config`, regardless of transport split):
      operated_scanners/injection/uptake_resources, operated_cyclotron_units,
      operated_radiopharmacy_units, annual_production_variable_cost,
      cyclotron_annual_opex_per_unit (Cyclotron fixed O&M), Cyclotron/Scanner/
      Other energy, annual_consumable_units, production_staff_fte (Production
      labor -- previously a Hybrid-local constant, now ledger-sourced),
      Clinical labor (REPLACED with the REAL workload-derived
      injection+uptake+scanner staffing total from `staffing`, never added
      alongside a fixed FTE assumption -- same precedent as
      `radiopharm_workflow_staffing.apply_staffing_authority_to_pure_pathway_outcome`).

    CONVENTIONAL_SPECIFIC (from `conv_config`, zero when `conv_active` is
    False): conventional_transport_staff_fte = actual `conv_transporters`
    (workload-derived, not the fixed layout heuristic pure Conventional uses)
    at the SAME $85,000/FTE rate. `annual_conventional_transport_opex` (the
    flat "Conventional transport and handling allowance") is set to 0.0 --
    LEGACY_FLAT_ALLOWANCE concept that does not apply to Hybrid's adaptive
    workload-derived transporter model; the row still appears (structural
    ledger-shape consistency with pure Conventional) but is legitimately $0,
    not omitted.

    MRT_SPECIFIC (from `mrt_config`, present only when `mrt_active`): MRT
    energy, MRT base/endpoint annual O&M, Guideway/vertical-transition/
    building-connection maintenance (using Hybrid's OWN already-computed real
    guideway length/transitions -- `compute_inbound_room_guideway_extension`,
    never re-derived), MRT support labor (previously MISSING from Hybrid's
    bespoke formula entirely), MRT carrier allocated electricity + maintenance
    (previously computed inline by Hybrid itself with the identical formula/
    assumptions -- now sourced from the SAME authoritative ledger function
    instead of a duplicate local computation, section 5; delta = 0 for this
    term).

    Previously MISSING from Hybrid's bespoke formula entirely (added here):
    Cyclotron annual fixed O&M, Radiopharmacy annual fixed O&M, Scanner/
    Cyclotron/Other energy, Consumables, Production variable cost, MRT base/
    endpoint annual O&M, Guideway/vertical-transition maintenance, MRT support
    labor.

    RUNTIME MIGRATION (SPEED & OPEX): when `mrt_runtime_config` is supplied
    (the CURRENT MRT/Hybrid/Part 3E runtime always passes the canonical
    config; every legacy caller/test passes None), the MRT ENERGY and
    MAINTENANCE streams are sourced from the canonical authorities instead of
    the heavy legacy `PlannerAssumptions` values, WITHOUT merging the distinct
    streams and WITHOUT zero-filling any NOT_CALIBRATED component:
      - ENERGY (single "MRT energy" row, category ENERGY): motion electricity
        is computed by `mrt_canonical_configuration.compute_mrt_annual_electricity`
        (E=P*t) from the REAL workload-derived `mrt_carrier_km_per_day` (round-
        trip carrier-km from the actual scheduled MRT missions -- never
        fabricated). Standby/controls/cooling remain NOT_CALIBRATED and are
        NEVER $0-filled (they are simply not added). The canonical MOTION kWh
        replaces the static per-scenario `annual_mrt_energy_kwh` (=25,000) as
        the generic-fallback kWh for this row; the tariff stays separate.
      - MAINTENANCE (category MRT, kept distinct from energy):
        "MRT carrier maintenance" unit cost = canonical
        `compute_mrt_carrier_annual_maintenance_usd` per-unit (=10% x $2,000 =
        $200/carrier-yr, replacing heavy $500); "Guideway annual maintenance"
        per-m-year = canonical guideway CapEx ($2,500/m) x canonical guideway
        maintenance fraction (10%) = $250/m-yr (replacing the heavy $5,000/m x
        3% fallback). "MRT carrier allocated electricity" (a THIRD, distinct
        electricity-adjacent term) is deliberately left UNCHANGED.
      When `mrt_runtime_config is None`, every MRT energy/maintenance term is
      byte-for-byte the prior heavy behaviour.
    """
    # RUNTIME MIGRATION (OPEX): canonical MRT energy + maintenance sourcing.
    # None everywhere -> heavy legacy back-compat (existing default-arg tests).
    _mrt_energy_kwh_override: float | None = None
    _mrt_carrier_maintenance_per_unit_override: float | None = None
    _mrt_guideway_maintenance_per_m_year_override: float | None = None
    _mrt_energy_electricity: "object | None" = None
    if mrt_active and mrt_runtime_config is not None:
        # Lazy import (breaks the shared_mrt_multistream_authority <-> this-module
        # circular import; see module-top note).
        from mrt_transport_energy_maintenance_authority import (
            MRT_GUIDEWAY_MAINTENANCE_FRACTION_PER_YEAR,
            compute_mrt_carrier_annual_maintenance_usd,
        )
        # ENERGY: canonical motion electricity from the REAL carrier-km/day
        # workload (standby/controls/cooling left NOT_CALIBRATED -> not added,
        # never $0-filled). Physical kWh is kept separate from the tariff.
        _mrt_energy_electricity = compute_mrt_annual_electricity(
            carrier_km_per_day=float(mrt_carrier_km_per_day),
            operating_days_per_year=int(assumptions.operating_days_per_year),
            active_power_case="BASE",
            standby_kwh_per_day=None,
            controls_kwh_per_day=None,
            cooling_kwh_per_day=None,
            tariff_usd_per_kwh=CONTROLLED_ELECTRICITY_TARIFF_USD_PER_KWH,
        )
        _mrt_energy_kwh_override = float(_mrt_energy_electricity.total_known_kwh_per_year)
        # MAINTENANCE (distinct stream): carrier per-unit from canonical authority.
        _mrt_carrier_maintenance_per_unit_override = compute_mrt_carrier_annual_maintenance_usd(
            carrier_count=1,
            carrier_capex_usd=mrt_runtime_config.carrier_capex_per_installed_unit_usd,
            fraction_per_year=mrt_runtime_config.carrier_maintenance_fraction_per_year,
        )
        # MAINTENANCE (distinct stream): guideway $/m-year from canonical guideway
        # CapEx x canonical guideway maintenance fraction (>0 -> used directly,
        # never the heavy $5,000/m x 3% fraction-of-capex fallback).
        _mrt_guideway_maintenance_per_m_year_override = (
            float(mrt_runtime_config.guideway_capex_per_m)
            * float(MRT_GUIDEWAY_MAINTENANCE_FRACTION_PER_YEAR.active_value)
        )

    energy_ledger_input = PathwayEnergyLedgerInput(
        cyclotron=build_ledger_energy_component(
            component_name="Cyclotron energy", calculated_energy_kwh=0.0, calibration_status="NOT_CALIBRATED",
            generic_fallback_annual_kwh=conv_config.annual_cyclotron_energy_kwh, uncalibrated_state_minutes=1440.0,
        ),
        scanner=build_ledger_energy_component(
            component_name="Scanner energy", calculated_energy_kwh=0.0, calibration_status="NOT_CALIBRATED",
            generic_fallback_annual_kwh=conv_config.annual_scanner_energy_kwh, uncalibrated_state_minutes=1440.0,
        ),
        other=build_ledger_energy_component(
            component_name="Other energy", calculated_energy_kwh=0.0, calibration_status="NOT_CALIBRATED",
            generic_fallback_annual_kwh=conv_config.annual_other_energy_kwh, uncalibrated_state_minutes=1440.0,
        ),
        mrt=(
            build_ledger_energy_component(
                component_name="MRT energy", calculated_energy_kwh=0.0, calibration_status="NOT_CALIBRATED",
                generic_fallback_annual_kwh=(
                    _mrt_energy_kwh_override
                    if _mrt_energy_kwh_override is not None
                    else mrt_config.annual_mrt_energy_kwh
                ),
                uncalibrated_state_minutes=1440.0,
            )
            if mrt_active else None
        ),
    )

    shared_inputs = InfrastructureOpexInputs(
        pathway="Conventional",
        deployment_mode=conv_config.deployment_mode,
        operated_scanners=candidate.scanners,
        operated_injection_resources=candidate.injection_resources,
        operated_uptake_resources=candidate.uptake_resources,
        operated_cyclotron_units=conv_config.operated_cyclotron_units,
        operated_radiopharmacy_units=conv_config.operated_radiopharmacy_units,
        operating_days_per_year=int(assumptions.operating_days_per_year),
        annual_conventional_transport_opex=0.0,
        conventional_transport_staff_fte=float(conv_transporters) if conv_active else 0.0,
        conventional_transport_staff_loaded_cost_per_fte=conv_config.conventional_transport_staff_loaded_cost_per_fte,
        annual_production_variable_cost=conv_config.annual_production_variable_cost,
        cyclotron_annual_opex_per_unit=conv_config.cyclotron_annual_opex_per_unit,
        annual_scanner_energy_kwh=conv_config.annual_scanner_energy_kwh,
        annual_cyclotron_energy_kwh=conv_config.annual_cyclotron_energy_kwh,
        annual_other_energy_kwh=conv_config.annual_other_energy_kwh,
        electricity_cost_per_kwh=conv_config.electricity_cost_per_kwh,
        clinical_staff_fte=0.0,  # replaced below with real workload-derived staffing
        clinical_staff_loaded_cost_per_fte=0.0,
        production_staff_fte=conv_config.production_staff_fte,
        production_staff_loaded_cost_per_fte=conv_config.production_staff_loaded_cost_per_fte,
        annual_consumable_units=conv_config.annual_consumable_units,
        consumable_cost_per_unit=conv_config.consumable_cost_per_unit,
        assumptions=assumptions,
        energy_ledger_input=energy_ledger_input,
    )
    shared_result = calculate_infrastructure_opex(shared_inputs)
    combined_fte = staffing.injection_staff.fte + staffing.uptake_staff.fte + staffing.scanner_staff.fte
    shared_ledger = replace_ledger_component(
        ledger=shared_result.ledger, component="Clinical labor",
        computed_annual_cost=staffing.total_new_pool_annual_opex,
        quantity=combined_fte, unit="FTE-year",
        cost_basis="radiopharm_workflow_staffing.compute_radiopharm_workflow_staffing() -- workload-derived from the REAL joint schedule, replaces the fixed FTE assumption (never added alongside it)",
    )

    if mrt_active:
        mrt_inputs = InfrastructureOpexInputs(
            pathway="MRT",
            deployment_mode=mrt_config.deployment_mode,
            operating_days_per_year=int(assumptions.operating_days_per_year),
            operated_mrt_base_units=1,
            operated_mrt_endpoints=mrt_endpoint_count,
            installed_mrt_carriers=mrt_carriers,
            operated_mrt_carriers=mrt_carriers,
            operated_guideway_length_m=mrt_guideway_length_m,
            operated_vertical_transitions=mrt_transitions,
            guideway_capex_per_m=mrt_config.guideway_capex_per_m,
            # MAINTENANCE stream (canonical when runtime config supplied): $/m-year
            # override (>0 -> used directly) else heavy fraction-of-capex fallback.
            guideway_maintenance_per_m_year=(
                _mrt_guideway_maintenance_per_m_year_override
                if _mrt_guideway_maintenance_per_m_year_override is not None
                else mrt_config.guideway_maintenance_per_m_year
            ),
            mrt_base_annual_opex_per_unit=mrt_config.mrt_base_annual_opex_per_unit,
            vertical_transition_annual_opex_per_unit=mrt_config.vertical_transition_annual_opex_per_unit,
            building_connection_annual_opex_per_unit=mrt_config.building_connection_annual_opex_per_unit,
            # ENERGY stream (canonical motion kWh when runtime config supplied,
            # else static per-scenario kWh). Kept a SINGLE "MRT energy" row.
            annual_mrt_energy_kwh=(
                _mrt_energy_kwh_override
                if _mrt_energy_kwh_override is not None
                else mrt_config.annual_mrt_energy_kwh
            ),
            electricity_cost_per_kwh=(
                CONTROLLED_ELECTRICITY_TARIFF_USD_PER_KWH
                if mrt_runtime_config is not None
                else mrt_config.electricity_cost_per_kwh
            ),
            # MAINTENANCE stream (canonical carrier maintenance per-unit when
            # runtime config supplied; None -> heavy PlannerAssumptions $500/unit).
            mrt_carrier_maintenance_opex_per_installed_unit_year=_mrt_carrier_maintenance_per_unit_override,
            mrt_support_staff_fte=mrt_config.mrt_support_staff_fte,
            mrt_support_staff_loaded_cost_per_fte=mrt_config.mrt_support_staff_loaded_cost_per_fte,
            assumptions=assumptions,
            energy_ledger_input=energy_ledger_input,
        )
        mrt_result = calculate_infrastructure_opex(mrt_inputs)
        final_ledger = merge_shared_and_mode_specific_ledgers(
            shared_and_conventional_ledger=shared_ledger, mrt_specific_ledger=mrt_result.ledger,
            mrt_specific_components=MRT_SPECIFIC_LEDGER_COMPONENTS,
        )
    else:
        final_ledger = shared_ledger

    totals = recompute_ledger_totals(final_ledger)
    return InfrastructureOpexResult(
        pathway="Hybrid",
        deployment_mode=conv_config.deployment_mode,
        operated_quantities=shared_result.operated_quantities,
        clinical_fixed_opex=totals["clinical_fixed_opex"],
        production_fixed_opex=totals["production_fixed_opex"],
        conventional_specific_opex=totals["conventional_specific_opex"],
        mrt_specific_opex=totals["mrt_specific_opex"],
        energy_opex=totals["energy_opex"],
        labor_opex=totals["labor_opex"],
        consumables_opex=totals["consumables_opex"],
        fixed_annual_opex=totals["fixed_annual_opex"],
        variable_annual_opex=totals["variable_annual_opex"],
        total_annual_opex=totals["total_annual_opex"],
        ledger=final_ledger,
        economic_comparability_status=energy_ledger_input.economic_comparability_status(),
    )


def evaluate_hybrid_zone_candidate(
    *,
    geometry: BenchmarkGeometry,
    candidate: HybridZoneCandidate,
    demand: int,
    production_basis: ProductionBasis,
    assumptions: PlannerAssumptions,
    network_assumptions: SharedNetworkAssumptions,
    seed: int = 1,
    retention_threshold: float | None = None,
    mrt_runtime_config: "MrtRuntimeConfig | None" = None,
) -> HybridEvaluationResult:
    """Evaluate one Hybrid zone-assignment candidate through ONE joint
    Conventional+MRT clinical schedule (see module docstring).

    RUNTIME MIGRATION: `mrt_runtime_config` (None by default) lets the CURRENT
    four-architecture MRT/Hybrid runtime price the MRT hardware from the
    canonical compact MRT authority (guideway $2,500/m two-way, carrier $2,000,
    NO $6,000,000 flat base). When None -- every legacy caller and existing
    default-arg test -- the exact heavy `assumptions.*` behaviour is preserved
    unchanged (mrt_guideway_capex_per_m=$5,000, mrt_carrier_capex_per_installed_unit
    =$10,000, mrt_infrastructure_capex=$6,000,000)."""
    effective_threshold = (
        float(assumptions.minimum_release_to_administration_retention_fraction) if retention_threshold is None else float(retention_threshold)
    )
    all_floors = tuple(sorted(candidate.mrt_floors | candidate.conventional_floors))
    if not all_floors:
        raise ValueError("Hybrid candidate must have at least one active floor")

    # ONE shared room layout (shared clinical resources, common to both zones).
    layout = _assign_rooms_for_candidate(
        geometry=geometry,
        active_floors=all_floors,
        scanners=candidate.scanners,
        injections=candidate.injection_resources,
        uptake=candidate.uptake_resources,
        distribution_mode="balanced",
        assumptions=assumptions,
        candidate_id=candidate.candidate_id,
        pattern_id=f"HYBRID:{candidate.candidate_id}",
        distribution_concurrency=max(1, min(8, len(all_floors))),
        feasible_room_ids=None,
    )
    if layout is None:
        raise ValueError(f"Hybrid candidate {candidate.candidate_id} could not assign rooms (space unavailable)")

    room_mode: dict[str, TransportMode] = {}
    for room_id in layout.injection_rooms:
        floor = _room_floor(geometry, room_id)
        room_mode[room_id] = "MRT" if floor in candidate.mrt_floors else "CONVENTIONAL"
    mrt_rooms = frozenset(r for r, m in room_mode.items() if m == "MRT")
    conv_rooms = frozenset(r for r, m in room_mode.items() if m == "CONVENTIONAL")
    total_injection = len(layout.injection_rooms)

    # ONE production authority (section 5/6): run each mode's native pipeline
    # once to obtain a fully resolved ProductionClinicalScenario (transport
    # physics, facility model) per mode; Conventional's run supplies the
    # authoritative batch/release/patient-population reference (conservative
    # transport-time basis for production sizing).
    conv_request = _build_request(
        demand=demand, pathway_layout=layout, production_basis=production_basis, assumptions=assumptions, seed=seed,
    )
    conv_result = run_native_pathway_pipeline(conv_request, pathway="Conventional")
    # RUNTIME MIGRATION (SPEED): the MRT pathway's STRAIGHT/HORIZONTAL route-time
    # cruise speed is sourced from the canonical runtime config (10.0 m/s) when
    # present; None -> heavy legacy assumptions.mrt_horizontal_speed_m_per_s. The
    # Conventional request above is deliberately left unchanged (fairness: Manual
    # / Automated Conventional route physics are untouched).
    mrt_request = _build_request(
        demand=demand, pathway_layout=layout, production_basis=production_basis, assumptions=assumptions, seed=seed,
        mrt_straight_speed_m_per_s_override=(
            mrt_runtime_config.max_straight_speed_m_per_s if mrt_runtime_config is not None else None
        ),
    )
    mrt_result = run_native_pathway_pipeline(mrt_request, pathway="MRT")

    conv_production = conv_result.operational_result.production_clinical_result
    mrt_production = mrt_result.operational_result.production_clinical_result
    conv_scenario = conv_production.scenario
    mrt_scenario = mrt_production.scenario

    released_inventory = conv_production.released_inventory
    batch_release_mappings = conv_production.batch_release_mappings
    destination_floor_by_id = _destination_floor_lookup(conv_scenario.facility_engineering_model)

    # Deterministic per-patient destination assignment held identical across
    # both mode-specific payload groupings (same released_inventory, same
    # active_destinations, same BALANCED_ROUND_ROBIN policy).
    conv_capacity_payloads = _build_transport_payloads(
        released_inventory, conv_scenario.conventional_payload_capacity_doses, "Conventional",
        conv_scenario.destination_assignment_policy, destination_floor_by_id,
    )
    mrt_capacity_payloads = _build_transport_payloads(
        released_inventory, mrt_scenario.mrt_payload_capacity_doses, "MRT",
        mrt_scenario.destination_assignment_policy, destination_floor_by_id,
    )
    # Each independent _build_transport_payloads call renumbers payload_id from
    # PAY-00001; mode-prefix so merged payload_ids never collide when the two
    # mode-specific sets are combined into the joint clinical schedule below.
    conv_capacity_payloads = tuple(replace(p, payload_id=f"CONV-{p.payload_id}") for p in conv_capacity_payloads)
    mrt_capacity_payloads = tuple(replace(p, payload_id=f"MRT-{p.payload_id}") for p in mrt_capacity_payloads)
    conv_payloads = tuple(p for p in conv_capacity_payloads if p.destination_object_id in conv_rooms)
    mrt_payloads = tuple(p for p in mrt_capacity_payloads if p.destination_object_id in mrt_rooms)

    # Adaptive, workload-driven minimum-feasible transport resource sizing
    # (Gap 2 / sections 21-22/42-44), replacing the Phase 15 floor-count
    # heuristic that caused the 3-vs-4 / 6-vs-7 discrepancies.
    if conv_payloads:
        conv_search = _adaptive_transport_resource_search(
            dimension="conventional_transporters",
            schedule_fn=lambda count: _schedule_conventional_transport_jobs(conv_payloads, count, conv_scenario),
            wait_extractor=lambda result: result.average_wait_minutes,
        )
    else:
        conv_search = ResourceSearchDiagnostic("conventional_transporters", 0, 0, "NO_WORKLOAD")
    conv_transporters = conv_search.selected_value

    mrt_route_profiles = {dest: _resolve_mrt_route_profile(mrt_scenario, dest) for dest in mrt_rooms}
    if mrt_payloads:
        mrt_search = _adaptive_transport_resource_search(
            dimension="mrt_carriers",
            schedule_fn=lambda count: _schedule_mrt_carrier_transport_jobs(
                mrt_payloads, count, mrt_route_profiles, mrt_scenario.mrt_reposition_policy, mrt_scenario.mrt_payload_capacity_doses,
            ),
            wait_extractor=lambda result: result.average_carrier_queue_wait_minutes,
        )
    else:
        mrt_search = ResourceSearchDiagnostic("mrt_carriers", 0, 0, "NO_WORKLOAD")
    mrt_carriers = mrt_search.selected_value

    conv_transport_schedule = (
        _schedule_conventional_transport_jobs(conv_payloads, conv_transporters, conv_scenario)
        if conv_payloads
        else ConventionalTransportScheduleResult((), 0, 0, 0.0, 0.0, 0.0, 0.0, ())
    )
    mrt_transport_schedule = (
        _schedule_mrt_carrier_transport_jobs(
            mrt_payloads, mrt_carriers, mrt_route_profiles, mrt_scenario.mrt_reposition_policy, mrt_scenario.mrt_payload_capacity_doses,
        )
        if mrt_payloads
        else None
    )

    # GAP 1 CENTRAL CORRECTION: merge both modes' deliveries into ONE
    # deterministic clinical arrival stream and run ONE shared
    # injection->uptake->scanner schedule (sections 8-13).
    all_payloads = conv_payloads + mrt_payloads
    all_deliveries = conv_transport_schedule.deliveries + (mrt_transport_schedule.deliveries if mrt_transport_schedule else ())
    merged_batch_releases = _build_batch_releases_from_transport(all_payloads, all_deliveries)

    joint_inputs = OperatingDayInputs(
        clinical_day_start_minute=conv_scenario.clinical_day_start_minute,
        operating_day_minutes=conv_scenario.operating_day_minutes,
        batch_releases=list(merged_batch_releases),
        transport_minutes=0.0,
        injection_service_minutes=conv_scenario.injection_service_minutes,
        uptake_minutes=conv_scenario.uptake_minutes,
        scanner_service_minutes=conv_scenario.scanner_service_minutes,
        injection_resources=candidate.injection_resources,
        uptake_resources=candidate.uptake_resources,
        scanners=candidate.scanners,
        distribution_concurrency=max(1, len(all_payloads)),
    )
    joint_clinical_schedule = schedule_operating_day(joint_inputs)
    joint_patient_traces: tuple[ProductionClinicalPatientTrace, ...] = _build_patient_traces(
        batch_release_mappings, all_payloads, all_deliveries, joint_clinical_schedule,
    )

    half_life_lookup = load_radionuclide_half_lives()
    half_life = float(half_life_lookup[production_basis.radionuclide])
    batch_release_time_by_id = {mapping.batch_id: mapping.release_time_minutes for mapping in batch_release_mappings}

    origin_by_cyclotron = conv_scenario.cyclotron_radiopharmacy_origin_object_id_by_cyclotron_id
    hybrid_traces: list[HybridPatientTrace] = []
    for trace in joint_patient_traces:
        mode: TransportMode = room_mode.get(trace.assigned_destination_object_id, "CONVENTIONAL")
        release_time = batch_release_time_by_id[trace.batch_id]
        # Section 15: retention calculated strictly AFTER joint scheduling,
        # using the authoritative decay engine, from the ACTUAL joint
        # injection_start (not the isolated single-mode run's timing).
        elapsed = max(0.0, float(trace.injection_start) - float(release_time))
        retained = retained_fraction(elapsed, half_life)
        retention_pass = retained >= effective_threshold
        # Live-State adapter identity (section 6): ONE shared INJ/UP/SCN
        # persistent-identity convention, same as Conventional/MRT -- never a
        # per-transport-mode duplicate.
        injection_resource_id = (
            trace.inbound_room_id or "" if trace.injection_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
            else resource_id_for_index("INJECTION_ROOM", trace.injection_resource_index)
        )
        uptake_resource_id = (
            trace.inbound_room_id or "" if trace.uptake_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
            else resource_id_for_index("UPTAKE_ROOM", trace.uptake_resource_index)
        )
        scanner_resource_id = resource_id_for_index("SCANNER", trace.scanner_resource_index)
        hybrid_traces.append(
            HybridPatientTrace(
                patient_id=trace.patient_id,
                destination_room_id=trace.assigned_destination_object_id,
                destination_floor=_room_floor(geometry, trace.assigned_destination_object_id),
                transport_mode=mode,
                production_cycle_batch_id=trace.batch_id,
                payload_id=trace.payload_id,
                release_time_minutes=release_time,
                injection_start_minutes=trace.injection_start,
                clinically_completed=bool(trace.completed_within_operating_day),
                elapsed_release_to_administration_minutes=elapsed,
                retained_fraction=retained,
                retention_pass=retention_pass,
                retention_qualified_completion=bool(trace.completed_within_operating_day) and retention_pass,
                assigned_cyclotron_id=trace.assigned_cyclotron_id,
                radiopharmacy_origin_id=origin_by_cyclotron.get(trace.assigned_cyclotron_id) if origin_by_cyclotron else None,
                production_window_id=trace.production_window_id,
                transport_arrival_time_minutes=trace.transport_arrival_time_minutes,
                clinical_resource_mode=trace.clinical_resource_mode,
                inbound_room_id=trace.inbound_room_id,
                injection_resource_id=injection_resource_id,
                uptake_resource_id=uptake_resource_id,
                scanner_resource_id=scanner_resource_id,
                injection_end_minutes=trace.injection_end,
                uptake_start_minutes=trace.uptake_start,
                uptake_end_minutes=trace.uptake_end,
                scan_start_minutes=trace.scan_start,
                scan_end_minutes=trace.scan_end,
            )
        )

    retention_qualified_completed = sum(1 for t in hybrid_traces if t.retention_qualified_completion)

    # MRT network cost: minimal, shared-trunk-deduplicated, MRT-zone-only
    # (sections 40-41), reusing the same accumulation technique validated for
    # inbound rooms, applied here to Hybrid MRT injection rooms.
    mrt_horizontal = 0.0
    mrt_vertical = 0.0
    mrt_transitions = 0
    mrt_guideway_capex = 0.0
    cumulative_mrt_floors: set[int] = set()
    # RUNTIME MIGRATION: canonical guideway unit cost ($2,500/m two-way) when a
    # runtime config is supplied; else None -> heavy assumptions.mrt_guideway_capex_per_m.
    _guideway_override = None if mrt_runtime_config is None else mrt_runtime_config.guideway_capex_per_m
    for room_id in sorted(mrt_rooms):
        extension = compute_inbound_room_guideway_extension(
            geometry=geometry, room_id=room_id, already_serviced_floors=frozenset(cumulative_mrt_floors),
            assumptions=assumptions, network_assumptions=network_assumptions,
            guideway_capex_per_m_override=_guideway_override,
        )
        mrt_horizontal += extension.incremental_horizontal_m
        mrt_vertical += extension.incremental_vertical_m
        mrt_transitions += extension.incremental_transitions
        mrt_guideway_capex += extension.incremental_capex
        cumulative_mrt_floors.add(_room_floor(geometry, room_id))

    scanner_uptake_injection_capex = (
        candidate.scanners * assumptions.scanner_capex
        + candidate.injection_resources * assumptions.additional_room_capex
        + candidate.uptake_resources * assumptions.additional_room_capex
    )
    cyclotron_capex = assumptions.cyclotron_purchase_capex + assumptions.cyclotron_installation_capex
    conventional_capex = 125_000.0 if conv_rooms else 0.0
    # RUNTIME MIGRATION: canonical compact MRT has NO $6,000,000 flat base
    # (include_flat_infrastructure_base=False) and prices carriers at $2,000.
    # When mrt_runtime_config is None, the heavy $6M base + $10,000/carrier are
    # preserved exactly (legacy back-compat).
    if mrt_runtime_config is None:
        mrt_base_capex = assumptions.mrt_infrastructure_capex if mrt_rooms else 0.0
        mrt_carrier_unit_capex = assumptions.mrt_carrier_capex_per_installed_unit
    else:
        mrt_base_capex = (
            assumptions.mrt_infrastructure_capex
            if (mrt_rooms and mrt_runtime_config.include_flat_infrastructure_base) else 0.0
        )
        mrt_carrier_unit_capex = mrt_runtime_config.carrier_capex_per_installed_unit_usd
    mrt_endpoint_capex = len(mrt_rooms) * assumptions.endpoint_capex
    mrt_carrier_capex = mrt_carriers * mrt_carrier_unit_capex
    total_capex = (
        scanner_uptake_injection_capex + cyclotron_capex + conventional_capex
        + mrt_base_capex + mrt_endpoint_capex + mrt_carrier_capex + mrt_guideway_capex
    )

    # Staffing authority integration (section 20): derived from the REAL
    # merged joint clinical schedule (joint_patient_traces), never a
    # per-mode-reconstructed or synthetic schedule -- this is the fix for the
    # prior inflated ad-hoc Hybrid staffing estimate, which used a synthetic
    # zero-wait reconstruction that overstated uptake/scanner concurrency.
    staffing = compute_radiopharm_workflow_staffing(
        patient_schedules=joint_patient_traces,
        operating_days_per_year=int(assumptions.operating_days_per_year),
    )

    # RUNTIME MIGRATION (OPEX energy): REAL workload-derived MRT carrier-km/day
    # for the canonical motion-electricity authority (E=P*t). Each scheduled MRT
    # job's one-way route length is the sum of its route segment lengths; the
    # carrier returns (round trip), so daily carrier-km = 2 * sum(one-way m)/1000.
    # No fabrication: derived from the ACTUAL scheduled MRT missions for the day.
    mrt_carrier_km_per_day = 0.0
    if mrt_transport_schedule is not None:
        one_way_m = sum(
            float(segment.length_m) for job in mrt_transport_schedule.jobs for segment in job.route
        )
        mrt_carrier_km_per_day = 2.0 * one_way_m / 1000.0

    # ONE authoritative OPEX ledger (this build, sections 5-6/41): REPLACES
    # the old bespoke scanner_uptake_injection_opex/conv_transport_labor_opex/
    # mrt_carrier_opex/production_labor_opex/total_annual_opex formula, which
    # is REMOVED_FROM_AUTHORITATIVE_PATH (never a second, competing total).
    opex_result = _build_hybrid_opex_result(
        candidate=candidate, conv_config=conv_request.conventional, mrt_config=mrt_request.mrt,
        conv_active=bool(conv_rooms), mrt_active=bool(mrt_rooms), conv_transporters=conv_transporters,
        mrt_carriers=mrt_carriers, mrt_endpoint_count=len(mrt_rooms), mrt_guideway_length_m=mrt_horizontal + mrt_vertical,
        mrt_transitions=mrt_transitions, staffing=staffing, assumptions=assumptions,
        mrt_runtime_config=mrt_runtime_config,
        mrt_carrier_km_per_day=mrt_carrier_km_per_day,
    )
    production_labor_opex = next(row.annual_cost for row in opex_result.ledger if row.component == "Production labor")

    qualified_annual_revenue = retention_qualified_completed * assumptions.revenue_per_scan * assumptions.operating_days_per_year
    # Section 36: NPV propagates through the EXISTING lifecycle economics
    # engine -- no independent NPV calculation here.
    lifecycle_result = evaluate_lifecycle_economics(
        initial_capex=total_capex,
        installed_capacity_per_day=float(retention_qualified_completed),
        annual_opex=opex_result.total_annual_opex,
        revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=assumptions.operating_days_per_year,
        discount_rate_pct=assumptions.discount_rate_pct,
        analysis_years=assumptions.analysis_years,
        starting_demand_per_day=float(retention_qualified_completed),
        annual_demand_growth_rate=0.0,
    )

    mrt_penetration = 100.0 * len(mrt_rooms) / total_injection if total_injection else 0.0

    return HybridEvaluationResult(
        candidate=candidate,
        mrt_penetration_pct=mrt_penetration,
        patient_traces=tuple(sorted(hybrid_traces, key=lambda t: t.patient_id)),
        retention_qualified_completed=retention_qualified_completed,
        conventional_transporters=conv_transporters,
        mrt_carriers=mrt_carriers,
        conventional_transporter_search=conv_search,
        mrt_carrier_search=mrt_search,
        mrt_guideway_horizontal_m=mrt_horizontal,
        mrt_guideway_vertical_m=mrt_vertical,
        mrt_transitions=mrt_transitions,
        staffing=staffing,
        production_labor_annual_opex=production_labor_opex,
        total_capex=total_capex,
        total_annual_opex=opex_result.total_annual_opex,
        qualified_annual_revenue=qualified_annual_revenue,
        qualified_lifecycle_npv=lifecycle_result.final_npv,
        opex_result=opex_result,
        radionuclide=production_basis.radionuclide,
        injection_service_minutes=conv_scenario.injection_service_minutes,
        uptake_minutes=conv_scenario.uptake_minutes,
        scanner_service_minutes=conv_scenario.scanner_service_minutes,
        clinical_day_start_minute=conv_scenario.clinical_day_start_minute,
        operating_day_minutes=conv_scenario.operating_day_minutes,
        half_life_minutes=half_life,
        retention_threshold_used=effective_threshold,
    )


# ---------------------------------------------------------------------------
# Hybrid Live-State affected-subset rerun (rolling-reoptimization locality for
# Hybrid, reusing the SAME `schedule_operating_day` primitive -- never a
# second Hybrid scheduler). Consumed by `live_operational_state.py`'s
# `apply_hybrid_event_and_replan` (section 4/14 of the Hybrid live-state spec).
# ---------------------------------------------------------------------------


def rerun_hybrid_affected_subset(
    *,
    hybrid_result: HybridEvaluationResult,
    affected_patient_ids: frozenset[str],
    blocked_injection_indices: frozenset[int] = frozenset(),
    blocked_uptake_indices: frozenset[int] = frozenset(),
    blocked_scanner_indices: frozenset[int] = frozenset(),
    injection_reserved_until: Mapping[int, float] | None = None,
    uptake_reserved_until: Mapping[int, float] | None = None,
    scanner_reserved_until: Mapping[int, float] | None = None,
) -> tuple[HybridPatientTrace, ...]:
    """Reschedules ONLY `affected_patient_ids` through the EXISTING
    `schedule_operating_day` (the same primitive `evaluate_hybrid_zone_candidate`
    already uses for the joint schedule), seeded with `*_reserved_until` /
    `blocked_*_indices` computed by the caller from the PRESERVED (untouched)
    Hybrid patients -- identity-sticky locality, reusing the mechanism already
    proven for Conventional/MRT (`operating_day_scheduler.py::_seed`). Never
    reruns the whole Hybrid joint schedule, never builds a second scheduler.

    Each affected patient's original `payload_id`/batch/transport-arrival time
    is preserved as the rerun's release basis (transport itself is NOT
    rerun) -- only the shared clinical (injection/uptake/scanner) placement is
    recomputed."""
    affected_traces = [t for t in hybrid_result.patient_traces if t.patient_id in affected_patient_ids]
    if not affected_traces:
        return ()
    by_payload: dict[str, list[HybridPatientTrace]] = {}
    for t in affected_traces:
        by_payload.setdefault(t.payload_id, []).append(t)

    batch_releases = [
        BatchRelease(
            batch_id=group[0].production_cycle_batch_id,
            release_time_minutes=group[0].transport_arrival_time_minutes,
            patients_in_batch=len(group),
            release_unit_id=payload_id,
            patient_clinical_modes=tuple(g.clinical_resource_mode for g in group),  # type: ignore[arg-type]
            patient_inbound_room_ids=tuple(g.inbound_room_id for g in group),
        )
        for payload_id, group in sorted(by_payload.items())
    ]
    inputs = OperatingDayInputs(
        clinical_day_start_minute=hybrid_result.clinical_day_start_minute,
        operating_day_minutes=hybrid_result.operating_day_minutes,
        batch_releases=batch_releases,
        transport_minutes=0.0,
        injection_service_minutes=hybrid_result.injection_service_minutes,
        uptake_minutes=hybrid_result.uptake_minutes,
        scanner_service_minutes=hybrid_result.scanner_service_minutes,
        injection_resources=hybrid_result.candidate.injection_resources,
        uptake_resources=hybrid_result.candidate.uptake_resources,
        scanners=hybrid_result.candidate.scanners,
        distribution_concurrency=max(1, len(affected_traces)),
        blocked_injection_indices=blocked_injection_indices,
        blocked_uptake_indices=blocked_uptake_indices,
        blocked_scanner_indices=blocked_scanner_indices,
        injection_reserved_until=injection_reserved_until or {},
        uptake_reserved_until=uptake_reserved_until or {},
        scanner_reserved_until=scanner_reserved_until or {},
    )
    schedule_result = schedule_operating_day(inputs)

    schedules_by_release_unit_id: dict[str, list] = {}
    for ps in schedule_result.patient_schedules:
        schedules_by_release_unit_id.setdefault(ps.release_unit_id, []).append(ps)
    for lst in schedules_by_release_unit_id.values():
        lst.sort(key=lambda ps: ps.patient_id)

    updated: list[HybridPatientTrace] = []
    for payload_id, group in sorted(by_payload.items()):
        schedules = schedules_by_release_unit_id.get(payload_id, [])
        for original, ps in zip(group, schedules):
            elapsed = max(0.0, float(ps.injection_start) - float(original.release_time_minutes))
            retained = retained_fraction(elapsed, hybrid_result.half_life_minutes)
            retention_pass = retained >= hybrid_result.retention_threshold_used
            injection_resource_id = (
                original.inbound_room_id or "" if ps.injection_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
                else resource_id_for_index("INJECTION_ROOM", ps.injection_resource_index)
            )
            uptake_resource_id = (
                original.inbound_room_id or "" if ps.uptake_resource_index == DEDICATED_ROOM_RESOURCE_INDEX
                else resource_id_for_index("UPTAKE_ROOM", ps.uptake_resource_index)
            )
            scanner_resource_id = resource_id_for_index("SCANNER", ps.scanner_resource_index)
            updated.append(replace(
                original,
                injection_start_minutes=ps.injection_start,
                injection_end_minutes=ps.injection_end,
                uptake_start_minutes=ps.uptake_start,
                uptake_end_minutes=ps.uptake_end,
                scan_start_minutes=ps.scan_start,
                scan_end_minutes=ps.scan_end,
                clinically_completed=bool(ps.completed_within_operating_day),
                elapsed_release_to_administration_minutes=elapsed,
                retained_fraction=retained,
                retention_pass=retention_pass,
                retention_qualified_completion=bool(ps.completed_within_operating_day) and retention_pass,
                injection_resource_id=injection_resource_id,
                uptake_resource_id=uptake_resource_id,
                scanner_resource_id=scanner_resource_id,
            ))
    return tuple(sorted(updated, key=lambda t: t.patient_id))

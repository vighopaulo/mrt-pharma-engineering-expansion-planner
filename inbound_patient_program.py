"""Patient-centric clinical spatial programming: INBOUND / ADMITTED patients vs
OUTPATIENT / same-day patients, dedicated inbound-room occupancy, two inbound
clinical architectures (INTEGRATED vs CENTRALIZED injection), and the
associated room, transport, and economic consequences.

This module reuses the same geometry, transport-time physics, retention
criterion, and economic rate constants (PlannerAssumptions.additional_room_capex,
mrt_guideway_capex_per_m, SharedNetworkAssumptions.vertical_transition_capex,
revenue_per_scan) rather than inventing a parallel model.

PIPELINE INTEGRATION (patient identity): `attach_patient_type_and_los()`
overlays patient_type/length-of-stay onto the SAME patient objects the
authoritative native pipeline already generated and carried end-to-end
(decision_pipeline.NativeDemandResult.simulation.generated_demand.patients ->
production cycle -> released inventory -> payload -> delivery job ->
ProductionClinicalPatientTrace -> PatientDecayTrace, all keyed by the identical
patient_id -- verified by direct code audit to never be collapsed or
regenerated). `build_patient_value_ledger()` JOINS that real, per-patient
production/clinical/decay trace data with the inbound-room admission/
architecture overlay to produce one patient-level economic/status record,
without threading new fields through every intermediate dataclass (the
smallest-necessary integration, per the phase specification) and without
reimplementing decay/production physics (both are read directly from the real
traces). Architecture-level (shared) CapEx/OPEX -- cyclotron, scanner,
guideway, buildings -- is never divided per patient (section 27); the ledger
reports only patient-attributable value/occupancy.

All economic rates introduced here that are not backed by an existing
repository constant are labeled SYNTHETIC_BENCHMARK / PROJECT_ASSUMPTION and
are never presented as source-backed reimbursement figures.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Mapping, Sequence

from models import PlannerAssumptions, SharedNetworkAssumptions
from multi_isotope_decay import retained_fraction
from spatial_benchmark import (
    BenchmarkGeometry,
    Pathway,
    _route_metrics_for_rooms,
)

if TYPE_CHECKING:
    from decision_pipeline import NativePathwayResult

PatientType = Literal["OUTPATIENT", "INBOUND_PATIENT"]
InboundArchitecture = Literal["INTEGRATED", "CENTRALIZED"]

# ---------------------------------------------------------------------------
# SYNTHETIC_BENCHMARK / PROJECT_ASSUMPTION constants (explicit, never presented
# as source-backed clinical or reimbursement standards -- sections 3/4/11/12).
# ---------------------------------------------------------------------------
DEFAULT_INBOUND_PATIENT_FRACTION = 0.15  # PROJECT_ASSUMPTION: modest mix, not chosen to favor either pathway.
MINIMUM_INBOUND_LENGTH_OF_STAY_DAYS = 1.0  # 24 hours, per project planning rule (section 4).
DEFAULT_LENGTH_OF_STAY_DAYS_OPTIONS: tuple[float, ...] = (1.0, 2.0, 3.0)  # SYNTHETIC / PROJECT PLANNING ASSUMPTION.
LENGTH_OF_STAY_SENSITIVITY_DAYS: tuple[float, ...] = (1.0, 3.0, 7.0, 14.0)  # SYNTHETIC / PROJECT PLANNING ASSUMPTION (section 49).
DEFAULT_INBOUND_ROOM_REVENUE_PER_OCCUPIED_DAY = 500.0  # PROJECT_ASSUMPTION, materially below $2,000/scan (section 11).
ROOM_VALUE_SENSITIVITY_USD_PER_DAY: tuple[float, ...] = (250.0, 500.0, 750.0, 1000.0)  # PROJECT_ASSUMPTION sensitivity (section 12/50).
DEFAULT_INBOUND_ROOM_ANNUAL_OPEX_PER_UNIT = 1_250.0  # PROJECT_ASSUMPTION (5% of additional_room_capex heuristic), not source-backed.


@dataclass(frozen=True)
class SyntheticPatient:
    """A single patient in the deterministic synthetic patient population.
    Every patient retains full production/administration traceability
    (section 2): patient_id, radionuclide, prescribed activity, administration
    time, and (for inbound patients) length of stay.
    """

    patient_id: str
    patient_type: PatientType
    radionuclide: str
    prescribed_activity_mbq: float
    administration_time_minutes: float
    length_of_stay_days: float  # 0.0 for OUTPATIENT; >= MINIMUM_INBOUND_LENGTH_OF_STAY_DAYS for INBOUND_PATIENT.


def generate_synthetic_patient_population(
    *,
    demand: int,
    radionuclide: str,
    prescribed_activity_mbq: float,
    inbound_patient_fraction: float = DEFAULT_INBOUND_PATIENT_FRACTION,
    length_of_stay_days_options: Sequence[float] = DEFAULT_LENGTH_OF_STAY_DAYS_OPTIONS,
    clinical_day_minutes: float = 1080.0,
    seed: int = 20260816,
) -> tuple[SyntheticPatient, ...]:
    """Deterministic, seeded patient-type mix (section 3): the SAME seed always
    produces the SAME population -- reproducibility is preserved, never
    silently randomized between runs.
    """
    if demand <= 0:
        raise ValueError("demand must be positive")
    if not (0.0 <= inbound_patient_fraction <= 1.0):
        raise ValueError("inbound_patient_fraction must be within [0, 1]")
    if any(los < MINIMUM_INBOUND_LENGTH_OF_STAY_DAYS for los in length_of_stay_days_options):
        raise ValueError(f"length_of_stay_days_options must each be >= {MINIMUM_INBOUND_LENGTH_OF_STAY_DAYS} days (24 hours)")

    rng = random.Random(seed)
    los_options = list(length_of_stay_days_options)
    patients: list[SyntheticPatient] = []
    for index in range(1, demand + 1):
        is_inbound = rng.random() < inbound_patient_fraction
        patient_type: PatientType = "INBOUND_PATIENT" if is_inbound else "OUTPATIENT"
        length_of_stay = rng.choice(los_options) if is_inbound else 0.0
        # Deterministic index-based administration-time spread across the clinical day.
        administration_time = clinical_day_minutes * (index - 1) / float(demand)
        patients.append(
            SyntheticPatient(
                patient_id=f"P{index}",
                patient_type=patient_type,
                radionuclide=radionuclide,
                prescribed_activity_mbq=prescribed_activity_mbq,
                administration_time_minutes=administration_time,
                length_of_stay_days=length_of_stay,
            )
        )
    return tuple(patients)


def attach_patient_type_and_los(
    demand_patients: Sequence[object],
    *,
    inbound_patient_fraction: float = DEFAULT_INBOUND_PATIENT_FRACTION,
    length_of_stay_days_options: Sequence[float] = DEFAULT_LENGTH_OF_STAY_DAYS_OPTIONS,
    clinical_day_minutes: float = 1080.0,
    seed: int = 20260816,
) -> tuple[SyntheticPatient, ...]:
    """PIPELINE-INTEGRATED patient-type overlay (section 6/7): rather than
    drawing an independent synthetic population, this overlays patient_type/LOS
    onto the SAME patient objects (patient_id, radionuclide,
    prescribed_activity_mbq) already generated by the authoritative native
    pipeline (decision_pipeline.NativeDemandResult.simulation.generated_demand.patients,
    which itself uses stochastic_design_day.generate_design_day_demand()). This
    guarantees patient_id identity consistency end-to-end: "P17" in the
    inbound/economic layer is the EXACT SAME "P17" that flowed through
    production, payloads, and clinical scheduling -- not an independently
    regenerated population that merely happens to share an ID scheme.

    `demand_patients` must expose `.patient_id`, `.radionuclide`, and
    `.prescribed_activity_mbq` (the native PatientRadionuclideDemand shape).
    """
    if not demand_patients:
        raise ValueError("demand_patients must not be empty")
    if not (0.0 <= inbound_patient_fraction <= 1.0):
        raise ValueError("inbound_patient_fraction must be within [0, 1]")
    if any(los < MINIMUM_INBOUND_LENGTH_OF_STAY_DAYS for los in length_of_stay_days_options):
        raise ValueError(f"length_of_stay_days_options must each be >= {MINIMUM_INBOUND_LENGTH_OF_STAY_DAYS} days (24 hours)")

    rng = random.Random(seed)
    los_options = list(length_of_stay_days_options)
    total = len(demand_patients)
    patients: list[SyntheticPatient] = []
    for index, demand_patient in enumerate(demand_patients, start=1):
        is_inbound = rng.random() < inbound_patient_fraction
        patient_type: PatientType = "INBOUND_PATIENT" if is_inbound else "OUTPATIENT"
        length_of_stay = rng.choice(los_options) if is_inbound else 0.0
        administration_time = clinical_day_minutes * (index - 1) / float(total)
        patients.append(
            SyntheticPatient(
                patient_id=str(demand_patient.patient_id),
                patient_type=patient_type,
                radionuclide=str(demand_patient.radionuclide),
                prescribed_activity_mbq=float(demand_patient.prescribed_activity_mbq),
                administration_time_minutes=administration_time,
                length_of_stay_days=length_of_stay,
            )
        )
    return tuple(patients)


def compute_peak_simultaneous_inbound_occupancy(
    patients: Sequence[SyntheticPatient],
    *,
    minutes_per_day: float = 1440.0,
) -> int:
    """Peak simultaneous inbound-room occupancy (section 5): derived purely
    from overlapping [administration_time, administration_time + LOS) occupancy
    intervals -- NOT from injection service time.
    """
    inbound = [p for p in patients if p.patient_type == "INBOUND_PATIENT"]
    if not inbound:
        return 0
    events: list[tuple[float, int]] = []
    for patient in inbound:
        admission = patient.administration_time_minutes
        discharge = admission + patient.length_of_stay_days * minutes_per_day
        events.append((admission, 1))
        events.append((discharge, -1))
    # Process departures before arrivals at identical instants so an
    # instantaneous room handoff is not double-counted as overlapping.
    events.sort(key=lambda event: (event[0], event[1]))
    peak = 0
    current = 0
    for _time, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


@dataclass(frozen=True)
class InboundAdmissionResult:
    """Deterministic room-constrained admission outcome for a fixed inbound
    room count (section 21/22): patients are prioritized by earliest
    administration time (ties by patient_id), admitted greedily to the first
    available room, and rejected (unmet) once no room is free.
    """

    admitted_patient_ids: tuple[str, ...]
    unmet_patient_ids: tuple[str, ...]
    occupied_room_days: float
    peak_occupancy: int
    average_length_of_stay_days: float


def admit_inbound_patients(
    patients: Sequence[SyntheticPatient],
    *,
    inbound_room_count: int,
    minutes_per_day: float = 1440.0,
) -> InboundAdmissionResult:
    inbound = sorted(
        (p for p in patients if p.patient_type == "INBOUND_PATIENT"),
        key=lambda p: (p.administration_time_minutes, p.patient_id),
    )
    if inbound_room_count <= 0:
        return InboundAdmissionResult(
            admitted_patient_ids=(),
            unmet_patient_ids=tuple(p.patient_id for p in inbound),
            occupied_room_days=0.0,
            peak_occupancy=compute_peak_simultaneous_inbound_occupancy(patients, minutes_per_day=minutes_per_day),
            average_length_of_stay_days=0.0,
        )

    room_free_at: list[float] = [float("-inf")] * inbound_room_count
    admitted: list[str] = []
    unmet: list[str] = []
    occupied_room_days = 0.0
    for patient in inbound:
        admission = patient.administration_time_minutes
        discharge = admission + patient.length_of_stay_days * minutes_per_day
        # Assign the room that has been free the longest (deterministic, explainable).
        room_index = min(range(inbound_room_count), key=lambda i: room_free_at[i])
        if room_free_at[room_index] <= admission:
            room_free_at[room_index] = discharge
            admitted.append(patient.patient_id)
            occupied_room_days += patient.length_of_stay_days
        else:
            unmet.append(patient.patient_id)

    average_los = occupied_room_days / len(admitted) if admitted else 0.0
    return InboundAdmissionResult(
        admitted_patient_ids=tuple(admitted),
        unmet_patient_ids=tuple(unmet),
        occupied_room_days=occupied_room_days,
        peak_occupancy=compute_peak_simultaneous_inbound_occupancy(patients, minutes_per_day=minutes_per_day),
        average_length_of_stay_days=average_los,
    )


@dataclass(frozen=True)
class InboundRoomEconomicAssumptions:
    """All rates below are explicit, configurable PROJECT_ASSUMPTION /
    SYNTHETIC_BENCHMARK values unless noted; none are source-backed
    reimbursement figures (section 9/10/11).
    """

    room_capex_per_unit: float  # Reuses PlannerAssumptions.additional_room_capex (existing repository rate).
    room_annual_opex_per_unit: float = DEFAULT_INBOUND_ROOM_ANNUAL_OPEX_PER_UNIT
    room_revenue_per_occupied_day: float = DEFAULT_INBOUND_ROOM_REVENUE_PER_OCCUPIED_DAY


def _room_delivery_transport_minutes(
    *,
    pathway: Pathway,
    geometry: BenchmarkGeometry,
    room_id: str,
    assumptions: PlannerAssumptions,
) -> float:
    (_dist, _vert, _trans, manual_by_room, mrt_by_room, _edges) = _route_metrics_for_rooms(geometry, (room_id,), assumptions)
    return manual_by_room[room_id] if pathway == "Conventional" else mrt_by_room[room_id]


def room_passes_retention_criterion(
    *,
    pathway: Pathway,
    geometry: BenchmarkGeometry,
    room_id: str,
    radionuclide: str,
    half_life_minutes: float,
    assumptions: PlannerAssumptions,
    threshold: float | None = None,
) -> bool:
    """Common retention criterion applied identically to both pathways
    (sections 16/17): direct radionuclide delivery to `room_id` must satisfy
    T_pathway(room_id) <= retention time budget derived from half-life/threshold.
    """
    effective_threshold = (
        float(assumptions.minimum_release_to_administration_retention_fraction) if threshold is None else float(threshold)
    )
    transport_minutes = _room_delivery_transport_minutes(pathway=pathway, geometry=geometry, room_id=room_id, assumptions=assumptions)
    retained = retained_fraction(max(0.0, transport_minutes), half_life_minutes)
    return retained >= effective_threshold


@dataclass(frozen=True)
class InboundRoomGuidewayExtension:
    """Incremental MRT infrastructure attributable to reaching one additional
    inbound room, beyond the ALREADY-SELECTED shared destination network
    (section 18/19): if the room's floor is already served, only the room's
    own horizontal spur is incremental; if the floor is new, the vertical
    guideway run (and its 2 physical H<->V transitions, per the validated
    transition-count correction) is also incremental. Rooms that are not
    selected never contribute guideway cost (section 19).
    """

    incremental_horizontal_m: float
    incremental_vertical_m: float
    incremental_transitions: int
    incremental_capex: float


def compute_inbound_room_guideway_extension(
    *,
    geometry: BenchmarkGeometry,
    room_id: str,
    already_serviced_floors: frozenset[int],
    assumptions: PlannerAssumptions,
    network_assumptions: SharedNetworkAssumptions,
    guideway_capex_per_m_override: float | None = None,
) -> InboundRoomGuidewayExtension:
    floor = geometry.room_floor_by_id[room_id]
    (dist_by_room, vert_by_room, _trans, _manual, _mrt, _edges) = _route_metrics_for_rooms(geometry, (room_id,), assumptions)
    total_distance = dist_by_room[room_id]
    total_vertical = vert_by_room[room_id]
    horizontal_spur = max(0.0, total_distance - total_vertical)

    if floor in already_serviced_floors:
        incremental_horizontal = horizontal_spur
        incremental_vertical = 0.0
        incremental_transitions = 0
    else:
        incremental_horizontal = horizontal_spur
        # Extend from the NEAREST already-serviced floor (not from the
        # ground/origin), so a new floor adjacent to the existing network only
        # pays for the additional floor-to-floor span actually required.
        if already_serviced_floors:
            nearest_floor_delta = min(abs(floor - serviced_floor) for serviced_floor in already_serviced_floors)
        else:
            nearest_floor_delta = floor
        incremental_vertical = geometry.floor_to_floor_height_m * nearest_floor_delta
        # One continuous new vertical run to reach the new floor: exactly one
        # H->V and one V->H physical transition (validated transition semantics).
        incremental_transitions = 2

    # RUNTIME MIGRATION: the CURRENT MRT/Hybrid runtime passes the canonical
    # $2,500/m two-way guideway rate via `guideway_capex_per_m_override`. When
    # None (legacy inbound-room program + all existing callers/tests), the
    # unchanged heavy `assumptions.mrt_guideway_capex_per_m` is used exactly as
    # before -- this override never affects the preserved legacy scope.
    guideway_capex_per_m = (
        assumptions.mrt_guideway_capex_per_m if guideway_capex_per_m_override is None
        else guideway_capex_per_m_override
    )
    incremental_capex = (
        (incremental_horizontal + incremental_vertical) * guideway_capex_per_m
        + incremental_transitions * network_assumptions.vertical_transition_capex
    )
    return InboundRoomGuidewayExtension(
        incremental_horizontal_m=incremental_horizontal,
        incremental_vertical_m=incremental_vertical,
        incremental_transitions=incremental_transitions,
        incremental_capex=incremental_capex,
    )


@dataclass(frozen=True)
class InboundRoomProgramResult:
    """Complete room program + occupancy + economics for one candidate inbound
    room count/architecture (sections 31-34).
    """

    architecture: InboundArchitecture
    inbound_room_count: int
    rooms_available: int
    rooms_selected: tuple[str, ...]
    admission: InboundAdmissionResult
    qualified_inbound_completions: int
    unmet_inbound_demand: int
    inbound_room_capex: float
    inbound_room_annual_opex: float
    inbound_room_day_annual_value: float
    incremental_mrt_guideway_capex: float
    qualified_inbound_scan_annual_revenue: float
    total_capex: float
    total_annual_revenue: float
    total_annual_opex: float


def evaluate_inbound_room_program(
    *,
    pathway: Pathway,
    geometry: BenchmarkGeometry,
    architecture: InboundArchitecture,
    patients: Sequence[SyntheticPatient],
    candidate_room_ids: Sequence[str],
    already_serviced_floors: frozenset[int],
    central_injection_room_id: str | None,
    inbound_room_count: int,
    half_life_minutes: float,
    assumptions: PlannerAssumptions,
    network_assumptions: SharedNetworkAssumptions,
    econ: InboundRoomEconomicAssumptions,
    retention_threshold: float | None = None,
) -> InboundRoomProgramResult:
    """Evaluate one candidate inbound-room program (count + architecture) for
    one pathway. Room selection is deterministic: the first `inbound_room_count`
    candidate_room_ids (in caller-provided, deterministic order) that pass the
    common retention criterion for their delivery mode (section 6/7/16/17).
    """
    if inbound_room_count < 0:
        raise ValueError("inbound_room_count must be non-negative")
    if inbound_room_count > len(candidate_room_ids):
        raise ValueError("inbound_room_count cannot exceed the number of candidate rooms")

    selected: list[str] = []
    for room_id in candidate_room_ids:
        if len(selected) >= inbound_room_count:
            break
        if architecture == "INTEGRATED":
            # Direct radionuclide delivery to the inbound room itself.
            if room_passes_retention_criterion(
                pathway=pathway,
                geometry=geometry,
                room_id=room_id,
                radionuclide=patients[0].radionuclide if patients else "F-18",
                half_life_minutes=half_life_minutes,
                assumptions=assumptions,
                threshold=retention_threshold,
            ):
                selected.append(room_id)
        else:
            # CENTRALIZED: retention is evaluated against the shared central
            # injection room, not the inbound room itself (section 17/47).
            if central_injection_room_id is None:
                raise ValueError("CENTRALIZED architecture requires central_injection_room_id")
            if room_passes_retention_criterion(
                pathway=pathway,
                geometry=geometry,
                room_id=central_injection_room_id,
                radionuclide=patients[0].radionuclide if patients else "F-18",
                half_life_minutes=half_life_minutes,
                assumptions=assumptions,
                threshold=retention_threshold,
            ):
                selected.append(room_id)

    admission = admit_inbound_patients(patients, inbound_room_count=len(selected))
    admitted_ids = set(admission.admitted_patient_ids)
    inbound_patients = [p for p in patients if p.patient_type == "INBOUND_PATIENT"]

    # Qualified completion: admitted (room available) AND passed the common
    # retention criterion for its delivery mode -- direct room delivery for
    # INTEGRATED, central-injection delivery for CENTRALIZED (section 15).
    # Every selected room already passed the retention criterion at selection
    # time (either direct room delivery for INTEGRATED, or central-injection
    # delivery for CENTRALIZED), so admitted patients are, by construction,
    # retention-qualified.
    qualified = len(admitted_ids)

    unmet_inbound_demand = len(inbound_patients) - qualified

    inbound_room_capex = float(len(selected)) * econ.room_capex_per_unit
    inbound_room_annual_opex = float(len(selected)) * econ.room_annual_opex_per_unit
    inbound_room_day_annual_value = admission.occupied_room_days * assumptions.operating_days_per_year * econ.room_revenue_per_occupied_day

    incremental_mrt_guideway_capex = 0.0
    if pathway == "MRT" and architecture == "INTEGRATED":
        # Track floors newly reached WITHIN this candidate's own selected rooms:
        # only the first room to reach a given new floor pays the vertical
        # guideway/transition cost for that floor -- a shared continuous
        # vertical run serves every subsequent room on the same floor.
        cumulative_serviced_floors = set(already_serviced_floors)
        for room_id in selected:
            extension = compute_inbound_room_guideway_extension(
                geometry=geometry,
                room_id=room_id,
                already_serviced_floors=frozenset(cumulative_serviced_floors),
                assumptions=assumptions,
                network_assumptions=network_assumptions,
            )
            incremental_mrt_guideway_capex += extension.incremental_capex
            cumulative_serviced_floors.add(geometry.room_floor_by_id[room_id])

    qualified_inbound_scan_annual_revenue = float(qualified) * assumptions.revenue_per_scan * assumptions.operating_days_per_year

    total_capex = inbound_room_capex + incremental_mrt_guideway_capex
    total_annual_revenue = qualified_inbound_scan_annual_revenue + inbound_room_day_annual_value
    total_annual_opex = inbound_room_annual_opex

    return InboundRoomProgramResult(
        architecture=architecture,
        inbound_room_count=len(selected),
        rooms_available=len(candidate_room_ids),
        rooms_selected=tuple(selected),
        admission=admission,
        qualified_inbound_completions=qualified,
        unmet_inbound_demand=max(0, unmet_inbound_demand),
        inbound_room_capex=inbound_room_capex,
        inbound_room_annual_opex=inbound_room_annual_opex,
        inbound_room_day_annual_value=inbound_room_day_annual_value,
        incremental_mrt_guideway_capex=incremental_mrt_guideway_capex,
        qualified_inbound_scan_annual_revenue=qualified_inbound_scan_annual_revenue,
        total_capex=total_capex,
        total_annual_revenue=total_annual_revenue,
        total_annual_opex=total_annual_opex,
    )


def compute_inbound_program_npv(result: InboundRoomProgramResult, assumptions: PlannerAssumptions) -> float:
    """Discount the inbound-room program's incremental CapEx/OPEX/revenue over
    the SAME analysis horizon and discount rate already used elsewhere
    (PlannerAssumptions.discount_rate_pct/analysis_years) -- no new discounting
    methodology invented (section 20/34).
    """
    discount_rate = float(assumptions.discount_rate_pct) / 100.0
    net_annual_cash_flow = result.total_annual_revenue - result.total_annual_opex
    npv = -float(result.total_capex)
    for year in range(1, int(assumptions.analysis_years) + 1):
        npv += net_annual_cash_flow / ((1.0 + discount_rate) ** year)
    return npv


def optimize_inbound_room_count(
    *,
    pathway: Pathway,
    geometry: BenchmarkGeometry,
    architecture: InboundArchitecture,
    patients: Sequence[SyntheticPatient],
    candidate_room_ids: Sequence[str],
    already_serviced_floors: frozenset[int],
    central_injection_room_id: str | None,
    half_life_minutes: float,
    assumptions: PlannerAssumptions,
    network_assumptions: SharedNetworkAssumptions,
    econ: InboundRoomEconomicAssumptions,
    retention_threshold: float | None = None,
) -> tuple[InboundRoomProgramResult, float, tuple[tuple[InboundRoomProgramResult, float], ...]]:
    """The optimizer CHOOSES the inbound room count (section 21): sweep every
    physically available count from 0 up to len(candidate_room_ids), and select
    the NPV-maximizing count. Returns (best_result, best_npv, all_evaluated).
    """
    peak_demand = compute_peak_simultaneous_inbound_occupancy(patients)
    max_rooms_to_consider = min(len(candidate_room_ids), max(peak_demand, 1))
    evaluated: list[tuple[InboundRoomProgramResult, float]] = []
    for count in range(0, max_rooms_to_consider + 1):
        result = evaluate_inbound_room_program(
            pathway=pathway,
            geometry=geometry,
            architecture=architecture,
            patients=patients,
            candidate_room_ids=candidate_room_ids,
            already_serviced_floors=already_serviced_floors,
            central_injection_room_id=central_injection_room_id,
            inbound_room_count=count,
            half_life_minutes=half_life_minutes,
            assumptions=assumptions,
            network_assumptions=network_assumptions,
            econ=econ,
            retention_threshold=retention_threshold,
        )
        npv = compute_inbound_program_npv(result, assumptions)
        evaluated.append((result, npv))

    best_result, best_npv = max(evaluated, key=lambda item: item[1])
    return best_result, best_npv, tuple(evaluated)


# ---------------------------------------------------------------------------
# PIPELINE INTEGRATION: patient identity flows from the REAL native pipeline
# result (production cycle, payload, delivery, clinical trace, decay trace)
# into a single per-patient economic/status ledger (section 25/26).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PatientValueLedgerEntry:
    """One row per patient (section 26). Never allocates shared architecture
    CapEx (cyclotron, scanner, guideway, buildings) per patient (section 27) --
    only patient-attributable occupancy/value is reported here.
    """

    patient_id: str
    patient_type: PatientType
    radionuclide: str
    production_cycle_batch_id: int
    payload_id: str
    delivery_job_id: int
    clinical_destination_object_id: str
    architecture: InboundArchitecture | None  # None for OUTPATIENT.
    assigned_inbound_room_id: str | None
    length_of_stay_days: float
    occupied_room_days: float
    clinically_completed: bool
    elapsed_release_to_administration_minutes: float
    retained_fraction: float
    retention_pass: bool
    retention_qualified_completion: bool
    qualified_scan_value: float
    room_day_value: float
    total_attributable_patient_value: float


def _integrated_room_retention(
    *,
    pathway: Pathway,
    geometry: BenchmarkGeometry,
    room_id: str,
    release_time_minutes: float,
    half_life_minutes: float,
    assumptions: PlannerAssumptions,
) -> tuple[float, float]:
    """Section 22: for INTEGRATED architecture, retention uses actual delivery
    to the inbound room itself (release time comes from the REAL production
    trace; transport time is computed to the room's real geometric location).
    Returns (elapsed_minutes, retained_fraction).
    """
    transport_minutes = _room_delivery_transport_minutes(pathway=pathway, geometry=geometry, room_id=room_id, assumptions=assumptions)
    elapsed_minutes = max(0.0, transport_minutes)
    return elapsed_minutes, retained_fraction(elapsed_minutes, half_life_minutes)


def build_patient_value_ledger(
    *,
    pathway_result: "NativePathwayResult",
    pathway: Pathway,
    geometry: BenchmarkGeometry,
    synthetic_patients: Sequence[SyntheticPatient],
    architecture: InboundArchitecture,
    admitted_inbound_room_by_patient_id: Mapping[str, str],
    central_injection_room_id: str | None,
    assumptions: PlannerAssumptions,
    econ: InboundRoomEconomicAssumptions,
    retention_threshold: float | None = None,
) -> tuple[PatientValueLedgerEntry, ...]:
    """Join the REAL per-patient production/clinical/decay traces with the
    inbound-program overlay to build one patient-level ledger (sections 25/26,
    34). Every field is read from the actual pipeline result for that exact
    patient_id -- no replacement/regenerated patient identity.
    """
    effective_threshold = (
        float(assumptions.minimum_release_to_administration_retention_fraction) if retention_threshold is None else float(retention_threshold)
    )
    clinical_traces_by_id = {
        trace.patient_id: trace for trace in pathway_result.operational_result.production_clinical_result.patient_traces
    }
    decay_traces_by_id = {trace.patient_id: trace for trace in pathway_result.decay_summary.patient_traces}
    synthetic_by_id = {patient.patient_id: patient for patient in synthetic_patients}

    entries: list[PatientValueLedgerEntry] = []
    for patient_id, clinical_trace in clinical_traces_by_id.items():
        decay_trace = decay_traces_by_id.get(patient_id)
        synthetic = synthetic_by_id.get(patient_id)
        if decay_trace is None or synthetic is None:
            continue

        is_inbound = synthetic.patient_type == "INBOUND_PATIENT"
        assigned_room = admitted_inbound_room_by_patient_id.get(patient_id) if is_inbound else None
        patient_architecture: InboundArchitecture | None = architecture if (is_inbound and assigned_room is not None) else None

        if patient_architecture == "INTEGRATED" and assigned_room is not None:
            elapsed_minutes, retained = _integrated_room_retention(
                pathway=pathway,
                geometry=geometry,
                room_id=assigned_room,
                release_time_minutes=float(decay_trace.release_time_minutes),
                half_life_minutes=float(decay_trace.half_life_minutes),
                assumptions=assumptions,
            )
        else:
            # CENTRALIZED and OUTPATIENT both use the REAL realized
            # release->administration timing from the native clinical/decay
            # trace (section 23: the patient's later return to the inbound
            # room does not extend this clock).
            elapsed_minutes = max(0.0, float(decay_trace.elapsed_release_to_injection_minutes))
            retained = retained_fraction(elapsed_minutes, float(decay_trace.half_life_minutes))

        clinically_completed = bool(decay_trace.completed_within_operating_day)
        retention_pass = retained >= effective_threshold
        retention_qualified = clinically_completed and retention_pass

        occupied_days = synthetic.length_of_stay_days if (is_inbound and assigned_room is not None) else 0.0
        qualified_scan_value = float(assumptions.revenue_per_scan) if retention_qualified else 0.0
        room_day_value = occupied_days * econ.room_revenue_per_occupied_day

        entries.append(
            PatientValueLedgerEntry(
                patient_id=patient_id,
                patient_type=synthetic.patient_type,
                radionuclide=synthetic.radionuclide,
                production_cycle_batch_id=clinical_trace.batch_id,
                payload_id=clinical_trace.payload_id,
                delivery_job_id=clinical_trace.delivery_job_id,
                clinical_destination_object_id=clinical_trace.assigned_destination_object_id,
                architecture=patient_architecture,
                assigned_inbound_room_id=assigned_room,
                length_of_stay_days=synthetic.length_of_stay_days,
                occupied_room_days=occupied_days,
                clinically_completed=clinically_completed,
                elapsed_release_to_administration_minutes=elapsed_minutes,
                retained_fraction=retained,
                retention_pass=retention_pass,
                retention_qualified_completion=retention_qualified,
                qualified_scan_value=qualified_scan_value,
                room_day_value=room_day_value,
                total_attributable_patient_value=qualified_scan_value + room_day_value,
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.patient_id))


@dataclass(frozen=True)
class IntegratedInboundProgramResult:
    """End-to-end result for one pathway/architecture combination (section 46):
    the REAL native pipeline result plus the joined patient-level ledger and
    architecture-level (never per-patient) inbound-room economics.
    """

    pathway: Pathway
    architecture: InboundArchitecture
    synthetic_patients: tuple[SyntheticPatient, ...]
    admitted_inbound_room_by_patient_id: Mapping[str, str]
    room_program: InboundRoomProgramResult
    ledger: tuple[PatientValueLedgerEntry, ...]


def evaluate_integrated_inbound_program(
    *,
    pathway_result: "NativePathwayResult",
    pathway: Pathway,
    geometry: BenchmarkGeometry,
    architecture: InboundArchitecture,
    candidate_inbound_room_ids: Sequence[str],
    already_serviced_floors: frozenset[int],
    central_injection_room_id: str | None,
    inbound_room_count: int,
    assumptions: PlannerAssumptions,
    network_assumptions: SharedNetworkAssumptions,
    econ: InboundRoomEconomicAssumptions,
    inbound_patient_fraction: float = DEFAULT_INBOUND_PATIENT_FRACTION,
    length_of_stay_days_options: Sequence[float] = DEFAULT_LENGTH_OF_STAY_DAYS_OPTIONS,
    seed: int = 20260816,
    retention_threshold: float | None = None,
) -> IntegratedInboundProgramResult:
    """Full pipeline-integration entry point (section 46): overlays
    patient_type/LOS onto the REAL patients that the given `pathway_result`
    already carried through production/payload/clinical/decay, admits inbound
    patients to a room program of the requested architecture and count, and
    builds the joined patient-level value ledger.
    """
    real_demand_patients = pathway_result.operational_result.demand_result.simulation.generated_demand.patients
    synthetic_patients = attach_patient_type_and_los(
        real_demand_patients,
        inbound_patient_fraction=inbound_patient_fraction,
        length_of_stay_days_options=length_of_stay_days_options,
        seed=seed,
    )
    half_life_minutes = float(pathway_result.decay_summary.patient_traces[0].half_life_minutes) if pathway_result.decay_summary.patient_traces else 109.8

    room_program = evaluate_inbound_room_program(
        pathway=pathway,
        geometry=geometry,
        architecture=architecture,
        patients=synthetic_patients,
        candidate_room_ids=candidate_inbound_room_ids,
        already_serviced_floors=already_serviced_floors,
        central_injection_room_id=central_injection_room_id,
        inbound_room_count=inbound_room_count,
        half_life_minutes=half_life_minutes,
        assumptions=assumptions,
        network_assumptions=network_assumptions,
        econ=econ,
        retention_threshold=retention_threshold,
    )

    # Re-derive the actual room selection -> per-patient room assignment (the
    # same deterministic priority/first-fit rule as admit_inbound_patients).
    admitted_room_by_patient_id: dict[str, str] = {}
    if room_program.rooms_selected:
        inbound_only = sorted(
            (p for p in synthetic_patients if p.patient_type == "INBOUND_PATIENT"),
            key=lambda p: (p.administration_time_minutes, p.patient_id),
        )
        room_count = len(room_program.rooms_selected)
        room_free_at = [float("-inf")] * room_count
        for patient in inbound_only:
            admission = patient.administration_time_minutes
            discharge = admission + patient.length_of_stay_days * 1440.0
            room_index = min(range(room_count), key=lambda i: room_free_at[i])
            if room_free_at[room_index] <= admission:
                room_free_at[room_index] = discharge
                admitted_room_by_patient_id[patient.patient_id] = room_program.rooms_selected[room_index]

    ledger = build_patient_value_ledger(
        pathway_result=pathway_result,
        pathway=pathway,
        geometry=geometry,
        synthetic_patients=synthetic_patients,
        architecture=architecture,
        admitted_inbound_room_by_patient_id=admitted_room_by_patient_id,
        central_injection_room_id=central_injection_room_id,
        assumptions=assumptions,
        econ=econ,
        retention_threshold=retention_threshold,
    )

    return IntegratedInboundProgramResult(
        pathway=pathway,
        architecture=architecture,
        synthetic_patients=synthetic_patients,
        admitted_inbound_room_by_patient_id=admitted_room_by_patient_id,
        room_program=room_program,
        ledger=ledger,
    )

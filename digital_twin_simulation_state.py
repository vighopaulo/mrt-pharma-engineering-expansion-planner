"""Digital-Twin Simulation-State Foundation (Phase 2B.1, sections 1-3, 11-23,
30).

GOVERNANCE: reuses -- never duplicates -- `operational_day_orchestrator.py`'s
existing event-driven, one-simulation-clock authority (`DayTrajectorySet`,
`DayEventJournalEntry`, `state_at_time()`). That authority ALREADY:
  - represents MRT + Manual/AGV/PTS missions under ONE `sim_start`/`sim_end`
    clock (never separate sequential simulations per technology, sections 1/3);
  - computes state analytically from start/end timestamps via
    `state_at_time(t)`, never by stepping through frames (section 2);
  - is horizon-independent -- `state_at_time(t)` costs O(missions), not
    O(elapsed_simulated_time), so a one-year horizon costs the same per-query
    as a one-day horizon (section 23) -- proven by test, not promised.

This module adds ONLY the entities that authority does not yet resolve at a
point in time:
  - patient CLINICAL state at time t (derived from EXISTING patient-trace
    timestamps -- injection/uptake/scan start-end -- never a new schedule);
  - cyclotron/generator PRODUCTION state at time t (genuinely new, since no
    existing authority exposes simultaneous production state; built from
    EXISTING per-batch timing fields already on `ProductionClinicalPatientTrace`);
  - the PHYSICAL_ASSET_ID vs SIMULATION_MISSION_INSTANCE_ID distinction
    (section 21/12).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

TransportRuntimeState = Literal["IDLE", "WAITING", "LOADING", "IN_TRANSIT", "UNLOADING", "RETURNING", "COMPLETE", "UNAVAILABLE"]
PatientClinicalState = Literal[
    "IN_ASSIGNED_ROOM", "MOVING_TO_INJECTION", "IN_INJECTION", "MOVING_TO_UPTAKE", "IN_UPTAKE",
    "MOVING_TO_SCANNER", "IN_SCANNER", "RETURNING", "COMPLETE",
]
CyclotronProductionState = Literal["IDLE", "PRODUCING", "AWAITING_RELEASE", "RELEASED", "UNAVAILABLE"]

# Section 21: which technologies carry genuine per-unit PHYSICAL_ASSET_ID vs
# only a SIMULATION_MISSION_INSTANCE_ID (fabricated fresh per mission, never
# implying a persistent physical vehicle) -- reuses Phase 1B's
# TRANSPORT_RESOURCE_IDENTITY_MODEL finding, restated here for the runtime
# layer's own use.
PHYSICAL_ASSET_ID_AVAILABLE: tuple[str, ...] = ("MRT_CARRIER",)
SIMULATION_MISSION_INSTANCE_ID_ONLY: tuple[str, ...] = ("AGV_AMR", "ORDINARY_PTS", "DEDICATED_RP_PTS", "MANUAL")


@dataclass(frozen=True)
class TransportRuntimeRecord:
    """Section 12: minimum runtime mission/resource state. `physical_asset_id`
    is None for technologies with no persistent per-unit identity (AGV/PTS/
    RP-PTS/Manual porter) -- never fabricated; `runtime_id` (a
    SIMULATION_MISSION_INSTANCE_ID) always exists, scoped to ONE mission."""

    runtime_id: str
    technology: Literal["MRT", "AGV_AMR", "ORDINARY_PTS", "DEDICATED_RP_PTS", "MANUAL"]
    mission_id: str
    physical_asset_id: str | None
    payload_id: str | None
    route_id: str | None
    current_segment_id: str | None
    departure_time_minutes: float
    arrival_time_minutes: float
    state: TransportRuntimeState


def resolve_transport_runtime_state(record: TransportRuntimeRecord, *, at_time_minutes: float) -> TransportRuntimeState:
    """Event-driven, not frame-driven (section 2): a pure function of
    (record, t) -- costs the same whether t is 1 minute or 1 year into the
    horizon (section 23)."""
    if at_time_minutes < record.departure_time_minutes:
        return "WAITING"
    if record.departure_time_minutes <= at_time_minutes < record.arrival_time_minutes:
        return "IN_TRANSIT"
    return "COMPLETE"


# ---------------------------------------------------------------------------
# Patient clinical state (sections 11, 29) -- derived from EXISTING trace
# timestamps only, never a new schedule.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PatientClinicalStateAtTime:
    patient_id: str
    at_time_minutes: float
    state: PatientClinicalState


def resolve_patient_clinical_state_at_time(trace: object, *, at_time_minutes: float) -> PatientClinicalStateAtTime:
    """`trace`: an existing `ProductionClinicalPatientTrace`/`HybridPatientTrace`-
    shaped object (duck-typed) already carrying `injection_start_minutes`/
    `injection_end_minutes`/`uptake_start_minutes`/`uptake_end_minutes`/
    `scan_start_minutes`/`scan_end_minutes`. Never recomputes the schedule --
    only classifies which phase `at_time_minutes` falls into."""
    t = at_time_minutes
    injection_start = getattr(trace, "injection_start_minutes", getattr(trace, "injection_start", None))
    injection_end = getattr(trace, "injection_end_minutes", getattr(trace, "injection_end", None))
    uptake_start = getattr(trace, "uptake_start_minutes", getattr(trace, "uptake_start", None))
    uptake_end = getattr(trace, "uptake_end_minutes", getattr(trace, "uptake_end", None))
    scan_start = getattr(trace, "scan_start_minutes", getattr(trace, "scan_start", None))
    scan_end = getattr(trace, "scan_end_minutes", getattr(trace, "scan_end", None))

    if t < injection_start:
        state: PatientClinicalState = "IN_ASSIGNED_ROOM"
    elif injection_start <= t < injection_end:
        state = "IN_INJECTION"
    elif injection_end <= t < uptake_start:
        state = "MOVING_TO_UPTAKE"
    elif uptake_start <= t < uptake_end:
        state = "IN_UPTAKE"
    elif uptake_end <= t < scan_start:
        state = "MOVING_TO_SCANNER"
    elif scan_start <= t < scan_end:
        state = "IN_SCANNER"
    else:
        state = "COMPLETE"
    return PatientClinicalStateAtTime(patient_id=trace.patient_id, at_time_minutes=t, state=state)


# ---------------------------------------------------------------------------
# Cyclotron / generator production state (sections 15, 26-27) -- built from
# EXISTING per-batch timing fields already on ProductionClinicalPatientTrace;
# generator state is kept in its OWN record, never forced into cyclotron
# semantics (section 15/26).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CyclotronRuntimeStateAtTime:
    cyclotron_id: str
    at_time_minutes: float
    active_batch_id: str | None
    radionuclide: str | None
    production_start_minutes: float | None
    eob_minutes: float | None
    release_status: Literal["NOT_YET_RELEASED", "RELEASED"] | None
    next_scheduled_batch_id: str | None
    state: CyclotronProductionState


def resolve_cyclotron_runtime_state(
    cyclotron_id: str, *, at_time_minutes: float, traces: Sequence[object],
) -> CyclotronRuntimeStateAtTime:
    """`traces`: existing `ProductionClinicalPatientTrace` records (duck-typed)
    already carrying `assigned_cyclotron_id`/`batch_id`/`radionuclide`/
    `production_window_start_time_minutes`/`production_window_end_time_minutes`/
    `batch_release_time_minutes`. Groups by `batch_id` (a cyclotron produces ONE
    batch per production window; `max_simultaneous_production_streams`,
    section 16/27, is an existing equipment-capability constraint this
    function reads, never recomputes). Calling this once per cyclotron_id
    under the SAME `at_time_minutes` supports simultaneous multi-cyclotron
    state (section 1/26) without a separate simulation per cyclotron."""
    own_traces = [t for t in traces if getattr(t, "assigned_cyclotron_id", None) == cyclotron_id]
    batches: dict[str, dict] = {}
    for t in own_traces:
        batch_id = str(t.batch_id)
        batches.setdefault(batch_id, {
            "radionuclide": t.radionuclide, "start": t.production_window_start_time_minutes,
            "end": t.production_window_end_time_minutes, "release": t.batch_release_time_minutes,
        })

    active = next((bid for bid, b in batches.items() if b["start"] <= at_time_minutes < b["end"]), None)
    awaiting_release = next((bid for bid, b in batches.items() if b["end"] <= at_time_minutes < b["release"]), None)
    upcoming = sorted((b for b in batches.values() if b["start"] > at_time_minutes), key=lambda b: b["start"])
    next_batch_id = next((bid for bid, b in batches.items() if b is upcoming[0]), None) if upcoming else None

    if active is not None:
        b = batches[active]
        return CyclotronRuntimeStateAtTime(
            cyclotron_id=cyclotron_id, at_time_minutes=at_time_minutes, active_batch_id=active, radionuclide=b["radionuclide"],
            production_start_minutes=b["start"], eob_minutes=b["end"], release_status="NOT_YET_RELEASED",
            next_scheduled_batch_id=next_batch_id, state="PRODUCING",
        )
    if awaiting_release is not None:
        b = batches[awaiting_release]
        return CyclotronRuntimeStateAtTime(
            cyclotron_id=cyclotron_id, at_time_minutes=at_time_minutes, active_batch_id=awaiting_release, radionuclide=b["radionuclide"],
            production_start_minutes=b["start"], eob_minutes=b["end"], release_status="NOT_YET_RELEASED",
            next_scheduled_batch_id=next_batch_id, state="AWAITING_RELEASE",
        )
    return CyclotronRuntimeStateAtTime(
        cyclotron_id=cyclotron_id, at_time_minutes=at_time_minutes, active_batch_id=None, radionuclide=None,
        production_start_minutes=None, eob_minutes=None, release_status=None, next_scheduled_batch_id=next_batch_id, state="IDLE",
    )


@dataclass(frozen=True)
class GeneratorRuntimeStateAtTime:
    """Kept structurally SEPARATE from `CyclotronRuntimeStateAtTime` (section
    15/26): a generator's supply model is elution-based
    (`oncology_pet_spect_scenario.PreparationBatch`/`GeneratorAsset`), never a
    production-window model -- forcing it into cyclotron semantics would
    misrepresent its physics."""

    generator_id: str
    at_time_minutes: float
    active_preparation_batch_id: str | None
    elution_datetime_minutes: float | None
    state: Literal["IDLE", "ELUTED_AWAITING_USE", "DEPLETED"]


def resolve_generator_runtime_state(
    generator_id: str, *, at_time_minutes: float, elution_time_minutes: float | None, preparation_batch_id: str | None,
    depletion_time_minutes: float | None = None,
) -> GeneratorRuntimeStateAtTime:
    if elution_time_minutes is None or at_time_minutes < elution_time_minutes:
        return GeneratorRuntimeStateAtTime(
            generator_id=generator_id, at_time_minutes=at_time_minutes, active_preparation_batch_id=None,
            elution_datetime_minutes=elution_time_minutes, state="IDLE",
        )
    if depletion_time_minutes is not None and at_time_minutes >= depletion_time_minutes:
        return GeneratorRuntimeStateAtTime(
            generator_id=generator_id, at_time_minutes=at_time_minutes, active_preparation_batch_id=preparation_batch_id,
            elution_datetime_minutes=elution_time_minutes, state="DEPLETED",
        )
    return GeneratorRuntimeStateAtTime(
        generator_id=generator_id, at_time_minutes=at_time_minutes, active_preparation_batch_id=preparation_batch_id,
        elution_datetime_minutes=elution_time_minutes, state="ELUTED_AWAITING_USE",
    )


# ---------------------------------------------------------------------------
# One-clock mixed-mode concurrency query (sections 1, 3, 18-19)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DigitalTwinStateAtTime:
    """Section 1/18-19: ONE snapshot, ONE `at_time_minutes` clock, covering
    every entity kind simultaneously -- never a separate per-technology
    snapshot/simulation."""

    at_time_minutes: float
    transport_states: tuple[tuple[str, TransportRuntimeState], ...]  # (runtime_id, state)
    patient_states: tuple[PatientClinicalStateAtTime, ...]
    cyclotron_states: tuple[CyclotronRuntimeStateAtTime, ...]


def digital_twin_state_at_time(
    *, at_time_minutes: float, transport_records: Sequence[TransportRuntimeRecord] = (),
    patient_traces: Sequence[object] = (), cyclotron_ids: Sequence[str] = (), production_traces: Sequence[object] = (),
) -> DigitalTwinStateAtTime:
    """Section 3/19: mixed-mode is first-class -- `transport_records` may
    freely mix MRT/AGV/ORDINARY_PTS/DEDICATED_RP_PTS/MANUAL technologies
    under this ONE call; no per-technology branch changes the clock."""
    transport_states = tuple((r.runtime_id, resolve_transport_runtime_state(r, at_time_minutes=at_time_minutes)) for r in transport_records)
    patient_states = tuple(resolve_patient_clinical_state_at_time(t, at_time_minutes=at_time_minutes) for t in patient_traces)
    cyclotron_states = tuple(
        resolve_cyclotron_runtime_state(cid, at_time_minutes=at_time_minutes, traces=production_traces) for cid in cyclotron_ids
    )
    return DigitalTwinStateAtTime(
        at_time_minutes=at_time_minutes, transport_states=transport_states, patient_states=patient_states, cyclotron_states=cyclotron_states,
    )

"""Intraday General-Logistics Demand Scheduling Correction.

DEFECT (correction sections 3-4, 19): `general_oncology_logistics.
generate_daily_logistics_demand` (UNCHANGED by this module) assigns every
demand a `release_datetime` of exactly midnight, concentrating an entire
day's missions at one instant and inflating peak-concurrency-derived porter
FTE/OPEX. This module is a SEPARATE, ADDITIVE correction layer: it consumes
`LogisticsDemand` tuples and returns a NEW tuple with corrected
`release_datetime`/`required_by_datetime` values -- the `LogisticsDemand`/
`TransportLoad` dataclasses themselves are NOT redesigned (same fields, same
types); only the intraday VALUE of one existing field is recomputed.

STREAM-APPROPRIATE SEMANTICS (sections 20-24): never a uniform random smear.
CLEAN_LINEN/STERILE_CLEAN_SUPPLY use SCHEDULED_WAVE (deterministic delivery
waves); PHARMACY_INFUSION/SPECIMEN_BLOOD use MIXED (scheduled waves plus a
stochastic fraction); any URGENT/CRITICAL-priority demand (regardless of
stream) is always treated as time-critical and is never delayed to a wave
(section 23/28) -- it is placed via the stream's own stochastic window,
representing the real, unscheduled moment the clinical need arose.

SEEDED REPRODUCIBILITY (section 25): one seeded `random.Random`, demands
processed in a stable (demand_id-sorted) order -- same seed -> identical
release-time sequence; a different seed may vary the SCHEDULED_WAVE choice
and the MIXED/URGENT stochastic draws.

PATIENT CALENDAR ALIGNMENT (section 26, disclosed limitation): demand is
already day-aligned to the patient's actual admission/discharge window
(`general_oncology_logistics.generate_daily_logistics_demand`, unchanged).
Finer clock-time alignment to a specific scheduled clinical event is
NOT_CALIBRATED -- neither `OncologyPatientRecord` nor
`NuclearProcedureAssignment` carries a scheduled clock-time field, and this
module does not invent one.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Literal, Mapping

from general_oncology_logistics import LogisticsDemand, LogisticsPriority, LogisticsStream, TransportLoad

IntradayTimingClass = Literal["SCHEDULED_WAVE", "MIXED", "URGENT_STOCHASTIC"]

URGENT_PRIORITIES: frozenset[LogisticsPriority] = frozenset({"URGENT", "CRITICAL"})


@dataclass(frozen=True)
class StreamIntradayPolicy:
    stream: LogisticsStream
    timing_class: IntradayTimingClass
    wave_times: tuple[time, ...]
    stochastic_fraction: float
    """Section 22/23: for MIXED streams, the fraction of non-urgent demands
    dispatched at a stochastic (urgent/ad-hoc) time rather than a wave."""
    stochastic_window: tuple[time, time]
    provenance: str = "CONTROLLED_SCENARIO_ASSUMPTION"


DEFAULT_INTRADAY_POLICIES: Mapping[LogisticsStream, StreamIntradayPolicy] = {
    "CLEAN_LINEN": StreamIntradayPolicy(
        stream="CLEAN_LINEN", timing_class="SCHEDULED_WAVE", wave_times=(time(7, 0), time(15, 0)),
        stochastic_fraction=0.0, stochastic_window=(time(6, 0), time(21, 0)),
        provenance="CONTROLLED_SCENARIO_ASSUMPTION (morning primary + afternoon secondary linen replenishment wave, section 21)",
    ),
    "STERILE_CLEAN_SUPPLY": StreamIntradayPolicy(
        stream="STERILE_CLEAN_SUPPLY", timing_class="SCHEDULED_WAVE", wave_times=(time(6, 30), time(14, 30)),
        stochastic_fraction=0.1, stochastic_window=(time(6, 0), time(21, 0)),
        provenance="CONTROLLED_SCENARIO_ASSUMPTION (scheduled replenishment waves + occasional urgent replenishment, section 24)",
    ),
    "PHARMACY_INFUSION": StreamIntradayPolicy(
        stream="PHARMACY_INFUSION", timing_class="MIXED", wave_times=(time(8, 0), time(12, 0), time(18, 0)),
        stochastic_fraction=0.25, stochastic_window=(time(6, 0), time(22, 0)),
        provenance="CONTROLLED_SCENARIO_ASSUMPTION (scheduled medication/supply waves + urgent stochastic missions, section 22)",
    ),
    "SPECIMEN_BLOOD": StreamIntradayPolicy(
        stream="SPECIMEN_BLOOD", timing_class="MIXED", wave_times=(time(6, 0), time(10, 0), time(16, 0)),
        stochastic_fraction=0.4, stochastic_window=(time(6, 0), time(22, 0)),
        provenance="CONTROLLED_SCENARIO_ASSUMPTION (scheduled collection/transport periods + urgent/STAT events, section 23)",
    ),
}


def _random_time_within(rng: random.Random, window: tuple[time, time], day: date) -> datetime:
    start = datetime.combine(day, window[0])
    end = datetime.combine(day, window[1])
    span_seconds = max(0.0, (end - start).total_seconds())
    return start + timedelta(seconds=rng.random() * span_seconds)


def assign_intraday_release_datetime(
    *, day: date, priority: LogisticsPriority, policy: StreamIntradayPolicy, rng: random.Random,
) -> datetime:
    """Section 20-23: urgent priority is always authoritative and bypasses
    wave scheduling entirely -- never delayed merely to align with a wave."""
    if priority in URGENT_PRIORITIES:
        return _random_time_within(rng, policy.stochastic_window, day)
    if policy.timing_class == "SCHEDULED_WAVE":
        return datetime.combine(day, rng.choice(policy.wave_times))
    if policy.timing_class == "MIXED":
        if rng.random() < policy.stochastic_fraction:
            return _random_time_within(rng, policy.stochastic_window, day)
        return datetime.combine(day, rng.choice(policy.wave_times))
    raise ValueError(f"Unknown timing_class: {policy.timing_class}")


def apply_intraday_timing(
    demands: tuple[LogisticsDemand, ...], *, day: date, seed: int = 0,
    policies: Mapping[LogisticsStream, StreamIntradayPolicy] = DEFAULT_INTRADAY_POLICIES,
) -> tuple[LogisticsDemand, ...]:
    """Section 19/25/27: corrects the midnight-concentration artifact.
    Physical fields (quantity/unit/patient_id/stream/...) are untouched --
    only `release_datetime`/`required_by_datetime` are recomputed, preserving
    the original release-to-deadline OFFSET exactly (deadline authority,
    section 23, is never weakened)."""
    rng = random.Random(seed)
    corrected: list[LogisticsDemand] = []
    for demand in sorted(demands, key=lambda d: d.demand_id):
        policy = policies[demand.stream]
        new_release = assign_intraday_release_datetime(day=day, priority=demand.priority, policy=policy, rng=rng)
        if demand.required_by_datetime is not None:
            offset = demand.required_by_datetime - demand.release_datetime
            new_required = new_release + offset
        else:
            new_required = None
        corrected.append(replace(demand, release_datetime=new_release, required_by_datetime=new_required))
    return tuple(corrected)


def consolidate_demands_into_loads_with_window(
    *, demands: tuple[LogisticsDemand, ...], max_quantity_per_load: float,
    consolidation_window_minutes: float = 90.0, urgent_window_minutes: float = 0.0,
) -> tuple[TransportLoad, ...]:
    """Section 27-29: keeps demand-release time distinct from mission-
    departure time -- routine/scheduled demands may consolidate only within a
    bounded window (default 90 min); URGENT/CRITICAL demands use a near-zero
    window so they are never delayed merely to improve consolidation. A
    consolidated load's `release_datetime` is the MAX (latest) release among
    its member demands -- the load can only depart once every consolidated
    demand has actually arrived, never earlier. Physical quantity/patient
    conservation is identical to
    `general_oncology_logistics.consolidate_demands_into_loads` (unchanged);
    only the grouping/timing rule differs."""
    by_key: dict[tuple, list[LogisticsDemand]] = {}
    for d in demands:
        by_key.setdefault((d.stream, d.ward_id, d.priority), []).append(d)

    loads: list[TransportLoad] = []
    load_index = 0
    for (stream, ward_id, priority), group in by_key.items():
        window_minutes = urgent_window_minutes if priority in URGENT_PRIORITIES else consolidation_window_minutes
        sample = group[0]
        ward_label = f"WARD-{ward_id}" if ward_id else "LOCATION_NOT_CALIBRATED"
        origins = {d.origin for d in group}
        if len(origins) == 1:
            origin, destination = sample.origin, ward_label
        else:
            origin, destination = ward_label, sample.destination

        ordered = sorted(group, key=lambda d: d.release_datetime)
        current_patients: list[str] = []
        current_quantity = 0.0
        current_deadline: datetime | None = None
        current_release: datetime | None = None
        current_window_start: datetime | None = None

        def _flush() -> None:
            nonlocal load_index, current_patients, current_quantity, current_deadline, current_release, current_window_start
            if not current_patients:
                return
            load_index += 1
            loads.append(TransportLoad(
                load_id=f"LOAD-{stream}-{load_index:04d}", stream=stream, patient_ids=tuple(current_patients),
                origin=origin, destination=destination, quantity=current_quantity, unit=group[0].unit,
                payload_class=group[0].payload_class, release_datetime=current_release, priority=priority,
                required_by_datetime=current_deadline,
            ))
            current_patients, current_quantity, current_deadline = [], 0.0, None
            current_release, current_window_start = None, None

        for d in ordered:
            exceeds_window = (
                current_window_start is not None
                and (d.release_datetime - current_window_start).total_seconds() / 60.0 > window_minutes
            )
            if current_patients and (current_quantity + d.quantity > max_quantity_per_load or exceeds_window):
                _flush()
            if not current_patients:
                current_window_start = d.release_datetime
            current_patients.append(d.patient_id)
            current_quantity += d.quantity
            current_release = d.release_datetime if current_release is None else max(current_release, d.release_datetime)
            if d.required_by_datetime is not None:
                current_deadline = d.required_by_datetime if current_deadline is None else min(current_deadline, d.required_by_datetime)
        _flush()
    return tuple(loads)

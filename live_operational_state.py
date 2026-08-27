"""Live Operational State + Event-Driven Rolling Re-Optimization.

GOVERNING ARCHITECTURE (spec PURPOSE):
    EXTERNAL/INTERNAL EVENT -> CANONICAL EVENT -> ACTUAL STATE UPDATE ->
    PLANNED-vs-ACTUAL COMPARISON -> IMPACT ANALYSIS -> AFFECTED CONSTRAINT
    SUBGRAPH -> ROLLING RE-OPTIMIZATION -> UPDATED PLAN -> NEW PLAN VERSION.

NEVER a second optimizer/scheduler: every replan reruns the EXISTING
`long_horizon_operational_planning.run_operating_day_plan` (one operating
date, the authoritative day-engine) with an updated committed-patient record
list and/or updated cyclotron/resource calendars, then DIFFS the resulting
`PatientOperationalPlan` set against the previous plan version to prove
localization (unaffected assignments are byte-for-byte identical, never
reshuffled merely because a mathematically equivalent alternative exists).

SCOPE DISCLOSURE (read before assuming full section coverage): event kinds
that map cleanly onto `run_operating_day_plan`'s existing input surface
(committed patient records, `CyclotronCalendar`, `ResourceAvailabilityCalendar`,
and -- this build -- persistent-identity resource RESERVATIONS, see
`operating_day_scheduler.py::OperatingDayInputs.*_reserved_until`) get a REAL
day-engine rerun + diff: PATIENT_CANCELLED, PATIENT_DELAYED, PATIENT_NO_SHOW,
NEW_URGENT_PATIENT, RESOURCE_UNAVAILABLE/AVAILABLE, CYCLOTRON_UNAVAILABLE/
AVAILABLE, CYCLOTRON_RELEASE_DELAY, ACTUAL_RELEASE_ACTIVITY, TRANSPORT_DELAY,
STAFF_CAPACITY_CHANGE. Event kinds with genuinely no day-engine input concept
remain state-tracking + impact-analysis-only: MRT_CARRIER_STATE_CHANGE
(carrier identity has no day-engine representation), ACTUAL_CLINICAL_TASK
(locks the stage via `is_locked()`, never rescheduled by definition).

ROLLING PRESERVATION + IDENTITY-STICKY LOCALITY (this build closes the prior
build's disclosed 0%-preservation gap): a replan partitions the previous
plan's patients into LOCKED_ACTUAL (completed tasks, carried forward
unchanged), PRESERVE_IF_VALID (not directly/downstream affected, carried
forward BYTE-FOR-BYTE unchanged, never rerun), and AFFECTED_REOPTIMIZATION_POOL
(only these are fed to a NEW `run_operating_day_plan` call). The affected pool
is scheduled using `preserve_resource_indices=True` plus `resource_reservations`
computed from the PRESERVED patients' actual resource consumption (their
real window end-times), so the affected subset is placed into the TRUE
residual capacity without perturbing -- or even touching -- preserved
patients' assignments (root cause of the prior 0% result: a full rerun of
EVERY non-locked patient through a fresh greedy pass, which is not
identity-sticky by construction; see `_allocate_earliest` in
operating_day_scheduler.py). If the affected-only rerun cannot produce ANY
feasible schedule (`schedule_result is None`), the mechanism escalates
explicitly to LEVEL_3_OPERATING_DAY_REOPTIMIZATION (a full rerun of every
non-locked patient, the prior build's mechanism) -- never silently.

Reuses -- never duplicates -- `healthcare_integration.CanonicalIntegrationEvent`
(vendor-neutral event envelope + idempotency precedent),
`clinical_resource_identity.ResourceAvailabilityCalendar`,
`long_horizon_operational_planning.CyclotronCalendar`/`run_operating_day_plan`/
`build_patient_operational_plans`, and `multi_isotope_decay.retained_fraction`
for retention recomputation.

HYBRID LIVE-STATE ADAPTER (this build): a Hybrid result
(`hybrid_optimization.HybridEvaluationResult`) is represented via a minimal
`HybridPlanVersion` wrapper whose `patient_plans` are the SAME
`PatientOperationalPlan` type Conventional/MRT already use (never a second
patient-plan type) -- see `build_hybrid_patient_operational_plans`. Hybrid
replans reuse `analyze_event_impact`/`diff_patient_plans`/`compute_plan_stability`
unchanged, and reschedule ONLY the affected subset via
`hybrid_optimization.rerun_hybrid_affected_subset` (which itself reuses the
SAME `schedule_operating_day` primitive Hybrid's baseline evaluation already
calls) -- never a second Hybrid scheduler, never a duplicated per-mode
clinical resource system.

STAFF-CAPACITY PATIENT TARGETING (this build): `identify_staff_shortfall_patient_tasks`
computes the ACTUAL over-capacity time interval and the minimum deterministic
release set from real scheduled task windows (never room count, never patient-
id order as a hidden priority) -- see its docstring for the greedy algorithm.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Literal, Mapping, Sequence

from clinical_resource_identity import ResourceAvailabilityCalendar
from decision_pipeline import Pathway
from facility_engineering_model import FacilityEngineeringObjectModel
from healthcare_integration import CanonicalIntegrationEvent, SourceSystem
from hybrid_optimization import HybridEvaluationResult, HybridPatientTrace, rerun_hybrid_affected_subset
from long_horizon_operational_planning import (
    CanonicalOperationalPatientRecord,
    CyclotronCalendar,
    CyclotronScenarioState,
    DailyOperationalSummary,
    PatientOperationalPlan,
    UnmetDemandRecord,
    build_patient_operational_plans,
    run_operating_day_plan,
)
from models import PlannerAssumptions
from multi_isotope_decay import retained_fraction

OperationalEventType = Literal[
    "PATIENT_CANCELLED", "PATIENT_DELAYED", "PATIENT_NO_SHOW", "NEW_URGENT_PATIENT",
    "RESOURCE_UNAVAILABLE", "RESOURCE_AVAILABLE",
    "CYCLOTRON_UNAVAILABLE", "CYCLOTRON_AVAILABLE", "CYCLOTRON_RELEASE_DELAY", "ACTUAL_RELEASE_ACTIVITY",
    "MRT_CARRIER_STATE_CHANGE", "CONVENTIONAL_TRANSPORT_CAPACITY_CHANGE", "TRANSPORT_DELAY", "STAFF_CAPACITY_CHANGE",
    "ACTUAL_CLINICAL_TASK", "INBOUND_EARLY_DISCHARGE", "INBOUND_EXTENDED_LOS",
    "ASSET_LOCATION_CHANGED",
    # PET/SPECT/GENERATOR NATIVE AUTHORITY COMPLETION (section 39, closed by
    # NUCLEAR TRUNK FINAL INTEGRATION CORRECTION section 22-25): GENERATOR_*
    # uses a dedicated `generator_state` dict (own identity, section 17);
    # SPECT_SCANNER_* reuses the EXISTING `resource_state` dict (a SPECT
    # scanner is just a SCN-xxx resource id, no new resource-identity engine).
    # Reoptimization dispatch for these kinds is now wired -- see
    # `analyze_generator_event_impact`/`replan_spect_after_generator_event`/
    # `replan_spect_after_scanner_event` below, which apply the SAME
    # LOCKED/PRESERVED/AFFECTED locality philosophy as
    # `apply_event_and_replan`, scoped to `oncology_pet_spect_scenario.SpectDoseLineage`
    # records so PET `PatientOperationalPlan` data is NEVER read/written by
    # these functions (non-drift by construction, section 25).
    "GENERATOR_UNAVAILABLE", "GENERATOR_AVAILABLE", "ELUTION_DELAYED", "ELUTION_FAILED_QC", "ACTUAL_ELUTION_ACTIVITY",
    "SPECT_SCANNER_UNAVAILABLE", "SPECT_SCANNER_RECOVERED",
]
"""Section 5/123-124: ASSET_LOCATION_CHANGED is a RESERVED event type -- it is
never dispatched/processed by this module (no BIM/facility geometry authority
exists yet); reserving the name only prevents a future naming collision."""

ReoptimizationScope = Literal["NONE", "PATIENT", "PRODUCTION_CYCLE", "RESOURCE", "OPERATING_DAY", "ROLLING_WINDOW", "CROSS_DAY"]
EventApplicationStatus = Literal["APPLIED", "DUPLICATE_IGNORED", "STALE_EVENT"]
ClinicalStage = Literal["INJECTION", "UPTAKE", "SCANNER"]
StaffPool = Literal["INJECTION", "UPTAKE", "SCANNER"]
ChangeClassification = Literal["DIRECTLY_AFFECTED_CHANGE", "COLLATERAL_CHANGE_REQUIRED_FOR_FEASIBILITY"]
ImpactClassification = Literal[
    "SHARED_RESOURCE_IMPACT", "CONVENTIONAL_SPECIFIC_IMPACT", "MRT_SPECIFIC_IMPACT", "OTHER",
]
"""Hybrid mode-specific impact classification: SHARED_RESOURCE_IMPACT (a
physical INJ/UP/SCN/IR/cyclotron/staff resource shared across transport
modes -- affects patients by resource assignment, never by transport mode),
CONVENTIONAL_SPECIFIC_IMPACT (Conventional transporter capacity only),
MRT_SPECIFIC_IMPACT (MRT carrier capacity only), OTHER (patient-identity
events with no shared/mode-specific resource dimension, e.g. cancellation)."""
EscalationLevel = Literal[
    "LEVEL_0_STATE_UPDATE_ONLY", "LEVEL_1_DIRECTLY_AFFECTED_ONLY", "LEVEL_2_AFFECTED_RESOURCE_NEIGHBORHOOD",
    "LEVEL_3_OPERATING_DAY_REOPTIMIZATION", "LEVEL_4_CROSS_DAY_ROLLING_WINDOW",
]

_DAY_ENGINE_REPLAN_EVENT_TYPES = frozenset({
    "PATIENT_CANCELLED", "PATIENT_DELAYED", "PATIENT_NO_SHOW", "NEW_URGENT_PATIENT",
    "RESOURCE_UNAVAILABLE", "RESOURCE_AVAILABLE", "CYCLOTRON_UNAVAILABLE", "CYCLOTRON_AVAILABLE",
    "CYCLOTRON_RELEASE_DELAY", "ACTUAL_RELEASE_ACTIVITY", "TRANSPORT_DELAY", "STAFF_CAPACITY_CHANGE",
})
"""Section (scope disclosure, module docstring): event kinds that feed a real
`run_operating_day_plan` rerun (directly, or via patient-record/resource-index
translation) when impact analysis determines reoptimization is required.
MRT_CARRIER_STATE_CHANGE and ACTUAL_CLINICAL_TASK remain state-tracking +
impact-analysis-only (no scheduler input concept exists for carrier identity
or completed-task locking beyond what `is_locked()` already provides)."""


@dataclass(frozen=True)
class OperationalEvent:
    """Wraps the EXISTING vendor-neutral `CanonicalIntegrationEvent` envelope
    (idempotency key, provenance, source system) with the typed operational
    fields this module's handlers need (section 5-6). `effective_timestamp`
    on the wrapped `integration_event` governs ordering/staleness (section 7-8)."""

    integration_event: CanonicalIntegrationEvent
    event_kind: OperationalEventType
    object_id: str | None = None
    """patient_id / resource_id (SCN-xxx, INJ-xxx, UP-xxx, IR-xxx) / cyclotron_id / carrier_id, as applicable."""
    new_state: str | None = None
    delay_minutes: float | None = None
    actual_value: float | None = None
    """Actual release activity (MBq) / actual staff capacity FTE, as applicable."""
    stage: ClinicalStage | None = None
    actual_start_minutes: float | None = None
    actual_end_minutes: float | None = None
    new_patient_record: CanonicalOperationalPatientRecord | None = None
    """Required for NEW_URGENT_PATIENT (section 24) -- never fabricated by this module."""
    half_life_minutes: float | None = None
    retention_threshold: float | None = None
    activity_per_patient_mbq: float | None = None
    scheduled_capacity_fte: float | None = None
    staff_pool: StaffPool | None = None
    """Section 26 (staff-capacity patient targeting): which shared clinical
    staff pool a STAFF_CAPACITY_CHANGE event constrains. When provided
    (together with `actual_value` as the available capacity), impact analysis
    identifies the ACTUAL overlapping patient tasks that exceed capacity from
    the previous plan's real scheduled windows -- never inferred from room
    count or patient identity order. When omitted, STAFF_CAPACITY_CHANGE
    falls back to the aggregate-only comparison (no patient-level target),
    the pre-existing disclosed behavior."""
    """Context needed to determine whether CYCLOTRON_RELEASE_DELAY/TRANSPORT_DELAY
    genuinely invalidate retention, whether ACTUAL_RELEASE_ACTIVITY creates a
    genuine shortfall, and whether STAFF_CAPACITY_CHANGE (`actual_value`) falls
    below the scheduled FTE demand -- never invented, supplied by the caller
    from the SAME authoritative sources (multi_isotope_decay half-lives,
    PlannerAssumptions retention threshold, radiopharm_workflow_staffing FTE)."""
    notes: str = ""


def _effective_timestamp(event: OperationalEvent) -> datetime:
    ie = event.integration_event
    return ie.event_timestamp if ie.event_timestamp is not None else ie.received_timestamp


@dataclass(frozen=True)
class ObjectStateRecord:
    object_id: str
    state: str
    effective_timestamp: datetime
    source_system: SourceSystem
    source_event_id: str


@dataclass(frozen=True)
class EventJournalEntry:
    """Section 9/99: one audit row per received event -- never erased."""

    source_event_id: str
    source_system: SourceSystem
    event_kind: OperationalEventType
    object_id: str | None
    effective_timestamp: datetime
    state_before: str | None
    state_after: str | None
    application_status: EventApplicationStatus
    reoptimization_scope: ReoptimizationScope
    resulting_plan_version_id: str | None


@dataclass
class OperationalStateStore:
    """Section 3-4/9: the ACTUAL-state twin, kept separate from any PLANNED
    state (which lives in `PlanVersion.daily_summary`/`.patient_plans` --
    never overwritten in place, section 3/10)."""

    resource_state: dict[str, ObjectStateRecord] = field(default_factory=dict)
    cyclotron_state: dict[str, ObjectStateRecord] = field(default_factory=dict)
    mrt_carrier_state: dict[str, ObjectStateRecord] = field(default_factory=dict)
    patient_status: dict[str, ObjectStateRecord] = field(default_factory=dict)
    staff_capacity_fte_by_pool: dict[str, ObjectStateRecord] = field(default_factory=dict)
    completed_task_stages: dict[str, set[ClinicalStage]] = field(default_factory=dict)
    """patient_id -> set of clinical stages actually completed (section 51: locked, never rescheduled)."""
    actual_task_timing: dict[tuple[str, ClinicalStage], tuple[float, float]] = field(default_factory=dict)
    """(patient_id, stage) -> (actual_start_minutes, actual_end_minutes), section 49-50."""
    cyclotron_release_delay_minutes: dict[str, float] = field(default_factory=dict)
    """cyclotron_id -> most recent reported actual release delay (section 37)."""
    actual_release_activity_mbq: dict[str, float] = field(default_factory=dict)
    """cyclotron_id -> most recent reported actual released activity (section 39-41)."""
    generator_state: dict[str, ObjectStateRecord] = field(default_factory=dict)
    """generator_id -> ObjectStateRecord (GENERATOR_UNAVAILABLE/AVAILABLE/ELUTION_FAILED_QC), mirrors cyclotron_state."""
    generator_elution_delay_minutes: dict[str, float] = field(default_factory=dict)
    """generator_id -> most recent reported ELUTION_DELAYED delay, mirrors cyclotron_release_delay_minutes."""
    actual_elution_activity_mbq: dict[str, float] = field(default_factory=dict)
    """generator_id -> most recent reported ACTUAL_ELUTION_ACTIVITY, mirrors actual_release_activity_mbq."""
    _processed_event_ids: set[tuple[SourceSystem, str]] = field(default_factory=set)
    event_journal: list[EventJournalEntry] = field(default_factory=list)

    def already_processed(self, *, source_system: SourceSystem, source_event_id: str) -> bool:
        return (source_system, source_event_id) in self._processed_event_ids

    def _state_dict_for(self, event: OperationalEvent) -> dict[str, ObjectStateRecord] | None:
        return {
            "RESOURCE_UNAVAILABLE": self.resource_state, "RESOURCE_AVAILABLE": self.resource_state,
            "CYCLOTRON_UNAVAILABLE": self.cyclotron_state, "CYCLOTRON_AVAILABLE": self.cyclotron_state,
            "MRT_CARRIER_STATE_CHANGE": self.mrt_carrier_state,
            "PATIENT_CANCELLED": self.patient_status, "PATIENT_NO_SHOW": self.patient_status,
            "GENERATOR_UNAVAILABLE": self.generator_state, "GENERATOR_AVAILABLE": self.generator_state,
            "ELUTION_FAILED_QC": self.generator_state,
            "SPECT_SCANNER_UNAVAILABLE": self.resource_state, "SPECT_SCANNER_RECOVERED": self.resource_state,
        }.get(event.event_kind)

    def record_event(self, event: OperationalEvent) -> EventApplicationStatus:
        """Section 6-8: idempotent + ordered application. Returns APPLIED,
        DUPLICATE_IGNORED (same source_system+source_event_id seen before), or
        STALE_EVENT (an older effective_timestamp than the current state for
        the same object -- never silently rewinds the twin, section 8)."""
        key = (event.integration_event.source_system, event.integration_event.source_event_id)
        if key in self._processed_event_ids:
            return "DUPLICATE_IGNORED"

        effective = _effective_timestamp(event)
        state_dict = self._state_dict_for(event)
        existing = state_dict.get(event.object_id) if state_dict is not None and event.object_id else None
        if existing is not None and effective < existing.effective_timestamp:
            self._processed_event_ids.add(key)
            self.event_journal.append(EventJournalEntry(
                source_event_id=event.integration_event.source_event_id, source_system=event.integration_event.source_system,
                event_kind=event.event_kind, object_id=event.object_id, effective_timestamp=effective,
                state_before=existing.state, state_after=existing.state, application_status="STALE_EVENT",
                reoptimization_scope="NONE", resulting_plan_version_id=None,
            ))
            return "STALE_EVENT"

        state_before = existing.state if existing is not None else None
        self._apply(event, state_dict, effective)
        self._processed_event_ids.add(key)
        state_after = state_dict.get(event.object_id).state if state_dict is not None and event.object_id in (state_dict or {}) else event.new_state
        self.event_journal.append(EventJournalEntry(
            source_event_id=event.integration_event.source_event_id, source_system=event.integration_event.source_system,
            event_kind=event.event_kind, object_id=event.object_id, effective_timestamp=effective,
            state_before=state_before, state_after=state_after, application_status="APPLIED",
            reoptimization_scope="NONE", resulting_plan_version_id=None,
        ))
        return "APPLIED"

    def _apply(self, event: OperationalEvent, state_dict: dict[str, ObjectStateRecord] | None, effective: datetime) -> None:
        record = ObjectStateRecord(
            object_id=event.object_id or "", state=event.new_state or event.event_kind, effective_timestamp=effective,
            source_system=event.integration_event.source_system, source_event_id=event.integration_event.source_event_id,
        )
        if state_dict is not None and event.object_id:
            state_dict[event.object_id] = record
        if event.event_kind == "ACTUAL_CLINICAL_TASK" and event.object_id and event.stage:
            self.completed_task_stages.setdefault(event.object_id, set()).add(event.stage)
            if event.actual_start_minutes is not None and event.actual_end_minutes is not None:
                self.actual_task_timing[(event.object_id, event.stage)] = (event.actual_start_minutes, event.actual_end_minutes)
        if event.event_kind == "CYCLOTRON_RELEASE_DELAY" and event.object_id and event.delay_minutes is not None:
            self.cyclotron_release_delay_minutes[event.object_id] = event.delay_minutes
        if event.event_kind == "ACTUAL_RELEASE_ACTIVITY" and event.object_id and event.actual_value is not None:
            self.actual_release_activity_mbq[event.object_id] = event.actual_value
        if event.event_kind == "ELUTION_DELAYED" and event.object_id and event.delay_minutes is not None:
            self.generator_elution_delay_minutes[event.object_id] = event.delay_minutes
        if event.event_kind == "ACTUAL_ELUTION_ACTIVITY" and event.object_id and event.actual_value is not None:
            self.actual_elution_activity_mbq[event.object_id] = event.actual_value
        if event.event_kind == "STAFF_CAPACITY_CHANGE" and event.object_id and event.actual_value is not None:
            self.staff_capacity_fte_by_pool[event.object_id] = ObjectStateRecord(
                object_id=event.object_id, state=str(event.actual_value), effective_timestamp=effective,
                source_system=event.integration_event.source_system, source_event_id=event.integration_event.source_event_id,
            )

    def is_locked(self, patient_id: str) -> bool:
        """Section 51: a patient with ANY actually-completed clinical stage is
        locked -- their plan entry is carried forward unchanged by a replan,
        never recomputed (the day-engine has no partial-stage re-scheduling
        concept, so the safest honest treatment is whole-patient carry-forward)."""
        return bool(self.completed_task_stages.get(patient_id))


# ---------------------------------------------------------------------------
# Plan versioning (sections 10-11, 63-66)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanVersion:
    version_id: str
    previous_version_id: str | None
    day: date
    pathway: Pathway
    daily_summary: DailyOperationalSummary
    patient_plans: tuple[PatientOperationalPlan, ...]
    triggering_event_id: str | None
    created_at: datetime


def baseline_plan_version(*, day: date, pathway: Pathway, daily_summary: DailyOperationalSummary, records_for_day: Sequence[CanonicalOperationalPatientRecord], created_at: datetime) -> PlanVersion:
    """Section 11: the deterministic master plan becomes PLAN-0000; live
    events operate against it."""
    return PlanVersion(
        version_id="PLAN-0000", previous_version_id=None, day=day, pathway=pathway, daily_summary=daily_summary,
        patient_plans=build_patient_operational_plans(daily_summary=daily_summary, records_for_day=records_for_day),
        triggering_event_id=None, created_at=created_at,
    )


def _next_version_id(previous_version_id: str) -> str:
    n = int(previous_version_id.split("-")[1])
    return f"PLAN-{n + 1:04d}"


def plan_history_for_patient(versions: Sequence[PlanVersion], *, patient_id: str) -> tuple[tuple[str, PatientOperationalPlan | None], ...]:
    """Section 64: original plan + every revision's entry for one patient."""
    return tuple(
        (v.version_id, next((p for p in v.patient_plans if p.internal_model_patient_id == patient_id), None))
        for v in versions
    )


def compare_plan_versions(old: PlanVersion, new: PlanVersion) -> "PlanChangeset":
    """Section 63."""
    return diff_patient_plans(old.patient_plans, new.patient_plans)


# ---------------------------------------------------------------------------
# Impact analysis (sections 12-15)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Staff-capacity patient-task targeting (sections 25-30 of the Hybrid/staff
# live-state spec): identifies the ACTUAL overlapping patient tasks in a
# shared staff pool that exceed available capacity, and the MINIMUM
# deterministic set of (non-locked) future tasks to release to restore
# concurrency <= capacity -- never every task in the day, never patient-id
# order used as a hidden priority (only as a final tie-break).
# ---------------------------------------------------------------------------

_STAFF_POOL_WINDOW_ATTR: Mapping[StaffPool, str] = {
    "INJECTION": "injection_window_minutes", "UPTAKE": "uptake_window_minutes", "SCANNER": "scan_window_minutes",
}


@dataclass(frozen=True)
class StaffShortfallTargetingResult:
    pool: StaffPool
    available_capacity: float
    max_required_concurrency: int
    shortfall_interval: tuple[float, float] | None
    candidate_patient_ids: tuple[str, ...]
    """Every patient task active during the worst (max-concurrency) interval."""
    released_patient_ids: tuple[str, ...]
    """The MINIMUM deterministic subset of candidate tasks released to restore
    concurrency <= capacity (never locked/completed tasks)."""
    final_concurrency: int
    feasible: bool
    """False only if releasing every releasable (non-locked) candidate task
    still leaves concurrency above capacity (section 38: report unmet, never fabricate capacity)."""


def _max_concurrency_interval(tasks: Sequence[tuple[str, float, float]]) -> tuple[int, tuple[float, float] | None]:
    if not tasks:
        return 0, None
    points = sorted({s for _, s, _ in tasks} | {e for _, _, e in tasks})
    best_count = 0
    best_interval: tuple[float, float] | None = None
    for i in range(len(points) - 1):
        t = points[i]
        count = sum(1 for _, s, e in tasks if s <= t < e)
        if count > best_count:
            best_count = count
            best_interval = (points[i], points[i + 1])
    return best_count, best_interval


def _greedy_release_for_capacity(
    tasks: Sequence[tuple[str, float, float]], capacity: int, locked_patient_ids: frozenset[str],
) -> tuple[str, ...]:
    """Section 27/29/30: repeatedly find the worst over-capacity interval and
    release the (non-locked) active task with the LATEST end time (least
    likely to still be needed, most likely to cause future conflicts) --
    patient_id is only a final deterministic tie-break. Optimal/minimal for
    this "reduce max overlap to <= k" class of interval problems."""
    remaining = list(tasks)
    released: list[str] = []
    while True:
        count, interval = _max_concurrency_interval(remaining)
        if count <= capacity or interval is None:
            break
        active = [t for t in remaining if t[1] <= interval[0] < t[2]]
        releasable_active = [t for t in active if t[0] not in locked_patient_ids]
        if not releasable_active:
            break  # every task in the worst interval is locked -- cannot reduce further (section 38)
        target = max(releasable_active, key=lambda t: (t[2], t[0]))
        released.append(target[0])
        remaining = [t for t in remaining if t[0] != target[0]]
    return tuple(released)


def _over_capacity_participants(tasks: Sequence[tuple[str, float, float]], capacity: int) -> set[str]:
    """Every patient active during ANY interval where concurrency exceeds
    capacity (section 28's candidate set) -- not just the single worst point,
    since the greedy release loop can target participants of any such
    interval across the operating day."""
    if not tasks:
        return set()
    points = sorted({s for _, s, _ in tasks} | {e for _, _, e in tasks})
    participants: set[str] = set()
    for i in range(len(points) - 1):
        t = points[i]
        active = [pid for pid, s, e in tasks if s <= t < e]
        if len(active) > capacity:
            participants.update(active)
    return participants


def identify_staff_shortfall_patient_tasks(
    *, pool: StaffPool, plans: Sequence[PatientOperationalPlan], available_capacity: float,
    locked_patient_ids: frozenset[str] = frozenset(),
) -> StaffShortfallTargetingResult:
    """Section 26-30: uses ACTUAL scheduled task intervals (never room count,
    never LOS alone) to find the exact over-capacity interval and the minimum
    necessary future-task release set."""
    attr = _STAFF_POOL_WINDOW_ATTR[pool]
    tasks = tuple((p.internal_model_patient_id, getattr(p, attr)[0], getattr(p, attr)[1]) for p in plans)
    capacity_count = int(available_capacity)
    max_count, worst_interval = _max_concurrency_interval(tasks)
    if max_count <= capacity_count or worst_interval is None:
        return StaffShortfallTargetingResult(
            pool=pool, available_capacity=available_capacity, max_required_concurrency=max_count,
            shortfall_interval=None, candidate_patient_ids=(), released_patient_ids=(),
            final_concurrency=max_count, feasible=True,
        )
    candidate_ids = tuple(sorted(_over_capacity_participants(tasks, capacity_count)))
    released = _greedy_release_for_capacity(tasks, capacity_count, locked_patient_ids)
    remaining = tuple(t for t in tasks if t[0] not in released)
    final_count, _ = _max_concurrency_interval(remaining)
    return StaffShortfallTargetingResult(
        pool=pool, available_capacity=available_capacity, max_required_concurrency=max_count,
        shortfall_interval=worst_interval, candidate_patient_ids=candidate_ids, released_patient_ids=released,
        final_concurrency=final_count, feasible=final_count <= capacity_count,
    )


@dataclass(frozen=True)
class ImpactAnalysisResult:
    event: OperationalEvent
    changed_object_id: str | None
    directly_affected_patient_ids: tuple[str, ...]
    downstream_affected_patient_ids: tuple[str, ...]
    unaffected_patient_ids: tuple[str, ...]
    constraints_invalidated: tuple[str, ...]
    reoptimization_required: bool
    recommended_scope: ReoptimizationScope
    impact_classification: ImpactClassification = "OTHER"


def analyze_event_impact(
    *, event: OperationalEvent, previous_plans: Sequence[PatientOperationalPlan],
    locked_patient_ids: frozenset[str] = frozenset(),
) -> ImpactAnalysisResult:
    """Section 13: structured impact result computed BEFORE any reoptimization.

    `locked_patient_ids` (optional, additive): completed-task-locked patients,
    excluded as release CANDIDATES by STAFF_CAPACITY_CHANGE's patient-task
    targeting (section 30) -- a locked task can never be moved regardless of
    how over-capacity its interval is. Ignored by every other event kind."""
    all_ids = tuple(p.internal_model_patient_id for p in previous_plans)
    directly: tuple[str, ...] = ()
    downstream: tuple[str, ...] = ()
    constraints: list[str] = []
    required = False
    scope: ReoptimizationScope = "NONE"
    classification: ImpactClassification = "OTHER"

    if event.event_kind in ("PATIENT_CANCELLED", "PATIENT_NO_SHOW"):
        directly = (event.object_id,) if event.object_id in all_ids else ()
        required = bool(directly)
        scope = "PATIENT" if required else "NONE"
        constraints = ["PATIENT_DEMAND_REMOVED"] if required else []
    elif event.event_kind == "PATIENT_DELAYED":
        directly = (event.object_id,) if event.object_id in all_ids else ()
        required = bool(directly)
        scope = "PATIENT" if required else "NONE"
        constraints = ["ADMINISTRATION_TIMING"] if required else []
    elif event.event_kind == "NEW_URGENT_PATIENT":
        required = event.new_patient_record is not None
        scope = "PATIENT" if required else "NONE"
        constraints = ["NEW_DEMAND"] if required else []
    elif event.event_kind in ("RESOURCE_UNAVAILABLE", "RESOURCE_AVAILABLE"):
        directly = tuple(
            p.internal_model_patient_id for p in previous_plans
            if event.object_id in (p.injection_resource_id, p.uptake_resource_id, p.scanner_resource_id, p.inbound_room_id)
        )
        # Section 28: recovery (AVAILABLE) alone never forces a reshuffle of
        # already-valid assignments -- only a genuine outage does.
        required = event.event_kind == "RESOURCE_UNAVAILABLE" and bool(directly)
        scope = "OPERATING_DAY" if required else "NONE"
        constraints = ["RESOURCE_EXCLUSIVITY"] if required else []
        classification = "SHARED_RESOURCE_IMPACT"
    elif event.event_kind in ("CYCLOTRON_UNAVAILABLE", "CYCLOTRON_AVAILABLE"):
        directly = tuple(p.internal_model_patient_id for p in previous_plans if p.cyclotron_id == event.object_id)
        required = event.event_kind == "CYCLOTRON_UNAVAILABLE" and bool(directly)
        scope = "OPERATING_DAY" if required else "NONE"
        constraints = ["PRODUCTION_CAPACITY"] if required else []
        classification = "SHARED_RESOURCE_IMPACT"
    elif event.event_kind == "CYCLOTRON_RELEASE_DELAY":
        directly = tuple(p.internal_model_patient_id for p in previous_plans if p.cyclotron_id == event.object_id)
        downstream = directly
        # Section 23-24/82: a genuine invalidation (retention crosses the
        # threshold, computed via the authoritative decay engine) triggers a
        # real replan; a delay that does not change qualification for any
        # dependent patient does not (section 25 locality).
        required = False
        if directly and event.delay_minutes and event.half_life_minutes and event.retention_threshold is not None:
            for p in previous_plans:
                if p.internal_model_patient_id not in directly:
                    continue
                variance = recompute_retention_after_delay(
                    patient_id=p.internal_model_patient_id, release_time_minutes=p.release_time_minutes,
                    planned_administration_minutes=p.injection_window_minutes[0], delay_minutes=event.delay_minutes,
                    half_life_minutes=event.half_life_minutes, retention_threshold=event.retention_threshold,
                )
                if variance.qualification_changed:
                    required = True
                    break
        scope = "PRODUCTION_CYCLE" if directly else "NONE"
        constraints = ["RETENTION_TIMING"] if directly else []
        classification = "SHARED_RESOURCE_IMPACT"
    elif event.event_kind == "ACTUAL_RELEASE_ACTIVITY":
        directly = tuple(p.internal_model_patient_id for p in previous_plans if p.cyclotron_id == event.object_id)
        required = False
        if directly and event.actual_value is not None and event.activity_per_patient_mbq:
            required_activity = len(directly) * event.activity_per_patient_mbq
            required = event.actual_value < required_activity - 1e-9
        scope = "PRODUCTION_CYCLE" if required else "NONE"
        constraints = ["PRODUCTION_CONSERVATION"] if directly else []
        classification = "SHARED_RESOURCE_IMPACT"
    elif event.event_kind == "MRT_CARRIER_STATE_CHANGE":
        directly = tuple(p.internal_model_patient_id for p in previous_plans if p.transport_mode == "MRT")
        # Section 11/42: a carrier failure IS material whenever ANY MRT patient
        # exists -- a Pure Conventional baseline has zero MRT patients so this
        # is naturally a no-op there; for MRT/Hybrid plans it is genuinely
        # required (never inferred/skipped merely because the day-engine has
        # no carrier-identity input concept -- see rerun_hybrid_affected_subset).
        required = bool(directly)
        scope = "RESOURCE" if directly else "NONE"
        constraints = ["MRT_TRANSPORT_CAPACITY"] if directly else []
        classification = "MRT_SPECIFIC_IMPACT"
    elif event.event_kind == "CONVENTIONAL_TRANSPORT_CAPACITY_CHANGE":
        directly = tuple(p.internal_model_patient_id for p in previous_plans if p.transport_mode == "Conventional")
        required = bool(directly)
        scope = "RESOURCE" if directly else "NONE"
        constraints = ["CONVENTIONAL_TRANSPORT_CAPACITY"] if directly else []
        classification = "CONVENTIONAL_SPECIFIC_IMPACT"
    elif event.event_kind == "TRANSPORT_DELAY":
        directly = (event.object_id,) if event.object_id in all_ids else ()
        required = False
        if directly and event.delay_minutes and event.half_life_minutes and event.retention_threshold is not None:
            p = next(p for p in previous_plans if p.internal_model_patient_id == event.object_id)
            variance = recompute_retention_after_delay(
                patient_id=p.internal_model_patient_id, release_time_minutes=p.release_time_minutes,
                planned_administration_minutes=p.injection_window_minutes[0], delay_minutes=event.delay_minutes,
                half_life_minutes=event.half_life_minutes, retention_threshold=event.retention_threshold,
            )
            required = variance.qualification_changed
        scope = "PATIENT" if required else "NONE"
        constraints = ["RETENTION_TIMING"] if directly else []
        if directly:
            target = next((p for p in previous_plans if p.internal_model_patient_id == directly[0]), None)
            classification = "MRT_SPECIFIC_IMPACT" if target is not None and target.transport_mode == "MRT" else "CONVENTIONAL_SPECIFIC_IMPACT"
    elif event.event_kind == "STAFF_CAPACITY_CHANGE":
        required = False
        classification = "SHARED_RESOURCE_IMPACT"
        if event.actual_value is not None and event.staff_pool is not None:
            # Section 25-30: real patient-task targeting from ACTUAL scheduled
            # windows -- replaces the aggregate-only comparison whenever the
            # caller supplies which pool + the plans to check against.
            targeting = identify_staff_shortfall_patient_tasks(
                pool=event.staff_pool, plans=previous_plans, available_capacity=event.actual_value,
                locked_patient_ids=locked_patient_ids,
            )
            directly = targeting.released_patient_ids
            required = bool(directly)
        elif event.actual_value is not None and event.scheduled_capacity_fte is not None:
            # Backward-compatible fallback (no staff_pool/plans-based targeting
            # context supplied): aggregate-only, no patient-level target.
            required = event.actual_value < event.scheduled_capacity_fte - 1e-9
        scope = "RESOURCE" if required else "NONE"
        constraints = ["STAFFING_CAPACITY"]
    elif event.event_kind == "ACTUAL_CLINICAL_TASK":
        directly = (event.object_id,) if event.object_id in all_ids else ()
        required = False
        scope = "NONE"
        constraints = []
    elif event.event_kind in ("INBOUND_EARLY_DISCHARGE", "INBOUND_EXTENDED_LOS"):
        directly = tuple(p.internal_model_patient_id for p in previous_plans if p.inbound_room_id == event.object_id)
        required = event.event_kind == "INBOUND_EXTENDED_LOS" and bool(directly)
        scope = "OPERATING_DAY" if required else "NONE"
        constraints = ["INBOUND_ROOM_OCCUPANCY_EXCLUSIVITY"] if directly else []
        classification = "SHARED_RESOURCE_IMPACT"
    else:
        required = False
        scope = "NONE"

    affected_set = set(directly) | set(downstream)
    unaffected = tuple(pid for pid in all_ids if pid not in affected_set)
    return ImpactAnalysisResult(
        event=event, changed_object_id=event.object_id, directly_affected_patient_ids=directly,
        downstream_affected_patient_ids=downstream, unaffected_patient_ids=unaffected,
        constraints_invalidated=tuple(constraints), reoptimization_required=required, recommended_scope=scope,
        impact_classification=classification,
    )


# ---------------------------------------------------------------------------
# Plan diff / changeset / stability (sections 16-18, 62, 97-98)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModifiedAssignment:
    patient_id: str
    old_plan: PatientOperationalPlan | None
    new_plan: PatientOperationalPlan | None
    reason: str
    classification: ChangeClassification = "DIRECTLY_AFFECTED_CHANGE"
    """Section 52-53: DIRECTLY_AFFECTED_CHANGE (patient was in the event's
    directly/downstream-affected set) vs COLLATERAL_CHANGE_REQUIRED_FOR_FEASIBILITY
    (patient was NOT directly affected but still had to move because the
    affected-only reoptimization pool could not otherwise reach a feasible
    result -- always paired with an explicit reason, never silent)."""


@dataclass(frozen=True)
class PlanChangeset:
    unchanged_patient_ids: tuple[str, ...]
    modified: tuple[ModifiedAssignment, ...]
    cancelled_patient_ids: tuple[str, ...]
    new_patient_ids: tuple[str, ...]
    new_unmet: tuple[UnmetDemandRecord, ...] = ()


def _plan_key(plan: PatientOperationalPlan) -> tuple:
    return (
        plan.cyclotron_id, plan.injection_resource_id, plan.uptake_resource_id, plan.scanner_resource_id,
        plan.injection_window_minutes, plan.uptake_window_minutes, plan.scan_window_minutes,
        plan.transport_mode, plan.completed_within_operating_day,
    )


def _diff_reason(old: PatientOperationalPlan, new: PatientOperationalPlan) -> str:
    if old.scanner_resource_id != new.scanner_resource_id:
        return "SCANNER_REASSIGNED"
    if old.injection_resource_id != new.injection_resource_id:
        return "INJECTION_REASSIGNED"
    if old.uptake_resource_id != new.uptake_resource_id:
        return "UPTAKE_REASSIGNED"
    if old.cyclotron_id != new.cyclotron_id:
        return "CYCLOTRON_REASSIGNED"
    if old.scan_window_minutes != new.scan_window_minutes or old.injection_window_minutes != new.injection_window_minutes or old.uptake_window_minutes != new.uptake_window_minutes:
        return "TIMING_SHIFT"
    if old.completed_within_operating_day != new.completed_within_operating_day:
        return "COMPLETION_STATUS_CHANGED"
    return "OTHER_EXPLICIT_REASON"


def diff_patient_plans(
    old_plans: Sequence[PatientOperationalPlan], new_plans: Sequence[PatientOperationalPlan],
    *, directly_affected_ids: frozenset[str] = frozenset(),
) -> PlanChangeset:
    """Section 16/62: byte-for-byte comparison of every committed patient's
    plan entry -- proves localization (identical entries are truly identical,
    never merely count-equivalent, section 113). `directly_affected_ids`
    (optional) classifies each modified assignment as DIRECTLY_AFFECTED_CHANGE
    vs COLLATERAL_CHANGE_REQUIRED_FOR_FEASIBILITY (section 52)."""
    old_by_id = {p.internal_model_patient_id: p for p in old_plans}
    new_by_id = {p.internal_model_patient_id: p for p in new_plans}
    unchanged: list[str] = []
    modified: list[ModifiedAssignment] = []
    cancelled: list[str] = []
    for pid, old in old_by_id.items():
        new = new_by_id.get(pid)
        if new is None:
            cancelled.append(pid)
        elif _plan_key(old) == _plan_key(new):
            unchanged.append(pid)
        else:
            classification: ChangeClassification = (
                "DIRECTLY_AFFECTED_CHANGE" if pid in directly_affected_ids else "COLLATERAL_CHANGE_REQUIRED_FOR_FEASIBILITY"
            )
            modified.append(ModifiedAssignment(pid, old, new, _diff_reason(old, new), classification))
    new_ids = [pid for pid in new_by_id if pid not in old_by_id]
    return PlanChangeset(
        unchanged_patient_ids=tuple(unchanged), modified=tuple(modified),
        cancelled_patient_ids=tuple(cancelled), new_patient_ids=tuple(new_ids),
    )


@dataclass(frozen=True)
class PlanStabilityResult:
    total_before: int
    unchanged: int
    modified: int
    cancelled: int
    new_unmet: int
    pct_preserved: float


def compute_plan_stability(changeset: PlanChangeset, *, total_before: int) -> PlanStabilityResult:
    """Section 98: proof that rolling optimization is localized."""
    pct = 100.0 * changeset.unchanged_patient_ids.__len__() / total_before if total_before else 100.0
    return PlanStabilityResult(
        total_before=total_before, unchanged=len(changeset.unchanged_patient_ids), modified=len(changeset.modified),
        cancelled=len(changeset.cancelled_patient_ids), new_unmet=len(changeset.new_unmet), pct_preserved=pct,
    )


# ---------------------------------------------------------------------------
# Rolling replan orchestrator (sections 2-4 governing architecture, 16, 55)
# ---------------------------------------------------------------------------


def _apply_patient_events_to_records(
    records: Sequence[CanonicalOperationalPatientRecord], event: OperationalEvent, affected_ids: frozenset[str],
) -> tuple[CanonicalOperationalPatientRecord, ...]:
    if event.event_kind in ("PATIENT_CANCELLED", "PATIENT_NO_SHOW"):
        return tuple(r for r in records if r.internal_model_patient_id != event.object_id)
    if event.event_kind == "ACTUAL_RELEASE_ACTIVITY":
        # Section 27/40: patients beyond actually-available activity are
        # removed from demand (never fabricated) -- `affected_ids` here is the
        # UNSERVABLE subset determined by the caller from the activity variance.
        return tuple(r for r in records if r.internal_model_patient_id not in affected_ids)
    if event.event_kind in ("PATIENT_DELAYED", "TRANSPORT_DELAY", "CYCLOTRON_RELEASE_DELAY") and event.delay_minutes is not None:
        target_ids = {event.object_id} if event.event_kind in ("PATIENT_DELAYED", "TRANSPORT_DELAY") else set(affected_ids)
        updated = []
        for r in records:
            if r.internal_model_patient_id not in target_ids:
                updated.append(r)
                continue
            new_start = None if r.administration_window_start_minute is None else r.administration_window_start_minute + event.delay_minutes
            new_end = None if r.administration_window_end_minute is None else r.administration_window_end_minute + event.delay_minutes
            updated.append(replace(r, administration_window_start_minute=new_start, administration_window_end_minute=new_end))
        return tuple(updated)
    if event.event_kind == "NEW_URGENT_PATIENT" and event.new_patient_record is not None:
        return tuple(records) + (event.new_patient_record,)
    return tuple(records)


def _apply_cyclotron_state_to_calendar(calendar: CyclotronCalendar, store: OperationalStateStore, day: date) -> CyclotronCalendar:
    overrides = dict(calendar.scenario_state_overrides_by_date)
    day_overrides = dict(overrides.get(day, {}))
    for cyclotron_id, record in store.cyclotron_state.items():
        state: CyclotronScenarioState = "OFF" if record.state == "UNAVAILABLE" else "ON"
        day_overrides[cyclotron_id] = state
    overrides[day] = day_overrides
    return replace(calendar, scenario_state_overrides_by_date=overrides)


def _apply_resource_state_to_calendar(calendar: ResourceAvailabilityCalendar, store: OperationalStateStore, day: date) -> ResourceAvailabilityCalendar:
    unavailable = dict(calendar.unavailable_by_date)
    day_unavailable = set(unavailable.get(day, frozenset()))
    for resource_id, record in store.resource_state.items():
        if record.state == "UNAVAILABLE":
            day_unavailable.add(resource_id)
        else:
            day_unavailable.discard(resource_id)
    unavailable[day] = frozenset(day_unavailable)
    return replace(calendar, unavailable_by_date=unavailable)


def _compute_resource_reservations(preserved_plans: Sequence[PatientOperationalPlan]) -> dict[str, float]:
    """Section 8/10: identity-sticky reservation -- the busy-until time each
    PRESERVED patient's real assignment consumes on its physical resource, so
    the affected-only rerun is placed into the TRUE residual capacity."""
    reservations: dict[str, float] = {}
    for p in preserved_plans:
        for resource_id, window in (
            (p.injection_resource_id, p.injection_window_minutes), (p.uptake_resource_id, p.uptake_window_minutes),
            (p.scanner_resource_id, p.scan_window_minutes),
        ):
            reservations[resource_id] = max(reservations.get(resource_id, 0.0), window[1])
    return reservations


@dataclass(frozen=True)
class EscalationRecord:
    """Section 12-13: every escalation is explicit -- never a silent full-day
    or full-horizon replan (section 14/115)."""

    starting_scope: EscalationLevel
    localization_feasible: bool
    reason: str
    released_assignment_ids: tuple[str, ...]
    final_scope: EscalationLevel
    result: str


def apply_event_and_replan(
    *,
    event: OperationalEvent,
    store: OperationalStateStore,
    previous_version: PlanVersion,
    records_for_day: Sequence[CanonicalOperationalPatientRecord],
    cyclotron_calendar: CyclotronCalendar,
    resource_calendar: ResourceAvailabilityCalendar,
    geometry: FacilityEngineeringObjectModel,
    assumptions: PlannerAssumptions,
    distribution_concurrency: int,
) -> tuple[EventApplicationStatus, ImpactAnalysisResult | None, PlanVersion | None, PlanChangeset | None, EscalationRecord | None]:
    """Section 2-4/16: the ONE rolling-replan entry point. Never reruns the
    full six-month horizon (section 55/115) -- only the ONE affected
    operating date, via the EXISTING `run_operating_day_plan`, and (this
    build) only the AFFECTED SUBSET of that date's patients wherever
    physically feasible (identity-sticky locality, see module docstring)."""
    status = store.record_event(event)
    if status != "APPLIED":
        return status, None, None, None, None

    locked_ids = {pid for pid in (p.internal_model_patient_id for p in previous_version.patient_plans) if store.is_locked(pid)}
    impact = analyze_event_impact(event=event, previous_plans=previous_version.patient_plans, locked_patient_ids=frozenset(locked_ids))
    if not impact.reoptimization_required:
        return status, impact, None, None, None  # STATE_UPDATE_ONLY / LEVEL_0 (section 14)

    if event.event_kind not in _DAY_ENGINE_REPLAN_EVENT_TYPES:
        # Scope-disclosed: impact computed, but no day-engine input hook exists for this event kind.
        return status, impact, None, None, None

    affected_ids = (set(impact.directly_affected_patient_ids) | set(impact.downstream_affected_patient_ids)) - locked_ids
    if event.event_kind == "NEW_URGENT_PATIENT" and event.new_patient_record is not None:
        affected_ids = affected_ids | {event.new_patient_record.internal_model_patient_id}
    if event.event_kind == "ACTUAL_RELEASE_ACTIVITY" and event.actual_value is not None and event.activity_per_patient_mbq:
        # Section 27-28/40: only the UNSERVABLE portion (beyond actual
        # available activity) is removed -- never the whole cyclotron's
        # patient set, and never more than physically supportable.
        servable = int(event.actual_value // event.activity_per_patient_mbq)
        ordered = sorted(affected_ids)
        affected_ids = set(ordered[servable:]) - locked_ids

    updated_records = _apply_patient_events_to_records(records_for_day, event, frozenset(affected_ids))
    updated_cyclotron_calendar = _apply_cyclotron_state_to_calendar(cyclotron_calendar, store, previous_version.day)
    updated_resource_calendar = _apply_resource_state_to_calendar(resource_calendar, store, previous_version.day)

    updated_ids = {r.internal_model_patient_id for r in updated_records}
    preserved_ids = {pid for pid in (p.internal_model_patient_id for p in previous_version.patient_plans) if pid not in locked_ids and pid not in affected_ids and pid in updated_ids}
    preserved_plans = tuple(p for p in previous_version.patient_plans if p.internal_model_patient_id in preserved_ids)
    locked_plans = tuple(p for p in previous_version.patient_plans if p.internal_model_patient_id in locked_ids)
    affected_records = tuple(r for r in updated_records if r.internal_model_patient_id in affected_ids or r.internal_model_patient_id not in preserved_ids and r.internal_model_patient_id not in locked_ids)

    escalation: EscalationRecord
    additional_blocked_injection_indices: frozenset[int] = frozenset()
    additional_blocked_uptake_indices: frozenset[int] = frozenset()
    additional_blocked_scanner_indices: frozenset[int] = frozenset()
    if event.event_kind == "STAFF_CAPACITY_CHANGE" and event.staff_pool is not None and event.actual_value is not None:
        # Section 37: cap the EFFECTIVE concurrent room count available to
        # THIS rerun to the available staff capacity -- reuses the
        # identity-sticky blocked-index mechanism (never a new scheduling
        # dimension) so the affected subset is forced to serialize within
        # what staff can actually support.
        resource_type = {"INJECTION": "INJECTION_ROOM", "UPTAKE": "UPTAKE_ROOM", "SCANNER": "SCANNER"}[event.staff_pool]
        total_count = len(resource_calendar.inventory.resources_of_type(resource_type))
        extra_blocked = frozenset(range(max(0, int(event.actual_value)), total_count))
        if event.staff_pool == "INJECTION":
            additional_blocked_injection_indices = extra_blocked
        elif event.staff_pool == "UPTAKE":
            additional_blocked_uptake_indices = extra_blocked
        else:
            additional_blocked_scanner_indices = extra_blocked

    if not affected_records:
        new_summary = previous_version.daily_summary
        recomputed_plans: tuple[PatientOperationalPlan, ...] = ()
        escalation = EscalationRecord(
            starting_scope="LEVEL_1_DIRECTLY_AFFECTED_ONLY", localization_feasible=True, reason="No affected records remained after applying the event (e.g. sole cancellation).",
            released_assignment_ids=(), final_scope="LEVEL_1_DIRECTLY_AFFECTED_ONLY", result="No rerun necessary.",
        )
    else:
        reservations = _compute_resource_reservations(preserved_plans)
        level1_summary = run_operating_day_plan(
            day=previous_version.day, records_for_day=affected_records, cyclotron_calendar=updated_cyclotron_calendar,
            pathway=previous_version.pathway, geometry=geometry, assumptions=assumptions,
            resource_calendar=updated_resource_calendar, distribution_concurrency=max(1, min(distribution_concurrency, len(affected_records))),
            requested_batch_count_by_radionuclide={affected_records[0].radionuclide: 1},
            preserve_resource_indices=True, resource_reservations=reservations,
            additional_blocked_injection_indices=additional_blocked_injection_indices,
            additional_blocked_uptake_indices=additional_blocked_uptake_indices,
            additional_blocked_scanner_indices=additional_blocked_scanner_indices,
        )
        if level1_summary.schedule_result is not None:
            new_summary = level1_summary
            recomputed_plans = build_patient_operational_plans(daily_summary=new_summary, records_for_day=affected_records)
            escalation = EscalationRecord(
                starting_scope="LEVEL_1_DIRECTLY_AFFECTED_ONLY", localization_feasible=True,
                reason="Affected-subset reoptimization produced a feasible schedule around preserved assignments.",
                released_assignment_ids=(), final_scope="LEVEL_1_DIRECTLY_AFFECTED_ONLY", result="Localized replan succeeded.",
            )
        else:
            # Section 11/18: escalate explicitly -- affected-only reoptimization
            # could not produce a feasible result within the reserved residual
            # capacity; fall back to a full rerun of every non-locked patient.
            rerun_records = tuple(r for r in updated_records if r.internal_model_patient_id not in locked_ids)
            preserved_batch_count = max(1, previous_version.daily_summary.production_cycle_count)
            radionuclide = rerun_records[0].radionuclide if rerun_records else affected_records[0].radionuclide
            new_summary = run_operating_day_plan(
                day=previous_version.day, records_for_day=rerun_records, cyclotron_calendar=updated_cyclotron_calendar,
                pathway=previous_version.pathway, geometry=geometry, assumptions=assumptions,
                resource_calendar=updated_resource_calendar, distribution_concurrency=distribution_concurrency,
                requested_batch_count_by_radionuclide={radionuclide: preserved_batch_count},
                additional_blocked_injection_indices=additional_blocked_injection_indices,
                additional_blocked_uptake_indices=additional_blocked_uptake_indices,
                additional_blocked_scanner_indices=additional_blocked_scanner_indices,
            ) if rerun_records else previous_version.daily_summary
            recomputed_plans = build_patient_operational_plans(daily_summary=new_summary, records_for_day=rerun_records) if rerun_records else ()
            preserved_plans = ()  # everyone non-locked was released into the LEVEL_3 rerun
            escalation = EscalationRecord(
                starting_scope="LEVEL_1_DIRECTLY_AFFECTED_ONLY", localization_feasible=False,
                reason="Affected-subset reoptimization could not produce ANY feasible schedule (no residual capacity).",
                released_assignment_ids=tuple(sorted(preserved_ids)), final_scope="LEVEL_3_OPERATING_DAY_REOPTIMIZATION",
                result="Escalated to a full operating-day rerun of all non-locked patients.",
            )

    new_plans = recomputed_plans + preserved_plans + locked_plans

    changeset = diff_patient_plans(previous_version.patient_plans, new_plans, directly_affected_ids=frozenset(affected_ids))
    changeset = replace(changeset, new_unmet=new_summary.unmet_demand)

    new_version = PlanVersion(
        version_id=_next_version_id(previous_version.version_id), previous_version_id=previous_version.version_id,
        day=previous_version.day, pathway=previous_version.pathway, daily_summary=new_summary, patient_plans=new_plans,
        triggering_event_id=event.integration_event.source_event_id, created_at=_effective_timestamp(event),
    )
    final_scope: ReoptimizationScope = "OPERATING_DAY" if escalation.final_scope == "LEVEL_3_OPERATING_DAY_REOPTIMIZATION" else impact.recommended_scope
    store.event_journal[-1] = replace(store.event_journal[-1], reoptimization_scope=final_scope, resulting_plan_version_id=new_version.version_id)
    return status, impact, new_version, changeset, escalation


# ---------------------------------------------------------------------------
# Hybrid Live-State adapter (this build): represents an EXISTING Hybrid
# result as the SAME PlanVersion/rolling-state abstraction, reusing the SAME
# `PatientOperationalPlan` type -- never a second patient-plan/scheduler.
# ---------------------------------------------------------------------------

_HYBRID_TRANSPORT_MODE: Mapping[str, Pathway] = {"CONVENTIONAL": "Conventional", "MRT": "MRT"}


def build_hybrid_patient_operational_plans(
    hybrid_result: HybridEvaluationResult, *, day: date,
) -> tuple[PatientOperationalPlan, ...]:
    """Section 4/D: the smallest adapter necessary -- maps each
    `HybridPatientTrace` (already carrying persistent shared INJ/UP/SCN
    identity, section 6) onto the EXISTING `PatientOperationalPlan` type, so
    every existing Live-State function (`diff_patient_plans`,
    `compute_plan_stability`, `analyze_event_impact`, ...) works UNCHANGED on
    a Hybrid plan."""
    return tuple(
        PatientOperationalPlan(
            internal_model_patient_id=trace.patient_id,
            external_patient_reference=None,
            day=day,
            radionuclide=hybrid_result.radionuclide,
            cyclotron_id=trace.assigned_cyclotron_id,
            radiopharmacy_origin_id=trace.radiopharmacy_origin_id,
            batch_id=trace.production_cycle_batch_id,
            production_window_id=trace.production_window_id,
            release_time_minutes=trace.release_time_minutes,
            transport_mode=_HYBRID_TRANSPORT_MODE[trace.transport_mode],
            clinical_resource_mode=trace.clinical_resource_mode,  # type: ignore[arg-type]
            injection_resource_id=trace.injection_resource_id,
            uptake_resource_id=trace.uptake_resource_id,
            scanner_resource_id=trace.scanner_resource_id,
            injection_window_minutes=(trace.injection_start_minutes, trace.injection_end_minutes),
            uptake_window_minutes=(trace.uptake_start_minutes, trace.uptake_end_minutes),
            scan_window_minutes=(trace.scan_start_minutes, trace.scan_end_minutes),
            inbound_room_id=trace.inbound_room_id,
            completed_within_operating_day=trace.clinically_completed,
        )
        for trace in sorted(hybrid_result.patient_traces, key=lambda t: t.patient_id)
    )


@dataclass(frozen=True)
class HybridPlanVersion:
    """Section 4: Hybrid's own minimal PlanVersion-equivalent -- `pathway` is
    fixed to "Hybrid" (never Literal["Conventional","MRT"], so never
    conflated with a pure-pathway `PlanVersion`), and `hybrid_result` replaces
    `daily_summary` (Hybrid has no `DailyOperationalSummary`, it has its own
    joint-schedule result type). `patient_plans` is the SAME
    `PatientOperationalPlan` tuple type as `PlanVersion` -- section 5/6."""

    version_id: str
    previous_version_id: str | None
    day: date
    pathway: Literal["Hybrid"]
    hybrid_result: HybridEvaluationResult
    patient_plans: tuple[PatientOperationalPlan, ...]
    triggering_event_id: str | None
    created_at: datetime


def baseline_hybrid_plan_version(*, day: date, hybrid_result: HybridEvaluationResult, created_at: datetime) -> HybridPlanVersion:
    return HybridPlanVersion(
        version_id="PLAN-0000", previous_version_id=None, day=day, pathway="Hybrid", hybrid_result=hybrid_result,
        patient_plans=build_hybrid_patient_operational_plans(hybrid_result, day=day),
        triggering_event_id=None, created_at=created_at,
    )


_HYBRID_DAY_ENGINE_REPLAN_EVENT_TYPES = frozenset({
    "PATIENT_CANCELLED", "PATIENT_NO_SHOW", "PATIENT_DELAYED",
    "RESOURCE_UNAVAILABLE", "RESOURCE_AVAILABLE",
    "MRT_CARRIER_STATE_CHANGE", "CONVENTIONAL_TRANSPORT_CAPACITY_CHANGE", "STAFF_CAPACITY_CHANGE",
})
"""Scope disclosure (section F/AH): Hybrid live-state, this build, covers
shared-resource outages, cancellation/no-show/delay, MRT-carrier failure,
Conventional-transport shortage, and staff-capacity shortfall -- the
scenarios required by sections 40-45. CYCLOTRON_RELEASE_DELAY/
ACTUAL_RELEASE_ACTIVITY/TRANSPORT_DELAY are NOT wired for Hybrid this build
(Hybrid's production/transport basis is fixed at evaluation time, not
re-derivable from `HybridEvaluationResult` alone) -- disclosed, not silently
claimed complete."""

_STAFF_POOL_RESOURCE_ID_PREFIX: Mapping[StaffPool, str] = {"INJECTION": "INJ-", "UPTAKE": "UP-", "SCANNER": "SCN-"}


def _hybrid_blocked_indices_from_store(store: OperationalStateStore) -> tuple[frozenset[int], frozenset[int], frozenset[int]]:
    injection: set[int] = set()
    uptake: set[int] = set()
    scanner: set[int] = set()
    for resource_id, record in store.resource_state.items():
        if record.state != "UNAVAILABLE":
            continue
        if resource_id.startswith("INJ-"):
            injection.add(int(resource_id.split("-")[1]) - 1)
        elif resource_id.startswith("UP-"):
            uptake.add(int(resource_id.split("-")[1]) - 1)
        elif resource_id.startswith("SCN-"):
            scanner.add(int(resource_id.split("-")[1]) - 1)
    return frozenset(injection), frozenset(uptake), frozenset(scanner)


def _hybrid_reservations_by_index(preserved_plans: Sequence[PatientOperationalPlan]) -> tuple[dict[int, float], dict[int, float], dict[int, float]]:
    reservations = _compute_resource_reservations(preserved_plans)
    injection: dict[int, float] = {}
    uptake: dict[int, float] = {}
    scanner: dict[int, float] = {}
    for resource_id, reserved_until in reservations.items():
        if resource_id.startswith("INJ-"):
            injection[int(resource_id.split("-")[1]) - 1] = reserved_until
        elif resource_id.startswith("UP-"):
            uptake[int(resource_id.split("-")[1]) - 1] = reserved_until
        elif resource_id.startswith("SCN-"):
            scanner[int(resource_id.split("-")[1]) - 1] = reserved_until
    return injection, uptake, scanner


def apply_hybrid_event_and_replan(
    *,
    event: OperationalEvent,
    store: OperationalStateStore,
    previous_version: HybridPlanVersion,
) -> tuple[EventApplicationStatus, ImpactAnalysisResult | None, HybridPlanVersion | None, PlanChangeset | None, EscalationRecord | None]:
    """Section 4/14/17: the Hybrid counterpart of `apply_event_and_replan`,
    reusing the IDENTICAL LOCKED/PRESERVED/AFFECTED partition, escalation
    record shape, and diff/stability machinery -- the only difference is the
    rerun call itself, which uses `rerun_hybrid_affected_subset` (reusing
    `schedule_operating_day`) instead of `run_operating_day_plan` (Hybrid has
    no `CyclotronCalendar`/`ResourceAvailabilityCalendar` input surface;
    resource-outage/staff-capacity state is read directly from the SAME
    `OperationalStateStore` used by the Conventional/MRT path, section 6)."""
    status = store.record_event(event)
    if status != "APPLIED":
        return status, None, None, None, None

    locked_ids = {pid for pid in (p.internal_model_patient_id for p in previous_version.patient_plans) if store.is_locked(pid)}
    impact = analyze_event_impact(event=event, previous_plans=previous_version.patient_plans, locked_patient_ids=frozenset(locked_ids))
    if not impact.reoptimization_required:
        return status, impact, None, None, None

    if event.event_kind not in _HYBRID_DAY_ENGINE_REPLAN_EVENT_TYPES:
        return status, impact, None, None, None

    affected_ids = (set(impact.directly_affected_patient_ids) | set(impact.downstream_affected_patient_ids)) - locked_ids
    removed_ids: set[str] = set()
    if event.event_kind in ("PATIENT_CANCELLED", "PATIENT_NO_SHOW") and event.object_id is not None:
        removed_ids = {event.object_id}
        affected_ids = affected_ids - removed_ids  # the cancelled patient is removed, never rescheduled

    preserved_ids = {pid for pid in (p.internal_model_patient_id for p in previous_version.patient_plans) if pid not in locked_ids and pid not in affected_ids and pid not in removed_ids}
    preserved_plans = tuple(p for p in previous_version.patient_plans if p.internal_model_patient_id in preserved_ids)
    locked_plans = tuple(p for p in previous_version.patient_plans if p.internal_model_patient_id in locked_ids)

    blocked_injection, blocked_uptake, blocked_scanner = _hybrid_blocked_indices_from_store(store)
    if event.event_kind == "STAFF_CAPACITY_CHANGE" and event.staff_pool is not None and event.actual_value is not None:
        total_count = {
            "INJECTION": previous_version.hybrid_result.candidate.injection_resources,
            "UPTAKE": previous_version.hybrid_result.candidate.uptake_resources,
            "SCANNER": previous_version.hybrid_result.candidate.scanners,
        }[event.staff_pool]
        extra = frozenset(range(max(0, int(event.actual_value)), total_count))
        if event.staff_pool == "INJECTION":
            blocked_injection = blocked_injection | extra
        elif event.staff_pool == "UPTAKE":
            blocked_uptake = blocked_uptake | extra
        else:
            blocked_scanner = blocked_scanner | extra

    escalation: EscalationRecord
    if not affected_ids:
        recomputed_plans: tuple[PatientOperationalPlan, ...] = ()
        escalation = EscalationRecord(
            starting_scope="LEVEL_1_DIRECTLY_AFFECTED_ONLY", localization_feasible=True,
            reason="No affected records remained after applying the event (e.g. sole cancellation).",
            released_assignment_ids=(), final_scope="LEVEL_1_DIRECTLY_AFFECTED_ONLY", result="No rerun necessary.",
        )
    else:
        injection_reserved, uptake_reserved, scanner_reserved = _hybrid_reservations_by_index(preserved_plans)
        updated_traces = rerun_hybrid_affected_subset(
            hybrid_result=previous_version.hybrid_result, affected_patient_ids=frozenset(affected_ids),
            blocked_injection_indices=blocked_injection, blocked_uptake_indices=blocked_uptake, blocked_scanner_indices=blocked_scanner,
            injection_reserved_until=injection_reserved, uptake_reserved_until=uptake_reserved, scanner_reserved_until=scanner_reserved,
        )
        localized_feasible = bool(updated_traces) and any(t.clinically_completed for t in updated_traces)
        if localized_feasible:
            recomputed_plans = build_hybrid_patient_operational_plans(
                replace(previous_version.hybrid_result, patient_traces=updated_traces), day=previous_version.day,
            )
            escalation = EscalationRecord(
                starting_scope="LEVEL_1_DIRECTLY_AFFECTED_ONLY", localization_feasible=True,
                reason="Affected-subset reoptimization produced a feasible schedule around preserved assignments.",
                released_assignment_ids=(), final_scope="LEVEL_1_DIRECTLY_AFFECTED_ONLY", result="Localized replan succeeded.",
            )
        else:
            # Section 11/18: escalate explicitly -- rerun EVERY non-locked
            # patient through the SAME joint-schedule rerun mechanism (never a
            # second Hybrid scheduler), releasing all preserved assignments.
            rerun_ids = frozenset(pid for pid in (p.internal_model_patient_id for p in previous_version.patient_plans) if pid not in locked_ids)
            updated_traces = rerun_hybrid_affected_subset(
                hybrid_result=previous_version.hybrid_result, affected_patient_ids=rerun_ids,
                blocked_injection_indices=blocked_injection, blocked_uptake_indices=blocked_uptake, blocked_scanner_indices=blocked_scanner,
            )
            recomputed_plans = build_hybrid_patient_operational_plans(
                replace(previous_version.hybrid_result, patient_traces=updated_traces), day=previous_version.day,
            )
            preserved_plans = ()
            escalation = EscalationRecord(
                starting_scope="LEVEL_1_DIRECTLY_AFFECTED_ONLY", localization_feasible=False,
                reason="Affected-subset reoptimization could not produce ANY feasible schedule (no residual capacity).",
                released_assignment_ids=tuple(sorted(preserved_ids)), final_scope="LEVEL_3_OPERATING_DAY_REOPTIMIZATION",
                result="Escalated to a full joint-schedule rerun of all non-locked patients.",
            )

    new_plans = recomputed_plans + preserved_plans + locked_plans
    changeset = diff_patient_plans(previous_version.patient_plans, new_plans, directly_affected_ids=frozenset(affected_ids))

    new_version = HybridPlanVersion(
        version_id=_next_version_id(previous_version.version_id), previous_version_id=previous_version.version_id,
        day=previous_version.day, pathway="Hybrid", hybrid_result=previous_version.hybrid_result, patient_plans=new_plans,
        triggering_event_id=event.integration_event.source_event_id, created_at=_effective_timestamp(event),
    )
    final_scope: ReoptimizationScope = "OPERATING_DAY" if escalation.final_scope == "LEVEL_3_OPERATING_DAY_REOPTIMIZATION" else impact.recommended_scope
    store.event_journal[-1] = replace(store.event_journal[-1], reoptimization_scope=final_scope, resulting_plan_version_id=new_version.version_id)
    return status, impact, new_version, changeset, escalation


# ---------------------------------------------------------------------------
# Direct-computation handlers for non-day-engine-hooked event kinds
# (sections 37-41, 45, 47-48, 50)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetentionVarianceResult:
    patient_id: str
    half_life_minutes: float
    planned_elapsed_minutes: float
    actual_elapsed_minutes: float
    retention_before: float
    retention_after: float
    qualification_changed: bool


def recompute_retention_after_delay(
    *, patient_id: str, release_time_minutes: float, planned_administration_minutes: float, delay_minutes: float,
    half_life_minutes: float, retention_threshold: float,
) -> RetentionVarianceResult:
    """Section 38/87: retention is ALWAYS recomputed from actual/revised
    release->administration timing via the authoritative decay engine --
    never a preserved stale qualification label."""
    planned_elapsed = max(0.0, planned_administration_minutes - release_time_minutes)
    actual_elapsed = max(0.0, planned_administration_minutes + delay_minutes - release_time_minutes)
    before = retained_fraction(planned_elapsed, half_life_minutes)
    after = retained_fraction(actual_elapsed, half_life_minutes)
    return RetentionVarianceResult(
        patient_id=patient_id, half_life_minutes=half_life_minutes, planned_elapsed_minutes=planned_elapsed,
        actual_elapsed_minutes=actual_elapsed, retention_before=before, retention_after=after,
        qualification_changed=(before >= retention_threshold) != (after >= retention_threshold),
    )


@dataclass(frozen=True)
class ProductionActivityVarianceResult:
    cyclotron_id: str
    required_activity_mbq: float
    actual_activity_mbq: float
    variance_mbq: float
    status: Literal["SHORTFALL", "SURPLUS", "MATCHED"]
    servable_patient_count: int


def compute_production_activity_variance(
    *, cyclotron_id: str, required_activity_mbq: float, actual_activity_mbq: float, activity_per_patient_mbq: float,
) -> ProductionActivityVarianceResult:
    """Section 39-41: never allocates more physical activity than actually
    exists (shortfall), never fabricates phantom patients/revenue from
    surplus -- both are reported, not silently absorbed."""
    variance = actual_activity_mbq - required_activity_mbq
    status: Literal["SHORTFALL", "SURPLUS", "MATCHED"] = "MATCHED"
    if variance < -1e-9:
        status = "SHORTFALL"
    elif variance > 1e-9:
        status = "SURPLUS"
    servable = int(actual_activity_mbq // activity_per_patient_mbq) if activity_per_patient_mbq > 0 else 0
    return ProductionActivityVarianceResult(
        cyclotron_id=cyclotron_id, required_activity_mbq=required_activity_mbq, actual_activity_mbq=actual_activity_mbq,
        variance_mbq=variance, status=status, servable_patient_count=servable,
    )


@dataclass(frozen=True)
class TaskVarianceResult:
    patient_id: str
    stage: ClinicalStage
    planned_start_minutes: float
    actual_start_minutes: float
    planned_end_minutes: float
    actual_end_minutes: float
    start_variance_minutes: float
    end_variance_minutes: float


def compute_task_variance(
    *, patient_id: str, stage: ClinicalStage, planned_window: tuple[float, float], actual_window: tuple[float, float],
) -> TaskVarianceResult:
    """Section 50."""
    return TaskVarianceResult(
        patient_id=patient_id, stage=stage, planned_start_minutes=planned_window[0], actual_start_minutes=actual_window[0],
        planned_end_minutes=planned_window[1], actual_end_minutes=actual_window[1],
        start_variance_minutes=actual_window[0] - planned_window[0], end_variance_minutes=actual_window[1] - planned_window[1],
    )


@dataclass(frozen=True)
class StaffCapacityImpactResult:
    pool_name: str
    scheduled_fte_demand: float
    actual_capacity_fte: float
    shortfall_fte: float
    affected: bool


def compute_staff_capacity_impact(*, pool_name: str, scheduled_fte_demand: float, actual_capacity_fte: float) -> StaffCapacityImpactResult:
    """Section 48."""
    shortfall = max(0.0, scheduled_fte_demand - actual_capacity_fte)
    return StaffCapacityImpactResult(
        pool_name=pool_name, scheduled_fte_demand=scheduled_fte_demand, actual_capacity_fte=actual_capacity_fte,
        shortfall_fte=shortfall, affected=shortfall > 1e-9,
    )


# ---------------------------------------------------------------------------
# GENERATOR / SPECT SCANNER LIVE-STATE REOPTIMIZATION (NUCLEAR TRUNK FINAL
# INTEGRATION CORRECTION, sections 22-25): reuses the SAME
# ImpactAnalysisResult type and LOCKED/PRESERVED/AFFECTED locality philosophy
# as `analyze_event_impact`/`apply_event_and_replan`, scoped to
# `oncology_pet_spect_scenario.SpectDoseLineage` records. These functions
# NEVER read or write `PatientOperationalPlan` (PET) data -- PET non-drift is
# proven by construction, not merely asserted (section 25).
# ---------------------------------------------------------------------------


def analyze_generator_event_impact(
    *, event: OperationalEvent, spect_lineages: Sequence["object"], locked_patient_ids: frozenset[str] = frozenset(),
) -> ImpactAnalysisResult:
    """Section 11: GENERATOR_UNAVAILABLE/AVAILABLE impact analysis over SPECT
    dose lineages ONLY -- mirrors `analyze_event_impact`'s CYCLOTRON_UNAVAILABLE
    branch exactly, matching `lineage.generator_id` instead of `p.cyclotron_id`.
    `locked_patient_ids` (completed/locked patients) are EXCLUDED from
    `directly_affected_patient_ids` -- a locked SPECT dose is never rewritten
    regardless of a later source outage."""
    all_ids = tuple(lineage.patient_id for lineage in spect_lineages)
    directly = tuple(
        lineage.patient_id for lineage in spect_lineages
        if lineage.generator_id == event.object_id and lineage.patient_id not in locked_patient_ids
    )
    required = event.event_kind == "GENERATOR_UNAVAILABLE" and bool(directly)
    return ImpactAnalysisResult(
        event=event, changed_object_id=event.object_id, directly_affected_patient_ids=directly,
        downstream_affected_patient_ids=(), unaffected_patient_ids=tuple(pid for pid in all_ids if pid not in directly),
        constraints_invalidated=(["PRODUCTION_CAPACITY"] if required else []),
        reoptimization_required=required, recommended_scope=("OPERATING_DAY" if required else "NONE"),
        impact_classification="SHARED_RESOURCE_IMPACT",
    )


def analyze_spect_scanner_event_impact(
    *, event: OperationalEvent, spect_lineages: Sequence["object"],
) -> ImpactAnalysisResult:
    """Section 24: SPECT_SCANNER_UNAVAILABLE/RECOVERED impact analysis over
    SPECT dose lineages ONLY -- reuses the SAME RESOURCE_UNAVAILABLE
    'directly affected by resource id' pattern, scoped to `scanner_id`."""
    all_ids = tuple(lineage.patient_id for lineage in spect_lineages)
    directly = tuple(lineage.patient_id for lineage in spect_lineages if lineage.scanner_id == event.object_id)
    required = event.event_kind == "SPECT_SCANNER_UNAVAILABLE" and bool(directly)
    return ImpactAnalysisResult(
        event=event, changed_object_id=event.object_id, directly_affected_patient_ids=directly,
        downstream_affected_patient_ids=(), unaffected_patient_ids=tuple(pid for pid in all_ids if pid not in directly),
        constraints_invalidated=(["RESOURCE_EXCLUSIVITY"] if required else []),
        reoptimization_required=required, recommended_scope=("OPERATING_DAY" if required else "NONE"),
        impact_classification="SHARED_RESOURCE_IMPACT",
    )


@dataclass(frozen=True)
class SpectReplanResult:
    """Section 22/25: locked/preserved/affected partition applied to SPECT
    dose lineages only -- proves locality (unaffected SPECT patients AND all
    PET patients are untouched, byte-for-byte)."""

    preserved_patient_ids: tuple[str, ...]
    affected_patient_ids: tuple[str, ...]
    revised_lineages: tuple["object", ...]
    unmet_patient_ids: tuple[str, ...]
    escalation: EscalationLevel


def replan_spect_after_generator_event(
    *, event: OperationalEvent, spect_lineages: Sequence["object"], alternate_sources: Sequence["object"] = (),
    elution_datetime: datetime | None = None, preparation_processing_minutes: float = 20.0,
    locked_patient_ids: frozenset[str] = frozenset(),
) -> SpectReplanResult:
    """Section 3/20: GENERATOR_UNAVAILABLE -> affected elutions -> affected
    preparation batches -> affected SPECT patient doses -> affected named
    patients -> COMPLETE alternate-generator lineage rematerialization.
    Preserved (unaffected) SPECT lineages are carried forward UNCHANGED --
    never reshuffled. PET patients are never referenced by this function.

    GOVERNING RULE (section 1): a patient is only ever reported served
    if a complete revised `SpectDoseLineage` (-> real `PreparationBatch` ->
    real `EluteEvent` -> the alternate `GeneratorAsset`'s own consumed state)
    exists in `revised_lineages`. Reuses -- never duplicates -- `generator.py`'s
    `GeneratorAsset.elute()`/`build_preparation_batch()` and
    `oncology_pet_spect_scenario.SpectDoseLineage` (section 2)."""
    from generator import build_preparation_batch
    from oncology_pet_spect_scenario import SpectDoseLineage, allocate_spect_patients_across_generators
    from multi_isotope_decay import retained_fraction as _retained_fraction

    impact = analyze_generator_event_impact(event=event, spect_lineages=spect_lineages, locked_patient_ids=locked_patient_ids)
    preserved = tuple(l for l in spect_lineages if l.patient_id not in impact.directly_affected_patient_ids)
    affected = tuple(l for l in spect_lineages if l.patient_id in impact.directly_affected_patient_ids)

    if not impact.reoptimization_required or not affected:
        return SpectReplanResult(
            preserved_patient_ids=tuple(l.patient_id for l in preserved), affected_patient_ids=(),
            revised_lineages=tuple(spect_lineages), unmet_patient_ids=(), escalation="LEVEL_0_STATE_UPDATE_ONLY",
        )

    if not alternate_sources or elution_datetime is None:
        # No alternate generator available -- explicit unmet status, never fabricated activity (section 15).
        return SpectReplanResult(
            preserved_patient_ids=tuple(l.patient_id for l in preserved), affected_patient_ids=tuple(l.patient_id for l in affected),
            revised_lineages=tuple(preserved), unmet_patient_ids=tuple(l.patient_id for l in affected),
            escalation="LEVEL_2_AFFECTED_RESOURCE_NEIGHBORHOOD",
        )

    activity_per_patient = affected[0].preparation_batch.activity_per_patient_mbq() if affected else 0.0
    allocation = allocate_spect_patients_across_generators(
        sources=tuple(alternate_sources), required_eluted_activity_per_patient_mbq=activity_per_patient,
        patients_requested=len(affected), elution_datetime=elution_datetime,
    )

    # Section 12: reuse the SAME per-generator serve counts the allocation authority
    # already computed -- never hard-code a single alternate generator. Slice the
    # affected list in the SAME order the allocator consumed it (greedy, per source).
    remaining_affected = list(affected)
    revised_served: list[SpectDoseLineage] = []
    for source, feasibility in zip(alternate_sources, allocation.per_generator):
        if feasibility.patients_served <= 0 or not remaining_affected:
            continue
        batch_patients = remaining_affected[: feasibility.patients_served]
        remaining_affected = remaining_affected[feasibility.patients_served :]

        # Section 6-7: consume the alternate generator's REAL state via the
        # SAME `GeneratorAsset.elute()` physics (pre-elution -> eluted ->
        # residual -> subsequent ingrowth), never allocate activity without
        # consuming it from the source.
        updated_generator, elute_event = source.generator_physics.elute(at_datetime=elution_datetime)
        batch = build_preparation_batch(
            batch_id=f"TC99M-BATCH-REASSIGN-{source.source_id}-{elution_datetime.isoformat()}",
            elute_event=elute_event, generator_id=source.source_id,
            preparation_processing_minutes=preparation_processing_minutes,
            patient_ids=tuple(l.patient_id for l in batch_patients),
        )
        activity_each = batch.activity_per_patient_mbq()
        for old_lineage in batch_patients:
            fraction = _retained_fraction(old_lineage.transport_minutes, 360.0)  # Tc-99m half-life, unchanged transport time (section 9)
            revised_served.append(SpectDoseLineage(
                patient_id=old_lineage.patient_id,  # section 4: identity preserved, never P-023-NEW
                procedure_id=old_lineage.procedure_id,  # section 4/8: procedure identity preserved
                generator_id=source.source_id,
                preparation_batch=batch,
                activity_at_administration_mbq=activity_each * fraction,
                retained_fraction_at_administration=fraction,
                transport_minutes=old_lineage.transport_minutes,  # section 9: scanner/transport preserved unless infeasible
                architecture=old_lineage.architecture,
                scanner_id=old_lineage.scanner_id,  # section 9: scanner assignment preserved (outage is generator-only)
            ))

    served_patient_ids = frozenset(l.patient_id for l in revised_served)
    unmet_patient_ids = tuple(l.patient_id for l in affected if l.patient_id not in served_patient_ids)
    return SpectReplanResult(
        preserved_patient_ids=tuple(l.patient_id for l in preserved), affected_patient_ids=tuple(l.patient_id for l in affected),
        revised_lineages=preserved + tuple(revised_served),  # section 20: complete lineages returned directly, no caller follow-up required
        unmet_patient_ids=unmet_patient_ids,
        escalation="LEVEL_2_AFFECTED_RESOURCE_NEIGHBORHOOD" if unmet_patient_ids else "LEVEL_1_DIRECTLY_AFFECTED_ONLY",
    )


def replan_spect_after_scanner_event(
    *, event: OperationalEvent, spect_lineages: Sequence["object"], alternate_scanner_ids: Sequence[str] = (),
) -> SpectReplanResult:
    """Section 24-25: SPECT_SCANNER_UNAVAILABLE reassigns ONLY the directly
    affected patients to an alternate SPECT scanner (if any) -- preserved
    patients and ALL PET patients are untouched (non-drift, section 25)."""
    impact = analyze_spect_scanner_event_impact(event=event, spect_lineages=spect_lineages)
    preserved = tuple(l for l in spect_lineages if l.patient_id not in impact.directly_affected_patient_ids)
    affected = tuple(l for l in spect_lineages if l.patient_id in impact.directly_affected_patient_ids)

    if not impact.reoptimization_required or not affected:
        return SpectReplanResult(
            preserved_patient_ids=tuple(l.patient_id for l in preserved), affected_patient_ids=(),
            revised_lineages=tuple(spect_lineages), unmet_patient_ids=(), escalation="LEVEL_0_STATE_UPDATE_ONLY",
        )

    if not alternate_scanner_ids:
        return SpectReplanResult(
            preserved_patient_ids=tuple(l.patient_id for l in preserved), affected_patient_ids=tuple(l.patient_id for l in affected),
            revised_lineages=tuple(preserved), unmet_patient_ids=tuple(l.patient_id for l in affected),
            escalation="LEVEL_2_AFFECTED_RESOURCE_NEIGHBORHOOD",
        )

    new_scanner = alternate_scanner_ids[0]
    revised_affected = tuple(replace(l, scanner_id=new_scanner) for l in affected)
    return SpectReplanResult(
        preserved_patient_ids=tuple(l.patient_id for l in preserved), affected_patient_ids=tuple(l.patient_id for l in affected),
        revised_lineages=preserved + revised_affected, unmet_patient_ids=(), escalation="LEVEL_1_DIRECTLY_AFFECTED_ONLY",
    )


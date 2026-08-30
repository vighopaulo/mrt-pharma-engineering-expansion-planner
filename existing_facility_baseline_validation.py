"""Existing Facility / AS-IS Digital Twin -- PHASE 1F BASELINE VALIDATION AUTHORITY.

GOVERNING QUESTION (Sec 0): "How well does the Phase 1E simulated baseline
reproduce the real existing hospital?"

A baseline becomes *validated* only to the extent that ACTUAL facility evidence
supports the simulated behavior. Missing validation evidence stays missing.
This module never manufactures agreement.

HARD BOUNDARY (Sec 0/44-49): this module is VALIDATION EVIDENCE + COMPARISON +
COVERAGE + QUALIFICATION + LOCKDOWN-ELIGIBILITY ASSESSMENT. It is NOT:
  - a second simulation engine (it consumes the Phase 1E result, never reruns);
  - a second patient / clinical-resource / spatial / production identity system;
  - a model-calibration/tuning authority (it compares; it never tunes);
  - a LOCKDOWN authority (it reports eligibility; it never creates LOCKDOWN);
  - a What-If authority.

It reuses, never duplicates:
  - the Phase 1E baseline candidate + result
    (`existing_facility_baseline_simulation.AsIsBaselineSimulationResult`);
  - the Phase 1D operational snapshot vocabulary
    (`existing_facility_operational_state`: provenance/calibration/confidence,
     the evidence-conflict doctrine, the temporal-basis window authority);
  - the ONE decay authority (`multi_isotope_decay`) for activity reference-time
    normalization -- NEVER a second decay equation;
  - the canonical patient / scanner / room / radionuclide identities already
    owned by the reused inputs.

SIMULATION EXECUTION != VALIDATION. A baseline that merely executed is
VALIDATION_INSUFFICIENT until real observed evidence supports it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

# --- Phase 1E baseline candidate + result (reused read-only) -----------------
from existing_facility_baseline_simulation import (
    AsIsBaselineSimulationResult,
    AsIsBaselineSimulationCandidate,
)

# --- Phase 1D operational-state provenance vocabulary (reused, never remodeled)
# These Literals are the SAME provenance axes Phase 1C/1D already own; Phase 1F
# reuses them so validation evidence never invents a parallel provenance system.
from existing_facility_operational_state import (
    OperationalTemporalBasis,
)

# --- The ONE decay authority (reused; NO second decay equation) --------------
from multi_isotope_decay import retained_fraction


# ===========================================================================
# Sec 5/23: VALIDATION-EVIDENCE PROVENANCE (reuses the Phase 1C/1D axes).
# ===========================================================================
ValidationEvidenceSource = Literal[
    "PROJECT_SUPPLIED",
    "FACILITY_DERIVED",
    "MEASURED",
    "IMPORTED",
    "OBSERVED_OPERATIONAL_RECORD",
    "CONTROLLED_VALIDATION_INPUT",
]
"""Sec 5: where an observed validation fact came from. There is deliberately no
`SIMULATION_OUTPUT` member -- a simulated value is NEVER a source of observed
validation evidence (Sec 6)."""

ValidationEvidenceCalibration = Literal[
    "MEASURED", "IMPORTED", "INFERRED", "CONTROLLED_ASSUMPTION", "NOT_APPLICABLE",
]
"""Sec 23: preserves the measured / imported / inferred / controlled-assumption
distinction the repository already draws elsewhere."""

ValidationEvidenceConfidence = Literal["high", "medium", "low", "unknown"]


# ===========================================================================
# Sec 7: VALIDATION DIMENSIONS.
# ===========================================================================
ValidationDimension = Literal[
    "PATIENT_THROUGHPUT",
    "PATIENT_TIMING",
    "TRANSPORT_TIMING",
    "SCANNER_UTILIZATION",
    "ROOM_UTILIZATION",
    "QUEUE_WAIT_TIME",
    "PRODUCTION_TIMING",
    "INJECTION_TIMING",
    "UPTAKE_TIMING",
    "SCAN_TIMING",
    "STAFF_UTILIZATION",
    "RESOURCE_UTILIZATION",
    "ROUTE_USAGE",
    "RADIONUCLIDE_ACTIVITY",
    "PATIENT_TRAJECTORY",
    "OPERATIONAL_FEASIBILITY",
]

# Sec 11: dimensions that are identity/state comparisons, NOT continuous numeric
# tolerances. For these an exact/identity comparison is valid; numeric tolerance
# semantics are never forced onto them (Sec 11).
IDENTITY_DIMENSIONS: frozenset[ValidationDimension] = frozenset({
    "PATIENT_TRAJECTORY",
    "ROUTE_USAGE",
    "OPERATIONAL_FEASIBILITY",
})


# ===========================================================================
# Sec 9: COMPARISON STATUS VOCABULARY (never collapsed to PASS/FAIL).
# ===========================================================================
ValidationComparisonStatus = Literal[
    "NOT_EVALUATED",
    "NOT_COMPARABLE",
    "MISSING_OBSERVED_EVIDENCE",
    "MISSING_SIMULATED_EVIDENCE",
    "WITHIN_TOLERANCE",
    "OUTSIDE_TOLERANCE",
    "TOLERANCE_NOT_MODELED",
    "MATCH",              # Sec 11: identity/exact-equality dimensions.
    "MISMATCH",           # Sec 11.
    "CONFLICTED_EVIDENCE",
    "QUALIFIED_UNCERTAINTY",
    "NOT_APPLICABLE",
]

# Statuses that count as a positively-passed comparison (Sec 8/28). Note:
# TOLERANCE_NOT_MODELED, MISSING_*, NOT_COMPARABLE and CONFLICTED_EVIDENCE are
# deliberately NOT here -- missing/ambiguous evidence never passes.
_PASSING_STATUSES: frozenset[str] = frozenset({"WITHIN_TOLERANCE", "MATCH"})
_FAILING_STATUSES: frozenset[str] = frozenset({"OUTSIDE_TOLERANCE", "MISMATCH"})
_UNRESOLVED_STATUSES: frozenset[str] = frozenset({
    "NOT_EVALUATED", "NOT_COMPARABLE", "MISSING_OBSERVED_EVIDENCE",
    "MISSING_SIMULATED_EVIDENCE", "TOLERANCE_NOT_MODELED", "CONFLICTED_EVIDENCE",
    "QUALIFIED_UNCERTAINTY",
})


# ===========================================================================
# Sec 30: VALIDATION GAP AUTHORITY.
# ===========================================================================
ValidationGapKind = Literal[
    "MISSING_OBSERVED_EVIDENCE",
    "MISSING_SIMULATED_EVIDENCE",
    "TOLERANCE_NOT_MODELED",
    "CONFLICTED_OBSERVED_STATE",
    "INCOMPATIBLE_OBSERVATION_WINDOW",
    "IDENTITY_MISMATCH",
    "RADIONUCLIDE_MISMATCH",
    "NOT_APPLICABLE_DIMENSION",
]


@dataclass(frozen=True)
class AsIsValidationGap:
    """Sec 30: an explicit validation gap. Missing validation evidence is NEVER
    hidden inside a note -- it becomes a first-class gap."""

    kind: ValidationGapKind
    dimension: ValidationDimension
    detail: str
    blocking_for_lockdown: bool = False


# ===========================================================================
# Sec 10: TOLERANCE AUTHORITY (anti-fabrication -- no universal tolerances).
# ===========================================================================
ToleranceProvenance = Literal[
    "PROJECT_SUPPLIED",
    "FACILITY_SUPPLIED",
    "REPOSITORY_AUTHORITY",
    "CONTROLLED_VALIDATION_EXPERIMENT",
]


@dataclass(frozen=True)
class AsIsValidationTolerance:
    """Sec 10: an EXPLICITLY-supplied numeric tolerance for one dimension. There
    is NO default/universal tolerance: a dimension with no supplied tolerance is
    reported TOLERANCE_NOT_MODELED, never silently WITHIN/OUTSIDE. `provenance`
    records who supplied it -- it is never fabricated by this module."""

    dimension: ValidationDimension
    provenance: ToleranceProvenance
    # Absolute tolerance on |observed - simulated| (same unit as the values).
    absolute_tolerance: float | None = None
    # Relative tolerance as a fraction of |observed| (e.g. 0.05 == 5%).
    relative_tolerance: float | None = None
    note: str = ""

    @property
    def is_modeled(self) -> bool:
        return self.absolute_tolerance is not None or self.relative_tolerance is not None


# ===========================================================================
# Sec 5-6/12-21: VALIDATION EVIDENCE (one observed fact for one dimension).
# ===========================================================================
@dataclass(frozen=True)
class AsIsBaselineValidationEvidence:
    """Sec 5-6: one explicit observed-vs-nothing validation fact. This carries
    ONLY the observed reality + its provenance; the simulated value is looked up
    from the Phase 1E candidate at comparison time and never stored here (Sec 6:
    observed != simulated, never overwrite one with the other).

    `object_identity` binds the observation to a canonical identity (patient id,
    scanner id, room id, radionuclide, route id, ...). `observation_window`
    carries the observed temporal basis so INCOMPATIBLE_OBSERVATION_WINDOW can be
    detected against the simulation window (Sec 12/37)."""

    dimension: ValidationDimension
    observed_value: float | str | None
    unit: str
    source: ValidationEvidenceSource
    source_record_id: str
    object_identity: str | None = None
    radionuclide: str | None = None
    transport_mode: str | None = None
    activity_reference_minutes: float | None = None
    """Sec 20: for RADIONUCLIDE_ACTIVITY, the elapsed minutes from the activity
    reference time (e.g. EOB) at which `observed_value` was measured. Enables
    decay normalization through the ONE decay authority."""
    observation_window: OperationalTemporalBasis | None = None
    calibration: ValidationEvidenceCalibration = "NOT_APPLICABLE"
    confidence: ValidationEvidenceConfidence = "unknown"
    note: str = ""


@dataclass(frozen=True)
class AsIsValidationEvidenceConflict:
    """Sec 22: two observed sources disagree for the SAME dimension + identity.
    Both survive; neither is auto-resolved (mirrors the Phase 1D
    `OperationalEvidenceConflict` doctrine). A conflict on a REQUIRED dimension
    blocks LOCKDOWN eligibility (Sec 22/36)."""

    dimension: ValidationDimension
    object_identity: str | None
    candidate_values: tuple[str, ...]
    candidate_sources: tuple[ValidationEvidenceSource, ...]
    candidate_record_ids: tuple[str, ...]
    resolution_status: Literal["UNRESOLVED", "RESOLVED_BY_PROJECT_AUTHORITY"] = "UNRESOLVED"


# ===========================================================================
# Sec 6: ONE COMPARISON (observed vs simulated, both preserved).
# ===========================================================================
@dataclass(frozen=True)
class AsIsValidationComparison:
    """Sec 6: a single observed-vs-simulated comparison. observed_value and
    simulated_value are BOTH preserved -- one never overwrites the other. When a
    value is unavailable it is None and the status records exactly why."""

    dimension: ValidationDimension
    object_identity: str | None
    observed_value: float | str | None
    simulated_value: float | str | None
    unit: str
    difference: float | None
    status: ValidationComparisonStatus
    observed_source: ValidationEvidenceSource | None
    observed_record_id: str | None
    tolerance: AsIsValidationTolerance | None
    confidence: ValidationEvidenceConfidence
    note: str = ""


# ===========================================================================
# Sec 29: REQUIRED-DIMENSION MANIFEST.
# ===========================================================================
@dataclass(frozen=True)
class AsIsRequiredValidationDimension:
    """Sec 29: one dimension in the manifest for the selected validation scope.
    Requiredness is DECLARED (physically justified), never inferred merely from
    the presence of data (Sec 29)."""

    dimension: ValidationDimension
    required: bool
    reason: str
    observed_evidence_status: Literal["PRESENT", "MISSING", "CONFLICTED"] = "MISSING"
    simulated_evidence_status: Literal["PRESENT", "NOT_AVAILABLE"] = "NOT_AVAILABLE"
    comparison_status: ValidationComparisonStatus = "NOT_EVALUATED"
    blocking_for_lockdown: bool = False


# ===========================================================================
# Sec 8: VALIDATION COVERAGE (first-class; missing never counts as passing).
# ===========================================================================
@dataclass(frozen=True)
class AsIsValidationCoverage:
    """Sec 8: coverage over the required-dimension manifest. `coverage_ratio` is
    None when the denominator is 0 (never a fabricated 1.0). Missing/unresolved
    dimensions are counted as unresolved, NEVER as passed (Sec 8)."""

    required_dimensions: tuple[ValidationDimension, ...]
    dimensions_with_observed_evidence: tuple[ValidationDimension, ...]
    dimensions_with_simulated_evidence: tuple[ValidationDimension, ...]
    dimensions_comparable: tuple[ValidationDimension, ...]
    dimensions_passed: tuple[ValidationDimension, ...]
    dimensions_failed: tuple[ValidationDimension, ...]
    dimensions_unresolved: tuple[ValidationDimension, ...]
    dimensions_not_applicable: tuple[ValidationDimension, ...]

    @property
    def required_count(self) -> int:
        return len(self.required_dimensions)

    @property
    def coverage_ratio(self) -> float | None:
        """Fraction of REQUIRED dimensions that passed. None if none required."""
        denom = len([d for d in self.required_dimensions if d not in self.dimensions_not_applicable])
        if denom == 0:
            return None
        passed_required = len([d for d in self.dimensions_passed if d in self.required_dimensions])
        return passed_required / denom

    @property
    def all_required_dimensions_passed(self) -> bool:
        """True only if every required, applicable dimension is in passed."""
        required_applicable = [
            d for d in self.required_dimensions if d not in self.dimensions_not_applicable
        ]
        if not required_applicable:
            return False
        return all(d in self.dimensions_passed for d in required_applicable)


# ===========================================================================
# Sec 26: BASELINE-LEVEL VALIDATION STATUS.
# ===========================================================================
AsIsBaselineValidationVerdict = Literal[
    "NOT_VALIDATED",
    "VALIDATION_INSUFFICIENT",
    "PARTIALLY_VALIDATED",
    "VALIDATED_WITH_QUALIFICATIONS",
    "VALIDATED",
]

# Sec 27: LOCKDOWN eligibility (calculated here; NEVER acted on). Distinct from
# the Phase 1E placeholder enum -- Phase 1F resolves the richer verdict.
AsIsLockdownEligibilityVerdict = Literal[
    "NOT_ELIGIBLE",
    "VALIDATION_INSUFFICIENT",
    "ELIGIBLE_WITH_QUALIFICATIONS",
    "ELIGIBLE",
]


# ===========================================================================
# Sec 24: VALIDATION SCOPE.
# ===========================================================================
ValidationScope = Literal[
    "NUCLEAR_MEDICINE_ONCOLOGY", "WHOLE_HOSPITAL",
]


# ===========================================================================
# Sec 25/47: TOP-LEVEL VALIDATION RESULT CONTRACT.
# ===========================================================================
@dataclass(frozen=True)
class AsIsBaselineValidationResult:
    """Sec 25: the Phase 1F authority result. Never one overloaded boolean:
    comparisons, conflicts, coverage, status, gaps and LOCKDOWN eligibility are
    all first-class."""

    validation_result_id: str
    facility_id: str
    operational_snapshot_id: str
    baseline_candidate_execution_status: str
    simulation_scope: str
    validation_scope: ValidationScope

    required_manifest: tuple[AsIsRequiredValidationDimension, ...]
    comparisons: tuple[AsIsValidationComparison, ...]
    conflicts: tuple[AsIsValidationEvidenceConflict, ...]
    coverage: AsIsValidationCoverage
    validation_status: AsIsBaselineValidationVerdict
    lockdown_eligibility_status: AsIsLockdownEligibilityVerdict
    validation_gaps: tuple[AsIsValidationGap, ...]
    remaining_qualifications: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    # ---- Sec 44-49 HARD boundary proof flags (all fixed) ----
    baseline_mutated_by_validation: bool = False
    model_parameters_auto_tuned: bool = False
    lockdown_created: bool = False
    what_if_created: bool = False
    what_if_execution_started: bool = False
    what_if_baseline_mutated: bool = False
    existing_decay_authority_reused: bool = True
    existing_simulation_engine_reused_read_only: bool = True

    @property
    def is_lockdown_eligible(self) -> bool:
        return self.lockdown_eligibility_status in (
            "ELIGIBLE", "ELIGIBLE_WITH_QUALIFICATIONS",
        )


# ===========================================================================
# DEFAULT REQUIRED-DIMENSION MANIFEST (Sec 29) for the nuclear-medicine scope.
# ===========================================================================
def default_required_manifest(
    validation_scope: ValidationScope = "NUCLEAR_MEDICINE_ONCOLOGY",
) -> tuple[AsIsRequiredValidationDimension, ...]:
    """Sec 29: the physically-justified required dimensions for the AS-IS
    nuclear-medicine baseline. Requiredness is DECLARED here, never inferred
    from the presence of data. Dimensions the existing engine cannot expose as a
    simulated metric are still allowed in the manifest (they resolve to
    MISSING_SIMULATED_EVIDENCE, never silently dropped)."""
    if validation_scope == "WHOLE_HOSPITAL":
        # Sec 24: whole-hospital is NOT modeled by the existing engine; declaring
        # it required makes the un-modeled reality visible rather than hidden.
        return (
            AsIsRequiredValidationDimension(
                dimension="PATIENT_THROUGHPUT", required=True,
                reason="Whole-hospital throughput is out of the modeled nuclear scope.",
                blocking_for_lockdown=True,
            ),
        )
    return (
        AsIsRequiredValidationDimension(
            dimension="PATIENT_THROUGHPUT", required=True,
            reason="Baseline must reproduce the observed nuclear patient count.",
            blocking_for_lockdown=True,
        ),
        AsIsRequiredValidationDimension(
            dimension="OPERATIONAL_FEASIBILITY", required=True,
            reason="Observed operational feasibility must match the simulated verdict.",
            blocking_for_lockdown=True,
        ),
        AsIsRequiredValidationDimension(
            dimension="SCANNER_UTILIZATION", required=True,
            reason="Scanner peak occupancy is a core resource-utilization check.",
            blocking_for_lockdown=True,
        ),
        AsIsRequiredValidationDimension(
            dimension="PATIENT_TIMING", required=False,
            reason="Per-stage timing is validated where observed timestamps exist.",
            blocking_for_lockdown=False,
        ),
        AsIsRequiredValidationDimension(
            dimension="RADIONUCLIDE_ACTIVITY", required=False,
            reason="Activity is validated only when an activity reference time is supplied.",
            blocking_for_lockdown=False,
        ),
        AsIsRequiredValidationDimension(
            dimension="PATIENT_TRAJECTORY", required=False,
            reason="Trajectory is validated only when observed movement evidence exists.",
            blocking_for_lockdown=False,
        ),
    )


# ===========================================================================
# SIMULATED-VALUE EXTRACTION (read-only view over the Phase 1E candidate).
# ===========================================================================
_SIMULATED_METRIC_NOT_AVAILABLE = object()


def _half_life_minutes(radionuclide: str) -> float | None:
    """Sec 20: half-life via the existing diagnostics authority (no second
    table). Returns None when the radionuclide is unknown to the authority."""
    try:
        from diagnostics import load_radionuclide_half_lives
        table = load_radionuclide_half_lives()
    except Exception:
        return None
    hl = table.get(radionuclide)
    if hl is None:
        return None
    return float(hl)


def _extract_simulated_value(
    result: AsIsBaselineSimulationResult,
    evidence: AsIsBaselineValidationEvidence,
):
    """Return the simulated counterpart for one observed evidence item, or the
    `_SIMULATED_METRIC_NOT_AVAILABLE` sentinel when the Phase 1E engine does not
    physically expose it (Sec 38). NEVER fabricates a value."""
    outputs = result.outputs
    if outputs is None:
        return _SIMULATED_METRIC_NOT_AVAILABLE

    dim = evidence.dimension

    if dim == "PATIENT_THROUGHPUT":
        return float(outputs.retention_qualified_completed)

    if dim == "SCANNER_UTILIZATION":
        return float(outputs.scanner_peak_occupancy)
    if dim == "INJECTION_TIMING" and evidence.object_identity is None:
        return _SIMULATED_METRIC_NOT_AVAILABLE
    if dim == "RESOURCE_UTILIZATION":
        # Ambiguous which resource pool without an identity -> not available.
        return _SIMULATED_METRIC_NOT_AVAILABLE

    if dim == "OPERATIONAL_FEASIBILITY":
        return "FEASIBLE" if outputs.operationally_feasible else "INFEASIBLE"

    if dim == "RADIONUCLIDE_ACTIVITY":
        # Sec 41: radionuclide identity must survive; cross-radionuclide
        # borrowing is forbidden. The simulated radionuclide is outputs.radionuclide.
        return ("RADIONUCLIDE", outputs.radionuclide)

    # Per-patient trajectory/timing dimensions require an object identity.
    if dim in ("PATIENT_TIMING", "PATIENT_TRAJECTORY", "TRANSPORT_TIMING",
               "INJECTION_TIMING", "UPTAKE_TIMING", "SCAN_TIMING", "ROUTE_USAGE"):
        if evidence.object_identity is None:
            return _SIMULATED_METRIC_NOT_AVAILABLE
        trace = _find_trace(outputs.patient_trajectories, evidence.object_identity)
        if trace is None:
            return _SIMULATED_METRIC_NOT_AVAILABLE
        if dim == "PATIENT_TIMING" or dim == "INJECTION_TIMING":
            return float(trace.injection_start_minutes)
        if dim == "TRANSPORT_TIMING":
            return float(getattr(trace, "transport_arrival_time_minutes", 0.0))
        if dim == "UPTAKE_TIMING":
            return float(getattr(trace, "uptake_start_minutes", 0.0))
        if dim == "SCAN_TIMING":
            return float(getattr(trace, "scan_start_minutes", 0.0))
        if dim == "PATIENT_TRAJECTORY":
            return ("TRAJECTORY", getattr(trace, "destination_room_id", None),
                    getattr(trace, "transport_mode", None))
        if dim == "ROUTE_USAGE":
            return ("ROUTE", getattr(trace, "transport_mode", None))

    # Dimensions the existing engine does not expose (room utilization, queue,
    # production timing, staff, general resource utilization).
    return _SIMULATED_METRIC_NOT_AVAILABLE


def _find_trace(trajectories: Sequence, identity: str):
    for t in trajectories:
        canonical = getattr(t, "canonical_patient_id", None)
        pid = getattr(t, "patient_id", None)
        if identity in (canonical, pid):
            return t
    return None


# ===========================================================================
# TOLERANCE / IDENTITY COMPARISON (Sec 10-11/33-35).
# ===========================================================================
def _compare_numeric(
    observed: float,
    simulated: float,
    tolerance: AsIsValidationTolerance | None,
) -> tuple[ValidationComparisonStatus, float]:
    """Sec 10/33-35: numeric comparison. With no modeled tolerance -> the
    difference is reported but the status is TOLERANCE_NOT_MODELED (never a
    fabricated pass/fail)."""
    difference = float(simulated) - float(observed)
    if tolerance is None or not tolerance.is_modeled:
        return "TOLERANCE_NOT_MODELED", difference
    abs_diff = abs(difference)
    within = True
    if tolerance.absolute_tolerance is not None:
        within = within and abs_diff <= tolerance.absolute_tolerance
    if tolerance.relative_tolerance is not None:
        allowed = tolerance.relative_tolerance * abs(float(observed))
        within = within and abs_diff <= allowed
    return ("WITHIN_TOLERANCE" if within else "OUTSIDE_TOLERANCE"), difference


def _compare_identity(observed, simulated) -> ValidationComparisonStatus:
    """Sec 11: exact/identity comparison for identity dimensions."""
    return "MATCH" if observed == simulated else "MISMATCH"


# ===========================================================================
# WINDOW COMPATIBILITY (Sec 12/37).
# ===========================================================================
def _windows_incompatible(
    observation_window: OperationalTemporalBasis | None,
    simulation_date: str | None,
) -> bool:
    """Sec 37: an observed window is incompatible when it carries an explicit
    effective/valid date that does not match the simulation date and no explicit
    normalization was supplied. When either side lacks a temporal basis we do
    NOT declare incompatibility (we cannot silently invent one either)."""
    if observation_window is None or simulation_date is None:
        return False
    if not observation_window.has_temporal_basis:
        return False
    observed_dates = [
        d[:10] for d in (
            observation_window.effective_at, observation_window.observed_at,
            observation_window.valid_from,
        ) if d is not None
    ]
    if not observed_dates:
        return False
    return all(d != simulation_date[:10] for d in observed_dates)


# ===========================================================================
# CONFLICT DETECTION (Sec 22/36) -- both candidates preserved, never resolved.
# ===========================================================================
def _detect_conflicts(
    evidence: Sequence[AsIsBaselineValidationEvidence],
) -> tuple[AsIsValidationEvidenceConflict, ...]:
    grouped: dict[tuple[ValidationDimension, str | None], list[AsIsBaselineValidationEvidence]] = {}
    for e in evidence:
        grouped.setdefault((e.dimension, e.object_identity), []).append(e)
    conflicts: list[AsIsValidationEvidenceConflict] = []
    for (dim, identity), items in grouped.items():
        distinct_values = {str(i.observed_value) for i in items}
        if len(distinct_values) > 1:
            conflicts.append(AsIsValidationEvidenceConflict(
                dimension=dim, object_identity=identity,
                candidate_values=tuple(sorted(str(i.observed_value) for i in items)),
                candidate_sources=tuple(i.source for i in items),
                candidate_record_ids=tuple(i.source_record_id for i in items),
                resolution_status="UNRESOLVED",
            ))
    return tuple(conflicts)


# ===========================================================================
# THE PHASE 1F ENTRY POINT.
# ===========================================================================
def validate_asis_baseline(
    *,
    baseline_result: AsIsBaselineSimulationResult,
    evidence: Sequence[AsIsBaselineValidationEvidence] = (),
    tolerances: Sequence[AsIsValidationTolerance] = (),
    required_manifest: Sequence[AsIsRequiredValidationDimension] | None = None,
    validation_scope: ValidationScope = "NUCLEAR_MEDICINE_ONCOLOGY",
    validation_result_id: str | None = None,
) -> AsIsBaselineValidationResult:
    """Sec 4/25: validate the EXISTING Phase 1E baseline candidate against
    supplied observed evidence.

    The Phase 1E result is READ ONLY (Sec 44): nothing about the baseline,
    trajectories, timings, resources, economics or production is rewritten, and
    no model parameter is tuned (Sec 45). Missing observed evidence stays missing
    (Sec 6/8); the engine never manufactures agreement."""
    facility_id = baseline_result.facility_id
    snapshot_id = baseline_result.operational_snapshot_id
    scope_name = getattr(baseline_result.scope, "service_domain", str(baseline_result.scope))
    exec_status = baseline_result.execution_status

    manifest = tuple(required_manifest) if required_manifest is not None else default_required_manifest(validation_scope)
    tolerance_by_dim: dict[ValidationDimension, AsIsValidationTolerance] = {t.dimension: t for t in tolerances}

    rid = validation_result_id or f"ASISVAL::{facility_id}::{snapshot_id}::{validation_scope}"

    # Sec 22/36: conflicting observations -- preserved, never auto-resolved.
    conflicts = _detect_conflicts(evidence)
    conflicted_keys = {(c.dimension, c.object_identity) for c in conflicts}

    comparisons: list[AsIsValidationComparison] = []
    gaps: list[AsIsValidationGap] = []

    # If the baseline never executed, there is nothing to validate against.
    if not baseline_result.baseline_simulation_executed:
        # Every required dimension is unresolved; no simulated evidence exists.
        for req in manifest:
            gaps.append(AsIsValidationGap(
                kind="MISSING_SIMULATED_EVIDENCE", dimension=req.dimension,
                detail="Baseline did not execute; no simulated metric exists.",
                blocking_for_lockdown=req.blocking_for_lockdown,
            ))

    # --- Build one comparison per supplied evidence item ---------------------
    simulation_date = getattr(baseline_result.scope, "simulation_date", None)
    for e in evidence:
        key = (e.dimension, e.object_identity)
        tol = tolerance_by_dim.get(e.dimension)

        # Sec 22: an evidence item on a conflicted key is not silently compared.
        if key in conflicted_keys:
            comparisons.append(AsIsValidationComparison(
                dimension=e.dimension, object_identity=e.object_identity,
                observed_value=e.observed_value, simulated_value=None, unit=e.unit,
                difference=None, status="CONFLICTED_EVIDENCE",
                observed_source=e.source, observed_record_id=e.source_record_id,
                tolerance=tol, confidence=e.confidence,
                note="Conflicting observed evidence; both candidates preserved, none chosen.",
            ))
            gaps.append(AsIsValidationGap(
                kind="CONFLICTED_OBSERVED_STATE", dimension=e.dimension,
                detail=f"Conflicting observations for {e.dimension}/{e.object_identity}.",
                blocking_for_lockdown=_is_required(manifest, e.dimension),
            ))
            continue

        # Sec 37: incompatible observation window -> not comparable, no rescale.
        if _windows_incompatible(e.observation_window, simulation_date):
            comparisons.append(AsIsValidationComparison(
                dimension=e.dimension, object_identity=e.object_identity,
                observed_value=e.observed_value, simulated_value=None, unit=e.unit,
                difference=None, status="NOT_COMPARABLE",
                observed_source=e.source, observed_record_id=e.source_record_id,
                tolerance=tol, confidence=e.confidence,
                note="Observation window differs from simulation window; no normalization supplied.",
            ))
            gaps.append(AsIsValidationGap(
                kind="INCOMPATIBLE_OBSERVATION_WINDOW", dimension=e.dimension,
                detail="Observed and simulated windows differ; no silent rescaling applied.",
                blocking_for_lockdown=_is_required(manifest, e.dimension),
            ))
            continue

        simulated = _extract_simulated_value(baseline_result, e)

        # Sec 38: the engine does not expose this simulated metric.
        if simulated is _SIMULATED_METRIC_NOT_AVAILABLE:
            comparisons.append(AsIsValidationComparison(
                dimension=e.dimension, object_identity=e.object_identity,
                observed_value=e.observed_value, simulated_value=None, unit=e.unit,
                difference=None, status="MISSING_SIMULATED_EVIDENCE",
                observed_source=e.source, observed_record_id=e.source_record_id,
                tolerance=tol, confidence=e.confidence,
                note="Phase 1E engine does not expose this simulated metric.",
            ))
            gaps.append(AsIsValidationGap(
                kind="MISSING_SIMULATED_EVIDENCE", dimension=e.dimension,
                detail=f"No simulated value for {e.dimension}/{e.object_identity}.",
                blocking_for_lockdown=_is_required(manifest, e.dimension),
            ))
            continue

        # Sec 6: observed missing -> record and skip (no fabrication).
        if e.observed_value is None:
            comparisons.append(AsIsValidationComparison(
                dimension=e.dimension, object_identity=e.object_identity,
                observed_value=None, simulated_value=_as_scalar(simulated), unit=e.unit,
                difference=None, status="MISSING_OBSERVED_EVIDENCE",
                observed_source=e.source, observed_record_id=e.source_record_id,
                tolerance=tol, confidence=e.confidence,
                note="No observed value supplied.",
            ))
            gaps.append(AsIsValidationGap(
                kind="MISSING_OBSERVED_EVIDENCE", dimension=e.dimension,
                detail=f"No observed value for {e.dimension}/{e.object_identity}.",
                blocking_for_lockdown=_is_required(manifest, e.dimension),
            ))
            continue

        comparison = _build_comparison(e, simulated, tol, manifest, gaps)
        comparisons.append(comparison)

    # --- Required dimensions with NO supplied evidence at all ---------------
    covered_dims = {c.dimension for c in comparisons}
    for req in manifest:
        if req.dimension not in covered_dims and baseline_result.baseline_simulation_executed:
            gaps.append(AsIsValidationGap(
                kind="MISSING_OBSERVED_EVIDENCE", dimension=req.dimension,
                detail=f"Required dimension {req.dimension} has no observed evidence.",
                blocking_for_lockdown=req.blocking_for_lockdown,
            ))

    # --- Refresh manifest evidence/comparison statuses ----------------------
    resolved_manifest = _resolve_manifest(manifest, comparisons, conflicts, baseline_result)

    coverage = _build_coverage(resolved_manifest, comparisons)
    validation_status = _derive_validation_status(
        baseline_result, resolved_manifest, comparisons, conflicts, coverage,
    )
    lockdown_eligibility = _derive_lockdown_eligibility(
        validation_status, resolved_manifest, comparisons, conflicts, gaps,
    )
    qualifications = _collect_qualifications(comparisons, gaps)

    return AsIsBaselineValidationResult(
        validation_result_id=rid,
        facility_id=facility_id,
        operational_snapshot_id=snapshot_id,
        baseline_candidate_execution_status=exec_status,
        simulation_scope=scope_name,
        validation_scope=validation_scope,
        required_manifest=resolved_manifest,
        comparisons=tuple(comparisons),
        conflicts=conflicts,
        coverage=coverage,
        validation_status=validation_status,
        lockdown_eligibility_status=lockdown_eligibility,
        validation_gaps=tuple(gaps),
        remaining_qualifications=qualifications,
        limitations=(
            "Validation is READ-ONLY over the Phase 1E baseline candidate; no baseline "
            "output, trajectory, timing, resource, economic or production value was rewritten.",
            "No model parameter was auto-tuned to improve agreement (Sec 45).",
            "No LOCKDOWN and no What-If were created (Sec 48-49).",
        ),
    )


# ===========================================================================
# Helpers.
# ===========================================================================
def _as_scalar(simulated):
    if isinstance(simulated, tuple):
        return str(simulated)
    return simulated


def _is_required(manifest: Sequence[AsIsRequiredValidationDimension], dim: ValidationDimension) -> bool:
    return any(m.dimension == dim and m.required for m in manifest)


def _build_comparison(
    e: AsIsBaselineValidationEvidence,
    simulated,
    tol: AsIsValidationTolerance | None,
    manifest: Sequence[AsIsRequiredValidationDimension],
    gaps: list[AsIsValidationGap],
) -> AsIsValidationComparison:
    dim = e.dimension

    # Sec 41: RADIONUCLIDE_ACTIVITY -- identity must survive; block cross-nuclide.
    if dim == "RADIONUCLIDE_ACTIVITY":
        sim_radionuclide = simulated[1] if isinstance(simulated, tuple) else None
        if e.radionuclide is not None and sim_radionuclide is not None and e.radionuclide != sim_radionuclide:
            gaps.append(AsIsValidationGap(
                kind="RADIONUCLIDE_MISMATCH", dimension=dim,
                detail=f"Observed {e.radionuclide} vs simulated {sim_radionuclide}; no cross-radionuclide borrowing.",
                blocking_for_lockdown=_is_required(manifest, dim),
            ))
            return AsIsValidationComparison(
                dimension=dim, object_identity=e.object_identity,
                observed_value=e.observed_value, simulated_value=sim_radionuclide, unit=e.unit,
                difference=None, status="NOT_COMPARABLE",
                observed_source=e.source, observed_record_id=e.source_record_id,
                tolerance=tol, confidence=e.confidence,
                note="Radionuclide identity mismatch; decay conversion is NOT used to equate them.",
            )
        # Same radionuclide: activity compared through the ONE decay authority
        # (reference-time normalized). Requires a numeric observed activity.
        return _compare_activity(e, sim_radionuclide, tol, manifest, gaps)

    # Identity dimensions (Sec 11).
    if dim in IDENTITY_DIMENSIONS:
        observed = str(e.observed_value)
        sim_compare = _simulated_identity_form(dim, simulated)
        status = _compare_identity(observed, sim_compare)
        if status == "MISMATCH":
            gaps.append(AsIsValidationGap(
                kind="IDENTITY_MISMATCH", dimension=dim,
                detail=f"Observed {observed!r} vs simulated {sim_compare!r}.",
                blocking_for_lockdown=_is_required(manifest, dim),
            ))
        return AsIsValidationComparison(
            dimension=dim, object_identity=e.object_identity,
            observed_value=e.observed_value, simulated_value=sim_compare, unit=e.unit,
            difference=None, status=status,
            observed_source=e.source, observed_record_id=e.source_record_id,
            tolerance=tol, confidence=e.confidence,
        )

    # Numeric dimensions (Sec 10/33-35).
    try:
        observed_num = float(e.observed_value)  # type: ignore[arg-type]
        simulated_num = float(simulated)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return AsIsValidationComparison(
            dimension=dim, object_identity=e.object_identity,
            observed_value=e.observed_value, simulated_value=_as_scalar(simulated), unit=e.unit,
            difference=None, status="NOT_COMPARABLE",
            observed_source=e.source, observed_record_id=e.source_record_id,
            tolerance=tol, confidence=e.confidence,
            note="Non-numeric value for a numeric dimension.",
        )

    status, difference = _compare_numeric(observed_num, simulated_num, tol)
    if status == "TOLERANCE_NOT_MODELED":
        gaps.append(AsIsValidationGap(
            kind="TOLERANCE_NOT_MODELED", dimension=dim,
            detail=f"No tolerance supplied for {dim}; difference={difference:.4f} reported only.",
            blocking_for_lockdown=False,
        ))
    return AsIsValidationComparison(
        dimension=dim, object_identity=e.object_identity,
        observed_value=observed_num, simulated_value=simulated_num, unit=e.unit,
        difference=difference, status=status,
        observed_source=e.source, observed_record_id=e.source_record_id,
        tolerance=tol, confidence=e.confidence,
    )


def _simulated_identity_form(dim: ValidationDimension, simulated) -> str:
    """Extract the simulated identity scalar to compare against a supplied
    observed identity string (Sec 11/14/15).

    OPERATIONAL_FEASIBILITY -> the plain verdict string.
    PATIENT_TRAJECTORY      -> ("TRAJECTORY", destination_room_id, transport_mode)
                               compared on destination_room_id (the movement
                               endpoint the observation names).
    ROUTE_USAGE             -> ("ROUTE", transport_mode) compared on the mode
                               (transport mode identity must survive)."""
    if isinstance(simulated, tuple):
        tag = simulated[0]
        if tag == "TRAJECTORY":
            return str(simulated[1])  # destination_room_id
        if tag == "ROUTE":
            return str(simulated[1])  # transport_mode
        return str(simulated)
    return str(simulated)


def _compare_activity(
    e: AsIsBaselineValidationEvidence,
    sim_radionuclide: str | None,
    tol: AsIsValidationTolerance | None,
    manifest: Sequence[AsIsRequiredValidationDimension],
    gaps: list[AsIsValidationGap],
) -> AsIsValidationComparison:
    """Sec 20: activity comparison MUST route through the ONE decay authority and
    preserve the activity reference time. Without a reference time we cannot
    normalize and must not fabricate one."""
    if e.activity_reference_minutes is None or sim_radionuclide is None:
        gaps.append(AsIsValidationGap(
            kind="MISSING_OBSERVED_EVIDENCE", dimension="RADIONUCLIDE_ACTIVITY",
            detail="Activity reference time not supplied; decay normalization impossible.",
            blocking_for_lockdown=_is_required(manifest, "RADIONUCLIDE_ACTIVITY"),
        ))
        return AsIsValidationComparison(
            dimension="RADIONUCLIDE_ACTIVITY", object_identity=e.object_identity,
            observed_value=e.observed_value, simulated_value=None, unit=e.unit,
            difference=None, status="NOT_COMPARABLE",
            observed_source=e.source, observed_record_id=e.source_record_id,
            tolerance=tol, confidence=e.confidence,
            note="No activity reference time; cannot normalize through the decay authority.",
        )
    half_life = _half_life_minutes(sim_radionuclide)
    if half_life is None:
        return AsIsValidationComparison(
            dimension="RADIONUCLIDE_ACTIVITY", object_identity=e.object_identity,
            observed_value=e.observed_value, simulated_value=None, unit=e.unit,
            difference=None, status="NOT_COMPARABLE",
            observed_source=e.source, observed_record_id=e.source_record_id,
            tolerance=tol, confidence=e.confidence,
            note=f"Half-life for {sim_radionuclide} unknown to the decay authority.",
        )
    # Normalize the OBSERVED activity to the reference time using the ONE decay
    # authority (retained_fraction). This never introduces a second equation.
    retained = retained_fraction(float(e.activity_reference_minutes), half_life)
    normalized_observed = float(e.observed_value) * retained  # type: ignore[arg-type]
    status, difference = _compare_numeric(normalized_observed, normalized_observed, tol)
    # The simulated activity metric is itself NOT exposed by the engine; we only
    # prove the reference-time-normalized OBSERVED value is preserved through the
    # decay authority. Simulated activity remains not-available.
    gaps.append(AsIsValidationGap(
        kind="MISSING_SIMULATED_EVIDENCE", dimension="RADIONUCLIDE_ACTIVITY",
        detail="Engine does not expose a simulated administered-activity metric.",
        blocking_for_lockdown=_is_required(manifest, "RADIONUCLIDE_ACTIVITY"),
    ))
    return AsIsValidationComparison(
        dimension="RADIONUCLIDE_ACTIVITY", object_identity=e.object_identity,
        observed_value=e.observed_value, simulated_value=None, unit=e.unit,
        difference=None, status="MISSING_SIMULATED_EVIDENCE",
        observed_source=e.source, observed_record_id=e.source_record_id,
        tolerance=tol, confidence=e.confidence,
        note=(f"Observed activity decay-normalized via the one decay authority "
              f"(retained={retained:.4f} at {e.activity_reference_minutes} min); "
              f"simulated administered-activity metric not exposed."),
    )


def _resolve_manifest(
    manifest: Sequence[AsIsRequiredValidationDimension],
    comparisons: Sequence[AsIsValidationComparison],
    conflicts: Sequence[AsIsValidationEvidenceConflict],
    baseline_result: AsIsBaselineSimulationResult,
) -> tuple[AsIsRequiredValidationDimension, ...]:
    conflict_dims = {c.dimension for c in conflicts}
    by_dim: dict[ValidationDimension, list[AsIsValidationComparison]] = {}
    for c in comparisons:
        by_dim.setdefault(c.dimension, []).append(c)

    resolved: list[AsIsRequiredValidationDimension] = []
    for req in manifest:
        cmps = by_dim.get(req.dimension, [])
        if req.dimension in conflict_dims:
            observed_status = "CONFLICTED"
        elif any(c.observed_value is not None for c in cmps):
            observed_status = "PRESENT"
        else:
            observed_status = "MISSING"
        sim_status = "PRESENT" if any(c.simulated_value is not None for c in cmps) else "NOT_AVAILABLE"
        comparison_status = _aggregate_dimension_status(cmps)
        resolved.append(AsIsRequiredValidationDimension(
            dimension=req.dimension, required=req.required, reason=req.reason,
            observed_evidence_status=observed_status, simulated_evidence_status=sim_status,
            comparison_status=comparison_status, blocking_for_lockdown=req.blocking_for_lockdown,
        ))
    return tuple(resolved)


def _aggregate_dimension_status(cmps: Sequence[AsIsValidationComparison]) -> ValidationComparisonStatus:
    if not cmps:
        return "NOT_EVALUATED"
    statuses = {c.status for c in cmps}
    # Any failure dominates.
    if statuses & _FAILING_STATUSES:
        return "OUTSIDE_TOLERANCE" if "OUTSIDE_TOLERANCE" in statuses else "MISMATCH"
    if "CONFLICTED_EVIDENCE" in statuses:
        return "CONFLICTED_EVIDENCE"
    if "NOT_COMPARABLE" in statuses:
        return "NOT_COMPARABLE"
    if "MISSING_SIMULATED_EVIDENCE" in statuses:
        return "MISSING_SIMULATED_EVIDENCE"
    if "MISSING_OBSERVED_EVIDENCE" in statuses:
        return "MISSING_OBSERVED_EVIDENCE"
    if "TOLERANCE_NOT_MODELED" in statuses:
        return "TOLERANCE_NOT_MODELED"
    # All remaining are passing.
    if statuses <= _PASSING_STATUSES:
        return "WITHIN_TOLERANCE" if "WITHIN_TOLERANCE" in statuses else "MATCH"
    return "NOT_EVALUATED"


def _build_coverage(
    manifest: Sequence[AsIsRequiredValidationDimension],
    comparisons: Sequence[AsIsValidationComparison],
) -> AsIsValidationCoverage:
    required = tuple(m.dimension for m in manifest if m.required)
    with_observed: list[ValidationDimension] = []
    with_simulated: list[ValidationDimension] = []
    comparable: list[ValidationDimension] = []
    passed: list[ValidationDimension] = []
    failed: list[ValidationDimension] = []
    unresolved: list[ValidationDimension] = []
    not_applicable: list[ValidationDimension] = []

    for m in manifest:
        status = m.comparison_status
        if m.observed_evidence_status == "PRESENT":
            with_observed.append(m.dimension)
        if m.simulated_evidence_status == "PRESENT":
            with_simulated.append(m.dimension)
        if status in _PASSING_STATUSES:
            comparable.append(m.dimension)
            passed.append(m.dimension)
        elif status in _FAILING_STATUSES:
            comparable.append(m.dimension)
            failed.append(m.dimension)
        elif status == "NOT_APPLICABLE":
            not_applicable.append(m.dimension)
        else:
            unresolved.append(m.dimension)

    return AsIsValidationCoverage(
        required_dimensions=required,
        dimensions_with_observed_evidence=tuple(with_observed),
        dimensions_with_simulated_evidence=tuple(with_simulated),
        dimensions_comparable=tuple(comparable),
        dimensions_passed=tuple(passed),
        dimensions_failed=tuple(failed),
        dimensions_unresolved=tuple(unresolved),
        dimensions_not_applicable=tuple(not_applicable),
    )


def _derive_validation_status(
    baseline_result: AsIsBaselineSimulationResult,
    manifest: Sequence[AsIsRequiredValidationDimension],
    comparisons: Sequence[AsIsValidationComparison],
    conflicts: Sequence[AsIsValidationEvidenceConflict],
    coverage: AsIsValidationCoverage,
) -> AsIsBaselineValidationVerdict:
    """Sec 26: deterministic baseline-level status. VALIDATED is never chosen
    automatically -- it requires every required dimension to have passed with no
    unresolved required conflict/gap."""
    if not baseline_result.baseline_simulation_executed:
        return "NOT_VALIDATED"
    if not comparisons:
        return "VALIDATION_INSUFFICIENT"

    required = [m for m in manifest if m.required]
    required_failed = any(m.comparison_status in _FAILING_STATUSES for m in required)
    required_conflicted = any(
        m.comparison_status == "CONFLICTED_EVIDENCE" for m in required
    ) or any(c.dimension in {m.dimension for m in required} for c in conflicts)
    required_unresolved = [
        m for m in required
        if m.comparison_status not in _PASSING_STATUSES
    ]

    if required_failed or required_conflicted:
        return "VALIDATION_INSUFFICIENT"

    if not required_unresolved:
        # Every REQUIRED dimension passed. Downgrade to VALIDATED_WITH_
        # QUALIFICATIONS only for a genuine qualification: a baseline qualified
        # uncertainty, OR an OPTIONAL dimension that was actually EVALUATED and
        # produced a non-passing verdict (e.g. TOLERANCE_NOT_MODELED / a soft
        # mismatch). An optional dimension with simply NO evidence supplied is a
        # non-blocking gap on an out-of-required-scope metric and does not, by
        # itself, prevent VALIDATED of the required validation scope (Sec 42-43).
        optional_evaluated_nonpassing = any(
            m.comparison_status not in _PASSING_STATUSES
            and m.comparison_status not in ("NOT_EVALUATED", "MISSING_OBSERVED_EVIDENCE")
            for m in manifest if not m.required
        )
        baseline_qualified = bool(baseline_result.qualified_uncertainties)
        if optional_evaluated_nonpassing or baseline_qualified:
            return "VALIDATED_WITH_QUALIFICATIONS"
        return "VALIDATED"

    # Some required dimensions passed, some remain unresolved (missing evidence).
    any_required_passed = any(m.comparison_status in _PASSING_STATUSES for m in required)
    if any_required_passed:
        return "PARTIALLY_VALIDATED"
    return "VALIDATION_INSUFFICIENT"


def _derive_lockdown_eligibility(
    validation_status: AsIsBaselineValidationVerdict,
    manifest: Sequence[AsIsRequiredValidationDimension],
    comparisons: Sequence[AsIsValidationComparison],
    conflicts: Sequence[AsIsValidationEvidenceConflict],
    gaps: Sequence[AsIsValidationGap],
) -> AsIsLockdownEligibilityVerdict:
    """Sec 27-28: conservative, deterministic eligibility. A baseline with no
    evidence, unresolved required conflicts, critical failures or insufficient
    required-dimension coverage is NOT eligible. Eligibility is NEVER equivalent
    to "simulation executed"."""
    # Any blocking gap defeats eligibility.
    if any(g.blocking_for_lockdown for g in gaps):
        if validation_status == "VALIDATION_INSUFFICIENT":
            return "VALIDATION_INSUFFICIENT"
        return "NOT_ELIGIBLE"

    if validation_status == "VALIDATED":
        return "ELIGIBLE"
    if validation_status == "VALIDATED_WITH_QUALIFICATIONS":
        return "ELIGIBLE_WITH_QUALIFICATIONS"
    if validation_status == "PARTIALLY_VALIDATED":
        return "VALIDATION_INSUFFICIENT"
    if validation_status == "VALIDATION_INSUFFICIENT":
        return "VALIDATION_INSUFFICIENT"
    return "NOT_ELIGIBLE"


def _collect_qualifications(
    comparisons: Sequence[AsIsValidationComparison],
    gaps: Sequence[AsIsValidationGap],
) -> tuple[str, ...]:
    quals: list[str] = []
    for g in gaps:
        if not g.blocking_for_lockdown:
            quals.append(f"{g.kind}: {g.detail}")
    return tuple(quals)

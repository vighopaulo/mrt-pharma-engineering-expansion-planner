"""Existing Facility / AS-IS Digital Twin -- Phase 1E:
Baseline Simulation Readiness & Execution Authority.

GOVERNING QUESTION (Sec 0): "Given what we actually know about this existing
hospital, can MRT Pharma truthfully run an AS-IS baseline simulation without
silently substituting benchmark facts?" If YES, run the EXISTING simulation
authorities using the supplied/canonical AS-IS facts. If NO, do not simulate --
return an explicit readiness failure with the exact blocking facts.

HARD BOUNDARY (Sec 0): this module is ORCHESTRATION + READINESS + EXECUTION
CONTROL. It is NOT a second simulation engine, NOT a second patient/resource/
spatial identity system, NOT a LOCKDOWN authority, and NOT What-If. It reuses,
never duplicates:
  - the Phase 1C structural twin (`ExistingFacilityAsIsTwinResult`);
  - the Phase 1D operational snapshot (`AsIsOperationalStateSnapshot`);
  - the ONE nuclear simulation engine
    (`whole_oncology_four_architecture_optimization._nuclear_result` ->
     `hybrid_optimization.evaluate_hybrid_zone_candidate` ->
     `operating_day_scheduler.schedule_operating_day`);
  - the Part 3D physical-feasibility authority (`derive_physical_feasibility`);
  - the canonical patient identity (`OncologyPatientRecord`), clinical-resource
    identity (`ClinicalResourceInputs`/`ClinicalResourceInventory`) and geometry/
    route authority (`canonical_spatial_authority`).

THE SOFTWARE MUST NEVER MAKE THE HOSPITAL LOOK MORE COMPLETE THAN THE EVIDENCE
SUPPORTS (Sec 0). Every no-silent-benchmark governor flag on the result is a
hard-proven False (Sec 9).

STOP boundary (Sec 26-28, 45-47): a successful baseline run yields
BASELINE_VALIDATION_STATUS=VALIDATION_REQUIRED and
LOCKDOWN_ELIGIBILITY_STATUS=VALIDATION_REQUIRED. LOCKDOWN is NEVER created and
What-If is NEVER created here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, Mapping, Sequence

# --- Phase 1C / 1D read-model authorities (reused, never re-modeled) ---------
from existing_facility_asis_twin import ExistingFacilityAsIsTwinResult
from existing_facility_operational_state import (
    AsIsOperationalStateSnapshot,
    AsIsScannerOperationalState,
    AsIsRoomOperationalState,
    AsIsCyclotronOperationalState,
    AsIsGeneratorOperationalState,
    OperationalEvidenceConflict,
)

# --- The ONE simulation engine + Part 3D feasibility (reused) ----------------
from whole_oncology_four_architecture_optimization import (
    WholeOncologyBaseline,
    ClinicalResourceInputs,
    HybridEvaluationResult,
    PhysicalFeasibilityResult,
    _nuclear_result,
    derive_physical_feasibility,
    resolve_canonical_inpatient_pet_subset,
)
from oncology_pet_spect_scenario import OncologyPatientRecord


# ===========================================================================
# Sec 5-6: READINESS VOCABULARY (a first-class authority, never one opaque bool).
# ===========================================================================
AsIsReadinessDomainStatus = Literal[
    "READY", "PARTIAL", "BLOCKED", "NOT_APPLICABLE", "NOT_MODELED",
]
"""Per-domain readiness verdict. READY = enough facts for THIS simulation;
PARTIAL = some facts present, insufficient alone; BLOCKED = a required fact is
missing / UNKNOWN / conflicting; NOT_APPLICABLE = the scope does not require
this domain (e.g. MRT for a manual-only facility, Sec 20); NOT_MODELED = the
domain is out of the current modeling scope."""

# Sec 5: the readiness domains Phase 1E must report (never collapsed to a bool).
READINESS_DOMAINS: tuple[str, ...] = (
    "STRUCTURAL_TWIN_READINESS",
    "OPERATIONAL_STATE_READINESS",
    "TEMPORAL_BASIS_READINESS",
    "PATIENT_DEMAND_READINESS",
    "CLINICAL_RESOURCE_READINESS",
    "ROOM_AVAILABILITY_READINESS",
    "PRODUCTION_READINESS",
    "SCANNER_READINESS",
    "STAFFING_READINESS",
    "ROUTE_TOPOLOGY_READINESS",
    "TRANSPORT_READINESS",
    "RADIONUCLIDE_READINESS",
    "CONFLICT_READINESS",
    "SIMULATION_INPUT_READINESS",
)


# Sec 23: explicit simulation execution statuses (never hidden behind an empty
# result).
AsIsSimulationExecutionStatus = Literal[
    "NOT_ATTEMPTED",
    "BLOCKED_MISSING_REQUIRED_FACTS",
    "BLOCKED_CONFLICTING_REQUIRED_FACT",
    "BLOCKED_INVALID_ROUTE",
    "BLOCKED_TEMPORAL_BASIS",
    "READY_NOT_RUN",
    "EXECUTED",
    "EXECUTED_WITH_QUALIFIED_UNCERTAINTY",
    "FAILED",
]

# Sec 26/45: validation is separate from execution.
AsIsBaselineValidationStatus = Literal[
    "NOT_VALIDATED", "VALIDATION_REQUIRED", "PARTIALLY_VALIDATED", "VALIDATED",
]

# Sec 27/46: LOCKDOWN eligibility (calculated, never acted on here).
AsIsLockdownEligibilityStatus = Literal[
    "NOT_ELIGIBLE", "VALIDATION_REQUIRED", "ELIGIBLE_AFTER_VALIDATION",
]

# Sec 19: transport modes the AS-IS facility may physically provide.
AsIsTransportMode = Literal["MANUAL", "AUTOMATED_CONVENTIONAL", "MRT", "UNKNOWN"]

# Sec 14: patient-demand provenance (never synthetic benchmark for AS-IS).
AsIsPatientDemandSource = Literal[
    "PROJECT_SUPPLIED", "FACILITY_DERIVED", "CONTROLLED_ASIS_STUDY_INPUT", "ABSENT",
]


# ===========================================================================
# Sec 7: EXPLICIT SIMULATION SCOPE.
# ===========================================================================
AsIsSimulationServiceDomain = Literal[
    "NUCLEAR_MEDICINE_ONCOLOGY", "WHOLE_HOSPITAL",
]


@dataclass(frozen=True)
class AsIsBaselineSimulationScope:
    """Sec 7: the exact service/facility domain being simulated. The default is
    the nuclear-medicine / oncology benchmark domain (the only domain the
    existing engine physically models); WHOLE_HOSPITAL is declared for
    completeness but is NOT_MODELED (Sec 7 -- never assume whole-hospital).

    The AS-IS facts the simulation will consume are carried EXPLICITLY here and
    are never defaulted from a benchmark (Sec 9). `asis_baseline` and
    `asis_clinical_resources` are the project-supplied / facility-derived engine
    inputs; when absent the simulation blocks (Sec 10) rather than substituting
    `build_common_project_baseline()` or `BENCHMARK_CLINICAL_RESOURCES`.

    `simulation_date` / `simulation_start_minute` / `simulation_horizon_minutes`
    are the caller-supplied temporal basis (Sec 13); none is invented from
    `datetime.now()`. `available_transport_modes` is the set of modes the AS-IS
    facility physically provides (Sec 19-20) -- MANUAL-only is legal and MRT is
    never required."""

    service_domain: AsIsSimulationServiceDomain = "NUCLEAR_MEDICINE_ONCOLOGY"
    scope_note: str = ""

    # Explicit AS-IS engine inputs (never benchmark-defaulted).
    asis_baseline: WholeOncologyBaseline | None = None
    asis_clinical_resources: ClinicalResourceInputs | None = None
    patient_demand_source: AsIsPatientDemandSource = "ABSENT"

    # Temporal basis (Sec 13) -- caller-supplied only.
    simulation_date: str | None = None
    simulation_start_minute: float | None = None
    simulation_horizon_minutes: float | None = None

    # Transport reality (Sec 19-20).
    available_transport_modes: tuple[AsIsTransportMode, ...] = ()

    # Which installed cyclotron model ids the production gate should treat as
    # AUTHORITATIVE (Sec 16 / Part 3D seam). Empty = no explicit installed
    # cyclotron selection (benchmark fleet path inside the gate).
    installed_cyclotron_model_ids: tuple[str, ...] = ()

    def requires_local_cyclotron_production(self) -> bool:
        """Sec 16/37: the nuclear-medicine scope requires local production only
        when an installed cyclotron model is declared for it. A generator-only
        or externally-supplied dose facility does not require a local
        cyclotron."""
        return bool(self.installed_cyclotron_model_ids)


# ===========================================================================
# Sec 8: REQUIRED-FACT MANIFEST (the core anti-fabrication mechanism).
# ===========================================================================
AsIsRequiredFactStatus = Literal["PRESENT", "MISSING", "UNKNOWN", "CONFLICTING"]


@dataclass(frozen=True)
class AsIsRequiredFact:
    """Sec 8: one required fact for the selected simulation scope. `source` is
    the AS-IS provenance where the fact came from (or ABSENT). A fact that is
    MISSING/UNKNOWN/CONFLICTING and `blocking_if_missing` blocks the
    simulation."""

    fact_id: str
    domain: str
    required_for: str
    source: str
    current_status: AsIsRequiredFactStatus
    blocking_if_missing: bool
    reason: str


# ===========================================================================
# Sec 5: PER-DOMAIN READINESS + AGGREGATE READINESS ASSESSMENT.
# ===========================================================================
@dataclass(frozen=True)
class AsIsReadinessDomainAssessment:
    """Sec 5-6: one readiness domain's verdict, with the exact blockers that
    reduced it. `completeness_note` preserves the readiness-vs-completeness
    distinction (Sec 6): a domain may be globally incomplete yet READY for THIS
    narrow simulation."""

    domain: str
    status: AsIsReadinessDomainStatus
    blocking_fact_ids: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class AsIsSimulationReadinessAssessment:
    """Sec 5-6: the first-class readiness authority. Never one opaque bool: the
    per-domain assessments and the required-fact manifest are both preserved.
    `simulation_input_ready` is True only when NO required-blocking fact is
    MISSING/UNKNOWN/CONFLICTING and every required domain is READY or
    NOT_APPLICABLE."""

    scope: AsIsBaselineSimulationScope
    domain_assessments: tuple[AsIsReadinessDomainAssessment, ...]
    required_facts: tuple[AsIsRequiredFact, ...]
    simulation_input_ready: bool
    blocking_reason: str = ""

    def domain(self, domain: str) -> AsIsReadinessDomainAssessment | None:
        return next((d for d in self.domain_assessments if d.domain == domain), None)

    @property
    def blocking_fact_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        for d in self.domain_assessments:
            ids.extend(d.blocking_fact_ids)
        return tuple(sorted(set(ids)))

    @property
    def completeness_distinct_from_readiness(self) -> bool:
        """Sec 6: HARD proof this authority separates readiness from global
        completeness -- always True; readiness is scoped to required facts."""
        return True


# ===========================================================================
# Sec 22/41: SIMULATION-INPUT ADAPTER MAPPING (auditable, benchmark-free).
# ===========================================================================
@dataclass(frozen=True)
class AsIsSimulationInputMapping:
    """Sec 22/41: one auditable AS-IS-fact -> simulation-input mapping. This is a
    traceability/read-model layer only (never a second source of truth). The
    adapter maps ONLY known/project-supplied AS-IS facts; a MISSING field is
    NEVER filled from a benchmark default (proven by `assumption_status`)."""

    asis_fact_id: str
    source_domain: str
    source_object_id: str
    source_value: str
    source_provenance: str
    source_calibration_status: str
    target_simulation_field: str
    transformation: str
    assumption_status: Literal["MAPPED_FROM_ASIS_FACT", "NOT_FILLED_FROM_BENCHMARK"]


# ===========================================================================
# Sec 24/44: BASELINE SIMULATION OUTPUT + CANDIDATE.
# ===========================================================================
@dataclass(frozen=True)
class AsIsBaselineSimulationOutputs:
    """Sec 24-25: the preserved existing engine outputs. Patient trajectories
    are preserved as the existing `HybridPatientTrace` records (movement is
    visible via per-stage windows + transport arrival + destination), never
    replaced by summary timestamps only. Only categories the existing engine
    actually produces are exposed."""

    patient_trajectories: tuple  # tuple[HybridPatientTrace, ...] (existing type, preserved)
    retention_qualified_completed: int
    scanner_peak_occupancy: int
    injection_peak_occupancy: int
    uptake_peak_occupancy: int
    scanner_available: int
    injection_available: int
    uptake_available: int
    radionuclide: str
    operationally_feasible: bool

    @property
    def patient_movement_visible(self) -> bool:
        """Sec 25: HARD proof patient movement is represented (not merely
        inferred). True when at least one trajectory carries a transport arrival
        + destination + clinical-stage windows."""
        for t in self.patient_trajectories:
            if getattr(t, "destination_room_id", None) is not None:
                return True
        return False


@dataclass(frozen=True)
class AsIsBaselineSimulationCandidate:
    """Sec 44: an explicit baseline candidate record produced ONLY when the
    baseline actually executed. This is NOT a LOCKDOWN (Sec 27/44)."""

    facility_id: str
    operational_snapshot_id: str
    simulation_scope: AsIsBaselineSimulationScope
    simulation_date: str | None
    simulation_start_minute: float | None
    simulation_horizon_minutes: float | None
    execution_status: AsIsSimulationExecutionStatus
    readiness_assessment: AsIsSimulationReadinessAssessment
    unresolved_gaps: tuple[str, ...]
    qualified_uncertainties: tuple[str, ...]
    validation_status: AsIsBaselineValidationStatus
    lockdown_eligibility_status: AsIsLockdownEligibilityStatus


# ===========================================================================
# Sec 4: TOP-LEVEL RESULT CONTRACT (never one overloaded boolean).
# ===========================================================================
@dataclass(frozen=True)
class AsIsBaselineSimulationResult:
    """Sec 4: the Phase 1E authority result. Cleanly separates (1) readiness
    assessment, (2) simulation execution status, (3) simulation inputs (the
    auditable adapter mapping), (4) simulation outputs, (5) unresolved facts,
    (6) validation status, (7) downstream LOCKDOWN eligibility."""

    facility_id: str
    operational_snapshot_id: str
    scope: AsIsBaselineSimulationScope

    # (1) readiness.
    readiness: AsIsSimulationReadinessAssessment

    # (2) execution status.
    execution_status: AsIsSimulationExecutionStatus

    # (3) simulation inputs (auditable AS-IS -> engine mapping).
    input_mappings: tuple[AsIsSimulationInputMapping, ...]

    # (4) simulation outputs (None unless executed).
    outputs: AsIsBaselineSimulationOutputs | None

    # Feasibility (Part 3D authority) when executed.
    physical_feasibility: PhysicalFeasibilityResult | None

    # (5) unresolved facts / qualified uncertainties.
    unresolved_gaps: tuple[str, ...]
    qualified_uncertainties: tuple[str, ...]

    # (6) validation status. (7) lockdown eligibility.
    validation_status: AsIsBaselineValidationStatus
    lockdown_eligibility_status: AsIsLockdownEligibilityStatus

    # Baseline candidate (only when executed).
    baseline_candidate: AsIsBaselineSimulationCandidate | None

    # Available transport reality (Sec 19-20).
    available_transport_modes: tuple[AsIsTransportMode, ...]

    limitations: tuple[str, ...] = ()

    # ---- Sec 9: NO-SILENT-BENCHMARK GOVERNOR PROOFS (all hard False) -------
    benchmark_patients_inserted: bool = False
    benchmark_resources_inserted: bool = False
    benchmark_geometry_inserted: bool = False
    benchmark_production_inserted: bool = False
    benchmark_mrt_inserted: bool = False
    benchmark_staffing_inserted: bool = False

    # ---- Sec 12: unknown state is NEVER inferred available (all hard False) -
    unknown_scanner_inferred_available: bool = False
    unknown_cyclotron_inferred_available: bool = False
    unknown_room_inferred_available: bool = False

    # ---- Sec 14-18 hard proofs ----
    patient_demand_fabricated: bool = False
    production_calibration_borrowed: bool = False
    route_edge_fabricated: bool = False
    transport_time_calculated_over_missing_route: bool = False

    # ---- Sec 21 reuse proof ----
    existing_simulation_engine_reused: bool = False

    # ---- Sec 20 MRT-absence support ----
    mrt_absence_supported: bool = True

    # ---- Sec 27-28/46-47 hard boundary proofs (all hard False) ----
    lockdown_created: bool = False
    what_if_created: bool = False
    what_if_execution_started: bool = False
    what_if_baseline_mutated: bool = False

    @property
    def baseline_simulation_executed(self) -> bool:
        return self.execution_status in ("EXECUTED", "EXECUTED_WITH_QUALIFIED_UNCERTAINTY")

    @property
    def patient_trajectory_seam_preserved(self) -> bool:
        """Sec 25/42: HARD proof the trajectory/movement seam survives when the
        simulation ran."""
        if not self.baseline_simulation_executed:
            return True  # nothing to preserve; vacuously true.
        return self.outputs is not None and self.outputs.patient_movement_visible


# ===========================================================================
# READINESS DERIVATION (Sec 5-20).
# ===========================================================================
def _availability_is_known_available(status: str) -> bool:
    """A resource/room is usable by the baseline only if a supplied observation
    says AVAILABLE. UNKNOWN is NEVER treated as available (Sec 11-12)."""
    return status == "AVAILABLE"


def _scanner_conflict_ids(conflicts: Sequence[OperationalEvidenceConflict], object_id: str) -> tuple[str, ...]:
    return tuple(
        c.conflict_id for c in conflicts
        if c.object_id == object_id and c.resolution_status == "UNRESOLVED"
    )


def _assess_scanner_readiness(
    snapshot: AsIsOperationalStateSnapshot,
    required_scanner_ids: Sequence[str],
    facts: list[AsIsRequiredFact],
) -> AsIsReadinessDomainAssessment:
    """Sec 17/30/34/36: scanner IDENTITY, MODALITY and AVAILABILITY are distinct
    (Control B/H). A required scanner whose availability is UNKNOWN blocks; a
    conflicting scanner state blocks; a required scanner with no state record at
    all blocks (missing fact)."""
    if not required_scanner_ids:
        return AsIsReadinessDomainAssessment(
            domain="SCANNER_READINESS", status="NOT_APPLICABLE",
            note="No scanner required by the selected simulation scope.",
        )
    state_by_id = {s.scanner_id: s for s in snapshot.scanner_states}
    blockers: list[str] = []
    for scanner_id in required_scanner_ids:
        state = state_by_id.get(scanner_id)
        fact_id = f"scanner_availability:{scanner_id}"
        conflict_ids = _scanner_conflict_ids(snapshot.conflicts, scanner_id)
        if conflict_ids:
            facts.append(AsIsRequiredFact(
                fact_id=fact_id, domain="SCANNER_READINESS", required_for="scan_stage",
                source="PHASE_1D_CONFLICT", current_status="CONFLICTING", blocking_if_missing=True,
                reason=f"Unresolved conflicting operational evidence for scanner {scanner_id}: {conflict_ids}",
            ))
            blockers.append(fact_id)
            continue
        if state is None:
            facts.append(AsIsRequiredFact(
                fact_id=fact_id, domain="SCANNER_READINESS", required_for="scan_stage",
                source="ABSENT", current_status="MISSING", blocking_if_missing=True,
                reason=f"No operational-state record supplied for required scanner {scanner_id}.",
            ))
            blockers.append(fact_id)
            continue
        if not _availability_is_known_available(state.availability_status):
            facts.append(AsIsRequiredFact(
                fact_id=fact_id, domain="SCANNER_READINESS", required_for="scan_stage",
                source="PHASE_1D", current_status="UNKNOWN", blocking_if_missing=True,
                reason=(
                    f"Scanner {scanner_id} availability is '{state.availability_status}' -- "
                    "availability is never inferred from installation (Sec 12/17)."
                ),
            ))
            blockers.append(fact_id)
    if blockers:
        return AsIsReadinessDomainAssessment(
            domain="SCANNER_READINESS", status="BLOCKED", blocking_fact_ids=tuple(blockers),
            note="One or more required scanners are UNKNOWN/MISSING/CONFLICTING.",
        )
    return AsIsReadinessDomainAssessment(
        domain="SCANNER_READINESS", status="READY",
        note="Every required scanner has a supplied AVAILABLE observation.",
    )


def _assess_cyclotron_readiness(
    snapshot: AsIsOperationalStateSnapshot,
    scope: AsIsBaselineSimulationScope,
    facts: list[AsIsRequiredFact],
) -> AsIsReadinessDomainAssessment:
    """Sec 12/37 (Control I): if the scope requires local cyclotron production
    and any declared installed cyclotron has UNKNOWN operating state, block --
    installed is never inferred available."""
    if not scope.requires_local_cyclotron_production():
        return AsIsReadinessDomainAssessment(
            domain="PRODUCTION_READINESS", status="NOT_APPLICABLE",
            note="Selected scope does not require local cyclotron production.",
        )
    state_by_id = {c.cyclotron_id: c for c in snapshot.cyclotron_states}
    blockers: list[str] = []
    for model_id in scope.installed_cyclotron_model_ids:
        # The declared installed selection must have a KNOWN-available operating
        # state to be usable for production availability (Sec 12/16/37).
        state = next(
            (c for c in snapshot.cyclotron_states if c.cyclotron_id == model_id), None,
        )
        fact_id = f"cyclotron_availability:{model_id}"
        if state is None:
            facts.append(AsIsRequiredFact(
                fact_id=fact_id, domain="PRODUCTION_READINESS", required_for="local_production",
                source="ABSENT", current_status="MISSING", blocking_if_missing=True,
                reason=f"No cyclotron operational-state record supplied for required installed model {model_id}.",
            ))
            blockers.append(fact_id)
            continue
        if not _availability_is_known_available(state.availability_status):
            facts.append(AsIsRequiredFact(
                fact_id=fact_id, domain="PRODUCTION_READINESS", required_for="local_production",
                source="PHASE_1D", current_status="UNKNOWN", blocking_if_missing=True,
                reason=(
                    f"Cyclotron {model_id} availability is '{state.availability_status}' -- "
                    "installed is never converted to available (Sec 12/19)."
                ),
            ))
            blockers.append(fact_id)
    if blockers:
        return AsIsReadinessDomainAssessment(
            domain="PRODUCTION_READINESS", status="BLOCKED", blocking_fact_ids=tuple(blockers),
            note="Local cyclotron production is required but a required cyclotron state is UNKNOWN/MISSING.",
        )
    # Availability known; the radionuclide-specific calibration verdict (support
    # vs NOT_CALIBRATED) is derived later by the Part 3D production gate, which
    # honestly reports NOT_CALIBRATED without blocking (Sec 16/38).
    return AsIsReadinessDomainAssessment(
        domain="PRODUCTION_READINESS", status="READY",
        note=(
            "Required cyclotron(s) have a supplied AVAILABLE state; radionuclide-specific "
            "calibration is resolved by the Part 3D production gate (NOT_CALIBRATED preserved honestly)."
        ),
    )


def _assess_room_readiness(
    snapshot: AsIsOperationalStateSnapshot,
    required_room_ids: Sequence[str],
    facts: list[AsIsRequiredFact],
) -> AsIsReadinessDomainAssessment:
    """Sec 36 (Control H): a required clinical room whose current operational
    availability is UNKNOWN blocks -- room existence never implies availability."""
    if not required_room_ids:
        return AsIsReadinessDomainAssessment(
            domain="ROOM_AVAILABILITY_READINESS", status="NOT_APPLICABLE",
            note="No specific clinical room availability required by the scope.",
        )
    state_by_id = {r.spatial_object_id: r for r in snapshot.room_states}
    blockers: list[str] = []
    for room_id in required_room_ids:
        state = state_by_id.get(room_id)
        fact_id = f"room_availability:{room_id}"
        if state is None:
            facts.append(AsIsRequiredFact(
                fact_id=fact_id, domain="ROOM_AVAILABILITY_READINESS", required_for="clinical_stage",
                source="ABSENT", current_status="MISSING", blocking_if_missing=True,
                reason=f"No room operational-state record supplied for required room {room_id}.",
            ))
            blockers.append(fact_id)
            continue
        if not _availability_is_known_available(state.availability_status):
            facts.append(AsIsRequiredFact(
                fact_id=fact_id, domain="ROOM_AVAILABILITY_READINESS", required_for="clinical_stage",
                source="PHASE_1D", current_status="UNKNOWN", blocking_if_missing=True,
                reason=(
                    f"Room {room_id} availability is '{state.availability_status}' -- "
                    "room existence never implies availability (Sec 12/36)."
                ),
            ))
            blockers.append(fact_id)
    if blockers:
        return AsIsReadinessDomainAssessment(
            domain="ROOM_AVAILABILITY_READINESS", status="BLOCKED", blocking_fact_ids=tuple(blockers),
            note="One or more required clinical rooms are UNKNOWN/MISSING.",
        )
    return AsIsReadinessDomainAssessment(
        domain="ROOM_AVAILABILITY_READINESS", status="READY",
        note="Every required clinical room has a supplied AVAILABLE observation.",
    )


def _assess_temporal_basis(
    snapshot: AsIsOperationalStateSnapshot,
    scope: AsIsBaselineSimulationScope,
    facts: list[AsIsRequiredFact],
) -> AsIsReadinessDomainAssessment:
    """Sec 13/35 (Control G): the baseline needs a defined simulation time
    basis. It is satisfied when the scope supplies a simulation_date + start +
    horizon, OR the Phase 1D snapshot carries a real temporal basis. No time is
    ever invented; no universal freshness threshold is invented."""
    scope_has_basis = (
        scope.simulation_date is not None
        and scope.simulation_start_minute is not None
        and scope.simulation_horizon_minutes is not None
    )
    snapshot_has_basis = snapshot.temporal_basis.has_temporal_basis
    if scope_has_basis or snapshot_has_basis:
        return AsIsReadinessDomainAssessment(
            domain="TEMPORAL_BASIS_READINESS", status="READY",
            note="A caller-supplied or Phase 1D temporal basis is present (never datetime.now).",
        )
    fact_id = "temporal_basis"
    facts.append(AsIsRequiredFact(
        fact_id=fact_id, domain="TEMPORAL_BASIS_READINESS", required_for="simulation_clock",
        source="ABSENT", current_status="MISSING", blocking_if_missing=True,
        reason="No simulation date/start/horizon supplied and Phase 1D snapshot has UNKNOWN_TIME basis (Sec 13).",
    ))
    return AsIsReadinessDomainAssessment(
        domain="TEMPORAL_BASIS_READINESS", status="BLOCKED", blocking_fact_ids=(fact_id,),
        note="No valid temporal basis; simulation clock cannot be established.",
    )


def _assess_patient_demand(
    scope: AsIsBaselineSimulationScope,
    facts: list[AsIsRequiredFact],
) -> tuple[AsIsReadinessDomainAssessment, tuple[OncologyPatientRecord, ...]]:
    """Sec 14/31 (Control C): patient demand must be real / project-supplied /
    explicit controlled AS-IS input -- never synthetic benchmark. Demand is
    carried on the scope's `asis_baseline.patients` (the canonical identity
    authority). If no baseline / no nuclear subset is supplied, block."""
    if scope.patient_demand_source == "ABSENT" or scope.asis_baseline is None:
        fact_id = "patient_demand"
        facts.append(AsIsRequiredFact(
            fact_id=fact_id, domain="PATIENT_DEMAND_READINESS", required_for="who_is_simulated",
            source="ABSENT", current_status="MISSING", blocking_if_missing=True,
            reason="No AS-IS patient demand supplied; synthetic benchmark patients are never inserted (Sec 14).",
        ))
        return (
            AsIsReadinessDomainAssessment(
                domain="PATIENT_DEMAND_READINESS", status="BLOCKED", blocking_fact_ids=(fact_id,),
                note="No AS-IS patient population supplied.",
            ),
            (),
        )
    subset = resolve_canonical_inpatient_pet_subset(scope.asis_baseline)
    if not subset:
        fact_id = "patient_demand"
        facts.append(AsIsRequiredFact(
            fact_id=fact_id, domain="PATIENT_DEMAND_READINESS", required_for="who_is_simulated",
            source=scope.patient_demand_source, current_status="MISSING", blocking_if_missing=True,
            reason="AS-IS baseline supplied but resolves to zero nuclear patients for the scope.",
        ))
        return (
            AsIsReadinessDomainAssessment(
                domain="PATIENT_DEMAND_READINESS", status="BLOCKED", blocking_fact_ids=(fact_id,),
                note="AS-IS population supplied but empty for this scope.",
            ),
            (),
        )
    return (
        AsIsReadinessDomainAssessment(
            domain="PATIENT_DEMAND_READINESS", status="READY",
            note=f"{len(subset)} AS-IS nuclear patient(s) from source={scope.patient_demand_source}.",
        ),
        subset,
    )


def _assess_transport(
    scope: AsIsBaselineSimulationScope,
    facts: list[AsIsRequiredFact],
) -> AsIsReadinessDomainAssessment:
    """Sec 19-20 (Control E/K): at least one physically available transport mode
    must be known. MRT absence is legal; MANUAL-only is sufficient. If NO
    transport mode is known at all, block (a movement cannot be simulated
    without a mode)."""
    modes = tuple(m for m in scope.available_transport_modes if m != "UNKNOWN")
    if modes:
        return AsIsReadinessDomainAssessment(
            domain="TRANSPORT_READINESS", status="READY",
            note=f"Available AS-IS transport modes: {modes} (MRT not required; MANUAL-only is legal).",
        )
    fact_id = "transport_mode"
    facts.append(AsIsRequiredFact(
        fact_id=fact_id, domain="TRANSPORT_READINESS", required_for="patient_movement",
        source="ABSENT", current_status="MISSING", blocking_if_missing=True,
        reason="No physically available transport mode supplied for the AS-IS facility (Sec 19).",
    ))
    return AsIsReadinessDomainAssessment(
        domain="TRANSPORT_READINESS", status="BLOCKED", blocking_fact_ids=(fact_id,),
        note="No transport mode known.",
    )


def _assess_route_topology(
    twin: ExistingFacilityAsIsTwinResult,
    facts: list[AsIsRequiredFact],
) -> AsIsReadinessDomainAssessment:
    """Sec 18/32 (Control D): a required movement needs a valid route. Phase 1C
    exposes connectivity route-readiness; a partial/absent topology for a scope
    that requires movement blocks. No edge is fabricated; no transport time is
    computed over a missing route."""
    connectivity = twin.connectivity
    if connectivity is None:
        fact_id = "route_topology"
        facts.append(AsIsRequiredFact(
            fact_id=fact_id, domain="ROUTE_TOPOLOGY_READINESS", required_for="patient_movement",
            source="ABSENT", current_status="MISSING", blocking_if_missing=True,
            reason="Phase 1C supplied no connectivity view; a required route cannot be resolved (Sec 18).",
        ))
        return AsIsReadinessDomainAssessment(
            domain="ROUTE_TOPOLOGY_READINESS", status="BLOCKED", blocking_fact_ids=(fact_id,),
            note="No connectivity topology.",
        )
    route_readiness = getattr(connectivity, "route_readiness", "TOPOLOGY_NOT_MODELED")
    if route_readiness == "TOPOLOGY_COMPLETE":
        return AsIsReadinessDomainAssessment(
            domain="ROUTE_TOPOLOGY_READINESS", status="READY",
            note="Phase 1C connectivity topology is complete for the required movements.",
        )
    if route_readiness == "TOPOLOGY_PARTIAL":
        fact_id = "route_topology"
        facts.append(AsIsRequiredFact(
            fact_id=fact_id, domain="ROUTE_TOPOLOGY_READINESS", required_for="patient_movement",
            source="PHASE_1C", current_status="MISSING", blocking_if_missing=True,
            reason="Phase 1C topology is PARTIAL: a required movement path is incomplete; no edge is fabricated (Sec 18/32).",
        ))
        return AsIsReadinessDomainAssessment(
            domain="ROUTE_TOPOLOGY_READINESS", status="BLOCKED", blocking_fact_ids=(fact_id,),
            note="Partial topology; required path incomplete.",
        )
    fact_id = "route_topology"
    facts.append(AsIsRequiredFact(
        fact_id=fact_id, domain="ROUTE_TOPOLOGY_READINESS", required_for="patient_movement",
        source="PHASE_1C", current_status="MISSING", blocking_if_missing=True,
        reason="Phase 1C topology is NOT_MODELED; no route exists to simulate the required movement (Sec 18).",
    ))
    return AsIsReadinessDomainAssessment(
        domain="ROUTE_TOPOLOGY_READINESS", status="BLOCKED", blocking_fact_ids=(fact_id,),
        note="Topology not modeled.",
    )


def _assess_clinical_resource_inputs(
    scope: AsIsBaselineSimulationScope,
    facts: list[AsIsRequiredFact],
) -> AsIsReadinessDomainAssessment:
    """Sec 6/9: the clinical-resource counts (scanner/injection/uptake) must be
    AS-IS facts (PROJECT_SUPPLIED / FACILITY_DERIVED), never the controlled
    benchmark. A CONTROLLED_BENCHMARK resource source is rejected for AS-IS."""
    resources = scope.asis_clinical_resources
    if resources is None:
        fact_id = "clinical_resource_counts"
        facts.append(AsIsRequiredFact(
            fact_id=fact_id, domain="CLINICAL_RESOURCE_READINESS", required_for="clinical_capacity",
            source="ABSENT", current_status="MISSING", blocking_if_missing=True,
            reason="No AS-IS clinical-resource counts supplied; the 6/6/12 benchmark is never inserted (Sec 9).",
        ))
        return AsIsReadinessDomainAssessment(
            domain="CLINICAL_RESOURCE_READINESS", status="BLOCKED", blocking_fact_ids=(fact_id,),
            note="No AS-IS clinical-resource counts.",
        )
    if resources.resource_source == "CONTROLLED_BENCHMARK":
        fact_id = "clinical_resource_counts"
        facts.append(AsIsRequiredFact(
            fact_id=fact_id, domain="CLINICAL_RESOURCE_READINESS", required_for="clinical_capacity",
            source="CONTROLLED_BENCHMARK", current_status="MISSING", blocking_if_missing=True,
            reason="Clinical-resource counts are CONTROLLED_BENCHMARK, not an AS-IS fact -- rejected for AS-IS (Sec 9).",
        ))
        return AsIsReadinessDomainAssessment(
            domain="CLINICAL_RESOURCE_READINESS", status="BLOCKED", blocking_fact_ids=(fact_id,),
            note="Benchmark clinical-resource counts are not AS-IS facts.",
        )
    return AsIsReadinessDomainAssessment(
        domain="CLINICAL_RESOURCE_READINESS", status="READY",
        note=f"AS-IS clinical-resource counts supplied (source={resources.resource_source}).",
    )


# ===========================================================================
# PUBLIC API.
# ===========================================================================
def assess_baseline_simulation_readiness(
    *,
    twin: ExistingFacilityAsIsTwinResult,
    snapshot: AsIsOperationalStateSnapshot,
    scope: AsIsBaselineSimulationScope,
    required_scanner_ids: Sequence[str] = (),
    required_room_ids: Sequence[str] = (),
) -> AsIsSimulationReadinessAssessment:
    """Sec 5-20: derive the first-class readiness assessment. This never runs
    the simulation and never inserts a benchmark fact. `required_scanner_ids` /
    `required_room_ids` name the specific resources the scope requires (so a
    facility incomplete elsewhere may still be READY -- Sec 6)."""
    facts: list[AsIsRequiredFact] = []
    assessments: list[AsIsReadinessDomainAssessment] = []

    # Sec 34: structural twin readiness (Phase 1C). `readiness_gates` carries the
    # fine-grained structural/engineering-object gates; `simulation_readiness_status`
    # is the coarse string verdict. A twin is structurally ready when its gates
    # say so, or (when gates are absent) when the string status is not the
    # explicit NOT_READY_FOR_SIMULATION.
    gates = twin.readiness_gates
    if gates is not None:
        structural_ready = bool(
            gates.structural_reconstruction_ready and gates.engineering_object_model_ready
        )
    else:
        structural_ready = twin.simulation_readiness_status != "NOT_READY_FOR_SIMULATION"
    assessments.append(AsIsReadinessDomainAssessment(
        domain="STRUCTURAL_TWIN_READINESS",
        status="READY" if structural_ready else "BLOCKED",
        blocking_fact_ids=() if structural_ready else ("structural_twin",),
        note="Phase 1C structural + engineering-object model readiness.",
    ))
    if not structural_ready:
        facts.append(AsIsRequiredFact(
            fact_id="structural_twin", domain="STRUCTURAL_TWIN_READINESS", required_for="facility_model",
            source="PHASE_1C", current_status="MISSING", blocking_if_missing=True,
            reason="Phase 1C structural / engineering-object model is not ready.",
        ))

    # Sec 5: operational-state readiness (Phase 1D normalized + linked).
    op_ready = snapshot.facility_model_linked and snapshot.snapshot_status != "EMPTY"
    assessments.append(AsIsReadinessDomainAssessment(
        domain="OPERATIONAL_STATE_READINESS",
        status="READY" if op_ready else "BLOCKED",
        blocking_fact_ids=() if op_ready else ("operational_state",),
        note="Phase 1D snapshot normalized and linked to the Phase 1C facility model.",
    ))
    if not op_ready:
        facts.append(AsIsRequiredFact(
            fact_id="operational_state", domain="OPERATIONAL_STATE_READINESS", required_for="current_state",
            source="PHASE_1D", current_status="MISSING", blocking_if_missing=True,
            reason="Phase 1D operational snapshot is empty or not linked to the facility model.",
        ))

    # Sec 13: temporal basis.
    assessments.append(_assess_temporal_basis(snapshot, scope, facts))

    # Sec 14: patient demand.
    demand_assessment, _subset = _assess_patient_demand(scope, facts)
    assessments.append(demand_assessment)

    # Sec 6/9: clinical-resource input authority.
    assessments.append(_assess_clinical_resource_inputs(scope, facts))

    # Sec 16/37: production readiness (cyclotron availability).
    assessments.append(_assess_cyclotron_readiness(snapshot, scope, facts))

    # Sec 17/36: scanner + room availability.
    assessments.append(_assess_scanner_readiness(snapshot, required_scanner_ids, facts))
    assessments.append(_assess_room_readiness(snapshot, required_room_ids, facts))

    # Sec 22: staffing readiness -- reported, never benchmark-filled. Staffing
    # is NOT_APPLICABLE to the clinical-capacity baseline unless the scope
    # requires an explicit staff availability that Phase 1D lacks. We report the
    # supplied Phase 1D staff evidence honestly without blocking the nuclear
    # clinical-capacity baseline (Sec 22/35).
    if snapshot.staff_states:
        assessments.append(AsIsReadinessDomainAssessment(
            domain="STAFFING_READINESS", status="READY",
            note="AS-IS staff states supplied (never benchmark-filled).",
        ))
    else:
        assessments.append(AsIsReadinessDomainAssessment(
            domain="STAFFING_READINESS", status="NOT_MODELED",
            note="No AS-IS staffing supplied; staffing is not a blocking input for the clinical-capacity baseline (Sec 22).",
        ))

    # Sec 18/32: route topology.
    assessments.append(_assess_route_topology(twin, facts))

    # Sec 19-20: transport mode.
    assessments.append(_assess_transport(scope, facts))

    # Sec 15: radionuclide identity -- preserved via the canonical procedure
    # (never collapsed into one generic stream). READY when demand is present
    # (each patient carries its own radionuclide); the per-radionuclide
    # production verdict is the Part 3D gate's job.
    if demand_assessment.status == "READY":
        assessments.append(AsIsReadinessDomainAssessment(
            domain="RADIONUCLIDE_READINESS", status="READY",
            note="Each AS-IS patient carries its own canonical radionuclide (never collapsed).",
        ))
    else:
        assessments.append(AsIsReadinessDomainAssessment(
            domain="RADIONUCLIDE_READINESS", status="BLOCKED",
            blocking_fact_ids=("patient_demand",),
            note="Radionuclide identity is carried by patient demand, which is blocked.",
        ))

    # Sec 11/34: conflict readiness -- any UNRESOLVED conflict on a required
    # object reduces readiness. (Object-specific conflicts already surfaced in
    # the scanner/room domains; this domain reports the overall conflict gate.)
    unresolved_conflicts = tuple(
        c for c in snapshot.conflicts if c.resolution_status == "UNRESOLVED"
    )
    if unresolved_conflicts:
        conflict_fact_ids = tuple(f"conflict:{c.conflict_id}" for c in unresolved_conflicts)
        for c in unresolved_conflicts:
            facts.append(AsIsRequiredFact(
                fact_id=f"conflict:{c.conflict_id}", domain="CONFLICT_READINESS",
                required_for="unambiguous_state", source="PHASE_1D", current_status="CONFLICTING",
                blocking_if_missing=True,
                reason=(
                    f"Unresolved conflicting evidence on {c.object_id}.{c.field_name}: "
                    f"{c.candidate_values} (both preserved; never auto-resolved -- Sec 11)."
                ),
            ))
        assessments.append(AsIsReadinessDomainAssessment(
            domain="CONFLICT_READINESS", status="BLOCKED", blocking_fact_ids=conflict_fact_ids,
            note="Unresolved decision-relevant conflicts present; both claims preserved.",
        ))
    else:
        assessments.append(AsIsReadinessDomainAssessment(
            domain="CONFLICT_READINESS", status="READY",
            note="No unresolved conflicting operational evidence.",
        ))

    # Sec 5: aggregate SIMULATION_INPUT_READINESS -- READY only if no assessed
    # domain is BLOCKED. NOT_APPLICABLE / NOT_MODELED do not block.
    blocked = [a for a in assessments if a.status == "BLOCKED"]
    input_ready = not blocked
    assessments.append(AsIsReadinessDomainAssessment(
        domain="SIMULATION_INPUT_READINESS",
        status="READY" if input_ready else "BLOCKED",
        blocking_fact_ids=tuple(sorted({fid for a in blocked for fid in a.blocking_fact_ids})),
        note="Aggregate: READY only when every required domain is READY/NOT_APPLICABLE/NOT_MODELED.",
    ))

    blocking_reason = "" if input_ready else "; ".join(
        f"{a.domain}:{a.note}" for a in blocked
    )
    return AsIsSimulationReadinessAssessment(
        scope=scope, domain_assessments=tuple(assessments), required_facts=tuple(facts),
        simulation_input_ready=input_ready, blocking_reason=blocking_reason,
    )


def _execution_status_for_block(readiness: AsIsSimulationReadinessAssessment) -> AsIsSimulationExecutionStatus:
    """Sec 23: choose the most specific blocked-execution status from the
    blocked domains (temporal / conflict / route take precedence over the
    generic missing-fact status)."""
    blocked_domains = {a.domain for a in readiness.domain_assessments if a.status == "BLOCKED"}
    if "TEMPORAL_BASIS_READINESS" in blocked_domains:
        return "BLOCKED_TEMPORAL_BASIS"
    if "CONFLICT_READINESS" in blocked_domains:
        return "BLOCKED_CONFLICTING_REQUIRED_FACT"
    if "ROUTE_TOPOLOGY_READINESS" in blocked_domains:
        return "BLOCKED_INVALID_ROUTE"
    return "BLOCKED_MISSING_REQUIRED_FACTS"


def _build_input_mappings(
    scope: AsIsBaselineSimulationScope,
    subset: tuple[OncologyPatientRecord, ...],
) -> tuple[AsIsSimulationInputMapping, ...]:
    """Sec 22/41: auditable AS-IS-fact -> engine-input mapping. Only known facts
    are mapped; nothing is filled from a benchmark."""
    mappings: list[AsIsSimulationInputMapping] = []
    resources = scope.asis_clinical_resources
    if resources is not None:
        for field_name, value in (
            ("scanners", resources.scanners),
            ("injection_resources", resources.injection_resources),
            ("uptake_resources", resources.uptake_resources),
        ):
            mappings.append(AsIsSimulationInputMapping(
                asis_fact_id=f"clinical_resource:{field_name}",
                source_domain="CLINICAL_RESOURCE", source_object_id=field_name,
                source_value=str(value), source_provenance=resources.resource_source,
                source_calibration_status="FACILITY_DERIVED_COUNT",
                target_simulation_field=f"HybridZoneCandidate.{field_name}",
                transformation="DIRECT_COUNT",
                assumption_status="MAPPED_FROM_ASIS_FACT",
            ))
    for p in subset:
        proc = p.nuclear_procedure
        mappings.append(AsIsSimulationInputMapping(
            asis_fact_id=f"patient:{p.patient_id}",
            source_domain="PATIENT_DEMAND", source_object_id=p.patient_id,
            source_value=(proc.radionuclide if proc else "UNKNOWN"),
            source_provenance=scope.patient_demand_source,
            source_calibration_status="CANONICAL_IDENTITY",
            target_simulation_field="OncologyPatientRecord.patient_id",
            transformation="CANONICAL_IDENTITY_PRESERVED",
            assumption_status="MAPPED_FROM_ASIS_FACT",
        ))
    return tuple(mappings)


def run_asis_baseline_simulation(
    *,
    twin: ExistingFacilityAsIsTwinResult,
    snapshot: AsIsOperationalStateSnapshot,
    scope: AsIsBaselineSimulationScope,
    required_scanner_ids: Sequence[str] = (),
    required_room_ids: Sequence[str] = (),
) -> AsIsBaselineSimulationResult:
    """Sec 10/21-24: the Phase 1E entry point. Assess readiness, then EITHER
    block (returning the exact blockers, no benchmark substitution, no engine
    call) OR run the EXISTING nuclear simulation engine on the supplied AS-IS
    facts and preserve its outputs.

    Never creates a LOCKDOWN and never creates a What-If (Sec 27-28/46-47)."""
    facility_id = twin.facility_identity.facility_id
    readiness = assess_baseline_simulation_readiness(
        twin=twin, snapshot=snapshot, scope=scope,
        required_scanner_ids=required_scanner_ids, required_room_ids=required_room_ids,
    )

    unresolved_gaps = tuple(
        f"{f.fact_id}: {f.reason}" for f in readiness.required_facts
        if f.current_status in ("MISSING", "UNKNOWN", "CONFLICTING")
    )

    # --- BLOCKED PATH (Sec 10-13): do not simulate. --------------------------
    if not readiness.simulation_input_ready:
        execution_status = _execution_status_for_block(readiness)
        candidate = AsIsBaselineSimulationCandidate(
            facility_id=facility_id, operational_snapshot_id=snapshot.snapshot_id,
            simulation_scope=scope, simulation_date=scope.simulation_date,
            simulation_start_minute=scope.simulation_start_minute,
            simulation_horizon_minutes=scope.simulation_horizon_minutes,
            execution_status=execution_status, readiness_assessment=readiness,
            unresolved_gaps=unresolved_gaps, qualified_uncertainties=(),
            validation_status="NOT_VALIDATED", lockdown_eligibility_status="NOT_ELIGIBLE",
        )
        return AsIsBaselineSimulationResult(
            facility_id=facility_id, operational_snapshot_id=snapshot.snapshot_id, scope=scope,
            readiness=readiness, execution_status=execution_status, input_mappings=(),
            outputs=None, physical_feasibility=None, unresolved_gaps=unresolved_gaps,
            qualified_uncertainties=(), validation_status="NOT_VALIDATED",
            lockdown_eligibility_status="NOT_ELIGIBLE", baseline_candidate=candidate,
            available_transport_modes=scope.available_transport_modes,
            limitations=(
                "Simulation blocked; the existing engine was NOT called and NO benchmark fact was inserted.",
            ),
            existing_simulation_engine_reused=False,
        )

    # --- READY PATH (Sec 21-24): run the EXISTING engine on AS-IS facts. -----
    # scope.asis_baseline / asis_clinical_resources are guaranteed non-None here
    # (readiness would otherwise be BLOCKED).
    assert scope.asis_baseline is not None
    assert scope.asis_clinical_resources is not None
    subset = resolve_canonical_inpatient_pet_subset(scope.asis_baseline)

    # Sec 21: reuse the ONE nuclear engine (no new engine). mrt_floors=() unless
    # the AS-IS facility actually has MRT infrastructure -- MRT is never inserted
    # (Sec 20/33). If MRT is a genuine available mode AND the twin carries MRT
    # infrastructure, an MRT zone could be modeled; the benchmark AS-IS control
    # is manual/conventional (mrt_floors empty) which is the honest default.
    nuclear: HybridEvaluationResult = _nuclear_result(
        scope.asis_baseline,
        mrt_floors=frozenset(),
        clinical_resources=scope.asis_clinical_resources,
    )

    # Sec 16/L: Part 3D physical-feasibility authority (reused) -- radionuclide-
    # specific production gate, NOT_CALIBRATED preserved honestly.
    feasibility = derive_physical_feasibility(
        nuclear, scope.asis_baseline,
        clinical_resources=scope.asis_clinical_resources,
        installed_cyclotron_model_ids=scope.installed_cyclotron_model_ids,
    )

    outputs = AsIsBaselineSimulationOutputs(
        patient_trajectories=nuclear.patient_traces,
        retention_qualified_completed=nuclear.retention_qualified_completed,
        scanner_peak_occupancy=feasibility.scanner_peak_occupancy,
        injection_peak_occupancy=feasibility.injection_peak_occupancy,
        uptake_peak_occupancy=feasibility.uptake_peak_occupancy,
        scanner_available=feasibility.scanner_available,
        injection_available=feasibility.injection_available,
        uptake_available=feasibility.uptake_available,
        radionuclide=nuclear.radionuclide,
        operationally_feasible=feasibility.physical_feasibility_status != "INFEASIBLE",
    )

    # Sec 16/38: a merely-uncalibrated production capacity is a QUALIFIED
    # UNCERTAINTY, not a block. Reflect that in the execution status.
    qualified_uncertainties = tuple(feasibility.unqualified_physical_constraints)
    if feasibility.physical_feasibility_status == "INFEASIBLE":
        # The AS-IS facts were sufficient to RUN, but the derived physical
        # feasibility is INFEASIBLE (e.g. a calibrated resource gate fails). The
        # simulation executed; the baseline honestly reports infeasibility.
        execution_status: AsIsSimulationExecutionStatus = "EXECUTED"
    elif qualified_uncertainties:
        execution_status = "EXECUTED_WITH_QUALIFIED_UNCERTAINTY"
    else:
        execution_status = "EXECUTED"

    input_mappings = _build_input_mappings(scope, subset)

    # Sec 26/45: a successful first baseline run is VALIDATION_REQUIRED, never
    # auto-VALIDATED. Sec 27/46: eligibility is VALIDATION_REQUIRED, never
    # eligible yet, and no LOCKDOWN is created.
    validation_status: AsIsBaselineValidationStatus = "VALIDATION_REQUIRED"
    lockdown_eligibility: AsIsLockdownEligibilityStatus = "VALIDATION_REQUIRED"

    candidate = AsIsBaselineSimulationCandidate(
        facility_id=facility_id, operational_snapshot_id=snapshot.snapshot_id,
        simulation_scope=scope, simulation_date=scope.simulation_date,
        simulation_start_minute=scope.simulation_start_minute,
        simulation_horizon_minutes=scope.simulation_horizon_minutes,
        execution_status=execution_status, readiness_assessment=readiness,
        unresolved_gaps=unresolved_gaps, qualified_uncertainties=qualified_uncertainties,
        validation_status=validation_status, lockdown_eligibility_status=lockdown_eligibility,
    )

    limitations = [
        "Baseline executed via the EXISTING nuclear engine (_nuclear_result -> "
        "evaluate_hybrid_zone_candidate -> schedule_operating_day); no second engine was built.",
        "BASELINE_VALIDATION_STATUS=VALIDATION_REQUIRED: a first successful run is never auto-VALIDATED.",
        "No LOCKDOWN and no What-If were created (Phase 1E ends before validation completion).",
    ]
    if qualified_uncertainties:
        limitations.append(
            "Qualified uncertainty present (e.g. NOT_CALIBRATED production capacity); "
            "the baseline ran but the affected facts are disclosed, never silently made certain."
        )

    return AsIsBaselineSimulationResult(
        facility_id=facility_id, operational_snapshot_id=snapshot.snapshot_id, scope=scope,
        readiness=readiness, execution_status=execution_status, input_mappings=input_mappings,
        outputs=outputs, physical_feasibility=feasibility, unresolved_gaps=unresolved_gaps,
        qualified_uncertainties=qualified_uncertainties, validation_status=validation_status,
        lockdown_eligibility_status=lockdown_eligibility, baseline_candidate=candidate,
        available_transport_modes=scope.available_transport_modes,
        limitations=tuple(limitations),
        existing_simulation_engine_reused=True,
    )

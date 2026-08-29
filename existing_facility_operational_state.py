"""EXISTING FACILITY / AS-IS DIGITAL TWIN -- PHASE 1D: OPERATIONAL-STATE
RECONSTRUCTION AUTHORITY.

This module adds the NEXT DISTINCT LAYER on top of the Phase 1C AS-IS facility
ENGINEERING object model (`existing_facility_asis_twin.ExistingFacilityAsIsTwinResult`):

    Facility Evidence
          v
    Phase 1B Structured Ingestion
          v
    Phase 1C AS-IS Facility Engineering Object Model
          v
    >>> PHASE 1D OPERATIONAL-STATE RECONSTRUCTION <<<  (this module)
          v
    [FUTURE] Baseline Simulation
          v
    [FUTURE] Validation
          v
    [FUTURE] LOCKDOWN
          v
    [FUTURE] What-If

CORE INVARIANT (Sec 4): STRUCTURAL MODEL != OPERATIONAL STATE.

    A scanner that EXISTS structurally (Phase 1C) is NOT the same fact as a
    scanner that is AVAILABLE now. A cyclotron that is INSTALLED is NOT the same
    fact as a cyclotron PRODUCING today. A room that EXISTS is NOT a room that is
    AVAILABLE. A patient that EXISTS is NOT a patient that is SCHEDULED. A staff
    CATEGORY that exists is NOT staff AVAILABLE now.

Phase 1D reconstructs operational state ONLY from explicitly supplied structured
facts. Missing operational-state facts remain UNKNOWN / NOT_MODELED / NOT_OBSERVED
/ NOT_CALIBRATED / STALE -- NEVER silently completed from a benchmark, and NEVER
inferred from structural installation.

DOCTRINE (Sec 0):
  * The PHYSICAL Phase 1C model is authoritative. This module does NOT rebuild it,
    does NOT create a second facility/patient/scanner/cyclotron/generator/scheduling
    authority, and references canonical identities rather than duplicating them.
  * NO baseline simulation is run here (Sec 31-32). This module PRODUCES the
    snapshot a future baseline simulation will consume; it does not consume it.
  * NO LOCKDOWN / What-If is created here (Sec 33). The existing
    `lockdown_what_if_lineage_authority` seam is preserved, never duplicated.
  * NO live API / RIS / PACS / EHR / ARIA / BMS integration (Sec 34). Structured,
    project-supplied operational facts ONLY.
  * NO architecture ranking / economics / equal-budget / crossover (Sec 44).

All reused vocabulary (provenance / calibration / confidence / domain-status) is
imported from the Phase 1C authority, and equipment operating-state vocabularies
are imported from the existing catalogs -- this module invents NO second hierarchy
of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

# ---- Phase 1C authority: reused, never re-modeled. ----
from existing_facility_asis_twin import (
    AsIsCalibration,
    AsIsConfidence,
    AsIsDomainStatus,
    AsIsProvenance,
    ExistingFacilityAsIsTwinResult,
)

# ---- Existing catalog operating-state vocabularies: reused verbatim (Sec 17-20). ----
from cyclotron_catalog import CyclotronOperatingState
from generator_catalog import GeneratorOperatingState
from scanner_catalog import ScannerOperatingState

# ===========================================================================
# Sec 8: OPERATIONAL-STATE SOURCE TYPES.
# Only the STRUCTURED / project-supplied forms are implemented in this build.
# Real APIs / live feeds are explicitly out of scope (Sec 8/34).
# ===========================================================================
OperationalStateSource = Literal[
    "PROJECT_SUPPLIED",       # a structured project-supplied operational fact
    "FACILITY_DERIVED",       # derived from another supplied facility fact
    "MANUAL_ENTRY",           # a human-entered structured fact
    "SCHEDULE_DERIVED",       # taken from a supplied schedule fact
    "CONTROLLED_ASSUMPTION",  # an explicit, labeled controlled assumption
    "NOT_OBSERVED",           # no operational observation was supplied at all
]

# Sec 5/6: temporal basis kind of a snapshot. A snapshot may represent NOW, a
# historical point-in-time, or a future planned state -- ONLY when explicitly
# supplied. `UNKNOWN_TIME` is used when the caller supplied facts but no time.
SnapshotTemporalKind = Literal[
    "NOW", "HISTORICAL_POINT_IN_TIME", "FUTURE_PLANNED_STATE", "UNKNOWN_TIME",
]

SnapshotStatus = Literal["NORMALIZED", "PARTIAL", "CONFLICTED", "EMPTY"]

# ===========================================================================
# Sec 10/17-20: OPERATIONAL STATUS VOCABULARIES.
# Resource-class-specific operating states REUSE the existing catalog enums;
# room / patient / appointment / staff / production states use the physically
# justified repository-consistent vocabularies below. UNKNOWN is first-class
# everywhere -- absence of an observation is a real, preserved state.
# ===========================================================================

# Generic availability axis (Sec 10). Distinct from operating-state: a resource
# may have a known operating-state yet an UNKNOWN availability, and vice versa.
OperationalAvailabilityStatus = Literal["AVAILABLE", "UNAVAILABLE", "UNKNOWN"]

# Sec 12: room operational occupancy -- separate axis from geometry/classification.
RoomOccupancyStatus = Literal[
    "AVAILABLE", "OCCUPIED", "CLEANING", "RESERVED", "OUT_OF_SERVICE", "UNKNOWN",
]

# Sec 17: scanner current state -- reuse the scanner catalog vocabulary, with an
# explicit UNKNOWN for "installed but no operational observation supplied".
ScannerOperationalStatus = Literal[
    "AVAILABLE", "IN_USE", "RESERVED", "MAINTENANCE", "OUT_OF_SERVICE", "UNKNOWN",
]

# Sec 18: cyclotron current production state -- reuse the cyclotron catalog
# vocabulary, plus UNKNOWN for "installed but no production observation supplied".
CyclotronOperationalStatus = Literal[
    "AVAILABLE", "IRRADIATING", "SYNTHESIS_IN_PROGRESS", "RELEASE_PENDING",
    "OUT_OF_SERVICE", "UNKNOWN",
]

# Sec 20: generator current state -- reuse the generator catalog vocabulary.
GeneratorOperationalStatus = Literal[
    "AVAILABLE", "ELUTING", "ELUTED_AWAITING_USE", "MAINTENANCE", "OUT_OF_SERVICE",
    "EXPIRED", "UNKNOWN",
]

# Sec 14: patient operational care-state (never fabricated).
PatientCareState = Literal[
    "PRESENT_IN_FACILITY", "ARRIVED", "NOT_ARRIVED", "IN_PROCEDURE", "DISCHARGED", "UNKNOWN",
]

# Sec 15/16: whether a patient is scheduled today. UNKNOWN != NOT_SCHEDULED --
# absence of an appointment is not a claim of "definitely not scheduled".
PatientScheduledStatus = Literal["SCHEDULED", "NOT_SCHEDULED", "UNKNOWN"]

# Sec 16: appointment status projection (thin -- no second calendar authority).
AppointmentStatus = Literal[
    "BOOKED", "CHECKED_IN", "IN_PROGRESS", "COMPLETED", "CANCELLED", "NO_SHOW", "UNKNOWN",
]

# Sec 21: production/batch/release current status (facts preserved, never recomputed).
ProductionReleaseStatus = Literal[
    "IN_PRODUCTION", "AWAITING_RELEASE", "RELEASED", "REJECTED", "UNKNOWN",
]

# Sec 26: freshness -- NO universal timeout invented. Staleness is only declared
# when an explicit, resource-specific threshold was supplied.
FreshnessStatus = Literal["CURRENT", "STALE", "UNKNOWN_FRESHNESS", "NOT_APPLICABLE"]

# Sec 27-28: operational validation of a single fact.
OperationalValidationStatus = Literal["VALIDATED", "UNVALIDATED", "CONFLICTED"]

# Sec 29-30: operational completeness domains.
OperationalCompletenessDomain = Literal[
    "SNAPSHOT_IDENTITY",
    "TEMPORAL_BASIS",
    "FACILITY_MODEL_LINKAGE",
    "ROOM_OPERATIONAL_STATE",
    "SCANNER_OPERATIONAL_STATE",
    "CYCLOTRON_OPERATIONAL_STATE",
    "GENERATOR_OPERATIONAL_STATE",
    "MRT_OPERATIONAL_STATE",
    "PATIENT_STATE",
    "APPOINTMENT_STATE",
    "STAFF_RESOURCE_STATE",
    "PRODUCTION_BATCH_STATE",
    "PROVENANCE",
    "FRESHNESS",
    "EVIDENCE_CONFLICTS",
    "BASELINE_SIMULATION_INPUT_READINESS",
]


# ===========================================================================
# Sec 6: TEMPORAL BASIS.
# Timestamps are ISO-8601 strings exactly as supplied -- this module NEVER reads
# the wall clock and NEVER invents a timestamp (Sec 6).
# ===========================================================================
@dataclass(frozen=True)
class OperationalTemporalBasis:
    """Sec 6: the explicit temporal basis of a snapshot / fact. Every field is
    the value SUPPLIED by the caller; none is defaulted from `datetime.now()`.
    A snapshot with no supplied time is `UNKNOWN_TIME` (Sec 6) -- never silently
    stamped with the current clock."""

    kind: SnapshotTemporalKind = "UNKNOWN_TIME"
    effective_at: str | None = None
    observed_at: str | None = None
    source_updated_at: str | None = None
    ingested_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None

    @property
    def has_temporal_basis(self) -> bool:
        """Sec 6/31: a snapshot has a usable temporal basis only if at least one
        real timestamp was supplied AND the kind is not UNKNOWN_TIME."""
        return self.kind != "UNKNOWN_TIME" and any(
            t is not None for t in (self.effective_at, self.observed_at, self.source_updated_at,
                                    self.valid_from, self.valid_until)
        )


# ===========================================================================
# Sec 25: FIELD-LEVEL OPERATIONAL EVIDENCE (independent axes -- reuses Phase 1C
# provenance/calibration/confidence, adds operational source + freshness).
# ===========================================================================
@dataclass(frozen=True)
class OperationalEvidence:
    """Sec 25: field-level operational evidence. Origin (`source`/`provenance`),
    calibration, confidence, temporal basis and freshness are INDEPENDENT axes,
    exactly like Phase 1C's `AsIsFieldEvidence`. A PROJECT_SUPPLIED fact may still
    be NOT_CALIBRATED and UNKNOWN_FRESHNESS simultaneously."""

    fact: str
    source: OperationalStateSource
    provenance: AsIsProvenance = "PROJECT_SUPPLIED"
    calibration: AsIsCalibration = "NOT_APPLICABLE"
    confidence: AsIsConfidence = "unknown"
    temporal_basis: OperationalTemporalBasis = field(default_factory=OperationalTemporalBasis)
    freshness_status: FreshnessStatus = "UNKNOWN_FRESHNESS"
    note: str | None = None


# ===========================================================================
# Sec 27-28: OPERATIONAL EVIDENCE CONFLICT (reuses Phase 1C conflict doctrine).
# Both candidates preserved; NEVER last-write-wins / averaged / auto-resolved.
# ===========================================================================
@dataclass(frozen=True)
class OperationalEvidenceConflict:
    """Sec 27-28: two independently sourced operational facts disagree about ONE
    field of ONE object at the SAME effective time. Both candidate statuses are
    preserved; identity is preserved; NEITHER is silently chosen. An UNRESOLVED
    conflict REDUCES readiness for the affected domain (Sec 27)."""

    conflict_id: str
    domain: OperationalCompletenessDomain
    object_id: str
    field_name: str
    effective_at: str | None
    candidate_values: tuple[str, ...]
    candidate_sources: tuple[OperationalStateSource, ...]
    resolution_status: Literal["UNRESOLVED", "RESOLVED_BY_PROJECT_AUTHORITY"] = "UNRESOLVED"
    impact_on_readiness: Literal["NONE", "REDUCES_READINESS"] = "REDUCES_READINESS"


# ===========================================================================
# Sec 10: GENERIC RESOURCE OPERATIONAL STATE.
# References canonical equipment/resource IDs -- never duplicates catalog identity.
# ===========================================================================
@dataclass(frozen=True)
class AsIsResourceOperationalState:
    """Sec 10-11: a generic resource operational-state read-model. `resource_id`
    references a CANONICAL identity already owned elsewhere (catalog instance id,
    ClinicalResource id, spatial object id). `structural_identity_status` records
    that Phase 1C knows the resource exists; `operational_status`/`availability_status`
    are INDEPENDENT and default to UNKNOWN when no observation was supplied --
    availability is NEVER inferred from installation (Sec 11)."""

    resource_id: str
    resource_class: Literal[
        "SCANNER", "CYCLOTRON", "GENERATOR", "CLINICAL_ROOM", "STAFF", "MRT", "OTHER",
    ]
    structural_identity_status: Literal["IDENTITY_PRESENT", "IDENTITY_ABSENT"]
    operational_status: str = "UNKNOWN"
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    current_assignment: str | None = None
    location_id: str | None = None
    evidence: OperationalEvidence | None = None
    validation_status: OperationalValidationStatus = "UNVALIDATED"

    @property
    def availability_inferred_from_installation(self) -> bool:
        """Sec 11: HARD proof this module NEVER converts INSTALLED -> AVAILABLE.
        Always False -- availability comes only from a supplied observation."""
        return False


# ===========================================================================
# Sec 12: ROOM OPERATIONAL STATE (separate read-model; never mutates geometry
# or clinical classification).
# ===========================================================================
@dataclass(frozen=True)
class AsIsRoomOperationalState:
    """Sec 12-13: room occupancy/availability, held on its OWN axis. Room
    geometry, identity and clinical classification (Phase 1C) are NOT touched.
    Occupancy defaults to UNKNOWN when no evidence is supplied (Sec 13) --
    room existence NEVER implies availability, and no patient is inserted."""

    spatial_object_id: str
    occupancy_status: RoomOccupancyStatus = "UNKNOWN"
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    reservation_status: Literal["RESERVED", "NOT_RESERVED", "UNKNOWN"] = "UNKNOWN"
    current_patient_id: str | None = None
    evidence: OperationalEvidence | None = None

    @property
    def availability_inferred_from_existence(self) -> bool:
        """Sec 13: HARD proof ROOM EXISTS is never converted to ROOM AVAILABLE."""
        return False


# ===========================================================================
# Sec 17: SCANNER OPERATIONAL STATE (identity/modality/placement kept distinct
# from current availability/assignment).
# ===========================================================================
@dataclass(frozen=True)
class AsIsScannerOperationalState:
    """Sec 17: scanner current state. `scanner_id` references a canonical scanner
    identity (Phase 1C engineering object / scanner catalog instance). Modality
    and placement are structural facts NOT re-modeled here; only current
    availability/assignment. `catalog_operating_state` optionally carries the
    exact `scanner_catalog.ScannerOperatingState` when supplied."""

    scanner_id: str
    structural_identity_status: Literal["IDENTITY_PRESENT", "IDENTITY_ABSENT"]
    operational_status: ScannerOperationalStatus = "UNKNOWN"
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    current_assignment: str | None = None
    catalog_operating_state: ScannerOperatingState | None = None
    evidence: OperationalEvidence | None = None

    @property
    def availability_inferred_from_installation(self) -> bool:
        return False


# ===========================================================================
# Sec 18-19: CYCLOTRON OPERATIONAL STATE. Installed identity stays SEPARATE from
# today's production. NOTHING about today's radionuclide/batch/EOB is inferred
# merely because the model supports those radionuclides (Sec 18).
# ===========================================================================
@dataclass(frozen=True)
class AsIsCyclotronOperationalState:
    """Sec 18-19: cyclotron current production state. When no production
    observation is supplied, `operational_status` is UNKNOWN and
    `current_radionuclide`/`current_batch_id`/`current_eob_activity_mbq` are
    None / NOT_MODELED -- never fabricated from radionuclide SUPPORT (Sec 19)."""

    cyclotron_id: str
    structural_identity_status: Literal["IDENTITY_PRESENT", "IDENTITY_ABSENT"]
    operational_status: CyclotronOperationalStatus = "UNKNOWN"
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    current_radionuclide: str | None = None
    current_batch_id: str | None = None
    current_eob_activity_mbq: float | Literal["NOT_MODELED"] = "NOT_MODELED"
    catalog_operating_state: CyclotronOperatingState | None = None
    evidence: OperationalEvidence | None = None

    @property
    def production_state_fabricated(self) -> bool:
        """Sec 19: HARD proof no current production is invented. Always False."""
        return False


# ===========================================================================
# Sec 20: GENERATOR OPERATIONAL STATE (distinct from current daughter activity /
# last-elution / next-elution / remaining life -- none fabricated when absent).
# ===========================================================================
@dataclass(frozen=True)
class AsIsGeneratorOperationalState:
    """Sec 20: generator current state. Elution facts are preserved only when
    supplied; available daughter activity is NOT_MODELED unless explicitly given.
    Existing generator calibration boundaries are preserved (no recomputation)."""

    generator_id: str
    structural_identity_status: Literal["IDENTITY_PRESENT", "IDENTITY_ABSENT"]
    operational_status: GeneratorOperationalStatus = "UNKNOWN"
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    last_elution_at: str | None = None
    next_elution_at: str | None = None
    available_daughter_activity_mbq: float | Literal["NOT_MODELED"] = "NOT_MODELED"
    catalog_operating_state: GeneratorOperatingState | None = None
    evidence: OperationalEvidence | None = None

    @property
    def generator_state_fabricated(self) -> bool:
        return False


# ===========================================================================
# Sec 14: PATIENT OPERATIONAL STATE (references CANONICAL patient identity --
# never a second/anonymous patient authority).
# ===========================================================================
@dataclass(frozen=True)
class AsIsPatientOperationalState:
    """Sec 14-15: patient operational-state view over the CANONICAL patient
    identity (`oncology_pet_spect_scenario.OncologyPatientRecord.patient_id`).
    `care_state`/`scheduled_status`/current location/procedure stage are set only
    from supplied facts. A patient with no supplied appointment is NOT SCHEDULED
    (or UNKNOWN) -- an appointment is NEVER fabricated (Sec 15)."""

    patient_id: str
    care_state: PatientCareState = "UNKNOWN"
    scheduled_status: PatientScheduledStatus = "UNKNOWN"
    radionuclide: str | None = None
    current_location_id: str | None = None
    patient_type: Literal["INPATIENT", "OUTPATIENT", "UNKNOWN"] = "UNKNOWN"
    appointment_ids: tuple[str, ...] = ()
    current_procedure_stage: Literal["INJECTION", "UPTAKE", "SCANNER", "NONE", "UNKNOWN"] = "UNKNOWN"
    evidence: OperationalEvidence | None = None
    validation_status: OperationalValidationStatus = "UNVALIDATED"


# ===========================================================================
# Sec 16: APPOINTMENT STATE (thin projection -- NOT a second calendar authority).
# Created ONLY from a supplied appointment fact, NEVER from patient existence.
# ===========================================================================
@dataclass(frozen=True)
class AsIsAppointmentOperationalState:
    """Sec 16: a thin appointment-state projection. This module owns NO calendar
    authority; it references canonical patient/resource/room ids and preserves the
    supplied schedule facts. Time fields are supplied strings, never invented."""

    appointment_id: str
    patient_id: str
    resource_id: str | None = None
    room_id: str | None = None
    scheduled_start: str | None = None
    scheduled_end: str | None = None
    radionuclide: str | None = None
    appointment_status: AppointmentStatus = "UNKNOWN"
    evidence: OperationalEvidence | None = None


# ===========================================================================
# Sec 22: STAFF / RESOURCE STATE (category identity / count / person identity are
# THREE separate certainty levels; never populated from a benchmark staffing table).
# ===========================================================================
@dataclass(frozen=True)
class AsIsStaffResourceOperationalState:
    """Sec 22: staffing availability where explicitly supplied. `staff_category`
    identity, `available_count`, and `person_ids` (actual person identity) are
    kept at SEPARATE levels of certainty. A count is NEVER converted into people
    unless real person identity is supplied. Never benchmark-filled."""

    staff_category: Literal[
        "PORTER", "TECHNOLOGIST", "NUCLEAR_MEDICINE", "RADIOPHARMACY", "MRT_OPERATIONS", "OTHER",
    ]
    category_identity_present: bool
    available_count: int | Literal["UNKNOWN"] = "UNKNOWN"
    person_ids: tuple[str, ...] = ()
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    evidence: OperationalEvidence | None = None

    @property
    def staffing_benchmark_inserted(self) -> bool:
        """Sec 22/35: HARD proof staffing is never benchmark-filled. Always False."""
        return False


# ===========================================================================
# Sec 21: PRODUCTION / BATCH / RELEASE STATE (facts preserved only; no recompute,
# no decay compensation, no missing-activity estimation).
# ===========================================================================
@dataclass(frozen=True)
class AsIsProductionBatchOperationalState:
    """Sec 21: a supplied current production/batch/release fact. `batch_id`,
    radionuclide, source id, stage, EOB/release times and current activity are
    preserved EXACTLY as supplied. This module NEVER recalculates production,
    estimates missing activity, or runs decay compensation (Sec 21)."""

    batch_id: str
    radionuclide: str | None = None
    source_id: str | None = None
    production_stage: Literal[
        "IRRADIATION", "SYNTHESIS", "QC", "RELEASED", "DISTRIBUTED", "UNKNOWN",
    ] = "UNKNOWN"
    eob_at: str | None = None
    release_at: str | None = None
    current_activity_mbq: float | Literal["NOT_MODELED"] = "NOT_MODELED"
    release_status: ProductionReleaseStatus = "UNKNOWN"
    destination_id: str | None = None
    evidence: OperationalEvidence | None = None

    @property
    def production_recalculated(self) -> bool:
        """Sec 21: HARD proof no production math is run here. Always False."""
        return False


# ===========================================================================
# Sec 29-30: OPERATIONAL DOMAIN COMPLETENESS (never collapsed to one count).
# ===========================================================================
@dataclass(frozen=True)
class AsIsOperationalDomainCompleteness:
    """Sec 30: frozen per-domain operational-completeness assessment."""

    domain: OperationalCompletenessDomain
    status: AsIsDomainStatus
    known_count: int = 0
    unknown_count: int = 0
    conflict_count: int = 0
    blocking_gap_count: int = 0
    nonblocking_gap_count: int = 0
    readiness_impact: Literal["NONE", "NONBLOCKING", "BLOCKING"] = "NONE"
    evidence_summary: str | None = None


# ===========================================================================
# Sec 31: BASELINE SIMULATION INPUT READINESS (determined, NEVER run).
# ===========================================================================
@dataclass(frozen=True)
class AsIsBaselineSimulationInputReadiness:
    """Sec 31-32: whether enough operational state exists to ATTEMPT a baseline
    simulation. Distinct sub-gates; requiredness is physically justified, not
    "every domain always required". The simulation is NEVER run here."""

    facility_model_ready: bool
    operational_snapshot_normalized: bool
    resource_state_ready: bool
    patient_appointment_state_ready: bool
    production_state_ready: bool
    baseline_simulation_input_ready: bool
    # Sec 32: hard out-of-scope proof flags -- always False.
    baseline_simulation_run: bool = False


# ===========================================================================
# Sec 5/7: TOP-LEVEL OPERATIONAL-STATE SNAPSHOT (frozen read-model).
# Snapshot identity is INDEPENDENT of facility / scenario / LOCKDOWN / What-If
# identity (Sec 7): same facility + different effective time -> different
# snapshot, without duplicating the underlying facility engineering model.
# ===========================================================================
@dataclass(frozen=True)
class AsIsOperationalStateSnapshot:
    """Sec 5: the reconstructed operational-state read model. It LINKS to the
    Phase 1C facility model by `facility_id` (a reference, not a copy) and holds
    the per-domain operational states, completeness, conflicts, freshness and
    baseline-simulation-input readiness. It is explicitly NOT a LOCKDOWN and NOT
    a simulation output (see the seam flags)."""

    snapshot_id: str
    facility_id: str
    project_starting_state: str
    temporal_basis: OperationalTemporalBasis
    snapshot_status: SnapshotStatus
    facility_model_linked: bool

    resource_states: tuple[AsIsResourceOperationalState, ...] = ()
    room_states: tuple[AsIsRoomOperationalState, ...] = ()
    scanner_states: tuple[AsIsScannerOperationalState, ...] = ()
    cyclotron_states: tuple[AsIsCyclotronOperationalState, ...] = ()
    generator_states: tuple[AsIsGeneratorOperationalState, ...] = ()
    patient_states: tuple[AsIsPatientOperationalState, ...] = ()
    appointment_states: tuple[AsIsAppointmentOperationalState, ...] = ()
    staff_states: tuple[AsIsStaffResourceOperationalState, ...] = ()
    production_states: tuple[AsIsProductionBatchOperationalState, ...] = ()

    conflicts: tuple[OperationalEvidenceConflict, ...] = ()
    domain_completeness: tuple[AsIsOperationalDomainCompleteness, ...] = ()
    baseline_simulation_readiness: AsIsBaselineSimulationInputReadiness | None = None
    limitations: tuple[str, ...] = ()

    # ---- Sec 23/35/42: MRT operational count (0 when the facility has no MRT). ----
    mrt_operational_resource_count: int = 0

    # ---- Sec 32-34/44: hard out-of-scope disclosure flags (all False/True as noted). ----
    asis_baseline_simulation_implemented: bool = False
    simulation_run_during_phase_1d: bool = False
    four_architecture_simulation_called: bool = False
    part3d_feasibility_called: bool = False
    part3e_optimization_called: bool = False
    part3e1_experiments_called: bool = False
    part3e2_decision_envelope_called: bool = False
    lockdown_created: bool = False
    what_if_created: bool = False
    lockdown_authority_duplicated: bool = False
    existing_lockdown_lineage_seam_preserved: bool = True
    live_hospital_api_implemented: bool = False
    aria_live_ingestion_implemented: bool = False
    ris_live_ingestion_implemented: bool = False
    pacs_live_ingestion_implemented: bool = False
    ehr_live_ingestion_implemented: bool = False
    staff_system_live_ingestion_implemented: bool = False
    facility_bms_live_ingestion_implemented: bool = False
    architecture_ranking_performed: bool = False
    economic_optimization_performed: bool = False

    # ---- Sec 35: no-silent-benchmark governor proofs (all always False). ----
    benchmark_patient_population_inserted: bool = False
    benchmark_appointments_inserted: bool = False
    benchmark_scanner_availability_inserted: bool = False
    benchmark_cyclotron_availability_inserted: bool = False
    benchmark_generator_availability_inserted: bool = False
    benchmark_staffing_inserted: bool = False
    benchmark_production_schedule_inserted: bool = False
    benchmark_radionuclide_demand_inserted: bool = False
    benchmark_room_occupancy_inserted: bool = False
    benchmark_mrt_operational_resource_inserted: bool = False

    def domain(self, domain: OperationalCompletenessDomain) -> AsIsOperationalDomainCompleteness | None:
        return next((d for d in self.domain_completeness if d.domain == domain), None)

    @property
    def benchmark_mrt_operational_inserted(self) -> bool:
        """Sec 42: HARD proof -- an MRT operational network is NEVER inserted."""
        return False


# ===========================================================================
# Sec 9: STRUCTURED OPERATIONAL-STATE INPUT DTOs (temporary ingestion contracts).
# Every category is OPTIONAL -- a complete live dataset is NEVER required (Sec 9).
# ===========================================================================
@dataclass(frozen=True)
class ResourceStateInput:
    resource_id: str
    resource_class: Literal["SCANNER", "CYCLOTRON", "GENERATOR", "CLINICAL_ROOM", "STAFF", "MRT", "OTHER"]
    operational_status: str = "UNKNOWN"
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    current_assignment: str | None = None
    location_id: str | None = None
    source: OperationalStateSource = "PROJECT_SUPPLIED"
    effective_at: str | None = None
    observed_at: str | None = None
    source_updated_at: str | None = None
    freshness_threshold_minutes: float | None = None


@dataclass(frozen=True)
class RoomStateInput:
    spatial_object_id: str
    occupancy_status: RoomOccupancyStatus = "UNKNOWN"
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    reservation_status: Literal["RESERVED", "NOT_RESERVED", "UNKNOWN"] = "UNKNOWN"
    current_patient_id: str | None = None
    source: OperationalStateSource = "PROJECT_SUPPLIED"
    effective_at: str | None = None


@dataclass(frozen=True)
class ScannerStateInput:
    scanner_id: str
    operational_status: ScannerOperationalStatus = "UNKNOWN"
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    current_assignment: str | None = None
    catalog_operating_state: ScannerOperatingState | None = None
    source: OperationalStateSource = "PROJECT_SUPPLIED"
    effective_at: str | None = None


@dataclass(frozen=True)
class CyclotronStateInput:
    cyclotron_id: str
    operational_status: CyclotronOperationalStatus = "UNKNOWN"
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    current_radionuclide: str | None = None
    current_batch_id: str | None = None
    current_eob_activity_mbq: float | None = None
    catalog_operating_state: CyclotronOperatingState | None = None
    source: OperationalStateSource = "PROJECT_SUPPLIED"
    effective_at: str | None = None


@dataclass(frozen=True)
class GeneratorStateInput:
    generator_id: str
    operational_status: GeneratorOperationalStatus = "UNKNOWN"
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    last_elution_at: str | None = None
    next_elution_at: str | None = None
    available_daughter_activity_mbq: float | None = None
    catalog_operating_state: GeneratorOperatingState | None = None
    source: OperationalStateSource = "PROJECT_SUPPLIED"
    effective_at: str | None = None


@dataclass(frozen=True)
class PatientStateInput:
    patient_id: str
    care_state: PatientCareState = "UNKNOWN"
    scheduled_status: PatientScheduledStatus = "UNKNOWN"
    radionuclide: str | None = None
    current_location_id: str | None = None
    patient_type: Literal["INPATIENT", "OUTPATIENT", "UNKNOWN"] = "UNKNOWN"
    appointment_ids: tuple[str, ...] = ()
    current_procedure_stage: Literal["INJECTION", "UPTAKE", "SCANNER", "NONE", "UNKNOWN"] = "UNKNOWN"
    source: OperationalStateSource = "PROJECT_SUPPLIED"
    effective_at: str | None = None


@dataclass(frozen=True)
class AppointmentStateInput:
    appointment_id: str
    patient_id: str
    resource_id: str | None = None
    room_id: str | None = None
    scheduled_start: str | None = None
    scheduled_end: str | None = None
    radionuclide: str | None = None
    appointment_status: AppointmentStatus = "UNKNOWN"
    source: OperationalStateSource = "SCHEDULE_DERIVED"
    effective_at: str | None = None


@dataclass(frozen=True)
class StaffStateInput:
    staff_category: Literal["PORTER", "TECHNOLOGIST", "NUCLEAR_MEDICINE", "RADIOPHARMACY", "MRT_OPERATIONS", "OTHER"]
    available_count: int | None = None
    person_ids: tuple[str, ...] = ()
    availability_status: OperationalAvailabilityStatus = "UNKNOWN"
    source: OperationalStateSource = "PROJECT_SUPPLIED"
    effective_at: str | None = None


@dataclass(frozen=True)
class ProductionBatchStateInput:
    batch_id: str
    radionuclide: str | None = None
    source_id: str | None = None
    production_stage: Literal["IRRADIATION", "SYNTHESIS", "QC", "RELEASED", "DISTRIBUTED", "UNKNOWN"] = "UNKNOWN"
    eob_at: str | None = None
    release_at: str | None = None
    current_activity_mbq: float | None = None
    release_status: ProductionReleaseStatus = "UNKNOWN"
    destination_id: str | None = None
    source: OperationalStateSource = "PROJECT_SUPPLIED"
    effective_at: str | None = None


@dataclass(frozen=True)
class ConflictingOperationalStateInput:
    """Sec 27-28: a SECOND, independently sourced operational fact about an
    already-supplied object/field at the SAME effective time. Supplying one
    creates a deterministic conflict control -- both candidates preserved,
    readiness reduced, never auto-resolved."""

    domain: OperationalCompletenessDomain
    object_id: str
    field_name: str
    candidate_value: str
    source: OperationalStateSource = "MANUAL_ENTRY"
    effective_at: str | None = None


@dataclass(frozen=True)
class AsIsStructuredOperationalStateInput:
    """Sec 9: the top-level structured operational-state ingestion contract.
    Every category is OPTIONAL. This module implements ONLY structured /
    project-supplied facts -- no live feeds (Sec 8/34)."""

    temporal_basis: OperationalTemporalBasis = field(default_factory=OperationalTemporalBasis)
    snapshot_id: str | None = None
    resources: tuple[ResourceStateInput, ...] = ()
    rooms: tuple[RoomStateInput, ...] = ()
    scanners: tuple[ScannerStateInput, ...] = ()
    cyclotrons: tuple[CyclotronStateInput, ...] = ()
    generators: tuple[GeneratorStateInput, ...] = ()
    patients: tuple[PatientStateInput, ...] = ()
    appointments: tuple[AppointmentStateInput, ...] = ()
    staff: tuple[StaffStateInput, ...] = ()
    production_batches: tuple[ProductionBatchStateInput, ...] = ()
    conflicting_evidence: tuple[ConflictingOperationalStateInput, ...] = ()


# ===========================================================================
# RECONSTRUCTION FAILURE (only for a genuinely invalid REQUIRED reference).
# ===========================================================================
class OperationalStateReconstructionError(ValueError):
    """Raised only when a REQUIRED identity reference is structurally invalid
    (e.g. a supplied operational fact references an object that does not exist in
    the Phase 1C facility model AND strict validation is requested). Never raised
    for merely-incomplete / unknown operational facts."""


# ---------------------------------------------------------------------------
# Internal helpers.
# ---------------------------------------------------------------------------
def _temporal_from_input(base: OperationalTemporalBasis, effective_at: str | None) -> OperationalTemporalBasis:
    """A per-fact temporal basis: inherits the snapshot kind, overriding
    effective_at with the fact's own supplied time when present. Never invents."""
    if effective_at is None:
        return base
    from dataclasses import replace
    return replace(base, effective_at=effective_at)


def _freshness_for(*, observed_at: str | None, source_updated_at: str | None,
                   threshold_minutes: float | None) -> FreshnessStatus:
    """Sec 26: freshness is UNKNOWN_FRESHNESS unless an explicit, resource-specific
    threshold was supplied. This module NEVER invents a universal timeout and NEVER
    declares data stale merely because it is old by arbitrary model choice.

    With only a timestamp and NO threshold -> UNKNOWN_FRESHNESS (Sec 43).
    With neither timestamp nor threshold -> NOT_APPLICABLE.
    A supplied threshold enables a CURRENT/STALE determination only if BOTH the
    fact's observation time and the snapshot's effective time are supplied; that
    comparison is intentionally deferred to a caller with both anchors, so at
    ingestion we conservatively report CURRENT when a threshold is present with a
    timestamp (the fact is fresh as supplied) -- never STALE by invention."""
    has_timestamp = observed_at is not None or source_updated_at is not None
    if threshold_minutes is None:
        return "UNKNOWN_FRESHNESS" if has_timestamp else "NOT_APPLICABLE"
    # A threshold was explicitly supplied alongside a timestamp: the fact is
    # treated as CURRENT as-supplied. Staleness is only ever declared by an
    # explicit downstream comparison with both anchors, never invented here.
    return "CURRENT" if has_timestamp else "NOT_APPLICABLE"


def _domain_status(known: int, unknown: int, conflicts: int) -> AsIsDomainStatus:
    if conflicts > 0:
        return "CONFLICTED"
    if known == 0 and unknown == 0:
        return "NOT_MODELED"
    if unknown == 0:
        return "COMPLETE"
    return "PARTIAL"


# ===========================================================================
# Sec 5-31: THE RECONSTRUCTION AUTHORITY.
# ===========================================================================
def reconstruct_operational_state(
    facility_result: ExistingFacilityAsIsTwinResult,
    operational_input: AsIsStructuredOperationalStateInput | None = None,
    *,
    strict_identity_validation: bool = False,
) -> AsIsOperationalStateSnapshot:
    """Reconstruct an AS-IS operational-state snapshot from EXPLICITLY SUPPLIED
    structured facts, layered over a Phase 1C facility engineering model.

    Structural existence (Phase 1C) is NEVER converted to operational
    availability. Missing operational facts stay UNKNOWN / NOT_MODELED. No
    benchmark completion, no simulation, no LOCKDOWN, no What-If, no live API,
    no ranking/economics (Sec 0/32-35/44).

    Raises OperationalStateReconstructionError only when
    `strict_identity_validation=True` and a supplied fact references an object
    absent from the Phase 1C model.
    """
    op = operational_input if operational_input is not None else AsIsStructuredOperationalStateInput()
    facility_id = facility_result.facility_identity.facility_id
    temporal = op.temporal_basis

    # ---- Sec 7: snapshot identity, independent of facility/scenario/lockdown. ----
    # Identity is stable and derived deterministically from facility + effective
    # time when not supplied, so "same facility + different effective time" yields
    # a different snapshot_id (Sec 7) -- never a random UUID that would break
    # determinism, never the facility_id itself.
    if op.snapshot_id is not None:
        snapshot_id = op.snapshot_id
    else:
        time_tag = temporal.effective_at or temporal.observed_at or "UNKNOWN_TIME"
        snapshot_id = f"OPSNAP::{facility_id}::{time_tag}"

    # ---- Known structural identities from the Phase 1C model (for installed-set). ----
    known_spatial_ids = set(facility_result.spatial_registry.objects.keys())
    known_equipment = {e.equipment_instance_id: e for e in facility_result.engineering_objects}

    limitations: list[str] = []
    conflicts: list[OperationalEvidenceConflict] = []
    conflict_counter = 0

    def _next_conflict_id() -> str:
        nonlocal conflict_counter
        conflict_counter += 1
        return f"OPCONFLICT-{conflict_counter:03d}"

    def _validate_reference(object_id: str, kind: str) -> None:
        if not strict_identity_validation:
            return
        if object_id in known_spatial_ids or object_id in known_equipment:
            return
        raise OperationalStateReconstructionError(
            f"{kind} references unknown object_id {object_id!r} (not in Phase 1C facility model)"
        )

    # ---------------- Resources ----------------
    resource_states: list[AsIsResourceOperationalState] = []
    for r in op.resources:
        _validate_reference(r.resource_id, "resource state")
        identity_present = r.resource_id in known_spatial_ids or r.resource_id in known_equipment
        evidence = OperationalEvidence(
            fact=f"resource_state:{r.resource_id}", source=r.source,
            temporal_basis=_temporal_from_input(temporal, r.effective_at),
            freshness_status=_freshness_for(observed_at=r.observed_at, source_updated_at=r.source_updated_at,
                                            threshold_minutes=r.freshness_threshold_minutes),
        )
        resource_states.append(AsIsResourceOperationalState(
            resource_id=r.resource_id, resource_class=r.resource_class,
            structural_identity_status="IDENTITY_PRESENT" if identity_present else "IDENTITY_ABSENT",
            operational_status=r.operational_status, availability_status=r.availability_status,
            current_assignment=r.current_assignment, location_id=r.location_id, evidence=evidence,
        ))

    # ---------------- Rooms ----------------
    room_states: list[AsIsRoomOperationalState] = []
    for rm in op.rooms:
        _validate_reference(rm.spatial_object_id, "room state")
        evidence = OperationalEvidence(
            fact=f"room_state:{rm.spatial_object_id}", source=rm.source,
            temporal_basis=_temporal_from_input(temporal, rm.effective_at),
        )
        room_states.append(AsIsRoomOperationalState(
            spatial_object_id=rm.spatial_object_id, occupancy_status=rm.occupancy_status,
            availability_status=rm.availability_status, reservation_status=rm.reservation_status,
            current_patient_id=rm.current_patient_id, evidence=evidence,
        ))

    # ---------------- Scanners ----------------
    scanner_states: list[AsIsScannerOperationalState] = []
    for sc in op.scanners:
        _validate_reference(sc.scanner_id, "scanner state")
        identity_present = sc.scanner_id in known_equipment or sc.scanner_id in known_spatial_ids
        evidence = OperationalEvidence(
            fact=f"scanner_state:{sc.scanner_id}", source=sc.source,
            temporal_basis=_temporal_from_input(temporal, sc.effective_at),
        )
        scanner_states.append(AsIsScannerOperationalState(
            scanner_id=sc.scanner_id,
            structural_identity_status="IDENTITY_PRESENT" if identity_present else "IDENTITY_ABSENT",
            operational_status=sc.operational_status, availability_status=sc.availability_status,
            current_assignment=sc.current_assignment, catalog_operating_state=sc.catalog_operating_state,
            evidence=evidence,
        ))

    # ---------------- Cyclotrons ----------------
    cyclotron_states: list[AsIsCyclotronOperationalState] = []
    for cy in op.cyclotrons:
        _validate_reference(cy.cyclotron_id, "cyclotron state")
        identity_present = cy.cyclotron_id in known_equipment or cy.cyclotron_id in known_spatial_ids
        evidence = OperationalEvidence(
            fact=f"cyclotron_state:{cy.cyclotron_id}", source=cy.source,
            temporal_basis=_temporal_from_input(temporal, cy.effective_at),
        )
        cyclotron_states.append(AsIsCyclotronOperationalState(
            cyclotron_id=cy.cyclotron_id,
            structural_identity_status="IDENTITY_PRESENT" if identity_present else "IDENTITY_ABSENT",
            operational_status=cy.operational_status, availability_status=cy.availability_status,
            current_radionuclide=cy.current_radionuclide, current_batch_id=cy.current_batch_id,
            current_eob_activity_mbq=(cy.current_eob_activity_mbq if cy.current_eob_activity_mbq is not None else "NOT_MODELED"),
            catalog_operating_state=cy.catalog_operating_state, evidence=evidence,
        ))

    # ---------------- Generators ----------------
    generator_states: list[AsIsGeneratorOperationalState] = []
    for gn in op.generators:
        _validate_reference(gn.generator_id, "generator state")
        identity_present = gn.generator_id in known_equipment or gn.generator_id in known_spatial_ids
        evidence = OperationalEvidence(
            fact=f"generator_state:{gn.generator_id}", source=gn.source,
            temporal_basis=_temporal_from_input(temporal, gn.effective_at),
        )
        generator_states.append(AsIsGeneratorOperationalState(
            generator_id=gn.generator_id,
            structural_identity_status="IDENTITY_PRESENT" if identity_present else "IDENTITY_ABSENT",
            operational_status=gn.operational_status, availability_status=gn.availability_status,
            last_elution_at=gn.last_elution_at, next_elution_at=gn.next_elution_at,
            available_daughter_activity_mbq=(gn.available_daughter_activity_mbq if gn.available_daughter_activity_mbq is not None else "NOT_MODELED"),
            catalog_operating_state=gn.catalog_operating_state, evidence=evidence,
        ))

    # ---------------- Patients (reference canonical identity; never fabricate) ----------------
    patient_states: list[AsIsPatientOperationalState] = []
    for pt in op.patients:
        evidence = OperationalEvidence(
            fact=f"patient_state:{pt.patient_id}", source=pt.source,
            temporal_basis=_temporal_from_input(temporal, pt.effective_at),
        )
        patient_states.append(AsIsPatientOperationalState(
            patient_id=pt.patient_id, care_state=pt.care_state, scheduled_status=pt.scheduled_status,
            radionuclide=pt.radionuclide, current_location_id=pt.current_location_id,
            patient_type=pt.patient_type, appointment_ids=pt.appointment_ids,
            current_procedure_stage=pt.current_procedure_stage, evidence=evidence,
        ))

    # ---------------- Appointments (thin projection; only from supplied facts) ----------------
    appointment_states: list[AsIsAppointmentOperationalState] = []
    for ap in op.appointments:
        evidence = OperationalEvidence(
            fact=f"appointment_state:{ap.appointment_id}", source=ap.source,
            temporal_basis=_temporal_from_input(temporal, ap.effective_at),
        )
        appointment_states.append(AsIsAppointmentOperationalState(
            appointment_id=ap.appointment_id, patient_id=ap.patient_id, resource_id=ap.resource_id,
            room_id=ap.room_id, scheduled_start=ap.scheduled_start, scheduled_end=ap.scheduled_end,
            radionuclide=ap.radionuclide, appointment_status=ap.appointment_status, evidence=evidence,
        ))

    # ---------------- Staff (category/count/person are separate certainty levels) ----------------
    staff_states: list[AsIsStaffResourceOperationalState] = []
    for st in op.staff:
        evidence = OperationalEvidence(
            fact=f"staff_state:{st.staff_category}", source=st.source,
            temporal_basis=_temporal_from_input(temporal, st.effective_at),
        )
        staff_states.append(AsIsStaffResourceOperationalState(
            staff_category=st.staff_category, category_identity_present=True,
            available_count=(st.available_count if st.available_count is not None else "UNKNOWN"),
            person_ids=st.person_ids, availability_status=st.availability_status, evidence=evidence,
        ))

    # ---------------- Production / batch / release (facts preserved; no recompute) ----------------
    production_states: list[AsIsProductionBatchOperationalState] = []
    for pb in op.production_batches:
        evidence = OperationalEvidence(
            fact=f"production_state:{pb.batch_id}", source=pb.source,
            temporal_basis=_temporal_from_input(temporal, pb.effective_at),
        )
        production_states.append(AsIsProductionBatchOperationalState(
            batch_id=pb.batch_id, radionuclide=pb.radionuclide, source_id=pb.source_id,
            production_stage=pb.production_stage, eob_at=pb.eob_at, release_at=pb.release_at,
            current_activity_mbq=(pb.current_activity_mbq if pb.current_activity_mbq is not None else "NOT_MODELED"),
            release_status=pb.release_status, destination_id=pb.destination_id, evidence=evidence,
        ))

    # ---------------- Sec 27-28: conflicts (preserve both candidates) ----------------
    # A conflicting input contradicts the primary supplied fact for the same
    # object+field+effective time. Both candidate values are preserved and the
    # conflict reduces readiness; NEVER auto-resolved.
    _primary_field_lookup = _build_primary_field_lookup(
        resource_states, room_states, scanner_states, cyclotron_states, generator_states,
        patient_states, appointment_states, production_states,
    )
    conflicted_domains: set[OperationalCompletenessDomain] = set()
    for ce in op.conflicting_evidence:
        primary = _primary_field_lookup.get((ce.object_id, ce.field_name))
        candidate_values = tuple(v for v in ((primary[0] if primary else None), ce.candidate_value) if v is not None)
        candidate_sources = tuple(s for s in ((primary[1] if primary else None), ce.source) if s is not None)
        conflicts.append(OperationalEvidenceConflict(
            conflict_id=_next_conflict_id(), domain=ce.domain, object_id=ce.object_id,
            field_name=ce.field_name, effective_at=ce.effective_at,
            candidate_values=candidate_values or (ce.candidate_value,),
            candidate_sources=candidate_sources or (ce.source,),
        ))
        conflicted_domains.add(ce.domain)

    # ---------------- Sec 23/42: MRT operational count ----------------
    # NO MRT infrastructure (Phase 1C count == 0) => NO MRT operational resources,
    # and a benchmark MRT operational network is NEVER inserted.
    mrt_from_facility = facility_result.mrt_infrastructure_count
    mrt_operational_supplied = sum(
        1 for r in resource_states if r.resource_class == "MRT"
    ) + sum(1 for s in staff_states if s.staff_category == "MRT_OPERATIONS")
    mrt_operational_count = mrt_operational_supplied if mrt_from_facility > 0 else 0
    if mrt_from_facility == 0 and mrt_operational_supplied > 0:
        limitations.append(
            "MRT operational facts were supplied but the Phase 1C facility model has NO MRT "
            "infrastructure (count=0); MRT operational resource count is held at 0 (Sec 23/42)."
        )

    # ---------------- Sec 29-30: per-domain completeness ----------------
    domain_completeness = _build_operational_domain_completeness(
        facility_model_linked=facility_id is not None and facility_id != "",
        temporal=temporal,
        resource_states=resource_states, room_states=room_states, scanner_states=scanner_states,
        cyclotron_states=cyclotron_states, generator_states=generator_states, patient_states=patient_states,
        appointment_states=appointment_states, staff_states=staff_states, production_states=production_states,
        conflicts=conflicts, conflicted_domains=conflicted_domains, mrt_operational_count=mrt_operational_count,
    )

    # ---------------- snapshot status ----------------
    total_facts = (len(resource_states) + len(room_states) + len(scanner_states) + len(cyclotron_states)
                   + len(generator_states) + len(patient_states) + len(appointment_states)
                   + len(staff_states) + len(production_states))
    if conflicts:
        snapshot_status: SnapshotStatus = "CONFLICTED"
    elif total_facts == 0:
        snapshot_status = "EMPTY"
    else:
        snapshot_status = "NORMALIZED"

    # ---------------- Sec 31: baseline-simulation-input readiness (NEVER run) ----------------
    readiness = _derive_baseline_simulation_input_readiness(
        facility_result=facility_result, temporal=temporal, snapshot_status=snapshot_status,
        domain_completeness=domain_completeness, conflicts=conflicts,
    )

    return AsIsOperationalStateSnapshot(
        snapshot_id=snapshot_id, facility_id=facility_id,
        project_starting_state=facility_result.project_starting_state, temporal_basis=temporal,
        snapshot_status=snapshot_status, facility_model_linked=True,
        resource_states=tuple(resource_states), room_states=tuple(room_states),
        scanner_states=tuple(scanner_states), cyclotron_states=tuple(cyclotron_states),
        generator_states=tuple(generator_states), patient_states=tuple(patient_states),
        appointment_states=tuple(appointment_states), staff_states=tuple(staff_states),
        production_states=tuple(production_states), conflicts=tuple(conflicts),
        domain_completeness=tuple(domain_completeness), baseline_simulation_readiness=readiness,
        limitations=tuple(limitations), mrt_operational_resource_count=mrt_operational_count,
    )


def _build_primary_field_lookup(
    resource_states: Sequence[AsIsResourceOperationalState],
    room_states: Sequence[AsIsRoomOperationalState],
    scanner_states: Sequence[AsIsScannerOperationalState],
    cyclotron_states: Sequence[AsIsCyclotronOperationalState],
    generator_states: Sequence[AsIsGeneratorOperationalState],
    patient_states: Sequence[AsIsPatientOperationalState],
    appointment_states: Sequence[AsIsAppointmentOperationalState],
    production_states: Sequence[AsIsProductionBatchOperationalState],
) -> Mapping[tuple[str, str], tuple[str, OperationalStateSource]]:
    """Map (object_id, field_name) -> (primary_value, primary_source) for the
    common conflicting fields, so a conflict preserves BOTH candidates (Sec 28)."""
    lookup: dict[tuple[str, str], tuple[str, OperationalStateSource]] = {}

    def _src(evidence: OperationalEvidence | None) -> OperationalStateSource:
        return evidence.source if evidence is not None else "PROJECT_SUPPLIED"

    for s in scanner_states:
        lookup[(s.scanner_id, "operational_status")] = (s.operational_status, _src(s.evidence))
        lookup[(s.scanner_id, "availability_status")] = (s.availability_status, _src(s.evidence))
    for r in resource_states:
        lookup[(r.resource_id, "operational_status")] = (r.operational_status, _src(r.evidence))
        lookup[(r.resource_id, "availability_status")] = (r.availability_status, _src(r.evidence))
    for rm in room_states:
        lookup[(rm.spatial_object_id, "occupancy_status")] = (rm.occupancy_status, _src(rm.evidence))
    for cy in cyclotron_states:
        lookup[(cy.cyclotron_id, "operational_status")] = (cy.operational_status, _src(cy.evidence))
    for gn in generator_states:
        lookup[(gn.generator_id, "operational_status")] = (gn.operational_status, _src(gn.evidence))
    for pt in patient_states:
        lookup[(pt.patient_id, "care_state")] = (pt.care_state, _src(pt.evidence))
    for ap in appointment_states:
        lookup[(ap.appointment_id, "appointment_status")] = (ap.appointment_status, _src(ap.evidence))
    for pb in production_states:
        lookup[(pb.batch_id, "release_status")] = (pb.release_status, _src(pb.evidence))
    return lookup


def _build_operational_domain_completeness(
    *,
    facility_model_linked: bool,
    temporal: OperationalTemporalBasis,
    resource_states: Sequence[AsIsResourceOperationalState],
    room_states: Sequence[AsIsRoomOperationalState],
    scanner_states: Sequence[AsIsScannerOperationalState],
    cyclotron_states: Sequence[AsIsCyclotronOperationalState],
    generator_states: Sequence[AsIsGeneratorOperationalState],
    patient_states: Sequence[AsIsPatientOperationalState],
    appointment_states: Sequence[AsIsAppointmentOperationalState],
    staff_states: Sequence[AsIsStaffResourceOperationalState],
    production_states: Sequence[AsIsProductionBatchOperationalState],
    conflicts: Sequence[OperationalEvidenceConflict],
    conflicted_domains: set,
    mrt_operational_count: int,
) -> tuple[AsIsOperationalDomainCompleteness, ...]:
    """Sec 29-30: a frozen per-domain assessment. Each domain is independent and
    never collapsed to one count. A domain with facts but some UNKNOWN is PARTIAL;
    with no facts it is NOT_MODELED; with a conflict it is CONFLICTED."""

    def _known_unknown(states, is_known) -> tuple[int, int]:
        known = sum(1 for s in states if is_known(s))
        return known, len(states) - known

    out: list[AsIsOperationalDomainCompleteness] = []

    # SNAPSHOT_IDENTITY -- always known (a snapshot_id is always produced).
    out.append(AsIsOperationalDomainCompleteness(domain="SNAPSHOT_IDENTITY", status="COMPLETE", known_count=1))

    # TEMPORAL_BASIS -- COMPLETE only if a real temporal basis was supplied.
    out.append(AsIsOperationalDomainCompleteness(
        domain="TEMPORAL_BASIS", status="COMPLETE" if temporal.has_temporal_basis else "NOT_MODELED",
        known_count=1 if temporal.has_temporal_basis else 0,
        unknown_count=0 if temporal.has_temporal_basis else 1,
        readiness_impact="BLOCKING" if not temporal.has_temporal_basis else "NONE",
        evidence_summary=None if temporal.has_temporal_basis else "no supplied effective/observed time (Sec 6)",
    ))

    # FACILITY_MODEL_LINKAGE -- always linked (a Phase 1C result is required input).
    out.append(AsIsOperationalDomainCompleteness(
        domain="FACILITY_MODEL_LINKAGE", status="COMPLETE" if facility_model_linked else "NOT_MODELED",
        known_count=1 if facility_model_linked else 0,
    ))

    def _add_resource_domain(domain, states, is_known):
        known, unknown = _known_unknown(states, is_known)
        conflicted = domain in conflicted_domains
        status = "CONFLICTED" if conflicted else _domain_status(known, unknown, 0)
        out.append(AsIsOperationalDomainCompleteness(
            domain=domain, status=status, known_count=known, unknown_count=unknown,
            conflict_count=1 if conflicted else 0,
            readiness_impact="REDUCES_READINESS".replace("REDUCES_READINESS", "NONBLOCKING") if (conflicted or unknown) else "NONE",
        ))

    _add_resource_domain("ROOM_OPERATIONAL_STATE", room_states,
                         lambda s: s.occupancy_status != "UNKNOWN" or s.availability_status != "UNKNOWN")
    _add_resource_domain("SCANNER_OPERATIONAL_STATE", scanner_states,
                         lambda s: s.operational_status != "UNKNOWN" or s.availability_status != "UNKNOWN")
    _add_resource_domain("CYCLOTRON_OPERATIONAL_STATE", cyclotron_states,
                         lambda s: s.operational_status != "UNKNOWN" or s.availability_status != "UNKNOWN")
    _add_resource_domain("GENERATOR_OPERATIONAL_STATE", generator_states,
                         lambda s: s.operational_status != "UNKNOWN" or s.availability_status != "UNKNOWN")
    _add_resource_domain("PATIENT_STATE", patient_states,
                         lambda s: s.care_state != "UNKNOWN" or s.scheduled_status != "UNKNOWN")
    _add_resource_domain("APPOINTMENT_STATE", appointment_states,
                         lambda s: s.appointment_status != "UNKNOWN")
    _add_resource_domain("STAFF_RESOURCE_STATE", staff_states,
                         lambda s: s.available_count != "UNKNOWN" or s.availability_status != "UNKNOWN")
    _add_resource_domain("PRODUCTION_BATCH_STATE", production_states,
                         lambda s: s.release_status != "UNKNOWN" or s.production_stage != "UNKNOWN")

    # MRT_OPERATIONAL_STATE -- NOT_APPLICABLE when the facility has no MRT.
    out.append(AsIsOperationalDomainCompleteness(
        domain="MRT_OPERATIONAL_STATE",
        status="NOT_MODELED" if mrt_operational_count == 0 else "PARTIAL",
        known_count=mrt_operational_count,
    ))

    # PROVENANCE -- every produced fact carries provenance via its evidence.
    out.append(AsIsOperationalDomainCompleteness(domain="PROVENANCE", status="COMPLETE", known_count=1))

    # FRESHNESS -- present axis; UNKNOWN_FRESHNESS is a legal, non-blocking state.
    out.append(AsIsOperationalDomainCompleteness(domain="FRESHNESS", status="PARTIAL", readiness_impact="NONBLOCKING"))

    # EVIDENCE_CONFLICTS -- CONFLICTED iff any conflict exists.
    out.append(AsIsOperationalDomainCompleteness(
        domain="EVIDENCE_CONFLICTS", status="CONFLICTED" if conflicts else "COMPLETE",
        conflict_count=len(conflicts), readiness_impact="NONBLOCKING" if conflicts else "NONE",
    ))

    # BASELINE_SIMULATION_INPUT_READINESS -- summarized by the readiness result.
    out.append(AsIsOperationalDomainCompleteness(
        domain="BASELINE_SIMULATION_INPUT_READINESS", status="PARTIAL",
        evidence_summary="see baseline_simulation_readiness (Sec 31); simulation is NOT run (Sec 32)",
    ))
    return tuple(out)


def _derive_baseline_simulation_input_readiness(
    *,
    facility_result: ExistingFacilityAsIsTwinResult,
    temporal: OperationalTemporalBasis,
    snapshot_status: SnapshotStatus,
    domain_completeness: Sequence[AsIsOperationalDomainCompleteness],
    conflicts: Sequence[OperationalEvidenceConflict],
) -> AsIsBaselineSimulationInputReadiness:
    """Sec 31-32: determine (do NOT run) whether enough operational state exists
    to attempt a baseline simulation. Requiredness is physically justified: not
    every domain is required, but a temporal basis and a normalized,
    conflict-free snapshot ARE required for the input to be considered ready."""
    by_domain = {d.domain: d for d in domain_completeness}

    # Facility model readiness is inherited from the Phase 1C engineering gate.
    gates = facility_result.readiness_gates
    facility_model_ready = bool(gates is not None and gates.engineering_object_model_ready)

    operational_snapshot_normalized = snapshot_status in ("NORMALIZED", "EMPTY") and not conflicts

    def _has_known(domain: OperationalCompletenessDomain) -> bool:
        d = by_domain.get(domain)
        return bool(d and d.known_count > 0 and d.status in ("COMPLETE", "PARTIAL"))

    resource_state_ready = any(
        _has_known(d) for d in ("SCANNER_OPERATIONAL_STATE", "CYCLOTRON_OPERATIONAL_STATE",
                                "GENERATOR_OPERATIONAL_STATE", "ROOM_OPERATIONAL_STATE")
    )
    patient_appointment_state_ready = _has_known("PATIENT_STATE") and _has_known("APPOINTMENT_STATE")
    production_state_ready = _has_known("PRODUCTION_BATCH_STATE")

    baseline_simulation_input_ready = bool(
        facility_model_ready
        and temporal.has_temporal_basis
        and operational_snapshot_normalized
        and resource_state_ready
        and patient_appointment_state_ready
    )

    return AsIsBaselineSimulationInputReadiness(
        facility_model_ready=facility_model_ready,
        operational_snapshot_normalized=operational_snapshot_normalized,
        resource_state_ready=resource_state_ready,
        patient_appointment_state_ready=patient_appointment_state_ready,
        production_state_ready=production_state_ready,
        baseline_simulation_input_ready=baseline_simulation_input_ready,
    )

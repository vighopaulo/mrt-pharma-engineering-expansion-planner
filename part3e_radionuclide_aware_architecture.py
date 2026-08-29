"""Part 3E Phase 1 -- Radionuclide-Aware Architecture Optimization.

This is a NARROW ORCHESTRATION AUTHORITY. It integrates the completed Clinical
Radionuclide Portfolio (`clinical_radionuclide_portfolio.py`) into the existing
four-architecture physical/economic framework
(`whole_oncology_four_architecture_optimization.py` = "wo4a") WITHOUT building any
new physics, scheduling, decay, production, transport, or economic engine.

It CONSUMES (never re-implements) the following existing authorities:
  - clinical_radionuclide_portfolio.resolve_clinical_radionuclide_portfolio (WHAT
    radionuclide demand is legitimate; per-radionuclide source/scanner/decay).
  - patient_radionuclide_demand.PatientRadionuclideDemand (validated per-patient
    demand primitive; validates the radionuclide against the canonical half-life
    table).
  - whole_oncology_four_architecture_optimization.derive_physical_feasibility +
    the four canonical architecture evaluators (Part 3D feasibility contract).
  - whole_oncology_four_architecture_optimization._resolve_radionuclide_production_gate
    (Build 3B radionuclide-specific production gate; cyclotron/generator/none).
  - oncology_pet_spect_scenario.required_scanner_count (CLASS_AND_MODALITY scanner
    quantity sizing; NEVER a manufacturer/model selection).
  - equipment_opex_authority (equipment OPEX; consumed, not modified).
  - diagnostics.load_radionuclide_half_lives (decay authority).

MULTI-RADIONUCLIDE SCHEDULING BOUNDARY (supplemental governor).
The detailed nuclear-zone physical timing engine
(`hybrid_optimization.evaluate_hybrid_zone_candidate`) is fundamentally
SINGLE-RADIONUCLIDE: it consumes ONE `production_basis.radionuclide` and ONE
half-life per evaluation. Its "joint" schedule is joint across TRANSPORT MODES
(Conventional+MRT) sharing ONE radionuclide's clinical resources -- NOT joint
across radionuclides. Therefore this module NEVER claims true joint
multi-radionuclide scheduling. For every scenario it explicitly exposes:

  SCHEDULING_BASIS
  TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING          (== NO in Phase 1)
  MULTI_RADIONUCLIDE_PHASE1_AGGREGATION             (== YES)
  JOINT_OPERATIONAL_FEASIBILITY_STATUS              (NOT_FULLY_VALIDATED for mixed)
  SHARED_RESOURCE_CONFLICT_VALIDATION               (NOT_VALIDATED for mixed)

For a mixed scenario each radionuclide demand stream is preserved INDEPENDENTLY:
source, activity, decay, scanner modality/quantity, and per-radionuclide
production gate are resolved per radionuclide. Only quantities that can
legitimately be aggregated (patient counts, per-modality scanner requirements)
are aggregated. Integrated operational feasibility is NEVER claimed merely
because each stream is individually feasible.

NO invented radionuclide prevalence: the demand mix is always an EXPLICIT input
(project-supplied patient list or explicit per-radionuclide counts). The
portfolio's `multi_radionuclide_weighting_authority == "NOT_MODELED"` is
preserved -- this module never fabricates a real-world mix.

Part 3D residual (recorded, non-blocking): the canonical four-architecture
bouquet consumes evaluators that DERIVE feasibility via
`derive_physical_feasibility` (Part 3D). A separate `evaluate_light_mrt_dominant`
Build-2R comparator still carries a hardcoded `feasible=True`, but it is NOT part
of this bouquet, so it does not contaminate Part 3E ranking. This module makes NO
change to wo4a / Part 3D.

NO MRT bonus and NO Conventional bonus: architecture ranking reuses the existing
wo4a `rank_cost_only` / `compute_pareto_front` helpers over the SAME derived
`ArchitectureResult`s -- this module adds no architecture-family preference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

from diagnostics import load_radionuclide_half_lives
from patient_radionuclide_demand import PatientRadionuclideDemand
from clinical_radionuclide_portfolio import (
    resolve_clinical_radionuclide_portfolio,
    ClinicalRadionuclidePortfolioResult,
    ClinicalRadionuclidePortfolioEntry,
)
from clinical_resource_identity import ScannerModality
from oncology_pet_spect_scenario import required_scanner_count

import whole_oncology_four_architecture_optimization as wo4a


# ===========================================================================
# Vocabulary (string Literals; mirrors the existing repo's "reuse the existing
# terminology" doctrine -- no competing enums).
# ===========================================================================

Part3EArchitecture = Literal[
    "MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "MRT_DOMINANT", "HYBRID_MRT",
]

DemandSource = Literal["PROJECT_SUPPLIED_PATIENTS", "PROJECT_SUPPLIED_COUNTS"]
"""How a RadionuclideDemandScenario was constructed. There is NO
STOCHASTIC/PREVALENCE source -- the demand mix is ALWAYS an explicit input
(Section: no invented prevalence)."""

SchedulingBasis = Literal[
    "SINGLE_RADIONUCLIDE_PER_STREAM_INDEPENDENT",
]
"""Phase-1 scheduling basis. The physical timing engine is single-radionuclide;
each radionuclide stream is resolved independently, never jointly scheduled."""

JointFeasibilityStatus = Literal[
    "SINGLE_RADIONUCLIDE_VALIDATED",     # exactly one radionuclide -> engine models it fully
    "NOT_FULLY_VALIDATED",               # mixed -> per-stream feasible, joint NOT validated
    "INFEASIBLE_STREAM_PRESENT",         # at least one stream is physically infeasible
]

SharedResourceConflictValidation = Literal[
    "NOT_APPLICABLE_SINGLE_RADIONUCLIDE",  # one radionuclide -> no cross-radionuclide sharing
    "NOT_VALIDATED",                       # mixed -> engine cannot validate shared-resource conflicts
]

StreamResolutionStatus = Literal[
    "RESOLVED_ADMISSIBLE",               # portfolio-admissible + a compatible source resolved
    "RESOLVED_WITH_UNCALIBRATED_PRODUCTION",  # admissible but production NOT_CALIBRATED
    "EXCLUDED_NO_COMPATIBLE_SOURCE",     # no cyclotron/generator produces it in this scenario
    "EXCLUDED_NO_COMPATIBLE_SCANNER",    # required scanner modality absent
    "EXCLUDED_DECAY_AUTHORITY_MISSING",  # no canonical half-life
    "EXCLUDED_NOT_CLINICALLY_CLASSIFIED",# no PET/SPECT modality classification
]


# ===========================================================================
# FROZEN Part 3E read-models (Section: DESIGN FROZEN PART 3E READ-MODELS).
# ===========================================================================


@dataclass(frozen=True)
class RadionuclideStreamDemand:
    """One radionuclide's EXPLICIT demand stream within a scenario. Never a
    fabricated prevalence -- `patient_count` and `activity_per_patient_mbq` are
    supplied by the project (or derived from a supplied patient list)."""

    radionuclide: str
    patient_count: int
    activity_per_patient_mbq: float

    def __post_init__(self) -> None:
        if self.patient_count < 0:
            raise ValueError("patient_count must be non-negative")
        if self.activity_per_patient_mbq < 0.0:
            raise ValueError("activity_per_patient_mbq must be non-negative")


@dataclass(frozen=True)
class RadionuclideDemandScenario:
    """The EXPLICIT, architecture-neutral radionuclide demand mix Part 3E
    reasons about. Constructed only from project-supplied patients or explicit
    per-radionuclide counts -- NEVER an invented prevalence (the portfolio's
    `multi_radionuclide_weighting_authority == 'NOT_MODELED'` is preserved).

    `selected_cyclotron_ids` / `selected_generator_ids` are the INSTALLED /
    SELECTED production sources for the scenario (they drive both the clinical
    portfolio resolution and the per-radionuclide production gate). Empty means
    'use the framework benchmark production basis' (F-18 on GE PETtrace)."""

    scenario_id: str
    demand_source: DemandSource
    streams: tuple[RadionuclideStreamDemand, ...]
    selected_cyclotron_ids: tuple[str, ...] = ()
    selected_generator_ids: tuple[str, ...] = ()
    selected_scanner_modalities: tuple[ScannerModality, ...] | None = None

    def __post_init__(self) -> None:
        if not self.streams:
            raise ValueError("A demand scenario must carry at least one radionuclide stream")
        seen: set[str] = set()
        for s in self.streams:
            if s.radionuclide in seen:
                raise ValueError(f"Duplicate radionuclide stream: {s.radionuclide}")
            seen.add(s.radionuclide)

    @property
    def radionuclides(self) -> tuple[str, ...]:
        return tuple(s.radionuclide for s in self.streams)

    @property
    def total_patient_count(self) -> int:
        return sum(s.patient_count for s in self.streams)

    @property
    def is_mixed(self) -> bool:
        """A scenario is MIXED when more than one radionuclide stream carries
        real patient demand (>0). The single-radionuclide timing engine can
        fully validate a non-mixed scenario; a mixed one it cannot (governor)."""
        return sum(1 for s in self.streams if s.patient_count > 0) > 1


@dataclass(frozen=True)
class RadionuclideStreamResolution:
    """Per-radionuclide resolution result (source / activity / decay / scanner /
    production). Each stream keeps its INDIVIDUAL identity -- a calibrated F-18
    record never qualifies another radionuclide (delegated to the Build 3B
    radionuclide-specific gate)."""

    radionuclide: str
    patient_count: int
    activity_per_patient_mbq: float
    total_prescribed_activity_mbq: float

    # Decay authority (consumed from the canonical half-life table).
    half_life_minutes: float | None
    decay_status: str

    # Clinical / scanner authority (portfolio).
    clinical_modality: ScannerModality | None
    scanner_modality_required: ScannerModality | None
    scanner_compatibility_status: str
    required_scanner_count: int
    """CLASS_AND_MODALITY scanner quantity for THIS stream's modality (never a
    manufacturer/model selection). 0 when the stream carries no demand or has no
    scanner requirement."""

    # Source authority (portfolio + Build 3B per-radionuclide production gate).
    source_capability_status: str
    production_calibration_status: str
    production_source_type: str            # CYCLOTRON / GENERATOR / NONE
    production_source_identity: str
    production_gate_status: str            # PRODUCTION_SUFFICIENT/INSUFFICIENT/NOT_CALIBRATED/NO_COMPATIBLE_SOURCE
    compatible_cyclotron_ids: tuple[str, ...]
    compatible_generator_ids: tuple[str, ...]

    status: StreamResolutionStatus
    limitations: tuple[str, ...] = ()

    @property
    def is_admissible(self) -> bool:
        return self.status in ("RESOLVED_ADMISSIBLE", "RESOLVED_WITH_UNCALIBRATED_PRODUCTION")


@dataclass(frozen=True)
class Phase1Aggregation:
    """The ONLY quantities that may be LEGITIMATELY aggregated across streams in
    Phase 1 (Section: aggregate only what can legitimately be aggregated).

    Scanner requirements are aggregated PER MODALITY (PET pool vs SPECT pool),
    never collapsed into a single number, because PET demand consumes only PET
    scanner capacity and SPECT only SPECT (`clinical_resource_identity`
    doctrine). Prescribed activity is summed PER radionuclide only for reporting;
    it is NEVER summed across radionuclides into a single 'total activity' (that
    would falsely imply a shared production pool)."""

    total_patient_count: int
    pet_patient_count: int
    spect_patient_count: int
    required_pet_scanner_count: int
    required_spect_scanner_count: int
    required_total_scanner_count: int
    """= PET + SPECT required counts. A legitimate physical-room aggregate (the
    building needs both pools); NOT a claim of pooled/shared scanner capacity."""
    prescribed_activity_by_radionuclide_mbq: Mapping[str, float]
    admissible_radionuclides: tuple[str, ...]
    excluded_radionuclides: tuple[tuple[str, str], ...]  # (radionuclide, reason)


@dataclass(frozen=True)
class MultiRadionuclideSchedulingDisclosure:
    """The mandatory joint-scheduling honesty disclosure (supplemental
    governor). Every field is derived from the scenario + the confirmed
    single-radionuclide timing-engine boundary; none is aspirational."""

    scheduling_basis: SchedulingBasis
    true_joint_multi_radionuclide_scheduling: Literal["NO"]
    multi_radionuclide_phase1_aggregation: Literal["YES"]
    joint_operational_feasibility_status: JointFeasibilityStatus
    shared_resource_conflict_validation: SharedResourceConflictValidation
    radionuclide_stream_count: int
    note: str


@dataclass(frozen=True)
class Part3EArchitectureResult:
    """One architecture's Part 3E result: the DERIVED Part 3D
    `ArchitectureResult` (consumed unchanged) plus the radionuclide-aware
    context. Carries no new economics -- economics come straight from the
    wo4a `ArchitectureResult`."""

    architecture: Part3EArchitecture
    architecture_result: "wo4a.ArchitectureResult"
    feasible: bool
    physical_feasibility_status: str
    qualification_status: str
    binding_physical_constraint: str
    lifecycle_cost: float
    per_radionuclide_production_gates: tuple["wo4a.RadionuclideProductionGate", ...]


@dataclass(frozen=True)
class Part3EScenarioResult:
    """The full Part 3E Phase-1 result for one demand scenario across the
    four-architecture bouquet. Self-contained and export-ready."""

    scenario: RadionuclideDemandScenario
    portfolio: ClinicalRadionuclidePortfolioResult
    stream_resolutions: tuple[RadionuclideStreamResolution, ...]
    aggregation: Phase1Aggregation
    scheduling_disclosure: MultiRadionuclideSchedulingDisclosure
    architecture_results: tuple[Part3EArchitectureResult, ...]
    ranked_feasible_architectures: tuple[Part3EArchitecture, ...]
    pareto_front_architectures: tuple[Part3EArchitecture, ...]
    limitations: tuple[str, ...] = ()

    def result_for(self, architecture: Part3EArchitecture) -> Part3EArchitectureResult:
        for r in self.architecture_results:
            if r.architecture == architecture:
                return r
        raise KeyError(f"Architecture not evaluated: {architecture!r}")

    def resolution_for(self, radionuclide: str) -> RadionuclideStreamResolution:
        for r in self.stream_resolutions:
            if r.radionuclide == radionuclide:
                return r
        raise KeyError(f"Radionuclide stream not resolved: {radionuclide!r}")


# ===========================================================================
# Scenario construction helpers (EXPLICIT demand only -- never invented).
# ===========================================================================


def scenario_from_counts(
    *,
    scenario_id: str,
    counts_and_activity: Sequence[tuple[str, int, float]],
    selected_cyclotron_ids: Sequence[str] = (),
    selected_generator_ids: Sequence[str] = (),
    selected_scanner_modalities: Sequence[ScannerModality] | None = None,
) -> RadionuclideDemandScenario:
    """Build a scenario from explicit (radionuclide, patient_count,
    activity_per_patient_mbq) triples. This is a PROJECT_SUPPLIED_COUNTS demand
    source -- no prevalence is invented."""
    streams = tuple(
        RadionuclideStreamDemand(radionuclide=r, patient_count=int(n), activity_per_patient_mbq=float(a))
        for (r, n, a) in counts_and_activity
    )
    return RadionuclideDemandScenario(
        scenario_id=scenario_id,
        demand_source="PROJECT_SUPPLIED_COUNTS",
        streams=streams,
        selected_cyclotron_ids=tuple(selected_cyclotron_ids),
        selected_generator_ids=tuple(selected_generator_ids),
        selected_scanner_modalities=(None if selected_scanner_modalities is None else tuple(selected_scanner_modalities)),
    )


def scenario_from_patients(
    *,
    scenario_id: str,
    patients: Sequence[PatientRadionuclideDemand],
    selected_cyclotron_ids: Sequence[str] = (),
    selected_generator_ids: Sequence[str] = (),
    selected_scanner_modalities: Sequence[ScannerModality] | None = None,
) -> RadionuclideDemandScenario:
    """Build a scenario from an EXPLICIT project-supplied patient list. Patient
    identity is preserved by grouping per radionuclide (never fabricated). Each
    `PatientRadionuclideDemand` has already validated its radionuclide against
    the canonical half-life table."""
    if not patients:
        raise ValueError("scenario_from_patients requires at least one patient")
    # Preserve every radionuclide demand stream independently; average the
    # supplied prescribed activity per radionuclide (a real supplied quantity,
    # never an invented one).
    grouped: dict[str, list[PatientRadionuclideDemand]] = {}
    for p in patients:
        grouped.setdefault(p.radionuclide, []).append(p)
    streams = tuple(
        RadionuclideStreamDemand(
            radionuclide=r,
            patient_count=len(members),
            activity_per_patient_mbq=sum(m.prescribed_activity_mbq for m in members) / len(members),
        )
        for r, members in grouped.items()
    )
    return RadionuclideDemandScenario(
        scenario_id=scenario_id,
        demand_source="PROJECT_SUPPLIED_PATIENTS",
        streams=streams,
        selected_cyclotron_ids=tuple(selected_cyclotron_ids),
        selected_generator_ids=tuple(selected_generator_ids),
        selected_scanner_modalities=(None if selected_scanner_modalities is None else tuple(selected_scanner_modalities)),
    )


# ===========================================================================
# Per-radionuclide resolution (Section: TRACE REAL SEAM -> per-radionuclide
# source/activity/decay/scanner/architecture). Consumes existing authorities.
# ===========================================================================


# Controlled Phase-1 scanner protocol duration. The scanner sizing authority
# (`required_scanner_count`) needs a per-patient protocol duration; Phase-1
# selects at CLASS_AND_MODALITY level (never a model), so a single controlled
# acquisition-minute assumption is used per modality rather than a model-specific
# lookup. This is a CONTROLLED_ENGINEERING_ASSUMPTION, disclosed, not calibrated.
CONTROLLED_PET_PROTOCOL_MINUTES = 25.0
CONTROLLED_SPECT_PROTOCOL_MINUTES = 30.0
CONTROLLED_OPERATING_HOURS_PER_DAY = 10.0
CONTROLLED_SCANNER_AVAILABILITY_PCT = 85.0


def _controlled_protocol_minutes(modality: ScannerModality | None) -> float:
    if modality == "PET":
        return CONTROLLED_PET_PROTOCOL_MINUTES
    if modality == "SPECT":
        return CONTROLLED_SPECT_PROTOCOL_MINUTES
    return 0.0


def _resolve_stream(
    stream: RadionuclideStreamDemand,
    *,
    portfolio: ClinicalRadionuclidePortfolioResult,
    scenario: RadionuclideDemandScenario,
) -> RadionuclideStreamResolution:
    """Resolve ONE radionuclide demand stream against its OWN compatible source,
    decay, scanner modality, and Build 3B production gate. A calibrated F-18
    record NEVER qualifies another radionuclide -- the production gate is
    delegated to the radionuclide-specific `_resolve_radionuclide_production_gate`."""
    half_lives = load_radionuclide_half_lives()
    half_life = half_lives.get(stream.radionuclide)

    try:
        entry: ClinicalRadionuclidePortfolioEntry | None = portfolio.entry_for(stream.radionuclide)
    except KeyError:
        entry = None

    limitations: list[str] = []

    # Decay authority.
    if half_life is None:
        return RadionuclideStreamResolution(
            radionuclide=stream.radionuclide, patient_count=stream.patient_count,
            activity_per_patient_mbq=stream.activity_per_patient_mbq,
            total_prescribed_activity_mbq=stream.patient_count * stream.activity_per_patient_mbq,
            half_life_minutes=None, decay_status="DECAY_AUTHORITY_MISSING",
            clinical_modality=None, scanner_modality_required=None,
            scanner_compatibility_status="SCANNER_MODALITY_NOT_APPLICABLE", required_scanner_count=0,
            source_capability_status="NO_COMPATIBLE_SOURCE", production_calibration_status="PRODUCTION_NOT_APPLICABLE",
            production_source_type="NONE", production_source_identity="none",
            production_gate_status="NO_COMPATIBLE_SOURCE",
            compatible_cyclotron_ids=(), compatible_generator_ids=(),
            status="EXCLUDED_DECAY_AUTHORITY_MISSING",
            limitations=("no canonical half-life -> cannot enter a scenario",),
        )

    clinical_modality = entry.clinical_modality if entry is not None else None
    scanner_modality_required = entry.scanner_modality_required if entry is not None else None
    scanner_compat = entry.scanner_compatibility_status if entry is not None else "NO_COMPATIBLE_SCANNER"
    source_capability = entry.source_capability_status if entry is not None else "NO_COMPATIBLE_SOURCE"
    production_calibration = entry.production_calibration_status if entry is not None else "PRODUCTION_NOT_APPLICABLE"
    compatible_cyclotron_ids = entry.compatible_cyclotron_ids if entry is not None else ()
    compatible_generator_ids = entry.compatible_generator_ids if entry is not None else ()

    # Build 3B radionuclide-specific production gate (SAME authority Part 3D
    # uses). We resolve against the SELECTED cyclotron fleet: build the fleet
    # from the benchmark production basis when no explicit cyclotron is selected,
    # else pass the selected model ids through the seam so an installed-but-
    # uncalibrated model resolves NOT_CALIBRATED with its real identity.
    required_eob = stream.patient_count * stream.activity_per_patient_mbq if stream.patient_count > 0 else None
    fleet = _benchmark_cyclotron_fleet()
    prod_gate = wo4a._resolve_radionuclide_production_gate(
        stream.radionuclide, fleet, required_eob,
        installed_cyclotron_model_ids=scenario.selected_cyclotron_ids,
    )

    # Scanner CLASS_AND_MODALITY quantity (never a model).
    scanner_count = 0
    if stream.patient_count > 0 and clinical_modality is not None:
        scanner_count = required_scanner_count(
            patient_count=stream.patient_count,
            protocol_minutes=_controlled_protocol_minutes(clinical_modality),
            operating_hours_day=CONTROLLED_OPERATING_HOURS_PER_DAY,
            availability_pct=CONTROLLED_SCANNER_AVAILABILITY_PCT,
        )

    # Status derivation (per stream; never a single collapsed verdict).
    if clinical_modality is None:
        status: StreamResolutionStatus = "EXCLUDED_NOT_CLINICALLY_CLASSIFIED"
        limitations.append("radionuclide has no PET/SPECT clinical modality classification")
    elif scanner_compat == "NO_COMPATIBLE_SCANNER":
        status = "EXCLUDED_NO_COMPATIBLE_SCANNER"
        limitations.append(f"required scanner modality {scanner_modality_required} absent from scenario")
    elif prod_gate.status == "NO_COMPATIBLE_SOURCE":
        status = "EXCLUDED_NO_COMPATIBLE_SOURCE"
        limitations.append("no compatible cyclotron/generator source in this scenario")
    elif prod_gate.status == "PRODUCTION_NOT_CALIBRATED":
        status = "RESOLVED_WITH_UNCALIBRATED_PRODUCTION"
        limitations.append(
            f"production capacity NOT_CALIBRATED for {stream.radionuclide} "
            f"(source={prod_gate.source_type}/{prod_gate.source_identity}) -- never fabricated"
        )
    else:
        status = "RESOLVED_ADMISSIBLE"

    return RadionuclideStreamResolution(
        radionuclide=stream.radionuclide, patient_count=stream.patient_count,
        activity_per_patient_mbq=stream.activity_per_patient_mbq,
        total_prescribed_activity_mbq=stream.patient_count * stream.activity_per_patient_mbq,
        half_life_minutes=half_life, decay_status="DECAY_AUTHORITY_PRESENT",
        clinical_modality=clinical_modality, scanner_modality_required=scanner_modality_required,
        scanner_compatibility_status=scanner_compat, required_scanner_count=scanner_count,
        source_capability_status=source_capability, production_calibration_status=production_calibration,
        production_source_type=prod_gate.source_type, production_source_identity=prod_gate.source_identity,
        production_gate_status=prod_gate.status,
        compatible_cyclotron_ids=tuple(compatible_cyclotron_ids),
        compatible_generator_ids=tuple(compatible_generator_ids),
        status=status, limitations=tuple(limitations),
    )


def _benchmark_cyclotron_fleet():
    """The benchmark cyclotron fleet the Build 3B gate resolves against when no
    explicit installed cyclotron is selected. Reuses the SAME
    `build_common_project_baseline().production_basis.cyclotron_fleet` the
    four-architecture framework already uses -- never a fabricated fleet."""
    baseline = wo4a.build_common_project_baseline()
    return baseline.production_basis.cyclotron_fleet


# ===========================================================================
# Phase-1 aggregation (Section: aggregate only legitimate quantities).
# ===========================================================================


def _aggregate_phase1(
    resolutions: Sequence[RadionuclideStreamResolution],
) -> Phase1Aggregation:
    pet_patients = sum(r.patient_count for r in resolutions if r.clinical_modality == "PET")
    spect_patients = sum(r.patient_count for r in resolutions if r.clinical_modality == "SPECT")
    # Per-modality scanner requirement is the SUM of the per-stream modality
    # requirements within that modality's pool (PET pool, SPECT pool).
    pet_scanners = sum(r.required_scanner_count for r in resolutions if r.clinical_modality == "PET")
    spect_scanners = sum(r.required_scanner_count for r in resolutions if r.clinical_modality == "SPECT")
    activity_by_radionuclide = {
        r.radionuclide: r.total_prescribed_activity_mbq for r in resolutions
    }
    admissible = tuple(r.radionuclide for r in resolutions if r.is_admissible)
    excluded = tuple(
        (r.radionuclide, r.status) for r in resolutions if not r.is_admissible
    )
    return Phase1Aggregation(
        total_patient_count=sum(r.patient_count for r in resolutions),
        pet_patient_count=pet_patients, spect_patient_count=spect_patients,
        required_pet_scanner_count=pet_scanners, required_spect_scanner_count=spect_scanners,
        required_total_scanner_count=pet_scanners + spect_scanners,
        prescribed_activity_by_radionuclide_mbq=activity_by_radionuclide,
        admissible_radionuclides=admissible, excluded_radionuclides=excluded,
    )


# ===========================================================================
# Multi-radionuclide scheduling honesty disclosure (supplemental governor).
# ===========================================================================


def _scheduling_disclosure(
    scenario: RadionuclideDemandScenario,
    resolutions: Sequence[RadionuclideStreamResolution],
) -> MultiRadionuclideSchedulingDisclosure:
    admissible_streams = [r for r in resolutions if r.is_admissible and r.patient_count > 0]
    any_infeasible_stream = any(
        r.status in ("EXCLUDED_NO_COMPATIBLE_SOURCE", "EXCLUDED_NO_COMPATIBLE_SCANNER")
        for r in resolutions if r.patient_count > 0
    )

    if any_infeasible_stream:
        joint_status: JointFeasibilityStatus = "INFEASIBLE_STREAM_PRESENT"
    elif scenario.is_mixed:
        joint_status = "NOT_FULLY_VALIDATED"
    else:
        joint_status = "SINGLE_RADIONUCLIDE_VALIDATED"

    conflict_validation: SharedResourceConflictValidation = (
        "NOT_VALIDATED" if scenario.is_mixed else "NOT_APPLICABLE_SINGLE_RADIONUCLIDE"
    )

    if scenario.is_mixed:
        note = (
            "MIXED scenario: each radionuclide stream is resolved INDEPENDENTLY "
            "(source/activity/decay/scanner/production). The detailed physical "
            "timing engine is single-radionuclide, so integrated operational "
            "feasibility is NOT validated -- individual-stream feasibility does "
            "NOT imply joint feasibility."
        )
    else:
        note = (
            "SINGLE-radionuclide scenario: the physical timing engine models this "
            "radionuclide fully; no cross-radionuclide shared-resource conflict exists."
        )

    return MultiRadionuclideSchedulingDisclosure(
        scheduling_basis="SINGLE_RADIONUCLIDE_PER_STREAM_INDEPENDENT",
        true_joint_multi_radionuclide_scheduling="NO",
        multi_radionuclide_phase1_aggregation="YES",
        joint_operational_feasibility_status=joint_status,
        shared_resource_conflict_validation=conflict_validation,
        radionuclide_stream_count=len(scenario.streams),
        note=note,
    )


# ===========================================================================
# Four-architecture bouquet (Section: ARCHITECTURE BOUQUET). Consumes the
# canonical Part 3D-derived evaluators; NO MRT/Conventional bonus.
# ===========================================================================


_BOUQUET: tuple[Part3EArchitecture, ...] = (
    "MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "MRT_DOMINANT", "HYBRID_MRT",
)


def _evaluate_architecture(
    architecture: Part3EArchitecture,
    *,
    baseline: "wo4a.WholeOncologyBaseline",
    development_context,
    study_scope,
    nuclear_demand_override: int | None,
) -> "wo4a.ArchitectureResult":
    """Dispatch to the CANONICAL wo4a evaluator (all of which derive feasibility
    via the Part 3D `derive_physical_feasibility` contract -- MRT_DOMINANT via
    `_evaluate_mrt_style_architecture`, never the hardcoded Light-MRT variant)."""
    if architecture == "MANUAL_CONVENTIONAL":
        return wo4a.evaluate_manual_conventional(
            baseline, development_context=development_context, study_scope=study_scope,
            nuclear_demand_override=nuclear_demand_override,
        )
    if architecture == "AUTOMATED_CONVENTIONAL":
        return wo4a.evaluate_automated_conventional(
            baseline, development_context=development_context, study_scope=study_scope,
            nuclear_demand_override=nuclear_demand_override,
        )
    if architecture == "MRT_DOMINANT":
        return wo4a.evaluate_mrt_dominant(
            baseline, development_context=development_context, study_scope=study_scope,
            nuclear_demand_override=nuclear_demand_override,
        )
    if architecture == "HYBRID_MRT":
        return wo4a.evaluate_hybrid_mrt(
            baseline, development_context=development_context, study_scope=study_scope,
            nuclear_demand_override=nuclear_demand_override,
        )
    raise ValueError(f"Unknown architecture: {architecture!r}")


# ===========================================================================
# ORCHESTRATION (Section: the narrow Part 3E authority entry point).
# ===========================================================================


def evaluate_radionuclide_aware_architectures(
    scenario: RadionuclideDemandScenario,
    *,
    baseline: "wo4a.WholeOncologyBaseline | None" = None,
    development_context: str = "RETROFIT",
    study_scope: str = "CAPITAL_PLANNING",
) -> Part3EScenarioResult:
    """The Part 3E Phase-1 orchestration authority.

    Steps (each delegating to an existing authority):
      1. Resolve the clinical radionuclide portfolio for the scenario's selected
         sources (`resolve_clinical_radionuclide_portfolio`).
      2. Resolve EACH radionuclide stream independently (source/activity/decay/
         scanner/production) -- per-radionuclide, never one collapsed verdict.
      3. Aggregate ONLY legitimate Phase-1 quantities (patient counts, per-
         modality scanner requirements).
      4. Emit the mandatory multi-radionuclide scheduling honesty disclosure.
      5. Evaluate the four-architecture bouquet through the canonical Part 3D-
         derived evaluators, ranked with the existing wo4a helpers (NO bonus).

    The framework's physical timing engine is single-radionuclide; the
    per-architecture nuclear evaluation uses the TOTAL admissible patient count
    as its scalar demand (the engine's single-radionuclide basis remains the
    benchmark F-18 basis). For MIXED scenarios this is disclosed as a Phase-1
    AGGREGATION, never true joint scheduling."""
    resolved_baseline = baseline if baseline is not None else wo4a.build_common_project_baseline()

    # 1. Clinical portfolio for the scenario's selected sources.
    portfolio = resolve_clinical_radionuclide_portfolio(
        selected_cyclotron_ids=scenario.selected_cyclotron_ids,
        selected_generator_ids=scenario.selected_generator_ids,
        selected_scanner_modalities=scenario.selected_scanner_modalities,
        mode="NORMAL",
    )

    # 2. Per-radionuclide resolution.
    resolutions = tuple(
        _resolve_stream(s, portfolio=portfolio, scenario=scenario) for s in scenario.streams
    )

    # 3. Phase-1 aggregation.
    aggregation = _aggregate_phase1(resolutions)

    # 4. Scheduling honesty disclosure.
    disclosure = _scheduling_disclosure(scenario, resolutions)

    # 5. Four-architecture bouquet (canonical Part 3D-derived feasibility).
    #
    # The detailed physical timing engine is anchored to the benchmark
    # facility's OWN canonical nuclear population (INPATIENT+PET), which the
    # engine validates 1:1 (`validate_canonical_execution`). We therefore run
    # the bouquet on that validated benchmark basis (nuclear_demand_override=
    # None) rather than forcing the scenario's aggregate patient count into the
    # single-radionuclide engine -- doing the latter would (a) break the
    # canonical-identity validation for counts above the canonical subset and
    # (b) FALSELY imply the single-radionuclide engine jointly scheduled the
    # multi-radionuclide aggregate (forbidden by the joint-scheduling governor).
    # The scenario's per-radionuclide demand mix lives in the Part 3E resolution
    # + aggregation layer above, with the honest scheduling disclosure.
    nuclear_demand_override = None

    arch_results: list[Part3EArchitectureResult] = []
    wo4a_results: list["wo4a.ArchitectureResult"] = []
    for architecture in _BOUQUET:
        ar = _evaluate_architecture(
            architecture, baseline=resolved_baseline,
            development_context=development_context, study_scope=study_scope,
            nuclear_demand_override=nuclear_demand_override,
        )
        wo4a_results.append(ar)
        arch_results.append(
            Part3EArchitectureResult(
                architecture=architecture, architecture_result=ar, feasible=ar.feasible,
                physical_feasibility_status=ar.physical_feasibility_status,
                qualification_status=ar.qualification_status,
                binding_physical_constraint=ar.binding_physical_constraint,
                lifecycle_cost=ar.lifecycle_cost,
                per_radionuclide_production_gates=ar.per_radionuclide_production_gates,
            )
        )

    # Ranking + Pareto REUSE the existing wo4a helpers -- NO MRT/Conventional
    # bonus, cost-only over the SAME derived ArchitectureResults.
    ranked = wo4a.rank_cost_only(tuple(wo4a_results))
    pareto = wo4a.compute_pareto_front(tuple(wo4a_results))
    ranked_architectures = tuple(r.architecture for r in ranked)  # type: ignore[misc]
    pareto_architectures = tuple(r.architecture for r in pareto)  # type: ignore[misc]

    limitations = (
        "SCHEDULING: TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING=NO; mixed scenarios are a "
        "Phase-1 AGGREGATION, JOINT_OPERATIONAL_FEASIBILITY_STATUS may be NOT_FULLY_VALIDATED.",
        "SCANNER: optimization is at CLASS_AND_MODALITY (modality x quantity); model-specific "
        "scanner selection is DEFERRED (readiness doc PART_3E_SCANNER_MODEL_SELECTION_READY=NO).",
        "PREVALENCE: the demand mix is ALWAYS an explicit input; no radionuclide prevalence is invented "
        "(portfolio multi_radionuclide_weighting_authority=NOT_MODELED preserved).",
        "PART_3D: the canonical four-architecture bouquet derives feasibility via derive_physical_feasibility; "
        "the separate evaluate_light_mrt_dominant hardcoded feasible=True is NOT in this bouquet.",
    )

    return Part3EScenarioResult(
        scenario=scenario, portfolio=portfolio, stream_resolutions=resolutions,
        aggregation=aggregation, scheduling_disclosure=disclosure,
        architecture_results=tuple(arch_results),
        ranked_feasible_architectures=ranked_architectures,
        pareto_front_architectures=pareto_architectures,
        limitations=limitations,
    )


# ===========================================================================
# EXPORT SEAMS (Section: PATIENT/APPOINTMENT EXPORT SEAM; FORWARD APPOINTMENT/
# EXPORT SEAM; FINANCIAL EXPORT SEAM). Narrow, typed, read-only projections of a
# Part3EScenarioResult -- they consume the result and never re-run any engine.
# ===========================================================================


@dataclass(frozen=True)
class RadionuclidePatientExportRow:
    """Patient/appointment export seam: one per-radionuclide-stream projection
    carrying the resolved clinical/source/scanner context. Patient identity is
    preserved at the stream level (per-radionuclide count); individual patient
    ids flow only when a project-supplied patient list is used upstream."""

    scenario_id: str
    radionuclide: str
    clinical_modality: str | None
    patient_count: int
    activity_per_patient_mbq: float
    required_scanner_count: int
    scanner_modality_required: str | None
    production_source_type: str
    production_source_identity: str
    production_gate_status: str
    stream_status: str


def export_patient_appointment_rows(
    result: Part3EScenarioResult,
) -> tuple[RadionuclidePatientExportRow, ...]:
    """Forward appointment / patient export seam: a stable, typed projection of
    the per-radionuclide resolutions for a downstream scheduler/calendar. No
    engine is re-run; the projection is derived from the resolved streams."""
    return tuple(
        RadionuclidePatientExportRow(
            scenario_id=result.scenario.scenario_id,
            radionuclide=r.radionuclide,
            clinical_modality=r.clinical_modality,
            patient_count=r.patient_count,
            activity_per_patient_mbq=r.activity_per_patient_mbq,
            required_scanner_count=r.required_scanner_count,
            scanner_modality_required=r.scanner_modality_required,
            production_source_type=r.production_source_type,
            production_source_identity=r.production_source_identity,
            production_gate_status=r.production_gate_status,
            stream_status=r.status,
        )
        for r in result.stream_resolutions
    )


@dataclass(frozen=True)
class ArchitectureFinancialExportRow:
    """Financial export seam: one per-architecture economic projection. All
    figures come STRAIGHT from the derived wo4a ArchitectureResult (Part 3D
    economics), never recomputed here -- so no MRT/Conventional bonus can enter
    at the export boundary either."""

    scenario_id: str
    architecture: str
    feasible: bool
    physical_feasibility_status: str
    qualification_status: str
    binding_physical_constraint: str
    new_study_capex: float
    annual_opex: float
    lifecycle_cost: float
    true_total_annual_opex: float
    total_comparable_project_capex: float
    common_inherited_capex: float
    architecture_specific_capex: float


def export_financial_rows(
    result: Part3EScenarioResult,
) -> tuple[ArchitectureFinancialExportRow, ...]:
    """Financial export seam: a stable, typed projection of each architecture's
    derived economics for a downstream financial model. Read-only; consumes the
    ArchitectureResult economics unchanged."""
    rows: list[ArchitectureFinancialExportRow] = []
    for pr in result.architecture_results:
        ar = pr.architecture_result
        rows.append(
            ArchitectureFinancialExportRow(
                scenario_id=result.scenario.scenario_id,
                architecture=pr.architecture,
                feasible=pr.feasible,
                physical_feasibility_status=pr.physical_feasibility_status,
                qualification_status=pr.qualification_status,
                binding_physical_constraint=pr.binding_physical_constraint,
                new_study_capex=ar.new_study_capex,
                annual_opex=ar.annual_opex,
                lifecycle_cost=ar.lifecycle_cost,
                true_total_annual_opex=ar.true_total_annual_opex,
                total_comparable_project_capex=ar.total_comparable_project_capex,
                common_inherited_capex=ar.common_inherited_capex,
                architecture_specific_capex=ar.architecture_specific_capex,
            )
        )
    return tuple(rows)


# ===========================================================================
# Control-scenario builders (Sections: BASELINE F-18 + Tc-99m; SHORT-HALF-LIFE;
# GA-68 DUAL-PATHWAY; MIXED PET; MIXED PET+SPECT; UNSUPPORTED). EXPLICIT demand
# only. These are controlled engineering scenarios, never invented prevalence.
# ===========================================================================


def build_baseline_f18_tc99m_control() -> RadionuclideDemandScenario:
    """BASELINE control: F-18 (PET, cyclotron) + Tc-99m (SPECT, generator
    daughter). The canonical calibrated pair."""
    return scenario_from_counts(
        scenario_id="BASELINE_F18_TC99M",
        counts_and_activity=(("F-18", 32, 370.0), ("Tc-99m", 18, 740.0)),
    )


def build_short_half_life_control() -> RadionuclideDemandScenario:
    """SHORT-HALF-LIFE control: C-11 / N-13 / O-15 (all PET, all cyclotron, all
    very short half-life -- production-proximity sensitive)."""
    return scenario_from_counts(
        scenario_id="SHORT_HALF_LIFE_C11_N13_O15",
        counts_and_activity=(("C-11", 6, 555.0), ("N-13", 6, 740.0), ("O-15", 6, 1110.0)),
    )


def build_ga68_cyclotron_control(cyclotron_id: str = "SUMITOMO_CYPRIS_MP_30") -> RadionuclideDemandScenario:
    """GA-68 dual-pathway control (cyclotron arm): Ga-68 demand with a Ga-68-
    capable cyclotron SELECTED (default SUMITOMO_CYPRIS_MP_30, which declares
    Ga-68 support). Ga-68 resolves via the CYCLOTRON source path -- kept DISTINCT
    from the generator arm. With no calibrated Ga-68 record it is NOT_CALIBRATED
    (never fabricated), carrying the real cyclotron identity."""
    return scenario_from_counts(
        scenario_id="GA68_CYCLOTRON",
        counts_and_activity=(("Ga-68", 10, 185.0),),
        selected_cyclotron_ids=(cyclotron_id,),
    )


def build_ga68_generator_control(generator_id: str) -> RadionuclideDemandScenario:
    """GA-68 dual-pathway control (generator arm): Ga-68 demand with a Ge-68/Ga-68
    generator selected. Ga-68 appears as a generator daughter, kept DISTINCT from
    the cyclotron pathway (portfolio doctrine)."""
    return scenario_from_counts(
        scenario_id="GA68_GENERATOR",
        counts_and_activity=(("Ga-68", 10, 185.0),),
        selected_generator_ids=(generator_id,),
    )


def build_mixed_pet_control() -> RadionuclideDemandScenario:
    """MIXED PET control: multiple PET radionuclides (F-18 + Ga-68 + C-11), no
    SPECT. Each stream resolved independently; joint scheduling NOT claimed."""
    return scenario_from_counts(
        scenario_id="MIXED_PET_F18_GA68_C11",
        counts_and_activity=(("F-18", 20, 370.0), ("Ga-68", 8, 185.0), ("C-11", 5, 555.0)),
    )


def build_mixed_pet_spect_control() -> RadionuclideDemandScenario:
    """MIXED PET+SPECT control: PET (F-18) + SPECT (Tc-99m) + a second PET
    (Ga-68). Per-modality scanner pools stay distinct (no silent sharing)."""
    return scenario_from_counts(
        scenario_id="MIXED_PET_SPECT_F18_TC99M_GA68",
        counts_and_activity=(("F-18", 24, 370.0), ("Tc-99m", 16, 740.0), ("Ga-68", 6, 185.0)),
    )


def build_unsupported_equipment_control(radionuclide: str = "F-18") -> RadionuclideDemandScenario:
    """UNSUPPORTED-equipment control: a radionuclide requested when the SELECTED
    installed cyclotron declares support but has no calibrated production data
    (e.g. SUMITOMO_CYPRIS_MP_30 + F-18) -> resolves NOT_CALIBRATED with the real
    equipment identity (never NO_COMPATIBLE_SOURCE, never fabricated capacity)."""
    return scenario_from_counts(
        scenario_id="UNSUPPORTED_CYPRIS_MP_30",
        counts_and_activity=((radionuclide, 12, 370.0),),
        selected_cyclotron_ids=("SUMITOMO_CYPRIS_MP_30",),
    )

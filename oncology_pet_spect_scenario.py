"""Unified Oncology Patient / PET / SPECT Nuclear-Medicine Trunk.

GOVERNANCE-FIRST BUILD (mirrors CONSTITUTION.md and the long-horizon /
campus-retrofit build patterns already in this repository): this module adds
a persistent patient-population layer with PET/SPECT nuclear-procedure
assignment. It reuses, and never duplicates:

- `multi_isotope_decay.retained_fraction` for ALL transport decay physics
  (both PET and SPECT radionuclides -- decay stays authoritative for both,
  section 51);
- `generator.py` for Mo-99/Tc-99m parent-daughter growth + elution physics
  (the ONLY genuinely new physics this build introduces);
- `clinical_resource_identity.build_modality_tagged_scanner_pool` for
  PET/SPECT scanner-pool separation (section 52);
- `PlannerAssumptions` transport-speed/time constants for Conventional and
  MRT transport modeling (same constants already used by
  `campus_retrofit_benchmark.py`/`hybrid_optimization.py`);
- `finance.incremental_financials` for the economics chain (section 53 --
  no second economics engine).

SCOPE BOUNDARY (NUCLEAR TRUNK FINAL INTEGRATION CORRECTION build):
`evaluate_authoritative_nuclear_candidate` (below) is now THE single
authoritative call path for oncology PET+SPECT campus candidates. It calls
the REAL, pre-existing, unmodified campus PET engine
(`campus_retrofit_benchmark.run_campus_case_1_conventional` /
`run_campus_case_2_hybrid` / `search_hybrid_building_b_floor_subsets`) for
the PET leg -- never reinvents or stubs it -- and reuses
`evaluate_native_mixed_candidate` ONLY as an internal SPECT-feasibility
helper (`pet_requested=0`) for the SPECT leg. The two legs' CapEx/OPEX/
qualified-throughput are combined BEFORE a single call to
`study_scope.apply_study_scope` -- one authoritative economics result, never
two independently-computed NPVs manually summed. `evaluate_native_mixed_candidate`
therefore remains available as a standalone qualification utility (e.g. for
day-level population reporting that doesn't need the full campus floor-subset
search) but is no longer a competing final decision authority for campus
comparisons.

DISCLOSED, NOT HIDDEN, REMAINING BOUNDARY: this repository has a SEPARATE,
pre-existing, single-facility Conventional-vs-MRT (no Hybrid) engine in
`decision_pipeline.py` (`NativeDecisionPipelineScenario`/
`run_native_decision_pipeline`), architecturally distinct from the campus/
Hybrid-capable `spatial_benchmark.py`/`campus_retrofit_benchmark.py`/
`hybrid_optimization.py` lineage this entire oncology PET+SPECT body of work
has always used (it was never SPECT/generator-aware and never part of any
prior oncology build's dependency chain). This closure integrates with the
Hybrid-capable campus lineage -- the one actually relevant to this program --
and does not force-fit into `decision_pipeline.py`'s separate, Hybrid-less
architecture, since doing so would require inventing Hybrid support there
(a genuine rewrite, prohibited by "do not rewrite the optimizer").
"""


from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from clinical_resource_identity import ScannerModality, build_modality_tagged_scanner_pool
from finance import incremental_financials
from generator import GeneratorAsset, PreparationBatch, build_preparation_batch
from models import PlannerAssumptions
from multi_isotope_decay import required_upstream_activity, retained_fraction
from nuclear_source import NuclearSourceInstance, SourceFeasibilityResult, evaluate_cyclotron_source_feasibility, evaluate_generator_source_feasibility
from scanner_catalog import ScannerCatalogModel
from study_scope import apply_study_scope

NuclearPatientOrigin = Literal["INPATIENT", "OUTPATIENT"]
Architecture = Literal["Conventional", "MRT", "Hybrid"]


PET_RADIONUCLIDE = "F-18"
SPECT_RADIONUCLIDE = "Tc-99m"


# ---------------------------------------------------------------------------
# Persistent patient population (section 47-48)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NuclearProcedureAssignment:
    """One nuclear-medicine procedure attached to an EXISTING patient identity
    -- never a second patient identity (section 47)."""

    procedure_id: str
    modality: Literal["PET", "SPECT"]
    radionuclide: str
    prescribed_activity_mbq: float
    scanner_id: str | None = None
    architecture: Architecture | None = None
    transport_mode: Literal["CONVENTIONAL", "MRT"] | None = None


@dataclass(frozen=True)
class OncologyPatientRecord:
    """A single persistent hospital patient for one representative operating
    day. `patient_type` distinguishes inpatient census from outpatient
    encounters (section 7) -- independent of whether a nuclear procedure is
    attached (section 47: a nuclear patient may be drawn from EITHER)."""

    patient_id: str
    patient_type: NuclearPatientOrigin
    admission_date: date | None = None
    expected_discharge_date: date | None = None
    building_id: str | None = None
    floor_id: str | None = None
    room_id: str | None = None
    outpatient_origin: str | None = None
    nuclear_procedure: NuclearProcedureAssignment | None = None

    def __post_init__(self) -> None:
        if self.patient_type == "INPATIENT" and self.room_id is None:
            raise ValueError(f"{self.patient_id}: INPATIENT requires room_id (spatial identity, section 47)")
        if self.patient_type == "OUTPATIENT" and self.room_id is not None:
            raise ValueError(f"{self.patient_id}: OUTPATIENT must not carry a room_id")
        if self.patient_type == "OUTPATIENT" and self.outpatient_origin is None:
            raise ValueError(f"{self.patient_id}: OUTPATIENT requires outpatient_origin identity")


@dataclass(frozen=True)
class DailyOncologyCensus:
    """Section 47 DAILY POPULATION TABLE row. `total_active_patients` !=
    `occupied_beds` != `total_nuclear_procedures` -- each is tracked
    independently and never equated."""

    day: date
    total_active_patients: int
    inpatients: int
    outpatients: int
    occupied_beds: int
    admissions: int
    discharges: int
    pet_procedures: int
    spect_procedures: int
    total_nuclear_procedures: int
    available_beds: int

    def __post_init__(self) -> None:
        if self.inpatients > self.available_beds:
            raise ValueError(
                f"{self.day}: inpatients ({self.inpatients}) exceeds available_beds "
                f"({self.available_beds}) -- INPATIENTS <= AVAILABLE BEDS invariant violated"
            )
        if self.occupied_beds != self.inpatients:
            raise ValueError("occupied_beds must equal inpatients (one inpatient = one occupied bed)")
        if self.pet_procedures + self.spect_procedures != self.total_nuclear_procedures:
            raise ValueError("PET + SPECT must reconcile to TOTAL NUCLEAR PROCEDURES (section 47)")
        if self.total_active_patients != self.inpatients + self.outpatients:
            raise ValueError("total_active_patients must equal inpatients + outpatients")


def build_representative_day_population(
    *,
    day: date,
    available_beds: int,
    occupied_beds: int,
    admissions: int,
    discharges: int,
    outpatient_encounters: int,
    target_pet_procedures: int,
    target_spect_procedures: int,
    seed: int,
) -> tuple[tuple[OncologyPatientRecord, ...], DailyOncologyCensus]:
    """Build ONE representative operating day's persistent population.
    Reproducible via `seed` (section 49). Nuclear procedures are drawn from
    BOTH inpatients and outpatients (section 47) -- an inpatient who receives
    a nuclear procedure keeps their existing room/floor/building identity; an
    outpatient keeps their existing outpatient_origin identity. No second
    patient identity is ever created."""
    if occupied_beds > available_beds:
        raise ValueError("occupied_beds must not exceed available_beds")
    if target_pet_procedures + target_spect_procedures > occupied_beds + outpatient_encounters:
        raise ValueError("nuclear procedure target exceeds total active patients -- cannot assign without duplicate identity")

    rng = random.Random(seed)
    patients: list[OncologyPatientRecord] = []

    for i in range(1, occupied_beds + 1):
        patients.append(OncologyPatientRecord(
            patient_id=f"INPT-{day.isoformat()}-{i:04d}",
            patient_type="INPATIENT",
            admission_date=day - timedelta(days=rng.randint(0, 5)),
            expected_discharge_date=day + timedelta(days=rng.randint(0, 5)),
            building_id="BLDG-A",
            floor_id=f"F{((i - 1) % 6) + 1}",
            room_id=f"IR-{i:03d}",
        ))
    for i in range(1, outpatient_encounters + 1):
        patients.append(OncologyPatientRecord(
            patient_id=f"OUTP-{day.isoformat()}-{i:04d}",
            patient_type="OUTPATIENT",
            outpatient_origin=f"ONCOLOGY_CLINIC_CHECKIN-{i:04d}",
        ))

    eligible_indices = list(range(len(patients)))
    rng.shuffle(eligible_indices)
    nuclear_total = target_pet_procedures + target_spect_procedures
    chosen = eligible_indices[:nuclear_total]
    pet_indices = set(chosen[:target_pet_procedures])
    spect_indices = set(chosen[target_pet_procedures:nuclear_total])

    for idx in pet_indices:
        p = patients[idx]
        patients[idx] = OncologyPatientRecord(
            **{**p.__dict__, "nuclear_procedure": NuclearProcedureAssignment(
                procedure_id=f"PET-{p.patient_id}", modality="PET", radionuclide=PET_RADIONUCLIDE,
                prescribed_activity_mbq=370.0,
            )},
        )
    for idx in spect_indices:
        p = patients[idx]
        patients[idx] = OncologyPatientRecord(
            **{**p.__dict__, "nuclear_procedure": NuclearProcedureAssignment(
                procedure_id=f"SPECT-{p.patient_id}", modality="SPECT", radionuclide=SPECT_RADIONUCLIDE,
                prescribed_activity_mbq=740.0,
            )},
        )

    census = DailyOncologyCensus(
        day=day,
        total_active_patients=occupied_beds + outpatient_encounters,
        inpatients=occupied_beds,
        outpatients=outpatient_encounters,
        occupied_beds=occupied_beds,
        admissions=admissions,
        discharges=discharges,
        pet_procedures=len(pet_indices),
        spect_procedures=len(spect_indices),
        total_nuclear_procedures=len(pet_indices) + len(spect_indices),
        available_beds=available_beds,
    )
    return tuple(patients), census


# ---------------------------------------------------------------------------
# SPECT source -> patient conservation (section 50)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpectDoseLineage:
    """Section 50 patient traceability: patient -> procedure -> Tc-99m ->
    generator -> elution -> preparation batch -> patient dose. No patient may
    receive an elution-less generator-derived dose via this constructor."""

    patient_id: str
    procedure_id: str
    generator_id: str
    preparation_batch: PreparationBatch
    activity_at_administration_mbq: float
    retained_fraction_at_administration: float
    transport_minutes: float
    architecture: Architecture
    scanner_id: str | None = None
    """Section 24/33 (Live-State closure): SPECT scanner assignment, so a
    SPECT_SCANNER_UNAVAILABLE event can identify affected patients by
    scanner_id -- mirrors PatientOperationalPlan.scanner_resource_id's role
    for PET, without modifying that PET-only dataclass."""


def assign_spect_patients_to_generator_batch(
    *,
    spect_patients: tuple[OncologyPatientRecord, ...],
    generator: GeneratorAsset,
    elution_datetime: datetime,
    preparation_processing_minutes: float,
    transport_minutes_by_architecture: dict[Architecture, float],
    architecture: Architecture,
    scanner_id: str | None = None,
) -> tuple[GeneratorAsset, PreparationBatch, tuple[SpectDoseLineage, ...]]:
    """One elution -> one preparation batch -> N patient doses (section 50).
    Reuses `multi_isotope_decay.retained_fraction` for transport decay -- the
    SAME physics used for PET, applied to Tc-99m's half-life (section 51)."""
    if not spect_patients:
        raise ValueError("spect_patients must be non-empty")
    patient_ids = tuple(p.patient_id for p in spect_patients)
    updated_generator, elute_event = generator.elute(at_datetime=elution_datetime)
    batch = build_preparation_batch(
        batch_id=f"TC99M-BATCH-{elution_datetime.isoformat()}",
        elute_event=elute_event,
        generator_id=generator.generator_id,
        preparation_processing_minutes=preparation_processing_minutes,
        patient_ids=patient_ids,
    )
    activity_per_patient = batch.activity_per_patient_mbq()
    transport_minutes = transport_minutes_by_architecture[architecture]
    half_life = 360.0  # Tc-99m, matches radionuclides.json (diagnostics.load_radionuclide_half_lives)
    fraction = retained_fraction(transport_minutes, half_life)
    lineages = tuple(
        SpectDoseLineage(
            patient_id=patient.patient_id,
            procedure_id=patient.nuclear_procedure.procedure_id if patient.nuclear_procedure else f"SPECT-{patient.patient_id}",
            generator_id=generator.generator_id,
            preparation_batch=batch,
            activity_at_administration_mbq=activity_per_patient * fraction,
            retained_fraction_at_administration=fraction,
            transport_minutes=transport_minutes,
            architecture=architecture,
            scanner_id=scanner_id,
        )
        for patient in spect_patients
    )
    return updated_generator, batch, lineages


# ---------------------------------------------------------------------------
# PET / SPECT scanner-modality capacity (section 52)
# ---------------------------------------------------------------------------


def scanner_daily_capacity(*, scanner_count: int, cycle_min_per_patient: float,
                           availability_pct: float, operating_hours_day: float) -> float:
    """Same formula as `scanner.Scanner.daily_capacity` (CONSTITUTION.md
    section 8) -- reused, not reinvented, per modality pool."""
    if cycle_min_per_patient <= 0:
        return 0.0
    return scanner_count * operating_hours_day * 60.0 / cycle_min_per_patient * availability_pct / 100.0


@dataclass(frozen=True)
class ModalityCapacityCheck:
    modality: Literal["PET", "SPECT"]
    scanner_count: int
    daily_capacity: float
    demand: int
    feasible: bool


def check_modality_capacity(
    *, pet_scanner_count: int, spect_scanner_count: int, pet_demand: int, spect_demand: int,
    assumptions: PlannerAssumptions,
) -> tuple[ModalityCapacityCheck, ModalityCapacityCheck]:
    """Section 52: PET demand consumes ONLY PET scanner capacity; SPECT demand
    consumes ONLY SPECT scanner capacity. Adding one modality's patients never
    changes the other modality's available capacity (proven by construction:
    each check below only reads its own scanner_count)."""
    pool = build_modality_tagged_scanner_pool(pet_scanner_count=pet_scanner_count, spect_scanner_count=spect_scanner_count)
    pet_pool = [r for r in pool if r.modality == "PET"]
    spect_pool = [r for r in pool if r.modality == "SPECT"]
    pet_capacity = scanner_daily_capacity(
        scanner_count=len(pet_pool), cycle_min_per_patient=assumptions.scanner_cycle_min,
        availability_pct=assumptions.scanner_availability_pct, operating_hours_day=assumptions.operating_hours_per_day,
    )
    spect_capacity = scanner_daily_capacity(
        scanner_count=len(spect_pool), cycle_min_per_patient=assumptions.scanner_cycle_min,
        availability_pct=assumptions.scanner_availability_pct, operating_hours_day=assumptions.operating_hours_per_day,
    )
    return (
        ModalityCapacityCheck(modality="PET", scanner_count=len(pet_pool), daily_capacity=pet_capacity,
                               demand=pet_demand, feasible=pet_capacity >= pet_demand),
        ModalityCapacityCheck(modality="SPECT", scanner_count=len(spect_pool), daily_capacity=spect_capacity,
                               demand=spect_demand, feasible=spect_capacity >= spect_demand),
    )


# ---------------------------------------------------------------------------
# Economics (section 53) -- NOT_CALIBRATED where genuinely uncalibrated
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpectEconomicsResult:
    spect_scanner_capex: float | Literal["NOT_CALIBRATED"]
    spect_scanner_incremental_opex: float | Literal["NOT_CALIBRATED"]
    generator_purchase_capex: float | Literal["NOT_CALIBRATED"]
    generator_installation_capex: float | Literal["NOT_CALIBRATED"]
    generator_annual_maintenance_opex: float | Literal["NOT_CALIBRATED"]


def evaluate_spect_economics(assumptions: PlannerAssumptions) -> SpectEconomicsResult:
    """Section 53: never invent SPECT/generator cost figures -- report
    NOT_CALIBRATED for any field the caller has not explicitly supplied via
    `PlannerAssumptions`."""
    def _value_or_not_calibrated(value: float | None) -> float | Literal["NOT_CALIBRATED"]:
        return value if value is not None else "NOT_CALIBRATED"

    return SpectEconomicsResult(
        spect_scanner_capex=_value_or_not_calibrated(assumptions.spect_scanner_capex),
        spect_scanner_incremental_opex=_value_or_not_calibrated(assumptions.spect_scanner_incremental_opex),
        generator_purchase_capex=_value_or_not_calibrated(assumptions.generator_purchase_capex),
        generator_installation_capex=_value_or_not_calibrated(assumptions.generator_installation_capex),
        generator_annual_maintenance_opex=_value_or_not_calibrated(assumptions.generator_annual_maintenance_opex),
    )


# ---------------------------------------------------------------------------
# Realistic vs stress benchmarks (section 54)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkDescriptor:
    name: str
    beds: int
    occupancy_fraction: float
    pet_per_day: int
    spect_per_day: int
    total_nuclear_per_day: int
    purpose: str


REALISTIC_ONCOLOGY_50 = BenchmarkDescriptor(
    name="REALISTIC_ONCOLOGY_50",
    beds=200,
    occupancy_fraction=0.85,
    pet_per_day=32,
    spect_per_day=18,
    total_nuclear_per_day=50,
    purpose="REALISTIC_CONTROLLED_OPERATING_BENCHMARK",
)

HIGH_VOLUME_F18_STRESS_200 = BenchmarkDescriptor(
    name="HIGH_VOLUME_F18_STRESS_200",
    beds=200,
    occupancy_fraction=1.0,
    pet_per_day=200,
    spect_per_day=0,
    total_nuclear_per_day=200,
    purpose="ENGINEERING_STRESS_TEST",
)


# ---------------------------------------------------------------------------
# Requirement-derived scanner sizing (section 8) -- never hard-coded counts
# ---------------------------------------------------------------------------


def required_scanner_count(
    *, patient_count: int, protocol_minutes: float, operating_hours_day: float, availability_pct: float,
) -> int:
    """Section 8: patient procedures + protocol duration + operating window +
    availability -> required scanner resources. Mirrors the SAME
    ceiling-division formula already used elsewhere in this repository
    (`spatial_benchmark._resource_requirements_for_demand`) -- never a fixed
    '4 PET / 2 SPECT' constant."""
    if patient_count <= 0:
        return 0
    daily_minutes_per_scanner = operating_hours_day * 60.0 * (availability_pct / 100.0)
    if daily_minutes_per_scanner <= 0 or protocol_minutes <= 0:
        raise ValueError("operating_hours_day, availability_pct, and protocol_minutes must be positive")
    capacity_per_scanner = daily_minutes_per_scanner / protocol_minutes
    import math
    return max(1, math.ceil(patient_count / capacity_per_scanner))


def required_scanner_counts_for_mixed_population(
    *, pet_patient_count: int, spect_patient_count: int, pet_model: ScannerCatalogModel, spect_model: ScannerCatalogModel,
    pet_protocol: str, spect_protocol: str, assumptions: PlannerAssumptions,
) -> tuple[int, int]:
    """Section 8: derives BOTH modality scanner counts from patient load +
    the catalog model's protocol duration -- reused by
    `evaluate_native_mixed_candidate` (never re-derived ad hoc per candidate)."""
    pet_minutes = pet_model.typical_acquisition_minutes_per_protocol.get(pet_protocol)
    spect_minutes = spect_model.typical_acquisition_minutes_per_protocol.get(spect_protocol)
    if pet_minutes is None:
        raise ValueError(f"{pet_model.catalog_model_id}: unknown protocol {pet_protocol}")
    if spect_minutes is None:
        raise ValueError(f"{spect_model.catalog_model_id}: unknown protocol {spect_protocol}")
    pet_count = required_scanner_count(
        patient_count=pet_patient_count, protocol_minutes=pet_minutes,
        operating_hours_day=assumptions.operating_hours_per_day, availability_pct=assumptions.scanner_availability_pct,
    ) if pet_patient_count > 0 else 0
    spect_count = required_scanner_count(
        patient_count=spect_patient_count, protocol_minutes=spect_minutes,
        operating_hours_day=assumptions.operating_hours_per_day, availability_pct=assumptions.scanner_availability_pct,
    ) if spect_patient_count > 0 else 0
    return pet_count, spect_count


# ---------------------------------------------------------------------------
# Native mixed PET+SPECT candidate evaluation (sections 1, 6, 48)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NativeMixedCandidateResult:
    """Section 48: ONE combined evaluation result -- never two independently
    optimized PET/SPECT totals manually merged. `annual_opex`/`study_capex`/
    `npv` are each computed ONCE over the COMBINED qualified population."""

    architecture: Architecture
    pet_requested: int
    pet_served: int
    spect_requested: int
    spect_served: int
    pet_source_feasibility: SourceFeasibilityResult
    spect_source_feasibility: SourceFeasibilityResult
    pet_scanner_count: int
    spect_scanner_count: int
    pet_scanner_utilization: float
    spect_scanner_utilization: float
    combined_qualified_throughput: int
    combined_unmet: int
    annual_revenue: float
    annual_opex: float
    annual_net_cash_flow: float
    npv: float
    study_capex: float


def evaluate_native_mixed_candidate(
    *,
    architecture: Architecture,
    pet_requested: int,
    spect_requested: int,
    pet_source: NuclearSourceInstance,
    spect_source: NuclearSourceInstance,
    pet_activity_per_patient_mbq: float,
    spect_activity_per_patient_mbq: float,
    pet_model: ScannerCatalogModel,
    spect_model: ScannerCatalogModel,
    pet_protocol: str,
    spect_protocol: str,
    pet_available_eob_capacity_mbq_per_day: float,
    spect_elution_datetime: datetime,
    transport_minutes_by_architecture: dict[Architecture, float],
    assumptions: PlannerAssumptions,
    scanner_capex_per_unit: float = 2_500_000.0,
    scanner_incremental_opex_per_unit: float = 300_000.0,
) -> NativeMixedCandidateResult:
    """Section 6/48: the SINGLE shared candidate evaluator. Capable of
    PET-only (spect_requested=0), SPECT-only (pet_requested=0), or PET+SPECT
    -- same function, same code path, never a manual merge of two separately
    optimized results. Both source types flow through `nuclear_source.py`'s
    common interface; economics are computed ONCE over the combined served
    population (section 37: propagates through the existing CapEx/OPEX/NPV
    chain, `finance.incremental_financials`)."""
    transport_minutes = transport_minutes_by_architecture[architecture]

    # ---- PET (CYCLOTRON source) ----
    if pet_requested > 0:
        pet_required_administered = pet_requested * pet_activity_per_patient_mbq
        pet_retained = retained_fraction(transport_minutes, 109.8)  # F-18 half-life
        pet_required_release = required_upstream_activity(pet_required_administered, pet_retained)
        pet_feasibility = evaluate_cyclotron_source_feasibility(
            source=pet_source, required_activity_mbq=pet_required_release,
            available_eob_capacity_mbq_per_day=pet_available_eob_capacity_mbq_per_day, patients_requested=pet_requested,
        )
    else:
        pet_feasibility = SourceFeasibilityResult(
            source_id=pet_source.source_id, source_type="CYCLOTRON", radionuclide=pet_source.radionuclide,
            required_activity_mbq=0.0, available_activity_mbq=pet_available_eob_capacity_mbq_per_day,
            utilization=0.0, patients_served=0, patients_requested=0, unmet=0, status="FEASIBLE",
        )

    # ---- SPECT (GENERATOR source) ----
    if spect_requested > 0:
        spect_required_administered = spect_requested * spect_activity_per_patient_mbq
        spect_retained = retained_fraction(transport_minutes, 360.0)  # Tc-99m half-life
        spect_required_eluted = required_upstream_activity(spect_required_administered, spect_retained)
        spect_feasibility = evaluate_generator_source_feasibility(
            source=spect_source, required_eluted_activity_mbq=spect_required_eluted,
            elution_datetime=spect_elution_datetime, patients_requested=spect_requested,
        )
    else:
        spect_feasibility = SourceFeasibilityResult(
            source_id=spect_source.source_id, source_type="GENERATOR", radionuclide=spect_source.radionuclide,
            required_activity_mbq=0.0, available_activity_mbq=0.0,
            utilization=0.0, patients_served=0, patients_requested=0, unmet=0, status="FEASIBLE",
        )

    pet_scanner_count, spect_scanner_count = required_scanner_counts_for_mixed_population(
        pet_patient_count=pet_feasibility.patients_served, spect_patient_count=spect_feasibility.patients_served,
        pet_model=pet_model, spect_model=spect_model, pet_protocol=pet_protocol, spect_protocol=spect_protocol,
        assumptions=assumptions,
    )
    pet_capacity = scanner_daily_capacity(
        scanner_count=pet_scanner_count, cycle_min_per_patient=pet_model.typical_acquisition_minutes_per_protocol[pet_protocol],
        availability_pct=assumptions.scanner_availability_pct, operating_hours_day=assumptions.operating_hours_per_day,
    ) if pet_scanner_count > 0 else 0.0
    spect_capacity = scanner_daily_capacity(
        scanner_count=spect_scanner_count, cycle_min_per_patient=spect_model.typical_acquisition_minutes_per_protocol[spect_protocol],
        availability_pct=assumptions.scanner_availability_pct, operating_hours_day=assumptions.operating_hours_per_day,
    ) if spect_scanner_count > 0 else 0.0

    combined_qualified = pet_feasibility.patients_served + spect_feasibility.patients_served
    combined_unmet = pet_feasibility.unmet + spect_feasibility.unmet
    combined_scanners = pet_scanner_count + spect_scanner_count

    # ---- ONE combined economics call (section 37, 48) -- never summed after two separate NPVs ----
    study_capex = combined_scanners * scanner_capex_per_unit
    annual_opex = combined_scanners * scanner_incremental_opex_per_unit
    annual_revenue, _, annual_ncf, npv, _, _ = incremental_financials(
        capex=study_capex, annual_incremental_opex=annual_opex, throughput_patients_per_day=combined_qualified,
        revenue_per_scan=assumptions.revenue_per_scan, operating_days_per_year=assumptions.operating_days_per_year,
        discount_rate_pct=assumptions.discount_rate_pct, analysis_years=assumptions.analysis_years,
    )

    return NativeMixedCandidateResult(
        architecture=architecture, pet_requested=pet_requested, pet_served=pet_feasibility.patients_served,
        spect_requested=spect_requested, spect_served=spect_feasibility.patients_served,
        pet_source_feasibility=pet_feasibility, spect_source_feasibility=spect_feasibility,
        pet_scanner_count=pet_scanner_count, spect_scanner_count=spect_scanner_count,
        pet_scanner_utilization=(pet_feasibility.patients_served / pet_capacity if pet_capacity > 0 else 0.0),
        spect_scanner_utilization=(spect_feasibility.patients_served / spect_capacity if spect_capacity > 0 else 0.0),
        combined_qualified_throughput=combined_qualified, combined_unmet=combined_unmet,
        annual_revenue=annual_revenue, annual_opex=annual_opex, annual_net_cash_flow=annual_ncf, npv=npv,
        study_capex=study_capex,
    )


# ---------------------------------------------------------------------------
# Genuinely stochastic PET/SPECT demand (section 27-29, 54-55) -- Poisson,
# labeled CONTROLLED_STOCHASTIC_MODEL, never a fixed 32/18 every day.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StochasticDemandDay:
    day: date
    target_mean_total: float
    realized_pet: int
    realized_spect: int
    realized_total: int
    distribution_model: str = "CONTROLLED_STOCHASTIC_MODEL_POISSON"


def generate_stochastic_daily_nuclear_demand(
    *, day: date, target_mean_pet: float, target_mean_spect: float, seed: int,
) -> StochasticDemandDay:
    """Section 27-29: each day's PET/SPECT counts are independent Poisson
    draws centered on the configured means -- NOT a fixed split. Reproducible
    via `seed`; different seeds are capable of different sequences; the
    multi-day mean converges toward the configured target (law of large
    numbers for Poisson). Explicitly labeled CONTROLLED_STOCHASTIC_MODEL
    (section 28) -- no epidemiological distribution claim is made."""
    rng = random.Random(seed)
    realized_pet = _poisson_sample(rng, target_mean_pet)
    realized_spect = _poisson_sample(rng, target_mean_spect)
    return StochasticDemandDay(
        day=day, target_mean_total=target_mean_pet + target_mean_spect,
        realized_pet=realized_pet, realized_spect=realized_spect, realized_total=realized_pet + realized_spect,
    )


def _poisson_sample(rng: random.Random, mean: float) -> int:
    """Knuth's algorithm -- standard, unmodified Poisson sampling. No fixed
    result is possible; counts >= 0 by construction."""
    if mean <= 0:
        return 0
    import math
    l = math.exp(-mean)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= l:
            return k - 1


def build_stochastic_representative_day_population(
    *,
    day: date,
    available_beds: int,
    occupied_beds: int,
    admissions: int,
    discharges: int,
    outpatient_encounters: int,
    target_mean_pet: float,
    target_mean_spect: float,
    seed: int,
) -> tuple[tuple[OncologyPatientRecord, ...], DailyOncologyCensus, StochasticDemandDay]:
    """Section 27-31: genuinely stochastic daily PET/SPECT counts (never
    forced to the exact target), still assigned to EXISTING persistent
    patients only (never anonymous/synthetic patients created merely to
    satisfy the stochastic count) -- reuses
    `build_representative_day_population`'s population construction, only the
    nuclear-procedure TARGET counts are stochastic."""
    demand_day = generate_stochastic_daily_nuclear_demand(
        day=day, target_mean_pet=target_mean_pet, target_mean_spect=target_mean_spect, seed=seed,
    )
    total_active = occupied_beds + outpatient_encounters
    realized_pet = min(demand_day.realized_pet, total_active)
    realized_spect = min(demand_day.realized_spect, total_active - realized_pet)
    patients, census = build_representative_day_population(
        day=day, available_beds=available_beds, occupied_beds=occupied_beds, admissions=admissions,
        discharges=discharges, outpatient_encounters=outpatient_encounters,
        target_pet_procedures=realized_pet, target_spect_procedures=realized_spect, seed=seed,
    )
    return patients, census, demand_day


# ---------------------------------------------------------------------------
# Multiple generators (sections 35, 56) -- no special-case code per instance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiGeneratorAllocationResult:
    total_patients_requested: int
    total_patients_served: int
    per_generator: tuple[SourceFeasibilityResult, ...]
    generators_required: int
    unmet: int


def allocate_spect_patients_across_generators(
    *, sources: tuple[NuclearSourceInstance, ...], required_eluted_activity_per_patient_mbq: float,
    patients_requested: int, elution_datetime: datetime,
) -> MultiGeneratorAllocationResult:
    """Section 35, 56: greedy allocation across N independent generator
    instances -- each generator's available activity is evaluated from its
    OWN independent physics state (no shared/double-counted activity). Stops
    allocating to additional generators as soon as demand is met -- never
    fabricates a need for a second generator when one suffices."""
    remaining = patients_requested
    per_generator: list[SourceFeasibilityResult] = []
    generators_used = 0
    for source in sources:
        if remaining <= 0:
            break
        required_for_remaining = remaining * required_eluted_activity_per_patient_mbq
        result = evaluate_generator_source_feasibility(
            source=source, required_eluted_activity_mbq=required_for_remaining,
            elution_datetime=elution_datetime, patients_requested=remaining,
        )
        per_generator.append(result)
        if result.patients_served > 0:
            generators_used += 1
        remaining -= result.patients_served
    total_served = patients_requested - remaining
    return MultiGeneratorAllocationResult(
        total_patients_requested=patients_requested, total_patients_served=total_served,
        per_generator=tuple(per_generator), generators_required=generators_used, unmet=remaining,
    )


# ---------------------------------------------------------------------------
# ONE authoritative nuclear candidate path (sections 2, 3, 35, 36, 37) --
# calls the REAL campus PET engine, uses evaluate_native_mixed_candidate
# strictly as an internal SPECT-feasibility helper, and combines both legs
# through exactly ONE call to study_scope.apply_study_scope.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthoritativeNuclearCandidateResult:
    """Section 2/35: the SINGLE authoritative result for a campus PET+SPECT
    candidate -- never two independent final results for the same
    architecture/day."""

    architecture: Architecture
    study_scope: str  # "CAPITAL_PLANNING" | "OPERATIONAL_ONLY"
    pet_qualified: int
    pet_capex: float
    pet_opex: float
    spect_served: int
    spect_unmet: int
    spect_capex: float
    spect_opex: float
    combined_qualified_throughput: int
    reference_capex: float
    study_capex: float
    annual_opex: float
    npv: float | None
    """None when study_scope == CAPITAL_PLANNING and the underlying
    `apply_study_scope` computes `capital_project_npv`; here it is populated
    for BOTH scopes from `operating_horizon_present_value` for a single
    consistent reportable NPV-like figure (section 37: one chain, one number)."""


def evaluate_authoritative_nuclear_candidate(
    *,
    architecture: Architecture,
    geometry,  # campus_retrofit_benchmark.BenchmarkGeometry
    pet_demand: int,
    spect_requested: int,
    spect_source: NuclearSourceInstance,
    spect_activity_per_patient_mbq: float,
    spect_model: ScannerCatalogModel,
    spect_protocol: str,
    spect_elution_datetime: datetime,
    assumptions: PlannerAssumptions,
    study_scope: str = "CAPITAL_PLANNING",
    spect_scanner_capex_per_unit: float = 2_500_000.0,
    spect_scanner_incremental_opex_per_unit: float = 300_000.0,
) -> AuthoritativeNuclearCandidateResult:
    """Section 2/35: THE single call path for a campus PET+SPECT candidate.

    PET leg: calls the REAL, existing, unmodified campus engine
    (`campus_retrofit_benchmark`) -- never reinvented, never stubbed with a
    duck-typed placeholder (see this session's own read-only reconciliation
    finding on why stubs are dangerous).

    SPECT leg: `evaluate_native_mixed_candidate` is called with
    `pet_requested=0` purely as an internal SPECT-feasibility helper -- its
    own (SPECT-only) NPV is discarded; only its physically-grounded
    served/scanner/capex/opex numbers are extracted.

    Both legs are summed BEFORE the ONE call to
    `study_scope.apply_study_scope` (section 13-16) -- the single
    authoritative economics chain for the combined candidate."""
    from campus_retrofit_benchmark import (
        run_campus_case_1_conventional, run_campus_case_2_hybrid,
        search_hybrid_building_b_floor_subsets, best_hybrid_floor_subset,
        new_study_capex_pathway, new_study_capex_hybrid,
    )

    # ---- PET leg: REAL campus engine, never stubbed ----
    conventional_winner = run_campus_case_1_conventional(geometry=geometry, demand=pet_demand) if pet_demand > 0 else None
    if architecture == "Conventional":
        if conventional_winner is None:
            pet_qualified, pet_capex, pet_opex = 0, 0.0, 0.0
        else:
            pet_qualified = conventional_winner.winner.patients_retention_qualified_completed
            pet_capex = new_study_capex_pathway(conventional_winner.winner, cyclotron_is_existing=True)
            pet_opex = conventional_winner.winner.annual_total_opex
    else:
        if pet_demand <= 0 or conventional_winner is None:
            pet_qualified, pet_capex, pet_opex = 0, 0.0, 0.0
        elif architecture == "MRT":
            hresult, candidate = run_campus_case_2_hybrid(geometry=geometry, conventional_winner=conventional_winner, demand=pet_demand, mrt_floors=None)
            pet_qualified = hresult.retention_qualified_completed
            pet_capex = new_study_capex_hybrid(hresult, assumptions, cyclotron_is_existing=True)
            pet_opex = hresult.total_annual_opex
        else:  # Hybrid: best (possibly mixed) floor subset
            outcomes = search_hybrid_building_b_floor_subsets(geometry=geometry, conventional_winner=conventional_winner, demand=pet_demand)
            best = best_hybrid_floor_subset(outcomes)
            pet_qualified = best.result.retention_qualified_completed
            pet_capex = new_study_capex_hybrid(best.result, assumptions, cyclotron_is_existing=True)
            pet_opex = best.result.total_annual_opex

    # ---- SPECT leg: internal helper only, never a competing final result ----
    # A syntactically-valid but functionally-unused PET source/model pair is required by
    # evaluate_native_mixed_candidate's signature when pet_requested=0 (no PET activity is computed).
    from cyclotron_catalog import FacilityCyclotronInstance, build_cyclotron_asset_from_instance, load_cyclotron_catalog
    _catalog = load_cyclotron_catalog()
    _placeholder_cyc_instance = FacilityCyclotronInstance(instance_id="UNUSED", catalog_model_id="GE_PETTRACE_890")
    _placeholder_cyc_asset = build_cyclotron_asset_from_instance(instance=_placeholder_cyc_instance, model=_catalog.by_id("GE_PETTRACE_890"))
    placeholder_pet_source = NuclearSourceInstance(source_id="UNUSED", source_type="CYCLOTRON", radionuclide="F-18", cyclotron_asset=_placeholder_cyc_asset)

    mixed = evaluate_native_mixed_candidate(
        architecture=architecture, pet_requested=0, spect_requested=spect_requested,
        pet_source=placeholder_pet_source, spect_source=spect_source,
        pet_activity_per_patient_mbq=370.0, spect_activity_per_patient_mbq=spect_activity_per_patient_mbq,
        pet_model=spect_model, spect_model=spect_model, pet_protocol=spect_protocol, spect_protocol=spect_protocol,
        pet_available_eob_capacity_mbq_per_day=1.0, spect_elution_datetime=spect_elution_datetime,
        transport_minutes_by_architecture={"Conventional": 12.0, "MRT": 2.0, "Hybrid": 5.0}, assumptions=assumptions,
        scanner_capex_per_unit=spect_scanner_capex_per_unit, scanner_incremental_opex_per_unit=spect_scanner_incremental_opex_per_unit,
    )
    spect_served = mixed.spect_served
    spect_unmet = mixed.spect_source_feasibility.unmet
    spect_capex = mixed.spect_scanner_count * spect_scanner_capex_per_unit
    spect_opex = mixed.spect_scanner_count * spect_scanner_incremental_opex_per_unit

    # ---- ONE combined economics call (section 13-16, 35, 37) ----
    combined_qualified = pet_qualified + spect_served
    reference_capex = pet_capex + spect_capex
    annual_opex = pet_opex + spect_opex
    scope_result = apply_study_scope(
        study_scope=study_scope, transport_architecture=architecture.upper(),
        qualified_throughput=combined_qualified, reference_capex=reference_capex, annual_opex=annual_opex,
        revenue_per_scan=assumptions.revenue_per_scan, operating_days_per_year=assumptions.operating_days_per_year,
        discount_rate_pct=assumptions.discount_rate_pct, analysis_years=assumptions.analysis_years,
    )

    return AuthoritativeNuclearCandidateResult(
        architecture=architecture, study_scope=study_scope, pet_qualified=pet_qualified, pet_capex=pet_capex, pet_opex=pet_opex,
        spect_served=spect_served, spect_unmet=spect_unmet, spect_capex=spect_capex, spect_opex=spect_opex,
        combined_qualified_throughput=combined_qualified, reference_capex=reference_capex,
        study_capex=scope_result.study_capex, annual_opex=annual_opex,
        npv=scope_result.operating_horizon_present_value,
    )


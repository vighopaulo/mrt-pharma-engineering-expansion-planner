"""Mo-99/Tc-99m Generator + Elution Physics.

GOVERNANCE-FIRST BUILD (mirrors CONSTITUTION.md section 7): this module adds
ONE new physical source authority -- a radionuclide generator producing a
short-lived daughter (Tc-99m) from a longer-lived parent (Mo-99) -- alongside
the existing cyclotron-batch authority (`cyclotron.py`, `production_engine.py`).
It reuses `radionuclide.py`/`multi_isotope_decay.py`'s existing exponential
decay physics for TRANSPORT decay; it adds ONLY the parent-daughter GROWTH
physics that governs how much Tc-99m activity is available to elute at any
given moment. No existing decay/production/scanner engine is modified or
duplicated.

PHYSICS (standard Bateman two-member secular/transient-equilibrium generator
equation, textbook nuclear-medicine physics -- not fabricated):

    A_daughter(dt) = A_parent(t_ref) * lambda_d / (lambda_d - lambda_p)
                     * (exp(-lambda_p * dt) - exp(-lambda_d * dt))

where `A_parent(t_ref)` is the Mo-99 activity AT THE REFERENCE TIME (the last
elution, or calibration if never eluted), `dt` is elapsed minutes since that
reference time, and `lambda_p`/`lambda_d` are the parent/daughter decay
constants (ln(2)/half_life_min). Elution removes only the daughter (Tc-99m);
the parent (Mo-99) decays continuously and independently of elution events.

An elution never recovers 100% of the available daughter activity -- an
`elution_efficiency` fraction (PROJECT_ASSUMPTION, not measured for any real
generator model in this repository) is extracted; the remainder stays in the
column and continues to be included in the next growth cycle's calculation
(since Mo-99 decay, not the residual Tc-99m, drives subsequent regrowth via
the `A_parent(t_ref)` term -- the standard generator equation already reflects
this because the un-eluted residual is negligible compared to the ongoing
parent-driven ingrowth).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

_LN2 = math.log(2.0)

MO99_HALF_LIFE_MIN = 3956.4  # 65.94 hours -- physical constant (OBSERVED_DATA)
TC99M_HALF_LIFE_MIN = 360.0  # 6.0 hours -- matches radionuclides.json entry


def _decay_constant(half_life_min: float) -> float:
    if half_life_min <= 0:
        raise ValueError("half_life_min must be positive")
    return _LN2 / half_life_min


def mo99_activity_mbq(*, calibration_activity_mbq: float, elapsed_min: float) -> float:
    """Mo-99 parent activity `elapsed_min` after calibration. Elution does not
    affect this value -- the parent decays independently of daughter removal."""
    if calibration_activity_mbq < 0:
        raise ValueError("calibration_activity_mbq must be non-negative")
    if elapsed_min < 0:
        raise ValueError("elapsed_min must be non-negative")
    lambda_p = _decay_constant(MO99_HALF_LIFE_MIN)
    return calibration_activity_mbq * math.exp(-lambda_p * elapsed_min)


def tc99m_available_activity_mbq(*, parent_activity_at_reference_mbq: float, minutes_since_reference: float) -> float:
    """Tc-99m activity available in the generator `minutes_since_reference`
    after the reference point (last elution, or calibration if none yet),
    given the Mo-99 activity AT that reference point. Standard Bateman
    two-member generator equation (see module docstring)."""
    if parent_activity_at_reference_mbq < 0:
        raise ValueError("parent_activity_at_reference_mbq must be non-negative")
    if minutes_since_reference < 0:
        raise ValueError("minutes_since_reference must be non-negative")
    lambda_p = _decay_constant(MO99_HALF_LIFE_MIN)
    lambda_d = _decay_constant(TC99M_HALF_LIFE_MIN)
    dt = minutes_since_reference
    growth_factor = (lambda_d / (lambda_d - lambda_p)) * (math.exp(-lambda_p * dt) - math.exp(-lambda_d * dt))
    return parent_activity_at_reference_mbq * growth_factor


@dataclass(frozen=True)
class EluteEvent:
    """Section 55 required coverage: 'repeat elution behavior'. One elution
    draws `eluted_activity_mbq` (= available Tc-99m x elution_efficiency) at
    `elution_datetime`, leaving the column's daughter clock reset to zero."""

    elution_datetime: datetime
    available_activity_mbq_before_elution: float
    elution_efficiency: float
    eluted_activity_mbq: float
    residual_activity_mbq_in_column: float


@dataclass(frozen=True)
class GeneratorAsset:
    """A single physical Mo-99/Tc-99m generator (section 55: 'multi-day
    generator persistence', 'calendar-day radioactive evolution'). Immutable --
    each elution returns a NEW `GeneratorAsset` with updated reference state
    (functional-state-update pattern, consistent with other frozen dataclasses
    in this repository, e.g. `CyclotronCalendar`)."""

    generator_id: str
    calibration_datetime: datetime
    calibration_mo99_activity_mbq: float
    elution_efficiency: float = 0.85  # PROJECT_ASSUMPTION -- typical clinical generator column extraction fraction
    last_reference_datetime: datetime | None = None
    """None until the first elution: growth is measured from calibration."""

    def __post_init__(self) -> None:
        if not self.generator_id.strip():
            raise ValueError("generator_id must be non-empty")
        if self.calibration_mo99_activity_mbq <= 0:
            raise ValueError("calibration_mo99_activity_mbq must be positive")
        if not (0.0 < self.elution_efficiency <= 1.0):
            raise ValueError("elution_efficiency must be within (0, 1]")
        if self.last_reference_datetime is not None and self.last_reference_datetime < self.calibration_datetime:
            raise ValueError("last_reference_datetime must not precede calibration_datetime")

    def _reference_datetime(self) -> datetime:
        return self.last_reference_datetime or self.calibration_datetime

    def _reference_mo99_activity_mbq(self) -> float:
        """Mo-99 activity AT the reference point (last elution or calibration)
        -- this is the parent activity the Bateman equation grows from."""
        reference = self._reference_datetime()
        elapsed_since_calibration = (reference - self.calibration_datetime).total_seconds() / 60.0
        return mo99_activity_mbq(
            calibration_activity_mbq=self.calibration_mo99_activity_mbq, elapsed_min=elapsed_since_calibration,
        )

    def available_tc99m_activity_mbq(self, *, at_datetime: datetime) -> float:
        """Tc-99m activity available for elution at `at_datetime` (must be at
        or after the current reference point -- calendar-day evolution)."""
        reference = self._reference_datetime()
        if at_datetime < reference:
            raise ValueError("at_datetime must not precede the last elution/calibration reference")
        minutes_since_reference = (at_datetime - reference).total_seconds() / 60.0
        return tc99m_available_activity_mbq(
            parent_activity_at_reference_mbq=self._reference_mo99_activity_mbq(),
            minutes_since_reference=minutes_since_reference,
        )

    def elute(self, *, at_datetime: datetime) -> tuple["GeneratorAsset", EluteEvent]:
        """Perform one elution at `at_datetime`. Returns the UPDATED generator
        (daughter clock reset to this elution) and the `EluteEvent` record.
        Repeatable: calling `.elute()` again on the returned asset models the
        next elution cycle (section 55: 'repeat elution behavior')."""
        available = self.available_tc99m_activity_mbq(at_datetime=at_datetime)
        eluted = available * self.elution_efficiency
        residual = available - eluted
        updated = GeneratorAsset(
            generator_id=self.generator_id,
            calibration_datetime=self.calibration_datetime,
            calibration_mo99_activity_mbq=self.calibration_mo99_activity_mbq,
            elution_efficiency=self.elution_efficiency,
            last_reference_datetime=at_datetime,
        )
        event = EluteEvent(
            elution_datetime=at_datetime,
            available_activity_mbq_before_elution=available,
            elution_efficiency=self.elution_efficiency,
            eluted_activity_mbq=eluted,
            residual_activity_mbq_in_column=residual,
        )
        return updated, event


@dataclass(frozen=True)
class PreparationBatch:
    """Section 55: 'preparation-batch patient allocation'. An elution's eluted
    activity is compounded into ONE preparation batch (mirrors the existing
    cyclotron-batch pattern in `patient_radionuclide_demand.py`'s
    `RadionuclideBatchDemand`, but sourced from an `EluteEvent` instead of a
    cyclotron release)."""

    batch_id: str
    source_generator_id: str
    elution_datetime: datetime
    eluted_activity_mbq: float
    preparation_processing_minutes: float
    patient_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.batch_id.strip():
            raise ValueError("batch_id must be non-empty")
        if self.eluted_activity_mbq <= 0:
            raise ValueError("eluted_activity_mbq must be positive")
        if self.preparation_processing_minutes < 0:
            raise ValueError("preparation_processing_minutes must be non-negative")
        if not self.patient_ids:
            raise ValueError("PreparationBatch requires at least one patient_id")

    def release_datetime(self) -> datetime:
        """Section 55: 'Tc-99m transport decay' begins after preparation
        completes -- release timestamp = elution + preparation processing."""
        return self.elution_datetime + timedelta(minutes=self.preparation_processing_minutes)

    def activity_per_patient_mbq(self) -> float:
        return self.eluted_activity_mbq / len(self.patient_ids)


def build_preparation_batch(
    *, batch_id: str, elute_event: EluteEvent, generator_id: str,
    preparation_processing_minutes: float, patient_ids: tuple[str, ...],
) -> PreparationBatch:
    """Section 50: source -> patient conservation for Tc-99m -- one elution
    yields exactly one preparation batch allocated to a named set of patients
    (no batch-less or elution-less dose is possible via this constructor)."""
    return PreparationBatch(
        batch_id=batch_id,
        source_generator_id=generator_id,
        elution_datetime=elute_event.elution_datetime,
        eluted_activity_mbq=elute_event.eluted_activity_mbq,
        preparation_processing_minutes=preparation_processing_minutes,
        patient_ids=patient_ids,
    )

"""Cyclotron Production Estimation Authority (OG-CYC-1 closure).

PURPOSE
-------
MRT Pharma is a simulation / planning system. A simulation frequently needs a
*numerical* production estimate (required EOB activity, irradiation duration,
physical cycles/batches, utilization, schedule/economic feasibility) even where
manufacturer / site production output for a cyclotron model x radionuclide pair
is `NOT_CALIBRATED`.

This authority is the explicit, separate layer that distinguishes:

    WHAT IS PHYSICALLY SUPPORTED
        (a cyclotron declares it can make this radionuclide)
    from WHAT IS CALIBRATED
        (manufacturer / site production evidence exists)
    from WHAT MRT PHARMA CAN NUMERICALLY ESTIMATE
        (a defensible physics/evidence-based estimate can be constructed).

It creates NO second cyclotron catalog, NO second radionuclide authority, and
NO second production-capacity resolver. It sits BETWEEN existing production
evidence (Build 3B `cyclotron_catalog` / `cyclotron_equipment_catalog.json`) and
downstream batch / capacity planning.

CANONICAL EVIDENCE HIERARCHY (governance-locked, `MRT_PHARMA_AUTHORITY_INDEX.md`)
--------------------------------------------------------------------------------
    SITE_CALIBRATED
      > MANUFACTURER_CALIBRATED
      > MODELED_ESTIMATE
      > CONTROLLED_ASSUMPTION
      > NOT_AVAILABLE

These are NOT interchangeable. A numerical estimate NEVER overwrites the
manufacturer / site calibration status or the raw manufacturer evidence: the
result preserves BOTH the evidence status AND the numerical value.

    MODELED_ESTIMATE  !=  MANUFACTURER_CALIBRATED  !=  SITE_CALIBRATED
    SUPPORTED         !=  CALIBRATED               !=  NUMERICALLY ESTIMABLE

A supported radionuclide may still carry `calibration_status = NOT_CALIBRATED`
and `estimation_status = NOT_AVAILABLE` when insufficient evidence exists. The
correct fallback is `NOT_AVAILABLE`, never a fabricated number.

ESTIMATION METHOD (physics / evidence first)
--------------------------------------------
Production is estimated ONLY from physical / evidence-based quantities. It is
NEVER derived from patients/day, historical usable doses/day, legacy 10%
production blocks, revenue, scanner capacity, or transport capacity.

The single defensible modeled relationship available from the physical
repository is the saturation activation form already encoded in
`cyclotron_catalog.calculate_eob_activity_from_calibrated_record`:

    A_EOB(I, t) = K * I * (1 - exp(-lambda * t))

where lambda = ln(2) / half_life. The yield constant `K` is NOT fabricated: it
is fit from that model x radionuclide's OWN manufacturer-calibrated anchor
record (beam current I_cal, irradiation time t_cal, normalized EOB A_cal):

    K = A_cal / (I_cal * (1 - exp(-lambda * t_cal)))

This makes the estimate an *irradiation-time response* anchored on the pair's
own calibration -- a MODELED_ESTIMATE, never a borrowed capacity from another
model or radionuclide.

RADIONUCLIDE SPECIFICITY
------------------------
Every estimate is specific to (cyclotron model x radionuclide). A calibrated /
estimated F-18 result can NEVER qualify C-11, N-13, O-15, Ga-68, Cu-64, Zr-89,
I-123, I-124, Tc-99m or any other radionuclide. The anchor record is matched on
`record.radionuclide == radionuclide` only.

BOUNDARIES
----------
- Generator production (e.g. Mo-99 -> Tc-99m) is OUT OF SCOPE. Tc-99m and other
  generator daughters resolve to `estimation_status = OUT_OF_CYCLOTRON_SCOPE`;
  the cyclotron saturation equation is never applied to generator output.
- No patient identity is accepted anywhere in this API (Sections 14, 21, 34):
  the estimator consumes engineering production requirements only.
- Excess estimated production is HEADROOM, never new patients / procedures /
  revenue (Section 45): this module produces no demand.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Sequence

import cyclotron_catalog as _cc
import generator_catalog as _gc
from diagnostics import load_radionuclide_half_lives


# ---------------------------------------------------------------------------
# Canonical vocabularies
# ---------------------------------------------------------------------------

EvidenceClass = Literal[
    "SITE_CALIBRATED",
    "MANUFACTURER_CALIBRATED",
    "MODELED_ESTIMATE",
    "CONTROLLED_ASSUMPTION",
    "NOT_AVAILABLE",
]

# Runtime precedence for the evidence hierarchy (higher = stronger authority).
_EVIDENCE_PRECEDENCE: dict[str, int] = {
    "SITE_CALIBRATED": 5,
    "MANUFACTURER_CALIBRATED": 4,
    "MODELED_ESTIMATE": 3,
    "CONTROLLED_ASSUMPTION": 2,
    "NOT_AVAILABLE": 1,
}

EstimationStatus = Literal[
    "AVAILABLE",              # a numerical production basis (calibrated OR modeled) exists
    "NOT_AVAILABLE",          # supported but no defensible numerical basis
    "NO_COMPATIBLE_SOURCE",   # the model does not support this radionuclide
    "OUT_OF_CYCLOTRON_SCOPE",  # radionuclide is a generator daughter, not cyclotron-produced here
]

# Minimal confidence vocabulary (Section 38). No canonical repo confidence
# scoring system exists, so this is deliberately small and explicitly
# documented. Confidence NEVER changes SUPPORTED or CALIBRATION status.
ConfidenceClass = Literal["HIGH", "MEDIUM", "LOW", "NOT_ASSESSED"]

# The cyclotron production-status vocabulary mirrored from Build 3B
# (`CyclotronCatalogModel.production_calibration_status`).
CalibrationStatus = Literal[
    "manufacturer_calibrated",
    "site_calibrated",
    "literature_calibrated",
    "modeled",
    "not_calibrated",
]


# ---------------------------------------------------------------------------
# Result contracts (Section 33)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CyclotronProductionEstimate:
    """Canonical estimator result. Carries BOTH the evidence classification AND
    the numerical value so downstream code can never confuse a MODELED_ESTIMATE
    with a MANUFACTURER_CALIBRATED / SITE_CALIBRATED value or with NOT_AVAILABLE.
    """

    catalog_model_id: str
    manufacturer: str
    model: str
    radionuclide: str

    supported: bool
    calibration_status: CalibrationStatus
    """The Build 3B manufacturer/site calibration evidence status for this pair.
    This is NEVER altered by the presence of a MODELED_ESTIMATE."""

    production_basis: EvidenceClass
    """The runtime production basis a simulation should use for this pair."""

    estimated_or_calibrated_eob_mbq: float | None
    """The numerical EOB activity (MBq) for the requested conditions, or None
    when `estimation_status != AVAILABLE`."""

    irradiation_minutes: float | None
    production_cycle_minutes: float | None

    evidence_class: EvidenceClass
    """Equal to `production_basis`; named separately for downstream clarity."""

    confidence: ConfidenceClass
    provenance: str
    raw_evidence_reference: str | None
    limitations: tuple[str, ...]
    estimation_status: EstimationStatus

    evidence_record_id: str | None = None
    """The stable id of the Cyclotron Production Evidence Registry record used to
    build a MODELED_ESTIMATE from external/physics evidence (Section 28). None for
    calibrated / NOT_AVAILABLE / NO_COMPATIBLE_SOURCE / OUT_OF_CYCLOTRON_SCOPE
    results, which are resolved without the registry."""

    source_reference: str | None = None
    """A human-readable citation for the evidence record used (title + url), so a
    consumer can identify the provenance of a MODELED_ESTIMATE without re-reading
    the registry. None when no registry record was used."""

    def has_numerical_value(self) -> bool:
        return self.estimated_or_calibrated_eob_mbq is not None and self.estimation_status == "AVAILABLE"

    def is_calibrated(self) -> bool:
        return self.production_basis in ("SITE_CALIBRATED", "MANUFACTURER_CALIBRATED")

    def is_modeled(self) -> bool:
        return self.production_basis == "MODELED_ESTIMATE"


@dataclass(frozen=True)
class CyclotronBatchCycleEstimate:
    """Physical batch/cycle requirement derived from a production estimate and a
    required EOB activity (Sections 13, 35). PHYSICAL CYCLE != PATIENT COHORT."""

    radionuclide: str
    catalog_model_id: str
    required_eob_activity_mbq: float
    production_per_cycle_mbq: float
    required_cycles: int
    production_basis: EvidenceClass
    provenance: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _half_life_minutes(radionuclide: str) -> float | None:
    table = load_radionuclide_half_lives()
    value = table.get(radionuclide)
    return None if value is None else float(value)


def _decay_lambda(radionuclide: str) -> float | None:
    hl = _half_life_minutes(radionuclide)
    if hl is None or hl <= 0.0:
        return None
    return math.log(2.0) / hl


def _generator_daughter_radionuclides() -> frozenset[str]:
    try:
        gcat = _gc.load_generator_catalog()
    except Exception:
        return frozenset()
    return frozenset(m.daughter_radionuclide for m in gcat.models)


def _manufacturer_calibrated_anchor(
    model: "_cc.CyclotronCatalogModel", radionuclide: str
) -> "_cc.ProductionPerformanceRecord | None":
    """The calibrated GROUND-TRUTH anchor record for THIS pair: a
    manufacturer-calibrated record with a normalized EOB and an irradiation
    time. Matched on radionuclide only (never borrowing another isotope's
    record). This anchor is sufficient to report the calibrated value AT its
    calibrated condition, even if the record's beam current is not published."""
    candidates = [
        r
        for r in model.production_performance_records
        if r.radionuclide == radionuclide
        and r.calibration_status == "manufacturer_calibrated"
        and r.normalized_eob_activity_mbq is not None
        and r.irradiation_time_minutes is not None
        and float(r.irradiation_time_minutes) > 0.0
    ]
    return candidates[0] if candidates else None


def _can_fit_saturation(anchor: "_cc.ProductionPerformanceRecord | None") -> bool:
    """A saturation-model MODELED_ESTIMATE (irradiation-time response) can be fit
    ONLY when the anchor also publishes a positive beam current. Without it, the
    yield constant K cannot be derived and no estimate is fabricated."""
    return (
        anchor is not None
        and anchor.beam_current_ua is not None
        and float(anchor.beam_current_ua) > 0.0
    )


def _fit_yield_constant(
    *, anchor: "_cc.ProductionPerformanceRecord", decay_lambda: float
) -> float | None:
    """K = A_cal / (I_cal * (1 - exp(-lambda * t_cal))). Not fabricated: derived
    from the pair's own calibrated anchor. Returns None if degenerate."""
    i_cal = float(anchor.beam_current_ua)  # type: ignore[arg-type]
    t_cal = float(anchor.irradiation_time_minutes)  # type: ignore[arg-type]
    a_cal = float(anchor.normalized_eob_activity_mbq)  # type: ignore[arg-type]
    saturation = 1.0 - math.exp(-decay_lambda * t_cal)
    denom = i_cal * saturation
    if denom <= 0.0:
        return None
    return a_cal / denom


# ---------------------------------------------------------------------------
# Cyclotron Production Evidence Registry (external / physics evidence seam)
# ---------------------------------------------------------------------------
#
# The registry is a SEPARATE, additive store of external/physics production
# evidence (`cyclotron_production_evidence.json`) that the estimator may consume
# ONLY as a MODELED_ESTIMATE basis where no manufacturer/site-calibrated
# production record exists. It NEVER holds manufacturer/site-calibrated output
# (that stays in Build 3B `cyclotron_equipment_catalog.json`) and NEVER changes a
# model's calibration status. Missing/malformed file -> empty registry (the
# estimator's behavior is then byte-identical to before this seam existed).

_EVIDENCE_REGISTRY_FILENAME = "cyclotron_production_evidence.json"

# Confidence ranking for the multi-evidence resolver (Section 27). This orders
# competing records; it never changes SUPPORTED or CALIBRATION status.
_CONFIDENCE_RANK: dict[str, int] = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NOT_ASSESSED": 0}


@dataclass(frozen=True)
class ProductionEvidenceRecord:
    """One traceable registry record. Raw evidence is preserved verbatim
    (`raw_value`/`raw_unit`) alongside the normalized canonical form."""

    evidence_record_id: str
    evidence_kind: str  # REACTION_SATURATION_YIELD | MACHINE_SPECIFIC_EOB
    catalog_model_id: str | None  # None => reaction-level physics (machine-agnostic)
    radionuclide: str
    reaction: str | None
    beam_current_ua: float | None
    raw_value: float | None
    raw_unit: str | None
    saturation_yield_mbq_per_ua: float | None
    eob_activity_mbq: float | None
    evidence_class: EvidenceClass
    confidence: ConfidenceClass
    reference_irradiation_minutes: float | None
    normalization_method: str | None
    source_title: str | None
    source_url: str | None
    source_type: str | None
    limitations: tuple[str, ...]

    @property
    def source_reference(self) -> str:
        title = self.source_title or "unattributed"
        return f"{title}" + (f" <{self.source_url}>" if self.source_url else "")


def _coerce_float(value: object) -> float | None:
    return None if value is None else float(value)  # type: ignore[arg-type]


def _parse_evidence_record(payload: dict) -> ProductionEvidenceRecord:
    normalized = dict(payload.get("normalized", {}) or {})
    source = dict(payload.get("source", {}) or {})
    return ProductionEvidenceRecord(
        evidence_record_id=str(payload["evidence_record_id"]),
        evidence_kind=str(payload.get("evidence_kind", "")),
        catalog_model_id=(None if payload.get("catalog_model_id") is None else str(payload.get("catalog_model_id"))),
        radionuclide=str(payload.get("radionuclide", "")),
        reaction=(None if payload.get("reaction") is None else str(payload.get("reaction"))),
        beam_current_ua=_coerce_float(payload.get("beam_current_ua")),
        raw_value=_coerce_float(payload.get("raw_value")),
        raw_unit=(None if payload.get("raw_unit") is None else str(payload.get("raw_unit"))),
        saturation_yield_mbq_per_ua=_coerce_float(normalized.get("saturation_yield_mbq_per_ua")),
        eob_activity_mbq=_coerce_float(normalized.get("eob_activity_mbq")),
        evidence_class=str(payload.get("evidence_class", "NOT_AVAILABLE")),  # type: ignore[assignment]
        confidence=str(payload.get("confidence", "NOT_ASSESSED")),  # type: ignore[assignment]
        reference_irradiation_minutes=_coerce_float(payload.get("reference_irradiation_minutes")),
        normalization_method=(None if payload.get("normalization_method") is None else str(payload.get("normalization_method"))),
        source_title=(None if source.get("title") is None else str(source.get("title"))),
        source_url=(None if source.get("url") is None else str(source.get("url"))),
        source_type=(None if source.get("source_type") is None else str(source.get("source_type"))),
        limitations=tuple(str(x) for x in (payload.get("limitations", []) or [])),
    )


_EVIDENCE_REGISTRY_CACHE: tuple[ProductionEvidenceRecord, ...] | None = None


def load_production_evidence_registry(*, force_reload: bool = False) -> tuple[ProductionEvidenceRecord, ...]:
    """Load the Cyclotron Production Evidence Registry. Missing/malformed file
    yields an EMPTY registry (never raises), so the estimator degrades to its
    pre-seam behavior when no external evidence is present."""
    global _EVIDENCE_REGISTRY_CACHE
    if _EVIDENCE_REGISTRY_CACHE is not None and not force_reload:
        return _EVIDENCE_REGISTRY_CACHE
    import json
    from pathlib import Path

    path = Path(__file__).with_name(_EVIDENCE_REGISTRY_FILENAME)
    records: list[ProductionEvidenceRecord] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for raw in payload.get("evidence_records", []):
            records.append(_parse_evidence_record(dict(raw)))
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        records = []
    _EVIDENCE_REGISTRY_CACHE = tuple(records)
    return _EVIDENCE_REGISTRY_CACHE


def resolve_evidence_registry_records(
    catalog_model_id: str, radionuclide: str
) -> tuple[ProductionEvidenceRecord, ...]:
    """All registry records applicable to (model x radionuclide): machine-specific
    records naming this model, PLUS reaction-level (catalog_model_id is None)
    records for this radionuclide. Radionuclide match is exact (no cross-
    radionuclide borrowing)."""
    return tuple(
        r
        for r in load_production_evidence_registry()
        if r.radionuclide == radionuclide
        and (r.catalog_model_id is None or r.catalog_model_id == catalog_model_id)
    )


@dataclass(frozen=True)
class EvidenceResolution:
    """The outcome of the multi-evidence resolver (Section 27): the single chosen
    record, WHY it was chosen, and the competing records (never silently
    averaged/discarded)."""

    chosen: ProductionEvidenceRecord | None
    selection_reason: str
    competing_record_ids: tuple[str, ...]


def resolve_evidence_record(catalog_model_id: str, radionuclide: str) -> EvidenceResolution:
    """Choose ONE evidence record for a pair from possibly several (Section 27).
    Never silently averages competing records. Deterministic ranking:
      1. evidence-class precedence (`stronger_basis`);
      2. machine-specific over reaction-level (more specific wins);
      3. confidence (HIGH > MEDIUM > LOW);
      4. stable evidence_record_id (tie-break for reproducibility).
    The competing records are preserved so a consumer can audit the choice."""
    candidates = resolve_evidence_registry_records(catalog_model_id, radionuclide)
    if not candidates:
        return EvidenceResolution(chosen=None, selection_reason="no applicable evidence records", competing_record_ids=())

    def sort_key(r: ProductionEvidenceRecord) -> tuple:
        return (
            _EVIDENCE_PRECEDENCE.get(r.evidence_class, 0),
            1 if r.catalog_model_id is not None else 0,
            _CONFIDENCE_RANK.get(r.confidence, 0),
            r.evidence_record_id,
        )

    ranked = sorted(candidates, key=sort_key, reverse=True)
    chosen = ranked[0]
    reason = (
        f"selected {chosen.evidence_record_id} "
        f"(class={chosen.evidence_class}, "
        f"{'machine-specific' if chosen.catalog_model_id is not None else 'reaction-level'}, "
        f"confidence={chosen.confidence}) over {len(ranked) - 1} competing record(s) "
        f"by evidence-class precedence, specificity, then confidence -- competing records preserved, never averaged."
    )
    return EvidenceResolution(
        chosen=chosen,
        selection_reason=reason,
        competing_record_ids=tuple(r.evidence_record_id for r in ranked),
    )


# ---------------------------------------------------------------------------
# Primary authority API
# ---------------------------------------------------------------------------

def estimate_cyclotron_production(
    catalog_model_id: str,
    radionuclide: str,
    *,
    irradiation_minutes: float | None = None,
) -> CyclotronProductionEstimate:
    """Resolve the production basis for one (cyclotron model x radionuclide).

    The API accepts ONLY engineering inputs (model, radionuclide, optional
    irradiation duration). It NEVER accepts patient identity (Sections 14/21/34).

    Runtime precedence (Section 40):
      SITE_CALIBRATED > MANUFACTURER_CALIBRATED > MODELED_ESTIMATE >
      CONTROLLED_ASSUMPTION > NOT_AVAILABLE.

    Returns a fully-populated `CyclotronProductionEstimate`. When no defensible
    numerical basis exists the result is honest `NOT_AVAILABLE` /
    `NO_COMPATIBLE_SOURCE` / `OUT_OF_CYCLOTRON_SCOPE`, never a fabricated number.
    """
    catalog = _cc.load_cyclotron_catalog()
    model = catalog.by_id(catalog_model_id)  # raises KeyError for an unknown id
    manufacturer = model.manufacturer
    model_name = model.model
    calibration_status: CalibrationStatus = model.production_calibration_status

    def _result(
        *,
        supported: bool,
        production_basis: EvidenceClass,
        eob: float | None,
        irr: float | None,
        cycle: float | None,
        confidence: ConfidenceClass,
        provenance: str,
        raw_ref: str | None,
        limitations: Sequence[str],
        estimation_status: EstimationStatus,
        evidence_record_id: str | None = None,
        source_reference: str | None = None,
    ) -> CyclotronProductionEstimate:
        return CyclotronProductionEstimate(
            catalog_model_id=catalog_model_id,
            manufacturer=manufacturer,
            model=model_name,
            radionuclide=radionuclide,
            supported=supported,
            calibration_status=calibration_status,
            production_basis=production_basis,
            estimated_or_calibrated_eob_mbq=eob,
            irradiation_minutes=irr,
            production_cycle_minutes=cycle,
            evidence_class=production_basis,
            confidence=confidence,
            provenance=provenance,
            raw_evidence_reference=raw_ref,
            limitations=tuple(limitations),
            estimation_status=estimation_status,
            evidence_record_id=evidence_record_id,
            source_reference=source_reference,
        )

    # --- Generator-daughter boundary (Sections 16/17). Tc-99m et al. are not a
    # cyclotron-estimation concern; the cyclotron equations are never applied. ---
    if radionuclide in _generator_daughter_radionuclides() and radionuclide not in model.supported_radionuclides:
        return _result(
            supported=False,
            production_basis="NOT_AVAILABLE",
            eob=None,
            irr=None,
            cycle=None,
            confidence="NOT_ASSESSED",
            provenance=(
                f"{radionuclide} is a generator daughter radionuclide; cyclotron production "
                f"estimation does not apply. Resolve via the generator authority."
            ),
            raw_ref=None,
            limitations=(
                "Generator production is a separate authority (OG-GEN-1); cyclotron "
                "saturation equations are never applied to generator output.",
            ),
            estimation_status="OUT_OF_CYCLOTRON_SCOPE",
        )

    # --- Support check (radionuclide-specific). ---
    supported = radionuclide in model.supported_radionuclides
    if not supported:
        return _result(
            supported=False,
            production_basis="NOT_AVAILABLE",
            eob=None,
            irr=None,
            cycle=None,
            confidence="NOT_ASSESSED",
            provenance=f"{model_name} does not declare support for {radionuclide}.",
            raw_ref=None,
            limitations=(
                f"No compatible cyclotron production source: {model_name} does not "
                f"support {radionuclide}.",
            ),
            estimation_status="NO_COMPATIBLE_SOURCE",
        )

    cycle_minutes = model.production_cycle_minutes_by_radionuclide.get(radionuclide)
    anchor = _manufacturer_calibrated_anchor(model, radionuclide)
    decay_lambda = _decay_lambda(radionuclide)

    # --- Calibrated ground truth (Section 7). If a manufacturer-calibrated
    # anchor exists and the query is AT its calibrated irradiation condition
    # (or no override irradiation time is requested), the calibrated value is
    # authoritative and no estimate overrides it. ---
    if anchor is not None:
        t_cal = float(anchor.irradiation_time_minutes)  # type: ignore[arg-type]
        at_calibrated_condition = irradiation_minutes is None or abs(float(irradiation_minutes) - t_cal) <= 1e-9
        raw_ref = (
            f"{anchor.source}"
            + (f" (rev {anchor.source_revision})" if anchor.source_revision else "")
            + f": {anchor.radionuclide} "
            f"{anchor.beam_current_ua} uA / {anchor.irradiation_time_minutes} min -> "
            f"{anchor.normalized_eob_activity_mbq} MBq"
        )
        if at_calibrated_condition:
            return _result(
                supported=True,
                production_basis="MANUFACTURER_CALIBRATED",
                eob=float(anchor.normalized_eob_activity_mbq),  # type: ignore[arg-type]
                irr=t_cal,
                cycle=cycle_minutes,
                confidence="HIGH",
                provenance=(
                    f"Manufacturer-calibrated EOB for {model_name} + {radionuclide} at the "
                    f"published calibration condition ({anchor.beam_current_ua} uA, {t_cal} min)."
                ),
                raw_ref=raw_ref,
                limitations=(
                    "Calibration input only; not an unconditional facility MBq/day capacity.",
                ),
                estimation_status="AVAILABLE",
            )

        # --- Irradiation-time response MODELED_ESTIMATE (Section 12). The
        # calibration status stays manufacturer_calibrated; the returned BASIS
        # for a *different* irradiation time is a MODELED_ESTIMATE anchored on
        # the pair's own calibration -- never a borrowed capacity. ---
        # A saturation fit requires the anchor's beam current. When the
        # calibrated record does not publish one (e.g. a source-published
        # condition without a universal single-target current), no defensible
        # irradiation-time estimate can be built -> honest NOT_AVAILABLE.
        if not _can_fit_saturation(anchor):
            return _result(
                supported=True,
                production_basis="NOT_AVAILABLE",
                eob=None,
                irr=float(irradiation_minutes),
                cycle=cycle_minutes,
                confidence="NOT_ASSESSED",
                provenance=(
                    f"{model_name} + {radionuclide} has a calibrated anchor but no published "
                    f"beam current, so the irradiation-time saturation model cannot be fit."
                ),
                raw_ref=raw_ref,
                limitations=(
                    "Calibrated at the anchor condition only; irradiation-time response "
                    "NOT_AVAILABLE without a published beam current to fit the yield constant.",
                ),
                estimation_status="NOT_AVAILABLE",
            )
        if decay_lambda is None:
            return _result(
                supported=True,
                production_basis="NOT_AVAILABLE",
                eob=None,
                irr=float(irradiation_minutes),
                cycle=cycle_minutes,
                confidence="NOT_ASSESSED",
                provenance=(
                    f"{model_name} + {radionuclide} has a calibrated anchor but no canonical "
                    f"half-life physics for irradiation-time modeling."
                ),
                raw_ref=raw_ref,
                limitations=(
                    f"No canonical half-life for {radionuclide}; irradiation-time response "
                    f"cannot be modeled without fabricating decay physics.",
                ),
                estimation_status="NOT_AVAILABLE",
            )
        if float(irradiation_minutes) <= 0.0:
            raise ValueError("irradiation_minutes must be positive when provided")

        yield_k = _fit_yield_constant(anchor=anchor, decay_lambda=decay_lambda)
        if yield_k is None:
            return _result(
                supported=True,
                production_basis="NOT_AVAILABLE",
                eob=None,
                irr=float(irradiation_minutes),
                cycle=cycle_minutes,
                confidence="NOT_ASSESSED",
                provenance=f"Degenerate calibration anchor for {model_name} + {radionuclide}.",
                raw_ref=raw_ref,
                limitations=("Anchor record yields a degenerate saturation constant.",),
                estimation_status="NOT_AVAILABLE",
            )
        i_cal = float(anchor.beam_current_ua)  # type: ignore[arg-type]
        modeled_eob = yield_k * i_cal * (1.0 - math.exp(-decay_lambda * float(irradiation_minutes)))
        return _result(
            supported=True,
            production_basis="MODELED_ESTIMATE",
            eob=float(modeled_eob),
            irr=float(irradiation_minutes),
            cycle=cycle_minutes,
            confidence="MEDIUM",
            provenance=(
                f"Irradiation-time response A_EOB = K*I*(1-exp(-lambda*t)) for {model_name} + "
                f"{radionuclide}; K fit from this pair's manufacturer-calibrated anchor "
                f"(K={yield_k:.6g} MBq/uA, I={i_cal} uA), t={float(irradiation_minutes)} min."
            ),
            raw_ref=raw_ref,
            limitations=(
                "MODELED_ESTIMATE: not manufacturer/site calibration. Assumes the anchor's "
                "beam current and target/reaction conditions; single-point K fit.",
                "Does not model target/beam-current variation beyond the calibrated anchor.",
            ),
            estimation_status="AVAILABLE",
        )

    # --- Supported but NO manufacturer-calibrated anchor in the catalog. Before
    # returning NOT_AVAILABLE, consult the Cyclotron Production Evidence Registry
    # for a defensible MODELED_ESTIMATE basis (external/physics evidence). This is
    # the additive seam: it can NEVER outrank a manufacturer/site anchor (handled
    # above) and NEVER changes calibration_status. ---
    registry_estimate = _try_registry_modeled_estimate(
        model=model,
        radionuclide=radionuclide,
        cycle_minutes=cycle_minutes,
        decay_lambda=decay_lambda,
        irradiation_minutes=irradiation_minutes,
        result=_result,
    )
    if registry_estimate is not None:
        return registry_estimate

    # --- No manufacturer anchor AND no applicable registry evidence (e.g.
    # SUMITOMO_CYPRIS_MP_30 + F-18: empty records, no OWN published beam current,
    # no machine-specific evidence). Honest NOT_AVAILABLE. Never borrow another
    # model's capacity; never fabricate (Section 15). ---
    return _result(
        supported=True,
        production_basis="NOT_AVAILABLE",
        eob=None,
        irr=irradiation_minutes,
        cycle=cycle_minutes,
        confidence="NOT_ASSESSED",
        provenance=(
            f"{model_name} supports {radionuclide} but the repository holds no "
            f"manufacturer-calibrated anchor and no applicable production-evidence-registry "
            f"record (with this model's own beam current) for this pair, so no defensible "
            f"numerical estimate can be constructed."
        ),
        raw_ref=None,
        limitations=(
            "SUPPORTED but NOT_CALIBRATED and estimation NOT_AVAILABLE: no beam current / "
            "target-yield anchor evidence exists for this pair.",
            "No borrowing of another model's or radionuclide's calibrated capacity.",
        ),
        estimation_status="NOT_AVAILABLE",
    )


def _model_own_beam_current_ua(model: "_cc.CyclotronCatalogModel") -> float | None:
    """The model's OWN published beam current (from Build 3B `field_provenance`),
    if any. Used to apply a reaction-level saturation yield to THIS machine
    without borrowing another model's current. Returns None when the model does
    not publish its own beam current."""
    field = model.field_provenance.get("beam_current_ua") if model.field_provenance else None
    if field is None:
        return None
    value = getattr(field, "value", None)
    try:
        current = None if value is None else float(value)
    except (TypeError, ValueError):
        return None
    return current if (current is not None and current > 0.0) else None


def _try_registry_modeled_estimate(
    *,
    model: "_cc.CyclotronCatalogModel",
    radionuclide: str,
    cycle_minutes: float | None,
    decay_lambda: float | None,
    irradiation_minutes: float | None,
    result,
) -> "CyclotronProductionEstimate | None":
    """Attempt a MODELED_ESTIMATE from the Cyclotron Production Evidence Registry.

    Two evidence kinds are honored:
      * MACHINE_SPECIFIC_EOB   -> a machine-specific normalized EOB (used directly).
      * REACTION_SATURATION_YIELD -> reaction physics K applied to THIS model's OWN
        published beam current: A_EOB = K * I_own * (1 - exp(-lambda*t)).

    Returns None (deferring to NOT_AVAILABLE) whenever a defensible estimate
    cannot be built -- e.g. no evidence record, or a reaction-yield record with no
    OWN beam current (SUMITOMO_CYPRIS_MP_30), or missing half-life physics. The
    registry NEVER fabricates a beam current and NEVER borrows another model's."""
    resolution = resolve_evidence_record(model.catalog_model_id, radionuclide)
    record = resolution.chosen
    if record is None:
        return None

    # Registry evidence is only ever a MODELED_ESTIMATE (literature/physics).
    if record.evidence_class != "MODELED_ESTIMATE":
        return None

    if irradiation_minutes is not None and float(irradiation_minutes) <= 0.0:
        raise ValueError("irradiation_minutes must be positive when provided")

    # --- Machine-specific EOB record: use the normalized EOB directly. ---
    if record.evidence_kind == "MACHINE_SPECIFIC_EOB" and record.eob_activity_mbq is not None:
        return result(
            supported=True,
            production_basis="MODELED_ESTIMATE",
            eob=float(record.eob_activity_mbq),
            irr=(irradiation_minutes if irradiation_minutes is not None else record.reference_irradiation_minutes),
            cycle=cycle_minutes,
            confidence=record.confidence,
            provenance=(
                f"MODELED_ESTIMATE for {model.model} + {radionuclide} from machine-specific "
                f"evidence record {record.evidence_record_id}. {resolution.selection_reason}"
            ),
            raw_ref=f"{record.raw_value} {record.raw_unit} ({record.source_reference})",
            limitations=record.limitations + (
                "MODELED_ESTIMATE: not manufacturer/site calibration; calibration status unchanged.",
            ),
            estimation_status="AVAILABLE",
            evidence_record_id=record.evidence_record_id,
            source_reference=record.source_reference,
        )

    # --- Reaction saturation-yield record: physics K applied to THIS model's OWN
    # published beam current. No own current -> defer to NOT_AVAILABLE. ---
    if record.evidence_kind == "REACTION_SATURATION_YIELD" and record.saturation_yield_mbq_per_ua is not None:
        if decay_lambda is None:
            # No canonical half-life physics -> cannot model an irradiation-time
            # response; never fabricate decay physics.
            return None
        own_current = _model_own_beam_current_ua(model)
        if own_current is None:
            # e.g. SUMITOMO_CYPRIS_MP_30 publishes no OWN beam current -> honest
            # NOT_AVAILABLE (no borrowing, no fabrication).
            return None
        t = float(irradiation_minutes) if irradiation_minutes is not None else record.reference_irradiation_minutes
        if t is None or t <= 0.0:
            return None
        k = float(record.saturation_yield_mbq_per_ua)
        modeled_eob = k * own_current * (1.0 - math.exp(-decay_lambda * t))
        # Honest composite confidence: a reaction-level yield applied to a model's
        # OWN (typically literature-grade) beam current is a two-source physics
        # synthesis -> capped at LOW, regardless of the yield record's own
        # (ranking) confidence. Never overstated as MEDIUM/HIGH.
        return result(
            supported=True,
            production_basis="MODELED_ESTIMATE",
            eob=float(modeled_eob),
            irr=t,
            cycle=cycle_minutes,
            confidence="LOW",
            provenance=(
                f"Irradiation-time response A_EOB = Ysat*I*(1-exp(-lambda*t)) for {model.model} + "
                f"{radionuclide}; Ysat={k:.6g} MBq/uA from reaction-physics evidence "
                f"{record.evidence_record_id} ({record.reaction}); I={own_current} uA is THIS model's "
                f"OWN published beam current (never borrowed); t={t} min. {resolution.selection_reason}"
            ),
            raw_ref=f"{record.raw_value} {record.raw_unit} ({record.source_reference})",
            limitations=record.limitations + (
                f"MODELED_ESTIMATE: reaction-level physics applied to {model.model}'s OWN beam "
                f"current ({own_current} uA); not a manufacturer/site EOB measurement; "
                f"calibration status unchanged.",
                "Assumes the reaction operates above threshold at this model's beam energy; "
                "single-target, single operating point; not an unlimited capacity curve.",
            ),
            estimation_status="AVAILABLE",
            evidence_record_id=record.evidence_record_id,
            source_reference=record.source_reference,
        )

    return None


def resolve_simulation_production_basis(
    catalog_model_id: str,
    radionuclide: str,
    *,
    irradiation_minutes: float | None = None,
) -> EvidenceClass:
    """Narrow accessor (Section 20 seam): the runtime production basis a
    simulation should use for (model x radionuclide). Returns one of the
    canonical `EvidenceClass` members. This is the single question downstream
    planning asks the estimator without needing the full result."""
    return estimate_cyclotron_production(
        catalog_model_id, radionuclide, irradiation_minutes=irradiation_minutes
    ).production_basis


def stronger_basis(a: EvidenceClass, b: EvidenceClass) -> EvidenceClass:
    """Return the higher-precedence evidence class (Section 39 promotion order).
    Supports future replacement of a MODELED_ESTIMATE by MANUFACTURER/SITE
    calibration without changing downstream architecture."""
    return a if _EVIDENCE_PRECEDENCE[a] >= _EVIDENCE_PRECEDENCE[b] else b


def estimate_required_physical_cycles(
    catalog_model_id: str,
    radionuclide: str,
    required_eob_activity_mbq: float,
    *,
    irradiation_minutes: float | None = None,
) -> CyclotronBatchCycleEstimate | None:
    """Physical batch/cycle requirement (Sections 13/35). Consumes an
    ENGINEERING required EOB activity (never a patient cohort) and the estimated
    or calibrated production-per-cycle for the pair.

        required_cycles = ceil(required_eob / production_per_cycle)

    Monotonic non-decreasing in `required_eob_activity_mbq` (Proof F): a larger
    required EOB can never yield fewer physical cycles. Returns None when no
    numerical production basis exists (NOT_AVAILABLE / NO_COMPATIBLE_SOURCE /
    OUT_OF_CYCLOTRON_SCOPE) -- never a fabricated cycle count.

    PHYSICAL CYCLOTRON CYCLE != PATIENT COHORT.
    """
    if required_eob_activity_mbq <= 0.0:
        raise ValueError("required_eob_activity_mbq must be positive")

    estimate = estimate_cyclotron_production(
        catalog_model_id, radionuclide, irradiation_minutes=irradiation_minutes
    )
    if not estimate.has_numerical_value():
        return None
    per_cycle = float(estimate.estimated_or_calibrated_eob_mbq)  # type: ignore[arg-type]
    if per_cycle <= 0.0:
        return None
    required_cycles = int(math.ceil(float(required_eob_activity_mbq) / per_cycle))
    return CyclotronBatchCycleEstimate(
        radionuclide=radionuclide,
        catalog_model_id=catalog_model_id,
        required_eob_activity_mbq=float(required_eob_activity_mbq),
        production_per_cycle_mbq=per_cycle,
        required_cycles=required_cycles,
        production_basis=estimate.production_basis,
        provenance=(
            f"required_cycles = ceil({float(required_eob_activity_mbq):.6g} / {per_cycle:.6g}) "
            f"using {estimate.production_basis} production per cycle."
        ),
    )

"""Synthetic Patient Radionuclide Source-Capability Authority (OG-SYNTH-1).

PURPOSE
-------
Close the OG-SYNTH-1 governance gap: normal synthetic patient radionuclide
demand must be constrained *before patient creation* by the radionuclides that
the scenario's **selected** production sources can actually supply. Previously
the representative synthetic generator assigned radionuclides purely by modality
(PET -> "F-18", SPECT -> "Tc-99m") with no reference to selected equipment.

REQUIRED NORMAL-SIMULATION CHAIN (this module supplies the first three links):

    SELECTED PRODUCTION SOURCES
      -> SOURCE-SUPPORTED RADIONUCLIDE SET          (this module)
      -> ADMISSIBLE SYNTHETIC RADIONUCLIDE SET      (this module)
      -> SYNTHETIC PATIENT RADIONUCLIDE REQUIREMENTS (generator seam)
      -> PATIENT-AWARE BATCH-PRODUCTION PLANNING     (unchanged downstream)
      -> PHYSICAL PRODUCTION REQUIREMENT             (unchanged downstream)
      -> CYCLOTRON / GENERATOR AUTHORITY             (unchanged downstream)

AUTHORITY BOUNDARY (what this module does NOT do)
-------------------------------------------------
- It does not redesign the cyclotron estimator, the generator physics, or any
  batch planner.
- It does not make cyclotrons or generators patient-identity-aware. No patient
  id / name / room / appointment / calendar identity is ever passed into a
  catalog capability API here.
- It answers only: CAN THIS SELECTED PHYSICAL SOURCE PRODUCE THIS RADIONUCLIDE
  IN PRINCIPLE (SUPPORT semantics), and is that radionuclide clinically
  recognized for the requested modality. Quantitative production sufficiency
  (capacity, calibration, EOB estimability) is a SEPARATE downstream concern and
  is deliberately NOT consulted here.

SOURCE SUPPORT  !=  QUANTITATIVE PRODUCTION SUFFICIENCY
------------------------------------------------------
A radionuclide is admissible for normal synthetic generation because a selected
source *supports* it (per the catalog's `supported_radionuclides`), even when
its production output is `NOT_CALIBRATED` or its numerical estimate is
`NOT_AVAILABLE`. Example: SUMITOMO_CYPRIS_MP_30 + F-18 is SUPPORTED = YES while
CALIBRATION_STATUS = NOT_CALIBRATED and ESTIMATION_STATUS = NOT_AVAILABLE. That
does not erase the catalog's physical statement that F-18 is supported; it only
means downstream feasibility may report unresolved capacity.

SELECTED-SOURCE SPECIFIC
------------------------
Admissible radionuclides are derived ONLY from the production sources SELECTED /
INSTALLED in the current scenario (the caller-supplied catalog_model_id lists),
never from every machine in the global catalog. A radionuclide supported by some
unrelated catalog machine never becomes admissible merely because that machine
exists in the catalog.

MODALITY AUTHORITY (reused, not invented)
-----------------------------------------
The repository's clinical modality vocabulary is `Literal["PET", "SPECT"]`
(`clinical_resource_identity.ScannerModality`, `nuclear_appointment.NuclearModality`,
`long_horizon_operational_planning.ClinicalModality`). The canonical diagnostic
radionuclide->modality authority is the single
`_CLINICALLY_RECOGNIZED_RADIONUCLIDES_BY_MODALITY` mapping below, also consumed by
`clinical_radionuclide_portfolio`. Following the Clinical Radionuclide
Completeness & Evidence Closure build, every binding is EVIDENCE-GATED against a
traceable record in `clinical_radionuclide_evidence.json` (FDA labeling / SNMMI /
peer-reviewed clinical, classified by emission evidence: positron -> PET, single
gamma photon -> SPECT):

    PET   : F-18, C-11, N-13, O-15, Ga-68, Cu-64, Zr-89, I-124
    SPECT : Tc-99m, I-123, In-111, Tl-201

Radionuclides with NO diagnostic scanner modality are deliberately excluded here
and never invented as admissible imaging demand: `At-211` is a THERAPY (alpha)
radionuclide, and `Ge-68`/`Mo-99` are GENERATOR PARENTS (production feedstock /
calibration source, never patient-administered). Any radionuclide a selected
source supports but that carries no diagnostic modality binding is reported as a
`SUPPORTED_BUT_NOT_CLINICALLY_MODALITY_CLASSIFIED` limitation, never silently
promoted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from cyclotron_catalog import load_cyclotron_catalog
from generator_catalog import load_generator_catalog

Modality = Literal["PET", "SPECT"]
"""Reuses the established repository modality vocabulary -- not a new one."""

SyntheticDemandMode = Literal["NORMAL", "STRESS_TEST"]
"""NORMAL  = source-capability-constrained before patient creation.
STRESS_TEST = deliberately allows an unsupported radionuclide request to be
              preserved so downstream feasibility can expose NO_COMPATIBLE_SOURCE
              (this module never fabricates or substitutes)."""

CapabilityStatus = Literal["ADMISSIBLE", "NO_COMPATIBLE_SOURCE"]

SourceType = Literal["CYCLOTRON", "GENERATOR"]


# ---------------------------------------------------------------------------
# Clinical radionuclide -> modality recognition (REUSED repository authority)
# ---------------------------------------------------------------------------
#
# The canonical repository clinical radionuclide -> DIAGNOSTIC-modality authority.
# This is the single dictionary consumed by BOTH this module and
# `clinical_radionuclide_portfolio._clinical_modality_for` (no competing modality
# table exists anywhere in the repository).
#
# Every binding below is EVIDENCE-GATED: each radionuclide->modality entry is
# backed by a traceable record in `clinical_radionuclide_evidence.json`
# (Clinical Radionuclide Completeness & Evidence Closure build). A radionuclide
# is classified PET vs SPECT by its EMISSION EVIDENCE (positron -> PET, single
# gamma photon -> SPECT), never by its element or by cyclotron support alone.
#
#   PET  (positron-emitter diagnostic agents):
#     F-18    control (mature reference)
#     C-11    FDA Choline C-11 PET (recurrent prostate cancer)        [EV-C11-MOD-001]
#     N-13    FDA Ammonia N-13 PET (myocardial perfusion)             [EV-N13-MOD-001]
#     O-15    [15O]water PET perfusion (peer-reviewed clinical)       [EV-O15-MOD-001]
#     Ga-68   FDA 68Ga-DOTATATE / SNMMI 68Ga-PSMA-11 PET              [EV-GA68-MOD-001]
#     Cu-64   FDA Cu-64 DOTATATE (Detectnet) PET (NET localization)   [EV-CU64-MOD-001]
#     Zr-89   Zr-89 immunoPET (peer-reviewed clinical)                [EV-ZR89-MOD-001]
#     I-124   I-124 immunoPET (peer-reviewed clinical)                [EV-I124-MOD-001]
#   SPECT (single-photon/gamma diagnostic agents):
#     Tc-99m  control (generator daughter)
#     I-123   FDA Sodium Iodide I-123 gamma imaging (159 keV)         [EV-I123-MOD-001]
#     In-111  FDA In-111 pentetreotide (OctreoScan) gamma imaging     [EV-IN111-MOD-001]
#     Tl-201  FDA Thallous Chloride Tl-201 SPECT (myocardial)         [EV-TL201-MOD-001]
#
# DELIBERATELY EXCLUDED from this DIAGNOSTIC-modality authority (evidence-honest,
# NOT an omission):
#   At-211  THERAPY (alpha emitter) — no diagnostic scanner modality; recognized
#           in the evidence registry as a THERAPY radionuclide and must NEVER be
#           forced into PET/SPECT scanner demand.               [EV-AT211-USE-001]
#   Ge-68   GENERATOR PARENT (Ge-68/Ga-68 generator + PET calibration source) —
#           not patient-administered diagnostic demand.               [EV-GE68-HL-001]
#   Mo-99   GENERATOR PARENT (Mo-99/Tc-99m) — production feedstock only.
#
# `Modality` is `Literal["PET", "SPECT"]` by construction, so THERAPY / generator
# parents cannot be represented here — that typed boundary is intentional.
_CLINICALLY_RECOGNIZED_RADIONUCLIDES_BY_MODALITY: Mapping[Modality, frozenset[str]] = {
    "PET": frozenset({"F-18", "C-11", "N-13", "O-15", "Ga-68", "Cu-64", "Zr-89", "I-124"}),
    "SPECT": frozenset({"Tc-99m", "I-123", "In-111", "Tl-201"}),
}


@dataclass(frozen=True)
class RadionuclideSourceBinding:
    """One admissible synthetic radionuclide and the SELECTED source(s) that can
    supply it. Source identities are preserved (never flattened) -- if multiple
    selected sources support the same radionuclide, all of their ids are
    recorded here as a single admissible radionuclide identity with multiple
    compatible sources."""

    radionuclide: str
    source_type: SourceType
    compatible_source_ids: tuple[str, ...]


@dataclass(frozen=True)
class SyntheticRadionuclideCapabilityResult:
    """The source-capability contract consumed by the normal synthetic patient
    generator. Deterministic and order-stable for reproducibility.

    - `admissible_radionuclides`: radionuclides the normal synthetic generator
      MAY assign for this modality/scenario (may be empty).
    - `excluded_radionuclides`: supported-by-a-selected-source radionuclides that
      were NOT admitted (e.g. not clinically classified for this modality, or
      wrong modality), with a reason.
    - `source_by_radionuclide`: preserves which selected source(s) supply each
      admissible radionuclide.
    - `status`: ADMISSIBLE if at least one admissible radionuclide exists, else
      NO_COMPATIBLE_SOURCE.
    - `limitations`: explicit, human-readable notes (never a silent drop)."""

    modality: Modality
    mode: SyntheticDemandMode
    selected_cyclotron_ids: tuple[str, ...]
    selected_generator_ids: tuple[str, ...]
    admissible_radionuclides: tuple[str, ...]
    excluded_radionuclides: tuple[tuple[str, str], ...]
    source_by_radionuclide: tuple[RadionuclideSourceBinding, ...]
    status: CapabilityStatus
    limitations: tuple[str, ...]

    @property
    def selected_source_ids(self) -> tuple[str, ...]:
        return tuple(self.selected_cyclotron_ids) + tuple(self.selected_generator_ids)

    def compatible_source_ids_for(self, radionuclide: str) -> tuple[str, ...]:
        for binding in self.source_by_radionuclide:
            if binding.radionuclide == radionuclide:
                return binding.compatible_source_ids
        return ()


def _clinically_recognized(modality: Modality) -> frozenset[str]:
    if modality not in _CLINICALLY_RECOGNIZED_RADIONUCLIDES_BY_MODALITY:
        raise ValueError(f"Unknown modality: {modality!r} (expected 'PET' or 'SPECT')")
    return _CLINICALLY_RECOGNIZED_RADIONUCLIDES_BY_MODALITY[modality]


def _resolve_cyclotron_supported(
    selected_cyclotron_ids: Sequence[str],
) -> dict[str, list[str]]:
    """radionuclide -> [selected cyclotron ids that SUPPORT it], resolved from
    the REAL catalog `supported_radionuclides` (SUPPORT semantics -- not
    schedulable/calibrated). Preserves each selected source identity; a
    radionuclide supported by N selected cyclotrons lists all N ids once."""
    catalog = load_cyclotron_catalog()
    supported_by_radionuclide: dict[str, list[str]] = {}
    for model_id in selected_cyclotron_ids:
        model = catalog.by_id(model_id)  # raises on unknown id -- never silently ignored
        for radionuclide in model.supported_radionuclides:
            ids = supported_by_radionuclide.setdefault(radionuclide, [])
            if model_id not in ids:
                ids.append(model_id)
    return supported_by_radionuclide


def _resolve_generator_supported(
    selected_generator_ids: Sequence[str],
) -> dict[str, list[str]]:
    """daughter radionuclide -> [selected generator ids that produce it]. Uses
    the generator catalog's `daughter_radionuclide` -- generator output NEVER
    goes through the cyclotron resolver (build governor Sec 7/23)."""
    catalog = load_generator_catalog()
    supported_by_radionuclide: dict[str, list[str]] = {}
    for model_id in selected_generator_ids:
        model = catalog.by_id(model_id)  # raises on unknown id
        daughter = model.daughter_radionuclide
        ids = supported_by_radionuclide.setdefault(daughter, [])
        if model_id not in ids:
            ids.append(model_id)
    return supported_by_radionuclide


def resolve_admissible_radionuclides(
    *,
    modality: Modality,
    selected_cyclotron_ids: Sequence[str] = (),
    selected_generator_ids: Sequence[str] = (),
    mode: SyntheticDemandMode = "NORMAL",
) -> SyntheticRadionuclideCapabilityResult:
    """Resolve the admissible synthetic radionuclide set for one modality from
    the SELECTED production sources.

    ADMISSIBLE = ( CYCLOTRON-supported radionuclides UNION GENERATOR-daughter
    radionuclides ) filtered by CLINICAL MODALITY compatibility. Source support
    (not calibration/estimability) is the admissibility signal. Source
    identities are preserved per radionuclide; duplicate support does not create
    duplicate radionuclide choices.

    The result is deterministic and order-stable given the same selected-source
    ids and modality. `mode` does not change admissibility itself; it is carried
    on the result so callers can honor the NORMAL-vs-STRESS_TEST contract
    (STRESS_TEST callers may deliberately request an inadmissible radionuclide
    and preserve it for downstream NO_COMPATIBLE_SOURCE exposure -- this module
    never substitutes)."""
    cyclotron_ids = tuple(selected_cyclotron_ids)
    generator_ids = tuple(selected_generator_ids)

    cyclotron_supported = _resolve_cyclotron_supported(cyclotron_ids)
    generator_supported = _resolve_generator_supported(generator_ids)

    recognized = _clinically_recognized(modality)

    bindings: list[RadionuclideSourceBinding] = []
    excluded: list[tuple[str, str]] = []
    limitations: list[str] = []

    # Deterministic evaluation order: cyclotron-supported radionuclides first
    # (sorted), then generator daughters (sorted) -- so the union is stable.
    def _classify(radionuclide: str, source_type: SourceType, compatible_ids: list[str]) -> None:
        if radionuclide in recognized:
            bindings.append(
                RadionuclideSourceBinding(
                    radionuclide=radionuclide,
                    source_type=source_type,
                    compatible_source_ids=tuple(compatible_ids),
                )
            )
        else:
            # Supported by a selected source but not clinically classified for
            # THIS modality. Distinguish "recognized for the OTHER modality"
            # from "not clinically classified at all" (build governor Sec 30).
            other_modality: Modality = "SPECT" if modality == "PET" else "PET"
            if radionuclide in _clinically_recognized(other_modality):
                reason = f"CLINICALLY_RECOGNIZED_FOR_{other_modality}_NOT_{modality}"
            else:
                reason = "SUPPORTED_BUT_NOT_CLINICALLY_MODALITY_CLASSIFIED"
                limitations.append(
                    f"{radionuclide} is supported by a selected {source_type.lower()} "
                    f"but the repository does not clinically classify it for {modality} "
                    f"synthetic demand; it is reported, never silently promoted."
                )
            excluded.append((radionuclide, reason))

    for radionuclide in sorted(cyclotron_supported):
        _classify(radionuclide, "CYCLOTRON", cyclotron_supported[radionuclide])
    for radionuclide in sorted(generator_supported):
        # A daughter already admitted via a cyclotron (not expected today, but
        # guard against double admission) -- merge source ids, do not duplicate.
        existing = next((b for b in bindings if b.radionuclide == radionuclide), None)
        if existing is not None:
            merged = tuple(dict.fromkeys(existing.compatible_source_ids + tuple(generator_supported[radionuclide])))
            bindings[bindings.index(existing)] = RadionuclideSourceBinding(
                radionuclide=existing.radionuclide, source_type=existing.source_type,
                compatible_source_ids=merged,
            )
        else:
            _classify(radionuclide, "GENERATOR", generator_supported[radionuclide])

    admissible = tuple(b.radionuclide for b in bindings)
    status: CapabilityStatus = "ADMISSIBLE" if admissible else "NO_COMPATIBLE_SOURCE"

    if not admissible:
        if not cyclotron_ids and not generator_ids:
            limitations.append(
                f"No production source selected: normal synthetic {modality} radionuclide "
                f"assignment cannot proceed (no cyclotron and no generator). "
                f"No F-18/Tc-99m fallback and no global-catalog borrowing."
            )
        else:
            limitations.append(
                f"No selected production source supports a clinically-recognized {modality} "
                f"radionuclide for cohort={modality}; selected sources="
                f"{list(cyclotron_ids) + list(generator_ids)}."
            )

    return SyntheticRadionuclideCapabilityResult(
        modality=modality,
        mode=mode,
        selected_cyclotron_ids=cyclotron_ids,
        selected_generator_ids=generator_ids,
        admissible_radionuclides=admissible,
        excluded_radionuclides=tuple(excluded),
        source_by_radionuclide=tuple(bindings),
        status=status,
        limitations=tuple(limitations),
    )


def choose_normal_synthetic_radionuclide(
    capability: SyntheticRadionuclideCapabilityResult,
) -> str:
    """Deterministic NORMAL-mode radionuclide choice from an admissible set.

    Policy (build governor Sec 13): there is no canonical clinical weighting
    authority in the repository, so the narrowest deterministic/reproducible
    policy is used -- the first admissible radionuclide in the stable resolved
    order. For the representative benchmark (one clinically-recognized
    radionuclide per modality: F-18 for PET, Tc-99m for SPECT) this is exactly
    that radionuclide, so backward compatibility is preserved by construction.

    Raises if the capability is NO_COMPATIBLE_SOURCE -- the normal generator
    must NOT invent or substitute a radionuclide (build governor Sec 9/10)."""
    if capability.status != "ADMISSIBLE" or not capability.admissible_radionuclides:
        raise NoCompatibleSourceError(
            f"No compatible selected production source for {capability.modality} "
            f"synthetic demand: {capability.limitations}"
        )
    return capability.admissible_radionuclides[0]


class NoCompatibleSourceError(ValueError):
    """Raised when normal synthetic generation is requested for a modality that
    has no admissible radionuclide from the selected sources. The typed failure
    explains modality, selected sources, and why no radionuclide was admissible
    (build governor Sec 10)."""

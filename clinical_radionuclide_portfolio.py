"""Clinical Radionuclide Portfolio Authority (OG-RAD-1).

PURPOSE
-------
The single, ARCHITECTURE-NEUTRAL authority that answers one question only:

    WHAT CLINICAL RADIONUCLIDE DEMAND IS LEGITIMATE?

It does NOT answer "what capital / transport architecture best serves that
demand" (that is the future Part 3E composition optimizer) and it does NOT
answer "how much of each radionuclide is requested" (that is a DEMAND SCENARIO).
Three concepts stay strictly separated:

    PORTFOLIO   = what MAY legitimately be requested   (this authority)
    DEMAND MIX  = how much of each is requested         (a demand scenario)
    OPTIMIZER   = what capital composition best serves  (Part 3E)

The repository already physically RECOGNIZES more radionuclides (cyclotron
`supported_radionuclides`, generator daughters, the canonical half-life table)
than the current NORMAL synthetic-demand pathway ADMITS. This authority makes
that distinction explicit and honest without expanding clinical use aspirationally.

CORE DOCTRINE (preserved, never collapsed)
------------------------------------------
    RADIONUCLIDE PHYSICALLY KNOWN   != RADIONUCLIDE CLINICALLY ADMISSIBLE
    CYCLOTRON SUPPORTED             != CLINICALLY USED
    SUPPORTED                       != CALIBRATED
    CLINICALLY ADMISSIBLE           != QUANTITATIVELY CALIBRATED
    RADIONUCLIDE PORTFOLIO          != DEMAND MIX
    NORMAL DEMAND != STRESS DEMAND  != EXPLICIT DEMAND

ARCHITECTURE NEUTRALITY (hard requirement)
------------------------------------------
This authority contains NO reference to MRT, Conventional, transport time,
logistics distance, decay-advantage, or any capital architecture. Short-lived
radionuclides are represented on exactly the same footing as long-lived ones;
they are NEVER promoted merely because they might favor a faster transport mode.
Part 3E must discover architecture consequences from physics downstream — this
authority never encodes them.

AUTHORITY BOUNDARY (what this module does NOT do)
-------------------------------------------------
- It builds NO new decay engine, cyclotron estimator, generator physics, scanner
  catalog, or transport model. It consumes those existing authorities read-only.
- It never invents a clinical modality, a procedure classification, a half-life,
  a production capacity, a cycle duration, an EOB activity, or a generator
  pathway that the repository does not already own.
- It is NEVER patient-identity-aware. No `patient_id`/name/room/appointment/
  calendar identity is consulted or stored. `PORTFOLIO != PATIENT`.
- It never makes cyclotrons or generators patient-identity-aware.

REUSED AUTHORITIES (never duplicated)
-------------------------------------
- `diagnostics.load_radionuclide_half_lives` / `radionuclides.json` -> the ONE
  decay/half-life authority (7 radionuclides today).
- `cyclotron_catalog.load_cyclotron_catalog` -> `supported_radionuclides`
  (SUPPORT), `schedulable_radionuclides`, `production_calibration_status`.
- `generator_catalog.load_generator_catalog` -> `daughter_radionuclide` /
  `parent_radionuclide` (Mo-99 -> Tc-99m only; no Ge-68/Ga-68 generator, OG-GEN-1).
- `scanner_catalog.load_scanner_catalog` + `clinical_resource_identity.ScannerModality`
  -> PET/SPECT modality availability (modality-level only; model-specific
  radionuclide compatibility is NOT_MODELED, OG-SCN-1).
- `synthetic_radionuclide_source_capability` -> the selected-source admissible
  chain link and the SAME clinical modality recognition set (F-18->PET,
  Tc-99m->SPECT). This module is the layer that sits conceptually between
  PHYSICAL SOURCE CAPABILITY and SYNTHETIC DEMAND and reuses that resolver's
  recognition rather than re-declaring a competing one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

from diagnostics import load_radionuclide_half_lives
from cyclotron_catalog import load_cyclotron_catalog
from generator_catalog import load_generator_catalog
from scanner_catalog import load_scanner_catalog
from clinical_resource_identity import ScannerModality
from synthetic_radionuclide_source_capability import (
    _CLINICALLY_RECOGNIZED_RADIONUCLIDES_BY_MODALITY as _CLINICAL_MODALITY_RECOGNITION,
    resolve_admissible_radionuclides,
)


# ---------------------------------------------------------------------------
# Status vocabulary (Section 22). Reuse existing terms where possible; add only
# precise, non-vague reasons. Never a bare "UNKNOWN" where a real reason exists.
# ---------------------------------------------------------------------------

PortfolioMode = Literal["NORMAL", "STRESS_TEST", "EXPLICIT"]

ClinicalModalityStatus = Literal[
    "CLINICALLY_MODALITY_CLASSIFIED",   # repository binds this radionuclide -> PET/SPECT
    "CLINICAL_MODALITY_NOT_MODELED",    # physically known but no modality authority
]

DecayStatus = Literal[
    "DECAY_AUTHORITY_PRESENT",          # canonical half-life table has it
    "DECAY_AUTHORITY_MISSING",          # no canonical half-life -> cannot enter NORMAL
]

ProcedureStatus = Literal[
    "PROCEDURE_NOT_MODELED",            # repository owns no radionuclide-specific procedure authority
]

SourceCapabilityStatus = Literal[
    "SUPPORTED_BY_SELECTED_SOURCE",     # a selected cyclotron/generator supports it (SUPPORT semantics)
    "SUPPORTED_BY_CATALOG_ONLY",        # some catalog machine supports it, but none SELECTED (never NORMAL-admissible)
    "NO_COMPATIBLE_SOURCE",             # no cyclotron/generator anywhere produces it
]

ScannerCompatibilityStatus = Literal[
    "SCANNER_MODALITY_AVAILABLE",       # a scanner of the required modality is present in the scenario
    "NO_COMPATIBLE_SCANNER",            # required modality absent from the scenario
    "SCANNER_MODALITY_NOT_APPLICABLE",  # radionuclide has no clinical modality, so no scanner requirement is defined
]

# Per-radionuclide production identity distinctions -- NEVER collapsed together
# (Section 4/8). SUPPORTED != CALIBRATED != ESTIMABLE.
ProductionCalibrationStatus = Literal[
    "MANUFACTURER_CALIBRATED",          # a selected source has a manufacturer-calibrated EOB point
    "MODELED",                          # schedulable (supported + cycle) but no manufacturer point
    "NOT_CALIBRATED",                   # supported but not schedulable/calibrated (e.g. CYPRIS MP-30 + F-18)
    "PRODUCTION_NOT_APPLICABLE",        # no selected source supports it
]

NormalAdmissibility = Literal["NORMAL_ADMISSIBLE", "NORMAL_EXCLUDED"]

Part3EEligibility = Literal["PART3E_ELIGIBLE", "PART3E_NOT_ELIGIBLE"]

# Generator PARENT radionuclides are production feedstock only; they are NEVER
# patient-administered demand (Section 20). Resolved from the generator catalog,
# not hardcoded.
_PET = "PET"
_SPECT = "SPECT"


# ---------------------------------------------------------------------------
# Result types (Section 21) -- immutable, explicit.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClinicalRadionuclidePortfolioEntry:
    """One radionuclide row in the canonical portfolio matrix. Every distinction
    the doctrine forbids collapsing (physically-known / clinically-classified /
    supported / calibrated / scanner-compatible / normal-admissible) is a
    separate field."""

    radionuclide: str
    physically_recognized: bool
    half_life_minutes: float | None
    decay_status: DecayStatus
    clinical_modality: ScannerModality | None
    clinical_modality_status: ClinicalModalityStatus
    procedure_status: ProcedureStatus
    is_generator_parent: bool
    compatible_cyclotron_ids: tuple[str, ...]
    compatible_generator_ids: tuple[str, ...]
    source_capability_status: SourceCapabilityStatus
    production_calibration_status: ProductionCalibrationStatus
    scanner_modality_required: ScannerModality | None
    scanner_compatibility_status: ScannerCompatibilityStatus
    normal_admissible: NormalAdmissibility
    stress_visible: bool
    explicit_demand_representable: bool
    part3e_eligible: Part3EEligibility
    blocking_gap: str | None
    limitations: tuple[str, ...]
    provenance: tuple[str, ...]


@dataclass(frozen=True)
class ClinicalRadionuclidePortfolioResult:
    """Portfolio-level contract Part 3E will consume alongside a DemandScenario.
    Deterministic and order-stable. Carries no patient identity, no demand mix,
    no economics, no architecture."""

    mode: PortfolioMode
    selected_cyclotron_ids: tuple[str, ...]
    selected_generator_ids: tuple[str, ...]
    available_scanner_modalities: tuple[ScannerModality, ...]
    entries: tuple[ClinicalRadionuclidePortfolioEntry, ...]
    physically_recognized_radionuclides: tuple[str, ...]
    normal_admissible_radionuclides: tuple[str, ...]
    stress_visible_radionuclides: tuple[str, ...]
    excluded_radionuclides: tuple[tuple[str, str], ...]
    multi_radionuclide_weighting_authority: Literal["NOT_MODELED"]
    limitations: tuple[str, ...]

    def entry_for(self, radionuclide: str) -> ClinicalRadionuclidePortfolioEntry:
        for entry in self.entries:
            if entry.radionuclide == radionuclide:
                return entry
        raise KeyError(f"Radionuclide not in portfolio matrix: {radionuclide!r}")

    @property
    def normal_admissible_count(self) -> int:
        return len(self.normal_admissible_radionuclides)


# ---------------------------------------------------------------------------
# Physical-universe discovery (Section 3). Built from repository authorities,
# never from a hardcoded prompt list.
# ---------------------------------------------------------------------------


def _clinical_modality_for(radionuclide: str) -> ScannerModality | None:
    """Reuse the SAME recognition set used by the synthetic source-capability
    authority (F-18 -> PET, Tc-99m -> SPECT). Never invents a classification."""
    for modality, members in _CLINICAL_MODALITY_RECOGNITION.items():
        if radionuclide in members:
            return modality  # type: ignore[return-value]
    return None


def _discover_physical_universe() -> tuple[
    tuple[str, ...],                # ordered universe
    dict[str, float],               # half-life table
    dict[str, list[str]],           # radionuclide -> cyclotron model ids supporting (SUPPORT)
    dict[str, list[str]],           # radionuclide -> cyclotron model ids schedulable
    dict[str, list[str]],           # radionuclide -> cyclotron model ids manufacturer-calibrated
    dict[str, list[str]],           # daughter -> generator model ids
    set[str],                       # generator parents
]:
    half_lives = load_radionuclide_half_lives()
    cyclotron = load_cyclotron_catalog()
    generator = load_generator_catalog()

    cyc_supported: dict[str, list[str]] = {}
    cyc_schedulable: dict[str, list[str]] = {}
    cyc_calibrated: dict[str, list[str]] = {}
    for model in cyclotron.models:
        for radionuclide in model.supported_radionuclides:
            cyc_supported.setdefault(radionuclide, []).append(model.catalog_model_id)
        for radionuclide in model.schedulable_radionuclides:
            cyc_schedulable.setdefault(radionuclide, []).append(model.catalog_model_id)
        # A manufacturer-calibrated EOB point for a specific radionuclide, read
        # from the catalog's own performance records (never fabricated).
        for record in model.production_performance_records:
            if (
                record.normalized_eob_activity_mbq is not None
                and record.calibration_status == "manufacturer_calibrated"
            ):
                cyc_calibrated.setdefault(record.radionuclide, []).append(model.catalog_model_id)

    gen_daughters: dict[str, list[str]] = {}
    gen_parents: set[str] = set()
    for model in generator.models:
        gen_daughters.setdefault(model.daughter_radionuclide, []).append(model.catalog_model_id)
        gen_parents.add(model.parent_radionuclide)

    universe = (
        set(half_lives)
        | set(cyc_supported)
        | set(gen_daughters)
        | gen_parents
    )
    return (
        tuple(sorted(universe)),
        dict(half_lives),
        cyc_supported,
        cyc_schedulable,
        {k: sorted(set(v)) for k, v in cyc_calibrated.items()},
        gen_daughters,
        gen_parents,
    )


def _available_scanner_modalities(
    selected_scanner_modalities: Sequence[ScannerModality] | None,
) -> tuple[ScannerModality, ...]:
    """The scanner modalities present in THIS scenario.

    When the caller supplies an explicit set, it is authoritative (a scenario
    may deliberately have only SPECT scanners, or none). When left `None`, the
    modality set is derived from the repository scanner CATALOG's modalities --
    a benchmark availability, honestly labeled, never a fabricated model-specific
    compatibility (OG-SCN-1: model-specific radionuclide compatibility is
    NOT_MODELED; only PET/SPECT modality is authoritative)."""
    if selected_scanner_modalities is not None:
        # De-duplicate, order-stable (PET before SPECT).
        seen: dict[ScannerModality, None] = {}
        for modality in selected_scanner_modalities:
            if modality not in (_PET, _SPECT):
                raise ValueError(f"Unknown scanner modality: {modality!r} (expected 'PET' or 'SPECT')")
            seen[modality] = None
        return tuple(m for m in (_PET, _SPECT) if m in seen)  # type: ignore[misc]
    catalog = load_scanner_catalog()
    present = {model.modality for model in catalog.models}
    return tuple(m for m in (_PET, _SPECT) if m in present)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Per-radionuclide resolution (Sections 4-20).
# ---------------------------------------------------------------------------


def _resolve_production_calibration(
    radionuclide: str,
    *,
    compatible_cyclotron_ids: tuple[str, ...],
    compatible_generator_ids: tuple[str, ...],
    schedulable_ids_all: Sequence[str],
    calibrated_ids_all: Sequence[str],
) -> ProductionCalibrationStatus:
    """Production identity is SEPARATE from source support and from clinical
    admissibility (Section 4/8). Resolved only from SELECTED sources. A
    generator daughter (Tc-99m) is treated as NOT_CALIBRATED at the generator
    level (the generator catalog carries no manufacturer-calibrated production
    EOB point -- only reference-activity options), never MODELED via the
    cyclotron path."""
    if not compatible_cyclotron_ids and not compatible_generator_ids:
        return "PRODUCTION_NOT_APPLICABLE"
    # Cyclotron path: manufacturer-calibrated point on a SELECTED model wins.
    selected_calibrated = [mid for mid in compatible_cyclotron_ids if mid in set(calibrated_ids_all)]
    if selected_calibrated:
        return "MANUFACTURER_CALIBRATED"
    selected_schedulable = [mid for mid in compatible_cyclotron_ids if mid in set(schedulable_ids_all)]
    if selected_schedulable:
        return "MODELED"
    # Supported by a selected source but not schedulable/calibrated
    # (e.g. CYPRIS MP-30 + F-18) OR a generator daughter (no manufacturer EOB point).
    return "NOT_CALIBRATED"


def _resolve_entry(
    radionuclide: str,
    *,
    mode: PortfolioMode,
    half_lives: Mapping[str, float],
    cyc_supported: Mapping[str, list[str]],
    cyc_schedulable: Mapping[str, list[str]],
    cyc_calibrated: Mapping[str, list[str]],
    gen_daughters: Mapping[str, list[str]],
    gen_parents: set[str],
    selected_cyclotron_ids: tuple[str, ...],
    selected_generator_ids: tuple[str, ...],
    available_scanner_modalities: tuple[ScannerModality, ...],
) -> ClinicalRadionuclidePortfolioEntry:
    provenance: list[str] = []
    limitations: list[str] = []

    # --- Decay authority (Section 7) ---
    half_life = half_lives.get(radionuclide)
    decay_status: DecayStatus = "DECAY_AUTHORITY_PRESENT" if half_life is not None else "DECAY_AUTHORITY_MISSING"
    if half_life is not None:
        provenance.append("radionuclides.json/diagnostics.load_radionuclide_half_lives")
    else:
        limitations.append("No canonical half-life authority (radionuclides.json); cannot enter NORMAL demand.")

    # --- Clinical modality authority (Section 5) ---
    clinical_modality = _clinical_modality_for(radionuclide)
    if clinical_modality is not None:
        clinical_modality_status: ClinicalModalityStatus = "CLINICALLY_MODALITY_CLASSIFIED"
        provenance.append("synthetic_radionuclide_source_capability._CLINICALLY_RECOGNIZED_RADIONUCLIDES_BY_MODALITY")
    else:
        clinical_modality_status = "CLINICAL_MODALITY_NOT_MODELED"
        limitations.append(
            "Repository owns no clinical PET/SPECT modality classification for this radionuclide; "
            "reported, never invented."
        )

    # --- Procedure authority (Section 6) -- none exists radionuclide-specific ---
    procedure_status: ProcedureStatus = "PROCEDURE_NOT_MODELED"

    # --- Source capability (Sections 8-10, 24-25): SELECTED sources only ---
    supported_by_selected_cyclotrons = tuple(
        mid for mid in selected_cyclotron_ids if mid in set(cyc_supported.get(radionuclide, ()))
    )
    supported_by_selected_generators = tuple(
        mid for mid in selected_generator_ids if mid in set(gen_daughters.get(radionuclide, ()))
    )
    supported_anywhere_cyclotron = bool(cyc_supported.get(radionuclide))
    supported_anywhere_generator = bool(gen_daughters.get(radionuclide))

    if supported_by_selected_cyclotrons or supported_by_selected_generators:
        source_capability_status: SourceCapabilityStatus = "SUPPORTED_BY_SELECTED_SOURCE"
        if supported_by_selected_cyclotrons:
            provenance.append("cyclotron_catalog.supported_radionuclides (SELECTED)")
        if supported_by_selected_generators:
            provenance.append("generator_catalog.daughter_radionuclide (SELECTED)")
    elif supported_anywhere_cyclotron or supported_anywhere_generator:
        source_capability_status = "SUPPORTED_BY_CATALOG_ONLY"
        limitations.append(
            "Supported by a catalog machine but not by any SELECTED source; never NORMAL-admissible "
            "(no global-catalog fallback)."
        )
    else:
        source_capability_status = "NO_COMPATIBLE_SOURCE"

    # --- Production calibration (Section 8) -- separate from support ---
    production_calibration_status = _resolve_production_calibration(
        radionuclide,
        compatible_cyclotron_ids=supported_by_selected_cyclotrons,
        compatible_generator_ids=supported_by_selected_generators,
        schedulable_ids_all=cyc_schedulable.get(radionuclide, ()),
        calibrated_ids_all=cyc_calibrated.get(radionuclide, ()),
    )

    # --- Generator parent boundary (Section 20) ---
    is_generator_parent = radionuclide in gen_parents

    # --- Scanner compatibility (Sections 26-27): modality-level only ---
    scanner_modality_required = clinical_modality  # PET radionuclide -> PET scanner, etc.
    if scanner_modality_required is None:
        scanner_compatibility_status: ScannerCompatibilityStatus = "SCANNER_MODALITY_NOT_APPLICABLE"
    elif scanner_modality_required in available_scanner_modalities:
        scanner_compatibility_status = "SCANNER_MODALITY_AVAILABLE"
    else:
        scanner_compatibility_status = "NO_COMPATIBLE_SCANNER"
        limitations.append(
            f"Required {scanner_modality_required} scanner modality is not present in this scenario."
        )

    # --- NORMAL admissibility chain (Sections 10-11) ---
    # SELECTED SOURCES -> SUPPORTED -> CLINICALLY CLASSIFIED -> (procedure not
    # required today) -> DECAY-AUTHORIZED -> SCANNER-COMPATIBLE -> NORMAL.
    # Blocking gap follows a stable precedence so the surfaced reason is precise.
    blocking_gap: str | None = None
    if clinical_modality is None:
        blocking_gap = "CLINICAL_MODALITY_NOT_MODELED"
    elif decay_status == "DECAY_AUTHORITY_MISSING":
        blocking_gap = "DECAY_AUTHORITY_MISSING"
    elif source_capability_status != "SUPPORTED_BY_SELECTED_SOURCE":
        blocking_gap = "NO_COMPATIBLE_SOURCE"
    elif scanner_compatibility_status == "NO_COMPATIBLE_SCANNER":
        blocking_gap = "NO_COMPATIBLE_SCANNER"

    normal_admissible: NormalAdmissibility = (
        "NORMAL_ADMISSIBLE" if blocking_gap is None else "NORMAL_EXCLUDED"
    )

    # --- Stress visibility (Section 12) ---
    # STRESS_TEST keeps every physically-recognized radionuclide identity visible
    # so a downstream request can expose the precise reason. Identity is never
    # substituted; the portfolio just does not hide it.
    stress_visible = True

    # --- Explicit demand representability (Section 13) ---
    # Explicit patient demand (patient_radionuclide_demand.PatientRadionuclideDemand)
    # validates a radionuclide against the canonical half-life table. So an
    # explicit request can be REPRESENTED (identity preserved) exactly when decay
    # authority exists; feasibility/limitations are reported downstream, never by
    # silently mutating the request.
    explicit_demand_representable = decay_status == "DECAY_AUTHORITY_PRESENT"

    # --- Part 3E portfolio eligibility (Section 28/38) ---
    # A radionuclide is Part-3E portfolio-eligible when it is clinically
    # classified AND decay-authorized (it can legitimately appear in a demand
    # scenario the optimizer reasons about). Source/scanner availability is
    # scenario-specific and is expressed per entry, not baked into eligibility.
    part3e_eligible: Part3EEligibility = (
        "PART3E_ELIGIBLE"
        if clinical_modality is not None and decay_status == "DECAY_AUTHORITY_PRESENT"
        else "PART3E_NOT_ELIGIBLE"
    )

    return ClinicalRadionuclidePortfolioEntry(
        radionuclide=radionuclide,
        physically_recognized=True,
        half_life_minutes=half_life,
        decay_status=decay_status,
        clinical_modality=clinical_modality,
        clinical_modality_status=clinical_modality_status,
        procedure_status=procedure_status,
        is_generator_parent=is_generator_parent,
        compatible_cyclotron_ids=supported_by_selected_cyclotrons,
        compatible_generator_ids=supported_by_selected_generators,
        source_capability_status=source_capability_status,
        production_calibration_status=production_calibration_status,
        scanner_modality_required=scanner_modality_required,
        scanner_compatibility_status=scanner_compatibility_status,
        normal_admissible=normal_admissible,
        stress_visible=stress_visible,
        explicit_demand_representable=explicit_demand_representable,
        part3e_eligible=part3e_eligible,
        blocking_gap=blocking_gap,
        limitations=tuple(limitations),
        provenance=tuple(dict.fromkeys(provenance)),  # order-stable de-dup
    )


def resolve_clinical_radionuclide_portfolio(
    *,
    selected_cyclotron_ids: Sequence[str] = (),
    selected_generator_ids: Sequence[str] = (),
    selected_scanner_modalities: Sequence[ScannerModality] | None = None,
    mode: PortfolioMode = "NORMAL",
) -> ClinicalRadionuclidePortfolioResult:
    """Resolve the clinical radionuclide portfolio for a scenario.

    The portfolio is the ARCHITECTURE-NEUTRAL set of radionuclides that MAY
    legitimately be requested, one entry per physically-recognized radionuclide,
    each carrying its own decay / modality / procedure / source / production /
    scanner status and NORMAL admissibility.

    - `selected_cyclotron_ids` / `selected_generator_ids`: the SELECTED /
      INSTALLED production sources (never the global catalog). Unknown ids raise
      via the catalog `by_id`.
    - `selected_scanner_modalities`: the PET/SPECT modalities present in the
      scenario; `None` derives them from the scanner catalog (benchmark
      availability).
    - `mode`: NORMAL / STRESS_TEST / EXPLICIT. Mode does not mutate any
      radionuclide identity; it is carried on the result and governs how callers
      read `normal_admissible` vs `stress_visible` vs
      `explicit_demand_representable`.

    Never substitutes, never falls back to F-18/Tc-99m, never borrows global
    catalog capability, never fabricates modality/procedure/decay/production
    data, and is never patient-identity-aware.
    """
    if mode not in ("NORMAL", "STRESS_TEST", "EXPLICIT"):
        raise ValueError(f"Unknown portfolio mode: {mode!r}")

    cyclotron_ids = tuple(selected_cyclotron_ids)
    generator_ids = tuple(selected_generator_ids)

    # Validate selected ids against the real catalogs (raise on unknown -- never
    # silently ignored, mirrors synthetic_radionuclide_source_capability).
    if cyclotron_ids:
        catalog = load_cyclotron_catalog()
        for mid in cyclotron_ids:
            catalog.by_id(mid)
    if generator_ids:
        gcatalog = load_generator_catalog()
        for mid in generator_ids:
            gcatalog.by_id(mid)

    (
        universe,
        half_lives,
        cyc_supported,
        cyc_schedulable,
        cyc_calibrated,
        gen_daughters,
        gen_parents,
    ) = _discover_physical_universe()

    available_scanner_modalities = _available_scanner_modalities(selected_scanner_modalities)

    entries = tuple(
        _resolve_entry(
            radionuclide,
            mode=mode,
            half_lives=half_lives,
            cyc_supported=cyc_supported,
            cyc_schedulable=cyc_schedulable,
            cyc_calibrated=cyc_calibrated,
            gen_daughters=gen_daughters,
            gen_parents=gen_parents,
            selected_cyclotron_ids=cyclotron_ids,
            selected_generator_ids=generator_ids,
            available_scanner_modalities=available_scanner_modalities,
        )
        for radionuclide in universe
    )

    normal_admissible = tuple(e.radionuclide for e in entries if e.normal_admissible == "NORMAL_ADMISSIBLE")
    stress_visible = tuple(e.radionuclide for e in entries if e.stress_visible)
    excluded = tuple(
        (e.radionuclide, e.blocking_gap)
        for e in entries
        if e.normal_admissible == "NORMAL_EXCLUDED" and e.blocking_gap is not None
    )

    limitations: list[str] = [
        "MULTI_RADIONUCLIDE_WEIGHTING_AUTHORITY = NOT_MODELED: the portfolio lists what MAY be "
        "requested; it never fabricates a real-world prevalence mix. PORTFOLIO != DEMAND MIX.",
        "PROCEDURE authority is NOT_MODELED: no radionuclide-specific clinical procedure classes exist "
        "in the repository; procedures are reported as PROCEDURE_NOT_MODELED, never invented.",
        "Model-specific scanner radionuclide compatibility is NOT_MODELED (OG-SCN-1); only PET/SPECT "
        "modality availability is authoritative.",
        "Ge-68/Ga-68 generator pathway is NOT_MODELED (OG-GEN-1); Ga-68 appears only as a "
        "cyclotron-supported radionuclide, never as a generator daughter.",
        "This authority is ARCHITECTURE-NEUTRAL: no transport/MRT/Conventional/decay-advantage bias.",
    ]

    return ClinicalRadionuclidePortfolioResult(
        mode=mode,
        selected_cyclotron_ids=cyclotron_ids,
        selected_generator_ids=generator_ids,
        available_scanner_modalities=available_scanner_modalities,
        entries=entries,
        physically_recognized_radionuclides=universe,
        normal_admissible_radionuclides=normal_admissible,
        stress_visible_radionuclides=stress_visible,
        excluded_radionuclides=excluded,
        multi_radionuclide_weighting_authority="NOT_MODELED",
        limitations=tuple(limitations),
    )


def discover_physically_recognized_radionuclides() -> tuple[str, ...]:
    """The complete physically-recognized radionuclide universe, discovered from
    repository authorities (half-life table UNION cyclotron supported UNION
    generator daughters UNION generator parents). Not a hardcoded list."""
    universe, *_ = _discover_physical_universe()
    return universe

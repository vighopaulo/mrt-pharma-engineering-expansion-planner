# Clinical Radionuclide Portfolio Authority (OG-RAD-1)

**Build:** Clinical Radionuclide Portfolio Authority — Pre-Part-3E Readiness
(CURRENT UNCOMMITTED BUILD; starting SHA `28552cd`).
**Canonical module:** `clinical_radionuclide_portfolio.py`
**Focused test:** `test_clinical_radionuclide_portfolio.py` (52 tests)
**Governance:** opens `OG-RAD-1` at **PARTIAL** — the portfolio authority exists
and is test-locked, but clinical modality / procedure evidence remains incomplete
for most physically-recognized radionuclides, so the gap is not CLOSED.

---

## A. Purpose

The single, **architecture-neutral** authority answering one question:

> **WHAT CLINICAL RADIONUCLIDE DEMAND IS LEGITIMATE?**

It does *not* answer "how much of each is requested" (a **demand scenario**) and
it does *not* answer "what capital / transport architecture best serves that
demand" (the future **Part 3E** composition optimizer). Three concepts stay
separated:

```
PORTFOLIO   = what MAY legitimately be requested   (this authority)
DEMAND MIX  = how much of each is requested         (a demand scenario)
OPTIMIZER   = what capital composition best serves  (Part 3E)
```

The repository physically **recognizes** more radionuclides than the current
NORMAL synthetic-demand pathway **admits**. This authority makes that gap
explicit and honest without expanding clinical use aspirationally. Evidence
honesty outranks portfolio size.

## B. Authority boundary

- Builds **no** new decay engine, cyclotron estimator, generator physics, scanner
  catalog, or transport model. It consumes those existing authorities read-only.
- Never invents a clinical modality, procedure classification, half-life,
  production capacity, cycle duration, EOB activity, or generator pathway.
- Is **never patient-identity-aware**. No `patient_id`/name/room/appointment/
  calendar identity is consulted or stored. `PORTFOLIO != PATIENT`.
- Contains **no** transport / MRT / Conventional / decay-advantage reference.
  Short-lived radionuclides are represented on the same footing as long-lived
  ones; they are never promoted because they might favor a faster transport mode.

## C. Radionuclide universe (discovered, not hardcoded)

Discovered from the physical authorities as the union of the canonical half-life
table, cyclotron `supported_radionuclides`, generator daughters, and generator
parents.

**`PHYSICALLY_RECOGNIZED_RADIONUCLIDE_COUNT = 15`:** At-211, C-11, Cu-64, F-18,
Ga-68, Ge-68, I-123, I-124, In-111, Mo-99, N-13, O-15, Tc-99m, Tl-201, Zr-89.

## D. Decay / half-life authority (reused)

`diagnostics.load_radionuclide_half_lives` → `radionuclides.json` is the single
decay authority. `HALF_LIFE_SUPPORTED_COUNT = 7`: F-18 (109.8 min), Ga-68 (67.7),
C-11 (20.3), N-13 (9.97), O-15 (2.04), Tc-99m (360.0), Mo-99 (3956.4). A
radionuclide lacking canonical decay authority (Cu-64, Zr-89, Ge-68, I-123,
I-124, In-111, Tl-201, At-211) is `DECAY_AUTHORITY_MISSING` and cannot enter
NORMAL demand. No half-life is inserted to improve coverage.

## E. Clinical modality authority (reused, not invented)

The repository clinically recognizes exactly two radionuclide → modality
bindings: **F-18 → PET** and **Tc-99m → SPECT** (reused from
`synthetic_radionuclide_source_capability._CLINICALLY_RECOGNIZED_RADIONUCLIDES_BY_MODALITY`,
consistent with `oncology_pet_spect_scenario.PET_RADIONUCLIDE / SPECT_RADIONUCLIDE`).
`CLINICALLY_MODALITY_CLASSIFIED_COUNT = 2`. Every other physically-recognized
radionuclide is `CLINICAL_MODALITY_NOT_MODELED` — reported, never invented.

## F. Procedure authority

No radionuclide-specific clinical procedure classes exist in the repository.
Every entry reports `PROCEDURE_NOT_MODELED`. `PROCEDURE_AUTHORIZED_COUNT = 0`.
Procedures are not fabricated from general medical knowledge.

## G. Source capability (selected-source specific)

Resolved only from the **selected / installed** cyclotron and generator sources,
never the global catalog. Per radionuclide:

- `SUPPORTED_BY_SELECTED_SOURCE` — a selected cyclotron `supported_radionuclides`
  or generator `daughter_radionuclide` includes it;
- `SUPPORTED_BY_CATALOG_ONLY` — some catalog machine supports it but none is
  selected → **never** NORMAL-admissible (no global-catalog fallback);
- `NO_COMPATIBLE_SOURCE` — no cyclotron/generator anywhere produces it.

## H. Production identity ≠ source support (never collapsed)

`production_calibration_status` is separate from support and from clinical
admissibility: `MANUFACTURER_CALIBRATED` (selected model has a manufacturer EOB
point) / `MODELED` (schedulable) / `NOT_CALIBRATED` (supported but not
schedulable, e.g. CYPRIS MP-30 + F-18; also generator daughters) /
`PRODUCTION_NOT_APPLICABLE` (no selected source). A `NOT_CALIBRATED` radionuclide
is still clinically admissible when the rest of the chain passes. **No GE
capacity is borrowed** for CYPRIS.

## I. Generator parent/daughter boundary

Generator authority is **Mo-99 → Tc-99m** only (`CURIUM_TECHNELITE`,
`CURIUM_ULTRA_TECHNEKOW_FM`, `GE_HEALTHCARE_DRYTEC`). **Mo-99** is a production
parent, marked `is_generator_parent=True`, and is **never** patient-administered
demand. **Ge-68/Ga-68 generator is NOT_MODELED** (OG-GEN-1): Ga-68 appears only
as a cyclotron-supported radionuclide.

## J. Scanner compatibility

Reuses the Scanner Authority Review boundary: **modality-level only**. A PET
radionuclide requires a PET scanner modality; a SPECT radionuclide requires a
SPECT scanner modality. Model-specific radionuclide compatibility is
`NOT_MODELED` (OG-SCN-1). When the required modality is absent from the scenario,
`NO_COMPATIBLE_SCANNER` is surfaced; unreachable demand is never generated
silently.

## K. NORMAL mode

The full admissibility chain:

```
SELECTED SOURCES -> PHYSICALLY SUPPORTED -> CLINICALLY CLASSIFIED
  -> (procedure not required today) -> DECAY-AUTHORIZED -> SCANNER-COMPATIBLE
  -> NORMAL ADMISSIBLE
```

A radionuclide is `NORMAL_ADMISSIBLE` only if it survives every link. The
`blocking_gap` follows a stable precedence:
`CLINICAL_MODALITY_NOT_MODELED` → `DECAY_AUTHORITY_MISSING` →
`NO_COMPATIBLE_SOURCE` → `NO_COMPATIBLE_SCANNER`. No silent substitution, no
F-18 fallback, no Tc-99m fallback, no global-catalog borrowing.
`NORMAL_SYNTHETIC_ADMISSIBLE_COUNT = 2` (F-18, Tc-99m) with a compatible selected
source and both scanner modalities present.

## L. STRESS mode

Every physically-recognized radionuclide identity remains `stress_visible=True`;
STRESS callers may deliberately request unsupported / unclassified / infeasible
radionuclides. The identity is preserved and the precise reason
(`NO_COMPATIBLE_SOURCE`, `CLINICAL_MODALITY_NOT_MODELED`, `DECAY_AUTHORITY_MISSING`,
`NO_COMPATIBLE_SCANNER`) is exposed. Never substituted.

## M. Explicit-demand mode

Explicit patient demand (`patient_radionuclide_demand.PatientRadionuclideDemand`)
remains authoritative and is never source-rewritten. The portfolio reports
`explicit_demand_representable` (true when canonical decay authority exists, which
is what the explicit-demand validator itself requires). Identity, activity,
appointment linkage survive; feasibility is a downstream result.

## N. Short-half-life controls (C-11 / N-13 / O-15)

Strategically important time-sensitivity controls. Each has physics known,
half-life known, and cyclotron support (schedulable on GE PETtrace 800), but each
is `NORMAL_EXCLUDED` with `blocking_gap = CLINICAL_MODALITY_NOT_MODELED`. They are
independently represented (never collapsed into F-18), remain stress-visible, and
are **not** forced admissible. `SHORT_HALF_LIFE_NORMAL_ADMISSIBLE_COUNT = 0`.

## O. Ga-68 / Cu-64 / Zr-89 / I-123 / I-124 controls

- **Ga-68:** half-life present, cyclotron-supported, **no generator** (OG-GEN-1),
  `CLINICAL_MODALITY_NOT_MODELED` → `NORMAL_EXCLUDED`.
- **Cu-64, Zr-89, I-123, I-124:** cyclotron-supported but `DECAY_AUTHORITY_MISSING`
  and `CLINICAL_MODALITY_NOT_MODELED` → `NORMAL_EXCLUDED`. No PET eligibility
  inferred from external medical knowledge.

## P. Multi-source behavior

- **Multi-cyclotron union:** a radionuclide admits if ≥1 selected cyclotron
  supports it; all compatible selected ids are preserved (no averaged machine).
- **Multi-generator union:** duplicate Tc-99m support yields **one** identity with
  multiple compatible source ids (no duplicate demand classes).
- A radionuclide supported only by an **unselected** machine never enters the
  portfolio as admissible.

## Q. Multi-radionuclide weighting

`MULTI_RADIONUCLIDE_WEIGHTING_AUTHORITY = NOT_MODELED`. No canonical clinical
weighting / prevalence authority exists; the portfolio never fabricates a demand
mix. `PORTFOLIO != DEMAND MIX`. This does not prevent the portfolio from
containing several admissible radionuclides — it only prevents auto-generating an
invented patient mix.

## R. Part 3E interface

Part 3E will consume `ClinicalRadionuclidePortfolioResult` **plus** a separate
`DemandScenario`. The portfolio carries **no** cost/NPV/CapEx/OPEX/architecture
ranking — it says only *what may be requested*. `part3e_eligible` is expressed per
entry (`PART3E_ELIGIBLE` when clinically classified **and** decay-authorized).

## S. Radionuclide sensitivity seam (documented, not implemented)

Future Part 3E scenarios (F-18-dominant, short-half-life PET, mixed PET/SPECT) are
the sensitivity seam. **No MRT advantage is encoded here.** Part 3E must discover
architecture consequences from physics downstream.

## T. Patient-export seam (preserved)

The portfolio never destroys the radionuclide identity + compatible source ids
needed for downstream patient-level export (patient_id, radionuclide, activity,
appointment, production source, batch, release timing, scanner assignment). The
export engine is **not** built here.

## U. Financial-export seam (preserved)

No financial dependency is introduced into the clinical portfolio authority (no
`equal_budget`, `equipment_opex_authority`, or `apply_study_scope` import). The
future separate financial-export requirement is preserved untouched.

## V. Calendar seam (preserved)

The long-horizon Hospital Master Calendar remains a separate downstream authority.
The portfolio has no date/calendar/horizon fields. Future chain:
`PORTFOLIO → DEMAND SCENARIO → PATIENT APPOINTMENTS → HOSPITAL MASTER CALENDAR →
PATIENT-AWARE BATCH PLANNING → PRODUCTION → TRANSPORT → SCANNER ASSIGNMENT`.

## W. Result types

`ClinicalRadionuclidePortfolioEntry` (one immutable row per radionuclide) and
`ClinicalRadionuclidePortfolioResult` (immutable portfolio-level contract). Every
distinction the doctrine forbids collapsing is a separate field
(physically-known / clinically-classified / supported / calibrated /
scanner-compatible / normal-admissible / stress-visible / explicit-representable /
part3e-eligible).

## X. Portfolio counts (from the physical authority)

| Count | Value |
| --- | --- |
| PHYSICALLY_RECOGNIZED_RADIONUCLIDE_COUNT | 15 |
| HALF_LIFE_SUPPORTED_COUNT | 7 |
| CLINICALLY_MODALITY_CLASSIFIED_COUNT | 2 |
| PROCEDURE_AUTHORIZED_COUNT | 0 |
| NORMAL_SYNTHETIC_ADMISSIBLE_COUNT | 2 |
| STRESS_VISIBLE_COUNT | 15 |
| EXPLICIT_DEMAND_REPRESENTABLE_COUNT | 7 (decay-authorized) |
| PART_3E_PORTFOLIO_ELIGIBLE_COUNT | 2 |
| SHORT_HALF_LIFE_NORMAL_ADMISSIBLE_COUNT | 0 |

## Y. Full radionuclide matrix

| Radionuclide | HL(min) | Decay | Modality | Cyc supported | Gen daughter | NORMAL | Blocking gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F-18 | 109.8 | present | PET | yes | — | **ADMISSIBLE** | — |
| Tc-99m | 360.0 | present | SPECT | — | yes | **ADMISSIBLE** | — |
| C-11 | 20.3 | present | NOT_MODELED | yes | — | excluded | CLINICAL_MODALITY_NOT_MODELED |
| N-13 | 9.97 | present | NOT_MODELED | yes | — | excluded | CLINICAL_MODALITY_NOT_MODELED |
| O-15 | 2.04 | present | NOT_MODELED | yes | — | excluded | CLINICAL_MODALITY_NOT_MODELED |
| Ga-68 | 67.7 | present | NOT_MODELED | yes | — (OG-GEN-1) | excluded | CLINICAL_MODALITY_NOT_MODELED |
| Mo-99 | 3956.4 | present | NOT_MODELED | — | parent | excluded | CLINICAL_MODALITY_NOT_MODELED |
| Cu-64 | — | missing | NOT_MODELED | yes | — | excluded | CLINICAL_MODALITY_NOT_MODELED |
| Zr-89 | — | missing | NOT_MODELED | yes | — | excluded | CLINICAL_MODALITY_NOT_MODELED |
| Ge-68 | — | missing | NOT_MODELED | yes | — | excluded | CLINICAL_MODALITY_NOT_MODELED |
| I-123 | — | missing | NOT_MODELED | yes | — | excluded | CLINICAL_MODALITY_NOT_MODELED |
| I-124 | — | missing | NOT_MODELED | yes | — | excluded | CLINICAL_MODALITY_NOT_MODELED |
| In-111 | — | missing | NOT_MODELED | yes | — | excluded | CLINICAL_MODALITY_NOT_MODELED |
| Tl-201 | — | missing | NOT_MODELED | yes | — | excluded | CLINICAL_MODALITY_NOT_MODELED |
| At-211 | — | missing | NOT_MODELED | yes | — | excluded | CLINICAL_MODALITY_NOT_MODELED |

(Blocking gap shows the FIRST failing link in precedence order; radionuclides with
`missing` decay would also fail `DECAY_AUTHORITY_MISSING` had they been clinically
classified.)

## Z. Limitations / remaining gaps (honestly disclosed)

- **Clinical modality evidence is incomplete** for 13 of 15 physically-recognized
  radionuclides (only F-18/Tc-99m classified). Reported, never invented.
- **Procedure authority is absent** (`PROCEDURE_NOT_MODELED`).
- **Decay authority is missing** for Cu-64/Zr-89/Ge-68/I-123/I-124/In-111/Tl-201/
  At-211.
- **Ge-68/Ga-68 generator is NOT_MODELED** (OG-GEN-1).
- **Model-specific scanner radionuclide compatibility is NOT_MODELED** (OG-SCN-1);
  only PET/SPECT modality is authoritative.
- **Multi-radionuclide weighting is NOT_MODELED** — the portfolio never fabricates
  a demand mix.
- These are why `OG-RAD-1 = PARTIAL`, not CLOSED. Closing would require
  repository-owned clinical modality / procedure evidence and canonical decay
  physics for the remaining radionuclides — none fabricated in this build.

---

*This repository Markdown file is the canonical governance document for the
Clinical Radionuclide Portfolio Authority.*

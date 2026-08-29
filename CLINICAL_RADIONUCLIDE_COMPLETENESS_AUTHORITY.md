# Clinical Radionuclide Completeness & Evidence Closure (Pre-Part-3E)

**Build:** Clinical Radionuclide Completeness & Evidence Closure — Pre-Part-3E
Evidence Build (starting SHA `6343ca1`; **uncommitted** — evidence build first).
**Purpose:** determine whether radionuclides excluded from the NORMAL clinical
portfolio were excluded because the evidence *does not exist* or because the
repository had simply *not yet incorporated available authoritative evidence* —
then propagate the found evidence into the CANONICAL authorities and recompute
the portfolio. The governing objective is **COMPLETENESS**, not making any
architecture win.

**Governing doctrine (never collapsed):**

```
CLINICAL INCLUSION   != MRT PREFERENCE
PHYSICAL SUPPORT     != CLINICAL USE
CLINICAL USE         != PRODUCTION CALIBRATION
SUPPORTED            != CALIBRATED != MODELED ESTIMATE
PORTFOLIO            != DEMAND MIX != OPTIMIZATION RESULT
```

**New artifacts:** `clinical_radionuclide_evidence.json` (canonical evidence
registry), `test_clinical_radionuclide_completeness.py` (62 tests: 50 invariants
+ 9 control proofs A–I + 3 traceability tests), this document.

**Canonical authorities updated (evidence-gated):** `radionuclides.json`
(half-life table 7 → 15), `synthetic_radionuclide_source_capability.py`
(the single canonical clinical modality authority, 2 → 12 bindings),
`generator_equipment_catalog.json` (added the Ge-68/Ga-68 generator, OG-GEN-1).

> *Content from external sources was rephrased/summarized for compliance with
> licensing restrictions; only short factual values (half-life, modality,
> indication) are carried, each with an inline source reference in the registry.*

---

## A. Method

1. **Authority-first read** — reproduced the CURRENT canonical matrix from the
   physical authorities BEFORE any external research.
2. **Physical universe rebuild** — union of `radionuclides.json` ∪ cyclotron
   `supported_radionuclides` ∪ generator daughters ∪ generator parents.
3. **Deep external evidence search** — authoritative sources preferred in order:
   manufacturer docs → FDA/regulatory labeling → IAEA/LNHB/ENSDF nuclear data →
   SNMMI/EANM professional guidance → peer-reviewed clinical/production
   literature.
4. **Evidence registry** — every found fact recorded with raw + normalized value,
   evidence class, confidence, and source reference in
   `clinical_radionuclide_evidence.json`.
5. **Canonical propagation** — each evidence-closed fact written to the canonical
   authority that OWNS it (not the registry/report only), then the portfolio
   RECOMPUTED (never manually set).
6. **Test-locking** — each promoted canonical fact protected by a test.

## B. Evidence classes used

`MANUFACTURER_SPECIFIED`, `REGULATORY`, `PROFESSIONAL_GUIDELINE`,
`AUTHORITATIVE_NUCLEAR_DATA`, `PEER_REVIEWED_CLINICAL`,
`PEER_REVIEWED_PRODUCTION`, `LITERATURE_DERIVED`, `MODELED_ESTIMATE`,
`CONTROLLED_ASSUMPTION`, `NOT_AVAILABLE`. Literature is never labelled
`MANUFACTURER_CALIBRATED`; modeled values are never labelled measured.

---

## TABLE 1 — Physical radionuclide universe (discovered, not hardcoded)

`PHYSICALLY_RECOGNIZED_RADIONUCLIDE_COUNT = 15` (unchanged by this build).

| # | Radionuclide | First recognized via |
| --- | --- | --- |
| 1 | At-211 | cyclotron `supported_radionuclides` (IBA 30XP) |
| 2 | C-11 | half-life table + cyclotron support |
| 3 | Cu-64 | cyclotron support (KIUBE/IKON/30XP/CYPRIS/ACSI) |
| 4 | F-18 | half-life table + cyclotron support (control) |
| 5 | Ga-68 | half-life table + cyclotron support + **now generator daughter** |
| 6 | Ge-68 | cyclotron support (IKON/30XP) + **now generator parent** |
| 7 | I-123 | cyclotron support (KIUBE/IKON/30XP/CYPRIS) |
| 8 | I-124 | cyclotron support (KIUBE/IKON/CYPRIS/ACSI) |
| 9 | In-111 | cyclotron support (IBA 30XP) |
| 10 | Mo-99 | generator parent (Mo-99/Tc-99m) |
| 11 | N-13 | half-life table + cyclotron support |
| 12 | O-15 | half-life table + cyclotron support |
| 13 | Tc-99m | half-life table + generator daughter (control) |
| 14 | Tl-201 | cyclotron support (IKON/30XP) |
| 15 | Zr-89 | cyclotron support (KIUBE/IKON/30XP/CYPRIS/ACSI) |

---

## TABLE 2 — Half-life / decay evidence (canonical `radionuclides.json`)

`HALF_LIFE_SUPPORTED_COUNT = 15` (was **7**). Eight half-lives newly propagated.

| Radionuclide | Half-life (raw) | Normalized (min) | Evidence class | Status | Evidence id |
| --- | --- | --- | --- | --- | --- |
| F-18 | 109.8 min | 109.8 | AUTHORITATIVE_NUCLEAR_DATA | pre-existing | EV-F18-HL-001 |
| C-11 | 20.3 min | 20.3 | AUTHORITATIVE_NUCLEAR_DATA | pre-existing | EV-C11-HL-001 |
| N-13 | 9.97 min | 9.97 | AUTHORITATIVE_NUCLEAR_DATA | pre-existing | EV-N13-HL-001 |
| O-15 | 2.04 min | 2.04 | AUTHORITATIVE_NUCLEAR_DATA | pre-existing | EV-O15-HL-001 |
| Ga-68 | 67.7 min | 67.7 | AUTHORITATIVE_NUCLEAR_DATA | pre-existing | EV-GA68-HL-001 |
| Tc-99m | 360.0 min | 360.0 | AUTHORITATIVE_NUCLEAR_DATA | pre-existing | EV-TC99M-HL-001 |
| Mo-99 | 3956.4 min | 3956.4 | AUTHORITATIVE_NUCLEAR_DATA | pre-existing | EV-MO99-HL-001 |
| **Cu-64** | 12.7 h | **762.0** | AUTHORITATIVE_NUCLEAR_DATA | **ADDED** | EV-CU64-HL-001 |
| **Zr-89** | 78.42 h | **4705.2** | AUTHORITATIVE_NUCLEAR_DATA | **ADDED** | EV-ZR89-HL-001 |
| **Ge-68** | 271.14 d | **390441.6** | PEER_REVIEWED_PRODUCTION | **ADDED** | EV-GE68-HL-001 |
| **I-123** | 13.2 h | **792.0** | REGULATORY | **ADDED** | EV-I123-HL-001 |
| **I-124** | 100.2 h | **6012.0** | PEER_REVIEWED_CLINICAL | **ADDED** | EV-I124-HL-001 |
| **In-111** | 2.8048 d | **4038.912** | AUTHORITATIVE_NUCLEAR_DATA | **ADDED** | EV-IN111-HL-001 |
| **Tl-201** | 3.0421 d | **4380.624** | AUTHORITATIVE_NUCLEAR_DATA | **ADDED** | EV-TL201-HL-001 |
| **At-211** | 7.216 h | **432.96** | AUTHORITATIVE_NUCLEAR_DATA | **ADDED** | EV-AT211-HL-001 |

The single decay authority (`diagnostics.load_radionuclide_half_lives` →
`radionuclides.json`) is consumed unchanged by `multi_isotope_decay`; **no second
decay table** was created (test-locked).

---

## TABLE 3 — Clinical modality evidence (canonical modality authority)

`CLINICALLY_MODALITY_CLASSIFIED_COUNT = 12` (was **2**). Ten bindings newly
propagated into the single `_CLINICALLY_RECOGNIZED_RADIONUCLIDES_BY_MODALITY`
authority (consumed by both the portfolio and the synthetic-capability authority).
Classification is by EMISSION evidence (positron → PET, single gamma → SPECT),
never by element.

| Radionuclide | Modality | Basis | Evidence class | Status | Evidence id |
| --- | --- | --- | --- | --- | --- |
| F-18 | PET | control | AUTHORITATIVE_NUCLEAR_DATA | pre-existing | — |
| Tc-99m | SPECT | control | AUTHORITATIVE_NUCLEAR_DATA | pre-existing | — |
| **C-11** | PET | FDA Choline C-11 (prostate) | REGULATORY | **ADDED** | EV-C11-MOD-001 |
| **N-13** | PET | FDA Ammonia N-13 (myocardial perfusion) | REGULATORY | **ADDED** | EV-N13-MOD-001 |
| **O-15** | PET | [15O]water PET perfusion | PEER_REVIEWED_CLINICAL | **ADDED** | EV-O15-MOD-001 |
| **Ga-68** | PET | FDA 68Ga-DOTATATE / SNMMI 68Ga-PSMA-11 | REGULATORY | **ADDED** | EV-GA68-MOD-001 |
| **Cu-64** | PET | FDA Cu-64 DOTATATE (Detectnet), NET | REGULATORY | **ADDED** | EV-CU64-MOD-001 |
| **Zr-89** | PET | Zr-89 immunoPET | PEER_REVIEWED_CLINICAL | **ADDED** | EV-ZR89-MOD-001 |
| **I-124** | PET | I-124 immunoPET (antibody) | PEER_REVIEWED_CLINICAL | **ADDED** | EV-I124-MOD-001 |
| **I-123** | SPECT | FDA Sodium Iodide I-123 (gamma, 159 keV) | REGULATORY | **ADDED** | EV-I123-MOD-001 |
| **In-111** | SPECT | FDA In-111 pentetreotide (OctreoScan) | REGULATORY | **ADDED** | EV-IN111-MOD-001 |
| **Tl-201** | SPECT | FDA Thallous Chloride Tl-201 (myocardial) | REGULATORY | **ADDED** | EV-TL201-MOD-001 |
| At-211 | *(THERAPY — no diagnostic modality)* | alpha emitter | PEER_REVIEWED_CLINICAL | recognized, not scanner | EV-AT211-USE-001 |
| Ge-68 | *(GENERATOR PARENT — not administered)* | Ge-68/Ga-68 generator | — | recognized, not scanner | EV-GE68-HL-001 |
| Mo-99 | *(GENERATOR PARENT — not administered)* | Mo-99/Tc-99m generator | — | recognized, not scanner | — |

---

## TABLE 4 — Procedure / use evidence

`PROCEDURE_AUTHORIZED_OR_PARTIAL_COUNT = 0` (canonical status). A radionuclide-
specific PROCEDURE classification authority is **still NOT_MODELED**: the build
closed *modality* and *decay* completeness, not procedure taxonomy. Procedure /
clinical-use *context* is preserved in the evidence registry (below) but the
canonical portfolio reports `PROCEDURE_NOT_MODELED` for every entry — never
fabricated.

| Radionuclide | Procedure / use context (registry, not canonical procedure authority) | Portfolio procedure status |
| --- | --- | --- |
| F-18 | oncology PET (control) | PROCEDURE_NOT_MODELED |
| C-11 | oncology — recurrent prostate cancer PET | PROCEDURE_NOT_MODELED |
| N-13 | cardiology — myocardial perfusion PET | PROCEDURE_NOT_MODELED |
| O-15 | neurology / cardiology — perfusion / blood-flow PET | PROCEDURE_NOT_MODELED |
| Ga-68 | oncology — NET (DOTATATE), prostate (PSMA) PET | PROCEDURE_NOT_MODELED |
| Cu-64 | oncology — NET localization PET (Detectnet) | PROCEDURE_NOT_MODELED |
| Zr-89 | oncology — immunoPET (antibody targets) | PROCEDURE_NOT_MODELED |
| I-124 | oncology — immunoPET / thyroid PET dosimetry | PROCEDURE_NOT_MODELED |
| I-123 | endocrine — thyroid gamma imaging; brain SPECT | PROCEDURE_NOT_MODELED |
| In-111 | oncology / infection — somatostatin, leukocyte SPECT | PROCEDURE_NOT_MODELED |
| Tl-201 | cardiology — myocardial perfusion SPECT | PROCEDURE_NOT_MODELED |
| At-211 | oncology — targeted alpha THERAPY | PROCEDURE_NOT_MODELED |
| Tc-99m | broad SPECT (control) | PROCEDURE_NOT_MODELED |
| Ge-68 / Mo-99 | generator parents (feedstock) | PROCEDURE_NOT_MODELED |

---

## TABLE 5 — Generator pathways (canonical `generator_equipment_catalog.json`)

OG-GEN-1 **closed**: the Ge-68/Ga-68 generator pathway is now canonical, distinct
from Mo-99/Tc-99m.

| Generator model | Parent | Daughter | Daughter modality | Economics | Status |
| --- | --- | --- | --- | --- | --- |
| CURIUM_TECHNELITE | Mo-99 | Tc-99m | SPECT | NOT_CALIBRATED | pre-existing |
| CURIUM_ULTRA_TECHNEKOW_FM | Mo-99 | Tc-99m | SPECT | NOT_CALIBRATED | pre-existing |
| GE_HEALTHCARE_DRYTEC | Mo-99 | Tc-99m | SPECT | NOT_CALIBRATED | pre-existing |
| **ECKERT_ZIEGLER_GALLIAPHARM** | **Ge-68** | **Ga-68** | PET | NOT_CALIBRATED | **ADDED** |

Parent identities (`Mo-99`, `Ge-68`) and daughter identities (`Tc-99m`, `Ga-68`)
never collapse (test-locked). Cyclotron-produced Ga-68 and generator-produced
Ga-68 are kept as **distinct** production pathways.

---

## TABLE 6 — Cyclotron model × radionuclide support matrix

Cell legend: `C` = the exact model/radionuclide pair has manufacturer-calibrated
quantitative EOB evidence · `S` = the exact model *declares* radionuclide support
(`supported_radionuclides`), but this symbol alone does **not** imply calibrated
quantitative production · `.` = the exact model does not declare support for that
radionuclide. Explicitly: **`S` != `MANUFACTURER_CALIBRATED`** — an `S` cell is a
support declaration only, never a production-output claim. **Model identity is
exact; no support was widened by this build** (support was already declared per
model). No production output is borrowed across models.

| Model | F-18 | C-11 | N-13 | O-15 | Ga-68 | Cu-64 | Zr-89 | I-123 | I-124 | In-111 | Tl-201 | At-211 | Ge-68 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GE_PETTRACE_840 | C | . | . | . | . | . | . | . | . | . | . | . | . |
| GE_PETTRACE_860 | C | . | . | . | . | . | . | . | . | . | . | . | . |
| GE_PETTRACE_880 | C | . | . | . | . | . | . | . | . | . | . | . | . |
| GE_PETTRACE_890 | C | . | . | . | . | . | . | . | . | . | . | . | . |
| GE_PETTRACE_800 | S | S | S | S | S | . | . | . | . | . | . | . | . |
| IBA_CYCLONE_KEY | C | S | S | . | . | . | . | . | . | . | . | . | . |
| IBA_CYCLONE_KIUBE | C | S | S | S | S | S | S | S | S | . | . | . | . |
| IBA_CYCLONE_IKON | S | . | . | . | S | S | S | S | S | . | S | . | S |
| IBA_CYCLONE_30XP | S | . | . | . | . | S | S | S | . | S | S | S | S |
| SUMITOMO_CYPRIS_HM_12 | S | S | S | S | S | S | S | S | S | . | . | . | . |
| SUMITOMO_CYPRIS_HM_20 | S | S | S | S | S | S | S | S | S | . | . | . | . |
| SUMITOMO_CYPRIS_MP_30 | S | . | . | . | S | S | S | S | S | . | . | . | . |
| SIEMENS_CTI_ECLIPSE_HP | S | S | S | S | . | . | . | . | . | . | . | . | . |
| SIEMENS_CTI_RDS_111 | S | S | S | S | . | . | . | . | . | . | . | . | . |
| ACSI_TR_19 | S | S | S | S | . | S | S | . | S | . | . | . | . |
| ACSI_TR_24 | S | S | S | S | . | S | S | . | S | . | . | . | . |
| BEST_14P | S | . | . | . | . | . | . | . | . | . | . | . | . |

---

## TABLE 7 — Quantitative production evidence (unchanged by this build)

Clinical inclusion ≠ quantitative production. This build did **not** create any
new quantitative production estimate; those remain governed by the Cyclotron
Production Estimation / Evidence Authority (OG-CYC-1). Manufacturer-calibrated
EOB anchors (existing):

| Model | Radionuclide | Normalized EOB (MBq) | Class |
| --- | --- | --- | --- |
| GE_PETTRACE_840 | F-18 | 240 000 | MANUFACTURER_CALIBRATED |
| GE_PETTRACE_860 | F-18 | 403 000 | MANUFACTURER_CALIBRATED |
| GE_PETTRACE_880 | F-18 | 524 000 | MANUFACTURER_CALIBRATED |
| GE_PETTRACE_890 | F-18 | 648 000 | MANUFACTURER_CALIBRATED |
| IBA_CYCLONE_KEY | F-18 | 111 000 | MANUFACTURER_CALIBRATED |
| IBA_CYCLONE_KIUBE | F-18 | 1 406 000 | MANUFACTURER_CALIBRATED |
| SIEMENS_CTI_ECLIPSE_HP / RDS_111 | F-18 | ≈264 528 | MODELED_ESTIMATE (reaction yield) |
| all other model × radionuclide pairs | — | — | NOT_AVAILABLE / OUT_OF_CYCLOTRON_SCOPE |

CYPRIS MP-30 + F-18 remains SUPPORTED but `NOT_CALIBRATED` / `NOT_AVAILABLE` (no
own beam current; no GE borrowing).

---

## TABLE 8 — Scanner modality compatibility (modality-level, OG-SCN-1)

Reuses the Scanner Authority Review boundary: **modality-level only**. PET
radionuclide → PET scanner; SPECT radionuclide → SPECT scanner; THERAPY-only and
generator parents impose **no** diagnostic scanner requirement.

| Radionuclide | Required scanner modality |
| --- | --- |
| F-18, C-11, N-13, O-15, Ga-68, Cu-64, Zr-89, I-124 | PET |
| Tc-99m, I-123, In-111, Tl-201 | SPECT |
| At-211 | *(none — THERAPY, never scanner demand)* |
| Ge-68, Mo-99 | *(none — generator parents)* |

---

## TABLE 9 — NORMAL / STRESS / EXPLICIT status (full-universe scenario)

Scenario: all catalog cyclotrons + all generators + both scanner modalities
selected. `blocking_gap` shows the first failing link (precedence:
`CLINICAL_MODALITY_NOT_MODELED` → `DECAY_AUTHORITY_MISSING` →
`NO_COMPATIBLE_SOURCE` → `NO_COMPATIBLE_SCANNER`).

| Radionuclide | Modality | Decay | NORMAL | STRESS visible | Explicit representable | Blocking gap |
| --- | --- | --- | --- | --- | --- | --- |
| F-18 | PET | present | **ADMISSIBLE** | yes | yes | — |
| C-11 | PET | present | **ADMISSIBLE** | yes | yes | — |
| N-13 | PET | present | **ADMISSIBLE** | yes | yes | — |
| O-15 | PET | present | **ADMISSIBLE** | yes | yes | — |
| Ga-68 | PET | present | **ADMISSIBLE** | yes | yes | — |
| Cu-64 | PET | present | **ADMISSIBLE** | yes | yes | — |
| Zr-89 | PET | present | **ADMISSIBLE** | yes | yes | — |
| I-124 | PET | present | **ADMISSIBLE** | yes | yes | — |
| Tc-99m | SPECT | present | **ADMISSIBLE** | yes | yes | — |
| I-123 | SPECT | present | **ADMISSIBLE** | yes | yes | — |
| In-111 | SPECT | present | **ADMISSIBLE** | yes | yes | — |
| Tl-201 | SPECT | present | **ADMISSIBLE** | yes | yes | — |
| At-211 | — (THERAPY) | present | excluded | yes | yes | CLINICAL_MODALITY_NOT_MODELED |
| Ge-68 | — (gen parent) | present | excluded | yes | yes | CLINICAL_MODALITY_NOT_MODELED |
| Mo-99 | — (gen parent) | present | excluded | yes | yes | CLINICAL_MODALITY_NOT_MODELED |

`NORMAL_SYNTHETIC_ADMISSIBLE_COUNT = 12` · `STRESS_VISIBLE_COUNT = 15` ·
`EXPLICIT_DEMAND_REPRESENTABLE_COUNT = 15`.

> The three excluded radionuclides are excluded **honestly**: At-211 is a THERAPY
> radionuclide (no diagnostic scanner modality) and Ge-68 / Mo-99 are generator
> PARENTS (production feedstock, never patient-administered). Their blocking gap
> is reported as `CLINICAL_MODALITY_NOT_MODELED` because they carry no *diagnostic*
> modality — this is correct completeness (not every radionuclide is scanner
> demand), documented and test-locked, not an unclosed gap.

---

## TABLE 10 — Part 3E portfolio eligibility

`PART_3E_PORTFOLIO_ELIGIBLE_COUNT = 12` (clinically modality-classified AND
decay-authorized). Eligibility is architecture-neutral and expressed per entry.

| Eligible (12) | Not eligible (3) | Reason not eligible |
| --- | --- | --- |
| F-18, C-11, N-13, O-15, Ga-68, Cu-64, Zr-89, I-124, Tc-99m, I-123, In-111, Tl-201 | At-211 | THERAPY — no diagnostic modality |
| | Ge-68 | generator parent — not administered |
| | Mo-99 | generator parent — not administered |

---

## TABLE 11 — Evidence gaps by radionuclide (remaining, honest)

| Radionuclide | Remaining gap |
| --- | --- |
| All 15 | Radionuclide-specific PROCEDURE authority NOT_MODELED (modality closed, procedure not) |
| C-11, N-13, O-15, Ga-68, Cu-64, Zr-89, I-124 | Quantitative production mostly NOT_CALIBRATED / MODELED (OG-CYC-1) |
| Ge-68/Ga-68 generator | Procurement economics / model reference-activity NOT_CALIBRATED |
| Tc-99m, Ga-68 (generator) | Generator model economics NOT_CALIBRATED |
| At-211 | THERAPY dosimetry / production not modeled (recognized as therapy only) |
| Multi-radionuclide mix | Prevalence / demand weighting NOT_MODELED (PORTFOLIO != DEMAND MIX) |
| Scanner | Model-specific radionuclide compatibility NOT_MODELED (OG-SCN-1; modality-level only) |

---

## TABLE 12 — Canonical-authority propagation changes (Section M.1 traceability)

| Canonical file | Radionuclide | Fact changed | Previous | New | Evidence id | Test-locking |
| --- | --- | --- | --- | --- | --- | --- |
| radionuclides.json | Cu-64 | half-life | MISSING | 762.0 min | EV-CU64-HL-001 | test_09/25, proof_g |
| radionuclides.json | Zr-89 | half-life | MISSING | 4705.2 min | EV-ZR89-HL-001 | test_09/26, proof_g |
| radionuclides.json | Ge-68 | half-life | MISSING | 390441.6 min | EV-GE68-HL-001 | test_09/31 |
| radionuclides.json | I-123 | half-life | MISSING | 792.0 min | EV-I123-HL-001 | test_09/27 |
| radionuclides.json | I-124 | half-life | MISSING | 6012.0 min | EV-I124-HL-001 | test_09/28 |
| radionuclides.json | In-111 | half-life | MISSING | 4038.912 min | EV-IN111-HL-001 | test_09/32 |
| radionuclides.json | Tl-201 | half-life | MISSING | 4380.624 min | EV-TL201-HL-001 | test_09/33 |
| radionuclides.json | At-211 | half-life | MISSING | 432.96 min | EV-AT211-HL-001 | test_09/30 |
| synthetic_radionuclide_source_capability.py | C-11 | modality | NOT_MODELED | PET | EV-C11-MOD-001 | test_21, proof_c |
| synthetic_radionuclide_source_capability.py | N-13 | modality | NOT_MODELED | PET | EV-N13-MOD-001 | test_22, proof_d |
| synthetic_radionuclide_source_capability.py | O-15 | modality | NOT_MODELED | PET | EV-O15-MOD-001 | test_23, proof_e |
| synthetic_radionuclide_source_capability.py | Ga-68 | modality | NOT_MODELED | PET | EV-GA68-MOD-001 | test_24, proof_f |
| synthetic_radionuclide_source_capability.py | Cu-64 | modality | NOT_MODELED | PET | EV-CU64-MOD-001 | test_25 |
| synthetic_radionuclide_source_capability.py | Zr-89 | modality | NOT_MODELED | PET | EV-ZR89-MOD-001 | test_26 |
| synthetic_radionuclide_source_capability.py | I-124 | modality | NOT_MODELED | PET | EV-I124-MOD-001 | test_28 |
| synthetic_radionuclide_source_capability.py | I-123 | modality | NOT_MODELED | SPECT | EV-I123-MOD-001 | test_27/29 |
| synthetic_radionuclide_source_capability.py | In-111 | modality | NOT_MODELED | SPECT | EV-IN111-MOD-001 | test_32 |
| synthetic_radionuclide_source_capability.py | Tl-201 | modality | NOT_MODELED | SPECT | EV-TL201-MOD-001 | test_33 |
| generator_equipment_catalog.json | Ga-68 | generator pathway | ABSENT (OG-GEN-1) | Ge-68/Ga-68 generator | EV-GA68-GEN-001 | test_34/35, proof_f |

Every canonical change has a traceable evidence record and a protecting test. No
canonical fact was promoted without both.

---

## TABLE 13 — Current versus completed portfolio comparison

| Count | Before (SHA 6343ca1) | After completeness closure |
| --- | --- | --- |
| PHYSICALLY_RECOGNIZED_RADIONUCLIDE_COUNT | 15 | 15 |
| HALF_LIFE_SUPPORTED_COUNT | 7 | **15** |
| CLINICALLY_MODALITY_CLASSIFIED_COUNT | 2 | **12** |
| PROCEDURE_AUTHORIZED_OR_PARTIAL_COUNT | 0 | 0 |
| NORMAL_SYNTHETIC_ADMISSIBLE_COUNT | 2 | **12** |
| STRESS_VISIBLE_COUNT | 15 | 15 |
| EXPLICIT_DEMAND_REPRESENTABLE_COUNT | 7 | **15** |
| PART_3E_PORTFOLIO_ELIGIBLE_COUNT | 2 | **12** |
| SHORT_HALF_LIFE_NORMAL_ADMISSIBLE_COUNT | 0 | **3 (C-11, N-13, O-15, when source selected)** |
| Generator pathways | 1 (Mo-99/Tc-99m) | **2 (+ Ge-68/Ga-68)** |

---

## TABLE 14 — Short-half-life control summary (C-11 / N-13 / O-15)

These are the completeness controls: admitted on **exactly the same footing** as
long-lived F-18, never preferentially promoted, no MRT/transport advantage.

| Radionuclide | Half-life (min) | Modality | Before | After (with schedulable source + scanner) |
| --- | --- | --- | --- | --- |
| C-11 | 20.3 | PET | NORMAL_EXCLUDED (modality not modeled) | **NORMAL_ADMISSIBLE** |
| N-13 | 9.97 | PET | NORMAL_EXCLUDED (modality not modeled) | **NORMAL_ADMISSIBLE** |
| O-15 | 2.04 | PET | NORMAL_EXCLUDED (modality not modeled) | **NORMAL_ADMISSIBLE** |

`SHORT_HALF_LIFE_NORMAL_ADMISSIBLE_COUNT = 3`. Their admissibility follows purely
from evidence-gated modality + pre-existing decay + selected source support —
identical to any long-lived radionuclide. **No short-half-life multiplier, no MRT
bonus** (architecture neutrality test-locked).

---

## C. MRT / architecture neutrality

The completeness authority contains no reference to MRT / Conventional /
transport / decay-advantage as *preference*. Short-lived and long-lived
radionuclides are represented identically. The portfolio module imports no
economics/transport authority and exposes no cost/architecture ranking field
(structurally test-locked). Part 3E must discover architecture consequences from
physics downstream; this build encodes none.

## D. Part 3E sensitivity seam (documented, not built)

The completed evidence-based portfolio now supports future Part 3E scenarios
(F-18-dominant, short-half-life PET, mixed PET/SPECT, research/academic,
community) **without** deciding prevalence. `MULTI_RADIONUCLIDE_WEIGHTING_AUTHORITY
= NOT_MODELED` remains: portfolio inclusion never authorizes a fabricated patient
mix. `PORTFOLIO != DEMAND MIX`.

## E. Preserved seams (untouched)

Patient / calendar / export traceability, the financial engine, Equipment OPEX,
transport physics, scanner scheduling, Part 3D, capital economics, and
`equal_budget` are all **unchanged**. This build added canonical DATA
(half-lives, one generator model, modality bindings) — no equations, no
economics, no architecture.

---

*This repository Markdown file is the canonical completeness report. Every table
above is rendered inline; the downloadable evidence data lives additionally in
`clinical_radionuclide_evidence.json`.*

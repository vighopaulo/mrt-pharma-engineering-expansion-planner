# Cyclotron Production Evidence Sources

**Build:** Cyclotron Production Evidence & Calibration Extension.
**Companion registry:** `cyclotron_production_evidence.json`.
**Companion authority:** `cyclotron_production_estimation_authority.py`
(`CYCLOTRON_PRODUCTION_ESTIMATION_AUTHORITY.md`).

This document is the human-readable provenance record for every external /
physics production-evidence record the estimator may consume. It exists so that
no numerical value in the registry is unattributed.

> Content from external sources was **rephrased/summarized** for compliance with
> licensing restrictions. Raw numeric values are reported as physical facts with
> their sources; no more than a short factual figure is reproduced from any one
> source. Values reflect the cited sources; they are not manufacturer/site
> calibration.

---

## 0. Governing principle

`MODELED_ESTIMATE` ≠ `MANUFACTURER_CALIBRATED` ≠ `SITE_CALIBRATED`. Every record
below is classified **`MODELED_ESTIMATE`** and is never promoted. Reaction-level
physics is applied **only** together with a specific cyclotron model's **own**
published beam current — never as a borrowed machine capacity, and never across
radionuclides. The runtime evidence hierarchy remains
`SITE_CALIBRATED > MANUFACTURER_CALIBRATED > MODELED_ESTIMATE > CONTROLLED_ASSUMPTION > NOT_AVAILABLE`.

The calibrated controls in `cyclotron_equipment_catalog.json` (e.g. GE PETtrace
890 + F-18 = 648 000 MBq at 160 µA / 120 min) are unchanged ground truth and are
never overridden by any record here.

---

## 1. Registry evidence records (consumed by the estimator)

### EV-F18-18OPN-SAT-001 — 18O(p,n)18F saturation yield (measured)

| Field | Value |
|---|---|
| `evidence_record_id` | `EV-F18-18OPN-SAT-001` |
| Applies to model | reaction-level (`catalog_model_id = null`) |
| Radionuclide | F-18 |
| Reaction / target | `18O(p,n)18F` on enriched [18O]H₂O liquid target |
| Beam particle | proton |
| Conditions | thick-target **saturation** (EOB) yield |
| Raw value / unit | **8.3 GBq/µA** (reported as ~80% of theoretical yield) |
| Normalized | 8 300 MBq/µA (`saturation_yield_mbq_per_ua`) |
| Normalization method | GBq/µA → MBq/µA (×1000); this is the coefficient `K` in `A_EOB = K·I·(1−e^(−λt))` |
| Evidence class | `MODELED_ESTIMATE` |
| Confidence (record) | MEDIUM (measured, used for resolver ranking) |
| Source title | Measurement of the ¹⁸F saturation yield from the ¹⁸O(p,n)¹⁸F reaction (thick liquid target) |
| Source author | Mirzaii et al. |
| Publisher | Iranian Journal of Radiation Research |
| URL | http://ijrr.com/article-1-16-en.pdf |
| Source type | peer-reviewed publication |

**Limitations:** reaction-level physics (a property of the reaction), not a
machine-specific EOB measurement; enriched-water liquid targets above the
reaction threshold; when applied to a specific model it uses that model's OWN
beam current only. `reference_irradiation_minutes = 120` is the standard FDG
production irradiation used as the default modeling condition.

### EV-F18-18OPN-SAT-002 — 18O(p,n)18F saturation yield (calculated, corroborating)

| Field | Value |
|---|---|
| `evidence_record_id` | `EV-F18-18OPN-SAT-002` |
| Applies to model | reaction-level (`catalog_model_id = null`) |
| Radionuclide | F-18 |
| Reaction / target | `18O(p,n)18F` on in-house recycled [18O]H₂O (~93% enrichment) |
| Conditions | calculated saturation yield |
| Raw value / unit | **7.8 GBq/µA** (≈210 mCi/µA) |
| Normalized | 7 800 MBq/µA (`saturation_yield_mbq_per_ua`) |
| Normalization method | GBq/µA → MBq/µA (×1000) |
| Evidence class | `MODELED_ESTIMATE` |
| Confidence (record) | LOW (calculated, enrichment-dependent) |
| Publisher | Deutsche Nationalbibliothek (archived technical record) |
| URL | https://d-nb.info/1220508144/34 |
| Source type | technical literature |

**Limitations:** calculated (not directly measured); enrichment-dependent;
corroborating record. Competing raw values (8.3 vs 7.8 GBq/µA) are **preserved**
and resolved by the documented multi-evidence resolver — **never averaged**.

---

## 2. Multi-evidence resolution (why EV-...-001 is chosen)

When several records apply to a pair, `resolve_evidence_record(...)` selects one
deterministically and exposes `selection_reason` + `competing_record_ids` (raw
records are never averaged or discarded):

1. evidence-class precedence (`stronger_basis`);
2. machine-specific record over reaction-level record;
3. confidence (HIGH > MEDIUM > LOW);
4. stable `evidence_record_id` (reproducible tie-break).

For F-18, both records are reaction-level `MODELED_ESTIMATE`, so the **measured**
record (`EV-F18-18OPN-SAT-001`, MEDIUM) outranks the **calculated** one
(`EV-F18-18OPN-SAT-002`, LOW) on confidence.

---

## 3. Corroborating context (NOT inserted as registry values)

These sources corroborate the ¹⁸O(p,n)¹⁸F saturation-yield range but are not
themselves used to produce a number; they are recorded for provenance only.

- **18F-SiFA good-practices review** (PubMed) — thick-target ¹⁸F yields in the
  range of roughly **5–14 GBq/µA**. https://pubmed.ncbi.nlm.nih.gov/37819534/
- **TRIUMF WTTC13 abstract** — at 55 µA, ~140 GBq [¹⁸F]fluoride for one hour of
  irradiation (≈84% of theoretical).
  https://wttc.triumf.ca/pdf/2010/051_ALGI_abstractWTTC13final.pdf
- **Short-irradiation operating point** (ResearchGate) — 11 MeV protons, ~35
  mCi/µA at a 5-minute (non-saturated) irradiation.
  https://www.researchgate.net/figure/Spectrum-of-the-F-18-radionuclide-observed-shortly-after-the-end-of-proton-irradiation-of_fig2_332653714

The chosen registry value (8.3 GBq/µA) sits within this corroborated range.

---

## 4. CYPRIS MP-30 evidence outcome (honest NOT_AVAILABLE)

An external search for a **CYPRIS MP-30-specific** F-18 EOB production anchor
(beam current + irradiation time + measured EOB) found none. The Sumitomo Heavy
Industries product literature confirms the MP-class machine produces ¹⁸F-FDG
(https://www.shi.co.jp/english/products/machinery/cyclotron/index.html) but
publishes **no** MP-30-specific numerical EOB anchor, and the catalog's own
`operating_character` note states MP-30 energy/current values require
authoritative reconciliation.

Because CYPRIS MP-30 publishes **no own beam current** in the repository, the
reaction-level saturation-yield record above **cannot** be applied to it without
fabricating a current or borrowing another machine's — both forbidden. Therefore:

```
SUMITOMO_CYPRIS_MP_30 + F-18  ->  SUPPORTED = YES
                                  CALIBRATION_STATUS = NOT_CALIBRATED
                                  ESTIMATION_STATUS  = NOT_AVAILABLE
                                  SIMULATION_BASIS   = NOT_AVAILABLE
                                  BORROWED_GE_CAPACITY = NO
```

This is retained honestly per the build's evidence-honesty acceptance criterion.

---

## 5. New modeled pairs enabled by this evidence

Two model × radionuclide pairs are enabled: **`SIEMENS_CTI_ECLIPSE_HP` + F-18**
and **`SIEMENS_CTI_RDS_111` + F-18**, each previously `NOT_AVAILABLE`. Both
Siemens/CTI models publish their **own** literature beam current (60 µA at
~11 MeV, `technical_literature` in the Build 3B catalog `field_provenance`) and
support F-18 (which has canonical half-life physics). Applying the reaction
saturation yield to each model's own current yields a `MODELED_ESTIMATE`:

```
A_EOB(t) = 8300 MBq/µA · 60 µA · (1 − e^(−λ·t)),  λ = ln2 / 109.8 min
        ≈ 264 528 MBq at t = 120 min (default reference condition)
```

The two pairs produce identical EOB values because both models publish the same
60 µA own beam current and share the same reaction-level saturation-yield
evidence — a physical coincidence, not a borrowed capacity. Confidence is
honestly **LOW** (reaction physics applied to a literature-grade beam current).
Each value is below GE PETtrace 890's 648 000 MBq (no capacity borrowed) and
increases monotonically with irradiation time. The Build 3B calibration status of
both models is unchanged.

# Cyclotron Production Estimation Authority

**Build:** Cyclotron Production Estimation (OG-CYC-1 closure/refinement).
**Starting authority:** branch `main`, HEAD `b8e759e`, `origin/main == b8e759e`,
working tree clean, divergence 0/0.
**Canonical file:** `cyclotron_production_estimation_authority.py`.
**Focused test:** `test_cyclotron_production_estimation_authority.py` (37 tests).
**Nature:** a new numerical **estimation** layer that sits BETWEEN existing
Build 3B production evidence and downstream batch/capacity planning. It creates
no second catalog, no second radionuclide authority, and no second capacity
resolver.

---

## A. Purpose and authority boundary

MRT Pharma is a simulation / planning system. A simulation frequently needs a
*numerical* production estimate (required EOB activity, irradiation duration,
physical cycles/batches, utilization, schedule/economic feasibility) even where
manufacturer / site production output for a cyclotron model × radionuclide pair
is `NOT_CALIBRATED`.

This authority makes explicit the distinction between three separate questions:

- **WHAT IS PHYSICALLY SUPPORTED** — the cyclotron declares it can make this
  radionuclide (Build 3B `supported_radionuclides`).
- **WHAT IS CALIBRATED** — manufacturer / site production evidence exists
  (Build 3B `production_performance_records` / `production_calibration_status`).
- **WHAT MRT PHARMA CAN NUMERICALLY ESTIMATE** — a defensible physics/evidence
  based estimate can be constructed (this authority).

> **SUPPORTED ≠ CALIBRATED ≠ NUMERICALLY ESTIMABLE.**
> A supported radionuclide may still carry `CALIBRATION_STATUS = NOT_CALIBRATED`
> **and** `ESTIMATION_STATUS = NOT_AVAILABLE` when insufficient evidence exists.

> **MODELED_ESTIMATE ≠ MANUFACTURER_CALIBRATED ≠ SITE_CALIBRATED.**
> A numerical estimate never overwrites the manufacturer/site calibration status
> or the raw manufacturer evidence. The result preserves BOTH the evidence
> status AND the numerical value.

The estimator is **downstream of patient-aware planning** and never becomes aware
of patient identity, patient calendar, room, or scanner assignment.

---

## B. Evidence hierarchy (runtime precedence)

Governance-locked in `MRT_PHARMA_AUTHORITY_INDEX.md`:

```
SITE_CALIBRATED  >  MANUFACTURER_CALIBRATED  >  MODELED_ESTIMATE  >  CONTROLLED_ASSUMPTION  >  NOT_AVAILABLE
```

These are NOT interchangeable. Runtime selection (`estimate_cyclotron_production`)
uses the strongest available basis for a pair; `stronger_basis(a, b)` exposes the
ordering so a future stronger evidence class can supersede a `MODELED_ESTIMATE`
without changing the downstream architecture (Section 39 of the build).

`CONTROLLED_ASSUMPTION` is reserved: no controlled production assumption is
physically approved/encoded for any pair in this build, so it is never emitted.
It exists in the vocabulary only so a future explicitly-approved assumption has a
home distinct from calibrated evidence and from a modeled estimate.

---

## C. Existing calibrated evidence (ground truth)

Where manufacturer/site calibrated production evidence already exists it is
**ground truth** and is never replaced by an estimate. Calibrated F-18 anchors
physically present in `cyclotron_equipment_catalog.json`:

| Model | Beam current | Irradiation | Normalized EOB |
|---|---|---|---|
| GE PETtrace 840 | 60 µA | 120 min | 240 000 MBq |
| GE PETtrace 860 | 100 µA | 120 min | 403 000 MBq |
| GE PETtrace 880 | 130 µA | 120 min | 524 000 MBq |
| GE PETtrace 890 | 160 µA | 120 min | 648 000 MBq |
| IBA Cyclone KEY | 100 µA | 120 min | 111 000 MBq |
| IBA Cyclone KIUBE | (not published) | 120 min | 1 406 000 MBq |

All are `manufacturer_calibrated`, F-18 only.

---

## D. Estimation methodology (physics / evidence first)

Production is estimated ONLY from physical / evidence-based quantities. It is
**never** derived from patients/day, historical usable doses/day, legacy 10%
production blocks, revenue, scanner capacity, or transport capacity.

The single defensible modeled relationship available from the physical
repository is the saturation activation form already encoded in
`cyclotron_catalog.calculate_eob_activity_from_calibrated_record`:

```
A_EOB(I, t) = K · I · (1 − exp(−λ · t)),   λ = ln(2) / half_life
```

The yield constant `K` is **not fabricated**: it is fit from that model ×
radionuclide's OWN manufacturer-calibrated anchor record `(I_cal, t_cal, A_cal)`:

```
K = A_cal / ( I_cal · (1 − exp(−λ · t_cal)) )
```

The estimate is therefore an **irradiation-time response** anchored on the pair's
own calibration, not a borrowed capacity from another model or radionuclide.

Behavior at the boundaries:

- **At the calibrated condition** (`irradiation_minutes` omitted, or equal to
  `t_cal`): the calibrated value is returned as `MANUFACTURER_CALIBRATED`
  (calibrated wins over any estimate).
- **At a different irradiation time**, when the anchor publishes a beam current
  and the radionuclide has canonical half-life physics: a `MODELED_ESTIMATE` is
  returned (`confidence = MEDIUM`).
- **When the anchor has no published beam current** (e.g. IBA KIUBE F-18): the
  calibrated value is still returned at the calibrated condition, but any
  irradiation-time estimate is honest `NOT_AVAILABLE` (K cannot be fit).
- **When no half-life physics exists** for the radionuclide (Cu-64/Zr-89/I-123/
  I-124 are absent from the canonical half-life table): irradiation-time
  modeling is `NOT_AVAILABLE`; decay physics is never fabricated.

## E. Normalization

The estimator reuses the Build 3B normalization authority
(`cyclotron_catalog._normalize_activity_to_mbq`, GBq/Ci/mCi → MBq). The canonical
activity unit is **MBq**. Raw evidence remains traceable: the result carries
`raw_evidence_reference` (source, revision, and the raw beam/time/EOB tuple) and
`limitations`; the raw catalog record itself is never mutated.

## F. Radionuclide specificity

Every estimate is specific to `(cyclotron model × radionuclide)`. The anchor is
matched on `record.radionuclide == radionuclide` only. A calibrated / estimated
F-18 result can **never** qualify C-11, N-13, O-15, Ga-68, Cu-64, Zr-89, I-123,
I-124, Tc-99m, or any other radionuclide. For a multi-radionuclide demand set,
each radionuclide is resolved independently and never collapsed into a single
`CYCLOTRON_CAPACITY` number.

## G. Physical batch / cycle estimation

`estimate_required_physical_cycles(model, radionuclide, required_eob_activity_mbq)`
consumes an **engineering** required EOB activity (never a patient cohort):

```
required_cycles = ceil( required_eob_activity_mbq / production_per_cycle_mbq )
```

This is monotonic non-decreasing in `required_eob_activity_mbq` (a larger
required EOB can never yield fewer cycles). When no numerical production basis
exists (`NOT_AVAILABLE` / `NO_COMPATIBLE_SOURCE` / `OUT_OF_CYCLOTRON_SCOPE`) it
returns `None` — never a fabricated cycle count.

> **PHYSICAL CYCLOTRON CYCLE ≠ PATIENT COHORT.**

## H. Irradiation-time response

Exposed via the optional `irradiation_minutes` argument on
`estimate_cyclotron_production`. Activity increases monotonically with
irradiation time under the saturation model and asymptotes toward `K · I`. It is
never assumed linear in time.

## I. Confidence / provenance

No canonical repository confidence vocabulary existed, so a minimal, explicitly
documented one is introduced: `HIGH` / `MEDIUM` / `LOW` / `NOT_ASSESSED`.
Calibrated results are `HIGH`; modeled irradiation-time responses are `MEDIUM`;
`NOT_AVAILABLE` / `NO_COMPATIBLE_SOURCE` / `OUT_OF_CYCLOTRON_SCOPE` are
`NOT_ASSESSED`. **Confidence never changes SUPPORTED or CALIBRATION status.**

## J. CYPRIS MP-30 + F-18 control (accepted Part 3D control preserved)

`SUMITOMO_CYPRIS_MP_30` declares support for F-18/Cu-64/Zr-89/I-123/I-124/Ga-68
but has **empty** production cycles and **empty** production performance records;
its only provenance is an `operating_character` note stating that exact
particle-energy-current values require authoritative reconciliation. There is no
beam current and no anchor. Therefore:

```
SUPPORTED            = YES
CALIBRATION_STATUS   = NOT_CALIBRATED
ESTIMATION_STATUS    = NOT_AVAILABLE
SIMULATION_BASIS     = NOT_AVAILABLE
ESTIMATED_EOB        = None
BORROWED_GE_CAPACITY = NO
```

No borrowing from GE PETtrace 890 / 648 000 MBq / any other model. An estimate is
not forced merely because a simulation would prefer one.

## K. Integration with Build 3B

The estimator **reads** Build 3B evidence (`load_cyclotron_catalog`, the
production performance records, and the normalization) and never mutates it.
Build 3B's calibrated capacity behavior and `production_calibration_status` are
unchanged (test-locked).

## L. Integration with Part 3D

A narrow, additive seam was added to the Part 3D per-radionuclide gate
(`whole_oncology_four_architecture_optimization.RadionuclideProductionGate`): a
new field `simulation_production_basis` (default `UNRESOLVED`). For a
SUPPORTED-but-NOT_CALIBRATED installed cyclotron model, the gate now records the
model's own simulation production basis via
`resolve_simulation_production_basis` (MODELED_ESTIMATE where defensible, else
NOT_AVAILABLE). **This never changes the gate `status`/`capacity_status`:**
`PRODUCTION_NOT_CALIBRATED` remains an evidence statement even when a modeled
numerical basis exists. Part 3D thus distinguishes:

```
CALIBRATED production sufficiency   (status = PRODUCTION_SUFFICIENT)
MODELED production sufficiency      (status = PRODUCTION_NOT_CALIBRATED, simulation_production_basis = MODELED_ESTIMATE)
UNRESOLVED / NOT_AVAILABLE capacity (status = PRODUCTION_NOT_CALIBRATED, simulation_production_basis = NOT_AVAILABLE)
```

Calibrated, generator, and no-compatible-source gates leave the field
`UNRESOLVED` (fully backward-compatible; all 46 Part 3D tests pass unchanged).

## M. Integration with patient-aware batch planning

The batch-planning consumer contract is engineering-only:

```
BatchProductionRequirement(radionuclide, required_eob_activity_mbq, ...)
   → CyclotronProductionEstimate(production_basis, per-cycle production, provenance)
   → estimate_required_physical_cycles(...) → required_cycles
```

Patient identity remains strictly upstream and is never passed to the estimator.

## N. Generator boundary

Generator production (Mo-99 → Tc-99m and any other generator daughter) is a
**separate authority**. Tc-99m and other generator daughters resolve to
`estimation_status = OUT_OF_CYCLOTRON_SCOPE`; the cyclotron saturation equation
is never applied to generator output. Ge-68/Ga-68 **generator** production
remains `NOT_MODELED` (OG-GEN-1) — Ga-68 appears only as a cyclotron-produced
isotope here.

## O. Simulation-use semantics

```
if   SITE_CALIBRATED         exists → use SITE_CALIBRATED
elif MANUFACTURER_CALIBRATED exists → use MANUFACTURER_CALIBRATED
elif defensible MODELED_ESTIMATE    → use MODELED_ESTIMATE (basis/qualification exposed)
elif approved CONTROLLED_ASSUMPTION → use CONTROLLED_ASSUMPTION (exposed prominently)
else                                → NOT_AVAILABLE / unresolved production basis
```

Numerical completeness never overrides evidence honesty. The correct fallback is
`NOT_AVAILABLE`, never a fabricated number. Excess estimated production is
**HEADROOM**, never new patients, procedures, or revenue.

---

## Required control table (Section 32)

Derived from the physical repository. `NOT_AVAILABLE` / `NOT_APPLICABLE` /
`NOT_CALIBRATED` are used where appropriate rather than fabricating a value.

| Catalog model | Radionuclide | Supported | Calibration status | Calibrated EOB | Modeled estimate | Simulation production basis | Provenance / status |
|---|---|---|---|---|---|---|---|
| GE PETtrace 890 | F-18 | YES | manufacturer_calibrated | 648 000 MBq @160 µA/120 min | at t≠120 min | MANUFACTURER_CALIBRATED | Calibrated ground truth (PROOF A) |
| GE PETtrace 890 | F-18 (t=60 min) | YES | manufacturer_calibrated | — | 384 637 MBq | MODELED_ESTIMATE | Irradiation-time response, K fit from own anchor |
| SUMITOMO CYPRIS MP-30 | F-18 | YES | not_calibrated | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | Supported, no anchor; no GE borrowing (PROOF B) |
| SUMITOMO CYPRIS MP-30 | Cu-64 | YES | not_calibrated | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | Additional declared CYPRIS radionuclide, no anchor / no half-life |
| SUMITOMO CYPRIS MP-30 | C-11 | NO | not_calibrated | NOT_APPLICABLE | NOT_APPLICABLE | NOT_AVAILABLE | Unsupported model × radionuclide control (PROOF D) |
| GE PETtrace 800 | Ga-68 | YES | modeled (cycles only) | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | Additional cyclotron-declared radionuclide, null-yield records |
| IBA Cyclone KEY | F-18 | YES | manufacturer_calibrated | 111 000 MBq @100 µA/120 min | at t≠120 min | MANUFACTURER_CALIBRATED | Second calibrated control |
| BEST 14p | Ga-68 | NO | not_calibrated | NOT_APPLICABLE | NOT_APPLICABLE | NOT_AVAILABLE | No compatible source control |
| (generator) Mo-99 → Tc-99m | Tc-99m | NOT_APPLICABLE (cyclotron) | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | Generator boundary — OUT_OF_CYCLOTRON_SCOPE (PROOF E) |

---

## Remaining model × radionuclide evidence gaps

After this build, the following remain unable to produce a numerical estimate
(honest `NOT_AVAILABLE`), pending future manufacturer/site evidence:

- **CYPRIS MP-30 / HM-12 / HM-20** — all declared radionuclides: no beam current,
  no anchor record.
- **GE PETtrace 800** — F-18/C-11/N-13/O-15/Ga-68: records present but all numeric
  yields null (no beam current / EOB).
- **IBA Cyclone IKON / 30XP** — research multi-isotope, empty cycles and records.
- **IBA Cyclone KIUBE** — F-18 calibrated value available at its anchor condition,
  but irradiation-time modeling `NOT_AVAILABLE` (no published beam current).
- **SIEMENS Eclipse HP / RDS-111, ACSI TR-19 / TR-24, BEST 14p** — supported
  radionuclides with literature/site energy/current only, no calibrated EOB anchor.
- **Cu-64 / Zr-89 / I-123 / I-124** on any model — absent from the canonical
  half-life table, so no decay physics for irradiation-time modeling.

These gaps are recorded in `MRT_PHARMA_OPEN_GAPS.md` (OG-CYC-1 refinement).

---

## Explicit statements

- `MODELED_ESTIMATE` ≠ `MANUFACTURER_CALIBRATED` ≠ `SITE_CALIBRATED`.
- `SUPPORTED` ≠ `CALIBRATED` ≠ `NUMERICALLY ESTIMABLE`.
- A supported radionuclide may have `CALIBRATION_STATUS = NOT_CALIBRATED` and
  `ESTIMATION_STATUS = NOT_AVAILABLE` simultaneously.
- No legacy `current_usable_doses_per_day × (1 + production_blocks × 0.10)`
  semantics are used or reintroduced. Explicit physical capacity remains
  `model × radionuclide × evidence/production basis`.
- The estimator never creates patient demand and excess production is headroom,
  not revenue.

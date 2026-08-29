# Synthetic Patient Radionuclide Source-Capability Authority (OG-SYNTH-1)

**Build:** Synthetic Patient Radionuclide Source-Capability Binding
(CURRENT UNCOMMITTED BUILD; starting SHA `c35bc4e`).
**Canonical module:** `synthetic_radionuclide_source_capability.py`
**Focused test:** `test_synthetic_patient_source_capability.py`
**Governance:** advances `OG-SYNTH-1` to **PARTIAL** — the selected-source
representative binding is implemented and test-locked, but the default/legacy
synthetic path (no selected-source ids) remains benchmark-driven, so the gap is
not globally closed.

---

## Purpose

Normal synthetic patient radionuclide demand must be constrained — *before any
patient is created* — by the radionuclides the scenario's **selected** production
sources can actually supply. Previously the representative synthetic generator
assigned radionuclides purely by modality (PET → `F-18`, SPECT → `Tc-99m`) with
no reference to selected equipment; a capability mismatch surfaced only
downstream at the feasibility stage.

This build supplies the first three links of the required normal-simulation
chain:

```
SELECTED PRODUCTION SOURCES
  -> SOURCE-SUPPORTED RADIONUCLIDE SET          (this authority)
  -> ADMISSIBLE SYNTHETIC RADIONUCLIDE SET      (this authority)
  -> SYNTHETIC PATIENT RADIONUCLIDE REQUIREMENTS (generator seam)
  -> PATIENT-AWARE BATCH-PRODUCTION PLANNING     (unchanged downstream)
  -> PHYSICAL PRODUCTION REQUIREMENT             (unchanged downstream)
  -> CYCLOTRON / GENERATOR AUTHORITY             (unchanged downstream)
```

## Authority boundary

- Does **not** redesign the cyclotron estimator, generator physics, or any batch
  planner.
- Does **not** make cyclotrons or generators patient-identity-aware. No
  `patient_id` / name / room / appointment / calendar identity is passed into a
  catalog capability API here. The cyclotron and generator feasibility APIs take
  `patients_requested` (a count), never a patient identity.
- Answers only: *can this SELECTED physical source produce this radionuclide in
  principle (SUPPORT semantics), and is that radionuclide clinically recognized
  for the requested modality.* Quantitative production sufficiency is a separate
  downstream concern and is deliberately not consulted.

## Selected-source semantics

Admissible radionuclides are derived only from the production sources
**selected / installed in the current scenario** (the caller-supplied
`selected_cyclotron_ids` / `selected_generator_ids`), never from every machine in
the global catalog. A radionuclide supported by an unselected catalog machine
never becomes admissible. `catalog.by_id(...)` raises on an unknown id — an
unknown selection is never silently ignored.

## Normal mode

`resolve_admissible_radionuclides(*, modality, selected_cyclotron_ids,
selected_generator_ids, mode="NORMAL")` returns a
`SyntheticRadionuclideCapabilityResult`:

```
ADMISSIBLE = ( CYCLOTRON supported_radionuclides  UNION  GENERATOR daughter_radionuclide )
             filtered by CLINICAL MODALITY recognition
```

`build_representative_day_population` (and its stochastic wrapper) consume the
admissible set via `choose_normal_synthetic_radionuclide` when selected-source ids
are supplied, **before** creating patient demand. The normal generator therefore
never emits demand for a radionuclide no selected source supports. If a requested
cohort (PET or SPECT count > 0) has no admissible radionuclide, a
`NoCompatibleSourceError` is raised — never a fallback, never a substitution.

The NORMAL-mode radionuclide choice is the first admissible radionuclide in the
stable resolved order (build governor Sec 13: no canonical clinical weighting
authority exists, so the narrowest deterministic policy is used). For the
representative benchmark (one clinically-recognized radionuclide per modality)
this is exactly F-18 / Tc-99m.

## Stress-test mode

A `STRESS_TEST` mode is carried on the result contract. STRESS_TEST callers may
deliberately request a radionuclide unsupported by the selected sources; the
resolver preserves the request and reports `NO_COMPATIBLE_SOURCE` (no
substitution). This is essential for a future Part 3E optimizer, which must be
able to discover that additional/different production equipment is required.

## Explicit-demand behavior

The explicit-demand paths remain authoritative and are never source-rewritten:
`patient_radionuclide_demand.PatientRadionuclideDemand` (validated only against
the canonical half-life table) and
`inbound_patient_program.generate_synthetic_patient_population` (stamps the
caller-supplied radionuclide verbatim). Equipment capability must never silently
mutate an existing patient demand's radionuclide, modality, count, or activity.
Capability filtering belongs **before** normal synthetic demand creation; after
demand exists, incompatibility is a downstream feasibility result.

## Cyclotron support vs quantitative sufficiency

Admissibility uses SUPPORT semantics only — a radionuclide is admissible when a
selected source's `supported_radionuclides` (cyclotron) or `daughter_radionuclide`
(generator) includes it, **even when** production output is `NOT_CALIBRATED` or
the numerical estimate is `NOT_AVAILABLE`. Example: `SUMITOMO_CYPRIS_MP_30` + F-18
is `SUPPORTED = YES`, `CALIBRATION_STATUS = NOT_CALIBRATED`,
`ESTIMATION_STATUS = NOT_AVAILABLE`; F-18 remains admissible and downstream
feasibility reports the unresolved capacity. No GE PETtrace capacity is borrowed.

## Generator boundary

Generator-produced radionuclides come from the generator catalog's
`daughter_radionuclide` (Mo-99 → Tc-99m). Tc-99m is never resolved through the
cyclotron resolver, and cyclotron production equations are never applied to
generator output. SPECT synthetic demand with only a cyclotron selected returns
`NO_COMPATIBLE_SOURCE`.

## Modality filtering

The repository's modality vocabulary is `Literal["PET", "SPECT"]`
(`clinical_resource_identity.ScannerModality`,
`nuclear_appointment.NuclearModality`,
`long_horizon_operational_planning.ClinicalModality`). The repository clinically
recognizes exactly two radionuclide → modality bindings today: `F-18 → PET`
(cyclotron) and `Tc-99m → SPECT` (generator daughter). Other cyclotron-*supported*
radionuclides (C-11, N-13, O-15, Ga-68, Cu-64, Zr-89, I-123, I-124) have no
clinical modality classification anywhere in the repository; this authority
reports them as `SUPPORTED_BUT_NOT_CLINICALLY_MODALITY_CLASSIFIED` limitations and
does **not** invent a classification for them (build governor Sec 8/30). A
radionuclide recognized for the *other* modality is excluded with reason
`CLINICALLY_RECOGNIZED_FOR_{other}_NOT_{modality}` (e.g. Tc-99m is not a PET
radionuclide).

## Multi-source behavior

- **Multiple cyclotrons:** each resolved independently; the union admits a
  radionuclide if at least one selected cyclotron supports it. All compatible
  selected source ids are preserved for that radionuclide (no fictional averaged
  machine).
- **Multiple generators:** individual identities preserved; duplicate support for
  the same daughter (e.g. three Tc-99m generators) yields **one** admissible
  radionuclide identity with three compatible source ids (no duplicate choices).
- **Mixed cyclotron + generator:** PET and SPECT admissibility are resolved
  independently from their appropriate source types; modalities never cross.

## Patient-aware batch-planning boundary

After radionuclide assignment, individual synthetic patient requirements continue
into the existing patient-aware batch-production authority
(`patient_radionuclide_demand.partition_facility_day_patient_demand`), which
carries patient identity while aggregating radionuclide / activity / count into
the physical production requirement. Patient identity is **not** passed into the
cyclotron estimator merely because the batch planner is patient-aware. Patient
cohort ≠ physical production batch.

## Representative benchmark compatibility

When both selected-source lists are left `None` (the default), the module-level
benchmark constants (`F-18` / `Tc-99m`) are used unchanged; patient census,
modality counts, timing, and identities are byte-identical to before this build.
When a compatible selected set is supplied, the same F-18 / Tc-99m assignment
results — but now **explicitly justified** by selected-source capability rather
than accidentally preserved by hardcoded constants. Verified: identical census,
identical patient identities, identical radionuclides.

## No-source behavior

With no selected cyclotron and no selected generator, normal synthetic PET/SPECT
radionuclide assignment returns `status = NO_COMPATIBLE_SOURCE` with a typed
explanation (modality, selected sources, why nothing was admissible). No F-18 /
Tc-99m fallback; no global-catalog borrowing.

## No demand from capacity or economics

The resolver has no capacity or economics inputs. More cyclotron/generator
capacity, more calibrated production, or `MODELED_ESTIMATE` availability never
increases synthetic patient count or weights radionuclide selection. Preserved:
`DEMAND → CAPACITY REQUIREMENT`, never `CAPACITY → DEMAND`.

## OG-SYNTH-1 status

**PARTIAL** (advanced from `PLANNED / PARTIAL`; NOT globally CLOSED). What is
implemented and test-locked:

- selected-source capability resolver = **IMPLEMENTED**;
- selected-source-constrained representative NORMAL path = **IMPLEMENTED**
  (when `selected_cyclotron_ids` / `selected_generator_ids` are supplied, NORMAL
  synthetic radionuclide assignment consumes the selected-source admissible set
  and no longer generates unsupported radionuclides);
- no-source explicit failure (`NO_COMPATIBLE_SOURCE`) = **IMPLEMENTED**;
- STRESS_TEST / explicit-demand preservation = **IMPLEMENTED**.

Why it is **not** globally CLOSED: the constraint is **opt-in**. The
default/legacy synthetic path — a caller supplying neither
`selected_cyclotron_ids` nor `selected_generator_ids` — remains
benchmark-driven (`PET → F-18`, `SPECT → Tc-99m`) and is **not** source-capability
constrained. That backward-compatible default is preserved deliberately; making
selected-source ids mandatory at every synthetic entry point is deferred work.

## Limitations (remaining, honestly disclosed)

- The constraint is **opt-in**: callers passing no selected-source ids retain the
  representative benchmark defaults for backward compatibility. A future build
  could make selected-source ids mandatory for every synthetic entry point.
- Only F-18 (PET) and Tc-99m (SPECT) are clinically modality-classified today;
  other cyclotron-supported radionuclides are reported, never promoted.
- The explicit inbound path (`generate_synthetic_patient_population`) is
  explicit-demand by design and is not source-constrained.

## Future Operations / calendar reuse

The resolver is a small, independently-testable authority that the future
Operations / Hospital Master Calendar layer (six-month horizon) can reuse to
constrain forecast/synthetic radionuclide demand from the same selected-source
capability set. This build does **not** implement the calendar and does not touch
ARIA integration.

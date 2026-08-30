# Existing Facility / AS-IS Digital Twin — Phase 1F: Baseline Validation Authority

**Starting HEAD:** `09a95bd` · **branch:** `main` · **origin/main:** `09a95bd` · **divergence:** 0 / 0
**Deliverables:** `existing_facility_baseline_validation.py`, `test_asis_twin_phase1f.py`, this document.
**Boundary:** no LOCKDOWN, no What-If, no auto-calibration, no new simulation engine, no commit/push.

---

## 1. Purpose and boundary

Phase 1F answers one governing question: **"How well does the Phase 1E simulated
baseline reproduce the real existing hospital?"** A baseline becomes *validated*
only to the extent that actual facility evidence supports the simulated behavior.
Missing validation evidence stays missing — the authority never manufactures
agreement.

The central principle is **SIMULATION EXECUTION ≠ VALIDATION.** A baseline that
merely executed is `VALIDATION_INSUFFICIENT` until observed evidence supports it.

Phase 1F is validation evidence + comparison + coverage + qualification +
LOCKDOWN-eligibility assessment. It is **not** a second simulation engine, **not**
a second identity authority, **not** a model-tuning authority, **not** a LOCKDOWN
authority, and **not** What-If. It never creates LOCKDOWN and never creates
What-If.

## 2. Physical validation-seam trace (ASIS_BASELINE_VALIDATION_INPUT_TRACE)

| Item | Physical authority | Classification |
|---|---|---|
| A. Phase 1E baseline candidate | `AsIsBaselineSimulationCandidate` | REUSE |
| B. Phase 1E simulation result | `AsIsBaselineSimulationResult` | REUSE (read-only) |
| C. Patient trajectory/event output | `AsIsBaselineSimulationOutputs.patient_trajectories: tuple[HybridPatientTrace]` | REUSE |
| D. Phase 1D operational observations | `AsIsOperationalStateSnapshot` | REUSE |
| E. Actual-vs-planned structures | `OperationalEvidence`, `OperationalEvidenceConflict` | REUSE (provenance + conflict doctrine) |
| F. Patient identity | `OncologyPatientRecord.patient_id` / `HybridPatientTrace.canonical_patient_id` | REUSE |
| G. Scanner/resource identity | `AsIsScannerOperationalState.scanner_id`, trace resource ids | REUSE |
| H. Room/spatial identity | `AsIsRoomOperationalState.spatial_object_id`, `destination_room_id` | REUSE |
| I. Production/batch identity | `AsIsProductionBatchOperationalState`, `RadionuclideProductionGate` | REUSE |
| J. Timing/event identity | `HybridPatientTrace` minute fields, `OperationalTemporalBasis` | REUSE |
| K. Validation/tolerance concepts | *none exist in repo* | **GENUINE_GAP** |
| L. Evidence/provenance/confidence vocab | `AsIsProvenance`/`AsIsCalibration`/`AsIsConfidence` | REUSE |
| M. LOCKDOWN eligibility / lineage authority | `lockdown_what_if_lineage_authority.py` | VIEW (never call mutators) |
| N. Existing validation functionality | Phase 1E `VALIDATION_REQUIRED` placeholder only | **GENUINE_GAP** |

Everything classified REUSE/VIEW is consumed read-only. The two GENUINE_GAP items
(a tolerance/validation vocabulary and the comparison engine itself) are what
Phase 1F builds.

## 3. Phase 1E candidate input

Phase 1F consumes the exact Phase 1E `AsIsBaselineSimulationResult` (and its
embedded `AsIsBaselineSimulationCandidate`). It never reruns Phase 1E to obtain a
validation result, and never silently reconstructs a different baseline. The
result preserves `facility_id`, `operational_snapshot_id`, `execution_status`,
`simulation_scope`, `qualified_uncertainties`, `unresolved_gaps`, and the
simulated `outputs`. The validation result records which candidate it validated
via `validation_result_id`, `facility_id`, `operational_snapshot_id`,
`baseline_candidate_execution_status`, `simulation_scope` and `validation_scope`.

## 4. Validation-evidence contract

`AsIsBaselineValidationEvidence` carries one explicit **observed** fact plus its
provenance. It never stores a simulated value (Section 5). Sources:
`PROJECT_SUPPLIED`, `FACILITY_DERIVED`, `MEASURED`, `IMPORTED`,
`OBSERVED_OPERATIONAL_RECORD`, `CONTROLLED_VALIDATION_INPUT`. There is
deliberately **no** `SIMULATION_OUTPUT` source — a simulated value can never be
observed validation evidence.

## 5. Observed vs simulated separation

Each `AsIsValidationComparison` preserves **both** `observed_value` and
`simulated_value`; one never overwrites the other. When a value is unavailable it
is `None` and the status records exactly why. The simulated counterpart is looked
up read-only from the Phase 1E outputs at comparison time.

## 6. Validation dimensions

`ValidationDimension` covers PATIENT_THROUGHPUT, PATIENT_TIMING, TRANSPORT_TIMING,
SCANNER_UTILIZATION, ROOM_UTILIZATION, QUEUE_WAIT_TIME, PRODUCTION_TIMING,
INJECTION_TIMING, UPTAKE_TIMING, SCAN_TIMING, STAFF_UTILIZATION,
RESOURCE_UTILIZATION, ROUTE_USAGE, RADIONUCLIDE_ACTIVITY, PATIENT_TRAJECTORY,
OPERATIONAL_FEASIBILITY. A dimension the existing engine does not expose resolves
to `MISSING_SIMULATED_EVIDENCE`, never a fabricated value.

## 7. Required-dimension manifest

`AsIsRequiredValidationDimension` declares requiredness (physically justified),
never inferred from the presence of data. Default nuclear-medicine manifest:

| Dimension | Required | Blocking for LOCKDOWN |
|---|---|---|
| PATIENT_THROUGHPUT | yes | yes |
| OPERATIONAL_FEASIBILITY | yes | yes |
| SCANNER_UTILIZATION | yes | yes |
| PATIENT_TIMING | no | no |
| RADIONUCLIDE_ACTIVITY | no | no |
| PATIENT_TRAJECTORY | no | no |

## 8. Validation coverage

`AsIsValidationCoverage` reports required / with-observed / with-simulated /
comparable / passed / failed / unresolved / not-applicable dimensions.
`coverage_ratio` is the fraction of applicable required dimensions that passed, or
`None` when the denominator is 0 (never a fabricated 1.0). Missing and unresolved
dimensions count as unresolved, **never** as passing.

## 9. Comparison-status vocabulary

`NOT_EVALUATED`, `NOT_COMPARABLE`, `MISSING_OBSERVED_EVIDENCE`,
`MISSING_SIMULATED_EVIDENCE`, `WITHIN_TOLERANCE`, `OUTSIDE_TOLERANCE`,
`TOLERANCE_NOT_MODELED`, `MATCH`, `MISMATCH`, `CONFLICTED_EVIDENCE`,
`QUALIFIED_UNCERTAINTY`, `NOT_APPLICABLE`. Results are never collapsed to
PASS/FAIL. Only `WITHIN_TOLERANCE` and `MATCH` count as passing.

## 10. Tolerance authority

`AsIsValidationTolerance` is **explicitly supplied**, with a provenance
(`PROJECT_SUPPLIED`, `FACILITY_SUPPLIED`, `REPOSITORY_AUTHORITY`,
`CONTROLLED_VALIDATION_EXPERIMENT`). There is **no** universal/default tolerance.
A numeric dimension with no supplied tolerance yields `TOLERANCE_NOT_MODELED` (the
difference is reported, but never a pass/fail). This is a hard anti-fabrication
rule.

## 11. Exact-identity comparisons

Identity dimensions (`PATIENT_TRAJECTORY`, `ROUTE_USAGE`, `OPERATIONAL_FEASIBILITY`)
use exact comparison (`MATCH`/`MISMATCH`); numeric tolerance semantics are never
forced onto them.

## 12. Patient throughput validation

Observed patient count is compared against the simulated
`retention_qualified_completed`. Difference is `simulated − observed`.

## 13. Patient timing validation

Where an observed per-stage timestamp exists AND the object identity resolves to a
simulated trajectory, the corresponding simulated stage minute is compared
(injection/uptake/scan). Missing observed timestamps stay missing.

## 14. Patient trajectory validation

Compares the observed movement endpoint (`destination_room_id`) against the
simulated trajectory identity; transport mode survives (Section 15). Trajectory
validation is not required when no observed movement evidence exists.

## 15. Transport timing validation

Transport mode identity survives every comparison. A manual observed mode is never
equated to an MRT simulated mode; a mode mismatch is a `MISMATCH` +
`IDENTITY_MISMATCH` gap.

## 16. Scanner utilization validation

Compares observed scanner peak occupancy against the simulated
`scanner_peak_occupancy`, preserving scanner identity.

## 17. Room utilization validation

Room identity is preserved. The existing engine does not expose per-room
utilization, so this dimension resolves to `MISSING_SIMULATED_EVIDENCE` rather
than aggregating distinct rooms.

## 18. Queue / wait validation

`QUEUE_WAIT_TIME` is not exposed by the existing engine →
`MISSING_SIMULATED_EVIDENCE` (never a fabricated queue metric).

## 19. Production validation

Production is compared per radionuclide using the same radionuclide/source
identity. F-18 evidence never validates another radionuclide (Section 20).

## 20. Radionuclide activity validation

Activity comparison routes through the **one** decay authority
(`multi_isotope_decay.retained_fraction`); the activity reference time is
preserved. No second decay equation is introduced. Cross-radionuclide comparison
is blocked (`NOT_COMPARABLE` + `RADIONUCLIDE_MISMATCH`); decay conversion is never
used to equate two radionuclides.

## 21. Staff / resource validation

Canonical staff/resource identity is preserved where supplied. Benchmark staffing
is never used as validation evidence; unexposed metrics resolve to
`MISSING_SIMULATED_EVIDENCE`.

## 22. Evidence conflicts

Two observed sources disagreeing on one dimension+identity produce an
`AsIsValidationEvidenceConflict` with **both** candidates preserved,
`resolution_status="UNRESOLVED"`. The dimension becomes `CONFLICTED_EVIDENCE` and,
if required, blocks LOCKDOWN eligibility. Conflicts are never auto-resolved.

## 23. Provenance

Every observation preserves source, source_record_id, calibration
(`MEASURED`/`IMPORTED`/`INFERRED`/`CONTROLLED_ASSUMPTION`/`NOT_APPLICABLE`),
confidence and (optionally) an observation window. The measured / imported /
inferred / controlled-assumption / simulation-output distinctions are preserved.

## 24. Scope-specific validation

`simulation_scope` and `validation_scope` are both retained. A narrow
nuclear-medicine validation never declares the whole hospital validated; a
`WHOLE_HOSPITAL` scope is not modeled by the engine and cannot reach VALIDATED.

## 25. Validation gaps

`AsIsValidationGap` kinds: `MISSING_OBSERVED_EVIDENCE`,
`MISSING_SIMULATED_EVIDENCE`, `TOLERANCE_NOT_MODELED`, `CONFLICTED_OBSERVED_STATE`,
`INCOMPATIBLE_OBSERVATION_WINDOW`, `IDENTITY_MISMATCH`, `RADIONUCLIDE_MISMATCH`,
`NOT_APPLICABLE_DIMENSION`. Missing evidence is a first-class gap, never hidden in
a note.

## 26. Baseline validation status

`AsIsBaselineValidationVerdict`: `NOT_VALIDATED`, `VALIDATION_INSUFFICIENT`,
`PARTIALLY_VALIDATED`, `VALIDATED_WITH_QUALIFICATIONS`, `VALIDATED`. Deterministic
rule:

- baseline did not execute → `NOT_VALIDATED`;
- no comparisons → `VALIDATION_INSUFFICIENT`;
- any required dimension failed/conflicted → `VALIDATION_INSUFFICIENT`;
- all required passed + baseline qualified-uncertainty or an evaluated-nonpassing
  optional dimension → `VALIDATED_WITH_QUALIFICATIONS`;
- all required passed with none of the above → `VALIDATED`;
- some required passed, some required unresolved (missing evidence) →
  `PARTIALLY_VALIDATED`.

`VALIDATED` is never chosen automatically.

## 27. LOCKDOWN eligibility

`AsIsLockdownEligibilityVerdict`: `NOT_ELIGIBLE`, `VALIDATION_INSUFFICIENT`,
`ELIGIBLE_WITH_QUALIFICATIONS`, `ELIGIBLE`. Eligibility is calculated, never acted
on; Phase 1F never touches `LockdownLineageRegistry`.

| Validation status | Eligibility (no blocking gap) |
|---|---|
| VALIDATED | ELIGIBLE |
| VALIDATED_WITH_QUALIFICATIONS | ELIGIBLE_WITH_QUALIFICATIONS |
| PARTIALLY_VALIDATED | VALIDATION_INSUFFICIENT |
| VALIDATION_INSUFFICIENT | VALIDATION_INSUFFICIENT |
| NOT_VALIDATED | NOT_ELIGIBLE |

Any blocking gap (required-dimension conflict, missing required evidence, failure)
defeats eligibility. Eligibility is never equivalent to "simulation executed".

## 28. Controls A–M

| Control | Scenario | Result |
|---|---|---|
| A | No validation evidence | `VALIDATION_INSUFFICIENT`, `NOT ELIGIBLE`, coverage 0.0, no LOCKDOWN |
| B | Partial evidence | missing required dims stay missing; not eligible |
| C | Within-tolerance | `WITHIN_TOLERANCE`, provenance preserved |
| D | Outside-tolerance | `OUTSIDE_TOLERANCE`, failure preserved, no auto-tuning, not eligible |
| E | No tolerance | `TOLERANCE_NOT_MODELED`, difference reported, no fabricated pass/fail |
| F | Conflicting observations | both preserved, `CONFLICTED_EVIDENCE`, not eligible |
| G | Incompatible windows | `NOT_COMPARABLE` + `INCOMPATIBLE_OBSERVATION_WINDOW`, no rescale |
| H | Missing simulated metric | observed survives, `MISSING_SIMULATED_EVIDENCE`, no fabrication |
| I | Missing observed metric | simulated survives, `MISSING_OBSERVED_EVIDENCE` |
| J | Identity mismatch | no silent pooling, `MISSING_SIMULATED_EVIDENCE` |
| K | Radionuclide mismatch | `NOT_COMPARABLE` + `RADIONUCLIDE_MISMATCH`, no decay conversion |
| L | Qualified validation | `VALIDATED_WITH_QUALIFICATIONS` / `ELIGIBLE_WITH_QUALIFICATIONS`, no LOCKDOWN |
| M | Fully validated control | `VALIDATED` / `ELIGIBLE`, `LOCKDOWN_CREATED=NO`, `WHAT_IF_CREATED=NO` |

All 52 Phase 1F invariants pass (`test_asis_twin_phase1f.py`).

## 29. Unresolved limitations

- The existing engine exposes no per-room utilization, no queue/wait metric, no
  simulated administered-activity metric, and no staff-utilization metric; those
  dimensions honestly resolve to `MISSING_SIMULATED_EVIDENCE`.
- Radionuclide-activity validation confirms the observed value is decay-normalized
  through the one authority, but the simulated administered-activity counterpart
  is not exposed, so the dimension remains `MISSING_SIMULATED_EVIDENCE`.
- Whole-hospital validation is out of the modeled nuclear-medicine scope.

## 30. Next-step boundary

Phase 1F STOPS at LOCKDOWN eligibility. It does **not** create LOCKDOWN, does not
create or execute What-If, does not begin Phase 1G, and does not begin automatic
model calibration. Any future calibration/tuning authority must be a separate
explicit build.

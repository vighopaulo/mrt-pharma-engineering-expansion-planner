# Physical Feasibility Authority — Part 3D (Unified Physical Feasibility Closure)

Starting authority: branch `main`, HEAD `95040d5` (Build 3C.1 complete), working
tree clean, divergence 0/0. Builds 3A, 3B, 3C and 3C.1 are complete and are
**reused, not reopened**. This part connects the already-built physical gates
(production / transport / injection / uptake / scanner) into the one place the
four-architecture engine actually reports feasibility — `ArchitectureResult.feasible`
— replacing a hardcoded `feasible=True`.

Deliverables: this document + one focused test file
(`test_part3d_physical_feasibility_closure.py`). No commit, no push, no
composition optimizer, no UI. `equal_budget.py` is untouched;
`hybrid_optimization.py` decay math is untouched.

---

## A. Problem statement

Before Part 3D, every `ArchitectureResult` produced by the four canonical
architecture evaluators set `feasible=True` unconditionally. The engine had
fully-built physical authorities (Build 3B production, Build 3C/3C.1 transport,
and a clinical-resource peak-occupancy computation) but none of them fed the
reported feasibility flag. The clinical occupancy computation
(`compute_clinical_resource_peak_occupancy`) was orphaned — referenced only by
tests. Part 3D closes that gap so feasibility is **derived** from the physical
gates.

## B. Scope and non-goals

In scope: derive `feasible` from a shared physical-feasibility contract; add a
clinical-resource input authority (project-supplied vs the 6/6/12 controlled
benchmark); bind radioactive route-time to decay without double-counting
(document + test-lock, no new decay code). Out of scope: composition optimizer,
UI, any change to `equal_budget.py`, any change to the `hybrid_optimization.py`
decay math.

## C. Authorities reused (no new engines)

- **Build 3A** — target-bounded / NO_BUILD nuclear floor envelopes
  (`resolve_nuclear_floor_envelopes`) and the hybrid zone candidate evaluation.
- **Build 3B** — per-radionuclide production authority: cyclotron catalog,
  generator catalog, and `resolve_fleet_eob_capacity_mbq_per_day` for
  schedule-derived EOB capacity.
- **Build 3C** — mode-specific transport resource authorities (conventional
  transporter search; MRT carrier search) with their stop-reason diagnostics.
- **Build 3C.1** — two-route-family spatial route authority (preserved; the
  transport gate consumes 3C/3C.1 search diagnostics rather than re-deriving
  routes).
- **Clinical occupancy** — `compute_clinical_resource_peak_occupancy`, the
  previously-orphaned sweep-line peak-occupancy computation over patient traces,
  now connected as the scanner/injection/uptake gate.

## D. The common physical-feasibility contract

`derive_physical_feasibility(nuclear, baseline, *, architecture="",
clinical_resources=None, installed_cyclotron_model_ids=()) ->
PhysicalFeasibilityResult` is the single contract every canonical architecture
consumes. It takes **no** universal transport scalar — transport is derived
mode-by-mode (Section H). It aggregates:

1. the clinical occupancy gate (scanner / injection / uptake) from
   `compute_clinical_resource_peak_occupancy`;
2. the per-radionuclide production gate (`_resolve_production_gate`);
3. the mode-specific transport gate (`_resolve_transport_gate`).

It returns a typed `PhysicalFeasibilityResult` carrying the overall status,
qualification, the binding constraint, each gate's availability/peak/feasibility,
production capacity figures, the per-radionuclide production breakdown, and the
list of unqualified constraints.

## E. Clinical-resource input authority (project-supplied vs 6/6/12 benchmark)

`ClinicalResourceInputs(scanners, injection_resources, uptake_resources,
resource_source)` is the input authority for clinical room counts.
`resource_source` is one of `PROJECT_SUPPLIED`, `FACILITY_DERIVED`, or
`CONTROLLED_BENCHMARK`. The controlled benchmark is `BENCHMARK_CLINICAL_RESOURCES`
= `(6, 6, 12, CONTROLLED_BENCHMARK)` (`BENCHMARK_SCANNERS=6`,
`BENCHMARK_INJECTION_RESOURCES=6`, `BENCHMARK_UPTAKE_RESOURCES=12`).

Counts flow into the model through `_nuclear_result(..., clinical_resources=...)`,
which threads them onto the `HybridZoneCandidate`. The resource_source label
flows through `derive_physical_feasibility(..., clinical_resources=...)`. To make
both the availability counts **and** the source label consistent, the same
`ClinicalResourceInputs` must be supplied to both calls (the default on both is
the controlled benchmark, preserving backward compatibility).

## F. Scanner / injection / uptake gates

Each clinical gate compares the demand-driven peak occupancy against the
available count. Peak occupancy is computed by the existing sweep-line over
patient-trace intervals — patient demand bounds throughput. Adding capacity
beyond the peak is genuine headroom: it does not increase the patient count or
the peak occupancy. When a peak exceeds availability the gate is infeasible and
becomes a binding-constraint candidate.

## G. Production gate (Build 3B, per-radionuclide)

`_resolve_radionuclide_production_gate(radionuclide, fleet, required_eob, *,
installed_cyclotron_model_ids=())` resolves ONE radionuclide against its own
compatible source, in order:

1. **Calibrated/schedulable cyclotron fleet** supporting the radionuclide →
   `resolve_fleet_eob_capacity_mbq_per_day` (never borrows another isotope's
   record). Yields `PRODUCTION_SUFFICIENT` / `PRODUCTION_INSUFFICIENT` /
   (if uncalibrated) `PRODUCTION_NOT_CALIBRATED`.
   **Installed-selection binding (Part 3D correction):** when the caller passes
   a non-empty `installed_cyclotron_model_ids`, that declared equipment is the
   authoritative selection. Path 1 is then scoped to fleet assets whose model
   corresponds to the selection — a leftover benchmark asset (e.g. GE PETtrace
   890 F-18) can no longer silently *shadow* a real installed selection (e.g. an
   installed CYPRIS MP-30) and borrow its calibrated capacity. With no explicit
   selection, every benchmark fleet asset stays in scope (default path
   unchanged).
2. **Installed-model seam** — a selected installed cyclotron model that
   *declares* the radionuclide as supported but forms no schedulable/calibrated
   fleet → `PRODUCTION_NOT_CALIBRATED` carrying the real model identity,
   fabricating no EOB figure. The exact control: installing `SUMITOMO_CYPRIS_MP_30`
   and requiring **F-18** resolves `RADIONUCLIDE_SUPPORTED=YES`,
   `PRODUCTION_NOT_CALIBRATED`, `source_identity="CYPRIS MP-30"`,
   `installed_eob_capacity=None` — and never the GE PETtrace 890 F-18 capacity
   (648000 MBq/day). The same holds for the MP-30's other declared isotopes
   (Cu-64, Zr-89, I-123).
3. **Generator daughter match** (for example Tc-99m from a Mo-99/Tc-99m
   generator) → distinct `GENERATOR` source; generator supply is
   `PRODUCTION_NOT_CALIBRATED` in the catalog.
4. Otherwise `NO_COMPATIBLE_SOURCE`, reported explicitly.

`_resolve_production_gate` aggregates per radionuclide: any `INSUFFICIENT` or
`NO_COMPATIBLE_SOURCE` → insufficient (a genuine physical failure); else any
`NOT_CALIBRATED` → not calibrated; else sufficient. The per-radionuclide
breakdown is preserved on the result — never collapsed into a single verdict.

## H. Transport gate (Build 3C / 3C.1 mode-specific, no universal scalar)

`_resolve_transport_gate(nuclear, *, architecture="")` derives transport
feasibility from the architecture's ACTUAL assigned transport searches — the
Build 3C conventional transporter search (mapped to the `MANUAL` shielded-porter
mode, since nuclear is ELIGIBLE on MANUAL and INELIGIBLE on RGHT / ordinary PTS)
and the MRT carrier search — never a single universal `transport_available`
scalar. There is no scalar transport parameter on `derive_physical_feasibility`
at all; the transport gate is entirely mode-derived.

Each mode is mapped by `_transport_mode_gate_from_search` onto a typed
`TransportModeGate(mode, status, required_resources, available_resources,
sizing_stop_reason, note)` — preserving the mode's INDIVIDUAL identity so the
aggregate verdict is explainable. Status vocabulary:
`TRANSPORT_SUFFICIENT` / `TRANSPORT_INSUFFICIENT` / `TRANSPORT_NOT_CALIBRATED` /
`TRANSPORT_NOT_APPLICABLE`. Stop-reason mapping:

- `DEMAND_SATURATED` / `NO_QUALIFIED_THROUGHPUT_GAIN` → `TRANSPORT_SUFFICIENT`
  (`required_resources == available_resources`, the minimum-feasible fleet);
- `NO_WORKLOAD` (or no diagnostic) → `TRANSPORT_NOT_APPLICABLE`
  (`required=available=None`) — a mode carrying no assigned nuclear workload is
  never a failure (no-workload semantics);
- `PHYSICAL_LIMIT` / `SEARCH_BOUND_REACHED` → `TRANSPORT_INSUFFICIENT` (a
  calibrated failure);
- any undocumented stop reason → `TRANSPORT_NOT_CALIBRATED` (never a silent
  SUFFICIENT, never an automatic INFEASIBLE).

Aggregation over the REQUIRED (non-NOT_APPLICABLE) modes only:

- any required mode INSUFFICIENT → `TRANSPORT_INSUFFICIENT` (feasible=False);
- else if no required mode has an applicable gate → `TRANSPORT_NOT_EVALUATED`
  (reserved strictly for the genuine no-applicable-gate case, never a shortcut);
- else if every required mode is NOT_CALIBRATED → `TRANSPORT_QUALIFIED_WITH_LIMITATIONS`
  (feasible=True, mode names added to unqualified constraints);
- else → `TRANSPORT_SUFFICIENT`.

The per-mode `TransportModeGate`s are propagated onto both
`PhysicalFeasibilityResult` and `ArchitectureResult.transport_mode_gates` so the
verdict is never a single collapsed scalar.

Observed nuclear-clinical transport mapping (test-locked):

- **MANUAL_CONVENTIONAL** — MANUAL required and SUFFICIENT (req == avail); MRT
  NOT_APPLICABLE (no MRT nuclear workload).
- **MRT_DOMINANT** — MRT required and SUFFICIENT (req == avail); MANUAL
  NOT_APPLICABLE (no conventional nuclear workload).
- **HYBRID_MRT** — both MANUAL and MRT can be required (composite).
- **AUTOMATED_CONVENTIONAL** — the nuclear leg falls back to MANUAL/conventional,
  so the MANUAL mode gate is the nuclear-clinical transport gate (see Section
  Z.2 for the honest boundary on other automated logistics).

## I. Deriving overall feasibility, qualification and the binding constraint

Calibrated gate failures (scanner / injection / uptake / transport-insufficient /
production-insufficient / production-no-compatible-source) make the architecture
`INFEASIBLE`; the binding constraint is the first such failure in gate order.
Otherwise, if the only outstanding issue is a merely NOT_CALIBRATED production
capacity, the status is `FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY`,
qualification `QUALIFIED_WITH_LIMITATIONS`, binding `none` — the uncalibrated
production is named per radionuclide in `unqualified_physical_constraints` and is
never the binding constraint. With no failures and no unqualified constraints the
status is `FEASIBLE` / `QUALIFIED`. The derived `feasible` flag is simply
`physical_feasibility_status != "INFEASIBLE"`.

## J. NOT_CALIBRATED is honest, never zeroed, never auto-infeasible

A NOT_CALIBRATED production capacity is reported with `installed_eob = None`
(not fabricated to zero) and does not by itself make an architecture infeasible.
This preserves the Build 3B honesty rule: the benchmark genuinely runs F-18 on a
calibrated cyclotron fleet while Tc-99m is generator-supplied and uncalibrated on
that fleet, so the benchmark's overall status is
`FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY`.

## K. Radioactive route-time bound to decay — exactly once

Two independent lineages exist and neither double-counts route-time:

- **Lineage A (hybrid clinical schedule):** transport arrival is baked into the
  batch release time, and the joint scheduler runs with `transport_minutes=0.0`,
  so the single decay interval runs from production release to injection start.
  Empirically, per patient trace `transport_arrival_time_minutes ==
  injection_start_minutes`: the route-time is inside that one interval, applied
  once.
- **Lineage B (cycle-relative production requirement):** administration offsets
  are transport-agnostic and are not fed into the hybrid injection-start path.

Part 3D changes **no decay mathematics** (`multi_isotope_decay.py` and
`hybrid_optimization.py` are byte-for-byte unchanged in the diff). It documents
and test-locks the single-application invariant (`retained_fraction` in (0, 1];
arrival equals injection start), and — for RP-PTS — adds a thin call-site binding
that **composes** the existing decay authority (Section K.1), never a second
decay equation.

### K.1 RP-PTS radioactive-time binding (final transport closure)

`derive_rp_pts_radioactive_timing(nuclear, cycle, *, half_life_minutes,
network_length_m, prescribed_administration_activity_mbq=None)` binds the
existing Build 3C RP-PTS mission cycle (`compute_rp_pts_mission_cycle` =
dispatch + source-handling + tube-transit + destination-handling) to the
authoritative release→administration decay timeline through **one** interval:

```
release_anchor  = trace.release_time_minutes            (reused, not recomputed)
administration  = release_anchor + rp_pts_delivery_minutes
elapsed         = administration − release_anchor        (== rp_pts_delivery_minutes)
retained        = multi_isotope_decay.retained_fraction(elapsed, half_life)
required_upstream = multi_isotope_decay.required_upstream_activity(A_admin, retained)
```

`evaluate_dedicated_rp_pts_nuclear_transport_with_decay` composes the UNCHANGED
Build 3C RP-PTS economic evaluator with this timing so the SAME route length now
BOTH sizes labor/concurrency AND drives the payload decay timeline. No
economics change. The RP-PTS mission cycle excludes carrier return/reavailability
by construction, so the return leg is absent from `rp_pts_delivery_minutes` and
cannot inflate delivered-payload decay
(`return_time_included_in_payload_decay = False`).

**Single-interval / no double-decay (test-locked):** `elapsed ==
rp_pts_delivery_minutes` and `retained == retained_fraction(elapsed, half_life)`
reproduced directly from the canonical function — never
`retained_fraction(full) × retained_fraction(transport again)`.

**Route What-If (test-locked, benchmark F-18, half-life 109.8 min):** a longer
valid RP-PTS route (50 m → 400 m network length) increases delivery time
(4.14 → 5.09 min), lowers retained fraction (0.9742 → 0.9684), and increases
required upstream activity (379.8 → 382.1 MBq for a 370 MBq administration) —
all via the canonical decay authority, no hardcoded duplicate equation.

## L. Additive, default-safe result fields

The `ArchitectureResult` gains only additive, default-safe fields
(`physical_feasibility_status`, `qualification_status`,
`binding_physical_constraint`, the scanner/injection/uptake gate fields plus
resource source, `transport_feasible`, `transport_gate_status`,
`production_gate_status`, `production_capacity_status`,
`required_eob_activity_mbq_per_day`, `installed_eob_capacity_mbq_per_day`,
`unqualified_physical_constraints`, `per_radionuclide_production_gates`,
`transport_mode_gates`). Defaults are `NOT_EVALUATED` / empty, so any
construction that does not populate them is unaffected.

## M. The single seam: `_physical_feasibility_result_fields`

`_physical_feasibility_result_fields(pf)` maps a derived
`PhysicalFeasibilityResult` to the `ArchitectureResult` physical-contract kwargs,
including the derived `feasible`. Each canonical evaluator constructs its result
with `**_physical_feasibility_result_fields(_pf)`, so there is exactly one place
that translates the contract into the reported flag.

## N. The four canonical architectures

- `evaluate_manual_conventional`
- `evaluate_automated_conventional`
- `evaluate_hybrid_mrt` → delegates to `_evaluate_mrt_style_architecture`
- `evaluate_mrt_dominant` → delegates to `_evaluate_mrt_style_architecture`

All four now derive `feasible` from the common contract and carry the full
per-radionuclide production breakdown. A regression test confirms all four agree
on the production verdict (they share the same nuclear demand/production
authority).

## O. Defect found and fixed during closure

During closure the four canonical evaluators were found to reference
`**_physical_feasibility_result_fields(_pf)` while that helper was momentarily
undefined — a runtime `NameError`. The fix defined
`_physical_feasibility_result_fields` (immediately after
`derive_physical_feasibility`) and added the `per_radionuclide_production_gates`
and `transport_mode_gates` fields to `ArchitectureResult` so the per-radionuclide
and per-mode breakdowns propagate. The four-architecture suite passing is direct
evidence the fix restored the evaluators.

## P. Backward compatibility

Calling `_nuclear_result` and `derive_physical_feasibility` without
`clinical_resources` uses the 6/6/12 controlled benchmark labelled
`CONTROLLED_BENCHMARK`. All new `ArchitectureResult` fields are default-safe.
Economic outputs are unchanged.

## Q–Y. Constraints honored

- No composition optimizer, no UI.
- `equal_budget.py` is not in the diff.
- `hybrid_optimization.py` is not in the diff (decay math untouched).
- Build 3A target-bounded/NO_BUILD, Build 3B production, Build 3C transport, and
  Build 3C.1 two-route-family authorities are all reused and their suites pass.
- No carrier CapEx is added to the legacy `equal_budget` MRT path.

## Z. Known gaps and honest mode-by-mode coverage (documented, test-locked)

### Z.1 Light-MRT comparator
`evaluate_light_mrt_dominant` is a Build 2R comparator, **not** one of the four
canonical architectures. It still sets `feasible=True` and leaves the physical
contract at `NOT_EVALUATED`. This gap is deliberately left in place and is
locked by a test (`test_light_mrt_dominant_is_not_wired_to_common_contract`) so
a future closure of it is a visible, intentional change.

### Z.2 Transport-gate coverage by mode (honest)
The transport gate (`_resolve_transport_gate`) reads exactly two search
diagnostics carried on the nuclear result: `conventional_transporter_search`
(the nuclear-payload conventional transporter) and `mrt_carrier_search` (the MRT
carrier fleet). Directly-connected status per mode:

- **MRT carrier fleet** — DIRECTLY connected for `HYBRID_MRT` / `MRT_DOMINANT`
  (gate reads `mrt_carrier_search`).
- **Nuclear-payload conventional transporter** — DIRECTLY connected wherever a
  conventional nuclear payload is assigned (gate reads
  `conventional_transporter_search`).
- **PORTER (general logistics), AGV/RGHT, ordinary PTS, RP-PTS** — NOT directly
  connected to the physical gate. Their sizing authorities feed only the
  economic (CapEx/OPEX) path; RP-PTS is an economic/diagnostic evaluator whose
  result type is not a search diagnostic on the nuclear result. These are
  classified **PARTIAL** (represented economically, not in the physical gate).
  The exact seam: `_resolve_transport_gate` inspects only the two named searches;
  extending direct coverage would require carrying additional per-mode search
  diagnostics onto the nuclear result. This is disclosed, not silently passed.

### Z.3 Radioactive route-time → decay lineage by mode (honest)
The authoritative decay elapsed is `injection_start − production_release`, where
`production_release` is EOB + hot-lab processing (no transport term). Transport
time is included **exactly once** and only via its effect on `injection_start`
through the joint clinical schedule (arrival-based batch releases):

- **MANUAL** — outbound porter/manual time flows into arrival → clinical
  schedule → `injection_start`; porter RETURN time is EXCLUDED from payload
  decay (it only advances transporter availability). Included once: YES.
- **MRT** — actual MRT mission time (`dispatch + transport_minutes`) flows into
  arrival → `injection_start`; reposition/return leg EXCLUDED. Included once:
  YES.
- **RP-PTS** — NOW BOUND (final transport closure, Section K.1). The RP-PTS
  mission cycle (dispatch + source-handling + tube-transit + destination-handling)
  is folded into `administration` through a single `elapsed = administration −
  release_anchor` interval via `derive_rp_pts_radioactive_timing`, reusing the
  canonical `retained_fraction` / `required_upstream_activity` authority. Longer
  route → longer delivery → lower retention → higher required upstream (proven).
  Carrier return/reposition is EXCLUDED from the delivery cycle
  (`return_time_included_in_payload_decay = False`). Included once: YES.

No mode double-counts transport time in the decay interval, and no return/
reposition leg increases payload decay:
`PORTER_RETURN_INCLUDED_IN_PAYLOAD_DECAY = NO`,
`MRT_RETURN_INCLUDED_IN_PAYLOAD_DECAY = NO`,
`RP_PTS_RETURN_INCLUDED_IN_PAYLOAD_DECAY = NO`.

Note the distinction (Section 7 / Z.2): the RP-PTS *decay binding* is connected,
but RP-PTS as a whole-architecture transport mode is still only represented
economically in the four-architecture engine (its evaluator result is not one of
the two search diagnostics the physical transport gate reads). It is a
diagnostic/economic evaluator, not the assigned nuclear transport mode of any of
the four canonical architectures at this design point.

### Z.4 Remaining-gap classification (ACCEPTABLE_FOR_PART_3D vs BLOCKING)

Every remaining physical gap is classified against the canonical
four-architecture **nuclear/clinical** physical-feasibility contract — the exact
scope Part 3D closes.

- **Whole-architecture non-nuclear hospital logistics** (PORTER general
  logistics, AGV/RGHT, ordinary PTS) not directly in the physical gate —
  **ACCEPTABLE_FOR_PART_3D.** Part 3D's contract qualifies the transport
  resources of the nuclear/clinical patient chain; the broader hospital-logistics
  streams remain economically represented and are honestly disclosed as PARTIAL
  (Z.2). They do not gate the nuclear-clinical chain, so their absence does not
  make the nuclear feasibility verdict wrong — only narrower than "the whole
  building is physically qualified," which the doc explicitly does not claim.
- **RP-PTS as an assigned whole-architecture nuclear transport mode** —
  **ACCEPTABLE_FOR_PART_3D.** RP-PTS is not the assigned nuclear transport mode of
  any of the four canonical architectures at this design point; it is a
  diagnostic/economic evaluator. Its radioactive-time decay binding IS closed
  (K.1). Bringing it in as a gated canonical mode is a future scope decision, not
  a defect in the current four.
- **Light-MRT comparator outside the canonical four** (Z.1) —
  **ACCEPTABLE_FOR_PART_3D**, test-locked; not one of the four canonical
  architectures.
- **Modeled cyclotron production estimation for supported-but-uncalibrated
  model×radionuclide pairs** (e.g. CYPRIS MP-30 + F-18) —
  **ACCEPTABLE_FOR_PART_3D.** Part 3D correctly reports SUPPORTED=YES,
  CALIBRATION=NOT_CALIBRATED, numerical EOB=unavailable, and never fabricates a
  batch output. A future Cyclotron Production Estimation Authority
  (SITE_CALIBRATED / MANUFACTURER_CALIBRATED / MODELED_ESTIMATE /
  CONTROLLED_ASSUMPTION / NOT_AVAILABLE with provenance) is explicitly out of
  scope (Section 22). A NOT_CALIBRATED capacity is honestly non-binding, so it
  does not block the canonical four.
- **Full facility geometry content hashing / concealed-right-of-way civil cost /
  floor AGV-AMR implementation** — **ACCEPTABLE_FOR_PART_3D**, unrelated to the
  nuclear/clinical physical-feasibility contract.

No gap is classified **BLOCKING_PART_3D**: every calibrated nuclear-clinical gate
(scanner / injection / uptake / mode-specific transport / per-radionuclide
production) is connected and derives `feasible`, and the radioactive route-time
is decay-bound once for MANUAL, MRT, and RP-PTS.

---

## Verification summary

All runs used `/opt/anaconda3/bin/python -m pytest`. Counts below are the
physically observed pytest results (not historical estimates), executed in
stable groups.

New focused suite `test_part3d_physical_feasibility_closure.py`: **46 collected,
46 passed** (35 original invariant locks + 11 appended in this final closure:
mode-gate no-workload/counts/propagation, the RP-PTS route What-If group
[single-interval, longer-route-increases-delivery, lowers-retention,
increases-upstream, return-excluded, reuses-canonical-authority], and the CYPRIS
MP-30 + F-18 real-identity-uncalibrated-no-borrow control).

Directly-affected regression, all passing:

- Part 3D focused + `test_whole_oncology_four_architecture_optimization` +
  `test_hybrid_optimization` — **267 passed, 1 skipped**.
- Build 3B production + cyclotron catalog/fleet/windows + generator native +
  multi-isotope decay + cycle-relative production requirement + production
  requirement reconciliation + multi-cyclotron radionuclide — **133 passed**.
- Build 3C transport + Build 3C.1 spatial route + dedicated RP-PTS authority +
  MRT carrier fleet + transport-spatial builds 1–4 + clinical resource identity +
  clinical bottleneck — **316 passed**.
- Build 3A (`test_build3a_mrt_patch_c`, `test_build3a2_identity`) + generator
  native authority completion — **49 passed**.
- Production/clinical scheduling (`test_production_clinical_schedule` 30,
  `test_operating_day_scheduler` 18) — **48 passed**.
- Retention (`test_retention_qualified_throughput_authority`,
  `test_retention_aware_resource_sizing`) — **15 passed**.
- Patient radionuclide demand + PET/SPECT nuclear completion + MRT transport
  separation + conventional route spatial sensitivity — **69 passed**.
- Capital Project API (FastAPI shared contract) — **27 passed**.
- Decision pipeline + cluster distribution + patient-aware general logistics —
  **74 passed**.
- Multi-origin cyclotron spatial + MRT vs second-cyclotron decentralization —
  **33 passed**.
- Legacy-engine preservation: `test_equal_budget.py` — **78 passed** (~146 s;
  `equal_budget.py` itself is a zero-byte diff).
- `test_spatial_benchmark.py` (the ProductionBasis / spatial authority) — full
  suite **22 passed** (~467 s; a heavy benchmark-optimization run).

Legacy engines untouched (git diff = 0 bytes each): `equal_budget.py`,
`hybrid_optimization.py`, `multi_isotope_decay.py`. The only modified tracked
file is `whole_oncology_four_architecture_optimization.py`.

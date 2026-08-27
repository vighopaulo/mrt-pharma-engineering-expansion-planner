# Four-Architecture Project Decision Authority — Repository-First Audit & Closure Report

**Governing principle for this build:** make the capital/project decision chain use
*existing* engineering authorities correctly, rather than build a new parallel
economics engine. This report supersedes the *approach* used by
`four_architecture_economic_report_PART_D_BASELINE.md` and
`four_architecture_economic_report_PART_D1_CORRECTED.md` (both preserved unchanged
as historical diagnostic artifacts, per instruction — neither is the governing
architecture authority). Those two documents described a bespoke comparator built
inside `operational_day_orchestrator.py`. This report documents auditing and
correcting the *actual*, deeper, pre-existing four-architecture chain in
`whole_oncology_four_architecture_optimization.py` and its dependencies.

---

## Table 1 — Mandatory Authority-Map (Section 3)

Traced via direct source reading and `grep` call-site verification, not inferred
from filenames.

| Decision quantity | Existing authoritative producer | Existing consumer | Binding status | Duplicate/parallel logic? | Action taken |
|---|---|---|---|---|---|
| Conventional spatial envelope | `spatial_benchmark.compute_retention_envelope` (pathway="Conventional") | `hybrid_optimization.evaluate_hybrid_zone_candidate` | Bound | No | None needed |
| MRT spatial envelope | `spatial_benchmark.compute_retention_envelope` (pathway="MRT") | `hybrid_optimization.evaluate_hybrid_zone_candidate` | Bound | No | None needed |
| Retention-qualified throughput | `spatial_benchmark._operational_retention_metrics` | `hybrid_optimization`, `_nuclear_result` | Bound | Yes — same formula reimplemented in `hybrid_optimization.py:641` and `inbound_patient_program.py:684` | Flagged; not consolidated this build (low priority, no behavioral defect) |
| Conventional resource sizing | `conventional_transport_authority.compute_porter_resource_requirement` (sweep-line peak concurrency) | `evaluate_manual_conventional`, `evaluate_automated_conventional` | Bound | No | None needed |
| **MRT carrier fleet sizing** | `hybrid_optimization`'s adaptive workload-driven search → `mrt_carrier_fleet.resolve_mrt_carrier_fleet` | `shared_mrt_multistream_authority.compute_shared_mrt_economic_result` → `evaluate_hybrid_mrt`/`evaluate_mrt_dominant` | **Confirmed already bound correctly** | No | Verified via a new proof test; **no code change required** |
| MRT guideway geometry | `hybrid_optimization`'s `compute_inbound_room_guideway_extension` (real per-room accumulation) | Same as above (embedded in `HybridEvaluationResult.total_capex`) | **Confirmed already bound correctly** | No | Verified via proof test |
| MRT endpoint count | `len(mrt_rooms)` in `evaluate_hybrid_zone_candidate` | Same | Bound | No | None needed |
| **AGV fleet sizing** | `conventional_transport_authority.agv_required_fleet_size` (existed, was never called) | `evaluate_automated_conventional` | **Was NOT bound — confirmed defect** | Yes — `fleet_size=1` hardcoded | **FIXED** (see Table 2) |
| **PTS infrastructure sizing** | Did not exist | `evaluate_automated_conventional` | **Was NOT bound — confirmed gap** | — | **Added** `pts_required_station_count()`; wired in |
| Manual transport workload | `compute_porter_resource_requirement` | `evaluate_manual_conventional` | Bound | No | None needed |
| **Automated-Conventional last-mile workload** | Did not exist anywhere in the repository | — | **Was NOT modeled** | — | **Added** CLUSTER+DISTRIBUTION landing-point/last-mile authority |
| **Hybrid building assignment** | `campus_retrofit_benchmark.py` (`CAMPUS_HYBRID_A_CONVENTIONAL_B_MRT`) already modeled this, but was disconnected from the four-architecture comparator | — | **Was NOT wired into the comparator** | No (pre-existing, correct authority) | **Added** `evaluate_building_level_campus_hybrid()` wrapper + explicit `HybridScope` disclosure |
| Infrastructure CapEx | `infrastructure_capex.calculate_infrastructure_capex` (pure ledger; also a locally-composed equivalent sum inside `evaluate_hybrid_zone_candidate`) | Various | Bound | No | None needed |
| Infrastructure OPEX | `infrastructure_opex.calculate_infrastructure_opex` (via `_build_hybrid_opex_result`) | `evaluate_hybrid_zone_candidate` | Bound | No | None needed |
| Lifecycle economics | `lifecycle_economics.evaluate_lifecycle_economics` | `evaluate_hybrid_zone_candidate`, `campus_retrofit_benchmark` | Bound | No | None needed |
| Architecture recommendation | `whole_oncology_four_architecture_optimization.rank_cost_only` / `rank_revenue_aware` / `compute_pareto_front` | Test suite (not yet a report-level entry point) | Bound, functional | No | None needed |

---

## Table 2 — Confirmed Defect & Fix: Automated Conventional

**Defect (confirmed by direct code read of `evaluate_automated_conventional`,
pre-closure):**

```python
agv_capex = agv_new_study_capex(proposed_agv, fleet_size=1, study_scope="CAPITAL_PLANNING")
agv_opex_val = agv_annual_opex(proposed_agv, fleet_size=1, loaded_annual_cost_per_fte=loaded_cost)
```

`fleet_size=1` was hard-coded regardless of real mission volume. The existing
`agv_required_fleet_size()` function (workload/availability/peak-concurrency
derived) was never called. There was also no PTS-equivalent sizing function —
`DEFAULT_PTS_NETWORK.station_count=6` was charged flat regardless of workload.
There was no landing-point / last-mile concept anywhere in the repository
(confirmed via grep: zero matches for "landing", "hub", "floor_station",
"distribution_point" in `conventional_transport_authority.py`).

**Fix — new authorities added to `conventional_transport_authority.py`:**

| New function/constant | Purpose |
|---|---|
| `pts_required_station_count()` | Mirrors `agv_required_fleet_size`; station count derived from real mission-minutes workload, never fixed at 6 |
| `AUTOMATED_CONVENTIONAL_CLUSTER_MAX_VERTICAL_TRANSITIONS = 1` | Disclosed policy threshold: floors within this many vertical transitions of the general-logistics origin stay CLUSTER (pure Manual); farther floors become DISTRIBUTION |
| `LANDING_POINT_LAST_MILE_DISTANCE_M = 15.0` | Short, explicit last-mile distance — never a reused full-route porter mission timing |
| `classify_floor_service_tier()` | CLUSTER vs DISTRIBUTION classifier, driven by the actual per-load floor number |
| `compute_automated_conventional_distribution_timing()` | Composes `T_origin_handling + T_automated_main_leg + T_landing_handoff + T_manual_last_mile + T_destination_handoff` from existing primitives only |

**`evaluate_automated_conventional()` rewritten** (in
`whole_oncology_four_architecture_optimization.py`) to: for each of the 4 general
logistics streams, split consolidated loads by real destination floor
(`_extract_load_floor_number`, parses `WARD-F{n}`) into CLUSTER (pure Manual,
unchanged authority) and DISTRIBUTION (automated main leg, sized via
`agv_required_fleet_size`/`pts_required_station_count`, plus a separately-sized
manual last-mile porter pool).

**Verified live numbers** (`build_common_project_baseline()` default seed):

| Architecture | New study CapEx | Annual OPEX | Porter FTE | Lifecycle cost |
|---|---:|---:|---:|---:|
| Manual Conventional | $0 | $1,750,320 | 33.0 | (baseline) |
| Automated Conventional (closed) | $270,000 | $1,826,272 | 34.0 | $12,524,433.78 |

Automated Conventional now costs **more** than Manual Conventional for this
controlled facility — the real AGV/PTS CapEx is no longer artificially cheap at
`fleet_size=1`, and the added equipment cost is not offset by proportional labor
savings. This is an honest, non-forced outcome (no architecture is designed to
win).

---

## Table 3 — MRT Carrier Fleet / Guideway Audit Result

**Traced call chain:** `evaluate_hybrid_mrt`/`evaluate_mrt_dominant` →
`_evaluate_mrt_style_architecture` → `_nuclear_result` →
`hybrid_optimization.evaluate_hybrid_zone_candidate` (real, adaptive,
workload-driven carrier search + real per-room guideway accumulation via
`compute_inbound_room_guideway_extension`) → `compute_shared_mrt_economic_result`
(in `shared_mrt_multistream_authority.py`), which reads `hybrid_result.total_capex`
/ `hybrid_result.mrt_carriers` **unchanged** and only *adds* the general-logistics
container ledger on top.

**Conclusion: this binding was already correct before this build.** The
$11,000-carrier-CapEx figure referenced in earlier session notes was isolated
entirely to the bespoke `operational_day_orchestrator.py` module (Parts B–D.1),
never to this deeper chain. **No code change was required here** — only a proof
test was added:

```
test_mrt_carrier_fleet_and_guideway_are_workload_derived_not_representative
```

which confirms widening MRT floor coverage genuinely changes carrier count,
guideway length, and total CapEx (a hard-coded representative figure would never
move).

**Pre-existing issue found (not fixed, flagged for follow-up):**
`_evaluate_mrt_style_architecture` contains
`automation_or_mrt_fte=combined_result.shared_carrier_fleet.installed_carriers * 0.0 + 3.0`
— this always evaluates to `3.0` regardless of `installed_carriers` (dead/placeholder
arithmetic). This is pre-existing code, not introduced by this session, and is out
of the explicit scope of this closure (CapEx/OPEX/guideway binding). It affects
only the reported `automation_or_mrt_fte` field, not CapEx/OPEX/lifecycle
economics. Recommend a follow-up decision on the correct formula before touching
it.

---

## Table 4 — Building-Level Hybrid (Capital-Project Definition)

The audit found `campus_retrofit_benchmark.py` **already implements** exactly the
capital-project Hybrid definition requested (Building A = Conventional existing
production, Building B = MRT-served retrofit), via `CAMPUS_HYBRID_A_CONVENTIONAL_B_MRT`
— but it was never wired into `whole_oncology_four_architecture_optimization.py`'s
comparator, which only exposed the **zone-level** (single-building, floor-split)
Hybrid definition via `evaluate_hybrid_mrt`.

**Closure added:**
- `HybridScope = Literal["ZONE_LEVEL_SAME_BUILDING", "BUILDING_LEVEL_CAMPUS"]`
- `CampusHybridResult` dataclass + `evaluate_building_level_campus_hybrid()` —
  thin wrapper reusing `campus_retrofit_benchmark.build_two_building_campus_geometry`,
  `run_campus_case_1_conventional`, `run_campus_case_2_hybrid` verbatim (no new
  physics/economics).
- `evaluate_hybrid_mrt`'s `notes` now explicitly disclose
  `HYBRID_SCOPE=ZONE_LEVEL_SAME_BUILDING`, pointing to the campus-level function —
  it is never silently presented as the campus-level definition.
- The existing zone-level `evaluate_hybrid_mrt`/`hybrid_optimization.py` are
  **unchanged and preserved** — both Hybrid interpretations coexist.

**Verified live numbers** (`evaluate_building_level_campus_hybrid()` default
500 m separation, Building B demand=200, all 4 Building-B floors MRT-served):

| Field | Value |
|---|---:|
| Building A new CapEx | $0 (existing shell) |
| Building B total CapEx | $45,040,000 |
| Combined annual OPEX | $6,580,955 |
| Retention-qualified completed | 72 |
| Qualified lifecycle NPV | $200,676,772.70 |

---

## Table 5 — Retrofit vs Greenfield Semantics (Reviewed, No Change Needed)

`DevelopmentContext` (`RETROFIT`/`GREENFIELD`) is tracked on `ArchitectureResult`/
`StudyConfiguration` and drives `compute_retrofit_to_greenfield_transition_impact()`,
which describes the asset-reclassification impact of moving from a Retrofit to a
Greenfield configuration (existing MRT guideway/endpoints/carriers/AGV/PTS/generator
→ PROPOSED). The actual retained-vs-new CapEx mechanism is the pre-existing
`StudyScope` (`CAPITAL_PLANNING`/`OPERATIONAL_ONLY`) + `existing_*`/`installed_*`
ledger fields in `infrastructure_capex.py`/`decision_pipeline.py` (confirmed via
`study_scope.py`'s own audit docstring). `evaluate_building_level_campus_hybrid`'s
`building_a_new_capex=0.0` is consistent with this pattern (Building A is always the
existing production shell in this benchmark). No code change was required.

---

## Table 6 — Test Coverage Added This Build

| Test file | New/updated tests |
|---|---|
| `test_patient_economics_conventional_transport_authority.py` | 6 new tests: PTS station-count zero/scaling, floor-tier classification, distribution timing never reuses full-route timing, technology-model validation, PTS vs AGV handoff-minutes distinction |
| `test_whole_oncology_four_architecture_optimization.py` | 1 renamed/updated non-regression test (CLUSTER+DISTRIBUTION closure), 3 new tests (never-forced-to-win, workload-derived fleet disclosure, CLUSTER reuses unchanged Manual authority), 1 new MRT carrier/guideway proof test, 2 new building-level-campus-Hybrid tests |
| `test_whole_oncology_patient_identity_unification.py` | 1 updated test (`test_cost_only_ranking_reflects_cluster_distribution_closure`, replacing a stale hard-coded "Automated always wins" expectation) |

**Directly-affected regression:** 499 passed (10 test files: canonical facility
geometry, canonical spatial authority closure, conventional economic calibration,
full operational capital qualification, OpenUSD spatial adapter, patient economics
conventional transport authority, shared MRT multistream authority, whole-oncology
four-architecture optimization, whole-oncology patient identity unification,
campus retrofit benchmark).

**Full-repository regression:** **2334 passed, 3 deselected, 0 failed (0:53:20).**
The 3 deselected tests are the same 3 pre-existing, independently-diagnosed,
unrelated failures carried throughout this session
(`test_cyclotron_catalog_e2e_integration`, `test_multi_cyclotron_radionuclide_authority`,
`test_zero_capacity_propagation`) — deliberately excluded via `--deselect` to give
a clean signal. **Zero new failures were introduced by this closure build.**

---

## Governing Rules Observed

- No existing physics/economics engine was redesigned or duplicated.
- No architecture was forced to win — Automated Conventional's real CapEx now
  makes it cost *more* than Manual for this facility; this was not adjusted to
  produce a different, more favorable-looking result.
- Tests were only changed when they encoded the confirmed-defective prior
  behavior as a permanent expectation (fleet_size=1, Automated-always-wins) —
  never to force a preferred result.
- UI/UX work was not started.
- The existing zone-level Hybrid optimizer (`hybrid_optimization.py`,
  `evaluate_hybrid_mrt`) was preserved unchanged; the building-level campus
  Hybrid is an additive, explicitly-scoped wrapper.

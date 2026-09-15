# MRT Pharma — Build 2A: Canonical Transport Unit Equipment + Mission Authority + Mode Eligibility + Shared Endpoints + Automatic Connectivity Foundation

**Checkpoint:** `HOLD_FOR_BUILD_2A_TRANSPORT_FOUNDATION_MANUAL_ACCEPTANCE`
**Status:** COMPLETE — awaiting manual acceptance. No stage / commit / push performed.
**Data file:** `mrt_pharma_build_2a_canonical_transport_and_automatic_connectivity_data.json`

> Distinct from the earlier `MRT_PHARMA_BUILD_2A_THREE_ROOM_COMPOSITION_REPORT.md`. This report covers the transport-mission / eligibility / automatic-connectivity foundation only.

---

## 1. Summary

Build 2A adds the **mission-first automatic-connectivity foundation** for hospital
logistics transport. It is a **thin, additive composition layer** over the transport
authorities that already exist in this repository. It introduces **no new physics,
no new economics engine, no new routing engine, no new eligibility engine, and no
new per-mode transport-unit equipment**. Every genuinely-missing seam is implemented
by composing existing canonical authority; nothing canonical was duplicated or
rewritten.

**Files changed:** `PYTHON_FILES_CHANGED = 2` — both **new, untracked**:

- `transport_connectivity_composition_authority.py` (the composition seam)
- `test_transport_connectivity_composition_authority.py` (26 deterministic tests)

**Zero existing `.py` files modified. Zero frontend files modified.** `frontend/.env`
was not staged or touched. Build 1A, Build 1B, and the prior-turn walkthrough edits
remain preserved and uncommitted.

---

## 2. Source-first audit outcome (what already existed)

The mission-first pipeline (`MISSION → ELIGIBILITY → CONNECTIVITY → INTERFACE
REQUIREMENTS → INFRASTRUCTURE`) is almost entirely already canonical. Classification:

| Concept | Verdict | Canonical owner (reused) |
|---|---|---|
| Mode taxonomy (MRT/RGHT/PTS/Manual) | `SOURCE_AUTHORITY_FOUND` | `transport_technology_authority.py` |
| Cross-mode eligibility gate | `SOURCE_AUTHORITY_FOUND` | `transport_mode_eligibility_authority.py` |
| Mode-neutral optimizer mission | `SOURCE_AUTHORITY_FOUND` (thin) | `generalized_transport_optimizer.OptimizerMission` |
| Route resolution / connectivity | `SOURCE_AUTHORITY_FOUND` | `canonical_spatial_authority.resolve_route`, `transport_mission_route_bridge.resolve_mission_route` |
| Endpoint semantics + validation | `SOURCE_AUTHORITY_FOUND` | `payload_endpoint_authority.py` |
| MRT/PTS/RGHT/conventional unit equipment | `SOURCE_AUTHORITY_FOUND` | `canonical_spatial_authority`, `pts_spatial_network_authority`, `rght_spatial_network_authority`, `conventional_transport_authority` |
| Cost authorities | `SOURCE_AUTHORITY_FOUND` | `MRT_VESTIBULE_CAPEX_USD = $30,000`; `LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT = $1,000`; `compute_mrt_transport_only_capex`; `study_scope` existing-vs-installed mechanism |
| PTS network contention/capacity | `NOT_IMPLEMENTED` (upstream) | `pts_spatial_network_authority.PTS_NETWORK_CONTENTION_STATUS` — **not invented here** |

### AGV/RGHT status correction

The committed baseline value at HEAD is
`transport_technology_authority.FLOOR_AGV_AMR_IMPLEMENTATION_STATUS = "IMPLEMENTED"`
(a `floor_agv_amr_authority.py` exists with `AGV_AMR_LIGHT_CLINICAL` +
`AGV_AMR_HEAVY_LOGISTICS`). A prior September-9 assumption of `NOT_IMPLEMENTED` has
been **superseded**. Recorded honestly:

- `TRUE_FLOOR_AGV_AMR_STATUS = IMPLEMENTED`
- `RGHT_EQUALS_AGV_AMR = NO` (RGHT is a distinct rail-guided installed network)

---

## 3. New Build 2A implementation (the genuinely-missing seams)

All in `transport_connectivity_composition_authority.py` — `ADDITIVE_COMPOSITION_ONLY`.

1. **`LogisticsMission`** — enriches the thin `OptimizerMission` with the mission-first
   attributes that were missing: radioactive/nuclear flag (forced `True` for a
   radiopharmaceutical stream), nuclear qualification, origin/destination canonical
   object ids, priority (`ROUTINE`/`URGENT`/`STAT`), demand frequency, and SLA.
   None-valued attributes remain honest `NOT_CALIBRATED`.

2. **`resolve_mission_endpoint_objects`** — composes `default_endpoints` roles with
   mission-supplied object ids. When object ids are absent, `endpoints_resolved = False`
   and downstream connectivity is honest `NOT_CALIBRATED` — never a fabricated id.

3. **One room → one shared clinical logistics endpoint**
   (`SharedClinicalLogisticsEndpointRegistry`) — idempotent, keyed by room canonical
   object id, reuse-before-create (accumulates `serving_modes` across missions/modes),
   refuses non-room-like and production objects. Unit cost is the **$1,000 crosswalk**
   to `LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT`. Existing rooms cost `$0` new.
   **`MRT_VESTIBULE_EQUALS_ROOM_ENDPOINT = NO`.**

4. **MRT vestibule requirement derivation** (`derive_mrt_vestibule_requirement`) —
   distinct from a room endpoint; **$30,000 crosswalk** to `MRT_VESTIBULE_CAPEX_USD`.
   An existing MRT vestibule is not charged as new.

5. **`TransportConnectivityCandidate` + `evaluate_transport_connectivity`** — the ONE
   deterministic per-(mission, mode) verdict, composing eligibility → endpoint
   resolution → route bridge → endpoint validation → vertical connectivity. Statuses:
   `FEASIBLE`, `INFEASIBLE`, `NOT_CALIBRATED`, `NO_NETWORK_PATH`,
   `MISSING_ORIGIN_INTERFACE`, `MISSING_DESTINATION_INTERFACE`,
   `MISSING_VERTICAL_CONNECTIVITY`, `PAYLOAD_INCOMPATIBLE`, `MODE_INELIGIBLE`.
   **`CONNECTIVITY_SEPARATE_FROM_CAPACITY = YES`** — a FEASIBLE verdict never asserts
   throughput. `evaluate_mission_connectivity` ranks nothing and picks no winner
   (**`MRT_FORCED_AS_DEFAULT_WINNER = NO`**).

6. **Cross-mode infrastructure bill-of-materials** (`compose_transport_infrastructure_bom`)
   — reuses `compute_pts_infrastructure_quantities` / `compute_rght_infrastructure_quantities`
   and the canonical `AssetStatus` (`EXISTING` vs `PROPOSED`) to split ALREADY-EXISTING
   from NEW_REQUIRED. **`SYNTHETIC_TRANSPORT_CAPEX = NO`** — network CapEx is deferred to
   the owning computers (reported `CROSSWALK`/`NOT_CALIBRATED`, never a fabricated
   percentage block).

### OUT_OF_SCOPE (protected, not built)

The 7 radiopharmacy production/handling units — `HOT_CELL`, `DISPENSING_QC_HOT_CELL`,
`DOSE_CALIBRATOR_BENCH`, `FUME_HOOD`, `ISOLATOR`, `SHIELDED_STORAGE`,
`WASTE_DECAY_STORE` — are **`OUT_OF_SCOPE`**. They are not transport-unit equipment and
receive no catalog entry, no CapEx, and no shared endpoint. Protection is enforced by
`is_out_of_scope_production_unit` and by the shared-endpoint registry refusing
non-room-like objects.

---

## 4. Deterministic proof

- Controlled RGHT cross-floor mission `RGHT-STN-RP → RGHT-STN-SCN` resolves
  `FEASIBLE`, `route_distance_m = 25.03`, `requires_vertical_connectivity = True`,
  `vertical_connectivity_satisfied = True`.
- The controlled RGHT proof network splits `existing = 3 / new_required = 7` via the
  canonical `AssetStatus`.

---

## 5. Verification

Runner: `.venv/bin/python -m pytest` (the system `python3` has no pytest).

- **New suite:** `test_transport_connectivity_composition_authority.py` — **26 passed / 0 failed.**
- **Regression (12 suites):** **541 passed / 4 failed.**

**Regressions introduced by Build 2A: 0.**

The 4 failures are **PRE-EXISTING at baseline HEAD `1de2c5b0`** and are not caused by
this build:

- `test_transport_spatial_authority_build1.py::test_6_floor_agv_amr_remains_not_implemented`
- `test_transport_spatial_authority_build2.py::test_3_floor_agv_amr_remains_distinct`
- `test_transport_spatial_authority_build3.py::test_35_floor_agv_amr_remains_not_implemented`
- `test_transport_spatial_authority_build4.py::test_50_floor_agv_amr_remains_not_implemented`

All four assert `FLOOR_AGV_AMR_IMPLEMENTATION_STATUS == "NOT_IMPLEMENTED"`, but the
committed value at HEAD is `"IMPLEMENTED"`. Proof they are independent of Build 2A:
`transport_technology_authority.py` is **not modified** vs HEAD
(`git diff --stat HEAD` empty); none of the four test files import
`transport_connectivity_composition`; and temporarily removing both Build 2A files
reproduced the `build1::test_6` failure identically. These are noted for a future
authority-reconciliation build; Build 2A does not touch them.

**Frontend verification:** not required — no frontend files were modified by Build 2A.

---

## 6. Scope / boundaries honored

- No transport animation started.
- No discrete-event transport simulation started.
- No Build 2B work started.
- Walkthrough and True-2D-Plan remain
  `IMPLEMENTED_BUT_MANUAL_ACCEPTANCE_FAILED_DEFERRED` (not modified, not deleted).
- Authority docs were **not** rewritten.
- No stage / commit / push. `frontend/.env` untouched.

**STOP — awaiting manual acceptance (`HOLD_FOR_BUILD_2A_TRANSPORT_FOUNDATION_MANUAL_ACCEPTANCE`).**

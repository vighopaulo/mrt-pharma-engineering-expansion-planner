# MRT Pharma — Build 1B Walkthrough / True-2D Plan: UX Deferred-Acceptance Checkpoint

**Nature:** truthful disposition checkpoint only. No Walkthrough fix, no 2D-plan
fix, no UX change, no authority-doc change, no stage/commit/push. The CURRENT
working tree is treated as authority.

## 1. Reconcile (actual current tree)

- `PRECHECK_HEAD` = `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3`
- `PRECHECK_ORIGIN_MAIN` = `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3`
- `PRECHECK_DIVERGENCE` = `0 0` · branch `main`
- `PRIOR_BUILD_1A_WORK_PRESERVED` = YES
- `CURRENT_BUILD_1B_WORK_PRESERVED` = YES
- `FRONTEND_ENV_STAGED` = NO (`frontend/.env` remains modified + unstaged; never staged)

The working tree contains substantial Build 1B work: canonical equipment catalog
+ instance + validation, clinical-room candidate + re-parent seams, simultaneous
2D-plan projection + panel, targeted walkthrough spawn, walkthrough trail, and
their reports/tests — all preserved. In-progress walkthrough-controller edits are
also preserved. Nothing was reverted.

## 2. Latest manual acceptance — authoritative result

The user has explicitly rejected the current Walkthrough / 2D-plan experience:

- `WALKTHROUGH_MANUAL_ACCEPTANCE` = FAIL
- `TRUE_2D_PLAN_MANUAL_ACCEPTANCE` = FAIL
- `WALKTHROUGH_TRAIL_MANUAL_ACCEPTANCE` = FAIL
- `BUILD_1B_UX_MANUAL_ACCEPTANCE` = FAIL

Automated-test success is NOT reinterpreted as manual acceptance. These features
are not reported complete.

## 3. Observed Walkthrough defect

- `WALKTHROUGH_IMPLEMENTATION_PRESENT` = YES
- `WALKTHROUGH_AUTOMATED_TESTS_PRESENT` = YES
- `WALKTHROUGH_PRODUCT_ACCEPTANCE` = FAIL
- Status: `IMPLEMENTED_BUT_MANUAL_ACCEPTANCE_FAILED`

Forward movement remains effectively stuck/constrained in actual use; the camera
can become trapped; practical navigation to intended clinical rooms is unreliable.
Collision is NOT disabled; no further collision/navigation rewrite is attempted
in this task.

## 4. Observed True-2D plan defect

- `TRUE_2D_PLAN_IMPLEMENTATION_PRESENT` = YES
- `TRUE_2D_PLAN_PROJECTION_TESTS_PRESENT` = YES
- `TRUE_2D_PLAN_PRODUCT_ACCEPTANCE` = FAIL
- Status: `IMPLEMENTED_BUT_MANUAL_ACCEPTANCE_FAILED`

The mini-plan can still report 0 rooms / 0 exact / 0 approx while Walkthrough is
active inside the BIM; BIM room/floor geometry is not reliably available in the
mini-plan during actual use. The existing implementation is retained; no further
projection/discovery correction is attempted here.

## 5. Observed trail defect

- `WALKTHROUGH_TRAIL_IMPLEMENTED` = YES
- `WALKTHROUGH_TRAIL_AUTOMATED_TESTS` = PASS (verified in the current suite)
- `WALKTHROUGH_TRAIL_PRODUCT_ACCEPTANCE` = FAIL

Trail samples accumulate mathematically, but without reliable movement + reliable
BIM-floor rendering the trail does not yet constitute an accepted navigation aid.
Heading indicator ≠ accumulated path. Trail implementation is retained; further
trail work is deferred with the Walkthrough / mini-plan UX.

## 6. Architectural separation (recorded)

- `WALKTHROUGH_IS_SIMULATION_AUTHORITY` = NO
- `TRUE_2D_PLAN_IS_SIMULATION_AUTHORITY` = NO
- `WALKTHROUGH_IS_TRANSPORT_ROUTING_AUTHORITY` = NO
- `TRUE_2D_PLAN_IS_TRANSPORT_ROUTING_AUTHORITY` = NO
- `WALKTHROUGH_IS_OPTIMIZATION_AUTHORITY` = NO

Walkthrough and the 2D plan are visual/manual inspection + navigation capabilities
only. Neither determines transport-mode eligibility, mission generation, routing
feasibility, infrastructure quantities, carrier/patient throughput, cyclotron
production, decay, economics, optimization, What-If, or LOCKDOWN. This separation
is why these UX defects may be deferred without blocking the transport engine.

## 7. Preserved foundation (not rolled back)

All currently implemented + tested work is preserved, including: generic BIM room
discovery; storey-aware room collection; exact IfcSpace geometry extraction;
ClinicalPlanningVolume; exact-parent containment; clinical-room candidate engine +
recommendation tiers + semantic guard; room re-parenting seam; canonical equipment
catalog binding; equipment containment; targeted Walkthrough spawn; Walkthrough
movement/collision; simultaneous 2D-plan projection; walkthrough-state
observability; walkthrough trail; all Build 1A + 1B regression tests; all Build 1B
reports and provenance.

## 8. Deferred open gaps (NOT closed)

- `GAP_WALKTHROUGH_NAVIGATION_RELIABILITY` — DEFERRED_FOR_UX_HARDENING:
  Walkthrough exists + automated-test-covered, but practical manual navigation is
  unreliable / prone to getting stuck.
- `GAP_TRUE_2D_PLAN_RUNTIME_ROOM_HYDRATION` — DEFERRED_FOR_UX_HARDENING:
  the mini-plan projection exists, but the runtime can still show zero BIM rooms
  while Walkthrough is active.
- `GAP_WALKTHROUGH_TRAIL_PRODUCT_USABILITY` — DEFERRED_FOR_UX_HARDENING:
  accumulated trail exists, but without reliable movement + reliable BIM-floor
  rendering it is not yet an accepted navigation aid.

`DEFERRED_GAP_COUNT` = 3.

## 9. Build 1B status

- `BUILD_1B_ENGINEERING_FOUNDATION` = IMPLEMENTED_AND_AUTOMATED_TESTED (verified
  against the current tree: typecheck PASS, 61 files / 1010 tests / 0 regressions,
  production build PASS).
- `BUILD_1B_WALKTHROUGH_UX` = IMPLEMENTED_BUT_MANUAL_ACCEPTANCE_FAILED
- `BUILD_1B_TRUE_2D_PLAN_UX` = IMPLEMENTED_BUT_MANUAL_ACCEPTANCE_FAILED
- `BUILD_1B_UX_COMPLETION_GATE` = FAIL_DEFERRED

This does not erase the successful Build 1B equipment / candidate / containment work.

## 10. Next major priority (recorded, NOT started)

`NEXT_MAJOR_BUILD` = BUILD 2A — CANONICAL TRANSPORT MODES + LOGISTICS MISSION
AUTHORITY + TRANSPORT ELIGIBILITY + SHARED ENDPOINT/ORIGIN INTERFACES + AUTOMATIC
CONNECTIVITY. Governing workflow: SIMULATE → infer required logistics missions →
determine eligible transport modes → automatically generate feasible
connections/routes → evaluate the facility. Transport families to carry forward:
MANUAL, AGV_AMR (light-clinical vs heavier material-handling), PTS
(CONVENTIONAL_PTS vs RADIOPHARMACEUTICAL_QUALIFIED_PTS), RTHS, MRT. Spatial
doctrine: HUMAN_CIRCULATION_NETWORK + CONCEALED_SERVICE_TRANSPORT_CORRIDOR (shared
right-of-way ≠ identical centerline). Room-side: SHARED_CLINICAL_LOGISTICS_ENDPOINT
(~$1,000/endpoint controlled assumption); MRT_RADIOPHARMACY_VESTIBULE distinct
(~$30,000 controlled assumption); mode-specific origin stations; mission-first
eligibility. No animation/economics in Build 2A's first authority phase. None of
this is implemented in this checkpoint task.

## 11. Verification (current tree)

- `TYPECHECK` = PASS
- `OFFLINE_TEST_FILE_COUNT` = 61
- `OFFLINE_TEST_COUNT` = 1010
- `OFFLINE_TEST_REGRESSIONS` = 0
- `PRODUCTION_BUILD` = PASS · `CORE_FRONTEND_VERSION` = 5.12.5
- `WORKER_ASSET_REAL` = YES (`(()=>{"use strict";f`) · `DRACO_WASM_ASSET_REAL` = YES
  (`0061 736d`)

## 12. Git safety

`FILES_STAGED` = NO · `COMMIT_CREATED` = NO · `PUSH_PERFORMED` = NO ·
`frontend/.env` untouched · authority documents NOT altered · Build 2A NOT started.

**CHECKPOINT = BUILD_1B_UX_DEFERRED_READY_FOR_TRANSPORT_BUILD.**

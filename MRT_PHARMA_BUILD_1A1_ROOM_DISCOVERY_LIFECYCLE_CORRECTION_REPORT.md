# MRT Pharma — Build 1A.1: Generic BIM Room-Discovery Lifecycle Correction (200 → 0 runtime regression)

**Continues:** Build 1A (uncommitted working tree). **Does not** restart 1A or begin 1B.
**Precheck:** HEAD = origin/main = `344d0289723e873c7a2974d0d8d295b38f44a6a3`,
divergence `0 0`; Build 1A work preserved; `frontend/.env` unstaged/excluded.
**Nature:** frontend lifecycle/dataflow fix + pure tests. No backend/domain change;
no Bentley writes; no stage/commit/push.

## 1. Preserved failure provenance (RUNTIME, from manual acceptance)

The first Build 1A acceptance gate FAILED at runtime:

- BIM_VISIBLE = YES (MRTway Medical Clinic Demo visibly rendered)
- Clinical Program ON, First Floor selected
- Room selector initially: **`Select a room (200)`**
- Later, same BIM still rendered: **`Select a room (0)`** +
  "No BIM spaces available yet — open the model, then retry."
- Persisted Uptake 01 assignment still present (Assigned rooms: 1)

`PREVIOUSLY_OBSERVED_DISCOVERED_ROOM_COUNT = 200`,
`FAILED_OBSERVED_DISCOVERED_ROOM_COUNT = 0`, `MANUAL_ROOM_DISCOVERY = FAIL`. This
observation is retained as provenance and is NOT erased.

## 2. Root cause (source-traced, not inferred)

Traced authority chain: active product viewport → `getIModel()` →
`buildModelSemantics` → `refreshModelSemantics` → `cachedModelSemantics.rooms` →
`getDiscoveredRoomVolumes()` / `getClinicalProgramRooms()` → the room selector.

- **FIRST_BROKEN_ROOM_DISCOVERY_SEAM** = `refreshModelSemantics()` in
  `spatialAssetOverlay.ts`. It did `cachedModelSemantics = await buildModelSemantics()`
  **unconditionally**, with no iModel ownership, no async-race guard, and no
  lifecycle status.
- **INITIAL_200_COUNT_SOURCE** = a real successful `buildModelSemantics()` against
  the clinic iModel (`cachedModelSemantics.rooms`, `LIMIT 200`).
- **ROOT_CAUSE** = `getIModel()` reads `IModelApp.viewManager?.selectedView?.iModel`,
  which is **transiently undefined** during viewer lifecycle events (remount /
  view reopen / focus change). When undefined, `buildModelSemantics()` returns
  `EMPTY_MODEL_SEMANTICS`. That NOT-READY empty result then **overwrote** the
  valid 200-room cache; `semanticsLoaded` stayed `true`, and the UI conflated
  `rooms.length === 0` with "no BIM spaces". Concurrent refresh callers (decorator
  one-shot, room loader, storey loader, diagnostics) could also let a stale empty
  completion clobber a good one.

The BIM never disappeared — this was a lifecycle/dataflow regression, exactly as
scoped.

## 3. The fix (minimum lifecycle/dataflow correction)

- **NEW** `frontend/src/components/spatial/roomDiscoveryLifecycle.ts` — pure,
  Bentley-free lifecycle + commit policy: explicit status
  `NOT_BOUND | LOADING | READY | ERROR`, iModel-owned `RoomDiscoveryState`, and
  `decideSemanticsCommit` which:
  - DISCARDS a completion from a non-active iModel (stale-iModel guard);
  - maps NOT_READY / FAILED to a KEEP-PRIOR decision (never erases a valid READY,
    non-empty cache) and surfaces LOADING/ERROR honestly;
  - ACCEPTS a legitimate current-iModel zero (`READY_EMPTY`) as READY-zero;
  - COMMITS a current-iModel non-empty result.
  Plus `beginRefreshState` (keeps a valid same-iModel cache READY while
  refreshing — no flicker to 0) and `roomSelectorLabel` (explicit per-status UI
  label).
- **MODIFIED** `frontend/src/components/spatial/bentleySpatialAdapter.ts` — added
  `getActiveSemanticsIModelId()` and `buildActiveModelSemantics()` which reports
  `{ bound, ranAgainstIModelId, semantics }` so the caller can distinguish a
  NOT_READY (unbound) refresh from a real result. `buildModelSemantics` itself is
  unchanged.
- **MODIFIED** `frontend/src/components/spatial/spatialAssetOverlay.ts` —
  `refreshModelSemantics()` now commits through `decideSemanticsCommit` with a
  single in-flight refresh (concurrent callers share it); tracks
  `roomDiscoveryState`; resets discovery to `NOT_BOUND` on a real iModel switch
  (never carries rooms across iModels); exposes `getRoomDiscoveryState`,
  `isSemanticsRefreshInFlight`, `getRoomDiscoveryUiStatus`, and a generic
  `diagnoseBimRoomDiscovery()` (§17).
- **MODIFIED** `frontend/src/components/spatial/ClinicalProgramControl.tsx` — the
  room loader reads the honest lifecycle status; the selector shows
  `Loading rooms…` / `Room discovery unavailable` / `Select a room (N)` /
  `Open the model to discover rooms` per status, and only reports "no valid rooms"
  on a true READY-zero. A bounded retry drives LOADING→READY (stops at READY,
  including READY-zero).

Clinical Program toggle, storey filter, camera mode, and developer mode do NOT
clear discovery (they never call the iModel-switch reset; the commit policy has no
input for them). Storey filtering is a view subset over `getDiscoveredRoomVolumes`
— it never mutates the base discovery authority. No eager meshing was introduced;
exact-mesh extraction stays lazy/on-demand/cached.

## 4. Offline verification (OFFLINE_VERIFIED)

- TYPECHECK = PASS.
- OFFLINE_TEST_FILE_COUNT = 37 · OFFLINE_TEST_COUNT = 666 · NEW_TEST_COUNT = 16 ·
  OFFLINE_TEST_REGRESSIONS = 0 (clean isolated run; not concurrent with the build).
- PRODUCTION_BUILD = PASS (only the known harmless INEFFECTIVE_DYNAMIC_IMPORT +
  chunk-size advisories) · CORE_FRONTEND_VERSION = 5.12.5.
- WORKER_ASSET_REAL = YES (`(()=>{"use strict";f`) · DRACO_WASM_ASSET_REAL = YES
  (`0061 736d`).

Lifecycle policy proven (`roomDiscoveryLifecycle.test.ts`): NOT_BOUND ≠ READY-zero;
LOADING ≠ READY-zero; READY-200 commits 200; legitimate READY-zero accepted; ERROR
≠ READY-zero; stale-iModel discarded; NOT_READY/FAILED cannot erase valid rooms
(the 200→0 fix); valid-empty vs not-ready distinguished; iModel switch binds
intentionally + late stale refresh discarded; same-iModel refresh updates
legitimately; toggle/camera/dev-mode independent of the commit policy; explicit
selector labels. The Build 1A generic-room + Uptake regression tests remain PASS.

## 5. Runtime verification (RUNTIME_VERIFIED)

- Dev server restarted cleanly (Vite ready, `http://localhost:3000/`).
- VIEWER_HTTP_STATUS = 200. Left running for manual acceptance.

## 6. Manual acceptance required (MANUAL_CONFIRMATION_REQUIRED)

The corrected first gate (§28) and the resumed Build 1A sequence (§29) are
browser-only and are NOT self-certified here. All remain
MANUAL_CONFIRMATION_REQUIRED, starting with reproducing the first gate: open the
clinic, Clinical Program ON, First Floor, wait for READY, confirm a non-zero
First-Floor room count, then exercise toggle / storey / camera / program-off-on
and confirm the count does not collapse to 0.

## 7. Git scope

New: `roomDiscoveryLifecycle.ts`, `roomDiscoveryLifecycle.test.ts`, this report
pair. Modified: `spatialAssetOverlay.ts`, `bentleySpatialAdapter.ts`,
`ClinicalProgramControl.tsx`. Build 1A files preserved. `frontend/.env` untouched.
Zero `.py` changed (equipment / routing / transport / simulation / OpenUSD /
NVIDIA / optimization / economics / What-If / Lockdown all untouched). Nothing
staged, committed, or pushed.

**CHECKPOINT = HOLD_FOR_BUILD_1A_MANUAL_ACCEPTANCE** (first gate re-test then the
rest). **NEXT_BUILD = BUILD_1B_COMPLETE_CLINICAL_PROGRAM_AND_EQUIPMENT_BINDING**
(not started).

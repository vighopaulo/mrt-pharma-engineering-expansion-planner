# MRT Pharma — Build 1A.3: Storey-Filter ↔ Clinical Room Collection Synchronization

**Continues:** Build 1A + 1A.1 + 1A.2 (uncommitted working tree). Does not restart 1A
or begin 1B. **Precheck:** HEAD = origin/main = `344d0289723e873c7a2974d0d8d295b38f44a6a3`,
divergence `0 0`; 1A/1A.1/1A.2 preserved; `frontend/.env` unstaged/excluded.
**Nature:** frontend storey-filter dataflow fix + pure/UI tests. No backend/domain
change; no Bentley writes; no stage/commit/push.

## 1. Preserved provenance (runtime evidence)

- 200 → 0 room-discovery lifecycle defect: **CLOSED** (Build 1A.1, manually
  retested). Not reopened.
- Build 1A.3 exposed seam (retained as provenance): base/All selector previously
  showed 200; **First Floor showed 153**; **Second Floor ALSO showed 153** while the
  viewer's visual storey filter changed. The equal 153/153 was NOT accepted as a
  verified count — `STOREY_FILTER_SYNCHRONIZATION_PRE_FIX = FAIL`.

## 2. Trace + root cause (source-grounded)

Chain: storey chip → `chooseStorey` → `setClinicalProgramActiveStorey` (sets
`programState.activeStoreyId`, calls `notifyProgram()`) → room storey identity
(`DiscoveredRoomVolume.storeyId`, resolved via `resolveRoomStoreyId` over
`programStoreyRanges`) → Clinical Program room selector options + count.

- `CANONICAL_STOREY_FILTER_OWNER` = `programState.activeStoreyId`
  (`setClinicalProgramActiveStorey`).
- `DUPLICATE_STOREY_STATE_FOUND` = NO (the control mirrors the canonical value as
  local `activeStoreyId` for rendering; it is not a second source of truth).
- `ROOM_STOREY_IDENTITY_SOURCE` = `DiscoveredRoomVolume.storeyId` (from
  `discoverRoomVolumes` → `resolveRoomStoreyIdSafe`/`resolveRoomStoreyId` over
  `programStoreyRanges`). `ROOM_STOREY_IDENTITY_COLLAPSE` = NO (rooms resolve to
  their own storey; the defect was in filtering/recompute, not identity).
- `CLINICAL_ROOM_FILTER_FUNCTION` (pre-fix) = none — the selector rendered
  `<option>` items directly from `getClinicalProgramRooms()` (the FULL unfiltered
  base ~200), and the selector *count label* came from `getRoomDiscoveryUiStatus`
  but was only recomputed inside `refreshRooms`, which is driven by the discovery
  effect that STOPS at READY.
- `FIRST_BROKEN_STOREY_FILTER_SEAM` = the room-selector options + count in
  `ClinicalProgramControl` were not recomputed on `activeStoreyId` change, and the
  rendered options were never storey-filtered at all.
- `ROOT_CAUSE` = the selector count froze at the First-Floor value (153) captured
  during discovery and never recomputed when the storey changed to Second Floor;
  separately, `getRoomDiscoveryUiStatus` filtered with `!r.storeyId || …`, which
  would have leaked unresolved-storey rooms into every storey.

## 3. The fix (minimum synchronization correction)

- **NEW pure seam (`bimRoomVolumeRegistry.ts`)**: `filterDiscoveredRoomsByStorey(rooms,
  activeStorey)` — `undefined` (All) returns a COPY of the base; a specific storey
  returns ONLY rooms whose resolved `storeyId` matches; an unresolved-storey room
  appears ONLY under All (never padding a specific storey). Plus `countRoomsByStorey`
  (all / unresolved / per-storey). Never mutates input.
- **`spatialAssetOverlay.ts`**: `getRoomDiscoveryUiStatus` now uses the pure filter
  (dropping the unresolved-room leak); added `getDiscoveredRoomOptions()`
  (storey-filtered discovered rooms for the selector) and
  `isSelectedRoomOutsideActiveStorey()`; `diagnoseBimRoomDiscovery` extended with
  `BASE_DISCOVERED_ROOM_COUNT`, `ACTIVE_STOREY_FILTER`, `FILTERED_ROOM_COUNT`,
  bounded per-storey counts + sample labels, and `SELECTED_ROOM_OUTSIDE_ACTIVE_STOREY`.
- **`ClinicalProgramControl.tsx`**: added `applyRoomOptions(o)` which builds the
  selector options from `getDiscoveredRoomOptions()` (storey-filtered) and sets the
  count/label from `getRoomDiscoveryUiStatus`. It is called on EVERY program
  notification inside `sync()` — and a storey-filter change calls `notifyProgram()`
  — so the selector recomputes immediately from the immutable base discovery. The
  out-of-filter policy clears the UI selection when the selected room is not in the
  active storey (`setClinicalProgramSelectedSpace(undefined)`) WITHOUT deleting the
  assignment or planning volume.

Base discovery (`cachedModelSemantics.rooms` / the generic registry) is never
mutated by a storey button. Storey change recomputes the subset immediately (no
reload / program toggle / dev mode / rediscovery). The Build 1A.1 lifecycle fix and
Build 1A.2 exact-geometry diagnostics/status are untouched.

## 4. Offline verification (OFFLINE_VERIFIED)

- TYPECHECK = PASS.
- OFFLINE_TEST_FILE_COUNT = 41 · OFFLINE_TEST_COUNT = 702 · NEW_TEST_COUNT = 19
  (13 pure + 6 UI) · OFFLINE_TEST_REGRESSIONS = 0 (clean isolated run; not
  concurrent with the build).
- PRODUCTION_BUILD = PASS (known harmless advisories only) · CORE_FRONTEND_VERSION
  = 5.12.5.
- WORKER_ASSET_REAL = YES (`(()=>{"use strict";f`) · DRACO_WASM_ASSET_REAL = YES
  (`0061 736d`).

Pure tests (§23) prove: All = base; each storey returns only its own rooms;
unresolved rooms only under All; **equal counts do not imply equal membership**
(the real acceptance criterion — First/Second may both be 2 but with distinct ids);
filtering never mutates the base; deterministic transitions; explicit unresolved
policy (counts bucket + non-existent storey → empty); iModel scoped; pure function
of (rooms, activeStorey) only. UI tests (§24) prove: All → 3; First Floor → 2
(Second-Floor room absent); **Second Floor → 1, a DISTINCT count (not stuck at
First's)**; back to All → 3; and storey filtering does not change the assignment
count.

## 5. Runtime verification (RUNTIME_VERIFIED)

- Dev server restarted cleanly (Vite ready, `http://localhost:3000/`).
- VIEWER_HTTP_STATUS = 200. Left running for manual acceptance.

## 6. Manual acceptance required (MANUAL_CONFIRMATION_REQUIRED)

Browser-only, not self-certified: the storey matrix counts (§30), First/Second
membership proof (§31), filter roundtrip (§32), and out-of-filter selected-room
policy (§33). After those pass, resume Build 1A.2 exact-geometry acceptance (§34).

## 7. Git scope

Modified (frontend only): `bimRoomVolumeRegistry.ts`, `spatialAssetOverlay.ts`,
`ClinicalProgramControl.tsx`. New: this report pair + Build 1A.3 tests. Build
1A/1A.1/1A.2 files preserved. `frontend/.env` untouched. Zero `.py` changed
(equipment / routing / transport / simulation / OpenUSD / NVIDIA / optimization /
economics / What-If / Lockdown untouched). Nothing staged, committed, or pushed.

**CHECKPOINT = HOLD_FOR_BUILD_1A3_MANUAL_ACCEPTANCE.**
**NEXT_BUILD = BUILD_1B_COMPLETE_CLINICAL_PROGRAM_AND_EQUIPMENT_BINDING** (not started).

# MRT Pharma — Build 1A.2: Generic Room Diagnostic + Exact-Geometry Inspection Wiring

**Continues:** Build 1A + Build 1A.1 (uncommitted working tree). Does not restart 1A
or begin 1B. **Precheck:** HEAD = origin/main = `344d0289723e873c7a2974d0d8d295b38f44a6a3`,
divergence `0 0`; 1A + 1A.1 work preserved; `frontend/.env` unstaged/excluded.
**Nature:** frontend diagnostic-UI wiring + geometry-status synchronization + tests.
No backend/domain change; no Bentley writes; no stage/commit/push.

## 1. Accepted prior result + preserved provenance

- Build 1A.1 room-discovery lifecycle regression: **PASS** (manual). The former
  200 → 0 collapse now survives dropdown open/close, Developer ON/OFF,
  Planning↔Bird's-eye, First Floor↔All↔First Floor, and Clinical Program OFF↔ON.
  `ROOM_DISCOVERY_LIFECYCLE_REGRESSION = CLOSED`. Not reopened.
- Build 1A.2 exposed seam (provenance retained): with `1DC1 WAITING / ACTIVITY AREA`
  (`0x200000001f6`) selected, `Show Room Volume` rendered a camera-invariant shell,
  but the panel still showed **"BIM range approximation"** AND the live Developer
  Diagnostics panel did **not** expose the generic `diagnoseSelectedRoomVolume` /
  `diagnoseBimRoomDiscovery` entrypoints (only Uptake-specific/older ones).

## 2. Trace results (source-grounded)

- `GENERIC_SELECTED_ROOM_DIAGNOSTIC_SOURCE_EXISTS` = YES
  (`spatialAssetOverlay.diagnoseSelectedRoomVolume`).
- `GENERIC_ROOM_DISCOVERY_DIAGNOSTIC_SOURCE_EXISTS` = YES
  (`spatialAssetOverlay.diagnoseBimRoomDiscovery`).
- `GENERIC_DIAGNOSTIC_UI_WIRING_STATUS_PRE_FIX` = NOT_WIRED — the functions
  existed and were exported, but `AuditDiagnosticsPanel.tsx` rendered no buttons
  for them.
- **Show Room Volume chain (pre-fix):** `setClinicalProgramShowRoomVolume(true)`
  only flipped a flag + `notifyProgram()`; it did NOT call
  `ensureAuthoritativeRoomFootprint` for the selected room. The decorator's
  `getRoomVolumeMesh` reads `authoritativeFootprints` only if already extracted.
  `CURRENT_ROOM_VOLUME_RENDER_SOURCE_PRE_FIX` = C (BIM range approximation) for a
  room whose exact mesh had not been lazily requested.
- **Geometry-status defect:** `getClinicalProgramRoomGeometryQuality` computed the
  quality ONLY from the range-based `resolveClinicalProgramFacilityAnchor`; it
  never consulted the exact-mesh cache, so it stayed `BIM_RANGE_APPROXIMATION`
  even after extraction. The control also read the quality only once at selection,
  not reactively.

## 3. The fix (minimum wiring/dataflow correction)

- **MODIFIED `AuditDiagnosticsPanel.tsx`** — added `DIAGNOSE BIM ROOM DISCOVERY`
  and `DIAGNOSE SELECTED ROOM VOLUME` buttons using the proven
  synchronous-pointerdown/click pattern (immediate `*_START_RECEIVED` + CLICK
  counter before any async). All Uptake regression diagnostics are preserved.
- **MODIFIED `spatialAssetOverlay.ts`**:
  - `setClinicalProgramSelectedSpace(id)` and `setClinicalProgramShowRoomVolume(true)`
    now lazily `ensureAuthoritativeRoomFootprint(selected)` — on-demand, idempotent,
    cached (never eager/all-rooms). Its async completion calls `notifyProgram()`.
  - `getClinicalProgramRoomGeometryQuality(roomId)` now passes the cached
    authoritative outer loop (when `ok`) as the `exactBoundary` to
    `resolveClinicalProgramFacilityAnchor`, so the reported quality becomes
    `EXACT_ROOM_BOUNDARY` when an exact mesh is cached and stays an honest range
    fallback otherwise.
  - The generic `diagnoseSelectedRoomVolume()` and `diagnoseBimRoomDiscovery()`
    entrypoints (already added in 1A/1A.1) are now reachable from the live panel;
    `diagnoseSelectedRoomVolume` defaults to the CURRENTLY selected room (falls
    back to the persisted assignment only when nothing is selected) — never an
    Uptake substitution when another room is selected.
- **MODIFIED `ClinicalProgramControl.tsx`** — the program subscription `sync()`
  re-reads `getClinicalProgramRoomGeometryQuality(selectedSpaceId)` on EVERY
  program notification, so async exact-mesh completion updates "Spatial geometry"
  reactively (no reselect / reload / dev-mode toggle needed).
- **MODIFIED `bentleySpatialAdapter.ts`** — unchanged from 1A.1 (the additive
  `getActiveSemanticsIModelId` / `buildActiveModelSemantics` helpers) — shown here
  only because it is part of the current diff.

Exact extraction reuses the accepted `ensureAuthoritativeRoomFootprint` →
`authoritativeRoomGeometryProbe.extractAuthoritativeRoomGeometry`
(`generateElementMeshes` / `readElementMeshes`) path with the canonical product
viewport resolver — no second extractor. Range fallback preserved; a range never
masquerades as exact. No assignment or planning volume is created by inspection;
no Bentley write. The 1A.1 lifecycle fix is untouched.

## 4. Offline verification (OFFLINE_VERIFIED)

- TYPECHECK = PASS.
- OFFLINE_TEST_FILE_COUNT = 39 · OFFLINE_TEST_COUNT = 683 · NEW_TEST_COUNT = 17
  (11 pure + 6 UI) · OFFLINE_TEST_REGRESSIONS = 0 (clean isolated run; not
  concurrent with the build).
- PRODUCTION_BUILD = PASS (only the known harmless advisories) ·
  CORE_FRONTEND_VERSION = 5.12.5.
- WORKER_ASSET_REAL = YES (`(()=>{"use strict";f`) · DRACO_WASM_ASSET_REAL = YES
  (`0061 736d`).

Pure tests (§20) prove: diagnostic targets the SELECTED room; never substitutes
Uptake; exact-cached → EXACT authority; range-only → RANGE approximation; nothing
→ NOT_AVAILABLE; range never promoted; counts come from the selected room's cache;
absence remains absence; inspection creates no assignment/volume; **async cache
update flips the same room's authority RANGE → EXACT** (the product-status path);
iModel scoped. UI tests (§21) prove: both generic buttons exist; the Uptake
diagnostics are preserved; clicking DIAGNOSE SELECTED ROOM VOLUME invokes the
generic (no forced Uptake id); the synchronous CLICK counter fires.

## 5. Runtime verification (RUNTIME_VERIFIED)

- Dev server restarted cleanly (Vite ready, `http://localhost:3000/`).
- VIEWER_HTTP_STATUS = 200. Left running for manual acceptance.

## 6. Manual acceptance required (MANUAL_CONFIRMATION_REQUIRED)

Browser-only, not self-certified: diagnostic visibility (§27), selected-room
identity `0x200000001f6` (§28), exact geometry after Show Room Volume (§29),
product-panel status synchronization (§30), and no-side-effects (§32). Camera
invariance for the unassigned room volume (§31) was already accepted in the
current live evidence and is carried as PASS.

## 7. Git scope

Modified (frontend only): `AuditDiagnosticsPanel.tsx`, `ClinicalProgramControl.tsx`,
`spatialAssetOverlay.ts`, `bentleySpatialAdapter.ts`. New: this report pair +
Build 1A.2 tests. Build 1A + 1A.1 files preserved. `frontend/.env` untouched. Zero
`.py` changed (equipment / routing / transport / simulation / OpenUSD / NVIDIA /
optimization / economics / What-If / Lockdown untouched). Nothing staged,
committed, or pushed.

**CHECKPOINT = HOLD_FOR_BUILD_1A2_MANUAL_ACCEPTANCE.**
**NEXT_BUILD = BUILD_1B_COMPLETE_CLINICAL_PROGRAM_AND_EQUIPMENT_BINDING** (not started).

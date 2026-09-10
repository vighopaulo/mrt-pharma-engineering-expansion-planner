# MRT Pharma — Build 1A: Generic BIM Room-Volume Activation + Editable Clinical Planning Volume Generalization

**Master workstream:** BUILD 1 — Complete Clinical Program + Equipment Composition.
**This build:** BUILD 1A — generalize the accepted Uptake 01 spatial proof into a
GENERIC room-volume discovery + activation contract for ALL valid BIM rooms.
**Checkpoint (precheck):** HEAD = origin/main = `344d0289723e873c7a2974d0d8d295b38f44a6a3`,
divergence `0 0`. Working tree clean except the intentionally-unstaged `frontend/.env`.
**Nature:** frontend product-code generalization + offline tests. No backend/domain
change; no Bentley writes; no stage/commit/push.

Every claim is tagged **OFFLINE_VERIFIED** (proven by typecheck/tests/build here),
**RUNTIME_VERIFIED** (proven by the dev-server smoke check here), or
**MANUAL_CONFIRMATION_REQUIRED** (a browser step the user must perform). No
unperformed browser test is marked PASS.

---

## 1. What changed (authorized scope only)

- **NEW** `frontend/src/components/spatial/bimRoomVolumeRegistry.ts` — pure,
  Bentley-free GENERIC room-volume authority. Composes discovered
  `SpatialRoomReference`s + caller-supplied lazy-mesh-cache facts into a bounded
  `DiscoveredRoomVolume` model with explicit geometry quality, a discovery
  summary, and a GENERIC selected-room diagnostic. Never auto-creates a planning
  volume or an assignment; never mutates Bentley.
  - `discoverRoomVolumes`, `summarizeRoomVolumeDiscovery`,
    `resolveRoomVolumeGeometryQuality`, `resolveRoomAuthorityClass`,
    `buildSelectedRoomVolumeDiagnostic`, `formatSelectedRoomVolumeDiagnostic`,
    `RoomMeshCacheFacts` / `NO_MESH_CACHE`.
- **MODIFIED** `frontend/src/components/spatial/spatialAssetOverlay.ts` — wired the
  generic runtime entrypoints on top of the accepted architecture (reusing
  `cachedModelSemantics.rooms`, the `authoritativeFootprints` lazy cache,
  `programStoreyRanges`, and the existing assignment/planning-volume state):
  - `getDiscoveredRoomVolumes()`, `getRoomVolumeDiscoverySummary()`,
    `inspectRoomVolume(bimSpaceId)` (lazy per-room extraction), and
    `diagnoseSelectedRoomVolume(bimSpaceId?)` (generic, defaults to the selected
    space; falls back to the persisted assignment).
  - Helpers `roomMeshCacheFacts` / `allRoomMeshCacheFacts` translate the on-demand
    `authoritativeFootprints` cache into the pure registry's fact shape.
- **NEW** `frontend/src/tests/build1aGenericBimRoomVolume.test.ts` — 31 offline
  domain tests covering the 18 required properties.

No product source changed outside `frontend/`. **Zero `.py` files changed** —
equipment, routing, transport, simulation, OpenUSD/NVIDIA, optimization,
economics, What-If/Lockdown are all untouched.

## 2. Generalization design (extends the accepted architecture; no second store)

The accepted proof already had the exact-geometry half of the chain
(`authoritativeRoomGeometryProbe.extractAuthoritativeRoomGeometry` →
`authoritativeRoomFootprint` → the on-demand `authoritativeFootprints` cache) and
a generic assignment (`clinicalProgram.assignClinicalFunction` accepts any
`bimSpaceId`) and a generic parent-derived seed
(`clinicalPlanningVolume.seedPrismParamsFromParent`, wired through
`suggestPlanningVolumeSeedForParent`). Build 1A adds the DISCOVERY + volume-aware
+ inspection + generic-diagnostic layer WITHOUT inventing a second room-geometry
store:

- **Discovery source of truth:** `cachedModelSemantics.rooms` (iModel-scoped;
  cleared on BIM switch). Room identity authority = `bimSpaceId` (`roomId`).
- **Authoritative room-volume registry:** the existing `authoritativeFootprints`
  map (iModel + bimSpaceId scoped, read-only vs Bentley, camera-independent,
  lazy). Build 1A only READS it; extraction stays on-demand.
- **Geometry quality (explicit):** `EXACT_SPACE_GEOMETRY` (only when a cached
  successful mesh exists) / `RANGE_ONLY_APPROXIMATION` / `ANCHOR_ONLY` /
  `NOT_AVAILABLE`. A range is NEVER silently promoted to exact.

## 3. Offline verification (OFFLINE_VERIFIED)

- **TYPECHECK** = PASS (`tsc -b`, exit 0).
- **OFFLINE_TEST_FILE_COUNT** = 36 · **OFFLINE_TEST_COUNT** = 650 ·
  **NEW_TEST_COUNT** = 31 · **OFFLINE_TEST_REGRESSIONS** = 0 (clean isolated run;
  tests NOT run concurrently with the build).
- **PRODUCTION_BUILD** = PASS (`tsc -b && vite build`; only the known harmless
  `INEFFECTIVE_DYNAMIC_IMPORT` + chunk-size advisories).
- **CORE_FRONTEND_VERSION** = 5.12.5.
- **WORKER_ASSET_REAL** = YES (`dist/scripts/parse-imdl-worker.js` head
  `(()=>{"use strict";f`).
- **DRACO_WASM_ASSET_REAL** = YES (`dist/scripts/draco_decoder.wasm` magic
  `0061 736d`).

### Domain properties proven (§35.1–18)

1. discovery returns stable BIM identities (sorted, deterministic) — PASS.
2. discovery is iModel scoped (every record tagged with active iModelId) — PASS.
3. discovery does NOT auto-create planning volumes (200 rooms → 0 volumes / 0
   assignments) — PASS.
4. exact vs range-only geometry-quality stays distinct; range never promoted —
   PASS.
5. selected-parent seed uses the selected room's footprint centroid — PASS.
6. seed is finite and truly 3D (`zHigh>zLow`, positive w/d) — PASS.
7. seed does NOT reuse Uptake 01 coordinates for another room — PASS.
8. one assignment owns zero-or-one planning volume (re-define replaces) — PASS.
9. planning volumes independently editable — PASS.
10. per-parent containment identity preserved — PASS.
11. cross-parent containment rejected — PASS.
12. visibility isolation — PASS.
13. lifecycle isolation (+ lock gate requires containment PASS) — PASS.
14. persistence roundtrip — PASS.
15. BIM-switch (iModel) isolation — PASS.
16. lazy extraction policy (registry reflects cache, never triggers eager mesh) —
    PASS.
17. camera invariance (world prism = pure function of params) — PASS.
18. Uptake 01 regression baseline constants unchanged; diagnostic flags baseline —
    PASS.

Also: zero-sample ≠ FAIL (`NOT_EVALUATED`), discovery summary counts, and
delete DRAFT-vs-LOCKED semantics — PASS.

## 4. Runtime verification (RUNTIME_VERIFIED)

- Dev server restarted cleanly (Vite ready on `http://localhost:3000/`).
- **VIEWER_HTTP_STATUS** = 200 (`/viewer`). Left running for manual acceptance.

## 5. Preserved invariants

- `BIM_PARENT_GEOMETRY_MUTABLE` = NO · `BENTLEY_ROOM_RENAMED` = NO ·
  `BENTLEY_WRITE_API_CALL_COUNT` = 0 · `SCREEN_SPACE_PHYSICAL_AUTHORITY` = NO.
- `GENERIC_ROOM_VOLUME_PATH_UPTAKE_SPECIFIC` = NO (Uptake IDs/coords remain only
  in the reconstruction helper, the persistence diagnostic, and as a read-only
  regression FLAG in the generic diagnostic).
- `UPTAKE_01_REGRESSION_BASELINE_PRESERVED` = YES (constants untouched; not
  reconstructed).
- `AUTO_CREATE_PLANNING_VOLUME_FOR_EVERY_ROOM` = NO ·
  `ROOM_DISCOVERY_AND_PLANNING_ACTIVATION_SEPARATED` = YES.
- `FULL_PET_DEPARTMENT_COMPLETE` = NO (Build 1A generalizes activation only).

## 6. Manual acceptance required (MANUAL_CONFIRMATION_REQUIRED)

These are browser-only steps the agent cannot self-certify. All are pending:
room discovery (§41), unassigned room-volume inspection (§42), lazy extraction
(§43), new-room activation (§44), parent-derived volume seed (§45), true-3D
editing (§46), containment transition (§47), camera invariance (§48), multi-room
independence (§49), Uptake 01 regression (§50), reload restore (§51), BIM-switch
isolation (§52), and discovery usability/performance (§53).

## 7. Git scope

Changed: `frontend/src/components/spatial/bimRoomVolumeRegistry.ts` (new),
`frontend/src/components/spatial/spatialAssetOverlay.ts` (modified),
`frontend/src/tests/build1aGenericBimRoomVolume.test.ts` (new). `frontend/.env`
remains the pre-existing unstaged, excluded, untouched file. Nothing staged,
committed, or pushed.

**CHECKPOINT = HOLD_FOR_BUILD_1A_MANUAL_ACCEPTANCE.**
**NEXT_BUILD = BUILD_1B_COMPLETE_CLINICAL_PROGRAM_AND_EQUIPMENT_BINDING** (not started).

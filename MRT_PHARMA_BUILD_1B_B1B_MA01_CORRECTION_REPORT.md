# MRT PHARMA — Build 1B Manual-Acceptance Correction Report

## B1B-MA-01 — Parent-Derived ClinicalPlanningVolume Containment Failure After Candidate-Room Acceptance

- **Status:** IMPLEMENTED / AUTOMATED GREEN / **MANUAL RETEST REQUIRED**
- **manual_acceptance:** `PENDING`
- **Build 1B completion:** NOT asserted by this report (manual retest gates completion).
- **Baseline commit (HEAD == origin/main):** `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` (branch `main`)
- **Scope:** correction only. No Build 1A/1B restart, no redesign, no Build 2, no scope expansion.

---

## 1. Defect (reproduced)

Manual path: **2D18 TECH. OFFICE → PET/CT Scanner Room → “Use This Room”**.

Accepting the candidate room reparents the clinical function and regenerates its
`ClinicalPlanningVolume`. The regenerated volume reported **containment: FAIL**
against its **own** newly-assigned parent (observed as “PET/CT 01 — OUTSIDE PARENT,
containment: FAIL”). Because the equipment safety gate correctly refuses to place
equipment into a volume that is not contained by a valid parent, the user was left
with a red warning and **no usable in-product recovery path**.

The FAIL was **honest** (the geometry really did protrude). The bug was in how the
parent-derived volume was **seeded**, not in the containment engine.

---

## 2. Root cause (proven from source, not guessed)

`seedPrismParamsFromParent` (`frontend/src/components/spatial/clinicalPlanningVolume.ts`)
built an **axis-aligned** prism sized to ~50% of the footprint **AABB**, centered on
the **vertex mean** of the footprint.

For an axis-aligned rectangular room this happens to sit inside. For a **rotated or
irregular** room (the real 2D18 TECH. OFFICE condition) that heuristic breaks in two
compounding ways:

1. **Wrong center for non-convex / offset footprints.** The vertex mean (and even the
   AABB center) can fall outside the actual polygon, so the seed box is anchored at a
   point that is not guaranteed interior.
2. **Wrong size/orientation for rotated footprints.** A 50%-of-AABB axis-aligned box
   over a rotated polygon has corners that protrude past the rotated walls.

Result: the parent-derived volume genuinely failed containment against its own parent
mesh. This is the exact `false`/protrusion the reproduction test reconstructs.

A **second, residual** protrusion existed in the fix’s own containment pre-check
(`boxContainedInPolygon`): it verified a box **shrunk by** the wall-clearance inset,
while the seed then **built the full-size** box — so the built corners could sit up to
`inset` beyond what was verified as interior. Corrected (see §3).

---

## 3. Correction (minimum, root-cause)

All changes confined to two source files (plus one new test file). No containment
tolerance was loosened, no PASS was fabricated, no FAIL was suppressed, and the
equipment safety gate is unchanged.

### `frontend/src/components/spatial/clinicalPlanningVolume.ts`
- `seedPrismParamsFromParent` now optionally accepts `holes` and `interiorAnchor`.
- **Center** on a **proven-interior anchor** when supplied (from
  `resolveRoomInteriorAnchor`, the guaranteed-interior largest-triangle centroid);
  else the AABB center; else the vertex mean.
- **Shrink-to-fit:** starting at ~25% of the parent XY extent, halve-ish (×0.7, up to
  12 bounded steps) until every sampled corner + edge-midpoint + center of the box —
  **plus** the wall-clearance inset — lies inside the outer polygon **and** outside any
  hole. Converges to a **guaranteed-contained** box whenever a usable polygon
  (≥ 3 points) exists.
- **`boxContainedInPolygon` corrected** to test the box at `halfExtent + inset` (a
  margin **larger** than the built box) so the built box is strictly interior with
  clearance — eliminating the residual protrusion described in §2(2).
- **Z contract preserved (Build 1A):** the seed **sits on the parent floor**
  (`zLow == room zLow`) and does **not** inset Z. The containment ray is horizontal
  (+X); a sample coplanar with the floor/ceiling is not a false crossing (in-plane
  triangles have ~0 determinant and are skipped), and the horizontal ray resolves
  inside/outside via the side walls. Insetting Z would have pushed **equipment** off
  the floor (equipment `zBase` is derived from this seed’s `zLow`) — so it was
  correctly **not** applied.
- Exported `WALL_CLEARANCE_INSET = 0.25` (used as the clearance margin).

### `frontend/src/components/spatial/spatialAssetOverlay.ts`
- `suggestPlanningVolumeSeedForParent` now passes `holes: parent.holes` and
  `interiorAnchor: parent.interiorAnchor` into the seed.
- `reparentClinicalFunction` now sets
  `programState.selectedSpaceId = plan.newParent.bimSpaceId` before notifying the
  program, so the **new parent** is selected in the normal product UI and the existing
  Build 1A.4 recovery controls (Restore Valid Position / Reset to Parent-Derived) are
  reachable for the reparented volume.

---

## 4. Geometry authority (exact vs approximate) — preserved

- The seed uses the **authoritative footprint** (`authoritativeRoomFootprint.ts`:
  outer loop, holes, floor Z, guaranteed-interior anchor) when exact geometry is
  available → contained, honest **PASS**.
- When only an **approximate** parent is available (no closed exact mesh),
  `getClinicalVolumeContainment` returns **NOT_EVALUATED** (unchanged). The seed still
  produces a bounded, centered box, but the status is **not** upgraded to PASS.
- A footprint with `< 3` points cannot prove containment; the seed falls back to the
  bounded default sizing centered on the point’s own coordinates (never origin), and
  the caller treats the room as approximate. The **exact-vs-approximate** and
  **FAIL-vs-NOT_EVALUATED** distinctions are intact.

---

## 5. Before / after containment (same reparent chain)

| Condition | Before fix | After fix |
| --- | --- | --- |
| Rotated rectangular parent (2D18-like) | **FAIL** (box protrudes past rotated walls) | **PASS** (contained, 0 failed samples) |
| Axis-aligned rectangular parent | PASS | PASS |
| L-shaped / irregular parent | FAIL / fragile | **PASS** (centered on interior anchor, shrunk to fit) |
| Volume deliberately placed outside parent | FAIL | **FAIL** (real failure preserved) |
| Approximate parent (no exact mesh) | NOT_EVALUATED | NOT_EVALUATED (unchanged) |

---

## 6. Recovery UX (reachable in normal product UI)

No new editor was invented. On reparent, the new parent space is selected in
`ClinicalProgramControl`, exposing the existing **Build 1A.4** controls:
- **Restore Valid Position** — restores last-known-valid geometry, else the
  parent-derived seed.
- **Reset to Parent-Derived** — regenerates the corrected seed for the current parent.
- The per-volume warning still **identifies the room** (not color-only), Lock stays
  disabled with a visible reason while invalid, and the equipment gate still refuses
  placement into a non-contained parent. The correction makes the **default**
  parent-derived state valid so recovery is rarely needed; when a volume is genuinely
  invalid, the honest FAIL and the recovery controls remain.

---

## 7. Equipment safety gate & canonical identity — unchanged

- The containment engine (`validatePlanningVolumeContainment`,
  `getClinicalVolumeContainment`) and the equipment placement gate are unmodified.
- An invalid parent still disables equipment placement.
- GE HealthCare Discovery MI exact identity vs proxy envelope, and all canonical
  equipment/cyclotron/generator/scanner authority, are untouched.

---

## 8. Tests

New reproduction + supporting file: `frontend/src/tests/build1bB1bMa01ReparentContainment.test.ts`
(8 tests) — exercises the **real** seed → `extrudeClosedMesh` →
`validatePlanningVolumeContainment` chain:
- Rotated parent: corrected seed **contained** (0 failed samples).
- Explicit reconstruction of the **old** 50%-AABB-on-vertex-mean heuristic → **not
  contained** (documents the defect).
- Axis-aligned parent → contained; L-shaped parent → contained.
- Z bounds: seed sits on the floor, capped by room height.
- Seed center inside the actual polygon (not origin) for a rotated room.
- `< 3` points → bounded approximate fallback centered on own coords.
- Deliberately-outside volume → **still FAIL** (real failure preserved).

No existing tests were weakened or deleted.

---

## 9. Regression counts & verification

| Check | Baseline | After fix |
| --- | --- | --- |
| Frontend test files | 61 | **62** (+1) |
| Frontend tests | 1010 | **1018** (+8) |
| Failures | 0 | **0** |
| TypeScript `tsc -b` | PASS | **PASS** |
| Production `npm run build` | PASS | **PASS** |
| Worker `dist/scripts/parse-imdl-worker.js` head | `(()=>{"use strict";f` | **`(()=>{"use strict";f`** |
| WASM `dist/scripts/draco_decoder.wasm` magic | `0061 736d` | **`0061 736d`** |
| `@itwin/core-frontend` version | 5.12.5 | **5.12.5** |
| Dev server `/viewer` | HTTP 200 | **HTTP 200** (clean restart, port 3000) |

Note: during iteration a Z-inset experiment temporarily broke 3 pre-existing seed
tests (equipment floor-aware `zBase`, seed `zLow == 0`, seed-in-own-mesh). The inset
was removed (§3, Z contract preserved); all three returned to green in the final run.

---

## 10. Files changed (B1B-MA-01)

- `frontend/src/components/spatial/clinicalPlanningVolume.ts` (seed + `boxContainedInPolygon` correction)
- `frontend/src/components/spatial/spatialAssetOverlay.ts` (seed inputs + reparent selects new parent)
- `frontend/src/tests/build1bB1bMa01ReparentContainment.test.ts` (new)

Out of scope / untouched by this correction: no `.py` / closed-domain changes
(canonical equipment, production physics, radionuclide, four-arch optimizer,
transport, economics, patient-demand, operations, What-If/Lockdown, OpenUSD, NVIDIA).
`frontend/.env` was left as-is (`M`, unstaged — pre-existing, not modified here).

---

## 11. Limitations

- The shrink-to-fit seed is a **conservative axis-aligned** box; for extreme aspect
  ratios (very long, thin rotated rooms) the contained seed may be smaller than a
  human might hand-tune. It is guaranteed contained, and the user can grow/rotate it
  via the existing editor (containment re-evaluates live). A future enhancement could
  seed an oriented (non-zero-yaw) box aligned to the dominant wall direction.
- Containment sampling is bounded (corners + edge midpoints + center). It is robust for
  the planning use case but is not an exact solid-intersection proof.
- Rooms with only approximate geometry remain **NOT_EVALUATED** by design.

---

## 12. Manual retest instructions (required before Build 1B is marked complete)

1. Load the MRTway Medical Clinic Demo; ensure `/viewer` shows the scene.
2. Enter the clinical program flow; open the candidate-room picker for the PET/CT
   Scanner Room clinical function.
3. Choose **2D18 TECH. OFFICE** as the candidate and click **Use This Room**.
4. Confirm the regenerated **PET/CT** planning volume shows **containment: PASS**
   (no “OUTSIDE PARENT” warning) and that the **new parent is selected** in the panel.
5. Confirm **equipment placement is enabled** for the contained volume and that
   canonical **Discovery MI** identity is preserved (vs proxy envelope).
6. Negative check: drag the volume outside its parent → confirm it **honestly FAILs**,
   Lock is disabled with a reason, and **Restore Valid Position / Reset to
   Parent-Derived** recover it.

Record the outcome and set `manual_acceptance` accordingly. This report keeps
`manual_acceptance = PENDING` and does **not** mark Build 1B complete.

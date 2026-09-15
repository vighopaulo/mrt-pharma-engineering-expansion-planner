# EVI-MA-04 — Standardize Medium-LOD Cyclotron Visual + Adjacent MRT Radiopharmacy Vestibule

**Status:** implementation complete · `manual_acceptance = PENDING` (do not self-accept)
**Scope:** the final bounded equipment-visual refinement before transport routing. Replaces ONLY the representative cyclotron visual recipe, adds an adjacent MRT Radiopharmacy Vestibule recipe + pure adjacency/placement logic, and corrects the selection render. The existing equipment architecture (canonical identity, room placement, persistence, selection, Hide/Show, Lock/Unlock, Delete, collision reservation, 2D marker) is unchanged.

---

## 1. What changed (honest summary)

1. **Medium-LOD cyclotron visual — `GENERIC_MEDICAL_CYCLOTRON_V2`.** The representative cyclotron went from a ~3-primitive proxy (body + shielding + service cabinet) to a **recognizable 27-primitive machine**. Canonical `CYCLOTRON` equipment now resolves to `GENERIC_MEDICAL_CYCLOTRON_V2` at every resolution seam (canonical class, asset family, geometry id).
2. **Adjacent MRT Radiopharmacy Vestibule — `GENERIC_MRT_RADIOPHARMACY_VESTIBULE_V1`.** A compact wall-adjacent controlled-transfer cabinet recipe, plus **pure** adjacency-candidate and placement logic that seeds the vestibule pose in a *different* adjoining room, wall-adjacent and non-overlapping.
3. **Selection render fix.** Selecting equipment no longer repaints the whole machine opaque cyan. Per-part materials are always retained; selection now applies only a **thin outline** (`EQUIPMENT_SELECTION_OUTLINE = [90, 200, 220]`) plus the pre-existing translucent containment envelope as the selection cue.
4. **Material palette by part role.** A single shared `EQUIPMENT_PART_COLOR` map in `equipmentGeometry.ts` now covers every V2 and vestibule part role and is imported by both decorators (no duplicated map to drift).

> **Honesty note:** live 3D appearance cannot be verified headlessly. This report proves the recipe, mapping, selection decision, adjacency, tests, typecheck, production build and `/viewer` HTTP status. Visual acceptance of the rendered machine is the manual step below.

---

## 2. Representative-family architecture (unchanged principle)

Canonical engineering identity and the representative *visual* are separate concerns:

- **Canonical identity** (e.g. `IBA_CYCLONE_KIUBE`, `GE_PETTRACE_890`) — manufacturer, model, calibrated envelope, provenance. **Never** mutated by visual resolution.
- **Visual family** — a generic, recognizable recipe that many canonical models share. `GENERIC_MEDICAL_CYCLOTRON_V2` is representative geometry, **NOT** manufacturer CAD. It scales parametrically from the instance's calibrated envelope pose.

Resolution seams (all now → V2 for cyclotrons):

| Seam | Function | Result |
|---|---|---|
| Canonical class | `resolveVisualFamilyForCanonical({ canonicalClass: 'CYCLOTRON' })` | `GENERIC_MEDICAL_CYCLOTRON_V2` |
| Asset family | `resolveVisualFamilyForAssetFamily('CYCLOTRON')` | `GENERIC_MEDICAL_CYCLOTRON_V2` |
| Geometry id | `resolveVisualFamilyForGeometryId(id.includes('CYCLOTRON'))` | `GENERIC_MEDICAL_CYCLOTRON_V2` |
| Asset family | `resolveVisualFamilyForAssetFamily('MRT_RADIOPHARMACY_VESTIBULE')` | `GENERIC_MRT_RADIOPHARMACY_VESTIBULE_V1` |

`GENERIC_MEDICAL_CYCLOTRON_V1` (function + family) is intentionally **kept** for backward-compatibility with direct-recipe tests; it is simply no longer the resolved family for canonical cyclotrons.

---

## 3. Cyclotron V2 primitive inventory (27 primitives, in the 15–30 band)

All primitives scale from the pose envelope `{ center, width W, depth D, height H, yaw }`. The shielded body occupies the rear/left ~70% of the footprint; the service cabinet sits to the +X side (the classic recognizable pairing).

| Group | Part role | Count | Kind |
|---|---|---:|---|
| Base | `CYC_BASE_RING` | 1 | cylinder (dark structural plinth) |
| Base | `CYC_FOOT` | 4 | cylinders (near-black leveling feet) |
| Body | `CYC_LOWER_SHELL` | 1 | cylinder (broad shielded drum, off-white) |
| Body | `CYC_UPPER_SHELL` | 1 | cylinder (narrower stepped upper, light gray) |
| Front | `CYC_ACCESS_PANEL` | 4 | boxes (segmented front access panels) |
| Front | `CYC_PANEL_HANDLE` | 4 | boxes (near-black handles/latches) |
| Upper | `CYC_SERVICE_COLUMN` | 1 | box (central service column) |
| Upper | `CYC_UPPER_MODULE` | 2 | boxes (service modules) |
| Upper | `CYC_CONDUIT` | 2 | cylinders (restrained back conduits) |
| Accent | `CYC_BRAND_ACCENT` | 1 | box (restrained accent stripe) |
| Cabinet | `CYC_CABINET_BASE` | 1 | box (dark base) |
| Cabinet | `CYC_CABINET` | 1 | box (off-white enclosure) |
| Cabinet | `CYC_CABINET_VENT` | 2 | boxes (near-black vent slots) |
| Cabinet | `CYC_CONTROL_SCREEN` | 1 | box (dark display face) |
| Cabinet | `CYC_ESTOP` | 1 | cylinder (restrained red e-stop) |
| **Total** | | **27** | |

---

## 4. Vestibule V1 primitive inventory

The vestibule is a compact, chest/waist-height controlled-transfer cabinet — deliberately **not** cyclotron-sized and **not** a generic MRT endpoint. Compact caps: width ≤ 1.2 m, depth ≤ 0.9 m, height ≤ 1.6 m.

| Part role | Kind | Purpose |
|---|---|---|
| `VEST_BASE` | box | plinth |
| `VEST_HOUSING` | box | shielded housing |
| `VEST_ACCESS_PANEL` | box | dark front (-Y) access panel |
| `VEST_TRANSFER_INTERFACE` | cylinder | metallic transfer interface on the front panel |
| `VEST_STATUS_LIGHT` (×2) | cylinders | status lights above the panel |
| `VEST_CONTROL_PANEL` | box | small side control panel |
| `VEST_TRANSFER_THROAT` | cylinder | throat proxy toward the back wall (+Y) — **visual cue only, no routing** |
| `VEST_BRAND_ACCENT` | box | restrained MRTway accent stripe |

---

## 5. Material palette (by part role, restrained)

No whole-machine cyan / blue / green. Differentiation is by material role only:

- Main housings / enclosures — warm off-white (`CYC_LOWER_SHELL [214,216,210]`, `CYC_CABINET [222,224,220]`).
- Secondary shells / modules — light gray (`CYC_UPPER_SHELL [198,202,206]`, `CYC_UPPER_MODULE [176,182,190]`).
- Structural bases / rings — dark gray (`CYC_BASE_RING [86,92,100]`, `CYC_CABINET_BASE [80,86,94]`).
- Vents / handles / feet / conduits — near-black (`CYC_CABINET_VENT [44,48,54]`, `CYC_FOOT [70,74,80]`, `CYC_CONDUIT [60,64,70]`).
- Control screen — dark display face (`CYC_CONTROL_SCREEN [40,52,66]`).
- E-stop — restrained red (`CYC_ESTOP [196,60,52]`).
- Accent — restrained green (`[78,168,120]`).

The palette lives once in `EQUIPMENT_PART_COLOR` (equipmentGeometry.ts) and is imported by `ClinicalProgramDecorator` and `SpatialAssetDecorator` (imported as `PART_COLOR`). No second copy.

---

## 6. Selection: outline / envelope only — never solid cyan (the corrected defect)

- **Before:** selection repainted the whole solid cyan, hiding all part materials (the reported defect).
- **After:** `drawEquipmentVisual` keeps every part's per-role fill regardless of selection. When selected, it sets only `line = EQUIPMENT_SELECTION_OUTLINE ([90,200,220])` — a thin cyan/teal outline — and the existing lightly translucent containment envelope remains the selection cue.

This is a pure decision covered by tests: selection changes the outline, not the fills.

---

## 7. Envelope vs visual distinction

- The **envelope** is the authoritative calibrated volume used for collision reservation and Fit-to-Equipment; the translucent envelope is the selection cue.
- The **visual** (V2 parts) is representative and regenerated from `family + pose` — never persisted as a mesh (`vertices`/`triangles` never appear in storage). Both derive from the **one** instance pose, so translation and yaw move visual and envelope together.

---

## 8. Vestibule adjacency relationship (pure logic, spec §13)

`equipmentAdjacency.ts` (new, pure — no Bentley, no I/O):

- `evaluateAdjacency(...)` — determines whether two room footprints share a wall / are adjacent.
- `findVestibuleAdjacentRoom(...)` — from the cyclotron's parent room, picks a **different** adjoining room as the vestibule host.
- `seedVestibulePoseInAdjoiningRoom(...)` — seeds a compact, wall-adjacent, non-overlapping pose in that adjoining room.

Key invariants (tested): the vestibule is placed in a **different parent room** than the cyclotron — the two objects do **not** share the same parent room — and it is wall-adjacent and non-overlapping. Cyclotron ($1,000-class representative endpoint distinction) and vestibule ($30,000-class controlled-transfer cabinet) keep separate identity, label and 2D marker.

> **Bounded delivery:** the vestibule is delivered as a pure recipe + pure adjacency/pose logic — sufficient to prove adjacency → placement (spec §13). Full `EquipmentAssetInstance` lifecycle wiring for MRT facility classes was deliberately **not** added: `createEquipmentInstance` depends on `canonicalEquipmentById()`, which excludes MRT facility classes, and broadening that is out of scope and risky for this bounded visual refinement.

---

## 9. Files changed this build

**New**
- `frontend/src/components/spatial/equipmentAdjacency.ts` — pure adjacency + placement.
- `frontend/src/tests/eviMa04MediumLodCyclotronVestibule.test.ts` — 15 EVI-MA-04 tests.

**Modified**
- `frontend/src/components/spatial/equipmentGeometry.ts` — V2 + vestibule recipes, expanded `EquipmentPart` union, shared `EQUIPMENT_PART_COLOR` + `EQUIPMENT_SELECTION_OUTLINE`, CYCLOTRON → V2 routing at all three seams, dispatch for both new families.
- `frontend/src/components/spatial/ClinicalProgramDecorator.ts` — outline-only selection, shared palette import.
- `frontend/src/components/spatial/SpatialAssetDecorator.ts` — shared palette import (removed local map).
- `frontend/src/tests/equipmentVisualIntegration.test.ts` — cyclotron resolver assertions → V2 (spec-mandated); V2 added to the finite-coordinate family loop. Direct `buildCyclotronParts` (V1) recipe tests unchanged.
- `frontend/src/tests/eviMa01LiveEquipmentVisibility.test.ts` — KIUBE resolver/diagnostic assertions → V2 with V2 part names (`CYC_LOWER_SHELL`/`CYC_UPPER_SHELL`/`CYC_CABINET`, ≥15 parts). Generic bounds-math tests left on V1 (validate the bounds function itself).

---

## 10. Verification (this build)

| Check | Command | Result |
|---|---|---|
| Typecheck | `npx tsc -b` | PASS (0 errors) |
| EVI-MA-04 + touched files | `npx vitest run <3 files>` | 44 passed |
| Full frontend suite | `npx vitest run` | **75 files / 1169 tests — all pass** |
| Production build | `npm run build` (in `frontend/`) | PASS (pre-existing INEFFECTIVE_DYNAMIC_IMPORT + chunk-size warnings only) |
| Live viewer | `curl /viewer` on :3000 | **200** |

Test-count movement: the 6 previously-failing pre-existing EVI assertions (broken by the deliberate CYCLOTRON V1→V2 mapping) are corrected to assert V2, and +15 new EVI-MA-04 tests were added. Net full suite: 75 files / 1169 tests, all green.

Dev server left running on **port 3000** (`npm run dev -- --port 3000 --strictPort`).

---

## 11. Manual acceptance steps (spec §17 / §18) — `manual_acceptance = PENDING`

Please verify in the live viewer at `http://localhost:3000/viewer`:

1. **Recognizable machine.** Place / open a canonical cyclotron (e.g. IBA Cyclone KIUBE). It reads as a real medium-LOD machine — shielded drum body with a stepped upper shell, base ring + leveling feet, segmented front access panels with handles, an upper service column + modules, and an adjacent service cabinet with vents, a control screen and a red e-stop — **not** a plain proxy.
2. **Materials.** Parts are differentiated by material (off-white housings, gray shells, dark bases, near-black vents/handles, dark screen, red e-stop, restrained accent). No whole-machine cyan / blue / green.
3. **Selection.** Selecting the cyclotron shows a **thin outline** + translucent envelope. It does **NOT** turn solid opaque cyan; part materials remain visible.
4. **Preserved lifecycle (must NOT regress):** selectable · floating SELECTED EQUIPMENT control · correct Hidden state label · Hide → Show semantics · Lock/Unlock · Delete · collision reservation · 2D marker.
5. **Vestibule (recipe/adjacency stage):** confirm the adjacency intent — the MRT Radiopharmacy Vestibule belongs immediately across the wall in the **adjoining** room (a different parent room from the cyclotron), compact and wall-adjacent, with its own identity/label distinct from the cyclotron.

**Do not self-accept.** Await explicit visual acceptance before starting PTS / RTHS / MRT animation / Build 2.

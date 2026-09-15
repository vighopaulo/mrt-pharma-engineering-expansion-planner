# MRT Pharma — Existing Equipment Visual Integration Report

Surface recognizable Cyclotron, PET/CT and Radiopharmacy equipment geometry in the live Bentley digital twin.

Status: automated success criteria satisfied. Awaiting user manual-acceptance confirmation. Transport visuals (Build 2) explicitly NOT started.

---

## 1. Exact current baseline

- Branch: `main` (HEAD `1de2c5b` — "MRT Pharma: complete Build 1A spatial planning foundation").
- Working tree contained substantial UNCOMMITTED Build 1B / manual-acceptance work at session start (Build 1B equipment binding, 2D plan, walkthrough trail, candidate acceptance, plus a Build 2A transport authority report). All of it was PRESERVED and left untouched — no revert, no ZIP restore, no GitHub reset.
- Typecheck (`tsc -b`): PASS
- Frontend suite (`vitest run`): 65 files / **1053 tests PASS** (before change and after change; +17 new tests included in the 1053)
- Production build (`tsc -b && vite build`): PASS (only pre-existing `INEFFECTIVE_DYNAMIC_IMPORT` + chunk-size advisory warnings — no errors)
- Dev server: clean start on `:3000`
- `/viewer` HTTP status: **200**; `/` : 200
- WASM asset present: `public/scripts/draco_decoder.wasm`
- Bentley worker present: `public/scripts/parse-imdl-worker.js`
- OpenUSD-related Python tests: 165 PASS (adapter + YC demo binding + Bentley renderability firewall)

Only 6 files changed by this build (2 new, 4 modified). All prior uncommitted work is intact.

---

## 2. Actual existing asset inventory (verified against the current tree)

| Asset | Exact path | Type | Primitives | Coord/units | Provenance | Used by Bentley? | Used by OpenUSD export? |
|---|---|---|---|---|---|---|---|
| Representative cyclotron | `openusd_visual_assets/representative_cyclotron.usda` | OpenUSD `.usda` | `Cylinder Body` (r=0.85,h=1), `Cylinder Shielding` (r=1.05,h=1.1), `Cube ServiceCabinet` | USD local, meters | `REPRESENTATIVE_ASSET` / `NON_AUTHORITATIVE` | **No** (firewalled) | Yes |
| Representative scanner | `openusd_visual_assets/representative_scanner.usda` | OpenUSD `.usda` | `Cylinder Gantry`, `Cube Table`, `Cube Base` | USD local, meters | `REPRESENTATIVE_ASSET` | No | Yes |
| Representative radiopharmacy | `openusd_visual_assets/representative_radiopharmacy.usda` | OpenUSD `.usda` | `Cube HotCell`, `Cube Workbench`, `Cube Dispensing` | USD local, meters | `REPRESENTATIVE_ASSET` | No | Yes |
| Room context + demos | `openusd_visual_assets/representative_room_context.usda`, `mrt_pharma_hospital_visual_demo.usda`, `mrt_pharma_hospital_dynamic_foundation_demo.usda`, `artifacts/yc_demo/mrt_pharma_yc_demo.usda` | OpenUSD `.usda` | Composed primitives | USD local | Representative/demo | No | Yes |
| BIM proof | `bim_test_assets/mrt_pharma_hospital_bim_proof.ifc` | IFC | IfcSpace/geometry | IFC world | Generated proof | Consumed by IFC/BIM path | No |
| Frontend PET/CT recipe | `frontend/src/components/spatial/scannerGeometry.ts` | TS (Bentley-free) | gantry box + bore cylinder + table + base | Bentley world, meters | `GENERIC_ENGINEERING_PLACEHOLDER` | **Yes** | No |

Reported filenames from the brief were verified: `openusd_visual_assets/representative_{cyclotron,scanner,radiopharmacy}.usda` and `bim_test_assets/mrt_pharma_hospital_bim_proof.ifc` all exist as described.

Equivalent pre-existing Bentley procedural geometry: only PET/CT existed (`scannerGeometry.ts`). No cyclotron/hot-cell procedural geometry existed for Bentley before this build.

---

## 3. Current Bentley rendering architecture (as found)

Two parallel decorator paths render placed equipment into the live iTwin.js viewer:

1. **AssetInstance path** — `SpatialAssetDecorator` (`GraphicBuilder` solids via `Box.createRange` / `Cone.createAxisPoints`), fed by the DEV/catalog fixtures including the GE HealthCare Discovery MI proof. This path already rendered recognizable PET/CT geometry from `buildScannerParts`.
2. **EquipmentAssetInstance path** (the product bind-to-room workflow) — `ClinicalProgramDecorator.drawEquipmentEnvelope`, which previously drew **only** a translucent oriented proxy box + edges + label. This was the visual gap: a cyclotron or hot cell appeared as an envelope, not recognizable equipment.

The user's demonstrated Discovery MI is a persisted product/fixture asset carrying `geometryRepresentationId = GENERIC_PET_CT_SCANNER_V1`.

## 4. Current OpenUSD architecture (as found)

Export-only and deliberately firewalled: `generate_openusd_hospital_visual_demo.py` authors the representative primitives; `openusd_spatial_adapter.py` binds them; Python tests assert Bentley/IFC generators do NOT import `openusd_spatial_adapter` or `pxr`. Bentley does not consume `.usda`. Therefore recognizable Bentley geometry must be authored in TypeScript, mirroring (not importing) the USDA composition.

---

## 5. Integration approach chosen

A single **renderer-independent generic geometry recipe** (`equipmentGeometry.ts`) that both Bentley decorators consume, mirroring the existing OpenUSD primitive composition rather than duplicating an unrelated model:

```
Generic geometry recipe (equipmentGeometry.ts)
        ├──→ Bentley: SpatialAssetDecorator (AssetInstance)
        └──→ Bentley: ClinicalProgramDecorator (EquipmentAssetInstance)
OpenUSD exporter (unchanged) authors the SAME conceptual primitives in Python.
```

- PET/CT reuses the existing `scannerGeometry` recipe (refactored into a pose-based core `buildScannerPartsFromPose`, no behavior change).
- Cyclotron mirrors `representative_cyclotron.usda`: cylindrical **body** + concentric **shielding** cylinder + **service cabinet** box.
- Radiopharmacy mirrors `representative_radiopharmacy.usda`: **hot cell** + **workbench** + **dispensing** boxes.
- The engineering **containment envelope is preserved** (authoritative for validation), drawn more translucent when a recognizable solid is present, and toggleable via `getShowEquipmentEnvelope` (default ON — nothing regresses).

No renderer rewrite. No new selectable object. No second lifecycle. No duplicate cyclotron model downloaded or authored.

---

## 6. Files changed

New:
- `frontend/src/components/spatial/equipmentGeometry.ts` — the shared recipe + visual-family resolution.
- `frontend/src/tests/equipmentVisualIntegration.test.ts` — 17 focused tests.

Modified:
- `frontend/src/components/spatial/scannerGeometry.ts` — extracted `buildScannerPartsFromPose`; `WorldBox`/`WorldCylinder` made generic over the part label (default `ScannerPart`).
- `frontend/src/components/spatial/ClinicalProgramDecorator.ts` — added `drawEquipmentVisual` + `buildEquipmentBox`; threads `canonicalClass`/`assetFamily`; envelope kept + more translucent when a visual is present; `getShowEquipmentEnvelope` toggle.
- `frontend/src/components/spatial/spatialAssetOverlay.ts` — `getEquipmentForRender` now passes `canonicalClass` + `assetFamily`.
- `frontend/src/components/spatial/SpatialAssetDecorator.ts` — uses `buildEquipmentPartsForInstance` (family-aware via `geometryRepresentationId`); part palette extended.

---

## 7. Generic visual families implemented

- `GENERIC_PET_CT_SCANNER_V1` — gantry + bore + patient table + table base.
- `GENERIC_MEDICAL_CYCLOTRON_V1` — cylindrical body + shielding drum + service cabinet.
- `GENERIC_RADIOPHARMACY_HOTCELL_V1` — shielded hot cell + workbench + dispensing station.

Radionuclide generator visualization was deliberately NOT built (per brief §7): no recognizable generator geometry pre-existed, and generators carry no spatial `assetFamily`. It can follow later through the same architecture.

## 8. Canonical → visual mappings (many-to-one; identity stays separate)

| Canonical (exact engineering identity) | Class | Generic VISUAL identity |
|---|---|---|
| GE HealthCare PETtrace 890 | CYCLOTRON | `GENERIC_MEDICAL_CYCLOTRON_V1` |
| IBA Cyclone KIUBE | CYCLOTRON | `GENERIC_MEDICAL_CYCLOTRON_V1` |
| (all 17 canonical cyclotrons) | CYCLOTRON | `GENERIC_MEDICAL_CYCLOTRON_V1` |
| GE HealthCare Discovery MI | SCANNER (PET) | `GENERIC_PET_CT_SCANNER_V1` |
| Siemens Biograph Vision, all SPECT scanners | SCANNER | `GENERIC_PET_CT_SCANNER_V1` |
| Radiopharmacy/hot-cell equipment | (HOT_CELL family) | `GENERIC_RADIOPHARMACY_HOTCELL_V1` |

Tests confirm: canonical A ≠ canonical B while both map to the same generic cyclotron visual, and the visual mapping never overwrites `canonicalEquipmentId`.

## 9. Provenance behavior

Representative geometry stays representative: envelope provenance (`GENERIC_ENGINEERING_PLACEHOLDER` vs `CATALOG`/`CALIBRATED`) is preserved from the canonical catalog. GE PETtrace envelopes remain placeholder; IBA Cyclone KEY/KIUBE and ACSI TR-24 remain calibrated. No manufacturer-exact dimensions are fabricated; where uncalibrated, `NOT_CALIBRATED` remains authoritative. The recipe parametrizes off the instance envelope, so future calibrated dimensions apply with no architectural change.

## 10. Persistence behavior

Unchanged and safe: `localStorage` key `mrtpharma.equipment.v1.<iModelId>`, strict allowlist, no mesh/secrets stored. The visual is regenerated deterministically from `visualRepresentationId` (resolved from family/pose) — never persisted as a mesh. Test proves a reloaded cyclotron reconstructs an identical part set and that `vertices`/`triangles` never appear in storage. The persisted GE Discovery MI resolves to recognizable PET/CT without destructive recreation.

## 11. Pose / lock / delete

- Pose: recognizable geometry uses the SAME authoritative pose (X, Y, Z-base, yaw) as the AssetInstance/envelope. Translation and yaw tests pass; visual + envelope move/rotate together.
- Lock: locking affects lifecycle only; a LOCKED instance still produces recognizable geometry (test).
- Delete: `deleteEquipment` filters the single `equipmentInstances` collection that `getEquipmentForRender` maps, so the recognizable visual AND its envelope vanish together with the one AssetInstance. No Bentley source BIM geometry is modified.

---

## 12. Test results

- New: `frontend/src/tests/equipmentVisualIntegration.test.ts` — 17 tests PASS. Covers: canonical→visual mapping (many-to-one), canonical identity separation, per-family structural composition (PET/CT gantry+bore+table; cyclotron body+shielding+cabinet with a cylinder; radiopharmacy hot cell+workbench+dispensing — none is a single box), finite coordinates, pose translation + yaw, persistence reconstruction, locked-stays-rendered, representative-vs-calibrated provenance, and the Discovery MI PET/CT regression.
- Full frontend suite: 65 files / 1053 tests PASS.
- Typecheck: PASS. Production build: PASS. `/viewer`: 200. WASM + worker present. OpenUSD tests: 165 PASS (firewall intact).

---

## 13. Known limitations

- Geometry is LOW-LOD REPRESENTATIVE (recognizable silhouette, not manufacturer CAD). Explicitly labeled representative; not authoritative for engineering.
- Cyclotron/hot-cell dimensions parametrize off the (often placeholder) envelope; only IBA Cyclone KEY/KIUBE and ACSI TR-24 carry calibrated cyclotron envelopes today.
- Radionuclide generator visual is deferred (no recognizable geometry existed to reuse).
- The Bentley decorator itself is validated through its pure geometry seam (Bentley-free), consistent with the repository's existing test convention; live rendering is confirmed via the manual-acceptance path below.

## 14. Transport visuals — explicitly deferred

NOT started in this build (per §22–§23): PTS tube/carrier, RTHS track/carrier, MRT guideway/endpoint/carrier, AGV/AMR, patient animation, automatic logistics missions, Build 2 routing. This build only establishes the recognizable equipment visual foundation.

## 15. Unrelated Build 1B UX findings

Not touched (per §21). Outstanding Build 1B UX/state items (clinical program panel, selected-room sync, walkthrough/clinical-room divergence) remain as-is; none blocked equipment rendering.

---

## 16. Manual acceptance instructions (do NOT self-accept)

Run the dev server (`npm run dev` in `frontend/`) and open `/viewer`.

Scanner
- PET/CT 01 → existing GE HealthCare Discovery MI → confirm a recognizable PET/CT (gantry + bore + patient table) is visible, not just an envelope. Equipment card still reads "GE HealthCare Discovery MI". No delete/recreate required.

Cyclotron
- Select a valid production / radiopharmacy-associated room → choose an exact canonical cyclotron (e.g. GE HealthCare PETtrace 890) → Place → confirm a recognizable cyclotron (cylindrical shielded body + service cabinet) appears → select it → card still shows the exact canonical cyclotron model.

Radiopharmacy equipment
- In the Radiopharmacy room (e.g. `2C17 PROSTH. LAB → Radiopharmacy` if still valid) → place/select representative hot-cell/workstation equipment → confirm recognizable radiopharmacy equipment (hot cell + workbench + dispensing) is visible.

Then
- Enter Walkthrough and confirm the equipment can be located from pedestrian view where walkthrough state permits.

If confirmed, mark manual acceptance. STOP — do not begin PTS/RTHS/MRT animation or Build 2 routing.

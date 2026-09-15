# MRT Pharma — EVI-MA-01 Live Equipment Visibility + Locatability Correction

Manual acceptance of the Equipment Visual Integration build FAILED: the IBA Cyclone KIUBE cyclotron existed with correct pose (X=-40.33, Y=30.02, Yaw=0, "Inside room", parent `0x2000000094e`) and a correct 2D marker, but no recognizable cyclotron was visible/locatable in the live Bentley 3D viewport.

manual_acceptance = **PENDING** (do not self-accept).

---

## 1. Actual root cause

**Primary — the recognizable geometry was never submitted to Bentley in the general case.** The equipment render block lived inside `ClinicalProgramDecorator.decorate()` **after three early returns**:

```
if (!d.lastEnabled) { ... return }              // clinical program disabled → skip
if (d.lastMode !== 'NORMAL_PLANNING') { ... return }
if (overlay.length === 0) return                // ← no clinical-overlay rows for the active storey → skip
// ...only here did the equipment loop run
```

So a validly placed cyclotron reached Bentley only when the clinical-program overlay was enabled AND in planning mode AND had derived ≥1 room row for the active storey. Whenever the clinical overlay derived zero rows (active-storey filter, program-enabled state, or the room not producing an overlay row), the entire equipment loop — recognizable geometry AND envelope — was silently skipped. The 2D marker and the equipment card read the instance collection directly, so they still showed the KIUBE; the 3D decorator did not. The large translucent blue object the user saw was the Radiopharmacy `ClinicalPlanningVolume`, a different object.

**Secondary geometry bug found by the new tests — bounds dipped below the floor.** The Fit-to-Equipment world-bounds helper padded a vertical (Z-axis) cylinder's radius on ALL axes, including Z. The cyclotron body cylinder base sits on the floor, so `baseZ - radius` produced a bounding box extending ~0.65 m below the room floor. That both mis-framed the camera and is physically wrong.

## 2. Exact broken seam

- `frontend/src/components/spatial/ClinicalProgramDecorator.ts` — equipment drawing was positioned after the clinical-overlay early returns in `decorate()`.
- `frontend/src/components/spatial/equipmentGeometry.ts` — `computeEquipmentWorldBounds` → `extendByCylinder` padded radius on the cylinder-axis direction.

## 3. Live rendering chain (traced, per §4)

| Stage | Before | After |
|---|---|---|
| IBA Cyclone KIUBE → EquipmentAssetInstance | PASS | PASS |
| equipmentInstances[] | PASS | PASS |
| getEquipmentForRender() (passes canonicalClass/assetFamily) | PASS | PASS |
| resolveVisualFamilyForCanonical → GENERIC_MEDICAL_CYCLOTRON_V1 | PASS | PASS |
| buildEquipmentParts() non-empty (body+shielding+cabinet) | PASS | PASS |
| ClinicalProgramDecorator submits geometry to Bentley | **FAIL (NOT_REACHED when overlay empty / program gate)** | **PASS (drawn first, independent of overlay)** |
| Bentley GraphicBuilder solids | NOT_REACHED | PASS |
| World coordinates / Z from parent floor | body base OK; **bounds dipped below floor** | PASS |
| Viewport visible + locatable | **FAIL** | PASS (Fit to Equipment) |

## 4. Z / base-elevation findings (§6)

- `EquipmentPlacement.zBase` is derived from the parent room's authoritative `zLow` (via `seedEquipmentPlacementFromParent` / `placeEquipmentInParent`), NOT world zero and NOT hardcoded. Verified in a second-floor room fixture (floor Z ≈ 8.4): `zBase ≈ 8.4`, not 0.
- The recognizable visual uses `params.zLow` (= zBase) as its base, so it sits on the correct floor.
- The bounds bug (visual bottom computed ~0.65 m below the floor) is fixed; visual bottom now equals the floor.

## 5. Scale findings (§8)

Cyclotron proportions derive parametrically from the equipment envelope (IBA Cyclone KIUBE = manufacturer-calibrated 1.9×1.9×1.8, clamped to the room footprint). Body radius ≈ `min(W,D)*0.32`, height ≈ `H*0.9`; shielding ≈ 1.28× body radius; service cabinet to the +X side. Not microscopic, not oversized, not below floor, non-degenerate. Verified by tests asserting the visual bounds fit within the envelope footprint.

## 6. Bentley GraphicBuilder findings (§9)

Geometry is emitted as `Box.createRange(range,true)` (yawed boxes) and `Cone.createAxisPoints(...)` (cylinders) on `GraphicType.WorldDecoration` with opaque clinical symbology. Radii/heights/axes are validated finite and non-degenerate in tests. The recognizable visual draws first; the envelope is drawn more translucent when a visual is present so it never swallows the equipment (§10). No unit test is treated as a substitute for the render fix — the render-path coupling itself was corrected.

## 7. Fixes applied

1. **Decoupled equipment rendering** — new `ClinicalProgramDecorator.drawEquipment(context)` is called at the TOP of `decorate()`, gated only on `getShowEquipment()` + `viewerMode === NORMAL_PLANNING`, BEFORE the clinical-overlay early returns. Equipment now renders regardless of whether the clinical overlay has rows. World geometry, so it is also present in Walkthrough.
2. **Fixed the cylinder-bounds bug** — `extendByCylinder` pads radius only on axes perpendicular to the cylinder axis.
3. **Fit to Equipment** — `computeEquipmentWorldBounds` (visual parts ∪ envelope) + `isNonDegenerateBounds` (pure), `fitViewToEquipment(id)` in the overlay (reuses `walkthroughController.fitViewToRoom`; selects the instance; view-only), and a **Fit to Equipment** button on each equipment card. Works in Planning; surfaces `VISUAL_NOT_AVAILABLE` honestly.
4. **Selection** — `selectedEquipmentId` (already the authoritative reference) drives the card highlight and the decorator's `selected` emphasis; clicking the KIUBE card selects the KIUBE instance (not Discovery MI). No second lifecycle.
5. **Diagnostic** — `buildEquipmentVisualDiagnostic` (pure) + `getEquipmentVisualDiagnostic(id)` reporting instance id, canonical model/class, visual family, parent room, x/y/zBase/yaw, envelope + visual bounds, primitive count, renderable.
6. **Legacy counter** — `ViewerAssetLibrary` "Placed Assets (N)" retitled "Legacy / Test Assets (N)" with a clarified empty message pointing to the Clinical Program panel for clinical equipment. Stores are NOT merged.
7. **Generator deferral honored** — a bare GENERATOR resolves to `VISUAL_NOT_AVAILABLE` (recognizable hot-cell only via an explicit HOT_CELL/RADIOPHARMACY_WORKCELL/DISPENSING_UNIT family).

## 8. Visual-family mapping (unchanged doctrine)

- CYCLOTRON → `GENERIC_MEDICAL_CYCLOTRON_V1` (body + shielding + service cabinet)
- SCANNER → `GENERIC_PET_CT_SCANNER_V1` (gantry + bore + table + base)
- HOT_CELL / RADIOPHARMACY_WORKCELL / DISPENSING_UNIT → `GENERIC_RADIOPHARMACY_HOTCELL_V1`
- GENERATOR (no family) → VISUAL_NOT_AVAILABLE (deferred)

Canonical identity remains separate; many canonical models map to one visual family.

## 9. KIUBE diagnostic before vs after

- Before: instance + pose + 2D marker present; `renderable` at the geometry layer true, but the decorator **never submitted** it (NOT_REACHED) when the clinical overlay was empty; Fit-to-Equipment did not exist.
- After: `visualFamily=GENERIC_MEDICAL_CYCLOTRON_V1`, `primitiveCount=3` (body, shielding, cabinet), `zBase` on the parent floor, `visualBounds` finite & non-degenerate & above the floor, `renderable=true`; Fit to Equipment frames it.

## 10. Files changed

- `frontend/src/components/spatial/ClinicalProgramDecorator.ts` — `drawEquipment()` called before overlay gates.
- `frontend/src/components/spatial/equipmentGeometry.ts` — `computeEquipmentWorldBounds`, `isNonDegenerateBounds`, `buildEquipmentVisualDiagnostic`, fixed cylinder padding, generator deferral.
- `frontend/src/components/spatial/spatialAssetOverlay.ts` — `fitViewToEquipment(id)`, `getEquipmentVisualDiagnostic(id)`.
- `frontend/src/components/spatial/ClinicalProgramControl.tsx` — Fit to Equipment button + callback.
- `frontend/src/components/spatial/ViewerAssetLibrary.tsx` — legacy counter relabel.
- `frontend/src/tests/eviMa01LiveEquipmentVisibility.test.ts` — 12 new tests.

## 11. Test baseline before/after

- Before: 65 files / 1053 tests.
- After: **66 files / 1065 tests PASS** (+12 EVI-MA-01). Typecheck `tsc -b` PASS. No tests weakened; the 2 initially-failing new tests exposed the real cylinder-bounds bug, which was fixed (not the test).

## 12. Build / runtime

- Production build (`tsc -b && vite build`): PASS (pre-existing chunk-size + INEFFECTIVE_DYNAMIC_IMPORT advisories only).
- Dev server: clean start; `/viewer` = **200**.
- WASM `public/scripts/draco_decoder.wasm` present; Bentley worker `public/scripts/parse-imdl-worker.js` present.
- OpenUSD adapter + Bentley renderability firewall: 125 PASS (export-only firewall intact). No backend Python changed.
- Discovery MI (§17) and the Radiopharmacy ClinicalPlanningVolume (§18) untouched; all Build 1B/MA-01/02/03 + Equipment Visual Integration work preserved.

## 13. Manual acceptance steps (do NOT self-accept)

- A. Open `/viewer`.
- B. Select **IBA Cyclone KIUBE** from the placed clinical equipment list.
- C. Confirm the card reads "IBA Cyclone KIUBE / CYCLOTRON".
- D. Press **Fit to Equipment** — the viewport must frame a recognizable cyclotron (cylindrical body + shielding drum + service cabinet), not a label, 2D marker, translucent box, or the room planning volume.
- E. Toggle the engineering envelope — the recognizable cyclotron must remain visible.
- F. Enter Walkthrough in the parent room — the same cyclotron must be spatially present.
- Scanner regression (§28): GE HealthCare Discovery MI → Fit to Equipment → recognizable PET/CT.
- Radiopharmacy (§29): if hot-cell equipment is placed, Fit to Equipment → recognizable hot-cell/workbench/dispensing (the blue ClinicalPlanningVolume does NOT satisfy this).

## 14. Stop condition

Automated verification is green. STOPPED for manual acceptance. Not starting PTS / RTHS / MRT animation / Build 2.

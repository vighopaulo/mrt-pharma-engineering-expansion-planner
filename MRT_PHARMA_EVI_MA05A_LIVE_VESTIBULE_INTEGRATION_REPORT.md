# EVI-MA-05A — Live Clinical Logistics Vestibule Placement, Bentley Rendering, Interaction & Persistence (+ Supplemental Hollow Passages)

**Status:** implementation complete · `manual_acceptance = PENDING` (do not self-accept)
**Continues from:** the CURRENT working tree. EVI-MA-05 established the vestibule architecture and deferred live Bentley lifecycle integration; EVI-MA-05A closes that gap and adds the supplemental HOLLOW carrier-traversable passage + distinct MRT/PTS carrier-clearance doctrine.
**Boundary:** this build ends at the transport CONNECTION PORTS. No hospital-wide routing, no carrier/capsule animation, no travel-time physics. That is Build 2.

---

## 1. Reconcile (before any edit)

| Field | Value |
|---|---|
| Branch | `main` |
| HEAD | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| origin/main | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| Divergence | 0 ahead / 0 behind |
| Test baseline (start) | 76 files / 1196 tests passing |

A prior EVI-MA-05A agent session had failed on a Kiro network error during read-only investigation. Reconcile confirmed it made **zero edits** (no files modified in that window, no EVI-MA-05A artifacts). No reset/revert/ZIP; all uncommitted EVI work preserved.

## 2. Reused EVI-MA-05 architecture (ONE vestibule model)

No new vestibule model was created. Everything reuses `CLINICAL_LOGISTICS_VESTIBULE_V1` and the single `ClinicalLogisticsVestibuleInstance` domain (service-class taxonomy, port policy, wall placement, geometry recipe, persistence). No `VestibuleV2`, no `MrtVestibuleObject`, no `PtsVestibuleObject`.

The live integration deliberately MIRRORS the proven equipment lifecycle seams: a module-level iModel-scoped store in `spatialAssetOverlay.ts`, `notifyProgram()` (React `subscribeClinicalProgram` + Bentley `invalidateDecorations`), a decorator render input, one transient pick id per instance, and a composite-snapshot floating control.

---

## 3. Live create action (§5)

`CREATE RADIOPHARMACY VESTIBULE` is a button on the SELECTED-EQUIPMENT floating control, shown only when the selected equipment is a `CYCLOTRON` (no scrolling through room controls). On activation `createRadiopharmacyVestibuleForCyclotron(cyclotronId)` runs the whole pipeline in the overlay:

1. resolve the selected cyclotron → 2. its parent BIM room → 3. `ensureAuthoritativeRoomFootprint` → 4. enumerate defensible walls (longest-first, ≥ `MIN_VESTIBULE_WALL_WIDTH_M`) → 5. seed a wall-integrated pose per wall → 6. collision-check the room-side reserved volume against equipment + other vestibules → 7. create exactly ONE `ClinicalLogisticsVestibuleInstance` (`serviceClass = RADIOPHARMACY`, `parentBimSpaceId == cyclotron.parentBimSpaceId`) → 8. persist → 9. select → 10. the control Fits to it.

Honest outcomes: `VESTIBULE_ALREADY_EXISTS` (selects + Fits the existing one — one active radiopharmacy vestibule per production context), `NO_DEFENSIBLE_WALL`, `VESTIBULE_COLLISION`, `ROOM_TOO_SHORT` — each creates nothing.

## 4. Wall-integrated pose, immutable BIM (§6–§8)

The vestibule shares the cyclotron's room but is placed against a defensible wall (opposite wall acceptable; never centroid-seeded; not optimized for shortest cyclotron distance). The front access face sits toward the room interior; the assembly extends through the wall into the rear manifold + port stubs. The Bentley wall is never cut/deleted/modified — `wallRelationshipStatus = PROPOSED_WALL_PENETRATION`.

## 5. Live 3D rendering + materials (§9–§10)

`ClinicalProgramDecorator.drawVestibules()` renders each vestibule via the SAME `drawEquipmentVisual` path (per-part materials, outline-only selection), using `buildEquipmentParts('CLINICAL_LOGISTICS_VESTIBULE_V1', pose, { vestibulePorts })`. Room-side: sage/pale-green fascia, transfer door, aperture, handle, HMI, green/amber/red status, e-stop, service panel. Behind-wall: wall sleeve, rear manifold, MRT large section + four planar reducer faces + trunk stub + connection port, and the separate PTS adapter + circular tube stub + connection port. Palette is the shared `EQUIPMENT_PART_COLOR` (distinct from the cyclotron; not cyan). Selection keeps materials (outline + translucent reserved-volume envelope only).

## 6. Pickable + selected control (§11–§16)

One transient pick id per `vestibuleInstanceId` covers every primitive (front + rear + MRT + PTS), held in a SEPARATE decorator map so a vestibule pick never resolves to an equipment id and vice versa. `MrtDirectManipulationTool` accepts vestibule hits and left-click selects the vestibule. `ViewerSelectedVestibuleControl.tsx` shows when `selectedVestibuleId` is set: title "Radiopharmacy Logistics Vestibule", metadata (Service, Parent, MRT status, PTS qualification + status), and Fit / Hide-Show / Lock-Unlock / Delete — all dispatching to the same overlay functions. It uses the EVI-MA-02E composite snapshot (`id|hidden|lifecycle`) so Hide↔Show flips immediately. Fit uses `computeEquipmentWorldBounds(family + vestibulePorts)` (view-only). Delete removes the ONE instance + both ports + reserved space (cyclotron and wall remain) and persists (no resurrect).

## 7. 2D plan (§22)

`projectBim2dPlan` emits ONE `PlanVestibule` marker per vestibule: the room-side reserved-volume footprint, the wall-penetration segment, and the MRT + PTS stub directions. `hitTestPlanVestibule` resolves a marker click to the same `vestibuleInstanceId` (selects + Fits). Hidden vestibules keep a subdued, recoverable marker. There is never a separate MRT/PTS marker.

## 8. Port identity + qualification (§19–§20, §25)

Each port persists `portId`, `vestibuleInstanceId`, `transportFamily`, qualification/configuration, `position`, `orientation`, `crossSection`, `status`. MRT port is a rectangular reducer/trunk stub; the PTS port is `RADIOPHARMACEUTICAL_QUALIFIED` with a circular tube stub. Both are short stubs, `status = UNCONNECTED`. Nuclear qualification is never auto-inherited (Pharmacy/Laboratory stay `CONVENTIONAL_CLINICAL`).

---

## 9. Supplemental: hollow carrier-traversable passages + distinct clearances

The vestibule and both branches are now carrier-traversable HOLLOW structures with explicit engineering clearances, separating OUTER (structural/collision) geometry from INNER FREE (carrier-clearance) geometry.

**Vestibule internal chamber.** `vestibuleInternalChamber(pose)` derives a genuine hollow transfer chamber: exterior housing vs `wallThickness` vs internal free W/H/D (each internal dim strictly < housing). Rendered as a dark `CLV_CHAMBER_VOID` recess (not a solid block).

**MRT carrier tract (rectangular, hollow).** Inner free cross-section from carrier + explicit clearance:
`W_inner = W_carrier + 2·C_side`, `H_inner = H_carrier + 2·C_vertical`; outer = inner + `2·wall`. The four planar reducer faces surround a continuous inner void rendered as two segments (`CLV_MRT_INNER_VOID`) that narrow toward the trunk. Persisted per-port: `innerCrossSection`, `carrierEnvelope`, `clearance`, `centerline`.

**PTS branch (circular, hollow).** Bore `ID = pig_OD + 2·radial_clearance`; `OD = ID + 2·wall`, so `OD > ID > pig > vial`. Rendered as a dark `CLV_PTS_INNER_BORE` cylinder inside the tube. The PTS bore is many times smaller than the MRT free width — materially different transport scales; an MRT carrier cannot be treated as a PTS carrier.

**Physics seam / collision distinction.** External collision uses the OUTER occupied geometry (reserved volume + outer cross-section); future carrier motion uses the INNER free passage + centerline. These are different tests, and both are persisted.

Representative planning values (architecture, not manufacturer CAD): MRT carrier 0.34×0.34 m, MRT side/vertical clearance 0.03 m, MRT wall 0.04 m; PTS vial 0.05 m, pig 0.09 m, radial clearance 0.008 m, tube wall 0.012 m.

Part count for the dual (radiopharmacy) configuration is now 29 (15 base + 7 MRT + 3 PTS + 4 hollow cues) — still within the 15–30 band.

---

## 10. Files

**New**
- `frontend/src/components/spatial/ViewerSelectedVestibuleControl.tsx`
- `frontend/src/tests/eviMa05aLiveVestibuleAndHollowPassages.test.ts` (21 tests)

**Modified**
- `clinicalLogisticsVestibule.ts` — collision helper (`findVestibuleCollision`/`aabbsOverlap`); hollow/clearance model (internal chamber, MRT inner/outer derivations, PTS bore/OD, named clearance constants); port augmented with `innerCrossSection` / `carrierEnvelope` / `clearance` / `centerline` + safe-persistence deep copy.
- `equipmentGeometry.ts` — `CLV_CHAMBER_VOID` / `CLV_MRT_INNER_VOID` / `CLV_PTS_INNER_BORE` roles + palette + hollow rendering (chamber recess, two-segment narrowing MRT inner void, PTS inner bore).
- `spatialAssetOverlay.ts` — vestibule store + lifecycle (`createRadiopharmacyVestibuleForCyclotron`, `select/set-visibility/lock/unlock/delete/fit`), `getVestibulesForRender`, 2D vestibule projection input, `vestibuleIdForPickId`, iModel-scoped load/persist; `selectEquipment` clears the selected vestibule.
- `ClinicalProgramDecorator.ts` — vestibule pick maps + `drawVestibules` + `drawEquipmentVisual` ports param.
- `MrtDirectManipulationTool.ts` — accept vestibule hits + left-click select.
- `BentleyViewer.tsx` / `BentleyViewer.css` — mount the control + CREATE button + styles.
- `bim2dPlanProjection.ts` — `PlanVestibule` type + projection + `hitTestPlanVestibule`.
- `Bim2dPlanPanel.tsx` — vestibule marker rendering + click resolution.

---

## 11. Tests (§10, §26)

`eviMa05aLiveVestibuleAndHollowPassages.test.ts` (21 tests) covers the Bentley-free substance of the live lifecycle (A..AI subset provable at the domain layer) and the supplemental hollowness A..P: same parent room; wall-integrated not centroid; no cyclotron duct; ONE instance owns MRT + PTS with distinct ids/families; PTS radiopharmaceutical-qualified; PROPOSED_WALL_PENETRATION; collision via reserved volume; persist→reload restores instance + ports + inner-passage seam (no mesh leak); identity independence; service-class policy preserved; EVI-MA-04 cyclotron V2 unchanged; vestibule nonzero internal free volume; MRT outer>inner with positive side/vertical clearance; reducer four planar faces + continuous narrowing inner void; PTS OD>ID>pig>vial with positive running clearance; MRT vs PTS materially different scales; external-collision geometry separate from inner carrier-clearance geometry; visible hollow cues.

> Honesty note: live 3D appearance, the actual camera Fit, and 3D/2D click selection in the running viewer cannot be verified headlessly. The domain lifecycle, geometry recipe, port model, hollow/clearance math, projection, and persistence are all verified by tests + typecheck + build. On-screen confirmation is the manual step.

## 12. Verification

| Check | Result |
|---|---|
| `npx tsc -b` | PASS (0 errors) |
| EVI-MA-05A + EVI-MA-05 suites | 48 passed |
| Full frontend suite | **77 files / 1217 tests — all pass** (was 76 / 1196; +1 file, +21 tests) |
| `npm run build` | PASS (pre-existing INEFFECTIVE_DYNAMIC_IMPORT + chunk-size warnings only) |
| `/viewer` on :3000 | 200 |

Dev server left running on **port 3000**.

## 13. Manual acceptance (§27) — `manual_acceptance = PENDING`

Open `http://localhost:3000/viewer`, then: select a cyclotron → CREATE RADIOPHARMACY VESTIBULE → camera fits → confirm the sage wall-integrated access face (door/HMI/status/e-stop) with the cyclotron still elsewhere in the same room and NO duct between them → orbit/cutaway and confirm behind the wall a rectangular MRT reducer/trunk stub AND a separate, visibly smaller circular PTS tube stub, both HOLLOW (visible inner passages), both belonging to the same vestibule → Fit / Hide-Show / Lock-Unlock / Delete → 2D plan shows one wall-integrated vestibule marker → refresh persists → delete → cyclotron remains → refresh stays absent.

**Do not self-accept.** Do not begin PTS/MRT/RTHS/AGV routing, carrier animation, dispatching/scheduling, travel-time calculation, or Build 2. Await explicit visual acceptance.

# EVI-MA-05B — Wall-Integrated Vestibule Correction + Universal 3D Right-Click Equipment Action

**Status:** implementation complete · `manual_acceptance = PENDING` (do not self-accept)
**Type:** manual-acceptance correction following EVI-MA-05A. Fixes exactly two proven defects and their required regression behavior. No transport routing/animation (that is Build 2).

---

## 1. Reconcile (before any edit)

| Field | Value |
|---|---|
| Branch | `main` |
| HEAD | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| origin/main | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| Divergence | 0 ahead / 0 behind |
| Test baseline (start) | 77 files / 1217 tests passing (EVI-MA-05A) |

All uncommitted EVI work preserved; no reset/revert/ZIP, no architecture duplication.

## 2. Proven manual defects

- **Defect A — placement/presentation.** The live Radiopharmacy Logistics Vestibule appeared as a large freestanding rectangular mass inside the cyclotron room, rather than an ATM-like wall-integrated interface.
- **Defect B — direct interaction.** Right-click quick actions (esp. a fast Delete) did not work consistently for all application-owned assets; the vestibule had no right-click menu at all.

Automated tests passing did not make the placement acceptable — the live manual test is authoritative, and this build treats it as such.

---

## 3. Defect A — root cause + wall-frame correction

**Root cause.** `seedWallIntegratedPose` placed the vestibule *center* `depth/2` INSIDE the room from the wall edge, and oriented the rear/ports toward the wall. So the whole port-bearing assembly floated in the room and only the rear touched the wall — the opposite of ATM integration.

**Fix — explicit wall coordinate frame.** Added `WallFrame` (`origin`, `tangent`, `roomInwardNormal`, `wallOutwardNormal` with `wallOutwardNormal = -roomInwardNormal`) and `wallFrameForSide(footprint, wallSide)`. `seedWallIntegratedPose` now derives the pose from that frame:
- pose center = `wallOrigin + wallOutwardNormal · (depth/2)` — so the FRONT access face lands flush on the room-side wall plane and the body extends OUTWARD (behind the wall);
- yaw is computed from `roomInwardNormal` (`atan2(roomInwardX, -roomInwardY)`), not a hard-coded per-side guess.

Consequently `frontFacePlaneFromPose` lands the front face exactly on the wall plane with its normal pointing into the room, and the housing rear + wall sleeve + rear manifold + MRT reducer/trunk + PTS adapter/tube all sit on the wall-outward side. Only the shallow fascia/door/handle/HMI (drawn a few cm forward of the front face) project into the room.

The wall frame is persisted on `wallReference.frame` (deep-copied in `toSafeInstance`), so the identical wall-integrated pose reconstructs after reload.

## 4. Room-side vs behind-wall collision (§9)

Collision now distinguishes room-side occupancy from the proposed through-wall geometry:
- `reservedVolumeFromPose(pose)` returns only the SHALLOW room-side access slab (full width/height, ~0.35 m into the room from the wall plane) — this is what must not overlap equipment.
- `fullOccupiedVolumeFromPose(pose)` (new) is the full room-side + behind-wall AABB, kept for reference and used for context picking.

So an intended wall penetration is never rejected as an ordinary collision, while a genuine room-side overlap (equipment at the access face) still is. `wallRelationshipStatus` stays `PROPOSED_WALL_PENETRATION`; the Bentley wall is never modified.

## 5. Hollow-passage preservation (§3, §14–§16)

The EVI-MA-05A hollow doctrine is untouched: the vestibule chamber recess, rear manifold, MRT large rectangular section + four planar reducer faces + trunk stub, and the separate circular PTS adapter/tube remain hollow with distinct OUTER (structural/collision) vs INNER (carrier-clearance) geometry. The correction changed only the pose placement + collision slab, not the recipe's part semantics.

---

## 6. Defect B — universal 3D right-click

**Governing rule implemented:** if the user can see an application-owned equipment/logistics object in 3D, they can right-click it.

- **Vestibule context-menu store** added to the overlay (`openVestibuleContextMenu` / `closeVestibuleContextMenu` / `subscribeVestibuleContextMenu` / `getVestibuleContextMenu`), mirroring the equipment menu store; opening it selects the exact vestibule and closes the equipment/asset menus (one selection).
- **`ViewerVestibuleContextMenu.tsx`** (new) — title "Radiopharmacy Logistics Vestibule", commands Fit to Vestibule / Lock-Unlock / Hide-Show / Delete, all dispatching to the SAME overlay vestibule lifecycle. No `window.confirm` (proven to fail in the viewer host); Delete is disabled while locked with Unlock available (never a silent no-op).
- **Pick resolution:** `pickVestibuleForContext(ray, vestibules, selectedId)` + `rayIntersectAabb` test the FULL occupied volume, so a right-click on ANY visible component (fascia, door, HMI, sleeve, manifold, MRT reducer/stub, PTS adapter/tube) resolves the ONE `vestibuleInstanceId`. Selection-aware (prefer the selected object when the ray hits it, else nearest); hidden vestibules excluded.
- **Tool wiring** (`MrtDirectManipulationTool`): both the persistent capture-phase contextmenu bridge (`onViewportContextMenu` via `locateVestibuleAtClient`) and `onResetButtonUp` (via `locateVestibuleTarget`) check vestibule BEFORE equipment (separate pick maps guarantee no cross-resolution), open the vestibule menu, and suppress the browser menu only for an app-owned hit. Esc / empty / delete close the vestibule menu. The bridge re-installs idempotently so right-click survives orbit/pan/zoom/Fit/viewport remount and does not depend on the Clinical Program panel.
- **Universality:** scanner (legacy `AssetInstance` → asset context menu), cyclotron (`EquipmentAssetInstance` → equipment menu), and vestibule (`ClinicalLogisticsVestibuleInstance` → vestibule menu) all right-click; each menu titles the exact target. The architecture extends to future service-class vestibules with no new interaction code.
- **BIM protection (§29):** native walls/floors/ceilings/doors/furniture never resolve to any app pick map, so no application Delete is offered for authoritative BIM.

Right-click is the fast path; the floating SELECTED EQUIPMENT / SELECTED VESTIBULE controls remain the deterministic fallback, and both paths call the same lifecycle functions (no duplicated logic).

## 7. One pick identity per instance (§18) + Delete convergence (§22–§25)

Each object's every visible subcomponent + envelope resolves to the one authoritative id (scanner/cyclotron/vestibule). All Delete surfaces (right-click, floating control) converge on the single authoritative lifecycle: `deleteEquipment(exactId)` for equipment, `deleteVestibule(exactId)` for vestibules — each removes exactly one instance and all derived representations (geometry, envelope, label, 2D marker, ports, collision reservation, floating control), persists, and does not resurrect. Deleting one cyclotron never deletes another; deleting the vestibule leaves the cyclotron and BIM wall intact and orphans no ports.

---

## 8. Files changed

**New**
- `frontend/src/components/spatial/ViewerVestibuleContextMenu.tsx`
- `frontend/src/tests/eviMa05bWallIntegrationRightClick.test.ts` (15 tests)

**Modified**
- `clinicalLogisticsVestibule.ts` — `WallFrame` + `wallFrameForSide`; corrected `seedWallIntegratedPose`; `reservedVolumeFromPose` (shallow room-side slab) + new `fullOccupiedVolumeFromPose`; persisted `wallReference.frame`; `pickVestibuleForContext` + `rayIntersectAabb`.
- `spatialAssetOverlay.ts` — vestibule context-menu store; `deleteVestibule` closes its menu.
- `MrtDirectManipulationTool.ts` — `locateVestibuleAtClient` (bridge) + `locateVestibuleTarget` (reset) checked before equipment; vestibule menu open; Esc/empty/delete close it.
- `BentleyViewer.tsx` — mount `ViewerVestibuleContextMenu`.

## 9. Tests

`eviMa05bWallIntegrationRightClick.test.ts` (15) proves the placement correction (wall frame `roomInward = -wallOutward`; front face flush with the wall plane; body behind wall; shallow room-side reserved slab < full depth; fabricated ports on the wall-outward side for whichever wall is chosen; penetration is not a collision but a real room overlap is; `PROPOSED_WALL_PENETRATION` + persisted frame; reload reconstructs the pose; EVI-MA-05A port semantics unchanged) and the universal pick (`pickVestibuleForContext` resolves the one id from the full occupied volume; selection-preference; nearest; hidden excluded; miss → none; `rayIntersectAabb` hit/miss).

> Honesty note: the actual on-screen wall-integration, the camera Fit, and live 3D/2D right-click in the running viewer are not headlessly verifiable. The wall-frame math, collision distinction, pick resolution, menu store, and delete convergence are verified by tests + typecheck + build. On-screen confirmation is the manual step below.

## 10. Verification

| Check | Result |
|---|---|
| `npx tsc -b` | PASS (0 errors) |
| Full frontend suite | **78 files / 1232 tests — all pass** (was 77 / 1217; +1 file, +15 tests) |
| `npm run build` | PASS (pre-existing INEFFECTIVE_DYNAMIC_IMPORT + chunk-size warnings only) |
| `/viewer` on :3000 | 200 |

Dev server left running on **port 3000**.

## 11. Manual acceptance — `manual_acceptance = PENDING`

**Vestibule (§37):** Fit the cyclotron (V2 unchanged) → create/select the Radiopharmacy vestibule → Fit. From inside the room the access face reads as built INTO the wall (only shallow room-side depth; door/HMI/status recognizable; materials visible; no freestanding box; no cyclotron duct). Bird's-eye/cutaway/service-side shows the wall sleeve → rear manifold → hollow MRT rectangular section → planar reducer → MRT trunk stub, and separately the PTS adapter → hollow circular PTS tube — clearly different sizes/shapes, behind the wall. 2D plan keeps the wall-integrated marker; refresh returns the identical pose.

**Right-click (§38):** right-click a scanner, a cyclotron body, and each vestibule component (fascia, transfer door, MRT service-side, PTS tube) — each opens a menu titled with the exact target, with Fit / Hide-Show / Lock-Unlock / Delete; Delete is a reliable fast path (no browser dialog), disabled only while locked with Unlock available. Deleting a test cyclotron removes only that instance; deleting the vestibule leaves the cyclotron and wall.

**BIM protection (§39):** right-clicking wall/floor/ceiling/door/native furniture exposes no application Delete.

**Do not self-accept.** Do not begin PTS/MRT/RTHS/AGV routing, carrier/capsule animation, dispatch/scheduling, travel-time calculation, or Build 2. Await explicit confirmation that the vestibule is correctly wall-integrated, the rear MRT/PTS branches are hollow and correctly positioned behind the wall, right-click works for scanner/cyclotron/vestibule, quick Delete is reliable, BIM is protected, and persistence works.

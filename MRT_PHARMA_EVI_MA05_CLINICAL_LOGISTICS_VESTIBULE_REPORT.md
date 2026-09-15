# EVI-MA-05 FINAL — Common Clinical Logistics Vestibule Family + Radiopharmacy Dual MRT/PTS Interface + Origin-Service Foundation

**Status:** implementation complete · `manual_acceptance = PENDING` (do not self-accept)
**Supersedes:** all earlier EVI-MA-05 / EVI-MA-05R vestibule prompts and doctrines.
**Scope:** establishes the ONE reusable wall-integrated clinical logistics vestibule family, the service-class taxonomy, the transport-port configuration policy, and the fully demonstrated Radiopharmacy dual-port instance. **Physical interfaces only.** No transport routing, no carrier/capsule animation, no MRT backbone, no RTHS, no AGV/AMR simulation, no Build 2 optimization.

---

## 1. Reconcile (before any edit)

| Field | Value |
|---|---|
| Branch | `main` |
| HEAD | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| origin/main | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| Divergence | 0 ahead / 0 behind |
| Working tree | 106 uncommitted paths preserved (all prior EVI work) — no reset, no revert, no ZIP reconstruction |
| Test baseline | 75 files / 1169 tests all passing |

EVI-MA-04 cyclotron V2, canonical identities, selection, Fit, Hide/Show, Lock/Unlock, Delete, persistence, collision exclusivity, 2D plan, walkthrough, Bentley auth lifecycle and Clinical Program state are all preserved.

---

## 2. Superseded doctrines (NOT implemented)

Per §2 of the prompt, the following earlier concepts were explicitly **not** implemented:
- A. cyclotron → dedicated duct across the cyclotron room → vestibule.
- B. cyclotron room → wall → vestibule in an **adjoining** BIM room.
- C. one MRT vestibule + one separate PTS vestibule for the same service point.
- D. vestibule mandatorily beside the cyclotron.

The EVI-MA-04 `equipmentAdjacency.ts` module (which encoded the now-superseded adjoining-room concept B) was left untouched so EVI-MA-04's own tests still pass, but it is **not used** by EVI-MA-05. The new same-room, wall-integrated doctrine is authoritative and lives in a new module.

---

## 3. Governing architecture

ONE reusable visual/spatial family: **`CLINICAL_LOGISTICS_VESTIBULE_V1`** — the controlled interface between a clinical/service room and the future automated transport infrastructure.

```
CLINICAL ROOM
     │
     ▼
┌──────────────────────────┐
│ CLINICAL LOGISTICS        │  front clinical access face (local -Y, toward room)
│ VESTIBULE                 │  transfer chamber / controls / status
└────────────┬─────────────┘
             │ WALL  (proposed penetration; BIM wall immutable)
             ▼
       REAR MANIFOLD
          ├── permitted transport port A (e.g. MRT)
          ├── permitted transport port B (e.g. radiopharm-qualified PTS)
          └── future permitted ports (reserved)
```

The visual family is reusable; each placed vestibule is an independent application-owned instance with its own id, service class, parent room, pose, wall relationship, allowed payloads, ports, visibility, lifecycle, reserved volume and persistence record.

---

## 4. Service-class taxonomy (WHAT function occurs here)

`clinicalLogisticsVestibule.ts` defines `ServiceClass`: `RADIOPHARMACY`, `PHARMACY`, `LABORATORY`, `STERILE_CLEAN_SUPPLY`, `LAUNDRY_LINEN`. The taxonomy is kept extensible — future classes (`CENTRAL_SUPPLY`, `MATERIALS_MANAGEMENT`, `BLOOD_BANK`, `WASTE_SOILED_MATERIAL`, `KITCHEN_NUTRITION`) are documented as a string list, not over-built.

A **service class** answers *what clinical logistics function occurs here*; a **transport port** answers *how payloads leave or arrive*. They are distinct concerns.

---

## 5. Transport-port configuration policy (HOW payloads move)

`permittedPortsForServiceClass()` is the single authoritative policy. Nuclear/radiopharmaceutical PTS qualification is **never** auto-inherited.

| Service class | MRT | PTS | Reserved (not built now) |
|---|---|---|---|
| RADIOPHARMACY | STANDARD (fabricated) | **RADIOPHARMACEUTICAL_QUALIFIED** (fabricated) | — |
| PHARMACY | STANDARD (fabricated) | CONVENTIONAL_CLINICAL (fabricated) | — |
| LABORATORY | STANDARD (fabricated) | CONVENTIONAL_CLINICAL (fabricated) | — |
| STERILE_CLEAN_SUPPLY | STANDARD (fabricated) | none | RTHS |
| LAUNDRY_LINEN | HEAVY_GENERAL (fabricated) | none | AGV/AMR + RTHS |

Sterile bulky payloads never get a small PTS tube; linen never gets a conventional PTS tube. The Radiopharmacy upstream is abstracted as the marker `RADIOPHARMACEUTICAL_PRODUCT_AVAILABLE_AT_VESTIBULE_INPUT` — there is **no** cyclotron-to-vestibule duct.

---

## 6. Standardized vestibule visual (`CLINICAL_LOGISTICS_VESTIBULE_V1`)

Medium-LOD, representative (NOT manufacturer CAD), wall-integrated (ATM-like). Part counts are within the 15–30 band for every configuration:

| Configuration | Parts |
|---|---:|
| Front face + wall + manifold (always) | 15 |
| + MRT branch | +7 |
| + PTS branch | +3 |
| **Radiopharmacy / Pharmacy / Lab (MRT + PTS)** | **25** |
| **Sterile (MRT only)** | **22** |
| **Laundry (MRT heavy only)** | **22** |

**Front clinical access face** (local -Y, toward the room): `CLV_WALL_FASCIA`, `CLV_HOUSING`, `CLV_TRANSFER_DOOR`, `CLV_TRANSFER_APERTURE`, `CLV_HANDLE`, `CLV_HMI`, `CLV_STATUS_GREEN`, `CLV_STATUS_AMBER`, `CLV_STATUS_RED`, `CLV_ESTOP`, `CLV_SERVICE_PANEL`, `CLV_SERVICE_LABEL`, `CLV_BASE`.

**Wall penetration + rear manifold** (local +Y, behind the wall): `CLV_WALL_SLEEVE`, `CLV_REAR_MANIFOLD`.

**MRT rear branch:** `CLV_MRT_MANIFOLD_SECTION` (large rectangular section) → **four planar `CLV_MRT_REDUCER_FACE` boxes** (a fabricated rectangular reducer — not a cone, not a rounded nozzle, not chamfering) → `CLV_MRT_TRUNK_STUB` → `CLV_MRT_TRUNK_PORT`.

**PTS rear branch:** `CLV_PTS_ADAPTER` → `CLV_PTS_TUBE_STUB` (a **cylinder** — reads clearly as a circular tube system) → `CLV_PTS_PORT` (circular).

All primitives scale parametrically from the pose; yaw orients the front face against the chosen wall.

---

## 7. Color standard (distinct from the cyclotron)

Restrained MRTway clinical palette, added to the shared `EQUIPMENT_PART_COLOR` map (so both decorators stay consistent): muted sage / pale clinical-green housing (`CLV_HOUSING [178,196,182]`), stainless/metallic-gray transfer door, dark charcoal HMI, dark neutral base, metallic/neutral rear manifold, green/amber/red status indicators, restrained accent. No whole-machine cyan, not neon, not identical to the cyclotron. Selection preserves per-part materials and applies only the thin outline (`EQUIPMENT_SELECTION_OUTLINE`) + translucent envelope — the EVI-MA-04 selection contract, reused unchanged.

---

## 8. Radiopharmacy dual-port configuration (fully demonstrated)

The Radiopharmacy vestibule exposes **two distinct physical ports on ONE vestibule**:

1. `MRT_PORT` — rectangular reducer/transition → short MRT trunk stub → `MRT_TRUNK_CONNECTION_PORT` (rectangular cross-section, standard config).
2. `RADIOPHARMACEUTICAL_QUALIFIED_PTS_PORT` — compact adapter → short circular tube stub → `PTS_CONNECTION_PORT` (circular cross-section, `ptsQualification = RADIOPHARMACEUTICAL_QUALIFIED`).

They are separate physical + logical interfaces with distinct `portId`s and distinct cross-sections; they never share a conduit. Both are short stubs with `status = UNCONNECTED` — no routing, no diverters, no blowers, no animation. The vestibule shares the cyclotron's `parentBimSpaceId` and is wall-integrated (not seeded at the cyclotron, not centroid-placed).

---

## 9. Origin-service foundation for the other four classes

Each other service class is a distinct instance built from the SAME family via `createVestibuleInstance` + `permittedPortsForServiceClass`:
- Pharmacy / Laboratory: MRT + conventional PTS (never nuclear-qualified).
- Sterile/Clean Supply: MRT only now; RTHS reserved.
- Laundry/Linen: MRT heavy/general only now; AGV/AMR + RTHS reserved.

Where a room is too narrow/short to host a wall-integrated vestibule, the factory returns an honest failure (`NO_DEFENSIBLE_WALL` / `ROOM_TOO_SHORT`) rather than fabricating a room.

---

## 10. Application-owned instance model + persistence

`ClinicalLogisticsVestibuleInstance`: `vestibuleInstanceId`, `iModelId`, `serviceClass`, `parentBimSpaceId`, `sourceClinicalContextId`, `displayLabel`, `visualFamily`, `wallReference` (side + length), `pose`, `frontFacePlane`, `reservedVolume`, `hidden`, `lifecycleState`, `wallRelationshipStatus = PROPOSED_WALL_PENETRATION`, `transportPorts[]`.

Each `VestibuleTransportPort`: `portId`, `vestibuleInstanceId`, `transportFamily`, `ptsQualification?`/`mrtConfiguration?`, `position`, `orientation`, `crossSection`, `status`, `fabricated`.

Persistence mirrors the accepted `equipmentInstance` doctrine: iModel-scoped key (`mrtpharma.vestibule.v1.<iModelId>`), a key allowlist, a forbidden-key guard (rejects `mesh`/`vertices`/`triangles`/token-like keys), round-trips deterministically, and never stores a rendered mesh. The Bentley iModel wall is never cut/deleted/renamed.

---

## 11. Wall placement

`enumerateWallCandidates` returns the four axis-aligned walls longest-first; `seedWallIntegratedPose` hugs the chosen wall with the front face toward the room interior and the rear manifold toward/through the wall. Placement is **never** the room centroid (tested). For Radiopharmacy the vestibule stays in the cyclotron's room but is not optimized for shortest cyclotron distance — any defensible wall (incl. the opposite wall) is acceptable.

---

## 12. Files

**New**
- `frontend/src/components/spatial/clinicalLogisticsVestibule.ts` — taxonomy, port policy, instance model, wall placement, port construction, safe persistence.
- `frontend/src/tests/eviMa05ClinicalLogisticsVestibule.test.ts` — 27 tests.

**Modified**
- `frontend/src/components/spatial/equipmentGeometry.ts` — added the `CLINICAL_LOGISTICS_VESTIBULE_V1` family, the `CLV_*` part roles + palette entries, `buildClinicalLogisticsVestibuleParts`, the `vestibulePorts` option threaded through `buildEquipmentParts` + `computeEquipmentWorldBounds`, and the dispatch case.

The decorators (`ClinicalProgramDecorator`, `SpatialAssetDecorator`) required no change — `drawEquipmentVisual` already renders any family via the shared palette + outline-only selection, and the palette map now covers every `CLV_*` role.

---

## 13. Verification (this build)

| Check | Command | Result |
|---|---|---|
| Typecheck | `npx tsc -b` | PASS (0 errors) |
| EVI-MA-05 suite | `npx vitest run eviMa05...` | 27 passed |
| Full frontend suite | `npx vitest run` | **76 files / 1196 tests — all pass** (was 75 / 1169; +1 file, +27 tests) |
| Production build | `npm run build` | PASS (pre-existing INEFFECTIVE_DYNAMIC_IMPORT + chunk-size warnings only) |
| Live viewer | `curl /viewer` on :3000 | **200** |

Dev server left running on **port 3000**.

---

## 14. Honesty / scope notes

- Live 3D appearance cannot be verified headlessly. The geometry recipe, taxonomy, port policy, instance model, wall placement and persistence are all verified by tests + typecheck + build. The rendered vestibule's on-screen appearance is the manual step below.
- The `CLINICAL_LOGISTICS_VESTIBULE_V1` family is render-ready through the existing `drawEquipmentVisual` path (shared palette, outline-only selection). Wiring the **live overlay lifecycle of vestibule instances** (a dedicated overlay store, selection card, pick ids and BentleyViewer persistence sync) is intentionally **deferred**, consistent with the prior vestibule builds and with this prompt's "physical interfaces only" scope. This build delivers the reusable family + full domain/port/persistence foundation and the fully demonstrated Radiopharmacy dual-port configuration, which is the mandatory acceptance target (§25).

---

## 15. Manual acceptance steps — `manual_acceptance = PENDING`

1. Confirm the family reads as a **wall-integrated controlled clinical logistics transfer interface** (front fascia, shielded transfer door + aperture, handle, HMI, green/amber/red status, e-stop, lower service panel), visually distinct from the cyclotron (sage clinical palette, not cyan/blue, not a freestanding center-of-room box).
2. Confirm the rear manifold exposes **two distinct ports** for Radiopharmacy: a rectangular MRT reducer/trunk stub and a **circular** radiopharmaceutical-qualified PTS tube stub — separate interfaces, not one shared conduit.
3. Confirm no cyclotron-to-vestibule duct is implied; the vestibule is wall-integrated in the radiopharmacy room, not seeded at the cyclotron.
4. Confirm selection preserves materials (outline + envelope only).
5. **Do not self-accept.** Do not begin PTS/MRT/RTHS routing, carrier/capsule animation, AGV/AMR simulation, or Build 2 transport optimization.

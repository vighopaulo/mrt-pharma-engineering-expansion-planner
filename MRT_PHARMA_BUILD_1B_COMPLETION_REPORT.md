# MRT Pharma — Build 1B Completion Report

## Complete Clinical Program + Canonical Equipment / Engineering-Authority Binding

**Completion gate:** `MANUAL_CONFIRMATION_REQUIRED` — the engineering integration
is implemented, source-verified, and fully automated-test covered. The §21 manual
acceptance (place a scanner, a production/source equipment model, and one more
equipment type, in an assigned clinical space, and confirm the binding both
locates it physically AND surfaces its canonical engineering identity) is a
browser-only, user-performed step. It is **not** self-certified here. No git
stage / commit / push was performed. Authority docs are **not** flipped to
"BUILD 1B — COMPLETE" (see §9).

This report is the consolidating Build 1B completion record. It does **not**
rewrite the prior Build 1B provenance reports; they remain the historical record
of each increment.

---

## 1. Baseline (reconciled, actual current tree)

| | |
|---|---|
| HEAD | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| origin/main | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| Divergence | `0 ahead / 0 behind` (branch `main`) |
| `frontend/.env` | modified + **unstaged** (pre-existing; never touched by this build) |
| Tracked `.py` changed | **0** |
| Authority docs changed | **0** |

Build 1A (COMPLETE, manually accepted, committed, pushed) was **not** reopened,
reverted, or reconstructed. Build 2 was **not** started.

---

## 2. What Build 1B is

Build 1B is an **integration build**. It connects three systems that already
exist in the repository so that placed equipment carries BOTH a physical/spatial
identity AND a canonical engineering identity:

1. the **clinical spatial authority** — `ClinicalPlanningVolume` + exact BIM room
   footprints + closed-mesh containment (Build 1A);
2. the **canonical equipment catalogs** — the backend cyclotron / generator /
   scanner catalogs (the single source of truth for identity, envelope,
   capacity, production, cost);
3. the **engineering / cost authorities** — cyclotron installation CapEx anchor,
   scanner CapEx anchor, MRT vestibule / light-MRT endpoint spatial-cost
   authorities.

No system was rebuilt. No second equipment system was created (see §3).

---

## 3. Reuse — not a second equipment system (§2 doctrine)

The app-owned binding object `EquipmentAssetInstance`
(`frontend/src/components/spatial/equipmentInstance.ts`) is the equipment
analogue of `ClinicalPlanningVolume`. It **reuses**, and does not duplicate,
existing systems:

- Envelope geometry + containment reuse the accepted planning-volume primitives
  (`buildOrientedPlanningPrism`, `validatePlanningVolumeContainment`,
  `resolveContainmentStatus`, `seedPrismParamsFromParent`) so containment is
  evaluated against the room's **exact closed mesh** by sampling corners + edges
  + anchor — **not** center-only.
- Equipment identity is **by reference** to the backend `catalog_model_id`; the
  spatial layer never copies a canonical numeric value.
- It reuses the existing `domain/assets` type vocabulary (`AssetFamily`,
  `DimensionProvenance`) rather than inventing a parallel taxonomy.

The pre-existing generic-geometry `AssetInstance` / `SpatialAssetStore` system is
project-scoped generic asset placement; it is **not** tied to
`ClinicalPlanningVolume` or the canonical clinical equipment catalogs.
`EquipmentAssetInstance` is the integration layer between the clinical spatial
authority and the canonical catalogs — a legitimate, narrow, app-owned binding,
not a competing placement engine. `SECOND_PLACEMENT_STORE_CREATED = NO`.

---

## 4. Source-first canonical equipment audit (mirrored by reference)

`frontend/src/components/spatial/canonicalEquipmentCatalog.ts` is a
**by-reference** mirror of the three backend catalogs. Totals:

| Class | Catalog | Count |
|---|---|---|
| Cyclotron | `cyclotron_equipment_catalog.json` (schema 1.1) | **17** |
| Generator | `generator_equipment_catalog.json` (schema 1.0) | **4** |
| Scanner | `scanner_equipment_catalog.json` (schema 1.0) | **6** |
| **Total canonical equipment models** | | **27** |
| MRT facility spatial classes | `canonical_spatial_authority.py` + `shared_mrt_multistream_authority.py` | **2** |

`NEW_UNAUTHORIZED_EQUIPMENT_CLASSES = 0`.

**Calibrated physical envelopes exist ONLY for:** `IBA_CYCLONE_KEY`
(1.5 × 1.4 × 1.35 m, manufacturer-calibrated), `IBA_CYCLONE_KIUBE`
(1.9 × 1.9 × 1.8 m, manufacturer-calibrated), `ACSI_TR_24` (1.8 × 1.8 × 2.5 m,
site-calibrated). Every other model carries an honest, clearly-labelled
`GENERIC_ENGINEERING_PLACEHOLDER` envelope (drawn only so a proxy box exists) and
its physical dimensions remain **NOT_CALIBRATED**.

`FABRICATED_COSTS = NO`. `FABRICATED_CAPACITY = NO`. `FABRICATED_DIMENSIONS = NO`.
Where the backend records a value as NOT_CALIBRATED, the mirror **preserves**
NOT_CALIBRATED (e.g. `SUMITOMO_CYPRIS_MP_30` supports F-18 but has no calibrated
production record → production crosswalk `NOT_CALIBRATED`, never borrowed). The
crosswalk carries **authority-id pointers only**, never the numeric value.

---

## 5. §24 completion gate — item-by-item (source-verified)

| # | Gate item | Status | Evidence |
|---|---|---|---|
| 1 | Clinical program is spatial | IMPLEMENTED | `ClinicalProgramControl.tsx` + `ClinicalProgramDecorator.ts` render real world geometry |
| 2 | `ClinicalPlanningVolume` is the authoritative clinical space | IMPLEMENTED | Equipment parents to it; reuses its primitives |
| 3 | Equipment parented to the clinical space | IMPLEMENTED | `parentBimSpaceId` + optional `parentClinicalPlanningVolumeId` |
| 4 | Parent BIM room identity preserved | IMPLEMENTED | `parentBimSpaceId` retained; binding never mutates the room |
| 5 | Exact canonical identity preserved | IMPLEMENTED | `canonicalEquipmentId == catalog_model_id`; rejects unknown ids |
| 6 | Generic geometry is visualization-only | IMPLEMENTED | Envelope is a proxy box; provenance disclosed |
| 7 | Containment enforced (not center-only) | IMPLEMENTED | Reuses corner+edge+anchor containment; test proves a protruding corner FAILs |
| 8 | Invalid placement not lockable | IMPLEMENTED | `canLockEquipment` blocks on FAIL / NOT_EVALUATED |
| 9 | Scanner / production crosswalk (by reference) | IMPLEMENTED | `capacity/production/cost` crosswalk pointers; no backend HTTP |
| 10 | NOT_CALIBRATED preserved | IMPLEMENTED | Placeholder envelope + NOT_CALIBRATED crosswalks retained |
| 11 | No synthetic values | IMPLEMENTED | No numeric canonical value copied into the frontend |
| 12 | Persistence + reload | IMPLEMENTED | `mrtpharma.equipment.v1.<iModelId>`; reload recomputes containment |
| 13 | iModel isolation | IMPLEMENTED | Per-iModel storage key; switch clears |
| 14 | Lifecycle (DRAFT / LOCKED) | IMPLEMENTED | Lock gate; restore / reset; last-known-valid |
| 15 | Invalid visual cue not colour-only | IMPLEMENTED | Red + dashed thick edges + "⚠ … OUTSIDE ROOM" badge |
| 16 | Lock disabled with a visible reason | IMPLEMENTED | `equipmentValidation` lock-disabled reason surfaced in UI |
| 17 | Restore valid position / reset to parent-derived | IMPLEMENTED | `restoreEquipmentPlacement` / `resetEquipmentToParentDerived` |
| 18 | Honest proxy / approximate-parent labelling | IMPLEMENTED | "(proxy envelope)" + approximate-parent disclosure |
| 19 | Transport-endpoint spatial authority recorded | IMPLEMENTED | `getMrtFacilitySpatialAuthority` (vestibule / endpoint, by reference) |
| 20 | No Bentley write | IMPLEMENTED | App-owned only; diagnostic asserts `BENTLEY_WRITE = NONE` |
| 21 | No Build 2 routing / simulation / optimizer | HELD (correct) | Build 1B binds only; no route / mission / simulation generated |
| 22 | Not developer-gated (product surface) | IMPLEMENTED | Equipment section is always shown, not dev-gated |
| 23 | Diagnostic asserts no fabrication | IMPLEMENTED | `FABRICATED_COSTS=NO` / `FABRICATED_CAPACITY=NO` / `BENTLEY_WRITE=NONE` |
| 24 | §21 manual acceptance (browser) | `MANUAL_CONFIRMATION_REQUIRED` | User-performed; cannot self-certify |

Gate items 1–23 are IMPLEMENTED / correctly HELD. Item 24 is the manual
acceptance step and remains open by design.

---

## 6. Verification (this session, current tree)

| Check | Result |
|---|---|
| `npx tsc -b` | **PASS** |
| Full isolated suite (`npm run test`) | **1010 / 1010 tests pass** across **61 files**, 0 failures |
| Build 1B equipment tests | `build1bEquipmentBinding.test.ts` (42 pure) + `build1bEquipmentBindingUi.test.tsx` (7 UI) — all pass, none weakened |
| `npm run build` | **PASS** (only benign chunk-size + ineffective-dynamic-import advisories) |
| Worker asset | `dist/scripts/parse-imdl-worker.js` → `(()=>{"use strict";f` (real) |
| Draco WASM | `dist/scripts/draco_decoder.wasm` magic `0061 736d` (valid) |
| `@itwin/core-frontend` | 5.12.5 |
| `/viewer` HTTP | **200** (dev server restarted cleanly on `http://localhost:3000`) |
| Tracked `.py` changed | 0 (crosswalk is reference-only → no backend test run warranted) |

No hidden, skipped, or weakened tests. The suite count (61 files / 1010 tests) is
well above the §20 baseline (51 files / 815 tests).

---

## 7. §19 test coverage (mapped)

`build1bEquipmentBinding.test.ts` + `build1bEquipmentBindingUi.test.tsx` cover:
canonical identity + counts (17 / 4 / 6 / 27 / 2); calibration honesty (only 3
calibrated envelopes; NOT_CALIBRATED preserved; placeholder disclosed;
`SUMITOMO_CYPRIS_MP_30` production NOT_CALIBRATED); parent binding (id embeds
iModel + room + canonical id; rejects unknown id / missing parent); envelope
containment **not** center-only (protruding corner FAILs; no mesh → NOT_EVALUATED);
lock lifecycle (blocked when outside / not evaluated; allowed when contained);
last-known-valid restore + reset; multi-instance isolation; safe persistence +
iModel isolation (rejects forbidden keys; strips mesh; rejects fabricated
canonical id on reload); by-reference crosswalk (authority ref + calibration, no
value); and the not-dev-gated UI (inventory, place, FAIL warning + lock-disabled
reason, restore / reset / delete, crosswalk readout).

---

## 8. Prior Build 1B UX add-ons — separate, deferred (not part of this gate)

Later Build 1B increments added Walkthrough targeted-spawn / navigation, a
simultaneous true-2D plan projection + panel, and a walkthrough trail. Those are
**IMPLEMENTED_AND_AUTOMATED_TESTED but MANUAL_ACCEPTANCE_FAILED** and were
explicitly deferred for UX hardening (see
`MRT_PHARMA_BUILD_1B_UX_DEFERRED_ACCEPTANCE_REPORT.md`). They are visual /
manual-inspection aids only and are **not** simulation, routing, or optimization
authorities. They are preserved, not rolled back, and are **not** part of the
equipment / engineering-binding completion gate covered by this report.

Deferred open gaps (unchanged, still open):
`GAP_WALKTHROUGH_NAVIGATION_RELIABILITY`,
`GAP_TRUE_2D_PLAN_RUNTIME_ROOM_HYDRATION`,
`GAP_WALKTHROUGH_TRAIL_PRODUCT_USABILITY`.

---

## 9. Authority-doc disposition (deliberately held)

The authority index / open-gaps / build-ledger were **not** flipped to
"BUILD 1B — COMPLETE" / "BUILD 2 — LIVE SPATIAL ROUTING". Reason:

- The equipment / engineering-binding engineering is implemented and
  automated-test complete, but the §21 manual acceptance is a browser-only,
  user-performed confirmation that cannot be self-certified; and
- the sibling Build 1B UX add-ons have failed manual acceptance and remain
  deferred.

Flipping the authoritative build ledger now would overstate completion. The
honest recorded state is `BUILD_1B_COMPLETION_GATE = MANUAL_CONFIRMATION_REQUIRED`
/ `CHECKPOINT = HOLD_FOR_BUILD_1B_MANUAL_ACCEPTANCE`. Upon your manual
acceptance, the ledger flip and the Build 2 entry can be made.

---

## 10. Scope review (git)

- Tracked `.py` changed: **0**. Authority docs changed: **0**.
- `frontend/.env`: pre-existing modification, never staged, never touched.
- New Build 1B binding modules: `canonicalEquipmentCatalog.ts`,
  `equipmentInstance.ts`, `equipmentValidation.ts` (+ the deferred UX modules).
- No second placement store. No Bentley write. No routing / simulation /
  optimizer. Build 2 not started.

---

## 11. Checkpoint

| | |
|---|---|
| `BUILD_1B_ENGINEERING_BINDING` | `IMPLEMENTED_AND_AUTOMATED_TESTED` |
| `BUILD_1B_COMPLETION_GATE` | `MANUAL_CONFIRMATION_REQUIRED` |
| `CHECKPOINT` | `HOLD_FOR_BUILD_1B_MANUAL_ACCEPTANCE` |
| `NEXT_MAJOR_BUILD` | `BUILD_2_LIVE_SPATIAL_ROUTING` (recorded; NOT started) |
| Authority docs | NOT updated (held for manual acceptance) |
| Git actions | NONE (no stage, no commit, no push) |

Machine-readable companion: `mrt_pharma_build_1b_completion_data.json`.

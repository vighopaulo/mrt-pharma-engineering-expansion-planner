# MRT Pharma — Build 1B Report

## Complete Clinical Program + Canonical Equipment / Resource Spatial Binding

**Completion gate:** `MANUAL_CONFIRMATION_REQUIRED` — this build is presented for
manual acceptance. No git stage / commit / push was performed. Authority docs are
NOT updated (deferred to manual acceptance per §73).

---

## 1. Baseline

Continued from the closed, accepted, committed, and pushed Build 1A:

| | |
|---|---|
| HEAD | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| origin/main | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| Divergence | `0 ahead / 0 behind` |
| Working tree at start | only `frontend/.env` modified (pre-existing; never touched) |

Build 1A was not reopened; no regression was demonstrated.

---

## 2. Source-first equipment audit (read directly from the backend catalogs)

The engineering/catalog layer is the **single source of truth**. The audit below
was read directly from the authoritative JSON this session, not recalled.

### Cyclotron — `cyclotron_equipment_catalog.json` (schema 1.1) — **17 models**

`GE_PETTRACE_840 / 860 / 880 / 890 / 800`, `IBA_CYCLONE_KEY / KIUBE / IKON / 30XP`,
`SUMITOMO_CYPRIS_HM_12 / HM_20 / MP_30`, `SIEMENS_CTI_ECLIPSE_HP / RDS_111`,
`ACSI_TR_19 / TR_24`, `BEST_14P`.

- **Calibrated physical envelope** only on: `IBA_CYCLONE_KEY` (1.5 × 1.4 × 1.35 m,
  manufacturer-calibrated), `IBA_CYCLONE_KIUBE` (1.9 × 1.9 × 1.8 m,
  manufacturer-calibrated), `ACSI_TR_24` (1.8 × 1.8 × 2.5 m, site-calibrated;
  +25 t, +180 kW site-calibrated). The other 14 cyclotrons carry **no** physical
  envelope → `NOT_CALIBRATED`.
- **Calibrated production (EOB MBq):** 840 = 240 000, 860 = 403 000, 880 = 524 000,
  890 = 648 000; `IBA_CYCLONE_KEY` = 111 000; `IBA_CYCLONE_KIUBE` = 1 406 000.
  `SUMITOMO_CYPRIS_MP_30` supports F-18 but has **no** production record →
  production `NOT_CALIBRATED` (never borrowed).
- **CapEx** is not in the catalog → `models.PlannerAssumptions.cyclotron_installation_capex`
  (study-level anchor). `FacilityCyclotronInstance` has **no** location field.

### Generator — `generator_equipment_catalog.json` (schema 1.0) — **4 models**

`CURIUM_TECHNELITE`, `CURIUM_ULTRA_TECHNEKOW_FM`, `GE_HEALTHCARE_DRYTEC`
(Mo-99 → Tc-99m); `ECKERT_ZIEGLER_GALLIAPHARM` (Ge-68 → Ga-68).

- `dimensions_cm` and `mass_kg` are **null** for every model → `NOT_CALIBRATED`.
- Economics all `NOT_CALIBRATED`. No geometry `AssetFamily` exists for a generator;
  the spatial envelope is a clearly-labelled proxy. `FacilityGeneratorInstance.location_object_id` exists.

### Scanner — `scanner_equipment_catalog.json` (schema 1.0) — **6 models**

SPECT: `SIEMENS_SYMBIA_PRO_SPECTA`, `GE_NM_CT_870_DR`, `GE_NM_CT_860`,
`PHILIPS_BRIGHTVIEW_XCT` (legacy installed base). PET: `GE_DISCOVERY_MI`,
`SIEMENS_BIOGRAPH_VISION`.

- `dimensions_footprint_notes` = `NOT_CALIBRATED`, power `NOT_CALIBRATED`, CapEx
  `NOT_CALIBRATED` (generic study-level scanner CapEx anchor applies).
  `FacilityScannerInstance.location_object_id` exists.

### MRT facility spatial classes (distinct cost authorities, §37)

| Class | Cost authority | Value |
|---|---|---|
| MRT radiopharmacy vestibule | `canonical_spatial_authority.MRT_VESTIBULE_CAPEX_USD` | $30,000 / vestibule (one per cyclotron interface requiring MRT transfer) |
| MRT endpoint (light-MRT panel) | `shared_mrt_multistream_authority.LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT` | $1,000 / endpoint (distinct from the $10,000 mainstream `PlannerAssumptions.endpoint_capex`) |

No double-count: the two are separate authorities.

**Totals:** 17 + 4 + 6 = **27 canonical equipment models** + **2 MRT facility
spatial classes**. `NEW_UNAUTHORIZED_EQUIPMENT_CLASSES = 0`.

**Equipment ↔ room compatibility authority does not exist** → `NOT_CALIBRATED`.
The `eligibleClinicalFunctions` mapping in the frontend mirror is an informational
binding hint only; it is never enforced.

---

## 3. What was built

All new spatial code is **pure / app-owned** and reuses the accepted Build 1A
room-volume + containment + validation-UX primitives. There is **no second
placement store** and **no Bentley write**.

### New modules

- **`canonicalEquipmentCatalog.ts`** — a by-reference frontend mirror of the 3
  canonical catalogs + the 2 MRT facility classes. Each entry carries
  `catalogModelId`, identity, a physical envelope (calibrated where the backend
  has it, otherwise a labelled `GENERIC_ENGINEERING_PLACEHOLDER`), and
  capacity / production / cost **crosswalk pointers** that name where the
  authoritative number lives — never the number itself. `FABRICATED_COSTS = NO`,
  `FABRICATED_CAPACITY = NO`.
- **`equipmentInstance.ts`** — the app-owned `EquipmentAssetInstance` domain:
  oriented-envelope build (reusing `buildOrientedPlanningPrism`), envelope
  containment against the exact parent room mesh (samples corners + edges +
  anchor, **not** center-only), floor-aware parent-derived placement seed,
  translate / rotate, lock gate, last-known-valid, restore / reset, and safe
  iModel-scoped persistence (`mrtpharma.equipment.v1.<iModelId>`).
- **`equipmentValidation.ts`** — the product-facing validation view model
  (`PASS` / `FAIL` / `NOT_EVALUATED`), warning that identifies the equipment and
  room, lock gate + reason, restore availability, honest approximate-parent and
  proxy-envelope labeling, the crosswalk readout, and the generic
  `DIAGNOSE SELECTED EQUIPMENT` report.

### Runtime + UI

- **`spatialAssetOverlay.ts`** — iModel-scoped equipment instances; place / move /
  rotate; live containment recompute + status cache; restore / reset; lock; delete;
  per-instance visibility; persistence; reload recompute; iModel-switch clear;
  capacity / production / cost crosswalk accessors; a transport-endpoint spatial
  authority accessor; and the generic equipment diagnostic. No Bentley writes.
- **`ClinicalProgramDecorator.ts`** — renders each equipment envelope as a true 3D
  world box. The invalid (containment `FAIL`) cue is **not colour-only**: red +
  dashed (`LinePixels.Code2`) thick edges + an "⚠ … — OUTSIDE ROOM" label badge.
  Proxy envelopes are labelled "(proxy envelope)".
- **`ClinicalProgramControl.tsx`** — a not-developer-gated Equipment section:
  canonical inventory (grouped Cyclotron / Generator / Scanner), place into the
  selected room, edit X / Y / Yaw, live validation warning, Lock disabled with a
  visible reason, Restore Valid Position, Reset to Parent-Derived, hide / show,
  delete, selection, and the by-reference crosswalk readout. The clinical-program
  summary now reports both the three-room proof and the full basic PET department
  required-vs-present functions.

---

## 4. Clinical program completion

- 20 clinical functions; multi-instance assignment supported.
- The panel surfaces the basic PET department required set
  (`RADIOPHARMACY`, `INJECTION_ROOM`, `UPTAKE_ROOM`, `PET_CT_SCANNER_ROOM`) as an
  informational required-vs-present summary. Completeness is **informational** and
  never auto-adds a room; the assigned program depends on the user's assignments
  in the active iModel.

---

## 5. Automatic-connectivity doctrine (recorded, not implemented)

Per §42, the normal workflow is **SIMULATE → infer missions → eligible modes →
auto-generate connections**, and `NORMAL_SIMULATION_REQUIRES_MANUAL_ROUTE_SELECTION
= NO`. Manual override is reserved for a future What-If / Engineering-Override.

Build 1B binds equipment/resources to BIM rooms spatially and records the
transport-endpoint spatial authority. It does **not** generate routes, run
simulation, or run the optimizer.

---

## 6. Verification

| Check | Result |
|---|---|
| `npx tsc -b` | PASS |
| Full isolated suite | **864 / 864 tests pass** across 53 files |
| Build 1A regressions | **0** (baseline 51 files / 815 tests → +2 files / +49 tests) |
| `npm run build` | PASS |
| Worker asset | `dist/scripts/parse-imdl-worker.js` → `(()=>{"use strict";f` (real) |
| Draco WASM | `dist/scripts/draco_decoder.wasm` magic `0061 736d` (real) |
| `@itwin/core-frontend` | 5.12.5 |
| `/viewer` HTTP | 200 (dev server running on `http://localhost:3000`) |

### New tests

- `build1bEquipmentBinding.test.ts` (42 pure): catalog audit (17 / 4 / 6 / 27 / 2;
  calibrated-envelope ids; no invented classes; bindable-family gate excludes
  SYNTHESIS / HOT_CELL / DOSE_CALIBRATOR), identity + iModel scope + parent binding,
  parent-derived floor-aware seed, translate / rotate, **envelope containment proven
  not center-only** (a 12 m box centred in a 10 m room `FAIL`s; no-mesh →
  `NOT_EVALUATED`), lock gate, last-known-valid restore / reset, multi-equipment
  isolation, safe persistence + iModel isolation, crosswalk by reference, diagnostic
  `FABRICATED_COSTS = NO` / `FABRICATED_CAPACITY = NO` / `BENTLEY_WRITE = NONE`.
- `build1bEquipmentBindingUi.test.tsx` (7 UI, not-dev-gated): inventory renders,
  place calls the overlay + row renders, `FAIL` warning identifies the equipment +
  Lock disabled with reason, Restore / Reset / Delete offered, Restore clears the
  warning + re-enables Lock, crosswalk shown by reference, Delete removes the row.

---

## 7. Scope review (git status)

- **0** Python files changed.
- **0** authority documents changed (`MRT_PHARMA_AUTHORITY_INDEX.md`,
  `MRT_PHARMA_OPEN_GAPS.md` untouched).
- `frontend/.env` is a **pre-existing** modification, never staged and never touched
  by this build.
- No second placement store; no Bentley write; no routing / simulation / optimizer.

Modified: `spatialAssetOverlay.ts`, `ClinicalProgramDecorator.ts`,
`ClinicalProgramControl.tsx`, `BentleyViewer.css`, and one Build 1A UI test
(`build1a4ContainmentValidationUi.test.tsx` — a test-harness accommodation for the
newly-added equipment inventory `<select>`, not a logic change). New: the 3 domain
modules + 2 test files.

---

## 8. Checkpoint

| | |
|---|---|
| `BUILD_1B_COMPLETION_GATE` | `MANUAL_CONFIRMATION_REQUIRED` |
| `CHECKPOINT` | `HOLD_FOR_BUILD_1B_MANUAL_ACCEPTANCE` |
| `NEXT_MAJOR_BUILD` | `BUILD_2_AUTOMATIC_FACILITY_CONNECTIVITY` |
| Authority docs | NOT updated (deferred to manual acceptance, §73) |
| Git actions | NONE (no stage, no commit, no push) |

Machine-readable companion: `mrt_pharma_build_1b_clinical_program_equipment_binding_data.json`.

# MRT Pharma — Real Equipment Catalog → Generic 3D Geometry Binding

Continues from checkpoint `bf5ebe96f5a3da7f6f7bfcecf5f61d17dcaeb748`. This build
proves the next architectural relationship:

```
REAL MRT PHARMA EQUIPMENT CATALOG RECORD
        ↓  (EquipmentSpatialAdapter — reference, not duplication)
SPATIAL ASSET DEFINITION
        ↓
SPATIAL ASSET INSTANCE
        ↓  (family-compatibility resolver, deterministic priority)
COMPATIBLE GENERIC GEOMETRY
        ↓  (existing SpatialAssetDecorator)
BENTLEY WORLD-SPACE REPRESENTATION
```

Central doctrine: the engineering/catalog layer is authoritative; 3D geometry is
a reusable spatial representation; there is **no second equipment catalog** inside
the 3D subsystem.

## Authoritative catalogs found in the repository (repository-source-derived facts)

- `scanner_equipment_catalog.json` + `scanner_catalog.py` — the authoritative PET
  + SPECT scanner catalog. Real PET/CT records: **`GE_DISCOVERY_MI`** (GE HealthCare,
  "Discovery MI", modality PET, `ct_configuration` "Integrated diagnostic CT (PET/CT)",
  current) and `SIEMENS_BIOGRAPH_VISION` (Siemens Healthineers, "Biograph Vision", PET/CT);
  SPECT: `SIEMENS_SYMBIA_PRO_SPECTA`, `GE_NM_CT_870_DR`, `GE_NM_CT_860`, `PHILIPS_BRIGHTVIEW_XCT`.
  For **all** scanner records `dimensions_footprint_notes = "NOT_CALIBRATED"`.
- `cyclotron_equipment_catalog.json` + `cyclotron_catalog.py` — real cyclotron models
  (GE PETtrace 890 calibrated F‑18, IBA Cyclone KEY, Sumitomo CYPRIS MP‑30, …).
- `generator_equipment_catalog.json` + `generator_catalog.py`.
- Existing doctrine precedent (`test_asis_twin_phase1b.py`): "Room object is geometry;
  equipment identity is a separate catalog instance; the geometry↔equipment link is an
  ID reference, not merged geometry." This build follows the same separation.

Because the backend catalog is Python and the 3D asset domain is TypeScript, the
frontend cannot import it directly. The adapter therefore consumes an
**identity-only** `AuthoritativeEquipmentRecord`. The `GE_DISCOVERY_MI` record used
here is `REPOSITORY_SOURCE_DERIVED` — its manufacturer/model/modality/ct-config values
are copied verbatim from the real `scanner_equipment_catalog.json`, not fabricated.
Its `dimensionsCalibrated = false` mirrors the catalog's NOT_CALIBRATED footprint.

## Implementation

- `frontend/src/domain/assets/catalogAdapter.ts` — `AuthoritativeEquipmentRecord`
  (identity only; NO throughput/power/CapEx/…), `adaptCatalogRecordToAssetDefinition`
  (label = manufacturer + model; `catalogReference` = `source#recordId`;
  `engineeringMetadataReference` referenced, not copied; `resolved=true` only for
  repository-source-derived records), `assetFamilyForCatalogModality`, and the real
  `GE_DISCOVERY_MI_RECORD`.
- `frontend/src/domain/assets/registry.ts` — `resolveCompatibleGeometry(family, explicitId?)`
  with deterministic priority: **explicit (if family-compatible) > compatible
  MANUFACTURER_SPECIFIC > compatible GENERIC > GEOMETRY_NOT_AVAILABLE**. Never returns a
  different family (no silent cross-family fallback).
- `frontend/src/domain/assets/commands.ts` — `createAssetInstanceFromCatalog(...)` with
  typed failures (`CATALOG_RECORD_NOT_FOUND`, `UNSUPPORTED_ASSET_FAMILY`,
  `GEOMETRY_NOT_AVAILABLE`, `GEOMETRY_FAMILY_MISMATCH`, `INVALID_CATALOG_ADAPTER`,
  `DIMENSIONS_NOT_CALIBRATED`). Label from catalog; dimension provenance kept honest.
- `frontend/src/domain/assets/testAsset.ts` — `buildGeDiscoveryMiCatalogTestAsset()`:
  the ONE catalog-backed proof instance `PETCT-CATALOG-TEST-01` (definition
  `CATALOG_PET_CT_GE_DISCOVERY_MI`), reusing `GENERIC_PET_CT_SCANNER_V1`, placed at a
  deterministic non-overlapping offset from the generic proof asset.
- `frontend/src/components/spatial/spatialAssetOverlay.ts` + `BentleyViewer.tsx` —
  DEV controls SHOW / HIDE / INSPECT CATALOG PET/CT, reusing the existing decorator
  (no separate CatalogAssetDecorator). Rendering consumes AssetInstances only; it never
  queries the catalog.

## Three identity layers (catalog-backed proof)

| Layer | Value |
|---|---|
| engineering/catalog identity | `GE_DISCOVERY_MI` (real record) → definition `CATALOG_PET_CT_GE_DISCOVERY_MI` |
| spatial instance identity | `PETCT-CATALOG-TEST-01` |
| geometry representation identity | `GENERIC_PET_CT_SCANNER_V1` (shared, manufacturerSpecific=false) |
| display label | "GE HealthCare Discovery MI" (from catalog identity, NOT the generic geometry label) |
| dimensions | 2.2 × 3.0 × 2.0 m, provenance `GENERIC_ENGINEERING_PLACEHOLDER` (catalog footprint NOT_CALIBRATED) |

The generic architecture proof (`GENERIC_PET_CT_ENGINEERING_TEST` / `PETCT-TEST-01`)
is preserved unchanged as a deterministic offline fixture.

## Report fields

```
AUTHORITATIVE_SCANNER_CATALOG_FOUND            = YES (scanner_equipment_catalog.json + scanner_catalog.py)
AUTHORITATIVE_PET_CT_RECORD_FOUND              = YES (GE_DISCOVERY_MI, SIEMENS_BIOGRAPH_VISION)
AUTHORITATIVE_CYCLOTRON_CATALOG_FOUND          = YES (cyclotron_equipment_catalog.json)
CATALOG_SCHEMA_USED                            = ScannerCatalogModel (identity-only mirror in TS AuthoritativeEquipmentRecord)
CATALOG_ADAPTER_IMPLEMENTED                    = YES
CATALOG_RECORD_ID_PRESERVED                    = PASS (catalogReference scanner_equipment_catalog.json#GE_DISCOVERY_MI)
ENGINEERING_METADATA_REFERENCE_PRESERVED       = PASS (referenced, not duplicated; resolved=true)
GENERIC_GEOMETRY_COMPATIBILITY_RESOLVER        = PASS
GEOMETRY_RESOLUTION_PRIORITY                   = PASS (explicit > mfr-specific > generic > GEOMETRY_NOT_AVAILABLE)
GENERIC_GEOMETRY_REUSE_ACROSS_CATALOG_IDENTITIES = PASS
ENGINEERING_DATA_DUPLICATED_IN_GEOMETRY        = NO
REAL_PET_CT_SPATIAL_INSTANCE_CREATED           = YES
REAL_PET_CT_CATALOG_RECORD_ID                  = GE_DISCOVERY_MI
REAL_PET_CT_DISPLAY_LABEL                      = "GE HealthCare Discovery MI"
DIMENSION_PROVENANCE                           = GENERIC_ENGINEERING_PLACEHOLDER (catalog footprint NOT_CALIBRATED)
```

## Targeted correction — NO_CATALOG_ASSET_PLACED

Manual failure: after SHOW CATALOG PET/CT then INSPECT CATALOG PET/CT the UI
reported `NO_CATALOG_ASSET_PLACED`.

Diagnosis: the domain creation path was proven fully working in isolation
(`buildGeDiscoveryMiCatalogTestAsset` returns `ok:true` with the correct
instance, `spatialSource=CATALOG`, `dimProvenance=GENERIC_ENGINEERING_PLACEHOLDER`,
`geometryRepresentationId=GENERIC_PET_CT_SCANNER_V1`). The defect was in the
overlay controller lifecycle: `disposeOverlay()` (called on the viewer effect
cleanup, which fires under React StrictMode mount→cleanup→mount and on any viewer
remount) **wiped the application-owned `instances` array**. An asset shown before
such a cleanup vanished from overlay state, so inspection found nothing.

```
ROOT_CAUSE   = OVERLAY_STATE_CLEARED_ON_DECORATOR_DISPOSE (StrictMode/remount cleanup wiped instances[])
CORRECTION   = disposeOverlay() now detaches only the Bentley decorator registration; it no longer
               clears `instances` (application-owned domain state) or the decorator object. Re-registration
               reuses the retained instances. Overlay dedupe is by assetInstanceId ONLY (never geometry id),
               so generic + catalog scanners coexist. Added a typed [catalog-asset] click-path diagnostic.
```

No change to the catalog record, generic geometry, Bentley auth/render path, camera,
or transparency. Only the overlay controller boundary was corrected.

## Manual acceptance (post-correction)

After the overlay-state correction, the build was manually accepted in Chrome.

Historical defect (retained for the record, do not delete):
```
HISTORICAL_MANUAL_FAILURE   = NO_CATALOG_ASSET_PLACED
HISTORICAL_FAILURE_STAGE    = overlay_state_lifecycle
HISTORICAL_FAILURE_CODE     = OVERLAY_STATE_CLEARED_ON_DECORATOR_DISPOSE
CORRECTION                  = Bentley decorator disposal no longer destroys application-owned spatial AssetInstance state.
```

Post-correction manual acceptance:
```
POST_CORRECTION_MANUAL_ACCEPTANCE                 = PASS
LIVE_IMODEL_VISIBLE_IN_BROWSER                    = YES
GENERIC_PET_CT_VISIBLE_IN_BROWSER                 = YES
CATALOG_PET_CT_VISIBLE_IN_BROWSER                 = YES
TWO_SCANNER_INSTANCES_VISIBLE_SIMULTANEOUSLY      = YES
GENERIC_AND_CATALOG_INSTANCES_COEXIST             = YES
CATALOG_PET_CT_INSPECTION_VISIBLE                 = YES
CATALOG_VISUAL_METADATA_LINKAGE                   = PASS
CATALOG_GEOMETRY_BINDING_MANUALLY_CONFIRMED       = YES
GENERIC_GEOMETRY_REUSE_ACROSS_CATALOG_IDENTITIES  = PASS
```

BROWSER_DERIVED_FACTS (from the INSPECT CATALOG PET/CT screenshot):
`assetInstanceId=PETCT-CATALOG-TEST-01`, `displayLabel="GE HealthCare Discovery MI"`,
`assetDefinitionId=CATALOG_PET_CT_GE_DISCOVERY_MI`,
`geometryRepresentationId=GENERIC_PET_CT_SCANNER_V1`,
`createdFrom=catalog:scanner_equipment_catalog.json#GE_DISCOVERY_MI`,
placed dimensions `2.2 x 3 x 2 METERS`, `dimProvenance=GENERIC_ENGINEERING_PLACEHOLDER`,
`position=(11.05, 10.00, 3.50)`, `room=NOT_ASSIGNED`, `state=PLACED`, `source=CATALOG`.

REPOSITORY_SOURCE_DERIVED_FACT (NOT shown in the browser inspection):
`CATALOG_DIMENSION_STATE = NOT_CALIBRATED` (from scanner_equipment_catalog.json
`dimensions_footprint_notes`).

## Verification
- TypeScript typecheck: PASS
- Offline tests: **96 passed** (94 prior + 2 new coexistence/dedupe invariants) — no Bentley auth, no network.
- Production build: PASS; genuine `parse-imdl-worker.js` (JS) + `draco_decoder.wasm` (`\0asm`).
- Dev server: `/viewer` 200; worker `text/javascript`; WASM `application/wasm`.

## Preserved / out of scope
No iModel writes / changesets; transparency remains DEFERRED (no ViewFlags change);
camera / ViewCreator3d / isometric orientation unchanged; auth/PKCE/lifecycle/runtime-assets
unchanged. No equipment library populated, no drag/drop, no room snapping, no manufacturer-specific
geometry, no simulation/economics, no Bentley Components Center / manufacturer CAD ingestion,
no NVIDIA. Manufacturer-specific geometry resolution semantics are implemented and tested via
fixtures, but no such geometry is created.

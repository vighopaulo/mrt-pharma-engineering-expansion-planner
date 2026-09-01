# MRT Pharma — Asset Library + Controlled 3D Placement Foundation

Continues from authoritative checkpoint `174228dd4cef040ee7ba5836f4f9577c5a9f2f7a`.
This build turns the proven catalog → geometry → overlay architecture into the
first user-facing spatial-planning workflow:

```
AUTHORITATIVE EQUIPMENT CATALOG
  → ASSET LIBRARY (view model)
    → SELECT GE Discovery MI
      → PLACE (enter placement mode)
        → CLICK ONE WORLD-SPACE LOCATION (bounded Bentley PrimitiveTool)
          → CREATE ONE UNIQUE AssetInstance (USER_PLACED)
            → RENDER via existing SpatialAssetDecorator overlay
              → INSPECT the placed asset (Placed Assets panel)
```

It is click-to-place, NOT drag/drop, NOT room snapping, NOT a full library.
No iModel writes, no transparency work, no camera changes, no auth changes.

## Repository baseline

```
PRECHECK_HEAD        = 174228dd4cef040ee7ba5836f4f9577c5a9f2f7a
PRECHECK_ORIGIN_MAIN = 174228dd4cef040ee7ba5836f4f9577c5a9f2f7a
PRECHECK_DIVERGENCE  = 0 / 0
```

## Catalog authority clarification

The real equipment identity used here comes from the authoritative equipment
catalog ALREADY PRESENT in this repository (`scanner_equipment_catalog.json` +
`scanner_catalog.py`), record `GE_DISCOVERY_MI`. `GE HealthCare Discovery MI` is
therefore a repository-catalog-derived identity, not a fabricated UI label. No
external GE HealthCare API was contacted and no manufacturer CAD/geometry was
ingested.

```
REPOSITORY_CATALOG_IDENTITY_USED = YES
CATALOG_RECORD_ID                = GE_DISCOVERY_MI
CATALOG_MANUFACTURER             = GE HealthCare
CATALOG_MODEL                    = Discovery MI
EXTERNAL_GE_API_CONNECTED        = NO
GE_MANUFACTURER_API_QUERIED      = NO
GE_MANUFACTURER_CAD_INGESTED     = NO
GE_MANUFACTURER_GEOMETRY_USED    = NO
```

The visual representation remains `GENERIC_PET_CT_SCANNER_V1` — it must NOT be
described as GE Discovery MI CAD, GE-provided geometry, or manufacturer-
calibrated geometry. The authoritative catalog footprint remains
`NOT_CALIBRATED`; the displayed generic dimensions `2.2 x 3 x 2 METERS` carry
provenance `GENERIC_ENGINEERING_PLACEHOLDER`.

Local-only files intentionally untouched: `frontend/.env`,
`AS_IS_DIGITAL_TWIN_PHASE_1A_SEAM_REPORT.md`.

## Bentley input API (verified, not guessed)

Installed `@itwin/core-frontend` **5.12.5**. Verified in the installed type
definitions:

- `ScreenViewport.pickNearestVisibleGeometry(pickPoint: Point3d, radius?, allowNonLocatable?, out?): Point3d | undefined`
  returns a point **in world coordinates** on visible geometry near the pick
  point, or `undefined`.
- `Viewport.viewToWorld` / `npcToWorld` / `worldToView` coordinate conversions exist.
- `PrimitiveTool` exposes `onDataButtonDown(ev: BeButtonEvent): Promise<EventHandled>`
  where `ev.point` is the tool-adjusted **world** `Point3d`; `onResetButtonUp`
  for cancel; `exitTool()`; `requireWriteableTarget()`.
- Lifecycle via `Tool.register(namespace)` + `IModelApp.tools.run(toolId)`;
  active tool via `IModelApp.toolAdmin.activeTool`.

**Selected mechanism:** a bounded Bentley `PrimitiveTool`
(`MrtAssetPlacementTool`), NOT a raw DOM click listener. On the first accepted
data-button click it resolves a world point via
`ev.viewport.pickNearestVisibleGeometry(ev.point)`; if no visible geometry is
hit it falls back to the tool-adjusted `ev.point` (view-plane projection) and
records that honestly. Then it exits so the tool never lingers.

```
BENTLEY_PLACEMENT_API        = PrimitiveTool.onDataButtonDown + ScreenViewport.pickNearestVisibleGeometry
PLACEMENT_WORLD_POINT_SOURCE = PICK_NEAREST_VISIBLE_GEOMETRY, else VIEW_PLANE_PROJECTION (ev.point)
FLOOR_SNAPPING_IMPLEMENTED   = NO
```

## Architecture

```
Asset Library UI (ViewerAssetLibrary.tsx)
  → spatialAssetOverlay product API (beginPlacementForLibraryEntry / cancelPlacement)
    → domain buildPlacementIntent (PlacementIntent; no instance yet)
      → MrtAssetPlacementTool (Bentley click → world point)
        → SpatialAssetStore.completePlacementAt (consumes intent once)
          → placeFromIntent → createAssetInstanceFromCatalog (single creation path)
            → SpatialAssetStore (single source of truth)
              → SpatialAssetDecorator (existing overlay)
```

- **Asset Library** (`assetLibrary.ts`): `AssetLibraryEntry` view model derived
  from authoritative catalog records via the registry resolver. NOT a second
  catalog; references catalog identity, never copies engineering values.
  PET/CT-scoped (cyclotron/SPECT excluded from the query).
- **Placement domain** (`placement.ts`): `PlacementIntent`, `buildPlacementIntent`,
  application-scoped `InstanceIdGenerator`, `placeFromIntent` (reuses
  `createAssetInstanceFromCatalog`), typed `PlacementFailure`.
- **Single source of truth** (`spatialAssetStore.ts`): `SpatialAssetStore` owns
  the registry + `AssetInstance[]` + id generator + active intent. Event-driven
  `subscribe`/`getSnapshot` (no polling, no `setInterval`). Consumed by the
  overlay, the Asset Library, and the Placed Assets panel.
- **Bentley layer** (`MrtAssetPlacementTool.ts`): the only Bentley input concern;
  never queries the catalog (receives a resolved intent from the store).
- **UI** (`ViewerAssetLibrary.tsx`): reads the store via `useSyncExternalStore`;
  drives placement only through the overlay product API; never touches
  `ScreenViewport`/`GraphicBuilder`/`Decorator`/`IModelApp` directly; never calls
  the DEV fixture path (`showCatalogPetCt`).

```
ASSET_LIBRARY_IMPLEMENTED       = YES
ASSET_LIBRARY_SOURCE            = AUTHORITATIVE_SCANNER_CATALOG (GE_DISCOVERY_MI record, REPOSITORY_SOURCE_DERIVED)
ASSET_LIBRARY_PET_CT_ENTRY      = GE_DISCOVERY_MI
ASSET_LIBRARY_DISPLAY_LABEL     = GE HealthCare Discovery MI
GEOMETRY_AVAILABILITY           = GENERIC_PET_CT_SCANNER_V1 (generic; "Generic spatial representation available")
CATALOG_DIMENSION_STATE         = NOT_CALIBRATED (shown separately from geometry)
PLACED_DIMENSION_PROVENANCE     = GENERIC_ENGINEERING_PLACEHOLDER
NO_MANUFACTURER_SPECIFIC_VISUAL_CLAIM = geometry stays GENERIC while identity is GE Discovery MI
```

## Placement behavior

```
PLACEMENT_INTENT_IMPLEMENTED = YES (select ≠ place; PLACE enters mode)
PLACEMENT_MODE_IMPLEMENTED   = YES (visible "Placing: GE HealthCare Discovery MI")
ONE_CLICK_ONE_INSTANCE       = PASS (intent consumed once; store guards double-click)
INSTANCE_ID_STRATEGY         = application-scoped sequence, per catalog record
USER_PLACED_INSTANCE_ID_EXAMPLE = PETCT-GE-DISCOVERY-MI-0001
POSITION_AUTHORITY           = ASSET_INSTANCE (geometry/catalog/iModel coords untouched)
DEFAULT_ROTATION             = yaw=0 pitch=0 roll=0 (stored; no rotation UI)
PLACED_ASSET_ROTATION_MODEL_PRESENT = YES
INTERACTIVE_ROTATION_IMPLEMENTED    = NO
AUTOMATIC_ROOM_ASSIGNMENT    = NO (roomAssignment = NOT_ASSIGNED)
SPATIAL_SOURCE               = USER_PLACED (catalog origin preserved in createdFrom)
SCENARIO_PROVENANCE          = scenarioId=MRT_DEV_SCENARIO, scenarioState=DRAFT (projectId=MRT_DEV_VIEWER_PROJECT)
ASSET_PLACED_EVENT           = PASS (type ASSET_PLACED with identity+position+rotation+room+scenario)
PLACED_ASSETS_PANEL          = YES (derives from the single store; inspection exposes full metadata)
OVERLAY_STATE_SOURCE_OF_TRUTH = SpatialAssetStore (module singleton) — ONE
```

`createdFrom = catalog:scanner_equipment_catalog.json#GE_DISCOVERY_MI` while
`spatialSource = USER_PLACED`: engineering/catalog origin and spatial placement
provenance are kept as separate concepts (not collapsed).

## Preserved invariants

```
OVERLAY_STATE_SURVIVES_DECORATOR_DISPOSE = PASS (store decoupled from decorator lifecycle)
MULTIPLE_USER_INSTANCES_SAME_GEOMETRY    = PASS (two placements: same def+geometry id, distinct instance ids)
ARCHITECTURE_FIXTURE_INSTANCE_PRESERVED  = YES (PETCT-TEST-01 + PETCT-CATALOG-TEST-01 unchanged; DEV buttons retained)
GEOMETRY_OBJECT_DUPLICATION_PER_INSTANCE = NO (shared GENERIC_PET_CT_SCANNER_V1)
STRICTMODE_DUPLICATE_PLACEMENT           = NO (tool registered once; store singleton; intent consumed once)
PLACEMENT_INPUT_ACTIVE_WHEN_IDLE         = NO (input only while the tool runs)
PLACEMENT_TOOL_REMAINS_ACTIVE_AFTER_SUCCESS = NO (exitTool after one click)
```

The existing DEV controls are all retained and grouped under a `DEV` label:
FIT LIVE MODEL, INSPECT RENDER STATE, INSPECT FEATURE APPEARANCE,
SHOW/HIDE/INSPECT GENERIC PET/CT, SHOW/HIDE/INSPECT CATALOG PET/CT, plus a new
INSPECT PLACEMENT INTENT diagnostic. The product Asset Library is a separate
top-left panel.

## Machine verification

```
TYPECHECK               = PASS
OFFLINE_TEST_COUNT      = 121
NEW_TEST_COUNT          = 25 (20 placementFoundation.test.ts + 5 placementStatus.test.ts)
OFFLINE_TEST_REGRESSIONS = 0 (96 baseline preserved)
PRODUCTION_BUILD        = PASS
CORE_FRONTEND_VERSION   = @itwin/core-frontend 5.12.5
WORKER_ASSET_REAL       = YES ((()=>{"use strict"; ; served text/javascript ; /viewer 200)
DRACO_WASM_ASSET_REAL   = YES (\0asm ; served application/wasm)
```

## Safety

```
AUTH_FLOW_CHANGED          = NO
VIEWER_LIFECYCLE_CHANGED   = NO
TRANSPARENCY_WORK_RESUMED  = NO
CAMERA_BEHAVIOR_CHANGED    = NO
IMODEL_MODIFIED            = NO
BENTLEY_CHANGESET_CREATED  = NO
BENTLEY_RESOURCE_MODIFIED  = NO
SECRET_EXPOSED             = NO
```

## Manual acceptance (obtained)

The workflow passed manual functional acceptance in Chrome:

```
LIVE_IMODEL_VISIBLE_IN_BROWSER              = YES
ASSET_LIBRARY_VISIBLE_IN_BROWSER            = YES
USER_PLACED_PET_CT_VISIBLE_IN_BROWSER       = YES
USER_PLACED_PET_CT_INSPECTION_VISIBLE       = YES
PLACEMENT_CANCEL_MANUALLY_CONFIRMED         = YES
MULTIPLE_USER_PLACEMENT_MANUALLY_CONFIRMED  = YES
FIRST_USER_INSTANCE_ID                      = PETCT-GE-DISCOVERY-MI-0001
SECOND_USER_INSTANCE_ID                     = PETCT-GE-DISCOVERY-MI-0002
PLACED_ASSET_COUNT_AFTER_SECOND_PLACEMENT   = 2
ONE_CLICK_ONE_INSTANCE                      = PASS
PLACEMENT_MODE_EXITS_AFTER_SUCCESS          = PASS
PLACEMENT_MODE_EXITS_AFTER_CANCEL           = PASS
DIFFERENT_SPATIAL_INSTANCE_IDS              = YES
SAME_ENGINEERING_IDENTITY                   = YES
SAME_GEOMETRY_IDENTITY                      = YES
MULTIPLE_USER_INSTANCES_SAME_GEOMETRY       = PASS
```

### Defect discovered during manual acceptance (corrected before checkpoint)

A small PRESENTATION-ONLY defect was found: after a successful placement the
Bentley tool correctly exited and the button correctly returned to
`PLACE IN MODEL`, but the informational status line kept showing the stale
`Placing: … click a location …` instruction. The underlying placement state was
NOT stuck.

```
STALE_SUCCESS_STATUS_DEFECT_FOUND     = YES
DEFECT_SCOPE                          = presentation/status only
ROOT_CAUSE                            = status was a manually-set local string never cleared when the tool exited
CORRECTION                            = status is now DERIVED from SpatialAssetStore placement-mode transitions (placementStatus.ts seam)
PLACEMENT_ARCHITECTURE_CHANGED        = NO
```

Status semantics after the fix: `PLACEMENT_ACTIVE` → "Placing: …"; success →
"Placed: PETCT-GE-DISCOVERY-MI-####"; cancel → "Placement cancelled"; idle →
no active-placement claim. Covered by `placementStatus.test.ts` (5 tests):
active contains "Placing"; success does NOT contain "Placing" and names the
placed instance; cancel equals "Placement cancelled".

Test count after the correction: **121** (116 preserved + 5 status regression
tests), OFFLINE_TEST_REGRESSIONS = 0.

### Final quick visual re-confirmation (passed)

```
STALE_PLACING_TEXT_GONE_AFTER_SUCCESS = YES
SUCCESS_STATUS_SHOWN                  = YES
SUCCESS_STATUS_EXAMPLE                = Placed: PETCT-GE-DISCOVERY-MI-0001
PLACEMENT_SUCCESS_STATUS_CLEANUP      = PASS
STALE_PLACING_STATUS_AFTER_SUCCESS    = NO
ASSET_LIBRARY_PLACEMENT_FOUNDATION_MANUAL_ACCEPTANCE = PASS
```

### First user placement (manual proof)

```
assetInstanceId          = PETCT-GE-DISCOVERY-MI-0001
displayLabel             = GE HealthCare Discovery MI
catalogRecordId          = GE_DISCOVERY_MI
assetDefinitionId        = CATALOG_PET_CT_GE_DISCOVERY_MI
geometryRepresentationId = GENERIC_PET_CT_SCANNER_V1
createdFrom              = catalog:scanner_equipment_catalog.json#GE_DISCOVERY_MI
position                 = (13.76, 7.00, 5.29)
rotation                 = yaw=0 pitch=0 roll=0
roomAssignment           = NOT_ASSIGNED
installationState        = PLACED
spatialSource            = USER_PLACED
scenario                 = MRT_DEV_SCENARIO / DRAFT
dimensionProvenance      = GENERIC_ENGINEERING_PLACEHOLDER
CATALOG_TO_USER_PLACEMENT_IDENTITY_CHAIN = PASS
```

### Cancellation + multiple-instance (manual proof)

```
PLACED_ASSET_COUNT_BEFORE_CANCEL          = 1
PLACEMENT_CANCELLED_WITHOUT_INSTANCE_CREATION = PASS
PLACED_ASSET_COUNT_AFTER_CANCEL           = 1
EXISTING_PLACED_ASSET_PRESERVED           = YES
FIRST_USER_INSTANCE_ID                    = PETCT-GE-DISCOVERY-MI-0001
SECOND_USER_INSTANCE_ID                   = PETCT-GE-DISCOVERY-MI-0002
PLACED_ASSET_COUNT_AFTER_SECOND_PLACEMENT = 2
ONE_GEOMETRY_MANY_SPATIAL_INSTANCES       = PASS
```

Procedure: open `http://localhost:3000/viewer`; confirm the live BIM renders;
open the Asset Library (top-left); select Imaging → PET/CT → GE HealthCare
Discovery MI; confirm it shows "Generic spatial representation available" and
"Catalog dimensions: Not calibrated"; click PLACE IN MODEL; confirm the
"Placing: GE HealthCare Discovery MI" status; click ONE location; confirm ONE
new scanner appears and placement mode exits; confirm it appears in Placed
Assets; inspect it and confirm the identity chain
(`GE_DISCOVERY_MI` → `CATALOG_PET_CT_GE_DISCOVERY_MI` →
`GENERIC_PET_CT_SCANNER_V1`, a NEW `PETCT-GE-DISCOVERY-MI-####` id,
`roomAssignment=NOT_ASSIGNED`, `state=PLACED`, `source=USER_PLACED`, scenario
present); confirm the fixtures `PETCT-TEST-01` and `PETCT-CATALOG-TEST-01` are
unaffected; enter placement again and cancel (right-click/Esc) and confirm no
second asset is created and the mode exits.

This build is NOT staged, committed, or pushed — implementation stops here for
manual browser acceptance.

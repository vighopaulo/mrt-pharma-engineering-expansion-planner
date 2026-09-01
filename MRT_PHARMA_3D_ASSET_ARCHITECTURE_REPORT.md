# MRT Pharma — 3D Asset Architecture Foundation

Continues from checkpoint `d5b622dc545a146ca16ab5dfcb00eeb73ecc0e05` (visible
isometric Bentley viewer). This build establishes the reusable, deterministic
architecture by which MRT Pharma represents, catalogs, places, identifies, and
later simulates physical equipment inside the 3D digital twin — proven
end-to-end by exactly ONE generic PET/CT test asset. The **architecture** is the
deliverable, not the scanner. No equipment library was created. The connected
iModel was NOT modified; transparency work was NOT reopened.

## Governing doctrine

```
ENGINEERING ASSET DEFINITION → SPATIAL ASSET INSTANCE → GEOMETRY REPRESENTATION
→ BENTLEY VIEWPORT OVERLAY → SIMULATION / ENGINEERING / ECONOMIC CONSUMERS
```

The 3D object **represents** the engineering asset; it never becomes the
authoritative source of manufacturer, capacity, CapEx, simulation behavior, etc.
Those come from the engineering/catalog layer, **referenced** (not duplicated)
via `EngineeringMetadataReference` (with an explicit `resolved: boolean`).

Three identities are always kept distinct:
- ENGINEERING IDENTITY → `AssetDefinition.assetDefinitionId`
- SPATIAL INSTANCE ID → `AssetInstance.assetInstanceId`
- GEOMETRY REP IDENTITY → `GeometryRepresentation.geometryRepresentationId`

One geometry representation may back many engineering identities.

## Implementation layout

Domain (pure, serializable, **Bentley-free**) — `frontend/src/domain/assets/`:
- `types.ts` — core typed model: `AssetClass`, `AssetFamily` (+ `ASSET_FAMILY_CLASS`),
  `AssetDefinition`, `AssetInstance`, `GeometryRepresentation`, `AssetDimensions`
  (unit `METERS`, `DimensionProvenance`), `SpatialTransform` /`Position`/`Rotation`(deg)/`Scale`
  (`CoordinateSpace = BENTLEY_WORLD_COORDINATES | MODEL_LOCAL`), `AssetInstallationState`,
  `SpatialSource`, `RoomAssignment`, `AssetConnectionPoint`, `ClearanceEnvelope`,
  `AssetCapabilities` (MRT-extensible), `ScenarioProvenance`.
- `validation.ts` — deterministic validation (finite/non-negative dims, scale > 0, family↔class).
- `registry.ts` — `AssetRegistry`; resolution returns `RESOLVED | GEOMETRY_NOT_AVAILABLE`
  (never a silent unrelated fallback); enforces geometry↔definition family compatibility.
- `serialization.ts` — `serialize/deserializeAssetInstance` (schema `mrt.asset-instance/v1`);
  never serializes runtime Bentley objects.
- `commands.ts` — pure immutable `createAssetInstance / placeAsset / moveAsset /
  rotateAsset / assignAssetToRoom / removeAsset`, each returning updated state +
  a structured `AssetJournalEvent` (future Event-Journal integration point).
- `genericCatalog.ts` — the ONE generic PET/CT geometry + two generic definitions.
- `testAsset.ts` — deterministic proof-instance construction from a model neighborhood.

Spatial/Bentley integration — `frontend/src/components/spatial/`:
- `scannerGeometry.ts` — **Bentley-free** `buildScannerParts()` → gantry (box) +
  bore (cylinder) + patient table (box) in world coordinates (testable).
- `SpatialAssetDecorator.ts` — Bentley `Decorator` (`useCachedDecorations = true`),
  emits `GraphicType.WorldDecoration` solids; consumes domain state (never owns identity).
- `spatialAssetOverlay.ts` — bounded controller: register-once decorator, show/hide/inspect,
  deterministic placement from `selectedView.view.computeFitRange()`.

Viewer wiring: `LiveItwinViewer.tsx` registers/disposes the decorator on mount/unmount
(dynamic import). `BentleyViewer.tsx` adds DEV controls **SHOW / HIDE / INSPECT
GENERIC PET/CT** alongside the preserved FIT LIVE MODEL / INSPECT RENDER STATE /
INSPECT FEATURE APPEARANCE controls.

## Bentley overlay mechanism

`BENTLEY_OVERLAY_MECHANISM = IModelApp.viewManager.addDecorator(Decorator) +
DecorateContext.createGraphicBuilder(GraphicType.WorldDecoration) +
addDecorationFromBuilder` (installed `@itwin/core-frontend` **v5.12.5**). World
decorations are application-owned overlay graphics — they do NOT touch the
iModel, ViewFlags, camera, or transparency. `useCachedDecorations` keeps the
overlay stable while idle (no render loop).

## The one proof asset (identity separation)

| Identity | Value |
|---|---|
| geometryRepresentationId | `GENERIC_PET_CT_SCANNER_V1` (GENERIC, PLACEHOLDER, parametric Bentley graphics) |
| assetDefinitionId | `GENERIC_PET_CT_ENGINEERING_TEST` (manufacturer GENERIC; engineering ref `resolved: false`) |
| assetInstanceId | `PETCT-TEST-01` |
| displayLabel | "Generic PET/CT Scanner" (derived from definition, not hardcoded in rendering) |
| dimensions | 2.2 × 3.0 × 2.0 m, provenance `GENERIC_ENGINEERING_PLACEHOLDER` (NOT manufacturer specs) |
| roomAssignment | `NOT_ASSIGNED` |
| installationState | `PLACED` |
| spatialSource | `GENERATED_GENERIC` |
| placement | model-range center + clamped offset [2,15] m (within model neighborhood) |
| geometry parts | GANTRY (box) + BORE (cylinder) + PATIENT_TABLE (box) — recognizably scanner-like, low LOD |

A second generic definition `GENERIC_PET_CT_ENGINEERING_TEST_B` reuses the SAME
geometry, proving `ONE_GEOMETRY_MANY_ENGINEERING_IDENTITIES` without duplicating
geometry metadata.

## Compatibility (architecture only, not implemented)

- **Scenario / LOCKDOWN / What-If**: `AssetInstance.scenario` (`ScenarioProvenance`)
  is optional and additive; this domain owns no competing scenario engine.
- **Event Journal**: every command returns an `AssetJournalEvent`
  (`ASSET_INSTANCE_CREATED / PLACED / MOVED / ROTATED / ROOM_ASSIGNED / REMOVED`) —
  the integration point; no duplicate journal built.
- **Connection points & clearance envelopes**: typed (`AssetConnectionPoint`,
  `ClearanceEnvelope`) with explicit provenance/`NOT_CALIBRATED` states; no
  clearance dimensions fabricated.
- **Future source formats**: `GeometrySourceFormat` enumerates IFC/RVT/DGN/IMODEL/
  OBJ/GLTF/GLB/FBX/Bentley Components Center — metadata-ready without rewriting the model.
- **Existing BIM vs MRT-placed**: `SpatialSource` distinguishes `BENTLEY_IMODEL`
  from `MRT_PHARMA` / `GENERATED_GENERIC` etc.; persistence/export remains possible.

## Verification

- TypeScript typecheck: PASS
- Offline tests: 75 passed (52 baseline preserved + 23 new in `assetArchitecture.test.ts`) — no network, no Bentley auth, no `@itwin` runtime.
- Production build: PASS; `dist/scripts/parse-imdl-worker.js` genuine JS, `dist/scripts/draco_decoder.wasm` genuine (`\0asm`).
- Dev server: `/viewer` 200; worker `text/javascript`; WASM `application/wasm`; spatial+domain modules transform.

## Out of scope (future builds)

Equipment library (multiple scanners/cyclotrons/beds/doors/elevators/hot cells),
MRT carrier/guideway/endpoint geometry, drag-and-drop UI, room snapping, collision/
clearance checking, routing, simulation, economics, Bentley Components Center /
manufacturer CAD ingestion, NVIDIA/Omniverse. Transparency normalization remains
DEFERRED and non-blocking.

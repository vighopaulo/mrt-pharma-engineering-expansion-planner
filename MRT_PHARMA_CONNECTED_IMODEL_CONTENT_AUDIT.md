# MRT Pharma — Connected iModel Content Audit (diagnosis only)

Baseline `HEAD = origin/main = b2abe6bf28056d002d140b52fb54e94c9cd417eb`, divergence `0 / 0`. The Visual Planning Foundation working tree remains uncommitted. This is a READ-ONLY diagnosis: no iModel changes, no visual changes, no checkpoint.

## Purpose

Establish whether the connected iModel contains detailed architectural hospital geometry that is not displaying correctly (A), or is primarily a simplified spatial-semantic / development fixture with limited architecture (B). The unobstructed browser view reads as `SIMPLIFIED_RECTANGULAR_MASSES`.

## Audited iModel identity (no secrets)

- iTwin: **MRTway Development Twin** (`bdf29ecd-b4a4-404d-861a-ac3061c7b12f`)
- iModel: **MRTway Hospital Campus Development** (id via browser-safe `VITE_BENTLEY_IMODEL_ID` — not printed; `frontend/.env` not read)
- `SECRET_EXPOSED = NO`

## Data provenance — important honesty note

The live counts this audit requires (schema inventory, per-class geometric element counts, physical/spatial element counts, room ranges, class-metadata searches for wall/door/window classes) can only be obtained from an **authenticated browser `IModelConnection`** (Bentley IMS + PKCE). They **cannot be queried from the terminal**, and I did not have an authenticated browser session to run them myself.

To obtain the data without guessing, I added a bounded, READ-ONLY audit helper:

- `frontend/src/components/spatial/bimContentAudit.ts` — `runBimContentAudit()` / `formatBimContentAudit()`
- overlay entrypoint `inspectBimContentAudit()` in `spatialAssetOverlay.ts`
- one DEV-drawer button: **RUN BIM CONTENT AUDIT**

It is diagnostic-only (not integrated into product behavior), modifies nothing, and prints no secrets. Running that button in `/viewer` (Developer mode) fills every `PENDING_LIVE_RUN` field below. Those fields are **not fabricated**.

### What the audit helper queries (read-only)

- `SELECT COUNT(*) FROM bis.Model` / `bis.GeometricModel`
- `SELECT Name FROM meta.ECSchemaDef` (schema inventory)
- `SELECT ec_classname(ECClassId), COUNT(*) FROM bis.GeometricElement3d GROUP BY ECClassId ORDER BY ... DESC` (actual class population, top 25)
- `bis.PhysicalElement`, `bis.SpatialLocationElement` counts
- `BuildingSpatial.Space`, `BuildingSpatial.Story`, `SpatialComposition.CompositeElement`, `SpatialComposition.SpatialStructureElement` counts
- class-metadata search (`meta.ECClassDef` join `meta.ECSchemaDef`) for names containing Wall/Partition/CurtainWall, Slab/Floor/Deck/Plate, Door/Opening, Window/Glazing, Ceiling/Roof — then counts each match (answers sections 13–17 by searching actual classes, not guessed names)
- bounded room inventory (id + label + geometric-range presence)

## Live-data results (AUDIT CLOSED — from the executed browser run)

```
CONNECTED_IMODEL_CLASSIFICATION = PARTIAL_ARCHITECTURAL_BIM
CONNECTED_IMODEL_CLASSIFICATION_CONFIDENCE = HIGH
IMODEL_MODEL_COUNT = 5
GEOMETRIC_3D_MODEL_COUNT = 1
GEOMETRIC_ELEMENT3D_COUNT = 12
PHYSICAL_ELEMENT_COUNT = 3
SPATIAL_LOCATION_ELEMENT_COUNT = 9
BUILDINGSPATIAL_SPACE_COUNT = 8
BUILDINGSPATIAL_STORY_COUNT = 0
SPATIALCOMPOSITION_COMPOSITE_COUNT = 12
ARCHITECTURAL_WALL_COUNT = 12
ARCHITECTURAL_SLAB_OR_FLOOR_COUNT = 0
ARCHITECTURAL_DOOR_COUNT = 0
VISIBLE_MASSES_MATCH_ROOM_RANGES = PARTIAL
```

Interpretation: 12 wall-like elements exist, but with 0 floors/slabs, 0 doors, 0 stories, and only 12 GeometricElement3d total, this is a PARTIAL architectural BIM — enough for engineering regression, not enough to read as a credible medical facility.

## Prior evidence (from earlier spatial-semantics work — not a substitute for the live run)

- ~8 `BuildingSpatial:Space` objects with finite, axis-aligned ranges.
- Floor source is `SpatialComposition:CompositeElement` (no reliable Story membership).
- Room labels observed: Floor 1 Main Corridor, Radiopharmacy, Cyclotron Room, Vertical Circulation Core, Patient Room, Injection/Uptake Room, Scanner Room, Floor 2 Main Corridor.
- Guessed wall/door/window classes (`BuildingPhysical:*`, `ArchitecturalPhysical:*`) matched nothing.

## Final assessment (audit closed)

- `TEST_FIXTURE_EVIDENCE = STRONG`: only 12 GeometricElement3d, 3 PhysicalElement, 8 Space, 0 Story, 0 slabs/floors, 0 doors; browser shows simple rectangular masses.
- `PRODUCTION_BIM_EVIDENCE = PARTIAL`: 12 wall-like elements but no floors/doors/stories and a tiny geometric population.
- `CONNECTED_IMODEL_CLASSIFICATION = PARTIAL_ARCHITECTURAL_BIM`.
- `CONNECTED_IMODEL_CLASSIFICATION_CONFIDENCE = HIGH` (live browser audit executed).
- `CURRENT_VISUAL_LIMITATION_ROOT_CAUSE = SOURCE_MODEL_GEOMETRY_LIMITATION` — not CSS, not transparency, not a Bentley renderer failure.

## Recommendation

- `CURRENT_IMODEL_RECOMMENDATION = RETAIN_AS_ENGINEERING_TEST_FIXTURE` (confirmed by live audit).
- `CURRENT_IMODEL_ROLE = ENGINEERING_REGRESSION_FIXTURE` — preserve for placement / selection / drag / rotation / right-click / selection-box / group translation / delete / spatial-semantics / room-association regression coverage.
- `CREDIBLE_HOSPITAL_DEMO_BIM_REQUIRED = YES` if product-grade architectural realism is the goal — **decision only; do not import in this audit**.
- Rationale: if the live audit confirms no walls/doors/slabs and a small geometric population, no visual polish (transparency, footprints, colors) can make the source geometry read as a detailed hospital.

## Machine verification

```
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 341   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5
WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES   /viewer = 200
IMODEL_MODIFIED = NO   BENTLEY_CHANGESET_CREATED = NO   SECRET_EXPOSED = NO
VISUAL_PLANNING_CODE_CHANGED = NO   EQUIPMENT_PIPELINE_CHANGED = NO
INTERACTION_CODE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO
AUTH_FLOW_CHANGED = NO   PKCE_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO
```

Diagnosis complete. To finalize the classification to HIGH confidence, open `/viewer`, enable Developer mode, click **RUN BIM CONTENT AUDIT**, and paste the Developer Inspector output into the PENDING_LIVE_RUN fields. Nothing was staged, committed, or pushed.

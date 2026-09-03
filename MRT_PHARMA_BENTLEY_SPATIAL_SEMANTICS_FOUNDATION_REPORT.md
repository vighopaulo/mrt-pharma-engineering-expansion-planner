# MRT Pharma — Bentley Spatial Semantics (Floor + Room Association) Foundation

Continued from authoritative checkpoint `fc355ab29fd19d7f9c2dde84d7c95069bb502233`
(0/0 divergence at start; implementation uncommitted). This build adds the first
BIM-aware spatial semantics layer: `asset position → floor association → room
association → spatial validity/provenance`. It is OBSERVATIONAL — it never moves
an asset, changes Z, snaps, or writes the iModel. No collision, clearance,
snapping, door-fit, path, simulation, or economics work was started.

## What the system can now say (honestly)

For an application-owned asset, the system can report which BIM floor and room
contain its position, OR explicitly say the BIM does not expose usable
floor/room semantics — distinguishing "checked and outside" from "the BIM has no
room geometry".

## Architecture

Pure Bentley-free domain — `frontend/src/domain/assets/spatialSemantics.ts`
(exported via the domain barrel):
- `SpatialFloorReference`, `SpatialRoomReference`, `SpatialModelSemantics`
  (Bentley-independent, serializable). Missing elevation/geometry stays optional
  — never fabricated.
- `SpatialAssociationResult` with INDEPENDENT typed statuses for floor and room:
  `ASSIGNED | NOT_FOUND_AT_POSITION | NOT_AVAILABLE_FROM_BIM | AMBIGUOUS |
  OUTSIDE_MODELED_SPACE`. Uncertainty is never collapsed into a single value.
- `SpatialAssociationProvenance`: source (`MANUAL | BIM_DERIVED | NOT_ASSIGNED`),
  method (`BIM_ROOM_VOLUME | BIM_ROOM_FOOTPRINT | BIM_ELEMENT_RANGE |
  STOREY_ELEVATION_RANGE | DERIVED_RANGE | NONE`), backing Bentley source element
  ids, tested point, and boundary policy flag.
- Deterministic association: `associateFloor` (storey vertical-range containment,
  else nearest-elevation labelled `DERIVED_RANGE`; ties → `AMBIGUOUS`);
  `associateRoom` (VOLUME → range3, FOOTPRINT → point-in-polygon, RANGE_ONLY →
  range3 labelled derived; multiple hits → `AMBIGUOUS`, no arbitrary pick).
- `ROOM_ASSOCIATION_POINT = ASSET_INSTANCE_ORIGIN` (documented first method;
  whole-equipment footprint containment deferred to clearance work).
- Boundary policy: `SPATIAL_BOUNDARY_INCLUSIVE = true` — a point exactly on a
  floor range bound or a room range/footprint edge is treated as inside,
  uniformly and deterministically.

Bentley adapter — `frontend/src/components/spatial/bentleySpatialAdapter.ts`
(the only spatial module importing `@itwin`; reached via dynamic import so vitest
never pulls the Bentley stack). Read-only ECSQL discovery:
- Probes candidate classes (`BuildingSpatial:Story`, `SpatialComposition:*`,
  `BisCore:SpatialLocationElement`, `BuildingSpatial:Space`) with bounded
  `COUNT(*)` + one example each; classes absent from the schema are skipped.
- Builds `SpatialModelSemantics` from present classes, reading element ranges
  from `bis.GeometricElement3d` placement bbox (RANGE_ONLY authority in this
  foundation; VOLUME/FOOTPRINT extraction is a future refinement). Absence is
  reported as `NOT_AVAILABLE`, never faked.
- Never inserts/updates; no changeset.

Derived association wiring — appended to `spatialAssetOverlay.ts`:
- Cached `SpatialModelSemantics` refreshed EXPLICITLY (`refreshModelSemantics`),
  never per-frame. `getAssociationForInstance` computes from the COMMITTED
  position + cache (pure wrt the asset). Two DEV inspectors:
  `inspectBimSpatialStructure`, `inspectSpatialAssociation`.

Product UI — `ViewerAssetLibrary.tsx`:
- Selected-asset detail now shows Floor / Room / Source / Method rows with honest
  labels ("Not available from BIM" vs "Not found at position" vs the assigned
  name+id). Association recomputes on selection + COMMITTED position change; it
  is SKIPPED while a drag/rotation preview is active (no authoritative floor/room
  change per preview frame).

DEV controls — `BentleyViewer.tsx`: added `INSPECT BIM SPATIAL STRUCTURE` and
`INSPECT SPATIAL ASSOCIATION` buttons, following the existing bounded dynamic-
import handler pattern. All existing DEV controls preserved.

## Machine verification

```
PRECHECK_HEAD        = fc355ab29fd19d7f9c2dde84d7c95069bb502233
PRECHECK_ORIGIN_MAIN = fc355ab29fd19d7f9c2dde84d7c95069bb502233
PRECHECK_DIVERGENCE  = 0 / 0

TYPECHECK               = PASS
OFFLINE_TEST_COUNT      = 254
NEW_TEST_COUNT          = 37 (spatialSemantics.test.ts; +6 invariant/consistency, +6 finite-range/honest-semantics, +3 multi-room/containment) — vs 217 checkpoint baseline
OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD        = PASS
CORE_FRONTEND_VERSION   = 5.12.5
WORKER_ASSET_REAL       = YES  ( (()=>{"use strict"; )
DRACO_WASM_ASSET_REAL   = YES  ( \0asm )
DEV_SERVER /viewer      = 200  worker=text/javascript  wasm=application/wasm

FLOOR_ASSOCIATION_IMPLEMENTED = YES   ROOM_ASSOCIATION_IMPLEMENTED = YES
FLOOR_ASSOCIATION_DETERMINISTIC = PASS   SPATIAL_BOUNDARY_POLICY = INCLUSIVE
SPATIAL_ASSOCIATION_PROVENANCE = PASS
SPATIAL_ASSOCIATION_POSITION_IMMUTABILITY = PASS
SPATIAL_ASSOCIATION_IDENTITY_IMMUTABILITY = PASS
DRAG_COMMIT_REASSOCIATION = PASS   DRAG_PREVIEW_ASSOCIATION_NON_AUTHORITATIVE = PASS
ROTATION_ASSOCIATION_IMMUTABILITY = PASS   DELETE_SPATIAL_ASSOCIATION_ISOLATION = PASS
SPATIAL_ASSOCIATION_STATUS_SEMANTICS = PASS   AMBIGUOUS_ROOM_NOT_SILENTLY_ASSIGNED = PASS
SPATIAL_DOMAIN_BENTLEY_INDEPENDENT = PASS

ROOM_ASSOCIATION_CHANGES_POSITION = NO   FLOOR_ASSOCIATION_CHANGES_POSITION = NO
AUTOMATIC_ROOM_ASSIGNMENT = NO   ROOM_SNAPPING_IMPLEMENTED = NO   FLOOR_SNAPPING_IMPLEMENTED = NO
COLLISION_DETECTION_IMPLEMENTED = NO   CLEARANCE_ENFORCEMENT_IMPLEMENTED = NO
SPATIAL_VALIDITY_BLOCKS_DRAG = NO   SPATIAL_VALIDITY_BLOCKS_ROTATION = NO   SPATIAL_VALIDITY_BLOCKS_PLACEMENT = NO

AUTH_FLOW_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO   TRANSPARENCY_WORK_RESUMED = NO   CAMERA_BEHAVIOR_CHANGED = NO
IMODEL_MODIFIED = NO   BENTLEY_CHANGESET_CREATED = NO   BENTLEY_RESOURCE_MODIFIED = NO
PLACEMENT_REGRESSION = 0   DIRECT_DRAG_REGRESSION = 0   OBJECT_ATTACHED_ROTATION_REGRESSION = 0   DELETE_REGRESSION = 0
```

## Live BIM discovery — MANUAL CONFIRMATION REQUIRED

The actual floor/room class inventory, counts, and geometry availability of the
CONNECTED iModel can only be established from the live session. The offline
fixtures prove the association logic; they do NOT assert what the real BIM
contains. These require the browser DEV inspectors:

```
SPATIAL_CLASS_INVENTORY               = MANUAL_CONFIRMATION_REQUIRED (INSPECT BIM SPATIAL STRUCTURE)
FLOOR_SOURCE_CLASS / CONFIDENCE       = MANUAL_CONFIRMATION_REQUIRED
ROOM_SOURCE_CLASS / COUNT / CONFIDENCE / GEOMETRY_TYPE = MANUAL_CONFIRMATION_REQUIRED
ROOM_ASSIGNMENT_SOURCE                = BIM_DERIVED (when a room is found) else NOT_ASSIGNED
BIM_SPATIAL_STRUCTURE_VISIBLE_IN_BROWSER = MANUAL_CONFIRMATION_REQUIRED
FLOOR_ASSOCIATION_VISIBLE_IN_BROWSER     = MANUAL_CONFIRMATION_REQUIRED
ROOM_ASSOCIATION_VISIBLE_IN_BROWSER      = MANUAL_CONFIRMATION_REQUIRED
DRAG_COMMIT_REASSOCIATION_VISIBLE_IN_BROWSER = MANUAL_CONFIRMATION_REQUIRED (NOT_TESTABLE_WITH_CURRENT_BIM if <2 usable regions)
```

If the connected BIM genuinely lacks explicit room/space objects, the correct
and ACCEPTED result is `ROOM_SOURCE_CLASS = NOT_AVAILABLE` and room status
`NOT_AVAILABLE_FROM_BIM` — honest absence is a valid engineering outcome, not a
failure.

## Targeted correction — floor UI/inspector consistency + status↔reference invariant

Manual evidence (accepted): `BIM_SPATIAL_STRUCTURE_VISIBLE_IN_BROWSER = YES`,
`BIM_SPATIAL_INVENTORY_MANUAL_ACCEPTANCE = PASS`, `SPATIAL_ASSOCIATION_MANUAL_VISIBILITY = PASS`.
Live inventory: `floorClass = SpatialComposition:CompositeElement`,
`roomClass = BuildingSpatial:Space (8)`, `floorAvail/roomAvail = AUTHORITATIVE_BIM`.
For `PETCT-GE-DISCOVERY-MI-0001`: `room = NOT_FOUND_AT_POSITION`, `validity =
OUTSIDE_MODELED_ROOM` — a valid engineering result (not forced).

Inconsistency: Placed Assets showed `Floor = ASSIGNED` while INSPECT SPATIAL
ASSOCIATION showed `floor = undefined` for the SAME asset.

`FLOOR_INCONSISTENCY_ROOT_CAUSE = C (STATUS_REFERENCE_INCONSISTENCY)` surfaced by
an adapter honesty gap and rendered two different ways by two formatters (classes
A/E). Both consumers DID read one shared result (`getAssociationForInstance`),
but that result could hold `floorStatus = ASSIGNED` with `floor = undefined`
(the live `SpatialComposition:CompositeElement` floors carry no placement
geometry, so no range/elevation — yet floor availability was still asserted).
The Placed Assets formatter rendered that invalid state as the bare word
`'ASSIGNED'`; the inspector rendered `undefined (undefined)`.

Correction (defect-only, no redesign):
1. Domain invariant (`normalizeAssignment` in `computeSpatialAssociation`): an
   `ASSIGNED` status without a concrete `floorId`/`roomId` is downgraded to
   `NOT_FOUND_AT_POSITION` (reference cleared). `ASSIGNED` can no longer coexist
   with a missing reference. `assignmentInvariantHolds` exported for tests.
2. Single shared formatter (`formatAssociationSlotLabel`) in the domain — both
   the Placed Assets UI and the DEV inspector render through it, so they cannot
   disagree. It never prints bare `ASSIGNED`.
3. Inspector (`summarizeAssociation`) now exposes BOTH status AND id AND label
   for floor and room explicitly (no compressed single field), plus
   `semanticsGeneration`.
4. Adapter honesty: when discovered floors expose no usable range OR elevation,
   `floorAvailability` is downgraded (→ association honestly reports
   `NOT_FOUND_AT_POSITION`, not a fabricated floor). `COMPOSITE_ELEMENT_FLOOR_
   INTERPRETATION` = composite/structure nodes, generally NOT storeys and
   without placement geometry; not asserted as authoritative floors.
5. Semantics generation stamped on every refresh; both consumers load semantics
   before computing (UI awaits `isSemanticsLoaded()`), so they share one
   generation (guards class B). INSPECT BIM SPATIAL STRUCTURE now also lists the
   8 space ranges (`summarizeRoomRanges`) so the NOT_FOUND result can be
   validated against the actual ranges.

```
FLOOR_INCONSISTENCY_ROOT_CAUSE                = C (+A/E rendering; B guarded)
ASSIGNED_FLOOR_REQUIRES_REFERENCE             = PASS
ASSIGNED_ROOM_REQUIRES_REFERENCE              = PASS
FLOOR_UI_INSPECTOR_CONSISTENCY (offline)      = PASS
ROOM_UI_INSPECTOR_CONSISTENCY (offline)       = PASS
FLOOR_DISPLAY_IDENTITY_NOT_STATUS             = PASS
ROOM_NOT_FOUND_DISPLAY                        = PASS
SPATIAL_ASSOCIATION_CALCULATION_ARCHITECTURE  = ONE_SHARED_SEAM
ROOM_SOURCE_CLASS = BuildingSpatial:Space   ROOM_OBJECT_COUNT = 8   ROOM_SOURCE_CONFIDENCE = AUTHORITATIVE_BIM
ROOM_GEOMETRY_TYPE = RANGE_ONLY (placement bbox) or METADATA_ONLY
FLOOR_SOURCE_CLASS = SpatialComposition:CompositeElement
FLOOR_SOURCE_CONFIDENCE = DERIVED or NOT_AVAILABLE (evidence-based; not asserted AUTHORITATIVE without range/elevation)
FLOOR_ASSOCIATION_BASIS = STOREY/COMPOSITE vertical range if present else NEAREST_ELEVATION (DERIVED_RANGE)
```

`OFFLINE_TEST_COUNT = 245` (6 new). Manual browser re-test of consistency + the
live NOT_FOUND validation remains required (below).

## Targeted correction — Developer Inspector UX + finite BIM range extraction

Manual evidence (accepted): consistency fix confirmed; body drag / rotation /
DELETE regression 0; live BIM exposes 8 `BuildingSpatial:Space` objects. Two
defects remained: (1) verbose DEV text painted over the 3D viewport; (2) room
ranges displayed as `low=(NaN,NaN,NaN) high=(NaN,NaN,NaN)`.

Objective A — Developer Inspector panel:
Verbose DEV diagnostics now render in a dedicated collapsible, scrollable
Developer Inspector panel in the right-side inspection area — never painted over
the 3D viewport. All INSPECT actions (Generic/Catalog PET/CT, Placement Intent,
Direct Drag, Rotation, BIM Spatial Structure, Spatial Association, Feature
Appearance, Render State) target the panel via a bounded UI-only state
(`{open,title,content}`) with CLEAR (empties content) and CLOSE (hides). The
panel is `UI_ONLY` (not in SpatialAssetStore), updates only on explicit inspect
clicks (no polling), and neither CLEAR nor CLOSE mutates asset/BIM/viewer state.
Short SHOW/HIDE/FIT statuses remain compact. All DEV capabilities preserved.
```
DEV_INSPECTOR_UX_CORRECTION_IMPLEMENTED = YES
VERBOSE_DEV_TEXT_OVER_3D_VIEWPORT       = NO
DEV_INSPECT_ACTION_TARGET               = DEVELOPER_INSPECTOR_PANEL
DEV_INSPECTOR_STATE_AUTHORITY           = UI_ONLY   DEV_INSPECTOR_UPDATE = EXPLICIT_EVENT
DEV_INSPECTOR_LONG_OUTPUT               = SCROLLABLE
DEV_INSPECTOR_CLEAR/CLOSE_MUTATES_ENGINEERING_STATE = NO / NO
```

Objective B — finite range extraction:
`SPACE_RANGE_NAN_ROOT_CAUSE`: the adapter selected the point/struct columns
`BBoxLow`/`BBoxHigh` directly under `UseECSqlPropertyIndexes`; the struct objects
were not decomposed, so their `.x/.y/.z` were undefined and `lo.x + origin.x`
produced `undefined + number = NaN`, which was then accepted as a `RANGE_ONLY`
range. `SPACE_RANGE_RAW_VALUE_TYPE` = point/struct column (object, not scalar
under index format).

Fix: query EXPLICIT SCALAR columns (`BBoxLow.X, .Y, .Z, BBoxHigh.X, .Y, .Z,
Origin.X, .Y, .Z`) so every value is a number, then validate with the pure
`validateWorldRange` (rejects any non-finite coordinate; normalizes low<=high).
A non-finite/malformed range yields `undefined` → the room is `METADATA_ONLY`,
never a fake `RANGE_ONLY`. Same discipline applies to floor ranges.

Honest containment semantics (critical): `associateRoom` now counts rooms with
USABLE geometry. If room objects exist but NONE are testable, it returns
`NOT_AVAILABLE_FROM_BIM` — NOT `NOT_FOUND_AT_POSITION`. `OUTSIDE_MODELED_ROOM`
validity requires at least one usable room geometry. Room SOURCE stays
`AUTHORITATIVE_BIM` (the BIM defines rooms) even when geometry is metadata-only —
source confidence is distinct from geometry capability.
```
ROOM_RANGE_REQUIRES_FINITE_COORDINATES = YES   NONFINITE_ROOM_RANGE_ACCEPTED = NO
ROOM_RANGE_ORDER_VALIDATED = YES   NONFINITE_FLOOR_RANGE_ACCEPTED = NO
ROOM_SOURCE_CLASS = BuildingSpatial:Space   ROOM_SOURCE_CONFIDENCE = AUTHORITATIVE_BIM
ROOM_GEOMETRY_TYPE = RANGE_ONLY (if finite bbox present) else METADATA_ONLY
NOT_FOUND_REQUIRES_USABLE_ROOM_GEOMETRY = PASS
OUTSIDE_ROOM_REQUIRES_USABLE_GEOMETRY   = PASS
```
Whether the live 8 spaces yield finite ranges (`USABLE_ROOM_RANGE_COUNT`) or are
metadata-only is established by INSPECT BIM SPATIAL STRUCTURE in the browser — it
now prints each space with a finite `low/high` or `RANGE_UNAVAILABLE`, never NaN.

`OFFLINE_TEST_COUNT = 251` (6 new). Manual re-test of the panel UX + range
extraction remains required (below).

## Completion — manual UX + finite-range acceptance; live room validation pending

Manual browser acceptance now confirms:
```
DEV_INSPECTOR_UX_VISIBLE_IN_BROWSER   = PASS   (verbose diagnostics in the right-side panel)
DEV_INSPECTOR_CLEAR_VISIBLE_IN_BROWSER = PASS   DEV_INSPECTOR_CLOSE_VISIBLE_IN_BROWSER = PASS
VERBOSE_DEV_TEXT_OVER_3D_VIEWPORT     = NO      DEV_INSPECT_ACTION_TARGET = DEVELOPER_INSPECTOR_PANEL
DEV_INSPECTOR_LONG_OUTPUT = SCROLLABLE   STATE_AUTHORITY = UI_ONLY   UPDATE = EXPLICIT_EVENT
ROOM_RANGE_EXTRACTION_VISIBLE_IN_BROWSER = PASS   NONFINITE_ROOM_RANGE_VISIBLE = NO   BIM_SPACE_RANGE_EXTRACTION_VALID = YES
```
The live inventory shows finite ranges, e.g. Floor 1 Main Corridor
low=(12,7,0) high=(18,13,3); Radiopharmacy low=(2,12,0) high=(8,18,3);
Cyclotron Room low=(9,12,0) high=(15,18,3); and further `BuildingSpatial:Space`
records (8 total). The prior NaN defect is corrected.

```
BIM_SPACE_OBJECT_COUNT = 8   ROOM_SOURCE_CLASS = BuildingSpatial:Space   ROOM_SOURCE_CONFIDENCE = AUTHORITATIVE_BIM
ROOM_GEOMETRY_TYPE = RANGE_ONLY (finite bbox ranges observed)
USABLE_ROOM_RANGE_COUNT  = MANUAL (read the full 8-space inventory in the panel)
INVALID_ROOM_RANGE_COUNT = MANUAL (expected 0 — no NaN shown)
```

Offline coverage added this step (structural, not a claim about the live BIM):
`MULTI_ROOM_FINITE_RANGE_VALIDATION` (8 finite/ordered ranges),
`ROOM_POINT_CONTAINMENT_DETERMINISTIC` (0 / 1 / multiple resolve deterministically,
repeatable), and position-immutability during containment. `OFFLINE_TEST_COUNT = 254`.

Current scanner containment: `CURRENT_SCANNER_POSITION`, `CURRENT_ROOM_STATUS`,
and `CURRENT_ROOM_NOT_FOUND_VALIDATED` are MANUAL — compare the selected
scanner's committed position (INSPECT SPATIAL ASSOCIATION) against the 8 finite
ranges (INSPECT BIM SPATIAL STRUCTURE). If it lies in none, `NOT_FOUND_AT_POSITION`
+ `OUTSIDE_MODELED_ROOM` is validated. A practical live room candidate (prefer
Scanner Room) is identified from the panel; the user drags the scanner in
manually (no programmatic relocation) to prove `roomStatus = ASSIGNED`.

Recorded FUTURE work (NOT implemented here):
- `ROTATION_HANDLE_VISUAL_REFINEMENT_REQUIRED = YES`; preferred idle appearance
  `FAINT_GREY_OR_HIDDEN`; `UNSELECTED_ASSET_ROTATION_HANDLE_REQUIRED = NO`;
  `CATALOG_TEST_GEOMETRY_ROTATION_HANDLE_REQUIRED = NO`.
- `MULTI_ASSET_SELECTION = NO`, `GROUP_TRANSLATION = NO` (current:
  `SINGLE_ASSET_SELECTION = YES`, `SINGLE_ASSET_TRANSLATION = YES`).
  `NEXT_BUILD = MULTI_SELECT_AND_GROUP_TRANSLATION_FOUNDATION` (no group identity
  collapse; one ASSET_MOVED per moved instance; group rotation specified separately).

## LIVE room assignment — MANUAL BROWSER evidence (PASS)

The user manually dragged `PETCT-GE-DISCOVERY-MI-0001` and the committed
position associated to a real BIM `BuildingSpatial:Space`. Developer Inspector
(live browser, not offline fixture):
```
CURRENT_SCANNER_ASSET_INSTANCE_ID = PETCT-GE-DISCOVERY-MI-0001
CURRENT_SCANNER_POSITION          = (12.00, 7.92, 4.85)
roomStatus  = ASSIGNED     roomId = 0x20000000018     roomLabel = Floor 2 Main Corridor
method      = DERIVED_RANGE  source = BIM_DERIVED       validity = VALID_ASSOCIATED
floorStatus = AMBIGUOUS     floorId = NONE  floorLabel = NONE   (semanticsGeneration = 2)

LIVE_ROOM_ASSIGNMENT_VISIBLE_IN_BROWSER      = PASS
DRAG_COMMIT_REASSOCIATION_VISIBLE_IN_BROWSER = PASS
ROOM_ASSOCIATION_CHANGES_POSITION            = NO   AUTHORITATIVE_ROOM_CHANGES_DURING_DRAG_PREVIEW = 0
ROOM_SOURCE_CLASS = BuildingSpatial:Space   ROOM_SOURCE_CONFIDENCE = AUTHORITATIVE_BIM   ROOM_GEOMETRY_TYPE = RANGE_ONLY
```
Floor `AMBIGUOUS` (no `floorId`) is a correct, preferred result — an ambiguous
floor is honestly reported rather than an unsupported assignment. The invariant
holds (AMBIGUOUS carries no reference). Room + floor remain consistent between
Placed Assets and the Developer Inspector. This is the first LIVE-browser proof
(beyond offline fixtures) that a finite `BuildingSpatial:Space` range drives a
real BIM-derived room association.

`CHECKPOINT = HOLD_FOR_AUTH_DIAGNOSIS_REVIEW` — spatial foundation has its live
evidence; a separate page-refresh auth defect is under diagnosis (see
`MRT_PHARMA_PAGE_REFRESH_AUTH_DIAGNOSIS.md`). Awaiting explicit checkpoint
authorization.

## Manual acceptance steps (STOP — do not checkpoint)

1. Open `http://localhost:3000/viewer`.
2. DEV → `INSPECT BIM SPATIAL STRUCTURE`; capture the class inventory / counts /
   availability from the `fitNote` + console `[bentley-spatial]`.
3. Place / select the GE HealthCare Discovery MI; DEV → `INSPECT SPATIAL
   ASSOCIATION`; confirm floor/room status + provenance + source element ids.
   The Placed Assets detail also shows Floor/Room/Source/Method rows.
4. If ≥2 usable regions exist, drag the scanner across a boundary, release, and
   confirm the association recomputes after commit (identity unchanged). Else
   record `NOT_TESTABLE_WITH_CURRENT_BIM`.
5. Brief regression: body drag, object-attached rotation, DELETE control, Asset
   Library placement all still work.

# MRT Pharma — Credible Demo BIM Transition Plan (preparation only)

Baseline `HEAD = origin/main = b2abe6bf28056d002d140b52fb54e94c9cd417eb`, divergence `0 / 0`. Uncommitted visual-planning + audit work retained. No IFC imported, no iModel created, no code changed, no checkpoint.

## A. Connected iModel audit — CLOSED (live browser evidence)

```
CONNECTED_IMODEL_CLASSIFICATION = PARTIAL_ARCHITECTURAL_BIM
CONNECTED_IMODEL_CLASSIFICATION_CONFIDENCE = HIGH
IMODEL_MODEL_COUNT = 5            GEOMETRIC_3D_MODEL_COUNT = 1
GEOMETRIC_ELEMENT3D_COUNT = 12    PHYSICAL_ELEMENT_COUNT = 3
SPATIAL_LOCATION_ELEMENT_COUNT = 9
BUILDINGSPATIAL_SPACE_COUNT = 8   BUILDINGSPATIAL_STORY_COUNT = 0
SPATIALCOMPOSITION_COMPOSITE_COUNT = 12
ARCHITECTURAL_WALL_COUNT = 12     ARCHITECTURAL_SLAB_OR_FLOOR_COUNT = 0    ARCHITECTURAL_DOOR_COUNT = 0
CURRENT_IMODEL_RECOMMENDATION = RETAIN_AS_ENGINEERING_TEST_FIXTURE
CURRENT_IMODEL_ROLE = ENGINEERING_REGRESSION_FIXTURE
CURRENT_VISUAL_LIMITATION_ROOT_CAUSE = SOURCE_MODEL_GEOMETRY_LIMITATION
CREDIBLE_HOSPITAL_DEMO_BIM_REQUIRED = YES
```

12 wall-like elements exist, but with 0 floors/slabs, 0 doors, 0 stories, and only 12 GeometricElement3d total, the connected model is a PARTIAL architectural BIM — good for engineering regression, insufficient as a showcase medical facility. This is corroborated locally by `bim_test_assets/mrt_pharma_hospital_bim_proof_manifest.json`, which declares `mrtway_model_class = SYNTHETIC_TEST_BIM` with 8 IFCSPACE rooms matching the observed labels.

The current fixture is retained (not deleted/replaced) for placement / selection / drag / rotation / right-click / selection-box / group translation / delete / spatial-association regression.

## B. IFC ingestion preparation

### Candidate

- `PRIMARY_DEMO_BIM_CANDIDATE = MedicalClinic_ARC.ifc` (~15.5 MB; architectural discipline, medical context, small enough for a controlled first ingestion). Secondary: `NBU_MedicalClinic_ARC.ifc` (~18.1 MB).
- `MEDICALCLINIC_ARC_LOCAL_FILE_STATUS = NOT_FOUND` — a filesystem search found only `bim_test_assets/mrt_pharma_hospital_bim_proof.ifc`. Neither the IFC nor a BIMData catalog file is present in the repo. I did not fabricate a path.
- `MEDICALCLINIC_ARC_SOURCE = NOT_ESTABLISHED_FROM_LOCAL_EVIDENCE` (referenced conversationally as the BIMData R&D catalog; no local catalog metadata to confirm).
- `MEDICALCLINIC_ARC_LICENSE = NOT_ESTABLISHED`; `COMMERCIAL_DEMO_USE_LICENSE_CONFIRMED = NO`. Licensing uncertainty is explicit.

### Supported Bentley path (verified, not guessed)

`IFC_TO_IMODEL_SUPPORTED_PATH` = Bentley **iTwin Synchronization (Connectors)**. Two supported options ([Synchronization API](https://developer.bentley.com/apis/synchronization/), [Get started](https://developer.bentley.com/get-started/)):
1. **iTwin Synchronizer** desktop app — synchronize the IFC into a new iModel on iModelHub.
2. **iTwin Platform Synchronization API** with the IFC connector — create/populate the iModel in the cloud.

Both produce/populate an iModel from the IFC; the viewer then opens it by id. *Content rephrased for compliance with licensing restrictions.*

- `CURRENT_VIEWER_DIRECT_RAW_IFC_SUPPORT = NO`. The frontend uses `@itwin/web-viewer-react` `<Viewer authClient iTwinId iModelId>`. Installed `@itwin` packages are frontend/viewer + `imodels-access` + `imodels-client-management` only — no IFC connector, no iModel transformer, no backend authoring. The viewer opens an existing iModel; it cannot convert IFC.
- Post-ingestion wiring is a **config change, not a code change**: point `VITE_BENTLEY_IMODEL_ID` (and `VITE_BENTLEY_ITWIN_ID` if a new iTwin) at the demo iModel. The engineering fixture id is retained separately.

### Proposed demo identity (not created)

- `PROPOSED_DEMO_IMODEL_NAME = "MRTway Medical Clinic Demo"`
- `ENGINEERING_FIXTURE_IMODEL = MRTway Hospital Campus Development` (current, retained)
- `DEMO_ARCHITECTURAL_IMODEL = SEPARATE MODEL`

### Required inputs + readiness

`IFC_INGESTION_REQUIRED_INPUTS`:
- MedicalClinic_ARC.ifc local file — **NOT_AVAILABLE**
- an iTwin id to host the demo iModel — AVAILABLE (existing twin or a new demo twin)
- Bentley auth with synchronization/iModel permissions — **UNKNOWN** (the SPA is a viewer PKCE client; connectors need appropriate scopes/roles)
- iModel creation permission — **UNKNOWN**
- IFC connector / Synchronization API access or iTwin Synchronizer — **NOT_AVAILABLE** (external tooling)
- file upload container for the IFC — **NOT_AVAILABLE**

`IFC_INGESTION_READINESS = BLOCKED` — blocked by: the IFC file is not present locally; no connector/synchronization tooling or confirmed permissions here; commercial demo licensing not established.

### First experiment success criteria (future)

A separate demo iModel exists; MedicalClinic_ARC architectural geometry is present; the current viewer opens it; walls/floors/doors (or equivalent) are visible; camera navigation works. NOT yet required: PET/CT placement, room association, MRT guideway, clearance, simulation.

### Post-ingestion first operation

Run the SAME RUN BIM CONTENT AUDIT against the demo iModel and compare to the engineering fixture (GeometricElement3d, PhysicalElement, wall, door, floor/slab, story, space, model count, schemas). Do not assume conversion succeeded because the viewer opens. `DEMO_BIM_VISUAL_REALISM = MANUAL_CONFIRMATION_REQUIRED`; `DEMO_BIM_ROOM_SEMANTICS = AUDIT_AFTER_INGESTION`.

## Equipment — next step recorded only (not implemented)

`NEXT_EQUIPMENT_VISUAL_MILESTONE = GLTF_GLB_GEOMETRY_REPRESENTATION_FOUNDATION`. Future: `AssetDefinition -> AssetInstance -> GeometryRepresentation { PARAMETRIC_GENERIC | GLTF_GLB | MANUFACTURER_MODEL }`. `MANUFACTURER_CERTIFIED_GEOMETRY_CLAIM = NO`. Current PET/CT stays `GENERIC_ENGINEERING_PLACEHOLDER`.

## Constraints honored

```
ASSET_INSTANCE_ARCHITECTURE_CHANGED = NO   VISUAL_CODE_CHANGED = NO
AUTH_FLOW_CHANGED = NO   PKCE_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO
INTERACTION_CODE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO
CURRENT_FIXTURE_VISUAL_BEAUTIFICATION_CONTINUED = NO
SECRET_EXPOSED = NO   IFC_IMPORTED = NO   DEMO_IMODEL_CREATED = NO
CHECKPOINT = NONE
```

## Next authorization needed

To proceed to ingestion, a subsequent prompt must authorize it and provide: the MedicalClinic_ARC.ifc file locally (or a fetch location), confirmation of licensing for demo use, and Bentley synchronization/iModel-creation access on a target iTwin.

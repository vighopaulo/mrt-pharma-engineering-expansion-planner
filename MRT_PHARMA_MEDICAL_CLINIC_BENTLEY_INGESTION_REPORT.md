# MRT Pharma — Medical Clinic Bentley Ingestion Report

IFC located and verified. Bentley ingestion **BLOCKED** on connector tooling + unconfirmed create/synchronize permissions. No iModel created, no code changed, no checkpoint. Baseline `HEAD = origin/main = b2abe6bf28056d002d140b52fb54e94c9cd417eb`, `0 / 0`, nothing staged; existing uncommitted work preserved.

## IFC located + verified

```
CLINIC_ARCHITECTURAL_IFC_STATUS = FOUND
CLINIC_ARCHITECTURAL_IFC_PATH = /Users/paulonaodowan/Downloads/Clinic_Architectural.ifc
CLINIC_IFC_SCHEMA = IFC2X3   (ISO-10303-21 STEP; Autodesk Revit Architecture 2011 export)
CLINIC_IFC_IDENTITY_VERIFIED = YES
```

Representative entity counts (bounded read-only `grep -c`) match the stated model exactly:

| Entity | Count |
|---|---|
| IfcWallStandardCase | 1065 |
| IfcDoor | 254 |
| IfcWindow | 58 |
| IfcSpace | 269 |
| IfcBuildingStorey | 4 |
| IfcSlab | 3 |
| IfcCovering | 250 |
| IfcPlate | 172 |
| IfcFurnishingElement | 118 |
| IfcFlowTerminal | 102 |

## Source / license

- `CLINIC_IFC_SOURCE` = NIBS Common BIM Files (`portal.nibs.org`) via the BIMData R&D IFC catalog (`~/Downloads/IFC_FILES.md`), Medical Clinic ARC discipline (`MedicalClinic_ARC.ifc`).
- `CLINIC_IFC_LICENSE` = CC BY 4.0 (per your independent sample-viewer evidence; the local catalog lists the NIBS source but does not itself print a license string — recorded honestly, not overstated).
- `LOCAL_TECHNICAL_EVALUATION_ALLOWED = YES`.

## Bentley capability probe (the readiness gate)

READ access ≠ CREATE ≠ SYNCHRONIZE. Probed actual environment:

```
BENTLEY_IMODEL_READ_ACCESS = YES        (SPA viewer opens the existing fixture)
BENTLEY_IMODEL_CREATE_ACCESS = UNKNOWN  (createEmpty exists in imodels-client-management, but that is an empty shell, not IFC ingestion; scopes unconfirmed)
BENTLEY_SYNCHRONIZATION_ACCESS = UNKNOWN
BENTLEY_IFC_CONNECTOR_AVAILABLE = NO
BENTLEY_UPLOAD_STORAGE_AVAILABLE = UNKNOWN
CURRENT_VIEWER_DIRECT_RAW_IFC_SUPPORT = NO
SELECTED_IFC_TO_IMODEL_PATH = NOT_AVAILABLE
DEMO_IMODEL_INGESTION_READINESS = BLOCKED
```

Evidence:
- iTwin Synchronizer desktop app **not installed** (and it is Windows-only; this host is macOS).
- No connector/bridge CLI on PATH; no `@itwin/imodel-transformer` or connector/synchronization packages in the project.
- Frontend `@itwin` packages are viewer + `imodels-access` + `imodels-client-management` only (read/manage, not IFC conversion).
- `.env` holds only browser-safe viewer PKCE config (presence-checked; no SYNC/CONNECTOR/SERVICE/SECRET keys; values never read).

## What was NOT done (correctly, per sections 11 & 30)

```
DEMO_IMODEL_CREATED = NO         IFC_INGESTION_STARTED = NO      IFC_INGESTION_COMPLETED = NO
SOURCE_IFC_MODIFIED = NO         DEMO_IMODEL_OPENED_IN_EXISTING_VIEWER = NO
DEMO_BIM_CONTENT_AUDIT_COMPLETED = NO
FRONTEND_CHANGED_BEFORE_SUCCESSFUL_INGESTION = NO   (did not code around the missing Bentley capability)
SUBSTITUTE_BIM_IMPROVISED = NO
```

## How to unblock (exact Bentley steps)

The IFC is ready; the missing piece is a supported IFC→iModel connector run + a demo iModel id.

- **Option A — iTwin Synchronizer (desktop).** On a Windows machine, install the iTwin Synchronizer, sign in with a Bentley account that has create+synchronize rights on the MRTway Development Twin (`bdf29ecd-…`), create a new iModel **MRTway Medical Clinic Demo**, add `Clinic_Architectural.ifc`, and run synchronization (IFC connector).
- **Option B — Synchronization API (cloud).** Use the iTwin Platform Synchronization API with the IFC connector — requires a service/agent client with synchronization scopes, a Storage/file container to upload the IFC, and iModel-creation permission on the iTwin.
- **Then:** capture the new demo iModel id and provide it here. This environment can then open it in the existing viewer (config change `VITE_BENTLEY_IMODEL_ID` for the demo, keeping the fixture id separate) and run RUN BIM CONTENT AUDIT against it.

## Demo counts / realism (not yet available)

```
DEMO_GEOMETRIC_ELEMENT3D_COUNT = NOT_AVAILABLE      DEMO_PHYSICAL_ELEMENT_COUNT = NOT_AVAILABLE
DEMO_ARCHITECTURAL_WALL_COUNT = NOT_AVAILABLE        DEMO_ARCHITECTURAL_SLAB_OR_FLOOR_COUNT = NOT_AVAILABLE
DEMO_ARCHITECTURAL_DOOR_COUNT = NOT_AVAILABLE        DEMO_ARCHITECTURAL_WINDOW_COUNT = NOT_AVAILABLE
DEMO_ARCHITECTURAL_CONTENT_MATERIALLY_RICHER = NOT_TESTED  (IFC counts strongly imply YES, but Bentley EC counts are the required evidence)
DEMO_ROOM_SEMANTICS_MAPPING = NOT_YET_ESTABLISHED    DEMO_BIM_VISUAL_REALISM = NOT_TESTABLE
FIRST_DEMO_VIEW_HAS_MRT_ASSET = NO
```

## Constraints honored

```
ENGINEERING_FIXTURE_PRESERVED = YES   IMODEL_FIXTURE_MODIFIED = NO
ASSET_INSTANCE_ARCHITECTURE_CHANGED = NO   INTERACTION_CODE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO
AUTH_FLOW_CHANGED = NO   MANUFACTURER_CERTIFIED_GEOMETRY_CLAIM = NO   SECRET_EXPOSED = NO
NEXT_EQUIPMENT_VISUAL_MILESTONE = GLTF_GLB_GEOMETRY_REPRESENTATION_FOUNDATION (record only)
CHECKPOINT = NONE
```

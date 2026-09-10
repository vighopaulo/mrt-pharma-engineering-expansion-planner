# MRT Pharma — Medical Clinic Demo BIM Ingestion (browser-runtime workflow implemented)

Baseline `HEAD = origin/main = b2abe6bf28056d002d140b52fb54e94c9cd417eb`, `0 / 0`, nothing staged. Implementation complete + verified. The cloud writes run only when YOU select the IFC and press START INGESTION. No checkpoint.

## What was built (Option A)

A DEV-only, explicitly two-stage ingestion workflow, mounted in the Developer drawer (absent in normal mode):

1. **File picker** — you select `Clinic_Architectural.ifc`. Selecting a file does nothing else.
2. **PREFLIGHT** (read-only) — reads the file header (confirms `ISO-10303-21` / `IFC2X3`) and does a GET-only existing-name check for `MRTway Medical Clinic Demo`. If the header is wrong or that iModel already exists, START stays disabled.
3. **START INGESTION** (explicit, writes) — only enabled after a passing preflight. Runs the verified iTwin cloud sequence:
   - re-check existing iModels (safety) → **POST /imodels** create `MRTway Medical Clinic Demo` (never the fixture)
   - **GET /storage** root folder → **POST** file metadata → **PUT** the bytes to the returned Azure upload URL (`x-ms-blob-type: BlockBlob`, no auth header) → **POST** complete
   - **POST /synchronization/imodels/storageConnections** with `connectorType: "IFC"` → **POST .../run** → poll **GET .../runs** until terminal
   - reports `IFC_SYNCHRONIZATION_STATUS = SUCCEEDED / FAILED` from the actual run state (not from "upload done" or "202 accepted").

Endpoint sequence verified against Bentley's Storage and Synchronization tutorials. *Content rephrased for licensing compliance.*

### Safety properties
- Token comes only from the existing runtime (`IModelApp.authorizationClient.getAccessToken()`); it is never shown, logged, or persisted.
- Targets a SEPARATE iModel; existing-name check aborts on a duplicate; `MRTway Hospital Campus Development` is never referenced for any write.
- The source IFC is never modified (read as a browser `File`).
- Nothing auto-runs on page load or on file selection.

### Open-the-demo seam
A temporary, non-destructive URL override `/viewer?imodel=<id>` (guarded by `isPlausibleBentleyId`) opens the demo iModel after a successful sync. With no query param, the engineering fixture loads unchanged — the env default is untouched. The panel prints the exact `/viewer?imodel=<DEMO_IMODEL_ID>` link on success.

## Machine verification

```
TYPECHECK = PASS
OFFLINE_TEST_COUNT = 352   NEW_TEST_COUNT = 2   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5
WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES   /viewer = 200
```

IFC re-verified: IFC2X3, walls=1065, doors=254, windows=58, spaces=269, storeys=4.

## Live write results — PENDING YOUR ACTION

```
DEMO_IMODEL_CREATED = PENDING_USER_START      DEMO_IMODEL_NAME = MRTway Medical Clinic Demo   DEMO_IMODEL_ID = NOT_CREATED
ENGINEERING_FIXTURE_PRESERVED = YES
IFC_UPLOADED = PENDING_USER_START             UPLOADED_SOURCE = Clinic_Architectural.ifc
SYNCHRONIZATION_CONNECTION_CREATED = PENDING_USER_START   SYNCHRONIZATION_CONNECTION_ID = NOT_CREATED
IFC_SYNCHRONIZATION_STARTED = PENDING_USER_START          IFC_SYNCHRONIZATION_STATUS = NOT_STARTED
DEMO_IMODEL_CHANGESET_CREATED = PENDING       DEMO_IMODEL_NONEMPTY = PENDING
DEMO_IMODEL_OPENED_IN_MRT_PHARMA = PENDING (via /viewer?imodel=<id> after SUCCEEDED)
FIRST_DEMO_VIEW_HAS_MRT_ASSET = NO            DEMO_BIM_VISUAL_REALISM = MANUAL_CONFIRMATION_REQUIRED
ENGINEERING_FIXTURE_MODIFIED = NO   SOURCE_IFC_MODIFIED = NO   AUTH_FLOW_CHANGED = NO   SECRET_EXPOSED = NO   CHECKPOINT = NONE
```

## To run it

1. Open `http://localhost:3000/viewer`, sign in, enable **Developer mode**.
2. In the drawer, under **MEDICAL CLINIC DEMO INGESTION**, choose `~/Downloads/Clinic_Architectural.ifc`.
3. Press **PREFLIGHT** — confirm header = `ISO-10303-21_IFC2X3` and existing demo = `NONE`.
4. Press **START INGESTION** — watch the log through to `IFC_SYNCHRONIZATION_STATUS`.
5. On `SUCCEEDED`, open the printed `/viewer?imodel=<DEMO_IMODEL_ID>` and STOP for manual visual acceptance (facility only, no MRT assets).

Paste the panel output back and I'll record the live results and set `DEMO_IMODEL_NONEMPTY` / open confirmation.

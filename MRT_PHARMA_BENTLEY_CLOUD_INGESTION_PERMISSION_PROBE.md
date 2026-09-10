# MRT Pharma — Bentley Cloud Ingestion Permission Probe (read-only)

Baseline `HEAD = origin/main = b2abe6bf28056d002d140b52fb54e94c9cd417eb`, `0 / 0`, nothing staged. No writes, no code changes, no checkpoint.

## The honest constraint on this probe

The iModels / Storage / Synchronization APIs all require an OAuth bearer token with the `itwin-platform` scope. That token exists **only inside the authenticated browser (PKCE SPA) runtime** — it is not available from this terminal, and this task holds `FRONTEND_CODE_CHANGED = NO`, so I did not add an in-browser GET probe. Consequently the account-permission verdicts that depend on the live token are honestly `UNKNOWN` here and must be resolved either on the Bentley portal or via a future in-browser read-only probe. No authenticated Bentley HTTP calls were made (`WRITE_API_CALL_COUNT = 0`, and zero read calls too, for the same token reason).

## Findings

```
CLINIC_ARCHITECTURAL_IFC_STATUS = FOUND       CLINIC_IFC_IDENTITY_VERIFIED = YES    CLINIC_IFC_SCHEMA = IFC2X3
TARGET_ITWIN = MRTway Development Twin (bdf29ecd-b4a4-404d-861a-ac3061c7b12f)
ENGINEERING_FIXTURE_PRESERVED = YES
PROPOSED_CLOUD_INGESTION_PATH = ITWIN_STORAGE -> SYNCHRONIZATION_API_IFC -> SEPARATE_IMODEL

ITWIN_PLATFORM_SCOPE_AVAILABLE = YES   (config: DEFAULT_SCOPE = 'itwin-platform'; necessary, not sufficient)
BENTLEY_IMODEL_READ_ACCESS = YES       (working viewer confirms read)
BENTLEY_IMODEL_CREATE_ACCESS = UNKNOWN
  IMODEL_CREATE_REQUIRED_PERMISSION = imodels_manage on the iTwin OR Organization Administrator
BENTLEY_STORAGE_READ_ACCESS = UNKNOWN
BENTLEY_STORAGE_WRITE_ACCESS = UNKNOWN
  STORAGE_WRITE_REQUIRED_PERMISSION = storage_write on the project/iTwin OR Organization Administrator
BENTLEY_SYNCHRONIZATION_API_REACHABLE = YES   (public endpoint exists)
SYNCHRONIZATION_AUTHORIZATION_INFORMATION = UNKNOWN
BENTLEY_IFC_CONNECTOR_SUPPORTED = YES
EXISTING_SYNC_CONNECTIONS_READABLE = UNKNOWN   EXISTING_SYNC_CONNECTION_COUNT = NOT_AVAILABLE
WRITE_API_CALL_COUNT = 0
PERMISSION_PROBE_HTTP_RESULTS = NONE_EXECUTED_FROM_TERMINAL (token only in browser runtime)
```

## Readiness matrix

```
IFC_FILE = READY
IMODEL_READ = READY
IMODEL_CREATE = UNKNOWN
STORAGE_READ = UNKNOWN
STORAGE_WRITE = UNKNOWN
SYNCHRONIZATION_API = UNKNOWN (reachable; user authorization unknown)
IFC_CONNECTOR_SUPPORT = READY

CLOUD_IFC_INGESTION_READINESS = PARTIAL
```

`PARTIAL`, not `BLOCKED` (no proven denial) and not `READY` (no positive evidence of write permission).

## Blockers (exact)

```
BENTLEY_INGESTION_BLOCKERS =
  IMODEL_CREATE_PERMISSION_UNVERIFIED   (confirm imodels_manage on MRTway Development Twin, or Org Admin)
  STORAGE_WRITE_PERMISSION_UNVERIFIED   (confirm storage_write on the project/iTwin)
  SYNCHRONIZATION_AUTHORIZATION_UNVERIFIED (call authorizationinformation with the live token)
```

## How to resolve the UNKNOWNs (your choice)

- **Portal route (fastest):** open the MRTway Development Twin (`bdf29ecd-…`) in the Bentley iTwin portal → Members/Roles → confirm the signed-in user has a role granting `imodels_manage` and `storage_write` (or is Organization Administrator).
- **In-browser probe route:** authorize a small **read-only** DEV probe (a future prompt allowing a frontend change) that, inside the viewer runtime, issues GET-only calls with the existing token — user permissions on the iTwin (Access Control API), a Storage GET (200/403), and `GET /synchronization/imodels/connections/authorizationinformation`. No writes, no token logging.

## No writes performed (per sections 15 & 20)

```
DEMO_IMODEL_CREATED = NO   IFC_UPLOADED = NO
SYNCHRONIZATION_CONNECTION_CREATED = NO   SYNCHRONIZATION_RUN_STARTED = NO
FRONTEND_CODE_CHANGED = NO   AUTH_FLOW_CHANGED = NO   SECRET_EXPOSED = NO   CHECKPOINT = NONE
```

---

## Update — GET-only browser DEV probe implemented

The token constraint above is now resolved by an in-browser diagnostic (this turn was authorized to add exactly one read-only DEV probe).

```
PERMISSION_PROBE_IMPLEMENTED = YES
PERMISSION_PROBE_VISIBLE_IN_NORMAL_MODE = NO
PERMISSION_PROBE_VISIBLE_IN_DEVELOPER_MODE = YES
PERMISSION_PROBE_OUTPUT_TARGET = DEVELOPER_INSPECTOR
TOKEN_SOURCE = EXISTING_BROWSER_AUTH_RUNTIME (IModelApp.authorizationClient.getAccessToken)
TOKEN_LOGGED = NO   TOKEN_PERSISTENCE_CHANGED = NO   PROBE_RESPONSE_SANITIZATION = PASS
WRITE_API_CALL_COUNT = 0
DEMO_IMODEL_CREATED = NO   IFC_UPLOADED = NO
SYNCHRONIZATION_CONNECTION_CREATED = NO   SYNCHRONIZATION_RUN_STARTED = NO
AUTH_FLOW_CHANGED = NO   INTERACTION_CODE_CHANGED = NO   SPATIAL_SEMANTICS_CHANGED = NO   VISUAL_PLANNING_CHANGED = NO
TYPECHECK = PASS   OFFLINE_TEST_COUNT = 350   NEW_TEST_COUNT = 9   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5   WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES   /viewer = 200
CHECKPOINT = HOLD_FOR_MANUAL_PERMISSION_PROBE
```

### What it does (GET-only)

A new DEV-drawer button **PROBE BENTLEY CLOUD PERMISSIONS** acquires the bearer token from the existing runtime (`IModelApp.authorizationClient.getAccessToken()` — never logged/persisted) and issues GET-only calls, classifying each by HTTP status:

- `GET /imodels?iTwinId=<twin>` — iModel read + implicit scope check
- `GET /accesscontrol/itwins/<twin>/permissions` — checks the permissions array for `imodels_manage` and `storage_write`
- `GET /storage?iTwinId=<twin>` — storage read
- `GET /synchronization/imodels/connections/authorizationinformation` — sync authorization (`isUserAuthorized`)

Results (statuses + verdicts only, no payloads/token) render in the Developer Inspector. A pure Bentley-free `classifyBentleyPermissionProbe` maps them to `READY / PARTIAL / BLOCKED` + exact blockers (offline-tested: all-YES→READY, missing imodels_manage/storage_write→BLOCKED, sync 403→BLOCKED, 401→auth-scope BLOCKER, unknown→PARTIAL).

### Live results — PENDING_USER_RUN

Open `http://localhost:3000/viewer`, enable Developer mode, click **PROBE BENTLEY CLOUD PERMISSIONS**, and paste the Developer Inspector output back. I will then finalize:
`BENTLEY_IMODEL_CREATE_ACCESS`, `BENTLEY_STORAGE_READ_ACCESS`, `BENTLEY_STORAGE_WRITE_ACCESS`, `SYNCHRONIZATION_AUTHORIZATION_INFORMATION`, `PERMISSION_PROBE_HTTP_RESULTS`, and `CLOUD_IFC_INGESTION_READINESS`.
